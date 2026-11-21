"""Darstellung der Desktop-Oberfläche: Qt-Stylesheet, Designs (Schiefer/Dunkel/Hoher
Kontrast, Erscheinungsbild „Schiefer und Signal“ seit 21.11.2026, siehe
berichte/Design-Richtung-2026-11.md), Schriftgröße in drei Stufen (seit dem UX-Test
03.11.2026), gespeicherte Auswahl (QSettings) und deren Anwendung. Die frühere
Akzentfarb-Wahl (Lohbraun/Blau/Grün/Violett) und das Design „Hell“ sind entfallen; der
Akzent gehört jetzt fest zum Design.

Aus app.py ausgelagert (Codex-Architekturprüfung 27.09.2026); rein interne Umstellung,
Aussehen und Verhalten sind unverändert. Die Abhängigkeiten laufen nur in eine Richtung:
app -> desktop_dialoge -> desktop_gemeinsam, app -> desktop_darstellung (jeweils -> db/
pdf_export); keines dieser Module importiert app.
"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QPointF, QSettings, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QImage,
    QPainter,
    QPalette,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
)



_QSS_TEMPLATE = """
/* Erscheinungsbild „Schiefer und Signal“ (Marco 21.11.2026): ruhige Grau-Grün-Flächen,
Schiefer als einziger Akzent, Signalfarben nur für „fehlt/ungespeichert“. Die
Platzhalter (Schlüsselname zwischen doppelten At-Zeichen) werden vor dem Anwenden per
str.replace() durch die Hexwerte des
gewählten Designs (_DESIGNS unten) ersetzt; str.format() geht hier nicht, da das
Stylesheet selbst voller literaler {}-Blockklammern ist. Standard ist "schiefer". RAND ist
der Rand von Bedienelementen (mindestens 3:1), TRENNER die ruhigere Linie zwischen
Tabellenzellen und um Bereiche. Global über QApplication.setStyleSheet() gesetzt
(siehe _darstellung_anwenden(), aufgerufen aus main() in app.py) - HauptFenster &
Dialoge setzen zusätzlich per ResponsiveSchriftMixin
eine eigene, nähere QHeaderView::section-/QLabel-Regel NUR für font-size bei
Größenänderung; das überschreibt hier absichtlich nichts anderes, da beide Regelsätze
unterschiedliche Eigenschaften des Selektors setzen. */

QMainWindow, QDialog {
    background: @@HINTERGRUND@@;
}
QWidget {
    color: @@TEXT@@;
}
QLabel {
    color: @@TEXT@@;
}

/* Reiter (Teilnehmer/Zeitplan/.../Datensicherung) */
QTabWidget::pane {
    border: 1px solid @@TRENNER@@;
    background: @@HINTERGRUND@@;
    top: -1px;
}
/* Reiter durchsichtig: sonst übermalen sie die obere Rahmenlinie des Inhaltsbereichs
(top: -1px), und die Linie erscheint nur in den Lücken (Marco, 16.10.2026). */
QTabBar::tab {
    background: transparent;
    color: @@TEXT_GEDAEMPFT@@;
    padding: 8px 16px;
    border: none;
    border-bottom: 3px solid transparent;
    margin-right: 2px;
    font-weight: 600;
}
QTabBar::tab:selected {
    color: @@TEXT_STARK@@;
    font-weight: 600;
    border-bottom: 3px solid @@AKZENT@@;
}
QTabBar::tab:hover:!selected {
    color: @@TEXT_STARK@@;
}

/* Schaltflächen: neutral/sekundär als Standard; die jeweilige Haupt-Aktion eines
Reiters/Dialogs trägt objectName "primaerButton" (siehe z.B. TeilnehmerTab) und wird
in der Akzentfarbe hervorgehoben - ebenso automatisch jeder Dialog-Default-Button (die "OK"-Schaltfläche
einer QDialogButtonBox, über die Qt-eigene :default-Pseudoklasse, ohne dass jeder
Dialog einzeln angepasst werden muss). */
QPushButton {
    background: @@FLAECHE@@;
    color: @@TEXT_BUTTON@@;
    border: 1px solid @@RAND@@;
    border-radius: 4px;
    padding: 6px 14px;
}
QPushButton:hover {
    background: @@FLAECHE_HOVER@@;
}
QPushButton:pressed {
    background: @@FLAECHE_PRESSED@@;
}
QPushButton:disabled {
    color: @@TEXT_DISABLED@@;
    background: @@FLAECHE_DISABLED@@;
    border-color: @@RAND_DISABLED@@;
}
QPushButton#primaerButton, QPushButton:default:enabled {
    background: @@AKZENT@@;
    color: @@AKZENT_TEXT@@;
    border: 1px solid @@AKZENT@@;
    font-weight: 600;
}
QPushButton#primaerButton:hover, QPushButton:default:enabled:hover {
    background: @@AKZENT_HOVER@@;
    border-color: @@AKZENT_HOVER@@;
}
QPushButton#primaerButton:pressed, QPushButton:default:enabled:pressed {
    background: @@AKZENT_PRESSED@@;
    border-color: @@AKZENT_PRESSED@@;
}

/* Eingabefelder */
QLineEdit, QComboBox, QSpinBox, QDateEdit {
    background: @@FLAECHE@@;
    border: 1px solid @@RAND@@;
    border-radius: 4px;
    padding: 4px 8px;
    color: @@TEXT@@;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {
    border: 1px solid @@LINK@@;
    background: @@HINTERGRUND@@;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
    color: @@TEXT_DISABLED@@;
    background: @@FLAECHE_DISABLED@@;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
/* Ohne eigenes Bild zeichnet Qt bei gestaltetem Rahmen keinen Pfeil: Auswahlfelder sahen aus
wie Textfelder und niemand erkannte, dass sie sich aufklappen lassen (Marco 12.11.2026). */
QComboBox::down-arrow {
    image: url("@@PFEIL_RUNTER@@");
    width: 10px;
    height: 10px;
}
QComboBox::down-arrow:disabled {
    image: url("@@PFEIL_RUNTER_AUS@@");
}
/* Pfeilknöpfe der Zahlenfelder (Marco 01.11.2026, Erscheinungsbild „Beagle“): Sobald das
Feld selbst einen Rahmen aus dem Stylesheet hat, zeichnet Qt die Knöpfe nur noch als flache
Kästchen ohne Pfeil. Deshalb eigene Knöpfe und Pfeile als Bild (_pfeile_bereitstellen()). */
QSpinBox, QDateEdit {
    padding-right: 22px;
}
QSpinBox::up-button, QDateEdit::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    border: none;
    border-left: 1px solid @@RAND@@;
    border-top-right-radius: 4px;
    background: @@FLAECHE@@;
}
QSpinBox::down-button, QDateEdit::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    border: none;
    border-left: 1px solid @@RAND@@;
    border-bottom-right-radius: 4px;
    background: @@FLAECHE@@;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDateEdit::up-button:hover, QDateEdit::down-button:hover {
    background: @@FLAECHE_HOVER@@;
}
QSpinBox::up-button:pressed, QSpinBox::down-button:pressed,
QDateEdit::up-button:pressed, QDateEdit::down-button:pressed {
    background: @@FLAECHE_PRESSED@@;
}
QSpinBox::up-arrow, QDateEdit::up-arrow {
    image: url("@@PFEIL_HOCH@@");
    width: 10px;
    height: 10px;
}
QSpinBox::down-arrow, QDateEdit::down-arrow {
    image: url("@@PFEIL_RUNTER@@");
    width: 10px;
    height: 10px;
}
QSpinBox::up-arrow:disabled, QSpinBox::up-arrow:off,
QDateEdit::up-arrow:disabled, QDateEdit::up-arrow:off {
    image: url("@@PFEIL_HOCH_AUS@@");
}
QSpinBox::down-arrow:disabled, QSpinBox::down-arrow:off,
QDateEdit::down-arrow:disabled, QDateEdit::down-arrow:off {
    image: url("@@PFEIL_RUNTER_AUS@@");
}
QCheckBox {
    color: @@TEXT@@;
    spacing: 6px;
}

/* Tabellen (Teilnehmer, Ergebniserfassung, Auswertung, Zeitplan, Terminübersicht) */
QTableWidget {
    background: @@KARTE@@;
    alternate-background-color: @@TABELLE_ALT@@;
    gridline-color: @@TRENNER@@;
    border: 1px solid @@RAND@@;
    border-radius: 4px;
    selection-background-color: @@AUSWAHL@@;
    selection-color: @@TEXT@@;
}
QTableWidget::item {
    padding: 4px 6px;
}
QTableWidget::item:selected {
    background: @@AUSWAHL@@;
    color: @@TEXT@@;
}
QHeaderView::section {
    background: @@TABELLE_ALT@@;
    color: @@TEXT_HEADER@@;
    padding: 6px;
    border: none;
    border-bottom: 1px solid @@RAND@@;
    font-weight: 600;
}
QTableCornerButton::section {
    background: @@TABELLE_ALT@@;
    border: none;
    border-bottom: 1px solid @@RAND@@;
}

QScrollBar:vertical, QScrollBar:horizontal {
    background: @@HINTERGRUND@@;
    border: none;
}
QScrollBar::handle {
    background: @@SCROLL@@;
    border-radius: 5px;
}
QScrollBar::handle:hover {
    background: @@SCROLL_HOVER@@;
}

/* Kopfbalken mit Beagle und Termin-Angaben (desktop_gemeinsam.KopfBalken), Menüleiste im
selben Ton, Gruppen als helle Karten und der kurze Hinweis mit Hilfe-Symbol
(desktop_gemeinsam.kurzer_hinweis) - Marco 01.11.2026, seit 21.11.2026 in Schiefer. Rand und
Hover im Kopf sind feste Farben statt durchscheinender, damit „Hoher Kontrast“ einen
klaren weißen Rand bekommt. */
QMenuBar {
    background: @@KOPF@@;
    color: @@KOPF_TEXT@@;
}
QMenuBar::item {
    background: transparent;
    color: @@KOPF_TEXT@@;
    padding: 4px 10px;
}
QMenuBar::item:selected {
    background: @@KOPF_HOVER@@;
}
#kopfBalken {
    background: @@KOPF@@;
}
#kopfBalken QLabel {
    color: @@KOPF_TEXT@@;
    background: transparent;
}
#kopfBalken QLabel#kopfUnterzeile {
    color: @@KOPF_TEXT2@@;
}
#kopfBalken QPushButton {
    background: transparent;
    color: @@KOPF_TEXT@@;
    border: 1px solid @@KOPF_RAND@@;
    border-radius: 4px;
    padding: 6px 12px;
}
#kopfBalken QPushButton:hover {
    background: @@KOPF_HOVER@@;
}
#kopfBalken QPushButton:pressed {
    background: @@KOPF_HOVER@@;
    border-color: @@KOPF_TEXT2@@;
}
/* Gesperrt (z. B. „Anderen Termin öffnen…“ während der Demo): gestrichelter Rand, damit es
auch in „Hoher Kontrast“ (Unterzeile ebenfalls weiß) erkennbar bleibt. */
#kopfBalken QPushButton:disabled {
    color: @@KOPF_TEXT2@@;
    border: 1px dashed @@KOPF_RAND@@;
}
QGroupBox {
    background: @@KARTE@@;
    border: 1px solid @@TRENNER@@;
    border-radius: 6px;
    margin-top: 18px;
    padding: 12px 8px 8px 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 4px;
    color: @@GRUPPE_TITEL@@;
}
QLabel#kurzHinweis {
    color: @@TEXT_GEDAEMPFT@@;
}
"""

_DESIGN_DEFAULT = "schiefer"

# Gut sichtbare Checkboxen in allen Designs (seit 21.11.2026 gibt es kein Design mit
# nativem Haken mehr; der Schalter "eigene_haken" bleibt für ein späteres Design). Ohne diese
# Regel zeichnet Fusion (dunkles Design) den Rahmen dunkler als den Hintergrund und die Box
# verschwindet. Eine eigene ::indicator-Regel schaltet allerdings das native Häkchen ab -
# deshalb das Häkchen als Bild in der Schriftfarbe auf dem Akzent (@@HAKEN@@, erzeugt von
# _haken_bild_bereitstellen()).
_QSS_CHECKBOX_ZUSATZ = """
QCheckBox::indicator, QAbstractItemView::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid @@TEXT_GEDAEMPFT@@;
    border-radius: 3px;
    background: @@FLAECHE@@;
}
QCheckBox::indicator:hover, QAbstractItemView::indicator:hover {
    border-color: @@AKZENT@@;
}
QCheckBox::indicator:checked, QAbstractItemView::indicator:checked {
    background: @@AKZENT@@;
    border-color: @@AKZENT@@;
    image: url("@@HAKEN@@");
}
QCheckBox::indicator:disabled, QAbstractItemView::indicator:disabled {
    background: @@FLAECHE_DISABLED@@;
    border-color: @@RAND_DISABLED@@;
}
QCheckBox::indicator:checked:disabled, QAbstractItemView::indicator:checked:disabled {
    background: @@TEXT_DISABLED@@;
    border-color: @@TEXT_DISABLED@@;
    image: url("@@HAKEN_AUS_BILD@@");
}
"""


def _haken_pfad() -> str:
    """Ablageort des weißen Häkchen-Bildes: der benutzereigene Programmordner (derselbe wie
    termine_ordner().parent, dort liegt auch das Absturzprotokoll) - nicht der unter
    Linux gemeinsam genutzte Temp-Ordner. Vorwärtsschrägstriche, wie QSS-url() sie
    erwartet. Häkchen in anderen Farben (dunkles Design) und die Pfeile liegen daneben."""
    return os.path.join(os.path.expanduser("~"), "SHS-Pruefungsprogramm", "haken.png").replace("\\", "/")


def _haken_pfad_fuer(farbe: str) -> str:
    """Häkchen in der Schriftfarbe auf dem Akzent: weiß wie bisher unter haken.png, andere
    Farben als haken_RRGGBB.png im selben Ordner."""
    if farbe.upper() == "#FFFFFF":
        return _haken_pfad()
    ordner = os.path.dirname(_haken_pfad())
    return f"{ordner}/haken_{farbe.lstrip('#').upper()}.png"


def _qss_url(pfad: str) -> str:
    """Pfad für url("...") im Stylesheet: Umlaute, Apostroph und Leerzeichen sind in
    Anführungszeichen unkritisch, nur Backslash und Anführungszeichen selbst werden
    maskiert. Ohne Anführungszeichen verwirft Qt sonst das ganze Stylesheet."""
    return pfad.replace("\\", "\\\\").replace('"', '\\"')


# In diesem Programmlauf schon geschriebene Häkchen-Dateien. Sie werden je Lauf einmal neu
# erzeugt, statt eine schon vorhandene Datei ungeprüft zu übernehmen.
_haken_geschrieben: set[str] = set()


def _bild_speichern(bild: QImage, pfad: str) -> bool:
    """Speichert ein PNG erst in eine Temp-Datei und setzt es dann per os.replace an seinen
    Platz; True bei Erfolg. Scheitert das (Ordner nicht beschreibbar), bleibt keine
    Zwischendatei liegen. Gemeinsam für Häkchen, Pfeile und desktop_gemeinsam.symbol_png."""
    try:
        os.makedirs(os.path.dirname(pfad), exist_ok=True)
    except OSError:
        return False
    zwischen = f"{pfad}.{os.getpid()}.tmp"
    try:
        if bild.save(zwischen, "PNG"):
            os.replace(zwischen, pfad)
            return True
    except OSError:
        pass
    finally:
        if os.path.exists(zwischen):
            try:
                os.remove(zwischen)
            except OSError:
                pass
    return False


def _strich_bild(punkte: list[tuple[float, float]], farbe: str, groesse: int, breite: float) -> QImage:
    """Zeichnet einen abgerundeten Linienzug (Häkchen, Pfeil) auf durchsichtigem Grund."""
    bild = QImage(groesse, groesse, QImage.Format_ARGB32)
    bild.fill(Qt.transparent)
    maler = QPainter(bild)
    maler.setRenderHint(QPainter.Antialiasing)
    stift = QPen(QColor(farbe), breite)
    stift.setCapStyle(Qt.RoundCap)
    stift.setJoinStyle(Qt.RoundJoin)
    maler.setPen(stift)
    maler.drawPolyline([QPointF(x, y) for x, y in punkte])
    maler.end()
    return bild


def _haken_bild_bereitstellen(farbe: str = "#FFFFFF") -> None:
    """Zeichnet das Häkchen für _QSS_CHECKBOX_ZUSATZ in der Schriftfarbe auf dem Akzent
    einmal je Programmlauf neu als PNG (erst in eine Temp-Datei, dann per os.replace an
    seinen Platz). Scheitert das (Ordner nicht beschreibbar), bleibt die angehakte Box nur
    akzentfarbig gefüllt - kein Grund, den Programmstart oder den Designwechsel abzubrechen."""
    pfad = _haken_pfad_fuer(farbe)
    if pfad in _haken_geschrieben:
        return
    bild = _strich_bild([(7, 17), (13, 23), (25, 9)], farbe, 32, 4)
    if _bild_speichern(bild, pfad):
        _haken_geschrieben.add(pfad)


# Pfeile der Zahlenfelder (QSpinBox), je Richtung und Farbe eine Datei neben dem Häkchen.
_PFEIL_PUNKTE = {
    "hoch": [(5, 13), (10, 8), (15, 13)],
    "runter": [(5, 8), (10, 13), (15, 8)],
}
# In diesem Programmlauf schon geschriebene Pfeil-Dateien (wie _haken_geschrieben).
_pfeile_geschrieben: set[str] = set()


def _pfeil_pfad(richtung: str, farbe: str) -> str:
    """Ablageort eines Pfeil-Bildes: derselbe Ordner wie das Häkchen (_haken_pfad)."""
    ordner = os.path.dirname(_haken_pfad())
    return f"{ordner}/pfeil_{richtung}_{farbe.lstrip('#').upper()}.png"


def _pfeil_farben(design: dict) -> dict[str, tuple[str, str]]:
    """Platzhalter -> Farbe der vier Pfeil-Bilder (aktiv und gesperrt)."""
    return {
        "PFEIL_HOCH": ("hoch", design["TEXT_BUTTON"]),
        "PFEIL_RUNTER": ("runter", design["TEXT_BUTTON"]),
        "PFEIL_HOCH_AUS": ("hoch", design["TEXT_DISABLED"]),
        "PFEIL_RUNTER_AUS": ("runter", design["TEXT_DISABLED"]),
    }


def _pfeile_bereitstellen(design: dict) -> None:
    """Zeichnet die Pfeile der Zahlenfelder für das Design einmal je Programmlauf (Marco
    01.11.2026). Scheitert das, zeigt das Feld nur leere Knöpfe - die Pfeiltasten der
    Tastatur und das Mausrad funktionieren weiter."""
    for richtung, farbe in _pfeil_farben(design).values():
        pfad = _pfeil_pfad(richtung, farbe)
        if pfad in _pfeile_geschrieben:
            continue
        # Doppelte Auflösung (20 px für 10 px im Stylesheet), damit es auch bei 150/200 %
        # Bildschirmskalierung scharf bleibt.
        bild = _strich_bild(_PFEIL_PUNKTE[richtung], farbe, 20, 2.4)
        if _bild_speichern(bild, pfad):
            _pfeile_geschrieben.add(pfad)


# Designs (Menü Ansicht -> Design). Die Großbuchstaben-Schlüssel füllen die gleichnamigen
# @@...@@-Platzhalter in _QSS_TEMPLATE; Standard ist "schiefer" (Marco 21.11.2026,
# Erscheinungsbild „Schiefer und Signal“; ersetzt „Beagle“, „Hell“ und die Akzentfarb-Wahl,
# siehe _ALTE_DESIGNS). Der Akzent gehört seitdem zum Design und ist in vier Aufgaben
# geteilt, weil eine Farbe im dunklen Design nicht alle erfüllt:
# - AKZENT (+ _HOVER/_PRESSED): Füllung von Hauptknopf, angehakter Box, Reiter-Linie;
#   AKZENT_TEXT ist Schrift, Häkchen und Symbol darauf; HAKEN_AUS das Häkchen einer
#   gesperrten, angehakten Box auf TEXT_DISABLED (mindestens 4,5:1, Marco 21.11.2026);
# - LINK: Links, Fokusrahmen der Eingabefelder und Punktezellen (QPalette.Link);
# - AUSWAHL: Hintergrund markierter Zeilen.
# RAND ist der Rand von Bedienelementen (mindestens 3:1 zu Fläche und Grund), TRENNER die
# ruhigere Linie zwischen Tabellenzellen, um Reiter-Inhalt und Gruppen. KOPF, KOPF_TEXT,
# KOPF_TEXT2 (Unterzeile), KOPF_RAND und KOPF_HOVER färben Menüleiste und Kopfbalken, KARTE
# Tabellen und Gruppen (QGroupBox), GRUPPE_TITEL deren Überschrift. "eigene_haken": True hängt
# _QSS_CHECKBOX_ZUSATZ an. Die Kleinbuchstaben-Farbschlüssel (ok, warnung, fehler,
# gedaempft, ungespeichert_bg, gesperrt_bg, zeile_bg) sind semantische Farben für Stellen, an
# denen der Code selbst färbt (Tabellenzellen, HTML-Labels) - abgerufen über _farbe(), das
# auch die Großbuchstaben-Schlüssel liefert (FLAECHE, RAND …, für die selbst gezeichneten
# Punktezellen der Ergebniserfassung); fehler und zeile_bg fließen außerdem in
# _design_palette() ein. ungespeichert_bg ist das Absperrband-Gelb, warnung das dunkle Signal
# für kleine Schrift. "anzeigename" ist der Menütext. "dunkel": True schaltet zusätzlich den
# Fusion-Stil ein und fordert das dunkle Farbschema an (siehe _darstellung_anwenden()).
# Jedes Design setzt seine eigene QPalette.
_DESIGNS: dict[str, dict] = {
    "schiefer": {
        "anzeigename": "Schiefer (Standard)",
        "dunkel": False,
        "eigene_haken": True,
        "HINTERGRUND": "#EEF0EC",  # Beton
        "FLAECHE": "#FFFFFF",
        "FLAECHE_HOVER": "#E4E8E5",
        "FLAECHE_PRESSED": "#D6DCD8",
        "FLAECHE_DISABLED": "#F4F5F3",
        "RAND": "#7A837E",
        "RAND_DISABLED": "#C9CFCB",
        "TRENNER": "#C9CFCB",
        "TEXT": "#1B2220",  # Tinte
        "TEXT_STARK": "#0F1513",
        "TEXT_BUTTON": "#1B2220",
        "TEXT_GEDAEMPFT": "#4F5853",
        "PLATZHALTER": "#69726D",
        "TEXT_HEADER": "#4F5853",
        "TEXT_DISABLED": "#A3AAA6",
        "TABELLE_ALT": "#F6F7F5",
        "SCROLL": "#B9C1BC",
        "SCROLL_HOVER": "#98A19C",
        "KOPF": "#2A3035",  # Schiefer
        "KOPF_TEXT": "#F1F3F2",
        "KOPF_TEXT2": "#B9C1BC",
        "KOPF_RAND": "#6E777C",
        "KOPF_HOVER": "#3B434A",
        "KARTE": "#FFFFFF",
        "GRUPPE_TITEL": "#2A3035",
        "AKZENT": "#2A3035",
        "AKZENT_HOVER": "#3B434A",
        "AKZENT_PRESSED": "#1B2024",
        "AKZENT_TEXT": "#FFFFFF",
        "HAKEN_AUS": "#1B2220",
        "LINK": "#2A3035",
        "AUSWAHL": "#DCE2E5",
        "ok": "#2A7A47",
        "warnung": "#B33A0A",  # Signal, dunkle Stufe für Schrift
        "fehler": "#B3261E",
        "gedaempft": "#6B746F",
        "ungespeichert_bg": "#FFD43B",  # Absperrband
        "gesperrt_bg": "#D6DCD8",
        "zeile_bg": "#FFFFFF",
    },
    "dunkel": {
        "anzeigename": "Dunkel",
        "dunkel": True,
        "eigene_haken": True,
        "HINTERGRUND": "#1A1F22",
        "FLAECHE": "#252B2F",
        "FLAECHE_HOVER": "#2F363B",
        "FLAECHE_PRESSED": "#394147",
        "FLAECHE_DISABLED": "#20262A",
        "RAND": "#7D888E",
        "RAND_DISABLED": "#343C41",
        "TRENNER": "#343C41",
        "TEXT": "#E8ECEA",
        "TEXT_STARK": "#FFFFFF",
        "TEXT_BUTTON": "#E1E6E3",
        "TEXT_GEDAEMPFT": "#A7B1AC",
        "PLATZHALTER": "#A7B1AC",
        "TEXT_HEADER": "#A7B1AC",
        "TEXT_DISABLED": "#5E676C",
        "TABELLE_ALT": "#20262A",
        "SCROLL": "#434C52",
        "SCROLL_HOVER": "#566067",
        "KOPF": "#111517",
        "KOPF_TEXT": "#E8ECEA",
        "KOPF_TEXT2": "#A7B1AC",
        "KOPF_RAND": "#4F585D",
        "KOPF_HOVER": "#2A3135",
        "KARTE": "#20262A",
        "GRUPPE_TITEL": "#DCE2DF",
        # Heller Schiefer mit dunkler Schrift: ein Akzent, der weiße Schrift trüge, wäre
        # auf dunklem Grund als Fokus und Link kaum zu sehen.
        "AKZENT": "#D7DDDA",
        "AKZENT_HOVER": "#C5CDC9",
        "AKZENT_PRESSED": "#B3BCB8",
        "AKZENT_TEXT": "#1A1F22",
        "HAKEN_AUS": "#FFFFFF",
        "LINK": "#C9D3CE",
        "AUSWAHL": "#34404A",
        "ok": "#6FCF97",
        "warnung": "#FF9A5C",
        "fehler": "#FF7B72",
        "gedaempft": "#87918C",
        "ungespeichert_bg": "#5C4A0E",
        "gesperrt_bg": "#111517",
        "zeile_bg": "#20262A",
    },
    "kontrast": {
        "anzeigename": "Hoher Kontrast",
        "dunkel": False,
        "eigene_haken": True,
        "HINTERGRUND": "#FFFFFF",
        "FLAECHE": "#FFFFFF",
        "FLAECHE_HOVER": "#E8E8E8",
        "FLAECHE_PRESSED": "#D0D0D0",
        "FLAECHE_DISABLED": "#F2F2F2",
        "RAND": "#1B1B1B",
        "RAND_DISABLED": "#9A9A9A",
        "TRENNER": "#1B1B1B",
        "TEXT": "#000000",
        "TEXT_STARK": "#000000",
        "TEXT_BUTTON": "#000000",
        "TEXT_GEDAEMPFT": "#333333",
        "PLATZHALTER": "#333333",  # UX-Test U14: heller als TEXT_GEDAEMPFT
        "TEXT_HEADER": "#000000",
        "TEXT_DISABLED": "#6E6E6E",
        "TABELLE_ALT": "#F2F2F2",
        "SCROLL": "#6E6E6E",
        "SCROLL_HOVER": "#3D3D3D",
        # Kopf ohne Zwischentöne: schwarz, Schrift und Rand weiß (keine Transparenz).
        "KOPF": "#000000",
        "KOPF_TEXT": "#FFFFFF",
        "KOPF_TEXT2": "#FFFFFF",
        "KOPF_RAND": "#FFFFFF",
        "KOPF_HOVER": "#333333",
        "KARTE": "#FFFFFF",
        "GRUPPE_TITEL": "#000000",
        "AKZENT": "#000000",
        "AKZENT_HOVER": "#333333",
        "AKZENT_PRESSED": "#1A1A1A",
        "AKZENT_TEXT": "#FFFFFF",
        "HAKEN_AUS": "#FFFFFF",
        "LINK": "#000000",
        "AUSWAHL": "#D9D9D9",
        "ok": "#0B6B2E",
        "warnung": "#8A4B00",
        "fehler": "#B00020",
        "gedaempft": "#4D4D4D",
        "ungespeichert_bg": "#FFD43B",
        "gesperrt_bg": "#C8C8C8",
        "zeile_bg": "#FFFFFF",
    },
}

# Zuletzt per _darstellung_anwenden() gesetztes Design; _farbe() liest es. Vorbelegt mit dem
# Standard, damit Tabs, die ohne main() erzeugt werden (GUI-Tests), dessen Farben bekommen.
_aktives_design = _DESIGN_DEFAULT


def _erzeuge_qss(design_name: str = _DESIGN_DEFAULT) -> str:
    """Setzt die Platzhalter des Designs in _QSS_TEMPLATE ein. Ein unbekannter Name fällt
    auf den Standard zurück."""
    design = _DESIGNS.get(design_name, _DESIGNS[_DESIGN_DEFAULT])
    text = _QSS_TEMPLATE
    if design.get("eigene_haken"):
        text += (_QSS_CHECKBOX_ZUSATZ
                 .replace("@@HAKEN@@", _qss_url(_haken_pfad_fuer(design["AKZENT_TEXT"])))
                 .replace("@@HAKEN_AUS_BILD@@", _qss_url(_haken_pfad_fuer(design["HAKEN_AUS"]))))
    for platzhalter, (richtung, farbe) in _pfeil_farben(design).items():
        text = text.replace(f"@@{platzhalter}@@", _qss_url(_pfeil_pfad(richtung, farbe)))
    for schluessel, wert in design.items():
        if schluessel.isupper():
            text = text.replace(f"@@{schluessel}@@", wert)
    return text


def _farbe(name: str) -> QColor:
    """Farbe des aktiven Designs - semantisch (ok/warnung/fehler/gedaempft/
    ungespeichert_bg/gesperrt_bg/zeile_bg) oder ein Stylesheet-Schlüssel (FLAECHE, RAND, …) - für
    Stellen, an denen der Code selbst färbt."""
    return QColor(_DESIGNS[_aktives_design][name])


_SETTINGS_ORG = "SHS-Pruefungsprogramm"
_SETTINGS_APP = "Desktop"
# Der Schlüssel heißt aus Verträglichkeit weiter "hintergrund"; das Menü heißt seit
# 21.11.2026 „Design“. Die frühere Akzentfarb-Wahl ("darstellung/theme") wird nicht mehr
# gelesen.
_SETTINGS_KEY_DESIGN = "darstellung/hintergrund"

# Gespeicherte Namen früherer Designs -> heutiger Name: „Warm / Sand“ (bis 01.11.2026),
# „Beagle“ und „Hell“ (bis 21.11.2026) gehen im Standard „Schiefer“ auf.
_ALTE_DESIGNS = {"sand": "schiefer", "beagle": "schiefer", "hell": "schiefer"}


def _gespeichertes_design_lesen() -> str:
    """Liest das zuletzt gewählte Design pro Windows-Benutzer (QSettings/Registry). Frühere
    Designs werden zum heutigen Standard (siehe _ALTE_DESIGNS)."""
    einstellungen = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
    wert = einstellungen.value(_SETTINGS_KEY_DESIGN, _DESIGN_DEFAULT)
    if not isinstance(wert, str):  # z. B. eine von Hand verstellte Registry
        return _DESIGN_DEFAULT
    wert = _ALTE_DESIGNS.get(wert, wert)
    return wert if wert in _DESIGNS else _DESIGN_DEFAULT


def _design_speichern(design_name: str) -> None:
    QSettings(_SETTINGS_ORG, _SETTINGS_APP).setValue(_SETTINGS_KEY_DESIGN, design_name)


# UX-Test 03.11.2026, X2: Schriftgröße in drei Stufen (Menü „Ansicht → Schriftgröße“). Der
# Faktor wirkt auf die Anwendungsschrift und auf die an die Fensterbreite angepassten
# Beschriftungen (desktop_gemeinsam._responsive_schriftgroesse).
_SCHRIFTSTUFEN = {
    "normal": {"anzeigename": "Normal", "faktor": 1.0},
    "gross": {"anzeigename": "Groß", "faktor": 1.15},
    "sehr_gross": {"anzeigename": "Sehr groß", "faktor": 1.3},
}
_SCHRIFT_DEFAULT = "normal"
_SETTINGS_KEY_SCHRIFT = "darstellung/schrift"
_schrift_faktor = 1.0
_basis_schrift_pt: float | None = None  # Anwendungsschrift beim ersten Anwenden (Faktor 1)


# Schrift der Oberfläche (Marco 21.11.2026, „Schiefer und Signal“): mitgeliefert im Ordner
# schrift/ (siehe schrift/README.md), im PyInstaller-Bundle unter sys._MEIPASS/schrift.
PROGRAMMSCHRIFT = "Atkinson Hyperlegible Next"
_PROGRAMMSCHRIFT_DATEIEN = (
    "AtkinsonHyperlegibleNext-Regular.ttf",
    "AtkinsonHyperlegibleNext-Italic.ttf",
    "AtkinsonHyperlegibleNext-SemiBold.ttf",
    "AtkinsonHyperlegibleNext-Bold.ttf",
)
# Ergebnis des Ladens je Programmlauf: None = noch nicht versucht, sonst ob es geklappt hat.
_programmschrift_geladen: bool | None = None


def programmschrift_pfad(datei: str) -> str:
    """Pfad einer Schriftdatei - im Bundle unter sys._MEIPASS, sonst neben diesem Modul
    (wie desktop_gemeinsam.bundle_pfad, das dieses Modul nicht importieren darf)."""
    basis = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(basis, "schrift", datei)


def _programmschrift_laden() -> bool:
    """Meldet die Schriftdateien einmal je Programmlauf bei Qt an. False, wenn eine Datei fehlt
    oder Qt die Familie nicht erkennt - dann bleibt die Systemschrift (kein Abbruch)."""
    global _programmschrift_geladen
    if _programmschrift_geladen is None:
        familien: set[str] = set()
        alle_da = True
        for datei in _PROGRAMMSCHRIFT_DATEIEN:
            kennung = QFontDatabase.addApplicationFont(programmschrift_pfad(datei))
            if kennung < 0:
                alle_da = False
                continue
            familien.update(QFontDatabase.applicationFontFamilies(kennung))
        _programmschrift_geladen = alle_da and PROGRAMMSCHRIFT in familien
    return _programmschrift_geladen


def _programmschrift_anwenden(app: QApplication) -> None:
    """Setzt die Programmschrift als Anwendungsschrift (Größe bleibt)."""
    if not _programmschrift_laden():
        return
    schrift = QFont(app.font())
    schrift.setFamilies([PROGRAMMSCHRIFT])
    app.setFont(schrift)


def ziffern_gleich_breit(schrift: QFont) -> QFont:
    """Kopie der Schrift mit Ziffern gleicher Breite (OpenType tnum, ab Qt 6.7), damit Punkte
    in Tabellenspalten untereinander stehen. Bewusst nicht für die ganze Anwendung: dort
    wirkten Datum und Versionsnummer damit gesperrt. Ohne die Qt-Funktion bleibt die Schrift
    unverändert."""
    kopie = QFont(schrift)
    if hasattr(QFont, "setFeature") and hasattr(QFont, "Tag"):
        kopie.setFeature(QFont.Tag("tnum"), 1)
    return kopie


def schrift_faktor() -> float:
    """Faktor der gewählten Schriftgröße (1,0 / 1,15 / 1,3), gesetzt von _darstellung_anwenden."""
    return _schrift_faktor


def _gespeicherte_schriftstufe_lesen() -> str:
    wert = QSettings(_SETTINGS_ORG, _SETTINGS_APP).value(_SETTINGS_KEY_SCHRIFT, _SCHRIFT_DEFAULT)
    return wert if isinstance(wert, str) and wert in _SCHRIFTSTUFEN else _SCHRIFT_DEFAULT


def _schriftstufe_speichern(stufe: str) -> None:
    QSettings(_SETTINGS_ORG, _SETTINGS_APP).setValue(_SETTINGS_KEY_SCHRIFT, stufe)


# Stil, mit dem die Anwendung gestartet ist - beim ersten _darstellung_anwenden()
# gemerkt, damit helle Designs den nativen Stil des Systems behalten (nur die Palette ist fest).
_ursprung_stil: str | None = None
# Zuletzt per setStyle() gesetzter Stil - selbst mitgeführt, weil app.style() bei aktivem
# Stylesheet den internen Stylesheet-Stil (ohne Namen) liefert.
_aktueller_stil: str | None = None


def _design_palette(design: dict) -> QPalette:
    """QPalette passend zum Design - färbt, was das Stylesheet nicht erreicht
    (Scrollbereiche, Listen, Textfelder, Menüs, Tooltips, Kalender-Popups)."""
    palette = QPalette()
    rollen = {
        QPalette.Window: design["HINTERGRUND"],
        QPalette.WindowText: design["TEXT"],
        QPalette.Base: design["zeile_bg"],
        QPalette.AlternateBase: design["TABELLE_ALT"],
        QPalette.Text: design["TEXT"],
        QPalette.Button: design["FLAECHE"],
        QPalette.ButtonText: design["TEXT_BUTTON"],
        QPalette.BrightText: design["fehler"],
        QPalette.ToolTipBase: design["FLAECHE"],
        QPalette.ToolTipText: design["TEXT"],
        QPalette.PlaceholderText: design["PLATZHALTER"],
        QPalette.Highlight: design["AUSWAHL"],
        QPalette.HighlightedText: design["TEXT"],
        QPalette.Link: design["LINK"],
        QPalette.Light: design["FLAECHE_HOVER"],
        QPalette.Midlight: design["FLAECHE"],
        QPalette.Mid: design["RAND"],
        QPalette.Dark: design["RAND"],
        QPalette.Shadow: "#000000",
    }
    # Accent gibt es erst ab Qt 6.6; ohne eigene Farbe käme sie aus der Systempalette.
    if hasattr(QPalette, "Accent"):
        rollen[QPalette.Accent] = design["AKZENT"]
    for rolle, wert in rollen.items():
        palette.setColor(rolle, QColor(wert))
    for rolle in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, rolle, QColor(design["TEXT_DISABLED"]))
    return palette


def _darstellung_anwenden(app: QApplication) -> None:
    """Wendet gespeichertes Design und Schriftgröße auf die ganze Anwendung an."""
    global _aktives_design, _ursprung_stil, _aktueller_stil, _schrift_faktor, _basis_schrift_pt
    if _basis_schrift_pt is None:
        _basis_schrift_pt = app.font().pointSizeF()
        _programmschrift_anwenden(app)
    _schrift_faktor = _SCHRIFTSTUFEN[_gespeicherte_schriftstufe_lesen()]["faktor"]
    schrift = app.font()
    ziel_pt = round(_basis_schrift_pt * _schrift_faktor, 1)
    if _basis_schrift_pt > 0 and schrift.pointSizeF() != ziel_pt:
        schrift.setPointSizeF(ziel_pt)
        app.setFont(schrift)
    design_name = _gespeichertes_design_lesen()
    design = _DESIGNS[design_name]

    if _ursprung_stil is None:
        # Stylesheet kurz entfernen, damit style() den echten Basis-Stil liefert.
        stylesheet = app.styleSheet()
        app.setStyleSheet("")
        _ursprung_stil = app.style().name()
        _aktueller_stil = _ursprung_stil
        app.setStyleSheet(stylesheet)

    # Native Windows-Stile ignorieren eine dunkle Palette bei Menüs/Popups teilweise,
    # Fusion zeichnet alles aus der Palette - deshalb nur für dunkle Designs.
    ziel_stil = "fusion" if design["dunkel"] else _ursprung_stil
    if ziel_stil and ziel_stil.lower() != (_aktueller_stil or "").lower():
        app.setStyle(ziel_stil)
        _aktueller_stil = ziel_stil

    # Desktop-Prüfung 14.10.2026 (Teil 9 Nr. 1, Marcos Entscheidung): auch helle Designs
    # bekommen eine feste helle Palette. Vorher folgte das damalige "hell" dem
    # System-Farbschema; bei "Apps:
    # dunkel" (Windows 11, macOS) wurden Scrollbereiche, Listen, Hilfetext und Menüs dunkel,
    # die Stylesheet-Schrift blieb aber fast schwarz - unlesbar. Das Farbschema wird
    # zusätzlich passend zum Design angefordert (ab Qt 6.8), damit native Stile wie
    # windows11 nicht doch dunkel zeichnen.
    schema = getattr(Qt, "ColorScheme", None)
    hinweise = app.styleHints()
    if schema is not None and hasattr(hinweise, "setColorScheme"):
        hinweise.setColorScheme(schema.Dark if design["dunkel"] else schema.Light)
    app.setPalette(_design_palette(design))
    if design.get("eigene_haken"):
        _haken_bild_bereitstellen(design["AKZENT_TEXT"])
        _haken_bild_bereitstellen(design["HAKEN_AUS"])
    _pfeile_bereitstellen(design)
    _aktives_design = design_name
    app.setStyleSheet(_erzeuge_qss(design_name))
