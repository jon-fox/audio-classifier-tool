import requests
import boto3
from src.logger.logger_setup import logger

client = boto3.client('autoscaling', 'us-east-1')

def get_instance_id():
    try:
        # Get the IMDSv2 token
        token_url = "http://169.254.169.254/latest/api/token"
        token_headers = {"X-aws-ec2-metadata-token-ttl-seconds": "21600"}
        token_response = requests.put(token_url, headers=token_headers, timeout=1)
        token_response.raise_for_status()
        token = token_response.text

        # Use the token to fetch the instance ID
        metadata_url = "http://169.254.169.254/latest/meta-data/instance-id"
        metadata_headers = {"X-aws-ec2-metadata-token": token}
        response = requests.get(metadata_url, headers=metadata_headers, timeout=1)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Error retrieving instance ID: {e}")
        return None

def is_terminating():
    response = client.describe_auto_scaling_instances(InstanceIds=[get_instance_id()])
    instances = response.get('AutoScalingInstances', [])
    if instances:
        state = instances[0].get('LifecycleState')
        return state.startswith('Terminating')
    return False
