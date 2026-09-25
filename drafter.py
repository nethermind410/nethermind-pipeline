#!/usr/bin/env python3
"""drafter.py — the Content agent: research → script → packaging, as a draft for you to approve.

    python3 drafter.py "topic"              draft a new video (cfg + packaging marked as a draft)
    python3 drafter.py --redraft <id> "notes"   rewrite the script with your notes (research kept)

Three Claude calls (your claude.ai login, headless), each a step of one Content task:
  Researcher     web search/fetch; every claim needs a source; the popular vs true version; one hero number
  Script writer  the config (lines + visuals plan + end card), from the checked facts only
  Packaging      title options, descriptions, captions, tags, pinned comment, thumbnail words
then the Hook & retention check scores it. Nothing is rendered or posted: the draft
waits in Today. Approve it in Studio and Production builds it; edit lines first if you like.
"""
import datetime, json, os, re, subprocess, sys
from pathlib import Path

import orchestrator as nether
import retention

HERE = Path(__file__).resolve().parent
CFG, PKG, ASSETS = HERE / "cfg", HERE / "packaging", HERE / "assets"
DRAFTS = HERE / "out" / "drafts"
ID_RE = re.compile(r"^[a-z0-9_]{3,48}$")


# ------------------------------------------------------------------ Claude
def ask(prompt, tools=(), timeout=900):
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY")}
    env["PATH"] = f"{Path.home()}/.local/bin:" + env.get("PATH", "/usr/bin:/bin")
    try:
        r = subprocess.run(["claude", "-p", prompt, "--output-format", "json", "--permission-prompts", "none",
                            "--allowedTools", ",".join(["ToolSearch", *tools])],
                           capture_output=True, text=True, timeout=timeout, env=env, cwd=HERE)
    except FileNotFoundError:
        raise RuntimeError("The claude command isn't installed on this Mac (needed to draft).")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Claude took longer than {timeout // 60} minutes — try again.")
    try:
        res = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise RuntimeError("Claude didn't answer. Is it logged in? Run `claude` in Terminal and type /login. "
                           + (r.stderr or "")[-300:])
    if res.get("is_error"):
        raise RuntimeError(f"Claude: {res.get('result')}")
    text = res.get("result", "")
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S) or re.search(r"(\{.*\})", text, re.S)
    if not m:
        raise RuntimeError("Claude's answer wasn't JSON; try again.")
    return json.loads(m.group(1))


def read(p, limit=None):
    try:
        t = Path(p).read_text()
        return t[:limit] if limit else t
    except Exception:
        return ""


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40] or "video"


def open_ideas(n=12):
    import studio_api
    out = []
    for s in studio_api.ideas()["sections"]:
        out += [i["hook"] for i in s["items"] if not i["made"] and not i["dismissed"]]
    return out[:n]


def example_cfg():
    for vid in ("regrow_body", "maggott", "wolverine_not_always_mutant", "hulk_color_origin"):
        t = read(CFG / f"{vid}.json")
        if t:
            return t
    return ""


RULES = """Channel: Nethermind — faceless, fact-checked YouTube Shorts on Marvel/comics history, anime, gaming,
space and strange animals; the best format so far is "a comic power that's real biology".
Retention rules: the hook is frame zero — line 1 is 8 words or fewer and says what the on-screen hook says;
show one hero number (the thing people repeat) in the first 3 seconds if the story allows; most lines 8–18
words so the picture changes every few seconds; a real payoff (a reveal, not a summary); state the honest
caveat where the popular version is exaggerated; end by naming the next video (the end card), not "subscribe".
Target 45–70 seconds of narration (about 125–190 words in total)."""


# ------------------------------------------------------------------ steps
def research(topic):
    prompt = f"""You are the Researcher for Nethermind. Research this video topic with web search and fetch:
"{topic}"

{RULES}

What the channel has learned (from real results — follow it):
{read(HERE / "LEARNINGS.md", 4000)}

Find the most surprising TRUE version of this story. Verify every claim against a reliable source (primary
sources, publishers, museums, peer-reviewed papers, reputable press — not fan wikis or listicles). If the
popular version is exaggerated, find the real range or caveat. Never include a claim you could not source.
Reply with ONLY this JSON:
{{"angle": "one sentence: the video's surprising claim",
  "popular_version": "what most people think", "true_version": "what's actually true",
  "hero_number": {{"value": "e.g. 1901 or 1 CELL", "what": "what it measures"}},
  "caveat": "the honest limit of what's known",
  "facts": [{{"claim": "...", "source_title": "...", "source_url": "https://..."}}],
  "visuals": [{{"beat": "what's on screen", "kind": "real|ai",
               "query": "Wikimedia Commons search words, for kind=real",
               "prompt": "archetype/pose/palette scene, for kind=ai — never a named character, costume or logo"}}],
  "sources_for_description": ["Publisher (Title)"]}}
Use kind "real" for real animals, people, places, science and public-domain history; "ai" only for comic,
anime or game-character beats. At least 5 facts."""
    r = ask(prompt, ["WebSearch", "WebFetch"])
    if len(r.get("facts") or []) < 3:
        raise RuntimeError("The research came back with fewer than 3 sourced facts — the topic may be too thin to verify.")
    return r


def write_script(topic, vid, facts, notes=None, current=None):
    ideas = "\n".join(f"- {i}" for i in open_ideas())
    prompt = f"""You are the Script writer for Nethermind. Write the video config for: "{topic}".

{RULES}

Checked research — use ONLY these facts, nothing else:
{json.dumps(facts, ensure_ascii=False)[:9000]}

{"Courtney's notes on the last draft — do what they ask:" + chr(10) + notes + chr(10) + "Last draft:" + chr(10) + json.dumps(current, ensure_ascii=False)[:6000] if notes else ""}

The config format (one JSON object; this is a real, recent one to match in style):
{example_cfg()[:7000]}

Rules for the config:
- "id": "{vid}", "file": "{vid}". Keep "score", "credit", "palette" (two RGB accents that suit the topic).
- "segments": 7–12 beats. Each: "id" ("s1", "s2"… unique), "text" (the spoken line), "vis", "gap" (0.12–0.2).
- First segment has "hook": true. Put a "hero": {{"at": <word index>, "lines": ["BIG TEXT"], "col": "a2", "y": 390, "size": 150}}
  on the line that says the hero number — as early as the story allows.
- Every "vis" is {{"t": "kb", "src": "<new file name>.jpg", "z0": .., "z1": .., "cx": .., "cy": ..}} with EITHER
  "real": {{"query": "Wikimedia Commons search words"}} (real subjects) OR "prompt": "..." (AI art for comic/anime/game
  beats: stylized, archetype/pose/palette only — never a named character, exact costume or logo). Reuse the same
  src on consecutive beats with a different zoom/centre so the picture keeps moving. Vary z0/z1 between 1.0 and 1.5.
- "hook": {{"lines": [["WORDS", "w"], ["MORE WORDS", "w"], ["PAYOFF.", "a"]], "size": 140, "y": 600}} — the same words as line 1.
- "end": {{"at": 1.4, "lines": ["SUBSCRIBE FOR MORE", "NEXT:", "<the next video, 3–6 words, upper case>"]}}. Pick the
  next video from these open ideas (the one that follows best):
{ideas}
Reply with ONLY the JSON config."""
    return ask(prompt)


def write_packaging(cfg, facts):
    script = " ".join(s["text"] for s in cfg["segments"])
    prompt = f"""You are the Packaging agent for Nethermind (faceless fact-checked Shorts). Package this video.
Script: {script}
Sources: {json.dumps(facts.get("sources_for_description") or [f.get("source_title") for f in facts.get("facts", [])], ensure_ascii=False)}
Hero number: {json.dumps(facts.get("hero_number"), ensure_ascii=False)}
Match this real example's voice and shape:
{read(PKG / "_example.json", 3000)}
Reply with ONLY this JSON:
{{"title": "best title (≤70 chars, curiosity gap, no clickbait lies)",
  "title_options": ["4 alternatives"],
  "hook_options": ["3 alternative first lines, ≤8 words each"],
  "youtube_description": "hook paragraph, the story in 2–3 short paragraphs, a subscribe line naming the channel's niche,
     then 'Sources: ...' and 6–8 hashtags incl. #nethermind",
  "youtube_tags": "comma-separated, 8–12 tags, include nethermind",
  "tiktok_caption": "≤150 chars, a hook + 'Follow for...' + 3 hashtags incl #nethermind",
  "instagram_caption": "starts 'Send this to the ...', ≤220 chars, 3 hashtags incl #nethermind",
  "pinned_comment": "a question that makes people answer",
  "thumbnail": {{"lines": ["2–3", "SHORT", "LINES"], "accent": 2, "cx": 0.5, "cy": 0.4, "zoom": 1.0}}}}"""
    return ask(prompt)


# ------------------------------------------------------------------ checks + files
def clean_cfg(cfg, vid):
    segs = cfg.get("segments") or []
    if not 5 <= len(segs) <= 14:
        raise ValueError(f"The script has {len(segs)} beats; it needs 5–14.")
    segs = clean_segments(segs, vid)
    segs[0]["hook"] = True
    cfg.update(id=vid, file=vid, segments=segs)
    cfg.setdefault("score", "deep")
    cfg.setdefault("credit", "ART: AI-GEN (ORIGINAL) · IMAGES: CC BY / PD — SEE DESCRIPTION")
    cfg.setdefault("palette", {"accent": [224, 41, 75], "accent2": [250, 204, 21]})
    cfg.setdefault("hook", {"lines": [], "size": 140, "y": 600})
    end = cfg.get("end") or {}
    if not any("NEXT" in str(l) for l in end.get("lines", [])):
        cfg["end"] = {"at": 1.4, "lines": ["SUBSCRIBE FOR MORE", "NEXT:", "MORE BURIED HISTORY"]}
    return cfg


def clean_segments(segs, vid, id_prefix=""):
    """Validate beats and give new images names that can't clash with another video's. Shared by the Short and
    long-form writers; an image defined (search or prompt) on any beat can be reused by later beats."""
    seen, rename = set(), {}
    defined = {str((s.get("vis") or {}).get("src")) for s in segs            # new images need a search or a prompt
               if (s.get("vis") or {}).get("real") or (s.get("vis") or {}).get("prompt")}   # on at least one beat
    for i, s in enumerate(segs):
        sid = str(s.get("id") or f"{id_prefix}s{i + 1}")
        if not re.fullmatch(r"[a-z0-9_]{1,16}", sid) or sid in seen:
            sid = f"{id_prefix}s{i + 1}"
        seen.add(sid); s["id"] = sid
        s["text"] = re.sub(r"\s+", " ", str(s.get("text") or "")).strip()
        if not s["text"] or len(s["text"]) > 400:
            raise ValueError(f"Beat {sid} is empty or too long.")
        v = s.get("vis") or {}
        if v.get("t") != "kb":
            raise ValueError(f"Beat {sid} uses a '{v.get('t')}' visual; drafts use stills only.")
        src = str(v.get("src") or f"{sid}.jpg")
        if not (ASSETS / src).exists():            # new art: give it a name that can't clash with another video's
            if src not in defined:
                raise ValueError(f"Beat {sid} needs an image source: a Commons search or an AI prompt.")
            rename.setdefault(src, f"{vid}_{slug(Path(src).stem)[:24]}.jpg")
            v["src"] = rename[src]
        for k, lo, hi in (("z0", 1.0, 2.6), ("z1", 1.0, 2.6), ("cx", 0.0, 1.0), ("cy", 0.0, 1.0)):
            v[k] = min(max(float(v.get(k, (lo + hi) / 2 if k[0] == "c" else 1.15)), lo), hi)
        s["vis"] = v
        s["gap"] = min(max(float(s.get("gap", 0.15)), 0.05), 0.4)
        s.pop("hook", None)
    return segs


def new_id(topic):
    base = slug(topic)
    vid, n = base, 2
    while (CFG / f"{vid}.json").exists():
        vid, n = f"{base}_{n}", n + 1
    return vid


def save(vid, cfg, pkg, record):
    hook_src = cfg["segments"][0]["vis"]["src"]
    pkg.setdefault("thumbnail", {}).setdefault("src", hook_src)
    CFG.joinpath(f"{vid}.json").write_text(json.dumps(cfg, indent=1, ensure_ascii=False) + "\n")
    PKG.joinpath(f"{vid}.json").write_text(json.dumps(pkg, indent=1, ensure_ascii=False) + "\n")
    DRAFTS.mkdir(parents=True, exist_ok=True)
    DRAFTS.joinpath(f"{vid}.json").write_text(json.dumps(record, indent=1, ensure_ascii=False))


def draft(topic, notes=None, vid=None):
    """New draft (vid None) or a redraft of an existing one with notes. Returns the video id."""
    topic = re.sub(r"\s+", " ", str(topic)).strip()[:160]
    redo = vid is not None
    if redo:
        record = json.loads(read(DRAFTS / f"{vid}.json") or "{}")
        topic = record.get("topic", topic)
    else:
        vid, record = new_id(topic), {"topic": topic, "notes": []}
    parent = nether.begin("content", f"{'Redraft' if redo else 'Draft'}: {topic}", video=vid,
                          input={"topic": topic, "notes": notes},
                          retry={"kind": "redraft", "id": vid, "notes": notes} if redo else {"kind": "draft", "topic": topic})
    cur = None
    try:
        cur = nether.begin("content", "Research & fact-check", sub="research", parent=parent)
        if redo and record.get("research"):
            facts = record["research"]
            nether.finish(cur, {"reused": True})
        else:
            facts = research(topic)
            nether.finish(cur, {"facts": len(facts["facts"]), "angle": facts.get("angle")})
        record["research"] = facts

        cur = nether.begin("content", "Write the script", sub="script", parent=parent)
        current = json.loads(read(CFG / f"{vid}.json") or "null") if redo else None
        cfg = clean_cfg(write_script(topic, vid, facts, notes, current), vid)
        nether.finish(cur, {"beats": len(cfg["segments"]), "words": sum(len(s["text"].split()) for s in cfg["segments"])})

        cur = nether.begin("content", "Packaging", sub="packaging", parent=parent)
        pkg = write_packaging(cfg, facts)
        if not pkg.get("title"):
            raise RuntimeError("Packaging came back without a title.")
        import business, intelligence                    # Business: affiliate + newsletter links in the description
        business.apply_links(pkg, topic, intelligence.lane_of(topic))
        nether.finish(cur, {"title": pkg["title"]})

        cur = nether.begin("content", "Hook & retention check", sub="hooks", parent=parent)
        score, rows = retention.check(cfg)
        nether.finish(cur, {"score": score, "misses": [m for ok, m in rows if not ok]})
        cur = None

        cfg["draft"] = {"at": nether.now(), "topic": topic, "task": parent}
        if notes:
            record["notes"].append({"at": nether.now(), "notes": notes})
        record.update(check={"score": score, "rows": [[ok, m] for ok, m in rows]}, task=parent)
        save(vid, cfg, pkg, record)
        nether.finish(parent, {"id": vid, "title": pkg["title"], "retention": score})
        return vid
    except (Exception, SystemExit) as e:                # never leave a task stuck on "working"
        if cur:
            nether.fail(cur, f"{type(e).__name__}: {e}")
        nether.fail(parent, f"{type(e).__name__}: {e}")
        raise


def is_draft(vid):
    cfg = json.loads(read(CFG / f"{vid}.json") or "{}")
    return bool(cfg.get("draft"))


def approve(vid):
    p = CFG / f"{vid}.json"
    if not (ID_RE.match(vid) and p.exists() and is_draft(vid)):
        raise ValueError("That draft isn't waiting for approval.")
    cfg = json.loads(p.read_text())
    record = json.loads(read(DRAFTS / f"{vid}.json") or "{}")
    record["approved"] = nether.now()
    DRAFTS.joinpath(f"{vid}.json").write_text(json.dumps(record, indent=1, ensure_ascii=False))
    cfg.pop("draft", None)
    p.write_text(json.dumps(cfg, indent=1, ensure_ascii=False) + "\n")
    return {"ok": True, "id": vid}


def discard(vid):
    if not (ID_RE.match(vid) and is_draft(vid)):
        raise ValueError("Only an unapproved draft can be discarded.")
    for p in (CFG / f"{vid}.json", PKG / f"{vid}.json", DRAFTS / f"{vid}.json"):
        p.unlink(missing_ok=True)
    return {"ok": True}


def drafts():
    out = []
    for p in sorted(CFG.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            cfg = json.loads(p.read_text())
        except Exception:
            continue
        if not cfg.get("draft"):
            continue
        vid = p.stem
        pkg = json.loads(read(PKG / f"{vid}.json") or "{}")
        rec = json.loads(read(DRAFTS / f"{vid}.json") or "{}")
        out.append({"id": vid, "topic": cfg["draft"].get("topic"), "at": cfg["draft"].get("at"), "title": pkg.get("title"),
                    "title_options": pkg.get("title_options", []), "hook_options": pkg.get("hook_options", []),
                    "lines": [{"id": s["id"], "text": s["text"], "hero": (s.get("hero") or {}).get("lines"),
                               "visual": s["vis"].get("real", {}).get("query") if s["vis"].get("real") else s["vis"].get("prompt"),
                               "kind": "real photo" if s["vis"].get("real") else "AI art" if s["vis"].get("prompt") else "same picture, new framing"}
                              for s in cfg["segments"]],
                    "end": (cfg.get("end") or {}).get("lines", []), "research": rec.get("research"),
                    "check": rec.get("check"), "notes": rec.get("notes", [])})
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "--redraft":
        print(draft("", notes=" ".join(a[2:]), vid=a[1]))
    else:
        print(draft(" ".join(a)))
