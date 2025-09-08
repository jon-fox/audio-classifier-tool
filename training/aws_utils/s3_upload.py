import boto3
import os

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
    print(f"Uploaded {file_path} to s3://{BUCKET_NAME}/{BUCKET_PATH}{podcast_path}")


def upload_output_files(output_dir: str = "training/output") -> None:
    """
    Upload all files from the output directory to S3.

    Args:
        output_dir (str): The local directory containing files to upload. Defaults to ../transcription
    """
    print(f"Current working directory: {os.getcwd()}")
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), '..', 'transcription')
    
    if not os.path.exists(output_dir):
        print(f"Output directory {output_dir} does not exist.")
        return
    
    for filename in os.listdir(output_dir):
        file_path = os.path.join(output_dir, filename)
        if os.path.isfile(file_path):
            # Use filename as the S3 key
            podcast_path = filename
            upload_to_s3(file_path, podcast_path)
