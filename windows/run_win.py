"""Runs a scenario in the original Outpost 2 natively on Windows (no Wine, no Xvfb) through harness.dll.

  python -I windows/run_win.py setup [--from "C:\\...\\Outpost 2"] [--game DIR]
      Copies the game (without movies and OPU backups) to a private folder, installs build\\win\\harness.dll and
      zScenario.dll into its OPU\\Harness and registers the module in its OPU\\outpost2.ini. Run again after a rebuild.
  python -I windows/run_win.py run SCENARIO.json OUT_DIR [--game DIR] [--shot-every N] [--map-every N] [--no-turbo] [--timeout S]
                                [--bot DLL] [--show]
      Writes the harness's outputs (trace.jsonl, telemetry.jsonl, gamedata.json, harness.log, shot_*.png,
      summary.json) to OUT_DIR. Compare with op2-rs: op2-inspect compare --scenario SCENARIO.json --oracle OUT_DIR
      --bot runs a bot DLL (HarnessBotTick, e.g. build\\win\\sample_bot.dll) every tick.
  python -I windows/run_win.py mission DLL OUT_DIR [--game DIR] [--ticks N] [--players N] [--telemetry-every N]
                                [--shot-every N] [--no-turbo] [--timeout S]
      Plays a mission DLL (found as the game finds it: OPU\\maps first, then the game folder) unattended, e.g.
      cde1.dll, with telemetry.jsonl, harness.log, screenshots and summary.json in OUT_DIR. --players N (2-6) starts a
      multiplayer DLL as the original's offline multiplayer start.
  python -I windows/run_win.py selftest [--game DIR]
      The Makefile's `make check` on Windows: plays the self-test mission (build\\win\\zHarnessEnd.dll, won at tick
      800) and requires MissionAccomplished with 4 screenshots, then plays it again with build\\win\\sample_bot.dll and
      requires the bot to load. The mission is in OPU\\maps\\HarnessTest only while the test runs.

An OPU 1.3.x install (no OPU folder) works too: the harness goes in its Harness\\ and its own outpost2.ini's LoadAddons,
and missions in its game folder (windows/README.md "OPU 1.3.6").

The private copy (default: game\\ next to this folder's parent) keeps harness runs from touching the player's install
and settings. The scenario translation is run.py's, imported unchanged.

The game runs on the person's own desktop, so it is left alone: a run that draws nothing (no screenshots, no bot) starts
the game hidden, one that does shows it at 0,0 without taking focus (--show forces that), and OP2H_DESKTOP keeps the
harness from moving the real pointer or taking focus. A hidden window still plays the same game; a minimised one loses
its screenshots and an off-screen one draws nothing, so those aren't used.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = Path(r"C:\Users\Desktop\Outpost 2")
DEFAULT_GAME = ROOT / "game"
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4  # STARTUPINFO.wShowWindow

sys.modules.setdefault("fcntl", types.ModuleType("fcntl"))  # run.py imports it for --record's lock only.
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import run  # noqa: E402
import ini  # noqa: E402


MISSION_EVERY = 100  # a mission's trace and telemetry interval: every tick would be gigabytes over a long game


def load_recipe(path: Path) -> tuple[dict, str]:
    """A scenario JSON, or a mission script (op2-rs's oracle/missions/*.txt), as (settings, script text).
    A mission script's header gives the DLL (`run.sh --mission NAME`), the seed and difficulty ("difficulty D, seed
    S") and the length: `--ticks N`, or with `--ticks 0` the tick its session ended at ("at tick N"). Without a
    header the DLL is the file name up to its first `_` and the run goes 100 ticks past the last line. Missions get a
    trace and telemetry every 100 ticks, the economy (`--eco`) and the audio log."""
    import re
    if path.suffix.lower() == ".json":
        scn = json.loads(path.read_text())
        return scn, run.scenario_script(scn)
    text = path.read_text(errors="replace")
    head = "\n".join(l for l in text.splitlines() if l.startswith("#"))
    m = re.search(r"--mission (\S+)", head)
    mission = m.group(1) if m else path.stem.split("_")[0] + ".dll"
    m = re.search(r"--ticks (\d+)", head)
    ticks = int(m.group(1)) if m else 0
    if not ticks:
        m = re.search(r"at tick (\d+)", head)
        ticks = int(m.group(1)) if m else 0
    if not ticks:
        last = [int(l.split()[0]) for l in text.splitlines() if l.strip() and l.split()[0].isdigit()]
        ticks = (max(last) if last else 0) + 100
    m = re.search(r"difficulty (\d)", head)
    difficulty = int(m.group(1)) if m else 1
    m = re.search(r"seed (\d+)", head)
    seed = int(m.group(1)) if m else 1
    return ({"mission": mission, "ticks": ticks, "seed": seed, "difficulty": difficulty, "traceEvery": MISSION_EVERY,
             "telemetryEvery": MISSION_EVERY, "eco": True, "audio": True}, text)


def is_opu13(game: Path) -> bool:
    """OPU 1.3.x (OPU's patched Outpost2.exe 1.3.0.x): no OPU folder; op2ext loads modules from the game folder's
    outpost2.ini (LoadAddons) and missions from the game folder. Otherwise OPU 1.4.1 on GOG 1.2.0.7."""
    return not (game / "OPU").is_dir()


def use_game(game: Path) -> None:
    run.GAME_DIR = game
    # On 1.3.x the harness, its ini and the scenario missions sit in the game folder itself (Harness\, outpost2.ini).
    run.OPU_DIR = game if is_opu13(game) else game / "OPU"


def setup(source: Path, game: Path) -> None:
    if not (source / "Outpost2.exe").exists():
        sys.exit(f"setup: no Outpost2.exe in {source}")
    if game.resolve() == source.resolve():
        sys.exit("setup: the private copy must not be the game install itself")
    opu13 = is_opu13(source)
    if opu13 and b"LoadAddons" not in (source / "op2ext.dll").read_bytes():
        sys.exit(f"setup: {source / 'op2ext.dll'} can't load modules (no LoadAddons): an older op2ext, e.g. one a mod's "
                 "installer put there; the harness needs OPU 1.3.5's or later")
    print(f"setup: copying {source} -> {game}")
    subprocess.run(["robocopy", str(source), str(game), "/E", "/XF", "*.avi",
                    "/XD", str(source / "OPU" / "backups"), str(source / "OPU" / "logs"),
                    "/NFL", "/NDL", "/NJH", "/NJS", "/NP"], check=False)  # robocopy exits 1 on success.
    use_game(game)
    harness_dir = run.OPU_DIR / "Harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    for dll in ("harness.dll", "zScenario.dll"):
        built = ROOT / "build" / "win" / dll
        if not built.exists():
            sys.exit(f"setup: {built} missing: run windows\\build.bat first")
        shutil.copy2(built, harness_dir / dll)
    ini_path = run.OPU_DIR / "outpost2.ini"
    text = ini_path.read_bytes().decode("latin-1").replace("\r\n", "\n")
    new = ini.install_addons(text) if opu13 else ini.install(text)
    if new != text:
        ini_path.write_bytes(new.replace("\n", "\r\n").encode("latin-1"))
    print(f"setup: harness installed in {harness_dir}")


def to_png(out: Path) -> int:
    """BMP -> PNG through System.Drawing (no PIL needed): the screenshots (the DLL writes whole-map images as PNGs
    itself). Returns the number of screenshots."""
    shots = len(list(out.glob("shot_*.bmp")))
    if shots:
        # One loop over the folder, not a command per file: a long run's list overflows the command line.
        ps = ("Add-Type -AssemblyName System.Drawing; "
              rf"Get-ChildItem -LiteralPath '{out}' -File | Where-Object {{ $_.Name -match '^shot_.*\.bmp$' }} | "
              "ForEach-Object { $i=[System.Drawing.Image]::FromFile($_.FullName); "
              "$i.Save([IO.Path]::ChangeExtension($_.FullName, '.png'), [System.Drawing.Imaging.ImageFormat]::Png); "
              "$i.Dispose(); Remove-Item -LiteralPath $_.FullName }")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False)
    return shots


def run_scenario(a) -> int:
    if not (run.OPU_DIR / "Harness" / "harness.dll").exists():
        sys.exit(f"run: no harness in {run.GAME_DIR}: run `run_win.py setup` first")
    scn, script_text = load_recipe(a.scenario)
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    for old in [*out.glob("shot_*"), *(out / n for n in ("trace.jsonl", "telemetry.jsonl", "harness.log",
                                                        "gamedata.json", "audio.jsonl", "summary.json"))]:
        old.unlink(missing_ok=True)
    ticks, seed = scn.get("ticks", 3000), scn.get("seed", 1)
    if "mission" in scn:  # a mission DLL, found where the game finds it
        mission = scn["mission"]
    else:
        mission = run.scenario_mission(scn.get("map", "cm01.map"), scn.get("techtree", "multitek.txt"))
        if is_opu13(run.GAME_DIR):
            mission = mission.removeprefix("OPU\\")  # Harness\zs_*.dll, relative to the game folder.
    script = out / "scenario_script.txt"
    script.write_text(newline="\n", data=script_text)
    (out / "scenario.json").write_text(newline="\n",
                                       data=json.dumps(dict(scn, seed=seed, ticks=ticks), indent=1) + "\n")
    env = dict(OP2H_MISSION=mission, OP2H_OUT=str(out), OP2H_SCRIPT=str(script),
               OP2H_TICKS=str(ticks), OP2H_SEED=str(seed), OP2H_DIFFICULTY=str(scn.get("difficulty", 1)),
               OP2H_TRACE_EVERY=str(scn.get("traceEvery", 1)), OP2H_TELEM_EVERY=str(scn.get("telemetryEvery", 100)),
               OP2H_TRACE_MAP="1" if scn.get("traceMap") else "0", OP2H_ECO="1" if scn.get("eco") else "0",
               OP2H_AUDIO="1" if scn.get("audio") else "0", OP2H_SHOT_EVERY=str(a.shot_every),
               OP2H_MAP_EVERY=str(getattr(a, "map_every", 0)), OP2H_MAP_PX=str(getattr(a, "map_px", 8)),
               OP2H_MAP_DAYLIGHT="0" if getattr(a, "map_night", False) else "1",
               OP2H_TURBO="0" if a.no_turbo else "1", OP2H_SPEED="10", OP2H_WIDTH="1024", OP2H_HEIGHT="768")
    if getattr(a, "bot", None):
        env["OP2H_BOT"] = str(a.bot.resolve())
    summary = launch(env, out, a.timeout, shown=a.show or a.shot_every > 0 or bool(a.bot))
    summary = {"scenario": str(a.scenario), "mission": mission, **summary}
    (out / "summary.json").write_text(newline="\n", data=json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))
    return 0 if summary["ok"] else 1


def run_mission(a) -> int:
    if not (run.OPU_DIR / "Harness" / "harness.dll").exists():
        sys.exit(f"mission: no harness in {run.GAME_DIR}: run `run_win.py setup` first")
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    for old in [*out.glob("shot_*"), *(out / n for n in ("telemetry.jsonl", "harness.log", "summary.json"))]:
        old.unlink(missing_ok=True)
    env = dict(OP2H_MISSION=a.dll, OP2H_OUT=str(out), OP2H_TICKS=str(a.ticks), OP2H_SEED="1", OP2H_DIFFICULTY="1",
               OP2H_TELEM_EVERY=str(a.telemetry_every), OP2H_SHOT_EVERY=str(a.shot_every),
               OP2H_TURBO="0" if a.no_turbo else "1", OP2H_SPEED="10", OP2H_WIDTH="1024", OP2H_HEIGHT="768")
    if a.players > 1:
        env["OP2H_PLAYERS"] = str(a.players)
    summary = {"mission": a.dll, **launch(env, out, a.timeout, shown=a.show or a.shot_every > 0)}
    (out / "summary.json").write_text(newline="\n", data=json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))
    return 0 if summary["ok"] else 1


def launch(harness_env: dict, out: Path, timeout: float, args: list[str] | None = None, shown: bool = True) -> dict:
    """Starts Outpost2.exe in the game copy (/OPU on OPU 1.4.1, then `args`, e.g. ["/loadmod", "NAME"]) with these
    OP2H_* settings and waits (killing it after `timeout` s). `shown`: the window is shown without taking focus (it
    must be, to draw), else hidden.
    Returns the run's summary: the platform, exit code, timeout, wall time, screenshots (converted to PNG), how the
    game ended (the last telemetry line's `end`), suppressed dialogs, the bot line, the quit line and `ok`."""
    start = time.monotonic()
    opu13 = is_opu13(run.GAME_DIR)
    env = dict(os.environ, OP2H_DESKTOP="1", **harness_env)
    if not opu13:
        ini.set_hp_bars(run.OPU_DIR / "outpost2.ini", env)
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = SW_SHOWNOACTIVATE if shown else SW_HIDE
    cmd = [str(run.GAME_DIR / "Outpost2.exe"), *([] if opu13 else ["/OPU"]), *(args or [])]
    game = subprocess.Popen(cmd, cwd=run.GAME_DIR, env=env, startupinfo=startup)
    try:
        code, timed_out = game.wait(timeout=timeout), False
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(game.pid)], capture_output=True)
        code, timed_out = game.wait(), True
    hlog = (out / "harness.log").read_text(errors="replace") if (out / "harness.log").exists() else ""
    quit_line = next((l for l in hlog.splitlines() if l.startswith("quit at tick")), None)
    end = None
    telem = out / "telemetry.jsonl"
    for line in reversed(telem.read_text(errors="replace").splitlines() if telem.exists() else []):
        try:
            end = json.loads(line)["end"]
            break
        except (json.JSONDecodeError, KeyError):
            continue
    return {"platform": "windows", "exit_code": code, "timed_out": timed_out, "wall_seconds": round(time.monotonic() - start, 1),
            "screenshots": to_png(out), "game_term_reason": run.END_REASONS.get(end, end),
            "dialogs": [l[len("dialog: "):] for l in hlog.splitlines() if l.startswith("dialog: ")],
            "bot": next((l for l in hlog.splitlines() if l.startswith("bot: ")), None),
            "quit": quit_line, "ok": bool(quit_line) and not timed_out and code == 0}


def selftest() -> int:
    """`make check` on Windows: the self-test mission ends MissionAccomplished at tick 800, with and without a bot."""
    for f in ("harness.dll", "zScenario.dll"):
        if not (run.OPU_DIR / "Harness" / f).exists():
            sys.exit(f"selftest: no {f} in {run.GAME_DIR}: run `run_win.py setup` first")
    built = ROOT / "build" / "win"
    mission, bot = built / "zHarnessEnd.dll", built / "sample_bot.dll"
    for f in (mission, bot):
        if not f.exists():
            sys.exit(f"selftest: {f} missing: run windows\\build.bat first")
    opu13 = is_opu13(run.GAME_DIR)  # OPU 1.3.x loads missions from the game folder only.
    maps = run.GAME_DIR if opu13 else run.OPU_DIR / "maps" / "HarnessTest"
    maps.mkdir(parents=True, exist_ok=True)
    shutil.copy2(mission, maps / mission.name)
    failures = []
    try:
        for name, extra in (("plain", {}), ("bot", {"OP2H_BOT": str(bot)})):
            out = ROOT / "build" / "selftest" / name
            out.mkdir(parents=True, exist_ok=True)
            for old in [*out.glob("shot_*"), *(out / n for n in ("telemetry.jsonl", "harness.log", "summary.json"))]:
                old.unlink(missing_ok=True)
            env = dict(OP2H_MISSION="zHarnessEnd.dll", OP2H_OUT=str(out), OP2H_TICKS="3000", OP2H_SHOT_EVERY="400",
                       OP2H_TELEM_EVERY="100", OP2H_TURBO="1", OP2H_WIDTH="1024", OP2H_HEIGHT="768", **extra)
            s = launch(env, out, 120)
            (out / "summary.json").write_text(newline="\n", data=json.dumps(s, indent=2) + "\n")
            problems = []
            if s["game_term_reason"] != "MissionAccomplished":
                problems.append(f"ended {s['game_term_reason']}")
            if s["screenshots"] != 4:
                problems.append(f"{s['screenshots']} screenshots, not 4")
            if not s["ok"]:
                problems.append(f"exit {s['exit_code']}, timed out {s['timed_out']}, quit line {s['quit']!r}")
            if extra and not (s["bot"] or "").endswith("-> ok"):
                problems.append(f"bot line {s['bot']!r}")
            print(f"selftest {name}: " + ("OK" if not problems else "FAILED: " + "; ".join(problems)) + f" ({out})")
            failures += [f"{name}: {p}" for p in problems]
    finally:
        if opu13:
            (maps / mission.name).unlink(missing_ok=True)
        else:
            shutil.rmtree(maps, ignore_errors=True)
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup", help="make the private game copy and install the harness into it")
    s.add_argument("--from", dest="source", type=Path, default=DEFAULT_SOURCE, help="the game install to copy")
    s.add_argument("--game", type=Path, default=DEFAULT_GAME, help="the private copy")
    r = sub.add_parser("run", help="run a scenario in the original game")
    r.add_argument("scenario", type=Path)
    r.add_argument("out", type=Path)
    r.add_argument("--game", type=Path, default=DEFAULT_GAME, help="the private copy")
    r.add_argument("--shot-every", type=int, default=0, metavar="N", help="screenshot every N ticks (0 = off)")
    r.add_argument("--map-every", type=int, default=0, metavar="N",
                    help="a whole-map image and its state_<tick>.json every N ticks (0 = off)")
    r.add_argument("--map-px", type=int, default=8, metavar="N", help="the whole-map images' pixels a tile: 1-32")
    r.add_argument("--map-night", action="store_true", help="draw the whole-map images lit as the game shows them")
    r.add_argument("--no-turbo", action="store_true", help="real time at full game speed, to watch it")
    r.add_argument("--timeout", type=float, default=600, help="wall-clock seconds before the game is killed")
    r.add_argument("--bot", type=Path, help="bot DLL exporting HarnessBotTick(int tick), called every tick")
    r.add_argument("--show", action="store_true", help="show the window (without taking focus) even when nothing draws")
    m = sub.add_parser("mission", help="play a mission DLL unattended")
    m.add_argument("dll", help="the mission DLL's name, e.g. cde1.dll")
    m.add_argument("out", type=Path)
    m.add_argument("--game", type=Path, default=DEFAULT_GAME, help="the private copy")
    m.add_argument("--ticks", type=int, default=3000, help="stop after this tick")
    m.add_argument("--players", type=int, default=1, help="human players in a multiplayer start (2-6)")
    m.add_argument("--telemetry-every", type=int, default=100, metavar="N", help="telemetry every N ticks")
    m.add_argument("--shot-every", type=int, default=0, metavar="N", help="screenshot every N ticks (0 = off)")
    m.add_argument("--no-turbo", action="store_true", help="real time at full game speed, to watch it")
    m.add_argument("--timeout", type=float, default=600, help="wall-clock seconds before the game is killed")
    m.add_argument("--show", action="store_true", help="show the window (without taking focus) even when nothing draws")
    c = sub.add_parser("selftest", help="make check on Windows: the self-test mission, with and without a bot")
    c.add_argument("--game", type=Path, default=DEFAULT_GAME, help="the private copy")
    a = ap.parse_args()
    use_game(a.game.resolve())
    if a.cmd == "setup":
        setup(a.source.resolve(), a.game.resolve())
        return 0
    if a.cmd == "selftest":
        return selftest()
    if a.cmd == "mission":
        return run_mission(a)
    return run_scenario(a)


if __name__ == "__main__":
    sys.exit(main())
