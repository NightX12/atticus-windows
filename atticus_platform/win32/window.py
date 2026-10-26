"""winctl section: window (split from winctl.py, code unchanged)."""
import ctypes, json, os, re, subprocess, sys, time
from ctypes import wintypes as W
from ..pure import key, rect_for  # platform-neutral, shared with the fake backend
from ._core import dwmapi, kernel32, user32, version

# ---------- processes and windows ----------

user32.GetForegroundWindow.restype = W.HWND
user32.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
user32.SetWindowPos.argtypes = [W.HWND, W.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, ctypes.c_int]
_desc = {}


def exe_of(pid):
    h = kernel32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ''
    try:
        buf, n = ctypes.create_unicode_buffer(1024), W.DWORD(1024)
        return buf.value if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else ''
    finally:
        kernel32.CloseHandle(h)


def describe_exe(path):
    """The app's own name from its file version info ("Google Chrome" for chrome.exe), else the file name."""
    if path in _desc:
        return _desc[path]
    name = os.path.splitext(os.path.basename(path))[0]
    try:
        size = version.GetFileVersionInfoSizeW(path, None)
        if size:
            data = ctypes.create_string_buffer(size)
            version.GetFileVersionInfoW(path, 0, size, data)
            ptr, ln = ctypes.c_void_p(), ctypes.c_uint()
            if version.VerQueryValueW(data, r'\VarFileInfo\Translation', ctypes.byref(ptr), ctypes.byref(ln)) and ln.value >= 4:
                lang, cp = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_uint16))[0:2]
                if version.VerQueryValueW(data, f'\\StringFileInfo\\{lang:04x}{cp:04x}\\FileDescription', ctypes.byref(ptr), ctypes.byref(ln)) and ln.value > 1:
                    d = ctypes.wstring_at(ptr, ln.value - 1).strip()
                    if d and len(d) < 40 and not re.search(r'\b(host|launcher|helper|runtime|setup)\b', d, re.I):
                        name = d
    except OSError:
        pass
    _desc[path] = name
    return name


def title(hwnd):
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value


def pid_of(hwnd):
    pid = W.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def real_pid(hwnd):
    """UWP apps (Calculator, Settings…) draw inside ApplicationFrameHost: the app is the child window's process."""
    pid = pid_of(hwnd)
    if not exe_of(pid).lower().endswith('applicationframehost.exe'):
        return pid
    hit = []
    PROC = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    user32.EnumChildWindows(hwnd, PROC(lambda c, _: (hit.append(pid_of(c)) if pid_of(c) != pid else None) or True), 0)
    return hit[0] if hit else pid


def cloaked(hwnd):
    v = ctypes.c_int()
    dwmapi.DwmGetWindowAttribute(W.HWND(hwnd), 14, ctypes.byref(v), ctypes.sizeof(v))
    return bool(v.value)


def windows():
    """Top-level app windows a person can see, front to back: [{hwnd, title, exe, proc, app}]."""
    hs = []
    PROC = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    user32.EnumWindows(PROC(lambda h, _: hs.append(h) or True), 0)
    out = []
    for h in hs:
        if not user32.IsWindowVisible(h) or user32.GetWindow(h, 4) or cloaked(h):   # 4 = GW_OWNER: dialogs and popups belong to another window
            continue
        ex = user32.GetWindowLongW(h, -20)
        t = title(h)
        if not t or ex & 0x80 and not ex & 0x40000:   # WS_EX_TOOLWINDOW without WS_EX_APPWINDOW
            continue
        exe = exe_of(real_pid(h))
        if not exe or os.path.basename(exe).lower() in ('textinputhost.exe', 'atticus.exe', 'searchhost.exe', 'startmenuexperiencehost.exe'):
            continue
        out.append({'hwnd': h, 'title': t, 'exe': exe, 'proc': os.path.splitext(os.path.basename(exe))[0], 'app': describe_exe(exe)})
    return out


def matches(w, name):
    """A window belongs to `name` when it names the process ("chrome", "Code"), the app ("Google Chrome") or ends its title ("… - Notepad")."""
    k = key(name)
    return bool(k) and (k in (key(w['proc']), key(w['app'])) or key(w['title'].rsplit(' - ', 1)[-1]) == k or
                        any(k == key(a.get('exe', '')) for a in apps() if key(a['name']) == key(w['app'])))


def find(name, words=''):
    words = words.lower()
    return [w for w in windows() if matches(w, name) and (not words or words in w['title'].lower())]


def front():
    """(app name, window title, hwnd) of the window in front."""
    h = user32.GetForegroundWindow()
    if not h:
        return '', '', None
    exe = exe_of(real_pid(h))
    return (describe_exe(exe) if exe else ''), title(h), h


def frame(hwnd):
    """The visible frame (no invisible resize borders): (x, y, w, h)."""
    r = RECT()
    if dwmapi.DwmGetWindowAttribute(W.HWND(hwnd), 9, ctypes.byref(r), ctypes.sizeof(r)):   # DWMWA_EXTENDED_FRAME_BOUNDS
        user32.GetWindowRect(W.HWND(hwnd), ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def set_frame(hwnd, x, y, w, h):
    """Move so the visible frame lands exactly there: the window rect is a few pixels bigger on each side."""
    r = RECT()
    user32.GetWindowRect(W.HWND(hwnd), ctypes.byref(r))
    fx, fy, fw, fh = frame(hwnd)
    dl, dt, dr, db = fx - r.left, fy - r.top, r.right - (fx + fw), r.bottom - (fy + fh)
    user32.SetWindowPos(hwnd, None, x - dl, y - dt, w + dl + dr, h + dt + db, 0x0014)   # SWP_NOZORDER | SWP_NOACTIVATE


def bring(hwnd):
    """Bring a window forward. Windows only lets the app with the last input do that, so borrow the front window's input queue."""
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)   # SW_RESTORE
    fg = user32.GetForegroundWindow()
    me, them = kernel32.GetCurrentThreadId(), user32.GetWindowThreadProcessId(fg, None) if fg else 0
    attached = them and them != me and user32.AttachThreadInput(me, them, True)
    user32.keybd_event(0xE8, 0, 0, 0); user32.keybd_event(0xE8, 0, 2, 0)   # an unassigned key: counts as input, does nothing
    user32.BringWindowToTop(hwnd)
    ok = user32.SetForegroundWindow(hwnd)
    if attached:
        user32.AttachThreadInput(me, them, False)
    return bool(ok)


def focus_app(name, words=''):
    ws = find(name, words)
    return bool(ws) and bring(ws[0]['hwnd'])


def close(hwnd):
    user32.PostMessageW(hwnd, 0x0010, 0, 0)   # WM_CLOSE: the app can still ask to save


def place(name, where='full', screen='current', words=''):
    """Move a window: where = left|right|full|center, screen = laptop|monitor|current|a display's name."""
    if where not in ('left', 'right', 'full', 'center'):
        return 'where must be left, right, full or center'
    words = re.sub(r'\.[a-z0-9]{2,4}$', '', words, flags=re.I)   # "notes.txt" also finds "notes - Notepad"
    for tries in range(8):   # a window just opened (--show right before) can take a moment to appear
        ws = find(name, words)
        if ws:
            break
        time.sleep(0.25)
    else:
        return f'no window found for "{name}" {words}'.strip()
    hwnd = ws[0]['hwnd']
    if user32.IsZoomed(hwnd) or user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)   # maximized windows can't be moved: restore first
    fx, fy, fw, fh = frame(hwnd)
    mons = monitors()
    pick = {'laptop': lambda m: m['built_in'], 'monitor': lambda m: not m['built_in']}.get(
        screen, (lambda m: m['name'].lower() == screen.lower()) if screen != 'current' else
        (lambda m: m['x'] <= fx + fw // 2 < m['x'] + m['w'] and m['y'] <= fy + fh // 2 < m['y'] + m['h']))
    m = next((m for m in mons if pick(m)), mons[0])
    x, y, w, h = rect_for(where, m['work'], (fw, fh))
    set_frame(hwnd, x, y, w, h)
    if where == 'full':
        user32.ShowWindow(hwnd, 3)   # SW_MAXIMIZE, on the display it now sits on
    return f"{ws[0]['app']} window -> {where} of {m['name']}"



# siblings last, so circular references resolve (all defs above exist by then)
from .apps import apps  # noqa: E402
from .displays import RECT, monitors  # noqa: E402
