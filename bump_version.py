"""Erhöht die Versionsnummer für einen neuen Release-Build automatisch.

Schema (wie vom Verein festgelegt): die 3. Stelle (Patch) wird bei jedem
Build um 1 erhöht, bis sie 99 erreicht hat - danach wird die 2. Stelle
(Minor) um 1 erhöht und die 3. Stelle beginnt wieder bei 0, und so weiter.
Erreicht auch die 2. Stelle 99, wird nach demselben Muster die 1. Stelle
(Major) erhöht (in der Praxis bei einem kleinen Vereinsprogramm eher
theoretisch, aber der Vollständigkeit halber genauso behandelt).

Liest/schreibt die aktuelle Versionsnummer in version.txt (einzige
"Quelle der Wahrheit") und schreibt dieselbe Nummer zusätzlich in
version_info.txt (Windows-Versionsinfo, die PyInstaller in die .exe
einbettet, siehe build.spec) sowie in version.py (von app.py importiert,
für die Versionsanzeige in der GUI - siehe Version-Button neben "Hilfe").
Außerdem wird die Zeile "Stand: Version X.Y.Z." in docs/HANDBUCH.md
nachgezogen (docs/HANDBUCH.pdf danach mit tools/handbuch_pdf.py neu erzeugen).

Wird von build_installer.bat VOR dem PyInstaller-Build aufgerufen und gibt
die neue Versionsnummer (z.B. "1.0.1") auf stdout aus, damit das Batch-Skript
sie unverändert an ISCC (Inno Setup, /DMyAppVersion=...) weitergeben kann.

Von Hand ausführen (z.B. zum Nachsehen, ohne gleich zu bauen):
    python bump_version.py
"""
from __future__ import annotations

import pathlib
import re

HIER = pathlib.Path(__file__).resolve().parent
VERSION_DATEI = HIER / "version.txt"
VERSION_INFO_DATEI = HIER / "version_info.txt"
# Laufzeit-lesbare Version für die GUI (siehe app.py, Version-Button neben "Hilfe"):
# version.txt/version_info.txt dienen PyInstaller/Inno Setup beim Bauen, werden aber
# selbst NICHT mit in die .exe gepackt (kein Eintrag in build.spec/datas). version.py
# dagegen ist eine ganz normale, von app.py importierte Python-Datei - PyInstaller
# erkennt und bündelt sie daher automatisch, genau wie db.py/shs_core.py (siehe
# Kommentar in build.spec), ganz ohne zusätzlichen datas-Eintrag.
VERSION_PY_DATEI = HIER / "version.py"
# Benutzerhandbuch mit der Zeile "Stand: Version X.Y.Z." (siehe handbuch_version_schreiben)
HANDBUCH_DATEI = HIER / "docs" / "HANDBUCH.md"
_HANDBUCH_VERSIONSZEILE = re.compile(r"^(Stand: Version )\d+\.\d+\.\d+(\.)", re.MULTILINE)


def version_lesen() -> tuple[int, int, int]:
    """Liest die aktuelle Version aus version.txt. Fehlt die Datei (z.B. beim
    allerersten Build), wird mit 1.0.0 als Startpunkt begonnen."""
    if not VERSION_DATEI.exists():
        return (1, 0, 0)
    text = VERSION_DATEI.read_text(encoding="utf-8").strip()
    teile = text.split(".")
    if len(teile) != 3 or not all(t.isdigit() for t in teile):
        raise ValueError(f"Ungültige Versionsnummer in {VERSION_DATEI}: {text!r} (erwartet: X.Y.Z)")
    major, minor, patch = (int(t) for t in teile)
    return (major, minor, patch)


def naechste_version(aktuell: tuple[int, int, int]) -> tuple[int, int, int]:
    """Odometer-Logik: zuerst die 3. Stelle erhöhen; läuft sie über 99, auf 0
    zurücksetzen und die 2. Stelle erhöhen; läuft die dann über 99, ebenso die
    1. Stelle erhöhen."""
    major, minor, patch = aktuell
    patch += 1
    if patch > 99:
        patch = 0
        minor += 1
    if minor > 99:
        minor = 0
        major += 1
    return (major, minor, patch)


def version_info_schreiben(version: tuple[int, int, int]) -> None:
    major, minor, patch = version
    inhalt = f"""# UTF-8
#
# Windows-Versionsinformationen für PyInstaller (siehe build.spec, Parameter
# `version="version_info.txt"`). Diese Datei wird in die .exe eingebettet und
# taucht z.B. im Windows-Explorer unter "Eigenschaften -> Details" auf.
#
# WIRD AUTOMATISCH von bump_version.py erzeugt (aufgerufen aus
# build_installer.bat vor jedem Build) - bitte nicht mehr von Hand editieren,
# sonst geht die nächste automatische Erhöhung von der falschen Zahl aus.
# Die aktuell gültige Versionsnummer steht in version.txt.

VSVersionInfo(
  ffi=FixedFileInfo(
    # filevers/prodvers sind 4er-Tupel (Major, Minor, Patch, Build).
    filevers=({major}, {minor}, {patch}, 0),
    prodvers=({major}, {minor}, {patch}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,        # VOS_NT_WINDOWS32
    fileType=0x1,      # VFT_APP
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          "040704B0",  # 0407 = Deutsch, 04B0 = Unicode
          [
            StringStruct("CompanyName", "SHS Verein"),
            StringStruct("FileDescription", "SHS-Pruefungsprogramm - Verwaltung von Spuerhundsport-Pruefungen"),
            StringStruct("FileVersion", "{major}.{minor}.{patch}.0"),
            StringStruct("InternalName", "SHS-Pruefungsprogramm"),
            StringStruct("LegalCopyright", "SHS Verein"),
            StringStruct("OriginalFilename", "SHS-Pruefungsprogramm.exe"),
            StringStruct("ProductName", "SHS-Pruefungsprogramm"),
            StringStruct("ProductVersion", "{major}.{minor}.{patch}.0"),
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct("Translation", [1031, 1200])]),  # 1031 = Deutsch, 1200 = Unicode BMP
  ]
)
"""
    VERSION_INFO_DATEI.write_text(inhalt, encoding="utf-8")


def version_py_schreiben(version_text: str) -> None:
    """Schreibt die kleine, von app.py importierte version.py neu (siehe VERSION_PY_DATEI
    oben) - WIRD AUTOMATISCH erzeugt, bitte nicht von Hand editieren."""
    inhalt = (
        '"""WIRD AUTOMATISCH von bump_version.py erzeugt - bitte nicht von Hand editieren.\n'
        "Von app.py importiert, um die aktuell laufende Version anzuzeigen (siehe\n"
        'Version-Button neben "Hilfe")."""\n'
        f'VERSION = "{version_text}"\n'
    )
    VERSION_PY_DATEI.write_text(inhalt, encoding="utf-8")


def handbuch_version_schreiben(version_text: str) -> None:
    """Zieht die Zeile "Stand: Version X.Y.Z." im Handbuch auf die neue Version nach.

    Fehlt die Datei oder die Zeile, passiert bewusst nichts (kein Fehler, keine
    Ausgabe): build_installer.bat liest die Versionsnummer von stdout und darf
    dadurch nicht gestört werden. Andere Fehler (Datei schreibgeschützt/gesperrt,
    kein gültiges UTF-8) brechen dagegen laut ab - main() ruft diese Funktion
    deshalb als Erstes auf, damit dann noch keine Versionsdatei verändert ist.
    Zeilenenden bleiben erhalten (newline="")."""
    try:
        with HANDBUCH_DATEI.open(encoding="utf-8", newline="") as f:
            inhalt = f.read()
    except FileNotFoundError:
        return
    neu, anzahl = _HANDBUCH_VERSIONSZEILE.subn(rf"\g<1>{version_text}\g<2>", inhalt, count=1)
    if anzahl:
        with HANDBUCH_DATEI.open("w", encoding="utf-8", newline="") as f:
            f.write(neu)


def main() -> str:
    aktuell = version_lesen()
    neu = naechste_version(aktuell)
    neu_text = ".".join(str(n) for n in neu)
    # Zuerst das Handbuch: scheitert das (z. B. Datei gesperrt), ist noch nichts hochgezählt
    handbuch_version_schreiben(neu_text)
    VERSION_DATEI.write_text(neu_text + "\n", encoding="utf-8")
    version_info_schreiben(neu)
    version_py_schreiben(neu_text)
    return neu_text


if __name__ == "__main__":
    print(main())
