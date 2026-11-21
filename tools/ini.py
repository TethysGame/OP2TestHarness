#!/usr/bin/env python3
"""Register/unregister the Harness module in OPU/outpost2.ini (OPU 1.4.1), or in the game folder's outpost2.ini's
LoadAddons (OPU 1.3.x, the `*_addons` functions), preserving everything else.

Backs the ini up once (outpost2.ini.pre-harness) before the first change. The module itself is inert unless the
OP2H_MISSION environment variable is set, so leaving it registered does not affect normal play.
"""
import re
import shutil
import sys
from pathlib import Path

ENTRY = "Harness=yes"
SECTION = "[Harness]\nDll=Harness\\harness.dll\n"


def install(text: str) -> str:
    if not re.search(r"(?mi)^Harness\s*=", text):
        if not re.search(r"(?mi)^\[ExternalModules\]", text):
            text = text.rstrip("\n") + "\n[ExternalModules]\n"
        text = re.sub(r"(?mi)^(\[ExternalModules\][^\n]*\n(?:(?!\[)[^\n]*\n)*?)(?=\[|\Z)",
                      lambda m: m.group(1).rstrip("\n") + "\n" + ENTRY + "\n", text, count=1)
    if not re.search(r"(?mi)^\[Harness\]", text):
        text = text.rstrip("\n") + "\n" + SECTION
    return text


def hp_bars(text: str, value: str = "0") -> str:
    """ShowUnitHPBars=<value> in [Game]."""
    line = f"ShowUnitHPBars={value}"
    if re.search(r"(?mi)^ShowUnitHPBars\s*=", text):
        return re.sub(r"(?mi)^ShowUnitHPBars\s*=[^\n]*", line, text)
    if not re.search(r"(?mi)^\[Game\]", text):
        text = "[Game]\n" + text
    return re.sub(r"(?mi)^\[Game\][^\n]*\n", lambda g: g.group(0) + line + "\n", text, count=1)


def set_hp_bars(ini_path: Path, env: dict) -> None:
    """Before a launch on OPU 1.4.1: ShowUnitHPBars in the game's own OPU/outpost2.ini, 0 (1.2's health bars: the
    selected unit and the one under the mouse) unless OP2H_INI_ShowUnitHPBars says otherwise. OPU reads it at startup,
    before the harness points the game at its per-run copy, so only this file decides what frames show."""
    if not ini_path.exists():
        return
    raw = ini_path.read_bytes().decode("latin-1")
    eol = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")
    # Any case: Windows' os.environ upper-cases names (the game's own lookup ignores case too).
    value = next((v for k, v in env.items() if k.upper() == "OP2H_INI_SHOWUNITHPBARS" and v), "0")
    new = hp_bars(text, value)
    if new != text:
        ini_path.write_bytes(new.replace("\n", eol).encode("latin-1"))


def uninstall(text: str) -> str:
    text = re.sub(r"(?mi)^Harness\s*=[^\n]*\n?", "", text)
    return re.sub(r"(?mis)^\[Harness\]\n(?:(?!\[)[^\n]*\n?)*", "", text)


# OPU 1.3.x (Outpost2.exe 1.3.0.x): op2ext reads the game folder's outpost2.ini, `LoadAddons = "A, B"` in [Game],
# each name a section whose Dll is loaded and its InitMod called.
ADDON_SECTION = '[Harness]\nDll = "Harness\\harness.dll"\n'
LOAD_ADDONS = re.compile(r'(?mi)^(LoadAddons\s*=\s*)"?([^"\n]*?)"?[ \t]*$')


def install_addons(text: str) -> str:
    m = LOAD_ADDONS.search(text)
    if not m:
        if not re.search(r"(?mi)^\[Game\]", text):
            text = "[Game]\n" + text
        text = re.sub(r"(?mi)^\[Game\][^\n]*\n", lambda g: g.group(0) + 'LoadAddons = "Harness"\n', text, count=1)
    else:
        names = [n.strip() for n in m.group(2).split(",") if n.strip()]
        if not any(n.lower() == "harness" for n in names):
            text = text[:m.start()] + m.group(1) + '"' + ", ".join(names + ["Harness"]) + '"' + text[m.end():]
    if not re.search(r"(?mi)^\[Harness\]", text):
        text = text.rstrip("\n") + "\n" + ADDON_SECTION
    return text


def uninstall_addons(text: str) -> str:
    m = LOAD_ADDONS.search(text)
    if m:
        names = [n.strip() for n in m.group(2).split(",") if n.strip() and n.strip().lower() != "harness"]
        text = text[:m.start()] + m.group(1) + '"' + ", ".join(names) + '"' + text[m.end():]
    return re.sub(r"(?mis)^\[Harness\]\n(?:(?!\[)[^\n]*\n?)*", "", text)


def main() -> None:
    action, path = sys.argv[1], Path(sys.argv[2])
    raw = path.read_bytes().decode("latin-1")
    eol = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")
    new = install(text) if action == "install" else uninstall(text)
    if new == text:
        print(f"{path.name}: already {action}ed")
        return
    backup = path.with_name(path.name + ".pre-harness")
    if not backup.exists():
        shutil.copy2(path, backup)
        print(f"backed up to {backup}")
    path.write_bytes(new.replace("\n", eol).encode("latin-1"))
    print(f"{path.name}: {action}ed")


if __name__ == "__main__":
    main()
