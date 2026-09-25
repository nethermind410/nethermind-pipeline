---
name: delegate
description: Use on EVERY task in this repo. Routes all work to sub-agents via the Agent tool with the right model (fable/opus/haiku) instead of doing it inline. Applies to coding, fixing, testing, docs, refactors, reviews, searches, and questions.
---

# Delegate

The main session plans, dispatches, and reads reports. It does not do the work itself.

## Rules

- Plan first, then dispatch. One sub-agent per task.
- Run independent sub-agents in parallel: several Agent calls in one message.
- Always pass `model` on every Agent call.
- Read the sub-agent's report. Don't re-read the files it touched.

## Model routing

| Model | Use for |
|---|---|
| `fable` (Fable 5.1) | Architecture, hard bugs, code review |
| `opus` (Opus 5.5) | Edits, tests, docs, refactors. **Default for ordinary tasks.** |
| `haiku` (Haiku 4.5) | Lookups, searches, summaries |

Don't default to Fable. Use it only for the three categories above. (`sonnet` is also a valid value but isn't part of this routing.)

## Writing the sub-agent prompt

Each prompt must stand on its own. Include:

1. **Goal**: what done looks like.
2. **Files/paths**: where to work, as absolute paths.
3. **Constraints**: what not to touch, style or scope limits.
4. **Branch**: the git branch to work on, and whether to commit/push.
5. **Report back**: a short summary of changes, test results, and anything unfinished.

## Worked example

Task: "Fix the crash in `make_short.py`, add a test for it, and update the README."

1. Dispatch one agent, `model: "fable"`: diagnose and fix the crash; report the root cause and the change.
2. After its report, dispatch two agents in parallel, in one message:
   - `model: "opus"`: add a regression test for the fix; report test results.
   - `model: "opus"`: update README.md to reflect the fix; report what changed.
3. Read the three reports and summarize for the user.

A quick "where is X defined?" question goes to one `haiku` agent.
