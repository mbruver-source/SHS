"""
PDF-Ausgabe für das SHS-Prüfungsprogramm: Bewertungsbögen, Ergebnislisten, Statistik,
ausfüllbares Anmeldeformular.

Bewusste Entscheidung: reportlab statt weasyprint/xhtml2pdf.
Der ursprüngliche Plan (siehe Grobkonzept) war eine HTML/CSS-Vorlage über weasyprint.
weasyprint braucht unter Windows aber die native GTK3-Runtime (Cairo/Pango/GDK-Pixbuf) -
das müsste als zusätzlicher Installer-Baustein mitgeliefert werden und ist ein bekannter
Stolperstein bei der Weitergabe an einen PC, auf dem sonst nichts weiter installiert wird
(genau der Fall hier: ein Installer, der "einfach funktionieren" soll). reportlab ist reines
Python (nur die Wheels selbst enthalten kompilierten Code, keine separate Laufzeitumgebung),
lässt sich rückstandslos mit PyInstaller in eine einzelne .exe packen und - wichtig - ließ
sich hier in der Arbeitsumgebung tatsächlich installieren und testen (anders als PySide6).
Der Aufbau der Bewertungsbögen ist 1:1 aus den 12 hochgeladenen .odt-Serienbrief-Vorlagen
übernommen (Layout, Punktebänder, "Verleitungen"-Hinweise je Leistungsklasse/Disziplin).
Am 24.09.2026 an Marcos neue Vorlagen in pdf/ angeglichen: Positions-Skizzen je Disziplin
und feste DK-Seitenaufteilung (2 Seiten). Noten und Verleitungs-Hinweise blieben bewusst
unverändert (Details in Fortschritt.md).

Alle Funktionen erwarten eine bereits offene `sqlite3.Connection` (siehe db.py) und einen
Zielpfad, unter dem die PDF-Datei geschrieben wird.
"""

from __future__ import annotations

import math
import sqlite3
from typing import NamedTuple
from xml.sax.saxutils import escape as _xml_escape

from reportlab.graphics.shapes import Drawing, Ellipse, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from db import (
    _GEGENSTAND_FELDER,
    ALLE_DISZIPLINEN,
    ANMELDEFORMULAR_HUENDIN,
    ANMELDEFORMULAR_KENNZEICHNUNG_CHIP,
    ANMELDEFORMULAR_KENNZEICHNUNG_TAETO,
    ANMELDEFORMULAR_PRUEFUNG_PRAEFIX,
    ANMELDEFORMULAR_RUEDE,
    ANMELDEFORMULAR_UNTERSCHRIFT_DATUM,
    ANMELDEFORMULAR_VOLLJAEHRIG_JA,
    ANMELDEFORMULAR_VOLLJAEHRIG_NEIN,
    angebotene_pruefungen,
    anmeldeformular_gegenstand_feld,
    BEHAELTNIS_BEDARF_HINWEIS,
    BEHAELTNIS_BEDARF_SPALTEN,
    BEHAELTNIS_BEDARF_TITEL,
    BEHAELTNIS_POSITIONEN,
    DISZIPLIN_SPALTEN,
    LR_EINHEITEN_JE_ART,
    LR_EINHEITEN_PRO_RICHTER,
    berechne_auswertung,
    behaeltnis_bedarf_zeilentexte,
    berechne_behaeltnis_bedarf,
    berechne_zeitplan,
    datum_anzeige,
    datum_oder_none,
    gegenstand_fuer_disziplin,
    get_veranstaltung,
    ist_jugendlicher,
    leistungsklasse_label,
    lies_datum,
    list_teilnehmer,
    pruefungsgebuehr_fuer_art,
)
from shs_core import (
    ABBRUCH_ABK,
    ABBRUCH_TEXT,
    DISQUALIFIZIERT_ABK,
    DISQUALIFIZIERT_TEXT,
    berechne_wertnote_dk,
)

# --- Gemeinsame Stile -------------------------------------------------------

_STYLES = getSampleStyleSheet()
_TITEL = ParagraphStyle("SHSTitel", parent=_STYLES["Heading1"], fontSize=14, spaceAfter=2 * mm)
_LK_TITEL = ParagraphStyle("SHSLkTitel", parent=_STYLES["Heading1"], fontSize=20, spaceAfter=0)
_ABSCHNITT = ParagraphStyle("SHSAbschnitt", parent=_STYLES["Heading2"], fontSize=13, spaceBefore=4 * mm, spaceAfter=1 * mm, alignment=1)
_HINWEIS = ParagraphStyle("SHSHinweis", parent=_STYLES["Normal"], fontSize=8, alignment=1, spaceAfter=2 * mm)
_TEXT = ParagraphStyle("SHSText", parent=_STYLES["Normal"], fontSize=9.5)
_TEXT_FETT = ParagraphStyle("SHSTextFett", parent=_STYLES["Normal"], fontSize=9.5, fontName="Helvetica-Bold")
_STAT_TITEL = ParagraphStyle("SHSStatTitel", parent=_STYLES["Heading1"], fontSize=16, alignment=1, spaceAfter=0)
_STAT_KOPF_LABEL = ParagraphStyle("SHSStatKopfLabel", parent=_STYLES["Normal"], fontSize=9.5, fontName="Helvetica-Bold")
_STAT_KOPF_WERT = ParagraphStyle("SHSStatKopfWert", parent=_STYLES["Normal"], fontSize=9.5)
# Nutzerwunsch (21.09., "Kosmetik"): die Spaltenüberschriften der Prädikat-Matrix
# (insbesondere "Behältnisstrecke"/"Flächensuche"/"Trümmerfeld") brachen bei der
# ursprünglichen Schriftgröße 7.5 mitten im Wort um, da die einzelnen ED-Spalten
# schmaler waren als das jeweils längste Wort. Entscheidung (Rückfrage beantwortet):
# Spalten verbreitern UND Kopfschrift leicht verkleinern (statt Wörter abzukürzen), siehe
# _stat_spalte_breite() unten - beides zusammen sorgt dafür, dass jede Überschrift
# einzeilig passt.
_STAT_MATRIX_KOPF = ParagraphStyle("SHSStatMatrixKopf", parent=_STYLES["Normal"], fontSize=6.5, fontName="Helvetica-Bold", alignment=1, leading=8)
_STAT_MATRIX_ZELLE = ParagraphStyle("SHSStatMatrixZelle", parent=_STYLES["Normal"], fontSize=9, alignment=1)

_WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
_MONATE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


def _datum_lang(iso_datum: str | None) -> str:
    """Formatiert ein Datum im Format JJJJ-MM-TT als deutschen Langtext
    ("Sonntag, 27. April 2025") - wie im Original-Statistikbogen. Ist der Wert leer oder
    nicht als Datum erkennbar, wird er unverändert zurückgegeben statt einen Fehler
    auszulösen (z. B. falls jemand ein anderes Datumsformat eingetragen hat)."""
    try:
        d = lies_datum(iso_datum)
    except ValueError:
        return iso_datum
    if d is None:
        return ""
    return f"{_WOCHENTAGE[d.weekday()]}, {d.day}. {_MONATE[d.month - 1]} {d.year}"


def _datum_kurz(iso_datum: str | None) -> str:
    """Formatiert ein Datum im Format JJJJ-MM-TT kompakt als TT.MM.JJJJ - für Tabellen-
    spalten, in denen der ausgeschriebene Langtext (_datum_lang) zu breit wäre (siehe
    Impfpass-Spalte in erstelle_pruefungsleitung_uebersicht_pdf). Ist der Wert leer oder
    nicht als Datum erkennbar, wird er wie bei _datum_lang unverändert zurückgegeben."""
    return datum_anzeige(iso_datum)


def _schriftgroesse_fuer_breite(
    text: str, max_breite_pt: float, start_groesse: float, min_groesse: float, font: str = "Helvetica",
) -> float:
    """Ermittelt die größte Schriftgröße (zwischen `min_groesse` und `start_groesse`, in
    0,5-Schritten), bei der `text` in genau EINER Zeile innerhalb `max_breite_pt` Punkt
    Platz findet - Grundlage für die automatische Schriftverkleinerung langer
    Vereinsnamen in der leeren Ergebnisliste (Nutzerwunsch 21.09.: Text soll einzeilig
    bleiben statt in die Nachbarspalte hineinzuragen, keine Zeilenumbrüche in der
    Zelle). Passt `text` auch bei `min_groesse` nicht (sehr langer Name), wird trotzdem
    `min_groesse` geliefert statt weiter zu schrumpfen - ein minimal überstehender,
    aber noch lesbarer Name ist der praktikablere Kompromiss als eine unleserlich
    kleine Schrift."""
    groesse = start_groesse
    while groesse > min_groesse and stringWidth(text, font, groesse) > max_breite_pt:
        groesse -= 0.5
    return max(groesse, min_groesse)


# Welcher der drei Gegenstände (frei eingetragener Text) welcher Disziplin zugeordnet ist,
# wird seit Einführung der Gegenstand-Zuordnung (siehe NeuerTeilnehmer.gegenstand_N_disziplin
# in db.py) pro Teilnehmer frei gewählt statt fest nach Position angenommen - Nachschlagen
# über db.gegenstand_fuer_disziplin(). Gilt einheitlich für ED und DK. Die Feldnamen
# (_GEGENSTAND_FELDER) kommen aus db.py statt hier ein zweites Mal definiert zu werden
# (Codeprüfung 22.09., G14).

# "Verleitungen"-Hinweise und Anzahl Behältnis-Positionen je Leistungsklasse/Disziplin -
# 1:1 aus den 12 Original-Vorlagen übernommen (siehe dortige Klammer-Hinweise).
_VERLEITUNGEN = {
    ("Trümmerfeld", 1): None,
    ("Trümmerfeld", 2): "(Eigengeruchsverleitung, 5 Spielzeugverleitungen)",
    ("Trümmerfeld", 3): "(Eigengeruchsverleitung, 5 Spielzeugverleitungen, 5 Futterverleitungen, 1 Material-/baugleicher Gegenstand)",
    ("Flächensuche", 1): None,
    ("Flächensuche", 2): "(5 Spielzeugverleitungen)",
    ("Flächensuche", 3): "(5 Spielzeugverleitungen, 5 Futterverleitungen, 1 Material-/baugleicher Gegenstand)",
    ("Behältnisstrecke", 1): None,
    ("Behältnisstrecke", 2): "(Eigengeruchsverleitung, 2 Spielzeugverleitungen)",
    ("Behältnisstrecke", 3): "(Eigengeruchsverleitung, 2 Spielzeugverleitungen, 2 Futterverleitungen, 1 Material-/baugleicher Gegenstand)",
}
_BEHAELTNIS_POSITIONEN = BEHAELTNIS_POSITIONEN  # zentral in db.py
_SUCHGEGENSTAENDE_TEXT = {1: "ein Suchgegenstand", 2: "zwei Suchgegenstände", 3: "drei Suchgegenstände"}


def _wert(v) -> str:
    return "" if v in (None, "") else str(v)


# Disqualifiziert/Abbruch: Abkürzung -> Anzeigetext (Codeprüfung 22.09., M3).
_STATUS_TEXT = {DISQUALIFIZIERT_ABK: DISQUALIFIZIERT_TEXT, ABBRUCH_ABK: ABBRUCH_TEXT}


def _status_abkuerzung(ergebnis: dict | None) -> str | None:
    """DISQUALIFIZIERT_ABK/ABBRUCH_ABK, falls der Ergebnis-Datensatz entsprechend markiert
    ist, sonst None - gleiche Priorität wie in db.berechne_auswertung()."""
    if not ergebnis:
        return None
    if ergebnis.get("disqualifiziert"):
        return DISQUALIFIZIERT_ABK
    if ergebnis.get("abbruch"):
        return ABBRUCH_ABK
    return None


def _p_wert(v) -> str:
    """Wie _wert(), aber zusätzlich XML-escaped (& < >) - für alle Werte, die in einen
    reportlab-Paragraph eingebettet werden. Paragraph() parst seinen Text als kleine
    Mini-Auszeichnungssprache (<b>, <i>, <br/> ...); ohne dieses Escaping ließ z. B. ein
    Zwingername mit einem einzelnen '<' (frei eingegebener Text, kein von uns kontrolliertes
    Format) den kompletten PDF-Export mit einem ValueError abbrechen - bei "alle
    Bewertungsbögen" sogar für ALLE Teilnehmer auf einmal, nicht nur den betroffenen
    (QS-Review 19./20.09., per Reproduktion bestätigt).
    Bewusst NICHT in _wert() selbst eingebaut: _wert() wird auch für reine Tabellenzellen-
    Strings (kein Paragraph, kein Markup-Parsing) verwendet - dort würde ein Escaping
    Sonderzeichen wie '&' sichtbar als "&amp;" im PDF anzeigen statt sie normal darzustellen."""
    return _xml_escape(_wert(v))


def _euro_text(wert: str | None) -> str:
    """Formatiert eine hinterlegte Prüfungsgebühr (z. B. "12,00") mit Euro-Zeichen, oder
    "", wenn (noch) keine hinterlegt ist."""
    if not wert:
        return ""
    wert = str(wert).strip()
    return wert if wert.endswith("€") else f"{wert} €"


def _wertungsnoten_tabelle_ed() -> Table:
    """Die kleine Punkte-Band-Tabelle (SUCHE/ANZEIGE/von 100 P.) - identisch auf jedem
    Bewertungsbogen, unabhängig von Leistungsklasse."""
    daten = [
        ["Wertungsnoten", "V = mind. 96%", "SG = 95–90%", "G = 89–80%", "B = 79–70%", "n.B. = 69–0%"],
        ["SUCHE", "60 – 58", "57 – 54", "53 – 48", "47 – 42", "41 – 0"],
        # ANZEIGE "V" ab 39 statt 38 (Codeprüfung 22.09., G10, Marcos Entscheidung): 96 %
        # von 40 sind aufgerundet 39 - 38 war aus der Original-Vorlage übernommen.
        ["ANZEIGE", "40 – 39", "38 – 36", "35 – 32", "31 – 28", "27 – 0"],
        ["von 100 P", "100 – 96", "95 – 90", "89 – 80", "79 – 70", "69 – 0"],
    ]
    tabelle = Table(daten, colWidths=[28 * mm] + [26.4 * mm] * 5)
    tabelle.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("BACKGROUND", (0, 3), (-1, 3), colors.whitesmoke),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 3), (0, 3), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tabelle


def _wertungsnoten_tabelle_dk() -> Table:
    """Die abschließende Gesamt-Prädikat-Tabelle (0-300 Punkte) am Ende eines DK-Bogens."""
    daten = [
        ["Prädikat", "V", "SG", "G", "B", "n.B."],
        ["von 300 P", "300 – 286", "285 – 270", "269 – 240", "239 – 210", "209 – 0"],
    ]
    tabelle = Table(daten, colWidths=[28 * mm] + [26.4 * mm] * 5)
    tabelle.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tabelle


def _stammdaten_tabelle(t: dict) -> Table:
    hund = _p_wert(t["zwingername"])
    rufname = _p_wert(t["rufname_hund"])
    hund_text = f"{hund}, Rufname: „{rufname}“" if hund else f"Rufname: „{rufname}“"
    daten = [
        [Paragraph("Name HF:", _TEXT), Paragraph(f"{_p_wert(t['nachname'])}, {_p_wert(t['vorname'])}", _TEXT),
         Paragraph("Name Hund:", _TEXT), Paragraph(hund_text, _TEXT)],
        [Paragraph("Verein:", _TEXT), Paragraph(_p_wert(t["verein"]), _TEXT),
         Paragraph("Chip-Nr.:", _TEXT), Paragraph(_p_wert(t["chip_nr"]), _TEXT)],
        [Paragraph("Widerristhöhe:", _TEXT), Paragraph(f"{_p_wert(t['schulterhoehe_cm'])} cm" if t["schulterhoehe_cm"] else "", _TEXT),
         Paragraph("Geschlecht:", _TEXT), Paragraph(_p_wert(t["geschlecht"]), _TEXT)],
    ]
    tabelle = Table(daten, colWidths=[26 * mm, 62 * mm, 24 * mm, 58 * mm])
    tabelle.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
    ]))
    return tabelle


# Positions-Skizzen zum Einzeichnen des Verstecks - nachgebaut nach den neuen Vorlagen in
# pdf/ (Nutzerwunsch 24.09.): Trümmerfeld = Quadrat, Flächensuche = Rechteck mit grauem
# Mittelstreifen, Behältnisstrecke = gezeichnete, nummerierte Behälter (6/8/10 je LK).

def _skizze_truemmerfeld() -> Drawing:
    seite = 34 * mm
    zeichnung = Drawing(seite + 2, seite + 2)
    zeichnung.add(Rect(1, 1, seite, seite, strokeWidth=1, fillColor=None))
    return zeichnung


def _skizze_flaeche() -> Drawing:
    # 24 mm hoch: damit passt DK-Seite 2 (Fläche + Behältnis + Gesamt) auch bei LK 2/3 mit
    # Verleitungs-Hinweisen noch auf eine A4-Seite.
    breite, hoehe, streifen = 70 * mm, 24 * mm, 3 * mm
    zeichnung = Drawing(breite + 2, hoehe + 2)
    zeichnung.add(Rect(1, 1, breite, hoehe, strokeWidth=1, fillColor=None))
    zeichnung.add(Rect(1, 1 + (hoehe - streifen) / 2, breite, streifen, strokeWidth=0, fillColor=colors.grey))
    return zeichnung


def _skizze_behaeltnisse(anzahl: int) -> Drawing:
    """Zeichnet `anzahl` stilisierte Zylinder (Rechteck + Ellipse als Deckel) mit fetter
    Nummer - Ersatz für die frühere Textdarstellung "[1] [2] ...". 9 mm je Behälter,
    damit auch die 10 Behälter von LK 3 in die 100-mm-Spalte passen."""
    breite, hoehe, abstand, deckel = 8 * mm, 11 * mm, 1 * mm, 1.2 * mm
    zeichnung = Drawing(anzahl * (breite + abstand), hoehe + deckel + 2)
    for i in range(anzahl):
        x = i * (breite + abstand) + 1
        zeichnung.add(Rect(x, 1, breite, hoehe, rx=1.5 * mm, ry=1.5 * mm, strokeWidth=0.8, fillColor=colors.white))
        zeichnung.add(Ellipse(x + breite / 2, 1 + hoehe, breite / 2, deckel, strokeWidth=0.8, fillColor=colors.white))
        zeichnung.add(String(x + breite / 2, 1 + hoehe / 2 - 4, str(i + 1),
                             fontName="Helvetica-Bold", fontSize=11, textAnchor="middle"))
    return zeichnung


def _bewertungsabschnitt(disziplin: str, stufe: int, suche: int | None, anzeige: int | None, gegenstand: str | None,
                         mit_wertungsnoten: bool = True) -> list:
    """Baut den kompletten "Bewertung <Disziplin>"-Block: Überschrift, ggf. Verleitungs-
    Hinweis, die beiden Bewertungsfelder (Suche/Anzeige) und die Positions-/Gesamtpunktzahl-
    Zeile mit der Positions-Skizze der Disziplin. `mit_wertungsnoten=False` lässt die
    Punkte-Band-Tabelle am Ende weg (DK-Seite 2: nur einmal unter der Behältnisstrecke,
    wie in der Vorlage)."""
    elemente: list = [Paragraph(f"Bewertung {disziplin}", _ABSCHNITT)]
    hinweis = _VERLEITUNGEN[(disziplin, stufe)]
    if hinweis:
        elemente.append(Paragraph(hinweis, _HINWEIS))

    kopf = Table(
        [["Suchleistung des Hundes (max. 60 P.)", "Anzeigeleistung des Hundes (max. 40 P.)"]],
        colWidths=[85 * mm, 85 * mm],
    )
    kopf.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    elemente.append(kopf)

    # Nutzerwunsch (21.09.): "Bei ED LK 1 Trümmerfeld ist das Feld zum eintragen doch
    # etwas schmal. Gerne etwas größer + Trennstrich zw. Suchleistung + Anzeige."
    # Betrifft technisch alle Disziplinen gleichermaßen (dieselbe Vorlage wird für
    # Trümmerfeld/Flächensuche/Behältnisstrecke gemeinsam genutzt, siehe Docstring oben) -
    # eigene Einschätzung: die Vergrößerung + der Trennstrich gelten daher einheitlich für
    # alle drei, nicht nur für Trümmerfeld. Höhe von 22mm auf 30mm vergrößert (mehr Platz
    # zum handschriftlichen Einzeichnen der Suchfläche); als zwei Zellen (statt einer
    # durchgehenden) angelegt, exakt so breit wie die Suchleistung/Anzeige-Kopfzeile
    # darüber (je 85mm) - GRID zeichnet dadurch automatisch eine durchgehende
    # Trennlinie genau zwischen beiden Bereichen.
    freiflaeche = Table([["", ""]], colWidths=[85 * mm, 85 * mm], rowHeights=[30 * mm])
    freiflaeche.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    elemente.append(freiflaeche)

    punktzahl = Table(
        [[Paragraph(f"<i>Punktzahl:</i> {_p_wert(suche)}", _TEXT), Paragraph(f"<i>Punktzahl:</i> {_p_wert(anzeige)}", _TEXT)]],
        colWidths=[85 * mm, 85 * mm],
    )
    punktzahl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
        ("LINEABOVE", (0, 0), (-1, 0), 1.2, colors.black),
    ]))
    elemente.append(punktzahl)

    gesamt = None if (suche is None or anzeige is None) else suche + anzeige
    gesamt_label = {
        "Trümmerfeld": "Trümmerfeldsuche:",
        "Flächensuche": "Flächensuche:",
        "Behältnisstrecke": "Behältnis:",
    }[disziplin]

    if disziplin == "Behältnisstrecke":
        links = [
            Paragraph("<b>Position Gegenstand im Behältnis-Nr.:</b>", _TEXT),
            Spacer(1, 1.5 * mm),
            _skizze_behaeltnisse(_BEHAELTNIS_POSITIONEN[stufe]),
            Spacer(1, 2 * mm),
            Paragraph("Gegenstand: ..................... Kammer-Nr.: .......", _TEXT),
        ]
    else:
        skizze = _skizze_truemmerfeld() if disziplin == "Trümmerfeld" else _skizze_flaeche()
        links = [Paragraph("<b>Position Gegenstand:</b>", _TEXT), Spacer(1, 1.5 * mm), skizze]
    gesamt_feld = Table(
        [[Paragraph(f"<b>Gesamtpunktzahl<br/>{gesamt_label}</b>", _TEXT), Paragraph(_p_wert(gesamt), _TEXT_FETT)]],
        colWidths=[45 * mm, 25 * mm],
    )
    gesamt_feld.setStyle(TableStyle([("GRID", (1, 0), (1, 0), 0.8, colors.black), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    if disziplin == "Behältnisstrecke":
        rechts = gesamt_feld
    else:
        # "Zu suchender Gegenstand" rechts neben der Skizze (wie in der Vorlage): dort ist
        # neben der hohen Skizze Platz frei, ein langer, umbrechender Gegenstand macht den
        # Block dadurch nicht höher - wichtig, damit DK-Seite 2 nicht überläuft
        # (Verifikation 24.09.).
        rechts = [
            Paragraph(f"Zu suchender Gegenstand: {_p_wert(gegenstand) or '.....................'}", _TEXT),
            Spacer(1, 3 * mm),
            gesamt_feld,
        ]

    fuss = Table([[links, rechts]], colWidths=[100 * mm, 70 * mm])
    fuss.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3 * mm)]))
    elemente.append(fuss)
    if mit_wertungsnoten:
        elemente.append(Spacer(1, 2 * mm))
        elemente.append(_wertungsnoten_tabelle_ed())

    return elemente


def _dk_folgeseiten_kopf(t: dict) -> Table:
    """Kopfzeile der DK-Seite 2 ("LK x  HF: ...  Hund: ..."), wie in der Vorlage - damit
    die zweite Seite auch lose eindeutig einem Team zugeordnet werden kann."""
    hund = _p_wert(t["zwingername"])
    rufname = _p_wert(t["rufname_hund"])
    hund_text = f"{hund}, Rufname: „{rufname}“" if hund else f"Rufname: „{rufname}“"
    # HF und Hund untereinander über die volle Breite: beide Zeilen passen in die Höhe des
    # großen "LK x", lange Namen brechen so praktisch nie um und schieben Seite 2 nicht
    # auf eine dritte Seite (Verifikation 24.09.).
    kopf = Table(
        [[Paragraph(f"LK {t['stufe']}", _LK_TITEL),
          [Paragraph(f"<b>HF:</b> {_p_wert(t['nachname'])}, {_p_wert(t['vorname'])}", _TEXT),
           Paragraph(f"<b>Hund:</b> {hund_text}", _TEXT)]]],
        colWidths=[25 * mm, 145 * mm],
    )
    kopf.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return kopf


def _bewertungsbogen_story(t: dict, ergebnis: dict | None, veranstaltung: dict | None) -> list:
    """Baut den vollständigen Bewertungsbogen (als reportlab-"Story") für einen
    Teilnehmer - je nach Art (ED/DK) mit einem bzw. drei Bewertungsabschnitten."""
    story: list = []

    kopf = Table(
        [[Paragraph("Bewertungsbogen SHS – Spürhundsport", _TITEL),
          Table([["Start-Nr.", _wert(t["startnummer"])]], colWidths=[22 * mm, 22 * mm],
                style=TableStyle([("GRID", (0, 0), (-1, -1), 0.8, colors.black), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))]],
        colWidths=[124 * mm, 46 * mm],
    )
    kopf.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(kopf)

    if t["art"] == "DK":
        lk_zeile = Table(
            [[Paragraph(f"LK {t['stufe']}", _LK_TITEL),
              Paragraph(f"<b>{_SUCHGEGENSTAENDE_TEXT[t['stufe']]}</b><br/><b>Dreikampf:</b> Trümmer, Fläche, Behältnisstrecke", _TEXT)]],
            colWidths=[30 * mm, 140 * mm],
        )
        story.append(lk_zeile)
    else:
        story.append(Paragraph(f"ED - LK {t['stufe']}", _LK_TITEL))
        story.append(Paragraph(f"<b>Einzeldisziplin: {t['disziplin']} – ein Suchgegenstand</b>", _TEXT))

    story.append(Spacer(1, 3 * mm))
    story.append(_stammdaten_tabelle(t))

    disziplinen = ALLE_DISZIPLINEN if t["art"] == "DK" else [t["disziplin"]]

    if t["art"] == "DK":
        # Listet alle drei Gegenstände (nach Position 1-3, wie erfasst) auf - die konkrete
        # Disziplin-Zuordnung erscheint dabei nur, wenn der Gegenstand tatsächlich einer
        # Disziplin zugeordnet ist ("frei" = keine Zuordnung = keine Klammerangabe).
        gegenstand_zeilen = []
        for i, feld in enumerate(_GEGENSTAND_FELDER, start=1):
            zugeordnete_disziplin = t.get(f"{feld}_disziplin")
            zusatz = f" ({zugeordnete_disziplin})" if zugeordnete_disziplin else ""
            gegenstand_zeilen.append(
                Paragraph(f"{i}. zu suchender Gegenstand: {_p_wert(t[feld]) or '.....'}{zusatz}", _TEXT)
            )
        story.extend(gegenstand_zeilen)
        story.append(Spacer(1, 2 * mm))

    einzelpunkte: dict[str, tuple[int | None, int | None]] = {}
    for disziplin in disziplinen:
        s_spalte, a_spalte = DISZIPLIN_SPALTEN[disziplin]
        einzelpunkte[disziplin] = (
            ergebnis[s_spalte] if ergebnis else None,
            ergebnis[a_spalte] if ergebnis else None,
        )

    def abschnitt(disziplin: str, mit_wertungsnoten: bool = True) -> KeepTogether:
        # Zu dieser Disziplin gehört nur der Gegenstand, der ihr auch tatsächlich
        # zugeordnet ist (siehe gegenstand_fuer_disziplin) - gilt einheitlich für ED und DK.
        suche, anzeige = einzelpunkte[disziplin]
        return KeepTogether(_bewertungsabschnitt(
            disziplin, t["stufe"], suche, anzeige, gegenstand_fuer_disziplin(t, disziplin), mit_wertungsnoten,
        ))

    verein = veranstaltung["verein"] if veranstaltung else ""
    datum = _datum_kurz(veranstaltung["datum"]) if veranstaltung else ""
    fusszeile = [
        Spacer(1, 4 * mm),
        Paragraph(f"austragender Verein: {_p_wert(verein)} &nbsp;&nbsp;&nbsp; Datum: {_p_wert(datum)}", _TEXT),
    ]

    status_abk = _status_abkuerzung(ergebnis)
    if t["art"] == "DK":
        # Feste Seitenaufteilung wie in der Vorlage (Nutzerwunsch 24.09.): Seite 1 =
        # Stammdaten + Trümmerfeld + Fußzeile, Seite 2 = Kopfzeile "LK x HF/Hund" +
        # Flächensuche + Behältnisstrecke + Gesamt. Ein DK-Bogen hat damit immer genau
        # 2 Seiten - beim beidseitigen Druck des Sammel-PDFs steht so nie ein anderes Team
        # auf der Rückseite.
        story.append(abschnitt("Trümmerfeld"))
        story.extend(fusszeile)
        story.append(PageBreak())
        story.append(_dk_folgeseiten_kopf(t))
        story.append(abschnitt("Flächensuche", mit_wertungsnoten=False))
        story.append(abschnitt("Behältnisstrecke"))
        story.append(Spacer(1, 3 * mm))
        vollstaendig = all(einzelpunkte[d][0] is not None and einzelpunkte[d][1] is not None for d in ALLE_DISZIPLINEN)
        gesamt_zeile = ["Pkt. Trümmer", "Pkt. Fläche", "Pkt. Behältnis", "GESAMT"]
        werte_zeile = [
            _wert(sum(einzelpunkte[d]) if None not in einzelpunkte[d] else None) for d in ALLE_DISZIPLINEN
        ]
        if status_abk is not None:
            # Disqualifiziert/Abbruch (Codeprüfung 22.09., M3): keine aus Punkten berechnete
            # Wertnote - wie in berechne_auswertung(). Die Einzelpunkte oben bleiben als
            # Dokumentation der Richterbewertung bewusst stehen (Marcos Entscheidung).
            werte_zeile.append(f"{_STATUS_TEXT[status_abk]} ({status_abk})")
        elif vollstaendig:
            gesamt = sum(sum(einzelpunkte[d]) for d in ALLE_DISZIPLINEN)
            wertnote = berechne_wertnote_dk(
                sum(einzelpunkte["Trümmerfeld"]), sum(einzelpunkte["Flächensuche"]), sum(einzelpunkte["Behältnisstrecke"])
            )
            werte_zeile.append(f"{gesamt}  ({wertnote.abkuerzung})")
        else:
            werte_zeile.append("")
        gesamt_tabelle = Table([gesamt_zeile, werte_zeile], colWidths=[42.5 * mm] * 4)
        gesamt_tabelle.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(KeepTogether([gesamt_tabelle, Spacer(1, 2 * mm), _wertungsnoten_tabelle_dk()]))
        return story

    story.append(abschnitt(t["disziplin"]))
    if status_abk is not None:
        # ED bei Disqualifiziert/Abbruch (Marcos Entscheidung 22.09., Nachtrag zu M3): die
        # Gesamtpunktzahl der Disziplin oben bleibt wie beim DK-Bogen als Dokumentation
        # stehen, darunter derselbe Status wie im DK-GESAMT-Feld - sonst sähe der Bogen
        # wie ein normal bewerteter aus.
        story.append(Spacer(1, 3 * mm))
        status_tabelle = Table(
            [["ERGEBNIS", f"{_STATUS_TEXT[status_abk]} ({status_abk})"]],
            colWidths=[42.5 * mm, 127.5 * mm],
        )
        status_tabelle.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("BACKGROUND", (0, 0), (0, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(status_tabelle)

    story.extend(fusszeile)
    return story


def erstelle_bewertungsbogen_pdf(conn: sqlite3.Connection, teilnehmer_id: int, pfad: str) -> None:
    """Erzeugt den Bewertungsbogen für genau einen Teilnehmer als eigene PDF-Datei."""
    t = next(x for x in list_teilnehmer(conn) if x["id"] == teilnehmer_id)
    ergebnis_row = conn.execute("SELECT * FROM ergebnisse WHERE teilnehmer_id = ?", (teilnehmer_id,)).fetchone()
    veranstaltung = get_veranstaltung(conn)

    dokument = SimpleDocTemplate(pfad, pagesize=A4, topMargin=14 * mm, bottomMargin=14 * mm, leftMargin=20 * mm, rightMargin=20 * mm)
    dokument.build(_bewertungsbogen_story(t, dict(ergebnis_row) if ergebnis_row else None, veranstaltung))


def erstelle_alle_bewertungsboegen_pdf(
    conn: sqlite3.Connection, pfad: str, erlaubte_labels: set[str] | None = None,
) -> int:
    """Erzeugt EINE Sammel-PDF mit dem Bewertungsbogen jedes Teilnehmers (sortiert nach
    Startnummer, wie die Teilnehmerliste) - praktisch zum Ausdrucken für alle Richter auf
    einmal. Gibt die Anzahl enthaltener Bögen zurück.

    `erlaubte_labels` (Nutzerwunsch 21.09.: "Das PDF enthält jetzt alle LK + Disziplinen.
    Auf einmal ein Doppelseitiger Druck führt dann dazu, dass ich bei den ED auf der
    Rückseite ein anderes Team habe. [...] ggf. auch nur Auswählbar, welche LK/Disziplin
    ich gedruckt haben will?") schränkt die Sammel-PDF optional auf die genannten Art/LK-
    Labels ein (wie leistungsklasse_label() sie liefert, z. B. "DK LK 1", "ED LK 2
    Trümmerfeld" - siehe BewertungsbogenAuswahlDialog in app.py). None (Standard, auch bei
    einem leeren Set gälte sonst 'nichts auswählen') bedeutet weiterhin ALLE Teilnehmer,
    identisch zum bisherigen Verhalten."""
    teilnehmer = list_teilnehmer(conn, nur_teilnehmende=True)
    if erlaubte_labels is not None:
        teilnehmer = [t for t in teilnehmer if leistungsklasse_label(t) in erlaubte_labels]
    veranstaltung = get_veranstaltung(conn)
    ergebnis_rows = {r["teilnehmer_id"]: dict(r) for r in conn.execute("SELECT * FROM ergebnisse").fetchall()}

    dokument = SimpleDocTemplate(pfad, pagesize=A4, topMargin=14 * mm, bottomMargin=14 * mm, leftMargin=20 * mm, rightMargin=20 * mm)
    story: list = []
    for i, t in enumerate(teilnehmer):
        if i > 0:
            story.append(PageBreak())
        story.extend(_bewertungsbogen_story(t, ergebnis_rows.get(t["id"]), veranstaltung))
    if not story:
        story = [Paragraph("Keine Teilnehmer erfasst.", _TEXT)]
    dokument.build(story)
    return len(teilnehmer)


# --- Ergebnisliste -----------------------------------------------------------

def erstelle_ergebnisliste_pdf(conn: sqlite3.Connection, pfad: str, leistungsklasse: str | None = None) -> None:
    """Gerankte Ergebnisliste je Leistungsklasse (Platzierung, Startnummer, Name,
    Gesamtpunkte, Wertnote) - "nicht Bestanden"-Teilnehmer erscheinen ohne Platzzahl,
    zählen aber weiterhin bei "von X Startern" mit (siehe shs_core.berechne_rangliste).

    `leistungsklasse` (Label wie "ED LK 1 Flächensuche", siehe leistungsklasse_label)
    beschränkt die Liste auf diese eine Leistungsklasse - genutzt vom Druck-Button im
    Auswertungs-Tab, der den dort gesetzten Art/LK-Filter übernimmt (Nutzerwunsch 23.09.).
    Die Platzierungen ändern sich dadurch nicht, sie gelten ohnehin je Leistungsklasse."""
    veranstaltung = get_veranstaltung(conn)
    fertig, ausstehend = berechne_auswertung(conn)
    startnummer_je_id = {str(t["id"]): t["startnummer"] for t in list_teilnehmer(conn)}

    story: list = []
    titel = "Ergebnisliste"
    if veranstaltung:
        titel += f" – {veranstaltung['verein']} ({_datum_kurz(veranstaltung['datum'])})"
    story.append(Paragraph(titel, _TITEL))
    story.append(Spacer(1, 2 * mm))

    leistungsklassen = sorted({t.leistungsklasse for t in fertig} | {leistungsklasse_label(t) for t in ausstehend})
    if leistungsklasse is not None:
        leistungsklassen = [lk for lk in leistungsklassen if lk == leistungsklasse]
    if not leistungsklassen:
        story.append(Paragraph("Keine Teilnehmer erfasst.", _TEXT))

    for lk in leistungsklassen:
        story.append(Paragraph(lk, _ABSCHNITT))
        gruppe = sorted(
            (t for t in fertig if t.leistungsklasse == lk),
            key=lambda t: (t.platzierung is None, t.platzierung or 0),
        )
        daten = [["Platz", "Start-Nr.", "Name", "Gesamtpunkte", "Wertnote"]]
        for t in gruppe:
            platz = "nB" if t.platzierung is None else f"{t.platzierung}. von {t.von_startern}"
            # Bei Disqualifiziert/Abbruch "–" statt einer irreführenden "0" (wie im
            # Auswertungs-Tab der Desktop-App).
            punkte = "–" if t.wertnote.abkuerzung in _STATUS_TEXT else str(t.gesamtpunkte)
            daten.append([platz, _wert(startnummer_je_id.get(t.id)), t.name, punkte, f"{t.wertnote.notentext} ({t.wertnote.abkuerzung})"])
        if len(daten) > 1:
            tabelle = Table(daten, colWidths=[28 * mm, 20 * mm, 50 * mm, 30 * mm, 42 * mm], repeatRows=1)
            tabelle.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]))
            story.append(tabelle)
        offene = [t for t in ausstehend if leistungsklasse_label(t) == lk]
        if offene:
            namen = ", ".join(f"{_p_wert(t['nachname'])}, {_p_wert(t['vorname'])}" for t in offene)
            story.append(Spacer(1, 1 * mm))
            story.append(Paragraph(f"<i>Noch ohne vollständiges Ergebnis: {namen}</i>", _HINWEIS))
        story.append(Spacer(1, 3 * mm))

    SimpleDocTemplate(pfad, pagesize=A4, topMargin=16 * mm, bottomMargin=16 * mm, leftMargin=18 * mm, rightMargin=18 * mm).build(story)


# Physische Etikettengröße wie vom Verein vorgegeben: Lang = 17 cm, Hoch ursprünglich
# 2 cm (je Teilnehmer EIN zweizeiliges Etikett dieser Größe, siehe
# erstelle_ergebnisliste_etiketten_pdf unten). Die Spaltenbreiten müssen sich exakt zu
# ETIKETT_BREITE_MM aufsummieren und die beiden Zeilenhöhen exakt zu ETIKETT_HOEHE_MM -
# vorher waren es (ungewollt) rund 17,8 cm Breite und eine von reportlab automatisch
# bestimmte, deutlich kleinere Höhe als die vorgegebene.
#
# Nutzerwunsch (21.09.): "fast ein bisschen zu Hoch - 1-2mm - ist aber bei anderen
# Sparten auch - reinpassen tut es". Entscheidung (Rückfrage beantwortet): trotzdem um
# 2mm verkleinert (18mm statt 20mm) - vorsichtig gewählt am oberen Ende der genannten
# Spanne, da Marco bestätigt hat, dass aktuell noch alles hineinpasst (siehe TOPPADDING/
# BOTTOMPADDING unten: bei 18mm bleiben je Zeile weiterhin gut 2,5mm Luft über dem
# tatsächlichen Platzbedarf des Texts - rechnerisch geprüft, siehe test_pdf_export.py).
#
# Weil die Zeilenhöhe FEST ist (statt sich wie vorher automatisch an den Inhalt
# anzupassen), müssen die Felder mit bekanntem Wertebereich auf einer Zeile bleiben, sonst
# würde umgebrochener Text optisch mit der Zeile darunter überlappen: die Spaltenbreiten
# unten sind bewusst so gewählt, dass die Punktzahl-Felder (max. "Trümmer: 100" bzw.
# "Behältnis: 100"/"Gesamt: 300") UND das Art/LK-Feld (max. "ED LK 3 Behältnis" - siehe
# _ETIKETT_DISZIPLIN_KURZ) garantiert einzeilig bleiben (mit echten Etiketten/Testdaten
# geprüft). Frei eingegebener Vereinsname/Teilnehmername kann bei ungewöhnlich langen
# Werten weiterhin umbrechen - das war schon vorher so und lässt sich bei Freitext nicht
# generell ausschließen.
ETIKETT_BREITE_MM = 170
ETIKETT_HOEHE_MM = 18
_ETIKETT_SPALTEN = [30 * mm, 29 * mm, 24 * mm, 21 * mm, 25 * mm, 23 * mm, 18 * mm]
# math.isclose statt "==": Summe von sieben einzeln mit dem (nicht exakt binär
# darstellbaren) Faktor "mm" multiplizierten Werten kann durch Gleitkomma-Rundung um
# einen verschwindend kleinen Bruchteil von der direkt berechneten Summe abweichen.
assert math.isclose(sum(_ETIKETT_SPALTEN), ETIKETT_BREITE_MM * mm)
_ETIKETT_ZEILEN = [ETIKETT_HOEHE_MM / 2 * mm, ETIKETT_HOEHE_MM / 2 * mm]
_ETIKETT_TEXT = ParagraphStyle("SHSEtikettText", parent=_STYLES["Normal"], fontSize=8.5, leading=10)
_ETIKETT_FELD = ParagraphStyle("SHSEtikettFeld", parent=_STYLES["Normal"], fontSize=8.5, fontName="Helvetica-Bold", leading=10)
# "Gesamt: DISQ"/"Gesamt: ABBR" ist in 8,5 pt breiter als das Gesamt-Feld (Codeprüfung
# 22.09., M3) - nur dieser Fall bekommt eine kleinere Schrift (Marcos Entscheidung).
_ETIKETT_FELD_STATUS = ParagraphStyle("SHSEtikettFeldStatus", parent=_ETIKETT_FELD, fontSize=7)
_ETIKETT_SHR = ParagraphStyle("SHSEtikettSHR", parent=_STYLES["Normal"], fontSize=7.5, alignment=1)

# Kurzform der Disziplin nur für das Art/LK-Feld des Etiketts (z.B. "ED LK 3 Behältnis"
# statt "ED LK 3 Behältnisstrecke") - passend zu den ohnehin schon abgekürzten
# Punktzahl-Feldern ("Behältnis: 100" statt "Behältnisstrecke: 100") auf demselben
# Etikett und nötig, damit das Feld bei der festen Zeilenhöhe nicht umbricht. Die
# GUI/der Filter nutzen weiterhin die ungekürzte leistungsklasse_label() aus db.py.
_ETIKETT_DISZIPLIN_KURZ = {
    "Trümmerfeld": "Trümmer",
    "Flächensuche": "Fläche",
    "Behältnisstrecke": "Behältnis",
}


def _etikett_art_lk_text(t: dict) -> str:
    if t["art"] == "DK":
        return f"DK LK {t['stufe']}"
    kurz = _ETIKETT_DISZIPLIN_KURZ.get(t["disziplin"], t["disziplin"])
    return f"ED LK {t['stufe']} {kurz}"


def _disziplin_gesamt_text(ergebnis: dict, disziplin: str) -> str:
    """Punktsumme (Suche+Anzeige) einer einzelnen Disziplin als Text, oder "-", wenn für
    diese Disziplin (noch) kein Ergebnis erfasst ist - z. B. bei ED grundsätzlich für die
    beiden nicht geprüften Disziplinen."""
    s_spalte, a_spalte = DISZIPLIN_SPALTEN[disziplin]
    suche, anzeige = ergebnis.get(s_spalte), ergebnis.get(a_spalte)
    if suche is None or anzeige is None:
        return "-"
    return str(suche + anzeige)


def erstelle_ergebnisliste_etiketten_pdf(conn: sqlite3.Connection, pfad: str) -> None:
    """Ergebnisliste als Etiketten zum Ausschneiden - EIN zweizeiliges Etikett je
    Teilnehmer, ganz ohne Seitentitel/Spaltenköpfe: Zeile 1 zeigt austragenden Verein,
    Art/Leistungsklasse, die Punktzahlen je Disziplin (Trümmer/Fläche/Behältnis), die
    Gesamtpunktzahl sowie ein Feld "SH-R", Zeile 2 Datum sowie Name, (eigener) Verein und
    Rufname des Hundes. Zwischen den Etiketten eine gestrichelte Linie als Schnittkante.
    Layout/Feldauswahl nach Vorlage aus der Originaldatei (Tabellenblatt "Druck_LU").
    Gedacht zum Bedrucken von Klebe-/Etikettenpapier, das danach zeilenweise
    auseinandergeschnitten wird.

    Jedes einzelne Etikett ist exakt ETIKETT_BREITE_MM x ETIKETT_HOEHE_MM groß (aktuell
    17 x 1,8 cm, siehe dort) - die gestrichelte Schnittlinie zwischen zwei Etiketten kommt
    beim Ausschneiden zusätzlich oben drauf, ist also nicht Teil der Etikettenhöhe.

    Das Feld "SH-R" bleibt bewusst leer - es ist ein Platzhalter, den der Spürhundesport-
    Richter später von Hand abstempelt und unterschreibt.

    Auch Teilnehmer ohne vollständiges Ergebnis erhalten ein Etikett (z.B. um es schon
    vorab mit Namen/Verein zu beschriften); die Punktzahl-Felder bleiben dort dann leer
    zum späteren handschriftlichen Nachtragen, statt Werte zu zeigen."""
    veranstaltung = get_veranstaltung(conn)
    austragender_verein = _p_wert(veranstaltung["verein"]) if veranstaltung else ""
    datum = _p_wert(_datum_kurz(veranstaltung["datum"])) if veranstaltung else ""

    fertig, _ausstehend = berechne_auswertung(conn)
    fertig_je_id = {erg.id: erg for erg in fertig}
    ergebnis_je_id = {str(r["teilnehmer_id"]): dict(r) for r in conn.execute("SELECT * FROM ergebnisse").fetchall()}
    alle_teilnehmer = list_teilnehmer(conn, nur_teilnehmende=True)

    def sortier_schluessel(t):
        erg = fertig_je_id.get(str(t["id"]))
        platzierung = erg.platzierung if erg is not None else None
        return (leistungsklasse_label(t), erg is None, platzierung is None, platzierung or 0, t["startnummer"] or 0)

    gruppe = sorted(alle_teilnehmer, key=sortier_schluessel)

    story: list = []
    for i, t in enumerate(gruppe):
        erg = fertig_je_id.get(str(t["id"]))
        ergebnis = ergebnis_je_id.get(str(t["id"]), {})

        name_info = f"{_p_wert(t['nachname'])}, {_p_wert(t['vorname'])}, {_p_wert(t['verein'])}"
        if t["rufname_hund"]:
            name_info += f", {_p_wert(t['rufname_hund'])}"

        gesamt_stil = _ETIKETT_FELD
        if erg is not None and erg.wertnote.abkuerzung in _STATUS_TEXT:
            # Disqualifiziert/Abbruch (Codeprüfung 22.09., M3, Marcos Entscheidung): keine
            # Punkte auf dem offiziellen Etikett, nur der Status statt "Gesamt: 0".
            truemmer_text = "Trümmer: -"
            flaeche_text = "Fläche: -"
            behaeltnis_text = "Behältnis: -"
            gesamt_text = f"Gesamt: {erg.wertnote.abkuerzung}"
            gesamt_stil = _ETIKETT_FELD_STATUS
        elif erg is not None:
            truemmer_text = f"Trümmer: {_disziplin_gesamt_text(ergebnis, 'Trümmerfeld')}"
            flaeche_text = f"Fläche: {_disziplin_gesamt_text(ergebnis, 'Flächensuche')}"
            behaeltnis_text = f"Behältnis: {_disziplin_gesamt_text(ergebnis, 'Behältnisstrecke')}"
            gesamt_text = f"Gesamt: {erg.gesamtpunkte}"
        else:
            # Noch kein vollständiges Ergebnis - Felder bleiben leer zum Nachtragen.
            truemmer_text = "Trümmer:"
            flaeche_text = "Fläche:"
            behaeltnis_text = "Behältnis:"
            gesamt_text = "Gesamt:"

        daten = [
            [
                Paragraph(austragender_verein, _ETIKETT_TEXT),
                Paragraph(_etikett_art_lk_text(t), _ETIKETT_TEXT),
                Paragraph(truemmer_text, _ETIKETT_FELD),
                Paragraph(flaeche_text, _ETIKETT_FELD),
                Paragraph(behaeltnis_text, _ETIKETT_FELD),
                Paragraph(gesamt_text, gesamt_stil),
                Paragraph("SH-R", _ETIKETT_SHR),
            ],
            [Paragraph(datum, _ETIKETT_TEXT), Paragraph(name_info, _ETIKETT_TEXT), "", "", "", "", ""],
        ]
        etikett = Table(daten, colWidths=_ETIKETT_SPALTEN, rowHeights=_ETIKETT_ZEILEN)
        etikett.setStyle(TableStyle([
            ("SPAN", (1, 1), (5, 1)),
            ("SPAN", (6, 0), (6, 1)),
            ("GRID", (2, 0), (5, 0), 0.6, colors.black),
            ("BOX", (6, 0), (6, 1), 0.6, colors.black),
            ("VALIGN", (0, 0), (5, -1), "MIDDLE"),
            ("VALIGN", (6, 0), (6, 1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
            ("LEFTPADDING", (2, 0), (5, 0), 2 * mm),
        ]))
        story.append(etikett)
        if i < len(gruppe) - 1:
            story.append(HRFlowable(
                width="100%", thickness=0.6, color=colors.grey, dash=(2, 2),
                spaceBefore=1 * mm, spaceAfter=1 * mm,
            ))
    # Bewusst KEIN Hinweistext bei fehlenden/leeren Daten - dieses Dokument enthält
    # ausschließlich die reinen Etikett-Zeilen zum Ausschneiden, keinerlei Beschriftung.

    SimpleDocTemplate(pfad, pagesize=A4, topMargin=10 * mm, bottomMargin=10 * mm, leftMargin=15 * mm, rightMargin=15 * mm).build(story)


def erstelle_leere_ergebnisliste_pdf(conn: sqlite3.Connection, pfad: str) -> None:
    """Ergebnisliste als leeres Formular zum handschriftlichen Ausfüllen - z. B. um sie
    vor Ort während der Prüfung papierbasiert zu führen und die Werte erst anschließend
    in die Software zu übernehmen. Zeigt je Leistungsklasse alle gemeldeten Teilnehmer
    sortiert nach Startnummer (Name/Verein bereits aus den Stammdaten vorausgefüllt);
    die Spalten Platz/Gesamtpunkte/Wertnote bleiben bewusst leer - auch für Teilnehmer,
    die bereits ein digitales Ergebnis haben, denn der Sinn dieses Formulars ist gerade
    die papierbasierte Erfassung unabhängig vom aktuellen Datenbankstand."""
    veranstaltung = get_veranstaltung(conn)
    teilnehmer = list_teilnehmer(conn, nur_teilnehmende=True)

    story: list = []
    titel = "Ergebnisliste – Formular zum Ausfüllen"
    if veranstaltung:
        titel += f" – {veranstaltung['verein']} ({_datum_kurz(veranstaltung['datum'])})"
    story.append(Paragraph(titel, _TITEL))
    story.append(Paragraph(
        "Start-Nr., Name und Verein sind vorausgefüllt. Platz, Gesamtpunkte und Wertnote "
        "bitte von Hand eintragen.",
        _HINWEIS,
    ))
    story.append(Spacer(1, 2 * mm))

    if not teilnehmer:
        story.append(Paragraph("Keine Teilnehmer erfasst.", _TEXT))

    labels = sorted({leistungsklasse_label(t) for t in teilnehmer})
    for label in labels:
        gruppe = sorted(
            (t for t in teilnehmer if leistungsklasse_label(t) == label),
            key=lambda t: (t["startnummer"] is None, t["startnummer"] or 0),
        )
        story.append(Paragraph(label, _ABSCHNITT))
        verein_spalte_breite = 40 * mm
        # Nutzerwunsch (21.09., Screenshot DK LK2/LK3): lange Vereinsnamen ragten bei
        # fester Schriftgröße 9 in die Nachbarspalte "Gesamtpunkte" hinein - die
        # Vereins-Zelle ist ein reiner String (kein Paragraph), reportlab bricht solche
        # Tabellenzellen nicht automatisch um. Entscheidung (Rückfrage beantwortet):
        # Schrift verkleinern statt umbrechen, bleibt dabei einzeilig. Nur die einzelnen
        # Vereins-Zellen bekommen bei Bedarf eine kleinere Schrift (per FONTSIZE-Eintrag
        # gezielt für diese eine Zelle) - alle übrigen Spalten/Zeilen bleiben bei der
        # üblichen Schriftgröße 9.
        _VEREIN_PADDING_PT = 12  # Standard-Zellinnenabstand (6pt links + 6pt rechts)
        verein_stile = []
        daten = [["Platz", "Start-Nr.", "Name", "Verein", "Gesamtpunkte", "Wertnote"]]
        for zeile, t in enumerate(gruppe, start=1):
            verein_text = _wert(t["verein"])
            daten.append(["", _wert(t["startnummer"]), f"{t['nachname']}, {t['vorname']}", verein_text, "", ""])
            if verein_text and stringWidth(verein_text, "Helvetica", 9) > verein_spalte_breite - _VEREIN_PADDING_PT:
                groesse = _schriftgroesse_fuer_breite(
                    verein_text, verein_spalte_breite - _VEREIN_PADDING_PT, start_groesse=9, min_groesse=5.5,
                )
                verein_stile.append(("FONTSIZE", (3, zeile), (3, zeile), groesse))
        tabelle = Table(
            daten, colWidths=[16 * mm, 18 * mm, 46 * mm, verein_spalte_breite, 26 * mm, 24 * mm], repeatRows=1,
        )
        tabelle.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            # Extra Innenabstand in den Datenzeilen, damit von Hand genug Platz zum
            # Schreiben bleibt (reine Kopfzeile bleibt kompakt).
            ("TOPPADDING", (0, 1), (-1, -1), 3.5 * mm),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 3.5 * mm),
            *verein_stile,
        ]))
        story.append(tabelle)
        story.append(Spacer(1, 4 * mm))

    SimpleDocTemplate(pfad, pagesize=A4, topMargin=16 * mm, bottomMargin=16 * mm, leftMargin=18 * mm, rightMargin=18 * mm).build(story)


# --- Statistik -----------------------------------------------------------
#
# Layout nach Vorlage aus der Originaldatei (Tabellenblatt "HSVRM Statistik/Sportbeitrag"):
# Kopf-Angaben zum Termin (Verein, Vereins-Nr., Prüfungsnummer, Prüfungstag,
# Richter 1-5, Prüfungsleiter), darunter eine Kreuztabelle "Prädikat" mit einer
# Spalte je Art/Leistungsklasse (Dreikampf LK1-3, sowie je Einzeldisziplin LK1-3) und
# einer Zeile je Prädikat (V/SG/G/B/nB) mit der jeweiligen Teilnehmerzahl. Bewusst OHNE
# das Vereinslogo der Vorlage (oben links) - das ist vereinsspezifisch und nicht Teil
# der eigentlichen Auswertung.

_STAT_SPALTEN: list[tuple[str, str]] = (
    [(f"DK LK {stufe}", f"LK {stufe}") for stufe in (1, 2, 3)]
    + [
        (f"ED LK {stufe} {disziplin}", f"{disziplin}<br/>LK {stufe}")
        for disziplin in ("Trümmerfeld", "Behältnisstrecke", "Flächensuche")
        for stufe in (1, 2, 3)
    ]
)
# Nutzerwunsch (21.09.): zwei zusätzliche Zeilen "Disqualifikation"/"Abbruch", die wie
# die bestehenden Prädikat-Zeilen zählen - db.berechne_auswertung() gibt DQ/Abbruch-
# Teilnehmern bereits eine Platzhalter-Wertnote mit abkuerzung=DISQUALIFIZIERT_ABK/
# ABBRUCH_ABK (siehe shs_core), _statistik_praedikat_matrix() unten muss dafür nicht
# geändert werden - die Zählung läuft rein über diese beiden Listen.
_PRAEDIKAT_REIHENFOLGE = ["V", "SG", "G", "B", "nB", DISQUALIFIZIERT_ABK, ABBRUCH_ABK]
_PRAEDIKAT_TEXT = {
    "V": "Vorzüglich", "SG": "Sehr Gut", "G": "Gut", "B": "Befriedigend", "nB": "nicht Bestanden",
    DISQUALIFIZIERT_ABK: "Disqualifikation", ABBRUCH_ABK: "Abbruch",
}

# Spaltenbreiten der Prädikat-Matrix (Nutzerwunsch 21.09., siehe _STAT_MATRIX_KOPF oben):
# je knapp genug bemessen, dass das jeweils längste Wort der Spaltenüberschrift bei
# Schriftgröße 6.5 (Helvetica-Bold) einzeilig hineinpasst (Textbreite + Standard-
# Zellinnenabstand 6pt links/rechts), aber nicht großzügiger - die Gesamtbreite muss auf
# die nutzbare Seitenbreite (A4 quer, 267mm bei 15mm Rand) passen. Die DK-Spalten
# brauchen dafür deutlich weniger Platz ("LK 1"/"LK 2"/"LK 3") als die ED-Spalten (volle
# Disziplinnamen) - deshalb bewusst unterschiedliche Breiten statt einer für alle 12
# Spalten gemeinsamen Breite wie zuvor.
_STAT_SPALTE_BREITE_LABEL = 30 * mm
_STAT_SPALTE_BREITE_DK = 14 * mm
_STAT_SPALTE_BREITEN_ED = {
    "Trümmerfeld": 19 * mm,
    "Behältnisstrecke": 23 * mm,
    "Flächensuche": 20 * mm,
}


def _stat_spalte_breite(spalte_key: str) -> float:
    """Liefert die passende Spaltenbreite zu einem _STAT_SPALTEN-Schlüssel ("DK LK 1"
    bzw. "ED LK <n> <Disziplin>", siehe leistungsklasse_label() in db.py)."""
    if spalte_key.startswith("DK "):
        return _STAT_SPALTE_BREITE_DK
    for disziplin, breite in _STAT_SPALTE_BREITEN_ED.items():
        if disziplin in spalte_key:
            return breite
    return _STAT_SPALTE_BREITE_DK  # Fallback, sollte bei den heutigen 6 Kombinationen nie eintreten


def _statistik_kopftabelle(veranstaltung: dict | None) -> Table:
    v = veranstaltung or {}

    def zelle(label: str, wert) -> list:
        return [Paragraph(label, _STAT_KOPF_LABEL), Paragraph(_p_wert(wert), _STAT_KOPF_WERT)]

    daten = [
        zelle("Verein:", v.get("verein")) + zelle("Vereins-Nr.:", v.get("vereins_nr")),
        zelle("Prüfungsnummer:", v.get("pruefungsnummer")) + zelle("Prüfungstag:", _datum_lang(v.get("datum"))),
        zelle("Richter 1:", v.get("wertungsrichter_1")) + zelle("Prüfungsleiter:", v.get("pruefungsleiter")),
        # Richter 3-5 (Nutzerwunsch 20.09., vorher nur 1/2): rechte Spalte bleibt
        # für Prüfungsleiter reserviert, daher hier zu zweit statt gepaart mit ihm.
        zelle("Richter 2:", v.get("wertungsrichter_2")) + zelle("Richter 3:", v.get("wertungsrichter_3")),
        zelle("Richter 4:", v.get("wertungsrichter_4")) + zelle("Richter 5:", v.get("wertungsrichter_5")),
    ]
    tabelle = Table(daten, colWidths=[42 * mm, 68 * mm, 42 * mm, 68 * mm])
    tabelle.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
    ]))
    return tabelle


def _statistik_praedikat_matrix(fertig) -> Table:
    zaehler = {(spalte_key, abk): 0 for spalte_key, _ in _STAT_SPALTEN for abk in _PRAEDIKAT_REIHENFOLGE}
    for t in fertig:
        schluessel = (t.leistungsklasse, t.wertnote.abkuerzung)
        if schluessel in zaehler:
            zaehler[schluessel] += 1

    zeile_gruppen = [""] + [""] * len(_STAT_SPALTEN)
    zeile_gruppen[1] = Paragraph("Dreikampf", _STAT_MATRIX_KOPF)
    zeile_gruppen[4] = Paragraph("Einzeldisziplin", _STAT_MATRIX_KOPF)

    zeile_unterkopf = [Paragraph("Prädikat", _STAT_MATRIX_KOPF)] + [
        Paragraph(header, _STAT_MATRIX_KOPF) for _, header in _STAT_SPALTEN
    ]

    daten = [zeile_gruppen, zeile_unterkopf]
    for abk in _PRAEDIKAT_REIHENFOLGE:
        zeile = [Paragraph(f"{_PRAEDIKAT_TEXT[abk]} ({abk})", _STAT_MATRIX_KOPF)]
        zeile += [Paragraph(str(zaehler[(spalte_key, abk)]), _STAT_MATRIX_ZELLE) for spalte_key, _ in _STAT_SPALTEN]
        daten.append(zeile)

    spalten_breiten = [_STAT_SPALTE_BREITE_LABEL] + [_stat_spalte_breite(spalte_key) for spalte_key, _ in _STAT_SPALTEN]
    tabelle = Table(daten, colWidths=spalten_breiten, repeatRows=2)
    tabelle.setStyle(TableStyle([
        ("GRID", (0, 1), (-1, -1), 0.5, colors.black),
        ("SPAN", (1, 0), (3, 0)),
        ("SPAN", (4, 0), (12, 0)),
        ("BOX", (1, 0), (3, 0), 0.5, colors.black),
        ("BOX", (4, 0), (12, 0), 0.5, colors.black),
        ("BACKGROUND", (0, 1), (-1, 1), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
    ]))
    return tabelle


def _statistik_jugendliche_tabelle(fertig, teilnehmer_je_id: dict, pruefungsdatum: str | None) -> Table:
    """Zusatztabelle 'Jugendliche' (Nutzerwunsch 21.09., Rückmeldung 'Statistik/
    Jugendliche': '(bei uns im Verband müssen Jugendliche gesondert ausgewiesen werden -
    weiß nicht ob das bei euch auch ist?)'. Entscheidung (Rückfrage beantwortet): jetzt
    als generelles Feature umgesetzt, nicht verbandsspezifisch konfigurierbar;
    Alterskriterium unter 18 Jahre, Stichtag Prüfungsdatum - siehe db.ist_jugendlicher().
    Zählt - unabhängig vom erreichten Prädikat - wie viele der vollständig bewerteten
    Teilnehmer je Art/Leistungsklasse-Spalte (dieselben Spalten wie die Prädikat-Matrix
    oben, gleiche Breiten) zum Prüfungstag noch minderjährig waren. Lehnt sich bewusst an
    die Prädikat-Matrix an, nur mit einer einzigen Datenzeile statt einer je Prädikat -
    eigene Einschätzung, da eine zusätzliche Zeile INNERHALB der Prädikat-Matrix die dort
    gezählten Prädikate verfälscht hätte (Jugendliche verteilen sich auf alle Prädikate,
    sind keine eigene Prädikats-Kategorie)."""
    zaehler = {spalte_key: 0 for spalte_key, _ in _STAT_SPALTEN}
    for t in fertig:
        alt_teilnehmer = teilnehmer_je_id.get(t.id)
        if alt_teilnehmer and ist_jugendlicher(alt_teilnehmer.get("geburtsdatum"), pruefungsdatum):
            if t.leistungsklasse in zaehler:
                zaehler[t.leistungsklasse] += 1

    zeile_unterkopf = [Paragraph("Jugendliche<br/>(u18)", _STAT_MATRIX_KOPF)] + [
        Paragraph(header, _STAT_MATRIX_KOPF) for _, header in _STAT_SPALTEN
    ]
    zeile_werte = [Paragraph("Anzahl", _STAT_MATRIX_KOPF)] + [
        Paragraph(str(zaehler[spalte_key]), _STAT_MATRIX_ZELLE) for spalte_key, _ in _STAT_SPALTEN
    ]

    spalten_breiten = [_STAT_SPALTE_BREITE_LABEL] + [_stat_spalte_breite(spalte_key) for spalte_key, _ in _STAT_SPALTEN]
    tabelle = Table([zeile_unterkopf, zeile_werte], colWidths=spalten_breiten)
    tabelle.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
    ]))
    return tabelle


def erstelle_statistik_pdf(conn: sqlite3.Connection, pfad: str) -> None:
    """Statistik-PDF nach der Original-Vorlage: Kopf-Angaben zum Termin (Verein,
    Vereins-Nr., Prüfungsnummer, Prüfungstag, Richter 1-5, Prüfungsleiter) sowie
    eine Kreuztabelle, die für jede Art/Leistungsklasse-Kombination zählt, wie viele
    Teilnehmer welches Prädikat (V/SG/G/B/nB) erreicht haben. Nur vollständig erfasste
    Ergebnisse fließen in die Zählung ein. Darunter (Nutzerwunsch 21.09.) eine gesonderte
    kleine Tabelle, wie viele dieser Teilnehmer je Spalte zum Prüfungsdatum noch
    Jugendliche (unter 18 Jahre) waren - siehe _statistik_jugendliche_tabelle()."""
    veranstaltung = get_veranstaltung(conn)
    fertig, _ausstehend = berechne_auswertung(conn)
    teilnehmer_je_id = {str(t["id"]): t for t in list_teilnehmer(conn)}
    pruefungsdatum = veranstaltung.get("datum") if veranstaltung else None

    story: list = [
        Paragraph("Spürhundsport (SHS) – Statistik / Sportbeitrag", _STAT_TITEL),
        Spacer(1, 4 * mm),
        _statistik_kopftabelle(veranstaltung),
        Spacer(1, 5 * mm),
        _statistik_praedikat_matrix(fertig),
        Spacer(1, 5 * mm),
        Paragraph("Jugendliche (unter 18 Jahre am Prüfungstag):", _STAT_KOPF_LABEL),
        Spacer(1, 1.5 * mm),
        _statistik_jugendliche_tabelle(fertig, teilnehmer_je_id, pruefungsdatum),
    ]

    SimpleDocTemplate(
        pfad, pagesize=landscape(A4),
        topMargin=12 * mm, bottomMargin=12 * mm, leftMargin=15 * mm, rightMargin=15 * mm,
    ).build(story)


# --- Übersicht für Prüfungsleitung ----------------------------------------
#
# Layout nach Vorlage aus der Originaldatei ("Übersicht für Prüfungsleitung"): eine Zeile
# je Teilnehmer mit Stammdaten und der Prüfungsgebühr. "bezahlt?" wird aus dem digital
# gepflegten Bezahlt-Status befüllt (siehe db.setze_bezahlt/app.TeilnehmerTab).
#
# Nutzerwunsch (21.09.): "Vielleicht kannst ja im Programm das mit dem Impfpass auch noch
# ergänzen? Dann hätte man alles digital." Entscheidung (Rückfrage beantwortet): kein
# bloßes Ja/Nein-Häkchen, sondern ein DATUM je Teilnehmer/Hund. Bewusst KEIN neues,
# separates Datenbankfeld dafür angelegt: das bereits bestehende Teilnehmerfeld
# `tollwutimpfung_bis` ("Tollwutimpfung gültig bis", siehe TeilnehmerDialog/
# _TEILNEHMER_NEUE_SPALTEN in db.py) IST inhaltlich genau das, was am Prüfungstag als
# "Impfpass kontrolliert" geprüft wird (Tollwut ist die für den Start relevante Pflicht-
# impfung) - ein zweites Feld hätte nur Doppelpflege riskiert. Die Spalte "Kontrolle
# Impfpass erledigt?" zeigt daher jetzt direkt dieses Datum statt eines leeren
# Ankreuzfelds; ist das Datum vor dem Prüfungstag abgelaufen (oder ganz leer), wird die
# Zelle rot/fett hervorgehoben, damit es der Prüfungsleitung sofort auffällt.
#
# "Abgabe Sportbeitrag" wurde auf Wunsch des Nutzers ("berechnet unser Verband anhand der
# im Portal erfassten Starterzahl selbst [...] Könnte man aus der Übersicht raus lassen")
# ersatzlos entfernt.

_UEBERSICHT_KOPF = ParagraphStyle(
    "SHSUebersichtKopf", parent=_STYLES["Normal"], fontSize=8, fontName="Helvetica-Bold", leading=9.5,
)
_UEBERSICHT_ZELLE = ParagraphStyle("SHSUebersichtZelle", parent=_STYLES["Normal"], fontSize=8.5, leading=10)
_UEBERSICHT_ZELLE_ROT = ParagraphStyle(
    "SHSUebersichtZelleRot", parent=_UEBERSICHT_ZELLE, textColor=colors.red, fontName="Helvetica-Bold",
)


def _impfung_hervorheben(impfung_bis: str | None, pruefungsdatum: str | None) -> bool:
    """True, wenn die Impfpass-Zelle rot hervorgehoben werden soll: Impfung vor dem
    Prüfungstag abgelaufen, oder kein bzw. ein nicht lesbares Impfdatum (unbekannt =
    ungeprüft). Echter Datumsvergleich statt Stringvergleich (Codeprüfung 22.09., M5):
    ein Altbestand in TT.MM.JJJJ wurde vorher falsch einsortiert."""
    impfung = datum_oder_none(impfung_bis)
    pruefung = datum_oder_none(pruefungsdatum)
    return impfung is None or (pruefung is not None and impfung < pruefung)


def erstelle_pruefungsleitung_uebersicht_pdf(conn: sqlite3.Connection, pfad: str) -> None:
    """Übersicht für die Prüfungsleitung: Nachname/Vorname/Verein/Hund/Chip-Nr./
    Leistungsklasse aus den Stammdaten, dazu die Prüfungsgebühr (aus den
    Veranstaltungsdaten, je nach Art ED/DK unterschiedlich), die Spalte "bezahlt?" (aus
    dem in der Teilnehmerliste gepflegten Bezahlt-Status) sowie - seit 21.09. digital
    statt Ankreuzfeld - "Impfpass gültig bis" (aus dem Stammdatenfeld
    `tollwutimpfung_bis`, siehe Modulkommentar oben), rot hervorgehoben bei fehlendem
    oder zum Prüfungstag bereits abgelaufenem Datum. Sortiert nach Nachname/Vorname."""
    veranstaltung = get_veranstaltung(conn)
    teilnehmer = sorted(list_teilnehmer(conn), key=lambda t: (t["nachname"], t["vorname"]))
    pruefungsdatum = veranstaltung.get("datum") if veranstaltung else None

    story: list = []
    titel = "Übersicht für Prüfungsleitung"
    if veranstaltung:
        titel += f" – {veranstaltung['verein']} ({_datum_kurz(veranstaltung['datum'])})"
    story.append(Paragraph(titel, _TITEL))
    story.append(Paragraph(
        "Rot hervorgehobene „Impfpass gültig bis“-Einträge sind zum Prüfungstag "
        "abgelaufen oder noch nicht hinterlegt.",
        _HINWEIS,
    ))
    story.append(Spacer(1, 2 * mm))

    if not teilnehmer:
        story.append(Paragraph("Keine Teilnehmer erfasst.", _TEXT))
    else:
        kopf_texte = [
            "Nachname", "Vorname", "Verein", "Hund", "Chip-Nr.", "Leistungs-\nklasse",
            "Prüfungs-\ngebühr", "bezahlt?", "Impfpass\ngültig bis",
        ]
        daten = [[Paragraph(k.replace("\n", "<br/>"), _UEBERSICHT_KOPF) for k in kopf_texte]]
        for t in teilnehmer:
            gebuehr = _euro_text(pruefungsgebuehr_fuer_art(veranstaltung, t["art"]))
            impfung_iso = t["tollwutimpfung_bis"]
            lk_text = leistungsklasse_label(t)
            if t.get("keine_teilnahme"):
                # Nutzerwunsch 02.10.2026: nicht erschienene Teilnehmer bleiben hier (die
                # Gebühr kann trotzdem fällig sein), aber mit sichtbarem Vermerk.
                lk_text += "<br/><i>keine Teilnahme</i>"
            impfung_stil = (
                _UEBERSICHT_ZELLE_ROT if _impfung_hervorheben(impfung_iso, pruefungsdatum) else _UEBERSICHT_ZELLE
            )
            daten.append([
                Paragraph(_p_wert(t["nachname"]), _UEBERSICHT_ZELLE),
                Paragraph(_p_wert(t["vorname"]), _UEBERSICHT_ZELLE),
                Paragraph(_p_wert(t["verein"]), _UEBERSICHT_ZELLE),
                Paragraph(_p_wert(t["rufname_hund"]), _UEBERSICHT_ZELLE),
                Paragraph(_p_wert(t["chip_nr"]), _UEBERSICHT_ZELLE),
                Paragraph(lk_text, _UEBERSICHT_ZELLE),
                Paragraph(gebuehr, _UEBERSICHT_ZELLE),
                Paragraph("Ja" if t["bezahlt"] else "", _UEBERSICHT_ZELLE),
                Paragraph(_datum_kurz(impfung_iso) or "–", impfung_stil),
            ])
        spalten = [26 * mm, 22 * mm, 32 * mm, 24 * mm, 30 * mm, 34 * mm, 20 * mm, 20 * mm, 28 * mm]
        tabelle = Table(daten, colWidths=spalten, repeatRows=1)
        tabelle.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, 0), 1.5 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 1.5 * mm),
            ("TOPPADDING", (0, 1), (-1, -1), 2.5 * mm),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 2.5 * mm),
        ]))
        story.append(tabelle)

    SimpleDocTemplate(
        pfad, pagesize=landscape(A4),
        topMargin=12 * mm, bottomMargin=12 * mm, leftMargin=15 * mm, rightMargin=15 * mm,
    ).build(story)


# --- Chipnummernliste -------------------------------------------------------
#
# Nutzerwunsch (21.09.): die Chip-Nr. steht zwar schon auf jedem Bewertungsbogen und als
# eigene Spalte in der "Übersicht für Prüfungsleitung"-PDF - Marco bekommt aber weiterhin
# von anderen Vereinsmitgliedern Nachfragen danach. Deshalb ein eigener, bewusst
# kompakter Export nur mit Start-Nr./Name/Hund/Chip-Nr. (der Hund-Rufname zusätzlich zur
# Eindeutigkeit, falls zwei Teilnehmer denselben Nachnamen haben), sortiert nach
# Startnummer statt wie die Übersicht für Prüfungsleitung nach Name - Anwendungsfall ist
# der Abgleich am Prüfungstag, z.B. an einer Chip-Scanner-Station, wo die Startnummer die
# naheliegendere Sortierung ist.

_CHIPLISTE_KOPF = ParagraphStyle(
    "SHSChiplisteKopf", parent=_STYLES["Normal"], fontSize=9.5, fontName="Helvetica-Bold", leading=11,
)
_CHIPLISTE_ZELLE = ParagraphStyle("SHSChiplisteZelle", parent=_STYLES["Normal"], fontSize=10, leading=12)


def erstelle_chipnummernliste_pdf(conn: sqlite3.Connection, pfad: str) -> None:
    """Kompakter Export nur mit Start-Nr./Name/Hund/Chip-Nr., sortiert nach Startnummer -
    siehe Modulkommentar oben."""
    veranstaltung = get_veranstaltung(conn)
    teilnehmer = sorted(
        list_teilnehmer(conn, nur_teilnehmende=True), key=lambda t: (t["startnummer"] is None, t["startnummer"])
    )

    story: list = []
    titel = "Chipnummernliste"
    if veranstaltung:
        titel += f" – {veranstaltung['verein']} ({_datum_kurz(veranstaltung['datum'])})"
    story.append(Paragraph(titel, _TITEL))
    story.append(Spacer(1, 2 * mm))

    if not teilnehmer:
        story.append(Paragraph("Keine Teilnehmer erfasst.", _TEXT))
    else:
        kopf_texte = ["Start-Nr.", "Name", "Hund", "Chip-Nr."]
        daten = [[Paragraph(k, _CHIPLISTE_KOPF) for k in kopf_texte]]
        for t in teilnehmer:
            daten.append([
                Paragraph(_p_wert(t["startnummer"]), _CHIPLISTE_ZELLE),
                Paragraph(_p_wert(f"{t['nachname']}, {t['vorname']}"), _CHIPLISTE_ZELLE),
                Paragraph(_p_wert(t["rufname_hund"]), _CHIPLISTE_ZELLE),
                Paragraph(_p_wert(t["chip_nr"]), _CHIPLISTE_ZELLE),
            ])
        spalten = [22 * mm, 60 * mm, 42 * mm, 42 * mm]
        tabelle = Table(daten, colWidths=spalten, repeatRows=1)
        tabelle.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
        ]))
        story.append(tabelle)

    SimpleDocTemplate(
        pfad, pagesize=A4,
        topMargin=16 * mm, bottomMargin=16 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
    ).build(story)


# --- Richter-Bedarf -----------------------------------------------
#
# Berechnung nach Vorgabe des Vereins: 1 Einzeldisziplin (ED) = 1 Einheit, 1 Dreikampf
# (DK) = 3 Einheiten (ein Dreikampf-Teilnehmer bindet einen Richter für alle drei
# Disziplinen). Ein Richter darf höchstens 36 Einheiten an einem Prüfungstag
# richten - die benötigte Richterzahl ergibt sich aus den Gesamteinheiten, aufgerundet.
# Konstanten LR_EINHEITEN_JE_ART/LR_EINHEITEN_PRO_RICHTER zentral in db.py (single source
# of truth, auch für db.berechne_teilnehmer_lk_uebersicht() - den GUI-Reiter "Übersicht
# Teilnehmer und LK" in app.py).


def erstelle_leistungsrichter_bedarf_pdf(conn: sqlite3.Connection, pfad: str) -> None:
    """Übersicht zur Berechnung der benötigten Richter: zeigt je Art/
    Leistungsklasse die Teilnehmerzahl und die daraus resultierenden Einheiten
    (1 ED = 1 Einheit, 1 DK = 3 Einheiten), sowie darunter die Gesamteinheiten und die
    (aufgerundete) Anzahl benötigter Richter bei höchstens 36 Einheiten je
    Richter. Darunter der Behältnis-Bedarf der Behältnisstrecke je LK (siehe
    db.berechne_behaeltnis_bedarf)."""
    veranstaltung = get_veranstaltung(conn)
    teilnehmer = list_teilnehmer(conn, nur_teilnehmende=True)

    story: list = []
    titel = "Richter-Bedarf"
    if veranstaltung:
        titel += f" – {veranstaltung['verein']} ({_datum_kurz(veranstaltung['datum'])})"
    story.append(Paragraph(titel, _TITEL))
    story.append(Paragraph(
        "1 Einzeldisziplin (ED) = 1 Einheit, 1 Dreikampf (DK) = 3 Einheiten. Ein "
        f"Richter darf höchstens {LR_EINHEITEN_PRO_RICHTER} Einheiten an einem "
        "Prüfungstag richten.",
        _HINWEIS,
    ))
    story.append(Spacer(1, 2 * mm))

    gesamt_einheiten = 0
    if not teilnehmer:
        story.append(Paragraph("Keine Teilnehmer erfasst.", _TEXT))
    else:
        labels = sorted({leistungsklasse_label(t) for t in teilnehmer})
        daten = [["Art / Leistungsklasse", "Teilnehmer", "Einheiten je Teilnehmer", "Einheiten gesamt"]]
        for label in labels:
            gruppe = [t for t in teilnehmer if leistungsklasse_label(t) == label]
            einheiten_je_teilnehmer = LR_EINHEITEN_JE_ART[gruppe[0]["art"]]
            summe = len(gruppe) * einheiten_je_teilnehmer
            gesamt_einheiten += summe
            daten.append([label, str(len(gruppe)), str(einheiten_je_teilnehmer), str(summe)])

        tabelle = Table(daten, colWidths=[75 * mm, 30 * mm, 45 * mm, 35 * mm], repeatRows=1)
        tabelle.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
        ]))
        story.append(tabelle)

    richter_benoetigt = math.ceil(gesamt_einheiten / LR_EINHEITEN_PRO_RICHTER) if gesamt_einheiten else 0
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph(f"Gesamteinheiten: {gesamt_einheiten}", _TEXT_FETT))
    story.append(Paragraph(
        f"Benötigte Richter (je höchstens {LR_EINHEITEN_PRO_RICHTER} Einheiten, "
        f"aufgerundet): {richter_benoetigt}",
        _TEXT_FETT,
    ))

    # Behältnis-Bedarf (Nutzerwunsch 25.09.) - dieselbe Tabelle wie im Reiter "Übersicht",
    # auch ohne Teilnehmer (dann mit Nullen).
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(BEHAELTNIS_BEDARF_TITEL, _TEXT_FETT))
    story.append(Spacer(1, 2 * mm))
    behaeltnis_daten = [BEHAELTNIS_BEDARF_SPALTEN] + [
        behaeltnis_bedarf_zeilentexte(zeile) for zeile in berechne_behaeltnis_bedarf(conn)
    ]
    behaeltnis_tabelle = Table(
        behaeltnis_daten, colWidths=[58 * mm, 22 * mm, 14 * mm, 28 * mm, 34 * mm, 18 * mm]
    )
    behaeltnis_tabelle.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        # Kopfzeile etwas kleiner, damit "mit Gegenstand"/"Material-Verleitung" mit
        # Innenabstand in ihre Spalten passen (Nutzerwunsch 25.09.).
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
    ]))
    story.append(behaeltnis_tabelle)
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(BEHAELTNIS_BEDARF_HINWEIS, _HINWEIS))

    SimpleDocTemplate(
        pfad, pagesize=A4,
        topMargin=16 * mm, bottomMargin=16 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
    ).build(story)


# --- Zeitplan --------------------------------------------------------------
#
# Layout eigens entworfen (das Original hatte für den Zeitplan keine Berechnungslogik,
# siehe Fortschritt.md - es wurde dort nur eine von Hand geplante Liste eingelesen und
# angezeigt): eine Seite je Richter mit einer Zeile je Teilnehmer bzw. je Pause,
# jeweils mit Start-/Endzeit (siehe db.berechne_zeitplan). Jede Art/Leistungsklasse-
# Kombination (ED LK 1-3, DK LK 1-3) bekommt eine EIGENE, feste Farbe (unabhängig von der
# Disziplin) als schnelle visuelle Orientierung für den Richter - z. B. damit alle drei
# Disziplin-Blöcke eines Dreikampf-Teilnehmers derselben Leistungsklasse durchgehend
# gleich eingefärbt bleiben, statt je nach Disziplin zu wechseln.

_ZEITPLAN_ZEILE = ParagraphStyle("SHSZeitplanZeile", parent=_STYLES["Normal"], fontSize=9, leading=11)
_ZEITPLAN_ZEIT = ParagraphStyle("SHSZeitplanZeit", parent=_STYLES["Normal"], fontSize=9.5, fontName="Helvetica-Bold", leading=11)
_ZEITPLAN_PAUSE_TEXT = ParagraphStyle("SHSZeitplanPauseText", parent=_STYLES["Normal"], fontSize=9, fontName="Helvetica-Oblique", leading=11)

#: Feste Farbe je Art/Leistungsklasse-Kombination - es gibt höchstens sechs (ED/DK × LK
#: 1-3, siehe CHECK-Constraints in db.SCHEMA), daher reicht eine feste Zuordnung ohne
#: dynamische Farbvergabe; dieselbe Leistungsklasse sieht dadurch in jedem Export gleich
#: aus, unabhängig davon, welche Leistungsklassen im jeweiligen Termin sonst vorkommen.
_ZEITPLAN_FARBE_JE_LK = {
    ("ED", 1): colors.HexColor("#d9ead3"),   # grün
    ("ED", 2): colors.HexColor("#fff2cc"),   # gelb
    ("ED", 3): colors.HexColor("#cfe2f3"),   # blau
    ("DK", 1): colors.HexColor("#f4cccc"),   # rot
    ("DK", 2): colors.HexColor("#d9d2e9"),   # lila
    ("DK", 3): colors.HexColor("#fce5cd"),   # orange
}
_ZEITPLAN_PAUSE_FARBE = colors.HexColor("#eeeeee")


def _zeitplan_zeile_farbe(zeile: dict):
    if zeile["typ"] == "pause":
        return _ZEITPLAN_PAUSE_FARBE
    return _ZEITPLAN_FARBE_JE_LK[(zeile["art"], zeile["stufe"])]


def _zeitplan_richter_tabelle(plan: dict) -> Table:
    daten = [["Uhrzeit", "Art / LK / Disziplin", "Start-Nr.", "Name", "Hund"]]
    stil = [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.8 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8 * mm),
    ]
    for i, zeile in enumerate(plan["zeilen"], start=1):
        zeit_text = f"{zeile['start'].strftime('%H:%M')} – {zeile['ende'].strftime('%H:%M')}"
        art_text = f"{zeile.get('art', '')} LK {zeile.get('stufe', '')} – {zeile.get('disziplin', '')}" if zeile["typ"] != "pause" else ""
        if zeile["typ"] == "pause":
            daten.append([
                Paragraph(zeit_text, _ZEITPLAN_ZEIT),
                Paragraph(_p_wert(zeile["bezeichnung"]), _ZEITPLAN_PAUSE_TEXT),
                "", "", "",
            ])
            stil.append(("SPAN", (1, i), (4, i)))
        elif zeile["teilnehmer"] is None:
            # Bereits angelegter Prüfungsblock, für den (noch) kein passender Teilnehmer
            # gemeldet ist - erscheint trotzdem als Zeile, statt spurlos zu fehlen.
            daten.append([
                Paragraph(zeit_text, _ZEITPLAN_ZEIT),
                Paragraph(art_text, _ZEITPLAN_ZEILE),
                Paragraph("(noch keine Teilnehmer gemeldet)", _ZEITPLAN_PAUSE_TEXT),
                "", "",
            ])
            stil.append(("SPAN", (2, i), (4, i)))
        else:
            t = zeile["teilnehmer"]
            daten.append([
                Paragraph(zeit_text, _ZEITPLAN_ZEIT),
                Paragraph(art_text, _ZEITPLAN_ZEILE),
                Paragraph(_p_wert(t["startnummer"]), _ZEITPLAN_ZEILE),
                Paragraph(f"{_p_wert(t['nachname'])}, {_p_wert(t['vorname'])}", _ZEITPLAN_ZEILE),
                Paragraph(_p_wert(t["rufname_hund"]), _ZEITPLAN_ZEILE),
            ])
        stil.append(("BACKGROUND", (0, i), (-1, i), _zeitplan_zeile_farbe(zeile)))

    tabelle = Table(daten, colWidths=[28 * mm, 55 * mm, 20 * mm, 55 * mm, 42 * mm], repeatRows=1)
    tabelle.setStyle(TableStyle(stil))
    return tabelle


def erstelle_zeitplan_pdf(conn: sqlite3.Connection, pfad: str) -> None:
    """Zeitplan-PDF: eine Seite je Richter mit der vollständigen, zeilenweise
    berechneten Abfolge (siehe db.berechne_zeitplan) aus Prüfungsblöcken (eine Zeile je
    Teilnehmer, mit Start-/Endzeit) und Pausen - farblich nach Art/Leistungsklasse
    unterschieden (jede der sechs möglichen Kombinationen ED/DK × LK 1-3 hat eine feste,
    eigene Farbe, siehe _ZEITPLAN_FARBE_JE_LK). Ist noch kein Richter angelegt,
    enthält die PDF nur einen entsprechenden Hinweis statt einer leeren Seite."""
    veranstaltung = get_veranstaltung(conn)
    plaene = berechne_zeitplan(conn)

    story: list = []
    if not plaene:
        titel = "Zeitplan"
        if veranstaltung:
            titel += f" – {veranstaltung['verein']} ({_datum_kurz(veranstaltung['datum'])})"
        story.append(Paragraph(titel, _TITEL))
        story.append(Paragraph("Es sind noch keine Richter/Zeitplan-Einträge angelegt.", _TEXT))
    else:
        for i, plan in enumerate(plaene):
            if i > 0:
                story.append(PageBreak())
            titel = f"Zeitplan – {plan['richter']}"
            if veranstaltung:
                titel += f" ({veranstaltung['verein']}, {_datum_kurz(veranstaltung['datum'])})"
            story.append(Paragraph(titel, _TITEL))
            story.append(Spacer(1, 2 * mm))
            if not plan["zeilen"]:
                story.append(Paragraph("Noch keine Prüfungsblöcke/Pausen für diesen Richter eingeplant.", _TEXT))
            else:
                story.append(_zeitplan_richter_tabelle(plan))

    SimpleDocTemplate(
        pfad, pagesize=A4,
        topMargin=14 * mm, bottomMargin=14 * mm, leftMargin=16 * mm, rightMargin=16 * mm,
    ).build(story)


# --- Anmeldeformular (ausfüllbares PDF) --------------------------------------
# Nutzerwunsch 28.09.2026: Das bisherige Word-Anmeldeformular wird durch ein vom Programm je
# Termin erzeugtes, ausfüllbares PDF ersetzt. Der Kopf (Veranstalter, Verband, Meldestelle,
# Datum) ist fest eingedruckt, ankreuzbar sind nur die für den Termin angebotenen Prüfungen
# (Veranstaltungsdaten im Reiter "Verwaltung"). Die Teilnehmer füllen es z. B. in Acrobat
# Reader oder im Browser aus; das zurückgeschickte PDF liest der Reiter "Formular-Import"
# direkt ein (db_import.importiere_anmeldeformular_pdf).
# Bewusst mit reportlab.pdfgen.canvas statt wie die übrigen Berichte mit platypus: platypus
# kennt keine Formularfelder, canvas.acroForm setzt Textfelder und Kästchen an feste
# Koordinaten - und das Formular ist ohnehin ein festes Einseiten-Layout ohne Umbruch.
# Die Feldnamen stammen ausschließlich aus db.py (ANMELDEFORMULAR_*), damit Erzeugung und
# Import nie auseinanderlaufen.

_AF_RAND = 16 * mm
_AF_BREITE = A4[0] - 2 * _AF_RAND
_AF_SPALTEN_ABSTAND = 8 * mm
_AF_SPALTE = (_AF_BREITE - _AF_SPALTEN_ABSTAND) / 2
_AF_FELD_HOEHE = 14
_AF_ZEILE = 18      # Abstand zweier Eingabezeilen
_AF_KREUZ = 10      # Kantenlänge der Ankreuzkästchen
_AF_LUECKE = 6      # Abstand zwischen zwei Feldern/Kästchen derselben Zeile
_AF_SCHRIFT = 9     # ganzzahlig, reportlab schreibt die Feld-Schriftgröße als %d
_AF_MELDESTELLE_MAX_ZEILEN = 7  # darüber wird gekürzt (Schrift bliebe sonst unter ~6,5 pt)
_AF_FELD_HINTERGRUND = colors.HexColor("#eef3fb")
_AF_FELD_RAHMEN = colors.HexColor("#7f8fa9")

_AF_ERKLAERUNG = [
    "Mir ist bekannt, dass die Teilnahme ohne gültige Tollwutschutzimpfung des Hundes nicht "
    "erlaubt ist und die Teilnahme auf eigene Rechnung und Gefahr erfolgt.",
    "Der Hund ist haftpflichtversichert und – soweit von einer Landeshundeordnung betroffen – "
    "liegt eine Haltererlaubnis vor.",
    "Ich akzeptiere das derzeit gültige Spürhundesport Regelwerk des VDH.",
    "Ich verpflichte mich, nach Eingang einer Meldebestätigung das in der Ausschreibung "
    "genannte Startgeld zu zahlen.",
    "Ich erkläre mich einverstanden, dass meine hier aufgeführten persönlichen Daten im Rahmen "
    "der Prüfung verwendet werden (Kommunikation des Ausrichters, Erfassung in "
    "Auswertesoftware, Übergabe der Prüfungsunterlagen an die Statistik führende Stelle bzw. "
    "den Wertungsrichter und übergeordnete Verbände).",
]
_AF_ERKLAERUNG_FETT = (
    "Mit meiner Unterschrift bestätige ich, dass ich Kenntnis von der "
    "Tierschutz-Hundeverordnung habe und diese beachte."
)
_AF_ERKLAERUNG_STIL = ParagraphStyle(
    "SHSAnmeldeErklaerung", parent=_STYLES["Normal"], fontName="Helvetica", fontSize=8, leading=9.8,
)


class _Feld(NamedTuple):
    """Beschriftetes Textfeld einer Formularzeile; `breite` None = restliche Spaltenbreite."""
    label: str
    name: str
    breite: float | None = None
    hinweis: str | None = None  # Tooltip, v. a. für Felder ohne eigene Beschriftung


class _Kreuz(NamedTuple):
    """Beschriftung mit dahinterliegendem Ankreuzkästchen."""
    label: str
    name: str


class _Text(NamedTuple):
    """Reiner Text innerhalb einer Formularzeile (z. B. die Einheit "cm")."""
    text: str


def _af_textbreite(text: str, fett: bool = False) -> float:
    return stringWidth(text, "Helvetica-Bold" if fett else "Helvetica", _AF_SCHRIFT)


def _af_hart_umbrechen(zeilen: list[str], max_breite_pt: float) -> list[str]:
    """Bricht Zeilen zusätzlich zeichenweise um, die auch nach simpleSplit noch zu breit
    sind - simpleSplit trennt nur an Leerzeichen, ein einzelnes sehr langes Wort (lange
    E-Mail-Adresse, URL) liefe sonst über den Kopfkasten des Anmeldeformulars hinaus
    (zweite Verifikation 28.09.2026, N2)."""
    ergebnis: list[str] = []
    for zeile in zeilen:
        while stringWidth(zeile, "Helvetica", _AF_SCHRIFT) > max_breite_pt and len(zeile) > 1:
            laenge = len(zeile) - 1
            while laenge > 1 and stringWidth(zeile[:laenge], "Helvetica", _AF_SCHRIFT) > max_breite_pt:
                laenge -= 1
            ergebnis.append(zeile[:laenge])
            zeile = zeile[laenge:]
        ergebnis.append(zeile)
    return ergebnis


def _af_label_breite(label: str) -> float:
    return _af_textbreite(label) + 6 if label else 0


def _af_platzbedarf(segment) -> float:
    """Mindestbreite eines Zeilensegments (für die Restbreite eines `_Feld` ohne Breite)."""
    if isinstance(segment, _Text):
        return _af_textbreite(segment.text)
    if isinstance(segment, _Kreuz):
        return _af_label_breite(segment.label) + _AF_KREUZ
    return _af_label_breite(segment.label) + (segment.breite or 0)


class _AnmeldeformularZeichner:
    """Zeichnet das Anmeldeformular von oben nach unten auf eine A4-Seite; `self.y` ist
    jeweils die Oberkante der nächsten Zeile."""

    def __init__(self, c: rl_canvas.Canvas):
        self.c = c
        self.y = A4[1] - 10 * mm

    # -- Grundbausteine --

    def text(self, x: float, y: float, text: str, groesse: float = _AF_SCHRIFT, fett: bool = False) -> None:
        self.c.setFont("Helvetica-Bold" if fett else "Helvetica", groesse)
        self.c.drawString(x, y, text)

    def textfeld(self, name: str, x: float, y_unten: float, breite: float, hinweis: str) -> None:
        self.c.acroForm.textfield(
            name=name, tooltip=hinweis, x=x, y=y_unten, width=breite, height=_AF_FELD_HOEHE,
            fontName="Helvetica", fontSize=_AF_SCHRIFT, textColor=colors.black,
            fillColor=_AF_FELD_HINTERGRUND, borderColor=_AF_FELD_RAHMEN, borderWidth=0.5,
            fieldFlags="", maxlen=None,
        )

    def kreuz(self, name: str, x: float, y_unten: float, hinweis: str) -> None:
        # fieldFlags="" statt reportlab-Standard "required": sonst markieren manche
        # Viewer jedes nicht angekreuzte Kästchen als Pflichtfeld.
        self.c.acroForm.checkbox(
            name=name, tooltip=hinweis, x=x, y=y_unten, size=_AF_KREUZ, buttonStyle="cross",
            textColor=colors.black, fillColor=_AF_FELD_HINTERGRUND, borderColor=_AF_FELD_RAHMEN,
            borderWidth=0.5, fieldFlags="",
        )

    def ueberschrift(self, titel: str, abstand_oben: float = 7) -> None:
        self.y -= abstand_oben
        self.text(_AF_RAND, self.y - 10, titel, groesse=10, fett=True)
        self.c.setStrokeColor(colors.grey)
        self.c.setLineWidth(0.4)
        self.c.line(_AF_RAND, self.y - 13.5, _AF_RAND + _AF_BREITE, self.y - 13.5)
        self.c.setStrokeColor(colors.black)
        self.y -= 18

    # -- Formularzeilen --

    def _spalte(self, x: float, breite: float, segmente: list, label_breite: float) -> None:
        """Eine Spalte der aktuellen Zeile. `label_breite` ist die Breite der Beschriftung
        des ersten Felds, damit die Felder eines Abschnitts bündig untereinander stehen."""
        y_feld = self.y - _AF_FELD_HOEHE
        y_text = y_feld + 4  # Grundlinie der Beschriftung, mittig zur Feldhöhe
        cursor = x
        for i, segment in enumerate(segmente):
            if isinstance(segment, _Text):
                self.text(cursor, y_text, segment.text)
                cursor += _af_textbreite(segment.text) + _AF_LUECKE
                continue
            if segment.label:
                self.text(cursor, y_text, segment.label)
            label_breite_hier = _af_label_breite(segment.label)
            if i == 0 and isinstance(segment, _Feld):
                label_breite_hier = max(label_breite_hier, label_breite)
            cursor += label_breite_hier
            hinweis = segment.label.rstrip(": ")
            if isinstance(segment, _Kreuz):
                self.kreuz(segment.name, cursor, y_feld + (_AF_FELD_HOEHE - _AF_KREUZ) / 2, hinweis)
                cursor += _AF_KREUZ + 2 * _AF_LUECKE
                continue
            feld_breite = segment.breite
            if feld_breite is None:
                rest = sum(_af_platzbedarf(s) + _AF_LUECKE for s in segmente[i + 1:])
                feld_breite = x + breite - cursor - rest
            self.textfeld(segment.name, cursor, y_feld, feld_breite, segment.hinweis or hinweis)
            cursor += feld_breite + _AF_LUECKE

    def abschnitt(self, titel: str, zeilen: list[tuple]) -> None:
        """Abschnitt mit Überschrift und Eingabezeilen. Jede Zeile ist (links, rechts) für
        zwei Spalten (rechts darf leer sein) oder (ganze_breite,) für eine durchgehende Zeile."""
        self.ueberschrift(titel)

        def label_spalte(index: int) -> float:
            breiten = [
                _af_label_breite(z[index][0].label) for z in zeilen
                if len(z) == 2 and z[index] and isinstance(z[index][0], _Feld)
            ]
            return max(breiten, default=0)

        label_links, label_rechts = label_spalte(0), label_spalte(1)
        for zeile in zeilen:
            if len(zeile) == 1:
                self._spalte(_AF_RAND, _AF_BREITE, zeile[0], 0)
            else:
                links, rechts = zeile
                self._spalte(_AF_RAND, _AF_SPALTE, links, label_links)
                self._spalte(_AF_RAND + _AF_SPALTE + _AF_SPALTEN_ABSTAND, _AF_SPALTE, rechts, label_rechts)
            self.y -= _AF_ZEILE

    # -- Feste Formularteile --

    def titel_und_kopf(self, veranstaltung: dict) -> None:
        titel = "Anmeldeformular SHS-Wettkampf"
        self.text(_AF_RAND, self.y - 16, titel, groesse=17, fett=True)
        self.c.setLineWidth(1)
        self.c.line(_AF_RAND, self.y - 19, _AF_RAND + stringWidth(titel, "Helvetica-Bold", 17), self.y - 19)
        self.y -= 30

        # Kopfkasten: links Veranstalter/Meldestelle, rechts Verband/Datum - nur Text,
        # keine Felder (kommt aus den Veranstaltungsdaten).
        innen = 5
        x_rechts = _AF_RAND + _AF_BREITE * 0.62
        label_links = _af_textbreite("Meldestelle:", fett=True) + 6
        label_rechts = _af_textbreite("Verband:", fett=True) + 6
        wert_x_links = _AF_RAND + innen + label_links
        wert_breite_links = x_rechts - innen - wert_x_links
        wert_x_rechts = x_rechts + innen + label_rechts
        wert_breite_rechts = _AF_RAND + _AF_BREITE - innen - wert_x_rechts

        meldestelle: list[str] = []
        for absatz in (veranstaltung.get("meldestelle") or "").strip().splitlines():
            meldestelle += _af_hart_umbrechen(
                simpleSplit(absatz.strip(), "Helvetica", _AF_SCHRIFT, wert_breite_links) or [""],
                wert_breite_links,
            )
        # Bis 5 Zeilen in normaler Größe; eine noch längere Meldestelle wird enger und
        # kleiner gesetzt, damit das Formular sicher auf EINE Seite passt. Höchstens
        # _AF_MELDESTELLE_MAX_ZEILEN Zeilen (danach "…"), sonst würde die Schrift ohne
        # Untergrenze unleserlich klein (Verifikation 28.09.2026, Befund 7b).
        if len(meldestelle) > _AF_MELDESTELLE_MAX_ZEILEN:
            meldestelle = meldestelle[:_AF_MELDESTELLE_MAX_ZEILEN]
            # Zweite Verifikation 28.09.2026, N3: so weit kürzen, dass " …" noch in die
            # Breite passt, statt über den Kasten hinauszuragen.
            letzte = meldestelle[-1].rstrip()
            while letzte and stringWidth(letzte + " …", "Helvetica", _AF_SCHRIFT) > wert_breite_links:
                letzte = letzte[:-1].rstrip()
            meldestelle[-1] = letzte + " …"
        zeilenabstand = min(11, 5 * 11 / max(len(meldestelle), 1))
        meldestelle_groesse = min(_AF_SCHRIFT, zeilenabstand * 0.82)
        hoehe_oben = 18
        hoehe_unten = max(18, len(meldestelle) * zeilenabstand + 7)
        oben = self.y
        unten = oben - hoehe_oben - hoehe_unten

        self.c.setLineWidth(0.7)
        self.c.rect(_AF_RAND, unten, _AF_BREITE, hoehe_oben + hoehe_unten)
        self.c.line(_AF_RAND, oben - hoehe_oben, _AF_RAND + _AF_BREITE, oben - hoehe_oben)
        self.c.line(x_rechts, unten, x_rechts, oben)

        def wert(x: float, y: float, text: str, max_breite: float) -> None:
            groesse = _schriftgroesse_fuer_breite(text, max_breite, _AF_SCHRIFT + 1, 7)
            self.text(x, y, text, groesse=groesse)

        y1 = oben - 12.5
        self.text(_AF_RAND + innen, y1, "Veranstalter:", fett=True)
        wert(wert_x_links, y1, veranstaltung.get("verein") or "", wert_breite_links)
        self.text(x_rechts + innen, y1, "Verband:", fett=True)
        wert(wert_x_rechts, y1, veranstaltung.get("verband") or "", wert_breite_rechts)

        y2 = oben - hoehe_oben - 12.5
        self.text(_AF_RAND + innen, y2, "Meldestelle:", fett=True)
        for i, zeile in enumerate(meldestelle):
            self.text(wert_x_links, y2 - i * zeilenabstand, zeile, groesse=meldestelle_groesse)
        self.text(x_rechts + innen, y2, "Datum:", fett=True)
        wert(wert_x_rechts, y2, datum_anzeige(veranstaltung.get("datum")), wert_breite_rechts)
        self.y = unten

    def pruefungen(self, angebot: list) -> None:
        """"Bitte ankreuzen!"-Kasten: je Art/Disziplin eine Reihe, je Leistungsklasse eine
        Spalte (wie im bisherigen Word-Formular), nicht angebotene Prüfungen fehlen."""
        self.y -= 12
        self.text(_AF_RAND, self.y - 9, "Bitte ankreuzen!", fett=True)
        self.y -= 13
        reihen: list[tuple] = []
        for p in angebot:
            if (p.art, p.disziplin) not in reihen:
                reihen.append((p.art, p.disziplin))
        innen = 6
        reihen_abstand = 17
        spalten_breite = (_AF_BREITE - 2 * innen) / 3
        label_breite = max(_af_textbreite(f"{p.bezeichnung}:") for p in angebot) + 8
        hoehe = len(reihen) * reihen_abstand + 5
        self.c.setLineWidth(0.7)
        self.c.rect(_AF_RAND, self.y - hoehe, _AF_BREITE, hoehe)
        for r, reihe in enumerate(reihen):
            y_kreuz = self.y - (r + 1) * reihen_abstand
            for p in angebot:
                if (p.art, p.disziplin) != reihe:
                    continue
                x = _AF_RAND + innen + (p.stufe - 1) * spalten_breite
                self.text(x, y_kreuz + 2, f"{p.bezeichnung}:")
                self.kreuz(ANMELDEFORMULAR_PRUEFUNG_PRAEFIX + p.kuerzel, x + label_breite, y_kreuz, p.bezeichnung)
        self.y -= hoehe

    def gegenstaende(self, stufen: list[int]) -> None:
        """Je angebotener Leistungsklasse so viele Gegenstands-Felder, wie die LK
        Gegenstände hat (LK 1: eins, LK 2: zwei, LK 3: drei)."""
        self.ueberschrift("Gegenstände")
        label_breite = _af_label_breite("LK 3:") + 4
        feld_breite = (_AF_BREITE - label_breite - 2 * _AF_LUECKE) / 3
        for stufe in stufen:
            segmente = [
                _Feld(f"LK {stufe}:" if n == 1 else "", anmeldeformular_gegenstand_feld(stufe, n), feld_breite,
                      f"Gegenstand {n} für LK {stufe}")
                for n in range(1, stufe + 1)
            ]
            self._spalte(_AF_RAND, _AF_BREITE, segmente, label_breite)
            self.y -= _AF_ZEILE

    def erklaerung_und_unterschrift(self) -> None:
        self.y -= 6
        titel = "Erklärung des Teilnehmers:"
        self.text(_AF_RAND, self.y - 9, titel, fett=True)
        self.c.setLineWidth(0.6)
        self.c.line(_AF_RAND, self.y - 11, _AF_RAND + _af_textbreite(titel, fett=True), self.y - 11)
        self.y -= 13
        text = "<br/>".join(_xml_escape(s) for s in _AF_ERKLAERUNG)
        text += f"<br/><b>{_xml_escape(_AF_ERKLAERUNG_FETT)}</b>"
        absatz = Paragraph(text, _AF_ERKLAERUNG_STIL)
        _, hoehe = absatz.wrapOn(self.c, _AF_BREITE, A4[1])
        absatz.drawOn(self.c, _AF_RAND, self.y - hoehe)
        self.y -= hoehe + 18

        y_linie = self.y - _AF_FELD_HOEHE
        self.text(_AF_RAND, y_linie + 4, "Datum:")
        self.textfeld(ANMELDEFORMULAR_UNTERSCHRIFT_DATUM, _AF_RAND + _af_label_breite("Datum:"), y_linie, 32 * mm, "Datum")
        x_unterschrift = _AF_RAND + _AF_BREITE * 0.48
        self.c.setLineWidth(0.6)
        self.c.line(x_unterschrift, y_linie, _AF_RAND + _AF_BREITE, y_linie)
        self.text(x_unterschrift, y_linie - 9, "Unterschrift des Teilnehmers /", groesse=7.5)
        self.text(x_unterschrift, y_linie - 18, "bei Minderjährigen Unterschrift eines Erziehungsberechtigten", groesse=7.5)
        self.y = y_linie - 18


def erstelle_anmeldeformular_pdf(conn: sqlite3.Connection, pfad: str) -> None:
    """Ausfüllbares Anmeldeformular (eine A4-Seite) für den geöffneten Termin, siehe
    Kommentar oben. Ohne hinterlegte angebotene Prüfungen gibt es nichts anzukreuzen -
    dann ValueError mit einem für den Nutzer verständlichen Hinweis."""
    veranstaltung = get_veranstaltung(conn) or {}
    angebot = angebotene_pruefungen(veranstaltung)
    if not angebot:
        raise ValueError("Bitte zuerst in den Veranstaltungsdaten die angebotenen Prüfungen auswählen.")

    c = rl_canvas.Canvas(pfad, pagesize=A4)
    c.setTitle("Anmeldeformular SHS-Wettkampf")
    if veranstaltung.get("verein"):
        c.setAuthor(veranstaltung["verein"])
    z = _AnmeldeformularZeichner(c)
    z.titel_und_kopf(veranstaltung)
    z.pruefungen(angebot)
    z.gegenstaende(sorted({p.stufe for p in angebot}))

    def adresse(praefix: str) -> tuple:
        return (
            [_Feld("Straße / Nr.:", f"{praefix}strasse"), _Feld("", f"{praefix}hausnummer", 14 * mm, "Hausnummer")],
            [_Feld("PLZ / Wohnort:", f"{praefix}plz", 16 * mm, "PLZ"), _Feld("", f"{praefix}ort", None, "Wohnort")],
        )

    z.abschnitt("Wettkampfteilnehmer", [
        ([_Feld("Vorname:", "vorname")], [_Feld("Name:", "nachname")]),
        adresse(""),
        ([_Feld("Mitgl.-Nr.:", "mitgliedsnummer")], [_Feld("Telefonnummer:", "telefon")]),
        ([_Feld("E-Mail:", "email")], [_Feld("Mitgliedsverein:", "verein")]),
        ([_Feld("Verband:", "verband")], []),
        ([
            _Text("Am Prüfungstag habe ich das 18. Lebensjahr vollendet:"),
            _Kreuz("Ja", ANMELDEFORMULAR_VOLLJAEHRIG_JA),
            _Kreuz("Nein", ANMELDEFORMULAR_VOLLJAEHRIG_NEIN),
        ],),
    ])
    z.abschnitt("Falls abweichend von Teilnehmer – Angaben des Hundeeigentümers", [
        ([_Feld("Vorname:", "halter_vorname")], [_Feld("Name:", "halter_nachname")]),
        adresse("halter_"),
        ([_Feld("Mitgl.-Nr.:", "halter_mitgliedsnummer")], [_Feld("Mitgliedsverein:", "halter_mitgliedsverein")]),
        ([_Feld("LU-Nr.:", "halter_lu_nr")], []),
    ])
    z.abschnitt("Angaben zum Hund", [
        ([_Feld("Zuchtbuchname:", "zwingername")], [_Feld("Rufname des Hundes:", "rufname_hund")]),
        ([_Feld("Rasse:", "rasse")], [_Feld("Wurfdatum:", "wurftag", hinweis="Wurfdatum (TT.MM.JJJJ)")]),
        (
            [_Feld("Größe in cm:", "schulterhoehe_cm", 18 * mm, "Größe in cm"), _Text("cm")],
            [_Feld("Tollwutimpfung gültig bis:", "tollwutimpfung_bis",
                   hinweis="Tollwutimpfung gültig bis (TT.MM.JJJJ)")],
        ),
        (
            [
                _Kreuz("Chip-Nr.:", ANMELDEFORMULAR_KENNZEICHNUNG_CHIP),
                _Kreuz("Täto-Nr.:", ANMELDEFORMULAR_KENNZEICHNUNG_TAETO),
                _Feld("", "kennzeichnung_nr", None, "Chip- bzw. Täto-Nummer"),
            ],
            [_Kreuz("Hündin:", ANMELDEFORMULAR_HUENDIN), _Kreuz("Rüde:", ANMELDEFORMULAR_RUEDE)],
        ),
    ])
    z.erklaerung_und_unterschrift()
    c.showPage()
    c.save()
