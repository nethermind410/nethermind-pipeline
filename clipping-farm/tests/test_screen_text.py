from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from clipping_farm.agent_handlers import LocalHandlers
from clipping_farm.providers import ProviderResult
from clipping_farm.screen_text import ScreenTextAnalyzer


def test_generate_candidates_uses_screen_text_when_transcript_is_empty():
    handlers = LocalHandlers.__new__(LocalHandlers)
    handlers._deps = lambda _: [
        {"transcript": []},
        {"screen_text": [
            {"start": 0, "end": 20, "text": "Step one explains the server setup."},
            {"start": 20, "end": 40, "text": "Step two explains how to open the local page."},
        ]},
    ]

    result = handlers.generate_candidates({"depends_on": "[]"})

    assert len(result["candidates"]) == 2
    assert all(c["decision"] == "REVIEW" for c in result["candidates"])
    assert all(c["source_modality"] == "screen_ocr" for c in result["candidates"])


def test_screen_ocr_candidate_cannot_be_auto_accepted():
    handlers = LocalHandlers.__new__(LocalHandlers)
    handlers._deps = lambda j: [
        {"candidates": [{"start": 0, "end": 12, "text": "Screen text", "scores": {}, "source_modality": "screen_ocr", "decision": "REVIEW"}]},
        {"transcript": []}, {"audio": {}}, {"scenes": []}, {"metadata": {"format": {"duration": 0}}},
    ]
    handlers.brain = Mock()
    handlers.brain.analyse.return_value = SimpleNamespace(
        actual_cost=0,
        trace=[],
        result=ProviderResult("accept", 0.99, "looks good", [], {}, "mock"),
    )
    handlers.vision_adaptive = Mock()
    handlers.vision_adaptive.analyse.return_value = (None, [])
    handlers.fusion = Mock()
    handlers.fusion.analyse.return_value = SimpleNamespace(
        scores={}, confidence=0.99, decision="accept", evidence=[], missing_modalities=[]
    )

    with patch("clipping_farm.agent_handlers.build_packet", return_value=SimpleNamespace(digest=lambda: "x")), patch(
        "clipping_farm.agent_handlers.standalone_evidence", return_value=[]
    ):
        result = handlers.score_candidates({"id": "j", "budget": 0, "payload": {"source_id": "s"}})

    assert result["candidates"][0]["decision"] == "REVIEW"


def test_screen_text_stage_skips_ocr_when_transcript_has_text():
    handlers = LocalHandlers.__new__(LocalHandlers)
    handlers._deps = lambda j: [
        {"metadata": {"format": {"duration": 30}}},
        {"transcript": [{"start": 0, "end": 10, "text": "Spoken narration"}]},
    ]
    handlers.frames = Mock()
    handlers.screen_text = Mock()

    result = handlers.analyse_screen_text({"payload": {"source_id": "s"}})

    assert result["status"] == "skipped_speech_transcript_available"
    handlers.frames.sample.assert_not_called()
    handlers.screen_text.detect.assert_not_called()


def test_screen_text_stage_uses_ocr_fallback_when_transcript_is_empty():
    handlers = LocalHandlers.__new__(LocalHandlers)
    handlers._deps = lambda j: [
        {"metadata": {"format": {"duration": 30}}},
        {"transcript": []},
    ]
    handlers.frames = Mock()
    frames = [{"time": 0, "path": "frame.jpg"}]
    handlers.frames.sample.return_value = frames
    segment = {"start": 0, "end": 30, "text": "A changed tutorial screen"}
    handlers.screen_text = Mock()
    handlers.screen_text.detect.return_value = [segment]

    with patch.object(handlers, "_path", return_value="source.mp4"):
        result = handlers.analyse_screen_text({"payload": {"source_id": "s"}})

    assert result["screen_text"] == [segment]
    assert result["status"] == "changes_detected"
    handlers.frames.sample.assert_called_once_with(
        "s", "source.mp4", 30.0, count=11, start=0.0, end=30.0
    )


def test_static_screen_does_not_generate_candidate(tmp_path):
    frames = [{"time": 0, "path": str(tmp_path / "0.jpg")}, {"time": 12, "path": str(tmp_path / "12.jpg")}, {"time": 24, "path": str(tmp_path / "24.jpg")}]
    for frame in frames:
        (tmp_path / Path(frame["path"]).name).write_bytes(b"fixture")

    analyzer = ScreenTextAnalyzer(ocr=lambda path: "same tutorial page")

    assert analyzer.detect(frames, duration=30) == []


def test_ocr_punctuation_noise_does_not_create_a_screen_change():
    base = "Tutorial explains server setup browser requests local terminal instructions"
    noisy = base + " " + ("- " * 24)
    frames = [{"time": 0, "path": "first"}, {"time": 10, "path": "second"}]
    text_by_path = {"first": base, "second": noisy}

    segments = ScreenTextAnalyzer(ocr=text_by_path.__getitem__).detect(frames, duration=20)

    assert segments == []


def test_screen_text_change_creates_review_only_segment_candidates(tmp_path):
    from pathlib import Path

    frames = []
    texts = ["Step one: start the server", "Step one: start the server", "Step two: open the browser", "Step two: open the browser"]
    for index, text in enumerate(texts):
        image = tmp_path / f"{index}.jpg"
        image.write_bytes(text.encode())
        frames.append({"time": index * 10, "path": str(image)})
    analyzer = ScreenTextAnalyzer(ocr=lambda path: Path(path).read_text())

    candidates = analyzer.candidates(frames, duration=40)

    assert len(candidates) == 2
    assert [(c.start, c.end) for c in candidates] == [(0, 20), (20, 40)]
    assert all(c.decision == "REVIEW" for c in candidates)
    assert all(c.source_modality == "screen_ocr" for c in candidates)
