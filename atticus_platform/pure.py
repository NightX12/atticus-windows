"""Platform-neutral helpers (no ctypes): used unchanged by the Windows backend and the fake backend."""
import json, re

from . import paths


def key(s):
    return re.sub(r'[^a-z0-9]', '', s.lower().removesuffix('.exe'))


def rect_for(where, area, size):
    """Where a window goes in a work area (x, y, w, h): left/right half, full, or centered at its own size (capped)."""
    x, y, w, h = area
    cw, ch = min(size[0], w), min(size[1], h)
    return {'left': (x, y, w // 2, h), 'right': (x + w // 2, y, w - w // 2, h), 'full': (x, y, w, h),
            'center': (x + (w - cw) // 2, y + (h - ch) // 2, cw, ch)}[where]


def ui_item(i):
    """An element from the last ui_see, by ID ("B3") or by its exact name ("Seven")."""
    try:
        items = json.load(open(paths.UI_FILE, encoding='utf-8'))['items']
    except (OSError, ValueError, TypeError, AttributeError):
        return None
    if i in items:
        return items[i]
    return next((it for it in items.values() if it['name'].lower() == i.lower() and it['type'] != 'Text'), None)
