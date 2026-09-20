import boto3
from audioclassifier.logger.logger_setup import logger
from audioclassifier.alerts.discord_alerts import send_error_alert
from datetime import datetime
import json

dynamodb = boto3.resource("dynamodb", "us-east-1")
METADATA_TABLE = dynamodb.Table("AudioClassifierMetadata")


def insert_audio_metadata(**kwargs):
    try:
        # Extract the audio_hash (id) for the DynamoDB key
        audio_hash = kwargs.get("id")
        if not audio_hash:
            logger.error("audio_hash (id) is required for DynamoDB insert")
            return

        # Prepare the item for DynamoDB
        item = {
            "audio_hash": audio_hash,
            "source": kwargs.get("source", ""),
            "uuid": kwargs.get("uuid", ""),
            "name": kwargs.get("name", ""),
            "guid": kwargs.get("guid", ""),
            "audio_hash_name": kwargs.get("audio_hash_name", ""),
            "audio_url": kwargs.get("audio_url", ""),
            "cdn_url": kwargs.get("cdn_url", ""),
            "image_url": kwargs.get("image_url", ""),
            "api_data": kwargs.get("api_data", ""),
            "api_audio_hash": kwargs.get("api_audio_hash", ""),
            "local_filename": kwargs.get("local_filename", ""),
            "s3_location": kwargs.get("s3_location", ""),
            "original_duration": int(kwargs.get("original_duration", 0)),
            "filtered_duration_seconds": int(kwargs.get("filtered_duration_seconds", 0)),
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
            f"Audio metadata inserted successfully for audio_hash: {audio_hash}"
        )

    except Exception as error:
        logger.error(f"Error inserting audio metadata to DynamoDB: {error}")
        send_error_alert(
            error=error,
            context="Failed to insert audio metadata to DynamoDB",
            additional_info={
                "audio_hash": kwargs.get("id", "unknown"),
                "table_name": "AudioClassifierMetadata",
                "source": kwargs.get("source", "unknown"),
                "name": kwargs.get("name", "unknown"),
            },
        )


def insert_message(
    audio_hash,
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
        "Inserting message processing info into DynamoDB AudioClassifierMetadata table"
    )
    logger.debug(
        f"Parameters: audio_hash={audio_hash}, status={status}, message_id={message_id}, processing_node={processing_node}"
    )

    try:
        timestamp = datetime.utcnow().isoformat()

        # Create or update the item in DynamoDB
        item = {
            "audio_hash": audio_hash,
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
            f"Message processing info inserted for audio_hash: {audio_hash}, message_id: {message_id}"
        )

    except Exception as error:
        logger.error(f"Error inserting message processing data to DynamoDB: {error}")
        send_error_alert(
            error=error,
            context="Failed to insert message processing data to DynamoDB",
            additional_info={
                "audio_hash": audio_hash,
                "message_id": message_id,
                "status": status,
                "table_name": "AudioClassifierMetadata",
            },
        )


def update_status(audio_hash, new_status):
    logger.info("Starting update_status function")
    logger.debug(f"Parameters: audio_hash={audio_hash}, new_status={new_status}")

    try:
        timestamp = datetime.utcnow().isoformat()
        logger.debug(f"Current UTC timestamp: {timestamp}")

        # Update the status in DynamoDB
        METADATA_TABLE.update_item(
            Key={"audio_hash": audio_hash},
            UpdateExpression="SET #status = :status, updated_timestamp = :timestamp",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": new_status.upper(),
                ":timestamp": timestamp,
            },
        )

        logger.info(
            f"Updated status to '{new_status}' for audio_hash: {audio_hash}"
        )

    except Exception as error:
        logger.error(f"Error updating status in DynamoDB: {error}")
        send_error_alert(
            error=error,
            context="Failed to update status in DynamoDB",
            additional_info={
                "audio_hash": audio_hash,
                "new_status": new_status,
                "table_name": "AudioClassifierMetadata",
            },
        )
