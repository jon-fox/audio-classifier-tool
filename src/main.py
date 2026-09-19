import os
from src.logger.logger_setup import logger
from src.pod_handler.mp3_handler import mp3_handler
import json
import sys
from datetime import datetime
from src.config import settings
from src.config.settings import AWS_ENABLED, get_setting
from src.cloud.aws import write_to_db, queue
from src.cloud.aws.ec2 import (
    is_terminating,
    get_instance_id,
    terminate_instance_on_error,
)
from src.alerts.discord_alerts import send_error_alert, send_processing_alert

# uvicorn app:app --reload
# curl -L "http://localhost:8000/stream?url=<MP3_FILE_URL>"
# http://localhost:8000/stream?podcast_name=Darknet%20Diaries
# http://localhost:8000/stream?podcast_name=The%20Jimmy%20DORE%20Show

# Configuration (env vars first; remote parameters when APP_MODE=aws)
REGION = settings.REGION
BUCKET_NAME = get_setting(settings.APP_STORAGE_BUCKET)
CDN_BASE_URL = get_setting(settings.CDN_BASE_URL)
SQS_URL = get_setting(settings.SQS_URL)
# sample cdn url, first part is the cloudfront distribution,
# the path is the s3 key path
# https://d1234abcdefg.cloudfront.net/path/to/my-object.txt


# Global polling variable
processing_message = False


def prepare_mp3_file(
    podcast_name, podcast_description, episode_hash, audio_url, json_data={}
):
    # async with httpx.AsyncClient() as client:
    logger.info(f"Fetching MP3 file::{audio_url}")
    s3_path = f"{podcast_name}/{episode_hash}/{episode_hash}.mp3"  # HACK may shorten this later
    cdn_url = f"{CDN_BASE_URL}/{s3_path}" if CDN_BASE_URL else ""

    try:
        processed_podcast_length = mp3_handler(
            podcast_name, podcast_description, cdn_url, episode_hash, audio_url
        )
        logger.info(f"MP3 file processed::{processed_podcast_length}")
        logger.info(f"Json data from Taddy API::{json_data}")
        logger.info(
            f"File uploaded to S3::{BUCKET_NAME}, "
            f"Episode::{episode_hash}, CDN URL::{cdn_url}"
        )
        return processed_podcast_length, cdn_url
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
                "cdn_url": cdn_url,
            },
        )
        raise e


def invoke_rssfeed_update_lambda(
    sanitized_podcast_name, episode_length, hashkey, audio_url, request_body
):
    logger.info(
        f"Invoking RSS Feed Update Lambda for episode {sanitized_podcast_name}, and hash {hashkey}"
    )

    data = request_body["data"]

    payload = {
        "user_feed": data["user_feed"],
        "episodes": data["episodes"],
        "feed_episodes": data["feed_episodes"],
    }

    payload["episodes"][0]["url"] = audio_url
    payload["episodes"][0]["podcast_length_seconds"] = str(episode_length)

    data_payload = {"data": payload}

    logger.info(f"Payload for RSS Feed Update Lambda::{data_payload}")

    response = queue.invoke_lambda(
        "jusskipit_rssfeed_update_lambda", json.dumps(data_payload)
    )
    logger.info(
        f"RSS Feed Update Lambda invoked for episode {sanitized_podcast_name}, and hash {hashkey}"
    )
    logger.info(f"Response from RSS Feed Update Lambda: {response}")
    return response


def process_payload(payload={}, receipt_handle=None, message_id=None):
    # Retrieve the payload from the environment variable
    # payload = json.loads(os.getenv('PAYLOAD', payload))
    logger.info(f"Received payload::{payload}")

    if payload:
        # Convert the payload from string to dictionary
        logger.info(f"Received payload: {payload}")
        logger.info(
            f"Received SQS response receipt_handle: {receipt_handle}, message_id: {message_id}"
        )

        # Process the payload
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
                message_id=message_id,
                processing_node=instance_id,
                result_data=payload,
                completed_timestamp=datetime.now(),
                aws_request_id=receipt_handle,
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

        processed_podcast_length, cdn_url = prepare_mp3_file(
            podcast_name=podcast_name,
            podcast_description=podcast_description,
            episode_hash=episode_hash,
            audio_url=audio_url,
        )
        logger.info(
            f"Processed podcast length::{processed_podcast_length}, CDN URL::{cdn_url}"
        )

        if AWS_ENABLED and payload.get("add_to_rss_feed", False):
            logger.info(
                f"Adding episode to Rss feed::{episode_hash}, invoking rss feed update lambda"
            )
            invoke_rssfeed_update_lambda(
                podcast_name, processed_podcast_length, episode_hash, cdn_url, payload
            )
            logger.info(
                f"RSS Feed Update Lambda invoked for episode {podcast_name}, and hash {episode_hash}"
            )

        # Send success alert
        send_processing_alert(
            message_type="success",
            podcast_name=podcast_name,
            episode_name=episode_name,
            additional_info={
                "Episode Hash": episode_hash,
                "Processed Length": f"{processed_podcast_length} seconds",
                "CDN URL": cdn_url,
                "Added to RSS": (
                    "Yes" if payload.get("add_to_rss_feed", False) else "No"
                ),
            },
        )
    else:
        logger.info("No payload received")


def process_message(message_body, receipt_handle, message_id):
    episode_name = "Unknown Episode"
    podcast_name = "Unknown Podcast"

    try:
        payload = json.loads(message_body)
        logger.info(f"Processing payload: {payload}")

        # Extract episode info for error reporting
        episode_name = payload.get("episode_name", "Unknown Episode")
        podcast_name = payload.get("podcast_name", "Unknown Podcast")

        # Send processing started alert
        send_processing_alert(
            message_type="started",
            podcast_name=podcast_name,
            episode_name=episode_name,
            additional_info={
                "Message ID": message_id,
                "Audio URL": payload.get("audio_url", "Unknown"),
                "Add to RSS": "Yes" if payload.get("add_to_rss_feed", False) else "No",
            },
        )

        process_payload(payload, receipt_handle, message_id)
        logger.info(f"Processed payload: {payload}")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON payload: {e}")
        send_error_alert(
            error=e,
            context="JSON decode error in process_message",
            episode_name=episode_name,
            podcast_name=podcast_name,
            additional_info={
                "message_id": message_id,
                "receipt_handle": receipt_handle,
                "message_body": (
                    message_body[:500] + "..."
                    if len(message_body) > 500
                    else message_body
                ),
            },
        )
        # Mark as failed in database if possible
        terminate_instance_on_error()
    except Exception as e:
        logger.error(f"Critical error processing payload: {e}")
        send_error_alert(
            error=e,
            context="Critical error in process_message",
            episode_name=episode_name,
            podcast_name=podcast_name,
            additional_info={
                "message_id": message_id,
                "receipt_handle": receipt_handle,
            },
        )
        # Send additional error alert with message payload
        send_error_alert(
            error=e,
            context="Message payload causing critical error",
            episode_name=episode_name,
            podcast_name=podcast_name,
            additional_info={
                "message_id": message_id,
                "receipt_handle": receipt_handle,
                "message_body": (
                    message_body[:500] + "..."
                    if len(message_body) > 500
                    else message_body
                ),
            },
        )
        # Delete the message from the queue
        try:
            queue.delete_message(SQS_URL, receipt_handle)
            logger.info("Failed message deleted from the queue")
        except Exception as delete_error:
            logger.error(f"Failed to delete message from queue: {delete_error}")
        # Mark as failed in database if possible
        terminate_instance_on_error()


def poll_sqs():
    global processing_message
    try:
        if not processing_message:
            logger.info("Polling SQS for messages...")

            sqs_response = queue.receive_message(SQS_URL)

            messages = sqs_response.get("Messages", [])
            if not messages:
                logger.info("No messages received")
                return None

            for message in messages:
                receipt_handle = message["ReceiptHandle"]
                message_id = message["MessageId"]
                body = message["Body"]
                logger.info(f"Received message: {body}")

                # Process the message
                processing_message = True
                process_message(body, receipt_handle, message_id)

                # Delete the message from the queue
                queue.delete_message(SQS_URL, receipt_handle)
                logger.info("Message deleted from the queue")
                logger.info("Waiting for next message...")
                processing_message = False
        else:
            logger.info("Processing message, waiting for processing to finish...")

    except Exception as e:
        logger.error(f"Critical error polling SQS: {e}")
        send_error_alert(
            error=e,
            context="Critical error in poll_sqs function",
            additional_info={
                "sqs_url": SQS_URL,
                "processing_message": processing_message,
            },
        )
        terminate_instance_on_error()
        sys.exit(1)


def main():
    if not AWS_ENABLED:
        # Local mode: process a single episode from the PAYLOAD env var, then exit
        payload = os.getenv("PAYLOAD")
        if not payload:
            logger.error(
                'Local mode: set PAYLOAD to a JSON object like {"podcast_name": ..., '
                '"episode_name": ..., "audio_url": ...} — see local.md'
            )
            sys.exit(1)
        process_payload(json.loads(payload))
        return

    if not SQS_URL:
        logger.error(
            "SQS_QUEUE_URL not found in parameter store /sqs/audio_processing/url"
        )
        sys.exit(1)

    while not is_terminating():
        poll_sqs()


if __name__ == "__main__":
    main()

    # payload = {
    #     "podcast_name": "Candace",
    #     "episode_name": "URGENT: Trump Must Drop JD Vance To Avoid Another Assassination Attempt | Candace Ep 65",
    #     "audio_url": "https://pscrb.fm/rss/p/traffic.megaphone.fm/GEORGETOMINC9411721285.mp3?updated=1726522694"
    # }

    # payload = {
    #     "podcast_name": "The Boyscast with Ryan Long",
    #     "episode_name": "The Debate Aftermath, Article Calls Believing in Aliens Dangerous, Jaoquin Phoenix Walks Off Movie For Being too Gay",
    #     "audio_url": "https://www.podtrac.com/pts/redirect.mp3/pdst.fm/e/chrt.fm/track/7GB118/pscrb.fm/rss/p/mgln.ai/e/35/arttrk.com/p/ADCT2/clrtpod.com/m/traffic.megaphone.fm/ADV8126990425.mp3?updated=1726194017"
    # }

    # export PAYLOAD='{"podcast_name": "Candace", "episode_name": "URGENT: Trump Must Drop JD Vance To Avoid Another Assassination Attempt | Candace Ep 65", "audio_url": "https://pscrb.fm/rss/p/traffic.megaphone.fm/GEORGETOMINC9411721285.mp3?updated=1726522694"}'
