# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller-Spec für das SHS-Prüfungsprogramm.

Windows: baut EINE einzelne .exe (--onefile) aus app.py, inklusive PySide6 und
reportlab (für die PDF-Ausgabe, siehe pdf_export.py). Weil alles in einer Datei
steckt (PyInstaller packt Python, Qt und alle Abhängigkeiten hinein und entpackt sie
beim Start in einen Temp-Ordner), gibt es später im Installationsordner keine losen
DLLs oder Zusatzdateien, um die man sich bei einem Update kümmern müsste - ein Update
ist schlicht "die alte .exe durch die neue ersetzen" (siehe installer.iss).

macOS und Linux (Vorschau, Marco 07.10.2026): ein Programmordner statt einer einzelnen
Datei (startet schneller, kein Entpacken bei jedem Start). Unter macOS wird daraus die
App "SHS-Pruefungsprogramm.app", unter Linux der Ordner dist/SHS-Pruefungsprogramm/, aus
dem die CI (build-installer.yml) das AppImage und das .deb-Paket baut. Beide sind nicht
signiert; PyInstaller signiert die macOS-App nur "ad hoc", damit sie auf Apple-Silicon-
Macs überhaupt startet.

Verwendung (mit Python + den Paketen aus requirements.txt sowie zusätzlich
`pip install pyinstaller`):

    pyinstaller build.spec

Ergebnis: dist/SHS-Pruefungsprogramm.exe (Windows), dist/SHS-Pruefungsprogramm.app (macOS)
bzw. dist/SHS-Pruefungsprogramm/ (Linux)

Die Versionsnummer wird NICHT mehr von Hand gepflegt: bump_version.py erhoeht sie
automatisch (siehe dort) und schreibt sie in version_info.txt; build_installer.bat
ruft bump_version.py vor diesem Build automatisch auf und gibt dieselbe Nummer
anschliessend an installer.iss (MyAppVersion) weiter - siehe README_INSTALLER.md.
"""

import sys
from pathlib import Path

NAME = "SHS-Pruefungsprogramm"
WINDOWS = sys.platform == "win32"
MACOS = sys.platform == "darwin"
# SPECPATH: Ordner dieser Spec-Datei (von PyInstaller gesetzt), unabhängig vom Arbeitsordner.
VERSION = (Path(SPECPATH) / "version.txt").read_text(encoding="utf-8").strip()

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    # db.py/db_import.py/db_sicherung.py/shs_core.py/pdf_export.py sowie version.py
    # (siehe bump_version.py und der Version-Button neben "Hilfe" in app.py) werden
    # von app.py per "import" eingebunden
    # und daher von PyInstaller automatisch mit erkannt und eingepackt - keine weiteren
    # Einträge hier nötig.
    # Das Programmsymbol (Fenster/Dock/Taskleiste) liest desktop_gemeinsam.programmsymbol()
    # zur Laufzeit; der Selbsttest prüft, dass es im Bundle liegt.
    datas=[("symbol/programmsymbol.png", "symbol")],
    # pyzipper (Datensicherung, siehe db_sicherung.py) importiert pycryptodomex für die
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

if WINDOWS:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=NAME,
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
        icon="symbol/programmsymbol.ico",
        version="version_info.txt",
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,  # die CI baut je Mac-Typ auf dem passenden Runner
        codesign_identity=None,
        entitlements_file=None,
    )
    sammlung = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=NAME)
    if MACOS:
        app = BUNDLE(
            sammlung,
            name=f"{NAME}.app",
            icon="symbol/programmsymbol.icns",
            bundle_identifier="io.github.mbruver-source.shs",
            version=VERSION,
            info_plist={
                "CFBundleDisplayName": "SHS-Prüfungsprogramm",
                "CFBundleName": "SHS-Prüfungsprogramm",
                "CFBundleShortVersionString": VERSION,
                "CFBundleVersion": VERSION,
                "NSHighResolutionCapable": True,
                # Aktuelle PySide6-/Qt-Versionen setzen macOS 13 voraus; älter -> klare
                # Meldung von macOS statt Absturz beim Start.
                "LSMinimumSystemVersion": "13.0",
            },
        )
