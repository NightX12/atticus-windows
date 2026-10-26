"""winctl section: joplin (split from winctl.py, code unchanged)."""
import ctypes, json, os, re, subprocess, sys, time
from ctypes import wintypes as W
from ._core import HOME

# ---------- Joplin: its local API (Tools → Options → Web Clipper), not its window ----------

def _joplin_settings():
    try:
        return json.load(open(os.path.join(HOME, '.config', 'joplin-desktop', 'settings.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def joplin(method, path, body=None, **query):
    """One call to Joplin's API. The token is read from Joplin's own settings here and never leaves this process."""
    import urllib.request, urllib.parse, urllib.error
    s = _joplin_settings()
    token = s.get('api.token')
    if not token:
        raise RuntimeError('Joplin has no API token: turn on Tools → Options → Web Clipper in Joplin')
    port = s.get('api.port') or 41184
    def up():
        try:
            return urllib.request.urlopen(f'http://127.0.0.1:{port}/ping', timeout=1).read() == b'JoplinClipperServer'
        except OSError:
            return False
    if not up():
        if not find('Joplin'):
            launch('Joplin')
        for _ in range(40):   # Joplin starts its server a few seconds after it opens
            time.sleep(0.25)
            if up():
                break
        else:
            raise RuntimeError('Joplin is not answering: open Joplin and turn on Tools → Options → Web Clipper')
    url = f'http://127.0.0.1:{port}/{path}?' + urllib.parse.urlencode({'token': token, **query})
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=10).read() or b'null')


def _all(path, **q):
    out, page = [], 1
    while page < 20:
        r = joplin('GET', path, page=page, limit=100, **q)
        out += r.get('items', [])
        if not r.get('has_more'):
            return out
        page += 1
    return out


def joplin_notebook(name):
    books = _all('folders', fields='id,title')
    k = key(name)
    return next((b for b in books if key(b['title']) == k), None) or next((b for b in books if k and k in key(b['title'])), None), books


def joplin_note(ref):
    """A note by its id, its exact title, or the best search match: {id, title, parent_id} or None."""
    if re.fullmatch(r'[0-9a-f]{32}', ref):
        return joplin('GET', f'notes/{ref}', fields='id,title,parent_id')
    hits = _all('search', query=ref, type='note', fields='id,title,parent_id')[:20]
    exact = next((n for n in hits if n['title'].lower() == ref.lower()), None)
    if exact:
        return exact
    recent = _titles()   # the search index lags behind new notes: look at titles too
    k = ref.lower()
    return next((n for n in recent if n['title'].lower() == k), None) or (hits[0] if hits else None) or next((n for n in recent if k in n['title'].lower()), None)


def _titles():
    out = []
    for page in range(1, 6):   # the 500 most recently changed notes
        r = joplin('GET', 'notes', fields='id,title,parent_id', order_by='updated_time', order_dir='DESC', limit=100, page=page)
        out += r.get('items', [])
        if not r.get('has_more'):
            break
    return out


def joplin_cmd(args):
    """--joplin new "<title>" "<text>" [--in "<notebook>"] | find "<words>" | read "<note>" | add "<note>" "<text>" | open "<note>" | notebooks"""
    try:
        what, rest = (args[0], args[1:]) if args else ('', [])
        book = None
        if '--in' in rest:
            i = rest.index('--in'); book = rest[i + 1] if i + 1 < len(rest) else ''; rest = rest[:i] + rest[i + 2:]
        if what == 'notebooks':
            return '\n'.join(b['title'] for b in _all('folders', fields='id,title')) or 'no notebooks'
        if what == 'new' and rest:
            body = {'title': rest[0], 'body': '\n'.join(rest[1:])}
            if book:
                b, books = joplin_notebook(book)
                if not b:
                    return f'no notebook called "{book}". Notebooks: ' + ', '.join(x['title'] for x in books)
                body['parent_id'] = b['id']
            n = joplin('POST', 'notes', body)
            return f'created note "{n["title"]}" (id {n["id"]})'
        if what == 'find' and rest:
            books = {b['id']: b['title'] for b in _all('folders', fields='id,title')}
            q = ' '.join(rest)
            hits = _all('search', query=q, type='note', fields='id,title,parent_id')[:15]
            seen = {n['id'] for n in hits}
            hits += [n for n in _titles() if all(w in n['title'].lower() for w in q.lower().split()) and n['id'] not in seen][:15 - len(hits)]
            return '\n'.join(f'{n["title"]} [{books.get(n["parent_id"], "?")}] id {n["id"]}' for n in hits) or 'no notes found'
        n = joplin_note(rest[0]) if rest else None
        if what in ('read', 'add', 'open') and not n:
            return f'no note matching "{rest[0] if rest else ""}"'
        if what == 'read':
            return f'{n["title"]}\n' + joplin('GET', f'notes/{n["id"]}', fields='body')['body'][:4000]
        if what == 'add' and len(rest) > 1:
            old = joplin('GET', f'notes/{n["id"]}', fields='body')['body'].rstrip()
            joplin('PUT', f'notes/{n["id"]}', {'body': (old + '\n\n' if old else '') + '\n'.join(rest[1:])})
            return f'added to "{n["title"]}"'
        if what == 'open':
            os.startfile(f'joplin://x-callback-url/openNote?id={n["id"]}')
            return f'opened "{n["title"]}" in Joplin'
        return joplin_cmd.__doc__
    except Exception as e:
        return f'Joplin: {e}'



# siblings last, so circular references resolve (all defs above exist by then)
from .apps import launch  # noqa: E402
from .window import find, key  # noqa: E402
