import logging

# Library-quiet by default; the CLI (or the embedding app) attaches handlers
logger = logging.getLogger("audioclassifier")
logger.addHandler(logging.NullHandler())


def configure_logging(log_file="audioclassifier.log", level=logging.INFO):
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(log_file)
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(filename)s - %(message)s"
        )
    )
    logger.addHandler(handler)
