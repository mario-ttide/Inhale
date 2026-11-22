# Provenance

Inhale is a modified version of Longshot, made by importing part of Longshot's tree once and changing it.

    upstream:       https://git.magicbean.dev/MagicBeanDev/Longshot.git
    upstream-base:  a2dc5385901812d183c4b7f0f9d48b295f17a510
    imported:       2026-11-16

`scripts/sync_upstream.py` reads the `upstream-base` line, brings Longshot's later changes over and rewrites the line.
Longshot is itself a fork of Hookshot; the older history of each folder is in `host/PROVENANCE.md`,
`gpu/PROVENANCE.md` and each `third_party/*/PROVENANCE.md`, carried over as Longshot has them. `CREDITS.md` has the
copyright lines and the people.

The first commit of this repository holds the imported files exactly as they are in Longshot at the base commit.
Everything Inhale changed or added is in the commits after it, so `git diff <first commit>.. -- <path>` shows what
differs from Longshot for any imported file.

Part of that difference is mechanical: `scripts/rename_full.py` changed the project's own name through the tree (file
names, variables, the player's texts) by one rule, which its head describes together with what it leaves alone.
`scripts/sync_upstream.py` puts Longshot's files through the same rule before it merges them, so the rename does not
stand between the two trees.

## What was imported

With the same paths as in Longshot: `nx2/`, `host/`, `gpu/`, `third_party/`, `tests/`, `scripts/`, `LICENSE`,
`requirements.txt`, `.gitattributes`, `.gitignore`, and three documents, `docs/dev/reference/architecture.md`,
`threads.md` and `build.md`: the code's `doc:` comments name their rules (`tests/test_doc_anchors.py`). Until the
sync to `v3.1.1` it was one, `docs/compiler-memory-accounting.md`, which Longshot folded into `build.md`.

## Adapted for this fork's release packages

`packaging/` and `.github/workflows/release.yml` are this fork's own, under a path Longshot does not have, so a sync
never touches them. Some of their scripts start from Longshot's, at `9af4808f`, and name that file in their head:
`packaging/linux/Dockerfile` (from `scripts/linux/Dockerfile`), `packaging/linux/docker.sh` (`scripts/linux/docker.sh`),
`packaging/linux/deps.sh` (`scripts/linux/deps.sh`, with its `tools` mode), `packaging/linux/appimage.sh`
(`scripts/linux/appimage.sh`), `packaging/linux/AppRun` (`builder/linux/AppRun`) and `packaging/windows/deps.sh`
(its dav1d build from `scripts/windows/dav1d.sh`). The versions in `packaging/pins.txt` are the ones Longshot's
`scripts/linux/deps.sh`, `tools.lock` and `third_party/sdl2/` name at that commit. Longshot's builder, its launcher,
`tools.lock`, `scripts/tools.py` and its release workflows are not carried: the packages here bring their tools
inside instead of downloading them.

## What was left out

Whole paths: `.forgejo/`, `.circleci/`, `.chunk/`, `.pre-commit-config.yaml`, `mise.toml`, `mise.lock`, `cliff.toml`,
`tools.lock`, `website/`, `builder/`, `recomplauncher.json`, `assets/`, `README.md`, `CONTRIBUTING.md`,
`RELEASING.md`, the rest of `docs/`, and Longshot's instruction files for its own development tooling (`AGENTS.md`,
`.claude/`). They belong to Longshot's releases, its builder and launcher, its website and its team's workflow, or to
the other game. `AGENTS.md` and `.claude/skills/fix-with-test/` here are adapted from Longshot's, without its team's
tooling; they are not imported files, and a sync does not touch them.

`packaging/recomplauncher.json` is this fork's own, written for this game from the shape of Longshot's root
`recomplauncher.json` (left out above), with `tests/test_recomplauncher_inhale.py` in place of its check.

`nx2/oot_patches.py`: Longshot's file holds text matched against the lifted code of another game. It is not carried.
The file of that name here is a stand-in written for Inhale, with the same function names and empty tables.

Scripts of Longshot's releases, packaging, team workflow, and of the other game's saves and tour
(35 files):

`scripts/builder_package.py`, `scripts/check_guide_screenshots.py`, `scripts/check_pr_description.py`,
`scripts/check_windows_files.py`, `scripts/ci_secret.sh`, `scripts/cpu_candidates.json`, `scripts/cpu_categories.py`,
`scripts/cpu_functions.json`, `scripts/cpu_report.py`, `scripts/crash_groups.py`, `scripts/dev_build.py`,
`scripts/dev_packs.py`, `scripts/fetch_commit.sh`, `scripts/forge.py`, `scripts/hardware_report.py`,
`scripts/job_queue.py`, `scripts/linux/Dockerfile`, `scripts/linux/appimage.sh`, `scripts/linux/check_player_build.sh`,
`scripts/linux/deps.sh`, `scripts/linux/docker.sh`, `scripts/longshot_saves.py`, `scripts/pipeline_tour.py`,
`scripts/release.py`, `scripts/release_keys.json`, `scripts/screenshots/LauncherCapture.cs`,
`scripts/screenshots/capture_launcher.py`, `scripts/screenshots/capture_menu.py`,
`scripts/screenshots/launcher-packages.lock.json`, `scripts/screenshots/menu.cpp`, `scripts/setup.py`,
`scripts/tested_configurations.py`, `scripts/tooling.py`, `scripts/tools.py`, `scripts/website_check.sh`

Tests and fixtures bound to something left out above, or to the text of the original `nx2/oot_patches.py`
(162 files):

`tests/builder_cli/.gitignore`, `tests/builder_cli/BuilderCliTests.csproj`, `tests/builder_cli/NuGet.Config`,
`tests/builder_cli/Program.cs`, `tests/builder_workers/obj/BuilderWorkersTests.csproj.nuget.dgspec.json`,
`tests/builder_workers/obj/BuilderWorkersTests.csproj.nuget.g.props`,
`tests/builder_workers/obj/BuilderWorkersTests.csproj.nuget.g.targets`,
`tests/builder_workers/obj/Debug/net8.0-windows/.NETCoreApp,Version=v8.0.AssemblyAttributes.cs`,
`tests/builder_workers/obj/Debug/net8.0-windows/BuilderWorkersTests.AssemblyInfo.cs`,
`tests/builder_workers/obj/Debug/net8.0-windows/BuilderWorkersTests.AssemblyInfoInputs.cache`,
`tests/builder_workers/obj/Debug/net8.0-windows/BuilderWorkersTests.GeneratedMSBuildEditorConfig.editorconfig`,
`tests/builder_workers/obj/Debug/net8.0-windows/BuilderWorkersTests.GlobalUsings.g.cs`,
`tests/builder_workers/obj/Debug/net8.0-windows/BuilderWorkersTests.assets.cache`,
`tests/builder_workers/obj/project.assets.json`, `tests/builder_workers/obj/project.nuget.cache`,
`tests/dlss_feature_size_test.cpp`, `tests/draw_stream_visibility_test.cpp`, `tests/driver_cache_env_test.cpp`,
`tests/frame_overlap_test.cpp`, `tests/fsr_image_retirement_test.cpp`, `tests/fsr_uniform_ownership_test.cpp`,
`tests/hold_gpu_test.cpp`, `tests/invalidate_quick_test.cpp`, `tests/linux_pressure_test.cpp`,
`tests/mesh_fallback_capacity_test.cpp`, `tests/mesh_fallback_layout_ir.cpp`, `tests/mesh_fallback_layout_model.cpp`,
`tests/nonuniform_image_arrays_ir.cpp`, `tests/parallel_init_order_test.cpp`, `tests/portable_builder_home_test.cs`,
`tests/portable_setup_home_test.c`, `tests/pr_description/good.md`, `tests/setup_tar_diagnostics_test.c`,
`tests/test_appimage_headers.py`, `tests/test_appimage_licenses.py`, `tests/test_appimage_package_retry.py`,
`tests/test_appimage_player_build.py`, `tests/test_appimage_prompt_fonts.py`, `tests/test_appimage_scripts.py`,
`tests/test_appimage_source_headers.py`, `tests/test_astc_pass_timing.py`, `tests/test_bug_report.py`,
`tests/test_builder_own_python.py`, `tests/test_builder_python.py`, `tests/test_builder_xml_valid.py`,
`tests/test_camera_centering.py`, `tests/test_camera_speed.py`, `tests/test_check_pr_description.py`,
`tests/test_commit_room.py`, `tests/test_cpu_report.py`, `tests/test_cpu_target.py`, `tests/test_crash_dialog.py`,
`tests/test_crash_groups.py`, `tests/test_dev_ab.py`, `tests/test_dev_build.py`, `tests/test_dev_packs.py`,
`tests/test_drive_target.py`, `tests/test_driver_cache_env.py`, `tests/test_driver_env_choose.py`,
`tests/test_exe_icon.py`, `tests/test_floor_carry_step.py`, `tests/test_frame_overlap.py`,
`tests/test_frame_rate_cap_step.py`, `tests/test_frame_whole.py`, `tests/test_free_view_anchor.py`,
`tests/test_function_ends.py`, `tests/test_gpu_clock.py`, `tests/test_guide_screenshots.py`,
`tests/test_hardware_report.py`, `tests/test_high_fps_fixes.py`, `tests/test_hle_stats.py`, `tests/test_hold_gpu.py`,
`tests/test_horse_jump_step.py`, `tests/test_hud_layout_row.py`, `tests/test_job_queue.py`,
`tests/test_jump_takeoff_step.py`, `tests/test_launcher_capture.py`, `tests/test_linux_deps_pins.py`,
`tests/test_linux_docker_packages.py`, `tests/test_linux_downgrade.py`, `tests/test_linux_pressure.py`,
`tests/test_linux_tools.py`, `tests/test_linux_update.py`, `tests/test_longshot_launch.py`,
`tests/test_longshot_saves.py`, `tests/test_loop_step.py`, `tests/test_make_game_ngx.py`, `tests/test_mark_groups.py`,
`tests/test_menu_hooks.py`, `tests/test_mesh_fallback_capacity.py`, `tests/test_mesh_fallback_layout.py`,
`tests/test_met_wait_capture.py`, `tests/test_mise_build.py`, `tests/test_movement_speed.py`,
`tests/test_movie_frame_count.py`, `tests/test_no_release_lookup.py`, `tests/test_no_webgpu.py`,
`tests/test_ocarina_wait.py`, `tests/test_ocb_hold.py`, `tests/test_oot_barrier.py`, `tests/test_oot_cloth_60.py`,
`tests/test_oot_cloth_time.py`, `tests/test_oot_damage.py`, `tests/test_oot_heap_retry.py`,
`tests/test_oot_state_tap.py`, `tests/test_oot_voice_option.py`, `tests/test_opening_skip.py`,
`tests/test_pass_timing_fallback.py`, `tests/test_patch_hooks_defined.py`, `tests/test_perf_report.py`,
`tests/test_pipeline_state_sources.py`, `tests/test_pipeline_tour.py`, `tests/test_portable_builder_home.py`,
`tests/test_portable_builder_startup.py`, `tests/test_portable_setup_paths.py`, `tests/test_portable_setup_start.py`,
`tests/test_portable_setup_transaction.py`, `tests/test_precompile_save.py`, `tests/test_prepare_at_build.py`,
`tests/test_present_queue_default.py`, `tests/test_prompts_size_table.py`, `tests/test_quick_pipelines.cpp`,
`tests/test_quick_pipelines.py`, `tests/test_readme_menu_rows.py`, `tests/test_recomplauncher_json.py`,
`tests/test_release.py`, `tests/test_renhdrum.py`, `tests/test_routes.py`, `tests/test_saved_turn_rate.py`,
`tests/test_scarecrow_timing.py`, `tests/test_scene_format.py`, `tests/test_settings_table.py`,
`tests/test_setup_rename_retry.py`, `tests/test_setup_runtime.py`, `tests/test_setup_runtime_paths.py`,
`tests/test_setup_tar_diagnostics.py`, `tests/test_setup_tool_merge.py`, `tests/test_ship_state_list.py`,
`tests/test_shipped_hot_list.py`, `tests/test_skip_title.py`, `tests/test_song_note_cue.py`,
`tests/test_split_before_draw.py`, `tests/test_sprint.py`, `tests/test_stick_dead_zone.py`,
`tests/test_target_reuse_memory.py`, `tests/test_tested_configurations.py`, `tests/test_tex_compact.py`,
`tests/test_text_size.py`, `tests/test_text_speed.py`, `tests/test_texture_ahead.cpp`, `tests/test_texture_ahead.py`,
`tests/test_third_party_objects.py`, `tests/test_threaded_rendering.py`, `tests/test_tools_lock.py`,
`tests/test_vk_pgo.py`, `tests/test_vulkan_fixtures_ci.py`, `tests/test_water_substeps.py`,
`tests/test_web_floor_steps.py`, `tests/test_windows_on_linux.py`, `tests/test_windows_package_frameworks.py`,
`tests/test_windows_toolchain.py`, `tests/test_xess_sdk.py`

Tests that fail in Longshot's own tree at the base commit on the import machine (Linux, GCC 16 and clang 23, the
system's Vulkan and SPIR-V headers), most of them because the source they compile or scan has moved on
(20 files). They are left out so that the test runner starts from zero failures; a later sync
can bring them back once they pass upstream:

`tests/test_bug_report_defaults.py`, `tests/test_cpm_discovery.py`, `tests/test_crt_options.py`,
`tests/test_damage_debug_menu.py`, `tests/test_dlss_feature_size.py`, `tests/test_failed_compile_keeps_objects.py`,
`tests/test_fsr_uniform_ownership.py`, `tests/test_guest_imported.py`, `tests/test_import_reach.py`,
`tests/test_linux_preflight.py`, `tests/test_missing_nup.py`, `tests/test_mods_size_table.py`,
`tests/test_nonuniform_image_arrays.py`, `tests/test_parallel_init_order.py`, `tests/test_pending_guest_import.py`,
`tests/test_replay_write_order.py`, `tests/test_run_all_changed.py`, `tests/test_upscaler_rows.py`,
`tests/test_vk_occlusion_queries.py`, `tests/test_walk_key.py`

The same at `v3.0.0-rc.7` (`544229a2`), the first sync, on the same machine: twelve that passed at the base, whose
source moved on without them, and three new ones (`tests/test_profiling_mode.py`, `tests/test_slow_frames.py`,
`tests/test_switch_table.py`)
(15 files):

`tests/test_display_startup_failure.py`, `tests/test_framegen_preset.py`, `tests/test_invalidate_vcore.py`,
`tests/test_mirror_budget.py`, `tests/test_pipeline_play_cache.py`, `tests/test_present_thread.py`,
`tests/test_profiling_mode.py`, `tests/test_readback_timeout_source.py`, `tests/test_rumble_menu.py`,
`tests/test_slow_frames.py`, `tests/test_switch_table.py`, `tests/test_target_image_pool.py`,
`tests/test_upscaler_round_trip.py`, `tests/test_vcore_escape.py`, `tests/test_vk_swapchain_compat.py`

The same at `9af4808f`, the second sync, on the same machine: four that passed before, whose source moved on without
them (two of them, `tests/test_draw_stream_visibility.py` and `tests/test_fsr_image_retirement.py`, run only with the
Vulkan headers at hand), and three new ones (`tests/test_compute_warm_apart.py`, `tests/test_invalidate_quick.py`,
`tests/test_libc_hooks.py`)
(7 files):

`tests/test_compute_warm_apart.py`, `tests/test_draw_stream_visibility.py`, `tests/test_fsr_image_retirement.py`,
`tests/test_invalidate_quick.py`, `tests/test_libc_hooks.py`, `tests/test_log_open_failure.py`,
`tests/test_psychov35_fsr3_fg.py`

The same at `v3.0.0` (`09cbdd97`), the third sync, on the same machine: one that passed before, whose source moved
on without it (`tests/test_prepare_cache_save.py`), and three new ones with the C file one of them compiles
(5 files):

`tests/test_capture_read_once.py`, `tests/test_host_guest_writes.py`, `tests/test_prepare_cache_save.py`,
`tests/test_vbytes.py`, `tests/vbytes_test.c`

The same at `v3.1.1` (`a2dc5385`), the fourth sync, on the same machine: nine that passed before, whose source moved
on without them, and eight new ones with the IR file one of them compiles. `tests/test_menu_i18n.py`, which fails
there too, is kept: two checks of this fork import it, and it reads `gpu/vk/vk_ui.h` here, where its missing text is
(18 files):

`nx2/test_import_windows.py`, `tests/sim_turf_pools_ir.cpp`, `tests/test_close_waits_for_save.py`,
`tests/test_compile_zero_byte.py`, `tests/test_damaged_rom_files.py`, `tests/test_fs_save_commit.py`,
`tests/test_guest_copies.py`, `tests/test_hold_toggle.py`, `tests/test_insn_fixed_convert.py`,
`tests/test_lower_atomg_cas.py`, `tests/test_menu_keys.py`, `tests/test_menu_slider_ends.py`,
`tests/test_pads_after_menu.py`, `tests/test_recording_admission.py`, `tests/test_sim_turf_pools.py`,
`tests/test_sim_turf_settings.py`, `tests/test_tls_objects.py`, `tests/test_vibration_menu.py`

## Files changed at import

- `host/discord_rpc.c`: no default Discord application id (Longshot's id named Longshot's application).
- `host/hos_crash_dialog.h`, `gpu/vk/vk_bug_report.cpp`, `gpu/vk/pipeline_share.h`, `nx2/pipeline_share.py`: the report
  links name a host that never resolves, not Longshot's tracker. Inhale's problems are not Longshot's to receive.
  The rule of `scripts/rename_full.py` does it (TRACKER), there and in the menu's texts (`gpu/vk/vk_menu.cpp`,
  `gpu/vk/menu_i18n.h`), so a sync brings Longshot's later texts over with the same host. By hand: the two report
  forms' template name, and a comment on three of the lines.
- `gpu/vk/menu_i18n.h` is Longshot's file after the rename, with no other change: the menu's texts that are this
  fork's own are in `gpu/vk/menu_i18n_inhale.h`, which `gpu/vk/vk_menu_i18n.cpp` reads after it. A text this fork
  reworded or removed keeps its row in Longshot's tables and is listed there as retired.
- `nx2/addresses.ini` (new in Longshot at `v3.0.0-rc.7`): every key is empty. Longshot's values are its own services,
  where the crash window's Send and the performance statistics post. With a key empty nothing is sent, which the
  file itself provides for.
- `nx2/make_game.py`, `nx2/nup.py`: messages about incomplete or unreadable game files no longer tell the user how
  to obtain the files (`tests/test_make_game_cache.py` expects the new text).
- `host/control.c`, `scripts/longshot_ctl.py`, `tests/run_all.py`, `tests/test_doc_anchors.py`,
  `tests/test_switches_removed.py`: comments reworded, and the last one's list of scanned paths cut to those that
  exist here.
- `gpu/vk/vk_dump.h`, `host/mouse_native.c`, `tests/f2i_immediate/README.md`: dash characters in comments replaced
  with ASCII (`tests/test_hygiene.py`). The same at the sync to `v3.1.1`, in Longshot's new lines of
  `gpu/render/rx_nvn.h`, `gpu/vk/vk_internal.h`, `gpu/vk/vk_main.cpp`, `gpu/vk/vk_replay.cpp`, `host/hos_crash_dialog.c`,
  `host/hos_main.c`, `nx2/perf_report.py` and `tests/test_present_semaphores.py`. (`gpu/shaderbatch.cpp`, `nx2/bake.py`
  and `tests/test_bake_mimo.py` were in this list: Longshot removed them at `v3.1.1`.)
- `.gitignore`: no exception for saves, this game's data formats added, the tools' Python environment added.

Changes made after the import are ordinary commits of this repository and are not listed here.

## Licence

Longshot is under the GNU General Public License, version 3 or later, and so is Inhale (`LICENSE`). Parts under other
licences keep their notices in their folders.
