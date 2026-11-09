"""
Abrechnung der Leistungsrichter (Marco, 09.11.2026): Fahrtkosten (Kilometer x Satz) plus
Tagespauschale je Leistungsrichter eines Termins.

Reine Fachlogik ohne Qt und ohne Datenbankzugriff: alles arbeitet auf dem Veranstaltungs-
Datensatz (`db.get_veranstaltung`), gerechnet wird mit `Decimal` (kaufmännisch auf Cent
gerundet). Gespeichert wird in drei Spalten der Tabelle `veranstaltung`:

- `lr_km_satz`: Vergütung je Kilometer (Text, z. B. "0,35"); leer = Standard 0,35 EUR.
- `lr_tagespauschale`: Tagespauschale je Richter (Text, z. B. "50"); leer = Standard 50 EUR.
- `lr_abrechnung`: JSON mit den Eingaben je Richter-Position 1-5, z. B.
  `{"1": {"km": "123,5", "km_satz": "", "pauschale": "25"}}`; leere Felder = Termin-Satz.

Die Eingaben hängen an der Positionsnummer (Wertungsrichter 1-5), nicht am Namen: wird ein
Richter in den Veranstaltungsdaten umbenannt, bleiben die Beträge stehen. Es erscheinen nur
Richter mit eingetragenem Namen.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

KM_SATZ_STANDARD = "0,35"
TAGESPAUSCHALE_STANDARD = "50"
ANZAHL_RICHTER = 5

# Obergrenzen gegen Tippfehler (und damit der Betrag in Worten immer darstellbar bleibt).
MAX_KM = Decimal("10000")
MAX_KM_SATZ = Decimal("10")
MAX_PAUSCHALE = Decimal("10000")

_CENT = Decimal("0.01")
_EINE_STELLE = Decimal("0.1")


def dezimal_lesen(text, maximum: Decimal | None = None, tausenderpunkt: bool = False) -> Decimal | None:
    """Liest eine Zahl in deutscher oder englischer Schreibweise ("1.234,5", "0,35", "12.5").
    None bei leerem, ungültigem, negativem oder zu großem Wert (> maximum). Mit
    `tausenderpunkt` gilt ein Punkt ohne Komma, hinter dem genau drei Ziffern stehen
    ("1.234", "12.345.678"), als Tausendertrenner (Marco 09.11.2026); ein führendes "0" davor
    ("0.355") bleibt eine Dezimalzahl."""
    if text is None:
        return None
    roh = str(text).strip().replace(" ", "").replace(" ", "")
    if not roh:
        return None
    if "," in roh:
        roh = roh.replace(".", "").replace(",", ".")
    elif tausenderpunkt and re.fullmatch(r"[1-9]\d{0,2}(\.\d{3})+", roh):
        roh = roh.replace(".", "")
    # Nur Ziffern mit einem Dezimalpunkt: schließt Exponenten ("1e999999"), Vorzeichen,
    # "NaN" und "Infinity" aus.
    if not re.fullmatch(r"\d+(\.\d*)?|\.\d+", roh):
        return None
    try:
        wert = Decimal(roh)
    except InvalidOperation:
        return None
    if maximum is not None and wert > maximum:
        return None
    return wert


def km_lesen(text) -> Decimal | None:
    """Kilometer, auf eine Nachkommastelle gerundet."""
    wert = dezimal_lesen(text, MAX_KM, tausenderpunkt=True)
    return None if wert is None else wert.quantize(_EINE_STELLE, rounding=ROUND_HALF_UP)


def km_satz_lesen(text) -> Decimal | None:
    return dezimal_lesen(text, MAX_KM_SATZ)


def pauschale_lesen(text) -> Decimal | None:
    wert = dezimal_lesen(text, MAX_PAUSCHALE, tausenderpunkt=True)
    return None if wert is None else wert.quantize(_CENT, rounding=ROUND_HALF_UP)


def zahl_text(wert: Decimal, stellen: int) -> str:
    """Deutsche Schreibweise mit Tausenderpunkt und Dezimalkomma, z. B. 1.234,50."""
    text = f"{wert.quantize(Decimal(1).scaleb(-stellen), rounding=ROUND_HALF_UP):,.{stellen}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def euro_text(wert: Decimal) -> str:
    return f"{zahl_text(wert, 2)} €"


def km_text(wert: Decimal) -> str:
    return zahl_text(wert, 1)


def eingabe_text(wert: Decimal | None, stellen: int) -> str:
    """Wert für ein Eingabefeld: ohne unnötige Nullen (35 statt 35,00), Komma als Trenner."""
    if wert is None:
        return ""
    text = f"{wert.quantize(Decimal(1).scaleb(-stellen), rounding=ROUND_HALF_UP):f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


def km_satz_des_termins(veranstaltung: dict | None) -> Decimal:
    wert = km_satz_lesen((veranstaltung or {}).get("lr_km_satz"))
    return wert if wert is not None else Decimal(KM_SATZ_STANDARD.replace(",", "."))


def pauschale_des_termins(veranstaltung: dict | None) -> Decimal:
    wert = pauschale_lesen((veranstaltung or {}).get("lr_tagespauschale"))
    return wert if wert is not None else Decimal(TAGESPAUSCHALE_STANDARD)


def richter_eingaben_lesen(veranstaltung: dict | None) -> dict[int, dict[str, str]]:
    """Eingaben je Richter-Position 1-5 aus `lr_abrechnung`. Unlesbares (beschädigter Text,
    falsche Typen) ergibt leere Eingaben, nie einen Fehler: Termin-Dateien gelten als fremde
    Eingaben."""
    roh = (veranstaltung or {}).get("lr_abrechnung")
    if not roh:
        return {}
    try:
        daten = json.loads(roh)
    except (TypeError, ValueError):
        return {}
    if not isinstance(daten, dict):
        return {}
    ergebnis: dict[int, dict[str, str]] = {}
    for schluessel, eintrag in daten.items():
        try:
            nummer = int(schluessel)
        except (TypeError, ValueError):
            continue
        if not 1 <= nummer <= ANZAHL_RICHTER or not isinstance(eintrag, dict):
            continue
        ergebnis[nummer] = {
            feld: str(eintrag.get(feld) or "").strip()[:20] for feld in ("km", "km_satz", "pauschale")
        }
    return ergebnis


def richter_eingaben_als_text(eingaben: dict[int, dict[str, str]]) -> str | None:
    """Speicherform (JSON) der Eingaben; Positionen ohne jede Eingabe entfallen, None wenn leer."""
    daten = {}
    for nummer in sorted(eingaben):
        eintrag = {feld: str(wert or "").strip() for feld, wert in eingaben[nummer].items()
                   if feld in ("km", "km_satz", "pauschale")}
        if 1 <= nummer <= ANZAHL_RICHTER and any(eintrag.values()):
            daten[str(nummer)] = eintrag
    return json.dumps(daten, ensure_ascii=False, sort_keys=True) if daten else None


@dataclass(frozen=True)
class Abrechnungszeile:
    nummer: int
    name: str
    km: Decimal
    km_satz: Decimal
    pauschale: Decimal
    fahrtkosten: Decimal
    summe: Decimal


def abrechnungszeile(nummer: int, name: str, km: Decimal, km_satz: Decimal, pauschale: Decimal) -> Abrechnungszeile:
    fahrtkosten = (km * km_satz).quantize(_CENT, rounding=ROUND_HALF_UP)
    return Abrechnungszeile(nummer, name, km, km_satz, pauschale, fahrtkosten, fahrtkosten + pauschale)


def abrechnungszeilen(veranstaltung: dict | None) -> list[Abrechnungszeile]:
    """Eine Zeile je Wertungsrichter mit eingetragenem Namen. Fehlende oder ungültige
    Eingaben gelten als 0 km bzw. als Satz des Termins."""
    termin_satz = km_satz_des_termins(veranstaltung)
    termin_pauschale = pauschale_des_termins(veranstaltung)
    eingaben = richter_eingaben_lesen(veranstaltung)
    zeilen = []
    for nummer in range(1, ANZAHL_RICHTER + 1):
        name = str((veranstaltung or {}).get(f"wertungsrichter_{nummer}") or "").strip()
        if not name:
            continue
        eintrag = eingaben.get(nummer, {})
        km = km_lesen(eintrag.get("km"))
        satz = km_satz_lesen(eintrag.get("km_satz"))
        pauschale = pauschale_lesen(eintrag.get("pauschale"))
        zeilen.append(abrechnungszeile(
            nummer, name,
            km if km is not None else Decimal("0.0"),
            satz if satz is not None else termin_satz,
            pauschale if pauschale is not None else termin_pauschale,
        ))
    return zeilen


def gesamtsumme(zeilen: list[Abrechnungszeile]) -> Decimal:
    return sum((z.summe for z in zeilen), Decimal("0.00"))


_EINER = ["null", "ein", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun", "zehn",
          "elf", "zwölf", "dreizehn", "vierzehn", "fünfzehn", "sechzehn", "siebzehn", "achtzehn",
          "neunzehn"]
_ZEHNER = {2: "zwanzig", 3: "dreißig", 4: "vierzig", 5: "fünfzig", 6: "sechzig", 7: "siebzig",
           8: "achtzig", 9: "neunzig"}


def _unter_hundert(n: int) -> str:
    if n < 20:
        return _EINER[n]
    einer, zehner = n % 10, n // 10
    return _ZEHNER[zehner] if einer == 0 else f"{_EINER[einer]}und{_ZEHNER[zehner]}"


def _unter_tausend(n: int) -> str:
    hunderter, rest = divmod(n, 100)
    teil = f"{_EINER[hunderter]}hundert" if hunderter else ""
    if rest:
        teil += _unter_hundert(rest)
    return teil


def zahl_in_worten(n: int) -> str:
    """Ganze Zahl 0 bis 999.999 in Worten („hundertdreiundzwanzig“ mit „ein-“: „einhundert…“,
    letzte Stelle „eins“: „einhunderteins“)."""
    if not 0 <= n <= 999_999:
        raise ValueError("Zahl außerhalb von 0 bis 999999")
    if n == 0:
        return "null"
    tausender, rest = divmod(n, 1000)
    text = f"{_unter_tausend(tausender)}tausend" if tausender else ""
    if rest:
        text += _unter_tausend(rest)
    if text.endswith("ein"):
        text += "s"
    return text


def betrag_in_worten(betrag: Decimal) -> str:
    """Betrag für die Quittung, z. B. „einhundertzwanzig Euro und fünfzig Cent“,
    „ein Euro“, „null Euro“."""
    betrag = betrag.quantize(_CENT, rounding=ROUND_HALF_UP)
    euro, cent = divmod(int(betrag * 100), 100)
    euro_text_ = zahl_in_worten(euro)
    if euro_text_.endswith("eins"):
        euro_text_ = euro_text_[:-1]
    text = f"{euro_text_} Euro"
    if cent:
        cent_text = zahl_in_worten(cent)
        if cent_text.endswith("eins"):
            cent_text = cent_text[:-1]
        text += f" und {cent_text} Cent"
    return text
