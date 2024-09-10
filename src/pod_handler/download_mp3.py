import os
import requests
from src.logger.logger_setup import logger


def download_episode(episode_name, audio_url, save_path):
    # Extracting the episode name or ID for the filename; adjust as needed

    # Define the full path for the saved file
    if not os.path.exists(save_path):
        os.makedirs(save_path)
        logger.info(f"Created directory {save_path}")

    # Define the full path for the saved file
    file_path = os.path.join(save_path, episode_name)
    logger.info(f"Downloading episode from {audio_url} to {file_path}")
    try:
    # Download the audio file
        response = requests.get(audio_url)
        if response.status_code == 200:
            logger.info(f"Writing episode to file {file_path}")
            # Write the content to a new file in binary write mode
            with open(file_path, 'wb') as file:
                file.write(response.content)
            logger.info(f"Episode saved to {file_path}")
            logger.info(f"File size: {len(response.content)} bytes")
            return os.path.getsize(file_path), file_path # returning file size and file path
        else:
            logger.info("Failed to download the episode")
            logger.info(f"Response status code: {response}")
    except Exception as e:
        logger.error(f"Error downloading episode: {e}")