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

from src.config.constants import CONFIDENCE_SCORE, LLM_MODEL
from src.logger.logger_setup import logger
from src.config import settings
from src.config.settings import get_setting
from src.config.detection_config import get_detection_config

# For OpenAI models, resolve the key through settings (env var, or SSM in AWS
# mode) and expose it where pydantic-ai looks for it. Other providers use their
# own standard env vars (ANTHROPIC_API_KEY, ...).
if LLM_MODEL.startswith("openai") and not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = get_setting(settings.OPENAI_API_KEY)

NO_DETECTION = [float("inf"), float("-inf"), 0]

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


_detection_agent = None
_sponsor_agent = None


def _get_detection_agent():
    global _detection_agent
    if _detection_agent is None:
        _detection_agent = Agent(
            LLM_MODEL,
            output_type=DetectionResult,
            instructions=get_detection_config().assistant_instructions,
        )
    return _detection_agent


def _get_sponsor_agent():
    global _sponsor_agent
    if _sponsor_agent is None:
        _sponsor_agent = Agent(
            LLM_MODEL,
            output_type=SponsorList,
            instructions=get_detection_config().sponsor_instructions,
        )
    return _sponsor_agent


def evaluate_detection(result):
    """Apply confidence/duration rules to a DetectionResult.

    Returns [min_timestamp, max_timestamp, confidence_score], or NO_DETECTION
    when the segment should be kept.
    """
    if not result.timestamps:
        logger.info("No timestamps provided. Returning default values.")
        return NO_DETECTION

    min_timestamp = min(t.start for t in result.timestamps)
    max_timestamp = max(t.end for t in result.timestamps)
    confidence_score = result.confidence_score
    duration = max_timestamp - min_timestamp

    if confidence_score > 80 and duration > 15:
        logger.info(
            f"Confidence Score: {confidence_score}, Timestamps: {min_timestamp} to {max_timestamp}"
        )
    elif confidence_score < CONFIDENCE_SCORE or duration < 20:
        logger.info(
            f"Confidence score below {CONFIDENCE_SCORE} or segment under 20 seconds "
            f"(confidence: {confidence_score}, duration: {duration})"
        )
        return NO_DETECTION

    return [min_timestamp, max_timestamp, confidence_score]


@backoff.on_exception(
    backoff.expo,
    ModelHTTPError,
    max_tries=5,
    giveup=lambda e: e.status_code != 429,
)
def get_specific_timestamps_using_llm(filename, path, sponsors, lock=None):
    """Ask the LLM for ad timestamps in a transcript segment.

    Returns [min_timestamp, max_timestamp, confidence_score].
    """
    logger.info(f"Requesting timestamps for {filename}, sponsors: {sponsors}")

    with open(path, encoding="utf-8") as f:
        transcript = f.read()

    result = _run(
        _get_detection_agent().run(
            f"{get_detection_config().get_detection_instructions(sponsors)}"
            f"\n\nTranscript segments (JSON):\n{transcript}"
        )
    )
    output = result.output
    logger.info(f"Detection result for {filename}: {output}")
    decision = evaluate_detection(output)
    _write_decision(path, output, decision)
    return decision


def _write_decision(transcript_path, output, decision):
    decision_path = transcript_path.replace(".json", "_decision.json")
    try:
        with open(decision_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "confidence_score": output.confidence_score,
                    "timestamps": [t.model_dump() for t in output.timestamps],
                    "reasoning": output.reasoning,
                    "action": "keep" if decision == NO_DETECTION else "cut",
                    "cut_range_seconds": (
                        None if decision == NO_DETECTION else decision[:2]
                    ),
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
