import logging
import boto3
from src.logger.logger_setup import logger

dynamodb = boto3.resource("dynamodb", "us-east-1")
METADATA_TABLE = dynamodb.Table("PodcastS3Metadata")


def get_metadata_item(episode_hash):
    try:
        response = METADATA_TABLE.get_item(Key={"episode_hash": episode_hash})
        return response.get("Item")
    except Exception as e:
        logger.error(f"Error fetching metadata from DynamoDB: {e}")
        return None


def get_podcast_url(podcast_hash):
    try:
        logger.info(f"Getting Podcast url for episode {podcast_hash}")
        item = get_metadata_item(podcast_hash)
        if item and "episode_url" in item:
            logger.info(f"URL:: {item['episode_url']}")
            return item["episode_url"]
        else:
            logger.info("No data found for the given podcast hash.")
            return None
    except Exception as error:
        logger.error(f"Error reading data: {error}")
        return None


def get_cdn_url(podcast_hash):
    try:
        logger.info(f"Getting Podcast cdn s3 url for episode {podcast_hash}")
        item = get_metadata_item(podcast_hash)
        if item and "cdn_url" in item:
            logger.info(f"CDN URL:: {item['cdn_url']}")
            return item["cdn_url"]
        else:
            logger.info("No data found for the given podcast hash.")
            return None
    except Exception as error:
        logger.error(f"Error reading data: {error}")
        return None


def get_cdn_url_and_length(episode_hash):
    item = get_metadata_item(episode_hash)
    if item and "cdn_url" in item:
        return {
            "cdn_url": item["cdn_url"],
            "podcast_length_seconds": item.get("podcast_length_seconds", 0),
        }
    return None


def get_status(episode_hash):
    item = get_metadata_item(episode_hash)
    return item.get("status", "na").lower() if item else "na"


def update_metadata_status(episode_hash, status):
    try:
        METADATA_TABLE.update_item(
            Key={"episode_hash": episode_hash},
            UpdateExpression="SET #s = :s",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": status},
        )
        logger.info(f"Updated status for {episode_hash} to {status} in DynamoDB")
    except Exception as e:
        logger.error(f"Error updating status in DynamoDB: {e}")
