"""Tests für app_web.py - Flask-Backend der geplanten Web-Version (V1: Ergebniseingabe,
siehe Modul-Docstring dort für den Architektur-Hintergrund).

Testet die eigentliche Anfragen-Logik (Login/Zugangscode, Teilnehmerliste, Ergebnis
erfassen inkl. Validierung) mit dem Flask-Test-Client GEGEN EINE ECHTE, temporäre
SQLite-Termin-Datei (über db.init_db() - dieselbe, bereits in test_db.py ausführlich
geprüfte Fachlogik wie die Desktop-Version). Nur die drei PostgreSQL-spezifischen
"Klebefunktionen" (verbinde_postgres_server/pruefe_zugangscode_postgres/
oeffne_termin_postgres) werden dafür durch einfache Ersatzfunktionen ausgetauscht, die
stattdessen mit der SQLite-Datei arbeiten - diese drei Funktionen selbst sind bereits in
test_db.py (TestTerminverwaltungPostgres) gegen einen echten PostgreSQL-Server geprüft.
So braucht dieses Modul kein installiertes psycopg2 und läuft überall, deckt aber die
komplette übrige Anwendungslogik (Formularvalidierung, Session, Weiterleitung,
Statusanzeige) mit echten Datenbankzugriffen statt gemockten Rückgabewerten ab."""

import os
import tempfile
import unittest
from unittest.mock import patch

import app_web
import db

_TEST_ZUGANGSCODE = "123456"
_TEST_SCHEMA = "termin_test"  # Platzhalter - die SQLite-Ersatzfunktion unten ignoriert
                               # den Schema-Namen ohnehin (eine einzelne Datei kennt
                               # keine Schemas/search_path)


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


def _fake_pruefe_zugangscode(conn, zugangscode):
    return _TEST_SCHEMA if zugangscode.strip() == _TEST_ZUGANGSCODE else None


def _fake_oeffne_termin(conn, schema_name):
    pass


class TestAppWeb(unittest.TestCase):
    def setUp(self):
        fd, self.pfad = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        os.remove(self.pfad)
        self.conn = db.init_db(self.pfad)

        self._patches = [
            patch("db.verbinde_postgres_server", lambda dsn: _NichtSchliessendeVerbindung(self.conn)),
            patch("db.pruefe_zugangscode_postgres", _fake_pruefe_zugangscode),
            patch("db.oeffne_termin_postgres", _fake_oeffne_termin),
        ]
        for p in self._patches:
            p.start()

        app_web.app.config.update(TESTING=True, SHS_POSTGRES_DSN="postgresql://test-dsn")
        self.client = app_web.app.test_client()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self.conn.close()
        if os.path.exists(self.pfad):
            os.remove(self.pfad)

    def _anmelden(self):
        return self.client.post("/", data={"zugangscode": _TEST_ZUGANGSCODE}, follow_redirects=True)

    # --- Login -----------------------------------------------------------------

    def test_login_mit_falschem_code_zeigt_fehler(self):
        antwort = self.client.post("/", data={"zugangscode": "000000"})
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("nicht erkannt".encode(), antwort.data)

    def test_login_mit_richtigem_code_leitet_zur_teilnehmerliste(self):
        antwort = self._anmelden()
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("Teilnehmer".encode(), antwort.data)

    def test_teilnehmerliste_ohne_login_leitet_zum_login(self):
        antwort = self.client.get("/teilnehmer")
        self.assertEqual(antwort.status_code, 302)

    def test_logout_entfernt_session(self):
        self._anmelden()
        self.client.get("/logout")
        antwort = self.client.get("/teilnehmer")
        self.assertEqual(antwort.status_code, 302)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
