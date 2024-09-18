import os
from src.logger.logger_setup import logger
from src.pod_handler.mp3_handler import mp3_handler
import json
import src.db_utils.write_to_db as write_to_db
import src.db_utils.read_db as read_db
import boto3
import sys


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
        if source_url := read_db.get_cdn_url(episode_hash):
            logger.info(f"Episode exists in the database, Podcast Name {podcast_name}, Episode Name {episode_name}")
            logger.info(f"Episode CDN URL::{source_url}")
        else:
            logger.info(f"Episode does not exist in the database, Podcast Name {podcast_name}, Episode Name {episode_name}")
            prepare_mp3_file(podcast_name=podcast_name, episode_hash=episode_hash, audio_url=audio_url)
    else:
        logger.info("No payload received")


def main(payload={}):
    if payload:
        logger.info(f"Received payload: {payload}")
        process_payload(payload)
    elif len(sys.argv) > 1:
        payload_str = sys.argv[1]
        try:
            payload = json.loads(payload_str)
            logger.info(f"Received payload: {payload}")
            
            # Process the payload
            process_payload(payload)
            logger.info(f"Procesed payload::{payload}")
        except json.JSONDecodeError:
            logger.error("Invalid JSON payload")
        except Exception as e:
            logger.error(f"Error processing payload: {e}")
            raise e
    else:
        logger.error("No payload provided")
        sys.exit(1)


if __name__ == "__main__":
    payload = {
        "podcast_name": "Candace",
        "episode_name": "URGENT: Trump Must Drop JD Vance To Avoid Another Assassination Attempt | Candace Ep 65",
        "audio_url": "https://pscrb.fm/rss/p/traffic.megaphone.fm/GEORGETOMINC9411721285.mp3?updated=1726522694"
    }

    # payload = {
    #     "podcast_name": "The Boyscast with Ryan Long",
    #     "episode_name": "The Debate Aftermath, Article Calls Believing in Aliens Dangerous, Jaoquin Phoenix Walks Off Movie For Being too Gay",
    #     "audio_url": "https://www.podtrac.com/pts/redirect.mp3/pdst.fm/e/chrt.fm/track/7GB118/pscrb.fm/rss/p/mgln.ai/e/35/arttrk.com/p/ADCT2/clrtpod.com/m/traffic.megaphone.fm/ADV8126990425.mp3?updated=1726194017"
    # }

    main(payload)