"""winctl section: browser (split from winctl.py, code unchanged)."""
import ctypes, json, os, re, subprocess, sys, time
from ctypes import wintypes as W

BROWSERS = ('Google Chrome', 'Microsoft Edge', 'Brave Browser', 'Firefox', 'Opera', 'Vivaldi', 'Arc')


def browser_url(hwnd):
    """The address in a browser window's address bar ('' if it can't be read quickly)."""
    import uiautomation as auto
    try:
        for c in _walk(auto.ControlFromHandle(hwnd), most=400, secs=0.6):
            if c.ControlTypeName == 'EditControl' and re.search(r'address|search with|enter address', c.Name or '', re.I):
                v = c.GetValuePattern().Value
                return v   # as Chrome shows it: an http site has no scheme in the bar
    except Exception:
        pass
    return ''



# siblings last, so circular references resolve (all defs above exist by then)
from .uia import _walk  # noqa: E402
