import json

from audioclassifier.detection.llm_detector import (
    DetectionResult,
    Timestamp,
    _write_decision,
    evaluate_detection,
)


def result(confidence, ranges):
    return DetectionResult(
        confidence_score=confidence,
        timestamps=[Timestamp(start=s, end=e) for s, e in ranges],
        reasoning="test",
    )


def test_distinct_ranges_stay_separate():
    assert evaluate_detection(result(90, [(60, 120), (480, 540)])) == [
        [60, 120],
        [480, 540],
    ]


def test_nearby_ranges_merge():
    assert evaluate_detection(result(90, [(60, 120), (121, 150)])) == [[60, 150]]


def test_short_ranges_dropped_individually():
    assert evaluate_detection(result(90, [(60, 120), (300, 305)])) == [[60, 120]]


def test_low_confidence_keeps_everything():
    assert evaluate_detection(result(30, [(60, 120)])) == []


def test_no_timestamps():
    assert evaluate_detection(result(90, [])) == []




def test_cut_decision_recorded(tmp_path):
    transcript_path = str(tmp_path / "transcript_3.json")
    output = DetectionResult(
        confidence_score=85,
        timestamps=[Timestamp(start=10.0, end=55.0)],
        reasoning="Sponsor read with promo code",
    )
    _write_decision(transcript_path, output, evaluate_detection(output))

    record = json.load(open(tmp_path / "transcript_3_decision.json"))
    assert record["action"] == "cut"
    assert record["cut_ranges_seconds"] == [[10.0, 55.0]]
    assert "promo" in record["reasoning"].lower()


def test_keep_decision_recorded(tmp_path):
    transcript_path = str(tmp_path / "transcript_3.json")
    output = DetectionResult(
        confidence_score=20, timestamps=[], reasoning="Just conversation"
    )
    _write_decision(transcript_path, output, evaluate_detection(output))

    record = json.load(open(tmp_path / "transcript_3_decision.json"))
    assert record["action"] == "keep"
    assert record["cut_ranges_seconds"] == []
