# SHS-Prüfungsprogramm - Hinweise für Claude-Sitzungen

Verwaltungssoftware für Spürhundsport-Prüfungen (SHS) eines Vereins. Bevor du hier arbeitest:

- **Architekturüberblick (mit Diagramm):** `Architektur.md` - lies das zuerst, bevor du dich
  selbst durch die großen Module (`app.py`: 2918 Zeilen, `db.py`: 1850 Zeilen) durcharbeitest.
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

GUI-Tests (`test_app_gui.py`) und die echten PostgreSQL-Tests in `test_db.py` brauchen
PySide6 bzw. `SHS_TEST_POSTGRES_DSN`+`psycopg2` und laufen nur in der CI
(`.github/workflows/tests.yml`).
