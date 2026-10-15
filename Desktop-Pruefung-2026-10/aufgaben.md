# Desktop-Prüfung: Aufgabenliste zur automatischen Abarbeitung

## Status (vor jeder Aufgabe lesen, danach aktualisieren)

| Aufgabe | Größe | Status | Commit | Limit vorher → nachher (5 h) | Bemerkung |
|---|---|---|---|---|---|
| A1 Darstellung/Stylesheet | M | erledigt | 9ed5622 | 64 % → 78 % | Kontrolle am echten Rechner mit „Apps: dunkel“ steht aus; alte %TEMP%\SHS-Pruefungsprogramm\haken.png wird nicht aufgeräumt (bedeutungslos) |
| A2 PDF maskieren [S] | M | erledigt | 265a064 | 78 % → 93 % | KeyError bei ungültiger stufe/disziplin → A8 |
| A3 Terminliste/Termin-Import [S] | M | erledigt | b04ae43 | ~0 % → 32 % | 2. Sicherheitsrunde (berechnete Spalten); Punkte für A8/A9 vermerkt |
| A4 Schreibfehler/Rollback | L | erledigt | 45dbb04 | 32 % → 62 % | Importmeldung ohne Anzahl → A12 |
| A5 Ergebniserfassung | M | erledigt | a08f25d | 62 % → 78 % | |
| A6 CSV/Excel | M | erledigt | 14b104a | ~0 % → 42 % | Restrisiken in Fortschritt.md |
| A7 Demoprüfung | M | erledigt | 73eccec | 42 % → 58 % | Sichtprüfung Taskleiste am echten Windows offen |
| A8 Termin öffnen/Lebenszyklus | L | erledigt | 8debf9e | 58 % → 85 % | Journal-Rückspielen ergänzt (Verifikation) |
| A9 Fehlerprotokoll/Klartext | M | erledigt | d416766 | 0 % → 20 % | Verifikation: Selbstblockade, Qt-Grenze nachgearbeitet; OSError bei „Sicherung auswählen“ → A11 |
| A10 Rückfrage ungespeichert | S | erledigt | bc5ba89 | 78 % → 88 % | vorgezogen: A6 (M) passte bei 78 % nicht |
| A11 Startdialog/Datensicherung | M | erledigt | c913cb7 | 21 % → 37 % | Verifikation: moveToTrash liefert bool (behoben); zweite Rückfrage ohne Papierkorb ergänzt |
| A12 Teilnehmerliste | S | erledigt | db0b992 | 38 % → 55 % | S brauchte 17 %; Verifikation: Reihenfolge Lesen/Import, Grammatik, Handbuch |
| A13 Teilnehmer-/Veranstaltungsdialog | M | erledigt | 0039fdc | 56 % → 76 % | Verifikation: Ordnerpfad ohne Namen, toter Code, Handbuch; Doppelung aus A12 entfernt |
| A14 Auswertung/Zeitplan | S | erledigt | baa14bd | 77 % → 89 % | Verifikation: verlorener Klick nach Startzeit-Eingabe behoben; T4-1 dokumentiert |
| A15 Update/Selbsttest/Zweitstart | M | erledigt | a1a6007 | 0 % → 14 % | Timer an Fenster gebunden; Mac-Prüfung CA offen |
| A16 PDF-Schrift und Rest | M | erledigt | b7f55e5 | 15 % → 37 % | Condensed statt normaler Breite (Tabellen), Helvetica für feste Texte; CSV-Ablauf zurückgestellt |
| A17 Dialoge/Wartecursor | S | erledigt | 91ee216 | 38 % → 45 % | Verifikation ohne Fehler |
| A18 Import-Rest | S | erledigt | beb3e7c | 45 % → 55 % | Verifikation ohne Fehler |
| A19a QS-Befund N-1 [S] (table_xinfo-Name als Parameter) | S | erledigt | 47175ce | 55 % → | aus qs-sicherheit A19; Python 3.11 warf sqlite3.Warning statt Error |
| A19b QS-Korrektheit K-1..K-3 + Stechen | S | erledigt | 8dfe7e8 | 0 % → 9 % | aus qs-korrektheit A19 (66 % → 89 %) |
| A19c QS-Wartbarkeit (Stil) | S | erledigt | 7bfcfb2 | 9 % → 15 % | größere Umbauten zurückgestellt (Fortschritt.md) |
| A19 Abschluss | M | erledigt | e376f29 | 55 % → 16 % (mit Reset) | QS dreifach; A19a–c; Doku |

Status-Werte: offen / läuft / erledigt / zurückgestellt (mit Grund).

## Kalibrierung der Schätzung

Startwerte: S ≈ 5 %, M ≈ 10 %, L ≈ 20 % des 5-h-Fensters. Nach A1 (M = 14 %): S ≈ 7 %,
M ≈ 14 %, L ≈ 25 %. Nach A3 (M = 32 % mit 2. Sicherheitsrunde): S ≈ 10 %, M ≈ 20 %, L ≈ 30 %. Nach A12 (S = 17 %): S ≈ 15 %. Nach jeder Aufgabe den gemessenen
Verbrauch in der Statustabelle eintragen und die Werte hier anpassen.

Limitquelle: `%USERPROFILE%\.claude\shs-limit.json` (schreibt die Statuszeile). Ist die Datei älter als
10 Minuten oder steht dort `"rate_limits": null`, gilt nur die Schätzung.

## Rückfragen an Marco (während der Abarbeitung entstanden)

(noch keine)

## Hinweise für Marco (für den Abschlussbericht)

- A11: Löschen in den Papierkorb einmal am echten Windows ausprobieren (lokal nur mit Attrappe getestet; ein Probelauf legte eine Testdatei `t.txt` aus dem Temp-Ordner in den Papierkorb).
- A16: Schrift DejaVu Sans **Condensed** statt normaler Breite (sonst Umbrüche mitten im Wort), zusätzlich Kursiv; Kopf der Statistik-Matrix, Etikett-Punktfelder und Formularfelder bleiben Helvetica. PDFs vor dem Build einmal ansehen.
- A15: Am echten Mac prüfen, ob die Update-Prüfung über HTTPS geht (CA-Zertifikate; Selbsttest-Schritt zeigt die Anzahl).
- A11: Termin löschen fragt ohne Papierkorb ein zweites Mal (Vorgabe „Nein“) – über Marcos Entscheidung hinaus, zur Sicherheit.

- Die Commits zu A1, A2 und A3 enthalten Tests, die die Sicherheitsbefunde nachstellen (S-4-Test mit
  Feldern, fremde Termin-Dateien). Deshalb **nur zusammen mit dem Release pushen**, nicht vorab etwa
  für die CI. Das gilt ebenso für Architektur.md-Änderungen in diesen Commits.

## Context

Die Desktop-Prüfung (Teile 1–10, 13./14.10.2026) ist abgeschlossen. Die Berichte liegen in
`Desktop-Pruefung-2026-10/teil-01.md` … `teil-10.md` und `uebersicht.md`. Insgesamt
gibt es 107 bestätigte Befunde: 1 hoch, 8 mittel, rund 40 niedrig, der Rest optional. 3 davon
sind Sicherheitsbefunde. Marco gibt mit diesem Plan das Go für **alle** Befunde. Abgearbeitet wird
von hoch nach optional, zusammenhängende Befunde als eine Aufgabe, automatisch und über
Nutzungslimit-Pausen hinweg, bis alle Aufgaben erledigt sind.

## Entscheidungen von Marco (14.10.2026)

| Punkt | Entscheidung |
|---|---|
| T1 Nr. 6 / T2 Nr. 13 nicht angebotene Prüfungen | Termin-Import übernimmt und meldet danach „N Teilnehmer in hier nicht angebotenen Prüfungen: … bitte LK anpassen“. Hand-Erfassung fragt „wird nicht angeboten, trotzdem speichern?“. `Architektur.md` wird angepasst. |
| T4 Nr. 1 Stechen bei gewachsener Gruppe | **Kein Code.** Je LK und Disziplin gibt es nur ein Stechen, und das erst ganz am Ende. Danach kann niemand mehr dazukommen. Als „fachlich ausgeschlossen“ dokumentieren. |
| T6 Nr. 3 Telefonnummern | „'“ voranstellen bei „+“/„-“ ohne Leerzeichen. Der Import entfernt es wieder. |
| T5 Nr. 1 / Excel-Weg | Der Import erkennt Werte wie `2,76E+14` und übernimmt sie mit Hinweis je Zeile. Die Meldung nach dem CSV-Export bekommt einen Hinweis, das Handbuch je einen Satz in Kap. 5 und 9. Kein xlsx-Export. |
| T9 Nr. 1 Design „Hell“ | Immer eine feste helle Palette. Hebt Fortschritt.md:1805f. auf. |
| T6 Nr. 2 Sonderbuchstaben im PDF | Unicode-Schrift DejaVu Sans mitliefern (`build.spec`, Lizenzdatei). |
| T7 Nr. 5 Termin löschen | Vorgabe „Nein“ und Löschen in den Papierkorb (`QFile.moveToTrash`). Ohne Papierkorb wird wie bisher endgültig gelöscht. |
| T7 Nr. 1 Sicherung, Termin außerhalb des Ordners | Rückfrage „Mitsichern / Ohne ihn fortfahren / Abbrechen“. |
| T7 Nr. 4 Schreibprobe beim Öffnen | Ja, `PRAGMA user_version = <aktuell>`. Dass sich dabei der Zeitstempel ändert, ist akzeptiert. |
| T8 Nr. 6 Zweiter Programmstart | Rückfrage, keine Sperre (`QLockFile`). |
| Commits | Lokaler Commit je Aufgabe. Kein Push, kein Tag, kein Versionsbump, kein Build. |
| Limit | Statuszeile schreibt die Limitwerte in eine Datei, dazu ein Fortsetzungs-Loop (siehe unten). |

Ohne Rückfrage festgelegte Standards (nach den Empfehlungen der Berichte):
- T8 Nr. 2: Rückfrage `Save | Discard | Cancel`, Vorgabe Save, Esc = Cancel.
- T8 Nr. 5: Update-Prüfung im Hintergrund-Thread mit Gesamtzeitgrenze.
- T3 Nr. 2: eigenes Hinweis-Label.

## Einrichtung (Schritt 0, vor Aufgabe 1)

1. Diesen Plan als `Desktop-Pruefung-2026-10/aufgaben.md` ablegen. Er ist die maßgebliche
   Liste, mit Status je Aufgabe (offen / läuft / erledigt + Commit / zurückgestellt + Grund). Er liegt
   nicht im Repo, weil er Sicherheitsdetails enthält.
2. In `Fortschritt.md` kommt ein kurzer, allgemeiner Briefing-Abschnitt: „Abarbeitung Desktop-Prüfung,
   Liste in `_unveroeffentlicht/…/aufgaben.md`“, ohne Sicherheitsdetails. Dieser Dokumentations-Commit
   ist erlaubt.
3. Statuszeile über den Agenten `statusline-setup`: Das Skript schreibt das `rate_limits`-JSON aus der
   Statuszeilen-Eingabe (5 h und 7 Tage, Prozent und Reset) nach `%USERPROFILE%\.claude\shs-limit.json`.
   Liefert Claude Code diese Felder nicht, gilt nur die Schätzung (siehe unten). Das wird in `aufgaben.md`
   vermerkt.
4. Marco startet die Abarbeitung mit
   `/loop Arbeite die nächste offene Aufgabe aus Desktop-Pruefung-2026-10/aufgaben.md nach dem dort beschriebenen Ablauf ab.`
   Jeder Loop-Durchlauf erledigt genau eine Aufgabe.

## Ablauf je Aufgabe

1. **Limit prüfen:** `shs-limit.json` lesen.
   - Weiter nur, wenn `5h-Nutzung + Schätzung + 3 % ≤ 100 %`. Gleiches gilt für das 7-Tage-Limit.
   - Schätzung je Größe (nach den ersten Aufgaben an den gemessenen Werten nachjustieren, Werte in
     `aufgaben.md` festhalten): S ≈ 5 %, M ≈ 10 %, L ≈ 20 % des 5-h-Fensters.
   - Passt die nächste Aufgabe nicht, aber eine kleinere offene, kommt diese vor. Das wird vermerkt.
   - Passt keine, folgt `ScheduleWakeup` bis `resets_at` (höchstens 3600 s, notfalls in Ketten), dann
     wieder bei Schritt 1.
   - Bricht das harte Limit eine Aufgabe ab, setzt der nächste Durchlauf an der Aufgabe mit dem Status
     „läuft“ fort: Arbeitsstand per `git status`/`git diff` prüfen, nicht neu beginnen.
2. **Lokalisieren:** ein Explore-Subagent findet die aktuellen Stellen. Die Zeilennummern in den
   Berichten verschieben sich durch frühere Aufgaben. Es läuft immer nur **ein** Subagent zugleich
   (Memory „Agents nach Limit fortsetzen“).
3. **Umsetzen und testen**, mit Tests zu jedem Befund:
   - Lokal: `%USERPROFILE%\anaconda3\python.exe -m unittest test_db test_db_postgres_wrapper test_backup test_pdf_export test_app_web test_bump_version test_shs_core test_bewertung_referenz test_altversionen`.
   - Dazu die passende GUI-Teilmenge: `%USERPROFILE%\anaconda3\python.exe -m pytest test_app_gui.py test_theme.py -k <Bereich>`.
     Vor dem Commit einmal den ganzen Satz `test_app_gui.py test_theme.py`.
4. **Verifikation:** Subagent `verifikation` prüft Diff und Tests gegen die Befunde der Aufgabe. Bei
   Sicherheitsaufgaben zusätzlich `qs-sicherheit`.
   - Befunde innerhalb der Aufgabe werden behoben.
   - Neue Befunde außerhalb der Aufgabe kommen als neue Aufgabe an passender Stelle in die Liste.
   - Fachlich unklare Punkte werden **nicht geraten**. Sie kommen in den Abschnitt „Rückfragen an Marco“
     in `aufgaben.md`, die Aufgabe bzw. der Teilpunkt wird als „zurückgestellt“ markiert, und es geht
     mit der nächsten Aufgabe weiter.
5. **Dokumentieren:**
   - `Fortschritt.md`-Eintrag. Sicherheitsbefunde nur allgemein („Sicherheitskorrektur S-x, Details
     folgen“).
   - Bei geänderter Bedienung `docs/HANDBUCH.md` bzw. `Architektur.md` anpassen.
   - In `uebersicht.md` und `aufgaben.md` den Status setzen.
6. **Commit** lokal mit Attribution-Footer und allgemeiner Commit-Nachricht bei Sicherheitsbezug. Kein Push.
7. **Ende:** Wenn alle Aufgaben erledigt bzw. zurückgestellt sind, Loop stoppen, Abschlussmeldung schreiben
   und eine PushNotification an Marco senden.

## Aufgaben (Reihenfolge = Abarbeitung)

Kennzeichnung der Befunde: `T<Teil>-<Nr>`. **[S]** = Sicherheitsbefund.

### Hoch

**A1 Darstellung und Stylesheet** (M): T9-1 (hoch), T9-2, T9-3 [S], T9-9, T9-12 (Theme-Teil), T9-11 (Texte in `desktop_darstellung.py`).
- „Hell“ bekommt eine feste Palette über `_design_palette` bzw. `_DESIGNS["hell"]`, dazu ab Qt 6.8
  `styleHints().setColorScheme` mit `hasattr`-Prüfung.
- Häkchen-URL in Anführungszeichen, mit Maskierung.
- Das Häkchen-Bild liegt im benutzereigenen Ordner (`termine_ordner().parent`) und wird bei jedem Start
  atomar neu geschrieben.
- `QAbstractItemView::indicator` aufnehmen.
- Tests:
  - Parse-Test aller 12 Kombinationen mit „ü“, „'“ und Leerzeichen über `qInstallMessageHandler`;
  - Test „Hell bei dunkler Palette“.
- Kommentar zu Fortschritt.md:1805 bzw. Handbuch anpassen.
- Dateien: `desktop_darstellung.py`, `desktop_dialoge.py` (Hilfetext), `test_theme.py`.

### Mittel

**A2 PDF: alle Nutzertexte maskieren** [S] (M): T6-1, T2-8b, T6-4.
- `_datum_kurz` und `_euro_text` liefern maskiert. `_p_wert` für Impfdatum, Zuordnung, LK-Label und
  Zeitplan-Disziplin.
- Die durch `KeyError` verdeckten Pfade (`stufe`, `t['disziplin']`) mitprüfen.
- Namen als `Paragraph`, damit sie umbrechen.
- S-4-Test erweitern, mit gültigem PNG und Feldern per `PRAGMA ignore_check_constraints`.
- `Architektur.md:142` prüfen.
- Dateien: `pdf_export.py`, `test_pdf_export.py`.

**A3 Terminliste und Termin-Import absichern** [S] (M): T1-1, T1-2, T7-3 [S], T7-6, Prüfung „Quelle bleibt
unverändert“ (Teil 5).
- `liste_termine`:
  - URI über `Path.as_uri()`;
  - Tabellenprüfung über `sqlite_master`;
  - `set_progress_handler`;
  - breites Fangen je Datei;
  - Sortierung robust.
- Termin-Import-Dialog:
  - Quelle mit `mode=ro` und `sqlite3.Row`;
  - Pfadvergleich über `normcase(abspath)`;
  - `sqlite3.Error` mit Meldung.
- Tests in `TestTerminuebersicht` und `test_app_gui`.
- Dateien: `db.py`, `desktop_dialoge.py`.

**A4 Schreibfehler, Rollback und DB-Klartext** (L): T3-1, T3-9 (Testteil), T2-1, T4-4, T4-5, T4-7, T1-7,
Import-Stellen aus Teil 5 (`sqlite3.Error`), T7 „`_neuer_termin`“.
- `_klartext_fehler(exc)` als Grundbaustein, zunächst für `sqlite3`-Fehler, genutzt von
  `_db_fehler_anzeigen`.
- `except sqlite3.Error` an allen genannten Schreibstellen.
- Speichern im Dialog vor `accept()` (Rückruf), damit Eingaben erhalten bleiben.
- `closeEvent` bzw. `_tab_gewechselt` brechen beim ersten Fehler ab, damit die vorhandene Nachfrage greift.
- Rollback in `tausche_startnummern` und den Zeitplanfunktionen.
- Mindestabstand: `setKeyboardTracking(False)`, Feld bei Fehler zurücksetzen.

**A5 Ergebniserfassung** (M): T3-2, T3-3, T3-4 mit T6-5 (gemeinsamer Sortierschlüssel), T3-5, T3-6, T3-7,
T3-8, T3-9 (Rest).
- Eigenes Hinweis-Label mit Rich Text nur für festen Text.
- `NoEditTriggers` und Tab-Reihenfolge.
- Qt-freier Sortierschlüssel in `db.py` (NFD ohne Kombinationszeichen plus `casefold`), genutzt im
  `ErgebnisTab` und in `pdf_export.py:1176`.
- Verworfene Disziplin-Eingaben melden.
- Stylesheet nur bei geänderter pt-Zahl neu setzen.
- Sortierpfeil anzeigen, Aliase entfernen.

**A6 CSV-Import/Export und Excel** (M): T5-1, T5-2, T5-3, T5-6, T5-10, T6-3, T6-10, Excel-Hinweis Export.
- Erkennen von Excel-Exponentenschreibweise in Chip-Nr., PLZ, Mitgl.-Nr., Telefon und
  `halter_*`-Nummern, mit Hinweis je Zeile.
- Kopfzeilenprüfung mit Verweis auf den OMA-Knopf.
- `;;;;`-Zeilen überspringen.
- NFC in `_csv_wert` und `_meldungs_schluessel`.
- „'“-Regel für Telefonnummern, symmetrischer Formelschutz.
- Parameter `hinweis` in `_datei_gespeichert_melden`.
- `docs/HANDBUCH.md` Kap. 5 und 9 ergänzen.

**A7 Demoprüfung** (M): T10-1, T10-2, T10-3, T10-4, T10-5, T10-7, T10-9, T10-10, T10-11.
- Erklärfenster unten in `availableGeometry` verankern.
- `ausweichen` nur, wenn die andere Ecke frei ist; kein Doppelsprung.
- Schritt 4 nutzt `_pruefen_und_akzeptieren`, IDs unter dem Demonamen.
- `_reiter_zeigen` in jedem Schritt.
- Startfehler im Startdialog-Weg abfangen, Merker `_gestartet`.
- „Erklärfenster zeigen“ aktiv lassen.
- Stechen je LK über `shs_core.stechen_gruppen`; Kern von `verteilen` ohne Rückfrage auslagern.
- „Durchsuchen“ in der Demo sperren.
- Tests je Punkt.
- T10-6 folgt in A9, T10-8 in A10.

### Niedrig

**A8 Termin öffnen und Lebenszyklus des Hauptfensters** (L): T7-4, T7-9, T8-3, T2-5, T9-7, Plausibilitätsprüfung
beim Öffnen (zweite Absicherung zu A2, T7-Einordnung, `quick_check`).
- `_termin_oeffnen(pfad)` für `main` und `_termin_wechseln`:
  - Prüfung vor `init_db` (leer oder Tabelle `veranstaltung`);
  - Schreibprobe;
  - Prüfung der Wertebereiche (`art`, `stufe`, `disziplin`, `gegenstand_N`, Zeitplan).
- `_termin_setzen`: erst neue Reiter aufbauen, dann tauschen; `blockSignals` in `try/finally`;
  `deleteLater`.
- `_titel_aktualisieren()` mit Rückfall auf den Dateinamen.
- `main` mit `try` und „Programm wird beendet“.
- Optional CHECK bei `ADD COLUMN gegenstand_N_disziplin`.
- Aus der Verifikation von A2: Ungültige `stufe`/`disziplin`-Werte lassen mehrere PDF-Exporte mit
  `KeyError` abbrechen (`_SUCHGEGENSTAENDE_TEXT`, `_VERLEITUNGEN`, `_ZEITPLAN_FARBE_JE_LK`). Die
  Plausibilitätsprüfung beim Öffnen deckt das ab; prüfen, ob sie wirklich alle Exportwege abdeckt.
- Aus der Sicherheitsprüfung von A3: Beim Öffnen einer fremden Datei (`init_db`) können berechnete
  Spalten (`GENERATED ALWAYS AS`) teure Ausdrücke enthalten. `db.pruefe_termin_aufbau`
  wiederverwenden, für alle Tabellen; berechnete Spalten sollen nicht übernommen werden.

**A9 Fehlerprotokoll und Klartext für Dateien** (M): T9-4, T9-5, T9-6, T9-8, T9-10, T10-6, T5-4, CSV-Export und
Sicherungs-ZIP (`PermissionError`).
- `fehler_protokollieren(exc)`.
- `_klartext_fehler` aus A4 um `PermissionError`, `FileNotFoundError` und `ENOSPC` erweitern.
- `_pdf_export_fehler_anzeigen` unterscheidet `OSError` von Programmfehlern.
- Protokoll beim Start rotieren, Wiederholungen zählen.
- `qInstallMessageHandler` ab Warnungen.
- `openUrl` bei `False` mit Meldung.
- Demo-Fehler protokollieren.
- Aus der Verifikation von A3:
  - `app.py` `_aus_anderem_termin_importieren` meldet Lesefehler der Quelle über
    `_db_fehler_anzeigen` mit „Die Änderung konnte nicht gespeichert werden“; nötig ist eine
    passende Formulierung.
  - Der Hinweis im TerminImportDialog zeigt die rohe Ausnahme; sie soll über
    `_klartext_fehler` laufen.
- Offen, keine Regression, nur zur Kenntnis:
  - Eine fremde Datei im WAL-Modus hinterlässt beim lesenden Öffnen `-wal`/`-shm`.
  - Eine Datei mit liegengebliebenem Journal gilt im Import-Dialog als nicht lesbar.

**A10 Rückfrage bei ungespeicherten Änderungen** (S): T8-2, T10-8, T8-10, T8-8 (`closeEvent`-Docstring).
- Gemeinsame Hilfsfunktion Save/Discard/Cancel für Reiterwechsel, Terminwechsel und Demo-Start.
- `closeEvent` speichert bei freigegebenem Beenden still.

**A11 Startdialog und Datensicherung** (M): T7-1, T7-2, T7-5 (mit T1-3), T7-8, T7-10, T7-11, T7-12, T7-7.
- Aus der Verifikation von A9: „Sicherung auswählen“ (`sicherung_inhalt`) fängt kein `OSError`; Meldung über `_klartext_fehler`.
- Rückfrage zum Mitsichern, Pfadvergleich beim Wiederherstellen.
- Passwortschleife korrigieren.
- Löschen: Vorgabe „Nein“, Papierkorb, Auswahl danach leeren. Handbuch anpassen.
- Enter öffnet den markierten Termin.
- Ungültige Zeichen in `_ist_sicherer_dateiname` ablehnen.
- Meldungsfenster nach dem Wiederherstellen.
- Leeres Passwort, `OSError` bzw. `NotImplementedError`, Anzeige `verein or dateiname`.
- Veraltete Verweise, Tests.

**A12 Teilnehmerliste** (S): T1-3, T1-4 mit T5-5, T1-5, T1-6, T1-8.
- „Löschen“ mit Vorgabe „Nein“.
- `_import_ergebnis_melden`: Namen auf 15 kürzen, vollständige Liste über `setDetailedText`, für CSV,
  OMA, PDF und Startnummern.
- Dateinamen des Bewertungsbogens bereinigen.
- Hinweis nach dem Termin-Import auf nicht angebotene Prüfungen, `Architektur.md` anpassen.
- `_teilnehmer_ids` entfernen, `next` durch `get_teilnehmer` ersetzen.
- Aus A4: Nach einem abgebrochenen Import nennt die Meldung nicht die Zahl der schon
  übernommenen Teilnehmer. Möglich wäre, im Import-Ergebnis mitzuzählen oder die Anzahl vorher
  und nachher zu vergleichen.

**A13 Teilnehmer- und Veranstaltungsdialog** (M): T2-2, T2-3, T2-6, T2-7, T2-4, T2-8a, T2-10, T2-11, T2-12,
T2-13, T2-14, T2-15.
- Speicherort prüfen (absolut, Ordner vorhanden, Endung `.sqlite`, noch nicht vorhanden,
  `DontConfirmOverwrite`).
- Startnummer-Zwischeneingabe.
- Fokus und Höhenbegrenzung über eine gemeinsame Hilfsfunktion.
- Leere DK-Zuordnung, Gebühr-Standard nur bei neuen Terminen.
- Gemeinsame Hilfsfunktion für den Dateinamen.
- `_aktualisiere_veranstaltung_feld` als gezieltes UPDATE mit Vollständigkeitstest.
- Rückfrage bei Datum in der Zukunft und bei nicht angebotener Prüfung.
- Texte; Tests patchen `termine_ordner`.

**A14 Auswertung und Zeitplan** (S): T4-2, T4-3, T4-6, T4-8, T4-9 (Rest); T4-1 nur dokumentieren.
- Stechen-Auswahl mit Hund und Start-Nr., Vorgabe „noch offen“.
- Zeitplan-Start über `editingFinished`/`returnPressed`, Abgleich vor PDF und Verteilung.
- Uhrzeit vereinheitlichen.
- Doppelte Berechnungen entfernen.
- Optionale Handler-Tests.

**A15 Update-Prüfung, Selbsttest und Zweitstart** (M): T8-1, T8-4, T8-5, T8-6, T8-7, T8-8 (Rest), T8-9.
- `HTTPException` und `dict`-Prüfung, Knopf über `finally` freigeben.
- Neutrale Meldung bei nicht lesbarer Version.
- Abfrage im Hintergrund-Thread mit Gesamtzeitgrenze, SSL-Fehler eigens melden, Selbsttest-Schritt
  CA-Speicher.
- `QLockFile` mit Rückfrage.
- `faulthandler`-Zeitgrenze, `timeout-minutes` im Windows-Job.
- Kommentare, Tests.
- Die Prüfung am echten Mac (CA-Zertifikate) lässt sich nicht automatisieren und wird als Punkt für
  den Mac-Rückmeldungstest notiert.

**A16 PDF-Export: Schrift und Rest** (M): T6-2, T6-6, T6-9, T6-11, T6-12.
- DejaVu Sans (Normal, Fett) unter `fonts/` mit Lizenz.
- Registrierung in `pdf_export`, `stringWidth` und `_AnmeldeformularZeichner` angepasst.
- `build.spec` ergänzen.
- Test mit „Paweł“.
- OK nur bei mindestens einem Haken.
- `explorer /select,"…"`.
- Gemeinsamer Exportablauf in `desktop_gemeinsam`.
- Veraltete Texte, Tests.

### Optional

**A17 Liegengebliebene Dialoge und Wartecursor** (S): T2-9, T6-8, T7-Dialoge (Passwortfeld leeren), T8 `VersionDialog`,
`HilfeDialog` und Boxen, T6-7 (auch Sicherung und Wiederherstellung).
- `deleteLater()` nach `exec()`.
- `setOverrideCursor` mit `try/finally`.

**A18 Import-Rest** (S): T5-7, T5-8, T5-9.
- Dublette vor Angebot beim PDF-Import.
- KI-Prompt überarbeiten.
- `NichtAngebotenError`, Docstrings.

**A19b Befunde der Abschluss-QS Korrektheit** (S) – vor A19 fortsetzen:
- **K-1 (mittel):** Startzeit tippen, dann direkt „Pause hinzufügen…“: `_nach_mausklick_aktualisieren`
  (app.py ~3316) baut die Spalten im modalen PauseDialog neu auf, danach `liste.currentItem()` auf
  gelöschte QListWidget (app.py ~3269) → Fehlerfenster, Pause fehlt. Lösung: in
  `_pause_hinzufuegen` die markierte Zeile vor `_ausfuehren(dialog)` lesen (eintrag_id) und
  `_nach_mausklick_aktualisieren` zusätzlich warten lassen, solange
  `QApplication.activeModalWidget()` gesetzt ist; ebenso andere Spalten-Aktionen mit Dialog
  prüfen; GUI-Test genau dieses Ablaufs.
- **K-2 (niedrig):** `importiere_teilnehmer_stammdaten` (db_import.py ~833) übernimmt BLOB-Werte
  aus der Quelle (TEXT-Affinität wandelt nicht) → eigener Termin danach nicht mehr öffenbar
  (`_termin_werte_pruefen`). Lösung: Textfelder bytes → `decode("utf-8", "replace")`, andere
  Nicht-Texte → `str()`; Test mit `UPDATE teilnehmer SET vorname = X'C3A46263'` in der Quelle.
- **K-3 (niedrig):** `termin_oeffnen` (db.py ~2615) legt eine fehlende Datei still neu an. Lösung:
  `TerminNichtOeffenbar("Die Datei wurde nicht gefunden …")`, wenn sie nicht existiert;
  `test_normaler_und_neuer_termin_oeffnen` anpassen (neu anlegen macht `_termin_datei_anlegen`).
- **Stechen (optional):** `zuordnung[eintraege.index(auswahl)]` (app.py ~2469) bei gleichlautenden
  Einträgen (gleicher Name/Hund, ohne Start-Nr.) – doppelte Texte eindeutig machen (z. B. „ (2)“),
  Kommentar korrigieren.
- Danach: Verifikation, Fortschritt.md, Commit; dann A19 mit `qs-wartbarkeit` fortsetzen.

**A19 Abschluss** (M):
- QS-Gesamtprüfung aller Aufgaben-Commits mit `qs-sicherheit`, `qs-korrektheit` und `qs-wartbarkeit`
  nacheinander, danach Gegenprüfung. Neue Befunde kommen als Aufgaben vor A19 in die Liste.
- `Architektur.md` und `README*.md` abgleichen.
- `uebersicht.md` abschließen.
- Abschlussbericht für Marco:
  - Commits;
  - zurückgestellte Punkte und Rückfragen;
  - Screenshots, die vor dem nächsten Build neu aufgenommen werden müssen (A1, A7, A11, A16);
  - Hinweis: Sicherheitsberichte bleiben bis zum Release in `_unveroeffentlicht/`.

## Grenzen

- Kein Push, Tag, Versionsbump, Build oder `HANDBUCH.pdf`. Screenshots werden erst vor dem Build
  erneuert, nach der Checkliste `shs-build`.
- Sicherheitsdetails stehen nur in `_unveroeffentlicht/`.
- Bereits abgelehnte bzw. akzeptierte Punkte bleiben unberührt:
  - Duplikatsperre im Fehlerfenster;
  - „Nein“ verwirft beim Terminwechsel;
  - Demo umgeht modale Rückfragen;
  - URLs in der Hilfe;
  - Web-Login-Limits.

## Verifikation (gesamt)

- Je Aufgabe:
  - laufen die lokale Unittest-Suite und die GUI-/Theme-Tests mit Anaconda-Python grün;
  - meldet der `verifikation`-Agent nichts mehr (Sicherheitsaufgaben zusätzlich `qs-sicherheit`).
- Am Ende: kompletter Testlauf und die QS-Gesamtprüfung in A19.
- CI-only-Tests (PostgreSQL) laufen erst bei Marcos Push.
