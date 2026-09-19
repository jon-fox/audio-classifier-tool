FROM nvidia/cuda:12.0.0-base-ubuntu22.04

# Set environment variables to prevent user interaction during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Update the package lists and install necessary packages for adding the PPA
# Install FFmpeg and system libraries (Python itself is managed by uv)
RUN apt-get update && \
    apt-get install -y software-properties-common wget && \
    apt-get install -y \
    ffmpeg \
    build-essential \
    libcudnn8 \
    libcudnn8-dev \
    vim \
    iputils-ping \
    software-properties-common wget \
    libasound2-dev \
    libavcodec-extra \
    portaudio19-dev \
    libpq-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Dependency layer: cached unless the lockfile or python version changes
COPY pyproject.toml uv.lock .python-version /app/
RUN uv sync --frozen --no-dev

COPY src/ /app/src

ENV PYTHONPATH=/app

# Pre-download Whisper model during build
RUN /app/.venv/bin/python -c "from faster_whisper import WhisperModel; import os; os.makedirs('/app/local_models/tiny', exist_ok=True); WhisperModel('tiny', download_root='/app/local_models/tiny')"

EXPOSE 80 443

CMD ["/app/.venv/bin/python", "/app/src/main.py"]
