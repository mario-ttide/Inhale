/* Inhale.exe, at the top of the Windows zip: what packaging/linux/AppRun is to the AppImage, for RecompLauncher
   (packaging/recomplauncher.json) and anyone else who starts the builder by its arguments.
     Inhale.exe                    the builder's window (gui\inhale_builder.py), as the installer's shortcut starts it
     Inhale.exe --cli <args>       nx2\make_game.py itself with the bundled tools, e.g. --cli --prepare --game <.nup> --out <dir>
     Inhale.exe --play [<dir>]     start the game built in <dir> (default %USERPROFILE%\Games\Inhale)
   --cli and --play wait for their program and return its exit code; its output goes where this program's goes, except
   the game's stderr: --play gives it none, so the game writes its own logs\inhale_log.txt (docs/design.md, "The game's
   log on a launcher start").
   Built by packaging/windows/build.sh: x86_64-w64-mingw32-clang -O2 -mwindows -municode -static -lshell32. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <string.h>
#include <wchar.h>

#define BIG 32768   /* (the longest path and command line Windows takes) */

static wchar_t dir[BIG];   /* the folder this program is in, without its last backslash */

static void say(const wchar_t *text) {
    HANDLE err = GetStdHandle(STD_ERROR_HANDLE);
    static char buf[4 * BIG];
    int n = WideCharToMultiByte(CP_UTF8, 0, text, -1, buf, sizeof buf, NULL, NULL);
    DWORD wrote;
    if (err && err != INVALID_HANDLE_VALUE && n > 1) WriteFile(err, buf, (DWORD)(n - 1), &wrote, NULL);
}

/* one argument onto the command line, quoted so CommandLineToArgvW and the C runtime read it back as it was */
static void quote(wchar_t *cmd, const wchar_t *arg) {
    size_t at = wcslen(cmd);
    if (at) cmd[at++] = L' ';
    if (*arg && !wcspbrk(arg, L" \t\n\v\"")) {
        wcscpy(cmd + at, arg);
        return;
    }
    cmd[at++] = L'"';
    for (const wchar_t *p = arg;; p++) {
        size_t slashes = 0;
        while (*p == L'\\') p++, slashes++;
        if (!*p) {   /* (backslashes before the closing quote are doubled) */
            while (slashes--) cmd[at++] = L'\\', cmd[at++] = L'\\';
            break;
        }
        if (*p == L'"') {   /* (and those before a quote, which is escaped) */
            while (slashes--) cmd[at++] = L'\\', cmd[at++] = L'\\';
            cmd[at++] = L'\\';
        } else {
            while (slashes--) cmd[at++] = L'\\';
        }
        cmd[at++] = *p;
    }
    cmd[at++] = L'"';
    cmd[at] = 0;
}

/* start cmd in cwd (NULL: this one) with this program's stdin and stdout and err as its stderr (NULL: none); wait: its exit
   code, else 0. -1 if it did not start */
static int run(const wchar_t *exe, wchar_t *cmd, const wchar_t *cwd, DWORD flags, BOOL wait, HANDLE err) {
    STARTUPINFOW si = {0};
    PROCESS_INFORMATION pi;
    si.cb = sizeof si;
    si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    si.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
    si.hStdError = err;
    if (!CreateProcessW(exe, cmd, NULL, NULL, TRUE, flags | CREATE_UNICODE_ENVIRONMENT, NULL, cwd, &si, &pi)) return -1;
    DWORD code = 0;
    if (wait) {
        WaitForSingleObject(pi.hProcess, INFINITE);
        GetExitCodeProcess(pi.hProcess, &code);
    }
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return (int)code;
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, PWSTR line, int show) {
    (void)inst, (void)prev, (void)line, (void)show;
    int argc;
    wchar_t **argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    static wchar_t exe[BIG], path[BIG], cmd[8 * BIG];   /* (cmd: room for every argument quoted; CreateProcessW refuses past BIG) */
    DWORD n = GetModuleFileNameW(NULL, dir, BIG);
    if (!argv || !n || n >= BIG) return 1;
    *wcsrchr(dir, L'\\') = 0;

    if (argc >= 2 && !wcscmp(argv[1], L"--cli")) {
        /* (the variables packaging/gui/tools_env.py build_env sets for the window's build) */
        _snwprintf(path, BIG, L"%ls\\llvm-mingw", dir);
        SetEnvironmentVariableW(L"LONGSHOT_MINGW", path);
        _snwprintf(path, BIG, L"%ls\\cpm", dir);
        SetEnvironmentVariableW(L"RX_CPM", path);
        SetEnvironmentVariableW(L"INHALE_MSVC", NULL);
        SetEnvironmentVariableW(L"PYTHONUTF8", L"1");
        SetEnvironmentVariableW(L"PYTHONUNBUFFERED", L"1");
        _snwprintf(exe, BIG, L"%ls\\python\\python.exe", dir);
        _snwprintf(path, BIG, L"%ls\\nx2\\make_game.py", dir);
        quote(cmd, exe);
        quote(cmd, L"-I");
        quote(cmd, path);
        for (int i = 2; i < argc; i++) quote(cmd, argv[i]);
        int code = run(exe, cmd, NULL, CREATE_NO_WINDOW, TRUE, GetStdHandle(STD_ERROR_HANDLE));   /* (the launcher reads its progress) */
        if (code == -1) say(L"Inhale: python\\python.exe did not start\n");
        return code == -1 ? 1 : code;
    }
    if (argc >= 2 && !wcscmp(argv[1], L"--play")) {
        if (argc >= 3) {
            wcsncpy(path, argv[2], BIG - 1);
        } else {
            wchar_t home[BIG];
            DWORD h = GetEnvironmentVariableW(L"USERPROFILE", home, BIG);
            if (!h || h >= BIG) return 1;
            _snwprintf(path, BIG, L"%ls\\Games\\Inhale", home);
        }
        _snwprintf(exe, BIG, L"%ls\\inhale.exe", path);
        if (GetFileAttributesW(exe) == INVALID_FILE_ATTRIBUTES) {
            _snwprintf(cmd, BIG, L"Inhale: no built game in %ls\n", path);
            say(cmd);
            return 1;
        }
        quote(cmd, exe);
        int code = run(exe, cmd, path, 0, TRUE, NULL);   /* (no stderr: the game opens its own log, as from its icon) */
        if (code == -1) say(L"Inhale: the game did not start\n");
        return code == -1 ? 1 : code;
    }
    /* (packaging/windows/inhale.nsi StartBuilder and its shortcuts: the same command) */
    _snwprintf(exe, BIG, L"%ls\\python\\pythonw.exe", dir);
    _snwprintf(path, BIG, L"%ls\\gui\\inhale_builder.py", dir);
    quote(cmd, exe);
    quote(cmd, L"-I");
    quote(cmd, path);
    for (int i = 1; i < argc; i++) quote(cmd, argv[i]);
    if (run(exe, cmd, NULL, 0, FALSE, GetStdHandle(STD_ERROR_HANDLE)) == -1) {
        MessageBoxW(NULL, L"python\\pythonw.exe did not start. Unpack the whole zip again.", L"Inhale", MB_ICONERROR);
        return 1;
    }
    return 0;
}
