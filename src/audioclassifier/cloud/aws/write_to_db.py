import boto3
from audioclassifier.logger.logger_setup import logger
from audioclassifier.alerts.discord_alerts import send_error_alert
import hashlib
from datetime import datetime
import json

dynamodb = boto3.resource("dynamodb", "us-east-1")
METADATA_TABLE = dynamodb.Table("PodcastS3Metadata")


def generate_hash(podcast_name, episode_name):
    # Concatenate the values to create a unique string
    unique_string = podcast_name + episode_name
    # Generate SHA-256 hash of the unique string
    return hashlib.sha256(unique_string.encode()).hexdigest()


def sanitize_name(name):
    # Define a dictionary of replacements for problematic characters
    replacements = {
        "/": "_",
        "\\": "_",
        ":": "_",
        "*": "_",
        "?": "_",
        '"': "_",
        "<": "_",
        ">": "_",
        "|": "_",
        " ": "_",
    }

    # Replace each problematic character in the filename
    for char, replacement in replacements.items():
        name = name.replace(char, replacement)

    return name


def insert_podcast_metadata(**kwargs):
    try:
        # Extract the episode_hash (id) for the DynamoDB key
        episode_hash = kwargs.get("id")
        if not episode_hash:
            logger.error("episode_hash (id) is required for DynamoDB insert")
            return

        # Prepare the item for DynamoDB
        item = {
            "episode_hash": episode_hash,
            "podcast_name": kwargs.get("podcast_name", ""),
            "episode_uuid": kwargs.get("episode_uuid", ""),
            "episode_name": kwargs.get("episode_name", ""),
            "episode_guid": kwargs.get("episode_guid", ""),
            "episode_hash_name": kwargs.get("episode_hash_name", ""),
            "episode_url": kwargs.get("episode_url", ""),
            "cdn_url": kwargs.get("cdn_url", ""),
            "image_url": kwargs.get("image_url", ""),
            "api_data": kwargs.get("api_data", ""),
            "api_episode_hash": kwargs.get("api_episode_hash", ""),
            "local_filename": kwargs.get("local_filename", ""),
            "s3_location": kwargs.get("s3_location", ""),
            "original_duration": int(kwargs.get("original_duration", 0)),
            "podcast_length_seconds": int(kwargs.get("podcast_length_seconds", 0)),
            "ad_time_removed": int(kwargs.get("ad_time_removed", 0)),
            "total_processing_time": int(kwargs.get("total_processing_time", 0)),
            "file_size": int(kwargs.get("file_size", 0)),
            "mime_type": kwargs.get("mime_type", ""),
            "upload_dt": kwargs.get("upload_dt", datetime.utcnow()).isoformat(),
            "status": "COMPLETED",
            "updated_timestamp": datetime.utcnow().isoformat(),
        }

        # Insert into DynamoDB
        METADATA_TABLE.put_item(Item=item)
        logger.info(
            f"Podcast metadata inserted successfully for episode_hash: {episode_hash}"
        )

    except Exception as error:
        logger.error(f"Error inserting podcast metadata to DynamoDB: {error}")
        send_error_alert(
            error=error,
            context="Failed to insert podcast metadata to DynamoDB",
            additional_info={
                "episode_hash": kwargs.get("id", "unknown"),
                "table_name": "PodcastS3Metadata",
                "podcast_name": kwargs.get("podcast_name", "unknown"),
                "episode_name": kwargs.get("episode_name", "unknown"),
            },
        )


def insert_message(
    episode_hash,
    status,
    message_id,
    processing_node=None,
    error_details=None,
    result_data=None,
    completed_timestamp=None,
    retry_count=0,
    priority=0,
    aws_request_id=None,
    is_archived=False,
    processing_duration=None,
):
    logger.info(
        "Inserting message processing info into DynamoDB PodcastS3Metadata table"
    )
    logger.debug(
        f"Parameters: episode_hash={episode_hash}, status={status}, message_id={message_id}, processing_node={processing_node}"
    )

    try:
        timestamp = datetime.utcnow().isoformat()

        # Create or update the item in DynamoDB
        item = {
            "episode_hash": episode_hash,
            "status": status.upper(),
            "message_id": message_id,
            "created_timestamp": timestamp,
            "updated_timestamp": timestamp,
            "processing_node": processing_node or "",
            "error_details": error_details or "",
            "result_data": json.dumps(result_data) if result_data else "",
            "completed_timestamp": (
                completed_timestamp.isoformat() if completed_timestamp else ""
            ),
            "retry_count": int(retry_count),
            "priority": int(priority),
            "aws_request_id": aws_request_id or "",
            "is_archived": "Y" if is_archived else "N",
            "processing_duration": (
                int(processing_duration) if processing_duration else 0
            ),
        }

        METADATA_TABLE.put_item(Item=item)
        logger.info(
            f"Message processing info inserted for episode_hash: {episode_hash}, message_id: {message_id}"
        )

    except Exception as error:
        logger.error(f"Error inserting message processing data to DynamoDB: {error}")
        send_error_alert(
            error=error,
            context="Failed to insert message processing data to DynamoDB",
            additional_info={
                "episode_hash": episode_hash,
                "message_id": message_id,
                "status": status,
                "table_name": "PodcastS3Metadata",
            },
        )


def update_status(episode_hash, new_status):
    logger.info("Starting update_status function")
    logger.debug(f"Parameters: episode_hash={episode_hash}, new_status={new_status}")

    try:
        timestamp = datetime.utcnow().isoformat()
        logger.debug(f"Current UTC timestamp: {timestamp}")

        # Update the status in DynamoDB
        METADATA_TABLE.update_item(
            Key={"episode_hash": episode_hash},
            UpdateExpression="SET #status = :status, updated_timestamp = :timestamp",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": new_status.upper(),
                ":timestamp": timestamp,
            },
        )

        logger.info(
            f"Updated status to '{new_status}' for episode_hash: {episode_hash}"
        )

    except Exception as error:
        logger.error(f"Error updating status in DynamoDB: {error}")
        send_error_alert(
            error=error,
            context="Failed to update status in DynamoDB",
            additional_info={
                "episode_hash": episode_hash,
                "new_status": new_status,
                "table_name": "PodcastS3Metadata",
            },
        )
