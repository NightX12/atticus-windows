"""Small file helpers that work on Windows and POSIX: an exclusive lock and an atomic, owner-only write."""
import contextlib, os, sys, tempfile, time

if sys.platform == 'win32':
    import msvcrt

    @contextlib.contextmanager
    def locked(path):
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'a+') as f:
            for _ in range(200):   # msvcrt.LK_LOCK gives up after 10 s; poll gently instead
                try:
                    f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1); break
                except OSError:
                    time.sleep(.05)
            try:
                yield
            finally:
                try:
                    f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
else:
    import fcntl

    @contextlib.contextmanager
    def locked(path):
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'a') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


def write_private(path, text):
    """Replace `path` in one step. POSIX: mode 600. Windows: %APPDATA% is already per-user."""
    folder = os.path.dirname(path)
    os.makedirs(folder, mode=0o700, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=folder, delete=False, encoding='utf-8') as f:
        try:
            f.write(text); f.flush()
            if hasattr(os, 'fchmod'):
                os.fchmod(f.fileno(), 0o600)
            f.close()
            os.replace(f.name, path)
        finally:
            if os.path.exists(f.name):
                os.unlink(f.name)
