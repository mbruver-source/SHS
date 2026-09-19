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
import tempfile
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


def _login_erforderlich(view):
    """Decorator für alle Ansichten, die ein angemeldetes Benutzerkonto voraussetzen
    (egal ob Admin oder "nur Eintragen") - Gegenstück zum früheren, rein
    zugangscodebasierten _termin_erforderlich (siehe unten)."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("benutzername"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


def _admin_erforderlich(view):
    """Decorator für die Benutzerverwaltung ('/admin/benutzer') - setzt zusätzlich zu
    _login_erforderlich voraus, dass das angemeldete Konto ein Administrator ist (siehe
    Entscheidung "zwei Rollen: Admin + Eintragen", db.py). Nicht-Admins bekommen 403 statt
    einer Weiterleitung zum Login, da sie ja bereits angemeldet sind."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("benutzername"):
            return redirect(url_for("login"))
        if not session.get("ist_admin"):
            abort(403)
        return view(*args, **kwargs)
    return wrapper


def _termin_erforderlich(view):
    """Decorator für alle Ansichten, die zusätzlich zum Login (siehe _login_erforderlich)
    einen ausgewählten Termin voraussetzen (siehe termin_waehlen() unten) - wechselt die
    Verbindung vorab auf dessen Schema (siehe db.oeffne_termin_postgres()) und reicht conn
    als ersten Parameter durch, damit die Ansichten selbst ganz normal die
    db.py-Funktionen aufrufen können."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("benutzername"):
            return redirect(url_for("login"))
        schema_name = session.get("schema_name")
        if not schema_name:
            return redirect(url_for("termin_waehlen"))
        conn = _postgres_verbindung()
        db.oeffne_termin_postgres(conn, schema_name)
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
            db.benutzer_anlegen(conn, benutzername, passwort, ist_admin=(rolle == "admin"))
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
_ausstehende_downloads: dict[str, tuple[str, str]] = {}


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
        sqlite_conn = db.init_db(temp_pfad)
        try:
            termin = db.exportiere_termin_nach_postgres(sqlite_conn, conn)
        finally:
            sqlite_conn.close()
    finally:
        os.remove(temp_pfad)

    return render_template(
        "admin_termine.html", termine=db.liste_termine_postgres(conn),
        veroeffentlicht=termin,
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
    _ausstehende_downloads[token] = (temp_pfad, download_name)

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
    temp_pfad, download_name = eintrag
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
        suche_text = _feld_zu_text(formular, f"suche_{disziplin}")
        anzeige_text = _feld_zu_text(formular, f"anzeige_{disziplin}")
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


@app.route("/teilnehmer/<int:teilnehmer_id>", methods=["GET", "POST"])
@_termin_erforderlich
def ergebnis_erfassen(conn, teilnehmer_id):
    teilnehmer = db.get_teilnehmer(conn, teilnehmer_id)
    if teilnehmer is None:
        abort(404)
    disziplinen = [teilnehmer["disziplin"]] if teilnehmer["art"] == "ED" else db.ALLE_DISZIPLINEN

    fehler = None
    if request.method == "POST":
        werte, fehler = _pruefe_und_parse_formular(request.form, disziplinen)
        if fehler is None:
            for disziplin, (suche, anzeige) in werte.items():
                db.eintragen_ergebnis(conn, teilnehmer_id, disziplin, suche, anzeige)
            return redirect(url_for("teilnehmerliste"))

    ergebnis = db.get_ergebnis(conn, teilnehmer_id) or {}
    zeilen = []
    for disziplin in disziplinen:
        spalte_suche, spalte_anzeige = db.DISZIPLIN_SPALTEN[disziplin]
        zeilen.append({
            "disziplin": disziplin,
            "suche": ergebnis.get(spalte_suche),
            "anzeige": ergebnis.get(spalte_anzeige),
        })
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
