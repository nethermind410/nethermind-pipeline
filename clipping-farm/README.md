# Clipping Farm — Harness Foundation

A provider-agnostic, credit-conscious job orchestration core for authorised short-form clip production.

## Design
- Jobs are durable; workers are disposable.
- SQLite is the source of truth.
- Every expensive operation is idempotent and cache-first.
- Workers claim jobs atomically with leases.
- Costs are reserved before execution and reconciled after execution.
- Agents request capabilities; the Harness chooses deterministic/local/cheap/premium execution.
- Rights are a hard gate.
- Publishing requires explicit human approval.

## Current foundation
A3 Worker Lifecycle · A4 Idempotency · A5 Locking · A6 Cost Accounting · A7 Model Router · A8 Adaptive Escalation · A9 Learning hooks · A10 Approval Gate · A11 Failure Isolation.

## Run
```bash
python -m clipping_farm.cli init
python -m clipping_farm.cli demo
python -m clipping_farm.cli worker --once
python -m clipping_farm.cli status
```

The implementation is intentionally small and dependency-light. FFmpeg, Whisper, vision models and external providers plug into the same contracts later.


## Next integration gate
The next implementation step is wiring real local media analysis/transcription/render adapters behind these contracts, with end-to-end fixture tests before touching the existing Nethermind factory.
