import os
import logging
from logging.handlers import TimedRotatingFileHandler

logger = logging.getLogger('my_logger')
logger.setLevel(logging.DEBUG)

logDir = r"C:\Temp\logs"
if os.path.isdir(logDir):
    pass
else:
    os.makedirs(logDir)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - in the "%(funcName)s" function - %(message)s')

# file_handler_debug = logging.FileHandler(r'C:\Temp\logs\pyscope_debug.log')
file_handler_debug = TimedRotatingFileHandler(r'C:\Temp\logs\pyscope_debug.log', when="H", interval=1, backupCount=168)
file_handler_debug.setLevel(logging.DEBUG)
file_handler_debug.setFormatter(formatter)
logger.addHandler(file_handler_debug)


file_handler_info = logging.FileHandler(r'C:\Temp\logs\pyscope_info.log')
# file_handler_info = TimedRotatingFileHandler(r'C:\Temp\logs\pyscope_info.log', when="S", interval=3, backupCount=5)
file_handler_info.setLevel(logging.INFO)
file_handler_info.setFormatter(formatter)
logger.addHandler(file_handler_info)


stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)
