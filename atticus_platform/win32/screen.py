"""winctl section: screen (split from winctl.py, code unchanged)."""
import ctypes, json, os, re, subprocess, sys, time
from ctypes import wintypes as W

# ---------- screen ----------

def capture(mon, path, width=1280):
    """One display as a JPEG `width` px wide. The Atticus box is never in it (the app excludes itself from capture)."""
    import mss
    from PIL import Image
    with mss.mss() as s:
        g = s.grab({'left': mon['x'], 'top': mon['y'], 'width': mon['w'], 'height': mon['h']})
    img = Image.frombytes('RGB', g.size, g.bgra, 'raw', 'BGRX')
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    img.save(path, 'JPEG', quality=70)
    return path
