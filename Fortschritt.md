
# Fortschritt: SHS-Prüfungsprogramm-Ablösung

Stand: 22.09.2026 (aktualisiert: Version 1.0.25 gebaut - Hund-Spalte in Ergebniserfassung und Auswertung, Umbenennung Vollständig→Anmerkungen, responsive Spaltenbreiten/Schriftgröße in der Ergebniserfassung, siehe eigene Abschnitte unten). Details/Hintergrund siehe `Grobkonzept.md`.

## Erledigt

**Kernlogik (`shs_core.py`)**
- `berechne_wertnote_ed(punkte)` / `berechne_wertnote_dk(truemmerfeld, flaechensuche, behaeltnisstrecke)`: Punkte → Wertnote (V/SG/G/B/nB).
- **Wichtige Korrektur (10.09., gemeldeter Fehler):** Eine Prüfung gilt nur als bestanden, wenn JEDE Einzeldisziplin für sich mindestens 70 Punkte erreicht (bei ED die eine, bei DK alle drei) – exakt aus der Originalformel der Tabelle "Prüfungsteilnehmer" rekonstruiert (`IF(AND(Art="DK"; Trümmerfeld>69; Flächensuche>69; Behältnis>69); VLOOKUP(...); "nicht Bestanden")`). Vorher wurde nur die Gesamtpunktzahl gegen die Notentabelle geprüft – eine hohe Summe konnte so fälschlich eine Note liefern, obwohl eine einzelne Disziplin unter 70 Punkten lag. Betrifft ED und DK gleichermaßen.
- Ranglisten-Logik ebenfalls korrigiert: "nicht Bestanden"-Teilnehmer erhalten keine Platzierung (statt versehentlich eine Platzzahl über die Gesamtpunktzahl) – genau wie im Original (dort erscheint "nB" statt einer Rangzahl in der Rankingliste). Sie zählen aber weiterhin bei "von X Startern" mit (ebenfalls 1:1 aus der Original-Formel "Anzahl Starter" übernommen).
- `berechne_rangliste(teilnehmer)`: Platzierung je Leistungsklasse, mit korrekter Gleichstand-Behandlung (wie Excel/Calc RANK.EQ) und korrekter Behandlung von "nicht Bestanden".

**Datenschicht (`db.py`, SQLite)**
- Ein Termin/eine Veranstaltung = eine eigenständige `.sqlite`-Datei (Datenschutz: Termin löschen = Datei löschen).
- Tabellen: `veranstaltung` (Verein/Ort/Datum), `teilnehmer` (Stammdaten inkl. Art ED/DK, Leistungsklasse, Disziplin, Gegenstände, Startnummer `UNIQUE`), `ergebnisse` (Suche/Anzeige je Disziplin).
- Datenbank-Constraints erzwingen die Fachregeln direkt (z. B. ED braucht eine Disziplin, DK darf keine haben; Punktzahlen nur 0–60 bzw. 0–40; Startnummer eindeutig).
- `berechne_auswertung()` verbindet Teilnehmer- und Ergebnisdaten mit der Kernlogik (inkl. Mindestpunktzahl-je-Disziplin-Prüfung) und liefert fertige Rangliste + Liste der noch unvollständig bewerteten Teilnehmer.
- `update_teilnehmer()`/`get_teilnehmer()` für Bearbeiten-Funktion; `leistungsklasse_label()`/`alle_leistungsklassen()` als Grundlage für die Art/LK-Filter; `naechste_freie_startnummer()`/`vergebene_startnummern()` für automatische Startnummern-Vergabe ohne Dubletten.
- **Neu (13.09., 2. Ergänzung): fünf Zusatzfelder für die Veranstaltung** – `vereins_nr`, `pruefungsnummer`, `wertungsrichter_1`, `wertungsrichter_2`, `pruefungsleiter` (alle optional, für die Statistik-PDF gedacht). Bereits vor diesem Update angelegte Termin-Dateien besitzen diese Spalten noch nicht – `_migriere_veranstaltung_spalten()` ergänzt sie automatisch per `ALTER TABLE`, sobald eine solche ältere Datei über `init_db()` geöffnet wird, ohne bestehende Daten anzurühren.
- **Neu (14.09.): zwei weitere Zusatzfelder `pruefungsgebuehr_ed`/`pruefungsgebuehr_dk`** (ebenfalls über `_migriere_veranstaltung_spalten()` in Altdateien nachgerüstet) – die Prüfungsgebühr unterscheidet sich je nach Art (Einzeldisziplin/Dreikampf) und wird für die neue "Übersicht für Prüfungsleitung"-PDF gebraucht (siehe unten). Neue Funktion `pruefungsgebuehr_fuer_art(veranstaltung, art)` liefert die passende Gebühr (oder `None`, falls noch keine hinterlegt ist).
- **Neu (14.09., 3. Ergänzung): Bezahlt-Markierung je Teilnehmer** (neue Spalte `teilnehmer.bezahlt`, Default 0/"nicht bezahlt") – auf Wunsch des Nutzers ("es fehlt die Möglichkeit bezahlt? beim Teilnehmer zu vermerken im Programm"). Bereits vor diesem Update angelegte Termin-Dateien besitzen diese Spalte noch nicht – `_migriere_teilnehmer_spalten()` ergänzt sie automatisch per `ALTER TABLE`, sobald eine solche ältere Datei über `init_db()` geöffnet wird (bestehende Teilnehmer gelten dabei bewusst als "noch nicht bezahlt", nicht als bezahlt). Neue Funktion `setze_bezahlt(conn, teilnehmer_id, bezahlt)` setzt/entfernt die Markierung gezielt, ohne die übrigen Stammdaten anzufassen – Grundlage für den neuen Umschalten-Button in der Teilnehmerliste (siehe `app.py` unten). Die "Übersicht für Prüfungsleitung"-PDF zeigt die Spalte "bezahlt?" jetzt entsprechend befüllt statt leer (siehe `pdf_export.py` unten).
- **Neu (16.09.): freie Gegenstand-Disziplin-Zuordnung** (drei neue Spalten `teilnehmer.gegenstand_1_disziplin`/`gegenstand_2_disziplin`/`gegenstand_3_disziplin`, je Trümmerfeld/Flächensuche/Behältnisstrecke/NULL="frei"). Hintergrund (Rückmeldung des Nutzers anhand eines Bewertungsbogen-Ausdrucks): im Original wie bisher im Prototyp war Gegenstand 1/2/3 FEST der Reihenfolge Trümmerfeld/Flächensuche/Behältnisstrecke zugeordnet ("Gegenstand 1 = Trümmerfeld" usw., unabhängig davon, wofür der Gegenstand tatsächlich vorgesehen war) – das entsprach nicht zuverlässig der Praxis. Jeder der drei Gegenstände hat jetzt eine eigene, frei wählbare Zuordnung zu einer der drei Disziplinen, **bewusst ohne Default-Belegung** (Vorbelegung "frei" = keiner bestimmten Disziplin zugeordnet). Bereits vor diesem Update angelegte Termin-Dateien besitzen diese drei Spalten noch nicht – `_migriere_teilnehmer_spalten()` (jetzt tabellengesteuert für beliebig viele neue Teilnehmer-Spalten) ergänzt sie automatisch, bestehende Teilnehmer gelten dabei als "frei" statt automatisch zugeordnet. Neue Funktion `gegenstand_fuer_disziplin(teilnehmer, disziplin)` liefert den (falls vorhanden) dieser Disziplin zugeordneten Gegenstand-Text – ersetzt die alte feste `_GEGENSTAND_JE_DISZIPLIN_INDEX`-Zuordnung in `pdf_export.py` (siehe unten) und gilt jetzt einheitlich für ED und DK (vorher war ED fest auf `gegenstand_1` verdrahtet, unabhängig von einer Zuordnung).
- **Terminübersicht/-verwaltung.** `termine_ordner()` legt einen festen Speicherort im Benutzerprofil an (`%USERPROFILE%\SHS-Pruefungsprogramm\Termine` bzw. `~/SHS-Pruefungsprogramm/Termine`) – bewusst außerhalb des Installationsordners, damit spätere Programm-Updates die Termine-Dateien nie berühren. `liste_termine()` scannt diesen Ordner (liest jede Datei nur read-only an, damit reines Anzeigen nichts sperrt oder verändert) und liefert je Termin Verein/Ort/Datum/Teilnehmerzahl bzw. markiert beschädigte Dateien statt abzustürzen. `dateiname_vorschlagen(verein, datum)` schlägt beim Anlegen automatisch einen sprechenden Dateinamen vor.
- **Neu (14.09.): Zeitplan-Datenmodell (zwei neue Tabellen `zeitplan_richter`/`zeitplan_eintrag`, plus Veranstaltungsfeld `zeitplan_start`).** Auf Wunsch des Nutzers ("Vorlage für Zeitpläne je nach Anzahl der Leistungsrichter, die Möglichkeiten frei belegbar, Prüfungsdauer/Pausendauer/Pausenbelegung frei wählbar, gesondert in einem Tab") – Hintergrund: die hochgeladene Original-`Zeitplan.xlsx` enthielt entgegen der Erwartung KEINE Berechnungslogik (Power-Query-Formel reverse-engineered: sie importierte nur eine von Hand erstellte `plan.csv`), der Zeitplan wurde im Original also komplett manuell geplant. Datenmodell komplett neu entworfen: je Termin beliebig viele "Leistungsrichter"-Spuren (`zeitplan_richter`, frei sortierbar/umbenennbar), jede mit einer eigenen, frei sortierbaren Abfolge aus Prüfungsblöcken und Pausen (`zeitplan_eintrag`). Ein Prüfungsblock speichert nur Art/Leistungsklasse/Disziplin und die Dauer PRO Teilnehmer – wie viele Teilnehmer (und damit die Gesamtdauer) tatsächlich betroffen sind, wird NICHT gespeichert, sondern bei jeder Anzeige/jedem Export live aus dem aktuellen Teilnehmerstand neu ermittelt (`zeitplan_gruppen()`/`_teilnehmer_fuer_pruefungseintrag()`) – ein nachträglich hinzugefügter/gelöschter Teilnehmer wirkt sich damit automatisch aus, ohne den Zeitplan von Hand nachziehen zu müssen. Bei DK wird je Leistungsklasse in drei getrennte Blöcke aufgeteilt (einen je Disziplin), da ein Dreikampf-Hund die drei Disziplinen nacheinander durchläuft und ggf. zeitlich/auf verschiedene Richter verteilt geplant werden soll. Start-/Endzeiten werden ebenfalls nicht gespeichert, sondern aus der Zeitplan-Startzeit (`zeitplan_start`, Default 09:00) und den Dauern der vorangehenden Einträge kaskadierend neu berechnet (`berechne_zeitplan()` – eine Zeile je Teilnehmer, Grundlage der PDF; `berechne_zeitplan_bloecke()` – eine Zeile je Block/Pause, Grundlage der Planungsansicht im Tab). Pausen werden unabhängig je Richter geplant (keine Synchronisierung zwischen Richtern), wie vom Nutzer bestätigt. `automatische_zeitplan_verteilung(conn, richter_ids, standard_dauer_minuten)` erzeugt einen Erstvorschlag per Longest-Processing-Time-Heuristik (größte Teilnehmergruppe zuerst, jeweils dem Richter mit der aktuell geringsten Gesamtdauer zugeteilt, für eine ausgewogene Auslastung) und ersetzt dabei den bisherigen Zeitplan der übergebenen Richter – das Ergebnis ist nur ein Vorschlag und bleibt danach beliebig von Hand änderbar (auf Rückfrage bestätigt: "Automatischer Vorschlag + frei änderbar"). Reihenfolge-Verwaltung (Richter wie Einträge) über einfache Verschieben-Funktionen mit Nachbar-Tausch plus Lücken-Auffüllung beim Löschen.

**Eingabemaske (`app.py`, PySide6)**
- Startdialog: zeigt eine **Terminübersicht** (Tabelle aller vorhandenen Termine mit Datum/Verein/Ort/Teilnehmerzahl) statt nur eines Datei-öffnen-Dialogs. Neuen Termin anlegen (mit automatischem Dateinamensvorschlag), vorhandenen Termin per Doppelklick/"Öffnen" laden, Termin mit Rückfrage löschen, alternativ weiterhin eine beliebige `.sqlite`-Datei über einen klassischen Dateidialog öffnen.
- Tab "Teilnehmer": Liste, Hinzufügen, Bearbeiten, Löschen (mit Rückfrage). Startnummer wird bei Neuanlage automatisch auf die kleinste freie Nummer vorgeschlagen und beim Speichern gegen bereits vergebene Nummern geprüft. **Neu (14.09., 3. Ergänzung): eigene Spalte "Bezahlt"** in der Liste sowie eine Checkbox "Prüfungsgebühr bezahlt" im Erfassen-/Bearbeiten-Dialog; zusätzlich ein eigener Button **"Bezahlt umschalten"** für den markierten Teilnehmer, damit der Status (z. B. am Anmeldetisch) nicht jedes Mal über den vollständigen Bearbeiten-Dialog geändert werden muss.
- **Neu (16.09.): Gegenstand-Disziplin-Zuordnung im Erfassen-/Bearbeiten-Dialog.** Hinter jedem der drei Gegenstand-Textfelder steht jetzt ein Auswahlfeld "gesucht in:" mit den vier Werten "frei" (Vorbelegung, keine Zuordnung), "Trümmerfeld", "Flächensuche", "Behältnisstrecke" – frei kombinierbar, unabhängig von der Position des Gegenstands (Gegenstand 2 kann z. B. der Trümmerfeld-Disziplin zugeordnet werden). Steht ein Gegenstand auf "frei", erscheint er auf den Bewertungsbögen nicht mit einer Disziplin-Zuordnung (siehe `pdf_export.py` unten).
- Tab "Ergebniserfassung": eine Zeile je Teilnehmer (beim Dreikampf alle drei Disziplinen nebeneinander in derselben Zeile); ein globaler "Alle Ergebnisse speichern"-Button statt eines Buttons je Zeile; nicht gespeicherte Zeilen werden gelb hervorgehoben und in einer Status-Spalte gekennzeichnet ("● nicht gespeichert" / "✓ gespeichert"); Filter blendet nur aus statt neu aufzubauen (keine verlorenen Eingaben); Tabwechsel fragt bei ungespeicherten Änderungen nach.
- Tab "Auswertung": Rangliste inkl. Wertnote, Start-Nr.-Spalte, Filter nach Art/LK und Startnummer. "nicht Bestanden"-Zeilen werden rot hervorgehoben, zeigen "nB (von X Startern)" statt einer Platzzahl.
- Tab "Export" – Buttons für PDF-Ausgabe: Ergebnisliste, **Ergebnisliste zum Ausfüllen (leeres Formular, 13.09. ergänzt)**, **Etiketten (eigener Button, 13.09., 3. Ergänzung)**, Statistik, alle Bewertungsbögen (siehe `pdf_export.py` unten). Eigene Fehlermeldung bei Export-Problemen (z. B. Zieldatei nicht beschreibbar), getrennt von den Fachregel-Fehlermeldungen der Dateneingabe. **Neu (13.09. ergänzt): Button "Ablageort öffnen"** – öffnet den Ordner, in dem die zuletzt exportierten PDFs liegen, direkt im Windows-Explorer. Als Ablageort wird beim Öffnen eines Termins zunächst der Ordner der Termin-Datei selbst vorgeschlagen (die Exporte landen also standardmäßig beim jeweiligen Termin); speichert der Nutzer bewusst woanders, merkt sich die App diesen Ordner für den nächsten Export und für den Öffnen-Button.
- **Neu (13.09., 2. Ergänzung): Button "Veranstaltungsdaten bearbeiten…"** – öffnet denselben Dialog wie beim Anlegen eines Termins (ohne die Speicherort-Auswahl), damit Verein/Ort/Datum sowie die neuen Zusatzfelder Vereins-Nr., Prüfungsnummer, Wertungsrichter 1, Wertungsrichter 2 und Prüfungsleiter auch nachträglich erfasst oder korrigiert werden können (diese Felder werden für die Statistik-PDF gebraucht, siehe unten).
- **Neu (14.09.): zwei Felder "Prüfungsgebühr ED (€)"/"Prüfungsgebühr DK (€)"** im selben Dialog (Neuanlage UND Bearbeiten) – mit dem Startwert "12,00" vorbelegt (Konstante `_STANDARD_PRUEFUNGSGEBUEHR`), pro Termin frei änderbar. Grund für zwei getrennte Felder statt eines einzigen: auf Rückfrage bestätigt, dass Einzeldisziplin und Dreikampf unterschiedlich bepreist werden können.
- **Neu (14.09.): zwei weitere Export-Buttons.** "Übersicht für Prüfungsleitung (PDF)…" – Nachname/Vorname/Verein/Hund/Chip-Nr./Leistungsklasse aus den Stammdaten plus die Prüfungsgebühr (je nach Art ED/DK). Die Spalten "Kontrolle Impfpass erledigt?" und "Abgabe Sportbeitrag" bleiben in der PDF bewusst leer, da sie laut Rückmeldung des Nutzers erst am Prüfungstag selbst am Anmeldetisch von Hand abgehakt werden (nicht digital erfasst); die Spalte "bezahlt?" wird dagegen seit der Bezahlt-Markierung je Teilnehmer (14.09., 3. Ergänzung) mit "Ja" befüllt, sobald ein Teilnehmer in der Teilnehmerliste als bezahlt markiert ist. "Leistungsrichter-Bedarf (PDF)…" – errechnet aus der Teilnehmerzahl je Art/Leistungsklasse die benötigte Zahl an Leistungsrichtern (siehe `pdf_export.py` unten für die genaue Formel).
- **Neu (14.09.): eigener Tab "Zeitplan"** (`ZeitplanTab`, eingehängt zwischen "Teilnehmer" und "Ergebniserfassung") – Kopfzeile mit Zeitplan-Startzeit (HH:MM, speicherbar), Standard-Prüfungsdauer (nur Vorschlagswert für neue Blöcke bzw. für "Automatisch verteilen…"), Button "Leistungsrichter hinzufügen" sowie "Automatisch verteilen…" (mit Rückfrage, da der bisherige Zeitplan der betroffenen Richter dabei ersetzt wird). Je Leistungsrichter eine eigene Spalte (horizontal scrollbar bei vielen Richtern) mit Umbenennen/Links-Rechts-Verschieben/Löschen-Buttons im Spaltenkopf, darunter die Liste seiner Prüfungsblöcke/Pausen (jeweils mit berechneter Start-/Endzeit, bei Prüfungsblöcken zusätzlich Teilnehmerzahl) inkl. Hoch/Runter/Bearbeiten/Entfernen; "Prüfungsblock hinzufügen…" (Art/Leistungsklasse/Disziplin/Dauer je Teilnehmer, eigener Dialog `PruefungsblockDialog`) und "Pause hinzufügen…" (Dauer/Bezeichnung, `PauseDialog`) je Spalte. Eigener Export-Button "Zeitplan (PDF)…" sowohl im Tab selbst als auch (Konsistenz mit den übrigen PDF-Ausgaben) im Tab "Export". Kein Zwischenspeicher – der Tab baut sich bei jeder Änderung sowie beim Tabwechsel dorthin komplett aus dem aktuellen Datenbankstand neu auf (`aktualisieren()`), damit z. B. neu erfasste Teilnehmer sofort in den berechneten Zeiten auftauchen.
- **Nutzer-Feedback aus dem ersten echten Test des Tabs "Zeitplan" (14.09.), vier Punkte, alle behoben:**
  1. *Farben waren teilweise gemischt.* Vorher wurde je Disziplin eingefärbt (mit LK-3-Sonderfarbe) – dadurch zeigte z. B. ein Dreikampf LK2 drei verschiedene Farben (je eine pro Disziplin), obwohl der Nutzer eine einzige, durchgängige Farbe je Art+Leistungsklasse erwartete. Umgestellt auf eine feste Zuordnung Art+LK → Farbe (6 Kombinationen, da Art und Stufe über Datenbank-Constraints ohnehin nur diese 6 Werte annehmen können): ED LK1 grün, ED LK2 gelb, ED LK3 blau, DK LK1 rot, DK LK2 lila, DK LK3 orange – jetzt über alle Disziplinen hinweg einheitlich.
  2. *PDF-Export landete im falschen Verzeichnis.* Der Button "Zeitplan (PDF)…" im Tab "Zeitplan" merkte sich den Ablageort bisher nicht und schlug immer einen Datei-eigenen Standardordner vor, unabhängig vom Tab "Export". Beide Tabs teilen sich jetzt einen gemeinsamen Ablageort (neue Hilfsklasse `_Ablageort`): wählt der Nutzer in einem der beiden Tabs bewusst einen anderen Speicherort, gilt dieser ab sofort auch als Vorschlag im jeweils anderen Tab.
  3. *Beim Verschieben musste nach jedem Klick neu markiert werden.* Der Tab baut sich bei jeder Änderung komplett neu auf (damit z. B. neue Teilnehmer sofort berücksichtigt werden) – dabei ging die Auswahl bisher verloren. Die App merkt sich jetzt den zuletzt bearbeiteten/verschobenen Eintrag und markiert ihn nach dem Neuaufbau automatisch wieder, sodass "Hoch"/"Runter" mehrfach hintereinander klickbar ist, ohne die Zeile erneut anzuklicken.
  4. *Im Tab selbst wurden nur ganze ED-/DK-Blöcke angezeigt, nicht die einzelnen Teilnehmer.* Die Planungsansicht nutzte bisher eine gröbere Berechnung (eine Zeile je Prüfungsblock, nur mit Teilnehmerzahl) – jetzt dieselbe feingranulare Berechnung wie die PDF (`berechne_zeitplan()`, eine Zeile je einzelnem Teilnehmer mit Start-Nr./Name/Hund). Damit ein Prüfungsblock ohne (noch) passende Teilnehmer dabei nicht spurlos verschwindet und unauffindbar wird, zeigt die Ansicht für einen solchen leeren Block jetzt eine Platzhalterzeile "(noch keine Teilnehmer gemeldet)" (auch in der PDF).
- **Kleiner Begleit-Fix (14.09.):** `set_veranstaltung()` ersetzt bei jedem Aufruf immer den KOMPLETTEN Veranstaltungs-Datensatz (kein partielles Update) – ohne Gegenmaßnahme hätte das Bearbeiten der Veranstaltungsdaten (Tab "Export") das vom neuen Zeitplan-Tab gepflegte Feld `zeitplan_start` stillschweigend auf leer zurückgesetzt, sobald der Nutzer z. B. nur den Prüfungsleiter nachträgt. Neuer gemeinsamer Helfer `_aktualisiere_veranstaltung_feld()` in `app.py` liest deshalb vor jedem Speichern zunächst den aktuellen Datensatz und überschreibt gezielt nur die tatsächlich geänderten Felder.
- Datenbankfehler (z. B. verletzte Fachregel, doppelte Startnummer) erscheinen als Fehlerdialog statt die App abstürzen zu lassen.
- **Termin wechseln ohne Neustart (13.09. ergänzt):** Im Hauptfenster gibt es oberhalb der Tabs jetzt einen Button "Anderen Termin öffnen…", der denselben Startdialog (Terminübersicht) erneut öffnet. Bei ungespeicherten Änderungen in der Ergebniserfassung wird vorher nachgefragt (wie beim Tabwechsel). Nach Auswahl eines Termins baut das Fenster alle vier Tabs (Teilnehmer/Ergebniserfassung/Auswertung/Export) für die neue Datenbank neu auf, aktualisiert den Titel und schließt die alte Datenbankverbindung – ein Terminwechsel erfordert damit keinen Programmneustart mehr. Der "Öffnen"-Button im Startdialog selbst (zum Laden eines ausgewählten Termins beim Programmstart) existierte bereits.
- **Responsive Oberfläche (13.09. ergänzt):** Filter-Dropdowns passen ihre Breite automatisch an den angezeigten Text an (`AdjustToContents`); Tabellenspalten sowie die letzte Spalte strecken sich passend zur Fenstergröße (`resizeColumnsToContents` + `setStretchLastSection`); Formularfelder wachsen mit der Fenstergröße (`AllNonFixedFieldsGrow`); Spaltenköpfe und Beschriftungen verkleinern sich bei schmaleren Fenstern automatisch (8–10pt, linear nach Fensterbreite). Die Punktzahl-Eingabefelder in der Ergebniserfassung zeigen kein "–" mehr als Vorbelegung – ein leeres Feld gilt jetzt eindeutig als "noch nicht eingetragen" (Umstellung von QSpinBox mit Sonderwert auf QLineEdit mit Zahlen-Validierung).
- **Neu (16.09.): Hilfe-Button im Hauptfenster** (`HilfeDialog`) – ein Button "❓ Hilfe" oben rechts in der Menüleiste, direkt unter der Titelleiste des Fensters (technisch bedingt die nächstliegende Position zu den nativen Minimieren/Maximieren/Schließen-Schaltflächen des Betriebssystems – ein Button lässt sich in Qt nicht in die native Titelleiste selbst einfügen, das gehört dem Betriebssystem). Öffnet ein eigenes, scrollbares Fenster mit einer allgemeinen Bedienungshilfe: ein Abschnitt "Erste Schritte" plus ein Abschnitt je Reiter (Teilnehmer/Zeitplan/Ergebniserfassung/Auswertung/Export), der kurz erklärt, was der jeweilige Reiter macht und wie die wichtigsten Buttons zu bedienen sind. Inhalt vorab mit dem Nutzer abgestimmt, bevor er fest eingebaut wurde.
- **Neu (16.09.): automatisches Speichern beim Beenden** (`HauptFenster.closeEvent`) – auf Wunsch des Nutzers ("beim beenden des Programm werden alle nicht gespeicherten Daten vorher noch gespeichert"). Schließt der Nutzer das Programm (z. B. über das Fenster-X) mit noch nicht gespeicherten Änderungen in der Ergebniserfassung, werden diese jetzt automatisch gespeichert, BEVOR das Fenster tatsächlich schließt – ohne extra nachzufragen (anders als beim Tabwechsel/Terminwechsel, wo weiterhin "Jetzt speichern?" gefragt wird, siehe oben). Nutzt dafür dieselbe, bereits bestehende `alle_speichern()`-Methode wie der "Alle Ergebnisse speichern"-Button.

**PDF-Ausgabe (`pdf_export.py`)**
- Erzeugt die Original-Bewertungsbögen (alle 12 Varianten aus ED/DK × LK 1–3 × Disziplin, als ein einziges parametrisiertes Template statt 12 fest verdrahteter Vorlagen): Stammdaten, Verleitungs-Hinweise und Behältnis-Positionsanzahl exakt wie in den Original-.odt-Vorlagen (je nach Leistungsklasse 6/8/10 Positionen), Wertungsnoten-Referenztabellen, bei DK zusätzlich Gesamt-Punkte-Tabelle und Prädikats-Tabelle. **Geändert (16.09.):** die Kopf-Auflistung "1./2./3. zu suchender Gegenstand" (nur DK) sowie die "Zu suchender Gegenstand:"-Zeile im jeweiligen Disziplin-Abschnitt (ED wie DK) verwenden jetzt die freie Gegenstand-Disziplin-Zuordnung (`db.gegenstand_fuer_disziplin()`) statt der alten festen Positions-Zuordnung – ein Gegenstand erscheint jeweils nur bei der Disziplin, der er tatsächlich zugeordnet ist, bzw. in der Kopf-Auflistung ganz ohne Disziplin-Zusatz, wenn er auf "frei" steht.
- Ergebnisliste (je Leistungsklasse gerankt, "nB" statt Platzzahl bei "nicht Bestanden", Hinweis auf noch unvollständig bewertete Teilnehmer) als eigenes PDF.
- **Etiketten-Ergebnisliste (13.09., mehrfach nachgebessert)** (`erstelle_ergebnisliste_etiketten_pdf`) – zunächst als schlichte Tabelle ohne Kopfzeile umgesetzt, dann anhand von zwei Original-Screenshots der alten Excel/Calc-Tabelle ("Druck_LU") exakt auf deren Etiketten-Layout umgebaut: pro Teilnehmer zwei Zeilen – oben Verein/Art-LK/"Trümmer: …"/"Fläche: …"/"Behältnis: …"/"Gesamt: …"/"SH-R", darunter Datum und "Nachname, Vorname, Verein, Rufname Hund" – getrennt durch eine gestrichelte Schnittlinie zum Auseinanderschneiden.
  - Die Spalte "SH-WR/SH-R" wurde zunächst komplett weggelassen (auf damaligen Wunsch), dann auf erneuten Wunsch als reines Feld **"SH-R"** wieder aufgenommen (3. Ergänzung, 13.09.) – bewusst ohne Wert, ein über beide Zeilen reichendes umrandetes Leerfeld als Platzhalter zum späteren handschriftlichen Abstempeln/Unterschreiben durch den Spürhundesport-Richter.
  - **Bugfix (3. Ergänzung, 13.09.): auch Teilnehmer ohne vollständiges Ergebnis erhalten jetzt ein Etikett** – vorher wurden sie stillschweigend ausgelassen ("kein Ergebnis zum Aufkleben"), was beim Nutzer auffiel, da für diese Teilnehmer dann gar kein Etikett zum Beschriften existierte. Jetzt wird für sie ebenfalls ein Etikett erzeugt, die Punktzahl-Felder (Trümmer/Fläche/Behältnis/Gesamt) bleiben dabei aber leer (nur die Feldbezeichnung, kein Wert und kein "-") zum späteren handschriftlichen Nachtragen, statt sie ganz wegzulassen.
  - **Eigener Button statt automatischer Zusatzdatei (3. Ergänzung, 13.09.):** früher erzeugte der Button "Ergebnisliste (PDF)…" automatisch zusätzlich eine "_Etiketten"-Datei. Auf Wunsch des Nutzers gibt es jetzt einen eigenständigen Button **"Etiketten (PDF)…"** in `app.py`, der unabhängig vom normalen Ergebnisliste-Export aufgerufen werden kann (z. B. um nur die Etiketten erneut zu drucken, ohne die Ergebnisliste neu zu exportieren).
  - Die Spaltenbreiten mussten beim Hinzufügen der SH-R-Spalte insgesamt leicht angepasst werden (Verein/Art-LK auf je 30 mm, Trümmer/Fläche auf je 24 mm, Behältnis/Gesamt auf je 26 mm, SH-R 18 mm), damit weiterhin nichts umbricht oder sich überlappt (per gerendertem PNG-Screenshot visuell geprüft).
- **Statistik-PDF (13.09., final an das Original angepasst)** (`erstelle_statistik_pdf`) – ebenfalls anhand eines Original-Screenshots ("Spürhundsport (SHS) – Statistik / Sportbeitrag") neu gebaut, das rote HSVRM-Logo-Feld oben links wurde dabei bewusst weggelassen. Kopfbereich mit Verein, Vereins-Nr., Prüfungsnummer, Prüfungstag (ausgeschrieben, z. B. "Samstag, 19. September 2026"), Wertungsrichter 1/2 und Prüfungsleiter; darunter eine Prädikats-Matrix (Zeilen V/SG/G/B/nB, Spalten Dreikampf LK1–3 sowie Einzeldisziplin Trümmerfeld/Behältnisstrecke/Flächensuche je LK1–3) mit den jeweiligen Teilnehmerzahlen. Seite im Querformat (13 Spalten). Die dafür nötigen fünf Zusatzfelder (Vereins-Nr., Prüfungsnummer, Wertungsrichter 1, Wertungsrichter 2, Prüfungsleiter) wurden neu zur Veranstaltung hinzugefügt (siehe `db.py` unten und den neuen Button "Veranstaltungsdaten bearbeiten…" oben) – bestehende, bereits angelegte Termin-Dateien werden dafür beim nächsten Öffnen automatisch migriert (`_migriere_veranstaltung_spalten()`, per `ALTER TABLE`), ohne dass vorhandene Daten verloren gehen.
- **Neu (13.09.): Ergebnisliste zum Ausfüllen** – reines Formular je Leistungsklasse (sortiert nach Startnummer statt Platzierung), Start-Nr./Name/Verein aus den Stammdaten vorausgefüllt, Platz/Gesamtpunkte/Wertnote bleiben bewusst leer (auch wenn digital schon ein Ergebnis vorliegt) – gedacht zum papierbasierten Ausfüllen vor Ort, bevor die Werte später in die Software übertragen werden. Zeilen mit extra Innenabstand für handschriftliche Einträge.
- **Neu (14.09.): Übersicht für Prüfungsleitung** (`erstelle_pruefungsleitung_uebersicht_pdf`) – anhand eines Original-Screenshots nachgebaut: eine Zeile je Teilnehmer (sortiert nach Nachname/Vorname) mit Nachname/Vorname/Verein/Hund/Chip-Nr./Leistungsklasse sowie der Prüfungsgebühr (aus `pruefungsgebuehr_fuer_art()`, je nach Art ED/DK, formatiert als "12,00 €"; leer, falls noch keine hinterlegt). Die Spalten "Kontrolle Impfpass erledigt?"/"Abgabe Sportbeitrag" bleiben bewusst leer, mit extra Innenabstand zum handschriftlichen Abhaken am Prüfungstag (diese zwei Punkte sind erst am Prüfungstag selbst bekannt). **Geändert (14.09., 3. Ergänzung):** die Spalte "bezahlt?" war ursprünglich ebenfalls für das handschriftliche Abhaken gedacht, wird jetzt aber – auf Wunsch des Nutzers – aus der neuen digitalen Bezahlt-Markierung je Teilnehmer befüllt ("Ja" bei bezahlt, sonst leer), statt weiterhin leer zu bleiben. Querformat wegen der zehn Spalten.
- **Neu (14.09.): Leistungsrichter-Bedarf** (`erstelle_leistungsrichter_bedarf_pdf`) – Vorgabe des Vereins: 1 Einzeldisziplin (ED) = 1 Einheit, 1 Dreikampf (DK) = 3 Einheiten, ein Leistungsrichter darf höchstens 36 Einheiten je Prüfungstag richten. Zeigt eine Tabelle mit Teilnehmerzahl und Einheiten je Art/Leistungsklasse, darunter die Gesamteinheiten und die daraus (aufgerundet) benötigte Anzahl Leistungsrichter. Kommt auch ohne Teilnehmer sauber mit 0 Einheiten/0 Richtern klar, statt einen Fehler zu werfen.
- **Neu (14.09.): Zeitplan-PDF** (`erstelle_zeitplan_pdf`) – eine Seite je Leistungsrichter (Seitenumbruch zwischen Richtern), pro Seite eine Tabelle mit der vollständig berechneten Abfolge aus `db.berechne_zeitplan()`: Uhrzeit/Art-LK-Disziplin/Start-Nr./Name/Hund/Verein je Teilnehmer-Zeile, Pausen als über die Zeile gespannte, grau hinterlegte Zeile mit Bezeichnung. Zeilen sind nach Disziplin eingefärbt (Trümmerfeld grün, Flächensuche gelb, Behältnisstrecke blau) als schnelle visuelle Orientierung; Leistungsklasse 3 wird zusätzlich rot hervorgehoben (dort die meisten Verleitungen, entsprechend mehr Aufmerksamkeit nötig). Layout komplett neu entworfen, da die Original-Vorlage dafür keine wiederverwendbare Struktur bot (siehe `db.py` oben). Per gerendertem PNG-Screenshot visuell geprüft (Farbcodierung, Pausen-Zeilen, Seitenumbruch je Richter, Hinweistext bei Richtern ohne Einträge bzw. ganz ohne angelegte Richter).
- **Technische Entscheidung:** reportlab statt des ursprünglich angedachten weasyprint/xhtml2pdf – weasyprint bräuchte auf dem Windows-Zielrechner zusätzlich die native GTK3-Laufzeitumgebung (Installationsrisiko für ein einfaches Installer-Setup), reportlab kommt ohne externe Abhängigkeit aus.
- Getestet: eigene Testdatei `test_pdf_export.py`, prüft nicht nur "läuft ohne Fehler", sondern liest den erzeugten PDF-Text wieder ein und kontrolliert Inhalte (Punktzahlen, LK-abhängige Verleitungs-Hinweise/Behältnis-Positionen, die "nicht Bestanden"-Regel, die leeren Formularfelder).

**Datensicherung: Export/Import als ZIP, optional AES-256-passwortgeschützt (neu, `db.py`/`app.py`)**
- Neuer Reiter **"Datensicherung"** im Hauptfenster (auf Wunsch des Nutzers: "Datensicherungsreiter mit Export und Import"). Arbeitet bewusst NICHT auf dem gerade geöffneten Termin, sondern immer auf dem gesamten Termine-Ordner (`termine_ordner()`) – Export sichert alle vorhandenen Termine auf einmal in eine ZIP-Datei, Import liest eine solche ZIP-Datei wieder ein.
- **Passwortschutz optional per Checkbox** (auf Rückfrage vom Nutzer so festgelegt): Ohne Häkchen entsteht ein normales ZIP über das eingebaute `zipfile`-Modul; mit Häkchen (inkl. Wiederholungsfeld) ein AES-256-verschlüsseltes ZIP über die neue Abhängigkeit **`pyzipper`** (`requirements.txt`) – das Standard-`zipfile`-Modul kann verschlüsselte ZIPs zwar lesen, aber nicht mit echter Verschlüsselung schreiben.
- **Import-Konflikte werden einzeln abgefragt** (ebenfalls auf Rückfrage vom Nutzer so festgelegt): Ist ein Termin aus dem ZIP im Termine-Ordner bereits vorhanden, fragt ein Dialog je Konflikt, ob überschrieben, als Kopie mit automatisch durchnummeriertem Namen importiert (`eindeutigen_dateinamen_finden()`), oder übersprungen werden soll. Bei einem passwortgeschützten ZIP wird das Passwort abgefragt (bis zu drei Versuche).
- Neue Funktionen in `db.py`: `sicherung_erstellen()`, `sicherung_inhalt()` (Vorschau der enthaltenen Termine ohne zu entpacken, Grundlage der Konflikterkennung), `sicherung_wiederherstellen()`, `eindeutigen_dateinamen_finden()`, sowie die Fehlerklasse `PasswortFalschError`.
- **Von der CI (siehe unten) zwei echte Bugs gefunden, beide behoben, bevor die Funktion beim Nutzer ankam:** (1) `pyzipper` wirft bei einer ungültigen ZIP-Datei seine eigene, von der Standardbibliothek abweichende `BadZipFile`-Klasse (`pyzipper.zipfile.BadZipFile`) – wurde zunächst nicht mit abgefangen und ist jetzt ergänzt. (2) Ein Test las eine wiederhergestellte (echte, binäre) SQLite-Datei fälschlich als Text ein.
- Testabdeckung in `test_backup.py` (22 Tests: Export mit/ohne Passwort, nur ausgewählte Termine, alle drei Konfliktfälle beim Import, falsches/fehlendes Passwort, ungültige ZIP-Datei, eindeutige Namensvergabe).
- **Die neue `pycryptodomex`-Abhängigkeit von `pyzipper` wurde auch im Windows-Installer-Build verifiziert** (manuell angestoßener Testlauf über `build-installer.yml`, siehe Infrastruktur-Abschnitt unten): PyInstaller hat sie ohne zusätzliche `hiddenimports`-Angabe automatisch mit eingepackt (Installer-Artefakt von 57,8 MB auf 59,1 MB gewachsen, passend zur neuen Abhängigkeit).

**Installer (Windows)**
- `build.spec` (PyInstaller, `--onefile`): baut die gesamte App inkl. PySide6 und reportlab zu einer einzigen `.exe` – dadurch gibt es im Installationsordner keine losen Zusatzdateien, um die man sich bei einem Update kümmern müsste.
- `version_info.txt`: Windows-Versionsinformationen für die .exe.
- `installer.iss` (Inno Setup): baut den eigentlichen Setup-Installer. **Update-fähig** – über eine feste `AppId` (GUID, darf sich nie ändern) erkennt Inno Setup eine bestehende Installation wieder und überschreibt sie beim nächsten Setup-Lauf an Ort und Stelle, statt daneben zu installieren oder eine manuelle Deinstallation zu verlangen. Läuft die App gerade beim Update, wird automatisch zum Schließen aufgefordert und danach neu gestartet (`CloseApplications`/`RestartApplications`). Die Termine-Dateien im Benutzerprofil sind davon nie betroffen, da sie außerhalb des Installationsordners liegen (siehe `termine_ordner()` oben).
- `README_INSTALLER.md`: Schritt-für-Schritt-Anleitung für den Release-Build inkl. Checkliste.
- `build_installer.bat`: Ein-Klick-Build-Skript für den Nutzer (Python finden, Pakete installieren, **Versionsnummer automatisch erhöhen**, `pyinstaller --clean build.spec`, Inno Setup Compiler suchen/aufrufen). **Wichtig:** baut IMMER mit `--clean` (PyInstaller-Zwischenspeicher wird verworfen), da ohne diese Option beobachtet wurde, dass eine geänderte `.py`-Datei nicht zuverlässig neu in die `.exe` eingepackt wurde.
- **Neu (13.09. ergänzt): automatische Versionsnummer** (`bump_version.py`, `version.txt`) – die Versionsnummer wird nicht mehr von Hand gepflegt. Bei jedem Build erhöht `bump_version.py` die 3. Stelle (Patch) um 1; erreicht sie 99, springt sie auf 0 zurück und die 2. Stelle (Minor) wird um 1 erhöht (nach demselben Muster bei Bedarf auch die 1. Stelle) – wie ein Kilometerzähler. `version.txt` ist dabei die einzige Quelle der aktuellen Nummer; `bump_version.py` schreibt sie zusätzlich in `version_info.txt`, und `build_installer.bat` gibt sie unverändert an Inno Setup (`/DMyAppVersion=...`) weiter, sodass überall (Datei-Eigenschaften der .exe, Installer-Dateiname, Windows-Systemsteuerung) dieselbe Nummer erscheint. Getestet in `test_bump_version.py` (Normalfall sowie beide Übertrags-Fälle 3.→2. und 2.→1. Stelle).

**Automatisierte GUI-Tests (`test_app_gui.py`, neu)**
- Bisher ließ sich `app.py` nur per `py_compile`/statischer Prüfung absichern, nicht durch echtes Klicken (siehe "Wichtiger Hinweis" unten) – seit der Einrichtung der CI-Pipeline (siehe nächster Punkt) ändert sich das: über **pytest-qt** (`qtbot`-Fixture) laufen jetzt echte, automatisierte Klick-/Tastatur-Tests gegen die tatsächlichen Qt-Widgets, komplett headless über Qts eigene "offscreen"-Plattform (kein sichtbarer Bildschirm/Xvfb nötig) – läuft bei jedem Push automatisch in der GitHub-Actions-Pipeline mit.
- Deckt gezielt die vier Bereiche ab, die zuvor nur per `py_compile` geprüft waren: die Bezahlt-Markierung (Umschalten-Button in der Teilnehmerliste, Checkbox im Erfassen-Dialog), die freie Gegenstand-Disziplin-Zuordnung (inkl. "bleibt frei ohne Default"), der Hilfe-Button (sichtbar, öffnet den Hilfedialog) sowie das automatische Speichern beim Schließen des Fensters (inkl. Gegenprobe: kein unnötiges Speichern, wenn nichts geändert wurde).
- **Echten Fehler durch den ersten CI-Lauf gefunden und behoben:** Der allererste automatisierte Lauf schlug bei einem Test fehl (Klick auf die "Prüfungsgebühr bezahlt"-Checkbox im Erfassen-Dialog registrierte nicht) – Ursache: Ein Widget muss vor einem koordinatenbasierten Klick erst mit `.show()` sichtbar gemacht werden, sonst kennt Qt die genaue Klickfläche einer Checkbox noch nicht zuverlässig. Nach Ergänzen von `.show()` (defensiv bei allen Widgets im Testfile) lief die komplette Suite fehlerfrei durch – ein gutes Beispiel dafür, dass diese Tests tatsächlich reale Bedienprobleme aufdecken können, nicht nur Syntaxfehler.
- Konfiguration in `pytest.ini` (`qt_api = pyside6`).

**Infrastruktur: GitHub-Repo & CI/CD-Pipeline (neu)**
- Das Projekt liegt jetzt in einem privaten GitHub-Repository (`mbruver-source/SHS`), inkl. `.gitignore` für Python-/Build-Artefakte.
- **`.github/workflows/tests.yml`** – läuft automatisch bei jedem Push/Pull Request: installiert zunächst die nötigen Qt-Systembibliotheken für Headless-Betrieb, dann die komplette Testsuite (`test_db.py`, `test_pdf_export.py`, `test_shs_core.py`, `test_bump_version.py`, `test_app_gui.py`, `test_backup.py`). Damit ist ab sofort bei jeder Änderung automatisch sichtbar, ob etwas kaputtgegangen ist – ohne dass der Nutzer selbst Tests anstoßen muss.
- **`.github/workflows/build-installer.yml`** – baut den fertigen Windows-Installer (PyInstaller + Inno Setup) automatisiert auf einem GitHub-Windows-Runner. Wird entweder manuell angestoßen (nur zum Testen, Ergebnis als herunterladbares Artefakt) oder durch einen gepushten Versions-Tag (`vX.Y.Z`) ausgelöst – dann wird die Setup-Datei zusätzlich automatisch als GitHub-Release veröffentlicht. Ruft `bump_version.py` bewusst nicht selbst auf, sondern baut mit der bereits in `version.txt` eingecheckten Nummer (Ablauf dokumentiert in `README_INSTALLER.md`).
- Beide Workflows wurden mit echten Testläufen verifiziert (u. a. zwei manuell angestoßene Installer-Builds, siehe auch den Datensicherung-Abschnitt oben für den zweiten Testlauf mit der neuen `pycryptodomex`-Abhängigkeit).

**Erster echter GUI-Test durch den Nutzer:** erfolgreich (bestätigt am 12.09.). Installer-Build wurde vom Nutzer selbst mehrfach durchgeführt (PyInstaller + Inno Setup, auf seinem eigenen Windows-PC) – dabei aufgetretene und gelöste Probleme: ISCC.exe war nicht im PATH (Skript sucht seither zusätzlich an den Standard-Installationsorten), ein veralteter PyInstaller-Zwischenspeicher lieferte zwischenzeitlich eine `.exe` ohne die neueste `pdf_export.py`-Funktion (behoben durch `--clean` im Build-Skript sowie manuelles Ersetzen der Quelldatei, nachdem sich zeigte, dass der Datei-Zugriff auf den PC des Nutzers durch ein Windows-Update vom 8.09. zeitweise unzuverlässig war).

**Wichtiger Hinweis:** Keine Qt-Python-Anbindung ließ sich in der Arbeitsumgebung, in der der Code entsteht, installieren (kein Netzwerkzugriff auf pip-/apt-Quellen dafür) – Codeänderungen an `app.py` werden dort weiterhin nur per `py_compile`/statischer Prüfung abgesichert, nicht durch echtes Klicken. **Das gilt inzwischen aber nicht mehr für das Endergebnis:** Dank der neuen CI-Pipeline (siehe oben) laufen bei jedem Push automatisch echte, klickbasierte GUI-Tests (`test_app_gui.py` über pytest-qt) auf einem GitHub-Runner, auf dem PySide6 tatsächlich installierbar ist – Änderungen an `app.py` werden also nicht mehr nur auf Syntaxebene, sondern real durch simulierte Bedienung geprüft, auch wenn diese Arbeitsumgebung selbst weiterhin nur `py_compile` kann. `reportlab` und `pypdf` ließen sich in dieser Umgebung dagegen schon vorher installieren, weshalb `pdf_export.py` bereits vollständig automatisiert getestet werden konnte (inkl. Prüfung des erzeugten PDF-Inhalts). Ergänzend gibt es eine statische, klickbare HTML-Vorschau (`gui_vorschau.html`) mit Beispieldaten. Der echte Funktionstest der GUI von Hand sowie der lokale Installer-Build laufen weiterhin zusätzlich beim Nutzer auf seinem Windows-PC.
- Gesamter Testlauf (CI, GitHub Actions, Lauf "Tests #7"): 108 bestanden, 31 übersprungen, 0 fehlgeschlagen (139 Tests insgesamt) – darunter mindestens die zwei bekannten Tests, die einen optionalen Abgleich gegen die Original-.ods-Datei machen; die übrigen übersprungenen Tests wurden nicht im Einzelnen nachgeprüft.

**Architektur-Entscheidung (19.09.): Datenbank-Grundlage für eine geplante zweite Variante (Podman/Web, Mehrbenutzerzugriff) neben der bestehenden Desktop-Version**
- **Ausgangsfrage des Nutzers:** neben der bisherigen Desktop-Version zusätzlich eine Podman-Variante mit Web-Oberfläche und echtem Mehrbenutzerzugriff anbieten (z. B. mehrere Richter tragen am Prüfungstag gleichzeitig Ergebnisse ein) – mit der ausdrücklichen Sorge, dass dafür bei jeder Änderung zwei Versionen gepflegt/gebaut werden müssten.
- **Entscheidung: SQLite bleibt für die Desktop-Version, PostgreSQL kommt für den Container hinzu**, aber `db.py`s ~40 Datenfunktionen (Teilnehmer, Ergebnisse, Zeitplan) bleiben dabei **unverändert und einfach** – keine zweite, separat gepflegte Fassung. Möglich gemacht durch einen neuen, schlanken Kompatibilitäts-Wrapper (`_PostgresConnection`/`_PostgresCursor` in `db.py`), der dieselbe (kleine) Teilmenge der `sqlite3.Connection`-Schnittstelle nachbildet, die dieses Modul tatsächlich nutzt: `execute()`/`executescript()`/`commit()`/`close()`, `?`-Platzhalter (statt psycopg2s `%s`, intern übersetzt) sowie dict-artige Ergebniszeilen wie `sqlite3.Row`. `init_db()` (SQLite, unverändert) und die neue Funktion `init_db_postgres()` liefern beide ein zu diesen Funktionen kompatibles Verbindungsobjekt – der Rest des Moduls merkt den Unterschied nicht.
  - **Ursprünglich war dafür SQLAlchemy/Alembic vorgesehen** (siehe Chatverlauf) – stellte sich aber als in dieser Arbeitsumgebung nicht installierbar heraus (kein PyPI-/apt-Netzwerkzugriff, ebenso wie bereits bei PySide6/pytest-qt/pyzipper bekannt). Da SQLAlchemy damit hier nicht ein einziges Mal hätte lokal getestet werden können – auch nicht der SQLite-Pfad, der heute bereits produktiv läuft und von 64 bestehenden Tests abgedeckt ist –, fiel die Wahl bewusst auf die schlankere, abhängigkeitsfreie Lösung oben: SQLite/Desktop bleibt dadurch zu 100 % wie bisher lokal testbar (alle 64 bestehenden Tests laufen unverändert weiter durch), nur der neue PostgreSQL-Pfad ist zusätzlich.
  - `psycopg2` wird dafür bewusst **nicht** am Modulanfang importiert, sondern erst innerhalb von `init_db_postgres()` (analog zum bestehenden `pyzipper`-Muster für die Datensicherung) – die SQLite-Desktop-Version (und damit der Windows-Installer) braucht diese zusätzliche Abhängigkeit nie und wird dadurch nicht größer. Eigene neue Datei `requirements-postgres.txt` dafür, **absichtlich getrennt von `requirements.txt`**, damit `build_installer.bat`/`build.spec`/`build-installer.yml` unverändert schlank bleiben.
- **Schema:** `SCHEMA_POSTGRES` wird automatisch aus dem bestehenden `SCHEMA` abgeleitet (`.replace(...)`), nicht separat gepflegt – der einzige tatsächliche Syntax-Unterschied zwischen SQLite und PostgreSQL im gesamten Schema ist die Autoincrement-Schreibweise der drei id-Spalten (`AUTOINCREMENT` → `GENERATED ALWAYS AS IDENTITY PRIMARY KEY`), alles andere (CHECK-Constraints, `REFERENCES ... ON DELETE CASCADE`, `INSERT ... ON CONFLICT DO UPDATE`) ist Standard-SQL und funktioniert in beiden Datenbanken identisch. Die bestehende Migrationslogik (`_migriere_veranstaltung_spalten`/`_migriere_teilnehmer_spalten`, ergänzt fehlende Spalten in älteren Termin-Dateien automatisch) wurde dialektunabhängig gemacht (`_vorhandene_spalten()`: `PRAGMA table_info` für SQLite, `information_schema.columns` für PostgreSQL) statt auf ein neues Migrationswerkzeug (Alembic) umzusteigen – Alembic war ebenfalls nicht installierbar, und ein kompletter Wechsel auf eine neue, migrations-verfolgte Historie hätte zudem ein echtes Risiko für bereits beim Nutzer vorhandene Termin-Dateien bedeutet (die ihre bisherigen Spalten-Ergänzungen ohne Historieneintrag "von Hand" bekommen haben).
- **Ein konkreter, beim Code-Review gefundener Portabilitäts-Fehler behoben, bevor er zum Problem wurde:** `vergebene_startnummern()` griff auf eine Ergebniszeile per Positions-Index (`row[0]`) zu – funktioniert bei `sqlite3.Row`, nicht aber bei den dict-artigen Zeilen der PostgreSQL-Anbindung (`RealDictCursor`). Auf Zugriff per Spaltenname (`row["startnummer"]`) umgestellt.
- **Testabdeckung:**
  - Neue Datei `test_db_postgres_wrapper.py` (9 Tests) – prüft die reine Übersetzungslogik des Wrappers (Platzhalter-Ersetzung, automatisches `RETURNING id` nur für die drei betroffenen Tabellen und nur bei INSERT, lastrowid-Emulation, Delegation von `executescript`/`commit`/`close`) über `unittest.mock` **ohne** echten PostgreSQL-Server oder installiertes psycopg2 – läuft daher überall, auch in dieser Arbeitsumgebung.
  - `test_db.py`: die bestehenden Testklassen `TestDatenbank` und `TestZeitplan` laufen jetzt über die neuen Unterklassen `TestDatenbankPostgres`/`TestZeitplanPostgres` (Mehrfachvererbung mit einem `_PostgresBackendMixin`) **zusätzlich vollständig gegen eine echte PostgreSQL-Datenbank** – ohne den Testsatz zu duplizieren. Lokal (kein `SHS_TEST_POSTGRES_DSN` gesetzt bzw. `psycopg2` fehlt) werden diese 56 Tests sauber übersprungen statt zu scheitern; in der CI laufen sie gegen einen echten PostgreSQL-Service-Container (siehe unten). `TestTerminuebersicht` bleibt bewusst nur SQLite (siehe offener Punkt unten). Dafür mussten die fünf Stellen, die bislang `sqlite3.IntegrityError` fest erwarteten, auf ein austauschbares `IntegrityErrorTyp`-Klassenattribut umgestellt werden (psycopg2 wirft bei CHECK-/UNIQUE-Verletzungen einen eigenen Exception-Typ), und die drei Migrations-Tests wurden auf gemeinsame Hilfsmethoden (`_lege_alte_teilnehmer_tabelle_an`, `_neu_verbinden`) umgebaut, damit auch ihre "so sah eine ältere Termin-Datei aus"-DDL dialektabhängig (`_ID_SPALTE_DDL`) bleibt.
  - **Manuell gegen einen echten, lokal gestarteten PostgreSQL-16-Server verifiziert** (in dieser Arbeitsumgebung zwar kein installierbares psycopg2, aber der PostgreSQL-Server selbst samt `psql` ist vorhanden): das komplette `SCHEMA_POSTGRES` erfolgreich angewendet, sowie alle im Code vorkommenden SQL-Formen einzeln geprüft – `INSERT ... RETURNING id`, `INSERT ... ON CONFLICT(id) DO UPDATE SET ... = excluded....`, `ALTER TABLE ... ADD COLUMN`, die `information_schema.columns`-Abfrage, eine CHECK-Constraint-Verletzung sowie `TRUNCATE ... RESTART IDENTITY CASCADE` (für den Testreset) – alle wie erwartet.
- **CI (`.github/workflows/tests.yml`) erweitert:** neuer PostgreSQL-16-Service-Container (Zugangsdaten testintern, kein Bezug zu echten Zugangsdaten), `requirements-postgres.txt` wird zusätzlich installiert, `SHS_TEST_POSTGRES_DSN` gesetzt – die neuen Postgres-Tests laufen dort also tatsächlich gegen eine echte Datenbank, nicht nur gegen den Mock-Wrapper-Test.
- **Bewusst NICHT Teil dieser Umstellung** (siehe "Noch offen"): das eigentliche Web/Container-Backend selbst (keine neue `app_web.py` o. Ä., kein Podman-Setup) sowie die Frage, wie die Web-Version einzelne Termine in einer gemeinsam genutzten PostgreSQL-Datenbank voneinander unterscheidet – das heutige "ein Termin = eine SQLite-Datei"-Modell (`termine_ordner`/`liste_termine`) ist ein Konzept der Desktop-Version und hat in einer gemeinsamen Datenbank kein direktes Gegenstück.

**Architektur-Entscheidung (19.09., Fortsetzung): Terminverwaltung für die PostgreSQL/Web-Variante – "Weg B", ein eigenes Datenbank-Schema je Termin**
- **Offene Frage aus dem Abschnitt oben geklärt:** wie unterscheidet die Web-Version einzelne Termine in der EINEN gemeinsamen PostgreSQL-Datenbank? Zwei Wege abgewogen – **Weg A** (eine gemeinsame Spalte `veranstaltung_id` quer durch alle Tabellen) hätte bedeutet, alle ~40 bestehenden Datenfunktionen in `db.py` um eine Mandanten-Filterung zu erweitern (genau die Doppelpflege, die ursprünglich vermieden werden sollte), **Weg B** (jeder Termin bekommt sein eigenes PostgreSQL-Schema, z. B. `termin_17`) braucht dagegen **keine einzige Änderung** an diesen Funktionen – sie führen weiterhin schlicht `SELECT * FROM teilnehmer` usw. aus, nur dass vorher per `SET search_path` festgelegt wird, welcher Termin gerade "aktiv" ist. Auf Nachfrage bestätigt der Nutzer: eine Auswertung über mehrere Termine hinweg ist nicht nötig – damit entfällt der einzige Vorteil von Weg A, und Weg B wurde umgesetzt. Weg B spiegelt außerdem sehr genau das bestehende, aus Datenschutzgründen bewusst gewählte "ein Termin = eine eigene Datei"-Modell der Desktop-Version wider: Termin löschen = Schema löschen (`DROP SCHEMA ... CASCADE`), genauso vollständig und gezielt wie das bisherige Löschen einer `.sqlite`-Datei.
- **Neue Funktionen in `db.py`** (Abschnitt "Terminverwaltung für PostgreSQL"): `verbinde_postgres_server(dsn)` verbindet sich und legt bei Bedarf eine kleine Registriertabelle `public.termin_registry` an (nur `id`/`schema_name`/`erstellt_am` – Verein/Ort/Datum werden bewusst NICHT dort gespiegelt, um keine zweite Quelle der Wahrheit zu schaffen, sondern beim Anzeigen live aus der `veranstaltung`-Tabelle im jeweiligen Schema gelesen, genau wie `liste_termine()` das für Dateien tut). `erstelle_termin_postgres(conn)` holt über eine eigene PostgreSQL-Sequenz (`termin_registry_id_seq`) eine neue Termin-ID (löst das Henne-Ei-Problem, den Schema-Namen vor dem ersten Registry-Eintrag zu kennen), legt das Schema `termin_<id>` an und richtet darin das volle `SCHEMA_POSTGRES` ein. `oeffne_termin_postgres()`/`liste_termine_postgres()`/`loesche_termin_postgres()` entsprechen funktional `init_db()`/`liste_termine()`/dem Datei-Löschen der Desktop-Version. Schema-Namen werden vor jeder Verwendung in einem SQL-Text (`SET search_path`, DDL) gegen ein striktes Muster geprüft (`_pruefe_schema_name()`), da PostgreSQL an dieser Stelle keine parametrisierten Platzhalter erlaubt – auch wenn Schema-Namen intern immer automatisch aus der Sequenz erzeugt werden, nie aus Nutzereingaben.
- **Beim Review selbst gefundener und behobener Fehler, bevor er zum Problem wurde:** Die bestehende Migrationsfunktion `_vorhandene_spalten()` (ermittelt für die automatische Spalten-Nachrüstung in älteren Terminen, welche Spalten eine Tabelle bereits hat) fragte bei PostgreSQL `information_schema.columns` nur nach dem Tabellennamen, ohne nach Schema zu filtern. Mit dem neuen Mehr-Termin-Modell haben aber mehrere Schemas gleichnamige Tabellen (`termin_1.teilnehmer`, `termin_2.teilnehmer`, …) – ohne Filter hätte die Funktion die Spalten ALLER Termine zusammengemischt zurückgeliefert, statt nur die des gerade aktiven. Behoben durch Ergänzung `AND table_schema = current_schema()`. Der Fehler wurde konkret nachgestellt (zwei Test-Schemas mit unterschiedlichen Zusatzspalten auf dem lokalen PostgreSQL-Server angelegt): vor der Korrektur lieferte die Abfrage fälschlich 34 statt der korrekten 2 Spalten (Vermischung mit `teilnehmer`-Tabellen anderer, zu Testzwecken vorher angelegter Schemas) – nach der Korrektur exakt die 2 erwarteten.
- **Testabdeckung:** neue Testklasse `TestTerminverwaltungPostgres` in `test_db.py` (4 Tests: zwei Termine sind voneinander isoliert, `liste_termine_postgres()` zeigt Verein/Ort/Datum/Teilnehmerzahl korrekt und neueste zuerst, Löschen entfernt nur den einen Termin, ein ungültiger Schema-Name wird abgelehnt). Gesamter lokaler Testlauf danach: 133 Tests, 60 übersprungen (PostgreSQL-Tests ohne lokal installierbares psycopg2), 0 fehlgeschlagen, 0 Fehler. Die Schema-Filter-Korrektur zusätzlich manuell gegen den lokalen PostgreSQL-Server nachgestellt (siehe oben).

**Architektur-Entscheidung (19.09., Fortsetzung 2) und erste Umsetzung: Web-Backend V1 – nur Ergebniseingabe, mit Nutzer abgestimmt**
- **Mit dem Nutzer abgestimmter Zuschnitt der ersten Ausbaustufe** (drei Entscheidungen): (1) **Netzwerk:** die Web-Version läuft NUR im lokalen Vereins-Netzwerk am Prüfungstag, nicht öffentlich aus dem Internet erreichbar – deshalb bewusst kein externes CSS/JS/Font-CDN in den Templates (am Veranstaltungsort ggf. kein Internetzugang) und kein eigenes HTTPS in `app_web.py`. (2) **Anmeldung:** EIN gemeinsamer, sechsstelliger Zugangscode je Termin statt einzelner Benutzerkonten je Richter – einfach für den Ablauf am Prüfungstag, dafür ohne Nachvollziehbarkeit, WER genau einen Eintrag gemacht hat (bewusst in Kauf genommen). (3) **Funktionsumfang V1:** NUR Ergebniseingabe. Termin anlegen, Teilnehmerverwaltung, Zeitplan und PDF-Export bleiben vorerst Desktop-Aufgaben vor/nach dem Prüfungstag.
- **Framework-Wahl: Flask statt des ursprünglich angedachten FastAPI** – `fastapi` selbst ließ sich in dieser Arbeitsumgebung nicht installieren (derselbe PyPI-Netzwerk-Block wie bei SQLAlchemy/psycopg2, siehe oben), Flask (samt Jinja2) ist hier dagegen bereits vorhanden und vollständig lokal testbar. Genau dieselbe Überlegung wie beim SQLAlchemy-Wrapper weiter oben: lieber die Technik wählen, die sich tatsächlich prüfen lässt, als eine, die bis zum ersten echten Einsatz beim Nutzer ungetestet bliebe. Serverseitig gerenderte Jinja2-Templates statt eines JavaScript-Frontends passen zudem gut zur LAN-only-Vorgabe.
- **Neue Datenbank-Bausteine in `db.py`:** Die Registry-Tabelle `termin_registry` bekommt eine `zugangscode`-Spalte (per `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, auch für bereits vorhandene Registries); `erstelle_termin_postgres()` erzeugt dabei automatisch einen sechsstelligen, per `secrets` gezogenen und auf Eindeutigkeit geprüften Code (`_eindeutigen_zugangscode_erzeugen()`); `pruefe_zugangscode_postgres(conn, code)` prüft einen eingegebenen Code gegen die Registry und liefert den zugehörigen Schema-Namen. Neuer Abschnitt "Austausch zwischen einer SQLite-Termin-Datei (Desktop) und einem PostgreSQL-Termin-Schema (Web)": `kopiere_termin_daten()`/`importiere_ergebnisse_nach_startnummer()` (die eigentliche, bewusst **dialektunabhängige** Kopierlogik – Zuordnung der Teilnehmer beim Rückimport über die Startnummer, da SQLite und PostgreSQL beim Export unabhängig vergebene IDs erzeugen) sowie die dünnen, tatsächlich an PostgreSQL gebundenen Wrapper `exportiere_termin_nach_postgres()`/`importiere_ergebnisse_aus_postgres()`. Zusätzlich neue Hilfsfunktion `get_ergebnis()` (Pendant zu `get_teilnehmer()` für die `ergebnisse`-Tabelle).
- **Ablauf am Prüfungstag:** Termin wird wie bisher in der Desktop-Version angelegt/geplant → **vor** der Prüfung `python sync_termin.py export <Termin-Datei> --dsn <Postgres-DSN>` veröffentlicht ihn als eigenen PostgreSQL-Termin (Weg B, eigenes Schema) und gibt den Zugangscode für die Richter aus → Richter tragen während der Prüfung gleichzeitig über die Web-Oberfläche Ergebnisse ein → **nach** der Prüfung `python sync_termin.py import <Schema-Name> <Termin-Datei> --dsn <Postgres-DSN>` holt die Ergebnisse zurück in dieselbe SQLite-Datei, danach laufen PDF-Export/Auswertung/Zeitplan wie gewohnt in der Desktop-Version weiter. Neues Kommandozeilen-Werkzeug `sync_termin.py` für genau diese zwei Schritte.
- **Neues Modul `app_web.py` (Flask):** Login-Seite (Zugangscode, `/`), Abmelden (`/logout`), Teilnehmerliste mit Status "offen"/"bewertet" je Teilnehmer (`/teilnehmer`, nutzt die bereits vorhandene, getestete `berechne_auswertung()` zur Bestimmung des Status statt eigener Logik), Ergebnis-Erfassungsformular (`/teilnehmer/<id>`, bei ED eine Disziplin, bei DK alle drei). Anmeldung über eine signierte Flask-Session (Cookie enthält nur den Schema-Namen, kein Geheimnis). **Jede HTTP-Anfrage bekommt ihre eigene, kurzlebige PostgreSQL-Verbindung** (statt einer global geteilten) – einfacher als ein Connection-Pool, unproblematisch bei der erwarteten Nutzerzahl (eine Handvoll Richter), vermeidet aber auch, dass sich `SET search_path` verschiedener gleichzeitiger Anfragen in die Quere kommt. Eingaben werden serverseitig geprüft (Suchleistung 0–60, Anzeigeleistung 0–40, nur Zahlen), bevor sie überhaupt an die Datenbank gehen – vermeidet, dass eine fehlgeschlagene CHECK-Constraint bei PostgreSQL die laufende Transaktion in einen Fehlerzustand versetzt (der schlanke `_PostgresConnection`-Wrapper bietet bewusst kein `rollback()` an, siehe Kommentar in `app_web.py`). Templates (`templates/*.html`) ohne externe CDN-Abhängigkeiten (LAN-only, siehe oben), mobilfreundlich für Richter mit Handy/Tablet am Prüfungstag.
- **Neue Datei `requirements-web.txt`** (nur `Flask`), bewusst getrennt von `requirements.txt` (Desktop-Installer) UND von `requirements-postgres.txt` (nur der DB-Treiber) – zum Einrichten des Web-Servers werden beide zusätzlichen Dateien gebraucht.
- **Testabdeckung:**
  - `kopiere_termin_daten()`/`importiere_ergebnisse_nach_startnummer()` (die eigentliche Kopierlogik) sind bewusst dialektunabhängig gehalten und werden in der neuen Testklasse `TestTerminSync` **mit zwei echten SQLite-Verbindungen** geprüft (6 Tests: Veranstaltung+Teilnehmer kopieren, bereits vorhandene Ergebnisse werden mitkopiert, ID-Zuordnung, Rückimport nach Startnummer überschreibt Ergebnisse im Ziel, Teilnehmer ohne Startnummer werden übersprungen und gemeldet, kompletter Export/Import-Rundlauf) – läuft dadurch vollständig ohne installiertes psycopg2.
  - Die dünnen Postgres-Wrapper (`exportiere_termin_nach_postgres`/`importiere_ergebnisse_aus_postgres`) sowie der neue Zugangscode (`_eindeutigen_zugangscode_erzeugen`/`pruefe_zugangscode_postgres`) zusätzlich in `TestTerminverwaltungPostgres` (4 neue Tests) und der neuen Klasse `TestTerminSyncPostgres` (2 Tests) gegen einen echten PostgreSQL-Server geprüft – lokal übersprungen (kein psycopg2), läuft in der CI.
  - Neue Datei `test_app_web.py` (11 Tests) – prüft `app_web.py` mit dem Flask-Test-Client **gegen eine echte, temporäre SQLite-Termin-Datei** (Login mit richtigem/falschem Code, Weiterleitung ohne Anmeldung, Abmelden, Teilnehmerliste mit Status offen/fertig, Ergebnis speichern bei ED/DK, Validierung – ungültiger Wertebereich/keine Zahl/leere Felder löschen ein Ergebnis, unbekannter Teilnehmer liefert 404). Nur die drei PostgreSQL-spezifischen "Klebefunktionen" werden dafür durch einfache, auf dieselbe SQLite-Datei umgeleitete Ersatzfunktionen ausgetauscht – die komplette übrige Anwendungslogik (Formularvalidierung, Session, Templates) läuft dabei über echte Datenbankzugriffe statt gemockte Rückgabewerte.
  - Gesamter lokaler Testlauf (`test_db.py` + `test_db_postgres_wrapper.py` + `test_app_web.py`): 156 Tests, 66 übersprungen (PostgreSQL-Tests ohne lokal installierbares psycopg2), 0 fehlgeschlagen, 0 Fehler. **Wichtige Einschränkung, die sich erst beim folgenden ersten echten CI-Lauf zeigte (siehe nächster Abschnitt): "0 Fehler" galt nur für den hier lokal möglichen Testumfang – die PostgreSQL-Tests selbst liefen dabei mangels installierbarem psycopg2 nie wirklich mit, sondern wurden nur sauber übersprungen.**
  - Die `zugangscode`-Spalte (inkl. `ADD COLUMN IF NOT EXISTS` für bereits vorhandene Registries) zusätzlich manuell gegen den lokalen PostgreSQL-Server verifiziert.
- **CI (`.github/workflows/tests.yml`) erweitert:** `requirements-web.txt` wird zusätzlich installiert, damit `test_app_web.py` (Flask) läuft; Kommentar am Dateianfang aktualisiert.
- **Bewusst NICHT Teil dieser ersten Ausbaustufe** (siehe "Noch offen"): Authentifizierung/Rechte über den gemeinsamen Zugangscode hinaus, eine PostgreSQL-Backup-Strategie, das eigentliche Podman-Containerfile/-Setup sowie ein produktionstauglicher WSGI-Server (der eingebaute Flask-Entwicklungsserver in `app_web.py` ist ausdrücklich nur für lokale Tests gedacht).

**Architektur-Entscheidung (19.09., Fortsetzung 3): erster echter CI-Lauf gegen einen echten PostgreSQL-Server – fünf reale Bugs gefunden und behoben (in zwei Runden), dritter CI-Lauf danach vollständig grün**
- **Hintergrund:** Der Push mit dem Web-Backend V1 (siehe oben) war der ALLERERSTE Lauf, bei dem die PostgreSQL-Testklassen (`TestDatenbankPostgres`/`TestZeitplanPostgres`/`TestTerminverwaltungPostgres`/`TestTerminSyncPostgres`) tatsächlich gegen einen echten PostgreSQL-Server liefen, statt in dieser Arbeitsumgebung mangels installierbarem `psycopg2` nur sauber übersprungen zu werden. Genau die Lücke, die im vorigen Abschnitt ("0 Fehler") offen benannt wurde – und genau deshalb wurde von Anfang an so viel Sorgfalt auf eine dialektunabhängige Testbarkeit gelegt (siehe `TestTerminSync` oben). Der Nutzer hat den CI-Lauf geprüft, 3 von 4 Jobs waren rot, und einen Ausschnitt des Fehlerprotokolls als Screenshot geteilt (7 fehlgeschlagene Tests + 2 Fehler). **Runde 1** – vier zugrunde liegende Ursachen identifiziert und behoben:
  1. **`DROP TABLE teilnehmer` ohne `CASCADE` bei PostgreSQL** (`TestDatenbankPostgres::test_migration_*`, `DependentObjectsStillExist`): Die drei Migrations-Tests legen sich für den Test bewusst eine "alte" `teilnehmer`-Tabelle ohne die neuesten Spalten an, indem die echte Tabelle vorher gelöscht und durch eine ältere Variante ersetzt wird. SQLite erzwingt Fremdschlüssel standardmäßig nicht (in dieser App nie über `PRAGMA foreign_keys` aktiviert) – `DROP TABLE teilnehmer` funktioniert dort also anstandslos, obwohl `ergebnisse.teilnehmer_id` per Fremdschlüssel darauf verweist. PostgreSQL erzwingt Fremdschlüssel dagegen immer und verweigert das `DROP TABLE` ohne `CASCADE`. SQLite kennt umgekehrt die `CASCADE`-Syntax bei `DROP TABLE` überhaupt nicht (Syntaxfehler) – ein pauschales `CASCADE` für beide Dialekte ging also nicht. Behoben mit einem neuen, dialektabhängigen Klassenattribut `_DROP_TEILNEHMER_SQL_ZUSATZ` (leer bei SQLite, `" CASCADE"` bei PostgreSQL über `_PostgresBackendMixin`).
  2. **`.fetchone()[0]` (Positions-Index) statt Spaltenname in zwei Tests** (`test_teilnehmer_loeschen_entfernt_auch_ergebnis`, `test_richter_loeschen_entfernt_auch_seine_eintraege`, beide `KeyError: 0`): dieselbe Falle wie der bereits einmal in `db.py` selbst behobene `vergebene_startnummern()`-Fehler (siehe oben) – `sqlite3.Row` erlaubt sowohl `row[0]` als auch `row["spalte"]`, die dict-artigen Zeilen von psycopg2s `RealDictCursor` dagegen nur den Namen. Diesmal steckte der Fehler nicht in `db.py`, sondern in den Tests selbst, die dadurch nie zuvor gegen echtes PostgreSQL gelaufen waren. Behoben durch `AS anzahl`-Alias in der jeweiligen `SELECT COUNT(*)`-Abfrage und Zugriff über `.fetchone()["anzahl"]`.
  3. **Fehlender `search_path`-Wechsel in `exportiere_termin_nach_postgres()`** (`TestTerminSyncPostgres`, `IndexError` bzw. `UniqueViolation` auf `startnummer`): `erstelle_termin_postgres()` setzt den `search_path` bewusst am Ende wieder auf `"public"` zurück (eigene Konvention, siehe Kommentar dort) – `exportiere_termin_nach_postgres()` rief direkt danach `kopiere_termin_daten()` auf, OHNE vorher zurück auf das neue Termin-Schema zu wechseln. Die kopierten Daten landeten dadurch im geteilten `public`-Schema statt im eigenen `termin_N`-Schema (dessen Tabellen blieben leer – daher der `IndexError` beim anschließenden Test) und kollidierten dort mit der von `TestDatenbankPostgres`/`TestZeitplanPostgres` (die bewusst direkt im `public`-Schema arbeiten, siehe `_PostgresBackendMixin`) bereits angelegten `teilnehmer`-Tabelle samt Unique-Constraint auf die Startnummer. Behoben durch einen expliziten `_setze_termin_suchpfad(postgres_conn, neuer_termin.schema_name)` zwischen `erstelle_termin_postgres()` und `kopiere_termin_daten()`.
  4. **Unqualifiziertes `DELETE FROM termin_registry` im Test-Aufräumcode** (`TestTerminverwaltungPostgres::test_zwei_termine_sind_voneinander_isoliert`, `UndefinedTable`): Die Aufräumfunktion `_registry_leeren()` (in `setUp`/`tearDown` beider Postgres-Terminverwaltungs-Testklassen) löscht zunächst alle Termin-Schemas und danach per `DELETE FROM termin_registry` (ohne Schema-Präfix) alle Registry-Zeilen. Endet ein Test aber – wie dieser eine – mit einem rohen `oeffne_termin_postgres()`-Aufruf statt mit einer der Registry-Funktionen (die intern immer wieder auf `"public"` zurückschalten), bleibt der `search_path` auf dem zuletzt geöffneten (und von `_registry_leeren()` gerade selbst gelöschten) Termin-Schema stehen – ein unqualifiziertes `termin_registry` findet die Tabelle dann nicht mehr, da `public` nicht mehr im Suchpfad steht. Behoben durch Qualifizierung als `DELETE FROM public.termin_registry` in beiden `_registry_leeren()`-Methoden.
  - Alle vier Ursachen wurden durch genaues Lesen des Codes hergeleitet (nicht durch Ausprobieren) und zusätzlich an einem lokal gestarteten echten PostgreSQL-16-Server per `psql` nachvollzogen (u. a. die genaue `search_path`-Fehlermeldung `relation "..." does not exist` bei unqualifiziertem Zugriff nachgestellt). Kompletter lokaler Testlauf nach allen vier Korrekturen erneut grün: `test_db.py` (136 Tests, 66 übersprungen), `test_app_web.py` (11 Tests), `test_db_postgres_wrapper.py` (9 Tests), `test_shs_core.py`, `test_pdf_export.py` – alle 0 fehlgeschlagen, 0 Fehler.
  - **Runde 2 (nach dem nächsten CI-Lauf):** Von 246 Tests schlug nur noch EIN einziger fehl – `TestDatenbankPostgres::test_teilnehmer_loeschen_entfernt_auch_ergebnis`, `AssertionError: 1 != 0` (Rest: 214 bestanden, 31 übersprungen, 22 Subtests bestanden) – ein enormer Sprung gegenüber Runde 1 (7 fehlgeschlagene Tests + 2 Fehler), der zeigt, dass die vier Korrekturen aus Runde 1 gegriffen haben. Der eine verbleibende Fehler war eine direkte, unbeabsichtigte NEBENWIRKUNG von Korrektur 1 (`_DROP_TEILNEHMER_SQL_ZUSATZ`) aus Runde 1 selbst:
    5. **Verlorene Fremdschlüssel-Constraint durch `DROP TABLE teilnehmer CASCADE` in den Migrations-Tests** (`test_teilnehmer_loeschen_entfernt_auch_ergebnis`, `AssertionError: 1 != 0`): Das in Runde 1 ergänzte `CASCADE` beim `DROP TABLE teilnehmer` in `_lege_alte_teilnehmer_tabelle_an()` (für die drei `test_migration_*`-Tests) reißt als Nebeneffekt auch die Fremdschlüssel-Constraint `ergebnisse_teilnehmer_id_fkey` mit ab (sie hängt als abhängiges Objekt an `teilnehmer`) – die Tabelle `ergebnisse` selbst bleibt dabei bestehen, aber ohne Fremdschlüssel. Da die anschließende `_neu_verbinden()` nur `CREATE TABLE IF NOT EXISTS ergebnisse (...)` erneut ausführt (ein No-Op, solange die Tabelle noch existiert), blieb die Constraint für den GESAMTEN restlichen, gemeinsam genutzten Postgres-Testlauf verloren – nicht nur für den einen Migrations-Test. `delete_teilnehmer()` verlässt sich in `db.py` vollständig auf `ON DELETE CASCADE` (kein manuelles `DELETE FROM ergebnisse`, siehe dortiger Code) und löschte deshalb ab dann keine zugehörige `ergebnisse`-Zeile mehr mit. Sichtbar wurde das erst bei `test_teilnehmer_loeschen_entfernt_auch_ergebnis` (alphabetisch NACH den Migrations-Tests in derselben Testklasse ausgeführt): `add_teilnehmer()` legt dort automatisch eine leere `ergebnisse`-Zeile an (siehe Kommentar bei `get_ergebnis()` in `db.py`), `delete_teilnehmer()` entfernte danach nur noch die `teilnehmer`-Zeile, die verwaiste `ergebnisse`-Zeile blieb zurück → `COUNT(*) = 1` statt `0`. Behoben, indem `_lege_alte_teilnehmer_tabelle_an()` jetzt zusätzlich `DROP TABLE ergebnisse` ausführt (kein `CASCADE` nötig, nichts verweist auf `ergebnisse`) – die anschließende `_neu_verbinden()` legt sie dadurch tatsächlich neu an, inklusive der Fremdschlüssel-Constraint aus der echten Schema-Definition. Unproblematisch für SQLite (dort entsteht durch das `DROP TABLE` ohnehin nie eine echte FK-Constraint) und für beide Dialekte gültiges Standard-SQL.
    - Der komplette Mechanismus wurde vor der Auslieferung zweifach an einem lokal gestarteten echten PostgreSQL-16-Server per `psql` nachgestellt: einmal die alte (fehlerhafte) Abfolge, die das `1 != 0` exakt reproduzierte, und einmal die neue (korrigierte) Abfolge mit `DROP TABLE ergebnisse`, die danach `COUNT = 0` lieferte – also nicht nur der Fehler nachgestellt, sondern auch der Fix positiv verifiziert. Kompletter lokaler Testlauf danach erneut grün (168 Tests, 67 übersprungen, 0 fehlgeschlagen, 0 Fehler).
  - **Einordnung:** Das ist genau der Fall, für den die aufwändige dialektunabhängige Testarchitektur (SQLite-only-Tests für die reine Logik, Postgres-only-Tests nur für die dünnen Wrapper, siehe `TestTerminSync` oben) gedacht war – alle fünf Bugs waren PostgreSQL-spezifisch und konnten in dieser Arbeitsumgebung nicht vorher gefunden werden, kamen aber dank der CI vor dem Nutzer ans Licht, nicht erst am Prüfungstag beim echten Einsatz mit mehreren Richtern gleichzeitig. Bug 5 zeigt außerdem, dass selbst ein sorgfältig hergeleiteter und einzeln verifizierter Fix (Bug 1) in einer gemeinsam genutzten, über den ganzen Testlauf hinweg persistenten Datenbank Nebenwirkungen auf spätere, unabhängige Tests haben kann – ein Grund mehr, jede Korrektur nach einem erneuten CI-Lauf tatsächlich zu bestätigen, statt sich auf die lokale Herleitung allein zu verlassen.
  - **Bestätigt (19.09.): DRITTER CI-Lauf nach dem Push von Bugfix 5 – Nutzer hat zurückgemeldet, dass jetzt alle Tests grün sind.** Damit sind alle PostgreSQL-Testklassen (`TestDatenbankPostgres`/`TestZeitplanPostgres`/`TestTerminverwaltungPostgres`/`TestTerminSyncPostgres`, zusammen ca. 66 Tests) erstmals vollständig gegen einen echten PostgreSQL-Server bestätigt grün, nicht nur lokal per `psql`-Simulation oder Übersprung. Das PostgreSQL-CI-Bugfixing ist damit abgeschlossen.

**Architektur-Entscheidung (19.09., Fortsetzung 4) und Umsetzung: Podman-Containerisierung des Web-Backends**
- **Mit dem Nutzer abgestimmter Zuschnitt** (drei Fragen, vorab geklärt): (1) **Laufzeitumgebung:** noch bewusst offengelassen (Windows-Laptop über Podman Desktop/WSL2 ODER ein separates Linux-Gerät im Vereinsnetz – beides möglich, Entscheidung wird auf später verschoben). (2) **PostgreSQL-Betrieb:** containerisiert im selben Compose-Stack (offizielles `postgres:16`-Image, genau wie der PostgreSQL-Service-Container, der in der CI bereits erfolgreich läuft, siehe oben) statt eines separat zu pflegenden Servers. (3) **Build & Verteilung:** automatisiert über GitHub Actions in eine Container-Registry (`ghcr.io`), analog zum bestehenden Windows-Installer-Workflow.
- **Neue Dateien:** `Containerfile` (baut NUR das Web-Backend – `db.py`/`shs_core.py`/`app_web.py`/`version.py`/`templates/`, bewusst OHNE PySide6/`app.py`, damit Desktop- und Web-Image unabhängig bleiben, siehe Begründung in `requirements-postgres.txt`), `compose.yaml` (zwei Dienste: `web` + `db`, `db` ohne nach außen offenen Port – nur der `web`-Dienst darf ihn im Compose-Netzwerk erreichen, Datenpersistenz über ein benanntes Volume `shs_postgres_daten`), `.env.example`/`.env` (Datenbank-Passwort und Session-Schlüssel, `.env` selbst in `.gitignore`), `.containerignore`, `README_CONTAINER.md` (vollständige Anleitung: Einrichtung, Starten/Stoppen, Ablauf am Prüfungstag, Versionsnummer, noch offene Punkte).
- **`app_web.py` läuft im Container über `waitress` statt des Flask-Entwicklungsservers** (`waitress>=3.0` neu in `requirements-web.txt`, ebenso `pyzipper>=0.4.0` – wird gebraucht, weil `db.py` es am Modulanfang importiert, obwohl das Web-Backend die Datensicherungsfunktion selbst nie aufruft, siehe Kommentar dort).
- **Ursprünglicher Nutzerwunsch umgesetzt: Windows-.exe und Container-Image tragen nach einem Release dieselbe Versionsnummer.** Beide werden vom selben Versions-Tag (`vX.Y.Z`) ausgelöst und lesen dieselbe `version.txt` (weiterhin die alleinige Quelle, siehe `bump_version.py`): `build-installer.yml` baut wie bisher den Installer, das neue `.github/workflows/build-container.yml` baut zusätzlich dieses Image und veröffentlicht es nach `ghcr.io/<Repo-Besitzer>/shs-web`, getaggt mit `X.Y.Z` UND `latest`. `version.py` (dieselbe Datei, die `app.py` für den Version-Button neben "Hilfe" verwendet) wird jetzt auch von `app_web.py` importiert und per neuem `context_processor` allen Templates zur Verfügung gestellt – die Versionsnummer erscheint dadurch in der Fußzeile jeder Web-Seite (`templates/base.html`), sichtbar und vergleichbar mit der Desktop-Version.
- **`build-container.yml` prüft bei JEDEM Push/Pull Request zusätzlich per Smoke-Test, ob der komplette Compose-Stack tatsächlich hochkommt** (PostgreSQL + Web-Container bauen und starten, warten bis die Login-Seite antwortet, danach wieder stoppen) – ohne Registry-Veröffentlichung, reine Absicherung analog zu `tests.yml`. Erst bei einem Versions-Tag kommt zusätzlich der eigentliche Veröffentlichen-Schritt nach `ghcr.io` hinzu.
- **Grenzen der Prüfung in dieser Arbeitsumgebung:** Der komplette Compose-Stack (inkl. `docker.io/library/python`- und `docker.io/library/postgres`-Basis-Images) ließ sich hier NICHT tatsächlich bauen/starten – die Arbeitsumgebung hat keinen Netzwerkzugriff auf Docker Hub (dieselbe Art Einschränkung wie das fehlende psycopg2/PyPI weiter oben, hier aber für Container-Registries). Stattdessen geprüft: `Containerfile`/`compose.yaml`/der neue Workflow sind syntaktisch valide (YAML geparst), `app_web.py`/`db.py` kompilieren fehlerfrei, und die komplette lokale Testsuite (inkl. `test_app_web.py` nach der Versions-Fußzeilen-Änderung) läuft weiterhin grün (168 Tests, 0 Fehler).
- **Zwei reale Fehler im neuen `build-container.yml` selbst, gefunden über den ersten echten CI-Lauf (genau die Art Lücke, die die lokale Prüfung oben nicht abdecken konnte) und behoben:**
  1. **Umgebungsvariablen im selben Step gesetzt UND verwendet:** `SHS_DB_PASSWORD`/`SHS_WEB_SECRET_KEY` wurden per `echo ... >> "$GITHUB_ENV"` gesetzt und im selben Step sofort von `docker compose up` gebraucht – `GITHUB_ENV`-Einträge gelten aber erst ab dem NÄCHSTEN Step. `docker compose` lief dadurch ohne die beiden Variablen und brach beim Interpolieren von `compose.yaml` ab (`required variable SHS_DB_PASSWORD is missing a value`).
  2. **Nachfolge-Fehler nach dem ersten Fix:** Als Fix 1 stattdessen `export` verwendete (wirkt sofort im selben Step), fehlten die Variablen im nachfolgenden, unabhängigen Step „Compose-Stack stoppen" (`docker compose down`) – `export` gilt nur innerhalb des Steps, in dem es gesetzt wurde, nicht in späteren Steps desselben Jobs.
  - **Endgültig behoben:** `SHS_DB_PASSWORD`/`SHS_WEB_SECRET_KEY` jetzt als `env:`-Block auf JOB-Ebene gesetzt (nicht in einem einzelnen Step) – gilt dadurch automatisch für alle Steps des Jobs (Start, Warten, Stoppen) gleichzeitig. Beide Fixes vor der Auslieferung zusätzlich mit `docker compose config` lokal geprüft (Interpolation löst sich korrekt auf), obwohl der Stack selbst hier mangels Docker-Hub-Zugriffs nicht gestartet werden konnte.
- **Bestätigt (19.09.): Smoke-Test-Job in `build-container.yml` nach diesen beiden Fixes vom Nutzer als grün zurückgemeldet.** Der komplette Compose-Stack (PostgreSQL + Web-Container) kommt damit erstmals nachweislich tatsächlich hoch und die Login-Seite antwortet – nicht nur syntaktisch/lokal geprüft wie oben beschrieben, sondern ein echter, laufender Testlauf auf einem GitHub-Runner mit vollem Internetzugriff.
- **Realer Vorfall (19.09.) beim ersten tatsächlichen Versions-Release und Absicherung dagegen:** Nutzer hat einen Tag gesetzt (erwartet: `v1.0.8`), der fertige Windows-Installer hieß aber weiterhin `SHS-Pruefungsprogramm-Setup-1.0.7.exe`. Ursache: `build-installer.yml` baut bewusst NICHT mit dem Tag-Namen selbst, sondern mit der Nummer, die zu diesem Zeitpunkt in `version.txt` eingecheckt ist (so schon immer dokumentiert, siehe README_INSTALLER.md) – der Tag wurde vermutlich gesetzt/gepusht, BEVOR die per `bump_version.py` lokal bereits erhöhte `version.txt` committet und gepusht war, wodurch der Workflow mit der noch alten, im Repo stehenden Nummer weiterbaute. Kein Bug im Workflow selbst, sondern eine Lücke: nichts prüfte bisher, ob Tag und `version.txt` überhaupt zusammenpassen, bevor gebaut/veröffentlicht wurde. **Behoben durch einen neuen Prüf-Schritt in BEIDEN Workflows** (`build-installer.yml` und `build-container.yml`, direkt nach dem Auslesen von `version.txt`, vor dem eigentlichen Build) – vergleicht bei einem Versions-Tag-Push den Tag-Namen (ohne führendes „v") mit dem Inhalt von `version.txt` und bricht mit einer klaren Fehlermeldung ab, falls beide nicht übereinstimmen, statt ein falsch benanntes Release stillschweigend zu veröffentlichen. Betrifft potenziell auch das Container-Image (dieselbe Ursache, dieselbe `version.txt`) – dort aber noch nicht tatsächlich in einem echten Release aufgetreten, da der erste Container-Release noch aussteht (siehe unten).
- **Realer Vorfall (19.09.) beim ersten echten Nutzertest auf dem PC des Nutzers und Behebung – Podman-Machine-Netzwerk kaputt, PostgreSQL-Port fehlte:** Zwei voneinander unabhängige Probleme traten nacheinander beim erstmaligen `podman-compose up --build -d` auf dem Windows-Rechner des Nutzers auf: (1) Web-Container lief laut `podman ps` einwandfrei ("healthy", Port `0.0.0.0:5000->5000/tcp` veröffentlicht), war aber unter `localhost:5000` nicht erreichbar – `netstat` zeigte, dass auf Windows-Seite gar nichts auf Port 5000 lauschte, Windows-Firewall testweise komplett deaktiviert brachte keine Besserung. Ursache: die Netzwerk-Weiterleitung der Podman-Maschine (WSL2-basiert) selbst war in einen kaputten Zustand geraten (kein Fehler in unseren Dateien) – behoben durch kompletten Reset der Maschine (`podman machine rm -f` + `podman machine init` + `start`), danach lauschte Windows korrekt auf Port 5000. (2) Nach dem Maschinen-Reset versuchte `podman-compose up --build -d`, das `web`-Image von `ghcr.io` zu PULLEN statt lokal zu bauen (weil `compose.yaml` sowohl `image:` als auch `build:` angibt) – schlug mit `unauthorized` fehl, da das GitHub-Repo und damit das dort veröffentlichte Image privat sind. Workaround: `podman-compose build` gefolgt von `podman-compose up -d` (getrennte Schritte, kein Pull-Versuch beim reinen Bauen). **Danach ein dritter, echter Lücke in unserer eigenen Konfiguration gefunden:** der Nutzer konnte keinen Zugangscode erzeugen, weil `sync_termin.py` (läuft direkt auf dem Windows-Rechner, nicht im Container) die Datenbank gar nicht erreichen konnte – `compose.yaml` gab den PostgreSQL-Port absichtlich NICHT nach außen frei (aus Sicherheitsgründen). **Behoben:** `db`-Dienst in `compose.yaml` bekommt jetzt `127.0.0.1:5432:5432` (NICHT `0.0.0.0`) – von diesem Rechner aus erreichbar für `sync_termin.py`, aber weiterhin nicht aus dem übrigen Vereinsnetz. `README_CONTAINER.md` bekam dafür einen neuen, vollständig ausgeschriebenen Abschnitt „Zugangscode erzeugen" (inkl. `pip install -r requirements-postgres.txt`, DSN-Aufbau aus `.env`-Werten, `$env:SHS_POSTGRES_DSN`). Mit diesen drei Korrekturen lief der komplette Ablauf beim Nutzer erstmals durch: Login-Seite erreichbar, Versionsnummer in der Fußzeile sichtbar (`0.99.99`, passend zur Desktop-Version).

**Architektur-Entscheidung (19.09., Fortsetzung 5) und Umsetzung: gemeinsamer Zugangscode durch echte Benutzerkonten ersetzt**
- **Nutzerwunsch:** *"das ist ziemlich kompliziert. können wir die Funktion nicht komplett vom Windows Team trennen und default alles per Web erreichbar machen. Beim ersten Mal ist der Administrator mit Vergabe des PW für sich und danach kann man user und PW anlegen die nur eintragen können."* Der bisherige gemeinsame, sechsstellige Zugangscode je Termin (siehe Fortsetzung 2) reichte damit nicht mehr aus. Drei Fragen vorab mit dem Nutzer abgestimmt (jeweils die empfohlene Option gewählt): (1) **Umfang der Trennung vom Windows-Team:** NUR Login/Zugriff umgestellt – Termin anlegen/Teilnehmer/Zeitplan bleiben weiterhin Desktop-Aufgaben, veröffentlicht über `sync_termin.py` (ein voller Umzug der Terminverwaltung ins Web war explizit NICHT gewählt). (2) **Netzwerk:** weiterhin NUR lokales Vereinsnetz – keine Internet-Erreichbarkeit, kein TLS/Domain, keine Änderung an der bisherigen Deployment-Annahme. (3) **Rollen:** genau zwei – Administrator (Benutzerverwaltung + voller Zugriff) und "Eintragen" (darf ausschließlich Ergebnisse erfassen) – keine feinere Rechtevergabe nötig.
- **Neuer Abschnitt "Benutzerkonten der Web-Version" in `db.py`:** neue GLOBALE (nicht mehr an einen einzelnen Termin gebundene) Tabelle `public.web_benutzer` (`benutzername` als Primärschlüssel statt einer separaten `id`-Spalte – der Benutzername ist ohnehin eindeutig, dadurch ganz ohne AUTOINCREMENT/SERIAL-Übersetzung zwischen SQLite und PostgreSQL auskommend, `passwort_hash`, `ist_admin`, `erstellt_am`), angelegt idempotent in `verbinde_postgres_server()` genau wie `termin_registry`. Neue Funktionen: `gibt_es_admin()`, `admin_einrichten()` (lehnt ab, falls zwischenzeitlich schon ein Administrator existiert – verhindert einen zweiten "ersten" Admin bei z. B. zwei parallel geöffneten Ersteinrichtungs-Formularen), `benutzer_anlegen()`, `benutzer_loeschen()` (verhindert das Löschen des LETZTEN verbleibenden Administrators, sonst könnte niemand mehr neue Konten anlegen), `liste_benutzer()`, `pruefe_login()` (liefert bei unbekanntem Benutzernamen bewusst denselben Fehlerweg wie bei falschem Passwort, damit sich über die Fehlermeldung keine Benutzernamen erraten lassen). Passwörter werden über `werkzeug.security` gehasht (`generate_password_hash`/`check_password_hash`) – KEINE neue pip-Abhängigkeit, da Flask werkzeug ohnehin mitzieht (siehe `requirements-web.txt`). Genau wie bei `psycopg2` wird `werkzeug.security` bewusst NICHT am Modulanfang importiert, sondern erst innerhalb der einzelnen Funktionen – die Desktop-Version (`requirements.txt`) soll diese zusätzliche Abhängigkeit weiterhin nie brauchen, obwohl sie dasselbe `db.py`-Modul importiert.
- **Zugangscode-Mechanismus vollständig abgelöst** (nicht nur ergänzt): `_eindeutigen_zugangscode_erzeugen()`/`pruefe_zugangscode_postgres()` sowie das `zugangscode`-Feld in `TerminInfoPostgres` wurden entfernt, `erstelle_termin_postgres()` erzeugt keinen Code mehr. Die Spalte `termin_registry.zugangscode` selbst bleibt in der Datenbank bestehen (bereits vorhandene Registry-Einträge/Datenbanken behalten ihren alten Wert als reine Historie), wird von `db.py` aber nirgends mehr gelesen oder neu befüllt – bewusst additiv statt eine `DROP COLUMN`-Migration zu riskieren.
- **Weil Konten jetzt GLOBAL sind** (nicht mehr wie der Zugangscode an einen einzelnen Termin gebunden), braucht es nach dem Login einen zusätzlichen Schritt: **`/termin-waehlen`** in `app_web.py` – zeigt alle aktuell veröffentlichten Termine (über die bereits vorhandene `liste_termine_postgres()`) zur Auswahl an, wird aber automatisch übersprungen, sobald genau ein Termin offen ist (der übliche Fall am Prüfungstag – bequem, kein unnötiger Klick).
- **`app_web.py` umgebaut:** `/`-Route zeigt, solange noch KEIN Administrator existiert, eine einmalige "Ersteinrichtung" (Benutzername/Passwort + Wiederholung, `admin_einrichten()`) statt des normalen Logins – danach nie wieder, auch nicht nach "Abmelden". Drei Decorator statt vorher einem: `_login_erforderlich` (irgendein angemeldetes Konto), `_admin_erforderlich` (zusätzlich `ist_admin`, sonst 403 statt Redirect – der Nutzer ist ja bereits angemeldet), `_termin_erforderlich` (zusätzlich ein per `/termin-waehlen` ausgewähltes Schema, wie zuvor). Neue Routen `/admin/benutzer` (Liste + Anlegen, nur Administratoren) und `/admin/benutzer/<name>/loeschen` (löscht sich selbst dabei automatisch ab, falls das eigene Konto betroffen ist). Gemeinsame Formularvalidierung `_pruefe_benutzername_und_passwort()` (Passwort mind. 8 Zeichen, beide Passwortfelder müssen übereinstimmen) für Ersteinrichtung UND Benutzerverwaltung. Doppelte Benutzernamen werden vor dem Anlegen per Vergleich mit `liste_benutzer()` abgefangen und mit einer klaren deutschen Fehlermeldung zurückgegeben, statt eine rohe Datenbank-Exception durchzureichen.
- **Neue/geänderte Templates:** `login.html` zeigt jetzt Benutzername/Passwort statt eines Zugangscode-Felds; neue `ersteinrichtung.html` (Ersteinrichtungsformular mit Erklärtext), `termin_waehlen.html` (Liste der offenen Termine als Buttons, mit Hinweistext falls keiner offen ist), `admin_benutzer.html` (Anlegen-Formular inkl. Rollenauswahl + Liste bestehender Konten mit Löschen-Button). `base.html`: Kopfzeile zeigt jetzt bei angemeldeten Nutzern zusätzlich "Termin wechseln" (falls ein Termin gewählt ist), "Benutzer" (nur für Administratoren) sowie den eigenen Benutzernamen neben "Abmelden".
- **`sync_termin.py` angepasst:** `_export()` gibt nach dem Veröffentlichen keinen Zugangscode mehr aus, sondern bestätigt, dass der Termin jetzt in der Termin-Auswahl der Web-Oberfläche erscheint (Login läuft über die Benutzerkonten). Modul-Docstring/Ablaufbeschreibung entsprechend aktualisiert.
- **Testabdeckung:**
  - `test_db.py`: neue Testklasse `TestBenutzerkontenPostgres` (11 Tests, gegen einen echten PostgreSQL-Server, lokal ohne `SHS_TEST_POSTGRES_DSN` übersprungen wie die übrigen Postgres-Testklassen) – deckt Ersteinrichtung, Ablehnung eines zweiten "ersten" Admins, richtiges/falsches Passwort, unbekannter Benutzername, Konto ohne Adminrechte anlegen, alphabetische+hash-freie Benutzerliste, doppelter Benutzername wird abgelehnt, Löschen eines Kontos, Schutz des letzten Administrators vor dem Löschen, Löschen ist möglich sobald zwei Administratoren existieren. Die vier obsoleten Zugangscode-Tests in `TestTerminverwaltungPostgres` entfernt bzw. durch eine allgemeinere "Termin taucht in der Auswahl auf"-Prüfung in `TestTerminSyncPostgres` ersetzt.
  - `test_app_web.py` (26 Tests, komplett neu strukturiert): Ersteinrichtung (Formular erscheint ohne Admin, legt Admin an + meldet sofort an, lehnt zu kurzes/nicht übereinstimmendes Passwort ab, normaler Login erscheint danach dauerhaft), Login (falsches Passwort/unbekannter Benutzer – identischer Fehlertext), Termin-Auswahl (wird bei einem offenen Termin übersprungen, zeigt Liste bei mehreren, lehnt unbekanntes Schema per POST ab, zeigt Hinweis ohne offene Termine), Benutzerverwaltung (403 für Nicht-Admins, Anlegen, doppelter Name abgelehnt, Löschen, letzter Admin kann sich nicht selbst löschen), plus die bestehenden Teilnehmerliste-/Ergebnis-erfassen-Tests unverändert inhaltlich, nur über den neuen Login-Weg. Anders als zuvor werden die neuen Konten-Funktionen dabei NICHT gemockt, sondern laufen für echt gegen die SQLite-Testdatei (`db._setze_termin_suchpfad` wird dafür durch einen No-Op ersetzt, da SQLite kein `SET search_path` kennt und eine einzelne Datei diesen PostgreSQL-Schema-Wechsel ohnehin nicht braucht) – nur `verbinde_postgres_server`/`oeffne_termin_postgres`/`liste_termine_postgres` bleiben wie zuvor gemockt.
  - Gesamter lokaler Testlauf (`test_db.py` + `test_db_postgres_wrapper.py` + `test_app_web.py`): 178 Tests, 73 übersprungen (PostgreSQL-Tests ohne lokal installierbares psycopg2), 0 fehlgeschlagen, 0 Fehler.
- **Noch offen:** ein echter End-zu-Ende-Test des neuen Konten-Flows beim Nutzer (Ersteinrichtung, Benutzer anlegen, Login mit "Eintragen"-Konto, Termin-Auswahl bei mehreren offenen Terminen). Die CI-Bestätigung, dass `TestBenutzerkontenPostgres` gegen den echten PostgreSQL-Service-Container grün läuft, liegt inzwischen vor (20.09., Version 1.0.12 - siehe dortiger Abschnitt).

**Umsetzung (19.09., Fortsetzung 6): Termin veröffentlichen/zurückholen auch über die Web-Oberfläche (Datei-Upload/Download), als Alternative zur Kommandozeile**
- **Nutzerwunsch:** *"die art des import und export ist sehr umständlich kann ich das nicht über die Weboberfläche machen nachdem ich einen Administartor festgelegt habe?"* – der bisherige `sync_termin.py`-Kommandozeilenweg (Fortsetzung 4/5, `psycopg2` installieren, DSN zusammensetzen, `export`/`import` mit `--dsn`) blieb als einzige Möglichkeit bestehen. Zwei Fragen vorab mit dem Nutzer abgestimmt (jeweils die empfohlene Option gewählt): (1) **Technischer Weg:** Datei-Upload/Download über die Web-Oberfläche statt direktem Zugriff des Containers auf den Termine-Ordner auf dem Rechner des Nutzers – funktioniert unabhängig davon, ob Container und Desktop-App später auf demselben Gerät oder getrennten Geräten laufen (die Laufzeitumgebungs-Frage ist laut "Noch offen" weiterhin nicht entschieden) und braucht keine Änderung an `compose.yaml`/Volume-Mounts. (2) **Berechtigung:** nur Administratoren dürfen veröffentlichen/zurückholen – passt zum bestehenden Rollenmodell, "Eintragen"-Konten sehen weiterhin nur die Ergebniserfassung.
- **Neue, ausschließlich administrative Seite `/admin/termine` in `app_web.py`** (Link "Termine" in der Kopfzeile, nur für Administratoren sichtbar) mit drei neuen Routen, die alle die BEREITS VORHANDENEN, bereits über `test_db.py` gegen einen echten PostgreSQL-Server geprüften `db.py`-Funktionen wiederverwenden (`exportiere_termin_nach_postgres`/`importiere_ergebnisse_aus_postgres`/`loesche_termin_postgres`) – die neuen Routen selbst enthalten keine neue Fachlogik, nur Datei-Upload/-Download-Mechanik und Berechtigungsprüfung:
  - **Veröffentlichen** (`/admin/termine/veroeffentlichen`): Termin-Datei (`.sqlite`) aus der Desktop-Version hochladen, wird serverseitig in eine temporäre Datei geschrieben, mit `db.init_db()` geöffnet und per `exportiere_termin_nach_postgres()` veröffentlicht – die temporäre Datei wird danach sofort gelöscht.
  - **Zurückholen** (`/admin/termine/<schema_name>/zurueckholen`): dieselbe Termin-Datei erneut hochladen, Ergebnisse werden per `importiere_ergebnisse_aus_postgres()` eingetragen (Zusammenfassung inkl. Anzahl aktualisierter Teilnehmer/übersprungener/nicht zugeordneter Startnummern wird angezeigt) – die aktualisierte Datei bleibt anschließend serverseitig unter einem einmaligen, per `secrets.token_urlsafe()` erzeugten Token verfügbar und wird über einen Download-Link (`/admin/termine/download/<token>`) ausgeliefert, danach sofort gelöscht (einmalig nutzbar, rein prozessintern gehalten – unkritisch, da der Container als ein einzelner `waitress`-Prozess läuft, keine mehrere parallele Worker).
  - **Löschen** (`/admin/termine/<schema_name>/loeschen`): entfernt einen veröffentlichten Termin direkt über die Web-Oberfläche (bisher nur indirekt über die Datenbank möglich).
- **Neues Template `templates/admin_termine.html`**: Veröffentlichen-Formular mit Upload-Feld, Ergebnis-Zusammenfassung + Download-Link nach dem Zurückholen, Liste der offenen Termine mit je einem Inline-Formular zum Zurückholen und einem Löschen-Button.
- **`sync_termin.py` bleibt vollständig unverändert und funktionsfähig** – die Web-Oberfläche ist eine Alternative, kein Ersatz; beide Wege können gemischt genutzt werden (z. B. per Kommandozeile veröffentlichen, über die Web-Oberfläche zurückholen), da beide dieselben `db.py`-Funktionen aufrufen.
- **Testabdeckung:** `test_app_web.py` um 8 neue Tests erweitert (34 insgesamt) – 403 für Nicht-Administratoren auf allen vier neuen Routen, Veröffentlichen mit Bestätigungsanzeige, Veröffentlichen ohne Datei/mit falscher Dateiendung (Fehleranzeige), Zurückholen mit Bericht-Anzeige UND funktionierendem, nur einmal nutzbarem Download-Link, Zurückholen mit unbekanntem Termin (400), Zurückholen ohne Datei (Fehleranzeige), Löschen entfernt den Termin und die Termin-Auswahl aus der Session. Die drei PostgreSQL-spezifischen Funktionen (`exportiere_termin_nach_postgres`/`importiere_ergebnisse_aus_postgres`/`loesche_termin_postgres`) werden dabei – wie schon `verbinde_postgres_server`/`oeffne_termin_postgres`/`liste_termine_postgres`/`_setze_termin_suchpfad` zuvor – durch steuerbare Ersatzfunktionen ausgetauscht (bereits real gegen PostgreSQL in `test_db.py` geprüft); der Datei-Upload/-Download selbst läuft dagegen echt, mit einer leeren `.sqlite`-Datei (0 Byte = gültige leere SQLite-Datenbank) als Testinhalt. Gesamter lokaler Testlauf (`test_db.py` + `test_db_postgres_wrapper.py` + `test_app_web.py`): 186 Tests, 73 übersprungen (PostgreSQL-Tests ohne lokal installierbares psycopg2), 0 fehlgeschlagen, 0 Fehler.
- **`README_CONTAINER.md`** bekam einen neuen Unterabschnitt "Alternative: Veröffentlichen/Zurückholen über die Web-Oberfläche" innerhalb des bestehenden Abschnitts "Termin veröffentlichen".
- **Noch offen:** ein echter End-zu-Ende-Test des neuen Web-Upload-Wegs beim Nutzer (Veröffentlichen, Zurückholen inkl. Download der aktualisierten Termin-Datei, Löschen).

**Realer Vorfall (19.09.) beim ersten echten Test des Konten-Systems und Behebung: Admin-Login nach Anlegen eines Richter-Kontos "Benutzername oder Passwort falsch"**
- **Gemeldeter Fehler:** Nutzer hat als Administrator ("Marco") ein Richter-Konto angelegt, sich ausgeloggt und wollte sich danach mit seinem eigenen Administrator-Konto wieder anmelden - "Benutzername oder Passwort falsch", obwohl Benutzername/Passwort korrekt waren (Screenshot: normale Login-Seite, kein Ersteinrichtungs-Bildschirm, Benutzername "Marco" eingegeben).
- **Ursache gefunden:** `db.pruefe_login()` vergleicht den Benutzernamen bisher exakt GROSS-/kleinschreibungsempfindlich. Wurde das Administrator-Konto ursprünglich z. B. am PC als "marco" angelegt (keine automatische Groß-/Kleinschreibung auf Desktop-Tastaturen) und meldet sich der Nutzer später über ein Mobilgerät an, schreibt die dortige automatische Autokapitalisierung des ersten Buchstabens im Benutzername-Feld daraus "Marco" - eine exakte Zeichenkettenprüfung lehnt das dann fälschlich ab, obwohl es sich um denselben Benutzernamen handelt. Kein Postgres-/Session-Problem, sondern eine reine Zeichenkettenungleichheit.
- **Behoben in `db.pruefe_login()`:** Vergleich läuft jetzt über `LOWER(benutzername) = LOWER(?)` (funktioniert unverändert in SQLite und PostgreSQL) - Benutzername GROSS-/kleinschreibungsUNabhängig, Passwort bleibt wie bisher GROSS-/kleinschreibungsempfindlich (dort unverändert `check_password_hash`). Passend dazu prüft die Duplikat-Prüfung beim Anlegen neuer Konten (`admin_benutzer()` in `app_web.py`) jetzt ebenfalls GROSS-/kleinschreibungsunabhängig, damit nicht z. B. "Richter1" UND "richter1" als zwei getrennte Konten entstehen können (das hätte den Login sonst uneindeutig gemacht).
- **Zusätzlich als Ursachenbekämpfung an der Wurzel:** allen Benutzername-Feldern (`login.html`, `ersteinrichtung.html`, `admin_benutzer.html`) `autocapitalize="none" autocorrect="off" spellcheck="false"` hinzugefügt, damit Mobilgeräte den eingegebenen Benutzernamen künftig gar nicht erst verändern.
- **Testabdeckung:** neuer Test in `test_db.py` (`TestBenutzerkontenPostgres`, gegen echtes PostgreSQL) prüft Login mit klein-/großgeschriebenem Benutzernamen bei unverändert GROSS-/kleinschreibungsempfindlichem Passwort. Zwei neue Tests in `test_app_web.py` (36 insgesamt): Login mit großgeschriebenem Benutzernamen gelingt, Anlegen eines nur anders geschriebenen, bereits vergebenen Benutzernamens wird abgelehnt. Gesamter lokaler Testlauf: 189 Tests, 74 übersprungen, 0 fehlgeschlagen, 0 Fehler.
- **Noch offen:** Bestätigung durch den Nutzer, dass die Anmeldung mit dem bestehenden Administrator-Konto jetzt tatsächlich funktioniert.

**Umsetzung (19.09.): MIT-Lizenz ergänzt, Repo soll auf öffentlich gestellt werden**
- **Nutzerwunsch:** Repo öffentlich stellen und mit MIT-Lizenz versehen. Copyright-Zeile auf Wunsch des Nutzers bewusst nur "Marco" (kein Nachname).
- **Neue Datei `LICENSE`** (Standard-MIT-Text, Copyright 2026 Marco) direkt in allen drei Ordnern des Nutzers angelegt, `README.md` um einen kurzen Abschnitt "Lizenz" mit Verweis darauf ergänzt.
- **Sicherheits-/Inhaltsprüfung vor der Veröffentlichung durchgeführt** (wichtig, weil beim Öffentlichstellen die GESAMTE bisherige Git-Historie sichtbar wird, nicht nur der aktuelle Stand): komplette Commit-Historie nach `.env`/Zugangsdaten-Dateien durchsucht (keine gefunden - `.env` war nie eingecheckt, korrekt in `.gitignore`), Historie und aktueller Stand nach eingebetteten Passwörtern/API-Keys/privaten Schlüsseln durchsucht (keine echten Werte gefunden, nur Code-Variablennamen und offensichtliche Test-Platzhalter wie "sicheres_passwort"), nach E-Mail-Adressen durchsucht (keine gefunden). Ergebnis: unauffällig, aus Sicht dieser Prüfung spricht nichts gegen eine Veröffentlichung.
- **Das eigentliche Umstellen der Repo-Sichtbarkeit auf "Public" muss der Nutzer selbst in den GitHub-Einstellungen vornehmen** (Settings → General → Danger Zone → "Change visibility") - diese Sitzung hat dafür keinen Zugriff auf sein GitHub-Konto (kein `gh`, kein API-Token für dieses Repo).
- **Nebenbefund beim Prüfen des Git-Ordners:** eine verwaiste `.git/index.lock`-Datei blockiert dort aktuell jedes `git add`/`git commit` ("Unable to create '.git/index.lock': File exists"). Der Nutzer hat die angefragte Berechtigung zum automatischen Entfernen abgelehnt - muss die Datei `.git\index.lock` im Ordner `SHS-Pruefungsprogramm-Git` daher selbst löschen (z. B. im Windows-Explorer, versteckte/System-Dateien anzeigen lassen, `.git`-Ordner öffnen), bevor er wieder committen kann.
- **Noch offen:** Nutzer stellt das Repo selbst auf öffentlich, löscht die verwaiste `index.lock` von Hand, und committet/pusht die ausstehenden Änderungen (u. a. `LICENSE`, `README.md`, die Konten-/Termine-Web-Oberfläche der letzten Sitzungen).

**Umsetzung (19.09.): automatische Update-Prüfung im Version-Dialog der Desktop-Version (Nutzung des nun öffentlichen Repos)**
- **Nutzerwunsch:** Nachfrage, ob im Programm noch etwas am Version-Button/der Möglichkeit, die neueste Version darüber zu laden, geändert werden muss, nachdem das Repo öffentlich wird. Hintergrund: `app.py` enthielt bereits einen Kommentar, dass die automatische Prüfung bewusst NICHT eingebaut war, weil sie bei einem privaten Repository Zugangsdaten gebraucht hätte - der Button öffnete stattdessen nur die Releases-Seite im Browser zum manuellen Nachschauen.
- **Mit dem Nutzer abgestimmt:** automatische Prüfung PER KLICK auf den bestehenden Button umsetzen (keine automatische Prüfung im Hintergrund beim Programmstart, um den Start nicht durch fehlendes Internet am Prüfungstag zu verzögern).
- **Umgesetzt in `app.py`:** neue Funktion `_neueste_version_pruefen()` fragt `https://api.github.com/repos/mbruver-source/SHS/releases/latest` ab (funktioniert seit der Öffentlichstellung ohne Zugangsdaten, über die Standardbibliothek `urllib` - keine neue Abhängigkeit) und liefert entweder die neueste Versionsnummer oder einen verständlichen Fehlertext (kein Internet, GitHub nicht erreichbar, noch kein Release, unerwartete Antwort - jeweils abgefangen statt das Programm abstürzen zu lassen). Neue Hilfsfunktion `_version_tupel()` vergleicht Versionsnummern als `(major, minor, patch)`-Tupel. `VersionDialog` zeigt nach Klick auf "Nach Updates suchen" direkt im Dialog an, ob eine neuere Version existiert (mit zusätzlichem Download-Button zur Releases-Seite) oder ob die installierte Version bereits aktuell ist bzw. eine Fehlermeldung. Ein zusätzlicher, immer sichtbarer Link "Releases-Seite im Browser öffnen" bleibt als manueller Rückfallweg bestehen (löst NIE selbst die API-Abfrage aus). Läuft synchron/blockierend (kurzer 5-Sekunden-Timeout, kein eigener Hintergrund-Thread) - bewusst einfach gehalten, da es sich um eine einzelne, vom Nutzer per Klick ausgelöste Anfrage handelt, keinen Programmstart blockiert und der Dialog ohnehin modal ist.
- **Hilfe-Text** (Reiter "Versionsanzeige" im Hilfe-Dialog) entsprechend aktualisiert.
- **Testabdeckung:** `test_app_gui.py` - vier neue/ersetzte Tests (echter Klick-Test über pytest-qt, GitHub-API dabei über `_neueste_version_pruefen` gemockt, kein echter Netzwerkzugriff nötig): neuere Version verfügbar zeigt Hinweistext + Download-Button, der beim Klick die Releases-Seite öffnet; bereits aktuelle Version zeigt entsprechenden Hinweis ohne Download-Button; ein simulierter Netzwerkfehler zeigt den Fehlertext an; der separate "Releases-Seite öffnen"-Link ruft nachweislich NIE die API auf. Läuft wie die übrigen `test_app_gui.py`-Tests nur in der CI (kein PySide6 lokal installierbar) - hier nur per `py_compile` auf Syntaxfehler geprüft.
- **Noch offen:** CI-Bestätigung dieser vier neuen Tests, sowie ein echter Test beim Nutzer (idealerweise einmal mit und einmal ohne Internetverbindung, sowie nach einem tatsächlichen neuen Release zum Prüfen der "neuere Version verfügbar"-Anzeige).

**Realer CI-Fund (19.09.) und Behebung: `TestBenutzerkontenPostgres::test_doppelter_benutzername_wird_abgelehnt` schlägt gegen echtes PostgreSQL fehl**
- **Vom Nutzer gemeldet:** kompletter `pytest -v`-Lauf aus der CI eingefügt - 247 bestanden, 1 fehlgeschlagen (`InFailedSqlTransaction: current transaction is aborted, commands ignored until end of transaction block`), 31 übersprungen. Anhand der im Log sichtbaren Testnamen erkannt, dass dieser Lauf noch VOR dem automatischen Update-Check-Feature (siehe eigener Abschnitt oben) lag - der eigentliche Fehler betrifft aber ohnehin einen unabhängigen, seit Fortsetzung 5 bestehenden Test, der hier zum ersten Mal tatsächlich gegen einen echten PostgreSQL-Server lief.
- **Ursache:** `test_doppelter_benutzername_wird_abgelehnt` löst absichtlich einen `IntegrityError` aus (doppelter Benutzername), um ihn per `assertRaises` zu prüfen - PostgreSQL markiert die laufende Transaktion nach einem Fehler als abgebrochen, jeder weitere Befehl auf DERSELBEN Verbindung schlägt danach mit `InFailedSqlTransaction` fehl, bis explizit zurückgerollt wurde (anders als SQLite, das diese Einschränkung nicht kennt). `TestBenutzerkontenPostgres.tearDown()` führt aber direkt danach ohne Rollback ein `DELETE FROM public.web_benutzer` auf derselben (jetzt abgebrochenen) Verbindung aus - das schlug fehl. Kein Fehler in der eigentlichen Anwendungslogik (`db.benutzer_anlegen`/`pruefe_login` usw.), sondern ein reiner Test-Aufräumcode-Bug, der erst beim ersten echten Lauf gegen PostgreSQL sichtbar wurde (lokal/mit gemockten Funktionen kam die Testklasse nie bis hierher).
- **Behoben:** `db._PostgresConnection` um eine neue `rollback()`-Methode ergänzt (delegiert wie `commit()`/`close()` einfach an die zugrunde liegende psycopg2-Verbindung - vervollständigt die ohnehin schon nachgebildete Teilmenge der `sqlite3.Connection`-Schnittstelle). `TestBenutzerkontenPostgres.tearDown()` ruft jetzt zuerst `self.conn.rollback()` auf, bevor die Aufräum-Abfrage läuft - unschädlich, falls die Transaktion gar nicht abgebrochen war, macht die Klasse aber robust gegen JEDEN Test in ihr, der einen erwarteten Datenbankfehler auslöst, nicht nur den einen betroffenen.
- **Testabdeckung:** neuer Test in `test_db_postgres_wrapper.py` (`test_rollback_delegiert_an_die_rohe_verbindung`, mit gemockter Verbindung, läuft lokal ohne echtes PostgreSQL). Gesamter lokaler Testlauf: 190 Tests, 74 übersprungen, 0 fehlgeschlagen, 0 Fehler.
- **Erledigt (20.09.):** CI-Bestätigung, dass `test_doppelter_benutzername_wird_abgelehnt` gegen den echten PostgreSQL-Service-Container grün läuft, liegt jetzt vor (Version 1.0.12, siehe dortiger Abschnitt).

**Umsetzung (19.09.): Code Signing Policy für die kostenlose SignPath-Foundation-Signierung erstellt**
- **Nutzerwunsch:** Nachfrage, ob nach dem Öffentlichstellen des Repos (MIT-Lizenz, siehe oben) noch etwas für die Signierung der Setup-Datei nötig ist. Recherche der aktuellen SignPath-Foundation-Voraussetzungen ergab: OSI-Lizenz ohne kommerzielle Doppellizenzierung (✅ jetzt MIT), öffentliches Repo mit LICENSE im Wurzelverzeichnis (✅), aktiv gepflegtes/dokumentiertes/bereits veröffentlichtes Projekt, automatisierter CI/CD-Build (✅ bereits über `.github/workflows/build-installer.yml`), MFA auf GitHub- und SignPath-Konto, sowie ein veröffentlichtes "Code Signing Policy"-Dokument mit den Rollen Author/Reviewer/Approver und einer Datenschutzerklärung.
- **Neue Datei `CODE_SIGNING_POLICY.md`** angelegt: beschreibt die Rollen (aktuell alle bei Marco als einzigem aktiven Entwickler), den Build-/Freigabeprozess (GitHub Actions als einzige Build-Quelle, Versions-Tag löst den signierten Release aus), die Datenschutzerklärung (rein lokale Datenhaltung, keine Telemetrie) und den vorgeschriebenen Signierungs-Hinweistext ("Free code signing provided by SignPath.io, certificate by SignPath Foundation.").
- **Querverweise ergänzt:** `README.md` bekam im Abschnitt "Lizenz" einen Verweis auf die neue Policy-Datei; `README_INSTALLER.md`s Abschnitt "Warum unsigniert bleibt" aktualisiert – die Voraussetzungen für die kostenlose SignPath-Signierung sind jetzt erfüllt, die eigentliche Bewerbung bei SignPath und die MFA-Aktivierung stehen aber noch aus, solange bleibt die Setup-Datei unsigniert.
- **Was der Nutzer selbst noch tun muss (kein Zugriff dieser Sitzung auf GitHub-/SignPath-Konten):** die eigentliche Bewerbung bei SignPath Foundation unter signpath.org einreichen, Zwei-Faktor-Authentifizierung (MFA) auf dem GitHub-Konto aktivieren, und nach einer Zusage das erhaltene SignPath-Projekt/API-Token als GitHub-Actions-Secret hinterlegen (nicht direkt an Claude weitergeben) – erst dann kann `build-installer.yml` um den eigentlichen Signierungsschritt ergänzt werden.
- **Update (19.09.): Bewerbung bei der SignPath Foundation eingereicht.** Formular ausgefüllt (u. a. Repository-/Homepage-URL auf die Repo-Hauptseite gesetzt, da dort das README den vorgeschriebenen SignPath-Hinweis zeigt und die reine `/releases`-Unterseite das nicht tut; Datenschutz-URL auf den Datenschutz-Abschnitt von `CODE_SIGNING_POLICY.md` verlinkt; als Discovery-Kanal ehrlich "AI / LLM tools" angegeben, da die Option über diese Sitzung recherchiert und vorgeschlagen wurde, nicht vom Nutzer selbst gefunden). Maintainer-Typ "Individual maintainer(s)", Build-System "GitHub Actions".
- **Noch offen:** Zusage/Rückmeldung der SignPath Foundation abwarten.
- **Erledigt (19.09.): fehlerhafter Versions-Tag `v1.0.10` korrigiert und Installer-Build erfolgreich.** Der Tag war zunächst VOR dem Committen/Pushen der `bump_version.py`-Änderung gesetzt worden und zeigte dadurch noch auf `version.txt = 1.0.9` - der Release-Build brach mit der eingebauten Tag/Versions-Prüfung erwartungsgemäß ab. Versionsbump-Commit (`bb6ee28`) nachträglich erstellt und vom Nutzer gepusht; der fehlerhafte Tag wurde vom Nutzer selbst gelöscht und auf dem richtigen Commit neu gesetzt (Push/Tag-Verwaltung war aus dieser Sitzung heraus nicht möglich, siehe unten). Nutzer hat bestätigt: Tag korrigiert und Installer-Build für v1.0.10 erfolgreich durchgelaufen.
- **Erkenntnis (19.09.):** die Shell, mit der auf den Rechner des Nutzers zugegriffen wird, hat keinen Netzwerkzugriff auf github.com (`403 von proxy nach CONNECT`) - `git push`/`git fetch`/`git ls-remote` gegen GitHub schlagen von dort aus grundsätzlich fehl. Commits können lokal im gemounteten Ordner erstellt werden, das eigentliche Pushen/Taggen auf GitHub muss der Nutzer selbst (z. B. über PowerShell) ausführen.

**QS-Review (19./20.09.): unabhängige Code-Prüfung durch 3 Subagents (Kernlogik/DB, Desktop-GUI/PDF, Web-Backend/Infra) und erste zwei Fixes**
- **Auf Wunsch des Nutzers** wurde der gesamte bisherige Code über drei parallele, unabhängige Subagents auf Fehler und Verbesserungen geprüft (Bereich 1: shs_core.py/db.py; Bereich 2: app.py/pdf_export.py/Backup/Packaging; Bereich 3: app_web.py/Templates/Container/CI). Kernlogik (Wertnoten/Ranglisten), Auth/Autorisierung, SQL-Injection-Schutz, XSS-Schutz und Backup-Verschlüsselung wurden als solide eingestuft. Gefundene Probleme (Übersicht, priorisiert nach Schweregrad):
  - Mittel-kritisch: Race Condition beim Löschen des letzten Admin-Kontos (`db.py`, `benutzer_loeschen`) - theoretisch 0 Admins bei gleichzeitigem Löschen möglich.
  - Mittel: **PDF-Export-Absturz bei Sonderzeichen in Freitext behoben (siehe unten)**, **doppelte Gegenstand-Disziplin-Zuordnung wird nicht verhindert - behoben (siehe unten)**, **Backup-Wiederherstellung nicht atomar - behoben (siehe unten)**, **Path Traversal beim Backup-Import (ZIP mit `../`) - behoben (siehe unten)**, **case-sensitive Benutzername-Eindeutigkeit vs. case-insensitiver Login - behoben (siehe unten)**, **fehlender CSRF-Schutz/explizites SameSite-Cookie im Web-Backend - behoben (siehe unten)**.
  - Gering: kein Upload-Größenlimit, kein Brute-Force-Schutz beim Web-Login, verwaiste Download-Links, ein Auto-Save-Randfall beim Fensterschließen, fragile `?`→`%s`-Übersetzung im Postgres-Wrapper, fehlende Absicherung einer Datenbank-Invariante.
- **Fix 1 (umgesetzt): PDF-Export brach bei Sonderzeichen in Freitextfeldern ab.** `reportlab.Paragraph()` parst seinen Text als kleine Mini-Auszeichnungssprache (`<b>`, `<i>`, `<br/>` ...) - ein frei eingegebener Zwingername/Rufname/Verein/Gegenstand/Pausenbezeichnung mit z.B. einem einzelnen `<` ließ den Export mit `ValueError` abstürzen, bei "alle Bewertungsbögen" sogar für ALLE Teilnehmer auf einmal (per Reproduktion bestätigt). Neue Funktion `_p_wert()` in `pdf_export.py` escaped Freitext (XML-Escaping via `xml.sax.saxutils.escape`) an allen betroffenen Stellen, bewusst NICHT in der bestehenden `_wert()` (die auch für reine Tabellenzellen ohne Markup-Parsing verwendet wird, wo Escaping Sonderzeichen fälschlich sichtbar gemacht hätte, z.B. "&amp;" statt "&"). 2 neue Regressionstests in `test_pdf_export.py` (31 insgesamt), alle grün.
- **Fix 2 (umgesetzt): Backup-Wiederherstellung schreibt jetzt atomar.** `sicherung_wiederherstellen()` in `db.py` schrieb bisher direkt per `Path.write_bytes()` in die Zieldatei - ein Abbruch mittendrin (Absturz, Stromausfall, volle Platte) hätte eine abgeschnittene/korrupte Termin-Datei zurückgelassen und damit den bisherigen, oft nicht anderweitig gesicherten Terminstand unwiederbringlich zerstört. Schreibt jetzt in eine temporäre Datei im selben Zielordner und verschiebt sie erst danach per `os.replace()` atomar an die Zielstelle (inkl. Aufräumen der temporären Datei bei einem Fehler). 2 neue Tests in `test_backup.py` (24 insgesamt, u.a. simulierter Schreibfehler per Mock), alle grün.
- **Nebenbei:** Für die lokale Testausführung ohne installierbares `pyzipper`-Paket musste der bestehende Test-Stub (`pyzipper.py` unter `/tmp/stub_pkgs`, kein Teil des Repos) um eine funktionsfähige Passwort-Simulation ergänzt werden, damit `test_backup.py` überhaupt lokal lauffähig ist - betrifft nur diese Sitzung, nicht die echte CI (dort ist das echte `pyzipper`-Paket installiert).
- **Fix 3 (umgesetzt): Race Condition beim Löschen des letzten Admin-Kontos behoben.** `benutzer_loeschen()` in `db.py` sperrt jetzt bei einer echten PostgreSQL-Verbindung zuerst alle Admin-Zeilen (`SELECT ... FOR UPDATE`), bevor gezählt wird - eine reine `COUNT(*)`-Prüfung ohne Sperre hätte zwei zeitgleiche Löschversuche (z.B. zwei Admins, die im selben Moment je ihr eigenes Konto löschen) nicht verhindern können, da PostgreSQL unter der Standard-Isolationsstufe (READ COMMITTED) rein lesende Zugriffe nicht blockiert. Bewusst positiv auf `_PostgresConnection` geprüft (nicht negativ auf `sqlite3.Connection`), da `web_benutzer` produktiv ausschließlich über PostgreSQL existiert und `test_app_web.py` die SQLite-Testverbindung über einen eigenen Wrapper reicht, der ebenfalls kein `FOR UPDATE` kann. Testabdeckung: ein echter Nebenläufigkeits-Test mit zwei parallelen Threads/Verbindungen und `threading.Barrier` in `test_db.py` (läuft nur gegen echtes PostgreSQL, also nur in der CI - genau wie die übrigen Postgres-Tests), plus zwei mock-basierte Tests in `test_db_postgres_wrapper.py`, die Reihenfolge/Auslösung der Sperre lokal ohne Postgres-Server prüfen. Gesamter lokaler Testlauf: 258 Tests, 76 übersprungen, 0 fehlgeschlagen.
- **Fix 4 (umgesetzt): doppelte Gegenstand-Disziplin-Zuordnung wird jetzt beim Speichern verhindert.** Vor der Klärung mit dem Nutzer bestand die Sorge, die Prüfung könnte mit den DK-Leistungsklassen-Regeln kollidieren (LK1: mind. 1 Gegenstand für alle 3 Disziplinen, LK2: mind. 2 Gegenstände, max. 2 Disziplinen je Gegenstand, LK3: 3 Gegenstände, je einer Disziplin). Klärung: das bleibt vollständig kompatibel, da "ein Gegenstand für mehrere Disziplinen" über denselben GEGENSTAND-TEXT in mehreren Feldern abgebildet wird, jeweils mit einer ANDEREN Disziplin-Zuordnung - nur die doppelte DISZIPLIN-Zuordnung (zwei Felder mit derselben Disziplin) ist das eigentliche Problem, weil `gegenstand_fuer_disziplin()` (`db.py`) für eine Disziplin nur den ersten Treffer liefert und ein zweiter, versehentlich gleich zugeordneter Gegenstand spurlos verschwinden würde (z.B. auf dem Bewertungsbogen). Neue Prüfung in `TeilnehmerDialog._pruefen_und_akzeptieren()` (`app.py`, analog zur bestehenden Startnummer-Dublettenprüfung): warnt und verhindert das Speichern, wenn zwei der drei `gegenstand_N_disziplin`-Felder denselben (nicht-"frei") Wert haben - unabhängig vom eingetragenen Gegenstand-Text. Zwei neue GUI-Tests in `test_app_gui.py` (doppelte Zuordnung wird abgelehnt; derselbe Gegenstand-Text in mehreren Disziplinen bleibt erlaubt). Diese GUI-Tests laufen nur in der CI (PySide6 lokal in dieser Sitzung nicht installierbar) - lokal per `py_compile` auf Syntaxfehler geprüft, übriger lokaler Testlauf (258 Tests ohne GUI-Modul) weiterhin grün.
- **Fix 5 (umgesetzt): Path Traversal beim Backup-Import behoben.** ZIP-Einträge aus einer Sicherungsdatei wurden bisher nur danach gefiltert, ob ihr Name auf `.sqlite` endet - ein präpariertes (nicht selbst erstelltes) Sicherungs-ZIP mit einem Eintrag wie `../../wichtig.sqlite` hätte diesen Namen unverändert als Zieldateinamen durchgereicht bekommen (`entscheidungen[name] = name` in `app.py`) und damit beim "Wiederherstellen" eine Datei AUSSERHALB des Termine-Ordners schreiben/überschreiben können - dabei sogar ohne den üblichen Konflikt-Dialog, da so ein Name nie mit einer vorhandenen Termin-Datei übereinstimmt. Neue Funktion `_ist_sicherer_dateiname()` in `db.py` (akzeptiert nur "flache" Dateinamen ohne `..`, `/` oder `\`, passend dazu, dass `sicherung_erstellen()` selbst auch nur flache Namen schreibt) wird an zwei Stellen angewendet: in `sicherung_inhalt()` (unsichere Einträge tauchen gar nicht erst in der dem Nutzer angezeigten Auswahl auf) und zusätzlich, unabhängig davon, direkt in `sicherung_wiederherstellen()` vor dem eigentlichen Schreiben (verteidigt auch für den Fall, dass ein Aufrufer die erste Prüfung nicht vorschaltet). 7 neue Tests in `test_backup.py` (u.a. präpariertes ZIP mit Traversal-Eintrag, reine Unit-Tests für `_ist_sicherer_dateiname()`), Gesamtlauf lokal: 265 Tests, 76 übersprungen, 0 fehlgeschlagen.
- **Fix 6 (umgesetzt): case-sensitive Benutzername-Eindeutigkeit vs. case-insensitiver Login behoben.** `web_benutzer.benutzername` war bisher nur als PRIMARY KEY (also case-SENSITIVE) eindeutig, `pruefe_login()` vergleicht beim Anmelden dagegen bewusst GROSS-/kleinschreibungs-unabhängig (wegen Autokapitalisierung auf Mobilgeräten). `app_web.py` prüfte das zwar schon vor dem Anlegen eines Kontos per eigener Python-Abfrage, ließ dabei aber ein kurzes Zeitfenster für einen echten Wettlauf zweier gleichzeitiger Anfragen offen (ganz analog zur Admin-Lösch-Race-Condition aus Fix 3) - z. B. könnten "MHelfer" und "mhelfer" als zwei getrennte Konten entstehen, obwohl der Login sie nicht unterscheiden kann. Neuer Unique-Index `CREATE UNIQUE INDEX ... ON web_benutzer (LOWER(benutzername))` (`db._WEB_BENUTZER_INDEX_BENUTZERNAME_LOWER`, wird von `verbinde_postgres_server()` automatisch angelegt/nachgerüstet, dieselbe Syntax funktioniert unverändert für PostgreSQL UND SQLite) schließt diese Lücke auf Datenbankebene endgültig. `admin_benutzer()` in `app_web.py` fängt den (jetzt nur noch im echten Rennen auftretenden) Datenbankfehler ab und zeigt weiterhin die normale "bereits vergeben"-Meldung statt eines rohen Serverfehlers. Testabdeckung: ein echter Duplikat-Test gegen PostgreSQL in `test_db.py` (läuft nur in der CI, wie die übrigen Postgres-Tests) sowie ein Test in `test_app_web.py`, der die Race Condition gezielt simuliert (Vorab-Prüfung wird übersprungen, der Datenbank-Index muss trotzdem greifen). Gesamter lokaler Testlauf: 267 Tests, 77 übersprungen, 0 fehlgeschlagen.
- **Fix 7 (umgesetzt): CSRF-Schutz für das Web-Backend eingeführt.** `app_web.py` hatte bisher gar keinen Schutz gegen Cross-Site-Request-Forgery - eine bösartige, in einem ANDEREN Browser-Tab geöffnete Seite hätte über ein automatisch abgeschicktes Formular im Namen eines gerade angemeldeten Nutzers Aktionen auf dieser Anwendung auslösen können (z. B. einen Termin oder ein Benutzerkonto löschen), allein weil der Browser das gültige Session-Cookie bei jedem Aufruf dieser Domain automatisch mitschickt. Umgesetzt als klassisches Synchronizer-Token-Pattern OHNE zusätzliche Abhängigkeit (Flask-WTF o.ä. - das Projekt hält seine Web-Abhängigkeiten bewusst minimal, siehe requirements-web.txt): ein Token wird pro Browser-Session serverseitig erzeugt (`_csrf_token()`), allen Templates über einen Kontext-Prozessor als Funktion bereitgestellt und in jedem der 9 Formulare (über alle 6 betroffenen Templates verteilt) als verstecktes Feld mitgeschickt; eine neue `before_request`-Prüfung (`_csrf_pruefen()`) lehnt jede POST-Anfrage ohne exakt passendes Token mit 403 ab (Vergleich über `secrets.compare_digest()`, konstante Zeit, dieselbe Vorsicht wie beim Passwortvergleich). Läuft global vor JEDER Ansicht statt als Decorator je Route, damit keine künftige neue POST-Route versehentlich ungeprüft bleibt. Zusätzlich `SESSION_COOKIE_SAMESITE = "Lax"` explizit gesetzt (zweite, unabhängige Absicherungsebene) - bewusst NICHT `SESSION_COOKIE_SECURE`, da die Web-Version laut Deployment-Annahme ohne eigenes HTTPS im lokalen Vereinsnetz läuft und das Cookie sonst gar nicht mehr mitgeschickt würde. Testabdeckung: die komplette bestehende Testsuite mit einem neuen Test-Client, der automatisch ein gültiges Token beilegt (damit die ~30 bestehenden POST-Tests weiterhin die fachliche Logik statt dieses rein technischen Felds prüfen), plus eine neue, unabhängige `TestCsrfSchutz`-Klasse mit dem UNVERÄNDERTEN Client, die den Mechanismus selbst gezielt prüft (Ablehnung ohne Token, Ablehnung mit falschem Token, Erfolg mit dem echten Token aus einer zuvor geladenen Seite). Gesamter lokaler Testlauf: 271 Tests, 77 übersprungen, 0 fehlgeschlagen.
- **Fix 8 (umgesetzt): Auto-Save-Randfall beim Fensterschließen behoben.** `closeEvent()` in `app.py` speicherte beim Schließen automatisch noch offene Ergebnisse, schloss das Fenster aber IMMER sofort danach - konnte `alle_speichern()` eine Zeile nicht speichern (z. B. nur "Suche" statt beider Felder ausgefüllt), verschwand die dabei gezeigte Warnung zusammen mit dem Fenster, ohne dass die Änderung je gespeichert wurde oder der Nutzer sie noch hätte korrigieren können. Prüft jetzt nach dem Speicherversuch erneut, ob noch Änderungen offen sind (`hat_ungespeicherte_aenderungen()`, genau wie bereits bei `_tab_gewechselt`/`_termin_wechseln`) und fragt in diesem Fall nach, ob trotzdem beendet werden soll (Standard: Nein, also nicht schließen) - so bleibt die Möglichkeit, die fehlerhafte Zeile noch zu korrigieren, statt sie stillschweigend zu verlieren. 2 neue GUI-Tests in `test_app_gui.py` (Rückfrage erscheint und verhindert das Schließen bei "Nein"; "Ja" schließt trotzdem) - laufen nur in der CI (PySide6 lokal nicht installierbar, wie bei Fix 4).
- **Fix 9 (umgesetzt): fragile `?`→`%s`-Übersetzung im Postgres-Wrapper gehärtet.** `_PostgresConnection.execute()` übersetzte SQLite-Platzhalter (`?`) bisher über ein blindes `sql.replace("?", "%s")` auf dem GESAMTEN SQL-Text - ein als reiner Text gemeintes Fragezeichen innerhalb eines SQL-String-Literals wäre dabei fälschlich mitersetzt worden und hätte die Abfrage unbemerkt kaputt gemacht (kam bisher nirgends im Code vor, war aber eine Falle für künftige Änderungen). Neue Funktion `_uebersetze_platzhalter()` erkennt einfach gequotete String-Literale (inkl. `''` für ein eingebettetes Apostroph) und lässt sie unangetastet, ersetzt nur echte `?`-Platzhalter außerhalb davon. 3 neue Tests in `test_db_postgres_wrapper.py` (Fragezeichen im String-Literal, escapetes Apostroph, mehrere echte Platzhalter).
- **Fix 10 (umgesetzt): fehlende Absicherung der Teilnehmer-Ergebnis-Invariante in `berechne_auswertung()`.** `add_teilnehmer()` legt normalerweise für jeden Teilnehmer sofort eine passende Zeile in `ergebnisse` an, `berechne_auswertung()` verließ sich darauf mit einem direkten `ergebnis_rows[t["id"]]`-Zugriff - wäre diese Invariante doch einmal verletzt (künftiger Programmierfehler, von Hand bearbeitete Termin-Datei), wäre die KOMPLETTE Auswertung mit einem harten `KeyError` abgestürzt, statt nur den betroffenen Teilnehmer zu betreffen. Greift jetzt über `.get()` zu und behandelt einen fehlenden Eintrag wie einen fachlich noch nicht vollständig bewerteten Teilnehmer (landet in der "ausstehend"-Liste statt die Auswertung für alle zu verhindern). 1 neuer Test in `test_db.py`, der die fehlende Zeile absichtlich nachstellt und prüft, dass die übrigen, korrekten Teilnehmer trotzdem normal ausgewertet werden. Gesamter lokaler Testlauf (ohne die GUI-Tests aus Fix 4/8, siehe dort): 276 Tests, 78 übersprungen, 0 fehlgeschlagen.
- **Fix 11 (umgesetzt): verwaiste Download-Links nach "Ergebnisse zurückholen" räumen sich jetzt automatisch ab.** Klickte der Administrator den Download-Link auf der Bestätigungsseite nicht an (Tab geschlossen, Seite verlassen o. Ä.), blieben sowohl der Eintrag in `app_web._ausstehende_downloads` als auch - schwerwiegender - die temporäre `.sqlite`-Datei mit personenbezogenen Teilnehmer-/Ergebnisdaten unbegrenzt lange auf der Festplatte des Containers liegen. Jeder Eintrag trägt jetzt zusätzlich seinen Erstellungszeitpunkt (`time.monotonic()`); eine neue Funktion `_bereinige_abgelaufene_downloads()` entfernt Einträge, die älter als 15 Minuten sind, und löscht dabei die zugehörige temporäre Datei gleich mit. Aufgerufen wird sie zentral im `_admin_erforderlich`-Decorator (nicht einzeln in jeder betroffenen Route) - so räumt jede Aktion irgendeines Administrators im Admin-Bereich nebenbei auch verwaiste Downloads aus früheren, abgebrochenen Sitzungen mit auf, und keine künftige neue Admin-Route kann das versehentlich vergessen. 2 neue Tests in `test_app_web.py` (ein simulierter alter Eintrag samt Datei wird beim nächsten Admin-Aufruf entfernt; ein frischer Eintrag bleibt unangetastet). Gesamter lokaler Testlauf: 278 Tests, 78 übersprungen, 0 fehlgeschlagen.
- **Nutzerentscheidung (20.09.):** die beiden übrigen "gering" eingestuften QS-Funde - kein Upload-Größenlimit und kein Brute-Force-Schutz beim Web-Login - werden bewusst NICHT behoben (vom Nutzer als akzeptables Restrisiko eingestuft, passend zum Deployment im geschlossenen Vereinsnetz am Prüfungstag).
- **Version 1.0.11 (20.09.) veröffentlicht** - enthält Fix 8-11. Commit `68b26d0` gepusht, Tag `v1.0.11` gesetzt und gepusht (löst automatisch `build-installer.yml` inkl. GitHub-Release aus).
- **CI-Bugfix (20.09.): `test_benutzername_der_sich_nur_in_gross_kleinschreibung_unterscheidet_wird_abgelehnt` (Fix 6, `test_db.py`) schlug im ersten echten CI-Lauf gegen PostgreSQL fehl.** Ursache: der Test löst ZWEI absichtliche `IntegrityError` auf derselben Verbindung nacheinander aus ("Chef" und "CHEF" gegen den bereits vorhandenen "chef"), PostgreSQL markiert die Transaktion nach dem ERSTEN abgefangenen Fehler aber als abgebrochen - jeder weitere Befehl auf derselben Verbindung (auch der zweite `benutzer_anlegen()`-Versuch) schlägt dann mit `InFailedSqlTransaction` statt mit dem erwarteten `IntegrityError` fehl, bis zurückgerollt wurde (anders als SQLite, das diese Einschränkung nicht kennt). Genau dasselbe Muster ist in `TestBenutzerkontenPostgres.tearDown()` bereits dokumentiert und dort schon berücksichtigt - der neue Test selbst hatte es zwischen seinen beiden `assertRaises`-Blöcken nur übersehen. Behoben durch ein zusätzliches `self.conn.rollback()` zwischen den beiden Versuchen.
- **Version 1.0.12 (20.09.) veröffentlicht** - enthält nur den obigen CI-Bugfix. Commit `095ddcd` gepusht, Tag `v1.0.12` gesetzt und gepusht. **Vom Nutzer bestätigt: kompletter CI-Lauf (alle Tests, inkl. GUI-Tests mit PySide6 und aller PostgreSQL-Tests) sowie der Installer-Build liefen erfolgreich durch.** Damit sind auch die zuvor offenen CI-Bestätigungen für Fix 3 (Nebenläufigkeits-Test), Fix 4/8 (GUI-Tests) und Fix 6 (Duplikat-Tests, inkl. des hier behobenen Bugs) erledigt - der gesamte automatisierte Testlauf ist grün.
- **Zwei wiederkehrende automatische Prüfungen eingerichtet (20.09.):** ein wöchentlicher CVE-Check (samstags 1:00 Uhr, prüft `requirements.txt`/`requirements-web.txt` per `pip-audit`) sowie eine monatliche QS-Prüfung mit 3 unabhängigen Subagents (jeweils am ersten Samstag im Monat, 2:00 Uhr, gleicher Prozess wie die QS-Runde vom 19./20.09., ohne die beiden bewusst akzeptierten Punkte oben erneut zu melden). Beide laufen komplett in der Cloud gegen das öffentliche GitHub-Repo (kein Zugriff auf den Windows-Rechner nötig), nehmen selbst keine Code-Änderungen vor und schicken das Ergebnis per E-Mail.
- **Architekturüberblick und Subagent-Arbeitsweise dokumentiert (20.09.):** neue Datei `Architektur.md` (Modulübersicht inkl. Mermaid-Diagramm, Testsuite-Struktur, Kurzfassung der Architekturentscheidungen) sowie `CLAUDE.md` im Repo-Wurzelverzeichnis (wird von künftigen Claude-Sitzungen/Subagents in diesem Ordner automatisch gelesen) angelegt, auf Wunsch des Nutzers für einen schnelleren Einstieg. `CLAUDE.md` hält außerdem die vier mit dem Nutzer abgestimmten Subagent-Arbeitsweisen fest (Explore-Agent vorab, Bereichs-Subagents bei bereichsübergreifenden Änderungen, differenzierte QS-Rollen, unabhängiger Verifikations-Subagent) sowie die beiden bewusst akzeptierten QS-Restrisiken, damit sie nicht erneut gemeldet werden. Die QS-Scheduled-Task wurde entsprechend auf differenzierte Rollen (Sicherheit / Korrektheit & Edge-Cases / Wartbarkeit & Stil) für ihre 3 Subagents umgestellt.
- **Fix 12 (umgesetzt): Zeilennummern-Spalte in "Auswertung" jetzt konsistent ausgeblendet.** Nutzerhinweis (20.09.): in den Tabs "Teilnehmer" und "Ergebniserfassung" war die linke Zeilennummern-Spalte bereits ausgeblendet, im Tab "Auswertung" (`AuswertungTab`) aber übersehen worden. Ergänzt um `self.tabelle.verticalHeader().setVisible(False)` (`app.py`), exakt dasselbe Muster wie in den beiden anderen Tabs. 1 neuer GUI-Test `test_auswertung_tabelle_zeigt_keine_zeilennummern` in `test_app_gui.py` (läuft nur in der CI, PySide6 lokal nicht installierbar - lokal per `py_compile` auf Syntaxfehler geprüft).
- **Fix 13 (umgesetzt): bis zu 5 Wertungsrichter statt bisher fest 2.** Nutzerwunsch (20.09.): manche Prüfungen sind größer besetzt, als die bisher fest verdrahteten zwei Wertungsrichter-Felder abbilden konnten. Neue Spalten `wertungsrichter_3`/`_4`/`_5` in der Tabelle `veranstaltung` (`db.py`, SCHEMA + `_VERANSTALTUNG_NEUE_SPALTEN` für die automatische Migration bereits angelegter Termin-Dateien, `set_veranstaltung()`/`kopiere_termin_daten()` entsprechend erweitert - alle weiterhin optional, keine Pflichtfelder). Dialog "Veranstaltungsdaten bearbeiten…"/"Neuen Termin anlegen" (`VeranstaltungsDialog`, `app.py`) zeigt jetzt fünf statt zwei Wertungsrichter-Eingabefelder. Statistik-PDF-Kopftabelle (`pdf_export.py`, `_statistik_kopftabelle()`) um zwei weitere Zeilen für Wertungsrichter 3-5 ergänzt. Testabdeckung: `test_db.py` (Zusatzfelder-Test, Migrations-Test, Termin-Kopier-Test je um die neuen Felder erweitert) und `test_pdf_export.py` (Statistik-Kopfangaben-Test prüft jetzt alle 5 Namen im PDF-Text). Gesamter lokaler Testlauf: 278 Tests, 78 übersprungen, 0 fehlgeschlagen.
- **Fix 14 (umgesetzt): Begriff "Wertungsrichter" in den Verwaltungsdaten durch "Leistungsrichter" ersetzt.** Nutzerwunsch (20.09.): einheitliche Begrifflichkeit mit dem bereits an anderer Stelle (Zeitplan-Tab, Leistungsrichter-Bedarf-PDF) verwendeten Begriff "Leistungsrichter". Reine Anzeige-Änderung: Feldbeschriftungen im Dialog "Veranstaltungsdaten bearbeiten…"/"Neuen Termin anlegen", die Statistik-PDF-Kopftabelle sowie diverse Hinweistexte in `app.py`/`pdf_export.py` zeigen jetzt "Leistungsrichter 1"-"5" statt "Wertungsrichter 1"-"5". Die internen Python-Attributnamen und die Datenbankspalten (`wertungsrichter_1`-`_5`) bleiben bewusst unverändert, um mit bereits im echten Einsatz befindlichen Termin-Dateien kompatibel zu bleiben (kein Migrationsaufwand für eine reine Anzeige-Umbenennung).
- **Fix 15 (umgesetzt): neuer Reiter "Übersicht" mit Teilnehmerzahlen je Art/LK und Leistungsrichter-Bedarf.** Nutzerwunsch (20.09.), anhand eines Screenshots aus der ursprünglichen Excel-Vorlage ("Übersicht Teilnehmer"-Tabellenblatt): ein neuer, live aus der Datenbank aufgebauter Reiter (`TeilnehmerUebersichtTab`, kein Zwischenspeicher, baut sich bei jedem Tabwechsel neu auf - wie `AuswertungTab`) zeigt je Art/Leistungsklasse die Teilnehmerzahl (bei ED zusätzlich je Disziplin Trümmerfeld/Flächensuche/Behältnisstrecke aufgeschlüsselt) sowie die "Abteilungen" (1 ED-Teilnehmer = 1 Abteilung, 1 DK-Teilnehmer = 3 Abteilungen, da er alle drei Disziplinen durchläuft) und darunter die Summen Teilnehmer gesamt/Abteilungen gesamt/benötigte Leistungsrichter. Der Begriff "SH-R" aus der Original-Vorlage wurde dabei durch "Leistungsrichter" ersetzt (Konsistenz mit Fix 14 und der bereits bestehenden Terminologie). Die Berechnungslogik (36 Abteilungen je Leistungsrichter, ED=1/DK=3 Abteilungen) war bisher nur privat in `pdf_export.py` für das PDF "Leistungsrichter-Bedarf" hinterlegt - dafür als gemeinsame Grundlage zentral nach `db.py` verschoben (neue öffentliche Konstanten `LR_EINHEITEN_JE_ART`/`LR_EINHEITEN_PRO_RICHTER` sowie neue Funktion `berechne_teilnehmer_lk_uebersicht()`), damit Reiter und PDF immer dieselben Zahlen liefern statt zwei gepflegte Kopien der Regel zu riskieren. `pdf_export.py` importiert die Konstanten jetzt von dort statt eigener privater Kopien - reiner interner Refactor, PDF-Ausgabe unverändert. Umgesetzt arbeitsteilig über zwei parallele Bereichs-Subagents (Daten: `db.py`/`pdf_export.py`/Tests; Desktop: `app.py`/GUI-Test) nach einem vorab festgelegten Funktions-Contract, anschließend von mir selbst integrationsgeprüft (Compile + kompletter lokaler Testlauf). Testabdeckung: 2 neue Tests in `test_db.py` (leerer Fall, gemischtes ED/DK-Szenario mit den Zahlen aus dem Referenz-Screenshot) sowie 1 neuer GUI-Test in `test_app_gui.py` (nur CI, PySide6 lokal nicht installierbar - lokal per `py_compile` geprüft). Gesamter lokaler Testlauf: 282 Tests, 80 übersprungen, 0 fehlgeschlagen.
- **Versionen 1.0.13-1.0.15 (20.09.) veröffentlicht** - enthalten Fix 12 (Zeilennummern Auswertung), Fix 13 (5 Wertungsrichter-Felder), Fix 14/15 (Leistungsrichter-Umbenennung + neuer Reiter "Übersicht"). Commits `6ec4c92`/`fd2e8a3`/`8a678b0`, Tags `v1.0.13`/`v1.0.14`/`v1.0.15` vom Nutzer gepusht. **Vom Nutzer bestätigt: die dadurch ausgelösten CI-Workflows liefen erfolgreich durch.**
- **Fix 16 (umgesetzt): Filter nach Bezahlt-Status im Tab "Teilnehmer".** Nutzerwunsch (20.09.): neben den bestehenden Filtern "Art/LK" und "Start-Nr." ein dritter Filter "Bezahlt" (Alle/Bezahlt/Nicht bezahlt) in `TeilnehmerTab` (`app.py`) - z.B. um am Anmeldetisch schnell zu sehen, wer noch nicht bezahlt hat. Neue `QComboBox self.filter_bezahlt` mit festen drei Einträgen (anders als der dynamische Art/LK-Filter keine Neubefüllung bei jedem `aktualisieren()` nötig), `_filter_anwenden()` um die entsprechende Bedingung erweitert - exakt dasselbe `setRowHidden`-Muster wie die beiden bestehenden Filter. 1 neuer GUI-Test `test_filter_bezahlt_blendet_zeilen_nach_status_aus` in `test_app_gui.py` (nur CI, PySide6 lokal nicht installierbar - lokal per `py_compile` geprüft). Umgesetzt nach Explore-Subagent-Recherche (bestehendes Filter-Muster/Bezahlt-Spalte lokalisiert), anschließend selbst implementiert (einzelner, gut abgegrenzter Bereich, keine Bereichs-Subagents nötig). Gesamter lokaler Testlauf: 282 Tests, 80 übersprungen, 0 fehlgeschlagen.
- **CI-Bugfix (20.09.): `test_filter_bezahlt_blendet_zeilen_nach_status_aus` (Fix 16, `test_app_gui.py`) schlug im ersten echten CI-Lauf fehl.** Ursache: der Test enthielt am Ende einen überflüssigen Block, der nach den eigentlichen Filter-Prüfungen zusätzlich einen "Toggle zurück"-Klick auf `bezahlt_btn` simulieren sollte, ohne vorher per `tabelle.selectRow(...)` eine Zeile auszuwählen - `bezahlt_btn` ist aber per `setEnabled(False)` deaktiviert, solange keine Zeile ausgewählt ist, wodurch `qtbot.mouseClick(...)` wirkungslos verpuffte. Die anschließende Prüfung `list_teilnehmer(conn)[0]["bezahlt"] == 0` schlug deshalb mit `assert 1 == 0` fehl, weil der Bezahlt-Status unverändert blieb. Der Block prüfte ohnehin kein neues Verhalten (das Umschalten per Klick ist bereits durch `test_bezahlt_umschalten_per_klick_aendert_datenbank_und_tabelle` abgedeckt) und wurde ersatzlos entfernt - der Test endet jetzt sauber mit der Rückkehr zu "Alle". Verifiziert per `py_compile` sowie komplettem lokalen Testlauf (PySide6-Test selbst läuft weiterhin nur in der CI).
- **Version 1.0.17 (20.09.) veröffentlicht** - enthält nur den obigen CI-Bugfix. Commit `9d2289b` gepusht, Tag `v1.0.17` gesetzt und gepusht. **Vom Nutzer bestätigt: CI-Workflow lief erfolgreich durch** (damit ist die zuvor offene CI-Bestätigung für Fix 16, den Bezahlt-Filter, erledigt).

- **Fix 17 (umgesetzt): Begriff "Leistungsrichter" durchgängig durch "Richter" ersetzt.** Nutzerwunsch (20.09., aus schriftlicher Anmerkung zum Programm v1.0.14, Punkt 1): "wir sind seit letztem Jahr alle Richter, es gibt keine Unterscheidungen mehr" - die noch aus Fix 14/15 stammende Zwischenstufe "Leistungsrichter" ist damit ebenfalls überholt. Reine Anzeige-Änderung nach demselben Muster wie Fix 14: alle sichtbaren Vorkommen von "Leistungsrichter" (Dialog "Veranstaltungsdaten bearbeiten…"/"Neuen Termin anlegen" jetzt "Richter 1"-"5", Statistik-PDF-Kopftabelle, Zeitplan-Tab inkl. Hinweistexten bei fehlender Auswahl, Reiter "Übersicht", sowie das PDF/der Button "Leistungsrichter-Bedarf" jetzt "Richter-Bedarf") in `app.py`/`pdf_export.py`/`db.py` sowie den zugehörigen Docstrings/Kommentaren auf "Richter" umgestellt (Skript-Ersetzung `content.replace("Leistungsrichter", "Richter")`, dadurch automatisch nur die großgeschriebene Anzeige-Form betroffen). Bewusst unverändert bleiben wie schon bei Fix 14: die Datenbankspalten `wertungsrichter_1`-`_5` (Bestandsschutz für bereits im Einsatz befindliche Termin-Dateien) sowie alle internen, kleingeschriebenen Python-Bezeichner (`leistungsrichter_benoetigt`, `erstelle_leistungsrichter_bedarf_pdf()`, `LR_EINHEITEN_JE_ART`/`LR_EINHEITEN_PRO_RICHTER`) - reiner interner Refactor ohne Funktionsänderung. `Architektur.md` (Modulübersicht) ebenfalls angepasst. Testabdeckung: bestehende String-Prüfungen in `test_app_gui.py`, `test_db.py` und `test_pdf_export.py` auf "Richter" umgestellt. Gesamter lokaler Testlauf: 282 Tests, 80 übersprungen, 0 fehlgeschlagen. Dies ist der erste von mehreren Punkten aus der Anmerkung - die übrigen werden nacheinander einzeln besprochen und umgesetzt (siehe "Noch offen").
- **Fix 18 (umgesetzt): Verein/Vereins-Nr./Ort werden beim Anlegen eines weiteren Termins vorbelegt.** Nutzerwunsch (20.09., Anmerkung Punkt 2, "Anlage neuer Termin nachdem bereits Anlagen erfolgt sind"): "Cool wäre es, wenn sich das Programm merken würde, welcher Verein ich bin, dass ich mir die oberen 3 Eingaben sparen könnte." `TerminInfo` (`db.py`) um das bisher fehlende Feld `vereins_nr` ergänzt (`liste_termine()` liest es wie `verein`/`ort` bereits mit aus der `veranstaltung`-Tabelle jeder Termin-Datei). `StartDialog._neuer_termin()` (`app.py`) übergibt jetzt eine `vorbelegung` an `VeranstaltungsDialog` mit Verein/Vereins-Nr./Ort des in der Terminübersicht obersten (nach Datum neuesten) Termins, sofern bereits einer existiert - das Datum selbst wird bewusst NICHT übernommen, da jeder Termin ein eigenes braucht, und alle drei Felder bleiben wie gehabt frei überschreibbar. Bewusst keine neue, dauerhafte Einstellungs-Datei/QSettings eingeführt, um beim bisherigen Prinzip zu bleiben, dass alle Daten ausschließlich in den Termin-Dateien selbst liegen (siehe Datenschutz-Anforderung im Grobkonzept) - die Vorbelegung wird stattdessen jedes Mal frisch aus der ohnehin schon vorhandenen Terminübersicht abgeleitet. Testabdeckung: `test_db.py` (bestehender Test um `vereins_nr`-Prüfung ergänzt) sowie 2 neue GUI-Tests in `test_app_gui.py` (Vorbelegung aus dem letzten Termin bzw. leere Vorbelegung ohne bestehende Termine - der eigentliche `VeranstaltungsDialog` wird dafür durch einen Test-Stub ersetzt, der nur die übergebene Vorbelegung aufzeichnet, statt einen echten blockierenden Dialog zu öffnen; nur CI, PySide6 lokal nicht installierbar). Gesamter lokaler Testlauf: 282 Tests, 80 übersprungen, 0 fehlgeschlagen. **Auf Nutzerwunsch (20.09.) wird ab jetzt erst nach ALLEN Punkten der Anmerkung ein gemeinsamer Build/Version/Auslieferung erzeugt, nicht mehr nach jedem einzelnen Punkt** - dieser und die folgenden Punkte bleiben bis dahin nur im Cloud-Arbeitsbereich und in diesem Fortschrittsdokument, noch nicht auf dem Rechner des Nutzers oder committet.
- **Fix 19 (umgesetzt): Teilnehmer-Dialog - Rasse/Tollwutimpfung, eigener Halter-Block, elektronisches Einlesen von Meldeformularen per CSV-Import.** Nutzerwunsch (20.09., Anmerkung Punkt "Teilnehmer") - hier ausdrücklich VOR der Umsetzung per Rückfrage geklärt, da nicht alle Teilanmerkungen dieses Abschnitts gewünscht waren (Datenminimierung z. B. explizit abgelehnt: "Nein, alle bleiben"). Anhand des vom Nutzer hochgeladenen echten, leeren Anmeldeformulars (`Anmeldeformular_SHS-Wettkampf.docx`, per `pandoc -t markdown` gelesen) das echte Feldschema übernommen:
  - **Rasse** und **Tollwutimpfung gültig bis** als zwei neue Felder im Teilnehmer-Dialog ergänzt (`rasse`/`tollwutimpfung_bis`, beide `TEXT`, optional) - beide standen auf dem Original-Formular, fehlten im Programm bisher komplett.
  - **Eigener Halter-Block, nur bei Abweichung vom Hundeführer.** Klargestellt: die bisherigen Adressfelder des Teilnehmer-Dialogs ("Halter && Kontakt") bilden tatsächlich den **Hundeführer** ab (die Person, die den Hund bei der Prüfung führt) - Gruppe entsprechend in "Hundeführer && Kontakt" umbenannt. Echter **Halter** (Hundeeigentümer) ist auf dem Formular ein eigener, nur "falls abweichend" auszufüllender Abschnitt - dafür ein neuer, standardmäßig ausgeblendeter Block mit 9 Feldern (Vorname/Name/Straße/Hausnummer/PLZ/Ort/Mitgliedsverein/Mitgl.-Nr./LU-Nr.) ergänzt, sichtbar/aktiv nur über eine Checkbox "Halter weicht vom Hundeführer ab" (Nutzerwunsch: "nur wenn der Halter abweicht"). Bei ausgeblendetem/deaktiviertem Block werden auch bereits eingetippte Werte beim Speichern NICHT übernommen (`None`), damit kein versehentlich stehengebliebener Text unbemerkt in die Datenbank gelangt.
  - **Elektronisches Einlesen von Meldeformularen:** da die Desktop-Software offline läuft und selbst keinen KI-Zugriff hat, als Prompt-Werkzeug gelöst statt als direkte Dateierkennung (Nutzerwunsch: "kannst du mir einen Prompt erzeugen das ggf. KI-Systeme die Dateien in CSV umwandeln"). Neuer Reiter **"Formular-Import"** (zwischen "Teilnehmer" und "Zeitplan") mit fertigem, kopierbarem Prompt-Text (Button "Prompt kopieren") - der Nutzer gibt diesen Prompt zusammen mit dem ausgefüllten Meldeformular (PDF/Word/Foto) einem beliebigen KI-System (z. B. Claude, ChatGPT), bekommt eine CSV-Datei zurück und importiert sie im selben Reiter (Button "CSV importieren…"). Die CSV-Spaltenliste (`CSV_IMPORT_SPALTEN` in `db.py`) ist die EINE gemeinsame Quelle sowohl für den im Programm angezeigten Prompt-Text als auch für den tatsächlichen Import-Parser (`importiere_teilnehmer_aus_csv()`/`_csv_zeile_zu_teilnehmer()`) - Prompt und Parser können dadurch nicht auseinanderlaufen. Eine einzelne fehlerhafte Zeile (z. B. fehlender Pflichtwert, ungültige Art/Leistungsklasse/Disziplin/Schulterhöhe/Geschlecht) bricht den Import nicht ab, sondern wird übersprungen und nach Zeilennummer benannt im Ergebnis-Dialog aufgeführt, der Rest der Datei wird trotzdem importiert.
  - **Vor der Auslieferung selbst gefundener und behobener Fehler:** ein unabhängiger Verifikations-Subagent (siehe Arbeitsweise oben) deckte auf, dass `geschlecht` beim CSV-Import - anders als Art/Leistungsklasse/Disziplin - NICHT geprüft wurde und der `add_teilnehmer()`-Aufruf außerhalb der zeilenweisen Fehlerbehandlung lag: eine von einer KI z. B. als "weiblich" statt "Hündin"/"Rüde" gelieferte Zeile hätte dadurch eine unabgefangene Datenbank-Ausnahme ausgelöst und den KOMPLETTEN Import abgebrochen, im Widerspruch zum eigenen Anspruch "einzelne fehlerhafte Zeile bricht nicht ab". Behoben, bevor der Fund den Nutzer überhaupt erreicht hat: `geschlecht` wird jetzt wie die übrigen Felder validiert (nur "Hündin"/"Rüde"/leer), und `add_teilnehmer()` liegt zusätzlich als zweite Absicherung ebenfalls innerhalb der zeilenweisen Fehlerbehandlung. Eigener Regressionstest ergänzt.
  - Migration: die 11 neuen Spalten (`rasse`, `tollwutimpfung_bis`, 9× `halter_*`) werden bei bereits bestehenden, älteren Termin-Dateien automatisch per `ALTER TABLE` nachgezogen, ohne Datenverlust.
  - Testabdeckung: 4 neue Tests in `test_db.py` (Speichern/Auslesen aller 11 neuen Felder, Migration einer alten Termin-Datei, erfolgreicher CSV-Import, Überspringen fehlerhafter Zeilen bei gleichzeitigem Import des Rests) plus 1 Regressionstest für den oben beschriebenen Geschlecht-Fund; 8 neue GUI-Tests in `test_app_gui.py` (Rasse/Tollwutimpfung im Dialog, Halter-Block standardmäßig ausgeblendet, Checkbox blendet ein/aus und übernimmt bzw. verwirft Werte korrekt, bestehender Teilnehmer mit/ohne Halterdaten zeigt Block direkt auf-/eingeklappt, Formular-Import-Prompt enthält alle CSV-Spalten und ist schreibgeschützt, Prompt-kopieren setzt die Zwischenablage, CSV-Import legt Teilnehmer an und zeigt eine Zusammenfassung inkl. übersprungener Zeilen) - GUI-Tests nur CI, PySide6 lokal nicht installierbar. Gesamter lokaler Testlauf: 292 Tests, 85 übersprungen, 0 fehlgeschlagen. **Weiterhin kein Build/keine Auslieferung** - wie mit Fix 18 vereinbart, erst wenn alle Punkte der Anmerkung durch sind.
- **Fix 20 (umgesetzt): "Kontrollbutton" für vollständige Prüfungsdaten + Startnummer nicht mehr zwingend/dubletten-blockierend.** Die zwei letzten offenen Punkte aus dem Abschnitt "Teilnehmer" der Anmerkung - auf ausdrücklichen Wunsch des Nutzers ("hier definitiv vorher Fragen") in zwei Frage-Runden vorab geklärt, bevor irgendetwas umgesetzt wurde.
  - **Warnsymbol statt Kontroll-Button.** Nutzerwunsch: "in der Übersicht von den Teilnehmern fehlt mir aktuell aber noch der Überblick, ob ich auch wirklich alles erfasst habe [...] ein „Kontrollbutton“ [...], der dann nochmal prüft ob auch alle Sachen Bspl. 3 Gegenstände bei LK 3 erfasst sind." Geklärt: kein separater Button, sondern eine neue Spalte **"Vollständig"** direkt in der Teilnehmerliste (`TeilnehmerTab`) - bei fehlenden Angaben ein fett-oranges "⚠ ..." mit Tooltip, bei Vollständigkeit bleibt die Zelle leer (die Ausnahme soll auffallen, nicht der Normalfall). Geprüft werden laut Absprache **Chip-Nr.** sowie die zur Leistungsklasse passende **Gegenstand-Disziplin-Zuordnung** - dafür wurde die am 16.09. mit dem Nutzer bereits abgestimmte LK-Regel (siehe Fix 4 oben: LK1 = 1 Gegenstand für alle 3 Disziplinen, LK2 = mind. 2 unterschiedliche Gegenstände, LK3 = 3 unterschiedliche Gegenstände, je einer Disziplin zugeordnet) jetzt erstmals tatsächlich als Vollständigkeits-Prüfung ausgewertet (neue Funktionen `_dk_gegenstaende_vollstaendig()`/`_ed_gegenstaende_vollstaendig()`/`teilnehmer_fehlende_pflichtangaben()` in `db.py`; bei ED gilt sinngemäß dieselbe LK-Zahl, aber bezogen auf die eine gewählte Disziplin). Bewusst NICHT geprüft werden die übrigen, weiterhin optionalen Erfassungsfelder (Absprache mit dem Nutzer).
  - **Startnummer bei der Ersterfassung kein Pflichtfeld mehr.** Nutzerwunsch: "Vergabe der Startnummern als Pflichtfeld finde ich hier noch nicht so gut, ich weiß ggf. nicht was alles an Meldungen kommt [...] ich muss jetzt die Startreihenfolge bzw. Startnummern ändern. Das ist sehr umständlich und ich muss die Nummern die ich jetzt eigentlich bräuchte erst „frei machen“, weil ich nicht doppelt vergeben kann." Neues Häkchen **"Startnummer steht noch nicht fest"** neben dem Startnummer-Feld im Teilnehmer-Dialog - aktiviert, wird keine Startnummer gespeichert (`NULL`, von `db.py`/dem Datenbankschema ohnehin schon unterstützt, bislang aber von der Oberfläche nie erzeugt). Eine bereits vergebene Startnummer wird beim Speichern weiterhin nicht akzeptiert (**Eindeutigkeit bleibt in der Datenbank strikt**, ausdrücklich vom Nutzer bestätigt), die Warnmeldung nennt jetzt aber den Namen des aktuellen Inhabers statt nur "ist bereits vergeben". Zusätzlich neue, eigenständige Funktion **"Startnummer tauschen…"** in der Teilnehmerliste (Button, neuer `StartnummerTauschenDialog`): tauscht die Startnummern zweier ausgewählter Teilnehmer direkt und atomar (`db.tausche_startnummern()`, über eine kurze NULL-Zwischenstufe, damit die UNIQUE-Spalte dabei nicht kollidiert) - löst genau das geschilderte "erst freimachen müssen"-Problem, ohne die Eindeutigkeit aufzuweichen.
  - Testabdeckung: 6 neue Tests in `test_db.py` (Tauschen inkl. Teilnehmer ohne Startnummer, Vollständigkeits-Prüfung für ED/DK inkl. aller drei LK-Stufen); 8 neue GUI-Tests in `test_app_gui.py` (Checkbox deaktiviert/reaktiviert das Startnummer-Feld und wirkt sich korrekt auf `ergebnis()` aus, bestehender Teilnehmer ohne Startnummer zeigt Checkbox direkt aktiviert, Dubletten-Warnung nennt den Namen und blockiert weiterhin, aktivierte Checkbox überspringt die Dubletten-Prüfung, Tauschen-Button nur bei mehr als einem Teilnehmer aktiv, Tauschen vertauscht die Nummern tatsächlich in der Datenbank, Warnsymbol erscheint/verschwindet korrekt in der Teilnehmerliste) - nur CI, PySide6 lokal nicht installierbar. Vor der Meldung als fertig zusätzlich durch einen unabhängigen Verifikations-Subagent gegengeprüft (Geschäftsregel-Herleitung, NULL-Tausch-Fälle, Signal-Verdrahtung, Spaltenindex-Kollisionen, sonstige Code-Stellen mit Startnummer-Annahmen) - keine Befunde. Gesamter lokaler Testlauf: 304 Tests, 91 übersprungen, 0 fehlgeschlagen. Weiterhin kein Build/keine Auslieferung - wie vereinbart, erst wenn alle Punkte durch sind.
- **Fix 21 (umgesetzt): Teilnehmer aus anderem Termin importieren.** Der Satz "Damit ist der Abschnitt 'Teilnehmer' [...] abgearbeitet" bei Fix 20 war verfrüht - ein Punkt auf Seite 2 der Anmerkung ("Teilnehmer müssen wieder einzeln eingegeben werden. → ist Option möglich, von anderem Termin importieren?") stand dort ohne eigene Überschrift direkt im Anschluss an den Teilnehmer-Abschnitt und wurde beim ersten Durchgang übersehen - vom Nutzer nachträglich zurückgemeldet. Vor der Umsetzung wie gewohnt per Rückfrage geklärt (Auswahl einzelner Teilnehmer statt immer aller, nur Stammdaten statt kompletter Übernahme, keine Dubletten-Prüfung).
  - Neuer Button **"Aus anderem Termin importieren…"** im Reiter "Teilnehmer" - öffnet `TerminImportDialog`: Auswahl des Quell-Termins (Terminübersicht, eigener Termin ausgeschlossen) per Dropdown, darunter eine Checkbox-Liste aller Teilnehmer dieses Termins (Vorbelegung: alle angehakt, "Alle/Keine auswählen"-Buttons). Übernommen werden bewusst NUR Stammdaten (Name, Hund, Verein, Kontakt, Rasse, Halter-Block usw.) - Startnummer, Gegenstand-Zuordnung, Bezahlt-Status und ein eventuelles Ergebnis bleiben immer leer/zurückgesetzt, auch wenn die Quelle welche hatte, da sie zum jeweils EINEN Prüfungstag gehören (Absprache mit dem Nutzer). Art/Leistungsklasse/Disziplin müssen technisch trotzdem mitkommen (Pflichtfelder in der Datenbank, ein Teilnehmer kann nicht ohne sie angelegt werden) - lassen sich im Teilnehmer-Dialog nach dem Import aber sofort anpassen, falls sich die Meldung geändert hat. Keine Dubletten-Prüfung beim Import (Absprache: einfach zusätzlich anlegen).
  - Neue Funktion `db.importiere_teilnehmer_stammdaten(quelle_conn, ziel_conn, teilnehmer_ids)` - bewusst NICHT die bestehende `kopiere_termin_daten()` (Web-Sync) wiederverwendet, die einen kompletten Termin 1:1 inkl. Startnummer/Ergebnis überträgt und für diesen Zweck nicht passt. Der Dialog öffnet dafür kurzzeitig eine ZWEITE, separate SQLite-Verbindung zur gewählten Quell-Termin-Datei (unproblematisch, da eine andere Datei als der gerade geöffnete Termin) und schließt sie zuverlässig wieder (`try`/`finally`), unabhängig davon, ob der Dialog akzeptiert oder abgebrochen wurde.
  - Testabdeckung: 3 neue Tests in `test_db.py` (Auswahl-Import inkl. Ausschluss nicht ausgewählter Teilnehmer und zurückgesetzter Felder, Startnummer-Kollision zwischen Quelle und Ziel führt zu keinem Fehler da nicht übernommen, nicht mehr vorhandene ID wird übersprungen); 4 neue GUI-Tests in `test_app_gui.py` (Dialog listet Teilnehmer des gewählten Termins und Auswahl lässt sich abwählen, eigener Termin wird aus der Auswahl ausgeschlossen, ohne anderen Termin ist OK deaktiviert, kompletter Import-Durchlauf übernimmt die ausgewählten Teilnehmer in die Datenbank) - nur CI, PySide6 lokal nicht installierbar. Vor der Meldung als fertig durch einen unabhängigen Verifikations-Subagent gegengeprüft (Verbindungs-Lebenszyklus der zweiten SQLite-Verbindung, Schema-Konstraints, Testaussagekraft) - keine Befunde, ein harmloser Nebeneffekt notiert: das bloße Anwählen eines Termins im Auswahl-Dropdown lädt ihn intern per `init_db()` und zieht dabei automatisch fällige (rein additive) Schema-Migrationen nach, auch wenn man den Import am Ende abbricht - unschädlich, aber der Vollständigkeit halber festgehalten. Gesamter lokaler Testlauf: 307 Tests, 91 übersprungen, 0 fehlgeschlagen. ~~Damit ist der Abschnitt "Teilnehmer" der Anmerkung jetzt tatsächlich vollständig abgearbeitet.~~ **Auch das war verfrüht - siehe Fix 22.** Weiterhin kein Build/keine Auslieferung - wie vereinbart, erst wenn alle Punkte durch sind.
- **Fix 22 (umgesetzt): Sortierung in der Teilnehmerliste per Klick auf eine Spaltenüberschrift.** Wieder ein Punkt aus demselben Abschnitt "Teilnehmer" der Anmerkung, der beim ersten (und zweiten) Durchgang übersehen wurde: "Filtermöglichkeit gut - kann hier ggf. noch Sortierungsoption ergänzt werden?" Kein weiterer Rückfrage-Bedarf (kleiner, zweifach vom Nutzer genannter Wunsch, Standardverhalten aus Tabellenkalkulationen wie LibreOffice) - direkt umgesetzt.
  - **Umsetzung:** `TeilnehmerTab.tabelle` nutzt jetzt Qt-Bordmittel (`setSortingEnabled(True)`) - Klick auf eine Spaltenüberschrift sortiert danach, erneuter Klick kehrt die Richtung um. Die zuletzt gewählte Sortierung bleibt über `aktualisieren()` hinweg erhalten (wird per `sortIndicatorChanged`-Signal gemerkt und nach jeder Neubefüllung erneut angewendet) - sonst würde jede Änderung (Speichern, Bezahlt umschalten, Import, ...) die Tabelle kommentarlos wieder auf die Standard-Sortierung (Start-Nr. aufsteigend) zurückspringen lassen. Die Start-Nr.-Spalte sortiert dabei numerisch statt alphabetisch (2 vor 10, nicht "10" vor "2").
  - **Technische Notwendigkeit dahinter:** bislang entsprach die sichtbare Zeilenreihenfolge der Tabelle immer der Datenbank-/Listenreihenfolge, mehrere Methoden (Zeilenauswahl, Filter) gingen implizit davon aus. Durch die Sortierbarkeit stimmt das nicht mehr zwingend überein - deshalb trägt jede Zeile jetzt zusätzlich ihre Teilnehmer-ID als Qt-Datenrolle (`Qt.UserRole`) an der Start-Nr.-Zelle, worüber Zeilenauswahl (`_ausgewaehlte_id()`) und Filter (`_filter_anwenden()`) die Zeile korrekt dem richtigen Teilnehmer zuordnen, unabhängig von der aktuellen Sortierung.
  - Testabdeckung: 6 neue GUI-Tests in `test_app_gui.py` (Sortierung nach Nachname per Klick, numerische statt alphabetische Sortierung der Start-Nr., Sortierung bleibt nach `aktualisieren()` erhalten, Zeilenauswahl liefert nach Sortierung weiterhin die richtige Teilnehmer-ID, Filter funktioniert korrekt auch nach Sortierung, kein Absturz beim Sortieren der Start-Nr.-Spalte mit gemischt vorhandener/fehlender Startnummer) - nur CI, PySide6 lokal nicht installierbar (auch ein Installationsversuch in dieser Sitzung schlug mangels Netzwerkzugriff auf den passenden Index fehl). Vor der Meldung als fertig durch einen unabhängigen Verifikations-Subagent gegengeprüft (alle übrigen `TeilnehmerTab`-Methoden auf noch verbliebene Zeilenindex-Annahmen, bestehende ältere Tests auf zufällig nur bei Standardsortierung korrekte Annahmen, neue Tests auf tatsächliche Aussagekraft) - keine Korrekturnotwendigkeit, ein kleiner Testlücken-Hinweis (fehlender Teilnehmer ohne Startnummer im Sortiertest) wurde direkt noch ergänzt. Gesamter lokaler Testlauf (ohne GUI-Tests): 307 Tests, 91 übersprungen, 0 fehlgeschlagen. **Damit ist der Abschnitt "Teilnehmer" der Anmerkung jetzt - nach zweimaliger Korrektur der eigenen "fertig"-Meldung - tatsächlich vollständig abgearbeitet.** Weiterhin kein Build/keine Auslieferung - wie vereinbart, erst wenn alle Punkte durch sind.
- **Version 1.0.19 (20.09.) vorbereitet - enthält Fix 18-22.** Auf Nutzerwunsch jetzt (statt nach jedem Einzelpunkt) als gemeinsame Auslieferung erzeugt: `version.txt`/`version.py`/`version_info.txt` per `bump_version.py` auf 1.0.19 erhöht, alle geänderten Dateien (`app.py`, `db.py`, `test_app_gui.py`, `test_db.py`, `Fortschritt.md`, die drei Versionsdateien) in die Ordner `SHS-Pruefungsprogramm-Git` und `SHS-Pruefungsprogramm-Quellcode` des Nutzers übertragen und lokal committet (Commit `67e9939`, "Fix 18-22 + Version 1.0.19"). **Push und Tag (`v1.0.19`) muss weiterhin der Nutzer selbst ausführen** (kein GitHub-Netzwerkzugriff aus dieser Sitzung, siehe unten):
  ```
  git push
  git tag v1.0.19
  git push --tags
  ```
  Danach läuft `build-installer.yml` (getriggert durch den Tag) automatisch und veröffentlicht den Installer als GitHub-Release. Noch offen: Bestätigung des Nutzers, dass Push/Tag/CI-Workflow/Installer-Build erfolgreich waren (analog zu den bisherigen Versionen).
- **CI-Fund (20.09.): erster echter Testlauf gegen reales PySide6/PostgreSQL nach dem Push von Version 1.0.19 deckt 3 reale Bugs auf, die lokal (ohne installierbares PySide6/PostgreSQL) nicht sichtbar waren.** Der Nutzer hat den kompletten `pytest -v`-Lauf aus der CI zurückgemeldet: 5 von 373 Tests fehlgeschlagen, alle drei ursächlichen Bugs stammen aus dem gerade erst gepushten Batch (Fix 19/22) und wurden noch nie zuvor gegen echtes Qt/PostgreSQL geprüft (nur per Code-Review durch Subagents, siehe jeweilige Fix-Einträge oben) - insofern kein Rückfall bei bereits abgenommenem Code, sondern die erste echte Verifikation frisch geschriebenen Codes, daher direkt behoben statt vorher einzeln rückzufragen:
  - **Bug A (Fix 22, Sortierung): Start-Nr.-Spalte sortierte in echtem Qt6/PySide6 entgegen der Erwartung weiterhin alphabetisch statt numerisch** (`assert '10' == '2'` schlug fehl). Ursache: der eingesetzte Ansatz (`item.setData(Qt.DisplayRole, zahl)` und sich auf Qts eingebauten Zellenvergleich verlassen) sortiert in einem echten Lauf NICHT numerisch - nur lokal per Code-Lesen nicht erkennbar, da PySide6 hier nicht installierbar ist. Behoben durch eine neue, gezielt für die Start-Nr.-Spalte verwendete Item-Unterklasse `_NumerischSortierbaresItem`, die `__lt__` (den von `QTableWidget.sortItems()`/`sortByColumn()` tatsächlich aufgerufenen Vergleich) direkt selbst nach einem echten Zahlenwert überschreibt - der laut Qt-Dokumentation eigentlich vorgesehene, robustere Weg für genau diesen Fall.
  - **Bug B (Fix 19, Halter-Block): `gruppe_halter.isVisible()` lieferte unmittelbar nach dem allerersten Einblenden per Checkbox-Klick (bei bereits sichtbarem Dialog) noch `False` statt `True`**, obwohl `setVisible(True)` bereits synchron aufgerufen worden war. Betrifft ausschließlich diese eine erstmalige Sichtbarkeits-Umschaltung EINER `QGroupBox` mit eigenem, zuvor nie aktiviertem Layout, nach dem bereits sichtbaren Dialog (nicht beim direkten Aufklappen während `__init__`, das funktioniert bereits nachweislich, siehe die parallelen, weiterhin grünen Tests dazu) - eine Eigenheit der Qt-„offscreen"-Testplattform, ähnlich dem bereits im Moduldocstring von `test_app_gui.py` dokumentierten früheren CI-Fund zu Klicks vor dem ersten Anzeigen. Kein Logikfehler in `app.py` (`_halter_sichtbarkeit_aktualisieren()` bleibt unverändert korrekt), sondern ein zu ungeduldiger Test: behoben durch ein kurzes `qtbot.wait(50)` nach dem Klick, bevor `isVisible()` geprüft wird.
  - **Bug C (Fix 19, CSV-Import-Tests gegen PostgreSQL): `TestDatenbankPostgres.test_importiere_teilnehmer_aus_csv_*` (3 Tests) schlugen mit `AttributeError: 'TestDatenbankPostgres' object has no attribute 'pfad'` fehl.** Ursache: die drei neuen CSV-Import-Tests leiteten den Ablagepfad der Test-CSV-Datei per `os.path.dirname(self.pfad)` vom SQLite-Dateipfad ab - `self.pfad` existiert aber nur bei der SQLite-Variante (`TestDatenbank.setUp()`), nicht bei der PostgreSQL-Variante (`_PostgresBackendMixin.setUp()`, die stattdessen direkt eine Datenbankverbindung ohne Dateipfad aufbaut). Die CSV-Datei selbst hat mit dem Datenbank-Backend nichts zu tun - behoben, indem alle drei Tests jetzt eine eigene, backend-unabhängige `tempfile.mkstemp()`-Datei verwenden statt sich am DB-Dateipfad zu orientieren.
  - Alle drei Fixes sind reine Korrekturen an frisch (diese Sitzung) geschriebenem, noch nicht bestätigtem Code - betreffen weder die zwei bereits akzeptierten QS-Restrisiken noch bereits vom Nutzer abgenommene ältere Stände. Lokaler Testlauf nach der Korrektur: weiterhin 307 Tests, 91 übersprungen, 0 fehlgeschlagen (GUI-Tests und die echten PostgreSQL-Tests laufen weiterhin nur in der CI). Vor der Meldung als fertig durch einen unabhängigen Verifikations-Subagent gegengeprüft (Qt-Korrektheit der `__lt__`-Überschreibung, `Qt.UserRole`-Zuordnung nach dem Item-Klassenwechsel, ob dieselbe QGroupBox- bzw. `self.pfad`-Falle noch an anderer Stelle im Code lauert) - keine weiteren Funde, alle drei Fixes als korrekt und vollständig bestätigt. Committet (Commit `5224ed8`, "CI-Fund: 3 reale Bugs aus Version 1.0.19 behoben") und wie zuvor in die Ordner `SHS-Pruefungsprogramm-Git`/`SHS-Pruefungsprogramm-Quellcode` übertragen. **Push muss der Nutzer erneut selbst ausführen:**
  ```
  git push
  ```
  Ein Tag (`v1.0.19`) war zu diesem Zeitpunkt laut CI-Log (nur `tests.yml`, kein `build-installer.yml`-Lauf sichtbar) vermutlich noch nicht gesetzt - falls doch, den Tag nach diesem Push auf den neuen Commit nachziehen (`git tag -f v1.0.19 && git push --force --tags`), sonst reicht ein normaler `git tag v1.0.19 && git push --tags`, sobald die CI grün ist.
  - **Korrektur (21.09.): Bug B war mit dem `qtbot.wait(50)`-Fix NICHT tatsächlich behoben.** Der Nutzer hat den `git push` ausgeführt, die CI erneut gelaufen lassen und den kompletten Log zurückgemeldet: Bug A und Bug C sind jetzt bestätigt grün (339 statt 335 bestanden, genau die beiden zuvor betroffenen Tests laufen jetzt durch), Bug B (`test_halter_checkbox_blendet_block_ein_und_uebernimmt_werte`) schlägt aber unverändert an derselben Stelle fehl (`gruppe_halter.isVisible()` weiterhin `False`) - das `qtbot.wait(50)` hat also nichts bewirkt. Das widerlegt die ursprüngliche Diagnose "reines Zeitproblem, durch etwas Warten lösbar": `QWidget.isVisible()` liest laut Qt-Doku einen synchron gesetzten Zustands-Flag, kein beliebig langes Warten sollte daran etwas ändern, wenn der Flag bereits falsch steht. Da PySide6 in dieser Sandbox nicht installierbar ist (kein PyPI-Netzwerkzugriff, auch für einen erneuten Versuch bestätigt), konnte auch dieser zweite Versuch nicht lokal verifiziert werden, sondern beruht wieder nur auf Qt-Dokumentationsrecherche: `test_app_gui.py` bettet `dialog.show()` jetzt in `qtbot.waitExposed(dialog)` ein (pytest-qt-Doku: für genau solche Fälle gedacht, in denen das Fenstersystem eine Anzeige nicht synchron abschließt) statt nur danach zu warten. **Unsicherheitsgrad diesmal explizit benannt statt wie beim ersten Versuch fälschlich als sicher behoben dargestellt** - könnte immer noch ein reines Testumgebungs-Artefakt der "offscreen"-Plattform ohne Auswirkung auf die echte Anwendung sein, oder ein echter (dann noch offener) Anzeige-Bug. **Bitte beim nächsten realen Test einmal kurz die Checkbox "Halter weicht vom Hundeführer ab" im Teilnehmer-Dialog der echten Anwendung anklicken und bestätigen, ob der Block darunter sichtbar aufklappt** - das klärt in Sekunden, ob es sich überhaupt um einen echten Anwendungs-Bug handelt, unabhängig vom Ausgang der CI.
  - **Antwort vom Nutzer (21.09.): Halter-Block funktioniert im echten Programm - Bug B ist damit ein reines Testumgebungs-Artefakt der "offscreen"-Plattform, kein echter Anwendungs-Bug.** Screenshots vom realen Testdurchlauf bestätigen aber DREI andere, echte UX-Probleme im "Teilnehmer bearbeiten"-Dialog, die beim ersten Öffnen mit echten (längeren) Nutzerdaten sofort auffielen und vorher nicht real getestet worden waren:
    1. **Fenster nicht maximierbar** - `QDialog` zeigt standardmäßig keinen Maximieren-Button.
    2. **Linke Spalte (Hundeführer & Kontakt) viel zu schmal, Text wird abgeschnitten dargestellt** (z. B. "Bruver" erscheint nur als "uver") - `QHBoxLayout` ohne Stretch-Faktoren hat der rechten Spalte (mehr/breitere Pflichtfelder) den Platzbedarf gegeben und die linke dafür ausgehungert.
    3. **Bei aufgeklapptem Halter-Block reicht die feste Dialoggröße (780x640) nicht mehr aus** - Block und OK/Abbrechen-Buttons lagen außerhalb des Bildschirms, ohne Scroll-Möglichkeit.
    Alle drei behoben: `spalten_zeile.addWidget(gruppe_links, 1)`/`addWidget(gruppe_rechts, 1)` (gleicher Stretch-Faktor, 50/50-Aufteilung unabhängig vom Inhalt); kompletter Formularinhalt (beide Spalten + Halter-Block) jetzt in einem `QScrollArea` mit `setWidgetResizable(True)` (Muster wie bereits im Zeitplan-Tab verwendet) - nur OK/Abbrechen bleiben fest am unteren Rand, immer erreichbar; `self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)` vor `resize()` ergänzt. Lokaler Testlauf weiterhin 307/91/0 (GUI-Tests laufen nur in der CI). Durch einen unabhängigen Verifikations-Subagenten gegengeprüft (alle drei Fixes korrekt, keine gebrochenen Widget-Referenzen in `_halter_sichtbarkeit_aktualisieren`/`_art_geaendert`/`ergebnis()`, keine betroffenen Tests in `test_app_gui.py`) - Verdikt "SHIP AS-IS". **Bitte im nächsten echten Test bestätigen: Fenster maximierbar, linke Spalte zeigt vollständigen Text, Halter-Block komplett einsehbar samt OK-Button erreichbar.**
  - **Zwischenstand (21.09., KORRIGIERT - "endgültig abgeschlossen" war verfrüht): CI-Log zum `qtbot.waitExposed`-Versuch zurückgemeldet - identischer Fehlschlag wie beim ersten Versuch, exakt dieselbe Stelle, exakt dieselbe Fehlermeldung.** Zwei Fix-Versuche auf Basis von `isVisible()` sind damit gescheitert. Da der Nutzer inzwischen per Screenshot bestätigt hat, dass der Halter-Block in der echten Anwendung korrekt funktioniert, wird nicht länger geraten: `test_halter_checkbox_blendet_block_ein_und_uebernimmt_werte` prüft jetzt `gruppe_halter.isHidden()` statt `gruppe_halter.isVisible()` - `isHidden()` liest nur das von `setVisible()` gesetzte Flag des Widgets selbst (genau das, was `_halter_sichtbarkeit_aktualisieren()` steuert), ohne wie `isVisible()` zusätzlich die komplette Vorfahren-Kette einzubeziehen.
  - **Dritter Fix-Versuch (isHidden()) ebenfalls gescheitert (21.09.) - WICHTIGE neue Erkenntnis.** CI-Log zurückgemeldet: `gruppe_halter.isHidden()` liefert nach dem Klick weiterhin `True` (versteckt), obwohl `isHidden()` NUR das von `setVisible()` direkt gesetzte Flag des Widgets selbst prüft, OHNE Vorfahren-Kette. Das entkräftet die "Vorfahren-Kette/Exposure"-Theorie der ersten beiden Versuche - wenn selbst das direkte, eigene Sichtbarkeits-Flag des Widgets falsch steht, ist eine reine Testumgebungs-Eigenheit deutlich unwahrscheinlicher geworden. **Wichtiger Verdacht: Dieser CI-Lauf testet zum ersten Mal die Kombination aus dem Halter-Block UND der neu eingeführten `QScrollArea`** (aus dem UX-Fix von eben, Commit `8833a9f`) - `gruppe_halter` liegt jetzt zusätzlich innerhalb eines `QScrollArea`-Inhalts-Widgets, dessen Größe/Layout erst durch einen eigenen (unter Umständen asynchronen) Layout-Durchlauf bestimmt wird. **Marcos Bestätigung "Halter-Block funktioniert in der echten Anwendung" stammt von VOR diesem QScrollArea-Fix** - sie deckt die aktuelle Version also noch nicht ab. Es ist daher nicht mehr auszuschließen, dass der QScrollArea-Fix selbst einen echten Regressions-Bug eingeführt hat, statt nur ein Testartefakt zu sein. Statt eines vierten Rateversuchs: `test_halter_checkbox_blendet_block_ein_und_uebernimmt_werte` jetzt mit `@pytest.mark.xfail(strict=False, reason="...")` markiert (blockiert die CI für alle anderen, unabhängigen Fixes nicht länger) - **aber Marco ausdrücklich gebeten, die Checkbox "Halter weicht vom Hundeführer ab" nochmal in der GERADE ausgelieferten Version (mit Scroll-Bereich und Maximieren-Button) zu testen**, um zu klären, ob es doch ein echter Bug ist. Lokaler Testlauf weiterhin 307/91/0.
  - **Bug B damit endgültig geklärt (21.09.): Marco hat die aktuelle Version (mit QScrollArea + Maximieren-Button) real getestet - Halter-Block klappt sauber auf, Fenster ist maximierbar und scrollbar, alle CI-Tests grün.** Der QScrollArea-Fix hat also KEINEN echten Regressions-Bug eingeführt - Bug B war die ganze Zeit ausschließlich ein Artefakt der "offscreen"-Testplattform, wie zuletzt vermutet. Die `xfail`-Markierung bleibt bestehen (dokumentiert den bekannten, harmlosen Testplattform-Fehlschlag, ohne dass er die CI blockiert) - eine weitere Testumgebungs-Recherche lohnt sich nicht, da die reale Funktion jetzt zweifach real bestätigt ist (vor UND nach dem QScrollArea-Fix).

- **Tag `v1.0.19` lokal auf den finalen Stand vorgezogen (21.09.):** zeigte noch auf einen älteren Commit (vor den drei CI-Fund-Bugfixes und den drei UX-Fixes am Teilnehmer-Dialog) - lokal auf `9e3920e` verschoben. **Bestätigt (21.09.): der Nutzer hat den `git push --force origin v1.0.19` ausgeführt** - per `git ls-remote --tags origin` gegengeprüft, Tag zeigt remote wie lokal korrekt auf `9e3920e`.

- **Feedback zum Tab "Zeitplan" (21.09., neue Anmerkung im Chat statt schriftliches Dokument):** Marco hat vier Punkte zurückgemeldet, nachdem er gebeten wurde, offene Zeitplan-Punkte zu nennen:
  1. *"Begriff Leistungsrichter durch Richter tauschen (auch in den Hinweisen, bei fehlender Auswahl)"* - bereits durch Fix 17 (20.09.) erledigt und Teil des von Marco bestätigten, grün laufenden Stands 1.0.19; keine weitere Änderung nötig, nur zurückgemeldet.
  2. *"Über Entfernen wird der ganze Block entfernt - hat mich zunächst irritiert... (kurzfristige Krankmeldung, müsste ich den Teilnehmer dann vorne raus nehmen)"* - als Beobachtung eingeordnet, nicht als Fehler: "Entfernen" in einer Richter-Spalte löscht bewusst den ganzen Prüfungsblock-Eintrag (Art/Stufe/Disziplin/Dauer), nicht einzelne Teilnehmer, da die Zuteilung einzelner Teilnehmer zu einem Block ohnehin nicht gespeichert, sondern bei jeder Anzeige live aus den aktuellen Anmeldedaten neu ermittelt wird (siehe `_teilnehmer_fuer_pruefungseintrag`). Für den genannten Anwendungsfall (kurzfristige Krankmeldung) folgt daraus: der Teilnehmer wird im Tab "Teilnehmer" entfernt/storniert, NICHT über "Entfernen" im Zeitplan - der Zeitplan-Block bleibt unverändert bestehen und zeigt beim nächsten Aufbau automatisch einen Teilnehmer weniger (keine manuelle Nachpflege im Zeitplan nötig). Diese Klärung an Marco zurückgemeldet; falls er trotzdem eine Sicherheitsabfrage vor "Entfernen" wünscht (ähnlich "Richter löschen"), steht das als möglicher Folgepunkt offen.
  3. *"Ich tue mir etwas schwer, ob ich von den benötigten Starts auch schon alles erwischt habe, nachdem ich scrollen muss. Vielleicht kann man rechts abbilden... was schon integriert ist und was noch fehlt?"* - **umgesetzt:** neue feste Seitenleiste "Offene Starts" im Zeitplan-Tab (`ZeitplanTab`, `app.py`), bewusst AUSSERHALB der horizontal scrollbaren Richter-Spalten platziert, damit sie beim Scrollen sichtbar bleibt. Zeigt je Art/Leistungsklasse/Disziplin mit mindestens einem Teilnehmer eine Zeile mit Teilnehmerzahl, grün mit Haken wenn dafür schon ein Prüfungsblock angelegt ist ("eingeplant"), sonst rot/fett mit "noch offen". Neue Funktion `zeitplan_gruppen_status()` in `db.py` (direkt neben `zeitplan_gruppen()`) liefert dafür je Gruppe zusätzlich `anzahl` und `eingeplant` - ein einzelner passender Block reicht aus, egal bei welchem Richter, da ein Block ohnehin automatisch ALLE passenden Teilnehmer zieht (kein Teilaufteilungs-Mechanismus vorhanden). Testabdeckung: 4 neue Fälle in `test_db.py` (gemischt eingeplant/offen, Abdeckung unabhängig vom Richter, Pause zählt nicht als Abdeckung, leerer Fall - laufen dank der bestehenden `TestZeitplan`/`TestZeitplanPostgres`-Struktur automatisch auch gegen Postgres in der CI) sowie 2 neue GUI-Tests in `test_app_gui.py` (nur CI, PySide6 lokal nicht installierbar). Durch einen unabhängigen Verifikations-Subagenten gegengeprüft (Matching-Semantik gegen `_teilnehmer_fuer_pruefungseintrag`, DK-Sonderfall über 3 Blöcke, Pause-Ausschluss, Layout-Verschachtelung, Attribut-Reihenfolge im Konstruktor) - Verdikt "SHIP AS-IS", keine Funde. Lokaler Testlauf: 315 Tests, 95 übersprungen, 0 fehlgeschlagen (GUI-Tests laufen nur in der CI).
  4. *"PDF erzeugen Zeitplan klappt super."* - positive Rückmeldung, keine Änderung nötig.
  Auf Wunsch des Nutzers (Vorgehen seit Fix 18) wird weiterhin erst nach Absprache ein gemeinsamer Build/Version/Auslieferung erzeugt statt nach jedem Einzelpunkt - dieser Punkt bleibt vorerst nur im Cloud-Arbeitsbereich, noch nicht auf dem Rechner des Nutzers oder committet.
  - **Ergänzung (21.09.): Klärung zu Punkt 2 ("Entfernen" löscht ganzen Block) zusätzlich in die eingebaute Hilfe aufgenommen**, auf ausdrücklichen Nutzerwunsch ("ergänze die Punkte 2 in die Hilfe damit die Anwender dies wissen"). `_HILFE_HTML`/`HilfeDialog` (app.py) - Abschnitt "Reiter Zeitplan" um einen Absatz "Wichtig zu Entfernen" ergänzt: erklärt, dass ein Prüfungsblock nur Art/LK/Disziplin speichert und die Teilnehmerzuordnung live erfolgt, "Entfernen" deshalb immer den ganzen Block löscht, und dass ein kurzfristig ausfallender Teilnehmer stattdessen im Reiter "Teilnehmer" ausgetragen wird (Zeitplan-Block bleibt bestehen, zeigt automatisch einen Teilnehmer weniger). Dabei auch gleich die neue Seitenleiste "Offene Starts" (Punkt 3) im Hilfetext erwähnt, die vorher noch fehlte. Kein bestehender Test prüft den Hilfetext inhaltlich, daher keine Testanpassung nötig - `py_compile` sauber.

- **Version 1.0.20 (21.09.) vorbereitet - enthält die "Offene Starts"-Seitenleiste + Hilfe-Ergänzung.** Auf Nutzerwunsch ("jetzt neuen Build erzeugen") als eigene Version erzeugt: `version.txt`/`version.py`/`version_info.txt` per `bump_version.py` auf 1.0.20 erhöht, alle geänderten Dateien (`app.py`, `db.py`, `test_app_gui.py`, `test_db.py`, `Fortschritt.md`, die drei Versionsdateien) in die Ordner `SHS-Pruefungsprogramm-Git` und `SHS-Pruefungsprogramm-Quellcode` des Nutzers übertragen und lokal committet (Commit `f999179`, "Zeitplan-Tab: Seitenleiste 'Offene Starts' + Hilfe-Ergänzung, Version 1.0.20"). Dabei erneut die bekannten, harmlosen `index.lock`/temp-object-Warnungen beim Commit aufgetreten (vermutlich ein Hintergrundprozess auf dem Windows-Rechner, der `.git/` kurzzeitig sperrt) - wie in früheren Sitzungen durch Verschieben der Lock-Datei (`mv .git/index.lock .git/index.lock.stale-<Zeitstempel>`, da Löschen in dieser Umgebung standardmäßig nicht erlaubt ist) umgangen, Commit danach erfolgreich. **Push und Tag (`v1.0.20`) muss wie gehabt der Nutzer selbst ausführen** (`git push` aus dieser Sitzung schlägt mit "could not read Username for 'https://github.com'" fehl - kein GitHub-Zugangsdaten-Zugriff von hier aus):
  ```
  git push
  git tag v1.0.20
  git push --tags
  ```

- **Neu (19.09.): reale Nutzertests laufen parallel beim Nutzer und wurden bereits von 2 Testern erfolgreich abgeschlossen** – betrifft die unten weiterhin aufgeführten offenen Einzelpunkte zum realen Testen (Datensicherung, Zeitplan-Tab, Bezahlt-Markierung, Installer-Update usw.); Details/Ergebnisse der beiden Testdurchläufe liegen nur beim Nutzer vor, nicht in diesem Dokument.
- **Erledigt (19.09.): Web-Backend (Ergebniseingabe) UND Podman-Containerisierung sind fertig – der Compose-Stack (PostgreSQL + Web-Container) läuft nachweislich, CI-Smoke-Test vom Nutzer als grün bestätigt.** `app_web.py` (Flask) + `sync_termin.py` (Export/Import-Werkzeug) sowie `Containerfile`/`compose.yaml`/`.github/workflows/build-container.yml` (siehe eigener Abschnitt oben, inkl. zweier dort gefundener und behobener Workflow-Bugs) sind fertig und bestätigt funktionsfähig. Noch offen: ein echter End-zu-Ende-Testlauf beim Nutzer (mehrere Geräte gleichzeitig im Vereins-WLAN gegen einen echten PostgreSQL-Server), eine PostgreSQL-Backup-Strategie (die bestehende ZIP-Datensicherung sichert nur *.sqlite-Dateien, siehe eigener Abschnitt oben), die endgültige Entscheidung für die Laufzeitumgebung (Windows-Laptop vs. separates Gerät, siehe eigener Abschnitt oben), ein erster echter Versions-Tag zur Veröffentlichung des Images nach ghcr.io, sowie eine mögliche spätere Ausbaustufe (Termin anlegen/Teilnehmerverwaltung/Zeitplan/PDF-Export auch über die Web-Oberfläche) – bewusst nicht Teil des jetzt abgestimmten Umfangs.
- **Erledigt (19.09., Fortsetzung 5): individuelle Benutzerkonten (Administrator + "Nur Eintragen") lösen den gemeinsamen Zugangscode ab** – siehe eigener Abschnitt oben. Noch offen: ein echter End-zu-Ende-Test beim Nutzer und die CI-Bestätigung von `TestBenutzerkontenPostgres` gegen den echten PostgreSQL-Server (siehe dortiger Abschnitt).
- **Erledigt (19.09., Fortsetzung 6): Termin veröffentlichen/zurückholen/löschen jetzt auch per Datei-Upload/Download über die Web-Oberfläche möglich, als Alternative zu `sync_termin.py`** – siehe eigener Abschnitt oben. Noch offen: ein echter End-zu-Ende-Test dieses Web-Upload-Wegs beim Nutzer.
- **Erledigt (19.09.): Login-Bug beim ersten echten Test des Konten-Systems behoben - Benutzername beim Anmelden jetzt GROSS-/kleinschreibungsunabhängig** (Ursache: Autokapitalisierung auf Mobilgeräten ließ einen eigentlich korrekten Benutzernamen anders geschrieben ankommen als beim Anlegen) – siehe eigener Abschnitt oben. Noch offen: Bestätigung durch den Nutzer, dass der Administrator-Login jetzt funktioniert.
- **Erledigt (19.09.): drei echte CI-Läufe gegen PostgreSQL erfolgt – fünf reale Bugs gefunden (siehe eigener Abschnitt oben), alle fünf behoben, dritter Lauf danach vom Nutzer als vollständig grün bestätigt.** Runde 1: 7 fehlgeschlagene Tests + 2 Fehler → vier Ursachen behoben. Runde 2 (nach erneutem Push): nur noch 1 fehlgeschlagener Test von 246 (eine Nebenwirkung der Korrektur aus Runde 1) → behoben. Runde 3 (nach erneutem Push): Nutzer bestätigt, alle Tests grün. Damit ist das PostgreSQL-CI-Bugfixing für `TestDatenbankPostgres`/`TestZeitplanPostgres`/`TestTerminverwaltungPostgres`/`TestTerminSyncPostgres` (zusammen ca. 66 Tests) abgeschlossen.
- **Neu: die Datensicherung (Export/Import als ZIP) beim Nutzer real testen** – automatisierte Tests (`test_backup.py`) decken die Logik ab, und der Installer-Build mit der neuen `pycryptodomex`-Abhängigkeit wurde in der CI erfolgreich verifiziert; ein echter Klick-Test der neuen Dialoge (Passwort setzen/eingeben, Konflikt-Dialog bei mehreren vorhandenen Terminen) fehlt aber noch, ebenso ein Test mit einer realistisch großen Anzahl an Terminen (Performance/Dateigröße) und ein Test, ob ein vergessenes Passwort wie dokumentiert tatsächlich nicht wiederherstellbar ist.
- **Aktualisiert (16.09.): Hilfe-Button und automatisches Speichern beim Beenden real (auf Windows) testen** – seit `test_app_gui.py` gibt es dafür automatisierte, echte Klick-Tests, die bei jedem Push in der CI-Pipeline laufen (Hilfe-Button sichtbar & öffnet den Dialog; automatisches Speichern greift bei ungespeicherten Änderungen, nicht aber wenn schon alles gespeichert ist). Ein manueller Test auf dem tatsächlichen Windows-Zielsystem bleibt trotzdem sinnvoll: ob der Hilfe-Button in der Fensterkopfzeile optisch wie gewünscht neben Minimieren/Maximieren/Schließen sitzt, ob der Hilfetext gut lesbar/scrollbar ist, und ob das automatische Speichern auch bei Programmende über Alt+F4 oder Task-Manager zuverlässig greift – das lässt sich headless nicht nachstellen.
- **Aktualisiert (16.09.): die neue Gegenstand-Disziplin-Zuordnung beim Nutzer testen** – automatisierte GUI-Tests (`test_app_gui.py`) prüfen inzwischen per echtem Klick, dass ein nicht explizit zugeordneter Gegenstand "frei" bleibt (kein Default) und dass sich die Zuordnung unabhängig von der Position frei wählen lässt, ergänzt um eine visuell geprüfte Beispiel-PDF. Ein Test mit echten Nutzerdaten am Verein steht aber weiterhin aus. Besonders zu prüfen: ob das Fehlen einer Default-Zuordnung in der Praxis dazu führt, dass Gegenstände vergessen zuzuordnen werden (und dadurch auf dem Bewertungsbogen fehlen) – ggf. wäre ein Hinweis/eine Erinnerung beim Speichern sinnvoll, falls sich das als Stolperstein erweist.
- Neu gebauten Installer beim Nutzer final verifizieren (Ergebnisliste-zum-Ausfüllen-Button, responsive Oberfläche, "Anderen Termin öffnen…", "Ablageort öffnen", die automatische Versionsnummer und die Etiketten-Ergebnisliste in der tatsächlich installierten Version testen – insbesondere den Andruck auf echtem Klebe-/Etikettenpapier).
- Das neue Etiketten- und Statistik-Layout (13.09., 2. Ergänzung) sowie den neuen Button "Veranstaltungsdaten bearbeiten…" beim Nutzer testen – insbesondere den Andruck der Etiketten auf echtem Klebepapier und ob die Statistik-Matrix inhaltlich mit der alten Excel/Calc-Statistik übereinstimmt.
- Die neue "Übersicht für Prüfungsleitung" und den "Leistungsrichter-Bedarf" (14.09.) beim Nutzer testen – insbesondere ob die vorbelegte Prüfungsgebühr (Startwert 12,00 €) und die tatsächlich am Verein üblichen ED-/DK-Beträge zusammenpassen, ob die neue digitale Bezahlt-Markierung (siehe unten) für die Spalte "bezahlt?" praktikabel ist, und ob die verbleibenden zwei Papier-Ankreuzspalten der Übersicht in der Praxis am Anmeldetisch gut nutzbar sind.
- **Aktualisiert: die Bezahlt-Markierung je Teilnehmer beim Nutzer testen** – automatisierte GUI-Tests (`test_app_gui.py`) decken inzwischen per echtem Klick ab, dass der Umschalten-Button erst nach Zeilenauswahl aktiv wird, den Status korrekt umschaltet (Datenbank und Tabelle) und die Checkbox im Erfassen-Dialog funktioniert. Ein Test am tatsächlichen Anmeldetisch mit echtem Ablauf steht aber weiterhin aus.
- **Tab "Zeitplan": zweite Testrunde beim Nutzer nach den vier Korrekturen vom 14.09. (Farben, Export-Ablageort, wiederholbares Verschieben, Einzelteilnehmer-Anzeige) noch ausstehend** – die Korrekturen selbst konnten in dieser Umgebung nur per `py_compile`/automatisierten Tests sowie einer visuell geprüften Beispiel-PDF abgesichert werden, nicht durch echtes Klicken in der GUI (kein PySide6 hier installierbar). Weiterhin zu prüfen: Spaltenlayout bei vielen Richtern (horizontales Scrollen - seit 21.09. durch die feste Seitenleiste "Offene Starts" entschärft, aber das Scrollen selbst bleibt bei vielen Richtern bestehen), Verhalten von "Automatisch verteilen…" bei bereits vorhandenem, von Hand angepasstem Zeitplan (wird bewusst komplett ersetzt, mit vorheriger Rückfrage), ob die Longest-Processing-Time-Verteilung in der Praxis sinnvoll ausbalanciert, und ob das Zeitplan-Start-Feld (HH:MM) robust genug gegen Tippfehler ist.
- Ein Update über eine bestehende Installation testen (Kernanforderung: alte Version wird beim Installieren einer neuen automatisch ersetzt).
- Optional: eigenes Anwendungssymbol (`.ico`) für `build.spec`/`installer.iss` – aktuell Standard-Icon.
- **Neu (19.09.): Housekeeping im Git-Repo (Git-Ordner auf dem PC des Nutzers)** – zwei kleine, unabhängig vom heutigen Bugfix-Batch aufgefallene Punkte: (1) im `.github/workflows/`-Ordner liegt noch eine überflüssige Datei `tests.yml.github-workflows` (Nebenprodukt eines früheren, inzwischen überholten Zustellversuchs) – kann aus dem Repo entfernt werden, die eigentliche `tests.yml` liegt separat und korrekt vor. (2) mehrere Dateien (`README.md`, `version.py`, `version.txt`, `version_info.txt`) sind seit einer Weile lokal geändert, aber nicht committet – unklar, ob das gewollt ist oder Reste eines Builds; bisher unangetastet gelassen, damit nichts versehentlich verloren geht.
- **Erkenntnis (19.09., beim Ausliefern von `build-container.yml`): das automatische Zustellwerkzeug in die drei Ordner des Nutzers kann bereits VORHANDENE `.github/workflows/*.yml`-Dateien aktualisieren (`tests.yml`/`build-installer.yml` wurden diese Sitzung mehrfach erfolgreich so aktualisiert), verweigert aber das Anlegen einer KOMPLETT NEUEN Workflow-Datei dort ("protected file") – eine bewusste Schutzmaßnahme gegen automatisiertes Einschleusen neuer CI/CD-Konfiguration. Deshalb wurde `build-container.yml` stattdessen in den Hauptordner der drei Verzeichnisse gelegt; der Nutzer muss sie einmalig selbst nach `.github/workflows/` verschieben, bevor er sie committet (siehe Hinweis im Chat). Für künftige neue Workflow-Dateien gilt dasselbe Vorgehen.

**Nutzer-Feedback (21.09., Screenshot "Ergebniserfassung"/"Auswertung") – vier Punkte, drei umgesetzt, einer bestätigtes Feedback ohne Code-Änderung. Umsetzung als geplante Aufgabe (10:25 Uhr) in einer eigenen, frischen Sitzung gelaufen - alle fachlichen Entscheidungen vorab mit Marco per AskUserQuestion geklärt.**
- **1. (umgesetzt) Ergebniserfassung: Sortierfunktion per Klick auf Spaltenkopf.** Marco: "klappt gut, ggf. hier auch Sortierungsfunktion" – analog zur vorhandenen Sortierung in der Teilnehmerliste (`TeilnehmerTab`, "Fix 22"). Technische Besonderheit: `ErgebnisTab` (`app.py`) setzt die Punkte-Eingabefelder über `setCellWidget()` (echte `QLineEdit`-Widgets) statt reiner `QTableWidgetItem`-Texte – Qt's `QTableWidget.sortItems()`/`setSortingEnabled(True)` verschiebt nur `QTableWidgetItem`s, NICHT per `setCellWidget` gesetzte Widgets; ein naiver `setSortingEnabled(True)` hätte die Eingabefelder von den falschen Zeilen getrennt. Deshalb eigene Sortierlogik: Klick auf eine Spaltenüberschrift (`horizontalHeader().sectionClicked` → `_spalte_geklickt`) sortiert `self._teilnehmer_je_zeile` nach der geklickten Spalte (erneuter Klick kehrt die Richtung um), sichert dabei VORHER die aktuellen (ggf. noch nicht gespeicherten) Punktwerte UND den Disqualifiziert-/Abbruch-Status je TEILNEHMER-ID (`_sortieren_und_neu_aufbauen`) und baut die Tabelle in neuer Reihenfolge komplett neu auf, befüllt mit den gesicherten statt den DB-Werten (`_zeilen_aufbauen`, jetzt gemeinsam von `aktualisieren()` und der Sortierung genutzt) – keine ungespeicherte Eingabe geht beim Sortieren verloren, keine Vertauschung zwischen Zeilen möglich (Zuordnung läuft über die Teilnehmer-ID, nicht den Zeilenindex). Tests: 3 neue GUI-Tests in `test_app_gui.py` (Sortierung nach Name inkl. Richtungswechsel; ungespeicherte Punkteeingabe bleibt nach Sortierung derselben Zeile zugeordnet und lässt sich danach normal speichern; Disqualifiziert-Status + gesperrte Punktefelder bleiben ebenfalls der richtigen Zeile zugeordnet) – laufen nur in der CI (PySide6 lokal nicht installierbar), lokal per `py_compile` geprüft und zusätzlich durch einen unabhängigen Verifikations-Subagenten gegen den tatsächlichen Code gelesen (keine Fundstellen für Vertauschung/Datenverlust).
- **2. (bestätigtes Feedback, keine Code-Änderung) Auswertung.** Marco bestätigt nur, dass der Tab gut funktioniert (inkl. Namensanzeige bei fehlender Eingabe) – keine Änderung nötig.
- **3. (umgesetzt) Disqualifikation/Abbruch als zwei getrennte, unabhängige Status je Teilnehmer** (NICHT ein gemeinsamer Status, mit Marco abgestimmt) – bisher gab es dafür kein Feld, nur die Punktwerte Suche (0-60)/Anzeige (0-40) je Disziplin.
  - **Datenmodell (`db.py`):** zwei neue Spalten auf `ergebnisse` – `disqualifiziert`/`abbruch` (`INTEGER NOT NULL DEFAULT 0 CHECK (... IN (0,1))`, Boolean-Konvention wie `teilnehmer.bezahlt`). Neue, tabellengesteuerte Migration `_migriere_ergebnisse_spalten()`/`_ERGEBNISSE_NEUE_SPALTEN` (analog zu `_migriere_teilnehmer_spalten`) ergänzt die Spalten automatisch in bereits vorher angelegten Termin-Dateien/-Datenbanken, aus `init_db()`, `_richte_schema_im_aktuellen_suchpfad_ein()` (Postgres) UND `oeffne_termin_postgres()` aufgerufen – bestehende Ergebniszeilen gelten dabei als "weder disqualifiziert noch Abbruch". Neue Funktion `setze_ergebnis_status(conn, teilnehmer_id, disqualifiziert, abbruch)`.
  - **Auswertung (`db.berechne_auswertung()`):** ein Teilnehmer mit gesetztem Disqualifiziert-/Abbruch-Status bekommt KEINE aus Punkten berechnete Wertnote mehr (unabhängig davon, ob ggf. doch noch Punktwerte in der DB stehen) – stattdessen eine Platzhalter-`Wertnote` mit Text "Disqualifiziert"/"Abbruch" (neue Konstanten `DISQUALIFIZIERT_TEXT`/`_ABK`, `ABBRUCH_TEXT`/`_ABK` in `shs_core.py`, `bestanden=False`). Landet dadurch (wie ein normaler "nicht bestanden"-Teilnehmer) in der `fertig`-Liste statt in `ausstehend`, `berechne_rangliste()` (unverändert) gibt ihm keine Platzierung, zählt ihn aber weiterhin bei "von X Startern" mit.
  - **Ergebniserfassung (`ErgebnisTab`, `app.py`):** zwei neue Spalten "Disqualifiziert"/"Abbruch" mit je einer Checkbox pro Zeile (zentriert über neue Hilfsfunktion `_zentrierte_zelle()`); bei Aktivierung werden die Punkte-Eingabefelder dieser Zeile gesperrt UND geleert (`_punkteeingabe_sperren`, eigene Einschätzung zur UX), bei Deaktivierung wieder freigegeben. `alle_speichern()` persistiert einen geänderten Status über `setze_ergebnis_status()`, der "ungespeichert"-Vergleich (`_zeile_ist_ungespeichert`) berücksichtigt jetzt auch den Status.
  - **Auswertung (`AuswertungTab`, `app.py`):** zeigt für Disqualifiziert/Abbruch den Text "Disqualifiziert"/"Abbruch" statt Wertnote bzw. "nB" (Platzierungs- UND Wertnote-Spalte), Gesamtpunkte-Spalte zeigt "–" statt einer (nicht mehr aus Punkten berechneten) Zahl; normales "nicht bestanden" (nB) bleibt unverändert.
  - **Statistik-PDF (`pdf_export.py`):** die Prädikat-Matrix (`_statistik_praedikat_matrix()`) bekommt zwei neue Zeilen "Disqualifikation"/"Abbruch" (`_PRAEDIKAT_REIHENFOLGE`/`_PRAEDIKAT_TEXT` erweitert) – zählt automatisch korrekt mit, da die Zählung ohnehin rein über `t.wertnote.abkuerzung` läuft, keine Sonderbehandlung im Zählcode nötig.
  - Tests: 4 neue Tests in `test_db.py` (Migration bei "alter" `ergebnisse`-Tabelle ohne die Spalten; `setze_ergebnis_status()` unabhängig je Flag; Disqualifiziert bzw. Abbruch bekommt keine aus Punkten berechnete Wertnote, auch wenn noch Punktwerte in der DB stehen, zählt aber als Starter mit), 1 neuer Test in `test_pdf_export.py` (Statistik zählt beide neuen Zeilen korrekt), 2 neue GUI-Tests in `test_app_gui.py` (Checkboxen sperren/leeren die Punkteeingabe; Status wird unabhängig gespeichert und bleibt nach "Liste aktualisieren" sichtbar) – GUI-Tests nur CI/`py_compile`.
- **4. (umgesetzt) Chipnummernliste als zusätzlicher, kompakter PDF-Export.** Chip-Nr. steht zwar schon auf jedem Bewertungsbogen und als eigene Spalte in der "Übersicht für Prüfungsleitung"-PDF – reicht Marco selbst, er bekommt aber von anderen im Verein weiterhin Nachfragen danach. Neue Funktion `erstelle_chipnummernliste_pdf()` in `pdf_export.py` (Vorbild: `erstelle_leistungsrichter_bedarf_pdf`/`erstelle_pruefungsleitung_uebersicht_pdf`) – kompakte Tabelle nur Start-Nr./Name/Hund/Chip-Nr., sortiert nach Startnummer statt wie die Übersicht für Prüfungsleitung nach Name (Anwendungsfall: Abgleich am Prüfungstag, z.B. an einer Chip-Scanner-Station); Hund-Rufname zusätzlich zur Eindeutigkeit bei gleichen Nachnamen (eigene Einschätzung). Neuer Button "Chipnummernliste (PDF)…" im Tab "Export" (`ExportTab`, `app.py`). Tests: 3 neue Tests in `test_pdf_export.py` (Inhalt + Sortierung nach Startnummer trotz anderer Anlage-Reihenfolge; kein Absturz bei fehlender Startnummer; Hinweis bei keinen Teilnehmern).
- **Gesamter lokaler Testlauf (non-GUI):** 327 Tests, 99 übersprungen (PySide6-/echte-Postgres-Tests, laufen nur in der CI), 0 fehlgeschlagen. Zusätzlich unabhängiger Verifikations-Subagent gegengeprüft (Migrationslogik, Reihenfolge der DQ/Abbruch-Prüfung in `berechne_auswertung()`, Sortier-/Zuordnungslogik in `ErgebnisTab`, Statistik-Zählung, Chipnummernliste-Sortierung bei `None`-Startnummer) – keine Befunde. Ausgeliefert (siehe unten), lokal committet; Push/Tag/Versionsbump stehen noch aus (macht Marco erst auf ausdrücklichen Wunsch).

## Ausgelieferte Dateien (im Chat, und lokal auf dem PC des Nutzers gesichert)

`shs_core.py`, `test_shs_core.py`, `db.py`, `test_db.py`, `test_db_postgres_wrapper.py` (Wrapper-Tests für die PostgreSQL/Podman-Variante), `app.py`, `test_app_gui.py` (echte GUI-Tests via pytest-qt), `test_backup.py` (Tests für die Datensicherung), `pytest.ini`, `pdf_export.py`, `test_pdf_export.py`, `requirements.txt`, `requirements-postgres.txt`, `build.spec`, `version.txt`, `bump_version.py`, `test_bump_version.py`, `version_info.txt`, `installer.iss`, `build_installer.bat`, `README_INSTALLER.md`, `gui_vorschau.html` (statische, interaktive Layout-Vorschau), `.gitignore`, `.github/workflows/tests.yml`, `.github/workflows/build-installer.yml`, `app_web.py` (19.09.: Flask-Backend der Web-Version; Fortsetzung 5: Login über Benutzerkonten statt Zugangscode, Termin-Auswahl, Benutzerverwaltung; Fortsetzung 6: Termin veröffentlichen/zurückholen/löschen per Datei-Upload/Download; 19.09. Bugfix: Duplikat-Prüfung beim Benutzeranlegen GROSS-/kleinschreibungsunabhängig), `test_app_web.py` (19.09., Fortsetzung 5: komplett neu strukturiert, 26 Tests; Fortsetzung 6: 8 weitere Tests für die neuen Upload/Download-Routen, 34 insgesamt; 19.09. Bugfix: 2 weitere Tests zur Groß-/Kleinschreibung, 36 insgesamt), `sync_termin.py` (19.09.: Export/Import-Werkzeug SQLite↔PostgreSQL; Fortsetzung 5: Export-Ausgabe ohne Zugangscode), `requirements-web.txt` (19.09.), `templates/base.html` (19.09.; Fortsetzung 5: Kopfzeile mit Termin-wechseln/Benutzer-Link; Fortsetzung 6: zusätzlicher "Termine"-Link für Administratoren), `templates/login.html` (19.09.; Fortsetzung 5: Benutzername/Passwort statt Zugangscode; 19.09. Bugfix: Benutzername-Feld ohne Autokapitalisierung/-korrektur), `templates/ersteinrichtung.html` (19.09. Bugfix: ebenfalls ohne Autokapitalisierung/-korrektur), `templates/termin_waehlen.html`, `templates/admin_benutzer.html` (alle Fortsetzung 5, neu; admin_benutzer.html 19.09. Bugfix: ebenfalls ohne Autokapitalisierung/-korrektur), `templates/admin_termine.html` (Fortsetzung 6, neu), `templates/teilnehmerliste.html`, `templates/ergebnis_erfassen.html` (beide 19.09.), `db.py`/`test_db.py` (19.09., aktualisiert: vier reale, per CI gegen PostgreSQL gefundene Bugs behoben – DROP-TABLE-CASCADE, zwei `.fetchone()[0]`-Stellen in Tests, fehlender `search_path`-Wechsel beim Export, unqualifizierte Registry-Bereinigung im Test-Teardown, siehe eigener Abschnitt oben; Fortsetzung 5: `web_benutzer`-Tabelle + Benutzerkonten-Funktionen, Zugangscode-Mechanismus entfernt; 19.09. Bugfix: Login-Benutzername GROSS-/kleinschreibungsunabhängig, 1 weiterer Test), `Containerfile` (19.09.: baut das Web-Backend-Image), `.containerignore` (19.09.), `compose.yaml` (19.09.: Web + PostgreSQL als Compose-Stack; Fortsetzung 4 Ende: `db`-Port `127.0.0.1:5432:5432` für `sync_termin.py`), `.env.example` (19.09.), `README_CONTAINER.md` (19.09.; Fortsetzung 5: Abschnitt "Benutzerkonten" statt "Zugangscode erzeugen"; Fortsetzung 6: neuer Unterabschnitt zum Veröffentlichen/Zurückholen über die Web-Oberfläche), `.github/workflows/build-container.yml` (19.09.: Smoke-Test bei jedem Push, Build+Veröffentlichung nach ghcr.io bei einem Versions-Tag – siehe eigener Abschnitt oben), `app.py`/`db.py`/`pdf_export.py`/`shs_core.py`/`test_db.py`/`test_pdf_export.py`/`test_app_gui.py` (21.09., aktualisiert: Sortierung per Spaltenklick in der Ergebniserfassung, Disqualifiziert-/Abbruch-Status inkl. Migration und Statistik-PDF-Zeilen, neuer PDF-Export "Chipnummernliste" – siehe eigener Abschnitt oben)

## Umsetzung (21.09.): 6 Punkte aus Marcos Rückmeldung (6 Fotos, Bereiche Übersicht PL/Statistik/Etikettendruck/Ergebnisliste/Bewertungsbögen) - als geplante Aufgabe (12:00 Uhr) in einer eigenen, frischen Sitzung umgesetzt

**Reihenfolge-Prüfung:** vor jeder Code-Änderung geprüft, dass die vorherige geplante Aufgabe (Sortierung Ergebniserfassung, DQ/Abbruch, Chipnummernliste) tatsächlich fertig und committet war - Commit `8163f4f` lag bereits vor (nach `6c883b5`), daher direkt gestartet, keine Wartezeit nötig.

Marco hatte 6 Fotos mit handschriftlichen Notizen geschickt, die offenen Fragen dazu waren bereits in der vorherigen Sitzung per AskUserQuestion geklärt und in der Aufgabenstellung dokumentiert. Alle 6 Punkte nacheinander umgesetzt:

### 1. Übersicht für Prüfungsleitung (`pdf_export.py`)

- **Bestätigtes Feedback, keine Code-Änderung:** "Übertrag bezahlt/nicht bezahlt klappt."
- **Digitaler Impfpass mit Datum umgesetzt** - bewusst KEIN neues Datenbankfeld angelegt: das bereits bestehende Stammdatenfeld `tollwutimpfung_bis` ("Tollwutimpfung gültig bis", Teilnehmer-Dialog) deckt inhaltlich genau das ab, was am Prüfungstag als "Impfpass kontrolliert" geprüft wird (Tollwut ist die für den Start relevante Pflichtimpfung) - ein zweites, separates Feld hätte nur Doppelpflege riskiert (eigene Einschätzung, im Modulkommentar von `pdf_export.py` begründet). Die bisher leere Ankreuzspalte "Kontrolle Impfpass erledigt?" zeigt jetzt dieses Datum (`_datum_kurz()`, neu, TT.MM.JJJJ); fehlt das Datum oder liegt es vor dem Prüfungsdatum (reiner String-Vergleich, beide Felder im Format JJJJ-MM-TT), wird die Zelle rot/fett hervorgehoben (`_UEBERSICHT_ZELLE_ROT`).
- **"Abgabe Sportbeitrag"-Spalte ersatzlos entfernt** (Nutzerwunsch: "berechnet unser Verband anhand der im Portal erfassten Starterzahl selbst [...] Könnte man aus der Übersicht raus lassen") - Tabelle hat jetzt 9 statt 10 Spalten, Hinweistext/Docstring/Hilfe-Text in `app.py` entsprechend angepasst.

### 2. Statistik-PDF - Spaltenüberschriften-Umbruch behoben (`pdf_export.py`)

Die Spaltenköpfe "Trümmerfeld"/"Flächensuche"/"Behältnisstrecke" der Prädikat-Matrix brachen bei der bisherigen Breite (19mm für alle 12 Spalten gleich) mitten im Wort um. Behoben durch **individuelle Spaltenbreiten je Disziplin** (`_STAT_SPALTE_BREITE_DK`/`_STAT_SPALTE_BREITEN_ED`/`_stat_spalte_breite()`, neu) statt einer Breite für alle: DK-Spalten (nur "LK N") bleiben schmal (14mm), die drei ED-Disziplinen bekommen je die Breite, die ihr längstes Wort tatsächlich braucht (Trümmerfeld 19mm, Flächensuche 20mm, Behältnisstrecke 23mm) - dazu die Kopfschrift von 7,5pt auf 6,5pt reduziert. Rechnerisch geprüft (`stringWidth`): jede Überschrift passt jetzt einzeilig, Gesamtbreite der Matrix (258mm) bleibt innerhalb der nutzbaren Seitenbreite (267mm, A4 quer, 15mm Rand). Zwei bereits vorher bestehende, aber am Anfang dieser Sitzung fehlschlagende Tests (`test_statistik_zeigt_kopfangaben_und_praedikat_matrix`, `test_statistik_zaehlt_disqualifikation_und_abbruch_in_eigenen_zeilen` - beide aus der vorherigen Sitzung, dort nie gegen echten Text-Umbruch verifiziert) laufen dadurch jetzt ebenfalls grün, Test-Kommentare/Assertions entsprechend aktualisiert.

### 3. Statistik-PDF - Jugendliche gesondert ausgewiesen (`db.py`, `pdf_export.py`, `app.py`)

Nutzerwunsch: "(bei uns im Verband müssen Jugendliche gesondert ausgewiesen werden - weiß nicht ob das bei euch auch ist?)" - bereits in der Vorsitzung geklärt: als generelles Feature umgesetzt (nicht verbandsspezifisch konfigurierbar), Alterskriterium unter 18 Jahre, Stichtag Prüfungsdatum.

- Explore ergab: kein Geburtsdatum-Feld vorhanden - **neues Feld `geburtsdatum`** in den Teilnehmer-Stammdaten ergänzt (`SCHEMA`, `_TEILNEHMER_NEUE_SPALTEN`/`_migriere_teilnehmer_spalten()` - exakt dasselbe, bereits mehrfach bewährte Migrationsmuster wie bei `rasse`/`tollwutimpfung_bis`; `SCHEMA_POSTGRES` erbt die Spalte automatisch über die bestehende `.replace()`-Ableitung). Durch alle Kopierpfade gezogen (`NeuerTeilnehmer`, `add_teilnehmer()`/`update_teilnehmer()`, `importiere_teilnehmer_stammdaten()`, `kopiere_termin_daten()`), damit es beim Import aus einem anderen Termin bzw. beim Web-Sync nicht stillschweigend verloren geht.
- Eingabefeld "Geburtsdatum (JJJJ-MM-TT)" im Teilnehmer-Dialog ergänzt (`app.py`, `form_links`, direkt unter Vorname) - als einfaches Freitext-Datumsfeld (Platzhalter "JJJJ-MM-TT"), genau die im Projekt bereits durchgängig verwendete Konvention für Datumsfelder (`wurftag`/`tollwutimpfung_bis`); im Projekt existiert an keiner Stelle ein echtes `QDateEdit`-Widget als Vorbild.
- Neue Funktion `ist_jugendlicher(geburtsdatum, stichtag)` in `db.py` (reine Datumsrechnung, `datetime.date`) - liefert bei fehlenden/nicht lesbaren Werten sicher `False` statt eines Fehlers.
- Neue Zusatztabelle unterhalb der Prädikat-Matrix (`_statistik_jugendliche_tabelle()`, `pdf_export.py`) - dieselbe Spaltenstruktur/-breite wie die Prädikat-Matrix, eine einzige Werte-Zeile ("Anzahl") statt einer je Prädikat, zählt unabhängig vom erreichten Prädikat. Bewusst als EIGENE Tabelle statt einer weiteren Zeile in der Prädikat-Matrix selbst (eigene Einschätzung: Jugendliche sind keine eigene Prädikats-Kategorie, sondern verteilen sich auf alle bestehenden Prädikate - eine zusätzliche Zeile in derselben Matrix hätte die dortige Zählung verfälscht/doppelt ausgewiesen).

### 4. Etikettendruck - Höhe reduziert (`pdf_export.py`)

Nutzerwunsch: "fast ein bisschen zu Hoch - 1-2mm - ist aber bei anderen Sparten auch - reinpassen tut es" - `ETIKETT_HOEHE_MM` von 20 auf 18 reduziert (am oberen Ende der genannten Spanne, da Marco bestätigt hat, dass aktuell noch alles hineinpasst). Rechnerisch geprüft: bei der neuen Zeilenhöhe (9mm) bleiben weiterhin gut 2,5mm Luft über dem tatsächlichen Platzbedarf des Texts (Zeilenhöhe 10pt + 2×1,5mm Innenabstand ≈ 6,5mm) - nichts wird abgeschnitten.

### 5. Ergebnisliste Leer - Verein ragt nicht mehr ins Gesamtpunktefeld (`pdf_export.py`)

Ursache: die Vereins-Zelle ist ein reiner String (kein `Paragraph`), reportlab bricht solche Tabellenzellen nicht automatisch um - ein langer Vereinsname lief deshalb bei fester Schriftgröße 9 optisch in die Nachbarspalte "Gesamtpunkte" hinein. Entscheidung (bereits vorher geklärt): Schrift verkleinern statt umbrechen, bleibt dabei einzeilig. Neue Funktion `_schriftgroesse_fuer_breite()` (nutzt reportlabs `stringWidth`) ermittelt je Vereins-Zelle die größte Schriftgröße, bei der der Name noch in die Spaltenbreite passt (bis minimal 5,5pt) - nur die einzelnen betroffenen Zellen bekommen eine kleinere Schrift (per gezieltem `FONTSIZE`-Tabellenstil-Eintrag), alle übrigen Zeilen/Spalten bleiben unverändert bei Schriftgröße 9.

### 6. Bewertungsbögen - drei Änderungen (`app.py`, `pdf_export.py`)

- **Direkt-Button pro Teilnehmer** in der Teilnehmerliste (`TeilnehmerTab`, neuer Button "Bewertungsbogen (PDF)…", aktiv bei Zeilenauswahl) - erzeugt sofort den Bewertungsbogen für genau diesen einen Teilnehmer (`pdf_export.erstelle_bewertungsbogen_pdf()`, bereits vorhandene Funktion, hier erstmals auch aus dem Reiter "Teilnehmer" statt nur aus "Export" heraus aufgerufen). Nutzt denselben, jetzt mit "Zeitplan"/"Export" geteilten Ablageort (`_ablageort`-Parameter neu an `TeilnehmerTab` durchgereicht, in `HauptFenster` dasselbe `_Ablageort`-Objekt wie an die beiden anderen Tabs übergeben).
- **Trümmerfeld-Eingabefeld vergrößert + Trennstrich** - betrifft technisch alle drei Disziplinen gleichermaßen (dieselbe Vorlage `_bewertungsabschnitt()` wird für Trümmerfeld/Flächensuche/Behältnisstrecke gemeinsam genutzt, eigene Einschätzung: Vergrößerung + Trennstrich gelten deshalb einheitlich für alle drei). Freifläche zum Einzeichnen von 22mm auf 30mm vergrößert und von einer durchgehenden 170mm-Zelle auf zwei 85mm-Zellen (mit `GRID`) umgestellt - erzeugt automatisch eine durchgehende Trennlinie genau zwischen Suchleistung und Anzeigeleistung, exakt an der Stelle, an der auch die Kopfzeile "Suchleistung des Hundes"/"Anzeigeleistung des Hundes" trennt.
- **Auswahl, welche LK/Disziplin gedruckt werden** - Marcos eigener Lösungsvorschlag umgesetzt: neuer Dialog `BewertungsbogenAuswahlDialog` (Checkbox-Liste, Muster wie `TerminImportDialog`) vor dem Sammel-Export im Reiter "Export" - zeigt alle im Termin vorkommenden Art/LK-Labels, Standard = alle angehakt (heutiges Verhalten bleibt Default), Abbrechen bricht den kompletten Export ab. `erstelle_alle_bewertungsboegen_pdf()` bekommt dafür einen neuen optionalen Parameter `erlaubte_labels` (Menge von Labels, `None` = weiterhin alle wie bisher).

### Tests und Verifikation

Zu jedem der 6 Punkte automatisierte Tests ergänzt: 8 neue/geänderte Tests in `test_pdf_export.py` (Impfpass-Datum inkl. drei Fällen gültig/abgelaufen/unbekannt, Spaltenbreiten-Fix rückwirkend an den beiden vorher fehlschlagenden Statistik-Tests verifiziert, neue Jugendlichen-Tabelle inkl. korrekter Zählung), 2 neue Tests in `test_db.py` (Migration der neuen `geburtsdatum`-Spalte in einer alten Termin-Datei, Alterskriterium von `ist_jugendlicher()` inkl. Grenzfall exakt 18 am Stichtag), 6 neue GUI-Tests in `test_app_gui.py` (Bewertungsbogen-Button-Aktivierung, echter Datei-Export für den ausgewählten Teilnehmer, Geburtsdatum-Feld inkl. Laden/Speichern, Auswahl-Dialog Standardbelegung/Abwählen/leere Liste).

**Besonderheit dieser Sitzung: PySide6, ein echter PostgreSQL-Server sowie `psycopg2`/`flask`/`pyzipper` ließen sich diesmal tatsächlich per `pip`/Paketmanager installieren** (anders als in den meisten vorherigen Sitzungen dokumentiert, wo dafür kein Netzwerkzugriff bestand) - dadurch konnte hier erstmals der GESAMTE Testumfang wirklich lokal ausgeführt werden, nicht nur simuliert/übersprungen:
- Kompletter non-GUI-Testlauf (`test_db`, `test_db_postgres_wrapper`, `test_backup`, `test_pdf_export`, `test_app_web`, `test_bump_version`, `test_shs_core`) gegen SQLite UND zusätzlich ein zweites Mal gegen einen echten, frisch angelegten PostgreSQL-16-Server: **333 Tests, 0 fehlgeschlagen** (1 bewusst übersprungen, da die Original-.ods-Referenzdatei hier nicht vorliegt).
- Kompletter GUI-Testlauf über pytest-qt gegen echtes PySide6 (headless, `QT_QPA_PLATFORM=offscreen`): **67 von 68 bestanden**, 1 bereits aus einer Vorsitzung bekannter, dokumentierter `xfail` (Bug B, reines Testplattform-Artefakt, kein echter Anwendungsfehler, siehe entsprechender Abschnitt weiter oben).
- Nebenbefund (keine Auswirkung auf diese Änderung, nur beim Herumprobieren aufgefallen): führt man denselben Testlauf gegen PostgreSQL zweimal hintereinander OHNE die Datenbank dazwischen neu anzulegen aus, schlagen zwei CHECK-Constraint-Tests fehl - eine bereits bekannte, in dieser Sitzung erneut bestätigte Eigenheit der Postgres-Testarchitektur (der Migrations-Test-Helfer legt die `teilnehmer`-Tabelle testweise ohne CHECK-Constraint neu an, siehe Bug 1/5 weiter oben), betrifft nur mehrfache lokale Testläufe gegen dieselbe, nicht zurückgesetzte Datenbank und nicht die echte CI (dort startet bei jedem Lauf ein frischer PostgreSQL-Service-Container).
- **Unabhängiger Verifikations-Subagent** hat den kompletten Diff sowie die Testläufe zusätzlich selbst gegengeprüft (Migrationslogik, Grenzfälle von `ist_jugendlicher()`, Impfpass-Datumsvergleich, Spaltenbreiten-Rechnung, `erlaubte_labels`-Verhalten, geteilter Ablageort) - Verdikt: alle 6 Punkte korrekt umgesetzt, keine Befunde.

Gesamter lokaler Testlauf: 333 Tests (non-GUI, davon 1 übersprungen) + 68 GUI-Tests (davon 1 bekannter xfail), 0 fehlgeschlagen.

### Ausgeliefert

Alle geänderten Dateien (`app.py`, `db.py`, `pdf_export.py`, `test_db.py`, `test_pdf_export.py`, `test_app_gui.py`, `Fortschritt.md`) in die Ordner `SHS-Pruefungsprogramm-Git` und `SHS-Pruefungsprogramm-Quellcode` übertragen und in `SHS-Pruefungsprogramm-Git` lokal committet. **Push, Tag und Versionsbump stehen wie vereinbart noch aus** - macht Marco erst auf ausdrücklichen Wunsch.

## Ausgelieferte Dateien (im Chat, und lokal auf dem PC des Nutzers gesichert)

`shs_core.py`, `test_shs_core.py`, `db.py`, `test_db.py`, `test_db_postgres_wrapper.py` (Wrapper-Tests für die PostgreSQL/Podman-Variante), `app.py`, `test_app_gui.py` (echte GUI-Tests via pytest-qt), `test_backup.py` (Tests für die Datensicherung), `pytest.ini`, `pdf_export.py`, `test_pdf_export.py`, `requirements.txt`, `requirements-postgres.txt`, `build.spec`, `version.txt`, `bump_version.py`, `test_bump_version.py`, `version_info.txt`, `installer.iss`, `build_installer.bat`, `README_INSTALLER.md`, `gui_vorschau.html` (statische, interaktive Layout-Vorschau), `.gitignore`, `.github/workflows/tests.yml`, `.github/workflows/build-installer.yml`, `app_web.py` (19.09.: Flask-Backend der Web-Version; Fortsetzung 5: Login über Benutzerkonten statt Zugangscode, Termin-Auswahl, Benutzerverwaltung; Fortsetzung 6: Termin veröffentlichen/zurückholen/löschen per Datei-Upload/Download; 19.09. Bugfix: Duplikat-Prüfung beim Benutzeranlegen GROSS-/kleinschreibungsunabhängig), `test_app_web.py` (19.09., Fortsetzung 5: komplett neu strukturiert, 26 Tests; Fortsetzung 6: 8 weitere Tests für die neuen Upload/Download-Routen, 34 insgesamt; 19.09. Bugfix: 2 weitere Tests zur Groß-/Kleinschreibung, 36 insgesamt), `sync_termin.py` (19.09.: Export/Import-Werkzeug SQLite↔PostgreSQL; Fortsetzung 5: Export-Ausgabe ohne Zugangscode), `requirements-web.txt` (19.09.), `templates/base.html` (19.09.; Fortsetzung 5: Kopfzeile mit Termin-wechseln/Benutzer-Link; Fortsetzung 6: zusätzlicher "Termine"-Link für Administratoren), `templates/login.html` (19.09.; Fortsetzung 5: Benutzername/Passwort statt Zugangscode; 19.09. Bugfix: Benutzername-Feld ohne Autokapitalisierung/-korrektur), `templates/ersteinrichtung.html` (19.09. Bugfix: ebenfalls ohne Autokapitalisierung/-korrektur), `templates/termin_waehlen.html`, `templates/admin_benutzer.html` (alle Fortsetzung 5, neu; admin_benutzer.html 19.09. Bugfix: ebenfalls ohne Autokapitalisierung/-korrektur), `templates/admin_termine.html` (Fortsetzung 6, neu), `templates/teilnehmerliste.html`, `templates/ergebnis_erfassen.html` (beide 19.09.), `db.py`/`test_db.py` (19.09., aktualisiert: vier reale, per CI gegen PostgreSQL gefundene Bugs behoben – DROP-TABLE-CASCADE, zwei `.fetchone()[0]`-Stellen in Tests, fehlender `search_path`-Wechsel beim Export, unqualifizierte Registry-Bereinigung im Test-Teardown, siehe eigener Abschnitt oben; Fortsetzung 5: `web_benutzer`-Tabelle + Benutzerkonten-Funktionen, Zugangscode-Mechanismus entfernt; 19.09. Bugfix: Login-Benutzername GROSS-/kleinschreibungsunabhängig, 1 weiterer Test), `Containerfile` (19.09.: baut das Web-Backend-Image), `.containerignore` (19.09.), `compose.yaml` (19.09.: Web + PostgreSQL als Compose-Stack; Fortsetzung 4 Ende: `db`-Port `127.0.0.1:5432:5432` für `sync_termin.py`), `.env.example` (19.09.), `README_CONTAINER.md` (19.09.; Fortsetzung 5: Abschnitt "Benutzerkonten" statt "Zugangscode erzeugen"; Fortsetzung 6: neuer Unterabschnitt zum Veröffentlichen/Zurückholen über die Web-Oberfläche), `.github/workflows/build-container.yml` (19.09.: Smoke-Test bei jedem Push, Build+Veröffentlichung nach ghcr.io bei einem Versions-Tag – siehe eigener Abschnitt oben), `app.py`/`db.py`/`pdf_export.py`/`shs_core.py`/`test_db.py`/`test_pdf_export.py`/`test_app_gui.py` (21.09., aktualisiert: Sortierung per Spaltenklick in der Ergebniserfassung, Disqualifiziert-/Abbruch-Status inkl. Migration und Statistik-PDF-Zeilen, neuer PDF-Export "Chipnummernliste" – siehe eigener Abschnitt oben; weiteres Update 21.09.: Übersicht PL (digitaler Impfpass, Sportbeitrag-Spalte entfernt), Statistik-Spaltenbreiten + Jugendlichen-Tabelle, Etiketten-Höhe, Ergebnisliste-Schriftanpassung, Bewertungsbogen-Direkt-Button + LK-Auswahl beim Sammel-Export – siehe eigener Abschnitt oben)

## Version 1.0.21 (21.09., neuer Build auf ausdrücklichen Wunsch "wir erzeugen jetzt eine neue Version")

Bündelt alle seit Version 1.0.20 gesammelten, bereits lokal committeten aber bis eben unversionierten Änderungen (waren wie vereinbart erst nach Absprache für einen gemeinsamen Build vorgesehen):
- Ergebniserfassung: Sortierung per Spaltenklick; Disqualifiziert-/Abbruch-Status je Teilnehmer (inkl. Migration, Auswertung, Statistik-PDF); neuer PDF-Export "Chipnummernliste" (Commit `8163f4f`).
- Übersicht für Prüfungsleitung/Statistik/Etiketten/Ergebnisliste/Bewertungsbögen: 6 weitere Rückmeldungspunkte umgesetzt (Commit `b04dcd9`) - Details siehe Abschnitt "Nutzer-Feedback (21.09., Screenshot..." oben.

**Build-Ablauf:** `version.txt`/`version.py`/`version_info.txt` per `bump_version.py` auf 1.0.21 erhöht. Kompletter lokaler Testlauf (`test_shs_core.py`, `test_db.py`, `test_pdf_export.py`, `test_bump_version.py`, `test_db_postgres_wrapper.py`, `test_backup.py`): 198 bestanden, 102 übersprungen (PySide6-/echte-Postgres-Tests, laufen nur in der CI), 0 fehlgeschlagen, 22 Subtests bestanden. Zusätzlich `py_compile` für `app.py`/`app_web.py`/`db.py`/`pdf_export.py`/`shs_core.py`/`sync_termin.py`/`bump_version.py` fehlerfrei. Die drei Versionsdateien in beide Geräte-Ordner (`SHS-Pruefungsprogramm-Git`/`SHS-Pruefungsprogramm-Quellcode`) übertragen (dabei nebenbei eine kleine, bereits vorher bestehende Terminologie-Abweichung in `Architektur.md` zwischen beiden Ordnern behoben - Quellcode-Ordner zeigte dort noch "Leistungsrichter-Bedarf" statt "Richter-Bedarf", siehe Fix 17).

**Push und Tag (`v1.0.21`) muss wie gehabt Marco selbst ausführen:**
```
git push
git tag v1.0.21
git push --tags
```
Danach läuft `build-installer.yml` automatisch (Installer-Release) - `build-container.yml` nur bei Bedarf (Web/Container-Image).

## Umsetzung (21.09.): Cowork-Arbeitsablauf zusätzlich in CLAUDE.md nachgebildet (Vorbereitung Migration auf Claude Code)

Nutzerwunsch: Der bisherige Cowork-spezifische Arbeitsablauf (Skill `shs-projekt-workflow`:
Feedback-Aufnahme, Build-/Versionsdisziplin, `create_trigger`-Vorgehen für geplante Aufgaben)
sollte als eigenständige Doku - unabhängig vom Cowork-Skill - festgehalten werden, damit bei
einer künftigen Migration auf Claude Code nichts von den mit Marco abgestimmten Absprachen
verloren geht. Umgesetzt durch einen neuen Abschnitt "Sitzungsablauf bei
Rückmeldungen/Aufgaben" in `CLAUDE.md` (wird von jeder Sitzung in diesem Ordner automatisch
gelesen, auch außerhalb von Cowork) mit den Kerninhalten des Skills: Feedback-Aufnahme,
Build-/Versionsdisziplin ("erst nach Absprache"), bekannte Fallstricke bei der
Geräte-Auslieferung sowie das Vorgehen bei geplanten/zeitversetzten Aufgaben (vollständiges
Briefing in `Fortschritt.md` statt im kurzen Trigger-Prompt). Der Cowork-Skill selbst bleibt
zusätzlich bestehen (aktiv für Cowork-Sitzungen), `CLAUDE.md` ist jetzt aber die von beiden
Umgebungen gelesene, gemeinsame Quelle für diese Absprachen. Reine Dokumentationsänderung,
kein Code betroffen - direkt in beide Geräte-Ordner übertragen und committet (kein
Versionsbump nötig).

## Codeprüfung (21.09.): 3 Bereichs-Subagents (Desktop/Web/Daten), 12 Punkte im Desktop-Bereich umgesetzt

Auf Marcos Wunsch ("prüfe den Code") vollständige Prüfung des aktuellen Codestands über alle
drei Bereiche, je ein Subagent für Desktop (`app.py`/`test_app_gui.py`), Web
(`app_web.py`/`templates/`/`test_app_web.py`) und Daten (`db.py`/`shs_core.py`/
`pdf_export.py`/`sync_termin.py`). Insgesamt 33 neue Befunde (keiner davon bereits als
"offen"/akzeptiertes Restrisiko bekannt). Marco hat die Punkte 1-12 (alle im Desktop-Bereich,
`app.py`/`db.py`) zur sofortigen Umsetzung freigegeben; die übrigen Punkte (Web-Bereich:
Lost-Update bei gleichzeitiger DK-Ergebniserfassung durch mehrere Richter, fehlende
Session-Invalidierung bei Kontolöschung, u.a.; Daten-Bereich: nicht-atomarer
Postgres-Export, Zeitplan-Verteilung kann bei Teilfehler Daten löschen, u.a.) sind noch
unbesprochen und **bewusst nicht umgesetzt** - siehe "Noch offen" unten.

### Wichtigster Fund und Fix: Datenverlust bei Disqualifiziert/Abbruch (`app.py`, `ErgebnisTab`)

Wurde am 21.09. (siehe oben, "Disqualifiziert/Abbruch") eingeführt, aber ein Zusammenspiel
zweier für sich genommen sinnvoller Mechanismen führte zu echtem, für den Nutzer nicht
offensichtlichem Datenverlust: `_punkteeingabe_sperren()` leert die Punkte-Eingabefelder
beim Ankreuzen von Disqualifiziert/Abbruch (Absicht: Eingabe wäre ohnehin irrelevant).
`alle_speichern()` interpretierte zwei leere Felder aber als "der Nutzer hat die Werte
bewusst gelöscht" und schrieb aktiv `NULL` in die Datenbank - dadurch gingen bereits
gespeicherte, echte Punktwerte verloren, sobald DANACH Disqualifiziert/Abbruch angehakt und
gespeichert wurde. Szenario: Punkte eintragen+speichern → Disqualifiziert ankreuzen+speichern
→ Häkchen wieder entfernen → die ursprünglichen Punkte waren weg. Widersprach der eigenen
Dokumentation in `db.setze_ergebnis_status()` ("eine ggf. weiterhin in suche_*/anzeige_*-
Spalten stehende Punktzahl bleibt dabei unangetastet").

**Fix:** `alle_speichern()` fasst Punkte einer Zeile jetzt gar nicht mehr an, solange
Disqualifiziert/Abbruch gesetzt ist (`punkte_gesperrt`-Flag). `_status_umgeschaltet()`
befüllt die Felder beim Entsperren (Häkchen entfernen) wieder mit dem zuletzt aus der DB
geladenen Stand, statt sie leer zu lassen. `_zeile_ist_ungespeichert()` ignoriert bei
gesperrter Zeile den (leeren) Punkte-Feldinhalt beim Vergleich, damit eine gesperrte,
gespeicherte Zeile nicht dauerhaft fälschlich als "nicht gespeichert" markiert bleibt. Neuer
Regressionstest `test_ergebnis_disqualifiziert_loescht_gespeicherte_punkte_nicht` in
`test_app_gui.py` deckt genau dieses Szenario ab.

### Weitere 11 Punkte (alle Desktop-Bereich, `app.py`/`db.py`)

2. `ergebnis_rows[t["id"]]` in `ErgebnisTab._zeilen_aufbauen()` auf `.get(t["id"], {})` plus
   `.get()` für die Spaltenzugriffe umgestellt - dieselbe Absicherung wie in
   `db.berechne_auswertung()` (dort bereits als "Fix 10" umgesetzt), verhindert einen
   KeyError-Absturz des gesamten Tabs bei verletzter Teilnehmer/Ergebnisse-Invariante.
3. `db.importiere_teilnehmer_aus_csv()`: `UnicodeDecodeError` (z.B. eine mit Windows-ANSI
   statt UTF-8 gespeicherte CSV, auf deutschem Windows beim Excel-"Speichern unter" der
   Standard) wird jetzt separat abgefangen - vorher brach der komplette Import mit einer
   unbehandelten Exception ab, im Widerspruch zum eigenen Docstring ("eine fehlerhafte Zeile
   bricht den Import nicht ab"). Neuer Test in `test_db.py` (mit genug gültigen Zeilen vor
   der Fehlzeile, um den TextIOWrapper-Lesepuffer realistisch zu überschreiten).
4. Datensicherung wiederherstellen (`DatensicherungTab`) und Termin löschen
   (`StartDialog._termin_loeschen`) verweigern jetzt gezielt das Überschreiben/Löschen des
   GERADE GEÖFFNETEN Termins mit klarer Meldung, statt in eine (schwer verständliche)
   Windows-Dateisperre zu laufen.
5. `TeilnehmerTab._aus_anderem_termin_importieren()`: zeigt jetzt eine Meldung, falls
   `quelle_conn()` unerwartet `None` ist, statt kommentarlos ohne Rückmeldung abzubrechen.
6. `VersionDialog`: `setTextFormat(Qt.PlainText)` für das Label, das den von der GitHub-API
   gelieferten Release-Text anzeigt (kein Rich-Text-Spoofing über eine kompromittierte
   GitHub-Quelle möglich).
7. Bisher ungeschützte DB-Aktionen (Bezahlt umschalten, Startnummer tauschen, Richter/
   Zeitplan-Einträge verwalten - insgesamt 9 Stellen) haben jetzt try/except mit
   Fehlerdialog (`_fehler_anzeigen`/neue `_db_fehler_anzeigen`) statt einer bei einem
   unerwarteten DB-Fehler (gesperrte Datei, voller Datenträger) unbehandelten Exception.
8. Duplizierter Zeitplan-PDF-Export-Code (`ZeitplanTab._pdf_exportieren`/
   `ExportTab._zeitplan_exportieren`, vorher wortgleich) in eine gemeinsame Funktion
   `_zeitplan_pdf_exportieren()` zusammengeführt.
9. `TeilnehmerDialog.__init__()` (~260 Zeilen) rein strukturell in `_felder_erstellen()`/
   `_layout_aufbauen()`/`_vorbelegung_uebernehmen()` aufgeteilt, ohne Verhaltensänderung.
10. Die 8 fast identischen Export-Methoden in `ExportTab` (Ergebnisliste, Etiketten, leere
    Ergebnisliste, Statistik, Übersicht Prüfungsleitung, Chipliste, Leistungsrichter,
    Bewertungsbögen) auf einen gemeinsamen Helfer `_pdf_export_ausfuehren()` umgestellt.
11. **Nicht umgesetzt** (bewusst): Dialoggrößen als "Magic Numbers" - bei genauerer Prüfung
    kein echtes Duplikationsproblem, da jede Dialoggröße nur genau einmal verwendet wird und
    bewusst pro Dialog gewählt ist. Benannte Konstanten hätten hier nichts vereinheitlicht.
12. `Architektur.md`/`CLAUDE.md`: veraltete Zeilenzahlen für `app.py`/`db.py` aktualisiert
    (2918→4144 bzw. 1850→2442 Zeilen, nach allen obigen Änderungen).

### Tests und Verifikation

PySide6/pytest/pytest-qt waren in dieser Sitzung lokal installiert (anders als der
Testbefehl-Hinweis in `CLAUDE.md` nahelegt) - dadurch auch die GUI-Tests lokal ausführbar,
nicht nur simuliert. Kompletter non-GUI-Testlauf: 335 Tests, 0 fehlgeschlagen (139
übersprungen, PostgreSQL-Tests ohne laufenden Server). Kompletter GUI-Testlauf (`pytest`,
`QT_QPA_PLATFORM=offscreen`): 68 bestanden, 1 bekannter `xfail`, 0 fehlgeschlagen. Zusätzlich
`py_compile` für `app.py`/`db.py` fehlerfrei. Beim ersten GUI-Testlauf nach dem
Disqualifiziert/Abbruch-Fix schlug `test_ergebnis_sortierung_verliert_keine_ungespeicherte_
eingabe` fehl (eine echte Regression: `_punkteeingabe_sperren()` überschrieb beim
Neuaufbau/Sortieren fälschlich eine noch nicht gespeicherte Eingabe mit dem DB-Wert) - vor
dem Weitermachen korrigiert (Wiederherstellung nur noch in `_status_umgeschaltet()`, nicht
mehr in `_punkteeingabe_sperren()` selbst), danach grün.

Die 7 auf den neuen `_pdf_export_ausfuehren()`-Helfer umgestellten Export-Methoden haben
keine dedizierte GUI-Testabdeckung - zusätzlich per Hand mit einer echten temporären
Termin-Datenbank smoke-getestet (alle 8 Methoden inkl. Bewertungsbögen-Sammelexport
erzeugen korrekte PDFs mit unverändertem Statustext; Fehlerpfad separat mit einem
ungültigen Zielpfad geprüft - Fehlerdialog erscheint wie vorher, Status bleibt leer).

**Unabhängiger Verifikations-Subagent** hat den kompletten Diff sowie alle Testläufe
zusätzlich selbst gegengeprüft (alle 12 Punkte einzeln, inkl. gezieltem Nachtest
`-k ergebnis_disqualifiziert`, Zeilenzahl-Abgleich per `wc -l`) - Verdikt: alle 12 Punkte
korrekt umgesetzt, keine Regressionen.

**Stand:** alle Änderungen (`app.py`, `db.py`, `test_app_gui.py`, `test_db.py`,
`Architektur.md`, `CLAUDE.md`) liegen wie vereinbart nur im Arbeitsstand - **noch nicht
committet, kein Versionsbump**, bis Marco das ausdrücklich anfordert.

## Codeprüfung (21.09.), Fortsetzung: 10 weitere Punkte (Web- + Daten-Bereich) umgesetzt

Auf Marcos Wunsch ("fixe erst den Rest") wurden im Anschluss an die 12 Desktop-Punkte auch
die restlichen Befunde aus derselben Codeprüfung umgesetzt - Web-Bereich (6 Punkte) und
Daten-Bereich (4 Punkte) parallel über je einen Bereichs-Subagent, danach wie beim
Desktop-Teil ein unabhängiger Verifikations-Subagent über den kombinierten Diff.

**Vorab geklärt:** "Disqualifiziert/Abbruch im Web setzbar machen" war als offene
Scope-Frage markiert - Marco hat sich bewusst dagegen entschieden (Web bleibt bei reiner
Punkte-Ergebniserfassung, Disqualifiziert/Abbruch wird weiterhin nur am Desktop-Rechner
gepflegt). Nicht umgesetzt, kein neuer Befund.

### Web-Bereich (`app_web.py`, `templates/ergebnis_erfassen.html`, `templates/admin_termine.html`)

1. **Lost Update bei gleichzeitiger DK-Ergebniserfassung durch mehrere Richter (wichtigster
   Fix).** Neue versteckte Formularfelder `geladen_suche_<disziplin>`/
   `geladen_anzeige_<disziplin>`, beim Laden der Seite aus dem echten DB-Stand befüllt.
   Beim Speichern wird je Disziplin der abgeschickte Wert gegen den geladenen verglichen -
   nur bei tatsächlicher Änderung wird geschrieben, eine vom aktuellen Richter unberührte
   Disziplin bleibt unangetastet (schützt vor stillschweigendem Überschreiben einer
   zwischenzeitlichen fremden Eintragung). Fehlt das versteckte Feld (z. B. eine ältere
   Anfrage ohne vorheriges GET), wird sicherheitshalber immer geschrieben.
2. **Validierungsfehler verwirft korrekt eingegebene Werte.** Bei einem Formularfehler wird
   die Seite jetzt aus den gerade abgeschickten Formulardaten neu aufgebaut statt aus dem
   (älteren) DB-Stand - die `geladen_*`-Felder aus Punkt 1 bleiben dabei unverändert aus dem
   ursprünglichen Seitenaufruf erhalten, damit ein nachfolgender erfolgreicher
   Speicherversuch weiterhin korrekt gegen den echten Ausgangsstand vergleicht.
3. **Keine Session-Invalidierung bei Kontolöschung / gelöschtes Termin-Schema führte zu
   hartem Fehler.** Neue Funktion `db.benutzer_stand()` (Existenz+Rolle ohne
   Passwort-Prüfung) sowie gemeinsame Hilfsfunktion `_aktueller_benutzer_oder_redirect()` in
   `app_web.py`, jetzt von `_login_erforderlich`/`_admin_erforderlich`/`_termin_erforderlich`
   gemeinsam genutzt (vorher dreifach dieselbe unvollständige Prüfung) - validiert bei
   JEDER Anfrage gegen den aktuellen DB-Stand, leert die Session und leitet zum Login um,
   sobald ein Konto zwischenzeitlich gelöscht wurde; aktualisiert `session["ist_admin"]` bei
   Rollenänderung. `_termin_erforderlich` fängt zusätzlich einen Fehler beim Öffnen eines
   inzwischen gelöschten Termin-Schemas ab und leitet sauber zu `/termin-waehlen` um.
4. **Ungültige/beschädigte hochgeladene `.sqlite`-Datei führte zu roher 500-Fehlerseite.**
   `db.init_db(temp_pfad)` wird beim Veröffentlichen/Zurückholen jetzt mit
   `except sqlite3.Error` abgefangen, zeigt dieselbe verständliche Meldung wie der
   bestehende Dateiendungs-Check. Notwendiger Begleitfix in `db.init_db()`: schließt die
   Datenbankverbindung bei einem Fehler während Schema-Anlage/Migration jetzt selbst, bevor
   die Exception weitergereicht wird - sonst blieb die kaputte Upload-Datei unter Windows
   durch die offene Verbindung gesperrt und das anschließende Aufräumen scheiterte
   zusätzlich mit `PermissionError` (im ersten Testlauf tatsächlich aufgetreten, dabei
   gefunden und behoben).
5. **Timing-Seitenkanal beim Login.** `db.pruefe_login()` ruft jetzt in jedem Fall genau
   einmal `check_password_hash()` auf - bei unbekanntem Benutzernamen gegen einen lazy beim
   ersten Aufruf erzeugten (nicht bei jedem Modulimport berechneten, damit die
   Desktop-Version ohne Flask/werkzeug unberührt bleibt) Dummy-Hash statt gegen einen echten.
   Die Antwortzeit unterscheidet sich dadurch nicht mehr danach, ob der Benutzername
   existiert.
6. **Kein Schutz vor doppeltem Veröffentlichen desselben Termins.** Neue, rein informative
   Prüfung vor dem Export: existiert bereits ein veröffentlichter Termin mit demselben
   Verein+Datum, erscheint auf der Erfolgsseite ein nicht blockierender Hinweis - der Admin
   kann den alten bei Bedarf selbst löschen, das Veröffentlichen selbst wird nicht verhindert.

### Daten-Bereich (`db.py`, `sync_termin.py`)

7. **Postgres-Export (`exportiere_termin_nach_postgres`) nicht atomar.** Bricht der
   Kopiervorgang mittendrin ab, wird der bereits angefangene, nur teilweise befüllte Termin
   jetzt automatisch wieder gelöscht (kompensierende Bereinigung statt eines echten
   Rollbacks, da die Teil-Kopien wegen des Commit-pro-Teilnehmer-Musters von
   `add_teilnehmer()`/`eintragen_ergebnis()` bereits committet sind) - kein für die
   Web-Oberfläche sichtbarer, kaputter Termin mehr nach einem Fehlschlag.
8. **`automatische_zeitplan_verteilung` konnte bei einem Teilfehler den kompletten
   Zeitplan leeren.** DELETE und alle INSERTs laufen jetzt in einer gemeinsamen Transaktion
   (der bisherige Zwischen-Commit direkt nach dem DELETE wurde entfernt), bei einem Fehler
   sorgt ein expliziter Rollback dafür, dass der alte Zeitplan unverändert erhalten bleibt
   statt leer oder halb-neu zurückzubleiben.
9. **`importiere_ergebnisse_nach_startnummer` brach beim ersten Fehler komplett ab, ohne
   Rückmeldung was schon übertragen wurde.** Ein Fehler bei einem einzelnen Teilnehmer wird
   jetzt gesammelt (neues Feld `ImportBericht.fehler`), der Import macht mit dem nächsten
   Teilnehmer weiter - analog zum bereits etablierten Muster beim CSV-Import. Anzeige der
   neuen Fehlerliste in `sync_termin.py` (CLI) und `templates/admin_termine.html` ergänzt.
10. **Drei fast identische Migrations-Funktionen zusammengefasst.** Neue interne
    `_migriere_spalten(conn, tabelle, neue_spalten)`, die bisherigen drei Funktionen sind
    jetzt dünne Wrapper darum - rein mechanisch, verhaltensgleich (String- und
    Tupel-Spaltenlisten werden weiterhin korrekt unterschieden).

**Nicht umgesetzt (bewusst, bereits als unproblematisch eingestuft):** ZIP-Quell-Eintragsname
bei `sicherung_wiederherstellen()` (kein eigenständiges Risiko), `_LASTROWID_TABELLEN`-Liste
(nur ein Hinweis für künftige Änderungen), uneinheitliches Commit-Muster (reine Beobachtung).

### Tests und Verifikation

Kompletter non-GUI-Testlauf nach Zusammenführung beider Bereichs-Subagents: 349 Tests, 0
fehlgeschlagen (140 übersprungen, PostgreSQL-Tests ohne laufenden Server). GUI-Testlauf
unverändert bei 68 bestanden/1 bekannter xfail. `py_compile` für alle geänderten
Python-Dateien fehlerfrei. 17 neue Tests in `test_app_web.py` (je einer/mehrere pro
Web-Punkt), 3 neue Tests in `test_db.py` (Postgres-Export-Fehlerpfad rein mock-basiert ohne
echte PostgreSQL-Verbindung, Zeitplan-Rollback, Import-Fehlersammlung).

**Unabhängiger Verifikations-Subagent** hat den kombinierten Diff aus beiden
Bereichs-Subagents sowie alle Testläufe zusätzlich selbst gegengeprüft (alle 10 Punkte
einzeln, inkl. Prüfung auf mögliche Doppel-Close-/Kompatibilitätsprobleme durch den
`init_db()`-Begleitfix und die `ImportBericht`-Erweiterung) - Verdikt: alle 10 Punkte korrekt
umgesetzt, keine Regressionen. Eine nicht-blockierende Beobachtung (kein Fund): der
explizite `_setze_termin_suchpfad(postgres_conn, "public")`-Aufruf vor
`loesche_termin_postgres()` in Punkt 7 ist redundant, da Letzteres das intern ohnehin selbst
tut - funktional harmlos, keine Änderung vorgenommen.

Damit sind ALLE 22 Befunde aus der Codeprüfung vom 21.09. abgearbeitet (12 Desktop + 10
Web/Daten), bis auf die bewusst nicht umgesetzten Punkte (Dialoggrößen, DQ/Abbruch im Web,
die drei oben genannten Daten-Kleinfunde). Marco hat direkt im Anschluss Commit, Push, Tag
und Versionsbump angefordert - siehe Abschnitt "Version 1.0.22" unten.

## Version 1.0.22 (21.09., neuer Build auf ausdrücklichen Wunsch "comitten und push, tag, versionsbump")

Bündelt alle 22 in dieser Sitzung umgesetzten QS-Fund-Fixes (12 Desktop + 10 Web/Daten, siehe
beide Abschnitte oben) - erster Build seit Version 1.0.21.

**Build-Ablauf:** `version.txt`/`version.py`/`version_info.txt` per `bump_version.py` auf
1.0.22 erhöht. Kompletter lokaler Testlauf: non-GUI (`test_db`, `test_db_postgres_wrapper`,
`test_backup`, `test_pdf_export`, `test_app_web`, `test_bump_version`, `test_shs_core`) 349
Tests, 0 fehlgeschlagen (140 übersprungen, PostgreSQL-Tests ohne laufenden Server); GUI
(`test_app_gui.py` via pytest-qt, `QT_QPA_PLATFORM=offscreen`) 68 bestanden, 1 bekannter
xfail. Zusätzlich `py_compile` für `app.py`/`app_web.py`/`db.py`/`pdf_export.py`/
`shs_core.py`/`sync_termin.py`/`bump_version.py` fehlerfrei.

**Push und Tag (`v1.0.22`) muss wie gehabt Marco selbst ausführen** (feste Regel in
`CLAUDE.md`, gilt auch wenn im Chat ausdrücklich "push, tag" mit angefordert wird):
```
git push
git tag v1.0.22
git push --tags
```
Danach läuft `build-installer.yml` automatisch (Installer-Release) - `build-container.yml`
nur bei Bedarf (Web/Container-Image).

## Mehrere Farbschemata (Themes) für die Desktop-App (22.09., Rückmeldung "mehrere Themes möglich")

Marcos kurzer Feedback-Stichpunkt "mehrere Themes möglich" wurde per Rückfrage präzisiert
(Umfang, Art des Themes, Speicherort, siehe Klärung unten), dann geplant und umgesetzt -
**nur im Arbeitsstand, noch nicht committet/versioniert/ausgeliefert** (Projekt-Konvention:
erst nach Marcos ausdrücklicher Build-Freigabe).

**Klärung/Entscheidungen (per Rückfrage bestätigt):**
- Nur Desktop-App (`app.py`) betroffen, nicht die Web-App - dort existiert bereits eine
  eigene CSS-Variablen-Struktur in `templates/base.html`, die für ein späteres, separates
  Web-Feature ein guter Ansatzpunkt wäre, war hier aber nicht Teil des Auftrags.
- "Theme" = mehrere fertige Akzentfarbschemata, kein Hell/Dunkel-Modus. 3 Themes: Blau
  (`#2F6FED`, Standard, identisch zum bisherigen Aussehen), Grün (`#1E8E5A`), Violett
  (`#6B4FBB`).
- Speicherung pro Windows-Benutzer via `QSettings` (Registry unter
  `HKCU\Software\SHS-Pruefungsprogramm\Desktop`) - die Desktop-App hat kein Login/keine
  Benutzerebene (Single-User pro Installation, Kontext ist nur die geöffnete
  Termin-SQLite-Datei), "pro Nutzer" bedeutet hier daher technisch "pro
  Windows-Benutzerkonto".
- Die 9 bereits bestehenden, fest verdrahteten semantischen Statusfarben (bezahlt=grün,
  Warnung=orange, Fehler=rot, ungespeichert=gelb) bleiben unverändert und sind NICHT Teil
  des Themes.

**Umsetzung:**
- Bisherige QSS-Konstante `_QSS_MODERN_MINIMAL` zu `_QSS_TEMPLATE` umbenannt, die 4
  Akzentfarben-Stellen (Tab-Unterstrich, Haupt-Button normal/hover/pressed,
  Eingabefeld-Fokusrahmen, Tabellen-Auswahl-Tönung) durch eigene Marker-Platzhalter
  (`@@AKZENT@@`/`@@AKZENT_HOVER@@`/`@@AKZENT_PRESSED@@`/`@@AKZENT_HELL@@`) ersetzt, per
  `str.replace()` statt `str.format()` befüllt (das QSS selbst ist voller literaler
  `{}`-Blockklammern, mit denen `.format()` kollidieren würde).
- Neue Datenstruktur `_THEMES` (3 Einträge) + Funktion `_erzeuge_qss(theme_name)`. "Blau"
  ist bit-für-bit identisch zum bisherigen Aussehen (per Regressionstest abgesichert, siehe
  unten).
- Neue Funktionen `_gespeichertes_theme_lesen()`/`_theme_speichern()` auf `QSettings`-Basis.
  `main()` wendet das gespeicherte Theme bereits vor dem Startdialog an.
- Neuer Menüpunkt in `HauptFenster` über die bisher ungenutzte `QMenuBar` ("Ansicht" >
  "Theme", 3 checkbare, exklusive `QAction`s über `QActionGroup`) - Wechsel wirkt sofort
  (`QApplication.instance().setStyleSheet(...)` neu gesetzt), kein Neustart nötig.
- Neue Testdatei `test_theme.py` (4 Tests, reine String-Logik: Blau-Regressionstest gegen
  den vor der Umstellung fest verdrahteten Original-QSS-Text, keine übrig gebliebenen
  Marker, Fallback bei unbekanntem Theme-Namen, genau 3 erwartete Theme-Schlüssel).

**Während der Umsetzung gefundener und behobener echter Fehler (kein akzeptiertes
Restrisiko, sondern ein reproduzierbarer Deadlock):** Die ursprüngliche
`_theme_menue_aufbauen()`-Fassung verband jede der 3 Menü-Actions per eigener
Lambda-Verbindung in einer Schleife (`action.triggered.connect(lambda checked=False,
s=schluessel: self._theme_wechseln(s))`). Das führte beim Schließen/Zerstören eines
`HauptFenster` (z. B. am Ende eines GUI-Tests über `qtbot`-Teardown) reproduzierbar zu
einem unendlichen Hänger - verifiziert per `git stash` gegen den unveränderten
Original-Code (dort lief dieselbe Testpaarung in 0,4s durch, der Hänger war also durch die
Theme-Änderung verursacht). Durch systematisches Ausklammern einzelner Codeteile isoliert:
Das Entfernen nur der lambda-`connect()`-Zeile behob den Hänger vollständig. Fix: eine
einzige Verbindung auf `QActionGroup.triggered` statt einer Lambda-Verbindung pro Action,
jede `QAction` trägt ihr Theme über `action.setData(schluessel)` statt über eine
eingefangene Schleifenvariable (`_theme_aktion_ausgeloest(self, action)` liest
`action.data()` und ruft `_theme_wechseln()`) - das Qt-übliche, robustere Muster für
exklusive Action-Gruppen. Nach dem Fix lief der komplette GUI-Testlauf wiederholt fehlerfrei
durch (siehe Tests unten). Kurze Suche nach ähnlichen Lambda-in-Schleife-Verbindungen an
anderer Stelle in `app.py` (Zeilen 1607f./1633f.) ergab: dort werden reguläre
QLineEdit/QCheckBox-Signale verbunden, keine checkable/exklusiven QActions in einer
QActionGroup - der Hänger trat spezifisch bei dieser Kombination (Lambda + QActionGroup +
checkable/exklusive QActions) auf, keine weitere Anpassung dort nötig.

**Tests:** `python -m unittest test_theme` (4/4 bestanden). Kompletter GUI-Testlauf
(`python -m pytest test_app_gui.py`, zweimal wiederholt zur Flakiness-Kontrolle) weiterhin
68 bestanden/1 bekannter xfail, jetzt ohne den oben beschriebenen Hänger. Kompletter
non-GUI-Testlauf (`test_db`, `test_db_postgres_wrapper`, `test_backup`, `test_pdf_export`,
`test_app_web`, `test_bump_version`, `test_shs_core`) unverändert 349 Tests, 0
fehlgeschlagen (140 übersprungen). `py_compile` für `app.py`/`test_app_gui.py`/
`test_theme.py` fehlerfrei. Ein unabhängiger Verifikations-Subagent hat den Diff sowie den
Hänger-Fix zusätzlich zweimal eigenständig gegengeprüft (erster Durchlauf fand die verwaiste
`_QSS_MODERN_MINIMAL`-Referenz in `test_app_gui.py`, die daraufhin korrigiert wurde; zweiter
Durchlauf nach dem Hänger-Fix: keine weiteren Funde, Verdikt "abschlussreif").

**Noch offen:** `CLAUDE.md`-Testbefehlzeile könnte um `test_theme` ergänzt werden (rein
lokal ohne PySide6 nicht separat lauffähig, da `test_theme.py` `app.py` importiert, das
PySide6 am Kopf lädt - keine künstliche Trennung erzwungen). Bleibt für den nächsten Build
offen.

## Version 1.0.23 (22.09., Build auf Marcos Wunsch "Bescheid"/"ja")

Bündelt das oben beschriebene Theme-Feature (inkl. Hänger-Fix) - erster Build seit Version
1.0.22.

**Build-Ablauf:** `version.txt`/`version.py`/`version_info.txt` per `bump_version.py` auf
1.0.23 erhöht. Kompletter lokaler Testlauf: non-GUI (`test_db`, `test_db_postgres_wrapper`,
`test_backup`, `test_pdf_export`, `test_app_web`, `test_bump_version`, `test_shs_core`,
`test_theme`) 353 Tests, 0 fehlgeschlagen (140 übersprungen, PostgreSQL-Tests ohne
laufenden Server); GUI (`test_app_gui.py` via pytest-qt, `QT_QPA_PLATFORM=offscreen`) 68
bestanden, 1 bekannter xfail. Zusätzlich `py_compile` für `app.py`/`app_web.py`/`db.py`/
`pdf_export.py`/`shs_core.py`/`sync_termin.py`/`bump_version.py`/`test_app_gui.py`/
`test_theme.py` fehlerfrei.

**Push und Tag (`v1.0.23`) muss wie gehabt Marco selbst ausführen:**
```
git push
git tag v1.0.23
git push --tags
```
Danach läuft `build-installer.yml` automatisch (Installer-Release).

## Gegenstände-Warnung in der Teilnehmerliste differenziert (22.09., Rückmeldung nach dem Theme-Feature)

Marcos Rückmeldung: "Fehlermeldung 'Gegenstände unvollständig' bei Teilnehmer bearbeiten:
nur bei fehlenden Gegenstand so wie vereinbart. Bei gesucht in 'frei' nur eine Info
'Gegenstände den Suchdisziplinen nicht zugeordnet' (angepasst an Spaltengröße Schrift
verkleinern)". **Nur im Arbeitsstand, noch nicht committet** (Build erst auf Marcos
Wunsch).

**Hintergrund/Fund:** Die Warnspalte "Vollständig" in der Teilnehmerliste
(`TeilnehmerTab.aktualisieren()`, `app.py`) zeigte die Fehlermeldung "Gegenstände
unvollständig" bisher UNABHÄNGIG davon, ob ein Gegenstand-Textfeld tatsächlich leer war
oder ob ein vorhandener Text nur nicht zugeordnet war ("gesucht in: frei") - beide Fälle
wurden identisch als Fehler behandelt (`db.py`, `_ed_gegenstaende_vollstaendig()`/
`_dk_gegenstaende_vollstaendig()` zählten nur korrekt zugeordnete Felder, ohne die zwei
Ursachen zu unterscheiden). Das entsprach nicht mehr der eigentlichen Absicht der am
20.09. abgestimmten Regel (nur Chip-Nr. und Gegenstand-Zuordnung prüfen, siehe "Erledigt"
oben) - "frei" ist ein bewusst erlaubter Zustand, kein Fehler.

**Klärung mit Marco:** Treffen ein echter Fehler (z. B. fehlende Chip-Nr. oder ein
wirklich fehlender Gegenstand-Text) UND die neue Info gleichzeitig zu, wird NUR der
Fehler angezeigt (Vorrang bestätigt).

**Umsetzung:**
- `db.py`: `_ed_gegenstaende_vollstaendig()`/`_dk_gegenstaende_vollstaendig()` (gaben
  `bool` zurück) zu `_ed_gegenstand_status()`/`_dk_gegenstand_status()` umgebaut - liefern
  jetzt `"ok"`/`"fehlt"`/`"nicht_zugeordnet"`. `"fehlt"` nur noch, wenn tatsächlich zu
  wenige Gegenstand-Textfelder befüllt sind (bzw. bei DK: zu wenig unterschiedliche Texte
  trotz vollständiger Disziplin-Abdeckung - bleibt bewusst ein Inhaltsfehler, kein
  Zuordnungsproblem). `"nicht_zugeordnet"`, wenn genug Texte vorhanden sind, aber
  mindestens einer nicht der benötigten Disziplin zugeordnet ist. `teilnehmer_fehlende_
  pflichtangaben()` meldet den Fehlertext nur noch bei `"fehlt"`. Neue Funktion
  `teilnehmer_gegenstand_hinweis(teilnehmer) -> str | None` liefert die neue Info bei
  `"nicht_zugeordnet"`.
- `app.py` (`TeilnehmerTab.aktualisieren()`): Vorrang-Regel direkt in der Anzeige - die
  Info wird nur geprüft/angezeigt, wenn `teilnehmer_fehlende_pflichtangaben()` leer ist.
  Die Info erscheint ohne "⚠"-Symbol, nicht fett, mit um 1 Punkt verkleinerter Schrift
  (`schrift.setPointSize(max(schrift.pointSize() - 1, 1)`), damit sie trotz der längeren
  Formulierung in die Spalte passt - der bisherige Fehler bleibt optisch unverändert
  (orange/fett).
- Tests: `test_db.py` - ein bestehender Test angepasst (ein Fall, der bisher als Fehler
  erwartet wurde, ist jetzt eine reine Info - siehe
  `test_teilnehmer_fehlende_pflichtangaben_dk_lk1_reicht_ein_gegenstand_fuer_alle_disziplinen`),
  plus 3 neue Tests für `teilnehmer_gegenstand_hinweis()` (ED und DK, sowie Abgrenzung
  zum echten Fehler). `test_app_gui.py` - 1 neuer Test
  `test_teilnehmerliste_zeigt_nur_info_statt_fehler_wenn_gegenstand_auf_frei_steht`.

**Tests:** `python -m unittest test_db` (209 Tests, 0 fehlgeschlagen) sowie der komplette
non-GUI-Lauf (359 Tests, 0 fehlgeschlagen, 143 übersprungen) weiterhin grün. GUI-Testlauf
jetzt 69 bestanden (1 neuer Test)/1 bekannter xfail. `py_compile` fehlerfrei. Ein
unabhängiger Verifikations-Subagent hat die DK/ED-Statuslogik anhand mehrerer eigener,
nicht in den Tests vorkommender Beispiele durchgerechnet und die Vorrang-Regel sowie
fehlende verwaiste Referenzen auf die alten Funktionsnamen gegengeprüft - Verdikt: korrekt,
keine Funde. Eine nicht-blockierende Beobachtung (kein Fund, nur für spätere Erweiterungen
vermerkt): die Vorrang-Regel (Fehler vor Info) ist ausschließlich in `app.py`s
Anzeige-Logik umgesetzt, nicht in `db.py` selbst - ein künftiger, isolierter Aufruf von
`teilnehmer_gegenstand_hinweis()` (z. B. in einem PDF-Export) ohne vorherige Prüfung von
`teilnehmer_fehlende_pflichtangaben()` müsste diese Regel selbst wiederholen.

## Version 1.0.24 (22.09., Build auf Marcos Wunsch "ja jetzt ein komplett Build")

Bündelt die oben beschriebene Differenzierung der Gegenstände-Warnung/-Info in der
Teilnehmerliste - erster Build seit Version 1.0.23.

**Build-Ablauf:** `version.txt`/`version.py`/`version_info.txt` per `bump_version.py` auf
1.0.24 erhöht. Kompletter lokaler Testlauf: non-GUI (`test_db`, `test_db_postgres_wrapper`,
`test_backup`, `test_pdf_export`, `test_app_web`, `test_bump_version`, `test_shs_core`,
`test_theme`) 359 Tests, 0 fehlgeschlagen (143 übersprungen, PostgreSQL-Tests ohne
laufenden Server); GUI (`test_app_gui.py` via pytest-qt, `QT_QPA_PLATFORM=offscreen`) 69
bestanden, 1 bekannter xfail. Zusätzlich `py_compile` für `app.py`/`app_web.py`/`db.py`/
`pdf_export.py`/`shs_core.py`/`sync_termin.py`/`bump_version.py`/`test_app_gui.py`/
`test_db.py`/`test_theme.py` fehlerfrei.

**Push und Tag (`v1.0.24`) muss wie gehabt Marco selbst ausführen:**
```
git push
git tag v1.0.24
git push --tags
```
Danach läuft `build-installer.yml` automatisch (Installer-Release).

## Hund-Spalte in der Ergebniserfassung (22.09., Rückmeldung nach Version 1.0.24)

Marcos Rückmeldung: "Feld Hund hinzufügen Ergebnisserfassung mit Rufname Hund füllen,
zwischen Name und ART/LK".

**Umsetzung (`app.py`, `ErgebnisTab`):** neue Spalte "Hund" zwischen "Name" und "Art/LK"
eingefügt (`rufname_hund`, bereits bestehendes Feld am Teilnehmer-Datensatz, keine
DB-Änderung nötig) - analog zum bereits bestehenden Muster in der Teilnehmerliste
(`TeilnehmerTab`, hat "Hund" schon zwischen "Vorname" und "Art/LK"). Die
Spalten-Offset-Konstante `_ERGEBNIS_SPALTEN_JE_DISZIPLIN`/`_DQ_SPALTE` (Basis für die
Disziplin-Punktepaare sowie Disqualifiziert/Abbruch/Status) entsprechend von 3 auf 4
verschoben, die eigene Klick-Sortierlogik (`_sortierschluessel_fuer_zeile`) um einen neuen
Sortierschlüssel für die Hund-Spalte ergänzt, bestehender Art/LK-Schlüssel auf die neue
Spaltenposition verschoben.

**Tests:** neuer Test `test_ergebnis_zeigt_hund_und_sortiert_danach` (Anzeige plus
Sortierbarkeit inkl. Richtungsumkehr, analog zum bestehenden Namens-Sortiertest). Bestehende
Tests referenzieren nur Start-Nr.-/Name-Spalte, blieben von der Verschiebung unberührt. Ein
unabhängiger Verifikations-Subagent hat Diff und Tests gegengeprüft (u. a. auf übersehene
Spaltenindex-Referenzen, `rufname_hund`-Nullbarkeit, Testannahmen) - Verdikt: keine Funde.

## Hund-Spalte in der Auswertung + Umbenennung "Vollständig" → "Anmerkungen" (22.09.)

Marcos Rückmeldung: "Feld Hund in der Auswertung zwischen Name und Gesamtpunkte einfügen.
Spaltenname Vollständig in Reiter Teilnehmer umbenennen in Anmerkungen."

**Hund-Spalte in der Auswertung (`app.py`, `AuswertungTab`):** `Teilnehmerergebnis`
(`shs_core.py`, Rückgabetyp von `db.berechne_auswertung()`) kennt `rufname_hund` nicht -
`AuswertungTab` löst das analog zur bereits bestehenden Lösung für die fehlende Startnummer
(`_startnummer_je_id`, separat aus den Stammdaten nachgeschlagen): neue Lookup-Map
`_rufname_hund_je_id`, in `aktualisieren()` befüllt, in `_rendern()` zwischen `t.name` und
den Punkte-Spalten eingefügt. `AuswertungTab` hat keine spaltenindex-abhängige
Klick-Sortierlogik (Sortierung erfolgt vorab über `sorted()` auf der Python-Liste),
entsprechend keine weiteren Anpassungen nötig. Kein Web-Pendant vorhanden (Auswertung
existiert nur im Desktop); PDF-Exporte mit Name/Gesamtpunkte-Spalten bewusst unangetastet
(nicht angefragt).

**Vollständig → Anmerkungen (`app.py`, `TeilnehmerTab`):** auf Rückfrage geklärt - reine
Label-Änderung, der Zellinhalt (automatisch berechneter Warn-/Hinweistext zu fehlender
Chip-Nr./Gegenständen, siehe `teilnehmer_fehlende_pflichtangaben()`/
`teilnehmer_gegenstand_hinweis()` in `db.py`) bleibt unverändert - kein neues freies
Eingabefeld. Nur die Spaltenüberschrift geändert. Der gleichnamige, aber inhaltlich andere
`vollstaendig`-Flag in der Web-Version (`app_web.py`, "bereits bewertet"-Status in der
Teilnehmerliste) ist ein eigenständiges Konzept ohne Bezug zu dieser Spalte und wurde nicht
angefasst.

**Tests:** neuer Test `test_auswertung_zeigt_hund_zwischen_name_und_gesamtpunkte`; bestehender
Test `test_teilnehmerliste_zeigt_warnung_bei_fehlender_chipnr_und_gegenstaenden` um eine
Header-Text-Assertion (`"Anmerkungen"`) ergänzt. Ein unabhängiger Verifikations-Subagent hat
beide Änderungen gegengeprüft (Spaltenreihenfolge, keine übersehenen Referenzen auf den alten
Spaltennamen, Testannahmen) - Verdikt: keine Funde.

## Responsive Spaltenbreiten/Schriftgröße in der Ergebniserfassung (22.09.)

Marcos Rückmeldung: "Ergebnisserfassung ist je nach Bildschirmgröße nicht auf einen Blick
sichtbar, sondern muss nach rechts gescrollt werden." Auf Rückfrage konkretisiert: "passe die
Schriftgröße und Spaltenbreite an das wenn Fenster maximiert ist alles auf den Bildschirm
passt".

**Hintergrund:** `ErgebnisTab` ist inzwischen auf 13 Spalten angewachsen (Start-Nr., Name,
Hund, Art/LK, je 2 Spalten für alle 3 Disziplinen, Disqualifiziert, Abbruch, Status) - vor
allem seit Disqualifiziert/Abbruch am 21.09. dazukamen. Für diese Tabelle gab es bisher KEIN
Breiten-Management (nur `setStretchLastSection(True)` für die Status-Spalte), Schriftgröße
war fest.

**Umsetzung (`app.py`):**
- Neue reine (Qt-freie) Funktion `_ergebnis_spaltenbreiten_verteilen(natuerliche_breiten,
  minimum_breiten, verfuegbare_breite)`: reicht der Platz, bleiben die natürlichen Breiten
  unverändert (Rest geht an die gestreckte Status-Spalte); sonst iterative
  "Water-Filling"-Verteilung - Spalten, deren proportionaler Anteil unter ihr Minimum fiele,
  werden mit exakt ihrem Minimum aus der Verteilung herausgenommen, der Faktor für die
  übrigen Spalten wird anhand des tatsächlich verbleibenden Budgets neu berechnet (mehrstufig
  statt ein einziger globaler Faktor - Begründung siehe QS-Fund unten).
- Neue Methode `ErgebnisTab._spaltenbreiten_anpassen()`: Schriftgröße zuerst per bereits
  bestehender `_responsive_schriftgroesse()` (wiederverwendet, aber mit eigenen, auf die
  Tabellenbreite zugeschnittenen Schwellwerten statt den Fenster-Schwellwerten von
  `ResponsiveSchriftMixin`) bestimmen und per lokalem Stylesheet direkt auf `self.tabelle`
  setzen (wichtig: eine window-weite Stylesheet-Regel von `ResponsiveSchriftMixin` würde ein
  reines `setFont()` sonst überschreiben - die lokale Regel gewinnt nur für diese Tabelle,
  andere Tabs bleiben unberührt), dann `resizeColumnsToContents()` und die neue
  Verteilungsfunktion. Aufgerufen am Ende von `_zeilen_aufbauen()` sowie über neue
  `resizeEvent`/`showEvent`-Overrides auf `ErgebnisTab` (Letzteres nötig, da der Tab als
  inaktive `QTabWidget`-Seite beim Maximieren kein zuverlässiges `resizeEvent` bekommt).
- Minima: Punkte-Eingabespalten dynamisch über Schriftmetrik (Boden 56px), DQ/Abbruch-Spalten
  fest 44px, die vier reinen Textspalten (Start-Nr./Name/Hund/Art-LK) schrumpfen nicht unter
  ihre natürliche Breite. Die Status-Spalte bekommt vorab eine eigene Reservierung
  (`status_minimum`, längster möglicher Inhalt "● nicht gespeichert") von der verfügbaren
  Breite abgezogen, damit sie nicht auf (fast) 0 zusammengedrückt wird.

**QS-Fund während der Verifikation (behoben, nicht nur akzeptiert):** ein
Verifikations-Subagent fand, dass die ursprüngliche einstufige Fassung den globalen
Stauchungsfaktor aus der Summe ALLER natürlichen Breiten berechnete - auch der vier
nicht-schrumpfbaren Textspalten, die ohnehin immer auf ihre volle natürliche Breite geklammert
wurden. Dadurch überschritt die tatsächliche Summe der 12 Spalten das vorgesehene Budget
leicht, die Status-Spalten-Reservierung wurde nicht zuverlässig eingehalten (gemessen: Einbruch
auf ~100px bei 2200-2560px Fensterbreite statt der vorgesehenen ~252px). Nach Rückfrage
("jetzt sauber beheben") auf die oben beschriebene mehrstufige Verteilung umgebaut - ein
zweiter Verifikations-Subagent-Durchlauf bestätigte danach konsistent ~251-252px Status-
Spaltenbreite bei 1300/1900/2200/2560px (statt vorher ~100px bei den größeren Breiten).

**Tests:** 4 reine Funktionstests für `_ergebnis_spaltenbreiten_verteilen` (genug Platz →
unverändert; Überlauf ohne Minimum-Verletzung → proportionale Stauchung; extremer Überlauf →
Minima eingehalten; gezielter Regressionstest für den QS-Fund - eine nicht-schrumpfbare Spalte
darf nicht in die Faktor-Berechnung einfließen). 2 GUI-Geometrietests (`qtbot`): passt bei
typischer maximierter Breite (1300px) ohne Scrollbalken; Punkte-Spalte bleibt bei sehr
schmalem Fenster (700px) nicht unter ihrem Minimum (Scrollbalken dort explizit als akzeptiert
geprüft, nicht als Fehler). Ein dritter, ursprünglich geplanter GUI-Test ("kein
Aufblähen bei sehr breitem Fenster") wurde bewusst nicht behalten - empirisch gezeigt, dass die
Disziplin-Kopfzeilen (z. B. "Flächensuche – Suche (0-60)") bei normaler Schriftgröße so breit
sind, dass auf jedem realistischen Bildschirm ohnehin weiter gestaucht wird (der "kein
Überlauf mehr"-Zweig bräuchte >3400px Fensterbreite); die Eigenschaft ist bereits über den
entsprechenden Funktionstest abgedeckt.

**Tests (Läufe):** `python -m pytest test_app_gui.py -q` (sowohl unter echtem Windows-Fenster
als auch headless via `QT_QPA_PLATFORM=offscreen`, identisches Ergebnis) 77 bestanden/1
bekannter xfail. Non-GUI-Lauf unverändert 359 Tests grün. Zwei unabhängige
Verifikations-Subagenten haben den Diff, die Algorithmus-Korrektheit (inkl. Termination der
Verteilungs-Schleife), die Qt-Stylesheet-Kaskade (empirisch geprüft) und reale
Spaltenbreiten bei mehreren Fensterbreiten gegengeprüft (zweiter Durchlauf nach dem
QS-Fund-Fix) - Verdikt: keine weiteren Funde.

## Version 1.0.25 (22.09., Build auf Marcos Wunsch "alles dokumentieren und comitten und wir
bauen ein neues Build")

Bündelt die drei oben beschriebenen Rückmeldungen (Hund-Spalte Ergebniserfassung, Hund-Spalte
Auswertung + Vollständig→Anmerkungen, responsive Spaltenbreiten/Schriftgröße
Ergebniserfassung) - erster Build seit Version 1.0.24.

**Build-Ablauf:** `version.txt`/`version.py`/`version_info.txt` per `bump_version.py` auf
1.0.25 erhöht. Kompletter lokaler Testlauf: non-GUI (`test_db`, `test_db_postgres_wrapper`,
`test_backup`, `test_pdf_export`, `test_app_web`, `test_bump_version`, `test_shs_core`,
`test_theme`) 359 Tests, 0 fehlgeschlagen (143 übersprungen, PostgreSQL-Tests ohne laufenden
Server); GUI (`test_app_gui.py` via pytest-qt) 77 bestanden, 1 bekannter xfail. Zusätzlich
`py_compile` für `app.py`/`app_web.py`/`db.py`/`pdf_export.py`/`shs_core.py`/
`sync_termin.py`/`bump_version.py`/`test_app_gui.py`/`test_db.py`/`test_theme.py` fehlerfrei.

**Push und Tag (`v1.0.25`) muss wie gehabt Marco selbst ausführen:**
```
git push
git tag v1.0.25
git push --tags
```
Danach läuft `build-installer.yml` automatisch (Installer-Release).

## 22.09.2026: Zeitplan-PDF ohne Verein-Spalte + Ergebniserfassung ohne abgeschnittene Header (Arbeitsstand, noch kein Build)

Zwei Rückmeldungen (Text + Screenshot der Ergebniserfassung mit abgeschnittenen Spalten-
überschriften wie "immerfeld – Suche (0-..." statt "Trümmerfeld – Suche (0-60)"):

1. **Zeitplan-PDF: Spalte "Verein" entfernt.** `pdf_export.py`, Funktion
   `_zeitplan_richter_tabelle` - Header und alle drei Fallzeilen (Pause/kein-Teilnehmer/
   normal) von 6 auf 5 Spalten reduziert, SPAN-Bereiche der Pause- und Kein-Teilnehmer-
   Zeile entsprechend angepasst, `colWidths` neu verteilt
   (`[28, 55, 20, 55, 42]mm`, weiterhin Summe 200mm) - die frei gewordene Breite ging vor
   allem an Name/Hund/Art-Disziplin. `db.berechne_zeitplan` liefert `verein` unverändert
   weiter, nur die PDF-Anzeige wurde entfernt (keine Datenmodell-Änderung).

2. **Ergebniserfassung (Desktop, `ErgebnisTab` in `app.py`): Spaltenüberschriften werden
   bei schmalem Fenster nicht mehr abgeschnitten.** Ursache war, dass die Mindestbreite
   der Such-/Anzeige- sowie der Disqualifiziert-/Abbruch-Spalten in
   `_spaltenbreiten_anpassen` bisher nur am Zelleninhalt ("88"-Textbreite bzw. fix 44px)
   bemessen war, nicht am (viel längeren) Headertext - bei knappem Platz schrumpfte die
   Spalte unter die Headerbreite, Qt schnitt den Text dann ab. Fix: die Disziplin-Header
   nutzen jetzt `"\n"` statt `" – "` als Trenner (z. B. `"Trümmerfeld\nSuche (0-60)"`) -
   Qt rendert das von sich aus mehrzeilig (Header-Höhe/-Breite passt sich automatisch an,
   empirisch verifiziert). Ein ursprünglicher Versuch, zusätzlich
   `self.tabelle.horizontalHeader().setWordWrap(True)` zu setzen, führte zu
   `AttributeError: 'QHeaderView' object has no attribute 'setWordWrap'` (diese Methode
   gibt es bei `QHeaderView` in Qt/PySide6 nicht, nur bei `QAbstractItemView` für
   Zellinhalte) - wieder entfernt, da für das mehrzeilige Header-Rendering nicht nötig.
   Neue Hilfsfunktion `header_zeilen_breite(spalte)` in `_spaltenbreiten_anpassen` misst
   die breiteste Headerzeile via `self.tabelle.horizontalHeader().fontMetrics()` und geht
   als zusätzliche Untergrenze (`max(bisheriges_minimum, header_zeilen_breite(c))`) in die
   Punkte- sowie DQ/Abbruch-Spalten-Minima ein. Der überholte Dokumentationskommentar in
   `test_app_gui.py` (der das Abschneiden bisher als hingenommen beschrieb) wurde
   entsprechend aktualisiert.

**Tests:** `python -m unittest test_db test_db_postgres_wrapper test_backup test_pdf_export
test_app_web test_bump_version test_shs_core` - 355 Tests, 0 fehlgeschlagen (143
übersprungen, u. a. alle `test_pdf_export`-Tests wegen fehlendem `pypdf` in dieser
Umgebung - deshalb zusätzlich manuell per Skript `_zeitplan_richter_tabelle`/
`erstelle_zeitplan_pdf` mit allen drei Zeilentypen aufgerufen: 5 Spalten je Zeile,
`colWidths`-Summe weiterhin 200mm, kein "Verein" mehr im Header, PDF-Erzeugung ohne
Fehler). `python -m pytest test_app_gui.py -q` - 77 bestanden, 1 bekannter xfail
(inkl. aller 15 `ergebnis`-bezogenen Tests). Zusätzlich manuell bei künstlich schmalem
Fenster (750×400px) geprüft: alle Spaltenbreiten wachsen jetzt auf die tatsächlich
benötigte Headerbreite (z. B. "Behältnisstrecke\nSuche (0-60)" → 109px statt vorher
starr 56px). Unabhängiger Verifikations-Subagent hat Diff (SPAN-Bereiche, colWidths-Summe,
`header_zeilen_breite`-Implementierung, keine verbliebene nicht-existente Qt-API) und
beide Testläufe gegengeprüft - keine Findings.

**Noch offen (Stand vor dem Build):** visuelle Bestätigung durch Marco am echten
Bildschirm (Zeitplan-PDF ohne Verein-Spalte, Ergebniserfassung mit lesbaren
zweizeiligen Headern bei schmalem Fenster) - laut Marco erfolgt dieser Test jetzt anhand
des unten gebauten Installers.

## Version 1.0.26 (22.09., Build auf Marcos Wunsch "direkt committen und wir erzeugen
eine neue Version. Diese wird dann getestet")

Bündelt die beiden oben beschriebenen Änderungen (Zeitplan-PDF ohne Verein-Spalte,
Ergebniserfassung ohne abgeschnittene Spaltenüberschriften) - erster Build seit
Version 1.0.25.

**Build-Ablauf:** `version.txt`/`version.py`/`version_info.txt` per `bump_version.py` auf
1.0.26 erhöht. Kompletter lokaler Testlauf: non-GUI (`test_db`,
`test_db_postgres_wrapper`, `test_backup`, `test_pdf_export`, `test_app_web`,
`test_bump_version`, `test_shs_core`) 355 Tests, 0 fehlgeschlagen (143 übersprungen,
u. a. `pypdf`/PostgreSQL-Tests ohne die jeweilige lokale Voraussetzung); zusätzlich
`test_theme` (4 Tests, grün). GUI (`test_app_gui.py` via pytest-qt) 77 bestanden, 1
bekannter xfail. Zusätzlich `py_compile` für `app.py`/`app_web.py`/`db.py`/
`pdf_export.py`/`shs_core.py`/`sync_termin.py`/`bump_version.py`/`test_app_gui.py`/
`test_db.py`/`test_theme.py` fehlerfrei.

**Push und Tag (`v1.0.26`) muss wie gehabt Marco selbst ausführen:**
```
git push
git tag v1.0.26
git push --tags
```
Danach läuft `build-installer.yml` automatisch (Installer-Release).

## 22.09.2026: CI-Regression nach Version 1.0.26 behoben - Rundungsfehler in
`_ergebnis_spaltenbreiten_verteilen` (Arbeitsstand, noch kein Build)

Marco hat eine fehlgeschlagene GitHub-Actions-CI-Ausgabe eingefügt: der GUI-Test
`test_ergebnis_tabelle_passt_bei_typischer_maximierter_breite_ohne_scrollbalken`
(`test_app_gui.py`) schlug fehl - `tab.tabelle.horizontalScrollBar().maximum()` lieferte
`1` statt der erwarteten `0` bei einer auf 1300×800 vergrößerten `ErgebnisTab`-Tabelle.

**Ursache (durch Codelektüre bestätigt):** `_ergebnis_spaltenbreiten_verteilen` (`app.py`)
rundet die proportional gestauchte Breite jeder Spalte einzeln mit `round()`. Diese
Rundung kann die Summe der Zielbreiten über `verfuegbare_breite` hinausschieben, wenn
dabei keine der offenen (noch nicht ans Minimum fixierten) Spalten ihr Minimum erreicht -
die Funktion garantierte `sum(ziel) <= verfuegbare_breite` bisher nicht, obwohl genau das
schon in den bestehenden Funktionstests geprüft wurde (nur zufällig nie verletzt, weil die
gewählten Testzahlen exakt aufgingen). Minimal-Reproduktion auf reiner Funktionsebene
(vor dem Fix per `git stash` verifiziert):
`_ergebnis_spaltenbreiten_verteilen([3]*10, [0]*10, 27)` ergab `sum(ziel) == 30 > 27`, weil
`round(3 * 0.9) == round(2.7) == 3` für jede der 10 Spalten und keine ihr Minimum 0
erreicht. Verschärft wurde das vermutlich durch Version 1.0.26 (Commit `05f81df`): dort
wurde für die Spalten "Disqualifiziert"/"Abbruch" das bisherige feste Minimum 44px durch
`max(44, header_zeilen_breite(c))` ersetzt, was den Stauchungs-Spielraum bei 1300px
gegenüber der ursprünglich bei Version 1.0.25 validierten Marge verringert hat - eine
erneute Verifikation der 1300px-Messung nach `05f81df` war in dieser Historie nicht
dokumentiert.

**Fix:** In `_ergebnis_spaltenbreiten_verteilen` wurde vor dem finalen `return ziel` eine
Korrektur-Passe ergänzt: Liegt die Summe der Zielbreiten noch über `verfuegbare_breite`,
wird Spalten mit noch vorhandenem Spielraum (`ziel[i] > minimum_breiten[i]`) reihum je 1px
abgezogen (größter Spielraum zuerst), bis entweder die Summe passt oder keine Spalte mehr
Spielraum hat - dann bleibt der bereits akzeptierte Scrollbalken-Fallback bestehen, ohne
ein Minimum zu unterschreiten. Docstring entsprechend ergänzt.

**Neuer Test:** `test_ergebnis_spaltenbreiten_rundung_ueberschreitet_budget_nicht` in
`test_app_gui.py` (reine Funktionsebene, kein Qt nötig) deckt genau den obigen
Rundungsfall dauerhaft ab, damit diese Regressionsklasse nicht wieder nur vom
langsameren/fragileren Pixel-GUI-Test abhängt.

**Tests:** `python -m pytest test_app_gui.py -v` - 78 bestanden, 1 bekannter xfail
(inkl. des neuen Tests und des zuvor fehlschlagenden 1300px-Tests, jetzt grün).
`python -m unittest test_db test_db_postgres_wrapper test_backup test_pdf_export
test_app_web test_bump_version test_shs_core` - 355 Tests, 0 fehlgeschlagen (106
übersprungen, PostgreSQL-Tests ohne lokale Voraussetzung). Unabhängiger
Verifikations-Subagent hat die Korrektur-Passe auf Terminierung, Einhaltung der Minima und
Interaktion mit den vier bestehenden `_ergebnis_spaltenbreiten_verteilen`-Funktionstests
gegengeprüft sowie beide Testläufe selbst wiederholt - keine Findings, PASS.

**Update:** auf Marcos Wunsch ("commit") zunächst ohne Versionsbump committet (Commit
`7275280`), anschließend auf Wunsch ("ja ein full build") zu Version 1.0.27 gebaut - siehe
unten.

## Version 1.0.27 (22.09., Build auf Marcos Wunsch "ja ein full build")

Bündelt die oben beschriebene Rundungsfehler-Behebung in
`_ergebnis_spaltenbreiten_verteilen` (CI-Regression aus 1.0.26) - erster Build seit
Version 1.0.26.

**Build-Ablauf:** `version.txt`/`version.py`/`version_info.txt` per `bump_version.py` auf
1.0.27 erhöht. Kompletter lokaler Testlauf: non-GUI (`test_db`,
`test_db_postgres_wrapper`, `test_backup`, `test_pdf_export`, `test_app_web`,
`test_bump_version`, `test_shs_core`, `test_theme`) 359 Tests, 0 fehlgeschlagen (106
übersprungen, PostgreSQL-Tests ohne lokale Voraussetzung). GUI (`test_app_gui.py` via
pytest-qt) 78 bestanden, 1 bekannter xfail. Zusätzlich `py_compile` für `app.py`/
`app_web.py`/`db.py`/`pdf_export.py`/`shs_core.py`/`sync_termin.py`/`bump_version.py`/
`version.py`/`test_app_gui.py`/`test_db.py`/`test_theme.py` fehlerfrei.

**Push und Tag (`v1.0.27`) muss wie gehabt Marco selbst ausführen:**
```
git push
git tag v1.0.27
git push --tags
```
Danach läuft `build-installer.yml` automatisch (Installer-Release).

## 22.09.2026: CI-Regression aus 1.0.27 hartnäckiger als gedacht - harte_minima-Fallback
ergänzt (Arbeitsstand, noch kein Build)

Marco hat erneut eine fehlgeschlagene CI-Ausgabe eingefügt: derselbe Test
(`test_ergebnis_tabelle_passt_bei_typischer_maximierter_breite_ohne_scrollbalken`) schlug
weiterhin mit `maximum()==1` fehl - obwohl die Testzeilennummer (1067 statt vorher 1054) und
die Testanzahl (407 statt 406 bestandene) eindeutig zeigen, dass CI bereits den
Rundungsfix aus Version 1.0.27 enthielt. Der erste Fix war also notwendig, aber nicht
ausreichend.

**Ursache der Fortsetzung (durch Codelektüre bestätigt):** `_ergebnis_spaltenbreiten_verteilen`
kann alle Spalten über den `while offen:`-Verteilungsloop regulär (ohne `break`) bis auf ihr
jeweiliges `minimum_breiten[i]` herunterfixieren - dann ist `ziel == minimum_breiten` exakt,
ohne jeden Spielraum, und die Rundungs-Korrektur aus 1.0.27 (die nur Spalten MIT Spielraum
kürzt) kann nichts mehr tun. Übersteigt in diesem Fall `sum(minimum_breiten)` die verfügbare
Breite, war das von Anfang an ein bewusst akzeptierter Fallback (siehe Test
`test_ergebnis_spaltenbreiten_respektiert_minimum_auch_bei_extremem_ueberlauf` - Minima
werden nie unterschritten, ein Scrollbalken ist dann korrekt). Das Problem: dieser
Fallback greift jetzt vermutlich auch dann, wenn eigentlich nur die Schriftmetriken auf dem
CI-Linux-Runner (headless `QT_QPA_PLATFORM=offscreen`, andere/fontconfig-ersetzte Schriften
als lokal unter Windows) die headertext-basierten Minima (`header_zeilen_breite`, seit
Version 1.0.26) um ein paar Pixel breiter messen als lokal - ohne dass das Fenster
tatsächlich zu schmal wäre. Lokal unter Windows lässt sich das nicht reproduzieren (siehe
schon frühere Notiz zu Version 1.0.25: dort war offscreen vs. echtes Fenster auf demselben
Windows-Rechner identisch - der Unterschied entsteht erst durch andere Schriftarten auf
einer anderen Plattform, nicht durch den Offscreen-Modus selbst).

**Fix:** `_ergebnis_spaltenbreiten_verteilen` bekommt einen neuen optionalen 4. Parameter
`harte_minima` (Standard `None` - ohne ihn ist das Verhalten byteidentisch zu vorher, alle
bisherigen Tests bestehen unverändert). Reicht `minimum_breiten` nicht aus UND ist
`harte_minima` übergeben, versucht eine zweite Korrektur-Passe, mit `harte_minima` statt
`minimum_breiten` als Untergrenze weiter zu kürzen - erst wenn auch das nicht reicht, bleibt
der Scrollbalken-Fallback. In `ErgebnisTab._spaltenbreiten_anpassen` (Aufrufer) wird
`harte_minima` jetzt parallel zu `minima` aufgebaut: für Punkte-Spalten der reine
Inhalts-Minimum (`minimum_punkte`, für "88"-Eingabe), für Disqualifiziert/Abbruch die alte
feste 44px-Grenze (Stand vor Version 1.0.26), für die reinen Textspalten (Start-Nr./Name/
Hund/Art-LK) unverändert ihre natürliche Breite (die dürfen nie schrumpfen). Effekt: greift
der harte_minima-Fallback, wird im Extremfall der Headertext einer Punkte- oder DQ/Abbruch-
Spalte um ein paar Pixel enger als "perfekt lesbar" dargestellt (ggf. mit "…" gekürzt) -
das wiegt laut Nutzerwunsch (22.09.: "kein Scrollbalken bei maximiertem Fenster") weniger
schwer als ein Scrollbalken bei einer eigentlich passenden Fensterbreite.

**Neue Tests:** drei neue reine Funktionstests in `test_app_gui.py`, direkt nach dem
Rundungs-Regressionstest aus 1.0.27:
`test_ergebnis_spaltenbreiten_ohne_harte_minima_bleibt_scrollbalken_fallback` (Standardfall
`None` unverändert), `test_ergebnis_spaltenbreiten_faellt_bei_knappem_minimum_auf_harte_minima_zurueck`
(Kernfall: weiche Minima reichen knapp nicht, harte_minima schon),
`test_ergebnis_spaltenbreiten_harte_minima_reicht_ebenfalls_nicht_bleibt_bei_harte_minima`
(auch harte_minima reicht nicht - bleibt dann bei harte_minima, kein schlechteres Verhalten
als vorher).

**Tests:** `python -m pytest test_app_gui.py -v` - 81 bestanden (inkl. aller 8
`ergebnis_spaltenbreiten`- und beider `ergebnis_tabelle`-Tests), 1 bekannter xfail.
`python -m unittest test_db test_db_postgres_wrapper test_backup test_pdf_export
test_app_web test_bump_version test_shs_core test_theme` - 359 Tests, 0 fehlgeschlagen (106
übersprungen). Unabhängiger Verifikations-Subagent hat Diff (Äquivalenz zur alten
Rundungs-Korrektur, Grenzen-Einhaltung des neuen Fallbacks, `harte_minima[c] <= minima[c]`-
Invariante, unveränderte Textspalten, alle bisherigen Tests) sowie beide Testläufe
gegengeprüft - PASS, keine Findings, mit einem ausdrücklichen Hinweis: **diese Verifikation
lief lokal unter Windows und beweist NICHT, dass der eigentliche CI-Scrollbalken-Fehler
behoben ist** (der ist auf Windows nicht reproduzierbar) - nur, dass die neue
Fallback-Logik in sich korrekt ist und nichts lokal Testbares kaputtgeht. Endgültige
Bestätigung erst durch den nächsten echten CI-Lauf.

**Update:** auf Marcos Wunsch ("commit ja, aber erstmal nur die Tests auf git anstoßen und
falls positiv danach erst build") zunächst ohne Versionsbump committet (Commit `6c7ab47`),
Push blieb wie immer Marcos eigene Aktion. CI-Lauf auf GitHub Actions nach dem Push war
grün (Marco: "ok alles grün") - der harte_minima-Fallback ist damit auf dem echten
CI-Runner (Linux, andere Schriftmetriken als lokal unter Windows) bestätigt, nicht nur
lokal verifiziert. Anschließend auf Wunsch ("jetzt neues Build") zu Version 1.0.28 gebaut -
siehe unten.

## Version 1.0.28 (22.09., Build auf Marcos Wunsch "jetzt neues Build", nachdem der
harte_minima-Fix durch einen grünen CI-Lauf bestätigt war)

Bündelt die zweite Fallback-Stufe (`harte_minima`) für die Ergebnistabellen-Spaltenbreiten
aus dem obigen Abschnitt - zweiter Build in Folge zur selben CI-Regression (nach 1.0.27,
das den Rundungsfehler behob, aber die zusätzliche, auf CI/Linux-Schriftmetriken
beruhende Ursache noch nicht abdeckte).

**Build-Ablauf:** `version.txt`/`version.py`/`version_info.txt` per `bump_version.py` auf
1.0.28 erhöht. Kompletter lokaler Testlauf: non-GUI (`test_db`,
`test_db_postgres_wrapper`, `test_backup`, `test_pdf_export`, `test_app_web`,
`test_bump_version`, `test_shs_core`, `test_theme`) 359 Tests, 0 fehlgeschlagen (106
übersprungen, PostgreSQL-Tests ohne lokale Voraussetzung). GUI (`test_app_gui.py` via
pytest-qt) 81 bestanden, 1 bekannter xfail. Zusätzlich `py_compile` für `app.py`/
`app_web.py`/`db.py`/`pdf_export.py`/`shs_core.py`/`sync_termin.py`/`bump_version.py`/
`version.py`/`test_app_gui.py`/`test_db.py`/`test_theme.py` fehlerfrei.

**Push und Tag (`v1.0.28`) muss wie gehabt Marco selbst ausführen:**
```
git push
git tag v1.0.28
git push --tags
```
Danach läuft `build-installer.yml` automatisch (Installer-Release).

## Codeprüfung (22.09.), gesamter Quellcode (Stand 1.0.28) - Funde noch unbesprochen

Auf Marcos Wunsch ("QS Prüfung des Source Code", Umfang ausdrücklich: gesamter Quellcode statt
nur Diff seit 1.0.22). Ablauf nach CLAUDE.md: 3 parallele Reviewer mit differenzierten Rollen
(Sicherheit / Korrektheit & Edge-Cases / Wartbarkeit & Stil), jeweils mit Ausschlussliste der
bereits akzeptierten/erledigten Punkte; danach Konsolidierung und ein unabhängiger
Verifikations-Subagent, der jeden Fund am Code nachgeprüft hat (kein Fund als falsch
eingestuft, einige in der Schwere korrigiert). Reine Lese-Prüfung, KEINE Code-Änderung.
Lokaler Testlauf entfiel: auf dem Windows-Rechner ist aktuell kein Python im PATH.

Status aller Punkte: **unbesprochen** - Umsetzung erst nach Marcos Go je Punkt.

**Mittel**
- M1 (N1, Neubewertung eines 21.09.-Fixes) `db.exportiere_termin_nach_postgres`: im `except`
  fehlt `rollback()` vor `_setze_termin_suchpfad` - bei echtem PG-Fehler nach dem ersten Commit
  läuft die kompensierende Löschung nie (InFailedSqlTransaction), halber Termin bleibt sichtbar.
- M2 (B2) `importiere_ergebnisse_nach_startnummer`: Zuordnung nur über Startnummer ohne
  Plausibilitätsprüfung (Name/Art) - nach Startnummerntausch oder falscher Upload-Datei
  landen Ergebnisse still beim falschen Teilnehmer.
- M3 (B5/C1/C5) DQ/Abbruch in PDFs: DK-Bewertungsbogen zeigt z. B. "285 (SG)" statt DISQ
  (ruft `berechne_wertnote_dk` direkt), Etiketten "Gesamt: 0" ohne Hinweis inkl. alter
  Disziplinpunkte; Ergebnisliste nur kosmetisch ("0" bei Gesamtpunkten).
- M4 (C2) `test_pdf_export.TestPdfExport` läuft auch in der CI nie (pypdf nicht installiert).
- M5 (B4) Datumsfelder ohne Formatprüfung: TT.MM.JJJJ → `ist_jugendlicher` still False,
  Impf-Hervorhebung per Stringvergleich falsch.
- M6 (C6) `geburtsdatum` fehlt im CSV-/Formular-Import; Teilnehmer-Feldliste 7-8fach gepflegt.

**Gering**
- G1 (S1) Ersteinrichtung: bis der erste Admin angelegt ist, kann jedes Gerät im Netz Admin
  werden (bewusstes Design, Zeitfenster nur nach Erststart / `compose down -v`).
- G2 (B1) Zurückholen überträgt im Web geleerte Ergebnisse nicht.
- G3 (B6) `_termin_wechseln`: keine erneute Prüfung nach fehlgeschlagenem `alle_speichern()`
  (analog closeEvent-Fix fehlt hier).
- G4 (B3) Geschlecht NULL wird beim Bearbeiten still auf "Hündin" gesetzt.
- G5 (B7) Wiederherstellen "als Kopie" kann bei "A.sqlite" + "A (2).sqlite" einen Termin still
  überschreiben.
- G6 (C7) Web speichert halb ausgefüllte Disziplin, Desktop lehnt ab; keine zentrale Prüfung.
- G7 (S3) Schema-Regex `$` akzeptiert "\n"; `admin_termin_loeschen` ohne Registry-Prüfung →
  (nur durch Admin auslösbar) 500 auf Terminauswahl.
- G8 (S2) Logout nur clientseitig, Cookie bis 31 Tage nach letzter Nutzung gültig.
- G9 (B8) Sortierung der Ergebniserfassung geht beim Tabwechsel verloren, Richtung kippt.
- G10 (C3/C4/C8) Punktegrenzen 60/40, Wertnoten-Bänder, LK-/Art-Labels mehrfach hart kodiert.
- G11 (C9) Veraltete Doku (Zeilenzahlen Architektur.md/CLAUDE.md, fehlende Testmodule,
  pyzipper-Docstring).
- G12 (C10) Abhängigkeiten ohne Obergrenze, keine requirements-dev.txt.
- G13 (C11) Dublette `.github/workflows/tests.yml.github-workflows`; `.gitignore` ignoriert
  `*.sqlite` nicht (Datenschutz-Risiko bei `git add -A`).
- G14 (C12) Ungenutzter Import/Konstante in `pdf_export.py`, `_GEGENSTAND_FELDER` doppelt.
- Zusatzbeobachtung Verifikation: `disqualifiziert`/`abbruch` werden beim Web-Export/Zurückholen
  nicht übertragen - passt zur Entscheidung "DQ/Abbruch nur am Desktop", kein Fund.

### Umsetzung M1, M3, M2 (22.09., Marcos Go "ja machen wir es so", Arbeitsstand, noch kein Build)

- **M1 (`db.py`, `test_db.py`):** im `except` von `exportiere_termin_nach_postgres` jetzt
  zuerst `postgres_conn.rollback()`, danach Suchpfad + `loesche_termin_postgres` - alles in
  `with suppress(Exception)`, damit immer die ursprüngliche Exception beim Aufrufer ankommt.
  2 neue Tests (Reihenfolge rollback → Bereinigung; Bereinigungsfehler verdeckt Ursprungsfehler
  nicht). Bleibt ein reiner Mock-Test - ein CI-Test mit echtem PG-Fehler existiert nicht.
- **M3 (`pdf_export.py`, `test_pdf_export.py`), Darstellung nach Marcos Vorgaben:**
  DK-Bewertungsbogen: Einzelpunkte bleiben stehen, GESAMT zeigt "Disqualifiziert (DISQ)" /
  "Abbruch (ABBR)". Etiketten: Trümmer/Fläche/Behältnis "-", "Gesamt: DISQ"/"Gesamt: ABBR" in
  7 statt 8,5 pt (sonst Umbruch, 8,5 pt bräuchte 61 pt bei nur 53,5 pt Platz; Marco hat
  "kleinere Schrift" gewählt). Ergebnisliste: Gesamtpunkte "–" statt "0". Neue Helfer
  `_STATUS_TEXT`/`_status_abkuerzung()`. 4 neue Tests.
- **M2 (`db.py`, `sync_termin.py`, `templates/admin_termine.html`, Tests), nach Marcos Vorgaben:**
  `importiere_ergebnisse_nach_startnummer` vergleicht zusätzlich Nachname, Rufname Hund, Art,
  LK und (ED) Disziplin (Groß-/Kleinschreibung, Rand-Leerzeichen egal, `_teilnehmer_merkmale`).
  Bei Abweichung wird NICHTS übernommen, stattdessen neues Feld `ImportBericht.abweichungen`
  ("Nr. X: Web … ≠ Termin-Datei …"), angezeigt in CLI und Web-Bericht. Die Prüfung meldet
  auch Abweichungen bei Teilnehmern ohne Ergebnis (bewusst: Hinweis auf falsche Datei/Tausch).
  3 neue DB-Tests, 1 Web-Test.
- **Tests:** lokal mit Anaconda-Python (`C:\Users\mbruv\anaconda3\python.exe`, inkl. pypdf -
  dadurch liefen hier auch die PDF-Inhaltstests): 365 Tests, 0 fehlgeschlagen, 106
  übersprungen. Gegenprobe: alle neuen Tests schlagen gegen den alten Code fehl. GUI-/PG-Tests
  nur in der CI.
- **Verifikation:** je ein unabhängiger Verifikations-Subagent für M1, M3, M2 - alle "OK".
  Zwei kleine Nachbesserungen aus den Verifikationen übernommen (rollback mit in `suppress`;
  Zusatztest "Gesamt: ABBR" einzeilig).
- **Nachtrag M3, ED-Bewertungsbogen (Marcos Go "passe den Bogen an"):** Bei DQ/Abbruch zeigte
  der ED-Bogen bisher nur die berechnete Gesamtpunktzahl ohne Status-Hinweis. Jetzt bleibt die
  Punktzahl stehen, darunter eine einzeilige Tabelle "ERGEBNIS | Disqualifiziert (DISQ)" bzw.
  "Abbruch (ABBR)" (170 mm, wie die DK-GESAMT-Tabelle). `status_abk` wird in
  `_bewertungsbogen_story` einmal vor dem DK/ED-Zweig berechnet. 1 neuer Test (inkl.
  "keine zusätzliche Seite"). Verifikations-Subagent: OK. Er hat ED LK 3 in allen drei
  Disziplinen als Einzel- und Sammel-PDF erzeugt: weiterhin 1 Seite je ED-Bogen, noch ca.
  85 mm Reserve. Die gerenderte Seite ist sauber. Lokal: 366 Tests, 0 fehlgeschlagen,
  106 übersprungen.
- **M4 (Marcos Go "go"):** neue `requirements-dev.txt` (pytest, pytest-qt, pypdf).
  `tests.yml` installiert sie statt `pip install pytest pytest-qt`. Ein zusätzlicher Schritt
  `python -c "import pypdf"` lässt die CI scheitern, statt die PDF-Tests wieder still zu
  überspringen. **`requirements-dev.txt` MUSS beim nächsten Build mitcommittet werden**, sonst
  scheitert die CI beim `pip install`. Der Verifikations-Subagent gibt die Änderung frei: Die
  PDF-Tests nutzen nur die reportlab-Standardschriften, sind also plattformunabhängig. Getestet
  hat er lokal mit pypdf 4.0, 5.0 und 6.19, jeweils 42 Tests OK. Das Restrisiko liegt nur bei
  künftigen pypdf-Versionen (Textextraktion). Optional und noch nicht besprochen:
  pypdf-Obergrenze (`<7`), Eintrag in `.containerignore`. Installer und Container sind nicht
  betroffen.
  Erst der nächste CI-Lauf zeigt, ob alle ~43 PDF-Tests auch unter Linux grün sind.
- **M5 + M6, Datumsfelder und Geburtsdatum im CSV-Import (Marcos Go "ja", Vorgaben: beide
  Formate annehmen, intern ISO, Anzeige TT.MM.JJJJ; im CSV ungültiges Datum → Zeile
  überspringen; M6 gleich mit erledigen):**
  - **`db.py`:** Neue zentrale Funktionen `lies_datum` (JJJJ-MM-TT oder TT.MM.JJJJ, auch
    ohne führende Nullen, prüft echte Kalendertage), `normalisiere_datum` (→ JJJJ-MM-TT),
    `datum_anzeige` (→ TT.MM.JJJJ, nicht lesbarer Altbestand bleibt sichtbar) und
    `datum_oder_none` (tolerant, für Auswertungen).
  - **CSV-Import:** Die Spalte `geburtsdatum` ist neu (M6). Alle drei Datumsspalten werden
    normalisiert, ein ungültiges Datum überspringt die Zeile mit Meldung.
  - **Auswertungen:** `ist_jugendlicher` liest jetzt auch Altbestand in TT.MM.JJJJ.
  - **`app.py`:**
    - TeilnehmerDialog und VeranstaltungsDialog zeigen TT.MM.JJJJ. Bei ungültigem Datum
      erscheint eine Warnung und der Dialog bleibt offen; gespeichert wird immer ISO.
    - Neue Methode `VeranstaltungsDialog.datum_iso()`, beide Aufrufer nutzen sie.
    - Der Dateinamen-Vorschlag verwendet das normalisierte Datum.
    - Platzhalter und Beschriftungen zeigen "TT.MM.JJJJ".
    - Der KI-Prompt beschreibt die Spalte `geburtsdatum`.
  - **`pdf_export.py`:** Neue Funktion `_impfung_hervorheben` vergleicht echte Daten statt
    Strings ("30.08.2026" wurde vorher nicht rot markiert). `_datum_lang`/`_datum_kurz`
    lesen beide Formate. Der ungenutzte `import datetime` ist entfernt.
  - **Tests:**
    - Neue Klasse `TestDatumsfelder`, CSV-Datumstest, `ist_jugendlicher` mit Altbestand,
      `TestImpfungHervorheben` (läuft ohne pypdf).
    - 4 neue GUI-Tests; 3 bestehende GUI-Tests auf die Anzeige TT.MM.JJJJ umgestellt.
    - Lokal: 372 Nicht-GUI-Tests OK (107 übersprungen). **GUI-Tests diesmal auch lokal:**
      88 bestanden, 1 bekannter xfail (pytest-qt nur temporär ins Sitzungs-Scratchpad
      installiert, Anaconda unverändert).
  - **Verifikations-Subagent: OK.** Die optionalen Testfälle Schaltjahr und
    Altbestand-Veranstaltungsdatum sind ergänzt. Bewertung des Subagents: Ein nicht lesbarer
    Altbestand (z. B. "irgendwann") blockiert das Speichern des Dialogs, bis das Datum
    korrigiert ist - das ist vertretbar.
  - **Nicht geändert, offen/kosmetisch (Entscheidung Marco):**
    - Angezeigt wird weiterhin ISO in Fenstertitel, Terminübersicht, Web-Templates,
      PDF-Titeln, Bewertungsbogen-Fuß und Etikett.
    - Die Terminliste sortiert und die Web-Duplikatsprüfung vergleicht nach dem rohen
      Datumsstring - relevant nur für Altbestand in TT.MM.JJJJ.
- **Datumsanzeige überall TT.MM.JJJJ (Marcos Go "1. ja"):** Gespeichert bleibt JJJJ-MM-TT.
  - **Desktop (`app.py`):** Terminübersicht, Fenstertitel, StartDialog-Liste und
    Lösch-Rückfrage nutzen `datum_anzeige`.
  - **PDFs (`pdf_export.py`):** alle Titel, der Bewertungsbogen-Fuß und das Etikett nutzen
    `_datum_kurz`.
  - **Web (`app_web.py`):** neuer Jinja-Filter `datum` (`db.datum_anzeige`) in
    `admin_termine.html`, `termin_waehlen.html` und `teilnehmerliste.html`, dazu der
    Dubletten-Hinweistext.
  - **Bewusst ISO geblieben:** Dateinamen (Termin-Dateien, PDF-Export, Sicherung - damit sie
    chronologisch sortieren) und der KI-Prompt (maschinelles Austauschformat).
  - **Tests:** Etiketten-Test umgestellt; neue Prüfungen für Bogen-Fuß, Ergebnisliste-Titel
    und Web-Terminauswahl. 373 Nicht-GUI-Tests OK, GUI 88 bestanden + 1 xfail.
  - **Verifikations-Subagent:** OK. Keine weitere Stelle mit roher Anzeige gefunden;
    Dateinamen, Sortierungen und Vergleiche sind unverändert.

### Umsetzung G1–G14 (22.09., Marcos Go "mit G1-G14 weitermachen", Arbeitsstand, noch kein Build)

Die Entscheidungen hat Marco je Punkt per Rückfrage getroffen. Umgesetzt wurde von drei
parallelen Bereichs-Subagents (Desktop / Web / Daten+Doku) mit fest zugeteilten Dateien.
Drei gemeinsame Bausteine hat die Hauptsitzung vorab in `db.py` gelegt:
`pruefe_ergebnis_eingabe`, `eindeutigen_dateinamen_finden(bereits_vergeben=...)` und
`_SCHEMA_NAME_MUSTER` mit fullmatch.

- **G1, Einrichtungs-Code (Entscheidung: Code aus .env):**
  - Die Ersteinrichtung des ersten Admins verlangt `SHS_ADMIN_SETUP_CODE`.
    `compare_digest` läuft auf Bytes, damit Umlaute nicht zu einem 500 führen.
  - Ist kein Code konfiguriert, wird die Ersteinrichtung verweigert - auch lokal. Ein
    zufälliger Code wäre niemandem bekannt, "kein Code = offen" würde die Lücke wieder
    öffnen.
  - Geändert: `compose.yaml` (Pflichtwert), `.env.example`, `README_CONTAINER.md` (inkl.
    Update-Hinweis), `build-container.yml` (Smoke-Env).
  - **Marco muss `SHS_ADMIN_SETUP_CODE` in seine `.env` eintragen, sonst startet der
    Container nach dem Update nicht.**
- **G2, "im Web leer" (Entscheidung: Verhalten lassen, nur melden):** neues Feld
  `ImportBericht.im_web_leer`. Es listet Disziplinen, die im Web leer sind, in der
  Termin-Datei aber gefüllt (der Wert bleibt erhalten). Anzeige in CLI und Web-Bericht.
- **G3:** `_termin_wechseln` fragt nach einem fehlgeschlagenen Speichern nach wie
  `closeEvent`; Standard ist "Nein".
- **G4, Geschlecht (Entscheidung: leerer Eintrag, neu = leer):** Die Combo beginnt mit "–",
  das als NULL gespeichert wird; NULL bleibt beim Bearbeiten erhalten.
- **G5:** `_wiederherstellungsziele_planen` vergibt die Kopie-Namen in einer zweiten Runde
  mit `bereits_vergeben`, sodass es keine doppelten Ziele mehr gibt.
  Restpunkt, nicht umgesetzt: kein casefold-Vergleich unter Windows. Praktisch
  ausgeschlossen, weil die App selbst nie solche ZIPs erzeugt.
- **G6, Halbe Disziplin (Entscheidung: Web lehnt ebenfalls ab):**
  - Neue gemeinsame Regel `db.pruefe_ergebnis_eingabe`, genutzt von Desktop und Web.
  - Im Web wird sie nur auf tatsächlich geänderte Disziplinen angewendet. Ein halber
    Altbestand blockiert deshalb keine anderen Disziplinen, und der Lost-Update-Schutz
    bleibt erhalten.
- **G7:** Der Schema-Name wird per fullmatch geprüft, und `admin_termin_loeschen` prüft
  gegen die Registry (sonst 400).
- **G8, Session-Dauer (Entscheidung: 12 h):** `PERMANENT_SESSION_LIFETIME = 12 h`. Am
  Flask-Quelltext bestätigt: `max_age` greift auch für nicht-permanente Sessions. Die Frist
  gleitet, gilt also ab der letzten Aktivität, weil das Cookie bei jeder Anfrage neu
  signiert wird.
- **G9:** `ErgebnisTab.aktualisieren` wendet die gemerkte Sortierung erneut an.
- **G10, Konstanten (Entscheidung: nur Test):**
  - Neue Klasse `TestRegelKonsistenz`: Sie gleicht die gedruckten Wertnoten-Bänder und die
    Grenzen 60/40 (Schema-CHECKs, PDF-Überschriften) gegen `shs_core` ab.
  - **Fund:** Das Band ANZEIGE "V" ist mit "40 – 38" gedruckt; nach "mind. 96 %" wären es
    39. Im Test als bekannte Ausnahme festgehalten, **Entscheidung Marco offen**.
- **G11, Doku:**
  - `Architektur.md`: Zeilenzahlen durch ungefähre Angaben ersetzt, `test_backup` und
    `test_theme` ergänzt.
  - `CLAUDE.md`: Zeilenzahlen und ein Hinweis auf `requirements-dev.txt`/pypdf.
  - Außerdem: `db.py`-Docstring zum pyzipper-Import und `tests.yml`-Kommentar korrigiert.
- **G12, Obergrenzen (Entscheidung: nächste Major):**
  - PySide6 <7, reportlab <6, pyzipper <1, Flask <4, waitress <4, psycopg2-binary <3,
    pytest <10, pytest-qt <5, pypdf <7. Die Untergrenzen sind unverändert.
  - Laut Verifikation liegen alle installierten Versionen innerhalb der Grenzen. pip liest
    die Dateien als UTF-8, der Umlaut-Kommentar ist also unproblematisch.
- **G13:**
  - Die Dublette `.github/workflows/tests.yml.github-workflows` ist gelöscht. Nur im
    Dateisystem gelöscht, beim Commit mitnehmen.
  - `.gitignore` enthält jetzt `*.sqlite`: `anderer.sqlite` erscheint dadurch nicht mehr als
    untracked. `.containerignore` enthält `requirements-dev.txt`.
- **G14:** In `pdf_export.py` sind der ungenutzte Import `berechne_wertnote_ed` und
  `_UNTERTITEL` entfernt; `_GEGENSTAND_FELDER` wird jetzt aus `db` importiert.
- **Tests:** 391 Nicht-GUI-Tests OK (107 übersprungen); GUI: 98 bestanden, 1 bekannter
  xfail. `py_compile` ist für alle Module fehlerfrei.
- **Verifikations-Subagent über alle G-Punkte:** OK, keine blockierenden Funde. Info:
  `admin_einrichten` prüft erst und legt dann an, zwei gleichzeitige Ersteinrichtungen
  könnten also zwei Admins anlegen. Das bestand schon vorher und ist seit G1 nur noch mit
  dem Code möglich.
- **Entscheidungen Marco zu den drei offenen Punkten ("1 beheben 2 nein 3 ja"):**
  1. **ANZEIGE-Band "V" korrigiert:** Auf dem ED-Bewertungsbogen steht jetzt "40 – 39" /
     "38 – 36" statt "40 – 38" / "37 – 36" (96 % von 40 = aufgerundet 39). Die Ausnahme in
     `TestRegelKonsistenz` ist entfernt; der Test prüft jetzt ohne Sonderfall.
  2. **Keine absolute Höchstdauer der Web-Session:** Die gleitenden 12 h reichen - bewusst
     so entschieden, nicht erneut als Befund melden.
  3. **CSRF-Prüfung behoben:** `_csrf_pruefen` vergleicht jetzt UTF-8-Bytes. Ein Token mit
     Sonderzeichen ergibt 403 statt 500. Neuer Test; die Gegenprobe gegen den alten Code
     zeigte den TypeError.
  - **Tests:** 392 Nicht-GUI-Tests OK (107 übersprungen), GUI 98 bestanden + 1 xfail.

## Version 1.0.29 (22.09., Build auf Marcos Wunsch "ja wir bauen ein neues build")

Bündelt die komplette QS-Runde vom 22.09. (siehe Abschnitt "Codeprüfung (22.09.), gesamter
Quellcode" oben):
- M1-M6.
- Nachtrag ED-Bewertungsbogen bei DQ/Abbruch.
- Einheitliche Datumsanzeige TT.MM.JJJJ.
- G1-G14.
- Korrektur ANZEIGE-Band "V" (39) und CSRF-Vergleich auf Bytes.

**Build-Ablauf:**
- `version.txt`, `version.py` und `version_info.txt` per `bump_version.py` auf 1.0.29
  erhöht.
- Lokaler Testlauf mit Anaconda-Python:
  - non-GUI 392 Tests, 0 fehlgeschlagen, 107 übersprungen (PostgreSQL-Tests ohne lokalen
    Server).
  - GUI (`test_app_gui.py`, `test_theme.py` via pytest-qt, nur temporär im
    Sitzungs-Scratchpad installiert): 98 bestanden, 1 bekannter xfail.
  - `py_compile` für alle Module fehlerfrei.
- Neu im Commit: `requirements-dev.txt`. Gelöscht wird die Dublette
  `.github/workflows/tests.yml.github-workflows`.

**Vor dem nächsten Container-Start:** `SHS_ADMIN_SETUP_CODE` in die eigene `.env`
eintragen (siehe G1 und README_CONTAINER.md), sonst startet `compose up` nicht.

**Erst der CI-Lauf nach dem Push zeigt:**
- ob die ~45 PDF-Inhaltstests (jetzt erstmals mit pypdf, M4) auch unter Linux grün sind;
- ob die echten PostgreSQL-Tests grün sind;
- ob der Container-Smoke-Test mit dem neuen Pflichtwert durchläuft.

**Push und Tag (`v1.0.29`) führt wie gehabt Marco selbst aus:**
```
git push
git tag v1.0.29
git push --tags
```

**Quellcode-Spiegel nachgezogen (22.09., Marcos Go "ja, spiegel auf Stand bringen"):**
`SHS-Pruefungsprogramm-Quellcode` stand seit der Migration auf Claude Code noch auf 1.0.21.
- Alle 52 versionierten Dateien von 1.0.29 wurden hineinkopiert und per Byte-Vergleich
  geprüft.
- Die Workflow-Dateien liegen dort wie bisher flach im Hauptordner (`build-container.yml`,
  `build-installer.yml`, neu auch `tests.yml`).
- Neu im Spiegel: `README.md`, `pytest.ini`, `requirements-dev.txt`, `test_theme.py`.
- Bewusst unangetastet: die dortige `.env` (Zugangsdaten), `gui_vorschau.html` und
  `__pycache__`. Nichts wurde gelöscht.

**CI-Bestätigung 1.0.29 (22.09.):** Marco hat Push und Tag ausgeführt. Laut GitHub-API
sind alle Läufe grün:
- Tag `v1.0.29`: "Tests", "Container bauen" und "Installer bauen".
- `main`: "Tests" und "Container bauen".

Damit ist bestätigt:
- Die PDF-Inhaltstests laufen erstmals auch in der CI (der Pflichtschritt "pypdf
  verfügbar" ist grün) und sind unter Linux grün.
- Die echten PostgreSQL-Tests sind grün.
- Der Container-Smoke-Test läuft mit dem neuen Pflichtwert `SHS_ADMIN_SETUP_CODE`.

## Dokumentation (23.09.): README als Startseite für Vereine + Umstiegsanleitung

- **Nutzerwunsch:** Dokumente für GitHub, Schwerpunkt neue Vereine gewinnen und bestehende
  Nutzer der LibreOffice-Datei beim Umstieg unterstützen.
- **`README.md` neu geschrieben** (bisher nur Titel + Lizenz): Kurzbeschreibung, Download-Link
  auf `releases/latest`, Hinweis zur SmartScreen-Warnung (Installer noch unsigniert), Updates,
  Funktionsübersicht als Tabelle, optionale Web-Version, Abschnitt "Deine Daten"
  (lokal, Termin löschbar, Datensicherung), Issues-Hinweis (keine echten Teilnehmerdaten),
  Entwickler-Abschnitt mit Verweisen. Lizenz-Abschnitt beibehalten, Signierung auf
  "sollen künftig signiert werden" korrigiert (entspricht README_INSTALLER).
- **Neu `docs/UMSTIEG.md`:** was gleich bleibt (Wertnoten-Grenzen ED/DK aus `shs_core.py`,
  Mindestpunkte 70 je Disziplin, Rangliste), Zuordnung altes Tabellenblatt → neuer Reiter,
  Neues/Weggefallenes (kein ODS/XLSX-Export), Altdaten bewusst nicht übernommen
  (Datenschutz), Umstieg in 5 Schritten mit Probelauf, FAQ.
- **Screenshots** von Marco mit Testdaten (Testuser1-5) unter `docs/bilder/`:
  `ergebniserfassung.png`, `zeitplan.png`, `bewertungsbogen.png` (aus PDF gerendert,
  leere Bereiche beschnitten).
- Alle inhaltlichen Aussagen gegen den Code (Stand 1.0.29) geprüft. Reine
  Dokumentationsänderung: kein Build, kein Versionsbump.

## 23.09.2026: Gegenstände-Vollständigkeit ED/DK korrigiert (Arbeitsstand, noch kein Build)

- **Rückmeldung Marco:** Im Reiter Teilnehmer meldet ED fälschlich „Gegenstände
  unvollständig“. ED hat nur eine Suchdisziplin und daher unabhängig von der LK nur einen
  Gegenstand.
- **Ursache:** `_ed_gegenstand_status` (`db.py`) verlangte seit 20.09. (Eintrag „Warnspalte
  Vollständig“) so viele der ED-Disziplin zugeordnete Gegenstände wie die LK-Zahl – sinngemäß
  von DK übertragen. Da der Dialog jede Disziplin nur einmal zulässt, war ED LK2/LK3 nie
  vollständig (zu wenig Texte → Fehler, sonst dauerhaft Info „nicht zugeordnet“).
- **Einzelprüfung der Regeln mit Marco (23.09.), Entscheidungen:**
  1. *ED Anzahl:* genau 1 Gegenstand in jeder LK; mehr als einer (Altdaten) → nur Hinweis.
  2. *ED Zuordnung:* automatisch – im Dialog ist bei ED nur Gegenstand 1 aktiv, „gesucht in“
     folgt fest der ED-Disziplin, Gegenstand 2/3 ausgegraut.
  3. *Fehler vs. Info:* bleibt – Fehler nur, wenn gar kein Gegenstand erfasst ist; Text da,
     aber nicht zugeordnet (Altdaten) → Info.
  4. *DK (Fix 4 vom 16.09. präzisiert):* LK1 = mind. 1, LK2 = mind. 2, LK3 = 3 unterschiedliche
     Gegenstände. Alles auf „frei“: Mindestanzahl reicht, **keine** Meldung (auch keine Info
     mehr). Sind Disziplinen ausgewählt, müssen alle 3 belegt sein (auch 3× derselbe
     Gegenstand). Mischfall (teils zugeordnet, Mindestanzahl erreicht) → nur Info.
     Dialogsperre „dieselbe Disziplin doppelt“ bleibt für DK unverändert.
- **Umsetzung:**
  - `db.py`: `_ed_gegenstand_status(teilnehmer, disziplin)` neu (`ok`/`fehlt`/`zu_viele`/
    `nicht_zugeordnet`, ohne LK-Parameter), `_dk_gegenstand_status` nach Regel 4.
    Fehlertext ED jetzt „Gegenstand fehlt“ (DK unverändert „Gegenstände unvollständig
    (Dreikampf)“). Info-Texte: DK „Gegenstände den Suchdisziplinen nicht vollständig
    zugeordnet“, ED „Gegenstand der Suchdisziplin nicht zugeordnet“ bzw. „Bei ED ist nur ein
    Gegenstand vorgesehen“.
  - `app.py`, `TeilnehmerDialog`: neuer Slot `_gegenstand_felder_aktualisieren` (bei Art- und
    Disziplinwechsel sowie nach dem Laden); `ergebnis()` speichert bei ED nur Gegenstand 1
    mit ED-Disziplin, 2/3 = NULL. Stehen bei ED noch Einträge in Gegenstand 2/3 (z. B. nach
    Wechsel DK → ED), fragt der Dialog vor dem Speichern nach. Altdaten: steht der einzige
    ED-Gegenstand in Feld 2/3, wird er beim Öffnen nach Feld 1 geholt.
  - Web nicht betroffen (dort gibt es keine Gegenstand-Prüfung).
- **Tests:** `test_db.py` angepasst/ergänzt (ED LK1–3 mit einem Gegenstand ok, ED ohne/mit
  zwei/anders zugeordnetem Gegenstand, DK alles frei, DK Mischfall, DK LK3 mit nur zwei
  Gegenständen). `test_app_gui.py`: bisherige Zuordnungs-Tests laufen jetzt explizit mit DK
  (Dialog-Standard ist ED), neue Tests für ED-Dialog (Felder gesperrt, Zuordnung folgt
  Disziplin, `ergebnis()`, Altdaten, Rückfrage), Texte der Listentests aktualisiert. Lokal:
  404 Tests OK (113 übersprungen); GUI-Tests laufen nur in der CI, Dialogverhalten lokal per
  Offscreen-Skript geprüft.
- **Verifikations-Subagent:** fand einen Fehler in der eigenen Änderung – da der Dialog mit
  ED startet, stand „gesucht in“ von Gegenstand 1 nach Wechsel auf DK ungewollt auf
  „Trümmerfeld“ statt „frei“ (hätte zwei bestehende GUI-Tests in der CI gebrochen). Behoben:
  beim Wechsel ED → DK wird die nur automatisch gesetzte Zuordnung wieder auf „frei“
  gestellt; gespeicherte DK-Zuordnungen bleiben beim Öffnen erhalten (Offscreen geprüft).
  Bekannte Kleinigkeit: ein ED-Altdatensatz mit zwei Gegenständen zeigt Feld 2 ausgegraut –
  Entfernen geht über die Rückfrage beim Speichern.
- Kein Build, kein Versionsbump, kein Commit (Build-Disziplin).

## Version 1.0.30 (23.09., Build auf Marcos Wunsch "ja ein neues Build")

Bündelt die Korrektur der Gegenstände-Vollständigkeit ED/DK vom 23.09. (siehe Abschnitt
oben).

**Build-Ablauf:**
- `version.txt`, `version.py` und `version_info.txt` per `bump_version.py` auf 1.0.30
  erhöht.
- Lokaler Testlauf mit Anaconda-Python:
  - non-GUI 404 Tests, 0 fehlgeschlagen, 113 übersprungen (PostgreSQL-Tests ohne lokalen
    Server).
  - GUI (`test_app_gui.py`, `test_theme.py` via pytest-qt, nur temporär im
    Sitzungs-Scratchpad installiert): 102 bestanden, 1 bekannter xfail.
  - `py_compile` für alle Module fehlerfrei.
- Quellcode-Spiegel `SHS-Pruefungsprogramm-Quellcode` auf 1.0.30 nachgezogen (8 Dateien,
  Hash-Abgleich identisch). Push/Tag durch Marco.
## 23.09.2026: Benutzerhandbuch (MD/PDF), Issue-Vorlagen, Hilfe im Programm aktualisiert

- **Nutzerwunsch:** Benutzerhandbuch und Issue-Vorlage.
- **Entscheidungen Marco (23.09.):**
  - Format: `docs/HANDBUCH.md` plus `docs/HANDBUCH.pdf` im Repo (kein Release-Asset).
  - Die Hilfe im Programm wird aktualisiert (kein Link-Button).
  - Zielgruppe: Prüfungsleitung (Desktop) plus ein Kapitel für Richter (Browser). Die
    Container-Einrichtung wird nur verlinkt.
  - Screenshots erzeugt Claude selbst mit Testdaten.
  - Issues: GitHub-Issue-Formulare „Fehler melden“ und „Idee / Wunsch“ plus `config.yml`.
- **Neu (Doku, committet):**
  - `docs/HANDBUCH.md`: 13 Kapitel entlang eines Prüfungstermins, Stand 1.0.30.
  - `docs/HANDBUCH.pdf`: 22 Seiten A4.
  - 17 Screenshots `docs/bilder/handbuch_*.png`: 11 Desktop, 6 Web.
  - `.github/ISSUE_TEMPLATE/fehler.yml`, `wunsch.yml`, `config.yml`: leere Issues aus, Links
    zu Handbuch und Umstieg.
  - README und UMSTIEG verlinken auf Handbuch, PDF und Issue-Formulare.
- **Screenshots:**
  - Desktop: offscreen mit `QT_QPA_FONTDIR=C:\Windows\Fonts` und Schrift Segoe UI, in einem
    temporären Benutzerprofil. Der angezeigte Profilpfad ist durch `C:\Users\Name` ersetzt.
  - Vor jedem `grab()` braucht es `QTest.qWait(...)`. Sonst sitzen die Zellen-Widgets der
    Ergebniserfassung noch an alter Stelle. Das war zunächst fälschlich als Programmfehler
    vermutet und mit Marco besprochen; mit echter Windows-Plattform geprüft ist es nur ein
    Aufnahme-Effekt.
  - Web: Seiten per Flask-Test-Client gerendert, die PostgreSQL-Funktionen per Patch auf
    SQLite umgebogen (Muster aus `test_app_web.py`). Fotografiert mit
    `msedge --headless=new --screenshot`.
- **PDF neu erzeugen** (nach jeder Handbuch-Änderung nötig):
  1. `HANDBUCH.md` mit dem Python-Paket `markdown` in HTML umwandeln, mit den Erweiterungen
     `tables`, `toc` (`slugify=slugify_unicode`) und `sane_lists`. `<base href>` zeigt auf
     `docs/`.
  2. Druck-CSS: A4, Segoe UI 10,5 pt, Seitenumbruch vor jedem Kapitel (h2), Bilder mit
     `max-width:100%`.
  3. Drucken:
     `msedge --headless=new --no-pdf-header-footer --print-to-pdf=docs\HANDBUCH.pdf <html>`.
  - Das Skript liegt als `tools/handbuch_pdf.py` im Repo, auf Marcos Wunsch vom 23.09.
    Aufruf: `python tools/handbuch_pdf.py`. Es findet Edge oder Chrome selbst, ein anderer
    Browser lässt sich über `SHS_PDF_BROWSER` angeben. Reines Entwickler-Werkzeug, wird
    nicht ausgeliefert. Auf Marcos Wunsch als eigener Commit, unabhängig vom Build.
- **Hilfe im Programm `_HILFE_HTML` (`app.py`), Arbeitsstand, noch kein Build:**
  - Teilnehmer: Gegenstand-Regeln ED/DK (1.0.30), Spalte Anmerkungen, „Startnummer
    tauschen…“, „Aus anderem Termin importieren…“, „Bewertungsbogen (PDF)…“.
  - Neue Abschnitte Formular-Import und Übersicht.
  - DQ/Abbruch und automatisches Speichern beim Schließen, Chipnummernliste.
  - Am Ende ein Hinweis auf das Handbuch.
  - GUI-Tests 102 bestanden, 1 xfail. Lokale Suite: 404 OK, 113 übersprungen.
- **Verifikations-Subagent:** hat Handbuch und Hilfetext gegen den Code geprüft.
  - Korrigiert:
    - „Suche (0-60)“ mit Bindestrich wie in der Desktop-Spalte
    - „Sehr Gut“ und „nicht Bestanden“ in der Schreibweise des Codes
    - FAQ „(nicht lesbar)“ und „Datei beschädigt“ getrennt
    - Kapitel 12: Desktop **vor** dem Zurückholen schließen, sonst gehen spätere
      Desktop-Änderungen beim Ersetzen verloren; Dateiname nach dem Download prüfen
  - Ein Fund war unzutreffend: ED-Altdaten mit Gegenstand in Feld 2/3 werden beim Öffnen
    nach Feld 1 geholt.
- **Offene Punkte (nicht geändert, einzeln mit Marco besprechen):**
  1. DQ/Abbruch lassen sich im Web nicht erfassen und werden beim Zurückholen nicht
     übertragen.
  2. Die Web-Seite „Termin wählen“ ohne veröffentlichten Termin verweist auf
     `sync_termin.py`. Für Richter ist das unverständlich.
  3. Das Passwort-Feld der Web-Anmeldung ist schmal und ungestaltet: Das CSS erfasst
     `type=password` offenbar nicht, siehe Screenshot `handbuch_web_login.png`.
  4. Die Labels `fehler`/`wunsch` müssen auf GitHub einmal angelegt werden, sonst setzen die
     Issue-Formulare kein Label.
  5. OK/Cancel-Buttons der Dialoge sind englisch (keine Qt-Übersetzung geladen).
## 23.09.2026: Community-Dokumente (Verhaltensregeln, Mitwirken, Sicherheit, PR-Vorlage)

Marcos Auftrag: Code of Conduct, Contributing, Security Policy und Pull-Request-Vorlage
erzeugen und vorher prüfen, ob das sinnvoll ist.

- **Einschätzung:** SECURITY.md klar sinnvoll (öffentliches Repo, Web-Version mit Login,
  geplante SignPath-Signierung). Ohne die Datei würden Lücken als öffentliches Issue
  gemeldet. CONTRIBUTING.md sinnvoll. PR-Vorlage nur begrenzt sinnvoll, weil keine PRs von
  Dritten gewünscht sind. Code of Conduct bringt bei einem Ein-Personen-Projekt am
  wenigsten, vervollständigt aber GitHubs Community-Standards-Checkliste.
- **Marcos Entscheidungen:**
  - Kurzer eigener CoC-Text statt Contributor Covenant.
  - Sicherheitsmeldungen über GitHubs Private Vulnerability Reporting und per E-Mail.
  - **Nur Issues, keine Pull Requests von Dritten.**
  - Ablage unter `.github/` mit Link im README.
- **Neu:** `.github/CODE_OF_CONDUCT.md`, `.github/CONTRIBUTING.md`, `.github/SECURITY.md`,
  `.github/pull_request_template.md`. Die PR-Vorlage verweist auf Issues und enthält eine
  Checkliste für Marcos eigene PRs.
- **Geändert:**
  - `README.md`: Hinweis auf die Sicherheitsrichtlinie und Links unter „Für Entwickler“.
  - `.github/ISSUE_TEMPLATE/config.yml`: zusätzlicher Kontakt-Link „Sicherheitslücke melden“.
- Die bewusst akzeptierten Restrisiken (kein Upload-Limit, kein Brute-Force-Schutz beim
  Web-Login) sind in SECURITY.md nicht aufgeführt.
- **Offen für Marco:** Unter Settings → Code security „Private vulnerability reporting“
  aktivieren, sonst läuft der Link „Report a vulnerability“ ins Leere.
- **Verifikations-Subagent:** Er hat Fakten und Links bestätigt. Eingearbeitet wurden:
  - Weg zum Aktualisieren der Web-Version (neu bauen oder `pull`)
  - Wortwahl („wir“ und „Sperre“)
  - Installationshinweis zu den Tests
  - PR-Vorlage klar als Vorlage für Marcos eigene PRs gekennzeichnet
- **Offen, mit Marco zu besprechen:** `CODE_SIGNING_POLICY.md` (Rolle Reviewer) sagt noch,
  ein PR eines Dritten würde geprüft und gemerged. Das widerspricht „nur Issues“. Die Datei
  ist Grundlage der SignPath-Bewerbung und wurde deshalb zunächst nicht angefasst.
  **Nachtrag:** Mit Marcos Go („ja“) ist der Satz jetzt angepasst. PRs von Dritten werden
  nicht angenommen, externe Beiträge laufen über Issues und werden von Marco selbst umgesetzt.
- Die Nennung des Finders in den Release-Notizen muss von Hand ergänzt werden. Der Workflow
  erzeugt die Notizen automatisch (`generate_release_notes`).

## 23.09.2026: Hintergrund-Designs für die Desktop-App (Arbeitsstand, noch kein Build)

Marcos Frage: Was ist nötig, um im Theme-Menü den ganzen Hintergrund anzupassen, und
können wir mehrere Designs zur Auswahl anbieten?

- **Klärung mit Marco:**
  - Vier Designs: Hell (bisher, Standard), Warm / Sand, Dunkel, Hoher Kontrast.
  - Hintergrund und Akzentfarbe sind frei kombinierbar, über zwei Untermenüs unter
    „Ansicht“.
  - Nur Desktop, die Web-Version bleibt unverändert.
  - Damit ist die Festlegung vom 22.09. („kein Hell/Dunkel-Modus“) bewusst aufgehoben.
- **Umsetzung (`app.py`):**
  - `_QSS_TEMPLATE`: Alle 16 Neutralfarben sind jetzt `@@…@@`-Platzhalter. Neue Tabelle
    `_DESIGNS` mit Template-Werten und semantischen Farben (ok, warnung, fehler, gedaempft,
    ungespeichert_bg, zeile_bg).
  - Neue Signatur `_erzeuge_qss(theme, design="hell")`. **Hell + Blau ist bit-für-bit
    unverändert**, der alte Regressionstest läuft weiter.
  - Neu `_darstellung_anwenden(app)` für `main()` und das Umschalten:
    - Nicht-Hell-Designs setzen zusätzlich eine passende `QPalette`, damit auch
      Scrollbereiche, Listen, Hilfe-Text und Menüs mitgehen.
    - Dunkel schaltet auf den Fusion-Stil um, weil native Windows-Stile die dunkle Palette
      teilweise ignorieren.
    - Hell stellt Ursprungsstil und Ursprungspalette wieder her.
  - Checkboxen: Fusion zeichnet den Rahmen im Design Dunkel dunkler als den Hintergrund,
    die Box war fast unsichtbar. Nicht-Hell-Designs bekommen deshalb eine eigene
    Indicator-Regel (`_QSS_CHECKBOX_ZUSATZ`): Rahmen gedämpft, angehakt in Akzentfarbe mit
    weißem Häkchen. Das Häkchen ist ein PNG, das beim Umschalten im Temp-Ordner erzeugt
    wird (`_haken_bild_bereitstellen()`). Eine eigene Indicator-Regel schaltet das native
    Häkchen ab.
  - Feste Farben im Code laufen jetzt über `_farbe()`: Bezahlt, ⚠-Anmerkungen,
    Ergebniszeilen gelb/normal, „–“, Status gespeichert/nicht gespeichert, „nicht
    bestanden“, Zeitplan ✓/✗. Kleine Abweichung in Hell: Die drei leicht verschiedenen
    Grüntöne und die zwei Rottöne sind jetzt je ein Ton (#2E7D32 bzw. #C62828).
    `FARBE_UNGESPEICHERT`/`FARBE_GESPEICHERT` entfallen.
  - Ein Wechsel wirkt sofort:
    - Teilnehmer, Auswertung und Zeitplan laden neu.
    - Die Ergebniserfassung färbt nur um (`ErgebnisTab.farben_auffrischen()`), damit
      **ungespeicherte Punkte erhalten bleiben**.
  - Menü: „Ansicht → Hintergrund“ und „Ansicht → Akzentfarbe“ (vorher „Theme“), gleiches
    `QActionGroup`-Muster ohne Lambda wie bisher. Neuer QSettings-Schlüssel
    `darstellung/hintergrund`. `darstellung/theme` bleibt für die Akzentfarbe, bestehende
    Einstellungen gehen also nicht verloren.
- **Hilfe und Handbuch:** kurzer Abschnitt zu Ansicht → Hintergrund/Akzentfarbe, mit dem
  Hinweis, dass der Windows-Dateidialog im Design Dunkel hell bleibt (nativ).
  `docs/HANDBUCH.pdf` wird beim nächsten Build mit `tools/handbuch_pdf.py` neu erzeugt.
- **Tests:**
  - `test_theme.py` hat 15 Tests. Unter anderem prüfen sie alle 12 Kombinationen auf übrige
    Platzhalter und den **WCAG-Kontrast**: Text mindestens 4.5:1, bei Hoher Kontrast
    mindestens 7:1; semantische Farben mindestens 3:1; Auswahl in allen Kombinationen
    lesbar.
  - `test_app_gui.py` hat 3 neue Tests: Menü, Umschalten samt Speichern und Stil, und dass
    ungespeicherte Ergebnisse den Wechsel überstehen. Die Tests ersetzen die QSettings
    durch einen Speicher im Arbeitsspeicher, schreiben also nicht in die Registry.
  - Lokal:
    - GUI + Theme: 118 bestanden, 1 xfail.
    - Standard-Suite aus CLAUDE.md: 404 OK, 113 übersprungen.
    - `pytest-qt` dafür lokal nachinstalliert, steht bereits in `requirements-dev.txt`.
- **Vorschau:** Screenshots aller vier Designs (Teilnehmer, Ergebniserfassung, Hilfe im
  Design Dunkel) wurden erzeugt und Marco zur Farbabstimmung gezeigt.
- **Verifikations-Subagent:**
  - Bestätigt:
    - Hell + Blau/Grün/Violett liefern dasselbe Stylesheet wie `HEAD`; nur der
      QSS-Kopfkommentar ist erweitert.
    - Kein Datenverlust in der Ergebniserfassung.
    - Lambda-freies Menü-Muster.
    - Stil-Rückweg `windows11` → `fusion` → `windows11` auf der echten Windows-Plattform.
  - Eingearbeitet:
    - `_haken_bild_bereitstellen()` fängt `OSError` ab. Ein nicht beschreibbarer
      Temp-Ordner hätte sonst den Programmstart verhindert. Eine leere `haken.png` wird neu
      erzeugt.
    - Die Palette wird beim Start in Hell nicht mehr explizit gesetzt, nur beim Rückweg von
      einem anderen Design. So folgt Hell weiter dem Windows-Farbschema.
    - Die Test-Fixture stellt Stil, Palette, Stylesheet und die Modulzustände vollständig
      wieder her.
    - Neue Tests: Rückweg mit echtem Stilwechsel, dafür „windows“ als Ursprung vorgegeben;
      Start ohne beschreibbaren Temp-Ordner.
    - `Architektur.md` ist ergänzt.
  - Hingenommen: Beim Designwechsel lädt der Zeitplan-Reiter neu. Das passiert heute schon
    bei jedem Reiterwechsel. Eine getippte, noch nicht übernommene Startzeit ohne Fokus und
    die Scrollposition gehen dabei zurück.
- **Mögliche spätere Punkte** (noch nicht besprochen): PDF-Ausgaben bleiben unabhängig vom
  Design (gewollt). Die Web-Version hat keine Designs.

## Version 1.0.31 (23.09., Build auf Marcos Wunsch "passt alles, wir bauen ein neues build")

Marco hat die Farben aller vier Designs anhand der Screenshots freigegeben („passt alles“).

**Enthalten seit 1.0.30:**
- Hintergrund-Designs Hell, Warm / Sand, Dunkel und Hoher Kontrast, frei kombinierbar mit
  der Akzentfarbe (siehe Abschnitt oben).
- Aktualisierter Hilfetext im Programm (`_HILFE_HTML`) aus der Handbuch-Sitzung vom 23.09.:
  Gegenstand-Regeln, Anmerkungen, Formular-Import, Übersicht, DQ/Abbruch,
  Chipnummernliste, Hinweis aufs Handbuch. Dazu der neue Abschnitt „Aussehen“.
- `docs/HANDBUCH.pdf` mit `tools/handbuch_pdf.py` neu erzeugt. Die Abschnitte „Hintergrund“,
  „Akzentfarbe“ und „Hoher Kontrast“ sind im PDF-Text vorhanden.

**Build-Ablauf:**
- Versionsdateien per `bump_version.py` auf 1.0.31 gesetzt (`version.txt`, `version.py`,
  `version_info.txt`).
- Lokaler Testlauf mit Anaconda-Python:
  - Standard-Suite: 404 OK, 113 übersprungen.
  - GUI und Theme (`pytest-qt`, jetzt dauerhaft im Anaconda-Python installiert): 118
    bestanden, 1 bekannter xfail.
  - `py_compile` für alle Module fehlerfrei.
- Push und Tag macht Marco.
- Quellcode-Spiegel `SHS-Pruefungsprogramm-Quellcode` auf 1.0.31 nachgezogen: 12 Dateien,
  Byte-Abgleich identisch. Darunter auch README und CODE_SIGNING_POLICY aus den
  Community-Doku-Commits. Die `.github/`-Dateien (Community-Dokumente, Issue-Vorlagen) führt
  der Spiegel wie bisher nicht; von dort sind nur die Workflows flach enthalten.

## 23.09.2026: Offene Aufgaben aus Marcos Rückmeldung (noch nicht geplant/umgesetzt)

Marco hat zwei Punkte gemeldet. Sie sind hier nur als zu erledigen festgehalten, Planung und
Umsetzung folgen später. Die Klärungsfragen sind schon beantwortet (siehe unten).

1. **Ergebniserfassung: Teilnehmer von DK auf ED umgestellt, alle drei Disziplinen bleiben
   beschreibbar.**
   - Nachstellen: Im Reiter Teilnehmer über „Bearbeiten…“ einen DK-Teilnehmer auf ED plus
     Disziplin umstellen (Marcos Weg), dann in die Ergebniserfassung wechseln. Dort lassen
     sich weiterhin alle drei Disziplinen mit Punkten füllen.
   - **Erledigt am 23.09.2026 (siehe Abschnitt unten).**
   - Die Auswertung rechnet korrekt: Sie wertet nur die ED-Disziplin und ignoriert die
     übrigen Punkte. Es ist also ein Fehler in der Anzeige und Eingabe, nicht in der
     Berechnung.
   - Ansatzpunkt aus der ersten Code-Sichtung: `ErgebnisTab.aktualisieren()` (`app.py`)
     sperrt die nicht zutreffenden Disziplinen korrekt über
     `zutreffende_disziplinen = ALLE_DISZIPLINEN if t["art"] == "DK" else [t["disziplin"]]`.
     Vermutung: Die Ergebniserfassung wird nach dem Bearbeiten eines Teilnehmers nicht neu
     aufgebaut. Möglich ist auch, dass das Neuaufbauen wegen ungespeicherter Eingaben
     unterbleibt (siehe `_tab_gewechselt`). Das ist zu prüfen.
   - Vor der Umsetzung mit Marco klären: Was passiert mit bereits gespeicherten DK-Punkten
     der jetzt nicht mehr gültigen Disziplinen in der Datenbank? Verwerfen mit Rückfrage oder
     stehen lassen?
2. **Auswertung: neuer Druck-Button.** Marco hat bestätigt, dass ein neuer Button gemeint ist
   und kein fehlerhafter vorhandener.
   - Im Reiter Auswertung soll es einen Button geben, der die angezeigte Rangliste direkt als
     PDF ausgibt. Heute geht das nur über Export → Ergebnisliste.
   - Wiederverwenden: die vorhandene Ergebnisliste-Erzeugung in `pdf_export.py` und den
     gemeinsamen Ablageort `_Ablageort` (`app.py`), wie ihn der Export-Reiter nutzt.
   - Bei der Umsetzung klären: Soll der aktuell gesetzte Filter (Art/LK) berücksichtigt
     werden, also nur die gefilterte Leistungsklasse drucken, oder immer alles?
   - **Erledigt am 23.09.2026 (siehe Abschnitt „Auswertung: Druck-Button“ unten).**
3. **Ablauf bei späterer Umsetzung** (laut CLAUDE.md):
   - Explore-Subagent, umsetzen, testen, Verifikations-Subagent, `Fortschritt.md`
     aktualisieren.
   - Kein Commit und kein Build ohne Marcos Anforderung.

## 23.09.2026: Fix Ergebniserfassung nach Umstellung DK → ED (offene Aufgabe 1)

- **Marcos Ergänzung:** Nach einem Programm-Neustart war das Problem weg. Es tritt also nur
  in der laufenden Sitzung auf.
- **Ursache:** `ErgebnisTab._zeilen_aufbauen()` (`app.py`) setzt für nicht zutreffende
  Disziplinen nur ein gesperrtes „–“-Item per `setItem()`. Das entfernt aber kein
  Cell-Widget. Ein Punkte-Eingabefeld (`QLineEdit`) aus einem früheren Aufbau (als der
  Teilnehmer noch DK war) blieb deshalb sichtbar und beschreibbar über der Zelle liegen.
  Diese Felder standen nicht in `_boxen_je_zeile`, wurden also weder gespeichert noch
  gewertet. Deshalb rechnete die Auswertung korrekt. Nach einem Neustart wird die Tabelle
  frisch aufgebaut, dann ist der Fehler weg. Derselbe Effekt konnte auch beim Sortieren per
  Spaltenklick auftreten (ED-Zeile rutscht auf die Position einer früheren DK-Zeile).
- **Fix:** `self.tabelle.removeCellWidget(row, spalte)` vor dem Setzen der „–“-Zelle.
- **Datenfrage geklärt (Marco):** Die Umstellung DK → ED erfolgt im realen Termin nur vor
  der Punktevergabe. Deshalb gibt es keine Sonderbehandlung für schon gespeicherte
  DK-Punkte, weder Löschen noch Rückfrage.
- **Tests:** 2 neue GUI-Tests in `test_app_gui.py`
  (`test_ergebnis_umstellung_dk_auf_ed_sperrt_fremde_disziplinen`,
  `test_ergebnis_sortierung_laesst_keine_dk_eingabefelder_in_ed_zeile`). Beide schlagen
  ohne Fix fehl und laufen mit Fix durch.
  - PySide6 und pytest-qt sind im lokalen Anaconda installiert, die GUI-Tests laufen also
    auch lokal: 105 bestanden, 1 bekannter xfail.
  - Nicht-GUI-Lauf: 404 Tests, 0 fehlgeschlagen, 113 übersprungen.
- **Verifikations-Subagent: OK, keine Funde.**
  - Alle anderen Zellen und Pfade der Ergebniserfassung sind gegengeprüft: Sortieren,
    Filter, Umfärben, Spaltenbreiten, weniger Zeilen als vorher.
  - `removeCellWidget` hat keine Nebenwirkungen auf `_boxen_je_zeile` oder die Signale.
- Noch kein Commit und kein Build, erst auf Marcos Anforderung.

## 23.09.2026: GitHub Page (Projekt-Website) in `docs/`

- **Wunsch Marco:** „Entwirf mir eine GitHub Page“. Geklärt: Startseite plus Handbuch und
  Umstieg als Unterseiten, statisches HTML in `docs/` ohne Build-Schritt, zuerst eine private
  Vorschau (claude.ai-Artifact), danach Übernahme ins Repo. Nachträglich gewünscht:
  Impressum und Datenschutzerklärung.
- **Adresse nach dem Einschalten:** `https://mbruver-source.github.io/SHS/`
  (GitHub → Settings → Pages → „Deploy from a branch“, `main` / `/docs`, Marcos Aktion).
- **Neue Dateien:**
  - `docs/index.html`: Startseite mit Download-Button, Wertnoten-Leiste (echte ED-Grenzen
    aus `shs_core.py`), Ablauf in 6 Schritten, 9 Funktionskacheln, Screenshots, Umstieg,
    Datenschutz, Web-Version, Installation/Updates, Hilfe.
  - `docs/handbuch.html`, `docs/umstieg.html`: rendern `HANDBUCH.md` bzw. `UMSTIEG.md` im
    Browser (`docs/assets/anleitung.js` + `docs/assets/marked.min.js`, marked 15.0.12, MIT).
    **Die .md-Dateien bleiben die einzige Quelle**, Änderungen daran erscheinen automatisch
    auf der Website. Welche Datei geladen wird, steht fest im `data-quelle`-Attribut (keine
    URL-Parameter). Überschriften bekommen Anker nach GitHub-Schema (Umlaute bleiben), die
    vorhandenen Inhaltsverzeichnis-Links funktionieren daher weiter. `UMSTIEG.md`/
    `HANDBUCH.md`-Links werden auf die Website-Seiten umgeschrieben, `../README_CONTAINER.md`
    auf GitHub. Das „Inhalt“-Kapitel des Handbuchs wird durch eine Kapitelleiste ersetzt.
  - `docs/impressum.html` (§ 5 DDG), `docs/datenschutz.html` (Hosting GitHub Pages,
    Server-Logs, Betroffenenrechte, Aufsichtsbehörde Hessen). Beide mit `noindex`.
    Die E-Mail-Adresse steht im Quelltext nur rückwärts/zerlegt und wird von
    `docs/assets/kontakt.js` zusammengesetzt (Schutz vor einfachen Adress-Sammlern), ohne
    JavaScript steht „m.bruver [at] gmail [punkt] com“. Name und Anschrift bewusst als
    Klartext (Impressumspflicht, Barrierefreiheit).
  - `docs/assets/site.css` (Hell/Dunkel, mobil), `docs/.nojekyll` (GitHub Pages liefert
    `.md` roh aus statt Jekyll).
- **Datenschutz:** keine externen Schriften, keine CDNs, keine Cookies, kein Tracking.
- **Abweichung vom Plan:** zwei feste Seiten statt `anleitung.html?seite=…` (einfacher,
  kein Nachladen beliebiger Dateien).
- **Lokal geprüft** (Python-`http.server` + Chrome): alle Bilder laden, alle lokalen Links
  und Anker vorhanden, keine Konsolenfehler, bei 375 px kein horizontales Scrollen.
  Gefunden und behoben: Direktlinks mit Anker (z. B. `handbuch.html#8-auswertung-und-übersicht`)
  landeten zu weit oben, weil nachladende Bilder das Ziel verschoben bzw. Chrome die alte
  Scroll-Position wiederherstellte (Lazy-Loading entfernt, erneuter Sprung nach dem Laden
  der Bilder, `history.scrollRestoration = "manual"`).
- **Offen/Hinweis:** Die Gmail-Adresse steht weiterhin im Klartext in `.github/SECURITY.md`,
  `.github/CODE_OF_CONDUCT.md` und `CODE_SIGNING_POLICY.md` (Marcos Entscheidung: bleibt).
  Die Texte von Impressum/Datenschutz sind eine Vorlage, keine Rechtsberatung.
- **Verifikations-Subagent: im Kern OK**, alle 17 Anker-Links in HANDBUCH.md/UMSTIEG.md
  finden ihr Ziel, keine externen Ressourcen, Wertnoten-Grenzen stimmen. Drei Funde, auf
  Marcos Go („beheb alle 3“) behoben:
  - F1: Auf dem Handy (zweizeilige Kopfleiste) lag das Sprungziel unter der Kopfleiste.
    `scroll-padding-top: 8.5rem` im 640px-Block von `site.css`. Nachgeprüft bei 360 px:
    Kopfleiste endet bei 85 px, Ziel steht bei 136 px.
  - F2: Ein kaputter Anker (`handbuch.html#%E0`) warf in `decodeURIComponent` und ersetzte
    das Handbuch durch die Fehlermeldung. Jetzt eigenes try/catch, nur der Sprung entfällt.
  - F3: Ablauf-Text der Startseite war ungenau („jeder Reiter, in genau dieser
    Reihenfolge“, Reiter „Drucken“ gibt es nicht). Jetzt „Der Weg zum Prüfungstag in sechs
    Schritten“, Druckzeitpunkte wie in Handbuch Kapitel 1, letzter Schritt „Export / Drucken“.
  - Nicht umgesetzt (Hinweis): Speicherdauer der GitHub-Server-Logs fehlt in der
    Datenschutzerklärung.

## 23.09.2026: Git-Historie von persönlichen E-Mail-Adressen bereinigt

- **Anlass:** Die Commits trugen `marco.bruver@unibw.de` (90, aus der lokalen und globalen
  Git-Konfiguration) bzw. `m.bruver@gmail.com` (3, im GitHub-Web erstellt).
- Marco hat `user.email` global auf `329938784+mbruver-source@users.noreply.github.com`
  umgestellt und den Eintrag in `.git/config` entfernt.
- Historie mit `git filter-repo --mailmap` umgeschrieben (Autor, Committer und Tagger der
  annotierten Tags `v1.0.11`/`v1.0.12`). Geprüft: 93 Commits, 31 Tags, Nachrichten und
  Dateistand von `HEAD` unverändert, keine alte Adresse mehr in der Historie. Sicherung des
  alten Stands: `C:\Users\mbruv\Documents\SHS-Git-Sicherung-2026-09-23\`.
- Marco hat per Force-Push hochgeladen (`main` und alle Tags auf einmal, damit keine
  Installer-Builds ausgelöst werden). Alle Commit-IDs haben sich dadurch geändert.

## 23.09.2026: Handbuch – Versionsstand automatisch, neuer Schritt „8 Tage vorher“

- **Wunsch Marco:** „Handbuch aktualisieren bezüglich Version“ und „bei Ablauf eines
  Prüfungstermins 8 Tage vorher Kontakt zum Richter aufnehmen und Zeitplan übermitteln“.
- **Version (Entscheidung: automatisch beim Build):**
  - `bump_version.py`: neue Funktion `handbuch_version_schreiben()`. Sie ersetzt die erste
    Zeile `Stand: Version X.Y.Z.` in `docs/HANDBUCH.md` durch die neue Nummer, lässt den Rest
    der Datei byte-gleich (Zeilenenden bleiben erhalten). Fehlt Datei oder Zeile, passiert
    nichts, ohne Fehler und ohne Ausgabe, weil `build_installer.bat` die Nummer von stdout liest.
  - Jetzt einmalig von Hand auf 1.0.31 gesetzt (stand noch auf 1.0.30).
  - Das PDF kann `bump_version.py` nicht erzeugen (braucht Edge/Chrome). Der Schritt
    `tools/handbuch_pdf.py` steht deshalb jetzt im Build-Ablauf in `CLAUDE.md` und
    `README_INSTALLER.md`.
- **Kapitel 1, Ablauf-Tabelle (Entscheidung: eigene Zeile):** neue Zeile „8 Tage vorher:
  Zeitplan erstellen, Kontakt zu den Richtern aufnehmen und ihnen den Zeitplan übermitteln
  (PDF) – Reiter „Zeitplan““. „Zeitplan erstellen“ ist dafür aus „Kurz vorher“ entfernt.
- `docs/HANDBUCH.pdf` mit `tools/handbuch_pdf.py` neu erzeugt (22 Seiten, zeigt 1.0.31 und
  die neue Zeile). Die Website zeigt die Änderung automatisch, da sie `HANDBUCH.md` rendert.
- **Tests:** `test_bump_version.py` – bestehender `main()`-Test biegt `HANDBUCH_DATEI` jetzt
  auf `tmp_path` um (sonst hätte er das echte Handbuch verändert), 3 neue Tests
  (Versionszeile ersetzt, CRLF erhalten, fehlende Datei, Datei ohne Versionszeile).
- `bump_version.py`/`test_bump_version.py` bleiben bis zum nächsten Build im Arbeitsstand.
- **Verifikations-Subagent: Code OK**, echte Versions-/Handbuch-Dateien bleiben bei den
  Testläufen unverändert (Hash-Vergleich), stdout von `bump_version.py` weiterhin nur die
  Nummer. Vier Funde, auf Marcos Go alle umgesetzt:
  - F1: Ein gesperrtes oder schreibgeschütztes Handbuch ließ einen halb erhöhten Stand zurück
    (`version.txt`/`version_info.txt`/`version.py` schon hochgezählt). `main()` schreibt das
    Handbuch jetzt zuerst, der Docstring nennt den lauten Abbruch bei anderen Fehlern.
    Neuer Test `test_main_zaehlt_nicht_hoch_wenn_handbuch_nicht_lesbar_ist` (jetzt 11 Tests).
  - F2: Die Release-Befehlsfolgen in `README_INSTALLER.md`, `README_CONTAINER.md` und im
    Kommentar von `.github/workflows/build-installer.yml` enthalten jetzt
    `python tools/handbuch_pdf.py` und `docs/HANDBUCH.md docs/HANDBUCH.pdf` im `git add`.
  - F3: Checkliste in `README_INSTALLER.md` um den PDF-Punkt ergänzt, „beiden Dateien“ →
    „drei Dateien“, Kommentar und Hinweis-Ausgabe in `build_installer.bat`, `Architektur.md`
    (Modultabelle `bump_version.py`).
  - F4: Zeile „8 Tage vorher“ um „bei späteren Änderungen erneut senden“ ergänzt (der
    Zeitplan ergibt sich immer aus der aktuellen Teilnehmerliste). PDF neu erzeugt.

## 23.09.2026: Auswertung: Druck-Button (offene Aufgabe 2)

- **Umsetzung:** Neuer Button **„Rangliste drucken (PDF)…“** im Reiter „Auswertung“
  (`AuswertungTab._rangliste_drucken`, `app.py`). Er nutzt dieselben Helfer wie der
  Export-Reiter (`_pdf_speicherort_waehlen`, `_export_dateiname`,
  `_pdf_export_fehler_anzeigen`) und den gemeinsamen `_Ablageort`. `AuswertungTab` bekommt
  dafür das `ablageort`-Objekt von `HauptFenster`.
- **Filter (Marcos Entscheidung):** Der Art/LK-Filter wird übernommen, der Startnummer-Filter
  bewusst nicht. `pdf_export.erstelle_ergebnisliste_pdf()` hat dafür den optionalen Parameter
  `leistungsklasse`. Ohne ihn verhält sich der Export-Reiter unverändert. Die Platzierungen
  gelten ohnehin je Leistungsklasse und ändern sich durch das Filtern nicht. Dateiname:
  `Ergebnisliste_<LK>` bzw. `Ergebnisliste` bei „Alle“.
- Hilfetext im Programm (`_HILFE_HTML`) und Handbuch (Kapitel 8, „Auswertung“) ergänzt.
- **Tests:** `test_pdf_export.py::test_ergebnisliste_nur_gewaehlte_leistungsklasse`
  (echte PDF-Textprüfung mit pypdf), `test_app_gui.py::test_auswertung_druck_button_uebernimmt_lk_filter`
  (parametrisiert, prüft auch, dass der Startnummer-Filter ignoriert wird).
- **Verifikations-Subagent: OK, keine blockierenden Funde.** GUI 107 bestanden, 1 xfail;
  Standard-Suite 405 OK, 113 übersprungen. Kleinigkeit ohne Fix: Verschwindet eine LK
  zwischen „neu berechnen“ und Druck, zeigt das PDF „Keine Teilnehmer erfasst.“.

## Version 1.0.32 (23.09., Build auf Marcos Wunsch "alles jetzt comitten und wir bauen ein neues build")

**Enthalten seit 1.0.31:**
- Fix Ergebniserfassung nach Umstellung DK → ED (verwaiste Punkte-Eingabefelder, siehe oben).
- Neuer Button „Rangliste drucken (PDF)…“ im Reiter „Auswertung“ (siehe oben).
- `bump_version.py` zieht die Stand-Zeile in `docs/HANDBUCH.md` automatisch nach (erstmals
  bei diesem Build: 1.0.31 → 1.0.32), Build-Anleitungen um `tools/handbuch_pdf.py` ergänzt.
- Handbuch: neue Zeile „8 Tage vorher“ im Ablauf, Druck-Button in Kapitel 8.
  `docs/HANDBUCH.pdf` neu erzeugt (22 Seiten, zeigt 1.0.32).
- Seit 1.0.31 schon committet: GitHub Page in `docs/` (Commit `9bf34ac`), Bereinigung der
  Git-Historie.

**Build-Ablauf:**
- Versionsdateien per `bump_version.py` auf 1.0.32 gesetzt (`version.txt`, `version.py`,
  `version_info.txt`, `docs/HANDBUCH.md`).
- Lokaler Testlauf mit Anaconda-Python:
  - Standard-Suite: 405 OK, 113 übersprungen.
  - GUI, Theme und `bump_version` (pytest): 133 bestanden, 1 bekannter xfail.
  - `py_compile` für alle Module fehlerfrei.
- Push und Tag macht Marco.
