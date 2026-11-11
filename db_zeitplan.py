"""
Zeitplan samt Überschneidungsprüfung und automatischer Verteilung.

Aus db.py ausgelagert (11.11.2026, Schichtenaufteilung); db.py bleibt als Fassade und reicht alle
Namen weiter. Code unverändert. Siehe Architektur.md.
"""

from __future__ import annotations
import datetime
import sqlite3

from db_stamm import (
    dk_mindestabstand,
    get_veranstaltung,
    list_teilnehmer,
)
from db_verbindung import (
    ALLE_DISZIPLINEN,
    _mit_rollback,
)


# --- Zeitplan --------------------------------------------------------------
#
# Siehe Tabellenkommentar bei SCHEMA weiter oben: ein Zeitplan besteht aus einer frei
# wählbaren Anzahl "Richter"-Spuren, jede mit einer eigenen, frei sortierbaren
# Abfolge aus Prüfungsblöcken und Pausen. Ein Prüfungsblock deckt alle Teilnehmer einer
# Art/Leistungsklasse(/Disziplin bei ED) ab; wie viele das sind (und damit wie lange der
# Block insgesamt dauert) ergibt sich erst bei der Berechnung (berechne_zeitplan*) aus den
# aktuell erfassten Teilnehmern - der Eintrag selbst speichert nur die Dauer PRO Teilnehmer.

def list_zeitplan_richter(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM zeitplan_richter ORDER BY reihenfolge").fetchall()
    return [dict(r) for r in rows]

@_mit_rollback
def add_zeitplan_richter(conn: sqlite3.Connection, name: str | None = None) -> int:
    """Legt einen neuen Richter (Zeitplan-Spur) an und hängt ihn ans Ende an.
    Ohne Namen wird automatisch 'Richter N' vergeben (frei umbenennbar)."""
    naechste_reihenfolge = len(list_zeitplan_richter(conn))
    name = name or f"Richter {naechste_reihenfolge + 1}"
    cur = conn.execute(
        "INSERT INTO zeitplan_richter (name, reihenfolge) VALUES (?, ?)",
        (name, naechste_reihenfolge),
    )
    conn.commit()
    return cur.lastrowid

def zeitplan_richter_aus_veranstaltung_anlegen(conn: sqlite3.Connection) -> int:
    """UX-Test 02.10.2026, U8: Legt für die in den Veranstaltungsdaten eingetragenen
    Richter 1-5 je eine Zeitplan-Spur mit ihrem Namen an - aber nur, solange der Zeitplan
    noch gar keine Richter hat (ein bestehender Zeitplan wird nie verändert). Liefert die
    Anzahl der angelegten Richter."""
    if list_zeitplan_richter(conn):
        return 0
    veranstaltung = get_veranstaltung(conn) or {}
    namen = [
        (veranstaltung.get(f"wertungsrichter_{nummer}") or "").strip() for nummer in range(1, 6)
    ]
    namen = [name for name in namen if name]
    for name in namen:
        add_zeitplan_richter(conn, name)
    return len(namen)

@_mit_rollback
def umbenennen_zeitplan_richter(conn: sqlite3.Connection, richter_id: int, name: str) -> None:
    conn.execute("UPDATE zeitplan_richter SET name = ? WHERE id = ?", (name, richter_id))
    conn.commit()

@_mit_rollback
def loesche_zeitplan_richter(conn: sqlite3.Connection, richter_id: int) -> None:
    """Löscht einen Richter samt aller seiner Zeitplan-Einträge (ON DELETE CASCADE)
    und rückt die reihenfolge der verbliebenen Richter lückenlos nach."""
    conn.execute("DELETE FROM zeitplan_richter WHERE id = ?", (richter_id,))
    for neue_position, richter in enumerate(list_zeitplan_richter(conn)):
        conn.execute(
            "UPDATE zeitplan_richter SET reihenfolge = ? WHERE id = ?",
            (neue_position, richter["id"]),
        )
    conn.commit()

@_mit_rollback
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

@_mit_rollback
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

@_mit_rollback
def add_zeitplan_pause(
    conn: sqlite3.Connection, richter_id: int, dauer_minuten: int, bezeichnung: str | None = None,
    nach_eintrag_id: int | None = None,
) -> int:
    """Fügt eine Pause in die Spur des Richters ein - ans Ende oder (UX-Test 02.10.2026,
    U9) direkt nach dem Eintrag `nach_eintrag_id` (z. B. dem in der Liste markierten Block)."""
    eintraege = list_zeitplan_eintraege(conn, richter_id)
    position = len(eintraege)
    if nach_eintrag_id is not None:
        position = next((i + 1 for i, e in enumerate(eintraege) if e["id"] == nach_eintrag_id), position)
    pause_id = _pause_an_position_einfuegen(conn, richter_id, position, dauer_minuten, bezeichnung)
    conn.commit()
    return pause_id

def _pause_an_position_einfuegen(conn, richter_id: int, position: int, dauer_minuten: int, bezeichnung: str | None,
                                 fest_um: str | None = None) -> int:
    """Schiebt die Einträge ab `position` um eins nach hinten und fügt dort eine Pause ein
    (ohne commit - siehe Aufrufer). `fest_um` siehe _pausen_beginn."""
    for eintrag in list_zeitplan_eintraege(conn, richter_id)[position:][::-1]:
        conn.execute(
            "UPDATE zeitplan_eintrag SET reihenfolge = ? WHERE id = ?", (eintrag["reihenfolge"] + 1, eintrag["id"])
        )
    cur = conn.execute(
        """
        INSERT INTO zeitplan_eintrag (richter_id, reihenfolge, typ, dauer_minuten, bezeichnung, fest_um)
        VALUES (?, ?, 'pause', ?, ?, ?)
        """,
        (richter_id, position, dauer_minuten, bezeichnung, fest_um),
    )
    return cur.lastrowid

#: R-B20 (Marco 05.11.2026): Ein Block, der weniger als so viele Minuten vor einer festen Pause
#: begonnen hätte, rückt hinter die Pause (Lücke davor); ein länger laufender wird nicht geteilt.
FESTE_PAUSE_SCHWELLE_MINUTEN = 15

def add_zeitplan_pause_bei_allen(
    conn: sqlite3.Connection, uhrzeit: str, dauer_minuten: int, bezeichnung: str | None = None,
    fest: bool = False,
) -> list[tuple[str | None, str | None]]:
    """UX-Test 02.10.2026, U9 (Marco öffnet damit bewusst die Entscheidung vom 14.09.):
    gleiche Pause bei allen Richtern. Je Spur wird sie vor dem ersten Eintrag eingefügt,
    der um `uhrzeit` (HH:MM) oder später beginnt - ein gerade laufender Block wird also
    nicht geteilt. Alles in einer Transaktion.

    Liefert je Richter (Name, tatsächliche Startzeit "HH:MM") - UX-Nachtest 03.10.2026, N3:
    beginnt die Pause später (laufender Block), soll die Meldung das ehrlich sagen.
    UX-Test 03.11.2026, X1 (Marcos Entscheidung, ersetzt N3 „Pause ans Ende“): Ist ein Richter
    vor der Wunschzeit schon fertig (oder hat keinen Plan), bekommt er KEINE Pause - sie stand
    sonst als sinnlose letzte Zeile im Aushang. Für ihn steht (Name, None) in der Liste.

    R-B20 (Marco 05.11.2026): Mit `fest` beginnt die Pause genau um `uhrzeit` (fest_um). Ein
    Prüfungsblock, der zu dieser Zeit erst weniger als FESTE_PAUSE_SCHWELLE_MINUTEN läuft, rückt
    als Ganzes hinter die Pause - davor bleibt eine Lücke. Ein länger laufender Block wird nicht
    geteilt; die Pause folgt dann direkt nach ihm."""
    zeitpunkt = datetime.datetime.strptime(uhrzeit.strip(), "%H:%M")
    try:
        eingefuegt = []  # (Name, Eintrags-ID oder None = weggelassen)
        for spur in berechne_zeitplan_bloecke(conn):
            bloecke = spur["bloecke"]
            position = next(
                (i for i, block in enumerate(bloecke) if block["start"].time() >= zeitpunkt.time()), len(bloecke)
            )
            if position == len(bloecke) and (not bloecke or bloecke[-1]["ende"].time() <= zeitpunkt.time()):
                eingefuegt.append((spur["richter_name"], None))
                continue
            if fest and position > 0:
                laufend = bloecke[position - 1]
                begonnen = laufend["start"].replace(year=1900, month=1, day=1)
                if (laufend["typ"] == "pruefung" and laufend["ende"].time() > zeitpunkt.time()
                        and zeitpunkt - begonnen < datetime.timedelta(minutes=FESTE_PAUSE_SCHWELLE_MINUTEN)):
                    position -= 1  # kurz vorher begonnen: der Block rückt hinter die Pause
            eingefuegt.append((spur["richter_name"], _pause_an_position_einfuegen(
                conn, spur["richter_id"], position, dauer_minuten, bezeichnung,
                zeitpunkt.strftime("%H:%M") if fest else None)))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    startzeiten = {
        block["id"]: block["start"].strftime("%H:%M")
        for spur in berechne_zeitplan_bloecke(conn) for block in spur["bloecke"]
    }
    return [(name, startzeiten.get(eintrag_id) if eintrag_id is not None else None)
            for name, eintrag_id in eingefuegt]

def zeitplan_eintrag(conn: sqlite3.Connection, eintrag_id: int) -> dict | None:
    """Ein einzelner Zeitplan-Eintrag (Prüfungsblock oder Pause) oder None - z. B. zum
    Bearbeiten, ohne den ganzen Blockplan zu berechnen (OFFEN.md B4, 19.10.2026)."""
    rows = conn.execute("SELECT * FROM zeitplan_eintrag WHERE id = ?", (eintrag_id,)).fetchall()
    return dict(rows[0]) if rows else None

@_mit_rollback
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

@_mit_rollback
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

@_mit_rollback
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
    teilnehmer = list_teilnehmer(conn, nur_teilnehmende=True)
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

def zeitplan_gruppen_status(conn: sqlite3.Connection) -> list[dict]:
    """Wie zeitplan_gruppen(), zusätzlich je Gruppe mit "anzahl" (Teilnehmerzahl) und
    "eingeplant" (bool), ob für diese Art/Stufe/Disziplin bereits mindestens ein
    Prüfungsblock in irgendeiner Richter-Spur angelegt wurde. Ein einzelner passender
    Block reicht dafür aus, egal bei welchem Richter - er deckt ohnehin automatisch ALLE
    Teilnehmer der Gruppe ab (siehe _teilnehmer_fuer_pruefungseintrag: die Zuteilung
    erfolgt live über Art/Stufe/Disziplin, nicht über eine gespeicherte Teilnehmerliste je
    Block). Grundlage für die Übersicht "Offene Starts" im Zeitplan-Tab (Nutzerwunsch
    21.09.: "ob ich von den benötigten Starts auch schon alles erwischt habe" - beim
    horizontalen Scrollen durch viele Richter-Spalten sonst schwer im Blick zu behalten)."""
    geplante_schluessel = {
        (eintrag["art"], eintrag["stufe"], eintrag["disziplin"])
        for richter in list_zeitplan_richter(conn)
        for eintrag in list_zeitplan_eintraege(conn, richter["id"])
        if eintrag["typ"] == "pruefung"
    }
    ergebnis = []
    for gruppe in zeitplan_gruppen(conn):
        schluessel = (gruppe["art"], gruppe["stufe"], gruppe["disziplin"])
        ergebnis.append({
            **gruppe,
            "anzahl": len(gruppe["teilnehmer"]),
            "eingeplant": schluessel in geplante_schluessel,
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
    gefiltert.sort(key=lambda t: (t["startnummer"] is None, t["startnummer"] or 0))
    # UX-Test 02.10.2026, U2: Startversatz = Rotation (Block beginnt mit dem k-ten Team).
    versatz = (eintrag.get("startversatz") or 0) % len(gefiltert) if gefiltert else 0
    return gefiltert[versatz:] + gefiltert[:versatz]

def _zeitplan_startzeit(veranstaltung: dict | None) -> datetime.datetime:
    start_text = (veranstaltung or {}).get("zeitplan_start") or "09:00"
    try:
        return datetime.datetime.strptime(start_text.strip(), "%H:%M")
    except ValueError:
        return datetime.datetime.strptime("09:00", "%H:%M")

def berechne_zeitplan(conn: sqlite3.Connection) -> list[dict]:
    """Berechnet für jeden Richter die vollständige, zeilenweise Abfolge (eine
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
    alle_teilnehmer = list_teilnehmer(conn, nur_teilnehmende=True)
    return [
        {
            "richter_id": richter["id"], "richter": richter["name"],
            "zeilen": _zeitplan_zeilen(list_zeitplan_eintraege(conn, richter["id"]), alle_teilnehmer, uhrzeit_start),
        }
        for richter in list_zeitplan_richter(conn)
    ]

def feste_pausenzeit(eintrag: dict) -> str | None:
    """Die lesbare feste Uhrzeit einer Pause („HH:MM“, R-B20) oder None."""
    try:
        return datetime.datetime.strptime(str(eintrag.get("fest_um") or "").strip(), "%H:%M").strftime("%H:%M")
    except ValueError:
        return None

def _pausen_beginn(aktuelle_zeit: datetime.datetime, eintrag: dict) -> datetime.datetime:
    """Beginn einer Pause: direkt im Anschluss oder - mit fester Uhrzeit (`fest_um`, R-B20) -
    frühestens dann; davor bleibt eine Lücke. Eine unlesbare Angabe (fremde Datei) zählt
    nicht."""
    fest = feste_pausenzeit(eintrag)
    if fest is None:
        return aktuelle_zeit
    uhrzeit = datetime.datetime.strptime(fest, "%H:%M")
    return max(aktuelle_zeit, aktuelle_zeit.replace(hour=uhrzeit.hour, minute=uhrzeit.minute, second=0))

def _zeitplan_zeilen(eintraege: list[dict], alle_teilnehmer: list[dict], uhrzeit_start) -> list[dict]:
    """Zeilen (je Teilnehmer bzw. Pause) einer Richter-Spur mit Start-/Endzeit - siehe
    berechne_zeitplan. Auch für die automatische Verteilung (Plan im Speicher)."""
    aktuelle_zeit = uhrzeit_start
    zeilen = []
    for eintrag in eintraege:
        if eintrag["typ"] == "pause":
            start = _pausen_beginn(aktuelle_zeit, eintrag)
            ende = start + datetime.timedelta(minutes=eintrag["dauer_minuten"])
            zeilen.append({
                "typ": "pause", "start": start, "ende": ende,
                "bezeichnung": eintrag["bezeichnung"] or "Pause",
                "eintrag_id": eintrag["id"], "fest_um": eintrag.get("fest_um"),
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
    return zeilen

def _ueberschneidungen_in_zeilen(zeilen_je_richter: list[tuple[int, list[dict]]], mindestabstand: int) -> list[dict]:
    """Findet Teams, die gleichzeitig bzw. mit zu wenig Abstand in zwei Zeilen stehen.
    Ergebnis je Konflikt: teilnehmer, erste/zweite Zeile (mit richter_id), gleichzeitig."""
    abstand = datetime.timedelta(minutes=mindestabstand)
    je_team: dict[int, list[tuple[int, dict]]] = {}
    for richter_id, zeilen in zeilen_je_richter:
        for zeile in zeilen:
            if zeile["typ"] == "pruefung" and zeile.get("teilnehmer") is not None:
                je_team.setdefault(zeile["teilnehmer"]["id"], []).append((richter_id, zeile))
    konflikte = []
    for eintraege in je_team.values():
        eintraege.sort(key=lambda e: e[1]["start"])
        for i, (richter_a, a) in enumerate(eintraege):
            for richter_b, b in eintraege[i + 1:]:
                if b["start"] < a["ende"] + abstand:
                    konflikte.append({
                        "teilnehmer": a["teilnehmer"], "erste": {**a, "richter_id": richter_a},
                        "zweite": {**b, "richter_id": richter_b}, "gleichzeitig": b["start"] < a["ende"],
                    })
    return konflikte

def zeitplan_ueberschneidungen(conn: sqlite3.Connection) -> list[dict]:
    """Alle Überschneidungen im aktuellen Zeitplan (auch nach Handbearbeitung) - Grundlage
    für die rote Markierung, die Warnliste und die Rückfrage vor dem Zeitplan-PDF."""
    plan = berechne_zeitplan(conn)
    return _ueberschneidungen_in_zeilen(
        [(r["richter_id"], r["zeilen"]) for r in plan], dk_mindestabstand(get_veranstaltung(conn))
    )

def berechne_zeitplan_bloecke(conn: sqlite3.Connection) -> list[dict]:
    """Wie berechne_zeitplan, aber eine Zeile je Eintrag (Prüfungsblock als Ganzes bzw.
    Pause) statt je Teilnehmer - für die kompakte Planungsansicht in der Oberfläche.
    Jeder zurückgegebene Eintrag wird um start/ende/teilnehmer_anzahl ergänzt."""
    veranstaltung = get_veranstaltung(conn)
    uhrzeit_start = _zeitplan_startzeit(veranstaltung)
    alle_teilnehmer = list_teilnehmer(conn, nur_teilnehmende=True)
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
            eintrag["start"] = _pausen_beginn(aktuelle_zeit, eintrag) if eintrag["typ"] == "pause" else aktuelle_zeit
            eintrag["ende"] = eintrag["start"] + datetime.timedelta(minutes=dauer_gesamt)
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
    einfügen, zwischen Richtern verschieben).

    DELETE und alle folgenden INSERTs laufen bewusst in EINER gemeinsamen Transaktion (ein
    einziges conn.commit() erst ganz am Ende, kein Zwischen-Commit nach dem DELETE) und bei
    einem Fehler mit conn.rollback() vollständig zurückgerollt: ein Teilfehler mittendrin
    (z. B. bei einem der INSERTs) soll weder den alten Zeitplan committet-gelöscht noch
    einen halb befüllten neuen zurücklassen, sondern garantiert den Stand VOR diesem Aufruf
    unangetastet erhalten (siehe Fund "kann bei Teilfehler den kompletten Zeitplan leeren",
    Codeprüfung 21.09.)."""
    if not richter_ids:
        return
    try:
        for richter_id in richter_ids:
            conn.execute("DELETE FROM zeitplan_eintrag WHERE richter_id = ?", (richter_id,))

        gruppen = [g for g in zeitplan_gruppen(conn) if g["teilnehmer"]]
        gruppen.sort(key=lambda g: len(g["teilnehmer"]), reverse=True)

        gesamtdauer_je_richter = {richter_id: 0 for richter_id in richter_ids}
        plan: dict[int, list[dict]] = {richter_id: [] for richter_id in richter_ids}
        for gruppe in gruppen:
            ziel_richter = min(richter_ids, key=lambda r: gesamtdauer_je_richter[r])
            plan[ziel_richter].append({
                "typ": "pruefung", "art": gruppe["art"], "stufe": gruppe["stufe"],
                "disziplin": gruppe["disziplin"], "dauer_minuten": standard_dauer_minuten,
                "startversatz": 0, "bezeichnung": None,
            })
            gesamtdauer_je_richter[ziel_richter] += len(gruppe["teilnehmer"]) * standard_dauer_minuten

        # UX-Test 02.10.2026, U2: DK-Blöcke so rotieren (Startversatz), dass kein Team
        # gleichzeitig bzw. ohne Mindestabstand an zwei Stellen steht; reicht die Rotation
        # nicht (z. B. nur 1-2 Teams), eine sichtbare Wartezeit vor dem Block einfügen.
        _dk_bloecke_entzerren(
            plan, list_teilnehmer(conn, nur_teilnehmende=True),
            _zeitplan_startzeit(get_veranstaltung(conn)), dk_mindestabstand(get_veranstaltung(conn)),
        )

        for richter_id, eintraege in plan.items():
            for reihenfolge, e in enumerate(eintraege):
                conn.execute(
                    """
                    INSERT INTO zeitplan_eintrag
                        (richter_id, reihenfolge, typ, art, stufe, disziplin, dauer_minuten, bezeichnung, startversatz)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        richter_id, reihenfolge, e["typ"], e["art"], e["stufe"], e["disziplin"],
                        e["dauer_minuten"], e["bezeichnung"], e["startversatz"],
                    ),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

WARTEZEIT_BEZEICHNUNG = "Wartezeit (DK)"

def _dk_reihenfolge_auflockern(plan: dict[int, list[dict]]) -> None:
    """DK-Blöcke derselben Leistungsklasse in jeder Spur möglichst nicht direkt
    hintereinander (sonst steht ein Team ohne Abstand zweimal nacheinander an)."""
    for rid, eintraege in plan.items():
        rest, neu_geordnet = list(eintraege), []
        while rest:
            letzter = neu_geordnet[-1] if neu_geordnet else None
            gesperrt = ("DK", letzter["stufe"]) if letzter and letzter["art"] == "DK" else None
            wahl = next((e for e in rest if (e["art"], e["stufe"]) != gesperrt), rest[0])
            rest.remove(wahl)
            neu_geordnet.append(wahl)
        plan[rid] = neu_geordnet

def _konflikt_schluessel(konflikte) -> set:
    """Kennzeichnet Überschneidungen unabhängig von ihrer Reihenfolge (Teilnehmer + Blockpaar)."""
    return {
        (k["teilnehmer"]["id"], frozenset((k["erste"]["eintrag_id"], k["zweite"]["eintrag_id"])))
        for k in konflikte
    }

class _DkEntzerrer:
    """Arbeitsstand von _dk_bloecke_entzerren: der Plan (im Speicher), die schon
    festgelegten Blöcke (`fixiert`) und die Hilfen, mit denen ein einzelner DK-Block
    gesetzt wird. Der Plan muss vorher temporäre Eintrags-IDs tragen."""

    def __init__(self, plan: dict[int, list[dict]], alle_teilnehmer: list[dict], uhrzeit_start, mindestabstand: int):
        self.plan = plan
        self.alle_teilnehmer = alle_teilnehmer
        self.uhrzeit_start = uhrzeit_start
        self.mindestabstand = mindestabstand
        self.fixiert: list[str] = []

    def zeilen_je_richter(self):
        return [
            (rid, _zeitplan_zeilen(eintraege, self.alle_teilnehmer, self.uhrzeit_start))
            for rid, eintraege in self.plan.items()
        ]

    def konflikte_mit(self, eintrag):
        relevant = {eintrag["id"], *self.fixiert}
        gefiltert = [
            (rid, [z for z in zeilen if z.get("eintrag_id") in relevant])
            for rid, zeilen in self.zeilen_je_richter()
        ]
        # Alle Konflikte zwischen den festgelegten Blöcken und dem aktuellen - auch solche
        # zwischen zwei festgelegten: verschiebt sich der aktuelle Block, rücken andere
        # Einträge derselben Spur mit.
        return _ueberschneidungen_in_zeilen(gefiltert, self.mindestabstand)

    def bekannte_konflikte(self) -> set:
        """Überschneidungen allein zwischen den schon festgelegten Blöcken."""
        festgelegt = set(self.fixiert)
        return _konflikt_schluessel(
            _ueberschneidungen_in_zeilen(
                [(r, [z for z in zl if z.get("eintrag_id") in festgelegt]) for r, zl in self.zeilen_je_richter()],
                self.mindestabstand,
            )
        )

    def offene_dk_bloecke(self) -> list[tuple[int, dict]]:
        return [
            (rid, e) for rid, eintraege in self.plan.items() for e in eintraege
            if e["typ"] == "pruefung" and e["art"] == "DK"
        ]

    def frueheste_zuerst(self, offen: list[tuple[int, dict]]) -> None:
        """Sortiert die offenen Blöcke nach ihrem Beginn im aktuellen Plan."""
        zeilen = dict(self.zeilen_je_richter())

        def beginn(paar):
            rid, e = paar
            return min(
                (z["start"] for z in zeilen[rid] if z.get("eintrag_id") == e["id"]), default=self.uhrzeit_start
            )

        offen.sort(key=beginn)

    def passender_versatz(self, eintrag: dict, anzahl: int, bekannte: set) -> bool:
        # Erfolgreich, wenn KEINE NEUE Überschneidung entsteht - eine früher nicht
        # auflösbare (dann in der Oberfläche markierte) soll nicht alle weiteren
        # Blöcke blockieren.
        for versatz in range(anzahl):
            eintrag["startversatz"] = versatz
            if not _konflikt_schluessel(self.konflikte_mit(eintrag)) - bekannte:
                return True
        return False

    def an_anderer_stelle_der_spur(self, eintrag: dict, eintraege: list[dict], anzahl: int, bekannte: set) -> bool:
        """1. Versuch: an der geplanten Stelle oder - damit kein Leerlauf entsteht - an
        einer anderen Stelle der Spur desselben Richters, zuerst weiter hinten, dann
        weiter vorn (andere Blöcke füllen dann die Lücke). Ohne Erfolg steht der Block
        danach wieder an seiner ursprünglichen Stelle."""
        ursprung = eintraege.index(eintrag)
        # Nicht hinter noch offene DK-Blöcke derselben LK (dieselben Teams) rücken - sonst
        # stünde ein offener Block direkt vor dem festgelegten, und keine spätere Wartezeit
        # könnte den Abstand zwischen beiden noch herstellen (Verifikation U2a).
        ohne_aktuellen = [e for e in eintraege if e is not eintrag]
        grenze = min(
            (i for i, e in enumerate(ohne_aktuellen)
             if e["typ"] == "pruefung" and e["art"] == "DK" and e["stufe"] == eintrag["stufe"]
             and e["id"] not in self.fixiert),
            default=len(ohne_aktuellen),
        )
        positionen = list(range(ursprung, grenze + 1)) + list(range(ursprung - 1, -1, -1))
        for ziel in positionen:
            eintraege.remove(eintrag)
            eintraege.insert(ziel, eintrag)
            if self.passender_versatz(eintrag, anzahl, bekannte):
                return True
        eintraege.remove(eintrag)
        eintraege.insert(ursprung, eintrag)
        return False

    def mit_wartezeit(self, eintrag: dict, eintraege: list[dict], anzahl: int, bekannte: set) -> None:
        """2. Versuch: sichtbare Wartezeit vor dem Block, schrittweise verlängert."""
        wartezeit = None
        for warte_schritte in range(0, 4 * anzahl + 10):
            if warte_schritte:
                if wartezeit is None:
                    wartezeit = {
                        "typ": "pause", "art": None, "stufe": None, "disziplin": None,
                        "dauer_minuten": eintrag["dauer_minuten"], "startversatz": 0,
                        "bezeichnung": WARTEZEIT_BEZEICHNUNG, "id": f"plan-warte-{id(eintrag)}",
                    }
                    eintraege.insert(eintraege.index(eintrag), wartezeit)
                else:
                    wartezeit["dauer_minuten"] = warte_schritte * eintrag["dauer_minuten"]
            if self.passender_versatz(eintrag, anzahl, bekannte):
                break
        else:
            # Nicht auflösbar (z. B. ein einzelnes Team bei nur einem Richter und großem
            # Mindestabstand): keine nutzlose Wartezeit stehen lassen - die verbleibende
            # Überschneidung wird in der Oberfläche markiert.
            if wartezeit is not None:
                eintraege.remove(wartezeit)
            eintrag["startversatz"] = 0

    def block_festlegen(self, rid: int, eintrag: dict) -> None:
        anzahl = len(_teilnehmer_fuer_pruefungseintrag(self.alle_teilnehmer, eintrag)) or 1
        eintraege = self.plan[rid]
        bekannte = self.bekannte_konflikte()
        if not self.an_anderer_stelle_der_spur(eintrag, eintraege, anzahl, bekannte):
            self.mit_wartezeit(eintrag, eintraege, anzahl, bekannte)
        self.fixiert.append(eintrag["id"])

def _dk_bloecke_entzerren(plan: dict[int, list[dict]], alle_teilnehmer: list[dict], uhrzeit_start, mindestabstand: int) -> None:
    """Wählt im Plan (im Speicher, siehe automatische_zeitplan_verteilung) für jeden
    DK-Block - in der Reihenfolge seines Beginns - den Startversatz, der keine
    Überschneidung mit den bereits festgelegten Blöcken erzeugt. Gelingt das mit keinem
    Versatz, wird vor dem Block eine Wartezeit (Vielfaches der Block-Dauer) eingefügt."""
    _dk_reihenfolge_auflockern(plan)

    # Temporäre IDs, damit sich die berechneten Zeilen ihren Plan-Einträgen zuordnen lassen.
    for eintraege in plan.values():
        for e in eintraege:
            e["id"] = f"plan-{id(e)}"

    entzerrer = _DkEntzerrer(plan, alle_teilnehmer, uhrzeit_start, mindestabstand)
    offen = entzerrer.offene_dk_bloecke()
    while offen:
        # Nächster DK-Block = der mit dem frühesten Beginn im aktuellen Plan.
        entzerrer.frueheste_zuerst(offen)
        rid, eintrag = offen.pop(0)
        entzerrer.block_festlegen(rid, eintrag)

    for eintraege in plan.values():
        for e in eintraege:
            e.pop("id", None)
