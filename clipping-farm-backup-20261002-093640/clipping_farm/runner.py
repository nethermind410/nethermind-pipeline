"""Run controller for draining a Clipping Farm pipeline DAG."""

from dataclasses import dataclass

from .db import DB
from .worker import Worker


@dataclass
class RunResult:
    source_id: str
    state: str
    processed: int
    jobs: dict


class PipelineRunner:
    """Drain an existing pipeline plan using the normal Worker."""

    TERMINAL = {"COMPLETE", "DEAD_LETTER"}

    def __init__(
        self,
        db: DB,
        handlers: dict,
        *,
        capabilities=None,
        worker_id=None,
        lease_seconds=300,
        max_steps=1000,
    ):
        self.db = db
        self.handlers = handlers
        self.capabilities = capabilities
        self.worker = Worker(
            db,
            worker_id=worker_id,
            capabilities=capabilities,
            lease_seconds=lease_seconds,
        )
        self.max_steps = max_steps

    def _jobs(self, job_ids):
        rows = []
        for job_id in job_ids.values():
            row = self.db.cx.execute(
                """
                SELECT id, task, agent, state, attempts,
                       actual_cost, error
                FROM jobs
                WHERE id=?
                """,
                (job_id,),
            ).fetchone()
            if row:
                rows.append(dict(row))
        return rows

    def run(self, source_id, job_ids):
        processed = 0

        for _ in range(self.max_steps):
            rows = self._jobs(job_ids)
            states = {row["id"]: row["state"] for row in rows}

            if rows and all(state == "COMPLETE" for state in states.values()):
                return RunResult(
                    source_id=source_id,
                    state="COMPLETE",
                    processed=processed,
                    jobs={row["task"]: row for row in rows},
                )

            if any(state == "DEAD_LETTER" for state in states.values()):
                return RunResult(
                    source_id=source_id,
                    state="FAILED",
                    processed=processed,
                    jobs={row["task"]: row for row in rows},
                )

            did_work = self.worker.run_once(self.handlers)

            if did_work:
                processed += 1
                continue

            # A worker can have no job temporarily because a dependency
            # has not yet been promoted. Try the normal promotion pass.
            self.db.promote_ready()

            did_work = self.worker.run_once(self.handlers)

            if did_work:
                processed += 1
                continue

            rows = self._jobs(job_ids)
            states = [row["state"] for row in rows]

            if rows and all(state == "COMPLETE" for state in states):
                return RunResult(
                    source_id=source_id,
                    state="COMPLETE",
                    processed=processed,
                    jobs={row["task"]: row for row in rows},
                )

            if any(state == "DEAD_LETTER" for state in states):
                return RunResult(
                    source_id=source_id,
                    state="FAILED",
                    processed=processed,
                    jobs={row["task"]: row for row in rows},
                )

            return RunResult(
                source_id=source_id,
                state="STALLED",
                processed=processed,
                jobs={row["task"]: row for row in rows},
            )

        rows = self._jobs(job_ids)

        return RunResult(
            source_id=source_id,
            state="STEP_LIMIT",
            processed=processed,
            jobs={row["task"]: row for row in rows},
        )
