#!/usr/bin/env python3
"""learning.py — how NETHER gets better: your decisions + real results → new weights and lessons.

    python3 learning.py            link scorecards to posted videos, re-weight, write lessons

Collaboration: every Intelligence scorecard waits for your call — "Make it" or
"Not for us", with a reason. Those calls become the "Your taste" part of the
next scorecard for that lane, and "Make it" adds the topic to TOPICS.md.

Learning: once a video made from a scorecard is posted and stats.py has its
views, each scorecard is a prediction that can be checked. With enough of
them, each part of the score (demand, competition, fit, taste, visuals,
sources) is re-weighted by whether high marks on it really went with more
views. Each part moves at most ±25% from its default (recomputed from scratch every run, so
it never compounds) and needs at least 2 videos on each side, so one lucky video can't swing it. Weights → out/intel_weights.json;
lessons → the auto block in LEARNINGS.md, which the daily build already reads.
"""
import json, re, statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEL = HERE / "out" / "intel"
WEIGHTS = HERE / "out" / "intel_weights.json"
DECISIONS = HERE / "out" / "learning" / "decisions.jsonl"
MIN_SIDE = 2          # videos needed on each side of a component before it moves
STOP = set("the a an of in on is are was were to for and or it its this that with at by from be has have had your you "
           "why how what who can could would still we our they them not always real really just".split())


def _cards():
    return [json.loads(p.read_text()) for p in sorted(INTEL.glob("*.json"))] if INTEL.exists() else []


def _save(card):
    (INTEL / f"{card['slug']}.json").write_text(json.dumps(card, indent=1, ensure_ascii=False))


def _words(text):
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and len(w) > 2}


# ------------------------------------------------------------------ collaboration
def taste(lane):
    calls = [c["decision"]["choice"] for c in _cards() if c.get("lane") == lane and c.get("decision")]
    if len(calls) < 2:
        return {"score": 0.5, "calls": len(calls),
                "say": f"You've judged {len(calls)} {lane} topic(s) so far — your taste counts as neutral until 2."}
    rate = calls.count("make") / len(calls)
    return {"score": round(rate, 2), "calls": len(calls),
            "say": f"You said \"make it\" to {calls.count('make')} of {len(calls)} {lane} topics."}


def decide(slug, choice, reason=""):
    p = INTEL / f"{slug}.json"
    if choice not in ("make", "skip") or not re.fullmatch(r"[a-z0-9_]+", slug) or not p.exists():
        raise ValueError("Pick Make it or Not for us.")
    card = json.loads(p.read_text())
    import orchestrator as nether
    card["decision"] = {"choice": choice, "reason": str(reason).strip()[:300], "at": nether.now()}
    _save(card)
    DECISIONS.parent.mkdir(parents=True, exist_ok=True)
    with open(DECISIONS, "a") as f:
        f.write(json.dumps({"slug": slug, "lane": card["lane"], "score": card["score"], **card["decision"]}) + "\n")
    added = None
    if choice == "make":
        import studio_api
        try:
            studio_api.add_idea("Intelligence picks", card["topic"], "hero" if card["lane"] in ("marvel", "anime", "gaming") else "fact",
                                f"NETHER {card['score']}/100 — {(card['evidence'].get('sources', {}).get('articles') or [{}])[0].get('url', 'to verify')}")
            added = "Added to TOPICS.md → Intelligence picks."
        except ValueError as e:
            added = f"Couldn't add to TOPICS.md: {e}"
    return {"ok": True, "reply": added or "Noted — NETHER will weigh that against this lane next time."}


# ------------------------------------------------------------------ learning from results
def _views():
    try:
        vids = json.loads((HERE / "out" / "stats.json").read_text()).get("videos", {})
    except Exception:
        return {}
    return {v: int(sum(p.get("views") or 0 for p in ps)) for v, ps in vids.items()}


def _title(vid):
    try:
        return json.loads((HERE / "packaging" / f"{vid}.json").read_text()).get("title", "")
    except Exception:
        return ""


def link(cards, views):
    """Match "make it" scorecards to posted videos by shared words (topic vs video id + title)."""
    made, taken = [], {c["made_as"] for c in cards if c.get("made_as")}
    for c in cards:
        if c.get("made_as") or not c.get("decision") or c["decision"]["choice"] != "make":
            continue
        tw = _words(c["topic"])
        hits = sorted(((len(tw & _words(vid.replace("_", " ") + " " + _title(vid))), vid) for vid in views
                       if vid not in taken), reverse=True)
        if not hits:
            continue
        (n, best), runner = hits[0], (hits[1][0] if len(hits) > 1 else 0)
        if n >= min(2, len(tw)) and n > runner:      # a tie is ambiguous: link nothing rather than guess
            taken.add(best)
            c["made_as"] = best
            _save(c)
            made.append((c["topic"], best))
    return made


def calibrate(cards, views):
    import intelligence
    w = dict(intelligence.DEFAULT_WEIGHTS)    # always from the defaults: the same evidence can't compound run after run
    done = [c for c in cards if c.get("made_as") in views]
    notes, new = [], dict(w)
    for comp in w:
        hi = [views[c["made_as"]] for c in done if (c["components"][comp]["score"] or 0) >= 0.6]
        lo = [views[c["made_as"]] for c in done if c["components"][comp]["score"] is not None
              and c["components"][comp]["score"] < 0.6]
        if len(hi) < MIN_SIDE or len(lo) < MIN_SIDE:
            continue
        ratio = (statistics.median(hi) + 1) / (statistics.median(lo) + 1)
        mult = min(max(ratio ** 0.5, 0.8), 1.25)
        new[comp] = w[comp] * mult
        notes.append(f"{comp}: high-scoring topics got a median {statistics.median(hi):,.0f} views vs "
                     f"{statistics.median(lo):,.0f} for low ({len(hi)} vs {len(lo)} videos) → weight ×{mult:.2f}")
    tot = sum(new.values())
    new = {k: round(v / tot * 100, 1) for k, v in new.items()}
    acc = None
    if len(done) >= 4:
        def ranks(xs):                         # average rank for ties (scores are rounded, ties are common)
            order = sorted(range(len(xs)), key=lambda i: xs[i])
            r, i = [0.0] * len(xs), 0
            while i < len(order):
                j = i
                while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
                    j += 1
                for k in range(i, j + 1):
                    r[order[k]] = (i + j) / 2
                i = j + 1
            return r
        rs, rv = ranks([c["score"] for c in done]), ranks([views[c["made_as"]] for c in done])
        ms, mv = sum(rs) / len(rs), sum(rv) / len(rv)
        cov = sum((a - ms) * (b - mv) for a, b in zip(rs, rv))
        den = (sum((a - ms) ** 2 for a in rs) * sum((b - mv) ** 2 for b in rv)) ** 0.5
        acc = cov / den if den else 0.0            # Spearman = Pearson on ranks, correct with ties
    hist = []
    try:
        hist = json.loads(WEIGHTS.read_text()).get("history", [])
    except Exception:
        pass
    import orchestrator as nether
    if notes:
        hist.append({"at": nether.now(), "weights": new, "notes": notes})
    WEIGHTS.parent.mkdir(exist_ok=True)
    WEIGHTS.write_text(json.dumps({"weights": new, "history": hist[-50:], "checked": len(done),
                                   "rank_agreement": None if acc is None else round(acc, 2)}, indent=1))
    return new, notes, len(done), acc


def lessons(cards, views, weights, notes, checked, acc):
    out = []
    lanes = {}
    for c in cards:
        if c.get("decision"):
            lanes.setdefault(c["lane"], []).append(c["decision"]["choice"])
    for lane, calls in sorted(lanes.items()):
        if len(calls) >= 2:
            out.append(f"Courtney's taste — {lane}: \"make it\" on {calls.count('make')} of {len(calls)} scorecards.")
    reasons = [c["decision"]["reason"] for c in cards if c.get("decision") and c["decision"].get("reason")]
    if reasons:
        out.append("Recent reasons given: " + " | ".join(f'"{r}"' for r in reasons[-5:]))
    out += notes
    if acc is not None:
        out.append(f"Scorecards vs real views across {checked} made videos: rank agreement {acc:+.2f} "
                   "(1 = perfect, 0 = no better than chance).")
    elif checked:
        out.append(f"{checked} scorecard(s) linked to posted videos — need 4 before judging the score's accuracy.")
    if not out:
        out.append("Nothing learned yet: investigate topics in Studio and give each scorecard your call.")
    return out


def write_learnings(lines):
    p = HERE / "LEARNINGS.md"
    text = p.read_text() if p.exists() else "# What's working — Nethermind\n"
    block = ("<!-- nether:auto — written by learning.py; edit above or below, not inside -->\n"
             "## NETHER learned (automatic)\n\n" + "\n".join(f"- {l}" for l in lines) + "\n<!-- /nether:auto -->")
    if "<!-- nether:auto" in text:
        text = re.sub(r"<!-- nether:auto.*?<!-- /nether:auto -->", lambda m: block, text, flags=re.S)
    else:
        text = text.rstrip() + "\n\n" + block + "\n"
    p.write_text(text)


def summary():
    """For Studio: the scorecards, what's linked, weights now vs default, lessons."""
    import intelligence
    cards, views = _cards(), _views()
    try:
        wj = json.loads(WEIGHTS.read_text())
    except Exception:
        wj = {"weights": intelligence.weights(), "history": []}
    auto = ""
    try:
        m = re.search(r"## NETHER learned \(automatic\)\n\n(.*?)\n<!-- /nether:auto -->", (HERE / "LEARNINGS.md").read_text(), re.S)
        auto = m.group(1) if m else ""
    except Exception:
        pass
    return {"cards": [{k: c.get(k) for k in ("topic", "slug", "lane", "score", "verdict", "reasons", "failed", "decision",
                                              "made_as", "at", "components", "evidence")}
                      | {"views": views.get(c.get("made_as"))} for c in sorted(cards, key=lambda c: c["at"], reverse=True)],
            "weights": wj["weights"], "default": intelligence.DEFAULT_WEIGHTS, "history": wj.get("history", [])[-5:],
            "lessons": [l[2:] for l in auto.splitlines() if l.startswith("- ")]}


def run():
    import orchestrator as nether
    tid = nether.begin("analytics", "Learning loop", sub="learning")
    try:
        cards, views = _cards(), _views()
        made = link(cards, views)
        w, notes, checked, acc = calibrate(cards, views)
        ls = lessons(cards, views, w, notes, checked, acc)
        write_learnings(ls)
        nether.finish(tid, {"linked": made, "weights": w, "lessons": ls})
        return {"linked": made, "weights": w, "lessons": ls}
    except (Exception, SystemExit) as e:
        nether.fail(tid, f"{type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    r = run()
    for t, v in r["linked"]:
        print(f"linked: {t} → {v}")
    print("weights:", r["weights"])
    for l in r["lessons"]:
        print(" -", l)
