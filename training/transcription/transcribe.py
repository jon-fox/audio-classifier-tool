import json
import os
import re
import traceback
import argparse
import threading
import gzip
from queue import Queue
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydub import AudioSegment
from faster_whisper import WhisperModel

from src.config.constants import *
from src.logger.logger_setup import logger
from src.alerts.discord_alerts import send_error_alert


# buffers to try and capture ad time after keyword is mentioned
# be careful with these, results in larger token cost to ai model
START_AD_BUFFER = 45
END_AD_BUFFER = 45

MINIMUM_AD_SKIP_TIME = 15  # Minimum time to skip an ad segment

# lock = threading.Lock()
lock = threading.RLock()

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


# Find positions of ad-related keywords in the transcription
def find_ad_timestamps(transcript):
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
        contains_ad = any(pattern.search(text) for pattern in ad_keywords_compiled)

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
            context="Error during segment extraction in mp3_converter_whisperx",
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


def process_audio_segment(index, audio_segment, total_segments):
    """
    Transcribe a single audio segment and sends to find ad timestamps if not in first 10 min
    or last 10 min segment. Reason being is that ads are most likely present in the first/final 10 minutes.

    Removes the ads in the audio segment in return by using the start/end timestamps to cut out the
    potential ad audio.

    Args:
        index (int): The index of the audio segment.
        audio_segment (AudioSegment): The audio segment to process.
        total_segments (int): The total number of audio segments.
    """
    try:
        # TODO lets try using openai's model api call here
        # model = whisper.load_model("tiny", device="cuda")

        model = model_pool.get(block=True)  # Wait until a model is available
        logger.info(
            f"Thread using model {id(model)}, processing transcript_{index}_logging.json"
        )
        segment_path = f"segment_{index}.wav"
        audio_segment.export(segment_path, format="wav")
        # audio = whisperx.load_audio(segment_path)
        result_generator, info = model.transcribe(segment_path, language="en")
        # Convert the generator to a list
        result = list(result_generator)
        # print(f"Result: {result}")
        # logger.info(f"Finding Timestamps for segment index {index}")
        # min_ms, max_ms = find_ad_timestamps(result["segments"])
        if index == 0:
            min_ms = 0  # 0 in milliseconds
            max_ms = 4 * 60 * 1000  # 4 minutes in milliseconds
            logger.info(
                f"Setting min_ms: {min_ms}, max_ms: {max_ms} for transcript_{index}_logging.json"
            )
            logger.info("Searching the first segment because it is likely to have ads")
        elif index == total_segments - 1:
            segment_duration_ms = len(audio_segment)
            min_ms = max(
                0, segment_duration_ms - (3 * 60 * 1000)
            )  # 3 minutes before the end
            max_ms = segment_duration_ms  # Length of the audio segment
            logger.info(
                f"Setting min_ms: {min_ms}, max_ms: {max_ms} for transcript_{index}_logging.json"
            )
            logger.info("Searching the last segment because it is likely to have ads")
        else:
            min_ms, max_ms = find_ad_timestamps(result)
        # Return the model to the pool
        model_pool.put(model)
    except Exception as e:
        logger.error(traceback.format_exc())
        send_error_alert(
            error=e,
            context="Error during transcription in mp3_converter_whisperx",
            additional_info={
                "segment_index": index,
                "transcript_file": f"transcript_{index}_logging.json",
                "traceback": traceback.format_exc()[:500],  # Truncate traceback
            },
        )
        raise Exception(
            f"An error occurred during Transcription for transcript_{index}_logging.json: {str(e)}"
        )

    # logger.info(f"ad timestamps: {ad_timestamps}")
    logger.info(f"##############################################")
    logger.info(f"Segment {index}, for transcript_{index}_logging.json")
    logger.info(
        f"min_ms: {min_ms}, max_ms: {max_ms}, for transcript_{index}_logging.json"
    )
    logger.info(f"##############################################")

    # Slice audio before and after the ad
    os.remove(segment_path)  # remove the audio segment after processing
    if min_ms == float("inf") and max_ms == float("-inf"):
        logger.info(
            f"No ads found in the segment for transcript transcript_{index}_logging.json"
        )
        return audio_segment
    elif max_ms - min_ms < MINIMUM_AD_SKIP_TIME:
        logger.info(
            "Skipping segment with less than 20 seconds of ads, likely false positive for transcript_{index}_logging.json"
        )
        return audio_segment
    else:
        # TODO commented out for now, need to test transcript logging
        # if max_ms - min_ms > 360:
        #     logger.info("Ad segment is over 6 minutes, likely false positive. Reducing to 5 minutes")
        # max_ms = min_ms + 300
        # logger.info(f"SETTING::: min_ms: {min_ms}, max_ms: {max_ms}")
        # Extract the segments containing ads for logging
        logger.info(f"Extracting segments for transcript_{index}_logging.json")
        segments = extract_segments(result, min_ms, max_ms)

        ################################################################
        try:
            with open(
                f"{script_dir}/transcript_{index}_logging.json", "w", encoding="utf-8"
            ) as file:
                logger.info(
                    f"Logging ad segments to {script_dir}/transcript_{index}_logging.json"
                )
                # logger.info(f"Segments type for transcript_{index}_logging.json: {type(segments)}")
                # logger.info(f"Segments for transcript_{index}_logging.json: {segments}")
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
                f"No ads found in the segment for transcript transcript_{index}_logging.json"
            )
            return audio_segment

        # markers
        start_ads_ms = round(min_ms * 1000)  # Convert minutes to milliseconds
        end_ads_ms = round(max_ms * 1000)

        if start_ads_ms < 0:
            logger.info(
                f"transcript_{index}_logging.json Start time is less than 0, setting to 0 {start_ads_ms}"
            )
            start_ads_ms = 0
        if end_ads_ms > len(audio_segment):
            logger.info(
                f"transcript_{index}_logging.json End time is greater than segment duration, setting to segment duration {end_ads_ms}"
            )
            end_ads_ms = len(audio_segment)
        # audio = AudioSegment.from_wav("sliced_result.wav")
        logger.info(
            f"start_ads_ms: {start_ads_ms}, end_ads_ms: {end_ads_ms}::: for transcript_{index}_logging.json"
        )

        audio_before_ad = audio_segment[:start_ads_ms]
        audio_after_ad = audio_segment[end_ads_ms:]
        # Concatenate audio segments
        return audio_before_ad + audio_after_ad


def process_episode(audio_file):
    """
    Process a single episode: transcribe, extract labels.

    Returns:
        dict: Data for NDJSON
    """
    wav_file = f"temp_{os.path.basename(audio_file)}.wav"

    audio = AudioSegment.from_mp3(audio_file)
    audio.export(wav_file, format="wav")

    # Load model (for parallel, perhaps share model, but for simplicity, load per worker)
    device = check_cuda()
    model_download_path = os.path.join(MODEL_DOWNLOAD_PATH)
    model = WhisperModel(MODEL_SIZE, download_root=model_download_path, device=device)

    # Transcribe
    result_generator, info = model.transcribe(wav_file, language="en")
    segments = list(result_generator)

    # Build transcript
    transcript = " ".join(segment.text for segment in segments)

    # Find ad timestamps
    ad_labels = find_ad_timestamps(segments)

    # Episode ID
    episode_id = os.path.splitext(os.path.basename(audio_file))[0]

    # Clean up
    os.remove(wav_file)

    return {"episode_id": episode_id, "transcript": transcript, "ad_labels": ad_labels}


def writer_thread(queue, output_file, compress):
    """
    Single writer thread to write to NDJSON.
    """
    temp_file = output_file + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        while True:
            data = queue.get()
            if data is None:  # Sentinel to stop
                break
            json.dump(data, f, ensure_ascii=False)
            f.write("\n")
            queue.task_done()

    # Atomic rename
    os.rename(temp_file, output_file)

    # Compress if needed
    if compress:
        with open(output_file, "r", encoding="utf-8") as f_in:
            with gzip.open(output_file + ".gz", "wt", encoding="utf-8") as f_out:
                f_out.write(f_in.read())
        os.remove(output_file)


def transcribe_for_training(
    audio_files, output_file="training_data.jsonl", compress=False, max_workers=4
):
    """
    Transcribes multiple audio files in parallel, extracts ad labels, outputs to NDJSON.

    Args:
        audio_files (list): List of paths to audio files.
        output_file (str): Path to output NDJSON file.
        compress (bool): Whether to compress output.
        max_workers (int): Number of parallel workers.

    Returns:
        None
    """
    queue = Queue()

    # Start writer thread
    writer = threading.Thread(target=writer_thread, args=(queue, output_file, compress))
    writer.start()

    # Process episodes in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_episode, audio_file) for audio_file in audio_files
        ]
        for future in as_completed(futures):
            try:
                data = future.result()
                queue.put(data)
            except Exception as exc:
                logger.error(f"Episode processing failed: {exc}")
                logger.error(traceback.format_exc())

    # Stop writer
    queue.put(None)
    writer.join()

    logger.info(f"Training data written to {output_file}")
