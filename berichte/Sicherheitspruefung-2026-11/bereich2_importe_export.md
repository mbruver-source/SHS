# Bereich 2: Importe und Export (Desktop)

Rohergebnis des Prüfers (Agenten-Typ `qs-sicherheit`), Stand HEAD e557b0f (1.0.61), 13.11.2026.
Umgebung der Nachstellungen: Python 3.14.8, SQLite 3.53.4, pypdf 6.19.0, Qt offscreen. Die Skripte sind
nicht veröffentlicht. Nicht belegt: GUI-Slots von Klick bis Meldung, Verhalten in
Excel/LibreOffice, I-3 unter Linux/macOS.

| Kennung | Schwere | Kurzfassung |
|---|---|---|
| I-5 | mittel (untere Grenze) | Überlange importierte Werte lassen Sammel-Ausdrucke des ganzen Termins scheitern |
| I-1 | gering | Sehr große Zahl bei „Schulterhöhe“ bricht den ganzen Import-Stapel ab |
| I-2 | gering | Quadratische Laufzeit von drei regulären Ausdrücken auf fremden Werten |
| I-3 | gering | Datum der Veranstaltung unbereinigt im Dateinamen, Export schreibt außerhalb des Ablageorts |
| I-4 | gering | Abrechnungs-CSV schreibt das Datum ohne Formelschutz |
| I-6 | gering | Abschlussmeldung übernimmt fremde Werte ungekürzt und mit Zeilenumbrüchen |
| I-7 | Hinweis | Unsichtbare Zeichen/Steuerzeichen werden gespeichert, Dublettenerkennung umgehbar |
| I-8 | Hinweis | Formelschutz sieht nicht hinter unsichtbare Zeichen am Zellanfang |
| I-9 | Hinweis | Laufzeit im GUI-Thread wächst mit der Dateigröße, ohne Obergrenze |

## I-5: Überlange importierte Werte

- Stelle: `db_import.py:210-219` (`_csv_wert`), `:694-696` (`_pdf_text`) ohne Längengrenze;
  `db_stamm.py:163-194` (`add_teilnehmer`) prüft nichts. Formularfelder ohne `maxlen`
  (`pdf_export.py:2069`).
- Weg: Teilnehmer trägt 3000 Zeichen in ein Formularfeld ein; Import meldet „1 Teilnehmer importiert“;
  am Prüfungstag scheitern die Sammel-Ausdrucke mit „Programmfehler (LayoutError: Flowable <Table…>
  too large on page 2 …)“. Die Meldung nennt weder Teilnehmer noch Feld.
- Nachgestellt: `b2\i9_sammelexport.py`, `b2\i8_lange_werte_pdf.py`.

| Feld | ab 1000 Zeichen scheitert | ab 3000 Zeichen scheitert zusätzlich |
|---|---|---|
| `nachname` | Übersicht Prüfungsleitung | alle Bewertungsbögen, Chipnummernliste, leere Ergebnisliste |
| `rufname_hund` | Übersicht, Chipnummernliste | alle Bewertungsbögen |
| `verein` | Übersicht | alle Bewertungsbögen, leere Ergebnisliste |
| `zwingername` | nichts | alle Bewertungsbögen |
| `kennzeichnung_nr` | Übersicht, Chipnummernliste | alle Bewertungsbögen |

  300 Zeichen überall unkritisch, `rasse` bis 3000, Etiketten immer; Einzel-Bewertungsbogen scheitert
  ab 2000 Zeichen im Nachnamen.
- Abgrenzung: C9 P1 betrifft `_af_hart_umbrechen` am eigenen Meldestellen-Text.
- Vorschlag: Obergrenze je Feld beim Import (z. B. 100 Zeichen Namen/Verein/Zwinger/Rasse, 40 Nummern,
  254 E-Mail), dieselbe Grenze im `TeilnehmerDialog` und im Stammdaten-Import; in `pdf_export` einen
  `LayoutError` abfangen und den Teilnehmer nennen.

## I-1: Sehr große Zahl bei „Schulterhöhe“

- Stelle: `db_import.py:257-263` (`int()` ohne Wertebereich); `:435-436` (CSV), `:851-852` (PDF) fangen
  nur `ValueError` und `sqlite3.IntegrityError`; Slots `desktop_import_meldungen.py:248-256`,
  `desktop_formular.py:335-340` fangen nur `OSError` bzw. `sqlite3.Error`.
- Weg: `1000000000000000000000000000000` im Feld „Größe“ bzw. in `schulterhoehe_cm`; `add_teilnehmer`
  wirft `OverflowError`, die Ausnahme verlässt Schleife und Slot.
- Auswirkung: folgende Dateien/Zeilen werden nicht eingelesen, keine Abschlussmeldung, Fenster
  „Unerwarteter Fehler“; `self.aktualisieren()` entfällt (`desktop_teilnehmer.py:716-717`).
- Nachgestellt: `b2\i1_ausnahmetypen.py` (CSV: nur erste von drei Zeilen; drei PDFs: nur die erste).
  Unter Python 3.11 gleich.
- Vorschlag: Bereich prüfen (z. B. 1 bis 150 cm); in den drei Schleifen zusätzlich `OverflowError` bzw.
  `sqlite3.Error` je Zeile/Datei als Fehlerzeile melden.

## I-2: Quadratische Laufzeit

| Stelle | Auslöser | 10 000 | 20 000 | 40 000 |
|---|---|---|---|---|
| `db_import.py:757`, `re.sub(r"\s*cm\s*$", …)` | langer Leerzeichenlauf mitten im Feld „Größe“ (nur PDF) | 0,45 s | 1,9 s | 7,7 s |
| `db_import.py:136`, `rat_bei_ablehnung` | viele „ ohne schließendes “ in einem abgelehnten Wert | 0,05 s | 0,21 s | 0,87 s |
| `desktop_gemeinsam.py:98`, `_dateiname_teil` | langer Leerzeichenlauf im Nachnamen, Knopf „Bewertungsbogen“ | 1,25 s | 4,7 s | 18,4 s |

- Weg: Formular-PDF mit `4` + 400 000 Leerzeichen + `5` im Feld „Größe“ (rund 400 KB); hochgerechnet
  rund 13 Minuten hängendes Fenster, ohne Meldung.
- Nachgestellt: `b2\i2_regex_laufzeit.py`, `b2\i2c_dateiname.py`.
- Vorschlag: Längengrenze aus I-5 vor die Ausdrücke; `cm` ohne Regex abschneiden; Muster `„[^“„]*“`;
  in `_dateiname_teil` vorher kürzen.

## I-3: Datum unbereinigt im Dateinamen

- Voraussetzung: fremde/präparierte Termin-Datei (über den Veranstaltungsdialog geht es nicht).
- Stelle: `desktop_gemeinsam.py:101-104` (`_export_dateiname` setzt `veranstaltung.datum` ohne
  `_dateiname_teil` ein), `:284-291` („ohne Nachfrage“ verbindet Ablageort und Vorschlag ungeprüft),
  `db_termine.py:349` (für `datum` nur Typ Text verlangt).
- Weg: Datum `x\..\..\..\..\..\AUSSERHALB`; Export mit „ohne Nachfrage speichern“ (Standard seit
  12.11.2026) schreibt `…\AUSSERHALB.csv` außerhalb des Ablageorts.
- Betroffen: alle Aufrufer von `_export_dateiname`.
- Grenzen: Endung immer `.pdf`/`.csv`, Inhalt ist der normale Export, `_freier_dateipfad` verhindert
  Überschreiben, die Meldung zeigt danach den echten Pfad.
- Nachgestellt: `b2\i3_datum_dateiname.py` („innerhalb des Ablageorts: False“).
- Vorschlag: Datum nur einsetzen, wenn `lies_datum` es lesen kann, sonst durch `_dateiname_teil`; in
  `_speicherort_waehlen` prüfen, dass der Ordner des Ergebnisses der Ablageort ist; in
  `_termin_werte_pruefen` das Datum prüfen (mit Marco klären wegen Altbestand).

## I-4: Abrechnungs-CSV ohne Formelschutz beim Datum

- Voraussetzung wie I-3. Stelle: `db_import.py:1014`, `:1022`; `datum_anzeige` gibt einen nicht
  lesbaren Wert unverändert zurück (`db_stamm.py:622-625`).
- Nachgestellt: `b2\i3_datum_dateiname.py`, Ausgabezeile beginnt mit `=1+1;Richter Eins;…`.
- Vorschlag: `_csv_zelle_absichern(datum)`.

## I-6: Abschlussmeldung mit fremden Werten

- Stelle: `db_import.py:173-176`, `:179-185`, `db_stamm.py:606`, `db_import.py:432`, `600`, `845-848`;
  Anzeige `desktop_import_meldungen.py:93-128` (`_MELDUNG_LISTE_MAX` begrenzt nur die Zahl der Einträge).
- Auswirkung: vorgetäuschte Meldungszeilen über Umbrüche im Namen; 20 abgelehnte Zeilen mit je 131 000
  Zeichen: Fensteraufbau 13,5 s, berechnete Höhe 467 570 Pixel (OK-Knopf außerhalb, Enter/Esc gehen).
- Nachgestellt: `b2\i6_wertehygiene.py`.
- Vorschlag: gemeinsamer Helfer für Werte in Meldungen (Steuerzeichen/Umbrüche ersetzen, auf 60 Zeichen
  kürzen).

## I-7 (Hinweis): Unsichtbare Zeichen

- Stelle: `db_import.py:213`, `:517-521` (`_meldungs_schluessel`), `desktop_gemeinsam.py:98`.
- Nachgestellt: `b2\i6_wertehygiene.py` (U+200B und U+00AD ergeben drei verschiedene Meldungen; NUL,
  Tab, Umbruch, U+202E werden gespeichert; U+202E bleibt im Dateinamen-Vorschlag, Endung bleibt `.pdf`).
- Vorschlag: Kategorien Cc und Cf beim Import entfernen, im Schlüssel zusätzlich NFKC.

## I-8 (Hinweis): Formelschutz hinter unsichtbaren Zeichen

- Stelle: `db_import.py:960` (`kern = wert.lstrip()`).
- Nachgestellt: `b2\i7_formelschutz.py`. Nicht geschützt: Formelanfang hinter U+200B, U+FEFF, U+2060,
  U+00AD, U+202E, NUL oder Anführungszeichen; Vollbreite-Zeichen ＝ ＋ － ＠ ﹦. Auswertung in
  Excel/LibreOffice nicht belegt.
- Vorschlag: in `_braucht_schutz` Cc/Cf überspringen.

## I-9 (Hinweis): Laufzeit ohne Obergrenze

- Stelle: `desktop_formular.py:336`, `desktop_import_meldungen.py:249` (im Slot, ohne Wartecursor);
  `db_import.py:366-367`, `534-535`, `654`.
- Nachgestellt: `b2\i5_pypdf_ressourcen.py`, `b2\i10_menge.py`.

| Fall | Dateigröße | Laufzeit | Speicherspitze |
|---|---|---|---|
| 1 Mio. Feldverweise auf dasselbe Feld | 5,9 MB | 65,7 s | 150 MB |
| 2 Mio. Annotationsverweise | 11,7 MB | 16,8 s | 255 MB |
| ein Feldwert mit 4 MB | 4 MB | 3,1 s | – |
| ein Feldwert mit 50 MB | 51 MB | über 90 s, abgebrochen | – |
| CSV mit 2000 Zeilen | 30 KB | 6,0 s (Commit je Zeile) | – |

- Vorschlag: Dateigröße vor dem Lesen prüfen (z. B. 5 MB je PDF, 2 MB je CSV/OMA), ab 500 Zeilen
  nachfragen, Wartecursor, eine Transaktion je Datei.

## Nebenbei (Korrektheit, kein Sicherheitsbefund)

`desktop_formular.py:313` und `:339` rufen `self.aktualisieren()` auf, `FormularImportTab` hat diese
Methode nicht: nach einem Schreibfehler mitten im OMA-/PDF-Import folgt ein `AttributeError`.

## Regression geprüft

- CSV-Formeln beim Export (`_braucht_schutz`/`_csv_zelle_absichern`, `db_import.py:948-974`): greift im
  Teilnehmer-Export für alle Spalten und in der Abrechnungs-CSV für Empfänger und Verwendungszweck;
  nicht für deren Spalte „Datum“ (I-4). Re-Import nimmt die Maskierung sauber zurück (184 Werte).
- S-1 in den Import-Meldungen: Klartext (`desktop_formular.py:148`, `:201`,
  `desktop_import_meldungen.py:115`, `desktop_gemeinsam.py:207`).
- PDF-Import, Ausnahmen je Datei (`db_import.py:819-834`): greift für alles aus pypdf (Zyklen, 1000×1000
  Seiten, 1-GB-Flate-Strom, 100 000-fach verschachteltes Array, verschlüsselte PDFs); nicht für den
  `OverflowError` dahinter (I-1). Grenzen aus pypdf 6.19.0; ob 6.10 sie schon hat, ungeprüft.
- `_dateiname_teil`: greift für Nachname und Richtername, nicht angewandt auf das Datum (I-3).
- K-2: steht. Bauart aus Bereich 1 (Spaltennamen in SQL): im Import-Code nicht vorhanden.
- Absturzprotokoll: für I-1 und I-5 nur Tracebacks ohne Personendaten.

## Ohne Befund geprüft

„KI-Liste“ (fester Prompt ohne Termin-/Personendaten, kein Netzmodul, Antwort durchläuft die normale
CSV-Prüfung, Datenschutzhinweis im Reiter); Kodierung und Trennzeichen; Werteprüfung gegen feste Listen;
lineare Muster; Startnummer wird nicht importiert; Stammdaten-Import; Feldnamen aus der PDF nur als
Schlüssel; kein Überschreiben bei „ohne Nachfrage“; Ablageort aus dem echten Dateinamen; CSV-Vorlage;
Diagnose ersetzt Benutzerpfad.
