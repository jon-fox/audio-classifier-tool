import requests
import boto3
import sys
from src.logger.logger_setup import logger

client = boto3.client("autoscaling", "us-east-1")


def terminate_instance_on_error():
    """Terminate EC2 instance when critical errors occur"""
    try:
        logger.error("Critical error detected - terminating EC2 instance to prevent runaway costs")
        
        instance_id = get_instance_id()
        if instance_id:
            ec2_client = boto3.client("ec2", region_name="us-east-1")
            ec2_client.terminate_instances(InstanceIds=[instance_id])
            logger.info(f"EC2 termination initiated for instance: {instance_id}")
        else:
            logger.error("Cannot get instance ID - falling back to container exit")
            
    except Exception as e:
        logger.error(f"EC2 termination failed: {e} - falling back to container exit")
    
    # If we reach here, either EC2 termination failed or we're being extra safe
    # Exit container so monitoring script can detect and terminate instance
    logger.info("Exiting container - monitoring script will terminate instance")
    sys.exit(1)


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


def is_terminating():
    logger.info("Checking if the instance is terminating.")
    instance_id = get_instance_id()
    if instance_id is None:
        logger.warning("Instance ID not found, returning False for termination state.")
        return False

    logger.info("Retrieving Auto Scaling instances.")
    # Retrieve all Auto Scaling instances
    response = client.describe_auto_scaling_instances()
    instances = response.get("AutoScalingInstances", [])

    # Filter for the current instance
    for instance in instances:
        if instance.get("InstanceId") == instance_id:
            state = instance.get("LifecycleState", "")
            logger.info(f"Found matching instance with state: {state}")
            is_term = state.startswith("Terminating")
            if is_term:
                logger.info("Instance is in a terminating state.")
            else:
                logger.info("Instance is not terminating.")
            return is_term

    logger.warning("Current instance not found in Auto Scaling instances.")
    return False
