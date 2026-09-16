"""Tests für die Datensicherung (Export/Import als ZIP, siehe db.py, Abschnitt
"Datensicherung"). Reine Logik-/Dateisystem-Tests ohne Qt, im selben Stil wie test_db.py
(unittest, tempfile.TemporaryDirectory) - decken sowohl den unverschlüsselten Weg
(Standard-`zipfile`) als auch den AES-256-verschlüsselten Weg (`pyzipper`) ab."""

import pathlib
import tempfile
import unittest
import zipfile

import pyzipper

from db import (
    NeuerTeilnehmer,
    PasswortFalschError,
    add_teilnehmer,
    eindeutigen_dateinamen_finden,
    init_db,
    set_veranstaltung,
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


class TestSicherungErstellen(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        basis = pathlib.Path(self._tmpdir.name)
        self.ordner = basis / "termine"
        self.ordner.mkdir()
        self.ziel_ordner = basis

    def tearDown(self):
        self._tmpdir.cleanup()

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
