"""Erfundene Daten für die geführte Demoprüfung (siehe desktop_demo.py).

Bewusst ohne Qt, damit test_db.py die Daten auch ohne PySide6 gegen die Datenschicht
prüfen kann (TestDemoDaten). Alle Namen, Vereine und Chipnummern sind frei erfunden;
Chipnummern beginnen wie in docs/beispiel_teilnehmer.csv mit 999.

Die Ergebnisse sind so gewählt, dass die Demo jede Wertnote zeigt, die am Prüfungstag
typischerweise vorkommt: zweimal punktgleich "Vorzüglich" (Stechen), "Sehr Gut", "Gut",
"nicht Bestanden", eine Disqualifikation und zwei Dreikampf-Teams.
"""

from __future__ import annotations

import datetime

#: Veranstaltungsdaten in der Form von VeranstaltungsDialog.veranstaltung_werte() bzw.
#: db.set_veranstaltung() - nur das Datum wird erst beim Start der Demo eingesetzt (heute).
VERANSTALTUNG: dict = {
    "verein": "DEMO Hundefreunde Musterstadt",
    "ort": "Musterstadt",
    "vereins_nr": "0000",
    "pruefungsnummer": "DEMO-1",
    "pruefungsleiter": "Paula Muster",
    "wertungsrichter_1": "Erika Beispiel",
    "wertungsrichter_2": "Hans Probe",
    "verband": "Beispielverband (Demo)",
    "meldestelle": "Paula Muster\nMusterweg 1\n12345 Musterstadt\nmeldestelle@example.org",
}

#: Angebotene Prüfungen (Kürzel wie db.ALLE_PRUEFUNGEN) mit Startnummern-Bereich.
PRUEFUNGEN: dict[str, tuple[int, int]] = {
    "DK1": (61, 79),
    "ED1-Trümmerfeld": (1, 19),
    "ED2-Behältnisstrecke": (41, 59),
    "ED1-Flächensuche": (21, 39),
}

#: Teilnehmer in Meldereihenfolge. "daten" sind die Felder von db.NeuerTeilnehmer,
#: "ergebnis" die Punkte je Disziplin als (Suche, Anzeige), "status" ggf. "dq".
TEILNEHMER: list[dict] = [
    {
        "daten": dict(nachname="Albers", vorname="Anna", rufname_hund="Aika", art="ED", stufe=1,
                      disziplin="Trümmerfeld", gegenstand_1_disziplin="Trümmerfeld", verein="SV Musterstadt", chip_nr="999000000000101",
                      gegenstand_1="Socke"),
        "ergebnis": {"Trümmerfeld": (58, 38)},  # 96 - V, punktgleich mit Brandt
    },
    {
        "daten": dict(nachname="Brandt", vorname="Ben", rufname_hund="Bruno", art="ED", stufe=1,
                      disziplin="Trümmerfeld", gegenstand_1_disziplin="Trümmerfeld", verein="Hundesport Beispielhausen",
                      chip_nr="999000000000102", gegenstand_1="Schlüsselbund"),
        "ergebnis": {"Trümmerfeld": (57, 39)},  # 96 - V
    },
    {
        "daten": dict(nachname="Claasen", vorname="Clara", rufname_hund="Cleo", art="ED", stufe=1,
                      disziplin="Trümmerfeld", gegenstand_1_disziplin="Trümmerfeld", verein="SV Musterstadt", chip_nr="999000000000103",
                      gegenstand_1="Handschuh"),
        "ergebnis": {"Trümmerfeld": (50, 32)},  # 82 - G
    },
    {
        "daten": dict(nachname="Dietrich", vorname="Daniel", rufname_hund="Dox", art="ED", stufe=1,
                      disziplin="Flächensuche", gegenstand_1_disziplin="Flächensuche", verein="Hundefreunde Probedorf",
                      chip_nr="999000000000104", gegenstand_1="Geldbörse"),
        "ergebnis": {"Flächensuche": (55, 36)},  # 91 - SG
    },
    {
        "daten": dict(nachname="Ehlers", vorname="Emma", rufname_hund="Enzo", art="ED", stufe=1,
                      disziplin="Flächensuche", gegenstand_1_disziplin="Flächensuche", verein="Hundesport Beispielhausen",
                      chip_nr="999000000000105", gegenstand_1="Mütze"),
        "ergebnis": {"Flächensuche": (40, 25)},  # 65 - nicht Bestanden
    },
    {
        "daten": dict(nachname="Fischer", vorname="Felix", rufname_hund="Frieda", art="ED", stufe=2,
                      disziplin="Behältnisstrecke", gegenstand_1_disziplin="Behältnisstrecke", verein="Hundefreunde Probedorf",
                      chip_nr="999000000000106", gegenstand_1="Taschentuch"),
        "status": "dq",
    },
    {
        "daten": dict(nachname="Gerdes", vorname="Greta", rufname_hund="Gino", art="DK", stufe=1,
                      verein="SV Musterstadt", chip_nr="999000000000107", gegenstand_1="Brille"),
        # 86 + 92 + 92 = 270 - SG
        "ergebnis": {"Trümmerfeld": (52, 34), "Flächensuche": (55, 37), "Behältnisstrecke": (56, 36)},
    },
    {
        # Ohne Chip-Nr. - zeigt die Warnung "⚠ Chip-Nr. fehlt" in der Teilnehmerliste.
        "daten": dict(nachname="Hansen", vorname="Hugo", rufname_hund="Hexe", art="DK", stufe=1,
                      verein="Hundesport Beispielhausen", gegenstand_1="Kugelschreiber"),
        # 80 + 78 + 82 = 240 - G
        "ergebnis": {"Trümmerfeld": (48, 32), "Flächensuche": (47, 31), "Behältnisstrecke": (50, 32)},
    },
]

#: Nachname des Teilnehmers, der in der Demo noch nicht bezahlt hat.
NICHT_BEZAHLT = "Hansen"

#: Nachname des Siegers im Stechen (Albers und Brandt sind punktgleich auf Platz 1).
STECHEN_SIEGER = "Albers"


def veranstaltung(datum: datetime.date | None = None) -> dict:
    """Vollständige Argumente für db.set_veranstaltung() (Datum: heute, sofern nicht
    angegeben) - für Tests und als Vorlage der im Dialog eingetragenen Werte."""
    from db import pruefungen_als_text, startnummer_bereiche_als_text

    return {
        **VERANSTALTUNG,
        "datum": (datum or datetime.date.today()).isoformat(),
        "angebotene_pruefungen": pruefungen_als_text(list(PRUEFUNGEN)),
        "startnummer_bereiche": startnummer_bereiche_als_text(PRUEFUNGEN),
    }
