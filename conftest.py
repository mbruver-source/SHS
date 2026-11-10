"""Gemeinsame pytest-Einstellungen: QSettings zeigen für die Tests in einen eigenen Ordner
(sonst schreiben die Tests in die echten Benutzereinstellungen, z. B. Registry unter Windows)."""
import tempfile

_ORDNER = tempfile.mkdtemp(prefix="shs_qsettings_")

try:
    from PySide6.QtCore import QSettings

    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, _ORDNER)
except ImportError:  # CI-Läufe ohne PySide6
    pass
