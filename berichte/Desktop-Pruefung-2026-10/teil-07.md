# Desktop-Prüfung Teil 7: Datensicherung, Start und Termine

> **Enthält einen Sicherheitsbefund (Nr. 3, Verfügbarkeit).** Nach CLAUDE.md erst nach dem
> Release mit dem Fix veröffentlichen. In `Fortschritt.md`, Commits und Code-Kommentaren bis
> dahin nur allgemein beschreiben, ohne Stelle oder Angriffsweg.

- **Datum:** 14.10.2026
- **Commit:** 04881ed (Version 1.0.47; Programmcode seit 25f9572 unverändert)
- **Geprüft:**
  - `app.py`: `DatensicherungTab` (Z. 3429–3622), `HauptFenster._termin_setzen`/
    `_termin_wechseln`/`_ungespeicherte_ergebnisse_klaeren` (4118–4230), `StartDialog`
    (4259–4455), `_startdialog_schleife` und `main` (4458–4507);
  - `desktop_dialoge.py`: `SicherungErstellenDialog` (933–994), `_wiederherstellungsziele_planen`
    (997–1036);
  - `db_sicherung.py` vollständig;
  - `db.py`: `init_db`, Migrationen, `_fremde_trigger_und_views_entfernen`, `termine_ordner`,
    `liste_termine`.
- **Ablauf:**
  - `desktop-pruefer` im Prüfmodus, danach Gegenprüfung durch einen zweiten `desktop-pruefer`.
  - Beide haben mit eigenen Skripten nachgestellt (PySide6 6.11 offscreen, SQLite 3.53);
    `termine_ordner()` umgeleitet, der echte Termine-Ordner ist unverändert.
  - Tests grün: `test_backup`, `test_altversionen`, `TestTerminuebersicht` 61 OK; 19 passende
    GUI-Tests.
- **Ergebnis:**
  - 12 Befunde gemeldet, 10 bestätigt, 2 teilweise (Nr. 4, Nr. 5).
  - Gegenprüfung hat Nr. 1 von mittel auf niedrig und Nr. 7 von niedrig auf optional gestuft.
  - **1 Sicherheitsbefund (Nr. 3, niedrig, Verfügbarkeit).**

| Schweregrad | Anzahl | Befunde |
|---|---|---|
| mittel | 0 | |
| niedrig | 6 | 1, 2, 3 (Sicherheit), 4, 5, 6 |
| optional | 6 | 7, 8, 9, 10, 11, 12 |

**Stand mit Marco:** alle Befunde noch unbesprochen.

## Bestätigte Befunde

### Nr. 1 [niedrig, vorher mittel] Die Sicherung erfasst den geöffneten Termin nicht, wenn er außerhalb des Termine-Ordners liegt; der Dateiname behauptet das Gegenteil

- **Stelle:** `app.py:3476–3492` (`_dateiname_vorschlag` nimmt Datum und Verein aus
  `self.conn`), `app.py:3506` → `db_sicherung.py:161–162` (nur
  `termine_ordner().glob("*.sqlite")`); Erfolgsmeldung `app.py:3517–3522`.
- **Kategorie:** Datenintegrität.
- **Ablauf:** Termin über „Andere Termin-Datei öffnen…“ vom USB-Stick öffnen (dokumentierter Weg,
  HANDBUCH.md:159), „Sicherung erstellen…“: Vorschlag
  `SHS-Sicherung_2026-11-14_<Verein>_erstellt-….zip`, Meldung „Sicherung erstellt
  (N Termin(e))“. Der geöffnete Termin ist nicht enthalten; geht der Stick verloren, fehlt genau
  dieser Termin in der nach ihm benannten Sicherung.
- **Nebenpunkt:** Die Erkennung des geöffneten Termins beim Wiederherstellen vergleicht nur den
  Dateinamen (`app.py:3555`); bei gleichnamiger Datei im Ordner fehlt dort unnötig
  „Überschreiben“ (sichere Seite).
- **Vorschlag:** Prüfen, ob der geöffnete Termin im Termine-Ordner liegt; wenn nicht, vor dem
  Erstellen fragen („… wäre nicht in der Sicherung. Trotzdem fortfahren / Termin mitsichern?“;
  Mitsichern über zusätzlichen Pfad für `sicherung_erstellen`), sonst im Vorschlag Datum und
  Verein weglassen. Beim Nebenpunkt vollen Pfad vergleichen. GUI-Test.
- **Gegenprüfung:** bestätigt, auf niedrig gestuft: Der Hinweistext im Reiter
  (`app.py:3446–3452`) nennt den Ordner ausdrücklich, ebenso HANDBUCH.md:239–241; irreführend ist
  vor allem der Dateiname, Verlust erst bei zusätzlichem Verlust des Originals.

### Nr. 2 [niedrig] Passwortabfrage beim Wiederherstellen: Das dritte eingegebene Passwort wird nie geprüft

- **Stelle:** `app.py:3533–3550`.
- **Kategorie:** Korrektheit.
- **Ablauf (beide mit echter AES-Sicherung nachgestellt):** Eingaben „falsch1“, „falsch2“,
  richtiges Passwort. Geprüft werden nur `[None, 'falsch1', 'falsch2']`, danach „Das Passwort war
  auch beim dritten Versuch falsch. Abgebrochen.“ In einer Wiederherstellungs-Situation kann der
  Nutzer daraus schließen, die Sicherung sei unbrauchbar.
- **Vorschlag:** Schleife auf 1× ohne + 3× mit Passwort auslegen oder Eingabe und Prüfung
  zusammenfassen; unbenutztes `versuch` mit erledigen. GUI-Test mit gepatchtem
  `QInputDialog.getText` (falsch, falsch, richtig).
- **Gegenprüfung:** bestätigt, niedrig.

### Nr. 3 [niedrig, SICHERHEIT/Verfügbarkeit] Eine einzige fremde Datei im Termine-Ordner legt den Programmstart lahm

- **Stelle:** `db.py:2392–2417` (`liste_termine` fängt nur `sqlite3.DatabaseError`;
  `v["verein"]` usw. werfen `IndexError`; `SELECT COUNT(*) FROM teilnehmer` bzw.
  `SELECT * FROM veranstaltung` laufen auch auf Views); Sortierung `db.py:2418`. Aufrufer:
  `StartDialog.__init__` → `_aktualisieren` (`app.py:4334/4338`), `main` →
  `_startdialog_schleife` (`app.py:4463`), Termin-Import-Dialog.
- **Weg:** wie H-1/Q-1 eine fremde Sicherung, die der Nutzer wiederherstellt, oder eine
  hineinkopierte Datei.
- **Nachgestellt:**
  - a) `veranstaltung` nur mit Spalte `id`: `IndexError: No item with that key`; die ganze Liste
    scheitert, auch für gültige Termine; `StartDialog()` wirft im Konstruktor, also bei jedem
    Programmstart (`main` endet) und bei „Anderen Termin öffnen…“.
  - a2) (Gegenprüfung) `veranstaltung.datum` als Zahl (Tabelle ohne TEXT-Affinität): `TypeError`
    in der Sortierung, ebenso Totalausfall der Liste.
  - b) `teilnehmer` als View mit endloser rekursiver CTE: unbegrenzter Hänger im GUI-Thread,
    bevor ein Fenster erscheint. `init_db` würde die View entfernen (H-1), `liste_termine` läuft
    aber vorher und nur lesend.
- **Ist:** Ohne Dateimanager nicht zu beheben, der Nutzer erfährt nicht, welche Datei schuld ist.
- **Soll:** Eine fremde oder präparierte Datei erscheint als „(nicht lesbar)“ und blockiert nichts.
- **Vorschlag:** In `liste_termine` je Datei breit fangen (`Exception` bzw. `DatabaseError`,
  `IndexError`, `KeyError`, `TypeError`); vor den Abfragen per `sqlite_master` prüfen, dass
  `veranstaltung` und `teilnehmer` Tabellen sind; `conn.set_progress_handler(...)` mit Abbruch
  nach z. B. 10⁶ Schritten; Sortierung robust gegen Nicht-Text. Tests in `TestTerminuebersicht`.
- **Gegenprüfung:** bestätigt, niedrig (wie Q-1/S-8: untergeschobene Datei nötig, nur
  Verfügbarkeit, Abhilfe von Hand möglich). Mittel wäre vertretbar, wenn man den Hänger ohne jede
  Meldung stark gewichtet.

### Nr. 4 [niedrig, teilweise] Öffnen eines Termins ist nicht gegen Fehler abgesichert

- **Stelle:** `app.py:4499–4502` (`main`: `init_db` und `HauptFenster` ohne `try`),
  `4194–4198` (`_termin_wechseln`), `4123–4175` (`_termin_setzen`: `self.conn` wird zuerst
  gesetzt, alle Reiter entfernt, `blockSignals(True)` ohne `finally`), `4451–4455` und
  `4392–4402` (Datei ohne Prüfung übernommen).
- **Kategorie:** Fehlerbehandlung, Datenintegrität.
- **Nachgestellt:**
  - a) Nicht-SQLite-Datei mit Endung `.sqlite` über „Andere Termin-Datei öffnen…“ beim Start:
    `DatabaseError: file is not a database`, Fenster „Unerwarteter Fehler … Programm neu
    starten“, Programm endet. Beim Wechsel scheitert es vor dem Austausch, der alte Termin bleibt.
  - b) Schreibgeschützte Termin-Datei einer älteren Version: `OperationalError: attempt to write
    a readonly database` beim Öffnen; beim Start endet das Programm.
  - c) Werte außerhalb der CHECKs (per `PRAGMA ignore_check_constraints`, z. B. `art='XX'`):
    `KeyError` im Reiteraufbau (`TeilnehmerUebersichtTab`, `db.py:1396`). Danach 0 Reiter,
    Signale der Reiterleiste blockiert, `self.conn`/`self.pfad` zeigen auf den kaputten Termin,
    `alte_verbindung.close()` wird nie erreicht; die alte Datei bleibt unter Windows gesperrt
    (WinError 32 beim Löschen/Wiederherstellen), beim nächsten Wechsel wird nur die kaputte
    Verbindung geschlossen. Beim Start Absturz.
  - d) Eine fremde, gültige Nicht-SHS-Datenbank (Filter `*.sqlite`) bekommt ohne Rückfrage das
    SHS-Schema (nachgestellt: Tabelle `kunden` bleibt, fünf SHS-Tabellen kommen dazu).
- **Verworfen (Teil von d):** Dass Trigger und Views verschwinden, ist beschlossenes H-1-Verhalten
  mit Hinweis über `_fremdobjekte_melden`.
- **Soll:** Nicht öffnbare Datei ergibt verständliche Meldung („keine Termin-Datei, beschädigt
  oder schreibgeschützt“); bisheriger Termin bzw. Startdialog bleibt erhalten.
- **Vorschlag:**
  - Gemeinsame Funktion `_termin_oeffnen(pfad)` für `main` und `_termin_wechseln` mit `try` um
    `init_db` und Aufbau.
  - Vor `init_db`: Datei leer oder mit Tabelle `veranstaltung`, sonst Meldung.
  - Nach `init_db`: Schreibprobe `PRAGMA user_version = <aktueller Wert>` (erkennt Schreibschutz,
    `BEGIN IMMEDIATE` nicht). Nebenwirkung laut Gegenprüfung: schreibt bei jedem Öffnen den
    Dateikopf (Zeitstempel, Sync-Programme). Optional Plausibilitätsprüfung der Wertebereiche.
  - In `_termin_setzen` erst neue Reiter aufbauen, dann austauschen; `blockSignals` mit
    `try/finally`; alte Reiter mit `deleteLater` (Nr. 9).
  - Tests für a) bis c).
- **Bezug:** Teil 3 Nr. 1, Teil 4 Nr. 4 (Schreibschutz), Teil 1 Nr. 2.
- **Gegenprüfung:** a–c bestätigt, d teilweise; niedrig.

### Nr. 5 [niedrig] „Termin löschen“: „Ja“ ist die Vorgabe, danach ist der nächste Termin markiert

- **Stelle:** `app.py:4432–4437` (`QMessageBox.question` ohne `defaultButton`), `4441`
  (`os.remove`), `4445` (`_aktualisieren` behält die Zeile).
- **Kategorie:** Bedienung, destruktive Aktion.
- **Nachgestellt:** In der echten Box hat „Yes“ den Fokus, Enter löscht die Datei endgültig (kein
  Papierkorb, samt aller Ergebnisse). Danach ist der nächste Termin markiert, „Löschen…“ aktiv; ein
  zweites „Löschen…“ + Enter löscht ihn.
- **Vorschlag:** `QMessageBox.Yes | QMessageBox.No, QMessageBox.No`; nach `_aktualisieren`
  Auswahl leeren; optional `QFile.moveToTrash` statt `os.remove`. Test mit Enter auf der echten
  Box.
- **Verworfen (Teilpunkt):** Pfadvergleich in 4424 mit `normcase`: unter Windows ist der geöffnete
  Termin ohnehin gesperrt („Löschen fehlgeschlagen“), unter macOS ändert `normcase` nichts; wenn
  überhaupt, `os.path.samefile`.
- **Einordnung:** bestätigt und erweitert den vorgemerkten Punkt Teil 1 Nr. 3; hier gezählt.
- **Gegenprüfung:** bestätigt, niedrig.

### Nr. 6 [niedrig] Termin-Dateien mit „#“ oder „%xx“ im Pfad gelten als „nicht lesbar“; SQLite legt dabei eine Fremddatei an

- **Stelle:** `db.py:2393` (`f"file:{pfad}?mode=ro"` ohne URI-Kodierung); richtig in
  `test_altversionen.py:62` mit `.as_uri()`.
- **Kategorie:** Korrektheit.
- **Nachgestellt:**
  - `Termin #2.sqlite`: alles ab `#` gilt als Fragment, `?mode=ro` fällt weg; SQLite öffnet
    lesend/schreibend `…\Termine\Termin ` und legt dort eine neue leere Datei an. Eintrag „nicht
    lesbar“, „Öffnen“ meldet „Datei beschädigt“ (`app.py:4414–4416`).
  - `Prüfung 50%41.sqlite` wird als „50A“ gelesen, „nicht lesbar“ (keine Datei angelegt).
  - Ordner `a#b` (z. B. Windows-Benutzername mit „#“): alle Termine nicht lesbar, im Elternordner
    entsteht eine Datei `a`.
- **Wege:** eigener Name über „Durchsuchen“, wiederhergestellte Sicherung, Umbenennen im Explorer,
  Benutzername mit „#“.
- **Vorschlag:** `Path(pfad).as_uri() + "?mode=ro"` (von der Gegenprüfung als korrekt geprüft).
  Test mit `#` und `%`. Betrifft auch den Termin-Import-Dialog.
- **Gegenprüfung:** bestätigt, niedrig.

### Nr. 7 [optional, vorher niedrig] Testlücken

- Kein Test für: Passwortschleife (Nr. 2; `test_app_gui.py:3399f.` patcht `sicherung_inhalt`),
  `SicherungErstellenDialog` (Passwort leer/ungleich), `_sicherung_erstellen` in der GUI, echtes
  `_konflikt_abfragen` (3405 patcht es), `StartDialog._termin_loeschen`, `_termin_oeffnen` mit
  „nicht lesbar“, `_andere_datei_oeffnen`, angenommener `_termin_wechseln` (Attrappe in 3231
  liefert immer `Rejected`).
- `TestTerminuebersicht` ohne Fälle für Sonderzeichen (Nr. 6), fremde Tabellen/Views/Spaltentypen
  (Nr. 3) und Altdateien (laut Prüfer funktioniert `liste_termine` für alle 15 Altdateien).
- Keine Tests zu Nr. 1 und Nr. 4.
- **Gegenprüfung:** bestätigt, auf optional gestuft (wie Teil 6 Nr. 12).

### Nr. 8 [optional] Enter in der Terminliste öffnet „Neuen Termin anlegen“ statt des markierten Termins

- **Stelle:** `app.py:4282` (nur `itemDoubleClicked`, kein `activated`), `4285–4287`.
- **Nachgestellt:** Zeile markieren, Enter: `_neuer_termin` wird aufgerufen (Standardknopf).
- **Vorschlag:** `self.tabelle.activated.connect(lambda _i: self._termin_oeffnen())` und Enter in
  der Tabelle abfangen. Test mit `keyClick`.
- **Gegenprüfung:** bestätigt, optional.

### Nr. 9 [optional] Alte Reiter bleiben nach jedem Terminwechsel liegen

- **Stelle:** `app.py:4134–4136` (`removeTab` ohne `deleteLater`). Aus Teil 3 vorgemerkt, hier
  gezählt (in Teil 8 nicht erneut zählen).
- **Gemessen:** nach 3 Wechseln 4 `ErgebnisTab`-Kinder und 1087 Widgets, nach 5 Wechseln 5 und
  1385. Ein alter Reiter wirft bei `aktualisieren()` `ProgrammingError: Cannot operate on a closed
  database`. Keine Folge im Betrieb gefunden (keine Timer, keine globalen Signale); die Demo ruft
  `_termin_setzen` je Lauf zweimal auf. Bei Nr. 4c halten die alten Reiter auch die nie
  geschlossene Verbindung fest.
- **Vorschlag:** `widget = self._tabs.widget(0); self._tabs.removeTab(0); widget.deleteLater()`,
  zusammen mit Nr. 4.
- **Gegenprüfung:** bestätigt, optional.

### Nr. 10 [optional, sicherheitsnah] Sicherung: Namen mit unter Windows ungültigen Zeichen werden angeboten und scheitern technisch

- **Stelle:** `db_sicherung.py:90–113` (`_ist_sicherer_dateiname` prüft weder `: * ? " < > |`
  noch Steuerzeichen).
- **Nachgestellt:** `ab:x.sqlite` → `OSError [WinError 87]`, im Termine-Ordner bleibt eine leere
  Datei `.ab` (Alternate Data Stream); `x.sqlite:y.sqlite` hinterlässt `.x.sqlite`, die in der
  Terminliste als „(nicht lesbar)“ erscheint und in jede weitere Sicherung käme; `bad?.sqlite`
  und Steuerzeichen → `Errno 22`; `Termin #2.sqlite` landet in Nr. 6.
- **Wirkung:** kein Pfadausbruch, vorhandene Termine werden nie verändert; nur präparierte
  Sicherungen. Marcos „lassen“ vom 07.10. betraf einen anderen Grenzfall.
- **Vorschlag:** Diese Zeichen in `_ist_sicherer_dateiname` ablehnen.
- **Gegenprüfung:** bestätigt, optional.

### Nr. 11 [optional] Kleinigkeiten Datensicherung und Startdialog

- Nach erfolgreichem Wiederherstellen nur die Statuszeile (`app.py:3588–3592`); beim Erstellen
  seit U7 ein Meldungsfenster.
- Leere Passworteingabe mit OK wird als „Passwort falsch“ gemeldet und kostet einen Versuch
  (`if passwort:` in `_zip_oeffnen`; `app.py:3541–3544`).
- `sicherung_inhalt` fängt nur `PasswortFalschError` und `ValueError` (`app.py:3537–3547`);
  `OSError` (Datei entfernt) und `NotImplementedError` (Komprimierungsverfahren) landen im
  allgemeinen Fehlerfenster.
- Ein lesbarer Termin ohne Veranstaltungsdaten (z. B. Rest eines gescheiterten `_neuer_termin`)
  zeigt `['?', '', '', '0']` ohne Dateinamen (`app.py:4343`); besser `t.verein or t.dateiname`.
- **Gegenprüfung:** alle vier Teilpunkte bestätigt, optional.

### Nr. 12 [optional] Veraltete Verweise

- `desktop_dialoge.py:999`: „für db.sicherung_wiederherstellen()“, liegt in `db_sicherung`.
- `db_sicherung.py:121`: „(siehe app.py)“, aufgerufen in `desktop_dialoge.py:1033`.
- `app.py:3533`: Schleifenvariable `versuch` unbenutzt (mit Nr. 2 erledigen).
- **Gegenprüfung:** bestätigt, optional.

## Einordnung der vorgemerkten Punkte

- **`_termin_loeschen` ohne `defaultButton` (Teil 1 Nr. 3):** bestätigt, in Nr. 5 gezählt und
  erweitert.
- **`_neuer_termin` (Teil 2 Nr. 1 und 2):** am Code bestätigt (`app.py:4392–4408`), nicht neu
  gezählt. Neu: Scheitert `set_veranstaltung`, bleibt `conn` offen und eine Datei ohne
  Veranstaltungsdaten liegen (Nr. 11). „Stattdessen öffnen“ übernimmt die vorhandene Datei
  ungeprüft (Nr. 4).
- **Schreibgeschützte Datei (Teil 3 Nr. 1, Teil 4 Nr. 4):** bestätigt. Aktuelles Schema: `init_db`
  läuft durch, `BEGIN IMMEDIATE` gelingt; `PRAGMA user_version = v` scheitert mit „readonly
  database“. Ältere Version: Fehler beim Öffnen (Nr. 4b). Vorschlag in Nr. 4.
- **Fremde Dateien/Sicherungen als Weg zu Teil 6 Nr. 1 (Sicherheit):** bestätigt. Wege: „Andere
  Termin-Datei öffnen“ (ohne Prüfung), Wiederherstellen (keine Inhaltsprüfung), Kopieren von Hand.
  `init_db` entfernt nur Trigger/Views; `CREATE TABLE IF NOT EXISTS` übernimmt fremde
  Tabellendefinitionen ohne CHECK. `quick_check` (derzeit nirgends aufgerufen) meldet
  CHECK-Verstöße nur bei Spalten mit CHECK, nicht bei präparierten Tabellen oder migrierten
  `gegenstand_N_disziplin` (`db.py:483`). Hauptabhilfe bleibt das Maskieren (Teil 6 Nr. 1);
  zweite Absicherung: Plausibilitätsprüfung der Wertebereiche beim Öffnen (`art`, `stufe`,
  `disziplin`, `gegenstand_N_disziplin`, Zeitplan-Felder) plus `quick_check`, verhindert zugleich
  Nr. 4c. Denkbar: CHECK bei `ADD COLUMN` für `gegenstand_N_disziplin` mitgeben.
- **`_termin_setzen` und `removeTab` (Teil 3):** bestätigt, Nr. 9.

## Bezug auf frühere Teile, nicht neu gezählt

- `StartDialog`, `SicherungErstellenDialog` und die `QMessageBox` in `_konflikt_abfragen` bleiben
  nach jedem Aufruf als Kinder liegen (je 3 nach 3 Aufrufen). Zusätzlich steht im liegengebliebenen
  `SicherungErstellenDialog` das Sicherungspasswort bis zum Programmende im Eingabefeld (von der
  Gegenprüfung nachgestellt; der Dialog lebt wegen Nr. 9 auch nach Terminwechsel weiter). Mit
  Teil 2 Nr. 9 / Teil 6 Nr. 8 umsetzen: `deleteLater()` oder Feld nach dem Auslesen leeren.
- Sicherung und Wiederherstellung (LZMA) ohne Wartecursor, wie Teil 6 Nr. 7.

## Ohne Befund geprüft (laut Prüfer)

Wiederherstellen mit temporären Dateien und `os.replace`, zweiphasiges Ersetzen mit
`TeilweiseWiederhergestelltError`, Grenzen nach S-8, Pfadanteile und Gerätenamen; Q-1
(`casefold` an allen drei Stellen, doppelte Zielnamen); Kopienamen (G5); Konfliktdialog mit
Vorgabe und Escape „Überspringen“; abgebrochene Datei-/Passwortdialoge; atomares Erstellen samt
Aufräumen; Klartext (S-1); Sicherungsname mit Umlauten und 40-Zeichen-Grenze; kein WAL-Modus;
Rückfrage bei ungespeicherten Ergebnissen beim Wechsel (Fortschritt.md:4690f.); Datensicherung in
der Demo gesperrt; alle 15 Altversionen lesbar, Datumssortierung. Bewusst entschieden: Ausdrucke-
Ordner bleibt beim Löschen liegen (U7).

## Hinweise für spätere Teile

- **Teil 8:** Nr. 4 und Nr. 9 hängen an `_termin_setzen`, zusammen umbauen. Bei `verein = NULL`
  zeigt der Fenstertitel „None (…)“ (`app.py:4131`).
- **Teil 9:** Bei einem Fehler in `main` sagt das Fehlerfenster „Programm neu starten“, obwohl sich
  das Programm ohnehin beendet. `PermissionError` beim Erstellen der Sicherung (Ziel-ZIP in anderem
  Programm geöffnet) erscheint als technischer Text.
- **Teil 10:** Die Demo ruft `_termin_setzen` je Lauf zweimal auf und verstärkt Nr. 9.
- **Teil 1/5:** Der Termin-Import-Dialog nutzt `liste_termine`; Nr. 3 und Nr. 6 betreffen ihn
  genauso.
