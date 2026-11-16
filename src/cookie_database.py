"""Hestia adapter for the shared recognition updater, separate from VCL state."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'shared'))
import cookie_recognition

BUNDLED = ROOT / 'shared/cookie-recognition/recognition.json'


def directory():
    import service
    return service.STORE / 'cookie-recognition'


def status():
    return cookie_recognition.status(directory(), BUNDLED)


def configure(automatic):
    return cookie_recognition.configure(directory(), BUNDLED, automatic)


def update(force=False):
    return cookie_recognition.update(directory(), BUNDLED, force=force)
