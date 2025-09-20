# JusSkipIt App - AI-Powered Podcast Ad Removal

🎧 **[JusSkipIt.com](https://www.jusskipit.com)** - The intelligent podcast ad removal service

## Overview

JusSkipIt automatically detects and removes advertisements from podcast audio files using advanced AI transcription technology. This application is the core processing engine that:

- Downloads podcast episodes from audio URLs
- Uses WhisperX/OpenAI Whisper for AI-powered transcription
- Intelligently identifies and removes advertisement segments
- Uploads cleaned audio files to AWS S3/CloudFront CDN
- Manages processing status via DynamoDB

## Setup & Configuration

### Environment Variables

```bash
# AWS Credentials
export AWS_SHARED_CREDENTIALS_FILE=/mnt/c/Users/foxj7/.aws/credentials
export AWS_CONFIG_FILE=/mnt/c/Users/foxj7/.aws/config

# Application Paths
export PYTHONPATH="${PYTHONPATH}:/mnt/c/Developer_Workspace/JusSkipIt_App"
export BASE_PATH=/mnt/c/Developer_Workspace/JusSkipIt_App/
# or for local development:
# export BASE_PATH=.

# API Keys
set OPENAI_API_KEY=your_openai_api_key_here
```

### GPU/CUDA Setup

```bash
# PyAudio & CUDA Library Path
# Required for GPU-accelerated AI transcription
export LD_LIBRARY_PATH=/usr/local/cuda-12.4/lib64:$LD_LIBRARY_PATH
```

## Infrastructure & Deployment

### Terraform Backend

```bash
terraform init -backend-config="bucket=094d0cca-01db-472d-adc8-5eae88f51899"
```

### AWS ECS Agent Setup

```bash
sudo yum install -y ecs-init
sudo systemctl start ecs
sudo systemctl status ecs
```

### Pre-configured AMIs

| AMI ID | Description |
|--------|-------------|
| `ami-092326650e967b14a` | NVIDIA drivers + Docker |
| `ami-02e30e25d601cac67` | NVIDIA + Docker + JusSkipIt container (stopped) |
| `ami-05f85bc16c1a0257a` | **Latest JusSkipIt v2** |

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

1. Set environment variables
2. Build Docker container: `docker build -t jusskipit-app .`
3. Run: `docker run --gpus all jusskipit-app`
4. Application polls SQS for podcast processing requests

For more information, visit **[JusSkipIt.com](https://www.jusskipit.com)**

