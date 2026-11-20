# SHS-Prüfungsprogramm – Web-Version (Podman/Container)

Diese Anleitung beschreibt, wie das Web-Backend (Ergebniseingabe für mehrere Richter
gleichzeitig am Prüfungstag, siehe `app_web.py`) als Container läuft – als Ergänzung
zur bestehenden Desktop-Version, nicht als Ersatz. Hintergrund/Architektur siehe
`Fortschritt.md` (Abschnitte zur Podman/Web-Version), Ablauf am Prüfungstag siehe unten
sowie `sync_termin.py`.

**Umfang (mit dem Nutzer abgestimmt):** NUR Ergebniseingabe, über echte Benutzerkonten
(Benutzername/Passwort) statt eines gemeinsamen Zugangscodes je Termin - siehe Abschnitt
"Benutzerkonten" unten. Termin anlegen, Teilnehmerverwaltung, Zeitplan und PDF-Export
bleiben Desktop-Aufgaben vor/nach dem Prüfungstag.

## Voraussetzungen

1. [Podman](https://podman.io/) – unter Windows am einfachsten über
   [Podman Desktop](https://podman-desktop.io/) (richtet im Hintergrund eine
   WSL2-Umgebung ein, in der die Container tatsächlich laufen).
2. `podman-compose` (wird von Podman Desktop meist mitgebracht; falls nicht:
   `pip install podman-compose`). Alternativ funktioniert auch `docker compose`
   unverändert mit denselben Dateien, falls stattdessen Docker verwendet wird.

## Einrichtung (einmalig)

1. **Geheimnisse anlegen** (siehe Abschnitt „Geheimnisse“ unten): drei Dateien im
   Ordner `secrets/` für Datenbank-Passwort, Session-Schlüssel und Einrichtungs-Code.
2. **HTTPS-Zertifikat erzeugen** (siehe Abschnitt „HTTPS und Zertifikat“ unten):
   `powershell -ExecutionPolicy Bypass -File tools\zertifikat_erzeugen.ps1`, den
   ausgegebenen Fingerabdruck notieren. Ohne Zertifikat startet der Proxy nicht.
3. Optional `.env.example` nach `.env` kopieren, um Benutzer- und Datenbankname oder das
   Image zu ändern. Ohne `.env` gelten die Vorgaben (Benutzer und Datenbank `shs`).
   `.env` und `secrets/` **nicht** committen (stehen in `.gitignore`).

   ```
   cp .env.example .env
   ```

   **Seit der Sicherheitsprüfung vom 03.10.2026:** Die Web-Version startet nicht, solange
   noch Platzhalter („bitte-hier-…“) eingetragen sind oder der Session-Schlüssel kürzer als
   32 bzw. der Einrichtungs-Code kürzer als 12 Zeichen ist. Die Fehlermeldung im
   Container-Log nennt den Befehl zum Erzeugen.

## Geheimnisse

Seit H-3 (05.10.2026) stehen Datenbank-Passwort, Session-Schlüssel und Einrichtungs-Code
nicht mehr in `.env`, sondern als Secret-Dateien in `secrets/`. Die Container lesen sie
unter `/run/secrets/`. So tauchen sie nicht in `podman inspect` auf, und Sonderzeichen im
Passwort sind kein Problem mehr.

| Datei | Inhalt | Erzeugen |
|---|---|---|
| `secrets/db_passwort.txt` | Datenbank-Passwort | `python -c "import secrets; print(secrets.token_hex(16))"` |
| `secrets/web_secret_key.txt` | Session-Schlüssel (mind. 32 Zeichen) | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `secrets/admin_setup_code.txt` | Einrichtungs-Code für den ersten Administrator (mind. 12 Zeichen) | `python -c "import secrets; print(secrets.token_urlsafe(16))"` |

Anlegen unter Windows (PowerShell, ohne Python – die Zufallswerte kommen aus Windows selbst):

```
mkdir secrets
function New-ShsGeheimnis([int]$Bytes) { $b = New-Object byte[] $Bytes; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); -join ($b | ForEach-Object { $_.ToString('x2') }) }
New-ShsGeheimnis 16 | Out-File -Encoding ascii secrets\db_passwort.txt
New-ShsGeheimnis 32 | Out-File -Encoding ascii secrets\web_secret_key.txt
New-ShsGeheimnis 12 | Out-File -Encoding ascii secrets\admin_setup_code.txt
```

Wer Python im PATH hat, kann stattdessen die Befehle aus der Tabelle oben nehmen
(`python -c "…" | Out-File -Encoding ascii secrets\…`). Unter Windows ist `python` oft nicht
eingerichtet oder öffnet nur den Microsoft Store – dann die Variante oben nehmen. Den
Einrichtungs-Code (`Get-Content secrets\admin_setup_code.txt`) braucht man einmal bei der
Ersteinrichtung im Browser.

Unter Linux:

```
mkdir -p secrets
python3 -c "import secrets; print(secrets.token_hex(16))" > secrets/db_passwort.txt
python3 -c "import secrets; print(secrets.token_hex(32))" > secrets/web_secret_key.txt
python3 -c "import secrets; print(secrets.token_urlsafe(16))" > secrets/admin_setup_code.txt
chmod 644 secrets/*.txt
```

Der Web-Container läuft als eigener Benutzer `shs` und muss die Dateien lesen dürfen.
Unter Linux mit rootless Podman deshalb `chmod 644`, sonst bricht die Web-Version beim
Start mit „Datei ist nicht lesbar“ ab. Den Ordner selbst schützt man über die Rechte des
Benutzerkontos, unter dem Podman läuft. Auf Linux mit SELinux (z. B. Fedora, RHEL) kann der
Zugriff trotzdem verweigert werden; dann hilft `chcon -t container_file_t secrets/*.txt`.
Unter Windows (Podman Desktop/WSL) ist das nicht nötig.

**Umzug einer bestehenden Installation** (die Geheimnisse standen bisher in `.env`):

1. Die Werte von `SHS_DB_PASSWORD`, `SHS_WEB_SECRET_KEY` und `SHS_ADMIN_SETUP_CODE` aus
   `.env` unverändert in die drei Dateien oben übernehmen. Das **Datenbank-Passwort muss
   gleich bleiben**: PostgreSQL liest die Secret-Datei nur beim allerersten Start mit
   leerem Volume, danach gilt das einmal gesetzte Passwort.
2. Die drei Zeilen aus `.env` löschen.
3. `podman-compose up -d` – die Daten im Volume bleiben erhalten.

## Starten

```
podman-compose up -d
```

Baut das Web-Image beim allerersten Start automatisch aus dem lokalen Quellcode
(`Containerfile`) und startet zusätzlich einen PostgreSQL-Container und den HTTPS-Proxy.
Danach ist die Web-Oberfläche im lokalen Netzwerk unter `https://<IP-des-Rechners>:5443`
erreichbar, auf dem Rechner selbst unter `https://localhost:5443`. Der Port 5000 des
Web-Dienstes ist von außen **nicht** mehr erreichbar (nur im internen Compose-Netz). Die
Web-Version läuft weiterhin nur im lokalen Vereins-Netzwerk am Prüfungstag, nicht öffentlich
aus dem Internet.

- **Etwas Geduld beim Start:** `podman-compose up -d` kehrt zurück, bevor alles bereit ist.
  Der Proxy wartet, bis die Web-Version läuft, und ist erst nach etwa 30 Sekunden (beim ersten
  Bau des Images länger) bereit. Antwortet die Seite noch nicht, kurz warten und neu laden;
  `podman ps` zeigt „healthy“, sobald alles läuft.
- **Rote Zeilen in Windows PowerShell 5.1:** `podman-compose` und `podman` schreiben auch normale
  Fortschrittsmeldungen in den Fehlerkanal. Leitet man ihn um (z. B. `podman logs … 2>&1`), zeigt
  PowerShell 5.1 diese Zeilen rot als „NativeCommandError“, obwohl nichts schiefgegangen ist. Entscheidend ist, ob die Container
  danach laufen (`podman ps`).
- **Anderer Port als 5443:** In `compose.yaml` beim Dienst `proxy` die Zeile `"5443:8443"`
  ändern, z. B. in `"6443:8443"` (nur die Zahl vor dem Doppelpunkt), dann `podman-compose up -d`.
  Das Zertifikat bleibt gültig (es gilt für den Rechnernamen, nicht für den Port); im Browser und
  im Desktop-Programm dann `https://localhost:6443` bzw. `https://<IP-des-Rechners>:6443`
  verwenden. Läuft auf dem Rechner schon ein PostgreSQL, beim Dienst `db` in der Zeile
  `"127.0.0.1:5432:5432"` die **mittlere** Zahl ändern (z. B. `"127.0.0.1:6432:5432"`) und dann auch
  in `SHS_POSTGRES_DSN` für `sync_termin.py` (siehe „Termin veröffentlichen“) `localhost:6432`
  statt `localhost:5432` verwenden. Wer die Dateien einer neuen Version übernimmt, muss eine
  solche Änderung in `compose.yaml` danach erneut eintragen.

## HTTPS und Zertifikat

Seit der Desktop-Anbindung (das Desktop-Programm veröffentlicht Termine und holt Ergebnisse
über die Schnittstelle unter `/api/`, Anmeldung mit dem Web-Administrator-Konto) ist HTTPS
Pflicht. Davor steht der Proxy Caddy (Dienst `proxy` in `compose.yaml`, Einstellungen in der
`Caddyfile`). Er nutzt ein **langlebiges, selbst signiertes Zertifikat**, das einmal erzeugt
wird. Bewusst kein „tls internal“ von Caddy: das stellt kurzlebige Zertifikate aus und
erneuert sie laufend, der vom Desktop festgehaltene Fingerabdruck (Zertifikats-Pinning)
würde dann ständig ungültig.

**Ablauf (einmalig):**

1. Zertifikat erzeugen (PowerShell, im Projektordner):
   ```
   powershell -ExecutionPolicy Bypass -File tools\zertifikat_erzeugen.ps1
   ```
   Das Skript schreibt `secrets/tls/zertifikat.pem` und `secrets/tls/schluessel.pem` (10 Jahre
   gültig, Namen `localhost`, `127.0.0.1`, `::1` und der Rechnername; weitere Namen oder die
   IP im Vereinsnetz mit `-Namen 192.168.1.20`). Es braucht `openssl` (das von Git für
   Windows mitgelieferte wird gefunden), sonst nutzt es einen kurzlebigen Container. Ein
   vorhandenes Zertifikat überschreibt es nie; neu erzeugen nur mit `-Erneuern`.
2. Den ausgegebenen **SHA-256-Fingerabdruck notieren** (steht auch in
   `secrets/tls/fingerabdruck.txt`). Der private Schlüssel bleibt in `secrets/` (steht in
   `.gitignore`) und wird nicht weitergegeben. Unter Linux wie bei den anderen Geheimnissen
   `chmod 644 secrets/tls/*.pem` (der Proxy läuft ohne Capabilities).
3. `podman-compose up -d`, dann im Browser `https://localhost:5443` öffnen. Der Browser
   warnt **einmalig**, weil das Zertifikat selbst signiert ist; die Ausnahme für diese Seite
   bestätigen. Es ist kein HSTS gesetzt, die Ausnahme bleibt jederzeit möglich. So sieht die
   Warnung aus und so bestätigt man sie:
   - **Microsoft Edge / Google Chrome:** „Ihre Verbindung ist nicht privat“ bzw. „Dies ist keine
     sichere Verbindung“ (`NET::ERR_CERT_AUTHORITY_INVALID`) → **„Erweitert“** →
     **„Weiter zu localhost (unsicher)“**.
   - **Firefox:** „Warnung: Mögliches Sicherheitsrisiko erkannt“ → **„Erweitert…“** →
     **„Risiko akzeptieren und fortfahren“**.
   - **Safari (iPad/iPhone/Mac):** „Diese Verbindung ist nicht privat“ → **„Details einblenden“**
     → **„diese Website besuchen“** und noch einmal bestätigen.

   Wer sichergehen will, vergleicht vorher den Fingerabdruck: In Edge/Chrome über
   **„Nicht sicher“** links in der Adressleiste → Zertifikat → **SHA-256-Fingerabdruck**; er muss
   mit dem notierten übereinstimmen (der Browser trennt die Zweierblöcke mit Leerzeichen statt
   Doppelpunkten). Auf jedem Gerät (Tablets der Richter) erscheint die Warnung
   einmal; „http://“ statt „https://“ funktioniert nicht (der Server antwortet dann mit einem Fehler).
4. Im Desktop-Programm beim ersten Verbinden den angezeigten Fingerabdruck mit dem notierten
   vergleichen und bestätigen. Er ändert sich nur, wenn ein neues Zertifikat erzeugt wird.

Das Session-Cookie der Web-Oberfläche trägt das Secure-Flag (Umgebungsvariable
`SHS_WEB_COOKIE_SECURE`, in `compose.yaml` auf `1`). Der lokale Entwicklungsserver
(`python app_web.py`, ohne Proxy, über http) schaltet es von selbst aus.

**Schnittstelle für das Desktop-Programm:** `POST /api/login` (JSON mit Benutzername und
Passwort eines Administrator-Kontos) liefert ein 8 Stunden gültiges Token; die weiteren
Aufrufe tragen es als `Authorization: Bearer <Token>`. Je Benutzername und je Client-IP sind
10 Fehlversuche in 15 Minuten erlaubt, danach antwortet der Server mit 429. Die genauen
Routen und Felder stehen in `Architektur.md`, Abschnitt „API für den Desktop“.

Das Image enthält seit 18.11.2026 auch `pdf_export.py`, `lr_abrechnung.py`, die Schriften aus `fonts/`
und `reportlab` (für „Benutzte Bögen als PDF“ in der Ergebnistabelle); kein Qt, kein PySide6.

Nach einer Code-Änderung an `db.py`/`app_web.py` neu bauen:

```
podman-compose up --build -d
```

Um stattdessen das über GitHub Actions veröffentlichte Image zu verwenden (siehe unten,
„Versionsnummer & Releases“), statt selbst zu bauen:

```
podman-compose pull
podman-compose up -d
```

`compose.yaml` nennt dafür die feste Version (`shs-web:X.Y.Z`), nicht `latest`. Ein `pull`
holt also genau das Image, das zur Compose-Datei passt.

## Versionen

Seit H-2 (05.10.2026) sind alle Images fest vorgegeben, damit sich beim Bauen oder Ziehen
nichts unbemerkt ändert:

- **Web-Image:** `ghcr.io/mbruver-source/shs-web:X.Y.Z` in `compose.yaml`. `bump_version.py`
  zieht die Nummer bei jedem Build mit. Eine andere Version (oder `latest`) lässt sich über
  `SHS_WEB_IMAGE` in `.env` wählen.
- **Basis-Image** `python:3.11.x-slim` im `Containerfile`, **`postgres:16.x`** und
  **`caddy:2.x`** (HTTPS-Proxy) in `compose.yaml` sind per Digest (`@sha256:…`) festgelegt.
  Für Sicherheitsupdates von Zeit zu Zeit nachziehen, z. B. bei einem Build:
  ```
  docker buildx imagetools inspect python:3.11-slim
  docker buildx imagetools inspect postgres:16
  docker buildx imagetools inspect caddy:2
  ```
  (oder `podman manifest inspect …`). Den angezeigten Index-Digest samt genauer Version
  eintragen. Die Hauptversion von PostgreSQL bleibt 16, ein Wechsel bräuchte ein Upgrade
  des Datenbestands.
- Die Python-Abhängigkeiten (`requirements-web.txt`, `requirements-postgres.txt`) haben
  nur Ober- und Untergrenzen. Fest ist ein Stand über das versionierte Image.

Der web-Dienst und der Proxy laufen zusätzlich gehärtet: Dateisystem nur lesbar (beim web
bis auf `/tmp`, beim Proxy bis auf `/data` und `/config`), keine Linux-Capabilities, keine
Rechteausweitung.

## Stoppen

```
podman-compose down
```

Die PostgreSQL-Daten bleiben dabei erhalten (liegen in einem eigenen, benannten Volume
`shs_postgres_daten`). **Achtung:** `podman-compose down -v` löscht dieses Volume mit –
das entspricht dem Löschen der gesamten Web-Datenbank aller bisher veröffentlichten
Termine und ist nur bewusst zu verwenden.

**Keine eigene Sicherung der PostgreSQL-Daten** (bewusst, Entscheidung 05.10.2026):
Maßgeblich ist die Termin-Datei der Desktop-Version. Pro Termin deshalb möglichst zeitnah
`sync_termin.py import` ausführen (siehe unten), damit die Ergebnisse in der gewohnten,
per ZIP gesicherten `.sqlite`-Datei landen.

## Benutzerkonten

Anmeldung an der Web-Oberfläche läuft über echte Benutzerkonten (Benutzername/Passwort),
nicht mehr über einen gemeinsamen Zugangscode je Termin - bewusst so umgestellt, damit die
Web-Version am Prüfungstag unabhängig vom "Windows-Team" nutzbar ist. Zwei Rollen (siehe
db.py, Abschnitt "Benutzerkonten der Web-Version", und app_web.py):

- **Administrator**: richtet sich beim allerersten Aufruf von `https://<Rechner-IP>:5443`
  selbst mit einem frei gewählten Benutzernamen/Passwort ein ("Ersteinrichtung" -
  erscheint nur, solange noch kein Administrator existiert). Dabei wird zusätzlich der
  Einrichtungs-Code aus `secrets/admin_setup_code.txt` abgefragt, damit nicht jeder im
  Vereinsnetz, der die Seite zuerst aufruft, den Administrator anlegen kann; ist kein
  Code gesetzt (z. B. beim lokalen Start von `app_web.py` ohne diese Umgebungsvariable),
  bleibt die Ersteinrichtung gesperrt. Kann danach unter „Benutzer“ in der Kopfzeile
  weitere Konten anlegen/löschen.
- **Nur Eintragen**: für Helfer/Richter, dürfen ausschließlich Ergebnisse eintragen,
  keine Benutzerverwaltung.

Eine Anmeldung bleibt höchstens 12 Stunden ohne Aktivität gültig (danach erneut
anmelden); „Abmelden“ beendet sie sofort im jeweiligen Browser.

Weil Konten global (nicht mehr an einen einzelnen Termin gebunden) sind, wählt jeder
Nutzer nach dem Login zusätzlich aus, mit welchem gerade veröffentlichten Termin er
arbeiten möchte - wird automatisch übersprungen, wenn genau ein Termin offen ist (der
übliche Fall am Prüfungstag).

## Termin veröffentlichen

Ein Termin entsteht weiterhin über `sync_termin.py` (läuft direkt auf diesem Rechner,
nicht im Container) - dieser Schritt ist von den Benutzerkonten oben unabhängig. Einmalige
Einrichtung, danach genügt Schritt 3 pro Termin:

1. **Einmalig:** `psycopg2` (den PostgreSQL-Treiber) im selben Python installieren, mit
   dem auch `app.py`/`build_installer.bat` laufen:
   ```
   pip install -r requirements-postgres.txt
   ```
2. **Einmalig:** DSN ohne Passwort setzen (Vorgaben: Benutzer `shs`, Datenbank `shs`).
   `localhost:5432` funktioniert, weil `compose.yaml` den Datenbank-Port gezielt nur auf
   `127.0.0.1` freigibt – erreichbar von diesem Rechner aus, nicht aus dem übrigen
   Vereinsnetz. Das Passwort kommt getrennt über `PGPASSWORD` direkt aus der Secret-Datei,
   so steht es weder in der Befehlshistorie noch in der Prozessliste (S-10, H-3). Mit
   beiden Variablen entfällt `--dsn` bei jedem Aufruf unten:
   ```
   $env:SHS_POSTGRES_DSN = "postgresql://shs@localhost:5432/shs"
   $env:PGPASSWORD = (Get-Content secrets\db_passwort.txt -Raw).Trim()
   ```
   Alternativ eine `.pgpass`-Datei (unter Windows `%APPDATA%\postgresql\pgpass.conf`).
3. **Vor jeder Prüfung:** Termin wie gewohnt in der Desktop-Version anlegen/planen,
   dann veröffentlichen:
   ```
   python sync_termin.py export <Termin-Datei>
   ```
   Der Termin erscheint danach in der Termin-Auswahl der Web-Oberfläche (siehe
   „Benutzerkonten“ oben - kein Zugangscode mehr nötig).
4. Richter melden sich mit ihrem Benutzernamen/Passwort an und tragen während der
   Prüfung über die Web-Oberfläche gleichzeitig Ergebnisse ein.
5. **Nach** der Prüfung zurückholen (Schema-Name stand in der Ausgabe von Schritt 3,
   z. B. `termin_3`):
   ```
   python sync_termin.py import <Schema-Name> <Termin-Datei>
   ```
   – danach laufen PDF-Export/Auswertung/Zeitplan wie gewohnt in der Desktop-Version
   weiter.

Der Container muss für alle Schritte bereits laufen (`podman-compose up -d`).

### Alternative: Veröffentlichen/Zurückholen über die Web-Oberfläche

Statt der Kommandozeilen-Schritte 1–3 und 5 oben kann ein **Administrator** Termine auch
direkt über die Web-Oberfläche veröffentlichen und zurückholen – bequemer, weil weder
`psycopg2` noch eine DSN auf dem eigenen Rechner eingerichtet werden müssen. Beide Wege
rufen intern dieselben Funktionen auf und können gemischt genutzt werden (z. B. per
Kommandozeile veröffentlichen, über die Web-Oberfläche zurückholen).

1. Als Administrator anmelden, oben in der Kopfzeile auf „Termine verwalten“ klicken.
2. **Veröffentlichen:** unter „Termin veröffentlichen“ die Termin-Datei (`.sqlite`) aus
   der Desktop-Version hochladen. Der Termin erscheint danach sofort in der
   Termin-Auswahl – kein Schema-Name/DSN nötig.
3. Richter melden sich mit ihrem Benutzernamen/Passwort an und tragen während der Prüfung
   über die Web-Oberfläche Ergebnisse ein (wie oben).
4. **Nach der Prüfung zurückholen:** auf der Seite „Termine verwalten“ bei dem betreffenden Termin
   dieselbe Termin-Datei erneut hochladen und auf „Ergebnisse zurückholen“ klicken. Die
   Seite zeigt eine Zusammenfassung (Teilnehmer geändert/unverändert, übersprungene/nicht
   zugeordnete Startnummern) und bietet die aktualisierte Termin-Datei zum Download an –
   dieser Link funktioniert nur einmal, danach die heruntergeladene Datei die
   ursprüngliche Termin-Datei in der Desktop-Version ersetzen. Danach laufen
   PDF-Export/Auswertung/Zeitplan dort wie gewohnt weiter.
5. **Löschen:** ein veröffentlichter Termin kann auf derselben Seite über „Löschen“
   entfernt werden (z. B. nach einem Versehen beim Veröffentlichen) – endgültig, die
   Web-Daten dieses Termins sind danach weg (die lokale Termin-Datei ist davon nicht
   betroffen).

## Versionsnummer & Releases

Container-Image und Windows-Installer tragen nach einem Release **dieselbe
Versionsnummer** – beide werden vom selben Versions-Tag ausgelöst und lesen dieselbe
`version.txt` (die alleinige Quelle der aktuellen Nummer, siehe `bump_version.py`/
README_INSTALLER.md):

```
python bump_version.py                 # Versionsnummer erhöhen
python tools/handbuch_pdf.py           # PDF-Handbuch mit neuer Nummer
python tools/handbuch_pdf.py --kurzanleitung   # Kurzanleitung Installation (PDF)
git add version.txt version_info.txt version.py compose.yaml docs/HANDBUCH.md docs/HANDBUCH.pdf docs/INSTALLATION_KURZ.pdf
git commit -m "Version X.Y.Z"
git push
git tag vX.Y.Z && git push origin vX.Y.Z
```

Der Tag-Push löst automatisch **beide** Workflows aus:

- `build-installer.yml` → baut den Windows-Installer und veröffentlicht ihn als
  GitHub-Release.
- `build-container.yml` → baut dieses Image und veröffentlicht es nach
  `ghcr.io/<Repo-Besitzer>/shs-web`, getaggt sowohl mit `X.Y.Z` als auch mit `latest`.

Die aktuell laufende Version steht in der Fußzeile jeder Web-Seite (`{{ version }}` in
`templates/base.html`, aus `version.py`) – lässt sich damit am Prüfungstag leicht mit
der in der Desktop-.exe angezeigten Version vergleichen (Version-Button neben „Hilfe“).

Bei jedem normalen Push/Pull Request (nicht nur bei einem Tag) baut
`build-container.yml` das Image zusätzlich **lokal** und prüft per Smoke-Test, ob der
komplette Compose-Stack tatsächlich hochkommt und die Login-Seite antwortet – ohne
Registry-Veröffentlichung. Reine Absicherung, dass `Containerfile`/`compose.yaml` nicht
kaputtgehen, analog zu `tests.yml` für die eigentliche Testsuite.

## Betriebsort und Grenzen

- Der Container läuft am Prüfungstag entweder auf demselben Rechner wie die Desktop-Version
  (z. B. über Podman Desktop) oder auf einem anderen Gerät im selben Netz (Marco 19.10.2026).
  Das Setup ist für beide Fälle gleich, nur der Zielrechner unterscheidet sich.
- HTTPS über den vorgeschalteten Caddy-Proxy mit selbst signiertem Zertifikat (siehe
  „HTTPS und Zertifikat“). Die Web-Version bleibt für das lokale Vereins-Netzwerk gedacht,
  nicht für den Zugriff aus dem Internet.
- Die Ratenbegrenzung der API-Anmeldung zählt im Prozessspeicher und beginnt nach einem
  Neustart des Web-Containers von vorn.
