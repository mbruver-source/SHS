"""
Gemeinsame Hilfen der Dialoge: Größe an den Bildschirm anpassen, scrollbare Fläche, Speichern vor dem Schließen.

Aus desktop_dialoge.py ausgelagert (11.11.2026), Code unverändert; desktop_dialoge.py bleibt als
Fassade. Bewusst KEIN `import app` (siehe desktop_programm.py).
"""

from __future__ import annotations
import sqlite3
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QScrollArea,
    QWidget,
)
from desktop_gemeinsam import (
    _db_fehler_anzeigen,
    _fehler_anzeigen,
)


#: Höchstens so viel des freien Bildschirms nimmt ein Dialog beim Öffnen ein (U3, N2, N14).
DIALOG_MAX_BREITE_ANTEIL = 0.95


DIALOG_MAX_HOEHE_ANTEIL = 0.9


def _groesse_auf_bildschirm_begrenzen(dialog, breite: int, hoehe: int, inhalt: QWidget | None = None,
                                      hoehe_nach_inhalt: bool = False) -> None:
    """Startgröße, begrenzt auf den verfügbaren Bildschirm (UX-Test 02.10.2026, U3), damit
    OK/Abbrechen auch auf kleinen Laptops sichtbar bleiben - gemeinsam für Teilnehmer- und
    Veranstaltungsdialog (Desktop-Prüfung 14.10.2026, Teil 2 Nr. 7). Mit `inhalt` (dem
    Formular in der Scrollfläche) mindestens so breit wie dessen Bedarf - bei Schrift „Groß“
    reichte die feste Breite nicht, und es gab einen waagerechten Bildlauf (Nachtest 2, N2).
    Mit `hoehe_nach_inhalt` auch mindestens so hoch (Termin-Dialog, Nachtest 2, N14) - der
    Bildlauf bleibt dann nur, wo der Bildschirm nicht reicht."""
    if inhalt is not None:
        # Erst polieren (Stylesheet-Ränder der Felder), dann messen; + Rand der Scrollfläche,
        # senkrechte Bildlaufleiste und Ränder des Dialogs.
        inhalt.ensurePolished()
        breite = max(breite, inhalt.sizeHint().width() + 100)
        if hoehe_nach_inhalt:
            # + Rand der Scrollfläche, OK/Abbrechen und Ränder des Dialogs
            hoehe = max(hoehe, inhalt.sizeHint().height() + 110)
    bildschirm = dialog.screen() or QApplication.primaryScreen()
    if bildschirm is not None:
        frei = bildschirm.availableGeometry()
        breite = min(breite, int(frei.width() * DIALOG_MAX_BREITE_ANTEIL))
        hoehe = min(hoehe, int(frei.height() * DIALOG_MAX_HOEHE_ANTEIL))
    dialog.resize(breite, hoehe)


def _scrollflaeche(inhalt) -> QScrollArea:
    """Scrollfläche um den Formularinhalt, die selbst keinen Fokus nimmt (Teil 2 Nr. 6:
    sonst ging sofortiges Tippen beim Öffnen ins Leere)."""
    scroll = QScrollArea()
    scroll.setWidget(inhalt)
    scroll.setWidgetResizable(True)
    scroll.setFocusPolicy(Qt.NoFocus)
    return scroll


def _speichern_vor_dem_schliessen(dialog: QDialog, speichern) -> bool:
    """Desktop-Prüfung 14.10.2026, Teil 2 Nr. 1: Speichert über den Rückruf des Aufrufers,
    BEVOR der Dialog schließt. Scheitert das (Fachregel oder z. B. schreibgeschützte bzw.
    gesperrte Termin-Datei), erscheint eine Meldung und der Dialog bleibt mit allen Eingaben
    offen. Ohne Rückruf (z. B. in der Demoprüfung) schließt er wie bisher sofort."""
    if speichern is None:
        return True
    try:
        speichern(dialog)
    except (sqlite3.IntegrityError, ValueError) as exc:  # ValueError: Wert zu lang o. Ä. (I-5)
        _fehler_anzeigen(dialog, exc)
        return False
    except sqlite3.Error as exc:
        _db_fehler_anzeigen(
            dialog, exc, "Die Eingaben wurden nicht gespeichert, sie bleiben im Fenster stehen."
        )
        return False
    return True
