#!/usr/bin/env python3
"""repair.py — Control's repair desk: explain a failed task, then fix it the safest way that works.

diagnose(task)   plain English: which department broke, what happened, what fixes it, and how (retry / wait /
                 settings / login / code). Deterministic — it reads the task's own error, nothing is guessed.
send(tid)        "Send to fix": files the failure with Control. Retryable causes come back as {"retry": true};
                 anything that looks like broken code becomes a fix ticket (out/fixes.json).
start_fix(n)     "Let Claude fix it": Claude works on ticket n in its own git worktree + branch (fix/<n>), never in
                 your checkout, never posting. You then see the change and Apply (merge) or Discard it.
Nothing here changes your code without you tapping Apply.
"""
import datetime, json, re, subprocess, threading
from pathlib import Path

import orchestrator as nether
from store import atomic_write_json, locked

HERE = Path(__file__).resolve().parent
from channel import DATA  # the data folder (this folder unless NETHER_DATA is set)
import channel
OUT = DATA / "out"
FIXES = OUT / "fixes.json"
WT = OUT / "fix_worktrees"
LOCK = threading.Lock()
STUCK_MINUTES = 45

# (pattern, kind, what happened, what fixes it). First match wins; order = most specific first.
RULES = [
    (r"weekly limit|usage limit|hit your (?:\w+ )?limit|resets? (?:\w+ \d+ )?at", "wait",
     "The Claude subscription hit its usage limit.",
     "Wait for the reset{reset}, or open AI engines and let another engine (API key or free local model) take this job."),
    (r"not logged in|/login|Invalid API key|authentication|401", "login",
     "The AI engine isn't signed in.", "Open Terminal, run `claude`, type /login — then Retry."),
    (r"429|Too Many Requests|rate.?limit", "retry", "A website asked us to slow down.", "Retry in a few minutes."),
    (r"ConnectionError|Max retries|Name or service not known|timed out|Temporary failure|URLError", "retry",
     "Couldn't reach the internet (or the service was down).", "Check the connection, then Retry."),
    (r"took longer than|TimeoutExpired", "retry", "The job ran out of time.", "Retry — if it keeps timing out, send it to fix."),
    (r"BUFFER_API_KEY|R2_|NoCredentialsError|InvalidAccessKeyId|YOUTUBE_API_KEY|CLOUDFLARE_|missing from \.env|isn't set up", "settings",
     "A connection or key is missing.", "Open Settings, fix the red connection, then Retry."),
    (r"Buffer rejected|MutationError", "settings", "Buffer refused the post.", "Open Buffer to see why, then Retry."),
    (r"No space left|ENOSPC", "settings", "The Mac is out of disk space.", "Free some space, then Retry."),
    (r"does not exist|No such file", "retry", "A file this job needs is missing — the video may have been archived or not made yet.",
     "Re-make the video, or clear this task if you archived it."),
    (r"missing out/|run \./build\.sh|missing from assets/", "retry",
     "A file this job needs hasn't been made yet.", "Make the video first (or Retry — it re-fetches what's missing)."),
    (r"Traceback|Error:|Exception|SyntaxError|TypeError|KeyError|AttributeError|NameError|IndexError|ValueError|exit code", "code",
     f"Something in {channel.get('app_name')}'s own code broke.", "Send it to fix — Control files a ticket and Claude can repair it on a separate branch for you to approve."),
]
RESET = re.compile(r"resets? ((?:\w+ \d+ )?(?:at )?\d[\w:]*(?: ?[ap]m)?(?: \([^)]*\))?)", re.I)


def _now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _failed_step(t):
    return next((s for s in reversed(t.get("steps") or []) if s["status"] == "failed"), None)


def diagnose(t):
    step = _failed_step(t)
    err = "\n".join(x for x in ((step or {}).get("error"), t.get("error")) if x) or ""
    agent = nether.AGENTS.get(t["agent"], {})
    sub = agent.get("subs", {}).get((step or t).get("sub") or t.get("sub") or "", ("",))[0]
    for pat, kind, what, fix in RULES:
        if re.search(pat, err, re.I):
            m = RESET.search(err)
            fix = fix.format(reset=f" — it resets {m[1]}" if m else "")
            break
    else:
        kind, what, fix = ("retry", "The job stopped without saying why.", "Retry — if it happens again, send it to fix.") if not err.strip() \
            else ("code", "Something unexpected went wrong.", "Send it to fix so Control can look at the full log.")
    last = [l for l in err.strip().splitlines() if l.strip()]
    return {"task": t["id"], "title": t["title"], "department": agent.get("name", t["agent"]), "desk": sub or None,
            "where": (step or {}).get("title"), "kind": kind, "what": what, "fix": fix,
            "error": last[-1][:300] if last else "", "log": err[-4000:], "can_retry": bool(t.get("retry")), "retry": t.get("retry"), "when": t.get("finished") or t.get("created")}


def _load():
    try:
        d = json.loads(FIXES.read_text())
    except Exception:
        d = {"next": 1, "tickets": []}
    changed = False
    now = datetime.datetime.now().astimezone()
    for x in d.get("tickets", []):
        if x.get("state") == "working":
            started = _parse_ts(x.get("started_working") or x.get("filed"))
            if started and (now - started).total_seconds() > STUCK_MINUTES * 60:
                x["state"] = "open"
                x["summary"] = (x.get("summary") or "") + f" (Nethermind marked this stuck after {STUCK_MINUTES}+ min and reopened it.)"
                changed = True
    if changed:
        _save(d)
    return d


def _parse_ts(s):
    try:
        return datetime.datetime.fromisoformat(s)
    except Exception:
        return None


def _save(d):
    atomic_write_json(FIXES, d, indent=1)


def tickets():
    return [t for t in _load()["tickets"] if t["state"] != "cleared"]


def send(tid):
    t = nether.task(int(tid))
    if not t:
        raise ValueError("That task isn't in the log any more.")
    d = diagnose(t)
    rid = nether.begin("control", f"Fix: {t['title']}", sub="repair", input={"task": t["id"], "kind": d["kind"]})
    if d["kind"] != "code":
        nether.finish(rid, {"kind": d["kind"], "advice": d["fix"]})
        return {**d, "retry": d["kind"] == "retry" and d["can_retry"], "reply": d["fix"]}
    with LOCK:
        s = _load()
        dup = next((x for x in s["tickets"] if x["task"] == t["id"] and x["state"] != "cleared"), None)
        if dup:
            nether.finish(rid, {"ticket": dup["n"]})
            return {**d, "ticket": dup["n"], "reply": f"Already filed as fix ticket #{dup['n']}."}
        n = s["next"]; s["next"] += 1
        s["tickets"].insert(0, {"n": n, "task": t["id"], "title": t["title"], "department": d["department"], "where": d["where"],
                                "error": d["error"], "log": d["log"], "retry": t.get("retry"), "state": "open", "filed": _now(),
                                "branch": None, "summary": None, "diff": None, "repair_task": rid})
        _save(s)
    nether.finish(rid, {"ticket": n})
    return {**d, "ticket": n, "reply": f"Filed fix ticket #{n} with Control. Open it to let Claude repair it on its own branch."}


def _update(n, **kw):
    with LOCK:
        s = _load()
        for x in s["tickets"]:
            if x["n"] == n:
                x.update(kw)
        _save(s)


def _get(n):
    x = next((x for x in _load()["tickets"] if x["n"] == n), None)
    if not x:
        raise ValueError("No such fix ticket.")
    return x


def _git(*a, cwd=HERE):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)


PROMPT = """You are Control, the repair agent of Nethermind Studio (a local Python stdlib + vanilla JS app for a YouTube Shorts
channel). A task failed. Find the root cause in THIS repository and fix it with the smallest correct change.

Task: {title}  (department: {department}{where})
Error log (last lines):
{log}

Rules: read README.md first. Only edit code/config in this repository. Never read or print .env. Never post, queue,
upload or call Buffer/YouTube write APIs. Don't touch out/ data. Match the surrounding style; keep files under 500 lines.
If you can verify the fix with a quick local command (python -c import, running the failing script with a harmless
flag, selftest.py), do it. If the cause is outside the code (keys, logins, internet, limits), change nothing.
Finish with ONLY this JSON: {{"fixed": true|false, "summary": "one or two plain sentences for a non-programmer", "files": ["..."]}}"""


def _fix_worker(n):
    x = _get(n)
    branch, wt = f"fix/{n}", WT / f"fix-{n}"
    rid = nether.begin("control", f"Repairing: {x['title']}", sub="repair", input={"ticket": n})
    try:
        WT.mkdir(parents=True, exist_ok=True)
        if not wt.exists():
            r = _git("worktree", "add", "-B", branch, str(wt), "HEAD")
            if r.returncode:
                raise RuntimeError(r.stderr.strip() or "couldn't create the repair branch")
        venv = HERE / ".venv"
        if venv.exists() and not (wt / ".venv").exists():
            (wt / ".venv").symlink_to(venv)
        where = f", step: {x['where']}" if x.get("where") else ""
        prompt = PROMPT.format(title=x["title"], department=x["department"], where=where, log=x["log"][-3000:])
        env_tools = ["Read", "Edit", "Write", "Grep", "Glob",
                     "Bash(.venv/bin/python selftest.py)", "Bash(.venv/bin/python -m py_compile:*)", "Bash(git diff:*)"]
        res = _claude_in(wt, prompt, env_tools)
        _git("add", "-A", ".", ":!.venv", cwd=wt)
        diff = _git("diff", "--cached", "--stat", cwd=wt).stdout.strip()
        if not diff:
            _update(n, state="nofix", summary=res.get("summary") or "Claude looked but found nothing in the code to change.", branch=branch)
            nether.finish(rid, {"ticket": n, "changed": False})
            return
        ok, msg = _compile_check(wt)
        if not ok:
            _git("reset", "--hard", "HEAD", cwd=wt)
            _update(n, state="open", summary=f"Repair didn't finish: the fix doesn't compile ({msg}).")
            nether.finish(rid, {"ticket": n, "changed": False})
            return
        _git("commit", "-m", f"Fix ticket #{n}: {x['title']}\n\n{res.get('summary', '')}", cwd=wt)
        full = _git("show", "--stat", "--patch", "HEAD", cwd=wt).stdout
        _update(n, state="ready", summary=res.get("summary", ""), branch=branch, diff=full[:20000], files=res.get("files", []))
        nether.finish(rid, {"ticket": n, "changed": True})
    except Exception as e:
        _update(n, state="open", summary=f"Repair didn't finish: {e}")
        nether.fail(rid, str(e))


_SECRET_SUFFIXES = ("_KEY", "_TOKEN", "_SECRET")
_SECRET_PREFIXES = ("R2_", "BUFFER_", "CLOUDFLARE_", "YOUTUBE_")


def _strip_secrets(env):
    return {k: v for k, v in env.items()
            if not k.startswith(_SECRET_PREFIXES) and not k.endswith(_SECRET_SUFFIXES)
            and k not in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY")}


def _compile_check(wt):
    """py_compile every changed .py file in the worktree; refuse the fix if any fails."""
    changed = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR", cwd=wt).stdout.split()
    py_files = [f for f in changed if f.endswith(".py")]
    if not py_files:
        return True, ""
    r = subprocess.run([str(wt / ".venv" / "bin" / "python"), "-m", "py_compile", *py_files],
                        cwd=wt, capture_output=True, text=True, timeout=120)
    if r.returncode:
        return False, (r.stderr or r.stdout).strip()[-500:]
    return True, ""


def _claude_in(cwd, prompt, tools):
    import os, shutil
    e = _strip_secrets(os.environ)
    e["PATH"] = f"{Path.home()}/.local/bin:/opt/homebrew/bin:" + e.get("PATH", "/usr/bin:/bin")
    if not shutil.which("claude", path=e["PATH"]):
        raise RuntimeError("the claude command isn't installed on this Mac")
    r = subprocess.run(["claude", "-p", prompt, "--output-format", "json", "--permission-prompts", "none",
                        "--allowedTools", ",".join(tools),
                        "--disallowedTools", "WebFetch,WebSearch",
                        "--strict-mcp-config", "--setting-sources", "project"],
                       cwd=cwd, env=e, capture_output=True, text=True, timeout=1800)
    try:
        res = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise RuntimeError("Claude didn't answer — is it logged in? " + (r.stderr or "")[-300:])
    if res.get("is_error"):
        raise RuntimeError(str(res.get("result"))[:300])
    m = re.search(r"\{[\s\S]*\}", res.get("result", ""))
    try:
        return json.loads(m[0]) if m else {}
    except json.JSONDecodeError:
        return {"summary": res.get("result", "")[:400]}


def start_fix(n):
    x = _get(int(n))
    if x["state"] == "working":
        raise ValueError("Claude is already working on this one.")
    _update(x["n"], state="working", summary="Claude is looking at it on its own branch…", started_working=_now())
    threading.Thread(target=_fix_worker, args=(x["n"],), daemon=True).start()
    return {"ok": True, "reply": f"Claude is repairing ticket #{x['n']} on a separate branch. Nothing changes until you Apply."}


def _drop_worktree(n):
    wt = WT / f"fix-{n}"
    if wt.exists():
        _git("worktree", "remove", "--force", str(wt))


def apply(n):
    x = _get(int(n))
    if x["state"] != "ready":
        raise ValueError("There's no finished repair to apply yet.")
    if _git("status", "--porcelain", "--untracked-files=no").stdout.strip():
        raise ValueError("Your code has unsaved changes — commit them first, then Apply.")
    wt = WT / f"fix-{x['n']}"
    if wt.exists():
        py_files = [f for f in _git("show", "--name-only", "--diff-filter=ACMR", "--pretty=format:", x["branch"], cwd=wt).stdout.split() if f.endswith(".py")]
        if py_files:
            r = subprocess.run([str(HERE / ".venv" / "bin" / "python"), "-m", "py_compile", *py_files],
                                cwd=wt, capture_output=True, text=True, timeout=120)
            if r.returncode:
                raise ValueError(f"The fix doesn't compile ({(r.stderr or r.stdout).strip()[-300:]}) — Discard it and let Claude try again.")
    _drop_worktree(x["n"])
    r = _git("merge", "--no-edit", x["branch"])
    if r.returncode:
        _git("merge", "--abort")
        raise ValueError("The fix clashes with newer changes. Discard it and let Claude try again.")
    _git("branch", "-d", x["branch"])
    _update(x["n"], state="applied", applied=_now())
    return {"ok": True, "retry": x.get("retry"), "reply": f"Fix #{x['n']} applied. Restart {channel.get('app_name')} to load it, then Retry the task."}


def discard(n):
    x = _get(int(n))
    _drop_worktree(x["n"])
    if x.get("branch"):
        _git("branch", "-D", x["branch"])
    _update(x["n"], state="cleared", cleared=_now())
    return {"ok": True, "reply": "Cleared."}
