import json
import os
import re
import time
import traceback
import argparse
import threading
from queue import Queue
import concurrent.futures

from pydub import AudioSegment
from faster_whisper import WhisperModel

from src.config.constants import *
from src.ad_utils.ai_ad_checker import (
    fetch_sponsors,
)
from src.logger.logger_setup import logger
from src.alerts.discord_alerts import send_error_alert
import threading

# import whisper
# import re

# buffers to try and capture ad time after keyword is mentioned
# be careful with these, results in larger token cost to ai model
START_AD_BUFFER = 45
END_AD_BUFFER = 45

MINIMUM_AD_SKIP_TIME = 15  # Minimum time to skip an ad segment

# lock = threading.RLock()

ad_keywords = [
    "signing up",
    "use the code",
    "support the show",
    "use code",
    "this episode is brought to you by",
    "this show is brought to you by",
    r"support for \w+ comes from",
    r"i've been using \w+",
    "supplies are limited",
    r"and enter code \w+ at checkout",
    "brought to you",
    "this episode is",
    "sponsors",
    "sponsor",
    "click the link in the description to find out more",
    "sponsored by",
    "advertisement",
    r"visit [\w-]+\.com to save",
    "use the promo code",
    r"visit [-\w.]+ to learn more",
    "sponsoring",
    "limited time",
    "download the app",
    "paid for by",
    r"get \d+% off your",
    r"save \d+% on your",
    r"\d+% discount on your",
    r"get \d+% off",
    "take a moment to thank our sponsor",
    "purchase",
    "sale",
    "checkout",
    "special offer",
    "discount",
    "discount code",
    "promo code",
    "promo",
    "code",
    "deal",
    "offer",
    "subscription service that",
    "exclusive offer",
    r"limited[-\s]?time deal",
    r"limited[-\s]?time offer",
    r"limited[-\s]?time discount",
    r"limited[-\s]?time sale",
    "partnering",
    "partner",
    "partnered",
    "promotion",
    "link in the episode description",
    "highly recommend",
    "you have to try",
    "shop",
    "shop now",
    "exclusive deal",
    "affiliate link",
    "commission earned",
    "as an affiliate",
    "partner program",
    "affiliate disclosure",
    "brought to you in part by",
    "our friends at",
    "a quick word from our sponsors",
    r"listener[-\s]?supported",
    "thanks to our sponsor",
    "subscribe today",
    "try it for free",
    "sign up now",
    "don't miss out",
    "order now",
    "learn more",
    "click here",
    "visit now",
    "explore more",
    "read more",
    "get your first month free",
    "free trial",
    "no obligation",
    r"money[-\s]?back guarantee",
    "best price",
    "partnered with",
    "in collaboration with",
    "powered by",
    "endorsed by",
    "brought to you by our partners",
    r"(visit|check\s(out|us\sat|our\swebsite)|go\sto)\s[\w-]+(\.[a-z]{2,})",
    "act now",
    "offer valid until",
    "use our code",
    "check the link below",
    "click to learn more",
    "brought to you in partnership with",
    "save big",
    "big savings",
    "limited stock",
    "early bird offer",
    "new customers only",
    "join now",
    "exclusive for listeners",
    "refer a friend",
    "referral bonus",
    "sign up for exclusive perks",
    "try it today",
    "as seen on",
    "number one choice",
    "voted best by",
    "receive your",
    "guaranteed results",
    "award winning",
    "customer favorite",
    "see why everyone loves",
    "start your journey",
    "get access now",
    "unbeatable value",
    "get started today",
    "your exclusive chance",
    "contact us for more",
    "fast delivery",
    "don't delay",
    "best in class",
    "industry leading",
    "on sale now",
    "your satisfaction guaranteed",
    # Gambling & Betting
    "bet now",
    "place your bets",
    "gamble responsibly",
    "must be 18 or older",
    "download the draftkings app",
    "odds boost",
    "promo odds",
    "parlay insurance",
    # Nicotine / Vaping
    "nicotine pouches",
    "vape pods",
    "tobacco-free nicotine",
    "switch to vaping",
    "smokeless alternative",
    "juul compatible",
    # Health / Pharma / Supplements
    "telehealth visit",
    "online doctor",
    "rx delivered",
    "consult a licensed physician",
    "clinically proven results",
    "fda cleared",
    "lab-tested",
    "doctor-formulated",
    "ashwagandha gummies",
    "adaptogen blend",
    "hormone balancing",
    # Adult / Intimate Wellness
    "bedroom confidence",
    "boost libido",
    "feminine care",
    "testosterone support",
    "sexual wellness",
    "lasting longer",
    "increase stamina",
    "intimate oil",
    "male enhancement",
    "natural male enhancement",
    # Beauty & Grooming
    "anti-aging serum",
    "retinol cream",
    "collagen peptides",
    "hair thickening",
    "hair-loss solution",
    "dermatologist recommended",
    "clean beauty",
    "spf moisturizer",
    # Food & Beverage Delivery
    "meal kit",
    "fresh ingredients delivered",
    "chef-curated recipes",
    "coffee subscription",
    "wine club",
    "snack box",
    "first box free",
    # Finance & Investing
    "robo-advisor",
    "cryptocurrency exchange",
    "commission-free trading",
    "investing app",
    "refinance your loan",
    "credit repair",
    "cash-back card",
    # Tech & Cybersecurity
    "vpn service",
    "password manager",
    "cloud backup",
    "identity theft protection",
    "malware scan",
    "data breach monitoring",
    "secure browser",
    # Education & Career
    "coding bootcamp",
    "online mba",
    "certificate program",
    "career coaching",
    "learn to code",
    "masterclass",
    "course bundle",
    # Travel & Mobility
    "discount flights",
    "hotel deals",
    "vacation package",
    "airport transfer",
    "ride credit",
    "e-bike subscription",
    # Charity & Political Appeals
    "donate today",
    "matching gift",
    "join the movement",
    "support our mission",
    "paid for by the committee",
    "grassroots campaign",
]

# compiled regex patterns for ad keywords
ad_keywords_compiled = [re.compile(pattern, re.IGNORECASE) for pattern in ad_keywords]

# Specify the relative path to the file

script_dir = os.path.dirname(os.path.realpath(__file__))

# Get the current working directory
cwd = os.getcwd()
logger.info(f"Current working directory: {cwd}")

# Construct the absolute path
# file_path = os.path.join(cwd, ADS_TXT_PATH)
# logger.info(f'Absolute file path: {file_path}')

# with open(ADS_TXT_PATH, 'r') as file:
#     ad_companies = {line.strip().lower() for line in file}


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


# Find positions of ad-related keywords in the transcription
def find_ad_timestamps(transcript, sponsors):
    """
    Find the timestamps of ad segments in a transcription.

    Args:
        transcript (list): List of segment objects.

    Returns:
        list: List of [start, end] in seconds for ad segments.
    """
    ad_segments = []
    current_block = None

    for t_segment in transcript:
        text = t_segment.text.lower()

        # high_certainty = any(company.lower() in text for company in ad_companies)

        contains_ad = any(company in text for company in sponsors) or any(
            pattern.search(text) for pattern in ad_keywords_compiled
        )

        if contains_ad:
            start = max(0, t_segment.start - START_AD_BUFFER)
            end = t_segment.end + END_AD_BUFFER

            if current_block is None:
                current_block = [start, end]
            else:
                if start <= current_block[1]:
                    current_block[1] = max(current_block[1], end)
                else:
                    ad_segments.append(
                        [current_block[0] / 1000, current_block[1] / 1000]
                    )  # to seconds
                    current_block = [start, end]
        else:
            if current_block is not None:
                ad_segments.append([current_block[0] / 1000, current_block[1] / 1000])
                current_block = None

    if current_block is not None:
        ad_segments.append([current_block[0] / 1000, current_block[1] / 1000])

    return ad_segments


def extract_segments(segments, start_time, end_time):
    """Extracts segments from a JSON string based on the given start and end times.

    Args:
        json_string (str): The JSON string containing the segments.
        start_time (float): The start time of the desired segments.
        end_time (float): The end time of the desired segments.

    Returns:
        list: A list of extracted segments that fall within the specified tii me range.
    """
    # data = json.loads(json_string)
    # segments = data['segments']
    # print(f"Extracing Segments: {segments}")
    try:
        logger.info(
            f"Extracting segments: start_time={start_time}, end_time={end_time}"
        )
        # extracted_segments = [segment for segment in segments if start_time <= segment.start <= end_time]

        extracted_segments = [
            {
                # "id": segment.id,
                # "seek": segment.seek,
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
                # "tokens": segment.tokens,
                # "temperature": segment.temperature,
                # "avg_logprob": segment.avg_logprob,
                # "compression_ratio": segment.compression_ratio,
                # "no_speech_prob": segment.no_speech_prob,
                # "words": segment.words,
            }
            for segment in segments
            if start_time <= segment.start <= end_time
        ]
    except Exception as e:
        logger.error(f"Error extracting segments: {e}")
        send_error_alert(
            error=e,
            context="Error during segment extraction in transcribe training data",
            additional_info={
                "start_time": start_time,
                "end_time": end_time,
                "segments_count": (
                    len(segments) if "segments" in locals() else "unknown"
                ),
            },
        )
        raise Exception(f"An error occurred during segment extraction: {str(e)}")
    # for segment in segments:
    #     print(f"Extracted segment: start={segment.start}, end={segment.end}, text={segment.text[:50]}...")
    return extracted_segments


# set PYTHONPATH="${PYTHONPATH}:/mnt/c/Developer_Workspace/JusSkipIt"
# export PYTHONPATH="${PYTHONPATH}:/mnt/c/Developer_Workspace/JusSkipIt"
# python pod_handler/mp3_converter.py
# python mp3_converter.py --device cuda

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Process audio segments.")
parser.add_argument(
    "--device",
    type=str,
    default="cpu",
    help="Device to use for processing (cuda or cpu)",
)
args = parser.parse_args()

# Use the specified device for processing
device = args.device

# Initialize model_pool at the module level
model_pool = Queue()


def check_cuda():
    import torch

    if torch.cuda.is_available():
        logger.info("CUDA is available")
        device = "cuda" if torch.cuda.is_available() else "cpu"
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


def process_audio_segment(index, audio_segment, total_segments, sponsors):
    try:
        # TODO lets try using openai's model api call here
        # model = whisper.load_model("tiny", device="cuda")

        model = model_pool.get(block=True)  # Wait until a model is available
        logger.info(
            f"Thread using model {id(model)}, processing transcript_{index}_ad_label.json"
        )
        segment_path = f"segment_{index}.wav"
        audio_segment.export(segment_path, format="wav")
        # audio = whisperx.load_audio(segment_path)
        result_generator, info = model.transcribe(segment_path, language="en")
        # Convert the generator to a list
        result = list(result_generator)
        logger.info(f"Generated result with {len(result)} segments for index {index}")
        # Convert segments to dicts for JSON serialization
        result_dicts = [
            {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
            }
            for segment in result
        ]
        # print(f"Result: {result}")
        # logger.info(f"Finding Timestamps for segment index {index}")
        # min_ms, max_ms = find_ad_timestamps(result["segments"])
        with open(
            f"{script_dir}/full_audio_transcript_{index}.json", "w", encoding="utf-8"
        ) as file:
            logger.info(
                f"Writing full transcript to {script_dir}/full_audio_transcript_{index}.json"
            )
            json.dump(result_dicts, file, indent=2, ensure_ascii=False)
        logger.info(
            f"Full transcript written with {len(result_dicts)} segments for index {index}"
        )
        if index == 0:
            min_ms = 0  # 0 in seconds
            max_ms = 4 * 60  # 4 minutes in seconds
            logger.info(
                f"Setting min_ms: {min_ms}, max_ms: {max_ms} for transcript_{index}_ad_label.json"
            )
            logger.info("Searching the first segment because it is likely to have ads")
        elif index == total_segments - 1:
            segment_duration_sec = len(audio_segment) / 1000  # in seconds
            min_ms = max(0, segment_duration_sec - (3 * 60))  # 3 minutes before the end
            max_ms = segment_duration_sec  # Length of the audio segment
            logger.info(
                f"Setting min_ms: {min_ms}, max_ms: {max_ms} for transcript_{index}_ad_label.json"
            )
            logger.info("Searching the last segment because it is likely to have ads")
        else:
            ad_segments = find_ad_timestamps(result, sponsors)
            if ad_segments:
                min_ms = min(s[0] for s in ad_segments)
                max_ms = max(s[1] for s in ad_segments)
            else:
                min_ms = float("inf")
                max_ms = float("-inf")
        # Return the model to the pool
        model_pool.put(model)
    except Exception as e:
        logger.error(traceback.format_exc())
        send_error_alert(
            error=e,
            context="Error during segment extraction in transcribe training data",
            additional_info={
                "segment_index": index,
                "transcript_file": f"transcript_{index}_ad_label.json",
                "traceback": traceback.format_exc()[:500],  # Truncate traceback
            },
        )
        raise Exception(
            f"An error occurred during Transcription for transcript_{index}_ad_label.json: {str(e)}"
        )

    # logger.info(f"ad timestamps: {ad_timestamps}")
    logger.info(f"##############################################")
    logger.info(f"Segment {index}, for transcript_{index}_ad_label.json")
    logger.info(
        f"min_ms: {min_ms}, max_ms: {max_ms}, for transcript_{index}_ad_label.json"
    )
    logger.info(f"##############################################")

    # Slice audio before and after the ad
    os.remove(segment_path)  # remove the audio segment after processing
    if min_ms == float("inf") and max_ms == float("-inf"):
        logger.info(
            f"No ads found in the segment for transcript transcript_{index}_ad_label.json"
        )
        return audio_segment
    elif max_ms - min_ms < MINIMUM_AD_SKIP_TIME:
        logger.info(
            "Skipping segment with less than 20 seconds of ads, likely false positive for transcript_{index}_ad_label.json"
        )
        return audio_segment
    else:
        # TODO commented out for now, need to test transcript logging
        # if max_ms - min_ms > 360:
        #     logger.info("Ad segment is over 6 minutes, likely false positive. Reducing to 5 minutes")
        # max_ms = min_ms + 300
        # logger.info(f"SETTING::: min_ms: {min_ms}, max_ms: {max_ms}")
        # Extract the segments containing ads for logging
        logger.info(f"Extracting segments for transcript_{index}_ad_label.json")
        segments = extract_segments(result, min_ms, max_ms)

        ################################################################
        try:
            with open(
                f"{script_dir}/transcript_{index}_ad_label.json", "w", encoding="utf-8"
            ) as file:
                logger.info(
                    f"Logging ad segments to {script_dir}/transcript_{index}_ad_label.json"
                )
                # logger.info(f"Segments type for transcript_{index}_ad_label.json: {type(segments)}")
                # logger.info(f"Segments for transcript_{index}_ad_label.json: {segments}")
                json.dump(segments, file, indent=2, ensure_ascii=False)
                # json_tricks.dump(segments, file, indent=2, ensure_ascii=False)
        except TypeError as e:
            logger.error(f"Serialization failed with error: {e}")
            logger.error(traceback.format_exc())

        logger.info(
            f"Before entering the lock for index {index}: {threading.get_ident()}"
        )

        if min_ms == float("inf") and max_ms == float("-inf"):
            logger.info(
                f"No ads found in the segment for transcript transcript_{index}_ad_label.json"
            )
            return audio_segment

        # TODO grabbing the ad segment TEXT and saving it to a file
        # TODO honestly we may not even need this at all, as giving the transcript json file appears to be enough
        # with open(f"transcript_{index}_ad_text.txt", "w", encoding="utf-8") as file:
        #     for segment in segments:
        #         file.write(segment['text'] + '\n')
        ################################################################

        start_ads_ms = round(min_ms * 1000)  # Convert minutes to milliseconds
        end_ads_ms = round(max_ms * 1000)

        if start_ads_ms < 0:
            logger.info(
                f"transcript_{index}_ad_label.json Start time is less than 0, setting to 0 {start_ads_ms}"
            )
            start_ads_ms = 0
        if end_ads_ms > len(audio_segment):
            logger.info(
                f"transcript_{index}_ad_label.json End time is greater than segment duration, setting to segment duration {end_ads_ms}"
            )
            end_ads_ms = len(audio_segment)
        # audio = AudioSegment.from_wav("sliced_result.wav")
        logger.info(
            f"start_ads_ms: {start_ads_ms}, end_ads_ms: {end_ads_ms}::: for transcript_{index}_ad_label.json"
        )

        audio_before_ad = audio_segment[:start_ads_ms]
        audio_after_ad = audio_segment[end_ads_ms:]
        # Concatenate audio segments
        return audio_before_ad + audio_after_ad


def label_ads_from_audio(audio_file, podcast_description):
    """
    Removes ads from an audio file.

    This function takes an MP3 audio file as input, splits it into 10-minute segments,
    transcribes each segment, identifies ad timestamps in the transcription, and removes
    the corresponding audio segments containing the ads. The resulting audio file without
    ads is saved as "finished_audio_without_ads.mp3".

    Note: This function requires the 'whisper' library and the 'AudioSegment' class from
    the 'pydub' library.

    Args:
        audio_files (list): List of paths to audio files.
        output_file (str): Path to output NDJSON file.
        compress (bool): Whether to compress output.
        max_workers (int): Number of parallel workers.

    Returns:
        None
    """
    wav_file = "result.wav"

    # model = whisper.load_model("tiny", device="cpu")
    # model = whisper.load_model("tiny", device="cuda")
    # model = whisper.load_model("medium", device="cuda")

    sponsors = update_ad_keywords_with_sponsors(podcast_description)

    audio = AudioSegment.from_mp3(audio_file)
    original_duration = len(audio) / 1000

    audio.export(wav_file, format="wav")

    # Load the WAV file
    audio = AudioSegment.from_wav(wav_file)

    # Duration of each segment in milliseconds (10 minutes)
    segment_duration_ms = 10 * 60 * 1000

    # Duration of audio in milliseconds
    duration_ms = len(audio)

    # Split audio into 10-minute segments
    segments = [
        audio[i : i + segment_duration_ms]
        for i in range(0, duration_ms, segment_duration_ms)
    ]

    finished_audio_without_ads = AudioSegment.empty()
    # if not os.path.exists("transcript.json"):

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
                process_audio_segment, i, segments[i], len(segments), sponsors
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
                logger.error(f"Episode processing failed: {exc}")
                logger.error(traceback.format_exc())
        # executor.shutdown(wait=True)
    logger.info(f"Finished transcribing audio segments")


def create_transcript_structure(podcast_name, write_to_file=False):
    """
    Reads the transcript JSON files and structures them into the required format.

    Args:
        podcast_name (str): Name of the podcast for the output file.
        write_to_file (bool): If True, writes the structure to {podcast_name}_training_data.json
    """
    logger.info(f"create_transcript_structure called with podcast_name={podcast_name}, write_to_file={write_to_file}")
    downloads_dir = os.path.join(script_dir, "..", "..", "downloads")

    # Determine episode_id from the latest mp3 in downloads
    episode_id = "unknown"
    if os.path.exists(downloads_dir):
        mp3_files = [f for f in os.listdir(downloads_dir) if f.endswith(".mp3")]
        if mp3_files:
            latest_mp3 = max(
                mp3_files,
                key=lambda x: os.path.getctime(os.path.join(downloads_dir, x)),
            )
            episode_id = os.path.splitext(latest_mp3)[0]

    all_texts = []
    all_segments = []
    labels = []

    # Find the maximum index dynamically
    max_index = -1
    if os.path.exists(script_dir):
        for filename in os.listdir(script_dir):
            if filename.startswith("full_audio_transcript_") and filename.endswith(".json"):
                try:
                    index = int(filename.split("_")[-1].split(".")[0])
                    max_index = max(max_index, index)
                except ValueError:
                    pass
    if max_index == -1:
        logger.warning("No full_audio_transcript files found")
        return None

    # Process from 0 to max_index
    for index in range(max_index + 1):
        full_file = os.path.join(script_dir, f"full_audio_transcript_{index}.json")
        if os.path.exists(full_file):
            with open(full_file, "r", encoding="utf-8") as f:
                segments = json.load(f)
                all_segments.extend(segments)
                for seg in segments:
                    all_texts.append(seg["text"])

    # Clean the text: strip each segment and join with single space
    cleaned_texts = [seg["text"].strip() for seg in all_segments]
    text = " ".join(cleaned_texts)
    
    # Update segments with cleaned text
    for i, seg in enumerate(all_segments):
        seg["text"] = cleaned_texts[i]

    # Now process logging files for labels
    for index in range(max_index + 1):
        logging_file = os.path.join(script_dir, f"transcript_{index}_ad_label.json")
        if os.path.exists(logging_file):
            with open(logging_file, "r", encoding="utf-8") as f:
                log_segments = json.load(f)
                if log_segments:
                    text_snippets = []
                    char_starts = []
                    char_ends = []
                    start_times = []
                    end_times = []
                    for seg in log_segments:
                        text_part = seg["text"].strip()
                        pos = text.find(text_part)
                        if pos != -1:
                            char_starts.append(pos)
                            char_ends.append(pos + len(text_part))
                            text_snippets.append(text_part)
                            start_times.append(seg["start"])
                            end_times.append(seg["end"])
                        else:
                            logger.warning(f"Segment text not found for index {index}: {text_part[:50]}...")
                    
                    if char_starts:
                        min_char_start = min(char_starts)
                        max_char_end = max(char_ends)
                        concatenated_snippet = " ".join(text_snippets)
                        labels.append({
                            "label": "Ad",
                            "char_start": min_char_start,
                            "char_end": max_char_end,
                            "text_snippet": concatenated_snippet
                        })

    structure = {
        "episode_id": episode_id,
        "text": text,
        "labels": labels,
        "model": "whisper-tiny",
        "transcript_prep": "join_with_single_space",
    }

    # Clean up the JSON files
    for index in range(max_index + 1):
        full_file = os.path.join(script_dir, f"full_audio_transcript_{index}.json")
        if os.path.exists(full_file):
            os.remove(full_file)
            logger.info(f"Cleaned up {full_file}")
        
        logging_file = os.path.join(script_dir, f"transcript_{index}_ad_label.json")
        if os.path.exists(logging_file):
            os.remove(logging_file)
            logger.info(f"Cleaned up {logging_file}")

    # Write to file if requested
    if write_to_file:
        output_file = os.path.join(script_dir, f"{podcast_name}_training_data.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(structure, f, indent=2, ensure_ascii=False)
        logger.info(f"Transcript structure written to {output_file}")

    return structure
