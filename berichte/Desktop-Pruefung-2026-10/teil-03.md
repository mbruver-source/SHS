# Desktop-Prüfung Teil 3: Ergebniserfassung

- **Datum:** 14.10.2026
- **Commit:** 6557190 (Version 1.0.47; Programmcode seit 25f9572 unverändert)
- **Geprüft:**
  - `app.py`: `_punkte_validator`, `ErgebnisTab`;
  - `desktop_gemeinsam.py`: `_responsive_schriftgroesse`, `_ergebnis_spaltenbreiten_verteilen`,
    `ResponsiveSchriftMixin`, Ergebnis-Spaltenkonstanten (`_ERGEBNIS_SPALTEN_JE_DISZIPLIN`,
    `_DQ_SPALTE`, `_ABBRUCH_SPALTE`, `_STATUS_SPALTE`);
  - die dabei aufgerufenen Ergebnisfunktionen in `db.py` und `shs_core.py`.
- **Ablauf:**
  - `desktop-pruefer` im Prüfmodus, danach Gegenprüfung durch einen zweiten `desktop-pruefer`.
  - Beide haben mit eigenen Skripten nachgestellt (PySide6 6.11, offscreen; Gegenprüfung mit
    pytest-qt und einem reinen SQLite-Skript).
  - Die 53 vorhandenen GUI-Tests zur Ergebniserfassung sind grün.
- **Ergebnis:**
  - 9 Befunde gemeldet. 6 bestätigt (1–4, 6, 7), 3 teilweise bestätigt (5, 8, 9).
    Kein Sicherheitsbefund.
  - Die Gegenprüfung hat Nr. 5 von niedrig auf optional herabgestuft (Teil „keine Teilnahme“
    verworfen) und bei Nr. 9 den Teil „viele Zeilen“ auf optional abgeschwächt.

| Schweregrad | Anzahl | Befunde |
|---|---|---|
| mittel | 2 | 1, 2 |
| niedrig | 3 | 3, 4, 9 |
| optional | 4 | 5, 6, 7, 8 |

**Stand mit Marco:** alle Befunde noch unbesprochen.

## Bestätigte Befunde

### Nr. 1 [mittel] Schreibfehler der Datenbank: ungespeicherte Ergebnisse gehen beim Schließen ohne Rückfrage verloren

- **Stelle:** `app.py:2081-2085` fängt nur `sqlite3.IntegrityError`. `eintragen_ergebnis` in
  Z. 2058 (Leeren) und `setze_ergebnis_status` in Z. 2096 haben gar kein `try`.
  `db.eintragen_ergebnis`/`setze_ergebnis_status` (db.py:1264-1285) committen je Aufruf.
  Aufrufer: `_beenden_vorbereiten` (4079ff.), `_sitzungsende_pruefen` (4110-4116),
  `_tab_gewechselt` (4245-4247).
- **Kategorie:** Datenintegrität, Fehlerbehandlung.
- **Ablauf (von beiden nachgestellt):**
  - Termin-Datei schreibgeschützt (z. B. von schreibgeschütztem Stick) oder von einem anderen
    Prozess gesperrt. `init_db` öffnet sie ohne Fehler; der erste Schreibversuch wirft
    `OperationalError: attempt to write a readonly database` bzw. `database is locked`.
  - „Alle Ergebnisse speichern“: nur das allgemeine Fenster „Unerwarteter Fehler … Bereits
    gespeicherte Daten bleiben erhalten“.
  - Fenster mit X schließen: Die Ausnahme fliegt aus `closeEvent`, das Ereignis bleibt
    angenommen, das Fenster schließt. Die Nachfrage „Nicht alle Ergebnisse gespeichert …
    trotzdem beenden?“ wird nie erreicht. `hat_ungespeicherte_aenderungen()` ist weiter True,
    in der DB steht `None`.
  - Weil `_fehlerbild` (desktop_gemeinsam.py:775-780) gleiche Fehler am letzten Frame erkennt
    und `fehlerfenster_einrichten` (805-808) sie unterdrückt, erscheint beim Schließen bzw. beim
    zweiten Speicherklick gar keine Meldung mehr.
  - Fehler mitten in der Schleife: frühere Zeilen gespeichert, spätere still verloren.
  - Windows-Abmeldung: Ausnahme vor `manager.cancel()`, das Abmelden läuft weiter.
  - `_tab_gewechselt`: `_vorheriger_tab_index` wird nicht gesetzt, der neue Reiter lädt nicht neu.
- **Abgrenzung:** Kein Duplikat von V5 (Fortschritt.md:5448, Startnummern-Knöpfe, „nur
  `sqlite3.Error`“); hier wird gar nichts gefangen.
- **Vorschlag:** `except sqlite3.Error` um alle drei Schreibaufrufe, beim ersten Fehler einmal
  mit Klartext abbrechen (z. B. „Termin-Datei schreibgeschützt oder nicht erreichbar“), damit
  die vorhandene Nachfrage beim Beenden greift. Test: `eintragen_ergebnis` beim Schließen
  scheitern lassen, Fenster muss offen bleiben.
- **Gegenprüfung:** bestätigt, mittel. Seltene, aber realistische Auslöser; Folge ist stiller
  Verlust von Prüfungsergebnissen.

### Nr. 2 [mittel] Komma-Hinweis zeigt rohes HTML in der Statuszeile

- **Stelle:** `app.py:1396` (`status_label.setTextFormat(Qt.PlainText)`, S-1) und
  `app.py:1951-1954` (N6-Hinweis als `<span style=…>`).
- **Kategorie:** Korrektheit, Rückwärts-Regression.
- **Ablauf:** „45,5“ in ein Punktefeld tippen. Die Statuszeile zeigt wörtlich
  `<span style="color:#b56a00; font-weight:bold;">Nur ganze Punkte von 0 bis 60 eingeben
  (keine Kommazahlen).</span>`, weder orange noch fett. N6 („Hinweis wurde übersehen“) ist damit
  wirkungslos.
- **Herkunft (git):** N6 kam mit d2458c6 (1.0.40), das `PlainText` aus S-1 mit fcfbbb2 (1.0.41)
  und hat N6 unbemerkt außer Kraft gesetzt.
- **Weitere Punkte:** Der Kommentar „S-1: enthält Pfade/Namen“ in 1396 stimmt nicht, das Label
  zeigt nur feste Texte. Der Test `test_app_gui.py:4003` prüft nur `"font-weight:bold" in text`
  und schreibt den Fehler damit fest.
- **Vorschlag:** Laut Fortschritt.md:4129 steckt die Hervorhebung bewusst im Text, damit
  spätere Meldungen sie nicht erben. Ein Stylesheet müsste daher bei jedem anderen `setText`
  (1478, 2103, 2105) zurückgesetzt werden. Einfacher: eigenes Hinweis-Label, oder `RichText`
  nur für diesen festen Text. Test auf Klartext und Format umstellen.
- **Gegenprüfung:** bestätigt, mittel.

### Nr. 3 [niedrig] Infospalten editierbar, Tab-Navigation führt in die Tabelle

- **Stelle:** `app.py:1340` (kein `setEditTriggers(NoEditTriggers)`, anders als `app.py:351` im
  `TeilnehmerTab`), `app.py:1519-1522`.
- **Kategorie:** Qt, Korrektheit.
- **Ablauf:** Zelle Start-Nr. oder Name aktuell, Tippen öffnet einen Editor und überschreibt die
  Anzeige (Name zeigte danach „Z“ bzw. „3“). Nicht als ungespeichert erkannt, nicht gespeichert:
  Anzeige still verfälscht; eine falsche Start-Nr. kann zur Eintragung beim falschen Teilnehmer
  verleiten. Laut Prüfer landet Tab aus einem Punktefeld zuerst in der Tabelle selbst und erst
  nach 9–11 weiteren Tabs im nächsten Punktefeld.
- **Vorschlag:** `setEditTriggers(QTableWidget.NoEditTriggers)`; optional Tab-Reihenfolge nur
  über die Eingabefelder (`setTabKeyNavigation(False)` plus `setTabOrder`). Test: Infozellen nicht
  editierbar.
- **Gegenprüfung:** bestätigt, niedrig. Den Tab-Teil konnte sie offscreen nicht nachstellen
  (kein aktives Fenster); der Kern trägt auch ohne ihn.

### Nr. 4 [niedrig] Sortierung nach Name und Hund ordnet Umlaute nach Codepunkt

- **Stelle:** `app.py:1757-1763` (`.lower()`), schon in Teil 1 vorgemerkt.
- **Kategorie:** Korrektheit.
- **Nachgestellt:** Reihenfolge `Adler, ebert, Zorn, Älter, Ötzi`. Der Teilnehmer-Reiter sortiert
  nach Gebietsschema (`Älter < Zorn`).
- **Vorschlag:** Gemeinsamer Schlüssel, z. B. `QCollator(QLocale(QLocale.German))` oder
  NFD plus `casefold`, für die Spalten 1–3. Test mit Umlauten.
- **Gegenprüfung:** bestätigt, niedrig. Keine frühere Entscheidung in Fortschritt.md.

### Nr. 9 [niedrig] Testlücken

- Es fehlen Tests für: DB-Schreibfehler in `alle_speichern`, beim Schließen und beim Abmelden
  (Nr. 1); Darstellung des Komma-Hinweises (Nr. 2, der vorhandene Test prüft das Falsche);
  nicht editierbare Infozellen (Nr. 3); Umlaut-Sortierung (Nr. 4).
- **Gegenprüfung:** teilweise bestätigt, niedrig. Abgeschwächt auf optional: Tests mit vielen
  Zeilen (bisher nur 1–2 Teilnehmer); mit 40 bzw. 60 Teilnehmern fanden beide keinen
  waagerechten Scrollbalken, also reine Lücke ohne Fehler. Verworfen: Test zu „keine Teilnahme“
  (siehe Nr. 5).

### Nr. 5 [optional, vorher niedrig] Ungespeicherte Eingaben verschwinden ohne Hinweis bei Disziplinwechsel

- **Stelle:** `app.py:1516-1517`, `1545-1547`, `aktualisieren_eingaben_erhalten` (1824-1831).
- **Kategorie:** Datenintegrität.
- **Ablauf:** Punkte für ED Flächensuche eintragen, Reiter wechseln, „Jetzt speichern?“ mit
  „Nein“. Im Teilnehmer-Reiter Disziplin auf Trümmerfeld ändern, zurückwechseln: Eingabe weg,
  `hat_ungespeicherte_aenderungen()` False. `_verworfene_melden` meldet nur DQ/Abbruch.
- **Vorschlag:** Verworfene Übernahmen bei nicht mehr geltender Disziplin in die vorhandene
  Meldung „Eingaben verworfen“ aufnehmen, mit Test.
- **Gegenprüfung:** teilweise bestätigt, auf optional herabgestuft. Der Nutzer hat selbst das
  Speichern abgelehnt und die Disziplin geändert. Verworfen ist der Teil „keine Teilnahme“
  (siehe unten).

### Nr. 6 [optional] Stylesheets bei jedem Größenwechsel neu gesetzt, Tabelle bei Sortierung doppelt aufgebaut

- **Stelle:** `desktop_gemeinsam.py:326-328` (Mixin setzt das Stylesheet bei jedem Resize, auch
  bei gleicher pt-Zahl); `app.py:1653-1656` und 1734 (Tabellen-Stylesheet neu, je Aufruf ein
  neues `QLineEdit()`); `app.py:1455/1464-1465` (`_neu_laden` baut bei aktiver Sortierung
  zweimal auf).
- **Kategorie:** Qt-Leistung.
- **Messung:** Prüfer ca. 170 ms je Resize bei 60 Teilnehmern, 370 ms bei 150; Sortierung 1,2 s
  statt 0,5 s bei 200 Teilnehmern. Gegenprüfung offscreen mit 60 ED-Teilnehmern nur ca. 29 ms je
  Resize und 70 ms je Sortierklick (Prüferwerte vermutlich DK und echte Schriften).
- **Vorschlag:** Stylesheet/Schrift nur bei geänderter pt-Zahl setzen; Feldhöhe einmal bestimmen;
  in `_neu_laden` erst sortieren, dann einmal aufbauen.
- **Gegenprüfung:** am Code bestätigt, optional; Messwerte nicht in der Höhe nachvollzogen.

### Nr. 7 [optional] Kein Sortierpfeil in der Kopfzeile

- **Stelle:** `app.py:1366`, `1739-1748`.
- **Ist:** Die eigene Sortierung zeigt weder Spalte noch Richtung; der Teilnehmer-Reiter schon
  (über `setSortingEnabled`).
- **Vorschlag:** `setSortIndicatorShown(True)` und `setSortIndicator(spalte, Richtung)`.
- **Gegenprüfung:** bestätigt, optional.

### Nr. 8 [optional] Wartbarkeit (teilweise bestätigt)

- **Bestätigt:**
  - Überflüssige Aliase `_SUCHE_MAX` und `_ANZEIGE_MAX` (`app.py:1300f.`), nirgends sonst
    genutzt, auch nicht in Tests.
  - `_eingabe_hinweis` nicht in `__init__` angelegt (`getattr`-Krücke in 1958).
  - Falscher Kommentar in 1396 (gehört zu Nr. 2).

## Verworfene Teile

- **Nr. 5, Teil „keine Teilnahme“:** Das Entfallen der Eingaben ist dokumentiert und von Marco
  abgenommen (Fortschritt.md:3029, Docstring in 1830); den Hinweis hat er bewusst nur für
  DQ/Abbruch beschlossen.
- **Nr. 8, doppelte Grenzprüfung Desktop/Web** (`app.py:2070-2079`, `app_web.py:874-877`):
  gewollt laut Docstring von `db.pruefe_ergebnis_eingabe`; U5a hat nur die Konstanten
  zusammengelegt.
- **Nr. 8, `IntegrityError`-Zweig (2083) praktisch tot:** bewusst als Rückfallebene behalten
  (Fortschritt.md:3587).
- **Nr. 9, Test zu „keine Teilnahme“:** entfällt mit dem verworfenen Teil von Nr. 5.

## Ohne Befund geprüft (laut Prüfer)

`_punkte_validator` (nur ASCII-Ziffern), Übernahme nur echter Abweichungen (`_eingaben_je_id`)
auch beim Sortieren und Neuladen, Meldung bei zwischenzeitlich gespeichertem DQ, DQ/Abbruch
(Sperren, Leeren, Wiederherstellen; Punkte bleiben in der DB), halb ausgefüllte Disziplin wie im
Web, `removeCellWidget` beim Wechsel DK→ED, `blockSignals` beim Filter, Strg+S nur im Reiter,
`_ergebnis_spaltenbreiten_verteilen` und `_responsive_schriftgroesse`, kein waagerechter
Scrollbalken bei 40 Zeilen (1300 und 1700 px), Spaltenkonstanten, Meldungen als Klartext (S-1).

## Hinweise für spätere Teile

- **Teil 8:** `HauptFenster._termin_setzen` entfernt alte Reiter nur mit `removeTab`, ohne sie
  zu löschen. Nach drei Terminwechseln gibt es 4 `ErgebnisTab`-Instanzen, die Verweise auf
  geschlossene Verbindungen halten (nicht gegengeprüft).
- **Teil 9:** Die Duplikatunterdrückung in `fehlerfenster_einrichten` lässt einen wiederholten
  Speicherfehler ganz ohne Meldung (siehe Nr. 1).
