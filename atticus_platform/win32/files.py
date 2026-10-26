"""winctl section: files (split from winctl.py, code unchanged)."""
import ctypes, json, os, re, subprocess, sys, time
from ctypes import wintypes as W
from ._core import HOME, ps

# ---------- files ----------

def find_files(words, content=False, where='', most=20):
    """Windows Search's index (like Spotlight): by name, or by what's inside. Falls back to a quick walk of the user's folders."""
    words = ' '.join(words.split())
    if not words:
        return []
    scope = (os.path.abspath(os.path.expanduser(where)) if where else HOME).replace('\\', '/')
    q = words.replace("'", "''")
    cond = f"CONTAINS(*, '\"{q}\"')" if content else ' AND '.join(f"System.FileName LIKE '%{w}%'" for w in q.split())
    sql = f"SELECT TOP {most} System.ItemPathDisplay FROM SYSTEMINDEX WHERE SCOPE='file:{scope}' AND {cond} ORDER BY System.DateModified DESC"
    out = ps("$c = New-Object -ComObject ADODB.Connection; $c.Open(\"Provider=Search.CollatorDSO;Extended Properties='Application=Windows';\"); "
             f"$r = $c.Execute(\"{sql}\"); while (-not $r.EOF) {{ $r.Fields.Item(0).Value; $r.MoveNext() }}", 15)
    hits = [l for l in out.splitlines() if l.strip()]
    if hits or content:
        return hits[:most]
    end, ws = time.time() + 3, [w.lower() for w in words.split()]
    for root, dirs, files in os.walk(scope):
        dirs[:] = [d for d in dirs if not d.startswith(('.', '$')) and d not in ('AppData', 'node_modules', '__pycache__')]
        for f in files + dirs:
            if all(w in f.lower() for w in ws):
                hits.append(os.path.join(root, f))
        if len(hits) >= most or time.time() > end:
            break
    return hits[:most]


