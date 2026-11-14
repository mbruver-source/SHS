# Bereich 1: Fremde Dateien in der Datenschicht (Desktop, SQLite)

Rohergebnis des Prüfers (Agenten-Typ `qs-sicherheit`), Stand HEAD e557b0f (1.0.61), 13.11.2026.
Rohergebnis vor der Gegenprüfung (siehe `Bericht.md`). Die Nachstellungs-Skripte sind nicht
veröffentlicht.

| Kennung | Schwere | Kurzfassung |
|---|---|---|
| D-1 | mittel | Spaltennamen einer fremden Datei landen im SQL von `teilnehmer_wiederherstellen` und überschreiben Ergebnisse |
| D-2 | mittel | Präpariertes Journal lässt SQLite eine fremde Datei löschen (mit SQLite 3.46.1, nicht mit 3.53.4) |
| D-3 | gering | S-8 begrenzt nur die angegebene Größe, entpackt wird trotzdem der ganze Datenstrom |
| D-4 | Hinweis | Gerätenamen mit Hochziffern, `CONIN$`/`CONOUT$` und Punkt/Leerzeichen am Ende gehen durch den Filter |
| D-5 | mittel | Automatische Kopien werden nur über den Dateistamm zugeordnet |
| D-6 | gering | Werte aus Kopien ohne Typprüfung, der eigene Termin lässt sich danach nicht mehr öffnen |
| D-7 | gering | Fremdschlüssel-Aktionen fremder Zusatzspalten überleben `init_db` |
| D-8 | gering | Tooltip des Rückgängig-Knopfs deutet den Nachnamen als HTML |

## D-1: Spaltennamen aus der fremden Datei im SQL

- Stelle: `db_stamm.py:446-461` (`teilnehmer_wiederherstellen`); Namen aus `teilnehmer_sichern`
  (`db_stamm.py:415-422`, `SELECT *`). Aufrufer: `desktop_teilnehmer.py:813`, `:823` (Löschen, dann
  „Rückgängig“), `:842-844`, `:878` („Aus Sicherung holen…“).
- Ursache: `spalten = list(daten)` wird ungequotet und ungeprüft in `INSERT INTO teilnehmer (…)` und
  `INSERT INTO ergebnisse (…)` gesetzt. `pruefe_termin_aufbau` (`db_termine.py:192-203`) prüft keine
  Spaltennamen, `_termin_werte_pruefen` (`db_termine.py:314-317`) verlangt nur Soll ⊆ Ist, `init_db`
  lässt Zusatzspalten stehen.
- Weg a (nur die fremde Termin-Datei): Zusatzspalte in `ergebnisse`, deren Name SQL ist
  (`stechen_sieger) SELECT … ON CONFLICT(teilnehmer_id) DO UPDATE SET … --`, mit `?12`, damit die Zahl
  der Bindewerte stimmt). Kein Trigger, keine View, der H-1-Hinweis bleibt leer. Die Prüfungsleitung
  öffnet die Datei, trägt Ergebnisse ein, löscht einen Teilnehmer, klickt „Rückgängig“: das zweite
  `INSERT` überschreibt die Ergebnisse aller Teilnehmer.
- Weg b (trifft den eigenen Termin, baut auf D-5 auf): fremde Datei heißt wie der eigene Termin, wird
  einmal vom Stick geöffnet, das Programm legt selbst eine Kopie in `Auto-Sicherung` ab (`backup`
  übernimmt die Zusatzspalte). Später zeigt „Aus Sicherung holen…“ im eigenen Termin einen Teilnehmer
  der fremden Datei als gelöscht; das Zurückholen überschreibt alle eigenen Ergebnisse.
- Auswirkung: stille Veränderung von Teilnehmer- und Ergebnisdaten; möglich ist, was eine einzelne
  `INSERT … SELECT … ON CONFLICT DO UPDATE`-Anweisung kann (auch Lesen anderer Tabellen per
  Unterabfrage). Mehrere Anweisungen, `ATTACH`, `PRAGMA` gehen nicht.
- Nachgestellt: `b1\d1_spaltenname_sql.py`. Weg a: `{1: (50, 30), 2: (50, 30), 3: (50, 30)}` → nach
  „Rückgängig“ `{1: (0, 0), 2: (0, 0), 3: (0, 0), 99: (0, 0)}`. Weg b: `(55, 35)` → `(0, 0)`.
- Vorschlag: in `teilnehmer_wiederherstellen` nur bekannte Spalten zulassen (Schnittmenge mit den
  Soll-Spalten, vgl. `_soll_spalten` in `db_termine.py:292`) und Namen quoten. Grundsätzlicher: beim
  Öffnen unbekannte Spalten/Tabellen ablehnen oder Daten in eine frische Datei mit eigenem Schema
  übernehmen (erledigt D-7 mit).

## D-2: Präpariertes Rücksprung-Journal lässt SQLite eine fremde Datei löschen

- Stellen: `db_termine.py:278-290` (`_journal_zurueckspielen`: rohes `sqlite3.connect` mit Schreibrecht,
  sobald ein `-journal` daneben liegt), aufgerufen aus `liste_termine` (`db_termine.py:435`) und
  `termin_oeffnen` (`:382`). `db_sicherung.py:603-604`: ein `<name>.sqlite-journal` aus dem ZIP wird
  ungeprüft neben den Termin geschrieben.
- Ursache: Ein SQLite-Journal kann am Ende auf ein Super-Journal verweisen. Beim Zurückspielen öffnet
  SQLite die genannte Datei, deutet ihren Inhalt als Liste von Journal-Namen und löscht sie, wenn keiner
  davon existiert. Der Verweis darf ein beliebiger absoluter Pfad sein.
- Weg über ein Sicherungs-ZIP: `neu.sqlite` plus 600 Bytes großes `neu.sqlite-journal`.
  `sicherung_inhalt` zeigt nur `neu.sqlite`; die Wiederherstellung legt beide Dateien ohne
  Konfliktdialog ab. Beim nächsten `liste_termine` (Startdialog, „Anderen Termin öffnen…“,
  Import-Dialog) ist die Zieldatei gelöscht. Weitere Wege: Termin-Datei samt Journal vom Stick in den
  Termine-Ordner kopiert oder direkt per „Termin öffnen“.
- Auswirkung: Löschen einer Datei mit den Rechten des Benutzers, ohne Meldung und ohne Papierkorb. Mit
  zu klein angegebener Seitenzahl im Journal-Kopf lässt sich die danebenliegende Termin-Datei
  abschneiden (45056 → 4096 Bytes), das trifft nur die mitgelieferte Datei.
- Einschränkungen: absoluter Pfad muss bekannt sein (Benutzername). Gelöscht wurden Textdatei 750 Bytes,
  CSV rund 800 Bytes, Binärdatei, Datei mit Inhalt `abc`; nicht gelöscht: leere Datei, kurze Textdateien
  mit Zeilenumbruch oder `*?"` in den ersten rund 260 Zeichen, eine SQLite-Datei. Mit SQLite 3.53.4
  (Anaconda) wird nichts gelöscht, mit 3.46.1 (miniforge, Python 3.12.5) schon. Die SQLite-Version der
  ausgelieferten EXE ist ungeprüft (Build mit Python 3.11).
- Abgrenzung: C27, C28, C29 betreffen etwas anderes.
- Nachgestellt: `b1\d2_journal_loescht_datei.py` über die echten Funktionen, drei Wege, mit 3.46.1
  jeweils „Opfer vorhanden = False“. Im 3.46.1-Lauf fehlt `pyzipper` (durch Standardbibliothek ersetzt,
  also nur unverschlüsselte ZIPs). `b1\d2_debug3.py` zeigt, welche Inhalte gelöscht werden.
- Vorschlag: vor jedem Öffnen mit Schreibrecht bei vorhandenem `-journal` prüfen, ob die letzten 8 Bytes
  das Journal-Magic `d9 d5 05 f9 20 a1 63 d7` sind und das Längenfeld davor ungleich 0 ist; dann nicht
  öffnen. Dieselbe Prüfung beim Zurückschreiben eines Journals aus einem ZIP. SQLite-Version in
  „Diagnose kopieren“ ausgeben.

## D-3: S-8 begrenzt nur die angegebene Größe

- Stelle: `db_sicherung.py:68-91` (`_zip_grenzen_pruefen`); gelesen wird in `:467` (`sicherung_inhalt`)
  und `:587`.
- Ursache: Grenzen werden gegen `file_size` aus dem ZIP-Verzeichnis geprüft; `ZipExtFile` entpackt erst
  den ganzen Datenstrom und schneidet danach ab.
- Weg: ZIP mit `termin.sqlite`, angegebene Größe 1000 Bytes, echter Inhalt beliebig groß. Entpackt wird
  schon bei der Auswahl der Datei.
- Auswirkung: Arbeitsspeicher in voller entpackter Größe (rund das Doppelte); Einfrieren oder
  `MemoryError` (`desktop_verwaltung.py:595-619` fängt ihn nicht).
- Nachgestellt: `b1\d3_zip_groesse.py`. Harmlos 30 MB; DEFLATE 300 MB Inhalt (ZIP 299 KB) 631 MB;
  BZIP2 (ZIP unter 1 KB) 634 MB; LZMA (ZIP 44 KB) 639 MB.
- Vorschlag: über `zf.open()` in Blöcken lesen und bei mehr als `min(info.file_size, _MAX_DATEIGROESSE)`
  abbrechen; `compress_size` begrenzen; für die Passwortprobe nur die ersten Bytes lesen; Docstring
  korrigieren.

## D-4 (Hinweis): Lücken im Gerätenamen-Filter, ohne Wirkung

- Stelle: `db_sicherung.py:94-121` (`_ist_sicherer_dateiname`, Zeile 115).
- Durchgelassen: `COM¹.sqlite`, `COM².sqlite`, `LPT³.sqlite`, `CONIN$.sqlite`, `CONOUT$.sqlite`,
  `termin.sqlite.`, `termin.sqlite ` (Punkt/Leerzeichen am Ende).
- Wirkung unter Windows 11 (10.0.26300): gewöhnliche Datei bzw. `termin.sqlite`; über die Oberfläche
  nicht erreichbar (nur Namen mit Endung `.sqlite` werden angeboten). Windows 10 ungeprüft.
- Nachgestellt: `b1\d4_dateinamen.py`.
- Vorschlag: Punkt/Leerzeichen am Ende ablehnen, `¹²³` wie `1-3` behandeln, `CONIN$`/`CONOUT$`
  aufnehmen.

## D-5: Automatische Kopien werden nur über den Dateistamm zugeordnet

- Stellen: `db_sicherung.py:230`, `:239-258`, `:269-273` (`auto_sicherungen_zu_termin`);
  `db_stamm.py:425-432` (`fehlende_teilnehmer`, Abgleich nur über die ID); `db_ergebnisse.py:104-133`
  (`ergebnis_unterschiede`: Abgleich nur über die ID, der Name kommt aus dem geöffneten Termin).
- Über B15 hinaus: es genügt, dass zwei Termin-Dateien in verschiedenen Ordnern denselben Dateinamen
  tragen (unter Windows auch mit anderer Groß-/Kleinschreibung), z. B. eine zugeschickte Datei nach
  demselben Schema `Datum_Verein.sqlite`. Auch ein gelöschter und gleichnamig neu angelegter Termin erbt
  die alten Kopien.
- Ablauf: eigener Termin hat 10 Kopien; fremde gleichnamige Datei wird geöffnet und beendet; nach 10
  Kopien der fremden Datei sind alle eigenen durch die Rotation gelöscht; beide Dialoge bieten die
  fremden Kopien als „Kopie dieses Termins“ an.
- Auswirkung: Sicherheitsnetz verschwindet unbemerkt; `ErgebnisseSicherungDialog` zeigt eigene Namen mit
  Werten der fremden Datei; „Aus Sicherung holen…“ bietet fremde Teilnehmer als „gelöscht“ an.
- Nachgestellt: `b1\d5_gleicher_stamm.py` („davon eigene Kopien noch da: 0“; nach dem Wiederherstellen
  `{1: (10, 5), 2: (10, 5), 3: (10, 5)}`).
- Vorschlag: Kopien an die Identität des Termins binden (einmalige Kennung in der Termin-Datei, im
  Kopiennamen oder beim Anbieten verglichen; einfacher: Kurz-Hash des absoluten Pfads im Namen). In
  beiden Dialogen Verein und Datum vergleichen und bei Abweichung warnen; `ergebnis_unterschiede` auch
  Name und Hund vergleichen.

## D-6: Werte aus Kopien ohne Typprüfung

- Voraussetzung: präparierte Datei im Ordner `Auto-Sicherung` (von Hand hineinkopiert oder von einem
  zweiten Benutzer mit Schreibrecht).
- Stellen: `db_ergebnisse.py:148-154`, `db_stamm.py:450-461`, `db_termine.py:192-203`;
  `desktop_dialoge_termin.py:329`, `:352`, `:476` (Schrittgrenze wird aufgehoben, bevor erneut aus der
  Kopie gelesen wird).
- Fall a: Kommazahl `30.5` geht durch die CHECK-Regel; beim nächsten Start lehnt
  `_termin_werte_pruefen` den eigenen Termin ab. Abhilfe nur mit einem SQLite-Werkzeug.
- Fall b: Nachname als BLOB; danach lässt sich der eigene Termin ebenfalls nicht öffnen (Schutz K-2,
  `_als_text` in `db_import.py:869-905`, fehlt auf dem neuen Weg).
- Fall c: `ergebnisse` darf in der Kopie eine View sein (44 KB Datei, 114 MB Speicher mit
  `zeroblob`). Vermutung, nicht nachgestellt: zeitabhängige View könnte die Oberfläche einfrieren.
- Nachgestellt: `b1\d6_werte_aus_kopie.py`.
- Vorschlag: Werte vor dem Schreiben prüfen oder nach dem Schreiben und vor dem Commit
  `_termin_werte_pruefen(conn)` aufrufen und bei Fehler zurückrollen; für Kopien `ergebnisse` als
  gewöhnliche Tabelle verlangen, Views ablehnen; Schrittgrenze erst nach dem letzten Lesen aufheben.

## D-7: Fremdschlüssel-Aktionen fremder Zusatzspalten überleben `init_db`

- Stelle: `db_verbindung.py:558-567`, `:587-590`.
- Weg: fremde Datei mit Platzhalter-Teilnehmer (ID 1) und Zusatzspalte
  `gruppe INTEGER DEFAULT 1 REFERENCES teilnehmer(id) ON DELETE CASCADE`. Kein Trigger, keine View.
  Jeder neu erfasste Teilnehmer bekommt `gruppe = 1`; wird der Platzhalter gelöscht, löscht SQLite alle
  anderen Teilnehmer samt Ergebnissen.
- Auswirkung: Datenverlust durch eine in der Datei hinterlegte Regel; mit Kopie „vor dem Löschen“
  umkehrbar.
- Nachgestellt: `b1\d7_fk_aktionen.py` (5 Teilnehmer/5 Ergebniszeilen → 0).
- Vorschlag: wie D-1; minimal Dateien ablehnen, deren `PRAGMA foreign_key_list` mehr liefert als die
  drei eigenen Beziehungen.

## D-8: Tooltip des Rückgängig-Knopfs deutet den Nachnamen als HTML

- Stelle: `desktop_rueckgaengig.py:32`; Beschreibung mit Nachname aus `desktop_teilnehmer.py:820-823`.
- Weg: Nachname `<img src="…">` aus fremder Termin-Datei, CSV oder Formular; Teilnehmer löschen, Maus
  über „Rückgängig“: Qt erkennt Rich Text und lädt das Bild. Netzpfad bewusst nicht getestet.
- Nachgestellt: `b1\d8_tooltip.py` (`Qt.mightBeRichText: True`, Dokumenthöhe 48 statt 22).
- Vorschlag: Beschreibung mit `html.escape` maskieren und in `<qt>…</qt>` setzen (wie
  `desktop_zeitplan.py:112`).

## Regression geprüft

- H-1: greift im Hauptweg (`db_verbindung.py:574-600`, über `termin_oeffnen`, Meldung
  `_fremdobjekte_melden` in `app.py:181`). `trusted_schema` wurde nie umgesetzt (war nur Empfehlung).
  Lesende Wege laufen alle über `termin_lesend_pruefen`. Am gehärteten Weg vorbei:
  `_journal_zurueckspielen` (D-2). Greift nicht für Spaltennamen (D-1), Fremdschlüssel und DEFAULT (D-7).
  `ATTACH` kommt nirgends vor; URI nur in `oeffne_termin_lesend` mit `quote`.
- S-8: Anzahl und Größen vor dem Entpacken geprüft, auf beiden Wegen; nicht beim tatsächlichen Lesen
  (D-3). Pfadanteile, `..`, Backslash, Doppelpunkt, Steuerzeichen, Gerätenamen abgelehnt, doppelt
  geprüft. Lücken ohne Wirkung: D-4.
- Q-1 (Groß-/Kleinschreibung beim Wiederherstellen): greift.
- K-2 (BLOB als Text): greift im Import, fehlt auf den neuen Wegen (D-6).
- S-1: greift in den neuen Dialogen und Statuszeilen, nicht im Tooltip (D-8).
- Größen- und Schrittgrenze: wirksam auf allen lesenden Wegen; in den Sicherungs-Dialogen zu früh
  aufgehoben (D-6).

## Ohne Befund geprüft

SQL aus Textbausteinen in `db_verbindung`, `db_termine`, `db_ergebnisse`, `db_stamm` (außer D-1 nur
Konstanten); Migrationen auf fremden Dateien; Pfadbildung und Rotation der Auto-Kopie (über B15 und D-5
hinaus kein Weg aus `Auto-Sicherung` heraus); Endung `_vor-Loeschen`; atomares Schreiben; Temp-Dateien;
symbolische Links/Junctions; Passwort der Sicherung (nicht gespeichert, nicht protokolliert);
Laufwerkshinweis; Terminübersicht; Datenschutz der Kopien (Handbuch nennt „unverschlüsselt“).

Nicht geprüft: Web, Container, PostgreSQL, Verhalten unter Windows 10, macOS, Linux.
