"""Studio extension: the single "what's next" answer for the home brain.

GET /api/next_step  -> {"done": bool, "action": {"title","why","go"}, "more": n, "streak", "out"}

Derived from the exact same source as Today's run (studio_ext_day.day()): the first
open step in priority order — post today's Short, approve a waiting script, fix a
failing connection, reply to comments, make the next video... When every step is
done, "done" is true and the streak/out numbers carry the quiet "all caught up" state.
"""
import studio_ext_day as day_ext


def next_step():
    d = day_ext.day()
    open_steps = [s for s in d["steps"] if not s["done"]]
    if not open_steps:
        return {"done": True, "streak": d["streak"], "out": d["out"]}
    s = open_steps[0]
    return {"done": False, "action": {"title": s["title"], "why": s["why"], "go": s["go"]},
            "more": len(open_steps) - 1, "streak": d["streak"], "out": d["out"]}


GET = {"/api/next_step": next_step}
