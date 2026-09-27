"""DAG builder for the production clipping pipeline.

This layer schedules work; specialist agents remain replaceable workers.
No publishing occurs here.
"""
from dataclasses import dataclass
from .db import DB
from .harness import Harness

@dataclass
class PipelinePlan:
    source_id: str
    jobs: dict

class ClippingPipeline:
    def __init__(self, db: DB):
        self.db = db
        self.harness = Harness(db)

    def create(self, source_id: str, *, budget=0.0, mode="FREE-FIRST"):
        self.harness.rights.check(source_id)
        common = {"source_id": source_id, "mode": mode}
        def add(task, agent, deps=()):
            j, _ = self.db.add_job(
                task, agent, {**common, "budget": budget},
                idempotency_key=f"{source_id}:{task}:{mode}",
                depends_on=list(deps), budget=budget,
            )
            return j["id"]
        metadata = add("metadata", "media_agent")
        audio = add("analyse_audio", "analysis_agent")
        scenes = add("analyse_scenes", "analysis_agent")
        transcript = add("transcribe", "transcript_agent")
        candidates = add("generate_candidates", "moment_agent",
                         [transcript, audio, scenes])
        scored = add("score_candidates", "scoring_agent", [candidates, transcript, scenes])
        selected = add("select_candidates", "scoring_agent", [scored])
        production = add("produce_clips", "production_agent", [selected, metadata, transcript, scenes])
        qc = add("qc", "qc_agent", [production, transcript, scenes])
        repair = add("repair", "repair_agent", [qc])
        export = add("export_review", "export_agent", [repair])
        return PipelinePlan(source_id, {
            "metadata": metadata, "analyse_audio": audio, "analyse_scenes": scenes,
            "transcribe": transcript, "generate_candidates": candidates,
            "score_candidates": scored, "select_candidates": selected,
            "produce_clips": production, "qc": qc, "repair": repair,
            "export_review": export,
        })
