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
| B11 | Abschluss: QS 3 Rollen, Doku, Screenshot-Liste, voller Testlauf | L | erledigt | b2fe6f3 | 0 → 16 % | QS-Befunde K1–K3 und Wartbarkeit als Q1–Q4 an Marco |
| B12 | T15 Nachtest mit Heinz, Sabine, Julia, Gerda, Werner | L | erledigt | c472344 | 16 → 76 %, 0 → 41 % | Bericht Nachtest2.md; je Persona ≈ 17–22 % | Harness aus dem Scratchpad; Werner auf Marcos Wunsch 04.11. dazu, ggf. über zwei Limit-Fenster |
| B13 | Q1–Q4 aus der Abschluss-QS (Demo-Zurück, Pausenmeldung, Verteilen ohne Teilnehmer, Aufräumen) | M | erledigt | 7a2d700 | 35 → 45 % | Marco 04.11.; nach dem Lauf Heinz, vor Sabine |
| B14 | N1 + N2 + N8 Ergebniserfassung: Abbruch-Spalte breit, kompakt bei großer Schrift, Komma ablehnen | M | erledigt | (dieser Commit) | 50 → 76 % | real ≈ 26 % (zwei Messfehler-Suchen) |
| B15 | N4 + N7 + N13 + N15 Tausch-Warnung, Richtername, Reset-Text, Entf löscht | M | erledigt | 8273862 | 0 → 14 %, real ≈ 14 % | R-B15 (Web-Status, Entf am Mac) |
| B16 | N6 + N11 + N12 Hilfe (Knopf, Suche, Texte), Gegenstand-Texte, Rat bei Ablehnung | M | erledigt | f5fae0d | 14 → 30 %, real ≈ 16 % | R-B16 (ED-Satz „Anmerkungen“) |
| B17 | N9 + N10 Demo-Texte/Beenden, Zählung nach Prüfungen und Teilnehmern | S | erledigt | 506c064 | 30 → 43 %, real ≈ 13 % | |
| B18 | N5 Prüfungsnamen überall einheitlich | L | erledigt | 19c410f | 43 → 62 %, real ≈ 19 % | ersetzt R-B8 |
| B19 | N14 Termin-Dialog ohne Bildlauf, Seitenleiste „Offene Starts“ breiter | M | erledigt | 03e6400 | 62 → 81 %, real ≈ 19 % | Demo-Erklärfenster auf 1366 ansehen |
| B20 | N16 Pause zu fester Uhrzeit (Block wird geteilt) | L | zurückgestellt | | 0 → 3 % | R-B20: braucht Datenmodell-Entscheidung |
| B21 | N3 Kurzanleitung: Website-Knopf, GitHub-Bild | S | erledigt | 0ed334c | 3 → 13 %, real ≈ 10 % | R-B21 (Bild auch auf der Website?) |
| B22 | Abschluss 2: QS 3 Rollen über B14–B21, Doku, Tests | L | erledigt | b3fcd1f | 13 → 27 %, real ≈ 14 % | QS-Befunde K1, W1–W10 zur Entscheidung |
| B23 | K1 + W4 Punkteingabe: Komma hinter einstelligem Wert, `_PunkteFeld` | M | erledigt | 9126bbf | 49 → 59 %, real ≈ 10 % | |
| B24 | W1–W3 + W8 Prüfungsbezeichnung/Sortierung zentral, Imports | S | erledigt | 443b1c1 | 59 → 66 %, real ≈ 7 % | |
| B25 | W5–W7 Tausch-Bereichsprüfung auslagern, Docstrings, Tests | S | erledigt | 1cd8597 | 66 → 73 %, real ≈ 7 % | |
| B26 | R-B20: feste Pause mit Lücke (Option „genau“, Schwelle 15 Min.) | M | erledigt | 75ff0e9 | 73 → ~90 %, real ≈ 17 % | R-B26 optional |

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
  → Marco 04.11.: vereinheitlichen (N5), umgesetzt in B18.
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
  → **Marco 04.11.2026: Q1–Q4 wie vorgeschlagen umsetzen** (als B13, zwischen den Nachtest-Läufen, damit kein Lauf halb geänderten Code lädt).
- **Nachtest 2 (B12):** neue bzw. verbliebene Funde N1–N16 in `Nachtest2.md` – je Fund umsetzen, zurückstellen oder verwerfen? N5 betrifft erneut R-B8 (Prüfungsnamen, von 4 Personas gemeldet).
- **R-B15 (aus B15):** (a) N13 „Web-Hinweis nur, wenn veröffentlicht“: Die Termin-Datei weiß nicht,
  ob sie im Web veröffentlicht wurde (die Veröffentlichung lädt eine Kopie hoch; von der
  Verifikation bestätigt). Umgesetzt ist deshalb „Nur falls der Termin schon im Web veröffentlicht
  ist: …“. Reicht das, oder soll die Desktop-Version beim Veröffentlichen etwas vermerken (ginge
  nur von Hand, z. B. ein Häkchen „im Web veröffentlicht“)? Vorschlag: so lassen.
  (b) Entf löscht in der Teilnehmerliste; auf dem Mac ist die „delete“-Taste aber die Rücktaste,
  die das Kürzel nicht auslöst. Für die Mac-Vorschau zusätzlich Rücktaste? Vorschlag: so lassen,
  bis jemand am Mac danach fragt.
- **R-B16 (aus B16, N11):** „Weiteren Gegenstand ggf. unter Anmerkungen notieren“ – ein Feld
  „Anmerkungen“ gibt es im Teilnehmer-Dialog nicht; die gleichnamige Spalte der Liste füllt das
  Programm selbst (Chip-Nr. fehlt, Gegenstand noch offen). Die ED-Rückfrage ist deshalb
  unverändert. Möglichkeiten: (a) so lassen, (b) Rat „mit dem Teilnehmer klären“ ohne Ort,
  (c) doch ein freies Notizfeld „Bemerkung“ (neues Datenbankfeld, auch in Export und Web).
  Vorschlag: (b).
- **R-B20 (B20, N16 zurückgestellt):** Ein Prüfungsblock umfasst heute immer **alle** Teams einer
  Prüfung (live nach Art/LK/Disziplin, nur mit Startversatz) – einen laufenden Block um 12:00 zu
  teilen, geht ohne Änderung am Datenmodell nicht. Möglichkeiten:
  (a) **Teilen wie entschieden:** neues Feld „Anzahl Teams“ je Block (Teil 1 die ersten k Teams,
  Teil 2 der Rest; neue Teilnehmer landen im Rest). Braucht Migration (SQLite und PostgreSQL),
  Anpassungen bei Berechnung, Anzeige, „Hoch/Runter/Entfernen“ (wirken heute auf den ganzen
  Block), „Offene Starts“ und beim Verteilen. Größe eher L+ (≈ 40 %).
  (b) **Feste Pause ohne Teilen** (Sabines eigentlicher Wunsch „12:00 mit Lücke davor“): Eine
  Pause kann eine feste Uhrzeit haben; ist der Richter früher fertig, entsteht davor eine Lücke
  („frei bis 12:00“); läuft um 12:00 noch ein Block, beginnt die Pause nach dem Team, das
  gerade dran ist – geht nicht, ohne zu teilen, also nach dem Block (wie heute, Meldung nennt die
  Zeit). Braucht nur ein Feld „fest um“ für Pausen. Größe M.
  (c) So lassen (die Meldung nennt die tatsächliche Pausenzeit, seit B13).
  Vorschlag: (b) – deckt den gemeldeten Wunsch mit deutlich weniger Risiko ab.
  → **Marco 05.11.2026: (b)**, und auf Rückfrage zum um 12:00 laufenden Block: **je nach Restzeit** –
  hat er weniger als 15 Minuten vorher begonnen, rückt er als Ganzes hinter die Pause (Lücke davor),
  sonst folgt die Pause nach ihm. Umsetzung als B26.
- **R-B26 (aus der Verifikation B26, optional):** (a) Pläne über Mitternacht: feste Pausenzeit
  bezieht sich auf den Tag der laufenden Planzeit (praxisfern). (b) Rückt ein DK-Block hinter die
  feste Pause, bleibt eine Mindestabstands-Wartezeit davor stehen (Überschneidungsprüfung zeigt
  Probleme). (c) Feste Uhrzeit beim Bearbeiten nicht änderbar (Handbuch nennt den Weg).
  Vorschlag: alles so lassen.
- **R-B21 (aus B21, optional):** Das neue Bild der Release-Seite (Kasten „Assets“) steht in
  Kurzanleitung und Handbuch. Soll es auch auf die Website (`docs/index.html`, Abschnitt
  Installation) und in die `README.md`? Ginge erst mit dem nächsten Release online. Vorschlag: ja,
  in `index.html` (dort beschreibt der Text denselben Weg ohne Bild).

## Entscheidungen zum Nachtest 2 (Marco 04.11.2026)

Alle Funde N1–N16 aus `Nachtest2.md` werden umgesetzt:

- **N1:** Abbruch-Spalte so breit wie der längste Grund (auch bei Schrift „Groß“), die Spalte „Status“ gibt Platz ab.
- **N2:** Spaltenbreiten der Ergebniserfassung bei „Groß“/„Sehr groß“ nach Inhalt, Bildlauf nur, wenn es nicht passt.
- **N3:** Kurzanleitung nennt den Download-Knopf der Website; GitHub-Bild mit „Assets“ nimmt die Sitzung selbst auf; Setup- und neues Edge-Bild nimmt Marco beim nächsten Release auf.
- **N4:** „Startnummer tauschen…“ fragt bei verschiedenen Prüfungen nach (Vorgabe Nein, Bereiche genannt, Hinweis auf gespeicherte Ergebnisse); danach Statuszeile „Nr. X und Y getauscht“.
- **N5:** Prüfungsnamen überall einheitlich wie im Anmeldeformular („Trümmer LK 2“, „DK LK 1“) – Listen, Filter, Zeitplan, Auswertung, PDFs. Ersetzt R-B8.
- **N6:** Knopf „Hilfe“ öffnet wie F1 beim aktuellen Reiter; Suche zuerst ganze Wörter bzw. Wortanfänge; Abschnitt „Tastenkürzel“ und USB-Stick bei der Sicherung ergänzen; Treffer kräftiger markieren.
- **N7:** „Richter hinzufügen“ fragt den Namen ab (leer erlaubt); Richter ohne Einträge stehen nicht im Zeitplan-PDF.
- **N8:** Punkteingaben mit Komma oder Buchstaben werden nicht übernommen, der alte Wert bleibt; Hinweis „nur ganze Zahlen“ passend zum Grund.
- **N9:** Demo-Text Schritt 3 an die Auswahl „Prüfung“ anpassen, Anzahl und Bereiche stimmig, „Beenden“ mit Rückfrage (Vorgabe Nein).
- **N10:** Bestätigung zählt Prüfungen (Dreikampf als eine) und Teilnehmer: „Alle 6 Prüfungen mit 16 Teilnehmern …“.
- **N11:** Nur Texte: ED-Rückfrage nennt „weiteren Gegenstand ggf. unter Anmerkungen notieren“, Erklärung zu „Gegenstand noch offen“, CSV-Meldung nennt das Nachtragen. Kein neues Feld.
- **N12:** Bei abgelehntem PDF ein konkreter Rat je Grund in der eigenen Zeile.
- **N13:** „Alle Startnummern zurücksetzen…“: Web-Hinweis nur, wenn veröffentlicht; vorhandene Ergebnisse nennen; Vorgabe Nein.
- **N14:** Termin-Dialog so, dass Prüfungen und Startnummern-Bereiche ohne Bildlauf sichtbar sind (z. B. zweispaltig/höher); Seitenleiste „Offene Starts“ breiter.
- **N15:** Entf in der Teilnehmerliste wirkt wie „Löschen“ (mit der bestehenden Rückfrage, Vorgabe Nein).
- **N16:** Pause zu fester Uhrzeit (im Pause- und im Verteilen-Dialog wählbar): Die Pause beginnt genau zur Uhrzeit; ein laufender Prüfungsblock wird dort geteilt, die übrigen Teilnehmer folgen nach der Pause. Ist ein Richter vor der Uhrzeit fertig, bekommt er keine Pause (wie bisher). Auslegung der Sitzung – bei Unklarheit zurückstellen und fragen.

## Abschluss 2 (B22): QS-Befunde zur Entscheidung (05.11.2026)

QS mit drei Rollen über `git diff 2fa38a3..HEAD` (B14–B21). **Sicherheit: keine Befunde.**
Nach Projektregel wird jeder Befund erst nach Marcos Go umgesetzt.

- **K1 (mittel, Korrektheit, N8):** Steht in einer Punktezelle schon „4“ und man tippt nach
  F2/Doppelklick hinter der 4 „,5“, wird 45 gespeichert – ohne Meldung (der Sonderfall „noch
  nichts getippt, Wert markiert“ greift, obwohl nicht mehr markiert ist). Bei zweistelligen Werten
  passiert es nicht. Vorschlag: Sonderfall nur bei leerem Feld oder ganz markiertem Wert;
  Test „4, Ende, ‚,5‘, Enter → 4 bleibt, Statuszeile meldet die Verwerfung“.
- **W1 (mittel):** Formular-Reihenfolge an ~13 Stellen von Hand übergeben; die Demo
  (`desktop_demo.py`, `stechen_gruppen(fertig)`) sortiert noch alphabetisch. Vorschlag:
  `db.sortiere_pruefungen(labels)` und überall nutzen, Demo angleichen.
- **W2 (gering):** „Bezeichnung → Prüfung“ dreimal einzeln gesucht. Vorschlag:
  `db.pruefung_nach_bezeichnung` und ein Index-Dict für den Sortierschlüssel.
- **W3 (gering):** Doppelter Rückfall in `db_import._angebot_pruefen` (und Hülle
  `app._pruefung_bezeichnung`). Vorschlag: nur `pruefung_bezeichnung(...)`.
- **W4 (mittel):** Punkteingabe N8 als Zustandsautomat aus vier Qt-Properties am `QLineEdit`.
  Vorschlag: kleine Unterklasse `_PunkteFeld` mit Attributen, Grund-Ermittlung als reine Funktion
  (ohne GUI testbar) – passt gut mit K1 zusammen.
- **W5 (gering):** Bereichsprüfung der Tausch-Warnung (N4) ist Qt-freie Logik in `app.py`.
  Vorschlag: `tausch_ausserhalb_bereich(...)` auslagern und einzeln testen.
- **W6 (gering):** Docstring `HilfeDialog` umständlich (Knopf und F1 tun dasselbe), Kommentar im
  `TeilnehmerDialog` unsauber umbrochen, `_fundstellen` ohne Docstring, Musterliste schwer lesbar.
- **W7 (gering):** Tests: Quelltext-Inspektion im Demo-Test, Hand-Monkeypatch im Dialoggrößen-Test,
  Tests rechnen Bildschirm-Faktoren (0,95/0,9/0,2/0,25) und Breiten-Zuschläge nach. Vorschlag:
  Faktoren als Modulkonstanten, echten Schritt-Text prüfen, `monkeypatch`.
- **W8 (Kleinigkeit):** Neue Imports nicht alphabetisch einsortiert; drei Leerzeilen in
  `pdf_export.py` nach dem Entfernen von `_ETIKETT_DISZIPLIN_KURZ`.
- **W9 (Kleinigkeit, optional):** Übersicht je LK nennt weiter „ED LK n“ (Sammelzeile, richtig) –
  ggf. im Handbuch erklären.
- **W10 (gering):** Vor dem Build Screenshots neu (`handbuch_termin_anlegen` jetzt 1080×900,
  alle Bilder mit Prüfungsnamen: Teilnehmer, Zeitplan, Auswertung, Ergebniserfassung, Demo,
  Export), dann `HANDBUCH.pdf`; `Architektur.md` könnte Seitenleistenbreite, Hilfe-Suche und
  Demo-Rückfrage nennen.

Vorschlag gesamt: K1 + W4 zusammen (eine Aufgabe M), W1–W3 + W8 zusammen (S), W5–W7 (S), W10 beim
Build; W9 so lassen.
→ **Marco 05.11.2026: wie vorgeschlagen** (B23 = K1 + W4, B24 = W1–W3 + W8, B25 = W5–W7; W10 beim Build, W9 bleibt).
