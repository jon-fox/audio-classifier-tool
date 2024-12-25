from psycopg2 import sql
from src.db_utils.db_get_conn import get_db_connection
from src.logger.logger_setup import logger
import hashlib
from datetime import datetime
import json


def generate_hash(podcast_name, episode_name):
    # Concatenate the values to create a unique string
    unique_string = podcast_name + episode_name
    # Generate SHA-256 hash of the unique string
    return hashlib.sha256(unique_string.encode()).hexdigest()

def sanitize_name(name):
    # Define a dictionary of replacements for problematic characters
    replacements = {
        '/': '_',
        '\\': '_',
        ':': '_',
        '*': '_',
        '?': '_',
        '"': '_',
        '<': '_',
        '>': '_',
        '|': '_',
        ' ': '_',
    }
    
    # Replace each problematic character in the filename
    for char, replacement in replacements.items():
        name = name.replace(char, replacement)
    
    return name


def insert_podcast_metadata(**kwargs):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Define the insert query
                insert_query = sql.SQL("""
                    INSERT INTO podcast_metadata.s3_metadata (
                        id, podcast_name, episode_uuid, episode_name, episode_guid, episode_hash_name, episode_url, 
                        cdn_url, image_url, api_data, api_episode_hash, local_filename, s3_location,
                        original_duration, podcast_length_seconds, ad_time_removed, total_processing_time, 
                        file_size, mime_type, upload_dt
                    ) VALUES (
                        %(id)s, %(podcast_name)s, %(episode_uuid)s, %(episode_name)s, %(episode_guid)s, %(episode_hash_name)s, %(episode_url)s, 
                        %(cdn_url)s, %(image_url)s, %(api_data)s, %(api_episode_hash)s, %(local_filename)s, %(s3_location)s, 
                        %(original_duration)s, %(podcast_length_seconds)s, %(ad_time_removed)s, %(total_processing_time)s, 
                        %(file_size)s, %(mime_type)s, %(upload_dt)s
                    )
                """)
                
                # Execute the insert query
                cursor.execute(insert_query, kwargs)

                # Commit the transaction
                conn.commit()

                logger.info("Data inserted successfully.")
    except Exception as error:
        logger.error(f"Error inserting data: {error}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def insert_pod_w_ads(**kwargs):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Define the insert query
                insert_query = sql.SQL("""
                    INSERT INTO podcast_metadata.pod_w_ads (
                        id, podcast_name, episode_uuid, episode_name, episode_guid, episode_url, 
                        api_data, api_episode_hash, local_filename, original_duration, 
                        file_size, mime_type, upload_dt
                    ) VALUES (
                        %(id)s, %(podcast_name)s, %(episode_uuid)s, %(episode_name)s, %(episode_guid)s, %(episode_url)s, 
                        %(api_data)s, %(api_episode_hash)s, %(local_filename)s, %(original_duration)s,
                        %(file_size)s, %(mime_type)s, %(upload_dt)s
                    )
                """)
                
                # Execute the insert query
                cursor.execute(insert_query, kwargs)

                # Commit the transaction
                conn.commit()

                logger.info("Data inserted successfully.")
    except Exception as error:
        logger.error(f"Error inserting data: {error}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def insert_message(episode_hash, status, message_id, processing_node=None, error_details=None, result_data=None, completed_timestamp=None, retry_count=0, priority=0, aws_request_id=None, is_archived=False, processing_duration=None):
    logger.info("Inserting sqs message into the podcast_metadata.message_processing")
    logger.debug(f"Parameters: episode_hash={episode_hash}, status={status}, message_id={message_id}, processing_node={processing_node}, error_details={error_details}, result_data={result_data}, completed_timestamp={completed_timestamp}, retry_count={retry_count}, priority={priority}, source={aws_request_id}, is_archived={is_archived}, processing_duration={processing_duration}")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                timestamp = datetime.utcnow()  # Get the current UTC time

                logger.debug(f"Current UTC timestamp: {timestamp}")

                # Prepare the SQL INSERT statement
                insert_query = sql.SQL("""
                    INSERT INTO podcast_metadata.message_processing (
                        episode_hash, message_id, status, created_timestamp, updated_timestamp, 
                        processing_node, error_details, result_data, completed_timestamp, 
                        retry_count, priority, aws_request_id, is_archived, processing_duration
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """)
                
                logger.debug(f"SQL Insert Query: {insert_query.as_string(cur)}")

                # Execute the query
                cur.execute(insert_query, (
                    episode_hash,
                    message_id,
                    status,
                    timestamp,  # created_timestamp
                    timestamp,  # updated_timestamp
                    processing_node,
                    error_details,
                    json.dumps(result_data) if result_data else None,  # Convert result_data to JSON
                    completed_timestamp,
                    retry_count,
                    priority,
                    aws_request_id,
                    is_archived,
                    processing_duration
                ))

                # Commit the transaction
                conn.commit()

                logger.info(f"Inserted message with episode_hash: {episode_hash} and message_id: {message_id}")
    except Exception as error:
        logger.error(f"Error inserting data in podcast_metadata.message_processing: {error}")
    finally:
        if conn:
            conn.close()
            logger.debug("Database connection closed.")


def update_status(episode_hash, new_status):
    logger.info("Starting update_status function")
    logger.debug(f"Parameters: episode_hash={episode_hash}, new_status={new_status}")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                timestamp = datetime.utcnow()  # Get the current UTC time
                logger.debug(f"Current UTC timestamp: {timestamp}")
                # Prepare the SQL UPDATE statement
                update_query = sql.SQL("""
                    UPDATE podcast_metadata.message_processing
                    SET status = %s,
                        updated_timestamp = %s
                    WHERE episode_hash = %s
                """)

                # Execute the query with the new status and current timestamp
                cur.execute(update_query, (
                    new_status,
                    timestamp,  # Updated timestamp to current UTC time
                    episode_hash
                ))
                logger.info(f"Executed update query for episode_hash: {episode_hash}")

                # Commit the transaction
                conn.commit()
                logger.info(f"Committed transaction for episode_hash: {episode_hash}")

                logger.info(f"Updated status to '{new_status}' for episode_hash: {episode_hash}")
    except Exception as error:
        logger.error(f"Error updating data in podcast_metadata.message_processing: {error}")
    finally:
        if conn:
            conn.close()
            logger.debug("Database connection closed.")
