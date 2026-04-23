from __future__ import annotations

import subprocess
from pathlib import Path

import av
import imageio_ffmpeg


def extract_audio_to_wav(video_path: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    command = [
        ffmpeg_path,
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(output_path),
    ]

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Khong the tach audio tu video. "
            f"ffmpeg tra ve ma loi {completed.returncode}: {completed.stderr.strip()}"
        )
    return output_path


def get_media_duration(media_path: Path) -> float | None:
    try:
        with av.open(str(media_path)) as container:
            if container.duration is None:
                return None
            return float(container.duration / av.time_base)
    except av.FFmpegError:
        return None


def safe_delete(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return
