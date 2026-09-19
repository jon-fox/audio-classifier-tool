# Local Testing

Process a single episode with no AWS account — just an OpenAI API key and `ffmpeg`. The episode to process is passed as a `PAYLOAD` JSON env var; the cleaned file lands in `output/`.

```bash
uv sync
export OPENAI_API_KEY=<your-key>
export BASE_PATH=. PYTHONPATH=$PWD
mkdir -p downloads output

PAYLOAD='{"podcast_name": "My Podcast", "episode_name": "Episode 1", "audio_url": "<episode-mp3-url>"}' \
  uv run python src/main.py
```

Optional: `export DISCORD_ALERTS=true DISCORD_WEBHOOK_URL=<url>` to get processing alerts in Discord.

## Docker

The image defaults to local mode:

```bash
docker build -t audioclassifier-app .
docker run --gpus all \
  -e OPENAI_API_KEY=<your-key> \
  -e PAYLOAD='{"podcast_name": "My Podcast", "episode_name": "Episode 1", "audio_url": "<episode-mp3-url>"}' \
  -v "$(pwd)/output:/app/output" \
  audioclassifier-app
```

Drop `--gpus all` to run on CPU (the Whisper `tiny` model is fine on CPU, just slower). The same container works on any rented GPU box — RunPod, Modal, a gaming PC — no cloud integration needed.
