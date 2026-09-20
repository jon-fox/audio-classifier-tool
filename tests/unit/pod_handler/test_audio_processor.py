from types import SimpleNamespace

import numpy as np
import soundfile as sf

from audioclassifier.pod_handler.audio_processor import (
    _cut_ranges,
    _join_with_crossfade,
    _snap_to_transcript,
    has_ad_keywords,
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


def test_snap_to_transcript_edges():
    transcript = [SimpleNamespace(start=s, end=s + 4.0, text="w") for s in range(0, 600, 5)]
    assert _snap_to_transcript([[61.8, 118.3]], transcript) == [[60, 119.0]]


def test_keyword_gate():
    assert has_ad_keywords([SimpleNamespace(text="use code PODCAST at checkout")], [])
    assert not has_ad_keywords([SimpleNamespace(text="we discussed philosophy")], [])
    assert has_ad_keywords([SimpleNamespace(text="thanks to acme corp")], ["acme"])


def test_mp3_roundtrip(tmp_path):
    audio = (np.sin(np.linspace(0, 3000, 30 * 44100)) * 8000).astype(np.int16)
    path = tmp_path / "test.mp3"
    sf.write(path, audio.astype(np.float32) / 32768.0, 44100)
    back, sr = sf.read(path, dtype="int16", always_2d=True)
    assert sr == 44100
    assert abs(len(back) / sr - 30) < 0.1
