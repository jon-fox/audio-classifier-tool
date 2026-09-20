from types import SimpleNamespace

import numpy as np
import soundfile as sf

from audioclassifier.processing.audio_processor import (
    _cut_ranges,
    _join_with_crossfade,
    _snap_cut_ranges,
    find_audio_boundaries,
    find_keyword_hits,
)

SR = 1000


def test_cut_ranges_removes_only_targets():
    audio = np.arange(60 * SR, dtype=np.int16).reshape(-1, 1)
    out = _cut_ranges(audio, [[10, 20], [40, 50]], SR)
    assert abs(len(out) / SR - 40) < 0.1
    # sample just after the first join comes from the post-cut region
    assert out[10 * SR + 100, 0] > 20 * SR - 200


def test_crossfade_join_length_and_dtype():
    a = np.full((500, 1), 1000, dtype=np.int16)
    b = np.full((500, 1), -1000, dtype=np.int16)
    out = _join_with_crossfade(a, b, 100)
    assert out.dtype == np.int16
    assert len(out) == 900


def test_snap_prefers_audio_boundaries_then_transcript_edges():
    transcript = [SimpleNamespace(start=s, end=s + 4.0, text="w") for s in range(0, 600, 5)]
    # start snaps to the nearby audio boundary; end (no boundary near) to a transcript edge
    assert _snap_cut_ranges([[61.8, 118.3]], transcript, [60.5]) == [[60.5, 119.0]]
    # no boundaries at all: transcript edges only
    assert _snap_cut_ranges([[61.8, 118.3]], transcript, []) == [[60, 119.0]]


def test_find_keyword_hits():
    import audioclassifier.config.detection_config as dc

    dc.set_detection_config("examples/configs/ads.toon")
    try:
        transcript = [
            SimpleNamespace(start=10.0, text="use code PODCAST at checkout"),
            SimpleNamespace(start=20.0, text="we discussed philosophy"),
            SimpleNamespace(start=30.0, text="thanks to acme corp"),
        ]
        assert find_keyword_hits(transcript, ["acme"]) == [10.0, 30.0]
        assert find_keyword_hits(transcript[1:2], []) == []
    finally:
        dc._config = None


def test_find_audio_boundaries_flags_silence_and_loudness_shift():
    sr = 8000
    quiet = (np.random.default_rng(0).normal(0, 300, 30 * sr)).astype(np.int16)
    silence = np.zeros(2 * sr, dtype=np.int16)
    loud = (np.random.default_rng(1).normal(0, 8000, 20 * sr)).astype(np.int16)
    audio = np.concatenate([quiet, silence, loud, silence, quiet]).reshape(-1, 1)

    boundaries = find_audio_boundaries(audio, sr)
    # transitions at ~30s, ~32s, ~52s, ~54s
    for expected in (30, 32, 52, 54):
        assert any(abs(b - expected) <= 2.5 for b in boundaries), (expected, boundaries)


def test_find_audio_boundaries_quiet_on_steady_audio():
    sr = 8000
    steady = (np.random.default_rng(2).normal(0, 3000, 60 * sr)).astype(np.int16)
    assert find_audio_boundaries(steady.reshape(-1, 1), sr) == []


def test_mp3_roundtrip(tmp_path):
    audio = (np.sin(np.linspace(0, 3000, 30 * 44100)) * 8000).astype(np.int16)
    path = tmp_path / "test.mp3"
    sf.write(path, audio.astype(np.float32) / 32768.0, 44100)
    back, sr = sf.read(path, dtype="int16", always_2d=True)
    assert sr == 44100
    assert abs(len(back) / sr - 30) < 0.1
