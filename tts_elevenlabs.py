"""
tts_elevenlabs.py — narration backend for make_short.py, backed by ElevenLabs.

Produces the same shape make_short.py's timeline builder expects from any TTS
backend: an MP3 file per segment, plus word-level timings
    [{"word": str, "start": seconds, "end": seconds}, ...]

Needs in .env (see .env.example):
    ELEVENLABS_API_KEY   your ElevenLabs API key
    ELEVENLABS_VOICE_ID  the voice to narrate with (Voices tab in the ElevenLabs
                          dashboard -> copy the voice's ID)
"""
import os
from dotenv import load_dotenv
from elevenlabs import ElevenLabs

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

MODEL_ID = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
_client = None


def _client_lazy():
    global _client
    if _client is None:
        _client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    return _client


def _words_from_alignment(align):
    """Character-level ElevenLabs alignment -> word-level {word,start,end} list."""
    words, buf, w_start, prev_end = [], "", None, 0.0
    for ch, s, e in zip(align.characters, align.character_start_times_seconds,
                         align.character_end_times_seconds):
        if ch.isspace():
            if buf:
                words.append({"word": buf, "start": w_start, "end": prev_end})
                buf, w_start = "", None
        else:
            if w_start is None:
                w_start = s
            buf += ch
            prev_end = e
    if buf:
        words.append({"word": buf, "start": w_start, "end": prev_end})
    return words


def synthesize(text, mp3_path, voice_id=None):
    """Write narration MP3 to mp3_path, return word-level timings."""
    import base64
    resp = _client_lazy().text_to_speech.convert_with_timestamps(
        voice_id=voice_id or os.environ["ELEVENLABS_VOICE_ID"],
        model_id=MODEL_ID,
        text=text,
        output_format="mp3_44100_128",
    )
    with open(mp3_path, "wb") as f:
        f.write(base64.b64decode(resp.audio_base_64))
    return _words_from_alignment(resp.alignment)
