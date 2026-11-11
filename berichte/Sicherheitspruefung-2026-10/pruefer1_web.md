# Prüfer 1 – Web und Server

Geprüft (statische Codeprüfung, gezielt gelesen): `app_web.py` komplett, Templates (Stichproben + Suche nach `|safe`/Skripten), `db.py` Abschnitte Web-Benutzer, Schema-Namen/search_path, Postgres-Verbindung, `kopiere_termin_daten`, `importiere_ergebnisse_nach_startnummer`, `Containerfile`, `compose.yaml`, `.env.example`, `.containerignore`, README_CONTAINER.md (Stichwortsuche). Keine Laufzeittests, alle "Lokal nachvollzogen" daher "nein (Codeanalyse)".

## Zusammenfassung (schwerster Fund zuerst)
Kein kritischer oder hoher Fund. Die Grundabsicherung ist solide (CSRF-Token auf allen POST, Konto wird bei jeder Anfrage gegen die Datenbank re-validiert, Schema-Namen per Muster `termin_<Zahl>` + Registry-Abgleich, parametrisierte SQL, Jinja-Autoescape ohne `|safe`, Upload-Temp-Dateien mit mkstemp, Download-Token zufällig und einmalig).
Offen bleiben vor allem Konfigurations- und Härtungsthemen:
1. Platzhalterwerte aus `.env.example` werden akzeptiert (Session-Schlüssel, Setup-Code, DB-Passwort) – mittel.
2. Klartext-HTTP im Vereinsnetz (Passwörter, Cookie) und Port 5000 auf allen Schnittstellen – mittel (bewusste Entscheidung laut Doku, aber als Restrisiko zu nennen).
3. Web-Dienst nutzt das Datenbank-Eigentümerkonto (Superuser des Containers) – gering.
4. Keine Sicherheits-Header / Clickjacking-Schutz, Logout per GET – gering.
5. Kleinere Hinweise (Temp-Datei-Leck im Fehlerpfad, ungepinnte Images, `:latest`).

## Funde

### P1-1: Platzhalter aus `.env.example` werden unverändert akzeptiert
- Schwere: mittel
- Stelle: `.env.example:8,16,34`; `compose.yaml:44-49` (`:?` prüft nur "nicht leer"); `app_web.py:153,202`
- Voraussetzungen und Szenario: Wer `.env.example` nach `.env` kopiert und nur teilweise anpasst (z. B. `SHS_WEB_SECRET_KEY=bitte-hier-einen-erzeugten-schluessel-eintragen`), startet erfolgreich mit einem öffentlich im Repo stehenden Session-Schlüssel. Ein Angreifer im Vereinsnetz kann dann ein Session-Cookie fälschen (`benutzername` eines existierenden Kontos, z. B. des ersten Admins – Name oft erratbar; `ist_admin` wird zwar aus der DB neu gesetzt, aber der Benutzername muss nur existieren). Folge: Übernahme eines beliebigen bestehenden Kontos, bei Admin-Name volle Adminrechte (Termine löschen, Benutzer anlegen, Daten herunterladen). Gleiches für `SHS_ADMIN_SETUP_CODE` (bekannter Platzhalter -> vor der Ersteinrichtung kann jeder den ersten Admin anlegen) und `SHS_DB_PASSWORD` (Port ist nur auf 127.0.0.1 gebunden, daher geringer).
- Lokal nachvollzogen: nein (Codeanalyse: keine Mindestlänge oder Platzhalterprüfung bei `SHS_WEB_SECRET_KEY`, `app_web.py:153`).
- Auswirkung: Kontoübernahme/Admin-Übernahme im Vereinsnetz bei Fehlkonfiguration.
- Empfehlung: In `app_web.py` beim Start verweigern (oder laut warnen), wenn `SHS_WEB_SECRET_KEY` kürzer als z. B. 32 Zeichen ist oder mit "bitte-" beginnt; analog Setup-Code. In `.env.example` Platzhalter leer lassen (`SHS_WEB_SECRET_KEY=`), sodass `compose.yaml` mit `:?` zwingend eine Eingabe erzwingt.

### P1-2: Unverschlüsseltes HTTP, Port 5000 auf allen Schnittstellen
- Schwere: mittel (für das Vereinsumfeld bewusste Entscheidung, daher nicht höher)
- Stelle: `compose.yaml:57` (`"5000:5000"`), `Containerfile:39` (`--host=0.0.0.0`), `app_web.py:165` (kein `SESSION_COOKIE_SECURE`), README_CONTAINER.md:48-49, 220
- Voraussetzungen und Szenario: Mitlesen im selben WLAN/LAN (Prüfungsgelände, Vereinsheim, ggf. Gäste-WLAN): Benutzername/Passwort und Session-Cookie gehen im Klartext über das Netz. Mit dem Cookie ist die Sitzung bis zu 12 h (bzw. bei Aktivität länger) übernehmbar; das Passwort wird zusätzlich offengelegt (Wiederverwendung).
- Lokal nachvollzogen: nein
- Auswirkung: Übernahme von Richter- und Admin-Konten durch Mithörer.
- Empfehlung: Mindestens in der Doku deutlich vor Betrieb in Gäste-/öffentlichen WLANs warnen und ein eigenes, abgeschottetes WLAN/VLAN empfehlen; optional Reverse-Proxy mit TLS (Caddy mit internem Zertifikat) als dokumentierte Variante und dann `SESSION_COOKIE_SECURE` per Umgebungsvariable schaltbar machen. Port optional an die LAN-IP des Rechners binden statt an alle Schnittstellen.

### P1-3: Web-Dienst nutzt das PostgreSQL-Eigentümerkonto
- Schwere: gering
- Stelle: `compose.yaml:44` (gleiche `SHS_DB_USER` für `POSTGRES_USER` und `SHS_POSTGRES_DSN`); `db.py` `CREATE/DROP SCHEMA`, `_setze_termin_suchpfad`
- Voraussetzungen und Szenario: Die Anwendung braucht `CREATE SCHEMA`/`DROP SCHEMA ... CASCADE` und `CREATE TABLE`, deshalb läuft alles mit dem Superuser des Containers. Eine künftige SQL-Injection oder Codeausführung im Webprozess hätte damit volle DB-Rechte (inkl. `COPY ... PROGRAM` im Container). Aktuell wurde keine Injektionsstelle gefunden (alle Werte parametrisiert, Bezeichner nur nach `fullmatch(r"termin_[0-9]+")`, `app_web.admin_termin_loeschen` und `zurueckholen` zusätzlich Registry-Abgleich).
- Lokal nachvollzogen: nein
- Auswirkung: Tiefenverteidigung fehlt, aber ohne konkreten Angriffsweg.
- Empfehlung: Optional eigene Rolle ohne Superuser (Eigentümer der Datenbank, aber nicht `SUPERUSER`) per Init-Skript; bei nur einem Container im Vereinsnetz vertretbar, als Restrisiko dokumentieren.

### P1-4: Keine Sicherheits-Header; Logout per GET; keine Cache-Kontrolle
- Schwere: gering
- Stelle: `app_web.py` (keine `after_request`-Header), `app_web.py:369` (`/logout` GET)
- Voraussetzungen und Szenario: Fehlendes `X-Frame-Options`/`frame-ancestors` erlaubt Einbettung der Admin-Seiten in einem fremden Frame (Clickjacking auf "Löschen"-Knöpfe, die per Bestätigungsdialog? – im Template nicht geprüft). Logout ist per GET auslösbar (Abmelde-CSRF, nur Ärgernis). Seiten mit Teilnehmerdaten haben keine `Cache-Control: no-store`; auf gemeinsam genutzten Geräten (Tablets der Richter) kann der Browser-Verlauf Seiten zwischenspeichern.
- Lokal nachvollzogen: nein
- Auswirkung: gering.
- Empfehlung: `after_request` mit `X-Frame-Options: DENY`, `Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'`, `X-Content-Type-Options: nosniff`, `Cache-Control: no-store` für authentifizierte Seiten; Logout als POST.

### P1-5: Temporäre Upload-Datei kann im Fehlerpfad liegen bleiben; personenbezogene Daten
- Schwere: gering
- Stelle: `app_web.py:633-664` (`admin_termin_zurueckholen`)
- Voraussetzungen und Szenario: Nach erfolgreichem `importiere_ergebnisse_aus_postgres` wird die Datei bis zum Download behalten. Tritt danach eine Ausnahme auf (z. B. `db.liste_termine_postgres` oder `render_template` in Zeile 661-664), bleibt die Datei ohne Token-Eintrag dauerhaft in `/tmp` des Containers liegen. Ebenso werden bei `init_db` nur `sqlite3.Error` abgefangen (Zeile 636); andere Ausnahmen (z. B. `UnicodeDecodeError` bei fehlerhaften Textspalten in Migrationen) lassen die Datei liegen. Die Datei enthält Teilnehmerdaten (Adresse, E-Mail, Telefon). Die 15-Minuten-Bereinigung greift nur für Einträge in `_ausstehende_downloads`. Zudem werden Download-Token beim Neustart des Containers verworfen, die Dateien in `/tmp` bleiben im Container-Dateisystem bis zur Neuerstellung.
- Lokal nachvollzogen: nein
- Auswirkung: Daten bleiben länger als gewollt im Container-Dateisystem; nur lesbar für den Containerbenutzer.
- Empfehlung: `try/finally` um den gesamten Block nach `_hochgeladene_termin_datei_speichern`, Datei nur bei erfolgreicher Registrierung des Tokens behalten; in `_bereinige_abgelaufene_downloads` zusätzlich Dateien mit Präfix im eigenen Temp-Ordner älter als 15 Minuten löschen (eigener `tempfile.mkdtemp`-Ordner mit festem Präfix).

### P1-6: Hochgeladene SQLite-Dateien werden mit `init_db` geöffnet und migriert (nur Admin)
- Schwere: Hinweis
- Stelle: `app_web.py:598,635`; `db.py:569-579`
- Voraussetzungen und Szenario: Ein Admin lädt eine von Dritten stammende `.sqlite`. `sqlite3.connect` + `executescript(SCHEMA)` + Migrationen laufen auf der Fremddatei; Trigger/Views darin könnten bei den Migrations-DML ausgeführt werden, wirken aber nur innerhalb dieser Temp-Datei (Standard-Python-SQLite ohne `load_extension`). Bösartig geformte Werte (NUL-Zeichen, falsche Typen, riesige Texte) führen zu Fehlern beim Kopieren nach PostgreSQL; `exportiere_termin_nach_postgres` räumt das teilweise angelegte Schema per kompensierendem `loesche_termin_postgres` auf, Fehler wird als 500 weitergereicht (generische Seite, kein Stacktrace, solange `debug=False`).
- Lokal nachvollzogen: nein
- Auswirkung: kein Codeausführungspfad gefunden; höchstens Abbruch/500 und Speicherverbrauch (Upload-Größe bewusst nicht beanstandet).
- Empfehlung: Optional vor `init_db` die Fremddatei mit `PRAGMA trusted_schema=OFF` und `PRAGMA integrity_check`/`quick_check` öffnen und Schema-Objekte außerhalb der erwarteten Tabellen (Trigger/Views) ablehnen; sinnvoll auch für den Desktop-Import (Prüfer Desktop informieren).

### P1-7: Containerbasis und Image-Herkunft nicht fixiert
- Schwere: Hinweis
- Stelle: `Containerfile:12` (`python:3.11-slim`), `compose.yaml:17,36` (`postgres:16`, `ghcr.io/mbruver-source/shs-web:latest`); `requirements-web.txt` nur `>=,<` Bereiche
- Voraussetzungen und Szenario: Bei jedem Build/Pull können sich Basis-Image und Abhängigkeiten ändern (Lieferkette); `:latest` des eigenen ghcr-Images wird vom Server ohne Digest-Prüfung gezogen. Kompromittierung des GitHub-Kontos/der Pipeline -> Schadcode im Vereinscontainer.
- Lokal nachvollzogen: nein
- Auswirkung: Lieferkettenrisiko, im Vereinsumfeld gering.
- Empfehlung: Image-Tags mit Digest pinnen oder bei Releases versionierte Tags (`shs-web:1.0.x`) in der README empfehlen; Lock-Datei (`pip-compile --generate-hashes`) für Web-Abhängigkeiten. Containerprofil härten: `read_only: true`, `tmpfs: /tmp`, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]` für den Dienst `web` (läuft bereits als Nicht-Root `shs`).

### P1-8: DB-Passwort im Klartext in Umgebungsvariablen; DSN mit Sonderzeichen
- Schwere: Hinweis
- Stelle: `compose.yaml:44-45`; README_CONTAINER.md:121-131 (DSN von Hand mit Passwort in `$env:`)
- Voraussetzungen und Szenario: Das DB-Passwort steht in `podman inspect` und der Shell-Historie des Admins (`$env:SHS_POSTGRES_DSN`). Passwörter mit `@`, `/`, `:` oder `%` zerstören die DSN-URL (Funktionsproblem, kann zu Fehlbedienung führen, z. B. Wechsel zu schwachem Passwort).
- Lokal nachvollzogen: nein
- Auswirkung: gering; nur lokale Nutzer des Servers.
- Empfehlung: In der README Hex-Passwort (`secrets.token_hex(16)`) empfehlen; `sync_termin.py` zusätzlich `PGPASSWORD`/`.pgpass` unterstützen.

## Ohne Befund geprüft (Stichworte)
- CSRF: `before_request` für alle POST, konstante Zeit, Token in Session, Upload-Formulare mit Token (Login-CSRF eingeschlossen). Offen nur Logout per GET (P1-4).
- Authentifizierung/Sitzung: scrypt-Hash (werkzeug), Dummy-Hash gegen Timing-Enumeration, Konto-Re-Validierung je Anfrage (gelöschte/degradierte Konten verlieren sofort Rechte), `session.clear()` beim Login (keine Session-Fixation), HttpOnly Standard, SameSite=Lax, 12 h Laufzeit. Brute-Force bewusst ausgenommen.
- Rollen: Admin-Routen alle mit `_admin_erforderlich`, Ergebnisrouten mit `_termin_erforderlich`; Nicht-Admin 403; Rolle nur aus DB.
- Zugriff auf fremde Termine/Teilnehmer: Teilnehmer-IDs nur im Schema des gewählten Termins abrufbar; `schema_name` aus Session wird per Registry und Namensmuster geprüft; `keine_teilnahme`-Teilnehmer 404. Alle Richter sehen bewusst alle veröffentlichten Termine (Designentscheidung).
- Ersteinrichtung: Setup-Code (Bytes-`compare_digest`), Race-Schutz in `admin_einrichten`; Code leer -> gesperrt.
- SQL-Injection: nur Bezeichner `termin_<Zahl>` (fullmatch) per f-String, alle Werte parametrisiert; `?`-Übersetzung ignoriert String-Literale.
- Ausgabe-Escaping: Jinja-Autoescape, kein `|safe`/`Markup`/Inline-Skript; Teilnehmer-/Importberichtsfelder werden escaped ausgegeben.
- Upload/Download: Endung `.sqlite` geprüft, `secure_filename` für Download-Namen, `mkstemp` (Rechte 0600), Token `token_urlsafe(16)`, einmalig (`pop`), 15 min Ablauf, Download nur für Admin.
- Rückhol-Import: Zuordnung per Startnummer mit Plausibilitätsprüfung (Name, Hund, Art), Schreiben nur ins Ziel; kein Schreiben außerhalb der Termin-Datei.
- Fehlermeldungen: generische Login-Meldung, kein Debug-Modus (`debug=False`), keine Stacktraces in Antworten.
- Container: Nicht-Root-Benutzer, DB-Port nur 127.0.0.1, `.containerignore` und gezieltes `COPY` (keine `.env` im Image), Pflichtvariablen mit `:?`, Healthcheck ohne Geheimnisse.

## Zählung
kritisch 0, hoch 0, mittel 2 (P1-1, P1-2), gering 3 (P1-3, P1-4, P1-5), Hinweis 3 (P1-6, P1-7, P1-8).

Bericht: C:\Users\mbruv\AppData\Local\Temp\claude\C--Users-mbruv-Documents-SHS-Pruefungsprogramm-Git\747ba2e2-5ac7-4459-b68f-11f18f9c2c8a\scratchpad\sicherheit\pruefer1_web.md
