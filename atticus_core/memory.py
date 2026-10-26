"""Saved rules (memory.md, one "- rule" per line) and the combined memory search, ported from atticus-mac.
Windows change: the fcntl lock became atticus_core.files.locked, os.fchmod became write_private."""
import threading
from functools import wraps

from . import config
from .files import locked as _file_lock, write_private
from .profile import CATEGORIES, _words, me

STOP = set('a an the to of in on and or for my me i you it is be do can could would please with at this that what how'.split())
_MEMORY_MUTEX = threading.RLock()
_MEMORY_STATE = threading.local()


def memory_file():
    return config.path('memory.md')


def _memory_locked(operation):
    @wraps(operation)
    def locked(*args, **kwargs):
        with _MEMORY_MUTEX:
            if getattr(_MEMORY_STATE, 'locked', False):
                return operation(*args, **kwargs)
            with _file_lock(memory_file() + '.lock'):
                _MEMORY_STATE.locked = True
                try:
                    return operation(*args, **kwargs)
                finally:
                    _MEMORY_STATE.locked = False
    return locked


def memory_rules():
    try:
        with open(memory_file(), encoding='utf-8') as f:
            return [line.removeprefix('- ').strip() for line in f if line.removeprefix('- ').strip()]
    except OSError:
        return []


def _save_memory_rules(rules):
    write_private(memory_file(), ''.join('- ' + rule + '\n' for rule in rules))


@_memory_locked
def remember_rule(text):
    text = ' '.join(str(text).split())
    if not text:
        return 'not saved: empty rule'
    rules = memory_rules()
    if text.casefold() not in {rule.casefold() for rule in rules}:
        rules.append(text)
        _save_memory_rules(rules)
    return 'saved'


@_memory_locked
def edit_rule(old, new):
    old, new = old.strip(), ' '.join(str(new).split())
    rules = [new if rule == old and new else rule for rule in memory_rules() if rule != old or new]
    _save_memory_rules(rules)
    return 'saved'


@_memory_locked
def forget_rules(query):
    words = ' '.join(str(query).split()).casefold().split()
    if not words:
        return 0
    rules = memory_rules()
    exact = [rule for rule in rules if rule.casefold() == ' '.join(words)]
    kept = [rule for rule in rules if rule not in exact] if exact else [rule for rule in rules if not all(word in rule.casefold() for word in words)]
    _save_memory_rules(kept)
    return len(rules) - len(kept)


def memory_find(query=''):
    """Search both user-memory stores without making the model guess a profile category."""
    words = _words(query) - STOP
    matches = lambda text: not words or bool(words & _words(text))
    facts = [f for f in me()['facts'] if not f.get('sensitive') and
             (matches(f['category'].replace('_', ' ') + ' ' + CATEGORIES[f['category']]) or
              matches(f['kind']) or matches(f['value']))]
    rules = [rule for rule in memory_rules() if matches(rule)]
    lines = []
    for key in CATEGORIES:
        found = [f for f in facts if f['category'] == key]
        if found:
            lines += [CATEGORIES[key] + ':'] + [f"- [{f['id']}] {f['kind']}: {f['value']}" for f in found]
    if rules:
        lines += ['Rules:'] + ['- ' + rule for rule in rules]
    return '\n'.join(lines)[:8000] or 'Nothing matches.'


def memory_items():
    """What Settings → Memory lists, as (category, text): profile facts by category, and saved rules under 'rules'."""
    rules = memory_rules()
    return {('rules', r) for r in rules if r} | {(f['category'], f"{f['kind']}: {f['value']}") for f in me()['facts']}


def memory_receipt(before):
    """The ask's memory changes for the box: [{c, label, t, add}], added first, in Settings order."""
    after, order = memory_items(), list(CATEGORIES) + ['rules']
    return [{'c': c, 'label': CATEGORIES.get(c, 'Rules'), 't': t, 'add': add}
            for add, items in ((True, after - before), (False, before - after)) for c, t in sorted(items, key=lambda i: (order.index(i[0]), i[1]))]
