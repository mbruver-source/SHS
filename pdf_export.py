"""
PDF-Ausgabe für das SHS-Prüfungsprogramm: Bewertungsbögen, Ergebnislisten, Statistik.

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

Alle Funktionen erwarten eine bereits offene `sqlite3.Connection` (siehe db.py) und einen
Zielpfad, unter dem die PDF-Datei geschrieben wird.
"""

from __future__ import annotations

import datetime
import math
import sqlite3
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
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
    ALLE_DISZIPLINEN,
    DISZIPLIN_SPALTEN,
    LR_EINHEITEN_JE_ART,
    LR_EINHEITEN_PRO_RICHTER,
    berechne_auswertung,
    berechne_zeitplan,
    gegenstand_fuer_disziplin,
    get_veranstaltung,
    ist_jugendlicher,
    leistungsklasse_label,
    list_teilnehmer,
    pruefungsgebuehr_fuer_art,
)
from shs_core import ABBRUCH_ABK, DISQUALIFIZIERT_ABK, berechne_wertnote_dk, berechne_wertnote_ed

# --- Gemeinsame Stile -------------------------------------------------------

_STYLES = getSampleStyleSheet()
_TITEL = ParagraphStyle("SHSTitel", parent=_STYLES["Heading1"], fontSize=14, spaceAfter=2 * mm)
_LK_TITEL = ParagraphStyle("SHSLkTitel", parent=_STYLES["Heading1"], fontSize=20, spaceAfter=0)
_UNTERTITEL = ParagraphStyle("SHSUntertitel", parent=_STYLES["Normal"], fontSize=10, spaceAfter=4 * mm)
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
    if not iso_datum:
        return ""
    try:
        d = datetime.date.fromisoformat(iso_datum.strip())
    except ValueError:
        return iso_datum
    return f"{_WOCHENTAGE[d.weekday()]}, {d.day}. {_MONATE[d.month - 1]} {d.year}"


def _datum_kurz(iso_datum: str | None) -> str:
    """Formatiert ein Datum im Format JJJJ-MM-TT kompakt als TT.MM.JJJJ - für Tabellen-
    spalten, in denen der ausgeschriebene Langtext (_datum_lang) zu breit wäre (siehe
    Impfpass-Spalte in erstelle_pruefungsleitung_uebersicht_pdf). Ist der Wert leer oder
    nicht als Datum erkennbar, wird er wie bei _datum_lang unverändert zurückgegeben."""
    if not iso_datum:
        return ""
    try:
        d = datetime.date.fromisoformat(iso_datum.strip())
    except ValueError:
        return iso_datum
    return f"{d.day:02d}.{d.month:02d}.{d.year}"


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
# über db.gegenstand_fuer_disziplin(). Gilt einheitlich für ED und DK.
_GEGENSTAND_FELDER = ("gegenstand_1", "gegenstand_2", "gegenstand_3")

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
_BEHAELTNIS_POSITIONEN = {1: 6, 2: 8, 3: 10}
_SUCHGEGENSTAENDE_TEXT = {1: "ein Suchgegenstand", 2: "zwei Suchgegenstände", 3: "drei Suchgegenstände"}


def _wert(v) -> str:
    return "" if v in (None, "") else str(v)


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
        ["ANZEIGE", "40 – 38", "37 – 36", "35 – 32", "31 – 28", "27 – 0"],
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


def _bewertungsabschnitt(disziplin: str, stufe: int, suche: int | None, anzeige: int | None, gegenstand: str | None) -> list:
    """Baut den kompletten "Bewertung <Disziplin>"-Block: Überschrift, ggf. Verleitungs-
    Hinweis, die beiden Bewertungsfelder (Suche/Anzeige) und die Positions-/Gesamtpunktzahl-
    Zeile (bei Behältnisstrecke mit den Positions-Kästchen 1..N statt einer Freifläche)."""
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
        anzahl = _BEHAELTNIS_POSITIONEN[stufe]
        positionen = " ".join(f"[{i}]" for i in range(1, anzahl + 1))
        links = Paragraph(
            f"<b>Position Gegenstand im Behältnis-Nr.:</b><br/>{positionen}<br/>"
            f"Gegenstand: ..................... Kammer-Nr.: .......",
            _TEXT,
        )
    else:
        links = Paragraph(
            "<b>Position Gegenstand:</b> (Freifläche oben zum Einzeichnen)<br/>"
            f"Zu suchender Gegenstand: {_p_wert(gegenstand) or '.....................'}",
            _TEXT,
        )
    rechts = Table(
        [[Paragraph(f"<b>Gesamtpunktzahl<br/>{gesamt_label}</b>", _TEXT), Paragraph(_p_wert(gesamt), _TEXT_FETT)]],
        colWidths=[45 * mm, 25 * mm],
    )
    rechts.setStyle(TableStyle([("GRID", (1, 0), (1, 0), 0.8, colors.black), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))

    fuss = Table([[links, rechts]], colWidths=[100 * mm, 70 * mm])
    fuss.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3 * mm)]))
    elemente.append(fuss)
    elemente.append(Spacer(1, 2 * mm))
    elemente.append(_wertungsnoten_tabelle_ed())

    return elemente


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
        suche = ergebnis[s_spalte] if ergebnis else None
        anzeige = ergebnis[a_spalte] if ergebnis else None
        einzelpunkte[disziplin] = (suche, anzeige)
        # Zu dieser Disziplin gehört nur der Gegenstand, der ihr auch tatsächlich
        # zugeordnet ist (siehe gegenstand_fuer_disziplin) - gilt einheitlich für ED und DK.
        gegenstand = gegenstand_fuer_disziplin(t, disziplin)
        story.append(KeepTogether(_bewertungsabschnitt(disziplin, t["stufe"], suche, anzeige, gegenstand)))

    if t["art"] == "DK":
        story.append(Spacer(1, 3 * mm))
        vollstaendig = all(einzelpunkte[d][0] is not None and einzelpunkte[d][1] is not None for d in ALLE_DISZIPLINEN)
        gesamt_zeile = ["Pkt. Trümmer", "Pkt. Fläche", "Pkt. Behältnis", "GESAMT"]
        werte_zeile = [
            _wert(sum(einzelpunkte[d]) if None not in einzelpunkte[d] else None) for d in ALLE_DISZIPLINEN
        ]
        if vollstaendig:
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
        story.append(gesamt_tabelle)
        story.append(Spacer(1, 2 * mm))
        story.append(_wertungsnoten_tabelle_dk())

    story.append(Spacer(1, 4 * mm))
    verein = veranstaltung["verein"] if veranstaltung else ""
    datum = veranstaltung["datum"] if veranstaltung else ""
    story.append(Paragraph(f"austragender Verein: {_p_wert(verein)} &nbsp;&nbsp;&nbsp; Datum: {_p_wert(datum)}", _TEXT))

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
    teilnehmer = list_teilnehmer(conn)
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

def erstelle_ergebnisliste_pdf(conn: sqlite3.Connection, pfad: str) -> None:
    """Gerankte Ergebnisliste je Leistungsklasse (Platzierung, Startnummer, Name,
    Gesamtpunkte, Wertnote) - "nicht Bestanden"-Teilnehmer erscheinen ohne Platzzahl,
    zählen aber weiterhin bei "von X Startern" mit (siehe shs_core.berechne_rangliste)."""
    veranstaltung = get_veranstaltung(conn)
    fertig, ausstehend = berechne_auswertung(conn)
    startnummer_je_id = {str(t["id"]): t["startnummer"] for t in list_teilnehmer(conn)}

    story: list = []
    titel = "Ergebnisliste"
    if veranstaltung:
        titel += f" – {veranstaltung['verein']} ({veranstaltung['datum']})"
    story.append(Paragraph(titel, _TITEL))
    story.append(Spacer(1, 2 * mm))

    leistungsklassen = sorted({t.leistungsklasse for t in fertig} | {leistungsklasse_label(t) for t in ausstehend})
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
            daten.append([platz, _wert(startnummer_je_id.get(t.id)), t.name, str(t.gesamtpunkte), f"{t.wertnote.notentext} ({t.wertnote.abkuerzung})"])
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
    datum = _p_wert(veranstaltung["datum"]) if veranstaltung else ""

    fertig, _ausstehend = berechne_auswertung(conn)
    fertig_je_id = {erg.id: erg for erg in fertig}
    ergebnis_je_id = {str(r["teilnehmer_id"]): dict(r) for r in conn.execute("SELECT * FROM ergebnisse").fetchall()}
    alle_teilnehmer = list_teilnehmer(conn)

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

        if erg is not None:
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
                Paragraph(gesamt_text, _ETIKETT_FELD),
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
    teilnehmer = list_teilnehmer(conn)

    story: list = []
    titel = "Ergebnisliste – Formular zum Ausfüllen"
    if veranstaltung:
        titel += f" – {veranstaltung['verein']} ({veranstaltung['datum']})"
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
        titel += f" – {veranstaltung['verein']} ({veranstaltung['datum']})"
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
            # Abgelaufen = Datum liegt vor dem Prüfungstag; beide Werte im Format
            # JJJJ-MM-TT (siehe db.py) sortieren als String bereits korrekt chronologisch,
            # ein echtes Datums-Parsing ist dafür nicht nötig. Kein Datum hinterlegt gilt
            # ebenfalls als hervorhebenswert (unbekannt = ungeprüft).
            abgelaufen_oder_leer = (
                not impfung_iso or (pruefungsdatum and impfung_iso.strip() < pruefungsdatum.strip())
            )
            impfung_stil = _UEBERSICHT_ZELLE_ROT if abgelaufen_oder_leer else _UEBERSICHT_ZELLE
            daten.append([
                Paragraph(_p_wert(t["nachname"]), _UEBERSICHT_ZELLE),
                Paragraph(_p_wert(t["vorname"]), _UEBERSICHT_ZELLE),
                Paragraph(_p_wert(t["verein"]), _UEBERSICHT_ZELLE),
                Paragraph(_p_wert(t["rufname_hund"]), _UEBERSICHT_ZELLE),
                Paragraph(_p_wert(t["chip_nr"]), _UEBERSICHT_ZELLE),
                Paragraph(leistungsklasse_label(t), _UEBERSICHT_ZELLE),
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
        list_teilnehmer(conn), key=lambda t: (t["startnummer"] is None, t["startnummer"])
    )

    story: list = []
    titel = "Chipnummernliste"
    if veranstaltung:
        titel += f" – {veranstaltung['verein']} ({veranstaltung['datum']})"
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
    Richter."""
    veranstaltung = get_veranstaltung(conn)
    teilnehmer = list_teilnehmer(conn)

    story: list = []
    titel = "Richter-Bedarf"
    if veranstaltung:
        titel += f" – {veranstaltung['verein']} ({veranstaltung['datum']})"
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
    daten = [["Uhrzeit", "Art / LK / Disziplin", "Start-Nr.", "Name", "Hund", "Verein"]]
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
                "", "", "", "",
            ])
            stil.append(("SPAN", (1, i), (5, i)))
        elif zeile["teilnehmer"] is None:
            # Bereits angelegter Prüfungsblock, für den (noch) kein passender Teilnehmer
            # gemeldet ist - erscheint trotzdem als Zeile, statt spurlos zu fehlen.
            daten.append([
                Paragraph(zeit_text, _ZEITPLAN_ZEIT),
                Paragraph(art_text, _ZEITPLAN_ZEILE),
                Paragraph("(noch keine Teilnehmer gemeldet)", _ZEITPLAN_PAUSE_TEXT),
                "", "", "",
            ])
            stil.append(("SPAN", (2, i), (5, i)))
        else:
            t = zeile["teilnehmer"]
            daten.append([
                Paragraph(zeit_text, _ZEITPLAN_ZEIT),
                Paragraph(art_text, _ZEITPLAN_ZEILE),
                Paragraph(_p_wert(t["startnummer"]), _ZEITPLAN_ZEILE),
                Paragraph(f"{_p_wert(t['nachname'])}, {_p_wert(t['vorname'])}", _ZEITPLAN_ZEILE),
                Paragraph(_p_wert(t["rufname_hund"]), _ZEITPLAN_ZEILE),
                Paragraph(_p_wert(t["verein"]), _ZEITPLAN_ZEILE),
            ])
        stil.append(("BACKGROUND", (0, i), (-1, i), _zeitplan_zeile_farbe(zeile)))

    tabelle = Table(daten, colWidths=[30 * mm, 48 * mm, 18 * mm, 42 * mm, 28 * mm, 34 * mm], repeatRows=1)
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
            titel += f" – {veranstaltung['verein']} ({veranstaltung['datum']})"
        story.append(Paragraph(titel, _TITEL))
        story.append(Paragraph("Es sind noch keine Richter/Zeitplan-Einträge angelegt.", _TEXT))
    else:
        for i, plan in enumerate(plaene):
            if i > 0:
                story.append(PageBreak())
            titel = f"Zeitplan – {plan['richter']}"
            if veranstaltung:
                titel += f" ({veranstaltung['verein']}, {veranstaltung['datum']})"
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
