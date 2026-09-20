"""Cloud provider integrations.

Each provider lives in its own subpackage (aws/ today; others can slot in).
src/config/settings.py routes remote config lookups here based on APP_MODE.
"""


def get_parameter(provider, name, decrypt=False):
    if provider == "aws":
        from audioclassifier.cloud.aws.params import get_parameter as aws_get_parameter

        return aws_get_parameter(name, decrypt)
    raise ValueError(f"Unsupported cloud provider: {provider}")
