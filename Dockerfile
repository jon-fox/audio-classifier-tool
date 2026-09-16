FROM nvidia/cuda:12.0.0-base-ubuntu22.04

# Set environment variables to prevent user interaction during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Update the package lists and install necessary packages for adding the PPA
# Install FFmpeg and Python 3.11
RUN apt-get update && \
    apt-get install -y software-properties-common wget && \
    apt-get install -y \
    ffmpeg \
    python3.11 \
    python3.11-distutils \
    python3.11-venv \
    python3-pip \
    python3.11-dev \
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


WORKDIR /app

COPY ./requirements.txt /app/
RUN python3.11 -m pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src

ENV PYTHONPATH=/app

# Pre-download Whisper model during build
RUN python3.11 -c "from faster_whisper import WhisperModel; import os; os.makedirs('/app/local_models/tiny', exist_ok=True); WhisperModel('tiny', download_root='/app/local_models/tiny')"

EXPOSE 80 443

CMD ["python3.11", "/app/src/main.py"]
