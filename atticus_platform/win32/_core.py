"""Windows side of Atticus's hands: displays, windows, apps, clipboard, typing, screenshots, files, toasts.
atticus.py calls these where the Mac version ran osascript, mdfind, screencapture or pbpaste. Pure ctypes plus
mss (screenshots), Pillow (resize) and psutil (process trees); every call returns quickly or gives up quietly."""
import ctypes, json, os, re, subprocess, sys, time
from ctypes import wintypes as W

if sys.platform != 'win32':   # tests import atticus on any OS; the functions below only run on Windows
    raise ImportError('winctl is Windows only')

user32, kernel32, dwmapi, version = ctypes.WinDLL('user32', use_last_error=True), ctypes.WinDLL('kernel32', use_last_error=True), ctypes.WinDLL('dwmapi'), ctypes.WinDLL('version')
try:   # physical pixels everywhere, the same numbers SetWindowPos, mss and the overlay use
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except (AttributeError, OSError):
    pass

HOME = os.path.expanduser('~')
NO_WINDOW = 0x08000000   # CREATE_NO_WINDOW: helpers never flash a console


def ps(script, timeout=20):
    """One PowerShell command -> stdout ('' on failure)."""
    try:
        return subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', script],
                              capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout, creationflags=NO_WINDOW).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ''


def bash():
    """Git for Windows' bash: Claude Code's Bash tool runs there, so learned shortcuts replay there too."""
    for d in (os.environ.get('ProgramFiles', r'C:\Program Files'), os.environ.get('LOCALAPPDATA', '') + r'\Programs'):
        p = os.path.join(d, 'Git', 'bin', 'bash.exe')
        if os.path.exists(p):
            return p
    return 'bash'
