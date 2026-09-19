"""
Web-Backend für die geplante PostgreSQL/Podman-Variante des SHS-Prüfungsprogramms
(Mehrbenutzerzugriff am Prüfungstag) - siehe Fortschritt.md für den Architektur-
Hintergrund (Weg B: ein PostgreSQL-Schema je Termin) und db.py für die eigentliche
Datenschicht (init_db_postgres(), die Terminverwaltung ab erstelle_termin_postgres()
sowie den SQLite<->Postgres-Austausch ab exportiere_termin_nach_postgres()).

Umfang dieser ersten Ausbaustufe (V1, mit dem Nutzer abgestimmt): NUR Ergebniseingabe.
Termin anlegen, Teilnehmerverwaltung, Zeitplan und PDF-Export bleiben vorerst
Desktop-Aufgaben vor/nach dem Prüfungstag - ein Termin wird dafür über
sync_termin.py export einmalig aus einer SQLite-Datei nach PostgreSQL veröffentlicht und
nach der Prüfung per sync_termin.py import wieder zurückgeholt.

Anmeldung: EIN gemeinsamer, sechsstelliger Zugangscode je Termin (kein Login mit
Benutzername/Passwort je Richter) - passt zum Ablauf am Prüfungstag (siehe
db.pruefe_zugangscode_postgres()). Damit lässt sich zwar nicht nachvollziehen, WER genau
einen Eintrag gemacht hat, das wurde bei der Abstimmung aber bewusst in Kauf genommen.

Deployment-Annahme (ebenfalls abgestimmt): läuft NUR im lokalen Vereins-Netzwerk am
Prüfungstag, nicht öffentlich aus dem Internet erreichbar - deshalb bewusst kein externes
CSS/JS/Font-CDN in den Templates (könnte am Veranstaltungsort ohne Internetzugang gar
nicht geladen werden) und kein eigenes HTTPS/TLS in diesem Modul (ein Reverse-Proxy davor
wäre bei Bedarf Aufgabe des Deployments, nicht dieses Prototyps).

Jede Anfrage bekommt ihre eigene, kurzlebige PostgreSQL-Verbindung (siehe
_postgres_verbindung()/_verbindung_schliessen() unten) statt einer global geteilten -
einfacher als ein Connection-Pool und unproblematisch bei der hier erwarteten
Nutzerzahl (eine Handvoll Richter an einem Prüfungstag), vermeidet aber auch, dass
sich `SET search_path` (siehe db._setze_termin_suchpfad) verschiedener gleichzeitiger
Anfragen in die Quere kommt.
"""

from __future__ import annotations

import os
import secrets
from functools import wraps

from flask import Flask, abort, g, redirect, render_template, request, session, url_for

import db

app = Flask(__name__)

# Verbindungsstring zum gemeinsamen PostgreSQL-Server - siehe db.verbinde_postgres_server()
# für das Format. Bewusst über eine Umgebungsvariable statt hart im Code, analog zu
# SHS_TEST_POSTGRES_DSN in test_db.py.
app.config["SHS_POSTGRES_DSN"] = os.environ.get("SHS_POSTGRES_DSN", "")

# Signaturschlüssel für die Session-Cookies (Flask signiert damit, verschlüsselt aber
# NICHT den Cookie-Inhalt - dort landet ohnehin nur der Schema-Name, kein Geheimnis).
# Ohne gesetzte Umgebungsvariable wird bei jedem Programmstart ein neuer, zufälliger
# Schlüssel erzeugt - bequem zum Ausprobieren, hat aber zur Folge, dass alle
# angemeldeten Richter nach einem Neustart des Web-Servers den Zugangscode erneut
# eingeben müssen. Für den echten Einsatz am Prüfungstag SHS_WEB_SECRET_KEY fest setzen
# (z.B. per `python -c "import secrets; print(secrets.token_hex(32))"` einmalig erzeugen).
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


def _termin_erforderlich(view):
    """Decorator für alle Ansichten, die einen erfolgreich per Zugangscode angemeldeten
    Termin voraussetzen - wechselt die Verbindung vorab auf dessen Schema (siehe
    db.oeffne_termin_postgres()) und reicht conn als ersten Parameter durch, damit die
    Ansichten selbst ganz normal die db.py-Funktionen aufrufen können."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        schema_name = session.get("schema_name")
        if not schema_name:
            return redirect(url_for("login"))
        conn = _postgres_verbindung()
        db.oeffne_termin_postgres(conn, schema_name)
        return view(conn, *args, **kwargs)
    return wrapper


@app.route("/", methods=["GET", "POST"])
def login():
    fehler = None
    if request.method == "POST":
        code = request.form.get("zugangscode", "")
        schema_name = db.pruefe_zugangscode_postgres(_postgres_verbindung(), code)
        if schema_name:
            session.clear()
            session["schema_name"] = schema_name
            return redirect(url_for("teilnehmerliste"))
        fehler = "Zugangscode nicht erkannt. Bitte erneut versuchen."
    return render_template("login.html", fehler=fehler)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


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
