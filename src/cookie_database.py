"""Load bundled recognition data for the cookie policy editor."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLED = ROOT / 'shared/cookie-recognition/recognition.json'


def database():
    return json.loads(BUNDLED.read_text(encoding='utf-8'))
