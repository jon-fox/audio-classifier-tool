import os
import requests
from audioclassifier.logger.logger_setup import logger
from audioclassifier.alerts.discord_alerts import send_error_alert


def download_audio(filename, audio_url, save_path):
    logger.info(f"Downloading audio {filename} from {audio_url}")

    # Define the full path for the saved file
    if not os.path.exists(save_path):
        os.makedirs(save_path)
        logger.info(f"Created directory {save_path}")

    # Define the full path for the saved file
    file_path = os.path.join(save_path, filename)
    logger.info(f"Downloading audio from {audio_url} to {file_path}")
    try:
        # Download the audio file
        response = requests.get(audio_url)
        if response.status_code == 200:
            logger.info(f"Writing audio to file {file_path}")
            # Write the content to a new file in binary write mode
            with open(file_path, "wb") as file:
                file.write(response.content)
            logger.info(f"Audio saved to {file_path}")
            logger.info(f"File size: {len(response.content)} bytes")
            return (
                os.path.getsize(file_path),
                file_path,
            )  # returning file size and file path
        else:
            error_msg = f"Failed to download the audio. Response status code: {response.status_code}"
            logger.error(error_msg)
            send_error_alert(
                error=error_msg,
                context="HTTP error in download_audio",
                name=filename,
                additional_info={
                    "audio_url": audio_url,
                    "status_code": response.status_code,
                    "response_text": (
                        response.text[:500]
                        if hasattr(response, "text")
                        else "No response text"
                    ),
                },
            )
            raise Exception(error_msg)
    except Exception as e:
        logger.error(f"Error downloading audio: {e}")
        send_error_alert(
            error=e,
            context="Exception in download_audio",
            name=filename,
            additional_info={
                "audio_url": audio_url,
                "save_path": save_path,
                "file_path": file_path,
            },
        )
        raise e
