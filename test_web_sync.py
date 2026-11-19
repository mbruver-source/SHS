"""Tests für web_sync.py (Netzwerk-Client der Web-Verbindung) und web_tresor.py - ohne Qt.

Gegen einen lokalen HTTPS-Server (127.0.0.1) mit einem zur Testlaufzeit erzeugten selbstsignierten
Zertifikat; keine Zugriffe nach außen. Ohne `cryptography` und ohne `openssl`-Programm entfällt der
Server-Teil (Überspringen mit Begründung)."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import socket
import ssl
import subprocess
import sqlite3
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import web_sync
import web_tresor


def _zertifikat_erzeugen(ordner: Path) -> tuple[str, str]:
    """Selbstsigniertes Zertifikat (cert, key) für 127.0.0.1; cryptography, sonst die openssl-Kommandozeile."""
    cert, key = str(ordner / "cert.pem"), str(ordner / "key.pem")
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID
        import ipaddress

        schluessel = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "shs-test")])
        jetzt = datetime.datetime.now(datetime.timezone.utc)
        zert = (
            x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(schluessel.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(jetzt - datetime.timedelta(days=1)).not_valid_after(jetzt + datetime.timedelta(days=2))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), False)
            .sign(schluessel, hashes.SHA256())
        )
        Path(cert).write_bytes(zert.public_bytes(serialization.Encoding.PEM))
        Path(key).write_bytes(schluessel.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
        return cert, key
    except ImportError:
        pass
    if shutil.which("openssl") is None:
        raise unittest.SkipTest("weder cryptography noch openssl verfügbar - kein Testzertifikat erzeugbar")
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", key, "-out", cert,
         "-days", "2", "-subj", "/CN=shs-test"],
        check=True, capture_output=True,
    )
    return cert, key


def _fingerabdruck_der_datei(cert: str) -> str:
    der = ssl.PEM_cert_to_DER_cert(Path(cert).read_text())
    return hashlib.sha256(der).hexdigest()


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # noqa: D401 - still
        pass

    def _bearbeiten(self):
        laenge = int(self.headers.get("Content-Length") or 0)
        koerper = self.rfile.read(laenge) if laenge else b""
        zustand = self.server.zustand
        zustand["anfragen"].append((self.command, self.path, dict(self.headers), koerper))
        regel = zustand["antworten"].get((self.command, self.path))
        if regel is None:
            status, daten, header = 404, {"fehler": "unbekannt"}, {}
        else:
            status, daten, header = regel() if callable(regel) else regel
        roh = daten if isinstance(daten, bytes) else json.dumps(daten).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(roh)))
        for k, v in header.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(roh)

    do_GET = do_POST = _bearbeiten


class _LeiserServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):  # abgebrochene Testverbindungen nicht ausgeben
        pass


class _Server:
    def __init__(self, cert: str, key: str):
        self.httpd = _LeiserServer(("127.0.0.1", 0), _Handler)
        self.httpd.daemon_threads = True
        self.httpd.zustand = {"anfragen": [], "antworten": {}}
        kontext = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        kontext.load_cert_chain(cert, key)
        self.httpd.socket = kontext.wrap_socket(self.httpd.socket, server_side=True)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.adresse = f"https://127.0.0.1:{self.httpd.server_address[1]}"

    @property
    def anfragen(self):
        return self.httpd.zustand["anfragen"]

    @property
    def antworten(self):
        return self.httpd.zustand["antworten"]

    def stoppen(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class TestAdresse(unittest.TestCase):
    def test_https_wird_normalisiert(self):
        self.assertEqual(web_sync.adresse_pruefen("https://Shs.Example.org/"), "https://shs.example.org")
        self.assertEqual(web_sync.adresse_pruefen("shs.example.org"), "https://shs.example.org")
        self.assertEqual(web_sync.adresse_pruefen(" https://shs.example.org:8443 "), "https://shs.example.org:8443")
        self.assertEqual(web_sync.adresse_pruefen("https://shs.example.org:443"), "https://shs.example.org")
        self.assertEqual(web_sync.adresse_pruefen("https://[::1]:8443"), "https://[::1]:8443")

    def test_http_wird_abgelehnt(self):
        with self.assertRaises(web_sync.AdressFehler) as fehler:
            web_sync.adresse_pruefen("http://shs.example.org")
        self.assertIn("https://", fehler.exception.meldung)

    def test_weitere_ungueltige_adressen(self):
        for text in ("", "   ", "ftp://x.example.org", "https://", "https://user:pw@x.example.org",
                     "https://x.example.org/pfad", "https://x.example.org/?a=1", "https://x.example.org:abc"):
            with self.subTest(text=text), self.assertRaises(web_sync.AdressFehler):
                web_sync.adresse_pruefen(text)

    def test_client_lehnt_http_ab(self):
        with self.assertRaises(web_sync.AdressFehler):
            web_sync.WebClient("http://127.0.0.1:1", "ab" * 32)

    def test_client_ohne_fingerabdruck_nicht_erlaubt(self):
        with self.assertRaises(ValueError):
            web_sync.WebClient("https://127.0.0.1:1", "")


class TestFingerabdruck(unittest.TestCase):
    def test_normalisieren(self):
        hexwert = "0123456789abcdef" * 4
        self.assertEqual(web_sync.fingerabdruck_normalisieren(hexwert.upper()), hexwert)
        mit_doppelpunkt = ":".join(hexwert[i:i + 2] for i in range(0, 64, 2))
        self.assertEqual(web_sync.fingerabdruck_normalisieren(mit_doppelpunkt), hexwert)
        self.assertIsNone(web_sync.fingerabdruck_normalisieren("zu kurz"))
        self.assertIsNone(web_sync.fingerabdruck_normalisieren(None))
        self.assertIsNone(web_sync.fingerabdruck_normalisieren("g" * 64))

    def test_anzeige_in_zweierbloecken(self):
        anzeige = web_sync.fingerabdruck_anzeige("0123456789abcdef" * 4)
        zeilen = anzeige.split("\n")
        self.assertEqual(len(zeilen), 4)
        self.assertTrue(zeilen[0].startswith("01:23:45:67"))
        self.assertEqual(zeilen[0].count(":"), 7)
        self.assertEqual(anzeige.replace(":", "").replace("\n", ""), ("0123456789abcdef" * 4).upper())


class TestMultipart(unittest.TestCase):
    def test_aufbau(self):
        inhalt = b"SQLite format 3\x00\r\n--fake\r\n"
        body, typ = web_sync.baue_multipart("sqlite_datei", 'ev"il\r\nname.sqlite', inhalt)
        grenze = typ.split("boundary=")[1]
        self.assertTrue(typ.startswith("multipart/form-data; "))
        self.assertTrue(body.startswith(f"--{grenze}\r\n".encode()))
        self.assertTrue(body.endswith(f"\r\n--{grenze}--\r\n".encode()))
        self.assertIn(inhalt, body)
        kopf = body.split(b"\r\n\r\n", 1)[0].decode()
        self.assertIn('name="sqlite_datei"', kopf)
        self.assertEqual(kopf.count('"'), 4, "Anführungszeichen im Dateinamen müssen entfernt sein")
        self.assertNotIn("\n\n", kopf)

    def test_grenze_ist_zufaellig(self):
        self.assertNotEqual(web_sync.baue_multipart("f", "a", b"x")[1], web_sync.baue_multipart("f", "a", b"x")[1])


class TestTresorOhneWindows(unittest.TestCase):
    def test_nicht_windows_speichert_nichts(self):
        with mock.patch.object(web_tresor, "_ist_windows", lambda: False):
            self.assertFalse(web_tresor.verfuegbar())
            self.assertFalse(web_tresor.passwort_speichern("https://x.example.org", "u", "geheim"))
            self.assertIsNone(web_tresor.passwort_lesen("https://x.example.org"))
            self.assertFalse(web_tresor.passwort_loeschen("https://x.example.org"))

    def test_zielname(self):
        self.assertEqual(web_tresor.ziel_name("https://x.example.org"), "SHS-Pruefungsprogramm/Web:https://x.example.org")

    @unittest.skipUnless(web_tresor._ist_windows() and os.environ.get("SHS_TEST_TRESOR") == "1",
                         "schreibt in den echten Windows-Tresor: nur unter Windows mit SHS_TEST_TRESOR=1")
    def test_tresor_rundlauf_unter_windows(self):
        adresse = "https://tresor-test.invalid:65000"
        try:
            if not web_tresor.passwort_speichern(adresse, "tester", "Pä55wort-üß"):
                self.skipTest("Anmeldeinformationsverwaltung in dieser Sitzung nicht beschreibbar")
            self.assertEqual(web_tresor.passwort_lesen(adresse), "Pä55wort-üß")
            self.assertTrue(web_tresor.passwort_speichern(adresse, "tester", "anders"))
            self.assertEqual(web_tresor.passwort_lesen(adresse), "anders")
        finally:
            self.assertTrue(web_tresor.passwort_loeschen(adresse))
        self.assertIsNone(web_tresor.passwort_lesen(adresse))
        self.assertTrue(web_tresor.passwort_loeschen(adresse))  # nichts mehr da: weiterhin „in Ordnung“


class TestMitServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._ordner = tempfile.TemporaryDirectory()
        try:
            cls.cert, cls.key = _zertifikat_erzeugen(Path(cls._ordner.name))
        except unittest.SkipTest:
            cls._ordner.cleanup()
            raise
        cls.fingerabdruck = _fingerabdruck_der_datei(cls.cert)

    @classmethod
    def tearDownClass(cls):
        cls._ordner.cleanup()

    def setUp(self):
        self.server = _Server(self.cert, self.key)
        self.addCleanup(self.server.stoppen)
        self.client = web_sync.WebClient(self.server.adresse, self.fingerabdruck)

    def _anmelden(self):
        self.server.antworten[("POST", "/api/login")] = (200, {"token": "tok123", "gueltig_sekunden": 3600}, {})
        self.client.anmelden("admin", "geheim-pw")

    # -- Erstverbindung / Pinning
    def test_fingerabdruck_holen_ohne_etwas_zu_senden(self):
        self.assertEqual(web_sync.hole_fingerabdruck(self.server.adresse), self.fingerabdruck)
        self.assertEqual(self.server.anfragen, [], "Die Erstverbindung darf keine Anfrage senden")

    def test_pinning_stimmt_anmelden_und_listen(self):
        self._anmelden()
        self.assertEqual(self.client.gueltig_sekunden, 3600)
        login = self.server.anfragen[0]
        self.assertEqual(json.loads(login[3]), {"benutzername": "admin", "passwort": "geheim-pw"})
        self.assertNotIn("Authorization", login[2])
        self.server.antworten[("GET", "/api/termine")] = (200, {"termine": [
            {"schema_name": "termin_1", "verein": "V", "ort": "O", "datum": "2026-12-01", "anzahl_teilnehmer": 3},
            "kaputt", {"ohne": "schema"}]}, {})
        termine = self.client.termine()
        self.assertEqual([t["schema_name"] for t in termine], ["termin_1"])
        self.assertEqual(self.server.anfragen[1][2]["Authorization"], "Bearer tok123")

    def test_pinning_abweichend_bricht_ab_und_sendet_nichts(self):
        falsch = web_sync.WebClient(self.server.adresse, "00" * 32)
        with self.assertRaises(web_sync.ZertifikatFehler) as fehler:
            falsch.anmelden("admin", "geheim-pw")
        self.assertEqual(fehler.exception.erhalten, self.fingerabdruck)
        self.assertIn("NICHTS gesendet", fehler.exception.meldung)
        self.assertNotIn("geheim-pw", fehler.exception.meldung)
        self.assertEqual(self.server.anfragen, [], "Bei abweichendem Fingerabdruck darf nichts gesendet werden")

    # -- Veröffentlichen / Ergebnisse
    def test_veroeffentlichen_sendet_multipart_und_liefert_hinweis(self):
        self._anmelden()
        pfad = Path(self._ordner.name) / "termin.sqlite"
        verbindung = sqlite3.connect(pfad)
        verbindung.execute("CREATE TABLE t (a)")
        verbindung.commit()
        verbindung.close()
        self.server.antworten[("POST", "/api/termine")] = (201, {
            "termin": {"schema_name": "termin_7", "verein": "V", "ort": "O", "datum": "2026-12-01", "anzahl_teilnehmer": 2},
            "dublette_hinweis": "Ein Termin am selben Datum existiert schon."}, {})
        termin, hinweis = self.client.veroeffentlichen(str(pfad))
        self.assertEqual(termin["schema_name"], "termin_7")
        self.assertIn("selben Datum", hinweis)
        _methode, _pfad, kopf, koerper = self.server.anfragen[-1]
        self.assertTrue(kopf["Content-Type"].startswith("multipart/form-data; boundary="))
        self.assertIn(b'name="sqlite_datei"', koerper)
        self.assertIn(pfad.read_bytes(), koerper)

    def test_veroeffentlichen_ohne_hinweis(self):
        self._anmelden()
        pfad = Path(self._ordner.name) / "x.sqlite"
        pfad.write_bytes(b"daten")
        self.server.antworten[("POST", "/api/termine")] = (201, {"termin": {"schema_name": "termin_8"}, "dublette_hinweis": None}, {})
        self.assertEqual(self.client.veroeffentlichen(str(pfad))[1], None)

    def test_veroeffentlichen_fehlende_datei(self):
        self._anmelden()
        with self.assertRaises(web_sync.WebFehler):
            self.client.veroeffentlichen(str(Path(self._ordner.name) / "gibt-es-nicht.sqlite"))

    def test_ergebnisse(self):
        self._anmelden()
        self.server.antworten[("GET", "/api/termine/termin_7/ergebnisse")] = (200, {"teilnehmer": [{"startnummer": 1, "ergebnis": None}]}, {})
        self.assertEqual(self.client.ergebnisse("termin_7"), [{"startnummer": 1, "ergebnis": None}])
        with self.assertRaises(web_sync.WebFehler):
            self.client.ergebnisse("../etc")

    def test_ergebnisse_im_format_des_servers_laufen_durch_den_import(self):
        from db import add_teilnehmer, get_ergebnis, importiere_ergebnisse_aus_liste, init_db, list_teilnehmer, NeuerTeilnehmer

        self._anmelden()
        pfad = Path(self._ordner.name) / "ziel.sqlite"
        conn = init_db(str(pfad))
        self.addCleanup(conn.close)
        ziel_id = add_teilnehmer(conn, NeuerTeilnehmer(
            nachname="Muster", vorname="Anna", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Flächensuche", startnummer=3))
        antwort = {"teilnehmer": [{
            "startnummer": 3, "nachname": "Muster", "vorname": "Anna", "rufname_hund": "Rex", "art": "ED",
            "stufe": 1, "disziplin": "Flächensuche",
            "ergebnis": {"teilnehmer_id": 77, "suche_truemmerfeld": None, "anzeige_truemmerfeld": None,
                         "suche_flaechensuche": 50, "anzeige_flaechensuche": 30, "suche_behaeltnis": None,
                         "anzeige_behaeltnis": None, "disqualifiziert": 0, "abbruch": 0, "abbruch_grund": None,
                         "stechen_sieger": 0}}, {
            "startnummer": None, "nachname": "Ohne", "vorname": "Nummer", "rufname_hund": "X", "art": "DK",
            "stufe": 2, "disziplin": None, "ergebnis": None}]}
        self.server.antworten[("GET", "/api/termine/termin_7/ergebnisse")] = (200, antwort, {})
        liste = self.client.ergebnisse("termin_7")
        self.assertEqual(set(liste[0]), set(web_sync._TEILNEHMER_FELDER))
        bericht = importiere_ergebnisse_aus_liste(conn, liste)
        self.assertEqual((bericht.aktualisiert, bericht.fehler, bericht.abweichungen), (1, [], []))
        self.assertEqual(bericht.ohne_startnummer_uebersprungen, ["Ohne, Nummer"])
        ergebnis = get_ergebnis(conn, ziel_id)
        self.assertEqual((ergebnis["suche_flaechensuche"], ergebnis["anzeige_flaechensuche"]), (50, 30))
        self.assertEqual(len(list_teilnehmer(conn)), 1)

    def test_adapter_laesst_fremdes_unveraendert(self):
        self.assertEqual(web_sync.teilnehmer_aus_antwort("kaputt"), "kaputt")
        self.assertEqual(web_sync.teilnehmer_aus_antwort({"startnummer": 1, "extra": 2}), {"startnummer": 1})

    def test_ergebnisse_falsches_format(self):
        self._anmelden()
        self.server.antworten[("GET", "/api/termine/termin_7/ergebnisse")] = (200, {"teilnehmer": "nein"}, {})
        with self.assertRaises(web_sync.WebFehler):
            self.client.ergebnisse("termin_7")

    # -- Fehlerklassifizierung
    def test_login_fehlerstatus(self):
        faelle = [
            (401, {"fehler": "Anmeldung falsch"}, {}, web_sync.AnmeldeFehler, "Anmeldung falsch"),
            (403, {"fehler": "kein Admin"}, {}, web_sync.AnmeldeFehler, "kein Admin"),
            (429, {"fehler": "x"}, {"Retry-After": "42"}, web_sync.AnmeldeFehler, "42 Sekunden"),
            (500, {"fehler": "kaputt"}, {}, web_sync.ServerFehler, "kaputt"),
            (404, {}, {}, web_sync.ServerFehler, "404"),
            (302, {}, {"Location": "http://anders.example.org/"}, web_sync.WebFehler, "weitergeleitet"),
        ]
        for status, daten, header, klasse, text in faelle:
            with self.subTest(status=status):
                self.server.antworten[("POST", "/api/login")] = (status, daten, header)
                with self.assertRaises(klasse) as fehler:
                    self.client.anmelden("admin", "pw-geheim")
                self.assertIn(text, fehler.exception.meldung)
                self.assertNotIn("pw-geheim", fehler.exception.meldung)
        self.server.antworten[("POST", "/api/login")] = (429, {}, {"Retry-After": "7"})
        with self.assertRaises(web_sync.AnmeldeFehler) as fehler:
            self.client.anmelden("a", "b")
        self.assertEqual(fehler.exception.status, 429)

    def test_antwort_kein_json(self):
        self.server.antworten[("POST", "/api/login")] = (200, b"<html>kein json</html>", {})
        with self.assertRaises(web_sync.WebFehler) as fehler:
            self.client.anmelden("a", "b")
        self.assertIn("unerwartetes Format", fehler.exception.meldung)

    def test_login_ohne_token(self):
        self.server.antworten[("POST", "/api/login")] = (200, {"gueltig_sekunden": 5}, {})
        with self.assertRaises(web_sync.WebFehler):
            self.client.anmelden("a", "b")

    def test_zeitueberschreitung(self):
        def langsam():
            import time
            time.sleep(1.5)
            return 200, {"token": "t"}, {}

        self.server.antworten[("POST", "/api/login")] = langsam
        with mock.patch.object(web_sync, "ZEITGRENZE_SEKUNDEN", 0.3):
            with self.assertRaises(web_sync.WebFehler) as fehler:
                self.client.anmelden("a", "b")
        self.assertIn("nicht rechtzeitig", fehler.exception.meldung)


class TestVerbindungsfehler(unittest.TestCase):
    def test_nicht_erreichbar(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        with self.assertRaises(web_sync.WebFehler) as fehler:
            web_sync.hole_fingerabdruck(f"https://127.0.0.1:{port}", zeitgrenze=2)
        self.assertNotIsInstance(fehler.exception, web_sync.ZertifikatFehler)

    def test_server_ohne_tls(self):
        class Klartext(BaseHTTPRequestHandler):
            def do_GET(self):  # pragma: no cover - wird nie erreicht
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args):
                pass

        httpd = HTTPServer(("127.0.0.1", 0), Klartext)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            with self.assertRaises(web_sync.WebFehler) as fehler:
                web_sync.hole_fingerabdruck(f"https://127.0.0.1:{httpd.server_address[1]}", zeitgrenze=3)
            self.assertNotIsInstance(fehler.exception, web_sync.ZertifikatFehler)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_uebersetzung(self):
        self.assertIn("nicht rechtzeitig", web_sync._uebersetze_fehler(TimeoutError()).meldung)
        self.assertIn("TLS", web_sync._uebersetze_fehler(ssl.SSLError("x")).meldung)
        self.assertIn("Servername", web_sync._uebersetze_fehler(socket.gaierror()).meldung)
        self.assertIn("nimmt keine Verbindung", web_sync._uebersetze_fehler(ConnectionRefusedError()).meldung)
        self.assertIn("Keine Verbindung", web_sync._uebersetze_fehler(OSError("x")).meldung)
        self.assertIn("nicht gelesen", web_sync._uebersetze_fehler(ValueError("x")).meldung)


if __name__ == "__main__":
    unittest.main()
