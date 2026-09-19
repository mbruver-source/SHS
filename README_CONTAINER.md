# SHS-Prüfungsprogramm – Web-Version (Podman/Container)

Diese Anleitung beschreibt, wie das Web-Backend (Ergebniseingabe für mehrere Richter
gleichzeitig am Prüfungstag, siehe `app_web.py`) als Container läuft – als Ergänzung
zur bestehenden Desktop-Version, nicht als Ersatz. Hintergrund/Architektur siehe
`Fortschritt.md` (Abschnitte zur Podman/Web-Version), Ablauf am Prüfungstag siehe unten
sowie `sync_termin.py`.

**Umfang V1 (mit dem Nutzer abgestimmt):** NUR Ergebniseingabe über einen gemeinsamen,
sechsstelligen Zugangscode je Termin. Termin anlegen, Teilnehmerverwaltung, Zeitplan und
PDF-Export bleiben Desktop-Aufgaben vor/nach dem Prüfungstag.

## Voraussetzungen

1. [Podman](https://podman.io/) – unter Windows am einfachsten über
   [Podman Desktop](https://podman-desktop.io/) (richtet im Hintergrund eine
   WSL2-Umgebung ein, in der die Container tatsächlich laufen).
2. `podman-compose` (wird von Podman Desktop meist mitgebracht; falls nicht:
   `pip install podman-compose`). Alternativ funktioniert auch `docker compose`
   unverändert mit denselben Dateien, falls stattdessen Docker verwendet wird.

## Einrichtung (einmalig)

1. `.env.example` nach `.env` kopieren und die Werte eintragen (Datenbank-Passwort,
   Session-Schlüssel – siehe Kommentare in `.env.example`, insbesondere den Befehl zum
   Erzeugen des Session-Schlüssels). `.env` **nicht** committen (steht in `.gitignore`).

   ```
   cp .env.example .env
   ```

## Starten

```
podman-compose up -d
```

Baut das Web-Image beim allerersten Start automatisch aus dem lokalen Quellcode
(`Containerfile`) und startet zusätzlich einen PostgreSQL-Container. Danach ist die
Web-Oberfläche im lokalen Netzwerk unter `http://<IP-des-Rechners>:5000` erreichbar
(bewusst kein HTTPS – siehe Deployment-Annahme im Modul-Docstring von `app_web.py`:
läuft nur im lokalen Vereins-Netzwerk am Prüfungstag, nicht öffentlich aus dem
Internet).

Nach einer Code-Änderung an `db.py`/`app_web.py` neu bauen:

```
podman-compose up --build -d
```

Um stattdessen das zuletzt über GitHub Actions veröffentlichte Image zu verwenden
(siehe unten, „Versionsnummer & Releases“), statt selbst zu bauen:

```
podman-compose pull
podman-compose up -d
```

## Stoppen

```
podman-compose down
```

Die PostgreSQL-Daten bleiben dabei erhalten (liegen in einem eigenen, benannten Volume
`shs_postgres_daten`). **Achtung:** `podman-compose down -v` löscht dieses Volume mit –
das entspricht dem Löschen der gesamten Web-Datenbank aller bisher veröffentlichten
Termine und ist nur bewusst zu verwenden.

**Noch keine Backup-Strategie für diese PostgreSQL-Daten** (siehe „Noch offen“ in
`Fortschritt.md`) – die bestehende ZIP-Datensicherung der Desktop-Version sichert nur
`.sqlite`-Dateien. Solange das nicht nachgerüstet ist: pro Termin möglichst zeitnah
`sync_termin.py import` ausführen (siehe unten), damit die Ergebnisse auch in der
gewohnten, per ZIP gesicherten `.sqlite`-Datei landen.

## Ablauf am Prüfungstag

Wie in `Fortschritt.md` beschrieben – der Container muss dafür bereits laufen
(`podman-compose up -d`):

1. Termin wie bisher in der Desktop-Version anlegen/planen.
2. **Vor** der Prüfung veröffentlichen:
   `python sync_termin.py export <Termin-Datei> --dsn <Postgres-DSN>`
   (DSN wie in `.env` – z. B. `postgresql://shs:<Passwort>@localhost:5432/shs`, falls
   der Container auf demselben Rechner läuft). Gibt den Zugangscode für die Richter aus.
3. Richter tragen während der Prüfung über die Web-Oberfläche Ergebnisse ein.
4. **Nach** der Prüfung zurückholen:
   `python sync_termin.py import <Schema-Name> <Termin-Datei> --dsn <Postgres-DSN>`
   – danach laufen PDF-Export/Auswertung/Zeitplan wie gewohnt in der Desktop-Version
   weiter.

## Versionsnummer & Releases

Container-Image und Windows-Installer tragen nach einem Release **dieselbe
Versionsnummer** – beide werden vom selben Versions-Tag ausgelöst und lesen dieselbe
`version.txt` (die alleinige Quelle der aktuellen Nummer, siehe `bump_version.py`/
README_INSTALLER.md):

```
python bump_version.py                 # Versionsnummer erhöhen
git add version.txt version_info.txt version.py
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

## Noch offen

- Wo der Container am Prüfungstag tatsächlich läuft (derselbe Windows-Laptop wie die
  Desktop-Version über Podman Desktop, oder ein separates Gerät im Vereinsnetz) ist
  bewusst noch nicht endgültig entschieden – dieses Setup funktioniert für beide Fälle
  unverändert, nur der Zielrechner unterscheidet sich.
- Ein echter End-zu-Ende-Testlauf beim Nutzer (mehrere Geräte gleichzeitig im
  Vereins-WLAN gegen einen echten PostgreSQL-Server) steht noch aus.
- PostgreSQL-Backup-Strategie (siehe oben) fehlt noch.
- Kein Reverse-Proxy/HTTPS (bewusst, siehe Deployment-Annahme oben) – bleibt so, solange
  die Web-Version nur im lokalen Vereins-Netzwerk läuft.
