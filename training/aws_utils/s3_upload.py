import boto3

BUCKET_NAME = "72b3736a-8a5f-4164-84b4-06121c5a70eb"
BUCKET_PATH = "/training/transcripts/"

s3_client = boto3.client("s3")

def upload_to_s3(file_path: str, podcast_path: str) -> None:
    """
    Upload a file to an S3 bucket.

    Args:
        file_path (str): The local path to the file to upload.
        podcast_path (str): The S3 key (path) where the file will be stored,
        includes podcast name and episode name.
    """
    s3_client.upload_file(file_path, BUCKET_NAME, BUCKET_PATH + podcast_path)