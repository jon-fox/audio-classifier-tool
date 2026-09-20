# Tests

```
tests/
  unit/           mirrors src/audioclassifier/ (unit/detection/ <-> detection/, ...)
  integration/    builds and installs the package, runs the real pipeline
```

## Unit tests

Fast, no network, no API key:

```bash
uv run pytest
```

Covers detection rules (confidence gating, range merging/filtering), audio cutting
(multi-range cuts, crossfades, boundary snapping, mp3 round-trip), detection config
loading/overrides, and decision-file output. Each test file mirrors its source file:
`tests/unit/detection/test_llm_detector.py` tests `src/audioclassifier/detection/llm_detector.py`.

## Integration tests

```bash
uv run pytest -m integration
```

- `test_package_install.py` — builds the wheel locally (`uv build`), installs it into an
  isolated environment, and exercises the installed package: import, bundled detection
  config, public API, and the `audioclassifier` console script. No API key needed.
- `test_process_episode.py` — the full pipeline (download, transcribe, detect, cut)
  against a real episode. Skipped unless configured:

```bash
export OPENAI_API_KEY=<your-key>
export AUDIOCLASSIFIER_TEST_URL=<episode-mp3-url>
uv run pytest -m integration
```

The episode test writes `downloads/` and `output/` in the current directory and takes
as long as a real run.

## Using AudioClassifier as a library

`test_process_episode.py` doubles as the usage example:

```python
import audioclassifier

result = audioclassifier.process_episode(
    podcast_name="My Podcast",
    episode_name="Episode 1",
    audio_url="https://example.com/episode.mp3",
    detection="ads",  # optional: bundled/local config name, or a .toon path
)

result["output_path"]        # the cleaned mp3
result["original_duration"]  # seconds
result["filtered_duration"]  # seconds
result["seconds_removed"]    # how much was cut
```

Importing the package has no side effects. Progress logging is opt-in:

```python
import logging
logging.getLogger("audioclassifier").addHandler(logging.StreamHandler())
logging.getLogger("audioclassifier").setLevel(logging.INFO)
```

Set `OPENAI_API_KEY` (or the key matching your `LLM_MODEL` provider) before calling.
