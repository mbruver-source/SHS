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

                original_write = zip_klasse.write
                aufrufe = []

                def write_mit_fehler(zf, *args, _original=original_write, _aufrufe=aufrufe, **kwargs):
                    _aufrufe.append(args)
                    if len(_aufrufe) == 2:
                        raise OSError(28, "No space left on device")
                    return _original(zf, *args, **kwargs)

                with patch.object(zip_klasse, "write", write_mit_fehler):
                    with self.assertRaises(OSError):
                        sicherung_erstellen(str(ziel), passwort=passwort, ordner=self.ordner)

                self.assertEqual(len(aufrufe), 2)
                self.assertEqual(ziel.read_bytes(), vorher)
                self.assertEqual(sorted(p.name for p in self.ziel_ordner.iterdir()), ["sicherung.zip", "termine"])


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
        with patch.object(pyzipper.AESZipFile, "read", side_effect=zlib.error("invalid stored block lengths")):
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

    def test_normale_sicherung_liegt_unter_den_grenzen(self):
        _termin_anlegen(self.ordner, "a.sqlite")
        sicherung_erstellen(self.zip_pfad, ordner=self.ordner)
        self.assertEqual(sicherung_inhalt(self.zip_pfad), ["a.sqlite"])

    def test_geraetename_wird_nicht_angeboten(self):
        self._zip({"CON.sqlite": b"x", "a.sqlite": b"x"})
        self.assertEqual(sicherung_inhalt(self.zip_pfad), ["a.sqlite"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
