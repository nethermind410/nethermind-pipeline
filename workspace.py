#!/usr/bin/env python3
"""workspace.py — make sure a data folder has everything the app reads, without touching what's there.

    python3 workspace.py          create any missing folders/files in the active data folder

Folders: out/ cfg/ packaging/ episodes/ assets/ tts/ music/. Files, only if missing: TOPICS.md (one idea table
per lane) and LEARNINGS.md (the sections the app and the learning loop read). Never overwrites anything;
the original install already has all of these, so this is a no-op there.
"""
import channel

TOPICS_HEAD = """# Topic backlog

The queue the pipeline pulls from. Each line is a video: the hook, the format, and where to verify it. **Nothing here is
pre-verified** — the source column is where to check, not proof. Verify before scripting.

Formats: `fact` = narrated story · `creature` = animal reveal · `iceberg` = long-form iceberg essay (never a Short)
"""
LEARNINGS = """# What's working — {name}

## Evidence so far

Nothing yet — the numbers arrive once videos are live and Refresh has run.

## Working hypotheses (not yet proven)

- **The hook is frame zero.** Big text, already on screen, saying the same thing the voice says.

## Production rules (from your feedback — not up for A/B testing)

## Reviewer notes

What the user asked to change on review — patterns here should shape future builds.
"""


def topics_md(rows=None):
    """TOPICS.md for this channel's lanes. rows: {lane_id: [(hook, format, source), ...]} (the demo passes some)."""
    defs, out = channel.lane_defs(), [TOPICS_HEAD]
    for lane in channel.lanes() + ["iceberg"]:
        label = defs[lane]["label"] if lane in defs else "Iceberg"
        note = "the long-form template: any topic, 5 tiers of obscurity" if lane == "iceberg" else "your lane"
        out += [f"## {label} — {note}", "", "| Hook | Format | Verify at |", "|---|---|---|"]
        out += [f"| {h} | {f} | {s} |" for h, f, s in (rows or {}).get(lane, [])]
        out.append("")
    return "\n".join(out)


def ensure():
    d = channel.DATA
    for sub in ("out", "cfg", "packaging", "episodes", "assets", "tts", "music"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    if not channel.TOPICS.exists():
        channel.TOPICS.write_text(topics_md())
    if not channel.LEARNINGS.exists():
        channel.LEARNINGS.write_text(LEARNINGS.format(name=channel.get("name")))
    return d


if __name__ == "__main__":
    print("ready:", ensure())
