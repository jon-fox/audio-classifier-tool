# AudioClassifier - Dynamic Classifier used for Audio Segment Identification and Removal

Runs locally by default: one episode in, cleaned audio out. Needs an OpenAI API key and `ffmpeg`.

## Quick Start

```bash
uv sync
export OPENAI_API_KEY=<your-key>

PAYLOAD='{"podcast_name": "My Podcast", "episode_name": "Episode 1", "audio_url": "<mp3-url>"}' \
  uv run audioclassifier --detection examples/configs/ads.toon
```

Results land in `output/<podcast_name>/<episode_name>/`: the original mp3, the cleaned `*_filtered.mp3`, and a `transcripts/` dir with what was transcribed and each LLM cut/keep decision (with reasoning). Or with Docker:

```bash
docker build -t audioclassifier-app .
docker run --gpus all \
  -e OPENAI_API_KEY=<your-key> \
  -e DETECTION_CONFIG=ads \
  -e PAYLOAD='{"podcast_name": "My Podcast", "episode_name": "Episode 1", "audio_url": "<mp3-url>"}' \
  -v "$(pwd)/output:/app/output" \
  audioclassifier-app
```

Drop `--gpus all` to run on CPU (slower). The same container runs on any GPU box — RunPod, Modal, a gaming PC.

## As a Library

```bash
uv add git+https://github.com/jon-fox/audio-classifier-tool
```

```python
import audioclassifier

result = audioclassifier.process_episode(
    podcast_name="My Podcast",
    episode_name="Episode 1",
    audio_url="<mp3-url>",
    detection="examples/configs/ads.toon",  # a .toon path or a name in ./configs
    detection_instructions="...",           # or pass the prompt directly
    detection_keywords=["use code", ...],   # and the keyword gate
)
print(result["output_path"], result["seconds_removed"])
```

Importing has no side effects; configure the `"audioclassifier"` logger to see progress.

For a real end-to-end run with live console output and a decision summary:

```bash
uv run python examples/process_episode.py "<episode-mp3-url>"
```

## How It Works

- Downloads the episode from the `PAYLOAD` JSON
- Transcribes with faster-whisper (GPU-accelerated, CPU works too)
- Detects target segments with OpenAI — ads by default
- Cuts them and re-assembles the audio

## Detection

The classifier is fully yours to define — nothing is bundled. A [TOON](https://github.com/toon-format/spec) config supplies the keywords and prompts: select one with `--detection <name|path>` or `DETECTION_CONFIG` (names resolve from `./configs/`), or pass the prompt and keywords directly (`detection_instructions`/`detection_keywords` in the API, `DETECTION_INSTRUCTIONS`/`DETECTION_KEYWORDS` env vars). Complete examples live in `examples/configs/` (ads, politics).

## Text Classifier (optional, opt-in)

A self-distilled local classifier can add a third detection signal alongside keywords and audio analysis. Every processed episode writes LLM-labeled decisions under `output/**/transcripts/` — that corpus is the classifier's training data, and it grows with each run.

Enable with `USE_TEXT_CLASSIFIER=true`: the classifier's flagged ranges join the LLM prompt (advisory only — the LLM still decides), and it retrains automatically after each run from the **full accumulated history** (retraining is from scratch, in seconds, so nothing is ever forgotten). Refresh manually anytime:

```bash
uv run python examples/train_classifier.py          # or audioclassifier.train_text_classifier()
```

How it propagates: the durable memory is the decision files in `output/` — the model file (`local_models/text_classifier.joblib`) is a disposable cache rebuilt from them. Editing a decision file's `cut_ranges_seconds` after listening feeds your correction into the next training pass. In Docker, mount `local_models/` alongside `output/` to carry the model between containers (the data already survives via the `output/` mount).

## Parallelism

One episode per `process_episode` call. Multiple processes are safe, even in the same directory — downloads and segment audio live in per-episode temp dirs, and the classifier model is written atomically. Within one process, run episodes sequentially (Whisper models load once and are reused); concurrent episodes in threads are supported only with one shared detection config. Don't feed the same episode to two processes at once — they'd write the same output files.

## Options

- `LLM_MODEL` — any [pydantic-ai model string](https://ai.pydantic.dev/models/) (default `openai:gpt-5.6`; e.g. `openai:gpt-5-nano` for cheapest, `anthropic:claude-sonnet-4-6`, `ollama:qwen3` — non-OpenAI providers may need their extra installed)
- `DISCORD_ALERTS=true DISCORD_WEBHOOK_URL=<url>` — processing alerts in Discord
- `APP_MODE=aws` — optional cloud mode: config from SSM, results to S3/DynamoDB (code isolated under `audioclassifier/cloud/`)

## License

[MIT](LICENSE)
