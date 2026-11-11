# Desktop-Prüfung Teil 9: Darstellung, Hilfe und Fehlerbehandlung

- **Datum:** 14.10.2026
- **Commit:** d903ee0
- **Code:** `desktop_darstellung.py`; `desktop_dialoge.py` `HilfeDialog`; `desktop_gemeinsam.py`
  `_fehler_anzeigen`, `_db_fehler_anzeigen`, Übersetzung/Qt-Texte, `programmsymbol*`,
  `meldungsfenster_als_klartext`, Absturzprotokoll, `_kurzpfad`, `_ohne_benutzerpfad`,
  `diagnose_text`, `_fehlerbild`, Fehlerfenster
- **Tests:** `test_theme.py` + GUI-Teilmenge Darstellung/Fehlerfenster/Diagnose/Hilfe: 37 passed,
  56 subtests
- **Ablauf:** Prüfer (`desktop-pruefer`), danach Gegenprüfung durch einen zweiten `desktop-pruefer`;
  nachgestellt mit PySide6 6.11 unter Windows 11 (Stil `windows11`) bzw. offscreen

**Ergebnis:** 12 bestätigte Befunde: **1 hoch**, 1 mittel, 3 niedrig (davon 1 Sicherheit), 7 optional.

**Sicherheitsbefund:** Nr. 3 (niedrig). Bis zum Release nur allgemein erwähnen.

---

## Hoch

### Nr. 1 Design „Hell“ (Standard) ist bei dunklem System-Farbschema unlesbar

- **Stelle:** `desktop_darstellung.py:534–549` (`_darstellung_anwenden`), `_QSS_TEMPLATE`
  (`QWidget { color: #1B2430 }`; hellen Hintergrund bekommen nur `QMainWindow`, `QDialog`, Tabellen
  und Eingabefelder), Kommentar Z. 545f.
- **Kategorie:** Korrektheit / Qt.
- **Ablauf:**
  - Das Programm setzt keinen eigenen Stil. Bei „Hell“ bleiben Stil (`windows11` ab Qt 6.7) und
    Systempalette unverändert; nur „Dunkel“ wechselt zu Fusion.
  - `windows11` folgt dem System-Farbschema: Bei „Apps: dunkel“ ist Window `#1e1e1e`, Base `#2d2d2d`.
  - Das Stylesheet setzt die Schrift fast schwarz. Alles, was den Hintergrund aus der Palette nimmt,
    wird dunkel mit dunkler Schrift (Kontrast ≈ 1,3:1):
    - Viewports von `QScrollArea`: Veranstaltungsdialog („Neuen Termin anlegen“, `desktop_dialoge.py:1439`),
      Teilnehmer-Dialog (`desktop_dialoge.py:322`), Zeitplan-Reiter (`app.py:2612`);
    - `QListWidget` (Richter-Spalten im Zeitplan, Termin-Import, Bewertungsbogen-Auswahl);
    - `QTextBrowser` (Hilfe), `QPlainTextEdit` (Meldestelle), `QGroupBox`;
    - Menü-Popups, also auch der Ausweg „Ansicht → Hintergrund → Hoher Kontrast“.
  - Hauptfenster, Menüleiste, Tabellen, Eingabefelder und Meldungsfenster bleiben hell.
- **Nachgestellt (beide Prüfer):** echte Windows-Plattform, `app.styleHints().setColorScheme(Qt.ColorScheme.Dark)`,
  Design „hell“. Gerenderte Bilder von `VeranstaltungsDialog` und `HilfeDialog`: Feldbeschriftungen und
  Hilfetext praktisch unsichtbar.
- **Vorbehalt:** Der echte App-Modus „Dunkel“ wurde nicht umgeschaltet (keine Systemänderungen).
  `setColorScheme` nutzt unter Windows denselben Weg (`QWindowsTheme::requestColorScheme`) wie eine
  Systemumstellung, der Vorbehalt ist laut Gegenprüfung weitgehend ausgeräumt. Betroffen: Windows 11
  mit „Apps: dunkel“, macOS im Dunkelmodus. Windows 10 (`windowsvista`) vermutlich nicht (nicht
  nachgestellt). Ein kurzer Test am echten Rechner mit Dunkelmodus wäre trotzdem gut.
- **Bezug zu früherer Entscheidung:** `Fortschritt.md:1805f.`: „Die Palette wird beim Start in Hell
  nicht mehr explizit gesetzt … So folgt Hell weiter dem Windows-Farbschema.“ Das war ein Vorschlag der
  Verifikation; die Folge (dunkle Stylesheet-Schrift auf dunkler Systempalette) wurde damals nicht
  betrachtet, getestet wurde nur der Stil-Rückweg. Kein akzeptiertes Restrisiko, aber eine Korrektur
  hebt diese Festlegung auf – Entscheidung bei Marco.
- **Schweregrad:** hoch (Standarddesign, gängige Systemeinstellung, Kernabläufe nicht ablesbar; kein
  Datenverlust – wer „hoch“ nur für Datenverlust vergibt, stuft auf mittel).
- **Vorschlag:**
  - Für „hell“ ebenfalls eine feste helle Palette setzen (`_design_palette(theme, _DESIGNS["hell"])`),
    und/oder ab Qt 6.8 `app.styleHints().setColorScheme(Light/Dark je design["dunkel"])` mit
    `hasattr`-Prüfung (`PySide6>=6.7` erlaubt).
  - Kommentar „folgt dem Windows-Farbschema“ anpassen.
  - Test: dunkle App-Palette setzen, `_darstellung_anwenden("hell")`, dann
    `palette().color(Base/Window).lightness() > 200`.

## Mittel

### Nr. 2 Häkchen-URL im Stylesheet ohne Anführungszeichen: Umlaut oder „'“ im Temp-Pfad zerstört das Stylesheet

- **Stelle:** `desktop_darstellung.py:234` (`image: url(@@HAKEN@@)`), `249` (`_haken_pfad`), `431`.
- **Kategorie:** Korrektheit / Qt.
- **Ablauf:** Temp-Pfad mit Nicht-ASCII-Zeichen oder Apostroph (z. B. `C:\Users\Jürgen`, `René`,
  `O'Brien`; `TEMP` zeigt oft, aber nicht immer auf die 8.3-Kurzform). In Sand, Dunkel und Hoher
  Kontrast meldet Qt „Could not parse application stylesheet“; das komplette Stylesheet fällt weg.
- **Nachgestellt (beide Prüfer):** angehakte und leere `QCheckBox` pixelgleich (`grab()` identisch),
  alle Knöpfe in Akzentfarbe `#2F6FED`. Leerzeichen/Klammern unkritisch; mit `url("…")` fehlerfrei.
  „Hell“ nicht betroffen.
- **Folge:** DQ und Abbruch in der Ergebniserfassung (`app.py:1592/1596`), „Startnummer steht noch
  nicht fest“, angebotene Prüfungen usw. nicht ablesbar; erneutes Anklicken kehrt den Zustand um.
  „Hoher Kontrast“ empfiehlt die Hilfe ausdrücklich.
- **Vorschlag:** `image: url("@@HAKEN@@");`, im Pfad `"` und `\` maskieren. Test: alle 12 Kombinationen
  mit Häkchen-Pfad mit „ü“, „'“ und Leerzeichen, per `qInstallMessageHandler` auf „Could not parse“ prüfen.
- **Gegenprüfung:** bestätigt, mittel.

## Niedrig

### Nr. 3 [SICHERHEIT] Häkchen-Bild im gemeinsam genutzten Temp-Ordner, vorhandene Datei wird übernommen

- **Stelle:** `desktop_darstellung.py:247–273`.
- **Ablauf:** Unter Linux (Vorschau) ist `tempfile.gettempdir()` das gemeinsame `/tmp`; unter Windows
  nur, wenn `TEMP` z. B. auf `C:\temp` umgelegt ist. Ein anderer lokaler Benutzer legt vorab
  `/tmp/SHS-Pruefungsprogramm/` an; `os.makedirs(exist_ok=True)` übernimmt ihn.
  - (a) Eine fremde `haken.png` wird nach `isfile` und Größe > 0 ungeprüft geladen (Bilddecoder).
  - (b) `haken.png` als ins Leere zeigender Symlink: `isfile` False, `QImage.save` legt die Zieldatei
    mit den Rechten des Opfers an. `fs.protected_symlinks` greift nicht (Ordner nicht sticky, gehört
    dem Angreifer).
- **Folge:** gering – PNG an fremd bestimmter, noch nicht vorhandener Stelle bzw. fremdes Bild im
  Kästchen. macOS und Windows-Standard nicht betroffen.
- **Vorschlag:** benutzereigener Ordner (`termine_ordner().parent`, dort liegt schon das
  Absturzprotokoll, oder `QStandardPaths.CacheLocation`); Bild bei jedem Start atomar neu schreiben.
- **Gegenprüfung:** bestätigt, niedrig, Sicherheit.

### Nr. 4 Absturzprotokoll: im Lauf unbegrenzt, beim nächsten Start ganz gelöscht

- **Stelle:** `desktop_gemeinsam.py:596–598`, `610–616`.
- **Ablauf:** `_protokollieren` schreibt jeden unbehandelten Fehler mit vollem Traceback und `flush()`
  ohne Grenze. Ein wiederkehrender Fehler in `paintEvent` oder einem Timer (landet über `PyErr_Print`
  im Hook) lässt die Datei beliebig wachsen und kostet bei jedem Zeichnen Plattenzugriffe. Beim nächsten
  Start ist sie > 1 MB und wird mit `"w"` geleert – die Ursache ist weg, bevor „Diagnose kopieren“
  möglich ist.
- **Vorschlag:** beim Start rotieren (`absturzprotokoll.alt.txt`), `diagnose_text` nimmt das Ende der
  alten Datei mit; im Hook gleiche Tracebacks zählen („… 250× wiederholt“) oder Größe beim Schreiben prüfen.
- **Gegenprüfung:** bestätigt, niedrig (setzt wiederholten Fehler voraus). Größentest vorhanden
  (`test_app_gui.py:3685`).

### Nr. 5 Breite Fänger bei PDF und Sicherung: nichts im Absturzprotokoll, PDF-Meldung nennt falsche Ursache

- **Stelle:** `desktop_gemeinsam.py:172–177`, `200`; `app.py:847`, `2284`, `3265` (über
  `_pdf_export_fehler_anzeigen`); `app.py:3510`, `3581` (Sicherung).
- **Ablauf:** `except Exception` zeigt nur `str(exc)` (bei `KeyError('Albers')` nur „'Albers'“), nichts
  wird protokolliert – „Diagnose kopieren“ und „Protokoll-Ordner öffnen“, auf die Hilfe und Handbuch
  verweisen, enthalten nichts. Die PDF-Meldung schreibt jeden Fehler dem Zielpfad oder einer geöffneten
  Datei zu, auch reportlab-Parserfehler (Weg aus Teil 6 Nr. 1) und Programmierfehler.
- **Nachgestellt:** `pdf_export.erstelle_ergebnisliste_pdf` mit `KeyError("Albers")` gepatcht: Meldung
  „…Zielpfad nicht schreibbar…: 'Albers'“, Protokoll unverändert.
- **Abgrenzung:** Demo-Anteil ist Teil 10 Nr. 6.
- **Vorschlag:** `fehler_protokollieren(exc)` in `desktop_gemeinsam` (auch für die Demo);
  `_pdf_export_fehler_anzeigen` unterscheidet `OSError` von anderen Fehlern („Programmfehler – bitte
  über Version → Diagnose kopieren melden“, mit `type(exc).__name__`).
- **Gegenprüfung:** bestätigt, niedrig.

## Optional

### Nr. 6 Kein gemeinsamer Klartext für erwartbare Datei- und Datenbankfehler

- **Stelle:** `desktop_gemeinsam.py:331–349` (`_fehler_anzeigen`, `_db_fehler_anzeigen`), `172–177`;
  `app.py:3284–3286` (CSV), `3510ff.` (Sicherungs-ZIP); Importstellen Teil 5 Nr. 4.
- `PermissionError` erscheint als `[Errno 13] Permission denied: '…'`; `_db_fehler_anzeigen` zeigt rohes
  Englisch („attempt to write a readonly database“, „database is locked“, „database or disk is full“).
- `_fehler_anzeigen`/`_fehlerbild` sind der falsche Ort (Fachregel bzw. Schlüssel der Duplikatsperre).
- **Vorschlag:** `_klartext_fehler(exc) -> str`: `PermissionError` → „schreibgeschützt oder in einem
  anderen Programm (z. B. Excel, PDF-Anzeige) geöffnet – bitte dort schließen“; dazu
  `FileNotFoundError`, `ENOSPC`, typische `sqlite3.OperationalError`; sonst `str(exc)`. Genutzt von
  `_db_fehler_anzeigen`, PDF, CSV, Sicherung. Einzelstellen bleiben in Teil 5/6/7 gezählt.

### Nr. 7 Fehlerfenster nach Fehler in `main` verspricht Weiterarbeit, das Programm endet aber

- **Stelle:** `desktop_gemeinsam.py:743–749`; `app.py:4495–4507`.
- Fehler in `_startdialog_schleife`, `init_db` oder `HauptFenster(...)` (z. B. kaputte Datei über
  „Andere Termin-Datei öffnen“, Teil 7 Nr. 4) verlässt `main`; der Hook zeigt „Termin neu öffnen bzw.
  Programm neu starten“, nach OK endet der Prozess mit Code 1.
- **Vorschlag:** `try/except Exception` in `main` nach `QApplication`, `fehlerfenster_zeigen(...,
  programm_endet=True)` mit „Das Programm wird beendet …“, protokollieren, `return 1`.

### Nr. 8 Qt-Warnungen gehen in der installierten Fassung verloren

- **Stelle:** `desktop_gemeinsam.py:582–623`; im Repo kein `qInstallMessageHandler`.
- Ohne Konsole verschwinden z. B. „Could not parse application stylesheet“ (Nr. 2) oder „QPainter::begin“.
- **Vorschlag:** `qInstallMessageHandler` ab `QtWarningMsg` ins Absturzprotokoll, mit
  Wiederholungsbegrenzung (Nr. 4).

### Nr. 9 Design Dunkel: leere Ankreuzkästchen in Listen kaum sichtbar

- **Stelle:** `desktop_darstellung.py:220–244` (`_QSS_CHECKBOX_ZUSATZ` nur `QCheckBox::indicator`);
  betroffen `desktop_dialoge.py:721` (Termin-Import), `892` (Bewertungsbogen-Auswahl).
- Gerendert: Häkchen gut sichtbar, leerer Kasten nur schwach.
- **Vorschlag:** `QAbstractItemView::indicator` mit denselben Regeln aufnehmen.

### Nr. 10 Rückgabe von `QDesktopServices.openUrl` ungeprüft

- **Stelle:** `desktop_gemeinsam.py:115`, `131`; `app.py:3248`, `3809`; `desktop_demo.py:622`.
- Liefert `openUrl` False (z. B. Linux ohne `xdg-open`), passiert nichts. Unter Windows zeigt meist die
  Shell selbst einen Dialog.
- **Vorschlag:** bei False Klartext-Meldung mit Pfad bzw. URL.
- **Gegenprüfung:** teilweise bestätigt; der Teil „URLs in der Hilfe nicht anklickbar“ ist verworfen
  (siehe unten).

### Nr. 11 Veraltete bzw. ungenaue Texte

- `desktop_darstellung.py:38`: „siehe main() unten“ – `main` liegt in `app.py`.
- Hilfe `desktop_dialoge.py:1197`: „Der Button "Version" neben "Hilfe"“ – Reihenfolge ist Wechseln,
  Version, Demoprüfung, Hilfe (`app.py:3934–3938`).
- `desktop_darstellung.py:279–280`: Kommentar zu Kleinbuchstaben-Schlüsseln ungenau (`anzeigename`,
  `dunkel` sind ebenfalls klein; einige semantische Farben fließen in `_design_palette` ein).
- `deutsche_qt_texte_laden` (`desktop_gemeinsam.py:553–559`): je erfolglosem Ordner bleibt ein
  `QTranslator` liegen – ein bis zwei Objekte beim Start, bedeutungslos.

### Nr. 12 Testlücken

- Kein Parse-Test des Stylesheets für alle 12 Kombinationen mit Sonderzeichen im Häkchen-Pfad (Nr. 2).
- Kein Test für „Hell“ bei dunkler System-/App-Palette (Nr. 1).
- `_kurzpfad` und die Kurzpfad-Ersetzung in `_ohne_benutzerpfad` ungetestet (Windows-CI oder gepatcht).
- Kein Test für den Fehlerfenstertext bei Fehler in `main` (Nr. 7).
- (Größentest des Protokolls vorhanden; Rotationstest erst mit Nr. 4.)

---

## Verworfen

- **URLs in der Hilfe nicht anklickbar (Teil von Nr. 10):** bewusst entschieden
  (`Fortschritt.md:2541f.`: „Der Hilfe-Dialog öffnet bewusst keine externen Links“). Die Zeilen
  `desktop_dialoge.py:1114/1217/1235` sind keine `openUrl`-Aufrufe.

## Einordnung vorgemerkter Hinweise

- **Duplikatsperre (`_fehlerbild`, `fehlerfenster_einrichten`):** „Fehlerbild = Typ + innerste Stelle,
  einmal je Sitzung“ hat Marco am 13.10.2026 bewusst zurückgestellt (Fortschritt.md Z. 5785–5792,
  5816f.) – kein Befund. Die Folgen (Teil 3 Nr. 1, Teil 8 Nr. 1) entfallen, sobald diese Stellen gezielt
  fangen. Falls nachgeschärft werden soll: erneut anzeigen nach Zeitfenster, mit Zähler.
- **PermissionError einheitlich:** Nr. 6.
- **„Programm neu starten“ bei Fehler in `main`:** Nr. 7.
- **`openUrl` ungeprüft:** Nr. 10.
- **Demo-Fehler nicht im Protokoll:** Teil 10 Nr. 6; die Hilfsfunktion aus Nr. 5 deckt es mit ab.
- **Liegengebliebene Boxen/Dialoge:** Gruppe aus Teil 8, nicht neu gezählt.
- **Zeitplan verwirft getippte Startzeit beim Designwechsel:** hingenommen (Fortschritt.md Z. 1812–1814),
  Teil 4 Nr. 3.

## Ohne Befund geprüft

Deutsche Qt-Texte (eingebauter Übersetzer ohne `.qm`, Qt 6.11 nachgestellt); `meldungsfenster_als_klartext`
(Signaturen, Standardknöpfe, Rückgabe, `NoButton` bei `done(0)`); `fehlerfenster_zeigen` (Klartext,
Details ohne Benutzerpfad, Kopieren schließt nicht, Protokoll-Ordner); Hook-Reihenfolge (Protokoll
zuerst, Nebenthread, `KeyboardInterrupt`, fehlende App, Fehler beim Anzeigen geschluckt); Fehler aus
`paintEvent` (Fenster öffnet sauber, zweiter gleicher Fehler unterdrückt); `_ohne_benutzerpfad`
(Schreibweisen, ganze Ordnernamen); `diagnose_text`; Programmsymbol; QSettings-Rückfall; Ansicht-Menü
und Darstellungswechsel; Kontraste (WCAG-Tests); `HilfeDialog` (fester Inhalt, keine Fremddaten).
