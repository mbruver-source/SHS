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

FROM python:3.11-slim

WORKDIR /app

# Erst nur die Abhängigkeiten kopieren (eigener Layer) - bei einer reinen Code-Änderung
# an db.py/app_web.py muss `pip install` dadurch nicht jedes Mal neu laufen.
COPY requirements-postgres.txt requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements-postgres.txt -r requirements-web.txt

# version.py (nicht version.txt/version_info.txt - die dienen nur dem PyInstaller-Build
# der Desktop-.exe, siehe bump_version.py) liefert dieselbe Versionsnummer wie die
# Desktop-Version, sichtbar in der Fußzeile jeder Web-Seite (siehe templates/base.html).
COPY db.py shs_core.py app_web.py version.py ./
COPY templates/ ./templates/

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
