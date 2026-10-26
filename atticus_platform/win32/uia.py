"""winctl section: uia (split from winctl.py, code unchanged)."""
import ctypes, json, os, re, subprocess, sys, time
from ctypes import wintypes as W
from .. import paths
from ..pure import ui_item  # platform-neutral, shared with the fake backend

# ---------- inside apps: UI Automation (what Peekaboo does on the Mac) ----------


ACTIONABLE = {'ButtonControl': 'B', 'SplitButtonControl': 'B', 'MenuItemControl': 'M', 'HyperlinkControl': 'L', 'TabItemControl': 'T',
              'CheckBoxControl': 'C', 'RadioButtonControl': 'R', 'ComboBoxControl': 'D', 'EditControl': 'E', 'DocumentControl': 'E',
              'ListItemControl': 'I', 'TreeItemControl': 'I', 'DataItemControl': 'I', 'TextControl': 'X'}   # X: labels, read-only (a result, a status)


def _walk(root, most=1500, secs=2.5):
    import uiautomation as auto
    end, n = time.time() + secs, 0
    for c, _ in auto.WalkControl(root, maxDepth=40):
        n += 1
        if n > most or time.time() > end:
            break
        yield c


def _rid(c):
    try:
        return list(c.GetRuntimeId())
    except Exception:
        return []


def ui_see(app, words='', most=80):
    """The buttons, links, fields, tabs and menu items in `app`'s window, each with an ID for ui_click / ui_set."""
    import uiautomation as auto
    ws = find(app, words) or find(app)
    if not ws:
        return f'no window found for "{app}"'
    root = auto.ControlFromHandle(ws[0]['hwnd'])
    items, lines, count = {}, [], {}
    for c in _walk(root):
        kind = ACTIONABLE.get(c.ControlTypeName)
        if not kind or kind == 'X' and count.get('X', 0) >= 15:
            continue
        try:
            if c.IsOffscreen or not c.IsEnabled:
                continue
            r = c.BoundingRectangle
            if r.width() <= 0 or r.height() <= 0:
                continue
            name = ' '.join((c.Name or '').split())[:60]
            value = ''
            if kind == 'E':
                try:
                    value = ' '.join(c.GetValuePattern().Value.split())[:60]
                except Exception:
                    pass
            if not re.search(r'\w', name + value):   # unnamed, or an icon-font glyph
                continue
        except Exception:
            continue
        count[kind] = count.get(kind, 0) + 1
        i = f'{kind}{count[kind]}'
        items[i] = {'rid': _rid(c), 'name': name, 'type': c.ControlTypeName[:-7], 'rect': [r.left, r.top, r.right, r.bottom]}
        lines.append(f'{i} {items[i]["type"]} "{name}"' + (f' = "{value}"' if value else ''))
        if len(items) >= most:
            break
    if paths.UI_FILE:
        json.dump({'hwnd': ws[0]['hwnd'], 'app': ws[0]['app'], 'items': items}, open(paths.UI_FILE, 'w', encoding='utf-8'))
    return f'{ws[0]["app"]}: {ws[0]["title"]}\n' + ('\n'.join(lines) or 'nothing clickable found')


def _find_items(ids):
    """[(id, control or None, saved item or None)] for several elements, in one walk of the window."""
    import uiautomation as auto
    saved = json.load(open(paths.UI_FILE, encoding='utf-8'))
    want = [(i, ui_item(i)) for i in ids]
    root = auto.ControlFromHandle(saved['hwnd'])
    found = {}
    if root:
        rids = {tuple(it['rid']): n for n, (_, it) in enumerate(want) if it and it['rid']}
        for c in _walk(root):
            r = tuple(_rid(c))
            if r in rids:
                found.setdefault(rids[r], c)
            else:
                for n, (_, it) in enumerate(want):   # the page redrew: same kind and name
                    if it and n not in found and c.ControlTypeName[:-7] == it['type'] and ' '.join((c.Name or '').split())[:60] == it['name']:
                        found[n] = c
            if len(found) == len(want):
                break
    return [(i, found.get(n), it) for n, (i, it) in enumerate(want)], saved['hwnd']


def _find_item(i):
    (got,), _ = _find_items([i])
    return got[1], got[2]


def _press(c, it):
    for how in ('GetInvokePattern', 'GetTogglePattern', 'GetSelectionItemPattern', 'GetExpandCollapsePattern'):
        try:
            p = getattr(c, how)()
            if not p:
                continue
            {'GetInvokePattern': lambda: p.Invoke(), 'GetTogglePattern': lambda: p.Toggle(),
             'GetSelectionItemPattern': lambda: p.Select(), 'GetExpandCollapsePattern': lambda: p.Expand()}[how]()
            return f'clicked {it["type"].lower()} "{it["name"]}"'
        except Exception:
            continue
    try:
        c.Click(simulateMove=False)
        return f'clicked "{it["name"]}" (with the mouse)'
    except Exception as e:
        return f'could not click "{it["name"]}": {e}'


def ui_click(*ids):
    """Press elements from the last ui_see, in order: through the app's own accessibility actions when it has them (no mouse),
    else a real click. Stops at the first one that is missing."""
    try:
        got, hwnd = _find_items(ids)
    except (OSError, ValueError):
        return 'look first: run --ui see "<app>"'
    bring(hwnd)
    out = []
    for i, c, it in got:
        if not it:
            out.append(f'no element {i}: look again'); break
        if not c:
            out.append(f'"{it["name"]}" is gone: look again'); break
        out.append(_press(c, it))
        if len(got) > 1:
            time.sleep(0.05)   # the app keeps up
    return '\n'.join(out)


def ui_set(i, text):
    """Fill a field from the last ui_see with text (no clipboard, no typing). Falls back to focus + paste."""
    try:
        c, it = _find_item(i)
    except (OSError, ValueError):
        return 'look first: run --ui see "<app>"'
    if not c:
        return f'no element {i}: look again'
    try:
        c.GetValuePattern().SetValue(text)
        return f'filled "{it["name"]}"'
    except Exception:
        try:
            c.SetFocus()
            time.sleep(0.15)
            old = get_clip(); set_clip(text); keys(0x11, 0x41); keys(0x11, 0x56); time.sleep(0.3); set_clip(old)
            return f'typed into "{it["name"]}"'
        except Exception as e:
            return f'could not fill "{it["name"]}": {e}'


KEYNAMES = {'ctrl': 0x11, 'control': 0x11, 'alt': 0x12, 'shift': 0x10, 'win': 0x5B, 'enter': 0x0D, 'return': 0x0D, 'tab': 0x09, 'esc': 0x1B,
            'escape': 0x1B, 'space': 0x20, 'backspace': 0x08, 'delete': 0x2E, 'del': 0x2E, 'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27,
            'home': 0x24, 'end': 0x23, 'pageup': 0x21, 'pagedown': 0x22, **{f'f{n}': 0x6F + n for n in range(1, 13)}}


def hotkey(app, combo):
    """Press a key combination ("ctrl+s", "alt+f4", "f5") in `app`'s front window."""
    vks = []
    for k in combo.lower().replace(' ', '').split('+'):
        vk = KEYNAMES.get(k) or (ord(k.upper()) if len(k) == 1 and k.isalnum() else None)
        if vk is None:
            return f'unknown key "{k}"'
        vks.append(vk)
    if app and key(front()[0]) != key(app):
        focus_app(app)
        time.sleep(0.2)
    keys(*vks)
    time.sleep(0.35)   # the app reacts (a switcher opens, a channel loads) before the next step
    return f'pressed {combo}'



# siblings last, so circular references resolve (all defs above exist by then)
from .clipboard import get_clip, keys, set_clip  # noqa: E402
from .window import bring, find, focus_app, front  # noqa: E402
