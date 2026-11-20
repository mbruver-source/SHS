"""
Web-Backend für die PostgreSQL/Podman-Variante des SHS-Prüfungsprogramms
(Mehrbenutzerzugriff am Prüfungstag) - siehe Fortschritt.md für den Architektur-
Hintergrund (Weg B: ein PostgreSQL-Schema je Termin) und db.py für die eigentliche
Datenschicht (init_db_postgres(), die Terminverwaltung ab erstelle_termin_postgres()
sowie den SQLite<->Postgres-Austausch ab exportiere_termin_nach_postgres()).

Umfang (mit dem Nutzer abgestimmt): NUR Ergebniseingabe. Termin anlegen,
Teilnehmerverwaltung, Zeitplan und PDF-Export bleiben Desktop-Aufgaben vor/nach dem
Prüfungstag. Das Veröffentlichen/Zurückholen selbst (Weiterreichen der SQLite-Termin-Datei
an/von PostgreSQL) kann seit Kurzem entweder über die Kommandozeile (`sync_termin.py`,
z. B. für Automatisierung/Skripte) ODER bequemer direkt über die Web-Oberfläche laufen
(`/admin/termine`, nur für Administratoren, siehe admin_termine() unten) - die
Termin-Datei wird dabei per Browser hochgeladen bzw. die aktualisierte Datei wieder
heruntergeladen, ohne dass der Administrator dafür psycopg2 installieren oder eine DSN von
Hand zusammensetzen müsste. Beide Wege rufen intern dieselben db.py-Funktionen auf
(exportiere_termin_nach_postgres()/importiere_ergebnisse_aus_postgres()).

Anmeldung: echte Benutzerkonten (Benutzername/Passwort, siehe db.py, Abschnitt
"Benutzerkonten der Web-Version") statt eines gemeinsamen Zugangscodes je Termin (frühere
V1, inzwischen abgelöst - auf ausdrücklichen Wunsch, um die Web-Version unabhängiger vom
"Windows-Team" nutzbar zu machen). Zwei Rollen (ebenfalls abgestimmt, keine feinere
Rechtevergabe):

  - Administrator: richtet sich beim allerersten Start selbst ein (siehe login() unten),
    kann danach weitere Konten anlegen/löschen (siehe /admin/benutzer).
  - Alle übrigen Konten: dürfen ausschließlich Ergebnisse eintragen.

Weil Konten global sind (nicht mehr an einen einzelnen Termin gebunden wie vorher der
Zugangscode), wählt jeder Nutzer nach dem Login zusätzlich aus, mit welchem gerade
veröffentlichten Termin er arbeiten möchte (siehe termin_waehlen() unten - wird
übersprungen, wenn genau ein Termin offen ist).

Deployment-Annahme (ebenfalls abgestimmt): läuft weiterhin NUR im lokalen Vereins-Netzwerk
am Prüfungstag, nicht öffentlich aus dem Internet erreichbar - deshalb bewusst kein
externes CSS/JS/Font-CDN in den Templates (könnte am Veranstaltungsort ohne Internetzugang
gar nicht geladen werden) und kein eigenes HTTPS/TLS in diesem Modul. Seit der
Desktop-Anbindung (API unter /api/, siehe Abschnitt "API für den Desktop" unten) ist HTTPS
aber Pflicht: compose.yaml schaltet einen Caddy-Proxy mit langlebigem, selbst signiertem
Zertifikat davor (siehe README_CONTAINER.md); das Session-Cookie trägt deshalb das
Secure-Flag (SHS_WEB_COOKIE_SECURE, Standard an).

Jede Anfrage bekommt ihre eigene, kurzlebige PostgreSQL-Verbindung (siehe
_postgres_verbindung()/_verbindung_schliessen() unten) statt einer global geteilten -
einfacher als ein Connection-Pool und unproblematisch bei der hier erwarteten
Nutzerzahl (eine Handvoll Richter an einem Prüfungstag), vermeidet aber auch, dass
sich `SET search_path` (siehe db._setze_termin_suchpfad) verschiedener gleichzeitiger
Anfragen in die Quere kommt.
"""

from __future__ import annotations

import io
import os
import secrets
import sqlite3
import tempfile
import time
import threading
from datetime import date, datetime, timedelta, timezone
from functools import wraps

from flask import Blueprint, Flask, abort, g, jsonify, redirect, render_template, request, send_file, session, url_for
from itsdangerous import BadSignature, URLSafeTimedSerializer
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

import db
from version import VERSION

app = Flask(__name__)
# Datumsanzeige TT.MM.JJJJ in den Templates (gespeichert wird JJJJ-MM-TT, siehe
# db.normalisiere_datum) - Marcos Wunsch 22.09., einheitlich mit Desktop und PDFs.
app.add_template_filter(db.datum_anzeige, "datum")


@app.context_processor
def _version_kontext():
    """Stellt die Versionsnummer allen Templates zur Verfügung (Fußzeile, siehe
    templates/base.html) - dieselbe Nummer wie in der Desktop-.exe (version.py wird von
    bump_version.py für beide zusammen erzeugt, siehe dortiger Kommentar und
    Containerfile), damit sich am Prüfungstag leicht erkennen lässt, ob Desktop- und
    Web-Version zusammenpassen."""
    return {"version": VERSION}


# --- CSRF-Schutz (QS-Review 19./20.09.: bisher komplett gefehlt) --------------------
#
# Ohne das könnte eine bösartige, in einem ANDEREN Browser-Tab geöffnete Seite über ein
# automatisch abgeschicktes Formular im Namen eines gerade angemeldeten Nutzers Aktionen
# auf DIESER Anwendung auslösen (z. B. einen Termin oder ein Benutzerkonto löschen) -
# allein weil der Browser das gültige Session-Cookie bei jedem Aufruf dieser Domain
# automatisch mitschickt, unabhängig davon, von welcher Seite aus der Aufruf kam. Ein
# Session-Cookie allein schützt davor NICHT.
#
# Bewusst als eigene, kleine before_request-Prüfung statt einer zusätzlichen
# Abhängigkeit wie Flask-WTF - das Projekt hält seine Web-Abhängigkeiten bewusst
# minimal (siehe requirements-web.txt) und braucht hier nur ein einfaches
# Token-in-Session/Token-im-Formular-Verfahren (das klassische "Synchronizer Token
# Pattern"), keine Formular-Bibliothek.


def _csrf_token() -> str:
    """Liefert das CSRF-Token der aktuellen Browser-Session, erzeugt bei Bedarf ein neues
    (einmal pro Session/Cookie, nicht pro Formular oder Anfrage) - wird über den
    Kontext-Prozessor unten allen Templates als Funktion `csrf_token()` bereitgestellt,
    damit jedes Formular es als verstecktes Feld mitschicken kann. Siehe _csrf_pruefen()
    für die Prüfung beim Empfang."""
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


@app.context_processor
def _csrf_kontext():
    return {"csrf_token": _csrf_token}


@app.before_request
def _csrf_pruefen():
    """Lehnt jede eingehende POST-Anfrage ohne exakt passendes CSRF-Token ab (siehe
    Abschnitts-Kommentar oben). Das Token liegt serverseitig in der (signierten, vom
    Browser selbst nicht lesbaren) Session - eine fremde Seite kennt es nicht und kann es
    deshalb auch nicht in einem automatisch abgeschickten Formular mitschicken, selbst
    wenn sie das Session-Cookie unfreiwillig mitsendet.

    secrets.compare_digest() statt '==' vergleicht in konstanter Zeit statt
    zeichenweise abzubrechen - dieselbe Vorsicht gegen Seitenkanal-Angriffe wie beim
    Passwortvergleich über werkzeug.security (siehe db.pruefe_login).

    Läuft als before_request VOR jeder einzelnen Ansicht, statt als Decorator an jeder
    POST-Route einzeln angebracht werden zu müssen - so kann keine künftige neue
    POST-Route versehentlich ungeprüft bleiben."""
    if request.method != "POST":
        return None
    # API für den Desktop (siehe Abschnitt "API für den Desktop" unten): dort zählt NIE ein
    # Cookie, sondern nur der Header "Authorization: Bearer <Token>" - ein Browser schickt
    # den nicht von selbst mit, ein CSRF-Angriff über eine fremde Seite ist dort also nicht
    # möglich. Die Ausnahme ist nur deshalb sicher, weil keine /api/-Route die Session
    # liest (Test: Cookie-Anmeldung allein ergibt dort 401).
    if request.path.startswith("/api/"):
        return None
    if request.path == "/ergebnisse" and session.get("benutzername"):
        # Die Ergebnistabelle schickt je Zeile mehrere Felder (siehe ergebnistabelle): ab etwa
        # 100 Teilnehmern überschritte sie Werkzeugs Standardgrenze von 1000 Formularfeldern.
        # Nur für angemeldete Nutzer: Eine nicht angemeldete Anfrage soll nicht mehr Daten
        # parsen lassen als die Standardgrenzen erlauben (das CSRF-Token wird erst danach geprüft).
        # Muss VOR dem ersten Zugriff auf request.form stehen (der Zugriff darunter parst).
        request.max_form_parts = _TABELLE_MAX_FORMULARFELDER
        request.max_form_memory_size = _TABELLE_MAX_FORMULARBYTES
    erwartet = session.get("csrf_token")
    erhalten = request.form.get("csrf_token", "")
    # Auf Bytes vergleichen (Codeprüfung 22.09.): compare_digest wirft bei str mit
    # Nicht-ASCII-Zeichen einen TypeError - ein manipuliertes Token hätte sonst einen 500
    # statt eines sauberen 403 ausgelöst.
    if not erwartet or not secrets.compare_digest(erwartet.encode("utf-8"), erhalten.encode("utf-8")):
        abort(403)


# Sicherheitsprüfung 03.10.2026, S-6: zentrale Schutz-Header für jede Antwort.
# - Content-Security-Policy: nur eigene Inhalte; 'unsafe-inline' für Styles, weil die
#   Templates eingebettete <style>-Blöcke und style-Attribute nutzen. Skripte gibt es
#   keine (script-src 'none'). frame-ancestors/X-Frame-Options verhindern das Einbetten
#   in fremde Seiten (Clickjacking).
# - Cache-Control no-store: Teilnehmer-/Ergebnisdaten nicht im Browser-Cache ablegen
#   (gemeinsam genutzte Vereinsrechner).
_SICHERHEITS_HEADER = {
    "Content-Security-Policy": (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'none'; "
        "img-src 'self' data:; object-src 'none'; base-uri 'none'; form-action 'self'; "
        "frame-ancestors 'none'"
    ),
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "Cache-Control": "no-store",
}


@app.after_request
def _sicherheits_header_setzen(antwort):
    for name, wert in _SICHERHEITS_HEADER.items():
        antwort.headers.setdefault(name, wert)
    return antwort


def geheimnis_lesen(name: str) -> str:
    """Liest ein Geheimnis aus der Datei in `<name>_FILE` (Docker-/Podman-Secret unter
    /run/secrets, siehe compose.yaml), sonst aus der Umgebungsvariablen `<name>`.
    Leerraum am Rand (z. B. der Zeilenumbruch am Dateiende) wird entfernt.

    Sicherheitshinweis H-3 (Marco 05.10.2026): Über Secrets stehen DB-Passwort,
    Signaturschlüssel und Einrichtungs-Code nicht mehr in der Container-Umgebung (sichtbar
    per `podman inspect`). Der Weg über die Umgebungsvariable bleibt für den Betrieb ohne
    Compose erhalten. Ist `<name>_FILE` gesetzt, die Datei aber nicht lesbar oder leer,
    bricht der Start mit einer verständlichen Meldung ab, statt still ohne Geheimnis
    weiterzulaufen (leer z. B., wenn der Befehl zum Erzeugen nichts ausgegeben hat - dann
    liefe die Web-Version sonst mit zufälligem Schlüssel und gesperrter Ersteinrichtung)."""
    pfad = os.environ.get(f"{name}_FILE", "").strip()
    if pfad:
        try:
            with open(pfad, encoding="utf-8") as datei:
                wert = datei.read().strip()
        except OSError as fehler:
            raise RuntimeError(
                f"Web-Version nicht gestartet: {name}_FILE verweist auf {pfad}, die Datei ist "
                f"nicht lesbar ({fehler.strerror}). Siehe README_CONTAINER.md, Abschnitt "
                "Geheimnisse."
            ) from None
        if not wert:
            raise RuntimeError(
                f"Web-Version nicht gestartet: Die Datei {pfad} ({name}_FILE) ist leer. Siehe "
                "README_CONTAINER.md, Abschnitt Geheimnisse."
            )
        return wert
    return os.environ.get(name, "").strip()


# Verbindungsstring zum gemeinsamen PostgreSQL-Server - siehe db.verbinde_postgres_server()
# für das Format. Bewusst über eine Umgebungsvariable statt hart im Code, analog zu
# SHS_TEST_POSTGRES_DSN in test_db.py. Das Passwort kann im DSN stehen oder getrennt über
# SHS_POSTGRES_PASSWORD(_FILE) kommen (H-3) - getrennt sind auch Sonderzeichen wie @ / :
# im Passwort kein Problem, die einen DSN-URL sonst zerlegen würden.
app.config["SHS_POSTGRES_DSN"] = os.environ.get("SHS_POSTGRES_DSN", "")
app.config["SHS_POSTGRES_PASSWORD"] = geheimnis_lesen("SHS_POSTGRES_PASSWORD")

# Signaturschlüssel für die Session-Cookies (Flask signiert damit, verschlüsselt aber
# NICHT den Cookie-Inhalt - dort landen Benutzername/Admin-Kennzeichen/Schema-Name, aber
# nie ein Passwort oder Passwort-Hash). Ohne gesetzte Umgebungsvariable wird bei jedem
# Programmstart ein neuer, zufälliger Schlüssel erzeugt - bequem zum Ausprobieren, hat
# aber zur Folge, dass sich alle angemeldeten Richter nach einem Neustart des
# Web-Servers erneut mit Benutzername/Passwort anmelden müssen. Für den echten Einsatz
# am Prüfungstag SHS_WEB_SECRET_KEY fest setzen (z.B. per
# `python -c "import secrets; print(secrets.token_hex(32))"` einmalig erzeugen).
# Sicherheitsprüfung 03.10.2026, S-2: Platzhalter aus .env.example bzw. zu kurze Werte
# werden abgelehnt - mit dem öffentlich bekannten Beispielschlüssel ließen sich Session-
# Cookies (auch eines Administrators) fälschen (Codex-Nachweis).
_MINDESTLAENGE_SCHLUESSEL = 32
_MINDESTLAENGE_EINRICHTUNGSCODE = 12


def pruefe_web_geheimnisse(schluessel: str, einrichtungscode: str) -> None:
    """Wirft RuntimeError mit verständlicher Anleitung, wenn SHS_WEB_SECRET_KEY bzw.
    SHS_ADMIN_SETUP_CODE noch Platzhalter oder zu kurz sind. Leere Werte sind erlaubt
    (Schlüssel: zufällig je Start; Einrichtungscode: Ersteinrichtung gesperrt)."""
    fehler = []
    if schluessel and (schluessel.startswith("bitte-hier") or len(schluessel) < _MINDESTLAENGE_SCHLUESSEL):
        fehler.append(
            f"SHS_WEB_SECRET_KEY ist ein Platzhalter oder kürzer als {_MINDESTLAENGE_SCHLUESSEL} Zeichen. "
            'Erzeugen mit: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    if einrichtungscode and (
        einrichtungscode.startswith("bitte-hier") or len(einrichtungscode) < _MINDESTLAENGE_EINRICHTUNGSCODE
    ):
        fehler.append(
            f"SHS_ADMIN_SETUP_CODE ist ein Platzhalter oder kürzer als {_MINDESTLAENGE_EINRICHTUNGSCODE} Zeichen. "
            'Erzeugen mit: python -c "import secrets; print(secrets.token_urlsafe(16))"'
        )
    if fehler:
        raise RuntimeError("Web-Version nicht gestartet (siehe secrets/ bzw. README_CONTAINER.md, Abschnitt Geheimnisse):\n- " + "\n- ".join(fehler))


_web_schluessel = geheimnis_lesen("SHS_WEB_SECRET_KEY")
pruefe_web_geheimnisse(_web_schluessel, geheimnis_lesen("SHS_ADMIN_SETUP_CODE"))
app.secret_key = _web_schluessel or secrets.token_hex(32)
del _web_schluessel

# Explizit gesetzt statt sich auf den Flask-Standard zu verlassen (QS-Review 19./20.09.):
# "Lax" schickt das Session-Cookie bei einer normalen Navigation zu dieser Seite (Link/
# Tippen der Adresse/Lesezeichen) weiterhin mit, aber NICHT bei einer von einer fremden
# Seite AUSGELÖSTEN Anfrage (z. B. einem automatisch abgeschickten Formular oder einem
# eingebetteten Bild/iframe) - zusätzlich zum CSRF-Token oben eine zweite, unabhängige
# Absicherungsebene, die auch dann noch greift, falls irgendeine künftige Route das
# Token einmal vergisst zu prüfen.
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


def _umgebung_ein(name: str, standard: bool) -> bool:
    """Liest einen Ein/Aus-Schalter aus der Umgebung ("0", "false", "nein", "aus" = aus)."""
    wert = os.environ.get(name, "").strip().lower()
    if not wert:
        return standard
    return wert not in ("0", "false", "nein", "aus", "no", "off")


# Secure-Flag des Session-Cookies (Desktop-Anbindung): die Web-Version läuft jetzt hinter
# dem HTTPS-Proxy aus compose.yaml, der Browser schickt das Cookie also nur noch über
# HTTPS. Standard an; SHS_WEB_COOKIE_SECURE=0 nur für einen Start OHNE Proxy über http
# (siehe __main__ unten - dort gilt für den Entwicklungsserver "aus"). HSTS wird bewusst
# NICHT gesetzt (selbst signiertes Zertifikat: ein HSTS-Eintrag ließe sich im Browser
# nicht mehr per Warnseite umgehen).
app.config["SESSION_COOKIE_SECURE"] = _umgebung_ein("SHS_WEB_COOKIE_SECURE", True)

# Codeprüfung 22.09., G8: maximale Gültigkeit eines Session-Cookies 12 Stunden statt des
# Flask-Standards von 31 Tagen. Hintergrund: das Session-Cookie ist rein clientseitig
# (signiert, siehe oben) - "Abmelden" (logout() unten) löscht es nur im Browser des
# Nutzers, eine zuvor abgegriffene/kopierte Cookie-Zeichenkette bliebe serverseitig bis
# zu ihrem Ablauf gültig. 12 Stunden decken einen kompletten Prüfungstag ab.
#
# Wirkt auch OHNE session.permanent (wird in dieser Anwendung nirgends gesetzt): Flask
# prüft beim Einlesen JEDES Session-Cookies dessen signierten Zeitstempel gegen
# max_age = PERMANENT_SESSION_LIFETIME (flask.sessions.SecureCookieSessionInterface.
# open_session -> itsdangerous URLSafeTimedSerializer.loads(max_age=...), am
# installierten Flask 3.1.3/itsdangerous 2.2.0 nachgeprüft) - ein älteres Cookie gilt
# dann als ungültig (SignatureExpired, Unterklasse von BadSignature) und die Anfrage
# läuft mit einer leeren Session weiter, also Weiterleitung zum Login. Der Browser
# selbst verwirft das nicht-permanente Cookie zusätzlich beim Schließen.
#
# Wichtig zur Einordnung: der Zeitstempel wird bei jeder Antwort erneuert, in der die
# Session verändert wurde - und _aktueller_benutzer_oder_redirect() unten schreibt bei
# jeder angemeldeten Anfrage session["ist_admin"] neu. Praktisch sind die 12 Stunden
# deshalb eine Grenze für INAKTIVITÄT (bzw. für das Alter eines abgegriffenen, danach
# nicht mehr benutzten Cookies), keine absolute Höchstdauer einer aktiv genutzten
# Anmeldung.
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)

# Codeprüfung 22.09., G1: Einrichtungs-Code für die einmalige Ersteinrichtung des ersten
# Administrators (siehe login() unten). Ohne ihn konnte bisher JEDER im Vereinsnetz, der
# die Seite vor dem Verein aufruft, den ersten Administrator anlegen und damit die
# gesamte Web-Version übernehmen. Anders als bei SHS_WEB_SECRET_KEY oben gibt es hier
# bewusst KEINEN zufällig erzeugten Ersatzwert: ein zufälliger Signaturschlüssel ist ohne
# Konfiguration genauso sicher (nur unbequemer, siehe dort), ein Einrichtungs-Code muss
# dagegen dem Einrichtenden bekannt sein - ein Zufallswert wäre also entweder unbenutzbar
# oder müsste irgendwo (Konsole/Container-Log) ausgegeben werden. Deshalb sicherer
# Standard: ist die Variable leer/nicht gesetzt, wird die Ersteinrichtung verweigert
# (mit Hinweis auf der Seite), auch beim lokalen Entwicklungsstart über app.run(). Im
# Container ist sie über die Secret-Datei Pflicht (fehlt sie, startet compose nicht; ist
# sie leer, bricht geheimnis_lesen ab). Über app.config (wie
# SHS_POSTGRES_DSN), damit die Tests sie gezielt setzen können.
app.config["SHS_ADMIN_SETUP_CODE"] = geheimnis_lesen("SHS_ADMIN_SETUP_CODE")


def _postgres_verbindung():
    """Liefert die PostgreSQL-Verbindung der aktuellen Anfrage (legt sie beim ersten
    Zugriff an) - siehe Modul-Docstring oben zur Begründung für eine Verbindung je
    Anfrage statt einer global geteilten."""
    if "postgres_conn" not in g:
        dsn = app.config["SHS_POSTGRES_DSN"]
        if not dsn:
            raise RuntimeError(
                "SHS_POSTGRES_DSN ist nicht gesetzt - siehe Modul-Docstring/README für die Einrichtung."
            )
        g.postgres_conn = db.verbinde_postgres_server(dsn, app.config.get("SHS_POSTGRES_PASSWORD") or None)
    return g.postgres_conn


@app.teardown_appcontext
def _verbindung_schliessen(exception=None):
    conn = g.pop("postgres_conn", None)
    if conn is not None:
        conn.close()


def _aktueller_benutzer_oder_redirect():
    """Re-validiert session["benutzername"] gegen den AKTUELLEN Datenbankstand
    (db.benutzer_stand()) statt der Session blind zu vertrauen - QS-Fund (21.09.): ohne
    das blieb die Session eines Nutzers bis zum Abmelden/Sitzungsablauf voll nutzbar
    (ggf. sogar mit Admin-Rechten), selbst wenn ein Administrator dessen Konto
    zwischenzeitlich gelöscht hatte. Von _login_erforderlich, _admin_erforderlich UND
    _termin_erforderlich unten gemeinsam genutzt statt die Prüfung dreimal zu
    duplizieren.

    Liefert (True, None), wenn die Anmeldung noch gültig ist - dabei wird
    session["ist_admin"] nebenbei aktualisiert, falls sich die Rolle des Kontos
    zwischenzeitlich geändert hat (z. B. Administrator degradiert). Liefert sonst
    (False, <Redirect zum Login>) und leert dabei die Session (session.clear())."""
    benutzername = session.get("benutzername")
    if not benutzername:
        return False, redirect(url_for("login"))
    konto = db.benutzer_stand(_postgres_verbindung(), benutzername)
    # Sicherheitsprüfung 03.10.2026, C-1: auch die Konto-Kennung muss passen - sonst
    # übernähme ein altes Cookie ein unter gleichem Namen neu angelegtes Konto.
    if konto is None or session.get("konto_kennung") != konto["kennung"]:
        session.clear()
        return False, redirect(url_for("login"))
    session["ist_admin"] = konto["ist_admin"]
    return True, None


def _login_erforderlich(view):
    """Decorator für alle Ansichten, die ein angemeldetes Benutzerkonto voraussetzen
    (egal ob Admin oder "nur Eintragen") - Gegenstück zum früheren, rein
    zugangscodebasierten _termin_erforderlich (siehe unten)."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        ok, antwort = _aktueller_benutzer_oder_redirect()
        if not ok:
            return antwort
        return view(*args, **kwargs)
    return wrapper


def _admin_erforderlich(view):
    """Decorator für die Benutzerverwaltung ('/admin/benutzer') - setzt zusätzlich zu
    _login_erforderlich voraus, dass das angemeldete Konto ein Administrator ist (siehe
    Entscheidung "zwei Rollen: Admin + Eintragen", db.py). Nicht-Admins bekommen 403 statt
    einer Weiterleitung zum Login, da sie ja bereits angemeldet sind.

    Räumt außerdem bei jedem Aufruf nebenbei abgelaufene Download-Tokens ab (siehe
    _bereinige_abgelaufene_downloads() weiter unten) - hier zentral statt in jeder
    einzelnen Admin-Ansicht, damit das nicht vom sorgfältigen Nachtragen bei künftigen
    neuen Admin-Routen abhängt."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        ok, antwort = _aktueller_benutzer_oder_redirect()
        if not ok:
            return antwort
        if not session.get("ist_admin"):
            abort(403)
        _bereinige_abgelaufene_downloads()
        return view(*args, **kwargs)
    return wrapper


def _termin_erforderlich(view):
    """Decorator für alle Ansichten, die zusätzlich zum Login (siehe _login_erforderlich)
    einen ausgewählten Termin voraussetzen (siehe termin_waehlen() unten) - wechselt die
    Verbindung vorab auf dessen Schema (siehe db.oeffne_termin_postgres()) und reicht conn
    als ersten Parameter durch, damit die Ansichten selbst ganz normal die
    db.py-Funktionen aufrufen können.

    QS-Fund (21.09.): löschte ein Administrator einen Termin, während ein anderer Nutzer
    noch mit dessen schema_name in der Session unterwegs war, scheiterte
    db.oeffne_termin_postgres() (Schema existiert nicht mehr) bisher mit einer
    unbehandelten Exception (rohe 500-Fehlerseite) statt einer sauberen Weiterleitung -
    deshalb jetzt in try/except, das die veraltete Session-Auswahl entfernt und zur
    Terminauswahl zurückschickt."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        ok, antwort = _aktueller_benutzer_oder_redirect()
        if not ok:
            return antwort
        schema_name = session.get("schema_name")
        if not schema_name:
            return redirect(url_for("termin_waehlen"))
        conn = _postgres_verbindung()
        try:
            db.oeffne_termin_postgres(conn, schema_name)
        except Exception:
            session.pop("schema_name", None)
            return redirect(url_for("termin_waehlen"))
        return view(conn, *args, **kwargs)
    return wrapper


@app.route("/", methods=["GET", "POST"])
def login():
    conn = _postgres_verbindung()
    fehler = None

    # Solange noch kein einziger Administrator existiert, ersetzt die einmalige
    # Ersteinrichtung den normalen Login (siehe db.gibt_es_admin/admin_einrichten sowie
    # Modul-Docstring oben) - danach nie wieder, auch nicht nach einem "Abmelden".
    if not db.gibt_es_admin(conn):
        # Codeprüfung 22.09., G1: ohne konfigurierten Einrichtungs-Code keine
        # Ersteinrichtung (siehe Kommentar bei app.config["SHS_ADMIN_SETUP_CODE"] oben) -
        # die Seite zeigt dann nur einen Hinweis statt des Formulars.
        erwarteter_code = app.config.get("SHS_ADMIN_SETUP_CODE") or ""
        if not erwarteter_code:
            return render_template("ersteinrichtung.html", fehler=None, code_nicht_konfiguriert=True)
        if request.method == "POST":
            benutzername = request.form.get("benutzername", "").strip()
            passwort = request.form.get("passwort", "")
            passwort_wiederholung = request.form.get("passwort_wiederholung", "")
            eingegebener_code = request.form.get("einrichtungs_code", "").strip()
            # compare_digest (konstante Laufzeit, siehe _csrf_pruefen oben) auf Bytes statt
            # auf str: mit str-Argumenten wirft es bei Nicht-ASCII-Zeichen (z. B. einem
            # "ä" im Code oder in der Eingabe) einen TypeError statt False zu liefern.
            if not secrets.compare_digest(eingegebener_code.encode("utf-8"), erwarteter_code.encode("utf-8")):
                fehler = "Der Einrichtungs-Code ist falsch (siehe secrets/admin_setup_code.txt)."
            else:
                fehler = _pruefe_benutzername_und_passwort(benutzername, passwort, passwort_wiederholung)
            if fehler is None:
                # False nur im seltenen Fall, dass zwischenzeitlich (z. B. zwei parallel
                # geöffnete Ersteinrichtungs-Formulare) bereits ein Administrator angelegt
                # wurde - dann ganz normal zum Login weiter, statt einen zweiten "ersten"
                # Administrator anzulegen (siehe db.admin_einrichten).
                if db.admin_einrichten(conn, benutzername, passwort):
                    konto = db.benutzer_stand(conn, benutzername)
                    session.clear()
                    session["benutzername"] = benutzername
                    session["ist_admin"] = True
                    session["konto_kennung"] = konto["kennung"] if konto else None
                    return redirect(url_for("termin_waehlen"))
                return redirect(url_for("login"))
        return render_template("ersteinrichtung.html", fehler=fehler, code_nicht_konfiguriert=False)

    # UX-Test Web 19.11.2026 (A2): Wer schon angemeldet ist, bekommt auf „/“ nicht wieder das
    # Anmeldeformular, sondern landet dort, wohin auch die Anmeldung führt (mit gewähltem Termin
    # die Teilnehmerliste, sonst „Termin wählen“). Eine veraltete Sitzung (Konto gelöscht) wird
    # dabei geleert, dann erscheint wie gewohnt das Formular.
    if request.method == "GET" and session.get("benutzername"):
        angemeldet, _ = _aktueller_benutzer_oder_redirect()
        if angemeldet:
            return redirect(url_for("teilnehmerliste" if session.get("schema_name") else "termin_waehlen"))

    if request.method == "POST":
        benutzername = request.form.get("benutzername", "")
        passwort = request.form.get("passwort", "")
        konto = db.pruefe_login(conn, benutzername, passwort)
        if konto:
            session.clear()
            session["benutzername"] = konto["benutzername"]
            session["ist_admin"] = konto["ist_admin"]
            session["konto_kennung"] = konto["kennung"]
            return redirect(url_for("termin_waehlen"))
        fehler = "Benutzername oder Passwort falsch. Bitte erneut versuchen."
    return render_template("login.html", fehler=fehler)


# S-6: Abmelden nur per POST (mit CSRF-Token, siehe _csrf_pruefen) - per GET hätte eine
# fremde Seite angemeldete Nutzer z. B. über ein eingebettetes Bild abmelden können.
@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# Lizenzseite (Marco 01.11.2026): MIT-Lizenz des Programms und Lizenzen der Fremdkomponenten,
# verlinkt in der Fußzeile jeder Seite (templates/base.html). Beide Dateien liegen neben
# app_web.py, im Container also unter /app (siehe Containerfile: COPY LICENSE, und
# THIRD_PARTY_LICENSES.txt erzeugt tools/drittlizenzen.py beim Bauen des Images). Als
# Modulvariablen, damit Tests sie umlenken können.
_PROGRAMMORDNER = os.path.dirname(os.path.abspath(__file__))
LIZENZ_DATEI = os.path.join(_PROGRAMMORDNER, "LICENSE")
DRITTLIZENZEN_DATEI = os.path.join(_PROGRAMMORDNER, "THIRD_PARTY_LICENSES.txt")


def _lizenztext_lesen(pfad: str, hinweis: str) -> str:
    """Liest eine Lizenzdatei; fehlt sie oder ist sie nicht lesbar, kommt der Hinweistext
    statt eines Fehlers 500 (z. B. beim Start aus dem Quellcode ohne Image-Build)."""
    try:
        with open(pfad, encoding="utf-8", errors="replace") as datei:
            return datei.read()
    except OSError:
        return hinweis


@app.route("/lizenzen")
def lizenzen():
    """Öffentlich wie die Anmeldeseite (kein _login_erforderlich): Die Lizenzen sollen auch
    ohne Konto einsehbar sein. Die Texte werden im Template automatisch maskiert."""
    return render_template(
        "lizenzen.html",
        lizenz=_lizenztext_lesen(
            LIZENZ_DATEI, "Die Lizenzdatei (LICENSE) fehlt in dieser Fassung."
        ),
        drittlizenzen=_lizenztext_lesen(
            DRITTLIZENZEN_DATEI,
            "Die Liste der Fremdkomponenten wird beim Bauen des Container-Images erzeugt und "
            "fehlt in dieser Fassung.",
        ),
    )


def _pruefe_benutzername_und_passwort(
    benutzername: str, passwort: str, passwort_wiederholung: str | None = None
) -> str | None:
    """Gemeinsame Formularvalidierung für Ersteinrichtung und Benutzerverwaltung (siehe
    login()/admin_benutzer_anlegen() unten). Liefert einen Fehlertext oder None."""
    if not benutzername:
        return "Bitte einen Benutzernamen eingeben."
    if len(passwort) < 8:
        return "Das Passwort muss mindestens 8 Zeichen lang sein."
    if passwort_wiederholung is not None and passwort != passwort_wiederholung:
        return "Die beiden Passwörter stimmen nicht überein."
    return None


@app.route("/termin-waehlen", methods=["GET", "POST"])
@_login_erforderlich
def termin_waehlen():
    """Auswahl, mit welchem gerade veröffentlichten Termin weitergearbeitet werden soll
    (siehe Modul-Docstring oben - Konten sind global, ein Termin-Schema entsteht dagegen
    weiterhin über sync_termin.py export). Bei genau einem offenen Termin wird die Auswahl
    automatisch übersprungen (bequem am Prüfungstag, wenn ohnehin nur eine Prüfung
    läuft)."""
    conn = _postgres_verbindung()
    # liste_termine_postgres() setzt den search_path selbst zuerst auf "public" zurück
    # (siehe dortiger Kommentar in db.py) - unabhängig davon, ob diese Verbindung vorher
    # schon per oeffne_termin_postgres() auf ein Termin-Schema gewechselt hatte.
    termine = db.liste_termine_postgres(conn)

    if request.method == "POST":
        schema_name = request.form.get("schema_name", "")
        if schema_name not in {t.schema_name for t in termine}:
            abort(400)
        session["schema_name"] = schema_name
        return redirect(url_for("teilnehmerliste"))

    if len(termine) == 1:
        session["schema_name"] = termine[0].schema_name
        return redirect(url_for("teilnehmerliste"))

    return render_template("termin_waehlen.html", termine=termine)


@app.route("/admin/benutzer", methods=["GET", "POST"])
@_admin_erforderlich
def admin_benutzer():
    conn = _postgres_verbindung()
    fehler = None
    if request.method == "POST":
        benutzername = request.form.get("benutzername", "").strip()
        passwort = request.form.get("passwort", "")
        passwort_wiederholung = request.form.get("passwort_wiederholung", "")
        rolle = request.form.get("rolle", "eintragen")
        fehler = _pruefe_benutzername_und_passwort(benutzername, passwort, passwort_wiederholung)
        # Groß-/Kleinschreibung ignorieren, wie beim Login (siehe db.pruefe_login) - sonst
        # könnten "Richter1" und "richter1" als zwei getrennte Konten angelegt werden,
        # obwohl der spätere Login beide als denselben Benutzernamen behandelt.
        if fehler is None and benutzername.lower() in {
            b["benutzername"].lower() for b in db.liste_benutzer(conn)
        }:
            fehler = f"Der Benutzername '{benutzername}' ist bereits vergeben."
        if fehler is None:
            try:
                db.benutzer_anlegen(conn, benutzername, passwort, ist_admin=(rolle == "admin"))
            except Exception:
                # Die Prüfung oben schließt eine doppelte Schreibweise im Normalfall
                # bereits aus, lässt aber (wie bei der Admin-Lösch-Race-Condition, siehe
                # db.benutzer_loeschen) ein kurzes Zeitfenster für zwei gleichzeitige
                # Anfragen offen - der zusätzliche Unique-Index auf LOWER(benutzername)
                # (db._WEB_BENUTZER_INDEX_BENUTZERNAME_LOWER) fängt genau diesen seltenen
                # Fall dann auf Datenbankebene ab. Statt eines rohen 500-Fehlers bekommt
                # der Admin dieselbe verständliche Meldung wie beim normalen Duplikat.
                conn.rollback()
                fehler = f"Der Benutzername '{benutzername}' ist bereits vergeben."
            else:
                return redirect(url_for("admin_benutzer", angelegt=benutzername))
    benutzer = db.liste_benutzer(conn)
    # UX-Test Web 19.11.2026 (B1): Bestätigung nach „Benutzer anlegen“. Nur für einen Namen, den
    # es wirklich gibt (keine beliebigen Texte über die Adresse).
    meldung = None
    angelegt = request.args.get("angelegt", "") if request.method == "GET" else ""
    gespeichert = {b["benutzername"].lower(): b["benutzername"] for b in benutzer}
    if angelegt and angelegt.lower() in gespeichert:
        meldung = f"Benutzer „{gespeichert[angelegt.lower()]}“ wurde angelegt."
    return render_template("admin_benutzer.html", benutzer=benutzer, fehler=fehler, meldung=meldung)


@app.route("/admin/benutzer/<benutzername>/loeschen", methods=["POST"])
@_admin_erforderlich
def admin_benutzer_loeschen(benutzername):
    conn = _postgres_verbindung()
    try:
        db.benutzer_loeschen(conn, benutzername)
    except ValueError:
        # Letzter verbleibender Administrator (siehe db.benutzer_loeschen) - ohne eigene
        # Fehleranzeige an dieser Stelle (kein Formular, nur ein Löschen-Knopf in
        # admin_benutzer.html): einfach zur Liste zurück, dort bleibt das Konto dann
        # sichtbar unverändert stehen.
        pass
    if benutzername == session.get("benutzername"):
        session.clear()
        return redirect(url_for("login"))
    return redirect(url_for("admin_benutzer"))


# --- Termin veröffentlichen/zurückholen über die Web-Oberfläche (Alternative zur
# Kommandozeile sync_termin.py, siehe Modul-Docstring oben) --------------------------
#
# Läuft komplett über Datei-Upload/-Download im Browser statt über einen direkten
# Dateizugriff des Containers auf den Termine-Ordner des Administrators (bewusst so
# entschieden: funktioniert dadurch unabhängig davon, ob der Container später auf
# demselben Rechner oder einem separaten Gerät im Vereinsnetz läuft - siehe "Noch offen"
# in Fortschritt.md zur noch offenen Laufzeitumgebung -, und braucht keine zusätzliche
# Volume-Mount-Konfiguration in compose.yaml).
#
# _ausstehende_downloads hält die nach "Ergebnisse zurückholen" aktualisierte
# Termin-Datei kurzzeitig serverseitig vor (Token -> temporärer Pfad + ursprünglicher
# Dateiname), damit sie auf der folgenden Bestätigungsseite (mit dem Übertragungsbericht)
# tatsächlich heruntergeladen werden kann, statt sie im selben Zug wie den Bericht in
# einer einzigen Antwort ausliefern zu müssen. Ein einfaches Prozess-Dict genügt dafür -
# `app_web.py` läuft als ein einzelner Container-Prozess (siehe Containerfile/waitress),
# nicht über mehrere Worker-Prozesse hinweg verteilt.
#
# QS-Fund (19./20.09.): klickt der Administrator den Download-Link NICHT an (Tab
# geschlossen, Seite verlassen, Browser abgestürzt o. Ä.), blieb der Eintrag hier für
# immer stehen UND - schlimmer - die temporäre .sqlite-Datei mit den personenbezogenen
# Teilnehmer-/Ergebnisdaten lag unbegrenzt lange auf der Festplatte des Containers, ohne
# dass sie je automatisch abgeräumt worden wäre. Jeder Eintrag trägt deshalb jetzt
# zusätzlich seinen Erstellungszeitpunkt; _bereinige_abgelaufene_downloads() löscht
# Einträge (samt Datei), die länger als _DOWNLOAD_TOKEN_GUELTIGKEIT_SEKUNDEN nicht
# abgeholt wurden.
_ausstehende_downloads: dict[str, tuple[str, str, float]] = {}

# Wie lange ein Download-Link gültig bleibt, bevor er (samt der zugehörigen temporären
# Datei) automatisch verworfen wird - großzügig genug, um dem Administrator Zeit für den
# Klick auf der Bestätigungsseite zu lassen, aber kurz genug, um personenbezogene Daten
# nicht unnötig lange auf der Festplatte des Containers liegen zu lassen.
_DOWNLOAD_TOKEN_GUELTIGKEIT_SEKUNDEN = 15 * 60


def _bereinige_abgelaufene_downloads() -> None:
    """Entfernt alle Einträge aus _ausstehende_downloads, die älter als
    _DOWNLOAD_TOKEN_GUELTIGKEIT_SEKUNDEN sind, und löscht dabei jeweils auch die
    zugehörige temporäre Datei von der Festplatte (siehe QS-Kommentar oben). Wird bei
    jedem Aufruf einer admin-geschützten Ansicht ausgeführt (siehe _admin_erforderlich
    unten) - so bleibt kein künftiger neuer Admin-Bereich versehentlich davon
    ausgenommen, und ein Administrator, der irgendetwas im Admin-Bereich tut, räumt dabei
    nebenbei auch verwaiste Downloads vorheriger Sitzungen mit auf."""
    jetzt = time.monotonic()
    abgelaufene_tokens = [
        token for token, (_, _, erstellt_um) in _ausstehende_downloads.items()
        if jetzt - erstellt_um > _DOWNLOAD_TOKEN_GUELTIGKEIT_SEKUNDEN
    ]
    for token in abgelaufene_tokens:
        temp_pfad, _, _ = _ausstehende_downloads.pop(token)
        try:
            os.remove(temp_pfad)
        except FileNotFoundError:
            # Wurde die Datei bereits anderweitig entfernt (sollte nicht vorkommen,
            # aber kein Grund, die Bereinigung der übrigen Einträge abzubrechen).
            pass


def _hochgeladene_termin_datei_speichern(datei) -> str:
    """Speichert eine per Formular hochgeladene .sqlite-Termin-Datei in eine temporäre
    Datei und liefert deren Pfad - der Aufrufer ist dafür verantwortlich, die Datei
    hinterher wieder zu löschen (os.remove), außer sie wird für einen Download in
    _ausstehende_downloads vorgemerkt."""
    fd, temp_pfad = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    try:
        datei.save(temp_pfad)
    except BaseException:
        # Schlägt das Speichern fehl (z. B. Platte voll), bleibt sonst eine leere
        # Temp-Datei liegen - der Aufrufer bekommt den Pfad ja nie zu sehen.
        try:
            os.remove(temp_pfad)
        except OSError:
            pass
        raise
    return temp_pfad


@app.route("/admin/termine")
@_admin_erforderlich
def admin_termine():
    conn = _postgres_verbindung()
    return render_template("admin_termine.html", termine=db.liste_termine_postgres(conn))


def _ungueltige_termin_datei_fehler(conn, termine=None):
    """Gemeinsame Fehler-Antwort für admin_termin_veroeffentlichen()/
    admin_termin_zurueckholen(), wenn eine hochgeladene .sqlite-Datei zwar die richtige
    Dateiendung hat, ihr Inhalt aber keine gültige SQLite-Datenbank ist (db.init_db()
    scheitert dann mit sqlite3.Error - QS-Fund 21.09.: führte vorher zu einer rohen
    500-Fehlerseite statt der sonst üblichen verständlichen Meldung)."""
    return render_template(
        "admin_termine.html",
        termine=termine if termine is not None else db.liste_termine_postgres(conn),
        fehler="Diese Datei ist keine gültige SHS-Termin-Datei.",
    )


def _dublette_hinweis_pruefen(conn, veranstaltung: dict | None) -> str | None:
    """Prüft VOR dem eigentlichen Export, ob unter den bereits veröffentlichten Terminen
    schon einer mit demselben Verein+Datum existiert (QS-Fund 21.09.: bisher legte jeder
    Klick auf "Veröffentlichen" einen neuen, unabhängigen Termin an, auch wenn Verein+
    Datum bereits als veröffentlichter Termin vorhanden waren). Blockiert das
    Veröffentlichen selbst NICHT (ein Administrator könnte z. B. bewusst einen zweiten,
    korrigierten Stand hochladen wollen) - liefert stattdessen nur einen nicht
    blockierenden Hinweistext für die Erfolgsseite, oder None, falls keine Dublette
    gefunden wurde."""
    if not veranstaltung or not veranstaltung.get("verein") or not veranstaltung.get("datum"):
        return None
    for bestehender in db.liste_termine_postgres(conn):
        if bestehender.verein == veranstaltung["verein"] and bestehender.datum == veranstaltung["datum"]:
            return (
                f"Hinweis: Es gibt bereits einen veröffentlichten Termin für "
                f"„{veranstaltung['verein']}“ am {db.datum_anzeige(veranstaltung['datum'])} "
                f"(Schema {bestehender.schema_name}) - bei Bedarf den alten selbst löschen."
            )
    return None


@app.route("/admin/termine/veroeffentlichen", methods=["POST"])
@_admin_erforderlich
def admin_termin_veroeffentlichen():
    conn = _postgres_verbindung()
    datei = request.files.get("sqlite_datei")
    fehler = None
    if not datei or not datei.filename:
        fehler = "Bitte eine .sqlite-Termin-Datei auswählen."
    elif not datei.filename.lower().endswith(".sqlite"):
        fehler = "Das ist keine .sqlite-Termin-Datei."

    if fehler:
        return render_template("admin_termine.html", termine=db.liste_termine_postgres(conn), fehler=fehler)

    temp_pfad = _hochgeladene_termin_datei_speichern(datei)
    try:
        try:
            sqlite_conn = db.init_db(temp_pfad)
        except sqlite3.Error:
            return _ungueltige_termin_datei_fehler(conn)
        try:
            dublette_hinweis = _dublette_hinweis_pruefen(conn, db.get_veranstaltung(sqlite_conn))
            termin = db.exportiere_termin_nach_postgres(sqlite_conn, conn)
        finally:
            sqlite_conn.close()
    finally:
        os.remove(temp_pfad)

    return render_template(
        "admin_termine.html", termine=db.liste_termine_postgres(conn),
        veroeffentlicht=termin, dublette_hinweis=dublette_hinweis,
    )


@app.route("/admin/termine/<schema_name>/zurueckholen", methods=["POST"])
@_admin_erforderlich
def admin_termin_zurueckholen(schema_name):
    conn = _postgres_verbindung()
    termine = db.liste_termine_postgres(conn)
    if schema_name not in {t.schema_name for t in termine}:
        abort(400)

    datei = request.files.get("sqlite_datei")
    fehler = None
    if not datei or not datei.filename:
        fehler = "Bitte dieselbe .sqlite-Termin-Datei hochladen, mit der der Termin veröffentlicht wurde."
    elif not datei.filename.lower().endswith(".sqlite"):
        fehler = "Das ist keine .sqlite-Termin-Datei."

    if fehler:
        return render_template("admin_termine.html", termine=termine, fehler=fehler)

    temp_pfad = _hochgeladene_termin_datei_speichern(datei)
    try:
        sqlite_conn = db.init_db(temp_pfad)
    except sqlite3.Error:
        # Wie beim Veröffentlichen (siehe _ungueltige_termin_datei_fehler oben) wird die
        # temporäre Datei bei einer ungültigen/beschädigten Upload-Datei sofort gelöscht -
        # es gibt hier ja keinen nachfolgenden Download-Klick, der sie noch bräuchte.
        os.remove(temp_pfad)
        return _ungueltige_termin_datei_fehler(conn, termine=termine)
    try:
        try:
            bericht = db.importiere_ergebnisse_aus_postgres(conn, schema_name, sqlite_conn)
        finally:
            sqlite_conn.close()
    except Exception:
        # Anders als beim Veröffentlichen (siehe oben) wird die temporäre Datei hier NUR
        # bei einem Fehler sofort gelöscht - im Erfolgsfall bleibt sie für den
        # nachfolgenden Download-Klick bestehen (siehe unten).
        os.remove(temp_pfad)
        raise

    # Die soeben aktualisierte Datei wird NICHT sofort mitgeschickt (die Antwort zeigt
    # stattdessen den Übertragungsbericht), sondern kurz für den nachfolgenden Download-
    # Klick vorgehalten - siehe Kommentar bei _ausstehende_downloads oben.
    token = secrets.token_urlsafe(16)
    download_name = secure_filename(datei.filename) or "termin.sqlite"
    _ausstehende_downloads[token] = (temp_pfad, download_name, time.monotonic())

    return render_template(
        "admin_termine.html", termine=db.liste_termine_postgres(conn),
        zurueckgeholt_bericht=bericht, zurueckgeholt_token=token, zurueckgeholt_name=download_name,
    )


@app.route("/admin/termine/download/<token>")
@_admin_erforderlich
def admin_termin_download(token):
    eintrag = _ausstehende_downloads.pop(token, None)
    if eintrag is None:
        abort(404)
    temp_pfad, download_name, _ = eintrag
    with open(temp_pfad, "rb") as f:
        daten = f.read()
    os.remove(temp_pfad)
    return send_file(io.BytesIO(daten), as_attachment=True, download_name=download_name)


@app.route("/admin/termine/<schema_name>/loeschen", methods=["POST"])
@_admin_erforderlich
def admin_termin_loeschen(schema_name):
    conn = _postgres_verbindung()
    # Codeprüfung 22.09., G7: wie bei admin_termin_zurueckholen nur Schemas zulassen, die
    # tatsächlich als Termin registriert sind - sonst reichte der Schema-Name aus der URL
    # (allein durch db._pruefe_schema_name auf das Namensmuster geprüft) ungefiltert bis
    # zum "DROP SCHEMA ... CASCADE" durch.
    if schema_name not in {t.schema_name for t in db.liste_termine_postgres(conn)}:
        abort(400)
    db.loesche_termin_postgres(conn, schema_name)
    # Falls der Administrator gerade selbst mit diesem (jetzt gelöschten) Termin arbeitet,
    # die Auswahl zurücksetzen - sonst würde der nächste Aufruf einer
    # "_termin_erforderlich"-Ansicht auf ein nicht mehr existierendes Schema treffen.
    if session.get("schema_name") == schema_name:
        session.pop("schema_name", None)
    return redirect(url_for("admin_termine"))


def _name_passt_zur_suche(teilnehmer: dict, suche: str) -> bool:
    """Suche nach Name oder Hund (Teilnehmerliste und Ergebnistabelle): jedes durch Leerzeichen
    getrennte Wort muss in Nachname, Vorname oder Hund vorkommen (Groß-/Kleinschreibung egal)."""
    woerter = suche.casefold().split()
    text = " ".join(
        str(teilnehmer[feld] or "") for feld in ("nachname", "vorname", "rufname_hund")
    ).casefold()
    return all(w in text for w in woerter)


@app.route("/teilnehmer")
@_termin_erforderlich
def teilnehmerliste(conn):
    veranstaltung = db.get_veranstaltung(conn)
    # "keine Teilnahme"-Teilnehmer (Nutzerwunsch 02.10.2026) werden schon beim
    # Veröffentlichen nicht übertragen - der Filter hier ist nur die Absicherung dafür.
    alle_teilnehmer = db.list_teilnehmer(conn, nur_teilnehmende=True)
    ergebnis_je_id = db.ergebnisse_je_teilnehmer(conn)
    zeilen = [
        {
            "teilnehmer": t,
            "label": db.leistungsklasse_label(t),
            "status": _listen_status(t, ergebnis_je_id.get(t["id"]) or {}),
            # UX-Test Web 19.11.2026 (A1): Links zum Online-Bewertungsbogen je Disziplin.
            "disziplinen": _disziplinen_von(t),
        }
        for t in alle_teilnehmer
    ]
    meldung = _meldung_nach_einzelseite(conn)
    # Marco 10.11.2026 (UI-Abgleich, wie im Desktop-Programm): Suche nach Name oder Hund. Ohne
    # JavaScript (die Sicherheitsrichtlinie erlaubt keine Skripte), deshalb als GET-Formular:
    # jedes Wort muss in Nachname, Vorname oder Hund vorkommen (Groß-/Kleinschreibung egal).
    suche = (request.args.get("q") or "").strip()[:80]
    if suche:
        zeilen = [z for z in zeilen if _name_passt_zur_suche(z["teilnehmer"], suche)]
    return render_template("teilnehmerliste.html", veranstaltung=veranstaltung, zeilen=zeilen,
                           suche=suche, gesamt=len(alle_teilnehmer), meldung=meldung)


def _listen_status(teilnehmer: dict, ergebnis: dict) -> dict:
    """Status eines Teilnehmers in der Teilnehmerliste (UX-Test Web 19.11.2026, B2, Marco: vier
    Stufen; vorher nur „offen“/„bewertet“, auch bei Disqualifikation und Abbruch). Liefert Text
    und Art (Name der CSS-Klasse status-<art>):
      - „disqualifiziert“ (dq) bzw. „Abbruch“ (abbruch) haben Vorrang,
      - „bewertet“ (fertig): alle Disziplinen mit Suche UND Anzeige,
      - „teilweise (n von m)“ (teilweise): ein Teil der Disziplinen (nur Dreikampf),
      - „offen“ (offen): noch keine Disziplin vollständig."""
    if ergebnis.get("disqualifiziert"):
        return {"text": "disqualifiziert", "art": "dq"}
    if ergebnis.get("abbruch"):
        return {"text": "Abbruch", "art": "abbruch"}
    disziplinen = _disziplinen_von(teilnehmer)
    fertig = sum(
        1 for d in disziplinen
        if all(ergebnis.get(spalte) is not None for spalte in db.DISZIPLIN_SPALTEN[d])
    )
    if fertig == len(disziplinen):
        return {"text": "bewertet", "art": "fertig"}
    if fertig:
        return {"text": f"teilweise ({fertig} von {len(disziplinen)})", "art": "teilweise"}
    return {"text": "offen", "art": "offen"}


def _meldung_nach_einzelseite(conn) -> str | None:
    """Bestätigung in der Teilnehmerliste nach dem Speichern auf der Einzelseite (UX-Test Web
    19.11.2026, B2: vorher kam man ohne jede Rückmeldung zurück zur Liste). Die Einzelseite leitet
    mit ?gespeichert=<id>&aenderung=0|1 hierher; unbekannte oder ungültige Werte zeigen nichts."""
    wert = request.args.get("gespeichert", "")
    if not (wert.isascii() and wert.isdigit()) or len(wert) > 9:  # riesige Zahlen: OverflowError in SQLite
        return None
    teilnehmer = db.get_teilnehmer(conn, int(wert))
    if teilnehmer is None or teilnehmer.get("keine_teilnahme"):
        return None
    name = f"{teilnehmer['nachname']}, {teilnehmer['vorname']}"
    if request.args.get("aenderung") == "0":
        return f"Keine Änderungen zu speichern ({name})."
    return f"Gespeichert: {name}."


def _feld_zu_text(formular, name: str) -> str:
    return (formular.get(name) or "").strip()


def _disziplin_text_werte(formular, disziplin: str) -> tuple[str, str]:
    """Rohe (nicht geparste) Formulartexte einer Disziplin - gemeinsame Grundlage sowohl
    für die Validierung (_pruefe_und_parse_formular) als auch für den
    Lost-Update-Vergleich (siehe _geladene_werte_aus_formular/ergebnis_erfassen)."""
    return _feld_zu_text(formular, f"suche_{disziplin}"), _feld_zu_text(formular, f"anzeige_{disziplin}")


def _disziplin_unveraendert(formular, disziplin: str, geladene_werte: dict) -> bool:
    """True, wenn der Richter diese Disziplin seit dem Laden der Seite NICHT verändert hat
    (abgeschickter Text == versteckter "geladen_*"-Text) - Grundlage sowohl für den
    Lost-Update-Schutz beim Speichern (siehe ergebnis_erfassen) als auch für die
    Vollständigkeitsprüfung in _pruefe_und_parse_formular. Fehlt ein "geladen_*"-Feld,
    gilt die Disziplin als verändert (siehe _feld_roh)."""
    geladen = geladene_werte[disziplin]
    return None not in geladen and _disziplin_text_werte(formular, disziplin) == geladen


def _pruefe_und_parse_formular(
    formular, disziplinen: list[str], geladene_werte: dict | None = None
) -> tuple[dict, str | None]:
    """Parst und validiert die Formularfelder einer Ergebniserfassung. Liefert
    (Werte je Disziplin als {disziplin: (suche, anzeige)}, Fehlertext oder None).

    Codeprüfung 22.09., G6: zusätzlich die gemeinsame Regel "Suche UND Anzeige oder
    keins von beiden" (db.pruefe_ergebnis_eingabe, dieselbe wie in der Desktop-Version) -
    bisher speicherte das Web eine halb ausgefüllte Disziplin klaglos. Geprüft werden
    dabei NUR vom Richter veränderte Disziplinen (siehe _disziplin_unveraendert, dafür
    geladene_werte aus _geladene_werte_aus_formular): eine unveränderte Disziplin wird
    ohnehin nicht gespeichert (Lost-Update-Schutz), und ein bereits halb gespeicherter
    Altbestand (z. B. aus der Zeit vor dieser Prüfung) darf das Speichern der ANDEREN
    Disziplinen desselben Dreikampf-Teilnehmers nicht blockieren. Ohne geladene_werte
    (None) werden alle Disziplinen geprüft.

    Die Wertebereiche (0-60 Suchleistung, 0-40 Anzeigeleistung) werden hier bewusst
    VOR dem Speichern geprüft, nicht erst über die CHECK-Constraints der Datenbank
    abgefangen - eine fehlgeschlagene Anweisung würde bei PostgreSQL sonst die laufende
    Transaktion in einen Fehlerzustand versetzen (erst durch ROLLBACK wieder nutzbar).
    Da hier ohnehin für jede Anfrage eine frische Verbindung verwendet wird (siehe
    _postgres_verbindung) und der _PostgresConnection-Wrapper in db.py rollback()
    anbietet, wäre das zwar unkritisch, sauberer und mit besserer Fehlermeldung für die
    Richter ist aber, das erst gar nicht so weit kommen zu lassen."""
    werte: dict[str, tuple[int | None, int | None]] = {}
    for disziplin in disziplinen:
        suche_text, anzeige_text = _disziplin_text_werte(formular, disziplin)
        try:
            suche = int(suche_text) if suche_text else None
            anzeige = int(anzeige_text) if anzeige_text else None
        except ValueError:
            return {}, f"Bitte bei {disziplin} nur Zahlen eintragen."
        if suche is not None and not (0 <= suche <= db.SUCHE_MAX):
            return {}, f"Suchleistung {disziplin}: nur Werte von 0 bis {db.SUCHE_MAX} möglich."
        if anzeige is not None and not (0 <= anzeige <= db.ANZEIGE_MAX):
            return {}, f"Anzeigeleistung {disziplin}: nur Werte von 0 bis {db.ANZEIGE_MAX} möglich."
        if geladene_werte is None or not _disziplin_unveraendert(formular, disziplin, geladene_werte):
            unvollstaendig = db.pruefe_ergebnis_eingabe(suche, anzeige)
            if unvollstaendig is not None:
                return {}, f"{disziplin}: {unvollstaendig}"
        werte[disziplin] = (suche, anzeige)
    return werte, None


def _feld_roh(formular, name: str) -> str | None:
    """Wie _feld_zu_text, liefert aber None statt einer leeren Zeichenkette, wenn das
    Feld im Formular komplett FEHLT (nicht bloß leer ist) - wichtig für den
    Lost-Update-Vergleich in _geladene_werte_aus_formular unten: ein fehlendes
    "geladen_*"-Feld bedeutet "keine Information über den ursprünglich geladenen Stand
    vorhanden" und muss deshalb IMMER als "verändert" (also: speichern) behandelt werden
    - sicherer Standard, lieber einmal zu viel speichern als eine echte Eingabe
    stillschweigend verwerfen."""
    wert = formular.get(name)
    return None if wert is None else wert.strip()


def _geladene_werte_aus_formular(formular, disziplinen: list[str]) -> dict[str, tuple[str | None, str | None]]:
    """Liest die beim Laden der Seite (GET, siehe ergebnis_erfassen/_zeilen_aus_ergebnis)
    in versteckten Formularfeldern ("geladen_suche_<disziplin>"/"geladen_anzeige_
    <disziplin>", siehe templates/ergebnis_erfassen.html) mitgeschickten Werte je
    Disziplin aus - der zu diesem Zeitpunkt sichtbare DB-Stand. Dient als
    Vergleichsbasis gegen die gerade abgeschickten Formularwerte, um einen "Lost Update"
    bei gleichzeitiger Bearbeitung verschiedener Disziplinen desselben
    Dreikampf-Teilnehmers durch zwei Richter zu vermeiden (QS-Fund 21.09., siehe
    ergebnis_erfassen: ohne das überschrieb ein Richter beim Speichern IMMER alle drei
    Disziplinen mit dem bei ihm noch alten Stand, auch die von einem anderen Richter
    zwischenzeitlich geänderte)."""
    return {
        disziplin: (_feld_roh(formular, f"geladen_suche_{disziplin}"), _feld_roh(formular, f"geladen_anzeige_{disziplin}"))
        for disziplin in disziplinen
    }


def _wert_zu_text(wert: int | None) -> str:
    return "" if wert is None else str(wert)


def _zeilen_aus_ergebnis(ergebnis: dict, disziplinen: list[str]) -> list[dict]:
    """Baut die Zeilen fürs Formular-Template beim erstmaligen Laden der Seite (GET) aus
    dem aktuellen DB-Stand auf - "suche"/"anzeige" (für die sichtbaren Eingabefelder)
    und "geladen_suche"/"geladen_anzeige" (für die versteckten Vergleichsfelder, siehe
    _geladene_werte_aus_formular) sind hier bewusst identisch: der "geladene" Stand ist
    genau der, der beim GET sichtbar war."""
    zeilen = []
    for disziplin in disziplinen:
        spalte_suche, spalte_anzeige = db.DISZIPLIN_SPALTEN[disziplin]
        suche_text = _wert_zu_text(ergebnis.get(spalte_suche))
        anzeige_text = _wert_zu_text(ergebnis.get(spalte_anzeige))
        zeilen.append({
            "disziplin": disziplin,
            "suche": suche_text, "anzeige": anzeige_text,
            "geladen_suche": suche_text, "geladen_anzeige": anzeige_text,
        })
    return zeilen


def _zeilen_aus_formular(formular, disziplinen: list[str]) -> list[dict]:
    """Baut die Zeilen fürs Formular-Template nach einem Validierungsfehler (POST) aus
    den GERADE ABGESCHICKTEN Werten auf, NICHT aus dem (ggf. davon abweichenden)
    DB-Stand - QS-Fund 21.09.: sonst gingen bei einem Fehler in einer Disziplin (z. B.
    Wert außerhalb 0-60) auch die korrekt eingegebenen Werte der übrigen Disziplinen
    derselben Absendung verloren. Die "geladen_*"-Felder werden dabei UNVERÄNDERT aus
    dem Formular übernommen (sie stammen aus dem ursprünglichen GET-Aufruf und müssen für
    den Lost-Update-Vergleich beim nächsten Speicherversuch weiterhin den ECHTEN
    ursprünglichen DB-Stand widerspiegeln, nicht die fehlerhafte Zwischeneingabe - siehe
    ergebnis_erfassen)."""
    geladene_werte = _geladene_werte_aus_formular(formular, disziplinen)
    zeilen = []
    for disziplin in disziplinen:
        suche_text, anzeige_text = _disziplin_text_werte(formular, disziplin)
        geladen_suche, geladen_anzeige = geladene_werte[disziplin]
        zeilen.append({
            "disziplin": disziplin,
            "suche": suche_text, "anzeige": anzeige_text,
            "geladen_suche": "" if geladen_suche is None else geladen_suche,
            "geladen_anzeige": "" if geladen_anzeige is None else geladen_anzeige,
        })
    return zeilen


@app.route("/teilnehmer/<int:teilnehmer_id>", methods=["GET", "POST"])
@_termin_erforderlich
def ergebnis_erfassen(conn, teilnehmer_id):
    """GET zeigt die Erfassungsseite (vorbelegt mit dem aktuellen DB-Stand), POST
    speichert. Die Seite trägt je Disziplin zusätzlich versteckte "geladen_*"-Felder mit
    dem beim GET sichtbaren Stand (siehe _zeilen_aus_ergebnis/
    templates/ergebnis_erfassen.html) - Grundlage für den Lost-Update-Schutz unten.

    QS-Fund 21.09.: bei einem Dreikampf-Teilnehmer wurden bisher IMMER alle drei
    Disziplinen gemeinsam gespeichert, basierend auf dem beim Laden der Seite sichtbaren
    Stand. Bearbeiteten zwei Richter gleichzeitig verschiedene Disziplinen desselben
    Hundes (am Prüfungstag normal), überschrieb der später speichernde Richter die
    zwischenzeitliche Eintragung des anderen mit dem bei ihm noch alten Wert -
    stillschweigend, ohne Warnung. Deshalb wird beim Speichern jetzt je Disziplin
    verglichen: submitted Wert == geladener (versteckter Feld-)Wert? Wenn ja, wurde diese
    Disziplin vom aktuellen Richter gar nicht bearbeitet - dann wird NICHTS geschrieben,
    damit eine zwischenzeitliche fremde Änderung nicht überschrieben wird. Wenn nein
    (Richter hat diese Disziplin tatsächlich bearbeitet), wird wie bisher gespeichert.

    Seit 19.11.2026 (UX-Test Web, D1) auch Disqualifiziert und Abbruch mit Grund, mit denselben
    Hilfen wie die Ergebnistabelle (_abbruch_fehler, _punkte_gesperrt, _status_einheit_schreiben,
    _extern_gesperrt): Konflikte beim Status oder Punkte in einer inzwischen fremd gesperrten Zeile
    werden nicht geschrieben, die Seite zeigt dann Hinweis und aktuellen Stand."""
    teilnehmer = db.get_teilnehmer(conn, teilnehmer_id)
    if teilnehmer is None or teilnehmer.get("keine_teilnahme"):
        abort(404)
    disziplinen = [teilnehmer["disziplin"]] if teilnehmer["art"] == "ED" else db.ALLE_DISZIPLINEN

    fehler = None
    konflikt = None
    meldung = None
    status_formular = None  # abgeschickter Status (dq, abbruch, geladen) bei Neuaufbau, sonst None
    if request.method == "POST":
        form = request.form
        # UX-Test Web 19.11.2026 (D1, B18 überholt): Disqualifiziert und Abbruch auch hier. Ein
        # Formular ohne das versteckte Feld geladen_status (ältere Seite, Skript) lässt den Status
        # unberührt.
        status = _einzelseite_status_lesen(form)
        if status is not None:
            fehler = _abbruch_fehler(status["abbruch"], status["geladen"][1] if status["geladen"] else None)
        gesperrt = status is not None and _punkte_gesperrt(status["dq"], status["abbruch"])
        geladene_werte = _geladene_werte_aus_formular(form, disziplinen)
        werte = {}
        if fehler is None and not gesperrt:  # gesperrt: Punkte ignoriert (wie in der Tabelle)
            werte, fehler = _pruefe_und_parse_formular(form, disziplinen, geladene_werte)
        if fehler is None:
            geschrieben = False
            konflikt_texte = []
            extern_gesperrt = False
            if status is not None:
                aktuell_ergebnis = db.get_ergebnis(conn, teilnehmer_id) or {}
                status_geschrieben, status_konflikt = _status_einheit_schreiben(
                    conn, teilnehmer_id, (status["dq"], status["abbruch"]), status["geladen"], aktuell_ergebnis)
                geschrieben = geschrieben or status_geschrieben
                if status_konflikt:
                    konflikt_texte.append(status_konflikt)
                extern_gesperrt = _extern_gesperrt(
                    status["geladen"], (bool(aktuell_ergebnis.get("disqualifiziert")), _abbruch_code(aktuell_ergebnis)))
            for disziplin, (suche, anzeige) in werte.items():
                if _disziplin_unveraendert(form, disziplin, geladene_werte):
                    # Diese Disziplin wurde vom aktuellen Richter nicht verändert - siehe
                    # Funktionsdocstring (Lost-Update-Schutz).
                    continue
                if extern_gesperrt:
                    # Wie in der Tabelle: jemand anderes hat inzwischen gesperrt, die Punkte aus dem
                    # alten Stand werden nicht geschrieben (steht der Wert schon so da: keine Meldung).
                    aktuell_jetzt = db.get_ergebnis(conn, teilnehmer_id) or {}
                    spalte_suche, spalte_anzeige = db.DISZIPLIN_SPALTEN[disziplin]
                    if (suche, anzeige) != (aktuell_jetzt.get(spalte_suche), aktuell_jetzt.get(spalte_anzeige)):
                        aktuell = _ergebnis_zustand(teilnehmer, aktuell_jetzt)
                        konflikt_texte.append(
                            _punkte_konflikt_text(disziplin, suche, anzeige, aktuell["punkte"][disziplin]))
                    continue
                db.eintragen_ergebnis(conn, teilnehmer_id, disziplin, suche, anzeige)
                _aenderung_merken(conn, teilnehmer_id, disziplin)
                geschrieben = True
            if not konflikt_texte:
                # UX-Test Web 19.11.2026 (A1): „Bewertungsbogen … öffnen“ speichert zuerst die
                # Eingaben dieser Seite (sonst gingen sie verloren) und öffnet dann den Bogen.
                bogen = form.get("bogen")
                if bogen in disziplinen:
                    return redirect(url_for("bewertungsbogen", teilnehmer_id=teilnehmer_id, disziplin=bogen,
                                            von="teilnehmer"))
                return redirect(url_for("teilnehmerliste", gespeichert=teilnehmer_id, aenderung=int(geschrieben)))
            # Konflikt: Seite mit dem aktuellen Stand und dem Hinweis zeigen.
            konflikt = konflikt_texte
            if geschrieben:
                meldung = "Die übrigen Eingaben wurden gespeichert."
            zeilen = _zeilen_aus_ergebnis(db.get_ergebnis(conn, teilnehmer_id) or {}, disziplinen)
        else:
            # Fehlerfall: Seite mit den gerade abgeschickten (nicht den gespeicherten) Werten
            # neu aufbauen, siehe _zeilen_aus_formular.
            zeilen = _zeilen_aus_formular(form, disziplinen)
            status_formular = status
    else:
        zeilen = _zeilen_aus_ergebnis(db.get_ergebnis(conn, teilnehmer_id) or {}, disziplinen)

    ergebnis = db.get_ergebnis(conn, teilnehmer_id) or {}
    gespeicherter_abbruch = _abbruch_code(ergebnis)
    if status_formular is not None:
        dq, abbruch, geladen_status = status_formular["dq"], status_formular["abbruch"], status_formular["geladen_roh"]
    else:
        dq, abbruch = bool(ergebnis.get("disqualifiziert")), gespeicherter_abbruch
        geladen_status = _einzelseite_status_text(dq, abbruch)

    return render_template(
        "ergebnis_erfassen.html",
        # Kopfbalken mit Verein, Datum und Ort wie in der Teilnehmerliste (Erscheinungsbild
        # „Beagle“, Marco 01.11.2026) - die Seite, auf der die Richter am Tablet arbeiten.
        veranstaltung=db.get_veranstaltung(conn),
        teilnehmer=teilnehmer,
        label=db.leistungsklasse_label(teilnehmer),
        zeilen=zeilen,
        fehler=fehler,
        konflikt=konflikt,
        meldung=meldung,
        dq=dq,
        abbruch=abbruch,
        geladen_status=geladen_status,
        abbruch_gruende=[(code, text[0]) for code, text in db.ABBRUCH_GRUENDE.items()],
        # „ohne Grund“ gibt es nur als Altdatum und wird nur dann angeboten (wie in der Tabelle).
        abbruch_ohne_grund=_ABBRUCH_OHNE_GRUND in (abbruch, gespeicherter_abbruch),
        gesperrt=_punkte_gesperrt(dq, abbruch),
        status_text=_tabellen_status_text(ergebnis),
        suche_max=db.SUCHE_MAX,
        anzeige_max=db.ANZEIGE_MAX,
    )


# --- Disqualifiziert/Abbruch auf der Seite je Teilnehmer ---------------------------------
#
# UX-Test Web 19.11.2026 (D1, Marco: B18 überholt). Gleiche Regeln wie in der Ergebnistabelle
# (gemeinsame Hilfen unten): ein Abbruch braucht einen Grund („ohne Grund“ nur als Altdatum),
# Disqualifiziert oder Abbruch ohne Grund sperren die Punkte (der Server ignoriert sie), und der
# Status ist eine eigene Einheit mit Lost-Update-Schutz (_einheit_entscheiden). Der beim Laden
# sichtbare Stand steht im versteckten Feld geladen_status („0|“, „1|krankheit“ ...).

def _einzelseite_status_text(dq: bool, abbruch: str) -> str:
    return f"{'1' if dq else '0'}|{abbruch}"


def _einzelseite_status_lesen(formular) -> dict | None:
    """Abgeschickter Status der Einzelseite oder None, wenn das Formular keinen Status trägt
    (kein Feld geladen_status). geladen ist None, wenn das Feld kaputt ist (dann gilt der Status
    als verändert, wie _geladen_lesen)."""
    roh = _feld_roh(formular, "geladen_status")
    if roh is None:
        return None
    geladen = None
    dq_geladen, trenner, abbruch_geladen = roh.partition("|")
    if trenner and dq_geladen in ("0", "1") and (
            not abbruch_geladen or abbruch_geladen == _ABBRUCH_OHNE_GRUND or abbruch_geladen in db.ABBRUCH_GRUENDE):
        geladen = (dq_geladen == "1", abbruch_geladen)
    return {"dq": _feld_zu_text(formular, "dq") == "1", "abbruch": _feld_zu_text(formular, "abbruch"),
            "geladen": geladen, "geladen_roh": roh}


# Gemeinsame Regeln für Disqualifiziert/Abbruch: Ergebnistabelle (_tabelle_pruefen/
# _tabelle_schreiben, auch für den Online-Bogen) und Einzelseite (ergebnis_erfassen) nutzen
# dieselben Hilfen. Ein Status ist ein Paar (Disqualifiziert, Abbruchcode).

def _punkte_gesperrt(dq: bool, abbruch: str) -> bool:
    """Disqualifiziert oder Abbruch ohne Grund sperren die Punkte (der Server ignoriert sie)."""
    return dq or abbruch == _ABBRUCH_OHNE_GRUND


def _abbruch_fehler(abbruch: str, geladen_abbruch: str | None) -> str | None:
    """Ein Abbruch braucht einen bekannten Grund; „ohne Grund“ nur, wenn es schon so geladen war
    (Altdatum). geladen_abbruch None: geladener Stand unbekannt."""
    if abbruch and abbruch != _ABBRUCH_OHNE_GRUND and abbruch not in db.ABBRUCH_GRUENDE:
        return "Unbekannter Abbruchgrund."
    if abbruch == _ABBRUCH_OHNE_GRUND and geladen_abbruch != _ABBRUCH_OHNE_GRUND:
        return "Ein Abbruch braucht einen Grund - bitte einen Grund wählen."
    return None


def _aenderung_merken(conn, teilnehmer_id: int, bereich: str, commit: bool = True) -> None:
    """Merkt das angemeldete Web-Konto und den Zeitpunkt einer Änderung (UX-Test Web 19.11.2026, B6;
    Anzeige nur für Admins in der Ergebnistabelle). Nach dem eigentlichen Schreiben aufrufen, mit
    demselben `commit` (beim Sammelspeichern ganz oder gar nicht)."""
    db.aenderung_merken(conn, teilnehmer_id, bereich, session.get("benutzername") or "?", commit=commit)


def _status_einheit_schreiben(conn, teilnehmer_id: int, neu: tuple, geladen: tuple | None, ergebnis: dict,
                              commit: bool = True) -> tuple[bool, str | None]:
    """Schreibt den Status als eigene Einheit mit Lost-Update-Schutz (_einheit_entscheiden).
    `ergebnis` ist der aktuelle DB-Stand. Liefert (geschrieben, Konflikttext)."""
    aktuell = (bool(ergebnis.get("disqualifiziert")), _abbruch_code(ergebnis))
    entscheidung = _einheit_entscheiden(
        unveraendert=geladen is not None and neu == geladen,
        schon_gleich=neu == aktuell,
        geladen_bekannt=geladen is not None,
        aktuell_wie_geladen=geladen is not None and aktuell == geladen,
    )
    if entscheidung == "schreiben":
        dq, abbruch = neu
        db.setze_ergebnis_status(conn, teilnehmer_id, dq, bool(abbruch),
                                 abbruch_grund=abbruch if abbruch in db.ABBRUCH_GRUENDE else None, commit=commit)
        _aenderung_merken(conn, teilnehmer_id, db._BEREICH_STATUS, commit=commit)
        return True, None
    if entscheidung == "konflikt":
        return False, ("Disqualifiziert/Abbruch wurde inzwischen von jemand anderem geändert "
                       f"(aktuell: {_tabellen_status_text(ergebnis)}) - Ihre Änderung wurde nicht gespeichert.")
    return False, None


def _extern_gesperrt(geladen: tuple | None, aktuell: tuple) -> bool:
    """Hat jemand anderes die Zeile seit dem Laden gesperrt (Disqualifiziert/Abbruch ohne Grund),
    sind Punkte aus dem alten Stand hinfällig (wie im Desktop: Eingaben verworfen)."""
    return geladen is not None and _punkte_gesperrt(*aktuell) and not _punkte_gesperrt(*geladen)


def _punkte_konflikt_text(disziplin: str, suche, anzeige, aktuelle_texte: tuple) -> str:
    ihre = f"{_wert_zu_text(suche) or '–'}/{_wert_zu_text(anzeige) or '–'}"
    jetzt = f"{aktuelle_texte[0] or '–'}/{aktuelle_texte[1] or '–'}"
    return (f"{disziplin} wurde inzwischen von jemand anderem geändert (aktuell Suche/Anzeige: {jetzt}) - "
            f"Ihre Eingabe {ihre} wurde nicht gespeichert.")


# --- Ergebnistabelle (/ergebnisse) -----------------------------------------------------
#
# Marco 18.11.2026: die Ergebniserfassung als Tabelle wie im Desktop-Reiter „Ergebniserfassung“
# (desktop_ergebnis.py), zusätzlich zur Erfassung je Teilnehmer (/teilnehmer/<id>). Eine Zeile je
# teilnehmenden Teilnehmer, je Disziplin Suche und Anzeige, dazu „Disqualifiziert“, „Abbruch“
# (Grund aus db.ABBRUCH_GRUENDE) und der Status. Reine Formulartabelle ohne JavaScript (CSP
# script-src 'none'): alles prüft der Server.
#
# Speichern (POST, ein Formular, „Alle speichern“):
#   - Es werden nur die Zeilen gespeichert, die im Formular stehen (also die sichtbaren: der
#     Filter ist ein GET-Formular, die Filterwerte hängen an der Adresse des Speicher-Formulars).
#   - Gemeinsame Regeln mit der Einzelseite: _pruefe_und_parse_formular (Zahlen, 0-60/0-40,
#     Suche UND Anzeige), über _ZeilenFormular für die Feldnamen einer Zeile.
#   - Validierungsfehler in IRGENDEINER Zeile: es wird NICHTS gespeichert, die Seite wird aus den
#     abgeschickten Werten neu aufgebaut (alle Eingaben bleiben), die Fehler stehen an der Zeile.
#   - Lost-Update-Schutz je Zeile und Einheit (Punkte einer Disziplin, Status Disqualifiziert/
#     Abbruch): jede Zeile trägt ein verstecktes Feld geladen_<id> mit dem beim Laden sichtbaren
#     Stand. Unveränderte Einheiten werden nicht geschrieben. Eine geänderte Einheit, deren DB-
#     Stand inzwischen vom geladenen abweicht (anderer Richter), wird NICHT überschrieben: die
#     Zeile erscheint mit dem Hinweis „inzwischen von jemand anderem geändert“ und dem aktuellen
#     Wert; die übrigen Einheiten und Zeilen sind gespeichert (die Meldung nennt beides).
#   - Disqualifiziert oder Abbruch ohne Grund sperren die Punkte der Zeile: der Server ignoriert
#     sie (die gespeicherten Punkte bleiben unangetastet). Ein Abbruch braucht einen Grund.

_TABELLE_MAX_FORMULARFELDER = 10000
_TABELLE_MAX_FORMULARBYTES = 4 * 1024 * 1024
_TABELLE_SAMMELSPEICHERN_UEBER = 200  # wie _SAMMELSPEICHERN_UEBER_TEILNEHMER im Desktop
_ABBRUCH_OHNE_GRUND = "ohne_grund"  # wie desktop_ergebnis_zellen._ABBRUCH_OHNE_GRUND (Altdaten)


def _disziplinen_von(teilnehmer: dict) -> list[str]:
    return [teilnehmer["disziplin"]] if teilnehmer["art"] == "ED" else list(db.ALLE_DISZIPLINEN)


def _abbruch_code(ergebnis: dict) -> str:
    """"" (kein Abbruch), Code aus db.ABBRUCH_GRUENDE oder _ABBRUCH_OHNE_GRUND (Altdaten)."""
    if not ergebnis.get("abbruch"):
        return ""
    grund = ergebnis.get("abbruch_grund")
    return grund if grund in db.ABBRUCH_GRUENDE else _ABBRUCH_OHNE_GRUND


def _tabellen_status_text(ergebnis: dict) -> str:
    """Status wie im Desktop (_gespeicherter_status_text)."""
    code = _abbruch_code(ergebnis)
    if ergebnis.get("disqualifiziert"):
        return "disqualifiziert"
    if code == _ABBRUCH_OHNE_GRUND:
        return "Abbruch"
    if code:
        return f"Abbruch: {db.ABBRUCH_GRUENDE[code][0]}"
    if any(ergebnis.get(spalte) is not None for spalten in db.DISZIPLIN_SPALTEN.values() for spalte in spalten):
        return "gespeichert"
    return "noch kein Ergebnis"


def _ergebnis_zustand(teilnehmer: dict, ergebnis: dict) -> dict:
    """Der in der Tabelle sichtbare Stand einer Zeile aus der Datenbank: Punkte je Disziplin als
    Text, Disqualifiziert, Abbruchcode."""
    punkte = {}
    for disziplin in _disziplinen_von(teilnehmer):
        spalte_suche, spalte_anzeige = db.DISZIPLIN_SPALTEN[disziplin]
        punkte[disziplin] = (_wert_zu_text(ergebnis.get(spalte_suche)), _wert_zu_text(ergebnis.get(spalte_anzeige)))
    return {"punkte": punkte, "dq": bool(ergebnis.get("disqualifiziert")), "abbruch": _abbruch_code(ergebnis)}


def _geladen_text(teilnehmer: dict, zustand: dict) -> str:
    """Inhalt des versteckten Feldes geladen_<id>: "S,A" je Disziplin (Reihenfolge von
    _disziplinen_von), dann Disqualifiziert (0/1) und Abbruchcode, getrennt durch "|"."""
    teile = [f"{s},{a}" for s, a in (zustand["punkte"][d] for d in _disziplinen_von(teilnehmer))]
    return "|".join(teile + ["1" if zustand["dq"] else "0", zustand["abbruch"]])


def _geladen_lesen(teilnehmer: dict, roh: str | None) -> dict | None:
    """Gegenstück zu _geladen_text. None, wenn das Feld fehlt oder kaputt ist: dann gibt es keine
    Information über den geladenen Stand, und die Zeile gilt als verändert (wie _feld_roh)."""
    if roh is None:
        return None
    teile = roh.split("|")
    disziplinen = _disziplinen_von(teilnehmer)
    if len(teile) != len(disziplinen) + 2:
        return None
    punkte = {}
    for disziplin, teil in zip(disziplinen, teile):
        suche, trenner, anzeige = teil.partition(",")
        if not trenner:
            return None
        punkte[disziplin] = (suche.strip(), anzeige.strip())
    dq, abbruch = teile[-2], teile[-1]
    if dq not in ("0", "1") or (abbruch and abbruch != _ABBRUCH_OHNE_GRUND and abbruch not in db.ABBRUCH_GRUENDE):
        return None
    return {"punkte": punkte, "dq": dq == "1", "abbruch": abbruch}


class _ZeilenFormular:
    """Sicht auf die Felder EINER Tabellenzeile mit den Feldnamen der Einzelseite
    (suche_<Disziplin>, geladen_suche_<Disziplin> ...), damit _pruefe_und_parse_formular und die
    Lost-Update-Hilfen unverändert wiederverwendet werden: Eingabefelder heißen in der Tabelle
    <name>_<Teilnehmer-ID>, der geladene Stand kommt aus dem einen Feld geladen_<id>."""

    def __init__(self, formular, teilnehmer_id: int, geladen: dict | None):
        self._formular = formular
        self._id = teilnehmer_id
        self._geladen = geladen

    def get(self, name: str, default=None):
        if name.startswith(("geladen_suche_", "geladen_anzeige_")):
            art, _, disziplin = name[len("geladen_"):].partition("_")
            if self._geladen is None or disziplin not in self._geladen["punkte"]:
                return default
            return self._geladen["punkte"][disziplin][0 if art == "suche" else 1]
        return self._formular.get(f"{name}_{self._id}", default)


def _tabellen_filter() -> dict:
    """Filter aus der Adresse (GET und, über die Adresse des Speicher-Formulars, auch POST)."""
    return {
        "lk": (request.args.get("lk") or "").strip()[:80],
        "nr": (request.args.get("nr") or "").strip()[:10],
        "q": (request.args.get("q") or "").strip()[:80],
    }


def _tabellen_teilnehmer(conn, filter_: dict) -> list[dict]:
    """Teilnehmende Teilnehmer, die zum Filter passen, in der Reihenfolge der Tabelle: nach
    Startnummer aufsteigend (UX-Test Web 19.11.2026, C2, Marco; vorher nach Prüfung, dann
    Startnummer), ohne Startnummer am Ende und diese nach Prüfung und Name (Startnummern sind
    eindeutig)."""
    gefunden = []
    for t in db.list_teilnehmer(conn, nur_teilnehmende=True):
        if filter_["lk"] and db.leistungsklasse_label(t) != filter_["lk"]:
            continue
        if filter_["nr"] and str(t["startnummer"] or "") != filter_["nr"]:
            continue
        if filter_["q"] and not _name_passt_zur_suche(t, filter_["q"]):
            continue
        gefunden.append(t)
    gefunden.sort(key=lambda t: (
        t["startnummer"] is None, t["startnummer"] or 0,
        db.pruefung_sortierschluessel(db.leistungsklasse_label(t)), db.sortierschluessel_text(t["nachname"]),
    ))
    return gefunden


def _zeilen_ids_aus_formular(formular) -> list[int]:
    """Teilnehmer-IDs der abgeschickten Zeilen (aus den Feldern geladen_<id>), ohne Doppelte."""
    ids: list[int] = []
    for name in formular.keys():
        nummer = name[len("geladen_"):]
        if name.startswith("geladen_") and nummer.isascii() and nummer.isdigit() and len(nummer) <= 12:
            if int(nummer) not in ids:
                ids.append(int(nummer))
    return ids


def _tabelle_pruefen(formular, ids: list[int], teilnehmer_je_id: dict) -> tuple[dict, dict]:
    """Phase 1 des Speicherns: liest und prüft alle Zeilen. Liefert ({id: Plan}, {id: Fehlertext});
    gespeichert wird nur, wenn es keinen Fehler gibt."""
    plaene: dict[int, dict] = {}
    fehler: dict[int, str] = {}
    for tid in ids:
        t = teilnehmer_je_id[tid]
        disziplinen = _disziplinen_von(t)
        geladen = _geladen_lesen(t, _feld_roh(formular, f"geladen_{tid}"))
        zeile = _ZeilenFormular(formular, tid, geladen)
        dq = _feld_zu_text(formular, f"dq_{tid}") == "1"
        abbruch = _feld_zu_text(formular, f"abbruch_{tid}")
        abbruch_fehler = _abbruch_fehler(abbruch, geladen["abbruch"] if geladen else None)
        if abbruch_fehler:
            fehler[tid] = abbruch_fehler
            continue
        werte = None
        geladene_werte = _geladene_werte_aus_formular(zeile, disziplinen)
        if not _punkte_gesperrt(dq, abbruch):  # sonst sind die Punkte gesperrt (ignoriert)
            werte, text = _pruefe_und_parse_formular(zeile, disziplinen, geladene_werte)
            if text is not None:
                fehler[tid] = text
                continue
        plaene[tid] = {"zeile": zeile, "geladen": geladen, "geladene_werte": geladene_werte,
                       "dq": dq, "abbruch": abbruch, "werte": werte}
    return plaene, fehler


def _einheit_entscheiden(unveraendert: bool, schon_gleich: bool, geladen_bekannt: bool, aktuell_wie_geladen: bool) -> str:
    """"skip", "schreiben" oder "konflikt" für eine Einheit (Punkte einer Disziplin bzw. Status)."""
    if unveraendert or schon_gleich:
        return "skip"
    if geladen_bekannt and not aktuell_wie_geladen:
        return "konflikt"
    return "schreiben"


def _tabelle_schreiben(conn, plaene: dict, teilnehmer_je_id: dict, ergebnis_je_id: dict) -> tuple[set, dict]:
    """Phase 2: Konfliktprüfung gegen den aktuellen DB-Stand und Schreiben. Liefert (IDs der
    Zeilen mit geschriebenen Werten, {id: [Konflikttexte]}). Ab _TABELLE_SAMMELSPEICHERN_UEBER
    Zeilen in EINER Transaktion (ganz oder gar nicht), sonst mit einem Commit je Wert."""
    gesammelt = len(plaene) > _TABELLE_SAMMELSPEICHERN_UEBER
    gespeichert: set[int] = set()
    konflikte: dict[int, list[str]] = {}
    for tid, plan in plaene.items():
        t = teilnehmer_je_id[tid]
        aktuell_ergebnis = ergebnis_je_id.get(tid) or {}
        aktuell = _ergebnis_zustand(t, aktuell_ergebnis)
        geladen = plan["geladen"]
        meldungen = konflikte.setdefault(tid, [])

        geladen_status = None if geladen is None else (geladen["dq"], geladen["abbruch"])
        status_geschrieben, status_konflikt = _status_einheit_schreiben(
            conn, tid, (plan["dq"], plan["abbruch"]), geladen_status, aktuell_ergebnis, commit=not gesammelt)
        if status_geschrieben:
            gespeichert.add(tid)
        if status_konflikt:
            meldungen.append(status_konflikt)

        if plan["werte"] is None:
            continue  # Punkte gesperrt: ignoriert, die gespeicherten Punkte bleiben
        extern_gesperrt = _extern_gesperrt(geladen_status, (aktuell["dq"], aktuell["abbruch"]))
        for disziplin, (suche, anzeige) in plan["werte"].items():
            aktuelle_texte = aktuell["punkte"][disziplin]
            spalte_suche, spalte_anzeige = db.DISZIPLIN_SPALTEN[disziplin]
            entscheidung = _einheit_entscheiden(
                unveraendert=_disziplin_unveraendert(plan["zeile"], disziplin, plan["geladene_werte"]),
                schon_gleich=(suche, anzeige) == (aktuell_ergebnis.get(spalte_suche), aktuell_ergebnis.get(spalte_anzeige)),
                geladen_bekannt=geladen is not None,
                aktuell_wie_geladen=geladen is not None and aktuelle_texte == geladen["punkte"].get(disziplin),
            )
            if entscheidung == "schreiben" and extern_gesperrt:
                entscheidung = "konflikt"
            if entscheidung == "schreiben":
                db.eintragen_ergebnis(conn, tid, disziplin, suche, anzeige, commit=not gesammelt)
                _aenderung_merken(conn, tid, disziplin, commit=not gesammelt)
                gespeichert.add(tid)
            elif entscheidung == "konflikt":
                meldungen.append(_punkte_konflikt_text(disziplin, suche, anzeige, aktuelle_texte))
    if gesammelt:
        conn.commit()
    return gespeichert, {tid: m for tid, m in konflikte.items() if m}


def _tabellenzeile(t: dict, ergebnis: dict, formular=None, fehler: str | None = None, konflikt: list[str] | None = None) -> dict:
    """Eine Tabellenzeile fürs Template. Mit `formular` (Neuaufbau nach einem Validierungsfehler)
    stammen Eingaben, Häkchen und Auswahl aus den abgeschickten Werten, das versteckte Feld
    geladen_<id> UNVERÄNDERT aus dem Formular (der ursprünglich geladene Stand, siehe
    _zeilen_aus_formular); sonst alles aus der Datenbank. Status und Abbruch-Optionen zeigen
    immer den gespeicherten Stand."""
    zustand = _ergebnis_zustand(t, ergebnis)
    geladen = _geladen_text(t, zustand)
    dq, abbruch = zustand["dq"], zustand["abbruch"]
    punkte = dict(zustand["punkte"])
    if formular is not None:
        zeile = _ZeilenFormular(formular, t["id"], None)
        geladen = _feld_roh(formular, f"geladen_{t['id']}") or ""
        dq = _feld_zu_text(formular, f"dq_{t['id']}") == "1"
        abbruch = _feld_zu_text(formular, f"abbruch_{t['id']}")
        for disziplin in punkte:
            punkte[disziplin] = _disziplin_text_werte(zeile, disziplin)
    gesperrt = dq or abbruch == _ABBRUCH_OHNE_GRUND
    return {
        "id": t["id"],
        "teilnehmer": t,
        "label": db.leistungsklasse_label(t),
        "geladen": geladen,
        "punkte": [
            {"disziplin": d, "aktiv": d in punkte,
             "suche": punkte[d][0] if d in punkte else "", "anzeige": punkte[d][1] if d in punkte else ""}
            for d in db.ALLE_DISZIPLINEN
        ],
        "dq": dq,
        "abbruch": abbruch,
        "gesperrt": gesperrt,
        # „ohne Grund“ gibt es nur als Altdatum und wird nur dann angeboten (wie im Desktop).
        "abbruch_ohne_grund": abbruch == _ABBRUCH_OHNE_GRUND or zustand["abbruch"] == _ABBRUCH_OHNE_GRUND,
        "status": _tabellen_status_text(ergebnis),
        "fehler": fehler,
        "konflikt": konflikt,
    }


def _vor_wann(zeitpunkt_iso: str, jetzt: datetime | None = None) -> str:
    """„gerade eben“, „vor 5 Min.“, „vor 2 Std.“ oder „am 20.11.“ - relativ statt Uhrzeit, weil der
    Server (Container) in UTC läuft und die Ortszeit der Richter nicht kennt."""
    try:
        zeitpunkt = datetime.fromisoformat(zeitpunkt_iso)
    except (TypeError, ValueError):
        return "?"
    if zeitpunkt.tzinfo is None:
        zeitpunkt = zeitpunkt.replace(tzinfo=timezone.utc)
    jetzt = jetzt or datetime.now(timezone.utc)
    sekunden = (jetzt - zeitpunkt).total_seconds()
    if sekunden < 60:
        return "gerade eben"
    if sekunden < 3600:
        return f"vor {int(sekunden // 60)} Min."
    if sekunden < 24 * 3600:
        return f"vor {int(sekunden // 3600)} Std."
    return f"am {zeitpunkt.day:02d}.{zeitpunkt.month:02d}."


def _zuletzt_texte(aenderungen: dict[str, tuple[str, str]] | None) -> tuple[str | None, str | None]:
    """(Kurztext der letzten Änderung, Einzelheiten je Bereich) für eine Tabellenzeile (nur Admins, B6)."""
    if not aenderungen:
        return None, None
    reihenfolge = list(db.ALLE_DISZIPLINEN) + [db._BEREICH_STATUS]
    eintraege = sorted(aenderungen.items(), key=lambda e: reihenfolge.index(e[0]) if e[0] in reihenfolge else 99)
    bereich, (name, zeit) = max(aenderungen.items(), key=lambda e: e[1][1])
    kurz = f"zuletzt {name}, {_vor_wann(zeit)} ({bereich})"
    einzeln = "; ".join(f"{b}: {n}, {_vor_wann(z)}" for b, (n, z) in eintraege)
    return kurz, einzeln


def _anzahl_zeilen(anzahl: int) -> str:
    return "1 Zeile" if anzahl == 1 else f"{anzahl} Zeilen"


def _gespeichert_text(anzahl: int) -> str:
    """UX-Test Web 19.11.2026 (B3): verständlich statt „n Zeile(n) gespeichert.“"""
    return f"Gespeichert: {anzahl} Teilnehmer."


def _bogen_ziel(wert: str | None, teilnehmer_je_id: dict) -> tuple[int, str] | None:
    """Wert des Knopfs „Bogen“ der Tabelle („<Teilnehmer-ID>:<Disziplin>“) -> (ID, Disziplin), nur
    für einen teilnehmenden Teilnehmer dieses Termins und eine seiner Disziplinen, sonst None."""
    tid_text, trenner, disziplin = (wert or "").partition(":")
    if not trenner or not (tid_text.isascii() and tid_text.isdigit()) or len(tid_text) > 12:
        return None
    t = teilnehmer_je_id.get(int(tid_text))
    if t is None or disziplin not in _disziplinen_von(t):
        return None
    return t["id"], disziplin


@app.route("/ergebnisse", methods=["GET", "POST"])
@_termin_erforderlich
def ergebnistabelle(conn):
    """GET zeigt die Ergebnistabelle (Filter per Adresse: lk, nr, q), POST speichert sie (siehe
    Abschnittskommentar oben für die Regeln)."""
    filter_ = _tabellen_filter()
    alle_lk = db.alle_leistungsklassen(conn)
    if filter_["lk"] not in alle_lk:
        filter_["lk"] = ""
    meldung = None
    hinweis = None
    fehlermeldung = None
    fehler_je_id: dict[int, str] = {}
    konflikte: dict[int, list[str]] = {}
    formular = None

    if request.method == "POST":
        # Maßgeblich sind alle teilnehmenden Teilnehmer dieses Termins, nicht nur die sichtbaren:
        # eine abgeschickte ID, die es hier nicht (mehr) gibt, wird ignoriert.
        teilnehmer_je_id = {t["id"]: t for t in db.list_teilnehmer(conn, nur_teilnehmende=True)}
        abgeschickt = _zeilen_ids_aus_formular(request.form)
        ids = [tid for tid in abgeschickt if tid in teilnehmer_je_id]
        ignoriert = len(abgeschickt) - len(ids)
        plaene, fehler_je_id = _tabelle_pruefen(request.form, ids, teilnehmer_je_id)
        if fehler_je_id:
            fehlermeldung = (f"Es wurde nichts gespeichert: {_anzahl_zeilen(len(fehler_je_id))} mit Fehlern "
                             "(rot markiert). Alle Eingaben stehen noch in der Tabelle.")
            formular = request.form
        else:
            gespeichert, konflikte = _tabelle_schreiben(conn, plaene, teilnehmer_je_id, db.ergebnisse_je_teilnehmer(conn))
            if not konflikte and not ignoriert:
                # UX-Test Web 19.11.2026 (C3): „Bogen“ ist ein Absendeknopf dieses Formulars - erst
                # speichern, dann den Bogen öffnen (vorher gingen nicht gespeicherte Eingaben verloren).
                bogen = _bogen_ziel(request.form.get("bogen"), teilnehmer_je_id)
                if bogen is not None:
                    return redirect(url_for("bewertungsbogen", teilnehmer_id=bogen[0], disziplin=bogen[1],
                                            **{k: v for k, v in filter_.items() if v}))
                return redirect(url_for("ergebnistabelle", gespeichert=len(gespeichert), **{
                    k: v for k, v in filter_.items() if v}))
            teile = [_gespeichert_text(len(gespeichert))]
            if konflikte:
                bei = "1 Teilnehmer" if len(konflikte) == 1 else f"{len(konflikte)} Teilnehmern"
                fehlermeldung = (f"Bei {bei} wurde inzwischen von jemand anderem etwas "
                                 "geändert; diese Werte wurden NICHT überschrieben (gelb markiert, die Tabelle "
                                 "zeigt den aktuellen Stand).")
                if request.form.get("bogen"):
                    fehlermeldung += " Der Bewertungsbogen wurde deshalb nicht geöffnet - bitte erst prüfen."
            if ignoriert:
                teile.append(f"{_anzahl_zeilen(ignoriert)} gehören nicht (mehr) zu diesem Termin und wurden ignoriert.")
            meldung = " ".join(teile)
    else:
        try:
            anzahl = int(request.args.get("gespeichert", ""))
        except ValueError:
            anzahl = None
        if anzahl is not None and 0 <= anzahl <= 100000:
            meldung = _gespeichert_text(anzahl) if anzahl else "Keine Änderungen zu speichern."
        # Rückmeldung von /ergebnisse/boegen.pdf: nur feste Texte zu festen Codes, nie Text aus der Adresse.
        boegen_hinweis = _BOEGEN_PDF_HINWEISE.get(request.args.get("boegen", ""))
        if boegen_hinweis is not None:
            # „keine benutzten Bögen“ ist nur ein Hinweis (neutral), nur ein echter Fehler wird rot gezeigt.
            if request.args.get("boegen") == "keine":
                hinweis = boegen_hinweis
            else:
                fehlermeldung = boegen_hinweis

    ergebnis_je_id = db.ergebnisse_je_teilnehmer(conn)
    # UX-Test Web 19.11.2026 (B6): nur Admins sehen, welches Konto wann zuletzt eingetragen hat.
    aenderungen = db.aenderungen_lesen(conn) if session.get("ist_admin") else {}
    sichtbare = _tabellen_teilnehmer(conn, filter_)
    zeilen = []
    for t in sichtbare:
        eigenes_formular = formular if formular is not None and f"geladen_{t['id']}" in formular else None
        zeilen.append(_tabellenzeile(
            t, ergebnis_je_id.get(t["id"]) or {}, eigenes_formular,
            fehler=fehler_je_id.get(t["id"]), konflikt=konflikte.get(t["id"]),
        ))
        zeilen[-1]["zuletzt"], zeilen[-1]["zuletzt_einzeln"] = _zuletzt_texte(aenderungen.get(t["id"]))
        # Der Knopf „Bogen“ je aktiver Disziplin ist seit UX-Test Web 19.11.2026 (C3) ein Absendeknopf
        # (siehe _bogen_ziel); der Filter hängt an der Adresse des Speicher-Formulars.

    return render_template(
        "ergebnis_tabelle.html",
        veranstaltung=db.get_veranstaltung(conn),
        zeilen=zeilen,
        disziplinen=list(db.ALLE_DISZIPLINEN),
        filter=filter_,
        alle_lk=alle_lk,
        abbruch_gruende=[(code, text[0]) for code, text in db.ABBRUCH_GRUENDE.items()],
        suche_max=db.SUCHE_MAX,
        anzeige_max=db.ANZEIGE_MAX,
        meldung=meldung,
        hinweis=hinweis,
        fehlermeldung=fehlermeldung,
        speichern_url=url_for("ergebnistabelle", **{k: v for k, v in filter_.items() if v}),
        boegen_pdf_url=url_for("ergebnis_boegen_pdf", **{k: v for k, v in filter_.items() if v}),
    )


# --- Benutzte Bewertungsbögen als Sammel-PDF (/ergebnisse/boegen.pdf) --------------------
#
# Marco 18.11.2026: ein Knopf in der Ergebnistabelle lädt alle BENUTZTEN Bewertungsbögen (Papierlayout
# wie am Desktop, mit eingetragenen Punkten, Status und Notizen) als eine PDF. Benutzt heißt: der
# Teilnehmer hat mindestens einen Punktwert, Disqualifiziert/Abbruch oder eine Notiz. Der Filter der
# Tabelle (lk, nr, q) gilt unverändert; gedruckt wird der GESPEICHERTE Stand (nicht gespeicherte
# Eingaben der Tabelle fehlen). Reihenfolge nach Startnummer, ED 1 Blatt, Dreikampf 2 Seiten - außer ein
# teilweise bewerteter Dreikampf ohne Status: dann nur die Blätter der benutzten Disziplinen (UX-Test Web
# 19.11.2026, G1; pdf_export.erstelle_alle_bewertungsboegen_pdf, nur_benutzte_disziplinen).
# pdf_export (reportlab) wird erst beim Aufruf importiert, damit die Web-App auch ohne reportlab startet.

_BOEGEN_PDF_HINWEISE = {
    "keine": "Keine benutzten Bewertungsbögen: Für die gewählten Teilnehmer ist noch nichts eingetragen "
             "(weder Punkte noch Disqualifikation, Abbruch oder Notiz).",
    "fehler": "Die PDF konnte nicht erstellt werden. Bitte später noch einmal versuchen; "
              "bleibt der Fehler, bitte den Administrator informieren.",
}


def _bogen_benutzt(ergebnis: dict | None) -> bool:
    """Hat dieser Teilnehmer einen Eintrag, der einen Bogen lohnt: Punktwert, Disqualifiziert,
    Abbruch oder eine Notiz (Leerraum zählt nicht)?"""
    if not ergebnis:
        return False
    if ergebnis.get("disqualifiziert") or ergebnis.get("abbruch"):
        return True
    if any(ergebnis.get(spalte) is not None for spalten in db.DISZIPLIN_SPALTEN.values() for spalte in spalten):
        return True
    return any(_notiz_text(ergebnis.get(spalte)) for spalte in db.NOTIZ_SPALTEN.values())


@app.route("/ergebnisse/boegen.pdf")
@_termin_erforderlich
def ergebnis_boegen_pdf(conn):
    """Sammel-PDF der benutzten Bewertungsbögen (siehe Abschnittskommentar oben). Ohne passende
    Teilnehmer und bei einem Fehler beim Erzeugen geht es mit einem festen Hinweis zurück zur
    Tabelle (kein 500, nichts Internes)."""
    filter_ = _tabellen_filter()
    if filter_["lk"] not in db.alle_leistungsklassen(conn):
        filter_["lk"] = ""  # wie die Tabelle: ein unbekannter Filterwert zeigt dort (und hier) alle
    zurueck = {k: v for k, v in filter_.items() if v}
    ergebnis_je_id = db.ergebnisse_je_teilnehmer(conn)
    ids = {t["id"] for t in _tabellen_teilnehmer(conn, filter_) if _bogen_benutzt(ergebnis_je_id.get(t["id"]))}
    if not ids:
        return redirect(url_for("ergebnistabelle", boegen="keine", **zurueck))
    try:
        import pdf_export  # erst hier: braucht reportlab (siehe oben)
        puffer = io.BytesIO()
        # UX-Test Web 19.11.2026 (G1): beim Dreikampf nur die Blätter benutzter Disziplinen
        pdf_export.erstelle_alle_bewertungsboegen_pdf(conn, puffer, teilnehmer_ids=ids, nur_benutzte_disziplinen=True)
        daten = puffer.getvalue()
        veranstaltung = db.get_veranstaltung(conn) or {}
    except Exception:  # noqa: BLE001 - jeder Fehler (auch fehlendes reportlab) -> feste Meldung
        app.logger.exception("Sammel-PDF der Bewertungsbögen konnte nicht erstellt werden")
        return redirect(url_for("ergebnistabelle", boegen="fehler", **zurueck))
    name = secure_filename(f"Bewertungsboegen_{veranstaltung.get('verein') or ''}_{veranstaltung.get('datum') or ''}")
    name = (name.strip("._") or "Bewertungsboegen") + ".pdf"
    antwort = send_file(io.BytesIO(daten), mimetype="application/pdf", as_attachment=True, download_name=name)
    # send_file setzt selbst Cache-Control (no-cache); der globale Header greift nur per setdefault.
    antwort.headers["Cache-Control"] = "no-store"
    return antwort


# --- Online-Bewertungsbogen (/bewertungsbogen/<id>/<Disziplin>) -------------------------
#
# Marco 18.11.2026: ein ausfüllbarer Bogen je Disziplin, geöffnet über den Knopf „Bogen“ in der
# Ergebnistabelle (bei Dreikampf je Richter sein Blatt für seine Disziplin, bei ED nur die eigene).
# Layout wie der Papierbogen (pdf_export._bewertungsabschnitt), aber eine reine Formularseite
# ohne JavaScript (CSP script-src 'none'). Die Punkte landen in denselben Ergebnisspalten wie in
# der Tabelle; die Notiz zum Bogen (Position des Gegenstands, Besonderheiten) liegt je Disziplin
# in ergebnisse.notiz_* (db.NOTIZ_SPALTEN).
#
# Alle Regeln der Tabelle gelten unverändert, weil der Bogen sie wiederverwendet: der Teilnehmer
# erscheint dafür als Einzeldisziplin-Teilnehmer der einen Disziplin (_bogen_sicht), und die Felder
# heißen wie in der Tabelle (suche_<Disziplin>_<id>, dq_<id>, abbruch_<id>, geladen_<id>) - so
# prüfen und schreiben _tabelle_pruefen/_tabelle_schreiben ausschließlich diese Disziplin, die
# anderen Disziplinen eines Dreikampf-Teilnehmers bleiben unangetastet. Neu ist nur die Notiz
# (Lost-Update-Schutz über geladen_notiz_<id>, bei Konflikt wird nichts überschrieben).

_BOGEN_NOTIZ_FELD = "notiz_{}"
_BOGEN_NOTIZ_GELADEN = "geladen_notiz_{}"


def _bogen_sicht(teilnehmer: dict, disziplin: str) -> dict:
    """Der Teilnehmer, wie ihn die Tabellen-Hilfen für den Bogen sehen sollen: als Einzeldisziplin
    der einen Disziplin (so gibt _disziplinen_von nur sie zurück)."""
    return dict(teilnehmer, art="ED", disziplin=disziplin)


def _notiz_text(text: str | None) -> str:
    """Notiz in der Form, in der sie gespeichert und verglichen wird: einheitliche Zeilenenden
    (Browser schicken beim Absenden CRLF) und ohne Leerraum am Rand (wie db.setze_notiz)."""
    return (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _bogen_zusammenfassung(teilnehmer: dict, ergebnis: dict, disziplin: str) -> dict:
    """Gespeicherter Stand für die Anzeige unter dem Bogen: Gesamtpunktzahl der Disziplin (nur,
    wenn Suche UND Anzeige da sind), Status und die Wertnote nach shs_core. Bei ED ist das die
    Wertnote der Prüfung, bei DK braucht sie alle drei Disziplinen. Bei Disqualifiziert/Abbruch
    gibt es keine Wertnote aus den Punkten (wie in db.berechne_auswertung)."""
    def punkte(d: str) -> int | None:
        spalte_suche, spalte_anzeige = db.DISZIPLIN_SPALTEN[d]
        suche, anzeige = ergebnis.get(spalte_suche), ergebnis.get(spalte_anzeige)
        return None if suche is None or anzeige is None else suche + anzeige

    gesamt = punkte(disziplin)
    wertnote = None
    hinweis = None
    if not (ergebnis.get("disqualifiziert") or ergebnis.get("abbruch")):
        if teilnehmer["art"] == "ED":
            if gesamt is not None:
                wertnote = db.berechne_wertnote_ed(gesamt)
        else:
            je_disziplin = [punkte(d) for d in db.ALLE_DISZIPLINEN]
            if None in je_disziplin:
                hinweis = ("Die Wertnote des Dreikampfs steht fest, sobald für alle drei Disziplinen "
                           "Suche und Anzeige eingetragen sind.")
            else:
                wertnote = db.berechne_wertnote_dk(*je_disziplin)
    return {"gesamt": gesamt, "status": _tabellen_status_text(ergebnis), "wertnote": wertnote,
            "wertnote_hinweis": hinweis}


def _bogen_notiz_schreiben(conn, teilnehmer_id: int, disziplin: str, neu: str, geladen_roh: str | None,
                           ergebnis: dict) -> tuple[bool, str | None]:
    """Speichert die Notiz, wenn sie verändert wurde und niemand sie inzwischen anders geändert
    hat (gleiche Regel wie _einheit_entscheiden). Liefert (geschrieben, Konflikttext)."""
    aktuell = _notiz_text(ergebnis.get(db.NOTIZ_SPALTEN[disziplin]))
    geladen = None if geladen_roh is None else _notiz_text(geladen_roh)
    entscheidung = _einheit_entscheiden(
        unveraendert=geladen is not None and neu == geladen,
        schon_gleich=neu == aktuell,
        geladen_bekannt=geladen is not None,
        aktuell_wie_geladen=geladen is not None and aktuell == geladen,
    )
    if entscheidung == "schreiben":
        try:
            db.setze_notiz(conn, teilnehmer_id, disziplin, neu)
        except ValueError as fehler:
            return False, f"Die Notiz wurde nicht gespeichert: {fehler}"
        _aenderung_merken(conn, teilnehmer_id, disziplin)
        return True, None
    if entscheidung == "konflikt":
        return False, ("Die Notiz wurde inzwischen von jemand anderem geändert - Ihre Änderung wurde nicht "
                       "gespeichert (die Seite zeigt die aktuelle Notiz).")
    return False, None


@app.route("/bewertungsbogen/<int:teilnehmer_id>/<disziplin>", methods=["GET", "POST"])
@_termin_erforderlich
def bewertungsbogen(conn, teilnehmer_id, disziplin):
    """GET zeigt den Bogen einer Disziplin (vorbelegt mit dem gespeicherten Stand), POST speichert
    (siehe Abschnittskommentar oben). 404 für unbekannte oder nicht teilnehmende Teilnehmer und
    für eine Disziplin, die nicht zur Prüfung des Teilnehmers gehört. „Speichern“ bleibt auf dem
    Bogen (und zeigt Gesamtpunktzahl und Wertnote), „Speichern und zurück …“ geht dorthin, woher der
    Bogen geöffnet wurde: mit ?von=liste zur Teilnehmerliste, mit ?von=teilnehmer zur Seite je
    Teilnehmer, sonst zur Zeile in der Tabelle; dann hängt der Filter der Tabelle (lk, nr, q) an der
    Adresse (auf den beiden anderen Wegen nicht)."""
    teilnehmer = db.get_teilnehmer(conn, teilnehmer_id)
    if teilnehmer is None or teilnehmer.get("keine_teilnahme") or disziplin not in _disziplinen_von(teilnehmer):
        abort(404)
    sicht = _bogen_sicht(teilnehmer, disziplin)
    filter_ = {k: v for k, v in _tabellen_filter().items() if v}
    # UX-Test Web 19.11.2026 (aus U1): Herkunft des Bogens (?von=liste bzw. ?von=teilnehmer), damit
    # „zurück“ dorthin führt statt immer in die Tabelle. Nur feste Werte, sonst die Tabelle.
    von = request.args.get("von") if request.args.get("von") in ("liste", "teilnehmer") else None
    if von:
        filter_ = {"von": von}  # die Tabellenfilter gelten auf diesen Wegen nicht
    notiz_feld = _BOGEN_NOTIZ_FELD.format(teilnehmer_id)
    notiz_geladen_feld = _BOGEN_NOTIZ_GELADEN.format(teilnehmer_id)

    fehler = None
    konflikt = None
    formular = None
    meldung = None
    if request.method == "POST":
        form = request.form
        plaene, fehler_je_id = _tabelle_pruefen(form, [teilnehmer_id], {teilnehmer_id: sicht})
        fehler = fehler_je_id.get(teilnehmer_id)
        notiz_neu = _notiz_text(form.get(notiz_feld)) if notiz_feld in form else None
        if fehler is None and notiz_neu is not None and len(notiz_neu) > db.NOTIZ_MAX:
            fehler = f"Die Notiz ist zu lang: höchstens {db.NOTIZ_MAX} Zeichen sind möglich."
        if fehler is not None:
            formular = form  # nichts gespeichert, alle Eingaben bleiben stehen
        else:
            gespeichert, konflikte = _tabelle_schreiben(
                conn, plaene, {teilnehmer_id: sicht}, {teilnehmer_id: db.get_ergebnis(conn, teilnehmer_id) or {}})
            konflikt_texte = list(konflikte.get(teilnehmer_id, []))
            geschrieben = teilnehmer_id in gespeichert
            if notiz_neu is not None:
                notiz_geschrieben, notiz_konflikt = _bogen_notiz_schreiben(
                    conn, teilnehmer_id, disziplin, notiz_neu, form.get(notiz_geladen_feld),
                    db.get_ergebnis(conn, teilnehmer_id) or {})
                geschrieben = geschrieben or notiz_geschrieben
                if notiz_konflikt:
                    konflikt_texte.append(notiz_konflikt)
            if not konflikt_texte:
                if form.get("weiter") == "tabelle":  # „Speichern und zurück …“
                    if von == "liste":
                        return redirect(url_for("teilnehmerliste", gespeichert=teilnehmer_id,
                                                aenderung=int(geschrieben)))
                    if von == "teilnehmer":
                        return redirect(url_for("ergebnis_erfassen", teilnehmer_id=teilnehmer_id))
                    return redirect(url_for("ergebnistabelle", gespeichert=int(geschrieben),
                                            _anchor=f"zeile-{teilnehmer_id}", **filter_))
                return redirect(url_for("bewertungsbogen", teilnehmer_id=teilnehmer_id, disziplin=disziplin,
                                        gespeichert=int(geschrieben), **filter_))
            konflikt = konflikt_texte
            if geschrieben:
                meldung = "Die übrigen Eingaben wurden gespeichert."
    else:
        gespeichert_arg = request.args.get("gespeichert")
        if gespeichert_arg in ("0", "1"):
            meldung = "Gespeichert." if gespeichert_arg == "1" else "Keine Änderungen zu speichern."

    ergebnis = db.get_ergebnis(conn, teilnehmer_id) or {}
    zeile = _tabellenzeile(sicht, ergebnis, formular, fehler=fehler, konflikt=konflikt)
    gespeicherte_notiz = _notiz_text(ergebnis.get(db.NOTIZ_SPALTEN[disziplin]))
    if formular is not None:
        notiz = (formular.get(notiz_feld) or "")
        notiz_geladen = _feld_roh(formular, notiz_geladen_feld) or ""
    else:
        notiz = notiz_geladen = gespeicherte_notiz

    return render_template(
        "bewertungsbogen.html",
        veranstaltung=db.get_veranstaltung(conn),
        teilnehmer=teilnehmer,
        label=db.leistungsklasse_label(teilnehmer),
        disziplin=disziplin,
        gegenstand=db.gegenstand_fuer_disziplin(teilnehmer, disziplin),
        zeile=zeile,
        punkte=next(p for p in zeile["punkte"] if p["disziplin"] == disziplin),
        notiz=notiz,
        notiz_geladen=notiz_geladen,
        notiz_max=db.NOTIZ_MAX,
        zusammenfassung=_bogen_zusammenfassung(teilnehmer, ergebnis, disziplin),
        abbruch_gruende=[(code, text[0]) for code, text in db.ABBRUCH_GRUENDE.items()],
        suche_max=db.SUCHE_MAX,
        anzeige_max=db.ANZEIGE_MAX,
        meldung=meldung,
        speichern_url=url_for("bewertungsbogen", teilnehmer_id=teilnehmer_id, disziplin=disziplin, **filter_),
        tabelle_url=(url_for("teilnehmerliste") if von == "liste"
                     else url_for("ergebnis_erfassen", teilnehmer_id=teilnehmer_id) if von == "teilnehmer"
                     else url_for("ergebnistabelle", _anchor=f"zeile-{teilnehmer_id}", **filter_)),
        zurueck_ziel={"liste": "zur Teilnehmerliste", "teilnehmer": "zur Seite des Teilnehmers"}.get(von, "zur Tabelle"),
    )


# --- API für den Desktop (/api/, nur Administratoren) -----------------------------------
#
# Das Desktop-Programm meldet sich mit dem Web-Administrator-Konto an, veröffentlicht
# Termine und holt die Web-Ergebnisse zurück - ohne Browser, ohne DSN auf dem eigenen
# Rechner. Der Vertrag (Schlüssel, Statuscodes) steht in den Docstrings der Routen und in
# Architektur.md, Abschnitt "API für den Desktop".
#
# Anmeldung: POST /api/login liefert ein signiertes Token (itsdangerous, Schlüssel =
# app.secret_key, eigenes Salz, 8 Stunden). Jede weitere Anfrage trägt es im Header
# "Authorization: Bearer <Token>"; es wird bei JEDER Anfrage gegen die Datenbank geprüft
# (Konto vorhanden, Konto-Kennung unverändert, noch Administrator) - ein gelöschtes oder
# herabgestuftes Konto verliert den Zugriff also sofort. Cookie-Sitzungen zählen hier nie
# (keine /api/-Route liest die Session) - darauf beruht die CSRF-Ausnahme oben.

api = Blueprint("api", __name__, url_prefix="/api")

_API_TOKEN_SALZ = "shs-api-token-v1"
_API_TOKEN_GUELTIGKEIT_SEKUNDEN = 8 * 60 * 60
# Nur für das Veröffentlichen über die API (Termin-Dateien sind sonst deutlich kleiner als
# 1 MB, siehe db_termine.TERMIN_GROESSE_GRENZE); gilt nicht für die übrigen Routen.
_API_MAX_UPLOAD_BYTES = 100 * 1024 * 1024

# Ratenbegrenzung NUR für POST /api/login (der Web-Login bleibt bewusst ohne Schutz,
# siehe CLAUDE.md "bewusst akzeptierte Funde"): je Client-IP höchstens
# _LOGIN_MAX_FEHLVERSUCHE Fehlversuche in _LOGIN_FENSTER_SEKUNDEN, danach 429 mit
# Retry-After. Zähler nur im Prozessspeicher (geht mit einem Neustart verloren, gilt je
# Prozess - der Container läuft mit einem Prozess). Hinter dem Proxy kommt die Client-IP
# über waitress (--trusted-proxy, siehe Containerfile) in request.remote_addr an.
_LOGIN_MAX_FEHLVERSUCHE = 10
_LOGIN_FENSTER_SEKUNDEN = 15 * 60
_LOGIN_MAX_EINTRAEGE = 10000
_login_fehlversuche: dict[str, list[float]] = {}
_login_sperre = threading.Lock()
_api_zeit = time.monotonic  # Modulvariable, damit Tests die Uhr umlenken können


def _api_fehler(text: str, status: int, **kopfzeilen):
    antwort = jsonify({"fehler": text})
    antwort.status_code = status
    for name, wert in kopfzeilen.items():
        antwort.headers[name.replace("_", "-")] = wert
    return antwort


@app.errorhandler(HTTPException)
def _http_fehler(fehler):
    """Unter /api/ immer JSON {"fehler": ...} statt der HTML-Fehlerseite; für alle übrigen
    Pfade bleibt das Verhalten unverändert (die Ausnahme selbst ist die Antwort)."""
    if not request.path.startswith("/api/"):
        return fehler
    texte = {
        400: "Ungültige Anfrage.",
        401: "Anmeldung erforderlich.",
        403: "Keine Berechtigung.",
        404: "Nicht gefunden.",
        405: "Methode nicht erlaubt.",
        413: "Die Datei ist zu groß.",
    }
    antwort = _api_fehler(texte.get(fehler.code, "Anfrage fehlgeschlagen."), fehler.code or 500)
    erlaubt = fehler.get_response().headers.get("Allow")
    if erlaubt:
        antwort.headers["Allow"] = erlaubt
    return antwort


def _json_wert(wert):
    """Datum/Zeit als ISO-Text (Flask würde sie sonst im HTTP-Datumsformat ausgeben)."""
    if isinstance(wert, (datetime, date)):
        return wert.isoformat()
    return wert


def _termin_json(termin) -> dict:
    return {
        "schema_name": termin.schema_name,
        "verein": termin.verein,
        "ort": termin.ort,
        "datum": _json_wert(termin.datum),
        "anzahl_teilnehmer": termin.anzahl_teilnehmer,
    }


def _api_token_erzeugen(konto: dict) -> str:
    return URLSafeTimedSerializer(app.secret_key, salt=_API_TOKEN_SALZ).dumps(
        {"b": konto["benutzername"], "k": konto["kennung"]}
    )


def _api_admin_erforderlich(view):
    """Decorator für alle /api/-Routen außer dem Login: prüft Header, Token-Signatur und
    -Alter und re-validiert das Konto gegen die Datenbank (wie
    _aktueller_benutzer_oder_redirect, aber mit JSON-Fehlern statt Weiterleitung).
    401 = nicht angemeldet/Token ungültig, abgelaufen oder Konto weg; 403 = kein
    Administrator."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        teile = request.headers.get("Authorization", "").split(None, 1)
        if len(teile) != 2 or teile[0].lower() != "bearer":
            return _api_fehler("Anmeldung erforderlich.", 401, WWW_Authenticate="Bearer")
        try:
            daten = URLSafeTimedSerializer(app.secret_key, salt=_API_TOKEN_SALZ).loads(
                teile[1].strip(), max_age=_API_TOKEN_GUELTIGKEIT_SEKUNDEN
            )
        except BadSignature:  # schließt SignatureExpired ein
            return _api_fehler("Token ungültig oder abgelaufen - bitte neu anmelden.", 401, WWW_Authenticate="Bearer")
        if not isinstance(daten, dict) or not isinstance(daten.get("b"), str) or not isinstance(daten.get("k"), str):
            return _api_fehler("Token ungültig oder abgelaufen - bitte neu anmelden.", 401, WWW_Authenticate="Bearer")
        konto = db.benutzer_stand(_postgres_verbindung(), daten["b"])
        if konto is None or konto["kennung"] != daten["k"]:
            return _api_fehler("Das Konto existiert nicht mehr - bitte neu anmelden.", 401, WWW_Authenticate="Bearer")
        if not konto["ist_admin"]:
            return _api_fehler("Nur Administratoren dürfen diese Schnittstelle nutzen.", 403)
        return view(*args, **kwargs)
    return wrapper


def _login_schluessel(benutzername: str) -> list[str]:
    # Nur die Client-IP wird gezählt, nicht der Benutzername: sonst könnte ein Fremder, der den
    # Admin-Namen kennt, die Desktop-Anmeldung des Admins mit Fehlversuchen sperren.
    return ["i:" + (request.remote_addr or "?")]


def _login_wartezeit(schluessel: list[str]) -> int:
    """Sekunden bis zum nächsten erlaubten Versuch (0 = frei). Räumt dabei abgelaufene
    Zeitstempel ab."""
    jetzt = _api_zeit()
    wartezeit = 0
    with _login_sperre:
        if len(_login_fehlversuche) > _LOGIN_MAX_EINTRAEGE:
            for name in list(_login_fehlversuche):
                if all(jetzt - z >= _LOGIN_FENSTER_SEKUNDEN for z in _login_fehlversuche[name]):
                    del _login_fehlversuche[name]
        for name in schluessel:
            zeiten = [z for z in _login_fehlversuche.get(name, []) if jetzt - z < _LOGIN_FENSTER_SEKUNDEN]
            if zeiten:
                _login_fehlversuche[name] = zeiten
            else:
                _login_fehlversuche.pop(name, None)
            if len(zeiten) >= _LOGIN_MAX_FEHLVERSUCHE:
                frei_ab = zeiten[len(zeiten) - _LOGIN_MAX_FEHLVERSUCHE] + _LOGIN_FENSTER_SEKUNDEN
                wartezeit = max(wartezeit, int(frei_ab - jetzt) + 1)
    return wartezeit


def _login_fehlversuch_merken(schluessel: list[str]) -> None:
    jetzt = _api_zeit()
    with _login_sperre:
        for name in schluessel:
            _login_fehlversuche.setdefault(name, []).append(jetzt)


@api.post("/login")
def api_login():
    """POST /api/login - Anmeldung mit dem Web-Administrator-Konto.

    Anfrage: JSON {"benutzername": str, "passwort": str}.
    Antwort 200: {"token": str, "gueltig_sekunden": int}.
    Fehler: 400 (kein/ungültiges JSON), 401 (Benutzername oder Passwort falsch),
    403 (Konto ist kein Administrator), 429 (zu viele Fehlversuche, Header Retry-After in
    Sekunden). Jede Fehlerantwort: {"fehler": "<deutscher Text>"}."""
    daten = request.get_json(silent=True)
    if not isinstance(daten, dict):
        return _api_fehler("Erwartet wird JSON mit benutzername und passwort.", 400)
    benutzername, passwort = daten.get("benutzername"), daten.get("passwort")
    if not isinstance(benutzername, str) or not isinstance(passwort, str) or not benutzername.strip():
        return _api_fehler("Erwartet wird JSON mit benutzername und passwort.", 400)

    schluessel = _login_schluessel(benutzername)
    wartezeit = _login_wartezeit(schluessel)
    if wartezeit:
        return _api_fehler(
            "Zu viele fehlgeschlagene Anmeldungen - bitte später erneut versuchen.", 429,
            Retry_After=str(wartezeit),
        )
    konto = db.pruefe_login(_postgres_verbindung(), benutzername, passwort)
    if not konto:
        _login_fehlversuch_merken(schluessel)
        return _api_fehler("Benutzername oder Passwort falsch.", 401)
    if not konto["ist_admin"]:
        return _api_fehler("Nur Administratoren dürfen diese Schnittstelle nutzen.", 403)
    with _login_sperre:
        _login_fehlversuche.pop(schluessel[0], None)
    return jsonify({"token": _api_token_erzeugen(konto), "gueltig_sekunden": _API_TOKEN_GUELTIGKEIT_SEKUNDEN})


@api.get("/termine")
@_api_admin_erforderlich
def api_termine():
    """GET /api/termine - alle veröffentlichten Termine.

    Antwort 200: {"termine": [{"schema_name": str, "verein": str|null, "ort": str|null,
    "datum": "JJJJ-MM-TT"|null, "anzahl_teilnehmer": int}, ...]}."""
    termine = db.liste_termine_postgres(_postgres_verbindung())
    return jsonify({"termine": [_termin_json(t) for t in termine]})


@api.post("/termine")
@_api_admin_erforderlich
def api_termin_veroeffentlichen():
    """POST /api/termine - veröffentlicht eine Termin-Datei (gleiche Logik wie
    admin_termin_veroeffentlichen).

    Anfrage: multipart/form-data mit dem Feld "sqlite_datei" (Dateiname endet auf .sqlite,
    höchstens _API_MAX_UPLOAD_BYTES = 100 MB).
    Antwort 201: {"termin": {"schema_name", "verein", "ort", "datum", "anzahl_teilnehmer"},
    "dublette_hinweis": str|null} - der Hinweis (gleicher Verein und Datum bereits
    veröffentlicht) blockiert nicht.
    Fehler: 400 (Datei fehlt, falsche Endung, keine gültige SHS-Termin-Datei),
    413 (zu groß), 500 (Serverfehler beim Veröffentlichen)."""
    request.max_content_length = _API_MAX_UPLOAD_BYTES
    if request.content_length is not None and request.content_length > _API_MAX_UPLOAD_BYTES:
        abort(413)
    datei = request.files.get("sqlite_datei")  # wirft 413, wenn der Upload das Limit sprengt
    if not datei or not datei.filename:
        return _api_fehler("Bitte eine .sqlite-Termin-Datei im Feld sqlite_datei senden.", 400)
    if not datei.filename.lower().endswith(".sqlite"):
        return _api_fehler("Das ist keine .sqlite-Termin-Datei.", 400)

    conn = _postgres_verbindung()
    temp_pfad = _hochgeladene_termin_datei_speichern(datei)
    try:
        try:
            sqlite_conn = db.init_db(temp_pfad)
        except sqlite3.Error:
            return _api_fehler("Diese Datei ist keine gültige SHS-Termin-Datei.", 400)
        try:
            dublette_hinweis = _dublette_hinweis_pruefen(conn, db.get_veranstaltung(sqlite_conn))
            termin = db.exportiere_termin_nach_postgres(sqlite_conn, conn)
        except Exception:
            app.logger.exception("Veröffentlichen über die API fehlgeschlagen")
            return _api_fehler("Das Veröffentlichen ist auf dem Server fehlgeschlagen.", 500)
        finally:
            sqlite_conn.close()
    finally:
        try:
            os.remove(temp_pfad)
        except FileNotFoundError:
            pass
    antwort = jsonify({"termin": _termin_json(termin), "dublette_hinweis": dublette_hinweis})
    antwort.status_code = 201
    return antwort


@api.get("/termine/<schema_name>/ergebnisse")
@_api_admin_erforderlich
def api_termin_ergebnisse(schema_name):
    """GET /api/termine/<schema_name>/ergebnisse - Teilnehmer und Web-Ergebnisse eines
    Termins, so dass der Desktop importiere_ergebnisse_nach_startnummer (db_sync.py) ohne
    zweite Datenbankverbindung ausführen kann.

    Antwort 200: {"teilnehmer": [ {"startnummer": int|null, "nachname": str,
    "vorname": str, "rufname_hund": str, "art": "ED"|"DK", "stufe": 1|2|3,
    "disziplin": "Trümmerfeld"|"Flächensuche"|"Behältnisstrecke"|null,
    "ergebnis": {...}|null}, ... ]}, sortiert nach Startnummer.
    "ergebnis" enthält alle Spalten der Tabelle ergebnisse: teilnehmer_id (Web-seitige ID,
    für den Desktop ohne Bedeutung), suche_truemmerfeld, anzeige_truemmerfeld,
    suche_flaechensuche, anzeige_flaechensuche, suche_behaeltnis, anzeige_behaeltnis
    (je int|null), disqualifiziert, abbruch (0/1), abbruch_grund (str|null),
    stechen_sieger (0/1); null, falls zum Teilnehmer keine Ergebniszeile existiert.
    Fehler: 404 (Schema-Name ungültig oder kein veröffentlichter Termin)."""
    conn = _postgres_verbindung()
    try:
        db._pruefe_schema_name(schema_name)
    except ValueError:
        return _api_fehler("Termin nicht gefunden.", 404)
    if schema_name not in {t.schema_name for t in db.liste_termine_postgres(conn)}:
        return _api_fehler("Termin nicht gefunden.", 404)
    db.oeffne_termin_postgres(conn, schema_name)
    teilnehmer = []
    for t in db.list_teilnehmer(conn):
        ergebnis = db.get_ergebnis(conn, t["id"])
        teilnehmer.append({
            "startnummer": t.get("startnummer"),
            "nachname": t.get("nachname"),
            "vorname": t.get("vorname"),
            "rufname_hund": t.get("rufname_hund"),
            "art": t.get("art"),
            "stufe": t.get("stufe"),
            "disziplin": t.get("disziplin"),
            "ergebnis": None if ergebnis is None else {k: _json_wert(v) for k, v in ergebnis.items()},
        })
    return jsonify({"teilnehmer": teilnehmer})


app.register_blueprint(api)


if __name__ == "__main__":
    # Nur für lokale Tests/Entwicklung - der echte Einsatz am Prüfungstag läuft über
    # einen WSGI-Server (z.B. waitress/gunicorn) innerhalb des geplanten Podman-Containers,
    # nicht über den eingebauten Flask-Entwicklungsserver. Ohne HTTPS-Proxy davor wäre ein
    # Secure-Cookie nie anmeldbar: der Entwicklungsserver setzt es deshalb auf "aus", außer
    # SHS_WEB_COOKIE_SECURE ist ausdrücklich gesetzt.
    if "SHS_WEB_COOKIE_SECURE" not in os.environ:
        app.config["SESSION_COOKIE_SECURE"] = False
    app.run(host="0.0.0.0", port=5000, debug=False)
