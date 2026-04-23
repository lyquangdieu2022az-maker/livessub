from __future__ import annotations

import json
from pathlib import Path

from app.models import SubtitleLine


def _format_timestamp(seconds: float, separator: str) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, ms = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}{separator}{ms:03}"


def to_srt(segments: list[SubtitleLine]) -> str:
    blocks: list[str] = []
    for index, segment in enumerate(segments, start=1):
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{_format_timestamp(segment.start, ',')} --> {_format_timestamp(segment.end, ',')}",
                    segment.text.strip(),
                ]
            )
        )
    return "\n\n".join(blocks).strip() + "\n"


def to_vtt(segments: list[SubtitleLine]) -> str:
    blocks = ["WEBVTT\n"]
    for segment in segments:
        blocks.append(
            "\n".join(
                [
                    f"{_format_timestamp(segment.start, '.')} --> {_format_timestamp(segment.end, '.')}",
                    segment.text.strip(),
                    "",
                ]
            )
        )
    return "\n".join(blocks).strip() + "\n"


def write_text(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path.name


def write_transcript_json(path: Path, segments: list[SubtitleLine], language: str | None) -> str:
    payload = {
        "language": language,
        "segments": [
            {"start": item.start, "end": item.end, "text": item.text} for item in segments
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path.name
