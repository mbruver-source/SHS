"""GUI-Tests: Barrierefreiheit (Tastatur und Bildschirmleser), seit 11.11.2026.

Prüft für die Hauptfenster-Reiter und die wichtigsten Dialoge, was sich ohne Bildschirmleser
messen lässt:
- Jedes bedienbare Element hat einen zugänglichen Namen (Text, accessibleName oder ein
  zugeordnetes Beschriftungsfeld „buddy“) - sonst liest ein Bildschirmleser nur „Schaltfläche“.
- Jedes bedienbare Element ist mit der Tastatur erreichbar (Fokus-Regel nicht „kein Fokus“).
- Tabellen haben einen Namen und lassen sich mit Pfeiltasten bedienen (Fokus erlaubt).
Fixtures und Hilfen stehen in gui_hilfen.py.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractSpinBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QTableWidget,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QWidget,
)

from db import add_zeitplan_pruefungsblock, add_zeitplan_richter
from gui_hilfen import *  # noqa: F401,F403
from app import HauptFenster, StartDialog
from desktop_dialoge import PauseDialog, TeilnehmerDialog, VeranstaltungsDialog
from desktop_hilfe import HilfeDialog
from desktop_programm import VersionDialog

_BEDIENELEMENTE = (QAbstractButton, QAbstractSpinBox, QComboBox, QLineEdit, QPlainTextEdit, QTextEdit, QTableWidget,
                  QListWidget)


def _hat_namen(widget: QWidget) -> bool:
    """True, wenn ein Bildschirmleser einen Namen für das Element findet."""
    if widget.accessibleName().strip():
        return True
    if isinstance(widget, QAbstractButton) and widget.text().strip():
        return True
    # Beschriftungsfeld mit buddy() auf das Element (z. B. aus QFormLayout.addRow("Text", feld)).
    fenster = widget.window()
    for label in fenster.findChildren(QLabel):
        if label.buddy() is widget and label.text().strip():
            return True
    # Eingebettetes Feld eines Dreh- oder Kombifelds: gehört zum Elternelement.
    eltern = widget.parentWidget()
    if isinstance(eltern, (QAbstractSpinBox, QComboBox)):
        return True
    return False


def _bedienelemente(wurzel: QWidget):
    for widget in wurzel.findChildren(QWidget):
        if not isinstance(widget, _BEDIENELEMENTE):
            continue
        if widget.objectName().startswith("qt_"):  # Qt-eigene Innenteile (Bildlaufleisten, Spinbox-Feld …)
            continue
        if isinstance(widget, QLineEdit) and isinstance(widget.parentWidget(), (QAbstractSpinBox, QComboBox)):
            continue
        if isinstance(widget, QToolButton) and isinstance(widget.parentWidget(), QLineEdit):
            continue  # Löschknopf des Suchfelds (setClearButtonEnabled): gehört zum Feld
        yield widget


def _attributname(widget: QWidget) -> str:
    """Findet den Attributnamen des Elements an einem Elternobjekt (für lesbare Befunde)."""
    eltern = widget.parentWidget()
    while eltern is not None:
        for name, wert in vars(eltern).items():
            if wert is widget:
                return f"{type(eltern).__name__}.{name}"
        eltern = eltern.parentWidget()
    return "?"


def _beschreibung(widget: QWidget) -> str:
    text = widget.text() if hasattr(widget, "text") and not isinstance(widget, QTableWidget) else ""
    return f"{_attributname(widget)} {type(widget).__name__}(text={text[:25]!r}, tooltip={widget.toolTip()[:30]!r})"


def _befunde(wurzel: QWidget) -> list[str]:
    befunde = []
    for widget in _bedienelemente(wurzel):
        if not _hat_namen(widget):
            befunde.append("ohne Namen: " + _beschreibung(widget))
        if widget.isEnabled() and widget.focusPolicy() == Qt.NoFocus and not isinstance(widget, (QTableWidget, QListWidget)):
            befunde.append("ohne Tastaturfokus: " + _beschreibung(widget))
        if isinstance(widget, (QTableWidget, QListWidget)) and widget.focusPolicy() == Qt.NoFocus:
            befunde.append("Tabelle ohne Tastaturfokus: " + _beschreibung(widget))
    return befunde


@pytest.fixture
def fenster_mit_daten(qtbot, termin):
    conn, pfad = termin
    for nr in range(1, 4):
        _teilnehmer_anlegen(conn, nachname=f"Name{nr}", startnummer=nr, art="DK" if nr == 3 else "ED",
                            disziplin=None if nr == 3 else "Flächensuche")
    # Ein Richter mit Block und eine Pause, damit die Zeitplan-Spalte samt ihren Knöpfen entsteht.
    richter_id = add_zeitplan_richter(conn, "Richter A")
    add_zeitplan_pruefungsblock(conn, richter_id, "ED", 1, "Flächensuche", 10)
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    return fenster


def test_hauptfenster_reiter_haben_namen_und_fokus(fenster_mit_daten):
    fenster = fenster_mit_daten
    tabs = fenster.findChild(QTabWidget)
    alle = []
    for i in range(tabs.count()):
        tabs.setCurrentIndex(i)
        reiter = tabs.widget(i)
        alle += [f"[{tabs.tabText(i)}] {b}" for b in _befunde(reiter)]
    assert alle == [], "\n" + "\n".join(alle)


def test_dialoge_haben_namen_und_fokus(qtbot, termin):
    conn, pfad = termin
    dialoge = {
        "Teilnehmer": TeilnehmerDialog(None),
        "Veranstaltung": VeranstaltungsDialog(None),
        "Version": VersionDialog(None),
        "Hilfe": HilfeDialog(None),
        "Pause": PauseDialog(None),
        "Start": StartDialog(None),
    }
    alle = []
    for name, dialog in dialoge.items():
        qtbot.addWidget(dialog)
        dialog.show()
        alle += [f"[{name}] {b}" for b in _befunde(dialog)]
    assert alle == [], "\n" + "\n".join(alle)


def _per_tab_erreichbar(fenster: QWidget, erwartet: list[QWidget], schritte: int = 400) -> list[str]:
    """Wandert mit „Nächstes Element“ (Tab) durch das Fenster und meldet erwartete Elemente, die
    dabei nie den Fokus bekommen (Tastaturfalle oder unerreichbares Bedienelement)."""
    fenster.activateWindow()
    gesehen: set[int] = set()
    for _ in range(schritte):
        fenster.focusNextChild()
        aktuell = fenster.focusWidget()
        if aktuell is not None:
            gesehen.add(id(aktuell))
    return [_beschreibung(w) for w in erwartet if id(w) not in gesehen]


def _tab_ziele(wurzel: QWidget) -> list[QWidget]:
    """Alle sichtbaren, aktiven Bedienelemente, die per Tab erreichbar sein sollen."""
    ziele = []
    for widget in _bedienelemente(wurzel):
        if widget.isVisibleTo(wurzel) and widget.isEnabled() and widget.focusPolicy() & Qt.TabFocus:
            ziele.append(widget)
    return ziele


@pytest.mark.parametrize("dialog_klasse", [TeilnehmerDialog, VeranstaltungsDialog, VersionDialog, HilfeDialog])
def test_dialoge_sind_mit_tab_vollstaendig_erreichbar(qtbot, dialog_klasse):
    dialog = dialog_klasse(None)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    verfehlt = _per_tab_erreichbar(dialog, _tab_ziele(dialog))
    assert verfehlt == [], "\n" + "\n".join(verfehlt)


def test_hauptfenster_reiter_sind_mit_tab_vollstaendig_erreichbar(fenster_mit_daten, qtbot):
    fenster = fenster_mit_daten
    qtbot.waitExposed(fenster)
    tabs = fenster.findChild(QTabWidget)
    verfehlt = []
    for i in range(tabs.count()):
        tabs.setCurrentIndex(i)
        reiter = tabs.widget(i)
        verfehlt += [f"[{tabs.tabText(i)}] {b}" for b in _per_tab_erreichbar(fenster, _tab_ziele(reiter))]
    assert verfehlt == [], "\n" + "\n".join(verfehlt)
