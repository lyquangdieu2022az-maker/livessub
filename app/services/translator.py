from __future__ import annotations

import json
from dataclasses import dataclass, field

from openai import OpenAI
from pydantic import BaseModel

from app.models import SubtitleLine


class TranslatedSubtitle(BaseModel):
    index: int
    text: str


class TranslationBatch(BaseModel):
    items: list[TranslatedSubtitle]


@dataclass(slots=True)
class SubtitleTranslator:
    api_key: str
    model: str
    client: OpenAI = field(init=False)

    def __post_init__(self) -> None:
        self.client = OpenAI(api_key=self.api_key)

    def translate(self, segments: list[SubtitleLine], target_language: str, source_language: str | None) -> list[SubtitleLine]:
        if not segments:
            return []

        translated_lines: list[SubtitleLine] = []
        for batch in _chunk_segments(segments):
            batch_payload = [
                {"index": index, "text": segment.text}
                for index, segment in enumerate(batch)
            ]
            response = self.client.responses.parse(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You are a professional subtitle translator. "
                            "Translate each subtitle line into the requested target language. "
                            "Preserve the meaning, keep lines concise for subtitles, "
                            "do not merge lines, do not split lines, and keep the item count identical."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Source language: {source_language or 'auto-detected'}\n"
                            f"Target language: {target_language}\n"
                            "Return JSON only.\n"
                            f"Items:\n{json.dumps(batch_payload, ensure_ascii=False)}"
                        ),
                    },
                ],
                text_format=TranslationBatch,
            )
            parsed = response.output_parsed
            if parsed is None or len(parsed.items) != len(batch):
                raise RuntimeError("Mo hinh tra ve so dong dich khong khop voi so dong phu de goc.")

            translated_lines.extend(
                SubtitleLine(
                    start=segment.start,
                    end=segment.end,
                    text=item.text.strip(),
                )
                for segment, item in zip(batch, parsed.items, strict=True)
            )

        return translated_lines


def _chunk_segments(segments: list[SubtitleLine], max_items: int = 20, max_chars: int = 2500) -> list[list[SubtitleLine]]:
    chunks: list[list[SubtitleLine]] = []
    current: list[SubtitleLine] = []
    current_chars = 0

    for segment in segments:
        segment_chars = len(segment.text)
        if current and (len(current) >= max_items or current_chars + segment_chars > max_chars):
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(segment)
        current_chars += segment_chars

    if current:
        chunks.append(current)

    return chunks
