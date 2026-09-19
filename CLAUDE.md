# AudioClassifier

Detects and cuts target segments (ads by default) from podcast audio. Local-first: `PAYLOAD` env var in, cleaned mp3 in `output/`. AWS (`APP_MODE=aws`) is an optional bolt-on isolated under `src/cloud/`.

## Commands

- `uv sync` — install deps (uv only, no pip/requirements.txt)
- `PAYLOAD='{"podcast_name": ..., "episode_name": ..., "audio_url": ...}' uv run python src/main.py` — process one episode (needs `OPENAI_API_KEY`, `ffmpeg`)
- Logs go to `audioclassifier.log`, not the console

## Architecture

- `src/main.py` — entry point; `--detection <name|path>` selects a detection config
- `src/pod_handler/` — download, transcribe (faster-whisper), cut (soundfile/numpy)
- `src/detection/` — LLM verification via pydantic-ai (`LLM_MODEL`, any provider)
- `src/config/` — settings (env first, SSM in AWS mode), constants, detection config loader
- `configs/*.toon` — detection keywords + prompts (TOON format)

## Code Style

- Comments only when necessary, and concise — no narrating what the code already says
- Simple implementations over clever ones; no complexity for its own sake
- Standard Python conventions; `_`-prefix for module-internal functions and state
