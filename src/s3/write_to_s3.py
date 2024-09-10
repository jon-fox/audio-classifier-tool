import boto3
from src.utils.logger_setup import logger


def upload_file_to_space(bucket_name, s3_key, local_path):
    """
    Upload an MP3 file to an S3 bucket.

    :param bucket_name: Name of the S3 bucket
    :param local_path: Local path to the MP3 file
    :param s3_key: S3 key where the file will be saved
    """
    try:
        s3 = boto3.client('s3')
    except Exception as e:
        logger.error(f"Error getting S3 client: {e}")
        raise e

    content_type = 'audio/mpeg'
    extra_args = {'ContentType': content_type}

    try:
        logger.info(f"Uploading file to S3, bucket_name::{bucket_name}, local_path::{local_path}, s3_key::{s3_key}")
        s3.upload_file(local_path, bucket_name, s3_key, ExtraArgs=extra_args)
        logger.info("Upload successful")
    except Exception as e:
        logger.error(f"Error uploading file to S3: {e}")
        raise e
