"""Nimmt die Bilder der Web-Version fürs Handbuch auf (docs/bilder/handbuch_web_*.png).

Aufruf:  python tools/web_screenshots.py [--ziel ORDNER] [--nur name1,name2]

Die Web-Oberfläche läuft dafür im Prozess selbst, mit einer temporären SQLite-Termin-Datei statt PostgreSQL
(dieselben Ersatzfunktionen wie in test_app_web.py) und Demo-Daten aus tools/screenshots.py. Die Seiten werden
über den Flask-Testclient abgerufen (angemeldet als Administrator bzw. als Konto „richterin.a“ mit der Rolle
„eintragen“), als HTML zwischengespeichert und dann von Microsoft Edge (headless) als PNG aufgenommen.
Es wird nichts im Netz erreicht und kein echter Termin gelesen. Voraussetzungen: Edge (unter Windows
vorhanden) und die Python-Pakete aus requirements-dev.txt; Qt wird nicht gebraucht, nur die Demo-Daten aus
tools/screenshots.py (importiert PySide6, läuft offscreen).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

EDGE_PFADE = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)
PORT = 5099
ADMIN, ADMIN_PW = "admin", "demo-passwort-1"
RICHTERIN, RICHTERIN_PW = "richterin.a", "demo-passwort-2"

#: Name -> (Seite, Breite, Höhe, Rolle). Seiten mit "@" werden aus einem Formular-Fehler gebaut.
BILDER = {
    "handbuch_web_login": ("/", 520, 560, None),
    "handbuch_web_teilnehmerliste": ("/teilnehmer", 520, 620, "richterin"),
    "handbuch_web_ergebnis_dk": ("/teilnehmer/@dk", 520, 1100, "richterin"),
    "handbuch_web_ergebnis_fehler": ("@fehler", 520, 620, "richterin"),
    "handbuch_web_admin_termine": ("/admin/termine", 1100, 900, "admin"),
    "handbuch_web_ergebnistabelle": ("/ergebnisse", 1980, 1180, "admin"),
    "handbuch_web_bewertungsbogen": ("/bewertungsbogen/@bogen/Tr%C3%BCmmerfeld", 900, 1480, "admin"),
}


def _edge() -> str:
    for pfad in EDGE_PFADE:
        if Path(pfad).exists():
            return pfad
    sys.exit("Microsoft Edge nicht gefunden (wird für die Aufnahme gebraucht).")


def _vorbereiten(tmp: Path):
    """Baut Demo-Termin und Ersatzfunktionen auf; liefert (conn, ids, Patches, TerminInfo)."""
    import db
    import screenshots as s
    from db_testhilfen import patch_db
    from test_app_web import (
        _NichtSchliessendeVerbindung, _fake_oeffne_termin, _fake_setze_termin_suchpfad, _termin_info,
    )

    conn, _pfad, ids = s._Termine(tmp).neu(ergebnisse="vorhanden")
    conn.execute(db._WEB_BENUTZER_SCHEMA.replace("public.web_benutzer", "web_benutzer"))
    conn.execute(db._WEB_BENUTZER_INDEX_BENUTZERNAME_LOWER)
    termine = [
        _termin_info("termin_demo", verein="Musterverein", ort="Musterstadt", datum="2026-11-14", anzahl_teilnehmer=8),
        _termin_info("termin_demo2", verein="Beispielverein", ort="Beispielstadt", datum="2026-10-10", anzahl_teilnehmer=12),
    ]
    patches = [
        patch_db("verbinde_postgres_server", lambda dsn, password=None: _NichtSchliessendeVerbindung(conn)),
        patch_db("oeffne_termin_postgres", _fake_oeffne_termin),
        patch_db("liste_termine_postgres", lambda c: termine),
        patch_db("_setze_termin_suchpfad", _fake_setze_termin_suchpfad),
    ]
    for p in patches:
        p.start()
    db.admin_einrichten(conn, ADMIN, ADMIN_PW)
    db.benutzer_anlegen(conn, RICHTERIN, RICHTERIN_PW)
    db.eintragen_ergebnis(conn, ids["Testuser5"], "Trümmerfeld", 58, 39)
    db.eintragen_ergebnis(conn, ids["Testuser3"], "Trümmerfeld", 50, 32)
    return conn, ids, patches, termine


def _clients(app):
    """Testclients für anonym, Administrator und Richterin (Rolle „eintragen“), je mit gewähltem Termin."""
    import secrets

    from flask.testing import FlaskClient

    def angemeldet(name, pw):
        c = FlaskClient(app, app.response_class)
        with c.session_transaction() as sitzung:
            sitzung["csrf_token"] = secrets.token_urlsafe(16)
            token = sitzung["csrf_token"]
        antwort = c.post("/", data={"benutzername": name, "passwort": pw, "csrf_token": token}, follow_redirects=True)
        assert antwort.status_code == 200, antwort.status_code
        with c.session_transaction() as sitzung:
            sitzung["schema_name"] = "termin_demo"
        return c

    return {None: FlaskClient(app, app.response_class), "admin": angemeldet(ADMIN, ADMIN_PW),
            "richterin": angemeldet(RICHTERIN, RICHTERIN_PW)}


def _seiten_holen(app, ids, auswahl):
    """Ruft alle gewünschten Seiten als HTML ab (Name -> HTML)."""
    clients = _clients(app)
    seiten = {}
    for name in auswahl:
        pfad, _b, _h, rolle = BILDER[name]
        client = clients[rolle]
        if pfad == "@fehler":
            # Einzelstarter-Formular mit nur einem der beiden Felder (Suche ohne Anzeige) -> Fehlermeldung
            tid = ids["Testuser7"]
            with client.session_transaction() as sitzung:
                token = sitzung["csrf_token"]
            antwort = client.post(f"/teilnehmer/{tid}", data={
                "csrf_token": token, "suche_Flächensuche": "45", "anzeige_Flächensuche": "",
            })
        else:
            pfad = pfad.replace("@dk", str(ids["Testuser2"])).replace("@bogen", str(ids["Testuser1"]))
            antwort = client.get(pfad)
        assert antwort.status_code == 200, f"{name}: HTTP {antwort.status_code}"
        seiten[name] = antwort.data
    return seiten


def main(argv: list[str] | None = None) -> list[Path]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ziel", type=Path, default=REPO / "docs" / "bilder")
    parser.add_argument("--nur", default="", help="kommagetrennte Namen: " + ", ".join(BILDER))
    args = parser.parse_args(argv)
    auswahl = [n.strip() for n in args.nur.split(",") if n.strip()] or list(BILDER)
    unbekannt = [n for n in auswahl if n not in BILDER]
    if unbekannt:
        parser.error(f"unbekannte Bilder: {', '.join(unbekannt)}")
    args.ziel.mkdir(parents=True, exist_ok=True)
    edge = _edge()

    import logging

    import app_web
    from werkzeug.serving import make_server

    logging.getLogger("werkzeug").setLevel(logging.ERROR)  # keine Zeile je Abruf

    with tempfile.TemporaryDirectory(prefix="shs-webbilder-", ignore_cleanup_errors=True) as tmp:
        conn, ids, patches, _termine = _vorbereiten(Path(tmp))
        app_web.app.config.update(
            TESTING=True, SHS_POSTGRES_DSN="postgresql://demo", SESSION_COOKIE_SECURE=False)
        try:
            seiten = _seiten_holen(app_web.app, ids, auswahl)
        finally:
            for p in patches:
                p.stop()
        # Die zwischengespeicherten Seiten und /static (Logo) über einen kleinen lokalen Server ausliefern.
        statisch = app_web.app.wsgi_app

        def wsgi(environ, start_response):
            pfad = environ.get("PATH_INFO", "")
            if pfad.startswith("/_seite/"):
                koerper = seiten[pfad.removeprefix("/_seite/")]
                start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"),
                                          ("Content-Length", str(len(koerper)))])
                return [koerper]
            return statisch(environ, start_response)

        server = make_server("127.0.0.1", PORT, wsgi, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        erzeugt: list[Path] = []
        try:
            for name in auswahl:
                _pfad, breite, hoehe, _rolle = BILDER[name]
                ziel = args.ziel / f"{name}.png"
                profil = Path(tmp) / f"edge-{name}"
                subprocess.run(
                    [edge, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={profil}",
                     f"--screenshot={ziel}", f"--window-size={breite},{hoehe}", f"http://127.0.0.1:{PORT}/_seite/{name}"],
                    check=True, capture_output=True, timeout=120)
                erzeugt.append(ziel)
                print(f"{ziel.name}: {breite} x {hoehe}")
        finally:
            server.shutdown()
            conn.close()
    return erzeugt


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    os._exit(0)  # offscreen-Qt aus tools/screenshots.py: kein sauberes Beenden nötig
