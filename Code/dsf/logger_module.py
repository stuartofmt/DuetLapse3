"""
Logging for duetLapse3

Derived from the duetPrintGuard logger_module but adapted for duetLapse3:
  - The logger exists at import time so any module can simply do
        from logger_module import logger
  - Console output is set up first (setup_logger) and the logfile later
    (create_log_file), once the directory for it is known
  - The logfile is moved to follow each job (move_log_file)
  - Formats include the thread name, as duetLapse3 is multi-threaded
"""
import logging
import shutil
import sys
import time

logger = logging.getLogger('duetLapse3')
logger.propagate = False

logfilename = ''  # Current logfile

FILE_FORMAT = '%(asctime)s - %(threadName)s - %(message)s'


def setup_logger(prefix, console=True):
    # Console output only - the file handler is created later by create_log_file
    if console:
        c_handler = logging.StreamHandler(sys.stdout)
        c_format = logging.Formatter(prefix + ' %(threadName)s - %(message)s')
        c_handler.setFormatter(c_format)
        logger.addHandler(c_handler)
    return logger


def close_log_file():
    # Remove any file handler. Returns True if one was removed
    closed = False
    for handler in list(logger.handlers):
        if isinstance(handler, logging.FileHandler):
            handler.flush()
            handler.close()
            logger.removeHandler(handler)
            closed = True
    return closed


def _add_file_handler(filename, mode):
    global logfilename
    f_handler = logging.FileHandler(filename, mode=mode, encoding='utf-8')
    f_handler.setFormatter(logging.Formatter(FILE_FORMAT))
    logger.addHandler(f_handler)
    logfilename = filename


def create_log_file(filename, wait=0):
    # Start a new (empty) logfile, replacing any existing one
    # wait - seconds to allow messages to propagate after closing the old file
    # logfilename is set first so a move_log_file during the wait does not
    # move the previous logfile
    global logfilename
    logfilename = filename
    if close_log_file() and wait > 0:
        time.sleep(wait)
    _add_file_handler(filename, 'w')
    return logfilename


def move_log_file(newfilename):
    # Move the current logfile to newfilename and continue appending to it
    oldfilename = logfilename
    close_log_file()
    try:
        logger.debug('Renaming logfile to ' + newfilename)
        shutil.move(oldfilename, newfilename)
    except shutil.Error as e:
        logger.info('Error on move of logfile ' + str(e))
    _add_file_handler(newfilename, 'a')
    return logfilename


def set_log_level(debug):
    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    return logger
