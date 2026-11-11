# Desktop-Prüfung Teil 1: Teilnehmerliste

- **Datum:** 13.10.2026
- **Commit:** 25f9572 (Version 1.0.47)
- **Geprüft:**
  - `app.py`: Hilfen Z. 235–330 und `TeilnehmerTab`;
  - `desktop_dialoge.py`: `StartnummerTauschenDialog`, `TerminImportDialog`;
  - die dabei aufgerufenen Funktionen in `db.py` und `db_import.py`.
- **Ablauf:** `desktop-pruefer` im Prüfmodus, danach Gegenprüfung durch einen zweiten
  `desktop-pruefer`. Beide haben ihre Ergebnisse mit kleinen Skripten nachgestellt (PySide6 6.11
  lokal). Der Teilsatz der GUI-Tests für diesen Bereich ist grün (70 passed).
- **Ergebnis:** 8 Befunde bestätigt, davon Befund 2 nur teilweise. Es gibt keinen
  Sicherheitsbefund.

| Schweregrad | Anzahl |
|---|---|
| mittel | 1 |
| niedrig | 5 |
| optional | 2 |

**Stand mit Marco:** alle Befunde noch unbesprochen.

---

## 1. [mittel] Eigener Termin erscheint im Dialog „Aus anderem Termin importieren“, vorausgewählt

- **Ort:** `desktop_dialoge.py:668` (`t.pfad != aktueller_pfad`); aufgerufen aus `app.py:801`.
- **Kategorie:** Datenintegrität / Korrektheit.
- **Ablauf:**
  - Der Termin wurde über „Andere Datei öffnen…“ (`app.py:4452`) oder beim Anlegen über
    „Durchsuchen“ (`desktop_dialoge.py:1569`) geöffnet.
  - Qt liefert den Pfad dann mit `/`, `liste_termine()` dagegen mit `\`.
  - Der Vergleich als Zeichenkette schlägt deshalb fehl.
- **Ist:**
  - Der eigene Termin steht in der Liste, als neuester meist an erster Stelle und damit
    vorausgewählt, mit allen Teilnehmern angehakt.
  - Ein Klick auf OK legt alle Teilnehmer doppelt an, ohne Startnummer. Eine
    Dublettenprüfung gibt es bewusst nicht (Fix 21).
  - Danach wird sogar noch die Startnummern-Vergabe angeboten.
- **Soll:** Der geöffnete Termin wird immer ausgeschlossen (so laut Fortschritt.md:277 und
  Docstring).
- **Nachstellung:** In einem Temp-Ordner liegen zwei Termine, `alt.sqlite` und `eigen.sqlite`
  (neueres Datum). Den Dialog mit dem Pfad in `/`-Schreibweise öffnen: Die Liste lautet dann
  `['eigen.sqlite', 'alt.sqlite']`, und der eigene Termin ist vorausgewählt.
- **Vorschlag:**
  - Vergleich über `os.path.normcase(os.path.abspath(...))` auf beiden Seiten.
    `StartDialog._termin_loeschen` (`app.py:4424`) nutzt schon `abspath`.
  - Den Test `test_termin_import_dialog_eigener_termin_wird_ausgeschlossen`
    (`test_app_gui.py:3041`) um einen Fall mit `/`-Pfad und anderer Groß-/Kleinschreibung
    ergänzen.
- **Gegenprüfung:** bestätigt, Schweregrad mittel.

## 2. [niedrig] Import-Dialog scheitert an schreibgeschützten Termin-Dateien älterer Versionen

- **Ort:** `desktop_dialoge.py:717` (Quelle wird mit `init_db` geöffnet, also schreibend und
  migrierend). Der Konstruktor wird in `app.py:801` vor dem `try` aufgerufen.
- **Kategorie:** Fehlerbehandlung.
- **Ablauf:**
  - Im Termine-Ordner liegt eine schreibgeschützte Termin-Datei einer älteren Version, die
    noch migriert werden müsste. Sie ist der neueste andere Termin.
  - Der Nutzer klickt „Aus anderem Termin importieren…“.
- **Ist:**
  - `liste_termine` öffnet mit `mode=ro` und zeigt die Datei als lesbar an.
  - `init_db` wirft dann `OperationalError: attempt to write a readonly database`.
  - Steht die Datei an erster Stelle, passiert das schon im Konstruktor. Der Dialog öffnet sich
    nicht, es erscheint nur das allgemeine Fehlerfenster.
  - Schreibgeschützte Dateien mit aktuellem Schema sind nicht betroffen.
- **Soll:** Die Quelle wird nur gelesen. Lesefehler erscheinen als verständliche Meldung.
- **Vorschlag:**
  - Quelle mit `sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)` und `row_factory =
    sqlite3.Row` öffnen.
  - In `_termin_gewaehlt` `try/except sqlite3.Error` mit Meldung einbauen.
  - Test mit schreibgeschützter Altdatei.
- **Gegenprüfung:** teilweise bestätigt. Verworfen sind zwei Teilaspekte:
  - „Ein bloßer Blick migriert fremde Termine“: steht in Fortschritt.md:279 bereits als
    harmloser Nebeneffekt.
  - Überschreiben von `_ENTFERNTE_FREMDOBJEKTE`: hat keine sichtbare Folge.

## 3. [niedrig] Rückfrage „Teilnehmer löschen“ hat „Ja“ als Standardknopf

- **Ort:** `app.py:869`.
- **Kategorie:** Korrektheit (Bedienung, destruktive Aktion).
- **Ablauf:** Strg+A, dann „Löschen“, dann Enter.
- **Ist:** Ohne `defaultButton` hat „Ja“ den Fokus. Enter löscht alle sichtbaren Teilnehmer
  samt Ergebnissen unwiderruflich.
- **Vergleich:** Andere destruktive Rückfragen setzen „Nein“ als Vorgabe (`app.py:776`,
  `2930`, `2954`).
- **Soll:** Die Vorgabe ist „Nein“.
- **Vorschlag:**
  - `QMessageBox.Yes | QMessageBox.No, QMessageBox.No`.
  - Optional ein Test mit Enter auf der echten Box.
- **Hinweis für Teil 7:** `StartDialog._termin_loeschen` (`app.py:4432`) hat dasselbe Muster.
- **Gegenprüfung:** bestätigt, nachgemessen.

## 4. [niedrig] Meldungen mit Namenslisten werden höher als der Bildschirm

- **Ort:**
  - `app.py:259–268` (`_fehlende_startnummern_vergeben_mit_meldung`);
  - `app.py:307–318` (`_teilnehmerliste_importieren`).
- **Kategorie:** Korrektheit (sehr viele Teilnehmer).
- **Ablauf:** Zum Beispiel 50 ED-Teilnehmer ohne Startnummernbereich, dann „Fehlende
  Startnummern vergeben“. Oder dieselbe CSV wird erneut eingelesen, dann steht jede Zeile
  unter „bereits vorhanden“.
- **Ist:** Alle Namen werden ungekürzt aufgelistet. Bei 60 Zeilen ist das Fenster 1077 px hoch,
  verfügbar sind 816 px. Der OK-Knopf ist nicht sichtbar, Enter schließt die Meldung aber
  trotzdem.
- **Vergleich:** Die Lösch-Rückfrage kürzt bereits auf 15 Namen (`app.py:864`).
- **Soll:** Die Meldung bleibt bedienbar und alle Namen sind trotzdem einsehbar.
- **Vorschlag:**
  - Auf 15 Namen kürzen („… und N weitere“).
  - Die vollständige Liste per `setDetailedText` anbieten.
  - Für beide Stellen eine gemeinsame Hilfsfunktion.
- **Gegenprüfung:** bestätigt.

## 5. [niedrig] Dateiname des Bewertungsbogens übernimmt den Nachnamen ungefiltert

- **Ort:** `app.py:841`.
- **Kategorie:** Korrektheit.
- **Ablauf:** Nachname „Meier/Schulz“ (oder mit `:`, `?`, `"`, `*`), dann
  „Bewertungsbogen (PDF)…“.
- **Ist:**
  - `QFileDialog` liest `Bewertungsbogen_5_Meier/Schulz.pdf` als Ordner plus Datei.
  - Der Dialog startet deshalb in einem fremden Ordner.
  - Wird dort gespeichert, setzt `_pdf_speicherort_waehlen` (`desktop_gemeinsam.py:168`)
    den gemeinsamen Ablageort dorthin. Alle weiteren PDF-Exporte des Termins landen dann auch
    dort.
  - Bei `:` und ähnlichen Zeichen meldet Windows einen ungültigen Dateinamen.
- **Soll:** Der Vorschlag ist immer ein gültiger, flacher Dateiname im Ausdrucke-Ordner.
- **Vorschlag:**
  - `re.sub(r'[\\/:*?"<>|]+', "-", nachname).strip(" .")`, wie bei `dateiname_vorschlagen`
    bzw. `app.py:3488f.`.
  - Dazu ein Test.
- **Gegenprüfung:** bestätigt. Kein Sicherheitsproblem, da der Nutzer den Dialog bestätigt.
  Niedrig ist die Obergrenze.

## 6. [niedrig] Import aus anderem Termin prüft die angebotenen Prüfungen nicht

- **Ort:** `db_import.py:696–744`, `app.py:815–821`. Gegenstelle ist `Architektur.md` um
  Z. 104: „alle Wege prüfen die angebotenen Prüfungen (`_angebot_pruefen`)“.
- **Kategorie:** Korrektheit / Doku.
- **Ablauf:** Import aus dem Vorjahrestermin mit Teilnehmern in einer Prüfung, die der
  aktuelle Termin nicht anbietet.
- **Ist:**
  - Die Teilnehmer werden ohne Hinweis angelegt.
  - Bei der Startnummernvergabe erscheinen sie nur unter „kein Bereich eingetragen“.
  - CSV, OMA und PDF lehnen solche Teilnehmer dagegen ab (U4/K8).
- **Soll / Vorschlag:** Mit Marco klären. Entweder ein Hinweis nach dem Import („N Teilnehmer
  in hier nicht angebotenen Prüfungen: … bitte LK anpassen“) plus Test, oder `Architektur.md`
  korrigieren. Ablehnen wäre hier eher falsch, weil Art/LK nach dem Import bewusst
  anpassbar sind.
- **Gegenprüfung:** bestätigt. Die Entscheidung U4/K8 betraf nur PDF, CSV und OMA.

## 7. [optional] `tausche_startnummern` ohne Rollback

- **Ort:** `db.py:1097–1114`; Aufrufer `app.py:678–682`, `710–714`.
- **Kategorie:** Datenintegrität.
- **Ist:**
  - Anders als `startnummern_zuruecksetzen` und `fehlende_startnummern_vergeben` gibt es kein
    `try/except: rollback`.
  - Bei einem `OperationalError` (z. B. Ein-/Ausgabefehler) nach dem ersten UPDATE bliebe die
    Transaktion offen. Ein späterer Commit würde dann den halben Tausch speichern.
  - Ein `IntegrityError` ist wegen der NULL-Zwischenstufe praktisch nicht erreichbar.
- **Vorschlag:** `try/except Exception: conn.rollback(); raise`, wie bei den Nachbarfunktionen.
- **Gegenprüfung:** bestätigt. Es geht um Einheitlichkeit.

## 8. [optional] Veraltete Kommentare und Restcode in `TeilnehmerTab`

- **Ort:** `app.py:344–345`, `636`, `661`, `671–675`/`693–697`, `930–931`;
  `test_app_gui.py:2789`.
- **Kategorie:** Wartbarkeit.
- **Ist:**
  - Die Kommentare zu `_teilnehmer_ids` und `_teilnehmer_je_zeile` stimmen nicht mehr. Beide
    Listen stehen in DB-Reihenfolge, und der Filter nutzt `_teilnehmer_je_id`.
  - `_teilnehmer_ids` wird nur noch vom Test gelesen. Dessen Zuordnung Zeile → ID stimmt nach
    einer Sortierung nicht mehr.
  - In `_teilnehmer_bearbeiten` und `_startnummer_tauschen` steht noch ein nacktes `next(...)`,
    das bei einem gelöschten Teilnehmer eine `StopIteration` werfen kann. Praktisch ist das
    kaum erreichbar. `_teilnahme_umschalten` wurde bereits auf `get_teilnehmer` umgestellt.
  - Der Text „Nichts zu tauschen“ steht doppelt.
- **Vorschlag:**
  - `_teilnehmer_ids` entfernen; der Test wählt die Zeile dann über die UserRole.
  - Die Kommentare korrigieren.
  - Beide `next(...)` auf `get_teilnehmer` umstellen.
  - Den Meldungstext zusammenführen.
- **Gegenprüfung:** bestätigt.

---

## Hinweis für Teil 3 (vorgemerkt)

`ErgebnisTab._sortierschluessel_fuer_zeile` (`app.py:1759`) sortiert Namen mit `.lower()`,
also nach Codepunkten: „Ötzi“ landet hinter „Zorn“. Der Teilnehmer-Reiter sortiert dagegen nach
Gebietsschema. Die Gegenprüfung hat das bestätigt.

## Ohne Befund geprüft

- **Klartext:** Labels, Tooltips, Combo- und Listeneinträge (S-1).
- **Signale:** Reihenfolge der Verbindungen, `blockSignals` beim Neuaufbau des Filters.
- **Sortierung und Auswahl:** Startsortierung, Erhalt nach `aktualisieren()`, ausgeblendete
  Markierungen.
- **Startnummern:** Transaktionen bei Zurücksetzen und Vergabe.
- **Web-Abgleich:** Ein Tausch wird bei `importiere_ergebnisse_nach_startnummer` erkannt.
- **Speicher:** keine angesammelten Dialog-Kinder.
- **Geschwindigkeit:** 0,55 s bei 400 Markierungen.
- **Bereits entschieden, nicht gemeldet:** Anzahl in der Zurücksetzen-Rückfrage (B), nur
  `sqlite3.Error` (V5), fehlender Vermerk „keine Teilnahme“ im Import, keine Dublettenprüfung,
  Filter „Unbekannte Prüfung“ (A).
