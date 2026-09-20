import asyncio
import atexit
import json
import os
import threading

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

import backoff
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError

from audioclassifier.config.constants import (
    CONFIDENCE_SCORE,
    LLM_MODEL,
    MERGE_GAP_SECONDS,
    MIN_CUT_SECONDS,
)
from audioclassifier.logger.logger_setup import logger
from audioclassifier.config import settings
from audioclassifier.config.settings import get_setting
from audioclassifier.config.detection_config import get_detection_config

def _ensure_api_key():
    # For OpenAI models, resolve the key through settings (env var, or SSM in
    # AWS mode) and expose it where pydantic-ai looks for it. Other providers
    # use their own standard env vars (ANTHROPIC_API_KEY, ...).
    if LLM_MODEL.startswith("openai") and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = get_setting(settings.OPENAI_API_KEY)

# All agent calls run on one persistent background event loop. The agents'
# async HTTP connection pool is bound to the loop it first runs on, so calls
# from worker threads must share a single live loop rather than each creating
# and closing their own.
_loop = None
_loop_thread = None
_loop_lock = threading.Lock()


def _run(coro):
    global _loop, _loop_thread
    with _loop_lock:
        if _loop is None:
            _loop = asyncio.new_event_loop()
            _loop_thread = threading.Thread(target=_loop.run_forever, daemon=True)
            _loop_thread.start()
            atexit.register(_shutdown_loop)
    return asyncio.run_coroutine_threadsafe(coro, _loop).result()


def _shutdown_loop():
    if _loop is not None:
        _loop.call_soon_threadsafe(_loop.stop)
        _loop_thread.join(timeout=5)
        _loop.close()


class Timestamp(BaseModel):
    start: float
    end: float


class DetectionResult(BaseModel):
    confidence_score: int
    timestamps: list[Timestamp]
    reasoning: str = Field(
        description="Brief justification for the confidence score and timestamps"
    )


class SponsorList(BaseModel):
    sponsors: list[str]


# Agents are cached per config so a config change rebuilds them
_agent_cache = {}


def _get_agent(kind, output_type, instructions):
    config = get_detection_config()
    cached_config, agent = _agent_cache.get(kind, (None, None))
    if cached_config is not config:
        _ensure_api_key()
        agent = Agent(LLM_MODEL, output_type=output_type, instructions=instructions)
        _agent_cache[kind] = (config, agent)
    return agent


def _get_detection_agent():
    return _get_agent(
        "detection",
        DetectionResult,
        get_detection_config().assistant_instructions,
    )


def _get_sponsor_agent():
    return _get_agent(
        "sponsor",
        SponsorList,
        get_detection_config().sponsor_instructions,
    )


def evaluate_detection(result):
    """Validate a DetectionResult into a list of [start, end] second ranges to cut.

    Ranges below the confidence threshold are discarded wholesale; nearby
    ranges are merged; ranges shorter than MIN_CUT_SECONDS are dropped
    individually.
    """
    if result.confidence_score < CONFIDENCE_SCORE or not result.timestamps:
        logger.info(
            f"Keeping segment (confidence: {result.confidence_score}, "
            f"ranges: {len(result.timestamps)})"
        )
        return []

    ranges = sorted([t.start, t.end] for t in result.timestamps if t.end > t.start)
    merged = []
    for start, end in ranges:
        if merged and start - merged[-1][1] <= MERGE_GAP_SECONDS:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    kept = [r for r in merged if r[1] - r[0] >= MIN_CUT_SECONDS]
    logger.info(
        f"Confidence {result.confidence_score}: {len(kept)} cut range(s) "
        f"after merging/filtering: {kept}"
    )
    return kept


@backoff.on_exception(
    backoff.expo,
    ModelHTTPError,
    max_tries=5,
    giveup=lambda e: e.status_code != 429,
)
def get_specific_timestamps_using_llm(
    filename, path, sponsors, keyword_hits=None, audio_boundaries=None
):
    """Ask the LLM for ad ranges in a transcript segment.

    keyword_hits / audio_boundaries are advisory signals included in the
    prompt. Returns a list of [start, end] second ranges to cut (empty =
    keep all).
    """
    logger.info(f"Requesting timestamps for {filename}, sponsors: {sponsors}")

    with open(path, encoding="utf-8") as f:
        transcript = f.read()

    signals = []
    if keyword_hits:
        signals.append(
            f"- Ad-keyword/sponsor matches occur near these transcript times "
            f"(seconds): {keyword_hits}"
        )
    if audio_boundaries:
        signals.append(
            f"- Audio discontinuities (silence gaps or loudness shifts, the "
            f"typical signature of dynamically inserted ad boundaries) at "
            f"these times (seconds): {audio_boundaries}"
        )
    signals_block = (
        "\n\nAdditional detection signals (advisory, not exhaustive):\n"
        + "\n".join(signals)
        if signals
        else ""
    )

    result = _run(
        _get_detection_agent().run(
            f"{get_detection_config().get_detection_instructions(sponsors)}"
            f"{signals_block}"
            f"\n\nTranscript segments (JSON):\n{transcript}"
        )
    )
    output = result.output
    logger.info(f"Detection result for {filename}: {output}")
    cut_ranges = evaluate_detection(output)
    _write_decision(path, output, cut_ranges, keyword_hits, audio_boundaries)
    return cut_ranges


def _write_decision(
    transcript_path, output, cut_ranges, keyword_hits=None, audio_boundaries=None
):
    decision_path = transcript_path.replace(".json", "_decision.json")
    try:
        with open(decision_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "confidence_score": output.confidence_score,
                    "timestamps": [t.model_dump() for t in output.timestamps],
                    "reasoning": output.reasoning,
                    "action": "cut" if cut_ranges else "keep",
                    "cut_ranges_seconds": cut_ranges,
                    "keyword_hits": keyword_hits or [],
                    "audio_boundaries": audio_boundaries or [],
                },
                f,
                indent=2,
            )
    except OSError as e:
        logger.error(f"Could not write decision file {decision_path}: {e}")


def fetch_sponsors(podcast_description):
    if not get_detection_config().sponsor_instructions:
        logger.info("No sponsor_instructions in detection config, skipping")
        return []
    logger.info(f"Fetching sponsors for podcast description: {podcast_description}")
    try:
        result = _run(_get_sponsor_agent().run(podcast_description))
        sponsors = result.output.sponsors
        logger.info(f"Sponsors: {sponsors}")
        return sponsors
    except Exception as e:
        logger.error(f"Error fetching sponsors: {e}")
        return []
