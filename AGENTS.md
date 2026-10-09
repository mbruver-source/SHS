# SHS-Prüfungsprogramm - Hinweise für Codex-Sitzungen

Diese Datei ist der Spiegel von `CLAUDE.md` für Codex (Stand 05.10.2026). Maßgeblich ist
`CLAUDE.md`; bei Änderungen an einer der beiden Dateien die andere nachziehen.

Verwaltungssoftware für Spürhundsport-Prüfungen (SHS) eines Vereins. Bevor du hier arbeitest:

- **Architekturüberblick (mit Diagramm):** `Architektur.md` - lies das zuerst, bevor du dich
  selbst durch die großen Module (`app.py`: rund 4500 Zeilen, `db.py`: rund 3200 Zeilen,
  Stand 09.10.2026; ausgelagert sind `desktop_*.py`, `db_import.py`, `db_sicherung.py`)
  durcharbeitest.
- **Vollständige Entscheidungs-/Fix-Historie, offene Punkte, akzeptierte Restrisiken:**
  `Fortschritt.md` - insbesondere die "Noch offen"-Abschnitte, bevor du einen bereits
  besprochenen und bewusst abgelehnten Punkt erneut als neuen Befund meldest.
- **Ursprünglicher fachlicher Hintergrund/Migrationsplan:** `Grobkonzept.md`

## Arbeitsweise mit Subagents (mit dem Nutzer am 20.09.2026 abgestimmt)

1. **Explore-Subagent vor neuen, nicht-trivialen Aufgaben.** Statt `app.py` oder `db.py`
   komplett selbst zu lesen, zuerst einen schnellen Such-Subagent die relevante Stelle
   lokalisieren lassen.
2. **Bereichs-Subagents bei bereichsübergreifenden Änderungen.** Betrifft eine Änderung
   mehrere der drei Bereiche Desktop (`app.py`, `desktop_*.py`, `test_app_gui.py`,
   `test_theme.py`), Web (`app_web.py`, `templates/`, `test_app_web.py`) und Daten (`db.py`,
   `db_import.py`, `db_sicherung.py`, `shs_core.py`, `test_db.py`, `test_backup.py`,
   `test_db_postgres_wrapper.py`), parallele Subagents je Bereich statt sequenziell
   nacheinander.
3. **QS-Prüfungen mit differenzierten Rollen statt identischer Aufträge.** Bei einer
   Mehr-Subagent-Codeprüfung (z. B. 3 unabhängige Reviewer) jedem Subagent einen anderen
   Schwerpunkt geben statt 3x denselben allgemeinen Auftrag: Sicherheit / Korrektheit &
   Edge-Cases / Wartbarkeit & Stil. Dafür gibt es feste Agenten-Typen in `.claude/agents/`:
   `qs-sicherheit`, `qs-korrektheit`, `qs-wartbarkeit` (läuft auf Sonnet).
   Den ganzen Ablauf samt Gegenprüfung aller Befunde fasst der gespeicherte Workflow
   `qs-pruefung` (`.claude/workflows/qs-pruefung.js`) zusammen.
4. **Unabhängiger Verifikations-Subagent nach jeder Umsetzung.** Bevor eine Änderung als
   fertig gemeldet wird, prüft zusätzlich zum eigenen Testlauf ein separater Subagent Diff
   und Tests gegen - besonders bei sicherheitsrelevanten Änderungen. Dafür den
   Agenten-Typ `verifikation` aus `.claude/agents/` nutzen.

Kein Subagent nimmt eigenständig Code-Änderungen an bereits abgeschlossenen, vom Nutzer
freigegebenen Ständen vor. Etablierter Prozess: jeder QS-/Sicherheits-Befund wird einzeln mit
dem Nutzer besprochen und erst nach seinem expliziten Go umgesetzt - das gilt für jede
Sitzung und jeden Subagent gleichermaßen, auch für automatisierte/geplante Läufe.

Die vier Agenten-Typen (07.10.2026 mit Marco abgestimmt) haben kein Edit- oder
Write-Werkzeug und ändern deshalb keinen Code. Sie liefern Befunde nur als Antwort; Berichte
legt die Hauptsitzung ab (Sicherheitsberichte in `_unveroeffentlicht/`).
Codex kennt diese Dateien nicht; dort die Texte als Auftrag für die jeweilige Rolle
verwenden.

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

## Bereits bewusst akzeptierte, nicht zu wiederholende QS-Funde

Diese zwei Punkte sind vom Nutzer als akzeptables Restrisiko eingestuft (Entscheidung
20.09.2026, siehe `Fortschritt.md`) - nicht erneut als neue Befunde melden:

- Kein Upload-Größenlimit beim Web-Login.
- Kein Brute-Force-Schutz beim Web-Login.

## Tests lokal ausführen (ohne PySide6/psycopg2/pytest)

```
python3 -m unittest test_db test_db_postgres_wrapper test_backup test_pdf_export test_app_web test_bump_version test_shs_core test_bewertung_referenz test_altversionen
```

Test-/Dev-Abhängigkeiten (pytest, pytest-qt, pypdf, hypothesis) stehen in `requirements-dev.txt`. Ohne
`pypdf` wird `test_pdf_export` fast komplett übersprungen (nur wenige Tests laufen dann).

GUI-Tests (`test_app_gui.py`) und die echten PostgreSQL-Tests in `test_db.py` brauchen
PySide6 bzw. `SHS_TEST_POSTGRES_DSN`+`psycopg2` und laufen nur in der CI
(`.github/workflows/tests.yml`).

## Sitzungsablauf bei Rückmeldungen/Aufgaben (aus dem Cowork-Arbeitsablauf übernommen, 21.09.2026)

Bis zur Migration auf Claude Code (und daneben Codex) lief die Zusammenarbeit über Cowork,
mit einem eigenen Cowork-Skill (`shs-projekt-workflow`) für das Sitzungs-/Drumherum. Damit diese mit Marco
abgestimmten Abläufe nicht verloren gehen, stehen sie ab jetzt hier - unabhängig vom
jeweils genutzten Werkzeug (Cowork, Claude Code oder Codex).

### Feedback-Aufnahme

Wenn Marco Rückmeldungen gibt (Text oder Fotos handschriftlicher Notizen):

1. Jeden Punkt einzeln analysieren und einordnen: bereits umgesetzt / echte Rückfrage nötig /
   direkt umsetzbar / bereits bewusst akzeptiertes Restrisiko (siehe Abschnitt oben).
2. Bei Unklarheiten (z. B. Datenmodell-Entscheidungen, Umfang eines Wunsches) IMMER zuerst
   nachfragen, bevor Code geändert wird - nicht raten.
3. Jeden Punkt in `Fortschritt.md` dokumentieren, auch wenn er nur geklärt und nicht
   code-seitig umgesetzt wurde (z. B. Erklärung statt Fix). `Fortschritt.md` ist die einzige
   durchgängige Historie über alle Sitzungen hinweg.

### Build-/Versionsdisziplin ("erst nach Absprache")

- Code-Änderungen bleiben zunächst nur im Arbeitsstand + `Fortschritt.md`-Eintrag - KEINE
  Auslieferung, KEIN Versionsbump, KEIN Commit, bis Marco explizit einen Build anfordert
  ("jetzt neuen Build erzeugen" o. ä.). Reine Dokumentationsänderungen (z. B. an dieser Datei,
  `Fortschritt.md`, `Architektur.md`) sind davon ausgenommen und können direkt committet
  werden.
- **Dokumente und Screenshots VOR dem Build (Marcos Vorgabe, 27.09.2026):** Bevor die Version
  erhöht und gebaut wird, müssen alle Dokumente zum Stand der gebündelten Änderungen passen.
  Anlass: Bei 1.0.35 wurde der Handbuch-Screenshot erst nach dem Build erneuert und musste
  deshalb auf den nächsten Build warten. Konkret vor jedem Build prüfen und nachziehen:
  - `docs/HANDBUCH.md` inhaltlich (neue/geänderte Funktionen, Bedienung);
  - Screenshots in `docs/bilder/` für jede sichtbar geänderte Oberfläche neu aufnehmen;
  - `Architektur.md`, `README*.md` und `Fortschritt.md`.
  Erst danach kommen Versionsbump, `docs/HANDBUCH.pdf` und Build. Kann ein Screenshot nicht
  erstellt werden, vor dem Build bei Marco nachfragen statt ohne ihn zu bauen.
- **Offene Punkte VOR dem Build klären (Marcos Vorgabe, 27.09.2026):** Liefern die Verifikation
  oder die Vorbereitung eines Builds noch Punkte, Befunde oder Auffälligkeiten, gilt das auch
  für optionale Kleinigkeiten wie veraltete Kommentare oder Test-Robustheit. Dann wird NICHT
  gebaut, sondern zuerst Marco gefragt und der Umgang damit geklärt: umsetzen, bewusst
  zurückstellen oder verwerfen. Erst danach folgt der Build, mit allem, was dazugehören soll.
  Anlass: 1.0.37 wurde gebaut, obwohl die Verifikation noch zwei kleine Punkte gemeldet hatte.
  Die kamen danach als Nachtrag-Commit dazu, sodass zwei Build-Durchläufe entstanden, wo einer
  gereicht hätte.
- Wenn Marco einen Build anfordert: die Checkliste in `.claude/skills/shs-build/SKILL.md`
  abarbeiten (in Claude Code als Skill `shs-build`; Codex liest die Datei direkt; seit
  07.10.2026). Sie enthält die Schritte in dieser Reihenfolge: offene Punkte klären, Dokumente und Screenshots wie oben,
  `bump_version.py`, `tools/handbuch_pdf.py`, lokale Tests, Build-Commit, danach die
  Altdaten der neuen Version als eigener Commit (Marcos Entscheidung T3, 03.10.2026).
  Die Regeln in diesem Abschnitt gehen vor; ändern sie sich, die Checkliste nachziehen.
- `git tag` und `git push --tags` NIE selbst ausführen - das bleibt immer Marcos eigene
  Aktion. Ihm die genauen Befehle nennen, wenn nötig.
- `git push` (Marcos Freigabe, 06.10.2026): Bei Kleinigkeiten ohne Programmcode darf die
  Sitzung selbst pushen. Gemeint sind Dokumentation (`Fortschritt.md`, `Architektur.md`,
  diese Datei usw.), die Website unter `docs/` sowie Agenten-Typen, Workflows und Skills in
  `.claude/agents/`, `.claude/workflows/` und `.claude/skills/` (Ergänzung 07.10.2026). Vorher mit
  `git diff --stat origin/main..HEAD` prüfen, dass alle ungepushten Commits nur solche
  Dateien betreffen. Sobald Programmcode, Tests, Build-/CI-Dateien oder ein Build-Commit
  dabei sind, pusht weiterhin nur Marco. Die Regel "Sicherheitsfunde erst nach dem Release
  veröffentlichen" gilt auch hier.
- Ausnahme (Marco 07.10.2026): Website-Änderungen unter `docs/`, die eine neue Funktion oder
  neue Download-Dateien beschreiben, gehen erst zusammen mit dem Release online, das diese
  enthält – nicht vorher separat pushen. Anlass: die Mac-/Linux-Vorschau; die Website hätte
  sonst Downloads angekündigt, die es im aktuellen Release noch nicht gibt.

### Bekannte Fallstricke bei der Auslieferung (traten bisher beim Arbeiten über die Cowork-Geräte-Brücke auf)

- Stale `.git/index.lock`/`.git/HEAD.lock` blockieren gelegentlich `git commit` (kein echter
  Git-Prozess läuft, vermutlich ein Hintergrundprozess auf dem Rechner). Workaround: Lock-Datei
  vor dem Commit-Versuch verschieben oder löschen, dann committen.
- Nach wichtigen Schreibvorgängen zur Sicherheit Byte-Anzahl/Inhalt gegenprüfen (z. B.
  `wc -c`/`grep`) - insbesondere wenn der Schreibweg (z. B. eine Cowork-Geräte-Brücke) einen
  stillen No-Op melden könnte, ohne den Inhalt tatsächlich zu aktualisieren.

### Geplante/zeitversetzte Aufgaben

Wenn Marco jetzt Feedback gibt und Rückfragen klärt, die eigentliche Umsetzung aber erst zu
einem späteren Zeitpunkt (z. B. als geplante/automatisierte Aufgabe) laufen soll:

1. Jetzt analysieren und alle nötigen Rückfragen stellen und beantworten lassen - die spätere
   Ausführung startet ohne Gedächtnis an dieses Gespräch und kann selbst nichts mehr
   nachfragen.
2. Die vollständige, detaillierte Arbeitsanweisung NICHT in einen kurzen Trigger-/Task-Prompt
   packen - lange Prompts haben in der Praxis (Cowork `create_trigger`) wiederholt zu Timeouts
   beim Tool-Aufruf geführt. Stattdessen: ausführliches Briefing als neuen Abschnitt in
   `Fortschritt.md` schreiben, den eigentlichen Trigger-/Task-Prompt kurz halten und nur auf
   diesen Abschnitt verweisen.
3. Das Briefing in `Fortschritt.md` muss vollständig eigenständig sein: exakten lokalen
   Testbefehl nennen und den vollständigen Ablauf festhalten (Explore-Subagent → umsetzen/
   testen → Verifikations-Subagent → `Fortschritt.md` aktualisieren → committen mit
   Attribution-Footer → NICHT pushen/taggen/Version bumpen, außer explizit angefordert →
   ausführliche Abschlussmeldung, da Marco bei der Ausführung nicht dabei ist).

### Projekt-Orte und Dokumenten-Synchronisation

- Neben diesem Repo (`SHS-Pruefungsprogramm-Git`) hält Marco einen reinen Quellcode-Spiegel
  ohne Git (`SHS-Pruefungsprogramm-Quellcode`) - bekommt bei Auslieferungen dieselben Dateien.
- `Fortschritt.md`, `Architektur.md` und `Grobkonzept.md` werden zusätzlich in der
  claude.ai-Projekt-Ablage "SHS" synchron gehalten - bei Änderungen an einer der drei Dateien
  auch dort nachziehen, sofern die jeweilige Sitzung Zugriff darauf hat.
