import argparse
import os
import sys

from audioclassifier.logger.logger_setup import configure_logging, logger
from audioclassifier.pod_handler.mp3_handler import mp3_handler
from audioclassifier.config.detection_config import (
    get_detection_config,
    set_detection_config,
)
import json
from datetime import datetime
from audioclassifier.config.constants import USE_TEXT_CLASSIFIER
from audioclassifier.config.settings import AWS_ENABLED
from audioclassifier.cloud.aws import write_to_db
from audioclassifier.cloud.aws.ec2 import get_instance_id
from audioclassifier.alerts.discord_alerts import send_error_alert, send_processing_alert


def prepare_mp3_file(
    podcast_name, podcast_description, episode_hash, audio_url, episode_name, json_data={}
):
    logger.info(f"Fetching MP3 file::{audio_url}")

    try:
        result = mp3_handler(
            podcast_name,
            podcast_description,
            episode_hash,
            audio_url,
            episode_name=episode_name,
        )
        logger.info(f"MP3 file processed::{result}")
        return result
    except Exception as e:
        logger.error(f"Error processing MP3 file::{e}")
        send_error_alert(
            error=e,
            context="MP3 file processing failed in prepare_mp3_file",
            episode_name=(
                json_data.get("episodes", [{}])[0].get("name", "Unknown Episode")
                if json_data
                else "Unknown Episode"
            ),
            podcast_name=podcast_name,
            additional_info={
                "audio_url": audio_url,
                "episode_hash": episode_hash,
            },
        )
        raise e


def process_payload(payload={}):
    logger.info(f"Received payload::{payload}")

    if not payload:
        logger.info("No payload received")
        return

    logger.info(f"Podcast before sanitization::{payload.get('podcast_name')}")
    podcast_name = write_to_db.sanitize_name(payload.get("podcast_name"))
    episode_name = payload.get("episode_name")
    audio_url = payload.get("audio_url")
    logger.info(
        f"Processing podcast_name: {podcast_name}, "
        f"episode_name: {episode_name}, "
        f"audio_url: {audio_url}"
    )
    episode_hash = write_to_db.generate_hash(podcast_name, episode_name)

    instance_id = get_instance_id() if AWS_ENABLED else None
    if instance_id:
        logger.info(f"Running on instance ID: {instance_id}")
    else:
        instance_id = "LOCAL" if not AWS_ENABLED else "UNKNOWN"

    if AWS_ENABLED:
        write_to_db.insert_message(
            episode_hash=episode_hash,
            status="PROCESSING",
            message_id=None,
            processing_node=instance_id,
            result_data=payload,
            completed_timestamp=datetime.now(),
            aws_request_id=None,
            is_archived=False,
        )

        logger.info(
            f"Status of {podcast_name} for hash {episode_hash} has been updated in meta table to PROCESSING"
        )
    else:
        logger.info("Local mode: skipping DynamoDB PROCESSING status write")

    try:
        podcast_description = payload["data"]["episodes"][0]["description"]
        logger.info(
            f"Podcast description fetched for processing::{podcast_description}"
        )
    except KeyError:
        podcast_description = ""

    result = prepare_mp3_file(
        podcast_name=podcast_name,
        podcast_description=podcast_description,
        episode_hash=episode_hash,
        audio_url=audio_url,
        episode_name=episode_name,
    )
    logger.info(f"Processing result::{result}")

    # Send success alert
    send_processing_alert(
        message_type="success",
        podcast_name=podcast_name,
        episode_name=episode_name,
        additional_info={
            "Episode Hash": episode_hash,
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
        description="AudioClassifier: detect and cut content from podcast audio"
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

    payload = os.getenv("PAYLOAD")
    if not payload:
        logger.error(
            'Set PAYLOAD to a JSON object like {"podcast_name": ..., '
            '"episode_name": ..., "audio_url": ...} — see README.md'
        )
        sys.exit(1)
    process_payload(json.loads(payload))


if __name__ == "__main__":
    main()
