"""Fake backend: winctl's names, no desktop. Deterministic state in plain dicts/lists so tests can set it up and
inspect what Atticus asked for (CALLS). Used on Linux/macOS CI and whenever ATTICUS_PLATFORM=fake."""
import os, signal, subprocess, sys

from . import paths
from .pure import key, rect_for, ui_item  # the same code the Windows backend runs

NAME = 'fake'
HOME = os.path.expanduser('~')
BROWSERS = ('Google Chrome', 'Microsoft Edge', 'Brave Browser', 'Firefox', 'Opera', 'Vivaldi', 'Arc')
MEDIA = {'playpause': 0xB3, 'next': 0xB0, 'previous': 0xB1, 'prev': 0xB1, 'stop': 0xB2, 'mute': 0xAD, 'volumeup': 0xAF, 'volumedown': 0xAE}
NOTES = os.path.join(HOME, 'Documents', 'Atticus Notes.md')

# ---- state a test may set ----
MONITORS = [{'name': 'Built-in', 'x': 0, 'y': 0, 'w': 1920, 'h': 1080, 'work': (0, 0, 1920, 1040), 'built_in': True}]
WINDOWS = []      # [{'hwnd', 'title', 'exe', 'proc', 'app'}], front window first
APPS = []         # [{'name', 'exe'?, 'id'?}]
CLIP = ['']
SECRETS = {}
FILES = []        # paths find_files may return
ANSWERS = {'text': None, 'yes': False, 'choose': None}
CALLS = []        # (function name, args) for every call that would change something


def reset():
    WINDOWS.clear(); APPS.clear(); SECRETS.clear(); FILES.clear(); CALLS.clear()
    CLIP[0] = ''
    ANSWERS.update(text=None, yes=False, choose=None)


def _did(name, *a):
    CALLS.append((name, a))


def ps(script, timeout=20):
    _did('ps', script)
    return ''


def bash():
    return 'bash'


# ---- displays and windows ----
def monitors():
    return [dict(m) for m in MONITORS]


def laptop():
    return any(m['built_in'] for m in MONITORS)


def windows():
    return [dict(w) for w in WINDOWS]


def apps(refresh=False):
    return [dict(a) for a in APPS]


def matches(w, name):
    k = key(name)
    return bool(k) and (k in (key(w.get('proc', '')), key(w.get('app', ''))) or key(w.get('title', '').rsplit(' - ', 1)[-1]) == k)


def find(name, words=''):
    words = words.lower()
    return [w for w in windows() if matches(w, name) and (not words or words in w['title'].lower())]


def front():
    return (WINDOWS[0]['app'], WINDOWS[0]['title'], WINDOWS[0]['hwnd']) if WINDOWS else ('', '', None)


def frame(hwnd):
    return next((tuple(w.get('frame', (0, 0, 800, 600))) for w in WINDOWS if w['hwnd'] == hwnd), (0, 0, 0, 0))


def bring(hwnd):
    _did('bring', hwnd)
    i = next((n for n, w in enumerate(WINDOWS) if w['hwnd'] == hwnd), None)
    if i is None:
        return False
    WINDOWS.insert(0, WINDOWS.pop(i))
    return True


def focus_app(name, words=''):
    ws = find(name, words)
    return bool(ws) and bring(ws[0]['hwnd'])


def close(hwnd):
    _did('close', hwnd)
    WINDOWS[:] = [w for w in WINDOWS if w['hwnd'] != hwnd]


def place(name, where='full', screen='current', words=''):
    if where not in ('left', 'right', 'full', 'center'):
        return 'where must be left, right, full or center'
    ws = find(name, words)
    if not ws:
        return f'no window found for {name}'
    _did('place', name, where, screen)
    return f'placed {ws[0]["app"]} {where}'


def launch(app):
    _did('launch', app)
    return any(key(a['name']) == key(app) for a in APPS)


def opener(target):
    return ''


# ---- clipboard, keys, screen ----
def get_clip():
    return CLIP[0]


def set_clip(text):
    CLIP[0] = text
    return True


def keys(*vks):
    _did('keys', *vks)


def paste_into(app, text):
    _did('paste_into', app, text)
    return f'typed into {app}' if find(app) or not app else f'no window found for {app}'


def media(what):
    if what not in MEDIA:
        return 'media key must be one of: ' + ', '.join(MEDIA)
    _did('media', what)
    return f'pressed {what}'


def capture(mon, path, width=1280):
    _did('capture', mon.get('name'), path)
    return None


def find_files(words, content=False, where='', most=20):
    ws = words.lower().split()
    return [f for f in FILES if all(w in f.lower() for w in ws)][:most]


# ---- talking to the person ----
def to_app(line):
    _did('to_app', line)


def notify(text, heading='Atticus'):
    _did('notify', heading, text)


def ask_text(prompt='What should I do?'):
    return ANSWERS['text']


def ask_yes(heading, text):
    return ANSWERS['yes']


def choose(question, options):
    return ANSWERS['choose']


# ---- processes: a real implementation, so cancellation tests mean something on Linux too ----
def _children(pid):
    try:
        import psutil
        return [k.pid for k in psutil.Process(pid).children(recursive=True)]
    except ImportError:
        pass
    except Exception:
        return []
    kids, todo = [], [pid]
    parents = {}
    for d in os.listdir('/proc') if os.path.isdir('/proc') else []:
        if d.isdigit():
            try:
                stat = open(f'/proc/{d}/stat').read()
                parents.setdefault(int(stat[stat.rindex(')') + 2:].split()[1]), []).append(int(d))
            except (OSError, ValueError, IndexError):
                pass
    while todo:
        for k in parents.get(todo.pop(), []):
            kids.append(k); todo.append(k)
    return kids


def kill_tree(pid, me_too=True):
    for k in _children(pid) + ([pid] if me_too else []):
        try:
            os.kill(k, signal.SIGKILL)
        except OSError:
            pass


def trash(path):
    p = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(p):
        return f'no such file: {path}'
    _did('trash', p)
    return f'moved to the Recycle Bin: {p}'


def note(text):
    _did('note', text)
    return f'noted in {NOTES}'


# ---- UI Automation ----
def ui_see(app, words='', most=80):
    return 'nothing clickable found'


def ui_click(*ids):
    _did('ui_click', *ids)
    return 'clicked ' + ', '.join(ids)


def ui_set(i, text):
    _did('ui_set', i, text)
    return f'set {i}'


def hotkey(app, combo):
    _did('hotkey', app, combo)
    return f'pressed {combo}'


def browser_url(hwnd):
    return next((w.get('url', '') for w in WINDOWS if w['hwnd'] == hwnd), '')


# ---- Joplin: no Joplin here ----
def _joplin_settings():
    return {}


def joplin(method, path, body=None, **query):
    raise OSError('Joplin is not available in the fake backend')


def joplin_cmd(args):
    return 'Joplin: not available on this platform'


# ---- secrets ----
def secret_get(name):
    return SECRETS.get(name, '')


def secret_set(name, value):
    if not value:
        return SECRETS.pop(name, None) is not None
    SECRETS[name] = value
    return True
