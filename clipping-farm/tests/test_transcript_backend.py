import sys
from types import SimpleNamespace

import clipping_farm.transcript as transcript


def test_apple_silicon_defaults_to_real_mlx_transcription(monkeypatch):
    factory = getattr(transcript, "build_transcriber", None)
    assert callable(factory)
    monkeypatch.delenv("CLIP_FARM_TRANSCRIBER", raising=False)
    monkeypatch.setattr("clipping_farm.transcript.platform.system", lambda: "Darwin")
    monkeypatch.setattr("clipping_farm.transcript.platform.machine", lambda: "arm64")

    transcriber = factory()

    assert isinstance(transcriber, transcript.MLXWhisperTranscriber)
    assert transcriber.model_name == "mlx-community/whisper-small-mlx"


def test_fixture_transcriber_requires_explicit_configuration(monkeypatch):
    factory = getattr(transcript, "build_transcriber", None)
    assert callable(factory)
    monkeypatch.setenv("CLIP_FARM_TRANSCRIBER", "fixture")

    assert isinstance(factory(), transcript.FixtureTranscriber)


def test_mlx_transcriber_converts_real_segment_response(monkeypatch, tmp_path):
    transcriber_class = getattr(transcript, "MLXWhisperTranscriber", None)
    assert transcriber_class is not None
    audio_path = tmp_path / "audio.mov"
    audio_path.write_bytes(b"not decoded by mocked adapter")
    calls = {}

    def fake_transcribe(path, **kwargs):
        calls["path"] = path
        calls.update(kwargs)
        return {
            "language": "en",
            "segments": [
                {"start": 1.25, "end": 3.5, "text": " Actual speech. "},
            ],
        }

    monkeypatch.setitem(
        sys.modules,
        "mlx_whisper",
        SimpleNamespace(transcribe=fake_transcribe),
    )
    transcriber = transcriber_class("local-model")

    result = transcriber.transcribe(audio_path)

    assert isinstance(result, transcript.Transcript)
    assert result.language == "en"
    assert [(s.start, s.end, s.text) for s in result.segments] == [
        (1.25, 3.5, "Actual speech."),
    ]
    assert calls["path"] == str(audio_path)
    assert calls["path_or_hf_repo"] == "local-model"
    assert calls["word_timestamps"] is False


def test_mlx_transcriber_drops_silence_and_repetition_hallucinations(monkeypatch, tmp_path):
    transcriber_class = getattr(transcript, "MLXWhisperTranscriber", None)
    assert transcriber_class is not None
    audio_path = tmp_path / "silence.mov"
    audio_path.write_bytes(b"audio")
    monkeypatch.setitem(
        sys.modules,
        "mlx_whisper",
        SimpleNamespace(
            transcribe=lambda *_args, **_kwargs: {
                "language": "nn",
                "segments": [
                    {
                        "start": 0,
                        "end": 30,
                        "text": "ᶠ" * 100,
                        "no_speech_prob": 0.74,
                        "compression_ratio": 12.5,
                    },
                    {
                        "start": 30,
                        "end": 60,
                        "text": "Real spoken words here.",
                        "no_speech_prob": 0.08,
                        "compression_ratio": 1.3,
                    },
                ],
            }
        ),
    )

    result = transcriber_class("local-model").transcribe(audio_path)

    assert [segment.text for segment in result.segments] == ["Real spoken words here."]
