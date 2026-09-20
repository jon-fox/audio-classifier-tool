import concurrent.futures
import json
import os
import re
import shutil
import traceback
from queue import Queue

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel

from audioclassifier.alerts.discord_alerts import send_error_alert
from audioclassifier.config.constants import *
from audioclassifier.config.detection_config import get_detection_config
from audioclassifier.detection.llm_detector import (
    fetch_sponsors,
    get_specific_timestamps_using_llm,
)
from audioclassifier.logger.logger_setup import logger

_keywords_compiled = None


def get_keywords_compiled():
    global _keywords_compiled
    if _keywords_compiled is None:
        _keywords_compiled = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in get_detection_config().keywords
        ]
    return _keywords_compiled

def update_ad_keywords_with_sponsors(podcast_description):
    if podcast_description:
        logger.info(f"Podcast description: {podcast_description}")
        try:
            sponsors = fetch_sponsors(podcast_description)
            if isinstance(sponsors, list):
                logger.info(f"Podcast sponsors: {sponsors}")
                return sponsors
            else:
                logger.error("Fetched sponsors is not a list")
                return []
        except Exception as e:
            logger.error(f"Error fetching or extending sponsors: {e}")
            return []
    return []


# Cheap gate: only segments with keyword/sponsor hits go to the LLM
def has_ad_keywords(transcript, sponsors):
    for t_segment in transcript:
        text = t_segment.text.lower()
        if any(company in text for company in sponsors) or any(
            pattern.search(text) for pattern in get_keywords_compiled()
        ):
            return True
    return False




# set PYTHONPATH="${PYTHONPATH}:/mnt/c/Developer_Workspace/AudioClassifier"
# export PYTHONPATH="${PYTHONPATH}:/mnt/c/Developer_Workspace/AudioClassifier"
# Initialize model_pool at the module level
model_pool = Queue()


def check_cuda():
    import ctranslate2

    if ctranslate2.get_cuda_device_count() > 0:
        logger.info("CUDA is available")
        device = "cuda"
    else:
        logger.info("CUDA is not available")
        device = "cpu"
    return device


def initialize_model_pool(device="cuda"):
    """
    Initializes a pool of Whisper models.
    """
    global model_pool
    logger.info(
        f"Initializing model pool with {NUMBER_OF_MODELS} WhisperModel instances"
    )

    model_download_path = os.path.join(MODEL_DOWNLOAD_PATH)
    logger.info(f"Model download path: {model_download_path}")

    # Check if model already exists locally
    if os.path.exists(model_download_path):
        logger.info(f"Pre-downloaded model found at {model_download_path}")
    else:
        logger.info(
            f"No pre-downloaded model found, will download during model loading"
        )

    for i in range(NUMBER_OF_MODELS):
        logger.info(
            f"Loading model {i + 1}/{NUMBER_OF_MODELS} from {model_download_path}"
        )
        whisper_model = WhisperModel(
            MODEL_SIZE, download_root=model_download_path, device=device
        )
        logger.info(f"Model {i + 1}/{NUMBER_OF_MODELS} loaded successfully")
        model_pool.put(whisper_model)


def process_audio_segment(
    index, audio_segment, samplerate, total_segments, sponsors, transcripts_dir
):
    try:
        model = model_pool.get(block=True)  # Wait until a model is available
        logger.info(f"Thread using model {id(model)}, processing segment {index}")
        segment_path = f"segment_{index}.wav"
        sf.write(segment_path, audio_segment, samplerate)
        result_generator, info = model.transcribe(segment_path, language="en")
        result = list(result_generator)
        model_pool.put(model)
    except Exception as e:
        logger.error(traceback.format_exc())
        send_error_alert(
            error=e,
            context="Error during transcription in audio_processor",
            additional_info={
                "segment_index": index,
                "traceback": traceback.format_exc()[:500],
            },
        )
        raise Exception(f"An error occurred during Transcription of segment {index}: {str(e)}")

    os.remove(segment_path)

    # First and last segments are likely to carry pre/post-roll ads, so they
    # always go to the LLM; the rest only when the keyword gate trips
    if index not in (0, total_segments - 1) and not has_ad_keywords(result, sponsors):
        logger.info(f"Segment {index}: no ad keywords, keeping as is")
        return audio_segment

    transcript = [
        {"start": s.start, "end": s.end, "text": s.text} for s in result
    ]
    transcript_path = os.path.join(transcripts_dir, f"transcript_{index}.json")
    with open(transcript_path, "w", encoding="utf-8") as file:
        json.dump(transcript, file, indent=2, ensure_ascii=False)

    cut_ranges = get_specific_timestamps_using_llm(
        f"transcript_{index}.json", transcript_path, sponsors
    )
    if not cut_ranges:
        logger.info(f"Segment {index}: nothing to cut")
        return audio_segment

    cut_ranges = _snap_to_transcript(cut_ranges, result)
    logger.info(f"Segment {index}: cutting ranges (seconds): {cut_ranges}")
    return _cut_ranges(audio_segment, cut_ranges, samplerate)


def _snap_to_transcript(cut_ranges, transcript):
    """Align cut boundaries to transcription segment edges to avoid mid-word cuts."""
    if not transcript:
        return cut_ranges
    starts = [t.start for t in transcript]
    ends = [t.end for t in transcript]
    snapped = []
    for start, end in cut_ranges:
        snapped_start = min(starts, key=lambda x: abs(x - start))
        snapped_end = min(ends, key=lambda x: abs(x - end))
        if snapped_end > snapped_start:
            snapped.append([snapped_start, snapped_end])
    return snapped


def _cut_ranges(audio, cut_ranges, samplerate):
    kept = []
    cursor = 0
    for start, end in cut_ranges:
        start_idx = max(0, round(start * samplerate))
        end_idx = min(len(audio), round(end * samplerate))
        if start_idx > cursor:
            kept.append(audio[cursor:start_idx])
        cursor = max(cursor, end_idx)
    kept.append(audio[cursor:])
    kept = [piece for piece in kept if len(piece)]
    if not kept:
        return audio[:0]

    total_cut = sum(end - start for start, end in cut_ranges)
    if total_cut * samplerate > 0.8 * len(audio):
        logger.warning(f"Cutting over 80% of a segment ({total_cut:.0f}s)")

    out = kept[0]
    fade = round(samplerate * CROSSFADE_MS / 1000)
    for piece in kept[1:]:
        out = _join_with_crossfade(out, piece, fade)
    return out


def _join_with_crossfade(a, b, fade):
    n = min(fade, len(a), len(b))
    if n == 0:
        return np.concatenate((a, b))
    ramp = np.linspace(1.0, 0.0, n)[:, None]
    mixed = (a[-n:] * ramp + b[:n] * (1 - ramp)).astype(a.dtype)
    return np.concatenate((a[:-n], mixed, b[n:]))


def remove_ads_from_audio(
    audio_file, podcast_description, output_dir=None, output_name=None
):
    """
    Removes ads from an audio file.

    This function takes an MP3 audio file as input, splits it into 10-minute segments,
    transcribes each segment, identifies ad timestamps in the transcription, and removes
    the corresponding audio segments containing the ads. The resulting audio file without
    ads is saved as "finished_audio_without_ads.mp3".

    Args:
        None

    Returns:
        None
    """
    if output_dir is None:
        output_dir = FINISHED_MP3_DIR
    if output_name is None:
        output_name = os.path.splitext(os.path.basename(audio_file))[0]
    transcripts_dir = os.path.join(output_dir, "transcripts")
    os.makedirs(transcripts_dir, exist_ok=True)

    # Keep the original episode alongside the filtered one
    shutil.copy2(audio_file, os.path.join(output_dir, f"{output_name}.mp3"))

    sponsors = update_ad_keywords_with_sponsors(podcast_description)

    audio, samplerate = sf.read(audio_file, dtype="int16", always_2d=True)
    original_duration = len(audio) / samplerate

    # Split audio into 10-minute segments
    segment_duration_samples = 10 * 60 * samplerate
    segments = [
        audio[i : i + segment_duration_samples]
        for i in range(0, len(audio), segment_duration_samples)
    ]

    logger.info(f"Initializing Model Pool with {NUMBER_OF_MODELS} models")
    initialize_model_pool(check_cuda())

    # Using ThreadPoolExecutor to process each segment
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=model_pool.qsize()
    ) as executor:
        logger.info(f"Using {model_pool.qsize()} models for processing")
        # Submit all segments to the executor
        future_to_segment = {
            executor.submit(
                process_audio_segment,
                i,
                segments[i],
                samplerate,
                len(segments),
                sponsors,
                transcripts_dir,
            ): i
            for i in range(len(segments))
        }

        # Collect results as they complete
        results = []
        for future in concurrent.futures.as_completed(future_to_segment):
            segment_index = future_to_segment[future]
            logger.info(
                f"Processing segment for segment index {segment_index}, for transcript_{segment_index}_logging.json"
            )
            try:
                result = future.result()
                results.append(
                    (segment_index, result)
                )  # Store results along with their original index
            except Exception as exc:
                logger.error(f"Segment {segment_index} generated an exception: {exc}")
                logger.error(traceback.format_exc())
                # Keep the original segment rather than dropping this chunk of
                # the episode from the output
                results.append((segment_index, segments[segment_index]))
        # executor.shutdown(wait=True)
    logger.info(f"Finished processing audio segments, exporting finished mp3")
    results.sort(key=lambda x: x[0])
    # concatenate the segments without ads
    finished_audio_without_ads = np.concatenate([x[1] for x in results])

    output_file_path = os.path.abspath(
        os.path.join(output_dir, f"{output_name}_filtered.mp3")
    )
    # libsndfile's mp3 encoder corrupts int16 input; float32 encodes cleanly
    sf.write(
        output_file_path,
        finished_audio_without_ads.astype(np.float32) / 32768.0,
        samplerate,
    )

    finished_duration = len(finished_audio_without_ads) / samplerate
    logger.info(f"Audio with ads duration: {original_duration} seconds")
    logger.info(
        f"Finished audio without ads duration: {finished_duration} seconds"
    )
    return finished_duration, original_duration, output_file_path


podcast_description = """<p>Today we’ll hear about: </p><ul>\n<li>A young owner looking for help establishing processes in his fast- growing business </li>\n<li>A woman looking to fire an employee who won’t see it coming </li>\n<li>Dave Ramsey’s take on Home Depot requiring corporate employees to work in retail stores </li>\n<li>A business owner looking for advice on profit sharing with her team </li>\n</ul><p> </p><p><strong>Next Steps</strong> </p><ul>\n<li>📞 Have a question for the show? Call 844-944-1070 or send us a message: <a href=\"https://ter.li/ask-us\">https://ter.li/ask-us</a> </li>\n<li>📚 Learn about the EntreLeadership System: <a href=\"https://ter.li/system-p\">https://ter.li/system-p</a> </li>\n<li>💻 Get EntreLeadership Elite for your business: <a href=\"https://ter.li/elite-p\">https://ter.li/elite-p</a> </li>\n<li>✉️ Sign up to receive tactical tools, advice and resources in your inbox every week: <a href=\"https://ter.li/enl\">https://ter.li/enl</a> </li>\n<li>🏢 Attend EntreLeadership Summit: <a href=\"https://ter.li/summit\">https://ter.li/summit</a>  </li>\n<li>🎤 Attend EntreLeadership Master Series: <a href=\"https://ter.li/masterseries\">https://ter.li/masterseries</a>  </li>\n</ul><p> </p><p><strong>Offers From Today's Sponsors</strong> </p><ul>\n<li>💼 Go to<a href=\"https://www.belaysolutions.com/Entreleadership\"> <strong>Belay Solutions</strong></a> or text ENTRE to 55123 for their free resource! </li>\n<li>💻 Visit<a href=\"https://www.netsuite.com/Ramsey\"> <strong>NetSuite</strong></a> today to learn more </li>\n<li>🧾 Visit<a href=\"https://www.payority.com/entreleadership\"> </a><a href=\"https://www.payority.com/entreleadership\"><strong>Payority</strong></a> for a free consultation! </li>\n<li>📝 Use code entre15 to get 15% off your first year of <a href=\"https://www.trainual.com/entre\"><strong>Trainual</strong></a> </li>\n</ul><p> </p><p><strong>Listen to More From Ramsey Network</strong> </p><p>🎙️ <a href=\"https://ter.li/gpny1a\">The Ramsey Show</a> </p><p>💸 <a href=\"https://ter.li/430qk2\">The Ramsey Show Highlights</a> </p><p><strong>🧠</strong> <a href=\"https://ter.li/w9syza\">The Dr. John Delony Show</a> </p><p>🍸 <a href=\"https://ter.li/k3waa1\">Smart Money Happy Hour</a> </p><p>💡 <a href=\"https://ter.li/j3ahu7\">The Rachel Cruze Show</a> </p><p>💰 <a href=\"https://ter.li/99j2kb\">George Kamel</a> </p><p>💼 <a href=\"https://ter.li/puh2qh\">The Ken Coleman Show</a> </p><p> </p><p><a href=\"https://www.megaphone.fm/adchoices\">Learn More About Your Ad Choices</a>  </p><p><a href=\"https://www.ramseysolutions.com/company/policies/privacy-policy\">Ramsey Solutions Privacy Policy</a> </p>"""

# if __name__ == "__main__":
#     remove_ads_from_audio("downloads/potp1201art19.mp3", podcast_description)
