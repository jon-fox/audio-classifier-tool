import requests
from audioclassifier.logger.logger_setup import logger


def get_instance_id():
    try:
        logger.info("Starting to retrieve IMDSv2 token for instance metadata.")
        # Get the IMDSv2 token
        token_url = "http://169.254.169.254/latest/api/token"
        token_headers = {"X-aws-ec2-metadata-token-ttl-seconds": "21600"}
        token_response = requests.put(token_url, headers=token_headers, timeout=1)
        token_response.raise_for_status()
        token = token_response.text
        logger.info("Successfully retrieved token.")

        logger.info("Fetching instance ID using the token.")
        # Use the token to fetch the instance ID
        metadata_url = "http://169.254.169.254/latest/meta-data/instance-id"
        metadata_headers = {"X-aws-ec2-metadata-token": token}
        response = requests.get(metadata_url, headers=metadata_headers, timeout=1)
        response.raise_for_status()
        instance_id = response.text
        logger.info(f"Successfully retrieved instance ID: {instance_id}")
        return instance_id
    except requests.RequestException as e:
        logger.error(f"Error retrieving instance ID: {e}")
        return None
