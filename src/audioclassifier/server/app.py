"""FastAPI wrapper: enqueue episode analysis, serve segment manifests.

Run with the `server` extra installed:
    uvicorn audioclassifier.server.app:app --host 0.0.0.0

Env: API_TOKEN (required, bearer auth), the usual pipeline vars
(OPENAI_API_KEY, DETECTION_CONFIG, ...), and optional STORAGE
(s3://bucket/prefix) to upload outputs and serve filtered_audio_url.
"""

import json
import os
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from pydantic import BaseModel

from audioclassifier import process_audio
from audioclassifier.config.constants import FINISHED_MP3_DIR
from audioclassifier.logger.logger_setup import configure_logging, logger
from audioclassifier.processing import manifest
from audioclassifier.util import sanitize_name

STATUS_FILENAME = "status.json"

# process_audio is blocking and the whisper model pool is process-global, so
# jobs run one at a time; everything else queues
_executor = ThreadPoolExecutor(max_workers=1)
_active = set()  # episode dirs queued or running in this process
_active_lock = threading.Lock()


@asynccontextmanager
async def _lifespan(app):
    configure_logging(stream=True)
    yield


app = FastAPI(title="audioclassifier", lifespan=_lifespan)

_bearer = HTTPBearer(auto_error=False)


def _require_token(credentials=Depends(_bearer)):
    token = os.getenv("API_TOKEN")
    if not token:
        raise HTTPException(status_code=503, detail="API_TOKEN is not configured")
    if credentials is None or not secrets.compare_digest(
        credentials.credentials, token
    ):
        raise HTTPException(status_code=401, detail="Invalid or missing bearer token")


class AnalyzeRequest(BaseModel):
    episode_id: str
    source: str
    audio_url: str
    duration_sec: float | None = None
    description: str | None = None


def _episode_dir(source, episode_id):
    return os.path.join(
        FINISHED_MP3_DIR, sanitize_name(source), sanitize_name(episode_id)
    )


def _find_episode_dir(episode_id):
    episode = sanitize_name(episode_id)
    if not os.path.isdir(FINISHED_MP3_DIR):
        return None
    for source in sorted(os.listdir(FINISHED_MP3_DIR)):
        candidate = os.path.join(FINISHED_MP3_DIR, source, episode)
        if os.path.isdir(candidate):
            return candidate
    return None


def _read_status(episode_dir):
    try:
        with open(os.path.join(episode_dir, STATUS_FILENAME), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _progress(episode_dir):
    """Fraction of analysis chunks finished, from the per-chunk decision files the
    pipeline writes as it works. Needs duration_sec from the analyze request to know
    the expected chunk count; capped below 1.0 because cutting/encoding follows."""
    status = _read_status(episode_dir) or {}
    duration = status.get("duration_sec")
    if not duration:
        return None
    expected = max(int(duration // 600) + 1, 1)
    transcripts_dir = os.path.join(episode_dir, "transcripts")
    try:
        done = len([f for f in os.listdir(transcripts_dir) if f.endswith("_decision.json")])
    except OSError:
        done = 0
    return round(min(done / expected, 0.95), 2)


def _processing_response(episode_dir):
    content = {"status": "processing"}
    progress = _progress(episode_dir)
    if progress is not None:
        content["progress"] = progress
    return content


def _write_status(episode_dir, status, **extra):
    os.makedirs(episode_dir, exist_ok=True)
    with open(os.path.join(episode_dir, STATUS_FILENAME), "w", encoding="utf-8") as f:
        json.dump({"status": status, **extra}, f, indent=2)


def _model_version():
    try:
        return manifest.model_version()
    except RuntimeError as e:  # no detection config selected
        raise HTTPException(status_code=503, detail=str(e))


def _done_response(episode_dir, data):
    response = {"status": "done", **data}
    status = _read_status(episode_dir) or {}
    if status.get("filtered_audio_url"):
        response["filtered_audio_url"] = status["filtered_audio_url"]
    return response


def _run_job(request, episode_dir):
    try:
        result = process_audio(
            source=request.source,
            name=request.episode_id,
            audio_url=request.audio_url,
            description=request.description,
            storage=os.getenv("STORAGE"),
        )
        filtered_audio_url = next(
            (u for u in result.get("uploaded", []) if u.endswith("_filtered.mp3")),
            None,
        )
        _write_status(episode_dir, "done", filtered_audio_url=filtered_audio_url)
    except Exception as e:
        logger.error(f"Analysis failed for {episode_dir}: {e}")
        _write_status(episode_dir, "failed", error=str(e))
    finally:
        with _active_lock:
            _active.discard(episode_dir)


@app.post("/v1/episodes/analyze", dependencies=[Depends(_require_token)])
def analyze(request: AnalyzeRequest):
    episode_dir = _episode_dir(request.source, request.episode_id)
    data = manifest.read_manifest(episode_dir)
    # Idempotent: a manifest from the current classifier setup is served as-is;
    # a stale model_version re-enqueues
    if data and data.get("model_version") == _model_version():
        return _done_response(episode_dir, data)

    with _active_lock:
        if episode_dir in _active:
            return JSONResponse(status_code=202, content=_processing_response(episode_dir))
        _active.add(episode_dir)
    _write_status(episode_dir, "processing", duration_sec=request.duration_sec)
    _executor.submit(_run_job, request, episode_dir)
    return JSONResponse(status_code=202, content=_processing_response(episode_dir))


@app.get("/v1/episodes/{episode_id}/segments", dependencies=[Depends(_require_token)])
def get_segments(episode_id: str):
    episode_dir = _find_episode_dir(episode_id)
    if episode_dir is None:
        raise HTTPException(status_code=404, detail="Unknown episode")

    data = manifest.read_manifest(episode_dir)
    status = _read_status(episode_dir) or {}
    if data and data.get("model_version") == _model_version():
        return _done_response(episode_dir, data)
    if status.get("status") == "processing":
        return _processing_response(episode_dir)
    if data:  # stale manifest; the client invalidates via model_version
        return _done_response(episode_dir, data)
    if status.get("status") == "failed":
        return {"status": "failed", "error": status.get("error")}
    return {"status": "processing"}
