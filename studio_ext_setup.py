"""Studio extension: first-run setup, and the demo.

GET  /api/setup               the channel (public fields), lanes, voices, which keys are set (names only), tools
POST /api/setup/channel       {name, owner, about, lanes, custom_lane, hashtag, youtube_channel_id, narration_voice, jarvis}
POST /api/setup/key           {name, value} → .env through llm.set_key (validated, 0600, never echoed back)
POST /api/setup/test          {service} → one small call that proves the connection works
POST /api/setup/finish        marks setup complete → the page lands on the brain
POST /api/setup/demo          builds the sample data folder and restarts on it ("Demo data" everywhere)
POST /api/setup/leave_demo    restarts on the real data folder
"""
import os, re, shutil, sys, threading, time
from pathlib import Path

import channel
import llm
import workspace

if channel.DATA != channel.HERE:          # a separate data folder (packaged app, demo): make sure it has the basics
    workspace.ensure()

VOICES = [("am_liam", "Liam — warm, American"), ("am_michael", "Michael — calm, American"), ("af_heart", "Heart — bright, American"),
          ("af_bella", "Bella — soft, American"), ("bf_emma", "Emma — clear, British"), ("bm_george", "George — low, British")]
SERVICES = {  # what each connection needs, in the order the wizard asks
    "writing": {"label": "Writing (Claude)", "keys": ["ANTHROPIC_API_KEY"], "optional": True,
                "why": "Researches and writes scripts. Uses your Claude subscription if Claude Code is installed; an API key is the alternative."},
    "youtube": {"label": "YouTube numbers", "keys": ["YOUTUBE_API_KEY"], "optional": True,
                "why": "True views, subscribers and comments. A free key from Google Cloud (YouTube Data API v3)."},
    "buffer": {"label": "Posting (Buffer)", "keys": ["BUFFER_API_KEY"], "optional": True,
               "why": "Schedules finished videos to YouTube, TikTok and Instagram through your Buffer account."},
    "r2": {"label": "Video hosting (Cloudflare R2)", "keys": ["R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT", "R2_BUCKET", "R2_PUBLIC_BASE_URL"],
           "optional": True, "why": "Buffer fetches each video from a public link; R2 holds it."},
    "cloudflare": {"label": "AI art (Cloudflare Workers AI)", "keys": ["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"], "optional": True,
                   "why": "Original artwork for topics with no public-domain photos."},
}
DEMO_DIR = Path(os.environ.get("NETHER_DEMO_DIR") or Path.home() / "Library" / "Application Support" / "Nether" / "Demo").expanduser()


def _env_set():
    return {k: bool(v) for k, v in llm.env().items() if k in llm.ENV_NAMES and v and k in _file_names()}


def _file_names():
    p = channel.ENV_FILE
    return {l.split("=", 1)[0].strip() for l in p.read_text().splitlines() if "=" in l and not l.strip().startswith("#")} if p.exists() else set()


def status():
    c = channel.get()
    have = _env_set()
    return {**channel.public(), "owner": c["owner"], "narration_voice": c["narration_voice"], "youtube_channel_id": c["youtube_channel_id"],
            "hashtag_raw": c["hashtag"], "setup_complete": bool(c.get("setup_complete")),
            "jarvis_dir": str(c["jarvis"].get("dir") or ""),
            "lane_library": [{"id": k, "label": v["label"], "copyright": v["copyright"], "on": k in channel.lanes(),
                              "custom": k in (c.get("custom_lanes") or {})} for k, v in channel.lane_defs().items()],
            "voices": [{"id": v, "label": l} for v, l in VOICES],
            "services": [{"id": k, **s, "set": {n: bool(have.get(n)) for n in s["keys"]}} for k, s in SERVICES.items()],
            "tools": {"claude": llm.available("claude")[0], "ffmpeg": bool(shutil.which("ffmpeg")), "demo_dir": str(DEMO_DIR)}}


def _clean(v, n=120):
    return re.sub(r"[\r\n\t]+", " ", str(v or "")).strip()[:n]


def save_channel(b):
    name = _clean(b.get("name"), 60)
    if not name:
        raise ValueError("Give your channel a name.")
    lanes = [l for l in (b.get("lanes") or []) if isinstance(l, str)]
    custom = dict(channel.get("custom_lanes") or {})
    cl = b.get("custom_lane") or {}
    if _clean(cl.get("label"), 40):
        lid = re.sub(r"[^a-z0-9]+", "_", cl["label"].lower()).strip("_")[:24] or "custom"
        words = " ".join(re.findall(r"[a-z0-9\-']+", str(cl.get("words") or cl["label"]).lower()))[:600]
        custom[lid] = {"label": _clean(cl["label"], 40), "words": words or lid, "copyright": bool(cl.get("copyright"))}
        lanes.append(lid)
    known = {**channel.LANE_LIBRARY, **custom}
    lanes = [l for l in dict.fromkeys(lanes) if l in known]
    if not lanes:
        raise ValueError("Pick at least one lane.")
    yt = _clean(b.get("youtube_channel_id"), 40)
    if yt and not re.fullmatch(r"UC[A-Za-z0-9_\-]{22}", yt):
        raise ValueError("A YouTube channel id starts with UC and is 24 characters (YouTube Studio → Settings → Channel → Advanced).")
    tag = re.sub(r"[^a-z0-9_]", "", str(b.get("hashtag") or name).lower().lstrip("#"))[:30]
    voice = b.get("narration_voice") if b.get("narration_voice") in dict(VOICES) else "am_liam"
    j = b.get("jarvis") or {}
    labels = [known[l]["label"] for l in lanes]
    channel.save({
        "name": name, "owner": _clean(b.get("owner"), 40) or "you", "about": _clean(b.get("about"), 300),
        "lanes": lanes, "custom_lanes": custom, "off_lanes": [l for l in channel.off_lanes() if l not in lanes],
        "title_subjects": sorted({w for l in lanes for w in known[l]["words"].split() if len(w) > 3})[:40],
        "hashtag": tag, "replies_about": ", ".join(labels), "long_hashtags": f"#{tag}" if tag else "",
        "subscribe_line": f"Subscribe to {name} for the true stories behind {', '.join(labels[:3]).lower()}.",
        "youtube_channel_id": yt, "narration_voice": voice, "app_name": channel.get("app_name"),
        "jarvis": {"enabled": bool(j.get("enabled")), "dir": _clean(j.get("dir"), 300), "url": channel.get("jarvis")["url"]},
    })
    if channel.TOPICS.exists() and "| Hook |" in channel.TOPICS.read_text() and len(channel.TOPICS.read_text().splitlines()) < 40:
        channel.TOPICS.write_text(workspace.topics_md())     # still the empty starter: re-cut it for the lanes just picked
    workspace.ensure()
    return {"ok": True, "reply": f"{name} is set up."}


def key(b):
    return llm.set_key(str(b.get("name", "")), str(b.get("value", "")), allowed=tuple(llm.ENV_NAMES))


def _redact(msg):
    msg = str(msg)
    for k, v in llm.env().items():
        if k in llm.ENV_NAMES and v and len(v) > 5:
            msg = msg.replace(v, "•••")
    return re.sub(r"key=[^&\s]+", "key=•••", msg)[:300]


def _test(service):
    import requests
    e = llm.env()
    if service == "writing":
        if llm.available("claude")[0] and not e.get("ANTHROPIC_API_KEY"):
            return "Claude Code is installed — drafting uses your Claude subscription."
        if not e.get("ANTHROPIC_API_KEY"):
            raise ValueError("Install Claude Code, or add an Anthropic API key.")
        r, meta = llm.call("anthropic", 'Reply with ONLY this JSON: {"ok": true}', timeout=60)
        return f"The Anthropic API answered ({meta.get('model')})."
    if service == "youtube":
        if not e.get("YOUTUBE_API_KEY"):
            raise ValueError("Add the YouTube API key first.")
        cid = channel.get("youtube_channel_id")
        r = requests.get("https://www.googleapis.com/youtube/v3/channels", timeout=20,
                         params={"part": "snippet,statistics", "id": cid or "UC_x5XG1OV2P6uZZ5FSM9Ttw", "key": e["YOUTUBE_API_KEY"]})
        if r.status_code != 200:
            raise ValueError(f"YouTube said {r.status_code}: {r.json().get('error', {}).get('message', '')}")
        items = r.json().get("items") or []
        if not cid:
            return "The key works. Add your channel id to see your own numbers."
        if not items:
            raise ValueError("The key works, but no channel has that id.")
        return f"Connected to {items[0]['snippet']['title']}."
    if service == "buffer":
        if not e.get("BUFFER_API_KEY"):
            raise ValueError("Add the Buffer key first.")
        h = {"Authorization": f"Bearer {e['BUFFER_API_KEY']}"}
        gql = lambda q, v=None: requests.post("https://api.buffer.com/graphql", headers=h, json={"query": q, "variables": v or {}}, timeout=30).json()
        d = gql("{ account { organizations { id name } } }")
        if d.get("errors") or not (d.get("data") or {}).get("account"):
            raise ValueError("Buffer didn't accept that key.")
        org = d["data"]["account"]["organizations"][0]["id"]
        try:                                        # find the connected channels so posting knows where to go
            ch = gql("query($o: OrganizationId!) { channels(input: {organizationId: $o}) { id service } }", {"o": org})
            found = {c["service"]: c["id"] for c in (ch.get("data") or {}).get("channels") or [] if c.get("service") in ("youtube", "instagram", "tiktok")}
        except Exception:
            found = {}
        if found:
            channel.save({"buffer_channels": {**channel.get("buffer_channels"), **found}})
            return "Connected. Found " + ", ".join(sorted(found)) + " in Buffer."
        return "Connected. Add your YouTube, TikTok and Instagram channels in Buffer, then test again."
    if service == "r2":
        miss = [k for k in SERVICES["r2"]["keys"] if not e.get(k)]
        if miss:
            raise ValueError("Still needed: " + ", ".join(miss))
        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            raise ValueError("The boto3 package isn't installed.")
        boto3.client("s3", endpoint_url=e["R2_ENDPOINT"], aws_access_key_id=e["R2_ACCESS_KEY_ID"], aws_secret_access_key=e["R2_SECRET_ACCESS_KEY"],
                     config=Config(signature_version="s3v4"), region_name="auto").head_bucket(Bucket=e["R2_BUCKET"])
        return f"Connected to the {e['R2_BUCKET']} bucket."
    if service == "cloudflare":
        if not (e.get("CLOUDFLARE_ACCOUNT_ID") and e.get("CLOUDFLARE_API_TOKEN")):
            raise ValueError("Add the account id and the API token first.")
        r = requests.get("https://api.cloudflare.com/client/v4/user/tokens/verify", timeout=20,
                         headers={"Authorization": f"Bearer {e['CLOUDFLARE_API_TOKEN']}"})
        if not r.ok or not r.json().get("success"):
            raise ValueError("Cloudflare didn't accept that token.")
        return "Connected to Cloudflare Workers AI."
    raise ValueError("Which connection?")


def test(b):
    try:
        return {"ok": True, "reply": _test(str(b.get("service", "")))}
    except ValueError as err:
        raise ValueError(_redact(err))
    except Exception as err:                       # network errors etc. — say what, never a key
        raise ValueError(_redact(f"{type(err).__name__}: {err}"))


def finish(b):
    channel.save({"setup_complete": True})
    _restart("same")                     # agents read the lanes and voice when they start: start them fresh
    return {"ok": True, "reply": "All set. This is your brain.", "restart": True}


def _restart(data):
    """Re-open this server (or the Mac app) on another data folder: the new process imports every module fresh."""
    env = dict(os.environ)
    if data == "same":
        pass
    elif data:
        env.setdefault("NETHER_HOME_DATA", str(channel.DATA))
        env["NETHER_DATA"] = str(data)
    else:
        home = env.pop("NETHER_HOME_DATA", "")
        env.pop("NETHER_DATA", None)
        if home and Path(home).resolve() != channel.HERE:
            env["NETHER_DATA"] = home
    env["STUDIO_NO_BROWSER"] = "1"

    def go():
        time.sleep(0.6)
        os.execve(sys.executable, [sys.executable, *[a for a in sys.argv if a != "--demo"]], env)   # the folder comes from env
    threading.Thread(target=go, daemon=True).start()


def demo(b):
    import demo_data
    demo_data.build(DEMO_DIR, fresh=bool(b.get("fresh")))
    _restart(DEMO_DIR)
    return {"ok": True, "reply": "Opening the demo…", "restart": True}


def leave_demo(b):
    if not channel.is_demo():
        raise ValueError("This isn't the demo.")
    _restart(None)
    return {"ok": True, "reply": "Back to your channel…", "restart": True}


GET = {"/api/setup": status}
POST = {"/api/setup/channel": save_channel, "/api/setup/key": key, "/api/setup/test": test, "/api/setup/finish": finish,
        "/api/setup/demo": demo, "/api/setup/leave_demo": leave_demo}
