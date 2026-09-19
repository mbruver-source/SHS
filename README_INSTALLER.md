# SHS-Prüfungsprogramm – Build & Release (Windows-Installer)

Diese Anleitung beschreibt, wie aus dem Python-Quellcode eine fertige
Windows-Installationsdatei (`SHS-Pruefungsprogramm-Setup-X.Y.Z.exe`) entsteht,
und wie sichergestellt wird, dass eine neue Version eine ältere automatisch
**aktualisiert** (statt danebenzuinstallieren oder eine manuelle
Deinstallation zu verlangen).

Die eigentliche Programmentwicklung läuft plattformunabhängig, der
Installer-Build (dieser Abschnitt) muss aber auf einem **Windows-Rechner**
erfolgen, weil PyInstaller eine Windows-.exe nur unter Windows erzeugen kann
und Inno Setup ein reines Windows-Werkzeug ist.

## Voraussetzungen (einmalig, auf dem Windows-Build-Rechner)

1. Python 3.11+ installiert.
2. Inno Setup installiert (kostenlos, <https://jrsoftware.org/isinfo.php>) –
   stellt den Befehl `ISCC.exe` (Inno Setup Compiler) bereit.
3. Im Projektordner:

   ```
   pip install -r requirements.txt
   pip install pyinstaller
   ```

## Ablauf für ein neues Release

Am einfachsten `build_installer.bat` ausführen – das Skript erledigt alle
Schritte unten automatisch, inklusive der Versionsnummer. Die folgende
Beschreibung ist für den Fall gedacht, dass die Schritte einmal von Hand
nachvollzogen werden müssen.

**Versionsnummer:** wird NICHT mehr von Hand eingetragen. `version.txt` ist
die alleinige Quelle der aktuellen Version (z. B. `1.0.5`). Bei jedem Build
erhöht `bump_version.py` automatisch die 3. Stelle (Patch) um 1 – erreicht
sie 99, beginnt sie wieder bei 0 und die 2. Stelle (Minor) wird um 1 erhöht
(und so weiter, sinngemäß auch für die 1. Stelle). `bump_version.py`
schreibt die neue Nummer sowohl in `version.txt` als auch in
`version_info.txt`; `build_installer.bat` liest sie danach aus und gibt sie
unverändert an Inno Setup weiter, sodass überall (Datei „Eigenschaften“ der
.exe, Installer-Dateiname, Windows-Systemsteuerung) dieselbe Nummer steht.
Manuell ausgeführt wird sie mit:

```
python bump_version.py
```

(gibt die neue Versionsnummer aus und schreibt die beiden Dateien).

1. **Versionsnummer erhöhen** (siehe oben – bei `build_installer.bat`
   automatisch Schritt 2/4):

   ```
   python bump_version.py
   ```

2. **Die .exe bauen** (PyInstaller, `--onefile`, siehe `build.spec`):

   ```
   pyinstaller build.spec
   ```

   Ergebnis: `dist\SHS-Pruefungsprogramm.exe` – eine einzelne Datei, die
   Python, PySide6, reportlab und den gesamten Quellcode enthält. Kurz
   testen, ob sie startet, bevor der Installer gebaut wird. **Wichtig:**
   Schritt 1 muss vorher gelaufen sein, damit die neue Versionsnummer schon
   in `version_info.txt` steht, wenn PyInstaller sie einbettet.

3. **Den Installer bauen** (Inno Setup), mit der in Schritt 1 erzeugten
   Versionsnummer (hier als Beispiel `1.1.0`):

   ```
   ISCC installer.iss /DMyAppVersion=1.1.0
   ```

   Ergebnis: `Output\SHS-Pruefungsprogramm-Setup-1.1.0.exe` – das ist die
   Datei, die an den Verein/die Nutzer weitergegeben wird.

## Warum ein Update automatisch funktioniert

- `installer.iss` verwendet eine **feste `AppId` (GUID)**, die sich mit
  jeder Version NIE ändert. Windows/Inno Setup erkennt eine vorhandene
  Installation ausschließlich über diese Id – nicht über den Namen oder die
  Versionsnummer. Läuft der neue Installer, findet er dieselbe Id wieder,
  behandelt die Installation also als Update derselben Anwendung und
  überschreibt sie an Ort und Stelle.
- Der Installationsordner (`DefaultDirName`) leitet sich ebenfalls von dieser
  festen Id ab, landet also bei jeder Version am selben Ort.
- Die App wird als **eine einzige .exe** (`--onefile`) gebaut – es gibt keine
  losen DLL- oder Zusatzdateien im Installationsordner, um die man sich beim
  Update kümmern müsste. Ein Update ist schlicht "alte .exe durch neue
  ersetzen".
- Ist die Anwendung beim Update gerade geöffnet, fordert der Installer
  (`CloseApplications=force`) automatisch zum Schließen auf und startet sie
  nach der Installation auf Wunsch wieder (`RestartApplications=yes`) – der
  Nutzer muss sie nicht selbst beenden.

**Wichtig:** Die `AppId` in `installer.iss` (`#define AppId ...`) darf bei
zukünftigen Releases **niemals verändert werden**. Nur die `AppVersion`
(Schritt 3 oben) ändert sich von Release zu Release.

## Nutzerdaten (Termine) sind von Updates/Deinstallation nicht betroffen

Die vom Verein angelegten Prüfungstermine (SQLite-Dateien) werden bewusst
**nicht** im Installationsordner gespeichert, sondern im Benutzerprofil unter:

```
%USERPROFILE%\SHS-Pruefungsprogramm\Termine
```

(siehe `db.py`, Funktion `termine_ordner()`). Der Installer installiert,
aktualisiert und deinstalliert ausschließlich den Programmordner – dieser
Termine-Ordner bleibt bei jeder dieser Aktionen unangetastet. Ein Update
"sieht" also weiterhin alle bisherigen Prüfungstermine, ohne dass dafür im
Installer irgendetwas Besonderes nötig wäre.

## Windows-SmartScreen-Warnung beim ersten Start

Da die Setup-Datei nicht signiert ist (siehe unten, warum das hier bewusst so
bleibt), zeigt Windows beim allerersten Start auf einem Rechner die
SmartScreen-Meldung "Windows hat den Start dieser App verhindert" bzw.
"Unbekannter Herausgeber". Das ist normal für neu gebaute, unsignierte
.exe-Dateien und kein Hinweis auf ein Problem mit dem Programm.

**So geht es weiter:** Auf der Warnmeldung auf "Weitere Informationen"
klicken, dann erscheint der Button "Trotzdem ausführen". Das ist nur beim
ersten Start auf einem Rechner nötig – bei jedem weiteren Start (auch nach
einem Update) erscheint die Meldung auf demselben Rechner nicht erneut.

**Warum unsigniert bleibt:** Eine Signatur, die diese Meldung zuverlässig
verhindert, würde eine laufende Kosten- bzw. Aufwandsverpflichtung bedeuten
(z. B. Azure Artifact Signing ab ca. 10 $/Monat, ein klassisches
Code-Signing-Zertifikat ab ca. 150 $/Jahr) oder – bei der kostenlosen
SignPath-Foundation-Option – eine Offenlegung des kompletten Quellcodes unter
einer Open-Source-Lizenz plus Umstellung des Builds auf eine automatisierte
CI/CD-Pipeline (z. B. GitHub Actions statt `build_installer.bat` auf dem
eigenen PC). Für ein vereinsintern verteiltes Tool mit wenigen Nutzern steht
der Aufwand dazu in keinem Verhältnis zum Nutzen – der einmalige Klick auf
"Trotzdem ausführen" ist der pragmatischere Weg. Falls sich das je ändert
(z. B. größere Verbreitung, Wunsch nach Open Source), lässt sich eine der
beiden Optionen jederzeit nachrüsten.

**Beim Weitergeben der Setup-Datei an neue Nutzer:** kurz auf diesen
Klick hinweisen, damit niemand die Installation deswegen abbricht.

## Installer automatisch über GitHub Actions bauen (Alternative zu lokal)

Seit der Umstellung auf ein GitHub-Repo gibt es neben dem lokalen Build über
`build_installer.bat` auch einen automatisierten Weg: der Workflow
`.github/workflows/build-installer.yml` baut denselben Installer auf einem
GitHub-Windows-Runner – nützlich, wenn gerade kein Windows-Rechner zur Hand
ist, oder um den Build-Schritt nicht mehr manuell erledigen zu müssen.

**Wichtiger Unterschied zum lokalen Build:** Der Workflow ruft
`bump_version.py` NICHT selbst auf, sondern baut mit der Nummer, die schon in
`version.txt` eingecheckt ist. Ablauf für ein Release darüber:

1. Lokal einmal `python bump_version.py` ausführen (oder die Zahl von Hand in
   `version.txt` setzen).
2. Die geänderten `version.txt`/`version_info.txt` committen und pushen.
3. Einen Versions-Tag setzen und pushen:

   ```
   git tag v1.2.0
   git push origin v1.2.0
   ```

   Das löst den Workflow automatisch aus, baut die Setup-Datei und veröffentlicht
   sie als GitHub Release (Reiter „Releases" im Repo) inklusive automatisch
   erzeugter Release-Notes.

Zum reinen Testen, ohne gleich ein Release zu erzeugen, lässt sich derselbe
Workflow auch manuell anstoßen: Im Repo unter „Actions" → „Installer bauen" →
„Run workflow". Das Ergebnis liegt dann als herunterladbares Artefakt am
Workflow-Lauf, ohne dass ein Release entsteht.

Die Kurz-Checkliste unten gilt für beide Wege – bei einem Actions-Build sind
Schritt 2 und 3 (PyInstaller/Inno Setup) bereits durch den Workflow erledigt,
Testinstallation und Versionsdisziplin bleiben aber genauso wichtig.

**Derselbe Versions-Tag löst zusätzlich einen zweiten Workflow aus:**
`.github/workflows/build-container.yml` baut bei jedem `vX.Y.Z`-Tag auch das
Container-Image der Web-Version und veröffentlicht es nach `ghcr.io` – mit
genau derselben Versionsnummer aus `version.txt`. Ein einziger Tag-Push
versorgt damit sowohl den Windows-Installer als auch das Container-Image mit
derselben Version. Details siehe `README_CONTAINER.md`.

## Kurz-Checkliste pro Release

- [ ] `bump_version.py` gelaufen (automatisch über `build_installer.bat`,
      oder von Hand) – neue Nummer steht in `version.txt`/`version_info.txt`
- [ ] `pyinstaller build.spec` erfolgreich, `dist\SHS-Pruefungsprogramm.exe`
      kurz angetestet
- [ ] `ISCC installer.iss /DMyAppVersion=X.Y.Z` erfolgreich
- [ ] Setup-Datei auf einem Testrechner mit vorheriger Version installiert
      und geprüft, dass (a) die neue Version läuft und (b) vorhandene
      Termine-Dateien weiterhin sichtbar sind
- [ ] `AppId` in `installer.iss` **nicht** verändert
