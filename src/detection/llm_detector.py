import openai
from openai import OpenAI

# from openai import AsyncOpenAI
# from openai import AssistantEventHandler
# from typing_extensions import override
# from pprint import pprint
import re
from src.config.constants import CONFIDENCE_SCORE, OPENAI_MODEL
import time
import backoff
from src.logger.logger_setup import logger
import json
from src.config import settings
from src.config.settings import get_setting
from src.config.prompts import (
    ad_checker_assistant_instructions,
    sponsor_instructions,
    get_ad_checker_instructions,
)

OPENAI_API_KEY = get_setting(settings.OPENAI_API_KEY)

client = OpenAI(api_key=OPENAI_API_KEY)
# client = AsyncOpenAI()
assistant_id = None

# import threading
# limiting the number of threads to 1
# semaphore = threading.Semaphore(1)

# Create a lock for each file
# event_handler_lock = Lock()


def _create_assistant():

    assistant = client.beta.assistants.create(
        name="Podcast Advertisement Recognizer",
        instructions=ad_checker_assistant_instructions,
        tools=[{"type": "file_search"}],
        temperature=0,
        #   model="gpt-4-turbo-preview",
        model=OPENAI_MODEL,
        # model="US Immigration Law AI",
        # https://chat.openai.com/g/g-2g79Fgyn6-us-immigration-law-ai
    )

    return assistant.id


def _retrieve_assistant(lock):
    logger.info(f"Retrieving assistant...")
    response = client.beta.assistants.list()
    global assistant_id
    with lock:
        if not assistant_id:
            logger.info(f"Assistant Not Found in Var Cache retrieving assistant...")
            for assistant in response.data:
                logger.info(f"Assistant Found: {assistant.id}")
                # client.beta.assistants.retrieve(assistant.id)
                assistant_id = assistant.id
                return assistant_id
            else:
                logger.info("No assistant found, creating assistant...")
                assistant_id = _create_assistant()
                return assistant_id
        return assistant_id


def _create_thread(filename, path, sponsors, lock):
    # thread = client.beta.threads.create()

    # Create a vector store called "Financial Statements"
    vector_store = client.vector_stores.create(name=filename)

    # Ready the files for upload to OpenAI
    file_paths = [path]
    file_streams = [open(path, "rb") for path in file_paths]

    # Use the upload and poll SDK helper to upload the files, add them to the vector store,
    # and poll the status of the file batch for completion.
    file_batch = client.vector_stores.file_batches.upload_and_poll(
        vector_store_id=vector_store.id, files=file_streams
    )

    # You can print the status and the file counts of the batch to see the result of this operation.
    logger.info(file_batch.status)
    logger.info(file_batch.file_counts)

    # print(f"File ID: {message_file.id}, Created for file: {filename} and path: {path}")
    logger.info(
        f"File ID: {file_batch.id}, Created for file: {filename} and path: {path}"
    )

    # Create a thread and attach the file to the message
    thread = client.beta.threads.create(
        messages=[
            {
                "role": "user",
                "content": get_ad_checker_instructions(sponsors),
            }
        ],
        tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
    )

    logger.info(
        f"Thread ID: {thread.id}, Created for file: {filename} and path: {path}"
    )

    # The thread now has a vector store with that file in its tool resources.
    # logger.info(thread.tool_resources.file_search)

    return thread


# First, we create a EventHandler class to define
# how we want to handle the events in the response stream.

# import json


def obj_dict(obj):
    return obj.__dict__


# class EventHandler(AssistantEventHandler):
class EventHandler:
    def __init__(self):
        # super().__init__()
        self.results = {}

    # @override
    def on_text_created(self, text) -> None:
        logger.info(f"\nassistant > ", end="", flush=True)

    # @override
    def on_tool_call_created(self, tool_call):
        logger.info(f"\nassistant > {tool_call.type}\n", flush=True)

    # @override
    def on_message_done(self, message) -> None:
        # logger.info a citation to the file searched
        # logger.info(f"On Message Done: {message}")
        message_content = message.content[0].text
        annotations = message_content.annotations
        citations = []
        for index, annotation in enumerate(annotations):
            message_content.value = message_content.value.replace(
                annotation.text, f"[{index}]"
            )
            if file_citation := getattr(annotation, "file_citation", None):
                cited_file = client.files.retrieve(file_citation.file_id)
                citations.append(f"[{index}] {cited_file.filename}")

        logger.info(f"Message content value:: {message_content.value}")
        # logger.info("##############################################")
        self.results["message"] = parse_message(message_content.value)
        logger.info(f"Results: {self.results['message']}")
        self.results["citations"] = citations


# Then, we use the `create_and_stream` SDK helper
# with the `EventHandler` class to create the Run
# and stream the response.


def parse_message(message):
    if "```" in message:
        logger.info("Removing code block from message")
        # Extract the JSON content between the code block markers
        json_match = re.search(r"```json\s*(\{.*\})\s*```", message, re.DOTALL)
        if json_match:
            message = json_match.group(1)
        else:
            logger.error("No JSON data found in message. Returning default values.")
            return [float("inf"), float("-inf"), 0]  # set min to inf and max to -inf

    try:
        logger.info("Parsing message...")
        # Attempt to parse the JSON message
        data = json.loads(message)
        logger.info(f"Parsed JSON data: {data}")
    except json.JSONDecodeError:
        # If JSON parsing fails, use regex to extract JSON data
        logger.error(
            "JSON parsing failed. Attempting to extract JSON data using regex."
        )
        json_match = re.search(r"\{.*\}", message)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
            except json.JSONDecodeError:
                logger.error(
                    "Invalid JSON format after extraction. Returning default values."
                )
                return [
                    float("inf"),
                    float("-inf"),
                    0,
                ]  # set min to inf and max to -inf
        else:
            logger.error("No JSON data found in message. Returning default values.")
            return [float("inf"), float("-inf"), 0]  # set min to inf and max to -inf

    # Extract confidence score
    confidence_score = data.get("confidence_score", 0)

    # Extract all timestamps
    timestamps = data.get("timestamps", [])

    all_min_timestamps = []
    all_max_timestamps = []

    for timestamp in timestamps:
        start = timestamp.get("start", 0)
        end = timestamp.get("end", 0)

        logger.info(f"Parsing message: {message}")
        logger.info(f"Parsed Timestamps: start={start}, end={end}")

        # Append the start and end times to the lists
        all_min_timestamps.append(start)
        all_max_timestamps.append(end)

    # Handle case where there are no timestamps
    if not all_min_timestamps or not all_max_timestamps:
        logger.error("No timestamps provided. Returning default values.")
        return [float("inf"), float("-inf"), 0]  # set min to inf and max to -inf

    overall_min_timestamp = min(all_min_timestamps)
    overall_max_timestamp = max(all_max_timestamps)

    if confidence_score > 80 and (15 < (overall_max_timestamp - overall_min_timestamp)):
        logger.info(
            f"Confidence Score: {confidence_score}, Timestamps: {overall_min_timestamp} to {overall_max_timestamp}"
        )
        logger.info(f"Ad likely present at end of audio segment, passing for skip")
    elif confidence_score < CONFIDENCE_SCORE or (
        20 > (overall_max_timestamp - overall_min_timestamp)
    ):
        logger.info(
            f"""Confidence score is less than {CONFIDENCE_SCORE} or ad is less than 20 seconds with low ad confidence 
              Confidence Score: {confidence_score}""".replace(
                "\n", "  "
            )
        )
        logger.info(
            f"confidence_score: {confidence_score}, min_timestamp: {overall_min_timestamp}, max_timestamp: {overall_max_timestamp}"
        )
        return [float("inf"), float("-inf"), 0]  # set min to inf and max to -inf

    return [overall_min_timestamp, overall_max_timestamp, confidence_score]


@backoff.on_exception(backoff.expo, openai.RateLimitError)
def get_specific_timestamps_using_llm(filename, path, sponsors, lock):
    logger.info(f"##################################################################")
    logger.info(f"Entering get_specific_timestamps_using_llm")
    logger.info(f"filename: {filename}, path: {path}, sponsors: {sponsors}")
    logger.info(f"##################################################################")
    with lock:
        logger.info(f"Lock Acquired for file: {filename} and path: {path}")
        thread = _create_thread(
            filename=filename, path=path, sponsors=sponsors, lock=lock
        )
        #   thread_id = _assistant_call(filename=filename, path=path)

        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=_retrieve_assistant(lock),
            # instructions="Please provide the answer to the confidence score and time stamps if applicable of the transcript in json format",
            # event_handler=event_handler
            # response_format={ "type": "json_object" },
            # tools=[{"type": "file_search"}],no
        )

        logger.info(f"Run ID: {run.id}, Created for file: {filename} and path: {path}")

        return run, thread


def get_run_output(run, thread):
    while run.status.lower() in ["queued", "in_progress"]:
        retrieving_thread_run = client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id,
        )

        logger.info(f"Run status: {retrieving_thread_run.status}")

        if retrieving_thread_run.status.lower() == "completed":
            messages = client.beta.threads.messages.list(
                thread_id=thread.id, run_id=run.id
            )
            # logger.info(f"Messages: {messages.data}")
            event_handler = EventHandler()
            event_handler.on_message_done(messages.data[0])
            logger.info("\n")
            # Step 6: Retrieve the Messages added by the Assistant to the Thread
            logger.info(f"#########################################################")
            logger.info(f"Thread ID: {thread.id}, and Run ID: {run.id}")
            logger.info(event_handler.results)
            logger.info(f"#########################################################")
            message = event_handler.results["message"]
            return message[0], message[1], message[2]
        elif (
            retrieving_thread_run.status == "queued"
            or retrieving_thread_run.status == "in_progress"
        ):
            time.sleep(5)
            pass
        else:
            logger.info(f"Run status: {retrieving_thread_run.status}")
            logger.info(f"Thread ID: {thread.id}, and Run ID: {run.id}")
            logger.info(f"Run output: {retrieving_thread_run}")
            logger.info("No timestamps provided. Returning None.")
            return [float("inf"), float("-inf"), 0]  # set min to inf and max to -inf


def extract_sponsors(response_content):
    match = re.search(r"Sponsors:\s*\[(.*?)\]", response_content)
    if match:
        sponsors = match.group(1).split(", ")
        return [sponsor.strip() for sponsor in sponsors]
    return []


def fetch_sponsors(podcast_description):
    logger.info(f"Fetching sponsors for podcast description: {podcast_description}")
    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=sponsor_instructions,
            input=podcast_description,
            temperature=0,
        )
        logger.info(f"Response: {response}")

        # Extract and print the list from the response
        return extract_sponsors(response.output_text.strip())
    except Exception as e:
        logger.error(f"Error fetching sponsors: {e}")
        return []
