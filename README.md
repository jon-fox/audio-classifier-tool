# AudioClassifier - AI-Powered Podcast Ad Removal

> AudioClassifier (formerly JusSkipIt) originally ran as a hosted service at jusskipit.com. The engine is now open source and can be self-hosted for podcast ad removal.

## How It Works

- Downloads an episode (via `PAYLOAD` locally, or polled from SQS in AWS mode)
- Transcribes with faster-whisper (GPU-accelerated, CPU works too)
- Detects target segments with OpenAI — ads by default
- Cuts them and re-assembles the audio
- Writes output to `output/` locally, or S3/CloudFront + DynamoDB in AWS mode

## Quick Start

See [local.md](local.md) — a single episode needs only an OpenAI key and `ffmpeg`.

## Configuration

Config comes from env vars; with `APP_MODE=aws`, missing values fall back to SSM Parameter Store:

| Env var | SSM fallback |
|---------|--------------|
| `OPENAI_API_KEY` | `/openai/api_key` |
| `DISCORD_WEBHOOK_URL` (needs `DISCORD_ALERTS=true`) | `/application/discord/errors_webhook` |
| `APP_STORAGE_BUCKET` | `/app/app_storage_bucket` |
| `CDN_BASE_URL` | `/cloudfront/distribution/url` |
| `SQS_URL` | `/sqs/audio_processing/url` |

### Detection

`configs/ads.toon` ([TOON](https://github.com/toon-format/spec)) defines the keywords and prompts. Point at your own with `--detection <name|path>` or `DETECTION_CONFIG`, or override inline with `DETECTION_INSTRUCTIONS` / `DETECTION_KEYWORDS`.

## AWS Mode

`APP_MODE=aws` turns on the worker: config from SSM, results to S3/DynamoDB, work polled from SQS. All AWS code is isolated under `src/cloud/`. Instances need NVIDIA drivers + Docker.

Workflows (manual dispatch only):

- `build.yml` — builds the Docker image, no AWS required
- `deploy-aws.yml` — pushes to ECR and runs the worker on a GPU EC2 instance

## License

[MIT](LICENSE)
