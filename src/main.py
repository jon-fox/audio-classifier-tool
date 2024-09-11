import os
import httpx
from src.utils.logger_setup import logger
from urllib.parse import quote, unquote
from src.pod_handler.mp3_handler import mp3_handler
import datetime
import json
from pydantic import BaseModel
import aiohttp
from urllib.parse import urlparse, urlunparse
import uvicorn
import multiprocessing


# uvicorn app:app --reload
# curl -L "http://localhost:8000/stream?url=<MP3_FILE_URL>"
# http://localhost:8000/stream?podcast_name=Darknet%20Diaries
# http://localhost:8000/stream?podcast_name=The%20Jimmy%20DORE%20Show


# Configuration
REGION = os.getenv("REGION")
BUCKET_NAME = os.getenv("BUCKET_NAME")
CDN_BASE_URL = os.getenv("CDN_URL")

# sample cdn url, first part is the cloudfront distribution, the path is the s3 key path
# https://d1234abcdefg.cloudfront.net/path/to/my-object.txt


def get_mp3_file(podcast_name, episode_hash, audio_url, json_data={}):
    # async with httpx.AsyncClient() as client:
    logger.info(f"Fetching MP3 file::{audio_url}")
    try:
        s3_path = f"{podcast_name}/{episode_hash}.mp3"
        cdn_url = f"{CDN_BASE_URL}/{s3_path}"
        mp3_handler(podcast_name, cdn_url, episode_hash, audio_url)
        logger.info(f"Json data from Taddy API::{json_data}")
        logger.info(f"File uploaded to Space::{BUCKET_NAME}, Episode::{episode_hash}, CDN URL::{cdn_url}")
    except Exception as e:
        logger.error(f"Error processing MP3 file::{e}")
        raise e


def process_payload():
    # Retrieve the payload from the environment variable
    payload_str = os.getenv('PAYLOAD')

    if payload_str:
        # Convert the payload from string to dictionary
        payload = json.loads(payload_str)
        logger.info(f"Received payload: {payload}")

        # Process the payload
        key1 = payload.get('key1')
        key2 = payload.get('key2')
        logger.info(f"Processing key1: {key1}, key2: {key2}")
    else:
        logger.info("No payload received")

if __name__ == "__main__":
    process_payload()