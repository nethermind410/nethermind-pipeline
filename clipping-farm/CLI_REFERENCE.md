# Clipping Farm CLI Reference

Actual CLI commands (18). The brief's "7-command contract" does not match reality — this is the source of truth.

## Core pipeline
- `plan` — generate a pipeline plan for a source (dry run)
- `run` — ingest source, plan, execute full pipeline
- `worker` — run one worker tick (process one pending job)
- `status` — database status summary
- `snapshot` — snapshot of a source's run state

## Source / asset management
- `ingest` — ingest a local file as a source
- `source` — get source info
- `asset` — get asset snapshot
- `assets` — list assets (filter by purpose)
- `authorise` — set rights state to AUTHORISED
- `acquire` — download a URL into the asset library

## Reference system
- `reference` — inspect a URL reference and persist it
- `run-reference` — run pipeline in REFERENCE mode on an asset
- `clip-reference` — run pipeline for a single reference clip
- `dna` — write reference DNA for an asset

## HUD / artifacts
- `hud` — start the local HUD server
- `artifact` — get artifact by cache key + verify
- `init` — initialise database
- `demo` — demo mode (authorises source, runs pipeline)

## Common options
- `--db` — database path (default: clipping_farm.db)
- `--source-id` — source identifier
- `--asset-id` — asset identifier
- `--source-path` — local file path
- `--budget` — budget limit
- `--kind` — file|url (default: file)
- `--purpose` — production_source|reference|both
- `--url` — URL for reference/acquire
- `--cache-key` — artifact cache key

## Agent workflow (business layer)
The CLI is the execution plane. The business layer adds agents on top:

1. Trending agent → writes JEV → script writer agent → writes JEV → content referencer → writes JEV → human approval → downloader → editor → metadata agent → human approval → platform posters

Each agent reads the previous agent's JEV. If the JEV is incomplete, the step didn't finish — retry or reassign.