"""Tests für die Datensicherung (Export/Import als ZIP, siehe
db_sicherung.py). Reine Logik-/Dateisystem-Tests ohne Qt, im selben Stil wie test_db.py
(unittest, tempfile.TemporaryDirectory) - decken sowohl den unverschlüsselten Weg
(Standard-`zipfile`) als auch den AES-256-verschlüsselten Weg (`pyzipper`) ab."""

import os
import pathlib
import tempfile
import unittest
import zipfile
import zlib
from unittest.mock import patch

import pyzipper

from db import (
    NeuerTeilnehmer,
    add_teilnehmer,
    init_db,
    list_teilnehmer,
    set_veranstaltung,
)
from db_sicherung import (
    PasswortFalschError,
    TeilweiseWiederhergestelltError,
    _ist_sicherer_dateiname,
    eindeutigen_dateinamen_finden,
    sicherung_erstellen,
    sicherung_inhalt,
    sicherung_wiederherstellen,
)


def _termin_anlegen(ordner: pathlib.Path, dateiname: str, verein: str = "Testverein") -> pathlib.Path:
    """Legt eine echte, initialisierte Termin-Datei mit einem Teilnehmer an - für die
    Backup-Funktionen genügt eine gültige .sqlite-Datei, der genaue Inhalt spielt keine
    Rolle, nur dass sie existiert."""
    pfad = ordner / dateiname
    conn = init_db(str(pfad))
    set_veranstaltung(conn, verein=verein, datum="2026-09-19")
    add_teilnehmer(conn, NeuerTeilnehmer(
        nachname="Muster", vorname="Max", rufname_hund="Bello", art="ED", stufe=1, disziplin="Flächensuche"))
    conn.close()
    return pfad


def _beschaedigtes_zip_schreiben(zip_pfad: str) -> None:
    """Schreibt ein ZIP mit einem unkomprimierten Eintrag und verändert danach ein Byte
    seines Inhalts - das ZIP bleibt lesbar, der Eintrag scheitert an der Prüfsumme."""
    inhalt = b"SQLite format 3\0" + b"x" * 100
    with zipfile.ZipFile(zip_pfad, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("a.sqlite", inhalt)
    daten = bytearray(pathlib.Path(zip_pfad).read_bytes())
    stelle = daten.index(inhalt) + 50
    daten[stelle] ^= 0xFF
    pathlib.Path(zip_pfad).write_bytes(bytes(daten))


class TestSicherungErstellen(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        basis = pathlib.Path(self._tmpdir.name)
        self.ordner = basis / "termine"
        self.ordner.mkdir()
        self.ziel_ordner = basis

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_zusaetzlicher_termin_ausserhalb_wird_mitgesichert(self):
        """Desktop-Prüfung 14.10.2026, Teil 7 Nr. 1: der geöffnete Termin vom USB-Stick;
        ein gleichnamiger Termin im Ordner bleibt erhalten, derselbe nicht doppelt."""
        _termin_anlegen(self.ordner, "a.sqlite")
        stick = self.ziel_ordner / "stick"
        stick.mkdir()
        _termin_anlegen(stick, "a.sqlite")
        _termin_anlegen(stick, "b.sqlite")
        ziel = str(self.ziel_ordner / "sicherung.zip")

        anzahl = sicherung_erstellen(
            ziel, ordner=self.ordner,
            zusaetzliche=[str(stick / "a.sqlite"), str(stick / "b.sqlite"), str(self.ordner / "a.sqlite")],
        )

        self.assertEqual(anzahl, 3)
        with zipfile.ZipFile(ziel) as zf:
            self.assertEqual(sorted(zf.namelist()), ["a (2).sqlite", "a.sqlite", "b.sqlite"])

    def test_zusaetzlicher_termin_bekommt_wiederherstellbaren_namen(self):
        """Verifikation A11: andere Endung bzw. Gerätename -> Name, den das Wiederherstellen
        auch anbietet."""
        stick = self.ziel_ordner / "stick"
        stick.mkdir()
        _termin_anlegen(stick, "termin.db")
        _termin_anlegen(stick, "CON.x")
        ziel = str(self.ziel_ordner / "sicherung.zip")
        sicherung_erstellen(ziel, ordner=self.ordner,
                            zusaetzliche=[str(stick / "termin.db"), str(stick / "CON.x")])
        self.assertEqual(sicherung_inhalt(ziel), ["Termin.sqlite", "termin.db.sqlite"])

    def test_nur_zusaetzlicher_termin_bei_leerem_ordner(self):
        stick = self.ziel_ordner / "stick"
        stick.mkdir()
        _termin_anlegen(stick, "x.sqlite")
        ziel = str(self.ziel_ordner / "sicherung.zip")
        self.assertEqual(sicherung_erstellen(ziel, ordner=self.ordner, zusaetzliche=[str(stick / "x.sqlite")]), 1)

    def test_nicht_unterstuetztes_verfahren_wird_zu_valueerror(self):
        """Desktop-Prüfung 14.10.2026, Teil 7 Nr. 11: NotImplementedError beim Lesen eines
        Eintrags (fremdes Komprimierungsverfahren) ergibt eine verständliche Meldung."""
        _termin_anlegen(self.ordner, "a.sqlite")
        ziel = str(self.ziel_ordner / "sicherung.zip")
        sicherung_erstellen(ziel, ordner=self.ordner)

        def nicht_unterstuetzt(*_a, **_k):
            raise NotImplementedError("That compression method is not supported")

        with patch.object(pyzipper.AESZipFile, "open", nicht_unterstuetzt):  # seit D-3 wird über open gelesen
            with self.assertRaisesRegex(ValueError, "nicht unterstützt"):
                sicherung_inhalt(ziel)

    def test_ohne_passwort_erzeugt_normales_lesbares_zip(self):
        _termin_anlegen(self.ordner, "a.sqlite")
        _termin_anlegen(self.ordner, "b.sqlite")
        ziel = str(self.ziel_ordner / "sicherung.zip")

        anzahl = sicherung_erstellen(ziel, ordner=self.ordner)

        self.assertEqual(anzahl, 2)
        with zipfile.ZipFile(ziel) as zf:
            self.assertEqual(sorted(zf.namelist()), ["a.sqlite", "b.sqlite"])

    def test_mit_passwort_erzeugt_verschluesseltes_zip(self):
        _termin_anlegen(self.ordner, "a.sqlite")
        ziel = str(self.ziel_ordner / "sicherung.zip")

        sicherung_erstellen(ziel, passwort="geheim123", ordner=self.ordner)

        # Ohne Passwort ist der Inhalt nicht lesbar (Datei ist verschlüsselt).
        with pyzipper.AESZipFile(ziel) as zf:
            with self.assertRaises(RuntimeError):
                zf.read("a.sqlite")

        # Mit dem richtigen Passwort schon.
        with pyzipper.AESZipFile(ziel) as zf:
            zf.setpassword(b"geheim123")
            daten = zf.read("a.sqlite")
        self.assertGreater(len(daten), 0)

    def test_nur_ausgewaehlte_dateien(self):
        _termin_anlegen(self.ordner, "a.sqlite")
        _termin_anlegen(self.ordner, "b.sqlite")
        ziel = str(self.ziel_ordner / "sicherung.zip")

        anzahl = sicherung_erstellen(ziel, nur_dateien=["a.sqlite"], ordner=self.ordner)

        self.assertEqual(anzahl, 1)
        with zipfile.ZipFile(ziel) as zf:
            self.assertEqual(zf.namelist(), ["a.sqlite"])

    def test_leerer_ordner_wirft_value_error(self):
        ziel = str(self.ziel_ordner / "sicherung.zip")
        with self.assertRaises(ValueError):
            sicherung_erstellen(ziel, ordner=self.ordner)

    def test_hinterlaesst_keine_temporaeren_dateien(self):
        _termin_anlegen(self.ordner, "a.sqlite")
        sicherung_erstellen(str(self.ziel_ordner / "sicherung.zip"), ordner=self.ordner)
        self.assertEqual(sorted(p.name for p in self.ziel_ordner.iterdir()), ["sicherung.zip", "termine"])

    def test_abbruch_laesst_vorhandene_sicherung_unveraendert(self):
        """QS-Prüfung 07.10.2026, Befund 2: Scheitert das Schreiben mittendrin (z. B.
        voller USB-Stick), bleibt eine gleichnamige ältere Sicherung byte-gleich erhalten,
        statt durch ein gültig aussehendes, unvollständiges ZIP ersetzt zu werden. Ohne
        Passwort schreibt zipfile, mit Passwort pyzipper - beide Wege werden geprüft."""
        _termin_anlegen(self.ordner, "a.sqlite")
        _termin_anlegen(self.ordner, "b.sqlite")
        ziel = self.ziel_ordner / "sicherung.zip"

        for passwort, zip_klasse in ((None, zipfile.ZipFile), ("geheim123", pyzipper.zipfile.ZipFile)):
            with self.subTest(passwort=passwort):
                sicherung_erstellen(str(ziel), passwort=passwort, ordner=self.ordner)
                vorher = ziel.read_bytes()

                original_write = zip_klasse.writestr
                aufrufe = []

                def write_mit_fehler(zf, *args, _original=original_write, _aufrufe=aufrufe, **kwargs):
                    _aufrufe.append(args)
                    if len(_aufrufe) == 2:
                        raise OSError(28, "No space left on device")
                    return _original(zf, *args, **kwargs)

                # Gesichert wird als Momentaufnahme über writestr (offene Punkte O1).
                with patch.object(zip_klasse, "writestr", write_mit_fehler):
                    with self.assertRaises(OSError):
                        sicherung_erstellen(str(ziel), passwort=passwort, ordner=self.ordner)

                self.assertEqual(len(aufrufe), 2)
                self.assertEqual(ziel.read_bytes(), vorher)
                self.assertEqual(sorted(p.name for p in self.ziel_ordner.iterdir()), ["sicherung.zip", "termine"])


class TestSicherungMomentaufnahme(unittest.TestCase):
    """Offene Punkte O1 (Marco 18.10.2026): Termine kommen als stimmige Momentaufnahme ins
    ZIP; was sich so nicht lesen lässt, wird roh samt Rücksprung-Datei gesichert, ohne die
    Quelle anzufassen."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        basis = pathlib.Path(self._tmpdir.name)
        self.ordner = basis / "termine"
        self.ordner.mkdir()
        self.ziel = basis / "sicherung.zip"
        self.zurueck = basis / "zurueck"
        self.zurueck.mkdir()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _halb_geschrieben(self, pfad: pathlib.Path) -> None:
        """Absturz mitten im Speichern (Muster aus test_db): Journal bleibt liegen."""
        import subprocess
        import sys
        skript = (
            "import os, sqlite3, sys; c = sqlite3.connect(sys.argv[1]); "
            "c.execute(\"PRAGMA journal_mode=DELETE\"); c.execute('PRAGMA cache_size=2'); c.execute('BEGIN'); "
            "c.execute(\"UPDATE veranstaltung SET verein = 'halb'\"); "
            "c.execute(\"INSERT INTO teilnehmer (nachname, vorname, rufname_hund, art, stufe) "
            "SELECT 'x', 'y', 'z', 'DK', 1 FROM (WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM n "
            "WHERE i < 3000) SELECT i FROM n)\"); os._exit(0)"
        )
        subprocess.run([sys.executable, "-c", skript, str(pfad)], check=False)
        if not os.path.exists(f"{pfad}-journal"):
            self.skipTest("kein Journal entstanden (Cache groß genug)")

    def _aus_zip_lesen(self, name: str) -> tuple[str, int, str]:
        """Verein, Teilnehmerzahl und quick_check der Datei `name` aus der Sicherung."""
        import sqlite3
        from contextlib import closing
        datei = self.zurueck / name
        with zipfile.ZipFile(self.ziel) as zf:
            datei.write_bytes(zf.read(name))
        with closing(sqlite3.connect(datei)) as conn:
            return (
                conn.execute("SELECT verein FROM veranstaltung").fetchone()[0],
                conn.execute("SELECT COUNT(*) FROM teilnehmer").fetchone()[0],
                conn.execute("PRAGMA quick_check").fetchone()[0],
            )

    def test_offene_fremde_transaktion_ist_nicht_in_der_sicherung(self):
        import sqlite3
        from contextlib import closing
        pfad = _termin_anlegen(self.ordner, "a.sqlite")
        with closing(sqlite3.connect(pfad)) as andere:
            andere.execute("BEGIN")
            andere.execute("UPDATE veranstaltung SET verein = 'ungespeichert'")
            roh = []
            self.assertEqual(sicherung_erstellen(str(self.ziel), ordner=self.ordner, roh_gesichert=roh), 1)
            andere.rollback()
        self.assertEqual(roh, [])
        self.assertEqual(self._aus_zip_lesen("a.sqlite"), ("Testverein", 1, "ok"))

    def test_liegengebliebenes_journal_wird_roh_mitgesichert_und_zurueckgeschrieben(self):
        from contextlib import closing
        from db import get_veranstaltung, termin_oeffnen
        pfad = _termin_anlegen(self.ordner, "a.sqlite")
        self._halb_geschrieben(pfad)
        quelle_vorher = pfad.read_bytes()
        journal_vorher = pathlib.Path(f"{pfad}-journal").read_bytes()

        roh = []
        sicherung_erstellen(str(self.ziel), ordner=self.ordner, roh_gesichert=roh)

        self.assertEqual(roh, ["a.sqlite"])
        with zipfile.ZipFile(self.ziel) as zf:
            self.assertEqual(sorted(zf.namelist()), ["a.sqlite", "a.sqlite-journal"])
        # Die Quelle bleibt unberührt (kein Zurückspielen beim Sichern).
        self.assertEqual(pfad.read_bytes(), quelle_vorher)
        self.assertEqual(pathlib.Path(f"{pfad}-journal").read_bytes(), journal_vorher)
        # Die Rücksprung-Datei erscheint nicht als eigener Termin ...
        self.assertEqual(sicherung_inhalt(str(self.ziel)), ["a.sqlite"])
        # ... wird aber mit zurückgeschrieben, sodass der letzte gespeicherte Stand gilt.
        geschrieben = sicherung_wiederherstellen(str(self.ziel), {"a.sqlite": "neu.sqlite"}, ordner=self.zurueck)
        self.assertEqual(geschrieben, ["neu.sqlite"])
        self.assertTrue((self.zurueck / "neu.sqlite-journal").exists())
        with closing(termin_oeffnen(str(self.zurueck / "neu.sqlite"))) as conn:
            self.assertEqual(get_veranstaltung(conn)["verein"], "Testverein")

    def test_journal_mit_verweis_in_der_sicherung_wird_abgelehnt(self):
        """Sicherheitskorrektur D-2: Eine Sicherung mit einem Journal mit Verweis auf eine weitere
        Datei wird abgelehnt, bevor ein Termin ersetzt ist; die weitere Datei bleibt unberührt."""
        from db_testhilfen import journal_mit_verweis_schreiben
        fremd = self.zurueck / "fremd.txt"
        fremd.write_bytes(b"erfundene Daten, keine Termin-Datei\n" * 20)
        pfad = _termin_anlegen(self.ordner, "a.sqlite")
        journal = journal_mit_verweis_schreiben(pfad, fremd)
        with zipfile.ZipFile(self.ziel, "w") as zf:
            zf.write(pfad, arcname="a.sqlite")
            zf.write(journal, arcname="a.sqlite-journal")
        with self.assertRaises(ValueError) as fehler:
            sicherung_wiederherstellen(str(self.ziel), {"a.sqlite": "neu.sqlite"}, ordner=self.zurueck)
        self.assertIn("Verweis", str(fehler.exception))
        self.assertEqual(sorted(p.name for p in self.zurueck.iterdir()), ["fremd.txt"])
        self.assertEqual(fremd.read_bytes(), b"erfundene Daten, keine Termin-Datei\n" * 20)

    def test_zip_eintrag_mit_zu_kleiner_groessenangabe_wird_nicht_entpackt(self):
        """Sicherheitskorrektur D-3: Das Lesen bricht ab, sobald mehr Bytes kommen als im ZIP-Verzeichnis
        stehen; der Arbeitsspeicher bleibt klein, auch wenn der Datenstrom sehr groß wäre."""
        import struct
        import tracemalloc

        echt, angeblich = 60 * 1024 * 1024, 1000
        for verfahren in (zipfile.ZIP_DEFLATED, zipfile.ZIP_LZMA, zipfile.ZIP_BZIP2):
            with self.subTest(verfahren=verfahren):
                with zipfile.ZipFile(self.ziel, "w", verfahren) as zf:
                    zf.writestr("termin.sqlite", bytes(echt))
                roh = bytearray(self.ziel.read_bytes())
                zentral = roh.rfind(b"PK\x01\x02")
                self.assertEqual(struct.unpack_from("<I", roh, zentral + 24)[0], echt)
                struct.pack_into("<I", roh, zentral + 24, angeblich)  # Zentralverzeichnis: unkomprimierte Größe
                lokal = roh.find(b"PK\x03\x04")
                struct.pack_into("<I", roh, lokal + 22, angeblich)  # lokaler Kopf
                self.ziel.write_bytes(bytes(roh))
                tracemalloc.start()
                try:
                    with self.assertRaises(ValueError) as fehler:
                        sicherung_inhalt(str(self.ziel))
                    spitze = tracemalloc.get_traced_memory()[1]
                finally:
                    tracemalloc.stop()
                # DEFLATE: zipfile kürzt selbst auf die angegebene Größe, die Prüfsumme schlägt an.
                self.assertRegex(str(fehler.exception), "größer als angegeben|beschädigt")
                self.assertLess(spitze, 30 * 1024 * 1024)

    def test_gefaehrliche_windows_dateinamen_werden_abgelehnt(self):
        """Sicherheitskorrektur D-4: Punkt oder Leerzeichen am Ende, hochgestellte Ziffern bei COM/LPT und
        CONIN$/CONOUT$ gelten als unsicher; normale Namen bleiben erlaubt."""
        hoch1, hoch2, hoch3 = chr(0xB9), chr(0xB2), chr(0xB3)
        for name in ("termin.sqlite.", "termin.sqlite ", f"COM{hoch1}.sqlite", f"lpt{hoch2}.sqlite",
                     f"COM{hoch3}", "CONIN$.sqlite", "conout$.sqlite", "CON.sqlite", "nul.sqlite"):
            with self.subTest(name=name):
                self.assertFalse(_ist_sicherer_dateiname(name))
        for name in ("termin.sqlite", "Termin (2).sqlite", "2026-11-20_Verein-Muster.sqlite", "COM10.sqlite",
                     "console.sqlite"):
            with self.subTest(name=name):
                self.assertTrue(_ist_sicherer_dateiname(name))

    def test_journal_mit_verweis_kommt_nicht_in_eine_neue_sicherung(self):
        """D-2: Ein solches Journal neben einer Termin-Datei wird nicht mitgesichert, damit die
        Sicherung wiederherstellbar bleibt; die Quelle bleibt unberührt."""
        from db_testhilfen import journal_mit_verweis_schreiben
        pfad = _termin_anlegen(self.ordner, "a.sqlite")
        journal = journal_mit_verweis_schreiben(pfad, self.zurueck / "fremd.txt")
        journal_vorher = journal.read_bytes()
        roh = []
        sicherung_erstellen(str(self.ziel), ordner=self.ordner, roh_gesichert=roh)
        with zipfile.ZipFile(self.ziel) as zf:
            self.assertEqual(zf.namelist(), ["a.sqlite"])
        self.assertEqual(journal.read_bytes(), journal_vorher)

    def test_gesperrte_datei_wird_ohne_endloses_warten_roh_gesichert(self):
        """Verifikation O1: backup() wartete bei einer exklusiv gesperrten Quelle endlos."""
        import sqlite3
        import time
        from contextlib import closing
        pfad = _termin_anlegen(self.ordner, "a.sqlite")
        with closing(sqlite3.connect(pfad)) as andere:
            andere.execute("BEGIN EXCLUSIVE")
            andere.execute("UPDATE veranstaltung SET verein = 'gesperrt'")
            roh = []
            beginn = time.monotonic()
            sicherung_erstellen(str(self.ziel), ordner=self.ordner, roh_gesichert=roh)
            dauer = time.monotonic() - beginn
            andere.rollback()
        self.assertEqual(roh, ["a.sqlite"])
        self.assertLess(dauer, 15)

    def test_scheitert_das_zurueckschreiben_des_journals_bleibt_kein_halber_termin(self):
        """QS 19.10.2026: Termin-Datei und Journal werden als Einheit ersetzt."""
        pfad = _termin_anlegen(self.ordner, "a.sqlite")
        self._halb_geschrieben(pfad)
        sicherung_erstellen(str(self.ziel), ordner=self.ordner)
        echt = os.replace
        aufrufe = []

        def journal_scheitert(quelle, ziel):
            aufrufe.append(ziel)
            if str(ziel).endswith("-journal") and not str(quelle).endswith(".alt"):
                raise PermissionError(13, "gesperrt", str(ziel))
            echt(quelle, ziel)

        with patch("db_sicherung.os.replace", journal_scheitert):
            with self.assertRaises(PermissionError):
                sicherung_wiederherstellen(str(self.ziel), {"a.sqlite": "neu.sqlite"}, ordner=self.zurueck)
        self.assertEqual([pathlib.Path(z).name for z in aufrufe], ["neu.sqlite", "neu.sqlite-journal"])
        self.assertEqual(list(self.zurueck.iterdir()), [])

    def test_scheitert_das_journal_kommen_alter_termin_und_altes_journal_zurueck(self):
        pfad = _termin_anlegen(self.ordner, "a.sqlite")
        self._halb_geschrieben(pfad)
        sicherung_erstellen(str(self.ziel), ordner=self.ordner)
        alt = _termin_anlegen(self.zurueck, "neu.sqlite", verein="Alter Stand")
        self._halb_geschrieben(alt)
        vorher = {p.name: p.read_bytes() for p in self.zurueck.iterdir()}
        echt = os.replace

        def journal_scheitert(quelle, ziel):
            if str(ziel).endswith("-journal") and str(quelle).endswith(".tmp"):
                raise PermissionError(13, "gesperrt", str(ziel))
            echt(quelle, ziel)

        with patch("db_sicherung.os.replace", journal_scheitert):
            with self.assertRaises(PermissionError):
                sicherung_wiederherstellen(str(self.ziel), {"a.sqlite": "neu.sqlite"}, ordner=self.zurueck)
        self.assertEqual({p.name: p.read_bytes() for p in self.zurueck.iterdir()}, vorher)

    def test_zweiter_termin_scheitert_erster_bleibt_vollstaendig(self):
        _termin_anlegen(self.ordner, "a.sqlite")
        _termin_anlegen(self.ordner, "b.sqlite")
        sicherung_erstellen(str(self.ziel), ordner=self.ordner)
        echt = os.replace

        def b_gesperrt(quelle, ziel):
            if pathlib.Path(ziel).name == "b.sqlite":
                raise PermissionError(13, "gesperrt", str(ziel))
            echt(quelle, ziel)

        with patch("db_sicherung.os.replace", b_gesperrt):
            with self.assertRaises(TeilweiseWiederhergestelltError) as kontext:
                sicherung_wiederherstellen(
                    str(self.ziel), {"a.sqlite": "a.sqlite", "b.sqlite": "b.sqlite"}, ordner=self.zurueck)
        self.assertEqual(kontext.exception.geschrieben, ["a.sqlite"])
        self.assertEqual(sorted(p.name for p in self.zurueck.iterdir()), ["a.sqlite"])

    def test_altes_journal_am_ziel_wird_beim_wiederherstellen_entfernt(self):
        """Marco 19.10.2026: SQLite würde ein altes Journal neben dem Ziel sonst auf die
        wiederhergestellte Datei zurückspielen."""
        from contextlib import closing
        from db import get_veranstaltung, termin_oeffnen
        _termin_anlegen(self.ordner, "a.sqlite")
        sicherung_erstellen(str(self.ziel), ordner=self.ordner)
        alt = _termin_anlegen(self.zurueck, "neu.sqlite")
        self._halb_geschrieben(alt)

        geschrieben = sicherung_wiederherstellen(str(self.ziel), {"a.sqlite": "neu.sqlite"}, ordner=self.zurueck)

        self.assertEqual(geschrieben, ["neu.sqlite"])
        self.assertEqual(sorted(p.name for p in self.zurueck.iterdir()), ["neu.sqlite"])
        with closing(termin_oeffnen(str(self.zurueck / "neu.sqlite"))) as conn:
            self.assertEqual(get_veranstaltung(conn)["verein"], "Testverein")

    def test_scheitert_das_ersetzen_bleibt_das_alte_journal_erhalten(self):
        _termin_anlegen(self.ordner, "a.sqlite")
        sicherung_erstellen(str(self.ziel), ordner=self.ordner)
        alt = _termin_anlegen(self.zurueck, "neu.sqlite")
        self._halb_geschrieben(alt)
        vorher = {p.name: p.read_bytes() for p in self.zurueck.iterdir()}
        echt = os.replace

        def termin_gesperrt(quelle, ziel):
            if pathlib.Path(ziel).name == "neu.sqlite":
                raise PermissionError(13, "gesperrt", str(ziel))
            echt(quelle, ziel)

        with patch("db_sicherung.os.replace", termin_gesperrt):
            with self.assertRaises(PermissionError):
                sicherung_wiederherstellen(str(self.ziel), {"a.sqlite": "neu.sqlite"}, ordner=self.zurueck)
        self.assertEqual({p.name: p.read_bytes() for p in self.zurueck.iterdir()}, vorher)

    def test_scheitert_auch_das_zurueckholen_kommen_die_uebrigen_zurueck(self):
        """Vor-Build-Verifikation 19.10.2026: Scheitert beim Rückweg das Zurückholen einer
        Datei, kommen die anderen trotzdem zurück, und gemeldet wird der ursprüngliche Fehler."""
        pfad = _termin_anlegen(self.ordner, "a.sqlite")
        self._halb_geschrieben(pfad)
        sicherung_erstellen(str(self.ziel), ordner=self.ordner)
        alt = _termin_anlegen(self.zurueck, "neu.sqlite", verein="Alter Stand")
        self._halb_geschrieben(alt)
        termin_vorher = alt.read_bytes()
        journal_vorher = pathlib.Path(f"{alt}-journal").read_bytes()
        echt = os.replace

        def scheitert(quelle, ziel):
            quelle, ziel = str(quelle), str(ziel)
            if ziel.endswith("-journal") and quelle.endswith(".tmp"):
                raise PermissionError(13, "Journal gesperrt", ziel)
            if ziel.endswith("neu.sqlite") and quelle.endswith(".alt"):
                raise PermissionError(13, "Zurückholen gesperrt", ziel)
            echt(quelle, ziel)

        with patch("db_sicherung.os.replace", scheitert):
            with self.assertRaises(PermissionError) as kontext:
                sicherung_wiederherstellen(str(self.ziel), {"a.sqlite": "neu.sqlite"}, ordner=self.zurueck)
        self.assertEqual(kontext.exception.strerror, "Journal gesperrt")
        self.assertEqual(pathlib.Path(f"{alt}-journal").read_bytes(), journal_vorher)
        beiseite = [p for p in self.zurueck.iterdir() if p.name.endswith(".alt")]
        self.assertEqual([p.read_bytes() for p in beiseite], [termin_vorher])

    def test_nicht_lesbare_datei_wird_roh_gesichert(self):
        _termin_anlegen(self.ordner, "gut.sqlite")
        kaputt = self.ordner / "kaputt.sqlite"
        kaputt.write_bytes(b"keine Datenbank " * 64)

        roh = []
        self.assertEqual(sicherung_erstellen(str(self.ziel), ordner=self.ordner, roh_gesichert=roh), 2)

        self.assertEqual(roh, ["kaputt.sqlite"])
        with zipfile.ZipFile(self.ziel) as zf:
            self.assertEqual(zf.read("kaputt.sqlite"), kaputt.read_bytes())
            self.assertEqual(sorted(zf.namelist()), ["gut.sqlite", "kaputt.sqlite"])
        self.assertEqual(self._aus_zip_lesen("gut.sqlite"), ("Testverein", 1, "ok"))


class TestSicherungInhalt(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        basis = pathlib.Path(self._tmpdir.name)
        self.ordner = basis / "termine"
        self.ordner.mkdir()
        self.zip_pfad = str(basis / "sicherung.zip")
        self._basis = basis

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_liefert_sortierte_dateinamen(self):
        _termin_anlegen(self.ordner, "b.sqlite")
        _termin_anlegen(self.ordner, "a.sqlite")
        sicherung_erstellen(self.zip_pfad, ordner=self.ordner)

        self.assertEqual(sicherung_inhalt(self.zip_pfad), ["a.sqlite", "b.sqlite"])

    def test_ignoriert_nicht_sqlite_eintraege(self):
        with zipfile.ZipFile(self.zip_pfad, "w") as zf:
            zf.writestr("liesmich.txt", "kein Termin")
            zf.writestr("a.sqlite", "fake-inhalt")
        self.assertEqual(sicherung_inhalt(self.zip_pfad), ["a.sqlite"])

    def test_ohne_termin_dateien_wirft_value_error(self):
        with zipfile.ZipFile(self.zip_pfad, "w") as zf:
            zf.writestr("liesmich.txt", "kein Termin")
        with self.assertRaises(ValueError):
            sicherung_inhalt(self.zip_pfad)

    def test_verschluesselt_ohne_passwortangabe_wirft_passwortfehler(self):
        _termin_anlegen(self.ordner, "a.sqlite")
        sicherung_erstellen(self.zip_pfad, passwort="geheim123", ordner=self.ordner)

        with self.assertRaises(PasswortFalschError):
            sicherung_inhalt(self.zip_pfad)

    def test_mit_falschem_passwort_wirft_passwortfehler(self):
        _termin_anlegen(self.ordner, "a.sqlite")
        sicherung_erstellen(self.zip_pfad, passwort="geheim123", ordner=self.ordner)

        with self.assertRaises(PasswortFalschError):
            sicherung_inhalt(self.zip_pfad, passwort="falsch")

    def test_mit_richtigem_passwort_liefert_dateinamen(self):
        _termin_anlegen(self.ordner, "a.sqlite")
        sicherung_erstellen(self.zip_pfad, passwort="geheim123", ordner=self.ordner)

        self.assertEqual(sicherung_inhalt(self.zip_pfad, passwort="geheim123"), ["a.sqlite"])

    def test_ungueltige_datei_wirft_value_error(self):
        kaputt = str(self._basis / "kaputt.zip")
        pathlib.Path(kaputt).write_text("das ist kein ZIP")
        with self.assertRaises(ValueError):
            sicherung_inhalt(kaputt)

    def test_pfad_traversal_eintraege_werden_herausgefiltert(self):
        """QS-Fund (19./20.09.): Ein ZIP-Eintragsname mit Pfadanteilen (z.B.
        '../../wichtig.sqlite') darf dem Nutzer gar nicht erst als vermeintlicher
        Termin zur Auswahl angeboten werden - sonst würde er unverändert als Zielname
        beim Wiederherstellen verwendet und könnte eine Datei außerhalb des
        Termine-Ordners schreiben."""
        with zipfile.ZipFile(self.zip_pfad, "w") as zf:
            zf.writestr("../../boese.sqlite", "fake-inhalt")
            zf.writestr("unterordner/auch_boese.sqlite", "fake-inhalt")
            zf.writestr("a.sqlite", "fake-inhalt")
        self.assertEqual(sicherung_inhalt(self.zip_pfad), ["a.sqlite"])

    def test_beschaedigter_eintrag_wird_als_beschaedigt_gemeldet(self):
        """Marco 07.10.2026 (Nachtrag zur Verifikation): Lässt sich das ZIP öffnen, ein
        Eintrag aber nicht fehlerfrei lesen, lautet die Meldung "beschädigt" statt "keine
        gültige ZIP-Datei" - beim Prüfen des Inhalts wie beim Wiederherstellen."""
        _beschaedigtes_zip_schreiben(self.zip_pfad)
        with self.assertRaisesRegex(ValueError, "beschädigt"):
            sicherung_inhalt(self.zip_pfad)
        with self.assertRaisesRegex(ValueError, "beschädigt"):
            sicherung_wiederherstellen(self.zip_pfad, {"a.sqlite": "a.sqlite"}, ordner=self.ordner)
        self.assertEqual(list(self.ordner.iterdir()), [])

    def test_entpackfehler_wird_als_beschaedigt_gemeldet(self):
        """Wie oben, für Fehler des Entpackers (zlib/lzma) statt der Prüfsumme."""
        _termin_anlegen(self.ordner, "a.sqlite")
        sicherung_erstellen(self.zip_pfad, ordner=self.ordner)
        with patch.object(pyzipper.AESZipFile, "open", side_effect=zlib.error("invalid stored block lengths")):
            with self.assertRaisesRegex(ValueError, "beschädigt"):
                sicherung_inhalt(self.zip_pfad)

    def test_zip_nur_mit_traversal_eintraegen_wirft_value_error(self):
        with zipfile.ZipFile(self.zip_pfad, "w") as zf:
            zf.writestr("../../boese.sqlite", "fake-inhalt")
        with self.assertRaises(ValueError):
            sicherung_inhalt(self.zip_pfad)


class TestSicherungWiederherstellen(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        basis = pathlib.Path(self._tmpdir.name)
        self.quell_ordner = basis / "quelle"
        self.quell_ordner.mkdir()
        self.ziel_ordner = basis / "ziel"
        self.ziel_ordner.mkdir()
        self.zip_pfad = str(basis / "sicherung.zip")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_stellt_dateien_im_zielordner_wieder_her(self):
        _termin_anlegen(self.quell_ordner, "a.sqlite")
        _termin_anlegen(self.quell_ordner, "b.sqlite")
        sicherung_erstellen(self.zip_pfad, ordner=self.quell_ordner)

        wiederhergestellt = sicherung_wiederherstellen(
            self.zip_pfad, {"a.sqlite": "a.sqlite", "b.sqlite": "b.sqlite"}, ordner=self.ziel_ordner
        )

        self.assertEqual(sorted(wiederhergestellt), ["a.sqlite", "b.sqlite"])
        self.assertTrue((self.ziel_ordner / "a.sqlite").exists())
        self.assertTrue((self.ziel_ordner / "b.sqlite").exists())

    def test_nicht_in_entscheidungen_enthaltene_datei_wird_uebersprungen(self):
        _termin_anlegen(self.quell_ordner, "a.sqlite")
        _termin_anlegen(self.quell_ordner, "b.sqlite")
        sicherung_erstellen(self.zip_pfad, ordner=self.quell_ordner)

        wiederhergestellt = sicherung_wiederherstellen(
            self.zip_pfad, {"a.sqlite": "a.sqlite"}, ordner=self.ziel_ordner
        )

        self.assertEqual(wiederhergestellt, ["a.sqlite"])
        self.assertFalse((self.ziel_ordner / "b.sqlite").exists())

    def test_kann_unter_abweichendem_zielnamen_importieren(self):
        """Entspricht der Option "als Kopie importieren" im Konflikt-Dialog (app.py) -
        die vorhandene Datei bleibt dabei unangetastet."""
        _termin_anlegen(self.quell_ordner, "a.sqlite")
        sicherung_erstellen(self.zip_pfad, ordner=self.quell_ordner)
        (self.ziel_ordner / "a.sqlite").write_text("bereits vorhanden")

        wiederhergestellt = sicherung_wiederherstellen(
            self.zip_pfad, {"a.sqlite": "a (2).sqlite"}, ordner=self.ziel_ordner
        )

        self.assertEqual(wiederhergestellt, ["a (2).sqlite"])
        self.assertTrue((self.ziel_ordner / "a (2).sqlite").exists())
        self.assertEqual((self.ziel_ordner / "a.sqlite").read_text(), "bereits vorhanden")

    def test_ueberschreibt_bei_gleichem_zielnamen(self):
        """Entspricht der Option "überschreiben" im Konflikt-Dialog (app.py)."""
        _termin_anlegen(self.quell_ordner, "a.sqlite")
        sicherung_erstellen(self.zip_pfad, ordner=self.quell_ordner)
        (self.ziel_ordner / "a.sqlite").write_text("alter Inhalt")

        sicherung_wiederherstellen(self.zip_pfad, {"a.sqlite": "a.sqlite"}, ordner=self.ziel_ordner)

        # Der wiederhergestellte Inhalt ist eine echte (binäre) SQLite-Datei - deshalb
        # bytes-weise lesen statt read_text() (das an den Binärdaten mit einem
        # UnicodeDecodeError scheitern würde).
        inhalt = (self.ziel_ordner / "a.sqlite").read_bytes()
        self.assertNotEqual(inhalt, b"alter Inhalt")
        self.assertTrue(inhalt.startswith(b"SQLite format 3"))

    def test_wiederherstellung_hinterlaesst_keine_temporaeren_dateien(self):
        """QS-Fund (19./20.09.): sicherung_wiederherstellen() schreibt jede Datei über
        eine temporäre Datei im selben Ordner (siehe Docstring dort) - nach einem
        erfolgreichen Lauf darf davon nichts mehr übrig bleiben, nur die echten
        Zieldateien."""
        _termin_anlegen(self.quell_ordner, "a.sqlite")
        sicherung_erstellen(self.zip_pfad, ordner=self.quell_ordner)

        sicherung_wiederherstellen(self.zip_pfad, {"a.sqlite": "a.sqlite"}, ordner=self.ziel_ordner)

        self.assertEqual([p.name for p in self.ziel_ordner.iterdir()], ["a.sqlite"])

    def test_unsicherer_zielname_wird_auch_hier_noch_abgelehnt(self):
        """QS-Fund (19./20.09., Path Traversal): sicherung_inhalt() filtert unsichere
        Namen zwar schon vorher heraus (siehe dortigen Test), aber
        sicherung_wiederherstellen() verlässt sich NICHT darauf, dass jeder Aufrufer das
        auch vorschaltet - eine zweite, unabhängige Prüfung hier verhindert, dass ein
        Ziel-Dateiname mit Pfadanteilen (z.B. aus versehentlich unvalidierten
        `entscheidungen`) tatsächlich zu einem Schreibversuch außerhalb des Zielordners
        führt. Simuliert direkt über die `entscheidungen`-Parameter, unabhängig davon,
        wie ein Aufrufer an so einen Namen gekommen wäre."""
        with zipfile.ZipFile(self.zip_pfad, "w") as zf:
            zf.writestr("boese.sqlite", "fake-inhalt")

        with self.assertRaises(ValueError):
            sicherung_wiederherstellen(
                self.zip_pfad, {"boese.sqlite": "../boese.sqlite"}, ordner=self.ziel_ordner
            )
        # Nichts außerhalb des Zielordners geschrieben, und auch keine liegen gebliebene
        # temporäre Datei im Zielordner selbst.
        self.assertEqual(list(self.ziel_ordner.iterdir()), [])
        self.assertFalse((self.ziel_ordner.parent / "boese.sqlite").exists())

    def test_abbruch_beim_schreiben_laesst_vorhandene_datei_unveraendert(self):
        """QS-Fund (19./20.09.): Bricht das Schreiben mittendrin ab (hier simuliert über
        einen Fehler beim abschließenden os.replace(), z.B. wie bei einem Stromausfall
        oder einer vollen Platte), muss die ZUVOR bestehende Termin-Datei unangetastet
        bleiben statt abgeschnitten/korrupt überschrieben zu werden - und es darf keine
        liegen gebliebene temporäre Datei zurückbleiben."""
        _termin_anlegen(self.quell_ordner, "a.sqlite")
        sicherung_erstellen(self.zip_pfad, ordner=self.quell_ordner)
        (self.ziel_ordner / "a.sqlite").write_text("alter Inhalt - darf nicht verloren gehen")

        with patch("db_sicherung.os.replace", side_effect=OSError("simulierter Schreibfehler")):
            with self.assertRaises(OSError):
                sicherung_wiederherstellen(self.zip_pfad, {"a.sqlite": "a.sqlite"}, ordner=self.ziel_ordner)

        # Alte Datei unverändert...
        self.assertEqual((self.ziel_ordner / "a.sqlite").read_text(), "alter Inhalt - darf nicht verloren gehen")
        # ...und keine liegen gebliebene .tmp-Datei im Zielordner.
        self.assertEqual([p.name for p in self.ziel_ordner.iterdir()], ["a.sqlite"])

    def test_q1_doppelte_zielnamen_werden_abgelehnt(self):
        """Sicherheitskorrektur Q-1 (07.10.2026), Details folgen."""
        with zipfile.ZipFile(self.zip_pfad, "w") as zf:
            zf.writestr("a.sqlite", "eins")
            zf.writestr("A.sqlite", "zwei")

        with self.assertRaisesRegex(ValueError, "mehrfach"):
            sicherung_wiederherstellen(
                self.zip_pfad, {"a.sqlite": "a.sqlite", "A.sqlite": "A.sqlite"}, ordner=self.ziel_ordner
            )
        self.assertEqual(list(self.ziel_ordner.iterdir()), [])

    def test_lesefehler_ersetzt_noch_keinen_termin(self):
        """QS-Prüfung 07.10.2026, Befund 3: Alle Einträge werden erst vollständig entpackt,
        bevor ein vorhandener Termin ersetzt wird - ein Lesefehler beim zweiten Eintrag
        lässt den ersten Termin unverändert."""
        with zipfile.ZipFile(self.zip_pfad, "w") as zf:
            zf.writestr("a.sqlite", "neu")
        (self.ziel_ordner / "a.sqlite").write_text("alt")

        with self.assertRaises(KeyError):
            sicherung_wiederherstellen(
                self.zip_pfad, {"a.sqlite": "a.sqlite", "fehlt.sqlite": "fehlt.sqlite"}, ordner=self.ziel_ordner
            )
        self.assertEqual((self.ziel_ordner / "a.sqlite").read_text(), "alt")
        self.assertEqual([p.name for p in self.ziel_ordner.iterdir()], ["a.sqlite"])

    def test_abbruch_nach_erstem_ersetzen_nennt_wiederhergestellte_termine(self):
        """QS-Prüfung 07.10.2026, Befund 3: Scheitert das Ersetzen erst beim zweiten
        Termin (z. B. Datei unter Windows gesperrt), nennt die Ausnahme den bereits
        ersetzten ersten Termin. Temporäre Dateien bleiben nicht liegen."""
        with zipfile.ZipFile(self.zip_pfad, "w") as zf:
            zf.writestr("a.sqlite", "neu-a")
            zf.writestr("b.sqlite", "neu-b")
        (self.ziel_ordner / "a.sqlite").write_text("alt-a")
        (self.ziel_ordner / "b.sqlite").write_text("alt-b")

        original_replace = os.replace
        aufrufe = []

        def replace_mit_fehler(quelle, ziel):
            aufrufe.append(ziel)
            if len(aufrufe) == 2:
                raise PermissionError("Datei gesperrt")
            return original_replace(quelle, ziel)

        with patch("db_sicherung.os.replace", side_effect=replace_mit_fehler):
            with self.assertRaises(TeilweiseWiederhergestelltError) as kontext:
                sicherung_wiederherstellen(
                    self.zip_pfad, {"a.sqlite": "a.sqlite", "b.sqlite": "b.sqlite"}, ordner=self.ziel_ordner
                )

        self.assertEqual(kontext.exception.geschrieben, ["a.sqlite"])
        self.assertIsInstance(kontext.exception.ursache, PermissionError)
        self.assertIn("a.sqlite", str(kontext.exception))
        self.assertEqual((self.ziel_ordner / "a.sqlite").read_text(), "neu-a")
        self.assertEqual((self.ziel_ordner / "b.sqlite").read_text(), "alt-b")
        self.assertEqual(sorted(p.name for p in self.ziel_ordner.iterdir()), ["a.sqlite", "b.sqlite"])

    def test_ungueltige_datei_wirft_value_error(self):
        """QS-Prüfung 07.10.2026, Befund 4: wie sicherung_inhalt() über _zip_oeffnen()."""
        kaputt = self.ziel_ordner.parent / "kaputt.zip"
        kaputt.write_text("das ist kein ZIP")
        with self.assertRaises(ValueError):
            sicherung_wiederherstellen(str(kaputt), {"a.sqlite": "a.sqlite"}, ordner=self.ziel_ordner)

    def test_mit_passwort(self):
        _termin_anlegen(self.quell_ordner, "a.sqlite")
        sicherung_erstellen(self.zip_pfad, passwort="geheim123", ordner=self.quell_ordner)

        wiederhergestellt = sicherung_wiederherstellen(
            self.zip_pfad, {"a.sqlite": "a.sqlite"}, passwort="geheim123", ordner=self.ziel_ordner
        )

        self.assertEqual(wiederhergestellt, ["a.sqlite"])

    def test_falsches_passwort_wirft_passwortfehler(self):
        _termin_anlegen(self.quell_ordner, "a.sqlite")
        sicherung_erstellen(self.zip_pfad, passwort="geheim123", ordner=self.quell_ordner)

        with self.assertRaises(PasswortFalschError):
            sicherung_wiederherstellen(
                self.zip_pfad, {"a.sqlite": "a.sqlite"}, passwort="falsch", ordner=self.ziel_ordner
            )


class TestEindeutigenDateinamenFinden(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.ordner = pathlib.Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_gibt_wunschname_zurueck_wenn_frei(self):
        self.assertEqual(eindeutigen_dateinamen_finden(self.ordner, "a.sqlite"), "a.sqlite")

    def test_haengt_zaehler_an_bei_konflikt(self):
        (self.ordner / "a.sqlite").write_text("x")
        self.assertEqual(eindeutigen_dateinamen_finden(self.ordner, "a.sqlite"), "a (2).sqlite")

    def test_erhoeht_zaehler_bis_ein_freier_name_gefunden_ist(self):
        (self.ordner / "a.sqlite").write_text("x")
        (self.ordner / "a (2).sqlite").write_text("x")
        (self.ordner / "a (3).sqlite").write_text("x")
        self.assertEqual(eindeutigen_dateinamen_finden(self.ordner, "a.sqlite"), "a (4).sqlite")

    def test_q1_bereits_vergebene_namen(self):
        """Sicherheitskorrektur Q-1 (07.10.2026), Details folgen."""
        (self.ordner / "a.sqlite").write_text("x")
        self.assertEqual(
            eindeutigen_dateinamen_finden(self.ordner, "a.sqlite", bereits_vergeben={"A (2).sqlite"}),
            "a (3).sqlite",
        )


class TestIstSichererDateiname(unittest.TestCase):
    """QS-Fund (19./20.09., Path Traversal beim Backup-Import) - siehe Docstring von
    _ist_sicherer_dateiname() in db_sicherung.py."""

    def test_normale_dateinamen_sind_sicher(self):
        self.assertTrue(_ist_sicherer_dateiname("a.sqlite"))
        self.assertTrue(_ist_sicherer_dateiname("Termin (2).sqlite"))
        self.assertTrue(_ist_sicherer_dateiname("Prüfung 19.09.2026.sqlite"))

    def test_pfadanteile_mit_slash_sind_unsicher(self):
        self.assertFalse(_ist_sicherer_dateiname("../boese.sqlite"))
        self.assertFalse(_ist_sicherer_dateiname("../../boese.sqlite"))
        self.assertFalse(_ist_sicherer_dateiname("unterordner/a.sqlite"))
        self.assertFalse(_ist_sicherer_dateiname("/etc/a.sqlite"))

    def test_pfadanteile_mit_backslash_sind_unsicher(self):
        self.assertFalse(_ist_sicherer_dateiname("..\\boese.sqlite"))
        self.assertFalse(_ist_sicherer_dateiname("unterordner\\a.sqlite"))

    def test_leerer_name_ist_unsicher(self):
        self.assertFalse(_ist_sicherer_dateiname(""))

    def test_windows_geraetenamen_sind_unsicher(self):
        """Sicherheitsprüfung 03.10.2026, S-8."""
        for name in ("CON.sqlite", "con.sqlite", "NUL.sqlite", "COM1.sqlite", "lpt9.sqlite",
                     "AUX .sqlite", "PRN.tar.sqlite"):
            with self.subTest(name=name):
                self.assertFalse(_ist_sicherer_dateiname(name))
        for name in ("CONTROL.sqlite", "Konzert.sqlite", "COM10.sqlite", "Nulltest.sqlite"):
            with self.subTest(name=name):
                self.assertTrue(_ist_sicherer_dateiname(name))

    def test_unter_windows_ungueltige_zeichen_sind_unsicher(self):
        """Desktop-Prüfung 14.10.2026, Teil 7 Nr. 10."""
        for name in ("ab:x.sqlite", "x.sqlite:y.sqlite", "a*.sqlite", "a?.sqlite", 'a".sqlite',
                     "a<b.sqlite", "a>b.sqlite", "a|b.sqlite", "a\x01.sqlite", "a\tb.sqlite"):
            with self.subTest(name=name):
                self.assertFalse(_ist_sicherer_dateiname(name))


class TestZipGrenzen(unittest.TestCase):
    """Sicherheitsprüfung 03.10.2026, S-8: Obergrenzen gegen ZIP-Bomben. Die Grenzen werden
    für den Test verkleinert, damit keine großen Dateien entstehen."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        basis = pathlib.Path(self._tmpdir.name)
        self.ordner = basis / "termine"
        self.ordner.mkdir()
        self.zip_pfad = str(basis / "sicherung.zip")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _zip(self, eintraege: dict[str, bytes]):
        with zipfile.ZipFile(self.zip_pfad, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, daten in eintraege.items():
                zf.writestr(name, daten)

    def test_zu_viele_eintraege(self):
        self._zip({f"t{i}.sqlite": b"x" for i in range(4)})
        with patch("db_sicherung._MAX_ZIP_EINTRAEGE", 3):
            with self.assertRaisesRegex(ValueError, "mehr als 3 Einträge"):
                sicherung_inhalt(self.zip_pfad)

    def test_zu_grosse_einzeldatei(self):
        # Stark komprimierbar: wenige Bytes im ZIP, ausgepackt deutlich größer.
        self._zip({"a.sqlite": b"\0" * 5000})
        self.assertLess(pathlib.Path(self.zip_pfad).stat().st_size, 1000)
        with patch("db_sicherung._MAX_DATEIGROESSE", 4000):
            with self.assertRaisesRegex(ValueError, "a.sqlite"):
                sicherung_inhalt(self.zip_pfad)
            with self.assertRaises(ValueError):
                sicherung_wiederherstellen(self.zip_pfad, {"a.sqlite": "a.sqlite"}, ordner=self.ordner)
        self.assertEqual(list(self.ordner.iterdir()), [])

    def test_zu_grosse_gesamtgroesse(self):
        self._zip({"a.sqlite": b"\0" * 3000, "b.sqlite": b"\0" * 3000})
        with patch("db_sicherung._MAX_GESAMTGROESSE", 5000):
            with self.assertRaisesRegex(ValueError, "ausgepackt größer"):
                sicherung_inhalt(self.zip_pfad)

    def test_lzma_fuellbytes_hinter_dem_datenstrom_werfen_keinen_eoferror(self):
        """Nacharbeit zur Sicherheitsprüfung: Hinter dem Ende des LZMA-Datenstroms liegende Bytes werden
        verworfen statt mit EOFError abzubrechen."""
        import lzma
        from db_sicherung import _BegrenzterEntpacker
        daten = b"A" * 2000
        entpacker = _BegrenzterEntpacker(lzma.LZMADecompressor(), 10_000, "a.sqlite")
        ausgabe = entpacker.decompress(lzma.compress(daten) + b"\0" * 600)
        self.assertEqual(ausgabe, daten)
        self.assertTrue(entpacker.eof)
        self.assertEqual(entpacker.decompress(b"\0" * 100), b"")

    def test_aes_archiv_mit_lzma_oder_bzip2_wird_ebenfalls_begrenzt(self):
        """Nacharbeit zur Sicherheitsprüfung: Auch bei einem verschlüsselten Fremdarchiv (pyzipper/AES)
        greift die Grenze, wenn das Verzeichnis eine zu kleine Größe angibt."""
        from db_sicherung import _lesen_begrenzt
        for verfahren in (zipfile.ZIP_LZMA, zipfile.ZIP_BZIP2):
            with self.subTest(verfahren=verfahren):
                with pyzipper.AESZipFile(self.zip_pfad, "w", compression=verfahren,
                                         encryption=pyzipper.WZ_AES) as zf:
                    zf.setpassword(b"pw")
                    zf.writestr("a.sqlite", b"\0" * 300_000)
                with pyzipper.AESZipFile(self.zip_pfad) as zf:
                    zf.setpassword(b"pw")
                    # Die Größenangabe im Verzeichnis wird erst nach dem Öffnen klein gelogen;
                    # die Grenze muss den Entpacker selbst erreichen, nicht nur den Lesepuffer.
                    with patch("db_sicherung._MAX_DATEIGROESSE", 1000):
                        with self.assertRaisesRegex(ValueError, "größer als angegeben"):
                            _lesen_begrenzt(zf, "a.sqlite")

    def test_normale_sicherung_liegt_unter_den_grenzen(self):
        _termin_anlegen(self.ordner, "a.sqlite")
        sicherung_erstellen(self.zip_pfad, ordner=self.ordner)
        self.assertEqual(sicherung_inhalt(self.zip_pfad), ["a.sqlite"])

    def test_geraetename_wird_nicht_angeboten(self):
        self._zip({"CON.sqlite": b"x", "a.sqlite": b"x"})
        self.assertEqual(sicherung_inhalt(self.zip_pfad), ["a.sqlite"])


class TestAutoSicherung(unittest.TestCase):
    """Marco 10.11.2026: automatische Kopie des geöffneten Termins."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.ordner = pathlib.Path(self._tmp.name) / "Auto"
        self.pfad = str(pathlib.Path(self._tmp.name) / "2026-11-14_Testverein.sqlite")
        self.conn = init_db(self.pfad)
        self.addCleanup(self.conn.close)
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Albers", vorname="Anna", rufname_hund="Aika", art="ED", stufe=1, disziplin="Trümmerfeld"))

    def test_kopie_enthaelt_den_stand_und_wird_begrenzt(self):
        import datetime

        from db_sicherung import auto_sicherung_erstellen

        start = datetime.datetime(2026, 11, 14, 8, 0, 0)
        pfade = [
            auto_sicherung_erstellen(self.conn, self.pfad, self.ordner, behalten=3,
                                     jetzt=start + datetime.timedelta(minutes=15 * i))
            for i in range(5)
        ]
        self.assertTrue(all(pfade))
        dateien = sorted(p.name for p in self.ordner.glob("*.sqlite"))
        self.assertEqual(len(dateien), 3)  # nur die letzten drei
        self.assertTrue(dateien[0].startswith("2026-11-14_Testverein_2026-11-14_"))
        kopie = init_db(str(self.ordner / dateien[-1]))
        try:
            self.assertEqual(len(list_teilnehmer(kopie)), 1)
        finally:
            kopie.close()

    def test_mindestabstand_verhindert_haeufige_kopien(self):
        import datetime

        from db_sicherung import auto_sicherung_erstellen

        start = datetime.datetime(2026, 11, 14, 8, 0, 0)
        self.assertIsNotNone(auto_sicherung_erstellen(self.conn, self.pfad, self.ordner, jetzt=start))
        # Die Datei trägt die echte Änderungszeit (jetzt): der Abstand wird dagegen gemessen.
        spaeter = datetime.datetime.now() + datetime.timedelta(seconds=30)
        self.assertIsNone(auto_sicherung_erstellen(self.conn, self.pfad, self.ordner, jetzt=spaeter))
        mit_abstand = datetime.datetime.now() + datetime.timedelta(minutes=20)
        self.assertIsNotNone(auto_sicherung_erstellen(self.conn, self.pfad, self.ordner, jetzt=mit_abstand))

    def test_misslungene_kopie_blockiert_und_verdraengt_nichts(self):
        import datetime
        import sqlite3

        from db_sicherung import auto_sicherung_erstellen

        start = datetime.datetime(2026, 11, 14, 8, 0, 0)
        gut =auto_sicherung_erstellen(self.conn, self.pfad, self.ordner, behalten=1, jetzt=start)
        self.assertIsNotNone(gut)

        class Kaputt:
            def backup(self, ziel):
                raise sqlite3.OperationalError("Datenträger voll")

        spaeter = datetime.datetime.now() + datetime.timedelta(minutes=30)
        self.assertIsNone(auto_sicherung_erstellen(Kaputt(), self.pfad, self.ordner, behalten=1, jetzt=spaeter))
        self.assertEqual([p.name for p in self.ordner.glob("*.sqlite")], [pathlib.Path(gut).name])

    def test_ohne_mindestabstand_sichert_immer(self):
        import datetime

        from db_sicherung import auto_sicherung_erstellen

        self.assertIsNotNone(auto_sicherung_erstellen(self.conn, self.pfad, self.ordner))
        spaeter = datetime.datetime.now() + datetime.timedelta(seconds=30)
        self.assertIsNotNone(
            auto_sicherung_erstellen(self.conn, self.pfad, self.ordner, mindestabstand_sekunden=0, jetzt=spaeter))

    def test_fehler_stoeren_nicht(self):
        from db_sicherung import auto_sicherung_erstellen

        blockiert = pathlib.Path(self._tmp.name) / "Datei"
        blockiert.write_text("x")  # ein Ordner kann hier nicht angelegt werden
        self.assertIsNone(auto_sicherung_erstellen(self.conn, self.pfad, blockiert / "Auto"))
        self.assertIsNone(auto_sicherung_erstellen(object(), self.pfad, self.ordner))  # keine SQLite-Verbindung
        self.assertIsNone(auto_sicherung_erstellen(self.conn, "", self.ordner))


class TestKopienVorDemLoeschen(unittest.TestCase):
    """Marco 12.11.2026: Kopien vor dem Löschen getrennt von den normalen (eigene Endung, eigene
    Rotation) und Rückholen einzelner Ergebniswerte - ohne PySide6 lauffähig."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.ordner = pathlib.Path(self._tmp.name) / "Auto"

    def _termin(self, name):
        pfad = str(pathlib.Path(self._tmp.name) / f"{name}.sqlite")
        conn = init_db(pfad)
        self.addCleanup(conn.close)
        return conn, pfad

    def test_getrennte_rotation_und_mindestabstand(self):
        import datetime
        import os

        from db_sicherung import auto_sicherung_erstellen, auto_sicherungen_zu_termin, ist_loeschen_kopie

        conn, pfad = self._termin("Pruefung")
        tag = datetime.datetime(2026, 1, 2, 8, 0, 0)  # Vergangenheit: der Abstand zählt ab der Dateizeit
        for i in range(7):
            self.assertIsNotNone(auto_sicherung_erstellen(
                conn, pfad, self.ordner, vor_loeschen=True, jetzt=tag + datetime.timedelta(minutes=20 * i)))
        letzte = max(self.ordner.glob("*_vor-Loeschen.sqlite"))
        zeit = (tag + datetime.timedelta(minutes=120)).timestamp()
        os.utime(letzte, (zeit, zeit))
        self.assertIsNone(auto_sicherung_erstellen(
            conn, pfad, self.ordner, vor_loeschen=True, jetzt=tag + datetime.timedelta(minutes=125)))
        for i in range(15):
            auto_sicherung_erstellen(conn, pfad, self.ordner, mindestabstand_sekunden=0,
                                     jetzt=tag + datetime.timedelta(hours=5, minutes=i))
        kopien = auto_sicherungen_zu_termin(pfad, self.ordner)
        self.assertEqual(sum(ist_loeschen_kopie(p) for p, _z in kopien), 5)
        self.assertEqual(sum(not ist_loeschen_kopie(p) for p, _z in kopien), 10)
        # Ein ausdrückliches `behalten` gilt auch mit vor_loeschen.
        auto_sicherung_erstellen(conn, pfad, self.ordner, vor_loeschen=True, behalten=2,
                                 mindestabstand_sekunden=0, jetzt=tag + datetime.timedelta(days=1))
        self.assertEqual(len(list(self.ordner.glob("*_vor-Loeschen.sqlite"))), 2)

    def test_namen_mit_klammern_und_endung_vor_loeschen(self):
        import datetime

        from db_sicherung import auto_sicherung_erstellen, auto_sicherungen_zu_termin, ist_loeschen_kopie

        jetzt = datetime.datetime(2026, 1, 2, 8, 0, 0)
        for name in ("Prüfung [A]", "Prüfung_vor-Loeschen"):
            conn, pfad = self._termin(name)
            for art in (False, True):
                self.assertIsNotNone(auto_sicherung_erstellen(
                    conn, pfad, self.ordner, vor_loeschen=art, mindestabstand_sekunden=0, jetzt=jetzt))
            kopien = auto_sicherungen_zu_termin(pfad, self.ordner)
            with self.subTest(name=name):
                self.assertEqual(sorted(ist_loeschen_kopie(p) for p, _z in kopien), [False, True])
                self.assertTrue(all(z == jetzt for _p, z in kopien))

    def test_ergebnis_unterschiede_ueberspringt_fehlende_spalten(self):
        import sqlite3

        from db import eintragen_ergebnis, ergebnis_unterschiede, ergebnis_werte_wiederherstellen

        conn, _pfad = self._termin("Aktuell")
        tid = add_teilnehmer(conn, NeuerTeilnehmer(
            nachname="Albers", vorname="Anna", rufname_hund="Aika", art="ED", stufe=1, disziplin="Trümmerfeld"))
        eintragen_ergebnis(conn, tid, "Trümmerfeld", 10, 5)
        # Kopie einer älteren Version: kein abbruch_grund, kein stechen_sieger.
        alt = sqlite3.connect(":memory:")
        self.addCleanup(alt.close)
        alt.row_factory = sqlite3.Row
        alt.execute("CREATE TABLE ergebnisse (teilnehmer_id INTEGER PRIMARY KEY, suche_truemmerfeld INTEGER, "
                    "anzeige_truemmerfeld INTEGER, disqualifiziert INTEGER, abbruch INTEGER)")
        alt.execute("INSERT INTO ergebnisse VALUES (?, 40, 20, 1, 1)", (tid,))
        alt.execute("CREATE TABLE teilnehmer (id INTEGER PRIMARY KEY, nachname, vorname, rufname_hund)")
        alt.execute("INSERT INTO teilnehmer VALUES (?, 'Albers', 'Anna', 'Aika')", (tid,))
        unterschiede = ergebnis_unterschiede(alt, conn)
        werte = {w["schluessel"] for w in unterschiede[0]["werte"]}
        self.assertEqual(werte, {"Trümmerfeld", "disqualifiziert"})  # Abbruch (ohne Grund-Spalte) und Stechen fehlen
        self.assertEqual(ergebnis_werte_wiederherstellen(conn, alt, [(tid, "abbruch"), (tid, "Trümmerfeld")]), 1)
        row = conn.execute("SELECT suche_truemmerfeld, abbruch FROM ergebnisse WHERE teilnehmer_id = ?", (tid,)).fetchone()
        self.assertEqual((row["suche_truemmerfeld"], row["abbruch"]), (40, 0))

    def test_ergebnisse_aus_kopie_nur_fuer_denselben_teilnehmer(self):
        """Sicherheitskorrektur D-5: Die ID allein genügt nicht; Name und Hund müssen übereinstimmen
        (ohne Groß-/Kleinschreibung und überzählige Leerzeichen). Sonst wird nichts angeboten und
        nichts zurückgeschrieben."""
        import sqlite3

        from db import eintragen_ergebnis, ergebnis_unterschiede, ergebnis_werte_wiederherstellen

        faelle = (
            ("Albers", "Anna", "Aika", True),
            ("  albers ", "ANNA", "aika", True),
            ("Brandt", "Anna", "Aika", False),
            ("Albers", "Berta", "Aika", False),
            ("Albers", "Anna", "Bruno", False),
        )
        for nachname, vorname, hund, erwartet in faelle:
            with self.subTest(nachname=nachname, vorname=vorname, hund=hund):
                conn, _pfad = self._termin(f"Aktuell-{nachname.strip()}-{vorname}-{hund}")
                tid = add_teilnehmer(conn, NeuerTeilnehmer(
                    nachname="Albers", vorname="Anna", rufname_hund="Aika", art="ED", stufe=1,
                    disziplin="Trümmerfeld"))
                eintragen_ergebnis(conn, tid, "Trümmerfeld", 10, 5)
                kopie = sqlite3.connect(":memory:")
                self.addCleanup(kopie.close)
                kopie.row_factory = sqlite3.Row
                kopie.execute("CREATE TABLE teilnehmer (id INTEGER PRIMARY KEY, nachname, vorname, rufname_hund)")
                kopie.execute("INSERT INTO teilnehmer VALUES (?, ?, ?, ?)", (tid, nachname, vorname, hund))
                kopie.execute("CREATE TABLE ergebnisse (teilnehmer_id INTEGER PRIMARY KEY, "
                              "suche_truemmerfeld INTEGER, anzeige_truemmerfeld INTEGER)")
                kopie.execute("INSERT INTO ergebnisse VALUES (?, 40, 20)", (tid,))
                unterschiede = ergebnis_unterschiede(kopie, conn)
                zahl = ergebnis_werte_wiederherstellen(conn, kopie, [(tid, "Trümmerfeld")])
                row = conn.execute("SELECT suche_truemmerfeld FROM ergebnisse WHERE teilnehmer_id = ?",
                                   (tid,)).fetchone()
                self.assertEqual(bool(unterschiede), erwartet)
                self.assertEqual(zahl, 1 if erwartet else 0)
                self.assertEqual(row["suche_truemmerfeld"], 40 if erwartet else 10)

    def test_werte_aus_der_kopie_werden_vor_dem_speichern_geprueft(self):
        """Sicherheitskorrektur D-6: Stünden nach dem Zurückholen Werte in der Datei, die das Programm
        beim Öffnen ablehnt (Dezimalzahl als Punkte, Binärwert als Name), wird nichts geändert."""
        import sqlite3
        from contextlib import closing

        from db import (
            KopieWerteUnzulaessig,
            eintragen_ergebnis,
            ergebnis_werte_wiederherstellen,
            get_ergebnis,
            list_teilnehmer,
            teilnehmer_sichern,
            teilnehmer_wiederherstellen,
            delete_teilnehmer,
            termin_oeffnen,
        )

        conn, pfad = self._termin("Aktuell")
        tid = add_teilnehmer(conn, NeuerTeilnehmer(
            nachname="Albers", vorname="Anna", rufname_hund="Aika", art="ED", stufe=1, disziplin="Trümmerfeld"))
        eintragen_ergebnis(conn, tid, "Trümmerfeld", 10, 5)

        # Ergebnisse: Kopie mit einem unzulässigen Wertetyp bei den Punkten.
        kopie = sqlite3.connect(":memory:")
        self.addCleanup(kopie.close)
        kopie.row_factory = sqlite3.Row
        kopie.execute("CREATE TABLE teilnehmer (id INTEGER PRIMARY KEY, nachname, vorname, rufname_hund)")
        kopie.execute("INSERT INTO teilnehmer VALUES (?, 'Albers', 'Anna', 'Aika')", (tid,))
        kopie.execute("CREATE TABLE ergebnisse (teilnehmer_id INTEGER PRIMARY KEY, "
                      "suche_truemmerfeld, anzeige_truemmerfeld)")
        kopie.execute("INSERT INTO ergebnisse VALUES (?, 30.5, 20)", (tid,))
        with self.assertRaises(KopieWerteUnzulaessig):
            ergebnis_werte_wiederherstellen(conn, kopie, [(tid, "Trümmerfeld")])
        self.assertEqual(get_ergebnis(conn, tid)["suche_truemmerfeld"], 10)
        kopie.execute("UPDATE ergebnisse SET suche_truemmerfeld = 40")
        self.assertEqual(ergebnis_werte_wiederherstellen(conn, kopie, [(tid, "Trümmerfeld")]), 1)
        self.assertEqual(get_ergebnis(conn, tid)["suche_truemmerfeld"], 40)

        # Teilnehmer: ein gesicherter Datensatz mit Binärwert als Nachname.
        sicherung = teilnehmer_sichern(conn, tid)
        delete_teilnehmer(conn, tid)
        sicherung["teilnehmer"]["nachname"] = b"Alb\xffers"
        with self.assertRaises(KopieWerteUnzulaessig):
            teilnehmer_wiederherstellen(conn, sicherung)
        self.assertEqual(list_teilnehmer(conn), [])  # zurückgerollt, nichts steht halb in der Datei
        sicherung["teilnehmer"]["nachname"] = "Albers"
        self.assertTrue(teilnehmer_wiederherstellen(conn, sicherung))
        conn.close()
        with closing(termin_oeffnen(pfad)) as offen:  # der Termin lässt sich weiter öffnen
            self.assertEqual([t["nachname"] for t in list_teilnehmer(offen)], ["Albers"])

    def test_kopie_mit_ansicht_oder_trigger_wird_in_den_dialogen_abgelehnt(self):
        """D-6: Das Programm legt nie Ansichten oder Trigger an; eine Kopie damit wird nicht gelesen
        (Option ohne_fremdobjekte); ohne die Option bleibt das Lesen wie bisher."""
        import sqlite3
        from contextlib import closing

        from db import KopieMitFremdobjekten, termin_lesend_pruefen

        for sql in ("CREATE VIEW v AS SELECT 1 AS x",
                    "CREATE TRIGGER t AFTER INSERT ON teilnehmer BEGIN SELECT 1; END"):
            with self.subTest(sql=sql.split()[1]):
                _conn, pfad = self._termin(f"Kopie-{sql.split()[1]}")
                _conn.close()
                with closing(sqlite3.connect(pfad)) as roh:
                    roh.execute(sql)
                    roh.commit()
                with self.assertRaises(KopieMitFremdobjekten):
                    termin_lesend_pruefen(pfad, ohne_fremdobjekte=True)
                with closing(termin_lesend_pruefen(pfad)) as gelesen:
                    self.assertIsNotNone(gelesen)
        _conn, sauber = self._termin("Sauber")
        _conn.close()
        with closing(termin_lesend_pruefen(sauber, ohne_fremdobjekte=True)) as gelesen:
            self.assertIsNotNone(gelesen)

    def test_kopie_abweichung_vergleicht_verein_und_datum(self):
        """D-5: Hinweis nur bei abweichendem Verein oder Datum; Werte aus der Kopie erscheinen
        gekürzt, einzeilig und ohne Steuerzeichen."""
        from db_sicherung import kopie_abweichung

        def termin(name, verein, datum):
            conn, _pfad = self._termin(name)
            set_veranstaltung(conn, verein=verein, datum=datum)
            return conn

        eigen = termin("Eigen", "Eigener Verein", "2026-11-20")
        self.assertIsNone(kopie_abweichung(termin("Gleich", "eigener  verein", "2026-11-20"), eigen))
        self.assertIsNone(kopie_abweichung(termin("Leer1", "x", "2026-11-20"), termin("Leer2", "x", "2026-11-20")))
        andere_datum = kopie_abweichung(termin("Datum", "Eigener Verein", "2026-12-24"), eigen)
        self.assertIn("2026-12-24", andere_datum)
        andere_verein = kopie_abweichung(termin("Verein", "Fremdverein", "2026-11-20"), eigen)
        self.assertIn("Fremdverein", andere_verein)
        nullbreit = chr(0x200B)
        # Der lange Wert kommt wie aus einer fremden Datei direkt in die Datenbank (set_veranstaltung
        # begrenzt die Länge, I-5).
        quelle = termin("Lang", "kurz", "2026-11-20")
        quelle.execute("UPDATE veranstaltung SET verein = ?", ("Zeile eins\nZeile zwei\x00" + "x" * 200 + nullbreit,))
        quelle.commit()
        lang = kopie_abweichung(quelle, eigen)
        self.assertNotIn("\n", lang)
        self.assertNotIn("\x00", lang)
        self.assertNotIn(nullbreit, lang)
        self.assertLess(len(lang), 250)
        self.assertIn("…", lang)


if __name__ == "__main__":
    unittest.main(verbosity=2)
