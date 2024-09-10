# logger_setup.py
import logging

def setup_logger():
    logger = logging.getLogger("jusskipit")
    logger.setLevel(logging.DEBUG)

    # Create handlers
    console_handler = logging.StreamHandler()
    file_handler = logging.FileHandler('jusskipit.log')
    console_handler.setLevel(logging.DEBUG)
    file_handler.setLevel(logging.INFO)

    # Create formatters and add them to handlers
    console_format = logging.Formatter('%(name)s - %(levelname)s - %(filename)s - %(message)s')
    file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s - %(message)s')
    console_handler.setFormatter(console_format)
    file_handler.setFormatter(file_format)

    # Add handlers to the logger
    # logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger

logger = setup_logger()
