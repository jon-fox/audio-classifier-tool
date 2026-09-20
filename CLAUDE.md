# AudioClassifier

Detects and cuts target segments (ads by default) from audio. Installable package (`audioclassifier`) usable as a library (`audioclassifier.process_audio`) or CLI.

## Commands

- `uv sync` — install deps + the package (uv only, no pip/requirements.txt)
- `PAYLOAD='{"source": ..., "name": ..., "audio_url": ...}' uv run audioclassifier --detection examples/configs/ads.toon` — process one audio file (needs `OPENAI_API_KEY`, `ffmpeg`)
- `uv run pytest` — unit tests; `-m integration` for the full-pipeline run (see tests/README.md)
- CLI logs go to `audioclassifier.log`, not the console; library imports are side-effect free (NullHandler logger)

## Architecture (src/audioclassifier/)

- `__init__.py` — public API: `process_audio(...)`, `train_text_classifier()`
- `cli.py` — CLI entry point; `--detection <name|path>` selects a detection config
- `processing/` — download, transcribe (faster-whisper), cut (soundfile/numpy)
- `detection/` — LLM verification via pydantic-ai (`LLM_MODEL`, any provider), self-distilled text classifier
- `config/` — constants, detection config loader
- `cloud/` — all cloud integrations live here, nothing cloud-touching outside it (today: optional S3 upload of outputs via `storage=`)
- No bundled classifier: users supply a `.toon` config (names resolve from `./configs/`) or pass instructions/keywords directly; examples in `examples/configs/`
- `tests/unit/` mirrors this layout (`tests/unit/cloud/test_storage.py` ↔ `cloud/storage.py`)

## Code Style

- Comments only when necessary, and concise — no narrating what the code already says
- Simple implementations over clever ones; no complexity for its own sake
- Standard Python conventions; `_`-prefix for module-internal functions and state
- Segregate by concern into packages — cloud code under `cloud/`, detection under `detection/`, audio work under `processing/`
