from psycopg2 import sql
from src.db_utils.db_get_conn import get_db_connection
import textwrap
from src.logger.logger_setup import logger
import json


def get_podcast_url(podcast_hash):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                logger.info(f"Getting Podcast url for episode {podcast_hash}")
                # Define the insert query
                read_query =f"""SELECT episode_url, podcast_name from podcast_metadata.pod_w_ads where id = '{podcast_hash}';"""

                # Execute the insert query
                logger.info(f"Executing query:: {read_query}")
                cursor.execute(read_query)
                first_row = cursor.fetchall()
                logger.info(f"Retrieved rows:: {first_row}")
                logger.info(f"URL:: {first_row[0][0]}")
                if first_row:
                    return first_row[0][0]
                else:
                    logger.info("No data found for the given podcast hash.")
                    return None
    except Exception as error:
        logger.error(f"Error reading data: {error}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_cdn_url(podcast_hash):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                logger.info(f"Getting Podcast cdn s3 url for episode {podcast_hash}")
                # Define the insert query
                read_query =f"""SELECT cdn_url, episode_name, episode_uuid from podcast_metadata.s3_metadata where id = '{podcast_hash}';"""

                # Execute the insert query
                logger.info(f"Executing query:: {read_query}")
                cursor.execute(read_query)
                first_row = cursor.fetchall()
                logger.info(f"Retrieved rows:: {first_row}")
                logger.info(f"URL:: {first_row[0][0]}")
                # Check if any row is found
                if first_row:
                    logger.info(f"CDN URL:: {first_row[0][0]}")  # Assuming cdn_url is what you want to log and return
                    return first_row[0][0]  # Return the cdn_url
                else:
                    logger.info("No data found for the given podcast hash.")
                    return None
    except Exception as error:
        logger.error(f"Error reading data: {error}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
