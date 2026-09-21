"""Segment manifest (segments.json): episode-absolute record of what was cut,
tied to the exact audio copy that was analyzed."""

import json
import os
from datetime import datetime, timezone

from audioclassifier.config.constants import LLM_MODEL, MODEL_SIZE
from audioclassifier.config.detection_config import get_detection_config

MANIFEST_FILENAME = "segments.json"
CHUNK_SECONDS = 600  # audio_processor's fixed 10-minute split
# An ad spanning a chunk edge shows up as two ranges touching the boundary
_BOUNDARY_MERGE_GAP_MS = 1000


def model_version():
    """Stable id of the classifier setup; clients cache segments against it."""
    return f"{LLM_MODEL}|whisper-{MODEL_SIZE}|config-{get_detection_config().name}"


def episode_segments(chunks):
    """Convert per-chunk cut ranges to episode-absolute millisecond segments.

    chunks: ordered per-chunk dicts with length_sec, confidence, and
    cut_ranges — post-snap [start, end] chunk-local seconds, or None when the
    chunk failed analysis. Returns (segments, analysis_gaps).
    """
    segments = []
    gaps = []
    for index, chunk in enumerate(chunks):
        offset_ms = index * CHUNK_SECONDS * 1000
        length_ms = round(chunk["length_sec"] * 1000)
        if chunk["cut_ranges"] is None:
            gaps.append({"start_ms": offset_ms, "end_ms": offset_ms + length_ms})
            continue
        for start, end in chunk["cut_ranges"]:
            # Whisper end-times can overshoot the chunk edge; clamp to its real length
            start_ms = offset_ms + min(max(round(start * 1000), 0), length_ms)
            end_ms = offset_ms + min(max(round(end * 1000), 0), length_ms)
            if end_ms <= start_ms:
                continue
            previous = segments[-1] if segments else None
            if previous and start_ms - previous["end_ms"] < _BOUNDARY_MERGE_GAP_MS:
                previous["end_ms"] = max(previous["end_ms"], end_ms)
                previous["confidence"] = max(
                    previous["confidence"], chunk["confidence"]
                )
            else:
                segments.append(
                    {
                        "start_ms": start_ms,
                        "end_ms": end_ms,
                        "confidence": chunk["confidence"],
                        "kind": "ad",
                    }
                )
    return segments, gaps


def write_manifest(output_dir, audio, segments, seconds_removed, analysis_gaps=None):
    data = {
        "version": 1,
        "model_version": model_version(),
        "audio": audio,
        "segments": segments,
        "seconds_removed": round(seconds_removed, 1),
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if analysis_gaps:
        data["analysis_gaps"] = analysis_gaps
    with open(os.path.join(output_dir, MANIFEST_FILENAME), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data


def read_manifest(output_dir):
    try:
        with open(os.path.join(output_dir, MANIFEST_FILENAME), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
