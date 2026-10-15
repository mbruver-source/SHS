# Desktop-Prüfung Teil 4: Auswertung, Übersicht und Zeitplan

- **Datum:** 14.10.2026
- **Commit:** 3d14c51 (Version 1.0.47; Programmcode seit 25f9572 unverändert)
- **Geprüft:**
  - `app.py`: `_fremdobjekte_melden`, `_vorname_nachname`, `_stechen_offen_bestaetigen`,
    `AuswertungTab`, `TeilnehmerUebersichtTab`, `ZeitplanTab`;
  - `desktop_dialoge.py`: `PruefungsblockDialog`, `PauseDialog`;
  - `desktop_gemeinsam.py`: `_zeitplan_pdf_exportieren`;
  - die dabei aufgerufenen Funktionen in `db.py` (Auswertung, Stechen, Zeitplan,
    Überschneidungen, Verteilung, Übersicht, Behältnisse), `shs_core.py` und `pdf_export.py`
    (`erstelle_ergebnisliste_pdf`, `erstelle_zeitplan_pdf`).
- **Ablauf:**
  - `desktop-pruefer` im Prüfmodus, danach Gegenprüfung durch einen zweiten `desktop-pruefer`.
  - Beide haben mit eigenen Skripten nachgestellt (PySide6 6.11, offscreen, bzw. reines `db`).
  - Vorhandene Tests grün: `test_bewertung_referenz` und `test_shs_core` 29 OK (1 übersprungen),
    GUI-Auswahl 15 passed.
- **Ergebnis:**
  - 9 Befunde gemeldet, alle bestätigt (Nr. 9 teilweise). Kein Sicherheitsbefund.
  - Die Gegenprüfung hat Nr. 1 von mittel auf niedrig und Nr. 5 von niedrig auf optional
    herabgestuft. Der Nebenpunkt von Nr. 2 und ein Teil von Nr. 9 sind optional.

| Schweregrad | Anzahl | Befunde |
|---|---|---|
| mittel | 0 | |
| niedrig | 5 | 1, 2, 3, 4, 9 |
| optional | 4 | 5, 6, 7, 8 |

**Stand mit Marco:** alle Befunde noch unbesprochen. Nr. 1 braucht vor einer Umsetzung eine
fachliche Entscheidung.

## Bestätigte Befunde

### Nr. 1 [niedrig, vorher mittel] Eine alte Stechen-Markierung entscheidet einen neuen Gleichstand ohne Hinweis

- **Stelle:** `shs_core.py:219–227` (`len(sieger) == 1`), `db.py:1288–1297` und `db.py:1674`,
  `app.py:2234–2265`; Hinweis und Rückfrage in `app.py:2399` bzw. `2143`
  (`all(... == "offen")`).
- **Kategorie:** Korrektheit, Datenintegrität.
- **Ablauf (von beiden nachgestellt):**
  1. Anna und Ben haben je 95 Punkte, über „Stechen-Sieger festlegen…“ wird Anna eingetragen.
  2. Danach wird Claras Ergebnis korrigiert oder nachgetragen (Ergebniserfassung oder
     Web-Rückimport), sie hat jetzt auch 95.
- **Ist:** `Anna 1. von 3 (nach Stechen)`, `Ben 2.`, `Clara 2.`; Clara hat nie am Stechen
  teilgenommen. Kein „Stechen nötig“, keine Rückfrage vor Rangliste/Ergebnisliste.
  `eintragen_ergebnis`, `setze_ergebnis_status` und der Rückimport lassen `stechen_sieger`
  stehen. Dasselbe gilt, wenn der Gleichstand wegfällt und später ein neuer mit der markierten
  Person entsteht. Referenztest c1b deckt nur „Gleichstand fällt weg“ ab.
- **Soll:** Ein Stechen gilt nur für die Gruppe, die es bestritten hat. Kommt jemand in die
  Spitzengruppe dazu, ist das Stechen wieder offen.
- **Abgrenzung (Gegenprüfung):** Laut Fortschritt.md:4398 hat Marco festgelegt, dass bei
  *demselben* wieder entstehenden Gleichstand der frühere Sieger gilt („so lassen“). Eine
  *gewachsene oder ausgetauschte* Gruppe ist ein anderer Fall, also kein Duplikat.
- **Vorschlag (mit Marco abzustimmen):**
  - (a) Bei jeder Ergebnis-/Statusänderung die Markierung der Leistungsklasse zurücksetzen.
    Laut Gegenprüfung widerspricht das Marcos Entscheidung zum Randfall.
  - (b) Die Stechen-Gruppe bzw. Punktzahl mitspeichern; `berechne_rangliste` erkennt die
    Markierung nur an, wenn die Spitzengruppe noch genau diese ist (neue Spalte nötig).
  - (c, Gegenprüfung) Auch die Verlierer markieren („Stechen verloren“). Wer ohne Markierung neu
    in die Spitzengruppe kommt, ergibt „offen“. Braucht eine Migration des CHECK `(0, 1)` in
    `db.py:179`.
  - Dazu ein Referenztest „Gruppe wächst“.
- **Gegenprüfung:** bestätigt, auf niedrig herabgestuft. Seltene Abfolge (erst Stechen, dann
  Korrektur mit neuem Gleichstand), verwandter Randfall bewusst hingenommen.

### Nr. 2 [niedrig] „Stechen-Sieger festlegen…“: bei gleichlautenden Einträgen wird der falsche Sieger gespeichert

- **Stelle:** `app.py:2242–2249` und `app.py:2263`.
- **Kategorie:** Korrektheit.
- **Ablauf (nachgestellt):** Max Muster startet mit Ali (Nr. 1) und Bello (Nr. 2) in derselben
  ED-LK, beide 95 Punkte. Die Auswahl zeigt zweimal
  `ED LK 1 Trümmerfeld: Max Muster (95 Punkte)`; `zuordnung[text]` wird überschrieben. Wahl des
  ersten Eintrags (Ali) speichert Bello (`{'Ali': 0, 'Bello': 1}`). Auch die Vorauswahl
  `aktuell` und der Hinweis „Stechen nötig in …: Max Muster, Max Muster“ sind mehrdeutig.
- **Vorschlag:** Hund und Start-Nr. in den Text aufnehmen („Max Muster mit Ali (Nr. 1,
  95 Punkte)“), auch im Hinweis; Zuordnung über `eintraege.index(auswahl)`.
- **Nebenpunkt [optional]:** Ohne festgelegten Sieger ist Index 0 vorausgewählt
  (`app.py:2250–2255`); ein schnelles Enter legt einen Sieger fest. Besser „Stechen noch offen“
  vorbelegen.
- **Gegenprüfung:** bestätigt, niedrig; Nebenpunkt optional.

### Nr. 3 [niedrig] Zeitplan-Start: nicht gespeicherte Eingabe wird ohne Hinweis verworfen, das PDF nutzt den alten Wert

- **Stelle:** `app.py:2549–2553`, `2670–2671`, `2887–2899`; `desktop_gemeinsam.py:180–204`;
  `_tab_gewechselt` (`app.py:4255f.`).
- **Kategorie:** Datenintegrität (verlorene Eingabe).
- **Ablauf (nachgestellt):**
  - A: „10:00“ eintippen, nicht auf „Startzeit speichern“ klicken. Dann Mindestabstand ändern,
    „Richter hinzufügen“, „Automatisch verteilen…“ oder Reiterwechsel: `aktualisieren()` setzt
    das Feld auf „09:00“ zurück, weil es keinen Fokus mehr hat.
  - B: „10:00“ eintippen und direkt „Zeitplan (PDF)…“: Feld zeigt 10:00, das PDF beginnt um 09:00
    (`berechne_zeitplan` liest aus der Datenbank).
  - Zusätzlich (Gegenprüfung): `returnPressed` ist nicht verbunden, Enter speichert nicht.
- **Vorschlag:** Bei `editingFinished`/`returnPressed` prüfen und speichern, wie beim
  Mindestabstand; mindestens vor PDF, Verteilung und Neuaufbau eine abweichende Eingabe erkennen
  und nachfragen.
- **Gegenprüfung:** bestätigt, niedrig.

### Nr. 4 [niedrig] Schreibfehler werden in Auswertung und Zeitplan teils nicht abgefangen

- **Stelle:** `app.py:2654–2663` (`showEvent`: `zeitplan_richter_aus_veranstaltung_anlegen`),
  `2705–2707` (`_mindestabstand_speichern`), `2897` (`_start_speichern`), `2264`
  (`setze_stechen_sieger`).
- **Kategorie:** Fehlerbehandlung.
- **Ablauf (nachgestellt):** Schreibgeschützte, aktuelle Termin-Datei öffnet sich normal
  (`init_db` schreibt nichts). Beim ersten Anzeigen des Zeitplans (Richter in den
  Veranstaltungsdaten, Plan leer) `OperationalError: attempt to write a readonly database` aus
  `showEvent`. Beim Mindestabstand dieselbe Ausnahme; das Feld zeigt 20, in der DB steht `None`,
  `in_transaction` ist True. Gleiches bei „database is locked“ oder abgezogenem Stick.
- **Ist:** Nur das allgemeine Fehlerfenster mit englischem Text; die Nachbaraktionen (z. B.
  `_richter_hinzufuegen`) nutzen `_db_fehler_anzeigen`. Uneinheitlich.
- **Vorschlag:** `except sqlite3.Error` mit `_db_fehler_anzeigen`; beim Mindestabstand das Feld
  unter `blockSignals` auf den gespeicherten Wert zurücksetzen.
- **Abgrenzung:** Teil 3 Nr. 1 hat dieselbe Ursache im `ErgebnisTab`; hier andere Stellen, keine
  verlorenen Eingaben. Zusammen umsetzen.
- **Gegenprüfung:** bestätigt, niedrig.

### Nr. 9 [niedrig, teils optional] Testlücken

- **Bestätigt (niedrig, jeweils mit der Umsetzung des Befunds):** kein Referenztest für eine
  wachsende Stechen-Gruppe (Nr. 1; c1b/c1c decken das nicht ab), keiner für gleichlautende
  Einträge (Nr. 2), keiner für `_start_speichern` und das Verwerfen der Eingabe (Nr. 3), keiner
  für Schreibfehler im Zeitplan (Nr. 4).
- **Abgeschwächt auf optional:** GUI-Tests für `_eintrag_verschieben`, `_eintrag_bearbeiten`,
  `_eintrag_entfernen`, `_richter_umbenennen`/`_loeschen`/`_verschieben`,
  `_pruefungsblock_hinzufuegen`, `_pause_hinzufuegen` ohne „bei allen“. Die Handler sind dünne
  Hüllen; die DB-Funktionen testet `TestZeitplan` (`test_db.py:2299–2372`, auch PostgreSQL).
- Ein Test zu Nr. 5 nur, wenn Nr. 5 umgesetzt wird.

### Nr. 5 [optional, vorher niedrig] Nach einem abgefangenen Datenbankfehler im Zeitplan bleibt die Transaktion offen

- **Stelle:** `db.py:1764–1928` (`umbenennen_`/`loesche_`/`verschiebe_zeitplan_richter`,
  `add_zeitplan_pruefungsblock`, `add_zeitplan_pause`,
  `aktualisiere_`/`loesche_`/`verschiebe_zeitplan_eintrag`, alle ohne `rollback`); Aufrufer
  `app.py:2904–3079` fangen `sqlite3.Error` ohne Rollback.
- **Kategorie:** Datenintegrität, Fehlerbehandlung.
- **Ablauf (nachgestellt):** Eine zweite Verbindung hält eine Lesetransaktion (z. B. zweite
  Programminstanz). `verschiebe_zeitplan_eintrag` scheitert beim `commit` mit „database is
  locked“, die Oberfläche meldet „nicht gespeichert“, `in_transaction` bleibt True. Die nächste
  harmlose Aktion (Richter umbenennen) committet den Tausch trotzdem. Ein halber Tausch ist nur
  bei einem E/A-Fehler genau zwischen zwei UPDATEs denkbar.
- **Vorschlag:** `try/except Exception: conn.rollback(); raise` in den Funktionen, wie in
  `add_zeitplan_pause_bei_allen` und `automatische_zeitplan_verteilung`, oder zentral im
  GUI-Fehlerpfad. Zusammen mit Teil 1 Nr. 7 und Nr. 4 umsetzen.
- **Gegenprüfung:** bestätigt, auf optional herabgestuft: gleiche Ursache wie Teil 1 Nr. 7
  (dort optional), seltener Auslöser, meist nur verspätet gespeicherte gewünschte Änderung.

### Nr. 6 [optional] Uhrzeit wird nicht vereinheitlicht

- **Stelle:** `app.py:2993–3005`, `2888–2897`; `desktop_dialoge.py:859–866`.
- **Ablauf:** Eingabe „9:20“ (`strptime` akzeptiert das); die Pause liegt korrekt um 09:20, aber
  wegen `"09:20" != "9:20"` erscheint „Die Pause beginnt nicht überall um 9:20: Anna:
  09:20 Uhr“. Startzeit „9:5“ wird ungeändert gespeichert (Berechnung stimmt trotzdem).
- **Vorschlag:** Nach der Prüfung mit `strftime("%H:%M")` vereinheitlichen.
- **Gegenprüfung:** bestätigt, optional.

### Nr. 7 [optional] Mindestabstand speichert und baut bei jedem Tastendruck neu auf

- **Stelle:** `app.py:2571`, `2705–2707`.
- **Ist:** „15“ eintippen ergibt 2 Schreibvorgänge und 2 Neuaufbauten (Zwischenwert 1); ein
  gehaltener Pfeil wiederholt das laufend. Bei schreibgeschützter Datei verstärkt das Nr. 4.
- **Vorschlag:** `setKeyboardTracking(False)` oder Speichern bei `editingFinished`.
- **Gegenprüfung:** bestätigt, optional.

### Nr. 8 [optional] Wartbarkeit, Kleinigkeiten

- `app.py:2295–2296`: `list_teilnehmer` zweimal gelesen.
- `app.py:2393–2394`: `stechen_gruppen(self._fertig)` zweimal berechnet.
- `app.py:3033–3038`: `_aktueller_eintrag` berechnet den ganzen Blockplan aller Richter für
  einen Eintrag.
- `app.py:2874`: unnötiges `getattr(self, "_konflikt_hinweise", {})`; besser in `__init__`.
- `desktop_dialoge.py:830–835`: `PauseDialog` legt `fuer_alle`/`uhrzeit` auch im
  Bearbeiten-Modus an, ohne Layout (laut Gegenprüfung kein Leck, nur Unordnung).
- **Gegenprüfung:** alle Einzelpunkte bestätigt, optional.

## Verworfene Befunde

Keine.

## Ohne Befund geprüft (laut Prüfer)

`_fremdobjekte_melden` (alle Aufrufer mit vorherigem `init_db`, Klartext, auf 10 Namen gekürzt);
Rich Text und Tooltips (Seitenleiste „Offene Starts“ mit `html.escape`, Tooltips über
`_klartext_tooltip`, PDF über `_p_wert`); Filter-Combo mit `blockSignals`, Lambdas binden
richtig, `deleteLater` beim Neuaufbau unkritisch; Rangliste (1,1,3), nB/DISQ/ABBR ohne Platz,
„von X“ mit K9-Hinweis, Rückfrage vor Druck bei offenem Stechen, LK-Filter; Übersicht und
Behältnisse (CHECK-Bedingungen); automatische Verteilung und „Pause bei allen“ mit Rollback;
Überschneidungsprüfung inklusive Mindestabstand 0.

## Hinweise für spätere Teile

- **Teil 7/8:** Eine schreibgeschützte Termin-Datei der aktuellen Version lässt sich normal
  öffnen, alle Schreibaktionen scheitern erst später, teils ungefangen. Eine Prüfung auf
  Schreibschutz beim Öffnen wäre sinnvoll (Teil 1 Nr. 2 betrifft nur den Import-Dialog).
- **Teil 5:** `TerminImportDialog` öffnet die Quell-Datei mit `init_db`
  (`desktop_dialoge.py:717`): fremde Trigger/Views werden aus der Quell-Datei entfernt und
  Migrationen hineingeschrieben, ohne H-1-Hinweis; die globale Liste `_ENTFERNTE_FREMDOBJEKTE`
  wird überschrieben (heute ohne Folge, aber eine Falle).
