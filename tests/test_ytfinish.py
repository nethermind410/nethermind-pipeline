#!/usr/bin/env python3
"""tests/test_ytfinish.py — the YouTube "finish it" automations, verified WITHOUT any real Google
calls: a tiny fake HTTP layer stands in for the YouTube Data API, and NETHER_DATA points at a throwaway
temp folder for the run. Checks each automation's idempotency (a second run makes no write) and that
the pieces the API can't do (pinning, end screens, Related video) stay untouched.

    .venv/bin/python tests/test_ytfinish.py
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

_tmp = tempfile.mkdtemp(prefix="ytfinish_test_")
os.environ["NETHER_DATA"] = _tmp
(Path(_tmp) / "out").mkdir(parents=True, exist_ok=True)
(Path(_tmp) / "packaging").mkdir(parents=True, exist_ok=True)

import youtube_auth  # noqa: E402
import studio_ext_ytfinish as yf  # noqa: E402


class FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = json.dumps(body)

    def json(self):
        return self._body


class FakeGoogle:
    """A minimal stand-in for the bits of the YouTube Data API this module calls. Tracks write
    counts per resource so tests can assert a second, no-op run makes zero additional writes."""

    def __init__(self):
        self.video = {"id": "yt123", "snippet": {"title": "T", "description": "D", "categoryId": "27", "tags": []},
                      "status": {"privacyStatus": "public", "containsSyntheticMedia": False}}
        self.comments = []
        self.playlists = []
        self.playlist_items = {}
        self.writes = {"videos": 0, "commentThreads": 0, "playlists": 0, "playlistItems": 0}

    def request(self, method, url, params=None, json=None, headers=None, timeout=None):
        params = params or {}
        path = url.rsplit("youtube/v3/", 1)[-1]
        if path == "videos" and method == "GET":
            part = params.get("part", "")
            body = {"items": [{k: self.video[k] for k in self.video if k == "id" or k in part.split(",")}]}
            return FakeResponse(200, body)
        if path == "videos" and method == "PUT":
            self.writes["videos"] += 1
            if "snippet" in json:
                self.video["snippet"] = json["snippet"]
            if "status" in json:
                self.video["status"] = json["status"]
            return FakeResponse(200, {"id": self.video["id"]})
        if path == "commentThreads" and method == "GET":
            return FakeResponse(200, {"items": self.comments})
        if path == "commentThreads" and method == "POST":
            self.writes["commentThreads"] += 1
            text = json["snippet"]["topLevelComment"]["snippet"]["textOriginal"]
            self.comments.append({"snippet": {"topLevelComment": {"snippet": {"textOriginal": text}}}})
            return FakeResponse(200, {"id": f"c{len(self.comments)}"})
        if path == "playlists" and method == "GET":
            return FakeResponse(200, {"items": [{"id": p["id"], "snippet": {"title": p["title"]}} for p in self.playlists]})
        if path == "playlists" and method == "POST":
            self.writes["playlists"] += 1
            pid = f"pl{len(self.playlists) + 1}"
            self.playlists.append({"id": pid, "title": json["snippet"]["title"]})
            self.playlist_items[pid] = []
            return FakeResponse(200, {"id": pid})
        if path == "playlistItems" and method == "GET":
            pid = params["playlistId"]
            items = [{"contentDetails": {"videoId": v}} for v in self.playlist_items.get(pid, [])]
            return FakeResponse(200, {"items": items})
        if path == "playlistItems" and method == "POST":
            self.writes["playlistItems"] += 1
            pid = json["snippet"]["playlistId"]
            self.playlist_items.setdefault(pid, []).append(json["snippet"]["resourceId"]["videoId"])
            return FakeResponse(200, {"id": "pi1"})
        raise AssertionError(f"unexpected call: {method} {path}")


class TestAutomations(unittest.TestCase):
    def setUp(self):
        self.google = FakeGoogle()
        youtube_auth.requests = self.google  # api_request() calls requests.request(...)
        youtube_auth.access_token = lambda: "FAKE-TOKEN"
        self.pkg = {"title": "Marvel's Founder Missed The Hindenburg", "youtube_tags": "Marvel, Stan Lee, nethermind",
                    "pinned_comment": "What surprised you most?", "synthetic_disclosure": True}

    def test_tags_idempotent(self):
        r1 = yf.do_tags("v1", "yt123", self.pkg)
        self.assertEqual(r1["action"], "updated")
        self.assertEqual(self.google.writes["videos"], 1)
        r2 = yf.do_tags("v1", "yt123", self.pkg)
        self.assertEqual(r2["action"], "skipped")
        self.assertEqual(self.google.writes["videos"], 1)  # no second write

    def test_disclosure_idempotent(self):
        r1 = yf.do_disclosure("v1", "yt123", self.pkg)
        self.assertEqual(r1["action"], "updated")
        self.assertEqual(self.google.writes["videos"], 1)
        self.assertTrue(self.google.video["status"]["containsSyntheticMedia"])
        self.assertEqual(self.google.video["status"]["privacyStatus"], "public")  # preserved, not clobbered
        r2 = yf.do_disclosure("v1", "yt123", self.pkg)
        self.assertEqual(r2["action"], "skipped")
        self.assertEqual(self.google.writes["videos"], 1)

    def test_disclosure_skips_when_not_flagged(self):
        pkg = {**self.pkg, "synthetic_disclosure": False}
        r = yf.do_disclosure("v1", "yt123", pkg)
        self.assertEqual(r["action"], "skipped")
        self.assertEqual(self.google.writes["videos"], 0)

    def test_comment_posts_then_skips(self):
        r1 = yf.do_comment("v1", "yt123", self.pkg)
        self.assertEqual(r1["action"], "posted")
        self.assertEqual(self.google.writes["commentThreads"], 1)
        r2 = yf.do_comment("v1", "yt123", self.pkg)
        self.assertEqual(r2["action"], "skipped")
        self.assertEqual(self.google.writes["commentThreads"], 1)  # never double-posts

    def test_playlist_creates_then_idempotent(self):
        r1 = yf.do_playlist("v1", "yt123", self.pkg)
        self.assertIn(r1["action"], ("created+added",))
        self.assertEqual(self.google.writes["playlists"], 1)
        self.assertEqual(self.google.writes["playlistItems"], 1)
        r2 = yf.do_playlist("v1", "yt123", self.pkg)
        self.assertEqual(r2["action"], "skipped")
        self.assertEqual(self.google.writes["playlists"], 1)
        self.assertEqual(self.google.writes["playlistItems"], 1)

    def test_playlist_reuses_existing_series(self):
        yf.do_playlist("v1", "yt123", self.pkg)
        r2 = yf.do_playlist("v2", "yt999", self.pkg)  # a second video, same lane/series
        self.assertEqual(self.google.writes["playlists"], 1)  # no second playlist created
        self.assertEqual(r2["action"], "added")

    def test_series_label_uses_lane(self):
        self.assertEqual(yf.series_label("Marvel's Founder Missed The Hindenburg"), "Marvel & comics")
        self.assertEqual(yf.series_label("Completely unrelated topic xyz"), "Other")

    def test_autorun_setting_defaults_off(self):
        self.assertFalse(yf.settings()["autorun"])
        yf.set_autorun({"on": True})
        self.assertTrue(yf.settings()["autorun"])
        yf.set_autorun({"on": False})
        self.assertFalse(yf.settings()["autorun"])


if __name__ == "__main__":
    unittest.main()
