@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo  SHS-Pruefungsprogramm - Installer-Build
echo ============================================================
echo.

rem --- Python finden -----------------------------------------------------
set "PY="
where python >nul 2>nul
if not errorlevel 1 (
    set "PY=python"
) else (
    where py >nul 2>nul
    if not errorlevel 1 (
        set "PY=py"
    )
)

if "%PY%"=="" (
    echo Python wurde in diesem Fenster nicht gefunden.
    echo.
    echo Bitte dieses Skript stattdessen aus einem "Anaconda PowerShell Prompt"
    echo oder "Anaconda Prompt" heraus starten ^(Windows-Startmenue -^> "Anaconda
    echo PowerShell Prompt" oeffnen, dann mit "cd" in diesen Ordner wechseln und
    echo build_installer.bat eingeben^), oder Python von https://python.org
    echo installieren und dabei "Add python.exe to PATH" aktivieren.
    goto :fehler
)

echo Verwende Python: %PY%
%PY% --version
echo.

echo [1/4] Python-Pakete installieren ^(PySide6, reportlab, PyInstaller^)...
%PY% -m pip install -r requirements.txt
if errorlevel 1 goto :fehler
%PY% -m pip install pyinstaller
if errorlevel 1 goto :fehler
echo.

echo [2/4] Versionsnummer erhoehen ^(bump_version.py^)...
rem Erhoeht automatisch die 3. Stelle der Versionsnummer (bis 99), danach die
rem 2. Stelle (und setzt die 3. wieder auf 0) - siehe bump_version.py fuer die
rem genaue Logik. Schreibt version.txt, version_info.txt und version.py neu
rem und zieht die Stand-Zeile in docs\HANDBUCH.md nach (das PDF-Handbuch danach
rem von Hand mit "python tools\handbuch_pdf.py" neu erzeugen); die neue
rem Nummer wird unten sowohl fuer den Fenster-/Dateinamen als auch fuer Inno
rem Setup (/DMyAppVersion) verwendet, damit ueberall dieselbe Nummer steht.
set "VERSION="
for /f "delims=" %%V in ('%PY% bump_version.py') do set "VERSION=%%V"
if "%VERSION%"=="" (
    echo Versionsnummer konnte nicht ermittelt werden ^(bump_version.py fehlgeschlagen^).
    goto :fehler
)
echo   -^> Neue Version: %VERSION%
echo   Hinweis: docs\HANDBUCH.pdf mit "python tools\handbuch_pdf.py" neu erzeugen.
echo.

echo [3/4] .exe bauen ^(PyInstaller, --onefile^)...
rem --clean verwirft den PyInstaller-Zwischenspeicher (Ordner "build") komplett und
rem baut alle Module frisch aus den aktuellen .py-Dateien - ohne --clean kommt es
rem vor, dass eine geaenderte Datei wie pdf_export.py NICHT neu eingepackt wird und
rem die alte, alte Version in der .exe landet ^(genau das war die Ursache, wenn die
rem App "no attribute ..." meldet, obwohl die Quelldatei die Funktion laengst hat^).
rem Wichtig: bump_version.py (Schritt 2) muss VOR diesem Schritt laufen, damit die
rem neue Versionsnummer bereits in version_info.txt steht, wenn PyInstaller sie
rem in die .exe einbettet.
%PY% -m PyInstaller --noconfirm --clean build.spec
if errorlevel 1 goto :fehler
echo.
echo   -^> dist\SHS-Pruefungsprogramm.exe wurde erstellt.
echo.

echo [4/4] Installer bauen ^(Inno Setup^)...
rem ISCC.exe wird von Inno Setup NICHT automatisch zum PATH hinzugefuegt -
rem "where ISCC" findet es daher meistens nicht, auch wenn es installiert ist.
rem Deshalb zusaetzlich an den ueblichen Installationsorten suchen.
set "ISCC="
where ISCC >nul 2>nul
if not errorlevel 1 (
    set "ISCC=ISCC"
) else (
    for %%C in (
        "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
        "%ProgramFiles%\Inno Setup 6\ISCC.exe"
        "%ProgramFiles(x86)%\Inno Setup 5\ISCC.exe"
        "%ProgramFiles%\Inno Setup 5\ISCC.exe"
        "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
    ) do (
        if exist %%C if "!ISCC!"=="" set "ISCC=%%~C"
    )
)

if "%ISCC%"=="" (
    echo.
    echo Inno Setup ^(ISCC.exe^) wurde weder im PATH noch an den ueblichen
    echo Installationsorten gefunden. Falls es installiert ist, aber woanders
    echo liegt: dieses Skript oeffnen und in der Zeile mit "for %%%%C in (..."
    echo den tatsaechlichen Pfad zu ISCC.exe ergaenzen - oder einfach direkt
    echo in der Kommandozeile ausfuehren:
    echo     "^<Pfad-zu^>\ISCC.exe" installer.iss /DMyAppVersion=%VERSION%
    echo Falls es NICHT installiert ist: https://jrsoftware.org/isinfo.php
    goto :fehler
)

echo Verwende Inno Setup Compiler: %ISCC%
"%ISCC%" installer.iss /DMyAppVersion=%VERSION%
if errorlevel 1 goto :fehler

echo.
echo ============================================================
echo  FERTIG!
echo  Der fertige Installer liegt hier:
echo  %~dp0Output\SHS-Pruefungsprogramm-Setup-%VERSION%.exe
echo ============================================================
pause
exit /b 0

:fehler
echo.
echo ------------------------------------------------------------
echo  Beim Build ist ein Fehler aufgetreten ^(siehe Meldungen oben^).
echo  Alternativ: die Schritte einzeln aus README_INSTALLER.md von
echo  Hand ausfuehren.
echo ------------------------------------------------------------
pause
exit /b 1
