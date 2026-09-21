import os
import shutil
import tempfile
import time

from audioclassifier.alerts.discord_alerts import send_error_alert
from audioclassifier.config.constants import *
from audioclassifier.logger.logger_setup import logger
from audioclassifier.processing.audio_processor import remove_ads_from_audio
from audioclassifier.processing.download_mp3 import download_audio
from audioclassifier.processing.manifest import write_manifest
from audioclassifier.util import sanitize_name


def mp3_handler(source, description, audio_hash, audio_url, name=None):
    name = name or "Unknown"

    # Per-run scratch space, so parallel processes never share files
    work_dir = tempfile.mkdtemp(prefix="audioclassifier-")

    try:
        start_time = time.time()
        logger.info(f"Removing target segments from {source} / {name}")

        try:
            file_size, local_path, audio_identity = download_audio(
                f"{audio_hash}.mp3", audio_url, work_dir
            )
        except Exception as e:
            send_error_alert(
                error=e,
                context="Failed to download audio in mp3_handler",
                name=name,
                source=source,
                additional_info={"audio_url": audio_url, "audio_hash": audio_hash},
            )
            raise e

        output_dir = os.path.join(FINISHED_MP3_DIR, source, sanitize_name(name))

        try:
            (
                filtered_duration,
                original_duration,
                output_path,
                ad_segments,
                analysis_gaps,
            ) = remove_ads_from_audio(
                audio_file=local_path,
                description=description,
                output_dir=output_dir,
                output_name=sanitize_name(name),
            )
        except Exception as e:
            send_error_alert(
                error=e,
                context="Failed to remove segments in mp3_handler",
                name=name,
                source=source,
                additional_info={"audio_hash": audio_hash, "audio_file": local_path},
            )
            raise e

        audio = {
            "source_url": audio_url,
            "duration_sec": round(original_duration, 1),
            **audio_identity,
        }
        manifest = write_manifest(
            output_dir,
            audio,
            ad_segments,
            original_duration - filtered_duration,
            analysis_gaps,
        )

        total_processing_time = time.time() - start_time
        logger.info(
            f"Filtered {name}: {filtered_duration:.0f}s vs original "
            f"{original_duration:.0f}s, took {total_processing_time:.0f}s "
            f"({file_size} bytes downloaded)"
        )

        return {
            "output_path": output_path,
            "filtered_duration": filtered_duration,
            "original_duration": original_duration,
            "seconds_removed": original_duration - filtered_duration,
            "ad_segments": ad_segments,
            "audio": audio,
            "model_version": manifest["model_version"],
        }

    except Exception as e:
        logger.error(f"Critical error in mp3_handler: {e}")
        send_error_alert(
            error=e,
            context="Critical error in mp3_handler function",
            name=name,
            source=source,
            additional_info={"audio_hash": audio_hash, "audio_url": audio_url},
        )
        raise e
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
