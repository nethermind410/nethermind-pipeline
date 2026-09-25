#!/usr/bin/env python3
"""claude_task.py — small Claude-powered jobs the app can run on demand.

    python3 claude_task.py replies <youtube_comment_thread_id>   draft 2 replies (you copy one; nothing is posted)
    python3 claude_task.py score <video_id>                       vidIQ-score the title options (5 credits each)

Runs the `claude` CLI headless with ONLY the tools each job needs (no shell, no file writes);
this script writes the results. Uses the user's claude.ai login (app env vars removed).
"""
import datetime, json, os, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
VIDIQ = "mcp__claude_ai_vidIQ_for_Claude__"


def ask(prompt, tools):
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY")}
    env["PATH"] = f"{Path.home()}/.local/bin:" + env.get("PATH", "/usr/bin:/bin")
    r = subprocess.run(["claude", "-p", prompt, "--output-format", "json", "--permission-prompts", "none",
                        "--allowedTools", ",".join(["ToolSearch", *tools])], capture_output=True, text=True, timeout=300, env=env)
    try:
        res = json.loads(r.stdout)
    except json.JSONDecodeError:
        sys.exit("Claude didn't answer. Is it logged in? Run `claude` in Terminal and type /login.")
    if res.get("is_error"):
        sys.exit(f"Claude: {res.get('result')}")
    m = re.search(r"\{.*\}|\[.*\]", res.get("result", ""), re.S)
    if not m:
        sys.exit("Claude's answer wasn't in the expected format; try again.")
    return json.loads(m[0])


def replies(thread_id):
    yt = json.loads((OUT / "youtube.json").read_text())
    c = next((x for x in yt.get("comments", []) if x["id"] == thread_id), None) or sys.exit("Comment not found; refresh first.")
    pkg = next((json.loads(p.read_text()) for p in (HERE / "packaging").glob("*.json")
                if json.loads(p.read_text()).get("title", "")[:40].lower() == c["video_title"][:40].lower()), {})
    import llm
    out = llm.ask("replies", f"""You write replies for Nethermind, a faceless YouTube Shorts channel about Marvel history, space and weird animals.
Voice: direct, warm, short, a little playful; never corporate; no hashtags; no emoji spam (max one).
Video: "{c['video_title']}". What the video covers: {pkg.get('youtube_description', '')[:600]}
Comment by {c['author']}: "{c['text']}"
Write 2 different replies (each under 220 characters). Only state facts that are in the video description above;
if the comment asks something you can't verify from it, say you'll look into it. Reply with ONLY JSON:
{{"replies": ["...", "..."]}}""", check=llm.check_replies)
    drafts = json.loads((OUT / "comment_drafts.json").read_text()) if (OUT / "comment_drafts.json").exists() else {}
    drafts[thread_id] = out["replies"][:2]
    (OUT / "comment_drafts.json").write_text(json.dumps(drafts, indent=1))
    print("Drafted:", *drafts[thread_id], sep="\n- ")


def score(vid):
    p = HERE / "packaging" / f"{vid}.json"
    pkg = json.loads(p.read_text())
    titles = [o["title"] if isinstance(o, dict) else o for o in pkg.get("title_options", [])] or [pkg["title"]]
    bal = ask(f"Call {VIDIQ}vidiq_balance and reply with ONLY JSON: " + '{"credits": <totalCredits>, "resets": "<renewableResetsAt>"}',
              [VIDIQ + "vidiq_balance"])
    bal["at"] = datetime.datetime.now().isoformat(timespec="minutes")
    (OUT / "vidiq_balance.json").write_text(json.dumps(bal))
    if bal.get("credits", 0) < 5 * len(titles):
        sys.exit(f"vidIQ has {bal.get('credits')} credits; scoring {len(titles)} titles needs {5 * len(titles)}. "
                 f"Credits refill {str(bal.get('resets', ''))[:10]}.")
    res = ask("Score each of these YouTube Shorts titles with vidiq_score_title (type 'short', channelId "
              f"'UCpE0Ce-qXmVWCwwqiW5bvxw'). Titles: {json.dumps(titles)}. Reply with ONLY JSON: "
              '{"scores": [{"title": "...", "score": <0-100>, "note": "<one short reason vidIQ gave>"}]} — use the exact numbers vidIQ returned.',
              [VIDIQ + "vidiq_score_title"])
    stamp = datetime.datetime.now().isoformat(timespec="minutes")
    by = {s["title"]: s for s in res.get("scores", [])}
    pkg["title_options"] = [{"title": t, **({"score": by[t]["score"], "note": by[t].get("note", ""), "scored": stamp, "source": "vidIQ"}
                                           if t in by else {})} for t in titles]
    p.write_text(json.dumps(pkg, indent=1, ensure_ascii=False) + "\n")
    print("Scored:", *(f"{s['score']}  {s['title']}" for s in res.get("scores", [])), sep="\n")


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("replies", "score"):
        sys.exit(__doc__)
    {"replies": replies, "score": score}[sys.argv[1]](sys.argv[2])
