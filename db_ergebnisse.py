"""
Ergebnisse, Bewertung und Auswertung je Teilnehmer.

Aus db.py ausgelagert (11.11.2026, Schichtenaufteilung); db.py bleibt als Fassade und reicht alle
Namen weiter. Code unverändert. Siehe Architektur.md.
"""

from __future__ import annotations
import math
import sqlite3
from shs_core import (
    ABBRUCH_ABK,
    ABBRUCH_TEXT,
    DISQUALIFIZIERT_ABK,
    DISQUALIFIZIERT_TEXT,
    Teilnehmerergebnis,
    Wertnote,
    berechne_rangliste,
    berechne_wertnote_dk,
    berechne_wertnote_ed,
    stechen_gilt,
    ABBRUCH_GRUENDE,
)

from db_stamm import (
    datum_oder_none,
    get_veranstaltung,
    lies_datum,
    list_teilnehmer,
    pruefungs_kuerzel,
)
from db_verbindung import (
    ALLE_DISZIPLINEN,
    ALLE_PRUEFUNGEN,
    DISZIPLIN_SPALTEN,
    pruefung_nach_kuerzel,
    sortierschluessel_text,
    _FORMULAR_POSITION,
    _mit_rollback,
)


# --- Ergebnisse ------------------------------------------------------------

def get_ergebnis(conn: sqlite3.Connection, teilnehmer_id: int) -> dict | None:
    """Liefert die (ggf. teilweise oder noch gar nicht ausgefüllte) Ergebniszeile eines
    Teilnehmers - z. B. um ein Erfassungsformular mit bereits eingetragenen Werten
    vorzubelegen (siehe app_web.py). None, wenn der Teilnehmer selbst nicht existiert
    (jeder existierende Teilnehmer hat durch add_teilnehmer() immer eine - anfangs leere -
    Ergebniszeile, siehe dort)."""
    row = conn.execute("SELECT * FROM ergebnisse WHERE teilnehmer_id = ?", (teilnehmer_id,)).fetchone()
    return dict(row) if row else None

def hat_erfasste_ergebnisse(conn: sqlite3.Connection, teilnehmer_id: int) -> bool:
    """True, sobald für den Teilnehmer irgendein Punktwert oder Disqualifiziert/Abbruch
    eingetragen ist - für die Rückfrage vor "keine Teilnahme" (Nutzerwunsch 02.10.2026)."""
    ergebnis = get_ergebnis(conn, teilnehmer_id)
    if ergebnis is None:
        return False
    if ergebnis.get("disqualifiziert") or ergebnis.get("abbruch"):
        return True
    return any(
        ergebnis.get(spalte) is not None
        for spalten in DISZIPLIN_SPALTEN.values()
        for spalte in spalten
    )

def ergebnisse_je_teilnehmer(conn: sqlite3.Connection) -> dict[int, dict]:
    """Liefert alle Ergebniszeilen auf einmal als {teilnehmer_id: Zeile} - gemeinsam
    genutzt von berechne_auswertung() und der Ergebnistabelle der Desktop-Version, damit
    die Oberfläche nicht selbst SQL gegen die Tabelle ergebnisse absetzt."""
    return {
        r["teilnehmer_id"]: dict(r)
        for r in conn.execute("SELECT * FROM ergebnisse").fetchall()
    }

def pruefe_ergebnis_eingabe(suche: int | None, anzeige: int | None) -> str | None:
    """Gemeinsame Eingaberegel für Desktop und Web (Codeprüfung 22.09., G6): eine
    Disziplin ist entweder komplett (Suche UND Anzeige) oder gar nicht eingetragen.
    Liefert einen Fehlertext für den Nutzer oder None, wenn die Eingabe passt. Die
    Bereichsgrenzen (0-60/0-40) prüfen die Frontends weiterhin selbst bzw. die
    CHECK-Constraints der Datenbank."""
    if (suche is None) != (anzeige is None):
        return "Bitte Suche UND Anzeige eintragen oder beide Felder leer lassen."
    return None

@_mit_rollback
def eintragen_ergebnis(
    conn: sqlite3.Connection, teilnehmer_id: int, disziplin: str, suche: int | None, anzeige: int | None,
    *, commit: bool = True,
) -> None:
    """Trägt Suchleistung/Anzeigeleistung für eine Disziplin eines Teilnehmers ein.

    suche/anzeige dürfen auch beide None sein - das löscht ein zuvor eingetragenes
    Ergebnis wieder (z.B. wenn in der Ergebniserfassung beide Felder einer Zeile geleert
    werden). Die CHECK-Constraints auf den Spalten (BETWEEN 0 AND 60/40) greifen bei
    NULL nicht, SQLite wertet einen NULL-Vergleich nicht als Verletzung.

    commit=False (Sammelspeichern der Ergebniserfassung, Lasttest 16.10.2026): der Aufrufer
    committet selbst. Ein Fehler rollt über _mit_rollback die GANZE offene Transaktion
    zurück, also auch die vorher ohne Commit geschriebenen Ergebnisse."""
    if disziplin not in DISZIPLIN_SPALTEN:
        raise ValueError(f"Unbekannte Disziplin: {disziplin!r}")
    spalte_suche, spalte_anzeige = DISZIPLIN_SPALTEN[disziplin]
    conn.execute(
        f"UPDATE ergebnisse SET {spalte_suche} = ?, {spalte_anzeige} = ? WHERE teilnehmer_id = ?",
        (suche, anzeige, teilnehmer_id),
    )
    if commit:
        conn.commit()

@_mit_rollback
def setze_ergebnis_status(
    conn: sqlite3.Connection, teilnehmer_id: int, disqualifiziert: bool, abbruch: bool,
    *, abbruch_grund: str | None = None, commit: bool = True,
) -> None:
    """Setzt die beiden unabhängigen Status "Disqualifiziert"/"Abbruch" eines Teilnehmers
    (Nutzerwunsch 21.09., siehe ErgebnisTab in app.py). Bei Disqualifiziert und bei einem
    Abbruch ohne Grund bildet berechne_auswertung() unten KEINE Wertnote aus den Punktwerten -
    eine ggf. weiterhin in suche_*/anzeige_*-Spalten stehende Punktzahl bleibt dabei
    unangetastet (die GUI leert/sperrt in diesen Fällen die Eingabe, siehe
    ErgebnisTab._punkteeingabe_sperren, ein direkter DB-Zugriff könnte sie aber weiterhin
    enthalten). commit=False wie bei eintragen_ergebnis().

    R7: `abbruch_grund` (Code aus shs_core.ABBRUCH_GRUENDE) gilt nur zusammen mit abbruch;
    mit Grund bildet berechne_auswertung() eine Teilbewertung aus den eingetragenen Punkten."""
    if abbruch_grund is not None and abbruch_grund not in ABBRUCH_GRUENDE:
        raise ValueError(f"Unbekannter Abbruchgrund: {abbruch_grund!r}")
    conn.execute(
        "UPDATE ergebnisse SET disqualifiziert = ?, abbruch = ?, abbruch_grund = ? WHERE teilnehmer_id = ?",
        (int(disqualifiziert), int(abbruch), abbruch_grund if abbruch else None, teilnehmer_id),
    )
    if commit:
        conn.commit()

@_mit_rollback
def setze_stechen_sieger(conn: sqlite3.Connection, sieger_id: int | None, gruppe_ids: list[int]) -> None:
    """S1 (Marco 03.10.2026): legt den Sieger eines Stechens fest - alle `gruppe_ids` (die
    Punktgleichen auf Platz 1) verlieren die Markierung, `sieger_id` bekommt sie. Mit
    sieger_id=None wird das Stechen wieder auf "offen" gesetzt."""
    for tid in gruppe_ids:
        conn.execute(
            "UPDATE ergebnisse SET stechen_sieger = ? WHERE teilnehmer_id = ?",
            (int(tid == sieger_id), tid),
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

def _teilpunkte(teilnehmer: dict, ergebnis: dict) -> int:
    """R7: Summe aller eingetragenen Punkte der Disziplinen des Teilnehmers (leere Felder
    zählen 0) - für die Teilbewertung nach einem Abbruch mit Grund."""
    disziplinen = [teilnehmer["disziplin"]] if teilnehmer["art"] == "ED" else ALLE_DISZIPLINEN
    return sum(ergebnis.get(spalte) or 0 for d in disziplinen for spalte in DISZIPLIN_SPALTEN[d])

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

def pruefung_bezeichnung(art: str, stufe, disziplin: str | None) -> str:
    """Bezeichnung einer Prüfung wie auf dem Anmeldeformular („DK LK 1“, „Trümmer LK 2“,
    „Behältnisse LK 3“, „Fläche LK 1“) - eine Schreibweise für Listen, Filter, Zeitplan,
    Auswertung und PDFs (Nachtest 2, N5). Unbekannte Kombinationen (z. B. beschädigte Daten)
    ergeben „<Art> LK <Stufe> <Disziplin>“."""
    try:
        pruefung = pruefung_nach_kuerzel(pruefungs_kuerzel(art, int(stufe), disziplin))
    except (TypeError, ValueError):
        pruefung = None
    if pruefung is not None:
        return pruefung.bezeichnung
    return " ".join(str(teil) for teil in (art, "LK", stufe, disziplin if art != "DK" else None) if teil)

def leistungsklasse_label(teilnehmer: dict) -> str:
    """Menschenlesbares Label der Prüfung eines Teilnehmers (pruefung_bezeichnung) - dient
    auch als Filterkriterium in der GUI (Ergebniserfassung/Auswertung)."""
    return pruefung_bezeichnung(teilnehmer["art"], teilnehmer["stufe"], teilnehmer["disziplin"])

def zeitplan_bezeichnung(art: str, stufe, disziplin: str | None) -> str:
    """Bezeichnung eines Prüfungsblocks im Zeitplan: wie pruefung_bezeichnung, beim Dreikampf
    mit der Disziplin des Blocks („DK LK 1 – Trümmerfeld“), da er je Disziplin geplant wird."""
    if art == "DK":
        return f"{pruefung_bezeichnung(art, stufe, None)} – {disziplin}" if disziplin else pruefung_bezeichnung(art, stufe, None)
    return pruefung_bezeichnung(art, stufe, disziplin)

def pruefung_sortierschluessel(bezeichnung: str) -> tuple:
    """Sortierung von Prüfungsbezeichnungen in der Reihenfolge des Anmeldeformulars (DK,
    Trümmer, Behältnisse, Fläche, je LK 1-3) statt alphabetisch; Unbekanntes ans Ende."""
    if bezeichnung in _FORMULAR_POSITION:
        return (_FORMULAR_POSITION[bezeichnung], "")
    return (len(ALLE_PRUEFUNGEN), sortierschluessel_text(bezeichnung))

def sortiere_pruefungen(bezeichnungen) -> list[str]:
    """Prüfungsbezeichnungen in der Reihenfolge des Anmeldeformulars (pruefung_sortierschluessel)
    - eine Stelle für alle Listen, Filter und PDFs (QS B22, W1)."""
    return sorted(bezeichnungen, key=pruefung_sortierschluessel)

# Konstanten für die Richter-Bedarfsberechnung nach Vorgabe des Vereins: 1
# Einzeldisziplin (ED) = 1 Einheit, 1 Dreikampf (DK) = 3 Einheiten (ein Dreikampf-
# Teilnehmer durchläuft alle drei Disziplinen und bindet einen Richter entsprechend
# länger). Ein Richter darf höchstens 36 Einheiten an einem Prüfungstag richten -
# die benötigte Richterzahl ergibt sich aus den Gesamteinheiten, aufgerundet. Zentral hier
# statt doppelt gepflegt (analog dazu, wie shs_core.py die Wertnoten-Logik zentralisiert):
# gemeinsame Grundlage für pdf_export.erstelle_leistungsrichter_bedarf_pdf() und
# berechne_teilnehmer_lk_uebersicht() unten.
LR_EINHEITEN_JE_ART = {"ED": 1, "DK": 3}

LR_EINHEITEN_PRO_RICHTER = 36

def berechne_teilnehmer_lk_uebersicht(conn) -> dict:
    """Liefert eine Übersicht der Teilnehmerzahlen je Art/Leistungsklasse (bei ED
    zusätzlich je Disziplin aufgeschlüsselt), sowie die daraus resultierende Anzahl
    benötigter Richter. Grundlage für den GUI-Reiter "Übersicht Teilnehmer und
    LK" (siehe desktop_auswertung.py) - fachlich identisch mit
    pdf_export.erstelle_leistungsrichter_bedarf_pdf() (nutzt dieselben Konstanten
    LR_EINHEITEN_JE_ART/LR_EINHEITEN_PRO_RICHTER, daher immer konsistente Zahlen
    zwischen GUI-Reiter und PDF-Export).

    Rückgabe:
    {
        "ed": {
            1: {"Trümmerfeld": int, "Flächensuche": int, "Behältnisstrecke": int, "summe": int, "abteilungen": int},
            2: {...gleiche Struktur...},
            3: {...gleiche Struktur...},
        },
        "ed_summe": int,
        "dk": {
            1: {"summe": int, "abteilungen": int},
            2: {...gleiche Struktur...},
            3: {...gleiche Struktur...},
        },
        "dk_summe": int,
        "teilnehmer_gesamt": int,
        "abteilungen_gesamt": int,
        "leistungsrichter_benoetigt": int,
    }

    "Abteilungen" je Teilnehmer = LR_EINHEITEN_JE_ART[art] (ED=1, DK=3) - deckt sich mit
    der Originalvorlage ("Übersicht Teilnehmer"-Tabellenblatt), wo ein Dreikampf-Hund als
    3 Abteilungen zählt (eine je Disziplin) und ein ED-Hund als 1 Abteilung.
    "leistungsrichter_benoetigt" = ceil(abteilungen_gesamt / LR_EINHEITEN_PRO_RICHTER),
    0 wenn abteilungen_gesamt == 0 (kein aufgerundetes ceil(0/36) das fälschlich 0 ergäbe
    - math.ceil(0/36) ist ohnehin 0, aber explizit behandeln macht die Absicht klarer,
    analog zum bestehenden Muster in pdf_export.erstelle_leistungsrichter_bedarf_pdf())."""
    teilnehmer = list_teilnehmer(conn, nur_teilnehmende=True)

    ed = {
        stufe: {
            **{disziplin: 0 for disziplin in ALLE_DISZIPLINEN},
            "summe": 0,
            "abteilungen": 0,
        }
        for stufe in (1, 2, 3)
    }
    dk = {stufe: {"summe": 0, "abteilungen": 0} for stufe in (1, 2, 3)}

    for t in teilnehmer:
        abteilungen_je_teilnehmer = LR_EINHEITEN_JE_ART[t["art"]]
        if t["art"] == "ED":
            gruppe = ed[t["stufe"]]
            gruppe[t["disziplin"]] += 1
        else:
            gruppe = dk[t["stufe"]]
        gruppe["summe"] += 1
        gruppe["abteilungen"] += abteilungen_je_teilnehmer

    ed_summe = sum(gruppe["summe"] for gruppe in ed.values())
    dk_summe = sum(gruppe["summe"] for gruppe in dk.values())
    abteilungen_gesamt = sum(gruppe["abteilungen"] for gruppe in ed.values()) + sum(
        gruppe["abteilungen"] for gruppe in dk.values()
    )
    leistungsrichter_benoetigt = (
        math.ceil(abteilungen_gesamt / LR_EINHEITEN_PRO_RICHTER) if abteilungen_gesamt else 0
    )

    return {
        "ed": ed,
        "ed_summe": ed_summe,
        "dk": dk,
        "dk_summe": dk_summe,
        "teilnehmer_gesamt": ed_summe + dk_summe,
        "abteilungen_gesamt": abteilungen_gesamt,
        "leistungsrichter_benoetigt": leistungsrichter_benoetigt,
    }

# Anzahl Behältnis-Positionen der Behältnisstrecke je Leistungsklasse - 1:1 aus den
# Original-Vorlagen der Bewertungsbögen. Zentral hier: gemeinsame Grundlage für die
# Behältnis-Skizze in pdf_export.py und berechne_behaeltnis_bedarf() unten.
BEHAELTNIS_POSITIONEN = {1: 6, 2: 8, 3: 10}

# Überschrift, Spaltenköpfe und Hinweis der Behältnis-Tabelle - gemeinsam für GUI-Reiter
# und Richter-Bedarf-PDF, damit beide gleich beschriftet bleiben.
BEHAELTNIS_BEDARF_TITEL = "Behältnisse Behältnisstrecke (ED Behältnisstrecke + DK)"

BEHAELTNIS_BEDARF_SPALTEN = ["LK", "Teilnehmer", "leer", "mit Gegenstand", "Material-Verleitung", "gesamt"]

BEHAELTNIS_BEDARF_HINWEIS = (
    "Leere Behältnisse einmal je LK, Behältnis mit Gegenstand und ggf. Material-Verleitung "
    "je Teilnehmer. Positionen: "
    + ", ".join(f"LK{stufe} {anzahl}" for stufe, anzahl in BEHAELTNIS_POSITIONEN.items())
    + "."
)

def behaeltnis_bedarf_zeilentexte(zeile: dict) -> list[str]:
    """Eine Zeile aus berechne_behaeltnis_bedarf() als Anzeigetexte in der Reihenfolge von
    BEHAELTNIS_BEDARF_SPALTEN ("–" für eine nicht vorhandene Material-Verleitung)."""
    verleitung = zeile["material_verleitung"]
    return [
        zeile["bezeichnung"],
        str(zeile["teilnehmer"]),
        str(zeile["leer"]),
        str(zeile["mit_gegenstand"]),
        "–" if verleitung is None else str(verleitung),
        str(zeile["gesamt"]),
    ]

def berechne_behaeltnis_bedarf(conn) -> list[dict]:
    """Benötigte Behältnisse für die Behältnisstrecke je Leistungsklasse (mit Marco am
    25.09. abgestimmt, siehe Fortschritt.md). Grundlage für den GUI-Reiter "Übersicht"
    (desktop_auswertung.py) und die Richter-Bedarf-PDF (pdf_export.py).

    Mitgezählt werden alle Teilnehmer, die die Behältnisstrecke laufen: ED mit Disziplin
    Behältnisstrecke und alle DK. Bei n > 0 Teilnehmern einer LK:
    - leer = Positionen - 1, einmal je LK (die Strecke wird für alle Hunde genutzt),
    - mit Gegenstand = n (jeder Teilnehmer bringt seinen eigenen Gegenstand mit),
    - Material-Verleitung = n, nur in LK3 und nur in der Variante mit separatem
      Behältnis (ohne separates Behältnis liegt sie in einem der leeren).
    Bei n == 0 ist alles 0. LK3 erscheint daher zweimal (ohne/mit separatem Behältnis).

    Rückgabe: 4 Zeilen (LK1, LK2, LK3 ohne, LK3 mit) mit den Schlüsseln "bezeichnung",
    "stufe", "teilnehmer", "leer", "mit_gegenstand", "material_verleitung" (None = gibt
    es in dieser Zeile nicht) und "gesamt"."""
    anzahl = {stufe: 0 for stufe in BEHAELTNIS_POSITIONEN}
    for t in list_teilnehmer(conn, nur_teilnehmende=True):
        if t["art"] == "DK" or t["disziplin"] == "Behältnisstrecke":
            anzahl[t["stufe"]] += 1

    varianten = [
        (1, "LK 1", False),
        (2, "LK 2", False),
        (3, "LK 3 ohne separates Behältnis", False),
        (3, "LK 3 mit separatem Behältnis", True),
    ]
    zeilen = []
    for stufe, bezeichnung, separat in varianten:
        n = anzahl[stufe]
        leer = BEHAELTNIS_POSITIONEN[stufe] - 1 if n else 0
        material_verleitung = n if separat else None
        zeilen.append({
            "bezeichnung": bezeichnung,
            "stufe": stufe,
            "teilnehmer": n,
            "leer": leer,
            "mit_gegenstand": n,
            "material_verleitung": material_verleitung,
            "gesamt": leer + n + (material_verleitung or 0),
        })
    return zeilen

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

def _dk_gegenstand_status(teilnehmer: dict, stufe: int) -> str:
    """Prüft die Gegenstände für Dreikampf (DK) gegen die mit Marco am 23.09.
    präzisierte Leistungsklassen-Regel (Fix 4 vom 16.09. weitergeführt, siehe
    Fortschritt.md): LK1 = mind. 1, LK2 = mind. 2, LK3 = 3 unterschiedliche
    Gegenstand-Texte.
    - Stehen alle Gegenstände auf "gesucht in: frei", reicht diese Mindestanzahl - das ist
      ein gültiger Zustand ohne jede Meldung.
    - Sobald mindestens eine Disziplin ausgewählt ist, müssen alle 3 Disziplinen
      (Trümmerfeld/Flächensuche/Behältnisstrecke) einem Gegenstand zugeordnet sein
      (derselbe Text darf dafür in mehreren Feldern stehen) - mit mindestens der
      Mindestanzahl unterschiedlicher zugeordneter Texte. Ein solcher Mischfall ist nur
      ein Hinweis, kein Fehler.
    Nutzt aus, dass eine Disziplin nie zwei Gegenstand-Feldern zugleich zugeordnet sein
    kann (wird beim Speichern in TeilnehmerDialog._pruefen_und_akzeptieren,
    desktop_dialoge_teilnehmer.py, verhindert).

    Liefert "ok", "fehlt" (zu wenig unterschiedliche Gegenstand-Texte - echter Fehler)
    oder "nicht_zugeordnet" (genug Texte, aber die begonnene Disziplin-Zuordnung ist
    unvollständig - nur Hinweis)."""
    mindestanzahl = {1: 1, 2: 2, 3: 3}.get(stufe, 3)
    texte = {teilnehmer.get(feld) for feld in _GEGENSTAND_FELDER if teilnehmer.get(feld)}
    if len(texte) < mindestanzahl:
        return "fehlt"
    text_je_disziplin: dict[str, str] = {}
    for feld in _GEGENSTAND_FELDER:
        disziplin = teilnehmer.get(f"{feld}_disziplin")
        text = teilnehmer.get(feld)
        if disziplin and text:
            text_je_disziplin[disziplin] = text
    if not text_je_disziplin:
        return "ok"  # alles "frei" - gültig, Mindestanzahl ist erreicht
    alle_disziplinen_abgedeckt = set(text_je_disziplin) == set(ALLE_DISZIPLINEN)
    if alle_disziplinen_abgedeckt and len(set(text_je_disziplin.values())) >= mindestanzahl:
        return "ok"
    return "nicht_zugeordnet"

def _ed_gegenstand_status(teilnehmer: dict, disziplin: str) -> str:
    """Prüft die Gegenstände für Einzeldisziplin (ED): Es gibt nur eine Suchdisziplin
    und daher unabhängig von der Leistungsklasse genau EINEN Gegenstand (Abstimmung mit
    Marco 23.09. - die frühere, von DK übertragene Regel "LK-Zahl = Anzahl Gegenstände"
    konnte bei LK2/LK3 nie erfüllt werden). Der Teilnehmer-Dialog ordnet diesen einen
    Gegenstand bei ED automatisch der gewählten Disziplin zu; "nicht_zugeordnet" und
    "zu_viele" betreffen daher nur Altdaten.

    Liefert "ok", "fehlt" (kein Gegenstand-Text - echter Fehler), "zu_viele" (mehr als
    ein Gegenstand-Text - Hinweis) oder "nicht_zugeordnet" (der eine Text ist nicht der
    ED-Disziplin zugeordnet - Hinweis)."""
    felder_mit_text = [feld for feld in _GEGENSTAND_FELDER if teilnehmer.get(feld)]
    if not felder_mit_text:
        return "fehlt"
    if len(felder_mit_text) > 1:
        return "zu_viele"
    if teilnehmer.get(f"{felder_mit_text[0]}_disziplin") != disziplin:
        return "nicht_zugeordnet"
    return "ok"

def teilnehmer_fehlende_pflichtangaben(teilnehmer: dict) -> list[str]:
    """Liefert eine Liste kurzer, für die Oberfläche gedachter Beschreibungen fehlender
    Prüfungsdaten (leere Liste = vollständig) - Grundlage für das Warnsymbol in der
    Teilnehmerliste (Nutzerwunsch 20.09., Anmerkung zum Programm: 'in der Übersicht von
    den Teilnehmern fehlt mir aktuell aber noch der Überblick, ob ich auch wirklich
    alles erfasst habe [...] ein „Kontrollbutton“ [...], der dann nochmal prüft ob auch
    alle Sachen Bspl. 3 Gegenstände bei LK 3 erfasst sind'). Geprüft werden bewusst nur
    Chip-Nr. und die zur Leistungsklasse passende Gegenstand-Disziplin-Zuordnung - nicht
    die übrigen, weiterhin bewusst optionalen Erfassungsfelder (Absprache mit dem
    Nutzer, siehe Fortschritt.md).

    Rückmeldung 22.09.: "Gegenstände unvollständig" erscheint hier bewusst NUR noch, wenn
    tatsächlich ein Gegenstand-Textfeld fehlt - der mildere Fall "Text vorhanden, aber
    'gesucht in: frei'" ist kein Fehler mehr und taucht hier nicht auf, sondern nur noch
    als reine Info über teilnehmer_gegenstand_hinweis() (siehe unten). Abstimmung 23.09.:
    ED hat nur einen Gegenstand, daher dort "Gegenstand fehlt" (Einzahl)."""
    fehlend: list[str] = []
    if not teilnehmer.get("chip_nr"):
        fehlend.append("Chip-Nr. fehlt")
    stufe = teilnehmer.get("stufe")
    art = teilnehmer.get("art")
    if stufe in (1, 2, 3):
        if art == "DK":
            if _dk_gegenstand_status(teilnehmer, stufe) == "fehlt":
                fehlend.append("Gegenstände unvollständig (Dreikampf)")
        elif art == "ED":
            disziplin = teilnehmer.get("disziplin")
            if disziplin and _ed_gegenstand_status(teilnehmer, disziplin) == "fehlt":
                fehlend.append("Gegenstand fehlt")
    return fehlend

def teilnehmer_gegenstand_hinweis(teilnehmer: dict) -> str | None:
    """Liefert eine milde Info (kein Fehler, siehe teilnehmer_fehlende_pflichtangaben()),
    wenn genug Gegenstand-Texte erfasst sind, die Disziplin-Zuordnung aber unvollständig
    ist (DK: begonnene Zuordnung deckt nicht alle 3 Disziplinen ab; ED: der Gegenstand
    ist nicht der ED-Disziplin zugeordnet) oder bei ED mehr als ein Gegenstand erfasst
    ist - oder None, wenn das nicht zutrifft (entweder in Ordnung, oder es liegt
    stattdessen ein echter Fehler vor, siehe teilnehmer_fehlende_pflichtangaben(), das
    hat Vorrang)."""
    stufe = teilnehmer.get("stufe")
    art = teilnehmer.get("art")
    if stufe not in (1, 2, 3):
        return None
    if art == "DK":
        if _dk_gegenstand_status(teilnehmer, stufe) == "nicht_zugeordnet":
            return "Gegenstände den Suchdisziplinen nicht vollständig zugeordnet"
        return None
    if art == "ED":
        disziplin = teilnehmer.get("disziplin")
        if not disziplin:
            return None
        status = _ed_gegenstand_status(teilnehmer, disziplin)
        if status == "nicht_zugeordnet":
            return "Gegenstand der Suchdisziplin nicht zugeordnet"
        if status == "zu_viele":
            return "Bei ED ist nur ein Gegenstand vorgesehen"
    return None

def alle_leistungsklassen(conn: sqlite3.Connection) -> list[str]:
    """Sortierte Liste aller in diesem Termin tatsächlich vorkommenden Art/LK-Label -
    zum Befüllen eines Filters in der Oberfläche."""
    labels = {leistungsklasse_label(t) for t in list_teilnehmer(conn, nur_teilnehmende=True)}
    return sortiere_pruefungen(labels)

# Nutzerwunsch (21.09., Rückmeldung "Statistik/Jugendliche"): "bei uns im Verband müssen
# Jugendliche gesondert ausgewiesen werden" - als generelles Feature umgesetzt (nicht
# verbandsspezifisch konfigurierbar, siehe Rückfrage-Antwort). Alterskriterium: unter 18
# Jahre, Stichtag ist das Prüfungsdatum (veranstaltung.datum) - nicht das heutige Datum,
# da die Statistik auch nach dem Prüfungstag noch unverändert erzeugt werden können soll.
JUGENDLICHE_ALTERSGRENZE = 18

def ist_jugendlicher(geburtsdatum: str | None, stichtag: str | None) -> bool:
    """True, wenn die Person am `stichtag` (i.d.R. das Prüfungsdatum) jünger als
    JUGENDLICHE_ALTERSGRENZE (18) Jahre ist. Gespeichert wird JJJJ-MM-TT (siehe
    normalisiere_datum); ein Altbestand in TT.MM.JJJJ wird ebenfalls gelesen (M5, 22.09.).
    Fehlt eines der beiden Daten oder lässt es sich nicht als Datum lesen (z. B. leeres
    Geburtsdatum, noch nicht gepflegtes Prüfungsdatum), liefert die Funktion bewusst False
    statt eines Fehlers - ohne bekanntes Geburtsdatum kann niemand als Jugendliche/r
    ausgewiesen werden, das ist der sichere Default (keine falsche Zuordnung)."""
    geburt = datum_oder_none(geburtsdatum)
    tag = datum_oder_none(stichtag)
    if geburt is None or tag is None:
        return False
    alter = tag.year - geburt.year - ((tag.month, tag.day) < (geburt.month, geburt.day))
    return alter < JUGENDLICHE_ALTERSGRENZE

def stechen_gilt_fuer_veranstaltung(conn: sqlite3.Connection) -> bool:
    """PO1 (PO_01012027.md, Marco 01.11.2026): gilt für die Veranstaltung dieses Termins noch
    das Stechen um Platz 1? Entscheidet das Veranstaltungsdatum (shs_core.stechen_gilt). Ohne
    Veranstaltung oder mit unlesbarem Datum gilt weiter das Stechen."""
    veranstaltung = get_veranstaltung(conn)
    try:
        datum = lies_datum(veranstaltung.get("datum") if veranstaltung else None)
    except ValueError:
        datum = None
    return stechen_gilt(datum)

def berechne_auswertung(conn: sqlite3.Connection) -> tuple[list[Teilnehmerergebnis], list[dict]]:
    """Liefert (gerankte Teilnehmer mit Ergebnis, Teilnehmer ohne vollständiges Ergebnis)."""
    teilnehmer_rows = list_teilnehmer(conn, nur_teilnehmende=True)
    ergebnis_rows = ergebnisse_je_teilnehmer(conn)

    fertig: list[Teilnehmerergebnis] = []
    ausstehend: list[dict] = []
    stechen_sieger = {str(tid) for tid, e in ergebnis_rows.items() if e.get("stechen_sieger")}

    for t in teilnehmer_rows:
        # add_teilnehmer() legt für jeden Teilnehmer sofort eine passende Zeile in
        # ergebnisse an (siehe dort) - diese Invariante gilt also im Normalfall immer.
        # QS-Fund (19./20.09.): ein direkter Zugriff über ergebnis_rows[t["id"]] hätte
        # die komplette Auswertung mit einem harten KeyError abstürzen lassen, sollte
        # diese Invariante doch einmal verletzt sein (z.B. durch einen künftigen
        # Programmierfehler oder eine von Hand bearbeitete Termin-Datei) - .get() plus
        # Behandlung wie "noch nicht vollständig bewertet" ist die sichere Variante:
        # der betroffene Teilnehmer taucht dann einfach in der ausstehend-Liste statt
        # die Auswertung für ALLE Teilnehmer zu verhindern.
        ergebnis = ergebnis_rows.get(t["id"])
        if ergebnis is None:
            ausstehend.append(t)
            continue
        if ergebnis.get("disqualifiziert") or ergebnis.get("abbruch"):
            # Disqualifiziert/Abbruch (Nutzerwunsch 21.09.): keine Wertnote aus den Punkten
            # (bei Disqualifiziert und Abbruch ohne Grund werden auch hinterlegte Punkte
            # ignoriert; ein Abbruch mit Grund zählt sie als Teilbewertung, R7) -
            # stattdessen eine Platzhalter-Wertnote mit dem jeweiligen Status-Text, damit
            # der Teilnehmer wie ein "nicht bestanden"-Teilnehmer in der Rangliste
            # erscheint (keine Platzierung, zählt aber als Starter, siehe
            # berechne_rangliste()) statt fälschlich als "noch ausstehend" zu gelten.
            if ergebnis.get("disqualifiziert"):
                wertnote = Wertnote(punkte=0, notentext=DISQUALIFIZIERT_TEXT,
                                    abkuerzung=DISQUALIFIZIERT_ABK, bestanden=False)
            elif ergebnis.get("abbruch_grund") in ABBRUCH_GRUENDE:
                # R7 (Marco 01.11.2026): Teilbewertung - die eingetragenen Punkte zählen
                # (leere Felder als 0), Text laut PO, nie bestanden.
                wertnote = Wertnote(
                    punkte=_teilpunkte(t, ergebnis),
                    notentext=ABBRUCH_GRUENDE[ergebnis["abbruch_grund"]][1],
                    abkuerzung=ABBRUCH_ABK, bestanden=False, teilbewertung=True,
                )
            else:
                wertnote = Wertnote(punkte=0, notentext=ABBRUCH_TEXT, abkuerzung=ABBRUCH_ABK, bestanden=False)
        else:
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

    # PO1: ab der neuen PO (Veranstaltungsdatum ab 01.01.2027) kein Stechen mehr; ein früher
    # gespeicherter stechen_sieger bleibt in der Datenbank, wird dann aber nicht ausgewertet.
    return berechne_rangliste(fertig, stechen_sieger, stechen_gilt_fuer_veranstaltung(conn),
                              sortierschluessel=pruefung_sortierschluessel), ausstehend
