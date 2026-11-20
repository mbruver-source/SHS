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
| U1 | Einzelseite: Bogen-Knopf je Disziplin, Bestätigung nach Speichern (A1, B2-Teil) | M | erledigt (19.11.) | siehe git log | unbekannt | Bogen-Links in der Liste, Knopf speichert vorher; Rückweg aus dem Bogen → U7 |
| U2 | Einzelseite: Disqualifikation und Abbruch mit Grund (D1, B18 überholt) | M | erledigt (19.11.) | siehe git log | unbekannt | gemeinsame Status-Hilfen für Tabelle, Bogen und Einzelseite |
| U3 | Teilnehmerliste: Status in vier Stufen (B2) | M | erledigt (19.11.) | siehe git log | unbekannt | Vollständigkeitsregel steht doppelt (`_listen_status` und `db_ergebnisse._wertnote`), Hinweis für U13 |
| U4 | Startseite, Navigation, Meldung „angelegt“, Anzeigen-Schalter (A2, A3, B1, F3) | M | erledigt (19.11.), F3 teilweise | siehe git log | unbekannt | Passwort-Schalter braucht JavaScript → Rückfrage an Marco |
| U5 | Ergebnistabelle mobil: feste Spalten, Sortierung, Bogen-Knopf, Scrollen (C1, C2, C4) | M | erledigt (19.11.) | siehe git log | unbekannt | C4 springt zur Tabelle statt zur ersten Trefferzeile (ohne Skript nicht anders); Safari/iOS ungeprüft |
| U6 | Ergebnistabelle: Texte und Meldungen (B3, C3, D2) | S | erledigt (19.11.), C3 anders | siehe git log | unbekannt | C3: statt Rückfrage (braucht JavaScript) speichert „Bogen“ vorher → Rückfrage an Marco |
| U7 | Bogen: nachstellen B4 und D3, Bogenkopf-Text, Kopfleiste (B4, D3, D4, A4) | M | erledigt (19.11.) | siehe git log | unbekannt | B4 nachgestellt und behoben (CSS-Hinweis am Feld); D3 nicht nachstellbar (Popup der Auswahlliste, Werkzeug) → geschlossen; Kopfleiste fest ab 701 × 560 px; Rückweg per ?von |
| U8 | [S] Desktop Web-Verbindung: Passwort bis Programmende im Speicher, Hinweise im Dialog, E5 nachstellen (E4, E5, E6, Heinz F5) | L | erledigt (20.11.) | siehe git log | unbekannt | `qs-sicherheit`: nichts hoch/mittel, Hinweise umgesetzt, ein älterer Punkt als Rückfrage; E5 nicht nachstellbar (Werkzeug) |
| U9 | Desktop-Texte: Rückhol-Bericht und Fragen (E1, E2, E3, A5) | S | erledigt (20.11.) | siehe git log | unbekannt | dabei Folgefehler der neuen Zählung beim zweiten Zurückholen behoben |
| U10 | Sammel-PDF: leere Bögen weglassen, Hinweis beim Klick (G1, B5) | S | erledigt (20.11.) | siehe git log | unbekannt | Einzelblätter nur für teilweise bewerteten DK ohne Status; Status/GESAMT bleiben |
| U11 | README_CONTAINER und Container-Skripte (F1, F2, F4) | S | erledigt (20.11.) | siehe git log | unbekannt | Skript jetzt UTF-8 mit BOM; Browser-Texte vor dem Build einmal live ansehen; Startfehlermeldungen nennen nur Python → U13 |
| U12 | Admin sieht je Ergebnis, wer wann eingetragen hat (B6) | L | erledigt (20.11.) | siehe git log | unbekannt | eigene Tabelle `web_aenderungen` nur im Web-Schema; PostgreSQL-Test nur in der CI |
| U13 | Abschluss: QS in drei Rollen, Doku-Abgleich, OFFEN.md/Entscheidungen, Abschlussbericht, Test-Stack aufräumen | L | erledigt (20.11.) | siehe git log | unbekannt | QS: K1–K3 behoben, Rückfragen ergänzt; `shsux` abgebaut |
| U14 | [S] Desktop: Sicherheitskorrektur Web-Verbindung (H-3, Details lokal) | S | erledigt (20.11.) | siehe git log | unbekannt | Verifikation + `qs-sicherheit`: Nachbesserungen umgesetzt |
| U15 | Web: angefangene Disziplin = „teilweise“, Bestätigung nach Rückweg Bogen → Einzelseite, Zeit in Europe/Berlin | M | erledigt (20.11.) | siehe git log | unbekannt | `?gespeichert=0\|1` (ID steht im Pfad); ohne Zonendaten EU-Regel statt UTC |
| U16 | Aufräumen Web-Logik: Vollständigkeitsregel einmal, Entscheidungs-/Status-Hilfen, `ergebnis_erfassen` teilen | M | erledigt (20.11.) | | unbekannt | |
| U17 | Aufräumen Templates/CSS und CSS-gekoppelte Tests | M | erledigt (20.11.) | | unbekannt | |
| U18 | Aufräumen Desktop: Passwortspeicher kapseln, Verbindungs-Hilfe | S | erledigt (20.11.) | | unbekannt | |
| U19 | Abschluss 2: OFFEN.md/Entscheidungen, QS über U14–U18, Gesamtlauf, Bericht | M | erledigt (20.11.) | | unbekannt | |

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
- Aus U1: Wird der Bogen aus der Teilnehmerliste oder von der Einzelseite geöffnet, führen „Speichern und zurück
  zur Tabelle“ und „Zurück“ in die Ergebnistabelle. Herkunft mitgeben (z. B. `?von=liste`) und dorthin
  zurückführen (Knopftext passend), Tabellen-Weg unverändert.

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

### Rückfragen geklärt (Marco, 20.11.2026) – Grundlage für U14–U19

| Rückfrage | Entscheidung |
|---|---|
| F3 Passwort anzeigen | So lassen (kein Skript, CSP bleibt `script-src 'none'`) → in U19 als akzeptiert in `OFFEN.md` |
| C3 Nachfrage vor dem Verlassen | Reicht so (Bogen speichert vorher, Hinweistext) → in U19 als akzeptiert in `OFFEN.md` |
| H-3 Sicherheitshinweis Web-Verbindung (Details lokal) | Umsetzen → U14 |
| Kontoname nach Kontolöschung | So lassen → in U19 als akzeptiert in `OFFEN.md` |
| Halb gefüllte Disziplin | „teilweise“ anzeigen → U15 |
| UTC-Datum in „zuletzt …“ | Europe/Berlin → U15 |
| Rückweg Bogen → Einzelseite | Bestätigung nachrüsten → U15 |
| Aufräumpaket | jetzt, ohne `web_regeln.py` → U16–U18; `web_regeln.py` in U19 als zurückgestellt in `OFFEN.md` |

### U14 [S] Desktop: Sicherheitskorrektur Web-Verbindung (H-3) – S
- Auftrag und Details nur lokal in `_unveroeffentlicht/Sicherheitspruefung-U8-2026-11-20.md` (H-3). Commit-Text,
  diese Liste und `Fortschritt.md` nur allgemein („Sicherheitskorrektur Web-Verbindung, Details folgen“).
- GUI-Tests in `test_gui_web.py`, danach `verifikation` und `qs-sicherheit`; Ergebnis im lokalen Bericht nachtragen.
- Handbuch Kap. Web-Verbindung: ein Satz zum geänderten Verhalten.

### U15 Web: drei Kleinigkeiten aus der QS – M
- **Teilnehmerliste „teilweise“:** `_listen_status` – steht in irgendeiner Disziplin ein Wert (Suche oder Anzeige),
  ist aber nicht alles vollständig: „teilweise“. Beim Dreikampf bleibt der Zähler „(n von 3)“ = vollständige
  Disziplinen; beim Einzelstart ohne Zähler. Auswertung (`_wertnote`) unverändert. Handbuch (Status-Stufen) und
  Tests anpassen.
- **Bestätigung auf der Einzelseite:** Rückweg aus dem Bogen mit `von=teilnehmer` leitet mit
  `?gespeichert=<id>&aenderung=0|1` (bzw. eigenem Parameter) auf `/teilnehmer/<id>`; die Einzelseite zeigt die
  gleiche Meldung wie Liste/Tabelle („Gespeichert …“ bzw. „Keine Änderung …“). Parameter streng prüfen wie bei
  `_meldung_nach_einzelseite` (nur Ziffern, nur eigener Teilnehmer).
- **Zeitzone:** `_vor_wann` rechnet das Datum („am TT.MM.“) und ggf. Uhrzeit in `Europe/Berlin` (`zoneinfo`).
  Prüfen, ob das Web-Image (`python:3.11-slim`) die Zonendaten hat; sonst `tzdata` in `requirements-web.txt`
  (Lizenz in `tools/drittlizenzen.py`/Drittlizenzen-Test beachten). Unter Windows lokal fehlt `tzdata` evtl.:
  Rückfall auf UTC mit Test für beide Fälle. Tests mit festem `jetzt` (23:30 UTC → nächster Tag in Berlin).
- Danach `verifikation`.

### U16 Aufräumen Web-Logik (ohne Verhaltensänderung) – M
- `db_ergebnisse._disziplin_punkte` → öffentliche `disziplin_punkte(ergebnis, disziplin)` mit `.get(...)`, Re-Export
  in `db.py` (`test_db_fassade` beachten); `_listen_status` und `_bogen_zusammenfassung` nutzen sie bzw. `_wertnote`
  statt eigener Kopien (U15 vorher erledigt: „teilweise“-Regel erhalten).
- `_einheit_entscheiden`: Rückgabewerte als Modulkonstanten; kurze Variante `_wert_entscheiden(neu, geladen,
  aktuell)` für Status und Notiz; in den Block „Gemeinsame Regeln“ verschieben. `_status_paar(ergebnis)` statt
  dreifacher Konstruktion.
- `ergebnis_erfassen` in View und `_einzelseite_speichern(...) -> (geschrieben, konflikt_texte)` teilen; Ergebniszeile
  nicht mehrfach lesen, wo nicht nötig (Lost-Update-Prüfung muss den aktuellen Stand behalten!).
- `db._BEREICH_STATUS` → `BEREICH_STATUS` (öffentlich, Tests anpassen); `sync_termin.py` gibt „unverändert“ mit aus;
  fehlende Docstrings (`_punkte_konflikt_text`, `_aenderung_merken`, `_einzelseite_status_*`), Abschnittskommentare
  nachziehen; `_bogen_ruecksprung` für den Rückweg-Code im Bogen; Zählwort-Hilfe `_anzahl(n, einzahl, mehrzahl)`.
- Volle Web-Tests vorher/nachher gleich grün; `verifikation` mit Schwerpunkt „Verhalten unverändert“.

### U17 Aufräumen Templates/CSS und Tests – M
- Jinja-Makros (eigene Datei, z. B. `templates/_bausteine.html`): Abbruch-Auswahl, Status-Erklärtext (ein
  Wortlaut), Zahlenfeld mit `.feld-hinweis` und `aria-describedby`. In Einzelseite, Tabelle und Bogen nutzen.
- Konfliktbox: CSS-Klasse statt Inline-Farben; weitere Inline-Styles der Einzelseite in Klassen; allgemeine
  `select`-Regel in `base.html`; CSS-Variable für die Kopfleistenhöhe (`--kopf-hoehe`, statt 4.5em/5.5em verstreut).
- Tests in `test_app_web.py` nicht mehr an exakte CSS-Zeichenketten koppeln (Leerraum normalisieren oder auf
  Klassen/IDs prüfen). Sichtprüfung mit `scratchpad\web_live.py` (Tabelle, Einzelseite, Bogen, 375/768/1280 px).
- `tools/web_screenshots.py` muss weiter laufen. Danach `verifikation`.

### U18 Aufräumen Desktop – S
- `desktop_web.py`: Passwortspeicher kapseln (`passwort_im_speicher() -> bool`; Dialog und Tests nutzen sie statt
  `_passwort_speicher`), `_eingegebene_verbindung()` im Dialog statt drei gleicher `WebEinstellungen(...)`,
  Quellen von `_passwort_fuer_test` als Konstanten. Nach U14, damit nichts doppelt angefasst wird.
- GUI-Tests grün; `verifikation`.

### U19 Abschluss 2 – M
- `OFFEN.md` + Entscheidungsdokumente (Vorlage `entscheidungen/VORLAGE.md`): F3 und C3 akzeptiert (keine Skripte),
  Kontoname nach Kontolöschung akzeptiert, `web_regeln.py` zurückgestellt.
- QS über `git diff f758046..HEAD` (drei Rollen nacheinander), Gesamtlauf SHS Test Suite, Doku-Abgleich (Handbuch,
  Architektur, UML mit mmdc, Modulreferenz), Abschlussbericht ergänzen, lokal committen, Loop beenden +
  PushNotification.

## Screenshots vor dem Build

(Jede Aufgabe trägt hier ein, welche Bilder in `docs/bilder/` neu aufgenommen werden müssen.)

- U1: `handbuch_web_teilnehmerliste.png` (Bogen-Links), `handbuch_web_ergebnis_dk.png` (Bogen-Knöpfe unter
  „Speichern“; Fensterhöhe in `tools/web_screenshots.py` prüfen), `handbuch_web_ergebnis_fehler.png`.
- U2: `handbuch_web_ergebnis_dk.png` und `handbuch_web_ergebnis_fehler.png` (neuer Abschnitt „Disqualifikation oder
  Abbruch“ auf der Einzelseite; Fensterhöhe prüfen).
- U3: `handbuch_web_teilnehmerliste.png` (neue Status-Pillen; die Demo-Daten in `tools/web_screenshots.py` sollten
  möglichst alle Stufen zeigen).
- U4: alle Web-Screenshots mit Kopfleiste als Admin (Navigation „Termine verwalten“), v. a.
  `handbuch_web_admin_termine.png`; Ersteinrichtung, falls es davon ein Bild gibt.
- U5: `handbuch_web_ergebnistabelle.png` (Rahmen mit 80vh-Höhe und neue Reihenfolge; bei 1980 x 1180 prüfen, ob
  der Ausschnitt noch passt).
- U6: `handbuch_web_ergebnistabelle.png` (neue Hinweistexte unter dem Filter und in der Speicherleiste, Knopf
  „Bogen“ als Absendeknopf).
- U12: `handbuch_web_ergebnistabelle.png` (Admin-Ansicht: „zuletzt …“ unter dem Status; die Demo-Daten in
  `tools/web_screenshots.py` sollten dafür eine Eintragung über das Web enthalten).
- U10: `handbuch_web_ergebnistabelle.png` (längerer Hinweistext am PDF-Knopf).
- U9: `handbuch_web_bericht.png` (neue Zusammenfassung), `handbuch_ergebniserfassung.png` (Hinweis über der
  Tabelle).
- U8: `handbuch_web_verbindung.png` (Hinweis bei leerem Passwort; ohne Tresor zusätzliche Erklärung unter dem
  Haken).
- U7: `handbuch_web_bewertungsbogen.png` (Erklärtext, Gegenstand-Zeile, Knopf „Speichern und zurück …“; der
  Screenshot-Bogen hat einen Gegenstand), alle Admin-Bilder ≥ 701 px Breite (feste Kopfleiste, optisch gleich).
- U15: keine (Demo-Daten tragen nur vollständige Paare ein, die Teilnehmerliste ändert sich nicht).
- U17: `handbuch_web_ergebnis_dk.png` (Erklärtext zu Disqualifiziert/Abbruch jetzt größer, neuer Wortlaut),
  `handbuch_web_bewertungsbogen.png` (Erklärtext ergänzt, Checkbox „Disqualifiziert“ bündig).

## Rückfragen an Marco

**Alle unten stehenden Rückfragen am 20.11.2026 mit Marco geklärt** – Entscheidungen in der Tabelle „Rückfragen
geklärt“ (vor U14), Umsetzung in U14–U19.

- **F3 Anzeigen-Schalter an Passwortfeldern (aus U4):** Ein Schalter „Passwort anzeigen“ braucht JavaScript; die
  Web-Version erlaubt per Sicherheitsrichtlinie gar keine Skripte (`script-src 'none'`). Umgesetzt ist nur der
  sichtbare Einrichtungs-Code (Textfeld statt Passwortfeld). Möglichkeiten für die Passwörter: (a) so lassen – beim
  Anlegen schützt „Passwort wiederholen“ vor Tippfehlern; (b) ein kleines eingebettetes Skript per Hash in der
  Sicherheitsrichtlinie freigeben (Sicherheitsänderung, eigene Prüfung). Der Loop hat nichts davon umgesetzt.
- **C3 Rückfrage vor dem Verlassen der Tabelle (aus U6):** Beschlossen war „nur bei ungespeicherten Änderungen
  vor dem Verlassen fragen“. Das braucht ebenfalls JavaScript. Umgesetzt ist stattdessen: „Bogen“ speichert zuerst
  alle Eingaben der Tabelle und öffnet dann den Bogen (keine Eingaben gehen mehr verloren). Ohne Nachfrage verwerfen
  ungespeicherte Eingaben weiterhin: „Filtern“, „Alle anzeigen“, „Zur Teilnehmerliste“ und die Navigation oben (der
  Hinweis unter dem Filter nennt das). Passt das so, oder soll die Rückfrage mit einem freigegebenen Skript kommen
  (siehe F3, gleiche Frage)?
- **Sicherheitshinweis aus der Prüfung von U8:** ein Punkt im älteren Code der Web-Verbindung (nicht durch U8
  entstanden), Details nur lokal in `_unveroeffentlicht/Sicherheitspruefung-U8-2026-11-20.md` (H-3). Bitte
  entscheiden: umsetzen oder zurückstellen.
- **Kontoname nach dem Löschen eines Web-Kontos (Hinweis aus der QS-Sicherheitsprüfung in U13, kein Fehler):** Die
  Zeile „zuletzt <Konto>, …“ (U12) bleibt in `web_aenderungen` stehen, wenn das Konto gelöscht wird; sie
  verschwindet erst mit dem Termin auf dem Server. Nur Admins sehen sie, sie geht nicht in die Termin-Datei.
  Möglichkeiten: (a) so lassen und in `OFFEN.md` als akzeptiert notieren; (b) beim Löschen des Kontos die Einträge
  aller Termine entfernen oder durch „gelöschtes Konto“ ersetzen.
- **Hinweise aus der QS-Korrektheitsprüfung in U13 (keine Fehler, nicht geändert):**
  - *Halb gefüllte Disziplin in der Teilnehmerliste:* Eine Disziplin zählt erst als bewertet, wenn Suche **und**
    Anzeige eingetragen sind (gleiche Regel wie die Auswertung). Ein Einzelstart mit „Suche 40, Anzeige leer“ zeigt
    deshalb „offen“, ein Dreikampf mit drei halb gefüllten Disziplinen ebenso. Soll so etwas als „teilweise“
    erscheinen?
  - *„zuletzt … am TT.MM.“ (U12):* Ab 24 Stunden steht das Datum ohne Jahr, gerechnet in UTC (der Container läuft in
    UTC). Zwischen 0 und 1 Uhr (Winterzeit) bzw. 0 und 2 Uhr (Sommerzeit) erscheint deshalb der Vortag. Für einen
    Prüfungstag unerheblich; mit Zeitzone Europe/Berlin wäre es genau.
  - *Rückweg aus dem Bogen zur Einzelseite:* „Speichern und zurück zur Seite des Teilnehmers“ zeigt dort keine
    Bestätigung „Gespeichert“ (der Rückweg zur Liste und zur Tabelle tut es). Nachrüsten?
- **Aufräumpaket aus der QS-Wartbarkeitsprüfung in U13 (kein Fehler, Umbau ohne Verhaltensänderung):** In U13 nur
  zwei Kleinigkeiten umgesetzt (Einzelseite: eine Prüfung statt zwei Kopien, `_tabellenzeile` nutzt
  `_punkte_gesperrt`). Vorgeschlagen, aber als eigener Umbau mit Marco abzustimmen:
  - Vollständigkeitsregel einmal in `db_ergebnisse` (öffentliche `disziplin_punkte`), genutzt von
    `_listen_status` und `_bogen_zusammenfassung` statt eigener Kopien (auch der vorgemerkte U3-Punkt).
  - `ergebnis_erfassen` (~125 Zeilen) in View und `_einzelseite_speichern` teilen; `_einheit_entscheiden` mit
    kurzer Variante für Status/Notiz, in den Block „Gemeinsame Regeln“, Rückgabe als Konstanten; `_status_paar`.
  - Passwortspeicher in `desktop_web.py` kapseln (`passwort_im_speicher()` statt direkter Zugriffe aus Dialog und
    Tests); `_eingegebene_verbindung()` statt drei gleicher Konstruktionen.
  - Templates: Jinja-Makros für Abbruch-Auswahl, Erklärtext und Zahlenfeld mit Hinweis (heute drei bzw. vier
    Kopien), Konfliktbox als CSS-Klasse statt Inline-Farben, eine allgemeine `select`-Regel, CSS-Variable für die
    Kopfleistenhöhe.
  - Tests weniger an CSS-Zeichenketten koppeln; `db._BEREICH_STATUS` öffentlich benennen; `sync_termin.py` gibt
    „unverändert“ mit aus.
  - Langfristig die reinen Regel-Funktionen aus `app_web.py` (2300 Zeilen) in ein Modul `web_regeln.py`.

## Fortsetzungsnotiz

- 19.11.2026: Liste angelegt, Entscheidungen abgestimmt, Basis-Commit `cfe6a8a`. SHS Test Suite auf der Basis
  grün (1555 bestanden, 0 fehlgeschlagen, 211 übersprungen, 251 s). Noch keine Aufgabe begonnen.
- 19.11.2026: U1 erledigt und committet. Hinweis: Bearbeitete Templates öffnen sich per Hook im Browser-Pane als
  neue Tabs; diese Tabs danach schließen, den Tab `seed` nie. Nächste: U2.
- 19.11.2026: U2 erledigt und committet. Nächste: U3 (Status in der Teilnehmerliste; „disqualifiziert“/„Abbruch“
  über `_tabellen_status_text` bzw. die Status-Hilfen in `app_web.py` ableiten).
- 19.11.2026: U3 erledigt und committet. Nächste: U4 (Startseite, Navigation, Meldung „angelegt“, Anzeigen-Schalter).
- 19.11.2026: U4 erledigt und committet (F3 teilweise, Rückfrage). Nächste: U5 (Ergebnistabelle mobil). Hinweis:
  Die Web-Seiten haben keine Skripte (CSP `script-src 'none'`) – Sticky-Spalten, Scrollen zur Trefferzeile (C4) usw.
  nur mit CSS bzw. Adress-Anker (`#zeile-<id>`) lösen.
- 19.11.2026: U5 erledigt und committet. Nächste: U6 (Texte der Ergebnistabelle). Sichtprüfung im Browser geht
  mit `scratchpad\web_live.py` (lokaler Demo-Server auf 127.0.0.1:5097, admin/demo-passwort-1 aus
  `tools/web_screenshots.py`), im neuen Tab, danach Tab schließen und Server mit TaskStop beenden.
- 19.11.2026: U6 erledigt und committet (C3 anders gelöst, Rückfrage). Nächste: U7 (Bogen: B4, D3 nachstellen –
  das alte Verhalten im Test-Stack `shsux` im Tab `seed`, das neue mit `web_live.py`; D4, A4, Rückweg aus dem Bogen).
- 19.11.2026: U7 erledigt und committet. Für U13 vormerken: im Browser bei 768 px als Admin prüfen, ob die
  Navigation umbricht (dann ist die feste Kopfleiste höher als `scroll-padding-top: 4.5em`), und ob nach
  „Speichern und zurück zur Tabelle“ die Tabellenkopfzeile sichtbar bleibt. Nächste: U8 [S] Desktop Web-Verbindung.
- 20.11.2026: U8 erledigt und committet (`ac2325c`), Sicherheitsbericht lokal. Nächste: U9 (Desktop-Texte: Rückhol-
  Bericht mit Notizen, Zählung, Termin-Name, A5-Hinweis; B20-Dokument ergänzen).
- 20.11.2026: U9 erledigt und committet. Nächste: U10 (Sammel-PDF: leere Bögen weglassen, Hinweis beim Klick –
  ohne Skript nur als Text am Knopf bzw. darunter).
- 20.11.2026: U10 erledigt und committet. Nächste: U11 (README_CONTAINER und Container-Skripte, F1, F2, F4; Details
  in `C:\Users\mbruv\Documents\Claude\UX-Test-Web\stack-notizen.md`).
- 20.11.2026: U11 erledigt und committet. Nächste: U12 (Admin sieht je Teilnehmer/Disziplin Konto und Zeitpunkt der
  letzten Änderung, nur Web-Datenbank; Daten + Web, PostgreSQL-tauglich, Altversionen beachten).
- 20.11.2026: U12 erledigt und committet. Nächste: U13 Abschluss (QS in drei Rollen über `git diff cfe6a8a..HEAD`,
  Gesamtlauf SHS Test Suite, Doku-Abgleich inkl. Mermaid-Prüfung, OFFEN.md/B16, Abschlussbericht, Test-Stack
  `shsux` abbauen). Vorgemerkte Punkte für U13: Startfehlermeldungen der Web-Version nennen nur Python (U11);
  Vollständigkeitsregel doppelt (U3); Kopfleiste bei 768 px als Admin ansehen (U7); Browser-Texte live (U11).
- 20.11.2026: U13 erledigt und committet. Loop beendet. Offen ist nur, was unter „Rückfragen an Marco“ und
  „Vor dem Build noch offen“ (Abschlussbericht) steht.
- 20.11.2026: Rückfragen mit Marco geklärt, Folgeaufgaben U14–U19 angelegt (gleicher Ablauf, gleicher Start-Befehl).
  Der Test-Stack `shsux` ist abgebaut; für Sichtprüfungen nur noch `scratchpad\web_live.py` (Aufruf
  `python web_live.py <repo>`, 127.0.0.1:5097, admin/demo-passwort-1). Nächste: U14 [S].
- 20.11.2026: U14 erledigt und committet (`0919a83`, zusammen mit der Klärung; der vorherige Klärungs-Commit enthielt
  Sicherheitsdetails und wurde vor jedem Push neu erstellt). Nächste: U15 (drei Web-Kleinigkeiten).
- 20.11.2026: U15 erledigt und committet. Nächste: U16 (Aufräumen Web-Logik, Verhalten unverändert; die neue
  „teilweise“-Regel in `_listen_status` – angefangen = irgendein Wert – beim Zusammenführen erhalten).
- 20.11.2026: **Gezielter Stopp (Marco, Nutzungslimit) mitten in U16.** Teil 1 lokal committet, Tests grün
  (test_app_web, test_ende_zu_ende_web, test_db, test_db_fassade): `db.disziplin_punkte` und
  `db.wertnote_aus_punkten` öffentlich und von `_listen_status`/`_bogen_zusammenfassung` genutzt;
  `db.BEREICH_STATUS` öffentlich; `_einheit_entscheiden` mit Konstanten im Block „Gemeinsame Regeln“, dazu
  `_wert_entscheiden` und `_status_paar`; `ergebnis_erfassen` in View und `_einzelseite_speichern` geteilt.
  **Offen in U16:** `sync_termin.py` gibt „unverändert“ mit aus; `_bogen_ruecksprung` für den Rückweg-Code im Bogen;
  Zählwort-Hilfe `_anzahl`; Docstrings `_einzelseite_status_*`, Abschnittskommentar des Bogens; danach
  `verifikation` (Schwerpunkt „Verhalten unverändert“, Diff ab dem Commit vor Teil 1), `Fortschritt.md`, Commit.
  U16 steht weiter auf „läuft“. Weiter mit demselben `/loop`-Befehl.
- 20.11.2026: U16 Teil 2 erledigt, verifiziert und committet. Nächste: U17 (Templates/CSS-Makros, CSS-gekoppelte
  Tests; Sichtprüfung mit `scratchpad\web_live.py <repo>`).
- 20.11.2026: U17 erledigt und committet (Hinweis: `web_live.py` cacht Templates – nach Template-Änderungen den
  Server neu starten). Nächste: U18 (Desktop: Passwortspeicher kapseln, Verbindungs-Hilfe).
- 20.11.2026: U18 erledigt und committet. Nächste: U19 Abschluss 2 (OFFEN.md/Entscheidungen für F3, C3, Kontoname,
  `web_regeln.py`; QS in drei Rollen über `git diff f758046..HEAD`; Gesamtlauf; Doku-Abgleich; Bericht; Loop beenden).
- 20.11.2026: U19 erledigt und committet, Loop beendet. Alle Aufgaben U1–U19 erledigt; offen nur „Vor dem Push /
  Build von Marco zu entscheiden“ im Abschlussbericht (Nachtrag Runde 2).

## Abschlussbericht

Stand 20.11.2026, nach U13. Alle 13 Aufgaben erledigt; alle Commits nur lokal auf `main` (Basis `cfe6a8a`, nicht
gepusht, kein Tag, kein Versionsbump, kein Build).

**Commits (ältester zuerst):**

| Aufgabe | Commit | Inhalt |
|---|---|---|
| Liste | `c2e90f7` | Funde besprochen, Aufgabenliste für den Loop |
| U1 | `6aee9a5` | Weg zum Bewertungsbogen aus Liste und Einzelseite, Bestätigung nach dem Speichern |
| U2 | `c4fb381` | Disqualifikation und Abbruch auf der Einzelseite (B18 überholt) |
| U3 | `448cdd9` | Teilnehmerliste: offen, teilweise, bewertet, disqualifiziert, Abbruch |
| U4 | `f5c0163` | Startseite leitet Angemeldete weiter, „Termine verwalten“, Meldung nach Benutzer anlegen |
| U5 | `e9fe823` | Ergebnistabelle am Handy mit fester Kopfzeile, Sortierung nach Start-Nr. |
| U6 | `029f915` | „Gespeichert: n Teilnehmer“, „Bogen“ speichert vorher |
| U7 | `72801f4` | Bogen: Hinweis bei zu hohen Punkten, feste Kopfleiste, Rückweg zur Herkunft |
| U8 | `3459c21` | Desktop: Web-Passwort ohne Tresor bis Programmende im Arbeitsspeicher, Hinweise im Dialog |
| U9 | `138a5f3` | Desktop: Rückhol-Bericht mit geändert/unverändert und Notizen, Termin mit Namen |
| U10 | `f93aa13` | Sammel-PDF ohne leere Dreikampf-Seiten, Hinweis zum Download |
| U11 | `8d97f2b` | Container-README: Geheimnisse ohne Python, Port, Zertifikatswarnung; Skript mit Umlauten |
| U12 | `431d022` | Admin sieht, wer wann eingetragen hat |
| U13 | (dieser Commit) | QS-Nachbesserungen K1–K3, Doku-Abgleich, Abschlussbericht |

**Nachstellungen:** B4 (zu hohe Punkte im Bogen ohne Hinweis) im alten Test-Stack nachgestellt und behoben
(Hinweis am Feld per CSS). D3 (Auswahlliste im Bogen) und E5 (Passwortfeld) nicht nachstellbar – Eigenheiten der
Testwerkzeuge, geschlossen.

**QS in drei Rollen (U13):** Sicherheit ohne Befund; Korrektheit drei Fehler (niedrig, alle im Loop-Code) behoben;
Wartbarkeit zwei Kleinigkeiten behoben, Aufräumpaket als Rückfrage. Alle Rückfragen stehen oben unter „Rückfragen an
Marco“: F3 (Passwort anzeigen), C3 (Rückfrage vor dem Verlassen), Sicherheitshinweis H-3 (lokal), Kontoname nach
Kontolöschung, drei Hinweise aus der Korrektheitsprüfung, Aufräumpaket.

**Tests:** SHS Test Suite gesamt grün (1633 bestanden, 0 fehlgeschlagen, 212 übersprungen; Basis vorher 1555);
nach den Nachbesserungen die betroffenen Testdateien erneut grün. PostgreSQL-Tests laufen nur in der CI.

**Doku:** `docs/HANDBUCH.md`, `README_CONTAINER.md`, `Architektur.md`, `UML.md` (mit mmdc geprüft),
`Modulreferenz.md`, `OFFEN.md` (B16, B18 überholt; B20, C5 ergänzt) und die Entscheidungsdokumente sind nachgezogen.

**Vor dem Build noch offen:** Screenshots laut Liste „Screenshots vor dem Build“ neu aufnehmen; die
Zertifikatswarnungs-Texte in `README_CONTAINER.md` einmal live im Browser ansehen; Safari/iOS für die feste
Tabellenkopfzeile ungeprüft; die Rückfragen klären.

**Aufgeräumt:** Test-Stack `shsux` samt Volume, Netz, Image `localhost/shsux-web:ux` und Ordner entfernt; Marcos
Stacks unverändert (gestoppt wie vorher, Volumes vorhanden).

### Nachtrag: Runde 2 (U14–U19, 20.11.2026)

Nach der Klärung aller Rückfragen mit Marco (Tabelle „Rückfragen geklärt“) sechs weitere Aufgaben, je lokal
committet, nicht gepusht:

| Aufgabe | Commit | Inhalt |
|---|---|---|
| Klärung + U14 | `0919a83` | Rückfragen geklärt; Sicherheitskorrektur Web-Verbindung (Details nur lokal) |
| – | `ddc4141` | Fortsetzungsnotiz |
| U15 | `bb07eb3` | „teilweise“ schon bei angefangener Disziplin, Bestätigung nach dem Bogen, deutsche Zeit |
| U16 | `751e1dd`, `7801b50` | Web-Logik aufgeräumt (zwei Teile wegen gezieltem Stopp vor dem Nutzungslimit) |
| U17 | `5ec3d18` | Templates/CSS aufgeräumt, gemeinsame Bausteine `templates/_bausteine.html` |
| U18 | `63dff2c` | Desktop: Passwortspeicher gekapselt |
| U19 | (dieser Commit) | OFFEN.md (C41, C42, B23), QS in drei Rollen, Nachbesserungen, Bericht |

**QS über `f758046..HEAD`:** Sicherheit ohne Befund im Code (Hinweis zur Offenlegung, siehe unten); Korrektheit
ein Fehler (niedrig: „Gespeichertes Passwort vergessen“ meldete bei gescheitertem Löschen aus dem Tresor trotzdem
„entfernt“) behoben, zwei Testlücken geschlossen; Wartbarkeit ohne mittleren Befund, Kleinigkeiten umgesetzt
(`--fehler-hg`, `_tresor_passwort_verwerfen`, Herkunftswerte des Bogens aus einer Quelle, Zeitzonen-Test ohne
stilles Auslassen und mit beiden Umstellungstagen).

**Tests:** SHS Test Suite gesamt grün (1648 bestanden, 0 fehlgeschlagen, 213 übersprungen); nach den
QS-Nachbesserungen die betroffenen Testdateien erneut grün. PostgreSQL-Tests nur in der CI.

**Vor dem Push / Build von Marco zu entscheiden:**
- Der Commit-Text von `0919a83` und der Handbuch-Satz in Kap. Web-Verbindung beschreiben das neue Verhalten der
  Sicherheitskorrektur U14 so, dass man die alte Lücke erschließen kann (`Fortschritt.md` ist schon allgemein
  gefasst). Die Desktop-Web-Verbindung war noch in keinem Release; Commit-Texte lassen sich nur vor dem Push ändern.
- Nicht umgesetzte Kleinigkeiten der Wartbarkeitsprüfung: `textarea`/`select` in die gemeinsame Eingabefeld-Regel
  aufnehmen; Inline-Styles in `admin_benutzer.html`/`admin_termine.html`; CSS-Tests teils nur über Teilzeichenketten.
- Screenshots laut Liste neu aufnehmen; Zertifikatswarnungs-Texte live ansehen; Safari/iOS ungeprüft.
