# AudioClassifier - Dynamic Classifier used for Audio Segment Identification and Removal

Runs locally by default: one episode in, cleaned audio out. Needs an OpenAI API key and `ffmpeg`.

## Quick Start

```bash
uv sync
export OPENAI_API_KEY=<your-key>

PAYLOAD='{"podcast_name": "My Podcast", "episode_name": "Episode 1", "audio_url": "<mp3-url>"}' \
  uv run python src/main.py
```

Results land in `output/<podcast_name>/`: the original mp3, the cleaned `*_clean.mp3`, and a `transcripts/` dir with what was transcribed and each LLM cut/keep decision (with reasoning). Or with Docker:

```bash
docker build -t audioclassifier-app .
docker run --gpus all \
  -e OPENAI_API_KEY=<your-key> \
  -e PAYLOAD='{"podcast_name": "My Podcast", "episode_name": "Episode 1", "audio_url": "<mp3-url>"}' \
  -v "$(pwd)/output:/app/output" \
  audioclassifier-app
```

Drop `--gpus all` to run on CPU (slower). The same container runs on any GPU box — RunPod, Modal, a gaming PC.

## How It Works

- Downloads the episode from the `PAYLOAD` JSON
- Transcribes with faster-whisper (GPU-accelerated, CPU works too)
- Detects target segments with OpenAI — ads by default
- Cuts them and re-assembles the audio

## Detection

`configs/ads.toon` ([TOON](https://github.com/toon-format/spec)) defines the keywords and prompts. Point at your own with `--detection <name|path>` or `DETECTION_CONFIG`, or override inline with `DETECTION_INSTRUCTIONS` / `DETECTION_KEYWORDS`.

## Options

- `LLM_MODEL` — any [pydantic-ai model string](https://ai.pydantic.dev/models/) (default `openai:gpt-5`; e.g. `anthropic:claude-sonnet-4-6`, `ollama:qwen3` — non-OpenAI providers may need their extra installed)
- `DISCORD_ALERTS=true DISCORD_WEBHOOK_URL=<url>` — processing alerts in Discord
- `APP_MODE=aws` — optional cloud mode: config from SSM, results to S3/DynamoDB (code isolated under `src/cloud/`); `deploy-aws.yml` runs one-shot jobs on a GPU EC2 instance

## License

[MIT](LICENSE)
