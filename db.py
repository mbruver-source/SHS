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
"""

from __future__ import annotations

import datetime
import re
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


def _migriere_veranstaltung_spalten(conn: sqlite3.Connection) -> None:
    """Ergänzt in bereits vor dieser Programmversion angelegten Termin-Dateien die neuen,
    optionalen Veranstaltungs-Spalten nachträglich (CREATE TABLE IF NOT EXISTS allein
    reicht dafür nicht, da die Tabelle in Altdateien schon ohne diese Spalten existiert).
    ALTER TABLE ADD COLUMN ist in SQLite dafür unproblematisch: keine Datenverluste,
    bestehende Zeilen bekommen für die neue Spalte einfach NULL."""
    vorhandene_spalten = {row[1] for row in conn.execute("PRAGMA table_info(veranstaltung)").fetchall()}
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


def _migriere_teilnehmer_spalten(conn: sqlite3.Connection) -> None:
    """Ergänzt in bereits vor dieser Programmversion angelegten Termin-Dateien neu
    hinzugekommene Teilnehmer-Spalten nachträglich (analog zu
    _migriere_veranstaltung_spalten oben) - aktuell 'bezahlt', die drei
    'gegenstand_N_disziplin'-Zuordnungsfelder sowie die Verwaltungs-/Kontaktdaten
    (Verband, Mitgliedsnummer, Wurftag, Straße, Hausnummer, PLZ, Ort, E-Mail, Telefon).
    Bestehende Teilnehmer gelten dabei als "noch nicht bezahlt" (Default 0), ihre
    Gegenstände als "frei" (NULL) statt automatisch einer Disziplin zugeordnet, und die
    neuen Verwaltungs-/Kontaktfelder als leer (NULL) - andernfalls würde allein durch das
    Öffnen einer alten Termin-Datei fälschlich der Eindruck entstehen, bereits erfasste
    Teilnehmer hätten schon bezahlt, eine bestimmte Gegenstand-Zuordnung oder Kontaktdaten
    hinterlegt."""
    vorhandene_spalten = {row[1] for row in conn.execute("PRAGMA table_info(teilnehmer)").fetchall()}
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
    return {row[0] for row in conn.execute(query, params).fetchall()}


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
