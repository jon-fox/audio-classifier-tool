from training.transcription.transcribe import remove_ads_from_audio


if __name__ == "__main__":
    # Example usage
    audio_files = ["downloads/potp1201art19.mp3"]  # Add more files as needed
    for audio_file in audio_files:
        remove_ads_from_audio(audio_file, podcast_description="YoDelta sponsor")