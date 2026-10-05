from clipping_farm.agent_handlers import LocalHandlers
from unittest.mock import patch


def test_select_candidates_only_passes_accept_decisions_to_production():
    handlers = LocalHandlers.__new__(LocalHandlers)
    handlers._deps = lambda _: [
        {
            "candidates": [
                {
                    "start": 0,
                    "end": 12,
                    "text": "A strong candidate that stands alone.",
                    "scores": {"standalone": 0.9, "hook": 0.9, "payoff": 0.9, "context": 0.9, "information": 0.9, "novelty": 0.9},
                    "decision": "ACCEPT",
                },
                {
                    "start": 20,
                    "end": 32,
                    "text": "A rejected candidate that stands alone.",
                    "scores": {"standalone": 0.9, "hook": 0.9, "payoff": 0.9, "context": 0.9, "information": 0.9, "novelty": 0.9},
                    "decision": "REJECT",
                },
                {
                    "start": 40,
                    "end": 52,
                    "text": "A candidate still waiting for review.",
                    "scores": {"standalone": 0.9, "hook": 0.9, "payoff": 0.9, "context": 0.9, "information": 0.9, "novelty": 0.9},
                    "decision": "REVIEW",
                },
            ]
        }
    ]

    result = handlers.select_candidates({"depends_on": "[]"})

    assert [candidate["decision"] for candidate in result["selected"]] == ["ACCEPT"]


def test_produce_clips_does_not_render_rejected_candidates(tmp_path):
    handlers = LocalHandlers.__new__(LocalHandlers)
    handlers.db = object()
    handlers.workdir = tmp_path
    handlers._deps = lambda _: [
        {
            "selected": [
                {
                    "start": 0,
                    "end": 12,
                    "text": "Rejected candidate.",
                    "scores": {},
                    "decision": "REJECT",
                }
            ]
        }
    ]
    handlers._path = lambda _: tmp_path / "source.mp4"

    with patch("clipping_farm.media.FFmpegMedia") as media_class:
        result = handlers.produce_clips(
            {"payload": {"source_id": "test-source"}}
        )

    media_class.return_value.cut.assert_not_called()
    assert result["clips"] == []
