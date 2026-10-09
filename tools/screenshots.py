"""Erzeugt die Desktop-Screenshots für Handbuch, README und Website neu (docs/bilder).

    python tools/screenshots.py                     # alle Bilder nach docs/bilder
    python tools/screenshots.py --nur handbuch_teilnehmer,handbuch_zeitplan
    python tools/screenshots.py --ziel C:\\temp\\bilder

Marcos Wunsch (09.10.2026): bisher entstand bei jedem Build ein neues Ad-hoc-Skript, die
Bilder waren dadurch uneinheitlich (Version, Testdaten, Pfade). Dieses Skript legt alles
fest:
- offscreen, Schrift Segoe UI, Standard-Design (die gespeicherte Auswahl des Rechners wird
  nur übergangen, nicht verändert), deutsche Qt-Texte, aktuelle Version aus version.py;
- feste, erfundene Testdaten (Testuser1-9, für das Teilnehmer-Bild zusätzlich 10-12 ohne
  Startnummer), alle Termine nur in einem temporären Ordner;
- angezeigter Termine-Ordner immer C:\\Users\\Name\\SHS-Pruefungsprogramm\\Termine.

Nicht enthalten (Handarbeit, selten geändert): Web-Bilder, handbuch_anmeldeformular
(per LibreOffice aus dem PDF), bewertungsbogen, handbuch_edge_download.
Nach dem Lauf jedes geänderte Bild ansehen. Nur ein Entwickler-Werkzeug - gehört nicht zum
Programm und wird nicht mit ausgeliefert.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_FONTS = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
if _FONTS.is_dir():
    os.environ.setdefault("QT_QPA_FONTDIR", str(_FONTS))

from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QScrollArea, QWidget  # noqa: E402

import db  # noqa: E402

#: Angezeigter Termine-Ordner (nie der echte Profilpfad).
ANZEIGE_ORDNER = Path(r"C:\Users\Name\SHS-Pruefungsprogramm\Termine")

#: Größe des Hauptfensters für die Handbuch-Bilder (og:image der Website nutzt
#: handbuch_zeitplan.png, siehe Fortschritt.md 06.10.2026 - Größe beibehalten).
HAUPTFENSTER = (1400, 820)

VERANSTALTUNG = dict(
    verein="Musterverein", datum="2026-11-14", ort="Musterstadt", verband="HSVRM",
    wertungsrichter_1="Richterin A", wertungsrichter_2="Richter B",
    angebotene_pruefungen="DK1,DK2,DK3,ED1-Trümmerfeld,ED2-Flächensuche,ED3-Behältnisstrecke",
    startnummer_bereiche="DK1=1-10,DK2=11-20,DK3=21-30,ED1-Trümmerfeld=31-40,"
                         "ED2-Flächensuche=41-50,ED3-Behältnisstrecke=51-60",
    startnummer_bereichsgroesse="10",
)

_DK_GEGENSTAENDE = dict(
    gegenstand_1="Leder", gegenstand_1_disziplin="Trümmerfeld",
    gegenstand_2="Metall", gegenstand_2_disziplin="Flächensuche",
    gegenstand_3="Holz", gegenstand_3_disziplin="Behältnisstrecke",
)


def _t(nachname, vorname, hund, art, stufe, disziplin, verein, startnummer, bezahlt,
       chip=True, geschlecht=None):
    daten = dict(
        nachname=nachname, vorname=vorname, rufname_hund=hund, art=art, stufe=stufe,
        disziplin=disziplin, verein=verein, startnummer=startnummer, bezahlt=bezahlt,
        # 15-stellige Chip-Nr. aus der Startnummer (ohne Startnummer: 80 + laufende Nummer).
        chip_nr=(f"2760999000000{startnummer or 80 + int(nachname.removeprefix('Testuser')):02d}"
                 if chip else None),
        geschlecht=geschlecht,
    )
    if art == "DK":
        daten.update(_DK_GEGENSTAENDE)
    else:
        daten.update(gegenstand_1="Leder", gegenstand_1_disziplin=disziplin)
    return daten


#: Grunddatensatz aller Bilder (Testuser9 = "keine Teilnahme", Testuser8 ohne Chip-Nr.).
TEILNEHMER = [
    _t("Testuser1", "Anna", "Bello", "DK", 1, None, "Musterverein", 1, True),
    _t("Testuser2", "Ben", "Luna", "DK", 1, None, "Beispielverein", 2, True),
    _t("Testuser3", "Clara", "Rocky", "DK", 2, None, "Musterverein", 11, False),
    _t("Testuser4", "David", "Emma", "DK", 3, None, "Beispielverein", 21, True),
    _t("Testuser5", "Eva", "Max", "ED", 1, "Trümmerfeld", "Musterverein", 31, True, geschlecht="Hündin"),
    _t("Testuser6", "Felix", "Nala", "ED", 1, "Trümmerfeld", "Musterverein", 32, True),
    _t("Testuser7", "Greta", "Balu", "ED", 2, "Flächensuche", "Beispielverein", 41, False),
    _t("Testuser8", "Hannes", "Kira", "ED", 3, "Behältnisstrecke", "Musterverein", 51, True, chip=False),
    _t("Testuser9", "Ina", "Paul", "ED", 1, "Trümmerfeld", "Beispielverein", 33, True),
]
KEINE_TEILNAHME = {"Testuser9"}

#: Nur für das Teilnehmer-Bild: noch ohne Startnummer (Hinweis "Ohne Startnummer").
OHNE_STARTNUMMER = [
    _t("Testuser10", "Jana", "Simba", "DK", 2, None, "Beispielverein", None, False),
    _t("Testuser11", "Kai", "Lotte", "ED", 1, "Trümmerfeld", "Musterverein", None, True),
    _t("Testuser12", "Lena", "Ronja", "ED", 1, "Trümmerfeld", "Beispielverein", None, False),
]

#: Ergebnisse (Suche, Anzeige) je Disziplin. EINGETIPPT werden sie in der
#: Ergebniserfassung sichtbar eingegeben und gespeichert ("4 Ergebnis(se) gespeichert."),
#: die übrigen stehen schon vorher in der Datenbank.
#: Der Zähler zählt Disziplinen: 3 + 1 = 4.
ERGEBNISSE_EINGETIPPT = {
    "Testuser2": {"Trümmerfeld": (50, 30), "Flächensuche": (45, 35), "Behältnisstrecke": (48, 30)},
    "Testuser5": {"Trümmerfeld": (58, 39)},
}
ERGEBNISSE_VORHANDEN = {
    "Testuser1": {"Trümmerfeld": (55, 36), "Flächensuche": (52, 34), "Behältnisstrecke": (58, 38)},
    "Testuser4": {"Trümmerfeld": (56, 37)},
    "Testuser6": {"Trümmerfeld": (40, 25)},
}
DISQUALIFIZIERT = {"Testuser8"}
#: In der Ergebniserfassung eingetippt, aber (noch) nicht gespeichert -> gelbe Zeile.
ERGEBNISSE_UNGESPEICHERT = {
    "Testuser3": {"Trümmerfeld": (50, 32), "Flächensuche": (47, 30)},
}


# --- Umgebung -------------------------------------------------------------------------


def _umgebung_einrichten() -> QApplication:
    """QApplication mit fester Darstellung; leitet Termine-Ordner und Meldungen um."""
    import app as app_modul
    import desktop_darstellung
    import desktop_demo
    import desktop_dialoge
    import desktop_gemeinsam
    from desktop_gemeinsam import deutsche_qt_texte_laden, meldungsfenster_als_klartext

    for modul in (app_modul, desktop_darstellung):
        if hasattr(modul, "_gespeichertes_theme_lesen"):
            modul._gespeichertes_theme_lesen = lambda: desktop_darstellung._THEME_DEFAULT
        if hasattr(modul, "_gespeichertes_design_lesen"):
            modul._gespeichertes_design_lesen = lambda: desktop_darstellung._DESIGN_DEFAULT
    for modul in (app_modul, desktop_dialoge, desktop_demo):
        modul.termine_ordner = lambda: ANZEIGE_ORDNER
    stumm = lambda *args, **kwargs: None  # noqa: E731
    desktop_gemeinsam._datei_gespeichert_melden = stumm
    app_modul._datei_gespeichert_melden = stumm
    app_modul._startnummern_nach_import_anbieten = stumm

    app = QApplication.instance() or QApplication([])
    if _FONTS.is_dir():
        from PySide6.QtGui import QFontDatabase

        for datei in _FONTS.glob("segoe*.ttf"):
            QFontDatabase.addApplicationFont(str(datei))
        for datei in _FONTS.glob("segui*.ttf"):
            QFontDatabase.addApplicationFont(str(datei))
    app.setFont(QFont("Segoe UI", 9))
    meldungsfenster_als_klartext()
    deutsche_qt_texte_laden(app)
    desktop_darstellung._darstellung_anwenden(app)
    return app


def _warten(ms: int = 150) -> None:
    QTest.qWait(ms)


def _speichern(widget: QWidget, ziel: Path, name: str, groesse: tuple[int, int] | None = None) -> Path:
    _warten()
    bild = widget.grab()
    if groesse is not None and (bild.width(), bild.height()) != groesse:
        bild = bild.copy(0, 0, *groesse)
    pfad = ziel / f"{name}.png"
    bild.save(str(pfad))
    return pfad


class _Termine:
    """Legt Termin-Dateien in einem temporären Ordner an."""

    def __init__(self, ordner: Path):
        self.ordner = ordner
        self._nr = 0

    def neu(self, mit_ohne_startnummer: bool = False, ergebnisse: str = "keine",
            datum: str = "2026-11-14"):
        """ergebnisse: "keine" | "vorhanden" (nur ERGEBNISSE_VORHANDEN + DQ) | "alle"."""
        self._nr += 1
        pfad = self.ordner / f"{datum}_Musterverein_{self._nr}.sqlite"
        conn = db.init_db(str(pfad))
        db.set_veranstaltung(conn, **{**VERANSTALTUNG, "datum": datum})
        ids = {}
        for daten in TEILNEHMER + (OHNE_STARTNUMMER if mit_ohne_startnummer else []):
            ids[daten["nachname"]] = db.add_teilnehmer(conn, db.NeuerTeilnehmer(**daten))
        for name in KEINE_TEILNAHME:
            db.setze_keine_teilnahme(conn, ids[name], True)
        if ergebnisse in ("vorhanden", "alle"):
            quellen = [ERGEBNISSE_VORHANDEN] + ([ERGEBNISSE_EINGETIPPT] if ergebnisse == "alle" else [])
            for quelle in quellen:
                for name, werte in quelle.items():
                    for disziplin, (suche, anzeige) in werte.items():
                        db.eintragen_ergebnis(conn, ids[name], disziplin, suche, anzeige)
            for name in DISQUALIFIZIERT:
                db.setze_ergebnis_status(conn, ids[name], True, False)
        return conn, str(pfad), ids


def _hauptfenster(conn, pfad, groesse=HAUPTFENSTER):
    import app as app_modul

    fenster = app_modul.HauptFenster(conn, pfad)
    fenster.resize(*groesse)
    fenster.show()
    _warten()
    return fenster


def _reiter(fenster, name: str) -> None:
    """Wählt einen Reiter über sein Attribut am Hauptfenster (z. B. "zeitplan_tab")."""
    fenster._tabs.setCurrentWidget(getattr(fenster, name))
    _warten(250)


def _schliessen(fenster, conn) -> None:
    fenster.hide()
    fenster.deleteLater()
    conn.close()
    _warten(50)


# --- Bilder ---------------------------------------------------------------------------


def _bild_start(termine: _Termine, ziel: Path) -> list[Path]:
    import app as app_modul

    conn, _pfad, _ids = termine.neu()
    conn.close()
    alt, _alt_pfad, alt_ids = termine.neu(datum="2026-04-18")
    for name in ("Testuser5", "Testuser6", "Testuser7", "Testuser8", "Testuser9"):
        db.delete_teilnehmer(alt, alt_ids[name])
    alt.close()
    app_modul.liste_termine = lambda: db.liste_termine(termine.ordner)
    dialog = app_modul.StartDialog()
    dialog.resize(900, 520)
    dialog.show()
    pfad = _speichern(dialog, ziel, "handbuch_start", (900, 520))
    dialog.close()
    for datei in termine.ordner.glob("*.sqlite"):
        datei.unlink()
    return [pfad]


def _bild_termin_anlegen(_termine: _Termine, ziel: Path) -> list[Path]:
    from desktop_dialoge import VeranstaltungsDialog

    dialog = VeranstaltungsDialog(vorbelegung={
        "verein": "Musterverein", "ort": "Musterstadt", "verband": "HSVRM",
        "angebotene_pruefungen": "DK1,DK2,ED1-Trümmerfeld",
        "startnummer_bereiche": "DK1=1-20,DK2=21-40,ED1-Trümmerfeld=41-60",
        "startnummer_bereichsgroesse": "20",
    })
    dialog.datum.setText("14.11.2026")
    dialog.pfad_feld.setCursorPosition(0)
    dialog.resize(640, 900)
    dialog.show()
    _warten()
    scroll = dialog.findChild(QScrollArea)
    if scroll is None:
        raise RuntimeError("Veranstaltungsdialog: Scrollbereich nicht gefunden")
    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    pfad = _speichern(dialog, ziel, "handbuch_termin_anlegen", (640, 900))
    dialog.close()
    return [pfad]


def _bild_teilnehmer(termine: _Termine, ziel: Path) -> list[Path]:
    conn, pfad, _ids = termine.neu(mit_ohne_startnummer=True)
    fenster = _hauptfenster(conn, pfad)
    _reiter(fenster, "teilnehmer_tab")
    ergebnis = _speichern(fenster, ziel, "handbuch_teilnehmer", HAUPTFENSTER)
    _schliessen(fenster, conn)
    return [ergebnis]


def _bild_teilnehmer_dialoge(termine: _Termine, ziel: Path) -> list[Path]:
    from desktop_dialoge import TeilnehmerDialog

    conn, _pfad, ids = termine.neu()
    pfade = []
    for name, datei in (("Testuser5", "handbuch_teilnehmer_dialog_ed"),
                        ("Testuser4", "handbuch_teilnehmer_dialog_dk")):
        dialog = TeilnehmerDialog(
            vorhandener=db.get_teilnehmer(conn, ids[name]),
            vergebene_nummern=db.vergebene_startnummern(conn, ausser_teilnehmer_id=ids[name]),
            bereiche=db.startnummer_bereiche(db.get_veranstaltung(conn)),
        )
        dialog.resize(1000, 760)
        dialog.show()
        pfade.append(_speichern(dialog, ziel, datei, (1000, 760)))
        dialog.close()
    conn.close()
    return pfade


def _bild_einfacher_reiter(reiter: str, name: str):
    def bild(termine: _Termine, ziel: Path) -> list[Path]:
        conn, pfad, _ids = termine.neu()
        fenster = _hauptfenster(conn, pfad)
        _reiter(fenster, reiter)
        ergebnis = _speichern(fenster, ziel, name, HAUPTFENSTER)
        _schliessen(fenster, conn)
        return [ergebnis]
    return bild


def _bild_zeitplan(termine: _Termine, ziel: Path) -> list[Path]:
    conn, pfad, _ids = termine.neu()
    richter = [db.add_zeitplan_richter(conn, "Richterin A"), db.add_zeitplan_richter(conn, "Richter B")]
    db.automatische_zeitplan_verteilung(conn, richter, standard_dauer_minuten=10)
    db.add_zeitplan_pause_bei_allen(conn, "10:00", 30, "Mittagspause")
    pfade = []
    for groesse, name in ((HAUPTFENSTER, "handbuch_zeitplan"), ((1880, 835), "zeitplan")):
        fenster = _hauptfenster(conn, pfad, groesse)
        _reiter(fenster, "zeitplan_tab")
        pfade.append(_speichern(fenster, ziel, name, groesse))
        fenster.hide()
        fenster.deleteLater()
        _warten(50)
    conn.close()
    return pfade


def _ergebnisse_eintippen(fenster, ids, werte_je_name) -> None:
    tab = fenster.ergebnis_tab
    for name, werte in werte_je_name.items():
        felder = tab.eingabefelder(ids[name])
        for disziplin, (suche, anzeige) in werte.items():
            suche_feld, anzeige_feld = felder[1][disziplin]
            suche_feld.setText(str(suche))
            anzeige_feld.setText(str(anzeige))
    _warten()


def _bild_ergebniserfassung(termine: _Termine, ziel: Path) -> list[Path]:
    conn, pfad, ids = termine.neu(ergebnisse="vorhanden")
    fenster = _hauptfenster(conn, pfad)
    _reiter(fenster, "ergebnis_tab")
    tab = fenster.ergebnis_tab
    _ergebnisse_eintippen(fenster, ids, ERGEBNISSE_EINGETIPPT)
    tab.alle_speichern()  # Statuszeile "4 Ergebnis(se) gespeichert."
    _ergebnisse_eintippen(fenster, ids, ERGEBNISSE_UNGESPEICHERT)
    tab._spaltenbreiten_anpassen()  # wie nach einer Größenänderung
    pfade = [_speichern(fenster, ziel, "handbuch_ergebniserfassung", HAUPTFENSTER)]
    # README/Website: dasselbe Fenster in die Breite gezogen.
    fenster.resize(1917, 651)
    _warten(250)
    tab._spaltenbreiten_anpassen()
    pfade.append(_speichern(fenster, ziel, "ergebniserfassung", (1917, 651)))
    # Ungespeichertes verwerfen, damit beim Schließen keine Rückfrage kommt.
    tab.aktualisieren()
    _schliessen(fenster, conn)
    return pfade


def _bild_auswertung(termine: _Termine, ziel: Path) -> list[Path]:
    conn, pfad, _ids = termine.neu(ergebnisse="alle")
    fenster = _hauptfenster(conn, pfad)
    _reiter(fenster, "auswertung_tab")
    ergebnis = _speichern(fenster, ziel, "handbuch_auswertung", HAUPTFENSTER)
    _schliessen(fenster, conn)
    return [ergebnis]


def _bild_uebersicht(termine: _Termine, ziel: Path) -> list[Path]:
    conn, pfad, _ids = termine.neu(ergebnisse="alle")
    fenster = _hauptfenster(conn, pfad)
    _reiter(fenster, "teilnehmer_uebersicht_tab")
    ergebnis = _speichern(fenster, ziel, "handbuch_uebersicht", HAUPTFENSTER)
    _schliessen(fenster, conn)
    return [ergebnis]


def _bild_demo(termine: _Termine, ziel: Path) -> list[Path]:
    import desktop_demo

    alt_tempdir = tempfile.tempdir
    tempfile.tempdir = str(termine.ordner)
    tempo = desktop_demo.DemoTour.TEMPO
    desktop_demo.DemoTour.TEMPO = 0
    conn, pfad, _ids = termine.neu()
    fenster = _hauptfenster(conn, pfad)
    tour = desktop_demo.DemoTour(fenster=fenster)
    try:
        tour.starten()
        for _ in range(30):
            _warten(100)
            titel = tour._schritte[tour._index].titel
            if titel.startswith("8."):
                break
            tour.weiter()
        else:
            raise RuntimeError("Demo: Schritt „8.“ (Ergebnisse eintragen) nicht gefunden")
        _warten(800)
        # Countdown auf "Weiter ▶ (10)" einfrieren.
        tour._countdown.stop()
        tour._panel.countdown_anzeigen(desktop_demo.DemoTour.AUTO_WEITER_S)
        _warten()
        bild = fenster.grab()
        panel = tour._panel.grab()
        # Das Erklärfenster ist ein eigenes Fenster und sitzt im Programm unten rechts
        # (DemoPanel._in_ecke_setzen); offscreen gibt es keinen passenden Bildschirm,
        # deshalb hier an dieselbe Stelle malen, mit dünnem Fensterrahmen.
        links = HAUPTFENSTER[0] - panel.width() - 14
        oben = HAUPTFENSTER[1] - panel.height() - 24
        maler = QPainter(bild)
        maler.drawPixmap(QPoint(links, oben), panel)
        maler.setPen(QColor("#8a8a8a"))
        maler.drawRect(links - 1, oben - 1, panel.width() + 1, panel.height() + 1)
        maler.end()
        bild = bild.copy(0, 0, *HAUPTFENSTER)
        datei = ziel / "handbuch_demo.png"
        bild.save(str(datei))
    finally:
        tour.beenden()
        _warten(300)
        desktop_demo.DemoTour.TEMPO = tempo
        tempfile.tempdir = alt_tempdir
    _schliessen(fenster, conn)
    return [datei]


#: Name -> Funktion (eine Funktion kann mehrere Bilder liefern, siehe BILD_DATEIEN).
BILDER = {
    "handbuch_start": _bild_start,
    "handbuch_termin_anlegen": _bild_termin_anlegen,
    "handbuch_teilnehmer": _bild_teilnehmer,
    "handbuch_teilnehmer_dialoge": _bild_teilnehmer_dialoge,
    "handbuch_formular_import": _bild_einfacher_reiter("formular_import_tab", "handbuch_formular_import"),
    "handbuch_zeitplan": _bild_zeitplan,
    "handbuch_ergebniserfassung": _bild_ergebniserfassung,
    "handbuch_auswertung": _bild_auswertung,
    "handbuch_uebersicht": _bild_uebersicht,
    "handbuch_export": _bild_einfacher_reiter("export_tab", "handbuch_export"),
    "handbuch_datensicherung": _bild_einfacher_reiter("datensicherung_tab", "handbuch_datensicherung"),
    "handbuch_demo": _bild_demo,
}

#: Erwartete Dateien und Größen (auch für den Test).
BILD_DATEIEN = {
    "handbuch_start": (900, 520),
    "handbuch_termin_anlegen": (640, 900),
    "handbuch_teilnehmer": HAUPTFENSTER,
    "handbuch_teilnehmer_dialog_ed": (1000, 760),
    "handbuch_teilnehmer_dialog_dk": (1000, 760),
    "handbuch_formular_import": HAUPTFENSTER,
    "handbuch_zeitplan": HAUPTFENSTER,
    "zeitplan": (1880, 835),
    "handbuch_ergebniserfassung": HAUPTFENSTER,
    "ergebniserfassung": (1917, 651),
    "handbuch_auswertung": HAUPTFENSTER,
    "handbuch_uebersicht": HAUPTFENSTER,
    "handbuch_export": HAUPTFENSTER,
    "handbuch_datensicherung": HAUPTFENSTER,
    "handbuch_demo": HAUPTFENSTER,
}


def main(argv: list[str] | None = None) -> list[Path]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ziel", type=Path, default=REPO / "docs" / "bilder")
    parser.add_argument("--nur", default="", help="kommagetrennte Namen aus BILDER")
    args = parser.parse_args(argv)
    auswahl = [n.strip() for n in args.nur.split(",") if n.strip()] or list(BILDER)
    unbekannt = [n for n in auswahl if n not in BILDER]
    if unbekannt:
        parser.error(f"unbekannte Bilder: {', '.join(unbekannt)} (möglich: {', '.join(BILDER)})")
    args.ziel.mkdir(parents=True, exist_ok=True)

    _umgebung_einrichten()
    erzeugt: list[Path] = []
    # ignore_cleanup_errors: nach der Demo hält das Hauptfenster die Datei ggf. noch offen.
    with tempfile.TemporaryDirectory(prefix="shs-screenshots-", ignore_cleanup_errors=True) as tmp:
        termine = _Termine(Path(tmp))
        for name in auswahl:
            erzeugt += BILDER[name](termine, args.ziel)
        _warten(300)
    for pfad in erzeugt:
        bild = QPixmap(str(pfad))
        print(f"{pfad.name}: {bild.width()} x {bild.height()}")
    return erzeugt


if __name__ == "__main__":
    main()
