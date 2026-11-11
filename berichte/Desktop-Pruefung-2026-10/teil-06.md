# Desktop-Prüfung Teil 6: Export und PDF

> **Enthält einen Sicherheitsbefund (Nr. 1).** Nach CLAUDE.md erst nach dem Release mit dem Fix
> veröffentlichen. In `Fortschritt.md`, Commits und Code-Kommentaren bis dahin nur allgemein
> beschreiben (z. B. „Sicherheitskorrektur, Details folgen“), ohne Stelle oder Angriffsweg.

- **Datum:** 14.10.2026
- **Commit:** 0d65aff (Version 1.0.47; Programmcode seit 25f9572 unverändert)
- **Geprüft:**
  - `app.py`: `ExportTab` (Z. 3090–3375);
  - `desktop_dialoge.py`: `BewertungsbogenAuswahlDialog` (Z. 875–930);
  - `desktop_gemeinsam.py`: `_Ablageort`, `_export_dateiname`, `_ausdrucke_ordner`,
    `_pfad_anzeige`, `_ordner_zeigen`, `_pdf_speicherort_waehlen`, `_datei_gespeichert_melden`,
    `_pdf_export_fehler_anzeigen` (Z. 74–204);
  - `pdf_export.py` vollständig aus Sicht der Desktopaufrufe;
  - `db_import.py`: `exportiere_teilnehmer_csv`, `_csv_zelle_absichern`, `_csv_wert`;
  - aufgerufene `db.py`-Hilfen (`datum_anzeige`, `lies_datum`, `pruefungsgebuehr_fuer_art`,
    `leistungsklasse_label`, `alle_leistungsklassen`, `list_teilnehmer`).
- **Ablauf:**
  - `desktop-pruefer` im Prüfmodus, danach Gegenprüfung durch einen zweiten `desktop-pruefer`.
  - Beide haben mit eigenen Skripten nachgestellt (reportlab 5.0.1, pypdf, PySide6 offscreen)
    und die Excel-Fälle mit dem lokalen Excel 16 über COM geprüft. Kein Netzwerkziel verwendet.
  - Tests grün: `test_pdf_export` 72 OK; GUI-Teilmenge Export/PDF/CSV 17 passed.
- **Ergebnis:**
  - 12 Befunde gemeldet, 10 bestätigt, 2 teilweise (Nr. 8; Einordnung Excel-Weg). Kein
    Schweregrad geändert.
  - **1 Sicherheitsbefund (Nr. 1, mittel):** unvollständiger Rest von S-4. Teil 2 Nr. 8b geht
    darin auf.

| Schweregrad | Anzahl | Befunde |
|---|---|---|
| mittel | 1 | 1 (Sicherheit) |
| niedrig | 4 | 2, 3, 4, 5 |
| optional | 7 | 6, 7, 8, 9, 10, 11, 12 |

**Stand mit Marco:** alle Befunde noch unbesprochen.

## Bestätigte Befunde

### Nr. 1 [mittel, Sicherheit] Der Fix von S-4 ist unvollständig: weitere Nutzertexte gehen ohne `_p_wert` in `Paragraph`

- **Stelle (`pdf_export.py`):**
  - 638, 878, 1182, 1268, 1325, 1499, 1508: `_datum_kurz(veranstaltung['datum'])` in 7 Titeln
    (Bögen und Etiketten maskieren das Datum, 507/779);
  - 1217: Prüfungsgebühr (= Teil 2 Nr. 8b);
  - 1219: Impfdatum (`tollwutimpfung_bis`);
  - 480: `zusatz` mit `gegenstand_N_disziplin` im DK-Bogen;
  - 649, 896, 1216: `leistungsklasse_label` als Paragraph;
  - **1451 (Gegenprüfung):** `art_text` mit `zeitplan_eintrag.disziplin`.
- **Kategorie:** Sicherheit, Testlücke.
- **Voraussetzung:** `datum_anzeige()` gibt nicht lesbare Werte unverändert zurück
  (`db.py:1182–1190`, „Altbestand“). Gebühr, Datum und Impfdatum haben keinen CHECK. Laut
  Gegenprüfung kann jede fremde Datei CHECKs beim Schreiben umgehen
  (`PRAGMA ignore_check_constraints` oder eigene Tabelle ohne CHECK); `init_db` prüft das Schema
  nicht (`CREATE TABLE IF NOT EXISTS`). In migrierten Dateien fehlt der CHECK für
  `gegenstand_N_disziplin` ohnehin (`db.py:483`). Weg: ein fremder Termin über „Andere
  Termin-Datei öffnen“ oder eine fremde Sicherung.
- **Nachgestellt (gültiges PNG, eingebettete Bilder per pypdf gezählt):**

| Feld | Ergebnis |
|---|---|
| `veranstaltung.datum` | je 1 Bild in Ergebnisliste, leerer Ergebnisliste, Übersicht, Chipliste, Richter-Bedarf, Zeitplan |
| Gebühr, `tollwutimpfung_bis` | je 1 Bild in der Übersicht |
| `gegenstand_1_disziplin` | 1 Bild im DK-Einzelbogen und in der Sammel-PDF |
| `disziplin` über `leistungsklasse_label` | Bild in leerer Ergebnisliste und Übersicht; andere Exporte brechen vorher mit `KeyError` ab |
| `zeitplan_eintrag.disziplin` (1451) | 1 Bild im Zeitplan-PDF |

  - HTTP blockt reportlab (`trustedHosts=None`). Pfade lädt `open_for_read_by_name` aber mit
    einfachem `open()`; ein UNC-Pfad würde sehr wahrscheinlich eine SMB-Verbindung auslösen (nicht
    getestet, bewusst kein Netzwerkziel).
  - Kaputtes Markup (z. B. `12,00 <b`) bricht den Export ab (Teil 2 Nr. 8b).
  - Über die eigene Oberfläche ist nur die Gebühr erreichbar; Datum und Impfdatum laufen im Dialog
    über `normalisiere_datum`.
- **Ist:** `Architektur.md:142` sagt „In PDFs geht jeder Nutzertext über `_p_wert`“; der Fix vom
  03.10. hat nur Verein und Richter maskiert. Der Test
  `test_alle_pdfs_maskieren_markup_in_allen_feldern` (`test_pdf_export.py:217`) setzt `datum`
  gültig und deckt Gebühr, Impfdatum und Zuordnung nicht ab. Sein Test-PNG ist ungültig („broken
  data stream“); der Test bleibt laut Gegenprüfung wirksam, weil ein nicht maskiertes Feld mit
  `OSError` abbricht, die eigentliche Bild-Prüfung greift aber nie.
- **Soll:** Jeder variable Wert in einem `Paragraph` ist maskiert.
- **Vorschlag:**
  - `_p_wert` für Datum, Gebühr, Impfdatum, Zuordnung, LK-Label und Zeile 1451. Am einfachsten:
    `_datum_kurz` liefert schon maskiert, Escaping in `_euro_text`.
  - Die heute durch `KeyError` verdeckten Pfade `stufe` (434/459/465) und `t['disziplin']` (466)
    mitprüfen.
  - S-4-Test erweitern um `pruefungsgebuehr_ed`/`_dk`, `datum`, `tollwutimpfung_bis`,
    `gegenstand_N_disziplin`, Zeitplan-Disziplin (per `PRAGMA ignore_check_constraints` bzw.
    direktem UPDATE), mit gültigem PNG.
  - `reportlab.rl_config.trustedSchemes = []` ändert laut Gegenprüfung am `open()`-Weg nichts;
    das Maskieren ist der eigentliche Schutz.
  - `Architektur.md:142` danach stimmt wieder.
- **Gegenprüfung:** bestätigt, mittel (gleiches Bedrohungsmodell wie S-4). Stelle 1451 ergänzt,
  Einschränkung auf migrierte Dateien zu eng.

### Nr. 2 [niedrig] Zeichen außerhalb von Windows-1252 erscheinen in allen PDFs als „■“

- **Stelle:** `pdf_export.py`; alle Stile nutzen Helvetica, auch das Anmeldeformular
  (`drawString`). Keine TTF registriert.
- **Kategorie:** Korrektheit.
- **Nachgestellt:** Verein „Klub Łódź“, Teilnehmer „Dvořák, Paweł“ ergeben in Chipliste, leerer
  Ergebnisliste und Bögen `Klub ■ód■`, `Dvo■ák, Pawe■`; das Anmeldeformular zeigt im Kopf
  ebenfalls `■`. Betroffen sind übliche polnische, tschechische, türkische und ungarische
  Buchstaben (ł ż ś ř č ğ ş ı ő ű); „Žofie“ bleibt richtig (in Windows-1252). Keine frühere
  Entscheidung in Fortschritt.md.
- **Vorschlag:** Unicode-TTF registrieren (z. B. DejaVu Sans, freie Lizenz) und mitliefern:
  `build.spec`, `_STYLES`, Tabellen-`FONTNAME`s, `_AnmeldeformularZeichner`,
  `stringWidth`-Berechnungen. Notlösung: NFD ohne diakritische Zeichen. Test mit „Paweł“.
- **Gegenprüfung:** bestätigt, niedrig.

### Nr. 3 [niedrig] Der CSV-Formelschutz lässt „+“/„-“-Telefonnummern ohne Leerzeichen durch, Excel rechnet sie aus

- **Stelle:** `db_import.py:760`, `773` (`_ZAHL_ODER_TELEFON`); Weg: „In Excel öffnen“
  (`app.py:3289`).
- **Kategorie:** Datenintegrität.
- **Mit Excel 16 nachgestellt:**

| Wert | Excel zeigt |
|---|---|
| `+43-1-5551234` | `-5551192` (Formel `=43-1-5551234`) |
| `+49/170/1234567` | `2,3347E-07` |
| `+49-170-1234567` | nach Speichern `-1234688` |
| `-1-1` | `-2` |
| `+491701234567` (Gegenprüfung) | `4,917E+11`, „+“ geht verloren |
| `+49 170 1234567` | bleibt Text (durch vorhandenen Test abgedeckt) |

- **Ist:** Die Ausnahme soll Telefonnummern erhalten, bewirkt für Schreibweisen ohne Leerzeichen
  das Gegenteil. Die „verlustfreie Rundreise“ (Fortschritt.md Z. 3857f.) gilt nur ohne Excel.
- **Vorschlag:** Bei `+`/`-` nur unverändert lassen, wenn der Wert ein Leerzeichen enthält oder
  genau „-“ ist, sonst „'“ voranstellen (der Import entfernt es). Excel zeigt das „'“ dann
  sichtbar (`'+43…`), derselbe Kompromiss wie bei „'=“; bewusst entscheiden. Sicherheitlich
  unkritisch (ohne Buchstaben keine Funktionen). Testfälle `+43-1-5551234`, `+49/170/1234567`.
- **Gegenprüfung:** bestätigt, niedrig.

### Nr. 4 [niedrig] Lange Namen ragen in Ergebnisliste und leerer Ergebnisliste in die Nachbarspalte

- **Stelle:** `pdf_export.py:662` (`t.name` als reiner String, Spalte 46 mm), `911` (Name in der
  leeren Liste).
- **Kategorie:** Korrektheit (Darstellung).
- **Ablauf:** Reine String-Zellen bricht reportlab nicht um (Kommentar Z. 899–901). Verfügbar
  sind 118,4 pt; „Schmidt-Hohenstein, Anna-Katharina“ braucht 148,6 pt,
  „Müller-Lüdenscheidt, Hans-Jürgen“ 137,5 pt. Für den Verein gibt es seit 21.09. eine
  Verkleinerung (898–916), für den Namen nicht.
- **Vorschlag:** Namen als `Paragraph(_p_wert(...))` oder Verkleinerung übernehmen. Test mit
  Doppelnamen.
- **Gegenprüfung:** bestätigt, niedrig.

### Nr. 5 [niedrig] Die Übersicht für die Prüfungsleitung sortiert nach Codepunkt

- **Stelle:** `pdf_export.py:1176` (`sorted(..., key=(nachname, vorname))`).
- **Kategorie:** Korrektheit.
- **Nachgestellt:** `Adler, Bauer, Zorn, von Berg, Ärmel, Özdemir`. Die Liste dient am
  Prüfungstag zum Nachschlagen (bezahlt, Impfpass).
- **Bezug:** gleiche Ursache wie Teil 3 Nr. 4, andere Stelle; zusammen umsetzen.
- **Vorschlag:** gemeinsamer, Qt-freier Sortierschlüssel in `db.py` (NFD ohne
  Kombinationszeichen plus `casefold`), hier und im ErgebnisTab. Test mit Umlauten und
  kleingeschriebenem Namenszusatz.
- **Gegenprüfung:** bestätigt, niedrig.

### Nr. 6 [optional] Bewertungsbogen-Auswahl: „Keine auswählen“ plus OK erzeugt ein leeres PDF

- **Stelle:** `desktop_dialoge.py:905–909`, `pdf_export.py:603–617`, `app.py:3369–3375`.
- **Nachgestellt:** OK bleibt aktiv; danach Speichern-Dialog, PDF mit „Keine Teilnehmer
  erfasst.“, Meldung „0 Bewertungsbögen gespeichert“. Sind alle auf „keine Teilnahme“, sagt der
  Dialog „Keine Teilnehmer erfasst.“. Der Docstring 599–601 klingt, als bedeute ein leeres Set
  „alle“, der Code behandelt es als „keine“; Verweis auf `app.py` veraltet.
- **Vorschlag:** OK über `itemChanged` nur bei mindestens einem Haken freigeben. Test.
- **Gegenprüfung:** bestätigt, optional.

### Nr. 7 [optional] Lange Exporte blockieren die Oberfläche ohne Wartecursor

- **Stelle:** `app.py:3263–3267`, `desktop_gemeinsam.py:198–199`.
- **Gemessen:** 200 Teilnehmer als Sammelbögen 2,1–2,2 s; nirgends `setOverrideCursor`.
- **Vorschlag:** `QApplication.setOverrideCursor(Qt.WaitCursor)` mit `try/finally` im
  gemeinsamen Exportablauf.
- **Gegenprüfung:** bestätigt, optional.

### Nr. 8 [optional, teilweise] Auswahldialog bleibt als verstecktes Kind liegen

- **Stelle:** `app.py:3366` (`BewertungsbogenAuswahlDialog(self, …)`); Lambdas mit `self`
  (`desktop_dialoge.py:897/899`).
- **Nachgestellt:** Nach 3 Aufrufen 3 Dialoge als Kinder von `ExportTab`, auch nach
  `gc.collect()`; bleiben bis zum Terminwechsel.
- **Verworfen (Gegenprüfung):** der Teil zu `QMessageBox(parent)` in `desktop_gemeinsam.py:121`;
  offscreen bleibt kein Kind zurück.
- **Vorschlag:** Nach `exec()` `deleteLater()`; zusammen mit Teil 2 Nr. 9 umsetzen.

### Nr. 9 [optional] „Ordner zeigen“ markiert die Datei bei Pfaden mit Komma nicht

- **Stelle:** `desktop_gemeinsam.py:113`.
- **Ablauf:** `list2cmdline` quotet nur bei Leerzeichen; `…\Liste,final.pdf` ohne Leerzeichen im
  Pfad ergibt `explorer /select, C:\…\Liste,final.pdf`, Explorer trennt am Komma. Nur aus der
  Befehlszeile abgeleitet (Explorer nicht gestartet); Standardpfade enthalten kein Komma.
- **Vorschlag:** `subprocess.Popen(f'explorer /select,"{_pfad_anzeige(pfad)}"')`.
- **Gegenprüfung:** bestätigt, optional.

### Nr. 10 [optional] Formelschutz: Export und Import bei absurden Werten nicht symmetrisch

- **Stelle:** `db_import.py:766–770` gegen `135–143` (aus Teil 5 vorgemerkt).
- **Nachgestellt (Rundreise):** `"' =x"` → `"=x"`, `"''=x"` → `"'=x"`, `"' '=x"` → `"'=x"`;
  `"'=x"` und `"'\t=x"` korrekt. Keine Sicherheitsfolge, der nächste Export schützt wieder.
- **Vorschlag:** In `_csv_zelle_absichern` dieselbe Prüfung wie beim Import; Rundreisetest.
- **Gegenprüfung:** bestätigt, optional.

### Nr. 11 [optional] Wartbarkeit: Doppelungen und veraltete Texte

- Vier fast gleiche Exportabläufe: `ExportTab._pdf_export_ausfuehren` (`app.py:3253`),
  `AuswertungTab._rangliste_drucken` (2272), `TeilnehmerTab._bewertungsbogen_exportieren` (829),
  `_zeitplan_pdf_exportieren`. Vorschlag: als Funktion nach `desktop_gemeinsam`.
- `_teilnehmerliste_exportieren` (`app.py:3274–3287`): eigener `makedirs`-/Dialog-Block, setzt den
  Ablageort erst nach Erfolg (anders als `desktop_gemeinsam.py:168`), `.replace(".pdf", ".csv")`.
  Vorschlag: Parameter für Endung und Filter.
- Veraltet: `app.py:3097–3102` („Ordner der Termin-Datei“, tatsächlich `Ausdrucke/<Termin>`;
  Rückfallwert 3104 weicht von 4143 ab); `_Ablageort`-Docstring (`desktop_gemeinsam.py:75–81`)
  und Kommentar 4138 ohne Teilnehmer-Reiter; `pdf_export.py:599` verweist auf `app.py`.
- `_ablageort_oeffnen` (`app.py:3245`) zeigt den Pfad ohne `_pfad_anzeige`.
- „In Excel öffnen“ öffnet nur das Standardprogramm für CSV (Mac-/Linux-Vorschau, LibreOffice).
- **Gegenprüfung:** alle Teilpunkte bestätigt, optional.

### Nr. 12 [optional] Testlücken

- Kein Test für `erstelle_alle_bewertungsboegen_pdf(erlaubte_labels=…)`, `_alle_umschalten`,
  `_ablageort_oeffnen`, die Fehlerzweige in ExportTab und CSV-Export.
- Die echte `_datei_gespeichert_melden` läuft in keinem Test (autouse-Fixture
  `test_app_gui.py:83–95`). Die Dialogtests (2928/2939) prüfen nur Vorbelegung und gesperrtes OK.
- Tests zu Nr. 1–6 und 10 fehlen.
- **Gegenprüfung:** bestätigt, optional.

## Vorgemerkte Punkte: Einordnung

- **Gebühr ohne `_p_wert` (Teil 2 Nr. 8b):** bestätigt, geht in Nr. 1 auf.
- **CSV-Export und „In Excel öffnen“ als zweiter Weg zu Teil 5 Nr. 1:** bestätigt, nicht neu
  gezählt. Excel-Nachweis: Chip-Nr. `2,76098E+14`, PLZ `01067` → `1067`, Mitgl.-Nr. `00123` →
  `123`, `+491701234567` → `4,917E+11`.
  - Ein vorangestelltes „'“ hilft nicht (Excel zeigt es sichtbar). `="276098765432101"` zeigt
    Excel korrekt als Text (Gegenprüfung), ist aber technisch eine Formel, widerspricht dem
    Formelschutz und müsste beim Import zurückgewandelt werden.
  - Machbar: a) Hinweis in der Meldung nach dem CSV-Export (Parameter `hinweis` in
    `_datei_gespeichert_melden`, `setInformativeText`): „Excel kürzt beim Speichern lange Nummern
    (Chip-Nr.) und entfernt führende Nullen (PLZ, Telefon). Zum Bearbeiten über Daten → Aus
    Text/CSV laden und diese Spalten als Text festlegen.“; b) derselbe Satz im Handbuch Kap. 9
    neben Kap. 5; c) größer: `.xlsx`-Export mit Textspalten (openpyxl).
- **Asymmetrie „' =x“:** bestätigt, Nr. 10.

## Ohne Befund geprüft (laut Prüfer)

Statuszeile und Meldungen als Klartext (S-1); Anmeldeformular (Hinweis ohne angebotene Prüfungen
vor dem Dialog, Canvas-Text ohne Markup, Meldestelle gekürzt); reportlab schreibt erst beim
`save`, abgebrochener Export lässt vorhandene Datei unverändert; Abbruch des Speichern-Dialogs;
`nur_teilnehmende` einheitlich; Übersicht zeigt „keine Teilnahme“ bewusst; Sortierung von
Chipliste und Etiketten ohne Startnummer; Statistik und Zeitplan maskieren (außer Nr. 1, Z. 1451);
CSV-Export UTF-8 mit BOM, Semikolon, Quoting; Signale je einmal verbunden.

## Hinweise für spätere Teile

- **Teil 7:** Fremde Termin-Dateien bzw. Sicherungen sind der Weg zu Nr. 1. `init_db` prüft weder
  CHECK-Constraints noch das Schema; migrierte Dateien haben für `gegenstand_N_disziplin` keinen
  CHECK (`db.py:483`).
- **Teil 9:** `_teilnehmerliste_exportieren` (`app.py:3284–3286`) meldet `PermissionError` ohne
  Hinweis „in Excel geöffnet“, gerade nach „In Excel öffnen“ und erneutem Export wahrscheinlich.
