import asyncio
import os

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

import backoff
from pydantic import BaseModel
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


class Timestamp(BaseModel):
    start: float
    end: float


class DetectionResult(BaseModel):
    confidence_score: int
    timestamps: list[Timestamp]


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

    # asyncio.run (rather than run_sync) so each worker thread's event loop is
    # closed cleanly instead of leaking until garbage collection
    result = asyncio.run(
        _get_detection_agent().run(
            f"{get_detection_config().get_detection_instructions(sponsors)}"
            f"\n\nTranscript segments (JSON):\n{transcript}"
        )
    )
    logger.info(f"Detection result for {filename}: {result.output}")
    return evaluate_detection(result.output)


def fetch_sponsors(podcast_description):
    if not get_detection_config().sponsor_instructions:
        logger.info("No sponsor_instructions in detection config, skipping")
        return []
    logger.info(f"Fetching sponsors for podcast description: {podcast_description}")
    try:
        result = asyncio.run(_get_sponsor_agent().run(podcast_description))
        sponsors = result.output.sponsors
        logger.info(f"Sponsors: {sponsors}")
        return sponsors
    except Exception as e:
        logger.error(f"Error fetching sponsors: {e}")
        return []
