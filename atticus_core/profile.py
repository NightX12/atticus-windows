"""About you (me.json v2), ported unchanged in behaviour from atticus-mac. Changes for Windows: fcntl/os.fchmod
became atticus_core.files (msvcrt lock, atomic write), and the snapshot for profile_import comes from the caller
(Windows has no Contacts.app; mac_profile() is not ported)."""
import hashlib, json, os, re, threading, time
from functools import wraps

from . import config
from .files import locked as _file_lock, write_private


def me_file():
    return config.path('me.json')


CATEGORIES = {
    'basics': 'Basics', 'contact': 'Contact', 'places': 'Places', 'school_work': 'School & work',
    'links': 'Links & handles', 'preferences': 'Preferences', 'people': 'People', 'notes': 'Notes',
}
SOURCES = ('you', 'contacts', 'mail', 'learned')
SENSITIVE = re.compile(r'\b(ssn|social security|credit card|debit card|card number|cvv|password|passcode|pin|health|medical|money|income|salary|bank|routing)\b', re.I)


def category(value):
    key = re.sub(r'[^a-z]+', '_', str(value).lower()).strip('_')
    return {'basic': 'basics', 'school': 'school_work', 'work': 'school_work', 'school_and_work': 'school_work',
            'links_handles': 'links', 'link': 'links', 'handle': 'links', 'preference': 'preferences',
            'person': 'people', 'note': 'notes'}.get(key, key if key in CATEGORIES else 'notes')


def _profile_date():
    return time.strftime('%Y-%m-%d')


def _mask(value):
    tail = ''.join(re.findall(r'\w', value, re.UNICODE))[-4:]
    return '••••' + (f' {tail}' if tail else '')


def _fact(category_, kind, value, source='you', date=None, identifier=None, sensitive=None):
    if value is None:
        return None
    category_, kind, value = category(category_), ' '.join(str(kind or '').split())[:40] or 'note', ' '.join(str(value).split())[:300]
    if not value:
        return None
    private = bool(sensitive) or bool(SENSITIVE.search(kind + ' ' + value))
    if private and not value.startswith('••••'):
        value = _mask(value)
    source = source if source in SOURCES else 'you'
    key = '\0'.join((source, category_, kind.lower(), value.lower()))
    return {'id': identifier or hashlib.sha256(key.encode()).hexdigest()[:12], 'category': category_, 'kind': kind,
            'value': value, 'source': source, 'date': date if re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(date or '')) else _profile_date(),
            **({'sensitive': True} if private else {})}



_PROFILE_MUTEX = threading.RLock()
_PROFILE_STATE = threading.local()


def _profile_locked(operation):
    @wraps(operation)
    def locked(*args, **kwargs):
        with _PROFILE_MUTEX:
            if getattr(_PROFILE_STATE, 'locked', False):
                return operation(*args, **kwargs)
            with _file_lock(me_file() + '.lock'):
                _PROFILE_STATE.locked = True
                try:
                    return operation(*args, **kwargs)
                finally:
                    _PROFILE_STATE.locked = False
    return locked


def _save_profile(profile):
    write_private(me_file(), json.dumps({'version': 2, 'facts': profile['facts']}, indent=1, ensure_ascii=False))


def _normalize_profile(raw, legacy_date=None):
    if isinstance(raw, dict) and raw.get('version') == 2 and isinstance(raw.get('facts'), list):
        facts = [_fact(f.get('category'), f.get('kind'), f.get('value'), f.get('source'), f.get('date'),
                       f.get('id'), f.get('sensitive')) for f in raw['facts'] if isinstance(f, dict)]
        profile = {'version': 2, 'facts': [f for f in facts if f]}
        return profile, profile != {'version': 2, 'facts': raw['facts']}
    facts = []
    if isinstance(raw, dict):
        if raw.get('name'):
            facts.append(_fact('basics', 'name', raw['name'], 'you', legacy_date))
        if raw.get('about'):
            facts.append(_fact('notes', 'about', raw['about'], 'you', legacy_date))
        facts.extend(_fact('notes', 'fact', value, 'learned', legacy_date) for value in raw.get('facts', []) if value)
    return {'version': 2, 'facts': [f for f in facts if f]}, isinstance(raw, dict)


@_profile_locked
def me():
    try:
        with open(me_file(), encoding='utf-8') as f:
            raw = json.load(f)
        legacy_date = time.strftime('%Y-%m-%d', time.localtime(os.path.getmtime(me_file())))
    except (OSError, ValueError):
        return {'version': 2, 'facts': []}
    profile, migrated = _normalize_profile(raw, legacy_date)
    if migrated:
        try:
            _save_profile(profile)
        except OSError:
            pass
    return profile


def profile_name(profile=None):
    facts = (profile or me())['facts']
    names = [f for f in facts if f['category'] == 'basics' and f['kind'].lower() == 'name' and not f.get('sensitive')]
    return next((f['value'] for source in SOURCES for f in names if f['source'] == source), '')


def _is_answer_preference(fact):
    return fact['category'] == 'preferences' and bool(_words(fact['kind']) & {'answer', 'response', 'reply', 'writing', 'style'})


def _answer_preferences(profile):
    return [f['value'] for f in profile['facts'] if _is_answer_preference(f) and not f.get('sensitive')]


def me_line(profile=None):
    profile = profile or me()
    parts = ([f'Name: {profile_name(profile)}.'] if profile_name(profile) else []) + \
            ([f"Answer preference: {_answer_preferences(profile)[0].rstrip('.')}."] if _answer_preferences(profile) else [])
    return ' '.join(parts)[:300]


def _words(value):
    words = set(re.findall(r'[a-z0-9]+', str(value).lower()))
    return words | {w[:-1] for w in words if len(w) > 3 and w.endswith('s')} | {w[:-2] for w in words if len(w) > 4 and w.endswith('es')}


def profile_context(task='', screen='', profile=None):
    provided = profile is not None
    profile = profile or me()
    safe = [f for f in profile['facts'] if not f.get('sensitive')]
    seen = _words(task + '\n' + screen)
    relevant = set()
    for f in safe:
        keys = _words(f['kind'])
        category_keys = _words(f['category'].replace('_', ' ') + ' ' + CATEGORIES[f['category']])
        if seen & keys or seen & category_keys or f['category'] == 'people' and seen & _words(f['value']):
            relevant.add(f['category'])
    always = me_line(profile) if provided else me_line()
    lines = [f'About you: {always}'] if always else []
    for key in CATEGORIES:
        facts = [f for f in safe if f['category'] == key and
                 not (key == 'basics' and f['kind'].lower() == 'name') and
                 not _is_answer_preference(f)]
        if key in relevant and facts:
            lines.append(CATEGORIES[key] + ': ' + '; '.join(f"{f['kind']}: {f['value']}" for f in facts))
    return '\n'.join(lines)


def profile_category(name):
    key, profile = category(name), me()
    facts = [f for f in profile['facts'] if f['category'] == key and not f.get('sensitive')]
    return CATEGORIES[key] + ':\n' + ('\n'.join(f"- {f['kind']}: {f['value']} [{f['id']}]" for f in facts) or 'Nothing saved.')


def _request_contains(evidence):
    """The user said these words: in this ask, or in a question of this chat ("remember that" points back). Never the AI's answers."""
    root = os.environ.get('ATTICUS_ASK')
    if not root:
        return True
    said = [str(q) for q in config.heard()]   # atticus.py: this ask's text + the questions of the last 10 min
    needle = ' '.join(re.findall(r'\w+', evidence.lower()))
    return bool(needle) and any(f' {needle} ' in ' ' + ' '.join(re.findall(r'\w+', q.lower())) + ' ' for q in said)


def _split_fact(text, fallback):
    match = re.match(r'\s*([^:=]{1,40})\s*[:=]\s*(.+)', text)
    return (match[1].strip(), match[2].strip()) if match else (fallback, text.strip())


@_profile_locked
def profile_add(category_, text, kind='', source=None):
    profile, category_ = me(), category(category_)
    source = source or ('learned' if os.environ.get('ATTICUS_ASK') else 'you')
    if source == 'learned' and not _request_contains(text):
        return 'not saved: only the user’s own words can change About you'
    kind, value = (kind, text.strip()) if kind else _split_fact(text, CATEGORIES[category_].rstrip('s').lower())
    private = bool(SENSITIVE.search(kind + ' ' + value))
    if source == 'learned' and private:
        return 'not saved: sensitive facts are never learned'
    fact = _fact(category_, kind, value, source, sensitive=private)
    if not fact:
        return 'not saved: empty fact'
    duplicate = next((f for f in profile['facts'] if all(f.get(k) == fact.get(k) for k in ('category', 'kind', 'value', 'source'))), None)
    if not duplicate:
        profile['facts'].append(fact); _save_profile(profile)
    return 'saved'


@_profile_locked
def profile_set(identifier, text, evidence=None):
    if os.environ.get('ATTICUS_ASK') and not _request_contains(evidence if evidence is not None else text):
        return 'not saved: only the user’s own words can change About you'
    profile = me()
    fact = next((f for f in profile['facts'] if f['id'] == identifier), None)
    if not fact:
        return 'not found'
    kind, value = _split_fact(text, fact['kind'])
    changed = _fact(fact['category'], kind, value, 'learned' if os.environ.get('ATTICUS_ASK') else 'you',
                    identifier=identifier, sensitive=bool(SENSITIVE.search(kind + ' ' + value)))
    if not changed:
        return 'not saved: empty fact'
    profile['facts'][profile['facts'].index(fact)] = changed; _save_profile(profile)
    return 'saved'


@_profile_locked
def profile_drop(identifier, evidence=''):
    if os.environ.get('ATTICUS_ASK') and not _request_contains(evidence):
        return 'not forgotten: only the user’s own words can change About you'
    profile = me()
    kept = [f for f in profile['facts'] if f['id'] != identifier]
    if len(kept) == len(profile['facts']):
        return 'not found'
    profile['facts'] = kept; _save_profile(profile)
    return 'forgotten'


@_profile_locked
def profile_forget_source(source, evidence=''):
    if os.environ.get('ATTICUS_ASK') and not _request_contains(evidence):
        return 'not forgotten: only the user’s own words can change About you'
    if source not in SOURCES:
        return 'not found'
    profile = me(); before = len(profile['facts'])
    profile['facts'] = [f for f in profile['facts'] if f['source'] != source]
    _save_profile(profile)
    return f'forgotten {before - len(profile["facts"])}'


@_profile_locked
def profile_import(snapshot=None):
    data, profile = snapshot if snapshot is not None else {'errors': ['contacts', 'mail']}, me()
    incoming, refreshed = [], set()
    contacts_data = data.get('contacts') if isinstance(data, dict) else None
    if isinstance(contacts_data, dict) and 'contacts' not in data.get('errors', []):
        refreshed.add('contacts')
        def add(category_, kind, value):
            fact = _fact(category_, kind, value, 'contacts')
            if fact:
                incoming.append(fact)
        add('basics', 'name', contacts_data.get('name'))
        add('basics', 'birthday', contacts_data.get('birthday'))
        add('basics', 'pronouns', contacts_data.get('pronouns'))
        for item in contacts_data.get('emails', []):
            add('contact', ((item.get('label') or '') + ' email').strip(), item.get('value'))
        for item in contacts_data.get('phones', []):
            add('contact', ((item.get('label') or '') + ' phone').strip(), item.get('value'))
        for item in contacts_data.get('addresses', []):
            add('places', ((item.get('label') or '') + ' address').strip(), item.get('value'))
        for key, label in [('organization', 'organization'), ('department', 'department'), ('jobTitle', 'job title')]:
            add('school_work', label, contacts_data.get(key))
        for item in contacts_data.get('urls', []):
            add('links', item.get('label') or 'url', item.get('value'))
        for item in contacts_data.get('social', []):
            add('links', item.get('label') or 'social', item.get('value'))
        for item in contacts_data.get('related', []):
            add('people', item.get('label') or 'relation', item.get('value'))
    mail_data = data.get('mail') if isinstance(data, dict) else None
    if isinstance(mail_data, list) and 'mail' not in data.get('errors', []):
        refreshed.add('mail')
        for account in mail_data:
            if not isinstance(account, dict):
                continue
            account_fact = _fact('contact', 'mail account', account.get('name'), 'mail')
            if account_fact:
                incoming.append(account_fact)
            for address in account.get('emails', []):
                fact = _fact('contact', ((account.get('name') or '') + ' email').strip() or 'email', address, 'mail')
                if fact:
                    incoming.append(fact)
    if refreshed:
        profile['facts'] = [f for f in profile['facts'] if f['source'] not in refreshed]
        seen = {(f['source'], f['category'], f['kind'].lower(), f['value'].lower()) for f in profile['facts']}
        for fact in incoming:
            key = (fact['source'], fact['category'], fact['kind'].lower(), fact['value'].lower())
            if key not in seen:
                profile['facts'].append(fact); seen.add(key)
        _save_profile(profile)
    counts = {source: sum(f['source'] == source for f in profile['facts']) for source in SOURCES}
    return {'counts': counts, 'imported': len(incoming), 'errors': data.get('errors', []) if isinstance(data, dict) else ['contacts', 'mail'],
            'errorReasons': data.get('errorReasons', {}) if isinstance(data, dict) else {}}
