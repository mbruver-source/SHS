# Aufgabenliste: Umsetzung der Funde aus dem UX-Test Web (19.11.2026)

Grundlage: `Bericht.md` (Funde A1–G1) und die Einzelberichte in `personas/`. Jeder Punkt wurde am 19.11.2026
einzeln mit Marco besprochen; die Entscheidungen stehen unten und sind verbindlich (der Loop fragt nicht nach).
Ablauf nach dem Skill `aufgaben-abarbeitung`; die Regeln aus `CLAUDE.md` gehen vor.

**Start durch Marco:**
`/loop Arbeite die nächste offene Aufgabe aus berichte/UX-Test-2026-11-Web/aufgaben-umsetzung.md nach dem dort beschriebenen Ablauf ab.`

## Rahmen (mit Marco abgestimmt)

- **Basis-Commit:** Der Web-Ausbau samt UX-Bericht ist lokal committet (`cfe6a8a`, nicht gepusht). Der Loop
  startet also auf einem sauberen Arbeitsbaum; je Aufgabe ein lokaler Commit, die Gegenprobe per
  `git stash push <dateien>` ist sicher. **Kein Push, kein Tag, kein Versionsbump, kein Build.**
- **Limit:** `~/.claude/shs-limit.json` ist veraltet (seit 05.11.2026), die Statuszeile liefert keine Werte.
  Deshalb: **je Runde genau eine Aufgabe**, danach kurze Meldung an Marco und `ScheduleWakeup` (60 s). Bricht das
  harte Limit mitten in einer Aufgabe ab, setzt die nächste Runde bei „läuft“ fort (`git status`/`git diff`
  prüfen, nicht neu beginnen). Keine feste Pausezeit. Spalte „Limit“ bleibt „unbekannt“.
- **Ein Subagent gleichzeitig** (Explore, dann `verifikation`; bei [S] zusätzlich `qs-sicherheit`).
- **Test-Stack `shsux`** (Port 6443, Ordner `C:\Users\mbruv\Documents\Claude\UX-Test-Web\`) bleibt laufen und darf
  zum Nachstellen im eingebauten Browser genutzt werden. Das Zertifikat ist **nur im Browser-Tab `seed`** bestätigt:
  diesen Tab nie schließen, nur dort mit `https://localhost:6443` arbeiten. Zugänge in `uebergabe\zugaenge.md`,
  Aufräumbefehle in `stack-notizen.md`. **Marcos Stack (Port 5443, `shs-pruefungsprogramm-git_*`) nie anfassen.**
  Der Test-Stack läuft mit dem Image vom 19.11. (Stand vor den Änderungen); er dient nur zum Nachstellen des
  **alten** Verhaltens (B4, D3). Geänderte Web-Teile werden mit dem Flask-Testserver (eigener Port, Testdaten) im
  eingebauten Browser angesehen. Das `shsux`-Image darf neu gebaut werden, wenn es nötig ist (nur Projekt
  `shsux`, eigenes Image-Tag laut `stack-notizen.md`), Marcos Image nie.
- **Tests:** `C:\Users\mbruv\anaconda3\python.exe -m unittest test_db test_db_fassade test_db_postgres_wrapper test_backup test_pdf_export test_app_web test_bump_version test_shs_core test_bewertung_referenz test_altversionen test_drittlizenzen test_agents_spiegel test_web_sync test_ende_zu_ende_web`,
  GUI-Tests (`test_gui_web.py` u. a.) mit `QT_QPA_PLATFORM=offscreen` und Zeitgrenze; für den Gesamtlauf die SHS
  Test Suite (`run_tests.py --kompakt`). Code muss unter Python 3.11 laufen; Tests PostgreSQL-tauglich
  (`fetchall()`, Spaltennamen).
- **Doku je Aufgabe:** Abschnitt in `Fortschritt.md` (oben, unter dem 19.11.-Eintrag), `docs/HANDBUCH.md` bei
  geänderter Bedienung, `OFFEN.md`/`entscheidungen/` bei überholten Entscheidungen. Screenshots werden im Loop
  **nicht** neu aufgenommen, sondern in „Screenshots vor dem Build“ (unten) gesammelt.
- **Keine echten Namen** (nur erfundene Testdaten); vor jedem Commit `git diff --cached` kurz darauf ansehen.
- Unklares, das nicht in den Entscheidungen steht: Teilpunkt zurückstellen, in „Rückfragen an Marco“ eintragen,
  weiter.

## Statustabelle

| Nr | Aufgabe (Funde) | Größe | Status | Commit | Limit | Bemerkung |
|---|---|---|---|---|---|---|
| U1 | Einzelseite: Bogen-Knopf je Disziplin, Bestätigung nach Speichern (A1, B2-Teil) | M | offen | | unbekannt | |
| U2 | Einzelseite: Disqualifikation und Abbruch mit Grund (D1, B18 überholt) | M | offen | | unbekannt | |
| U3 | Teilnehmerliste: Status in vier Stufen (B2) | M | offen | | unbekannt | |
| U4 | Startseite, Navigation, Meldung „angelegt“, Anzeigen-Schalter (A2, A3, B1, F3) | M | offen | | unbekannt | |
| U5 | Ergebnistabelle mobil: feste Spalten, Sortierung, Bogen-Knopf, Scrollen (C1, C2, C4) | M | offen | | unbekannt | |
| U6 | Ergebnistabelle: Texte und Meldungen (B3, C3, D2) | S | offen | | unbekannt | |
| U7 | Bogen: nachstellen B4 und D3, Bogenkopf-Text, Kopfleiste (B4, D3, D4, A4) | M | offen | | unbekannt | |
| U8 | [S] Desktop Web-Verbindung: Passwort bis Programmende im Speicher, Hinweise im Dialog, E5 nachstellen (E4, E5, E6, Heinz F5) | L | offen | | unbekannt | mit `qs-sicherheit` |
| U9 | Desktop-Texte: Rückhol-Bericht und Fragen (E1, E2, E3, A5) | S | offen | | unbekannt | |
| U10 | Sammel-PDF: leere Bögen weglassen, Hinweis beim Klick (G1, B5) | S | offen | | unbekannt | |
| U11 | README_CONTAINER und Container-Skripte (F1, F2, F4) | S | offen | | unbekannt | nur Doku/Skripte |
| U12 | Admin sieht je Ergebnis, wer wann eingetragen hat (B6) | L | offen | | unbekannt | Daten + Web, SQLite und PostgreSQL |
| U13 | Abschluss: QS in drei Rollen, Doku-Abgleich, OFFEN.md/Entscheidungen, Abschlussbericht, Test-Stack aufräumen | L | offen | | unbekannt | |

## Entscheidungen (Marco, 19.11.2026)

Einzeln mit Marco entschieden: A1, A2, B2, B4/D3/E5 (Nachstellen), B5, B6, C1, C2, D1, E1, E4, G1 sowie A4, C4, F3
(„alles umsetzen“). Die übrigen Zeilen sind **Vorschläge der Sitzung, von Marco pauschal freigegeben** („passt
so“): A3, A5, B1, B3, C3, D2, D4, E2, E3, E6, Heinz F5, F1, F2, F4. Dort darf der Loop im Wortlaut nach Augenmaß
abweichen, nicht im Umfang.

| Fund | Entscheidung |
|---|---|
| A1 Bogen schwer zu finden | Einzelseite `/teilnehmer/<id>` bekommt je Disziplin einen deutlichen Knopf „Bewertungsbogen öffnen“; die Teilnehmerliste zusätzlich einen Bogen-Link je Disziplin. |
| A2 Startseite zeigt Anmeldung trotz Angemeldet-Sein | Angemeldete werden von `/` dorthin geleitet, wohin auch direkt nach der Anmeldung geleitet wird (mit gewähltem Termin zur Teilnehmerliste, sonst „Termin wählen“; Admin ohne Termin ebenso). |
| A3 „Termine“ und „Termin wechseln“ verwechselbar, Weg zur Tabelle | umsetzen: Navigation eindeutig beschriften (z. B. „Termine verwalten“ vs. „Termin wechseln“), Ergebnistabelle in der Navigation bzw. auf der Teilnehmerliste deutlich verlinken. |
| A4 Kopfleiste wandert weg (Tablet) | umsetzen: Kopfleiste bleibt beim Scrollen oben (sticky), ohne Inhalte zu verdecken. |
| A5 „Web“ im Desktop schwer zu finden | umsetzen: kurzer Hinweis in der Ergebniserfassung (z. B. „Erfassung im Web: Reiter Datensicherung → Web“). |
| B1 keine Meldung nach „Benutzer anlegen“ | umsetzen: Erfolgsmeldung „Benutzer <name> wurde angelegt.“ |
| B2 Status in der Liste, keine Bestätigung | **Vier Stufen:** „offen“, „teilweise“ (n von m Disziplinen), „bewertet“, „disqualifiziert“ bzw. „Abbruch“ in eigener Farbe. Einzelseite zeigt nach dem Speichern eine Meldung „Gespeichert“. |
| B3 „1 Zeile(n) gespeichert.“ | umsetzen: verständlich („Gespeichert: 2 Teilnehmer.“) und sichtbar (Meldung im Blick, z. B. Seite springt zur Meldung oder Meldung steht fest). Tests in `test_app_web.py` (Zeilen mit „Zeile(n) gespeichert“) anpassen. |
| B4 Fehlermeldung Höchstwert kaum lesbar | nachstellen; ist es nachstellbar → beheben (Meldung lesbar am Feld bzw. oben), sonst als Werkzeug-Eigenheit vermerken und schließen. |
| B5 Sammel-PDF ohne Rückmeldung, Datei als `.tmp` | nur Hinweistext nach dem Klick („PDF wird erstellt, kann einige Sekunden dauern“); der Dateiname gilt als Eigenheit des Test-Browsers (Server sendet den richtigen Namen). |
| B6 wer hat wann eingetragen | **umsetzen** (Marco): **je Teilnehmer und Disziplin** Konto und Zeitpunkt der letzten Änderung, **nur in der Web-Datenbank** (PostgreSQL bzw. der Web-Seite der Daten); nicht in die Termin-Datei, nicht beim Zurückholen, nicht im Desktop. **Nur Admins** sehen es (Tooltip o. ä. in der Ergebnistabelle). Migration für bestehende Web-Datenbanken; Altdaten ohne Angabe. |
| C1 Tabelle am Handy/Tablet zu breit | Feste Spalten: Start-Nr./Name und Kopfzeile bleiben beim Wischen stehen (sticky), größerer Bogen-Knopf, am Handy Hinweis „bequemer: Einzelseite je Person“. Keine Karten-Ansicht. |
| C2 Sortierung | Standard nach Start-Nr. aufsteigend; Art/LK bleibt als Filter. |
| C3 Hinweis „Eingaben gehen verloren“ schreckt ab | umsetzen: Text entschärfen und nur bei ungespeicherten Änderungen vor dem Verlassen fragen (Rückfrage im Browser). |
| C4 Zeile nach Filtern unter dem Falz | umsetzen: nach dem Filtern zur ersten Trefferzeile scrollen. |
| D1 Disqualifikation nur in der Tabelle | **B18 überholt:** Einzelseite bekommt Disqualifiziert-Haken und Abbruch-Auswahl mit Grund, mit derselben Konfliktprüfung wie die Tabelle (C7/B19-Verhalten unverändert). `entscheidungen/B18-…` als überholt kennzeichnen, OFFEN.md nachziehen. |
| D2 Hinweistext spricht von „Grund“ bei Disqualifikation | Text so umformulieren, dass „Grund“ eindeutig zum Abbruch gehört. |
| D3 Abbruch-Auswahl am Tablet | nachstellen; nachstellbar → beheben (z. B. Auswahlknöpfe statt Liste), sonst vermerken und schließen. „Verletzung HF“ ausschreiben bzw. erklären (Hundeführer); Erklärtext lesbarer. |
| D4 „Zu suchender Gegenstand: nicht hinterlegt“ | umsetzen: verständlicher Text (z. B. „Gegenstand: im Termin nicht eingetragen“) oder Zeile weglassen, wenn leer. |
| E1 Notizen im Desktop unsichtbar | **Nur der Rückhol-Bericht nennt sie** („3 Notizen übernommen, sichtbar im PDF-Bogen“). Keine Anzeige im Desktop; B20 bleibt sonst (Dokument ergänzen). |
| E2 „12 Teilnehmer“ vs. „9 aktualisiert“; „0 Disziplin(en) im Web leer“ | umsetzen: Bericht erklärt, dass nur geänderte zählen („9 geändert, 3 unverändert“); die Zeile zu leeren Disziplinen so fassen, dass sie nicht leeren Dreikampf-Disziplinen widerspricht (prüfen, was `im_web_leer` zählt, `db_sync.py`). |
| E3 Desktop-Texte | „gemerkter Termin [termin_1]“ → Name und Datum des Termins (`desktop_web.py`); Satz zur Status-Rücknahme kürzer und ruhiger; „teilnehmende Teilnehmer“ korrigieren. |
| E4 Passwort wird erneut abgefragt | **[S] umsetzen:** Ohne „Passwort merken“ hält das Programm das Passwort nur im Arbeitsspeicher bis Programmende; verworfen bei Terminwechsel, Änderung der Verbindungsdaten (Adresse, Benutzer, Fingerabdruck) und bei Ablehnung durch den Server (401). Nie auf Platte, nie im Log, nicht in Fehlermeldungen. Prüfung mit `qs-sicherheit`. |
| E5 Dialog nahm nach Fehlgriff keine Eingaben an | nachstellen (GUI-Test bzw. offscreen); nachstellbar → beheben, sonst vermerken und schließen. |
| E6 (Julia F5) „Passwort merken“ ausgegraut ohne Erklärung | umsetzen: Tooltip/Hinweis, warum der Haken nicht verfügbar ist (Tresor nicht vorhanden). |
| Heinz F5 OK mit leerem Passwort | umsetzen: Hinweis beim Speichern der Verbindung, wenn das Passwort leer ist (kein Blocker; Speichern ohne Passwort bleibt erlaubt, weil es sonst bei der Aktion abgefragt wird). |
| F1 README Port/Python | umsetzen: README_CONTAINER nennt, wie man einen anderen Port wählt und was dann gleich bleibt; `python -c …` durch einen Weg ersetzen, der ohne Python im PATH klappt (oder beide Wege nennen). |
| F2 Zertifikatswarnung | umsetzen: README beschreibt, wie die Warnung in Edge/Chrome/Firefox aussieht und wie man sie bestätigt. |
| F3 Anzeigen-Schalter | umsetzen: Schalter „anzeigen“ an Passwort- und Einrichtungscode-Feldern im Web. |
| F4 Container-Kleinigkeiten | umsetzen: Skriptmeldungen mit echten Umlauten; README-Hinweis, dass der Proxy ca. 30 s bis „gesund“ braucht und dass `podman-compose` unter PowerShell 5.1 harmlose Ausgaben rot zeigt; Fingerabdruck-Ausgabe auch bei Umleitung (Details in `C:\Users\mbruv\Documents\Claude\UX-Test-Web\stack-notizen.md`). |
| G1 leere Seiten im Sammel-PDF | Leere Bögen weglassen: nur Bögen mit Punkten, Notiz, Abbruch oder Disqualifikation. |

## Aufgaben im Einzelnen

### U1 Einzelseite: Weg zum Bogen und Bestätigung (A1, B2-Teil) – M
- `templates/` Einzelseite (`/teilnehmer/<id>`) und Teilnehmerliste (`templates/teilnehmerliste.html`): Knopf
  „Bewertungsbogen öffnen“ je Disziplin (nur Disziplinen, die einen Online-Bogen haben), Link je Disziplin in der Liste.
- Nach dem Speichern auf der Einzelseite eine sichtbare Meldung „Gespeichert“ (statt nur zurück zur Liste).
- Tests in `test_app_web.py`; Handbuch-Abschnitt Web anpassen.

### U2 Einzelseite: Disqualifikation und Abbruch (D1) – M
- Felder wie in der Ergebnistabelle (Disqualifiziert, Abbruch mit Grund), gleiche Speicherlogik und Konfliktprüfung
  (gemeinsame Hilfsfunktion statt Kopie). Rechte wie bisher (Rolle „eintragen“ darf).
- Tests: Speichern, Konflikt, Teilbewertung bei Abbruch mit Grund, Zurückholen übernimmt es (Ende-zu-Ende-Test).
- `entscheidungen/B18-…` als überholt kennzeichnen (Datum, Marco), OFFEN.md B18 durchstreichen; in OFFEN.md den
  Text zu C5 („Rest siehe B17 und B18“) auf B17 kürzen.

### U3 Teilnehmerliste: vier Stufen (B2) – M
- Status je Teilnehmer: offen / teilweise (n von m) / bewertet / disqualifiziert bzw. Abbruch; eigene Farben, gut
  lesbar und barrierefrei (Text, nicht nur Farbe). Bestehende Prüfung „bewertet“ in Tests anpassen.

### U4 Startseite, Navigation, Meldungen, Anzeigen-Schalter (A2, A3, B1, F3) – M
- `login`-Route: Angemeldete wie nach dem Login weiterleiten (Test: angemeldet → `/` → Redirect; abgelaufene Sitzung
  → Formular).
- Navigation in `templates/base.html` eindeutig; Weg zur Ergebnistabelle sichtbar.
- Meldung nach „Benutzer anlegen“.
- Anzeigen-Schalter an Passwort-/Code-Feldern (ohne externes Skript; CSP beachten, falls gesetzt).

### U5 Ergebnistabelle mobil (C1, C2, C4) – M
- Sticky erste Spalten und Kopfzeile, größerer Bogen-Knopf, Handy-Hinweis auf die Einzelseite.
- Sortierung Start-Nr. aufsteigend (numerisch, nicht als Text).
- Nach dem Filtern zur ersten Trefferzeile scrollen.
- Im eingebauten Browser bei 375 px und 768 px ansehen (Flask-Testserver oder `shsux` nach Neubau).

### U6 Ergebnistabelle: Texte (B3, C3, D2) – S
- Meldung „Gespeichert: n Teilnehmer.“ sichtbar; Tests anpassen.
- Bogen-Hinweis entschärfen, Rückfrage nur bei ungespeicherten Änderungen (`beforeunload` bzw. Klick-Abfrage).
- Hinweistext (`templates/ergebnis_tabelle.html`, Zeile mit „Bei „Disqualifiziert“ oder „Abbruch“ ohne Grund …“)
  so fassen, dass „Grund“ nur beim Abbruch steht.

### U7 Bogen: nachstellen und Texte (B4, D3, D4, A4) – M
- B4: Punkte über Höchstwert im Bogen eingeben (Tablet-Breite) und prüfen, ob die Meldung lesbar ist.
- D3: Abbruch-Auswahl per Klick/Touch im eingebauten Browser (Tablet-Größe) prüfen.
- Nach Entscheidung: beheben oder als Werkzeug-Eigenheit vermerken (Ergebnis in die Bemerkung).
- D4 Bogenkopf-Text, „Verletzung HF“ ausschreiben, Erklärtext lesbarer; A4 Kopfleiste sticky.

### U8 [S] Desktop Web-Verbindung (E4, E5, E6, Heinz F5) – L
- `desktop_web.py`, `web_sync.py`, `web_tresor.py`: Passwort-Zwischenspeicher nur im Speicher (siehe Entscheidung
  E4), verworfen bei Terminwechsel, geänderten Verbindungsdaten, 401 und Programmende.
- E6 Tooltip, Heinz F5 Hinweis bei leerem Passwort, E5 nachstellen (Passwort ins Feld Benutzername, dann
  korrigieren; Dialog muss Eingaben annehmen).
- GUI-Tests (`test_gui_web.py`), Verifikation **und** `qs-sicherheit`. Fortschritt.md darf den Zwischenspeicher
  beschreiben (Funktion, kein offener Fund).

### U9 Desktop-Texte (E1, E2, E3, A5) – S
- Rückhol-Bericht: Anzahl übernommener Notizen mit Hinweis „sichtbar im PDF-Bogen“; „n geändert, m unverändert“;
  Zeile zu leeren Disziplinen klären (`db_sync.py` `im_web_leer`, `desktop_web.py` Bericht).
- Termin-Bezeichnung statt `[termin_1]`, kürzerer Satz zur Status-Rücknahme, „teilnehmende Teilnehmer“.
- Hinweis auf „Web“ in der Ergebniserfassung (A5).
- `entscheidungen/B20-…` um „Bericht nennt Notizen (19.11.2026)“ ergänzen, OFFEN.md B20 anpassen.

### U10 Sammel-PDF (G1, B5) – S
- Nur Bögen mit Eintragung ins PDF (`app_web.py`, `pdf_export.py`); Test mit Dreikampf ohne Eintragung.
- Hinweis nach dem Klick „PDF wird erstellt …“.

### U11 README_CONTAINER und Skripte (F1, F2, F4) – S
- Nur Doku und Container-Skripte (`tools/zertifikat_erzeugen.ps1` u. a.). README.md/Handbuch abgleichen.

### U12 Wer hat wann eingetragen (B6) – L
- Datenbereich: je Teilnehmer und Disziplin Konto und Zeitpunkt der letzten Änderung, nur dort, wo die Web-Version
  speichert (PostgreSQL-Schema des Termins); Migration für bestehende Web-Datenbanken, Altdaten leer. Die
  Termin-Datei (SQLite) bekommt nichts; wird das Schema gemeinsam erzeugt, die Spalten so anlegen, dass Export,
  `kopiere_termin_daten` und Zurückholen sie nicht übertragen.
- Web: beim Speichern (Tabelle, Einzelseite, Bogen) setzen; nur Admins sehen es in der Ergebnistabelle (Tooltip
  oder kleine Zeile).
- Prüfen, dass Zurückholen und Altversionen unberührt bleiben (`test_altversionen`, Ende-zu-Ende-Test).
- Tests PostgreSQL-tauglich; `test_altversionen` beachten.

### U13 Abschluss – L
- QS nacheinander mit `qs-sicherheit`, `qs-korrektheit`, `qs-wartbarkeit` über `git diff cfe6a8a..HEAD`; Funde
  innerhalb des Rahmens beheben, sonst in „Rückfragen an Marco“.
- Gesamtlauf SHS Test Suite (`run_tests.py --kompakt`).
- Doku-Abgleich: `docs/HANDBUCH.md`, `README*.md`, `Architektur.md`, `UML.md` (Mermaid prüfen mit mmdc), `Modulreferenz.md`,
  `OFFEN.md` (B18 überholt, B20 ergänzt, C5 nachgezogen; **B16** „Web-Komponenten zurückgestellt“ als für den
  Web-Ausbau vom 18./19.11.2026 überholt vermerken), Entscheidungsdokumente.
- Abschlussbericht unten ergänzen (Commits, Ergebnisse der Nachstellungen, Rückfragen, Screenshot-Liste).
- Test-Stack `shsux` mit den Befehlen aus `stack-notizen.md` abbauen; Marcos Stack unverändert prüfen.
- Loop mit `ScheduleWakeup(stop: true)` beenden, PushNotification an Marco.

## Screenshots vor dem Build

(Jede Aufgabe trägt hier ein, welche Bilder in `docs/bilder/` neu aufgenommen werden müssen.)

## Rückfragen an Marco

(leer)

## Fortsetzungsnotiz

- 19.11.2026: Liste angelegt, Entscheidungen abgestimmt, Basis-Commit `cfe6a8a`. SHS Test Suite auf der Basis
  grün (1555 bestanden, 0 fehlgeschlagen, 211 übersprungen, 251 s). Noch keine Aufgabe begonnen.

## Abschlussbericht

(folgt mit U13)
