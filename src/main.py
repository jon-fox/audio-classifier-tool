import os
from src.utils.logger_setup import logger
from src.pod_handler.mp3_handler import mp3_handler
import json
import src.db_utils.write_to_db as write_to_db
import boto3


# uvicorn app:app --reload
# curl -L "http://localhost:8000/stream?url=<MP3_FILE_URL>"
# http://localhost:8000/stream?podcast_name=Darknet%20Diaries
# http://localhost:8000/stream?podcast_name=The%20Jimmy%20DORE%20Show

ssm = boto3.client('ssm', region_name='us-east-1')

# Configuration
REGION = os.getenv("REGION", "us-east-1")
BUCKET_NAME = ssm.get_parameter(Name="/app/app_storage_bucket")['Parameter']['Value']
CDN_BASE_URL = ssm.get_parameter(Name="/cloudfront/distribution/url")['Parameter']['Value']

# sample cdn url, first part is the cloudfront distribution, 
# the path is the s3 key path
# https://d1234abcdefg.cloudfront.net/path/to/my-object.txt


def prepare_mp3_file(podcast_name, episode_hash, audio_url, json_data={}):
    # async with httpx.AsyncClient() as client:
    logger.info(f"Fetching MP3 file::{audio_url}")
    try:
        s3_path = f"{podcast_name}/{episode_hash}.mp3"
        cdn_url = f"{CDN_BASE_URL}/{s3_path}"
        mp3_handler(podcast_name, cdn_url, episode_hash, audio_url)
        logger.info(f"Json data from Taddy API::{json_data}")
        logger.info(f"File uploaded to Space::{BUCKET_NAME}, " 
                    f"Episode::{episode_hash}, CDN URL::{cdn_url}")
    except Exception as e:
        logger.error(f"Error processing MP3 file::{e}")
        raise e


def process_payload(payload={}):
    # Retrieve the payload from the environment variable
    # payload = json.loads(os.getenv('PAYLOAD', payload))
    logger.info(f"Received payload::{payload}")

    if payload:
        # Convert the payload from string to dictionary
        logger.info(f"Received payload: {payload}")

        # Process the payload
        logger.info(f"Podcast before sanitization::{payload.get('podcast_name')}")
        podcast_name = write_to_db.sanitize_name(payload.get('podcast_name'))
        episode_name = payload.get('episode_name')
        audio_url = payload.get('audio_url')
        logger.info(f"Processing podcast_name: {podcast_name}, "
                    f"episode_name: {episode_name}, "
                    f"audio_url: {audio_url}")
        episode_hash = write_to_db.generate_hash(podcast_name, episode_name)
        prepare_mp3_file(podcast_name=podcast_name, episode_hash=episode_hash, audio_url=audio_url)
    else:
        logger.info("No payload received")

if __name__ == "__main__":
    payload = {
        "podcast_name": "Candace",
        "episode_name": "Trump VS Kamala: The Unexpected Winner… | Candace Ep 62",
        "audio_url": "https://pscrb.fm/rss/p/traffic.megaphone.fm/GEORGETOMINC1881985008.mp3?updated=1726094456"
    }
    process_payload(payload)