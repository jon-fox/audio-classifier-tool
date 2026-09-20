import pytest
import toon

import audioclassifier.config.detection_config as dc


@pytest.fixture(autouse=True)
def reset_config():
    dc._config = None
    yield
    dc._config = None


def test_bundled_ads_config_loads():
    config = dc.get_detection_config()
    assert config.name == "ads"
    assert len(config.keywords) > 100
    assert "confidence_score" in config.get_detection_instructions()


def test_sponsors_render_into_instructions():
    config = dc.get_detection_config()
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


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("DETECTION_KEYWORDS", '["crypto", "nft"]')
    monkeypatch.setenv("DETECTION_INSTRUCTIONS", "Find crypto shilling.")
    config = dc.get_detection_config()
    assert config.keywords == ["crypto", "nft"]
    assert config.get_detection_instructions() == "Find crypto shilling."


def test_unknown_name_raises():
    with pytest.raises(FileNotFoundError):
        dc.set_detection_config("does-not-exist")
