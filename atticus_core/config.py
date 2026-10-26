"""Where the core keeps its files and how it reads settings. Defaults match atticus.py (%APPDATA%/Atticus)."""
import json, os

HOME = os.path.expanduser('~')
DIR = os.environ.get('ATTICUS_DIR') or os.path.join(os.environ.get('APPDATA') or os.path.join(HOME, '.config'), 'Atticus')
_pref = None
heard = lambda: []   # the user's own recent words (this ask + recent questions); atticus.py sets it, see profile._request_contains


def prefs_file():
    return os.path.join(DIR, 'settings.json')


def pref(key, default):
    if _pref:
        return _pref(key, default)
    try:
        with open(prefs_file(), encoding='utf-8') as f:
            return json.load(f).get(key, default)
    except (OSError, ValueError, AttributeError):
        return default


def setup(directory=None, pref_fn=None, heard_fn=None):
    global DIR, _pref, heard
    if directory:
        DIR = directory
    if pref_fn:
        _pref = pref_fn
    if heard_fn:
        heard = heard_fn


def path(name):
    return os.path.join(DIR, name)
