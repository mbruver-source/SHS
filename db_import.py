"""Teilnehmer-Import für die Desktop-Version: CSV aus dem Formular-Import, OMA-Meldeliste,
ausgefüllte Anmeldeformular-PDFs und Stammdaten aus einem anderen Termin.

Aus db.py ausgelagert (Codex-Architekturprüfung 27.09.2026). Baut auf db auf (Teilnehmer
anlegen, Datumsfelder, Disziplinen); db selbst importiert dieses Modul nicht, damit kein
Ringimport entsteht.
"""

from __future__ import annotations

import csv
import io
import os
import re
import sqlite3
from dataclasses import dataclass, field

from db import (
    ALLE_DISZIPLINEN,
    ANMELDEFORMULAR_HUENDIN,
    ANMELDEFORMULAR_KENNZEICHNUNG_CHIP,
    ANMELDEFORMULAR_KENNZEICHNUNG_TAETO,
    ANMELDEFORMULAR_PRUEFUNG_PRAEFIX,
    ANMELDEFORMULAR_RUEDE,
    ANMELDEFORMULAR_TEXTFELDER,
    NeuerTeilnehmer,
    add_teilnehmer,
    anmeldeformular_gegenstand_feld,
    angebotene_pruefungen,
    get_teilnehmer,
    get_veranstaltung,
    list_teilnehmer,
    normalisiere_datum,
    pruefung_nach_kuerzel,
    datum_anzeige,
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
    # Nur beim OMA- und Anmeldeformular-Import (importiere_teilnehmer_aus_oma,
    # importiere_anmeldeformular_pdf) befüllt: Zeilen bzw. Dateien, die als bereits
    # vorhandene Meldung erkannt und deshalb bewusst nicht erneut angelegt wurden.
    uebersprungen: list[str] = field(default_factory=list)
    # Allgemeine Hinweise zum Import (nicht an eine Zeile gebunden), z. B. dass mangels
    # hinterlegter angebotener Prüfungen nicht geprüft werden konnte (UX-Test U4).
    hinweise: list[str] = field(default_factory=list)


# UX-Test 02.10.2026, U4/K8: CSV- und OMA-Import lehnen wie der PDF-Import Meldungen für
# Prüfungen ab, die im Termin nicht angeboten werden. Der Hinweis verweist zuerst auf die
# Rücksprache mit dem Teilnehmer - der Weg zum Freischalten steht bewusst nur als Nachsatz
# da, damit er nicht zum bloßen Freischalten verleitet.
_KEINE_ANGEBOTE_HINWEIS = (
    "In diesem Termin sind keine angebotenen Prüfungen hinterlegt - es wurde daher nicht "
    "geprüft, ob die importierten Prüfungen angeboten werden (Reiter „Verwaltung“ → "
    "„Veranstaltungsdaten bearbeiten…“)."
)


def _nicht_angeboten_text(bezeichnung: str, formular: bool = False) -> str:
    vermutung = " - Formular eines anderen Termins?" if formular else "."
    # UX-Nachtest 03.10.2026, N5: der Hinweis zum Freischalten steht nur noch EINMAL am Ende
    # der Meldung (_NICHT_ANGEBOTEN_HINWEIS), statt in jeder abgelehnten Zeile.
    return f"{bezeichnung} wird in diesem Termin nicht angeboten{vermutung} Bitte mit dem Teilnehmer klären."


_NICHT_ANGEBOTEN_HINWEIS = (
    "Nur falls eine Prüfung doch angeboten werden soll: Reiter „Verwaltung“ → "
    "„Veranstaltungsdaten bearbeiten…“."
)


def _hinweise_ergaenzen(fehler: list[str], hinweise: list[str]) -> list[str]:
    """Hängt den Freischalt-Hinweis einmal an, wenn mindestens eine Zeile/Datei wegen einer
    nicht angebotenen Prüfung abgelehnt wurde (N5)."""
    if any("nicht angeboten" in f for f in fehler):
        hinweise.append(_NICHT_ANGEBOTEN_HINWEIS)
    return hinweise


def _zeilen_bezeichnung(zeilennummer: int, vorname: str | None, nachname: str | None) -> str:
    """"Zeile 8 (Mia Meyer)" statt nur "Zeile 8" (UX-Nachtest 03.10.2026, N5)."""
    name = " ".join(t for t in (vorname, nachname) if t)
    return f"Zeile {zeilennummer} ({name})" if name else f"Zeile {zeilennummer}"


def _csv_feld_fehler(feld: str, wert: str | None, erlaubt: str, fehlt_zusatz: str = "") -> str:
    """Verständliche Begründung für eine abgelehnte CSV-Zeile, z. B. "Disziplin fehlt (bei
    Einzeldisziplin ED nötig) – bitte Trümmerfeld, Flächensuche oder Behältnisstrecke
    eintragen" bzw. "Art „EDX“ ist ungültig – bitte ED (…) oder DK (…) eintragen"."""
    if wert is None:
        return f"{feld} fehlt{fehlt_zusatz} – bitte {erlaubt} eintragen"
    return f"{feld} „{wert}“ ist ungültig – bitte {erlaubt} eintragen"


def _angebot_pruefen(teilnehmer: NeuerTeilnehmer, angebotene: set[str]) -> None:
    """Wirft ValueError, wenn die Prüfung des Teilnehmers nicht unter `angebotene`
    (Kürzel, siehe db.ALLE_PRUEFUNGEN) ist. Leeres `angebotene` = nicht prüfen."""
    if not angebotene:
        return
    kuerzel = f"DK{teilnehmer.stufe}" if teilnehmer.art == "DK" else f"ED{teilnehmer.stufe}-{teilnehmer.disziplin}"
    if kuerzel not in angebotene:
        pruefung = pruefung_nach_kuerzel(kuerzel)
        bezeichnung = pruefung.bezeichnung if pruefung else f"{teilnehmer.art} LK {teilnehmer.stufe}"
        raise ValueError(_nicht_angeboten_text(bezeichnung))


def _csv_wert(zeile: dict, spalte: str) -> str | None:
    wert = (zeile.get(spalte) or "").strip()
    # Gegenstück zu _csv_zelle_absichern (Export): das vorangestellte "'" vor einem
    # Formelzeichen wieder entfernen, damit Export -> Import verlustfrei bleibt.
    if len(wert) > 1 and wert[0] == "'":
        kern = wert[1:].lstrip()
        if kern[:1] in _FORMEL_ZEICHEN or (kern[:1] == "'" and kern[1:2] in _FORMEL_ZEICHEN):
            wert = wert[1:].strip()
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

    # Vor-Build-Klärung 03.10.2026: Meldungen in Alltagssprache statt "ungültige Disziplin
    # None für ED (muss eine von ['Trümmerfeld', …] sein)" - fehlend und falsch getrennt.
    art = _csv_wert(zeile, "art")
    if art not in ("ED", "DK"):
        raise ValueError(_csv_feld_fehler("Art", art, "ED (Einzeldisziplin) oder DK (Dreikampf)"))

    stufe_text = _csv_wert(zeile, "stufe")
    try:
        stufe = int(stufe_text) if stufe_text is not None else None
    except ValueError:
        stufe = None
    if stufe not in (1, 2, 3):
        raise ValueError(_csv_feld_fehler("Leistungsklasse", stufe_text, "1, 2 oder 3"))

    disziplin = _csv_wert(zeile, "disziplin")
    if art == "ED":
        if disziplin not in ALLE_DISZIPLINEN:
            raise ValueError(_csv_feld_fehler(
                "Disziplin", disziplin, ", ".join(ALLE_DISZIPLINEN[:-1]) + " oder " + ALLE_DISZIPLINEN[-1],
                fehlt_zusatz=" (bei Einzeldisziplin ED nötig)",
            ))
    else:
        disziplin = None

    schulterhoehe_text = _csv_wert(zeile, "schulterhoehe_cm")
    schulterhoehe_cm = None
    if schulterhoehe_text is not None:
        try:
            schulterhoehe_cm = int(schulterhoehe_text)
        except ValueError:
            raise ValueError(_csv_feld_fehler("Schulterhöhe", schulterhoehe_text, "eine ganze Zahl in cm, z. B. 45"))

    geschlecht = _csv_wert(zeile, "geschlecht")
    if geschlecht is not None and geschlecht not in ("Hündin", "Rüde"):
        raise ValueError(_csv_feld_fehler("Geschlecht", geschlecht, "Hündin oder Rüde"))

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

    Kodierung und Trennzeichen (UX-Test 02.10.2026, U10/N1): UTF-8 (mit/ohne BOM), sonst
    Windows-1252 wie bei Excel "CSV (Trennzeichen-getrennt)"; Komma oder Semikolon wird an
    der Kopfzeile erkannt. add_teilnehmer() committet pro Zeile einzeln."""
    fehler: list[str] = []
    uebersprungen: list[str] = []
    importiert = 0
    letzte_zeile = 1  # Zeile 1 = Kopfzeile
    angebotene = {p.kuerzel for p in angebotene_pruefungen(get_veranstaltung(conn))}
    # UX-Nachtest 03.10.2026, N1: wie beim PDF-/OMA-Import werden bereits vorhandene
    # Meldungen übersprungen - vorher ergab ein zweiter Import derselben Datei alle doppelt.
    vorhandene = {
        _meldungs_schluessel(t["nachname"], t["vorname"], t["rufname_hund"], t["art"], t["stufe"], t["disziplin"])
        for t in list_teilnehmer(conn)
    }
    # UX-Test 02.10.2026, U10/N1: Excel speichert auf deutschem Windows mit Semikolon und
    # (bei "CSV (Trennzeichen-getrennt)") in Windows-1252 - beides wird jetzt erkannt,
    # statt mit "nicht UTF-8-kodiert" abzubrechen (wie beim OMA-Import).
    with open(pfad, "rb") as datei:
        rohdaten = datei.read()
    try:
        text = rohdaten.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = rohdaten.decode("cp1252", errors="replace")
    # Leerzeilen vor der Kopfzeile überspringen (Zeilennummern in Meldungen bleiben die der Datei).
    rest = text.lstrip("\r\n")
    fuehrende_leerzeilen = len(re.findall(r"\r\n|\r|\n", text[: len(text) - len(rest)]))
    text = rest
    kopfzeile = text.splitlines()[0] if text else ""
    trennzeichen = ";" if kopfzeile.count(";") > kopfzeile.count(",") else ","
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=trennzeichen)
    iterator = enumerate(reader, start=2 + fuehrende_leerzeilen)
    letzte_zeile += fuehrende_leerzeilen
    while True:
        try:
            zeilennummer, zeile = next(iterator)
        except StopIteration:
            break
        except csv.Error as exc:
            # z. B. "field larger than field limit" (> 131072 Zeichen in einem Feld) bei
            # einer defekten Datei - vorher eine unbehandelte Exception im GUI-Slot
            # (Verifikation 25.09.). Sauberer Abbruch statt Absturz.
            fehler.append(
                f"Import nach Zeile {letzte_zeile} abgebrochen - die Datei ist beschädigt "
                f"oder keine gültige CSV-Datei ({exc}); bereits importierte Zeilen bleiben "
                "erhalten."
            )
            break
        letzte_zeile = zeilennummer
        bezeichnung = _zeilen_bezeichnung(zeilennummer, _csv_wert(zeile, "vorname"), _csv_wert(zeile, "nachname"))
        try:
            teilnehmer = _csv_zeile_zu_teilnehmer(zeile)
            schluessel = _meldungs_schluessel(
                teilnehmer.nachname, teilnehmer.vorname, teilnehmer.rufname_hund,
                teilnehmer.art, teilnehmer.stufe, teilnehmer.disziplin,
            )
            if schluessel in vorhandene:
                uebersprungen.append(f"{bezeichnung} mit {teilnehmer.rufname_hund} ist bereits gemeldet")
                continue
            _angebot_pruefen(teilnehmer, angebotene)
            add_teilnehmer(conn, teilnehmer)
        except (ValueError, sqlite3.IntegrityError) as exc:
            fehler.append(f"{bezeichnung}: {exc}")
            continue
        vorhandene.add(schluessel)
        importiert += 1
    hinweise = [_KEINE_ANGEBOTE_HINWEIS] if not angebotene and (importiert or fehler) else []
    if not importiert and not fehler and not uebersprungen:
        hinweise.append("Die Datei enthält keine Teilnehmerzeilen - es wurde nichts importiert.")
    return CsvImportErgebnis(
        importiert=importiert, fehler=fehler, uebersprungen=uebersprungen,
        hinweise=_hinweise_ergaenzen(fehler, hinweise),
    )


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
    angebotene = {p.kuerzel for p in angebotene_pruefungen(get_veranstaltung(conn))}
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
        bezeichnung = _zeilen_bezeichnung(
            zeilennummer, _oma_wert(werte, kopf_index, "Starter_Vorname"),
            _oma_wert(werte, kopf_index, "Starter_Nachname"),
        )
        try:
            teilnehmer = _csv_zeile_zu_teilnehmer(_oma_zeile_zu_csv_zeile(werte, kopf_index))
            schluessel = _meldungs_schluessel(
                teilnehmer.nachname, teilnehmer.vorname, teilnehmer.rufname_hund,
                teilnehmer.art, teilnehmer.stufe, teilnehmer.disziplin,
            )
            if schluessel in vorhandene:
                uebersprungen.append(f"{bezeichnung} mit {teilnehmer.rufname_hund} ist bereits gemeldet")
                continue
            _angebot_pruefen(teilnehmer, angebotene)
            add_teilnehmer(conn, teilnehmer)
        except (ValueError, sqlite3.IntegrityError) as exc:
            fehler.append(f"{bezeichnung}: {exc}")
            continue
        vorhandene.add(schluessel)
        importiert += 1
    hinweise = [_KEINE_ANGEBOTE_HINWEIS] if not angebotene and (importiert or fehler) else []
    return CsvImportErgebnis(
        importiert=importiert, fehler=fehler, uebersprungen=uebersprungen,
        hinweise=_hinweise_ergaenzen(fehler, hinweise),
    )


# Nutzerwunsch 28.09.2026: ausfüllbares Anmeldeformular (PDF) je Termin, das die Teilnehmer
# am Rechner ausfüllen und zurückschicken - hier werden die ausgefüllten PDFs wieder als
# Teilnehmer eingelesen. Die Feldnamen stammen ausschließlich aus db.py
# (ANMELDEFORMULAR_*), dieselbe Quelle nutzt pdf_export.erstelle_anmeldeformular_pdf().
# Marcos Entscheidungen: genau EINE Prüfung je Formular (keine oder mehrere angekreuzt ->
# Datei wird mit Hinweis abgelehnt), die eingetragenen Gegenstände gelten für die
# angekreuzte LK und werden als "frei" (gegenstand_N_disziplin = None) gespeichert,
# Dubletten werden wie beim OMA-Import übersprungen.
_PDF_HAKEN_AUS = (None, "", "/Off", "Off")


def _pdf_feldwerte(pfad: str) -> dict[str, object]:
    """Formularfelder einer PDF-Datei als {Feldname: Wert} (leer, wenn die PDF keine
    Formularfelder hat). pypdf wird erst hier importiert: db_import ist nur Teil der
    Desktop-Anwendung, und so bleibt ein fehlendes pypdf auf die Anmeldeformular-Funktion
    beschränkt statt den Programmstart zu verhindern.

    Feldnamen mit Umlauten (z. B. "pruefung_ED2-Trümmerfeld") schreibt reportlab in
    PDFDocEncoding, pypdf liest sie korrekt als "ü" zurück (Rundlauf am 28.09.2026 geprüft).
    Die NFC-Normalisierung (Feldnamen UND Textwerte) fängt zusätzlich PDF-Programme ab, die
    Umlaute beim Speichern zerlegt (NFD) ablegen - sonst würde z. B. die Dublettenprüfung
    ein zerlegtes "Müller" nicht als vorhandenes "Müller" erkennen (Verifikation 28.09.2026,
    Befund 2).

    Kreuze (Checkboxen): Maßgeblich ist der Feldwert /V. Manche PDF-Programme setzen beim
    Ankreuzen aber nur den Darstellungszustand /AS des Widgets - ist /V "aus", gilt das
    Feld deshalb auch dann als angekreuzt, wenn ein Widget gleichen Namens einen
    "An"-Zustand in /AS trägt (Verifikation 28.09.2026, Befund 3)."""
    import unicodedata

    from pypdf import PdfReader

    def nfc(wert):
        return unicodedata.normalize("NFC", str(wert)) if isinstance(wert, str) else wert

    reader = PdfReader(pfad)
    felder = reader.get_fields() or {}
    werte = {
        nfc(str(name)): nfc(feld.get("/V") if hasattr(feld, "get") else None)
        for name, feld in felder.items()
    }
    for seite in reader.pages:
        annots = seite.get("/Annots")
        annots = annots.get_object() if annots is not None else None
        if not isinstance(annots, list):  # fehlt, null oder kaputt
            continue
        for annot in annots:
            # Der /AS-Rückfallweg ist nur eine Ergänzung zu get_fields(): eine unsauber
            # aufgebaute Annotation (null-Einträge, /Parent null, ...) wird übersprungen und
            # darf die sonst lesbare Datei nie zum Scheitern bringen (zweite Verifikation
            # 28.09.2026, Befund L1).
            try:
                _kreuz_aus_darstellung_ergaenzen(annot.get_object(), werte, nfc)
            except Exception:  # noqa: BLE001
                continue
    return werte


def _kreuz_aus_darstellung_ergaenzen(widget, werte: dict, nfc) -> None:
    """Siehe _pdf_feldwerte: übernimmt einen "An"-Zustand aus /AS, wenn /V "aus" ist."""
    if not isinstance(widget, dict):
        return
    zustand = widget.get("/AS")
    name = widget.get("/T")
    if name is None:
        eltern = widget.get("/Parent")
        eltern = eltern.get_object() if eltern is not None else None
        name = eltern.get("/T") if isinstance(eltern, dict) else None
    if name is None or zustand is None or str(zustand) in _PDF_HAKEN_AUS:
        return
    name = nfc(str(name))
    if name in werte and not _pdf_angekreuzt(werte, name):
        werte[name] = str(zustand)


def _pdf_text(werte: dict, feldname: str) -> str:
    wert = werte.get(feldname)
    return "" if wert is None else str(wert).strip()


def _pdf_angekreuzt(werte: dict, feldname: str) -> bool:
    """Checkbox gilt als angekreuzt, wenn ihr Wert nicht "aus" ist - der Exportwert
    ("/Yes", "/On", ...) unterscheidet sich je nach Programm, deshalb nur die Gegenprüfung."""
    wert = werte.get(feldname)
    return (None if wert is None else str(wert).strip()) not in _PDF_HAKEN_AUS


def _anmeldeformular_zu_teilnehmer(werte: dict, angebotene: set[str]) -> tuple[NeuerTeilnehmer, list[str]]:
    """Setzt die Feldwerte eines ausgefüllten Anmeldeformulars in einen NeuerTeilnehmer um.
    `angebotene` sind die Kürzel der im geöffneten Termin angebotenen Prüfungen. Wirft
    ValueError mit einer für den Nutzer verständlichen Begründung. Liefert zusätzlich die
    bei ED nicht übernommenen Gegenstände (UX-Test U11)."""
    if not any(feld in werte for feld in ANMELDEFORMULAR_TEXTFELDER):
        raise ValueError("die PDF ist kein SHS-Anmeldeformular (keine passenden Formularfelder)")

    angekreuzt = [
        name[len(ANMELDEFORMULAR_PRUEFUNG_PRAEFIX):] for name in werte
        if name.startswith(ANMELDEFORMULAR_PRUEFUNG_PRAEFIX) and _pdf_angekreuzt(werte, name)
    ]
    if not angekreuzt:
        raise ValueError("keine Prüfung angekreuzt")
    if len(angekreuzt) > 1:
        bezeichnungen = [
            p.bezeichnung if (p := pruefung_nach_kuerzel(k)) else k for k in angekreuzt
        ]
        raise ValueError(
            f"mehrere Prüfungen angekreuzt ({', '.join(bezeichnungen)}) - je Formular ist "
            "nur eine Prüfung möglich"
        )
    pruefung = pruefung_nach_kuerzel(angekreuzt[0])
    if pruefung is None:
        raise ValueError(f"unbekannte Prüfung {angekreuzt[0]!r} angekreuzt")
    # Verifikation 28.09.2026, Befund 1 (Marco: umsetzen): ein Formular eines anderen
    # Termins (z. B. vom Vorjahr) oder der Import in die falsche Termin-Datei fällt so auf,
    # statt eine hier gar nicht angebotene Prüfung stillschweigend zu übernehmen.
    if not angebotene:
        # Zweite Verifikation 28.09.2026, N1: eigene Meldung statt der Vermutung "Formular
        # eines anderen Termins?", wenn im Termin noch gar nichts hinterlegt ist.
        raise ValueError(
            "in diesem Termin sind noch keine angebotenen Prüfungen hinterlegt (Reiter "
            "„Verwaltung“ → „Veranstaltungsdaten bearbeiten…“)"
        )
    if pruefung.kuerzel not in angebotene:
        raise ValueError(_nicht_angeboten_text(pruefung.bezeichnung, formular=True))

    zeile = {spalte: _pdf_text(werte, feld) for feld, spalte in ANMELDEFORMULAR_TEXTFELDER.items()}
    zeile["art"], zeile["stufe"], zeile["disziplin"] = pruefung.art, str(pruefung.stufe), pruefung.disziplin or ""

    # Schulterhöhe: Teilnehmer schreiben erfahrungsgemäß oft "45 cm" - die Einheit wird
    # toleriert, alles andere (Kommazahlen usw.) prüft _csv_zeile_zu_teilnehmer() wie beim
    # CSV-Import.
    zeile["schulterhoehe_cm"] = re.sub(r"\s*cm\s*$", "", zeile["schulterhoehe_cm"], flags=re.IGNORECASE)

    huendin = _pdf_angekreuzt(werte, ANMELDEFORMULAR_HUENDIN)
    ruede = _pdf_angekreuzt(werte, ANMELDEFORMULAR_RUEDE)
    if huendin and ruede:
        raise ValueError("Hündin und Rüde sind beide angekreuzt")
    zeile["geschlecht"] = "Hündin" if huendin else ("Rüde" if ruede else "")

    # Kennzeichnung: es gibt nur die eine Spalte chip_nr - eine Tätowiernummer wird mit
    # Präfix "Täto " abgelegt, damit sie in den Listen erkennbar bleibt.
    if (
        zeile["chip_nr"]
        and _pdf_angekreuzt(werte, ANMELDEFORMULAR_KENNZEICHNUNG_TAETO)
        and not _pdf_angekreuzt(werte, ANMELDEFORMULAR_KENNZEICHNUNG_CHIP)
    ):
        zeile["chip_nr"] = f"Täto {zeile['chip_nr']}"

    teilnehmer = _csv_zeile_zu_teilnehmer(zeile)
    # Gegenstände nur aus dem Block der angekreuzten LK (LK n = n Gegenstände), als "frei".
    gegenstaende = [
        _pdf_text(werte, anmeldeformular_gegenstand_feld(pruefung.stufe, nummer)) or None
        for nummer in range(1, pruefung.stufe + 1)
    ]
    verworfen: list[str] = []
    if pruefung.art == "ED":
        # UX-Test 02.10.2026, U11: bei Einzeldisziplin gibt es genau einen Gegenstand - das
        # Formular hat für LK 2/3 aber mehrere Felder. Nur den ersten ausgefüllten
        # übernehmen und die übrigen im Import-Ergebnis nennen (statt später beim
        # Bearbeiten eine Rückfrage auszulösen, die sie stillschweigend verwirft).
        ausgefuellt = [g for g in gegenstaende if g]
        verworfen = ausgefuellt[1:]
        gegenstaende = ausgefuellt[:1]
    for nummer, gegenstand in enumerate(gegenstaende, start=1):
        setattr(teilnehmer, f"gegenstand_{nummer}", gegenstand)
        setattr(teilnehmer, f"gegenstand_{nummer}_disziplin", None)
    return teilnehmer, verworfen


def importiere_anmeldeformular_pdf(conn: sqlite3.Connection, pfade: list[str]) -> CsvImportErgebnis:
    """Liest ausgefüllte Anmeldeformular-PDFs (siehe Kommentar oben) ein - eine Datei = eine
    Meldung = ein Teilnehmer. Wie beim CSV-/OMA-Import bricht eine fehlerhafte Datei den
    Import nicht ab: sie wird mit "<Dateiname>: <Grund>" in `fehler` gemeldet, die übrigen
    werden trotzdem importiert. Bereits vorhandene Meldungen (gleicher Name, Hund, Art, LK
    und Disziplin - auch aus einer früheren Datei desselben Aufrufs) landen in
    `uebersprungen`, so lässt sich ein Ordner mit Nachzüglern gefahrlos erneut einlesen."""
    vorhandene = {
        _meldungs_schluessel(t["nachname"], t["vorname"], t["rufname_hund"], t["art"], t["stufe"], t["disziplin"])
        for t in list_teilnehmer(conn)
    }
    angebotene = {p.kuerzel for p in angebotene_pruefungen(get_veranstaltung(conn))}
    fehler: list[str] = []
    uebersprungen: list[str] = []
    hinweise: list[str] = []
    importiert = 0
    for pfad in pfade:
        name = os.path.basename(pfad)
        try:
            werte = _pdf_feldwerte(pfad)
        except ImportError:
            fehler.append(f"{name}: das Einlesen von PDF-Formularen ist nicht verfügbar (pypdf fehlt)")
            continue
        except Exception as exc:  # noqa: BLE001
            # Bewusst breit: pypdf wirft bei beschädigten/fremden Dateien je nach Defekt
            # PdfReadError, aber auch ValueError/KeyError/TypeError u. a. - eine einzelne
            # kaputte Datei darf den Import der übrigen nie verhindern.
            fehler.append(f"{name}: Datei ist keine lesbare PDF-Datei ({exc})")
            continue
        if not werte:
            fehler.append(f"{name}: die PDF enthält keine Formularfelder (kein ausfüllbares Anmeldeformular)")
            continue
        try:
            teilnehmer, verworfen = _anmeldeformular_zu_teilnehmer(werte, angebotene)
            schluessel = _meldungs_schluessel(
                teilnehmer.nachname, teilnehmer.vorname, teilnehmer.rufname_hund,
                teilnehmer.art, teilnehmer.stufe, teilnehmer.disziplin,
            )
            if schluessel in vorhandene:
                uebersprungen.append(
                    f"{name}: {teilnehmer.vorname} {teilnehmer.nachname} mit "
                    f"{teilnehmer.rufname_hund} ist bereits gemeldet"
                )
                continue
            add_teilnehmer(conn, teilnehmer)
        except (ValueError, sqlite3.IntegrityError) as exc:
            fehler.append(f"{name}: {exc}")
            continue
        vorhandene.add(schluessel)
        importiert += 1
        if verworfen:
            hinweise.append(
                f"{name}: bei Einzeldisziplin nur ein Gegenstand – übernommen „{teilnehmer.gegenstand_1}“, "
                "nicht übernommen " + ", ".join(f"„{g}“" for g in verworfen)
            )
    return CsvImportErgebnis(
        importiert=importiert, fehler=fehler, uebersprungen=uebersprungen,
        hinweise=_hinweise_ergaenzen(fehler, hinweise),
    )


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



# Nutzerwunsch 02.10.2026 (UX-Test, N1): Teilnehmer als CSV exportieren - Excel-freundlich
# (Semikolon, UTF-8 mit BOM, Datum TT.MM.JJJJ) und mit denselben Spalten wie der Import,
# sodass die Datei auch wieder eingelesen werden kann (Startnummer/Bezahlt/Status kommen
# zusätzlich dazu und werden beim Import ignoriert).
CSV_EXPORT_SPALTEN = ["startnummer", *CSV_IMPORT_SPALTEN, "bezahlt", "keine_teilnahme"]

# Sicherheitsbefund der Verifikation (Marco 03.10.2026: absichern): Teilnehmerdaten stammen
# von Dritten (Anmelde-PDFs). Ein Wert wie "=HYPERLINK(...)" würde in Excel als Formel
# ausgeführt (CSV-Injection). Solche Werte bekommen ein "'" vorangestellt - Excel zeigt sie
# dann als Text; der Import entfernt es wieder (siehe _csv_wert). "+"/"-" nur, wenn der
# Wert keine Telefonnummer/Zahl ist ("+49 170 …" bleibt unverändert).
_FORMEL_ZEICHEN = ("=", "@", "+", "-", "\t", "\r")
_ZAHL_ODER_TELEFON = re.compile(r"[+-]?[\d\s()/.-]+")


def _csv_zelle_absichern(wert: str) -> str:
    kern = wert.lstrip()  # führende Leerzeichen ändern nichts an der Formel-Erkennung
    if not kern:
        return wert
    if kern[0] == "'" and len(kern) > 1 and kern[1] in _FORMEL_ZEICHEN:
        # Echter Wert, der schon mit "'=" beginnt: ebenfalls schützen, sonst würde der
        # Import das "'" für das eigene Schutzzeichen halten (Verifikation N1).
        return "'" + wert
    if kern[0] not in _FORMEL_ZEICHEN:
        return wert
    if kern[0] in "+-" and _ZAHL_ODER_TELEFON.fullmatch(kern):
        return wert
    return "'" + wert


_CSV_DATUMSSPALTEN = {"tollwutimpfung_bis", "geburtsdatum", "wurftag"}


def exportiere_teilnehmer_csv(conn: sqlite3.Connection, pfad: str) -> int:
    """Schreibt alle Teilnehmer (auch "keine Teilnahme") nach Startnummer sortiert in eine
    CSV-Datei. Liefert die Anzahl der Zeilen."""
    teilnehmer = list_teilnehmer(conn)
    with open(pfad, "w", newline="", encoding="utf-8-sig") as datei:
        schreiber = csv.writer(datei, delimiter=";")
        schreiber.writerow(CSV_EXPORT_SPALTEN)
        for t in teilnehmer:
            zeile = []
            for spalte in CSV_EXPORT_SPALTEN:
                wert = t.get(spalte)
                if spalte in ("bezahlt", "keine_teilnahme"):
                    wert = "ja" if wert else ""
                elif spalte in _CSV_DATUMSSPALTEN:
                    wert = datum_anzeige(wert)
                zeile.append("" if wert is None else _csv_zelle_absichern(str(wert)))
            schreiber.writerow(zeile)
    return len(teilnehmer)


def schreibe_csv_vorlage(pfad: str) -> None:
    """UX-Test 02.10.2026, U10: leere Vorlage (nur Kopfzeile, Excel-freundlich) für eine
    Teilnehmerliste, die z. B. der Schriftführer ausfüllt und die dann über "CSV
    importieren…" eingelesen wird."""
    with open(pfad, "w", newline="", encoding="utf-8-sig") as datei:
        csv.writer(datei, delimiter=";").writerow(CSV_IMPORT_SPALTEN)
