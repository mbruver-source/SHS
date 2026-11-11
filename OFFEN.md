# Offene, zurückgestellte und akzeptierte Punkte

Stand: 11.11.2026 (Dokumentation umgestellt), davor 05.11.2026 (UX-Test 2026-11 eingearbeitet). Die Datei fasst zusammen, was in
`Fortschritt.md` und `historie/` über viele Abschnitte verteilt steht. Bevor ein Punkt als neuer Befund
gemeldet oder neu geplant wird, hier nachsehen. Jede Entscheidung (B*, C*) hat ein eigenes
Dokument in `entscheidungen/` (Nummer in der ersten Spalte ist der Link); Schönheitsfehler und Randfälle
ohne Datenrisiko stehen gebündelt in `entscheidungen/K01-bekannte-kleinigkeiten.md`.

Die Fundstellen nennen Datei und Abschnittstitel (früher Zeilennummern der damals noch
einzigen `Fortschritt.md`; die Zuordnung der alten Zeilen zu Abschnitten ist nachträglich
gemacht, im Zweifel nach dem Titel suchen). Ältere Monate liegen in `historie/`.

**Pflege:** Wird ein Punkt erledigt, entschieden, zurückgestellt oder als Restrisiko
akzeptiert, hier eintragen bzw. streichen (mit Datum); bei B*/C* zusätzlich ein Dokument nach
`entscheidungen/VORLAGE.md` anlegen. Die Build-Checkliste (`shs-build`) und der Agent
`verifikation` prüfen das.

## A. Offen: wartet auf Prüfung am Gerät oder Rückmeldung

| Nr. | Punkt | Seit | Fundstelle |
|---|---|---|---|
| A1 | Rückmeldungen zur Mac-/Linux-Vorschau von echten Geräten, dazu die Lizenzabfrage beim Öffnen der .dmg ansehen (seit 01.11.2026) | 07.10.2026 | historie/2026-10.md „07.10.2026: 1.0.45 ausgeliefert“; historie/2026-10.md „19.10.2026: 1.0.51 ausgeliefert“; Fortschritt.md „01.11.2026: CI-Probelauf der …“ |
| A2 | Update-Prüfung am echten Mac: klappt HTTPS (CA-Zertifikate im Bundle)? Der Selbsttest zeigt die Anzahl | 15.10.2026 | historie/2026-10.md „Briefing (14.10.2026): Automatische …“ |
| A6 | PDF-Ausdrucke auf Papier ansehen, vor allem Etiketten auf Klebepapier (Bildschirmprüfung am 01.11.2026 erledigt) | 15.10.2026 | historie/2026-10.md „Briefing (14.10.2026): Automatische …“; Fortschritt.md „01.11.2026: Durchgang aller offenen …“ |
| A7 | Hinweisfenster „Termin liegt auf USB-Stick/Netzlaufwerk“ und automatische Kopie am echten Stick/Netzlaufwerk ansehen | 10.11.2026 | Fortschritt.md „10.11.2026: Automatische Kopie des Termins …“ |

## PO. Neue Prüfungsordnung ab 01.01.2027

Eigene ToDo-Liste: `PO_01012027.md` (seit 01.11.2026). Dort stehen die Punkte (PO1: Stechen
entfällt ab 01.01.2027, ausgeliefert mit 1.0.55) mit Status und offenen Fachfragen sowie der
Regelkatalog „aktuelle PO (01.07.2022) ↔ Programm“ (R1–R24; R7 Abbruchgründe ausgeliefert mit
1.0.55). Offen: Gleichstandsregel der neuen PO, sobald der Text vorliegt; ob einzelne „nicht
abgebildete“ Regeln (R10 Mindestalter, R14, R16, R18) einen Hinweis bekommen.

## B. Bewusst zurückgestellt (Marcos Entscheidung)

| Nr. | Punkt | Entscheidung | Fundstelle |
|---|---|---|---|
| [B3](entscheidungen/B03-excel-verdacht-kann-bei-nummern-wie-1e5-faelschl.md) | Excel-Verdacht kann bei Nummern wie „1E5“ fälschlich anschlagen (Altexporte und Telefon-Grenze erledigt 19.10.2026, V4) | 14.10., weiter 18.10.2026 | historie/2026-10.md „Briefing (14.10.2026): Automatische …“; historie/2026-10.md „18.10.2026: Offene Punkte gesichtet, …“; historie/2026-10.md „19.10.2026: V4 CSV-Altexporte und …“ |
| [B7](entscheidungen/B07-sicherheitspruefung-s-5.md) | Sicherheitsprüfung S-5 (gering): Web-App nutzt das DB-Eigentümerkonto; Nutzen gering bei hohem Umbau | 03.10.2026 | historie/2026-10.md „03.10.2026: Sicherheits-Codeprüfung …“ |
| [B8](entscheidungen/B08-signpath-foundation.md) | SignPath Foundation (Code-Signatur): erst wieder, wenn das Programm weiter verbreitet ist | 05.10.2026 | historie/2026-10.md „05.10.2026: Offene Altpunkte geklärt …“ |
| [B9](entscheidungen/B09-englische-sprachumschaltung.md) | Englische Sprachumschaltung: nur geschätzt (Desktop 5–6, alles 9–11 Fenster), Weg beschrieben | 15.10.2026 | historie/2026-10.md „Idee: Englische Sprachumschaltung …“ |
| [B10](entscheidungen/B10-weitere-testarten.md) | Weitere Testarten (erledigt: Windows in der CI 19.10.2026, V2; Abdeckung und bandit 01.11.2026); offen Desktop: Generalprobe, Barrierefreiheit mit echtem Bildschirmleser (Namen und Tab-Erreichbarkeit seit 11.11.2026 automatisch geprüft); offen Web (B16): gleichzeitige Eingaben, ZAP/XSS | 03.10.2026 | historie/2026-10.md „03.10.2026: Ergänzende Testarten T1–T3 …“; Fortschritt.md „01.11.2026: Durchgang aller offenen …“ |
| [B11](entscheidungen/B11-altdaten-tests-erweitern.md) | Altdaten-Tests erweitern (Web-Sync, CSV-Export, Anmeldeformular mit Altdaten) | 03.10.2026 | historie/2026-10.md „03.10.2026: Ergänzende Testarten T1–T3 …“ |
| [B12](entscheidungen/B12-app-py-nicht-weiter-aufteilen-ueberholt-am-11-11.md) | ~~`app.py` nicht weiter aufteilen~~ **Überholt am 11.11.2026 (Marco):** Teilnehmer-, Formular-Import- und Ergebnis-Reiter liegen jetzt in `desktop_teilnehmer.py`, `desktop_formular.py`, `desktop_ergebnis.py`; `app.py` hat nur noch Hauptfenster, StartDialog und `main`. Weitere Zerlegung der großen Klassen (`ErgebnisTab`, `TeilnehmerTab`, `DemoTour`) und von `db.py` ist der nächste Schritt (Entscheidung steht aus) | 18.10.2026 | Fortschritt.md (11.11.2026, Code-Struktur) |
| [B16](entscheidungen/B16-web-komponenten-insgesamt-zurueckgestellt.md) | Web-Komponenten insgesamt zurückgestellt (Web wird selten genutzt, Marco 11.11.2026), darunter die optimistische Sperre je Ergebniszeile gegen stilles Überschreiben bei gleichzeitigem Speichern (siehe C7). Vor dem nächsten Einsatz der Web-Version wieder aufnehmen | 11.11.2026 | Fortschritt.md (11.11.2026, Code-Struktur) |
| [B13](entscheidungen/B13-python-version-anheben.md) | Python-Version anheben (heute 3.11 in CI, Installer, Paketen, Container; Sicherheitsupdates bis Oktober 2027): Wiedervorlage Juni 2027, direkt auf 3.13/3.14, nicht über 3.12. Dabei sqlite3-Datumsumwandlungen prüfen (heute ungenutzt) | 19.10.2026 | historie/2026-10.md „19.10.2026: Python-Version bleibt …“ |
| [B14](entscheidungen/B14-marke-langsam-in-conftest-py-ist-an-keinem-test.md) | ~~Marke `langsam` in `conftest.py` ist an keinem Test angebracht~~ **Erledigt 11.11.2026:** an zwei Tests angebracht (nur diese brauchen über 10 s) | 10.11.2026 | Fortschritt.md „10.11.2026: Automatische Kopie des Termins …“ |
| [B15](entscheidungen/B15-auto-sicherung.md) | Auto-Sicherung: Das Dateimuster `{name}_JJJJ-MM-TT_HHMMSS.sqlite` kann bei einem Terminnamen, der selbst so endet, Kopien eines anderen Termins mitzählen und löschen (sehr unwahrscheinlich) | 10.11.2026 | Fortschritt.md „10.11.2026: Automatische Kopie des Termins …“ |

## C. Akzeptierte Restrisiken und abgelehnte Punkte: nicht erneut melden

**Web-Version**

| Nr. | Punkt | Seit | Fundstelle |
|---|---|---|---|
| [C1](entscheidungen/C01-kein-upload-groessenlimit-beim-web-login.md) | Kein Upload-Größenlimit beim Web-Login | 20.09.2026 | historie/2026-09.md „Erledigt“; CLAUDE.md |
| [C2](entscheidungen/C02-kein-brute-force-schutz-beim-web-login.md) | Kein Brute-Force-Schutz beim Web-Login | 20.09.2026 | historie/2026-09.md „Erledigt“; CLAUDE.md |
| [C3](entscheidungen/C03-keine-absolute-hoechstdauer-der-web-session.md) | Keine absolute Höchstdauer der Web-Session (gleitende 12 h reichen) | 22.09.2026 | historie/2026-09.md „Codeprüfung (22.09.), gesamter …“ |
| [C4](entscheidungen/C04-http-ohne-https-nur-im-lokalen-vereinsnetz.md) | HTTP ohne HTTPS, nur im lokalen Vereinsnetz | 03.10.2026 | historie/2026-10.md „03.10.2026: Sicherheits-Codeprüfung …“ |
| [C5](entscheidungen/C05-disqualifiziert-abbruch-nur-am-desktop-nicht-im.md) | Disqualifiziert/Abbruch nur am Desktop, nicht im Web und nicht beim Zurückholen | 21.09.2026 | historie/2026-09.md „Codeprüfung (21.09.), Fortsetzung: 10 …“ |
| [C6](entscheidungen/C06-keine-eigene-postgresql-sicherung.md) | Keine eigene PostgreSQL-Sicherung; maßgeblich sind Termin-Datei und ZIP-Sicherung | 05.10.2026 | historie/2026-10.md „05.10.2026: Offene Altpunkte geklärt …“ |
| [C7](entscheidungen/C07-gleichzeitiges-speichern.md) | Gleichzeitiges Speichern: zuletzt gespeichert gewinnt still, Konflikte je Disziplin statt je Feld | 18.10.2026 | historie/2026-10.md „18.10.2026: Offene Punkte gesichtet, …“ |
| [C36](entscheidungen/C36-lizenzen-prueft-die-sitzung-nicht-gegen-die-date.md) | `/lizenzen` prüft die Sitzung nicht gegen die Datenbank: bei veralteter Sitzung erscheint dort noch die Navigation (die Links dahinter prüfen wieder) | 01.11.2026 | Fortschritt.md „01.11.2026: Lizenzen im Versionsfenster …“; Fortschritt.md „01.11.2026: Durchgang aller offenen …“ |

**Bewertung, Stechen, PDFs**

| Nr. | Punkt | Seit | Fundstelle |
|---|---|---|---|
| [C8](entscheidungen/C08-noten-u-m-der-neuen-vorlagen-nicht-uebernommen.md) | Noten U/M der neuen Vorlagen nicht übernommen; Anzeige-Band V bleibt „40–39 / 38–36“ | 24.09.2026 | historie/2026-09.md „24.09.2026: Bewertungsbögen an neue …“ |
| [C9](entscheidungen/C09-anmeldeformular-p1p3.md) | Anmeldeformular P1–P3 (Laufzeit bei sehr langen Wörtern, `/AS` ohne Typprüfung, schwacher Test) | 28.09.2026 | historie/2026-09.md „28.09.2026: Ausfüllbares …“ |
| [C10](entscheidungen/C10-stechen-bei-nachtraeglich-gewachsener-gruppe.md) | Stechen bei nachträglich gewachsener Gruppe: fachlich ausgeschlossen | 14.10.2026 | historie/2026-10.md „Briefing (14.10.2026): Automatische …“ |
| [C11](entscheidungen/C11-nach-korrektur-wieder-derselbe-gleichstand.md) | Nach Korrektur wieder derselbe Gleichstand: der frühere Stechen-Sieger gilt | 03.10.2026 | historie/2026-10.md „03.10.2026: Ergänzende Testarten T1–T3 …“ |
| [C12](entscheidungen/K01-bekannte-kleinigkeiten.md) | Screenshots `handbuch_anmeldeformular`, `bewertungsbogen` mit alter PDF-Schrift | 15.10.2026 | historie/2026-10.md „Version 1.0.48 (15.10.2026, Build auf …“ |
| [C13](entscheidungen/K01-bekannte-kleinigkeiten.md) | Richter-Bedarf-PDF ragt ca. 2 mm in den Rand | 25.09.2026 | historie/2026-09.md „25.09.2026: Behältnis-Bedarf im Reiter …“ |

**Desktop-Bedienung**

| Nr. | Punkt | Seit | Fundstelle |
|---|---|---|---|
| [C14](entscheidungen/C14-grenzliste-der-desktop-pruefung.md) | Grenzliste der Desktop-Prüfung: Duplikatsperre im Fehlerfenster, „Nein/Verwerfen“ verwirft beim Terminwechsel, Demo umgeht modale Rückfragen, Hilfe-URLs nur als Text | 14.10.2026 | berichte/Desktop-Pruefung-2026-10/aufgaben.md:377 |
| [C15](entscheidungen/C15-schreibprobe-beim-oeffnen-aendert-den-zeitstempe.md) | Schreibprobe beim Öffnen ändert den Zeitstempel der Datei | 14.10.2026 | historie/2026-10.md „Briefing (14.10.2026): Automatische …“ |
| [C16](entscheidungen/K01-bekannte-kleinigkeiten.md) | Demo-Countdown „(3)“ steht nach einer Meldung kurz weiter | 05.10.2026 | historie/2026-10.md „Version 1.0.43 (05.10.2026, Build auf …“ |
| [C17](entscheidungen/K01-bekannte-kleinigkeiten.md) | Zeitplan lädt beim Designwechsel neu (nicht übernommene Startzeit, Scrollposition gehen verloren) | 23.09.2026 | historie/2026-09.md „23.09.2026: Hintergrund-Designs für die …“ |
| [C18](entscheidungen/K01-bekannte-kleinigkeiten.md) | Ordner `Ausdrucke\<Termin>` bleibt beim Löschen eines Termins | 03.10.2026 | historie/2026-10.md „Rubrik ux_test_2026_10 – Aufgabenliste …“ |
| [C19](entscheidungen/K01-bekannte-kleinigkeiten.md) | Startnummern-Kleinpunkte V4, V5, B, Anzeige der Standardgröße | 09.10.2026 | historie/2026-10.md „09.10.2026: Startnummern zurücksetzen …“; historie/2026-10.md „Version 1.0.46 (09.10.2026, Build auf …“ |
| [C20](entscheidungen/K01-bekannte-kleinigkeiten.md) | Dialoggrößen als feste Zahlen | 21.09.2026 | historie/2026-09.md „Codeprüfung (21.09.): 3 …“ |
| [C21](entscheidungen/C21-qt-sprachdatei.md) | Qt-Sprachdatei: eingebauter Ersatz übersetzt die Standardknöpfe | 03.10.2026 | historie/2026-10.md „Version 1.0.40 (03.10.2026, Build auf …“ |
| [C22](entscheidungen/K01-bekannte-kleinigkeiten.md) | Handbuch Kap. 13 nennt den Abmelden-Knopf „Link oben rechts“ | 03.10.2026 | historie/2026-10.md „Version 1.0.41 (03.10.2026, Build auf …“ |
| [C23](entscheidungen/K01-bekannte-kleinigkeiten.md) | „Alle speichern“ ab 201 Teilnehmern ganz oder gar nicht, ohne eigenen Handbuchsatz | 16.10.2026 | historie/2026-10.md „Lasttest mit 200 / 500 / 1000 …“ |
| [C24](entscheidungen/K01-bekannte-kleinigkeiten.md) | Ergebniserfassung: Gelb erst nach dem Übernehmen (der rote Rahmen kommt seit UX-Test 2026-11 T4, 04.11.2026, schon beim Tippen); Demo markiert das Zellenrechteck | 18.10.2026 | historie/2026-10.md „19.10.2026: O8 Ergebniserfassung, …“ |
| [C25](entscheidungen/K01-bekannte-kleinigkeiten.md) | Ansichtswechsel bei 1000 Teilnehmern 0,42 s (Ziel war < 0,3 s) | 19.10.2026 | historie/2026-10.md „19.10.2026: Rückfragen 3–8 der offenen …“ |
| [C35](entscheidungen/C35-closeevent-nach-abgebrochenem-abmelden-ohne-inte.md) | `closeEvent` nach abgebrochenem Abmelden ohne Interaktion (X11) speichert neue Eingaben weiter mit Meldungen | 19.10.2026 | historie/2026-10.md „19.10.2026: V8 Abschluss der …“; (V8), berichte/Verbesserungen-2026-10/aufgaben.md |

**Datensicherung**

| Nr. | Punkt | Seit | Fundstelle |
|---|---|---|---|
| [C27](entscheidungen/C27-wiederherstellen-mit-journal-in-zwei-schritten.md) | Wiederherstellen mit Journal in zwei Schritten: Absturz genau dazwischen lässt den alten Stand als versteckte `.alt`-Datei liegen | 19.10.2026 | historie/2026-10.md „19.10.2026: Rückfragen 3–8 der offenen …“ |
| [C28](entscheidungen/C28-grenzfall-bei-praeparierten-sicherungen.md) | Grenzfall bei präparierten Sicherungen (allgemein); Strg+C während des Ersetzens ohne Teil-Meldung | 07.10.2026 | historie/2026-10.md „07.10.2026: QS-Prüfung …“ |
| [C29](entscheidungen/C29-import-dialog-spielt-kein-journal-zurueck.md) | Import-Dialog spielt kein Journal zurück | 15.10.2026 | historie/2026-10.md „Restpunkte der Desktop-Prüfung: H1–H3 …“ |
| [C30](entscheidungen/C30-drei-daten-kleinfunde-vom-21-09.md) | Drei Daten-Kleinfunde vom 21.09. (ZIP-Eintragsname, `_LASTROWID_TABELLEN`, Commit-Muster) | 21.09.2026 | historie/2026-09.md „Codeprüfung (21.09.), Fortsetzung: 10 …“ |
| [C34](entscheidungen/C34-fremde-wal-datei-ohne-wal-wird-mit-immutable-1-o.md) | Fremde WAL-Datei ohne `-wal` wird mit `immutable=1` ohne Sperre gelesen: Checkpoint eines fremden Werkzeugs genau währenddessen kann Mischstand/„beschädigt“ ergeben | 19.10.2026 | historie/2026-10.md „19.10.2026: V7 `-wal`/`-shm` beim …“; (V7) |

**Sonstiges**

| Nr. | Punkt | Seit | Fundstelle |
|---|---|---|---|
| [C31](entscheidungen/C31-kontaktadresse-im-klartext-in-security-md-code-o.md) | Kontaktadresse im Klartext in SECURITY.md, CODE_OF_CONDUCT.md, CODE_SIGNING_POLICY.md | 23.09.2026 | historie/2026-09.md „23.09.2026: GitHub Page …“ |
| [C32](entscheidungen/K01-bekannte-kleinigkeiten.md) | Website- und Projekt-Kleinigkeiten (Website F2/F4, Review-Historie im Docstring, Chrome-Tipp, Maintainer-Adresse im .deb, Selbsttest legt evtl. leeren Termine-Ordner an) | 30.09.–08.10.2026 | historie/2026-09.md „30.09.2026: 3D-Behältnisse auf der …“; historie/2026-10.md „07.10.2026: QS-Prüfung …“; historie/2026-10.md „Version 1.0.45 (07.10.2026, Build auf …“; historie/2026-10.md „08.10.2026: Hinweis „Browser blockiert …“; historie/2026-10.md „03.10.2026: Ergänzende Testarten T1–T3 …“ |
| [C33](entscheidungen/K01-bekannte-kleinigkeiten.md) | Alte `haken.png` im TEMP-Ordner wird nicht aufgeräumt | 14.10.2026 | berichte/Desktop-Pruefung-2026-10/aufgaben.md:7 |
| [C37](entscheidungen/C37-dmgbuild-nutzt-intern-das-von-apple-als-veraltet.md) | dmgbuild nutzt intern das von Apple als veraltet geführte `hdiutil udifrez`; fällt es weg, schlägt der dmg-Schritt fehl und wird dann ersetzt | 01.11.2026 | Fortschritt.md „01.11.2026: Lizenzen im Versionsfenster …“; Fortschritt.md „01.11.2026: Durchgang aller offenen …“ |
| [C38](entscheidungen/C38-ux-test-2026-11-r-b15.md) | UX-Test 2026-11, R-B15: Startnummern-Zurücksetzen nennt das Web nur „falls veröffentlicht“ (die Termin-Datei kennt den Veröffentlicht-Status nicht); Entf löscht am Mac nicht (dort ist „delete“ die Rücktaste) | 05.11.2026 | berichte/UX-Test-2026-11/aufgaben-note1.md (R-B15) |
| [C39](entscheidungen/K01-bekannte-kleinigkeiten.md) | UX-Test 2026-11, R-B26 (feste Pause): Pläne über Mitternacht, Mindestabstands-Wartezeit bleibt vor einer festen Pause stehen, feste Uhrzeit beim Bearbeiten nicht änderbar (entfernen und neu anlegen) | 05.11.2026 | berichte/UX-Test-2026-11/aufgaben-note1.md (R-B26) |
| [C40](entscheidungen/K01-bekannte-kleinigkeiten.md) | UX-Test 2026-11: Demo-Erklärfenster verdeckt auf 1366 px unten rechts einen Teil des breiteren Termin-Dialogs (auf 1920 px nicht); Termin-Dialog bei Schrift „Groß“ ohne angehakte Prüfungen 10 px Bildlauf | 05.11.2026 | Fortschritt.md (B19) |
