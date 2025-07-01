import os

# Function to determine the base path based on environment variable
BASE_PATH = os.getenv("BASE_PATH", "/app")  # Default to /app if not set

# Paths for downloads, models, and ad utilities based on the base path
DOWNLOAD_DIR = os.path.join(BASE_PATH, "downloads")
FINISHED_MP3_DIR = os.path.join(BASE_PATH, "output")
MODEL_DOWNLOAD_PATH = os.path.join(BASE_PATH, "local_models", "tiny")
MODEL_NAME = "gpt-4o"
MODEL_FILE_NAME = "tiny.pt"
NUMBER_OF_MODELS = int(os.getenv("NUMBER_OF_MODELS", 8))
MODEL_SIZE = "tiny"

ADS_TXT_PATH = os.path.join(BASE_PATH, "src", "ad_utils", "popular_ads.txt")
CONFIDENCE_SCORE = 60
