import json
import tempfile

from clipping_farm.db import DB
from clipping_farm.pipeline import ClippingPipeline


def test_snapshot_exposes_screen_ocr_candidates_for_review():
    with tempfile.NamedTemporaryFile(suffix=".db") as file:
        db = DB(file.name)
        db.set_rights("screen-source", "AUTHORISED", {"basis": "fixture"})
        plan = ClippingPipeline(db).create("screen-source")
        candidate = {
            "start": 12,
            "end": 24,
            "text": "Visible tutorial instructions",
            "decision": "REVIEW",
            "source_modality": "screen_ocr",
            "scores": {},
        }
        accepted = {
            "start": 30,
            "end": 42,
            "text": "Accepted candidate",
            "decision": "ACCEPT",
            "scores": {"source_modality": "speech"},
        }
        db.cx.execute(
            "UPDATE jobs SET state='COMPLETE', result=? WHERE id=?",
            (json.dumps({"candidates": [candidate, accepted]}), plan.jobs["score_candidates"]),
        )
        db.cx.commit()

        snapshot = db.run_snapshot("screen-source")

        assert snapshot["review_candidates"] == [candidate]
