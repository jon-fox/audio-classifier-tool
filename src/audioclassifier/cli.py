import argparse
import os
import sys

from audioclassifier.logger.logger_setup import configure_logging, logger
from audioclassifier.processing.mp3_handler import mp3_handler
from audioclassifier.config.detection_config import (
    get_detection_config,
    set_detection_config,
)
import json
from audioclassifier.config.constants import USE_TEXT_CLASSIFIER
from audioclassifier.detection.llm_detector import _ensure_api_key
from audioclassifier.util import generate_hash, sanitize_name
from audioclassifier.alerts.discord_alerts import (
    send_error_alert,
    send_processing_alert,
)


def prepare_mp3_file(source, description, audio_hash, audio_url, name):
    logger.info(f"Fetching MP3 file::{audio_url}")

    try:
        result = mp3_handler(
            source,
            description,
            audio_hash,
            audio_url,
            name=name,
        )
        logger.info(f"MP3 file processed::{result}")
        return result
    except Exception as e:
        logger.error(f"Error processing MP3 file::{e}")
        send_error_alert(
            error=e,
            context="MP3 file processing failed in prepare_mp3_file",
            name=name,
            source=source,
            additional_info={
                "audio_url": audio_url,
                "audio_hash": audio_hash,
            },
        )
        raise e


def process_payload(payload={}):
    logger.info(f"Received payload::{payload}")

    if not payload:
        logger.info("No payload received")
        return

    source = sanitize_name(payload.get("source"))
    name = payload.get("name")
    audio_url = payload.get("audio_url")
    logger.info(f"Processing source: {source}, name: {name}, audio_url: {audio_url}")
    audio_hash = generate_hash(source, name)

    description = payload.get("description") or ""
    if description:
        logger.info(f"Description provided for processing::{description}")

    result = prepare_mp3_file(
        source=source,
        description=description,
        audio_hash=audio_hash,
        audio_url=audio_url,
        name=name,
    )
    logger.info(f"Processing result::{result}")

    storage = payload.get("storage")
    if storage:
        from audioclassifier.cloud.storage import upload_outputs

        result["uploaded"] = upload_outputs(
            os.path.dirname(result["output_path"]),
            f"{storage.rstrip('/')}/{source}/{sanitize_name(name)}",
        )

    # Send success alert
    send_processing_alert(
        message_type="success",
        source=source,
        name=name,
        additional_info={
            "Audio Hash": audio_hash,
            "Processed Length": f"{result['filtered_duration']} seconds",
        },
    )

    # This run's decisions are new training data; refresh the classifier
    if USE_TEXT_CLASSIFIER:
        from audioclassifier.detection.text_classifier import retrain_after_run

        retrain_after_run()

    return result


def main():
    configure_logging()

    parser = argparse.ArgumentParser(
        description="AudioClassifier: detect and cut content from audio"
    )
    parser.add_argument(
        "--detection",
        help="detection config: a name in ./configs or a path to a .toon file",
    )
    args = parser.parse_args()
    try:
        config = (
            set_detection_config(args.detection)
            if args.detection
            else get_detection_config()
        )
    except (RuntimeError, FileNotFoundError, ValueError) as e:
        logger.error(str(e))
        print(e, file=sys.stderr)
        sys.exit(1)
    logger.info(f"Using detection config: {config.name}")

    try:
        _ensure_api_key()
    except RuntimeError as e:
        logger.error(str(e))
        print(e, file=sys.stderr)
        sys.exit(1)

    payload = os.getenv("PAYLOAD")
    if not payload:
        message = (
            'Set PAYLOAD to a JSON object like {"source": ..., '
            '"name": ..., "audio_url": ...} — see README.md'
        )
        logger.error(message)
        print(message, file=sys.stderr)
        sys.exit(1)
    process_payload(json.loads(payload))


if __name__ == "__main__":
    main()
