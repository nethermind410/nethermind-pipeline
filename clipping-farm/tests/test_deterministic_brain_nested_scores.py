from clipping_farm.brain import DeterministicBrain
from clipping_farm.candidates import Candidate


def test_deterministic_brain_preserves_nested_scores_without_rounding_error():
    candidate = Candidate(
        start=10.0,
        end=20.0,
        text="A complete candidate.",
        scores={
            "hook": 0.8,
            "payoff": 0.8,
            "standalone": 0.9,
            "information": 0.8,
            "novelty": 0.7,
            "jev_score": 7.8,
            "jev_metrics": {
                "opening_strength": 9.0,
                "payoff_strength": 8.0,
            },
            "jev_risks": [],
            "semantic_qc": {
                "pass": True,
            },
        },
    )

    result = DeterministicBrain().analyse(candidate)

    assert result.decision in {"accept", "reject"}
    assert isinstance(result.confidence, float)

    assert result.scores["standalone"] == 0.9
    assert result.scores["jev_score"] == 7.8
    assert result.scores["jev_metrics"]["opening_strength"] == 9.0
    assert result.scores["semantic_qc"]["pass"] is True
