"""Studio extension: Live — a small diagnostic for the SSE event stream.

GET /api/live/status   how many tabs are listening right now (verify: two tabs open → 2)

The stream itself (GET /api/events), the job runner's publishes, and the queue live in
studio.py — this file just exposes a way to check the broker from outside.
"""
import events


def status():
    return {"subscribers": events.subscriber_count()}


GET = {"/api/live/status": status}
