"""
quality_loop.py — a draft doesn't reach Courtney until it clears the bar.

After the Script writer and Packaging agent finish, draft() calls improve(). Cheapest first:
  1. free fixes in code (no Claude): hook text = the spoken first line, a moving opening zoom,
     over-long beats split so the picture changes, and the best title picked from the options
     by the title checklist;
  2. if the Hook & retention check is still under BAR, up to MAX_REWRITES Claude rewrites, each
     told exactly which checks missed (the same redraft path as "Needs changes");
  3. still under the bar → held back: the draft is saved with "held" reasons so the app shows it
     as not ready, instead of handing her a 6/10.
"""
import copy, re

import retention

BAR = 8            # out of 10 — at most one heavy miss (first line, hero number, length) or two light ones
MAX_REWRITES = 2   # each is one Claude call on the script model


def _free_fixes(cfg):
    """Deterministic repairs for checks that don't need a writer. Returns the list of what changed."""
    done = []
    segs = cfg["segments"]
    first = (segs[0].get("text") or "").strip()
    words = first.split()
    if words and len(words) <= 8:                                   # on-screen hook = the words actually spoken
        spoken = {w.strip(".,!?—'").lower() for w in words}
        hook = {w.strip(".,!?—'").lower() for l in (cfg.get("hook") or {}).get("lines", []) for w in l[0].split()}
        if len(hook & spoken) / max(len(hook), 1) < .5:
            up = first.upper().rstrip(".")
            mid = max(1, len(up.split()) // 2)
            parts = up.split()
            cfg.setdefault("hook", {"size": 140, "y": 600})["lines"] = [[" ".join(parts[:mid]), "w"], [" ".join(parts[mid:]) + ".", "a"]]
            done.append("hook text now matches the first spoken line")
    v = segs[0].get("vis") or {}
    if v.get("t") == "kb" and abs(v.get("z0", 1) - v.get("z1", 1)) < .3:
        v["z0"], v["z1"] = 1.0, 1.35
        done.append("opening shot now zooms so frame 0 isn't a still")
    if any(retention.est(s) > 6 for s in segs[1:]):
        split = segs[:1] + retention.split_long(segs[1:])
        if len(split) > len(segs):
            cfg["segments"] = split
            done.append("long beats split so the picture changes every ≤6s")
    return done


def best_title(pkg):
    """Pick the title (from the writer's options) that passes the most checklist items. Free."""
    import studio_channel
    opts = [pkg.get("title")] + list(pkg.get("title_options") or [])
    opts = [t for t in opts if t]
    if not opts:
        return None
    score = lambda t: sum(c["ok"] for c in studio_channel.title_checklist(t))
    best = max(opts, key=score)
    if best != pkg.get("title") and score(best) > score(pkg.get("title") or ""):
        rest = [t for t in opts if t != best]
        pkg["title"], pkg["title_options"] = best, rest
        return f"title swapped for a stronger option ({score(best)}/5 on the title checklist)"
    return None


def improve(cfg, pkg, rewrite):
    """rewrite(notes, current_cfg) -> new cleaned cfg (one Claude call). Returns (cfg, score, rows, log, held)."""
    log = _free_fixes(cfg)
    t = best_title(pkg)
    if t:
        log.append(t)
    score, rows = retention.check(cfg)
    tries = 0
    while score < BAR and tries < MAX_REWRITES:
        tries += 1
        misses = [m for ok, m in rows if not ok]
        notes = ("The Hook & retention check scored this " f"{score}/10; it must reach {BAR}/10. Fix exactly these, keep "
                 "every fact and the story: " + "; ".join(misses))
        try:
            new = rewrite(notes, copy.deepcopy(cfg))
        except Exception as e:                       # a failed rewrite keeps the best version so far
            log.append(f"rewrite {tries} failed ({type(e).__name__}) — kept the previous version")
            break
        log += _free_fixes(new)
        s2, r2 = retention.check(new)
        log.append(f"rewrite {tries}: {score}/10 → {s2}/10")
        if s2 >= score:
            cfg, score, rows = new, s2, r2
    held = [m for ok, m in rows if not ok] if score < BAR else []
    return cfg, score, rows, log, held
