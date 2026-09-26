"""Studio extension: Connections (Settings) — one card per service instead of the plain status list,
and the Daily schedule switch. Keys and tests reuse the setup wizard's own endpoints; nothing here
stores or echoes a key value.

GET  /api/connect          services with a health() status dot, why you need each, a deep link to get
                            a key, and which of its keys are already saved (names only)
GET  /api/schedule          the Daily run's LaunchAgent: installed?, its time, last run
POST /api/schedule          {"on": bool, "time": "07:00"} → install/update or remove the LaunchAgent
"""
import channel
import schedule
import studio_api as api
import studio_ext_setup as setup

LINKS = {
    "writing": "https://console.anthropic.com/settings/keys",
    "youtube": "https://console.cloud.google.com/apis/library/youtube.googleapis.com",
    "buffer": "https://publish.buffer.com/settings/apps",
    "r2": "https://dash.cloudflare.com/?to=/:account/r2/api-tokens",
    "cloudflare": "https://dash.cloudflare.com/profile/api-tokens",
}
HEALTH_NAME = {
    "writing": "Drafting (Claude)", "youtube": "YouTube (true numbers)", "buffer": "Buffer",
    "r2": "Video hosting (R2)", "cloudflare": "AI art (Cloudflare)", "vidiq": "vidIQ (title scores)", "jarvis": "Jarvis",
}


def connections():
    st = setup.status()
    hs = {h["name"]: h for h in api.health()}
    out = []
    for s in st["services"]:
        h = hs.get(HEALTH_NAME.get(s["id"], ""))
        ok = bool(h and h["ok"]) if h is not None else all(s["set"].values())
        out.append({**s, "ok": ok, "link": LINKS.get(s["id"], "")})
    vh = hs.get(HEALTH_NAME["vidiq"])
    out.append({"id": "vidiq", "label": "vidIQ (title scores)", "optional": True, "keyless": True,
                "why": "Scores titles and thumbnails before you publish. Connected through the vidIQ "
                       "integration, so there's no key to paste here.",
                "ok": bool(vh and vh["ok"]), "detail": vh["detail"] if vh else "Not connected",
                "link": "https://vidiq.com/pricing/"})
    j = channel.jarvis()
    jh = hs.get(HEALTH_NAME["jarvis"])
    out.append({"id": "jarvis", "label": "Jarvis", "optional": True, "jarvis": True,
                "why": "Answers ⌘K questions about your channel out loud, if you run a Jarvis voice assistant on this Mac.",
                "enabled": j["enabled"], "dir": str(j["dir"] or ""),
                "ok": bool(j["enabled"] and jh and jh["ok"]),
                "detail": (jh["detail"] if jh else "Not connected") if j["enabled"] else "Off"})
    return {"services": out, "tools": st["tools"]}


def schedule_status():
    return schedule.status()


def schedule_set(b):
    if not b.get("on"):
        return schedule.remove()
    return schedule.install(str(b.get("time") or "07:00"))


def jarvis_save(b):
    name = channel.get("name")
    j = b.get("jarvis") or {}
    channel.save({"name": name, "jarvis": {"enabled": bool(j.get("enabled")), "dir": str(j.get("dir") or "")[:300],
                                            "url": channel.jarvis()["url"]}})
    return {"ok": True, "reply": "Saved."}


GET = {"/api/connect": connections, "/api/schedule": schedule_status}
POST = {"/api/schedule": schedule_set, "/api/connect/jarvis": jarvis_save}
