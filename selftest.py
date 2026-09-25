#!/usr/bin/env python3
"""selftest.py — is everything NETHER needs on this Mac working? Same checks as Control → Settings.

    python3 selftest.py
"""
import studio_api

rows = studio_api.health()
for r in rows:
    print(f"  {'ok  ' if r['ok'] else 'FIX '} {r['name']:24s} {r['detail']}")
bad = [r for r in rows if not r["ok"]]
print(f"\n{len(rows) - len(bad)} of {len(rows)} working" + (f" — fix: {', '.join(r['name'] for r in bad)}" if bad else " — all good"))
