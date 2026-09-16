; Inno Setup Script für das SHS-Prüfungsprogramm
; ================================================
;
; Baut einen Windows-Installer, der auch UPDATES kann: wird der Installer für
; eine neuere Version über eine bestehende Installation laufen gelassen,
; erkennt Windows/Inno Setup automatisch "das ist ein Update dieser Anwendung"
; und ersetzt die alte Installation, statt eine zweite parallel anzulegen
; oder eine manuelle Deinstallation zu verlangen.
;
; Das funktioniert über zwei Dinge, die NIEMALS geändert werden dürfen:
;   1. #AppId - eine feste GUID, die die Anwendung eindeutig identifiziert.
;      Inno Setup erkennt eine bestehende Installation ausschließlich über
;      diese Id (nicht über den Namen). Ändert sich die Id, hält Windows es
;      für eine ANDERE Anwendung und installiert daneben - genau das wollen
;      wir vermeiden.
;   2. DefaultDirName, das auf {#AppId} statt auf den (ggf. wechselnden)
;      Anzeigenamen aufbaut - dadurch landet jede Version im selben Ordner
;      und eine neue .exe überschreibt beim Update einfach die alte.
;
; Die Versionsnummer (#MyAppVersion) wird bei jedem Release NEU gesetzt und
; beim Kompilieren übergeben:
;
;     ISCC installer.iss /DMyAppVersion=1.1.0
;
; (Ohne /DMyAppVersion greift der Default weiter unten.) Sie muss zur
; FileVersion/ProductVersion in version_info.txt passen - siehe
; README_INSTALLER.md.
;
; TERMINE-DATEN SIND VON UPDATES NICHT BETROFFEN:
; Die vom Nutzer angelegten Termine (SQLite-Dateien) liegen bewusst NICHT im
; Installationsordner, sondern im Benutzerprofil unter
; "%USERPROFILE%\SHS-Pruefungsprogramm\Termine" (siehe db.py, Funktion
; termine_ordner()). Der Installer deinstalliert/überschreibt ausschließlich
; den Programmordner unter {app} - der Termine-Ordner im Benutzerprofil wird
; davon nie berührt, egal ob es sich um eine Neuinstallation, ein Update oder
; eine Deinstallation handelt.

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

#define MyAppName "SHS-Pruefungsprogramm"
#define MyAppPublisher "SHS Verein"
#define MyAppExeName "SHS-Pruefungsprogramm.exe"
; Feste, für immer gleichbleibende Kennung dieser Anwendung - NIEMALS ändern!
; (Neu erzeugt z.B. mit Inno Setup: Menü "Tools -> Generate GUID".)
#define AppId "{{8F2C1E4A-3B7D-4E6F-9A1C-5D8E2F0B6C4A}"

[Setup]
AppId={#AppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Baut auf der festen AppId auf statt auf dem Namen -> bleibt über alle
; Versionen hinweg derselbe Ordner, damit ein Update wirklich "update" ist.
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Einzelne, portable Installer-Datei (kein separates Setup-Verzeichnis nötig).
OutputBaseFilename=SHS-Pruefungsprogramm-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; Deinstallations-Einträge tragen ebenfalls die AppVersion, damit man in der
; Windows-Systemsteuerung sieht, welche Version installiert ist.
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
; Kein Admin-Zwang nötig, da nur in den Nutzer-eigenen "Programme"-Ordner
; installiert wird (autopf löst je nach Rechten automatisch passend auf).
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Läuft das Setup über eine bereits gestartete alte/neue Version, fordert
; Inno Setup (ab Version 6) automatisch zum Schließen auf und kann die
; Anwendung danach wieder automatisch starten - wichtig für ein reibungsloses
; Update, ohne dass der Nutzer die Anwendung erst selbst beenden muss.
CloseApplications=force
RestartApplications=yes

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknüpfung anlegen"; GroupDescription: "Zusätzliche Symbole:"

[Files]
; --onefile-Build aus build.spec: genau eine .exe, keine losen Zusatzdateien -
; das ist es, was ein Update so einfach macht (eine Datei ersetzt die andere).
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} jetzt starten"; Flags: nowait postinstall skipifsilent

; Hinweis zur Deinstallation: Ein "Deinstallieren" über die Systemsteuerung
; entfernt nur die Programmdateien unter {app}. Die Termine-Dateien im
; Benutzerprofil (%USERPROFILE%\SHS-Pruefungsprogramm\Termine) bleiben
; erhalten, damit sie bei einer Neuinstallation/einem Update sofort wieder
; zur Verfügung stehen. Es wird bewusst KEIN [UninstallDelete]-Eintrag für
; diesen Ordner angelegt.
