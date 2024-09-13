import openai
from openai import OpenAI
# from openai import AsyncOpenAI
from openai import AssistantEventHandler
from typing_extensions import override
from pprint import pprint
from src.config.constants import CONFIDENCE_SCORE
import time
import backoff
from src.logger.logger_setup import logger
import boto3
import os
# from threading import Lock
# from model.conversation_storage import store_conversation
# from langchain_community.document_loaders import PyPDFLoader
# from langchain_community.vectorstores import FAISS
# from langchain_openai import OpenAIEmbeddings

try:
    ssm = boto3.client('ssm', region_name='us-east-1')
    OPENAI_API_KEY = ssm.get_parameter(Name="/openai/api_key", WithDecryption=True)['Parameter']['Value']
except Exception as e:
    logger.error(f"Error getting OpenAI API Key: {e}")
    raise e

client = OpenAI(api_key=OPENAI_API_KEY)
# client = AsyncOpenAI()
assistant_id = None

# import threading
# limiting the number of threads to 1
# semaphore = threading.Semaphore(1)

# Create a lock for each file
# event_handler_lock = Lock()

# this is the most important indicator for an ad being present

instructions = f"""on a scale of 1 - 100 what degree of confidence
        do you have that the attached text contains an advertisement.
        Give the confidence score as 'Confidence Score['Score']'.
        If your confidence is greater than {CONFIDENCE_SCORE} then please give the
        specific timestamps from the start of the ad segments to the end. 
        The output timestamps should be in the format 'Timestamps: [Start] - [End]', 
        and match the format of the timestamps in the transcript.
        Just provide the minimum and maximum timestamps for each ad segment.
        When determining timestamps, consider that in most cases a particular ad segment will run from
        30 to 60 seconds. Longer or shorter ads are possible, but this is a good rule of thumb when 
        determining the timestamp of each ad segment.
        
        Consider that advertisements will usually have an explicit sponsor mentioned,
        a change in tone or pace, or a jingle. They will often encourage the listener to 
        purchase or subscribe to something. The advertisement could also be catered to a listener's
        business. Ad text will often contain Often a call to action is also given,
        such as visiting a specific site, using a promo code, a discount is available, etc.

        If there is no sponsor explicitly mentioned, then lower the confidence score significantly.
        
        If no sponsor is explicitly mentioned then the confidence score should be less than 50.

        Be Concise, only provide the score and the timestamps."""

def _create_assistant():
  
#   instructions = f"""
#     You are tasked with identifying advertisement segments in the attached transcript. 
#     Please follow these instructions:

#     1. On a scale of 1 to 100, what degree of confidence do you have that the attached text contains an advertisement?
#     - Provide the confidence score in the format: 'Confidence Score: [Score]'.

#     2. If your confidence score is greater than 50, identify the specific timestamps for each ad segment.
#     - Provide the start and end timestamps for each ad segment in the format: 'Timestamps: [Start] - [End]'.

#     Be concise and only provide the confidence score and the timestamps.
#     """

  # logger.info(f"Creating assistant with instructions: {instructions}")

  assistant = client.beta.assistants.create(
    name="Podcast Advertisement Recognizer",
    instructions=instructions,
    tools=[{"type": "file_search"}],
    temperature=0,
  #   model="gpt-4-turbo-preview",
    model="gpt-4o",
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


def _create_thread(filename, path, lock):
  # thread = client.beta.threads.create()

  # Create a vector store caled "Financial Statements"
  vector_store = client.beta.vector_stores.create(name=filename)

  # Ready the files for upload to OpenAI
  file_paths = [path]
  file_streams = [open(path, "rb") for path in file_paths]

   # Use the upload and poll SDK helper to upload the files, add them to the vector store,
   # and poll the status of the file batch for completion.
  file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
    vector_store_id=vector_store.id, files=file_streams
  )

  # You can print the status and the file counts of the batch to see the result of this operation.
  logger.info(file_batch.status)
  logger.info(file_batch.file_counts)

  assistant = client.beta.assistants.update(
    assistant_id=_retrieve_assistant(lock),
    tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
  )

  # Upload the user provided file to OpenAI
  # message_file = client.files.create(
  #   file=open(path, "rb"), purpose="assistants"
  # )
  
  # print(f"File ID: {message_file.id}, Created for file: {filename} and path: {path}")
  logger.info(f"File ID: {file_batch.id}, Created for file: {filename} and path: {path}")

  # Create a thread and attach the file to the message
  thread = client.beta.threads.create(
    messages=[
      {
        "role": "user",
        "content": instructions,
        # Attach the new file to the message.
        # "attachments": [
          # { "file_id": file_batch.id, "tools": [{"type": "file_search"}] }
        #  {
        # ],
      }
    ],
        tool_resources={
          "file_search": {
          "vector_store_ids": [vector_store.id]
          }
      }
  )

  logger.info(f"Thread ID: {thread.id}, Created for file: {filename} and path: {path}")
 
  # The thread now has a vector store with that file in its tool resources.
  # logger.info(thread.tool_resources.file_search)

  return thread

# First, we create a EventHandler class to define
# how we want to handle the events in the response stream.

import json

def obj_dict(obj):
    return obj.__dict__

 
# class EventHandler(AssistantEventHandler):
class EventHandler():
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
        self.results['message'] = parse_message(message_content.value)
        logger.info(f"Results: {self.results['message']}")
        self.results['citations'] = citations

# Then, we use the `create_and_stream` SDK helper 
# with the `EventHandler` class to create the Run 
# and stream the response.

def parse_message(message):
    import re
    # sample message from llm
    # input_string = "Confidence Score[95]\n\nTimestamps:\n- 242.66 to 253.38\n- 269.06 to 273.48\n- 275.08 to 285.98\n- 289.36 to 294.35\n- 305.44 to 315.08"

    # Extract confidence score
    confidence_score = int(re.search(r'Confidence Score\s*\[?(\d+)\]?', message, re.IGNORECASE).group(1))

    # Extract all numeric values from the timestamps
    numeric_values = [float(num) for num in re.findall(r'(\d+\.\d+)', message)]

    logger.info(f"Parsing message: {message}")
    logger.info(f"Parsed Timestamps: {numeric_values}")

    # Find the minimum and maximum values
    try:
        min_timestamp = min(numeric_values)
        max_timestamp = max(numeric_values)
    except Exception:
        logger.error("No timestamps provided. Returning None.")
        return [float('inf'), float('-inf'), 0] # set min to inf and max to -inf
    if confidence_score > 80 and (15 < (max_timestamp - min_timestamp)):
        logger.info(f"Confidence Score: {confidence_score}, Timestamps: {min_timestamp} to {max_timestamp}")
        logger.info(f"Ad likely present at end of audio segment, passing for skip")
    elif confidence_score < CONFIDENCE_SCORE or (20 > (max_timestamp - min_timestamp)):
        logger.info(f"""Confidence score is less than {CONFIDENCE_SCORE} or ad is less than 20 seconds with low ad confidence 
              Confidence Score: {confidence_score}""".replace("\n", "  "))
        logger.info(f"confidence_score: {confidence_score}, min_timestamp: {min_timestamp}, max_timestamp: {max_timestamp}")
        return [float('inf'), float('-inf'), 0] # set min to inf and max to -inf

    # logger.info the parsed data
    logger.info(f"Confidence Score: {confidence_score}, Timestamps: {min_timestamp} to {max_timestamp}")
    return [min_timestamp, max_timestamp, confidence_score]


@backoff.on_exception(backoff.expo, openai.RateLimitError)
def get_specific_timestamps_using_llm(filename, path, lock):
    logger.info(f"##################################################################")
    logger.info(f"Entering get_specific_timestamps_using_llm")
    logger.info(f"filename: {filename}, path: {path}")
    logger.info(f"##################################################################")
    with lock:
      logger.info(f"Lock Acquired for file: {filename} and path: {path}")
      thread = _create_thread(filename=filename, path=path, lock=lock)
      #   thread_id = _assistant_call(filename=filename, path=path)

      run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=_retrieve_assistant(lock),
        # instructions="Please provide the answer to the confidence score and time stamps if applicable of the transcript in json format",
        # event_handler=event_handler
        # response_format={ "type": "json_object" },
        # tools=[{"type": "file_search"}],no
      )

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
          thread_id=thread.id,
          run_id=run.id
        )
        # logger.info(f"Messages: {messages.data}")
        event_handler=EventHandler()
        event_handler.on_message_done(messages.data[0])
        logger.info("\n")
        # Step 6: Retrieve the Messages added by the Assistant to the Thread
        logger.info(f"#########################################################")
        logger.info(f"Thread ID: {thread.id}, and Run ID: {run.id}")
        logger.info(event_handler.results)
        logger.info(f"#########################################################")
        message = event_handler.results['message']
        return message[0], message[1], message[2]
      elif retrieving_thread_run.status == "queued" or retrieving_thread_run.status == "in_progress":
          time.sleep(5)
          pass
      else:
          logger.info(f"Run status: {retrieving_thread_run.status}")
          logger.info(f"Thread ID: {thread.id}, and Run ID: {run.id}")
          logger.info(f"Run output: {retrieving_thread_run}")
          logger.info("No timestamps provided. Returning None.")
          return [float('inf'), float('-inf'), 0] # set min to inf and max to -inf
