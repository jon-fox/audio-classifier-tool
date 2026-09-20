"""Self-distilled sentence-level ad classifier.

Trains on the decision files past runs wrote to output/ (the LLM's cut/keep
verdicts label each transcript sentence), and at runtime flags suspect ranges
as an advisory signal for the LLM. No trained model = the signal is absent.
"""

import glob
import json
import os

import joblib

from audioclassifier.config.constants import (
    CLASSIFIER_MIN_RANGE_SECONDS,
    CLASSIFIER_THRESHOLD,
    FINISHED_MP3_DIR,
    TEXT_CLASSIFIER_PATH,
    USE_TEXT_CLASSIFIER,
)
from audioclassifier.logger.logger_setup import logger

_loaded = (None, False)  # (model, attempted)


def build_dataset(output_dir=FINISHED_MP3_DIR):
    """Sentences + labels from every transcript/decision pair under output_dir."""
    texts, labels = [], []
    for decision_path in glob.glob(
        os.path.join(output_dir, "**", "transcripts", "*_decision.json"),
        recursive=True,
    ):
        transcript_path = decision_path.replace("_decision.json", ".json")
        if not os.path.isfile(transcript_path):
            continue
        with open(decision_path, encoding="utf-8") as f:
            cut_ranges = json.load(f).get("cut_ranges_seconds") or []
        with open(transcript_path, encoding="utf-8") as f:
            sentences = json.load(f)
        for sentence in sentences:
            inside = any(
                start <= sentence["start"] < end for start, end in cut_ranges
            )
            texts.append(sentence["text"])
            labels.append(1 if inside else 0)
    return texts, labels


def train(output_dir=FINISHED_MP3_DIR, model_path=TEXT_CLASSIFIER_PATH):
    """Train and save the classifier; returns evaluation metrics."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import f1_score
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import make_pipeline
    from sklearn.feature_extraction.text import TfidfVectorizer

    texts, labels = build_dataset(output_dir)
    positives = sum(labels)
    if len(texts) < 200 or positives < 20:
        raise RuntimeError(
            f"Not enough training data ({len(texts)} sentences, {positives} ad "
            f"sentences); process more episodes first"
        )

    train_x, test_x, train_y, test_y = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )
    pipeline = make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True),
        LogisticRegression(class_weight="balanced", max_iter=1000),
    )
    pipeline.fit(train_x, train_y)

    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    joblib.dump(pipeline, model_path)

    global _loaded
    _loaded = (pipeline, True)

    metrics = {
        "sentences": len(texts),
        "ad_sentences": positives,
        "f1": round(f1_score(test_y, pipeline.predict(test_x)), 3),
        "model_path": model_path,
    }
    logger.info(f"Text classifier trained: {metrics}")
    return metrics


def retrain_after_run():
    """Refresh the classifier from all accumulated decisions; never raises."""
    try:
        train()
    except RuntimeError as e:
        logger.info(f"Classifier not retrained yet: {e}")
    except Exception as e:
        logger.error(f"Classifier training failed: {e}")


def _get_model():
    global _loaded
    model, attempted = _loaded
    if model is None and not attempted:
        if os.path.isfile(TEXT_CLASSIFIER_PATH):
            model = joblib.load(TEXT_CLASSIFIER_PATH)
            logger.info(f"Loaded text classifier from {TEXT_CLASSIFIER_PATH}")
        _loaded = (model, True)
    return model


def find_classifier_ranges(transcript):
    """Ranges (seconds) the trained classifier flags as ads; [] without a model.

    Consecutive suspect sentences merge into ranges (one clean sentence of
    slack); short blips are dropped.
    """
    if not USE_TEXT_CLASSIFIER:
        return []
    model = _get_model()
    if model is None or not transcript:
        return []

    probs = model.predict_proba([t.text for t in transcript])[:, 1]
    ranges = []
    current = None
    slack = 0
    for sentence, prob in zip(transcript, probs):
        if prob >= CLASSIFIER_THRESHOLD:
            if current is None:
                current = [sentence.start, sentence.end]
            else:
                current[1] = sentence.end
            slack = 0
        elif current is not None:
            slack += 1
            if slack > 1:
                ranges.append(current)
                current = None
    if current is not None:
        ranges.append(current)

    return [
        [round(start, 1), round(end, 1)]
        for start, end in ranges
        if end - start >= CLASSIFIER_MIN_RANGE_SECONDS
    ]
