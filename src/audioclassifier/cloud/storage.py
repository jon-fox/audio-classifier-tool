"""Optional cloud storage: push a run's outputs to an s3:// location."""

import os

from audioclassifier.logger.logger_setup import logger


def upload_outputs(output_dir, storage_uri):
    """Upload everything under output_dir to storage_uri (s3://bucket/prefix).

    Uses ambient AWS credentials (env/profile/role). Returns the uploaded
    s3:// URIs.
    """
    import boto3

    bucket, prefix = _parse_s3_uri(storage_uri)
    client = boto3.client("s3")
    uploaded = []
    for root, _, files in os.walk(output_dir):
        for filename in files:
            local_path = os.path.join(root, filename)
            relative = os.path.relpath(local_path, output_dir).replace(os.sep, "/")
            key = f"{prefix}/{relative}" if prefix else relative
            client.upload_file(local_path, bucket, key)
            uploaded.append(f"s3://{bucket}/{key}")
            logger.info(f"Uploaded {relative} to s3://{bucket}/{key}")
    return uploaded


def _parse_s3_uri(uri):
    if not uri.startswith("s3://"):
        raise ValueError(f"storage must be an s3:// URI, got {uri!r}")
    bucket, _, prefix = uri[5:].partition("/")
    if not bucket:
        raise ValueError(f"storage URI is missing a bucket: {uri!r}")
    return bucket, prefix.strip("/")
