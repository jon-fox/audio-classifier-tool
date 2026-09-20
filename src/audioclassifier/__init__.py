"""AudioClassifier: detect and cut target segments from audio, defined by your detection config."""


def process_audio(
    source,
    name,
    audio_url,
    detection=None,
    detection_instructions=None,
    detection_keywords=None,
    description=None,
    storage=None,
):
    """Process one audio file: download, transcribe, detect, and cut.

    source groups outputs (output/<source>/<name>/); name is used for the
    output filenames. detection: a config name (in ./configs) or a .toon path;
    detection_instructions / detection_keywords override the selected config
    directly. description is optional context about the audio for the
    detection config's context-extraction prompt. storage: optional
    s3://bucket/prefix — outputs are uploaded under <prefix>/<source>/<name>/.
    Returns a dict with output_path, filtered_duration, original_duration,
    seconds_removed, and (with storage) the uploaded S3 URIs.

    Configure the "audioclassifier" logger to see progress; set OPENAI_API_KEY
    (or the provider key matching LLM_MODEL) before calling.
    """
    if detection or detection_instructions or detection_keywords:
        from audioclassifier.config.detection_config import set_detection_config

        set_detection_config(
            detection,
            instructions=detection_instructions,
            keywords=detection_keywords,
        )

    from audioclassifier.cli import process_payload

    return process_payload(
        {
            "source": source,
            "name": name,
            "audio_url": audio_url,
            "description": description,
            "storage": storage,
        }
    )


def train_text_classifier(output_dir=None):
    """Train the self-distilled ad classifier from past runs' decision files.

    Returns training metrics. The trained model is picked up automatically by
    subsequent runs as an extra detection signal.
    """
    from audioclassifier.config.constants import FINISHED_MP3_DIR
    from audioclassifier.detection import text_classifier

    return text_classifier.train(output_dir or FINISHED_MP3_DIR)
