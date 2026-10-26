"""winctl section: clipboard (split from winctl.py, code unchanged)."""
import ctypes, json, os, re, subprocess, sys, time
from ctypes import wintypes as W
from ._core import kernel32, user32

# ---------- clipboard and typing ----------

kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
user32.GetClipboardData.restype = ctypes.c_void_p
user32.SetClipboardData.restype = ctypes.c_void_p
user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]


def _open_clip():
    for _ in range(20):   # another app may hold it for a moment
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.03)
    return False


def get_clip():
    if not _open_clip():
        return ''
    try:
        h = user32.GetClipboardData(13)   # CF_UNICODETEXT
        p = h and kernel32.GlobalLock(h)
        if not p:
            return ''
        try:
            return ctypes.wstring_at(p)
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def set_clip(text):
    data = (text or '').encode('utf-16-le') + b'\0\0'
    if not _open_clip():
        return False
    try:
        user32.EmptyClipboard()
        h = kernel32.GlobalAlloc(0x0002, len(data))   # GMEM_MOVEABLE
        p = kernel32.GlobalLock(h)
        ctypes.memmove(p, data, len(data))
        kernel32.GlobalUnlock(h)
        return bool(user32.SetClipboardData(13, h))
    finally:
        user32.CloseClipboard()


def keys(*vks):
    """Press keys together, then let them go in reverse (e.g. keys(0x11, 0x56) = Ctrl+V)."""
    for v in vks:
        user32.keybd_event(v, 0, 0, 0)
    for v in reversed(vks):
        user32.keybd_event(v, 0, 2, 0)


def paste_into(app, text):
    """Paste text into the focused box of `app` (its front window), then put the user's clipboard back."""
    old = get_clip()
    if not set_clip(text):
        return 'could not use the clipboard'
    fg_app = front()[0]
    if app and key(fg_app) != key(app):
        focus_app(app)
        time.sleep(0.25)
    keys(0x11, 0x56)
    time.sleep(0.4)
    set_clip(old)
    return f'typed into {front()[0] or app}'


MEDIA = {'playpause': 0xB3, 'next': 0xB0, 'previous': 0xB1, 'prev': 0xB1, 'stop': 0xB2, 'mute': 0xAD, 'volumeup': 0xAF, 'volumedown': 0xAE}


def media(what):
    vk = MEDIA.get(re.sub(r'[^a-z]', '', what.lower()))
    if not vk:
        return 'media key must be one of: ' + ', '.join(MEDIA)
    keys(vk)
    return f'pressed {what}'



# siblings last, so circular references resolve (all defs above exist by then)
from .window import focus_app, front, key  # noqa: E402
