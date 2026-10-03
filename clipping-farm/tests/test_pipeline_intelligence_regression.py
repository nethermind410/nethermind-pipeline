import inspect

from clipping_farm.pipeline import ClippingPipeline
from clipping_farm.intelligence.jev import score_candidate
from clipping_farm.intelligence.semantic_qc import semantic_qc
from clipping_farm.intelligence.context_repair import repair_candidate
from clipping_farm.intelligence.boundary_optimizer import optimize_candidate


def test_pipeline_version_is_bumped():
    assert ClippingPipeline.VERSION == "screen-ocr-v2"


def test_asset_id_path_is_supported_by_create_signature():
    sig = inspect.signature(ClippingPipeline.create)
    assert "asset_id" in sig.parameters


def test_jev_and_semantic_gate_reject_weak_candidate():
    text = "and then this continues from something I said before"
    jev = score_candidate(text, 10, 22)
    semantic = semantic_qc({
        "start": 10,
        "end": 22,
        "text": text,
    })

    assert jev["jev_score"] < 7.5
    assert semantic["verdict"] != "SEMANTIC_PASS"


def test_jev_acceptance_threshold_is_explicit():
    text = (
        "Why did this happen? The answer is surprisingly simple, "
        "because the design changed everything and that is why it works."
    )
    result = score_candidate(text, 10, 24)

    assert "jev_score" in result
    assert "verdict" in result
    assert result["jev_score"] >= 0
    assert result["jev_score"] <= 10


def test_boundary_optimizer_respects_max_duration():
    candidate = {
        "start": 20,
        "end": 45,
        "text": "Why does this matter? Here is the answer."
    }
    segments = [
        {"start": 0, "end": 10, "text": "Earlier context."},
        {"start": 10, "end": 20, "text": "More context."},
        {"start": 20, "end": 30, "text": "Why does this matter?"},
        {"start": 30, "end": 45, "text": "Here is the answer."},
        {"start": 45, "end": 60, "text": "And the result is useful."},
    ]

    optimized = optimize_candidate(
        candidate,
        segments,
        score_candidate,
        max_duration=60,
    )

    assert optimized["end"] - optimized["start"] <= 60


def test_context_repair_does_not_invent_segments():
    candidate = {
        "start": 20,
        "end": 30,
        "text": "This is why it works."
    }
    segments = [
        {"start": 20, "end": 30, "text": "This is why it works."},
    ]

    repaired = repair_candidate(
        candidate,
        segments,
        score_candidate,
        max_duration=60,
    )

    assert repaired is not None
    assert repaired["text"] in {
        candidate["text"],
        "This is why it works.",
    }


def test_create_source_resolution_is_present_before_rights_check():
    source = inspect.getsource(ClippingPipeline.create)
    assert "self.db.get_asset(asset_id)" in source
    assert 'source_id = asset["source_id"]' in source
    assert "self.harness.rights.check(source_id)" in source
    assert source.index("self.db.get_asset(asset_id)") < source.index(
        "self.harness.rights.check(source_id)"
    )
