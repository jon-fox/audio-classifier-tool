import pytest

from audioclassifier.cloud.storage import _parse_s3_uri


def test_parse_s3_uri():
    assert _parse_s3_uri("s3://my-bucket/some/prefix/") == ("my-bucket", "some/prefix")
    assert _parse_s3_uri("s3://my-bucket") == ("my-bucket", "")


def test_parse_s3_uri_rejects_bad_input():
    with pytest.raises(ValueError):
        _parse_s3_uri("https://bucket/x")
    with pytest.raises(ValueError):
        _parse_s3_uri("s3://")
