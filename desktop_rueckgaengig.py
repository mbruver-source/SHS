"""
Eine Ebene „Rückgängig“ für Reiter der Desktop-Oberfläche (seit 11.11.2026 aus
desktop_teilnehmer.py herausgelöst; dort Marco 10.11.2026: Löschen und Startnummern
zurücksetzen ließen sich nicht zurücknehmen). Die Klasse hält nur Zustand und Knopf; das
Ausführen, Fehlermeldungen und das Neuladen der Anzeige bleiben beim Reiter.
Bewusst KEIN `import app` (siehe desktop_programm.py).
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QPushButton

from desktop_gemeinsam import _klartext_tooltip

_NICHTS_ZURUECK = "Nichts zum Rückgängigmachen"


class RueckgaengigSpeicher:
    """Merkt die zuletzt gemerkte Aktion samt Beschreibung und steuert den Knopf (aktiv und
    Tooltip nur, solange etwas zum Rückgängigmachen da ist). Eine neue Aktion ersetzt die alte."""

    def __init__(self, knopf: QPushButton):
        self.knopf = knopf
        self._aktion: tuple[str, Callable[[], str]] | None = None
        self._knopf_zuruecksetzen()

    def merken(self, beschreibung: str, aktion: Callable[[], str]) -> None:
        """Merkt eine Aktion; `aktion` liefert beim Ausführen den Text für die Statuszeile."""
        self._aktion = (beschreibung, aktion)
        self.knopf.setEnabled(True)
        # Die Beschreibung kann einen Namen aus importierten Daten enthalten (D-8): als Klartext.
        self.knopf.setToolTip(_klartext_tooltip(f"Macht rückgängig: {beschreibung} (Strg+Z)"))

    def entnehmen(self) -> tuple[str, Callable[[], str]] | None:
        """Gibt (Beschreibung, Aktion) zurück und leert den Speicher (der Knopf wird wieder
        gesperrt), oder None, wenn nichts gemerkt ist."""
        if self._aktion is None:
            return None
        eintrag = self._aktion
        self._aktion = None
        self._knopf_zuruecksetzen()
        return eintrag

    def _knopf_zuruecksetzen(self) -> None:
        self.knopf.setEnabled(False)
        self.knopf.setToolTip(_NICHTS_ZURUECK)
