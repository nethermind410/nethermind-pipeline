"""
shotplanner — NETHERMIND Shot Planner v0.2.

Turns a narration script into a machine-readable production plan
(schemas/shotplan-0.2.schema.json): one entry per shot, each saying what the
viewer must see, how to generate it, what must stay consistent, and how to
check the result.

Two stages, deliberately separate:

  beats.py     the creative decisions — what separate things each sentence asks
               the viewer to see, and how to group them into shots. Comes from a
               hand-written beat sheet, an LLM (llm.py providers), or an offline
               heuristic draft.
  compiler.py  deterministic: aligns narration to the script, estimates timing,
               links continuity between shots, assembles prompts, negative
               prompts and QC checks. Same beats in, same plan out.

validate.py re-checks any plan file (including hand-edited ones) against the
schema and the cross-field rules.
"""
VERSION = "0.2.0"
SCHEMA_ID = "nethermind.shotplan/0.2"
