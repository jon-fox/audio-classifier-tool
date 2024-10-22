from pydub import AudioSegment
import whisperx
import concurrent.futures
import json
import os
import re
import time
import traceback
import argparse
from queue import Queue
from src.config.constants import *
from src.ad_utils.ai_ad_checker import get_specific_timestamps_using_llm, get_run_output
from src.logger.logger_setup import logger
import threading

# import whisper
# import re

# buffers to try and capture ad time after keyword is mentioned
# be careful with these, results in larger token cost to ai model
START_AD_BUFFER = 15
END_AD_BUFFER = 15

MINIMUM_AD_SKIP_TIME = 15 # Minimum time to skip an ad segment

# lock = threading.Lock()
lock = threading.RLock()

# DOWNLOAD_DIR = '/mnt/h/Developer_Workspace/gpodder/downloads/'

ad_keywords = ["signing up", "use the code", "support the show", "use code", "this episode is brought to you by","this show is brought to you by", 
               r"Support for \w+ comes from", r"I've been using \w+", "supplies are limited", r"and enter code \w+ at checkout",
                "brought to you", "this episode is", "sponsors", "sponsor", "Click the link in the description to find out more",
            "sponsored by", "advertisement", r'visit \w+\.com to save', "use the promo code", r'visit [\w.]+ to learn more' 
            "sponsoring", "limited time", "subscription service that", "download the app",
            r'get \d+% off your', r'save \d+% on your', r'\d+% discount on your', r'get \d+% off', "take a moment to thank our sponsor",
            "signing up", "sponsors", "sponsor", "advertisement", "purchase", "sale", "sponsoring", "checkout"]

# compiled regex patterns for ad keywords
ad_keywords_compiled = [re.compile(pattern, re.IGNORECASE) for pattern in ad_keywords]

# Specify the relative path to the file

script_dir = os.path.dirname(os.path.realpath(__file__))

# Get the current working directory
cwd = os.getcwd()
logger.info(f'Current working directory: {cwd}')

# Construct the absolute path
# file_path = os.path.join(cwd, ADS_TXT_PATH)
# logger.info(f'Absolute file path: {file_path}')

with open(ADS_TXT_PATH, 'r') as file:
    ad_companies = {line.strip().lower() for line in file}


# Find positions of ad-related keywords in the transcription
def find_ad_timestamps(transcript):
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

    min_ms = float('inf')  # Positive infinity
    max_ms = float('-inf')  # Negative infinity

    # for logging
    current_block = None

    # TODO need to capture the words that kicked off the ad segment
    for t_segment in transcript:
        text = t_segment['text'].lower()

        # high_certainty = any(company.lower() in text for company in ad_companies)

        contains_ad = any(company in text for company in ad_companies) or \
                any(pattern.search(text) for pattern in ad_keywords_compiled)

        if contains_ad:
            start = max(0, t_segment['start'] - START_AD_BUFFER)
            end = t_segment['end'] + END_AD_BUFFER

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
        list: A list of extracted segments that fall within the specified time range.
    """
    # data = json.loads(json_string)
    # segments = data['segments']
    extracted_segments = [segment for segment in segments if start_time <= segment['start'] <= end_time]
    return extracted_segments

# set PYTHONPATH="${PYTHONPATH}:/mnt/c/Developer_Workspace/JusSkipIt"
# export PYTHONPATH="${PYTHONPATH}:/mnt/c/Developer_Workspace/JusSkipIt"
# python pod_handler/mp3_converter.py
# python mp3_converter.py --device cuda

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Process audio segments.')
parser.add_argument('--device', type=str, default='cpu', help='Device to use for processing (cuda or cpu)')
args = parser.parse_args()

# Use the specified device for processing
device = args.device

# Initialize model_pool at the module level
model_pool = Queue()

def check_cuda():
    import torch
    if torch.cuda.is_available():
        logger.info("CUDA is available")
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    else:
        logger.info("CUDA is not available")
        device = 'cpu'
    return device

def initialize_model_pool(device="cuda"):
    """
    Initializes a pool of Whisper models.

    Parameters:
    - number_of_models: The number of Whisper models to load into the pool. Maybe use later
    - device: The device to load the models on. Defaults to 'cuda'.

    Returns:
    - A queue.Queue object containing the loaded Whisper models.
    """
    global model_pool
    model_file_path = os.path.join(MODEL_DOWNLOAD_PATH, MODEL_FILE_NAME)
    logger.info(f"Checking Model file path: {model_file_path}")

    # Check if the model file exists
    if not os.path.isfile(model_file_path):
        logger.info(f"Downloading model from Hugging Face model hub")
        whisper_model = whisperx.load_model("tiny", download_root=os.path.join(MODEL_DOWNLOAD_PATH), device=device)
    else:
        logger.info(f"Loading model from file: {model_file_path}")
        whisper_model = whisperx.load_model(model_file_path, device=device)

    # Load the model into the pool multiple times
    for _ in range(NUMBER_OF_MODELS):
        model_pool.put(whisper_model)


def process_audio_segment(index, audio_segment):
    try:
        # TODO lets try using openai's model api call here
        # model = whisper.load_model("tiny", device="cuda")
        
        model = model_pool.get(block=True) # Wait until a model is available
        logger.info(f"Thread using model {id(model)}, processing transcript_{index}_logging.json")
        segment_path = f"segment_{index}.wav"
        audio_segment.export(segment_path, format="wav")
        audio = whisperx.load_audio(segment_path)
        result = model.transcribe(audio, language="en")
        # Clean up segment file after use
        # logger.info(f"Finding Timestamps for segment index {index}")
        min_ms, max_ms = find_ad_timestamps(result["segments"])
        # Return the model to the pool
        model_pool.put(model)
    except Exception as e:
        logger.error(traceback.print_exc())
        raise Exception(f"An error occurred during Transcription for transcript_{index}_logging.json: {str(e)}")

    # logger.info(f"ad timestamps: {ad_timestamps}")
    logger.info(f"##############################################")
    logger.info(f"Segment {index}, for transcript_{index}_logging.json")
    logger.info(f"min_ms: {min_ms}, max_ms: {max_ms}, for transcript_{index}_logging.json")
    logger.info(f"##############################################")

    # Slice audio before and after the ad
    os.remove(segment_path)
    if min_ms == float('inf') and max_ms == float('-inf'):
        logger.info(f"No ads found in the segment for transcript transcript_{index}_logging.json")
        return audio_segment
    elif max_ms - min_ms < MINIMUM_AD_SKIP_TIME:
        logger.info("Skipping segment with less than 20 seconds of ads, likely false positive for transcript_{index}_logging.json")
        return audio_segment
    else:
        # TODO commented out for now, need to test transcript logging
        # if max_ms - min_ms > 360:
        #     logger.info("Ad segment is over 6 minutes, likely false positive. Reducing to 5 minutes")
            # max_ms = min_ms + 300
            # logger.info(f"SETTING::: min_ms: {min_ms}, max_ms: {max_ms}")
        # Extract the segments containing ads for logging
        segments = extract_segments(result["segments"], min_ms, max_ms)

        ################################################################

        with open(f"{script_dir}/transcript_{index}_logging.json", "w", encoding="utf-8") as file:
            logger.info(f"Logging ad segments to {script_dir}/transcript_{index}_logging.json")
            json.dump(segments, file, indent=2, ensure_ascii=False)
        
        logger.info(f"Before entering the lock for index {index}: {threading.get_ident()}")

        with lock:
            logger.info(f"Thread {threading.get_ident()} is entering the openai api call for file transcript_{index}_logging.json")
            run, thread = get_specific_timestamps_using_llm(f"transcript_{index}_logging.json", 
                                                                os.path.join(script_dir, f"transcript_{index}_logging.json"), lock)
            logger.info(f"Put prompts into assistant thread openai thread {thread.id} and polling run {run.id}")
            min_ms, max_ms, confidence_score = get_run_output(run=run, thread=thread)
            logger.info(f"Thread {threading.get_ident()} has exited the openai api call for file transcript_{index}_logging.json")
            logger.info(f"OpenAI Thread {thread.id} and Run {run.id}:: Finished with values MIN[{min_ms}], MAX[{max_ms}], "
                        f"and Confidence Score [{confidence_score}], transcript_{index}_logging.json")


        if min_ms == float('inf') and max_ms == float('-inf'):
            logger.info(f"No ads found in the segment for transcript transcript_{index}_logging.json")
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
            logger.info("transcript_{index}_logging.json Start time is less than 0 or None, setting to 0", start_ads_ms)
            start_ads_ms = 0
        if end_ads_ms > len(audio_segment):
            logger.info(f"transcript_{index}_logging.json End time is greater than segment duration or None, setting to segment duration", end_ads_ms)
            end_ads_ms = len(audio_segment)
        # audio = AudioSegment.from_wav("sliced_result.wav")
        logger.info(f"start_ads_ms: {start_ads_ms}, end_ads_ms: {end_ads_ms}::: for transcript_{index}_logging.json")

        audio_before_ad = audio_segment[:start_ads_ms]
        audio_after_ad = audio_segment[end_ads_ms:]
        # Concatenate audio segments
        return audio_before_ad + audio_after_ad


def remove_ads_from_audio(audio_file):
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
    segments = [audio[i:i + segment_duration_ms] for i in range(0, duration_ms, segment_duration_ms)]

    finished_audio_without_ads = AudioSegment.empty()
    # if not os.path.exists("transcript.json"):

    logger.info(f"Initializing Model Pool with {NUMBER_OF_MODELS} models")
    initialize_model_pool(check_cuda())

    # Using ThreadPoolExecutor to process each segment
    with concurrent.futures.ThreadPoolExecutor(max_workers=model_pool.qsize()) as executor:
        logger.info(f"Using {model_pool.qsize()} models for processing")
        # Submit all segments to the executor
        future_to_segment = {executor.submit(process_audio_segment, i, segments[i]): i for i in range(len(segments))}
        
        # Collect results as they complete
        results = []
        for future in concurrent.futures.as_completed(future_to_segment):
            segment_index = future_to_segment[future]
            logger.info(f"Processing segment for segment index {segment_index}, for transcript_{segment_index}_logging.json")
            try:
                result = future.result()
                results.append((segment_index, result))  # Store results along with their original index
            except Exception as exc:
                logger.error(f"Segment {segment_index} generated an exception: {exc}")
                traceback.print_exc()
        # executor.shutdown(wait=True)
    logger.info(f"Finished processing audio segments, exporting finished mp3")
    results.sort(key=lambda x: x[0])
    # concatenate the segments without ads
    finished_audio_without_ads = sum(x[1] for x in results)
    # Save the result
    finished_audio_without_ads.export("finished_audio_without_ads.mp3", format="mp3")
    # Return the duration of the finished audio in seconds
    logger.info(f"Finished audio without ads duration: {len(finished_audio_without_ads) / 1000} seconds")
    return len(finished_audio_without_ads) / 1000, original_duration
