import psycopg2
import boto3
from src.config.constants import DB_INFO
from src.logger.logger_setup import logger
import os
import json

def get_db_connection():
    logger.info(f"Connecting to database with credentials from Secrets Manager")

    try:
        # Create a boto3 client for Secrets Manager
        secrets_client = boto3.client('secretsmanager', region_name=DB_INFO['region'])

        # Retrieve the secret value
        secret_response = secrets_client.get_secret_value(SecretId=DB_INFO['secret_arn'])
        secret_string = secret_response['SecretString']
        secret = json.loads(secret_string)
        logger.info(f"Secret retrieved successfully")

        # Extract the username and password from the secret
        db_username = secret['username']
        db_password = secret['password']

        script_dir = os.path.dirname(os.path.abspath(__file__))
        ca_cert_path = os.path.join(script_dir, '../../certs/us-east-1-bundle.pem')

        logger.info(f"Connecting to database::{DB_INFO['dbname']}")

        # Connect to the PostgreSQL database using the IAM token and CA certificate
        connection = psycopg2.connect(
            dbname=DB_INFO['dbname'],
            user=db_username,
            password=db_password,
            host=DB_INFO['host'],
            port=DB_INFO['port'],
            sslmode='require',
            sslrootcert=ca_cert_path
        )
        logger.info(f"Connected to database successfully")
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise e

    return connection