# AudioClassifier - AI-Powered Podcast Ad Removal

> AudioClassifier (formerly JusSkipIt) originally ran as a hosted service at jusskipit.com. The service has been retired, but the full processing engine is open source here and can be self-hosted for podcast ad removal.

## Overview

AudioClassifier automatically detects and removes advertisements from podcast audio files using AI transcription. This is the core processing engine:

- Downloads podcast episodes from audio URLs (a single episode via `PAYLOAD`, or polled from SQS in AWS mode)
- Transcribes audio with faster-whisper (GPU-accelerated, runs on CPU too)
- Identifies advertisement segments using OpenAI
- Cuts the ads and re-assembles the audio
- Writes cleaned files to `output/` (local) or S3/CloudFront with status in DynamoDB (AWS mode)

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
| `DISCORD_WEBHOOK_URL` (needs `DISCORD_ALERTS=true`) | `/application/discord/errors_webhook` |
| `APP_STORAGE_BUCKET` | `/app/app_storage_bucket` |
| `CDN_BASE_URL` | `/cloudfront/distribution/url` |
| `SQS_URL` | `/sqs/audio_processing/url` |

Without `APP_MODE=aws`, only `OPENAI_API_KEY` is needed — see [local.md](local.md).

### Detection Config

What the app finds and cuts is defined by a [TOON](https://github.com/toon-format/spec) config (keywords + prompts) in the top-level `configs/` directory, defaulting to `configs/ads.toon`:

- `--detection <name|path>` (CLI) or `DETECTION_CONFIG` (env) — a config name in `configs/` or a path to a `.toon` file
- `DETECTION_INSTRUCTIONS` / `DETECTION_KEYWORDS` — inject the prompt or keyword list directly (keywords as a JSON array or comma-separated), overriding the file

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

Both workflows are manual dispatch only:

- `build.yml`: builds the Docker image (no AWS required)
- `deploy-aws.yml`: pushes to ECR and runs the SQS worker on a GPU EC2 instance

## Architecture
- **Container-based**: Docker with NVIDIA CUDA support
- **Cloud integration**: optional, isolated under `src/cloud/` (AWS today: S3, DynamoDB, SQS, Lambda, SSM), enabled with `APP_MODE=aws`
- **AI Processing**: GPU-accelerated transcription for faster ad detection

## Quick Start

1. Local single-episode runs (native or Docker): see [local.md](local.md)
2. AWS worker mode: set `APP_MODE=aws` with the SSM parameters above — the container then polls SQS for processing requests
