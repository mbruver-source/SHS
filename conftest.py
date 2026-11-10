"""Gemeinsame pytest-Einstellungen.

- QSettings zeigen für die Tests in einen eigenen Ordner (sonst schreiben die Tests in die echten
  Benutzereinstellungen, z. B. Registry unter Windows); der Ordner wird am Ende gelöscht.
- Vor jedem GUI-Test sind die gespeicherten Einstellungen leer (kein Zustand von einem
  vorigen Test, z. B. Sortierung, Schriftgröße, „ohne Nachfrage speichern“).
- Wächter gegen hängende Meldungsfenster (Marco 10.11.2026): bleibt in einem GUI-Test ein
  modales Fenster länger als 20 Sekunden offen, wird es geschlossen und der Test scheitert mit
  dem Fenstertitel, statt den ganzen Lauf anzuhalten.
- Marke `langsam` für die Tests, die über etwa 10 Sekunden dauern (`pytest -m "not langsam"`).
"""
import atexit
import shutil
import tempfile

import pytest

_ORDNER = tempfile.mkdtemp(prefix="shs_qsettings_")
atexit.register(shutil.rmtree, _ORDNER, ignore_errors=True)

try:
    from PySide6.QtCore import QSettings

    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, _ORDNER)
except ImportError:  # CI-Läufe ohne PySide6
    QSettings = None

_WARTEZEIT_SEKUNDEN = 20


def pytest_configure(config):
    config.addinivalue_line("markers", "langsam: dauert über etwa 10 Sekunden (pytest -m \"not langsam\" lässt sie aus)")


@pytest.fixture(autouse=True)
def _einstellungen_leeren_und_fenster_wachen(request):
    if QSettings is None or "qtbot" not in request.fixturenames:
        yield
        return
    import time

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QDialog

    import desktop_darstellung

    QSettings(desktop_darstellung._SETTINGS_ORG, desktop_darstellung._SETTINGS_APP).clear()
    haengende: list[str] = []
    zustand = {"fenster": None, "seit": 0.0}

    def pruefen() -> None:
        modal = QApplication.activeModalWidget()
        if modal is None:
            zustand["fenster"] = None
            return
        if modal is not zustand["fenster"]:
            zustand["fenster"], zustand["seit"] = modal, time.monotonic()
            return
        if time.monotonic() - zustand["seit"] >= _WARTEZEIT_SEKUNDEN:
            haengende.append(f"{type(modal).__name__} „{modal.windowTitle()}“")
            zustand["fenster"] = None
            modal.reject() if isinstance(modal, QDialog) else modal.close()

    zeitgeber = QTimer()
    zeitgeber.setInterval(500)
    zeitgeber.timeout.connect(pruefen)
    zeitgeber.start()
    try:
        yield
    finally:
        zeitgeber.stop()
    assert not haengende, f"Der Test ließ ein echtes Fenster offen (nicht abgefangen): {', '.join(haengende)}"
