"""winctl section: apps (split from winctl.py, code unchanged)."""
import ctypes, json, os, re, subprocess, sys, time
from ctypes import wintypes as W
from ._core import NO_WINDOW, ps
from .. import paths

# ---------- apps ----------


_apps = None
INDEX = r'''
$sh = New-Object -ComObject WScript.Shell
$lnk = @{}
foreach ($d in @("$env:ProgramData\Microsoft\Windows\Start Menu\Programs", "$env:APPDATA\Microsoft\Windows\Start Menu\Programs")) {
  Get-ChildItem $d -Recurse -Filter *.lnk -ErrorAction SilentlyContinue | ForEach-Object {
    try { $t = $sh.CreateShortcut($_.FullName).TargetPath } catch { $t = '' }
    if ($t -like '*.exe') { $lnk[$_.BaseName] = @{ lnk = $_.FullName; exe = $t } } } }
@(Get-StartApps | ForEach-Object { $l = $lnk[$_.Name]
  [pscustomobject]@{ name = $_.Name; id = $_.AppID; lnk = if ($l) { $l.lnk } else { '' }; exe = if ($l) { [IO.Path]::GetFileNameWithoutExtension($l.exe) } elseif ($_.AppID -like '*.exe') { [IO.Path]::GetFileNameWithoutExtension($_.AppID) } else { '' } } }) | ConvertTo-Json -Compress
'''


def apps(refresh=False):
    """The Start menu's apps: [{name, id (AppUserModelID), lnk, exe}]. Built with PowerShell (~1 s), cached a day."""
    global _apps
    if _apps is not None and not refresh:
        return _apps
    if not refresh and paths.APPS_FILE and os.path.exists(paths.APPS_FILE) and time.time() - os.path.getmtime(paths.APPS_FILE) < 86400:
        try:
            _apps = json.load(open(paths.APPS_FILE, encoding='utf-8'))
            return _apps
        except ValueError:
            pass
    try:
        got = json.loads(ps(INDEX, 40) or '[]')
        _apps = [a for a in (got if isinstance(got, list) else [got]) if a.get('name') and not re.search(r'\b(uninstall|readme|help|documentation|website)\b', a['name'], re.I)]
    except ValueError:
        _apps = []
    if paths.APPS_FILE and _apps:
        os.makedirs(os.path.dirname(paths.APPS_FILE), exist_ok=True)
        json.dump(_apps, open(paths.APPS_FILE, 'w', encoding='utf-8'))
    return _apps


def launch(app):
    """Open a Start-menu app by its exact name. False if there is none."""
    a = next((a for a in apps() if a['name'] == app), None)
    if not a:
        return False
    if a.get('lnk') and os.path.exists(a['lnk']):
        os.startfile(a['lnk'])
    else:
        subprocess.Popen(['explorer.exe', 'shell:AppsFolder\\' + a['id']], creationflags=NO_WINDOW)
    return True


def opener(target):
    """The app name that opens a URL or file, for "open it on the other screen"."""
    if re.match(r'^[a-z]+://', target):
        ext, kind = re.match(r'^([a-z]+)', target)[1], 'URL'
    else:
        ext, kind = os.path.splitext(target)[1] or '.txt', 'FILE'
    buf, n = ctypes.create_unicode_buffer(1024), W.DWORD(1024)
    # AssocQueryStringW(ASSOCF_NONE, ASSOCSTR_EXECUTABLE=2, ext or protocol, "open", out, &n)
    if ctypes.WinDLL('shlwapi').AssocQueryStringW(0, 2, ext if kind == 'FILE' else ext, 'open', buf, ctypes.byref(n)) == 0 and buf.value:
        return describe_exe(buf.value) if os.path.exists(buf.value) else ''
    return ''



# siblings last, so circular references resolve (all defs above exist by then)
from .window import describe_exe  # noqa: E402
