from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from app.models import SubtitleLine

_MODEL: Any | None = None


@dataclass(slots=True)
class TranscriptionStream:
    language: str | None
    segments: Iterator[SubtitleLine]


def _get_model(model_size: str) -> Any:
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel

        _MODEL = WhisperModel(model_size, device="auto", compute_type="int8")
    return _MODEL


def stream_transcription(
    audio_path: Path,
    model_size: str,
    source_language: str | None,
) -> TranscriptionStream:
    model = _get_model(model_size)
    detected_segments, info = model.transcribe(
        str(audio_path),
        language=source_language or None,
        vad_filter=True,
        word_timestamps=False,
        beam_size=5,
        condition_on_previous_text=True,
    )

    def _segment_iterator() -> Iterator[SubtitleLine]:
        for segment in detected_segments:
            text = segment.text.strip()
            if not text:
                continue
            yield SubtitleLine(
                start=segment.start,
                end=segment.end,
                text=text,
            )

    return TranscriptionStream(language=info.language, segments=_segment_iterator())


def transcribe_audio(audio_path: Path, model_size: str, source_language: str | None) -> list[SubtitleLine]:
    stream = stream_transcription(audio_path, model_size, source_language)
    return list(stream.segments)
