"""The platform interfaces atticus.py talks to. Backends: win32 (real), fake (tests, Linux CI), later mac.
Each backend is also a flat module (`ctl`) with winctl's function names, which is what atticus.py calls today;
the grouped interfaces below are the target shape for new code and for upstream merges (see docs/MERGE.md)."""
from typing import Protocol, runtime_checkable


@runtime_checkable
class Apps(Protocol):
    def installed(self, refresh: bool = False) -> list: ...
    def launch(self, name: str) -> bool: ...
    def opener(self, target: str) -> str: ...
    def focus(self, name: str, words: str = '') -> bool: ...


@runtime_checkable
class Windows(Protocol):
    def list(self) -> list: ...
    def find(self, name: str, words: str = '') -> list: ...
    def front(self) -> tuple: ...
    def frame(self, hwnd) -> tuple: ...
    def place(self, name: str, where: str = 'full', screen: str = 'current', words: str = '') -> str: ...
    def rect_for(self, where: str, area: tuple, size: tuple) -> tuple: ...
    def monitors(self) -> list: ...
    def bring(self, hwnd) -> bool: ...
    def close(self, hwnd) -> None: ...


@runtime_checkable
class Hands(Protocol):
    def see(self, app: str, words: str = '', most: int = 80) -> str: ...
    def click(self, *ids: str) -> str: ...
    def set_text(self, i: str, text: str) -> str: ...
    def hotkey(self, app: str, combo: str) -> str: ...
    def paste_into(self, app: str, text: str) -> str: ...
    def media(self, what: str) -> str: ...


@runtime_checkable
class Screen(Protocol):
    def capture(self, mon: dict, path: str, width: int = 1280): ...


@runtime_checkable
class Clipboard(Protocol):
    def get(self) -> str: ...
    def set(self, text: str) -> bool: ...


@runtime_checkable
class Secrets(Protocol):
    def get(self, name: str) -> str: ...
    def set(self, name: str, value: str) -> bool: ...


@runtime_checkable
class Process(Protocol):
    def shell(self) -> str: ...
    def kill_tree(self, pid: int, me_too: bool = True) -> None: ...


@runtime_checkable
class Scheduler(Protocol):
    def install(self, routine: dict) -> str: ...
    def remove(self, routine_id: str) -> bool: ...


@runtime_checkable
class Browser(Protocol):
    def url(self, hwnd) -> str: ...


@runtime_checkable
class Audio(Protocol):
    def loopback_start(self, path: str) -> bool: ...
    def loopback_stop(self) -> str: ...


INTERFACES = {'apps': Apps, 'windows': Windows, 'hands': Hands, 'screen': Screen, 'clipboard': Clipboard,
              'secrets': Secrets, 'process': Process, 'scheduler': Scheduler, 'browser': Browser, 'audio': Audio}


class _Grouped:
    """Grouped interfaces built on a flat backend module. Lookups go through the module each call, so a test
    that patches `ctl.find` also changes `windows.find`."""
    def __init__(self, ctl):
        self._ctl = ctl


class _Apps(_Grouped):
    def installed(self, refresh=False): return self._ctl.apps(refresh)
    def launch(self, name): return self._ctl.launch(name)
    def opener(self, target): return self._ctl.opener(target)
    def focus(self, name, words=''): return self._ctl.focus_app(name, words)


class _Windows(_Grouped):
    def list(self): return self._ctl.windows()
    def find(self, name, words=''): return self._ctl.find(name, words)
    def front(self): return self._ctl.front()
    def frame(self, hwnd): return self._ctl.frame(hwnd)
    def place(self, name, where='full', screen='current', words=''): return self._ctl.place(name, where, screen, words)
    def rect_for(self, where, area, size): return self._ctl.rect_for(where, area, size)
    def monitors(self): return self._ctl.monitors()
    def bring(self, hwnd): return self._ctl.bring(hwnd)
    def close(self, hwnd): return self._ctl.close(hwnd)


class _Hands(_Grouped):
    def see(self, app, words='', most=80): return self._ctl.ui_see(app, words, most)
    def click(self, *ids): return self._ctl.ui_click(*ids)
    def set_text(self, i, text): return self._ctl.ui_set(i, text)
    def hotkey(self, app, combo): return self._ctl.hotkey(app, combo)
    def paste_into(self, app, text): return self._ctl.paste_into(app, text)
    def media(self, what): return self._ctl.media(what)


class _Screen(_Grouped):
    def capture(self, mon, path, width=1280): return self._ctl.capture(mon, path, width)


class _Clipboard(_Grouped):
    def get(self): return self._ctl.get_clip()
    def set(self, text): return self._ctl.set_clip(text)


class _Secrets(_Grouped):
    def get(self, name): return self._ctl.secret_get(name)
    def set(self, name, value): return self._ctl.secret_set(name, value)


class _Process(_Grouped):
    def shell(self): return self._ctl.bash()
    def kill_tree(self, pid, me_too=True): return self._ctl.kill_tree(pid, me_too)


class _NotYet(_Grouped):
    """Interfaces with no backend code yet (roadmap AP4–AP9): say so instead of failing somewhere deeper."""
    def _no(self, what):
        raise NotImplementedError(f'{what} is not implemented on {getattr(self._ctl, "NAME", "this platform")} yet')


class _Scheduler(_NotYet):
    def install(self, routine): self._no('Scheduler.install')
    def remove(self, routine_id): self._no('Scheduler.remove')


class _Browser(_Grouped):
    def url(self, hwnd): return self._ctl.browser_url(hwnd)


class _Audio(_NotYet):
    def loopback_start(self, path): self._no('Audio.loopback_start')
    def loopback_stop(self): self._no('Audio.loopback_stop')


def grouped(ctl):
    """{'apps': Apps, 'windows': Windows, ...} for a flat backend module."""
    return {'apps': _Apps(ctl), 'windows': _Windows(ctl), 'hands': _Hands(ctl), 'screen': _Screen(ctl), 'clipboard': _Clipboard(ctl),
            'secrets': _Secrets(ctl), 'process': _Process(ctl), 'scheduler': _Scheduler(ctl), 'browser': _Browser(ctl), 'audio': _Audio(ctl)}
