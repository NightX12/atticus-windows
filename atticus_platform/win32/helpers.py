"""winctl section: helpers (split from winctl.py, code unchanged)."""
import ctypes, json, os, re, subprocess, sys, time
from ctypes import wintypes as W
from ._core import HOME, ps

# ---------- small helpers the AI calls ----------

def trash(path):
    """To the Recycle Bin (undoable), never a permanent delete."""
    p = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(p):
        return f'no such file: {path}'
    kind = 'DeleteDirectory' if os.path.isdir(p) else 'DeleteFile'
    q = p.replace("'", "''")
    ps(f"Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.FileIO.FileSystem]::{kind}('{q}', 'OnlyErrorDialogs', 'SendToRecycleBin')")
    return f'moved to the Recycle Bin: {p}' if not os.path.exists(p) else f'could not move {p} to the Recycle Bin'


NOTES = os.path.join(HOME, 'Documents', 'Atticus Notes.md')


def note(text):
    """Windows' to-do and notes apps can't be scripted: notes go in one Markdown file the user owns."""
    os.makedirs(os.path.dirname(NOTES), exist_ok=True)
    with open(NOTES, 'a', encoding='utf-8') as f:
        f.write(f"\n## {time.strftime('%a %b %d %Y %I:%M %p')}\n{text.strip()}\n")
    return f'noted in {NOTES}'


