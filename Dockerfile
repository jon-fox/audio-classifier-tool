FROM nvidia/cuda:12.0.0-base-ubuntu22.04

# Set environment variables to prevent user interaction during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install FFmpeg and system libraries (Python itself is managed by uv)
RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    build-essential \
    libavcodec-extra \
    vim \
    iputils-ping && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

WORKDIR /app

# Dependency layer: cached unless the lockfile or python version changes
COPY pyproject.toml uv.lock .python-version /app/
RUN uv sync --frozen --no-dev

# Pre-download Whisper model during build (before src so code changes don't invalidate it)
RUN /app/.venv/bin/python -c "from faster_whisper import WhisperModel; import os; os.makedirs('/app/local_models/tiny', exist_ok=True); WhisperModel('tiny', download_root='/app/local_models/tiny')"

COPY src/ /app/src

ENV PYTHONPATH=/app
# Let ctranslate2 find the pip-installed cuBLAS/cuDNN libraries
ENV LD_LIBRARY_PATH=/app/.venv/lib/python3.13/site-packages/nvidia/cublas/lib:/app/.venv/lib/python3.13/site-packages/nvidia/cudnn/lib:$LD_LIBRARY_PATH

CMD ["/app/.venv/bin/python", "/app/src/main.py"]
