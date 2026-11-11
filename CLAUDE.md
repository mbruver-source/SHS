# SHS-Prüfungsprogramm - Hinweise für Claude-Sitzungen

Verwaltungssoftware für Spürhundsport-Prüfungen (SHS) eines Vereins. Bevor du hier arbeitest:

- **Sprache und Umgebung:** Antworten, Commit-Nachrichten und Dokumentation auf Deutsch.
  Commit-Nachrichten sind kurze Beschreibungen ohne Präfix (Beispiel: "Zeitplan bei grosser
  Schrift nicht mehr abgeschnitten"). Hauptshell ist PowerShell unter Windows; Bash nur für
  POSIX-Skripte.
- **Architekturüberblick (mit Diagramm):** `Architektur.md` - lies das zuerst, bevor du dich
  selbst durch die großen Module (`app.py`, `db.py`, `desktop_dialoge.py`) durcharbeitest.
  Die Abläufe und Klassen als UML (Mermaid) stehen in `UML.md`.
- **Offene, zurückgestellte und akzeptierte Punkte auf einen Blick:** `OFFEN.md` - vor jeder
  Planung und bevor du einen Befund meldest dort nachsehen; jede zurückgestellte oder
  akzeptierte Entscheidung hat ein Dokument in `entscheidungen/` (Vorlage dort), die
  Fundstellen nennen Datei und Abschnittstitel in `Fortschritt.md` bzw. `historie/`.
- **Neue Prüfungsordnung ab 01.01.2027:** `PO_01012027.md` - ToDo-Liste der nötigen Anpassungen
  (Umschaltung über das Prüfungsdatum).
- **Entscheidungs-/Fix-Historie:** `Fortschritt.md` enthält nur den laufenden Monat; ältere
  Monate stehen unverändert in `historie/` (Übersicht dort). Vor einem erneuten Befund zu
  einem bereits besprochenen Punkt `OFFEN.md` und `entscheidungen/` lesen und die Historie mit
  `git grep -i "Stichwort" -- historie Fortschritt.md` durchsuchen, nicht komplett lesen.
  Am Monatsende den laufenden Monat nach `historie/JJJJ-MM.md` verschieben.
- **Berichte der Prüfungen** (Sicherheit, UX-Test, Desktop-Prüfung, QS, Abdeckung): `berichte/`.
- **Ausführliche Modulbeschreibung:** `Modulreferenz.md` (in `Architektur.md` steht nur ein
  Satz je Modul).
- **Ursprünglicher fachlicher Hintergrund/Migrationsplan:** `Grobkonzept.md`
- **`AGENTS.md`** ist der Spiegel dieser Datei für Codex-Sitzungen und wird aus ihr erzeugt:
  nach Änderungen hier `python test_agents_spiegel.py --schreiben` ausführen (der Test
  `test_agents_spiegel` schlägt sonst fehl).

## Arbeitsweise mit Subagents (mit dem Nutzer am 20.09.2026 abgestimmt)

1. **Explore-Subagent vor neuen, nicht-trivialen Aufgaben.** Statt `app.py` oder `db.py`
   komplett selbst zu lesen, zuerst einen schnellen Such-Subagent die relevante Stelle
   lokalisieren lassen.
2. **Bereichs-Subagents bei bereichsübergreifenden Änderungen.** Betrifft eine Änderung
   mehrere der drei Bereiche Desktop (`app.py`, `desktop_*.py`, `test_gui_*.py`,
   `gui_hilfen.py`, `test_theme.py`), Web (`app_web.py`, `templates/`, `test_app_web.py`) und Daten (`db.py` und die
   Schichtmodule `db_*.py`, `db_import.py`, `db_sicherung.py`, `shs_core.py`, `test_db.py`, `test_backup.py`,
   `test_db_postgres_wrapper.py`), parallele Subagents je Bereich statt sequenziell
   nacheinander.
3. **QS-Prüfungen mit differenzierten Rollen statt identischer Aufträge.** Bei einer
   Mehr-Subagent-Codeprüfung jedem Subagent einen anderen Schwerpunkt geben (Sicherheit /
   Korrektheit & Edge-Cases / Wartbarkeit & Stil). Dafür gibt es die Agenten-Typen in
   `.claude/agents/` (`qs-*`, `desktop-pruefer`), den Workflow `qs-pruefung`
   (`.claude/workflows/qs-pruefung.js`, mit Gegenprüfung aller Befunde) und den Skill
   `desktop-pruefung` (Desktopversion in 10 einzeln startbaren Teilen).
4. **Viele Aufgaben automatisch abarbeiten (Projektstandard).** Gibt Marco eine größere
   Menge Befunde "zur automatischen Abarbeitung", gilt der Skill `aufgaben-abarbeitung`
   (Limitprüfung über die Statuszeile, je Aufgabe Explore → Umsetzen → Tests → Verifikation
   → `Fortschritt.md` → lokaler Commit). Das ist die Ausnahme von "KEIN Commit" unten: dort
   wird je Aufgabe lokal committet, nie gepusht.
5. **Unabhängiger Verifikations-Subagent nach jeder Umsetzung.** Bevor eine Änderung als
   fertig gemeldet wird, prüft zusätzlich zum eigenen Testlauf ein separater Subagent Diff
   und Tests gegen - besonders bei sicherheitsrelevanten Änderungen. Dafür den
   Agenten-Typ `verifikation` nutzen.

Kein Subagent nimmt eigenständig Code-Änderungen an bereits abgeschlossenen, vom Nutzer
freigegebenen Ständen vor. Etablierter Prozess: jeder QS-/Sicherheits-Befund wird einzeln mit
dem Nutzer besprochen und erst nach seinem expliziten Go umgesetzt - das gilt für jede
Sitzung und jeden Subagent gleichermaßen, auch für automatisierte/geplante Läufe.

Die Agenten-Typen haben kein Edit- oder Write-Werkzeug und ändern deshalb keinen Code. Sie
liefern Befunde nur als Antwort; Berichte legt die Hauptsitzung ab (Sicherheitsberichte in
`_unveroeffentlicht/`).

## Sicherheitsfunde erst nach dem Release veröffentlichen (Marco 04.10.2026)

Das Repo ist öffentlich. Am 03.10.2026 standen die Sicherheitsberichte samt Nachstellung
knapp eine Stunde vor dem Release mit den Fixes im Netz. Das soll nicht wieder passieren:

- Berichte zu Sicherheitsprüfungen und gemeldeten Lücken entstehen im Ordner
  `_unveroeffentlicht/` (per `.gitignore` ausgeschlossen), nicht im Repo.
- In `Fortschritt.md`, Commit-Nachrichten und Code-Kommentaren werden offene
  Sicherheitsfunde bis zum Release nur allgemein beschrieben (z. B. "Sicherheitskorrektur
  S-1, Details folgen"), ohne betroffene Stelle, Angriffsweg oder Nachstellung.
- Erst wenn das Release mit allen Fixes veröffentlicht ist (CI grün, Installer und Image
  verfügbar), werden die Berichte in den Repo-Ordner verschoben und committet. Funde, die
  zurückgestellt oder nur notiert sind, werden dabei vorher mit Marco abgestimmt.
- UX-Tests und andere Berichte ohne Sicherheitsbezug sind davon nicht betroffen.

## Keine echten Namen (Marco 11.11.2026)

Das Repo ist öffentlich. Grundsätzlich steht kein echter Personenname außer Marco im Programm,
in der Dokumentation, in Aufgaben, `Fortschritt.md`, Commit-Nachrichten, Testdaten, Berichten
oder sonst wo. Rückmeldungen Dritter werden neutral beschrieben („Rückmeldung eines
Prüfungsteilnehmers“). Vor jedem Commit und Build mit `git grep -i` nach Namen suchen. Anlass:
Am 10.11.2026 stand ein Name in `Fortschritt.md` und einer Commit-Nachricht und ging mit dem
Release 1.0.60 raus; das Release musste neu gebaut werden. Erfundene Personas des UX-Tests sind
keine echten Personen.

## Bereits bewusst akzeptierte, nicht zu wiederholende QS-Funde

Diese zwei Punkte sind vom Nutzer als akzeptables Restrisiko eingestuft (Entscheidung
20.09.2026, siehe `Fortschritt.md`) - nicht erneut als neue Befunde melden:

- Kein Upload-Größenlimit beim Web-Login.
- Kein Brute-Force-Schutz beim Web-Login.

## Tests lokal ausführen (ohne PySide6/psycopg2/pytest)

```
python3 -m unittest test_db test_db_fassade test_db_postgres_wrapper test_backup test_pdf_export test_app_web test_bump_version test_shs_core test_bewertung_referenz test_altversionen test_drittlizenzen test_agents_spiegel
```

Lokal unter Windows immer den Anaconda-Python nehmen: `C:\Users\mbruv\anaconda3\python.exe`
statt `python3`. Das `python3` im PATH ist die Microsoft-Store-Variante (WindowsApps); ihr
fehlen `pypdf` und `psycopg2`, `test_pdf_export` läuft damit fast leer und meldet trotzdem
"OK". Der Anaconda-Python hat alles (PySide6, pypdf, psycopg2, Flask, pytest).

Test-/Dev-Abhängigkeiten (pytest, pytest-qt, pypdf, hypothesis) stehen in `requirements-dev.txt`. Ohne
`pypdf` wird `test_pdf_export` fast komplett übersprungen (nur wenige Tests laufen dann).

GUI-Tests (`test_gui_*.py` mit den gemeinsamen Fixtures in `gui_hilfen.py`, `test_theme.py`) und die echten PostgreSQL-Tests in `test_db.py` brauchen
PySide6 bzw. `SHS_TEST_POSTGRES_DSN`+`psycopg2`. Die GUI-Tests laufen lokal mit dem Anaconda-Python;
die echten PostgreSQL-Tests laufen nur in der CI (`.github/workflows/tests.yml`, Job `test` unter
Linux). Der zweite Job `test-windows` führt die Suite zusätzlich unter Windows aus (ohne PostgreSQL).

**Test-Suite (eigenes Repo `SHS Test Suite`, token-sparend):** `C:\Users\mbruv\anaconda3\python.exe "C:\Users\mbruv\Documents\Claude\SHS Test Suite\run_tests.py" --kompakt`
führt alle Tests inkl. GUI aus (grün: eine Zeile; sonst nur die Fehler mit Kurzgrund; Exit-Code 0/1). `--schnell` lässt
die GUI-Tests aus, `--json` liefert die Fehler maschinenlesbar, `--installation` testet zusätzlich die installierte EXE.
Details je Test (mit Erklärung): `bericht.md` im Berichtsordner der Suite - nur bei Fehlern nachlesen.

## Werkzeuge

- `gh` ist installiert und angemeldet (Konto `mbruver-source`). Für Releases, Release-Texte
  und Repo-Einstellungen nutzen (z. B. `gh release edit`). Nie behaupten, `gh` sei nicht
  verfügbar, ohne vorher `gh --version` auszuführen.
- Dateien mit dem Edit-/Write-Werkzeug ändern, nicht mit sed, PowerShell oder Heredoc-Skripten:
  Skript-Ersetzungen haben hier wiederholt Escapes, Backslashes, Zeilenenden und Zeilennummern
  zerstört.
- Python: lokal Anaconda 3.14, die CI (Tests und Installer-Build) läuft mit 3.11. Code und Tests
  müssen unter 3.11 laufen (keine Syntax/Bibliotheken erst ab 3.12+). Maßgeblich sind die
  Workflows in `.github/workflows/`, nicht die lokale Version.

## Fertig-Definition für Funktionen

Eine für Nutzer sichtbare Funktion gilt erst als fertig, wenn zum Stand der Änderung passen:
Code mit Tests, Demo-Daten, `docs/HANDBUCH.md`, `README*.md`, Screenshots in `docs/bilder/` und
die Website unter `docs/`. Wann was geschieht, regelt die Build-/Versionsdisziplin unten:
Änderungen bleiben bis zum Build im Arbeitsstand (kein Commit), das Handbuch-PDF entsteht erst
beim Build, die Screenshots werden nach dem Versionsbump noch einmal mit der neuen Version
aufgenommen, und Website-Änderungen zu neuen Funktionen gehen erst mit dem Release online.

- Tests müssen plattformunabhängig sein: keine fest eingebauten Windows-Pfadtrenner oder
  -Escapes, stattdessen `pathlib`/`os.path` (die CI läuft auch unter Linux).
- Nur erfundene Testdaten, nie echte Namen, E-Mail-Adressen oder Chipnummern.

## Sitzungsablauf bei Rückmeldungen/Aufgaben

### Feedback-Aufnahme

Wenn Marco Rückmeldungen gibt (Text oder Fotos handschriftlicher Notizen):

1. Jeden Punkt einzeln analysieren und einordnen: bereits umgesetzt / echte Rückfrage nötig /
   direkt umsetzbar / bereits bewusst akzeptiertes Restrisiko (siehe Abschnitt oben).
2. Bei Unklarheiten (z. B. Datenmodell-Entscheidungen, Umfang eines Wunsches) IMMER zuerst
   nachfragen, bevor Code geändert wird - nicht raten.
3. Jeden Punkt in `Fortschritt.md` dokumentieren, auch wenn er nur geklärt und nicht
   code-seitig umgesetzt wurde (z. B. Erklärung statt Fix). `Fortschritt.md` (laufender Monat) und
   `historie/` (ältere Monate) sind zusammen die einzige durchgängige Historie über alle
   Sitzungen hinweg.

### Build-/Versionsdisziplin ("erst nach Absprache")

- Code-Änderungen bleiben zunächst nur im Arbeitsstand + `Fortschritt.md`-Eintrag - KEINE
  Auslieferung, KEIN Versionsbump, KEIN Commit, bis Marco explizit einen Build anfordert
  ("jetzt neuen Build erzeugen" o. ä.). Ausnahmen: reine Dokumentationsänderungen (z. B. an
  dieser Datei, `Fortschritt.md`, `Architektur.md`) können direkt committet werden, und der
  Ablauf `aufgaben-abarbeitung` committet je Aufgabe lokal (siehe Subagents, Punkt 4).
- **Dokumente und Screenshots VOR dem Build (Marcos Vorgabe):** Bevor die Version erhöht und
  gebaut wird, müssen `docs/HANDBUCH.md`, die Screenshots in `docs/bilder/` (für jede sichtbar
  geänderte Oberfläche neu aufnehmen), `Architektur.md`, `README*.md` und `Fortschritt.md` zum
  Stand der gebündelten Änderungen passen. Kann ein Screenshot nicht erstellt werden, vor dem
  Build bei Marco nachfragen statt ohne ihn zu bauen.
- **Offene Punkte VOR dem Build klären (Marcos Vorgabe):** Liefern die Verifikation oder die
  Vorbereitung eines Builds noch Punkte, Befunde oder Auffälligkeiten - auch optionale
  Kleinigkeiten wie veraltete Kommentare oder Test-Robustheit -, wird NICHT gebaut, sondern
  zuerst Marco gefragt: umsetzen, bewusst zurückstellen oder verwerfen. Erst danach folgt der
  Build, mit allem, was dazugehören soll.
- Wenn Marco einen Build anfordert: die Checkliste in `.claude/skills/shs-build/SKILL.md`
  abarbeiten (in Claude Code als Skill `shs-build`). Die Regeln in diesem Abschnitt gehen vor;
  ändern sie sich, die Checkliste nachziehen.
- **Gilt auch für delegierte Sessions und Subagents:** Sie committen höchstens lokal und bauen,
  bumpen oder taggen nie. Wer eine Session startet, schreibt das ausdrücklich in den Brief
  (bei 1.0.58 hat eine delegierte Session ohne Anforderung gebaut).
- **Builds laufen in der CI auf GitHub, nicht lokal.** Die lokal installierte EXE ist die
  Vorversion und für Tests vor dem Build unerheblich; der EXE-Selbsttest der SHS Test Suite
  folgt erst nach dem Release und Marcos Installation (siehe `shs-build`, Schritt 7).
- `git tag` und `git push --tags` NIE selbst ausführen - das bleibt immer Marcos eigene
  Aktion. Ihm die genauen Befehle nennen, wenn nötig.
- `git push` (Marcos Freigabe): Bei Kleinigkeiten ohne Programmcode darf die Sitzung selbst
  pushen. Gemeint sind Dokumentation (`Fortschritt.md`, `Architektur.md`, diese Datei usw.),
  die Website unter `docs/` sowie Agenten-Typen, Workflows und Skills in `.claude/agents/`,
  `.claude/workflows/` und `.claude/skills/`. Vorher mit `git diff --stat origin/main..HEAD`
  prüfen, dass alle ungepushten Commits nur solche Dateien betreffen. Sobald Programmcode,
  Tests, Build-/CI-Dateien oder ein Build-Commit dabei sind, pusht weiterhin nur Marco. Die
  Regel "Sicherheitsfunde erst nach dem Release veröffentlichen" gilt auch hier.
- Ausnahme (Marco): Website-Änderungen unter `docs/`, die eine neue Funktion oder neue
  Download-Dateien beschreiben, gehen erst zusammen mit dem Release online, das diese
  enthält - nicht vorher separat pushen (die Website würde sonst Downloads ankündigen, die es
  im aktuellen Release noch nicht gibt).
- Hängt `git commit` an einer verwaisten `.git/index.lock` oder `.git/HEAD.lock` (kein echter
  Git-Prozess läuft), die Lock-Datei verschieben oder löschen und erneut committen.

### Geplante/zeitversetzte Aufgaben

Wenn Marco jetzt Feedback gibt und Rückfragen klärt, die eigentliche Umsetzung aber erst zu
einem späteren Zeitpunkt (z. B. als geplante/automatisierte Aufgabe) laufen soll:

1. Jetzt analysieren und alle nötigen Rückfragen stellen und beantworten lassen - die spätere
   Ausführung startet ohne Gedächtnis an dieses Gespräch und kann selbst nichts mehr
   nachfragen.
2. Die vollständige, detaillierte Arbeitsanweisung NICHT in einen kurzen Trigger-/Task-Prompt
   packen - lange Prompts haben in der Praxis wiederholt zu Timeouts beim Tool-Aufruf geführt.
   Stattdessen: ausführliches Briefing als neuen Abschnitt in `Fortschritt.md` schreiben, den
   eigentlichen Trigger-/Task-Prompt kurz halten und nur auf diesen Abschnitt verweisen.
3. Das Briefing in `Fortschritt.md` muss vollständig eigenständig sein: exakten lokalen
   Testbefehl nennen und den vollständigen Ablauf festhalten (Explore-Subagent → umsetzen/
   testen → Verifikations-Subagent → `Fortschritt.md` aktualisieren → lokal committen mit
   Attribution-Footer → NICHT pushen/taggen/Version bumpen, außer explizit angefordert →
   ausführliche Abschlussmeldung, da Marco bei der Ausführung nicht dabei ist).

### Projekt-Orte und Dokumenten-Synchronisation

- Neben diesem Repo (`SHS-Pruefungsprogramm-Git`) hält Marco einen reinen Quellcode-Spiegel
  ohne Git (`SHS-Pruefungsprogramm-Quellcode`) - bekommt bei Auslieferungen dieselben Dateien.
  Den Spiegel zieht die Sitzung beim Build automatisch nach (Marco 09.11.2026, Ablauf in
  `.claude/skills/shs-build/SKILL.md`).
- `Fortschritt.md`, `Architektur.md` und `Grobkonzept.md` werden zusätzlich in der
  claude.ai-Projekt-Ablage "SHS" synchron gehalten - bei Änderungen an einer der drei Dateien
  auch dort nachziehen, sofern die jeweilige Sitzung Zugriff darauf hat.
