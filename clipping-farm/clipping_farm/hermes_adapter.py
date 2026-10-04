"""Hermes adapter — Hermes controls Clipping Farm.

Hermes is the control plane. Clipping Farm is the execution plane.
No duplication of execution logic. Hermes inspects, plans, submits,
monitors, retrieves, cancels, and cleans up.
"""
import time, hashlib, json
from typing import Optional


class HermesAdapter:
    """Adapter between Hermes control plane and Clipping Farm execution plane."""

    VERSION = "hermes-adapter-v1"

    def __init__(self, db, manifest=None, registry=None, preflight=None):
        self.db = db
        self.manifest = manifest
        self.registry = registry
        self.preflight = preflight

    def inspect_capabilities(self):
        """Hermes inspects what the system can do."""
        if self.registry:
            return self.registry.inspect()
        return {"error": "no registry"}

    def plan(self, source_id, *, title="", budget=0.0, quality_required=0.0):
        """Hermes plans a job. Returns plan dict with steps and requirements."""
        # Run preflight
        if self.preflight:
            ok, checks = self.preflight.check(
                source_id, rights_state="AUTHORISED",
                required_capabilities=["transcription", "rendering"],
                budget=budget, quality_required=quality_required,
            )
            if not ok:
                return {"plan": None, "preflight": checks, "blocked": True}

        capabilities = self.inspect_capabilities()
        return {
            "plan": {
                "source_id": source_id,
                "title": title,
                "budget": budget,
                "quality_required": quality_required,
                "steps": self._get_steps(capabilities),
            },
            "preflight": checks if self.preflight else {},
            "blocked": False,
        }

    def _get_steps(self, capabilities):
        """Determine pipeline steps based on available capabilities."""
        steps = []
        caps = capabilities.get("capabilities", {}) if isinstance(capabilities, dict) else {}

        if caps.get("transcription", {}).get("status") == "AVAILABLE":
            steps.append("transcribe")
        if caps.get("audio_analysis", {}).get("status") == "AVAILABLE":
            steps.append("analyse_audio")
        if caps.get("scene_analysis", {}).get("status") == "AVAILABLE":
            steps.append("analyse_scenes")
        if caps.get("screen_ocr", {}).get("status") == "AVAILABLE":
            steps.append("analyse_screen_text")
        steps.append("generate_candidates")
        steps.append("score_candidates")
        steps.append("select_candidates")
        steps.append("produce_clips")
        steps.append("qc")
        steps.append("repair")
        steps.append("export_review")
        return steps

    def submit(self, source_id, *, title="", budget=0.0, mode="FREE-FIRST"):
        """Hermes submits a pipeline job to Clipping Farm.

        Returns pipeline state. Hermes does not execute — it delegates.
        """
        from clipping_farm.agents.orchestrator import Orchestrator
        orch = Orchestrator(self.db)
        state = orch.run_pipeline(source_id, title=title)
        return {
            "pipeline_id": state.pipeline_id,
            "status": state.status,
            "jev_chain": state.jev_chain,
            "current_agent": state.current_agent,
        }

    def status(self, pipeline_id):
        """Hermes checks pipeline status."""
        from clipping_farm.agents.orchestrator import Orchestrator
        orch = Orchestrator(self.db)
        state = orch.get_pipeline(pipeline_id)
        if not state:
            return {"pipeline_id": pipeline_id, "status": "NOT_FOUND"}
        return {
            "pipeline_id": state.pipeline_id,
            "status": state.status,
            "current_agent": state.current_agent,
            "jev_chain": state.jev_chain,
        }

    def result(self, pipeline_id):
        """Hermes retrieves pipeline result."""
        from clipping_farm.agents.orchestrator import Orchestrator
        orch = Orchestrator(self.db)
        state = orch.get_pipeline(pipeline_id)
        if not state:
            return {"pipeline_id": pipeline_id, "status": "NOT_FOUND"}
        return {
            "pipeline_id": state.pipeline_id,
            "status": state.status,
            "jev_chain": state.jev_chain,
            "completed_at": state.completed_at,
        }

    def cancel(self, pipeline_id):
        """Hermes cancels a running pipeline."""
        row = self.db.cx.execute(
            "SELECT * FROM pipelines WHERE pipeline_id=?", (pipeline_id,)
        ).fetchone()
        if not row:
            return {"pipeline_id": pipeline_id, "status": "NOT_FOUND"}
        if row["status"] == "COMPLETE":
            return {"pipeline_id": pipeline_id, "status": "ALREADY_COMPLETE"}
        self.db.cx.execute(
            "UPDATE pipelines SET status='CANCELLED' WHERE pipeline_id=?",
            (pipeline_id,),
        )
        self.db.cx.commit()
        return {"pipeline_id": pipeline_id, "status": "CANCELLED"}

    def cleanup(self, pipeline_id):
        """Hermes cleans up pipeline artifacts."""
        # Remove pipeline record
        self.db.cx.execute("DELETE FROM pipelines WHERE pipeline_id=?", (pipeline_id,))
        # Remove associated jobs
        self.db.cx.execute(
            "DELETE FROM jobs WHERE id IN (SELECT id FROM pipelines WHERE pipeline_id=?)",
            (pipeline_id,),
        )
        self.db.cx.commit()
        return {"pipeline_id": pipeline_id, "cleaned_up": True}

    def run_full_cycle(self, source_id, *, title="", budget=0.0, quality_required=0.0):
        """Hermes runs full cycle: inspect → plan → submit → monitor → result."""
        # 1. Inspect
        capabilities = self.inspect_capabilities()

        # 2. Plan
        try:
            plan = self.plan(source_id, title=title, budget=budget, quality_required=quality_required)
        except Exception as e:
            return {"cycle": "blocked", "reason": str(e)}
        if plan.get("blocked"):
            return {"cycle": "blocked", "reason": "preflight failed", "details": plan["preflight"]}

        # 3. Submit
        submitted = self.submit(source_id, title=title, budget=budget)

        # 4. Monitor (poll until complete or error)
        max_wait = 60
        start = time.time()
        while time.time() - start < max_wait:
            status = self.status(submitted["pipeline_id"])
            if status["status"] in ("COMPLETE", "CANCELLED", "FAILED", "DEAD_LETTER"):
                break
            time.sleep(0.1)

        # 5. Retrieve result
        result = self.result(submitted["pipeline_id"])
        return {
            "cycle": "complete",
            "capabilities": capabilities.get("summary", {}),
            "plan": plan["plan"],
            "submitted": submitted,
            "final_status": result["status"],
            "jev_chain": result.get("jev_chain", []),
        }