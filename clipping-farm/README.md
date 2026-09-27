# Clipping Farm

A provider-agnostic, credit-conscious production machine for turning **authorised** source media into short-form clips. It stops at `READY_FOR_REVIEW`; publishing is a separate human-approved gate.

## Architecture

```
SOURCE
  ↓
RIGHTS GATE
  ↓
DURABLE DAG / JOB QUEUE
  ├── metadata
  ├── audio analysis
  ├── scene analysis
  └── transcription
          ↓
   candidate generation
          ↓
      Brain scoring
          ↓
    diversity selection
          ↓
       FFmpeg cuts
          ↓
          QC
          ↓
       bounded repair
          ↓
    READY_FOR_REVIEW
```

## Operating rules

- Jobs are durable; workers are disposable.
- SQLite is the source of truth.
- Claims are atomic and lease-based.
- Workers can be capability-limited.
- Downstream workers read dependency results from the DB; no in-memory agent state is required.
- Deterministic/local processing happens before model escalation.
- Artifacts are cacheable by stable keys.
- Rights are a hard gate.
- Publishing requires explicit human approval.
- No network download or protection circumvention is performed by the local media layer.

## Current implementation

### Foundation
- worker lifecycle, leases and recovery
- atomic job claiming
- idempotent job creation
- dependency-aware DAG scheduling
- retry/dead-letter states
- rights gate
- approval gate
- artifact cache
- cost/model-router scaffolding
- explicit AgentRequest/AgentResult contracts

### Deterministic analysis
- FFmpeg/ffprobe metadata
- WAV extraction and audio-energy/silence analysis
- FFmpeg scene detection
- deterministic frame sampling with hashes
- transcript contract + optional local Whisper adapter
- candidate generation and scoring
- standalone/context evidence
- deterministic Brain with confidence/evidence/escalation flag
- temporal diversity selection

### Production
- 9:16 FFmpeg clipping
- explicit PASS/FAIL QC
- bounded repair loop
- review manifest
- publishing remains blocked until approval

### Worker execution
The DAG now has concrete local handlers rather than placeholder completions. Handler results are persisted through jobs, so a worker can die and another worker can continue from the DB.

## Run locally

Set the package path:

```bash
export PYTHONPATH=clipping-farm
```

Initialise:

```bash
python -m clipping_farm.cli init
```

Create an authorised plan:

```bash
python -m clipping_farm.cli demo --source-id fixture --source-path /path/to/authorised.mp4
```

Process one eligible job:

```bash
python -m clipping_farm.cli worker
```

Inspect state:

```bash
python -m clipping_farm.cli status
```

Run tests:

```bash
PYTHONPATH=clipping-farm python -m unittest discover -s clipping-farm/tests -v
```

CI runs the test suite against Python 3.10, 3.11 and 3.12 with FFmpeg installed.

## Deliberately deferred

These require model/provider capacity or later product integration:

- premium multimodal Brain
- external vision/LLM providers
- adaptive provider cost benchmarking
- sophisticated semantic hook/payoff/emotion detection
- learned user-specific scoring
- platform publishing
- performance feedback from YouTube/TikTok/Instagram
- automatic learning from retention/views/shares

The deterministic infrastructure is designed so those capabilities can be plugged in without replacing the Farm's orchestration layer.
