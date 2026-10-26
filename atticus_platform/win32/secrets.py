"""winctl section: secrets (split from winctl.py, code unchanged)."""
import ctypes, json, os, re, subprocess, sys, time
from ctypes import wintypes as W

# ---------- secrets: Windows Credential Manager (generic credentials, this user only) ----------

class _CRED(ctypes.Structure):
    _fields_ = [('Flags', W.DWORD), ('Type', W.DWORD), ('TargetName', W.LPWSTR), ('Comment', W.LPWSTR), ('LastWritten', W.FILETIME),
                ('CredentialBlobSize', W.DWORD), ('CredentialBlob', ctypes.POINTER(ctypes.c_byte)), ('Persist', W.DWORD),
                ('AttributeCount', W.DWORD), ('Attributes', ctypes.c_void_p), ('TargetAlias', W.LPWSTR), ('UserName', W.LPWSTR)]


_advapi = ctypes.WinDLL('advapi32', use_last_error=True)
_advapi.CredReadW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, ctypes.POINTER(ctypes.POINTER(_CRED))]
_advapi.CredWriteW.argtypes = [ctypes.POINTER(_CRED), W.DWORD]
_advapi.CredDeleteW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD]
_advapi.CredFree.argtypes = [ctypes.c_void_p]


def secret_get(name):
    p = ctypes.POINTER(_CRED)()
    if not _advapi.CredReadW(f'Atticus/{name}', 1, 0, ctypes.byref(p)):
        return ''
    try:
        return ctypes.string_at(p.contents.CredentialBlob, p.contents.CredentialBlobSize).decode('utf-16-le')
    finally:
        _advapi.CredFree(p)


def secret_set(name, value):
    if not value:
        return bool(_advapi.CredDeleteW(f'Atticus/{name}', 1, 0))
    blob = value.encode('utf-16-le')
    buf = (ctypes.c_byte * len(blob)).from_buffer_copy(blob)
    c = _CRED(Type=1, TargetName=f'Atticus/{name}', CredentialBlobSize=len(blob), CredentialBlob=buf, Persist=2, UserName='Atticus')   # Persist 2: this user, this PC
    return bool(_advapi.CredWriteW(ctypes.byref(c), 0))
