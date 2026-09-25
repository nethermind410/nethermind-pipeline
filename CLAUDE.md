# CLAUDE.md

## Delegation (applies to every task)

Follow the `delegate` skill (`.claude/skills/delegate/SKILL.md`) on every task in this repo. Key rules, in case the skill isn't loaded:

- Don't do the work inline. Plan, then dispatch one sub-agent per task via the Agent tool; run independent agents in parallel.
- Always pass `model`: `fable` for architecture, hard bugs, code review; `opus` for edits, tests, docs, refactors (the default); `haiku` for lookups, searches, summaries.
- Don't default to Fable.
- Give each agent the goal, paths, constraints, and branch, and ask for a short report. Read the report; don't re-read the files it touched.
