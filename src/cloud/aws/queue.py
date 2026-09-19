import boto3

from src.config.settings import REGION

_sqs = None
_lambda = None


def _sqs_client():
    global _sqs
    if _sqs is None:
        _sqs = boto3.client("sqs", REGION)
    return _sqs


def receive_message(queue_url, max_messages=1, wait_seconds=10):
    return _sqs_client().receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=max_messages,
        WaitTimeSeconds=wait_seconds,
    )


def delete_message(queue_url, receipt_handle):
    return _sqs_client().delete_message(
        QueueUrl=queue_url, ReceiptHandle=receipt_handle
    )


def invoke_lambda(function_name, payload):
    global _lambda
    if _lambda is None:
        _lambda = boto3.client("lambda", REGION)
    return _lambda.invoke(
        FunctionName=function_name,
        InvocationType="Event",  # Asynchronous invocation
        Payload=payload,
    )
