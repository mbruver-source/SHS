# Sicherheitsprüfung des SHS-Prüfungsprogramms

Datum: 03.10.2026. Auftraggeber: Marco, Software-Eigentümer.
Geprüft: aktueller lokaler Arbeitsstand in `C:\Users\mbruv\Documents\SHS-Pruefungsprogramm-Git`, einschließlich bereits vorhandener uncommitteter Änderungen. Referenz: `Sicherheitspruefung-2026-10/Bericht.md` und relevante Entscheidungen in `Fortschritt.md`.

## Ergebnis und Einordnung

**11 Befunde: 0 kritisch, 0 hoch, 6 mittel, 5 gering.** Davon **ein neuer Befund C-1**, neun bestätigte bekannte S-Befunde und der nun mit konkreter Integritätsverletzung belegte bisherige Hinweis H-1. H-2 bis H-4 bleiben zusätzliche Hinweise und sind nicht mitgezählt. S-7 wird für den untersuchten Fehlerpfad nicht bestätigt.

| ID | Schwere | Kurztitel |
|---|---|---|
| C-1 | mittel | Alte Sitzung übernimmt ein unter gleichem Namen neu angelegtes Konto |
| S-1 | mittel | Rich-Text-Injektion in der Zeitplan-Seitenleiste |
| S-2 | mittel | Öffentlich bekannter Beispielschlüssel erlaubt Cookie-Fälschung |
| S-3 | mittel | Überbreite CI-Rechte und bewegliche Build-Abhängigkeiten |
| S-4 | mittel | PDF-Markup-Injektion mit lokaler Bildeinbettung und Exportabbruch |
| H-1 | mittel | Fremde SQLite-Trigger manipulieren spätere Ergebniseingaben |
| S-5 | gering | Web-Anwendung verwendet das Datenbank-Eigentümerkonto |
| S-6 | gering | Fehlende Schutz-/Cache-Header und Abmelden per GET |
| S-8 | gering | Sicherungsimport ohne Entpackgrenzen; reservierte Windows-Namen |
| S-9 | gering | Tag-Inhalt wird als PowerShell-Ausdruck interpretiert |
| S-10 | gering | DSN-Passwort als Kommandozeilenargument |

Die Schwere berücksichtigt das Vereinsnetz, erforderliche Nutzeraktionen und Angreiferrechte. Insbesondere C-1 kann Adminrechte vermitteln, setzt aber eine legitime erneute Vergabe desselben Kontonamens voraus. S-3 ist eine statisch bestätigte Härtungslücke, kein nachgewiesener Lieferkettenkompromiss. S-4 wurde gegenüber dem Vorbericht auf mittel eingeordnet; H-1 erhält wegen des konkreten Manipulationsnachweises erstmals eine Schwachstellen-Schwere.

## Vorgehen und Grenzen

- Quellcodeprüfung mit getrennten Rollen für Web, Daten/Dateiformate sowie Desktop/CI; ergänzende Prüfung und Zusammenführung durch den Hauptprüfer. C-1 zusätzlich unabhängig gegengeprüft.
- Schreiborte ausschließlich `C:\Users\mbruv\AppData\Local\Temp\shs_codex_pruefung` und diese Berichtsdatei. Keine Änderungen im Repository, kein Commit/Push, keine Installation, kein Zugriff auf echte Termine. Inhalts-Hashes der Repo-Dateien waren bei der Abschlusskontrolle unverändert (ausgenommen von diesem Vergleich: `.git` und vorhandene Bytecode-Verzeichnisse). Python wurde mit `-B` ausgeführt.
- Laufzeit: `C:\Users\mbruv\anaconda3\python.exe`. Web-Reproduktionen mit Flask-Testclient, echten Kontenfunktionen und temporärer SQLite-Datenbank; PostgreSQL-Verbindungs-/Schemaschicht wie in `test_app_web.py` ersetzt. Kein echter PostgreSQL-Server und kein Container/CI-Deployment gestartet. Aussagen über produktive SQL-Nebenläufigkeit bleiben daher statisch.
- Kein externer Netzwerkzugriff. Ein PDF-Bildlade-Gegenversuch verwendete ausschließlich einen lokalen Testserver; dabei kam kein HTTP-Request an. Keine UNC-/SMB-Ziele getestet. Keine echten Zugangsdaten verwendet.
- Bewusst akzeptierte Punkte aus dem Auftrag sind ausgeschlossen. Auch die bereits akzeptierte gleitende Sessiondauer wird nicht erneut gemeldet.
- 113 ausgewählte vorhandene Tests: **112 bestanden, 1 übersprungen, keine Fehler** (Web/CSRF 68; PostgreSQL-Wrapper/Kernlogik 27 mit einem Skip; Synchronisation/Exportfehlerpfade 18). Zusätzlich gezielte Nachweise, deren Skripte und Ergebnisse im Temp-Testordner liegen. Keine vollständige GUI-/PostgreSQL-/Installationsprüfung und kein CVE-Abgleich gegen externe Datenbanken.

## Befunde mit Nachweisen

### C-1 — Alte Sitzung übernimmt ein neu angelegtes Konto gleichen Namens

**Schwere:** mittel. **Neu. Stelle:** `app_web.py:226–247`, `app_web.py:358–364`; `db.py:2549–2574`, Kontoschema `db.py:2404–2410`.

Die Sitzung speichert nur den wiederverwendbaren Benutzernamen. Bei jeder Anfrage wird das aktuell unter diesem Namen bestehende Konto nachgeladen und dessen aktuelle Rolle übernommen. Eine unveränderliche Konto-ID oder Generation der Anmeldung wird nicht verglichen. Das Löschen und erneute Anlegen desselben Namens mit einem neuen Passwort entwertet deshalb ein zuvor ausgestelltes Cookie nicht zuverlässig.

**Lokal reproduziert: ja.** Nachweis `web/verify_web.py`, Ergebnisse `web/web_results.json`:

1. Testadministrator legt einen gewöhnlichen Richter an. Dieser meldet sich regulär an; sein Cookie wird für die Gegenprobe bewahrt. Adminseite liefert zunächst 403.
2. Administrator löscht das Richterkonto. Zugriff in diesem Zustand führt korrekt zum Login (302).
3. Administrator legt denselben Namen mit anderem Passwort und Adminrolle neu an.
4. Ein separater Testclient verwendet ausschließlich das vorher bewahrte, regulär ausgestellte Cookie: Adminseite liefert 200; das alte Passwort bleibt ungültig.
5. Mit dieser Sitzung wird ein zusätzliches erfundenes Adminkonto erfolgreich angelegt (302, anschließend in der Datenbank mit Adminrolle nachgewiesen).

Keine Signaturfälschung, kein Wissen um den geheimen Schlüssel und kein CSRF-Bypass sind hierfür nötig. Der CSRF-Testclient verwendet das legitime Sitzungstoken. Voraussetzung ist ein noch gültiges altes Cookie sowie die tatsächliche Wiedervergabe des Namens. Ein normaler Browser darf während des Löschfensters keine Anfrage gestellt haben, die sein Cookie leert; alternativ kann eine zuvor gespeicherte Kopie wiederverwendet werden, wie im Nachweis. Bei Neuanlage ohne Adminrolle entsteht unbefugter Zugriff auf das neue normale Konto. Eine unabhängige Code-/Nachweisprüfung bestätigte Ursache und Ergebnis.

**Behebungsvorschlag:** Zufällige unveränderliche Konto-ID bzw. Authentifizierungsgeneration je Konto anlegen und in der signierten Sitzung speichern. Bei jeder Anfrage gegen den aktuellen Datensatz prüfen. Bei Kontoneuanlage stets neue Kennung erzeugen, bei Passwortwechsel/Sperrung die Generation erneuern. Regressionstest für Löschen/Neuanlegen mit gleicher und geänderter Rolle.

### S-2 — Unveränderter Beispielschlüssel ermöglicht Cookie-Fälschung

**Schwere:** mittel. **Stelle:** `app_web.py:153`, `app_web.py:202`, `app_web.py:328–340`; `.env.example:16`, `.env.example:28`; `compose.yaml:50–53`.

**Lokal reproduziert: ja, für die Session-Fälschung bei unveränderter Beispielkonfiguration.** Vor dem Import der Anwendung wurde ausschließlich im Testprozess der öffentliche Beispielwert aus `.env.example` als `SHS_WEB_SECRET_KEY` gesetzt. Ein unabhängiges Flask-Signierobjekt mit diesem bekannten Wert erzeugte ein Cookie für den existierenden Testadministrator. Ein separater Client ohne Passwortanmeldung erhielt die Adminseite (200) und konnte ein künstliches Adminkonto anlegen (302 und Datenbanknachweis). Die aktuelle Rollenrevalidierung verhindert dies nicht: der Angreifer muss lediglich einen existierenden Adminnamen kennen oder erraten. Ergebnisse unter `S2_*` in `web/web_results.json`.

Der Anwendungscode lehnt den Beispielwert nicht ab; ebenso wird der öffentliche Beispiel-Einrichtungscode ohne Platzhalterprüfung als Konfiguration übernommen. Letzteres wurde statisch bestätigt, nicht gesondert mit unverändertem Einrichtungscode nachgestellt. Dieser Fund betrifft ausdrücklich Installationen mit unverändertem bzw. bekanntem Schlüssel; ein korrekt erzeugter geheimer Zufallswert wurde nicht gebrochen.

**Behebungsvorschlag:** Bekannte Platzhalter und unzureichende Schlüssel beim Start ablehnen; Einrichtung nur mit individuell erzeugtem Code erlauben. Wurde ein Beispielschlüssel bereits verwendet, Schlüssel wechseln und damit alle bisherigen Cookies invalidieren; Konten auf unberechtigte Änderungen prüfen.

### S-6 — Fehlende Schutz-/Cache-Header; Abmelden per GET

**Schwere:** gering. **Stelle:** `app_web.py:369–372`, zentrale App-Konfiguration ab `app_web.py:63` und geschützte Antworten, etwa `app_web.py:539–544`.

**Lokal reproduziert: ja, HTTP-Verhalten.** Authentifizierte Antwort auf `/admin/benutzer` enthält weder `X-Frame-Options`, `Content-Security-Policy`, `Cache-Control` noch `X-Content-Type-Options`. GET `/logout` liefert 302 und führt `session.clear()` aus. Protokoll: `web/web_results.json`, Felder `S6_*`. Eine tatsächliche Clickjacking-Aktion in einem Browser oder Offenlegung aus einem Browsercache wurde nicht reproduziert; das sind mögliche Folgen der fehlenden expliziten Schutzrichtlinien. GET-Abmeldung ermöglicht fremdveranlasste Abmeldung bei passender Navigation, keine privilegierte Datenänderung.

**Behebungsvorschlag:** Zentrale Antwortheader einrichten: mindestens `frame-ancestors 'none'`/`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` und `Cache-Control: no-store` auf vertraulichen Seiten. CSP anhand vorhandener Inline-Skripte/-Stile passend gestalten. Abmelden als POST mit dem vorhandenen CSRF-Schutz anbieten.

## S-1 – mittel – Unmaskierte Daten im Rich Text der Zeitplan-Seitenleiste

**Stelle:** app.py:2457, app.py:2565, app.py:2566, app.py:2579.

**Lokal reproduziert: ja, Komponentenprüfung.** Die unveränderte Originalmethode `_offene_starts_aktualisieren` wurde per AST extrahiert. Mit erfundenen Status-/Konfliktdaten und einem echten PySide6-QLabel (Qt.RichText) wurde ein Nachname mit `<img src="lokaler Testbildpfad">` angezeigt. Das eigens erzeugte 16×16-Pixel-Testbild erschien vollständig: 256 magentafarbene Pixel im gerenderten Label. Damit sind HTML-Injektion und das Laden einer lokalen Bildressource nachgewiesen. Keine vollständige Import-/GUI-Kette ausgeführt. **UNC-/SMB-Zugriff und Anmeldedatenabfluss wurden nicht getestet und sind lediglich mögliche, unvalidierte Folgen.** Kein Netzwerkzugriff.

Nachweis: `desktop_ci/repro_s1.py`, `desktop_ci/marker.png`, `desktop_ci/s1-render.png` im Temp-Testordner. Wiederholung aus dem Repo mit `C:/Users/mbruv/anaconda3/python.exe -B <Temp-Testordner>/desktop_ci/repro_s1.py`; es entstehen ausschließlich Testartefakte dort.

**Behebung:** Sämtliche dynamischen Texte vor Rich-Text-Einfügung mit `html.escape(str(...))` maskieren, insbesondere Teilnehmer- und Richternamen. Alternativ strukturierte Anzeige ohne HTML.

## S-3 – mittel – Überbreite CI-Rechte und bewegliche Build-Abhängigkeiten

**Stelle:** .github/workflows/build-installer.yml:30, :38, :41, :48, :50, :101, :131; .github/workflows/build-container.yml:35, :37, :61, :89, :109, :112, :119.

**Lokal reproduziert: nein; statisch bestätigt.** Installer setzt `contents: write` für den ganzen Workflow, Container-Workflow `packages: write` auch für den Smoke-Test. Actions sind über bewegliche Tags statt Commit-SHAs eingebunden; PyInstaller/Inno Setup werden ohne feste Version installiert. Kein CI-Lauf, kein nachgewiesener Lieferkettenkompromiss. Aus diesen Dateien lässt sich insbesondere nicht ableiten, dass fremde Fork-PRs automatisch Schreibrechte erhalten. Bedingte Härtungslücke, Schwere des früheren Berichts übernommen.

**Behebung:** Rechte pro Job minimieren, Veröffentlichung abtrennen, Actions auf geprüfte Commit-SHAs und Buildwerkzeuge auf geprüfte Versionen festlegen.

## S-9 – gering – PowerShell-Ausdrucksauswertung über Tag-Namen

**Stelle:** .github/workflows/build-installer.yml:69, :72.

**Lokal reproduziert: ja, Teilreproduktion der Skriptsemantik.** `git check-ref-format 'refs/tags/v$(7+7)'` akzeptierte den Testnamen. Die daraus resultierende Originalzeile `$tagVersion = "v$(7+7)".TrimStart('v')` ergab lokal `14` statt des literalen Tag-Inhalts `$(7+7)`. Ausdrucksauswertung erfolgt vor dem Versionsvergleich. Keine GitHub-Ausführung; nur harmlose lokale Arithmetik. Ein gespeichertes `.ps1` wurde durch ExecutionPolicy blockiert; die Policy blieb unverändert. Derselbe Einzeiler wurde inline ausgeführt. Artefakt: `desktop_ci/repro_s9.ps1`.

Voraussetzung ist die Möglichkeit, relevante Tags zu pushen bzw. den betroffenen Workflow auszulösen; kein anonymer Angriffspfad.

**Behebung:** Den Tag über `env:` übergeben und mittels `$env:SHS_TAG` lesen; zusätzlich strenge Versionsformatprüfung. Keine direkte Einbettung von GitHub-Ausdrücken in Skriptquelltext.


## S-4 – Unmaskiertes PDF-Markup kann lokale Bilder in den Export übernehmen

- **Schwere:** mittel (bisher gering–mittel; zusätzlicher Vertraulichkeitsnachweis). Voraussetzung: fremde Termin-Datei bzw. beeinflussbarer Vereins-/Richtername wird geöffnet und ein betroffener Export erstellt. Eine automatische Übermittlung ist nicht nachgewiesen; eine Weitergabe des erzeugten PDFs kann eingebettete Bildinhalte offenlegen.
- **Stelle:** `pdf_export.py:638–639`, weitere gleichartige Titel bei 878, 1182, 1268, 1325, 1499 und 1506–1509. Die vorhandene Maskierungshilfe `_p_wert` steht bei 210.
- **Lokal reproduziert: ja.** In der isolierten SQLite-Testdatei wurde der Vereinsname mit `Test <img src="C:/Users/mbruv/AppData/Local/Temp/shs_codex_pruefung/data/marker.png" width="7" height="9"/>` gesetzt. Das PNG wurde eigens als künstliches 7×9-Pixel-Testbild angelegt. Aufruf von `erstelle_ergebnisliste_pdf` erzeugte `s4.pdf`; die Auswertung mit pypdf wies im Seiten-XObject ein Bild mit Breite 7 und Höhe 9 nach. Es wurde ausschließlich das eigens erzeugte Testbild gelesen. Anschließend verursachte `Test <font color="not-a-color">Name</font>` einen `ValueError: Invalid color value 'not-a-color'` beim Export.
- **Zusatzprüfung:** Dieselbe Bildmarkierung mit einer URL zu einem eigens gestarteten HTTP-Server auf `127.0.0.1` führte zu OSError; der Server registrierte **null Requests**. Netzwerkzugriff/SSRF ist somit in dieser Umgebung **nicht** nachgewiesen. Kein externes Ziel wurde verwendet. Beliebige Nicht-Bilddateien sind ebenfalls nicht als auslesbar nachgewiesen.
- **Behebungsvorschlag:** Vereins- und Richternamen sowie alle übrigen variablen Texte vor Übergabe an `Paragraph` mit `_p_wert`/XML-Escaping maskieren. Tests mit `<img>`, `<font>` und normalen Sonderzeichen für sämtliche Titel ergänzen.
- **Nachweisdateien:** `%TEMP%\shs_codex_pruefung\data\repro.py`, `results.json`, `marker.png`, `s4.pdf`, `http_repro.py`, `http_result.json`.

## S-8 – Sicherungsarchive werden ohne Mengenbegrenzung dekomprimiert

- **Schwere:** gering.
- **Stelle:** `db_sicherung.py:125–135` (erste Datei wird bereits zur Passwortprüfung komplett gelesen), `db_sicherung.py:186–195` (vollständiges Lesen und Schreiben jedes Eintrags), `_ist_sicherer_dateiname` bei 33–53.
- **Lokal reproduziert: ja, begrenzter Funktionsnachweis; Speichererschöpfung nicht ausgelöst.** Ein künstliches ZIP mit einem 4-MiB-Eintrag `gross.sqlite` war komprimiert 4.203 Byte groß. `sicherung_inhalt` akzeptierte es; `sicherung_wiederherstellen` schrieb 4.194.304 Byte in den isolierten Wiederherstellungsordner. Der Code enthält weder Anzahl-, Einzelgrößen- noch Gesamtgrößenlimits. Ein tatsächlicher Ressourcenabsturz wurde bewusst nicht provoziert und wird nicht als reproduziert behauptet.
- **Sondernamen:** `_ist_sicherer_dateiname('CON.sqlite')` liefert auf Windows `True`; Geräte-Sondernamen werden nicht ausdrücklich abgefangen. Ein Schreibversuch auf das Gerät wurde nicht durchgeführt. **Korrektur zum früheren Bericht:** `x:ads.sqlite` wurde auf diesem Windows-Rechner bereits abgelehnt (`False`, durch die Basename-Prüfung); der dort genannte ADS-Beispielname ist hier nicht reproduzierbar.
- **Behebungsvorschlag:** Vor dem ersten Lesen Anzahl und `ZipInfo.file_size` aller ausgewählten Einträge prüfen; zusätzlich beim gestreamten Dekomprimieren ein tatsächliches Bytebudget erzwingen. Reservierte Windows-Gerätenamen vor Auswahl und Wiederherstellung ablehnen. Dies betrifft lokale Sicherungsarchive und nicht das bewusst akzeptierte Web-Login-Uploadlimit.
- **Nachweisdateien:** `%TEMP%\shs_codex_pruefung\data\repro.py`, `results.json`, `bounded.zip`, `restore\gross.sqlite`.

## H-1 – Zusatznachweis: fremder SQLite-Trigger verändert Ergebnisse nach dem Öffnen

- **Schwere:** mittel (bestehende ID H-1 beibehalten; gegenüber dem früheren Hinweis jetzt durch stille Veränderung später regulär erfasster Ergebnisse belegt).
- **Stelle:** `db.py:569–578` (`init_db` öffnet und migriert ohne Trigger-Ablehnung), `db.py:1144–1148` (normale Ergebnisaktualisierung).
- **Lokal reproduziert: ja.** In einer künstlichen Termin-Datei wurde ein zusätzlicher `AFTER UPDATE OF suche_flaechensuche ON ergebnisse`-Trigger angelegt, der den gerade geschriebenen Wert wieder auf 0 setzt. Verbindung geschlossen und über das reguläre `init_db` erneut geöffnet. Der Trigger war weiterhin vorhanden. Der reguläre Aufruf `eintragen_ergebnis(conn, id, 'Flächensuche', 50, 30)` lief erfolgreich; anschließendes Lesen ergab Suchleistung **0 statt 50**. Betroffen blieb ausschließlich die künstliche Datei im Temp-Testordner.
- **Behebungsvorschlag:** Fremde Dateien in eine frisch erzeugte Datenbank mit bekanntem Schema übernehmen; Tabellen und Spalten explizit zulassen, Trigger und unerwartete Views ablehnen. `PRAGMA trusted_schema=OFF` kann zusätzlich härten, verhindert allein aber **nicht** gewöhnliche UPDATE-Trigger. `integrity_check` prüft strukturelle Integrität und erkennt diese fachliche Manipulation ebenfalls nicht zuverlässig.
- **Nachweisdateien:** `%TEMP%\shs_codex_pruefung\data\repro.py`, `results.json`, `test3.sqlite`.


### S-5 — Web-Anwendung verwendet das Datenbank-Eigentümerkonto

**Schwere:** gering. **Stelle:** `compose.yaml:18`, `compose.yaml:49`; Schema-Erzeugung in `db.py:2688`.

**Lokal reproduziert: nein.** Statische Prüfung: `POSTGRES_USER` für die Datenbankinitialisierung und der Benutzer in `SHS_POSTGRES_DSN` stammen aus derselben Variable `SHS_DB_USER`. Ein separates eingeschränktes Laufzeitkonto wird im Stack nicht eingerichtet. Damit ist die fehlende Trennung von Datenbankverwaltung und Web-Laufzeit im Code belegt; tatsächliche Datenbankrechte eines bestehenden Deployments wurden nicht abgefragt. Ein zusätzlicher Angriff auf die Anwendung hätte entsprechend größeren Datenbank-Schadensradius. Dies ist allein kein Nachweis einer SQL-Injection.

**Behebungsvorschlag:** Datenbankinitialisierung/Migration und Laufzeitkonto trennen. Dynamische Schema-Verwaltung über eine eng begrenzte Verwaltungsfunktion oder einen gesonderten Verwaltungsdienst durchführen; Ergebniseingabe mit minimalen Rechten betreiben.

### S-10 — Passwort im DSN-Kommandozeilenargument

**Schwere:** gering. **Stelle:** `sync_termin.py:27`, `sync_termin.py:28`, `sync_termin.py:43`, `sync_termin.py:124`, `sync_termin.py:133`.

**Lokal reproduziert: nein.** Statische Prüfung: Beide Unterbefehle akzeptieren `--dsn`, und die Beispiele zeigen einen DSN mit Passwort. Bei dieser Verwendungsweise wird das Passwort Bestandteil der Prozessargumente und gegebenenfalls des Shellverlaufs. Kein echter Synchronisationslauf gestartet und keine fremden Prozesse/Verläufe ausgelesen. Sichtbarkeit hängt von Betriebssystemrechten und Shellkonfiguration ab. Bereits vorhandene Alternative: `SHS_POSTGRES_DSN`.

**Behebungsvorschlag:** Passwortlose DSNs mit restriktiv geschützter PostgreSQL-Passwortdatei oder interaktive geheime Eingabe bevorzugen; Dokumentationsbeispiele ohne Passwortargument. Umgebungsvariablen vermeiden zumindest die Kommandozeile, sind aber kein vollständiger Geheimnisschutz (H-3).

## Ohne Befund geprüft

- **SQL-Injection über Schema-Namen:** `db.py:2342` verwendet `fullmatch` mit `termin_[0-9]+`. Sechs lokale Gegenproben mit SQL-Anhang, Zeilenumbruch, Pfad, Anführungszeichen und Unicode-Ziffer wurden abgewiesen. Skript: `root/additional.py`.
- **SQL-Injection beim Login:** `db.py:2589` und folgende verwenden gebundene Parameter. Lokale Eingabe `' OR 1=1 --` und falsches Passwort ergaben keine Anmeldung; die richtige Testanmeldung funktionierte. Benutzerlisten enthalten keine Passwort-Hashes.
- **Rollen und CSRF:** Normaler Benutzer erhält 403 für Benutzerverwaltung, Terminverwaltung und Admin-Downloadroute. Fehlendes/falsches CSRF-Token wird mit 403 abgewiesen. 68 bestehende Web-/CSRF-Tests erfolgreich. Das gilt unabhängig vom neuen Kontowiederverwendungsproblem C-1.
- **Web-HTML-Escaping:** Ein künstlicher Benutzername mit `<script>` wurde im tatsächlichen Admin-Template escaped ausgegeben; kein ungefiltertes Script-Element. Statische Templateprüfung ergänzt den Laufzeittest.
- **ZIP-Pfadtraversal:** `../escape.sqlite`, `..\escape.sqlite` und `C:\escape.sqlite` werden abgewiesen. Der im Vorbericht pauschal beanstandete Doppelpunktname `x:ads.sqlite` wurde auf diesem Windows-System ebenfalls abgewiesen; kein bestätigter ADS-Angriff. S-8 beschränkt sich auf belegte Teilaspekte.
- **CSV-Formelschutz:** Gefährliche Präfixe `=`, `@`, `+`, `-` und führende Leerzeichen/Tabulator vor einer Formel erhielten das Schutzapostroph; ein gewöhnlicher Telefonwert blieb erhalten. Keine Excel-Ausführung getestet.
- **Synchronisation und Fehlerpfade:** 18 Tests für Zuordnung, Schutz vor falscher Teilnehmerzuordnung und Exportbereinigung erfolgreich. Zusätzlich Wrapper-/Kernlogiktests erfolgreich bis auf einen regulären Skip; Protokolle `root/sync_tests.txt`, `root/tests.txt`.
- **S-7 — nicht bestätigt im untersuchten Fehlerpfad:** `app_web.py:629–648` löscht Uploads bei SQLite-Initialisierungs- bzw. Importfehlern. Bei Fehlern der nachfolgenden Seitenerzeugung ist die Datei bereits unter einem Downloadtoken registriert (`app_web.py:657`), sodass die vorhandene Ablaufbereinigung greifen kann. Keine Reproduktion einer dauerhaft unregistrierten Datei für den im Vorbericht beschriebenen Pfad; keine pauschale Garantie für jeden denkbaren Prozessabbruch.
- **Prozess-/Pfadübergaben Desktop:** Explorer mit Argumentliste ohne Shell, lokale URLs mittels `QUrl.fromLocalFile`; keine belegte Shell-Injection in diesen Aufrufen. Hilfedialog hat statischen Inhalt und deaktivierte externe Links. Manuelle Versionsprüfung statisch mit festen Adressen/PlainText geprüft, nicht ausgeführt.
- **Deployment/Installer:** Container verwendet Benutzer `shs`; PostgreSQL-Port an `127.0.0.1` gebunden. Installer standardmäßig mit niedrigsten Rechten; keine Löschanweisung für den echten Termineordner gefunden. Kein `pull_request_target`-/`workflow_run`-Vertrauensübergang in den geprüften Workflows.

## Weitere bekannte Hinweise, nicht als neue Schwachstellen gezählt

- **H-2:** `Containerfile:12`, `Containerfile:19`, `compose.yaml:15` sowie Requirements: bewegliche Image-Tags und Versionsbereiche statt vollständiger Versions-/Hashbindung. **Lokal reproduziert: nein**, statisch bestätigt. Vorschlag: geprüfte Digests/Lockdateien mit planmäßigen Updates. Überschneidung mit S-3, keine zusätzliche Zählung.
- **H-3:** `compose.yaml:19` und `compose.yaml:49`: Datenbankpasswort wird über Containerumgebung weitergegeben. **Lokal reproduziert: nein**, keine Umgebung eines laufenden Containers ausgelesen. Vorschlag: geschützte Secret-Dateien/Passwortdatei und beschränkter Verwaltungszugriff.
- **H-4:** `installer.iss:76`: `CloseApplications=force`. **Lokal reproduziert: nein**, kein Installer gestartet. Vorschlag: Rückfrage oder verifizierte Datensicherung vor erzwungenem Schließen. Dies bleibt der bekannte Betriebs-/Datenverlustrisiko-Hinweis.

## Reproduktionsartefakte

Alle relativen Pfade in diesem Bericht beziehen sich auf `C:\Users\mbruv\AppData\Local\Temp\shs_codex_pruefung`.

- `web/verify_web.py`, `web/web_results.json`, `web/existing_web_tests.txt`
- `data/repro.py`, `data/results.json`, lokale Testdaten und Test-PDFs
- `desktop_ci/repro_s1.py`, `desktop_ci/s1-render.png`, `desktop_ci/repro_s9.ps1`
- `root/additional.py`, `root/tests.txt`, `root/sync_tests.txt`, `root/verify_unchanged.py`

Repros ausschließlich im Testordner ausführen. Daten-Repro legt künstliche Datenbanken/Trigger an; für Wiederholungen die im Skript genannten Testdateien innerhalb dieses Testordners durch neue Namen ersetzen, falls sie bereits bestehen. Das PowerShell-Skript erfordert keine Änderung der ExecutionPolicy: der Nachweis verwendete den dokumentierten harmlosen Einzeiler inline.
