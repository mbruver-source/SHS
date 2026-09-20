"""Tests für die Datensicherung (Export/Import als ZIP, siehe db.py, Abschnitt
"Datensicherung"). Reine Logik-/Dateisystem-Tests ohne Qt, im selben Stil wie test_db.py
(unittest, tempfile.TemporaryDirectory) - decken sowohl den unverschlüsselten Weg
(Standard-`zipfile`) als auch den AES-256-verschlüsselten Weg (`pyzipper`) ab."""

import pathlib
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import pyzipper

from db import (
    NeuerTeilnehmer,
    PasswortFalschError,
    _ist_sicherer_dateiname,
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

        with patch("db.os.replace", side_effect=OSError("simulierter Schreibfehler")):
            with self.assertRaises(OSError):
                sicherung_wiederherstellen(self.zip_pfad, {"a.sqlite": "a.sqlite"}, ordner=self.ziel_ordner)

        # Alte Datei unverändert...
        self.assertEqual((self.ziel_ordner / "a.sqlite").read_text(), "alter Inhalt - darf nicht verloren gehen")
        # ...und keine liegen gebliebene .tmp-Datei im Zielordner.
        self.assertEqual([p.name for p in self.ziel_ordner.iterdir()], ["a.sqlite"])

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


class TestIstSichererDateiname(unittest.TestCase):
    """QS-Fund (19./20.09., Path Traversal beim Backup-Import) - siehe Docstring von
    _ist_sicherer_dateiname() in db.py."""

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
