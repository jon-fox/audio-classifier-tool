import json
import os

import toon

# Top-level configs/ directory (repo root locally, /app/configs in the container)
CONFIGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "configs",
)
DEFAULT_CONFIG_NAME = "ads"


class DetectionConfig:
    """What to find and cut: keywords and prompts, fully user-configurable.

    Resolution order:
    1. --detection CLI flag / DETECTION_CONFIG env var: a config name looked up
       in the top-level configs/ directory (e.g. "ads" -> configs/ads.toon),
       or a direct path to a .toon file. Defaults to "ads".
    2. DETECTION_INSTRUCTIONS / DETECTION_KEYWORDS env vars: inject or override
       the detection prompt and keyword list directly, no config file needed
       (keywords as a JSON array, or comma-separated).
    """

    def __init__(self, path):
        with open(path) as f:
            data = toon.decode(f.read())
        self.name = data.get("name", os.path.basename(path))
        self.keywords = data["keywords"]
        self.assistant_instructions = data["prompts"]["assistant_instructions"]
        self.sponsor_instructions = data["prompts"].get("sponsor_instructions")
        self._detection_template = data["prompts"]["detection_instructions"]

        instructions_override = os.getenv("DETECTION_INSTRUCTIONS")
        if instructions_override:
            self._detection_template = instructions_override

        keywords_override = os.getenv("DETECTION_KEYWORDS")
        if keywords_override:
            try:
                self.keywords = json.loads(keywords_override)
            except json.JSONDecodeError:
                self.keywords = [
                    k.strip() for k in keywords_override.split(",") if k.strip()
                ]

    def get_detection_instructions(self, sponsors=None):
        if sponsors and not (len(sponsors) == 1 and sponsors[0] == ""):
            section = (
                "If one or more of these sponsor names are present, increase the confidence "
                f"score that an ad is present greatly: {', '.join(sponsors)}"
            )
        else:
            section = ""
        return self._detection_template.replace("{optional_sponsors_section}", section)


def _resolve_path(name_or_path):
    if os.path.isfile(name_or_path):
        return name_or_path
    candidate = os.path.join(CONFIGS_DIR, f"{name_or_path}.toon")
    if os.path.isfile(candidate):
        return candidate
    raise FileNotFoundError(
        f"Detection config '{name_or_path}' not found (looked for a file at that "
        f"path and at {candidate})"
    )


_config = None


def get_detection_config():
    global _config
    if _config is None:
        _config = DetectionConfig(
            _resolve_path(os.getenv("DETECTION_CONFIG", DEFAULT_CONFIG_NAME))
        )
    return _config


def set_detection_config(name_or_path):
    """Explicitly select the detection config (used by the CLI)."""
    global _config
    _config = DetectionConfig(_resolve_path(name_or_path))
    return _config
