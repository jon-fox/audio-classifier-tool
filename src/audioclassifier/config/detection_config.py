import json
import os

import toon

# Config names resolve from ./configs
CONFIGS_DIR = os.path.join(os.getcwd(), "configs")

_DEFAULT_ASSISTANT_INSTRUCTIONS = (
    "Your role is to analyze text for target segments. Prioritize accuracy and "
    "follow the scoring and timestamping instructions carefully."
)

_NO_CONFIG_ERROR = (
    "No detection config selected. Pass a .toon config (a path, or a name in "
    "./configs) or detection instructions/keywords directly — via "
    "process_episode(detection=..., detection_instructions=..., "
    "detection_keywords=...), the --detection flag, or the DETECTION_CONFIG / "
    "DETECTION_INSTRUCTIONS / DETECTION_KEYWORDS env vars. Example configs: "
    "examples/configs/ in the repository."
)


class DetectionConfig:
    """What to find and cut: keywords and prompts.

    Nothing is bundled — supply a .toon config file, or instructions/keywords
    directly. See examples/configs/ for complete classifiers (ads, politics).
    """

    def __init__(
        self,
        name,
        keywords,
        detection_template,
        assistant_instructions,
        sponsor_instructions=None,
    ):
        self.name = name
        self.keywords = list(keywords)
        self.assistant_instructions = assistant_instructions
        self.sponsor_instructions = sponsor_instructions
        self._detection_template = detection_template

    @classmethod
    def from_file(cls, path):
        with open(path) as f:
            data = toon.decode(f.read())
        prompts = data["prompts"]
        return cls(
            name=data.get("name", os.path.basename(path)),
            keywords=data["keywords"],
            detection_template=prompts["detection_instructions"],
            assistant_instructions=prompts["assistant_instructions"],
            sponsor_instructions=prompts.get("sponsor_instructions"),
        )

    @classmethod
    def from_parts(cls, instructions, keywords=None, name="custom"):
        if not instructions:
            raise ValueError(
                "detection instructions are required when no config file is given"
            )
        return cls(
            name=name,
            keywords=keywords or [],
            detection_template=instructions,
            assistant_instructions=_DEFAULT_ASSISTANT_INSTRUCTIONS,
        )

    def apply_overrides(self, instructions=None, keywords=None):
        if instructions:
            self._detection_template = instructions
        if keywords:
            self.keywords = list(keywords)

    def get_detection_instructions(self, sponsors=None):
        if sponsors and not (len(sponsors) == 1 and sponsors[0] == ""):
            section = (
                "If one or more of these sponsor names are present, increase the confidence "
                f"score that an ad is present greatly: {', '.join(sponsors)}"
            )
        else:
            section = ""
        return self._detection_template.replace("{optional_sponsors_section}", section)


def _parse_keywords(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return [k.strip() for k in value.split(",") if k.strip()]


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


def _build(name_or_path=None, instructions=None, keywords=None):
    if name_or_path:
        config = DetectionConfig.from_file(_resolve_path(name_or_path))
        config.apply_overrides(instructions=instructions, keywords=keywords)
        return config
    if instructions or keywords:
        return DetectionConfig.from_parts(instructions, keywords)
    return None


_config = None


def get_detection_config():
    global _config
    if _config is None:
        _config = _build(
            os.getenv("DETECTION_CONFIG"),
            os.getenv("DETECTION_INSTRUCTIONS"),
            _parse_keywords(os.getenv("DETECTION_KEYWORDS")),
        )
        if _config is None:
            raise RuntimeError(_NO_CONFIG_ERROR)
    return _config


def set_detection_config(name_or_path=None, instructions=None, keywords=None):
    """Select the detection config: a file, direct instructions/keywords, or both."""
    global _config
    config = _build(name_or_path, instructions, keywords)
    if config is None:
        raise RuntimeError(_NO_CONFIG_ERROR)
    _config = config
    return _config
