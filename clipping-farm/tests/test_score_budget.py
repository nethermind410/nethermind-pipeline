from types import SimpleNamespace
from unittest.mock import Mock, patch

from clipping_farm.agent_handlers import LocalHandlers
from clipping_farm.providers import ProviderResult


def test_visual_scoring_receives_budget_after_text_model_cost():
    handlers = LocalHandlers.__new__(LocalHandlers)
    handlers._deps = lambda j: [
        {"candidates": [{"start": 1, "end": 13, "text": "Candidate", "scores": {}, "decision": "REVIEW"}]},
        {"transcript": [{"start": 1, "end": 13, "text": "Candidate"}]},
        {"audio": {}},
        {"scenes": []},
        {"metadata": {"format": {"duration": 20}}},
    ]
    handlers.frames = Mock()
    handlers.frames.sample.return_value = []
    handlers.brain = Mock()
    handlers.brain.analyse.return_value = SimpleNamespace(
        result=ProviderResult("review", 0.8, "reason", [], {}, "mock", actual_cost=0.3),
        trace=[],
        actual_cost=0.3,
    )
    handlers.vision_adaptive = Mock()
    handlers.vision_adaptive.analyse.return_value = (None, [])
    handlers.fusion = Mock()
    handlers.fusion.analyse.return_value = Mock(
        scores={}, confidence=0.8, decision="review", evidence=[], missing_modalities=[]
    )
    job = {
        "id": "score-job",
        "budget": 1.0,
        "payload": {"source_id": "source", "source_path": "/unused"},
    }

    with patch.object(handlers, "_path", return_value="video.mp4"), patch(
        "clipping_farm.agent_handlers.build_packet",
        return_value=Mock(digest=Mock(return_value="digest")),
    ), patch("clipping_farm.agent_handlers.standalone_evidence", return_value=[]):
        handlers.score_candidates(job)

    request = handlers.vision_adaptive.analyse.call_args.args[0]
    assert request.budget_remaining == 0.7
