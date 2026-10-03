"""Darstellung der Desktop-Oberfläche: Qt-Stylesheet, Akzentfarben (Themes),
Hintergrund-Designs (hell/dunkel), gespeicherte Auswahl (QSettings) und deren Anwendung.

Aus app.py ausgelagert (Codex-Architekturprüfung 27.09.2026); rein interne Umstellung,
Aussehen und Verhalten sind unverändert. Die Abhängigkeiten laufen nur in eine Richtung:
app -> desktop_dialoge -> desktop_gemeinsam, app -> desktop_darstellung (jeweils -> db/
pdf_export); keines dieser Module importiert app.
"""

from __future__ import annotations

import os
import tempfile

from PySide6.QtCore import QPointF, QSettings, Qt
from PySide6.QtGui import (
    QColor,
    QImage,
    QPainter,
    QPalette,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
)



_QSS_TEMPLATE = """
/* "Modern/Minimal"-Erscheinungsbild (siehe Design-Mockup-Vergleich): kühles Grau-Blau,
ein einzelner Akzentton (je gewähltem Theme, siehe _THEMES/_erzeuge_qss() unten -
@@AKZENT@@/@@AKZENT_HOVER@@/@@AKZENT_PRESSED@@/@@AKZENT_HELL@@ sind Platzhalter, die vor
dem Anwenden per str.replace() durch die Theme-Hexwerte ersetzt werden; str.format() geht
hier nicht, da das Stylesheet selbst voller literaler {}-Blockklammern ist). Die übrigen
Platzhalter dieser Art (Hintergrund, Flächen, Rahmen, Schrift) kommen aus dem gewählten
Hintergrund-Design (_DESIGNS unten); "hell" entspricht dem bisherigen Aussehen. Ruhige
Flächen statt vieler Rahmen/Schatten. Global über QApplication.setStyleSheet() gesetzt
(siehe main() unten) - HauptFenster & Dialoge setzen zusätzlich per ResponsiveSchriftMixin
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

/* Reiter (Teilnehmer/Zeitplan/.../Datensicherung sowie der Hilfe-Dialog) */
QTabWidget::pane {
    border: 1px solid @@RAND@@;
    background: @@HINTERGRUND@@;
    top: -1px;
}
QTabBar::tab {
    background: @@HINTERGRUND@@;
    color: @@TEXT_GEDAEMPFT@@;
    padding: 8px 16px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-right: 2px;
}
QTabBar::tab:selected {
    color: @@TEXT_STARK@@;
    font-weight: 600;
    border-bottom: 2px solid @@AKZENT@@;
}
QTabBar::tab:hover:!selected {
    color: @@TEXT_STARK@@;
}

/* Schaltflächen: neutral/sekundär als Standard; die jeweilige Haupt-Aktion eines
Reiters/Dialogs trägt objectName "primaerButton" (siehe z.B. TeilnehmerTab) und wird
blau hervorgehoben - ebenso automatisch jeder Dialog-Default-Button (die "OK"-Schaltfläche
einer QDialogButtonBox, über die Qt-eigene :default-Pseudoklasse, ohne dass jeder
Dialog einzeln angepasst werden muss). */
QPushButton {
    background: @@FLAECHE@@;
    color: @@TEXT_BUTTON@@;
    border: 1px solid @@RAND@@;
    border-radius: 6px;
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
    color: #FFFFFF;
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
    border-radius: 6px;
    padding: 4px 8px;
    color: @@TEXT@@;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {
    border: 1px solid @@AKZENT@@;
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
QCheckBox {
    color: @@TEXT@@;
    spacing: 6px;
}

/* Tabellen (Teilnehmer, Ergebniserfassung, Auswertung, Zeitplan, Terminübersicht) */
QTableWidget {
    background: @@HINTERGRUND@@;
    alternate-background-color: @@TABELLE_ALT@@;
    gridline-color: @@RAND@@;
    border: 1px solid @@RAND@@;
    border-radius: 6px;
    selection-background-color: @@AKZENT_HELL@@;
    selection-color: @@TEXT@@;
}
QTableWidget::item {
    padding: 4px 6px;
}
QTableWidget::item:selected {
    background: @@AKZENT_HELL@@;
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
"""

_THEME_DEFAULT = "blau"

# Drei Akzentfarb-Themes (Menü Ansicht -> Akzentfarbe): nur der Akzentton wechselt, der
# Hintergrund kommt unabhängig davon aus _DESIGNS unten. "blau" + Design "hell" entspricht
# bit-für-bit dem bisherigen, fest verdrahteten Erscheinungsbild (siehe test_theme.py).
_THEMES: dict[str, dict[str, str]] = {
    "blau": {
        "anzeigename": "Blau (Standard)",
        "akzent": "#2F6FED",
        "akzent_hover": "#2A63D6",
        "akzent_pressed": "#2558BF",
        "akzent_hell": "#EAF1FF",
    },
    "gruen": {
        "anzeigename": "Grün",
        "akzent": "#1E8E5A",
        "akzent_hover": "#1A7A4D",
        "akzent_pressed": "#166741",
        "akzent_hell": "#E7F3EC",
    },
    "violett": {
        "anzeigename": "Violett",
        "akzent": "#6B4FBB",
        "akzent_hover": "#5F45A8",
        "akzent_pressed": "#523B92",
        "akzent_hell": "#EEEAF8",
    },
}


_DESIGN_DEFAULT = "hell"

# Nur für Designs außer "hell" angehängt (hell bleibt damit bit-für-bit wie bisher): gut
# sichtbare Checkboxen. Ohne diese Regel zeichnet Fusion (dunkles Design) den Rahmen
# dunkler als den Hintergrund und die Box verschwindet. Eine eigene ::indicator-Regel
# schaltet allerdings das native Häkchen ab - deshalb das weiße Häkchen als Bild
# (@@HAKEN@@, erzeugt von _haken_bild_bereitstellen()).
_QSS_CHECKBOX_ZUSATZ = """
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid @@TEXT_GEDAEMPFT@@;
    border-radius: 3px;
    background: @@FLAECHE@@;
}
QCheckBox::indicator:hover {
    border-color: @@AKZENT@@;
}
QCheckBox::indicator:checked {
    background: @@AKZENT@@;
    border-color: @@AKZENT@@;
    image: url(@@HAKEN@@);
}
QCheckBox::indicator:disabled {
    background: @@FLAECHE_DISABLED@@;
    border-color: @@RAND_DISABLED@@;
}
QCheckBox::indicator:checked:disabled {
    background: @@TEXT_DISABLED@@;
    border-color: @@TEXT_DISABLED@@;
}
"""


def _haken_pfad() -> str:
    """Ablageort des Häkchen-Bildes (Vorwärtsschrägstriche, wie QSS-url() sie erwartet)."""
    return os.path.join(tempfile.gettempdir(), "SHS-Pruefungsprogramm", "haken.png").replace("\\", "/")


def _haken_bild_bereitstellen() -> None:
    """Zeichnet das weiße Häkchen für _QSS_CHECKBOX_ZUSATZ einmalig als PNG. Scheitert
    das (Temp-Ordner nicht beschreibbar), bleibt die angehakte Box nur akzentfarbig
    gefüllt - kein Grund, den Programmstart oder den Designwechsel abzubrechen."""
    pfad = _haken_pfad()
    if os.path.isfile(pfad) and os.path.getsize(pfad) > 0:
        return
    try:
        os.makedirs(os.path.dirname(pfad), exist_ok=True)
    except OSError:
        return
    bild = QImage(32, 32, QImage.Format_ARGB32)
    bild.fill(Qt.transparent)
    maler = QPainter(bild)
    maler.setRenderHint(QPainter.Antialiasing)
    stift = QPen(QColor("#FFFFFF"), 4)
    stift.setCapStyle(Qt.RoundCap)
    stift.setJoinStyle(Qt.RoundJoin)
    maler.setPen(stift)
    maler.drawPolyline([QPointF(7, 17), QPointF(13, 23), QPointF(25, 9)])
    maler.end()
    bild.save(pfad)


# Hintergrund-Designs (unabhängig von der Akzentfarbe in _THEMES frei kombinierbar, siehe
# Menü Ansicht -> Hintergrund). Die Großbuchstaben-Schlüssel füllen die gleichnamigen
# @@...@@-Platzhalter in _QSS_TEMPLATE; "hell" entspricht bit-für-bit dem bisherigen
# Aussehen (siehe test_theme.py). Die Kleinbuchstaben-Schlüssel sind semantische Farben für
# Stellen, an denen der Code selbst färbt (Tabellenzellen, HTML-Labels) - abgerufen über
# _farbe(). "dunkel": True schaltet zusätzlich den Fusion-Stil samt dunkler QPalette ein
# und mischt die Auswahlfarbe aus Akzent und Hintergrund (siehe _darstellung_anwenden()).
_DESIGNS: dict[str, dict] = {
    "hell": {
        "anzeigename": "Hell (Standard)",
        "dunkel": False,
        "HINTERGRUND": "#FFFFFF",
        "FLAECHE": "#F1F4F8",
        "FLAECHE_HOVER": "#E7ECF3",
        "FLAECHE_PRESSED": "#DCE3EC",
        "FLAECHE_DISABLED": "#F6F8FA",
        "RAND": "#E4E8EE",
        "RAND_DISABLED": "#EDF0F4",
        "TEXT": "#1B2430",
        "TEXT_STARK": "#16233E",
        "TEXT_BUTTON": "#2A3342",
        # UX-Test 02.10.2026, U14: Reiter/Spaltenköpfe dunkler (vorher #6B7686/#8A94A6,
        # Spaltenköpfe nur Kontrast 3:1 - für schlechtere Augen zu blass).
        "TEXT_GEDAEMPFT": "#55606F",
        "PLATZHALTER": "#6B7686",  # UX-Test U14: heller als TEXT_GEDAEMPFT
        "TEXT_HEADER": "#55606F",
        "TEXT_DISABLED": "#A7B0BD",
        "TABELLE_ALT": "#FBFCFD",
        "SCROLL": "#D8DEE7",
        "SCROLL_HOVER": "#C3CBD8",
        "ok": "#2E7D32",
        "warnung": "#B56A00",
        "fehler": "#C62828",
        "gedaempft": "#808080",
        "ungespeichert_bg": "#FFF3CD",
        "zeile_bg": "#FFFFFF",
    },
    "sand": {
        "anzeigename": "Warm / Sand",
        "dunkel": False,
        "HINTERGRUND": "#FBF8F3",
        "FLAECHE": "#F2EDE4",
        "FLAECHE_HOVER": "#EAE3D7",
        "FLAECHE_PRESSED": "#E0D7C8",
        "FLAECHE_DISABLED": "#F6F2EB",
        "RAND": "#E3DBCD",
        "RAND_DISABLED": "#ECE6DB",
        "TEXT": "#2B2620",
        "TEXT_STARK": "#1F1A14",
        "TEXT_BUTTON": "#3A332A",
        # UX-Test 02.10.2026, U14: dunkler (vorher #756B5E/#8C8172).
        "TEXT_GEDAEMPFT": "#5E5549",
        "PLATZHALTER": "#756B5E",  # UX-Test U14: heller als TEXT_GEDAEMPFT
        "TEXT_HEADER": "#5E5549",
        "TEXT_DISABLED": "#B3A898",
        "TABELLE_ALT": "#F7F3EC",
        "SCROLL": "#DDD4C5",
        "SCROLL_HOVER": "#CABFAE",
        "ok": "#2E7D32",
        "warnung": "#A15C00",
        "fehler": "#B3261E",
        "gedaempft": "#857A6C",
        "ungespeichert_bg": "#FCEBC0",
        "zeile_bg": "#FBF8F3",
    },
    "dunkel": {
        "anzeigename": "Dunkel",
        "dunkel": True,
        "HINTERGRUND": "#1E2228",
        "FLAECHE": "#2A2F37",
        "FLAECHE_HOVER": "#333944",
        "FLAECHE_PRESSED": "#3C434F",
        "FLAECHE_DISABLED": "#24282F",
        "RAND": "#3A414B",
        "RAND_DISABLED": "#2E333B",
        "TEXT": "#E6E9EE",
        "TEXT_STARK": "#FFFFFF",
        "TEXT_BUTTON": "#DDE2E8",
        "TEXT_GEDAEMPFT": "#9AA4B2",
        "PLATZHALTER": "#9AA4B2",  # UX-Test U14: heller als TEXT_GEDAEMPFT
        "TEXT_HEADER": "#9AA4B2",
        "TEXT_DISABLED": "#5F6875",
        "TABELLE_ALT": "#23272E",
        "SCROLL": "#454C57",
        "SCROLL_HOVER": "#58606C",
        "ok": "#6FCF97",
        "warnung": "#F2B84B",
        "fehler": "#FF7B72",
        "gedaempft": "#7D8795",
        "ungespeichert_bg": "#4A3F1F",
        "zeile_bg": "#1E2228",
    },
    "kontrast": {
        "anzeigename": "Hoher Kontrast",
        "dunkel": False,
        "HINTERGRUND": "#FFFFFF",
        "FLAECHE": "#FFFFFF",
        "FLAECHE_HOVER": "#E8E8E8",
        "FLAECHE_PRESSED": "#D0D0D0",
        "FLAECHE_DISABLED": "#F2F2F2",
        "RAND": "#1B1B1B",
        "RAND_DISABLED": "#9A9A9A",
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
        "ok": "#0B6B2E",
        "warnung": "#8A4B00",
        "fehler": "#B00020",
        "gedaempft": "#4D4D4D",
        "ungespeichert_bg": "#FFE58A",
        "zeile_bg": "#FFFFFF",
    },
}

# Anteil der Akzentfarbe an der Auswahlfarbe in dunklen Designs (Rest: Hintergrund) -
# das helle akzent_hell aus _THEMES wäre auf dunklem Grund ein greller Balken.
_AUSWAHL_MISCHANTEIL_DUNKEL = 0.35

# Zuletzt per _darstellung_anwenden() gesetztes Design; _farbe() liest es. Standard "hell",
# damit Tabs, die ohne main() erzeugt werden (GUI-Tests), die bisherigen Farben bekommen.
_aktives_design = _DESIGN_DEFAULT


def _mische(farbe1: str, farbe2: str, anteil1: float) -> str:
    """Mischt zwei #RRGGBB-Farben linear; anteil1 = Gewicht von farbe1 (0..1)."""
    kanaele = []
    for i in (1, 3, 5):
        a = int(farbe1[i:i + 2], 16)
        b = int(farbe2[i:i + 2], 16)
        kanaele.append(round(a * anteil1 + b * (1 - anteil1)))
    return "#{:02X}{:02X}{:02X}".format(*kanaele)


def _auswahlfarbe(theme: dict, design: dict) -> str:
    """Hintergrund markierter Tabellenzeilen: in dunklen Designs aus Akzent und
    Hintergrund gemischt, sonst das helle akzent_hell des Themes."""
    if design["dunkel"]:
        return _mische(theme["akzent"], design["HINTERGRUND"], _AUSWAHL_MISCHANTEIL_DUNKEL)
    return theme["akzent_hell"]


def _erzeuge_qss(theme_name: str, design_name: str = _DESIGN_DEFAULT) -> str:
    """Setzt die Akzentfarb-Platzhalter (Theme) und die Hintergrund-Platzhalter (Design)
    in _QSS_TEMPLATE ein. Unbekannte Namen fallen auf den jeweiligen Standard zurück."""
    theme = _THEMES.get(theme_name, _THEMES[_THEME_DEFAULT])
    design = _DESIGNS.get(design_name, _DESIGNS[_DESIGN_DEFAULT])
    text = _QSS_TEMPLATE
    if design_name in _DESIGNS and design_name != _DESIGN_DEFAULT:
        text += _QSS_CHECKBOX_ZUSATZ.replace("@@HAKEN@@", _haken_pfad())
    text = text.replace("@@AKZENT_HOVER@@", theme["akzent_hover"])
    text = text.replace("@@AKZENT_PRESSED@@", theme["akzent_pressed"])
    text = text.replace("@@AKZENT_HELL@@", _auswahlfarbe(theme, design))
    text = text.replace("@@AKZENT@@", theme["akzent"])
    for schluessel, wert in design.items():
        if schluessel.isupper():
            text = text.replace(f"@@{schluessel}@@", wert)
    return text


def _farbe(name: str) -> QColor:
    """Semantische Farbe (ok/warnung/fehler/gedaempft/ungespeichert_bg/zeile_bg) des
    aktiven Hintergrund-Designs - für Stellen, an denen der Code selbst färbt."""
    return QColor(_DESIGNS[_aktives_design][name])


_SETTINGS_ORG = "SHS-Pruefungsprogramm"
_SETTINGS_APP = "Desktop"
_SETTINGS_KEY_THEME = "darstellung/theme"
_SETTINGS_KEY_DESIGN = "darstellung/hintergrund"


def _gespeichertes_theme_lesen() -> str:
    """Liest das zuletzt gewählte Theme pro Windows-Benutzer (QSettings/Registry)."""
    einstellungen = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
    wert = einstellungen.value(_SETTINGS_KEY_THEME, _THEME_DEFAULT)
    return wert if wert in _THEMES else _THEME_DEFAULT


def _theme_speichern(theme_name: str) -> None:
    QSettings(_SETTINGS_ORG, _SETTINGS_APP).setValue(_SETTINGS_KEY_THEME, theme_name)


def _gespeichertes_design_lesen() -> str:
    """Liest das zuletzt gewählte Hintergrund-Design pro Windows-Benutzer."""
    einstellungen = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
    wert = einstellungen.value(_SETTINGS_KEY_DESIGN, _DESIGN_DEFAULT)
    return wert if wert in _DESIGNS else _DESIGN_DEFAULT


def _design_speichern(design_name: str) -> None:
    QSettings(_SETTINGS_ORG, _SETTINGS_APP).setValue(_SETTINGS_KEY_DESIGN, design_name)


# Stil und Palette, mit denen die Anwendung gestartet ist - beim ersten
# _darstellung_anwenden() gemerkt, damit "hell" exakt das bisherige Aussehen behält.
_ursprung_stil: str | None = None
_ursprung_palette: QPalette | None = None
# Zuletzt per setStyle() gesetzter Stil - selbst mitgeführt, weil app.style() bei aktivem
# Stylesheet den internen Stylesheet-Stil (ohne Namen) liefert.
_aktueller_stil: str | None = None


def _design_palette(theme: dict, design: dict) -> QPalette:
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
        QPalette.Highlight: _auswahlfarbe(theme, design),
        QPalette.HighlightedText: design["TEXT"],
        QPalette.Link: theme["akzent"],
        QPalette.Light: design["FLAECHE_HOVER"],
        QPalette.Midlight: design["FLAECHE"],
        QPalette.Mid: design["RAND"],
        QPalette.Dark: design["RAND"],
        QPalette.Shadow: "#000000",
    }
    for rolle, wert in rollen.items():
        palette.setColor(rolle, QColor(wert))
    for rolle in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, rolle, QColor(design["TEXT_DISABLED"]))
    return palette


def _darstellung_anwenden(app: QApplication) -> None:
    """Wendet gespeicherte Akzentfarbe + Hintergrund-Design auf die ganze Anwendung an."""
    global _aktives_design, _ursprung_stil, _ursprung_palette, _aktueller_stil
    theme_name = _gespeichertes_theme_lesen()
    design_name = _gespeichertes_design_lesen()
    theme = _THEMES[theme_name]
    design = _DESIGNS[design_name]

    if _ursprung_stil is None:
        # Stylesheet kurz entfernen, damit style() den echten Basis-Stil liefert.
        stylesheet = app.styleSheet()
        app.setStyleSheet("")
        _ursprung_stil = app.style().name()
        _aktueller_stil = _ursprung_stil
        _ursprung_palette = QPalette(app.palette())
        app.setStyleSheet(stylesheet)

    # Native Windows-Stile ignorieren eine dunkle Palette bei Menüs/Popups teilweise,
    # Fusion zeichnet alles aus der Palette - deshalb nur für dunkle Designs.
    ziel_stil = "fusion" if design["dunkel"] else _ursprung_stil
    if ziel_stil and ziel_stil.lower() != (_aktueller_stil or "").lower():
        app.setStyle(ziel_stil)
        _aktueller_stil = ziel_stil

    if design_name != _DESIGN_DEFAULT:
        app.setPalette(_design_palette(theme, design))
        _haken_bild_bereitstellen()
    elif _aktives_design != _DESIGN_DEFAULT:
        # Nur beim Rückweg zu "hell" - beim Start in "hell" bleibt die Palette ganz
        # unangetastet, damit sie weiter dem Windows-Farbschema folgen kann.
        app.setPalette(_ursprung_palette)
    _aktives_design = design_name
    app.setStyleSheet(_erzeuge_qss(theme_name, design_name))
