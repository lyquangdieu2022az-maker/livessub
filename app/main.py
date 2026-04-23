from __future__ import annotations

import shutil
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.models import JobRecord, SubtitleLine
from app.services.media import extract_audio_to_wav, get_media_duration, safe_delete
from app.services.subtitles import to_srt, to_vtt, write_text, write_transcript_json
from app.services.transcriber import stream_transcription
from app.services.translator import SubtitleTranslator

app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

JOBS: dict[str, JobRecord] = {}
JOBS_LOCK = threading.Lock()


@app.on_event("startup")
def ensure_directories() -> None:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)


@app.get("/")
def home() -> FileResponse:
    return FileResponse("app/static/index.html")


@app.get("/api/health")
def healthcheck() -> JSONResponse:
    return JSONResponse({"ok": True, "service": settings.app_name})


@app.post("/api/jobs")
async def create_job(
    file: UploadFile = File(...),
    target_language: str = Form("Vietnamese"),
    source_language: str = Form(""),
    translate: bool = Form(True),
) -> JSONResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Ban can chon mot video de bat dau.")

    job_id = uuid.uuid4().hex[:12]
    safe_filename = Path(file.filename).name
    upload_path = settings.upload_dir / f"{job_id}_{safe_filename}"

    with upload_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    job = JobRecord(
        id=job_id,
        filename=safe_filename,
        target_language=target_language.strip() or "Vietnamese",
        source_language=source_language.strip() or None,
        translate=translate,
    )
    with JOBS_LOCK:
        JOBS[job_id] = job

    worker = threading.Thread(
        target=process_job,
        args=(job_id, upload_path),
        daemon=True,
    )
    worker.start()

    return JSONResponse(
        {
            "job_id": job_id,
            "message": "Video dang phat tren may cua ban. He thong dang tao phu de tieng Viet o nen.",
        }
    )


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> JSONResponse:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Khong tim thay job.")

    payload = {
        "id": job.id,
        "filename": job.filename,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "target_language": job.target_language,
        "source_language": job.source_language,
        "detected_language": job.detected_language,
        "translate": job.translate,
        "total_duration": job.total_duration,
        "translated_segment_count": job.translated_segment_count,
        "media_deleted": job.media_deleted,
        "outputs": {
            "original_srt": job.original_srt,
            "translated_srt": job.translated_srt,
            "original_vtt": job.original_vtt,
            "translated_vtt": job.translated_vtt,
            "transcript_json": job.transcript_json,
        },
        "error": job.error,
    }
    return JSONResponse(payload)


@app.get("/api/jobs/{job_id}/segments")
def get_segments(
    job_id: str,
    from_index: int = Query(0, ge=0),
) -> JSONResponse:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Khong tim thay job.")

        segments = job.translated_segments[from_index:]
        next_index = len(job.translated_segments)
        detected_language = job.detected_language
        status = job.status

    return JSONResponse(
        {
            "job_id": job_id,
            "segments": [_serialize_segment(item) for item in segments],
            "next_index": next_index,
            "status": status,
            "detected_language": detected_language,
        }
    )


@app.get("/download/{job_id}/{filename}")
def download_output(job_id: str, filename: str) -> FileResponse:
    path = settings.output_dir / job_id / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Khong tim thay tep dau ra.")
    return FileResponse(path)


def process_job(job_id: str, upload_path: Path) -> None:
    job_dir = settings.output_dir / job_id
    audio_path = job_dir / "audio.wav"
    original_srt_path = job_dir / "original.srt"
    original_vtt_path = job_dir / "original.vtt"
    translated_srt_path = job_dir / "translated.srt"
    translated_vtt_path = job_dir / "translated.vtt"
    transcript_json_path = job_dir / "transcript.json"
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        duration = get_media_duration(upload_path)
        _update_job(
            job_id,
            status="processing",
            progress=6,
            total_duration=duration,
            message="Dang tao audio tam tu video. Tep video se duoc xoa sau buoc nay.",
        )
        extract_audio_to_wav(upload_path, audio_path)

        job = _get_job(job_id)
        stream = stream_transcription(
            audio_path=audio_path,
            model_size=settings.whisper_model_size,
            source_language=job.source_language,
        )
        _update_job(
            job_id,
            progress=16,
            detected_language=stream.language,
            message="Da bat dau nghe video va tao subtitle tieng Viet theo tung doan.",
        )

        translate_needed = job.translate and not _language_matches(
            job.target_language,
            stream.language,
        )
        if translate_needed and not settings.openai_api_key:
            raise RuntimeError(
                "Can OPENAI_API_KEY de dich subtitle sang tieng Viet trong che do browser live."
            )

        translator = (
            SubtitleTranslator(
                api_key=settings.openai_api_key,
                model=settings.translation_model,
            )
            if translate_needed and settings.openai_api_key
            else None
        )

        pending_batch: list[SubtitleLine] = []
        processed_segments = 0
        for segment in stream.segments:
            processed_segments += 1
            _append_original_segment(job_id, segment)
            pending_batch.append(segment)

            _update_job(
                job_id,
                progress=_progress_from_segment(segment.end, duration),
                message=_processing_message(
                    segment.end,
                    duration,
                    stream.language,
                ),
            )

            if _should_flush_batch(pending_batch):
                _flush_translated_batch(
                    job_id=job_id,
                    batch=pending_batch,
                    translator=translator,
                    target_language=job.target_language,
                    source_language=stream.language,
                )
                pending_batch = []

        if pending_batch:
            _flush_translated_batch(
                job_id=job_id,
                batch=pending_batch,
                translator=translator,
                target_language=job.target_language,
                source_language=stream.language,
            )

        job = _get_job(job_id)
        translated_segments = job.translated_segments or [
            SubtitleLine(start=item.start, end=item.end, text=item.text)
            for item in job.original_segments
        ]

        write_text(original_srt_path, to_srt(job.original_segments))
        write_text(original_vtt_path, to_vtt(job.original_segments))
        write_text(translated_srt_path, to_srt(translated_segments))
        write_text(translated_vtt_path, to_vtt(translated_segments))
        write_transcript_json(
            transcript_json_path,
            translated_segments,
            job.target_language if job.translate else stream.language,
        )

        message = "Hoan tat. Player da co the hien subtitle tieng Viet."
        if processed_segments == 0:
            message = "Khong phat hien loi noi ro rang. Da xuat file subtitle trong de ban kiem tra lai."

        _update_job(
            job_id,
            status="completed",
            progress=100,
            message=message,
            original_srt=original_srt_path.name,
            original_vtt=original_vtt_path.name,
            translated_srt=translated_srt_path.name,
            translated_vtt=translated_vtt_path.name,
            transcript_json=transcript_json_path.name,
        )
    except Exception as exc:  # noqa: BLE001
        _update_job(
            job_id,
            status="failed",
            progress=100,
            message="Khong the tao subtitle tieng Viet cho video nay.",
            error=str(exc),
        )
    finally:
        safe_delete(upload_path)
        safe_delete(audio_path)
        _update_job(job_id, media_deleted=True)


def _get_job(job_id: str) -> JobRecord:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise RuntimeError("Job khong ton tai.")
    return job


def _update_job(job_id: str, **changes: object) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        for key, value in changes.items():
            setattr(job, key, value)


def _append_original_segment(job_id: str, segment: SubtitleLine) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
        job.original_segments.append(segment)


def _append_translated_segments(job_id: str, segments: list[SubtitleLine]) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
        job.translated_segments.extend(segments)
        job.translated_segment_count = len(job.translated_segments)


def _flush_translated_batch(
    job_id: str,
    batch: list[SubtitleLine],
    translator: SubtitleTranslator | None,
    target_language: str,
    source_language: str | None,
) -> None:
    if translator is None:
        translated = [
            SubtitleLine(start=item.start, end=item.end, text=item.text)
            for item in batch
        ]
    else:
        translated = translator.translate(
            batch,
            target_language=target_language,
            source_language=source_language,
        )

    _append_translated_segments(job_id, translated)
    _update_job(
        job_id,
        message=f"Da san sang {len(_get_job(job_id).translated_segments)} dong subtitle de player hien ngay.",
    )


def _should_flush_batch(batch: list[SubtitleLine]) -> bool:
    if len(batch) >= 6:
        return True
    total_chars = sum(len(item.text) for item in batch)
    return total_chars >= 360


def _processing_message(
    current_seconds: float,
    duration: float | None,
    detected_language: str | None,
) -> str:
    parts = [f"Dang nghe va dich den {_format_clock(current_seconds)}."]
    if duration:
        parts.append(f"Do dai video: {_format_clock(duration)}.")
    if detected_language:
        parts.append(f"Ngon ngu nhan dien: {detected_language}.")
    parts.append("Subtitle se nhay vao player ngay khi tung doan xong.")
    return " ".join(parts)


def _progress_from_segment(current_seconds: float, duration: float | None) -> int:
    if not duration or duration <= 0:
        return 72
    ratio = min(max(current_seconds / duration, 0.0), 1.0)
    return min(92, 18 + int(ratio * 72))


def _format_clock(seconds: float) -> str:
    total_seconds = max(int(seconds), 0)
    minutes, secs = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02}:{minutes:02}:{secs:02}"
    return f"{minutes:02}:{secs:02}"


def _serialize_segment(segment: SubtitleLine) -> dict[str, float | str]:
    return {
        "start": segment.start,
        "end": segment.end,
        "text": segment.text,
    }


def _language_matches(target_language: str, detected_language: str | None) -> bool:
    if not detected_language:
        return False

    target = target_language.strip().lower()
    aliases = {
        "vi": {"vi", "vie", "vietnamese", "tieng viet"},
        "en": {"en", "eng", "english", "tieng anh"},
        "ja": {"ja", "jpn", "japanese", "tieng nhat"},
        "ko": {"ko", "kor", "korean", "tieng han"},
        "zh": {"zh", "zho", "chi", "chinese", "tieng trung"},
    }

    normalized_detected = detected_language.lower()
    for values in aliases.values():
        if normalized_detected in values and target in values:
            return True
    return normalized_detected == target
