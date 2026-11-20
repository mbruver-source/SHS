"""Ende-zu-Ende-Test der Web-Strecke zwischen Desktop und Web-Server - ohne Qt.

Der ECHTE Desktop-Client (web_sync.WebClient, mit Fingerabdruck-Pinning) spricht über HTTPS
(lokaler werkzeug-Server auf einem freien Port, selbstsigniertes Zertifikat zur Testlaufzeit, wie
in test_web_sync.py) mit der ECHTEN Flask-App app_web.app. Echt laufen: Client, TLS/Pinning, alle
Routen (/api/, /ergebnisse, /bewertungsbogen, Sammel-PDF), Token-/Sitzungsprüfung, kopiere_termin_daten
und exportiere_termin_nach_postgres (Kopierlogik, Status/Notizen), Ergebnisserialisierung der API,
importiere_ergebnisse_aus_liste (Desktop-Import) und die Konten-Logik (db.admin_einrichten, pruefe_login).

Ersetzt ist nur die PostgreSQL-Klebeschicht (verbinde_postgres_server, erstelle_termin_postgres,
oeffne_termin_postgres, liste_termine_postgres, loesche_termin_postgres, _setze_termin_suchpfad):
Das „public“-Schema (Konten) und jeder Termin („Schema“) sind je eine SQLite-Datei in einem
Temp-Ordner; die Verbindung einer Anfrage (_SimVerbindung) zeigt je nach „search_path“ auf die eine
oder andere. Die echten PostgreSQL-Wrapper sind in test_db.py (TestTerminSyncPostgres, nur CI)
geprüft.

Nicht abgedeckt: echte PostgreSQL-Semantik (Schemas, Transaktionen, Nebenläufigkeit mehrerer
Richter), der Windows-Tresor und die Qt-Dialoge (desktop_web.py), ein Reverse-Proxy (Caddy) vor dem
Server und die Ratenbegrenzung (steht in test_app_web.py)."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import quote

from werkzeug.serving import WSGIRequestHandler, make_server

import app_web
import db
import web_sync
from db_testhilfen import patch_db
from test_app_web import _CsrfTestClient, _FormularLeser
from test_web_sync import _fingerabdruck_der_datei, _zertifikat_erzeugen

_ADMIN = "webadmin"
_ADMIN_PW = "admin-passwort-123"
_HELFER = "helfer"
_HELFER_PW = "helfer-passwort-123"
T, F, B = db.ALLE_DISZIPLINEN  # Trümmerfeld, Flächensuche, Behältnisstrecke

_ECHTES_CONNECT = sqlite3.connect


def _connect_threadfrei(*args, **kwargs):
    """Der Server beantwortet Anfragen in eigenen Threads, die Test-Datenbanken werden aber im
    Test-Thread geöffnet: sqlite3.connect darf deshalb den Thread-Check abschalten (Anfragen laufen
    im Test nacheinander, nie gleichzeitig)."""
    kwargs.setdefault("check_same_thread", False)
    return _ECHTES_CONNECT(*args, **kwargs)


# --- Ersatz für die PostgreSQL-Klebeschicht ----------------------------------------------------

class _SimWebDb:
    """„Server-Datenbank“: public (Konten) und je Termin ein Schema, jeweils eine SQLite-Datei."""

    def __init__(self, ordner: Path):
        self.ordner = ordner
        self.public = _connect_threadfrei(str(ordner / "public.sqlite"))
        self.public.row_factory = sqlite3.Row
        self.public.execute(db._WEB_BENUTZER_SCHEMA.replace("public.web_benutzer", "web_benutzer"))
        self.public.execute(db._WEB_BENUTZER_INDEX_BENUTZERNAME_LOWER)
        self.public.commit()
        self.termine: dict[str, tuple[int, sqlite3.Connection]] = {}
        self._zaehler = 0

    def verbindung(self) -> "_SimVerbindung":
        return _SimVerbindung(self)

    def termin_verbindung(self, schema_name: str) -> sqlite3.Connection:
        return self.termine[schema_name][1]

    def schliessen(self) -> None:
        for _id, conn in self.termine.values():
            conn.close()
        self.public.close()


class _SimVerbindung:
    """Verbindung EINER Anfrage: leitet an das Schema weiter, auf das der „search_path“ zeigt;
    close() tut nichts (die Dateien gehören der _SimWebDb)."""

    def __init__(self, sim: _SimWebDb):
        self.sim = sim
        self.aktuell = sim.public

    def __getattr__(self, name):
        return getattr(self.aktuell, name)

    def close(self):
        pass


def _sim_setze_suchpfad(conn, schema_name):
    if schema_name == "public":
        conn.aktuell = conn.sim.public
        return
    db._pruefe_schema_name(schema_name)
    conn.aktuell = conn.sim.termin_verbindung(schema_name)


def _sim_oeffne_termin(conn, schema_name):
    _sim_setze_suchpfad(conn, schema_name)  # unbekanntes Schema: KeyError, wie ein fehlendes Schema


def _sim_erstelle_termin(conn):
    sim = conn.sim
    sim._zaehler += 1
    schema_name = f"termin_{sim._zaehler}"
    termin_conn = db.init_db(str(sim.ordner / f"{schema_name}.sqlite"))
    sim.termine[schema_name] = (sim._zaehler, termin_conn)
    conn.aktuell = sim.public
    return db.TerminInfoPostgres(
        id=sim._zaehler, schema_name=schema_name, verein=None, ort=None, datum=None,
        anzahl_teilnehmer=0, erstellt_am="2026-11-19T00:00:00+00:00",
    )


def _sim_liste_termine(conn):
    ergebnis = []
    for schema_name, (nummer, termin_conn) in conn.sim.termine.items():
        v = termin_conn.execute("SELECT * FROM veranstaltung WHERE id = 1").fetchone()
        anzahl = termin_conn.execute(
            "SELECT COUNT(*) AS anzahl FROM teilnehmer WHERE COALESCE(keine_teilnahme, 0) = 0").fetchone()["anzahl"]
        ergebnis.append(db.TerminInfoPostgres(
            id=nummer, schema_name=schema_name, verein=v["verein"] if v else None, ort=v["ort"] if v else None,
            datum=v["datum"] if v else None, anzahl_teilnehmer=anzahl, erstellt_am="2026-11-19T00:00:00+00:00"))
    conn.aktuell = conn.sim.public
    ergebnis.sort(key=lambda t: (t.datum or "", t.schema_name), reverse=True)
    return ergebnis


def _sim_loesche_termin(conn, schema_name):
    _id, termin_conn = conn.sim.termine.pop(schema_name)
    termin_conn.close()


# --- lokaler HTTPS-Server mit der echten Flask-App ---------------------------------------------

class _ZaehlendeApp:
    """WSGI-Hülle um die Flask-App: merkt sich jede Anfrage, die tatsächlich ankommt (HTTP-Ebene,
    also erst nach TLS-Handshake und gesendeter Anfrage)."""

    def __init__(self, app):
        self.app = app
        self.anfragen: list[tuple[str, str]] = []

    def __call__(self, environ, start_response):
        self.anfragen.append((environ["REQUEST_METHOD"], environ["PATH_INFO"]))
        return self.app(environ, start_response)


class _StilleAnfragen(WSGIRequestHandler):
    def log(self, type, message, *args):  # noqa: A002 - Signatur von werkzeug
        pass


class _HttpsServer:
    def __init__(self, cert: str, key: str, wsgi):
        self.httpd = make_server("127.0.0.1", 0, wsgi, threaded=True, ssl_context=(cert, key),
                                 request_handler=_StilleAnfragen)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.adresse = f"https://127.0.0.1:{self.httpd.server_address[1]}"

    def stoppen(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(5)


# --- der Test ----------------------------------------------------------------------------------

class TestEndeZuEndeWeb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._zert_ordner = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        try:
            cls.cert, cls.key = _zertifikat_erzeugen(Path(cls._zert_ordner.name))
        except unittest.SkipTest:
            cls._zert_ordner.cleanup()
            raise
        cls.fingerabdruck = _fingerabdruck_der_datei(cls.cert)

    @classmethod
    def tearDownClass(cls):
        cls._zert_ordner.cleanup()

    def setUp(self):
        self._ordner_obj = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._ordner_obj.cleanup)
        self.ordner = Path(self._ordner_obj.name)

        patch_connect = mock.patch.object(sqlite3, "connect", _connect_threadfrei)
        patch_connect.start()
        self.addCleanup(patch_connect.stop)

        self.sim = _SimWebDb(self.ordner)
        self.addCleanup(self.sim.schliessen)
        patches = [
            patch_db("verbinde_postgres_server", lambda dsn, password=None: self.sim.verbindung()),
            patch_db("erstelle_termin_postgres", _sim_erstelle_termin),
            patch_db("oeffne_termin_postgres", _sim_oeffne_termin),
            patch_db("liste_termine_postgres", _sim_liste_termine),
            patch_db("loesche_termin_postgres", _sim_loesche_termin),
            patch_db("_setze_termin_suchpfad", _sim_setze_suchpfad),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        alter_dsn = app_web.app.config.get("SHS_POSTGRES_DSN")
        app_web.app.config["SHS_POSTGRES_DSN"] = "postgresql://test-dsn"
        self.addCleanup(app_web.app.config.__setitem__, "SHS_POSTGRES_DSN", alter_dsn)
        app_web._login_fehlversuche.clear()
        self.addCleanup(app_web._login_fehlversuche.clear)

        # Web-Admin über die echte Konten-Logik (Passwort-Hashing ist langsam: weitere Konten nur bei Bedarf).
        self.assertTrue(db.admin_einrichten(self.sim.verbindung(), _ADMIN, _ADMIN_PW))

        self.wsgi = _ZaehlendeApp(app_web.app)
        self.server = _HttpsServer(self.cert, self.key, self.wsgi)
        self.addCleanup(self.server.stoppen)

        self.client = web_sync.WebClient(self.server.adresse, self.fingerabdruck)
        self.browser = _CsrfTestClient(app_web.app, app_web.app.response_class)

        self._desktop_datei()

    # -- Desktop-Termin-Datei (echte SQLite-Datei von db.init_db)
    def _desktop_datei(self):
        self.pfad = self.ordner / "desktop.sqlite"
        self.desktop = db.init_db(str(self.pfad))
        self.addCleanup(self.desktop.close)
        db.set_veranstaltung(self.desktop, verein="Musterverein", datum="2026-12-05", ort="Musterstadt")

        def neu(nr, nachname, vorname, hund, art, stufe, disziplin=None):
            return db.add_teilnehmer(self.desktop, db.NeuerTeilnehmer(
                nachname=nachname, vorname=vorname, rufname_hund=hund, art=art, stufe=stufe,
                disziplin=disziplin, startnummer=nr))

        self.d = {}
        self.d[1] = neu(1, "Aaltje", "Anna", "Rex", "ED", 1, F)
        self.d[2] = neu(2, "Baumann", "Bernd", "Bello", "DK", 2)
        self.d[3] = neu(3, "Cramer", "Cora", "Luna", "ED", 3, T)
        self.d[4] = neu(4, "Dorn", "Dora", "Fonda", "ED", 1, T)
        self.d[5] = neu(5, "Ehlert", "Emil", "Max", "ED", 1, B)
        self.d[6] = neu(6, "Fiedler", "Frieda", "Nika", "ED", 2, F)
        self.d[7] = neu(7, "Graf", "Gert", "Ben", "ED", 2, T)
        self.d[8] = neu(8, "Hahn", "Hilde", "Asta", "ED", 1, F)
        db.eintragen_ergebnis(self.desktop, self.d[1], F, 40, 30)
        db.eintragen_ergebnis(self.desktop, self.d[2], T, 50, 30)
        db.setze_ergebnis_status(self.desktop, self.d[3], True, False)  # disqualifiziert
        db.setze_ergebnis_status(self.desktop, self.d[4], False, True, abbruch_grund="krankheit")
        db.eintragen_ergebnis(self.desktop, self.d[5], B, 30, 20)
        db.setze_notiz(self.desktop, self.d[5], B, "Gegenstand in der Ecke")

    def _ergebnis(self, conn, nummer, ids):
        return db.get_ergebnis(conn, ids[nummer]) or {}

    def _web_ids(self, schema_name):
        conn = self.sim.termin_verbindung(schema_name)
        return {t["startnummer"]: t["id"] for t in db.list_teilnehmer(conn)}

    def _anmelden(self):
        self.client.anmelden(_ADMIN, _ADMIN_PW)

    def _veroeffentlichen(self):
        """Wie desktop_web.termin_veroeffentlichen: konsistente Kopie hochladen."""
        self._anmelden()
        kopie = self.ordner / "hochladen.sqlite"
        ziel = sqlite3.connect(str(kopie))
        try:
            self.desktop.backup(ziel)
        finally:
            ziel.close()
        termin, hinweis = self.client.veroeffentlichen(str(kopie))
        return termin, hinweis

    def _browser_anmelden(self):
        antwort = self.browser.post("/", data={"benutzername": _ADMIN, "passwort": _ADMIN_PW}, follow_redirects=True)
        self.assertEqual(antwort.status_code, 200)
        self.assertIn("Teilnehmer", antwort.get_data(as_text=True))

    def _formular(self, pfad):
        antwort = self.browser.get(pfad)
        self.assertEqual(antwort.status_code, 200, pfad)
        leser = _FormularLeser()
        leser.feed(antwort.get_data(as_text=True))
        return leser.daten

    def _senden(self, pfad, daten):
        antwort = self.browser.post(pfad, data=daten)
        self.assertEqual(antwort.status_code, 302, antwort.get_data(as_text=True)[:600])
        self.assertNotIn("nichts+gespeichert", antwort.headers["Location"])

    # -- 1. Fingerabdruck und Pinning
    def test_fingerabdruck_holen_und_pinning(self):
        self.assertEqual(web_sync.hole_fingerabdruck(self.server.adresse), self.fingerabdruck)
        self.assertEqual(self.wsgi.anfragen, [], "die Erstverbindung darf nichts senden")

        gepinnt = web_sync.WebClient(self.server.adresse, web_sync.fingerabdruck_anzeige(self.fingerabdruck))
        gepinnt.anmelden(_ADMIN, _ADMIN_PW)
        self.assertEqual(self.wsgi.anfragen, [("POST", "/api/login")])

        falsch = web_sync.WebClient(self.server.adresse, "ab" * 32)
        vorher = len(self.wsgi.anfragen)
        with self.assertRaises(web_sync.ZertifikatFehler) as fehler:
            falsch.anmelden(_ADMIN, _ADMIN_PW)
        self.assertEqual(fehler.exception.erhalten, self.fingerabdruck)
        self.assertNotIn(_ADMIN_PW, fehler.exception.meldung)
        self.assertEqual(len(self.wsgi.anfragen), vorher, "bei falschem Fingerabdruck darf nichts gesendet werden")

    # -- 2. Anmeldung per API
    def test_anmeldung_per_api(self):
        self._anmelden()
        self.assertEqual(self.client.gueltig_sekunden, 8 * 60 * 60)
        self.assertEqual(self.client.termine(), [])

        with self.assertRaises(web_sync.AnmeldeFehler) as falsch:
            web_sync.WebClient(self.server.adresse, self.fingerabdruck).anmelden(_ADMIN, "falsches-passwort")
        self.assertEqual(falsch.exception.status, 401)
        self.assertNotIn("falsches-passwort", falsch.exception.meldung)

        db.benutzer_anlegen(self.sim.verbindung(), _HELFER, _HELFER_PW)
        with self.assertRaises(web_sync.AnmeldeFehler) as kein_admin:
            web_sync.WebClient(self.server.adresse, self.fingerabdruck).anmelden(_HELFER, _HELFER_PW)
        self.assertEqual(kein_admin.exception.status, 403)

    # -- 3. Termin veröffentlichen
    def test_veroeffentlichen_uebernimmt_teilnehmer_status_und_notiz(self):
        termin, hinweis = self._veroeffentlichen()
        self.assertIsNone(hinweis)
        schema = termin["schema_name"]
        self.assertEqual((termin["verein"], termin["datum"], termin["anzahl_teilnehmer"]), ("Musterverein", "2026-12-05", 8))
        self.assertEqual([t["schema_name"] for t in self.client.termine()], [schema])

        web = self.sim.termin_verbindung(schema)
        ids = self._web_ids(schema)
        self.assertEqual(sorted(ids), list(range(1, 9)))
        self.assertEqual(db.get_veranstaltung(web)["ort"], "Musterstadt")
        self.assertEqual(self._ergebnis(web, 1, ids)["suche_flaechensuche"], 40)
        self.assertEqual(self._ergebnis(web, 2, ids)["anzeige_truemmerfeld"], 30)
        self.assertEqual(self._ergebnis(web, 3, ids)["disqualifiziert"], 1)
        abbruch = self._ergebnis(web, 4, ids)
        self.assertEqual((abbruch["abbruch"], abbruch["abbruch_grund"]), (1, "krankheit"))
        self.assertEqual(self._ergebnis(web, 5, ids)[db.NOTIZ_SPALTEN[B]], "Gegenstand in der Ecke")

        # ... und auch in der Antwort der API (Serialisierung der Server-Seite)
        liste = {t["startnummer"]: t for t in self.client.ergebnisse(schema)}
        self.assertEqual(liste[3]["ergebnis"]["disqualifiziert"], 1)
        self.assertEqual(liste[4]["ergebnis"]["abbruch_grund"], "krankheit")
        self.assertEqual(liste[5]["ergebnis"].get(db.NOTIZ_SPALTEN[B]), "Gegenstand in der Ecke")

        # Dublette: zweites Veröffentlichen gibt einen Hinweis, blockiert aber nicht.
        _termin2, hinweis2 = self._veroeffentlichen()
        self.assertIn("Musterverein", hinweis2)
        self.assertEqual(len(self.client.termine()), 2)

    # -- 4.-5. Im Web erfassen und zurückholen
    def _im_web_erfassen(self, schema):
        ids = self._web_ids(schema)
        self._browser_anmelden()

        # Ergebnistabelle: Punkte ändern (Nr. 1), Disqualifikation zurücknehmen (Nr. 3), Abbruchgrund
        # ändern (Nr. 4), neue Disqualifikation (Nr. 7), neuer Abbruch (Nr. 8), Nr. 6 (umbenannt) mit Punkten.
        daten = self._formular("/ergebnisse")
        daten[f"suche_{F}_{ids[1]}"], daten[f"anzeige_{F}_{ids[1]}"] = "55", "35"
        self.assertEqual(daten[f"dq_{ids[3]}"], "1")
        del daten[f"dq_{ids[3]}"]
        daten[f"abbruch_{ids[4]}"] = "verletzung_hund"
        daten[f"dq_{ids[7]}"] = "1"
        daten[f"abbruch_{ids[8]}"] = "krankheit"
        daten[f"suche_{F}_{ids[6]}"], daten[f"anzeige_{F}_{ids[6]}"] = "33", "22"
        self._senden("/ergebnisse", daten)

        # Online-Bewertungsbogen: Nr. 2 (DK) Behältnisstrecke mit Punkten und Notiz.
        pfad = f"/bewertungsbogen/{ids[2]}/{quote(B)}"
        bogen = self._formular(pfad)
        bogen[f"suche_{B}_{ids[2]}"], bogen[f"anzeige_{B}_{ids[2]}"] = "20", "10"
        bogen[f"notiz_{ids[2]}"] = "Gegenstand links hinten"
        self._senden(pfad, bogen)
        return ids

    def test_web_erfassen_und_zurueckholen_in_die_desktop_datei(self):
        termin, _hinweis = self._veroeffentlichen()
        schema = termin["schema_name"]
        ids = self._im_web_erfassen(schema)
        web = self.sim.termin_verbindung(schema)

        # Stand im Web
        self.assertEqual(self._ergebnis(web, 1, ids)["suche_flaechensuche"], 55)
        self.assertEqual(self._ergebnis(web, 3, ids)["disqualifiziert"], 0)
        self.assertEqual(self._ergebnis(web, 4, ids)["abbruch_grund"], "verletzung_hund")
        self.assertEqual(self._ergebnis(web, 7, ids)["disqualifiziert"], 1)
        self.assertEqual(self._ergebnis(web, 2, ids)[db.NOTIZ_SPALTEN[B]], "Gegenstand links hinten")

        # Nach dem Veröffentlichen wird in der Desktop-Datei Nr. 6 umbenannt: andere Person unter derselben Nummer.
        self.desktop.execute("UPDATE teilnehmer SET nachname = ? WHERE id = ?", ("Anders", self.d[6]))
        self.desktop.commit()
        vorher5 = dict(self._ergebnis(self.desktop, 5, self.d))

        # Zurückholen wie desktop_web.ergebnisse_aus_web_holen (ohne Qt)
        self._anmelden()
        liste = self.client.ergebnisse(schema)
        bericht = db.importiere_ergebnisse_aus_liste(self.desktop, liste)

        self.assertEqual(bericht.fehler, [])
        self.assertEqual(bericht.nicht_gefunden, [])
        self.assertEqual(bericht.ohne_startnummer_uebersprungen, [])
        # Nr. 6: abweichender Name -> nicht übernommen, im Bericht gemeldet
        self.assertEqual(len(bericht.abweichungen), 1)
        self.assertIn("Nr. 6", bericht.abweichungen[0])
        self.assertIn("Fiedler", bericht.abweichungen[0])
        self.assertIn("Anders", bericht.abweichungen[0])
        self.assertIsNone(self._ergebnis(self.desktop, 6, self.d).get("suche_flaechensuche"))
        # aktualisiert: nur Teilnehmer, bei denen sich in der Datei wirklich etwas geändert hat: Punkte
        # (1, 2), Status (3, 4, 7, 8). Nr. 5 ist im Web unverändert und zählt nicht mit.
        self.assertEqual(bericht.aktualisiert, 6)
        # UX-Test Web 19.11.2026 (E1, E2): Notiz von Nr. 2 übernommen; zugeordnet und ohne Änderung bleibt Nr. 5
        self.assertEqual(bericht.notizen_uebernommen, 1)
        self.assertEqual(bericht.unveraendert, 1)
        self.assertEqual(len(bericht.status_geaendert), 4)
        text = "\n".join(bericht.status_geaendert)
        self.assertIn("Nr. 3", text)
        self.assertIn("disqualifiziert → ohne Status", text)
        self.assertIn("Nr. 4", text)
        self.assertIn("Abbruch (Krankheit) → Abbruch (Verletzung Hund)", text)
        self.assertIn("Nr. 7", text)
        self.assertIn("Nr. 8", text)

        # Punkte, Status, Notiz in der Desktop-Datei
        e1 = self._ergebnis(self.desktop, 1, self.d)
        self.assertEqual((e1["suche_flaechensuche"], e1["anzeige_flaechensuche"]), (55, 35))
        e2 = self._ergebnis(self.desktop, 2, self.d)
        self.assertEqual((e2["suche_truemmerfeld"], e2["anzeige_truemmerfeld"]), (50, 30))
        self.assertEqual((e2["suche_behaeltnis"], e2["anzeige_behaeltnis"]), (20, 10))
        self.assertEqual(e2[db.NOTIZ_SPALTEN[B]], "Gegenstand links hinten")
        e3 = self._ergebnis(self.desktop, 3, self.d)
        self.assertFalse(e3["disqualifiziert"])
        e4 = self._ergebnis(self.desktop, 4, self.d)
        self.assertEqual((bool(e4["abbruch"]), e4["abbruch_grund"]), (True, "verletzung_hund"))
        self.assertTrue(self._ergebnis(self.desktop, 7, self.d)["disqualifiziert"])
        e8 = self._ergebnis(self.desktop, 8, self.d)
        self.assertEqual((bool(e8["abbruch"]), e8["abbruch_grund"]), (True, "krankheit"))
        # unverändert im Web: bleibt in der Desktop-Datei wie vorher (Punkte und Notiz)
        nachher5 = self._ergebnis(self.desktop, 5, self.d)
        for schluessel in ("suche_behaeltnis", "anzeige_behaeltnis", "disqualifiziert", "abbruch", "abbruch_grund",
                           db.NOTIZ_SPALTEN[B]):
            self.assertEqual(nachher5[schluessel], vorher5[schluessel], schluessel)
        self.assertEqual(nachher5[db.NOTIZ_SPALTEN[B]], "Gegenstand in der Ecke")

        # zweites Zurückholen ohne neue Web-Änderung: kein Statuswechsel mehr, nichts geht kaputt
        zweiter = db.importiere_ergebnisse_aus_liste(self.desktop, self.client.ergebnisse(schema))
        self.assertEqual((zweiter.status_geaendert, zweiter.fehler), ([], []))
        self.assertEqual(zweiter.aktualisiert, 0)  # nichts geändert -> nichts „aktualisiert“
        self.assertEqual(zweiter.unveraendert, 7)  # alle zugeordneten (Nr. 6 weicht ab und zählt nicht)
        self.assertEqual(zweiter.notizen_uebernommen, 0)

    def test_status_von_der_einzelseite_kommt_beim_zurueckholen_an(self):
        # UX-Test Web 19.11.2026 (D1): Disqualifiziert und Abbruch auch auf der Seite je Teilnehmer.
        termin, _hinweis = self._veroeffentlichen()
        schema = termin["schema_name"]
        ids = self._web_ids(schema)
        self._browser_anmelden()
        seite = self._formular(f"/teilnehmer/{ids[1]}")
        seite["abbruch"] = "krankheit"
        self._senden(f"/teilnehmer/{ids[1]}", seite)
        seite = self._formular(f"/teilnehmer/{ids[5]}")
        seite["dq"] = "1"
        self._senden(f"/teilnehmer/{ids[5]}", seite)

        self._anmelden()
        db.importiere_ergebnisse_aus_liste(self.desktop, self.client.ergebnisse(schema))
        e1 = self._ergebnis(self.desktop, 1, self.d)
        self.assertEqual((bool(e1["abbruch"]), e1["abbruch_grund"]), (True, "krankheit"))
        self.assertTrue(self._ergebnis(self.desktop, 5, self.d)["disqualifiziert"])

    # -- 6. Sammel-PDF
    @unittest.skipUnless(importlib.util.find_spec("reportlab"), "reportlab nicht installiert")
    def test_sammel_pdf_der_bewertungsboegen(self):
        termin, _hinweis = self._veroeffentlichen()
        self._im_web_erfassen(termin["schema_name"])
        antwort = self.browser.get("/ergebnisse/boegen.pdf")
        self.assertEqual(antwort.status_code, 200)
        self.assertEqual(antwort.mimetype, "application/pdf")
        self.assertTrue(antwort.data.startswith(b"%PDF"))
        self.assertGreater(len(antwort.data), 1000)

    # -- 7. Absicherungen auf der Strecke
    def test_cookie_sitzung_allein_genuegt_auf_api_nicht(self):
        self._veroeffentlichen()
        self._browser_anmelden()
        self.assertEqual(self.browser.get("/api/termine").status_code, 401)
        self.assertEqual(self.browser.get("/ergebnisse").status_code, 200)  # die Sitzung selbst ist gültig

    def test_token_eines_geloeschten_kontos_wird_abgelehnt(self):
        konten = self.sim.verbindung()
        db.benutzer_anlegen(konten, "zweitadmin", "zweitadmin-pw-123", ist_admin=True)
        client = web_sync.WebClient(self.server.adresse, self.fingerabdruck)
        client.anmelden("zweitadmin", "zweitadmin-pw-123")
        self.assertEqual(client.termine(), [])
        db.benutzer_loeschen(konten, "zweitadmin")
        with self.assertRaises(web_sync.AnmeldeFehler) as fehler:
            client.termine()
        self.assertEqual(fehler.exception.status, 401)

    def test_anfrage_ohne_token_ergibt_401(self):
        with self.assertRaises(web_sync.AnmeldeFehler) as fehler:
            web_sync.WebClient(self.server.adresse, self.fingerabdruck).termine()
        self.assertEqual(fehler.exception.status, 401)

    def test_ohne_https_lehnt_der_client_ab(self):
        for adresse in ("http://127.0.0.1:1", self.server.adresse.replace("https://", "http://")):
            with self.subTest(adresse=adresse):
                with self.assertRaises(web_sync.AdressFehler):
                    web_sync.WebClient(adresse, self.fingerabdruck)
                with self.assertRaises(web_sync.AdressFehler):
                    web_sync.hole_fingerabdruck(adresse)
        self.assertEqual(self.wsgi.anfragen, [])


if __name__ == "__main__":
    unittest.main()
