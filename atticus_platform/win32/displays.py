"""winctl section: displays (split from winctl.py, code unchanged)."""
import ctypes, json, os, re, subprocess, sys, time
from ctypes import wintypes as W
from ._core import kernel32, user32

# ---------- displays ----------

class RECT(ctypes.Structure):
    _fields_ = [('left', W.LONG), ('top', W.LONG), ('right', W.LONG), ('bottom', W.LONG)]


class MONITORINFOEX(ctypes.Structure):
    _fields_ = [('cbSize', W.DWORD), ('rcMonitor', RECT), ('rcWork', RECT), ('dwFlags', W.DWORD), ('szDevice', W.WCHAR * 32)]


class LUID(ctypes.Structure):
    _fields_ = [('LowPart', W.DWORD), ('HighPart', W.LONG)]


class PATH_INFO(ctypes.Structure):   # DISPLAYCONFIG_PATH_INFO, flattened (72 bytes)
    _fields_ = [('srcAdapter', LUID), ('srcId', ctypes.c_uint32), ('srcMode', ctypes.c_uint32), ('srcFlags', ctypes.c_uint32),
                ('tgtAdapter', LUID), ('tgtId', ctypes.c_uint32), ('tgtMode', ctypes.c_uint32), ('tech', ctypes.c_uint32),
                ('rot', ctypes.c_uint32), ('scale', ctypes.c_uint32), ('rate', ctypes.c_uint32 * 2), ('order', ctypes.c_uint32),
                ('avail', W.BOOL), ('tgtFlags', ctypes.c_uint32), ('flags', ctypes.c_uint32)]


class HEADER(ctypes.Structure):
    _fields_ = [('type', ctypes.c_uint32), ('size', ctypes.c_uint32), ('adapter', LUID), ('id', ctypes.c_uint32)]


class SOURCE_NAME(ctypes.Structure):
    _fields_ = [('h', HEADER), ('gdi', W.WCHAR * 32)]


class TARGET_NAME(ctypes.Structure):
    _fields_ = [('h', HEADER), ('flags', ctypes.c_uint32), ('tech', ctypes.c_uint32), ('mfr', ctypes.c_uint16), ('product', ctypes.c_uint16),
                ('connector', ctypes.c_uint32), ('friendly', W.WCHAR * 64), ('path', W.WCHAR * 128)]


INTERNAL = {6, 11, 13, 0x80000000}   # LVDS, embedded DisplayPort, UDI embedded, "internal": a laptop's own panel


def _panels():
    """GDI device name (\\\\.\\DISPLAY1) -> (friendly monitor name, built in?), from the display configuration."""
    out, n_path, n_mode = {}, ctypes.c_uint32(), ctypes.c_uint32()
    try:
        if user32.GetDisplayConfigBufferSizes(2, ctypes.byref(n_path), ctypes.byref(n_mode)):
            return out
        paths, modes = (PATH_INFO * n_path.value)(), (ctypes.c_byte * (64 * max(1, n_mode.value)))()
        if user32.QueryDisplayConfig(2, ctypes.byref(n_path), paths, ctypes.byref(n_mode), modes, None):
            return out
        for p in paths[:n_path.value]:
            s = SOURCE_NAME(HEADER(1, ctypes.sizeof(SOURCE_NAME), p.srcAdapter, p.srcId))
            t = TARGET_NAME(HEADER(2, ctypes.sizeof(TARGET_NAME), p.tgtAdapter, p.tgtId))
            if user32.DisplayConfigGetDeviceInfo(ctypes.byref(s)) == 0:
                user32.DisplayConfigGetDeviceInfo(ctypes.byref(t))
                out[s.gdi] = (t.friendly or '', p.tech in INTERNAL)
    except (AttributeError, OSError):
        pass
    return out


def monitors():
    """[{name, x, y, w, h, work: (x, y, w, h), built_in, primary}], the primary one first. Physical pixels, top-left origin."""
    found = []
    PROC = ctypes.WINFUNCTYPE(W.BOOL, W.HMONITOR, W.HDC, ctypes.POINTER(RECT), W.LPARAM)

    def each(h, _dc, _r, _l):
        mi = MONITORINFOEX(); mi.cbSize = ctypes.sizeof(MONITORINFOEX)
        if user32.GetMonitorInfoW(h, ctypes.byref(mi)):
            found.append(mi)
        return True
    user32.EnumDisplayMonitors(None, None, PROC(each), 0)
    names, out, seen = _panels(), [], {}
    for mi in found:
        friendly, built_in = names.get(mi.szDevice, ('', False))
        name = friendly or ('Built-in Display' if built_in else 'Display')
        seen[name] = seen.get(name, 0) + 1
        m, w = mi.rcMonitor, mi.rcWork
        out.append({'name': name if seen[name] == 1 else f'{name} {seen[name]}', 'x': m.left, 'y': m.top, 'w': m.right - m.left, 'h': m.bottom - m.top,
                    'work': (w.left, w.top, w.right - w.left, w.bottom - w.top), 'built_in': built_in, 'primary': bool(mi.dwFlags & 1)})
    out.sort(key=lambda d: not d['primary'])
    if out and not any(d['built_in'] for d in out) and len(out) > 1 and laptop():   # no EDID answer: a laptop's panel is usually the primary
        out[0]['built_in'] = True
    return out


def laptop():
    class SPS(ctypes.Structure):
        _fields_ = [('ac', ctypes.c_byte), ('flag', ctypes.c_byte), ('pct', ctypes.c_byte), ('saver', ctypes.c_byte), ('life', W.DWORD), ('full', W.DWORD)]
    s = SPS()
    return bool(kernel32.GetSystemPowerStatus(ctypes.byref(s))) and s.flag != -128 and (s.flag & 128) == 0   # 128 = no battery


