# JusSkipIt - AI-Powered Podcast Ad Removal

> JusSkipIt originally ran as a hosted service at jusskipit.com. The service has been retired, but the full processing engine is open source here and can be self-hosted for podcast ad removal.

## Overview

JusSkipIt automatically detects and removes advertisements from podcast audio files using AI transcription. This is the core processing engine:

- Downloads podcast episodes from audio URLs (polled from SQS)
- Transcribes audio with WhisperX/OpenAI Whisper (GPU-accelerated)
- Identifies advertisement segments using OpenAI
- Cuts the ads and re-assembles the audio
- Uploads cleaned files to S3/CloudFront and tracks status in DynamoDB

## Setup & Configuration

### Environment Variables

```bash
# AWS Credentials
export AWS_SHARED_CREDENTIALS_FILE=~/.aws/credentials
export AWS_CONFIG_FILE=~/.aws/config

# Application Paths
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export BASE_PATH=.   # working directory for downloads/output (defaults to /app in the container)
```

### Secrets

Secrets are read at runtime, not from env vars:

- OpenAI API key: SSM Parameter Store at `/openai/api_key`
- Discord error webhook: SSM Parameter Store at `/application/discord/errors_webhook`
- Database credentials: Secrets Manager

### GPU/CUDA Setup

```bash
# CUDA library path, required for GPU-accelerated transcription
export LD_LIBRARY_PATH=/usr/local/cuda-12.4/lib64:$LD_LIBRARY_PATH
```

## Infrastructure & Deployment

### Terraform Backend

```bash
terraform init -backend-config="bucket=<your-tf-state-bucket>"
```

### AWS ECS Agent Setup

```bash
sudo yum install -y ecs-init
sudo systemctl start ecs
sudo systemctl status ecs
```

### AMI Requirements

Instances need NVIDIA drivers + Docker (build your own AMI or start from an AWS Deep Learning AMI).

## CI/CD

- GitHub Actions configured for workflow dispatch from UI
- Automated deployment pipeline for ECS containers

## Development Notes

### Known Issues
- **11/28**: WhisperX compatibility issues due to ctranslate2 updates
- Monitor for audio processing library version conflicts

### Architecture
- **Container-based**: Docker with NVIDIA CUDA support
- **AWS Integration**: ECS, S3, DynamoDB, SQS, Lambda
- **AI Processing**: GPU-accelerated transcription for faster ad detection

## Quick Start

1. Set environment variables and store secrets in SSM (see above)
2. Build Docker container: `docker build -t jusskipit-app .`
3. Run: `docker run --gpus all jusskipit-app`
4. Application polls SQS for podcast processing requests
