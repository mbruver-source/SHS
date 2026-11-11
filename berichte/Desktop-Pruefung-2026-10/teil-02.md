# Desktop-Prüfung Teil 2: Teilnehmer-Dialog und Veranstaltung

- **Datum:** 14.10.2026
- **Commit:** 485f258 (Version 1.0.47; Programmcode seit 25f9572 unverändert)
- **Geprüft:**
  - `desktop_dialoge.py`: `TeilnehmerDialog`, `VeranstaltungsDialog`;
  - `app.py`: `VerwaltungTab`;
  - `desktop_gemeinsam.py`: `_aktualisiere_veranstaltung_feld` und die Feld- und Tabellenhelfer;
  - die dabei aufgerufenen Funktionen in `db.py` und `pdf_export._euro_text`.
- **Ablauf:**
  - `desktop-pruefer` im Prüfmodus, danach Gegenprüfung durch einen zweiten `desktop-pruefer`.
  - Beide haben mit eigenen Skripten nachgestellt (PySide6 6.11, de_DE).
  - Die passenden GUI-Tests sind grün (57 passed, 1 xfailed).
- **Ergebnis:**
  - 15 Befunde bestätigt, keiner verworfen. Kein Sicherheitsbefund.
  - Die Gegenprüfung hat Nr. 1 von mittel auf niedrig herabgestuft und Nr. 4 von niedrig auf
    optional.
  - Nr. 8 ist aufgeteilt in 8b (niedrig) und 8a (optional).

| Schweregrad | Anzahl | Befunde |
|---|---|---|
| mittel | 0 | |
| niedrig | 7 | 1, 2, 3, 5, 6, 7, 8b |
| optional | 8 | 4, 8a, 9, 10, 11, 12, 13, 14, 15 |

Die Nummern sind die des Prüfers. Weil Nr. 8 zweigeteilt ist, stehen bei „optional“ neun
Nummern für acht Befunde.

**Stand mit Marco:** alle Befunde noch unbesprochen.

**Entscheidungsfrage zusammen mit Teil 1, Befund 6:** Wie geht das Programm bei Hand-Erfassung
und beim Import aus einem anderen Termin mit Prüfungen um, die gar nicht angeboten werden
(Nr. 13)?

---

## Niedrig

### 1. Schreibfehler beim Speichern aus beiden Dialogen: Eingaben gehen verloren
- **Ort:**
  - `app.py:3417–3426`: `VerwaltungTab._veranstaltung_bearbeiten`, ohne `try`.
  - `app.py:625–629` und `645–649`: Teilnehmer neu bzw. bearbeiten, fangen nur `IntegrityError`.
- **Kategorie:** Fehlerbehandlung / Datenintegrität.
- **Ablauf:** Die Termin-Datei ist lesbar, aber nicht schreibbar, z. B. durch Schreibschutz,
  eine Sperre durch Synchronisierung oder Virenscanner, oder einen abgezogenen Stick. Man
  bearbeitet die Veranstaltung oder erfasst einen Teilnehmer und klickt OK.
- **Ist:**
  - `set_veranstaltung` bzw. `add_teilnehmer` werfen `OperationalError` („readonly database“
    bzw. nach ca. 5,6 s „database is locked“).
  - Der Dialog ist dann schon geschlossen, alle Eingaben sind weg, und es erscheint nur das
    allgemeine Fehlerfenster.
  - Beim zweiten Mal kommt gar keine Meldung mehr. Das liegt an der Fehlerfenster-Abwägung vom
    13.10., ist also kein eigener Befund.
- **Weitere ungeschützte Stellen:** Zeitplan-Start (`app.py:2897`) und Mindestabstand
  (`app.py:2706`) speichern über `_aktualisiere_veranstaltung_feld` ebenfalls ohne Schutz.
- **Soll:** Eine verständliche Meldung, und die Eingaben bleiben erhalten.
- **Vorschlag:**
  - `except sqlite3.Error` mit `_db_fehler_anzeigen` einbauen (passt zu V5).
  - Besser noch: im Dialog vor `accept()` speichern, z. B. über einen Rückruf.
  - Die Zeitplan-Stellen mit abdecken.
  - GUI-Tests mit gepatchter Funktion, die `OperationalError` wirft.
- **Hinweis für Teil 7:** `StartDialog._neuer_termin` (`app.py:4404f.`) hat dasselbe Muster.
- **Gegenprüfung:** bestätigt, herabgestuft von mittel auf niedrig. Begründung: Der Auslöser ist
  selten, und die Datenbank bleibt intakt. Bei starker Gewichtung des Eingabeverlusts ist mittel
  vertretbar.

### 2. Speicherort beim Anlegen nur auf „nicht leer“ geprüft
- **Ort:** `desktop_dialoge.py:1568–1572` (`_durchsuchen`) und `1584–1586`. Die Folgen zeigen sich
  in `app.py:4390–4405`.
- **Kategorie:** Korrektheit / Datenintegrität.
- **Ist:**
  - **a) Datei existiert schon:** Das trifft schon der automatische Vorschlag bei gleichem Verein
    und Datum.
    - `getSaveFileName` fragt „Ersetzen?“, danach fragt der StartDialog „Stattdessen öffnen?“.
      Die beiden Fragen widersprechen sich.
    - Bei „Nein“ sind alle Eingaben weg.
  - **b) Ordner fehlt:** `init_db` wirft ungefangen `OperationalError: unable to open database
    file`.
  - **c) Pfad ohne `.sqlite`:** Der Termin erscheint nie in `liste_termine` und auch nicht im
    Filter von „Andere Termin-Datei öffnen…“.
  - **d) Relativer Pfad:** Die Datei landet im Arbeitsverzeichnis.
- **Soll:** Vor `accept()` prüfen: Pfad absolut, Ordner vorhanden, Endung `.sqlite`, Datei noch
  nicht vorhanden.
- **Vorschlag:**
  - Diese Prüfungen in `_pruefen_und_akzeptieren` ergänzen.
  - Für den Vorschlag `eindeutigen_dateinamen_finden` nutzen.
  - `.sqlite` anhängen, falls die Endung fehlt.
  - `QFileDialog.DontConfirmOverwrite` setzen.
  - Tests für `_pfad_vorschlagen`, `_pfad_manuell_markieren` und `_durchsuchen` ergänzen.
- **Gegenprüfung:** bestätigt.

### 3. Zwischeneingabe im Startnummern-Bereich ergibt eine englische Python-Meldung
- **Ort:** `desktop_dialoge.py:1356` (`QIntValidator`), `1540` (`int(von)`), `1587–1592`.
- **Kategorie:** Fehlerbehandlung.
- **Ablauf:** Im Feld „von“ `20.` eingeben (gilt in de_DE als Zwischeneingabe), „bis“ = 40,
  dann OK.
- **Ist:** Es erscheint die Meldung `invalid literal for int() with base 10: '20.'`.
- **Soll:** Eine deutsche Meldung mit Prüfung und Feld, dazu der Fokus auf dem Feld.
- **Vorschlag:**
  - `hasAcceptableInput()` bzw. `try` um `int()`.
  - Die Meldung „{Prüfung}: „{text}“ ist keine Startnummer (1–999)“.
  - Ein Test mit `keyClicks`.
- **Gegenprüfung:** bestätigt.

### 5. Fenstertitel bleibt nach Änderung von Verein/Datum veraltet
- **Ort:** `app.py:4126–4132` (der Titel wird nur in `_termin_setzen` gesetzt), `app.py:3425`.
- **Kategorie:** Korrektheit (Anzeige).
- **Ist:** Nach dem Speichern in der Verwaltung zeigt der Titel bis zum Terminwechsel weiter die
  alten Werte.
- **Vorschlag:**
  - Ein Signal `veranstaltung_geaendert` oder eine Methode zur Titelaktualisierung im
    Hauptfenster.
  - Ein Test dazu.
- **Gegenprüfung:** bestätigt.

### 6. Erster Fokus liegt auf der Scrollfläche statt auf dem ersten Eingabefeld
- **Ort:** `desktop_dialoge.py:322–327`, `1439–1444`, `472`, `1575–1577`.
- **Kategorie:** Qt (Fokus).
- **Ist:**
  - Beim Öffnen von „Teilnehmer erfassen“ bzw. „Neuen Termin anlegen“ hat die `QScrollArea` den
    Fokus. Sofortiges Tippen geht ins Leere.
  - Die Pflichtfeld-Meldungen setzen anders als die Datumsprüfung keinen Fokus.
- **Soll:** Fokus auf Nachname bzw. Verein. Nach einer Pflichtfeld-Meldung steht er im ersten
  leeren Pflichtfeld.
- **Vorschlag:**
  - `inhalt_scroll.setFocusPolicy(Qt.NoFocus)` bzw. `setFocus()` am Ende von `__init__`.
  - Ein Test dazu.
- **Gegenprüfung:** bestätigt.

### 7. VeranstaltungsDialog fest 700 px hoch, ohne Begrenzung auf den Bildschirm
- **Ort:** `desktop_dialoge.py:1447`.
- **Vergleich:** Der TeilnehmerDialog begrenzt seit U3 auf 90 % der Bildschirmhöhe (Z. 340–346).
- **Kategorie:** Qt (Größe).
- **Ist:** Bei 1366×768 und 125 % Skalierung (Zielgerät aus U12) liegen OK und Abbrechen
  unterhalb des Bildschirms. Sie sind dann nur über Maximieren oder Enter erreichbar.
- **Vorschlag:** Dieselbe Begrenzung wie im TeilnehmerDialog, als gemeinsame Hilfsfunktion.
- **Gegenprüfung:** bestätigt. Abgeleitet aus dem Code, nicht am echten Gerät gemessen.

### 8b. Prüfungsgebühr geht ohne Escaping ins PDF
- **Ort:** `pdf_export.py:1217` (`Paragraph(gebuehr, …)` ohne `_p_wert`). Der Export selbst
  gehört zu Teil 6.
- **Kategorie:** Robustheit.
- **Ist:**
  - Eine Gebühr wie `12,00 <b` lässt `erstelle_pruefungsleitung_uebersicht_pdf` abbrechen
    („paraparser: syntax error“).
  - Die Oberfläche meldet den Fehler, aber das PDF entsteht nicht.
  - Das widerspricht `Architektur.md:142` („jeder Nutzertext über `_p_wert`“).
  - Die Eingabe ist unwahrscheinlich.
- **Vorschlag:**
  - `_p_wert(gebuehr)` bzw. Escaping in `_euro_text`.
  - Ein Test dazu.
- **Gegenprüfung:** bestätigt.

## Optional

### 4. DK: Zuordnung ohne Gegenstand-Text blockiert das Speichern als „doppelt vergeben“
- **Ort:** `desktop_dialoge.py:520–528` (Prüfung), `551–558` (`ergebnis()`).
- **Ablauf:**
  - Gegenstand 1 „Socke“ ist dem Trümmerfeld zugeordnet.
  - Gegenstand 3 hat keinen Text, die Zuordnung steht aber ebenfalls auf Trümmerfeld.
- **Ist:** Es erscheint die Meldung „doppelt vergeben“.
- **Widerspruch:** `db.gegenstand_fuer_disziplin` und `_dk_gegenstand_status` ignorieren
  Zuordnungen ohne Text, ebenso der ED-Zweig.
- **Vorschlag:**
  - Nur Felder mit Text zählen.
  - Bei leerem Text `None` speichern.
  - Ein Test dazu.
- **Gegenprüfung:** bestätigt. Herabgestuft von niedrig auf optional, weil keine Daten verloren
  gehen und man den Fehler über „frei“ beheben kann.

### 8a. Geleertes Feld „Prüfungsgebühr“ kommt als 12,00 zurück
- **Ort:** `desktop_dialoge.py:1278–1279`, `1293f.`.
- **Ist:**
  - Ein bewusst geleertes Feld wird als NULL gespeichert.
  - Beim nächsten Öffnen steht dort per `or "12,00"` wieder 12,00, und jedes OK speichert den
    Wert.
  - Für Alttermine ohne Gebühr ist der Startwert gewollt (`Fortschritt.md:35`).
- **Vorschlag:** Den Standardwert nur bei neuen Terminen bzw. fehlender Spalte setzen.
- **Gegenprüfung:** bestätigt.

### 9. VeranstaltungsDialog-Instanzen sammeln sich als versteckte Kinder an
- **Ort:** `desktop_dialoge.py:1373–1375` (Lambda mit `self`), `app.py:3419`.
- **Ist:**
  - Nach dreimaligem Öffnen bleiben 3 versteckte Dialoge mit zusammen 390 Widgets bestehen,
    bis zum nächsten Terminwechsel.
  - Beim TeilnehmerDialog bleibt nichts zurück.
- **Vorschlag:** `dialog.deleteLater()` nach dem Auslesen (auch in der Demo) oder ein Slot ohne
  Lambda.
- **Gegenprüfung:** bestätigt. Ein Speicherproblem ist das nur in der Theorie.

### 10. `dateiname_vorschlagen`: Umlaute werden zu „-“, keine Längengrenze, doppelte Logik
- **Ort:** `db.py:2422–2427`.
- **Vergleich:** `app.py:3484–3489` (`DatensicherungTab._dateiname_vorschlag`).
- **Ist:**
  - „SGV Köppern e.V.“ wird zu `…_SGV-K-ppern-e-V.sqlite`. Der Docstring verspricht
    `SGV-Koeppern-eV`.
  - Ein Vereinsname mit 300 Zeichen ergibt einen Dateinamen mit 318 Zeichen.
  - Die Datensicherung hat dagegen eine eigene Umschrift und eine Grenze von 40 Zeichen.
- **Vorschlag:**
  - Eine gemeinsame Hilfsfunktion in `db.py`.
  - Den Test `test_db.py:2618` schärfen.
- **Gegenprüfung:** bestätigt.

### 11. `_aktualisiere_veranstaltung_feld` listet alle Spalten von Hand auf
- **Ort:** `desktop_gemeinsam.py:45–70`.
- **Ist:**
  - Heute ist die Liste vollständig (21 Parameter).
  - Eine künftige Spalte, die hier vergessen wird, würde bei jeder Änderung von Zeitplan-Start
    oder Mindestabstand still gelöscht.
  - Kein Test sichert die Vollständigkeit ab.
- **Vorschlag:**
  - Die Parameter aus der Signatur von `set_veranstaltung` ableiten oder ein gezieltes UPDATE
    verwenden.
  - Ein Vollständigkeitstest.
- **Gegenprüfung:** bestätigt. Eingeschränkt: Der Kommentar Z. 61f. belegt nicht, dass das schon
  einmal passiert ist.

### 12. Geburtsdatum und Wurftag in der Zukunft werden ohne Hinweis angenommen
- **Ort:** `desktop_dialoge.py:476–485`, `db.py:1651–1664`.
- **Ist:** Bei einem Tippfehler wie 2085 statt 2005 ergibt sich ein negatives Alter.
  `ist_jugendlicher` liefert dann `True`, und die Person zählt in der Statistik als
  Jugendliche/r.
- **Vorschlag:** Eine Rückfrage (keine Sperre), wenn das Datum nach dem Prüfungsdatum bzw. nach
  heute liegt.
- **Gegenprüfung:** bestätigt.

### 13. TeilnehmerDialog bietet auch nicht angebotene Prüfungen ohne Hinweis an
- **Ort:** `desktop_dialoge.py:176–185`, `470–540`.
- **Ist:**
  - Die Importe (U4/K8) lehnen solche Prüfungen ab, die Erfassung von Hand nimmt sie still an.
  - Folge: Der Teilnehmer landet bei der Startnummernvergabe unter „kein Bereich“.
- **Vorschlag:** Mit Marco zusammen mit Teil 1, Befund 6 entscheiden. Denkbar ist eine
  Rückfrage „wird nicht angeboten, trotzdem speichern?“.
- **Gegenprüfung:** bestätigt als offene Frage. Es gibt dazu noch keine Entscheidung.

### 14. Veraltete Texte und Kommentare
- **Ist:**
  - `app.py:3379–3382` und `3392–3400`: Der Hinweis in der Verwaltung nennt die
    Startnummern-Bereiche nicht und nutzt gerade Anführungszeichen.
  - `desktop_dialoge.py:83`: Dort steht „Neuanlage“, der Dialog dient aber auch zum Bearbeiten.
  - `db.py:1531`: verweist auf `app.py` statt `desktop_dialoge.py`.
  - `db.py:2364`: nur halb veraltet. `VeranstaltungsDialog` wurde verschoben,
    `StartDialog._neuer_termin` liegt weiterhin in `app.py`.
- **Gegenprüfung:** bestätigt, `db.py:2364` nur teilweise.

### 15. Testlücken und Testhygiene
- **Ist:**
  - Zu den Befunden 1–8 und 11 gibt es keine Tests.
  - Pfadvorschlag und `_durchsuchen` sind ungetestet.
  - `test_neuer_termin_hinweis_bei_leerem_verband_und_meldestelle` (`test_app_gui.py:4125`)
    patcht `desktop_dialoge.termine_ordner` nicht. Der Test legt so den Ordner
    `~/SHS-Pruefungsprogramm/Termine` im echten Benutzerprofil an.
  - Erweiterung der Gegenprüfung: Die StartDialog-Tests `test_app_gui.py:2621`, `2655` und `4788`
    patchen nur `app.liste_termine`. Sie legen über `termine_ordner()` (`app.py:4306`) ebenfalls
    den echten Ordner an. Das ist harmlos, aber eine Nebenwirkung.
- **Vorschlag:**
  - `monkeypatch.setattr(..., "termine_ordner", lambda: tmp_path)` an diesen Stellen.
  - Tests zu den oben genannten Befunden.
- **Gegenprüfung:** bestätigt und erweitert.

---

## Hinweise für spätere Teile
- **Teil 6:** Die Gebühr ohne `_p_wert` (8b) dort mit aufgreifen. Weitere Nutzertexte in
  `pdf_export.py` auf `_p_wert` prüfen.
- **Teil 7:** `StartDialog._neuer_termin` fängt Schreibfehler ebenfalls nicht ab (Befund 1). Siehe
  auch Befund 2: Zusammenspiel von „Ersetzen?“ und „Stattdessen öffnen?“.

## Ohne Befund geprüft
- **Signale:** ohne Rekursion (`textEdited`, Reihenfolge der Verbindungen und Slots).
- **Vorbelegung:**
  - ED/DK-Zuordnung, Altdaten ED;
  - Geschlecht NULL;
  - Schema-CHECKs;
  - Halter-Block.
- **Startnummern:**
  - Vorschlag und Prüfung auf doppelte Nummer;
  - Bereiche: Überschneidung, halbe Angaben, Überlauf über 999, Entfernen.
- **Datum und Texte:** `normalisiere_datum`, `datum_anzeige`, `leistungsklasse_label`,
  `pruefungen_als_text`, `angebotene_pruefungen`.
- **Hilfsfunktionen:** `_NumerischSortierbaresItem`, `_zentrierte_zelle`, Klartext der Meldungen.
- **Bewusst nicht gemeldet:**
  - V4;
  - Anzahl gleich Standardgröße;
  - Automatik überschreibt Bereiche;
  - alle Punkte aus Teil 1.
