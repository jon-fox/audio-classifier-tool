import logging

# Library-quiet by default; the CLI (or the embedding app) attaches handlers
logger = logging.getLogger("audioclassifier")
logger.addHandler(logging.NullHandler())


def configure_logging(log_file="audioclassifier.log", level=logging.INFO, stream=False):
    """stream=True also logs to stdout (for container logs)."""
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s - %(message)s"
    )
    handlers = [logging.FileHandler(log_file)]
    if stream:
        handlers.append(logging.StreamHandler())
    for handler in handlers:
        handler.setLevel(level)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
