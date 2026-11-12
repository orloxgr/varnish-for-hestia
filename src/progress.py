"""Opt-in administrator console progress; never a work deadline or panel output."""
from contextlib import contextmanager
import datetime
import sys
import threading
import time

_stream = None
_message = ''
_since = 0
_lock = threading.RLock()


def _emit(message):
    if _stream is None:
        return
    stamp = datetime.datetime.now().astimezone().strftime('%H:%M:%S')
    try:
        _stream.write('[' + stamp + '] ' + message + '\n')
        _stream.flush()
    except (OSError, ValueError):
        # A closed console must not fail or cancel completed service work.
        pass


def stage(message):
    global _message, _since
    with _lock:
        if _stream is None:
            return
        _message, _since = message, time.monotonic()
        _emit(message)


@contextmanager
def reporting(stream=None, interval=10):
    """Emit current-stage heartbeats while the native operation is still running."""
    global _stream, _message, _since
    with _lock:
        previous = (_stream, _message, _since)
        _stream = sys.stderr if stream is None else stream
        _message, _since = 'Starting installer', time.monotonic()
    stop = threading.Event()
    def heartbeat():
        while not stop.wait(interval):
            with _lock:
                _emit('Still working (' + str(int(time.monotonic() - _since)) + 's): ' + _message)
    worker = threading.Thread(target=heartbeat, daemon=True)
    worker.start()
    try:
        yield
    finally:
        stop.set()
        worker.join()
        with _lock:
            _stream, _message, _since = previous
