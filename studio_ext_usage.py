"""Studio extension: usage — how much Claude allowance / paid-API spend each job has used, today and this week.

GET  /api/usage      today's and this week's totals by job: calls, tokens in/out, cost — read straight
                      from out/llm_usage.jsonl (every llm.py call, plus anything logged with llm.log_paid_call,
                      such as vidIQ scoring). Nothing here calls Claude or any paid API; it only reads the log.
"""
import datetime
import json

import llm

OUT = llm.OUT
USAGE = llm.USAGE


def _rows(since_iso):
    if not USAGE.exists():
        return []
    out = []
    for line in USAGE.read_text().splitlines()[-20000:]:
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("at", "") >= since_iso:
            out.append(r)
    return out


def _bucket(rows):
    """calls/tokens/cost per job, plus an overall total — for the day or the week."""
    jobs = {}
    total = {"calls": 0, "in": 0, "out": 0, "cost": 0.0}
    for r in rows:
        if r.get("ok") is False:
            # a failed attempt is still logged (for llm.usage()'s per-engine table), but for "how much did
            # this cost me" we only count answers that actually landed.
            continue
        job = r.get("job") or "other"
        b = jobs.setdefault(job, {"calls": 0, "in": 0, "out": 0, "cost": 0.0})
        b["calls"] += 1
        b["in"] += r.get("in") or 0
        b["out"] += r.get("out") or 0
        b["cost"] += r.get("cost") or 0.0
        total["calls"] += 1
        total["in"] += r.get("in") or 0
        total["out"] += r.get("out") or 0
        total["cost"] += r.get("cost") or 0.0
    for b in jobs.values():
        b["cost"] = round(b["cost"], 4)
    total["cost"] = round(total["cost"], 4)
    top_job = max(jobs.items(), key=lambda kv: kv[1]["calls"])[0] if jobs else None
    top_pct = round(100 * jobs[top_job]["calls"] / total["calls"]) if top_job and total["calls"] else None
    return {"jobs": jobs, "total": total, "top_job": top_job, "top_pct": top_pct}


def usage():
    now = datetime.datetime.now().astimezone()
    today_since = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
    week_since = (now - datetime.timedelta(days=7)).isoformat(timespec="seconds")
    week_rows = _rows(week_since)
    today_rows = [r for r in week_rows if r.get("at", "") >= today_since]
    return {"today": _bucket(today_rows), "week": _bucket(week_rows)}


GET = {"/api/usage": usage}
