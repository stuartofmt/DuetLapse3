"""
Logging for duetLapse3

Derived from the duetPrintGuard logger_module but adapted for duetLapse3:
  - The logger exists at import time so any module can simply do
        from logger_module import logger
  - Console output is set up first (setup_logger) and the logfile later (create_log_file)
  - Formats include the thread name, as duetLapse3 is multi-threaded
"""
import logging
import os
import re
import sys

# Passwords are never logged: password=xxx in the printer's urls, and a login in a camera url (http://user:xxx@host)
SECRETS = re.compile(r'(password=)[^&\s\'"]*|(://[^/\s:@]+:)[^/\s@]+(?=@)')


class MaskSecrets(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        masked = SECRETS.sub(lambda m: (m.group(1) or m.group(2)) + '***', message)
        if masked != message:
            record.msg, record.args = masked, ()
        return True


logger = logging.getLogger('duetLapse3')
logger.propagate = False
logger.addFilter(MaskSecrets())

logfilename = ''  # Current logfile

FILE_FORMAT = '%(asctime)s - %(threadName)s - %(message)s'

#  Used for debugging by calling current_func_name(x)
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.


def current_func_name(n=0):
    return sys._getframe(n + 1).f_code.co_name


def setup_logger(prefix, console=True):
    # Console output only - the file handler is created later by create_log_file
    # Called first with the program's name, before the settings are read, then again with the printer's address:
    # each call replaces the console output set up before
    for handler in list(logger.handlers):
        if type(handler) is logging.StreamHandler:
            logger.removeHandler(handler)
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


def create_log_file(filename, previous):
    # Start a new (empty) logfile.  The one before it becomes previous, replacing the one before that
    close_log_file()
    try:
        os.replace(filename, previous)
    except OSError:  # The first logfile
        pass
    _add_file_handler(filename, 'w')
    return logfilename


def set_log_level(debug):
    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    return logger
