import json
from types import SimpleNamespace

import pytest

import audioclassifier.detection.text_classifier as tc


AD_TEXTS = [
    "use code PODCAST for twenty percent off your first order",
    "this episode is brought to you by our sponsor",
    "head to example dot com slash pod to sign up today",
    "get a free trial when you use our link",
]
CONTENT_TEXTS = [
    "so I was thinking about what you said earlier",
    "the history of this goes back decades honestly",
    "and then he told me the whole story about the trip",
    "let's get back into the main topic for today",
]


def _write_episode(root, index, n=40):
    transcripts = root / "Show" / f"Episode_{index}" / "transcripts"
    transcripts.mkdir(parents=True)
    sentences = []
    cut_ranges = [[0.0, n * 5.0 / 2]]  # first half labeled as ad
    for i in range(n):
        pool = AD_TEXTS if i < n // 2 else CONTENT_TEXTS
        sentences.append(
            {"start": i * 5.0, "end": i * 5.0 + 4.0, "text": pool[i % len(pool)]}
        )
    (transcripts / "transcript_0.json").write_text(json.dumps(sentences))
    (transcripts / "transcript_0_decision.json").write_text(
        json.dumps({"cut_ranges_seconds": cut_ranges})
    )


@pytest.fixture
def trained_model(tmp_path, monkeypatch):
    for i in range(6):
        _write_episode(tmp_path / "output", i)
    model_path = str(tmp_path / "model.joblib")
    monkeypatch.setattr(tc, "TEXT_CLASSIFIER_PATH", model_path)
    monkeypatch.setattr(tc, "USE_TEXT_CLASSIFIER", True)
    tc._loaded = (None, False)
    yield tc.train(str(tmp_path / "output"), model_path)
    tc._loaded = (None, False)


def test_train_reports_metrics(trained_model):
    assert trained_model["sentences"] == 240
    assert trained_model["ad_sentences"] == 120
    assert trained_model["f1"] > 0.8


def test_classifier_ranges_flag_ad_run(trained_model):
    transcript = [
        SimpleNamespace(start=i * 5.0, end=i * 5.0 + 4.0, text=text)
        for i, text in enumerate(AD_TEXTS * 3 + CONTENT_TEXTS * 3)
    ]
    ranges = tc.find_classifier_ranges(transcript)
    assert ranges, "expected the ad run to be flagged"
    assert ranges[0][0] == 0.0
    # the flagged range should not extend deep into the content half
    assert ranges[-1][1] <= 12 * 5.0 + 10


def test_no_model_no_ranges(monkeypatch, tmp_path):
    monkeypatch.setattr(tc, "TEXT_CLASSIFIER_PATH", str(tmp_path / "missing.joblib"))
    monkeypatch.setattr(tc, "USE_TEXT_CLASSIFIER", True)
    tc._loaded = (None, False)
    try:
        transcript = [SimpleNamespace(start=0.0, end=4.0, text="use code PODCAST")]
        assert tc.find_classifier_ranges(transcript) == []
    finally:
        tc._loaded = (None, False)


def test_disabled_by_default(trained_model, monkeypatch):
    monkeypatch.setattr(tc, "USE_TEXT_CLASSIFIER", False)
    transcript = [SimpleNamespace(start=0.0, end=4.0, text=AD_TEXTS[0])]
    assert tc.find_classifier_ranges(transcript) == []


def test_insufficient_data_raises(tmp_path):
    with pytest.raises(RuntimeError, match="Not enough training data"):
        tc.train(str(tmp_path), str(tmp_path / "model.joblib"))
