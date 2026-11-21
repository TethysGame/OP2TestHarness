"""Compares two harness telemetry files (telemetry.jsonl) field by field, tick by tick: which fields agree, and where each
first differs.

  python -I windows/telemetry_diff.py A/telemetry.jsonl B/telemetry.jsonl [--labels original,port] [--json report.json]
                                      [--ignore FIELDS]

Players are matched by id, units by id (the game's object index), beacons by position. For each player field (`food`,
`techs`, `eco.powerAvail`...), unit field and the top-level `end` (and, in input runs, `selected` and `view`), the report gives the first tick the two disagree and
both values there; a unit present in one file and not the other counts as its field `present`. Only ticks both files
have are compared, and only fields both files write somewhere: the port leaves out what it doesn't model (some `eco`
fields, `pi`, the units' `raw` and `hive`), and those aren't counted. --ignore takes field names (`cmd`, `eco.recalc`).
"""
import argparse
import json
import sys
from pathlib import Path


def load(path: Path) -> dict:
    ticks = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:  # A crashed run's last line can be cut off.
                continue
            ticks[rec["tick"]] = rec
    return ticks


def player_fields(p: dict) -> dict:
    """A player's fields, the `eco` object's as `eco.<name>`."""
    out = {k: v for k, v in p.items() if k not in ("id", "eco")}
    out.update({f"eco.{k}": v for k, v in p.get("eco", {}).items()})
    return out


def written(tel: dict) -> tuple[set, set]:
    players, units = set(), set()
    for rec in tel.values():
        for p in rec.get("players", []):
            players |= set(player_fields(p))
        for u in rec.get("units", []):
            units |= set(u)
    return players, units - {"id"}


def compare(a_path: Path, b_path: Path, ignore: tuple = ()) -> dict:
    a, b = load(a_path), load(b_path)
    common = sorted(set(a) & set(b))
    (pa, ua), (pb, ub) = written(a), written(b)
    pfields = sorted((pa & pb) - set(ignore))
    ufields = sorted((ua & ub) - set(ignore))
    beacons = "beacons" not in ignore and any("beacons" in r for r in a.values()) and any("beacons" in r for r in b.values())
    first: dict[str, dict] = {}
    unit_ticks = equal_unit_ticks = 0

    def note(key: str, tick: int, va, vb):
        if key not in first:
            first[key] = {"tick": tick, "a": va, "b": vb}

    for t in common:
        ra, rb = a[t], b[t]
        if "end" not in ignore and ra.get("end") != rb.get("end"):
            note("end", t, ra.get("end"), rb.get("end"))
        for key in ("selected", "view"):  # input runs: the selection and the view's top-left corner
            if key not in ignore and key in ra and key in rb and ra[key] != rb[key]:
                note(key, t, ra[key], rb[key])
        pla = {p["id"]: player_fields(p) for p in ra.get("players", [])}
        plb = {p["id"]: player_fields(p) for p in rb.get("players", [])}
        for i in sorted(set(pla) | set(plb)):
            if i not in pla or i not in plb:
                note(f"player {i} present", t, i in pla, i in plb)
                continue
            for f in pfields:
                if pla[i].get(f) != plb[i].get(f):
                    note(f"player {i} {f}", t, pla[i].get(f), plb[i].get(f))
        una = {u["id"]: u for u in ra.get("units", [])}
        unb = {u["id"]: u for u in rb.get("units", [])}
        for i in sorted(set(una) | set(unb)):
            if i not in una or i not in unb:
                side = una.get(i) or unb.get(i)
                note(f"unit {i} present", t, f"{side['type']}" if i in una else None, f"{side['type']}" if i in unb else None)
                continue
            unit_ticks += 1
            same = True
            for f in ufields:  # A field a unit doesn't write (a vehicle's cargo when it has none) counts as null.
                if una[i].get(f) != unb[i].get(f):
                    same = False
                    note(f"unit {i} {f}", t, una[i].get(f), unb[i].get(f))
            equal_unit_ticks += same
        if beacons:
            ba = sorted(json.dumps(x, sort_keys=True) for x in ra.get("beacons", []))
            bb = sorted(json.dumps(x, sort_keys=True) for x in rb.get("beacons", []))
            if ba != bb:
                note("beacons", t, [json.loads(x) for x in ba], [json.loads(x) for x in bb])
    return {
        "a": str(a_path), "b": str(b_path), "ticks_a": len(a), "ticks_b": len(b), "ticks_compared": len(common),
        "unit_ticks": unit_ticks, "unit_ticks_equal": equal_unit_ticks, "player_fields": pfields, "unit_fields": ufields,
        "ignored": sorted(ignore),
        "match": not first and len(common) > 0,
        "first_differences": dict(sorted(first.items(), key=lambda kv: (kv[1]["tick"], kv[0]))),
    }


def summary_line(r: dict) -> str:
    ignored = f" (ignoring {','.join(r['ignored'])})" if r.get("ignored") else ""
    if r["match"]:
        return (f"MATCH: {r['ticks_compared']} ticks, {r['unit_ticks']} unit-ticks, every compared field equal{ignored}")
    if not r["ticks_compared"]:
        return f"DIFF: no tick in common ({r['ticks_a']} / {r['ticks_b']} ticks){ignored}"
    d = r["first_differences"]
    t0 = min(v["tick"] for v in d.values())
    return (f"DIFF: first at tick {t0} ({len(d)} field(s) differ); {r['unit_ticks_equal']} of {r['unit_ticks']} "
            f"unit-ticks fully equal over {r['ticks_compared']} ticks{ignored}")


def print_report(r: dict, labels=("A", "B"), limit: int = 0) -> None:
    print(summary_line(r))
    items = list(r["first_differences"].items())
    for key, v in items[:limit or None]:
        print(f"  {key}: tick {v['tick']}: {labels[0]} {json.dumps(v['a'])} / {labels[1]} {json.dumps(v['b'])}")
    if limit and len(items) > limit:
        print(f"  ... and {len(items) - limit} more")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a", type=Path)
    ap.add_argument("b", type=Path)
    ap.add_argument("--labels", default="A,B", help="names for the two sides in the output")
    ap.add_argument("--json", type=Path, help="also write the report as JSON")
    ap.add_argument("--ignore", default="", metavar="FIELDS", help="fields left out, comma separated (e.g. cmd,eco.recalc)")
    ap.add_argument("--limit", type=int, default=0, help="print at most this many differences (0 = all)")
    args = ap.parse_args()
    r = compare(args.a, args.b, tuple(f for f in args.ignore.split(",") if f))
    print_report(r, tuple(args.labels.split(",", 1)), args.limit)
    if args.json:
        args.json.write_text(json.dumps(r, indent=1) + "\n")
    return 0 if r["match"] else 1


if __name__ == "__main__":
    sys.exit(main())
