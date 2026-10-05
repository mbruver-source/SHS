#!/usr/bin/env python3
"""
Kommandozeilen-Werkzeug zum Austausch EINES Termins zwischen der lokalen
SQLite-Desktop-Datei und der gemeinsam genutzten PostgreSQL-Datenbank der geplanten
Web-Version (V1: nur Ergebniseingabe) - siehe db.exportiere_termin_nach_postgres()/
db.importiere_ergebnisse_aus_postgres() für die eigentliche Logik sowie app_web.py für
den Web-Server selbst.

Ablauf am Prüfungstag:

  1. Termin wie bisher in der Desktop-Version anlegen und vorbereiten (Teilnehmer,
     Zeitplan, ...).
  2. VOR der Prüfung: `python sync_termin.py export <Termin-Datei> --dsn <Postgres-DSN>`
     veröffentlicht den Termin als eigenen PostgreSQL-Termin - er taucht danach in der
     Termin-Auswahl der Web-Oberfläche auf (siehe unten, kein Zugangscode mehr nötig: der
     Login läuft über die Benutzerkonten, die der Administrator einmalig einrichtet bzw.
     unter "Benutzer verwalten" anlegt).
  3. Die Richter melden sich mit ihrem Benutzernamen/Passwort an der Web-Oberfläche
     (app_web.py) an, wählen (falls mehr als ein Termin offen ist) den richtigen Termin
     aus und tragen währenddessen gleichzeitig Ergebnisse ein.
  4. NACH der Prüfung: `python sync_termin.py import <Schema-Name> <Termin-Datei>
     --dsn <Postgres-DSN>` holt die eingetragenen Ergebnisse zurück in dieselbe
     Termin-Datei (Zuordnung über die Startnummer) - danach laufen
     PDF-Export/Auswertung/Zeitplan wie gewohnt in der Desktop-Version weiter.

Beispiele (empfohlen: Verbindungsstring ohne Passwort über die Umgebungsvariable
SHS_POSTGRES_DSN, das Passwort getrennt über PGPASSWORD - siehe README_CONTAINER.md):
  Windows (PowerShell):  $env:SHS_POSTGRES_DSN = "postgresql://shs@localhost:5432/shs"
                         $env:PGPASSWORD = (Get-Content secrets/db_passwort.txt -Raw).Trim()
  Linux/macOS:           export SHS_POSTGRES_DSN="postgresql://shs@localhost:5432/shs"
                         export PGPASSWORD="$(cat secrets/db_passwort.txt)"
  python sync_termin.py export Herbstpruefung_2026.sqlite
  python sync_termin.py import termin_3 Herbstpruefung_2026.sqlite

--dsn ist weiterhin möglich, z. B. --dsn "postgresql://user@host/db" mit dem Passwort in
PGPASSWORD bzw. einer .pgpass-Datei. Sicherheitsprüfung 03.10.2026, S-10: Ein PASSWORT direkt
in --dsn ist für andere Benutzer desselben Rechners in der Prozessliste sichtbar und landet in
der Befehlshistorie - das Werkzeug warnt dann.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from urllib.parse import parse_qs, urlsplit

import db


def dsn_enthaelt_passwort(dsn: str) -> bool:
    """S-10: True, wenn der Verbindungsstring ein Passwort enthält - als URL
    (postgresql://user:passwort@host/db) oder als Schlüssel-Wert-Paar (password=...)."""
    if "://" in dsn:
        try:
            teile = urlsplit(dsn)
            # libpq erlaubt das Passwort auch als Parameter: postgresql://u@h/db?password=...
            return bool(teile.password) or "password" in {k.lower() for k in parse_qs(teile.query)}
        except ValueError:
            return False
    return re.search(r"(^|\s)password\s*=", dsn, re.IGNORECASE) is not None


def _postgres_dsn(uebergeben: str | None) -> str:
    if uebergeben and dsn_enthaelt_passwort(uebergeben):
        print(
            "Hinweis: Das Passwort in --dsn ist für andere Benutzer dieses Rechners in der "
            "Prozessliste sichtbar und steht in der Befehlshistorie. Besser den "
            "Verbindungsstring über die Umgebungsvariable SHS_POSTGRES_DSN übergeben "
            "(siehe python sync_termin.py --help).",
            file=sys.stderr,
        )
    dsn = uebergeben or os.environ.get("SHS_POSTGRES_DSN")
    if not dsn:
        print(
            "Kein PostgreSQL-Verbindungsstring angegeben (weder als Argument noch über "
            "SHS_POSTGRES_DSN).",
            file=sys.stderr,
        )
        sys.exit(1)
    return dsn


def _export(sqlite_pfad: str, postgres_dsn: str | None) -> None:
    dsn = _postgres_dsn(postgres_dsn)
    sqlite_conn = db.init_db(sqlite_pfad)
    postgres_conn = db.verbinde_postgres_server(dsn)
    try:
        termin = db.exportiere_termin_nach_postgres(sqlite_conn, postgres_conn)
    finally:
        sqlite_conn.close()
        postgres_conn.close()

    print(f"Termin veröffentlicht: Schema '{termin.schema_name}', {termin.anzahl_teilnehmer} Teilnehmer.")
    print()
    print("  Ab sofort in der Termin-Auswahl der Web-Oberfläche wählbar (nach Anmeldung")
    print("  mit einem Benutzerkonto - siehe README_CONTAINER.md, 'Benutzerkonten').")
    print()
    print(f"Zum Zurückholen der Ergebnisse nach der Prüfung:")
    print(f"  python sync_termin.py import {termin.schema_name} {sqlite_pfad} --dsn <Postgres-DSN>")


def _import(postgres_dsn: str | None, schema_name: str, sqlite_pfad: str) -> None:
    dsn = _postgres_dsn(postgres_dsn)
    postgres_conn = db.verbinde_postgres_server(dsn)
    sqlite_conn = db.init_db(sqlite_pfad)
    try:
        bericht = db.importiere_ergebnisse_aus_postgres(postgres_conn, schema_name, sqlite_conn)
    finally:
        postgres_conn.close()
        sqlite_conn.close()

    print(f"{bericht.aktualisiert} Teilnehmer mit Ergebnissen aktualisiert.")
    if bericht.ohne_startnummer_uebersprungen:
        print(
            "Übersprungen (keine Startnummer in der Termin-Datei, nicht zuordenbar): "
            + ", ".join(bericht.ohne_startnummer_uebersprungen)
        )
    if bericht.nicht_gefunden:
        print(
            "Startnummern aus der Web-Erfassung ohne Entsprechung in der Termin-Datei: "
            + ", ".join(bericht.nicht_gefunden)
        )
    if bericht.fehler:
        print(
            "Fehler beim Übertragen (bitte für diese Teilnehmer manuell prüfen): "
            + ", ".join(bericht.fehler)
        )
    if bericht.abweichungen:
        print(
            "NICHT übernommen - Startnummer gehört in der Termin-Datei zu einem anderen "
            "Teilnehmer (bitte manuell prüfen/nachtragen): " + "; ".join(bericht.abweichungen)
        )
    if bericht.im_web_leer:
        # Codeprüfung 22.09., G2
        print(
            "Hinweis - im Web leer, Wert der Termin-Datei beibehalten (bitte prüfen, ob das "
            "so gewollt ist): " + "; ".join(bericht.im_web_leer)
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    unterbefehle = parser.add_subparsers(dest="befehl", required=True)

    export_parser = unterbefehle.add_parser(
        "export", help="Termin aus einer .sqlite-Datei nach PostgreSQL veröffentlichen"
    )
    export_parser.add_argument("sqlite_pfad", help="Pfad zur bestehenden Termin-Datei (.sqlite)")
    export_parser.add_argument(
        "--dsn", dest="postgres_dsn", help="PostgreSQL-Verbindungsstring (sonst SHS_POSTGRES_DSN)"
    )

    import_parser = unterbefehle.add_parser(
        "import", help="Ergebnisse aus PostgreSQL zurück in eine .sqlite-Datei holen"
    )
    import_parser.add_argument("schema_name", help="Schema-Name des Termins, z. B. termin_3")
    import_parser.add_argument("sqlite_pfad", help="Pfad zur Termin-Datei (.sqlite), die aktualisiert wird")
    import_parser.add_argument(
        "--dsn", dest="postgres_dsn", help="PostgreSQL-Verbindungsstring (sonst SHS_POSTGRES_DSN)"
    )

    args = parser.parse_args()
    if args.befehl == "export":
        _export(args.sqlite_pfad, args.postgres_dsn)
    else:
        _import(args.postgres_dsn, args.schema_name, args.sqlite_pfad)


if __name__ == "__main__":
    main()
