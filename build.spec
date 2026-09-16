# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller-Spec für das SHS-Prüfungsprogramm.

Baut EINE einzelne Windows-.exe (--onefile) aus app.py, inklusive PySide6 und
reportlab (für die PDF-Ausgabe, siehe pdf_export.py). Weil alles in einer Datei
steckt (PyInstaller packt Python, Qt und alle Abhängigkeiten hinein und entpackt sie
beim Start in einen Temp-Ordner), gibt es später im Installationsordner keine losen
DLLs oder Zusatzdateien, um die man sich bei einem Update kümmern müsste - ein Update
ist schlicht "die alte .exe durch die neue ersetzen" (siehe installer.iss).

Verwendung (in einer normalen Windows-Umgebung mit Python + den Paketen aus
requirements.txt sowie zusätzlich `pip install pyinstaller`):

    pyinstaller build.spec

Ergebnis: dist/SHS-Pruefungsprogramm.exe

Die Versionsnummer wird NICHT mehr von Hand gepflegt: bump_version.py erhoeht sie
automatisch (siehe dort) und schreibt sie in version_info.txt; build_installer.bat
ruft bump_version.py vor diesem Build automatisch auf und gibt dieselbe Nummer
anschliessend an installer.iss (MyAppVersion) weiter - siehe README_INSTALLER.md.
"""

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    # db.py/shs_core.py/pdf_export.py sowie version.py (siehe bump_version.py und der
    # Version-Button neben "Hilfe" in app.py) werden von app.py per "import" eingebunden
    # und daher von PyInstaller automatisch mit erkannt und eingepackt - keine weiteren
    # Einträge hier nötig.
    datas=[],
    # pyzipper (Datensicherung, siehe db.py) importiert pycryptodomex für die
    # AES-Verschlüsselung - PyInstaller bringt dafür über pyinstaller-hooks-contrib
    # normalerweise einen eigenen Hook mit und erkennt es automatisch wie reportlab;
    # falls ein Build dennoch mit einem ModuleNotFoundError für Cryptodome/pyzipper
    # fehlschlägt, hier "pyzipper" bzw. "Cryptodome" eintragen.
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SHS-Pruefungsprogramm",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # keine Konsole im Hintergrund - reine GUI-Anwendung
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # optional: Pfad zu einer eigenen .ico-Datei eintragen
    version="version_info.txt",
)
