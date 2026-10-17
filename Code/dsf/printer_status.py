"""
Printer status reference for duetLapse3

The printer reports its status in the object model as state.status.  This module says, for each
status, what it means to duetLapse3 (is a print job running?  should images be taken?) and which
status changes are allowed.  It only describes - it does not talk to the printer or change anything.

Quick use:
    import printer_status as ps

    ps.logical_state('paused')                 # -> LogicalState(status='paused', category='paused', ...)
    ps.logical_state('idle', previous='cancelling').event   # -> 'job_cancelled'
    ps.can_capture('processing')               # -> True
    ps.allowed_next('paused')                  # -> frozenset({'resuming', 'processing', 'cancelling', 'halted'})
    ps.is_valid_transition('idle', 'paused')   # -> False

Allowed transitions (the reference list):
    Standard print lifecycle
        idle --> processing --> decelerating --> paused --> resuming --> processing
        paused --> processing
    Cancellation
        processing --> cancelling --> idle
        paused --> cancelling --> idle
    Exceptions and system states
        processing --> halted --> idle
        paused --> halted --> idle
        idle --> busy --> idle
        idle --> configuring --> idle
        idle --> simulating --> idle

Also known (not in the reference list):
    pausing       - sent by the firmware while a pause is happening.  Treated the same as decelerating
    disconnected  - set by duetLapse3 when the printer does not answer
    unknown       - set by duetLapse3 before the first status is read

Run this file to print the tables:  python printer_status.py
"""
from collections import namedtuple

###########################
# Categories - what a status means to duetLapse3
###########################

IDLE = 'idle'                  # No print job.  Waiting for one to start
PRINTING = 'printing'          # A print job is running - images are taken
PAUSING = 'pausing'            # A print job is stopping for a pause
PAUSED = 'paused'              # A print job is paused - images are taken only for detect = pause
RESUMING = 'resuming'          # A paused print job is starting again
ENDING = 'ending'              # A print job is ending early (cancelled or halted) - the video is made
BUSY = 'busy'                  # No print job, but the printer is doing something else (e.g. a macro)
SIMULATING = 'simulating'      # A simulated print - nothing moves, so no images are taken
NOT_CONNECTED = 'not_connected'  # No usable status from the printer

CATEGORIES = (IDLE, PRINTING, PAUSING, PAUSED, RESUMING, ENDING, BUSY, SIMULATING, NOT_CONNECTED)

###########################
# Statuses
###########################

# Where a status comes from
REFERENCE = 'reference'    # In the reference list above
FIRMWARE = 'firmware'      # Sent by the firmware, but not in the reference list
DUETLAPSE3 = 'duetLapse3'  # Set by duetLapse3 itself, never by the printer

# job_active - a print job is in progress (started and not yet finished)
# capture    - duetLapse3 takes images in this status (detect = layer or seconds).
#              paused is False here - for detect = pause, images are taken at a pause (see capture_on_pause)
Status = namedtuple('Status', ['name', 'category', 'job_active', 'capture', 'source', 'description'])

STATUSES = {s.name: s for s in [
    Status('idle',         IDLE,          False, False, REFERENCE,  'Nothing is printing'),
    Status('processing',   PRINTING,      True,  True,  REFERENCE,  'Printing'),
    Status('decelerating', PAUSING,       True,  False, REFERENCE,  'Slowing down to pause'),
    Status('pausing',      PAUSING,       True,  False, FIRMWARE,   'Pausing (the same as decelerating)'),
    Status('paused',       PAUSED,        True,  False, REFERENCE,  'Paused'),
    Status('resuming',     RESUMING,      True,  True,  REFERENCE,  'Starting again after a pause'),
    Status('cancelling',   ENDING,        True,  False, REFERENCE,  'The print is being cancelled'),
    Status('halted',       ENDING,        True,  False, REFERENCE,  'Stopped by an emergency stop or error'),
    Status('busy',         BUSY,          False, False, REFERENCE,  'Busy, e.g. running a macro'),
    Status('configuring',  BUSY,          False, False, REFERENCE,  'Being configured'),
    Status('simulating',   SIMULATING,    False, False, REFERENCE,  'Simulating a print - nothing moves'),
    Status('disconnected', NOT_CONNECTED, False, False, DUETLAPSE3, 'The printer does not answer'),
    Status('unknown',      NOT_CONNECTED, False, False, DUETLAPSE3, 'No status has been read yet'),
]}

###########################
# Transitions - status: the statuses that can come next
###########################

TRANSITIONS = {
    'idle':         frozenset({'processing', 'busy', 'configuring', 'simulating'}),
    'processing':   frozenset({'decelerating', 'cancelling', 'halted'}),
    'decelerating': frozenset({'paused'}),
    'paused':       frozenset({'resuming', 'processing', 'cancelling', 'halted'}),
    'resuming':     frozenset({'processing'}),
    'cancelling':   frozenset({'idle'}),
    'halted':       frozenset({'idle'}),
    'busy':         frozenset({'idle'}),
    'configuring':  frozenset({'idle'}),
    'simulating':   frozenset({'idle'}),
}

# Not in the reference list - the firmware's pausing, and duetLapse3's own statuses
EXTRA_TRANSITIONS = {
    'processing':   frozenset({'pausing'}),
    'pausing':      frozenset({'paused'}),
    # The printer can stop answering, and is first seen, in any status
    'disconnected': frozenset(STATUSES) - {'disconnected'},
    'unknown':      frozenset(STATUSES) - {'unknown'},
}

###########################
# Events - what a status change means to duetLapse3
###########################

JOB_STARTED = 'job_started'      # A print job started - start taking images
PAUSE_STARTED = 'pause_started'  # A print job is pausing
JOB_PAUSED = 'job_paused'        # A print job is now paused
JOB_RESUMED = 'job_resumed'      # A paused print job is printing again
JOB_COMPLETED = 'job_completed'  # A print job finished normally - make the video
JOB_CANCELLED = 'job_cancelled'  # A print job was cancelled - make the video
JOB_HALTED = 'job_halted'        # A print job was halted - make the video
CONNECTION_LOST = 'connection_lost'
CONNECTION_RESTORED = 'connection_restored'

# Events that mean the print job is over and its video should be made
JOB_ENDED = frozenset({JOB_COMPLETED, JOB_CANCELLED, JOB_HALTED})

LogicalState = namedtuple('LogicalState', ['status', 'category', 'job_active', 'capture', 'known', 'previous',
                                           'event', 'valid_transition'])

###########################
# Functions
###########################

def normalise(status):
    # The status as used in this module ('' and None become 'unknown')
    status = (status or '').strip()
    return status if status else 'unknown'

def is_known(status):
    return normalise(status) in STATUSES

def info(status):
    # The Status for a status.  An unrecognised status is treated as not connected
    status = normalise(status)
    return STATUSES.get(status, Status(status, NOT_CONNECTED, False, False, 'unrecognised', 'Not a recognised status'))

def category(status):
    return info(status).category

def describe(status):
    return info(status).description

def is_job_active(status):
    return info(status).job_active

def can_capture(status):
    # Whether duetLapse3 takes images in this status (detect = layer or seconds)
    return info(status).capture

def capture_on_pause(status):
    # Whether this is the status in which detect = pause takes its image
    return category(status) == PAUSED

def allowed_next(status, include_extra = True):
    # The statuses that can follow status
    status = normalise(status)
    allowed = TRANSITIONS.get(status, frozenset())
    if include_extra:
        allowed = allowed | EXTRA_TRANSITIONS.get(status, frozenset())
    return allowed

def is_valid_transition(previous, current, include_extra = True):
    # True if the change from previous to current is allowed.  No change is always allowed
    previous, current = normalise(previous), normalise(current)
    if previous == current:
        return True
    if include_extra and current == 'disconnected':  # Can happen at any time
        return True
    return current in allowed_next(previous, include_extra)

def event(previous, current):
    # What the change from previous to current means to duetLapse3 - one of the event names above, or None
    previous, current = normalise(previous), normalise(current)
    if previous == current:
        return None
    was, now = category(previous), category(current)
    if now == NOT_CONNECTED and was != NOT_CONNECTED:
        return CONNECTION_LOST
    if was == NOT_CONNECTED and now != NOT_CONNECTED:
        if previous == 'disconnected':
            return CONNECTION_RESTORED
        return None  # First status read at startup
    if now == PRINTING and was in (IDLE, BUSY, SIMULATING):
        return JOB_STARTED
    if now == PAUSING:
        return PAUSE_STARTED
    if now == PAUSED:
        return JOB_PAUSED
    if now in (RESUMING, PRINTING) and was in (PAUSING, PAUSED):  # Reported once - resuming --> processing is not an event
        return JOB_RESUMED
    if now == ENDING and was != ENDING:
        return JOB_HALTED if current == 'halted' else JOB_CANCELLED
    if now == IDLE and info(previous).job_active and was != ENDING:  # ENDING --> idle was already reported
        return JOB_COMPLETED
    return None

def logical_state(status, previous = None):
    # Everything about the current status that matters to duetLapse3.
    # Give previous (the last status read) to also get the event and whether the change was allowed
    current = normalise(status)
    s = info(current)
    if previous is None:
        return LogicalState(current, s.category, s.job_active, s.capture, is_known(current), None, None, None)
    previous = normalise(previous)
    return LogicalState(current, s.category, s.job_active, s.capture, is_known(current), previous,
                        event(previous, current), is_valid_transition(previous, current))


def _check():
    # Every status used in a transition must be in STATUSES
    for table in (TRANSITIONS, EXTRA_TRANSITIONS):
        for status, nexts in table.items():
            unknown = ({status} | nexts) - set(STATUSES)
            assert not unknown, 'Unknown status in transitions: ' + ', '.join(sorted(unknown))

_check()


if __name__ == '__main__':
    print('%-13s %-14s %-10s %-8s %-11s %s' % ('status', 'category', 'job active', 'capture', 'source', 'description'))
    for s in STATUSES.values():
        print('%-13s %-14s %-10s %-8s %-11s %s' % (s.name, s.category, s.job_active, s.capture, s.source, s.description))
    print('\nAllowed transitions (* = not in the reference list)')
    for status in STATUSES:
        nexts = sorted(allowed_next(status))
        if status in ('disconnected', 'unknown'):
            print('  %-13s --> any status *' % status)
            continue
        if nexts:
            extra = EXTRA_TRANSITIONS.get(status, frozenset())
            print('  %-13s --> %s' % (status, ', '.join(n + ('*' if n in extra else '') for n in nexts)))
