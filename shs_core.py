"""
Kernlogik des SHS-Prüfungsprogramms: Notenberechnung (Wertnote) und Rangbildung.

Die Punkt-zu-Note-Zuordnung wurde aus der Originaldatei "SHS Prüfungsprogramm_V2026.ods",
Tabellenblatt "Hilfstabelle Wertnote", extrahiert. Laut Rückmeldung ändern sich diese
Regeln aktuell nicht, sie sind daher hier als feste Konstanten hinterlegt.

WICHTIG - Mindestpunktzahl je Einzeldisziplin (siehe Tabellenblatt "Prüfungsteilnehmer",
Spalte AF, Originalformel):

    IF(AND(Art="EDB"; Anzeige_Behältnis>69); VLOOKUP(...); "nicht Bestanden")
    IF(AND(Art="EDT"; Anzeige_Trümmerfeld>69); VLOOKUP(...); "nicht Bestanden")
    IF(AND(Art="EDF"; Anzeige_Flächensuche>69); VLOOKUP(...); "nicht Bestanden")
    IF(AND(Art="DK"; Trümmerfeld>69; Flächensuche>69; Behältnis>69); VLOOKUP(...); "nicht Bestanden")

Das heißt: Unabhängig von der Gesamtpunktzahl gilt eine Prüfung nur dann als "bestanden",
wenn JEDE einzelne Disziplin (bei ED die eine, bei DK alle drei) mindestens 70 Punkte
(>69) erreicht. Nur dann wird überhaupt eine Wertnote aus der Tabelle nachgeschlagen -
andernfalls lautet das Ergebnis wörtlich "nicht Bestanden", unabhängig von der Summe.
Die Ranglisten-Formeln (Tabellenblatt "Hilfstabelle Rankingliste") bestätigen das: dort
wird für "nicht Bestanden"-Teilnehmer statt einer Platzierung ("RANK.EQ") das Kürzel
"nB" ausgegeben - sie werden also aus der Platzierung herausgenommen (aber weiterhin bei
"Anzahl Starter" mitgezählt).
"""

from dataclasses import dataclass, field
from enum import Enum

MINDESTPUNKTE_JE_DISZIPLIN = 70  # ">69" in der Originalformel = mindestens 70 Punkte


class Disziplinart(str, Enum):
    EINZELDISZIPLIN = "ED"   # max. 100 Punkte (eine Disziplin)
    DREIKAMPF = "DK"         # max. 300 Punkte (drei Disziplinen)


# Schwellenwerte je Disziplinart: (Mindestpunktzahl, Notentext, Abkürzung).
# Absteigend sortiert - die erste zutreffende Zeile (Punkte >= Mindestpunktzahl) gewinnt.
# Diese Tabellen werden NUR erreicht, nachdem die Mindestpunktzahl-je-Disziplin-Prüfung
# (s.o.) bereits bestanden wurde - die tiefsten Bänder ("ungenügend"/"Mangelhaft") aus
# der Original-Nachschlagetabelle sind daher toter Code (nie erreichbar, siehe Originalformel)
# und wurden hier bewusst weggelassen; ein Nichtbestehen wird stattdessen einheitlich als
# "nicht Bestanden" (Kürzel "nB") über MINDESTPUNKTE_JE_DISZIPLIN abgebildet.
WERTNOTEN_ED: list[tuple[int, str, str]] = [
    (96, "Vorzüglich", "V"),
    (90, "Sehr Gut", "SG"),
    (80, "Gut", "G"),
    (70, "Befriedigend", "B"),
]

WERTNOTEN_DK: list[tuple[int, str, str]] = [
    (286, "Vorzüglich", "V"),
    (270, "Sehr Gut", "SG"),
    (240, "Gut", "G"),
    (210, "Befriedigend", "B"),
]

PUNKTE_MAX = {
    Disziplinart.EINZELDISZIPLIN: 100,
    Disziplinart.DREIKAMPF: 300,
}

NICHT_BESTANDEN_TEXT = "nicht Bestanden"
NICHT_BESTANDEN_ABK = "nB"


@dataclass(frozen=True)
class Wertnote:
    punkte: int
    notentext: str
    abkuerzung: str
    bestanden: bool = True


def _wertnote_aus_tabelle(punkte: int, tabelle: list[tuple[int, str, str]]) -> tuple[str, str]:
    for schwelle, notentext, abkuerzung in tabelle:
        if punkte >= schwelle:
            return notentext, abkuerzung
    raise AssertionError(
        "unerreichbar - wird nur mit bereits bestandener Mindestpunktzahl aufgerufen"
    )


def berechne_wertnote_ed(punkte: int) -> Wertnote:
    """Wertnote für eine Einzeldisziplin (Trümmerfeld, Flächensuche ODER Behältnisstrecke).

    `punkte` ist die Summe aus Such- und Anzeigeleistung der jeweiligen Disziplin (0-100).
    Werden weniger als MINDESTPUNKTE_JE_DISZIPLIN (70) erreicht, ist die Prüfung
    "nicht Bestanden" - unabhängig davon, wie hoch die Punktzahl sonst wäre.
    """
    maximum = PUNKTE_MAX[Disziplinart.EINZELDISZIPLIN]
    if not (0 <= punkte <= maximum):
        raise ValueError(f"Punktzahl {punkte} außerhalb des gültigen Bereichs 0-{maximum}")

    if punkte < MINDESTPUNKTE_JE_DISZIPLIN:
        return Wertnote(punkte=punkte, notentext=NICHT_BESTANDEN_TEXT, abkuerzung=NICHT_BESTANDEN_ABK, bestanden=False)

    notentext, abkuerzung = _wertnote_aus_tabelle(punkte, WERTNOTEN_ED)
    return Wertnote(punkte=punkte, notentext=notentext, abkuerzung=abkuerzung, bestanden=True)


def berechne_wertnote_dk(truemmerfeld: int, flaechensuche: int, behaeltnisstrecke: int) -> Wertnote:
    """Wertnote für den Dreikampf (DK) aus den drei Einzeldisziplin-Punktzahlen (je 0-100).

    Bestehen setzt voraus, dass JEDE der drei Disziplinen für sich mindestens
    MINDESTPUNKTE_JE_DISZIPLIN (70) Punkte erreicht - eine hohe Gesamtpunktzahl allein
    reicht nicht, wenn eine einzelne Disziplin darunter liegt. In diesem Fall lautet das
    Ergebnis "nicht Bestanden", auch wenn die Summe rechnerisch für eine bessere Note
    reichen würde.
    """
    maximum = PUNKTE_MAX[Disziplinart.EINZELDISZIPLIN]
    einzelwerte = {
        "Trümmerfeld": truemmerfeld,
        "Flächensuche": flaechensuche,
        "Behältnisstrecke": behaeltnisstrecke,
    }
    for name, wert in einzelwerte.items():
        if not (0 <= wert <= maximum):
            raise ValueError(f"Punktzahl {wert} für {name} außerhalb des gültigen Bereichs 0-{maximum}")

    gesamtpunkte = truemmerfeld + flaechensuche + behaeltnisstrecke
    bestanden = all(wert >= MINDESTPUNKTE_JE_DISZIPLIN for wert in einzelwerte.values())

    if not bestanden:
        return Wertnote(punkte=gesamtpunkte, notentext=NICHT_BESTANDEN_TEXT, abkuerzung=NICHT_BESTANDEN_ABK, bestanden=False)

    notentext, abkuerzung = _wertnote_aus_tabelle(gesamtpunkte, WERTNOTEN_DK)
    return Wertnote(punkte=gesamtpunkte, notentext=notentext, abkuerzung=abkuerzung, bestanden=True)


@dataclass
class Teilnehmerergebnis:
    """Ein Teilnehmer mit seinem Gesamtergebnis innerhalb einer Leistungsklasse.

    Die Wertnote wird von außen übergeben (bereits fertig berechnet über
    `berechne_wertnote_ed`/`berechne_wertnote_dk`), weil beim DK dafür die drei
    einzelnen Disziplin-Punktzahlen benötigt werden, nicht nur die Summe.
    """
    id: str
    name: str
    leistungsklasse: str
    wertnote: Wertnote
    platzierung: int | None = field(init=False, default=None)
    von_startern: int = field(init=False, default=0)

    @property
    def gesamtpunkte(self) -> int:
        return self.wertnote.punkte

    @property
    def bestanden(self) -> bool:
        return self.wertnote.bestanden


def berechne_rangliste(teilnehmer: list[Teilnehmerergebnis]) -> list[Teilnehmerergebnis]:
    """Berechnet die Platzierung je Leistungsklasse (höhere Punktzahl = besserer Rang).

    Verwendet "Standard Competition Ranking" (wie Excel/Calc RANK.EQ): Teilnehmer
    mit gleicher Punktzahl erhalten denselben Rang, der nächste Rang überspringt
    entsprechend viele Plätze (1, 1, 3, 4, ...).

    Teilnehmer mit Ergebnis "nicht Bestanden" erhalten KEINE Platzierung (platzierung
    bleibt None) - genau wie im Original, wo die Rankingliste für sie statt einer Zahl
    das Kürzel "nB" ausweist. Sie zählen aber weiterhin bei "von X Startern" mit, da das
    Original auch sie in "Anzahl Starter" mitzählt.

    Das Original bildet das über die riesige Kreuztabelle "Hilfstabelle Rankingliste"
    (25.200 Formeln) ab - hier reicht dafür ein einfaches Sortieren pro
    Leistungsklassen-Gruppe.
    """
    ergebnis: list[Teilnehmerergebnis] = []
    leistungsklassen = sorted({t.leistungsklasse for t in teilnehmer})

    for lk in leistungsklassen:
        gruppe = [t for t in teilnehmer if t.leistungsklasse == lk]
        anzahl_starter = len(gruppe)

        bestandene = [t for t in gruppe if t.bestanden]
        nicht_bestandene = [t for t in gruppe if not t.bestanden]
        bestandene.sort(key=lambda t: t.gesamtpunkte, reverse=True)

        rang = 0
        letzte_punkte: int | None = None
        for position, t in enumerate(bestandene, start=1):
            if t.gesamtpunkte != letzte_punkte:
                rang = position
                letzte_punkte = t.gesamtpunkte
            t.platzierung = rang
            t.von_startern = anzahl_starter
            ergebnis.append(t)

        for t in nicht_bestandene:
            t.platzierung = None
            t.von_startern = anzahl_starter
            ergebnis.append(t)

    return ergebnis
