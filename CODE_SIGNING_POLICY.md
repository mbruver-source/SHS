# Code Signing Policy – SHS-Prüfungsprogramm

Diese Richtlinie beschreibt, wer im Projekt [SHS-Prüfungsprogramm](https://github.com/mbruver-source/SHS)
Code verändern, prüfen und Releases freigeben darf, sowie den Bau- und
Signierungsprozess der ausgelieferten Windows-Installationsdatei. Sie dient als
Grundlage für die kostenlose Codesignierung über die
[SignPath Foundation](https://signpath.org/) (Zertifikat) und
[SignPath.io](https://signpath.io/) (Signierungsplattform).

## Über das Projekt

SHS-Prüfungsprogramm verwaltet Prüfungstermine, Teilnehmer und Ergebnisse für
Spürhundsport-Prüfungen eines einzelnen Vereins. Quellcode und Historie sind
öffentlich unter der [MIT-Lizenz](LICENSE) einsehbar; eine allgemeine
Projektbeschreibung steht in [README.md](README.md) und
[Grobkonzept.md](Grobkonzept.md).

## Rollen

| Rolle | Person(en) | Aufgabe |
|---|---|---|
| Author | Marco ([mbruver-source](https://github.com/mbruver-source)) | Schreibt und committet den Code. Aktuell der einzige aktive Entwickler des Projekts. |
| Reviewer | Marco | Prüft Änderungen vor der Übernahme – bislang gibt es keine externen Mitwirkenden. Pull Requests von Dritten werden nicht angenommen (siehe [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md)); externe Beiträge laufen über Issues und werden von Marco selbst umgesetzt. |
| Approver | Marco | Einzige Person, die Versions-Tags setzt und damit einen signierten Release-Build auslöst. |

Sobald das Projekt weitere regelmäßige Mitwirkende hat, wird diese Tabelle um
die entsprechenden Personen und eine klare Trennung der Rollen ergänzt.

Für den Zugriff auf sowohl das GitHub-Repository als auch das SignPath-Konto
ist Zwei-Faktor-Authentifizierung (MFA) aktiviert bzw. wird vor der ersten
Signierungs-Freigabe aktiviert.

## Build- und Freigabeprozess

- **Quelle der Wahrheit:** ausschließlich das öffentliche GitHub-Repository
  <https://github.com/mbruver-source/SHS>, Branch `main`.
- **Build:** Der Windows-Installer wird ausschließlich automatisiert über den
  öffentlich einsehbaren GitHub-Actions-Workflow
  [`.github/workflows/build-installer.yml`](.github/workflows/build-installer.yml)
  gebaut (PyInstaller + Inno Setup) – nicht von Hand auf einem privaten
  Rechner. Ausgelöst wird ein Release-Build durch einen Versions-Tag
  (`vX.Y.Z`), den ausschließlich der Approver (siehe oben) setzt.
- **Versionierung:** Vor jedem Release wird die Versionsnummer konsistent in
  `version.txt`/`version_info.txt`/`version.py` aktualisiert (siehe
  `bump_version.py`), sodass Produktname und Versionsnummer im signierten
  Artefakt korrekt und über Installer und Programm hinweg einheitlich sind.
- **Signiertes Artefakt:** die vom Workflow erzeugte Setup-Datei
  `SHS-Pruefungsprogramm-Setup-X.Y.Z.exe`, veröffentlicht als GitHub Release.
  Es wird ausschließlich Code aus diesem Repository signiert, keine
  Fremdbinärdateien.

## Datenschutz

- Das Programm läuft rein lokal auf dem Rechner des Nutzers bzw. – in der
  optionalen Web-Version, siehe [README_CONTAINER.md](README_CONTAINER.md) –
  im lokalen Netzwerk des Vereins. Es sammelt keine Telemetrie- oder
  Nutzungsdaten und sendet keine Daten an Dritte oder an den Entwickler.
- Verarbeitet werden ausschließlich vom Verein selbst eingegebene
  Prüfungsdaten (Teilnehmer, Ergebnisse), gespeichert lokal in einer
  SQLite-Datei im Benutzerprofil
  (`%USERPROFILE%\SHS-Pruefungsprogramm\Termine`, siehe
  [README_INSTALLER.md](README_INSTALLER.md)).
- Bei der optionalen Web-Version verbleiben alle Daten innerhalb des selbst
  betriebenen PostgreSQL-Containers im Vereinsnetz; es besteht keine
  Internet-Erreichbarkeit von außen (siehe README_CONTAINER.md).

## Deinstallation

Der Installer (Inno Setup) bietet eine vollständige Deinstallation über die
Windows-Systemsteuerung. Vom Verein angelegte Prüfungstermine bleiben dabei
bewusst erhalten (siehe README_INSTALLER.md) und können bei Bedarf manuell
gelöscht werden.

## Hinweis zur Signierung

Free code signing provided by SignPath.io, certificate by SignPath Foundation.

## Kontakt

Marco – [m.bruver@gmail.com](mailto:m.bruver@gmail.com) – GitHub:
[mbruver-source](https://github.com/mbruver-source)
