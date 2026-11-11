# Prüfer 3 – Build, CI und Lieferkette

## Zusammenfassung (schwerster Fund zuerst)
Keine kritischen oder hohen Funde. Die Workflows sind unauffällig (kein `pull_request_target`, kein `${{ }}` mit nutzerkontrollierten Werten außer dem Tag-Namen). Hauptrisiko ist die Lieferkette beim Release-Build. Der Build-Job hat Schreibrechte (`contents: write`), nutzt Actions nur mit beweglichen Tags und installiert unfixierte Abhängigkeiten. Der neue Selbsttest- und Installationsschritt ist unkritisch.

## Funde

### P3-1: Release-Job mit Schreibrecht, Actions ohne Commit-Hash, Pakete ohne Hash/Lockfile
- Schwere: mittel (Lieferketten-Risiko; Auswirkung = manipulierte Setup-.exe im Release)
- Stelle: `.github/workflows/build-installer.yml:28-30` (permissions), `:36,:39,:109,:117` (`actions/checkout@v4`, `setup-python@v5`, `upload-artifact@v4`, `softprops/action-gh-release@v2`), `:46-48` (`pip install -r requirements.txt`, `pip install pyinstaller` ohne Version), `:98` (`choco install innosetup -y` ohne Version). Ebenso `build-container.yml:121-136` (docker/*-Actions, `packages: write` auf Workflow-Ebene).
- Voraussetzungen und Szenario: Ein kompromittierter Action-Tag (insbesondere die Drittanbieter-Action `softprops/action-gh-release`), ein bösartiges Update von PyInstaller, einer Abhängigkeit oder des choco-Pakets. Der Code läuft dann im selben Job, der das Release schreiben darf und die .exe baut.
- Lokal nachvollzogen: nein (reine Konfigurationsprüfung).
- Auswirkung: Vereinsrechner installieren die .exe aus dem Release. Der Installer ist nicht signiert (bewusst akzeptiert), daher gibt es keine zweite Prüfinstanz.
- Empfehlung:
  - Drittanbieter-Actions auf Commit-Hash pinnen (Dependabot für Actions).
  - `permissions` auf Job-Ebene setzen: Build-Job `contents: read`, ein getrennter Release-Job mit `contents: write`.
  - PyInstaller-Version festlegen (z. B. `pyinstaller==x.y.z`). Optional ein Constraints-/Lockfile mit Hashes für den Release-Build.
  - Im Container-Workflow `packages: write` nur im `publish`-Job setzen.

### P3-2: Tag-Name direkt in PowerShell-Skript eingesetzt
- Schwere: gering
- Stelle: `build-installer.yml:69` und `:72` (`"${{ github.ref_name }}"` in einem doppelt gequoteten pwsh-String)
- Voraussetzungen und Szenario: Wer einen Tag `v...` pushen darf (Schreibrecht), kann einen Tag-Namen wie `v$(Befehl)` wählen. PowerShell wertet `$(...)` im doppelt gequoteten String aus. Der Workflow läuft dann mit Schreibtoken und hat die Release-Rechte.
- Lokal nachvollzogen: nein. Das Muster ist bekannt, und die Rechte-Voraussetzung macht es für ein Einzelmaintainer-Repo praktisch irrelevant.
- Auswirkung: Codeausführung im Runner durch jemanden, der ohnehin Schreibrecht hat.
- Empfehlung: Den Wert über `env:` übergeben (`$env:REF_NAME`) statt `${{ }}` im Skript. Dasselbe für `steps.version.outputs.version` (stammt aus `version.txt`, ebenfalls Repo-Inhalt) in `:72` und `:96`/`ISCC`-Aufruf. In `build-container.yml:106` ist es dasselbe Muster, dort aber in bash mit Einfachquotes, daher unkritisch.

### P3-3: Datenbank-Zugangsdaten (DSN) als Kommandozeilenargument in `sync_termin.py`
- Schwere: gering
- Stelle: `sync_termin.py:21-30` (Doku), `--dsn` in `main()`; Beispiele in der Doku mit `user:pass@host`
- Voraussetzungen und Szenario: Auf einem Rechner mit mehreren Benutzern oder Prozessansicht sind Argumente für andere sichtbar, und sie landen in der Shell-Historie. Die Umgebungsvariable `SHS_POSTGRES_DSN` wird bereits unterstützt.
- Lokal nachvollzogen: ja, durch Code-Lektüre. Die Datei enthält sonst keine Auffälligkeiten: kein `eval`, keine SQL-Zusammensetzung im Skript, die Schema-Namen-Validierung liegt in `db.py` (Bereich anderer Prüfer). Der DB-Port ist in `compose.yaml` nur an `127.0.0.1` gebunden.
- Auswirkung: Preisgabe des DB-Passworts an lokale Mitnutzer.
- Empfehlung: In der Doku die Umgebungsvariable als Standardweg nennen, `--dsn` mit Passwort als nicht empfohlen kennzeichnen.

### P3-4: `CloseApplications=force` im Installer
- Schwere: Hinweis
- Stelle: `installer.iss`, `[Setup]` (`CloseApplications=force`, `RestartApplications=yes`)
- Szenario: Beim Update wird die laufende App ohne Rückfrage beendet. Nicht sicherheitsrelevant, aber Datenverlust ist möglich, wenn gerade ein Termin offen ist (SQLite-Änderungen sind jedoch sofort committet, Einschätzung ohne Gewähr).
- Empfehlung: Bei Bedarf `CloseApplications=yes` (mit Rückfrage).

### P3-5: Testdaten-Ausnahme in `.gitignore` und Altversionen-Erzeugung
- Schwere: Hinweis
- Stelle: `.gitignore` (`!testdaten/altversionen/*/termin.sqlite`), `tools/altdaten_erzeugen.py`
- Befund: Die Ausnahme ist eng gefasst (nur `termin.sqlite` in Unterordnern von `altversionen`), der Rest von `*.sqlite` bleibt ignoriert. Inhalt: erfundene Daten ("Altdaten-Testverein", Chip-Nr. `2760000...`, `a@example.org`). Das Testpasswort `Altdaten-Test-1` steht bewusst im Quelltext (nur für Testsicherungen). Das Skript ruft `git` und `tar` ohne Shell (Liste, `shell=False`) auf. Die Tag-Namen kommen aus fester Liste bzw. Kommandozeile des Entwicklers. Der Tag steht vor `--` fehlt: ein Argument wie `--output=...` könnte als Option an `git archive` gehen, aber nur durch den Entwickler selbst aufgerufen, daher irrelevant. Gefahr: `*.zip` ist nicht ignoriert, versehentlich eingecheckte echte Sicherungen wären möglich (kleines Hygiene-Risiko).
- Empfehlung: Optional `*.zip` in `.gitignore` mit Ausnahme für `testdaten/altversionen/**`.

## Ohne Befund geprüft (Stichworte)
- Workflow-Auslöser: nur `push`, `pull_request`, Tags `v*`, `workflow_dispatch`; kein `pull_request_target`.
- `tests.yml`: `permissions` nicht gesetzt (Standard-Token), Zugangsdaten sind reine Test-Werte (`shs_test`, `smoketest`), kein Geheimnis; Postgres-Port nur im Runner.
- Fork-PRs: `GITHUB_TOKEN` ist dort schreibgeschützt; die Geheimnisse `secrets.GITHUB_TOKEN` werden nur im `publish`-Job nach Tag genutzt.
- Selbsttest- und Installationsschritt: Installation `/CURRENTUSER` in `RUNNER_TEMP`, Deinstallation danach, Pfade nicht von außen steuerbar. Ein fehlgeschlagener Selbsttest bricht den Build (nach der Deinstallation) korrekt ab.
- Tag-gegen-`version.txt`-Prüfung vorhanden (Release kann nicht mit falscher Nummer entstehen).
- `installer.iss`: `PrivilegesRequired=lowest`, `{autopf}` (ohne Adminrechte = Benutzerprofil, nicht von anderen beschreibbar; bei Admin-Override Program Files, geschützt). Nur eine Datei, Deinstallation über Standard-Uninstaller, einziger `[Run]`-Eintrag ist der optionale Programmstart (`postinstall skipifsilent`) ohne erhöhte Rechte. Keine festen Pfade außerhalb von `{app}`.
- `requirements*.txt`: Obergrenzen je Major gesetzt, `pypdf>=6.10` mit begründeter Untergrenze; keine Git- oder URL-Abhängigkeiten.
- `build.spec`, `build_installer.bat`, `bump_version.py`: keine Befehlsinjektion; `bump_version.py` schreibt nur feste Dateien und ersetzt per Regex nur die Versionszeile im Handbuch.
- Repo-Hygiene: keine Schlüssel/Tokens gefunden (Muster `AKIA`, `ghp_`, private Schlüssel, Passwortzuweisungen); `.env` ist ignoriert, nur `.env.example` eingecheckt. `docs/beispiel_teilnehmer.csv` und die Persona-/Test-Dateien nutzen `example.org`, "Musterstraße" und Fantasie-Chipnummern (`99900...`). Echte E-Mail-Adressen stehen nur beim Eigentümer selbst (Kontakt/Impressum/Attribution, bewusst öffentlich).
- `testdaten/altversionen/*/sicherung.zip`: enthält nur `termin.sqlite` mit erfundenen Daten.
- `compose.yaml`: DB-Port nur auf `127.0.0.1`, Pflichtvariablen mit `:?`.
- `docs/behaeltnisse/vendor/` (three.js) lizenziert mitgeliefert; nicht auf Aktualität/bekannte CVEs geprüft (nur statische Seite).

## Anzahl Funde je Schwere
kritisch 0, hoch 0, mittel 1, gering 2, Hinweis 2.

Bericht: `C:\Users\mbruv\AppData\Local\Temp\claude\C--Users-mbruv-Documents-SHS-Pruefungsprogramm-Git\747ba2e2-5ac7-4459-b68f-11f18f9c2c8a\scratchpad\sicherheit\pruefer3_build.md`
