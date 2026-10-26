# Offene, zurückgestellte und akzeptierte Punkte

Stand: 19.10.2026, nach Release 1.0.51. Die Datei fasst zusammen, was in `Fortschritt.md` über
viele Abschnitte verteilt steht. Maßgeblich bleibt `Fortschritt.md`; die Fundstellen (F:Zeile)
zeigen auf den entscheidenden Absatz. Bevor ein Punkt als neuer Befund gemeldet oder neu
geplant wird, hier nachsehen.

**Pflege:** Wird ein Punkt erledigt, entschieden, zurückgestellt oder als Restrisiko
akzeptiert, hier eintragen bzw. streichen (mit Datum). Die Build-Checkliste (`shs-build`) und
der Agent `verifikation` prüfen das. Zeilenangaben sind ungefähr; im Zweifel nach dem Titel
suchen.

## A. Offen: wartet auf Prüfung am Gerät oder Rückmeldung

| Nr. | Punkt | Seit | Fundstelle |
|---|---|---|---|
| A1 | Rückmeldungen zur Mac-/Linux-Vorschau von echten Geräten | 07.10.2026 | F:5352, F:7617 |
| A2 | Update-Prüfung am echten Mac: klappt HTTPS (CA-Zertifikate im Bundle)? Der Selbsttest zeigt die Anzahl | 15.10.2026 | F:6380 |
| A3 | Design „Hell“ bei Windows-Einstellung „Apps: dunkel“ am echten Rechner ansehen | 14.10.2026 | F:5980 |
| A4 | Erklärfenster der Demo über der Taskleiste am echten Windows ansehen | 14.10.2026 | F:6159 |
| A5 | Löschen in den Papierkorb am echten Windows (lokal nur mit Attrappe getestet) | 15.10.2026 | F:6488 |
| A6 | PDF-Schrift DejaVu in den Ausdrucken am Gerät ansehen | 15.10.2026 | F:6403, F:6904 |
| A7 | Praxistests vom September: wohl überholt, bei Gelegenheit mit Marco streichen | 18.10.2026 | F:6904 |

## B. Bewusst zurückgestellt (Marcos Entscheidung)

| Nr. | Punkt | Entscheidung | Fundstelle |
|---|---|---|---|
| B3 | Excel-Verdacht kann bei Nummern wie „1E5“ fälschlich anschlagen (Altexporte und Telefon-Grenze erledigt 19.10.2026, V4) | 14.10., weiter 18.10.2026 | F:6146, F:6980, F:7729 |
| B7 | Sicherheitsprüfung S-5 (gering): Web-App nutzt das DB-Eigentümerkonto; Nutzen gering bei hohem Umbau | 03.10.2026 | F:4510 |
| B8 | SignPath Foundation (Code-Signatur): erst wieder, wenn das Programm weiter verbreitet ist | 05.10.2026 | F:4770 |
| B9 | Englische Sprachumschaltung: nur geschätzt (Desktop 5–6, alles 9–11 Fenster), Weg beschrieben | 15.10.2026 | F:6605 |
| B10 | Weitere Testarten (Windows in der CI erledigt 19.10.2026, V2): gleichzeitige Web-Eingaben, Abdeckung, bandit/ZAP/XSS, Generalprobe, Barrierefreiheit | 03.10.2026 | F:4198 |
| B11 | Altdaten-Tests erweitern (Web-Sync, CSV-Export, Anmeldeformular mit Altdaten) | 03.10.2026 | F:4383 |
| B12 | `app.py` nicht weiter aufteilen: Teilnehmer-, Formular-Import-, Ergebnis-Reiter, Hauptfenster, StartDialog und `main` bleiben dort | 18.10.2026 | F:6474 |
| B13 | Python-Version anheben (heute 3.11 in CI, Installer, Paketen, Container; Sicherheitsupdates bis Oktober 2027): etwa Mitte 2027 direkt auf 3.13/3.14, nicht über 3.12. Dabei sqlite3-Datumsumwandlungen prüfen (heute ungenutzt) | 19.10.2026 | F:7861 |
| B14 | Verweis auf `THIRD_PARTY_LICENSES.txt` im Versionsfenster der App | 26.10.2026 | F:7926 |

## C. Akzeptierte Restrisiken und abgelehnte Punkte: nicht erneut melden

**Web-Version**

| Nr. | Punkt | Seit | Fundstelle |
|---|---|---|---|
| C1 | Kein Upload-Größenlimit beim Web-Login | 20.09.2026 | F:248, CLAUDE.md |
| C2 | Kein Brute-Force-Schutz beim Web-Login | 20.09.2026 | F:248, CLAUDE.md |
| C3 | Keine absolute Höchstdauer der Web-Session (gleitende 12 h reichen) | 22.09.2026 | F:1482 |
| C4 | HTTP ohne HTTPS, nur im lokalen Vereinsnetz | 03.10.2026 | F:4524 |
| C5 | Disqualifiziert/Abbruch nur am Desktop, nicht im Web und nicht beim Zurückholen | 21.09.2026 | F:566 |
| C6 | Keine eigene PostgreSQL-Sicherung; maßgeblich sind Termin-Datei und ZIP-Sicherung | 05.10.2026 | F:4764 |
| C7 | Gleichzeitiges Speichern: zuletzt gespeichert gewinnt still, Konflikte je Disziplin statt je Feld | 18.10.2026 | F:6997 |

**Bewertung, Stechen, PDFs**

| Nr. | Punkt | Seit | Fundstelle |
|---|---|---|---|
| C8 | Noten U/M der neuen Vorlagen nicht übernommen; Anzeige-Band V bleibt „40–39 / 38–36“ | 24.09.2026 | F:2065 |
| C9 | Anmeldeformular P1–P3 (Laufzeit bei sehr langen Wörtern, `/AS` ohne Typprüfung, schwacher Test) | 28.09.2026 | F:2846 |
| C10 | Stechen bei nachträglich gewachsener Gruppe: fachlich ausgeschlossen | 14.10.2026 | F:6343 |
| C11 | Nach Korrektur wieder derselbe Gleichstand: der frühere Stechen-Sieger gilt | 03.10.2026 | F:4399 |
| C12 | Screenshots `handbuch_anmeldeformular`, `bewertungsbogen` mit alter PDF-Schrift | 15.10.2026 | F:6502 |
| C13 | Richter-Bedarf-PDF ragt ca. 2 mm in den Rand | 25.09.2026 | F:2323 |

**Desktop-Bedienung**

| Nr. | Punkt | Seit | Fundstelle |
|---|---|---|---|
| C14 | Grenzliste der Desktop-Prüfung: Duplikatsperre im Fehlerfenster, „Nein/Verwerfen“ verwirft beim Terminwechsel, Demo umgeht modale Rückfragen, Hilfe-URLs nur als Text | 14.10.2026 | Desktop-Pruefung-2026-10/aufgaben.md:377 |
| C15 | Schreibprobe beim Öffnen ändert den Zeitstempel der Datei | 14.10.2026 | F:5968 |
| C16 | Demo-Countdown „(3)“ steht nach einer Meldung kurz weiter | 05.10.2026 | F:4934 |
| C17 | Zeitplan lädt beim Designwechsel neu (nicht übernommene Startzeit, Scrollposition gehen verloren) | 23.09.2026 | F:1812 |
| C18 | Ordner `Ausdrucke\<Termin>` bleibt beim Löschen eines Termins | 03.10.2026 | F:4056 |
| C19 | Startnummern-Kleinpunkte V4, V5, B, Anzeige der Standardgröße | 09.10.2026 | F:5447, F:5493, F:5549 |
| C20 | Dialoggrößen als feste Zahlen | 21.09.2026 | F:524 |
| C21 | Qt-Sprachdatei: eingebauter Ersatz übersetzt die Standardknöpfe | 03.10.2026 | F:4163 |
| C22 | Handbuch Kap. 13 nennt den Abmelden-Knopf „Link oben rechts“ | 03.10.2026 | F:4561 |
| C23 | „Alle speichern“ ab 201 Teilnehmern ganz oder gar nicht, ohne eigenen Handbuchsatz | 16.10.2026 | F:6780 |
| C24 | Ergebniserfassung: Gelb/roter Rahmen erst nach dem Übernehmen; Demo markiert das Zellenrechteck | 18.10.2026 | F:7347 |
| C25 | Ansichtswechsel bei 1000 Teilnehmern 0,42 s (Ziel war < 0,3 s) | 19.10.2026 | F:7517 |
| C35 | `closeEvent` nach abgebrochenem Abmelden ohne Interaktion (X11) speichert neue Eingaben weiter mit Meldungen | 19.10.2026 | F:7834 (V8), Verbesserungen-2026-10/aufgaben.md |

**Datensicherung**

| Nr. | Punkt | Seit | Fundstelle |
|---|---|---|---|
| C27 | Wiederherstellen mit Journal in zwei Schritten: Absturz genau dazwischen lässt den alten Stand als versteckte `.alt`-Datei liegen | 19.10.2026 | F:7540 |
| C28 | Grenzfall bei präparierten Sicherungen (allgemein); Strg+C während des Ersetzens ohne Teil-Meldung | 07.10.2026 | F:5192 |
| C29 | Import-Dialog spielt kein Journal zurück | 15.10.2026 | F:6564 |
| C30 | Drei Daten-Kleinfunde vom 21.09. (ZIP-Eintragsname, `_LASTROWID_TABELLEN`, Commit-Muster) | 21.09.2026 | F:638 |
| C34 | Fremde WAL-Datei ohne `-wal` wird mit `immutable=1` ohne Sperre gelesen: Checkpoint eines fremden Werkzeugs genau währenddessen kann Mischstand/„beschädigt“ ergeben | 19.10.2026 | F:7809 (V7) |

**Sonstiges**

| Nr. | Punkt | Seit | Fundstelle |
|---|---|---|---|
| C31 | Kontaktadresse im Klartext in SECURITY.md, CODE_OF_CONDUCT.md, CODE_SIGNING_POLICY.md | 23.09.2026 | F:1948 |
| C32 | Website- und Projekt-Kleinigkeiten (Website F2/F4, Review-Historie im Docstring, Chrome-Tipp, Maintainer-Adresse im .deb, Selbsttest legt evtl. leeren Termine-Ordner an) | 30.09.–08.10.2026 | F:2949, F:5172, F:5311, F:5367, F:4457 |
| C33 | Alte `haken.png` im TEMP-Ordner wird nicht aufgeräumt | 14.10.2026 | Desktop-Pruefung-2026-10/aufgaben.md:7 |
