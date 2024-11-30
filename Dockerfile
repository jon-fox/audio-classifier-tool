# Use Ubuntu 22.04 as a parent image
# FROM ubuntu:22.04
FROM nvidia/cuda:12.3.2-cudnn9-runtime-ubuntu22.04

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
    vim \
    iputils-ping \
    software-properties-common wget \
    libasound2-dev \
    libavcodec-extra \
    portaudio19-dev \
    libpq-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*


# Manually download and install PortAudio libraries if not available
# RUN wget http://ftp.us.debian.org/debian/pool/main/p/portaudio19/libportaudio2_19.6.0-1_amd64.deb && \
#     dpkg -i libportaudio2_19.6.0-1_amd64.deb && \
#     rm libportaudio2_19.6.0-1_amd64.deb

# Verify the FFmpeg and Python 3.11 installation

# ENV PATH=/usr/local/cuda-12.4/bin:$PATH

# ENV LD_LIBRARY_PATH=/usr/local/cuda-12.4/lib64:$LD_LIBRARY_PATH

# RUN CUDNN_PATH=$(dirname $(python3 -c "import nvidia.cudnn;print(nvidia.cudnn.__file__)"))
# ENV LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$CONDA_PREFIX/lib/:$CUDNN_PATH/lib

# RUN nvcc --version

# Set the working directory (optional)
WORKDIR /app

# COPY requirements.txt /app/
# COPY ./requirements.txt /app/
COPY ./requirements-whisperx.txt /app/
# RUN pip3 install --no-cache-dir -r requirements.txt
# RUN python3.11 -m pip install --no-cache-dir -r requirements.txt
RUN python3.11 -m pip install --no-cache-dir -r requirements-whisperx.txt

RUN python3.11 -m pip install torch --index-url https://download.pytorch.org/whl/cu121

# Copy your application files to the container (optional)
# COPY ./dist /app
COPY src/ /app/src

COPY certs/ /app/certs
# COPY set_env_vars.py /app/
# COPY ./startup.sh /app/

# RUN python3.11 -m venv venv

# RUN /bin/bash -c "source /app/venv/bin/activate && pip install --no-cache-dir -r /app/requirements.txt"

ENV PYTHONPATH=/app

EXPOSE 80 443

# ENTRYPOINT ["/app/startup.sh"]
CMD ["python3.11", "/app/src/main.py"]
