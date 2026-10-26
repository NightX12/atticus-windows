"""Model choice and routing (Settings → Model / Routing / Custom server), ported unchanged from atticus-mac."""
import json, os, urllib.error, urllib.parse, urllib.request

from .config import pref


def routing_mode():
    mode = pref('routing', '')
    if mode in ('cheapest', 'balanced', 'capable'): return mode
    if pref('model', 'haiku') != 'haiku': return 'capable'
    return 'balanced' if pref('escalate', True) and pref('escalateAuto', True) else 'cheapest'


def work_model():
    model = pref('model', 'haiku')
    if model == 'haiku': model = pref('agentModel', 'sonnet')
    return model if model != 'haiku' else 'sonnet'


def main_model():
    if server(): return pref('model', 'haiku')
    return work_model() if routing_mode() == 'capable' else 'haiku'


def server(model=None):
    """Settings → Custom server: env that points `claude` at another server with Claude's API (DeepSeek, Ollama, LM Studio, vLLM)."""
    base, model = str(pref('apiBase', '')).strip(), str(pref('apiModel', '') if model is None else model).strip()
    if not base: return {}
    env = {'ANTHROPIC_BASE_URL': base, 'ANTHROPIC_AUTH_TOKEN': str(pref('apiKey', '')).strip() or 'none', 'ANTHROPIC_API_KEY': ''}
    return {**env, **{f'ANTHROPIC_DEFAULT_{m}_MODEL': model for m in ('HAIKU', 'SONNET', 'OPUS') if model}}


def _models_at(url, key='', timeout=4):
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {key}', 'x-api-key': key, 'anthropic-version': '2023-06-01'})
    try:
        response = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as error:
        error.close()
        raise
    with response:
        return [m['id'] for m in json.load(response).get('data', []) if isinstance(m, dict) and m.get('id')]


def models():
    """The custom server's model names. /v1/models is the same list shape on OpenAI-style and Anthropic-style servers."""
    probe = os.environ.get('ATTICUS_PROBE_BASE')
    base = str(pref('apiBase', '') if probe is None else probe).strip().rstrip('/')
    key = str(pref('apiKey', '') if probe is None else os.environ.get('ATTICUS_PROBE_KEY', '')).strip()
    try: u = urllib.parse.urlparse(base)
    except ValueError: return []
    if u.scheme not in ('http', 'https') or not u.hostname: return []
    root = f'{u.scheme}://{u.netloc}'
    for url in dict.fromkeys([base + '/v1/models', root + '/v1/models', root + '/models']) if u.netloc else []:
        try:
            ids = _models_at(url, key)
            if ids: return ids
        except (OSError, ValueError, AttributeError, TypeError):
            continue
    return []
