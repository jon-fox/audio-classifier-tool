import boto3

from src.config.settings import REGION

_ssm = None


def get_parameter(name, decrypt=False):
    global _ssm
    if _ssm is None:
        _ssm = boto3.client("ssm", region_name=REGION)
    return _ssm.get_parameter(Name=name, WithDecryption=decrypt)["Parameter"]["Value"]
