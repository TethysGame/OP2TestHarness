"""Compares two gamedata.json files (the game's data as loaded, written at the first cycle) field by field.

  python -I windows/gamedata_diff.py A/gamedata.json B/gamedata.json [--labels original,port] [--json report.json]

Compared: the map's geometry (`map.*`), each cell type by id (`cell N field`), each unit type by map id
(`type CODE field`; its `stats` word by word, `type CODE stats[K]`), with `--eco` runs the morale levels and
modifiers by name, the mine rows, the tech tree in order and each type's `typeExtra`, and the cell type of every tile
(`cells`: how many tiles differ, and the first). A `typeExtra` entry's resource priority is compared only on
buildings and walls, the types the byte belongs to. Only fields both files write are compared: each side may leave some
out (outpost2-port's has no cell type names, `vehicleFlags` only for buildings, walls and weapons, no morale `maxima`).
"""
import argparse
import json
import sys
from pathlib import Path


def by(items, key):
    return {item[key]: item for item in items or []}


def compare(a_path: Path, b_path: Path, ignore: tuple = ()) -> dict:
    a = json.loads(Path(a_path).read_text(encoding="utf-8"))
    b = json.loads(Path(b_path).read_text(encoding="utf-8"))
    diffs: dict[str, dict] = {}
    compared = 0

    def note(key, va, vb):
        nonlocal compared
        compared += 1
        if va != vb and not any(key == i or key.startswith(i + " ") or key.startswith(i + ".") for i in ignore):
            diffs[key] = {"a": va, "b": vb}

    def fields(prefix, da, db, skip=()):
        for k in sorted(set(da) & set(db)):
            if k in skip:
                continue
            if k == "stats" and isinstance(da[k], list) and isinstance(db[k], list):
                for i in range(max(len(da[k]), len(db[k]))):
                    note(f"{prefix} stats[{i}]", da[k][i] if i < len(da[k]) else None, db[k][i] if i < len(db[k]) else None)
            else:
                note(f"{prefix} {k}", da[k], db[k])

    fields("map", a.get("map", {}), b.get("map", {}))
    ca, cb = by(a.get("cellTypes"), "id"), by(b.get("cellTypes"), "id")
    for i in sorted(set(ca) | set(cb)):
        if i not in ca or i not in cb:
            note(f"cell {i} present", i in ca, i in cb)
        else:
            fields(f"cell {i}", ca[i], cb[i], skip=("id",))
    ua, ub = by(a.get("unitTypes"), "mapId"), by(b.get("unitTypes"), "mapId")
    for i in sorted(set(ua) | set(ub)):
        code = (ua.get(i) or ub.get(i)).get("code", i)
        if i not in ua or i not in ub:
            note(f"type {code} present", i in ua, i in ub)
        else:
            fields(f"type {code}", ua[i], ub[i], skip=("mapId",))
    if "morale" in a and "morale" in b:
        la, lb = by(a["morale"].get("levels"), "name"), by(b["morale"].get("levels"), "name")
        for n in sorted(set(la) | set(lb)):
            note(f"morale level {n}", la.get(n, {}).get("v"), lb.get(n, {}).get("v"))
        if "maxima" in a["morale"] and "maxima" in b["morale"]:
            note("morale maxima", a["morale"]["maxima"], b["morale"]["maxima"])
        ma = {m[0]: m[1:] for m in a["morale"].get("modifiers", [])}
        mb = {m[0]: m[1:] for m in b["morale"].get("modifiers", [])}
        for n in sorted(set(ma) | set(mb)):
            note(f"morale modifier {n}", ma.get(n), mb.get(n))
    if "mines" in a and "mines" in b:
        for ra, rb in zip(a["mines"], b["mines"]):
            fields(f"mine {ra['variant']}/{ra['bar']}", ra, rb, skip=("variant", "bar"))
        if len(a["mines"]) != len(b["mines"]):
            note("mines count", len(a["mines"]), len(b["mines"]))
    if "techTree" in a and "techTree" in b:
        ta, tb = a["techTree"], b["techTree"]
        if len(ta) != len(tb):
            note("techTree count", len(ta), len(tb))
        for k, (x, y) in enumerate(zip(ta, tb)):
            note(f"tech {x[0]}" if x[0] == y[0] else f"tech #{k}", x, y)
    if "typeExtra" in a and "typeExtra" in b:
        xa, xb = {t[0]: t[1:] for t in a["typeExtra"]}, {t[0]: t[1:] for t in b["typeExtra"]}
        for i in sorted(set(xa) | set(xb)):
            code = (ua.get(i) or ub.get(i) or {}).get("code", i)
            # +0x2A0 is the resource priority only on buildings and walls (0x11..0x3A); elsewhere the original reads
            # whatever byte the type keeps there, so only the research topic is compared.
            va, vb = xa.get(i), xb.get(i)
            if va and vb and not 0x11 <= i <= 0x3A:
                va, vb = va[1:], vb[1:]
            note(f"typeExtra {code}", va, vb)
    if "cells" in a and "cells" in b and "cells" not in ignore:
        sa, sb = a["cells"], b["cells"]
        w = a.get("map", {}).get("width", 1) or 1
        bad = [k for k in range(min(len(sa), len(sb))) if sa[k] != sb[k]]
        compared += 1
        if bad or len(sa) != len(sb):
            k = bad[0] if bad else min(len(sa), len(sb))
            diffs["cells"] = {"a": sa[k] if k < len(sa) else None, "b": sb[k] if k < len(sb) else None,
                              "first": [k % w, k // w], "tiles": len(bad), "of": max(len(sa), len(sb))}
    return {"a": str(a_path), "b": str(b_path), "compared": compared, "ignored": sorted(ignore), "match": not diffs,
            "first_differences": diffs}


def summary_line(r: dict) -> str:
    ignored = f" (ignoring {','.join(r['ignored'])})" if r.get("ignored") else ""
    if r["match"]:
        return f"MATCH: {r['compared']} fields equal{ignored}"
    return f"DIFF: {len(r['first_differences'])} of {r['compared']} fields differ{ignored}"


def detail(key: str, v: dict, labels=("original", "port")) -> str:
    extra = f" (first at {v['first']}, {v['tiles']} of {v['of']} tiles)" if key == "cells" else ""
    return f"  {key}: {labels[0]} {json.dumps(v['a'])} / {labels[1]} {json.dumps(v['b'])}{extra}"


def print_report(r: dict, labels=("A", "B"), limit: int = 0) -> None:
    print(summary_line(r))
    items = list(r["first_differences"].items())
    for key, v in items[:limit or len(items)]:
        print(detail(key, v, labels))
    if limit and len(items) > limit:
        print(f"  ... and {len(items) - limit} more")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a", type=Path)
    ap.add_argument("b", type=Path)
    ap.add_argument("--labels", default="A,B", help="names for the two sides in the output")
    ap.add_argument("--json", type=Path, help="also write the report as JSON")
    ap.add_argument("--ignore", default="", metavar="FIELDS",
                    help="keys or key prefixes left out, comma separated (e.g. cells,type BFG)")
    ap.add_argument("--limit", type=int, default=0, help="print at most this many differences")
    args = ap.parse_args()
    r = compare(args.a, args.b, tuple(f for f in args.ignore.split(",") if f))
    print_report(r, tuple(args.labels.split(",", 1)), args.limit)
    if args.json:
        args.json.write_text(json.dumps(r, indent=1) + "\n")
    return 0 if r["match"] else 1


if __name__ == "__main__":
    sys.exit(main())
