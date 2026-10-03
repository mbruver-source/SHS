"""Upgrade-Tests mit echten Dateien älterer Versionen (T3, mit Marco abgestimmt am 03.10.2026).

Die Dateien unter testdaten/altversionen/<tag>/ hat tools/altdaten_erzeugen.py mit dem Code
der jeweiligen alten Version geschrieben (nur erfundene Daten). Jede Datei wird hier mit dem
AKTUELLEN Code geöffnet (Migration) und geprüft: Stammdaten, Auswertung, Zeitplan,
PDF-Ausgaben und Wiederherstellung der Sicherungen. Die Dateien selbst bleiben unverändert -
getestet wird immer auf einer Kopie.

Inhalt jeder Altdatei (siehe Füllskript im Erzeugungs-Skript):
- ED LK 1 Trümmerfeld: Anna 96 (V, 1.), Ben 80 (G, 2.), Clara 69 (nB) -> "von 3"
- DK LK 2: Dieter 270 (SG, 1.); Emil nur Trümmerfeld -> ausstehend
- ED LK 2 Fläche: Frieda disqualifiziert (falls die Version das konnte, sonst ohne Ergebnis)
- ED LK 3 Behältnis: Gerd 100 Punkte, "Keine Teilnahme" (falls die Version das konnte)
- Zeitplan mit 2 Richtern und einer Mittagspause
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import db
from db_sicherung import sicherung_inhalt, sicherung_wiederherstellen

ALTDATEN = Path(__file__).resolve().parent / "testdaten" / "altversionen"
PASSWORT = "Altdaten-Test-1"  # wie in tools/altdaten_erzeugen.py
VERSIONEN = sorted(
    (p for p in ALTDATEN.iterdir() if (p / "termin.sqlite").exists()) if ALTDATEN.exists() else [],
    key=lambda p: [int(x) for x in p.name.lstrip("v").split(".")],
)

try:
    import pdf_export
except ImportError:  # pragma: no cover - reportlab fehlt
    pdf_export = None


class TestAltversionen(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="altversion_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_altdaten_vorhanden(self):
        self.assertGreaterEqual(len(VERSIONEN), 8, "testdaten/altversionen fehlt oder ist unvollständig")
        self.assertEqual(VERSIONEN[0].name, "v1.0.0")

    def test_altdaten_haben_wirklich_das_alte_datenmodell(self):
        """Sonst würde die Migration gar nicht geprüft: die Originaldateien (ungeöffnet) dürfen
        die erst später eingeführten Spalten noch nicht haben."""
        import sqlite3

        spalte_seit = {"keine_teilnahme": "1.0.39", "startnummer_bereiche": "1.0.40", "strasse": "1.0.3",
                       "disqualifiziert": "1.0.21"}
        tabelle = {"keine_teilnahme": "teilnehmer", "startnummer_bereiche": "veranstaltung",
                   "strasse": "teilnehmer", "disqualifiziert": "ergebnisse"}
        for ordner in VERSIONEN:
            version = [int(x) for x in ordner.name.lstrip("v").split(".")]
            roh = sqlite3.connect((ordner / "termin.sqlite").as_uri() + "?mode=ro", uri=True)
            try:
                for spalte, seit in spalte_seit.items():
                    with self.subTest(version=ordner.name, spalte=spalte):
                        vorhanden = spalte in [r[1] for r in roh.execute(f"PRAGMA table_info({tabelle[spalte]})")]
                        self.assertEqual(vorhanden, version >= [int(x) for x in seit.split(".")])
            finally:
                roh.close()

    def _oeffnen(self, version_ordner: Path):
        kopie = self.tmp / f"{version_ordner.name}.sqlite"
        shutil.copy(version_ordner / "termin.sqlite", kopie)
        return db.init_db(str(kopie)), kopie

    def _kann(self, version_ordner: Path) -> dict:
        return json.loads((version_ordner / "info.json").read_text(encoding="utf-8"))["kann"]

    def test_stammdaten_bleiben_erhalten(self):
        for ordner in VERSIONEN:
            with self.subTest(version=ordner.name):
                conn, _ = self._oeffnen(ordner)
                try:
                    v = db.get_veranstaltung(conn)
                    self.assertEqual((v["verein"], v["datum"], v["ort"]), ("Altdaten-Testverein", "2026-11-14", "Teststadt"))
                    teilnehmer = {t["nachname"]: t for t in db.list_teilnehmer(conn)}
                    self.assertEqual(sorted(teilnehmer), ["Anna", "Ben", "Clara", "Dieter", "Emil", "Frieda", "Gerd"])
                    self.assertEqual(
                        [teilnehmer[n]["startnummer"] for n in ("Anna", "Ben", "Clara", "Dieter", "Emil", "Frieda", "Gerd")],
                        [1, 2, 3, 4, 5, 6, 7],
                    )
                    self.assertTrue(teilnehmer["Anna"]["bezahlt"])
                    self.assertEqual(teilnehmer["Anna"]["chip_nr"], "276000000000001")
                    self.assertEqual(teilnehmer["Dieter"]["gegenstand_2"], "Metall")
                    kann = self._kann(ordner)
                    if kann["kontaktfelder"]:
                        self.assertEqual(teilnehmer["Anna"]["strasse"], "Testweg")
                    if kann["halter"]:
                        self.assertEqual(teilnehmer["Anna"]["halter_nachname"], "Halterin")
                    if kann["geburtsdatum"]:
                        self.assertEqual(teilnehmer["Anna"]["geburtsdatum"], "1980-05-01")
                    if kann["richter_3"]:
                        self.assertEqual(v["wertungsrichter_3"], "Richter C")
                    # Neue Felder haben in alten Dateien sinnvolle Standardwerte.
                    self.assertEqual(bool(teilnehmer["Anna"]["keine_teilnahme"]), False)
                    self.assertIsNone(v["startnummer_bereiche"])
                    self.assertEqual(db.dk_mindestabstand(v), 10)
                finally:
                    conn.close()

    def test_auswertung_und_rangliste(self):
        for ordner in VERSIONEN:
            with self.subTest(version=ordner.name):
                conn, _ = self._oeffnen(ordner)
                try:
                    kann = self._kann(ordner)
                    fertig, ausstehend = db.berechne_auswertung(conn)
                    erg = {t.name.split(",")[0]: t for t in fertig}
                    self.assertEqual((erg["Anna"].wertnote.abkuerzung, erg["Anna"].platzierung, erg["Anna"].von_startern), ("V", 1, 3))
                    self.assertEqual((erg["Ben"].wertnote.abkuerzung, erg["Ben"].platzierung), ("G", 2))
                    self.assertEqual((erg["Clara"].wertnote.abkuerzung, erg["Clara"].platzierung), ("nB", None))
                    self.assertEqual((erg["Dieter"].wertnote.abkuerzung, erg["Dieter"].gesamtpunkte), ("SG", 270))
                    ausstehend_namen = [t["nachname"] for t in ausstehend]
                    self.assertIn("Emil", ausstehend_namen)
                    if kann["disqualifikation"]:
                        self.assertEqual(erg["Frieda"].wertnote.abkuerzung, "DISQ")
                    else:
                        self.assertIn("Frieda", ausstehend_namen)
                    if kann["keine_teilnahme"]:
                        self.assertNotIn("Gerd", erg)
                        self.assertNotIn("Gerd", ausstehend_namen)
                    else:
                        self.assertEqual(erg["Gerd"].wertnote.abkuerzung, "V")
                finally:
                    conn.close()

    def test_zeitplan_bleibt_erhalten_und_ist_berechenbar(self):
        for ordner in VERSIONEN:
            with self.subTest(version=ordner.name):
                conn, _ = self._oeffnen(ordner)
                try:
                    richter = db.list_zeitplan_richter(conn)
                    self.assertEqual([r["name"] for r in richter], ["Richterin A", "Richter B"])
                    bloecke = db.berechne_zeitplan_bloecke(conn)
                    alle = [b for spur in bloecke for b in spur["bloecke"]]
                    self.assertIn("Mittagspause", [b.get("bezeichnung") for b in alle])
                    self.assertTrue(any(b["typ"] != "pause" for b in alle))
                    self.assertEqual(alle[0]["start"].strftime("%H:%M"), "08:30")
                    db.zeitplan_ueberschneidungen(conn)  # darf auf Altdaten nicht scheitern
                finally:
                    conn.close()

    @unittest.skipIf(pdf_export is None, "reportlab nicht installiert")
    def test_pdf_ausgaben_funktionieren(self):
        for ordner in VERSIONEN:
            with self.subTest(version=ordner.name):
                conn, _ = self._oeffnen(ordner)
                try:
                    anna = next(t["id"] for t in db.list_teilnehmer(conn) if t["nachname"] == "Anna")
                    ausgaben = {
                        "ergebnisliste": lambda p: pdf_export.erstelle_ergebnisliste_pdf(conn, p),
                        "etiketten": lambda p: pdf_export.erstelle_ergebnisliste_etiketten_pdf(conn, p),
                        "bewertungsbogen": lambda p: pdf_export.erstelle_bewertungsbogen_pdf(conn, anna, p),
                        "zeitplan": lambda p: pdf_export.erstelle_zeitplan_pdf(conn, p),
                    }
                    for name, erzeugen in ausgaben.items():
                        ziel = self.tmp / f"{ordner.name}_{name}.pdf"
                        erzeugen(str(ziel))
                        self.assertGreater(ziel.stat().st_size, 500, name)
                finally:
                    conn.close()

    def test_sicherungen_lassen_sich_wiederherstellen(self):
        for ordner in VERSIONEN:
            for datei, passwort in (("sicherung.zip", None), ("sicherung_passwort.zip", PASSWORT)):
                with self.subTest(version=ordner.name, sicherung=datei):
                    ziel = self.tmp / f"{ordner.name}_{datei}"
                    ziel.mkdir()
                    namen = sicherung_inhalt(str(ordner / datei), passwort=passwort)
                    self.assertEqual(namen, ["termin.sqlite"])
                    sicherung_wiederherstellen(
                        str(ordner / datei), {"termin.sqlite": "termin.sqlite"}, passwort=passwort, ordner=ziel
                    )
                    conn = db.init_db(str(ziel / "termin.sqlite"))
                    try:
                        self.assertEqual(len(db.list_teilnehmer(conn)), 7)
                    finally:
                        conn.close()

    def test_erneutes_oeffnen_ist_unschaedlich(self):
        for ordner in VERSIONEN:
            with self.subTest(version=ordner.name):
                conn, kopie = self._oeffnen(ordner)
                conn.close()
                conn = db.init_db(str(kopie))  # Migration ein zweites Mal
                try:
                    self.assertEqual(len(db.list_teilnehmer(conn)), 7)
                finally:
                    conn.close()


if __name__ == "__main__":
    unittest.main()
