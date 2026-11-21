# Changelog

All notable changes to OP2TestHarness. Versions follow [Semantic Versioning](https://semver.org/); the version is in
`VERSION`, and each release is tagged `vX.Y.Z`. The rules below hold from 1.0.0 on: the contract is op2-rs's, which
its recordings already depend on.

## Versioning rules

op2-rs and other users replay recorded runs against this harness, and those recordings depend on **the contract**:

- **Environment and options:** the `OP2H_*` environment variables and the `run.sh` / `run.py` options.
- **Script verbs and their meaning:** README.md "Scripted input" and the sections after it.
- **Unit names:** `$NAME`, `as NAME` and `$TYPE@x,y`.
- **Output fields:** the telemetry and trace JSONL fields, `gamedata.json`, `start_info.json`, the audio log and the
  screenshots.
- **The scenario JSON format.**

How a change moves the version:

- **MAJOR:** a change to the contract that can change a recorded run's output or break an existing script or option:
  a renamed or removed variable, option, verb or field, a verb or field whose meaning changes, a different screenshot.
- **MINOR:** additions that leave every existing recording replaying identically: a new verb, option, variable or output
  field, a new launcher or platform (e.g. a Windows launcher).
- **PATCH:** fixes and changes that don't touch the contract: docs, build scripts, launcher fixes, crash fixes in paths no
  recording uses.

Every release notes its contract changes, if any, under **Contract**. A release is only made from a commit whose
`harness.dll` replays op2-rs's recorded runs identically (op2-rs's `make accuracy`, 0 failures) unless its changelog
says which runs change and why.

## Unreleased

**Added** (MINOR: every existing recording replays identically)
- `windows/trace_diff.py` compares every trace field both sides write: each unit's `cmd`, `action`, `busy`, `ipx`/`ipy`,
  `dest`, `path` (part by part, or as `path` when only one side has one) and `tiles`, and per tick `fx`, `ents`, `alloc`
  (without stale ring slots and the ring's [head, tail]) and `reused`, for marcelomgoncalves/outpost2's fuller trace.
- `windows/gamedata_diff.py`: compares two `gamedata.json` files field by field (map, cell types, unit types and their
  stats words, the `--eco` tables, every tile's cell type); `compare_port.py` compares the port's with the original's.
- `windows/telemetry_diff.py` compares input runs' `selected` and `view`. `run_port.py` runs the port at
  `--size 1056x800`, whose client (inside the frame the port draws) is the original's 1032x766, so the input verbs'
  pixel positions land on the same spot.

## 1.3.0 (2026-11-21)

**Contract:** one change to what screenshots show: health bars, under **Changed** (frames with damaged units differ
from 1.0.0's; telemetry, traces and every other output field are unchanged). The rest are additions that leave every
existing recording replaying identically.

**Changed** (screenshots of damaged units change)
- Every launch on OPU 1.4.1 (mission runs, scenarios, shell sessions) sets `ShowUnitHPBars=0` in the game's own
  `OPU/outpost2.ini` first: health bars only on the selected unit and the one under the mouse, as in the original
  1.2, not OPU's bars on every damaged unit. OPU reads the setting at startup, before the harness points the game at
  its private outpost2.ini, so setting it in the private copy alone left OPU's bars on (measured with
  `hp_bars.json`: the game ini at 1 or 0 changes 7 of its 8 frames; the private copy's value changes none).
  `OP2H_INI_ShowUnitHPBars=1` keeps OPU's. On Linux the play prefix's ini is never written.

**Added** (MINOR: every existing recording replays identically)
- `harness.dll` has a version resource: its file version (from `VERSION`) and the description "OP2TestHarness",
  shown in Explorer's Details tab (`src/harness.rc`; `make` builds it with windres, `build.bat` with rc).
- `windows/telemetry_diff.py`: compares two `telemetry.jsonl` files field by field (players and their `eco` fields,
  units by id, beacons). `compare_port.py` compares the port's telemetry with the original's as well, and a scenario
  with no trace on its telemetry alone. `run_port.py` passes the scenario's `telemetryEvery` and `eco`, and installs
  from marcelomgoncalves/outpost2's checkout by default.
- `--map-every N` (`OP2H_MAP_EVERY`), `--map-px N`, `--map-night`: a whole-map image in the game's own drawing and
  `state_<tick>.json`, the state it shows, every N ticks (README.md "Whole-map images"). A run's telemetry is the
  same with and without them.
- Whole-map states list what the game drew for the image (`views`: every sprite, laser and microwave line, piece by
  piece, and `viewSize`), each object's animation, frame and flags, the animated tiles' counter (`animCounter`) and
  the image's size (`px`, `shown`): enough to draw the image again, pixel for pixel, without the game.
  Whole-map images skip units' overlays (health bars, selection marks), and the DLL writes them as PNGs itself, with
  an encoder whose output is fixed (README.md "Whole-map images", File): the same pixels always give the same file,
  so images can be compared by hash.
  `OP2H_MAP_DRAWS=0` leaves `views` out. A piece whose view the game moves while drawing it is drawn again (the log
  says so), so no piece has an undrawn strip.
- `netgame.py --lobby-chat "HOST|JOINER"`: the host and the first joiner chat in GAME SETTINGS once every joiner is
  ready; each machine shoots and dumps its lobby after each line.
- `netgame.py --join-ticks T`: the first joiner plays only to tick T (its script leaves the game there: End Mission, a
  quit), then waits for the host to end.
- `netgame.py --ends`: every copy waits for its game to end by itself (a quit, a victory) after `--ticks` (or
  `--join-ticks`) instead of quitting there.
- After a player quits (command 49), the copies' telemetry is compared up to the tick the Quit ran: from then on each
  machine keeps its own view of who is human.
- OPU 1.3.6 (OPU's patched `Outpost2.exe` 1.3.0.6, op2ext with `LoadAddons`), for mods made for it.
  Its op2ext calls `InitMod` as it loads, before the game's static data and command line, so `harness.dll` then waits
  for WinMain's `TApp::Init()` call (0x4A8877), where OPU 1.4.1's op2ext calls it. On 1.4.1 nothing changes.
  `run_win.py` takes a 1.3.x copy (no `OPU` folder): `setup` lists the module in the game folder's `outpost2.ini`
  (`LoadAddons`) and refuses an op2ext without it; `selftest` and `run` pass there. `launch()` takes extra arguments
  (`/loadmod NAME`). 1.3.x's op2ext doesn't call `RunMod`, so shell mode isn't available there, and a mission that ends
  through the shell isn't noticed (`--ticks` or the timeout end it).
  On 1.3.x the harness also puts back the process command line after `TApp::ParseCommandLine()` has cut it up in
  place: that op2ext reads `/loadmod NAME` from it on every `GetCurrentModDir()` call, and failed ("ModMgr.cpp:38:
  Argument missing") for mod DLLs calling it later.
- `--unload` / `OP2H_UNLOAD=1`: unload the mission DLL before the run quits, so its `DLL_PROCESS_DETACH` runs (some
  campaign missions write their carry-over there). Off by default.
- `OP2H_CRASHLOG=1`: `crash.txt` with the start-up stages, every fault (module, offset, stack) and the loaded modules.
- On OPU 1.3.0.5's op2ext, the harness fixes an overflow in its `/loadmod` start. `GetCurrentModDir()` returns
  `_strdup(the mod folder)` and the start appends `\op2mod.dll` to that copy (`strcat`, 0x1000144D), 11 bytes past
  the block. Depending on the heap's layout (the environment moves it; an administrator window happened to miss) the
  game died in ntdll at start. The harness makes that copy long enough, and `harness.log` says so.
- `OP2H_ALL_UNITS=1`: the telemetry, trace, state and unit scans also cover the players beyond the lobby, up to player
  6 (a mission's own enemy). Off by default.
- Lobby choices for a multiplayer start: `OP2H_MP_DISASTERS`, `OP2H_MP_DAYNIGHT`, `OP2H_MP_MORALE_STEADY` (0/1),
  `OP2H_MP_VEHICLES` (initial vehicles 0-9), and one digit per player in `OP2H_MP_RESOURCES` (0 high, 1 medium, 2 low)
  and `OP2H_MP_COLONY` (1 Eden, 0 Plymouth). Unset, the start is as before.
- Script `peek *ADDRESS N`: logs the memory the pointer stored at ADDRESS points to (a mission's vector items).

## 1.0.0 (2026-11-10)

The first version as a repository of its own (op2-rs issue #34), shown to work for the three projects it measures for:
the original game, op2-rs and outpost2-port (see **Verified**). It was developed as 0.9.0, which was never released.

**Contract:** identical to op2-rs's `harness/` at commit ab5f74dd (2026-11-09): the same `OP2H_*` variables, `run.sh`
options, script verbs, unit names, output fields and scenario format. `src/harness.cpp` behaves as op2-rs's; it differs
only in comments and in the command line written into a recording's header.

**History:** op2-rs's `harness/` history, filtered with `git filter-repo` and without `oracle/` (PROVENANCE.md).

**Added**
- `windows/`: an MSVC build of every DLL a release ships, reproducible with `/Brepro` (`build.bat`, `msvc_compat.h`:
  `harness.dll`, `zScenario.dll`, `zHarnessEnd.dll` and the seven bots); a native Windows launcher that plays scenarios
  in a private copy of the game, without Wine, with an optional bot (`run_win.py`), and its `selftest`, the Makefile's
  `make check` on Windows; the release zip with `SHA256SUMS` (`package.py`); the original vs op2-rs on one
  scenario, with op2-sim's tick-by-tick compare and both pictures side by side (`compare.py`); the original vs
  outpost2-port (`run_port.py`, `trace_diff.py`, `compare_port.py`).
- CI (GitHub Actions): both toolchains build all ten DLLs on every push (`make` with MinGW on Ubuntu, `build.bat` with
  MSVC on Windows), each build must be reproducible, and a `vX.Y.Z` tag publishes a GitHub release with
  `OP2TestHarness-<VERSION>-mingw.zip` and `-msvc.zip`, their `.sha256` and this changelog's section.
- `ARCHITECTURE.md`, `PROVENANCE.md`, this changelog, `VERSION`, `.gitignore`, `.gitattributes`.

**Changed**
- README.md describes a project of its own: Windows and Linux quick starts, requirements, where prefixes and the game
  copy live, and "Comparing with op2-rs". op2-rs's scenarios stay in op2-rs (`harness/oracle/`), written `$ORACLE`.
- `test/session_check.py` reads the canonical campaign scripts from `$ORACLE` (default `oracle/` in this folder, as
  inside op2-rs).
- The Makefile reads TethysAPI from `vendor/include` in this folder first; `run.py` compares the installed DLLs with this
  folder's `build/`.
- The Windows scripts write their text files (`scenario.json`, `scenario_script.txt`, summaries, reports) with LF, as
  `run.py` does on Linux, so they hash the same as op2-rs's recordings.

**Verified** on Windows 10:
- **The original game.** All 456 of op2-rs's scenarios (its `harness/oracle/scenarios`, at ab5f74dd) run to their tick
  limit with no timeout, crash or dialog. `run_win.py selftest` passes (the self-test mission ends MissionAccomplished,
  alone and with `sample_bot.dll`).
- **Both toolchains.** The MinGW DLLs (CI) and the MSVC DLLs give byte-identical `trace.jsonl`, `telemetry.jsonl` and
  `gamedata.json` on line_fast, cmb_duel_laser and cmb_duel_rail_gun, and so does op2-rs's own harness source at
  ab5f74dd built with MSVC. Each toolchain's build is reproducible (CI checks this on every push).
- **op2-rs.** op2-sim matches line_fast, cmb_duel_laser and cmb_duel_rail_gun on every trace field of every tick.
  Against the hashes of op2-rs's recorded runs (`accuracy/manifest.json`, hashed with its `accuracy/runs.py`), over the
  456 scenarios: `gamedata.json` and `scenario_script.txt` match on every run, `scenario.json` on 452 (the other 4
  scenario files were edited after their runs were recorded), `audio.jsonl` on all 8 that have one, and 30 runs match
  in every file. The other `trace.jsonl` and `telemetry.jsonl` files differ from recordings made by earlier harness
  versions, which wrote fewer fields: no scenario added before 2026-10-31 matches and most added since do, and the
  differing telemetry is the economy runs' newer fields (hives, beacons). op2-rs's own `runs.py check --fresh` accepts
  such runs as `fresh_newer_fields`.
- **outpost2-port.** Compared with `windows/compare_port.py`: 8 of 9 scenarios match the original (outpost2-port
  958323a). Its upstream, marcelomgoncalves/outpost2 (1ac3673), matches cmb_duel_laser and cmb_duel_rail_gun on every
  compared field, and line_fast on every tick but its arrival (tick 731, x 16/65536 of a pixel short); op2-rs matches
  all three.

Not verified here: the Linux harness under Wine (`run.sh`, `make check`) since the move (CI builds it but can't run the
game), and op2-rs's `runs.py check --fresh` / `make accuracy` against this version's DLLs, which needs op2-rs's stored
recordings.
