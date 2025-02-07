import os
from src.logger.logger_setup import logger
from src.pod_handler.mp3_handler import mp3_handler
import json
import src.db_utils.write_to_db as write_to_db
import boto3
import sys
from datetime import datetime
import requests
from src.metadata.utils import is_terminating, get_instance_id


# uvicorn app:app --reload
# curl -L "http://localhost:8000/stream?url=<MP3_FILE_URL>"
# http://localhost:8000/stream?podcast_name=Darknet%20Diaries
# http://localhost:8000/stream?podcast_name=The%20Jimmy%20DORE%20Show

ssm = boto3.client('ssm', region_name='us-east-1')
sqs_client = boto3.client('sqs', 'us-east-1')
lambda_client = boto3.client('lambda', 'us-east-1')

# Configuration
REGION = os.getenv("REGION", "us-east-1")
BUCKET_NAME = ssm.get_parameter(Name="/app/app_storage_bucket")['Parameter']['Value']
CDN_BASE_URL = ssm.get_parameter(Name="/cloudfront/distribution/url")['Parameter']['Value']
SQS_URL = ssm.get_parameter(Name='/sqs/audio_processing/url')['Parameter']['Value']
# sample cdn url, first part is the cloudfront distribution, 
# the path is the s3 key path
# https://d1234abcdefg.cloudfront.net/path/to/my-object.txt


# Global polling variable
processing_message = False


def prepare_mp3_file(podcast_name, podcast_description, episode_hash, audio_url, json_data={}):
    # async with httpx.AsyncClient() as client:
    logger.info(f"Fetching MP3 file::{audio_url}")
    try:
        s3_path = f"{podcast_name}/{episode_hash}/{episode_hash}.mp3" #HACK may shorten this later
        cdn_url = f"{CDN_BASE_URL}/{s3_path}"
        processed_podcast_length = mp3_handler(podcast_name, podcast_description, cdn_url, episode_hash, audio_url)
        logger.info(f"MP3 file processed::{processed_podcast_length}")
        logger.info(f"Json data from Taddy API::{json_data}")
        logger.info(f"File uploaded to S3::{BUCKET_NAME}, " 
                    f"Episode::{episode_hash}, CDN URL::{cdn_url}")
        return processed_podcast_length, cdn_url
    except Exception as e:
        logger.error(f"Error processing MP3 file::{e}")
        raise e
    

def invoke_rssfeed_update_lambda(sanitized_podcast_name, episode_length, hashkey, audio_url, request_body):
    logger.info(f"Invoking RSS Feed Update Lambda for episode {sanitized_podcast_name}, and hash {hashkey}")

    data = request_body['data']

    payload = {
            'user_feed': data['user_feed'],
            'episodes': data['episodes'],
            'feed_episodes': data['feed_episodes']
        }

    payload['episodes'][0]['url'] = audio_url
    payload['episodes'][0]['podcast_length_seconds'] = str(episode_length)

    data_payload = {'data': payload}

    logger.info(f"Payload for RSS Feed Update Lambda::{data_payload}")

    response = lambda_client.invoke(
        FunctionName='jusskipit_rssfeed_update_lambda',
        InvocationType='Event',  # Asynchronous invocation
        Payload=json.dumps(data_payload)
    )
    logger.info(f"RSS Feed Update Lambda invoked for episode {sanitized_podcast_name}, and hash {hashkey}")
    logger.info(f"Response from RSS Feed Update Lambda: {response}")
    return response


def process_payload(payload={}, receipt_handle=None, message_id=None):
    # Retrieve the payload from the environment variable
    # payload = json.loads(os.getenv('PAYLOAD', payload))
    logger.info(f"Received payload::{payload}")

    if payload:
        # Convert the payload from string to dictionary
        logger.info(f"Received payload: {payload}")
        logger.info(f"Received SQS response receipt_handle: {receipt_handle}, message_id: {message_id}")

        # Process the payload
        logger.info(f"Podcast before sanitization::{payload.get('podcast_name')}")
        podcast_name = write_to_db.sanitize_name(payload.get('podcast_name'))
        episode_name = payload.get('episode_name')
        audio_url = payload.get('audio_url')
        logger.info(f"Processing podcast_name: {podcast_name}, "
                    f"episode_name: {episode_name}, "
                    f"audio_url: {audio_url}")
        episode_hash = write_to_db.generate_hash(podcast_name, episode_name)
        
        instance_id = get_instance_id()
        if instance_id:
            logger.info(f"Running on instance ID: {instance_id}")
        else:
            logger.error("Failed to retrieve instance ID")
            instance_id = "UNKNOWN"
    

        write_to_db.insert_message(
            episode_hash=episode_hash,
            status='PROCESSING',
            message_id=message_id,
            processing_node=instance_id,
            result_data=json.dumps(payload),
            completed_timestamp=datetime.now(),
            aws_request_id=receipt_handle,
            is_archived='N'
        )

        logger.info(f"Status of {podcast_name} for hash {episode_hash} has been updated in meta table to PROCESSING")

        try:
            podcast_description = payload['data']['episodes'][0]['description']
            logger.info(f"Podcast description fetched for processing::{podcast_description}")
        except KeyError:
            podcast_description = ""

        processed_podcast_length, cdn_url = prepare_mp3_file(
            podcast_name=podcast_name, 
            podcast_description=podcast_description, 
            episode_hash=episode_hash, 
            audio_url=audio_url)
        logger.info(f"Processed podcast length::{processed_podcast_length}, CDN URL::{cdn_url}")
        if payload.get('add_to_rss_feed', False):
            logger.info(f"Adding episode to Rss feed::{episode_hash}, invoking rss feed update lambda")
            invoke_rssfeed_update_lambda(podcast_name, processed_podcast_length, episode_hash, cdn_url, payload)
            logger.info(f"RSS Feed Update Lambda invoked for episode {podcast_name}, and hash {episode_hash}")
    else:
        logger.info("No payload received")


def process_message(message_body, receipt_handle, message_id):
    try:
        payload = json.loads(message_body)
        logger.info(f"Processing payload: {payload}")
        process_payload(payload, receipt_handle, message_id)
        logger.info(f"Processed payload: {payload}")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON payload: {e}")
    except Exception as e:
        logger.error(f"Error processing payload: {e}")


def poll_sqs():
    global processing_message
    try:
        
        if not processing_message:
            logger.info("Polling SQS for messages...")

            sqs_response = sqs_client.receive_message(
                QueueUrl=SQS_URL,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=10
            )

            messages = sqs_response.get('Messages', [])
            if not messages:
                logger.info("No messages received")
                return None

            for message in messages:
                receipt_handle = message['ReceiptHandle']
                message_id = message['MessageId']
                body = message['Body']
                logger.info(f"Received message: {body}")

                # Process the message
                processing_message = True
                process_message(body, receipt_handle, message_id)

                # Delete the message from the queue
                sqs_client.delete_message(
                    QueueUrl=SQS_URL,
                    ReceiptHandle=receipt_handle
                )
                logger.info("Message deleted from the queue")
                logger.info("Waiting for next message...")
                processing_message = False
        else:
            logger.info("Processing message, waiting for processing to finish...")

    except Exception as e:
        logger.error(f"Error polling SQS: {e}")
        sys.exit(1)


def main():
    if not SQS_URL:
        logger.error("SQS_QUEUE_URL not found in parameter store /sqs/audio_processing/url")
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