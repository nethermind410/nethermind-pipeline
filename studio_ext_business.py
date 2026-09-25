"""Studio extension: Business → Money — revenue beyond ads, and progress to getting paid.

GET  /api/money               monetisation progress (Shorts + watch-hours routes), revenue streams, one-time setup
POST /api/business/settings   {"amazon_tag", "newsletter_url", "sponsor_email", "disclosure", "links"} → saved
POST /api/business/links      refresh the links block on every packaging file not yet posted
POST /api/business/kit        build the media kit from real numbers → {"html"} (the page opens it in a new tab)
"""
import business
import orchestrator as nether


def settings(body):
    s = business.save_settings(body)
    changed = business.refresh_all()
    return {"ok": True, "settings": s, "reply": f"Saved — links updated on {len(changed)} unposted video(s)."}


def links(body):
    tid = nether.begin("business", "Refresh affiliate + newsletter links", sub="affiliates")
    try:
        changed = business.refresh_all()
        nether.finish(tid, {"updated": changed})
        return {"ok": True, "reply": f"Links updated on {len(changed)} unposted video(s)."}
    except Exception as e:
        nether.fail(tid, f"{type(e).__name__}: {e}")
        raise ValueError(str(e))


def kit(body):
    tid = nether.begin("business", "Build the media kit", sub="sponsors")
    try:
        path = business.media_kit()
        nether.finish(tid, {"path": str(path)})
        return {"ok": True, "html": path.read_text(), "reply": "Media kit built from your real numbers."}
    except Exception as e:
        nether.fail(tid, f"{type(e).__name__}: {e}")
        raise ValueError(str(e))


GET = {"/api/money": business.money}
POST = {"/api/business/settings": settings, "/api/business/links": links, "/api/business/kit": kit}
