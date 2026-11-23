# HANDOFF — Muse ⇄ Claude Code

The shared task file. Muse writes briefs here; Claude Code (in a cloud session)
picks them up, does the work, and writes results back. Start every session by
reading `CLAUDE.md`, then this file.

**Protocol**
- One task open at a time. Status flow: `QUEUED → WORKING → DONE` (or `BLOCKED` + the reason).
- Claude sets the status to WORKING when it starts, and writes the result —
  what was built, file paths, gate results — in the task's Result block before
  setting DONE. Commit + push after every update.
- Muse verifies every DONE result before it is used. A result is not finished
  until Muse has checked it.
- Questions go in the task's Notes. No guessing past a gap.

---

## CURRENT TASK

_None queued. Muse adds the first brief here._

## QUEUE

_Empty._

## DONE

_Empty._
