# Desktop-Prüfung Teil 5: Import

- **Datum:** 14.10.2026
- **Commit:** 87ea7e2 (Version 1.0.47; Programmcode seit 25f9572 unverändert)
- **Geprüft:**
  - `app.py`: `_formular_import_prompt`, `FormularImportTab`, dazu
    `_startnummern_nach_import_anbieten`, `_teilnehmerliste_importieren`;
  - `desktop_gemeinsam.py`: `_import_startordner`, `_import_ordner_merken`;
  - `db_import.py` vollständig, die dabei aufgerufenen Funktionen in `db.py`;
  - `desktop_dialoge.TerminImportDialog` nur für den aus Teil 4 vorgemerkten Punkt.
- **Ablauf:**
  - `desktop-pruefer` im Prüfmodus, danach Gegenprüfung durch einen zweiten `desktop-pruefer`.
  - Beide haben mit eigenen Skripten nachgestellt; die Gegenprüfung hat die Excel-Fragen mit dem
    lokal installierten Excel (über COM) belegt.
  - Tests grün: `TestCsvMeldungen` und `TestAnmeldeformularImport` 17 OK; `test_db -k
    csv/oma/vorlage` 68 OK (34 übersprungen, PostgreSQL); GUI-Teilmenge Import 14 passed.
- **Ergebnis:**
  - 10 Befunde gemeldet. 9 bestätigt (Nr. 4 und 10 nur teilweise), Nr. 5 geht in Teil 1 Nr. 4
    auf. Kein Sicherheitsbefund.
  - Nr. 4 von niedrig auf optional herabgestuft: Der Kern (in Excel geöffnete CSV lässt sich
    nicht lesen) ist widerlegt.

| Schweregrad | Anzahl | Befunde |
|---|---|---|
| mittel | 1 | 1 |
| niedrig | 2 | 2, 3 |
| optional | 6 | 4, 6, 7, 8, 9, 10 |

Nr. 5 ist nicht mitgezählt, sondern als Ergänzung zu Teil 1 Nr. 4 geführt.

**Stand mit Marco:** alle Befunde noch unbesprochen.

## Bestätigte Befunde

### Nr. 1 [mittel] Von Excel zerstörte Chip-, Telefon- und Postleitzahlen übernimmt der Import ohne Warnung

- **Stelle:** `db_import.py:135–143` (`_csv_wert`) und `210`/`212`/`214` (`chip_nr`,
  `mitgliedsnummer`, `plz` ungeprüft übernommen). Weg dorthin: Export `db_import.py:781–798`,
  „In Excel öffnen“ `app.py:3289`, `docs/HANDBUCH.md:442–459` (Vorlage → Excel → CSV; „Eine
  gespeicherte Liste lässt sich ebenso wieder einlesen“). Folge: Chipliste
  (`pdf_export.py:1282`) und Bewertungsbogen.
- **Kategorie:** Datenintegrität.
- **Ablauf (mit echtem Excel nachgestellt):** Vorlage in Excel öffnen, Werte wie beim Tippen
  eintragen, als „CSV (Trennzeichen-getrennt)“ speichern. Datei enthält
  `Meyer;Mia;Rex;DK;1;;2,76098E+14;1067;1701234567`. Der Import meldet „1 importiert,
  0 Fehler“; in der Datenbank stehen `2,76098E+14` und `1067`.
- **Ergänzung (Gegenprüfung):** Auch `telefon` verliert die führende 0
  (`01701234567` → `1701234567`), das trifft fast jede deutsche Telefonnummer ohne Leerzeichen.
- **Soll:** Ein offensichtlich von Excel verstümmelter Wert fällt beim Import auf.
- **Vorschlag:**
  - Werte nach dem Muster `^\d+([.,]\d+)?[eE][+-]?\d+$` in `chip_nr`, `plz`, `mitgliedsnummer`,
    `telefon` und den `halter_*`-Nummern erkennen. Laut Gegenprüfung besser nicht ablehnen,
    sondern mit Hinweis je Zeile übernehmen, z. B. „Chip-Nr. „2,76E+14“ wurde von Excel gekürzt –
    Spalte in Excel als Text formatieren und neu eintragen“.
  - PLZ nicht automatisch mit Nullen auffüllen (AT/CH haben 4 Stellen).
  - Billigster Teil: Satz im Handbuch Kap. 5, Spalten `chip_nr`, `plz`, `telefon`,
    `mitgliedsnummer` vor dem Ausfüllen als „Text“ formatieren.
  - Test in `test_db.py`.
- **Gegenprüfung:** bestätigt, mittel. Tritt bei jeder Chipnummer auf dem vom Handbuch
  empfohlenen Weg auf; die Ziffern sind unwiederbringlich verloren.

### Nr. 2 [niedrig] Der CSV-Import prüft die Kopfzeile nicht

- **Stelle:** `db_import.py:261–264` und `282–296`; zum Vergleich hat OMA eine
  Pflichtspaltenprüfung (`409–418`).
- **Kategorie:** Korrektheit, Fehlerbehandlung.
- **Ablauf (alle vier Fälle nachgestellt):**
  - a) OMA-Export (Endung `.csv`, der Dateifilter lässt ihn zu) versehentlich über
    „Teilnehmerliste einlesen“. Die Metazeile mit Kommas wird zur Kopfzeile, Komma als Trenner.
  - b) Eigene Liste mit Überschriften `Nachname;Vorname;…`.
  - c) Kopf mit „, “ (Leerzeichen nach dem Komma): Nur `nachname` passt, Meldung „Zeile 2
    (Meyer): …“.
  - d) UTF-16 aus Excel „Unicode-Text“: als cp1252 mit Ersatzzeichen gelesen.
- **Ist:** Jede Zeile meldet „Zeile N: Nachname/Vorname/Rufname des Hundes fehlt“; nirgends
  steht, dass die Spaltennamen nicht passen. Bei großen Dateien kommt Teil 1 Nr. 4 dazu.
- **Soll:** Klarer Abbruch wie bei OMA: „Die Datei hat nicht die erwarteten Spalten (fehlend: …;
  gefunden: …). Leere Vorlage verwenden“; bei OMA-Spalten Verweis auf den OMA-Knopf.
- **Vorschlag:** `reader.fieldnames` nach dem Anlegen prüfen, per `strip()`/`casefold()`
  vergleichen; Pflicht `nachname`, `vorname`, `rufname_hund`, `art`, `stufe`. Tests für a) bis c).
- **Gegenprüfung:** bestätigt, niedrig.

### Nr. 3 [niedrig] Leere Excel-Zeilen (`;;;;;`) erscheinen als Fehlerzeilen

- **Stelle:** `db_import.py:263–296`; `csv.DictReader` überspringt nur echte Leerzeilen.
- **Kategorie:** Korrektheit.
- **Ablauf (mit echtem Excel belegt):** Eine nur formatierte (eingefärbte) Zeile führt beim
  CSV-Speichern zu Zeilen `;;;;;`.
- **Ist:** 1 gültige plus 2 leere Zeilen ergeben „1 importiert, 2 Fehler (Zeile 3, Zeile 4)“.
  Nur Kopf plus `;;;;;` ergibt einen Fehler statt des Hinweises „Die Datei enthält keine
  Teilnehmerzeilen“ (U10).
- **Vorschlag:** Zeilen, deren Werte alle leer sind, vor `_csv_zeile_zu_teilnehmer` still
  überspringen, wie Leerzeilen beim OMA-Import. Test dazu.
- **Gegenprüfung:** bestätigt, niedrig.

### Nr. 4 [optional, vorher niedrig] Gesperrte bzw. nicht lesbare Datei: Systemtext und falsche PDF-Meldung

- **Stelle:** `app.py:1229–1233` (Vorlage speichern), `db_import.py:658–663` (PDF, breites
  `except Exception`); ursprünglich auch `app.py:304–306` (CSV) und `1249–1253` (OMA).
- **Kategorie:** Fehlerbehandlung.
- **Widerlegt (Gegenprüfung mit Excel):** Eine in Excel geöffnete CSV lässt sich problemlos
  lesen; Excel sperrt nur gegen Schreiben. CSV- und OMA-Import scheitern daran nicht.
- **Bleibt:**
  - „Leere Vorlage speichern“ auf eine gerade geöffnete Datei: „Die Vorlage konnte nicht
    gespeichert werden:\n[Errno 13] Permission denied: 'C:\\…'“, ohne Hinweis auf das andere
    Programm. Der PDF-Export hat diesen Hinweis schon (`desktop_gemeinsam.py:172–177`).
  - PDF-Import: Jeder `OSError` (Datei inzwischen weg, Netzlaufwerk) wird als „keine lesbare
    PDF-Datei“ gemeldet.
  - Doppelte Backslashes (repr des Pfads) in allen OSError-Meldungen.
- **Vorschlag:** `PermissionError` beim Speichern der Vorlage gesondert melden („in einem
  anderen Programm geöffnet“); im PDF-Import vor dem breiten `except` ein `except OSError` mit
  „konnte nicht gelesen werden“. Optional gemeinsame Hilfe in `desktop_gemeinsam`.
- **Gegenprüfung:** teilweise bestätigt, auf optional herabgestuft.

### Nr. 6 [optional] NFC-Normalisierung nur beim PDF-Import

- **Stelle:** `db_import.py:135–143` (`_csv_wert`) und `372–376` (`_meldungs_schluessel`);
  dagegen `494–506` (PDF).
- **Ablauf (nachgestellt):** CSV mit `Müller` (NFC) und `Mu\u0308ller` (NFD), sonst gleich,
  ergibt 2 importiert, 0 übersprungen.
- **Vorschlag:** `unicodedata.normalize("NFC", …)` in `_csv_wert`; laut Gegenprüfung zusätzlich
  in `_meldungs_schluessel`, das deckt auch vorhandene Einträge ab.
- **Gegenprüfung:** bestätigt, optional.

### Nr. 7 [optional] PDF-Import prüft das Angebot vor der Dublette, anders als CSV und OMA

- **Stelle:** `db_import.py:588–589` und `667–679`; dagegen `284–292` und `444–452`
  (U4 + K8, Fortschritt.md Z. 3607: Dublettenerkennung zuerst).
- **Ablauf:** Formulare importieren, eine Prüfung aus dem Angebot nehmen, Ordner mit
  Nachzüglern erneut einlesen.
- **Ist:** Schon übernommene Teilnehmer erscheinen als „… nicht angeboten – Formular eines
  anderen Termins? Bitte mit dem Teilnehmer klären“ statt „bereits gemeldet“.
- **Vorschlag:** Dublettenschlüssel vor der Angebotsprüfung prüfen;
  `_anmeldeformular_zu_teilnehmer` muss die Angebotsprüfung dafür herausgeben, wie
  `_angebot_pruefen` bei CSV und OMA.
- **Gegenprüfung:** bestätigt, optional.

### Nr. 8 [optional] KI-Prompt: stilles Auslassen von Formularen und überholte Aussagen

- **Stelle:** `app.py:1083–1084`, `1102–1106`; dazu `db_import.py:605–612`.
- **Ist:**
  - „Ein Formular ohne diese Angaben bitte auslassen“: das Formular verschwindet spurlos; als
    Zeile ausgegeben würde der Import den Mangel melden.
  - „gegenstand_… stehen NICHT auf dem Meldeformular“ stimmt seit 28.09. nicht mehr für das
    eigene Programmformular; die Spalten fehlen in `CSV_IMPORT_SPALTEN` ohnehin.
  - Keine Regel zu Chip/Täto; der PDF-Import setzt das Präfix „Täto “.
  - „nicht raten oder freilassen mit einem Platzhalter wie 'unbekannt' füllen“ ist grammatisch
    kaputt.
- **Vorschlag:** Auch unvollständige Formulare als Zeile ausgeben, Gegenstände „werden nicht
  übernommen“, Täto-Regel ergänzen, Satz glätten.
- **Gegenprüfung:** bestätigt, optional.

### Nr. 9 [optional] Veraltete Docstrings und Kommentare, fragiler Textabgleich

- `db_import.py:61`: „Rückgabe von importiere_teilnehmer_aus_csv()“, gilt für alle drei Wege.
- `db_import.py:67–69`: `uebersprungen` wird seit N1 auch beim CSV-Import befüllt.
- `db_import.py:373`: „beim OMA-Import“, der Schlüssel gilt für alle drei.
- `db_import.py:702`: „TerminImportDialog in app.py“, heute `desktop_dialoge.py:650`.
- `db_import.py:704`: „kopiere_termin_daten() weiter unten“, steht in `db.py:2952`.
- `app.py:1241–1242`: „importiere_teilnehmer_aus_oma in db.py“, heute in `db_import.py`.
- `db_import.py:100–105` (`_hinweise_ergaenzen`) erkennt die Ablehnung am Text „nicht
  angeboten“; ein Fehlalarm wäre nur über einen passenden Namen möglich. Vorschlag: eigene
  Ausnahmeklasse (`NichtAngebotenError(ValueError)`) oder Zähler.
- **Gegenprüfung:** alle Stellen bestätigt, optional.

### Nr. 10 [optional] Testlücken

- **Bestätigt:**
  - `test_db.py:1994–1996`: Die Schleife prüft nur die letzte Meldung, entgegen dem Docstring.
  - In `test_db.py` fehlen Tests für die Befunde 1, 2, 3, 6 und 7.
  - In `test_app_gui.py` fehlen Tests für den Zweig „Import fehlgeschlagen“ (nach Nr. 4 nur noch
    für Vorlage und PDF sinnvoll) und für die Ausgabe von `ergebnis.hinweise`.
- **Abgeschwächt:** `_import_startordner()`/`_import_ordner_merken()` sind getestet
  (`test_app_gui.py:4079–4093`); es fehlt nur die Verdrahtung in den Dialogen.
- **Gegenprüfung:** teilweise bestätigt, optional.

## In anderen Befund überführt

- **Nr. 5 (vom Prüfer als niedrig gemeldet):** Unbegrenzte Namenslisten auch beim OMA- und
  PDF-Import (`app.py:1254–1266`, `1281–1293`); beim erneuten Einlesen werden alle vorhandenen
  Meldungen unter „bereits vorhanden“ gelistet. Drei fast gleiche Meldungsblöcke (CSV und OMA
  wörtlich gleich, PDF weicht in „Datei(en) nicht importiert“ und „Hinweis:\n“ ab). Laut
  Gegenprüfung dieselbe Ursache und Behebung wie Teil 1 Nr. 4, das schon eine gemeinsame Hilfe
  vorschlägt. Bei der Umsetzung von Teil 1 Nr. 4 alle drei Stellen umstellen
  (`_import_ergebnis_melden` o. ä.).

## Verworfene Teile

- **Nr. 4, Kern:** Eine in Excel geöffnete CSV lässt sich lesen; CSV- und OMA-Import scheitern
  daran nicht (mit Excel belegt).
- **Vorgemerkter Punkt aus Teil 4 (`TerminImportDialog`/`init_db`, `desktop_dialoge.py:717`):**
  Bestätigt, dass Trigger und Views der Quell-Datei beim Öffnen stillschweigend entfernt werden
  und die Datei dabei beschrieben wird. Kein eigener Befund, sondern Teilaspekt von Teil 1 Nr. 2
  (Quelle mit `mode=ro` öffnen). Keine Sicherheitsfolge (Quelle wird nur gelesen, SELECT löst
  keine Trigger aus); ein H-1-Hinweis brächte nichts, da keine Ergebnisse übernommen werden. Das
  Überschreiben von `_ENTFERNTE_FREMDOBJEKTE` ist folgenlos (schon in Teil 1 verworfen).
  Ergänzbar: Test, dass die Quell-Datei unverändert bleibt.

## Nur als Bezug, kein neuer Befund

- Die drei Import-Stellen (`app.py:302–306`, `1249–1253`, `1280`) fangen nur `OSError`, nicht
  `sqlite3.Error`. Bei schreibgeschütztem Termin kommt das allgemeine Fehlerfenster; bricht ein
  Import mittendrin ab, bleiben die bis dahin committeten Zeilen ohne Angabe der Anzahl. Gehört
  zu „Gemeinsam umsetzen“ (Teil 1 Nr. 7, Teil 3 Nr. 1, Teil 4 Nr. 4/5) und zum
  Schreibschutz-Hinweis für Teil 7/8.

## Ohne Befund geprüft (laut Prüfer)

Klartext-Meldungen (S-1), CSV-Formelschutz symmetrisch zwischen Export und Import (auch „'=“),
Kodierung (UTF-8 mit/ohne BOM, sonst cp1252), Zeilenzählung, Feldlimit; OMA: Leerzeilen, CR als
Zeilenende, abgeschnittene Zeilen, mehrfache Spalte `RESERVE`, „-“ als leer; PDF: Abfangen je
Datei, /AS-Rückfallweg, Gegenstände bei ED und DK; Dialogabbruch, Signale je einmal verbunden;
Aktualisierung nach dem Import; Startordner-Fallback. Bewusst entschieden und nicht gemeldet:
P1–P3, Ablehnung des ganzen Formulars bei falschem optionalem Feld, keine Statusfilterung bei OMA,
„keine Teilnahme“ nicht importiert, keine Dublettenprüfung beim Termin-Import, Commit je Zeile.

## Hinweise für spätere Teile

- **Teil 6 (Export):** `exportiere_teilnehmer_csv` und „In Excel öffnen“ sind der zweite Weg zu
  Nr. 1; prüfen, ob dort gegengesteuert werden kann (Hinweis im Meldungsfenster oder Handbuch).
  Theoretische Asymmetrie: „' =x“ wird beim Export nicht geschützt, beim Import aber zu „=x“.
- **Teil 9:** Einheitlicher Umgang mit `PermissionError` („Datei in anderem Programm geöffnet“)
  in allen Schreibdialogen (siehe Nr. 4).
