"""Studio extension: the guided "Make your first video" card (Today), shown until the channel has
made one. It composes existing state only — nothing here drafts, posts or approves by itself.

GET /api/first   {"show": bool, "step": 0-3, "picks": [...], "next": {...}|None, "busy": str|None,
                  "draft": {"id", "title"}|None}
"""
import studio_api as api
import studio_ext_make as make


def first():
    if api.videos():
        return {"show": False}
    ideas = api.ideas()
    d = make.drafts()
    drafts = d.get("drafts") or []
    draft = drafts[0] if drafts else None
    busy = d.get("busy")
    nxt = ideas.get("next")
    picks = [i for s in ideas.get("sections", []) for i in s["items"] if not i["made"] and not i["dismissed"]][:3]
    step = 3 if draft else 2 if busy else 1 if nxt else 0
    return {
        "show": True, "step": step, "busy": busy, "next": nxt, "picks": picks,
        "draft": {"id": draft["id"], "title": draft.get("title") or draft.get("topic") or ""} if draft else None,
    }


GET = {"/api/first": first}
