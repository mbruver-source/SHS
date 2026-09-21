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
gar nicht geladen werden) und kein eigenes HTTPS/TLS in diesem Modul (ein Reverse-Proxy
davor wäre bei Bedarf Aufgabe des Deployments, nicht dieses Prototyps).

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
from functools import wraps

from flask import Flask, abort, g, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

import db
from version import VERSION

app = Flask(__name__)


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
    erwartet = session.get("csrf_token")
    erhalten = request.form.get("csrf_token", "")
    if not erwartet or not secrets.compare_digest(erwartet, erhalten):
        abort(403)

# Verbindungsstring zum gemeinsamen PostgreSQL-Server - siehe db.verbinde_postgres_server()
# für das Format. Bewusst über eine Umgebungsvariable statt hart im Code, analog zu
# SHS_TEST_POSTGRES_DSN in test_db.py.
app.config["SHS_POSTGRES_DSN"] = os.environ.get("SHS_POSTGRES_DSN", "")

# Signaturschlüssel für die Session-Cookies (Flask signiert damit, verschlüsselt aber
# NICHT den Cookie-Inhalt - dort landen Benutzername/Admin-Kennzeichen/Schema-Name, aber
# nie ein Passwort oder Passwort-Hash). Ohne gesetzte Umgebungsvariable wird bei jedem
# Programmstart ein neuer, zufälliger Schlüssel erzeugt - bequem zum Ausprobieren, hat
# aber zur Folge, dass sich alle angemeldeten Richter nach einem Neustart des
# Web-Servers erneut mit Benutzername/Passwort anmelden müssen. Für den echten Einsatz
# am Prüfungstag SHS_WEB_SECRET_KEY fest setzen (z.B. per
# `python -c "import secrets; print(secrets.token_hex(32))"` einmalig erzeugen).
app.secret_key = os.environ.get("SHS_WEB_SECRET_KEY") or secrets.token_hex(32)

# Explizit gesetzt statt sich auf den Flask-Standard zu verlassen (QS-Review 19./20.09.):
# "Lax" schickt das Session-Cookie bei einer normalen Navigation zu dieser Seite (Link/
# Tippen der Adresse/Lesezeichen) weiterhin mit, aber NICHT bei einer von einer fremden
# Seite AUSGELÖSTEN Anfrage (z. B. einem automatisch abgeschickten Formular oder einem
# eingebetteten Bild/iframe) - zusätzlich zum CSRF-Token oben eine zweite, unabhängige
# Absicherungsebene, die auch dann noch greift, falls irgendeine künftige Route das
# Token einmal vergisst zu prüfen. Bewusst NICHT SESSION_COOKIE_SECURE=True gesetzt: die
# Web-Version läuft laut Modul-Docstring oben ohne eigenes HTTPS/TLS im lokalen
# Vereinsnetz - mit Secure=True würde der Browser das Cookie über die dann übliche
# HTTP-Verbindung gar nicht erst mitschicken und niemand könnte sich mehr anmelden.
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


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
        g.postgres_conn = db.verbinde_postgres_server(dsn)
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
    if konto is None:
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
        if request.method == "POST":
            benutzername = request.form.get("benutzername", "").strip()
            passwort = request.form.get("passwort", "")
            passwort_wiederholung = request.form.get("passwort_wiederholung", "")
            fehler = _pruefe_benutzername_und_passwort(benutzername, passwort, passwort_wiederholung)
            if fehler is None:
                # False nur im seltenen Fall, dass zwischenzeitlich (z. B. zwei parallel
                # geöffnete Ersteinrichtungs-Formulare) bereits ein Administrator angelegt
                # wurde - dann ganz normal zum Login weiter, statt einen zweiten "ersten"
                # Administrator anzulegen (siehe db.admin_einrichten).
                if db.admin_einrichten(conn, benutzername, passwort):
                    session.clear()
                    session["benutzername"] = benutzername
                    session["ist_admin"] = True
                    return redirect(url_for("termin_waehlen"))
                return redirect(url_for("login"))
        return render_template("ersteinrichtung.html", fehler=fehler)

    if request.method == "POST":
        benutzername = request.form.get("benutzername", "")
        passwort = request.form.get("passwort", "")
        konto = db.pruefe_login(conn, benutzername, passwort)
        if konto:
            session.clear()
            session["benutzername"] = konto["benutzername"]
            session["ist_admin"] = konto["ist_admin"]
            return redirect(url_for("termin_waehlen"))
        fehler = "Benutzername oder Passwort falsch. Bitte erneut versuchen."
    return render_template("login.html", fehler=fehler)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


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
                return redirect(url_for("admin_benutzer"))
    return render_template("admin_benutzer.html", benutzer=db.liste_benutzer(conn), fehler=fehler)


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
    datei.save(temp_pfad)
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
                f"„{veranstaltung['verein']}“ am {veranstaltung['datum']} "
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
    db.loesche_termin_postgres(_postgres_verbindung(), schema_name)
    # Falls der Administrator gerade selbst mit diesem (jetzt gelöschten) Termin arbeitet,
    # die Auswahl zurücksetzen - sonst würde der nächste Aufruf einer
    # "_termin_erforderlich"-Ansicht auf ein nicht mehr existierendes Schema treffen.
    if session.get("schema_name") == schema_name:
        session.pop("schema_name", None)
    return redirect(url_for("admin_termine"))


@app.route("/teilnehmer")
@_termin_erforderlich
def teilnehmerliste(conn):
    veranstaltung = db.get_veranstaltung(conn)
    alle_teilnehmer = db.list_teilnehmer(conn)
    _, ausstehend = db.berechne_auswertung(conn)
    offene_ids = {t["id"] for t in ausstehend}
    zeilen = [
        {
            "teilnehmer": t,
            "label": db.leistungsklasse_label(t),
            "vollstaendig": t["id"] not in offene_ids,
        }
        for t in alle_teilnehmer
    ]
    return render_template("teilnehmerliste.html", veranstaltung=veranstaltung, zeilen=zeilen)


def _feld_zu_text(formular, name: str) -> str:
    return (formular.get(name) or "").strip()


def _disziplin_text_werte(formular, disziplin: str) -> tuple[str, str]:
    """Rohe (nicht geparste) Formulartexte einer Disziplin - gemeinsame Grundlage sowohl
    für die Validierung (_pruefe_und_parse_formular) als auch für den
    Lost-Update-Vergleich (siehe _geladene_werte_aus_formular/ergebnis_erfassen)."""
    return _feld_zu_text(formular, f"suche_{disziplin}"), _feld_zu_text(formular, f"anzeige_{disziplin}")


def _pruefe_und_parse_formular(formular, disziplinen: list[str]) -> tuple[dict, str | None]:
    """Parst und validiert die Formularfelder einer Ergebniserfassung. Liefert
    (Werte je Disziplin als {disziplin: (suche, anzeige)}, Fehlertext oder None).

    Die Wertebereiche (0-60 Suchleistung, 0-40 Anzeigeleistung) werden hier bewusst
    VOR dem Speichern geprüft, nicht erst über die CHECK-Constraints der Datenbank
    abgefangen - eine fehlgeschlagene Anweisung würde bei PostgreSQL sonst die laufende
    Transaktion in einen Fehlerzustand versetzen (erst durch ROLLBACK wieder nutzbar,
    das der schlanke _PostgresConnection-Wrapper in db.py nicht anbietet - siehe dort).
    Da hier ohnehin für jede Anfrage eine frische Verbindung verwendet wird (siehe
    _postgres_verbindung), wäre das zwar unkritisch, sauberer und mit besserer
    Fehlermeldung für die Richter ist aber, das erst gar nicht so weit kommen zu lassen."""
    werte: dict[str, tuple[int | None, int | None]] = {}
    for disziplin in disziplinen:
        suche_text, anzeige_text = _disziplin_text_werte(formular, disziplin)
        try:
            suche = int(suche_text) if suche_text else None
            anzeige = int(anzeige_text) if anzeige_text else None
        except ValueError:
            return {}, f"Bitte bei {disziplin} nur Zahlen eintragen."
        if suche is not None and not (0 <= suche <= 60):
            return {}, f"Suchleistung {disziplin}: nur Werte von 0 bis 60 möglich."
        if anzeige is not None and not (0 <= anzeige <= 40):
            return {}, f"Anzeigeleistung {disziplin}: nur Werte von 0 bis 40 möglich."
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
    (Richter hat diese Disziplin tatsächlich bearbeitet), wird wie bisher gespeichert."""
    teilnehmer = db.get_teilnehmer(conn, teilnehmer_id)
    if teilnehmer is None:
        abort(404)
    disziplinen = [teilnehmer["disziplin"]] if teilnehmer["art"] == "ED" else db.ALLE_DISZIPLINEN

    fehler = None
    if request.method == "POST":
        werte, fehler = _pruefe_und_parse_formular(request.form, disziplinen)
        if fehler is None:
            geladene_werte = _geladene_werte_aus_formular(request.form, disziplinen)
            for disziplin, (suche, anzeige) in werte.items():
                aktuell = _disziplin_text_werte(request.form, disziplin)
                geladen = geladene_werte[disziplin]
                if None not in geladen and aktuell == geladen:
                    # Diese Disziplin wurde vom aktuellen Richter nicht verändert - siehe
                    # Funktionsdocstring (Lost-Update-Schutz).
                    continue
                db.eintragen_ergebnis(conn, teilnehmer_id, disziplin, suche, anzeige)
            return redirect(url_for("teilnehmerliste"))
        # Fehlerfall: Seite mit den gerade abgeschickten (nicht den gespeicherten) Werten
        # neu aufbauen, siehe _zeilen_aus_formular.
        zeilen = _zeilen_aus_formular(request.form, disziplinen)
    else:
        zeilen = _zeilen_aus_ergebnis(db.get_ergebnis(conn, teilnehmer_id) or {}, disziplinen)

    return render_template(
        "ergebnis_erfassen.html",
        teilnehmer=teilnehmer,
        label=db.leistungsklasse_label(teilnehmer),
        zeilen=zeilen,
        fehler=fehler,
    )


if __name__ == "__main__":
    # Nur für lokale Tests/Entwicklung - der echte Einsatz am Prüfungstag läuft über
    # einen WSGI-Server (z.B. waitress/gunicorn) innerhalb des geplanten Podman-Containers,
    # nicht über den eingebauten Flask-Entwicklungsserver.
    app.run(host="0.0.0.0", port=5000, debug=False)
