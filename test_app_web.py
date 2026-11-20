"""Tests für app_web.py - Flask-Backend der Web-Version (V1: Ergebniseingabe, siehe
Modul-Docstring dort für den Architektur-Hintergrund).

Testet die eigentliche Anfragen-Logik (Ersteinrichtung/Login mit Benutzerkonten,
Termin-Auswahl, Benutzerverwaltung, Termin veröffentlichen/zurückholen per Upload,
Teilnehmerliste, Ergebnis erfassen inkl. Validierung) mit dem Flask-Test-Client GEGEN EINE
ECHTE, temporäre SQLite-Termin-Datei (über db.init_db() - dieselbe, bereits in test_db.py
ausführlich geprüfte Fachlogik wie die Desktop-Version). Nur die PostgreSQL-spezifischen
"Klebefunktionen" (verbinde_postgres_server/oeffne_termin_postgres/liste_termine_postgres/
loesche_termin_postgres/exportiere_termin_nach_postgres/importiere_ergebnisse_aus_postgres/
_setze_termin_suchpfad) werden dafür durch einfache Ersatzfunktionen ausgetauscht, die
stattdessen mit der SQLite-Datei arbeiten bzw. eine von den Tests steuerbare Termin-Liste/
ein steuerbares Veröffentlichen-Ergebnis/einen steuerbaren Übertragungsbericht liefern -
diese Funktionen selbst sind bereits in test_db.py (TestTerminverwaltungPostgres/
TestBenutzerkontenPostgres/TestTerminSyncPostgres) gegen einen echten PostgreSQL-Server
geprüft. Der Datei-Upload/-Download selbst (app_web._hochgeladene_termin_datei_speichern/
send_file) läuft dagegen echt, mit einer harmlosen leeren .sqlite-Datei als Upload-Inhalt
(eine 0-Byte-Datei ist eine gültige, leere SQLite-Datenbank).

Die eigentliche Konten-Logik (gibt_es_admin/admin_einrichten/benutzer_anlegen/
benutzer_loeschen/liste_benutzer/pruefe_login) wird dagegen NICHT gemockt, sondern läuft
für echt gegen die SQLite-Testdatei (_setze_termin_suchpfad wird dafür durch einen No-Op
ersetzt - SQLite kennt kein "SET search_path", eine einzelne Datei braucht diesen
PostgreSQL-Schema-Wechsel aber ohnehin nicht). So braucht dieses Modul kein installiertes
psycopg2 und läuft überall, deckt aber die komplette übrige Anwendungslogik
(Formularvalidierung, Session, Weiterleitung, Statusanzeige, Rollenprüfung) mit echten
Datenbankzugriffen statt gemockten Rückgabewerten ab."""

import io
import os
import re
import secrets
import sqlite3
import tempfile
import time
import unittest
from html.parser import HTMLParser
from unittest.mock import patch
from urllib.parse import quote
from db_testhilfen import patch_db

from flask.testing import FlaskClient

import app_web
import db

_TEST_SCHEMA = "termin_test"  # Platzhalter - die SQLite-Ersatzfunktion unten ignoriert
                               # den Schema-Namen ohnehin (eine einzelne Datei kennt
                               # keine Schemas/search_path)
_ADMIN_NAME = "chef"
_ADMIN_PASSWORT = "sicheres_passwort"
# Codeprüfung 22.09., G1: Einrichtungs-Code für die Ersteinrichtung (in den Tests über
# app.config statt der Umgebungsvariablen SHS_ADMIN_SETUP_CODE gesetzt, siehe setUp).
_EINRICHTUNGS_CODE = "test-einrichtungs-code"


def _termin_info(schema_name: str, **override) -> db.TerminInfoPostgres:
    werte = {
        "id": 1, "schema_name": schema_name, "verein": None, "ort": None, "datum": None,
        "anzahl_teilnehmer": 0, "erstellt_am": "2026-09-19T00:00:00+00:00",
    }
    werte.update(override)
    return db.TerminInfoPostgres(**werte)


class _NichtSchliessendeVerbindung:
    """Wickelt die eine, für den gesamten Testfall offene SQLite-Verbindung, ignoriert
    aber .close() - im echten Betrieb öffnet/schließt app_web je HTTP-Anfrage eine neue
    PostgreSQL-Verbindung (siehe app_web._postgres_verbindung), hier soll die
    Termin-Datei dagegen über mehrere Anfragen EINES Tests hinweg bestehen bleiben."""
    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        pass


def _fake_oeffne_termin(conn, schema_name):
    pass


def _fake_setze_termin_suchpfad(conn, schema_name):
    pass


def _fake_loesche_termin(fall, conn, schema_name):
    """Ersatz für db.loesche_termin_postgres - entfernt den Termin aus der von den
    Tests steuerbaren self.termine-Liste und protokolliert den Aufruf, statt ein
    echtes "DROP SCHEMA ... CASCADE" auszuführen (SQLite kennt keine Schemas)."""
    fall.geloeschte_termine.append(schema_name)
    fall.termine = [t for t in fall.termine if t.schema_name != schema_name]


def _fake_exportiere_termin(fall, sqlite_conn, postgres_conn):
    """Ersatz für db.exportiere_termin_nach_postgres - liefert das von den Tests
    steuerbare fall.export_ergebnis statt tatsächlich in eine PostgreSQL-Schema zu
    schreiben. Öffnet die hochgeladene Datei aber wirklich (sqlite_conn), damit
    Fehler beim Öffnen selbst (z. B. eine kaputte Datei) real durchschlagen."""
    fall.export_aufrufe.append(sqlite_conn)
    return fall.export_ergebnis


def _fake_importiere_ergebnisse(fall, postgres_conn, schema_name, sqlite_conn):
    """Ersatz für db.importiere_ergebnisse_aus_postgres - liefert den von den Tests
    steuerbaren fall.import_bericht statt echt aus einem PostgreSQL-Schema zu lesen."""
    fall.import_aufrufe.append(schema_name)
    return fall.import_bericht


# TestCsrfSchutz weiter unten braucht bewusst den UNVERÄNDERTEN Flask-Test-Client zurück
# (statt des _CsrfTestClient direkt unten), um den CSRF-Mechanismus selbst zu prüfen -
# siehe dortiger Docstring. app.test_client_class ist standardmäßig None (Flask
# verwendet dann intern FlaskClient) - hier deshalb explizit importiert statt vom
# (noch ungesetzten) Attribut abgeleitet.
class _CsrfTestClient(FlaskClient):
    """Test-Client, der jeder POST-Anfrage automatisch ein gültiges CSRF-Token beilegt
    (siehe app_web._csrf_pruefen/_csrf_token) - genau wie es ein echter Browser hätte,
    der zuvor die Seite mit dem jeweiligen Formular aufgerufen und dessen verstecktes
    csrf_token-Feld übernommen hätte. Ohne das müssten alle ~30 POST-Testaufrufe in
    dieser Datei einzeln um dieses rein technische Feld ergänzt werden, obwohl sie
    eigentlich die FACHLICHE Formularlogik prüfen sollen. Der CSRF-Mechanismus selbst
    (Ablehnung OHNE oder mit FALSCHEM Token) wird unabhängig davon in
    TestCsrfSchutz weiter unten geprüft - dort bewusst OHNE diesen Test-Client."""

    def post(self, *args, **kwargs):
        with self.session_transaction() as sess:
            token = sess.get("csrf_token")
            if not token:
                token = secrets.token_urlsafe(32)
                sess["csrf_token"] = token
        daten = kwargs.get("data")
        if daten is None:
            kwargs["data"] = {"csrf_token": token}
        elif isinstance(daten, dict) and "csrf_token" not in daten:
            kwargs["data"] = {**daten, "csrf_token": token}
        return super().post(*args, **kwargs)


class _AppWebTestBasis(unittest.TestCase):
    """Gemeinsames setUp/tearDown/_anmelden für TestAppWeb UND TestCsrfSchutz weiter
    unten (Testdatenbank, gemockte PostgreSQL-Klebefunktionen, Login-Hilfsfunktion) -
    OHNE eigene test_*-Methoden, damit TestCsrfSchutz nicht versehentlich die komplette
    fachliche Testsuite von TestAppWeb mit dem dortigen, CSRF-Token automatisch
    beilegenden Test-Client noch einmal mitlaufen lässt (siehe dortiger Docstring: dort
    ist genau das ja erwünscht, hier hingegen nicht)."""

    def setUp(self):
        fd, self.pfad = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        os.remove(self.pfad)
        self.conn = db.init_db(self.pfad)
        # web_benutzer existiert normalerweise erst nach verbinde_postgres_server() (hier
        # gemockt) - für die Konten-Tests hier einmalig von Hand in derselben
        # SQLite-Testdatei anlegen. Dieselbe Tabellendefinition wie db._WEB_BENUTZER_SCHEMA,
        # nur ohne das "public."-Präfix (SQLite kennt - anders als PostgreSQL - kein
        # gleichnamiges Schema/keine gleichnamige Datenbank "public").
        self.conn.execute(db._WEB_BENUTZER_SCHEMA.replace("public.web_benutzer", "web_benutzer"))
        # Derselbe zusätzliche Unique-Index wie in verbinde_postgres_server() (siehe dort
        # und db._WEB_BENUTZER_INDEX_BENUTZERNAME_LOWER) - ohne ihn würde die
        # Nebenläufigkeits-Absicherung gegen unterschiedlich geschriebene Benutzernamen in
        # dieser SQLite-Testdatei gar nicht mitgeprüft.
        self.conn.execute(db._WEB_BENUTZER_INDEX_BENUTZERNAME_LOWER)
        # Wer hat wann eingetragen (UX-Test Web 19.11.2026, B6): im Web legt oeffne_termin_postgres die
        # Tabelle an, das hier ersetzt wird - deshalb wie web_benutzer von Hand.
        self.conn.execute(db._WEB_AENDERUNGEN_SCHEMA)

        # Von den Tests steuerbare "aktuell veröffentlichte Termine" für termin_waehlen()
        # - Standard: genau ein Termin (passend zu _TEST_SCHEMA), damit die Auswahl wie
        # bisher automatisch übersprungen wird und bestehende Tests unverändert bis zur
        # Teilnehmerliste durchlaufen.
        self.termine = [_termin_info(_TEST_SCHEMA)]

        # Von den Tests steuerbarer Rückgabewert/Protokoll für die neuen
        # Veröffentlichen/Zurückholen/Löschen-Routen (siehe _fake_*-Funktionen oben).
        self.export_ergebnis = _termin_info(_TEST_SCHEMA, verein="Testverein", anzahl_teilnehmer=3)
        self.export_aufrufe = []
        self.import_bericht = db.ImportBericht(
            aktualisiert=0, ohne_startnummer_uebersprungen=[], nicht_gefunden=[]
        )
        self.import_aufrufe = []
        self.geloeschte_termine = []

        self._patches = [
            patch_db("verbinde_postgres_server", lambda dsn, password=None: _NichtSchliessendeVerbindung(self.conn)),
            patch_db("oeffne_termin_postgres", _fake_oeffne_termin),
            patch_db("liste_termine_postgres", lambda conn: self.termine),
            patch_db("_setze_termin_suchpfad", _fake_setze_termin_suchpfad),
            patch_db("loesche_termin_postgres", lambda conn, schema_name: _fake_loesche_termin(self, conn, schema_name)),
            patch_db("exportiere_termin_nach_postgres", lambda sqlite_conn, postgres_conn: _fake_exportiere_termin(self, sqlite_conn, postgres_conn)),
            patch_db("importiere_ergebnisse_aus_postgres", lambda postgres_conn, schema_name, sqlite_conn: _fake_importiere_ergebnisse(self, postgres_conn, schema_name, sqlite_conn)),
        ]
        for p in self._patches:
            p.start()

        self._alter_einrichtungs_code = app_web.app.config.get("SHS_ADMIN_SETUP_CODE")
        app_web.app.config.update(
            TESTING=True, SHS_POSTGRES_DSN="postgresql://test-dsn", SHS_ADMIN_SETUP_CODE=_EINRICHTUNGS_CODE,
        )
        # _CsrfTestClient statt des normalen Test-Clients - siehe dortiger Docstring:
        # ergänzt jede POST-Anfrage automatisch um ein gültiges CSRF-Token, damit diese
        # Tests weiterhin die fachliche Formularlogik prüfen, ohne an der (separat
        # geprüften) CSRF-Absicherung zu scheitern.
        app_web.app.test_client_class = _CsrfTestClient
        self.client = app_web.app.test_client()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        app_web.app.config["SHS_ADMIN_SETUP_CODE"] = self._alter_einrichtungs_code
        self.conn.close()
        if os.path.exists(self.pfad):
            os.remove(self.pfad)

    def _anmelden(self, benutzername=_ADMIN_NAME, passwort=_ADMIN_PASSWORT):
        """Richtet bei Bedarf den ersten Administrator ein (siehe _ersteinrichtung) und
        meldet ihn an - mit dem Standard-self.termine (genau ein Termin) landet man damit
        direkt auf der Teilnehmerliste, wie es die bestehenden Tests unten erwarten."""
        return self.client.post(
            "/",
            data={
                "benutzername": benutzername, "passwort": passwort, "passwort_wiederholung": passwort,
                "einrichtungs_code": _EINRICHTUNGS_CODE,
            },
            follow_redirects=True,
        )


class TestAppWeb(_AppWebTestBasis):
    # --- Ersteinrichtung ---------------------------------------------------------

    def test_ersteinrichtung_wird_angezeigt_wenn_kein_admin_existiert(self):
        antwort = self.client.get("/")
        self.assertIn("Ersteinrichtung".encode(), antwort.data)

    def test_ersteinrichtung_legt_admin_an_und_meldet_direkt_an(self):
        antwort = self._anmelden()
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("Teilnehmer".encode(), antwort.data)
        self.assertTrue(db.gibt_es_admin(self.conn))

    def test_ersteinrichtung_lehnt_zu_kurzes_passwort_ab(self):
        antwort = self.client.post(
            "/", data={
                "benutzername": _ADMIN_NAME, "passwort": "kurz", "passwort_wiederholung": "kurz",
                "einrichtungs_code": _EINRICHTUNGS_CODE,
            }
        )
        self.assertIn("mindestens 8 Zeichen".encode(), antwort.data)
        self.assertFalse(db.gibt_es_admin(self.conn))

    def test_ersteinrichtung_lehnt_unterschiedliche_passwoerter_ab(self):
        antwort = self.client.post(
            "/",
            data={
                "benutzername": _ADMIN_NAME, "passwort": _ADMIN_PASSWORT, "passwort_wiederholung": "anders123",
                "einrichtungs_code": _EINRICHTUNGS_CODE,
            },
        )
        self.assertIn("stimmen nicht überein".encode(), antwort.data)
        self.assertFalse(db.gibt_es_admin(self.conn))

    # Codeprüfung 22.09., G1: Ersteinrichtung nur mit dem Einrichtungs-Code aus
    # SHS_ADMIN_SETUP_CODE (hier über app.config gesetzt, siehe setUp).

    def _ersteinrichtung_mit_code(self, code):
        daten = {"benutzername": _ADMIN_NAME, "passwort": _ADMIN_PASSWORT, "passwort_wiederholung": _ADMIN_PASSWORT}
        if code is not None:
            daten["einrichtungs_code"] = code
        return self.client.post("/", data=daten)

    def test_ersteinrichtung_mit_falschem_code_legt_keinen_admin_an(self):
        antwort = self._ersteinrichtung_mit_code("falscher-code")
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("Einrichtungs-Code ist falsch".encode(), antwort.data)
        self.assertFalse(db.gibt_es_admin(self.conn))

    def test_ersteinrichtung_ohne_code_feld_legt_keinen_admin_an(self):
        antwort = self._ersteinrichtung_mit_code(None)
        self.assertIn("Einrichtungs-Code ist falsch".encode(), antwort.data)
        self.assertFalse(db.gibt_es_admin(self.conn))

    def test_ersteinrichtung_mit_nicht_ascii_code_liefert_fehler_statt_absturz(self):
        # secrets.compare_digest wirft bei str mit Nicht-ASCII-Zeichen einen TypeError -
        # deshalb vergleicht login() Bytes (siehe dortiger Kommentar).
        antwort = self._ersteinrichtung_mit_code("Prüfung-ä")
        self.assertEqual(antwort.status_code, 200)
        self.assertFalse(db.gibt_es_admin(self.conn))

    def test_ersteinrichtung_mit_richtigem_code_legt_admin_an(self):
        antwort = self._ersteinrichtung_mit_code(_EINRICHTUNGS_CODE)
        self.assertEqual(antwort.status_code, 302)
        self.assertTrue(db.gibt_es_admin(self.conn))

    def test_ersteinrichtung_ohne_konfigurierten_code_wird_verweigert(self):
        for nicht_konfiguriert in ("", None):
            with self.subTest(code=nicht_konfiguriert):
                app_web.app.config["SHS_ADMIN_SETUP_CODE"] = nicht_konfiguriert
                seite = self.client.get("/")
                self.assertIn("Ersteinrichtung ist gesperrt".encode(), seite.data)
                self.assertNotIn(b'name="benutzername"', seite.data)
                # Auch ein leer mitgeschickter Code darf gegen einen leeren
                # "konfigurierten" Code NICHT als Treffer durchgehen.
                antwort = self._ersteinrichtung_mit_code("")
                self.assertIn("Ersteinrichtung ist gesperrt".encode(), antwort.data)
                self.assertFalse(db.gibt_es_admin(self.conn))

    def test_normaler_login_erscheint_sobald_admin_existiert(self):
        self._anmelden()
        self.client.post("/logout")
        antwort = self.client.get("/")
        self.assertNotIn("Ersteinrichtung".encode(), antwort.data)
        self.assertIn("Benutzername".encode(), antwort.data)

    # --- Login ---------------------------------------------------------------

    def test_login_mit_falschem_passwort_zeigt_fehler(self):
        self._anmelden()
        self.client.post("/logout")
        antwort = self.client.post("/", data={"benutzername": _ADMIN_NAME, "passwort": "falsches_passwort"})
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("falsch".encode(), antwort.data)

    def test_login_mit_unbekanntem_benutzer_zeigt_denselben_fehler(self):
        self._anmelden()
        self.client.post("/logout")
        antwort = self.client.post("/", data={"benutzername": "gibtsnicht", "passwort": "irgendwas123"})
        self.assertIn("falsch".encode(), antwort.data)

    def test_login_ignoriert_gross_und_kleinschreibung_beim_benutzernamen(self):
        # Praxisfall (siehe db.pruefe_login): ein Konto wurde z. B. als "chef" angelegt,
        # beim Anmelden - insbesondere auf Mobilgeräten mit automatischer
        # Groß-/Kleinschreibung des ersten Buchstabens - wird aber "Chef" eingegeben.
        self._anmelden()
        self.client.post("/logout")
        antwort = self.client.post(
            "/",
            data={"benutzername": _ADMIN_NAME.upper(), "passwort": _ADMIN_PASSWORT},
            follow_redirects=True,
        )
        self.assertNotIn("falsch".encode(), antwort.data)
        self.assertIn("Teilnehmer".encode(), antwort.data)

    def test_login_ruft_check_password_hash_auch_bei_unbekanntem_benutzernamen_auf(self):
        """QS-Fund 21.09. (Timing-Seitenkanal): db.pruefe_login() rief
        check_password_hash() (teures PBKDF2) früher NUR bei bekanntem Benutzernamen
        auf - bei unbekanntem Benutzernamen kam der Funktionsaufruf gar nicht erst
        zustande, die Antwortzeit unterschied sich dadurch messbar. Prüft hier direkt
        (statt über eine im CI unzuverlässige Zeitmessung), dass jetzt in BEIDEN Fällen
        genau einmal check_password_hash() aufgerufen wird - bei unbekanntem
        Benutzernamen gegen den in db._DUMMY_PASSWORT_HASH einmalig erzeugten
        Dummy-Hash."""
        self._anmelden()
        with patch("werkzeug.security.check_password_hash", return_value=False) as mock_check:
            self.assertIsNone(db.pruefe_login(self.conn, "gibtsnicht", "irgendwas123"))
            self.assertEqual(mock_check.call_count, 1)
            self.assertIsNone(db.pruefe_login(self.conn, _ADMIN_NAME, "falsches_passwort"))
            self.assertEqual(mock_check.call_count, 2)

    def test_teilnehmerliste_ohne_login_leitet_zum_login(self):
        antwort = self.client.get("/teilnehmer")
        self.assertEqual(antwort.status_code, 302)

    # --- UX-Test Web 19.11.2026: U4 (A2, A3, B1, F3) -----------------------------------

    def test_startseite_leitet_angemeldete_weiter(self):
        self._anmelden()  # genau ein Termin: der ist gewählt
        antwort = self.client.get("/")
        self.assertEqual(antwort.status_code, 302)
        self.assertTrue(antwort.headers["Location"].endswith("/teilnehmer"), antwort.headers["Location"])
        with self.client.session_transaction() as sitzung:
            sitzung.pop("schema_name", None)
        antwort = self.client.get("/")
        self.assertEqual(antwort.status_code, 302)
        self.assertIn("/termin-waehlen", antwort.headers["Location"])

    def test_startseite_zeigt_formular_bei_veralteter_sitzung(self):
        self._anmelden()
        db.benutzer_anlegen(self.conn, "helfer", "helferpasswort")
        self.client.post("/logout")
        self.client.post("/", data={"benutzername": "helfer", "passwort": "helferpasswort"})
        db.benutzer_loeschen(self.conn, "helfer")
        antwort = self.client.get("/")
        self.assertEqual(antwort.status_code, 200)
        self.assertIn('name="passwort"', antwort.data.decode())
        with self.client.session_transaction() as sitzung:
            self.assertNotIn("benutzername", sitzung)

    def test_startseite_mit_geloeschtem_termin_endet_bei_terminauswahl(self):
        self._anmelden()
        with self.client.session_transaction() as sitzung:
            sitzung["schema_name"] = "termin_gibt_es_nicht"
        original = app_web.db.oeffne_termin_postgres

        def oeffnen(conn, schema_name):
            if schema_name == "termin_gibt_es_nicht":
                raise RuntimeError("Schema fehlt")
            return original(conn, schema_name)

        # Kette: / -> /teilnehmer (veraltetes Schema wird entfernt) -> /termin-waehlen -> /teilnehmer
        # mit dem einzigen echten Termin; endet nach wenigen Schritten (keine Schleife).
        pfade = []
        with patch.object(app_web.db, "oeffne_termin_postgres", side_effect=oeffnen):
            adresse = "/"
            for _ in range(6):
                antwort = self.client.get(adresse)
                pfade.append(adresse)
                if antwort.status_code != 302:
                    break
                adresse = antwort.headers["Location"]
        self.assertEqual(antwort.status_code, 200, pfade)
        self.assertEqual(pfade, ["/", "/teilnehmer", "/termin-waehlen", "/teilnehmer"])

    def test_terminauswahl_ohne_termin_knopf_nur_fuer_admins(self):
        self.termine = []
        self._anmelden()
        db.benutzer_anlegen(self.conn, "helfer", "helferpasswort")
        self.client.post("/logout")
        antwort = self.client.post("/", data={"benutzername": "helfer", "passwort": "helferpasswort"},
                                   follow_redirects=True)
        html = antwort.data.decode()
        self.assertIn("kein Termin veröffentlicht", html)
        self.assertNotIn('<a class="knopf" href="/admin/termine">', html)

    def test_startseite_ohne_anmeldung_zeigt_formular(self):
        self._anmelden()
        self.client.post("/logout")
        antwort = self.client.get("/")
        self.assertEqual(antwort.status_code, 200)
        self.assertIn('name="passwort"', antwort.data.decode())

    def test_navigation_termine_verwalten_eindeutig(self):
        self._anmelden()
        html = self.client.get("/teilnehmer").data.decode()
        self.assertIn(">Termine verwalten</a>", html)
        self.assertIn(">Termin wechseln</a>", html)
        self.assertNotIn(">Termine</a>", html)

    def test_meldung_nach_benutzer_anlegen(self):
        self._anmelden()
        antwort = self.client.post("/admin/benutzer", data={
            "benutzername": "helfer", "passwort": "helferpasswort",
            "passwort_wiederholung": "helferpasswort", "rolle": "eintragen"})
        self.assertEqual(antwort.status_code, 302)
        html = self.client.get(antwort.headers["Location"]).data.decode()
        self.assertIn("Benutzer „helfer“ wurde angelegt.", html)
        # Kein beliebiger Text über die Adresse: nur existierende Konten werden gemeldet.
        html = self.client.get("/admin/benutzer?angelegt=gibtsnicht").data.decode()
        self.assertNotIn("wurde angelegt", html)

    def test_einrichtungs_code_ist_sichtbar(self):
        html = self.client.get("/").data.decode()
        self.assertRegex(html, r'<input type="text" id="einrichtungs_code"')
        self.assertIn('<input type="password" id="passwort"', html)

    def test_logout_per_get_meldet_nicht_ab(self):
        """S-6: Abmelden nur per POST mit CSRF-Token - ein GET (z. B. über ein Bild auf
        einer fremden Seite) beendet die Sitzung nicht."""
        self._anmelden()
        antwort = self.client.get("/logout")
        self.assertEqual(antwort.status_code, 405)
        self.assertEqual(self.client.get("/teilnehmer").status_code, 200)

    def test_abmelde_formular_mit_csrf_token(self):
        self._anmelden()
        seite = self.client.get("/teilnehmer").data.decode()
        self.assertRegex(
            seite,
            r'<form class="abmelden" method="post" action="/logout">\s*'
            r'<input type="hidden" name="csrf_token" value="[^"]+">',
        )

    def test_sicherheits_header_in_jeder_antwort(self):
        """S-6: Schutz-Header gegen Einbetten, MIME-Raten, Caching und fremde Skripte."""
        for antwort in (self.client.get("/"), self.client.get("/teilnehmer")):
            with self.subTest(pfad=antwort.request.path):
                self.assertEqual(antwort.headers["X-Frame-Options"], "DENY")
                self.assertEqual(antwort.headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(antwort.headers["Cache-Control"], "no-store")
                self.assertEqual(antwort.headers["Referrer-Policy"], "same-origin")
                csp = antwort.headers["Content-Security-Policy"]
                self.assertIn("frame-ancestors 'none'", csp)
                self.assertIn("script-src 'none'", csp)

    def test_logout_entfernt_session(self):
        self._anmelden()
        self.client.post("/logout")
        antwort = self.client.get("/teilnehmer")
        self.assertEqual(antwort.status_code, 302)

    # --- Termin-Auswahl --------------------------------------------------------

    def test_bei_einem_offenen_termin_wird_auswahl_uebersprungen(self):
        antwort = self._anmelden()  # self.termine hat genau einen Eintrag (Standard)
        self.assertIn("Teilnehmer".encode(), antwort.data)

    def test_bei_mehreren_terminen_wird_liste_gezeigt(self):
        self.termine = [
            _termin_info("termin_a", verein="Verein A"),
            _termin_info("termin_b", verein="Verein B"),
        ]
        antwort = self._anmelden()
        self.assertIn("Verein A".encode(), antwort.data)
        self.assertIn("Verein B".encode(), antwort.data)

    def test_terminauswahl_zeigt_datum_deutsch(self):
        # Marcos Wunsch 22.09.: Datum überall als TT.MM.JJJJ (Template-Filter "datum").
        self.termine = [
            _termin_info("termin_a", verein="Verein A", datum="2026-09-27"),
            _termin_info("termin_b", verein="Verein B"),
        ]
        antwort = self._anmelden()
        self.assertIn(b"27.09.2026", antwort.data)
        self.assertNotIn(b"2026-09-27", antwort.data)
        self.assertIn(b"ohne Datum", antwort.data)

    def test_termin_auswahl_per_post_setzt_schema_und_leitet_weiter(self):
        self.termine = [
            _termin_info("termin_a", verein="Verein A"),
            _termin_info("termin_b", verein="Verein B"),
        ]
        self._anmelden()
        antwort = self.client.post("/termin-waehlen", data={"schema_name": "termin_b"}, follow_redirects=True)
        self.assertIn("Teilnehmer".encode(), antwort.data)

    def test_termin_auswahl_lehnt_unbekanntes_schema_ab(self):
        self.termine = [
            _termin_info("termin_a", verein="Verein A"),
            _termin_info("termin_b", verein="Verein B"),
        ]
        self._anmelden()
        antwort = self.client.post("/termin-waehlen", data={"schema_name": "nicht_offen"})
        self.assertEqual(antwort.status_code, 400)

    def test_ohne_offene_termine_zeigt_hinweis(self):
        self.termine = []
        antwort = self._anmelden()
        self.assertIn("kein Termin veröffentlicht".encode(), antwort.data)
        # Der Hinweis verweist auf Desktop und Web-Oberfläche, nicht nur auf das Kommandozeilenskript
        # (UX-Test Web 19.11.2026, A3: Admin bekommt zusätzlich den Knopf „Termine verwalten“).
        html = antwort.data.decode()
        self.assertIn("„Ins Web veröffentlichen…“", html)
        self.assertIn('<a class="knopf" href="/admin/termine">Termine verwalten</a>', html)

    def test_passwortfeld_hat_dieselbe_gestaltung_wie_textfelder(self):
        """Das Passwortfeld der Anmeldung war schmal und ungestaltet (offener Punkt 23.09.)."""
        antwort = self.client.get("/")
        self.assertEqual(antwort.status_code, 200)
        self.assertIn(b"input[type=password]", antwort.data)

    def test_geloeschtes_termin_schema_leitet_sauber_zur_terminauswahl_um(self):
        """QS-Fund 21.09.: löschte ein Administrator einen Termin, während ein anderer
        Nutzer noch mit dessen schema_name in der Session unterwegs war, scheiterte der
        nächste Datenbankzugriff bisher mit einer unbehandelten Exception (rohe
        500-Fehlerseite) statt einer sauberen Weiterleitung zu '/termin-waehlen'.
        Simuliert das geänderte/gelöschte Schema hier, indem db.oeffne_termin_postgres()
        für diese eine Anfrage eine Exception wirft (im normalen Testaufbau ein No-Op,
        siehe _fake_oeffne_termin)."""
        self._anmelden()  # setzt session["schema_name"], self.termine hat 1 Eintrag
        self.assertEqual(self.client.get("/teilnehmer").status_code, 200)

        def _schema_existiert_nicht_mehr(conn, schema_name):
            raise Exception("Schema existiert nicht mehr (simuliert gelöscht)")

        with patch("app_web.db.oeffne_termin_postgres", _schema_existiert_nicht_mehr):
            antwort = self.client.get("/teilnehmer")
        self.assertEqual(antwort.status_code, 302)
        self.assertIn("/termin-waehlen", antwort.headers["Location"])

        # Die veraltete Session-Auswahl wurde entfernt - ein normaler Folgeaufruf (ohne
        # die simulierte Exception) landet wieder sauber bei der Teilnehmerliste, statt
        # dauerhaft auf dem kaputten Schema hängenzubleiben.
        antwort2 = self.client.get("/teilnehmer", follow_redirects=True)
        self.assertEqual(antwort2.status_code, 200)
        self.assertIn("Teilnehmer".encode(), antwort2.data)

    # --- Benutzerverwaltung ------------------------------------------------------

    def test_nicht_admin_bekommt_403_bei_benutzerverwaltung(self):
        self._anmelden()
        db.benutzer_anlegen(self.conn, "helfer", "helferpasswort")
        self.client.post("/logout")
        self.client.post("/", data={"benutzername": "helfer", "passwort": "helferpasswort"})
        antwort = self.client.get("/admin/benutzer")
        self.assertEqual(antwort.status_code, 403)

    def test_admin_kann_benutzer_anlegen(self):
        self._anmelden()
        antwort = self.client.post(
            "/admin/benutzer",
            data={
                "benutzername": "helfer", "passwort": "helferpasswort",
                "passwort_wiederholung": "helferpasswort", "rolle": "eintragen",
            },
            follow_redirects=True,
        )
        self.assertIn("helfer".encode(), antwort.data)
        konto = db.pruefe_login(self.conn, "helfer", "helferpasswort")
        self.assertEqual({k: konto[k] for k in ("benutzername", "ist_admin")}, {"benutzername": "helfer", "ist_admin": False})
        self.assertEqual(len(konto["kennung"]), 32)  # C-1: Konto-Kennung für die Session

    def test_admin_benutzeranlage_lehnt_doppelten_namen_ab(self):
        self._anmelden()
        antwort = self.client.post(
            "/admin/benutzer",
            data={
                "benutzername": _ADMIN_NAME, "passwort": "irgendein_passwort",
                "passwort_wiederholung": "irgendein_passwort", "rolle": "eintragen",
            },
        )
        self.assertIn("bereits vergeben".encode(), antwort.data)

    def test_admin_benutzeranlage_lehnt_doppelten_namen_unabhaengig_von_gross_kleinschreibung_ab(self):
        # Passend zum groß-/kleinschreibungsunabhängigen Login (siehe oben) darf auch
        # keine zweite, nur anders geschriebene Variante eines bestehenden Benutzernamens
        # angelegt werden können (z. B. "Chef" neben bereits vorhandenem "chef").
        self._anmelden()
        antwort = self.client.post(
            "/admin/benutzer",
            data={
                "benutzername": _ADMIN_NAME.upper(), "passwort": "irgendein_passwort",
                "passwort_wiederholung": "irgendein_passwort", "rolle": "eintragen",
            },
        )
        self.assertIn("bereits vergeben".encode(), antwort.data)

    def test_race_zwischen_vorabpruefung_und_insert_wird_ueber_datenbank_index_abgefangen(self):
        """QS-Fund (19./20.09.): die Vorab-Prüfung in admin_benutzer() (siehe oben) ist
        eine separate Python-Abfrage VOR dem eigentlichen INSERT - zwischen beiden bleibt
        theoretisch ein Zeitfenster für eine zweite, gleichzeitige Anfrage. Simuliert hier
        direkt, indem db.liste_benutzer() für die Vorab-Prüfung (nicht aber für den
        anschließenden Render-Aufruf) so getan wird, als gäbe es den Namen noch nicht -
        der INSERT selbst muss trotzdem am Unique-Index auf LOWER(benutzername)
        (db._WEB_BENUTZER_INDEX_BENUTZERNAME_LOWER) scheitern und darf NICHT als rohe
        Server-Fehlerseite durchschlagen, sondern muss dieselbe verständliche Meldung wie
        beim normalen Duplikat zeigen."""
        self._anmelden()
        with patch("app_web.db.liste_benutzer", return_value=[]):
            antwort = self.client.post(
                "/admin/benutzer",
                data={
                    "benutzername": _ADMIN_NAME.upper(), "passwort": "irgendein_passwort",
                    "passwort_wiederholung": "irgendein_passwort", "rolle": "eintragen",
                },
            )
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("bereits vergeben".encode(), antwort.data)
        # Es wurde tatsächlich kein zweites Konto angelegt.
        self.assertEqual(len(db.liste_benutzer(self.conn)), 1)

    def test_admin_kann_benutzer_loeschen(self):
        self._anmelden()
        db.benutzer_anlegen(self.conn, "helfer", "helferpasswort")
        self.client.post("/admin/benutzer/helfer/loeschen", follow_redirects=True)
        self.assertIsNone(db.pruefe_login(self.conn, "helfer", "helferpasswort"))

    def test_letzter_admin_kann_sich_nicht_selbst_loeschen(self):
        self._anmelden()
        self.client.post(f"/admin/benutzer/{_ADMIN_NAME}/loeschen", follow_redirects=True)
        # Löschen wurde von db.benutzer_loeschen abgelehnt (ValueError, siehe db.py) -
        # das Konto existiert weiterhin.
        self.assertIsNotNone(db.pruefe_login(self.conn, _ADMIN_NAME, _ADMIN_PASSWORT))

    def test_geloeschtes_konto_wird_bei_naechster_anfrage_ausgeloggt(self):
        """QS-Fund 21.09.: _login_erforderlich/_admin_erforderlich/_termin_erforderlich
        prüften bisher nur den in der Session hinterlegten Stand, nie den aktuellen
        Datenbankstand - löschte ein Administrator währenddessen das Konto eines
        anderen angemeldeten Nutzers, blieb dessen Session bis zum Abmelden/
        Sitzungsablauf voll nutzbar. Simuliert hier: "helfer" ist angemeldet, ein
        (anderer) Administrator löscht sein Konto direkt in der Datenbank - der nächste
        Aufruf von "helfer" muss zum Login zurückschicken UND die Session tatsächlich
        geleert haben (nicht nur einmalig abweisen)."""
        self._anmelden()
        db.benutzer_anlegen(self.conn, "helfer", "helferpasswort")
        self.client.post("/logout")
        self.client.post(
            "/", data={"benutzername": "helfer", "passwort": "helferpasswort"}, follow_redirects=True
        )
        self.assertEqual(self.client.get("/teilnehmer").status_code, 200)

        db.benutzer_loeschen(self.conn, "helfer")

        antwort = self.client.get("/teilnehmer", follow_redirects=True)
        self.assertIn("Benutzername".encode(), antwort.data)  # zurück auf der Login-Seite
        # Die Session wurde wirklich geleert (session.clear()), nicht nur diese eine
        # Anfrage abgewiesen - auch admin-geschützte Bereiche sind jetzt wieder zu.
        self.assertEqual(self.client.get("/admin/benutzer").status_code, 302)

    def test_altes_cookie_gilt_nicht_fuer_neu_angelegtes_konto_gleichen_namens(self):
        """Sicherheitsprüfung 03.10.2026, C-1 (Codex-Nachweis): Konto "helfer" wird
        gelöscht und unter demselben Namen als ADMIN neu angelegt - das alte Cookie darf
        weder das neue Konto noch Admin-Rechte bekommen."""
        self._anmelden()
        db.benutzer_anlegen(self.conn, "helfer", "helferpasswort")
        self.client.post("/logout")
        self.client.post(
            "/", data={"benutzername": "helfer", "passwort": "helferpasswort"}, follow_redirects=True
        )
        self.assertEqual(self.client.get("/teilnehmer").status_code, 200)

        db.benutzer_loeschen(self.conn, "helfer")
        db.benutzer_anlegen(self.conn, "helfer", "ganz-neues-passwort", ist_admin=True)

        self.assertEqual(self.client.get("/admin/benutzer").status_code, 302)
        self.assertEqual(self.client.get("/teilnehmer").status_code, 302)

    def test_platzhalter_und_zu_kurze_geheimnisse_werden_abgelehnt(self):
        """Sicherheitsprüfung 03.10.2026, S-2: Werte aus .env.example bzw. zu kurze Werte
        verhindern den Start; leer bleibt erlaubt."""
        pruefe = app_web.pruefe_web_geheimnisse
        pruefe("", "")
        pruefe("a" * 64, "b" * 16)
        for schluessel, code in (
            ("bitte-hier-einen-erzeugten-schluessel-eintragen", ""),
            ("zu-kurz", ""),
            ("a" * 64, "bitte-hier-einen-erzeugten-code-eintragen"),
            ("a" * 64, "kurz"),
        ):
            with self.subTest(schluessel=schluessel, code=code):
                with self.assertRaises(RuntimeError):
                    pruefe(schluessel, code)

    def test_geheimnis_wird_aus_secret_datei_gelesen(self):
        """Sicherheitshinweis H-3 (05.10.2026): <NAME>_FILE hat Vorrang vor <NAME>,
        Leerraum am Rand (Zeilenumbruch am Dateiende) wird entfernt."""
        with tempfile.TemporaryDirectory() as ordner:
            pfad = os.path.join(ordner, "geheimnis.txt")
            with open(pfad, "w", encoding="utf-8") as datei:
                datei.write("  aus-der-datei\r\n")
            with patch.dict(os.environ, {"SHS_TEST_GEHEIMNIS_FILE": pfad, "SHS_TEST_GEHEIMNIS": "aus-env"}):
                self.assertEqual(app_web.geheimnis_lesen("SHS_TEST_GEHEIMNIS"), "aus-der-datei")

    def test_geheimnis_ohne_datei_kommt_aus_der_umgebung(self):
        with patch.dict(os.environ, {"SHS_TEST_GEHEIMNIS": " aus-env \n"}):
            os.environ.pop("SHS_TEST_GEHEIMNIS_FILE", None)
            self.assertEqual(app_web.geheimnis_lesen("SHS_TEST_GEHEIMNIS"), "aus-env")
        with patch.dict(os.environ, {}):
            os.environ.pop("SHS_TEST_GEHEIMNIS", None)
            os.environ.pop("SHS_TEST_GEHEIMNIS_FILE", None)
            self.assertEqual(app_web.geheimnis_lesen("SHS_TEST_GEHEIMNIS"), "")

    def test_nicht_lesbare_secret_datei_bricht_mit_klarer_meldung_ab(self):
        """Ist <NAME>_FILE gesetzt, die Datei aber nicht lesbar, darf die Web-Version nicht
        still ohne Geheimnis (z. B. mit zufälligem Schlüssel oder gesperrter
        Ersteinrichtung) weiterlaufen."""
        with tempfile.TemporaryDirectory() as ordner:
            fehlt = os.path.join(ordner, "fehlt.txt")
            with patch.dict(os.environ, {"SHS_TEST_GEHEIMNIS_FILE": fehlt, "SHS_TEST_GEHEIMNIS": "aus-env"}):
                with self.assertRaises(RuntimeError) as kontext:
                    app_web.geheimnis_lesen("SHS_TEST_GEHEIMNIS")
        self.assertIn("SHS_TEST_GEHEIMNIS_FILE", str(kontext.exception))
        self.assertIn("nicht lesbar", str(kontext.exception))

    def test_leere_secret_datei_bricht_mit_klarer_meldung_ab(self):
        """Verifikation 05.10.2026: Eine leere Datei (z. B. weil der Befehl zum Erzeugen
        nichts ausgegeben hat) darf nicht als "nicht gesetzt" durchgehen."""
        with tempfile.TemporaryDirectory() as ordner:
            pfad = os.path.join(ordner, "leer.txt")
            with open(pfad, "w", encoding="utf-8") as datei:
                datei.write(" \n")
            with patch.dict(os.environ, {"SHS_TEST_GEHEIMNIS_FILE": pfad}):
                with self.assertRaises(RuntimeError) as kontext:
                    app_web.geheimnis_lesen("SHS_TEST_GEHEIMNIS")
        self.assertIn("ist leer", str(kontext.exception))

    def test_db_passwort_wird_getrennt_an_die_verbindung_gereicht(self):
        """H-3: Das Passwort aus SHS_POSTGRES_PASSWORD(_FILE) geht getrennt vom DSN an
        db.verbinde_postgres_server; ohne Passwort wird None übergeben."""
        aufrufe = []

        def verbinden(dsn, password=None):
            aufrufe.append((dsn, password))
            return _NichtSchliessendeVerbindung(self.conn)

        for passwort, erwartet in (("p@ss/wort", "p@ss/wort"), ("", None)):
            with self.subTest(passwort=passwort):
                aufrufe.clear()
                with patch.dict(app_web.app.config, {"SHS_POSTGRES_PASSWORD": passwort}), patch(
                    "db.verbinde_postgres_server", verbinden
                ):
                    with app_web.app.app_context():
                        app_web._postgres_verbindung()
                self.assertEqual(aufrufe, [(app_web.app.config["SHS_POSTGRES_DSN"], erwartet)])

    def test_rollenaenderung_wird_ohne_neuanmeldung_uebernommen(self):
        """Teil desselben Fixes: _aktueller_benutzer_oder_redirect() aktualisiert
        session["ist_admin"] bei JEDER Anfrage neu aus der Datenbank - ein
        zwischenzeitlich auf die Rolle "Eintragen" zurückgestuftes Konto verliert damit
        seine Admin-Rechte, ohne sich neu anmelden zu müssen (und ohne dass die stale
        Session weiterhin Admin-Zugriff gewähren würde)."""
        self._anmelden()
        db.benutzer_anlegen(self.conn, "helfer", "helferpasswort", ist_admin=True)
        self.client.post("/logout")
        self.client.post("/", data={"benutzername": "helfer", "passwort": "helferpasswort"})
        self.assertEqual(self.client.get("/admin/benutzer").status_code, 200)

        self.conn.execute("UPDATE web_benutzer SET ist_admin = 0 WHERE benutzername = 'helfer'")
        self.conn.commit()

        self.assertEqual(self.client.get("/admin/benutzer").status_code, 403)

    # --- Teilnehmerliste ---------------------------------------------------------

    def test_teilnehmerliste_suche_nach_name_oder_hund(self):
        """Marco 10.11.2026: Suche ohne JavaScript (GET-Formular), Treffer nach Name oder Hund."""
        db.set_veranstaltung(self.conn, verein="Testverein", datum="2026-09-19")
        for nr, (nach, hund) in enumerate([("Albers", "Aika"), ("Brandt", "Bruno <b>"), ("Claasen", "Cleo")], start=1):
            db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
                nachname=nach, vorname="A", rufname_hund=hund, art="ED", stufe=1,
                disziplin="Trümmerfeld", startnummer=nr))
        self._anmelden()
        text = self.client.get("/teilnehmer").data.decode()
        self.assertIn("Albers, A", text)
        self.assertIn("Brandt, A", text)
        text = self.client.get("/teilnehmer?q=bruno").data.decode()
        self.assertIn("Brandt, A", text)
        self.assertNotIn("Albers, A", text)
        self.assertIn("1 von 3 Teilnehmern", text)
        text = self.client.get("/teilnehmer?q=ALB+a").data.decode()
        self.assertIn("Albers, A", text)
        self.assertNotIn("Claasen, A", text)
        # Eingabe wird maskiert zurückgegeben, nichts gefunden -> Hinweis
        text = self.client.get("/teilnehmer?q=%3Cscript%3E").data.decode()
        self.assertNotIn("<script>", text)
        self.assertIn("Kein Teilnehmer passt", text)

    def test_teilnehmerliste_zeigt_status_offen_und_fertig(self):
        db.set_veranstaltung(self.conn, verein="Testverein", datum="2026-09-19")
        db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Offen", vorname="A", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1,
        ))
        fertig_id = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Fertig", vorname="B", rufname_hund="Bello", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=2,
        ))
        db.eintragen_ergebnis(self.conn, fertig_id, "Trümmerfeld", 50, 30)

        self._anmelden()
        antwort = self.client.get("/teilnehmer")
        text = antwort.data.decode()
        self.assertIn("Testverein", text)
        self.assertIn("Offen, A", text)
        self.assertIn("Fertig, B", text)
        self.assertIn("status-offen", text)
        self.assertIn("status-fertig", text)

    def test_teilnehmerliste_status_in_vier_stufen(self):
        # UX-Test Web 19.11.2026 (B2): vorher „bewertet“ auch bei Disqualifikation/Abbruch und
        # „offen“ trotz gespeicherter Disziplin beim Dreikampf.
        def dk(name, nummer):
            return db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
                nachname=name, vorname="X", rufname_hund="Hund", art="DK", stufe=2, startnummer=nummer))
        offen = dk("Offen", 1)
        teilweise = dk("Teilweise", 2)
        db.eintragen_ergebnis(self.conn, teilweise, db.ALLE_DISZIPLINEN[0], 40, 30)
        fertig = dk("Fertig", 3)
        for disziplin in db.ALLE_DISZIPLINEN:
            db.eintragen_ergebnis(self.conn, fertig, disziplin, 40, 30)
        dq = dk("Dq", 4)
        for disziplin in db.ALLE_DISZIPLINEN:
            db.eintragen_ergebnis(self.conn, dq, disziplin, 40, 30)
        db.setze_ergebnis_status(self.conn, dq, True, False)
        abbruch = dk("Abbruch", 5)
        db.setze_ergebnis_status(self.conn, abbruch, False, True, abbruch_grund=next(iter(db.ABBRUCH_GRUENDE)))
        self._anmelden()
        html = self.client.get("/teilnehmer").data.decode()

        def status_von(tid):
            start = html.index(f'href="/teilnehmer/{tid}"')
            return re.search(r'<span class="status (status-\w+)">(?:<svg.*?</svg>)?([^<]*)</span>',
                             html[start:]).groups()

        self.assertEqual(status_von(offen), ("status-offen", "offen"))
        self.assertEqual(status_von(teilweise), ("status-teilweise", f"teilweise (1 von {len(db.ALLE_DISZIPLINEN)})"))
        self.assertEqual(status_von(fertig), ("status-fertig", "bewertet"))
        self.assertEqual(status_von(dq), ("status-dq", "disqualifiziert"))
        self.assertEqual(status_von(abbruch), ("status-abbruch", "Abbruch"))

    def test_listen_status_vorrang_und_fehlende_ergebniszeile(self):
        dk = {"art": "DK", "disziplin": None}
        self.assertEqual(app_web._listen_status(dk, {})["art"], "offen")
        spalten = db.DISZIPLIN_SPALTEN[db.ALLE_DISZIPLINEN[0]]
        teilpunkte = {spalten[0]: 40, spalten[1]: 30}
        # Abbruch geht vor „teilweise“, Disqualifiziert vor Abbruch.
        self.assertEqual(app_web._listen_status(dk, {**teilpunkte, "abbruch": 1})["art"], "abbruch")
        self.assertEqual(app_web._listen_status(dk, {**teilpunkte, "abbruch": 1, "disqualifiziert": 1})["art"], "dq")
        self.assertEqual(app_web._listen_status(dk, teilpunkte)["art"], "teilweise")

    def test_listen_status_angefangene_disziplin_ist_teilweise(self):
        # Marco nach der QS in U13: auch nur Suche (oder nur Anzeige) zählt als angefangen.
        such, anz = db.DISZIPLIN_SPALTEN["Flächensuche"]
        ed = {"art": "ED", "disziplin": "Flächensuche"}
        self.assertEqual(app_web._listen_status(ed, {such: 40}), {"text": "teilweise", "art": "teilweise"})
        self.assertEqual(app_web._listen_status(ed, {anz: 0})["art"], "teilweise")  # 0 ist ein Wert
        self.assertEqual(app_web._listen_status(ed, {such: None, anz: None})["art"], "offen")
        dk = {"art": "DK", "disziplin": None}
        halb = {db.DISZIPLIN_SPALTEN[d][0]: 10 for d in db.ALLE_DISZIPLINEN}
        self.assertEqual(app_web._listen_status(dk, halb)["text"], f"teilweise (0 von {len(db.ALLE_DISZIPLINEN)})")

    def test_teilnehmerliste_ed_vollstaendig_ist_bewertet(self):
        tid = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Muster", vorname="A", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Flächensuche", startnummer=1))
        db.eintragen_ergebnis(self.conn, tid, "Flächensuche", 40, 30)
        self._anmelden()
        html = self.client.get("/teilnehmer").data.decode()
        self.assertNotIn('class="status status-teilweise"', html)
        self.assertIn("bewertet</span>", html)

    def test_keine_teilnahme_fehlt_in_liste_und_erfassung_liefert_404(self):
        # Nutzerwunsch 02.10.2026: "keine Teilnahme" wird beim Veröffentlichen gar nicht
        # erst übertragen. Wer NACH dem Veröffentlichen markiert, muss neu veröffentlichen
        # (das Flag selbst wird nie übertragen) - dieser Filter ist nur eine zusätzliche
        # Absicherung für eine Web-Datenbank, die das Flag doch enthält.
        db.set_veranstaltung(self.conn, verein="Testverein", datum="2026-09-19")
        db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Da", vorname="A", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1,
        ))
        fehlt_id = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Fehlt", vorname="B", rufname_hund="Bello", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=2,
        ))
        db.setze_keine_teilnahme(self.conn, fehlt_id, True)

        self._anmelden()
        text = self.client.get("/teilnehmer").data.decode()
        self.assertIn("Da, A", text)
        self.assertNotIn("Fehlt, B", text)
        self.assertEqual(self.client.get(f"/teilnehmer/{fehlt_id}").status_code, 404)

    # --- Ergebnis erfassen -------------------------------------------------------

    @staticmethod
    def _formularfeld(html: str, name: str) -> str:
        """Liest den value-Attributwert eines Formularfelds (Eingabe- oder verstecktes
        Feld) direkt aus dem gerenderten HTML - für die Lost-Update-/
        Validierungsfehler-Tests unten, die prüfen, was tatsächlich im wiederholt
        angezeigten Formular steht bzw. es als Formulardaten eines "geladenen" Richters
        weiterverwenden."""
        treffer = re.search(rf'name="{re.escape(name)}"[^>]*value="([^"]*)"', html)
        return treffer.group(1) if treffer else ""

    @classmethod
    def _formulardaten_aus_seite(cls, html: str, disziplinen) -> dict:
        """Baut die Formulardaten nach, die ein Browser beim Absenden der Seite
        mitschicken würde - inklusive der versteckten "geladen_*"-Felder (siehe
        app_web._geladene_werte_aus_formular/templates/ergebnis_erfassen.html) -,
        basierend auf dem gerade per GET geladenen Formularstand. Simuliert damit einen
        Richter, der die Seite geladen hat und sie (ggf. mit ein paar geänderten
        Feldern) wieder abschickt."""
        daten = {}
        for disziplin in disziplinen:
            for prefix in ("suche_", "anzeige_", "geladen_suche_", "geladen_anzeige_"):
                name = f"{prefix}{disziplin}"
                daten[name] = cls._formularfeld(html, name)
        return daten

    def test_ergebnis_speichern_ed(self):
        teilnehmer_id = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Muster", vorname="A", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Flächensuche", startnummer=1,
        ))
        self._anmelden()
        antwort = self.client.post(
            f"/teilnehmer/{teilnehmer_id}",
            data={"suche_Flächensuche": "45", "anzeige_Flächensuche": "25"},
            follow_redirects=True,
        )
        self.assertEqual(antwort.status_code, 200)
        ergebnis = db.get_ergebnis(self.conn, teilnehmer_id)
        self.assertEqual(ergebnis["suche_flaechensuche"], 45)
        self.assertEqual(ergebnis["anzeige_flaechensuche"], 25)

    def test_einzelseite_bestaetigt_speichern_in_der_liste(self):
        # UX-Test Web 19.11.2026 (B2): nach dem Speichern eine sichtbare Bestätigung in der Liste.
        teilnehmer_id = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Muster", vorname="A", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Flächensuche", startnummer=1,
        ))
        self._anmelden()
        antwort = self.client.post(
            f"/teilnehmer/{teilnehmer_id}",
            data={"suche_Flächensuche": "45", "anzeige_Flächensuche": "25"},
        )
        self.assertEqual(antwort.status_code, 302)
        self.assertIn(f"gespeichert={teilnehmer_id}", antwort.headers["Location"])
        self.assertIn("aenderung=1", antwort.headers["Location"])
        html = self.client.get(antwort.headers["Location"]).data.decode()
        self.assertIn('role="status">Gespeichert: Muster, A.', html)

        # Zweites Absenden ohne Änderung (gleiche Werte als „geladen“): keine Änderung gemeldet.
        antwort = self.client.post(f"/teilnehmer/{teilnehmer_id}", data={
            "suche_Flächensuche": "45", "anzeige_Flächensuche": "25",
            "geladen_suche_Flächensuche": "45", "geladen_anzeige_Flächensuche": "25",
        })
        self.assertIn("aenderung=0", antwort.headers["Location"])
        html = self.client.get(antwort.headers["Location"]).data.decode()
        self.assertIn("Keine Änderungen zu speichern (Muster, A).", html)

    def test_liste_ohne_oder_mit_ungueltiger_bestaetigung_zeigt_keine_meldung(self):
        db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Muster", vorname="A", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Flächensuche", startnummer=1,
        ))
        self._anmelden()
        for adresse in ("/teilnehmer", "/teilnehmer?gespeichert=abc", "/teilnehmer?gespeichert=999999",
                        "/teilnehmer?gespeichert=99999999999999999999999", "/teilnehmer?gespeichert=-1"):
            antwort = self.client.get(adresse)
            self.assertEqual(antwort.status_code, 200, adresse)
            self.assertNotIn('karte-erfolg" role="status"', antwort.data.decode(), adresse)

    def test_liste_und_einzelseite_fuehren_zum_bewertungsbogen(self):
        # UX-Test Web 19.11.2026 (A1): der Bogen war nur über die Ergebnistabelle erreichbar.
        ed = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Muster", vorname="A", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Flächensuche", startnummer=1,
        ))
        dk = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Muster", vorname="B", rufname_hund="Bello", art="DK", stufe=2, startnummer=2,
        ))
        self._anmelden()
        liste = self.client.get("/teilnehmer").data.decode()
        self.assertIn(f'href="/bewertungsbogen/{ed}/Fl%C3%A4chensuche?von=liste"', liste)
        self.assertEqual(liste.count(f"/bewertungsbogen/{dk}/"), len(db.ALLE_DISZIPLINEN))
        self.assertEqual(liste.count(f"/bewertungsbogen/{ed}/"), 1)

        seite = self.client.get(f"/teilnehmer/{dk}").data.decode()
        for disziplin in db.ALLE_DISZIPLINEN:
            self.assertIn(f'name="bogen" value="{disziplin}"', seite)
        # „Speichern“ steht vor den Bogen-Knöpfen (die Eingabetaste löst den ersten Absendeknopf aus).
        self.assertLess(seite.index(">Speichern</button>"), seite.index('name="bogen"'))

    def test_bogen_knopf_speichert_zuerst_und_oeffnet_den_bogen(self):
        dk = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Muster", vorname="B", rufname_hund="Bello", art="DK", stufe=2, startnummer=2,
        ))
        self._anmelden()
        disziplin = db.ALLE_DISZIPLINEN[1]
        antwort = self.client.post(f"/teilnehmer/{dk}", data={
            f"suche_{disziplin}": "40", f"anzeige_{disziplin}": "30", "bogen": disziplin,
        })
        self.assertEqual(antwort.status_code, 302)
        self.assertTrue(antwort.headers["Location"].startswith(f"/bewertungsbogen/{dk}/"))
        self.assertTrue(antwort.headers["Location"].endswith("?von=teilnehmer"), antwort.headers["Location"])
        spalte_suche, spalte_anzeige = db.DISZIPLIN_SPALTEN[disziplin]
        ergebnis = db.get_ergebnis(self.conn, dk)
        self.assertEqual((ergebnis[spalte_suche], ergebnis[spalte_anzeige]), (40, 30))
        self.assertEqual(self.client.get(antwort.headers["Location"]).status_code, 200)

    def test_bogen_knopf_mit_fremder_disziplin_fuehrt_zur_liste(self):
        ed = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Muster", vorname="A", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Flächensuche", startnummer=1,
        ))
        self._anmelden()
        for fremd in ("Gebäudesuche", "//evil.example"):
            antwort = self.client.post(f"/teilnehmer/{ed}", data={"bogen": fremd})
            self.assertEqual(antwort.status_code, 302)
            self.assertTrue(antwort.headers["Location"].startswith("/teilnehmer?gespeichert="),
                            antwort.headers["Location"])

    def test_bogen_links_der_liste_gelten_fuer_rolle_eintragen(self):
        ed = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Muster", vorname="A", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Flächensuche", startnummer=1,
        ))
        self._anmelden()
        db.benutzer_anlegen(self.conn, "helfer", "helferpasswort")  # Rolle „eintragen“ (kein Admin)
        self.client.post("/logout")
        self.client.post("/", data={"benutzername": "helfer", "passwort": "helferpasswort"}, follow_redirects=True)
        liste = self.client.get("/teilnehmer").data.decode()
        self.assertIn(f"/bewertungsbogen/{ed}/", liste)
        self.assertEqual(self.client.get(f"/bewertungsbogen/{ed}/Fl%C3%A4chensuche").status_code, 200)

    def test_bogen_knopf_bei_fehler_bleibt_auf_der_seite(self):
        ed = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Muster", vorname="A", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Flächensuche", startnummer=1,
        ))
        self._anmelden()
        antwort = self.client.post(f"/teilnehmer/{ed}", data={
            "suche_Flächensuche": "84", "anzeige_Flächensuche": "25", "bogen": "Flächensuche",
        })
        self.assertEqual(antwort.status_code, 200)
        self.assertIsNone((db.get_ergebnis(self.conn, ed) or {}).get("suche_flaechensuche"))

    # --- Disqualifiziert/Abbruch auf der Einzelseite (UX-Test Web 19.11.2026, D1) ---------

    def _ed_teilnehmer(self):
        return db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Muster", vorname="A", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Flächensuche", startnummer=1,
        ))

    def test_einzelseite_zeigt_disqualifikation_und_abbruch(self):
        tid = self._ed_teilnehmer()
        self._anmelden()
        seite = self.client.get(f"/teilnehmer/{tid}").data.decode()
        self.assertIn('name="dq" value="1"', seite)
        self.assertIn('<select id="abbruch" name="abbruch">', seite)
        self.assertIn('name="geladen_status" value="0|"', seite)
        for code in db.ABBRUCH_GRUENDE:
            self.assertIn(f'<option value="{code}"', seite)
        self.assertNotIn('value="ohne_grund"', seite)  # nur als Altdatum
        self.assertLess(seite.index('name="dq"'), seite.index(">Speichern</button>"))

    def test_einzelseite_disqualifiziert_speichern(self):
        tid = self._ed_teilnehmer()
        self._anmelden()
        antwort = self.client.post(f"/teilnehmer/{tid}", data={
            "suche_Flächensuche": "", "anzeige_Flächensuche": "",
            "geladen_suche_Flächensuche": "", "geladen_anzeige_Flächensuche": "",
            "geladen_status": "0|", "dq": "1",
        })
        self.assertEqual(antwort.status_code, 302)
        self.assertIn("aenderung=1", antwort.headers["Location"])
        ergebnis = db.get_ergebnis(self.conn, tid)
        self.assertTrue(ergebnis["disqualifiziert"])
        self.assertIn('name="geladen_status" value="1|"', self.client.get(f"/teilnehmer/{tid}").data.decode())

    def test_einzelseite_abbruch_mit_grund_und_teilbewertung(self):
        tid = self._ed_teilnehmer()
        self._anmelden()
        grund = next(iter(db.ABBRUCH_GRUENDE))
        antwort = self.client.post(f"/teilnehmer/{tid}", data={
            "suche_Flächensuche": "30", "anzeige_Flächensuche": "20",
            "geladen_suche_Flächensuche": "", "geladen_anzeige_Flächensuche": "",
            "geladen_status": "0|", "abbruch": grund,
        })
        self.assertEqual(antwort.status_code, 302)
        ergebnis = db.get_ergebnis(self.conn, tid)
        self.assertTrue(ergebnis["abbruch"])
        self.assertEqual(ergebnis["abbruch_grund"], grund)
        self.assertEqual((ergebnis["suche_flaechensuche"], ergebnis["anzeige_flaechensuche"]), (30, 20))

    def test_einzelseite_abbruch_ohne_grund_und_unbekannter_grund_abgelehnt(self):
        tid = self._ed_teilnehmer()
        self._anmelden()
        for abbruch, text in (("ohne_grund", "Ein Abbruch braucht einen Grund"),
                              ("gibtsnicht", "Unbekannter Abbruchgrund")):
            antwort = self.client.post(f"/teilnehmer/{tid}", data={
                "suche_Flächensuche": "30", "anzeige_Flächensuche": "20",
                "geladen_suche_Flächensuche": "", "geladen_anzeige_Flächensuche": "",
                "geladen_status": "0|", "abbruch": abbruch,
            })
            self.assertEqual(antwort.status_code, 200, abbruch)
            html = antwort.data.decode()
            self.assertIn(text, html)
            self.assertIn('value="30"', html)  # Eingaben bleiben stehen
            ergebnis = db.get_ergebnis(self.conn, tid) or {}  # nichts gespeichert
            self.assertIsNone(ergebnis.get("suche_flaechensuche"), abbruch)
            self.assertFalse(ergebnis.get("abbruch"), abbruch)

    def test_einzelseite_disqualifiziert_sperrt_punkte(self):
        tid = self._ed_teilnehmer()
        db.eintragen_ergebnis(self.conn, tid, "Flächensuche", 40, 30)
        self._anmelden()
        # Auch ein Wert über dem Höchstwert führt nicht zum Fehler: die Punkte sind gesperrt.
        antwort = self.client.post(f"/teilnehmer/{tid}", data={
            "suche_Flächensuche": "84", "anzeige_Flächensuche": "30",
            "geladen_suche_Flächensuche": "40", "geladen_anzeige_Flächensuche": "30",
            "geladen_status": "0|", "dq": "1",
        })
        self.assertEqual(antwort.status_code, 302)
        ergebnis = db.get_ergebnis(self.conn, tid)
        self.assertTrue(ergebnis["disqualifiziert"])
        self.assertEqual((ergebnis["suche_flaechensuche"], ergebnis["anzeige_flaechensuche"]), (40, 30))

    def test_einzelseite_status_konflikt_ueberschreibt_nicht(self):
        tid = self._ed_teilnehmer()
        self._anmelden()
        # Ein anderer Richter disqualifiziert, nachdem diese Seite mit „0|“ geladen wurde.
        db.setze_ergebnis_status(self.conn, tid, True, False)
        grund = next(iter(db.ABBRUCH_GRUENDE))
        antwort = self.client.post(f"/teilnehmer/{tid}", data={
            "suche_Flächensuche": "30", "anzeige_Flächensuche": "20",
            "geladen_suche_Flächensuche": "", "geladen_anzeige_Flächensuche": "",
            "geladen_status": "0|", "abbruch": grund,
        })
        self.assertEqual(antwort.status_code, 200)
        html = antwort.data.decode()
        self.assertIn("Disqualifiziert/Abbruch wurde inzwischen von jemand anderem geändert", html)
        # Die Zeile ist inzwischen gesperrt: auch die Punkte aus dem alten Stand werden (wie in
        # der Tabelle) nicht geschrieben.
        self.assertIn("Flächensuche wurde inzwischen von jemand anderem geändert", html)
        self.assertNotIn("Die übrigen Eingaben wurden gespeichert.", html)
        self.assertIn('name="geladen_status" value="1|"', html)  # Seite zeigt den aktuellen Stand
        ergebnis = db.get_ergebnis(self.conn, tid)
        self.assertTrue(ergebnis["disqualifiziert"])
        self.assertFalse(ergebnis["abbruch"])
        self.assertIsNone(ergebnis["suche_flaechensuche"])

    def test_einzelseite_status_konflikt_speichert_punkte_einer_ungesperrten_zeile(self):
        tid = self._ed_teilnehmer()
        self._anmelden()
        grund_fremd, grund_eigen = list(db.ABBRUCH_GRUENDE)[:2]
        db.setze_ergebnis_status(self.conn, tid, False, True, abbruch_grund=grund_fremd)  # anderer Richter
        antwort = self.client.post(f"/teilnehmer/{tid}", data={
            "suche_Flächensuche": "30", "anzeige_Flächensuche": "20",
            "geladen_suche_Flächensuche": "", "geladen_anzeige_Flächensuche": "",
            "geladen_status": "0|", "abbruch": grund_eigen, "bogen": "Flächensuche",
        })
        self.assertEqual(antwort.status_code, 200)  # Konflikt: kein Weiterleiten zum Bogen
        html = antwort.data.decode()
        self.assertIn("Disqualifiziert/Abbruch wurde inzwischen", html)
        self.assertIn("Die übrigen Eingaben wurden gespeichert.", html)
        ergebnis = db.get_ergebnis(self.conn, tid)
        self.assertEqual(ergebnis["abbruch_grund"], grund_fremd)  # nicht überschrieben
        # Abbruch mit Grund sperrt nicht: die Punkte sind eine eigene Einheit und gespeichert.
        self.assertEqual((ergebnis["suche_flaechensuche"], ergebnis["anzeige_flaechensuche"]), (30, 20))

    def test_einzelseite_fremd_gesperrt_ohne_meldung_wenn_wert_schon_gleich(self):
        tid = self._ed_teilnehmer()
        db.eintragen_ergebnis(self.conn, tid, "Flächensuche", 30, 20)
        db.setze_ergebnis_status(self.conn, tid, True, False)  # anderer Richter, nach dem Laden
        self._anmelden()
        antwort = self.client.post(f"/teilnehmer/{tid}", data={
            "suche_Flächensuche": "30", "anzeige_Flächensuche": "20",
            "geladen_suche_Flächensuche": "", "geladen_anzeige_Flächensuche": "",
            "geladen_status": "0|",
        })
        self.assertEqual(antwort.status_code, 302)

    def test_einzelseite_unveraenderter_status_ueberschreibt_fremde_aenderung_nicht(self):
        tid = self._ed_teilnehmer()
        self._anmelden()
        db.setze_ergebnis_status(self.conn, tid, True, False)  # anderer Richter
        antwort = self.client.post(f"/teilnehmer/{tid}", data={
            "suche_Flächensuche": "30", "anzeige_Flächensuche": "20",
            "geladen_suche_Flächensuche": "", "geladen_anzeige_Flächensuche": "",
            "geladen_status": "0|",  # Status nicht angefasst
        })
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("Flächensuche wurde inzwischen von jemand anderem geändert", antwort.data.decode())
        ergebnis = db.get_ergebnis(self.conn, tid)
        self.assertTrue(ergebnis["disqualifiziert"])
        self.assertIsNone(ergebnis["suche_flaechensuche"])

    def test_einzelseite_dk_status_gilt_fuer_alle_disziplinen(self):
        dk = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Muster", vorname="B", rufname_hund="Bello", art="DK", stufe=2, startnummer=2,
        ))
        self._anmelden()
        daten = {"geladen_status": "0|", "dq": "1"}
        for disziplin in db.ALLE_DISZIPLINEN:
            daten.update({f"suche_{disziplin}": "", f"anzeige_{disziplin}": "",
                          f"geladen_suche_{disziplin}": "", f"geladen_anzeige_{disziplin}": ""})
        self.assertEqual(self.client.post(f"/teilnehmer/{dk}", data=daten).status_code, 302)
        self.assertTrue(db.get_ergebnis(self.conn, dk)["disqualifiziert"])
        seite = self.client.get(f"/teilnehmer/{dk}").data.decode()
        self.assertEqual(seite.count('name="dq"'), 1)
        self.assertIn("Aktuell gespeichert: disqualifiziert", seite)

    def test_einzelseite_kaputtes_statusfeld_gilt_als_veraendert(self):
        tid = self._ed_teilnehmer()
        self._anmelden()
        antwort = self.client.post(f"/teilnehmer/{tid}", data={
            "suche_Flächensuche": "", "anzeige_Flächensuche": "",
            "geladen_suche_Flächensuche": "", "geladen_anzeige_Flächensuche": "",
            "geladen_status": "kaputt", "dq": "1",
        })
        self.assertEqual(antwort.status_code, 302)
        self.assertTrue(db.get_ergebnis(self.conn, tid)["disqualifiziert"])

    def test_einzelseite_fehler_behaelt_haken_und_auswahl(self):
        tid = self._ed_teilnehmer()
        self._anmelden()
        grund = next(iter(db.ABBRUCH_GRUENDE))
        antwort = self.client.post(f"/teilnehmer/{tid}", data={
            "suche_Flächensuche": "30", "anzeige_Flächensuche": "",  # unvollständig
            "geladen_suche_Flächensuche": "", "geladen_anzeige_Flächensuche": "",
            "geladen_status": "0|", "abbruch": grund,
        })
        self.assertEqual(antwort.status_code, 200)
        html = antwort.data.decode()
        self.assertIn(f'<option value="{grund}" selected>', html)
        self.assertIn('name="geladen_status" value="0|"', html)
        self.assertFalse(db.get_ergebnis(self.conn, tid)["abbruch"])

    def test_einzelseite_ohne_statusfeld_laesst_status_unberuehrt(self):
        # Ältere Formulare/Skripte ohne geladen_status ändern Disqualifiziert/Abbruch nicht.
        tid = self._ed_teilnehmer()
        db.setze_ergebnis_status(self.conn, tid, True, False)
        self._anmelden()
        antwort = self.client.post(f"/teilnehmer/{tid}", data={
            "suche_Flächensuche": "30", "anzeige_Flächensuche": "20"})
        self.assertEqual(antwort.status_code, 302)
        ergebnis = db.get_ergebnis(self.conn, tid)
        self.assertTrue(ergebnis["disqualifiziert"])
        self.assertEqual(ergebnis["suche_flaechensuche"], 30)

    def test_einzelseite_bietet_ohne_grund_nur_bei_altdaten(self):
        tid = self._ed_teilnehmer()
        db.setze_ergebnis_status(self.conn, tid, False, True)  # Abbruch ohne Grund (Altdaten)
        self._anmelden()
        seite = self.client.get(f"/teilnehmer/{tid}").data.decode()
        self.assertIn('<option value="ohne_grund" selected>', seite)
        self.assertIn('name="geladen_status" value="0|ohne_grund"', seite)
        # Unverändert speichern ist erlaubt (kein „braucht einen Grund“).
        antwort = self.client.post(f"/teilnehmer/{tid}", data={
            "suche_Flächensuche": "", "anzeige_Flächensuche": "",
            "geladen_suche_Flächensuche": "", "geladen_anzeige_Flächensuche": "",
            "geladen_status": "0|ohne_grund", "abbruch": "ohne_grund",
        })
        self.assertEqual(antwort.status_code, 302)
        ergebnis = db.get_ergebnis(self.conn, tid)
        self.assertTrue(ergebnis["abbruch"])
        self.assertIsNone(ergebnis["abbruch_grund"])

    def test_ergebnis_dk_zeigt_alle_drei_disziplinen(self):
        teilnehmer_id = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Muster", vorname="B", rufname_hund="Bello", art="DK", stufe=2, startnummer=2,
        ))
        self._anmelden()
        antwort = self.client.get(f"/teilnehmer/{teilnehmer_id}")
        text = antwort.data.decode()
        for disziplin in db.ALLE_DISZIPLINEN:
            self.assertIn(disziplin, text)

    def test_ungueltiger_wert_wird_abgelehnt_und_nichts_gespeichert(self):
        teilnehmer_id = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Muster", vorname="C", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=3,
        ))
        self._anmelden()
        antwort = self.client.post(
            f"/teilnehmer/{teilnehmer_id}",
            data={"suche_Trümmerfeld": "999", "anzeige_Trümmerfeld": "10"},
        )
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("nur Werte von 0 bis 60".encode(), antwort.data)
        ergebnis = db.get_ergebnis(self.conn, teilnehmer_id)
        self.assertIsNone(ergebnis["suche_truemmerfeld"])

    def test_nicht_numerischer_wert_wird_abgelehnt(self):
        teilnehmer_id = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Muster", vorname="D", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=4,
        ))
        self._anmelden()
        antwort = self.client.post(
            f"/teilnehmer/{teilnehmer_id}",
            data={"suche_Trümmerfeld": "abc", "anzeige_Trümmerfeld": ""},
        )
        self.assertIn("nur Zahlen".encode(), antwort.data)

    def test_leere_felder_loeschen_vorhandenes_ergebnis(self):
        teilnehmer_id = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Muster", vorname="E", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=5,
        ))
        db.eintragen_ergebnis(self.conn, teilnehmer_id, "Trümmerfeld", 40, 20)
        self._anmelden()
        self.client.post(
            f"/teilnehmer/{teilnehmer_id}",
            data={"suche_Trümmerfeld": "", "anzeige_Trümmerfeld": ""},
        )
        ergebnis = db.get_ergebnis(self.conn, teilnehmer_id)
        self.assertIsNone(ergebnis["suche_truemmerfeld"])
        self.assertIsNone(ergebnis["anzeige_truemmerfeld"])

    def test_unbekannter_teilnehmer_liefert_404(self):
        self._anmelden()
        antwort = self.client.get("/teilnehmer/999999")
        self.assertEqual(antwort.status_code, 404)

    def test_dk_lost_update_schutz_bei_gleichzeitiger_bearbeitung_durch_zwei_richter(self):
        """QS-Fund 21.09. (höchste Priorität): bei einem Dreikampf-Teilnehmer wurden
        bisher IMMER alle drei Disziplinen gemeinsam gespeichert, basierend auf dem beim
        Laden der Seite sichtbaren Stand. Bearbeiten zwei Richter gleichzeitig
        verschiedene Disziplinen desselben Hundes, überschrieb der später speichernde
        Richter die zwischenzeitliche Eintragung des anderen mit dem bei ihm noch alten
        (leeren) Wert. Simuliert hier: beide Richter laden zuerst dieselbe (leere) Seite,
        Richter A speichert Trümmerfeld, DANACH speichert Richter B (mit dem beim Laden
        noch leeren Formularstand) Flächensuche - Richter As Eintragung darf dabei NICHT
        verloren gehen."""
        teilnehmer_id = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Muster", vorname="F", rufname_hund="Rex", art="DK", stufe=2, startnummer=6,
        ))
        self._anmelden()
        seite_a = self.client.get(f"/teilnehmer/{teilnehmer_id}").data.decode()
        seite_b = self.client.get(f"/teilnehmer/{teilnehmer_id}").data.decode()
        formular_a = self._formulardaten_aus_seite(seite_a, db.ALLE_DISZIPLINEN)
        formular_b = self._formulardaten_aus_seite(seite_b, db.ALLE_DISZIPLINEN)

        formular_a["suche_Trümmerfeld"] = "50"
        formular_a["anzeige_Trümmerfeld"] = "30"
        antwort_a = self.client.post(f"/teilnehmer/{teilnehmer_id}", data=formular_a)
        self.assertEqual(antwort_a.status_code, 302)

        # Richter B schickt sein Formular ab, das noch auf dem ALTEN (vor Richter As
        # Speicherung geladenen) Stand basiert - er hat nur Flächensuche geändert.
        formular_b["suche_Flächensuche"] = "40"
        formular_b["anzeige_Flächensuche"] = "20"
        antwort_b = self.client.post(f"/teilnehmer/{teilnehmer_id}", data=formular_b)
        self.assertEqual(antwort_b.status_code, 302)

        ergebnis = db.get_ergebnis(self.conn, teilnehmer_id)
        self.assertEqual(ergebnis["suche_truemmerfeld"], 50)
        self.assertEqual(ergebnis["anzeige_truemmerfeld"], 30)
        self.assertEqual(ergebnis["suche_flaechensuche"], 40)
        self.assertEqual(ergebnis["anzeige_flaechensuche"], 20)

    def test_dk_validierungsfehler_behaelt_korrekt_eingegebene_werte_der_anderen_disziplin(self):
        """QS-Fund 21.09.: bei einem Validierungsfehler wurde die Seite bisher aus dem
        GESPEICHERTEN DB-Stand neu aufgebaut statt aus den gerade abgeschickten
        Formulardaten - alle korrekt eingegebenen Werte derselben Absendung gingen
        dadurch verloren, auch wenn nur EINE Disziplin einen ungültigen Wert enthielt."""
        teilnehmer_id = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Muster", vorname="G", rufname_hund="Rex", art="DK", stufe=2, startnummer=7,
        ))
        self._anmelden()
        antwort = self.client.post(
            f"/teilnehmer/{teilnehmer_id}",
            data={
                "suche_Trümmerfeld": "999", "anzeige_Trümmerfeld": "10",
                "suche_Flächensuche": "42", "anzeige_Flächensuche": "22",
            },
        )
        self.assertEqual(antwort.status_code, 200)
        text = antwort.data.decode()
        self.assertIn("nur Werte von 0 bis 60".encode(), antwort.data)
        # Der korrekt eingegebene Wert der ANDEREN Disziplin steht weiterhin im
        # erneut angezeigten Formular, statt verworfen worden zu sein.
        self.assertEqual(self._formularfeld(text, "suche_Flächensuche"), "42")
        self.assertEqual(self._formularfeld(text, "anzeige_Flächensuche"), "22")
        # Nichts wurde gespeichert (wie bisher schon bei einem Validierungsfehler).
        ergebnis = db.get_ergebnis(self.conn, teilnehmer_id)
        self.assertIsNone(ergebnis["suche_truemmerfeld"])
        self.assertIsNone(ergebnis["suche_flaechensuche"])

    # --- Halb ausgefüllte Disziplin (Codeprüfung 22.09., G6) ---------------------

    def test_nur_suche_ohne_anzeige_wird_abgelehnt_und_nichts_gespeichert(self):
        teilnehmer_id = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Muster", vorname="H", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=8,
        ))
        self._anmelden()
        antwort = self.client.post(
            f"/teilnehmer/{teilnehmer_id}",
            data={"suche_Trümmerfeld": "45", "anzeige_Trümmerfeld": ""},
        )
        self.assertEqual(antwort.status_code, 200)
        text = antwort.data.decode()
        self.assertIn("Suche UND Anzeige", text)
        # Eingabe bleibt im Formular stehen (siehe _zeilen_aus_formular).
        self.assertEqual(self._formularfeld(text, "suche_Trümmerfeld"), "45")
        ergebnis = db.get_ergebnis(self.conn, teilnehmer_id)
        self.assertIsNone(ergebnis["suche_truemmerfeld"])
        self.assertIsNone(ergebnis["anzeige_truemmerfeld"])

    def test_dk_halbe_disziplin_blockiert_speichern_aller_disziplinen(self):
        teilnehmer_id = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Muster", vorname="I", rufname_hund="Rex", art="DK", stufe=2, startnummer=9,
        ))
        self._anmelden()
        seite = self.client.get(f"/teilnehmer/{teilnehmer_id}").data.decode()
        formular = self._formulardaten_aus_seite(seite, db.ALLE_DISZIPLINEN)
        formular["suche_Flächensuche"] = "40"
        formular["anzeige_Flächensuche"] = "20"
        formular["anzeige_Trümmerfeld"] = "30"  # Suche fehlt
        antwort = self.client.post(f"/teilnehmer/{teilnehmer_id}", data=formular)
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("Suche UND Anzeige", antwort.data.decode())
        self.assertIn("Trümmerfeld", antwort.data.decode())
        ergebnis = db.get_ergebnis(self.conn, teilnehmer_id)
        self.assertIsNone(ergebnis["suche_flaechensuche"])
        self.assertIsNone(ergebnis["anzeige_truemmerfeld"])

    def test_unveraenderter_halber_altbestand_blockiert_andere_disziplin_nicht(self):
        """Eine bereits halb gespeicherte Disziplin (Altbestand von vor dieser Prüfung)
        wird nur dann bemängelt, wenn der Richter sie selbst bearbeitet - das Speichern
        einer ANDEREN Disziplin desselben Teilnehmers muss weiterhin klappen, und der
        Altbestand bleibt unangetastet (Lost-Update-Schutz)."""
        teilnehmer_id = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Muster", vorname="J", rufname_hund="Rex", art="DK", stufe=2, startnummer=10,
        ))
        # Direkt per SQL statt über db.eintragen_ergebnis, damit der Altbestand auch dann
        # entsteht, falls eintragen_ergebnis selbst halbe Eingaben künftig ablehnt.
        self.conn.execute(
            "UPDATE ergebnisse SET suche_truemmerfeld = 50, anzeige_truemmerfeld = NULL WHERE teilnehmer_id = ?",
            (teilnehmer_id,),
        )
        self.conn.commit()
        self._anmelden()
        seite = self.client.get(f"/teilnehmer/{teilnehmer_id}").data.decode()
        formular = self._formulardaten_aus_seite(seite, db.ALLE_DISZIPLINEN)
        self.assertEqual(formular["suche_Trümmerfeld"], "50")
        formular["suche_Flächensuche"] = "40"
        formular["anzeige_Flächensuche"] = "20"
        antwort = self.client.post(f"/teilnehmer/{teilnehmer_id}", data=formular)
        self.assertEqual(antwort.status_code, 302)
        ergebnis = db.get_ergebnis(self.conn, teilnehmer_id)
        self.assertEqual(ergebnis["suche_flaechensuche"], 40)
        self.assertEqual(ergebnis["anzeige_flaechensuche"], 20)
        self.assertEqual(ergebnis["suche_truemmerfeld"], 50)
        self.assertIsNone(ergebnis["anzeige_truemmerfeld"])

        # Bearbeitet der Richter den halben Altbestand dagegen selbst (weiterhin halb),
        # wird er abgelehnt.
        seite = self.client.get(f"/teilnehmer/{teilnehmer_id}").data.decode()
        formular = self._formulardaten_aus_seite(seite, db.ALLE_DISZIPLINEN)
        formular["suche_Trümmerfeld"] = "55"
        antwort = self.client.post(f"/teilnehmer/{teilnehmer_id}", data=formular)
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("Suche UND Anzeige", antwort.data.decode())
        self.assertEqual(db.get_ergebnis(self.conn, teilnehmer_id)["suche_truemmerfeld"], 50)

    # --- Termine veröffentlichen/zurückholen/löschen (Upload/Download) -----------

    @staticmethod
    def _leere_sqlite_datei():
        """Eine 0-Byte-Datei ist eine gültige, leere SQLite-Datenbank - reicht als
        Upload-Inhalt, weil db.init_db() sie in der gefakten Export/Import-Funktion
        ohnehin nur öffnet, nicht fachlich auswertet (siehe _fake_exportiere_termin/
        _fake_importiere_ergebnisse oben)."""
        import io
        return (io.BytesIO(b""), "termin_verein.sqlite")

    @staticmethod
    def _kaputte_sqlite_datei():
        """Eine Datei mit der richtigen Endung (.sqlite), aber ungültigem Inhalt - QS-Fund
        21.09.: db.init_db() scheitert dabei mit sqlite3.DatabaseError ("file is not a
        database", eine Unterklasse von sqlite3.Error), siehe
        app_web._ungueltige_termin_datei_fehler."""
        return (io.BytesIO(b"das ist keine sqlite-datenbank, nur irgendein text"), "termin.sqlite")

    @staticmethod
    def _echte_sqlite_datei_mit_veranstaltung(verein: str, datum: str):
        """Baut - anders als _leere_sqlite_datei() oben - eine ECHTE, gültige
        Termin-Datei MIT befüllten Veranstaltungsdaten (für den
        Dubletten-Hinweis-Test unten, der db.get_veranstaltung() der hochgeladenen Datei
        braucht, um sie mit den bereits veröffentlichten Terminen zu vergleichen)."""
        fd, pfad = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        os.remove(pfad)
        sqlite_conn = db.init_db(pfad)
        db.set_veranstaltung(sqlite_conn, verein=verein, datum=datum)
        sqlite_conn.close()
        with open(pfad, "rb") as f:
            inhalt = f.read()
        os.remove(pfad)
        return (io.BytesIO(inhalt), "termin_verein.sqlite")

    def test_nicht_admin_bekommt_403_bei_termineverwaltung(self):
        self._anmelden()
        db.benutzer_anlegen(self.conn, "helfer", "helferpasswort")
        self.client.post("/logout")
        self.client.post("/", data={"benutzername": "helfer", "passwort": "helferpasswort"})
        for pfad, methode in [
            ("/admin/termine", "get"),
            ("/admin/termine/veroeffentlichen", "post"),
            (f"/admin/termine/{_TEST_SCHEMA}/zurueckholen", "post"),
            (f"/admin/termine/{_TEST_SCHEMA}/loeschen", "post"),
        ]:
            antwort = getattr(self.client, methode)(pfad)
            self.assertEqual(antwort.status_code, 403, pfad)

    def test_termin_veroeffentlichen_zeigt_bestaetigung(self):
        self._anmelden()
        antwort = self.client.post(
            "/admin/termine/veroeffentlichen",
            data={"sqlite_datei": self._leere_sqlite_datei()},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("Testverein".encode(), antwort.data)
        self.assertEqual(len(self.export_aufrufe), 1)

    def test_termin_veroeffentlichen_formular_nennt_desktop_termine_ordner(self):
        self._anmelden()
        antwort = self.client.get("/admin/termine")
        self.assertEqual(antwort.status_code, 200)
        self.assertIn(r"SHS-Pruefungsprogramm\Termine".encode(), antwort.data)

    def test_termin_veroeffentlichen_ohne_datei_zeigt_fehler(self):
        self._anmelden()
        antwort = self.client.post(
            "/admin/termine/veroeffentlichen", data={}, content_type="multipart/form-data"
        )
        self.assertIn("Bitte eine".encode(), antwort.data)
        self.assertEqual(self.export_aufrufe, [])

    def test_termin_veroeffentlichen_lehnt_falsche_dateiendung_ab(self):
        import io
        self._anmelden()
        antwort = self.client.post(
            "/admin/termine/veroeffentlichen",
            data={"sqlite_datei": (io.BytesIO(b""), "termin.txt")},
            content_type="multipart/form-data",
        )
        self.assertIn("keine .sqlite-Termin-Datei".encode(), antwort.data)
        self.assertEqual(self.export_aufrufe, [])

    def test_termin_veroeffentlichen_mit_beschaedigter_datei_zeigt_verstaendliche_meldung(self):
        """QS-Fund 21.09.: eine Upload-Datei mit der richtigen Endung, aber ungültigem
        Inhalt führte bisher zu einer rohen 500-Fehlerseite (db.init_db() scheiterte mit
        einer unbehandelten sqlite3.DatabaseError) statt der sonst üblichen
        verständlichen Fehlermeldung."""
        self._anmelden()
        antwort = self.client.post(
            "/admin/termine/veroeffentlichen",
            data={"sqlite_datei": self._kaputte_sqlite_datei()},
            content_type="multipart/form-data",
        )
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("keine gültige SHS-Termin-Datei".encode(), antwort.data)
        self.assertEqual(self.export_aufrufe, [])

    def test_termin_veroeffentlichen_zeigt_dublette_hinweis_bei_gleichem_verein_und_datum(self):
        """QS-Fund 21.09. (niedrigste Priorität der 6): bisher legte jeder Klick auf
        "Veröffentlichen" einen neuen, unabhängigen Termin an, auch wenn bereits ein
        Termin mit demselben Verein+Datum veröffentlicht war. Blockiert das
        Veröffentlichen NICHT, zeigt aber einen Hinweis auf der Erfolgsseite."""
        self.termine = [_termin_info(_TEST_SCHEMA, verein="Testverein", datum="2026-09-19")]
        self._anmelden()
        antwort = self.client.post(
            "/admin/termine/veroeffentlichen",
            data={"sqlite_datei": self._echte_sqlite_datei_mit_veranstaltung("Testverein", "2026-09-19")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("bereits einen veröffentlichten Termin".encode(), antwort.data)
        self.assertIn("Testverein".encode(), antwort.data)

    def test_termin_veroeffentlichen_ohne_dublette_zeigt_keinen_hinweis(self):
        self.termine = [_termin_info(_TEST_SCHEMA, verein="Anderer Verein", datum="2020-01-01")]
        self._anmelden()
        antwort = self.client.post(
            "/admin/termine/veroeffentlichen",
            data={"sqlite_datei": self._echte_sqlite_datei_mit_veranstaltung("Testverein", "2026-09-19")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(antwort.status_code, 200)
        self.assertNotIn("bereits einen veröffentlichten Termin".encode(), antwort.data)

    def test_termin_zurueckholen_zeigt_abweichungen(self):
        # Codeprüfung 22.09. (M2): nicht übernommene Ergebnisse wegen abweichendem
        # Teilnehmer müssen für den Admin sichtbar sein.
        self.import_bericht = db.ImportBericht(
            aktualisiert=0, ohne_startnummer_uebersprungen=[], nicht_gefunden=[],
            abweichungen=["Nr. 1: Web Muster, A (Rex, Trümmer LK 1) ≠ Termin-Datei Beispiel, B (Bello, Trümmer LK 1)"],
        )
        self._anmelden()
        antwort = self.client.post(
            f"/admin/termine/{_TEST_SCHEMA}/zurueckholen",
            data={"sqlite_datei": self._leere_sqlite_datei()},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(antwort.status_code, 200)
        text = antwort.data.decode()
        self.assertIn("NICHT übernommen", text)
        self.assertIn("Beispiel, B (Bello, Trümmer LK 1)", text)

    def test_termin_zurueckholen_zeigt_bericht_und_download_funktioniert(self):
        self.import_bericht = db.ImportBericht(
            aktualisiert=2, ohne_startnummer_uebersprungen=["Muster, A"], nicht_gefunden=["7"]
        )
        self._anmelden()
        antwort = self.client.post(
            f"/admin/termine/{_TEST_SCHEMA}/zurueckholen",
            data={"sqlite_datei": self._leere_sqlite_datei()},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(antwort.status_code, 200)
        text = antwort.data.decode()
        self.assertIn("2 Teilnehmer", text)
        self.assertIn("Muster, A", text)
        self.assertIn("7", text)
        self.assertEqual(self.import_aufrufe, [_TEST_SCHEMA])

        # Der Download-Link in der Antwort funktioniert genau einmal.
        import re
        treffer = re.search(r'href="(/admin/termine/download/[^"]+)"', text)
        self.assertIsNotNone(treffer)
        download_antwort = self.client.get(treffer.group(1))
        self.assertEqual(download_antwort.status_code, 200)
        zweite_antwort = self.client.get(treffer.group(1))
        self.assertEqual(zweite_antwort.status_code, 404)

    def test_termin_zurueckholen_mit_unbekanntem_schema_liefert_400(self):
        self._anmelden()
        antwort = self.client.post(
            "/admin/termine/unbekanntes_schema/zurueckholen",
            data={"sqlite_datei": self._leere_sqlite_datei()},
            content_type="multipart/form-data",
        )
        self.assertEqual(antwort.status_code, 400)

    def test_termin_zurueckholen_ohne_datei_zeigt_fehler(self):
        self._anmelden()
        antwort = self.client.post(
            f"/admin/termine/{_TEST_SCHEMA}/zurueckholen", data={}, content_type="multipart/form-data"
        )
        self.assertIn("Bitte dieselbe".encode(), antwort.data)
        self.assertEqual(self.import_aufrufe, [])

    def test_termin_zurueckholen_mit_beschaedigter_datei_zeigt_verstaendliche_meldung(self):
        """QS-Fund 21.09. - Gegenstück zu
        test_termin_veroeffentlichen_mit_beschaedigter_datei_zeigt_verstaendliche_meldung
        oben, für die "Ergebnisse zurückholen"-Route."""
        self._anmelden()
        antwort = self.client.post(
            f"/admin/termine/{_TEST_SCHEMA}/zurueckholen",
            data={"sqlite_datei": self._kaputte_sqlite_datei()},
            content_type="multipart/form-data",
        )
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("keine gültige SHS-Termin-Datei".encode(), antwort.data)
        self.assertEqual(self.import_aufrufe, [])

    def test_admin_bereinigt_abgelaufene_download_tokens_und_loescht_temporaere_datei(self):
        """QS-Fund (19./20.09.): klickt der Administrator den Download-Link nach
        "Ergebnisse zurückholen" nie an, blieben Eintrag UND die temporäre .sqlite-Datei
        mit personenbezogenen Teilnehmer-/Ergebnisdaten unbegrenzt lange liegen (siehe
        Kommentar bei app_web._ausstehende_downloads). Simuliert hier einen "alten"
        Eintrag direkt (statt _DOWNLOAD_TOKEN_GUELTIGKEIT_SEKUNDEN in einem Test wirklich
        abzuwarten) und prüft, dass ein beliebiger Aufruf einer admin-geschützten Ansicht
        (hier: die Terminliste selbst) ihn zusammen mit der Datei abräumt."""
        self._anmelden()
        fd, temp_pfad = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        alter_token = secrets.token_urlsafe(16)
        app_web._ausstehende_downloads[alter_token] = (
            temp_pfad, "alt.sqlite",
            self._monotonic_vor(app_web._DOWNLOAD_TOKEN_GUELTIGKEIT_SEKUNDEN + 1),
        )

        self.client.get("/admin/termine")

        self.assertNotIn(alter_token, app_web._ausstehende_downloads)
        self.assertFalse(os.path.exists(temp_pfad))

    def test_admin_laesst_noch_gueltige_download_tokens_unangetastet(self):
        self._anmelden()
        fd, temp_pfad = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(temp_pfad) and os.remove(temp_pfad))
        frischer_token = secrets.token_urlsafe(16)
        app_web._ausstehende_downloads[frischer_token] = (temp_pfad, "frisch.sqlite", time.monotonic())

        self.client.get("/admin/termine")

        self.assertIn(frischer_token, app_web._ausstehende_downloads)
        self.assertTrue(os.path.exists(temp_pfad))

    @staticmethod
    def _monotonic_vor(sekunden):
        """Liefert einen Zeitstempel im selben Zeitmaß wie time.monotonic(), der so weit
        in der Vergangenheit liegt, wie er hier als Sekunden übergeben wird - ohne dafür
        wirklich warten oder time.monotonic() selbst mocken zu müssen (das würde auch das
        Flask/Werkzeug-interne Timing der Testanfrage verfälschen)."""
        return time.monotonic() - sekunden

    def test_termin_loeschen_entfernt_termin_und_session(self):
        self._anmelden()
        self.assertEqual(self.client.get("/teilnehmer").status_code, 200)
        antwort = self.client.post(f"/admin/termine/{_TEST_SCHEMA}/loeschen", follow_redirects=True)
        self.assertEqual(antwort.status_code, 200)
        self.assertEqual(self.geloeschte_termine, [_TEST_SCHEMA])
        self.assertEqual(self.termine, [])
        # Die Session-Auswahl wurde entfernt - ein erneuter Aufruf der Teilnehmerliste
        # landet deshalb wieder bei der (jetzt leeren) Terminauswahl.
        antwort = self.client.get("/teilnehmer", follow_redirects=True)
        self.assertIn("kein Termin veröffentlicht".encode(), antwort.data)

    def test_termin_loeschen_lehnt_unbekanntes_schema_ab(self):
        # Codeprüfung 22.09., G7: wie beim Zurückholen nur registrierte Termine - ein
        # unbekannter (wenn auch formal gültiger) Schema-Name erreicht
        # db.loesche_termin_postgres gar nicht erst.
        self._anmelden()
        antwort = self.client.post("/admin/termine/termin_unbekannt/loeschen")
        self.assertEqual(antwort.status_code, 400)
        self.assertEqual(self.geloeschte_termine, [])
        self.assertEqual([t.schema_name for t in self.termine], [_TEST_SCHEMA])

    # --- Session-Gültigkeit (Codeprüfung 22.09., G8) -----------------------------

    def _session_cookie_mit_alter(self, sekunden: int) -> str:
        """Erzeugt ein korrekt signiertes Session-Cookie für den angemeldeten Admin,
        dessen (von itsdangerous mitsignierter) Zeitstempel `sekunden` in der
        Vergangenheit liegt - simuliert ein altes, z. B. abgegriffenes Cookie."""
        serializer = app_web.app.session_interface.get_signing_serializer(app_web.app)
        # C-1 (03.10.2026): eine gültige Session enthält auch die Konto-Kennung.
        kennung = db.benutzer_stand(self.conn, _ADMIN_NAME)["kennung"]
        daten = {"benutzername": _ADMIN_NAME, "ist_admin": True, "schema_name": _TEST_SCHEMA,
                 "konto_kennung": kennung}
        with patch("time.time", return_value=time.time() - sekunden):
            return serializer.dumps(daten)

    def test_session_lebensdauer_ist_12_stunden(self):
        from datetime import timedelta
        self.assertEqual(app_web.app.permanent_session_lifetime, timedelta(hours=12))

    def test_session_cookie_aelter_als_12_stunden_wird_abgewiesen(self):
        db.admin_einrichten(self.conn, _ADMIN_NAME, _ADMIN_PASSWORT)
        cookie_name = app_web.app.config["SESSION_COOKIE_NAME"]

        # Gegenprobe: ein 11 Stunden altes Cookie gilt noch.
        self.client.set_cookie(cookie_name, self._session_cookie_mit_alter(11 * 3600))
        self.assertEqual(self.client.get("/teilnehmer").status_code, 200)

        # 13 Stunden alt: abgewiesen, leere Session -> Weiterleitung zum Login.
        self.client.set_cookie(cookie_name, self._session_cookie_mit_alter(13 * 3600))
        antwort = self.client.get("/teilnehmer")
        self.assertEqual(antwort.status_code, 302)
        self.assertTrue(antwort.headers["Location"].endswith("/"))


class _FormularLeser(HTMLParser):
    """Liest aus der Ergebnistabelle, was ein Browser beim Absenden mitschickte: Eingabefelder
    (auch versteckte), angehakte Kontrollkästchen und die gewählten Einträge der Auswahllisten."""

    def __init__(self):
        super().__init__()
        self.daten: dict[str, str] = {}
        self._select: str | None = None
        self._erste_option: str | None = None
        self._gewaehlt = False
        self._textarea: str | None = None

    def handle_data(self, data):
        if self._textarea is not None:
            self.daten[self._textarea] += data

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "textarea" and a.get("name"):
            self._textarea = a["name"]
            self.daten[self._textarea] = ""
        elif tag == "input" and a.get("name"):
            if a.get("type") == "checkbox":
                if "checked" in a:
                    self.daten[a["name"]] = a.get("value", "on")
            else:
                self.daten[a["name"]] = a.get("value") or ""
        elif tag == "select":
            self._select, self._erste_option, self._gewaehlt = a.get("name"), None, False
        elif tag == "option" and self._select:
            wert = a.get("value", "")
            if self._erste_option is None:
                self._erste_option = wert
            if "selected" in a:
                self.daten[self._select] = wert
                self._gewaehlt = True

    def handle_endtag(self, tag):
        if tag == "textarea":
            self._textarea = None
        if tag == "select" and self._select:
            if not self._gewaehlt:
                self.daten[self._select] = self._erste_option or ""
            self._select = None


class TestErgebnistabelle(_AppWebTestBasis):
    """Ergebnistabelle /ergebnisse (Marco 18.11.2026): Anzeige, Filter, Speichern, Validierung,
    Lost-Update-Schutz, Sperrregel für Disqualifiziert/Abbruch, Rechte und Sicherheit."""

    T, F, B = db.ALLE_DISZIPLINEN  # Trümmerfeld, Flächensuche, Behältnisstrecke

    def setUp(self):
        super().setUp()
        self.ed = self._teilnehmer("Muster", "Anna", "Rex", "ED", 1, 1, "Flächensuche")
        self.dk = self._teilnehmer("Beispiel", "Bernd", "Bello", "DK", 2, 2)
        self.ed2 = self._teilnehmer("Probe", "Cora", "Luna", "ED", 3, 3, "Trümmerfeld")

    def _teilnehmer(self, nachname, vorname, hund, art, stufe, nr, disziplin=None):
        return db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname=nachname, vorname=vorname, rufname_hund=hund, art=art, stufe=stufe,
            disziplin=disziplin, startnummer=nr,
        ))

    def _seite(self, pfad="/ergebnisse", client=None) -> dict:
        antwort = (client or self.client).get(pfad)
        self.assertEqual(antwort.status_code, 200)
        leser = _FormularLeser()
        leser.feed(antwort.data.decode())
        return leser.daten

    def _speichern(self, daten, pfad="/ergebnisse", client=None, **kw):
        return (client or self.client).post(pfad, data=daten, **kw)

    # --- Anzeige und Filter -------------------------------------------------------

    def test_zeigt_eine_zeile_je_teilnehmenden_teilnehmer_mit_status(self):
        keine = self._teilnehmer("Fehlt", "Dora", "Nix", "ED", 1, 4, "Trümmerfeld")
        db.setze_keine_teilnahme(self.conn, keine, True)
        db.eintragen_ergebnis(self.conn, self.ed, self.F, 40, 30)
        db.setze_ergebnis_status(self.conn, self.ed2, True, False)
        self._anmelden()
        antwort = self.client.get("/ergebnisse")
        html = antwort.data.decode()
        self.assertEqual(antwort.status_code, 200)
        daten = self._seite()
        for t in (self.ed, self.dk, self.ed2):
            self.assertIn(f"geladen_{t}", daten)
        self.assertNotIn(f"geladen_{keine}", daten)
        self.assertIn("Muster, Anna", html)
        self.assertNotIn("Fehlt, Dora", html)
        self.assertEqual(daten[f"suche_{self.F}_{self.ed}"], "40")
        self.assertEqual(daten[f"anzeige_{self.F}_{self.ed}"], "30")
        # ED: nur die eigene Disziplin hat Eingabefelder, DK alle drei
        self.assertNotIn(f"suche_{self.T}_{self.ed}", daten)
        for d in db.ALLE_DISZIPLINEN:
            self.assertIn(f"suche_{d}_{self.dk}", daten)
        self.assertIn(">gespeichert</span>", html)
        self.assertIn(">disqualifiziert</span>", html)
        self.assertIn(">noch kein Ergebnis</span>", html)
        self.assertEqual(daten[f"dq_{self.ed2}"], "1")
        self.assertIn("Suche (0-60)", html)
        self.assertIn("Anzeige (0-40)", html)
        self.assertIn('inputmode="numeric"', html)

    def test_abbruch_status_nennt_den_grund(self):
        db.setze_ergebnis_status(self.conn, self.dk, False, True, abbruch_grund="krankheit")
        self._anmelden()
        daten = self._seite()
        self.assertEqual(daten[f"abbruch_{self.dk}"], "krankheit")
        self.assertIn("Abbruch: Krankheit", self.client.get("/ergebnisse").data.decode())

    def test_filter_nach_art_startnummer_und_name(self):
        self._anmelden()
        lk_dk = db.leistungsklasse_label(db.get_teilnehmer(self.conn, self.dk))
        daten = self._seite("/ergebnisse?lk=" + lk_dk.replace(" ", "+"))
        self.assertEqual([k for k in daten if k.startswith("geladen_")], [f"geladen_{self.dk}"])
        daten = self._seite("/ergebnisse?nr=3")
        self.assertEqual([k for k in daten if k.startswith("geladen_")], [f"geladen_{self.ed2}"])
        daten = self._seite("/ergebnisse?q=rex")
        self.assertEqual([k for k in daten if k.startswith("geladen_")], [f"geladen_{self.ed}"])
        daten = self._seite("/ergebnisse?q=muster+anna")
        self.assertEqual([k for k in daten if k.startswith("geladen_")], [f"geladen_{self.ed}"])
        # unbekannte Art/LK wird wie „Alle“ behandelt
        daten = self._seite("/ergebnisse?lk=gibt-es-nicht")
        self.assertEqual(len([k for k in daten if k.startswith("geladen_")]), 3)

    # --- Wer hat wann eingetragen (UX-Test Web 19.11.2026, B6) -------------------------------------

    def _als_helfer(self):
        db.benutzer_anlegen(self.conn, "helfer", "helferpasswort")  # Rolle „eintragen“
        self.client.post("/logout")
        self.client.post("/", data={"benutzername": "helfer", "passwort": "helferpasswort"}, follow_redirects=True)

    def test_tabelle_merkt_konto_je_disziplin_und_status(self):
        self._anmelden()
        self._als_helfer()
        daten = self._seite()
        daten[f"suche_{self.F}_{self.ed}"], daten[f"anzeige_{self.F}_{self.ed}"] = "45", "25"
        daten[f"dq_{self.dk}"] = "1"
        self.assertEqual(self._speichern(daten).status_code, 302)
        aenderungen = db.aenderungen_lesen(self.conn)
        self.assertEqual(set(aenderungen), {self.ed, self.dk})
        self.assertEqual(aenderungen[self.ed][self.F][0], "helfer")
        self.assertEqual(aenderungen[self.dk][db.BEREICH_STATUS][0], "helfer")
        self.assertNotIn(self.ed2, aenderungen)  # nichts geändert, nichts gemerkt
        # Richter sehen es nicht ...
        self.assertNotIn("zuletzt helfer", self.client.get("/ergebnisse").data.decode())
        # ... der Admin schon, mit Einzelheiten im Tooltip
        self.client.post("/logout")
        self._anmelden()
        html = self.client.get("/ergebnisse").data.decode()
        self.assertIn(f"zuletzt helfer, gerade eben ({self.F})", html)
        self.assertIn(f'title="{db.BEREICH_STATUS}: helfer, gerade eben"', html)

    def test_unveraendertes_speichern_merkt_nichts_und_letzter_gewinnt(self):
        self._anmelden()
        self._speichern(self._seite())
        self.assertEqual(db.aenderungen_lesen(self.conn), {})
        db.aenderung_merken(self.conn, self.ed, self.F, "alt")
        daten = self._seite()
        daten[f"suche_{self.F}_{self.ed}"], daten[f"anzeige_{self.F}_{self.ed}"] = "45", "25"
        self._speichern(daten)
        self.assertEqual(db.aenderungen_lesen(self.conn)[self.ed][self.F][0], _ADMIN_NAME)

    def test_einzelseite_und_bogen_merken_das_konto(self):
        self._anmelden()
        self._als_helfer()
        self.client.post(f"/teilnehmer/{self.ed}", data={
            f"suche_{self.F}": "40", f"anzeige_{self.F}": "30", "geladen_status": "0|", "abbruch": "krankheit"})
        aenderungen = db.aenderungen_lesen(self.conn)[self.ed]
        self.assertEqual(set(aenderungen), {self.F, db.BEREICH_STATUS})
        pfad = f"/bewertungsbogen/{self.ed2}/{quote(self.T)}"
        leser = _FormularLeser()
        leser.feed(self.client.get(pfad).data.decode())
        daten = leser.daten
        daten[f"notiz_{self.ed2}"] = "nur eine Notiz"
        self.client.post(pfad, data=daten)
        self.assertEqual(set(db.aenderungen_lesen(self.conn)[self.ed2]), {self.T})

    def test_status_allein_von_der_einzelseite_wird_gemerkt(self):
        self._anmelden()
        self.client.post(f"/teilnehmer/{self.ed}", data={
            f"suche_{self.F}": "", f"anzeige_{self.F}": "",
            f"geladen_suche_{self.F}": "", f"geladen_anzeige_{self.F}": "",
            "geladen_status": "0|", "dq": "1"})
        self.assertEqual(set(db.aenderungen_lesen(self.conn)[self.ed]), {db.BEREICH_STATUS})

    def test_einzelseite_schreibt_gleichen_fremden_wert_nicht_dem_konto_zu(self):
        # QS U13: wie `schon_gleich` der Tabelle - steht der Wert schon so da, wird nichts geschrieben.
        self._anmelden()
        self._als_helfer()
        db.eintragen_ergebnis(self.conn, self.ed, self.F, 40, 30)
        db.aenderung_merken(self.conn, self.ed, self.F, "fremd")
        antwort = self.client.post(f"/teilnehmer/{self.ed}", data={
            f"suche_{self.F}": "40", f"anzeige_{self.F}": "30",
            f"geladen_suche_{self.F}": "", f"geladen_anzeige_{self.F}": "", "geladen_status": "0|"})
        self.assertIn("aenderung=0", antwort.headers["Location"])
        self.assertEqual(db.aenderungen_lesen(self.conn)[self.ed][self.F][0], "fremd")

    def test_vor_wann(self):
        from datetime import datetime, timezone
        jetzt = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(app_web._vor_wann("2026-11-20T11:59:30+00:00", jetzt), "gerade eben")
        self.assertEqual(app_web._vor_wann("2026-11-20T11:55:00+00:00", jetzt), "vor 5 Min.")
        self.assertEqual(app_web._vor_wann("2026-11-20T09:00:00+00:00", jetzt), "vor 3 Std.")
        self.assertEqual(app_web._vor_wann("2026-11-18T09:00:00+00:00", jetzt), "am 18.11.")
        self.assertEqual(app_web._vor_wann("kaputt", jetzt), "?")

    def test_vor_wann_datum_in_deutscher_zeit(self):
        # Marco nach der QS in U13: 23:30 UTC ist in Deutschland schon der nächste Tag.
        from datetime import datetime, timezone
        jetzt = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(app_web._vor_wann("2026-11-18T23:30:00+00:00", jetzt), "am 19.11.")  # Winterzeit +1
        self.assertEqual(app_web._vor_wann("2026-11-18T22:30:00+00:00", jetzt), "am 18.11.")
        sommer = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(app_web._vor_wann("2026-07-18T22:30:00+00:00", sommer), "am 19.07.")  # Sommerzeit +2

    def test_vor_wann_ohne_zonendaten_faellt_auf_die_eu_regel_zurueck(self):
        import zoneinfo
        from datetime import datetime, timezone
        from unittest import mock

        def fehlt(_name):
            raise zoneinfo.ZoneInfoNotFoundError("Europe/Berlin")

        jetzt = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
        with mock.patch.object(zoneinfo, "ZoneInfo", fehlt):
            self.assertEqual(app_web._vor_wann("2026-11-18T23:30:00+00:00", jetzt), "am 19.11.")

    def test_deutsche_zeit_ohne_zonendaten_nach_eu_regel(self):
        from datetime import datetime, timezone
        regel = app_web._deutsche_zeit_nach_eu_regel
        # 2026: Sommerzeit vom 29.03. 01:00 UTC bis 25.10. 01:00 UTC
        self.assertEqual(regel(datetime(2026, 3, 29, 0, 59, tzinfo=timezone.utc)).utcoffset().total_seconds(), 3600)
        self.assertEqual(regel(datetime(2026, 3, 29, 1, 0, tzinfo=timezone.utc)).utcoffset().total_seconds(), 7200)
        self.assertEqual(regel(datetime(2026, 10, 25, 0, 59, tzinfo=timezone.utc)).utcoffset().total_seconds(), 7200)
        self.assertEqual(regel(datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc)).utcoffset().total_seconds(), 3600)
        try:
            from zoneinfo import ZoneInfo
            berlin = ZoneInfo("Europe/Berlin")
        except Exception:  # noqa: BLE001 - ohne Zonendaten nur die Regel prüfen
            return
        for monat in range(1, 13):
            for tag in (1, 15, 28):
                for stunde in (0, 1, 2, 23):
                    t = datetime(2027, monat, tag, stunde, tzinfo=timezone.utc)
                    self.assertEqual(regel(t).utcoffset(), t.astimezone(berlin).utcoffset(), t)

    def test_web_aenderungen_nie_in_der_termin_datei(self):
        # Die Tabelle gehört nur ins Web-Schema: nicht in SCHEMA, also nie in eine Termin-Datei.
        self.assertNotIn("web_aenderungen", db.SCHEMA)
        fd, pfad = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        os.remove(pfad)
        conn = db.init_db(pfad)
        try:
            namen = {z[0] for z in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        finally:
            conn.close()
            os.remove(pfad)
        self.assertNotIn("web_aenderungen", namen)

    def test_sortierung_nach_startnummer(self):
        # UX-Test Web 19.11.2026 (C2, Marco): nach Start-Nr. statt nach Prüfung (vorher DK, Trümmerfeld,
        # Behältnisse, Fläche). Nr. 10 nach Nr. 9 (Zahl, nicht Text), ohne Nummer am Ende.
        self._teilnehmer("Zehn", "Zora", "Zack", "ED", 1, 10, "Flächensuche")
        self._teilnehmer("Neun", "Nina", "Nemo", "DK", 2, 9)
        self._teilnehmer("Ohne", "Olga", "Odin", "ED", 1, None, "Trümmerfeld")
        self._anmelden()
        html = self.client.get("/ergebnisse").data.decode()
        namen = ("Muster, Anna", "Beispiel, Bernd", "Probe, Cora", "Neun, Nina", "Zehn, Zora", "Ohne, Olga")
        positionen = [html.index(name) for name in namen]
        self.assertEqual(positionen, sorted(positionen))

    def test_tabelle_mobil_kopfzeile_fest_und_filter_springt_zur_tabelle(self):
        # UX-Test Web 19.11.2026 (C1, C4)
        self._anmelden()
        html = self.client.get("/ergebnisse").data.decode()
        self.assertIn("table.ergebnisse thead { position: sticky; top: 0;", html)
        self.assertIn('<div class="tabellenrahmen" id="tabelle">', html)
        self.assertIn('action="/ergebnisse#tabelle" role="search"', html)
        self.assertIn('class="nur-handy"', html)
        self.assertIn("min-height: 44px", html)

    def test_speichern_behaelt_den_filter(self):
        self._anmelden()
        html = self.client.get("/ergebnisse?q=rex").data.decode()
        # (B3) Anker #meldung: der Browser springt nach dem Speichern zur Meldung.
        self.assertIn('action="/ergebnisse?q=rex#meldung"', html)
        self.assertIn('<div id="meldung"', html)
        daten = self._seite("/ergebnisse?q=rex")
        daten[f"suche_{self.F}_{self.ed}"], daten[f"anzeige_{self.F}_{self.ed}"] = "50", "35"
        antwort = self._speichern(daten, "/ergebnisse?q=rex")
        self.assertEqual(antwort.status_code, 302)
        self.assertIn("q=rex", antwort.headers["Location"])
        # die nicht angezeigten Teilnehmer bleiben unangetastet
        self.assertIsNone(db.get_ergebnis(self.conn, self.dk)["suche_truemmerfeld"])
        self.assertEqual(db.get_ergebnis(self.conn, self.ed)["suche_flaechensuche"], 50)

    # --- Speichern ----------------------------------------------------------------

    def test_speichern_ok_fuer_ed_und_dk(self):
        self._anmelden()
        daten = self._seite()
        daten[f"suche_{self.F}_{self.ed}"], daten[f"anzeige_{self.F}_{self.ed}"] = "45", "25"
        for d, (s, a) in zip(db.ALLE_DISZIPLINEN, [("50", "30"), ("41", "22"), ("55", "38")]):
            daten[f"suche_{d}_{self.dk}"], daten[f"anzeige_{d}_{self.dk}"] = s, a
        antwort = self._speichern(daten, follow_redirects=True)
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("Gespeichert: 2 Teilnehmer.", antwort.data.decode())
        self.assertEqual(db.get_ergebnis(self.conn, self.ed)["anzeige_flaechensuche"], 25)
        dk = db.get_ergebnis(self.conn, self.dk)
        self.assertEqual((dk["suche_truemmerfeld"], dk["anzeige_behaeltnis"]), (50, 38))
        self.assertEqual(dk["suche_flaechensuche"], 41)
        self.assertIsNone(db.get_ergebnis(self.conn, self.ed2)["suche_truemmerfeld"])

    def test_unveraenderte_zeilen_werden_nicht_geschrieben(self):
        self._anmelden()
        daten = self._seite()
        with patch.object(db, "eintragen_ergebnis") as eintragen, patch.object(db, "setze_ergebnis_status") as status:
            antwort = self._speichern(daten, follow_redirects=True)
        self.assertIn("Keine Änderungen zu speichern", antwort.data.decode())
        eintragen.assert_not_called()
        status.assert_not_called()

    def test_leeren_beider_felder_loescht_das_ergebnis(self):
        db.eintragen_ergebnis(self.conn, self.ed, self.F, 40, 30)
        self._anmelden()
        daten = self._seite()
        daten[f"suche_{self.F}_{self.ed}"] = daten[f"anzeige_{self.F}_{self.ed}"] = ""
        self._speichern(daten)
        ergebnis = db.get_ergebnis(self.conn, self.ed)
        self.assertIsNone(ergebnis["suche_flaechensuche"])
        self.assertIsNone(ergebnis["anzeige_flaechensuche"])

    def test_maximalwerte_sind_erlaubt_und_ein_mehr_wird_abgelehnt(self):
        self._anmelden()
        daten = self._seite()
        daten[f"suche_{self.F}_{self.ed}"], daten[f"anzeige_{self.F}_{self.ed}"] = "60", "40"
        self._speichern(daten)
        self.assertEqual(db.get_ergebnis(self.conn, self.ed)["suche_flaechensuche"], 60)
        for suche, anzeige, text in (("61", "10", "von 0 bis 60"), ("10", "41", "von 0 bis 40"), ("-1", "10", "von 0 bis 60")):
            daten = self._seite()
            daten[f"suche_{self.T}_{self.ed2}"], daten[f"anzeige_{self.T}_{self.ed2}"] = suche, anzeige
            antwort = self._speichern(daten)
            self.assertEqual(antwort.status_code, 200)
            self.assertIn(text, antwort.data.decode())
            self.assertIsNone(db.get_ergebnis(self.conn, self.ed2)["suche_truemmerfeld"])

    def test_validierungsfehler_speichert_nichts_und_behaelt_alle_eingaben(self):
        self._anmelden()
        daten = self._seite()
        daten[f"suche_{self.F}_{self.ed}"], daten[f"anzeige_{self.F}_{self.ed}"] = "45", "25"  # gültig
        daten[f"suche_{self.T}_{self.ed2}"], daten[f"anzeige_{self.T}_{self.ed2}"] = "30", ""  # unvollständig
        antwort = self._speichern(daten)
        html = antwort.data.decode()
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("Es wurde nichts gespeichert", html)
        self.assertIn("Bitte Suche UND Anzeige eintragen", html)
        self.assertIsNone(db.get_ergebnis(self.conn, self.ed)["suche_flaechensuche"])
        self.assertIsNone(db.get_ergebnis(self.conn, self.ed2)["suche_truemmerfeld"])
        neu = _FormularLeser()
        neu.feed(html)
        self.assertEqual(neu.daten[f"suche_{self.F}_{self.ed}"], "45")  # gültige Eingabe bleibt stehen
        self.assertEqual(neu.daten[f"anzeige_{self.F}_{self.ed}"], "25")
        self.assertEqual(neu.daten[f"suche_{self.T}_{self.ed2}"], "30")
        # der geladene Stand bleibt der ursprüngliche (leere), nicht die Eingabe
        self.assertEqual(neu.daten[f"geladen_{self.ed}"], daten[f"geladen_{self.ed}"])
        # ... und ein zweiter Versuch mit korrigiertem Wert speichert beide Zeilen
        neu.daten[f"anzeige_{self.T}_{self.ed2}"] = "20"
        self._speichern(neu.daten)
        self.assertEqual(db.get_ergebnis(self.conn, self.ed)["suche_flaechensuche"], 45)
        self.assertEqual(db.get_ergebnis(self.conn, self.ed2)["anzeige_truemmerfeld"], 20)

    def test_nicht_numerische_eingabe_wird_abgelehnt(self):
        self._anmelden()
        daten = self._seite()
        daten[f"suche_{self.F}_{self.ed}"], daten[f"anzeige_{self.F}_{self.ed}"] = "abc", "10"
        antwort = self._speichern(daten)
        self.assertIn("nur Zahlen", antwort.data.decode())
        self.assertIsNone(db.get_ergebnis(self.conn, self.ed)["anzeige_flaechensuche"])

    # --- Lost Update ---------------------------------------------------------------

    def test_lost_update_zweiter_richter_ueberschreibt_nicht(self):
        self._anmelden()
        richter_a = self._seite()
        richter_b = self._seite()
        richter_a[f"suche_{self.T}_{self.dk}"], richter_a[f"anzeige_{self.T}_{self.dk}"] = "50", "30"
        self._speichern(richter_a)
        # B hat die alte (leere) Seite geladen und ändert dieselbe Disziplin sowie eine andere
        richter_b[f"suche_{self.T}_{self.dk}"], richter_b[f"anzeige_{self.T}_{self.dk}"] = "10", "10"
        richter_b[f"suche_{self.F}_{self.dk}"], richter_b[f"anzeige_{self.F}_{self.dk}"] = "44", "22"
        antwort = self._speichern(richter_b)
        html = antwort.data.decode()
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("inzwischen von jemand anderem geändert", html)
        dk = db.get_ergebnis(self.conn, self.dk)
        self.assertEqual((dk["suche_truemmerfeld"], dk["anzeige_truemmerfeld"]), (50, 30))  # A bleibt
        self.assertEqual((dk["suche_flaechensuche"], dk["anzeige_flaechensuche"]), (44, 22))  # B's andere Disziplin
        neu = _FormularLeser()
        neu.feed(html)
        self.assertEqual(neu.daten[f"suche_{self.T}_{self.dk}"], "50")  # aktueller Wert wird gezeigt
        self.assertIn("aktuell Suche/Anzeige: 50/30", html)
        self.assertIn("Ihre Eingabe 10/10", html)

    def test_lost_update_bei_status(self):
        self._anmelden()
        seite_b = self._seite()
        db.setze_ergebnis_status(self.conn, self.ed, False, True, abbruch_grund="krankheit")  # Richter A
        seite_b[f"dq_{self.ed}"] = "1"
        antwort = self._speichern(seite_b)
        self.assertIn("inzwischen von jemand anderem geändert", antwort.data.decode())
        ergebnis = db.get_ergebnis(self.conn, self.ed)
        self.assertEqual((ergebnis["disqualifiziert"], ergebnis["abbruch"]), (0, 1))

    def test_punkte_nach_fremder_disqualifikation_werden_nicht_geschrieben(self):
        self._anmelden()
        seite_b = self._seite()
        db.setze_ergebnis_status(self.conn, self.ed, True, False)  # Richter A
        seite_b[f"suche_{self.F}_{self.ed}"], seite_b[f"anzeige_{self.F}_{self.ed}"] = "40", "20"
        antwort = self._speichern(seite_b)
        self.assertIn("inzwischen von jemand anderem geändert", antwort.data.decode())
        self.assertIsNone(db.get_ergebnis(self.conn, self.ed)["suche_flaechensuche"])

    def test_unveraenderte_felder_ueberschreiben_fremde_aenderungen_nicht(self):
        self._anmelden()
        seite_b = self._seite()
        db.eintragen_ergebnis(self.conn, self.ed, self.F, 33, 11)  # Richter A
        antwort = self._speichern(seite_b)  # B ändert nichts
        self.assertEqual(antwort.status_code, 302)
        self.assertEqual(db.get_ergebnis(self.conn, self.ed)["suche_flaechensuche"], 33)

    # --- Disqualifiziert / Abbruch ---------------------------------------------------

    def test_disqualifiziert_wird_gesetzt_und_ignoriert_punkte_der_zeile(self):
        db.eintragen_ergebnis(self.conn, self.ed, self.F, 40, 20)
        self._anmelden()
        daten = self._seite()
        daten[f"dq_{self.ed}"] = "1"
        daten[f"suche_{self.F}_{self.ed}"], daten[f"anzeige_{self.F}_{self.ed}"] = "5", ""  # würde sonst abgelehnt
        antwort = self._speichern(daten)
        self.assertEqual(antwort.status_code, 302)
        ergebnis = db.get_ergebnis(self.conn, self.ed)
        self.assertEqual(ergebnis["disqualifiziert"], 1)
        self.assertEqual((ergebnis["suche_flaechensuche"], ergebnis["anzeige_flaechensuche"]), (40, 20))
        # gesperrte Zeile: Felder nur lesbar, Punkte bleiben sichtbar
        html = self.client.get("/ergebnisse").data.decode()
        self.assertRegex(html, rf'name="suche_{self.F}_{self.ed}"[^>]*readonly')
        # Häkchen wieder weg: Punkte sind weiter da
        daten = self._seite()
        del daten[f"dq_{self.ed}"]
        self._speichern(daten)
        ergebnis = db.get_ergebnis(self.conn, self.ed)
        self.assertEqual((ergebnis["disqualifiziert"], ergebnis["suche_flaechensuche"]), (0, 40))

    def test_abbruch_mit_grund_laesst_teilbewertung_zu(self):
        self._anmelden()
        daten = self._seite()
        daten[f"abbruch_{self.dk}"] = "verletzung_hund"
        daten[f"suche_{self.T}_{self.dk}"], daten[f"anzeige_{self.T}_{self.dk}"] = "30", "20"
        self._speichern(daten)
        ergebnis = db.get_ergebnis(self.conn, self.dk)
        self.assertEqual((ergebnis["abbruch"], ergebnis["abbruch_grund"]), (1, "verletzung_hund"))
        self.assertEqual(ergebnis["suche_truemmerfeld"], 30)
        # Abbruch zurücknehmen
        daten = self._seite()
        daten[f"abbruch_{self.dk}"] = ""
        self._speichern(daten)
        ergebnis = db.get_ergebnis(self.conn, self.dk)
        self.assertEqual((ergebnis["abbruch"], ergebnis["abbruch_grund"]), (0, None))

    def test_abbruch_ohne_grund_wird_abgelehnt(self):
        self._anmelden()
        daten = self._seite()
        daten[f"abbruch_{self.ed}"] = "ohne_grund"
        antwort = self._speichern(daten)
        self.assertIn("Abbruch braucht einen Grund", antwort.data.decode())
        self.assertEqual(db.get_ergebnis(self.conn, self.ed)["abbruch"], 0)

    def test_unbekannter_abbruchgrund_wird_abgelehnt(self):
        self._anmelden()
        daten = self._seite()
        daten[f"abbruch_{self.ed}"] = "Quatsch"
        antwort = self._speichern(daten)
        self.assertIn("Unbekannter Abbruchgrund", antwort.data.decode())

    def test_alter_abbruch_ohne_grund_bleibt_erhalten_und_sperrt_punkte(self):
        self.conn.execute("UPDATE ergebnisse SET abbruch = 1, abbruch_grund = NULL WHERE teilnehmer_id = ?", (self.ed,))
        self.conn.commit()
        self._anmelden()
        daten = self._seite()
        self.assertEqual(daten[f"abbruch_{self.ed}"], "ohne_grund")
        self.assertIn("Abbruch (ohne Grund, Altdaten)", self.client.get("/ergebnisse").data.decode())
        self.assertEqual(self._speichern(daten).status_code, 302)  # unverändert: kein Fehler
        daten[f"dq_{self.ed}"] = "1"
        self._speichern(daten)
        ergebnis = db.get_ergebnis(self.conn, self.ed)
        self.assertEqual((ergebnis["disqualifiziert"], ergebnis["abbruch"], ergebnis["abbruch_grund"]), (1, 1, None))

    # --- Rechte und Sicherheit -------------------------------------------------------

    def test_nicht_angemeldet_wird_zum_login_geleitet(self):
        antwort = self.client.get("/ergebnisse")
        self.assertEqual(antwort.status_code, 302)
        self.assertTrue(antwort.headers["Location"].endswith("/"))
        antwort = self.client.post("/ergebnisse", data={f"geladen_{self.ed}": "x"})
        self.assertEqual(antwort.status_code, 302)
        self.assertIsNone(db.get_ergebnis(self.conn, self.ed)["suche_flaechensuche"])

    def test_ohne_gewaehlten_termin_geht_es_zur_terminauswahl(self):
        self.termine = [_termin_info(_TEST_SCHEMA), _termin_info("termin_zwei", id=2)]
        self._anmelden()
        antwort = self.client.get("/ergebnisse")
        self.assertEqual(antwort.status_code, 302)
        self.assertIn("/termin-waehlen", antwort.headers["Location"])

    def test_post_ohne_csrf_token_wird_abgelehnt(self):
        self._anmelden()
        daten = self._seite()
        daten[f"suche_{self.F}_{self.ed}"], daten[f"anzeige_{self.F}_{self.ed}"] = "45", "25"
        daten.pop("csrf_token")
        # FlaskClient.post direkt: umgeht das automatische Token des _CsrfTestClient
        antwort = FlaskClient.post(self.client, "/ergebnisse", data=daten)
        self.assertEqual(antwort.status_code, 403)
        antwort = FlaskClient.post(self.client, "/ergebnisse", data={**daten, "csrf_token": "falsch"})
        self.assertEqual(antwort.status_code, 403)
        self.assertIsNone(db.get_ergebnis(self.conn, self.ed)["suche_flaechensuche"])

    def test_viele_formularfelder_nur_fuer_angemeldete(self):
        felder = {f"feld_{n}": "1" for n in range(1500)}  # über Werkzeugs Standardgrenze (1000)
        # Nicht angemeldet: es gelten die Standardgrenzen, die Anfrage wird abgelehnt, bevor das
        # CSRF-Token zählt (413 statt 403).
        # (Die Feldgrenze gilt nur für multipart-Formulare, wie sie die Tabelle sendet.)
        antwort = FlaskClient.post(
            app_web.app.test_client(), "/ergebnisse", data=felder, content_type="multipart/form-data")
        self.assertEqual(antwort.status_code, 413)
        # Angemeldet: die höhere Grenze gilt, die Anfrage kommt bis zur normalen Prüfung.
        self._anmelden()
        antwort = FlaskClient.post(self.client, "/ergebnisse", data=felder, content_type="multipart/form-data")
        self.assertEqual(antwort.status_code, 403)  # CSRF-Token fehlt, aber nicht 413

    def test_rolle_eintragen_darf_die_tabelle_nutzen(self):
        self._anmelden()
        db.benutzer_anlegen(self.conn, "helfer", "helferpasswort")
        self.client.post("/logout")
        self.client.post("/", data={"benutzername": "helfer", "passwort": "helferpasswort"}, follow_redirects=True)
        with self.client.session_transaction() as sitzung:
            self.assertEqual(sitzung.get("benutzername"), "helfer")
            self.assertFalse(sitzung.get("ist_admin"))
        daten = self._seite()
        daten[f"suche_{self.F}_{self.ed}"], daten[f"anzeige_{self.F}_{self.ed}"] = "45", "25"
        daten[f"abbruch_{self.dk}"] = "ungehorsam"
        self.assertEqual(self._speichern(daten).status_code, 302)
        self.assertEqual(db.get_ergebnis(self.conn, self.ed)["suche_flaechensuche"], 45)
        self.assertEqual(db.get_ergebnis(self.conn, self.dk)["abbruch_grund"], "ungehorsam")

    def test_fremde_oder_nicht_teilnehmende_ids_werden_ignoriert(self):
        keine = self._teilnehmer("Fehlt", "Dora", "Nix", "ED", 1, 4, "Trümmerfeld")
        db.setze_keine_teilnahme(self.conn, keine, True)
        self._anmelden()
        daten = self._seite()
        daten[f"suche_{self.F}_{self.ed}"], daten[f"anzeige_{self.F}_{self.ed}"] = "45", "25"
        for fremd in (999999, keine):
            daten[f"geladen_{fremd}"] = ",|0|"
            daten[f"suche_{self.T}_{fremd}"], daten[f"anzeige_{self.T}_{fremd}"] = "10", "10"
            daten[f"dq_{fremd}"] = "1"
        daten["geladen_abc"] = "x"
        daten["geladen_-5"] = "x"
        antwort = self._speichern(daten)
        html = antwort.data.decode()
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("Gespeichert: 1 Teilnehmer.", html)
        self.assertIn("2 Zeilen gehören nicht (mehr) zu diesem Termin", html)
        self.assertEqual(db.get_ergebnis(self.conn, self.ed)["suche_flaechensuche"], 45)
        ergebnis = db.get_ergebnis(self.conn, keine)
        self.assertEqual((ergebnis["disqualifiziert"], ergebnis["suche_truemmerfeld"]), (0, None))
        self.assertIsNone(db.get_ergebnis(self.conn, 999999))

    def test_manipulierte_geladen_felder_fuehren_nicht_zum_absturz(self):
        self._anmelden()
        daten = self._seite()
        for kaputt in ("", "quatsch", "1,2|3,4|5,6|1|x", "|||"):
            daten[f"geladen_{self.dk}"] = kaputt
            daten[f"suche_{self.T}_{self.dk}"], daten[f"anzeige_{self.T}_{self.dk}"] = "11", "12"
            self.assertEqual(self._speichern(daten).status_code, 302)
            self.assertEqual(db.get_ergebnis(self.conn, self.dk)["suche_truemmerfeld"], 11)

    def test_tabelle_laesst_sich_ohne_javascript_und_mit_festem_kopf_ausliefern(self):
        self._anmelden()
        antwort = self.client.get("/ergebnisse")
        html = antwort.data.decode()
        self.assertNotIn("<script", html)
        self.assertIn("position: sticky", html)
        self.assertIn(".tabellenrahmen { overflow: auto;", html)  # seit U5 in beide Richtungen
        self.assertIn("script-src 'none'", antwort.headers["Content-Security-Policy"])

    def test_navigation_und_links_zwischen_liste_und_tabelle(self):
        self._anmelden()
        liste = self.client.get("/teilnehmer").data.decode()
        self.assertIn('href="/ergebnisse"', liste)
        tabelle = self.client.get("/ergebnisse").data.decode()
        self.assertIn('href="/teilnehmer"', tabelle)

    # --- Große Zahl Zeilen -----------------------------------------------------------

    def test_viele_zeilen_werden_in_einer_transaktion_gespeichert(self):
        for i in range(250):
            self._teilnehmer(f"Viel{i:03d}", "X", f"Hund{i}", "DK", 1, 100 + i)
        self._anmelden()
        daten = self._seite()
        ids = [int(k[len("geladen_"):]) for k in daten if k.startswith("geladen_")]
        self.assertEqual(len(ids), 253)
        self.assertGreater(len(daten), 1000)  # mehr als Werkzeugs Standardgrenze für Formularfelder
        for tid in ids:
            daten[f"suche_{self.T}_{tid}"], daten[f"anzeige_{self.T}_{tid}"] = "20", "10"
        antwort = self._speichern(daten, follow_redirects=True)
        self.assertEqual(antwort.status_code, 200)
        # alle außer self.ed (ED Flächensuche: das Feld für Trümmerfeld gibt es dort nicht)
        self.assertIn("Gespeichert: 252 Teilnehmer.", antwort.data.decode())
        self.assertEqual(db.get_ergebnis(self.conn, max(ids))["suche_truemmerfeld"], 20)

    def test_sammelspeichern_rollt_bei_einem_fehler_alles_zurueck(self):
        for i in range(210):
            self._teilnehmer(f"Viel{i:03d}", "X", f"Hund{i}", "ED", 1, 100 + i, "Trümmerfeld")
        self._anmelden()
        daten = self._seite()
        ids = [int(k[len("geladen_"):]) for k in daten if k.startswith("geladen_")]
        for tid in ids:
            daten[f"suche_{self.T}_{tid}"], daten[f"anzeige_{self.T}_{tid}"] = "20", "10"
        echt = db.eintragen_ergebnis
        zaehler = {"n": 0}

        def fehlerhaft(*args, **kwargs):
            zaehler["n"] += 1
            if zaehler["n"] == 100:  # CHECK-Verletzung mitten im Sammelspeichern
                return echt(args[0], args[1], args[2], 999, 999, **kwargs)
            return echt(*args, **kwargs)

        with patch.object(db, "eintragen_ergebnis", fehlerhaft), self.assertRaises(sqlite3.IntegrityError):
            self._speichern(daten)
        gespeichert = [r for r in db.ergebnisse_je_teilnehmer(self.conn).values() if r["suche_truemmerfeld"] is not None]
        self.assertEqual(gespeichert, [])


class TestBewertungsbogen(_AppWebTestBasis):
    """Online-Bewertungsbogen /bewertungsbogen/<id>/<Disziplin> (Marco 18.11.2026): Anzeige, Speichern
    in die Ergebnisspalten, Validierung, Lost-Update-Schutz, Notiz, Rechte und die Knöpfe in der
    Ergebnistabelle."""

    T, F, B = db.ALLE_DISZIPLINEN  # Trümmerfeld, Flächensuche, Behältnisstrecke

    def setUp(self):
        super().setUp()
        self.ed = self._teilnehmer("Muster", "Anna", "Rex", "ED", 1, 1, "Flächensuche")
        self.dk = self._teilnehmer("Beispiel", "Bernd", "Bello", "DK", 2, 2)
        self.ed2 = self._teilnehmer("Probe", "Cora", "Luna", "ED", 3, 3, "Trümmerfeld")
        self.conn.execute(
            "UPDATE teilnehmer SET gegenstand_1 = ?, gegenstand_1_disziplin = ? WHERE id = ?",
            ("Metallröhrchen", self.F, self.ed))
        self.conn.execute(
            "UPDATE teilnehmer SET gegenstand_1 = ?, gegenstand_1_disziplin = ?, gegenstand_2 = ?, gegenstand_2_disziplin = ? WHERE id = ?",
            ("Holzwürfel", self.T, "Stoffball", self.B, self.dk))
        self.conn.commit()

    def _teilnehmer(self, nachname, vorname, hund, art, stufe, nr, disziplin=None):
        return db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname=nachname, vorname=vorname, rufname_hund=hund, art=art, stufe=stufe,
            disziplin=disziplin, startnummer=nr,
        ))

    @staticmethod
    def _pfad(tid, disziplin, filter_=""):
        return f"/bewertungsbogen/{tid}/{quote(disziplin)}{filter_}"

    _seite = TestErgebnistabelle._seite  # Formular der Ergebnistabelle lesen (Knopf „Bogen“)

    def _bogen(self, tid, disziplin, client=None) -> dict:
        antwort = (client or self.client).get(self._pfad(tid, disziplin))
        self.assertEqual(antwort.status_code, 200)
        leser = _FormularLeser()
        leser.feed(antwort.data.decode())
        return leser.daten

    def _senden(self, daten, tid, disziplin, **kw):
        return self.client.post(self._pfad(tid, disziplin), data=daten, **kw)

    def _punkte(self, daten, tid, disziplin, suche, anzeige):
        daten[f"suche_{disziplin}_{tid}"], daten[f"anzeige_{disziplin}_{tid}"] = suche, anzeige

    # --- Anzeige ---------------------------------------------------------------------

    def test_zeigt_den_bogen_einer_ed_disziplin(self):
        self._anmelden()
        antwort = self.client.get(self._pfad(self.ed, self.F))
        html = antwort.data.decode()
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("Bewertungsbogen SHS – Spürhundsport", html)
        for text in ("Muster, Anna", "Rex", "Flächensuche", "Metallröhrchen", "Suchleistung – Punktzahl (0-60)",
                     "Anzeige – Punktzahl (0-40)", "Disqualifiziert", "Notiz zum Bogen (Position Gegenstand, Besonderheiten)",
                     "Speichern und zurück zur Tabelle"):
            self.assertIn(text, html)
        self.assertIn("Gesamtpunktzahl Flächensuche", html)
        daten = self._bogen(self.ed, self.F)
        for name in (f"suche_{self.F}_{self.ed}", f"anzeige_{self.F}_{self.ed}", f"geladen_{self.ed}",
                     f"geladen_notiz_{self.ed}", f"notiz_{self.ed}", f"abbruch_{self.ed}", "csrf_token"):
            self.assertIn(name, daten)

    def test_zeigt_bei_dk_nur_die_gewaehlte_disziplin_mit_ihrem_gegenstand(self):
        self._anmelden()
        html = self.client.get(self._pfad(self.dk, self.T)).data.decode()
        self.assertIn("Holzwürfel", html)
        self.assertNotIn("Stoffball", html)
        daten = self._bogen(self.dk, self.T)
        self.assertIn(f"suche_{self.T}_{self.dk}", daten)
        self.assertNotIn(f"suche_{self.F}_{self.dk}", daten)
        self.assertNotIn(f"suche_{self.B}_{self.dk}", daten)
        self.assertIn("Stoffball", self.client.get(self._pfad(self.dk, self.B)).data.decode())
        # ohne zugeordneten Gegenstand entfällt die Zeile (UX-Test Web 19.11.2026, D4: „nicht hinterlegt“ war unklar)
        html = self.client.get(self._pfad(self.dk, self.F)).data.decode()
        self.assertNotIn("nicht hinterlegt", html)
        self.assertNotIn("Zu suchender Gegenstand", html)

    def test_bogen_zeigt_hinweis_bei_ungueltigen_punkten_und_erklaert_hf(self):
        # UX-Test Web 19.11.2026 (B4, D3): Hinweis direkt am Feld (per CSS bei :invalid sichtbar).
        self._anmelden()
        html = self.client.get(self._pfad(self.ed, self.F)).data.decode()
        self.assertIn('<p class="feld-hinweis" id="hinweis-suche">Bitte eine ganze Zahl von 0 bis 60 eintragen.</p>', html)
        self.assertIn('<p class="feld-hinweis" id="hinweis-anzeige">Bitte eine ganze Zahl von 0 bis 40 eintragen.</p>', html)
        self.assertIn('aria-describedby="hinweis-suche"', html)
        self.assertIn("input:invalid + .feld-hinweis { display: block; }", html)
        self.assertIn("Verletzung des Hundeführers", html)
        # A4: feste Kopfleiste ab Tablet-Breite
        self.assertIn("header { position: sticky; top: 0; z-index: 20; }", html)

    def test_bogen_aus_der_liste_fuehrt_zur_liste_zurueck(self):
        self._anmelden()
        pfad = self._pfad(self.ed, self.F, "?von=liste")
        html = self.client.get(pfad).data.decode()
        self.assertIn("Speichern und zurück zur Teilnehmerliste", html)
        self.assertIn('href="/teilnehmer">Abbrechen', html)
        daten = self._bogen(self.ed, self.F)
        daten[f"suche_{self.F}_{self.ed}"], daten[f"anzeige_{self.F}_{self.ed}"] = "40", "30"
        daten["weiter"] = "tabelle"
        antwort = self.client.post(pfad, data=daten)
        self.assertEqual(antwort.status_code, 302)
        self.assertEqual(antwort.headers["Location"], f"/teilnehmer?gespeichert={self.ed}&aenderung=1")

    def test_bogen_von_der_einzelseite_fuehrt_dorthin_zurueck(self):
        self._anmelden()
        pfad = self._pfad(self.ed, self.F, "?von=teilnehmer")
        html = self.client.get(pfad).data.decode()
        self.assertIn("Speichern und zurück zur Seite des Teilnehmers", html)
        self.assertIn(f'href="/teilnehmer/{self.ed}">Abbrechen', html)
        daten = self._bogen(self.ed, self.F)
        daten["weiter"] = "tabelle"
        antwort = self.client.post(pfad, data=daten)
        self.assertEqual(antwort.headers["Location"], f"/teilnehmer/{self.ed}?gespeichert=0")
        self.assertIn("Keine Änderungen im Bewertungsbogen zu speichern.",
                      self.client.get(antwort.headers["Location"]).data.decode())
        daten[f"suche_{self.F}_{self.ed}"], daten[f"anzeige_{self.F}_{self.ed}"] = "40", "30"
        antwort = self.client.post(pfad, data=daten)
        self.assertEqual(antwort.headers["Location"], f"/teilnehmer/{self.ed}?gespeichert=1")
        self.assertIn("Bewertungsbogen gespeichert.", self.client.get(antwort.headers["Location"]).data.decode())
        for unsinn in ("2", "<b>", "1x"):  # andere Werte zeigen nichts
            html = self.client.get(f"/teilnehmer/{self.ed}?gespeichert={unsinn}").data.decode()
            self.assertNotIn("Bewertungsbogen gespeichert", html)
            self.assertNotIn("Keine Änderungen im Bewertungsbogen", html)

    def test_bogen_speichern_behaelt_die_herkunft_und_verwirft_tabellenfilter(self):
        self._anmelden()
        pfad = self._pfad(self.ed, self.F, "?von=liste&q=rex&lk=x")
        html = self.client.get(pfad).data.decode()
        self.assertIn(f'action="{self._pfad(self.ed, self.F, "?von=liste")}"', html)
        daten = self._bogen(self.ed, self.F)
        daten["weiter"] = "bogen"
        antwort = self.client.post(self._pfad(self.ed, self.F, "?von=liste"), data=daten)
        ziel = antwort.headers["Location"]
        self.assertTrue(ziel.startswith(self._pfad(self.ed, self.F, "?")), ziel)
        self.assertEqual(sorted(ziel.split("?", 1)[1].split("&")), ["gespeichert=0", "von=liste"])
        # Fehlerfall: Seite bleibt, Formular sendet weiter mit ?von=liste
        daten[f"suche_{self.F}_{self.ed}"] = "84"
        html = self.client.post(self._pfad(self.ed, self.F, "?von=liste"), data=daten).data.decode()
        self.assertIn("Es wurde nichts gespeichert", html)
        self.assertIn(f'action="{self._pfad(self.ed, self.F, "?von=liste")}"', html)

    def test_bogen_unbekannte_herkunft_fuehrt_zur_tabelle(self):
        self._anmelden()
        html = self.client.get(self._pfad(self.ed, self.F, "?von=//evil.example")).data.decode()
        self.assertIn("Speichern und zurück zur Tabelle", html)
        self.assertNotIn("evil", html)

    def test_zeigt_gespeicherte_werte_und_notiz(self):
        db.eintragen_ergebnis(self.conn, self.ed, self.F, 40, 30)
        db.setze_notiz(self.conn, self.ed, self.F, "Ecke links hinten")
        self._anmelden()
        daten = self._bogen(self.ed, self.F)
        self.assertEqual((daten[f"suche_{self.F}_{self.ed}"], daten[f"anzeige_{self.F}_{self.ed}"]), ("40", "30"))
        self.assertEqual(daten[f"notiz_{self.ed}"], "Ecke links hinten")
        self.assertEqual(daten[f"geladen_notiz_{self.ed}"], "Ecke links hinten")
        html = self.client.get(self._pfad(self.ed, self.F)).data.decode()
        self.assertRegex(html, r"Gesamtpunktzahl Flächensuche:\s*<strong>70</strong>")

    def test_ist_ohne_javascript_und_mit_notizfeld_grenze(self):
        self._anmelden()
        antwort = self.client.get(self._pfad(self.ed, self.F))
        html = antwort.data.decode()
        self.assertNotIn("<script", html)
        self.assertIn("script-src 'none'", antwort.headers["Content-Security-Policy"])
        self.assertIn(f'maxlength="{db.NOTIZ_MAX}"', html)

    def test_falsche_disziplin_fremde_id_und_nicht_teilnehmende_sind_404(self):
        keine = self._teilnehmer("Fehlt", "Dora", "Nix", "ED", 1, 4, "Trümmerfeld")
        db.setze_keine_teilnahme(self.conn, keine, True)
        self._anmelden()
        for tid, disziplin in ((self.ed, self.T), (self.ed, self.B), (self.ed2, self.F), (self.dk, "Quatsch"),
                               (999999, self.T), (keine, self.T)):
            self.assertEqual(self.client.get(self._pfad(tid, disziplin)).status_code, 404, (tid, disziplin))
            self.assertEqual(self.client.post(self._pfad(tid, disziplin), data={}).status_code, 404, (tid, disziplin))

    # --- Speichern -------------------------------------------------------------------

    def test_speichern_schreibt_punkte_in_die_ergebnisspalten_und_zeigt_gesamt_und_wertnote(self):
        self._anmelden()
        daten = self._bogen(self.ed, self.F)
        self._punkte(daten, self.ed, self.F, "55", "35")
        antwort = self._senden(daten, self.ed, self.F)
        self.assertEqual(antwort.status_code, 302)
        self.assertIn(self._pfad(self.ed, self.F), antwort.headers["Location"])
        ergebnis = db.get_ergebnis(self.conn, self.ed)
        self.assertEqual((ergebnis["suche_flaechensuche"], ergebnis["anzeige_flaechensuche"]), (55, 35))
        html = self.client.get(antwort.headers["Location"]).data.decode()
        self.assertIn("Gespeichert.", html)
        self.assertRegex(html, r"Gesamtpunktzahl Flächensuche:\s*<strong>90</strong>")
        self.assertIn("Wertnote Flächensuche", html)
        self.assertIn("gespeichert", html)
        # dieselben Werte stehen in der Ergebnistabelle
        tabelle = _FormularLeser()
        tabelle.feed(self.client.get("/ergebnisse").data.decode())
        self.assertEqual((tabelle.daten[f"suche_{self.F}_{self.ed}"], tabelle.daten[f"anzeige_{self.F}_{self.ed}"]), ("55", "35"))

    def test_speichern_und_zurueck_leitet_zur_zeile_in_der_tabelle(self):
        self._anmelden()
        daten = self._bogen(self.ed2, self.T)
        self._punkte(daten, self.ed2, self.T, "40", "20")
        antwort = self._senden({**daten, "weiter": "tabelle"}, self.ed2, self.T)
        self.assertEqual(antwort.status_code, 302)
        self.assertTrue(antwort.headers["Location"].endswith(f"#zeile-{self.ed2}"), antwort.headers["Location"])
        self.assertIn("/ergebnisse", antwort.headers["Location"])
        self.assertEqual(db.get_ergebnis(self.conn, self.ed2)["suche_truemmerfeld"], 40)

    def test_filter_der_tabelle_bleibt_erhalten(self):
        self._anmelden()
        daten = self._bogen(self.ed, self.F)
        antwort = self._senden({**daten, "weiter": "tabelle"}, self.ed, self.F)  # ohne Filter
        self.assertNotIn("q=", antwort.headers["Location"])
        html = self.client.get(self._pfad(self.ed, self.F, "?q=rex")).data.decode()
        self.assertIn(f'action="{self._pfad(self.ed, self.F, "?q=rex")}"', html)
        self.assertIn('href="/ergebnisse?q=rex#zeile-', html)
        antwort = self.client.post(self._pfad(self.ed, self.F, "?q=rex"), data={**daten, "weiter": "tabelle"})
        self.assertIn("q=rex", antwort.headers["Location"])

    def test_dk_speichern_veraendert_nur_diese_disziplin(self):
        db.eintragen_ergebnis(self.conn, self.dk, self.F, 44, 22)
        db.eintragen_ergebnis(self.conn, self.dk, self.B, 50, 30)
        self._anmelden()
        daten = self._bogen(self.dk, self.T)
        self._punkte(daten, self.dk, self.T, "60", "40")
        self._senden(daten, self.dk, self.T)
        ergebnis = db.get_ergebnis(self.conn, self.dk)
        self.assertEqual((ergebnis["suche_truemmerfeld"], ergebnis["anzeige_truemmerfeld"]), (60, 40))
        self.assertEqual((ergebnis["suche_flaechensuche"], ergebnis["anzeige_flaechensuche"]), (44, 22))
        self.assertEqual((ergebnis["suche_behaeltnis"], ergebnis["anzeige_behaeltnis"]), (50, 30))

    def test_dk_wertnote_erst_wenn_alle_drei_disziplinen_vollstaendig_sind(self):
        self._anmelden()
        for d, (s, a) in ((self.T, ("50", "30")), (self.F, ("45", "30"))):
            daten = self._bogen(self.dk, d)
            self._punkte(daten, self.dk, d, s, a)
            self._senden(daten, self.dk, d)
        html = self.client.get(self._pfad(self.dk, self.F)).data.decode()
        self.assertRegex(html, r"Gesamtpunktzahl Flächensuche:\s*<strong>75</strong>")
        self.assertNotIn("Wertnote Dreikampf", html)
        self.assertIn("sobald für alle drei Disziplinen", html)
        daten = self._bogen(self.dk, self.B)
        self._punkte(daten, self.dk, self.B, "50", "30")
        self._senden(daten, self.dk, self.B)
        html = self.client.get(self._pfad(self.dk, self.B)).data.decode()
        self.assertIn("Wertnote Dreikampf", html)
        self.assertNotIn("sobald für alle drei Disziplinen", html)

    def test_leeren_beider_felder_loescht_die_punkte(self):
        db.eintragen_ergebnis(self.conn, self.ed, self.F, 40, 30)
        self._anmelden()
        daten = self._bogen(self.ed, self.F)
        self._punkte(daten, self.ed, self.F, "", "")
        self._senden(daten, self.ed, self.F)
        ergebnis = db.get_ergebnis(self.conn, self.ed)
        self.assertEqual((ergebnis["suche_flaechensuche"], ergebnis["anzeige_flaechensuche"]), (None, None))

    def test_unveraendert_speichern_schreibt_nichts(self):
        self._anmelden()
        daten = self._bogen(self.ed, self.F)
        with patch.object(db, "eintragen_ergebnis") as eintragen, patch.object(db, "setze_ergebnis_status") as status, \
                patch.object(db, "setze_notiz") as notiz:
            antwort = self._senden(daten, self.ed, self.F, follow_redirects=True)
        self.assertIn("Keine Änderungen zu speichern", antwort.data.decode())
        eintragen.assert_not_called()
        status.assert_not_called()
        notiz.assert_not_called()

    # --- Validierung -----------------------------------------------------------------

    def test_maximalwerte_gehen_und_ein_mehr_wird_abgelehnt(self):
        self._anmelden()
        daten = self._bogen(self.ed, self.F)
        self._punkte(daten, self.ed, self.F, "60", "40")
        self._senden(daten, self.ed, self.F)
        self.assertEqual(db.get_ergebnis(self.conn, self.ed)["suche_flaechensuche"], 60)
        for suche, anzeige, text in (("61", "10", "von 0 bis 60"), ("10", "41", "von 0 bis 40"), ("-1", "10", "von 0 bis 60"),
                                     ("abc", "10", "nur Zahlen")):
            daten = self._bogen(self.ed2, self.T)
            self._punkte(daten, self.ed2, self.T, suche, anzeige)
            antwort = self._senden(daten, self.ed2, self.T)
            self.assertEqual(antwort.status_code, 200)
            self.assertIn(text, antwort.data.decode())
            self.assertIsNone(db.get_ergebnis(self.conn, self.ed2)["suche_truemmerfeld"])

    def test_nur_eines_von_beiden_wird_abgelehnt_und_die_eingaben_bleiben(self):
        self._anmelden()
        daten = self._bogen(self.ed, self.F)
        self._punkte(daten, self.ed, self.F, "30", "")
        daten[f"notiz_{self.ed}"] = "bleibt stehen"
        antwort = self._senden(daten, self.ed, self.F)
        html = antwort.data.decode()
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("Es wurde nichts gespeichert", html)
        self.assertIn("Bitte Suche UND Anzeige eintragen", html)
        neu = _FormularLeser()
        neu.feed(html)
        self.assertEqual(neu.daten[f"suche_{self.F}_{self.ed}"], "30")
        self.assertEqual(neu.daten[f"notiz_{self.ed}"], "bleibt stehen")
        self.assertEqual(neu.daten[f"geladen_{self.ed}"], daten[f"geladen_{self.ed}"])
        ergebnis = db.get_ergebnis(self.conn, self.ed)
        self.assertIsNone(ergebnis["suche_flaechensuche"])
        self.assertIsNone(ergebnis[db.NOTIZ_SPALTEN[self.F]])  # auch die Notiz wurde nicht gespeichert
        # zweiter Versuch mit korrigiertem Wert
        neu.daten[f"anzeige_{self.F}_{self.ed}"] = "20"
        self._senden(neu.daten, self.ed, self.F)
        ergebnis = db.get_ergebnis(self.conn, self.ed)
        self.assertEqual((ergebnis["suche_flaechensuche"], ergebnis["anzeige_flaechensuche"]), (30, 20))
        self.assertEqual(ergebnis[db.NOTIZ_SPALTEN[self.F]], "bleibt stehen")

    # --- Lost Update -----------------------------------------------------------------

    def test_lost_update_bei_den_punkten_ueberschreibt_nichts(self):
        self._anmelden()
        richter_b = self._bogen(self.dk, self.T)
        db.eintragen_ergebnis(self.conn, self.dk, self.T, 50, 30)  # Richter A war schneller
        self._punkte(richter_b, self.dk, self.T, "10", "10")
        antwort = self._senden(richter_b, self.dk, self.T)
        html = antwort.data.decode()
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("inzwischen von jemand anderem geändert", html)
        ergebnis = db.get_ergebnis(self.conn, self.dk)
        self.assertEqual((ergebnis["suche_truemmerfeld"], ergebnis["anzeige_truemmerfeld"]), (50, 30))
        neu = _FormularLeser()
        neu.feed(html)
        self.assertEqual(neu.daten[f"suche_{self.T}_{self.dk}"], "50")  # aktueller Stand wird gezeigt

    def test_lost_update_bei_der_notiz(self):
        self._anmelden()
        richter_a = self._bogen(self.ed, self.F)
        richter_b = self._bogen(self.ed, self.F)
        richter_a[f"notiz_{self.ed}"] = "Notiz von A"
        self._senden(richter_a, self.ed, self.F)
        richter_b[f"notiz_{self.ed}"] = "Notiz von B"
        antwort = self._senden(richter_b, self.ed, self.F)
        html = antwort.data.decode()
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("Die Notiz wurde inzwischen von jemand anderem geändert", html)
        self.assertEqual(db.get_ergebnis(self.conn, self.ed)[db.NOTIZ_SPALTEN[self.F]], "Notiz von A")
        neu = _FormularLeser()
        neu.feed(html)
        self.assertEqual(neu.daten[f"notiz_{self.ed}"], "Notiz von A")

    def test_unveraenderte_notiz_ueberschreibt_fremde_aenderung_nicht(self):
        self._anmelden()
        richter_b = self._bogen(self.ed, self.F)
        db.setze_notiz(self.conn, self.ed, self.F, "Notiz von A")
        self._punkte(richter_b, self.ed, self.F, "40", "20")  # B ändert nur Punkte
        self.assertEqual(self._senden(richter_b, self.ed, self.F).status_code, 302)
        ergebnis = db.get_ergebnis(self.conn, self.ed)
        self.assertEqual(ergebnis[db.NOTIZ_SPALTEN[self.F]], "Notiz von A")
        self.assertEqual(ergebnis["suche_flaechensuche"], 40)

    def test_punkte_nach_fremder_disqualifikation_werden_nicht_geschrieben(self):
        self._anmelden()
        richter_b = self._bogen(self.ed, self.F)
        db.setze_ergebnis_status(self.conn, self.ed, True, False)
        self._punkte(richter_b, self.ed, self.F, "40", "20")
        antwort = self._senden(richter_b, self.ed, self.F)
        self.assertIn("inzwischen von jemand anderem geändert", antwort.data.decode())
        self.assertIsNone(db.get_ergebnis(self.conn, self.ed)["suche_flaechensuche"])

    # --- Disqualifiziert / Abbruch ---------------------------------------------------

    def test_disqualifiziert_sperrt_die_punkte(self):
        db.eintragen_ergebnis(self.conn, self.ed, self.F, 40, 20)
        self._anmelden()
        daten = self._bogen(self.ed, self.F)
        daten[f"dq_{self.ed}"] = "1"
        self._punkte(daten, self.ed, self.F, "5", "")  # würde sonst abgelehnt, ist aber gesperrt
        self.assertEqual(self._senden(daten, self.ed, self.F).status_code, 302)
        ergebnis = db.get_ergebnis(self.conn, self.ed)
        self.assertEqual((ergebnis["disqualifiziert"], ergebnis["suche_flaechensuche"]), (1, 40))
        html = self.client.get(self._pfad(self.ed, self.F)).data.decode()
        self.assertRegex(html, rf'name="suche_{self.F}_{self.ed}"[^>]*readonly')
        self.assertIn("disqualifiziert", html)
        self.assertNotIn("Wertnote", html)

    def test_abbruch_mit_grund_laesst_teilbewertung_zu_ohne_grund_wird_abgelehnt(self):
        self._anmelden()
        daten = self._bogen(self.dk, self.T)
        daten[f"abbruch_{self.dk}"] = "ohne_grund"
        antwort = self._senden(daten, self.dk, self.T)
        self.assertIn("Abbruch braucht einen Grund", antwort.data.decode())
        self.assertEqual(db.get_ergebnis(self.conn, self.dk)["abbruch"], 0)
        daten[f"abbruch_{self.dk}"] = "verletzung_hund"
        self._punkte(daten, self.dk, self.T, "30", "20")
        self.assertEqual(self._senden(daten, self.dk, self.T).status_code, 302)
        ergebnis = db.get_ergebnis(self.conn, self.dk)
        self.assertEqual((ergebnis["abbruch"], ergebnis["abbruch_grund"], ergebnis["suche_truemmerfeld"]),
                         (1, "verletzung_hund", 30))
        self.assertIn("Abbruch: Verletzung", self.client.get(self._pfad(self.dk, self.T)).data.decode())
        daten = self._bogen(self.dk, self.T)
        daten[f"abbruch_{self.dk}"] = "Quatsch"
        self.assertIn("Unbekannter Abbruchgrund", self._senden(daten, self.dk, self.T).data.decode())

    # --- Notiz -----------------------------------------------------------------------

    def test_notiz_wird_je_disziplin_gespeichert_getrimmt_und_geleert(self):
        self._anmelden()
        daten = self._bogen(self.dk, self.T)
        daten[f"notiz_{self.dk}"] = "  Zeile 1\r\nZeile 2  "
        self._senden(daten, self.dk, self.T)
        ergebnis = db.get_ergebnis(self.conn, self.dk)
        self.assertEqual(ergebnis[db.NOTIZ_SPALTEN[self.T]], "Zeile 1\nZeile 2")
        self.assertIsNone(ergebnis[db.NOTIZ_SPALTEN[self.F]])
        # der Bogen zeigt sie wieder, ein erneutes Speichern ohne Änderung schreibt nichts
        daten = self._bogen(self.dk, self.T)
        self.assertEqual(daten[f"notiz_{self.dk}"], "Zeile 1\nZeile 2")
        with patch.object(db, "setze_notiz") as notiz:
            daten[f"notiz_{self.dk}"] = "Zeile 1\r\nZeile 2"  # so schickt ein Browser sie zurück
            self._senden(daten, self.dk, self.T)
        notiz.assert_not_called()
        daten[f"notiz_{self.dk}"] = "   "
        self._senden(daten, self.dk, self.T)
        self.assertIsNone(db.get_ergebnis(self.conn, self.dk)[db.NOTIZ_SPALTEN[self.T]])

    def test_zu_lange_notiz_wird_abgelehnt_und_genau_die_grenze_geht(self):
        self._anmelden()
        daten = self._bogen(self.ed, self.F)
        self._punkte(daten, self.ed, self.F, "40", "20")
        daten[f"notiz_{self.ed}"] = "x" * (db.NOTIZ_MAX + 1)
        antwort = self._senden(daten, self.ed, self.F)
        html = antwort.data.decode()
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("Die Notiz ist zu lang", html)
        ergebnis = db.get_ergebnis(self.conn, self.ed)
        self.assertIsNone(ergebnis[db.NOTIZ_SPALTEN[self.F]])
        self.assertIsNone(ergebnis["suche_flaechensuche"])  # auch die Punkte wurden nicht gespeichert
        daten[f"notiz_{self.ed}"] = "x" * db.NOTIZ_MAX
        self.assertEqual(self._senden(daten, self.ed, self.F).status_code, 302)
        self.assertEqual(db.get_ergebnis(self.conn, self.ed)[db.NOTIZ_SPALTEN[self.F]], "x" * db.NOTIZ_MAX)

    def test_notiz_wird_html_maskiert(self):
        db.setze_notiz(self.conn, self.ed, self.F, '<b>"fett"</b> & mehr')
        self._anmelden()
        html = self.client.get(self._pfad(self.ed, self.F)).data.decode()
        self.assertNotIn("<b>", html)
        self.assertEqual(self._bogen(self.ed, self.F)[f"notiz_{self.ed}"], '<b>"fett"</b> & mehr')

    def test_notiz_mit_skript_und_textarea_ende_kann_den_bogen_nicht_aufbrechen(self):
        boese = '</textarea><script>alert(1)</script><img src=x onerror=alert(2)>'
        self._anmelden()
        daten = self._bogen(self.ed, self.F)
        daten[f"notiz_{self.ed}"] = boese
        self.assertEqual(self._senden(daten, self.ed, self.F).status_code, 302)
        self.assertEqual(db.get_ergebnis(self.conn, self.ed)[db.NOTIZ_SPALTEN[self.F]], boese)
        for pfad in (self._pfad(self.ed, self.F), "/ergebnisse"):
            html = self.client.get(pfad).data.decode()
            self.assertNotIn("<script>alert(1)", html, pfad)
            self.assertNotIn("<img src=x", html, pfad)
        html = self.client.get(self._pfad(self.ed, self.F)).data.decode()
        self.assertIn("&lt;/textarea&gt;&lt;script&gt;", html)
        # Der Bogen liefert den Text unverändert zurück (der Browser setzt ihn wieder ein).
        self.assertEqual(self._bogen(self.ed, self.F)[f"notiz_{self.ed}"], boese)

    def test_notiz_mit_unicode_und_umbruechen_bleibt_erhalten(self):
        text = "Größe ✓ – Straße, Zeile 2: 犬\nZeile 3"
        self._anmelden()
        daten = self._bogen(self.ed, self.F)
        daten[f"notiz_{self.ed}"] = text.replace("\n", "\r\n")  # so sendet ein Browser Zeilenumbrüche
        self._senden(daten, self.ed, self.F)
        self.assertEqual(db.get_ergebnis(self.conn, self.ed)[db.NOTIZ_SPALTEN[self.F]], text)
        self.assertEqual(self._bogen(self.ed, self.F)[f"notiz_{self.ed}"], text)

    def test_notiz_ohne_geladen_feld_wird_ohne_konfliktpruefung_geschrieben(self):
        # Bekannter Randfall (B19): fehlt `geladen_notiz_<id>` (veraltete Seite, gebauter POST), gibt es
        # keine Konfliktprüfung für die Notiz; das Verhalten ist so gewollt und hier festgehalten.
        db.setze_notiz(self.conn, self.ed, self.F, "von jemand anderem")
        self._anmelden()
        daten = self._bogen(self.ed, self.F)
        daten.pop(f"geladen_notiz_{self.ed}")
        daten[f"notiz_{self.ed}"] = "meine Notiz"
        self.assertEqual(self._senden(daten, self.ed, self.F).status_code, 302)
        self.assertEqual(db.get_ergebnis(self.conn, self.ed)[db.NOTIZ_SPALTEN[self.F]], "meine Notiz")

    # --- Rechte und Sicherheit -------------------------------------------------------

    def test_nicht_angemeldet_wird_zum_login_geleitet(self):
        antwort = self.client.get(self._pfad(self.ed, self.F))
        self.assertEqual(antwort.status_code, 302)
        self.assertTrue(antwort.headers["Location"].endswith("/"))
        antwort = self.client.post(self._pfad(self.ed, self.F), data={f"suche_{self.F}_{self.ed}": "40"})
        self.assertEqual(antwort.status_code, 302)
        self.assertIsNone(db.get_ergebnis(self.conn, self.ed)["suche_flaechensuche"])

    def test_post_ohne_csrf_token_wird_abgelehnt(self):
        self._anmelden()
        daten = self._bogen(self.ed, self.F)
        self._punkte(daten, self.ed, self.F, "45", "25")
        daten.pop("csrf_token")
        antwort = FlaskClient.post(self.client, self._pfad(self.ed, self.F), data=daten)
        self.assertEqual(antwort.status_code, 403)
        antwort = FlaskClient.post(self.client, self._pfad(self.ed, self.F), data={**daten, "csrf_token": "falsch"})
        self.assertEqual(antwort.status_code, 403)
        self.assertIsNone(db.get_ergebnis(self.conn, self.ed)["suche_flaechensuche"])

    def test_rolle_eintragen_darf_den_bogen_nutzen(self):
        self._anmelden()
        db.benutzer_anlegen(self.conn, "helfer", "helferpasswort")
        self.client.post("/logout")
        self.client.post("/", data={"benutzername": "helfer", "passwort": "helferpasswort"}, follow_redirects=True)
        with self.client.session_transaction() as sitzung:
            self.assertFalse(sitzung.get("ist_admin"))
        daten = self._bogen(self.ed, self.F)
        self._punkte(daten, self.ed, self.F, "45", "25")
        daten[f"notiz_{self.ed}"] = "von Helfer"
        self.assertEqual(self._senden(daten, self.ed, self.F).status_code, 302)
        ergebnis = db.get_ergebnis(self.conn, self.ed)
        self.assertEqual((ergebnis["suche_flaechensuche"], ergebnis[db.NOTIZ_SPALTEN[self.F]]), (45, "von Helfer"))

    def test_manipulierte_geladen_felder_fuehren_nicht_zum_absturz(self):
        self._anmelden()
        daten = self._bogen(self.dk, self.T)
        self._punkte(daten, self.dk, self.T, "11", "12")
        for kaputt in ("", "quatsch", "1,2|3,4|5,6|1|x"):
            daten[f"geladen_{self.dk}"] = kaputt
            self.assertEqual(self._senden(daten, self.dk, self.T).status_code, 302)
            self.assertEqual(db.get_ergebnis(self.conn, self.dk)["suche_truemmerfeld"], 11)

    # --- Knöpfe in der Ergebnistabelle -----------------------------------------------

    def test_tabelle_hat_je_aktiver_disziplin_einen_bogen_knopf(self):
        self._anmelden()
        html = self.client.get("/ergebnisse").data.decode()
        # Seit UX-Test Web 19.11.2026 (C3) ist „Bogen“ ein Absendeknopf: erst speichern, dann öffnen.
        self.assertEqual(html.count(">Bogen</button>"), 1 + 3 + 1)  # ED, DK, ED
        self.assertIn(f'name="bogen" value="{self.ed}:{self.F}"', html)
        self.assertNotIn(f'name="bogen" value="{self.ed}:{self.T}"', html)  # ED: nur die eigene Disziplin
        for d in db.ALLE_DISZIPLINEN:
            self.assertIn(f'name="bogen" value="{self.dk}:{d}"', html)
        self.assertIn(f'aria-label="Speichern und Bewertungsbogen {self.T} öffnen: Beispiel, Bello"', html)
        self.assertIn("„Bogen“ speichert zuerst alle Eingaben", html)
        # „Alle speichern“ ist der erste Absendeknopf (die Eingabetaste löst ihn aus, nicht „Bogen“).
        formular = html[html.index('id="ergebnisform"'):]
        self.assertLess(formular.index(">Alle speichern</button>"), formular.index('name="bogen"'))

    def test_tabelle_hat_zeilenanker_und_gibt_den_filter_an_die_knoepfe_weiter(self):
        self._anmelden()
        html = self.client.get("/ergebnisse").data.decode()
        for tid in (self.ed, self.dk, self.ed2):
            self.assertIn(f'id="zeile-{tid}"', html)
        html = self.client.get("/ergebnisse?q=rex").data.decode()
        self.assertEqual(html.count(">Bogen</button>"), 1)
        # Der Filter steht in der Adresse des Speicher-Formulars und geht an den Bogen weiter.
        daten = self._seite("/ergebnisse?q=rex")
        daten["bogen"] = f"{self.ed}:{self.F}"
        antwort = self.client.post("/ergebnisse?q=rex", data=daten)
        self.assertEqual(antwort.status_code, 302)
        self.assertEqual(antwort.headers["Location"], self._pfad(self.ed, self.F, "?q=rex"))

    def test_bogen_knopf_speichert_zuerst_die_tabelle(self):
        self._anmelden()
        daten = self._seite()
        daten[f"suche_{self.F}_{self.ed}"], daten[f"anzeige_{self.F}_{self.ed}"] = "44", "33"
        daten["bogen"] = f"{self.dk}:{self.T}"
        antwort = self.client.post("/ergebnisse", data=daten)
        self.assertEqual(antwort.status_code, 302)
        self.assertEqual(antwort.headers["Location"], self._pfad(self.dk, self.T))
        self.assertEqual(db.get_ergebnis(self.conn, self.ed)["suche_flaechensuche"], 44)

    def test_bogen_knopf_bei_fehler_bleibt_in_der_tabelle(self):
        self._anmelden()
        daten = self._seite()
        daten[f"suche_{self.F}_{self.ed}"] = "84"  # über dem Höchstwert, Anzeige fehlt
        daten["bogen"] = f"{self.ed}:{self.F}"
        antwort = self.client.post("/ergebnisse", data=daten)
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("Es wurde nichts gespeichert", antwort.data.decode())

    def test_bogen_knopf_bei_konflikt_bleibt_in_der_tabelle_mit_hinweis(self):
        self._anmelden()
        daten = self._seite()
        db.eintragen_ergebnis(self.conn, self.ed, self.F, 50, 30)  # anderer Richter, nach dem Laden
        daten[f"suche_{self.F}_{self.ed}"], daten[f"anzeige_{self.F}_{self.ed}"] = "44", "33"
        daten["bogen"] = f"{self.ed}:{self.F}"
        antwort = self.client.post("/ergebnisse", data=daten)
        self.assertEqual(antwort.status_code, 200)
        html = antwort.data.decode()
        self.assertIn("Bei 1 Teilnehmer wurde inzwischen", html)
        self.assertIn("Der Bewertungsbogen wurde deshalb nicht geöffnet", html)
        self.assertEqual(db.get_ergebnis(self.conn, self.ed)["suche_flaechensuche"], 50)

    def test_bogen_knopf_mit_fremdem_wert_fuehrt_zur_tabelle(self):
        self._anmelden()
        for wert in (f"{self.ed}:{self.T}", "999999:Trümmerfeld", "abc", "//evil.example:x", f"{self.ed}"):
            daten = self._seite()
            daten["bogen"] = wert
            antwort = self.client.post("/ergebnisse", data=daten)
            self.assertEqual(antwort.status_code, 302, wert)
            self.assertTrue(antwort.headers["Location"].startswith("/ergebnisse?gespeichert="), wert)

    def test_tabelle_mit_den_knoepfen_bleibt_ohne_javascript(self):
        self._anmelden()
        self.assertNotIn("<script", self.client.get("/ergebnisse").data.decode())

    def test_nicht_teilnehmende_haben_keinen_knopf(self):
        keine = self._teilnehmer("Fehlt", "Dora", "Nix", "ED", 1, 4, "Trümmerfeld")
        db.setze_keine_teilnahme(self.conn, keine, True)
        self._anmelden()
        self.assertNotIn(f"/bewertungsbogen/{keine}/", self.client.get("/ergebnisse").data.decode())


try:
    import reportlab  # noqa: F401 - nur zur Prüfung, ob die PDF-Tests laufen können
except ImportError:  # pragma: no cover
    reportlab = None
try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None


class TestBoegenPdf(_AppWebTestBasis):
    """Sammel-PDF der benutzten Bewertungsbögen /ergebnisse/boegen.pdf (Marco 18.11.2026): Rechte,
    Filter, was als „benutzt“ zählt, Download-Antwort, Fehlerfälle und der Knopf in der Tabelle."""

    T, F, B = db.ALLE_DISZIPLINEN
    URL = "/ergebnisse/boegen.pdf"

    def setUp(self):
        super().setUp()
        db.set_veranstaltung(self.conn, verein="Hundefreunde Köln/Süd", datum="2026-11-18", ort="Köln")
        self.ed = self._teilnehmer("Muster", "Anna", "Rex", "ED", 1, 1, "Flächensuche")
        self.dk = self._teilnehmer("Beispiel", "Bernd", "Bello", "DK", 2, 2)
        self.ed2 = self._teilnehmer("Probe", "Cora", "Luna", "ED", 3, 3, "Trümmerfeld")
        self.leer = self._teilnehmer("Unbenutzt", "Dora", "Nix", "ED", 1, 4, "Trümmerfeld")

    def _teilnehmer(self, nachname, vorname, hund, art, stufe, nr, disziplin=None):
        return db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname=nachname, vorname=vorname, rufname_hund=hund, art=art, stufe=stufe,
            disziplin=disziplin, startnummer=nr,
        ))

    def _seiten(self, antwort) -> list[str]:
        return [s.extract_text() for s in PdfReader(io.BytesIO(antwort.data)).pages]

    # --- Rechte -----------------------------------------------------------------------

    def test_ohne_anmeldung_geht_es_zum_login(self):
        antwort = self.client.get(self.URL)
        self.assertEqual(antwort.status_code, 302)
        self.assertNotIn("pdf", antwort.headers.get("Content-Type", ""))

    def test_ohne_gewaehlten_termin_geht_es_zur_terminauswahl(self):
        self.termine = [_termin_info(_TEST_SCHEMA), _termin_info("termin_zwei", id=2)]
        self._anmelden()
        antwort = self.client.get(self.URL)
        self.assertEqual(antwort.status_code, 302)
        self.assertIn("/termin-waehlen", antwort.headers["Location"])

    def test_beide_rollen_duerfen_die_pdf_holen(self):
        db.eintragen_ergebnis(self.conn, self.ed, self.F, 40, 30)
        self._anmelden()
        db.benutzer_anlegen(self.conn, "helfer", "helferpasswort")
        self.client.post("/logout")
        self.client.post("/", data={"benutzername": "helfer", "passwort": "helferpasswort"}, follow_redirects=True)
        with self.client.session_transaction() as sitzung:
            self.assertFalse(sitzung.get("ist_admin"))
        antwort = self.client.get(self.URL)
        self.assertNotEqual(antwort.status_code, 403)
        self.assertNotEqual(antwort.status_code, 500)

    def test_nur_get_ist_erlaubt(self):
        self._anmelden()
        self.assertEqual(self.client.post(self.URL).status_code, 405)

    # --- Keine passenden Teilnehmer / Fehler (ohne reportlab pruefbar) ----------------------

    def test_ohne_eintragungen_geht_es_mit_hinweis_zur_tabelle(self):
        self._anmelden()
        antwort = self.client.get(self.URL)
        self.assertEqual(antwort.status_code, 302)
        self.assertIn("/ergebnisse?boegen=keine", antwort.headers["Location"])
        html = self.client.get(antwort.headers["Location"]).data.decode()
        self.assertIn("Keine benutzten Bewertungsbögen", html)
        # nur ein neutraler Hinweis, kein roter Fehler
        self.assertIn('<div class="karte" role="status">Keine benutzten Bewertungsbögen', html)
        self.assertNotIn('<div class="fehler" role="alert">Keine benutzten', html)

    def test_filter_ohne_benutzte_boegen_gibt_hinweis_und_behaelt_den_filter(self):
        db.eintragen_ergebnis(self.conn, self.ed, self.F, 40, 30)
        self._anmelden()
        antwort = self.client.get(self.URL + "?q=Probe")
        self.assertEqual(antwort.status_code, 302)
        ort = antwort.headers["Location"]
        self.assertIn("boegen=keine", ort)
        self.assertIn("q=Probe", ort)

    def test_nur_leerraum_notiz_und_nicht_teilnehmende_zaehlen_nicht(self):
        self.conn.execute("UPDATE ergebnisse SET notiz_flaechensuche = ? WHERE teilnehmer_id = ?", ("  \n ", self.ed))
        keine = self._teilnehmer("Fehlt", "Eva", "Weg", "ED", 1, 5, "Trümmerfeld")
        db.eintragen_ergebnis(self.conn, keine, self.T, 40, 30)
        db.setze_keine_teilnahme(self.conn, keine, True)
        self.conn.commit()
        self._anmelden()
        self.assertIn("boegen=keine", self.client.get(self.URL).headers["Location"])

    def test_fehler_beim_erzeugen_ergibt_hinweis_statt_500(self):
        db.eintragen_ergebnis(self.conn, self.ed, self.F, 40, 30)
        self._anmelden()
        import pdf_export  # in diesem Zweig nötig: der Test patcht die Funktion
        with patch.object(pdf_export, "erstelle_alle_bewertungsboegen_pdf",
                          side_effect=RuntimeError("geheim: /app/intern.py Zeile 5")), \
                self.assertLogs(app_web.app.logger, level="ERROR"):  # der Fehler wird nur protokolliert
            antwort = self.client.get(self.URL)
            self.assertEqual(antwort.status_code, 302)
            self.assertIn("boegen=fehler", antwort.headers["Location"])
            html = self.client.get(antwort.headers["Location"]).data.decode()
        self.assertIn("Die PDF konnte nicht erstellt werden", html)
        self.assertNotIn("geheim", html)
        self.assertNotIn("intern.py", html)

    def test_ohne_pdf_modul_startet_die_app_und_meldet_den_fehler(self):
        """pdf_export wird erst beim Aufruf importiert; fehlt reportlab, gibt es den Hinweis."""
        import sys
        db.eintragen_ergebnis(self.conn, self.ed, self.F, 40, 30)
        self._anmelden()
        with patch.dict(sys.modules, {"pdf_export": None}), \
                self.assertLogs(app_web.app.logger, level="ERROR"):  # import pdf_export -> ImportError
            antwort = self.client.get(self.URL)
        self.assertEqual(antwort.status_code, 302)
        self.assertIn("boegen=fehler", antwort.headers["Location"])

    def test_hinweiscodes_in_der_adresse_zeigen_nur_feste_texte(self):
        self._anmelden()
        html = self.client.get("/ergebnisse?boegen=%3Cscript%3Ealert(1)%3C/script%3E").data.decode()
        self.assertNotIn("alert(1)", html)
        self.assertNotIn("Keine benutzten Bewertungsbögen", html)

    def test_app_importiert_pdf_export_nicht_beim_start(self):
        import subprocess
        import sys
        ergebnis = subprocess.run(
            [sys.executable, "-I", "-c", "import sys; sys.path.insert(0, '.'); import app_web; "
             "raise SystemExit(1 if 'pdf_export' in sys.modules or 'reportlab' in sys.modules else 0)"],
            cwd=os.path.dirname(os.path.abspath(__file__)) or ".", capture_output=True, timeout=120)
        self.assertEqual(ergebnis.returncode, 0, ergebnis.stderr.decode(errors="replace"))

    # --- Die PDF ----------------------------------------------------------------------------

    def test_antwort_ist_ein_pdf_als_anhang_mit_sicherem_dateinamen(self):
        if reportlab is None:
            self.skipTest("reportlab nicht installiert")
        db.eintragen_ergebnis(self.conn, self.ed, self.F, 40, 30)
        self._anmelden()
        antwort = self.client.get(self.URL)
        self.assertEqual(antwort.status_code, 200)
        self.assertTrue(antwort.data.startswith(b"%PDF"))
        self.assertEqual(antwort.mimetype, "application/pdf")
        disposition = antwort.headers["Content-Disposition"]
        self.assertTrue(disposition.startswith("attachment"))
        # secure_filename: ASCII, ohne Leerzeichen, Umlaute und "/" des Vereinsnamens
        self.assertIn("filename=Bewertungsboegen_Hundefreunde_Koln_Sud_2026-11-18.pdf", disposition)
        self.assertTrue(disposition.isascii())
        self.assertEqual(antwort.headers["Cache-Control"], "no-store")
        self.assertEqual(antwort.headers["X-Content-Type-Options"], "nosniff")

    def test_dateiname_ohne_vereinsangaben_bleibt_gueltig(self):
        if reportlab is None:
            self.skipTest("reportlab nicht installiert")
        db.set_veranstaltung(self.conn, verein="äöü /", datum="2026-11-18")
        db.eintragen_ergebnis(self.conn, self.ed, self.F, 40, 30)
        self._anmelden()
        disposition = self.client.get(self.URL).headers["Content-Disposition"]
        self.assertRegex(disposition, r'filename="?Bewertungsboegen[A-Za-z0-9_.-]*\.pdf"?')

    @unittest.skipIf(PdfReader is None, "pypdf nicht installiert")
    def test_nur_benutzte_boegen_dk_nur_benutzte_disziplin_ed_eine_in_startnummernfolge(self):
        if reportlab is None:
            self.skipTest("reportlab nicht installiert")
        db.eintragen_ergebnis(self.conn, self.ed, self.F, 40, 30)
        db.eintragen_ergebnis(self.conn, self.dk, self.T, 55, 35)
        db.setze_ergebnis_status(self.conn, self.ed2, True, False)  # nur disqualifiziert
        # self.leer bleibt ohne Eintragung
        self._anmelden()
        antwort = self.client.get(self.URL)
        seiten = self._seiten(antwort)
        # ED 1 + DK nur das Trümmerfeld-Blatt (UX-Test Web 19.11.2026, G1: keine leeren Seiten) + ED 1
        self.assertEqual(len(seiten), 3)
        self.assertIn(f"Bewertung {self.T}", seiten[1])
        text = "\n".join(seiten)
        for name in ("Muster, Anna", "Beispiel, Bernd", "Probe, Cora"):
            self.assertIn(name, text)
        self.assertNotIn("Unbenutzt", text)
        self.assertLess(text.index("Muster, Anna"), text.index("Beispiel, Bernd"))
        self.assertLess(text.index("Beispiel, Bernd"), text.index("Probe, Cora"))
        self.assertIn("Punktzahl: 40", seiten[0])
        self.assertIn("Punktzahl: 30", seiten[0])
        self.assertIn("disqualifiziert", text.lower())

    @unittest.skipIf(PdfReader is None, "pypdf nicht installiert")
    def test_filter_wirkt_auf_die_pdf(self):
        if reportlab is None:
            self.skipTest("reportlab nicht installiert")
        db.eintragen_ergebnis(self.conn, self.ed, self.F, 40, 30)
        db.eintragen_ergebnis(self.conn, self.ed2, self.T, 50, 20)
        self._anmelden()
        text = "\n".join(self._seiten(self.client.get(self.URL + "?nr=3")))
        self.assertIn("Probe, Cora", text)
        self.assertNotIn("Muster, Anna", text)
        text = "\n".join(self._seiten(self.client.get(self.URL + "?q=rex")))
        self.assertIn("Muster, Anna", text)
        self.assertNotIn("Probe, Cora", text)
        # unbekannte Art/LK wie in der Tabelle: wie „Alle“
        text = "\n".join(self._seiten(self.client.get(self.URL + "?lk=gibt-es-nicht")))
        self.assertIn("Muster, Anna", text)
        self.assertIn("Probe, Cora", text)

    @unittest.skipIf(PdfReader is None, "pypdf nicht installiert")
    def test_notiz_allein_macht_einen_bogen_benutzt_und_erscheint_im_pdf(self):
        if reportlab is None:
            self.skipTest("reportlab nicht installiert")
        db.setze_notiz(self.conn, self.ed2, self.T, "Gegenstand hinter dem Reifen")
        self._anmelden()
        seiten = self._seiten(self.client.get(self.URL))
        self.assertEqual(len(seiten), 1)
        self.assertIn("Probe, Cora", seiten[0])
        self.assertIn("Notiz:", seiten[0])
        self.assertIn("Gegenstand hinter dem Reifen", seiten[0])

    @unittest.skipIf(PdfReader is None, "pypdf nicht installiert")
    def test_notiz_mit_markup_und_sehr_lange_notiz_brechen_die_pdf_nicht(self):
        if reportlab is None:
            self.skipTest("reportlab nicht installiert")
        db.setze_notiz(self.conn, self.ed, self.F, "<b>fett</b> & <i>x</unknown> &amp; <para>")
        lang = "".join(f"Zeile {n}\n" for n in range(1, 80))[:db.NOTIZ_MAX]
        db.setze_notiz(self.conn, self.dk, self.T, lang)
        db.setze_notiz(self.conn, self.dk, self.F, "x" * db.NOTIZ_MAX)  # ein Wort ohne Leerzeichen
        db.setze_notiz(self.conn, self.dk, self.B, "Ende")
        self._anmelden()
        antwort = self.client.get(self.URL)
        self.assertEqual(antwort.status_code, 200)
        seiten = self._seiten(antwort)
        self.assertEqual(len(seiten), 3)  # ED 1 + DK (alle Disziplinen benutzt: ganzer Bogen) genau 2: auch mit langen Notizen
        for stueck in ("<b>fett</b> & <i>x</unknown>", "&amp;", "<para>"):  # wörtlich, nicht als Markup gedeutet
            self.assertIn(stueck, seiten[0])
        text = "\n".join(seiten)
        self.assertIn("…", text)
        self.assertNotIn("Zeile 79", text)  # sehr lange Notiz ist gekürzt

    @unittest.skipIf(PdfReader is None, "pypdf nicht installiert")
    def test_dreikampf_hat_auch_mit_abbruch_und_notizen_genau_zwei_seiten(self):
        if reportlab is None:
            self.skipTest("reportlab nicht installiert")
        for d in db.ALLE_DISZIPLINEN:
            db.eintragen_ergebnis(self.conn, self.dk, d, 40, 30)
            db.setze_notiz(self.conn, self.dk, d, "Hund zeigte spät an, Wind von links. " * 12)
        db.setze_ergebnis_status(self.conn, self.dk, False, True, abbruch_grund="krankheit")
        self._anmelden()
        seiten = self._seiten(self.client.get(self.URL + "?nr=2"))
        self.assertEqual(len(seiten), 2)  # mit Status ganzer Bogen; lange Notizen sprengen nichts
        self.assertIn("Krankheit", "\n".join(seiten))  # Status bleibt sichtbar (Verifikation U10)

    @unittest.skipIf(PdfReader is None, "pypdf nicht installiert")
    def test_dreikampf_teilweise_ohne_status_mit_punkten_im_statusfall_ganzer_bogen(self):
        if reportlab is None:
            self.skipTest("reportlab nicht installiert")
        db.eintragen_ergebnis(self.conn, self.dk, self.F, 40, 30)
        db.setze_ergebnis_status(self.conn, self.dk, False, True, abbruch_grund="krankheit")
        self._anmelden()
        seiten = self._seiten(self.client.get(self.URL + "?nr=2"))
        self.assertEqual(len(seiten), 2)
        self.assertIn("Krankheit", "\n".join(seiten))

    @unittest.skipIf(PdfReader is None, "pypdf nicht installiert")
    def test_dreikampf_nur_disqualifiziert_bekommt_den_ganzen_bogen(self):
        if reportlab is None:
            self.skipTest("reportlab nicht installiert")
        db.setze_ergebnis_status(self.conn, self.dk, True, False)
        self._anmelden()
        self.assertEqual(len(self._seiten(self.client.get(self.URL + "?nr=2"))), 2)

    def test_pdf_hinweis_nennt_was_nach_dem_klick_passiert(self):
        # UX-Test Web 19.11.2026 (B5): ohne Skript keine Fortschrittsanzeige, deshalb vorher erklärt
        self._anmelden()
        html = self.client.get("/ergebnisse").data.decode()
        self.assertIn("das kann bei vielen Teilnehmern einige Sekunden dauern", html)
        self.assertIn("beim Dreikampf nur die Blätter der Disziplinen mit Eintragung", html)

    # --- Knopf in der Tabelle -----------------------------------------------------------------

    def test_tabelle_hat_den_knopf_mit_filter_und_ohne_javascript(self):
        self._anmelden()
        html = self.client.get("/ergebnisse").data.decode()
        self.assertIn("Benutzte Bögen als PDF", html)
        self.assertIn('href="/ergebnisse/boegen.pdf"', html)
        self.assertIn("Nicht gespeicherte Eingaben der Tabelle sind nicht enthalten", html)
        self.assertNotIn("<script", html)
        html = self.client.get("/ergebnisse?q=rex&nr=1").data.decode()
        self.assertIn('href="/ergebnisse/boegen.pdf?nr=1&amp;q=rex"', html)
        self.assertIn("für die gefilterten Teilnehmer", html)


class TestLizenzseite(_AppWebTestBasis):
    """Öffentliche Seite /lizenzen mit der MIT-Lizenz und den Lizenzen der Fremdkomponenten,
    verlinkt in der Fußzeile jeder Seite (Marco 01.11.2026)."""

    def _datei(self, inhalt: str) -> str:
        fd, pfad = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as datei:
            datei.write(inhalt)
        self.addCleanup(os.remove, pfad)
        return pfad

    def test_lizenzseite_ohne_anmeldung_erreichbar(self):
        antwort = self.client.get("/lizenzen")
        self.assertEqual(antwort.status_code, 200)
        self.assertIn(b"MIT License", antwort.data)
        self.assertIn(b"Copyright (c) 2026 Marco", antwort.data)
        # Dieselben Schutz-Header wie jede andere Seite (S-6).
        self.assertIn("script-src 'none'", antwort.headers["Content-Security-Policy"])

    def test_lizenzseite_auch_angemeldet_erreichbar(self):
        self._anmelden()
        antwort = self.client.get("/lizenzen")
        self.assertEqual(antwort.status_code, 200)
        self.assertIn(b"MIT License", antwort.data)

    def test_fusszeile_verlinkt_lizenzseite(self):
        # Ersteinrichtung (noch kein Administrator) ...
        self.assertIn(b'href="/lizenzen"', self.client.get("/").data)
        # ... und die normale Anmeldeseite nach dem Abmelden.
        self._anmelden()
        self.client.post("/logout")
        antwort = self.client.get("/")
        self.assertIn("Anmelden".encode(), antwort.data)
        self.assertIn(b'href="/lizenzen"', antwort.data)

    def test_fehlende_drittlizenzen_zeigen_hinweis_statt_fehler(self):
        fehlt = os.path.join(tempfile.gettempdir(), "gibt-es-nicht-" + secrets.token_hex(8) + ".txt")
        with patch.object(app_web, "DRITTLIZENZEN_DATEI", fehlt):
            antwort = self.client.get("/lizenzen")
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("wird beim Bauen des Container-Images erzeugt".encode(), antwort.data)
        # Die MIT-Lizenz bleibt trotzdem sichtbar.
        self.assertIn(b"MIT License", antwort.data)

    def test_fehlende_lizenzdatei_zeigt_hinweis_statt_fehler(self):
        fehlt = os.path.join(tempfile.gettempdir(), "gibt-es-nicht-" + secrets.token_hex(8))
        with patch.object(app_web, "LIZENZ_DATEI", fehlt):
            antwort = self.client.get("/lizenzen")
        self.assertEqual(antwort.status_code, 200)
        self.assertIn(b"Die Lizenzdatei (LICENSE) fehlt", antwort.data)

    def test_lizenztexte_werden_maskiert(self):
        pfad = self._datei("Paket <script>x</script> & Co")
        with patch.object(app_web, "DRITTLIZENZEN_DATEI", pfad):
            antwort = self.client.get("/lizenzen")
        self.assertEqual(antwort.status_code, 200)
        self.assertNotIn(b"<script>x</script>", antwort.data)
        self.assertIn(b"&lt;script&gt;x&lt;/script&gt; &amp; Co", antwort.data)


class TestErscheinungsbild(_AppWebTestBasis):
    """Kopf mit Beagle und Termin-Angaben, Bild über /static (Marco 01.11.2026,
    Erscheinungsbild „Beagle“)."""

    def test_beagle_bild_ohne_anmeldung_erreichbar(self):
        antwort = self.client.get("/static/beagle.png")
        self.assertEqual(antwort.status_code, 200)
        self.assertEqual(antwort.mimetype, "image/png")
        self.assertTrue(antwort.data.startswith(b"\x89PNG"))
        antwort.close()

    def test_anmeldeseite_zeigt_beagle_und_programmnamen(self):
        self._anmelden()
        self.client.post("/logout")
        seite = self.client.get("/").data.decode()
        self.assertIn("Anmelden", seite)
        kopf = seite.split("</header>")[0]
        self.assertIn('<img src="/static/beagle.png"', kopf)
        self.assertIn("SHS-Prüfungsprogramm", kopf)
        self.assertIn("Ergebniserfassung", kopf)

    def test_kopf_zeigt_verein_datum_und_ort_des_termins(self):
        db.set_veranstaltung(self.conn, verein="Hundefreunde Musterstadt", datum="2026-11-14", ort="Musterstadt")
        self._anmelden()
        kopf = self.client.get("/teilnehmer").data.decode().split("</header>")[0]
        self.assertIn("Hundefreunde Musterstadt", kopf)
        self.assertIn("14.11.2026 · Musterstadt", kopf)
        self.assertNotIn("Ergebniserfassung", kopf)

    def test_ergebnisseite_zeigt_termin_im_kopf_und_navigation_ohne_trennpunkte(self):
        """Am Tablet arbeiten die Richter auf der Ergebnisseite - auch dort steht der Termin
        im Kopf. Die Navigation trennt per CSS statt mit „·“ (blieb beim Umbruch allein am
        Zeilenende stehen)."""
        db.set_veranstaltung(self.conn, verein="Hundefreunde Musterstadt", datum="2026-11-14", ort="Musterstadt")
        tid = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Test", vorname="A", rufname_hund="Rex", art="DK", stufe=1, startnummer=1))
        self._anmelden()
        kopf = self.client.get(f"/teilnehmer/{tid}").data.decode().split("</header>")[0]
        self.assertIn("Hundefreunde Musterstadt", kopf)
        self.assertIn("14.11.2026 · Musterstadt", kopf)
        nav = kopf.split("<nav>")[1]
        self.assertNotIn("·", nav)
        self.assertIn("Termin wechseln", nav)

    def test_kopf_ohne_ort_zeigt_nur_datum(self):
        db.set_veranstaltung(self.conn, verein="Testverein", datum="2026-09-19")
        self._anmelden()
        kopf = self.client.get("/teilnehmer").data.decode().split("</header>")[0]
        self.assertRegex(kopf, r'<span class="unterzeile">19\.09\.2026</span>')

    def test_status_bewertet_mit_haken_symbol(self):
        db.set_veranstaltung(self.conn, verein="Testverein", datum="2026-09-19")
        fertig_id = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Fertig", vorname="B", rufname_hund="Bello", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=2,
        ))
        db.eintragen_ergebnis(self.conn, fertig_id, "Trümmerfeld", 50, 30)
        self._anmelden()
        seite = self.client.get("/teilnehmer").data.decode()
        self.assertRegex(seite, r'<span class="status status-fertig"><svg [^>]*aria-hidden="true"[^>]*>.*?</svg>bewertet</span>')

    def test_csp_erlaubt_eigene_bilder(self):
        for pfad in ("/", "/static/beagle.png"):
            with self.subTest(pfad=pfad):
                antwort = self.client.get(pfad)
                csp = antwort.headers["Content-Security-Policy"]
                self.assertIn("img-src 'self'", csp)
                self.assertIn("script-src 'none'", csp)
                antwort.close()


class TestCsrfSchutz(_AppWebTestBasis):
    """Prüft den CSRF-Mechanismus selbst (QS-Review 19./20.09., siehe
    app_web._csrf_pruefen/_csrf_token) - bewusst mit dem UNVERÄNDERTEN Flask-Test-Client
    (FlaskClient statt des _CsrfTestClient von oben, der diesen Schutz für TestAppWeb
    automatisch umgeht), damit hier tatsächlich geprüft wird, was ein echter Browser
    ohne (oder mit einem falschen) Token erlebt. Erbt von _AppWebTestBasis (nicht von
    TestAppWeb!) nur wegen des gemeinsamen setUp/tearDown (Testdatenbank, gemockte
    PostgreSQL-Klebefunktionen) - führt dadurch keinen der fachlichen Tests aus
    TestAppWeb ein zweites Mal aus."""

    def setUp(self):
        super().setUp()
        app_web.app.test_client_class = FlaskClient
        self.client = app_web.app.test_client()

    def test_post_ohne_csrf_token_wird_mit_403_abgelehnt(self):
        antwort = self.client.post(
            "/",
            data={
                "benutzername": _ADMIN_NAME, "passwort": _ADMIN_PASSWORT,
                "passwort_wiederholung": _ADMIN_PASSWORT,
            },
        )
        self.assertEqual(antwort.status_code, 403)
        self.assertFalse(db.gibt_es_admin(self.conn))

    def test_post_mit_falschem_csrf_token_wird_mit_403_abgelehnt(self):
        self.client.get("/")  # legt ein echtes Token in der Session an
        antwort = self.client.post(
            "/",
            data={
                "benutzername": _ADMIN_NAME, "passwort": _ADMIN_PASSWORT,
                "passwort_wiederholung": _ADMIN_PASSWORT, "csrf_token": "ein-falsches-token",
            },
        )
        self.assertEqual(antwort.status_code, 403)
        self.assertFalse(db.gibt_es_admin(self.conn))

    def test_csrf_token_mit_sonderzeichen_ergibt_403_statt_500(self):
        # Codeprüfung 22.09.: compare_digest auf str mit Nicht-ASCII warf TypeError (500).
        self.client.get("/")
        antwort = self.client.post("/", data={"benutzername": "x", "csrf_token": "Tökén"})
        self.assertEqual(antwort.status_code, 403)

    def test_post_mit_dem_echten_token_aus_der_seite_funktioniert(self):
        """Entspricht dem normalen Ablauf eines echten Browsers: erst die Seite mit dem
        Formular laden (das versteckte csrf_token-Feld kommt von dort), dann genau
        dieses Token beim Abschicken mitschicken."""
        import re
        seite = self.client.get("/")
        treffer = re.search(r'name="csrf_token" value="([^"]+)"', seite.data.decode())
        self.assertIsNotNone(treffer)
        antwort = self.client.post(
            "/",
            data={
                "benutzername": _ADMIN_NAME, "passwort": _ADMIN_PASSWORT,
                "passwort_wiederholung": _ADMIN_PASSWORT, "csrf_token": treffer.group(1),
                "einrichtungs_code": _EINRICHTUNGS_CODE,
            },
            follow_redirects=True,
        )
        self.assertEqual(antwort.status_code, 200)
        self.assertTrue(db.gibt_es_admin(self.conn))

    def test_get_anfragen_brauchen_kein_csrf_token(self):
        # GET verändert nichts - hier wäre eine CSRF-Prüfung wirkungslos gegen den
        # eigentlichen Angriff (unerwünschte SCHREIBENDE Aktionen) und würde nur ganz
        # normales Navigieren/Verlinken behindern.
        self.assertEqual(self.client.get("/").status_code, 200)


class TestApiDesktop(_AppWebTestBasis):
    """API für den Desktop (/api/, siehe app_web, Abschnitt "API für den Desktop"):
    Token-Anmeldung, Ratenbegrenzung, Termine veröffentlichen/auflisten, Ergebnisse holen.
    Läuft mit dem UNVERÄNDERTEN Flask-Test-Client (kein automatisches CSRF-Token) - die
    API darf gerade keines brauchen."""

    _API_ADMIN = "apiadmin"
    _API_PASSWORT = "api_passwort_123"

    def setUp(self):
        super().setUp()
        app_web.app.test_client_class = FlaskClient
        self.client = app_web.app.test_client()
        app_web._login_fehlversuche.clear()
        db.admin_einrichten(self.conn, self._API_ADMIN, self._API_PASSWORT)
        db.benutzer_anlegen(self.conn, "helfer", "helferpasswort")

    def tearDown(self):
        app_web._login_fehlversuche.clear()
        super().tearDown()

    def _login(self, benutzername=None, passwort=None, client=None):
        return (client or self.client).post(
            "/api/login",
            json={
                "benutzername": benutzername or self._API_ADMIN,
                "passwort": passwort or self._API_PASSWORT,
            },
        )

    def _kopf(self, token=None):
        if token is None:
            token = self._login().get_json()["token"]
        return {"Authorization": f"Bearer {token}"}

    # --- Anmeldung --------------------------------------------------------------

    def test_login_liefert_token_und_gueltigkeit(self):
        antwort = self._login()
        self.assertEqual(antwort.status_code, 200)
        daten = antwort.get_json()
        self.assertIsInstance(daten["token"], str)
        self.assertEqual(daten["gueltig_sekunden"], 8 * 60 * 60)
        self.assertEqual(antwort.headers["Cache-Control"], "no-store")
        # Das Token öffnet die geschützten Routen.
        self.assertEqual(self.client.get("/api/termine", headers=self._kopf(daten["token"])).status_code, 200)

    def test_login_ohne_csrf_token_und_ohne_cookie_moeglich(self):
        antwort = self._login()
        self.assertEqual(antwort.status_code, 200)
        self.assertNotIn("Set-Cookie", antwort.headers)

    def test_login_mit_falschem_passwort_ergibt_401(self):
        antwort = self._login(passwort="falsch")
        self.assertEqual(antwort.status_code, 401)
        self.assertIn("fehler", antwort.get_json())

    def test_login_mit_unbekanntem_konto_ergibt_401(self):
        self.assertEqual(self._login(benutzername="gibtsnicht").status_code, 401)

    def test_login_eines_nicht_admins_ergibt_403(self):
        antwort = self._login(benutzername="helfer", passwort="helferpasswort")
        self.assertEqual(antwort.status_code, 403)
        self.assertIn("fehler", antwort.get_json())

    def test_login_ohne_json_ergibt_400(self):
        self.assertEqual(self.client.post("/api/login", data={"benutzername": "x"}).status_code, 400)
        self.assertEqual(self.client.post("/api/login", json=["x"]).status_code, 400)
        self.assertEqual(self.client.post("/api/login", json={"benutzername": "x"}).status_code, 400)
        self.assertEqual(self.client.post("/api/login", json={"benutzername": 1, "passwort": 2}).status_code, 400)

    def test_ratenbegrenzung_sperrt_die_client_ip(self):
        for _ in range(app_web._LOGIN_MAX_FEHLVERSUCHE):
            self.assertEqual(self._login(passwort="falsch").status_code, 401)
        gesperrt = self._login(passwort="falsch")
        self.assertEqual(gesperrt.status_code, 429)
        self.assertGreater(int(gesperrt.headers["Retry-After"]), 0)
        self.assertIn("fehler", gesperrt.get_json())
        # Auch das richtige Passwort kommt während der Sperre nicht durch.
        self.assertEqual(self._login().status_code, 429)

    def test_ratenbegrenzung_zaehlt_nicht_je_benutzername(self):
        # Fehlversuche einer fremden IP mit dem Admin-Namen sperren den Admin nicht aus.
        fremd = app_web.app.test_client()
        for _ in range(app_web._LOGIN_MAX_FEHLVERSUCHE + 2):
            antwort = fremd.post(
                "/api/login",
                json={"benutzername": self._API_ADMIN, "passwort": "falsch"},
                environ_overrides={"REMOTE_ADDR": "203.0.113.9"},
            )
        self.assertEqual(antwort.status_code, 429)
        self.assertEqual(self._login().status_code, 200)

    def test_ratenbegrenzung_je_client_ip_mit_wechselnden_namen(self):
        for nummer in range(app_web._LOGIN_MAX_FEHLVERSUCHE):
            self.assertEqual(self._login(benutzername=f"unbekannt{nummer}", passwort="x").status_code, 401)
        # Ein weiterer Benutzername von derselben IP ist ebenfalls gesperrt.
        self.assertEqual(self._login().status_code, 429)

    def test_ratenbegrenzung_laeuft_nach_dem_zeitfenster_ab(self):
        jetzt = [1000.0]
        with patch.object(app_web, "_api_zeit", lambda: jetzt[0]):
            for _ in range(app_web._LOGIN_MAX_FEHLVERSUCHE):
                self._login(passwort="falsch")
            self.assertEqual(self._login().status_code, 429)
            jetzt[0] += app_web._LOGIN_FENSTER_SEKUNDEN + 1
            self.assertEqual(self._login().status_code, 200)

    def test_erfolgreicher_login_setzt_den_benutzerzaehler_zurueck(self):
        for _ in range(app_web._LOGIN_MAX_FEHLVERSUCHE - 1):
            self._login(passwort="falsch")
        self.assertEqual(self._login().status_code, 200)
        self.assertEqual(self._login(passwort="falsch").status_code, 401)

    def test_web_login_bleibt_ohne_ratenbegrenzung(self):
        # Bewusst akzeptiert (CLAUDE.md) - die Begrenzung gilt nur für /api/login.
        for _ in range(app_web._LOGIN_MAX_FEHLVERSUCHE + 3):
            antwort = self.client.post("/", data={"benutzername": "x", "passwort": "y"})
            self.assertNotEqual(antwort.status_code, 429)

    # --- Token-Prüfung ----------------------------------------------------------

    def test_ohne_token_ergibt_401(self):
        antwort = self.client.get("/api/termine")
        self.assertEqual(antwort.status_code, 401)
        self.assertEqual(antwort.headers["WWW-Authenticate"], "Bearer")
        self.assertIn("fehler", antwort.get_json())

    def test_ungueltiges_token_ergibt_401(self):
        for kopf in ("Bearer abc", "Bearer ", "Basic abc", "abc", "Bearer " + "x" * 200):
            antwort = self.client.get("/api/termine", headers={"Authorization": kopf})
            self.assertEqual(antwort.status_code, 401, kopf)

    def test_token_mit_anderem_salz_ergibt_401(self):
        from itsdangerous import URLSafeTimedSerializer
        konto = db.benutzer_stand(self.conn, self._API_ADMIN)
        fremd = URLSafeTimedSerializer(app_web.app.secret_key, salt="anderes-salz").dumps(
            {"b": konto["benutzername"], "k": konto["kennung"]}
        )
        self.assertEqual(self.client.get("/api/termine", headers=self._kopf(fremd)).status_code, 401)

    def test_abgelaufenes_token_ergibt_401(self):
        kopf = self._kopf()
        with patch.object(app_web, "_API_TOKEN_GUELTIGKEIT_SEKUNDEN", -1):
            self.assertEqual(self.client.get("/api/termine", headers=kopf).status_code, 401)

    def test_token_eines_geloeschten_kontos_ergibt_401(self):
        db.benutzer_anlegen(self.conn, "zweiter", "zweiterpasswort", ist_admin=True)
        kopf = self._kopf(self._login("zweiter", "zweiterpasswort").get_json()["token"])
        self.assertEqual(self.client.get("/api/termine", headers=kopf).status_code, 200)
        db.benutzer_loeschen(self.conn, "zweiter")
        self.assertEqual(self.client.get("/api/termine", headers=kopf).status_code, 401)

    def test_token_eines_neu_angelegten_kontos_gleichen_namens_ergibt_401(self):
        db.benutzer_anlegen(self.conn, "zweiter", "zweiterpasswort", ist_admin=True)
        kopf = self._kopf(self._login("zweiter", "zweiterpasswort").get_json()["token"])
        db.benutzer_loeschen(self.conn, "zweiter")
        db.benutzer_anlegen(self.conn, "zweiter", "zweiterpasswort", ist_admin=True)
        self.assertEqual(self.client.get("/api/termine", headers=kopf).status_code, 401)

    def test_token_eines_herabgestuften_admins_ergibt_403(self):
        db.benutzer_anlegen(self.conn, "zweiter", "zweiterpasswort", ist_admin=True)
        kopf = self._kopf(self._login("zweiter", "zweiterpasswort").get_json()["token"])
        self.conn.execute("UPDATE web_benutzer SET ist_admin = 0 WHERE benutzername = ?", ("zweiter",))
        self.conn.commit()
        self.assertEqual(self.client.get("/api/termine", headers=kopf).status_code, 403)

    def test_cookie_sitzung_allein_zaehlt_auf_api_nie(self):
        # Browser-Anmeldung als Administrator (Cookie), danach /api/ OHNE Bearer-Token.
        seite = self.client.get("/")
        treffer = re.search(r'name="csrf_token" value="([^"]+)"', seite.data.decode())
        anmeldung = self.client.post(
            "/", data={
                "benutzername": self._API_ADMIN, "passwort": self._API_PASSWORT, "csrf_token": treffer.group(1),
            },
        )
        self.assertEqual(anmeldung.status_code, 302)
        self.assertEqual(self.client.get("/admin/termine").status_code, 200)  # Cookie gilt im Web
        self.assertEqual(self.client.get("/api/termine").status_code, 401)
        self.assertEqual(self.client.get(f"/api/termine/{_TEST_SCHEMA}/ergebnisse").status_code, 401)
        # POST: die CSRF-Ausnahme darf keinen Zugriff öffnen - 401, nicht 403 oder 201.
        antwort = self.client.post(
            "/api/termine", data={"sqlite_datei": (io.BytesIO(b""), "t.sqlite")},
            content_type="multipart/form-data",
        )
        self.assertEqual(antwort.status_code, 401)
        self.assertEqual(self.export_aufrufe, [])

    def test_unbekannte_api_pfade_und_methoden_liefern_json_fehler(self):
        self.assertEqual(self.client.get("/api/gibtsnicht").get_json()["fehler"], "Nicht gefunden.")
        antwort = self.client.delete("/api/termine", headers=self._kopf())
        self.assertEqual(antwort.status_code, 405)
        self.assertIn("fehler", antwort.get_json())

    # --- Termine ------------------------------------------------------------------

    def test_termine_liste(self):
        self.termine = [
            _termin_info("termin_1", verein="Verein A", ort="Ort A", datum="2026-09-19", anzahl_teilnehmer=4),
            _termin_info("termin_2"),
        ]
        antwort = self.client.get("/api/termine", headers=self._kopf())
        self.assertEqual(antwort.status_code, 200)
        self.assertEqual(antwort.get_json(), {"termine": [
            {"schema_name": "termin_1", "verein": "Verein A", "ort": "Ort A", "datum": "2026-09-19",
             "anzahl_teilnehmer": 4},
            {"schema_name": "termin_2", "verein": None, "ort": None, "datum": None, "anzahl_teilnehmer": 0},
        ]})

    def test_nicht_admin_token_gibt_es_nicht(self):
        # Ein Helfer bekommt gar kein Token (403 beim Login) - siehe oben; hier zusätzlich:
        # ein von Hand gebautes Helfer-Token wird mit 403 abgewiesen.
        from itsdangerous import URLSafeTimedSerializer
        konto = db.benutzer_stand(self.conn, "helfer")
        token = URLSafeTimedSerializer(app_web.app.secret_key, salt=app_web._API_TOKEN_SALZ).dumps(
            {"b": konto["benutzername"], "k": konto["kennung"]}
        )
        self.assertEqual(self.client.get("/api/termine", headers=self._kopf(token)).status_code, 403)

    def _veroeffentlichen(self, datei, **zusatz):
        return self.client.post(
            "/api/termine", headers=self._kopf(), data={"sqlite_datei": datei},
            content_type="multipart/form-data", **zusatz,
        )

    def test_veroeffentlichen_ok(self):
        self.termine = []
        antwort = self._veroeffentlichen(TestAppWeb._echte_sqlite_datei_mit_veranstaltung("Testverein", "2026-09-19"))
        self.assertEqual(antwort.status_code, 201)
        daten = antwort.get_json()
        self.assertEqual(daten["termin"], {
            "schema_name": _TEST_SCHEMA, "verein": "Testverein", "ort": None, "datum": None,
            "anzahl_teilnehmer": 3,
        })
        self.assertIsNone(daten["dublette_hinweis"])
        self.assertEqual(len(self.export_aufrufe), 1)

    def test_veroeffentlichen_meldet_dublette_ohne_zu_blockieren(self):
        self.termine = [_termin_info("termin_9", verein="Testverein", datum="2026-09-19")]
        antwort = self._veroeffentlichen(TestAppWeb._echte_sqlite_datei_mit_veranstaltung("Testverein", "2026-09-19"))
        self.assertEqual(antwort.status_code, 201)
        self.assertIn("bereits einen veröffentlichten Termin", antwort.get_json()["dublette_hinweis"])
        self.assertEqual(len(self.export_aufrufe), 1)

    def test_veroeffentlichen_loescht_die_temp_datei(self):
        temp_dateien = []
        original = app_web._hochgeladene_termin_datei_speichern

        def merken(datei):
            pfad = original(datei)
            temp_dateien.append(pfad)
            return pfad

        with patch.object(app_web, "_hochgeladene_termin_datei_speichern", merken):
            self._veroeffentlichen(TestAppWeb._echte_sqlite_datei_mit_veranstaltung("Testverein", "2026-09-19"))
            self._veroeffentlichen(TestAppWeb._kaputte_sqlite_datei())
        self.assertEqual(len(temp_dateien), 2)
        for pfad in temp_dateien:
            self.assertFalse(os.path.exists(pfad), pfad)

    def test_veroeffentlichen_mit_falscher_endung_ergibt_400(self):
        antwort = self._veroeffentlichen((io.BytesIO(b""), "termin.txt"))
        self.assertEqual(antwort.status_code, 400)
        self.assertIn("keine .sqlite-Termin-Datei", antwort.get_json()["fehler"])
        self.assertEqual(self.export_aufrufe, [])

    def test_veroeffentlichen_ohne_datei_ergibt_400(self):
        antwort = self.client.post(
            "/api/termine", headers=self._kopf(), data={}, content_type="multipart/form-data",
        )
        self.assertEqual(antwort.status_code, 400)
        self.assertIn("fehler", antwort.get_json())
        self.assertEqual(self.export_aufrufe, [])

    def test_veroeffentlichen_mit_kaputter_datei_ergibt_400(self):
        antwort = self._veroeffentlichen(TestAppWeb._kaputte_sqlite_datei())
        self.assertEqual(antwort.status_code, 400)
        self.assertIn("keine gültige SHS-Termin-Datei", antwort.get_json()["fehler"])

    def test_veroeffentlichen_zu_gross_ergibt_413(self):
        with patch.object(app_web, "_API_MAX_UPLOAD_BYTES", 2000):
            antwort = self._veroeffentlichen((io.BytesIO(b"\0" * 5000), "gross.sqlite"))
        self.assertEqual(antwort.status_code, 413)
        self.assertIn("zu groß", antwort.get_json()["fehler"])
        self.assertEqual(self.export_aufrufe, [])

    def test_veroeffentlichen_limit_gilt_nur_fuer_diese_route(self):
        self.assertIsNone(app_web.app.config.get("MAX_CONTENT_LENGTH"))

    def test_veroeffentlichen_serverfehler_ergibt_500_json_und_loescht_temp(self):
        def kaputt(sqlite_conn, postgres_conn):
            raise RuntimeError("interner Fehler mit Details")

        with patch_db("exportiere_termin_nach_postgres", kaputt), self.assertLogs(app_web.app.logger, "ERROR"):
            antwort = self._veroeffentlichen(TestAppWeb._echte_sqlite_datei_mit_veranstaltung("Testverein", "2026-09-19"))
        self.assertEqual(antwort.status_code, 500)
        self.assertNotIn("Details", antwort.get_json()["fehler"])

    # --- Ergebnisse -----------------------------------------------------------------

    def test_ergebnisse_liefert_teilnehmer_mit_ergebnis(self):
        self.termine = [_termin_info("termin_7")]
        mit_id = db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Beispiel", vorname="Anna", rufname_hund="Rex", art="ED", stufe=2,
            disziplin="Trümmerfeld", startnummer=5,
        ))
        db.add_teilnehmer(self.conn, db.NeuerTeilnehmer(
            nachname="Muster", vorname="Max", rufname_hund="Bello", art="DK", stufe=1,
        ))
        db.eintragen_ergebnis(self.conn, mit_id, "Trümmerfeld", 50, 30)
        antwort = self.client.get("/api/termine/termin_7/ergebnisse", headers=self._kopf())
        self.assertEqual(antwort.status_code, 200)
        teilnehmer = {t["nachname"]: t for t in antwort.get_json()["teilnehmer"]}
        self.assertEqual(set(teilnehmer), {"Beispiel", "Muster"})
        anna = teilnehmer["Beispiel"]
        for schluessel, erwartet in (
            ("startnummer", 5), ("vorname", "Anna"), ("rufname_hund", "Rex"), ("art", "ED"),
            ("stufe", 2), ("disziplin", "Trümmerfeld"),
        ):
            self.assertEqual(anna[schluessel], erwartet, schluessel)
        self.assertEqual(set(anna), {
            "startnummer", "nachname", "vorname", "rufname_hund", "art", "stufe", "disziplin", "ergebnis",
        })
        self.assertEqual(anna["ergebnis"]["suche_truemmerfeld"], 50)
        self.assertEqual(anna["ergebnis"]["anzeige_truemmerfeld"], 30)
        self.assertIsNone(anna["ergebnis"]["suche_flaechensuche"])
        self.assertEqual(
            set(anna["ergebnis"]),
            {"teilnehmer_id", "suche_truemmerfeld", "anzeige_truemmerfeld", "suche_flaechensuche",
             "anzeige_flaechensuche", "suche_behaeltnis", "anzeige_behaeltnis", "disqualifiziert",
             "abbruch", "abbruch_grund", "stechen_sieger",
             "notiz_truemmerfeld", "notiz_flaechensuche", "notiz_behaeltnis"},
        )
        self.assertIsNone(teilnehmer["Muster"]["startnummer"])
        # Keine Kontaktdaten o. Ä. in der Antwort.
        self.assertNotIn("email", anna)

    def test_ergebnisse_fuer_unbekanntes_schema_ergibt_404(self):
        self.termine = [_termin_info("termin_7")]
        kopf = self._kopf()
        for schema in ("termin_8", "gibtsnicht", "termin_7; DROP SCHEMA public", "public"):
            antwort = self.client.get(f"/api/termine/{schema}/ergebnisse", headers=kopf)
            self.assertEqual(antwort.status_code, 404, schema)
            self.assertIn("fehler", antwort.get_json())

    def test_secure_cookie_standard_ist_an(self):
        self.assertTrue(app_web._umgebung_ein("SHS_GIBT_ES_NICHT", True))
        with patch.dict(os.environ, {"SHS_WEB_COOKIE_SECURE": "0"}):
            self.assertFalse(app_web._umgebung_ein("SHS_WEB_COOKIE_SECURE", True))
        with patch.dict(os.environ, {"SHS_WEB_COOKIE_SECURE": "1"}):
            self.assertTrue(app_web._umgebung_ein("SHS_WEB_COOKIE_SECURE", True))
        self.assertTrue(app_web.app.config["SESSION_COOKIE_SECURE"])


try:
    import psycopg2
except ImportError:
    psycopg2 = None

_POSTGRES_TEST_DSN =os.environ.get("SHS_TEST_POSTGRES_DSN")


class TestAppWebPostgres(unittest.TestCase):
    """Wenige HTTP-Abläufe end-zu-Ende gegen einen ECHTEN PostgreSQL-Server (Codex-
    Architekturprüfung 27.09.2026): anders als TestAppWeb oben ohne jeden db.*-Patch -
    Login, Terminwahl, Ergebniserfassung und Rückimport laufen also genau wie im
    Container über db.verbinde_postgres_server()/search_path je Termin-Schema. Dasselbe
    Skip-Verhalten wie die PostgreSQL-Tests in test_db.py (lokal ohne
    SHS_TEST_POSTGRES_DSN/psycopg2 übersprungen, läuft in der CI)."""

    _anmelden = _AppWebTestBasis._anmelden

    def setUp(self):
        if not _POSTGRES_TEST_DSN:
            self.skipTest(
                "SHS_TEST_POSTGRES_DSN nicht gesetzt - PostgreSQL-Tests übersprungen "
                "(z. B. lokal ohne laufenden Postgres-Server; läuft in der CI)"
            )
        if psycopg2 is None:
            self.skipTest("psycopg2 nicht installiert - PostgreSQL-Tests übersprungen")
        # Aufräumen über addCleanup statt tearDown: läuft auch dann, wenn setUp nach dem
        # Verbindungsaufbau scheitert (tearDown würde unittest in dem Fall überspringen).
        # Reihenfolge rückwärts: Config zurück, Datenbank leeren, Dateien löschen,
        # Verbindung schließen.
        self.pg = db.verbinde_postgres_server(_POSTGRES_TEST_DSN)
        self.addCleanup(self.pg.close)
        self._temp_dateien = []
        self.addCleanup(self._temp_dateien_loeschen)
        self._postgres_leeren()
        self.addCleanup(self._postgres_leeren)

        alte_config = {
            k: app_web.app.config.get(k) for k in ("SHS_POSTGRES_DSN", "SHS_ADMIN_SETUP_CODE")
        }
        self.addCleanup(app_web.app.config.update, alte_config)
        app_web.app.config.update(
            TESTING=True, SHS_POSTGRES_DSN=_POSTGRES_TEST_DSN, SHS_ADMIN_SETUP_CODE=_EINRICHTUNGS_CODE,
        )
        app_web.app.test_client_class = _CsrfTestClient
        self.client = app_web.app.test_client()

    def _temp_dateien_loeschen(self):
        for pfad in self._temp_dateien:
            if os.path.exists(pfad):
                os.remove(pfad)

    def _postgres_leeren(self):
        """Entfernt Termin-Schemas, Registry-Einträge und Web-Konten eines evtl. vorigen
        Testlaufs - wie TestTerminverwaltungPostgres/TestBenutzerkontenPostgres in
        test_db.py (rollback() zuerst, "public." nicht weglassen, siehe dort)."""
        self.pg.rollback()
        zeilen = self.pg.execute("SELECT schema_name FROM public.termin_registry").fetchall()
        for zeile in zeilen:
            self.pg.execute(f"DROP SCHEMA IF EXISTS {zeile['schema_name']} CASCADE")
        self.pg.execute("DELETE FROM public.termin_registry")
        self.pg.execute("DELETE FROM public.web_benutzer")
        self.pg.commit()

    # Wichtig: jede Hilfsfunktion, die über self.pg liest oder schreibt, schließt ihre
    # Transaktion mit commit() ab, damit self.pg keine Tabellensperren offen hält, während
    # die App über eigene Verbindungen arbeitet. Beim ersten lokalen Lauf gegen einen
    # echten Server hat genau das den Verbindungsaufbau der App hängen lassen: Damals
    # führte verbinde_postgres_server() bei JEDER Verbindung ein ALTER TABLE aus. Seit
    # 1.0.37 läuft die Einrichtung nur noch, wenn im Katalog etwas fehlt (siehe
    # test_db.TestTerminverwaltungPostgres.test_verbindungsaufbau_wartet_nicht_auf_offene_fremde_transaktion).

    def _termin_datei(self, verein: str) -> str:
        """Legt eine echte SQLite-Termin-Datei mit einem ED-Teilnehmer (Startnummer 1)
        an und liefert ihren Pfad."""
        fd, pfad = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        os.remove(pfad)
        self._temp_dateien.append(pfad)
        conn = db.init_db(pfad)
        try:
            db.set_veranstaltung(conn, verein=verein, datum="2026-09-27")
            db.add_teilnehmer(conn, db.NeuerTeilnehmer(
                nachname=f"Muster{verein}", vorname="Anna", rufname_hund="Rex", art="ED",
                stufe=1, disziplin="Trümmerfeld", startnummer=1,
            ))
        finally:
            conn.close()
        return pfad

    def _veroeffentlichen(self, pfad: str) -> db.TerminInfoPostgres:
        conn = db.init_db(pfad)
        try:
            return db.exportiere_termin_nach_postgres(conn, self.pg)
        finally:
            conn.close()
            self.pg.commit()

    def _pg_teilnehmer(self, schema_name: str) -> dict:
        db.oeffne_termin_postgres(self.pg, schema_name)
        teilnehmer = db.list_teilnehmer(self.pg)[0]
        self.pg.commit()
        return teilnehmer

    def test_ersteinrichtung_abmelden_und_erneut_anmelden(self):
        self._veroeffentlichen(self._termin_datei("VereinA"))
        antwort = self._anmelden()
        self.assertIn(b"MusterVereinA", antwort.data)
        admin_vorhanden = db.gibt_es_admin(self.pg)
        self.pg.commit()
        self.assertTrue(admin_vorhanden)

        self.client.post("/logout")
        self.assertEqual(self.client.get("/teilnehmer").status_code, 302)
        antwort = self.client.post(
            "/", data={"benutzername": _ADMIN_NAME, "passwort": _ADMIN_PASSWORT}, follow_redirects=True,
        )
        self.assertIn(b"MusterVereinA", antwort.data)

    def test_terminwahl_zeigt_daten_des_gewaehlten_termins(self):
        self._veroeffentlichen(self._termin_datei("VereinA"))
        termin_b = self._veroeffentlichen(self._termin_datei("VereinB"))
        antwort = self._anmelden()
        self.assertIn(b"VereinA", antwort.data)
        self.assertIn(b"VereinB", antwort.data)

        antwort = self.client.post(
            "/termin-waehlen", data={"schema_name": termin_b.schema_name}, follow_redirects=True,
        )
        self.assertIn(b"MusterVereinB", antwort.data)
        self.assertNotIn(b"MusterVereinA", antwort.data)

    def test_ergebnis_speichern_landet_in_postgres(self):
        termin = self._veroeffentlichen(self._termin_datei("VereinA"))
        teilnehmer_id = self._pg_teilnehmer(termin.schema_name)["id"]
        self._anmelden()

        antwort = self.client.post(
            f"/teilnehmer/{teilnehmer_id}",
            data={"suche_Trümmerfeld": "45", "anzeige_Trümmerfeld": "25"},
            follow_redirects=True,
        )
        self.assertEqual(antwort.status_code, 200)

        db.oeffne_termin_postgres(self.pg, termin.schema_name)
        ergebnis = db.get_ergebnis(self.pg, teilnehmer_id)
        self.pg.commit()
        self.assertEqual(ergebnis["suche_truemmerfeld"], 45)
        self.assertEqual(ergebnis["anzeige_truemmerfeld"], 25)

    def test_wer_hat_eingetragen_steht_nur_im_web_schema(self):
        # UX-Test Web 19.11.2026 (B6): web_aenderungen entsteht im Termin-Schema (auch für ältere
        # Termine beim Öffnen nachgerüstet), wird beim Speichern gefüllt und vom Admin gesehen.
        termin = self._veroeffentlichen(self._termin_datei("VereinA"))
        teilnehmer_id = self._pg_teilnehmer(termin.schema_name)["id"]
        db.oeffne_termin_postgres(self.pg, termin.schema_name)
        self.pg.execute("DROP TABLE web_aenderungen")  # Stand eines älteren Web-Termins
        self.pg.commit()
        self._anmelden()  # öffnet den Termin: Tabelle wird nachgerüstet
        self.client.post(f"/teilnehmer/{teilnehmer_id}", data={"suche_Trümmerfeld": "45", "anzeige_Trümmerfeld": "25"})
        db.oeffne_termin_postgres(self.pg, termin.schema_name)
        aenderungen = db.aenderungen_lesen(self.pg)
        self.pg.commit()
        self.assertEqual(aenderungen[teilnehmer_id]["Trümmerfeld"][0], _ADMIN_NAME)
        self.assertIn(f"zuletzt {_ADMIN_NAME}", self.client.get("/ergebnisse").data.decode())

    def test_rueckimport_ueber_admin_termine_mit_download(self):
        pfad = self._termin_datei("VereinA")
        termin = self._veroeffentlichen(pfad)
        teilnehmer_id = self._pg_teilnehmer(termin.schema_name)["id"]
        self._anmelden()
        self.client.post(
            f"/teilnehmer/{teilnehmer_id}",
            data={"suche_Trümmerfeld": "48", "anzeige_Trümmerfeld": "28"},
        )

        with open(pfad, "rb") as f:
            inhalt = f.read()
        antwort = self.client.post(
            f"/admin/termine/{termin.schema_name}/zurueckholen",
            data={"sqlite_datei": (io.BytesIO(inhalt), "termin_verein.sqlite")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(antwort.status_code, 200)
        text = antwort.data.decode()
        self.assertIn("1 Teilnehmer", text)

        treffer = re.search(r'href="(/admin/termine/download/[^"]+)"', text)
        self.assertIsNotNone(treffer)
        download = self.client.get(treffer.group(1))
        self.assertEqual(download.status_code, 200)

        # Die heruntergeladene Termin-Datei enthält das im Web erfasste Ergebnis.
        fd, zurueck_pfad = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self._temp_dateien.append(zurueck_pfad)
        with open(zurueck_pfad, "wb") as f:
            f.write(download.data)
        conn = db.init_db(zurueck_pfad)
        try:
            ergebnis = db.get_ergebnis(conn, db.list_teilnehmer(conn)[0]["id"])
        finally:
            conn.close()
        self.assertEqual(ergebnis["suche_truemmerfeld"], 48)
        self.assertEqual(ergebnis["anzeige_truemmerfeld"], 28)


if __name__ == "__main__":
    unittest.main(verbosity=2)
