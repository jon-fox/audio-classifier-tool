import time
import os
import datetime
import json
from src.pod_handler.download_mp3 import download_episode

from src.pod_handler.audio_processor import remove_ads_from_audio
from src.config.constants import *
from src.config import settings
from src.config.settings import AWS_ENABLED, get_setting
from src.logger.logger_setup import logger
from src.cloud.aws.write_to_s3 import upload_file_to_s3
from src.cloud.aws import write_to_db
from src.alerts.discord_alerts import send_error_alert

script_dir = os.path.dirname(os.path.realpath(__file__))

BUCKET_NAME = get_setting(settings.APP_STORAGE_BUCKET)
logger.info(f"Bucket name::{BUCKET_NAME}")


def get_mp3_file(mp3_dir, filename):
    """Get the full path to the single specified mp3 file."""

    # Create the full path to the file
    mp3_file = os.path.join(mp3_dir, filename)

    return mp3_file


def mp3_handler(
    podcast_name,
    podcast_description,
    cdn_url,
    hashkey,
    audio_url,
    episode_data={},
    json_data={},
):
    episode_name = (
        getattr(episode_data, "name", "")
        or json_data.get("episodes", [{}])[0].get("name", "Unknown Episode")
        if json_data
        else "Unknown Episode"
    )

    try:
        # Load the MP3 file
        start_time = time.time()

        logger.info(f"Removing ads from episode and storing in Spaces:: {podcast_name}")

        saved_episode_name = f"{hashkey}.mp3"

        try:
            file_size, local_path = download_episode(
                saved_episode_name, audio_url, DOWNLOAD_DIR
            )
        except Exception as e:
            send_error_alert(
                error=e,
                context="Failed to download episode in mp3_handler",
                episode_name=episode_name,
                podcast_name=podcast_name,
                additional_info={
                    "audio_url": audio_url,
                    "hashkey": hashkey,
                    "saved_episode_name": saved_episode_name,
                },
            )
            raise e

        try:
            podcast_length, original_duration, mp3_output_path = remove_ads_from_audio(
                audio_file=get_mp3_file(DOWNLOAD_DIR, saved_episode_name),
                podcast_description=podcast_description,
            )
        except Exception as e:
            send_error_alert(
                error=e,
                context="Failed to remove ads from audio in mp3_handler",
                episode_name=episode_name,
                podcast_name=podcast_name,
                additional_info={
                    "hashkey": hashkey,
                    "audio_file": get_mp3_file(DOWNLOAD_DIR, saved_episode_name),
                    "podcast_description_length": (
                        len(podcast_description) if podcast_description else 0
                    ),
                },
            )
            raise e

        logger.info(
            f"Episode {saved_episode_name} has been processed, ads removed, new duration: "
            f"{podcast_length} vs original duration: {original_duration}"
        )

        end_time = time.time()

        total_processing_time = end_time - start_time

        logger.info(f"Time taken: {total_processing_time} seconds")

        s3_key = f"{podcast_name}/{hashkey}"

        episode_s3_key = f"{s3_key}/{saved_episode_name}"
        s3_location = f"{BUCKET_NAME}/{episode_s3_key}"

        if AWS_ENABLED:
            try:
                upload_file_to_s3(BUCKET_NAME, episode_s3_key, mp3_output_path)
                logger.info(f"Uploaded file to {s3_location}")
            except Exception as e:
                send_error_alert(
                    error=e,
                    context="Failed to upload file to S3 in mp3_handler",
                    episode_name=episode_name,
                    podcast_name=podcast_name,
                    additional_info={
                        "bucket": BUCKET_NAME,
                        "s3_key": episode_s3_key,
                        "local_path": mp3_output_path,
                        "hashkey": hashkey,
                    },
                )
                raise e
        else:
            logger.info(f"Local mode: skipping S3 upload, output at {mp3_output_path}")

        logger.info(f"Saving hashkey for episode {podcast_name}, hashkey {hashkey}")
        logger.info(
            f"Episode Length: {podcast_length} seconds, "
            f"Original Duration: {original_duration} seconds, Removed: {original_duration - podcast_length} seconds"
        )

        if AWS_ENABLED:
            try:
                write_to_db.insert_podcast_metadata(
                    id=hashkey,
                    podcast_name=podcast_name,
                    episode_uuid=getattr(episode_data, "uuid", "") or "",
                    episode_name=getattr(episode_data, "name", "") or "",
                    episode_guid=getattr(episode_data, "guid", "") or "",
                    episode_hash_name=saved_episode_name or "",
                    episode_url=audio_url,
                    cdn_url=cdn_url,
                    image_url=getattr(episode_data, "imageUrl", "") or "",
                    api_data=json.dumps(json_data) or "",
                    api_episode_hash=getattr(episode_data, "hash", "") or "",
                    local_filename=local_path,
                    s3_location=s3_location,
                    podcast_length_seconds=int(podcast_length),
                    original_duration=int(original_duration),
                    ad_time_removed=int(original_duration - podcast_length),
                    total_processing_time=int(total_processing_time),
                    file_size=file_size,
                    mime_type="audio/mpeg",
                    upload_dt=datetime.datetime.now(),
                )
            except Exception as e:
                send_error_alert(
                    error=e,
                    context="Failed to insert podcast metadata in mp3_handler",
                    episode_name=episode_name,
                    podcast_name=podcast_name,
                    additional_info={
                        "hashkey": hashkey,
                        "s3_location": s3_location,
                        "podcast_length": podcast_length,
                        "file_size": file_size,
                    },
                )
                raise e

            logger.info(f"Data inserted successfully for episode {hashkey}")

            logger.info(
                f"Updating status for episode {hashkey} to COMPLETED in db podcast_metadata.message_processing"
            )
            try:
                write_to_db.update_status(hashkey, "COMPLETED")
            except Exception as e:
                send_error_alert(
                    error=e,
                    context="Failed to update status to COMPLETED in mp3_handler",
                    episode_name=episode_name,
                    podcast_name=podcast_name,
                    additional_info={"hashkey": hashkey, "new_status": "COMPLETED"},
                )
                raise e

            # write transcripts to s3
            transcript_files = [
                f for f in os.listdir(script_dir) if f.endswith("_logging.json")
            ]

            # Upload each transcript file to S3
            for transcript_file in transcript_files:
                try:
                    local_path = os.path.join(script_dir, transcript_file)
                    transcript_s3_key = f"{s3_key}/{transcript_file}"
                    upload_file_to_s3(BUCKET_NAME, transcript_s3_key, local_path)

                    logger.info(f"Uploaded transcript file to S3: {transcript_s3_key}")

                    # Remove the transcript file after uploading
                    try:
                        os.remove(local_path)
                        logger.info(f"Removed local transcript file: {local_path}")
                    except Exception as e:
                        logger.error(f"Error removing local transcript file: {e}")
                except Exception as e:
                    logger.error(f"Error uploading transcript file to S3: {e}")
        else:
            logger.info(
                "Local mode: skipping DynamoDB metadata/status writes and transcript upload"
            )

        # Clean up MP3 and WAV files in the downloads directory
        audio_files = [
            f
            for f in os.listdir(DOWNLOAD_DIR)
            if f.endswith(".mp3") or f.endswith(".wav")
        ]
        logger.info(f"Removing local audio files: {audio_files}")
        for audio_file in audio_files:
            try:
                audio_path = os.path.join(DOWNLOAD_DIR, audio_file)
                os.remove(audio_path)
                logger.info(f"Removed local audio file: {audio_path}")
            except Exception as e:
                logger.error(f"Error removing local audio file: {e}")

        # Clean up MP3 and WAV files in the base directory
        audio_files = [
            f for f in os.listdir(BASE_PATH) if f.endswith(".mp3") or f.endswith(".wav")
        ]
        for audio_file in audio_files:
            try:
                audio_path = os.path.join(BASE_PATH, audio_file)
                os.remove(audio_path)
                logger.info(f"Removed local audio file: {audio_path}")
            except Exception as e:
                logger.error(f"Error removing local audio file: {e}")

        return podcast_length

    except Exception as e:
        logger.error(f"Critical error in mp3_handler: {e}")
        send_error_alert(
            error=e,
            context="Critical error in mp3_handler function",
            episode_name=episode_name,
            podcast_name=podcast_name,
            additional_info={
                "hashkey": hashkey,
                "audio_url": audio_url,
                "cdn_url": cdn_url,
            },
        )
        # Update status to FAILED before raising
        if AWS_ENABLED:
            try:
                write_to_db.update_status(hashkey, "FAILED")
            except:
                pass  # Don't fail on status update failure during error handling
        raise e
