"""
Image capture from http cameras

The camera url can be:
  - a snapshot url, which returns one JPEG image (preferred - quickest and lightest), or
  - an MJPEG stream url, in which case the first frame is used and the connection closed.

The camera already delivers JPEG images, so they are saved as they are,
without decoding or re-encoding them.

Frames in an MJPEG stream are found by their JPEG start / end markers, so this works
whatever boundary string the camera uses (as in duetPrintGuard utils/mjpeg_source.py).
"""
import os
import time

import requests

from logger_module import logger

JPEG_START = b'\xff\xd8'
JPEG_END = b'\xff\xd9'
READ_CHUNK_SIZE = 16384
MAX_IMAGE_BYTES = 20 * 1024 * 1024  # Safety limit - no single image should be this big
TIMEOUT = (5, 10)  # Seconds to connect, and to wait for data
MAX_SECONDS = 15  # Give up if an image takes longer than this in total


def is_http_url(url):
    return url.lower().startswith(('http://', 'https://'))


def fetch_image(url):
    # The JPEG bytes from a snapshot or MJPEG stream url, or None (the reason is logged)
    try:
        with requests.get(url, stream=True, timeout=TIMEOUT) as r:
            r.raise_for_status()
            content_type = r.headers.get('Content-Type', '').lower()
            if content_type.startswith('multipart/'):
                return _first_frame(r, url)
            return _whole_image(r, url, content_type)
    except requests.exceptions.RequestException as e:
        logger.info('Could not get an image from ' + url + ' -- ' + str(e))
        return None


def _whole_image(r, url, content_type):
    # A snapshot url - the whole response is the image
    data = b''
    deadline = time.time() + MAX_SECONDS
    for chunk in r.iter_content(chunk_size=READ_CHUNK_SIZE):
        data += chunk
        if len(data) > MAX_IMAGE_BYTES or time.time() > deadline:
            logger.info(url + ' did not return a single image. If it is a stream, it must be MJPEG')
            return None
    if not data.startswith(JPEG_START):
        logger.info(url + ' did not return a JPEG image (Content-Type: ' + content_type + ')')
        return None
    return data


def _first_frame(r, url):
    # An MJPEG stream url - return the first complete frame
    buffer = b''
    deadline = time.time() + MAX_SECONDS
    for chunk in r.iter_content(chunk_size=READ_CHUNK_SIZE):
        buffer += chunk
        start = buffer.find(JPEG_START)
        if start == -1:
            buffer = buffer[-1:]  # Keep the last byte in case a marker is split across chunks
        else:
            end = buffer.find(JPEG_END, start + 2)
            if end != -1:
                return buffer[start:end + 2]
            buffer = buffer[start:]  # Wait for the rest of this frame
        if len(buffer) > MAX_IMAGE_BYTES or time.time() > deadline:
            logger.info('No complete image was found in the stream from ' + url)
            return None
    logger.info('The stream from ' + url + ' ended before an image was received')
    return None


def capture_image(url, filename):
    # Save one image from the camera url to filename.  Returns True if successful
    data = fetch_image(url)
    if data is None:
        return False
    tempname = filename + '.part'  # So a partly written file is never used in a video
    try:
        with open(tempname, 'wb') as f:
            f.write(data)
        os.replace(tempname, filename)
    except OSError as e:
        logger.info('Could not save image ' + filename + ' -- ' + str(e))
        return False
    logger.debug('Captured ' + str(len(data)) + ' bytes from ' + url)
    return True
