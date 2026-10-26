"""Windows backend: the former winctl.py, split by topic. Function bodies are unchanged; only the module-wide files
(APPS_FILE, UI_FILE) moved to atticus_platform.paths, and key/rect_for/ui_item to atticus_platform.pure (shared with fake).
Importing this package anywhere but Windows raises ImportError (see _core)."""
from . import _core, displays, window, apps, clipboard, screen, files, dialogs, process, helpers, uia, browser, joplin, secrets

_MODULES = (_core, displays, window, apps, clipboard, screen, files, dialogs, process, helpers, uia, browser, joplin, secrets)
# one flat namespace with every name winctl had, so callers keep `ctl.find(...)`, `ctl.focus_app(...)`.
# Sibling imports are the same objects, so setdefault in module order is enough.
for _m in _MODULES:
    for _n, _v in vars(_m).items():
        if not _n.startswith('__') and not isinstance(_v, type(_core)):
            globals().setdefault(_n, _v)
for _n, _v in list(globals().items()):   # a function named like its module (apps.apps) wins over the submodule
    if isinstance(_v, type(_core)) and _v in _MODULES:
        _f = next((vars(_m)[_n] for _m in _MODULES if not isinstance(vars(_m).get(_n, _core), type(_core))), None)
        if _f is not None:
            globals()[_n] = _f
del _m, _n, _v, _f
NAME = 'win32'
