"""Tests für pdf_export.py - prüft nicht nur "läuft ohne Fehler", sondern liest den
erzeugten PDF-Text wieder ein und kontrolliert die wichtigsten Inhalte (Werte, die
"nicht Bestanden"-Regel, die LK-abhängigen Verleitungs-Hinweise/Behältnis-Positionen)."""

import math
import os
import tempfile
import unittest

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

from db import (
    NeuerTeilnehmer,
    add_teilnehmer,
    add_zeitplan_pause,
    add_zeitplan_pruefungsblock,
    add_zeitplan_richter,
    eintragen_ergebnis,
    init_db,
    set_veranstaltung,
    setze_ergebnis_status,
)
import pdf_export


class TestImpfungHervorheben(unittest.TestCase):
    """Codeprüfung 22.09. (M5): echter Datumsvergleich statt Stringvergleich - braucht
    weder pypdf noch eine Datenbank."""

    def test_abgelaufen_gueltig_und_unbekannt(self):
        hervorheben = pdf_export._impfung_hervorheben
        self.assertFalse(hervorheben("2027-01-01", "2026-09-19"))
        self.assertTrue(hervorheben("2026-01-01", "2026-09-19"))
        self.assertTrue(hervorheben(None, "2026-09-19"))
        self.assertTrue(hervorheben("unleserlich", "2026-09-19"))
        # Vorher falsch: "30.08.2026" < "2026-09-19" ist als String False -> nicht rot.
        self.assertTrue(hervorheben("30.08.2026", "2026-09-19"))
        self.assertFalse(hervorheben("01.01.2027", "2026-09-19"))
        # Ohne Prüfungsdatum lässt sich "abgelaufen" nicht beurteilen.
        self.assertFalse(hervorheben("2026-01-01", None))


class TestRegelKonsistenz(unittest.TestCase):
    """Codeprüfung 22.09., G10: die Bewertungsregeln stehen bewusst an mehreren Stellen
    (shs_core-Tabellen, gedruckte Wertnoten-Bänder im Bewertungsbogen, CHECK-Constraints
    im db.SCHEMA, Überschriften "max. 60/40 P.") - statt sie umzubauen, schlagen diese
    Tests Alarm, sobald eine Stelle geändert wird und die anderen nicht mitziehen. Braucht
    weder pypdf noch eine Datenbank (prüft direkt die Tabellendaten/den Quelltext)."""

    # Erwartete Höchstpunktzahlen je Disziplin - bewusst hier als eigene Konstante, damit
    # eine Änderung an nur einer Produktionsstelle auffällt.
    SUCHE_MAX = 60
    ANZEIGE_MAX = 40

    @staticmethod
    def _band(text: str) -> tuple[int, int]:
        """"60 – 58" -> (60, 58)."""
        oben, unten = (int(teil.strip()) for teil in text.split("–"))
        return oben, unten

    def _pruefe_baender(self, zeile: list[str], maximum: int, untergrenzen: list[int]):
        """Zeile = [Beschriftung, V, SG, G, B, n.B.]: die Bänder müssen bei `maximum`
        beginnen, lückenlos absteigen, bei 0 enden und die erwarteten Untergrenzen haben."""
        baender = [self._band(zelle) for zelle in zeile[1:]]
        self.assertEqual(baender[0][0], maximum, zeile)
        self.assertEqual(baender[-1][1], 0, zeile)
        for (_, unten), (oben_naechstes, _) in zip(baender, baender[1:]):
            self.assertEqual(oben_naechstes, unten - 1, zeile)
        self.assertEqual([unten for _, unten in baender[:-1]], untergrenzen, zeile)

    def test_gedruckte_ed_baender_passen_zu_shs_core(self):
        from shs_core import MINDESTPUNKTE_JE_DISZIPLIN, PUNKTE_MAX, WERTNOTEN_ED, Disziplinart

        maximum = PUNKTE_MAX[Disziplinart.EINZELDISZIPLIN]
        self.assertEqual(maximum, self.SUCHE_MAX + self.ANZEIGE_MAX)
        daten = pdf_export._wertungsnoten_tabelle_ed()._cellvalues
        kopf, suche, anzeige, gesamt = daten

        schwellen = [schwelle for schwelle, _, _ in WERTNOTEN_ED]
        self.assertEqual(schwellen[-1], MINDESTPUNKTE_JE_DISZIPLIN)
        self.assertEqual(gesamt[0], f"von {maximum} P")
        self.assertEqual(
            [abk for _, _, abk in WERTNOTEN_ED], [zelle.split(" =")[0] for zelle in kopf[1:5]]
        )
        self._pruefe_baender(gesamt, maximum, schwellen)
        # Prozent-Kopfzeile (bei ED entsprechen Punkte von 100 genau Prozent).
        self.assertEqual(kopf[1], f"V = mind. {schwellen[0]}%")
        prozent_untergrenzen = [int(zelle.split("–")[1].rstrip("%")) for zelle in kopf[2:5]]
        self.assertEqual(prozent_untergrenzen, schwellen[1:])

        self.assertEqual(suche[0], "SUCHE")
        self.assertEqual(anzeige[0], "ANZEIGE")
        # Teilleistungs-Bänder = aufgerundeter Prozentsatz der Teil-Höchstpunktzahl.
        # (ANZEIGE "V" war bis 22.09. ab 38 gedruckt - auf Marcos Entscheidung auf 39
        # korrigiert, jetzt ohne Ausnahme.)
        def untergrenzen(teil_max: int) -> list[int]:
            return [math.ceil(schwelle * teil_max / maximum) for schwelle in schwellen]

        self._pruefe_baender(suche, self.SUCHE_MAX, untergrenzen(self.SUCHE_MAX))
        self._pruefe_baender(anzeige, self.ANZEIGE_MAX, untergrenzen(self.ANZEIGE_MAX))

    def test_gedruckte_dk_baender_passen_zu_shs_core(self):
        from shs_core import PUNKTE_MAX, WERTNOTEN_DK, Disziplinart

        maximum = PUNKTE_MAX[Disziplinart.DREIKAMPF]
        self.assertEqual(maximum, 3 * PUNKTE_MAX[Disziplinart.EINZELDISZIPLIN])
        kopf, gesamt = pdf_export._wertungsnoten_tabelle_dk()._cellvalues
        self.assertEqual(kopf[1:5], [abk for _, _, abk in WERTNOTEN_DK])
        self.assertEqual(gesamt[0], f"von {maximum} P")
        self._pruefe_baender(gesamt, maximum, [schwelle for schwelle, _, _ in WERTNOTEN_DK])

    def test_hoechstpunkte_im_db_schema(self):
        import re

        import db

        grenzen = re.findall(r"(suche|anzeige)_\w+ INTEGER CHECK \(\w+ BETWEEN 0 AND (\d+)\)", db.SCHEMA)
        self.assertEqual(len(grenzen), 2 * len(db.DISZIPLIN_SPALTEN))
        for art, grenze in grenzen:
            erwartet = self.SUCHE_MAX if art == "suche" else self.ANZEIGE_MAX
            self.assertEqual(int(grenze), erwartet, art)

    def test_hoechstpunkte_in_bewertungsbogen_ueberschrift(self):
        import inspect
        import re

        quelltext = inspect.getsource(pdf_export)
        self.assertEqual(
            re.findall(r"Suchleistung des Hundes \(max\. (\d+) P\.\)", quelltext), [str(self.SUCHE_MAX)]
        )
        self.assertEqual(
            re.findall(r"Anzeigeleistung des Hundes \(max\. (\d+) P\.\)", quelltext), [str(self.ANZEIGE_MAX)]
        )


def _text(pfad: str) -> str:
    reader = PdfReader(pfad)
    return "\n".join(seite.extract_text() for seite in reader.pages)


def test_etikett_masse_entsprechen_der_physischen_etikettengroesse():
    """Regressionstest für den gemeldeten Fehler: jedes Etikett muss exakt der
    physischen Etikettengröße entsprechen (aktuell vom Verein vorgegeben: Lang = 17 cm,
    Hoch = 2 cm) - vorher waren es ungewollt rund 17,8 cm Breite und eine von reportlab
    automatisch bestimmte, deutlich kleinere Höhe als 2 cm. Läuft unabhängig von
    PdfReader/pypdf, da direkt an den Bausteinen (Spaltenbreiten/Zeilenhöhen) geprüft,
    aus denen die Etiketten-Tabelle gebaut wird - reportlab selbst ist bereits über
    requirements.txt vorhanden."""
    import math

    from reportlab.lib.units import mm

    assert math.isclose(sum(pdf_export._ETIKETT_SPALTEN), pdf_export.ETIKETT_BREITE_MM * mm)
    assert math.isclose(sum(pdf_export._ETIKETT_ZEILEN), pdf_export.ETIKETT_HOEHE_MM * mm)


class TestPositionsSkizzen(unittest.TestCase):
    """Positions-Skizzen nach den neuen Vorlagen (pdf/, 24.09.) - direkt an den
    reportlab-Zeichnungen geprüft, läuft daher auch ohne pypdf."""

    def test_behaeltnis_skizze_hat_je_lk_die_richtige_anzahl_nummern(self):
        from reportlab.graphics.shapes import String

        for stufe, anzahl in pdf_export._BEHAELTNIS_POSITIONEN.items():
            with self.subTest(stufe=stufe):
                zeichnung = pdf_export._skizze_behaeltnisse(anzahl)
                nummern = [e.text for e in zeichnung.contents if isinstance(e, String)]
                self.assertEqual(nummern, [str(i) for i in range(1, anzahl + 1)])
        self.assertEqual(pdf_export._BEHAELTNIS_POSITIONEN, {1: 6, 2: 8, 3: 10})

    def test_skizzen_passen_in_die_linke_spalte(self):
        from reportlab.lib.units import mm

        for zeichnung in (pdf_export._skizze_truemmerfeld(), pdf_export._skizze_flaeche(),
                          pdf_export._skizze_behaeltnisse(10)):
            self.assertLessEqual(zeichnung.width, 100 * mm)


@unittest.skipIf(PdfReader is None, "pypdf nicht installiert - PDF-Inhaltsprüfung wird übersprungen")
class TestPdfExport(unittest.TestCase):
    def setUp(self):
        fd, self.db_pfad = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        os.remove(self.db_pfad)
        self.conn = init_db(self.db_pfad)
        set_veranstaltung(self.conn, verein="SGV Köppern e.V.", datum="2026-09-19", ort="Köppern")

        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.db_pfad):
            os.remove(self.db_pfad)

    def _pfad(self, name: str) -> str:
        return os.path.join(self.tmpdir, name)

    def test_bewertungsbogen_ed_enthaelt_stammdaten_und_punktzahl(self):
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Holst", vorname="Katrin", rufname_hund="Freda",
            art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=1,
            verein="SGV Köppern e.V.",
            gegenstand_1="Schlüsselbund", gegenstand_1_disziplin="Trümmerfeld",
        ))
        eintragen_ergebnis(self.conn, tid, "Trümmerfeld", suche=58, anzeige=38)

        pfad = self._pfad("bogen_ed.pdf")
        pdf_export.erstelle_bewertungsbogen_pdf(self.conn, tid, pfad)
        self.assertTrue(os.path.exists(pfad))
        text = _text(pfad)

        self.assertIn("ED - LK 1", text)
        self.assertIn("Holst, Katrin", text)
        self.assertIn("Schlüsselbund", text)
        self.assertIn("58", text)  # Suchleistung
        self.assertIn("38", text)  # Anzeigeleistung
        self.assertIn("96", text)  # Gesamtpunktzahl (58+38)
        # ED LK 1 hat laut Original-Vorlage KEINEN Verleitungs-Hinweis
        self.assertNotIn("Spielzeugverleitung", text)
        # Fußzeile: Datum als TT.MM.JJJJ (Marcos Wunsch 22.09.).
        self.assertIn("Datum: 19.09.2026", text)

    def test_bewertungsbogen_mit_reportlab_sonderzeichen_in_freitext_bricht_nicht_ab(self):
        # QS-Fund (19./20.09.): Paragraph() aus reportlab parst seinen Text als kleine
        # Mini-Auszeichnungssprache (<b>, <i>, <br/> ...). Freitextfelder wie Zwingername,
        # Rufname, Verein oder Gegenstand sind aber ganz normaler, von Nutzern frei
        # eingegebener Text - enthält so ein Feld z.B. ein einzelnes "<" oder einen nicht
        # als Markup gemeinten Tag-Namen, ließ das den PDF-Export vorher mit einem
        # ValueError abstürzen (siehe _p_wert() in pdf_export.py). Dieser Test reproduziert
        # genau das und prüft zusätzlich, dass die Sonderzeichen unverändert (nicht als
        # könnte man aus vom Nutzer eingegebenem "&" ein sichtbares "&amp;" auf dem PDF
        # machen) im extrahierten PDF-Text erscheinen.
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Muster & Sohn", vorname="<b>Max</wrongtag", rufname_hund="Rex</br>",
            art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=1,
            verein="H&K Sportverein", zwingername="vom Wald <i>Sued",
            gegenstand_1="Schlüssel <b>bund", gegenstand_1_disziplin="Trümmerfeld",
        ))
        eintragen_ergebnis(self.conn, tid, "Trümmerfeld", suche=58, anzeige=38)

        pfad = self._pfad("bogen_sonderzeichen.pdf")
        pdf_export.erstelle_bewertungsbogen_pdf(self.conn, tid, pfad)  # darf nicht werfen
        text = _text(pfad)
        self.assertIn("Muster & Sohn", text)
        self.assertIn("vom Wald <i>Sued", text)
        self.assertIn("Schlüssel <b>bund", " ".join(text.split()))  # Gegenstand steht in schmaler Spalte, darf umbrechen
        self.assertNotIn("&amp;", text)
        self.assertNotIn("&lt;", text)

        # Die Sammel-PDF darf durch EINEN betroffenen Teilnehmer nicht komplett blockiert
        # werden (vorher: ein einziger "kaputter" Teilnehmer verhinderte den Export für alle).
        sammel_pfad = self._pfad("alle_sonderzeichen.pdf")
        anzahl = pdf_export.erstelle_alle_bewertungsboegen_pdf(self.conn, sammel_pfad)
        self.assertEqual(anzahl, 1)

    def test_ergebnisliste_etiketten_und_zeitplan_mit_sonderzeichen_brechen_nicht_ab(self):
        # Dieselbe Sonderzeichen-Absicherung wie im obigen Test, aber für die drei weiteren
        # Stellen, an denen Freitext (Name, Verein, Rufname, Pausenbezeichnung) OHNE Umweg
        # über _wert() direkt in einen Paragraph eingebaut wurde (name_info bei den
        # Etiketten, "namen" der noch ausstehenden Teilnehmer in der Ergebnisliste, sowie
        # eine frei benannte Zeitplan-Pause).
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Muster & Sohn", vorname="<i>Max", rufname_hund="Rex<br/>",
            art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=1,
            verein="H&K Sportverein",
        ))
        # Bewusst OHNE Ergebnis -> landet in der "noch ausstehend"-Liste der Ergebnisliste.

        pdf_export.erstelle_ergebnisliste_pdf(self.conn, self._pfad("ergebnisliste_sz.pdf"))
        pdf_export.erstelle_ergebnisliste_etiketten_pdf(self.conn, self._pfad("etiketten_sz.pdf"))

        richter_id = add_zeitplan_richter(self.conn, "Richter A")
        add_zeitplan_pause(self.conn, richter_id, bezeichnung="Mittagspause <b>&amp;", dauer_minuten=30)
        pdf_export.erstelle_zeitplan_pdf(self.conn, self._pfad("zeitplan_sz.pdf"))  # darf nicht werfen

    def test_bewertungsbogen_ed_ohne_gegenstand_zuordnung_zeigt_platzhalter(self):
        # Ohne explizite Zuordnung ("frei", der Default) erscheint der Gegenstand NICHT auf
        # dem Bogen - es gibt bewusst keine automatische Zuordnung mehr nach Position.
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Holst", vorname="Katrin", rufname_hund="Freda",
            art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=1,
            gegenstand_1="Schlüsselbund",  # keine gegenstand_1_disziplin gesetzt -> frei
        ))
        pfad = self._pfad("bogen_ed_frei.pdf")
        pdf_export.erstelle_bewertungsbogen_pdf(self.conn, tid, pfad)
        text = _text(pfad)
        self.assertNotIn("Schlüsselbund", text)
        self.assertIn("Zu suchender Gegenstand:", text)

    def test_bewertungsbogen_dk_gegenstand_zuordnung_frei_waehlbar(self):
        # Gegenstand 2 wird der Trümmerfeld-Disziplin zugeordnet (nicht Position 1) und
        # Gegenstand 3 bleibt "frei" - beides muss sich korrekt in der PDF niederschlagen:
        # Gegenstand 2 erscheint auf der Trümmerfeld-Seite, Gegenstand 3 auf keiner
        # Disziplin-Seite und ohne Disziplin-Zusatz in der Kopf-Auflistung.
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Kleemann", vorname="Doris", rufname_hund="Dorie",
            art="DK", stufe=1, startnummer=2, verein="RHV Musterstadt",
            gegenstand_1="Holzklotz", gegenstand_1_disziplin="Flächensuche",
            gegenstand_2="Lederhandschuh", gegenstand_2_disziplin="Trümmerfeld",
            gegenstand_3="Kunststoffdose",  # frei
        ))
        pfad = self._pfad("bogen_dk_zuordnung.pdf")
        pdf_export.erstelle_bewertungsbogen_pdf(self.conn, tid, pfad)
        text = _text(pfad)

        self.assertIn("1. zu suchender Gegenstand: Holzklotz (Flächensuche)", text)
        self.assertIn("2. zu suchender Gegenstand: Lederhandschuh (Trümmerfeld)", text)
        self.assertIn("3. zu suchender Gegenstand: Kunststoffdose", text)
        # Kein Disziplin-Zusatz für den freien Gegenstand 3
        self.assertNotIn("Kunststoffdose (", text)
        # "Lederhandschuh" erscheint als Zu-suchender-Gegenstand auf der Trümmerfeld-Seite
        self.assertIn("Zu suchender Gegenstand: Lederhandschuh", " ".join(text.split()))
        self.assertIn("Zu suchender Gegenstand: Holzklotz", " ".join(text.split()))

    def test_bewertungsbogen_dk_lk3_verleitungen_und_behaeltnis_positionen(self):
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Kleemann", vorname="Doris", rufname_hund="Dorie",
            art="DK", stufe=3, startnummer=2, verein="RHV Musterstadt",
            gegenstand_1="Holzklotz", gegenstand_2="Lederhandschuh", gegenstand_3="Kunststoffdose",
        ))
        eintragen_ergebnis(self.conn, tid, "Trümmerfeld", suche=55, anzeige=35)
        eintragen_ergebnis(self.conn, tid, "Flächensuche", suche=52, anzeige=33)
        eintragen_ergebnis(self.conn, tid, "Behältnisstrecke", suche=50, anzeige=32)

        pfad = self._pfad("bogen_dk.pdf")
        pdf_export.erstelle_bewertungsbogen_pdf(self.conn, tid, pfad)
        text = _text(pfad)

        self.assertIn("LK 3", text)
        self.assertIn("drei Suchgegenstände", text)
        # LK3-spezifische Verleitungs-Hinweise aus den Original-Vorlagen
        self.assertIn("5 Futterverleitungen", text)
        self.assertIn("1 Material-/baugleicher Gegenstand", text)
        # LK3 Behältnisstrecke hat 10 gezeichnete, nummerierte Behälter (LK1: 6, LK2: 8, LK3: 10)
        self.assertIn("1 2 3 4 5 6 7 8 9 10", " ".join(text.split()))
        # Gesamtpunktzahl (90+85+82=257) und Prädikat "G" (240-269 -> Gut)
        self.assertIn("257", text)
        self.assertIn("(G)", text)

    def test_bewertungsbogen_dk_nicht_bestanden_zeigt_trotzdem_summe(self):
        # Regressionsfall aus der Fehlerkorrektur: eine Disziplin unter 70 Punkten trotz
        # hoher Summe - der Bogen soll die Summe weiterhin zeigen (Prädikat wird nicht
        # extra als "nicht Bestanden" ausgeschrieben, das steht in der Ergebnisliste).
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Vogel", vorname="Nils", rufname_hund="Rex",
            art="DK", stufe=1, startnummer=3,
        ))
        eintragen_ergebnis(self.conn, tid, "Trümmerfeld", suche=60, anzeige=40)
        eintragen_ergebnis(self.conn, tid, "Flächensuche", suche=60, anzeige=40)
        eintragen_ergebnis(self.conn, tid, "Behältnisstrecke", suche=35, anzeige=34)  # 69 < 70

        pfad = self._pfad("bogen_dk_nb.pdf")
        pdf_export.erstelle_bewertungsbogen_pdf(self.conn, tid, pfad)
        text = _text(pfad)
        self.assertIn("269", text)  # Summe wird trotzdem angezeigt

    def test_bewertungsbogen_ohne_ergebnis_bleibt_leer_ohne_fehler(self):
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Muster", vorname="Jonas", rufname_hund="Bello",
            art="ED", stufe=2, disziplin="Behältnisstrecke", startnummer=4,
        ))
        pfad = self._pfad("bogen_leer.pdf")
        pdf_export.erstelle_bewertungsbogen_pdf(self.conn, tid, pfad)
        self.assertTrue(os.path.exists(pfad))
        text = _text(pfad)
        self.assertIn("Muster, Jonas", text)
        # LK2 Behältnisstrecke hat 8 gezeichnete Behälter
        self.assertIn("1 2 3 4 5 6 7 8 Gegenstand:", " ".join(text.split()))

    # Neue Vorlagen (pdf/, 24.09.): lange Namen reizen den Platz aus - die festen
    # Seitenumfänge müssen auch dann halten. Die Werte sind die realistischen Grenzfälle,
    # mit denen die Verifikation (24.09.) DK-Seite 2 vor dem Fix auf eine 3. Seite schob.
    _LANGE_NAMEN = dict(
        nachname="Schmidt-Leutheusser-Schnarrenberger", vorname="Sabine-Charlotte", rufname_hund="Freda",
        zwingername="Crazy Cooper of the Silver Highland Moor",
        verein="Hundesportverein Musterstadt-Nord e.V.",
    )

    def test_bewertungsbogen_dk_hat_immer_genau_zwei_seiten(self):
        # Seitenaufteilung wie in der Vorlage: Seite 1 = Stammdaten + Trümmerfeld +
        # Fußzeile, Seite 2 = Kopfzeile "LK x HF/Hund" + Fläche + Behältnis + Gesamt.
        for stufe in (1, 2, 3):
            with self.subTest(stufe=stufe):
                tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
                    **self._LANGE_NAMEN, art="DK", stufe=stufe, startnummer=stufe,
                    gegenstand_1="Schlüsselbund", gegenstand_1_disziplin="Trümmerfeld",
                    gegenstand_2="Futterbeutel mit Reißverschluss, blau gestreift",
                    gegenstand_2_disziplin="Flächensuche",
                    gegenstand_3="Dose", gegenstand_3_disziplin="Behältnisstrecke",
                ))
                for disziplin in ("Trümmerfeld", "Flächensuche", "Behältnisstrecke"):
                    eintragen_ergebnis(self.conn, tid, disziplin, suche=55, anzeige=36)
                pfad = self._pfad(f"bogen_dk_seiten_{stufe}.pdf")
                pdf_export.erstelle_bewertungsbogen_pdf(self.conn, tid, pfad)
                seiten = [s.extract_text() for s in PdfReader(pfad).pages]

                self.assertEqual(len(seiten), 2)
                self.assertIn("Bewertung Trümmerfeld", seiten[0])
                self.assertIn("austragender Verein", seiten[0])
                self.assertNotIn("Bewertung Flächensuche", seiten[0])
                self.assertIn(f"LK {stufe}", seiten[1])
                self.assertIn("Schmidt-Leutheusser-Schnarrenberger", seiten[1])
                self.assertIn("Bewertung Flächensuche", seiten[1])
                self.assertIn("Bewertung Behältnisstrecke", seiten[1])
                self.assertIn("von 300 P", seiten[1])
                # Punkte-Band-Tabelle nur noch 2x (unter Trümmerfeld und Behältnis)
                self.assertEqual("".join(seiten).count("von 100 P"), 2)

    def test_bewertungsbogen_ed_alle_varianten_einseitig(self):
        startnummer = 0
        for stufe in (1, 2, 3):
            for disziplin in ("Trümmerfeld", "Flächensuche", "Behältnisstrecke"):
                with self.subTest(stufe=stufe, disziplin=disziplin):
                    startnummer += 1
                    tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
                        **self._LANGE_NAMEN, art="ED", stufe=stufe, disziplin=disziplin,
                        startnummer=startnummer,
                    ))
                    eintragen_ergebnis(self.conn, tid, disziplin, suche=55, anzeige=36)
                    setze_ergebnis_status(self.conn, tid, disqualifiziert=True, abbruch=False)
                    pfad = self._pfad(f"bogen_ed_{startnummer}.pdf")
                    pdf_export.erstelle_bewertungsbogen_pdf(self.conn, tid, pfad)
                    self.assertEqual(len(PdfReader(pfad).pages), 1)

    def test_sammel_pdf_seitenzahl_dk_zwei_ed_eine(self):
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Dk", vorname="X", rufname_hund="H", art="DK", stufe=3, startnummer=1))
        for i, disziplin in enumerate(("Trümmerfeld", "Behältnisstrecke"), start=2):
            add_teilnehmer(self.conn, NeuerTeilnehmer(
                nachname=f"Ed{i}", vorname="X", rufname_hund="H", art="ED", stufe=3,
                disziplin=disziplin, startnummer=i))
        pfad = self._pfad("sammel_seiten.pdf")
        self.assertEqual(pdf_export.erstelle_alle_bewertungsboegen_pdf(self.conn, pfad), 3)
        self.assertEqual(len(PdfReader(pfad).pages), 4)

    def test_sammel_pdf_enthaelt_alle_teilnehmer(self):
        for i in range(3):
            add_teilnehmer(self.conn, NeuerTeilnehmer(
                nachname=f"Person{i}", vorname="X", rufname_hund="H",
                art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=i + 1,
            ))
        pfad = self._pfad("sammel.pdf")
        anzahl = pdf_export.erstelle_alle_bewertungsboegen_pdf(self.conn, pfad)
        self.assertEqual(anzahl, 3)
        text = _text(pfad)
        for i in range(3):
            self.assertIn(f"Person{i}, X", text)

    def test_sammel_pdf_ohne_teilnehmer_erzeugt_leeren_hinweis_statt_fehler(self):
        pfad = self._pfad("sammel_leer.pdf")
        anzahl = pdf_export.erstelle_alle_bewertungsboegen_pdf(self.conn, pfad)
        self.assertEqual(anzahl, 0)
        self.assertTrue(os.path.exists(pfad))

    def test_ergebnisliste_zeigt_nb_ohne_platzzahl(self):
        a = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Gut", vorname="A", rufname_hund="H", art="DK", stufe=1, startnummer=1))
        b = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Schlecht", vorname="B", rufname_hund="H", art="DK", stufe=1, startnummer=2))
        for disziplin, punkte in [("Trümmerfeld", (60, 40)), ("Flächensuche", (60, 40)), ("Behältnisstrecke", (50, 30))]:
            eintragen_ergebnis(self.conn, a, disziplin, *punkte)
        eintragen_ergebnis(self.conn, b, "Trümmerfeld", suche=60, anzeige=40)
        eintragen_ergebnis(self.conn, b, "Flächensuche", suche=60, anzeige=40)
        eintragen_ergebnis(self.conn, b, "Behältnisstrecke", suche=35, anzeige=34)  # nicht bestanden

        pfad = self._pfad("ergebnisliste.pdf")
        pdf_export.erstelle_ergebnisliste_pdf(self.conn, pfad)
        text = _text(pfad)
        self.assertIn("Gut, A", text)
        self.assertIn("Schlecht, B", text)
        self.assertIn("nicht Bestanden", text)
        self.assertIn("nB", text)
        # Titel: Datum als TT.MM.JJJJ (Marcos Wunsch 22.09.).
        self.assertIn("(19.09.2026)", text)
        self.assertNotIn("2026-09-19", text)

    def test_ergebnisliste_zeigt_ausstehende_teilnehmer(self):
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Wartend", vorname="C", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1))
        pfad = self._pfad("ergebnisliste_offen.pdf")
        pdf_export.erstelle_ergebnisliste_pdf(self.conn, pfad)
        text = _text(pfad)
        self.assertIn("Wartend, C", text)
        self.assertIn("Noch ohne vollständiges Ergebnis", text)

    def test_ergebnisliste_nur_gewaehlte_leistungsklasse(self):
        """Druck-Button im Auswertungs-Tab (Nutzerwunsch 23.09.) übergibt die im Filter
        gewählte Leistungsklasse - nur diese erscheint dann in der PDF."""
        a = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Flaeche", vorname="A", rufname_hund="H", art="ED", stufe=1,
            disziplin="Flächensuche", startnummer=1))
        b = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Truemmer", vorname="B", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=2))
        eintragen_ergebnis(self.conn, a, "Flächensuche", suche=58, anzeige=38)
        eintragen_ergebnis(self.conn, b, "Trümmerfeld", suche=55, anzeige=35)

        pfad = self._pfad("ergebnisliste_lk.pdf")
        pdf_export.erstelle_ergebnisliste_pdf(self.conn, pfad, "ED LK 1 Flächensuche")
        text = _text(pfad)
        self.assertIn("Flaeche, A", text)
        self.assertNotIn("Truemmer, B", text)
        self.assertNotIn("Trümmerfeld", text)

    def test_etiketten_ergebnisliste_enthaelt_werte_ohne_seitentitel(self):
        a = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Siegreich", vorname="A", rufname_hund="Bella", verein="VPS Schwanheim",
            art="DK", stufe=1, startnummer=1))
        for disziplin, punkte in [("Trümmerfeld", (60, 40)), ("Flächensuche", (60, 40)), ("Behältnisstrecke", (50, 30))]:
            eintragen_ergebnis(self.conn, a, disziplin, *punkte)

        pfad = self._pfad("ergebnisliste_etiketten.pdf")
        pdf_export.erstelle_ergebnisliste_etiketten_pdf(self.conn, pfad)
        self.assertTrue(os.path.exists(pfad))
        text = _text(pfad)

        # Zeile 1: austragender Verein, Art/LK, Punkte je Disziplin, Gesamtpunktzahl.
        self.assertIn("SGV Köppern e.V.", text)  # austragender Verein (siehe setUp)
        self.assertIn("DK LK 1", text)
        self.assertIn("Trümmer: 100", text)
        self.assertIn("Fläche: 100", text)
        self.assertIn("Behältnis: 80", text)
        self.assertIn("Gesamt: 280", text)
        # Zeile 2: Datum, Name, eigener Verein, Rufname des Hundes.
        self.assertIn("19.09.2026", text)  # Anzeige TT.MM.JJJJ (22.09.)
        self.assertNotIn("2026-09-19", text)
        self.assertIn("Siegreich, A, VPS Schwanheim, Bella", text)
        # Platzhalter-Feld zum späteren Abstempeln/Unterschreiben.
        self.assertIn("SH-R", text)
        # Kein Seitentitel/keine Spaltenköpfe wie bei der normalen Ergebnisliste.
        self.assertNotIn("Ergebnisliste", text)
        self.assertNotIn("Platz", text)
        self.assertNotIn("Start-Nr.", text)

    def test_etiketten_ergebnisliste_zeigt_bindestrich_fuer_fehlende_disziplin(self):
        # ED: nur EINE Disziplin wird geprüft - die anderen beiden sollen "-" zeigen statt
        # fälschlich 0 Punkte zu suggerieren.
        b = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Moebus", vorname="Reni", rufname_hund="Rex", verein="SGV Köppern e.V.",
            art="ED", stufe=2, disziplin="Trümmerfeld", startnummer=2))
        eintragen_ergebnis(self.conn, b, "Trümmerfeld", suche=50, anzeige=30)

        pfad = self._pfad("ergebnisliste_etiketten_ed.pdf")
        pdf_export.erstelle_ergebnisliste_etiketten_pdf(self.conn, pfad)
        text = _text(pfad)
        self.assertIn("Trümmer: 80", text)
        self.assertIn("Fläche: -", text)
        self.assertIn("Behältnis: -", text)
        self.assertIn("Gesamt: 80", text)

    def test_etiketten_ergebnisliste_zeigt_auch_unvollstaendige_teilnehmer_mit_leeren_feldern(self):
        # Auch ohne vollständiges Ergebnis soll ein Etikett entstehen (z.B. um es schon
        # vorab zu beschriften) - die Punktzahl-Felder bleiben dann aber leer, statt
        # (falsche) Werte oder einen Bindestrich zu zeigen.
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Wartend", vorname="C", rufname_hund="H", verein="SGV Köppern e.V.",
            art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=1))
        pfad = self._pfad("ergebnisliste_etiketten_offen.pdf")
        pdf_export.erstelle_ergebnisliste_etiketten_pdf(self.conn, pfad)
        self.assertTrue(os.path.exists(pfad))
        text = _text(pfad)
        self.assertIn("Wartend, C", text)
        self.assertIn("Trümmer:", text)
        self.assertIn("Fläche:", text)
        self.assertIn("Behältnis:", text)
        self.assertIn("Gesamt:", text)
        self.assertNotIn("Trümmer: -", text)
        self.assertNotIn("Gesamt: None", text)

    def test_leere_ergebnisliste_zeigt_stammdaten_ohne_werte(self):
        a = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Holst", vorname="Katrin", rufname_hund="Freda", verein="SGV Köppern e.V.",
            art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=2))
        b = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Kleemann", vorname="Doris", rufname_hund="Dorie", verein="RHV Musterstadt",
            art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=1))
        # a hat bereits ein digitales Ergebnis - das leere Formular soll die Werte
        # trotzdem NICHT vorausfüllen (Sinn ist die papierbasierte Neu-Erfassung).
        eintragen_ergebnis(self.conn, a, "Trümmerfeld", suche=58, anzeige=38)

        pfad = self._pfad("ergebnisliste_leer.pdf")
        pdf_export.erstelle_leere_ergebnisliste_pdf(self.conn, pfad)
        self.assertTrue(os.path.exists(pfad))
        text = _text(pfad)

        self.assertIn("Formular zum Ausfüllen", text)
        self.assertIn("Holst, Katrin", text)
        self.assertIn("Kleemann, Doris", text)
        self.assertIn("SGV Köppern e.V.", text)
        # Trotz bereits erfasstem Ergebnis für Katrin Holst: keine Punktzahl im Formular.
        self.assertNotIn("96", text)
        self.assertNotIn("58", text)

    def test_leere_ergebnisliste_ohne_teilnehmer_erzeugt_hinweis_statt_fehler(self):
        pfad = self._pfad("ergebnisliste_leer_ohne_teilnehmer.pdf")
        pdf_export.erstelle_leere_ergebnisliste_pdf(self.conn, pfad)
        self.assertTrue(os.path.exists(pfad))
        text = _text(pfad)
        self.assertIn("Keine Teilnehmer erfasst.", text)

    def test_statistik_zeigt_kopfangaben_und_praedikat_matrix(self):
        set_veranstaltung(
            self.conn, verein="SGV Köppern e.V.", datum="2026-09-19", ort="Köppern",
            vereins_nr="19010", pruefungsnummer="P-2026-04",
            wertungsrichter_1="A. Muster", wertungsrichter_2="B. Beispiel",
            wertungsrichter_3="C. Vorbild", wertungsrichter_4="D. Vorlage", wertungsrichter_5="E. Original",
            pruefungsleiter="Katja Bruver",
        )
        a = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="A", vorname="A", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1))
        eintragen_ergebnis(self.conn, a, "Trümmerfeld", suche=58, anzeige=38)  # 96 -> Vorzüglich
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="B", vorname="B", rufname_hund="H", art="DK", stufe=2, startnummer=2))  # ausstehend

        pfad = self._pfad("statistik.pdf")
        pdf_export.erstelle_statistik_pdf(self.conn, pfad)
        text = _text(pfad)

        # Titel und Kopf-Angaben (Zusatzfelder aus set_veranstaltung).
        self.assertIn("Spürhundsport (SHS)", text)
        self.assertIn("19010", text)
        self.assertIn("P-2026-04", text)
        self.assertIn("A. Muster", text)
        self.assertIn("B. Beispiel", text)
        self.assertIn("C. Vorbild", text)
        self.assertIn("D. Vorlage", text)
        self.assertIn("E. Original", text)
        self.assertIn("Katja Bruver", text)
        self.assertIn("Samstag, 19. September 2026", text)
        # Prädikat-Matrix: Spaltenüberschriften und die Zeile für den erreichten Wert.
        # Nutzerwunsch (21.09., "Kosmetik"): die Spalten wurden verbreitert und die
        # Kopfschrift verkleinert (siehe _stat_spalte_breite() in pdf_export.py), damit
        # "Trümmerfeld"/"Flächensuche"/"Behältnisstrecke" NICHT mehr mitten im Wort
        # umbrechen - text.replace("\n", "") ist dadurch nicht mehr zwingend nötig, bleibt
        # hier aber defensiv stehen (schadet nicht, falls künftig doch wieder umgebrochen
        # würde).
        text_ohne_umbrueche = text.replace("\n", "")
        self.assertIn("Dreikampf", text)
        self.assertIn("Einzeldisziplin", text)
        self.assertIn("Trümmerfeld", text_ohne_umbrueche)
        self.assertIn("Flächensuche", text_ohne_umbrueche)
        self.assertIn("Behältnisstrecke", text_ohne_umbrueche)
        self.assertIn("Vorzüglich (V)", text)
        self.assertIn("nicht Bestanden (nB)", text)
        # Der ausstehende Teilnehmer B fließt nicht in die Zählung ein.
        self.assertNotIn("B, B", text)
        # Jugendliche-Zusatztabelle (Nutzerwunsch 21.09., siehe eigener Test unten) ist
        # immer Teil der Statistik-PDF, auch ohne Jugendliche im Termin.
        self.assertIn("Jugendliche", text)

    def test_statistik_zaehlt_disqualifikation_und_abbruch_in_eigenen_zeilen(self):
        # Nutzerwunsch (21.09.): die Prädikat-Matrix bekommt zwei neue Zeilen
        # "Disqualifikation"/"Abbruch", die pro Art/LK-Spalte zählen wie viele
        # Teilnehmer den jeweiligen Status haben - wie die bestehenden Prädikat-Zeilen.
        disq = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Diskval", vorname="D", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1))
        setze_ergebnis_status(self.conn, disq, disqualifiziert=True, abbruch=False)
        abbr = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Abbrecher", vorname="A", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=2))
        setze_ergebnis_status(self.conn, abbr, disqualifiziert=False, abbruch=True)

        pfad = self._pfad("statistik_disq_abbruch.pdf")
        pdf_export.erstelle_statistik_pdf(self.conn, pfad)
        text = _text(pfad)
        # Die Zeilenbeschriftung "Disqualifikation (DISQ)" passt seit der Spaltenbreiten-
        # Anpassung (21.09., siehe test_statistik_zeigt_kopfangaben_und_praedikat_matrix
        # oben) einzeilig in die Prädikat-Spalte, kein Umbruch mehr nötig.
        self.assertIn("Disqualifikation (DISQ)", text)
        self.assertIn("Abbruch (ABBR)", text)
        # Beide Teilnehmer fließen NICHT in die "ausstehend"-Behandlung, sondern werden
        # als eigene Zeile gezählt - kein Absturz und keine falsche Wertnote.
        self.assertNotIn("Diskval", text)  # Namen erscheinen nicht in der Statistik-PDF

    def _dk_mit_vollen_punkten(self, nachname: str, startnummer: int) -> int:
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname=nachname, vorname="A", rufname_hund="H", verein="SGV Köppern e.V.",
            art="DK", stufe=1, startnummer=startnummer))
        for disziplin, punkte in [("Trümmerfeld", (60, 40)), ("Flächensuche", (60, 40)), ("Behältnisstrecke", (50, 30))]:
            eintragen_ergebnis(self.conn, tid, disziplin, *punkte)
        return tid

    def test_bewertungsbogen_dk_disqualifiziert_zeigt_status_statt_wertnote(self):
        # Codeprüfung 22.09. (M3): trotz vollständiger, weiter gespeicherter Punkte darf
        # der Bogen keine berechnete Wertnote ("280 (SG)") zeigen - Einzelpunkte bleiben
        # als Dokumentation der Richterbewertung stehen (Marcos Entscheidung).
        tid = self._dk_mit_vollen_punkten("Diskval", 1)
        setze_ergebnis_status(self.conn, tid, disqualifiziert=True, abbruch=False)

        pfad = self._pfad("bogen_dk_disq.pdf")
        pdf_export.erstelle_bewertungsbogen_pdf(self.conn, tid, pfad)
        text = _text(pfad)
        self.assertIn("Disqualifiziert (DISQ)", text)
        self.assertNotIn("(SG)", text)
        self.assertNotIn("280", text)
        self.assertIn("100", text)  # Einzelpunkte Trümmer/Fläche bleiben sichtbar
        self.assertEqual(len(PdfReader(pfad).pages), 2)

    def test_bewertungsbogen_ed_abbruch_zeigt_punkte_und_status(self):
        # Nachtrag zu M3 (Marcos Entscheidung 22.09.): wie beim DK-Bogen bleiben die
        # Punkte stehen, zusätzlich erscheint der Status - ohne zusätzliche Seite.
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Abbrecher", vorname="A", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1))
        eintragen_ergebnis(self.conn, tid, "Trümmerfeld", suche=58, anzeige=38)
        normal_pfad = self._pfad("bogen_ed_normal.pdf")
        pdf_export.erstelle_bewertungsbogen_pdf(self.conn, tid, normal_pfad)
        self.assertNotIn("ERGEBNIS", _text(normal_pfad))

        setze_ergebnis_status(self.conn, tid, disqualifiziert=False, abbruch=True)
        pfad = self._pfad("bogen_ed_abbr.pdf")
        pdf_export.erstelle_bewertungsbogen_pdf(self.conn, tid, pfad)
        text = _text(pfad)
        self.assertIn("ERGEBNIS", text)
        self.assertIn("Abbruch (ABBR)", text)
        self.assertIn("96", text)
        self.assertEqual(len(PdfReader(pfad).pages), len(PdfReader(normal_pfad).pages))

    def test_etiketten_bei_disqualifikation_nur_status_ohne_punkte(self):
        # Codeprüfung 22.09. (M3, Marcos Entscheidung): auf dem offiziellen Etikett keine
        # Punkte, die nicht zählen, und kein irreführendes "Gesamt: 0".
        tid = self._dk_mit_vollen_punkten("Diskval", 1)
        setze_ergebnis_status(self.conn, tid, disqualifiziert=True, abbruch=False)

        pfad = self._pfad("etiketten_disq.pdf")
        pdf_export.erstelle_ergebnisliste_etiketten_pdf(self.conn, pfad)
        text = _text(pfad)
        # Einzeilig - kein Umbruch im Gesamt-Feld (dank kleinerer Schrift, siehe
        # _ETIKETT_FELD_STATUS).
        self.assertIn("Gesamt: DISQ", text)
        self.assertIn("Trümmer: -", text)
        self.assertIn("Fläche: -", text)
        self.assertIn("Behältnis: -", text)
        self.assertNotIn("Trümmer: 100", text)
        self.assertNotIn("Gesamt: 0", text)

    def test_etiketten_bei_abbruch_gesamt_einzeilig(self):
        # "Gesamt: ABBR" ist der breiteste Fall (50,2 von 53,5 pt in 7 pt) - bricht er
        # um, taucht er in der Textextraktion nicht mehr zusammenhängend auf.
        tid = self._dk_mit_vollen_punkten("Abbrecher", 1)
        setze_ergebnis_status(self.conn, tid, disqualifiziert=False, abbruch=True)

        pfad = self._pfad("etiketten_abbr.pdf")
        pdf_export.erstelle_ergebnisliste_etiketten_pdf(self.conn, pfad)
        self.assertIn("Gesamt: ABBR", _text(pfad))

    def test_ergebnisliste_bei_abbruch_bindestrich_statt_null_punkte(self):
        tid = self._dk_mit_vollen_punkten("Abbrecher", 1)
        setze_ergebnis_status(self.conn, tid, disqualifiziert=False, abbruch=True)

        pfad = self._pfad("ergebnisliste_abbr.pdf")
        pdf_export.erstelle_ergebnisliste_pdf(self.conn, pfad)
        text = _text(pfad)
        # pypdf liefert jede Tabellenzelle als eigene Zeile.
        zeilen = [z.strip() for z in text.splitlines()]
        self.assertIn("Abbruch (ABBR)", zeilen)
        self.assertIn("–", zeilen)
        self.assertNotIn("0", zeilen)

    def test_statistik_zaehlt_jugendliche_getrennt(self):
        # Nutzerwunsch (21.09., Rückmeldung "Statistik/Jugendliche"): Teilnehmer, die zum
        # Prüfungsdatum noch unter 18 Jahre alt sind, werden in einer eigenen Zusatztabelle
        # gezählt - unabhängig vom erreichten Prädikat.
        set_veranstaltung(self.conn, verein="Verein", datum="2026-09-19", ort="Ort")
        jugendlich = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Jung", vorname="J", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1, geburtsdatum="2009-09-20"))  # am 19.09.2026 noch 16
        eintragen_ergebnis(self.conn, jugendlich, "Trümmerfeld", suche=58, anzeige=38)
        erwachsen = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Alt", vorname="A", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=2, geburtsdatum="2000-01-01"))
        eintragen_ergebnis(self.conn, erwachsen, "Trümmerfeld", suche=58, anzeige=38)
        ohne_geburtsdatum = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Unbekannt", vorname="U", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=3))
        eintragen_ergebnis(self.conn, ohne_geburtsdatum, "Trümmerfeld", suche=58, anzeige=38)

        pfad = self._pfad("statistik_jugendliche.pdf")
        pdf_export.erstelle_statistik_pdf(self.conn, pfad)
        text = _text(pfad)

        self.assertIn("Jugendliche", text)
        # Nur EIN Jugendlicher wurde gezählt (Alt und Unbekannt zählen nicht mit) - die
        # Namen selbst erscheinen (wie bei der Prädikat-Matrix) nicht in der PDF, deshalb
        # hier indirekt über die Werte-Zeile der Jugendlichen-Tabelle (12 Spalten, davon
        # genau eine "1") geprüft.
        jugend_index = text.index("Anzahl")
        werte_zeile = text[jugend_index:jugend_index + 60]
        self.assertEqual(werte_zeile.count("1"), 1)

    def test_statistik_ohne_teilnehmer_erzeugt_leere_matrix_statt_fehler(self):
        pfad = self._pfad("statistik_leer.pdf")
        pdf_export.erstelle_statistik_pdf(self.conn, pfad)
        self.assertTrue(os.path.exists(pfad))
        text = _text(pfad)
        self.assertIn("Prädikat", text)

    def test_pruefungsleitung_uebersicht_zeigt_stammdaten_und_gebuehr_je_art(self):
        set_veranstaltung(
            self.conn, verein="SGV Köppern e.V.", datum="2026-09-19", ort="Köppern",
            pruefungsgebuehr_ed="12,00", pruefungsgebuehr_dk="18,00",
        )
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Schurig", vorname="Sandra", rufname_hund="Molly", verein="HSV Trailfreunde",
            chip_nr="276095300089410", art="DK", stufe=1, startnummer=1))
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Moebus", vorname="Reni", rufname_hund="Rex", verein="SGV Köppern e.V.",
            chip_nr="981189900092729", art="ED", stufe=3, disziplin="Behältnisstrecke", startnummer=2))

        pfad = self._pfad("pruefungsleitung.pdf")
        pdf_export.erstelle_pruefungsleitung_uebersicht_pdf(self.conn, pfad)
        self.assertTrue(os.path.exists(pfad))
        text = _text(pfad)

        self.assertIn("Übersicht für Prüfungsleitung", text)
        self.assertIn("Schurig", text)
        self.assertIn("276095300089410", text)
        self.assertIn("18,00 €", text)  # DK-Gebühr
        self.assertIn("Moebus", text)
        self.assertIn("12,00 €", text)  # ED-Gebühr
        # Nutzerwunsch (21.09.): "Abgabe Sportbeitrag" wurde ersatzlos entfernt, "Kontrolle
        # Impfpass erledigt?" ist jetzt die digitale Spalte "Impfpass gültig bis" (siehe
        # eigener Test unten für die Datums-/Hervorhebungslogik). "bezahlt?" selbst wird
        # weiterhin aus dem gepflegten Bezahlt-Status befüllt; beide Teilnehmer hier sind
        # (Standardwert) noch nicht als bezahlt markiert, also erscheint dort noch kein "Ja".
        self.assertIn("bezahlt?", text)
        self.assertIn("Impfpass", text)
        self.assertIn("gültig bis", text)
        self.assertNotIn("Kontrolle", text)
        self.assertNotIn("Sportbeitrag", text)
        self.assertNotIn("Ja", text)
        self.assertNotIn("Nein", text)

    def test_pruefungsleitung_uebersicht_zeigt_impfpass_datum(self):
        # Nutzerwunsch (21.09.): digitaler Impfpass mit Datum statt leerem Ankreuzfeld -
        # aus dem bestehenden Stammdatenfeld tollwutimpfung_bis befüllt (siehe
        # Modulkommentar in pdf_export.py). Drei Fälle: gültig (nach dem Prüfungstag),
        # abgelaufen (vor dem Prüfungstag) und gar nicht hinterlegt.
        set_veranstaltung(self.conn, verein="Verein", datum="2026-09-19", ort="Ort")
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Gueltig", vorname="G", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1, tollwutimpfung_bis="2027-01-01"))
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Abgelaufen", vorname="A", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=2, tollwutimpfung_bis="2026-01-01"))
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Unbekannt", vorname="U", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=3))

        pfad = self._pfad("pruefungsleitung_impfpass.pdf")
        pdf_export.erstelle_pruefungsleitung_uebersicht_pdf(self.conn, pfad)
        text = _text(pfad)

        self.assertIn("01.01.2027", text)  # gültig, im kurzen TT.MM.JJJJ-Format
        self.assertIn("01.01.2026", text)  # abgelaufen, wird trotzdem angezeigt
        self.assertIn("–", text)  # kein Datum hinterlegt

    def test_pruefungsleitung_uebersicht_zeigt_bezahlt_status(self):
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Bezahlt", vorname="B", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1, bezahlt=True))
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Offen", vorname="O", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=2, bezahlt=False))
        pfad = self._pfad("pruefungsleitung_bezahlt.pdf")
        pdf_export.erstelle_pruefungsleitung_uebersicht_pdf(self.conn, pfad)
        text = _text(pfad)
        self.assertIn("Bezahlt", text)
        self.assertIn("Ja", text)

    def test_pruefungsleitung_uebersicht_ohne_gebuehr_zeigt_leeres_feld(self):
        # Noch keine Prüfungsgebühr in den Veranstaltungsdaten hinterlegt.
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Wartend", vorname="C", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1))
        pfad = self._pfad("pruefungsleitung_ohne_gebuehr.pdf")
        pdf_export.erstelle_pruefungsleitung_uebersicht_pdf(self.conn, pfad)
        text = _text(pfad)
        self.assertIn("Wartend", text)
        self.assertNotIn("€", text)

    def test_pruefungsleitung_uebersicht_ohne_teilnehmer_zeigt_hinweis(self):
        pfad = self._pfad("pruefungsleitung_leer.pdf")
        pdf_export.erstelle_pruefungsleitung_uebersicht_pdf(self.conn, pfad)
        self.assertTrue(os.path.exists(pfad))
        text = _text(pfad)
        self.assertIn("Keine Teilnehmer erfasst.", text)

    def test_chipnummernliste_zeigt_start_nr_name_hund_und_chip_nr_sortiert_nach_startnummer(self):
        # Nutzerwunsch (21.09.): eigener, kompakter Export nur mit Start-Nr./Name/Hund/
        # Chip-Nr., sortiert nach Startnummer (Anwendungsfall: Abgleich am Prüfungstag,
        # z.B. an einer Chip-Scanner-Station) - bewusst unabhängig von der "Übersicht für
        # Prüfungsleitung" (die nach Name sortiert).
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Zweiter", vorname="Z", rufname_hund="Rex",
            chip_nr="981189900092729", art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=2))
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Erster", vorname="E", rufname_hund="Molly",
            chip_nr="276095300089410", art="DK", stufe=1, startnummer=1))

        pfad = self._pfad("chipliste.pdf")
        pdf_export.erstelle_chipnummernliste_pdf(self.conn, pfad)
        self.assertTrue(os.path.exists(pfad))
        text = _text(pfad)

        self.assertIn("Chipnummernliste", text)
        self.assertIn("Erster", text)
        self.assertIn("276095300089410", text)
        self.assertIn("Molly", text)
        self.assertIn("Zweiter", text)
        self.assertIn("981189900092729", text)
        # Nach Startnummer sortiert: Start-Nr. 1 (Erster) muss VOR Start-Nr. 2 (Zweiter)
        # im extrahierten Text erscheinen, obwohl "Zweiter" alphabetisch vor "Erster"
        # zuerst angelegt wurde.
        self.assertLess(text.index("Erster"), text.index("Zweiter"))

    def test_chipnummernliste_ohne_startnummer_stuerzt_nicht_ab(self):
        # Die Startnummer ist optional (INTEGER UNIQUE, kann NULL sein) - ein Teilnehmer
        # ohne Startnummer darf die Sortierung nicht mit einem TypeError abbrechen lassen.
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="OhneStartnummer", vorname="O", rufname_hund="H",
            art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=None))
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="MitStartnummer", vorname="M", rufname_hund="H",
            art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=1))

        pfad = self._pfad("chipliste_ohne_startnummer.pdf")
        pdf_export.erstelle_chipnummernliste_pdf(self.conn, pfad)
        text = _text(pfad)
        self.assertIn("OhneStartnummer", text)
        self.assertIn("MitStartnummer", text)

    def test_chipnummernliste_ohne_teilnehmer_zeigt_hinweis(self):
        pfad = self._pfad("chipliste_leer.pdf")
        pdf_export.erstelle_chipnummernliste_pdf(self.conn, pfad)
        self.assertTrue(os.path.exists(pfad))
        text = _text(pfad)
        self.assertIn("Keine Teilnehmer erfasst.", text)

    def test_leistungsrichter_bedarf_berechnet_einheiten_und_richterzahl(self):
        # 2x DK (je 3 Einheiten) + 2x ED (je 1 Einheit) = 8 Einheiten -> 1 Richter (36/Richter).
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="A", vorname="A", rufname_hund="H", art="DK", stufe=1, startnummer=1))
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="B", vorname="B", rufname_hund="H", art="DK", stufe=1, startnummer=2))
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="C", vorname="C", rufname_hund="H", art="ED", stufe=2,
            disziplin="Trümmerfeld", startnummer=3))
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="D", vorname="D", rufname_hund="H", art="ED", stufe=3,
            disziplin="Behältnisstrecke", startnummer=4))

        pfad = self._pfad("leistungsrichter.pdf")
        pdf_export.erstelle_leistungsrichter_bedarf_pdf(self.conn, pfad)
        self.assertTrue(os.path.exists(pfad))
        text = _text(pfad)
        self.assertIn("Richter-Bedarf", text)
        self.assertIn("Gesamteinheiten: 8", text)
        self.assertIn("Benötigte Richter", text)
        self.assertIn(": 1", text)

    def test_leistungsrichter_bedarf_rundet_auf(self):
        # 13x DK = 39 Einheiten -> über 36, also 2 Richter benötigt (aufgerundet).
        for i in range(13):
            add_teilnehmer(self.conn, NeuerTeilnehmer(
                nachname=f"T{i}", vorname="X", rufname_hund="H", art="DK", stufe=1, startnummer=i + 1))
        pfad = self._pfad("leistungsrichter_aufrunden.pdf")
        pdf_export.erstelle_leistungsrichter_bedarf_pdf(self.conn, pfad)
        text = _text(pfad)
        self.assertIn("Gesamteinheiten: 39", text)
        self.assertIn("aufgerundet): 2", text)

    def test_leistungsrichter_bedarf_ohne_teilnehmer_zeigt_null(self):
        pfad = self._pfad("leistungsrichter_leer.pdf")
        pdf_export.erstelle_leistungsrichter_bedarf_pdf(self.conn, pfad)
        self.assertTrue(os.path.exists(pfad))
        text = _text(pfad)
        self.assertIn("Keine Teilnehmer erfasst.", text)
        self.assertIn("Gesamteinheiten: 0", text)
        self.assertIn("aufgerundet): 0", text)

    def test_zeitplan_pdf_zeigt_seite_je_richter_mit_start_und_endzeiten(self):
        set_veranstaltung(self.conn, verein="SGV Köppern e.V.", datum="2026-09-19", zeitplan_start="09:00")
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Holst", vorname="Katrin", rufname_hund="Freda", verein="SGV Köppern e.V.",
            art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=1))
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Berger", vorname="Uwe", rufname_hund="Findus", verein="SGV Köppern e.V.",
            art="ED", stufe=3, disziplin="Flächensuche", startnummer=2))
        r1 = add_zeitplan_richter(self.conn, name="Herr Meier")
        r2 = add_zeitplan_richter(self.conn, name="Frau Schmidt")
        add_zeitplan_pruefungsblock(self.conn, r1, art="ED", stufe=1, disziplin="Trümmerfeld", dauer_minuten=8)
        add_zeitplan_pruefungsblock(self.conn, r2, art="ED", stufe=3, disziplin="Flächensuche", dauer_minuten=12)

        pfad = self._pfad("zeitplan.pdf")
        pdf_export.erstelle_zeitplan_pdf(self.conn, pfad)
        self.assertTrue(os.path.exists(pfad))
        reader = PdfReader(pfad)
        self.assertEqual(len(reader.pages), 2)  # eine Seite je Richter

        text = _text(pfad)
        self.assertIn("Zeitplan – Herr Meier", text)
        self.assertIn("Zeitplan – Frau Schmidt", text)
        self.assertIn("Holst, Katrin", text)
        self.assertIn("Berger, Uwe", text)
        self.assertIn("09:00", text)
        self.assertIn("09:08", text)  # Ende des ersten (einzigen) Blocks bei Herr Meier
        self.assertIn("09:12", text)  # Ende des Blocks bei Frau Schmidt (12 Minuten)

    def test_zeitplan_pdf_pause_verschiebt_folgende_startzeit(self):
        set_veranstaltung(self.conn, verein="V", datum="2026-09-19", zeitplan_start="09:00")
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Holst", vorname="Katrin", rufname_hund="Freda",
            art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=1))
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Berger", vorname="Uwe", rufname_hund="Findus",
            art="DK", stufe=2, startnummer=2))
        rid = add_zeitplan_richter(self.conn, name="Herr Meier")
        add_zeitplan_pause(self.conn, rid, dauer_minuten=15, bezeichnung="Kaffeepause")
        add_zeitplan_pruefungsblock(self.conn, rid, art="ED", stufe=1, disziplin="Trümmerfeld", dauer_minuten=10)

        pfad = self._pfad("zeitplan_pause.pdf")
        pdf_export.erstelle_zeitplan_pdf(self.conn, pfad)
        text = _text(pfad)
        self.assertIn("Kaffeepause", text)
        self.assertIn("09:15", text)  # Ende der Pause = Beginn des anschließenden Blocks
        self.assertIn("09:25", text)  # Ende des Prüfungsblocks nach der Pause

    def test_zeitplan_pdf_ohne_richter_zeigt_hinweis(self):
        pfad = self._pfad("zeitplan_leer.pdf")
        pdf_export.erstelle_zeitplan_pdf(self.conn, pfad)
        self.assertTrue(os.path.exists(pfad))
        text = _text(pfad)
        self.assertIn("Zeitplan", text)
        self.assertIn("keine Richter", text)

    def test_zeitplan_pdf_richter_ohne_eintraege_zeigt_hinweis(self):
        add_zeitplan_richter(self.conn, name="Herr Ohne Plan")
        pfad = self._pfad("zeitplan_richter_leer.pdf")
        pdf_export.erstelle_zeitplan_pdf(self.conn, pfad)
        text = _text(pfad)
        self.assertIn("Herr Ohne Plan", text)
        self.assertIn("Noch keine Prüfungsblöcke/Pausen", text)

    def test_zeitplan_pdf_block_ohne_teilnehmer_zeigt_hinweiszeile(self):
        # Ein angelegter, aber noch leerer Prüfungsblock darf nicht spurlos aus der PDF
        # verschwinden (siehe db.berechne_zeitplan - Platzhalterzeile mit teilnehmer=None).
        rid = add_zeitplan_richter(self.conn, name="Herr Meier")
        add_zeitplan_pruefungsblock(self.conn, rid, art="ED", stufe=1, disziplin="Trümmerfeld", dauer_minuten=10)
        pfad = self._pfad("zeitplan_block_leer.pdf")
        pdf_export.erstelle_zeitplan_pdf(self.conn, pfad)
        text = _text(pfad)
        self.assertIn("ED LK 1", text)
        self.assertIn("noch keine Teilnehmer gemeldet", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
