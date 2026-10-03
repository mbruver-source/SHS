"""Fachliche Referenzfälle für die Bewertung (T2, mit Marco abgestimmt am 03.10.2026).

Die erwarteten Werte stammen NICHT aus dem Code, sondern aus der von Marco gegen das Regelwerk
geprüften Referenztabelle (siehe Fortschritt.md, "T2 – Plan"). Bestätigte Regeln:
- Notengrenzen ED 70/80/90/96 und DK 210/240/270/286 gelten für alle Leistungsklassen gleich.
- Mindestens 70 Punkte je Disziplin, gerechnet auf die SUMME aus Suche und Anzeige.
- Disqualifiziert und Abbruch zählen bei "von x Startern" mit, "Keine Teilnahme" nicht.
- Gleichstand: gleicher Platz, der nächste Platz wird übersprungen (1., 2., 2., 4.) - AUSSER
  um Platz 1: dort entscheidet ein Stechen (S1, Marco 03.10.2026): bis zum Eintrag des
  Siegers "Stechen offen", danach Sieger 1., die übrigen Punktgleichen 2.

Zeigt ein Referenzfall eine Abweichung, wird sie mit Marco geklärt - nicht der Test angepasst.

Teil A/B: Wertnoten (shs_core), Teil C: Rangliste über die echte Datenschicht (db), Teil D:
Eigenschaftstests mit hypothesis (werden übersprungen, wenn hypothesis fehlt).
"""

import os
import tempfile
import unittest

from db import (
    NeuerTeilnehmer,
    add_teilnehmer,
    berechne_auswertung,
    eintragen_ergebnis,
    init_db,
    setze_ergebnis_status,
    setze_keine_teilnahme,
    setze_stechen_sieger,
)
from shs_core import (
    Teilnehmerergebnis,
    berechne_rangliste,
    berechne_wertnote_dk,
    berechne_wertnote_ed,
    platz_text,
    stechen_gruppen,
)

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st
except ImportError:  # pragma: no cover - lokal ohne requirements-dev.txt
    given = None

# Reihenfolge der Ergebnisse von schlecht nach gut (für Monotonie-Prüfungen).
_RANG = {"nB": 0, "B": 1, "G": 2, "SG": 3, "V": 4}


# --- Teil A: Einzeldisziplin (Suche 0-60 + Anzeige 0-40) ---------------------------------
ED_FAELLE = [
    # (Nr, Suche, Anzeige, erwartete Abkürzung)
    ("A1", 0, 0, "nB"),
    ("A2", 60, 9, "nB"),     # 69: ein Punkt unter der Schwelle
    ("A2b", 60, 10, "B"),    # 70 nur über die Summe - kein Einzelminimum (Marco 03.10.)
    ("A3", 40, 30, "B"),     # 70: knapp bestanden
    ("A4", 45, 34, "B"),     # 79
    ("A5", 50, 30, "G"),     # 80
    ("A6", 55, 34, "G"),     # 89
    ("A7", 55, 35, "SG"),    # 90
    ("A8", 58, 37, "SG"),    # 95
    ("A9", 58, 38, "V"),     # 96
    ("A10", 60, 40, "V"),    # 100
]

# --- Teil B: Dreikampf (drei Disziplinen je 0-100, jede mindestens 70) --------------------
DK_FAELLE = [
    # (Nr, Trümmer, Fläche, Behältnis, erwartete Abkürzung)
    ("B1", 70, 70, 70, "B"),       # 210
    ("B2", 70, 70, 69, "nB"),      # 209
    ("B3", 100, 100, 69, "nB"),    # 269 - hohe Summe, eine Disziplin unter 70
    ("B4", 79, 80, 80, "B"),       # 239
    ("B5", 80, 80, 80, "G"),       # 240
    ("B6", 90, 90, 89, "G"),       # 269
    ("B7", 90, 90, 90, "SG"),      # 270
    ("B8", 95, 95, 95, "SG"),      # 285
    ("B9", 96, 95, 95, "V"),       # 286
    ("B10", 100, 100, 100, "V"),   # 300
    ("B11", 0, 0, 0, "nB"),
]


class TestReferenzWertnoten(unittest.TestCase):
    def test_einzeldisziplin(self):
        for nr, suche, anzeige, erwartet in ED_FAELLE:
            with self.subTest(nr):
                note = berechne_wertnote_ed(suche + anzeige)
                self.assertEqual(note.abkuerzung, erwartet)
                self.assertEqual(note.bestanden, erwartet != "nB")
                self.assertEqual(note.punkte, suche + anzeige)

    def test_dreikampf(self):
        for nr, truemmer, flaeche, behaeltnis, erwartet in DK_FAELLE:
            with self.subTest(nr):
                note = berechne_wertnote_dk(truemmer, flaeche, behaeltnis)
                self.assertEqual(note.abkuerzung, erwartet)
                self.assertEqual(note.bestanden, erwartet != "nB")
                self.assertEqual(note.punkte, truemmer + flaeche + behaeltnis)

    def test_ed_mehr_punkte_nie_schlechter_und_bestanden_ab_70(self):
        # Vollständig statt zufällig (alle Werte 0-100) - braucht kein hypothesis.
        vorher = None
        for punkte in range(0, 101):
            note = berechne_wertnote_ed(punkte)
            self.assertEqual(note.bestanden, punkte >= 70)
            if vorher is not None:
                self.assertGreaterEqual(_RANG[note.abkuerzung], _RANG[vorher.abkuerzung], punkte)
            vorher = note


# --- Teil C: Rangliste über die Datenschicht (ED LK 1 Trümmerfeld) -----------------------
class TestReferenzRangliste(unittest.TestCase):
    def setUp(self):
        fd, self.pfad = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        os.remove(self.pfad)
        self.conn = init_db(self.pfad)
        self._nr = 0

    def tearDown(self):
        self.conn.close()
        os.remove(self.pfad)

    def _ed(self, name, punkte=None, disziplin="Trümmerfeld"):
        """ED LK 1; punkte als (Suche, Anzeige) oder None (noch kein Ergebnis)."""
        self._nr += 1
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname=name, vorname="T", rufname_hund="H", art="ED", stufe=1,
            disziplin=disziplin, startnummer=self._nr))
        if punkte is not None:
            eintragen_ergebnis(self.conn, tid, disziplin, *punkte)
        return tid

    def _auswertung(self):
        fertig, ausstehend = berechne_auswertung(self.conn)
        return {t.name.split(",")[0]: t for t in fertig}, [t["nachname"] for t in ausstehend]

    def _c1_grundfall(self):
        # Anna und Ben punktgleich auf Platz 2 (Platz 1 bewusst eindeutig, siehe S1 unten).
        self._ed("Sieger", (60, 38))   # 98
        self._ed("Anna", (58, 37))     # 95
        self._ed("Ben", (55, 40))      # 95
        self._ed("Clara", (55, 35))    # 90

    def test_c1_gleichstand_teilt_platz_naechster_wird_uebersprungen(self):
        self._c1_grundfall()
        fertig, _ = self._auswertung()
        self.assertEqual(
            {n: (t.platzierung, t.von_startern) for n, t in fertig.items()},
            {"Sieger": (1, 4), "Anna": (2, 4), "Ben": (2, 4), "Clara": (4, 4)},
        )

    def test_c1b_gleichstand_um_platz_1_verlangt_stechen(self):
        """S1 (Marco 03.10.2026): Gleichstand um Platz 1 -> "Stechen offen"; nach dem
        Eintrag des Siegers wird er 1., die übrigen Punktgleichen 2., danach geht es normal
        weiter. Ändern sich die Punkte und der Gleichstand fällt weg, zählt die Markierung
        nicht mehr."""
        anna = self._ed("Anna", (58, 37))   # 95
        ben = self._ed("Ben", (55, 40))     # 95
        self._ed("Clara", (55, 35))         # 90
        fertig, _ = self._auswertung()
        self.assertEqual([(fertig[n].platzierung, fertig[n].stechen) for n in ("Anna", "Ben")],
                         [(1, "offen"), (1, "offen")])
        self.assertEqual(platz_text(fertig["Anna"]), "1. von 3 (Stechen offen)")
        self.assertEqual(list(stechen_gruppen(list(fertig.values()))), ["ED LK 1 Trümmerfeld"])

        setze_stechen_sieger(self.conn, ben, [anna, ben])
        fertig, _ = self._auswertung()
        self.assertEqual(
            {n: (t.platzierung, t.stechen) for n, t in fertig.items()},
            {"Ben": (1, "gewonnen"), "Anna": (2, None), "Clara": (3, None)},
        )
        self.assertEqual(platz_text(fertig["Ben"]), "1. von 3 (nach Stechen)")
        self.assertEqual(platz_text(fertig["Anna"]), "2. von 3")

        # Zurück auf "offen".
        setze_stechen_sieger(self.conn, None, [anna, ben])
        fertig, _ = self._auswertung()
        self.assertEqual({fertig["Anna"].stechen, fertig["Ben"].stechen}, {"offen"})

        # Punkte ändern sich, Gleichstand weg: alte Markierung bleibt wirkungslos.
        setze_stechen_sieger(self.conn, ben, [anna, ben])
        eintragen_ergebnis(self.conn, ben, "Trümmerfeld", 55, 39)  # 94
        fertig, _ = self._auswertung()
        self.assertEqual((fertig["Anna"].platzierung, fertig["Anna"].stechen), (1, None))
        self.assertEqual((fertig["Ben"].platzierung, fertig["Ben"].stechen), (2, None))

    def test_c1c_stechen_bei_drei_punktgleichen_entscheidet_nur_den_sieger(self):
        ids = [self._ed(n, (58, 37)) for n in ("Anna", "Ben", "Clara")]  # je 95
        self._ed("Dieter", (55, 35))  # 90
        setze_stechen_sieger(self.conn, ids[2], ids)
        fertig, _ = self._auswertung()
        self.assertEqual(
            {n: t.platzierung for n, t in fertig.items()},
            {"Clara": 1, "Anna": 2, "Ben": 2, "Dieter": 4},
        )

    def test_c2_nicht_bestanden_ohne_platz_zaehlt_mit(self):
        self._c1_grundfall()
        self._ed("Dieter", (60, 9))  # 69
        fertig, _ = self._auswertung()
        self.assertIsNone(fertig["Dieter"].platzierung)
        self.assertEqual(fertig["Dieter"].wertnote.abkuerzung, "nB")
        self.assertEqual({t.von_startern for t in fertig.values()}, {5})

    def test_c3_c4_disqualifiziert_und_abbruch_ohne_platz_zaehlen_mit(self):
        self._c1_grundfall()
        emil = self._ed("Emil", None)
        frieda = self._ed("Frieda", None)
        setze_ergebnis_status(self.conn, emil, disqualifiziert=True, abbruch=False)
        setze_ergebnis_status(self.conn, frieda, disqualifiziert=False, abbruch=True)
        fertig, ausstehend = self._auswertung()
        self.assertEqual(ausstehend, [])
        for name, abk in (("Emil", "DISQ"), ("Frieda", "ABBR")):
            with self.subTest(name):
                self.assertIsNone(fertig[name].platzierung)
                self.assertFalse(fertig[name].bestanden)
                self.assertEqual(fertig[name].wertnote.abkuerzung, abk)
        self.assertEqual({t.von_startern for t in fertig.values()}, {6})

    def test_c5_keine_teilnahme_zaehlt_nirgends(self):
        self._c1_grundfall()
        gerd = self._ed("Gerd", (60, 40))  # hätte gewonnen
        setze_keine_teilnahme(self.conn, gerd, True)
        fertig, ausstehend = self._auswertung()
        self.assertNotIn("Gerd", fertig)
        self.assertNotIn("Gerd", ausstehend)
        self.assertEqual(fertig["Sieger"].platzierung, 1)
        self.assertEqual({t.von_startern for t in fertig.values()}, {4})

    def test_c6_unvollstaendiger_dreikampf_ist_ausstehend_und_zaehlt_nicht(self):
        self._c1_grundfall()
        dk = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Hanna", vorname="T", rufname_hund="H", art="DK", stufe=1, startnummer=99))
        eintragen_ergebnis(self.conn, dk, "Trümmerfeld", 60, 40)
        eintragen_ergebnis(self.conn, dk, "Flächensuche", 60, 40)
        fertig, ausstehend = self._auswertung()
        self.assertIn("Hanna", ausstehend)
        self.assertNotIn("Hanna", fertig)
        self.assertEqual({t.von_startern for t in fertig.values()}, {4})

    def test_c7_disqualifiziert_ignoriert_eingetragene_punkte(self):
        self._c1_grundfall()
        ida = self._ed("Ida", (60, 40))  # 100 Punkte eingetragen ...
        setze_ergebnis_status(self.conn, ida, disqualifiziert=True, abbruch=False)  # ... aber DQ
        fertig, _ = self._auswertung()
        self.assertIsNone(fertig["Ida"].platzierung)
        self.assertEqual(fertig["Ida"].wertnote.abkuerzung, "DISQ")
        self.assertEqual(fertig["Sieger"].platzierung, 1)

    def test_c8_getrennte_ranglisten_je_leistungsklasse_und_disziplin(self):
        self._ed("Truemmer", (55, 35), disziplin="Trümmerfeld")
        self._ed("Flaeche", (55, 35), disziplin="Flächensuche")
        fertig, _ = self._auswertung()
        for name in ("Truemmer", "Flaeche"):
            with self.subTest(name):
                self.assertEqual((fertig[name].platzierung, fertig[name].von_startern), (1, 1))
        self.assertNotEqual(fertig["Truemmer"].leistungsklasse, fertig["Flaeche"].leistungsklasse)

    def test_c9_notengrenzen_gelten_in_allen_leistungsklassen_gleich(self):
        """Marco 03.10.2026: gleiche Grenzen für LK 1-3 - gleiche Punkte, gleiche Note."""
        for stufe in (1, 2, 3):
            tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
                nachname=f"ED{stufe}", vorname="T", rufname_hund="H", art="ED", stufe=stufe,
                disziplin="Flächensuche", startnummer=10 + stufe))
            eintragen_ergebnis(self.conn, tid, "Flächensuche", 50, 30)  # 80 -> G
            dk = add_teilnehmer(self.conn, NeuerTeilnehmer(
                nachname=f"DK{stufe}", vorname="T", rufname_hund="H", art="DK", stufe=stufe,
                startnummer=20 + stufe))
            for disziplin in ("Trümmerfeld", "Flächensuche", "Behältnisstrecke"):
                eintragen_ergebnis(self.conn, dk, disziplin, 55, 35)  # 270 -> SG
        fertig, _ = self._auswertung()
        for stufe in (1, 2, 3):
            with self.subTest(stufe=stufe):
                self.assertEqual(fertig[f"ED{stufe}"].wertnote.abkuerzung, "G")
                self.assertEqual(fertig[f"DK{stufe}"].wertnote.abkuerzung, "SG")


# --- Teil D: Eigenschaftstests (hypothesis) -----------------------------------------------
@unittest.skipIf(given is None, "hypothesis nicht installiert (requirements-dev.txt)")
class TestBewertungEigenschaften(unittest.TestCase):
    if given is not None:
        punkte = st.integers(min_value=0, max_value=100)

        @settings(max_examples=300, deadline=None)
        @given(punkte, punkte, punkte, st.integers(min_value=0, max_value=2), st.integers(min_value=1, max_value=100))
        def test_dk_mehr_punkte_in_einer_disziplin_nie_schlechter(self, t, f, b, welche, plus):
            werte = [t, f, b]
            vorher = berechne_wertnote_dk(*werte)
            werte[welche] = min(100, werte[welche] + plus)
            nachher = berechne_wertnote_dk(*werte)
            self.assertGreaterEqual(_RANG[nachher.abkuerzung], _RANG[vorher.abkuerzung])

        @settings(max_examples=300, deadline=None)
        @given(punkte, punkte, punkte)
        def test_dk_bestanden_genau_wenn_jede_disziplin_mindestens_70(self, t, f, b):
            note = berechne_wertnote_dk(t, f, b)
            self.assertEqual(note.bestanden, min(t, f, b) >= 70)
            self.assertEqual(note.punkte, t + f + b)

        @settings(max_examples=200, deadline=None)
        @given(st.lists(st.tuples(st.sampled_from(["LK1", "LK2"]), punkte), max_size=25))
        def test_rangliste_vollstaendig_und_konsistent(self, eintraege):
            teilnehmer = [
                Teilnehmerergebnis(id=str(i), name=f"T{i}", leistungsklasse=lk,
                                   wertnote=berechne_wertnote_ed(p))
                for i, (lk, p) in enumerate(eintraege)
            ]
            ergebnis = berechne_rangliste(teilnehmer)
            # Jeder Teilnehmer genau einmal.
            self.assertEqual(sorted(t.id for t in ergebnis), sorted(t.id for t in teilnehmer))
            for lk in {"LK1", "LK2"}:
                gruppe = [t for t in ergebnis if t.leistungsklasse == lk]
                for t in gruppe:
                    self.assertEqual(t.von_startern, len(gruppe))
                    self.assertEqual(t.platzierung is None, not t.bestanden)
                bestandene = [t for t in gruppe if t.bestanden]
                for a in bestandene:
                    # Platz = 1 + Anzahl der Bestandenen mit MEHR Punkten (1., 2., 2., 4.).
                    besser = sum(1 for b in bestandene if b.gesamtpunkte > a.gesamtpunkte)
                    self.assertEqual(a.platzierung, besser + 1)

        @settings(max_examples=100, deadline=None)
        @given(st.sampled_from([(True, False), (False, True), (True, True)]), punkte)
        def test_disqualifiziert_oder_abbruch_nie_bestanden(self, status, p):
            fd, pfad = tempfile.mkstemp(suffix=".sqlite")
            os.close(fd)
            os.remove(pfad)
            conn = init_db(pfad)
            try:
                tid = add_teilnehmer(conn, NeuerTeilnehmer(
                    nachname="X", vorname="Y", rufname_hund="H", art="ED", stufe=1,
                    disziplin="Trümmerfeld", startnummer=1))
                eintragen_ergebnis(conn, tid, "Trümmerfeld", min(p, 60), max(0, min(p - 60, 40)))
                setze_ergebnis_status(conn, tid, disqualifiziert=status[0], abbruch=status[1])
                fertig, _ = berechne_auswertung(conn)
                self.assertEqual(len(fertig), 1)
                self.assertFalse(fertig[0].bestanden)
                self.assertIsNone(fertig[0].platzierung)
            finally:
                conn.close()
                os.remove(pfad)


if __name__ == "__main__":
    unittest.main()
