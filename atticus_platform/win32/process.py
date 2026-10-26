"""winctl section: process (split from winctl.py, code unchanged)."""
import ctypes, json, os, re, subprocess, sys, time
from ctypes import wintypes as W
from ._core import NO_WINDOW

# ---------- process trees ----------

def kill_tree(pid, me_too=True):
    """Stop a process and everything it started (Claude Code, its tools, the gate hook)."""
    try:
        import psutil
    except ImportError:
        if me_too:   # no threads here: this also runs while Python shuts down
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
        return
    try:
        p = psutil.Process(pid)
        for k in p.children(recursive=True):
            try:
                k.kill()
            except psutil.Error:
                pass
        if me_too:
            p.kill()
    except psutil.Error:   # already gone
        pass


