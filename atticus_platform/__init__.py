"""Atticus's platform layer. atticus.py imports only this, never ctypes or osascript.

    import atticus_platform as plat
    plat.ctl.find('Notepad')          # flat, winctl-compatible names
    plat.windows.find('Notepad')      # grouped interfaces (base.py)

Backend: win32 -> win32 (the former winctl.py), anything else -> fake (deterministic, for tests and Linux CI). ATTICUS_PLATFORM=fake forces
the fake on Windows too. Named atticus_platform, not platform: that would shadow Python's own `platform` module."""
import os, sys

from . import base, paths

BACKEND = os.environ.get('ATTICUS_PLATFORM') or ('win32' if sys.platform == 'win32' else 'fake')
if BACKEND == 'win32':
    from . import win32 as ctl
else:
    from . import fake as ctl

_g = base.grouped(ctl)
apps, windows, hands, screen, clipboard = _g['apps'], _g['windows'], _g['hands'], _g['screen'], _g['clipboard']
secrets, process, scheduler, browser, audio = _g['secrets'], _g['process'], _g['scheduler'], _g['browser'], _g['audio']
del _g
REAL = BACKEND != 'fake'   # False: nothing here touches the real desktop


def configure(directory):
    """Where the backends keep their small state files (atticus.py's DIR)."""
    paths.APPS_FILE = os.path.join(directory, 'apps.json')
    paths.UI_FILE = os.path.join(directory, 'ui.json')
