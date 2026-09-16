"""
Tests für shs_core.py.

Drei Ebenen:
1. Schnelle Grenzwert-Tests (laufen immer, keine externe Datei nötig).
2. Der "mind. 70 Punkte je Einzeldisziplin"-Test - das Kernstück dieser Datei, siehe
   Docstring von shs_core.py. Deckt genau den Fehler ab, der ursprünglich im Programm
   übersehen wurde: eine hohe Gesamtpunktzahl beim DK reicht NICHT, wenn eine einzelne
   Disziplin unter 70 Punkten liegt.
3. Erschöpfender Abgleich der Notenberechnung gegen die Original-Tabelle
   "Hilfstabelle Wertnote" aus SHS Prüfungsprogramm_V2026.ods - prüft für den
   "bestanden"-Bereich (>= 70 Punkte je Disziplin bzw. Summe >= 210 beim DK) wirklich
   JEDEN möglichen Punktwert gegen die im Original hinterlegten Werte. Läuft nur, wenn
   die Originaldatei unter ODS_PATH gefunden wird (siehe unten), wird sonst übersprungen.
"""

import os
import unittest

from shs_core import (
    MINDESTPUNKTE_JE_DISZIPLIN,
    Teilnehmerergebnis,
    berechne_rangliste,
    berechne_wertnote_dk,
    berechne_wertnote_ed,
)

ODS_PATH = os.environ.get(
    "SHS_ODS_PATH", os.path.join(os.path.dirname(__file__), "SHS Prüfungsprogramm_V2026.ods")
)


class TestWertnoteGrenzwerte(unittest.TestCase):
    """Prüft die bekannten Notengrenzen aus dem Original an den kritischen Übergängen."""

    def test_ed_grenzwerte_im_bestandenen_bereich(self):
        faelle = [
            (100, "V"), (96, "V"),
            (95, "SG"), (90, "SG"),
            (89, "G"), (80, "G"),
            (79, "B"), (70, "B"),
        ]
        for punkte, erwartete_abk in faelle:
            with self.subTest(punkte=punkte):
                note = berechne_wertnote_ed(punkte)
                self.assertEqual(note.abkuerzung, erwartete_abk)
                self.assertTrue(note.bestanden)

        self.assertEqual(berechne_wertnote_ed(96).notentext, "Vorzüglich")
        self.assertEqual(berechne_wertnote_ed(95).notentext, "Sehr Gut")
        self.assertEqual(berechne_wertnote_ed(70).notentext, "Befriedigend")

    def test_ed_unter_70_punkten_ist_nicht_bestanden(self):
        # Genau die Regel, die ursprünglich fehlte: unter 70 Punkten -> "nicht Bestanden",
        # unabhängig davon, wie "gut" der Wert sonst aussähe.
        for punkte in (69, 50, 36, 35, 1, 0):
            with self.subTest(punkte=punkte):
                note = berechne_wertnote_ed(punkte)
                self.assertEqual(note.abkuerzung, "nB")
                self.assertEqual(note.notentext, "nicht Bestanden")
                self.assertFalse(note.bestanden)
                self.assertEqual(note.punkte, punkte)  # Punktzahl bleibt trotzdem sichtbar

    def test_ed_ungueltige_punktzahl_wirft_fehler(self):
        with self.assertRaises(ValueError):
            berechne_wertnote_ed(101)
        with self.assertRaises(ValueError):
            berechne_wertnote_ed(-1)

    def test_dk_grenzwerte_im_bestandenen_bereich(self):
        # Alle drei Disziplinen jeweils gleich hoch, damit die Summe den Tabellengrenzen entspricht.
        faelle = [
            (100, 100, 100, "V"),   # 300
            (96, 95, 95, "V"),      # 286
            (95, 95, 95, "SG"),     # 285
            (90, 90, 90, "SG"),     # 270
            (90, 89, 90, "G"),      # 269
            (80, 80, 80, "G"),      # 240
            (80, 79, 80, "B"),      # 239
            (70, 70, 70, "B"),      # 210, exakt die Mindestpunktzahl in jeder Disziplin
        ]
        for t, f, b, erwartete_abk in faelle:
            with self.subTest(t=t, f=f, b=b):
                note = berechne_wertnote_dk(t, f, b)
                self.assertEqual(note.abkuerzung, erwartete_abk)
                self.assertTrue(note.bestanden)
                self.assertEqual(note.punkte, t + f + b)

    def test_dk_eine_disziplin_unter_70_ist_nicht_bestanden_trotz_hoher_summe(self):
        # Der ursprünglich gemeldete Fehler: Trümmerfeld und Flächensuche sind exzellent,
        # aber Behältnisstrecke liegt mit 69 Punkten unter der Mindestpunktzahl -> trotz einer
        # Summe von 269 (die für sich allein "Gut" wäre) lautet das Ergebnis "nicht Bestanden".
        note = berechne_wertnote_dk(100, 100, 69)
        self.assertEqual(note.notentext, "nicht Bestanden")
        self.assertEqual(note.abkuerzung, "nB")
        self.assertFalse(note.bestanden)
        self.assertEqual(note.punkte, 269)  # Summe wird weiterhin angezeigt, nur die Note ändert sich

        # Gilt unabhängig davon, welche der drei Disziplinen betroffen ist.
        self.assertFalse(berechne_wertnote_dk(69, 100, 100).bestanden)
        self.assertFalse(berechne_wertnote_dk(100, 69, 100).bestanden)
        self.assertFalse(berechne_wertnote_dk(69, 69, 69).bestanden)

    def test_mindestpunktzahl_konstante_ist_70(self):
        # Regressionsschutz: falls sich die Konstante versehentlich ändert, sollen die
        # Tests oben klar fehlschlagen statt still eine andere Grenze zu prüfen.
        self.assertEqual(MINDESTPUNKTE_JE_DISZIPLIN, 70)

    def test_dk_ungueltige_punktzahl_wirft_fehler(self):
        with self.assertRaises(ValueError):
            berechne_wertnote_dk(101, 50, 50)
        with self.assertRaises(ValueError):
            berechne_wertnote_dk(50, -1, 50)


class TestWertnoteGegenOriginaldatei(unittest.TestCase):
    """Erschöpfender Abgleich gegen die echte Original-Nachschlagetabelle -
    ausschließlich für den Bereich, der laut Originalformel überhaupt erreichbar ist
    (>= 70 Punkte je Disziplin; darunter liefert das Original hart "nicht Bestanden",
    ohne die Tabelle überhaupt nachzuschlagen - das wird oben separat getestet)."""

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(ODS_PATH):
            raise unittest.SkipTest(
                f"Originaldatei nicht gefunden unter '{ODS_PATH}' - Abgleich wird übersprungen. "
                "Pfad über Umgebungsvariable SHS_ODS_PATH setzen, um den Test auszuführen."
            )
        try:
            import pandas as pd  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("pandas nicht installiert - Abgleich wird übersprungen.")

    def test_ed_tabelle_ab_mindestpunktzahl_identisch(self):
        import pandas as pd

        df = pd.read_excel(ODS_PATH, sheet_name="Hilfstabelle Wertnote", engine="odf", header=None)
        ed = df.iloc[4:, [10, 12]].dropna(subset=[10])
        abweichungen = []
        geprueft = 0
        for _, row in ed.iterrows():
            punkte = int(row[10])
            if punkte < MINDESTPUNKTE_JE_DISZIPLIN:
                continue  # unterhalb der Mindestpunktzahl: siehe test_ed_unter_70_punkten_ist_nicht_bestanden
            geprueft += 1
            erwartete_abk = row[12]
            berechnete_abk = berechne_wertnote_ed(punkte).abkuerzung
            if berechnete_abk != erwartete_abk:
                abweichungen.append((punkte, erwartete_abk, berechnete_abk))
        self.assertEqual(
            abweichungen, [], f"{len(abweichungen)} Abweichungen zur Originaltabelle (ED): {abweichungen[:10]}"
        )
        self.assertEqual(geprueft, 100 - MINDESTPUNKTE_JE_DISZIPLIN + 1)

    def test_dk_tabelle_ab_mindestpunktzahl_identisch(self):
        import pandas as pd

        df = pd.read_excel(ODS_PATH, sheet_name="Hilfstabelle Wertnote", engine="odf", header=None)
        dk = df.iloc[4:, [15, 17]].dropna(subset=[15])
        mindestsumme = MINDESTPUNKTE_JE_DISZIPLIN * 3
        abweichungen = []
        geprueft = 0
        for _, row in dk.iterrows():
            punkte = int(row[15])
            if punkte < mindestsumme:
                continue  # bei so geringer Summe wäre ohnehin mind. eine Einzeldisziplin < 70
            geprueft += 1
            erwartete_abk = row[17]
            # Möglichst gleichmäßig auf die drei Disziplinen verteilt (jede <= 100), damit
            # jede Disziplin für sich >= 70 bleibt - Summe bleibt exakt `punkte`.
            basis, rest = divmod(punkte, 3)
            t, f, b = (basis + 1 if i < rest else basis for i in range(3))
            berechnete_abk = berechne_wertnote_dk(t, f, b).abkuerzung
            if berechnete_abk != erwartete_abk:
                abweichungen.append((punkte, erwartete_abk, berechnete_abk))
        self.assertEqual(
            abweichungen, [], f"{len(abweichungen)} Abweichungen zur Originaltabelle (DK): {abweichungen[:10]}"
        )
        self.assertEqual(geprueft, 300 - mindestsumme + 1)


def _wn(punkte: int, bestanden: bool = True):
    """Testhilfe: baut eine Wertnote mit gegebener Gesamtpunktzahl, ohne dass der genaue
    Notentext für die Rangberechnung eine Rolle spielt."""
    from shs_core import Wertnote

    return Wertnote(punkte=punkte, notentext="Test", abkuerzung="T", bestanden=bestanden)


class TestRangliste(unittest.TestCase):
    def test_einfache_rangfolge_ohne_gleichstand(self):
        teilnehmer = [
            Teilnehmerergebnis("1", "A", "DK LK 1", _wn(250)),
            Teilnehmerergebnis("2", "B", "DK LK 1", _wn(280)),
            Teilnehmerergebnis("3", "C", "DK LK 1", _wn(200)),
        ]
        rangliste = berechne_rangliste(teilnehmer)
        by_name = {t.name: t for t in rangliste}
        self.assertEqual(by_name["B"].platzierung, 1)
        self.assertEqual(by_name["A"].platzierung, 2)
        self.assertEqual(by_name["C"].platzierung, 3)
        self.assertTrue(all(t.von_startern == 3 for t in rangliste))

    def test_gleichstand_teilt_sich_platz_und_naechster_rang_ueberspringt(self):
        # Zwei Teilnehmer mit identischer Punktzahl -> beide Platz 1, nächster Rang ist 3 (nicht 2)
        teilnehmer = [
            Teilnehmerergebnis("1", "A", "ED LK 2 Trümmerfeld", _wn(90)),
            Teilnehmerergebnis("2", "B", "ED LK 2 Trümmerfeld", _wn(90)),
            Teilnehmerergebnis("3", "C", "ED LK 2 Trümmerfeld", _wn(85)),
        ]
        rangliste = berechne_rangliste(teilnehmer)
        by_name = {t.name: t for t in rangliste}
        self.assertEqual(by_name["A"].platzierung, 1)
        self.assertEqual(by_name["B"].platzierung, 1)
        self.assertEqual(by_name["C"].platzierung, 3)

    def test_leistungsklassen_werden_getrennt_gerankt(self):
        # Ein Teilnehmer mit niedrigerer Punktzahl in einer anderen LK darf trotzdem Platz 1 sein
        teilnehmer = [
            Teilnehmerergebnis("1", "A", "DK LK 1", _wn(200)),
            Teilnehmerergebnis("2", "B", "DK LK 3", _wn(290)),
            Teilnehmerergebnis("3", "C", "DK LK 3", _wn(250)),
        ]
        rangliste = berechne_rangliste(teilnehmer)
        by_name = {t.name: t for t in rangliste}
        self.assertEqual(by_name["A"].platzierung, 1)
        self.assertEqual(by_name["A"].von_startern, 1)
        self.assertEqual(by_name["B"].platzierung, 1)
        self.assertEqual(by_name["B"].von_startern, 2)
        self.assertEqual(by_name["C"].platzierung, 2)

    def test_nicht_bestandene_bekommen_keine_platzierung_aber_zaehlen_bei_startern(self):
        # Entspricht der Original-Rankingliste: "nicht Bestanden" -> Kürzel "nB" statt einer
        # Platzzahl, aber weiterhin Teil von "Anzahl Starter".
        teilnehmer = [
            Teilnehmerergebnis("1", "A", "DK LK 1", _wn(280, bestanden=True)),
            Teilnehmerergebnis("2", "B", "DK LK 1", _wn(269, bestanden=False)),  # z.B. eine Disziplin < 70
            Teilnehmerergebnis("3", "C", "DK LK 1", _wn(250, bestanden=True)),
        ]
        rangliste = berechne_rangliste(teilnehmer)
        by_name = {t.name: t for t in rangliste}
        self.assertEqual(by_name["A"].platzierung, 1)
        self.assertEqual(by_name["C"].platzierung, 2)
        self.assertIsNone(by_name["B"].platzierung)
        # B hat trotz höherer Punktzahl als C keine bessere (oder überhaupt eine) Platzierung.
        self.assertTrue(all(t.von_startern == 3 for t in rangliste))

    def test_alle_nicht_bestanden_ergibt_keine_platzierungen(self):
        teilnehmer = [
            Teilnehmerergebnis("1", "A", "ED LK 1 Trümmerfeld", _wn(50, bestanden=False)),
            Teilnehmerergebnis("2", "B", "ED LK 1 Trümmerfeld", _wn(60, bestanden=False)),
        ]
        rangliste = berechne_rangliste(teilnehmer)
        self.assertTrue(all(t.platzierung is None for t in rangliste))
        self.assertTrue(all(t.von_startern == 2 for t in rangliste))


if __name__ == "__main__":
    unittest.main(verbosity=2)
