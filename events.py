"""events.py — thread-safe in-process pub/sub behind Studio's live updates.

studio.py's GET /api/events streams these to the browser over Server-Sent Events: one
subscription (a bounded queue) per open tab. Anything in the app — the job runner,
orchestrator's task log, /api/done — calls publish() and every open tab hears about it
within a second, instead of each page polling on its own timer.

publish() never blocks the caller and never raises: a full subscriber (a slow or gone
tab) just drops its oldest queued message rather than stall whoever is publishing.
"""
import itertools
import json
import queue
import threading

_lock = threading.Lock()
_subs = {}
_ids = itertools.count(1)
MAXQ = 200          # per-subscriber backlog before we start dropping the oldest


def subscribe():
    """Register a new subscriber. Returns (id, Queue[str]) — id for unsubscribe()."""
    q = queue.Queue(maxsize=MAXQ)
    with _lock:
        sid = next(_ids)
        _subs[sid] = q
    return sid, q


def unsubscribe(sid):
    with _lock:
        _subs.pop(sid, None)


def publish(kind, data=None):
    """Fan a JSON-able event out to every subscriber. kind: "job" | "queue" | "task" | "done"."""
    try:
        payload = json.dumps({"event": kind, "data": data if data is not None else {}}, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return
    with _lock:
        subs = list(_subs.values())
    for q in subs:
        try:
            q.put_nowait(payload)
        except queue.Full:
            try:
                q.get_nowait()          # drop the oldest rather than block or lose the newest
                q.put_nowait(payload)
            except queue.Empty:
                pass


def subscriber_count():
    with _lock:
        return len(_subs)
