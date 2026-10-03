"""Erzeugt Termin-Dateien und Sicherungen ÄLTERER Programmversionen für die Upgrade-Tests
(test_altversionen.py, T3 - mit Marco abgestimmt am 03.10.2026).

Für jede Version wird der Code des Git-Tags (git archive) in einen temporären Ordner
entpackt und dort ein festes Füllskript mit GENAU diesem alten Code ausgeführt. So entstehen
Dateien, wie die alte Version sie wirklich geschrieben hat (Spaltenreihenfolge,
Standardwerte, Sicherungsformat) - nicht von Hand nachgebaut. Nur erfundene Testdaten.

Ergebnis je Version in testdaten/altversionen/<tag>/:
  termin.sqlite            Termin mit Teilnehmern, Ergebnissen, Zeitplan
  sicherung.zip            Sicherung ohne Passwort
  sicherung_passwort.zip   Sicherung mit Passwort (siehe PASSWORT)
  info.json                Version und was sie konnte (Disqualifikation, Keine Teilnahme, ...)

Aufruf:
    python tools/altdaten_erzeugen.py               # Standardauswahl (STANDARD_TAGS)
    python tools/altdaten_erzeugen.py v1.0.41       # einzelne, bereits getaggte Version
    python tools/altdaten_erzeugen.py --aktuell     # beim Build: committeter Stand (HEAD),
                                                    # benannt nach version.txt (Tag gibt es noch nicht)

Standardauswahl = 1.0.0 und jede Version direkt vor einer Änderung des Datenmodells, dazu die
jeweils neueste (Stand 03.10.2026 ermittelt über die Tabellenstruktur je Tag).
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ZIEL = REPO / "testdaten" / "altversionen"
PASSWORT = "Altdaten-Test-1"
STANDARD_TAGS = ["v1.0.0", "v1.0.13", "v1.0.18", "v1.0.20", "v1.0.37", "v1.0.38", "v1.0.39", "v1.0.40"]

# Läuft im entpackten Code der jeweiligen Version (cwd = dieser Ordner). Prüft vorhandene
# Funktionen/Felder über hasattr bzw. die Dataclass-Felder, damit es mit allen Versionen läuft.
FUELLSKRIPT = r'''
import dataclasses, inspect, json, sys
from pathlib import Path
sys.path.insert(0, ".")
import db

ausgabe = Path(sys.argv[1]); passwort = sys.argv[2]
ausgabe.mkdir(parents=True, exist_ok=True)
termin = ausgabe / "termin.sqlite"
if termin.exists():
    termin.unlink()
conn = db.init_db(str(termin))

def nur_bekannte(funktion, werte):
    erlaubt = inspect.signature(funktion).parameters
    return {k: v for k, v in werte.items() if k in erlaubt}

db.set_veranstaltung(conn, **nur_bekannte(db.set_veranstaltung, dict(
    verein="Altdaten-Testverein", datum="2026-11-14", ort="Teststadt", vereins_nr="4711",
    pruefungsnummer="ALT-1", wertungsrichter_1="Richterin A", wertungsrichter_2="Richter B",
    wertungsrichter_3="Richter C", pruefungsleiter="Paula Prüf", pruefungsgebuehr_ed=25.0,
    pruefungsgebuehr_dk=40.0, zeitplan_start="08:30", verband="TESTV",
    meldestelle="Paula Prüf\nTestweg 1", angebotene_pruefungen="ED1-Trümmerfeld,DK2",
)))

felder = {f.name for f in dataclasses.fields(db.NeuerTeilnehmer)}
def teilnehmer(**werte):
    return db.add_teilnehmer(conn, db.NeuerTeilnehmer(**{k: v for k, v in werte.items() if k in felder}))

basis = dict(verein="Altdaten-Testverein", geschlecht="Hündin", chip_nr="276000000000001",
             strasse="Testweg", hausnummer="1", plz="12345", ort="Teststadt", email="a@example.org",
             rasse="Mischling", geburtsdatum="1980-05-01", halter_nachname="Halterin",
             gegenstand_1="Leder")
ids = {}
ids["Anna"] = teilnehmer(nachname="Anna", vorname="Test", rufname_hund="Aika", art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=1, bezahlt=True, **basis)
ids["Ben"] = teilnehmer(nachname="Ben", vorname="Test", rufname_hund="Bruno", art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=2)
ids["Clara"] = teilnehmer(nachname="Clara", vorname="Test", rufname_hund="Cleo", art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=3)
ids["Dieter"] = teilnehmer(nachname="Dieter", vorname="Test", rufname_hund="Dox", art="DK", stufe=2, startnummer=4,
                          gegenstand_1="Leder", gegenstand_1_disziplin="Trümmerfeld",
                          gegenstand_2="Metall", gegenstand_2_disziplin="Flächensuche")
ids["Emil"] = teilnehmer(nachname="Emil", vorname="Test", rufname_hund="Enzo", art="DK", stufe=2, startnummer=5)
ids["Frieda"] = teilnehmer(nachname="Frieda", vorname="Test", rufname_hund="Fee", art="ED", stufe=2, disziplin="Flächensuche", startnummer=6)
ids["Gerd"] = teilnehmer(nachname="Gerd", vorname="Test", rufname_hund="Gino", art="ED", stufe=3, disziplin="Behältnisstrecke", startnummer=7)

db.eintragen_ergebnis(conn, ids["Anna"], "Trümmerfeld", 58, 38)       # 96 V
db.eintragen_ergebnis(conn, ids["Ben"], "Trümmerfeld", 50, 30)        # 80 G
db.eintragen_ergebnis(conn, ids["Clara"], "Trümmerfeld", 60, 9)       # 69 nB
for disziplin in ("Trümmerfeld", "Flächensuche", "Behältnisstrecke"):
    db.eintragen_ergebnis(conn, ids["Dieter"], disziplin, 55, 35)     # 270 SG
db.eintragen_ergebnis(conn, ids["Emil"], "Trümmerfeld", 50, 30)       # DK unvollständig
db.eintragen_ergebnis(conn, ids["Gerd"], "Behältnisstrecke", 60, 40)  # 100

kann = {
    "disqualifikation": hasattr(db, "setze_ergebnis_status"),
    "keine_teilnahme": hasattr(db, "setze_keine_teilnahme"),
    "richter_3": "wertungsrichter_3" in inspect.signature(db.set_veranstaltung).parameters,
    "kontaktfelder": "strasse" in felder,
    "halter": "halter_nachname" in felder,
    "geburtsdatum": "geburtsdatum" in felder,
    "anmeldeformular": "angebotene_pruefungen" in inspect.signature(db.set_veranstaltung).parameters,
}
if kann["disqualifikation"]:
    db.setze_ergebnis_status(conn, ids["Frieda"], disqualifiziert=True, abbruch=False)
if kann["keine_teilnahme"]:
    db.setze_keine_teilnahme(conn, ids["Gerd"], True)

r1 = db.add_zeitplan_richter(conn, "Richterin A")
r2 = db.add_zeitplan_richter(conn, "Richter B")
db.automatische_zeitplan_verteilung(conn, [r1, r2], 10)
db.add_zeitplan_pause(conn, r1, 30, "Mittagspause")
conn.commit()
conn.close()

try:
    from db_sicherung import sicherung_erstellen
except ImportError:
    from db import sicherung_erstellen
sicherung_erstellen(str(ausgabe / "sicherung.zip"), ordner=ausgabe)
sicherung_erstellen(str(ausgabe / "sicherung_passwort.zip"), passwort=passwort, ordner=ausgabe)
(ausgabe / "info.json").write_text(json.dumps({"kann": kann}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
'''


def erzeugen(tag: str, quelle: str | None = None) -> None:
    """`quelle` = Git-Stand, aus dem der Code kommt (Standard: der Tag selbst)."""
    ziel = ZIEL / tag
    with tempfile.TemporaryDirectory() as ordner:
        archiv = subprocess.run(["git", "archive", quelle or tag], cwd=REPO, capture_output=True, check=True)
        subprocess.run(["tar", "-x", "-C", ordner], input=archiv.stdout, check=True)
        lauf = subprocess.run(
            [sys.executable, "-c", FUELLSKRIPT, str(ziel), PASSWORT], cwd=ordner, capture_output=True, text=True
        )
    if lauf.returncode != 0:
        raise SystemExit(f"{tag}: Erzeugung fehlgeschlagen\n{lauf.stderr}")
    info = json.loads((ziel / "info.json").read_text(encoding="utf-8"))
    info = {"version": tag.lstrip("v"), **info}
    (ziel / "info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{tag}: erzeugt in {ziel.relative_to(REPO)}")


if __name__ == "__main__":
    if sys.argv[1:] == ["--aktuell"]:
        version = subprocess.run(
            ["git", "show", "HEAD:version.txt"], cwd=REPO, capture_output=True, text=True, check=True
        ).stdout.strip()
        erzeugen(f"v{version}", quelle="HEAD")
    else:
        for tag in sys.argv[1:] or STANDARD_TAGS:
            erzeugen(tag)
