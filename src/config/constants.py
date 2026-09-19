import os

# Working directory for downloads/output; defaults to the current directory
# (which is /app in the container)
BASE_PATH = os.getenv("BASE_PATH", ".")

# Paths for downloads, models, and ad utilities based on the base path
DOWNLOAD_DIR = os.path.join(BASE_PATH, "downloads")
FINISHED_MP3_DIR = os.path.join(BASE_PATH, "output")
MODEL_DOWNLOAD_PATH = os.path.join(BASE_PATH, "local_models", "tiny")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(FINISHED_MP3_DIR, exist_ok=True)
# Any pydantic-ai model string works: openai:gpt-5, anthropic:claude-sonnet-4-6,
# ollama:qwen3, ... (non-OpenAI providers may need their extra installed)
LLM_MODEL = os.getenv("LLM_MODEL", "openai:gpt-5.6")
MODEL_FILE_NAME = "tiny.pt"
NUMBER_OF_MODELS = int(os.getenv("NUMBER_OF_MODELS", 8))
MODEL_SIZE = "tiny"

CONFIDENCE_SCORE = 60

DISCORD_ALERTS_ENABLED = os.getenv("DISCORD_ALERTS", "false").lower() in (
    "1",
    "true",
    "yes",
)
