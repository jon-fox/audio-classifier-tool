import time
import os
import boto3
import datetime
import json
from src.pod_handler.download_mp3 import download_episode
from src.pod_handler.mp3_converter import remove_ads_from_audio
from src.config.constants import *
from src.logger.logger_setup import logger
from src.s3.write_to_s3 import upload_file_to_space
from src.db_utils import write_to_db


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

    podcast_length, original_duration = remove_ads_from_audio(audio_file=get_mp3_file(DOWNLOAD_DIR, saved_episode_name))

    logger.info(f"Episode {saved_episode_name} has been processed, ads removed, new duration: "
                f"{podcast_length} vs original duration: {original_duration}")

    end_time = time.time()

    total_processing_time = end_time - start_time

    logger.info(f'Time taken: {total_processing_time} seconds')

    s3_key = f"{podcast_name}/{saved_episode_name}"
    s3_location = f"{BUCKET_NAME}/{s3_key}"

    logger.info(f"Uploaded file to {s3_location}")

    upload_file_to_space(BUCKET_NAME, s3_key, local_path)

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
