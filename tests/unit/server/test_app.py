import json
import os

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import audioclassifier.server.app as server
from audioclassifier.processing import manifest


class InlineExecutor:
    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)


AUTH = {"Authorization": "Bearer sekret"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "sekret")
    monkeypatch.setattr(server, "FINISHED_MP3_DIR", str(tmp_path))
    monkeypatch.setattr(server, "_executor", InlineExecutor())
    monkeypatch.setattr(server, "_active", set())
    monkeypatch.setattr(manifest, "model_version", lambda: "model-v1")
    return TestClient(server.app)


def episode_dir(tmp_path, source="My_Show", episode="ep-1"):
    path = tmp_path / source / episode
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_manifest_file(path, model_version="model-v1"):
    data = {
        "version": 1,
        "model_version": model_version,
        "audio": {"duration_sec": 100.0},
        "segments": [{"start_ms": 0, "end_ms": 20000, "confidence": 90, "kind": "ad"}],
        "seconds_removed": 20.0,
        "created_at": "2026-09-20T00:00:00Z",
    }
    (path / "segments.json").write_text(json.dumps(data))
    return data


def analyze_body(episode="ep-1"):
    return {
        "episode_id": episode,
        "source": "My Show",
        "audio_url": "https://example.com/ep.mp3",
        "duration_sec": 100.0,
    }


def test_rejects_missing_and_wrong_token(client):
    assert client.get("/v1/episodes/x/segments").status_code == 401
    response = client.get(
        "/v1/episodes/x/segments", headers={"Authorization": "Bearer nope"}
    )
    assert response.status_code == 401


def test_unconfigured_token_is_503(tmp_path, monkeypatch):
    monkeypatch.delenv("API_TOKEN", raising=False)
    response = TestClient(server.app).get("/v1/episodes/x/segments", headers=AUTH)
    assert response.status_code == 503


def test_analyze_returns_cached_manifest(client, tmp_path):
    data = write_manifest_file(episode_dir(tmp_path))
    response = client.post("/v1/episodes/analyze", json=analyze_body(), headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["segments"] == data["segments"]


def test_analyze_enqueues_and_get_reports_done(client, tmp_path, monkeypatch):
    def fake_process_audio(source, name, audio_url, description=None, storage=None):
        write_manifest_file(episode_dir(tmp_path, episode=name))
        return {"uploaded": [f"s3://bucket/{name}_filtered.mp3"]}

    monkeypatch.setattr(server, "process_audio", fake_process_audio)
    monkeypatch.setenv("STORAGE", "s3://bucket")

    response = client.post("/v1/episodes/analyze", json=analyze_body(), headers=AUTH)
    assert response.status_code == 202
    assert response.json() == {"status": "processing"}

    response = client.get("/v1/episodes/ep-1/segments", headers=AUTH)
    body = response.json()
    assert body["status"] == "done"
    assert body["filtered_audio_url"] == "s3://bucket/ep-1_filtered.mp3"


def test_stale_model_version_reenqueues(client, tmp_path, monkeypatch):
    write_manifest_file(episode_dir(tmp_path), model_version="model-v0")
    calls = []
    monkeypatch.setattr(
        server, "process_audio", lambda **kw: calls.append(kw) or {"uploaded": []}
    )

    response = client.post("/v1/episodes/analyze", json=analyze_body(), headers=AUTH)
    assert response.status_code == 202
    assert len(calls) == 1


def test_already_running_returns_processing(client, tmp_path):
    server._active.add(str(tmp_path / "My_Show" / "ep-1"))
    response = client.post("/v1/episodes/analyze", json=analyze_body(), headers=AUTH)
    assert response.status_code == 202
    assert response.json() == {"status": "processing"}


def test_failed_job_reports_failed(client, tmp_path, monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("download exploded")

    monkeypatch.setattr(server, "process_audio", boom)
    client.post("/v1/episodes/analyze", json=analyze_body(), headers=AUTH)

    body = client.get("/v1/episodes/ep-1/segments", headers=AUTH).json()
    assert body["status"] == "failed"
    assert "download exploded" in body["error"]
    # a failed episode can be re-enqueued
    assert str(tmp_path / "My_Show" / "ep-1") not in server._active


def test_unknown_episode_is_404(client):
    assert client.get("/v1/episodes/nope/segments", headers=AUTH).status_code == 404


def test_queued_episode_reports_processing(client, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "process_audio", lambda **kw: {"uploaded": []})
    client.post("/v1/episodes/analyze", json=analyze_body(), headers=AUTH)
    # job "ran" but wrote no manifest; status.json says done with no url
    body = client.get("/v1/episodes/ep-1/segments", headers=AUTH).json()
    assert body["status"] == "processing"
