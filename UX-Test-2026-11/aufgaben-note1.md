# Aufgabenliste „Note 1“ (UX-Test 2026-11, Start 04.11.2026)

Abarbeitung nach dem Skill `aufgaben-abarbeitung`. Grundlage: [note1-todos.md](note1-todos.md)
mit Marcos Entscheidungen vom 04.11.2026. Rubrik in `Fortschritt.md`: `ux_test_2026_11 B…`.
Kein Push, Tag, Versionsbump oder Build. Website-Änderungen unter `docs/` gehen erst mit dem
Release online.

Start per `/loop Arbeite die nächste offene Aufgabe aus UX-Test-2026-11/aufgaben-note1.md nach dem Skill aufgaben-abarbeitung ab.`

## Status

| Aufgabe | Inhalt | Größe | Status | Commit | Limit vorher → nachher | Bemerkung |
|---|---|---|---|---|---|---|
| B1 | T3 + T4 Ergebniserfassung | M | erledigt | 916d954 | 38 → 55 % | C24 teilweise; R-B1; real ≈ 17 % |
| B2 | T6 + T7 Teilnehmer-ED und Meldestelle | S | erledigt | eaa2d5b | 55 → 65 % | real ≈ 10 % (inkl. CVE-Rückfrage) |
| B3 | T9 + T10 + T11 Version, Sicherungstext, Dateiname | M | erledigt | 96db049 | 65 → 80 % | real ≈ 15 %; Enter-Fehler N5 echt, behoben |
| B4 | T2 Import-Ablehnungen nachlesbar | M | erledigt | 76ae4d6 | 9 → 17 % | R-B4 |
| B5 | T1 Zeitplan: Bestätigung und Pausenfeld | M | erledigt | 170f9bc | 17 → 26 % | |
| B6 | T8 Hilfe mit Suche und F1 | M | erledigt | 082fed2 | 31 → 40 % | |
| B7 | T14 Kleinigkeiten (R7) | S | erledigt | 5b8823c | 80 → 85 %, 0 → 9 % | vor B4 gezogen; R-B7 (Befundnummern) |
| B8 | T5 Auswahl „Prüfung“ | L | erledigt | 1077eb9 | 40 → 52 % | ersetzt R2; R-B8 |
| B9 | T12 Demo mit echtem Zurück | L | erledigt | 1a7675f | 52 → 67 % | ersetzt R4 |
| B10 | T13 Kurzanleitung Installation (PDF) | M | erledigt | 48fa7a5 | 67 → 76 % | Website erst mit dem Release; R-B10 |
| B11 | Abschluss: QS 3 Rollen, Doku, Screenshot-Liste, voller Testlauf | L | erledigt | (siehe Log) | 0 → 16 % | QS-Befunde K1–K3 und Wartbarkeit als Q1–Q4 an Marco |
| B12 | T15 Nachtest mit Heinz, Sabine, Julia, Gerda, Werner | L | offen | | | Harness aus dem Scratchpad; Werner auf Marcos Wunsch 04.11. dazu, ggf. über zwei Limit-Fenster |

## Kalibrierung

Startwerte S ≈ 15 %, M ≈ 20 %, L ≈ 30 % des 5-h-Fensters (Erfahrung A1–A13: oft weniger).
Regel: Nutzung + Schätzung + 3 % ≤ 100 % (5 h und Woche), Limit über `get_usage`.

## Aufgaben

**B1 – T3, T4 (M):** Ergebniserfassung.
- Spalte „Status“ zeigt bei DQ „disqualifiziert“ und bei Abbruch „Abbruch: <Grund>“ statt nur
  „gespeichert“.
- Die Speichermeldung zählt Teilnehmer („16 Teilnehmer gespeichert“), nicht Disziplinen.
- Abbruch-Spalte so breit, dass der Grund nicht abgeschnitten wird (Tooltip mit vollem Text).
- T4: Werte über dem Höchstwert schon beim Tippen markieren (roter Rahmen am Editor, Text
  „höchstens N Punkte“); Eingabe bleibt möglich. C24 in `OFFEN.md` als erledigt austragen.

**B2 – T6, T7 (S):**
- T6: ED-Gegenstand 1 mit Komma, „und“ oder „/“ → Rückfrage „Bei ED ist nur ein Gegenstand
  erlaubt. Trotzdem so speichern?“ (Vorgabe Nein).
- T7: Rückfrage bei leerem Verband/Meldestelle beim Termin-Anlegen mit Vorgabe „Nein“; beim
  Erzeugen des Anmeldeformulars ohne Meldestelle noch einmal warnen.

**B3 – T9, T10, T11 (M):**
- T9: Menüpunkt „Hilfe → Nach Updates suchen“. Im Versionsfenster Diagnose- und Protokoll-Knöpfe
  in einen Bereich „Für Fehlermeldungen“. Enter-Verhalten im Test absichern.
- T10: Text der Datensicherung: Passwort klar als freiwillig („auf Wunsch mit Passwort“).
- T11: Vorschlag für den Dateinamen `SHS-Sicherung_<Datum>_<Umfang>.zip` (Umfang z. B.
  „alle-Termine“ bzw. Terminname), änderbar.

**B4 – T2 (M):** Im Reiter „Formular-Import“ ein Bereich „Letzter Import“ mit vollständiger
Liste (abgelehnt, bereits vorhanden, Hinweise) und Knopf „Kopieren“; bleibt bis zum nächsten
Import (nur im Speicher der Sitzung).

**B5 – T1 (M):** Nach „Automatisch verteilen…“ ausdrückliche Bestätigung „Keine
Überschneidungen, alle N Starts eingeplant“ (bzw. was fehlt). Im Verteilen-Dialog optional
„Mittagspause um … für … Minuten“; beim Verteilen wird sie wie die Pause bei allen eingefügt
und bleibt beim Neu-Verteilen erhalten.

**B6 – T8 (M):** Hilfe mit Suchfeld (Treffer hervorheben, weiter springen). F1 öffnet die Hilfe
beim Abschnitt des aktuellen Reiters.

**B7 – T14 (S):** Stilpunkte der Wartbarkeits-QS aus `Fortschritt.md` („A11 – Abschluss-QS“);
Web- und Postgres-Übersicht zählen Abgemeldete wie der Desktop; Demo zeigt die
Angebotsmarkierung im Teilnehmer-Dialog.

**B8 – T5 (L):** Teilnehmer-Dialog: eine Auswahl „Prüfung“ mit den angebotenen Prüfungen des
Termins in dessen Schreibweise; Eintrag „andere …“ blendet Art/LK/Disziplin ein. Bei
Bearbeitung einer nicht angebotenen Prüfung direkt „andere …“. Prüfungsnamen überall
einheitlich. Ersetzt R2 (die Auswahl beginnt weiter mit der ersten angebotenen Prüfung). Handbuch und Screenshots nachziehen.

**B9 – T12 (L):** Demo: „Vorheriger Schritt“ spielt den letzten Schritt zurück (Zustand vor dem
Schritt wiederherstellen, z. B. über Sicherungspunkte der Demo-Datenbank je Schritt). Ersetzt
„nur Text zurück“ (R4).

**B10 – T13 (M):** Bebilderte Kurzanleitung „Installation in 5 Schritten“ als PDF zum
Ausdrucken (`docs/`), mit Bildern der Download-, Browser- und SmartScreen-Hinweise. Echte
Bildschirmfotos der Windows-Warnungen kann die Sitzung nicht aufnehmen: nachgestellte
Abbildungen, gekennzeichnet; sonst Rückfrage an Marco und Teilpunkt zurückstellen.

**B11 – Abschluss (L):** QS mit `qs-sicherheit`, `qs-korrektheit`, `qs-wartbarkeit`; Doku
abgleichen; Screenshot-Liste für den Build; voller Unit- und GUI-Testlauf.

**B12 – T15 (L):** Nachtest mit Heinz (E-A), Sabine (E-B), Julia (N-A), Gerda (L-A) und Werner
(L-B3, Marco 04.11.2026; Vergleich mit L-B und L-B2) über die
Harness, Bericht `Nachtest2.md`, Noten mit dem ersten Test vergleichen.

## Rückfragen an Marco

- **R-B1 (optional, aus der Verifikation B1):** (a) Designwechsel bei offenem Eingabefeld: der rote
  Rahmen behält bis zum nächsten Tastendruck die alte Farbe (Kosmetik). (b) Sortieren nach
  „Status“ gruppiert jetzt „Abbruch: …“ und „disqualifiziert“ eigens – so lassen? (c) Test für die
  Zählung „N Teilnehmer gespeichert“ nach einem Datenbankfehler mitten im Speichern ergänzen?
  Vorschlag: (a) lassen, (b) lassen, (c) in B11 ergänzen.
- **R-B7 (aus B7):** „Befundnummern in Code-Kommentaren“ (letzter Stilpunkt der Wartbarkeits-QS)
  nicht umgesetzt – sie zu entfernen träfe das ganze Projekt und nähme die Verbindung zu
  `Fortschritt.md`. Vorschlag: so lassen (Projektstil).
- **R-B4 (aus B4):** Bei Abbruch oder Datenbankfehler mitten im Import bleibt unter „Letzter
  Import“ das vorige Ergebnis stehen (Uhrzeit zeigt es). Vorschlag: so lassen.
- **R-B8 (aus B8):** Prüfungsnamen sind im Teilnehmer-Dialog jetzt wie im Anmeldeformular
  („Trümmer LK 1“); Teilnehmerliste, Zeitplan und Auswertung schreiben weiter „ED LK 1 –
  Trümmerfeld“. Vereinheitlichen (betrifft auch PDFs) oder so lassen? Vorschlag: so lassen.
- **R-B10 (aus B10):** Für die Kurzanleitung fehlen echte Bilder der Chrome-Download-Warnung und
  der SmartScreen-Meldung (die Sitzung kann sie nicht aufnehmen). Nimmst du sie beim nächsten
  Download auf (`docs/bilder/handbuch_chrome_download.png`, `handbuch_smartscreen.png`)?
  → Marco 04.11.: SmartScreen-Bilder geliefert und eingebunden; Chrome warnt derzeit nicht
  mehr (auch bei den letzten Versionen nicht, Erweiterter Schutz an) – kein Chrome-Bild nötig;
  R-B10 erledigt.
- **Q1 (K1, mittel, aus B11):** Demo: „Schritt zurück“ aus Schritt 10/11 verliert die in Schritt 8
  nur getippten Punkte, die Demo endet dann ohne Stechen. Vorschlag: Liegt das Ziel nach Schritt 8,
  auf den Beginn von Schritt 8 zurückgehen (einfach, robust); dazu ein Test 10→ und 11→ bis zum Ende.
- **Q2 (K2, niedrig–mittel):** Mittagspause beim Verteilen: Meldung nennt immer die Wunschzeit.
  Vorschlag: abweichende tatsächliche Zeiten je Richter nennen wie bei „Pause bei allen Richtern“,
  über einen gemeinsamen Helfer (erledigt zugleich den Wartbarkeitspunkt „doppelte Pausen-Logik“).
- **Q3 (K3, niedrig):** Verteilen ohne Teilnehmer meldet „Alle 0 Prüfung(en) … eingeplant“.
  Vorschlag: Hinweis „Noch keine Teilnehmer – nichts zu verteilen.“
- **Q4 (Wartbarkeit, niedrig):** veralteter Modul-Docstring in `desktop_demo.py` („läuft nur
  vorwärts“), doppelte Verband/Meldestelle-Prüfung (gemeinsame Funktion), Kommentar mitten im
  `_ja_nein`-Aufruf, `ERSTER_SCHRITT_IM_TERMIN` zu den Klassenkonstanten, Sicherungsname-Test
  prüft „Verein nicht im Namen“, doppeltes `aktualisieren()`/Statustext nach dem Verteilen.
  Vorschlag: alles umsetzen (klein). Nicht vorgeschlagen: „Letzter Import“ aus `app.py`
  auslagern (eigene Aufräumaufgabe) und Mittagspause am Namen erkennen (so lassen, Kommentar ergänzen).
