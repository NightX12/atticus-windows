"""Opt-in, privacy-safe telemetry, ported from atticus-mac. Differences on purpose:
- OFF unless the user turned Settings → stats on (Mac: on by default) AND the build has ATTICUS_POSTHOG_KEY.
- sent with urllib on a daemon thread instead of /bin/sh + curl."""
import base64, json, os, re, sys, threading, urllib.request

from . import config

APP_VERSION = '0.1-windows'
ME = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ''


def posthog_key():
    return os.environ.get('ATTICUS_POSTHOG_KEY', '')


def telemetry_enabled():
    return bool(posthog_key() and config.pref('stats', False) is True and not os.environ.get('ATTICUS_DIR'))


def install_id():
    idf = config.path('id')
    if not os.path.exists(idf):
        os.makedirs(config.DIR, mode=0o700, exist_ok=True)
        with open(idf, 'w') as f: f.write(base64.b32encode(os.urandom(10)).decode())
    with open(idf) as f: return f.read()


def _send(body):
    try:
        req = urllib.request.Request('https://us.i.posthog.com/i/v0/e/', body, {'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=10).close()
    except Exception:   # telemetry never breaks an ask
        pass


def posthog(event, props=None):
    if not telemetry_enabled():
        return None
    body = json.dumps({'api_key': posthog_key(), 'event': event, 'distinct_id': install_id(),
                       'properties': {'$process_person_profile': False, 'version': APP_VERSION, 'os': 'windows', **(props or {})}}).encode()
    t = threading.Thread(target=_send, args=(body,), daemon=True); t.start()
    return t


def clean(text):
    """No emails, numbers, file paths, link queries, long tokens or typed text."""
    t = str(text).replace(os.path.expanduser('~'), '~')
    t = re.sub(r'[\w.+-]+@[\w-]+\.[\w.]+', '<email>', t)
    t = re.sub(r'(https?://[^\s"\'?#]+)[?#][^\s"\']*', r'\1', t)
    t = re.sub(r'~[\\/][^\s"\']+', '~/<path>', t)
    t = re.sub(r'\b[A-Za-z]:\\[^\s"\']*', '<path>', t)   # C:\Users\...
    t = re.sub(r'(?<![:/])/(?:[^/\s"\']+/)+[^/\s"\']*', '<path>', t)
    t = re.sub(r'\b[A-Za-z0-9_-]{24,}\b', '<secret>', t)
    return re.sub(r'\d[\d\s().-]{4,}\d', '<number>', t)[:300]


def report_error(kind, **props):
    """Callers pass enums, indexes and code locations, never user text."""
    if telemetry_enabled():
        return posthog('error', {'kind': kind, **props})


def exception_error(exc_type, tb, value=None, *, kind='exception', **props):
    ours = None
    while tb and tb.tb_next:
        if tb.tb_frame.f_code.co_filename == ME: ours = tb
        tb = tb.tb_next
    if tb and tb.tb_frame.f_code.co_filename == ME: ours = tb
    frame = tb.tb_frame if tb else None
    errno = value.errno if isinstance(value, OSError) else None
    return report_error(kind, **props, exception=getattr(exc_type, '__name__', 'Exception'),
                        file=os.path.basename(frame.f_code.co_filename) if frame else '',
                        line=tb.tb_lineno if tb else 0, function=frame.f_code.co_name if frame else '',
                        at_line=ours.tb_lineno if ours else 0, at_function=ours.tb_frame.f_code.co_name if ours else '',
                        **({'errno': errno} if isinstance(errno, int) else {}))


def install_exception_hooks():
    previous_sys, previous_thread = sys.excepthook, getattr(threading, 'excepthook', None)
    def system_hook(exc_type, value, tb):
        exception_error(exc_type, tb, value)
        previous_sys(exc_type, value, tb)
    def thread_hook(args):
        if not threading.main_thread().is_alive() or issubclass(args.exc_type, SystemExit): return
        exception_error(args.exc_type, args.exc_traceback, args.exc_value)
        if previous_thread: previous_thread(args)
    sys.excepthook = system_hook
    if previous_thread: threading.excepthook = thread_hook
    return previous_sys, previous_thread
