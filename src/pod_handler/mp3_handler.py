import time
import os
import boto3
import datetime
import json
from src.pod_handler.download_mp3 import download_episode
# from src.pod_handler.mp3_converter import remove_ads_from_audio
from src.pod_handler.mp3_converter_whisperx import remove_ads_from_audio
from src.config.constants import *
from src.logger.logger_setup import logger
from src.s3.write_to_s3 import upload_file_to_s3
from src.db_utils import write_to_db


script_dir = os.path.dirname(os.path.realpath(__file__))

try:
    ssm = boto3.client('ssm', 'us-east-1')
    BUCKET_NAME = ssm.get_parameter(Name='/app/app_storage_bucket')['Parameter']['Value']
    logger.info(f"Bucket name::{BUCKET_NAME}")
except Exception as e:
    logger.error(f"Error getting SSM parameters: {e}")
    raise e   


def get_mp3_file(mp3_dir, filename):
    """Get the full path to the single specified mp3 file."""

    # Create the full path to the file
    mp3_file = os.path.join(mp3_dir, filename)

    return mp3_file


def mp3_handler(podcast_name, cdn_url, hashkey, audio_url, episode_data={}, json_data={}):

    # Load the MP3 file
    start_time = time.time()

    logger.info(f"Removing ads from episode and storing in Spaces:: {podcast_name}")

    saved_episode_name = f"{hashkey}.mp3"
    file_size, local_path = download_episode(saved_episode_name, audio_url, DOWNLOAD_DIR)

    podcast_length, original_duration, mp3_output_path = remove_ads_from_audio(audio_file=get_mp3_file(DOWNLOAD_DIR, saved_episode_name))

    logger.info(f"Episode {saved_episode_name} has been processed, ads removed, new duration: "
                f"{podcast_length} vs original duration: {original_duration}")

    end_time = time.time()

    total_processing_time = end_time - start_time

    logger.info(f'Time taken: {total_processing_time} seconds')

    s3_key = f"{podcast_name}/{hashkey}"

    episode_s3_key = f"{s3_key}/{saved_episode_name}"
    s3_location = f"{BUCKET_NAME}/{episode_s3_key}"

    logger.info(f"Uploaded file to {s3_location}")

    upload_file_to_s3(BUCKET_NAME, episode_s3_key, mp3_output_path)

    logger.info(f"Saving hashkey for episode {podcast_name}, hashkey {hashkey}")
    logger.info(f"Episode Length: {podcast_length} seconds, "
                f"Original Duration: {original_duration} seconds, Removed: {original_duration - podcast_length} seconds")

    # Example usage
    write_to_db.insert_podcast_metadata(
        id=hashkey,
        podcast_name=podcast_name,
        episode_uuid=getattr(episode_data, 'uuid', "") or "",
        episode_name=getattr(episode_data, 'name', "") or "",
        episode_guid=getattr(episode_data, 'guid', "") or "",
        episode_hash_name=saved_episode_name or "",
        episode_url=audio_url,
        cdn_url=cdn_url,
        image_url=getattr(episode_data, 'imageUrl', "") or "",
        api_data=json.dumps(json_data) or "",
        api_episode_hash=getattr(episode_data, 'hash', "") or "",
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

    logger.info(f"Data inserted successfully for episode {hashkey}")

    logger.info(f"Updating status for episode {hashkey} to COMPLETED in db podcast_metadata.message_processing")
    write_to_db.update_status(hashkey, 'COMPLETED')

    # write transcripts to s3
    transcript_files = [f for f in os.listdir(script_dir) if f.endswith('_logging.json')]

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

    # Clean up MP3 and WAV files in the downloads directory
    audio_files = [f for f in os.listdir(DOWNLOAD_DIR) if f.endswith('.mp3') or f.endswith('.wav')]
    logger.info(f"Removing local audio files: {audio_files}")
    for audio_file in audio_files:
        try:
            audio_path = os.path.join(DOWNLOAD_DIR, audio_file)
            os.remove(audio_path)
            logger.info(f"Removed local audio file: {audio_path}")
        except Exception as e:
            logger.error(f"Error removing local audio file: {e}")

    # Clean up MP3 and WAV files in the base directory
    audio_files = [f for f in os.listdir(BASE_PATH) if f.endswith('.mp3') or f.endswith('.wav')]
    for audio_file in audio_files:
        try:
            audio_path = os.path.join(BASE_PATH, audio_file)
            os.remove(audio_path)
            logger.info(f"Removed local audio file: {audio_path}")
        except Exception as e:
            logger.error(f"Error removing local audio file: {e}")
