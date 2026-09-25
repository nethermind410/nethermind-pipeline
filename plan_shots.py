#!/usr/bin/env python3
"""
plan_shots.py — Shot Planner v0.2: narration script -> machine-readable shot plan.

    python3 plan_shots.py plan briefs/<id>.json --beats beats/<id>.beats.json   # from a written beat sheet
    python3 plan_shots.py plan briefs/<id>.json --llm gemini                   # an LLM writes the beats
    python3 plan_shots.py plan briefs/<id>.json --heuristic                    # offline draft, needs review
    python3 plan_shots.py validate plans/<id>.shotplan.json                    # re-check an edited plan
    python3 plan_shots.py show plans/<id>.shotplan.json [S04]                  # readable summary / one shot

Writes plans/<id>.shotplan.json (and, with --llm/--heuristic, the beat sheet
it used to beats/<id>.beats.json, so it can be edited and re-compiled).
Exit code 1 if the plan has errors. See docs/SHOT_PLANNER.md.
"""
import argparse
import json
import os
import sys

from shotplanner import beats as B
from shotplanner import llm
from shotplanner.compiler import PlanError, compile_plan
from shotplanner.validate import check_structure, load_schema, validate_plan

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(p):
    with open(p) as f:
        return json.load(f)


def _dump(obj, p):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with open(p, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def cmd_plan(a):
    brief = _load(a.brief)
    errs = check_structure(brief, load_schema("brief-0.2.schema.json"))
    if errs:
        print("brief errors:\n  " + "\n  ".join(errs))
        return 1
    pid = brief["project"]["id"]
    beats_out = os.path.join(HERE, "beats", f"{pid}.beats.json")
    try:
        if a.beats:
            beats, backend = B.load(a.beats), f"manual:{os.path.relpath(a.beats, HERE)}"
        elif a.llm:
            prov = llm.get(a.llm, a.model)
            print(f"[{pid}] planning beats with {prov.label} ...")
            beats, backend = B.from_llm(brief, prov), prov.label
        else:
            beats, backend = B.heuristic(brief), "heuristic"
        prev = a.out or os.path.join(HERE, "plans", f"{pid}.shotplan.json")
        version = _load(prev)["plan_version"] + 1 if os.path.exists(prev) else 1
        plan = compile_plan(brief, beats, backend=backend, plan_version=version)
    except PlanError as e:
        print(f"[{pid}] cannot build a plan:\n  " + "\n  ".join(e.errors))
        return 1
    if not a.beats:
        if os.path.exists(beats_out) and not a.force:
            beats_out = beats_out.replace(".beats.json", f".{backend.split(':')[0]}.beats.json")
        _dump(beats, beats_out)
        print(f"   beats -> {os.path.relpath(beats_out, HERE)}")
    out = a.out or os.path.join(HERE, "plans", f"{pid}.shotplan.json")
    _dump(plan, out)
    show(plan)
    print(f"   plan  -> {os.path.relpath(out, HERE)}  (v{version})")
    return 0


def show(plan, shot_id=None):
    if shot_id:
        s = next((s for s in plan["shots"] if s["id"] == shot_id), None)
        if not s:
            print(f"no shot {shot_id}")
            return
        print(json.dumps(s, indent=2, ensure_ascii=False))
        return
    t = plan["totals"]
    print(f"[{plan['project']['id']}] {t['shots']} shots, ~{t['estimated_duration_s']}s, modes {t['by_mode']}")
    for s in plan["shots"]:
        cam = s["visual"]["camera"]
        print(f"  {s['id']} {s['timing']['start_s']:5.1f}s +{s['timing']['estimated_duration_s']:<4} "
              f"{s['generation']['mode']:<19} {cam['framing']}/{cam['movement']:<13} {s['status']}")
        print(f"       \"{s['narration']['text']}\"")
        print(f"       -> {s['visual']['goal']}")
    for w in plan["warnings"]:
        print(f"  ! {w}")


def cmd_validate(a):
    plan = _load(a.plan)
    errs, warns = validate_plan(plan)
    for w in warns:
        print(f"  ! {w}")
    for e in errs:
        print(f"  x {e}")
    print(f"{a.plan}: {'INVALID' if errs else 'OK'} ({len(errs)} error(s), {len(warns)} warning(s))")
    return 1 if errs else 0


def cmd_show(a):
    show(_load(a.plan), a.shot)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="compile a brief into a shot plan")
    p.add_argument("brief")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--beats", help="hand-written/edited beat sheet")
    src.add_argument("--llm", choices=sorted(llm.PROVIDERS), help="let an LLM write the beat sheet")
    src.add_argument("--heuristic", action="store_true", help="offline draft (every shot NEEDS_REVIEW)")
    p.add_argument("--model", help="override the LLM model id")
    p.add_argument("--out", help="plan path (default plans/<id>.shotplan.json)")
    p.add_argument("--force", action="store_true", help="overwrite beats/<id>.beats.json")
    p.set_defaults(fn=cmd_plan)
    v = sub.add_parser("validate", help="check a plan file")
    v.add_argument("plan")
    v.set_defaults(fn=cmd_validate)
    s = sub.add_parser("show", help="print a plan summary, or one shot in full")
    s.add_argument("plan")
    s.add_argument("shot", nargs="?")
    s.set_defaults(fn=cmd_show)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
