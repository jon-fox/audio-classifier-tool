import boto3
from src.logger.logger_setup import logger
from src.alerts.discord_alerts import send_error_alert
import mimetypes


def upload_file_to_s3(bucket_name, s3_key, local_path):
    """
    Upload an MP3 file to an S3 bucket.

    :param bucket_name: Name of the S3 bucket
    :param local_path: Local path to the MP3 file
    :param s3_key: S3 key where the file will be saved
    """
    try:
        s3 = boto3.client("s3")
    except Exception as e:
        logger.error(f"Error getting S3 client: {e}")
        send_error_alert(
            error=e,
            context="Failed to create S3 client in upload_file_to_s3",
            additional_info={
                "bucket_name": bucket_name,
                "s3_key": s3_key,
                "local_path": local_path,
            },
        )
        raise e

    if local_path.lower().endswith(".mp3"):
        content_type = "audio/mpeg"
    elif local_path.lower().endswith(".json"):
        content_type = "application/json"
    else:
        content_type, _ = mimetypes.guess_type(local_path)
        if content_type is None:
            content_type = "application/octet-stream"  # Default content type if unknown

    extra_args = {"ContentType": content_type}

    try:
        logger.info(
            f"Uploading file to S3, bucket_name::{bucket_name}, local_path::{local_path}, s3_key::{s3_key}"
        )
        s3.upload_file(local_path, bucket_name, s3_key, ExtraArgs=extra_args)
        logger.info("Upload successful")
    except Exception as e:
        logger.error(f"Error uploading file to S3: {e}")
        send_error_alert(
            error=e,
            context="Failed to upload file to S3 in upload_file_to_s3",
            additional_info={
                "bucket_name": bucket_name,
                "s3_key": s3_key,
                "local_path": local_path,
                "content_type": content_type,
            },
        )
        raise e
