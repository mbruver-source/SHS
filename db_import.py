"""Teilnehmer-Import für die Desktop-Version: CSV aus dem Formular-Import, OMA-Meldeliste
und Stammdaten aus einem anderen Termin.

Aus db.py ausgelagert (Codex-Architekturprüfung 27.09.2026). Baut auf db auf (Teilnehmer
anlegen, Datumsfelder, Disziplinen); db selbst importiert dieses Modul nicht, damit kein
Ringimport entsteht.
"""

from __future__ import annotations

import csv
import re
import sqlite3
from dataclasses import dataclass, field

from db import (
    ALLE_DISZIPLINEN,
    NeuerTeilnehmer,
    add_teilnehmer,
    get_teilnehmer,
    list_teilnehmer,
    normalisiere_datum,
)

# Nutzerwunsch (20.09., Anmerkung zum Programm, Abschnitt "Teilnehmer"): Meldeformulare
# nicht mehr von Hand abtippen müssen. Die Desktop-Anwendung selbst hat keinen eigenen
# KI-Zugriff (arbeitet komplett offline) - deshalb läuft das Einlesen über einen
# vorformulierten Prompt (siehe FormularImportTab/_formular_import_prompt() in app.py),
# den der Nutzer zusammen mit einem ausgefüllten Meldeformular einem beliebigen externen
# KI-System übergibt. Das liefert eine CSV-Datei zurück, die sich hier direkt importieren
# lässt. CSV_IMPORT_SPALTEN ist die einzige Quelle der Wahrheit für die erwarteten
# Spaltennamen - der Prompt-Text in app.py baut seine Kopfzeile aus genau dieser Liste,
# damit Prompt und Parser nie auseinanderlaufen können.
CSV_IMPORT_SPALTEN = [
    "nachname", "vorname", "rufname_hund", "art", "stufe", "disziplin",
    "verein", "zwingername", "geschlecht", "rasse", "schulterhoehe_cm", "chip_nr",
    "tollwutimpfung_bis", "geburtsdatum",
    "verband", "mitgliedsnummer", "wurftag", "strasse", "hausnummer", "plz", "ort",
    "email", "telefon",
    "halter_vorname", "halter_nachname", "halter_strasse", "halter_hausnummer",
    "halter_plz", "halter_ort", "halter_mitgliedsverein", "halter_mitgliedsnummer",
    "halter_lu_nr",
]


@dataclass
class CsvImportErgebnis:
    """Rückgabe von importiere_teilnehmer_aus_csv(): wie viele Zeilen tatsächlich als
    Teilnehmer angelegt wurden, sowie eine Liste menschenlesbarer Fehlertexte ("Zeile N:
    ...") für übersprungene Zeilen - der Import bricht bei einer fehlerhaften Zeile NICHT
    komplett ab, sondern importiert die übrigen trotzdem (siehe FormularImportTab)."""
    importiert: int
    fehler: list[str]
    # Nur beim OMA-Import (importiere_teilnehmer_aus_oma) befüllt: Zeilen, die als bereits
    # vorhandene Meldung erkannt und deshalb bewusst nicht erneut angelegt wurden.
    uebersprungen: list[str] = field(default_factory=list)


def _csv_wert(zeile: dict, spalte: str) -> str | None:
    wert = (zeile.get(spalte) or "").strip()
    return wert or None


def _csv_zeile_zu_teilnehmer(zeile: dict) -> NeuerTeilnehmer:
    """Wandelt eine einzelne CSV-Zeile (Spalten wie CSV_IMPORT_SPALTEN) in einen
    NeuerTeilnehmer um. Wirft ValueError mit einer für den Nutzer verständlichen
    Begründung, wenn Pflichtangaben fehlen oder Art/Stufe/Disziplin/Schulterhöhe nicht
    plausibel sind - importiere_teilnehmer_aus_csv() fängt das je Zeile ab."""
    nachname = _csv_wert(zeile, "nachname")
    vorname = _csv_wert(zeile, "vorname")
    rufname_hund = _csv_wert(zeile, "rufname_hund")
    if not nachname or not vorname or not rufname_hund:
        raise ValueError("Nachname/Vorname/Rufname des Hundes fehlt")

    art = _csv_wert(zeile, "art")
    if art not in ("ED", "DK"):
        raise ValueError(f"ungültige Art {art!r} (muss ED oder DK sein)")

    stufe_text = _csv_wert(zeile, "stufe")
    try:
        stufe = int(stufe_text) if stufe_text is not None else None
    except ValueError:
        stufe = None
    if stufe not in (1, 2, 3):
        raise ValueError(f"ungültige Leistungsklasse {stufe_text!r} (muss 1, 2 oder 3 sein)")

    disziplin = _csv_wert(zeile, "disziplin")
    if art == "ED":
        if disziplin not in ALLE_DISZIPLINEN:
            raise ValueError(f"ungültige Disziplin {disziplin!r} für ED (muss eine von {ALLE_DISZIPLINEN} sein)")
    else:
        disziplin = None

    schulterhoehe_text = _csv_wert(zeile, "schulterhoehe_cm")
    schulterhoehe_cm = None
    if schulterhoehe_text is not None:
        try:
            schulterhoehe_cm = int(schulterhoehe_text)
        except ValueError:
            raise ValueError(f"ungültige Schulterhöhe {schulterhoehe_text!r} (muss eine Zahl sein)")

    geschlecht = _csv_wert(zeile, "geschlecht")
    if geschlecht is not None and geschlecht not in ("Hündin", "Rüde"):
        raise ValueError(f"ungültiges Geschlecht {geschlecht!r} (muss Hündin oder Rüde sein)")

    # Datumsfelder: TT.MM.JJJJ wird akzeptiert und umgewandelt, ein ungültiges Datum
    # überspringt die Zeile wie die übrigen Plausibilitätsfehler (Codeprüfung 22.09., M5,
    # Marcos Entscheidung). geburtsdatum fehlte bis dahin ganz im Import (M6).
    daten: dict[str, str | None] = {}
    for spalte, bezeichnung in (
        ("tollwutimpfung_bis", "Tollwutimpfung"), ("wurftag", "Wurftag"), ("geburtsdatum", "Geburtsdatum"),
    ):
        try:
            daten[spalte] = normalisiere_datum(_csv_wert(zeile, spalte))
        except ValueError as fehler:
            raise ValueError(f"{bezeichnung}: {fehler}") from None

    return NeuerTeilnehmer(
        nachname=nachname, vorname=vorname, rufname_hund=rufname_hund,
        art=art, stufe=stufe, disziplin=disziplin,
        verein=_csv_wert(zeile, "verein"), zwingername=_csv_wert(zeile, "zwingername"),
        geschlecht=geschlecht, rasse=_csv_wert(zeile, "rasse"),
        schulterhoehe_cm=schulterhoehe_cm, chip_nr=_csv_wert(zeile, "chip_nr"),
        tollwutimpfung_bis=daten["tollwutimpfung_bis"], geburtsdatum=daten["geburtsdatum"],
        verband=_csv_wert(zeile, "verband"), mitgliedsnummer=_csv_wert(zeile, "mitgliedsnummer"),
        wurftag=daten["wurftag"], strasse=_csv_wert(zeile, "strasse"),
        hausnummer=_csv_wert(zeile, "hausnummer"), plz=_csv_wert(zeile, "plz"), ort=_csv_wert(zeile, "ort"),
        email=_csv_wert(zeile, "email"), telefon=_csv_wert(zeile, "telefon"),
        halter_vorname=_csv_wert(zeile, "halter_vorname"), halter_nachname=_csv_wert(zeile, "halter_nachname"),
        halter_strasse=_csv_wert(zeile, "halter_strasse"), halter_hausnummer=_csv_wert(zeile, "halter_hausnummer"),
        halter_plz=_csv_wert(zeile, "halter_plz"), halter_ort=_csv_wert(zeile, "halter_ort"),
        halter_mitgliedsverein=_csv_wert(zeile, "halter_mitgliedsverein"),
        halter_mitgliedsnummer=_csv_wert(zeile, "halter_mitgliedsnummer"),
        halter_lu_nr=_csv_wert(zeile, "halter_lu_nr"),
    )


def importiere_teilnehmer_aus_csv(conn: sqlite3.Connection, pfad: str) -> CsvImportErgebnis:
    """Liest eine CSV-Datei (Kopfzeile mit Spaltennamen aus CSV_IMPORT_SPALTEN - fehlende
    oder zusätzliche Spalten werden toleriert) und legt daraus Teilnehmer an, siehe
    FormularImportTab in app.py. Eine einzelne fehlerhafte Zeile bricht den Import nicht
    ab, sondern wird übersprungen und im Ergebnis aufgeführt - der Rest der Datei wird
    trotzdem importiert. 'utf-8-sig' statt 'utf-8', damit ein von Excel/Windows-Tools
    gespeichertes BOM am Dateianfang nicht versehentlich Teil des ersten Spaltennamens
    wird (sonst würde 'nachname' der ersten Spalte nicht erkannt).

    Eine mit einer anderen Kodierung (z.B. Windows-ANSI statt UTF-8) gespeicherte Datei
    löst beim Weiterlesen einen UnicodeDecodeError aus - der tritt außerhalb der
    zeilenweisen try/except-Behandlung auf (beim Vorrücken des Datei-Iterators selbst),
    wird daher separat abgefangen: der Import bricht an der betroffenen Stelle sauber ab
    statt mit einer unbehandelten Exception, bereits importierte Zeilen bleiben erhalten
    (add_teilnehmer() committet pro Zeile einzeln)."""
    fehler: list[str] = []
    importiert = 0
    letzte_zeile = 1  # Zeile 1 = Kopfzeile
    with open(pfad, newline="", encoding="utf-8-sig") as datei:
        reader = csv.DictReader(datei)
        iterator = enumerate(reader, start=2)
        while True:
            try:
                zeilennummer, zeile = next(iterator)
            except StopIteration:
                break
            except UnicodeDecodeError as exc:
                fehler.append(
                    f"Import nach Zeile {letzte_zeile} abgebrochen - Datei ist nicht "
                    f"UTF-8-kodiert ({exc}). Bitte die CSV-Datei mit UTF-8-Kodierung "
                    "speichern und erneut importieren; bereits importierte Zeilen bleiben "
                    "erhalten."
                )
                break
            except csv.Error as exc:
                # z. B. "field larger than field limit" (> 131072 Zeichen in einem Feld) bei
                # einer defekten Datei - vorher eine unbehandelte Exception im GUI-Slot
                # (Verifikation 25.09.). Sauberer Abbruch wie bei der falschen Kodierung.
                fehler.append(
                    f"Import nach Zeile {letzte_zeile} abgebrochen - die Datei ist beschädigt "
                    f"oder keine gültige CSV-Datei ({exc}); bereits importierte Zeilen bleiben "
                    "erhalten."
                )
                break
            letzte_zeile = zeilennummer
            try:
                teilnehmer = _csv_zeile_zu_teilnehmer(zeile)
                add_teilnehmer(conn, teilnehmer)
            except (ValueError, sqlite3.IntegrityError) as exc:
                fehler.append(f"Zeile {zeilennummer}: {exc}")
                continue
            importiert += 1
    return CsvImportErgebnis(importiert=importiert, fehler=fehler)


# Nutzerwunsch 25.09.2026: Meldungen aus der OMA (Online-Meldeannahme) direkt übernehmen.
# Der OMA-Export ("OMA-ExportGeneric_Spürhundesport") ist tabulatorgetrennt, Windows-1252-
# kodiert, hat vor der Kopfzeile eine Metazeile "[Sportart,Datum,Veranstalter]" und
# mehrfach die Spalte "RESERVE". Die Zuordnung wurde mit Marco Spalte für Spalte
# abgestimmt (siehe Fortschritt.md) - nicht aufgeführte Spalten (UeID, Anrede, Land,
# ZBRegNr, Meldung_*) werden bewusst ignoriert, ebenso die Metazeile.
OMA_SPALTEN = {
    "Starter_Nachname": "nachname", "Starter_Vorname": "vorname",
    "Starter_Geburtstag": "geburtsdatum", "Starter_EMail": "email",
    "Starter_Verein": "verein", "Starter_Verband": "verband",
    "Starter_MitglNr": "mitgliedsnummer",
    "Hund_Rufname": "rufname_hund", "Hund_Zwingername": "zwingername",
    "Hund_Rasse": "rasse", "Hund_Wurftag": "wurftag", "Hund_Chipnummer": "chip_nr",
    "Hund_LBNummer": "halter_lu_nr",
}
OMA_PFLICHTSPALTEN = ["Starter_Nachname", "Starter_Vorname", "Hund_Rufname", "SHS_Disziplinen"]
OMA_DISZIPLINEN = {
    "Trümmersuche": ("ED", "Trümmerfeld"),
    "Flächensuche": ("ED", "Flächensuche"),
    "Behältnissuche": ("ED", "Behältnisstrecke"),
    "Dreikampf": ("DK", None),
}
OMA_GESCHLECHT = {"0": "Hündin", "1": "Rüde"}
_OMA_DISZIPLIN_MUSTER = re.compile(r"LK\s*([1-3])\s+(.+)")


def _oma_wert(werte: list[str], kopf_index: dict[str, int], spalte: str) -> str:
    """Wert einer OMA-Spalte; "-" (OMA-Platzhalter für leer) und fehlende Spalten/Zellen
    gelten als leer."""
    index = kopf_index.get(spalte)
    if index is None or index >= len(werte):
        return ""
    wert = werte[index].strip()
    return "" if wert == "-" else wert


def _oma_zeile_zu_csv_zeile(werte: list[str], kopf_index: dict[str, int]) -> dict:
    """Setzt eine OMA-Zeile in eine Zeile mit den Schlüsseln aus CSV_IMPORT_SPALTEN um, damit
    sie anschließend dieselbe Prüfung wie der Formular-Import durchläuft
    (_csv_zeile_zu_teilnehmer). ValueError bei unbekanntem Geschlecht/Disziplin."""
    zeile = {ziel: _oma_wert(werte, kopf_index, spalte) for spalte, ziel in OMA_SPALTEN.items()}
    # Verband: Starter_Verband hat Vorrang, Hund_LBVerband nur als Ersatz (Marcos Entscheidung).
    if not zeile["verband"]:
        zeile["verband"] = _oma_wert(werte, kopf_index, "Hund_LBVerband")

    geschlecht = _oma_wert(werte, kopf_index, "Hund_Geschlecht")
    if geschlecht:
        if geschlecht not in OMA_GESCHLECHT:
            raise ValueError(f"unbekanntes Geschlecht {geschlecht!r} (erwartet 0 = Hündin oder 1 = Rüde)")
        zeile["geschlecht"] = OMA_GESCHLECHT[geschlecht]

    disziplin_text = _oma_wert(werte, kopf_index, "SHS_Disziplinen")
    treffer = _OMA_DISZIPLIN_MUSTER.fullmatch(disziplin_text)
    zuordnung = OMA_DISZIPLINEN.get(treffer.group(2).strip()) if treffer else None
    if zuordnung is None:
        raise ValueError(
            f"unbekannte Disziplin {disziplin_text!r} (erwartet z. B. 'LK1 Trümmersuche', "
            "'LK2 Flächensuche', 'LK3 Behältnissuche' oder 'LK1 Dreikampf')"
        )
    zeile["art"], zeile["disziplin"] = zuordnung
    zeile["stufe"] = treffer.group(1)
    return zeile


def _meldungs_schluessel(nachname, vorname, rufname_hund, art, stufe, disziplin) -> tuple:
    """Vergleichsschlüssel für die Dublettenerkennung beim OMA-Import."""
    def norm(text):
        return (text or "").strip().casefold()
    return (norm(nachname), norm(vorname), norm(rufname_hund), art, int(stufe), disziplin)


def importiere_teilnehmer_aus_oma(conn: sqlite3.Connection, pfad: str) -> CsvImportErgebnis:
    """Liest einen OMA-Export (siehe OMA_SPALTEN) und legt daraus Teilnehmer an - eine
    OMA-Zeile = eine Meldung = ein Teilnehmer. Wie importiere_teilnehmer_aus_csv() wird
    eine fehlerhafte Zeile übersprungen und gemeldet, der Rest trotzdem importiert.
    Zusätzlich wird eine Meldung übersprungen, die im Termin (oder weiter oben in derselben
    Datei) bereits mit gleichem Namen, Hund, Art, LK und Disziplin existiert - so lässt sich
    ein späterer Export mit Nachmeldungen gefahrlos erneut importieren.

    Kodierung: die OMA liefert Windows-1252; UTF-8 (auch mit BOM) wird ebenfalls erkannt.
    Zeilennummern in den Meldungen beziehen sich auf die Datei (inkl. Metazeile/Kopf)."""
    with open(pfad, "rb") as datei:
        rohdaten = datei.read()
    try:
        text = rohdaten.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = rohdaten.decode("cp1252", errors="replace")

    # Bewusst zeilenweise mit split("\t") statt csv.reader (Verifikation 25.09.): der
    # OMA-Export kennt keine Anführungszeichen, und so gibt es weder das Feldgrößen-Limit
    # von csv.reader (csv.Error bei > 131072 Zeichen) noch Probleme mit reinen
    # CR-Zeilenenden. (nummer, zeile) mit Dateizeilennummer ab 1; Leerzeilen - auch
    # zwischen Metazeile und Kopf - werden übersprungen.
    zeilen = [
        (nummer, zeile) for nummer, zeile in enumerate(re.split(r"\r\n|\r|\n", text), start=1)
        if zeile.strip()
    ]
    if zeilen and zeilen[0][1].lstrip().startswith("["):
        # Metazeile "[Spürhundesport,Datum,Veranstalter]" - wird ignoriert.
        zeilen = zeilen[1:]

    kopf = [spalte.strip() for spalte in zeilen[0][1].split("\t")] if zeilen else []
    kopf_index: dict[str, int] = {}
    for index, spalte in enumerate(kopf):
        kopf_index.setdefault(spalte, index)
    fehlend = [spalte for spalte in OMA_PFLICHTSPALTEN if spalte not in kopf_index]
    if fehlend:
        return CsvImportErgebnis(importiert=0, fehler=[
            "Die Datei ist kein OMA-Export (fehlende Spalte(n): " + ", ".join(fehlend) + "). "
            "Es wurde nichts importiert."
        ])

    vorhandene = {
        _meldungs_schluessel(t["nachname"], t["vorname"], t["rufname_hund"], t["art"], t["stufe"], t["disziplin"])
        for t in list_teilnehmer(conn)
    }
    fehler: list[str] = []
    uebersprungen: list[str] = []
    importiert = 0
    pflicht_bis = max(kopf_index[spalte] for spalte in OMA_PFLICHTSPALTEN)
    for zeilennummer, zeile in zeilen[1:]:
        werte = zeile.split("\t")
        if len(werte) <= pflicht_bis:
            # Abgeschnittene Zeile: sonst käme die irreführende Meldung "unbekannte
            # Disziplin ''", weil SHS_Disziplinen fehlt.
            fehler.append(
                f"Zeile {zeilennummer}: Zeile ist unvollständig (nur {len(werte)} von "
                f"{len(kopf)} Spalten) - Datei evtl. abgeschnitten oder beschädigt"
            )
            continue
        try:
            teilnehmer = _csv_zeile_zu_teilnehmer(_oma_zeile_zu_csv_zeile(werte, kopf_index))
            schluessel = _meldungs_schluessel(
                teilnehmer.nachname, teilnehmer.vorname, teilnehmer.rufname_hund,
                teilnehmer.art, teilnehmer.stufe, teilnehmer.disziplin,
            )
            if schluessel in vorhandene:
                uebersprungen.append(
                    f"Zeile {zeilennummer}: {teilnehmer.vorname} {teilnehmer.nachname} mit "
                    f"{teilnehmer.rufname_hund} ist bereits gemeldet"
                )
                continue
            add_teilnehmer(conn, teilnehmer)
        except (ValueError, sqlite3.IntegrityError) as exc:
            fehler.append(f"Zeile {zeilennummer}: {exc}")
            continue
        vorhandene.add(schluessel)
        importiert += 1
    return CsvImportErgebnis(importiert=importiert, fehler=fehler, uebersprungen=uebersprungen)


def importiere_teilnehmer_stammdaten(
    quelle_conn: sqlite3.Connection, ziel_conn: sqlite3.Connection, teilnehmer_ids: list[int]
) -> int:
    """Übernimmt die ausgewählten Teilnehmer (per ID in quelle_conn) als NEUE Teilnehmer in
    ziel_conn - für 'Teilnehmer aus anderem Termin importieren' (Nutzerwunsch 20.09.,
    Anmerkung zum Programm: 'Teilnehmer müssen wieder einzeln eingegeben werden [...] ist
    Option möglich, von anderem Termin importieren?'). Siehe TerminImportDialog in app.py.

    Anders als kopiere_termin_daten() weiter unten (die für die Web-Sync einen KOMPLETTEN
    Termin 1:1 überträgt, inkl. Startnummer/Gegenstand-Zuordnung/Bezahlt-Status/Ergebnis)
    werden hier bewusst NUR die über mehrere Prüfungstage hinweg gültigen Stammdaten
    übernommen (Absprache mit dem Nutzer) - Startnummer, Gegenstand-Zuordnung, Bezahlt-
    Status und ein eventuell schon eingetragenes Ergebnis gehören zum jeweils EINEN
    Prüfungstag und bleiben deshalb auf ihren NeuerTeilnehmer-Defaults (None/False), auch
    wenn die Quelle bereits welche hatte. Art/Leistungsklasse/Disziplin müssen technisch
    trotzdem mitkommen (Pflichtfelder in der Datenbank, ein Teilnehmer kann nicht ohne sie
    angelegt werden) - lassen sich im Teilnehmer-Dialog nach dem Import aber wie gewohnt
    sofort anpassen, falls sich die Meldung geändert hat.

    Keine Dubletten-Prüfung (Absprache mit dem Nutzer: einfach zusätzlich anlegen - der
    Nutzer erkennt und bereinigt Dubletten im Zweifel selbst). Liefert die Anzahl der
    tatsächlich importierten Teilnehmer (übersprungen wird nur eine in quelle_conn nicht
    mehr vorhandene ID, z.B. durch eine zwischenzeitliche Änderung)."""
    importiert = 0
    for teilnehmer_id in teilnehmer_ids:
        alt = get_teilnehmer(quelle_conn, teilnehmer_id)
        if alt is None:
            continue
        neu = NeuerTeilnehmer(
            nachname=alt["nachname"], vorname=alt["vorname"], rufname_hund=alt["rufname_hund"],
            art=alt["art"], stufe=alt["stufe"], disziplin=alt["disziplin"],
            verein=alt.get("verein"), zwingername=alt.get("zwingername"), geschlecht=alt.get("geschlecht"),
            schulterhoehe_cm=alt.get("schulterhoehe_cm"), chip_nr=alt.get("chip_nr"),
            rasse=alt.get("rasse"), tollwutimpfung_bis=alt.get("tollwutimpfung_bis"),
            geburtsdatum=alt.get("geburtsdatum"),
            verband=alt.get("verband"), mitgliedsnummer=alt.get("mitgliedsnummer"), wurftag=alt.get("wurftag"),
            strasse=alt.get("strasse"), hausnummer=alt.get("hausnummer"), plz=alt.get("plz"), ort=alt.get("ort"),
            email=alt.get("email"), telefon=alt.get("telefon"),
            halter_vorname=alt.get("halter_vorname"), halter_nachname=alt.get("halter_nachname"),
            halter_strasse=alt.get("halter_strasse"), halter_hausnummer=alt.get("halter_hausnummer"),
            halter_plz=alt.get("halter_plz"), halter_ort=alt.get("halter_ort"),
            halter_mitgliedsverein=alt.get("halter_mitgliedsverein"),
            halter_mitgliedsnummer=alt.get("halter_mitgliedsnummer"), halter_lu_nr=alt.get("halter_lu_nr"),
            # Bewusst NICHT übernommen: startnummer, gegenstand_1/2/3(_disziplin), bezahlt -
            # bleiben auf ihren NeuerTeilnehmer-Defaults (None/False), siehe Docstring oben.
        )
        add_teilnehmer(ziel_conn, neu)
        importiert += 1
    return importiert
