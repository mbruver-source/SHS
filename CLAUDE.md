# SHS-Prüfungsprogramm - Hinweise für Claude-Sitzungen

Verwaltungssoftware für Spürhundsport-Prüfungen (SHS) eines Vereins. Bevor du hier arbeitest:

- **Architekturüberblick (mit Diagramm):** `Architektur.md` - lies das zuerst, bevor du dich
  selbst durch die großen Module (`app.py`: rund 4500 Zeilen, `db.py`: rund 2700 Zeilen,
  Stand 22.09.2026) durcharbeitest.
- **Vollständige Entscheidungs-/Fix-Historie, offene Punkte, akzeptierte Restrisiken:**
  `Fortschritt.md` - insbesondere die "Noch offen"-Abschnitte, bevor du einen bereits
  besprochenen und bewusst abgelehnten Punkt erneut als neuen Befund meldest.
- **Ursprünglicher fachlicher Hintergrund/Migrationsplan:** `Grobkonzept.md`

## Arbeitsweise mit Subagents (mit dem Nutzer am 20.09.2026 abgestimmt)

1. **Explore-Subagent vor neuen, nicht-trivialen Aufgaben.** Statt `app.py` oder `db.py`
   komplett selbst zu lesen, zuerst einen schnellen Such-Subagent die relevante Stelle
   lokalisieren lassen.
2. **Bereichs-Subagents bei bereichsübergreifenden Änderungen.** Betrifft eine Änderung
   mehrere der drei Bereiche Desktop (`app.py`, `test_app_gui.py`), Web (`app_web.py`,
   `templates/`, `test_app_web.py`) und Daten (`db.py`, `shs_core.py`, `test_db.py`,
   `test_db_postgres_wrapper.py`), parallele Subagents je Bereich statt sequenziell
   nacheinander.
3. **QS-Prüfungen mit differenzierten Rollen statt identischer Aufträge.** Bei einer
   Mehr-Subagent-Codeprüfung (z. B. 3 unabhängige Reviewer) jedem Subagent einen anderen
   Schwerpunkt geben statt 3x denselben allgemeinen Auftrag: Sicherheit / Korrektheit &
   Edge-Cases / Wartbarkeit & Stil.
4. **Unabhängiger Verifikations-Subagent nach jeder Umsetzung.** Bevor eine Änderung als
   fertig gemeldet wird, prüft zusätzlich zum eigenen Testlauf ein separater Subagent Diff
   und Tests gegen - besonders bei sicherheitsrelevanten Änderungen.

Kein Subagent nimmt eigenständig Code-Änderungen an bereits abgeschlossenen, vom Nutzer
freigegebenen Ständen vor. Etablierter Prozess: jeder QS-/Sicherheits-Befund wird einzeln mit
dem Nutzer besprochen und erst nach seinem expliziten Go umgesetzt - das gilt für jede
Sitzung und jeden Subagent gleichermaßen, auch für automatisierte/geplante Läufe.

## Bereits bewusst akzeptierte, nicht zu wiederholende QS-Funde

Diese zwei Punkte sind vom Nutzer als akzeptables Restrisiko eingestuft (Entscheidung
20.09.2026, siehe `Fortschritt.md`) - nicht erneut als neue Befunde melden:

- Kein Upload-Größenlimit beim Web-Login.
- Kein Brute-Force-Schutz beim Web-Login.

## Tests lokal ausführen (ohne PySide6/psycopg2/pytest)

```
python3 -m unittest test_db test_db_postgres_wrapper test_backup test_pdf_export test_app_web test_bump_version test_shs_core
```

Test-/Dev-Abhängigkeiten (pytest, pytest-qt, pypdf) stehen in `requirements-dev.txt`. Ohne
`pypdf` wird `test_pdf_export` fast komplett übersprungen (nur wenige Tests laufen dann).

GUI-Tests (`test_app_gui.py`) und die echten PostgreSQL-Tests in `test_db.py` brauchen
PySide6 bzw. `SHS_TEST_POSTGRES_DSN`+`psycopg2` und laufen nur in der CI
(`.github/workflows/tests.yml`).

## Sitzungsablauf bei Rückmeldungen/Aufgaben (aus dem Cowork-Arbeitsablauf übernommen, 21.09.2026)

Bis zur Migration auf Claude Code lief die Zusammenarbeit über Cowork, mit einem eigenen
Cowork-Skill (`shs-projekt-workflow`) für das Sitzungs-/Drumherum. Damit diese mit Marco
abgestimmten Abläufe nicht verloren gehen, stehen sie ab jetzt hier - unabhängig vom
jeweils genutzten Werkzeug (Cowork oder Claude Code).

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
- Wenn Marco einen Build anfordert: alle seit dem letzten Build gesammelten Änderungen
  bündeln, Version per `bump_version.py` erhöhen, lokale Tests laufen lassen, committen
  (Attribution-Footer aus dem System-Reminder anhängen, sofern vorhanden).
- `git push`, `git tag`, `git push --tags` NIE selbst ausführen - das bleibt immer Marcos
  eigene Aktion. Ihm die genauen Befehle nennen, wenn nötig.

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
