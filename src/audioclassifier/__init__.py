"""AudioClassifier: detect and cut target segments (ads by default) from podcast audio."""


def process_episode(podcast_name, episode_name, audio_url, detection=None):
    """Process one episode: download, transcribe, detect, and cut.

    detection: optional config name (bundled or in ./configs) or path to a
    .toon file. Returns a dict with output_path, filtered_duration,
    original_duration, and seconds_removed.

    Configure the "audioclassifier" logger to see progress; set OPENAI_API_KEY
    (or the provider key matching LLM_MODEL) before calling.
    """
    if detection:
        from audioclassifier.config.detection_config import set_detection_config

        set_detection_config(detection)

    from audioclassifier.cli import process_payload

    return process_payload(
        {
            "podcast_name": podcast_name,
            "episode_name": episode_name,
            "audio_url": audio_url,
        }
    )
