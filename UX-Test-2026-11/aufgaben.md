# Aufgabenliste UX-Test 2026-11 (Rubrik ux_test_2026_11, X1–X16)

Abarbeitung nach dem Skill `aufgaben-abarbeitung`. Quelle: [Bericht.md](Bericht.md). Keine
Sicherheitsbefunde. Kein Push, Tag, Versionsbump oder Build. Die Code-Signatur (X16) ist
ausgenommen (Marco 03.11.2026: mit dem Installer derzeit nicht lösbar).

**Limit:** Die Statuszeilen-Datei `shs-limit.json` wird in der Desktop-App nicht geschrieben. Das
Limit kommt deshalb aus `mcp__ccd_session_mgmt__get_usage` (5-h- und Wochenwert). Regel: Nutzung
+ Schätzung + 3 % ≤ 100 %. Schätzwerte: S ≈ 15 %, M ≈ 20 %, L ≈ 30 % des 5-h-Fensters.

## Status

| Aufgabe | Punkte | Größe | Fenster | Status | Commit | Limit vorher → nachher | Bemerkung |
|---|---|---|---|---|---|---|---|
| A1 | X3 ED-Gegenstand nach PDF-Import | S | 1 | offen | | | R1 |
| A2 | X5, X7, X8 Ergebniserfassung | M | 1 | offen | | | |
| A3 | X4, X11, X12 Teilnehmer-Dialog | M | 1 | offen | | | R2: vorbelegen + markieren |
| A4 | X1 Mittagspause | S | 2 | offen | | | R3: weglassen |
| A5 | X2 Schriftgröße | L | 2 | offen | | | |
| A6 | X6 Demo-Tempo | S | 2 | offen | | | R4: nur Text zurück |
| A7 | X9, X13 Tauschen, Teilnehmerzahl | S | 3 | offen | | | |
| A8 | X10 Import-Meldungen | S | 3 | offen | | | |
| A9 | X14, X15 Hilfe und Kleinigkeiten | M | 3 | offen | | | |
| A10 | X16 Installationstexte (ohne Signatur) | S | 3 | offen | | | Website erst mit dem Release online |
| A11 | Abschluss: QS 3 Rollen, Doku, Screenshot-Liste, Bericht | L | 4 | offen | | | |
| A12 | UX-Nachtest mit 2 Personas (Laie ohne, Normal ohne Handbuch) | L | 4 | offen | | | |

## Je Aufgabe

**A1 – X3 (S):** Beim PDF-Import einer ED-Meldung `gegenstand_1_disziplin` = ED-Disziplin setzen
(`db_import.py` ~717–735). DK bleibt „frei“. Handbuch Z. ~387 („ED (ältere Daten)“) präzisieren.
Test: PDF-Import ED → kein Hinweis aus `teilnehmer_gegenstand_hinweis`.

**A2 – X5, X7, X8 (M):** Ergebniserfassung in `app.py`.
- X5: Abbruch-Zelle öffnet mit **einem** Klick (Klick auf die Spalte startet `edit()`); leere Zelle
  zeigt „– wählen –“ mit Pfeil; Spaltenbreite bzw. Tooltip mit vollem Grund prüfen. Handbuch
  Z. ~633 angleichen.
- X7: Wird ein Wert über dem Maximum getippt, zusätzlich zum roten Rahmen der Klartext im
  `hinweis_label` („Höchstens 60 Punkte“), nicht nur als Tooltip.
- X8: Der Komma-Hinweis bleibt stehen, bis die Zelle verlassen wird (nicht bei der nächsten Ziffer
  ausblenden).
Tests in `test_app_gui.py` je Punkt mit Gegenprobe.

**A3 – X4, X11, X12 (M):** `TeilnehmerDialog` in `desktop_dialoge.py`.
- X4: Bei ED neben den gesperrten Feldern der Text „Bei Einzeldisziplin nur ein Gegenstand“
  (Label + Tooltip), gesperrte Felder deutlicher.
- X11: Startnummer außerhalb des Bereichs der gewählten Prüfung → Rückfrage beim Speichern
  („liegt außerhalb 41–60 für Trümmer LK 1 – trotzdem speichern?“, Vorgabe Nein). Nur wenn Bereiche
  festgelegt sind.
- X12: nach R2.

**A4 – X1 (S):** `add_zeitplan_pause_bei_allen` / `_pause_hinzufuegen`: Endet der Plan eines
Richters vor der Pausenzeit, nach R3 verfahren. Handbuch Zeitplan anpassen.

**A5 – X2 (L):**
- „Ansicht → Schriftgröße“ (Normal / Groß / Sehr groß, Faktor 1,0 / 1,15 / 1,3) in QSettings.
- Der Faktor wirkt in `_responsive_schriftgroesse`, der Ergebnistabelle und den festen
  `setPointSize`-Stellen.
- Hilfe-Text und Starttipp berichtigen („im Hauptfenster“, Verweis auf die Windows-Skalierung).
- Spaltenbreiten bei „Sehr groß“ prüfen.
- Sichtprüfung per Screenshots; Handbuch-Abschnitt „Aussehen“.

**A6 – X6 (S):** Countdown nach Textlänge (etwa 0,35 s je Wort, mindestens 10 s, höchstens 40 s).
Prüfen, warum Enter bei N-B nichts bewirkte (`weiter_btn` ist Default). „Zurück“ nach R4.

**A7 – X9, X13 (S):**
- X9: `StartnummerTauschenDialog` ohne Vorauswahl, „OK“ erst nach einer Wahl.
- X13: Startbildschirm zählt wie der Kopfbalken die Teilnehmenden und zeigt Abgemeldete als
  Zusatz, z. B. „16 (+1 abgemeldet)“. Vorschlag; Marco kann widersprechen.

**A8 – X10 (S):** `_meldung_mit_listen`:
- Bei Ablehnungen das Warnsymbol statt „i“.
- Knopf „Liste kopieren“ (Zwischenablage).
- Bei Formularfehlern der Rat „bitte beim Teilnehmer nachfragen und von Hand erfassen“.
- Einzahl „1 Teilnehmer hat“.
- Startnummern-Rückfrage nur, wenn gerade importierte Teilnehmer ohne Nummer sind.

**A9 – X14, X15 (M):**
- Hilfe:
  - Inhaltsverzeichnis mit Sprungmarken.
  - „Löschen…“ → Papierkorb.
  - „gewählte Richter“ → „alle Richter“.
  - Doppelte Stellen prüfen.
- Kleinigkeiten:
  - Datum „14.11.26“ als 2026 akzeptieren (Vorschlag).
  - „Fehlende Angaben“ nennt nur fehlende Felder.
  - „Offene Starts“ breiter.
  - Versionsfenster: Default „Schließen“.
  - Tooltip „Dort“ → „Im Reiter Verwaltung“.
  - Startbildschirm: bei genau einem Termin diesen vorauswählen.
- Bleibt wie es ist: Name der Sicherungsdatei und sofortige Spalte bei „Richter hinzufügen“.

**A10 – X16 (S):**
- Website und Handbuch Kap. 2 für Laien: Schritt-für-Schritt mit Bild zur Browserwarnung, „Assets“
  erklären, Update-Weg „Version …“ hervorheben.
- „GitHub-Releases-Seite“ einfacher benennen.
- Website-Teil erst mit dem nächsten Release pushen (Regel 07.10.).

**A11 – Abschluss (L):**
- QS mit `qs-sicherheit`, `qs-korrektheit`, `qs-wartbarkeit` nacheinander.
- `Architektur.md` und Handbuch abgleichen.
- Liste der Screenshots, die vor dem nächsten Build neu müssen.
- `OFFEN.md` und Rubrik nachziehen, Abschlussbericht.

**A12 – Nachtest (L):** Harness aus dem Scratchpad neu aufsetzen, Laie ohne Handbuch (Werner) und
Normal ohne Handbuch (Tobias), Szenario wie 03.11., Bericht `Nachtest.md`.

## Entscheidungen

- 03.11.2026 Marco: Code-Signatur ausgenommen.
- R1 (X3): Die Entscheidung vom 28.09. („Gegenstände als frei“) bleibt für DK. Bei ED wird der
  Gegenstand der einzigen Disziplin zugeordnet – fachlich eindeutig, kein Widerspruch.
- R2 (X12), Marco 03.11.: **Vorbelegen + markieren.** Bei Neuanlage wird die erste angebotene
  Prüfung vorbelegt. Darunter steht im Klartext, ob die gewählte Kombination angeboten wird. Die
  drei Felder bleiben.
- R3 (X1), Marco 03.11.: **Dann weglassen.** Erreicht der Plan eines Richters die Pausenzeit
  nicht, bekommt er keine Pause. Die Meldung nennt, bei wem sie fehlt. Das ersetzt die
  Nachtest-Entscheidung N3 (Pause am Ende + Meldung).
- R4 (X6), Marco 03.11.: **Nur Text zurück.** Ein Knopf „Vorigen Text zeigen“ blättert die
  Erklärung zurück, die Demo läuft vorwärts. Dazu kommt der Countdown nach Textlänge.
- Start, Marco 03.11.: **jetzt, limitgesteuert.**

## Rückfragen an Marco

- (keine offen)
