"""
Passwort der Web-Verbindung im Windows-Tresor (Anmeldeinformationsverwaltung, advapi32) -
ohne Qt und ohne zusätzliche Bibliothek (ctypes).

Das Passwort steht nie in den Einstellungen (QSettings), nie in Protokollen und nie in
Fehlermeldungen. Auf anderen Systemen als Windows gibt es kein Speichern: die Funktionen
liefern dann None bzw. False, das Programm fragt das Passwort bei jeder Nutzung ab.

Zielname im Tresor: "SHS-Pruefungsprogramm/Web:<Adresse>" (eine Adresse, ein Eintrag).
"""

from __future__ import annotations

import sys

_ZIEL_VORSATZ = "SHS-Pruefungsprogramm/Web:"
_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2  # bleibt auf diesem Rechner (wird nicht ins Netz gespiegelt)
_ERROR_NOT_FOUND = 1168


def _ist_windows() -> bool:
    """Eigene Funktion, damit Tests die Plattformweiche ersetzen können."""
    return sys.platform == "win32"


def verfuegbar() -> bool:
    """Gibt es auf diesem System einen Tresor?"""
    return _ist_windows()


def ziel_name(adresse: str) -> str:
    return _ZIEL_VORSATZ + adresse


def _api():
    """Bindet advapi32 mit den Strukturen (nur unter Windows aufrufen)."""
    import ctypes
    from ctypes import wintypes

    class CREDENTIALW(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]

    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIALW), wintypes.DWORD]
    advapi.CredWriteW.restype = wintypes.BOOL
    advapi.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                 ctypes.POINTER(ctypes.POINTER(CREDENTIALW))]
    advapi.CredReadW.restype = wintypes.BOOL
    advapi.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    advapi.CredDeleteW.restype = wintypes.BOOL
    advapi.CredFree.argtypes = [ctypes.c_void_p]
    advapi.CredFree.restype = None
    return ctypes, advapi, CREDENTIALW


def passwort_speichern(adresse: str, benutzer: str, passwort: str) -> bool:
    """Legt das Passwort im Tresor ab (ersetzt einen vorhandenen Eintrag). False, wenn es auf diesem
    System keinen Tresor gibt oder das Speichern scheitert - das Passwort bleibt dann ungespeichert."""
    if not _ist_windows() or not passwort:
        return False
    try:
        ctypes, advapi, CREDENTIALW = _api()
        blob = passwort.encode("utf-16-le")
        puffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
        eintrag = CREDENTIALW()
        eintrag.Type = _CRED_TYPE_GENERIC
        eintrag.TargetName = ziel_name(adresse)
        eintrag.CredentialBlobSize = len(blob)
        eintrag.CredentialBlob = ctypes.cast(puffer, ctypes.POINTER(ctypes.c_ubyte))
        eintrag.Persist = _CRED_PERSIST_LOCAL_MACHINE
        eintrag.UserName = benutzer
        return bool(advapi.CredWriteW(ctypes.byref(eintrag), 0))
    except Exception:  # noqa: BLE001 - ein defekter Tresor darf die Arbeit nie stören
        return False


def passwort_lesen(adresse: str) -> str | None:
    """Das gespeicherte Passwort oder None (nichts gespeichert, kein Tresor, Lesefehler)."""
    if not _ist_windows():
        return None
    try:
        ctypes, advapi, CREDENTIALW = _api()
        zeiger = ctypes.POINTER(CREDENTIALW)()
        if not advapi.CredReadW(ziel_name(adresse), _CRED_TYPE_GENERIC, 0, ctypes.byref(zeiger)):
            return None
        try:
            eintrag = zeiger.contents
            roh = ctypes.string_at(eintrag.CredentialBlob, eintrag.CredentialBlobSize)
            return roh.decode("utf-16-le") or None
        finally:
            advapi.CredFree(zeiger)
    except Exception:  # noqa: BLE001
        return None


def passwort_loeschen(adresse: str) -> bool:
    """Entfernt den Eintrag. True, wenn danach keiner mehr da ist (auch wenn vorher keiner da war)."""
    if not _ist_windows():
        return False
    try:
        ctypes, advapi, _ = _api()
        if advapi.CredDeleteW(ziel_name(adresse), _CRED_TYPE_GENERIC, 0):
            return True
        return ctypes.get_last_error() == _ERROR_NOT_FOUND
    except Exception:  # noqa: BLE001
        return False
