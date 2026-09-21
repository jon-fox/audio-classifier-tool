import json

import audioclassifier.config.detection_config as dc
from audioclassifier.processing.manifest import (
    episode_segments,
    model_version,
    read_manifest,
    write_manifest,
)


def test_segments_are_episode_absolute_ms():
    segments, gaps = episode_segments(
        [
            {"length_sec": 600.0, "cut_ranges": [[10.0, 40.5]], "confidence": 90},
            {"length_sec": 600.0, "cut_ranges": [[5.0, 25.0]], "confidence": 80},
        ]
    )
    assert segments == [
        {"start_ms": 10000, "end_ms": 40500, "confidence": 90, "kind": "ad"},
        {"start_ms": 605000, "end_ms": 625000, "confidence": 80, "kind": "ad"},
    ]
    assert gaps == []


def test_ranges_touching_a_chunk_boundary_merge():
    segments, _ = episode_segments(
        [
            {"length_sec": 600.0, "cut_ranges": [[570.0, 600.0]], "confidence": 70},
            {"length_sec": 300.0, "cut_ranges": [[0.0, 20.0]], "confidence": 95},
        ]
    )
    assert segments == [
        {"start_ms": 570000, "end_ms": 620000, "confidence": 95, "kind": "ad"}
    ]


def test_overshooting_whisper_end_times_are_clamped():
    segments, _ = episode_segments(
        [
            # whisper end-time overshoot past the 600s chunk edge
            {"length_sec": 600.0, "cut_ranges": [[580.0, 601.76]], "confidence": 88},
            # final, shorter chunk: clamp to its real length
            {"length_sec": 100.0, "cut_ranges": [[80.0, 130.0]], "confidence": 88},
        ]
    )
    assert segments[0]["end_ms"] == 600000
    assert segments[1]["end_ms"] == 700000


def test_failed_chunk_becomes_analysis_gap():
    segments, gaps = episode_segments(
        [
            {"length_sec": 600.0, "cut_ranges": [[10.0, 40.0]], "confidence": 90},
            {"length_sec": 450.0, "cut_ranges": None, "confidence": None},
        ]
    )
    assert len(segments) == 1
    assert gaps == [{"start_ms": 600000, "end_ms": 1050000}]


def test_empty_and_inverted_ranges_dropped():
    segments, _ = episode_segments(
        [
            {
                "length_sec": 600.0,
                "cut_ranges": [[50.0, 50.0], [-5.0, -1.0]],
                "confidence": 90,
            }
        ]
    )
    assert segments == []


def test_manifest_roundtrip(tmp_path):
    dc.set_detection_config("examples/configs/ads.toon")
    try:
        audio = {
            "source_url": "https://example.com/ep.mp3",
            "duration_sec": 4460.2,
            "bytes": 71314458,
            "sha256": "abc123",
            "etag": None,
        }
        segments = [{"start_ms": 0, "end_ms": 28200, "confidence": 100, "kind": "ad"}]
        written = write_manifest(str(tmp_path), audio, segments, 451.23)

        assert written["version"] == 1
        assert written["model_version"] == model_version()
        assert "config-" in written["model_version"]
        assert written["seconds_removed"] == 451.2
        assert written["created_at"].endswith("Z")
        assert "analysis_gaps" not in written

        assert read_manifest(str(tmp_path)) == json.loads(json.dumps(written))
        assert read_manifest(str(tmp_path / "missing")) is None
    finally:
        dc._config = None


def test_manifest_records_analysis_gaps(tmp_path):
    dc.set_detection_config("examples/configs/ads.toon")
    try:
        gaps = [{"start_ms": 600000, "end_ms": 1200000}]
        written = write_manifest(str(tmp_path), {}, [], 0, analysis_gaps=gaps)
        assert written["analysis_gaps"] == gaps
    finally:
        dc._config = None
