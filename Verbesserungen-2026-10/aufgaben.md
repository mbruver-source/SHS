# Verbesserungen Oktober 2026: automatische Abarbeitung (V1–V8)

Angelegt am 19.10.2026 nach Marcos Freigabe (nach Release 1.0.51). Gewählt hat Marco:
- Windows-Tests in der CI;
- die zwei wackeligen GUI-Tests;
- die kleinen zurückgestellten Punkte B1–B6 aus `OFFEN.md`.

Ablauf nach dem Skill `aufgaben-abarbeitung` (`.claude/skills/aufgaben-abarbeitung/SKILL.md`).
Die Regeln aus `CLAUDE.md` gehen vor: kein Push, Tag, Versionsbump oder Build. Programmcode und
CI-Dateien pusht nur Marco.

Start durch Marco:
`/loop Arbeite die nächste offene Aufgabe aus Verbesserungen-2026-10/aufgaben.md nach dem dort beschriebenen Ablauf ab.`

## Statustabelle

| Aufgabe | Größe | Status | Commit | Limit vorher → nachher (5 h / 7 T) | Bemerkung |
|---|---|---|---|---|---|
| V1 Robuste GUI-Tests (Bezahlt-Checkbox, Strg+S) | S | erledigt | c1ff49c | 82 % / 19 % → 88 % / 20 % | GUI 408 grün; mit echter Windows-Plattform 1 passed + 1 begründeter Skip |
| V2 Windows-Job in der CI | M | erledigt | f494b39 | 0 % / 20 % → 8 % / 21 % | lokal im frischen venv 922 passed; CI-Ergebnis erst nach Marcos Push |
| V3 B1 + B2 Fehlerfenster | S | erledigt | 34bc9ef | 9 % / 21 % → 14 % / 21 % | GUI 410 grün; Nacharbeit aus Verifikation (Pfad am Satzende) |
| V4 B3 CSV-Altexporte und Excel-Verdacht | S | erledigt | 61f0faa | 15 % / 21 % → 19 % / 22 % | Unittests OK, GUI 410 grün; „1E5“ bleibt in B3 |
| V5 B4 Zeitplan-Effizienz | S | erledigt | 1b9bdda | 19 % / 22 % → 26 % / 22 % | Unittests OK, GUI 412 grün; UML Diagramm 7 berichtigt |
| V6 B5 Warnung ohne erlaubte Interaktion | S | erledigt | 7b46b4e | 26 % / 22 % → 36 % / 23 % | GUI 413 grün; Knopf-Verbindung per Lambda (im Testlauf gefunden) |
| V7 B6 `-wal`/`-shm` beim lesenden Öffnen | S | erledigt | 8a8a078 | 36 % / 23 % → 42 % / 24 % | GUI 413 grün; Rückfrage 1 (Restrisiko immutable) |
| V8 Abschluss | S | erledigt | dieser Commit | 42 % / 24 % → 48 % / 24 % | Abschluss-Verifikation in Ordnung; Rückfragen 1 und 2 offen |

Status: offen / läuft / erledigt / zurückgestellt (mit Grund).

## Kalibrierung

Startwerte als Anteil am 5-h-Fenster: S ≈ 10 %, M ≈ 15 %. Nach jeder Aufgabe den gemessenen
Verbrauch eintragen und die Werte nachjustieren.

Limitregel: weiter nur, wenn **Nutzung + Schätzung + 3 % ≤ 100 %**. Das gilt für den 5-h- und
den 7-Tage-Wert aus `%USERPROFILE%\.claude\shs-limit.json`. Fehlt `five_hour`, hat ein neues
Fenster begonnen (≈ 0 %).
- Passt die nächste Aufgabe nicht, aber eine kleinere: diese vorziehen. Dabei die Reihenfolge
  beachten: V1 vor V2, V8 zuletzt.
- Passt keine: `ScheduleWakeup` bis `resets_at` (höchstens 3600 s je Schritt, `noop: true`).

Stand beim Anlegen (19.10. 11:54): 5 h 80 %, 7 Tage 19 %. Das 5-h-Fenster setzt um 14:00
zurück.

## Ablauf je Aufgabe

1. Limit prüfen, Status „läuft“, Limit vorher eintragen. Steht schon „läuft“ aus einer
   abgebrochenen Runde: `git status`/`git diff` prüfen und fortsetzen.
2. Kurzes Explore der Fundstellen (Zeilen unten sind ungefähr), immer nur ein Subagent.
3. Umsetzen per Python-Skript im Scratchpad, angelegt mit dem Write-Werkzeug, nicht per Heredoc.
   Helfer `ed()` mit Trefferzählung und Zeilenenden-Erhalt.
4. Tests mit Gegenprobe. Die Gegenprobe erst, wenn kein anderer Testlauf mehr läuft, danach
   `git stash list` prüfen.
   - `C:\Users\mbruv\anaconda3\python.exe -m unittest test_db test_db_postgres_wrapper test_backup test_pdf_export test_app_web test_bump_version test_shs_core test_bewertung_referenz test_altversionen`
   - GUI: `QT_QPA_PLATFORM=offscreen timeout 580 C:\Users\mbruv\anaconda3\python.exe -X faulthandler -m pytest test_app_gui.py test_theme.py -q -p no:cacheprovider -o faulthandler_timeout=30`
     (rund 50 s). Stand vorher: 407 passed, 1 skipped, 1 xfailed.
5. Verifikation mit dem Agenten `verifikation`, ohne komplette Testsuiten im Agenten. Befunde
   innerhalb der Aufgabe beheben; Unklares unter „Rückfragen an Marco“ eintragen und den
   Teilpunkt zurückstellen.
6. Abschnitt in `Fortschritt.md`; `OFFEN.md` nachziehen (erledigte Punkte streichen).
7. Lokaler Commit (`git commit -F <datei>`) mit Footer
   `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` und der Claude-Session-Zeile.
8. Tabelle aktualisieren, kurze Meldung, `ScheduleWakeup` (60 s, wenn das Limit reicht).

## Aufgaben

### V1 Robuste GUI-Tests (S)
- `test_app_gui.py`:
  - `test_bezahlt_checkbox_im_teilnehmer_dialog` (~Z. 1515): `qtbot.mouseClick` auf die
    Checkbox, eventuell bevor der Dialog sichtbar ist.
  - `test_strg_s_speichert_in_der_ergebniserfassung` (~Z. 5992): Das Kürzel greift nur im
    aktiven Fenster; `activateWindow`/`waitUntil(isActiveWindow)` hängen vom Fokus ab.
- Rot nachstellen: einzeln und in der vollen Suite, offscreen und mit `QT_QPA_PLATFORM=windows`,
  während ein anderes Fenster den Fokus hat.
- Bezahlt: vor dem Klick `qtbot.waitExposed(dialog)`. Bleibt der Test wackelig, über Tastatur
  oder `click()` schalten. Geprüft wird die Verdrahtung mit `ergebnis()`.
- Strg+S:
  - Das `QShortcut`/die `QAction` mit `QKeySequence.Save` suchen. Prüfen: Kontext,
    `activated` ruft `alle_speichern` auf, in einem anderen Reiter passiert nichts.
  - Den echten Tastenweg nur prüfen, wenn das Fenster wirklich aktiv wird. Sonst diesen Teil
    mit Begründung überspringen.
- Fertig, wenn beide Tests zehnmal hintereinander und in der vollen Suite grün sind.
- Danach `OFFEN.md` C26 streichen.

### V2 Windows-Job in der CI (M)
- `.github/workflows/tests.yml`: zweiter Job `test-windows` mit `runs-on: windows-latest` und
  Python 3.11.
  - Dieselben festgenagelten Action-Hashes wie der Linux-Job (S-3).
  - `env`: `QT_QPA_PLATFORM: offscreen`, `PYTHONUTF8: "1"`.
  - Installiert werden `requirements.txt`, `requirements-web.txt` und `requirements-dev.txt`.
  - Ohne PostgreSQL: Service-Container gehen unter Windows nicht, die echten PostgreSQL-Tests
    überspringen sich ohne `SHS_TEST_POSTGRES_DSN` selbst.
  - Die pypdf-Prüfung wie im Linux-Job, danach `pytest -v`.
  - Kopfkommentar ergänzen.
- Vorher lokal nachstellen: eigenes venv im Scratchpad (nicht im Repo), nur diese
  Anforderungen, `PYTHONUTF8=1`, volle Suite. Unterschiede gegenüber Anaconda beheben.
- Tests, die nur auf einer Plattform sinnvoll sind, bekommen `pytest.mark.skipif` mit
  Begründung. Kein Test darf echte Einstellungen in die Registry schreiben (QSettings).
- Doku nachziehen:
  - `Architektur.md`: CI-Kasten und Abschnitt 4;
  - `CLAUDE.md`/`AGENTS.md`: Absatz zu GUI- und PostgreSQL-Tests;
  - `OFFEN.md` B10: „Windows in der CI“ als erledigt.
- Das CI-Ergebnis gibt es erst nach Marcos Push. Als Prüfschritt in V8 und in der
  Abschlussmeldung nennen.

### V3 B1 + B2 Fehlerfenster (S)
- **B1** `desktop_gemeinsam._ohne_benutzerpfad` (~Z. 921): Der Benutzername wird im Freitext
  erst ab 6 Zeichen ersetzt. Kürzere Namen deckt die Pfad-Ersetzung ab (Ordner, `Users\…`,
  `home/…`).
  - Test: „max“ in `max(` bleibt, `C:\Users\max\x` wird zu `~\x`.
- **B2** `desktop_gemeinsam._fehlerbild` (~Z. 1058): Das Fehlerbild ist Typ plus alle
  Traceback-Stellen (Datei und Zeile) statt nur der innersten.
  - Ein wiederkehrender Timer-Fehler bleibt ein Fehlerbild.
  - Verschiedene Aufrufwege über dieselbe Hilfsfunktion zeigen je ein Fenster.
  - Test mit zwei Aufrufwegen und mit Wiederholung.
- Handbuch und Architektur nur, wenn sich dort Beschriebenes ändert.

### V4 B3 CSV-Altexporte und Excel-Verdacht (S)
- `db_import.py`: Formelschutz `_braucht_schutz`, Import-Pfad, `_excel_verdacht` (~Z. 260).
- Beim Import das „'“ auch nach der alten Exportregel entfernen: die zwei Sonderfälle „'+49 170
  …“ (mit Leerzeichen) und genau „'-“. Die alte Regel aus der Git-Historie vor dem 14.10.2026
  ermitteln.
- Telefon-Verdacht „ohne führende 0“ erst ab 9 Ziffern; Ortsnummern mit 6–8 Ziffern lösen ihn
  nicht mehr aus. Den Exponent-Verdacht unverändert lassen.
- Tests: Rundreise mit den Altfällen, kein Fehlalarm bei „123456“, Treffer bei „17012345678“.

### V5 B4 Zeitplan-Effizienz (S)
- `desktop_zeitplan.ZeitplanTab._aktueller_eintrag` (~Z. 675) rechnet den ganzen Blockplan, nur
  um Typ, Dauer und Bezeichnung zu lesen. Stattdessen den Eintrag direkt lesen: vorhandene
  Lesefunktion in `db.py` suchen, sonst `zeitplan_eintrag(conn, id)` mit Test in `test_db.py`.
  - Muss auch unter PostgreSQL laufen: `fetchall()` und Spaltennamen, siehe Memory „Tests
    PostgreSQL-tauglich“.
- `PauseDialog` (`desktop_dialoge.py`) legt seine Felder beim Bearbeiten nicht doppelt an.
- Tests: Bearbeiten einer Pause und eines Blocks, die vorhandenen Zeitplan-Tests bleiben grün.

### V6 B5 Warnung ohne erlaubte Interaktion (S)
- `app.py`: `HauptFenster._beenden_vorbereiten(rueckfrage_moeglich)` (~Z. 2963) ruft
  `ErgebnisTab.alle_speichern()` auf. Das zeigt Warnungen (`QMessageBox.warning`,
  `_db_fehler_anzeigen`), auch wenn das System beim Sitzungsende keine Interaktion erlaubt (X11,
  macOS).
- Umsetzung: `alle_speichern(meldungen: bool = True)`. Ohne Meldungen gehen die Gründe ins
  Protokoll (`fehler_protokollieren` bzw. `logging`), es öffnet sich kein Fenster.
  `_beenden_vorbereiten` gibt `meldungen=rueckfrage_moeglich` weiter.
- Test: `_sitzungsende_pruefen` mit einem Manager, der keine Interaktion erlaubt, und einer
  nicht speicherbaren Zeile. Erwartet: keine Meldung, `manager.cancel()` aufgerufen.
- `UML.md` Diagramm 12 prüfen.

### V7 B6 `-wal`/`-shm` beim lesenden Öffnen (S)
- `db.oeffne_termin_lesend` (~Z. 2482): Eine fremde Datei im WAL-Modus hinterlässt beim nur
  lesenden Öffnen `-wal`/`-shm`.
- Umsetzung: Header-Bytes 18/19 == 2 (WAL) und keine `<datei>-wal` daneben → URI zusätzlich mit
  `immutable=1`. Liegt eine `-wal` daneben, bleibt es wie bisher (ihr Inhalt muss mitgelesen
  werden).
- Test: Eine WAL-Datei (vorher `PRAGMA journal_mode=WAL`, dann geschlossen) durchläuft
  `liste_termine`, `termin_lesend_pruefen` plus `termin_unversehrt_pruefen` und die Sicherung.
  Danach gibt es keine neuen Dateien im Ordner. Gegenprobe rot.
- Den Hinweis in `Desktop-Pruefung-2026-10/aufgaben.md` (A9, „Offen, keine Regression“) als
  erledigt vermerken.

### V8 Abschluss (S)
- Agent `verifikation` über alle V-Commits. Er prüft auch `OFFEN.md` und `UML.md`.
- `OFFEN.md`: C26 und B1–B6 gestrichen bzw. Restbedingungen notiert, B10 angepasst.
- Abschlussbericht hier und in `Fortschritt.md`:
  - Commits;
  - Rückfragen;
  - Prüfschritt für Marco: nach dem Push in „Actions“ beide Test-Jobs (Linux und Windows)
    prüfen.
- Loop mit `ScheduleWakeup(stop: true)` beenden, PushNotification an Marco.

## Rückfragen an Marco

1. **V7, Restrisiko `immutable=1`:** Eine fremde Termin-Datei im WAL-Modus ohne `-wal` daneben
   wird jetzt ohne Sperre gelesen (sonst blieben `-wal`/`-shm` liegen). Öffnet genau während
   des Lesens ein fremdes Werkzeug (z. B. DB Browser) die Datei, schreibt und macht einen
   Checkpoint, könnten Übersicht, Import oder Sicherung einen Mischstand lesen oder
   „beschädigt“ melden. Eigene Termin-Dateien sind nie betroffen (Rollback-Journal). Sehr
   unwahrscheinlich. Vorschlag: als akzeptiertes Restrisiko in `OFFEN.md` Teil C eintragen.
   Alternative: B6 zurücknehmen (Zusatzdateien bleiben dann liegen).
2. **V8, Randfall Sitzungsende:** Erlaubt das System beim Abmelden keine Rückfrage und wird
   das Abmelden danach doch abgebrochen (X11), speichert das spätere Schließen per Fenster-X
   neue Eingaben wie gewohnt mit Meldungen. Das ist vorhandenes Verhalten. Soll dort ebenfalls
   ohne Meldungen gespeichert werden? Vorschlag: so lassen. Wer das Fenster selbst schließt,
   darf die Meldung sehen.

**Antwort Marco (19.10.2026):** Beide Vorschläge angenommen. Rückfrage 1 ist als
akzeptiertes Restrisiko `OFFEN.md` C34 eingetragen, Rückfrage 2 bleibt so (C35).

## Abschlussbericht (19.10.2026)

Commits (alle lokal, nicht gepusht): c1ff49c V1, f494b39 V2, 34bc9ef V3, 61f0faa V4,
1b9bdda V5, 7b46b4e V6, 8a8a078 V7, dazu der Abschluss-Commit V8.

- Verbrauch: 82 % → 88 % (V1), dann neues Fenster 0 % → 42 % für V2–V7, V8 rund 5 %.
  Tatsächlich etwa S ≈ 5–10 %, M ≈ 8 %.
- Tests am Ende: Unittests OK (skipped=175), GUI 413 passed, 1 skipped, 1 xfailed. Frisches
  venv wie im Windows-Job: 922 passed (Stand V2).
- Abschluss-Verifikation über alle Commits: in Ordnung, keine Muss-Punkte. Übernommen:
  - UML Diagramm 12 (`ErgebnisTab.alle_speichern`, Hinweis SitzungsendeFilter für alle
    Freigaben) und Klassendiagramm (`alle_speichern(meldungen)`);
  - Fundstellen in `OFFEN.md` A8/B3.
- `OFFEN.md`: C26, B1, B2, B4, B5, B6 gestrichen; B3 auf „1E5“ gekürzt; B10 „Windows in der
  CI“ erledigt; A8 und A9 (Rückfragen 1 und 2) neu.
- **Prüfschritt für Marco nach dem Push:** unter „Actions“ beide Test-Jobs prüfen, `test`
  (Linux, mit PostgreSQL) und `test-windows`. Der Windows-Job läuft dann zum ersten Mal
  (lokal mit Python 3.12 nachgestellt, die CI nutzt 3.11). Restrisiko laut Verifikation: der
  Strg+S-Test unter Linux-offscreen, falls das Aktivieren dort verzögert ist.
- Die Änderung am Codex-Agenten `.codex/agents/verifikation.toml` ist nur lokal, `.codex/`
  ist von Git ausgeschlossen.
