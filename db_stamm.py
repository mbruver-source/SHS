"""
Veranstaltung, Teilnehmer, Startnummern-Bereiche und Datumsfelder.

Aus db.py ausgelagert (11.11.2026, Schichtenaufteilung); db.py bleibt als Fassade und reicht alle
Namen weiter. Code unverändert. Siehe Architektur.md.
"""

from __future__ import annotations
import datetime
import re
import sqlite3
from dataclasses import dataclass, field

from db_verbindung import (
    ALLE_PRUEFUNGEN,
    KopieWerteUnzulaessig,
    pruefung_nach_kuerzel,
    pruefe_werte_der_kopie,
    UNZULAESSIGE_KOPIE_WERTE_TEXT,
    _mit_rollback,
    _PostgresConnection,
    _soll_spalten,
)


def kurzer_text(wert, laenge: int = 60) -> str:
    """Ein Wert aus einer womöglich fremden Quelle (Datei, Import) für eine Meldung: einzeilig,
    nur druckbare Zeichen, auf `laenge` Zeichen gekürzt (Sicherheitskorrektur I-6)."""
    text = " ".join(str(wert if wert is not None else "").split())
    text = "".join(zeichen for zeichen in text if zeichen.isprintable())
    return text if len(text) <= laenge else text[:laenge - 1] + "…"


# --- Veranstaltung -----------------------------------------------------

# Sicherheitskorrektur I-5 (Veranstaltungsfelder): wie bei den Teilnehmern ein Höchstmaß je Textfeld,
# damit ein überlanger Wert keine Ausdrucke verhindert. Feld -> (Anzeigename, höchstens Zeichen).
VERANSTALTUNG_LAENGEN: dict[str, tuple[str, int]] = {
    "verein": ("Verein", 200), "ort": ("Ort", 200), "verband": ("Verband", 200),
    "vereins_nr": ("Vereins-Nr.", 40), "pruefungsnummer": ("Prüfungsnummer", 40),
    "wertungsrichter_1": ("Wertungsrichter 1", 100), "wertungsrichter_2": ("Wertungsrichter 2", 100),
    "wertungsrichter_3": ("Wertungsrichter 3", 100), "wertungsrichter_4": ("Wertungsrichter 4", 100),
    "wertungsrichter_5": ("Wertungsrichter 5", 100), "pruefungsleiter": ("Prüfungsleiter", 100),
    "meldestelle": ("Meldestelle", 2000),
}

def pruefe_veranstaltung_werte(conn: sqlite3.Connection, werte: dict) -> None:
    """Wirft ValueError, wenn ein Textfeld aus `werte` länger als in VERANSTALTUNG_LAENGEN erlaubt ist.
    Geprüft werden nur Felder, deren Wert sich gegenüber dem gespeicherten ändert: ein schon
    vorhandener langer Altwert blockiert so nie das Speichern anderer Angaben."""
    aktuell = get_veranstaltung(conn) or {}
    for feld, (bezeichnung, hoechstens) in VERANSTALTUNG_LAENGEN.items():
        wert = werte.get(feld)
        if isinstance(wert, str) and len(wert) > hoechstens and wert != aktuell.get(feld):
            raise ValueError(f"{bezeichnung} ist zu lang (höchstens {hoechstens} Zeichen, hier {len(wert)})")


@_mit_rollback
def set_veranstaltung(
    conn: sqlite3.Connection,
    verein: str,
    datum: str,
    ort: str | None = None,
    vereins_nr: str | None = None,
    pruefungsnummer: str | None = None,
    wertungsrichter_1: str | None = None,
    wertungsrichter_2: str | None = None,
    wertungsrichter_3: str | None = None,
    wertungsrichter_4: str | None = None,
    wertungsrichter_5: str | None = None,
    pruefungsleiter: str | None = None,
    pruefungsgebuehr_ed: str | None = None,
    pruefungsgebuehr_dk: str | None = None,
    zeitplan_start: str | None = None,
    verband: str | None = None,
    meldestelle: str | None = None,
    angebotene_pruefungen: str | None = None,
    startnummer_bereiche: str | None = None,
    dk_mindestabstand: str | None = None,
    startnummer_bereichsgroesse: str | None = None,
    lr_km_satz: str | None = None,
    lr_tagespauschale: str | None = None,
    lr_abrechnung: str | None = None,
    checkliste: str | None = None,
    checkliste_eigene: str | None = None,
) -> None:
    pruefe_veranstaltung_werte(conn, {
        "verein": verein, "ort": ort, "verband": verband, "vereins_nr": vereins_nr,
        "pruefungsnummer": pruefungsnummer, "wertungsrichter_1": wertungsrichter_1,
        "wertungsrichter_2": wertungsrichter_2, "wertungsrichter_3": wertungsrichter_3,
        "wertungsrichter_4": wertungsrichter_4, "wertungsrichter_5": wertungsrichter_5,
        "pruefungsleiter": pruefungsleiter, "meldestelle": meldestelle,
    })
    conn.execute(
        """
        INSERT INTO veranstaltung (
            id, verein, ort, datum, vereins_nr, pruefungsnummer,
            wertungsrichter_1, wertungsrichter_2, wertungsrichter_3, wertungsrichter_4, wertungsrichter_5,
            pruefungsleiter, pruefungsgebuehr_ed, pruefungsgebuehr_dk, zeitplan_start,
            verband, meldestelle, angebotene_pruefungen, startnummer_bereiche, dk_mindestabstand,
            startnummer_bereichsgroesse, lr_km_satz, lr_tagespauschale, lr_abrechnung, checkliste,
            checkliste_eigene
        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            verein=excluded.verein, ort=excluded.ort, datum=excluded.datum,
            vereins_nr=excluded.vereins_nr, pruefungsnummer=excluded.pruefungsnummer,
            wertungsrichter_1=excluded.wertungsrichter_1, wertungsrichter_2=excluded.wertungsrichter_2,
            wertungsrichter_3=excluded.wertungsrichter_3, wertungsrichter_4=excluded.wertungsrichter_4,
            wertungsrichter_5=excluded.wertungsrichter_5,
            pruefungsleiter=excluded.pruefungsleiter,
            pruefungsgebuehr_ed=excluded.pruefungsgebuehr_ed, pruefungsgebuehr_dk=excluded.pruefungsgebuehr_dk,
            zeitplan_start=excluded.zeitplan_start,
            verband=excluded.verband, meldestelle=excluded.meldestelle,
            angebotene_pruefungen=excluded.angebotene_pruefungen,
            startnummer_bereiche=excluded.startnummer_bereiche,
            dk_mindestabstand=excluded.dk_mindestabstand,
            startnummer_bereichsgroesse=excluded.startnummer_bereichsgroesse,
            lr_km_satz=excluded.lr_km_satz, lr_tagespauschale=excluded.lr_tagespauschale,
            lr_abrechnung=excluded.lr_abrechnung, checkliste=excluded.checkliste,
            checkliste_eigene=excluded.checkliste_eigene
        """,
        (
            verein, ort, datum, vereins_nr, pruefungsnummer, wertungsrichter_1, wertungsrichter_2,
            wertungsrichter_3, wertungsrichter_4, wertungsrichter_5,
            pruefungsleiter, pruefungsgebuehr_ed, pruefungsgebuehr_dk, zeitplan_start,
            verband, meldestelle, angebotene_pruefungen, startnummer_bereiche, dk_mindestabstand,
            startnummer_bereichsgroesse, lr_km_satz, lr_tagespauschale, lr_abrechnung,
            checkliste, checkliste_eigene,
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
    # Rasse/Tollwutimpfung sowie ein optionaler Halter-Block (Nutzerwunsch 20.09., siehe
    # SCHEMA/_TEILNEHMER_NEUE_SPALTEN) - der Halter (Hundeeigentümer) kann laut
    # Meldeformular eine andere Person als der Hundeführer (nachname/vorname oben) sein.
    # Bleibt komplett leer, solange kein abweichender Halter angegeben wird.
    rasse: str | None = None
    tollwutimpfung_bis: str | None = None
    # Geburtsdatum des Hundeführers/der Hundeführerin (Nutzerwunsch 21.09., siehe SCHEMA/
    # _TEILNEHMER_NEUE_SPALTEN oben) - Grundlage für ist_jugendlicher() weiter unten.
    geburtsdatum: str | None = None
    halter_vorname: str | None = None
    halter_nachname: str | None = None
    halter_strasse: str | None = None
    halter_hausnummer: str | None = None
    halter_plz: str | None = None
    halter_ort: str | None = None
    halter_mitgliedsverein: str | None = None
    halter_mitgliedsnummer: str | None = None
    halter_lu_nr: str | None = None

# Sicherheitskorrektur I-5/I-1: Obergrenzen für Textfelder und die Schulterhöhe. Ein einzelner
# überlanger Wert (z. B. aus einem Formular oder einer CSV-Datei) darf keine Ausdrucke des ganzen
# Termins verhindern. Über der Grenze wird die Meldung mit Feldname abgelehnt, nichts wird still
# gekürzt. (Feldname im NeuerTeilnehmer, Anzeigename, höchstens Zeichen.)
_FELD_LAENGEN: tuple[tuple[str, str, int], ...] = (
    ("nachname", "Nachname", 100), ("vorname", "Vorname", 100), ("rufname_hund", "Rufname des Hundes", 100),
    ("halter_vorname", "Vorname des Halters", 100), ("halter_nachname", "Nachname des Halters", 100),
    ("verein", "Verein", 200), ("zwingername", "Zwingername", 200), ("rasse", "Rasse", 200),
    ("verband", "Verband", 200), ("strasse", "Straße", 200), ("ort", "Ort", 200),
    ("halter_strasse", "Straße des Halters", 200), ("halter_ort", "Ort des Halters", 200),
    ("halter_mitgliedsverein", "Mitgliedsverein des Halters", 200),
    ("gegenstand_1", "Gegenstand 1", 200), ("gegenstand_2", "Gegenstand 2", 200),
    ("gegenstand_3", "Gegenstand 3", 200), ("email", "E-Mail", 254),
    ("chip_nr", "Kennzeichnung", 40), ("mitgliedsnummer", "Mitgliedsnummer", 40),
    ("wurftag", "Wurftag", 40), ("geburtsdatum", "Geburtsdatum", 40),
    ("tollwutimpfung_bis", "Tollwutimpfung", 40), ("hausnummer", "Hausnummer", 40), ("plz", "PLZ", 40),
    ("telefon", "Telefon", 40), ("geschlecht", "Geschlecht", 40),
    ("halter_hausnummer", "Hausnummer des Halters", 40), ("halter_plz", "PLZ des Halters", 40),
    ("halter_mitgliedsnummer", "Mitgliedsnummer des Halters", 40), ("halter_lu_nr", "LU-Nr. des Halters", 40),
)
FELD_LAENGEN: dict[str, int] = {feld: hoechstens for feld, _name, hoechstens in _FELD_LAENGEN}
SCHULTERHOEHE_MIN = 1
SCHULTERHOEHE_MAX = 100  # wie die Eingabe im Teilnehmer-Dialog

def pruefe_teilnehmer_werte(t: NeuerTeilnehmer, bisher: dict | None = None) -> None:
    """Wirft ValueError mit einer für den Nutzer verständlichen Begründung, wenn ein Textfeld von `t`
    die Obergrenze aus FELD_LAENGEN überschreitet, die Schulterhöhe außerhalb von 1 bis 100 cm liegt
    oder eine Zahl nicht in die Datenbank passt (Sicherheitskorrektur I-5/I-1). Mit `bisher` (der
    vorhandene Datensatz beim Bearbeiten) werden nur geänderte Felder geprüft, damit ein Altwert über
    der Grenze das Speichern anderer Änderungen nicht blockiert."""
    bisher = bisher or {}
    for feld, bezeichnung, hoechstens in _FELD_LAENGEN:
        wert = getattr(t, feld)
        if isinstance(wert, str) and len(wert) > hoechstens and wert != bisher.get(feld):
            raise ValueError(f"{bezeichnung} ist zu lang (höchstens {hoechstens} Zeichen, hier {len(wert)})")
    hoehe = t.schulterhoehe_cm
    if "schulterhoehe_cm" in bisher and bisher["schulterhoehe_cm"] == hoehe:
        hoehe = None  # unverändert: nicht erneut prüfen
    if hoehe is not None and (isinstance(hoehe, bool) or not isinstance(hoehe, (int, float))):
        raise ValueError("Schulterhöhe ist keine Zahl")  # z. B. Text oder BLOB aus einer fremden Datei
    if hoehe is not None and not SCHULTERHOEHE_MIN <= hoehe <= SCHULTERHOEHE_MAX:
        raise ValueError(f"Schulterhöhe {hoehe if abs(hoehe) < 10**6 else 'außerhalb des Bereichs'} ist ungültig "
                         f"– bitte eine ganze Zahl von {SCHULTERHOEHE_MIN} bis {SCHULTERHOEHE_MAX} cm angeben")
    for feld in ("startnummer", "stufe"):
        wert = getattr(t, feld)
        if isinstance(wert, int) and abs(wert) >= 2 ** 62:
            raise ValueError(f"{feld} ist zu groß")

@_mit_rollback
def add_teilnehmer(conn: sqlite3.Connection, t: NeuerTeilnehmer) -> int:
    pruefe_teilnehmer_werte(t)
    cur = conn.execute(
        """
        INSERT INTO teilnehmer (
            nachname, vorname, verein, zwingername, rufname_hund, geschlecht,
            schulterhoehe_cm, chip_nr, art, stufe, disziplin, startnummer,
            gegenstand_1, gegenstand_2, gegenstand_3,
            gegenstand_1_disziplin, gegenstand_2_disziplin, gegenstand_3_disziplin, bezahlt,
            verband, mitgliedsnummer, wurftag, strasse, hausnummer, plz, ort, email, telefon,
            rasse, tollwutimpfung_bis, geburtsdatum,
            halter_vorname, halter_nachname, halter_strasse, halter_hausnummer,
            halter_plz, halter_ort, halter_mitgliedsverein, halter_mitgliedsnummer, halter_lu_nr
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            t.nachname, t.vorname, t.verein, t.zwingername, t.rufname_hund, t.geschlecht,
            t.schulterhoehe_cm, t.chip_nr, t.art, t.stufe, t.disziplin, t.startnummer,
            t.gegenstand_1, t.gegenstand_2, t.gegenstand_3,
            t.gegenstand_1_disziplin, t.gegenstand_2_disziplin, t.gegenstand_3_disziplin, int(t.bezahlt),
            t.verband, t.mitgliedsnummer, t.wurftag, t.strasse, t.hausnummer, t.plz, t.ort, t.email, t.telefon,
            t.rasse, t.tollwutimpfung_bis, t.geburtsdatum,
            t.halter_vorname, t.halter_nachname, t.halter_strasse, t.halter_hausnummer,
            t.halter_plz, t.halter_ort, t.halter_mitgliedsverein, t.halter_mitgliedsnummer, t.halter_lu_nr,
        ),
    )
    teilnehmer_id = cur.lastrowid
    conn.execute("INSERT INTO ergebnisse (teilnehmer_id) VALUES (?)", (teilnehmer_id,))
    conn.commit()
    return teilnehmer_id

def list_teilnehmer(conn: sqlite3.Connection, nur_teilnehmende: bool = False) -> list[dict]:
    """Alle Teilnehmer des Termins. Mit `nur_teilnehmende=True` ohne die als "keine
    Teilnahme" markierten (Nutzerwunsch 02.10.2026) - so laden alle nachgelagerten
    Prozesse (Ergebniserfassung, Auswertung, Zeitplan, Bedarf, PDFs, Web-Export), damit
    nicht erschienene Teilnehmer dort nirgends mehr auftauchen. Ohne Filter bleibt es für
    die Teilnehmerliste selbst, Startnummern, Dubletten-Prüfungen und die
    Prüfungsleitungs-Übersicht (Gebühren)."""
    query = "SELECT * FROM teilnehmer"
    if nur_teilnehmende:
        query += " WHERE COALESCE(keine_teilnahme, 0) = 0"
    rows = conn.execute(query + " ORDER BY startnummer, nachname").fetchall()
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

# --- Startnummern-Bereiche und Sammelvergabe (UX-Test 02.10.2026, U1) ---------------
# Marcos Entscheidungen: Bereich je Prüfung (Art + LK + Disziplin), je Termin gespeichert;
# die Sammelvergabe vergibt nur an Teilnehmer OHNE Nummer (vergebene werden nie
# überschrieben), überspringt "keine Teilnahme", und ein Bereich ist Pflicht - ohne Bereich
# oder bei vollem Bereich bleiben die Teilnehmer ohne Nummer und werden gemeldet.
# Überlappende Bereiche sind nicht erlaubt.

def pruefungs_kuerzel(art: str, stufe: int, disziplin: str | None) -> str:
    """Kürzel der Prüfung eines Teilnehmers wie in ALLE_PRUEFUNGEN (z. B. "DK1",
    "ED2-Trümmerfeld")."""
    return f"DK{stufe}" if art == "DK" else f"ED{stufe}-{disziplin}"

def startnummer_bereiche(veranstaltung: dict | None) -> dict[str, tuple[int, int]]:
    """Liest die Startnummern-Bereiche ("DK1=1-20,ED1-Trümmerfeld=21-40") als
    {kuerzel: (von, bis)}. Unlesbare Einträge werden ignoriert."""
    text = (veranstaltung or {}).get("startnummer_bereiche") or ""
    bereiche: dict[str, tuple[int, int]] = {}
    for eintrag in text.split(","):
        kuerzel, _, spanne = eintrag.strip().partition("=")
        von, _, bis = spanne.partition("-")
        try:
            bereiche[kuerzel.strip()] = (int(von), int(bis))
        except ValueError:
            continue
    return bereiche

def startnummer_bereiche_als_text(bereiche: dict[str, tuple[int, int]]) -> str | None:
    """Speicherform für veranstaltung.startnummer_bereiche (None, wenn leer), in der
    Reihenfolge von ALLE_PRUEFUNGEN."""
    teile = [
        f"{p.kuerzel}={bereiche[p.kuerzel][0]}-{bereiche[p.kuerzel][1]}"
        for p in ALLE_PRUEFUNGEN if p.kuerzel in bereiche
    ]
    return ",".join(teile) or None

def pruefe_startnummer_bereiche(bereiche: dict[str, tuple[int, int]]) -> str | None:
    """Fehlertext für den Nutzer oder None: jeder Bereich von >= 1 und bis >= von,
    keine zwei Bereiche überschneiden sich."""
    def bezeichnung(kuerzel):
        pruefung = pruefung_nach_kuerzel(kuerzel)
        return pruefung.bezeichnung if pruefung else kuerzel

    for kuerzel, (von, bis) in bereiche.items():
        if von < 1 or bis < von:
            return f"{bezeichnung(kuerzel)}: Bereich {von}–{bis} ist ungültig (von ab 1, bis nicht kleiner als von)."
    eintraege = sorted(bereiche.items(), key=lambda e: e[1])
    for (k1, (_v1, b1)), (k2, (v2, _b2)) in zip(eintraege, eintraege[1:]):
        if v2 <= b1:
            return (
                f"Die Startnummern-Bereiche von {bezeichnung(k1)} und {bezeichnung(k2)} "
                "überschneiden sich."
            )
    return None

#: Standardgröße eines Startnummern-Bereichs je Prüfung (Marco 09.10.2026) und
#: höchste Startnummer (wie das Startnummer-Feld im Teilnehmer-Dialog).
STANDARD_BEREICHSGROESSE = 20

HOECHSTE_STARTNUMMER = 999

def startnummer_bereichsgroesse(veranstaltung: dict | None) -> int:
    """Gespeicherte Standardgröße der Startnummern-Bereiche (Standard 20)."""
    roh = (veranstaltung or {}).get("startnummer_bereichsgroesse")
    try:
        groesse = int(roh)
    except (TypeError, ValueError):
        return STANDARD_BEREICHSGROESSE
    return groesse if 1 <= groesse <= HOECHSTE_STARTNUMMER else STANDARD_BEREICHSGROESSE

def bereiche_automatisch_berechnen(
    groessen: dict[str, int], start: int = 1
) -> dict[str, tuple[int, int]]:
    """Lückenlose Startnummern-Bereiche ab `start` in der Reihenfolge von
    ALLE_PRUEFUNGEN (Marco 09.10.2026), z. B. {"ED1-Trümmerfeld": 20,
    "ED1-Flächensuche": 20} -> Trümmer 1-20, Fläche 21-40. Prüfungen, die nicht in
    `groessen` stehen oder eine Größe < 1 haben, bekommen keinen Bereich. Wirft
    ValueError mit einem Text für den Nutzer, wenn die Nummern über 999 hinauslaufen."""
    bereiche: dict[str, tuple[int, int]] = {}
    naechste = start
    for pruefung in ALLE_PRUEFUNGEN:
        groesse = groessen.get(pruefung.kuerzel, 0)
        if groesse < 1:
            continue
        bis = naechste + groesse - 1
        if bis > HOECHSTE_STARTNUMMER:
            raise ValueError(
                f"Die Bereiche passen nicht in die Startnummern 1–{HOECHSTE_STARTNUMMER} "
                f"({pruefung.bezeichnung} ginge bis {bis}). Bitte die Anzahl verkleinern."
            )
        bereiche[pruefung.kuerzel] = (naechste, bis)
        naechste = bis + 1
    return bereiche

def naechste_freie_startnummer_im_bereich(
    conn: sqlite3.Connection, bereich: tuple[int, int], ausser_teilnehmer_id: int | None = None
) -> int | None:
    """Kleinste freie Startnummer innerhalb von `bereich` oder None, wenn er voll ist."""
    vergeben = vergebene_startnummern(conn, ausser_teilnehmer_id)
    return next((n for n in range(bereich[0], bereich[1] + 1) if n not in vergeben), None)

@dataclass
class StartnummernVergabe:
    """Ergebnis von fehlende_startnummern_vergeben()."""
    vergeben: list[tuple[dict, int]] = field(default_factory=list)
    ohne_bereich: list[dict] = field(default_factory=list)
    bereich_voll: list[dict] = field(default_factory=list)

def _teilnehmer_kuerzel(t: dict) -> str:
    return pruefungs_kuerzel(t["art"], t["stufe"], t["disziplin"])

def fehlende_startnummern_vergeben(
    conn: sqlite3.Connection, pruefung: str | None = None
) -> StartnummernVergabe:
    """Vergibt allen Teilnehmern OHNE Startnummer (außer "keine Teilnahme") die jeweils
    kleinste freie Nummer im Bereich ihrer Prüfung - Reihenfolge nach Prüfung (wie
    ALLE_PRUEFUNGEN), darin nach Name. Bereits vergebene Nummern bleiben unangetastet.
    Teilnehmer ohne hinterlegten Bereich bzw. bei vollem Bereich bleiben ohne Nummer und
    werden im Ergebnis aufgeführt. Alles in einer Transaktion. Mit `pruefung` (Kürzel wie
    in ALLE_PRUEFUNGEN) nur für die Teilnehmer dieser Prüfung (Marco 09.10.2026: der
    Filter Art/LK im Reiter "Teilnehmer" schränkt die Vergabe ein)."""
    bereiche = startnummer_bereiche(get_veranstaltung(conn))
    reihenfolge = {p.kuerzel: i for i, p in enumerate(ALLE_PRUEFUNGEN)}
    offen = teilnehmer_ohne_startnummer(conn, pruefung)
    offen.sort(key=lambda t: (
        reihenfolge.get(pruefungs_kuerzel(t["art"], t["stufe"], t["disziplin"]), len(reihenfolge)),
        (t["nachname"] or "").casefold(), (t["vorname"] or "").casefold(), t["id"],
    ))
    vergeben_nummern = vergebene_startnummern(conn)
    ergebnis = StartnummernVergabe()
    try:
        for t in offen:
            bereich = bereiche.get(pruefungs_kuerzel(t["art"], t["stufe"], t["disziplin"]))
            if bereich is None:
                ergebnis.ohne_bereich.append(t)
                continue
            nummer = next(
                (n for n in range(bereich[0], bereich[1] + 1) if n not in vergeben_nummern), None
            )
            if nummer is None:
                ergebnis.bereich_voll.append(t)
                continue
            conn.execute("UPDATE teilnehmer SET startnummer = ? WHERE id = ?", (nummer, t["id"]))
            vergeben_nummern.add(nummer)
            ergebnis.vergeben.append((t, nummer))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return ergebnis

def get_teilnehmer(conn: sqlite3.Connection, teilnehmer_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM teilnehmer WHERE id = ?", (teilnehmer_id,)).fetchone()
    return dict(row) if row else None

@_mit_rollback
def update_teilnehmer(conn: sqlite3.Connection, teilnehmer_id: int, t: NeuerTeilnehmer) -> None:
    pruefe_teilnehmer_werte(t, get_teilnehmer(conn, teilnehmer_id))  # nur geänderte Felder
    conn.execute(
        """
        UPDATE teilnehmer SET
            nachname=?, vorname=?, verein=?, zwingername=?, rufname_hund=?, geschlecht=?,
            schulterhoehe_cm=?, chip_nr=?, art=?, stufe=?, disziplin=?, startnummer=?,
            gegenstand_1=?, gegenstand_2=?, gegenstand_3=?,
            gegenstand_1_disziplin=?, gegenstand_2_disziplin=?, gegenstand_3_disziplin=?, bezahlt=?,
            verband=?, mitgliedsnummer=?, wurftag=?, strasse=?, hausnummer=?, plz=?, ort=?, email=?, telefon=?,
            rasse=?, tollwutimpfung_bis=?, geburtsdatum=?,
            halter_vorname=?, halter_nachname=?, halter_strasse=?, halter_hausnummer=?,
            halter_plz=?, halter_ort=?, halter_mitgliedsverein=?, halter_mitgliedsnummer=?, halter_lu_nr=?
        WHERE id=?
        """,
        (
            t.nachname, t.vorname, t.verein, t.zwingername, t.rufname_hund, t.geschlecht,
            t.schulterhoehe_cm, t.chip_nr, t.art, t.stufe, t.disziplin, t.startnummer,
            t.gegenstand_1, t.gegenstand_2, t.gegenstand_3,
            t.gegenstand_1_disziplin, t.gegenstand_2_disziplin, t.gegenstand_3_disziplin,
            int(t.bezahlt),
            t.verband, t.mitgliedsnummer, t.wurftag, t.strasse, t.hausnummer, t.plz, t.ort, t.email, t.telefon,
            t.rasse, t.tollwutimpfung_bis, t.geburtsdatum,
            t.halter_vorname, t.halter_nachname, t.halter_strasse, t.halter_hausnummer,
            t.halter_plz, t.halter_ort, t.halter_mitgliedsverein, t.halter_mitgliedsnummer, t.halter_lu_nr,
            teilnehmer_id,
        ),
    )
    conn.commit()

def teilnehmer_sichern(conn: sqlite3.Connection, teilnehmer_id: int) -> dict | None:
    """Vollständiger Stand eines Teilnehmers (Stammdaten und Ergebnis) für „Rückgängig“ nach
    dem Löschen (Marco 10.11.2026); None, wenn es ihn nicht gibt."""
    row = conn.execute("SELECT * FROM teilnehmer WHERE id = ?", (teilnehmer_id,)).fetchone()
    if row is None:
        return None
    ergebnis = conn.execute("SELECT * FROM ergebnisse WHERE teilnehmer_id = ?", (teilnehmer_id,)).fetchone()
    return {"teilnehmer": dict(row), "ergebnis": dict(ergebnis) if ergebnis else None}


def fehlende_teilnehmer(quelle: sqlite3.Connection, conn: sqlite3.Connection) -> list[dict]:
    """Teilnehmer der Kopie `quelle` (z. B. aus „Auto-Sicherung“), die im Termin `conn` fehlen
    (Marco 12.11.2026: gelöschten Teilnehmer aus der Sicherung zurückholen). Verglichen wird die
    ID: sie wird nie neu vergeben (AUTOINCREMENT), eine fehlende ID ist also ein gelöschter
    Teilnehmer. Sortiert nach Nachname, Vorname."""
    vorhandene = {row["id"] for row in conn.execute("SELECT id FROM teilnehmer")}
    zeilen = quelle.execute("SELECT * FROM teilnehmer ORDER BY nachname, vorname, id").fetchall()
    return [dict(z) for z in zeilen if z["id"] not in vorhandene]

@_mit_rollback
def teilnehmer_wiederherstellen(conn: sqlite3.Connection, sicherung: dict) -> bool:
    """Legt einen mit teilnehmer_sichern() gesicherten Teilnehmer wieder an (gleiche ID, mit
    Ergebnis). Ist seine Startnummer inzwischen vergeben, bleibt er ohne Nummer. Liefert
    False, wenn es die ID schon gibt (nichts wird geändert). Stünden danach Werte in der Datei,
    die das Programm beim Öffnen ablehnt, wirft sie KopieWerteUnzulaessig und nichts wird
    geändert (Sicherheitskorrektur D-6)."""
    daten = dict(sicherung["teilnehmer"])
    if conn.execute("SELECT 1 FROM teilnehmer WHERE id = ?", (daten["id"],)).fetchone():
        return False
    nummer = daten.get("startnummer")
    if nummer is not None and conn.execute(
            "SELECT 1 FROM teilnehmer WHERE startnummer = ?", (nummer,)).fetchone():
        daten["startnummer"] = None
    postgres = isinstance(conn, _PostgresConnection)
    for feld, wert in daten.items():  # Längengrenzen wie beim Anlegen (Sicherheitskorrektur I-5)
        hoechstens = FELD_LAENGEN.get(feld)
        if hoechstens and isinstance(wert, str) and len(wert) > hoechstens:
            raise KopieWerteUnzulaessig(UNZULAESSIGE_KOPIE_WERTE_TEXT)
    spalten = _spalten_fuer_einfuegen(postgres, "teilnehmer", daten)
    # PostgreSQL: id ist GENERATED ALWAYS AS IDENTITY, die alte ID braucht OVERRIDING SYSTEM VALUE
    # (die Sequenz liegt ohnehin schon darüber, die ID wurde früher von ihr vergeben).
    ueberschreiben = " OVERRIDING SYSTEM VALUE" if postgres else ""
    conn.execute(
        f"INSERT INTO teilnehmer ({_spaltenliste(postgres, spalten)}){ueberschreiben} "
        f"VALUES ({', '.join('?' for _ in spalten)})",
        [daten[s] for s in spalten],
    )
    if sicherung.get("ergebnis"):
        ergebnis = dict(sicherung["ergebnis"])
        spalten = _spalten_fuer_einfuegen(postgres, "ergebnisse", ergebnis)
        conn.execute(
            f"INSERT INTO ergebnisse ({_spaltenliste(postgres, spalten)}) "
            f"VALUES ({', '.join('?' for _ in spalten)})",
            [ergebnis[s] for s in spalten],
        )
    pruefe_werte_der_kopie(conn)  # D-6: keine Werte speichern, die beim Öffnen abgelehnt würden
    conn.commit()
    return True

def _spalten_fuer_einfuegen(postgres: bool, tabelle: str, werte: dict) -> list[str]:
    """Spaltennamen für das INSERT in teilnehmer_wiederherstellen (Sicherheitskorrektur D-1).
    Die Namen stammen aus einer gesicherten, womöglich fremden Termin-Datei: bei SQLite werden
    nur Spalten übernommen, die das Programm selbst kennt (SCHEMA); alles andere wird nicht
    zurückgeholt. PostgreSQL: das Schema stammt vom Programm, dort unverändert."""
    if postgres:
        return list(werte)
    bekannt = _soll_spalten()[tabelle]
    return [spalte for spalte in werte if spalte in bekannt]

def _spaltenliste(postgres: bool, spalten: list[str]) -> str:
    """Kommagetrennte Spaltenliste für ein INSERT; bei SQLite zusätzlich in Anführungszeichen."""
    return ", ".join(spalten if postgres else (f'"{spalte}"' for spalte in spalten))

def startnummern_wiederherstellen(conn: sqlite3.Connection, nummern: dict[int, int]) -> int:
    """Setzt Startnummern (Teilnehmer-ID -> Nummer) zurück, soweit der Teilnehmer noch keine
    hat und die Nummer frei ist - „Rückgängig“ nach „Startnummern zurücksetzen“. Liefert die
    Zahl der wiederhergestellten Nummern."""
    zahl = 0
    try:
        for teilnehmer_id, nummer in nummern.items():
            hat = conn.execute("SELECT startnummer FROM teilnehmer WHERE id = ?", (teilnehmer_id,)).fetchone()
            if hat is None or hat["startnummer"] is not None:
                continue
            if conn.execute("SELECT 1 FROM teilnehmer WHERE startnummer = ?", (nummer,)).fetchone():
                continue
            conn.execute("UPDATE teilnehmer SET startnummer = ? WHERE id = ?", (nummer, teilnehmer_id))
            zahl += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return zahl

def startnummern_zuruecksetzen(conn: sqlite3.Connection, pruefung: str | None = None) -> int:
    """Entfernt die Startnummern ALLER Teilnehmer des Termins (Marco 09.10.2026), z. B.
    um sie danach mit fehlende_startnummern_vergeben() neu zu vergeben - mit `pruefung`
    (Kürzel) nur die der Teilnehmer dieser Prüfung, einschließlich "keine Teilnahme".
    Liefert die Zahl der Teilnehmer, die vorher eine Nummer hatten."""
    ids = [
        t["id"] for t in list_teilnehmer(conn)
        if t["startnummer"] is not None and (pruefung is None or _teilnehmer_kuerzel(t) == pruefung)
    ]
    try:
        for teilnehmer_id in ids:
            conn.execute("UPDATE teilnehmer SET startnummer = NULL WHERE id = ?", (teilnehmer_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return len(ids)

def teilnehmer_ohne_startnummer(conn: sqlite3.Connection, pruefung: str | None = None) -> list[dict]:
    """Teilnehmende (ohne „keine Teilnahme“) ohne Startnummer, mit `pruefung` (Kürzel) nur
    die dieser Prüfung - gemeinsame Auswahl für die Vergabe, den Hinweis im Reiter
    „Teilnehmer“ und die Rückfrage nach einem Import (UX-Test 2026-11, T14)."""
    return [
        t for t in list_teilnehmer(conn, nur_teilnehmende=True)
        if t["startnummer"] is None and (pruefung is None or _teilnehmer_kuerzel(t) == pruefung)
    ]

def fehlende_startnummern_je_pruefung(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    """(Kürzel, Anzahl) der Prüfungen, in denen teilnehmende Teilnehmer noch keine
    Startnummer haben, in der Reihenfolge von ALLE_PRUEFUNGEN - für den Hinweis unter den
    Startnummern-Knöpfen im Reiter "Teilnehmer" (Marco 09.10.2026)."""
    anzahl: dict[str, int] = {}
    for t in teilnehmer_ohne_startnummer(conn):
        kuerzel = _teilnehmer_kuerzel(t)
        anzahl[kuerzel] = anzahl.get(kuerzel, 0) + 1
    reihenfolge = {p.kuerzel: i for i, p in enumerate(ALLE_PRUEFUNGEN)}
    return sorted(anzahl.items(), key=lambda e: (reihenfolge.get(e[0], len(reihenfolge)), e[0]))

@_mit_rollback
def tausche_startnummern(conn: sqlite3.Connection, teilnehmer_id_a: int, teilnehmer_id_b: int) -> None:
    """Tauscht die Startnummern zweier Teilnehmer atomar - über eine kurzzeitige NULL-
    Zwischenstufe, da 'startnummer INTEGER UNIQUE' ein direktes Vertauschen sonst als
    Dublette ablehnen würde (Teilnehmer B hätte für einen Moment dieselbe Nummer wie
    Teilnehmer A). Erleichtert das Umnummerieren, ohne dass man Startnummern vorher von
    Hand an anderer Stelle 'freimachen' muss (Nutzerwunsch 20.09., Anmerkung zum
    Programm: 'ich muss die Nummern die ich jetzt eigentlich bräuchte erst „frei
    machen“, weil ich nicht doppelt vergeben kann'). Funktioniert unabhängig davon, ob
    einer der beiden (oder beide) noch gar keine Startnummer haben (None)."""
    a = get_teilnehmer(conn, teilnehmer_id_a)
    b = get_teilnehmer(conn, teilnehmer_id_b)
    if a is None or b is None:
        raise ValueError("Teilnehmer nicht gefunden")
    nummer_a, nummer_b = a["startnummer"], b["startnummer"]
    conn.execute("UPDATE teilnehmer SET startnummer = NULL WHERE id = ?", (teilnehmer_id_a,))
    conn.execute("UPDATE teilnehmer SET startnummer = ? WHERE id = ?", (nummer_a, teilnehmer_id_b))
    conn.execute("UPDATE teilnehmer SET startnummer = ? WHERE id = ?", (nummer_b, teilnehmer_id_a))
    conn.commit()

def nummern_ausserhalb_nach_tausch(bereiche: dict[str, tuple[int, int]], a: dict, b: dict) -> int:
    """Wie viele der beiden Startnummern nach einem Tausch zwischen `a` und `b` außerhalb des
    Bereichs der neuen Prüfung lägen (0-2) - für die Warnung vor dem Tausch (Nachtest 2, N4).
    Ohne Nummer oder ohne Bereich zählt nichts; liegen die Nummern schon über Kreuz, bringt der
    Tausch sie gerade zurück (0). Ohne Qt, einzeln testbar (QS B22, W5)."""
    ausserhalb = 0
    for neue_nummer, t in ((b["startnummer"], a), (a["startnummer"], b)):
        bereich = bereiche.get(pruefungs_kuerzel(t["art"], t["stufe"], t["disziplin"]))
        if neue_nummer is not None and bereich and not bereich[0] <= neue_nummer <= bereich[1]:
            ausserhalb += 1
    return ausserhalb

@_mit_rollback
def setze_bezahlt(conn: sqlite3.Connection, teilnehmer_id: int, bezahlt: bool) -> None:
    """Setzt/entfernt die Bezahlt-Markierung eines Teilnehmers, ohne die übrigen
    Stammdaten anzufassen - für den schnellen Umschalten-Button in der Teilnehmerliste
    (z.B. am Anmeldetisch), ohne dafür den kompletten Bearbeiten-Dialog öffnen zu müssen."""
    conn.execute("UPDATE teilnehmer SET bezahlt = ? WHERE id = ?", (int(bezahlt), teilnehmer_id))
    conn.commit()

@_mit_rollback
def setze_keine_teilnahme(conn: sqlite3.Connection, teilnehmer_id: int, keine_teilnahme: bool) -> None:
    """Markiert einen Teilnehmer als nicht erschienen bzw. nimmt die Markierung zurück
    (Nutzerwunsch 02.10.2026). Bereits erfasste Ergebnisse bleiben bewusst unangetastet:
    sie werden nur nicht mehr gewertet und sind nach dem Zurücknehmen wieder wirksam."""
    conn.execute(
        "UPDATE teilnehmer SET keine_teilnahme = ? WHERE id = ?", (int(keine_teilnahme), teilnehmer_id)
    )
    conn.commit()

@_mit_rollback
def delete_teilnehmer(conn: sqlite3.Connection, teilnehmer_id: int) -> None:
    conn.execute("DELETE FROM teilnehmer WHERE id = ?", (teilnehmer_id,))
    conn.commit()

# --- CSV-Import (Meldeformular) ---------------------------------------------
#
# --- Datumsfelder (Codeprüfung 22.09., M5) -----------------------------------------------
#
# Alle Datumsfelder (Veranstaltungsdatum, Geburtsdatum, Wurftag, Tollwutimpfung) werden
# intern IMMER als JJJJ-MM-TT gespeichert - darauf bauen ist_jugendlicher(), der
# Impfpass-Vergleich im PDF und die Dateinamen auf. Eingegeben werden dürfen aber auch
# deutsche Schreibweisen (TT.MM.JJJJ, auch ohne führende Nullen); vorher landete z. B.
# "27.09.2026" unverändert in der Datenbank und ließ Jugendlichen-Statistik und
# Impf-Hervorhebung still falsch rechnen.
_DATUM_ISO_MUSTER = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

_DATUM_DEUTSCH_MUSTER = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")

def lies_datum(text: str | None) -> datetime.date | None:
    """Liest ein Datum in JJJJ-MM-TT oder TT.MM.JJJJ. None bei leerem Wert; ValueError bei
    einem nicht lesbaren oder ungültigen Datum (z. B. 31.02.2026)."""
    wert = (text or "").strip()
    if not wert:
        return None
    iso = _DATUM_ISO_MUSTER.fullmatch(wert)
    deutsch = _DATUM_DEUTSCH_MUSTER.fullmatch(wert)
    if iso:
        jahr, monat, tag = iso.groups()
    elif deutsch:
        tag, monat, jahr = deutsch.groups()
    else:
        # UX-Test 02.10.2026, U14: mit Beispiel statt nur Formatkürzeln.
        raise ValueError(
            f"„{kurzer_text(wert)}“ ist kein gültiges Datum – bitte z. B. 14.11.2026 eingeben (TT.MM.JJJJ)")
    try:
        return datetime.date(int(jahr), int(monat), int(tag))
    except ValueError:
        raise ValueError(f"„{wert}“ ist kein gültiges Datum – diesen Tag gibt es nicht") from None

def normalisiere_datum(text: str | None) -> str | None:
    """Wandelt eine Datumseingabe (siehe lies_datum) in die Speicherform JJJJ-MM-TT um.
    None bei leerem Wert, ValueError bei ungültigem Datum."""
    datum = lies_datum(text)
    return datum.isoformat() if datum else None

def datum_anzeige(gespeichert: str | None) -> str:
    """Speicherform JJJJ-MM-TT -> TT.MM.JJJJ für Eingabefelder/Anzeige. Ein nicht lesbarer
    Altbestand wird unverändert angezeigt (damit er korrigiert werden kann, statt zu
    verschwinden)."""
    try:
        datum = lies_datum(gespeichert)
    except ValueError:
        return gespeichert or ""
    return f"{datum.day:02d}.{datum.month:02d}.{datum.year}" if datum else ""

def datum_oder_none(text: str | None) -> datetime.date | None:
    """Wie lies_datum(), aber tolerant: None statt ValueError - für Auswertungen, die bei
    einem nicht lesbaren Altbestand nicht abbrechen dürfen."""
    try:
        return lies_datum(text)
    except ValueError:
        return None

# --- Überschneidungen (UX-Test 02.10.2026, U2) -----------------------------------------
# Marco: ein Team darf nie gleichzeitig an zwei Stellen eingeplant sein; zwischen zwei
# Starts desselben Teams (z. B. DK-Disziplinen) gilt ein einstellbarer Mindestabstand.
STANDARD_MINDESTABSTAND = 10

def dk_mindestabstand(veranstaltung: dict | None) -> int:
    """Mindestabstand in Minuten zwischen zwei Starts desselben Teams (Standard 10)."""
    roh = (veranstaltung or {}).get("dk_mindestabstand")
    if roh is None or str(roh).strip() == "":
        return STANDARD_MINDESTABSTAND
    try:
        return max(0, int(roh))
    except (TypeError, ValueError):
        return STANDARD_MINDESTABSTAND
