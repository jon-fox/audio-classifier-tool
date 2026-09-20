import os

# Working directory for downloads/output; defaults to the current directory
# (which is /app in the container)
BASE_PATH = os.getenv("BASE_PATH", ".")

# Paths for downloads, models, and ad utilities based on the base path
FINISHED_MP3_DIR = os.path.join(BASE_PATH, "output")
MODEL_DOWNLOAD_PATH = os.path.join(BASE_PATH, "local_models", "tiny")
# Any pydantic-ai model string works: openai:gpt-5, anthropic:claude-sonnet-4-6,
# ollama:qwen3, ... (non-OpenAI providers may need their extra installed)
LLM_MODEL = os.getenv("LLM_MODEL", "openai:gpt-5.6")
NUMBER_OF_MODELS = int(os.getenv("NUMBER_OF_MODELS", 8))
MODEL_SIZE = "tiny"

CONFIDENCE_SCORE = 60
MIN_CUT_SECONDS = 15  # drop detected ranges shorter than this (likely false positives)
MERGE_GAP_SECONDS = 3  # merge detected ranges separated by less than this
CROSSFADE_MS = 30

# Audio boundary detection (dynamic ad insertion signatures)
SILENCE_DB = -45.0
LOUDNESS_SHIFT_DB = 4.0
BOUNDARY_WINDOW_SECONDS = 0.5
SHIFT_SPAN_WINDOWS = 8  # loudness comparison span on each side, in windows (4s)
SNAP_TOLERANCE_SECONDS = 3.0  # max distance to snap a cut edge to an audio boundary

# Self-distilled text classifier (trained from past runs' decision files).
# Opt-in: when enabled, its flags join the LLM prompt and it retrains after
# each run; manual (re)training via train_text_classifier() always works.
TEXT_CLASSIFIER_PATH = os.path.join(BASE_PATH, "local_models", "text_classifier.joblib")
USE_TEXT_CLASSIFIER = os.getenv("USE_TEXT_CLASSIFIER", "false").lower() in (
    "1",
    "true",
    "yes",
)
CLASSIFIER_THRESHOLD = 0.65
CLASSIFIER_MIN_RANGE_SECONDS = 8

DISCORD_ALERTS_ENABLED = os.getenv("DISCORD_ALERTS", "false").lower() in (
    "1",
    "true",
    "yes",
)
