# "Containerfile" ist der von Podman bevorzugte Name (inhaltlich identisch zu einem
# Dockerfile) - funktioniert unverändert auch mit `docker build`/`docker compose`.
#
# Baut NUR das Web-Backend (app_web.py, V1: Ergebniseingabe über einen gemeinsamen
# Zugangscode je Termin) - siehe README_CONTAINER.md für den Gesamtablauf
# (compose.yaml, Versionsnummer, Prüfungstag) und Fortschritt.md für den Architektur-
# Hintergrund (Weg B: ein PostgreSQL-Schema je Termin). Enthält bewusst NICHT die
# SQLite-Desktop-Version (PySide6 aus requirements.txt wird hier nicht installiert,
# app.py/pdf_export.py werden nicht mit hineinkopiert) - die beiden Varianten bleiben
# unabhängig baubar, siehe Kommentar in requirements-postgres.txt.

# Feste Basis per Digest (Sicherheitshinweis H-2, Marco 05.10.2026): entspricht
# python:3.11.17-slim, Stand 05.10.2026. Nachziehen: siehe README_CONTAINER.md, "Versionen".
FROM python:3.11.17-slim@sha256:6f31d6e9ba2b0a787a3f81c37b004155b87b9efa1b771182bd550c1615745be5

WORKDIR /app

# Erst nur die Abhängigkeiten kopieren (eigener Layer) - bei einer reinen Code-Änderung
# an db.py (und den db_*.py)/app_web.py muss `pip install` dadurch nicht jedes Mal neu laufen.
COPY requirements-postgres.txt requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements-postgres.txt -r requirements-web.txt

# Lizenzen der Fremdkomponenten (Python, Flask, waitress, psycopg2 ...), passend zu den eben
# installierten Paketen (Marco 25.10.2026). Liegt danach unter /app/THIRD_PARTY_LICENSES.txt.
# Dazu die Lizenz der Tabler Icons (Haken in der Teilnehmerliste, siehe tools/drittlizenzen.py).
COPY tools/drittlizenzen.py ./tools/
COPY symbole/LICENSE-Tabler.txt ./symbole/
RUN python tools/drittlizenzen.py web THIRD_PARTY_LICENSES.txt && rm -r tools symbole

# version.py (nicht version.txt/version_info.txt - die dienen nur dem PyInstaller-Build
# der Desktop-.exe, siehe bump_version.py) liefert dieselbe Versionsnummer wie die
# Desktop-Version, sichtbar in der Fußzeile jeder Web-Seite (siehe templates/base.html).
# db.py ist seit 11.11.2026 eine Fassade über die Schichtmodule db_*.py (Liste ausdrücklich,
# damit db_import.py/db_sicherung.py - Desktop, brauchen pypdf/pyzipper - nicht mitkommen).
COPY db.py db_verbindung.py db_stamm.py db_ergebnisse.py db_zeitplan.py db_termine.py db_web.py db_sync.py ./
COPY shs_core.py app_web.py version.py ./
COPY templates/ ./templates/
# Bilder der Web-Oberfläche (Beagle im Kopf, templates/base.html), ausgeliefert von Flask
# unter /static (Marco 01.11.2026, Erscheinungsbild „Beagle“).
COPY static/ ./static/
# MIT-Lizenz des Programms; die Seite /lizenzen (app_web.py) zeigt sie zusammen mit
# THIRD_PARTY_LICENSES.txt an (Marco 01.11.2026).
COPY LICENSE ./

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Ohne root laufen (Podman ist im Einsatz meist ohnehin schon rootless, hier zusätzlich
# auch innerhalb des Containers ohne Root-Rechte).
RUN useradd --create-home --shell /usr/sbin/nologin shs
USER shs

EXPOSE 5000

# waitress statt des eingebauten Flask-Entwicklungsservers (app.run() in app_web.py ist
# ausdrücklich nur für lokale Tests gedacht, siehe dortiger Kommentar) - "app_web:app"
# verweist auf das fertige Flask-Objekt "app" im Modul app_web.py.
CMD ["waitress-serve", "--host=0.0.0.0", "--port=5000", "app_web:app"]
