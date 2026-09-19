from training.transcription.transcribe import (
    label_ads_from_audio,
    create_transcript_structure,
)
from training.aws_utils.s3_upload import upload_output_files
import time

if __name__ == "__main__":
    # Example usage
    audio_files = ["downloads/potp1201art19.mp3"]  # Add more files as needed
    for audio_file in audio_files:
        podcast_name = audio_file.split("/")[-1].split(".")[0]
        label_ads_from_audio(audio_file, podcast_description="YoDelta sponsor")
        print(f"Processing podcast: {podcast_name}")
        time.sleep(2)
        create_transcript_structure(podcast_name=podcast_name, write_to_file=True)

    upload_output_files()
