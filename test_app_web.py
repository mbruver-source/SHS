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
import tempfile
import time
import unittest
from unittest.mock import patch

from flask.testing import FlaskClient

import app_web
import db

_TEST_SCHEMA = "termin_test"  # Platzhalter - die SQLite-Ersatzfunktion unten ignoriert
                               # den Schema-Namen ohnehin (eine einzelne Datei kennt
                               # keine Schemas/search_path)
_ADMIN_NAME = "chef"
_ADMIN_PASSWORT = "sicheres_passwort"


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
            patch("db.verbinde_postgres_server", lambda dsn: _NichtSchliessendeVerbindung(self.conn)),
            patch("db.oeffne_termin_postgres", _fake_oeffne_termin),
            patch("db.liste_termine_postgres", lambda conn: self.termine),
            patch("db._setze_termin_suchpfad", _fake_setze_termin_suchpfad),
            patch("db.loesche_termin_postgres", lambda conn, schema_name: _fake_loesche_termin(self, conn, schema_name)),
            patch("db.exportiere_termin_nach_postgres", lambda sqlite_conn, postgres_conn: _fake_exportiere_termin(self, sqlite_conn, postgres_conn)),
            patch("db.importiere_ergebnisse_aus_postgres", lambda postgres_conn, schema_name, sqlite_conn: _fake_importiere_ergebnisse(self, postgres_conn, schema_name, sqlite_conn)),
        ]
        for p in self._patches:
            p.start()

        app_web.app.config.update(TESTING=True, SHS_POSTGRES_DSN="postgresql://test-dsn")
        # _CsrfTestClient statt des normalen Test-Clients - siehe dortiger Docstring:
        # ergänzt jede POST-Anfrage automatisch um ein gültiges CSRF-Token, damit diese
        # Tests weiterhin die fachliche Formularlogik prüfen, ohne an der (separat
        # geprüften) CSRF-Absicherung zu scheitern.
        app_web.app.test_client_class = _CsrfTestClient
        self.client = app_web.app.test_client()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self.conn.close()
        if os.path.exists(self.pfad):
            os.remove(self.pfad)

    def _anmelden(self, benutzername=_ADMIN_NAME, passwort=_ADMIN_PASSWORT):
        """Richtet bei Bedarf den ersten Administrator ein (siehe _ersteinrichtung) und
        meldet ihn an - mit dem Standard-self.termine (genau ein Termin) landet man damit
        direkt auf der Teilnehmerliste, wie es die bestehenden Tests unten erwarten."""
        return self.client.post(
            "/",
            data={"benutzername": benutzername, "passwort": passwort, "passwort_wiederholung": passwort},
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
            "/", data={"benutzername": _ADMIN_NAME, "passwort": "kurz", "passwort_wiederholung": "kurz"}
        )
        self.assertIn("mindestens 8 Zeichen".encode(), antwort.data)
        self.assertFalse(db.gibt_es_admin(self.conn))

    def test_ersteinrichtung_lehnt_unterschiedliche_passwoerter_ab(self):
        antwort = self.client.post(
            "/",
            data={"benutzername": _ADMIN_NAME, "passwort": _ADMIN_PASSWORT, "passwort_wiederholung": "anders123"},
        )
        self.assertIn("stimmen nicht überein".encode(), antwort.data)
        self.assertFalse(db.gibt_es_admin(self.conn))

    def test_normaler_login_erscheint_sobald_admin_existiert(self):
        self._anmelden()
        self.client.get("/logout")
        antwort = self.client.get("/")
        self.assertNotIn("Ersteinrichtung".encode(), antwort.data)
        self.assertIn("Benutzername".encode(), antwort.data)

    # --- Login ---------------------------------------------------------------

    def test_login_mit_falschem_passwort_zeigt_fehler(self):
        self._anmelden()
        self.client.get("/logout")
        antwort = self.client.post("/", data={"benutzername": _ADMIN_NAME, "passwort": "falsches_passwort"})
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("falsch".encode(), antwort.data)

    def test_login_mit_unbekanntem_benutzer_zeigt_denselben_fehler(self):
        self._anmelden()
        self.client.get("/logout")
        antwort = self.client.post("/", data={"benutzername": "gibtsnicht", "passwort": "irgendwas123"})
        self.assertIn("falsch".encode(), antwort.data)

    def test_login_ignoriert_gross_und_kleinschreibung_beim_benutzernamen(self):
        # Praxisfall (siehe db.pruefe_login): ein Konto wurde z. B. als "chef" angelegt,
        # beim Anmelden - insbesondere auf Mobilgeräten mit automatischer
        # Groß-/Kleinschreibung des ersten Buchstabens - wird aber "Chef" eingegeben.
        self._anmelden()
        self.client.get("/logout")
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

    def test_logout_entfernt_session(self):
        self._anmelden()
        self.client.get("/logout")
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
        self.client.get("/logout")
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
        self.assertEqual(konto, {"benutzername": "helfer", "ist_admin": False})

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
        self.client.get("/logout")
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

    def test_rollenaenderung_wird_ohne_neuanmeldung_uebernommen(self):
        """Teil desselben Fixes: _aktueller_benutzer_oder_redirect() aktualisiert
        session["ist_admin"] bei JEDER Anfrage neu aus der Datenbank - ein
        zwischenzeitlich auf die Rolle "Eintragen" zurückgestuftes Konto verliert damit
        seine Admin-Rechte, ohne sich neu anmelden zu müssen (und ohne dass die stale
        Session weiterhin Admin-Zugriff gewähren würde)."""
        self._anmelden()
        db.benutzer_anlegen(self.conn, "helfer", "helferpasswort", ist_admin=True)
        self.client.get("/logout")
        self.client.post("/", data={"benutzername": "helfer", "passwort": "helferpasswort"})
        self.assertEqual(self.client.get("/admin/benutzer").status_code, 200)

        self.conn.execute("UPDATE web_benutzer SET ist_admin = 0 WHERE benutzername = 'helfer'")
        self.conn.commit()

        self.assertEqual(self.client.get("/admin/benutzer").status_code, 403)

    # --- Teilnehmerliste ---------------------------------------------------------

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
        self.client.get("/logout")
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
