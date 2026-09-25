"""Studio extension: AI engines — which engine writes each job, the fallbacks, keys and cost.

GET  /api/llm              jobs → engine chains, engine status, presets, last 7 days' usage
POST /api/llm/save         {"routes": {job: [engine, ...]}, "engines": {engine: {model, base_url, key_env}}}
POST /api/llm/preset       {"id": "claude" | "never_stop" | "lean"}
POST /api/llm/key          {"name": "ANTHROPIC_API_KEY" | ..., "value"} → written to .env (never shown again)
POST /api/llm/test         {"engine"} → one tiny call to prove it's connected
"""
import llm


def status():
    return llm.status()


def save(body):
    llm.save(body)
    return {"ok": True, "reply": "Saved — the next draft uses these engines."}


def preset(body):
    p = llm.PRESETS.get(str(body.get("id")))
    if not p:
        raise ValueError("Unknown preset.")
    llm.save({"routes": p[2]})
    return {"ok": True, "reply": f"{p[0]}: {p[1]}"}


def key(body):
    return llm.set_key(str(body.get("name", "")), str(body.get("value", "")))


def test(body):
    engine = str(body.get("engine", ""))
    if engine not in llm.ENGINES:
        raise ValueError("Which engine?")
    try:
        r, meta = llm.call(engine, 'Reply with ONLY this JSON: {"ok": true}', timeout=120)
    except llm.EngineError as e:
        raise ValueError(f"{llm.ENGINES[engine]['name']}: {e}")
    return {"ok": True, "reply": f"{llm.ENGINES[engine]['name']} answered" + (f" ({meta.get('model')})" if meta.get("model") else "") + "."}


GET = {"/api/llm": status}
POST = {"/api/llm/save": save, "/api/llm/preset": preset, "/api/llm/key": key, "/api/llm/test": test}
