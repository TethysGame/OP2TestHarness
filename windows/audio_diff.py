"""Compares two audio logs (audio.jsonl, `--audio`) event by event, tick by tick.

  python -I windows/audio_diff.py A/audio.jsonl B/audio.jsonl [--labels original,port] [--json report.json]

Each tick's sound events (`sfx`, `savant`, `play`, `msg`) are compared as a list of [ev, id, x, y, pass], in the order
the game asked for them; `at` (a return address in Outpost2.exe) and `name` (which follows from the id) are left out.
The music playlist is compared as `music` (songs, repeat, pos) and the sound lengths of the `tables` line as
`tables.ms`; the tables' Savant priorities only when both logs have them. The report gives the first tick each kind of
event differs, with both sides' events there, and how many ticks differ.
"""
import argparse
import json
import sys
from pathlib import Path

SOUND_EVENTS = ("sfx", "savant", "play", "msg")


def load(path: Path):
    events, music, tables = {}, {}, {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            ev, t = e.get("ev"), e.get("tick", 0)
            if ev in SOUND_EVENTS:
                events.setdefault(t, []).append([ev, e.get("id"), e.get("x"), e.get("y"), e.get("pass")])
            elif ev == "music":
                music[t] = [e.get("songs"), e.get("repeat"), e.get("pos")]
            elif ev == "tables" and not tables:
                tables = e
    return events, music, tables


def compare(a_path: Path, b_path: Path, ignore: tuple = ()) -> dict:
    ea, ma, ta = load(a_path)
    eb, mb, tb = load(b_path)
    first: dict[str, dict] = {}
    ticks_differ = 0

    def note(key, tick, va, vb):
        if key not in first:
            first[key] = {"tick": tick, "a": va, "b": vb}

    for t in sorted(set(ea) | set(eb)):
        la = [e for e in ea.get(t, []) if e[0] not in ignore]
        lb = [e for e in eb.get(t, []) if e[0] not in ignore]
        if la == lb:
            continue
        ticks_differ += 1
        kinds = False
        for ev in SOUND_EVENTS:
            xa, xb = [e for e in la if e[0] == ev], [e for e in lb if e[0] == ev]
            if xa != xb:
                kinds = True
                note(ev, t, xa, xb)
        if not kinds:  # each kind's events equal: only their interleaving differs
            note("order", t, la, lb)
    if "music" not in ignore:
        last_a = last_b = None
        for t in sorted(set(ma) | set(mb)):
            last_a, last_b = ma.get(t, last_a), mb.get(t, last_b)
            if last_a != last_b:
                note("music", t, last_a, last_b)
                break
    if "tables" not in ignore and ta and tb:
        for k in ("ms", "prio", "prio_ctor"):
            if k in ta and k in tb and ta[k] != tb[k]:
                bad = [i for i, (x, y) in enumerate(zip(ta[k], tb[k])) if x != y]
                note(f"tables.{k}", ta.get("tick", 0), {"ids": bad[:20], "count": len(bad)},
                     {"a": [ta[k][i] for i in bad[:20]], "b": [tb[k][i] for i in bad[:20]]})
    count = lambda ev: sum(len(v) for v in ev.values())
    return {"a": str(a_path), "b": str(b_path), "events_a": count(ea), "events_b": count(eb), "ticks_differ": ticks_differ,
            "ignored": sorted(ignore), "match": not first,
            "first_differences": dict(sorted(first.items(), key=lambda kv: (kv[1]["tick"], kv[0])))}


def summary_line(r: dict) -> str:
    ignored = f" (ignoring {','.join(r['ignored'])})" if r.get("ignored") else ""
    if r["match"]:
        return f"MATCH: {r['events_a']} sound events, the music and the tables equal{ignored}"
    t0 = min(v["tick"] for v in r["first_differences"].values())
    return (f"DIFF: first at tick {t0}; {r['ticks_differ']} ticks' events differ ({r['events_a']} vs {r['events_b']} "
            f"events){ignored}")


def print_report(r: dict, labels=("A", "B")) -> None:
    print(summary_line(r))
    for key, v in r["first_differences"].items():
        print(f"  {key}: tick {v['tick']}: {labels[0]} {json.dumps(v['a'])} / {labels[1]} {json.dumps(v['b'])}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a", type=Path)
    ap.add_argument("b", type=Path)
    ap.add_argument("--labels", default="A,B", help="names for the two sides in the output")
    ap.add_argument("--json", type=Path, help="also write the report as JSON")
    ap.add_argument("--ignore", default="", metavar="KINDS", help="event kinds left out, comma separated (e.g. play,music)")
    args = ap.parse_args()
    r = compare(args.a, args.b, tuple(f for f in args.ignore.split(",") if f))
    print_report(r, tuple(args.labels.split(",", 1)))
    if args.json:
        args.json.write_text(json.dumps(r, indent=1) + "\n")
    return 0 if r["match"] else 1


if __name__ == "__main__":
    sys.exit(main())
