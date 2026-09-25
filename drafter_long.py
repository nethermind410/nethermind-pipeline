#!/usr/bin/env python3
"""drafter_long.py — the Content agent's long-form: one topic researched deeply → a 10–12 minute episode.

    python3 drafter_long.py "topic"                 draft episodes/<id>.json (+ packaging/<id>_long.json), as a draft
    python3 drafter_long.py --redraft <id> "notes"  rewrite with your notes (research kept)

This is the real long-form — one story told in depth, in chapters — not Shorts stitched together. Each chapter
is written so its lines tagged for "short" also stand alone as a 40–60s Short, so one research pass feeds the
whole week (episode.py cuts them). Steps of one Content task:
  Researcher     deep web research: 15+ sourced facts, a chapter outline with a mini-arc each, caveats
  Script writer  the episode: cold open, 5–7 chapters (~250–350 words each), outro that names the next episode
  Packaging      title options, a description with a {CHAPTERS} slot (make_long.py fills the real timestamps),
                 tags, pinned comment, 3 thumbnail options for YouTube's Test & Compare
Nothing is rendered or posted: it waits in Today. Approve → Production fetches the visuals and renders it.
"""
import json, re, sys
from pathlib import Path

import drafter
import orchestrator as nether
from drafter import ask, read, slug, RULES

HERE = Path(__file__).resolve().parent
EPS, PKG, DRAFTS = HERE / "episodes", HERE / "packaging", HERE / "out" / "drafts"
TARGET_WORDS = (1400, 2100)          # ≈ 9–13 minutes at Kokoro's ~2.8 words/sec
MAX_AI_IMAGES = 12                   # Cloudflare's free tier makes ~30 images a day; real photos fill the rest

LONG_RULES = """Long-form rules (YouTube, 16:9, 10–12 minutes): open cold on the single most surprising claim (no
"welcome back", no channel intro); make a promise in the first 30 seconds of what the viewer will know by the end;
every chapter is a mini-story with its own question, turn and payoff, and ends on a line that pulls into the next;
re-hook every 60–90 seconds; state caveats honestly; the outro names next week's episode. Voice: curious, direct,
a little dry — a knowledgeable friend, never a lecture."""


ICEBERG = """Format: an ICEBERG video essay — the topic broken into 5 tiers of obscurity, descending: Tier 1 "The
Surface" (what every fan knows, told with a twist), Tier 2, Tier 3, Tier 4, Tier 5 "The Bottom" (deep lore almost nobody
knows). Each tier is one chapter holding 3–5 entries; each entry is a mini-story (claim → surprise → why it matters).
Every entry must be verified; label shaky ones honestly as rumours. The deeper the tier, the stranger — but never
invented."""


def is_iceberg(topic, style=None):
    return style == "iceberg" or (style is None and "iceberg" in topic.lower())


def research(topic, style=None):
    prompt = f"""You are the Researcher for Nethermind's weekly long-form episode. Research this topic in depth with
web search and fetch: "{topic}"

{RULES}
{LONG_RULES}
{ICEBERG if is_iceberg(topic, style) else ""}

What the channel has learned from real results — follow it:
{read(HERE / "LEARNINGS.md", 4000)}

Verify every claim against a reliable source (primary sources, publishers, museums, peer-reviewed papers, reputable
press — not fan wikis or listicles). Find where the popular version is wrong. Never include a claim you couldn't source.
Reply with ONLY this JSON:
{{"angle": "the episode's big surprising claim, one sentence",
  "promise": "what the viewer will understand by the end",
  "popular_version": "...", "true_version": "...",
  "outline": [{{"chapter": "title", "question": "what this chapter answers", "turn": "the surprise", "payoff": "..."}}],
  "facts": [{{"claim": "...", "source_title": "...", "source_url": "https://..."}}],
  "caveats": ["..."],
  "visuals": [{{"beat": "what's on screen", "kind": "real|ai", "query": "Wikimedia Commons search words", "prompt": "..."}}],
  "sources_for_description": ["Publisher (Title)"]}}
{"Exactly 5 chapters, one per tier, surface to bottom, with the entries in each." if is_iceberg(topic, style) else "5–7 chapters."} At least 15 facts. Prefer real public-domain photos (kind "real"); AI art only for comic, anime or game
character beats, archetype/pose/palette only — never a named character, costume or logo."""
    r = ask(prompt, ["WebSearch", "WebFetch"], timeout=1500)
    if len(r.get("facts") or []) < 8 or len(r.get("outline") or []) < 3:
        raise RuntimeError("The research came back too thin for a long-form (under 8 sourced facts or 3 chapters).")
    return r


def write_episode(topic, eid, facts, notes=None, current=None, style=None):
    ice = is_iceberg(topic, style)
    prompt = f"""You are the Script writer for Nethermind's weekly long-form episode: "{topic}".

{RULES}
{LONG_RULES}
{ICEBERG if ice else ""}
{'For the iceberg: 5 chapters, one per tier, surface → bottom. Give each chapter a "tier_label" (e.g. "TIER 3") and a "depth" (2–3 words shown on the iceberg, e.g. "ONLY COLLECTORS KNOW"). The chapter title names the tier (e.g. "Tier 3: The Cancelled Games").' if ice else ""}

Checked research — use ONLY these facts:
{json.dumps(facts, ensure_ascii=False)[:14000]}

{"Courtney's notes on the last draft — do what they ask:" + chr(10) + notes + chr(10) + "Last draft:" + chr(10) + json.dumps(current, ensure_ascii=False)[:9000] if notes else ""}

Beats use the same shape as the channel's Shorts (this is a real one, match its style):
{drafter.example_cfg()[:4000]}

Write the episode as ONE JSON object:
{{"id": "{eid}", "title": "episode title", "next": "NEXT WEEK'S EPISODE, 3–6 WORDS",
  "palette": {{"accent": [r,g,b], "accent2": [r,g,b]}}, "score": "deep",
  "intro": [beats — the cold open, 30–45 seconds, each with "in": ["long"]],
  "chapters": [{{"id": "ch1", "title": "chapter title",
                 "hook": {{"lines": [["WORDS", "w"], ["PAYOFF.", "a"]], "size": 140, "y": 600}},
                 "segments": [beats]}}],
  "outro": [beats — 20–30 seconds, names next week's episode, each with "in": ["long"]]}}
Beat: {{"id": "s1", "text": "spoken line, 8–18 words", "vis": {{"t": "kb", "src": "name.jpg", "z0": 1.1, "z1": 1.3,
  "cx": 0.5, "cy": 0.45, "real": {{"query": "..."}} OR "prompt": "..."}}, "gap": 0.15}}, optional
  "hero": {{"at": <word index>, "lines": ["BIG TEXT"], "col": "a2", "y": 390, "size": 150}} on the line with a key number.
Rules: {TARGET_WORDS[0]}–{TARGET_WORDS[1]} words in total. 5–7 chapters of ~12–22 beats. In every chapter, mark the
lines that only make sense in the long-form (context, bridges, "as we saw") with "in": ["long"]; the remaining lines,
read on their own, must work as a 40–60 second Short with the chapter's hook text as its first line. At most
{MAX_AI_IMAGES} AI images in the whole episode; reuse each image on 2–4 consecutive beats with different zoom/centre.
Reply with ONLY the JSON."""
    return ask(prompt, timeout=1500)


def write_packaging(ep, facts):
    chapters = "\n".join(f"- {c['title']}" for c in ep["chapters"])
    prompt = f"""You are the Packaging agent for Nethermind's weekly long-form (YouTube only, 16:9). Package it.
Episode: {ep["title"]}. Angle: {facts.get("angle")}. Promise: {facts.get("promise")}.
Chapters:
{chapters}
Sources: {json.dumps(facts.get("sources_for_description") or [], ensure_ascii=False)}
Voice reference (a real Short's packaging): {read(PKG / "_example.json", 2000)}
Reply with ONLY this JSON:
{{"title": "best title (≤70 chars, curiosity gap, honest)", "title_options": ["2 alternatives"],
  "youtube_description": "2 short hook paragraphs, then the line {{CHAPTERS}} on its own, then 'Sources:' with each source,
     a subscribe line, and 5–8 hashtags incl. #nethermind",
  "youtube_tags": "comma-separated, 10–15 tags incl. nethermind",
  "pinned_comment": "a question that makes people answer",
  "thumbnail": {{"lines": ["2–3", "SHORT", "LINES"], "accent": 1, "cx": 0.5, "cy": 0.4, "zoom": 1.0}},
  "thumbnail_options": [{{"lines": ["..."], "accent": 1}}, {{"lines": ["..."], "accent": 1}}]}}"""
    return ask(prompt)


# ------------------------------------------------------------------ checks + files
def clean_episode(ep, eid):
    chapters = ep.get("chapters") or []
    if not 3 <= len(chapters) <= 8:
        raise ValueError(f"The episode has {len(chapters)} chapters; it needs 3–8.")
    blocks = [("intro", ep.get("intro") or [])] + [(f"c{i + 1}", c.get("segments") or []) for i, c in enumerate(chapters)] \
             + [("outro", ep.get("outro") or [])]
    flat = [(name, s) for name, segs in blocks for s in segs]
    words = sum(len(str(s.get("text", "")).split()) for _, s in flat)
    if words < TARGET_WORDS[0] * 0.7:
        raise ValueError(f"The episode is only {words} words (~{words / 168:.0f} min) — too short for a long-form.")
    for name, s in flat:                                      # unique ids across the whole episode
        s["id"] = f"{name}_{re.sub(r'[^a-z0-9]', '', str(s.get('id', 's')))[:6] or 's'}"
    segs = drafter.clean_segments([s for _, s in flat], eid)   # validates beats + renames new images consistently
    ai = {s["vis"]["src"] for s in segs if s["vis"].get("prompt")}
    if len(ai) > MAX_AI_IMAGES + 4:
        raise ValueError(f"{len(ai)} AI images — over the daily free limit; ask for more real photos.")
    it = iter(segs)
    ep["intro"] = [next(it) for _ in blocks[0][1]]
    for n, (c, (_, raw)) in enumerate(zip(chapters, blocks[1:-1]), 1):
        c["segments"] = [next(it) for _ in raw]
        c["id"] = f"ch{n}"                                    # unique: it names the Short cut from it
        c.setdefault("title", c["id"])
        c.setdefault("hook", {"lines": [], "size": 140, "y": 600})
    ep["outro"] = [next(it) for _ in blocks[-1][1]]
    for s in ep["intro"] + ep["outro"]:
        s["in"] = ["long"]
    ep.update(id=eid, chapters=chapters, kind="long")
    ep.setdefault("score", "deep")
    ep.setdefault("palette", {"accent": [224, 41, 75], "accent2": [250, 204, 21]})
    ep.setdefault("credit", "ART: AI-GEN (ORIGINAL) · IMAGES: CC BY / PD — SOURCES IN THE DESCRIPTION")
    return ep, words


def new_id(topic):
    base = "ep_" + slug(topic)[:36]
    eid, n = base, 2
    while (EPS / f"{eid}.json").exists():
        eid, n = f"{base}_{n}", n + 1
    return eid


def draft(topic, notes=None, eid=None, style=None):
    topic = re.sub(r"\s+", " ", str(topic)).strip()[:160]
    redo = eid is not None
    if redo:
        record = json.loads(read(DRAFTS / f"{eid}.json") or "{}")
        topic = record.get("topic", topic)
        style = style or record.get("style") or load(eid).get("style")
    else:
        eid, record = new_id(topic), {"topic": topic, "kind": "long", "notes": [], "style": style}
    parent = nether.begin("content", f"{'Redraft' if redo else 'Draft'} long-form: {topic}", video=f"{eid}_long",
                          input={"topic": topic, "notes": notes},
                          retry={"kind": "redraft_long", "id": eid, "notes": notes} if redo else {"kind": "draft_long", "topic": topic})
    cur = None
    try:
        cur = nether.begin("content", "Deep research", sub="research", parent=parent)
        if redo and record.get("research"):
            facts = record["research"]
            nether.finish(cur, {"reused": True})
        else:
            facts = research(topic, style)
            nether.finish(cur, {"facts": len(facts["facts"]), "chapters": len(facts.get("outline", []))})
        record["research"] = facts

        cur = nether.begin("content", "Write the episode", sub="episodes", parent=parent)
        current = json.loads(read(EPS / f"{eid}.json") or "null") if redo else None
        ep, words = clean_episode(write_episode(topic, eid, facts, notes, current, style), eid)
        if is_iceberg(topic, style):                   # the tier chart the renderer draws for each chapter card
            cols = ["a", "a", "a", "a2", "a2"]
            ep["iceberg"] = {"tiers": [{"label": str(c.get("tier_label") or f"TIER {i + 1}").upper(),
                                        "depth": str(c.get("depth") or ("THE SURFACE" if i == 0 else "THE BOTTOM" if i == len(ep["chapters"]) - 1 else "DEEPER")).upper(),
                                        "col": cols[min(i, 4)]} for i, c in enumerate(ep["chapters"])]}
            ep["style"] = "iceberg"
        nether.finish(cur, {"chapters": len(ep["chapters"]), "words": words, "minutes": round(words / 168, 1)})

        cur = nether.begin("content", "Packaging (+3 thumbnails)", sub="packaging", parent=parent)
        pkg = write_packaging(ep, facts)
        if not pkg.get("title"):
            raise RuntimeError("Packaging came back without a title.")
        if "{CHAPTERS}" not in pkg.get("youtube_description", ""):
            pkg["youtube_description"] = pkg.get("youtube_description", "") + "\n\n{CHAPTERS}"
        pkg["drafted"] = True
        import business, intelligence                    # Business: affiliate + newsletter links in the description
        business.apply_links(pkg, topic, intelligence.lane_of(topic))
        pkg.setdefault("thumbnail", {}).setdefault("src", ep["chapters"][0]["segments"][0]["vis"]["src"])
        nether.finish(cur, {"title": pkg["title"]})
        cur = None

        ep["draft"] = {"at": nether.now(), "topic": topic, "task": parent}
        if notes:
            record["notes"].append({"at": nether.now(), "notes": notes})
        record.update(task=parent, words=words)
        EPS.mkdir(exist_ok=True)
        (EPS / f"{eid}.json").write_text(json.dumps(ep, indent=1, ensure_ascii=False))
        (PKG / f"{eid}_long.json").write_text(json.dumps(pkg, indent=1, ensure_ascii=False) + "\n")
        DRAFTS.mkdir(parents=True, exist_ok=True)
        (DRAFTS / f"{eid}.json").write_text(json.dumps(record, indent=1, ensure_ascii=False))
        nether.finish(parent, {"id": eid, "title": pkg["title"], "minutes": round(words / 168, 1)})
        return eid
    except (Exception, SystemExit) as e:
        if cur:
            nether.fail(cur, f"{type(e).__name__}: {e}")
        nether.fail(parent, f"{type(e).__name__}: {e}")
        raise


def load(eid):
    return json.loads(read(EPS / f"{eid}.json") or "{}")


def is_draft(eid):
    return bool(re.fullmatch(r"[a-z0-9_]{3,60}", eid) and load(eid).get("draft"))


def save_lines(eid, lines):
    """lines: {beat id: text} — edit a long-form draft's spoken lines (visuals and timing stay)."""
    if not is_draft(eid):
        raise ValueError("That episode isn't a draft any more.")
    ep, changed = load(eid), []
    for s in ep.get("intro", []) + [x for c in ep["chapters"] for x in c["segments"]] + ep.get("outro", []):
        if s["id"] in lines:
            new = re.sub(r"\s+", " ", str(lines[s["id"]])).strip()
            if not new or len(new) > 400:
                raise ValueError(f"Line {s['id']} is empty or too long.")
            if new != s["text"]:
                s["text"] = new
                changed.append(s["id"])
    (EPS / f"{eid}.json").write_text(json.dumps(ep, indent=1, ensure_ascii=False))
    return {"ok": True, "changed": changed}


def approve(eid):
    if not is_draft(eid):
        raise ValueError("That episode isn't waiting for approval.")
    ep = load(eid)
    ep.pop("draft", None)
    (EPS / f"{eid}.json").write_text(json.dumps(ep, indent=1, ensure_ascii=False))
    rec = json.loads(read(DRAFTS / f"{eid}.json") or "{}")
    rec["approved"] = nether.now()
    (DRAFTS / f"{eid}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False))
    return {"ok": True, "id": eid, "long": True}


def discard(eid):
    if not is_draft(eid):
        raise ValueError("Only an unapproved draft can be discarded.")
    for p in (EPS / f"{eid}.json", PKG / f"{eid}_long.json", DRAFTS / f"{eid}.json", EPS / f"{eid}.plan.md"):
        p.unlink(missing_ok=True)
    return {"ok": True}


def drafts():
    """Long-form drafts in the same shape the review page uses for Shorts, with a chapter on each line."""
    out = []
    for p in sorted(EPS.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if EPS.exists() else []:
        if p.stem.startswith("_"):
            continue
        try:
            ep = json.loads(p.read_text())
        except Exception:
            continue
        if not ep.get("draft"):
            continue
        eid = p.stem
        pkg = json.loads(read(PKG / f"{eid}_long.json") or "{}")
        rec = json.loads(read(DRAFTS / f"{eid}.json") or "{}")
        lines = []
        for chap, segs in [("Cold open", ep.get("intro", []))] + [(c["title"], c["segments"]) for c in ep["chapters"]] \
                          + [("Outro", ep.get("outro", []))]:
            for s in segs:
                v = s["vis"]
                lines.append({"id": s["id"], "text": s["text"], "chapter": chap, "long_only": s.get("in") == ["long"],
                              "hero": (s.get("hero") or {}).get("lines"),
                              "visual": v.get("real", {}).get("query") if v.get("real") else v.get("prompt"),
                              "kind": "real photo" if v.get("real") else "AI art" if v.get("prompt") else "same picture, new framing"})
        words = sum(len(l["text"].split()) for l in lines)
        out.append({"id": eid, "kind": "long", "topic": ep["draft"].get("topic"), "at": ep["draft"].get("at"),
                    "title": pkg.get("title") or ep.get("title"), "title_options": pkg.get("title_options", []),
                    "title_pkg": f"{eid}_long", "hook_options": [], "lines": lines, "minutes": round(words / 168, 1),
                    "chapters": [c["title"] for c in ep["chapters"]], "end": [f"NEXT WEEK: {ep.get('next', '')}"],
                    "thumbnails": [pkg.get("thumbnail", {})] + pkg.get("thumbnail_options", []),
                    "research": rec.get("research"), "check": None, "notes": rec.get("notes", [])})
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "--redraft":
        print(draft("", notes=" ".join(a[2:]), eid=a[1]))
    else:
        print(draft(" ".join(a)))
