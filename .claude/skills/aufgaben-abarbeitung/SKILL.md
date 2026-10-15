---
name: aufgaben-abarbeitung
description: Projektstandard (Marco 15.10.2026) für das automatische Abarbeiten einer größeren Menge von Befunden bzw. Aufgaben über Nutzungslimit-Pausen hinweg - Aufgabenliste anlegen, Größen schätzen, Limit über die Statuszeile prüfen, je Aufgabe Explore → Umsetzen → Tests → Verifikation → Fortschritt.md → Commit, Loop mit ScheduleWakeup. Verwenden, wenn Marco viele Punkte "zur automatischen Abarbeitung" gibt.
---

# Aufgaben automatisch abarbeiten (Projektstandard)

Bewährt bei der Abarbeitung der Desktop-Prüfung (14./15.10.2026, A1–A19). Die Regeln aus
`CLAUDE.md` gehen vor (Sicherheitsfunde erst nach dem Release, Build-/Versionsdisziplin, kein
Push von Programmcode).

## 1. Vorbereitung (mit Marco, vor dem Start)

1. **Rückfragen zuerst:** Alle fachlich offenen Punkte vorab mit Marco klären und die
   Entscheidungen festhalten - die spätere Abarbeitung fragt nicht nach, sondern stellt Unklares
   zurück (siehe 3.4).
2. **Aufgaben bilden:** Zusammenhängende Befunde (gleiche Datei, gleicher Ablauf, gemeinsame
   Hilfsfunktion) zu einer Aufgabe bündeln. Reihenfolge: hoch → mittel → niedrig → optional;
   Sicherheitsbefunde mit **[S]** kennzeichnen. Am Ende immer eine Abschlussaufgabe (QS mit
   `qs-sicherheit`, `qs-korrektheit`, `qs-wartbarkeit` nacheinander, Doku abgleichen,
   Abschlussbericht).
3. **Größe je Aufgabe schätzen:** S / M / L. Startwerte (Anteil am 5-h-Fenster, gemessen
   14./15.10.2026): **S ≈ 15 %, M ≈ 20 %, L ≈ 30 %**. Mit Sicherheitsrunde eher eine Stufe höher.
4. **Aufgabenliste** als Datei anlegen (enthält sie Sicherheitsdetails: in `_unveroeffentlicht/`).
   Inhalt: Statustabelle (Aufgabe | Größe | Status | Commit | Limit vorher → nachher | Bemerkung),
   Kalibrierung, Entscheidungen, Rückfragen an Marco, Hinweise für den Abschlussbericht, je
   Aufgabe die Befunde mit Kurzbeschreibung der Lösung. Status: offen / läuft / erledigt /
   zurückgestellt (mit Grund).
5. **Statuszeile einrichten** (einmalig je Rechner): `statusline-shs.ps1` aus diesem Ordner nach
   `%USERPROFILE%\.claude\` kopieren und in `%USERPROFILE%\.claude\settings.json` eintragen:
   ```json
   "statusLine": { "type": "command",
     "command": "powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:/Users/<Name>/.claude/statusline-shs.ps1" }
   ```
   Das Skript zeigt „5h: N % | 7T: N %“ und schreibt `rate_limits` nach
   `%USERPROFILE%\.claude\shs-limit.json` (`five_hour`/`seven_day` mit `used_percentage` und
   `resets_at` als Unix-Zeit). Fehlt `five_hour`, hat ein neues Fenster begonnen (≈ 0 %).
6. **Start** durch Marco: `/loop Arbeite die nächste offene Aufgabe aus <Liste> nach dem dort
   beschriebenen Ablauf ab.` (dynamischer Modus, jede Runde endet mit `ScheduleWakeup`).

## 2. Limitregel

- Weiter nur, wenn **Nutzung + Schätzung + 3 % ≤ 100 %** (5-h- und 7-Tage-Wert).
- Passt die nächste Aufgabe nicht, aber eine kleinere offene: diese vorziehen und vermerken.
- Passt keine: `ScheduleWakeup` bis `resets_at` (höchstens 3600 s je Schritt, `noop: true`),
  kurz nach dem Reset weiter. Lieber warten als eine Aufgabe knapp anfangen.
- Vor der Verifikation einer Aufgabe das Limit erneut lesen; Subagents zählen mit.
- Bricht das harte Limit mitten in einer Aufgabe ab: nächste Runde setzt bei „läuft“ fort
  (`git status`/`git diff` prüfen, nicht neu beginnen).
- Nach jeder Aufgabe den gemessenen Verbrauch eintragen und die Schätzwerte nachjustieren.

## 3. Ablauf je Aufgabe

1. Limit prüfen, Status auf „läuft“, Limit-vorher eintragen.
2. **Explore-Subagent** liefert Befundtexte und aktuelle Code-Stellen (Zeilennummern in
   Berichten veralten). Immer nur **ein** Subagent gleichzeitig; auf seine Meldung warten
   (Rückfall-Wecker 1800 s).
3. **Umsetzen**, am besten per Python-Skript im Temp-Ordner mit eindeutigen Ersetzungen
   (Treffer zählen, Zeilenenden CRLF/LF der Datei erhalten). Skripte mit dem Write-Werkzeug
   anlegen, nicht per Heredoc (verfälscht Backslashes und Escape-Folgen).
4. **Tests** zu jedem Befund, lokaler Unittest-Befehl aus `CLAUDE.md`, GUI-Tests mit
   `QT_QPA_PLATFORM=offscreen` und Zeitgrenze (modale Dialoge hängen sonst). **Gegenprobe:**
   Programmdateien per `git stash push <dateien>` zurücknehmen, die neuen Tests müssen
   scheitern, dann `git stash pop` (danach Zeilenenden prüfen).
5. **Verifikation** mit `verifikation`, bei [S] zusätzlich `qs-sicherheit`. Befunde innerhalb
   der Aufgabe beheben; neue Punkte außerhalb als Aufgabe an passender Stelle eintragen;
   fachlich Unklares in „Rückfragen an Marco“, Teilpunkt zurückstellen, weiter.
6. **Dokumentieren:** Abschnitt in `Fortschritt.md` (Sicherheitsfunde nur allgemein), bei
   geänderter Bedienung `docs/HANDBUCH.md`, bei Struktur `Architektur.md`.
7. **Commit** lokal, Nachricht über eine Datei (`git commit -F`), mit Attribution-Footer. Kein
   Push, Tag, Versionsbump oder Build.
8. Status, Commit und „Limit vorher → nachher“ in der Liste eintragen; kurze Meldung an Marco;
   nächste Runde per `ScheduleWakeup` (60 s, wenn das Limit reicht).

## 4. Abschluss

Wenn alle Aufgaben erledigt oder zurückgestellt sind: Loop mit `ScheduleWakeup(stop: true)`
beenden, Abschlussbericht (Commits, zurückgestellte Punkte, Rückfragen, ausstehende
Sichtprüfungen, Screenshots vor dem nächsten Build, Push-Hinweis bei Sicherheitstests) und eine
PushNotification an Marco.
