"""
Datenschicht für das SHS-Prüfungsprogramm (Prototyp).

Entwurfsentscheidung (siehe Grobkonzept): Jede Veranstaltung/Termin ist eine
eigene, in sich abgeschlossene SQLite-Datei - die Datei selbst entspricht
also dem heutigen "eine .ods-Datei pro Prüfungstermin". Löschen eines Termins
bedeutet einfach: diese Datei löschen (kein Aufräumen über Tabellen nötig) -
das war die geforderte, gezielte Löschmöglichkeit aus Datenschutzgründen.

Enthält reine Datenhaltung + die Verbindung zur Kernlogik aus shs_core.py
(Notenberechnung, Rangbildung). Keine GUI-Abhängigkeiten - lässt sich
unabhängig von PySide6 testen.

Zweite Datenbank-Anbindung (für die geplante Podman/Web-Version mit
Mehrbenutzerzugriff): init_db_postgres() öffnet dieselbe fachliche Datenbank auf
PostgreSQL statt SQLite. Damit dafür keine zweite Fassung jeder einzelnen
Datenfunktion gepflegt werden muss, geben init_db()/init_db_postgres() jeweils ein
Objekt zurück, das dieselbe (kleine) Teilmenge der sqlite3.Connection-Schnittstelle
anbietet (execute/executescript/commit/close, '?'-Platzhalter, dict-artige Zeilen) -
siehe _PostgresConnection weiter unten. Alle Funktionen ab DISZIPLIN_SPALTEN sind
deshalb bewusst weiterhin mit `conn: sqlite3.Connection` typisiert (das ist die
Desktop-Verbindungsart, für die dieses Modul ursprünglich geschrieben wurde), obwohl sie
zur Laufzeit unverändert auch mit einer PostgreSQL-Verbindung funktionieren - dank
`from __future__ import annotations` wird diese Typisierung nicht ausgewertet, sie dient
nur der Dokumentation des ursprünglichen Anwendungsfalls.
"""

from __future__ import annotations

import datetime
import re
import secrets
import sqlite3
import zipfile
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import pyzipper

from shs_core import (
    Teilnehmerergebnis,
    berechne_rangliste,
    berechne_wertnote_dk,
    berechne_wertnote_ed,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS veranstaltung (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    verein TEXT NOT NULL,
    ort TEXT,
    datum TEXT NOT NULL,
    -- Zusätzliche Kopf-Angaben für die Statistik-PDF (siehe pdf_export.py) - alle
    -- optional, da sie oft erst im Lauf der Planung/am Prüfungstag feststehen.
    vereins_nr TEXT,
    pruefungsnummer TEXT,
    wertungsrichter_1 TEXT,
    wertungsrichter_2 TEXT,
    pruefungsleiter TEXT
);

CREATE TABLE IF NOT EXISTS teilnehmer (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nachname TEXT NOT NULL,
    vorname TEXT NOT NULL,
    verein TEXT,
    zwingername TEXT,
    rufname_hund TEXT NOT NULL,
    geschlecht TEXT CHECK (geschlecht IN ('Hündin', 'Rüde')),
    schulterhoehe_cm INTEGER,
    chip_nr TEXT,
    art TEXT NOT NULL CHECK (art IN ('ED', 'DK')),
    stufe INTEGER NOT NULL CHECK (stufe IN (1, 2, 3)),
    disziplin TEXT CHECK (disziplin IN ('Trümmerfeld', 'Flächensuche', 'Behältnisstrecke')),
    startnummer INTEGER UNIQUE,
    gegenstand_1 TEXT,
    gegenstand_2 TEXT,
    gegenstand_3 TEXT,
    -- Für welche Disziplin ist der jeweilige Gegenstand (frei wählbar, siehe
    -- gegenstand_fuer_disziplin()) hinterlegt? NULL = "frei" (keiner bestimmten Disziplin
    -- zugeordnet) - bewusst OHNE Default-Zuordnung nach Position (früher/im Original war
    -- Gegenstand 1 implizit immer Trümmerfeld usw., was nicht zuverlässig zutraf). Fließt
    -- in die Bewertungsbögen-PDF ein: bei "frei" erscheint dort keine Zuordnung zu
    -- Trümmer/Fläche/Behältnis.
    gegenstand_1_disziplin TEXT CHECK (gegenstand_1_disziplin IN ('Trümmerfeld', 'Flächensuche', 'Behältnisstrecke')),
    gegenstand_2_disziplin TEXT CHECK (gegenstand_2_disziplin IN ('Trümmerfeld', 'Flächensuche', 'Behältnisstrecke')),
    gegenstand_3_disziplin TEXT CHECK (gegenstand_3_disziplin IN ('Trümmerfeld', 'Flächensuche', 'Behältnisstrecke')),
    -- Hat der Teilnehmer die Prüfungsgebühr bereits entrichtet? Frei umschaltbar in der
    -- Teilnehmerliste, ohne den kompletten Bearbeiten-Dialog öffnen zu müssen - siehe
    -- setze_bezahlt(). Fließt auch in die "Übersicht für Prüfungsleitung"-PDF ein.
    bezahlt INTEGER NOT NULL DEFAULT 0 CHECK (bezahlt IN (0, 1)),
    -- Verwaltungs-/Kontaktdaten (alle optional, siehe TeilnehmerDialog) - "verband" meint
    -- den übergeordneten Dachverband (z.B. VDH), nicht den lokalen "verein" oben.
    verband TEXT,
    mitgliedsnummer TEXT,
    wurftag TEXT,
    strasse TEXT,
    hausnummer TEXT,
    plz TEXT,
    ort TEXT,
    email TEXT,
    telefon TEXT,
    -- bei ED ist die Disziplin Pflicht, bei DK darf sie nicht gesetzt sein
    CHECK (
        (art = 'ED' AND disziplin IS NOT NULL) OR
        (art = 'DK' AND disziplin IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS ergebnisse (
    teilnehmer_id INTEGER PRIMARY KEY REFERENCES teilnehmer(id) ON DELETE CASCADE,
    suche_truemmerfeld INTEGER CHECK (suche_truemmerfeld BETWEEN 0 AND 60),
    anzeige_truemmerfeld INTEGER CHECK (anzeige_truemmerfeld BETWEEN 0 AND 40),
    suche_flaechensuche INTEGER CHECK (suche_flaechensuche BETWEEN 0 AND 60),
    anzeige_flaechensuche INTEGER CHECK (anzeige_flaechensuche BETWEEN 0 AND 40),
    suche_behaeltnis INTEGER CHECK (suche_behaeltnis BETWEEN 0 AND 60),
    anzeige_behaeltnis INTEGER CHECK (anzeige_behaeltnis BETWEEN 0 AND 40)
);

-- Zeitplan: je Termin beliebig viele "Leistungsrichter"-Spuren (zeitplan_richter), jede
-- mit einer eigenen, frei sortierbaren Abfolge aus Prüfungsblöcken und Pausen
-- (zeitplan_eintrag). Start-/Endzeiten werden NICHT gespeichert, sondern bei Bedarf aus
-- der Zeitplan-Startzeit (veranstaltung.zeitplan_start) und den Dauern der Einträge neu
-- berechnet (siehe berechne_zeitplan/berechne_zeitplan_bloecke) - so bleibt der Plan
-- immer konsistent, auch wenn nachträglich ein Eintrag verschoben/geändert wird.
CREATE TABLE IF NOT EXISTS zeitplan_richter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    reihenfolge INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS zeitplan_eintrag (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    richter_id INTEGER NOT NULL REFERENCES zeitplan_richter(id) ON DELETE CASCADE,
    reihenfolge INTEGER NOT NULL,
    typ TEXT NOT NULL CHECK (typ IN ('pruefung', 'pause')),
    art TEXT CHECK (art IN ('ED', 'DK')),
    stufe INTEGER CHECK (stufe IN (1, 2, 3)),
    disziplin TEXT CHECK (disziplin IN ('Trümmerfeld', 'Flächensuche', 'Behältnisstrecke')),
    dauer_minuten INTEGER NOT NULL CHECK (dauer_minuten > 0),
    bezeichnung TEXT,
    -- Prüfungsblöcke brauchen Art/Leistungsklasse/Disziplin, Pausen dürfen sie nicht
    -- haben (Pausen haben stattdessen optional eine freie Bezeichnung).
    CHECK (
        (typ = 'pruefung' AND art IS NOT NULL AND stufe IS NOT NULL AND disziplin IS NOT NULL) OR
        (typ = 'pause' AND art IS NULL AND stufe IS NULL AND disziplin IS NULL)
    )
);
"""

# PostgreSQL-Variante desselben Schemas (für die geplante Podman/Web-Version mit
# Mehrbenutzerzugriff, siehe init_db_postgres() weiter unten). Der einzige tatsächliche
# Syntax-Unterschied zwischen SQLite und PostgreSQL in diesem Schema ist die
# Autoincrement-Schreibweise der drei id-Spalten (teilnehmer/zeitplan_richter/
# zeitplan_eintrag) - alles andere (CHECK-Constraints, REFERENCES ... ON DELETE CASCADE,
# Kommentare) ist Standard-SQL und funktioniert in beiden Datenbanken identisch. Daher
# hier bewusst KEINE zweite, separat gepflegte Schema-Definition, sondern eine einmalige
# Ersetzung - eine Änderung an SCHEMA oben wirkt automatisch auf beide Datenbanken.
SCHEMA_POSTGRES = SCHEMA.replace(
    "INTEGER PRIMARY KEY AUTOINCREMENT",
    "INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY",
)


_INSERT_TABELLE_RE = re.compile(r"\s*INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
# Tabellen, bei denen eine INSERT-Funktion in diesem Modul den neu vergebenen
# Primärschlüssel über `cur.lastrowid` abfragt (siehe add_teilnehmer, add_zeitplan_richter,
# add_zeitplan_pruefungsblock, add_zeitplan_pause). psycopg2 kennt `lastrowid` nicht -
# _PostgresConnection.execute() hängt für INSERTs in diese Tabellen automatisch
# "RETURNING id" an und liefert den Wert stattdessen über dieses Attribut zurück, damit
# der aufrufende Code unverändert bleiben kann.
_LASTROWID_TABELLEN = {"teilnehmer", "zeitplan_richter", "zeitplan_eintrag"}


class _PostgresCursor:
    """Reicht fetchone()/fetchall() an den echten psycopg2-Cursor durch und stellt
    zusätzlich .lastrowid bereit, das psycopg2 (anders als sqlite3.Cursor) nicht kennt -
    siehe _PostgresConnection.execute()."""

    def __init__(self, roh_cursor, lastrowid: int | None) -> None:
        self._roh_cursor = roh_cursor
        self.lastrowid = lastrowid

    def fetchone(self):
        return self._roh_cursor.fetchone()

    def fetchall(self):
        return self._roh_cursor.fetchall()


class _PostgresConnection:
    """Dünner Kompatibilitäts-Wrapper um eine psycopg2-Verbindung, der die von diesem
    Modul verwendete Teilmenge der sqlite3.Connection-Schnittstelle nachbildet:
    execute()/executescript()/commit()/close(), '?'-Platzhalter statt psycopg2s '%s', sowie
    dict-artige Ergebniszeilen (row["spalte"], dict(row)) wie sqlite3.Row.

    Dadurch bleiben alle ~40 Datenfunktionen in diesem Modul UNVERÄNDERT - sie
    funktionieren identisch, egal ob `conn` eine lokale SQLite-Termin-Datei (Desktop,
    sqlite3.Connection direkt) oder eine gemeinsame PostgreSQL-Datenbank (Container/Web,
    dieser Wrapper) ist. Das war genau das Ziel dieser Umstellung: eine Änderung an der
    Geschäftslogik/den Abfragen muss nur an EINER Stelle gemacht werden, nicht doppelt
    für beide Datenbanken."""

    def __init__(self, roh_verbindung) -> None:
        self._roh_verbindung = roh_verbindung

    def execute(self, sql: str, params=()) -> _PostgresCursor:
        sql_pg = sql.replace("?", "%s")
        tabelle_treffer = _INSERT_TABELLE_RE.match(sql)
        braucht_lastrowid = (
            tabelle_treffer is not None
            and tabelle_treffer.group(1).lower() in _LASTROWID_TABELLEN
            and "returning" not in sql.lower()
        )
        if braucht_lastrowid:
            sql_pg = f"{sql_pg} RETURNING id"
        roh_cursor = self._roh_verbindung.cursor()
        roh_cursor.execute(sql_pg, params)
        lastrowid = roh_cursor.fetchone()["id"] if braucht_lastrowid else None
        return _PostgresCursor(roh_cursor, lastrowid)

    def executescript(self, sql: str) -> None:
        # Anders als sqlite3.Connection.executescript() reicht bei psycopg2 ein
        # einzelner execute()-Aufruf mit mehreren durch ';' getrennten Anweisungen -
        # verwendet hier für das mehrteilige CREATE-TABLE-Schema (SCHEMA_POSTGRES).
        self._roh_verbindung.cursor().execute(sql)

    def commit(self) -> None:
        self._roh_verbindung.commit()

    def close(self) -> None:
        self._roh_verbindung.close()


DISZIPLIN_SPALTEN = {
    "Trümmerfeld": ("suche_truemmerfeld", "anzeige_truemmerfeld"),
    "Flächensuche": ("suche_flaechensuche", "anzeige_flaechensuche"),
    "Behältnisstrecke": ("suche_behaeltnis", "anzeige_behaeltnis"),
}
ALLE_DISZIPLINEN = list(DISZIPLIN_SPALTEN)


_VERANSTALTUNG_NEUE_SPALTEN = [
    "vereins_nr", "pruefungsnummer", "wertungsrichter_1", "wertungsrichter_2", "pruefungsleiter",
    "pruefungsgebuehr_ed", "pruefungsgebuehr_dk", "zeitplan_start",
]


def _vorhandene_spalten(conn, tabelle: str) -> set[str]:
    """Ermittelt die aktuell in `tabelle` vorhandenen Spalten - gemeinsame Grundlage für
    die beiden Migrations-Funktionen unten. Funktioniert für eine lokale SQLite-
    Termin-Datei (PRAGMA table_info, dort per Positionsindex - so liefert es sqlite3)
    genauso wie für eine gemeinsame PostgreSQL-Datenbank (information_schema.columns,
    dort per Spaltenname - so liefert es der _PostgresConnection-Wrapper).

    Wichtig bei PostgreSQL mit mehreren Terminen (siehe Terminverwaltungs-Abschnitt
    weiter unten): information_schema.columns listet OHNE Einschränkung Spalten aus
    ALLEN Schemas, nicht nur aus dem gerade aktiven (search_path) - eine gleichnamige
    Tabelle in einem ANDEREN Termin-Schema (z.B. termin_2.veranstaltung) würde sonst mit
    hineinzählen. `table_schema = current_schema()` schränkt deshalb gezielt auf das
    Schema ein, das der aktuelle search_path gerade tatsächlich anspricht."""
    if isinstance(conn, sqlite3.Connection):
        return {row[1] for row in conn.execute(f"PRAGMA table_info({tabelle})").fetchall()}
    rows = conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = ? AND table_schema = current_schema()",
        (tabelle,),
    ).fetchall()
    return {row["column_name"] for row in rows}


def _migriere_veranstaltung_spalten(conn) -> None:
    """Ergänzt in bereits vor dieser Programmversion angelegten Termin-Dateien/
    Datenbanken die neuen, optionalen Veranstaltungs-Spalten nachträglich (CREATE TABLE
    IF NOT EXISTS allein reicht dafür nicht, da die Tabelle in Altdateien schon ohne
    diese Spalten existiert). ALTER TABLE ADD COLUMN ist dafür in SQLite wie PostgreSQL
    unproblematisch: keine Datenverluste, bestehende Zeilen bekommen für die neue Spalte
    einfach NULL. Funktioniert dialektunabhängig, siehe _vorhandene_spalten()."""
    vorhandene_spalten = _vorhandene_spalten(conn, "veranstaltung")
    for spalte in _VERANSTALTUNG_NEUE_SPALTEN:
        if spalte not in vorhandene_spalten:
            conn.execute(f"ALTER TABLE veranstaltung ADD COLUMN {spalte} TEXT")
    conn.commit()


_TEILNEHMER_NEUE_SPALTEN = [
    ("bezahlt", "INTEGER NOT NULL DEFAULT 0"),
    ("gegenstand_1_disziplin", "TEXT"),
    ("gegenstand_2_disziplin", "TEXT"),
    ("gegenstand_3_disziplin", "TEXT"),
    ("verband", "TEXT"),
    ("mitgliedsnummer", "TEXT"),
    ("wurftag", "TEXT"),
    ("strasse", "TEXT"),
    ("hausnummer", "TEXT"),
    ("plz", "TEXT"),
    ("ort", "TEXT"),
    ("email", "TEXT"),
    ("telefon", "TEXT"),
]


def _migriere_teilnehmer_spalten(conn) -> None:
    """Ergänzt in bereits vor dieser Programmversion angelegten Termin-Dateien/
    Datenbanken neu hinzugekommene Teilnehmer-Spalten nachträglich (analog zu
    _migriere_veranstaltung_spalten oben) - aktuell 'bezahlt', die drei
    'gegenstand_N_disziplin'-Zuordnungsfelder sowie die Verwaltungs-/Kontaktdaten
    (Verband, Mitgliedsnummer, Wurftag, Straße, Hausnummer, PLZ, Ort, E-Mail, Telefon).
    Bestehende Teilnehmer gelten dabei als "noch nicht bezahlt" (Default 0), ihre
    Gegenstände als "frei" (NULL) statt automatisch einer Disziplin zugeordnet, und die
    neuen Verwaltungs-/Kontaktfelder als leer (NULL) - andernfalls würde allein durch das
    Öffnen einer alten Termin-Datei fälschlich der Eindruck entstehen, bereits erfasste
    Teilnehmer hätten schon bezahlt, eine bestimmte Gegenstand-Zuordnung oder Kontaktdaten
    hinterlegt. Funktioniert dialektunabhängig, siehe _vorhandene_spalten()."""
    vorhandene_spalten = _vorhandene_spalten(conn, "teilnehmer")
    for spalte, sql_typ in _TEILNEHMER_NEUE_SPALTEN:
        if spalte not in vorhandene_spalten:
            conn.execute(f"ALTER TABLE teilnehmer ADD COLUMN {spalte} {sql_typ}")
    conn.commit()


def init_db(pfad: str) -> sqlite3.Connection:
    """Öffnet (oder erstellt) die Termin-Datenbankdatei unter `pfad`."""
    conn = sqlite3.connect(pfad)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.commit()
    _migriere_veranstaltung_spalten(conn)
    _migriere_teilnehmer_spalten(conn)
    return conn


def _richte_schema_im_aktuellen_suchpfad_ein(conn) -> None:
    """Legt die Tabellen (SCHEMA_POSTGRES) im aktuellen search_path der Verbindung an und
    führt die Migrationen aus. Gemeinsam genutzt von init_db_postgres() (ein Termin = eine
    ganze Datenbank/eigene Verbindung) und erstelle_termin_postgres()/
    oeffne_termin_postgres() weiter unten (mehrere Termine = mehrere Schemas innerhalb
    EINER gemeinsam genutzten Datenbank, siehe dortige Kommentare)."""
    conn.executescript(SCHEMA_POSTGRES)
    conn.commit()
    _migriere_veranstaltung_spalten(conn)
    _migriere_teilnehmer_spalten(conn)


def init_db_postgres(dsn: str) -> _PostgresConnection:
    """Öffnet eine PostgreSQL-Datenbank für EINEN Termin (die ganze Datenbank entspricht
    dabei einer SQLite-Termin-Datei) - das Pendant zu init_db() für die SQLite-Desktop-
    Version, mit identischem Schema (SCHEMA_POSTGRES) und denselben Migrations-
    Funktionen. Alle übrigen Funktionen in diesem Modul funktionieren mit der
    zurückgegebenen Verbindung unverändert (siehe _PostgresConnection).

    Für die geplante Podman/Web-Version mit MEHREREN Terminen in EINER gemeinsam
    genutzten Datenbank (Mehrbenutzerzugriff) siehe stattdessen die Terminverwaltung
    weiter unten (verbinde_postgres_server()/erstelle_termin_postgres()/
    oeffne_termin_postgres()/loesche_termin_postgres()) - diese Funktion hier bleibt der
    einfachere Baustein für den Fall einer eigenen Datenbank pro Termin.

    Importiert psycopg2 bewusst erst hier statt am Modulanfang, damit db.py für die
    SQLite-Desktop-Version weiterhin ganz ohne diese zusätzliche Abhängigkeit auskommt -
    genau wie pyzipper aktuell nur innerhalb der Backup-Funktionen gebraucht wird statt
    global importiert zu werden.

    dsn: vollständiger PostgreSQL-Verbindungsstring,
    z. B. "postgresql://benutzer:passwort@host:5432/datenbankname".
    """
    import psycopg2
    import psycopg2.extras

    roh_verbindung = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    conn = _PostgresConnection(roh_verbindung)
    _richte_schema_im_aktuellen_suchpfad_ein(conn)
    return conn


# --- Veranstaltung -----------------------------------------------------

def set_veranstaltung(
    conn: sqlite3.Connection,
    verein: str,
    datum: str,
    ort: str | None = None,
    vereins_nr: str | None = None,
    pruefungsnummer: str | None = None,
    wertungsrichter_1: str | None = None,
    wertungsrichter_2: str | None = None,
    pruefungsleiter: str | None = None,
    pruefungsgebuehr_ed: str | None = None,
    pruefungsgebuehr_dk: str | None = None,
    zeitplan_start: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO veranstaltung (
            id, verein, ort, datum, vereins_nr, pruefungsnummer,
            wertungsrichter_1, wertungsrichter_2, pruefungsleiter,
            pruefungsgebuehr_ed, pruefungsgebuehr_dk, zeitplan_start
        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            verein=excluded.verein, ort=excluded.ort, datum=excluded.datum,
            vereins_nr=excluded.vereins_nr, pruefungsnummer=excluded.pruefungsnummer,
            wertungsrichter_1=excluded.wertungsrichter_1, wertungsrichter_2=excluded.wertungsrichter_2,
            pruefungsleiter=excluded.pruefungsleiter,
            pruefungsgebuehr_ed=excluded.pruefungsgebuehr_ed, pruefungsgebuehr_dk=excluded.pruefungsgebuehr_dk,
            zeitplan_start=excluded.zeitplan_start
        """,
        (
            verein, ort, datum, vereins_nr, pruefungsnummer, wertungsrichter_1, wertungsrichter_2,
            pruefungsleiter, pruefungsgebuehr_ed, pruefungsgebuehr_dk, zeitplan_start,
        ),
    )
    conn.commit()


def get_veranstaltung(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute("SELECT * FROM veranstaltung WHERE id = 1").fetchone()
    return dict(row) if row else None


def pruefungsgebuehr_fuer_art(veranstaltung: dict | None, art: str) -> str | None:
    """Liefert die für Art (ED/DK) in den Veranstaltungsdaten hinterlegte Prüfungsgebühr,
    oder None, wenn dafür noch keine hinterlegt ist (z. B. bei einer vor Einführung
    dieses Felds angelegten Veranstaltung)."""
    if not veranstaltung:
        return None
    spalte = "pruefungsgebuehr_ed" if art == "ED" else "pruefungsgebuehr_dk"
    return veranstaltung.get(spalte)


# --- Teilnehmer ----------------------------------------------------------

@dataclass
class NeuerTeilnehmer:
    nachname: str
    vorname: str
    rufname_hund: str
    art: str  # "ED" oder "DK"
    stufe: int  # 1, 2 oder 3
    disziplin: str | None = None  # Pflicht bei ED, muss None sein bei DK
    verein: str | None = None
    zwingername: str | None = None
    geschlecht: str | None = None
    schulterhoehe_cm: int | None = None
    chip_nr: str | None = None
    startnummer: int | None = None
    gegenstand_1: str | None = None
    gegenstand_2: str | None = None
    gegenstand_3: str | None = None
    # Welcher Disziplin (Trümmerfeld/Flächensuche/Behältnisstrecke) ist der jeweilige
    # Gegenstand zugeordnet? None = "frei" (keiner bestimmten Disziplin zugeordnet, kein
    # Default). Siehe gegenstand_fuer_disziplin() weiter unten.
    gegenstand_1_disziplin: str | None = None
    gegenstand_2_disziplin: str | None = None
    gegenstand_3_disziplin: str | None = None
    bezahlt: bool = False
    # Verwaltungs-/Kontaktdaten (siehe SCHEMA oben) - "verband" meint den übergeordneten
    # Dachverband (z.B. VDH), nicht den lokalen "verein" oben.
    verband: str | None = None
    mitgliedsnummer: str | None = None
    wurftag: str | None = None
    strasse: str | None = None
    hausnummer: str | None = None
    plz: str | None = None
    ort: str | None = None
    email: str | None = None
    telefon: str | None = None


def add_teilnehmer(conn: sqlite3.Connection, t: NeuerTeilnehmer) -> int:
    cur = conn.execute(
        """
        INSERT INTO teilnehmer (
            nachname, vorname, verein, zwingername, rufname_hund, geschlecht,
            schulterhoehe_cm, chip_nr, art, stufe, disziplin, startnummer,
            gegenstand_1, gegenstand_2, gegenstand_3,
            gegenstand_1_disziplin, gegenstand_2_disziplin, gegenstand_3_disziplin, bezahlt,
            verband, mitgliedsnummer, wurftag, strasse, hausnummer, plz, ort, email, telefon
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            t.nachname, t.vorname, t.verein, t.zwingername, t.rufname_hund, t.geschlecht,
            t.schulterhoehe_cm, t.chip_nr, t.art, t.stufe, t.disziplin, t.startnummer,
            t.gegenstand_1, t.gegenstand_2, t.gegenstand_3,
            t.gegenstand_1_disziplin, t.gegenstand_2_disziplin, t.gegenstand_3_disziplin, int(t.bezahlt),
            t.verband, t.mitgliedsnummer, t.wurftag, t.strasse, t.hausnummer, t.plz, t.ort, t.email, t.telefon,
        ),
    )
    teilnehmer_id = cur.lastrowid
    conn.execute("INSERT INTO ergebnisse (teilnehmer_id) VALUES (?)", (teilnehmer_id,))
    conn.commit()
    return teilnehmer_id


def list_teilnehmer(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM teilnehmer ORDER BY startnummer, nachname").fetchall()
    return [dict(r) for r in rows]


def vergebene_startnummern(conn: sqlite3.Connection, ausser_teilnehmer_id: int | None = None) -> set[int]:
    """Alle bereits vergebenen Startnummern in diesem Termin (für Dubletten-Prüfung/Vorschlag
    in der GUI). `ausser_teilnehmer_id` blendet die eigene Nummer beim Bearbeiten aus."""
    query = "SELECT startnummer FROM teilnehmer WHERE startnummer IS NOT NULL"
    params: list = []
    if ausser_teilnehmer_id is not None:
        query += " AND id != ?"
        params.append(ausser_teilnehmer_id)
    # Spaltenname statt Positionsindex (row[0]): sqlite3.Row erlaubt beides, die
    # dict-artigen Zeilen der PostgreSQL-Verbindung (_PostgresConnection) nur den Zugriff
    # per Spaltenname - siehe SCHEMA_POSTGRES/init_db_postgres weiter oben.
    return {row["startnummer"] for row in conn.execute(query, params).fetchall()}


def naechste_freie_startnummer(conn: sqlite3.Connection) -> int:
    """Kleinste noch nicht vergebene Startnummer ab 1 (füllt auch Lücken durch
    gelöschte Teilnehmer wieder auf, statt immer nur hochzuzählen)."""
    vergeben = vergebene_startnummern(conn)
    n = 1
    while n in vergeben:
        n += 1
    return n


def get_teilnehmer(conn: sqlite3.Connection, teilnehmer_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM teilnehmer WHERE id = ?", (teilnehmer_id,)).fetchone()
    return dict(row) if row else None


def update_teilnehmer(conn: sqlite3.Connection, teilnehmer_id: int, t: NeuerTeilnehmer) -> None:
    conn.execute(
        """
        UPDATE teilnehmer SET
            nachname=?, vorname=?, verein=?, zwingername=?, rufname_hund=?, geschlecht=?,
            schulterhoehe_cm=?, chip_nr=?, art=?, stufe=?, disziplin=?, startnummer=?,
            gegenstand_1=?, gegenstand_2=?, gegenstand_3=?,
            gegenstand_1_disziplin=?, gegenstand_2_disziplin=?, gegenstand_3_disziplin=?, bezahlt=?,
            verband=?, mitgliedsnummer=?, wurftag=?, strasse=?, hausnummer=?, plz=?, ort=?, email=?, telefon=?
        WHERE id=?
        """,
        (
            t.nachname, t.vorname, t.verein, t.zwingername, t.rufname_hund, t.geschlecht,
            t.schulterhoehe_cm, t.chip_nr, t.art, t.stufe, t.disziplin, t.startnummer,
            t.gegenstand_1, t.gegenstand_2, t.gegenstand_3,
            t.gegenstand_1_disziplin, t.gegenstand_2_disziplin, t.gegenstand_3_disziplin,
            int(t.bezahlt),
            t.verband, t.mitgliedsnummer, t.wurftag, t.strasse, t.hausnummer, t.plz, t.ort, t.email, t.telefon,
            teilnehmer_id,
        ),
    )
    conn.commit()


def setze_bezahlt(conn: sqlite3.Connection, teilnehmer_id: int, bezahlt: bool) -> None:
    """Setzt/entfernt die Bezahlt-Markierung eines Teilnehmers, ohne die übrigen
    Stammdaten anzufassen - für den schnellen Umschalten-Button in der Teilnehmerliste
    (z.B. am Anmeldetisch), ohne dafür den kompletten Bearbeiten-Dialog öffnen zu müssen."""
    conn.execute("UPDATE teilnehmer SET bezahlt = ? WHERE id = ?", (int(bezahlt), teilnehmer_id))
    conn.commit()


def delete_teilnehmer(conn: sqlite3.Connection, teilnehmer_id: int) -> None:
    conn.execute("DELETE FROM teilnehmer WHERE id = ?", (teilnehmer_id,))
    conn.commit()


# --- Ergebnisse ------------------------------------------------------------

def get_ergebnis(conn: sqlite3.Connection, teilnehmer_id: int) -> dict | None:
    """Liefert die (ggf. teilweise oder noch gar nicht ausgefüllte) Ergebniszeile eines
    Teilnehmers - z. B. um ein Erfassungsformular mit bereits eingetragenen Werten
    vorzubelegen (siehe app_web.py). None, wenn der Teilnehmer selbst nicht existiert
    (jeder existierende Teilnehmer hat durch add_teilnehmer() immer eine - anfangs leere -
    Ergebniszeile, siehe dort)."""
    row = conn.execute("SELECT * FROM ergebnisse WHERE teilnehmer_id = ?", (teilnehmer_id,)).fetchone()
    return dict(row) if row else None


def eintragen_ergebnis(
    conn: sqlite3.Connection, teilnehmer_id: int, disziplin: str, suche: int | None, anzeige: int | None
) -> None:
    """Trägt Suchleistung/Anzeigeleistung für eine Disziplin eines Teilnehmers ein.

    suche/anzeige dürfen auch beide None sein - das löscht ein zuvor eingetragenes
    Ergebnis wieder (z.B. wenn in der Ergebniserfassung beide Felder einer Zeile geleert
    werden). Die CHECK-Constraints auf den Spalten (BETWEEN 0 AND 60/40) greifen bei
    NULL nicht, SQLite wertet einen NULL-Vergleich nicht als Verletzung."""
    if disziplin not in DISZIPLIN_SPALTEN:
        raise ValueError(f"Unbekannte Disziplin: {disziplin!r}")
    spalte_suche, spalte_anzeige = DISZIPLIN_SPALTEN[disziplin]
    conn.execute(
        f"UPDATE ergebnisse SET {spalte_suche} = ?, {spalte_anzeige} = ? WHERE teilnehmer_id = ?",
        (suche, anzeige, teilnehmer_id),
    )
    conn.commit()


def _disziplin_punkte(ergebnis: dict, disziplin: str) -> int | None:
    """Summe aus Such- und Anzeigeleistung einer einzelnen Disziplin, oder None,
    wenn eine der beiden noch nicht erfasst ist."""
    s_spalte, a_spalte = DISZIPLIN_SPALTEN[disziplin]
    suche, anzeige = ergebnis[s_spalte], ergebnis[a_spalte]
    if suche is None or anzeige is None:
        return None
    return suche + anzeige


def _wertnote(teilnehmer: dict, ergebnis: dict):
    """Berechnet die Wertnote (inkl. Mindestpunktzahl-je-Disziplin-Prüfung, siehe
    shs_core.berechne_wertnote_ed/_dk) - oder None, wenn noch nicht alle nötigen
    Disziplin-Ergebnisse erfasst sind."""
    if teilnehmer["art"] == "ED":
        punkte = _disziplin_punkte(ergebnis, teilnehmer["disziplin"])
        if punkte is None:
            return None
        return berechne_wertnote_ed(punkte)

    # DK: alle drei Disziplinen müssen vollständig erfasst sein
    einzelpunkte = [_disziplin_punkte(ergebnis, d) for d in ALLE_DISZIPLINEN]
    if any(p is None for p in einzelpunkte):
        return None
    truemmerfeld, flaechensuche, behaeltnisstrecke = einzelpunkte
    return berechne_wertnote_dk(truemmerfeld, flaechensuche, behaeltnisstrecke)


def leistungsklasse_label(teilnehmer: dict) -> str:
    """Menschenlesbares Label für Art+Leistungsklasse(+Disziplin bei ED) - dient auch
    als Filterkriterium in der GUI (Ergebniserfassung/Auswertung)."""
    if teilnehmer["art"] == "DK":
        return f"DK LK {teilnehmer['stufe']}"
    return f"ED LK {teilnehmer['stufe']} {teilnehmer['disziplin']}"


_GEGENSTAND_FELDER = ("gegenstand_1", "gegenstand_2", "gegenstand_3")


def gegenstand_fuer_disziplin(teilnehmer: dict, disziplin: str) -> str | None:
    """Liefert den (frei eingetragenen) Gegenstand, der der angegebenen Disziplin
    zugeordnet ist - oder None, wenn keiner der drei Gegenstände 1-3 dieser Disziplin
    zugeordnet ist (z.B. weil alle auf "frei" stehen, oder für ED ohne hinterlegte
    Zuordnung). Jeder der drei Gegenstände hat eine eigene, frei wählbare Zuordnung
    (gegenstand_N_disziplin: Trümmerfeld/Flächensuche/Behältnisstrecke/None="frei") -
    es gibt bewusst KEINE automatische Zuordnung nach Position (Gegenstand 1 also nicht
    automatisch Trümmerfeld usw.), da das nicht zuverlässig der tatsächlichen Zuteilung
    entsprach. Fließt in die Bewertungsbögen-PDF ein (siehe pdf_export.py)."""
    for feld in _GEGENSTAND_FELDER:
        if teilnehmer.get(feld) and teilnehmer.get(f"{feld}_disziplin") == disziplin:
            return teilnehmer[feld]
    return None


def alle_leistungsklassen(conn: sqlite3.Connection) -> list[str]:
    """Sortierte Liste aller in diesem Termin tatsächlich vorkommenden Art/LK-Label -
    zum Befüllen eines Filters in der Oberfläche."""
    labels = {leistungsklasse_label(t) for t in list_teilnehmer(conn)}
    return sorted(labels)


def berechne_auswertung(conn: sqlite3.Connection) -> tuple[list[Teilnehmerergebnis], list[dict]]:
    """Liefert (gerankte Teilnehmer mit Ergebnis, Teilnehmer ohne vollständiges Ergebnis)."""
    teilnehmer_rows = list_teilnehmer(conn)
    ergebnis_rows = {
        r["teilnehmer_id"]: dict(r)
        for r in conn.execute("SELECT * FROM ergebnisse").fetchall()
    }

    fertig: list[Teilnehmerergebnis] = []
    ausstehend: list[dict] = []

    for t in teilnehmer_rows:
        ergebnis = ergebnis_rows[t["id"]]
        wertnote = _wertnote(t, ergebnis)
        if wertnote is None:
            ausstehend.append(t)
            continue
        fertig.append(
            Teilnehmerergebnis(
                id=str(t["id"]),
                name=f"{t['nachname']}, {t['vorname']}",
                leistungsklasse=leistungsklasse_label(t),
                wertnote=wertnote,
            )
        )

    return berechne_rangliste(fertig), ausstehend


# --- Zeitplan --------------------------------------------------------------
#
# Siehe Tabellenkommentar bei SCHEMA weiter oben: ein Zeitplan besteht aus einer frei
# wählbaren Anzahl "Leistungsrichter"-Spuren, jede mit einer eigenen, frei sortierbaren
# Abfolge aus Prüfungsblöcken und Pausen. Ein Prüfungsblock deckt alle Teilnehmer einer
# Art/Leistungsklasse(/Disziplin bei ED) ab; wie viele das sind (und damit wie lange der
# Block insgesamt dauert) ergibt sich erst bei der Berechnung (berechne_zeitplan*) aus den
# aktuell erfassten Teilnehmern - der Eintrag selbst speichert nur die Dauer PRO Teilnehmer.

def list_zeitplan_richter(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM zeitplan_richter ORDER BY reihenfolge").fetchall()
    return [dict(r) for r in rows]


def add_zeitplan_richter(conn: sqlite3.Connection, name: str | None = None) -> int:
    """Legt einen neuen Leistungsrichter (Zeitplan-Spur) an und hängt ihn ans Ende an.
    Ohne Namen wird automatisch 'Leistungsrichter N' vergeben (frei umbenennbar)."""
    naechste_reihenfolge = len(list_zeitplan_richter(conn))
    name = name or f"Leistungsrichter {naechste_reihenfolge + 1}"
    cur = conn.execute(
        "INSERT INTO zeitplan_richter (name, reihenfolge) VALUES (?, ?)",
        (name, naechste_reihenfolge),
    )
    conn.commit()
    return cur.lastrowid


def umbenennen_zeitplan_richter(conn: sqlite3.Connection, richter_id: int, name: str) -> None:
    conn.execute("UPDATE zeitplan_richter SET name = ? WHERE id = ?", (name, richter_id))
    conn.commit()


def loesche_zeitplan_richter(conn: sqlite3.Connection, richter_id: int) -> None:
    """Löscht einen Leistungsrichter samt aller seiner Zeitplan-Einträge (ON DELETE CASCADE)
    und rückt die reihenfolge der verbliebenen Richter lückenlos nach."""
    conn.execute("DELETE FROM zeitplan_richter WHERE id = ?", (richter_id,))
    for neue_position, richter in enumerate(list_zeitplan_richter(conn)):
        conn.execute(
            "UPDATE zeitplan_richter SET reihenfolge = ? WHERE id = ?",
            (neue_position, richter["id"]),
        )
    conn.commit()


def verschiebe_zeitplan_richter(conn: sqlite3.Connection, richter_id: int, richtung: int) -> None:
    """Vertauscht die Reihenfolge mit dem Nachbarn (richtung: -1 = nach vorn, +1 = nach
    hinten). Am Rand (kein Nachbar in die Richtung) passiert nichts."""
    richter_liste = list_zeitplan_richter(conn)
    index = next((i for i, r in enumerate(richter_liste) if r["id"] == richter_id), None)
    if index is None:
        return
    ziel_index = index + richtung
    if not (0 <= ziel_index < len(richter_liste)):
        return
    a, b = richter_liste[index], richter_liste[ziel_index]
    conn.execute("UPDATE zeitplan_richter SET reihenfolge = ? WHERE id = ?", (b["reihenfolge"], a["id"]))
    conn.execute("UPDATE zeitplan_richter SET reihenfolge = ? WHERE id = ?", (a["reihenfolge"], b["id"]))
    conn.commit()


def list_zeitplan_eintraege(conn: sqlite3.Connection, richter_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM zeitplan_eintrag WHERE richter_id = ? ORDER BY reihenfolge",
        (richter_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_zeitplan_pruefungsblock(
    conn: sqlite3.Connection, richter_id: int, art: str, stufe: int, disziplin: str, dauer_minuten: int,
) -> int:
    """Fügt einen Prüfungsblock ans Ende der Spur des Richters an. `dauer_minuten` ist die
    Dauer PRO Teilnehmer in diesem Block (die Gesamtdauer ergibt sich erst zur Laufzeit aus
    der aktuellen Teilnehmerzahl, siehe berechne_zeitplan_bloecke)."""
    naechste_reihenfolge = len(list_zeitplan_eintraege(conn, richter_id))
    cur = conn.execute(
        """
        INSERT INTO zeitplan_eintrag (richter_id, reihenfolge, typ, art, stufe, disziplin, dauer_minuten)
        VALUES (?, ?, 'pruefung', ?, ?, ?, ?)
        """,
        (richter_id, naechste_reihenfolge, art, stufe, disziplin, dauer_minuten),
    )
    conn.commit()
    return cur.lastrowid


def add_zeitplan_pause(
    conn: sqlite3.Connection, richter_id: int, dauer_minuten: int, bezeichnung: str | None = None,
) -> int:
    naechste_reihenfolge = len(list_zeitplan_eintraege(conn, richter_id))
    cur = conn.execute(
        """
        INSERT INTO zeitplan_eintrag (richter_id, reihenfolge, typ, dauer_minuten, bezeichnung)
        VALUES (?, ?, 'pause', ?, ?)
        """,
        (richter_id, naechste_reihenfolge, dauer_minuten, bezeichnung),
    )
    conn.commit()
    return cur.lastrowid


def aktualisiere_zeitplan_eintrag(
    conn: sqlite3.Connection, eintrag_id: int, dauer_minuten: int | None = None, bezeichnung: str | None = None,
) -> None:
    """Ändert Dauer und/oder Bezeichnung eines bestehenden Eintrags (Prüfungsblock oder
    Pause) nachträglich - z. B. um die je Block frei überschreibbare Dauer anzupassen."""
    if dauer_minuten is not None:
        conn.execute("UPDATE zeitplan_eintrag SET dauer_minuten = ? WHERE id = ?", (dauer_minuten, eintrag_id))
    if bezeichnung is not None:
        conn.execute("UPDATE zeitplan_eintrag SET bezeichnung = ? WHERE id = ?", (bezeichnung, eintrag_id))
    conn.commit()


def loesche_zeitplan_eintrag(conn: sqlite3.Connection, eintrag_id: int) -> None:
    row = conn.execute("SELECT richter_id FROM zeitplan_eintrag WHERE id = ?", (eintrag_id,)).fetchone()
    if row is None:
        return
    richter_id = row["richter_id"]
    conn.execute("DELETE FROM zeitplan_eintrag WHERE id = ?", (eintrag_id,))
    for neue_position, eintrag in enumerate(list_zeitplan_eintraege(conn, richter_id)):
        conn.execute(
            "UPDATE zeitplan_eintrag SET reihenfolge = ? WHERE id = ?",
            (neue_position, eintrag["id"]),
        )
    conn.commit()


def verschiebe_zeitplan_eintrag(conn: sqlite3.Connection, eintrag_id: int, richtung: int) -> None:
    """Vertauscht die Reihenfolge mit dem Nachbarn innerhalb derselben Richter-Spur
    (richtung: -1 = nach vorn, +1 = nach hinten)."""
    row = conn.execute("SELECT richter_id FROM zeitplan_eintrag WHERE id = ?", (eintrag_id,)).fetchone()
    if row is None:
        return
    eintrag_liste = list_zeitplan_eintraege(conn, row["richter_id"])
    index = next((i for i, e in enumerate(eintrag_liste) if e["id"] == eintrag_id), None)
    if index is None:
        return
    ziel_index = index + richtung
    if not (0 <= ziel_index < len(eintrag_liste)):
        return
    a, b = eintrag_liste[index], eintrag_liste[ziel_index]
    conn.execute("UPDATE zeitplan_eintrag SET reihenfolge = ? WHERE id = ?", (b["reihenfolge"], a["id"]))
    conn.execute("UPDATE zeitplan_eintrag SET reihenfolge = ? WHERE id = ?", (a["reihenfolge"], b["id"]))
    conn.commit()


def zeitplan_gruppen(conn: sqlite3.Connection) -> list[dict]:
    """Fasst die aktuell erfassten Teilnehmer zu den Gruppen zusammen, für die je ein
    Prüfungsblock im Zeitplan sinnvoll ist: bei ED eine Gruppe je (Art, Stufe, Disziplin),
    bei DK eine Gruppe je Stufe UND Disziplin (da DK-Teilnehmer nacheinander in allen drei
    Disziplinen geprüft werden, taucht ein DK-Teilnehmer in bis zu drei Gruppen auf)."""
    teilnehmer = list_teilnehmer(conn)
    gruppen: dict[tuple, list] = {}
    for t in teilnehmer:
        if t["art"] == "ED":
            schluessel = (t["art"], t["stufe"], t["disziplin"])
            gruppen.setdefault(schluessel, []).append(t)
        else:
            for disziplin in ALLE_DISZIPLINEN:
                schluessel = (t["art"], t["stufe"], disziplin)
                gruppen.setdefault(schluessel, []).append(t)
    ergebnis = []
    for (art, stufe, disziplin), gruppen_teilnehmer in sorted(gruppen.items()):
        ergebnis.append({
            "art": art,
            "stufe": stufe,
            "disziplin": disziplin,
            "teilnehmer": sorted(
                gruppen_teilnehmer, key=lambda t: (t["startnummer"] is None, t["startnummer"] or 0)
            ),
        })
    return ergebnis


def _teilnehmer_fuer_pruefungseintrag(alle_teilnehmer: list[dict], eintrag: dict) -> list[dict]:
    """Filtert die zu einem Prüfungsblock-Eintrag passenden Teilnehmer (siehe zeitplan_gruppen
    für die Gruppenlogik) - wird bei jeder Zeitplan-Berechnung neu ausgewertet, damit
    nachträglich hinzugefügte/gelöschte Teilnehmer automatisch berücksichtigt werden."""
    gefiltert = [
        t for t in alle_teilnehmer
        if t["art"] == eintrag["art"] and t["stufe"] == eintrag["stufe"]
        and (eintrag["art"] == "DK" or t["disziplin"] == eintrag["disziplin"])
    ]
    return sorted(gefiltert, key=lambda t: (t["startnummer"] is None, t["startnummer"] or 0))


def _zeitplan_startzeit(veranstaltung: dict | None) -> datetime.datetime:
    start_text = (veranstaltung or {}).get("zeitplan_start") or "09:00"
    try:
        return datetime.datetime.strptime(start_text.strip(), "%H:%M")
    except ValueError:
        return datetime.datetime.strptime("09:00", "%H:%M")


def berechne_zeitplan(conn: sqlite3.Connection) -> list[dict]:
    """Berechnet für jeden Leistungsrichter die vollständige, zeilenweise Abfolge (eine
    Zeile je Teilnehmer bzw. je Pause) mit Start-/Endzeit - Grundlage für die Zeitplan-PDF
    sowie für die Planungsansicht im Zeitplan-Tab (dort werden so auch einzelne Teilnehmer
    statt nur ganzer Prüfungsblöcke angezeigt). Jede Zeile trägt zusätzlich "eintrag_id" -
    die ID des zugrundeliegenden Prüfungsblocks/der Pause -, damit z. B. die Oberfläche
    eine ausgewählte Teilnehmer-Zeile auf den passenden Block zum Verschieben/Bearbeiten/
    Löschen zurückführen kann. Hat ein Prüfungsblock (noch) keinen einzigen passenden
    Teilnehmer, erscheint trotzdem EINE Zeile dafür (mit teilnehmer=None, Dauer 0) - sonst
    würde ein leerer, aber bereits angelegter Block spurlos aus der Ansicht verschwinden
    und wäre nicht mehr auswähl-/verschiebbar. Für eine kompaktere Block-Ansicht (eine
    Zeile je Prüfungsblock/Pause, mit Teilnehmerzahl statt einzelner Teilnehmer) siehe
    berechne_zeitplan_bloecke."""
    veranstaltung = get_veranstaltung(conn)
    uhrzeit_start = _zeitplan_startzeit(veranstaltung)
    alle_teilnehmer = list_teilnehmer(conn)
    ergebnis = []
    for richter in list_zeitplan_richter(conn):
        aktuelle_zeit = uhrzeit_start
        zeilen = []
        for eintrag in list_zeitplan_eintraege(conn, richter["id"]):
            if eintrag["typ"] == "pause":
                start, ende = aktuelle_zeit, aktuelle_zeit + datetime.timedelta(minutes=eintrag["dauer_minuten"])
                zeilen.append({
                    "typ": "pause", "start": start, "ende": ende,
                    "bezeichnung": eintrag["bezeichnung"] or "Pause",
                    "eintrag_id": eintrag["id"],
                })
                aktuelle_zeit = ende
            else:
                teilnehmer_liste = _teilnehmer_fuer_pruefungseintrag(alle_teilnehmer, eintrag)
                if not teilnehmer_liste:
                    zeilen.append({
                        "typ": "pruefung", "start": aktuelle_zeit, "ende": aktuelle_zeit,
                        "art": eintrag["art"], "stufe": eintrag["stufe"], "disziplin": eintrag["disziplin"],
                        "teilnehmer": None, "eintrag_id": eintrag["id"],
                    })
                for t in teilnehmer_liste:
                    start, ende = aktuelle_zeit, aktuelle_zeit + datetime.timedelta(minutes=eintrag["dauer_minuten"])
                    zeilen.append({
                        "typ": "pruefung", "start": start, "ende": ende,
                        "art": eintrag["art"], "stufe": eintrag["stufe"], "disziplin": eintrag["disziplin"],
                        "teilnehmer": t, "eintrag_id": eintrag["id"],
                    })
                    aktuelle_zeit = ende
        ergebnis.append({"richter_id": richter["id"], "richter": richter["name"], "zeilen": zeilen})
    return ergebnis


def berechne_zeitplan_bloecke(conn: sqlite3.Connection) -> list[dict]:
    """Wie berechne_zeitplan, aber eine Zeile je Eintrag (Prüfungsblock als Ganzes bzw.
    Pause) statt je Teilnehmer - für die kompakte Planungsansicht in der Oberfläche.
    Jeder zurückgegebene Eintrag wird um start/ende/teilnehmer_anzahl ergänzt."""
    veranstaltung = get_veranstaltung(conn)
    uhrzeit_start = _zeitplan_startzeit(veranstaltung)
    alle_teilnehmer = list_teilnehmer(conn)
    ergebnis = []
    for richter in list_zeitplan_richter(conn):
        aktuelle_zeit = uhrzeit_start
        bloecke = []
        for eintrag in list_zeitplan_eintraege(conn, richter["id"]):
            eintrag = dict(eintrag)
            if eintrag["typ"] == "pause":
                dauer_gesamt = eintrag["dauer_minuten"]
                eintrag["teilnehmer_anzahl"] = None
            else:
                anzahl = len(_teilnehmer_fuer_pruefungseintrag(alle_teilnehmer, eintrag))
                dauer_gesamt = eintrag["dauer_minuten"] * anzahl
                eintrag["teilnehmer_anzahl"] = anzahl
            eintrag["start"] = aktuelle_zeit
            eintrag["ende"] = aktuelle_zeit + datetime.timedelta(minutes=dauer_gesamt)
            aktuelle_zeit = eintrag["ende"]
            bloecke.append(eintrag)
        ergebnis.append({"richter_id": richter["id"], "richter_name": richter["name"], "bloecke": bloecke})
    return ergebnis


def automatische_zeitplan_verteilung(
    conn: sqlite3.Connection, richter_ids: list[int], standard_dauer_minuten: int,
) -> None:
    """Ersetzt die Zeitplan-Einträge der übergebenen Richter durch einen automatischen
    Vorschlag: alle anfallenden Prüfungsblöcke (siehe zeitplan_gruppen) werden - größte
    Gruppe zuerst - jeweils dem Richter mit der aktuell geringsten Gesamtdauer zugeteilt
    (Longest-Processing-Time-Heuristik für eine ausgewogene Auslastung). Das Ergebnis ist
    nur ein Vorschlag und bleibt danach frei editierbar (verschieben, Dauer ändern, Pausen
    einfügen, zwischen Richtern verschieben)."""
    if not richter_ids:
        return
    for richter_id in richter_ids:
        conn.execute("DELETE FROM zeitplan_eintrag WHERE richter_id = ?", (richter_id,))
    conn.commit()

    gruppen = [g for g in zeitplan_gruppen(conn) if g["teilnehmer"]]
    gruppen.sort(key=lambda g: len(g["teilnehmer"]), reverse=True)

    gesamtdauer_je_richter = {richter_id: 0 for richter_id in richter_ids}
    naechste_reihenfolge = {richter_id: 0 for richter_id in richter_ids}
    for gruppe in gruppen:
        ziel_richter = min(richter_ids, key=lambda r: gesamtdauer_je_richter[r])
        dauer = len(gruppe["teilnehmer"]) * standard_dauer_minuten
        conn.execute(
            """
            INSERT INTO zeitplan_eintrag (richter_id, reihenfolge, typ, art, stufe, disziplin, dauer_minuten)
            VALUES (?, ?, 'pruefung', ?, ?, ?, ?)
            """,
            (
                ziel_richter, naechste_reihenfolge[ziel_richter],
                gruppe["art"], gruppe["stufe"], gruppe["disziplin"], standard_dauer_minuten,
            ),
        )
        naechste_reihenfolge[ziel_richter] += 1
        gesamtdauer_je_richter[ziel_richter] += dauer
    conn.commit()


# --- Terminübersicht -----------------------------------------------------------
#
# Jeder Termin ist eine eigenständige .sqlite-Datei (siehe Moduldocstring). Damit die
# Prüfungsleitung nicht bei jedem Start manuell zu einer Datei navigieren muss, legt das
# Programm neue Termine standardmäßig in einem festen Ordner im Benutzerprofil ab und
# kann diesen Ordner beim Start als Übersichtsliste anzeigen (öffnen/löschen). Termine,
# die anderswo liegen (z. B. auf einem USB-Stick), lassen sich weiterhin über einen
# normalen Datei-öffnen-Dialog einbinden - die Übersicht ist eine Erleichterung, keine
# Einschränkung.

def termine_ordner() -> Path:
    """Standard-Speicherort für Termin-Dateien - wird bei Bedarf angelegt. Liegt im
    Benutzerprofil (nicht neben dem Programm selbst), damit er unabhängig vom
    Installationsort ist und ein Update der Anwendung (siehe Installer) die
    vorhandenen Termine unberührt lässt."""
    ordner = Path.home() / "SHS-Pruefungsprogramm" / "Termine"
    ordner.mkdir(parents=True, exist_ok=True)
    return ordner


@dataclass
class TerminInfo:
    """Eintrag für die Terminübersicht im Startdialog."""
    pfad: str
    dateiname: str
    verein: str | None
    ort: str | None
    datum: str | None
    anzahl_teilnehmer: int
    lesbar: bool  # False = Datei vorhanden, aber nicht als Termin-Datenbank lesbar


def liste_termine(ordner: Path | None = None) -> list[TerminInfo]:
    """Listet alle Termin-Dateien (*.sqlite) in `ordner` (Standard: termine_ordner())
    mit ihren Stammdaten, neueste zuerst. Eine beschädigte/fremde Datei lässt die
    Übersicht nicht abstürzen, sondern taucht mit lesbar=False auf."""
    ordner = ordner or termine_ordner()
    ergebnisse: list[TerminInfo] = []
    for pfad in sorted(ordner.glob("*.sqlite")):
        try:
            with closing(sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)) as conn:
                conn.row_factory = sqlite3.Row
                v = conn.execute("SELECT * FROM veranstaltung WHERE id = 1").fetchone()
                anzahl = conn.execute("SELECT COUNT(*) FROM teilnehmer").fetchone()[0]
            ergebnisse.append(TerminInfo(
                pfad=str(pfad),
                dateiname=pfad.name,
                verein=v["verein"] if v else None,
                ort=v["ort"] if v else None,
                datum=v["datum"] if v else None,
                anzahl_teilnehmer=anzahl,
                lesbar=True,
            ))
        except sqlite3.DatabaseError:
            ergebnisse.append(TerminInfo(
                pfad=str(pfad), dateiname=pfad.name, verein=None, ort=None, datum=None,
                anzahl_teilnehmer=0, lesbar=False,
            ))
    ergebnisse.sort(key=lambda t: (t.datum or "", t.dateiname), reverse=True)
    return ergebnisse


def dateiname_vorschlagen(verein: str, datum: str) -> str:
    """Schlägt einen Dateinamen für einen neuen Termin aus Verein + Datum vor,
    z. B. '2026-09-19_SGV-Koeppern-eV.sqlite'."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", verein or "").strip("-") or "Termin"
    datum_teil = re.sub(r"[^0-9-]", "", datum or "") or "ohne-datum"
    return f"{datum_teil}_{slug}.sqlite"


# --- Terminverwaltung für PostgreSQL (mehrere Termine in EINER gemeinsamen Datenbank) --
#
# Pendant zum Terminübersicht-Abschnitt oben, für die geplante Podman/Web-Version mit
# Mehrbenutzerzugriff (siehe Grobkonzept/Fortschritt.md). Bei der SQLite-Desktop-Version
# entspricht ein Termin einer eigenen Datei - "alle Termine auflisten" heißt dort einfach
# "den Ordner auflisten" (liste_termine()), und "einen Termin löschen" heißt "die Datei
# löschen". Auf einem gemeinsam genutzten PostgreSQL-Server, auf den mehrere Nutzer
# gleichzeitig zugreifen, gibt es aber keine "Dateien" - stattdessen bekommt jeder Termin
# ein eigenes PostgreSQL-SCHEMA (ein Namensraum für Tabellen innerhalb einer Datenbank,
# z. B. "termin_17"), das dieselben Tabellen enthält wie eine SQLite-Termin-Datei. Das
# bildet dieselbe Isolation und dieselbe gezielte, vollständige Löschbarkeit nach, die im
# Grobkonzept aus Datenschutzgründen ausdrücklich gefordert ist (DROP SCHEMA ... CASCADE
# entspricht dabei dem Löschen einer Datei) - und der entscheidende Vorteil: alle ~40
# Datenfunktionen weiter oben in diesem Modul (add_teilnehmer, eintragen_ergebnis, ...)
# brauchen dafür KEINE Änderung. Welcher Termin gemeint ist, wird eine Ebene darüber
# entschieden, indem der search_path der Verbindung auf das passende Schema gesetzt wird
# (oeffne_termin_postgres()) - danach arbeiten alle übrigen Funktionen ganz normal auf
# `conn` weiter, exakt wie bei einer geöffneten SQLite-Termin-Datei.
#
# Eine schlanke "Registry"-Tabelle (im PostgreSQL-Standard-Schema "public", also
# außerhalb jedes einzelnen Termin-Schemas) führt Buch darüber, welche Schema-Namen zu
# welchem Termin gehören - das Pendant zum "Ordner mit *.sqlite-Dateien" der
# Desktop-Version. Absichtlich SCHLANK gehalten (nur id/schema_name/erstellt_am, keine
# Kopie von Verein/Ort/Datum): liste_termine_postgres() liest diese Angaben stattdessen
# direkt aus der "veranstaltung"-Tabelle jedes einzelnen Termin-Schemas, genau wie
# liste_termine() bei SQLite jede Datei kurz öffnet - so gibt es nur EINE Quelle der
# Wahrheit statt zwei, die auseinanderlaufen könnten.
#
# Bewusst NICHT Teil dieses Moduls: eine Auswertung ÜBER mehrere Termine hinweg (auf
# ausdrücklichen Wunsch nicht benötigt, siehe Chatverlauf) - jedes Schema bleibt
# vollständig eigenständig, wie bisher jede Termin-Datei.

_SCHEMA_NAME_MUSTER = re.compile(r"^termin_[0-9]+$")


def _pruefe_schema_name(schema_name: str) -> None:
    """Stellt sicher, dass `schema_name` dem erwarteten Muster ('termin_<Zahl>')
    entspricht, BEVOR er in einen SQL-Text eingesetzt wird (CREATE/DROP SCHEMA und SET
    search_path erlauben - anders als normale Werte - keine parametrisierten Platzhalter
    für Bezeichner). In der Praxis wird `schema_name` in diesem Modul ausschließlich
    intern aus der Registry-ID erzeugt (nie aus direkter Nutzereingabe übernommen) - diese
    Prüfung ist die zusätzliche Absicherung dagegen, falls sich das einmal ändert."""
    if not _SCHEMA_NAME_MUSTER.match(schema_name):
        raise ValueError(f"Ungültiger Schema-Name: {schema_name!r}")


def _setze_termin_suchpfad(conn, schema_name: str) -> None:
    """Wechselt die Verbindung auf das angegebene Schema ('public' für die
    Registry-Tabelle, sonst ein Termin-Schema) - siehe Abschnitts-Kommentar oben."""
    if schema_name != "public":
        _pruefe_schema_name(schema_name)
    conn.execute(f"SET search_path TO {schema_name}")


@dataclass
class TerminInfoPostgres:
    """Eintrag für die Terminübersicht der PostgreSQL/Web-Version - das Pendant zu
    TerminInfo (SQLite) oben, ohne die dort dateibezogenen Felder (pfad/dateiname/
    lesbar), dafür mit der registrierten ID, dem Schema-Namen und dem Zugangscode für
    die Web-Oberfläche (siehe pruefe_zugangscode_postgres() weiter unten)."""
    id: int
    schema_name: str
    zugangscode: str | None
    verein: str | None
    ort: str | None
    datum: str | None
    anzahl_teilnehmer: int
    erstellt_am: object  # datetime, vom psycopg2-Treiber geliefert


def verbinde_postgres_server(dsn: str) -> _PostgresConnection:
    """Öffnet eine Verbindung zum gemeinsam genutzten PostgreSQL-Server für die
    Terminverwaltung (anlegen/auflisten/öffnen/löschen, siehe die Funktionen unten) - das
    Pendant zum Anzeigen der Terminübersicht beim Programmstart der Desktop-Version
    (termine_ordner()/liste_termine()). Legt bei Bedarf die Registry-Tabelle an.

    Importiert psycopg2 bewusst erst hier statt am Modulanfang - siehe init_db_postgres()
    weiter oben für die Begründung.

    dsn: vollständiger PostgreSQL-Verbindungsstring (ohne Bezug zu einem bestimmten
    Termin - die Datenbank selbst wird von allen Terminen gemeinsam genutzt, siehe
    Abschnitts-Kommentar oben), z. B. "postgresql://benutzer:passwort@host:5432/shs".
    """
    import psycopg2
    import psycopg2.extras

    roh_verbindung = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    conn = _PostgresConnection(roh_verbindung)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS public.termin_registry ("
        "id INTEGER PRIMARY KEY, schema_name TEXT NOT NULL UNIQUE, "
        "zugangscode TEXT, "
        "erstellt_am TIMESTAMPTZ NOT NULL DEFAULT now())"
    )
    # Bereits vor der Zugangscode-Einführung angelegte Registry-Tabellen bekommen die
    # Spalte hier nachgerüstet (ADD COLUMN IF NOT EXISTS ist in PostgreSQL ein No-Op,
    # wenn die Spalte - z. B. durch das CREATE TABLE oben bei einer neuen Datenbank -
    # schon vorhanden ist) - dasselbe Prinzip wie _migriere_veranstaltung_spalten() für
    # einzelne Termine, hier aber genügt eine einzelne feste ALTER-Anweisung, da es nur
    # um eine einzige, unabhängige Spalte ohne Constraints geht.
    conn.execute("ALTER TABLE public.termin_registry ADD COLUMN IF NOT EXISTS zugangscode TEXT")
    conn.commit()
    return conn


def _eindeutigen_zugangscode_erzeugen(conn) -> str:
    """Erzeugt einen sechsstelligen, rein numerischen Zugangscode für den gemeinsamen
    Web-Login aller Richter/Helfer EINES Termins (siehe app_web.py) - kurz genug, um ihn
    am Prüfungstag mündlich durchzugeben oder auf ein Flipchart zu schreiben. `secrets`
    statt `random`, obwohl es sich nur um einen gemeinsamen PIN und kein Passwort für
    einzelne Nutzer handelt. Kollisionen mit einem bereits vergebenen Code sind bei sechs
    Ziffern extrem unwahrscheinlich, werden aber sicherheitshalber abgefangen (neu
    gezogen statt zwei Terminen versehentlich denselben Code zu geben)."""
    while True:
        code = "".join(secrets.choice("0123456789") for _ in range(6))
        treffer = conn.execute(
            "SELECT 1 AS vorhanden FROM termin_registry WHERE zugangscode = ?", (code,)
        ).fetchone()
        if not treffer:
            return code


def pruefe_zugangscode_postgres(conn, zugangscode: str) -> str | None:
    """Prüft einen von einem Richter/Helfer in der Web-Oberfläche eingegebenen
    Zugangscode gegen die Registry und liefert bei Erfolg den zugehörigen Schema-Namen
    (sonst None) - Grundlage für den Login in app_web.py. Whitespace am Rand wird
    toleriert (Tippen/Copy-Paste auf dem Handy)."""
    _setze_termin_suchpfad(conn, "public")
    zeile = conn.execute(
        "SELECT schema_name FROM termin_registry WHERE zugangscode = ?",
        (zugangscode.strip(),),
    ).fetchone()
    return zeile["schema_name"] if zeile else None


def erstelle_termin_postgres(conn) -> TerminInfoPostgres:
    """Legt einen neuen, leeren Termin als eigenes PostgreSQL-Schema an (Postgres-Pendant
    zu einer neuen, leeren Termin-Datei bei der SQLite-Desktop-Version) - Isolation und
    spätere gezielte Löschbarkeit bleiben dadurch erhalten (siehe loesche_termin_postgres
    unten). Enthält danach dieselben (leeren) Tabellen wie init_db()/init_db_postgres().
    Verein/Ort/Datum werden anschließend ganz normal über set_veranstaltung() gesetzt,
    NACHDEM mit oeffne_termin_postgres() auf das neue Schema gewechselt wurde (hier noch
    None, wie bei einer frisch angelegten SQLite-Termin-Datei vor dem ersten Ausfüllen).

    Die Schema-ID kommt aus einer eigenen Sequenz statt aus der Registry-Tabelle selbst
    (die 'id' dort könnte sonst erst NACH dem Einfügen der Zeile bekannt sein, obwohl der
    Schema-Name - der ja von der ID abhängt - schon beim Einfügen gebraucht wird). Eine
    Sequenz vergibt zudem nie zweimal denselben Wert, auch nicht nach einem Löschen - ein
    neuer Termin bekommt also nie versehentlich den Schema-Namen eines zuvor gelöschten.

    Bekommt außerdem direkt einen eindeutigen Zugangscode für den Web-Login zugewiesen
    (siehe _eindeutigen_zugangscode_erzeugen/pruefe_zugangscode_postgres oben)."""
    _setze_termin_suchpfad(conn, "public")
    conn.execute("CREATE SEQUENCE IF NOT EXISTS termin_registry_id_seq")
    neue_id = conn.execute("SELECT nextval('termin_registry_id_seq') AS id").fetchone()["id"]
    schema_name = f"termin_{neue_id}"
    zugangscode = _eindeutigen_zugangscode_erzeugen(conn)
    conn.execute(
        "INSERT INTO termin_registry (id, schema_name, zugangscode) VALUES (?, ?, ?)",
        (neue_id, schema_name, zugangscode),
    )
    conn.execute(f"CREATE SCHEMA {schema_name}")
    _setze_termin_suchpfad(conn, schema_name)
    _richte_schema_im_aktuellen_suchpfad_ein(conn)
    zeile = conn.execute(
        "SELECT erstellt_am FROM public.termin_registry WHERE id = ?", (neue_id,)
    ).fetchone()
    _setze_termin_suchpfad(conn, "public")
    return TerminInfoPostgres(
        id=neue_id, schema_name=schema_name, zugangscode=zugangscode, verein=None, ort=None, datum=None,
        anzahl_teilnehmer=0, erstellt_am=zeile["erstellt_am"],
    )


def oeffne_termin_postgres(conn, schema_name: str) -> None:
    """Wechselt die Verbindung auf das Schema eines bestehenden Termins (Postgres-Pendant
    zum Öffnen einer Termin-Datei bei der SQLite-Desktop-Version) und führt dabei - genau
    wie init_db()/init_db_postgres() - die Migrationen erneut aus, damit auch ein älterer
    Termin automatisch auf den aktuellen Stand gebracht wird. Alle übrigen Funktionen in
    diesem Modul (add_teilnehmer, eintragen_ergebnis, berechne_auswertung, ...) arbeiten
    danach ganz normal auf `conn` weiter - bis zum nächsten Wechsel (ein erneuter Aufruf
    hier, oder _setze_termin_suchpfad(conn, "public") für die Registry-Funktionen)."""
    _setze_termin_suchpfad(conn, schema_name)
    _migriere_veranstaltung_spalten(conn)
    _migriere_teilnehmer_spalten(conn)


def liste_termine_postgres(conn) -> list[TerminInfoPostgres]:
    """Postgres-Pendant zu liste_termine() (SQLite) - ein Registry-Eintrag entspricht
    dabei einer Datei im Termine-Ordner. Für jeden registrierten Termin wird kurz auf
    dessen Schema gewechselt, um Verein/Ort/Datum/Teilnehmerzahl zu lesen - genau die
    gleiche Vorgehensweise wie bei liste_termine(), das jede Datei kurz öffnet. Neueste
    zuerst (nach Datum, wie liste_termine())."""
    _setze_termin_suchpfad(conn, "public")
    eintraege = conn.execute(
        "SELECT id, schema_name, zugangscode, erstellt_am FROM termin_registry ORDER BY erstellt_am"
    ).fetchall()
    ergebnisse: list[TerminInfoPostgres] = []
    for eintrag in eintraege:
        schema_name = eintrag["schema_name"]
        _setze_termin_suchpfad(conn, schema_name)
        v = conn.execute("SELECT * FROM veranstaltung WHERE id = 1").fetchone()
        anzahl = conn.execute("SELECT COUNT(*) AS anzahl FROM teilnehmer").fetchone()["anzahl"]
        ergebnisse.append(TerminInfoPostgres(
            id=eintrag["id"], schema_name=schema_name, zugangscode=eintrag["zugangscode"],
            verein=v["verein"] if v else None, ort=v["ort"] if v else None,
            datum=v["datum"] if v else None, anzahl_teilnehmer=anzahl,
            erstellt_am=eintrag["erstellt_am"],
        ))
    _setze_termin_suchpfad(conn, "public")
    ergebnisse.sort(key=lambda t: (t.datum or "", t.schema_name), reverse=True)
    return ergebnisse


def loesche_termin_postgres(conn, schema_name: str) -> None:
    """Löscht einen Termin vollständig und gezielt (Postgres-Pendant zum Löschen einer
    Termin-Datei bei der SQLite-Desktop-Version - siehe Grobkonzept: aus
    Datenschutzgründen ausdrücklich geforderte, gezielte Löschmöglichkeit, ohne andere
    Termine zu berühren). DROP SCHEMA ... CASCADE entfernt dabei alle Tabellen/Daten
    dieses einen Termins auf einen Schlag."""
    _pruefe_schema_name(schema_name)
    _setze_termin_suchpfad(conn, "public")
    conn.execute(f"DROP SCHEMA {schema_name} CASCADE")
    conn.execute("DELETE FROM termin_registry WHERE schema_name = ?", (schema_name,))
    conn.commit()


# --- Austausch zwischen einer SQLite-Termin-Datei (Desktop) und einem PostgreSQL-
# Termin-Schema (Web) ---------------------------------------------------------
#
# Für die geplante V1 der Web-Version ("nur Ergebniseingabe", siehe Chatverlauf) wird ein
# Termin weiterhin ganz normal in der Desktop-Version angelegt/geplant (Teilnehmer,
# Zeitplan, ...) und erst VOR dem Prüfungstag als eigener PostgreSQL-Termin
# "veröffentlicht" (exportiere_termin_nach_postgres) - danach tragen mehrere Richter
# gleichzeitig über die Web-Oberfläche Ergebnisse ein. NACH der Prüfung werden diese
# Ergebnisse zurück in dieselbe SQLite-Datei geholt (importiere_ergebnisse_aus_postgres),
# damit PDF-Export/Auswertung/Zeitplan wie bisher in der Desktop-Version weiterlaufen -
# die PostgreSQL-Datenbank ist also nur für den Prüfungstag selbst "die Wahrheit", davor
# und danach bleibt es die SQLite-Datei. Siehe sync_termin.py für das Kommandozeilen-
# Werkzeug, das diese beiden Funktionen aufruft.
#
# Die eigentliche Kopierlogik (kopiere_termin_daten/importiere_ergebnisse_nach_startnummer)
# ist bewusst dialektunabhängig gehalten - sie arbeitet ausschließlich über bereits
# vorhandene, für beide Datenbanken getestete Funktionen (add_teilnehmer, eintragen_ergebnis,
# ...) bzw. portables SQL. Dadurch lässt sie sich, genau wie die übrige Kernlogik dieses
# Moduls, vollständig mit zwei SQLite-Verbindungen automatisiert testen, ohne dass dafür
# psycopg2 installiert sein müsste (siehe TestTerminSync in test_db.py) - nur die dünnen
# Wrapper-Funktionen exportiere_termin_nach_postgres/importiere_ergebnisse_aus_postgres
# selbst binden sich an eine echte PostgreSQL-Verbindung.


def kopiere_termin_daten(quelle_conn, ziel_conn) -> dict[int, int]:
    """Kopiert Veranstaltungsdaten und alle Teilnehmer (inkl. bereits vorhandener
    Ergebnisse, falls schon welche eingetragen waren) von quelle_conn nach ziel_conn.

    ziel_conn sollte auf ein leeres Schema/eine leere Datenbank zeigen (z. B. direkt nach
    erstelle_termin_postgres()) - vorhandene Teilnehmer dort werden NICHT gelöscht, die
    kopierten kommen einfach hinzu. Liefert die Zuordnung alte Teilnehmer-ID (in
    quelle_conn) -> neue Teilnehmer-ID (in ziel_conn)."""
    veranstaltung = get_veranstaltung(quelle_conn)
    if veranstaltung:
        set_veranstaltung(
            ziel_conn,
            verein=veranstaltung["verein"],
            datum=veranstaltung["datum"],
            ort=veranstaltung.get("ort"),
            vereins_nr=veranstaltung.get("vereins_nr"),
            pruefungsnummer=veranstaltung.get("pruefungsnummer"),
            wertungsrichter_1=veranstaltung.get("wertungsrichter_1"),
            wertungsrichter_2=veranstaltung.get("wertungsrichter_2"),
            pruefungsleiter=veranstaltung.get("pruefungsleiter"),
            pruefungsgebuehr_ed=veranstaltung.get("pruefungsgebuehr_ed"),
            pruefungsgebuehr_dk=veranstaltung.get("pruefungsgebuehr_dk"),
            zeitplan_start=veranstaltung.get("zeitplan_start"),
        )

    id_zuordnung: dict[int, int] = {}
    for alt in list_teilnehmer(quelle_conn):
        neu = NeuerTeilnehmer(
            nachname=alt["nachname"], vorname=alt["vorname"], rufname_hund=alt["rufname_hund"],
            art=alt["art"], stufe=alt["stufe"], disziplin=alt["disziplin"],
            verein=alt.get("verein"), zwingername=alt.get("zwingername"), geschlecht=alt.get("geschlecht"),
            schulterhoehe_cm=alt.get("schulterhoehe_cm"), chip_nr=alt.get("chip_nr"),
            startnummer=alt.get("startnummer"),
            gegenstand_1=alt.get("gegenstand_1"), gegenstand_2=alt.get("gegenstand_2"),
            gegenstand_3=alt.get("gegenstand_3"),
            gegenstand_1_disziplin=alt.get("gegenstand_1_disziplin"),
            gegenstand_2_disziplin=alt.get("gegenstand_2_disziplin"),
            gegenstand_3_disziplin=alt.get("gegenstand_3_disziplin"),
            bezahlt=bool(alt.get("bezahlt")),
            verband=alt.get("verband"), mitgliedsnummer=alt.get("mitgliedsnummer"), wurftag=alt.get("wurftag"),
            strasse=alt.get("strasse"), hausnummer=alt.get("hausnummer"), plz=alt.get("plz"), ort=alt.get("ort"),
            email=alt.get("email"), telefon=alt.get("telefon"),
        )
        neue_id = add_teilnehmer(ziel_conn, neu)
        id_zuordnung[alt["id"]] = neue_id

        alte_ergebnisse = get_ergebnis(quelle_conn, alt["id"])
        if alte_ergebnisse:
            for disziplin, (spalte_suche, spalte_anzeige) in DISZIPLIN_SPALTEN.items():
                suche, anzeige = alte_ergebnisse[spalte_suche], alte_ergebnisse[spalte_anzeige]
                if suche is not None or anzeige is not None:
                    eintragen_ergebnis(ziel_conn, neue_id, disziplin, suche, anzeige)

    return id_zuordnung


def exportiere_termin_nach_postgres(sqlite_conn: sqlite3.Connection, postgres_conn) -> TerminInfoPostgres:
    """Veröffentlicht einen bestehenden SQLite-Termin (Desktop) als neuen, eigenständigen
    PostgreSQL-Termin (eigenes Schema, siehe erstelle_termin_postgres) für die
    Mehrbenutzer-Ergebniserfassung am Prüfungstag - Veranstaltungsdaten und alle
    Teilnehmer (inkl. bereits vorhandener Ergebnisse) werden dabei übernommen. Der
    zurückgegebene Zugangscode ist das, was die Richter für den Login in der
    Web-Oberfläche brauchen (siehe sync_termin.py).

    Der SQLite-Termin bleibt dabei unverändert (reiner Export, keine Rückwirkung) - erst
    nach der Prüfung holt importiere_ergebnisse_aus_postgres() die dort eingetragenen
    Ergebnisse zurück."""
    neuer_termin = erstelle_termin_postgres(postgres_conn)
    kopiere_termin_daten(sqlite_conn, postgres_conn)
    postgres_conn.commit()
    # anzahl_teilnehmer/verein/ort/datum in erstelle_termin_postgres()s Rückgabe waren noch
    # leer/0 (vor dem Kopieren) - aktuellen Stand für die Rückgabe nachladen.
    _setze_termin_suchpfad(postgres_conn, "public")
    aktuelle = [t for t in liste_termine_postgres(postgres_conn) if t.schema_name == neuer_termin.schema_name]
    return aktuelle[0] if aktuelle else neuer_termin


@dataclass
class ImportBericht:
    """Ergebnis von importiere_ergebnisse_nach_startnummer()/importiere_ergebnisse_aus_postgres() -
    zur Anzeige/Protokollierung nach einem Import (siehe sync_termin.py)."""
    aktualisiert: int
    # "Nachname, Vorname" von Teilnehmern in der Quelle ohne Startnummer - können nicht
    # zugeordnet werden (Zuordnung erfolgt ausschließlich über die Startnummer, siehe
    # importiere_ergebnisse_nach_startnummer).
    ohne_startnummer_uebersprungen: list[str]
    # Startnummern aus der Quelle, zu denen es im Ziel keinen Teilnehmer mit derselben
    # Startnummer gibt (z. B. wenn ein Teilnehmer nach dem Export noch umbenannt/gelöscht
    # oder die Startnummer geändert wurde).
    nicht_gefunden: list[str]


def importiere_ergebnisse_nach_startnummer(quelle_conn, ziel_conn) -> ImportBericht:
    """Kernlogik: überträgt für jeden Teilnehmer in quelle_conn mit gesetzter Startnummer
    die dort eingetragenen Ergebnisse auf den Teilnehmer mit DERSELBEN Startnummer in
    ziel_conn. Zuordnung über die Startnummer statt über die interne ID, da beide
    Datenbanken beim Export unabhängig voneinander vergebene IDs bekommen haben (siehe
    kopiere_termin_daten oben) - die Startnummer ist das einzige beiden Seiten gemeinsame,
    eindeutige Merkmal. Überschreibt dabei die Ergebnisse im Ziel vollständig mit dem
    Stand der Quelle (nach der Prüfung gilt die Web-Erfassung als maßgeblich)."""
    ziel_nach_startnummer = {
        t["startnummer"]: t["id"] for t in list_teilnehmer(ziel_conn) if t.get("startnummer") is not None
    }
    aktualisiert = 0
    ohne_startnummer: list[str] = []
    nicht_gefunden: list[str] = []
    for quelle_teilnehmer in list_teilnehmer(quelle_conn):
        startnummer = quelle_teilnehmer.get("startnummer")
        name = f"{quelle_teilnehmer['nachname']}, {quelle_teilnehmer['vorname']}"
        if startnummer is None:
            ohne_startnummer.append(name)
            continue
        ziel_id = ziel_nach_startnummer.get(startnummer)
        if ziel_id is None:
            nicht_gefunden.append(str(startnummer))
            continue
        ergebnis = get_ergebnis(quelle_conn, quelle_teilnehmer["id"])
        if not ergebnis:
            continue
        hat_wert = False
        for disziplin, (spalte_suche, spalte_anzeige) in DISZIPLIN_SPALTEN.items():
            suche, anzeige = ergebnis[spalte_suche], ergebnis[spalte_anzeige]
            if suche is not None or anzeige is not None:
                eintragen_ergebnis(ziel_conn, ziel_id, disziplin, suche, anzeige)
                hat_wert = True
        if hat_wert:
            aktualisiert += 1
    return ImportBericht(
        aktualisiert=aktualisiert,
        ohne_startnummer_uebersprungen=ohne_startnummer,
        nicht_gefunden=nicht_gefunden,
    )


def importiere_ergebnisse_aus_postgres(postgres_conn, schema_name: str, sqlite_conn: sqlite3.Connection) -> ImportBericht:
    """Holt nach der Prüfung die über die Web-Oberfläche eingetragenen Ergebnisse aus dem
    angegebenen PostgreSQL-Termin-Schema zurück in die lokale SQLite-Termin-Datei (siehe
    sync_termin.py) - Gegenstück zu exportiere_termin_nach_postgres()."""
    oeffne_termin_postgres(postgres_conn, schema_name)
    return importiere_ergebnisse_nach_startnummer(postgres_conn, sqlite_conn)


# --- Datensicherung (Export/Import aller Termine als ZIP, optional passwortgeschützt) ---
#
# Nutzt pyzipper (reines Python, keine kompilierten Zusatzabhängigkeiten) statt des
# eingebauten zipfile-Moduls, da zipfile zwar passwortgeschützte ZIPs LESEN, aber keine
# mit echter (AES-256-)Verschlüsselung SCHREIBEN kann. Ein Backup ohne Passwort wird
# trotzdem mit dem einfacheren, garantiert überall (z.B. Windows-Explorer) kompatiblen
# zipfile-Modul erzeugt.


class PasswortFalschError(Exception):
    """Ein Sicherungs-ZIP ist passwortgeschützt und das angegebene Passwort fehlt oder
    ist falsch (siehe sicherung_inhalt()/sicherung_wiederherstellen())."""


def eindeutigen_dateinamen_finden(ordner: Path, gewuenschter_name: str) -> str:
    """Hängt bei einem im Ordner bereits vergebenen Dateinamen einen Zähler an (z.B.
    'Termin (2).sqlite'), bis ein noch freier Name gefunden ist - für die Option "als
    Kopie importieren" beim Wiederherstellen einer Sicherung (siehe app.py)."""
    ordner = Path(ordner)
    if not (ordner / gewuenschter_name).exists():
        return gewuenschter_name
    ziel = Path(gewuenschter_name)
    stamm, endung = ziel.stem, ziel.suffix
    zaehler = 2
    while (ordner / f"{stamm} ({zaehler}){endung}").exists():
        zaehler += 1
    return f"{stamm} ({zaehler}){endung}"


def sicherung_erstellen(
    ziel_pfad: str, passwort: str | None = None, nur_dateien: list[str] | None = None, ordner: Path | None = None
) -> int:
    """Erstellt ein ZIP-Backup der Termin-Dateien aus `ordner` (Standard: termine_ordner()).

    nur_dateien: optionale Liste von Dateinamen (nicht volle Pfade) - falls angegeben,
    werden nur diese gesichert, sonst ALLE *.sqlite-Dateien im Ordner.
    passwort: falls angegeben (nicht leer), wird das ZIP AES-256-verschlüsselt.
    Gibt die Anzahl der gesicherten Termin-Dateien zurück.
    Wirft ValueError, falls es nichts zu sichern gibt.
    """
    ordner = ordner or termine_ordner()
    dateien = sorted(p for p in ordner.glob("*.sqlite") if p.is_file())
    if nur_dateien is not None:
        gewaehlt = set(nur_dateien)
        dateien = [p for p in dateien if p.name in gewaehlt]
    if not dateien:
        raise ValueError("Es gibt keine Termine zum Sichern.")

    if passwort:
        with pyzipper.AESZipFile(
            ziel_pfad, "w", compression=pyzipper.ZIP_LZMA, encryption=pyzipper.WZ_AES
        ) as zf:
            zf.setpassword(passwort.encode("utf-8"))
            for datei in dateien:
                zf.write(datei, arcname=datei.name)
    else:
        with zipfile.ZipFile(ziel_pfad, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for datei in dateien:
                zf.write(datei, arcname=datei.name)
    return len(dateien)


def sicherung_inhalt(zip_pfad: str, passwort: str | None = None) -> list[str]:
    """Liefert die Namen der Termin-Dateien (*.sqlite) in einem Sicherungs-ZIP, ohne sie
    zu entpacken - Grundlage für die Konflikterkennung vor dem eigentlichen
    Wiederherstellen (siehe sicherung_wiederherstellen() und app.py).

    Wirft PasswortFalschError, wenn das ZIP passwortgeschützt ist und `passwort` fehlt
    oder falsch ist; ValueError, wenn die Datei kein gültiges ZIP ist oder keine
    Termin-Dateien enthält.
    """
    try:
        with pyzipper.AESZipFile(zip_pfad) as zf:
            if passwort:
                zf.setpassword(passwort.encode("utf-8"))
            namen = [n for n in zf.namelist() if n.lower().endswith(".sqlite")]
            if not namen:
                raise ValueError("Das ZIP enthält keine Termin-Dateien (.sqlite).")
            # Erzwingt die Passwortprüfung sofort (Lesen der ersten Datei), statt erst
            # beim eigentlichen Wiederherstellen mittendrin zu scheitern.
            zf.read(namen[0])
    except RuntimeError as exc:
        if "password" in str(exc).lower():
            raise PasswortFalschError(
                "Das Passwort ist falsch, oder die Datei ist passwortgeschützt und es "
                "wurde keines angegeben."
            ) from exc
        raise
    except (zipfile.BadZipFile, pyzipper.zipfile.BadZipFile) as exc:
        # pyzipper verwendet eine eigene, von zipfile GEERBTE/geforkte BadZipFile-Klasse
        # (pyzipper.zipfile.BadZipFile) statt der Standardbibliotheks-Klasse - beide
        # werden hier abgefangen, da AESZipFile ausschließlich die eigene wirft (per
        # echtem CI-Testlauf bestätigt).
        raise ValueError("Das ist keine gültige ZIP-Datei.") from exc
    return sorted(namen)


def sicherung_wiederherstellen(
    zip_pfad: str, entscheidungen: dict[str, str], passwort: str | None = None, ordner: Path | None = None
) -> list[str]:
    """Entpackt ausgewählte Termin-Dateien aus einem Sicherungs-ZIP in `ordner`
    (Standard: termine_ordner()).

    entscheidungen: {Dateiname im ZIP: Zieldateiname im Zielordner} - ein von
    sicherung_inhalt() gelieferter Name, der hier NICHT vorkommt, wird übersprungen
    (z.B. weil der Nutzer diesen Termin beim Konflikt-Dialog übersprungen hat). Bei
    Namensgleichheit mit einer vorhandenen Datei wird diese überschrieben; für "als Kopie
    importieren" vorher eindeutigen_dateinamen_finden() für einen freien Zielnamen
    verwenden. Gibt die Liste der tatsächlich geschriebenen Zieldateinamen zurück.
    """
    ordner = ordner or termine_ordner()
    geschrieben: list[str] = []
    try:
        with pyzipper.AESZipFile(zip_pfad) as zf:
            if passwort:
                zf.setpassword(passwort.encode("utf-8"))
            for quelle, ziel in entscheidungen.items():
                daten = zf.read(quelle)
                (ordner / ziel).write_bytes(daten)
                geschrieben.append(ziel)
    except RuntimeError as exc:
        if "password" in str(exc).lower():
            raise PasswortFalschError("Das Passwort ist falsch.") from exc
        raise
    return geschrieben
