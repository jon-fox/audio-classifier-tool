from psycopg2 import sql
from src.db_utils.db_get_conn import get_db_connection
from src.logger.logger_setup import logger
import hashlib


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
                        cdn_url, api_data, api_episode_hash, local_filename, s3_location,
                        original_duration, ad_time_removed, total_processing_time, 
                        file_size, mime_type, upload_dt
                    ) VALUES (
                        %(id)s, %(podcast_name)s, %(episode_uuid)s, %(episode_name)s, %(episode_guid)s, %(episode_hash_name)s, %(episode_url)s, 
                        %(cdn_url)s, %(api_data)s, %(api_episode_hash)s, %(local_filename)s, %(s3_location)s, 
                        %(original_duration)s, %(ad_time_removed)s, %(total_processing_time)s, 
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
