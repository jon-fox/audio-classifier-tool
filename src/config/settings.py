import os
from collections import namedtuple

# app_mode is handling if we run locally or in cloud
CLOUD = os.getenv("APP_MODE", "local").lower()
CLOUD_ENABLED = CLOUD != "local"
AWS_ENABLED = CLOUD == "aws"

REGION = os.getenv("REGION", "us-east-1")

Setting = namedtuple(
    "Setting",
    ["env_var", "remote_param", "decrypt", "required"],
    defaults=[None, False, False],
)

OPENAI_API_KEY = Setting(
    "OPENAI_API_KEY", "/openai/api_key", decrypt=True, required=True
)
DISCORD_WEBHOOK_URL = Setting(
    "DISCORD_WEBHOOK_URL", "/application/discord/errors_webhook"
)
APP_STORAGE_BUCKET = Setting("APP_STORAGE_BUCKET", "/app/app_storage_bucket")
CDN_BASE_URL = Setting("CDN_BASE_URL", "/cloudfront/distribution/url")
SQS_URL = Setting("SQS_URL", "/sqs/audio_processing/url")


def get_setting(setting):
    value = os.getenv(setting.env_var)
    if value:
        return value
    if CLOUD_ENABLED and setting.remote_param:
        from src.cloud import get_parameter

        return get_parameter(CLOUD, setting.remote_param, setting.decrypt)
    if setting.required:
        remote = (
            f" (or cloud parameter {setting.remote_param} with APP_MODE=aws)"
            if setting.remote_param
            else ""
        )
        raise RuntimeError(f"Missing required setting: set {setting.env_var}{remote}")
    return None
