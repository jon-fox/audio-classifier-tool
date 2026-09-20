import pytest
import toon

import audioclassifier.config.detection_config as dc

ADS_CONFIG = "examples/configs/ads.toon"


@pytest.fixture(autouse=True)
def reset_config(monkeypatch):
    for var in ("DETECTION_CONFIG", "DETECTION_INSTRUCTIONS", "DETECTION_KEYWORDS"):
        monkeypatch.delenv(var, raising=False)
    dc._config = None
    yield
    dc._config = None


def test_ads_example_config_loads():
    config = dc.set_detection_config(ADS_CONFIG)
    assert config.name == "ads"
    assert len(config.keywords) > 100
    assert "confidence_score" in config.get_detection_instructions()


def test_sponsors_render_into_instructions():
    config = dc.set_detection_config(ADS_CONFIG)
    assert "Acme" in config.get_detection_instructions(["Acme"])


def test_custom_config_file(tmp_path):
    path = tmp_path / "politics.toon"
    path.write_text(
        toon.encode(
            {
                "name": "politics",
                "keywords": ["election"],
                "prompts": {
                    "assistant_instructions": "You detect political segments.",
                    "detection_instructions": "Find political content. {optional_sponsors_section}",
                },
            }
        )
    )
    config = dc.set_detection_config(str(path))
    assert config.name == "politics"
    assert config.keywords == ["election"]
    assert config.sponsor_instructions is None


def test_config_from_parts_without_file():
    config = dc.set_detection_config(
        instructions="Find crypto shilling. {optional_sponsors_section}",
        keywords=["crypto", "nft"],
    )
    assert config.name == "custom"
    assert config.keywords == ["crypto", "nft"]
    assert config.get_detection_instructions() == "Find crypto shilling. "


def test_overrides_layer_on_config_file():
    config = dc.set_detection_config(ADS_CONFIG, keywords=["only-this"])
    assert config.name == "ads"
    assert config.keywords == ["only-this"]


def test_env_config_and_overrides(monkeypatch):
    monkeypatch.setenv("DETECTION_CONFIG", ADS_CONFIG)
    monkeypatch.setenv("DETECTION_KEYWORDS", '["crypto"]')
    config = dc.get_detection_config()
    assert config.name == "ads"
    assert config.keywords == ["crypto"]


def test_no_config_raises_with_guidance():
    with pytest.raises(RuntimeError, match="No detection config"):
        dc.get_detection_config()


def test_keywords_without_instructions_raises():
    with pytest.raises(ValueError, match="instructions are required"):
        dc.set_detection_config(keywords=["orphan"])


def test_unknown_name_raises():
    with pytest.raises(FileNotFoundError):
        dc.set_detection_config("does-not-exist")


def test_keyword_cache_follows_config_changes():
    from audioclassifier.pod_handler.audio_processor import get_keywords_compiled

    dc.set_detection_config(instructions="Find X.", keywords=["first"])
    assert [p.pattern for p in get_keywords_compiled()] == ["first"]
    dc.set_detection_config(instructions="Find X.", keywords=["second"])
    assert [p.pattern for p in get_keywords_compiled()] == ["second"]
