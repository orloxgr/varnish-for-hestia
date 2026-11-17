"""Ship recognition and reviewed executable choices together with the addon."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'shared'))

BUNDLED = ROOT / 'shared/cookie-recognition/recognition.json'


def directory():
    import service
    return service.STORE / 'cookie-recognition'


def status():
    from cookie_defaults import bundle
    data=database()
    defaults, assessments=bundle()
    return dict(automatic=False,bundled=True,result='bundled',
                records=len(data['records']),rules=len(defaults['rules']),
                revision=data.get('revision',''),version=assessments['version'],
                message='Cookie recognition and reviewed cache rules are bundled together. Update the plugin to receive a new reviewed version.')


def database():
    return json.loads(BUNDLED.read_text(encoding='utf-8'))


def configure(automatic):
    # Compatibility for a previously opened panel; no obsolete daily download.
    return status()


def update(force=False):
    # Old manual commands report the new lifecycle instead of claiming a fetch.
    return status()
