from pydub import AudioSegment
from faster_whisper import WhisperModel
import concurrent.futures
import json

# import json_tricks
import os
import re
import time
import traceback
import argparse
from queue import Queue
from src.config.constants import *
from src.detection.llm_detector import (
    get_specific_timestamps_using_llm,
    get_run_output,
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

# lock = threading.Lock()
lock = threading.RLock()

# DOWNLOAD_DIR = '/mnt/h/Developer_Workspace/gpodder/downloads/'

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
        transcription (dict): The transcription data containing segments.
        ad_keywords (list): A list of keywords to search for in the transcription.
        ad_companies (list): A list of company names to search for in the transcription.

    Returns:
        tuple: A tuple containing the ad timestamps dictionary,
        the minimum start time, and the maximum end time.

    The ad timestamps dictionary has the following structure:
    {
        'keyword1': [[start1, end1], [start2, end2], ...],
        'keyword2': [[start1, end1], [start2, end2], ...],
        ...
    }
    The minimum start time and maximum end time represent
    the overall time range of the ad segments found.
    """

    # Assuming transcript is a dictionary
    # keys = list(transcript[0].keys())
    # logger.info("############################################")
    # logger.info(f"First few of transcript keys: {keys[:1]}")
    # logger.info(f"Transcript: {transcript}")
    # logger.info("############################################")

    min_ms = float("inf")  # Positive infinity
    max_ms = float("-inf")  # Negative infinity

    # for logging
    current_block = None

    # TODO need to capture the words that kicked off the ad segment
    for t_segment in transcript:
        text = t_segment.text.lower()

        # high_certainty = any(company.lower() in text for company in ad_companies)

        contains_ad = any(company in text for company in sponsors) or any(
            pattern.search(text) for pattern in ad_keywords_compiled
        )

        if contains_ad:
            start = max(0, t_segment.start - START_AD_BUFFER)
            end = t_segment.end + END_AD_BUFFER

            # logging ad segment keywords to file
            # with open("ad_keywords.txt", "a") as file:
            #     file.write(text + '\n' + f'{start} - {end}\n\n')

            if current_block is None:
                current_block = [start, end]
            else:
                # Extend the current ad block if overlapping or adjacent within buffer
                if start <= current_block[1]:
                    current_block[1] = max(current_block[1], end)
                else:
                    # Update overall min and max if current block is finalized
                    min_ms = min(min_ms, current_block[0])
                    max_ms = max(max_ms, current_block[1])
                    current_block = [start, end]
        else:
            if current_block is not None:
                # Update overall min and max if moving out of ad segment
                min_ms = min(min_ms, current_block[0])
                max_ms = max(max_ms, current_block[1])
                current_block = None

    # Final update at the end of the transcript
    if current_block is not None:
        min_ms = min(min_ms, current_block[0])
        max_ms = max(max_ms, current_block[1])
    return min_ms, max_ms


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
            context="Error during segment extraction in audio_processor",
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


# set PYTHONPATH="${PYTHONPATH}:/mnt/c/Developer_Workspace/AudioClassifier"
# export PYTHONPATH="${PYTHONPATH}:/mnt/c/Developer_Workspace/AudioClassifier"
# python pod_handler/audio_processor.py
# python audio_processor.py --device cuda

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


def process_audio_segment(index, audio_segment, total_segments, sponsors):
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
            min_ms, max_ms = find_ad_timestamps(result, sponsors)
        # Return the model to the pool
        model_pool.put(model)
    except Exception as e:
        logger.error(traceback.format_exc())
        send_error_alert(
            error=e,
            context="Error during transcription in audio_processor",
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

        with lock:
            logger.info(
                f"Thread {threading.get_ident()} is entering the openai api call for file transcript_{index}_logging.json"
            )
            run, thread = get_specific_timestamps_using_llm(
                f"transcript_{index}_logging.json",
                os.path.join(script_dir, f"transcript_{index}_logging.json"),
                sponsors,
                lock,
            )
            logger.info(
                f"Put prompts into assistant thread openai thread {thread.id} and polling run {run.id}"
            )
            min_ms, max_ms, confidence_score = get_run_output(run=run, thread=thread)
            logger.info(
                f"Thread {threading.get_ident()} has exited the openai api call for file transcript_{index}_logging.json"
            )
            logger.info(
                f"OpenAI Thread {thread.id} and Run {run.id}:: Finished with values MIN[{min_ms}], MAX[{max_ms}], "
                f"and Confidence Score [{confidence_score}], transcript_{index}_logging.json"
            )

        if min_ms == float("inf") and max_ms == float("-inf"):
            logger.info(
                f"No ads found in the segment for transcript transcript_{index}_logging.json"
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


def remove_ads_from_audio(audio_file, podcast_description):
    """
    Removes ads from an audio file.

    This function takes an MP3 audio file as input, splits it into 10-minute segments,
    transcribes each segment, identifies ad timestamps in the transcription, and removes
    the corresponding audio segments containing the ads. The resulting audio file without
    ads is saved as "finished_audio_without_ads.mp3".

    Note: This function requires the 'whisper' library and the 'AudioSegment' class from
    the 'pydub' library.

    Args:
        None

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
                logger.error(f"Segment {segment_index} generated an exception: {exc}")
                logger.error(traceback.format_exc())
        # executor.shutdown(wait=True)
    logger.info(f"Finished processing audio segments, exporting finished mp3")
    results.sort(key=lambda x: x[0])
    # concatenate the segments without ads
    finished_audio_without_ads = sum(x[1] for x in results)
    # Save the result
    finished_audio_without_ads.export("finished_audio_without_ads.mp3", format="mp3")

    output_file_path = os.path.abspath("finished_audio_without_ads.mp3")

    # Return the duration of the finished audio in seconds
    logger.info(f"Audio with ads duration: {original_duration} seconds")
    logger.info(
        f"Finished audio without ads duration: {len(finished_audio_without_ads) / 1000} seconds"
    )
    return len(finished_audio_without_ads) / 1000, original_duration, output_file_path


podcast_description = """<p>Today we’ll hear about: </p><ul>\n<li>A young owner looking for help establishing processes in his fast- growing business </li>\n<li>A woman looking to fire an employee who won’t see it coming </li>\n<li>Dave Ramsey’s take on Home Depot requiring corporate employees to work in retail stores </li>\n<li>A business owner looking for advice on profit sharing with her team </li>\n</ul><p> </p><p><strong>Next Steps</strong> </p><ul>\n<li>📞 Have a question for the show? Call 844-944-1070 or send us a message: <a href=\"https://ter.li/ask-us\">https://ter.li/ask-us</a> </li>\n<li>📚 Learn about the EntreLeadership System: <a href=\"https://ter.li/system-p\">https://ter.li/system-p</a> </li>\n<li>💻 Get EntreLeadership Elite for your business: <a href=\"https://ter.li/elite-p\">https://ter.li/elite-p</a> </li>\n<li>✉️ Sign up to receive tactical tools, advice and resources in your inbox every week: <a href=\"https://ter.li/enl\">https://ter.li/enl</a> </li>\n<li>🏢 Attend EntreLeadership Summit: <a href=\"https://ter.li/summit\">https://ter.li/summit</a>  </li>\n<li>🎤 Attend EntreLeadership Master Series: <a href=\"https://ter.li/masterseries\">https://ter.li/masterseries</a>  </li>\n</ul><p> </p><p><strong>Offers From Today's Sponsors</strong> </p><ul>\n<li>💼 Go to<a href=\"https://www.belaysolutions.com/Entreleadership\"> <strong>Belay Solutions</strong></a> or text ENTRE to 55123 for their free resource! </li>\n<li>💻 Visit<a href=\"https://www.netsuite.com/Ramsey\"> <strong>NetSuite</strong></a> today to learn more </li>\n<li>🧾 Visit<a href=\"https://www.payority.com/entreleadership\"> </a><a href=\"https://www.payority.com/entreleadership\"><strong>Payority</strong></a> for a free consultation! </li>\n<li>📝 Use code entre15 to get 15% off your first year of <a href=\"https://www.trainual.com/entre\"><strong>Trainual</strong></a> </li>\n</ul><p> </p><p><strong>Listen to More From Ramsey Network</strong> </p><p>🎙️ <a href=\"https://ter.li/gpny1a\">The Ramsey Show</a> </p><p>💸 <a href=\"https://ter.li/430qk2\">The Ramsey Show Highlights</a> </p><p><strong>🧠</strong> <a href=\"https://ter.li/w9syza\">The Dr. John Delony Show</a> </p><p>🍸 <a href=\"https://ter.li/k3waa1\">Smart Money Happy Hour</a> </p><p>💡 <a href=\"https://ter.li/j3ahu7\">The Rachel Cruze Show</a> </p><p>💰 <a href=\"https://ter.li/99j2kb\">George Kamel</a> </p><p>💼 <a href=\"https://ter.li/puh2qh\">The Ken Coleman Show</a> </p><p> </p><p><a href=\"https://www.megaphone.fm/adchoices\">Learn More About Your Ad Choices</a>  </p><p><a href=\"https://www.ramseysolutions.com/company/policies/privacy-policy\">Ramsey Solutions Privacy Policy</a> </p>"""

# if __name__ == "__main__":
#     remove_ads_from_audio("downloads/potp1201art19.mp3", podcast_description)
