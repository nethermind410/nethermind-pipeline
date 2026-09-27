"""Studio extension: the quality gate. quality_gate.py does the actual checking (cheap,
local, no paid AI calls); this module just exposes it to the front end and records
overrides so "I posted it anyway" always has a reason attached.

GET /api/gate/<id>  ->  quality_gate.check(id)

studio.py's /api/run calls quality_gate.check() itself (not this module) before letting
post_live/post_now/post_at through, and calls record_override() here when she supplies a
gate_override reason on a failing gate — that keeps studio.py's change to a few lines and
this file owning the "what happens when she overrides" logic, same split as everywhere else.
"""
import re

import quality_gate
import studio_ext_why as why

ID_RE = re.compile(r"^[a-z0-9_]+$")


def gate_for_id(rest):
    vid = rest.strip("/")
    if not ID_RE.match(vid):
        raise ValueError("bad id")
    return quality_gate.check(vid)


def record_override(vid, result, reason):
    """Logs the override through the same overrides.json / confidence-nudge plumbing every
    other AI-choice override uses (studio_ext_why.py) — lane "post" so overriding the gate a
    lot (across different videos) is what nudges confidence down, not overriding one video
    repeatedly."""
    blockers = "; ".join(c["name"] for c in result.get("checks", []) if not c["ok"] and c["level"] == "block")
    return why.record({"kind": "gate", "lane": "post", "ai": f"blocked: {blockers}" if blockers else "blocked",
                        "user": reason[:300]})


GET_PREFIX = {"/api/gate/": gate_for_id}
