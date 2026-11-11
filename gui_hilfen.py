"""Gemeinsame Fixtures und Hilfen der GUI-Tests (aus test_app_gui.py ausgelagert).

Jede Datei test_gui_*.py holt sie per `from gui_hilfen import *`; `__all__` enthält bewusst auch
die Namen mit Unterstrich, die Fixtures (auch die automatischen) wirken so in jeder Testdatei.
"""

from __future__ import annotations

import datetime
import os
import sys
import pytest
from contextlib import closing
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QMessageBox, QPushButton
import db as _db_modul
from app import HauptFenster, StartDialog
from desktop_dialoge import TeilnehmerDialog, VeranstaltungsDialog
import desktop_ergebnis_speichern
from desktop_ergebnis import ErgebnisTab
from desktop_gemeinsam import _ERGEBNIS_SPALTEN_JE_DISZIPLIN
from db import (
    NeuerTeilnehmer,
    add_teilnehmer,
    get_teilnehmer,
    add_zeitplan_pruefungsblock,
    get_veranstaltung,
    init_db,
    set_veranstaltung,
)
from desktop_verwaltung import VerwaltungTab
from desktop_zeitplan import ZeitplanTab
from desktop_gemeinsam import _ABBRUCH_SPALTE


# Hinweistexte der letzten Speichermeldungen (siehe gespeichert_meldungen).
meldungen_hinweise: list = []


@pytest.fixture(autouse=True)
def gespeichert_meldungen(monkeypatch):
    """UX-Test U7: Nach jedem Speichern erscheint ein modales Meldungsfenster - in den Tests
    wird es durch eine Aufzeichnung ersetzt, damit kein Test daran hängen bleibt."""
    meldungen = []

    def _aufzeichnen(parent, pfad, titel, datei_oeffnen_text="PDF öffnen", hinweis=None):
        meldungen.append((str(pfad), titel, datei_oeffnen_text))
        meldungen_hinweise.append(hinweis)

    meldungen_hinweise[:] = []

    # In jedem Modul, das die Meldung selbst importiert (app, desktop_gemeinsam,
    # desktop_verwaltung ...), siehe ueberall_ersetzen.
    ueberall_ersetzen(monkeypatch, "_datei_gespeichert_melden", _aufzeichnen)
    # UX-Test U1: nach Importen wird die Sammelvergabe per Rückfrage angeboten - in den
    # Tests nur aufzeichnen (eigener Test unten nutzt die echte Funktion).
    ueberall_ersetzen(
        monkeypatch, "_startnummern_nach_import_anbieten",
        lambda parent, conn, *_vorher: meldungen.append(("import", None, None)),
    )
    return meldungen


@pytest.fixture
def termin(tmp_path):
    """Frische, initialisierte Termin-Datenbank (Datei + Verbindung) für jeden Test -
    entspricht dem Muster aus test_db.py, liefert zusätzlich den Dateipfad, den
    HauptFenster für den Fenstertitel und die Export-Ablage benötigt."""
    pfad = str(tmp_path / "test_termin.sqlite")
    connection = init_db(pfad)
    yield connection, pfad
    connection.close()


# --- Gemeinsame Attrappen und Zeitgrenzen (Abschluss-QS A19c, umgesetzt 18.10.2026) -------
#
# Zeitgrenze für qtbot.waitUntil: Hintergrundarbeit (Update-Abfrage, Neuaufbau, Freigabe
# eines Dialogs) braucht lokal Millisekunden; die Grenze gilt nur für langsame CI-Rechner.
WARTEZEIT_MS = 3000


# Welcher Teil eines QMessageBox-Aufrufs (parent, titel, text, knoepfe, vorgabe) gemerkt wird.
_DIALOG_TEIL = {
    "text": lambda a: a[2],
    "titel": lambda a: a[1],
    "args": lambda a: a,
    "titel_text": lambda a: (a[1], a[2]),
    "titel_vorgabe": lambda a: (a[1], a[4]),
    "text_vorgabe": lambda a: (a[2], a[4]),
}


def rueckfragen_sammeln(monkeypatch, *antworten, merke="text"):
    """Ersetzt app.QMessageBox.question: merkt je Aufruf den Teil `merke` und antwortet
    der Reihe nach mit `antworten` (die letzte gilt für alle weiteren Fragen)."""
    gesammelt = []

    def _frage(*a, **_k):
        gesammelt.append(_DIALOG_TEIL[merke](a))
        return antworten[min(len(gesammelt), len(antworten)) - 1]

    monkeypatch.setattr("app.QMessageBox.question", _frage)
    return gesammelt


def rueckfragen_beantworten(monkeypatch, antwort):
    """Ersetzt app.QMessageBox.question durch eine feste Antwort, ohne mitzuschreiben -
    oft nur, damit beim Schließen am Testende kein modales Fenster hängt."""
    monkeypatch.setattr("app.QMessageBox.question", lambda *_a, **_k: antwort)


def meldungen_sammeln(monkeypatch, art, merke="text"):
    """Ersetzt app.QMessageBox.<art> ("information", "warning", "critical") und merkt je
    Aufruf den Teil `merke`."""
    gesammelt = []
    monkeypatch.setattr(f"app.QMessageBox.{art}", lambda *a, **_k: gesammelt.append(_DIALOG_TEIL[merke](a)))
    return gesammelt


def verteilen_dialog_bestaetigen(monkeypatch, pause: tuple[str, int] | None = None, abbrechen: bool = False):
    """Ersetzt das Anzeigen des Dialogs „Automatisch verteilen“ (UX-Test 2026-11, T1): setzt
    auf Wunsch die Mittagspause und bestätigt; liefert die Liste der gezeigten Dialoge."""
    from desktop_dialoge import VerteilenDialog

    gezeigt = []

    def _exec(dialog):
        gezeigt.append(dialog)
        if abbrechen:
            return QDialog.Rejected
        dialog.mit_pause.setChecked(pause is not None)
        if pause is not None:
            dialog.uhrzeit.setText(pause[0])
            dialog.dauer_minuten.setValue(pause[1])
        return QDialog.Accepted

    monkeypatch.setattr(VerteilenDialog, "exec", _exec)
    return gezeigt


def import_meldungen_sammeln(monkeypatch):
    """Wie meldungen_sammeln(..., "information"), fängt aber auch die Importmeldung mit Knopf
    „Meldung kopieren und schließen“ und Warnsymbol ab (UX-Test 03.11.2026, X10: eigenes QMessageBox-Fenster)."""
    gesammelt = meldungen_sammeln(monkeypatch, "information")
    monkeypatch.setattr(QMessageBox, "exec", lambda box: gesammelt.append(box.text()) or 0)
    return gesammelt


#: Module der Desktop-Oberfläche, die gemeinsame Namen (z. B. termine_ordner) jeweils selbst
#: importieren - siehe ueberall_ersetzen.
DESKTOP_MODULE = ("app", "desktop_abrechnung", "desktop_auswertung", "desktop_darstellung", "desktop_demo", "desktop_dialoge",
                  "desktop_demo_panel", "desktop_demo_schritte",
                  "desktop_ergebnis", "desktop_ergebnis_speichern", "desktop_ergebnis_zellen",
                  "desktop_formular", "desktop_gemeinsam",
                  "desktop_import_meldungen", "desktop_programm", "desktop_teilnehmer", "desktop_verwaltung",
                  "desktop_zeitplan")


#: Die echte Funktion, bevor ein Test sie ersetzt (für die Gegenprobe zum Ordner-Schutz).
_ECHTER_TERMINE_ORDNER = _db_modul.termine_ordner


def ueberall_ersetzen(monkeypatch, name, wert):
    """Ersetzt `name` in jedem Desktop-Modul, das ihn hat (offene Punkte O3, 19.10.2026).
    Seit app.py aufgeteilt ist, holt sich jedes Modul z. B. termine_ordner per
    `from … import` selbst - ein Patch nur auf "app.termine_ordner" erreicht die anderen nicht.
    Nicht erreicht werden Namen, die ein Modul erst in einer Funktion importiert (z. B.
    termine_ordner in desktop_gemeinsam.absturzprotokoll_einrichten - dort wirkt nur der
    db-Patch aus _termine_ordner_schuetzen)."""
    import importlib
    for modulname in DESKTOP_MODULE:
        modul = importlib.import_module(modulname)
        if hasattr(modul, name):
            monkeypatch.setattr(modul, name, wert)


@pytest.fixture(autouse=True)
def _termine_ordner_schuetzen(monkeypatch, tmp_path_factory):
    """Kein Test landet im echten Termine-Ordner des Benutzerprofils (offene Punkte O3):
    termine_ordner zeigt in allen Desktop-Modulen und in db auf einen eigenen Temp-Ordner.
    Tests mit einem bestimmten Ordner setzen ihn mit ueberall_ersetzen. db_sicherung nutzt
    termine_ordner als Vorgabe für Sicherung und Wiederherstellung."""
    import db_sicherung
    ordner = tmp_path_factory.mktemp("termine")
    ueberall_ersetzen(monkeypatch, "termine_ordner", lambda: ordner)
    for modul in (_db_modul, db_sicherung):
        monkeypatch.setattr(modul, "termine_ordner", lambda: ordner)
    return ordner


@pytest.fixture(autouse=True)
def _bilder_ordner_schuetzen(monkeypatch, tmp_path_factory):
    """Häkchen, Pfeile und Symbol-PNGs (desktop_darstellung/desktop_gemeinsam.symbol_png)
    landen in einem Temp-Ordner statt im echten Benutzerprofil (Marco 01.11.2026). Tests
    mit eigenem Pfad (darstellung_speicher) ersetzen _haken_pfad danach noch einmal."""
    import desktop_darstellung as darstellung
    ordner = tmp_path_factory.mktemp("bilder")
    monkeypatch.setattr(darstellung, "_haken_pfad", lambda: f"{ordner}/haken.png".replace("\\", "/"))


def meldungen_stumm(monkeypatch, *arten):
    """Ersetzt app.QMessageBox.<art> für jede Art durch einen stummen Aufruf."""
    for art in arten:
        monkeypatch.setattr(f"app.QMessageBox.{art}", lambda *_a, **_k: None)


def _pause_dialog_attrappe(dauer_minuten, bezeichnung, uhrzeit=None, genau=False):
    """Ersetzt PauseDialog: sofort „OK“ mit den gegebenen Werten. Mit `uhrzeit` gilt die
    Pause für alle Richter ab dieser Uhrzeit (wie das Häkchen im echten Dialog), mit `genau`
    beginnt sie genau dann (R-B20)."""

    class _Feld:
        def __init__(self, wert):
            self._wert = wert

        def isChecked(self):
            return bool(self._wert)

        def text(self):
            return self._wert or ""

    class _PauseDialog:
        def __init__(self, *_a, **_k):
            self.fuer_alle = _Feld(uhrzeit)
            self.uhrzeit = _Feld(uhrzeit)
            self.genau = _Feld(genau)

        def exec(self):
            return QDialog.Accepted

        def werte(self):
            return {"dauer_minuten": dauer_minuten, "bezeichnung": bezeichnung}

    return _PauseDialog


def _vorbelegung_aufzeichnen(ziel: dict):
    """Ersetzt VeranstaltungsDialog: schreibt die übergebene Vorbelegung nach `ziel` und
    bricht sofort ab, statt einen echten (blockierenden) Dialog zu öffnen."""

    class _AbbrechenderDialog:
        def __init__(self, parent=None, vorbelegung=None, bearbeiten=False, speichern=None):
            ziel.clear()
            ziel.update(vorbelegung or {})

        def exec(self):
            return QDialog.Rejected

    return _AbbrechenderDialog


def _import_dialog_attrappe(quelle, ids):
    """Ersetzt TerminImportDialog: sofort „OK“ mit der (schon geöffneten) Quelle `quelle`
    und den Teilnehmer-IDs `ids`; schliesse_quelle schließt sie, falls sie das kann."""

    class _ImportDialog:
        def __init__(self, parent, aktueller_pfad):
            pass

        def exec(self):
            return QDialog.Accepted

        def quelle_conn(self):
            return quelle

        def ausgewaehlte_ids(self):
            return ids

        def schliesse_quelle(self):
            if hasattr(quelle, "close"):
                quelle.close()

    return _ImportDialog


@pytest.fixture
def conn(termin):
    """Nur die Verbindung, für Tests ohne HauptFenster (kein Pfad nötig)."""
    connection, _pfad = termin
    return connection


def _teilnehmer_anlegen(connection, **overrides) -> int:
    daten = dict(
        nachname="Muster",
        vorname="Max",
        rufname_hund="Bello",
        art="ED",
        stufe=1,
        disziplin="Flächensuche",
        startnummer=1,
    )
    daten.update(overrides)
    return add_teilnehmer(connection, NeuerTeilnehmer(**daten))


def _zeilen_markieren(tab, *zeilen):
    from PySide6.QtCore import QItemSelectionModel

    modell = tab.tabelle.selectionModel()
    modell.clearSelection()
    for zeile in zeilen:
        modell.select(tab.tabelle.model().index(zeile, 0), QItemSelectionModel.Select | QItemSelectionModel.Rows)


_ALTDATEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdaten", "altversionen")


def _ergebnis_zeile(tab, nachname):
    """Zeile des (ersten) Teilnehmers mit diesem Nachnamen in der Ergebniserfassung."""
    return next(r for r in range(tab.zeilenanzahl()) if tab.teilnehmer_der_zeile(r)["nachname"] == nachname)


def _ergebnis_nachnamen(tab):
    """Nachnamen in der angezeigten Reihenfolge der Ergebniserfassung."""
    return [tab.teilnehmer_der_zeile(r)["nachname"] for r in range(tab.zeilenanzahl())]


def _fenster_auf_ergebnis_tab(qtbot, conn, pfad):
    set_veranstaltung(conn, verein="SGV Köppern e.V.", datum="2026-09-19")
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._tabs.setCurrentWidget(fenster.ergebnis_tab)
    return fenster, fenster.ergebnis_tab


def _hin_und_zurueck(fenster):
    fenster._tabs.setCurrentWidget(fenster.teilnehmer_tab)
    fenster._tabs.setCurrentWidget(fenster.ergebnis_tab)


def _zwei_eingaben_mit_fehler_beim_zweiten(qtbot, termin, monkeypatch, sammeln_ab):
    """Zwei Teilnehmer mit Eingaben; das Schreiben des zweiten Ergebnisses scheitert."""
    conn, pfad = termin
    erster = _teilnehmer_anlegen(conn, nachname="Erster", startnummer=1)
    zweiter = _teilnehmer_anlegen(conn, nachname="Zweiter", startnummer=2)
    monkeypatch.setattr("desktop_ergebnis_speichern._SAMMELSPEICHERN_UEBER_TEILNEHMER", sammeln_ab)
    fenster, ergebnis_tab = _fenster_auf_ergebnis_tab(qtbot, conn, pfad)
    for zeile in range(2):
        ergebnis_tab.punkte_eintragen(zeile, "Flächensuche", "50", "30")

    echt = desktop_ergebnis_speichern.eintragen_ergebnis

    def zweites_scheitert(conn_, tid, *a, **k):
        if tid == zweiter:
            _schreibfehler()
        echt(conn_, tid, *a, **k)

    meldungen = []
    monkeypatch.setattr("desktop_ergebnis_speichern.eintragen_ergebnis", zweites_scheitert)
    ueberall_ersetzen(monkeypatch, "_db_fehler_anzeigen", lambda parent, exc, einleitung: meldungen.append(einleitung))
    # Beim Schließen am Testende: ungespeicherte Eingaben verwerfen statt modal nachzufragen.
    rueckfragen_beantworten(monkeypatch, QMessageBox.No)
    ergebnis_tab.alle_speichern()
    return conn, ergebnis_tab, erster, meldungen


def _commit_zaehlen(liste, funktion):
    def aufruf(*a, commit=True, **k):
        liste.append(commit)
        return funktion(*a, commit=commit, **k)
    return aufruf


def _disziplin_waehlbar(combo, text):
    index = combo.findText(text)
    return combo.model().item(index).isEnabled()


class _Antwort:
    def __init__(self, daten=None, fehler=None):
        self._daten, self._fehler = daten, fehler

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        if self._fehler is not None:
            raise self._fehler
        return self._daten


def _schreibfehler(*_a, **_k):
    import sqlite3 as _sqlite3
    raise _sqlite3.OperationalError("attempt to write a readonly database")


def _neuer_termin_dialog(qtbot, tmp_path, monkeypatch):
    ueberall_ersetzen(monkeypatch, "termine_ordner", lambda: tmp_path)
    dialog = VeranstaltungsDialog(vorbelegung={"verein": "SGV Köppern", "datum": "2026-11-14",
                                               "verband": "HSVRM", "meldestelle": "x"})
    qtbot.addWidget(dialog)
    return dialog


def _teilnehmer_dialog_ausgefuellt(qtbot, **kwargs):
    dialog = TeilnehmerDialog(vergebene_nummern=set(), **kwargs)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.nachname.setText("Muster")
    dialog.vorname.setText("Max")
    dialog.rufname_hund.setText("Bello")
    return dialog


def _tag(abstand_tage: int) -> datetime.date:
    return datetime.date.today() + datetime.timedelta(days=abstand_tage)


def _vorhandener_ed_teilnehmer(conn, startnummer):
    tid = add_teilnehmer(conn, NeuerTeilnehmer(
        nachname="Alt", vorname="A", rufname_hund="Rex", art="ED", stufe=1, disziplin="Trümmerfeld",
        startnummer=startnummer, gegenstand_1="Socke", gegenstand_1_disziplin="Trümmerfeld"))
    return get_teilnehmer(conn, tid)


class _FakeSitzungsManager:
    """Ersatz für QSessionManager (commitDataRequest, H-4): merkt sich cancel/release."""

    def __init__(self, interaktion: bool):
        self.interaktion = interaktion
        self.abgebrochen = False
        self.freigegeben = False

    def allowsInteraction(self):
        return self.interaktion

    def cancel(self):
        self.abgebrochen = True

    def release(self):
        self.freigegeben = True


_STATUS_SPALTE_PRUEFUNG = """
import os, sys, tempfile
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
app = QApplication([])
import db
from app import HauptFenster
from desktop_gemeinsam import _STATUS_SPALTE
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
    pfad = str(Path(tmp) / "t.sqlite")
    conn = db.init_db(pfad)
    sys.path.insert(0, str(Path.cwd() / "tools"))
    import screenshots  # dieselben Testdaten wie auf den Handbuch-Bildern
    for daten in screenshots.TEILNEHMER[:2]:
        db.add_teilnehmer(conn, db.NeuerTeilnehmer(**daten))
    fenster = HauptFenster(conn, pfad)
    fenster.resize(1400, 820)
    fenster.show()
    QTest.qWait(150)
    fenster._tabs.setCurrentWidget(fenster.ergebnis_tab)
    QTest.qWait(250)
    fenster.resize(1917, 651)
    QTest.qWait(300)
    fenster.ergebnis_tab.aktualisieren()
    QTest.qWait(300)
    t = fenster.ergebnis_tab.tabelle
    summe = sum(t.columnWidth(c) for c in range(t.columnCount()))
    print(summe, t.viewport().width(), t.columnWidth(_STATUS_SPALTE), t.sizeHintForColumn(_STATUS_SPALTE))
    fenster.close()
    conn.close()
"""


def _ed_zeile_hat_nur_eigene_eingabefelder(tab, row: int, ed_disziplin: str) -> None:
    assert tab.erfassbare_disziplinen(row) == [ed_disziplin]
    for disziplin, spalten in _ERGEBNIS_SPALTEN_JE_DISZIPLIN.items():
        for spalte in spalten:
            if disziplin == ed_disziplin:
                assert tab.spalte_bearbeitbar(row, spalte)
            else:
                # Regressionsschutz 23.09.: kein altes DK-Eingabefeld über dem „–“.
                assert not tab.spalte_bearbeitbar(row, spalte)
                assert tab.tabelle.item(row, spalte).text() == "–"


def _termin_mit_teilnehmer(pfad, verein, datum, nachname):
    conn = init_db(str(pfad))
    set_veranstaltung(conn, verein=verein, datum=datum, ort="X")
    add_teilnehmer(conn, NeuerTeilnehmer(
        nachname=nachname, vorname="V", rufname_hund="Rex", art="ED", stufe=1, disziplin="Trümmerfeld"))
    conn.close()


def _seite_beschaedigen(pfad, tabelle):
    """Überschreibt die Wurzelseite von `tabelle` - Aufbauprüfung und Abfragen auf anderen
    Tabellen gelingen weiter, erst quick_check findet den Schaden."""
    import sqlite3
    with closing(sqlite3.connect(pfad)) as c:
        seite = c.execute("SELECT rootpage FROM sqlite_master WHERE name = ?", (tabelle,)).fetchone()[0]
        groesse = c.execute("PRAGMA page_size").fetchone()[0]
    with open(pfad, "r+b") as datei:
        datei.seek((seite - 1) * groesse)
        datei.write(b"\xff" * 64)


# --- Codeprüfung 22.09., G3: Terminwechsel mit nicht speicherbaren Ergebnissen ------
# Analog zu den closeEvent-Tests oben: bleibt nach "Jetzt speichern? -> Ja" trotzdem etwas
# ungespeichert (z. B. nur Suche ODER Anzeige eingetragen), wird vor dem Wechsel erneut
# nachgefragt; Standard/Nein bricht den Wechsel ab. StartDialog wird durch eine Attrappe
# ersetzt, die nur mitzählt, ob der Wechsel überhaupt bis zur Terminauswahl gekommen ist.


class _StartDialogAttrappe:
    """Startdialog, der einen Termin wählt (oder, mit `ergebnis`, abbricht bzw. die Demo
    anfordert). `geoeffnet` zählt die Dialoge, `termin_geoeffnet` die Versuche, den gewählten
    Termin zu öffnen - die Rückfrage nach ungespeicherten Ergebnissen kommt dazwischen."""
    geoeffnet = 0
    termin_geoeffnet = 0
    ergebnis = QDialog.Accepted
    demo = False
    neu = False
    pfad_vorgabe = "gewaehlter_termin.sqlite"

    def __init__(self, *args, **kwargs):
        type(self).geoeffnet += 1
        self.pfad = type(self).pfad_vorgabe
        self.demo_angefordert = type(self).demo
        self.neu_angelegt = type(self).neu

    def exec(self):
        return type(self).ergebnis


def _terminwechsel_vorbereiten(qtbot, termin, monkeypatch, antworten, speichern_gelingt):
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)

    zustand = {"ungespeichert": True}
    monkeypatch.setattr(
        type(fenster.ergebnis_tab), "hat_ungespeicherte_aenderungen", lambda self: zustand["ungespeichert"]
    )

    def _speichern(self):
        if speichern_gelingt:
            zustand["ungespeichert"] = False

    monkeypatch.setattr(type(fenster.ergebnis_tab), "alle_speichern", _speichern)
    fragen = rueckfragen_sammeln(monkeypatch, *antworten, merke="titel")
    monkeypatch.setattr(_StartDialogAttrappe, "geoeffnet", 0)
    monkeypatch.setattr(_StartDialogAttrappe, "termin_geoeffnet", 0)
    monkeypatch.setattr(_StartDialogAttrappe, "ergebnis", QDialog.Accepted)
    monkeypatch.setattr(_StartDialogAttrappe, "demo", False)
    monkeypatch.setattr(_StartDialogAttrappe, "neu", False)
    monkeypatch.setattr(_StartDialogAttrappe, "pfad_vorgabe", "gewaehlter_termin.sqlite")
    monkeypatch.setattr("app.StartDialog", _StartDialogAttrappe)

    def _termin_oeffnen_attrappe(*_args, **_kwargs):
        _StartDialogAttrappe.termin_geoeffnet += 1
        return None  # wie ein gescheitertes Öffnen: der bisherige Termin bleibt

    monkeypatch.setattr("app._termin_oeffnen_mit_meldung", _termin_oeffnen_attrappe)
    return fenster, fragen


class _StartDialogMitPfad:
    """Startdialog-Attrappe, die einen festen Pfad wählt."""
    pfad_vorgabe = None

    def __init__(self, *a, **k):
        self.demo_angefordert = False
        self.pfad = _StartDialogMitPfad.pfad_vorgabe

    def exec(self):
        return QDialog.Accepted


def _startdialog_mit_terminen(qtbot, tmp_path, monkeypatch):
    from types import SimpleNamespace

    termine = []
    for name, verein in (("a.sqlite", "Verein A"), ("b.sqlite", "")):
        (tmp_path / name).write_bytes(b"")
        termine.append(SimpleNamespace(pfad=str(tmp_path / name), dateiname=name, datum="2026-11-14",
                                       verein=verein, ort="", anzahl_teilnehmer=0, lesbar=True,
                                       teilnehmer_anzeige="0"))
    monkeypatch.setattr("app.liste_termine", lambda: [t for t in termine if os.path.exists(t.pfad)])
    ueberall_ersetzen(monkeypatch, "termine_ordner", lambda: tmp_path)
    start = StartDialog()
    qtbot.addWidget(start)
    return start


# --- Darstellung: Hintergrund-Design + Akzentfarbe (23.09.) ------------------------------


@pytest.fixture
def darstellung_speicher(monkeypatch, tmp_path_factory):
    """Ersetzt die QSettings-Zugriffe durch einen Speicher im Arbeitsspeicher (keine
    Schreibzugriffe in Registry/~/.config) und stellt danach den Zustand der
    QApplication (Stil, Palette, Stylesheet, Schrift) sowie die Modul-Zustände von app.py wieder
    her, damit nachfolgende Tests nicht im dunklen Design laufen. Die Einstellungs-
    Funktionen werden in BEIDEN Modulen ersetzt: HauptFenster (app.py) ruft sie direkt
    auf, _darstellung_anwenden() in desktop_darstellung.py ebenfalls."""
    import app as app_modul
    import desktop_darstellung as darstellung

    qapp = QApplication.instance()
    vorher_stylesheet = qapp.styleSheet()
    qapp.setStyleSheet("")
    vorher_stil = qapp.style().name()
    qapp.setStyleSheet(vorher_stylesheet)
    vorher_palette = QPalette(qapp.palette())
    hinweise = qapp.styleHints()
    for name in ("_aktives_design", "_ursprung_stil", "_aktueller_stil", "_haken_geschrieben",
                 "_schrift_faktor", "_basis_schrift_pt"):
        monkeypatch.setattr(darstellung, name, getattr(darstellung, name))
    vorher_schrift = QFont(qapp.font())
    monkeypatch.setattr(darstellung, "_pfeile_geschrieben", set())
    # Häkchen-Bild nicht ins echte Benutzerprofil schreiben.
    haken = tmp_path_factory.mktemp("haken") / "haken.png"
    monkeypatch.setattr(darstellung, "_haken_pfad", lambda: str(haken).replace("\\", "/"))

    speicher = {"theme": "blau", "design": "hell", "schrift": "normal"}
    for modul in (app_modul, darstellung):
        monkeypatch.setattr(modul, "_gespeichertes_theme_lesen", lambda: speicher["theme"])
        monkeypatch.setattr(modul, "_gespeichertes_design_lesen", lambda: speicher["design"])
        monkeypatch.setattr(modul, "_gespeicherte_schriftstufe_lesen", lambda: speicher["schrift"])
        monkeypatch.setattr(modul, "_theme_speichern", lambda name: speicher.__setitem__("theme", name))
        monkeypatch.setattr(modul, "_design_speichern", lambda name: speicher.__setitem__("design", name))
        monkeypatch.setattr(modul, "_schriftstufe_speichern", lambda name: speicher.__setitem__("schrift", name))
    yield speicher
    if hasattr(Qt, "ColorScheme") and hasattr(hinweise, "setColorScheme"):
        hinweise.setColorScheme(Qt.ColorScheme.Unknown)  # wieder dem System folgen
    qapp.setFont(vorher_schrift)
    qapp.setStyle(vorher_stil)
    qapp.setPalette(vorher_palette)
    qapp.setStyleSheet(vorher_stylesheet)


@pytest.fixture
def fehlerfenster_hook(qtbot, monkeypatch):
    """Richtet den Fehlerfenster-Hook über einem protokollierenden Ersatz-Hook ein; zeigt
    statt eines Fensters nur einen Eintrag in `fenster`. Zustand wird danach zurückgesetzt."""
    import desktop_gemeinsam

    protokolliert, fenster = [], []
    monkeypatch.setattr(sys, "excepthook", lambda typ, wert, tb: protokolliert.append(str(wert)))
    monkeypatch.setattr(desktop_gemeinsam, "_gezeigte_fehler", set())
    monkeypatch.setattr(desktop_gemeinsam, "_fehlerfenster_offen", False)
    monkeypatch.setattr(desktop_gemeinsam, "fehlerfenster_zeigen",
                        lambda version, fehler, parent=None: fenster.append(fehler))
    desktop_gemeinsam.fehlerfenster_einrichten("9.9.9")
    return protokolliert, fenster


def _fehler_melden(fehler: BaseException, zeile: int = 0) -> None:
    """Löst `fehler` aus und reicht ihn an sys.excepthook weiter; `zeile` wählt eine von zwei
    Auslösestellen (für unterschiedliche Fehlerbilder)."""
    try:
        if zeile:
            raise fehler
        raise fehler
    except BaseException:
        sys.excepthook(*sys.exc_info())


def _hilfsfunktion_mit_fehler():
    raise RuntimeError("gleiche innerste Stelle")


def _weg_a():
    _hilfsfunktion_mit_fehler()


def _weg_b():
    _hilfsfunktion_mit_fehler()


def _ueber_weg_melden(weg) -> None:
    try:
        weg()
    except RuntimeError:
        sys.excepthook(*sys.exc_info())


# --- Ergebniserfassung: Tastatur (offene Punkte O8, Marco 18.10.2026) ---------------------
# Seit O8 Zellen statt Eingabefelder: Lostippen ersetzt den Wert, Enter übernimmt und bleibt
# in der Zelle, Tab springt nur durch bedienbare Zellen, die Leertaste schaltet ein Häkchen,
# und eine gerade getippte Zahl geht beim Speichern nicht verloren.


def _ergebnis_tab_gezeigt(qtbot, conn):
    tab = ErgebnisTab(conn)
    qtbot.addWidget(tab)
    tab.show()
    tab.tabelle.setFocus()
    return tab


def _abbruch_auswahl(qtbot, tab, zeile: int, text: str) -> None:
    """Öffnet die Auswahlliste der Abbruch-Zelle per Leertaste und wählt `text` (R7)."""
    from PySide6.QtWidgets import QComboBox

    tab.tabelle.setCurrentCell(zeile, _ABBRUCH_SPALTE)
    qtbot.keyClick(tab.tabelle, Qt.Key_Space)
    # Ein zuvor geschlossener Editor kann noch auf deleteLater warten - nur der sichtbare zählt.
    editoren = [c for c in tab.tabelle.viewport().findChildren(QComboBox) if c.isVisible()]
    assert len(editoren) == 1, "Auswahlliste erwartet"
    combo = editoren[0]
    index = combo.findText(text)
    assert index >= 0, [combo.itemText(i) for i in range(combo.count())]
    combo.setCurrentIndex(index)
    combo.activated.emit(index)


def _dk_parallel_termin(conn):
    """Drei DK-Blöcke derselben LK gleichzeitig bei drei Richtern = jedes Team dreifach."""
    from db import zeitplan_richter_aus_veranstaltung_anlegen, list_zeitplan_richter

    set_veranstaltung(conn, verein="HSV", datum="2026-11-14",
                      wertungsrichter_1="Anna", wertungsrichter_2="Bernd", wertungsrichter_3="Clara")
    for i, name in enumerate(["Muster", "Otto"], 1):
        _teilnehmer_anlegen(conn, nachname=name, art="DK", stufe=1, disziplin=None, startnummer=i)
    zeitplan_richter_aus_veranstaltung_anlegen(conn)
    for richter, disziplin in zip(list_zeitplan_richter(conn), ("Trümmerfeld", "Flächensuche", "Behältnisstrecke")):
        add_zeitplan_pruefungsblock(conn, richter["id"], "DK", 1, disziplin, 10)


# --- Demoprüfung (Marcos Wunsch 04.10.2026, desktop_demo.py) --------------------------


@pytest.fixture
def demo_umgebung(tmp_path, monkeypatch):
    """Temp- und Termine-Ordner der Demo ins tmp_path umleiten, ohne Pausen ablaufen
    lassen und jede modale Rückfrage/Meldung zum Testfehler machen - die Demo darf den
    Anwender nie mit einem Meldungsfenster blockieren. Einzige Ausnahme ist die Rückfrage, wenn
    er selbst „Beenden“ klickt (Nachtest 2, N9); Tests dafür ersetzen question eigens."""
    import tempfile

    import desktop_demo
    from PySide6.QtWidgets import QInputDialog

    temp = tmp_path / "temp"
    termine = tmp_path / "termine"
    temp.mkdir()
    termine.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    ueberall_ersetzen(monkeypatch, "termine_ordner", lambda: termine)
    monkeypatch.setattr(desktop_demo.DemoTour, "TEMPO", 0)
    # Automatisch weiter aus - die Countdown-Tests schalten es gezielt ein.
    monkeypatch.setattr(desktop_demo.DemoTour, "AUTO_WEITER_S", 0)

    def _modal(*args, **kwargs):
        pytest.fail(f"Demoprüfung zeigt ein modales Fenster: {args[1:3]}")

    for name in ("question", "information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, name, _modal)
    monkeypatch.setattr(QInputDialog, "getItem", _modal)
    return temp, termine


def _demo_bis(tour, praefix: str | None, pruefen=None, max_schritte: int = 30) -> None:
    """Klickt „Weiter“, bis der Schritt mit `praefix` erreicht ist (None: bis zum Ende).
    `pruefen(titel)` läuft nach jedem fertig ausgeführten Schritt."""
    for _ in range(max_schritte):
        if tour.ist_beendet:
            assert praefix is None, f"Demo beendet, bevor „{praefix}“ erreicht war"
            return
        titel = tour._schritte[tour._index].titel
        assert tour._panel.weiter_btn.isEnabled(), tour._panel.hinweis_label.text()
        if pruefen is not None:
            pruefen(titel)
        if praefix is not None and titel.startswith(praefix):
            return
        tour.weiter()
    pytest.fail("Demo endet nicht")


def _demo_mit_countdown(qtbot, termin, monkeypatch, sekunden=3):
    """Demo im Hauptfenster mit eingeschaltetem „Automatisch weiter“ (Fixture setzt 0)."""
    import desktop_demo

    monkeypatch.setattr(desktop_demo.DemoTour, "AUTO_WEITER_S", sekunden)
    # Feste Zeit statt Lesezeit nach Textlänge (X6), damit die Zählerstände vorhersagbar sind.
    monkeypatch.setattr(desktop_demo.DemoTour, "LESEZEIT_JE_WORT_S", 0)
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._demo_starten()
    return fenster._demo_tour


# --- Abdeckung 01.11.2026 (OFFEN B10): Zeitplan-Bearbeitung über die Oberfläche ----------


def _zeitplan_spalten(tab) -> list:
    """Die Richter-Spalten (QGroupBox) des Zeitplan-Reiters in der angezeigten Reihenfolge."""
    from PySide6.QtWidgets import QGroupBox

    spalten = []
    for i in range(tab._spalten_layout.count()):
        widget = tab._spalten_layout.itemAt(i).widget()
        if isinstance(widget, QGroupBox):
            spalten.append(widget)
    return spalten


def _zeitplan_spalte(tab, name):
    return next(s for s in _zeitplan_spalten(tab) if s.title() == name)


def _zeitplan_titel(tab) -> list[str]:
    return [s.title() for s in _zeitplan_spalten(tab)]


def _knopf(widget, text) -> QPushButton:
    return next(b for b in widget.findChildren(QPushButton) if b.text() == text)


def _symbolknopf(widget, tooltip) -> QPushButton:
    """Knopf nur mit Symbol (ohne Text), gefunden über den Tooltip."""
    return next(b for b in widget.findChildren(QPushButton) if not b.text() and b.toolTip() == tooltip)


def _zeitplan_liste(spalte):
    from PySide6.QtWidgets import QListWidget

    return spalte.findChild(QListWidget)


def _richter_namen(connection) -> list[str]:
    from db import list_zeitplan_richter

    return [r["name"] for r in list_zeitplan_richter(connection)]


def _zeitplan_tab(qtbot, connection) -> ZeitplanTab:
    # Bewusst ohne show(): showEvent würde Richter aus den Veranstaltungsdaten anlegen.
    tab = ZeitplanTab(connection)
    qtbot.addWidget(tab)
    return tab


def _zeitplan_aktionen():
    """(betroffene db-Funktion, Aufruf der Aktion) für den Fehlerweg-Test unten."""
    return [
        ("add_zeitplan_richter", lambda tab, r, liste: tab._richter_hinzufuegen()),
        ("umbenennen_zeitplan_richter", lambda tab, r, liste: tab._richter_umbenennen(r)),
        ("verschiebe_zeitplan_richter", lambda tab, r, liste: tab._richter_verschieben(r, 1)),
        ("loesche_zeitplan_richter", lambda tab, r, liste: tab._richter_loeschen(r, "R1")),
        ("add_zeitplan_pruefungsblock", lambda tab, r, liste: tab._pruefungsblock_hinzufuegen(r)),
        ("verschiebe_zeitplan_eintrag", lambda tab, r, liste: tab._eintrag_verschieben(liste, 1)),
        ("zeitplan_eintrag", lambda tab, r, liste: tab._eintrag_bearbeiten(liste)),
        ("aktualisiere_zeitplan_eintrag", lambda tab, r, liste: tab._eintrag_bearbeiten(liste)),
        ("loesche_zeitplan_eintrag", lambda tab, r, liste: tab._eintrag_entfernen(liste)),
    ]


# --- Abdeckung 01.11.2026 (OFFEN B10): Konflikt-Rückfrage beim Wiederherstellen ----------


def _sicherung_mit_namenskonflikt(tmp_path, termine) -> str:
    """Echte Sicherung mit „Pruefung.sqlite“ (Verein „Aus Sicherung“) und „Neu.sqlite“; im
    Termine-Ordner `termine` liegt schon eine andere „Pruefung.sqlite“ (Verein „Bestand“)."""
    from db_sicherung import sicherung_erstellen

    quelle = tmp_path / "quelle"
    quelle.mkdir()
    for ordner, name, verein in (
        (quelle, "Pruefung.sqlite", "Aus Sicherung"),
        (quelle, "Neu.sqlite", "Neu"),
        (termine, "Pruefung.sqlite", "Bestand"),
    ):
        with closing(init_db(str(ordner / name))) as verbindung:
            set_veranstaltung(verbindung, verein=verein, datum="2026-11-14")
    zip_pfad = tmp_path / "sicherung.zip"
    assert sicherung_erstellen(str(zip_pfad), ordner=quelle) == 2
    return str(zip_pfad)


def _vereine_im_ordner(ordner) -> dict:
    from db import oeffne_termin_lesend

    vereine = {}
    for pfad in ordner.glob("*.sqlite"):
        with closing(oeffne_termin_lesend(pfad)) as verbindung:
            vereine[pfad.name] = get_veranstaltung(verbindung)["verein"]
    return vereine


def _konflikt_box_ersetzen(monkeypatch, knopf):
    """Ersetzt QMessageBox.exec/clickedButton: merkt Titel, Text, Knöpfe und Vorgabe und
    „klickt“ den Knopf mit dem Text `knopf` (None: Fenster ohne Knopf geschlossen)."""
    gefragt = []

    def _exec(box):
        gefragt.append((box.windowTitle(), box.text(), sorted(b.text() for b in box.buttons()),
                        box.defaultButton().text()))
        return 0

    monkeypatch.setattr(QMessageBox, "exec", _exec)
    monkeypatch.setattr(QMessageBox, "clickedButton",
                        lambda box: next((b for b in box.buttons() if b.text() == knopf), None))
    return gefragt


# --- Abdeckung 01.11.2026 (OFFEN B10): bisher nie aufgebaute Dialoge --------------------


def _dialog_knopf(dialog, rolle):
    return dialog.findChild(QDialogButtonBox).button(rolle)


# --- Kleine Überraschung (desktop_beagle, Marco 01.11.2026) ---------------------------


def _beagle_fenster(qtbot, termin, monkeypatch):
    import desktop_beagle

    jetzt = {"t": 100.0}
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.resize(900, 600)
    fenster.show()
    qtbot.waitExposed(fenster)
    # Zähler mit der austauschbaren Uhr neu anlegen (der des Fensters nutzt die echte).
    fenster.kopf.bild_label.removeEventFilter(fenster._beagle_zaehler)
    zaehler = desktop_beagle.BeagleKlickZaehler(fenster, fenster.kopf.bild_label, uhr=lambda: jetzt["t"])
    return fenster, zaehler, jetzt


def _beagle_klicks(qtbot, fenster, jetzt, anzahl, pause=0.3):
    for _ in range(anzahl):
        jetzt["t"] += pause
        qtbot.mouseClick(fenster.kopf.bild_label, Qt.LeftButton)


# --- Abrechnung Leistungsrichter (Marco 09.11.2026) --------------------------------------------


def _abrechnung_termin(conn):
    set_veranstaltung(conn, verein="HSV", datum="2026-11-14", ort="Musterstadt",
                      wertungsrichter_1="Anna Alt", wertungsrichter_3="Carla Claus")


def _checkliste_tab(qtbot, conn):
    set_veranstaltung(conn, verein="HSV", datum="2026-11-14")
    tab = VerwaltungTab(conn)
    qtbot.addWidget(tab)
    return tab


__all__ = [
    "DESKTOP_MODULE",
    "WARTEZEIT_MS",
    "_ALTDATEN",
    "_Antwort",
    "_DIALOG_TEIL",
    "_ECHTER_TERMINE_ORDNER",
    "_FakeSitzungsManager",
    "_STATUS_SPALTE_PRUEFUNG",
    "_StartDialogAttrappe",
    "_StartDialogMitPfad",
    "_abbruch_auswahl",
    "_abrechnung_termin",
    "_beagle_fenster",
    "_beagle_klicks",
    "_bilder_ordner_schuetzen",
    "_checkliste_tab",
    "_commit_zaehlen",
    "_demo_bis",
    "_demo_mit_countdown",
    "_dialog_knopf",
    "_disziplin_waehlbar",
    "_dk_parallel_termin",
    "_ed_zeile_hat_nur_eigene_eingabefelder",
    "_ergebnis_nachnamen",
    "_ergebnis_tab_gezeigt",
    "_ergebnis_zeile",
    "_fehler_melden",
    "_fenster_auf_ergebnis_tab",
    "_hilfsfunktion_mit_fehler",
    "_hin_und_zurueck",
    "_import_dialog_attrappe",
    "_knopf",
    "_konflikt_box_ersetzen",
    "_neuer_termin_dialog",
    "_pause_dialog_attrappe",
    "_richter_namen",
    "_schreibfehler",
    "_seite_beschaedigen",
    "_sicherung_mit_namenskonflikt",
    "_startdialog_mit_terminen",
    "_symbolknopf",
    "_tag",
    "_teilnehmer_anlegen",
    "_teilnehmer_dialog_ausgefuellt",
    "_termin_mit_teilnehmer",
    "_termine_ordner_schuetzen",
    "_terminwechsel_vorbereiten",
    "_ueber_weg_melden",
    "_vereine_im_ordner",
    "_vorbelegung_aufzeichnen",
    "_vorhandener_ed_teilnehmer",
    "_weg_a",
    "_weg_b",
    "_zeilen_markieren",
    "_zeitplan_aktionen",
    "_zeitplan_liste",
    "_zeitplan_spalte",
    "_zeitplan_spalten",
    "_zeitplan_tab",
    "_zeitplan_titel",
    "_zwei_eingaben_mit_fehler_beim_zweiten",
    "conn",
    "darstellung_speicher",
    "demo_umgebung",
    "fehlerfenster_hook",
    "gespeichert_meldungen",
    "import_meldungen_sammeln",
    "meldungen_hinweise",
    "meldungen_sammeln",
    "meldungen_stumm",
    "rueckfragen_beantworten",
    "rueckfragen_sammeln",
    "termin",
    "ueberall_ersetzen",
    "verteilen_dialog_bestaetigen",
]
