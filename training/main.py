from training.transcription.transcribe import transcribe_for_training


if __name__ == "__main__":
    # Example usage
    audio_files = ["downloads/potp1201art19.mp3"]  # Add more files as needed
    transcribe_for_training(audio_files, compress=False)
