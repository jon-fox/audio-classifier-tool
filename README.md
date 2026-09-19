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

### Configuration

Config resolves from environment variables first. Setting `APP_MODE=aws` enables the AWS integrations — config falls back to SSM Parameter Store, results go to S3/DynamoDB, and the app polls SQS for work:

| Env var | SSM fallback (`APP_MODE=aws`) |
|---------|-------------------------------|
| `OPENAI_API_KEY` | `/openai/api_key` |
| `DISCORD_WEBHOOK_URL` (optional) | `/application/discord/errors_webhook` |
| `APP_STORAGE_BUCKET` | `/app/app_storage_bucket` |
| `CDN_BASE_URL` | `/cloudfront/distribution/url` |
| `SQS_URL` | `/sqs/audio_processing/url` |

Without `APP_MODE=aws`, only `OPENAI_API_KEY` is needed — see [local.md](local.md).

### GPU/CUDA Setup

```bash
# CUDA library path, required for GPU-accelerated transcription
export LD_LIBRARY_PATH=/usr/local/cuda-12.4/lib64:$LD_LIBRARY_PATH
```

## Local Testing

See [local.md](local.md) to run the ad-removal pipeline on a single episode without the AWS worker infrastructure.

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

- `build.yml`: builds the Docker image on push/PR (no AWS required)
- `deploy-aws.yml`: optional manual dispatch — pushes to ECR and runs the SQS worker on a GPU EC2 instance

## Development Notes

### Known Issues
- **11/28**: WhisperX compatibility issues due to ctranslate2 updates
- Monitor for audio processing library version conflicts

### Architecture
- **Container-based**: Docker with NVIDIA CUDA support
- **Cloud integration**: optional, isolated under `src/cloud/` (AWS today: S3, DynamoDB, SQS, Lambda, SSM), enabled with `APP_MODE=aws`
- **AI Processing**: GPU-accelerated transcription for faster ad detection

## Quick Start

1. Set environment variables and store secrets in SSM (see above)
2. Build Docker container: `docker build -t jusskipit-app .`
3. Run: `docker run --gpus all jusskipit-app`
4. Application polls SQS for podcast processing requests
