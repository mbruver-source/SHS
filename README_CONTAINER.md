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

1. `.env.example` nach `.env` kopieren und die Werte eintragen (Datenbank-Passwort,
   Session-Schlüssel, Einrichtungs-Code `SHS_ADMIN_SETUP_CODE` für den ersten
   Administrator – siehe Kommentare in `.env.example`, insbesondere die Befehle zum
   Erzeugen von Session-Schlüssel und Einrichtungs-Code). `.env` **nicht** committen
   (steht in `.gitignore`).

   **Update einer bestehenden Installation (ab der Version nach 1.0.28):**
   `SHS_ADMIN_SETUP_CODE` ist jetzt ein Pflichtwert – ohne ihn startet `compose up` nicht,
   auch wenn bereits ein Administrator existiert. Einfach einen Code erzeugen und als
   `SHS_ADMIN_SETUP_CODE=...` in die vorhandene `.env` eintragen.

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

## Benutzerkonten

Anmeldung an der Web-Oberfläche läuft über echte Benutzerkonten (Benutzername/Passwort),
nicht mehr über einen gemeinsamen Zugangscode je Termin - bewusst so umgestellt, damit die
Web-Version am Prüfungstag unabhängig vom "Windows-Team" nutzbar ist. Zwei Rollen (siehe
db.py, Abschnitt "Benutzerkonten der Web-Version", und app_web.py):

- **Administrator**: richtet sich beim allerersten Aufruf von `http://<Rechner-IP>:5000`
  selbst mit einem frei gewählten Benutzernamen/Passwort ein ("Ersteinrichtung" -
  erscheint nur, solange noch kein Administrator existiert). Dabei wird zusätzlich der
  Einrichtungs-Code aus `SHS_ADMIN_SETUP_CODE` (`.env`) abgefragt, damit nicht jeder im
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
2. **Einmalig:** DSN aus den Werten in `.env` zusammensetzen. Mit den Vorgaben aus
   `.env.example` (Benutzer `shs`, Datenbank `shs`) und dem selbst gesetzten Passwort:
   ```
   postgresql://shs:<dein SHS_DB_PASSWORD aus .env>@localhost:5432/shs
   ```
   (`localhost:5432` funktioniert, weil `compose.yaml` den Datenbank-Port gezielt nur
   auf `127.0.0.1` freigibt – erreichbar von diesem Rechner aus, nicht aus dem übrigen
   Vereinsnetz.) Am einfachsten als Umgebungsvariable setzen, dann muss `--dsn` bei
   jedem Aufruf unten entfallen:
   ```
   $env:SHS_POSTGRES_DSN = "postgresql://shs:<Passwort>@localhost:5432/shs"
   ```
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

1. Als Administrator anmelden, oben in der Kopfzeile auf „Termine“ klicken.
2. **Veröffentlichen:** unter „Termin veröffentlichen“ die Termin-Datei (`.sqlite`) aus
   der Desktop-Version hochladen. Der Termin erscheint danach sofort in der
   Termin-Auswahl – kein Schema-Name/DSN nötig.
3. Richter melden sich mit ihrem Benutzernamen/Passwort an und tragen während der Prüfung
   über die Web-Oberfläche Ergebnisse ein (wie oben).
4. **Nach der Prüfung zurückholen:** auf der „Termine“-Seite bei dem betreffenden Termin
   dieselbe Termin-Datei erneut hochladen und auf „Ergebnisse zurückholen“ klicken. Die
   Seite zeigt eine Zusammenfassung (Anzahl aktualisierter Teilnehmer, übersprungene/nicht
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
git add version.txt version_info.txt version.py docs/HANDBUCH.md docs/HANDBUCH.pdf
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
