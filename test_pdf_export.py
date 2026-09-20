"""Tests für pdf_export.py - prüft nicht nur "läuft ohne Fehler", sondern liest den
erzeugten PDF-Text wieder ein und kontrolliert die wichtigsten Inhalte (Werte, die
"nicht Bestanden"-Regel, die LK-abhängigen Verleitungs-Hinweise/Behältnis-Positionen)."""

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
)
import pdf_export


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
        self.assertIn("Schlüssel <b>bund", text)
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
        self.assertIn("Zu suchender Gegenstand: Lederhandschuh", text)
        self.assertIn("Zu suchender Gegenstand: Holzklotz", text)

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
        # LK3 Behältnisstrecke hat 10 Positionen (LK1: 6, LK2: 8, LK3: 10)
        self.assertIn("[10]", text)
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
        # LK2 Behältnisstrecke hat 8 Positionen
        self.assertIn("[8]", text)

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

    def test_ergebnisliste_zeigt_ausstehende_teilnehmer(self):
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Wartend", vorname="C", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1))
        pfad = self._pfad("ergebnisliste_offen.pdf")
        pdf_export.erstelle_ergebnisliste_pdf(self.conn, pfad)
        text = _text(pfad)
        self.assertIn("Wartend, C", text)
        self.assertIn("Noch ohne vollständiges Ergebnis", text)

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
        self.assertIn("2026-09-19", text)
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
        # Hinweis: In der schmalen Matrix-Spalte wird "Trümmerfeld" zeilenweise
        # umgebrochen (auch mitten im Wort); pypdf extrahiert das als getrennte
        # Textfragmente. Zeilenumbrüche entfernen wir daher vor dieser Prüfung.
        text_ohne_umbrueche = text.replace("\n", "")
        self.assertIn("Dreikampf", text)
        self.assertIn("Einzeldisziplin", text)
        self.assertIn("Trümmerfeld", text_ohne_umbrueche)
        self.assertIn("Vorzüglich (V)", text)
        self.assertIn("nicht Bestanden (nB)", text)
        # Der ausstehende Teilnehmer B fließt nicht in die Zählung ein.
        self.assertNotIn("B, B", text)

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
        # "Kontrolle Impfpass erledigt?"/"Abgabe Sportbeitrag" bleiben weiterhin leer (werden
        # von Hand abgehakt) - nur die Spaltenüberschriften erscheinen. "bezahlt?" selbst wird
        # dagegen inzwischen aus dem gepflegten Bezahlt-Status befüllt; beide Teilnehmer hier
        # sind (Standardwert) noch nicht als bezahlt markiert, also erscheint auch dort noch
        # kein "Ja".
        self.assertIn("bezahlt?", text)
        self.assertIn("Kontrolle", text)
        self.assertIn("Sportbeitrag", text)
        self.assertNotIn("Ja", text)
        self.assertNotIn("Nein", text)

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
