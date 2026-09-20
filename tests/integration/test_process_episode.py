"""Full pipeline run against a real episode; doubles as the library usage example.

Requires OPENAI_API_KEY and AUDIOCLASSIFIER_TEST_URL; run with:
    uv run pytest -m integration
"""

import os

import pytest

import audioclassifier

pytestmark = pytest.mark.integration


def test_process_episode():
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("set OPENAI_API_KEY")
    url = os.getenv("AUDIOCLASSIFIER_TEST_URL")
    if not url:
        pytest.skip("set AUDIOCLASSIFIER_TEST_URL to an episode mp3 url")

    result = audioclassifier.process_episode(
        podcast_name="Integration Test",
        episode_name="Test Episode",
        audio_url=url,
    )

    assert os.path.isfile(result["output_path"])
    assert result["output_path"].endswith("_filtered.mp3")
    assert 0 < result["filtered_duration"] <= result["original_duration"]
    assert result["seconds_removed"] >= 0
