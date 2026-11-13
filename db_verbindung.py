"""
Verbindung, Schema, Migrationen und der PostgreSQL-Adapter (_PostgresConnection).

Aus db.py ausgelagert (11.11.2026, Schichtenaufteilung); db.py bleibt als Fassade und reicht alle
Namen weiter. Code unverändert. Siehe Architektur.md.
"""

from __future__ import annotations
import functools
import os
import re
import sqlite3
import unicodedata
from contextlib import closing, suppress
from dataclasses import dataclass

from shs_core import ANZEIGE_MAX, SUCHE_MAX



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
    -- Nutzerwunsch (20.09.): bis zu 5 Wertungsrichter statt bisher fest 2 (manche
    -- Prüfungen sind entsprechend größer besetzt) - alle weiterhin optional.
    wertungsrichter_1 TEXT,
    wertungsrichter_2 TEXT,
    wertungsrichter_3 TEXT,
    wertungsrichter_4 TEXT,
    wertungsrichter_5 TEXT,
    pruefungsleiter TEXT,
    -- Nutzerwunsch (28.09.2026): Kopfangaben für das ausfüllbare Anmeldeformular
    -- (pdf_export.erstelle_anmeldeformular_pdf). Veranstalter ist dort "verein" oben.
    -- angebotene_pruefungen: kommagetrennte Kürzel aus ALLE_PRUEFUNGEN (z.B.
    -- "DK1,ED2-Trümmerfeld"), steuert, welche Prüfungen im Formular ankreuzbar sind.
    verband TEXT,
    meldestelle TEXT,
    angebotene_pruefungen TEXT,
    -- UX-Test 02.10.2026, U1: Startnummern-Bereich je Prüfung für die Sammelvergabe,
    -- z. B. "DK1=1-20,ED1-Trümmerfeld=21-40" (Kürzel wie bei angebotene_pruefungen).
    startnummer_bereiche TEXT,
    -- UX-Test 02.10.2026, U2: Mindestabstand (Minuten) zwischen zwei Starts desselben
    -- Teams, z. B. DK-Disziplinen nacheinander; leer = 10 Minuten.
    dk_mindestabstand TEXT,
    -- Marco 09.10.2026: Standardgröße eines Startnummern-Bereichs je Prüfung für
    -- "Bereiche automatisch festlegen" im Veranstaltungsdialog; leer = 20.
    startnummer_bereichsgroesse TEXT,
    -- Marco 09.11.2026: Abrechnung Leistungsrichter (siehe lr_abrechnung.py): Satz je
    -- Kilometer, Tagespauschale (je Termin, leer = Standard) und die Eingaben je Richter
    -- (JSON, Position 1-5).
    lr_km_satz TEXT,
    lr_tagespauschale TEXT,
    lr_abrechnung TEXT,
    -- Marco 09.11.2026: Checkliste zum Abhaken im Reiter Verwaltung (checkliste.py), JSON-Liste
    -- der erledigten Schritte.
    checkliste TEXT,
    -- Marco 09.11.2026: eigene Kategorien und Punkte der Checkliste (JSON, siehe checkliste.py).
    checkliste_eigene TEXT
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
    -- Nutzerwunsch 02.10.2026: Teilnehmer ist nicht erschienen ("keine Teilnahme"). Bleibt
    -- in der Teilnehmerliste (ausgegraut) und in der Prüfungsleitungs-Übersicht, fällt aber
    -- aus allen nachgelagerten Prozessen/Wertungen heraus - siehe setze_keine_teilnahme()
    -- und list_teilnehmer(nur_teilnehmende=True).
    keine_teilnahme INTEGER NOT NULL DEFAULT 0 CHECK (keine_teilnahme IN (0, 1)),
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
    -- Rasse/Tollwutimpfung sowie ein optionaler Halter-Block (Nutzerwunsch 20.09., siehe
    -- _TEILNEHMER_NEUE_SPALTEN) - der Halter (Hundeeigentümer) kann laut Meldeformular
    -- eine andere Person als der Hundeführer (nachname/vorname oben) sein. Alle Felder
    -- bleiben leer (NULL), solange kein abweichender Halter angegeben wird.
    rasse TEXT,
    tollwutimpfung_bis TEXT,
    -- Geburtsdatum des Hundeführers/der Hundeführerin (Nutzerwunsch 21.09., Statistik:
    -- Jugendliche unter 18 Jahren müssen gesondert ausgewiesen werden) - siehe
    -- ist_jugendlicher() weiter unten. Optional, da nicht bei jedem Verband/Verein
    -- verpflichtend.
    geburtsdatum TEXT,
    halter_vorname TEXT,
    halter_nachname TEXT,
    halter_strasse TEXT,
    halter_hausnummer TEXT,
    halter_plz TEXT,
    halter_ort TEXT,
    halter_mitgliedsverein TEXT,
    halter_mitgliedsnummer TEXT,
    halter_lu_nr TEXT,
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
    anzeige_behaeltnis INTEGER CHECK (anzeige_behaeltnis BETWEEN 0 AND 40),
    -- Disqualifikation/Abbruch (Nutzerwunsch 21.09.): zwei getrennte, unabhängige Status
    -- je Teilnehmer (bewusst NICHT ein gemeinsamer Status) - bei gesetztem Status wird
    -- keine aus den Punktwerten berechnete Wertnote gebildet (siehe berechne_auswertung()
    -- unten). Boolean-Konvention wie teilnehmer.bezahlt (INTEGER 0/1).
    disqualifiziert INTEGER NOT NULL DEFAULT 0 CHECK (disqualifiziert IN (0, 1)),
    abbruch INTEGER NOT NULL DEFAULT 0 CHECK (abbruch IN (0, 1)),
    -- R7 (Marco 01.11.2026): Grund eines Abbruchs (shs_core.ABBRUCH_GRUENDE), NULL = ohne
    -- Grund (Daten vor R7). abbruch bleibt zusätzlich 1, damit ältere Versionen ihn erkennen.
    abbruch_grund TEXT CHECK (abbruch_grund IS NULL OR abbruch_grund IN
        ('ungehorsam', 'verletzung_hund', 'krankheit', 'verletzung_hf')),
    -- S1 (Marco 03.10.2026): Sieger eines Stechens bei Gleichstand um Platz 1 (0/1).
    -- Gilt nur, solange der Gleichstand besteht (siehe shs_core.berechne_rangliste).
    stechen_sieger INTEGER NOT NULL DEFAULT 0 CHECK (stechen_sieger IN (0, 1))
);

-- Zeitplan: je Termin beliebig viele "Richter"-Spuren (zeitplan_richter), jede
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
    -- UX-Test 02.10.2026, U2: Startversatz innerhalb des Blocks - mit welchem Team der
    -- Block beginnt (Rotation), damit parallele DK-Blöcke nicht dasselbe Team gleichzeitig
    -- ansetzen. 0 = Reihenfolge nach Startnummer.
    startversatz INTEGER NOT NULL DEFAULT 0,
    -- R-B20 (Marco 05.11.2026): feste Uhrzeit einer Pause („HH:MM“) - ist der Richter vorher
    -- fertig, beginnt sie trotzdem erst dann (Lücke davor). NULL = direkt im Anschluss.
    fest_um TEXT,
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

# QS-Fund (19./20.09.): _PostgresConnection.execute() übersetzte '?'-Platzhalter bisher
# über ein blindes sql.replace("?", "%s") auf dem GESAMTEN SQL-Text - das hätte auch ein
# echtes, als reiner Text gemeintes Fragezeichen innerhalb eines SQL-String-Literals
# (z.B. '...?' als fest im Code stehender Vergleichs- oder Anzeigetext) fälschlich
# mitersetzt und die Abfrage unbemerkt kaputt gemacht. Kommt aktuell nirgends in diesem
# Modul vor, ist aber eine Falle für künftige Änderungen. Dieser Regex erkennt einfach
# gequotete String-Literale ('...', inkl. der SQL-Schreibweise '' für ein eingebettetes
# Apostroph) UND einzelne '?'-Zeichen in einem Durchlauf - _uebersetze_platzhalter()
# unten ersetzt dabei gezielt nur die '?'-Treffer und lässt String-Literale unangetastet
# durchlaufen, statt sie versehentlich mitzuersetzen.
_PLATZHALTER_ODER_STRING_RE = re.compile(r"'(?:[^']|'')*'|\?")

def _uebersetze_platzhalter(sql: str) -> str:
    """Ersetzt '?'-Platzhalter durch PostgreSQLs '%s' - siehe Kommentar bei
    _PLATZHALTER_ODER_STRING_RE oben für die Begründung, warum das NICHT einfach per
    sql.replace("?", "%s") auf dem gesamten Text passiert."""
    return _PLATZHALTER_ODER_STRING_RE.sub(lambda m: "%s" if m.group(0) == "?" else m.group(0), sql)

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
    execute()/executescript()/commit()/rollback()/close(), '?'-Platzhalter statt psycopg2s '%s', sowie
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
        sql_pg = _uebersetze_platzhalter(sql)
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

    def rollback(self) -> None:
        self._roh_verbindung.rollback()

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
    # Nutzerwunsch (20.09.): Wertungsrichter 3-5, siehe Kommentar bei SCHEMA oben.
    "wertungsrichter_3", "wertungsrichter_4", "wertungsrichter_5",
    # Nutzerwunsch (28.09.2026): Anmeldeformular, siehe Kommentar bei SCHEMA oben.
    "verband", "meldestelle", "angebotene_pruefungen",
    # UX-Test 02.10.2026, U1: Startnummern-Bereiche, siehe Kommentar bei SCHEMA oben.
    "startnummer_bereiche",
    # UX-Test 02.10.2026, U2: Mindestabstand für Starts desselben Teams.
    "dk_mindestabstand",
    # Marco 09.10.2026: Standardgröße der Startnummern-Bereiche.
    "startnummer_bereichsgroesse",
    # Marco 09.11.2026: Abrechnung Leistungsrichter, siehe Kommentar bei SCHEMA oben.
    "lr_km_satz", "lr_tagespauschale", "lr_abrechnung",
    # Marco 09.11.2026: Checkliste, siehe Kommentar bei SCHEMA oben.
    "checkliste", "checkliste_eigene",
]

@dataclass(frozen=True)
class Pruefungsangebot:
    """Eine im Anmeldeformular ankreuzbare Prüfung (Art + Leistungsklasse + ggf.
    Disziplin). `kuerzel` ist die Speicherform in veranstaltung.angebotene_pruefungen und
    zugleich Teil des PDF-Feldnamens ("pruefung_<kuerzel>")."""
    kuerzel: str
    art: str
    stufe: int
    disziplin: str | None
    bezeichnung: str

# Reihenfolge wie im bisherigen Word-Anmeldeformular: DK, Trümmer, Behältnisse, Fläche,
# jeweils LK 1-3. Die Bezeichnung gilt seit dem Nachtest 2 (N5, Marco 04.11.2026) überall im
# Programm (siehe leistungsklasse_label) - vorher stand „DK-LK 1“ / „Trümmer LK 1“ nur hier und
# sonst „DK LK 1“ / „ED LK 1 Trümmerfeld“.
ALLE_PRUEFUNGEN: list[Pruefungsangebot] = [
    Pruefungsangebot(f"DK{stufe}", "DK", stufe, None, f"DK LK {stufe}") for stufe in (1, 2, 3)
] + [
    Pruefungsangebot(f"ED{stufe}-{disziplin}", "ED", stufe, disziplin, f"{kurz} LK {stufe}")
    for disziplin, kurz in (("Trümmerfeld", "Trümmer"), ("Behältnisstrecke", "Behältnisse"), ("Flächensuche", "Fläche"))
    for stufe in (1, 2, 3)
]

_PRUEFUNG_NACH_KUERZEL = {p.kuerzel: p for p in ALLE_PRUEFUNGEN}

_PRUEFUNG_NACH_BEZEICHNUNG = {p.bezeichnung: p for p in ALLE_PRUEFUNGEN}

_FORMULAR_POSITION = {p.bezeichnung: nummer for nummer, p in enumerate(ALLE_PRUEFUNGEN)}

def pruefungen_als_text(kuerzel: list[str]) -> str | None:
    """Speicherform für veranstaltung.angebotene_pruefungen (None bei leerer Auswahl).
    Unbekannte Kürzel werfen ValueError; die Reihenfolge folgt ALLE_PRUEFUNGEN."""
    unbekannt = [k for k in kuerzel if k not in _PRUEFUNG_NACH_KUERZEL]
    if unbekannt:
        raise ValueError(f"unbekannte Prüfung(en): {', '.join(unbekannt)}")
    gewaehlt = set(kuerzel)
    return ",".join(p.kuerzel for p in ALLE_PRUEFUNGEN if p.kuerzel in gewaehlt) or None

def angebotene_pruefungen(veranstaltung: dict | None) -> list[Pruefungsangebot]:
    """Die für den Termin angebotenen Prüfungen in Formularreihenfolge (leer, wenn noch
    keine hinterlegt sind). Unbekannte Kürzel in der Datenbank werden ignoriert."""
    text = (veranstaltung or {}).get("angebotene_pruefungen") or ""
    gewaehlt = {k.strip() for k in text.split(",") if k.strip()}
    return [p for p in ALLE_PRUEFUNGEN if p.kuerzel in gewaehlt]

def pruefung_nach_kuerzel(kuerzel: str) -> Pruefungsangebot | None:
    return _PRUEFUNG_NACH_KUERZEL.get(kuerzel)

def pruefung_nach_bezeichnung(bezeichnung: str) -> Pruefungsangebot | None:
    """Die Prüfung zu einer Bezeichnung wie „Trümmer LK 2“ (Filter, Statistik) oder None."""
    return _PRUEFUNG_NACH_BEZEICHNUNG.get(bezeichnung)

# Feste Feldnamen des ausfüllbaren Anmeldeformulars (pdf_export.erstelle_anmeldeformular_pdf)
# -> Spaltenname wie in db_import.CSV_IMPORT_SPALTEN. Einzige Quelle der Wahrheit für
# Erzeugung UND Import (db_import.importiere_anmeldeformular_pdf), damit beide nie
# auseinanderlaufen. Nicht in der Datenbank abgebildete Angaben (18 Jahre ja/nein) haben
# eigene Feldnamen unten, ebenso Prüfungs-Kreuze, Gegenstände, Chip/Täto und Geschlecht.
ANMELDEFORMULAR_TEXTFELDER: dict[str, str] = {
    "vorname": "vorname", "nachname": "nachname",
    "strasse": "strasse", "hausnummer": "hausnummer", "plz": "plz", "ort": "ort",
    "mitgliedsnummer": "mitgliedsnummer", "telefon": "telefon", "email": "email",
    "verein": "verein", "verband": "verband",
    "halter_vorname": "halter_vorname", "halter_nachname": "halter_nachname",
    "halter_strasse": "halter_strasse", "halter_hausnummer": "halter_hausnummer",
    "halter_plz": "halter_plz", "halter_ort": "halter_ort",
    "halter_mitgliedsnummer": "halter_mitgliedsnummer",
    "halter_mitgliedsverein": "halter_mitgliedsverein", "halter_lu_nr": "halter_lu_nr",
    "zwingername": "zwingername", "rufname_hund": "rufname_hund", "rasse": "rasse",
    "wurftag": "wurftag", "schulterhoehe_cm": "schulterhoehe_cm",
    "tollwutimpfung_bis": "tollwutimpfung_bis",
    # Nummer aus dem Chip-/Täto-Feld; landet in chip_nr (bei Täto mit Präfix "Täto ").
    "kennzeichnung_nr": "chip_nr",
}

ANMELDEFORMULAR_PRUEFUNG_PRAEFIX = "pruefung_"      # Checkbox je Pruefungsangebot.kuerzel

ANMELDEFORMULAR_KENNZEICHNUNG_CHIP = "kennzeichnung_chip"   # Checkbox

ANMELDEFORMULAR_KENNZEICHNUNG_TAETO = "kennzeichnung_taeto"  # Checkbox

ANMELDEFORMULAR_HUENDIN = "geschlecht_huendin"      # Checkbox

ANMELDEFORMULAR_RUEDE = "geschlecht_ruede"          # Checkbox

ANMELDEFORMULAR_VOLLJAEHRIG_JA = "volljaehrig_ja"   # Checkbox, wird nicht gespeichert

ANMELDEFORMULAR_VOLLJAEHRIG_NEIN = "volljaehrig_nein"  # Checkbox, wird nicht gespeichert

ANMELDEFORMULAR_UNTERSCHRIFT_DATUM = "unterschrift_datum"  # Textfeld, wird nicht gespeichert

def anmeldeformular_gegenstand_feld(stufe: int, nummer: int) -> str:
    """Feldname des n-ten Gegenstands (1..stufe) für Leistungsklasse `stufe`."""
    return f"gegenstand_lk{stufe}_{nummer}"

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

def _migriere_spalten(conn, tabelle: str, neue_spalten: list) -> None:
    """Gemeinsame Hilfsfunktion für _migriere_veranstaltung_spalten/
    _migriere_teilnehmer_spalten/_migriere_ergebnisse_spalten unten (waren vorher drei bis
    auf Tabellen-/Spaltenliste identische Funktionen, siehe Codeprüfung 21.09.): ergänzt in
    `tabelle` alle in `neue_spalten` genannten, noch fehlenden Spalten per ALTER TABLE ADD
    COLUMN (CREATE TABLE IF NOT EXISTS allein reicht dafür nicht, da die Tabelle in
    Altdateien schon ohne diese Spalten existiert - keine Datenverluste, bestehende Zeilen
    bekommen für die neue Spalte einfach NULL). Funktioniert dialektunabhängig, siehe
    _vorhandene_spalten(). Jeder Eintrag in `neue_spalten` ist entweder nur ein Spaltenname
    (Typ dann TEXT, siehe _VERANSTALTUNG_NEUE_SPALTEN) oder ein (Spaltenname, SQL-Typ)-Tupel,
    falls ein anderer Typ/DEFAULT/NOT NULL gebraucht wird (siehe _TEILNEHMER_NEUE_SPALTEN/
    _ERGEBNISSE_NEUE_SPALTEN)."""
    vorhandene_spalten = _vorhandene_spalten(conn, tabelle)
    for eintrag in neue_spalten:
        spalte, sql_typ = eintrag if isinstance(eintrag, tuple) else (eintrag, "TEXT")
        if spalte not in vorhandene_spalten:
            conn.execute(f"ALTER TABLE {tabelle} ADD COLUMN {spalte} {sql_typ}")
    conn.commit()

def _migriere_veranstaltung_spalten(conn) -> None:
    """Ergänzt in bereits vor dieser Programmversion angelegten Termin-Dateien/
    Datenbanken die neuen, optionalen Veranstaltungs-Spalten nachträglich - siehe
    _migriere_spalten() oben. Dünner Wrapper (statt direktem Aufruf von _migriere_spalten
    an den drei Aufrufstellen unten), damit der Funktionsname weiterhin erkennen lässt,
    welche Tabelle gemeint ist."""
    _migriere_spalten(conn, "veranstaltung", _VERANSTALTUNG_NEUE_SPALTEN)

_TEILNEHMER_NEUE_SPALTEN = [
    ("bezahlt", "INTEGER NOT NULL DEFAULT 0"),
    ("gegenstand_1_disziplin", "TEXT CHECK (gegenstand_1_disziplin IN ('Trümmerfeld', 'Flächensuche', 'Behältnisstrecke'))"),
    ("gegenstand_2_disziplin", "TEXT CHECK (gegenstand_2_disziplin IN ('Trümmerfeld', 'Flächensuche', 'Behältnisstrecke'))"),
    ("gegenstand_3_disziplin", "TEXT CHECK (gegenstand_3_disziplin IN ('Trümmerfeld', 'Flächensuche', 'Behältnisstrecke'))"),
    ("verband", "TEXT"),
    ("mitgliedsnummer", "TEXT"),
    ("wurftag", "TEXT"),
    ("strasse", "TEXT"),
    ("hausnummer", "TEXT"),
    ("plz", "TEXT"),
    ("ort", "TEXT"),
    ("email", "TEXT"),
    ("telefon", "TEXT"),
    # Nutzerwunsch (20.09., Anmerkung zum Programm): "Rasse" und "Tollwutimpfung gültig
    # bis" stehen auf dem echten Meldeformular, fehlten bisher aber im Programm. Sowie ein
    # eigener Halter-Block ("falls abweichend von Teilnehmer - Angaben des
    # Hundeeigentümers" auf dem Formular) - der Halter (Hundeeigentümer) kann eine andere
    # Person als der Hundeführer (Teilnehmer/nachname+vorname oben) sein. Bewusst NICHT
    # als eigene Tabelle/Beziehung modelliert, da es sich um höchstens EINE zusätzliche
    # Person je Teilnehmer handelt, keine Liste - ein flacher, optionaler Spaltenblock
    # reicht dafür wie schon beim Teilnehmer selbst.
    ("rasse", "TEXT"),
    ("tollwutimpfung_bis", "TEXT"),
    # Nutzerwunsch (21.09., Rückmeldung "Statistik/Jugendliche"): Geburtsdatum des
    # Hundeführers/der Hundeführerin, um Jugendliche (unter 18 Jahre am Prüfungstag)
    # gesondert in der Statistik-PDF auszuweisen (siehe ist_jugendlicher() unten und
    # pdf_export._statistik_jugendliche_tabelle()).
    ("geburtsdatum", "TEXT"),
    ("halter_vorname", "TEXT"),
    ("halter_nachname", "TEXT"),
    ("halter_strasse", "TEXT"),
    ("halter_hausnummer", "TEXT"),
    ("halter_plz", "TEXT"),
    ("halter_ort", "TEXT"),
    ("halter_mitgliedsverein", "TEXT"),
    ("halter_mitgliedsnummer", "TEXT"),
    ("halter_lu_nr", "TEXT"),
    ("keine_teilnahme", "INTEGER NOT NULL DEFAULT 0"),
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
    hinterlegt. Siehe _migriere_spalten() oben (dünner Wrapper, siehe dortiger Kommentar)."""
    _migriere_spalten(conn, "teilnehmer", _TEILNEHMER_NEUE_SPALTEN)

_ERGEBNISSE_NEUE_SPALTEN = [
    ("disqualifiziert", "INTEGER NOT NULL DEFAULT 0"),
    ("abbruch", "INTEGER NOT NULL DEFAULT 0"),
    ("stechen_sieger", "INTEGER NOT NULL DEFAULT 0"),  # S1, 03.10.2026
    ("abbruch_grund", "TEXT"),  # R7, 01.11.2026
]

def _migriere_ergebnisse_spalten(conn) -> None:
    """Ergänzt in bereits vor dieser Programmversion angelegten Termin-Dateien/
    Datenbanken die neuen Status-Spalten 'disqualifiziert'/'abbruch' nachträglich (analog
    zu _migriere_veranstaltung_spalten/_migriere_teilnehmer_spalten oben). Bestehende
    Ergebniszeilen gelten dabei als "weder disqualifiziert noch Abbruch" (Default 0) -
    ihre bisherige, aus den Punktwerten berechnete Wertnote bleibt dadurch unverändert
    gültig. Siehe _migriere_spalten() oben (dünner Wrapper, siehe dortiger Kommentar)."""
    _migriere_spalten(conn, "ergebnisse", _ERGEBNISSE_NEUE_SPALTEN)

_ZEITPLAN_EINTRAG_NEUE_SPALTEN = [
    # UX-Test 02.10.2026, U2: Rotation innerhalb eines Prüfungsblocks.
    ("startversatz", "INTEGER NOT NULL DEFAULT 0"),
    # R-B20 (05.11.2026): feste Uhrzeit einer Pause.
    "fest_um",
]

def _migriere_zeitplan_spalten(conn) -> None:
    """Ergänzt die neuen Zeitplan-Spalten in älteren Termin-Dateien (siehe _migriere_spalten)."""
    _migriere_spalten(conn, "zeitplan_eintrag", _ZEITPLAN_EINTRAG_NEUE_SPALTEN)

# Sicherheitskorrektur D-2 (13.11.2026): Rücksprung-Journale mit Verweis auf eine weitere Datei.
# Ein Journal kann am Ende auf eine zweite Datei verweisen (Aufbau am Dateiende: Name, 4 Byte
# Namenslänge, 4 Byte Prüfsumme, 8 Byte Kennung). Das Programm schreibt nie in zwei
# Datenbanken zugleich, ein solches Journal stammt also immer von außen. Es wird nicht
# verarbeitet; die Datei daneben wird nicht geöffnet.
_JOURNAL_VERWEIS_KENNUNG = bytes.fromhex("d9d505f920a163d7")
JOURNAL_ENDUNG = "-journal"
JOURNAL_VERWEIS_TEXT = (
    "Neben der Termin-Datei liegt eine Rücksprung-Datei („-journal“) mit einem Verweis auf eine "
    "weitere Datei. Das Programm erzeugt so etwas nie, die Datei wird deshalb nicht geöffnet. "
    "Bitte nur Termin-Dateien aus vertrauenswürdiger Quelle verwenden."
)

class JournalMitVerweis(sqlite3.DatabaseError):
    """Neben einer Termin-Datei liegt ein Journal mit Verweis auf eine weitere Datei (siehe
    oben); der Text ist für den Nutzer bestimmt."""

def journal_daten_haben_verweis(ende: bytes) -> bool:
    """True, wenn `ende` (die letzten Bytes eines Journals, mindestens 16) einen Verweis auf
    eine weitere Datei anzeigt: Kennung am Ende und Namenslänge ungleich 0."""
    return (len(ende) >= 16 and ende[-8:] == _JOURNAL_VERWEIS_KENNUNG
            and int.from_bytes(ende[-16:-12], "big") != 0)

def journal_hat_verweis(pfad) -> bool:
    """Wie journal_daten_haben_verweis für die Journal-Datei `pfad`; False, wenn es sie nicht
    gibt oder sie sich nicht lesen lässt (dann scheitert auch SQLite)."""
    try:
        with open(pfad, "rb") as datei:
            groesse = datei.seek(0, os.SEEK_END)
            if groesse < 16:
                return False
            datei.seek(groesse - 16)
            return journal_daten_haben_verweis(datei.read(16))
    except OSError:
        return False

def pruefe_journal_ohne_verweis(termin_pfad) -> None:
    """Wirft JournalMitVerweis, wenn neben der Termin-Datei ein Journal mit Verweis liegt."""
    if journal_hat_verweis(f"{termin_pfad}{JOURNAL_ENDUNG}"):
        raise JournalMitVerweis(JOURNAL_VERWEIS_TEXT)

# Sicherheitsprüfung 03.10.2026, H-1: Das Programm legt selbst NIE Trigger oder Views an.
# Stehen welche in einer Termin-Datei, stammen sie von außen (präparierte oder fremde Datei)
# und könnten z. B. eingetragene Ergebnisse still verändern (Codex-Nachweis: 50 -> 0).
_ENTFERNTE_FREMDOBJEKTE: list[str] = []

def _fremde_trigger_und_views_entfernen(conn) -> list[str]:
    """Entfernt alle Trigger und Views aus einer SQLite-Termin-Datei; liefert ihre Namen."""
    objekte = conn.execute(
        "SELECT type, name FROM sqlite_master WHERE type IN ('trigger', 'view') ORDER BY type, name"
    ).fetchall()
    for typ, name in objekte:
        conn.execute(f'DROP {"TRIGGER" if typ == "trigger" else "VIEW"} IF EXISTS "{name.replace(chr(34), chr(34) * 2)}"')
    if objekte:
        conn.commit()
    return [f"{typ} {name}" for typ, name in objekte]

def _soll_spalten() -> dict[str, set[str]]:
    """Spalten, die eine aktuelle Termin-Datei je Tabelle hat (aus SCHEMA). Für teilnehmer und
    ergebnisse deckt SCHEMA alle Spalten ab; bei veranstaltung fehlen die später per Migration
    ergänzten (nur dort relevant, siehe db_termine._termin_werte_pruefen). Liegt hier unten, weil
    auch db_stamm die Liste der dem Programm bekannten Spalten braucht (Sicherheitskorrektur D-1)."""
    with closing(sqlite3.connect(":memory:")) as conn:
        conn.executescript(SCHEMA)
        tabellen = [z[0] for z in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
        return {
            tabelle: {z[1] for z in conn.execute(f'PRAGMA table_info("{tabelle}")')}
            for tabelle in tabellen if not tabelle.startswith("sqlite_")
        }

def termin_werte_verletzt(conn: sqlite3.Connection) -> bool:
    """True, wenn in den Tabellen teilnehmer, ergebnisse, zeitplan_eintrag oder veranstaltung Werte
    stehen, die das Programm nicht kennt: unbekannte Prüfungsart, Stufe, Disziplin, Punkte außerhalb
    des Bereichs oder vom falschen Typ, Namen, die kein Text sind. Gemeinsame Regel für das Öffnen
    einer Termin-Datei (db_termine._termin_werte_pruefen) und das Zurückholen aus einer Kopie
    (pruefe_werte_der_kopie). Vergleiche immer binär und mit Typprüfung, damit fremde
    Spaltendefinitionen (Sortierregel, Datentyp) nichts durchlassen. Nur SQLite (typeof)."""
    disz = "(" + ", ".join(f"'{d}'" for d in ALLE_DISZIPLINEN) + ")"

    def text_in(spalte: str, liste: str) -> str:
        return f"(typeof({spalte}) = 'text' AND ({spalte} COLLATE BINARY) IN {liste})"

    def stufe_ok(spalte: str) -> str:
        return f"(typeof({spalte}) IN ('integer', 'real') AND {spalte} IN (1, 2, 3))"

    def text_oder_null(spalte: str) -> str:
        return f"(typeof({spalte}) IN ('text', 'null'))"

    gegenstaende = " AND ".join(
        f"(gegenstand_{i}_disziplin IS NULL OR {text_in(f'gegenstand_{i}_disziplin', disz)})" for i in (1, 2, 3)
    )
    punkte = " AND ".join(
        f"({spalte} IS NULL OR (typeof({spalte}) = 'integer' AND {spalte} BETWEEN 0 AND {maximum}))"
        for suche, anzeige in DISZIPLIN_SPALTEN.values()
        for spalte, maximum in ((suche, SUCHE_MAX), (anzeige, ANZEIGE_MAX))
    )
    namen = " AND ".join(text_oder_null(s) for s in ("nachname", "vorname", "rufname_hund", "verein"))
    arten, pause, pruefung = "('ED', 'DK')", "('pause')", "('pruefung')"
    abfragen = [
        "SELECT COUNT(*) FROM teilnehmer WHERE NOT ("
        f"{text_in('art', arten)} AND {stufe_ok('stufe')} "
        f"AND (disziplin IS NULL OR {text_in('disziplin', disz)}) "
        f"AND (art COLLATE BINARY <> 'ED' OR disziplin IS NOT NULL) AND {gegenstaende} AND {namen})",
        f"SELECT COUNT(*) FROM ergebnisse WHERE NOT ({punkte})",
        "SELECT COUNT(*) FROM zeitplan_eintrag WHERE NOT ("
        f"(typeof(dauer_minuten) = 'integer' AND dauer_minuten > 0) AND ("
        f"({text_in('typ', pause)}) OR ({text_in('typ', pruefung)} "
        f"AND {text_in('art', arten)} AND {stufe_ok('stufe')} AND {text_in('disziplin', disz)})))",
        f"SELECT COUNT(*) FROM veranstaltung WHERE NOT ({text_oder_null('verein')} AND {text_oder_null('datum')})",
    ]
    return any(conn.execute(abfrage).fetchone()[0] for abfrage in abfragen)

# Sicherheitskorrektur D-6: Werte aus einer Kopie werden vor dem Speichern mit derselben Regel
# geprüft wie beim Öffnen einer Termin-Datei.
UNZULAESSIGE_KOPIE_WERTE_TEXT = (
    "Die Kopie enthält Werte, die das Programm nicht kennt (z. B. eine unbekannte Prüfungsart, "
    "Leistungsklasse oder Punktzahl). Die Werte aus der Kopie wurden nicht übernommen."
)

class KopieWerteUnzulaessig(sqlite3.DatabaseError):
    """Nach dem Zurückholen aus einer Kopie stünden Werte in der Termin-Datei, die das Programm
    beim Öffnen ablehnt; der Text ist für den Nutzer bestimmt."""

def pruefe_werte_der_kopie(conn) -> None:
    """Wirft KopieWerteUnzulaessig, wenn die Termin-Datei `conn` nach dem Zurückholen von Daten aus
    einer Kopie (vor dem Commit) Werte enthält, die beim Öffnen abgelehnt würden. Der Aufrufer
    rollt dann zurück (_mit_rollback). Bei PostgreSQL entfällt die Prüfung (dort ist das Schema
    vom Programm und typeof gibt es nicht)."""
    if isinstance(conn, _PostgresConnection):
        return
    if termin_werte_verletzt(conn):
        raise KopieWerteUnzulaessig(UNZULAESSIGE_KOPIE_WERTE_TEXT)

def entfernte_fremdobjekte() -> list[str]:
    """Trigger/Views, die das zuletzt per init_db() geöffnete Termin-File enthielt und die
    dabei entfernt wurden (leer im Normalfall) - für einen Hinweis in der Oberfläche."""
    return list(_ENTFERNTE_FREMDOBJEKTE)

def init_db(pfad: str) -> sqlite3.Connection:
    """Öffnet (oder erstellt) die Termin-Datenbankdatei unter `pfad`.

    Schließt die gerade erst geöffnete Verbindung wieder, falls das Anlegen des Schemas/
    der Migrationen fehlschlägt (z. B. `pfad` ist gar keine gültige SQLite-Datenbank,
    siehe app_web.admin_termin_veroeffentlichen()/admin_termin_zurueckholen(), QS-Fund
    21.09.) - sonst bliebe die Datei über die offene, nie wieder erreichbare Verbindung
    gesperrt (unter Windows verhindert das ein anschließendes os.remove() der
    temporären Upload-Datei mit einem PermissionError)."""
    global _ENTFERNTE_FREMDOBJEKTE
    pruefe_journal_ohne_verweis(pfad)  # D-2: vor jedem Öffnen mit Schreibrecht
    conn = sqlite3.connect(pfad)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        # Sicherheitsprüfung 03.10.2026, H-1: ZUERST fremde Trigger/Views entfernen, bevor
        # irgendetwas in die Datei geschrieben wird (auch nicht die Migrationen).
        _ENTFERNTE_FREMDOBJEKTE = _fremde_trigger_und_views_entfernen(conn)
        conn.executescript(SCHEMA)
        conn.commit()
        _migriere_veranstaltung_spalten(conn)
        _migriere_teilnehmer_spalten(conn)
        _migriere_ergebnisse_spalten(conn)
        _migriere_zeitplan_spalten(conn)
    except Exception:
        conn.close()
        raise
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
    _migriere_ergebnisse_spalten(conn)
    _migriere_zeitplan_spalten(conn)

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
    SQLite-Desktop-Version weiterhin ganz ohne diese zusätzliche Abhängigkeit auskommt.
    (pyzipper für die Datensicherung braucht db.py gar nicht mehr - das liegt seit
    27.09.2026 in db_sicherung.py.)

    dsn: vollständiger PostgreSQL-Verbindungsstring,
    z. B. "postgresql://benutzer:passwort@host:5432/datenbankname".
    """
    import psycopg2
    import psycopg2.extras

    roh_verbindung = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    conn = _PostgresConnection(roh_verbindung)
    _richte_schema_im_aktuellen_suchpfad_ein(conn)
    return conn

def _mit_rollback(funktion):
    """Desktop-Prüfung 14.10.2026 (Teil 1 Nr. 7, Teil 4 Nr. 5): Scheitert eine schreibende
    Funktion (z. B. schreibgeschützte, gesperrte oder nicht mehr erreichbare Datei), wird die
    angefangene Transaktion zurückgerollt. Sonst bliebe sie offen, und der nächste Commit
    einer harmlosen Aktion würde einen halben Vorgang speichern."""
    @functools.wraps(funktion)
    def mit_rollback(conn, *args, **kwargs):
        try:
            return funktion(conn, *args, **kwargs)
        except BaseException:
            with suppress(Exception):
                conn.rollback()
            raise
    return mit_rollback

def sortierschluessel_text(text) -> str:
    """Sortierschlüssel für Namen und Bezeichnungen nach deutscher Gewohnheit: Umlaute
    und Akzente wie der Grundbuchstabe (Ä wie A, Ö wie O), ohne Unterschied zwischen
    Groß- und Kleinschreibung (Desktop-Prüfung 14.10.2026, Teil 3 Nr. 4 und Teil 6 Nr. 5).
    Qt-frei, damit auch die PDF-Erzeugung ihn nutzen kann."""
    zerlegt = unicodedata.normalize("NFD", "" if text is None else str(text))
    return "".join(z for z in zerlegt if not unicodedata.combining(z)).casefold()
