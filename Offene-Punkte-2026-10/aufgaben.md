# Offene Punkte Oktober 2026: automatische Abarbeitung (O1–O11)

Angelegt am 18.10.2026 nach Marcos Freigabe. Grundlage sind die zurückgestellten Punkte aus
Gruppe 3, siehe `Fortschritt.md`, Abschnitte vom 18.10.2026. Ablauf nach dem Skill
`aufgaben-abarbeitung` (`.claude/skills/aufgaben-abarbeitung/SKILL.md`). Die Regeln aus
`CLAUDE.md` gehen vor: kein Push, Tag, Versionsbump oder Build, Sicherheitsfunde nur allgemein.

Start durch Marco:
`/loop Arbeite die nächste offene Aufgabe aus Offene-Punkte-2026-10/aufgaben.md nach dem dort beschriebenen Ablauf ab.`

## Statustabelle

| Aufgabe | Größe | Status | Commit | Limit vorher → nachher (5 h / 7 T) | Bemerkung |
|---|---|---|---|---|---|
| O1 Sicherung konsistent | S | erledigt | 97214c1 | 16 % / ~0 % → 33 % / 1 % | GUI 388 grün, Unittests 660 grün; 2 Rückfragen offen (unten) |
| O2 Dateiprüfung (Größe, Import-quick_check, Schrittgrenze) | S | erledigt | f03447b | 33 % / 1 % → 41 % / 2 % | Unittests 664, GUI 393 grün; Rückfrage 3 offen |
| O3 Schnitt 1 `desktop_programm.py` (+ Patch-Helfer, Ordner-Schutz) | M | erledigt | c7a0866 | 42 % / 2 % → 53 % / 3 % | Unittests 664, GUI 394 grün |
| O4 Schnitt 2 `desktop_auswertung.py` | M | erledigt | 7cc2548 | 54 % / 3 % → 0 % / 4 % (neues 5-h-Fenster) | Unittests OK, GUI 394 grün |
| O5 Schnitt 3 `desktop_zeitplan.py` | M | erledigt | fbd85fd | 1 % / 4 % → 7 % / 4 % | Unittests OK, GUI 394 grün |
| O6 Schnitt 3b `desktop_verwaltung.py` (+ Architektur-Doku) | M | erledigt | (s. git log) | 7 % / 4 % → 16 % / 5 % | Unittests OK, GUI 394 grün; Doku der Aufteilung nachgezogen |
| O7 Ergebnis 1: Zellwert-Schnittstelle, Tests umstellen | L | offen | | | |
| O8 Ergebnis 2: Items + Delegate + Tastatur | L | offen | | | nach O7 |
| O9 Ergebnis 3: Demo, Darstellung, Handbuch, Screenshots | M | offen | | | nach O8 |
| O10 Messung Lasttest-1000 | S | offen | | | nach O9 |
| O11 Abschluss (QS 3 Rollen, Doku, Bericht) | M | offen | | | zuletzt |

Status: offen / läuft / erledigt / zurückgestellt (mit Grund).

## Kalibrierung

Startwerte als Anteil am 5-h-Fenster: S ≈ 15 %, M ≈ 20 %, L ≈ 30 %. Nach jeder Aufgabe den
gemessenen Verbrauch eintragen und die Werte nachjustieren.

Limitregel: weiter nur, wenn **Nutzung + Schätzung + 3 % ≤ 100 %**. Das gilt für den 5-h- und
den 7-Tage-Wert aus `%USERPROFILE%\.claude\shs-limit.json`. Fehlt `five_hour`, hat ein neues
Fenster begonnen (≈ 0 %). Passt die nächste Aufgabe nicht, aber eine kleinere: diese vorziehen
(Reihenfolgebindungen beachten). Passt keine: `ScheduleWakeup` bis `resets_at` (höchstens 3600 s
je Schritt, `noop: true`).

Stand beim Anlegen (18.10. 18:45): 5 h 56 %, 7 Tage 89 %. Reset 5 h am 18.10. um 22:20,
7 Tage am 19.10. um 00:00.

## Ablauf je Aufgabe (Kurzfassung des Skills)

1. Limit prüfen, Status „läuft“, Limit vorher eintragen. Steht schon „läuft“ aus einer
   abgebrochenen Runde: `git status`/`git diff` prüfen und fortsetzen, nicht neu beginnen.
2. Ein Explore-Subagent liefert die aktuellen Stellen (die Zeilen unten veralten). Immer nur ein
   Subagent gleichzeitig.
3. Umsetzen per Python-Skript im Scratchpad, angelegt mit dem Write-Werkzeug, nicht per Heredoc.
   Eindeutige Ersetzungen mit Trefferzählung, Zeilenenden der Datei erhalten
   (`desktop_dialoge.py` und `desktop_demo.py` haben CRLF, der Rest LF).
4. Tests mit Gegenprobe: `git stash push <programmdateien>`, die neuen Tests müssen scheitern,
   dann `git stash pop`.
   - `C:\Users\mbruv\anaconda3\python.exe -m unittest test_db test_db_postgres_wrapper test_backup test_pdf_export test_app_web test_bump_version test_shs_core test_bewertung_referenz test_altversionen`
   - GUI: `QT_QPA_PLATFORM=offscreen C:\Users\mbruv\anaconda3\python.exe -m pytest test_app_gui.py test_theme.py -q`
     als Hintergrundlauf (dauert rund 90 s).
   - Bekannt rot und fokusbedingt (auch ohne Änderungen): `test_bezahlt_checkbox_im_teilnehmer_dialog`
     und `test_strg_s_speichert_in_der_ergebniserfassung`. Jeder weitere rote Test ist ein Befund.
5. Verifikation mit dem Agenten `verifikation`. Befunde innerhalb der Aufgabe beheben, neue Punkte
   als Aufgabe eintragen, Unklares unter „Rückfragen an Marco“ und den Teilpunkt zurückstellen.
6. Abschnitt in `Fortschritt.md`, bei Bedarf `docs/HANDBUCH.md` und `Architektur.md`.
7. Lokaler Commit (`git commit -F <datei>`), Footer
   `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
8. Diese Tabelle aktualisieren, kurze Meldung, `ScheduleWakeup` (60 s, wenn das Limit reicht).

## Entscheidungen (Marco, 18.10.2026)

### O1 Sicherung
- Je Termin-Datei ein `sqlite3`-Backup im Speicher:
  - `db.oeffne_termin_lesend(pfad)` als Quelle, `sqlite3.connect(":memory:")` als Ziel;
  - `src.backup(dst)`, dann `zf.writestr(name, dst.serialize())`;
  - Python ab 3.11 (CI und Build erfüllen das).
- Keine Temp-Datei mit Personendaten.
- Dateien, die sich nicht lesend öffnen bzw. sichern lassen (kaputt, fremd), werden **wie heute
  roh** mitgesichert. Eine zugehörige `<name>-journal`-Datei wird mitgesichert.
- **Nichts** wird in die Quelldatei geschrieben, also kein Journal-Zurückspielen.
- Die Erfolgsmeldung nennt die roh gesicherten Dateien.
- Das gilt auch für den geöffneten Termin außerhalb des Ordners (`zusaetzliche`).

### O2 Dateiprüfung
- Größengrenze **50 MB** (Konstante in `db.py`):
  - In `termin_lesend_pruefen`, also Startdialog-Liste und Import, gilt eine größere Datei als
    nicht lesbar mit dem Grund „ungewöhnlich groß“.
  - In `termin_oeffnen` gibt es eine Rückfrage „ungewöhnlich groß (N MB), trotzdem öffnen?“. Der
    Aufrufer in `app.py` zeigt sie. Technisch über einen Parameter
    (`groesse_bestaetigt`/Rückruf) oder eine eigene Ausnahme, die der Aufrufer abfragt und dann
    mit Bestätigung erneut aufruft.
- Der Import (`TerminImportDialog._termin_gewaehlt`) prüft die gewählte Quelle zusätzlich mit
  `PRAGMA quick_check`. Die Liste im Startdialog prüft nicht so (Start bleibt schnell).
- Scheitert eine Datei an der Rechenschritt-Grenze (`lesen_begrenzen`, `OperationalError
  interrupted`), heißt die Meldung „zu groß bzw. zu aufwendig zu prüfen“ statt „beschädigt“.

### O3–O6 `app.py` aufteilen
- Nur die Schnitte 1–3b; Teilnehmer-Tab, Formular-Import, Ergebnis-Tab, Hauptfenster, StartDialog
  und main bleiben in `app.py` (danach rund 2900 Zeilen).
- Module:
  - `desktop_programm.py`: Version/Update, Sitzung, Zweitstart;
  - `desktop_auswertung.py`: Auswertungshelfer, `AuswertungTab`, `TeilnehmerUebersichtTab`,
    `ExportTab`;
  - `desktop_zeitplan.py`: `ZeitplanTab`;
  - `desktop_verwaltung.py`: `VerwaltungTab`, `DatensicherungTab`.
- Code unverändert verschieben (Syntaxbaum/Zeilenbereiche), `app.py` holt die Namen per
  `from desktop_x import (...)` zurück.
- Neue Module importieren **nie** `app` (wegen `__main__`, siehe `desktop_demo.py:13`). Was sie aus
  `app.py` brauchen, gehört nach `desktop_gemeinsam.py`.
- Testpatches werden auf `"desktop_x.Name"` umgestellt. Mehrfach genutzte Namen laufen über einen
  Patch-Helfer in `test_app_gui.py`, der in allen Modulen ersetzt, die den Namen haben (Muster:
  Fixture `darstellung_speicher` bzw. Modulschleife in `tools/screenshots.py` 138–148). Betroffen:
  `termine_ordner`, `_db_fehler_anzeigen`, `_ausfuehren`, `_datei_gespeichert_melden`,
  `_aktualisiere_veranstaltung_feld`, `_zeitplan_pdf_exportieren`.
- Ein Schutz (autouse-Fixture) sorgt dafür, dass `termine_ordner()` in allen Modulen auf einen
  Temp-Ordner zeigt bzw. ein Schreibversuch in den echten Ordner den Test scheitern lässt.
- Die Re-Exports in `app.py` schrumpfen auf das Nötige: Namen, die `app.py` selbst nutzt, die
  Klassen für `from app import` in `test_app_gui.py` und das, was `selbsttest.py:216–221` braucht.
  Ein veralteter `"app.X"`-Patch scheitert dann mit AttributeError.
- Pro Schnitt ein Commit. `tools/screenshots.py` (Modulliste), `build.spec` (Kommentar 46–52),
  `Architektur.md` (Diagramm Z. 26, Modultabelle Z. 96, Patch-Ziele 194–199) und die Zeilenzahlen
  in `CLAUDE.md`/`AGENTS.md` nachziehen, spätestens in O6.

### O7–O10 Ergebnisserfassung ohne Widgets je Zelle
- Variante A: `QTableWidget` bleibt, Punktezellen werden `QTableWidgetItem` mit einem
  `QStyledItemDelegate`. Der Editor (`QLineEdit` mit `_punkte_validator`) erscheint nur beim
  Bearbeiten.
- Aussehen: Zellen **umrandet wie heute** (Rahmen im Delegate gezeichnet), Häkchen für DQ/Abbruch
  **mittig** (`ItemIsUserCheckable` mit `paint`/`editorEvent`), gesperrte Zellen grau und leer.
- Tastatur:
  - In einer markierten Zelle **direkt lostippen** ersetzt den Wert.
  - **Tab** wie heute: Suche → Anzeige → nächste Disziplin → DQ → Abbruch → nächste Zeile.
    Gesperrte Zellen, Info-Spalten und „–“ werden übersprungen.
  - **Enter** übernimmt und bleibt in der Zelle. Die **Leertaste** schaltet das Häkchen.
  - Strg+S, Reiterwechsel, Schließen und „Alle speichern“ übernehmen zuerst einen offenen Editor.
    Die zuletzt getippte Zahl darf nie verloren gehen.
- Akzeptierte Abweichungen:
  - Gelbe Zeile bzw. roter Rahmen über dem Maximum erst nach dem Übernehmen (Verlassen der Zelle
    bzw. Enter).
  - Die Demo markiert das Zellenrechteck (`visualRect`).
  - Leicht anderes Aussehen in Hell/Dunkel/Hoher Kontrast; die Screenshots werden neu aufgenommen.
- Ziel bei `Lasttest-1000`: Ansichtswechsel **< 0,3 s**, Reiterwechsel mit Neuaufbau und
  Sortieren **< 0,5 s**. Messskript nach `tools/`.
- **Tests:**
  - Alle Ergebnis-Tests werden auf eine **neue Zellwert-Schnittstelle** am `ErgebnisTab`
    umgestellt, nicht über Stellvertreter-Objekte.
  - Dazu kommen eigene Tastatur-Tests (Lostippen, Tab überspringt, Enter, Leertaste, kein Verlust
    bei offenem Editor).
  - Die Identitätsprüfungen „kein Neuaufbau“ (heute `is suche_feld`) laufen über einen Zähler bzw.
    eine Aufbau-Kennung.

## Aufgaben im Einzelnen (Stand der Fundstellen: 18.10.2026)

### O1 Sicherung konsistent (S)
- Code:
  - `db_sicherung.py:152–211` `sicherung_erstellen`: heute `zf.write(datei, arcname=name)`
    bzw. `AESZipFile.write`, Dateien aus `ordner.glob("*.sqlite")` plus `zusaetzliche`.
  - Aufrufer: `app.py` `DatensicherungTab._sicherung_erstellen` (~3920–3953).
- Grenze: 200 MB je Datei (S-8) beachten, bestehende Prüfung beibehalten.
- Tests in `test_backup.py` (`TestSicherungErstellen` ab Z. 58):
  - Die vorhandenen Tests bleiben grün, Byte-Gleichheit ist kein Kriterium mehr.
  - Neu: eine zweite Verbindung hält `BEGIN` + `INSERT` ohne Commit; die Sicherung lässt sich
    öffnen, `quick_check` liefert ok, der ungespeicherte Satz fehlt.
  - Neu: halb geschriebener Stand mit liegengebliebenem Journal (Muster `test_db.py:3066–3077`);
    roh gesichert samt `-journal`, Quelle unverändert.
  - Neu: kaputte Datei, roh gesichert und in der Rückgabe bzw. Meldung genannt.
- Wiederherstellung (`db_sicherung.py:306 ff.`) muss die `-journal`-Datei mit zurückschreiben
  oder bewusst nicht. Beim Umsetzen prüfen; ist das unklar, Rückfrage eintragen.

### O2 Dateiprüfung (S)
- Code:
  - `db.py:2489–2504` `termin_lesend_pruefen`;
  - `db.py:2624 ff.` `termin_oeffnen` (Reihenfolge: Journal → lesend → `lesen_begrenzen` →
    `pruefe_termin_aufbau` → `quick_check` → `init_db` → Schreibprobe → Wertebereiche);
  - `db.py:2436–2472` `lesen_begrenzen`;
  - `desktop_dialoge.py` `TerminImportDialog._termin_gewaehlt` (~819 ff.);
  - Aufrufer von `termin_oeffnen`: `main` und Terminwechsel (`_termin_oeffnen_mit_meldung`).
- Tests:
  - Größengrenze per monkeypatch klein setzen (Liste/Import „nicht lesbar“; Öffnen fragt, Nein
    bricht ab, Ja öffnet).
  - Beschädigte Seite ohne Journal, bei der Aufbau und erste Abfrage gelingen: der Import meldet
    „nicht lesbar“. Gegenprobe rot.
  - Schrittgrenze per monkeypatch gesenkt: eigene Meldung.

### O3 Schnitt 1 `desktop_programm.py` (M)
- Code: `app.py` ~4090–4429.
  - Update-Adressen, `_version_tupel`, `_neueste_version_pruefen`, `_UpdateBote`, `VersionDialog`;
  - `SitzungsendeFilter`, `_lauf_mutex`/`_zweitstart_sperre` (Modulvariablen!),
    `zweitstart_pruefen`, `laufkennung_setzen`, `sitzungsende_einrichten`.
- Patches: 10 Stellen per `setattr(app, …)`, u. a. `_neueste_version_pruefen` (7) sowie
  `_ordner_zeigen`, `_zweitstart_sperre` und `_lauf_mutex` (je 1).
- Erster Schnitt, deshalb gehören hierher auch Patch-Helfer, Ordner-Schutz, die Regel für
  Re-Exports und die Modulliste in `tools/screenshots.py`.

### O4 Schnitt 2 `desktop_auswertung.py` (M)
- Code: `app.py` ~2426–2834 (Auswertungshelfer, `AuswertungTab`, `TeilnehmerUebersichtTab`) und
  ~3494–3758 (`_EXCEL_CSV_HINWEIS`, `ExportTab`).
- Patches: `exportiere_teilnehmer_csv` (2), `_zeitplan_pdf_exportieren` (1), `termine_ordner`
  (Helfer).
- Achtung: `HauptFenster` erzeugt `TeilnehmerUebersichtTab`. Den Patch
  `"app.TeilnehmerUebersichtTab"` behalten (der Name bleibt in `app` importiert, weil das
  Hauptfenster ihn nutzt).

- Nachtrag aus der Verifikation von O4 (für O6): Zeilenangaben der Teile 1 und 8 im Skill
  `desktop-pruefung` (beide Spiegel) erneuern; Kommentar „siehe BewertungsbogenAuswahlDialog
  oben“ in `desktop_auswertung.py` (bei `ExportTab`) auf `desktop_dialoge.py` korrigieren;
  `app.QDesktopServices` NICHT als „unbenutzt“ entfernen (Tests patchen es).

### O5 Schnitt 3 `desktop_zeitplan.py` (M)
- Code: `app.py` ~2836–3489 `ZeitplanTab`.
- Patches (~8): `PauseDialog` (2), `zeitplan_richter_aus_veranstaltung_anlegen`,
  `_zeitplan_pdf_exportieren`, `_aktualisiere_veranstaltung_feld` (Helfer), `_db_fehler_anzeigen`
  (Helfer).
- Die Attrappe `_pause_dialog_attrappe` ist schon gebündelt; nur das Patchziel ändert sich.

### O6 Schnitt 3b `desktop_verwaltung.py` (M)
- Code: `app.py` ~3761–4081 (`VerwaltungTab`, `DatensicherungTab`).
- Patches (~15): `termine_ordner` (5), `sicherung_inhalt` (5), `sicherung_wiederherstellen` (2),
  `sicherung_erstellen`, `SicherungErstellenDialog`, `_datei_gespeichert_melden`,
  `_aktualisiere_veranstaltung_feld`.
- Danach die Doku nachziehen (siehe Entscheidungen).

### O7 Ergebnis 1: Zellwert-Schnittstelle (L)
- `ErgebnisTab` (`app.py` ~1419–2384) bekommt öffentliche Methoden. Vorschlag; Namen beim
  Umsetzen festlegen und hier eintragen:
  - `punkte(zeile, disziplin) -> (str, str)`
  - `punkte_eintragen(zeile, disziplin, suche, anzeige)`
  - `status(zeile) -> (bool, bool)`
  - `status_setzen(zeile, dq, abbruch)`
  - `zelle_gesperrt(zeile, disziplin) -> bool`
  - `zellzustand(zeile, disziplin) -> {"ungespeichert", "zu_hoch", "tooltip": ...}`
  - `zelle_bearbeiten(zeile, disziplin, feld)`: öffnet den Editor bzw. gibt ihn zurück, für
    Tastatur-Tests
  - `aufbau_kennung`: Zähler je `_zeilen_aufbauen`, ersetzt die `is`-Prüfungen
- Umgesetzt zunächst über die heutigen Widgets, ohne Verhaltensänderung.
- Umstellen: alle ~67 Ergebnis-Tests (43 mit direktem Widget-Zugriff, Beispiele 934, 973, 1113,
  1160, 1227, 1270, 1277, 1350, 3631, 3692, 3719, 3729, 3772, 5642, 5897, 6263, 6295, 7454, 7494,
  7508, 7542). Dazu `eingabefelder()`-Verbraucher in `desktop_demo.py` (1158–1188) und
  `tools/screenshots.py` (335–342).
- Alle Tests grün; die Gegenprobe entfällt, weil sich nichts am Verhalten ändert. Ein voller Lauf
  vorher/nachher mit identischem Ergebnis genügt.

### O8 Ergebnis 2: Items + Delegate (L)
- `_zeilen_aufbauen` (~1642–1794) ohne `setCellWidget`. Ein Delegate für die Punktespalten:
  - `createEditor` mit Validator, `inputRejected` → `_eingabe_abgelehnt`;
  - Rahmen, roter Rahmen und Tooltip über Rollen.
- Checkbox-Delegate mittig.
- `_punkteeingabe_sperren` über Flags, `_aktualisiere_zeilenstatus` über `setBackground` und
  Rollen.
- `_sortierschluessel_fuer_zeile`, `_eingaben_je_id`, `alle_speichern`, `_zeile_ist_ungespeichert`
  und `_zeile_ist_leer` lesen aus den Items.
- `_spaltenbreiten_anpassen` ohne `setFont`-Schleife, Zeilenhöhe aus dem Font.
- Tastatur: `setTabKeyNavigation(True)` mit `moveCursor`-Override, Bearbeitungsauslöser
  `AnyKeyPressed | DoubleClicked | SelectedClicked | EditKeyPressed`, Enter bleibt, Leertaste
  schaltet.
- Vor Speichern, Reiterwechsel, Schließen und Strg+S: `commitData` bzw. `closePersistentEditor`
  auf den aktiven Editor.
- `desktop_darstellung.py` 117–131 (Feldrahmen) und 223–242 (Indikator) für den Delegate nutzen.
- Neue Tastatur-Tests.

### O9 Ergebnis 3: Demo, Darstellung, Doku (M)
- `desktop_demo.py` 1158–1188: Eintippen über die Schnittstelle, Markierung über
  `tabelle.visualRect(index)` (`DemoMarkierung` 683–690 braucht ein Rechteck statt eines Widgets).
- Hell/Dunkel/Hoher Kontrast prüfen (Screenshots).
- `docs/HANDBUCH.md` (~605: Tab-Taste, Lostippen, Enter, Leertaste).
- Screenshots der Ergebniserfassung mit `tools/screenshots.py` neu (Details im Skill `shs-build`).
  Geht das nicht: Rückfrage eintragen, nicht ohne Bilder weiter.

### O10 Messung (S)
- Messskript `tools/lasttest_ergebniserfassung.py`:
  - erzeugt bzw. nutzt einen Termin mit 1000 TN (bisher `Lasttest-1000.sqlite`, nicht im Repo,
    also selbst erzeugen);
  - misst Reiterwechsel mit und ohne Neuaufbau, Sortieren, „Alle speichern“, Ansichtswechsel und
    Speicher.
- Vergleich mit den Werten aus `Fortschritt.md` (1.0.48/1.0.49). Ziele < 0,3 s bzw. < 0,5 s.
  Verfehlt: Rückfrage eintragen.

### O11 Abschluss (M)
- QS über `fb1918a..HEAD` nacheinander mit `qs-sicherheit`, `qs-korrektheit` und
  `qs-wartbarkeit`, je Befund Gegenprüfung. Befunde innerhalb des Auftrags beheben, alles Weitere
  unter „Rückfragen an Marco“.
- Doku abgleichen: `Architektur.md`, `CLAUDE.md`/`AGENTS.md`, `docs/HANDBUCH.md`,
  `Fortschritt.md`.
- Abschlussbericht in `Fortschritt.md` und hier:
  - Commits, zurückgestellte Punkte, Rückfragen;
  - ausstehende Sichtprüfungen: neue Ergebniserfassung am echten Windows, Mac/Linux-Vorschau;
  - Hinweis: vor dem nächsten Build Screenshots und HANDBUCH.pdf.
- Loop mit `ScheduleWakeup(stop: true)` beenden, PushNotification an Marco.

## Rückfragen an Marco

1. **O1, alte Rücksprung-Datei beim Wiederherstellen:**
   - Liegt neben dem Ziel noch eine alte `<Ziel>-journal` (etwa nach einem Absturz) und enthält
     das ZIP keine, bleibt sie liegen. Beim nächsten Öffnen spielt SQLite sie auf die neu
     wiederhergestellte Datei zurück, der Inhalt kann dabei beschädigt werden. Das war schon vor
     O1 so.
   - Vorschlag: eine solche Datei beim Ersetzen wegräumen (Papierkorb oder löschen).
   - Bis zur Entscheidung bleibt es wie bisher.
2. **O1, Journal mit zurückschreiben:** Beim Wiederherstellen wird eine im ZIP enthaltene
   `-journal` mit zurückgeschrieben (sonst wäre das Mitsichern wirkungslos). Das stand nicht
   ausdrücklich in deiner Entscheidung, bitte bestätigen.
3. **O2, Wortlaut in der Terminübersicht:** Eine Datei über 50 MB steht als „… (nicht lesbar: zu
   groß)“ da, lässt sich aber nach der Rückfrage trotzdem öffnen (sonst wäre die Rückfrage nicht
   erreichbar). Lieber „… (ungewöhnlich groß)“ ohne „nicht lesbar“? Bis zur Entscheidung bleibt
   es wie beschlossen.

## Hinweise für den Abschlussbericht

- Sechs Commits aus Gruppe 1–3 lagen schon vor O1 ungepusht vor (`fb1918a`…`cc1c192`).
- Die CI (GUI auf Linux, echte PostgreSQL-Tests) läuft erst nach Marcos Push.
