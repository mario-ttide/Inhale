"""Game-free checks of packaging/recomplauncher.json, RecompLauncher's manifest (adapted from upstream's
tests/test_recomplauncher_json.py): every settings key is a row this game's menu shows, the build goes into the folder the
launcher plays, and the packages carry the file and the programs it names.

Run with: python -I -B tests/test_recomplauncher_inhale.py
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)
from srccut import block, between
from menu_model_fixture import module_rows  # noqa: E402

MANIFEST = ROOT / "packaging" / "recomplauncher.json"


def manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def read(*parts):
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def menu_keys():
    """{ini key: hidden for this game} for each menu row with a value (vk_menu.cpp rows, ini_key, is_oot_row; and since
    upstream's #1633 the rows its modules describe, gpu/vk/menu/*.cpp, each with its own key)"""
    menu = read("gpu", "vk", "vk_menu.cpp")
    special = dict((field, key) for field, key in
                   re.findall(r'if \(r\.value == &opts\.(\w+)\) return "([a-z_0-9]+)";',
                              block(menu, "const char* ini_key(const Row& r) {")))
    hidden = set(re.findall(r"&opts\.(\w+)", block(menu, "bool is_oot_row(const Row& r) {")))
    keys = {}
    for name, field in re.findall(r'\{TAB_[A-Z]+, "([^"]+)", &opts\.(\w+),', menu):
        keys[special.get(field, name.lower().replace(" ", "_"))] = field in hidden
    for row in module_rows():
        field = re.fullmatch(r"&opts\.(\w+)", row.get("value", ""))
        if field and "key" in row:
            keys[row["key"].strip('"')] = field.group(1) in hidden
    return keys


class RecompLauncherInhaleTests(unittest.TestCase):
    def test_settings_are_rows_this_game_shows(self):
        m = manifest()
        self.assertEqual(m["format"], 1)
        rows = menu_keys()
        self.assertIn("frame_generation", rows)
        self.assertTrue(rows["text_speed"], "is_oot_row no longer read: Text speed is a hidden row")
        keys = {key for setting in m["settings"] for choice in setting["choices"] for key in choice["set"]}
        self.assertTrue(keys)
        # (Compile shaders: no menu row, read by the preparation and the game, nx2/make_game.py and vk_draw.cpp compile_all)
        elsewhere = {"compile_shaders"} if '"compile_shaders="' in read("gpu", "vk", "vk_draw.cpp") else set()
        self.assertEqual(keys - set(rows) - elsewhere, set())
        # (a row hidden for this game is one its code never reads: docs/design.md, "The in-game menu")
        self.assertEqual({k for k in keys if rows.get(k)}, set())
        for setting in m["settings"]:
            for key, value in setting["defaults"].items():
                self.assertIn({key: value}, [c["set"] for c in setting["choices"]], setting["id"])

    def test_frame_generation_offers_no_fixed_multiplier(self):
        # (README, Project status: a fixed 2x and up can freeze the game for a few seconds; Auto works)
        (fg,) = [s for s in manifest()["settings"] if "frame_generation" in s["defaults"]]
        self.assertEqual(sorted(c["set"]["frame_generation"] for c in fg["choices"]), ["0", "1"])

    def test_builds_into_the_launchers_game_folder(self):
        # (RecompLauncher issue 215: without --out the build went to ~/Games, not the drive the player installed to. The
        # folder it builds into is the one it plays, and the settings and saves live in it)
        m = manifest()
        prepare = m["prepare"]["args"]
        out = prepare[prepare.index("--out") + 1]
        self.assertTrue(out.startswith("{install}/"))
        self.assertEqual(prepare[:2], ["--cli", "--prepare"])
        self.assertEqual(prepare[prepare.index("--game") + 1], "{game}")
        self.assertEqual(m["start"]["args"], ["--play", out])
        self.assertEqual(m["folders"]["game"][0]["path"], out)
        self.assertEqual(m["config"][0]["file"][0]["path"], out + "/inhale_options.ini")
        self.assertIn(out + "/user", m["saves"])
        self.assertNotIn("{home}/Games", json.dumps(m))

    def test_build_id_is_make_games(self):
        bid = re.search(r'^BUILD_ID = "([0-9a-f]+)"', read("nx2", "make_game.py"), re.M).group(1)
        self.assertEqual(manifest()["game"]["check"]["nup_build_id"], bid)
        self.assertIn(bid, manifest()["game"]["label"])

    def test_programs_are_the_release_packages(self):
        m = manifest()
        self.assertEqual(m["start"]["program"], m["prepare"]["program"])
        files = re.search(r"files=\(([^)]*)\)", read(".github", "workflows", "release.yml")).group(1).split()
        self.assertIn("dist/Inhale-x86_64.AppImage", files)
        self.assertIn("dist/Inhale-Windows-x64.zip", files)
        self.assertEqual(m["start"]["program"], ["Inhale-x86_64.AppImage", "Inhale.exe"])
        self.assertIn('packaging/stamp_manifest.py "$APPDIR/recomplauncher.json" "$VERSION"', read("packaging", "linux", "appimage.sh"))

    def test_windows_zip_has_both_at_its_top(self):
        build = read("packaging", "windows", "build.sh")
        self.assertIn('-o "$S/Inhale.exe" packaging/windows/inhale_launch.c', build)
        self.assertIn('packaging/stamp_manifest.py "$S/recomplauncher.json" "$VERSION"', build)
        self.assertIn('python3 -I - "$S" "$B/Inhale-Windows-x64.zip" <<\'PY\'', build)
        script = between(build, "<<'PY'\n", "\nPY\n")[len("<<'PY'\n"):]
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / "stage"
            (stage / "python").mkdir(parents=True)
            (stage / "Inhale.exe").write_bytes(b"MZ")
            (stage / "recomplauncher.json").write_text("{}")
            (stage / "python" / "python.exe").write_bytes(b"MZ")
            os.chmod(stage / "Inhale.exe", 0o755)
            out = Path(tmp) / "Inhale-Windows-x64.zip"
            subprocess.run([sys.executable, "-I", "-c", script, str(stage), str(out)], check=True)
            with zipfile.ZipFile(out) as z:
                self.assertEqual(z.namelist(), ["Inhale.exe", "python/python.exe", "recomplauncher.json"])
                self.assertEqual({i.date_time for i in z.infolist()}, {(1980, 1, 1, 0, 0, 0)})
                self.assertEqual(z.getinfo("Inhale.exe").external_attr >> 16, 0o100755)
            first = out.read_bytes()
            os.utime(stage / "Inhale.exe", (0, 0))
            subprocess.run([sys.executable, "-I", "-c", script, str(stage), str(out)], check=True)
            self.assertEqual(out.read_bytes(), first)

    def test_packages_stamp_the_release_into_prepare_version(self):
        # (RecompLauncher runs prepare again only when prepare.version changes, "not even a new release" otherwise: with
        # "1" in every package, v0.3.0's update kept playing the v0.2.0 build. Each package's manifest line, run with a
        # release name, must leave that name in prepare.version)
        for script, var in ((("packaging", "linux", "appimage.sh"), "APPDIR"), (("packaging", "windows", "build.sh"), "S")):
            (line,) = [l for l in read(*script).splitlines() if f'"${var}/recomplauncher.json"' in l]
            with tempfile.TemporaryDirectory() as tmp:
                env = dict(os.environ, VERSION="v9.8.7-0-gabcdef0", **{var: tmp})
                subprocess.run(["bash", "-euc", line], cwd=ROOT, env=env, check=True)
                out = json.loads((Path(tmp) / "recomplauncher.json").read_text(encoding="utf-8"))
            self.assertEqual(out["prepare"]["version"], "v9.8.7-0-gabcdef0", script)
            out["prepare"]["version"] = manifest()["prepare"]["version"]
            self.assertEqual(out, manifest(), script)

    def test_launcher_runs_make_game_as_apprun_does(self):
        c = read("packaging", "windows", "inhale_launch.c")
        cli = between(c, 'if (argc >= 2 && !wcscmp(argv[1], L"--cli")) {', 'if (argc >= 2 && !wcscmp(argv[1], L"--play")) {')
        for text in ('quote(cmd, L"-I");', r'L"%ls\\nx2\\make_game.py"', r'L"%ls\\python\\python.exe"',
                     'L"PYTHONUNBUFFERED", L"1"', 'L"PYTHONUTF8", L"1"', r'L"%ls\\llvm-mingw"', r'L"%ls\\cpm"',
                     "CREATE_NO_WINDOW, TRUE"):
            self.assertIn(text, cli)
        play = between(c, 'if (argc >= 2 && !wcscmp(argv[1], L"--play")) {', "/* (packaging/windows/inhale.nsi")
        self.assertIn(r'L"%ls\\inhale.exe"', play)
        self.assertIn(r'L"%ls\\Games\\Inhale"', play)
        self.assertNotIn("SetEnvironmentVariableW", play)
        # (the window's command, as the installer's shortcut has it)
        self.assertIn(r'"$INSTDIR\python\pythonw.exe" -I "$INSTDIR\gui\inhale_builder.py"', read("packaging", "windows", "inhale.nsi"))
        self.assertIn(r'L"%ls\\gui\\inhale_builder.py"', c)
        self.assertNotIn("CP_ACP", c)


if __name__ == "__main__":
    unittest.main()
