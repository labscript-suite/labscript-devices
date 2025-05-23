import os
import logging

# Configure the logger
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, 'logs.log')

# Create logger
logger = logging.getLogger("logs")
logger.setLevel(logging.DEBUG)

# Create file handler and set level to debug
handler = logging.FileHandler(LOG_FILE)
handler.setLevel(logging.DEBUG)

# Create formatter and set it for the handler
formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
handler.setFormatter(formatter)

# Add handler to the logger
logger.addHandler(handler)

# Test the logger in the config file
logger.info("Logger initialized successfully")
