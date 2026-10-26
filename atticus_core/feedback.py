"""Settings → Report a bug: a prefilled GitHub issue the user reviews and sends themselves. Nothing is sent from here."""
import os, platform, urllib.parse

from . import config
from .models import routing_mode
from .telemetry import APP_VERSION

ISSUES = os.environ.get('ATTICUS_ISSUES', 'https://github.com/NightX12/atticus-windows/issues/new')


def feedback(data, last_ask=None):
    model = config.pref('model', 'haiku')
    model = model if model in ('haiku', 'sonnet', 'opus') else 'custom'
    text = str(data.get('text', '')).strip()[:4000]
    body = (f'## What happened\n\n{text}\n\n' if text else '## What happened\n\n\n## What you expected\n\n\n') + ('## Atticus\n'
            f'Version: {APP_VERSION}\nVersion / commit: {str(data.get("version", "unknown"))[:80]}\n'
            f'Windows: {platform.platform()}\nMachine: {platform.machine()}\n'
            f'Model: {model}\nRouting: {routing_mode()}\nSafe mode: {"on" if config.pref("safe", True) else "off"}\n')
    if data.get('include') is True:
        body += '\n## My last ask\n' + (str(last_ask) if last_ask else '(No previous ask)') + '\n'
    return {'body': body, 'include': data.get('include') is True,
            'url': ISSUES + '?' + urllib.parse.urlencode({'title': 'Atticus feedback', 'body': body})}
