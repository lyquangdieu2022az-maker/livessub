from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(slots=True)
class SubtitleLine:
    start: float
    end: float
    text: str


@dataclass(slots=True)
class JobRecord:
    id: str
    filename: str
    target_language: str
    source_language: str | None
    translate: bool
    status: str = "queued"
    progress: int = 0
    message: str = "Dang cho xu ly"
    detected_language: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    total_duration: float | None = None
    translated_segment_count: int = 0
    media_deleted: bool = False
    original_srt: str | None = None
    translated_srt: str | None = None
    original_vtt: str | None = None
    translated_vtt: str | None = None
    transcript_json: str | None = None
    error: str | None = None
    original_segments: list[SubtitleLine] = field(default_factory=list)
    translated_segments: list[SubtitleLine] = field(default_factory=list)
