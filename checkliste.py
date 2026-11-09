"""
Checkliste zum Abhaken im Reiter „Verwaltung“ (Marco, 09.11.2026): der Ablauf eines
Prüfungstermins aus Kapitel 1 des Handbuchs in einzelnen Schritten, dazu eigene Kategorien und
Punkte. Reine Fachlogik ohne Qt und ohne Datenbankzugriff.

Gespeichert wird je Termin in zwei Spalten der Tabelle `veranstaltung`:

- `checkliste`: JSON-Liste der erledigten Schritt-Kennungen (feste und eigene).
- `checkliste_eigene`: JSON mit den eigenen Kategorien und Punkten,
  `{"kategorien": [{"id": "e1", "name": "..."}], "punkte": [{"id": "e2", "kategorie": "e1", "text": "..."}]}`.
  `kategorie` ist die Kennung einer eigenen Kategorie oder der Schlüssel einer festen
  (z. B. "vorher"). Eigene Kategorien stehen hinter den festen, eigene Punkte hinter den festen
  Punkten ihrer Kategorie.

Die festen Kennungen und Schlüssel sind stabil (nie umbenennen oder wiederverwenden); unbekannte
Kennungen in der Datei werden beim Lesen ignoriert. Eigene Kennungen heißen "e1", "e2", ….
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

#: (Schlüssel, Titel, [(Kennung, Text), ...]) in der Reihenfolge des Ablaufs
CHECKLISTE: list[tuple[str, str, list[tuple[str, str]]]] = [
    ("vorher", "Wochen vorher", [
        ("veranstaltung", "Termin angelegt, Veranstaltungsdaten und angebotene Prüfungen eingetragen"),
        ("anmeldeformular", "Anmeldeformular (PDF) erzeugt und mit der Ausschreibung verschickt"),
    ]),
    ("meldungen", "Mit den Meldungen", [
        ("teilnehmer", "Teilnehmer erfasst (auch aus Formular-Import, CSV oder OMA)"),
        ("zahlungen", "Zahlungen abgehakt"),
    ]),
    ("tage8", "8 Tage vorher", [
        ("zeitplan", "Zeitplan erstellt"),
        ("richter_kontakt", "Richter kontaktiert und Zeitplan (PDF) übermittelt"),
        ("zeitplan_aenderung", "Bei späteren Änderungen Zeitplan erneut gesendet"),
    ]),
    ("kurz", "Kurz vorher", [
        ("startnummern", "Startnummern geprüft"),
        ("gegenstaende", "Gegenstände geprüft"),
        ("bewertungsboegen", "Bewertungsbögen gedruckt"),
        ("listen", "Listen gedruckt"),
    ]),
    ("tag", "Am Prüfungstag", [
        ("ergebnisse", "Ergebnisse eingetragen"),
        ("speichern", "Regelmäßig gespeichert"),
    ]),
    ("danach", "Danach", [
        ("ergebnisliste", "Rangliste und Ergebnisliste erstellt"),
        ("etiketten", "Etiketten gedruckt"),
        ("statistik", "Statistik erstellt"),
        ("abrechnung", "Leistungsrichter abgerechnet (Quittungen unterschrieben)"),
    ]),
    ("schluss", "Zum Schluss", [
        ("sicherung", "Datensicherung erstellt"),
    ]),
]

ALLE_KENNUNGEN = [kennung for _s, _t, punkte in CHECKLISTE for kennung, _text in punkte]
_FESTE_SCHLUESSEL = [schluessel for schluessel, _t, _p in CHECKLISTE]

# Grenzen gegen Tippfehler und beschädigte Dateien
MAX_KATEGORIEN = 20
MAX_PUNKTE = 200
MAX_NAME = 60
MAX_TEXT = 120


@dataclass(frozen=True)
class Punkt:
    kennung: str
    text: str
    eigen: bool


@dataclass(frozen=True)
class Kategorie:
    schluessel: str
    titel: str
    eigen: bool
    punkte: tuple[Punkt, ...]


def _bereinigt(text, maximum: int) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:maximum]


def eigene_lesen(veranstaltung: dict | None) -> dict:
    """Eigene Kategorien und Punkte aus `checkliste_eigene`; Unlesbares ergibt eine leere
    Struktur, Punkte ohne vorhandene Kategorie entfallen."""
    leer = {"kategorien": [], "punkte": []}
    roh = (veranstaltung or {}).get("checkliste_eigene")
    if not roh:
        return leer
    try:
        daten = json.loads(roh)
    except (TypeError, ValueError):
        return leer
    if not isinstance(daten, dict):
        return leer
    kategorien, punkte, benutzt = [], [], set(ALLE_KENNUNGEN) | set(_FESTE_SCHLUESSEL)
    for eintrag in daten.get("kategorien") if isinstance(daten.get("kategorien"), list) else []:
        if not isinstance(eintrag, dict) or len(kategorien) >= MAX_KATEGORIEN:
            continue
        kennung, name = eintrag.get("id"), _bereinigt(eintrag.get("name"), MAX_NAME)
        if isinstance(kennung, str) and re.fullmatch(r"e\d+", kennung) and name and kennung not in benutzt:
            benutzt.add(kennung)
            kategorien.append({"id": kennung, "name": name})
    gueltige = set(_FESTE_SCHLUESSEL) | {k["id"] for k in kategorien}
    for eintrag in daten.get("punkte") if isinstance(daten.get("punkte"), list) else []:
        if not isinstance(eintrag, dict) or len(punkte) >= MAX_PUNKTE:
            continue
        kennung, text = eintrag.get("id"), _bereinigt(eintrag.get("text"), MAX_TEXT)
        if (isinstance(kennung, str) and re.fullmatch(r"e\d+", kennung) and kennung not in benutzt
                and text and isinstance(eintrag.get("kategorie"), str) and eintrag["kategorie"] in gueltige):
            benutzt.add(kennung)
            punkte.append({"id": kennung, "kategorie": eintrag["kategorie"], "text": text})
    return {"kategorien": kategorien, "punkte": punkte}


def eigene_als_text(eigene: dict) -> str | None:
    """Speicherform der eigenen Kategorien und Punkte; None, wenn es keine gibt."""
    if not eigene.get("kategorien") and not eigene.get("punkte"):
        return None
    return json.dumps(eigene, ensure_ascii=False, sort_keys=True)


def struktur(veranstaltung: dict | None) -> list[Kategorie]:
    """Alle Kategorien in Anzeigereihenfolge: feste, dann eigene; je Kategorie erst die festen,
    dann die eigenen Punkte."""
    eigene = eigene_lesen(veranstaltung)

    def eigene_punkte(schluessel: str) -> list[Punkt]:
        return [Punkt(p["id"], p["text"], True) for p in eigene["punkte"] if p["kategorie"] == schluessel]

    ergebnis = [
        Kategorie(schluessel, titel, False,
                  tuple([Punkt(k, t, False) for k, t in punkte] + eigene_punkte(schluessel)))
        for schluessel, titel, punkte in CHECKLISTE
    ]
    ergebnis += [Kategorie(k["id"], k["name"], True, tuple(eigene_punkte(k["id"]))) for k in eigene["kategorien"]]
    return ergebnis


def alle_kennungen(kategorien: list[Kategorie]) -> list[str]:
    return [p.kennung for k in kategorien for p in k.punkte]


def _naechste_kennung(eigene: dict) -> str:
    zahlen = [int(e["id"][1:]) for e in eigene["kategorien"] + eigene["punkte"]]
    return f"e{max(zahlen, default=0) + 1}"


def kategorie_hinzufuegen(eigene: dict, name: str) -> dict:
    """Neue eigene Kategorie; ValueError bei leerem Namen oder wenn die Grenze erreicht ist."""
    name = _bereinigt(name, MAX_NAME)
    if not name:
        raise ValueError("Der Name der Kategorie fehlt.")
    if len(eigene["kategorien"]) >= MAX_KATEGORIEN:
        raise ValueError(f"Es sind höchstens {MAX_KATEGORIEN} eigene Kategorien möglich.")
    neu = {"kategorien": list(eigene["kategorien"]), "punkte": list(eigene["punkte"])}
    neu["kategorien"].append({"id": _naechste_kennung(eigene), "name": name})
    return neu


def punkt_hinzufuegen(eigene: dict, schluessel: str, text: str) -> dict:
    """Neuer eigener Punkt in einer festen oder eigenen Kategorie."""
    text = _bereinigt(text, MAX_TEXT)
    if not text:
        raise ValueError("Der Text des Punkts fehlt.")
    if schluessel not in _FESTE_SCHLUESSEL and schluessel not in {k["id"] for k in eigene["kategorien"]}:
        raise ValueError("Unbekannte Kategorie.")
    if len(eigene["punkte"]) >= MAX_PUNKTE:
        raise ValueError(f"Es sind höchstens {MAX_PUNKTE} eigene Punkte möglich.")
    neu = {"kategorien": list(eigene["kategorien"]), "punkte": list(eigene["punkte"])}
    neu["punkte"].append({"id": _naechste_kennung(eigene), "kategorie": schluessel, "text": text})
    return neu


def punkt_loeschen(eigene: dict, kennung: str) -> dict:
    return {"kategorien": list(eigene["kategorien"]),
            "punkte": [p for p in eigene["punkte"] if p["id"] != kennung]}


def kategorie_loeschen(eigene: dict, kennung: str) -> dict:
    """Löscht eine eigene Kategorie samt ihren Punkten."""
    return {"kategorien": [k for k in eigene["kategorien"] if k["id"] != kennung],
            "punkte": [p for p in eigene["punkte"] if p["kategorie"] != kennung]}


def erledigte(veranstaltung: dict | None) -> set[str]:
    """Erledigte Schritte aus `checkliste` (feste und eigene, soweit sie noch existieren);
    Unlesbares oder Unbekanntes ergibt keinen Fehler."""
    roh = (veranstaltung or {}).get("checkliste")
    if not roh:
        return set()
    try:
        daten = json.loads(roh)
    except (TypeError, ValueError):
        return set()
    if not isinstance(daten, list):
        return set()
    gueltig = set(alle_kennungen(struktur(veranstaltung)))
    return {k for k in daten if isinstance(k, str) and k in gueltig}


def als_text(kennungen: set[str], reihenfolge: list[str] | None = None) -> str | None:
    """Speicherform in der Reihenfolge der Checkliste (`reihenfolge`, Standard: nur die festen
    Schritte); unbekannte Kennungen entfallen. None, wenn nichts erledigt ist."""
    gehakt = [k for k in (reihenfolge or ALLE_KENNUNGEN) if k in kennungen]
    return json.dumps(gehakt) if gehakt else None
