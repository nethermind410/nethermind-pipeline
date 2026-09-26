#!/usr/bin/env python3
"""llm.py — every piece of writing goes through here, on whichever engine you choose for that job.

    python3 llm.py status        which engine does each job, and what's connected
    python3 llm.py usage         the last 7 days: calls, failures and cost per engine
    python3 llm.py test <engine> a one-line test call

Jobs:     research (needs web search) · script · episode (long-form script) · packaging · replies
Engines:  claude     your Claude subscription through the `claude` command (what the system always used)
          anthropic  an Anthropic API key (ANTHROPIC_API_KEY in .env) — pay per use, has web search
          openai     any OpenAI-compatible service: OpenAI, OpenRouter, Gemini — a base URL, a model, a key
          local      a model running on this Mac through Ollama — free, no web search

Each job has a chain, e.g. packaging: local → claude. The first engine that's connected answers; its answer
must pass the job's checks (valid JSON, the fields the rest of the pipeline needs, sources, the channel hashtag…).
If it errors, refuses, hits a limit or fails a check, the next engine in the chain takes over — so a cheap
engine can cost a retry, never a broken video. Jobs that need the web only go to engines that can search.
Every call is logged to out/llm_usage.jsonl (engine, tokens, estimated cost, whether it fell back).

Settings live in out/llm.json (Studio → Control → AI engines). Keys live only in .env, never in settings.
The default is Claude-only for every job, so nothing changes until you choose otherwise.
"""
import datetime, json, os, re, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
from channel import DATA  # the data folder (this folder unless NETHER_DATA is set)
import channel
from store import atomic_write_json, atomic_write_text, locked
OUT = DATA / "out"
SETTINGS, USAGE = OUT / "llm.json", OUT / "llm_usage.jsonl"

JOBS = {  # job: (what it is, needs web search)
    "research": ("Research & fact-check (Shorts and long-form)", True),
    "script": ("Short scripts", False),
    "episode": ("Long-form scripts", False),
    "packaging": ("Titles, descriptions, tags, captions", False),
    "replies": ("Comment reply drafts", False),
}
ENGINES = {
    "claude": {"name": "Claude subscription", "short": "Claude (subscription)", "web": True},
    "anthropic": {"name": "Anthropic API key", "short": "Claude (API key)", "web": True},
    "openai": {"name": "OpenAI-compatible (OpenAI / OpenRouter / Gemini)", "short": "OpenAI-compatible", "web": False},
    "local": {"name": "Local model (Ollama)", "short": "Local model (free)", "web": False},
}
DEFAULTS = {
    "routes": {j: ["claude"] for j in JOBS},
    "engines": {
        "anthropic": {"model": "claude-opus-5"},
        "openai": {"base_url": "https://api.openai.com/v1", "model": "", "key_env": "OPENAI_API_KEY"},
        "local": {"base_url": "http://localhost:11434/v1", "model": ""},
    },
}
PRESETS = {
    "claude": ("Claude only", "Every job on your Claude subscription — how the system has always run.",
               {j: ["claude"] for j in JOBS}),
    "never_stop": ("Never stop", "Claude subscription first; when its limit is hit, the API key carries on so drafting never pauses.",
                   {j: ["claude", "anthropic"] for j in JOBS}),
    "lean": ("Lean", "Claude researches and writes the scripts (accuracy is the channel); a cheaper engine does packaging "
                     "and replies, with Claude as the safety net.",
             {"research": ["claude", "anthropic"], "script": ["claude", "anthropic"], "episode": ["claude", "anthropic"],
              "packaging": ["local", "openai", "anthropic", "claude"], "replies": ["local", "openai", "anthropic", "claude"]}),
}
# Anthropic API prices, $ per million tokens (input, output) — for the cost estimate in the usage log
PRICES = {"claude-opus-5-5": (4, 20), "claude-opus-5": (5, 25), "claude-opus-4-8": (5, 25), "claude-sonnet-5": (2, 10),
          "claude-sonnet-4-6": (3, 15), "claude-haiku-4-5": (1, 5), "claude-fable-5-1": (10, 50)}
SEARCH_PRICE = 0.01   # per web search (estimate — check Anthropic's pricing page)


class EngineError(RuntimeError):
    pass


class NotSetUp(EngineError):
    """The engine isn't connected (no key, no model, not installed) — skipped quietly, not counted as a failure."""


# ------------------------------------------------------------------ settings
def settings():
    s = json.loads(json.dumps(DEFAULTS))
    try:
        saved = json.loads(SETTINGS.read_text())
        s["routes"].update({k: v for k, v in saved.get("routes", {}).items() if k in JOBS})
        for k, v in saved.get("engines", {}).items():
            if k in s["engines"]:
                s["engines"][k].update(v)
    except Exception:
        pass
    return s


# which key_env names each engine may point at (never arbitrary — this ends up read by env() and sent as a bearer token)
ALLOWED_KEY_ENV = {"openai": {"OPENAI_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY"}, "local": set()}


def _valid_base_url(engine, url):
    from urllib.parse import urlparse
    u = urlparse(url)
    if u.scheme == "https" and u.netloc:
        return True
    if engine == "local" and u.scheme == "http" and u.hostname in ("localhost", "127.0.0.1", "::1"):
        return True
    return False


def save(new):
    s = settings()
    for job, chain in (new.get("routes") or {}).items():
        if job in JOBS:
            chain = [e for e in chain if e in ENGINES]
            if JOBS[job][1]:                          # web jobs: only engines that can search
                chain = [e for e in chain if ENGINES[e]["web"]]
            s["routes"][job] = chain or ["claude"]
    for k, v in (new.get("engines") or {}).items():
        if k in s["engines"]:
            clean = {kk: str(vv).strip() for kk, vv in v.items() if kk in ("model", "base_url", "key_env")}
            if "key_env" in clean and clean["key_env"] not in ALLOWED_KEY_ENV.get(k, set()):
                clean.pop("key_env")
            if "base_url" in clean and not _valid_base_url(k, clean["base_url"]):
                clean.pop("base_url")
            s["engines"][k].update(clean)
    OUT.mkdir(exist_ok=True)
    with locked(SETTINGS):
        atomic_write_json(SETTINGS, s)
    return s


def env():
    """.env values (without printing them anywhere)."""
    vals = dict(os.environ)
    p = channel.ENV_FILE
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                vals.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return vals


KEY_RE = r"[A-Za-z0-9_\-\.]{10,300}"
ENV_NAMES = {  # every .env name the app may write, and what a valid value looks like (setup wizard + AI engines)
    **{k: KEY_RE for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY", "YOUTUBE_API_KEY",
                           "BUFFER_API_KEY", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "CLOUDFLARE_API_TOKEN")},
    "CLOUDFLARE_ACCOUNT_ID": r"[a-f0-9]{32}", "R2_BUCKET": r"[a-z0-9][a-z0-9.\-]{1,62}",
    "R2_ENDPOINT": r"https://[A-Za-z0-9.\-]+(:\d+)?/?", "R2_PUBLIC_BASE_URL": r"https://[A-Za-z0-9.\-]+(:\d+)?(/[A-Za-z0-9._~\-/]*)?",
}


def set_key(name, value, allowed=("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY")):
    """Store an API key in .env (replacing an old value). Only known names are accepted; the value is never echoed."""
    if name not in allowed or name not in ENV_NAMES:
        raise ValueError("Unknown key name.")
    value = value.strip()
    if not re.fullmatch(ENV_NAMES[name], value):
        raise ValueError("That doesn't look like an API key." if ENV_NAMES[name] == KEY_RE else f"That doesn't look like a valid {name}.")
    p = channel.ENV_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    with locked(p):
        lines = [l for l in (p.read_text().splitlines() if p.exists() else []) if not l.strip().startswith(name + "=")]
        lines.append(f"{name}={value}")
        atomic_write_text(p, "\n".join(lines) + "\n")   # temp file is 0600 by default; never readable by others
    os.chmod(p, 0o600)
    return {"ok": True, "reply": f"Saved {name} to .env."}


# ------------------------------------------------------------------ engines
def _json(text, who):
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text or "", re.S) or re.search(r"(\{.*\})", text or "", re.S)
    if not m:
        raise EngineError(f"{who}'s answer wasn't JSON.")
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise EngineError(f"{who}'s JSON didn't parse ({e.msg}).")


# On the Claude subscription, lighter jobs run on lighter models so the plan's limit lasts; the script keeps the default.
CLAUDE_MODEL = {"research": "sonnet", "packaging": "sonnet", "titles": "sonnet", "replies": "haiku"}


def _claude(prompt, tools, timeout, cfg, job=None):
    import shutil
    e = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY")}
    e["PATH"] = f"{Path.home()}/.local/bin:" + e.get("PATH", "/usr/bin:/bin")     # the subscription, never the API key
    if not shutil.which("claude", path=e["PATH"]):
        raise NotSetUp("The claude command isn't installed on this Mac.")
    try:
        m = cfg.get("model") or CLAUDE_MODEL.get(job)
        r = subprocess.run(["claude", "-p", prompt, "--output-format", "json", "--permission-prompts", "none",
                            "--allowedTools", ",".join(["ToolSearch", *tools]), *(["--model", m] if m else [])],
                           capture_output=True, text=True, timeout=timeout, env=e, cwd=HERE)
    except subprocess.TimeoutExpired:
        raise EngineError(f"Claude took longer than {timeout // 60} minutes.")
    try:
        res = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise EngineError("Claude didn't answer. Is it logged in? Run `claude` in Terminal and type /login. " + (r.stderr or "")[-300:])
    if res.get("is_error"):
        raise EngineError(f"Claude: {res.get('result')}")
    return _json(res.get("result", ""), "Claude"), {"model": "subscription", "cost": 0.0}


def _anthropic(prompt, tools, timeout, cfg):
    key = env().get("ANTHROPIC_API_KEY")
    if not key:
        raise NotSetUp("No ANTHROPIC_API_KEY in .env.")
    try:
        import anthropic
    except ImportError:
        raise NotSetUp("The anthropic package isn't installed: pip install anthropic")
    model = cfg.get("model") or "claude-opus-5"
    client = anthropic.Anthropic(api_key=key).with_options(timeout=float(timeout), max_retries=2)
    new_tools = model.startswith(("claude-opus-5", "claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6", "claude-sonnet-5",
                                  "claude-sonnet-4-6", "claude-fable"))
    api_tools = []
    if "WebSearch" in tools:
        api_tools.append({"type": "web_search_20260209" if new_tools else "web_search_20250305", "name": "web_search", "max_uses": 10})
    if "WebFetch" in tools:
        api_tools.append({"type": "web_fetch_20260209" if new_tools else "web_fetch_20250910", "name": "web_fetch", "max_uses": 10})
    messages = [{"role": "user", "content": prompt}]
    ins = outs = searches = 0
    for _ in range(6):                                       # server tools can pause a long turn; resume it
        kw = {"model": model, "max_tokens": 16000, "messages": messages}
        if api_tools:
            kw["tools"] = api_tools
        try:
            if model.startswith(("claude-opus-5", "claude-fable-5")) and not model.startswith("claude-opus-5-5"):
                # on a policy decline, the API re-runs the request on Opus 4.8 inside the same call
                r = client.beta.messages.create(betas=["server-side-fallback-2026-06-01"], fallbacks=[{"model": "claude-opus-4-8"}], **kw)
            else:
                r = client.messages.create(**kw)
        except anthropic.AuthenticationError:
            raise EngineError("The Anthropic API key was rejected — check ANTHROPIC_API_KEY.")
        except anthropic.RateLimitError:
            raise EngineError("Anthropic rate limit — try again shortly.")
        except anthropic.APIStatusError as e:
            raise EngineError(f"Anthropic API error {e.status_code}: {str(e.message)[:200]}")
        except anthropic.APIConnectionError:
            raise EngineError("Couldn't reach the Anthropic API.")
        u = r.usage
        ins += (u.input_tokens or 0) + (getattr(u, "cache_read_input_tokens", 0) or 0) + (getattr(u, "cache_creation_input_tokens", 0) or 0)
        outs += u.output_tokens or 0
        stu = getattr(u, "server_tool_use", None)
        searches += (getattr(stu, "web_search_requests", 0) or 0) if stu else 0
        if r.stop_reason == "refusal":
            raise EngineError("The API declined this request.")
        if r.stop_reason == "pause_turn":
            messages = messages + [{"role": "assistant", "content": r.content}]
            continue
        break
    texts = [b.text for b in r.content if b.type == "text"]
    pi, po = PRICES.get(model, PRICES["claude-opus-5"])
    cost = ins / 1e6 * pi + outs / 1e6 * po + searches * SEARCH_PRICE
    parsed = None
    for t in reversed(texts):                                # with web search the answer comes last, after notes
        try:
            parsed = _json(t, "The API"); break
        except EngineError:
            continue
    return parsed if parsed is not None else _json("".join(texts), "The API"), {"model": model, "in": ins, "out": outs, "searches": searches, "cost": round(cost, 4)}


def _openai_compatible(prompt, tools, timeout, cfg, local=False):
    import requests
    model, base = cfg.get("model"), (cfg.get("base_url") or "").rstrip("/")
    if not model or not base:
        raise NotSetUp("No model set for this engine (Control → AI engines).")
    headers = {"Content-Type": "application/json"}
    if not local:
        key = env().get(cfg.get("key_env") or "OPENAI_API_KEY")
        if not key:
            raise NotSetUp(f"No {cfg.get('key_env') or 'OPENAI_API_KEY'} in .env.")
        headers["Authorization"] = f"Bearer {key}"
    body = {"model": model, "messages": [{"role": "system", "content": "Reply with only the JSON requested — no commentary."},
                                         {"role": "user", "content": prompt}]}
    try:
        r = requests.post(f"{base}/chat/completions", json=body, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        raise EngineError(("Ollama isn't running on this Mac" if local else "Couldn't reach the service") + f" ({type(e).__name__}).")
    if r.status_code != 200:
        raise EngineError(f"{'Local model' if local else 'Service'} error {r.status_code}: {r.text[:200]}")
    j = r.json()
    text = ((j.get("choices") or [{}])[0].get("message") or {}).get("content", "")
    u = j.get("usage") or {}
    return _json(text, "The local model" if local else "The service"), {"model": model, "in": u.get("prompt_tokens"), "out": u.get("completion_tokens"),
                                                                         "cost": 0.0 if local else None}


def call(engine, prompt, tools=(), timeout=900, job=None):
    cfg = settings()["engines"].get(engine, {})
    if engine == "claude":
        return _claude(prompt, tools, timeout, cfg, job)
    if engine == "anthropic":
        return _anthropic(prompt, tools, timeout, cfg)
    if engine == "openai":
        return _openai_compatible(prompt, tools, timeout, cfg)
    if engine == "local":
        return _openai_compatible(prompt, tools, timeout, cfg, local=True)
    raise EngineError(f"Unknown engine {engine}.")


# ------------------------------------------------------------------ the one entry point
def _log(row):
    OUT.mkdir(exist_ok=True)
    with USAGE.open("a") as f:
        f.write(json.dumps(row) + "\n")


def ask(job, prompt, tools=(), timeout=900, check=None):
    """Run a writing job on its chain of engines. `check(result)` raises ValueError when an answer isn't good
    enough; the next engine then takes over. Returns the parsed JSON answer."""
    chain = settings()["routes"].get(job, ["claude"])
    if tools:
        chain = [e for e in chain if ENGINES[e]["web"]] or ["claude"]
    errors = []
    for i, engine in enumerate(chain):
        t0 = time.time()
        row = {"at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "job": job, "engine": engine, "fallback": i > 0}
        try:
            result, meta = call(engine, prompt, tools, timeout, job)
        except NotSetUp as e:
            errors.append(f"{ENGINES[engine]['name']}: {e}")
            continue
        except (EngineError, ValueError, KeyError, TypeError) as e:
            msg = str(e) or type(e).__name__
            errors.append(f"{ENGINES[engine]['name']}: {msg}")
            _log({**row, "ok": False, "error": msg[:300], "secs": round(time.time() - t0, 1)})
            continue
        try:
            if check:
                check(result)
            _log({**row, **meta, "ok": True, "secs": round(time.time() - t0, 1)})
            return result
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            msg = str(e) or type(e).__name__
            if i == len(chain) - 1:        # the last engine: keep its answer — the pipeline's own checks still judge it,
                _log({**row, **meta, "ok": True, "warning": msg[:200], "secs": round(time.time() - t0, 1)})   # exactly as before
                return result
            errors.append(f"{ENGINES[engine]['name']}: answer failed the check ({msg})")
            _log({**row, **meta, "ok": False, "error": f"failed the check: {msg}"[:300], "secs": round(time.time() - t0, 1)})
    if len(errors) == 1:
        raise RuntimeError(errors[0].split(": ", 1)[1])
    raise RuntimeError("Every engine failed — " + " | ".join(errors))


# ------------------------------------------------------------------ checks: what each job's answer must contain
def _need(cond, why):
    if not cond:
        raise ValueError(why)


def check_research(r):
    facts = r.get("facts") or []
    _need(len(facts) >= 3, "fewer than 3 facts")
    _need(sum(1 for f in facts if str(f.get("source_url", "")).startswith("http")) >= 3, "facts without source links")
    _need(r.get("angle") and r.get("true_version"), "no angle / true version")


def check_script(r):
    segs = r.get("segments") or []
    _need(len(segs) >= 4, "fewer than 4 beats")
    _need(all(isinstance(s, dict) and s.get("text") and isinstance(s.get("vis"), dict) for s in segs), "a beat without text or a visual")


def check_episode(r):
    chs = r.get("chapters") or []
    _need(len(chs) >= 3, "fewer than 3 chapters")
    _need(all(c.get("segments") for c in chs), "a chapter without lines")


def check_packaging(r):
    """Only what the pipeline needs; small slips are repaired rather than rejected (so good answers aren't wasted)."""
    _need(isinstance(r.get("title"), str) and 10 <= len(r["title"].strip()) <= 120, "no usable title")
    d = str(r.get("youtube_description", "")).strip()
    _need(len(d) >= 80, "description is too short")
    t = channel.tag()                                          # the channel's own hashtag, if it has one
    if t and f"#{t}" not in d.lower():
        r["youtube_description"] = d + ("\n\n" if "#" not in d[-80:] else " ") + f"#{t}"
    tags = r.get("youtube_tags")
    tags = ", ".join(tags) if isinstance(tags, list) else str(tags or "")
    _need(len([x for x in tags.split(",") if x.strip()]) >= 3, "fewer than 3 tags")
    if t and t not in tags.lower():
        tags = tags.rstrip(", ") + f", {t}"
    r["youtube_tags"] = tags
    _need(str(r.get("pinned_comment", "")).strip(), "no pinned comment")


def check_packaging_short(r):
    check_packaging(r)
    _need(str(r.get("tiktok_caption", "")).strip() and str(r.get("instagram_caption", "")).strip(), "missing TikTok/Instagram captions")


def check_packaging_long(r):
    check_packaging(r)
    if "{CHAPTERS}" not in r["youtube_description"]:           # the chapter list slots in after the hook paragraphs
        parts = r["youtube_description"].split("\n\n", 2)
        r["youtube_description"] = "\n\n".join(parts[:2] + ["{CHAPTERS}"] + parts[2:])


def check_replies(r):
    rs = r.get("replies") or []
    _need(rs and all(isinstance(x, str) and 0 < len(x) <= 300 for x in rs), "no usable replies")


# ------------------------------------------------------------------ status + usage (for Studio)
def available(engine):
    s, e = settings()["engines"].get(engine, {}), env()
    if engine == "claude":
        import shutil
        ok = bool(shutil.which("claude") or (Path.home() / ".local/bin/claude").exists())
        return ok, "the claude command is installed" if ok else "install Claude Code (the claude command)"
    if engine == "anthropic":
        return bool(e.get("ANTHROPIC_API_KEY")), f"model {s.get('model')}" if e.get("ANTHROPIC_API_KEY") else "add an Anthropic API key"
    if engine == "openai":
        ok = bool(e.get(s.get("key_env") or "OPENAI_API_KEY") and s.get("model"))
        return ok, f"{s.get('model')} at {s.get('base_url')}" if ok else "add a key and a model name"
    if engine == "local":
        if not s.get("model"):
            return False, "install Ollama and set a model name"
        try:
            import requests
            requests.get((s.get("base_url") or "").replace("/v1", "") + "/api/tags", timeout=1.5)
            return True, f"{s.get('model')} on this Mac"
        except Exception:
            return False, "Ollama isn't running"
    return False, ""


def usage(days=7):
    since = (datetime.datetime.now().astimezone() - datetime.timedelta(days=days)).isoformat()
    by, jobs = {}, {}
    if USAGE.exists():
        for line in USAGE.read_text().splitlines()[-5000:]:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("at", "") < since:
                continue
            b = by.setdefault(r["engine"], {"calls": 0, "ok": 0, "failed": 0, "cost": 0.0})
            b["calls"] += 1
            b["ok" if r.get("ok") else "failed"] += 1
            b["cost"] += r.get("cost") or 0
            if r.get("ok"):
                jobs.setdefault(r["job"], {}).setdefault(r["engine"], 0)
                jobs[r["job"]][r["engine"]] += 1
    ok = sum(b["ok"] for b in by.values())
    return {"days": days, "engines": by, "jobs": jobs, "claude_share": round(by.get("claude", {}).get("ok", 0) / ok, 2) if ok else None,
            "cost": round(sum(b["cost"] for b in by.values()), 2)}


def status():
    s = settings()
    return {"jobs": {j: {"what": w, "web": web, "chain": s["routes"][j]} for j, (w, web) in JOBS.items()},
            "engines": {k: {**v, "config": s["engines"].get(k, {}), "available": available(k)[0], "detail": available(k)[1]}
                        for k, v in ENGINES.items()},
            "presets": {k: {"name": n, "what": w, "routes": r} for k, (n, w, r) in PRESETS.items()},
            "preset": next((k for k, (_, _, r) in PRESETS.items() if r == s["routes"]), None),
            "usage": usage()}


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["status"]:
        for j, v in status()["jobs"].items():
            print(f"{j:10} {' → '.join(v['chain'])}")
        for k, v in status()["engines"].items():
            print(f"  {'ok ' if v['available'] else '-- '} {v['name']}: {v['detail']}")
    elif a[:1] == ["usage"]:
        print(json.dumps(usage(), indent=1))
    elif a[:1] == ["test"] and len(a) == 2:
        r, meta = call(a[1], 'Reply with ONLY this JSON: {"ok": true, "engine": "<your model name>"}', timeout=120)
        print(r, meta)
    else:
        sys.exit(__doc__)
