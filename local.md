# Local Testing

Process a single episode — needs only an OpenAI API key and `ffmpeg`. The cleaned file lands in `output/`.

```bash
uv sync
export OPENAI_API_KEY=<your-key>
export BASE_PATH=. PYTHONPATH=$PWD
mkdir -p downloads output

PAYLOAD='{"podcast_name": "My Podcast", "episode_name": "Episode 1", "audio_url": "<mp3-url>"}' \
  uv run python src/main.py
```

## Docker

```bash
docker build -t audioclassifier-app .
docker run --gpus all \
  -e OPENAI_API_KEY=<your-key> \
  -e PAYLOAD='{"podcast_name": "My Podcast", "episode_name": "Episode 1", "audio_url": "<mp3-url>"}' \
  -v "$(pwd)/output:/app/output" \
  audioclassifier-app
```

Drop `--gpus all` to run on CPU (slower). The same container runs on any GPU box — RunPod, Modal, a gaming PC.

## Options

- `--detection <name|path>` — detect something other than ads (default: `configs/ads.toon`)
- `DISCORD_ALERTS=true DISCORD_WEBHOOK_URL=<url>` — processing alerts in Discord
