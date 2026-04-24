from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(slots=True)
class Settings:
    app_name: str = "VietSub Live"
    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", "data/uploads"))
    output_dir: Path = Path(os.getenv("OUTPUT_DIR", "data/outputs"))
    whisper_model_size: str = os.getenv("WHISPER_MODEL_SIZE", "small")
    translation_model: str = os.getenv("SUBTITLE_TRANSLATION_MODEL", "gemini-2.5-flash")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")


settings = Settings()
