"""Echte GUI-Tests für app.py über pytest-qt (qtbot).

Anders als test_db.py/test_pdf_export.py (die nur die Datenschicht bzw. die PDF-
Erzeugung prüfen, ganz ohne Qt) klickt und tippt dieses Modul tatsächlich in echten
Qt-Widgets - simuliert also, was ein Nutzer mit Maus/Tastatur tun würde, statt nur die
Syntax zu prüfen (wie es bislang nur über `py_compile` möglich war). Läuft komplett
headless (ohne sichtbares Fenster) über die Qt-eigene "offscreen"-Plattform, siehe
QT_QPA_PLATFORM in .github/workflows/tests.yml sowie pytest.ini (qt_api = pyside6).

Deckt gezielt die Bereiche ab, die laut Fortschritt.md zuletzt als "noch nicht real in
der GUI getestet" markiert waren: Bezahlt-Markierung, freie Gegenstand-Disziplin-
Zuordnung (ohne Default), Hilfe-Button und automatisches Speichern beim Beenden.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from app import HauptFenster, HilfeDialog, TeilnehmerDialog, TeilnehmerTab
from db import NeuerTeilnehmer, add_teilnehmer, init_db, list_teilnehmer, set_veranstaltung


@pytest.fixture
def termin(tmp_path):
    """Frische, initialisierte Termin-Datenbank (Datei + Verbindung) für jeden Test -
    entspricht dem Muster aus test_db.py, liefert zusätzlich den Dateipfad, den
    HauptFenster für den Fenstertitel und die Export-Ablage benötigt."""
    pfad = str(tmp_path / "test_termin.sqlite")
    connection = init_db(pfad)
    yield connection, pfad
    connection.close()


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


# --- Bezahlt-Markierung -------------------------------------------------------------


def test_bezahlt_button_ist_erst_nach_auswahl_einer_zeile_aktiv(qtbot, conn):
    _teilnehmer_anlegen(conn)
    tab = TeilnehmerTab(conn)
    qtbot.addWidget(tab)

    assert not tab.bezahlt_btn.isEnabled()
    tab.tabelle.selectRow(0)
    assert tab.bezahlt_btn.isEnabled()


def test_bezahlt_umschalten_per_klick_aendert_datenbank_und_tabelle(qtbot, conn):
    _teilnehmer_anlegen(conn)
    tab = TeilnehmerTab(conn)
    qtbot.addWidget(tab)
    tab.tabelle.selectRow(0)

    assert list_teilnehmer(conn)[0]["bezahlt"] == 0
    assert tab.tabelle.item(0, 6).text() == ""

    qtbot.mouseClick(tab.bezahlt_btn, Qt.MouseButton.LeftButton)

    assert list_teilnehmer(conn)[0]["bezahlt"] == 1
    assert "bezahlt" in tab.tabelle.item(0, 6).text()

    # Erneuter Klick schaltet wieder zurück (Toggle-Verhalten, nicht nur "setzen").
    qtbot.mouseClick(tab.bezahlt_btn, Qt.MouseButton.LeftButton)
    assert list_teilnehmer(conn)[0]["bezahlt"] == 0


def test_bezahlt_checkbox_im_teilnehmer_dialog(qtbot):
    dialog = TeilnehmerDialog(vergebene_nummern=set())
    qtbot.addWidget(dialog)
    dialog.nachname.setText("Muster")
    dialog.vorname.setText("Max")
    dialog.rufname_hund.setText("Bello")

    assert dialog.ergebnis().bezahlt is False
    qtbot.mouseClick(dialog.bezahlt, Qt.MouseButton.LeftButton)
    assert dialog.ergebnis().bezahlt is True


# --- Gegenstand-Disziplin-Zuordnung (frei wählbar, kein Default) --------------------


def test_gegenstand_ohne_zuordnung_bleibt_frei_kein_default(qtbot):
    dialog = TeilnehmerDialog(vergebene_nummern=set())
    qtbot.addWidget(dialog)
    dialog.nachname.setText("Muster")
    dialog.vorname.setText("Max")
    dialog.rufname_hund.setText("Bello")
    dialog.gegenstand_1.setText("Schlüsselbund")
    # Zuordnungs-Combobox bewusst UNVERÄNDERT lassen (bleibt auf "frei") - das ist der
    # vom Nutzer explizit geforderte Zustand ohne automatische Vorbelegung.

    ergebnis = dialog.ergebnis()
    assert ergebnis.gegenstand_1 == "Schlüsselbund"
    assert ergebnis.gegenstand_1_disziplin is None


def test_gegenstand_disziplin_frei_waehlbar_unabhaengig_von_position(qtbot):
    dialog = TeilnehmerDialog(vergebene_nummern=set())
    qtbot.addWidget(dialog)
    dialog.nachname.setText("Muster")
    dialog.vorname.setText("Max")
    dialog.rufname_hund.setText("Bello")
    dialog.gegenstand_2.setText("Korken")
    dialog.gegenstand_2_disziplin.setCurrentText("Trümmerfeld")

    ergebnis = dialog.ergebnis()
    assert ergebnis.gegenstand_2 == "Korken"
    assert ergebnis.gegenstand_2_disziplin == "Trümmerfeld"
    # Nicht explizit zugeordnete Gegenstände bleiben unabhängig davon "frei".
    assert ergebnis.gegenstand_1_disziplin is None
    assert ergebnis.gegenstand_3_disziplin is None


def test_bestehender_teilnehmer_im_dialog_zeigt_gespeicherte_zuordnung(qtbot, conn):
    _teilnehmer_anlegen(
        conn,
        gegenstand_1="Schlüsselbund",
        gegenstand_1_disziplin="Behältnisstrecke",
    )
    vorhandener = list_teilnehmer(conn)[0]

    dialog = TeilnehmerDialog(vorhandener=vorhandener)
    qtbot.addWidget(dialog)

    assert dialog.gegenstand_1.text() == "Schlüsselbund"
    assert dialog.gegenstand_1_disziplin.currentText() == "Behältnisstrecke"
    # Nicht belegte Gegenstände zeigen "frei", nicht irgendeine Disziplin.
    assert dialog.gegenstand_2_disziplin.currentText() == "frei"


# --- Hilfe-Button ---------------------------------------------------------------


def test_hilfe_button_ist_sichtbar_und_oeffnet_hilfedialog(qtbot, termin, monkeypatch):
    """Funktionaler Test für den Hilfe-Button: existiert im Fenster, ist sichtbar und
    öffnet beim Klick den HilfeDialog. Ergänzt (ersetzt aber nicht vollständig) den
    manuellen Test auf Windows - der ursprüngliche Bug (Button unsichtbar auf einer
    leeren QMenuBar) war an die native Windows-Menüleisten-Darstellung gekoppelt und
    lässt sich auf einem headless Linux-Runner nicht zuverlässig nachstellen. Die
    jetzige Umsetzung (Button in der normalen Kopfzeile statt Ecken-Widget einer
    Menüleiste) macht dieses spezielle Problem aber ohnehin strukturell unmöglich."""
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()

    hilfe_buttons = [b for b in fenster.findChildren(QPushButton) if b.text() == "❓ Hilfe"]
    assert len(hilfe_buttons) == 1
    hilfe_btn = hilfe_buttons[0]
    assert hilfe_btn.isVisible()
    assert hilfe_btn.height() > 0

    geoeffnet = {}
    monkeypatch.setattr(HilfeDialog, "exec", lambda self: geoeffnet.setdefault("ja", True))

    qtbot.mouseClick(hilfe_btn, Qt.MouseButton.LeftButton)

    assert geoeffnet.get("ja") is True


# --- Automatisches Speichern beim Beenden -------------------------------------------


def test_schliessen_speichert_automatisch_bei_ungespeicherten_aenderungen(qtbot, termin, monkeypatch):
    conn, pfad = termin
    set_veranstaltung(conn, verein="SGV Köppern e.V.", datum="2026-09-19")
    _teilnehmer_anlegen(conn)

    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)

    aufgerufen = {}
    monkeypatch.setattr(type(fenster.ergebnis_tab), "hat_ungespeicherte_aenderungen", lambda self: True)
    monkeypatch.setattr(
        type(fenster.ergebnis_tab), "alle_speichern", lambda self: aufgerufen.setdefault("gespeichert", True)
    )

    fenster.close()

    assert aufgerufen.get("gespeichert") is True


def test_schliessen_speichert_nicht_wenn_bereits_alles_gespeichert(qtbot, termin, monkeypatch):
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)

    aufgerufen = {}
    monkeypatch.setattr(type(fenster.ergebnis_tab), "hat_ungespeicherte_aenderungen", lambda self: False)
    monkeypatch.setattr(
        type(fenster.ergebnis_tab), "alle_speichern", lambda self: aufgerufen.setdefault("gespeichert", True)
    )

    fenster.close()

    assert "gespeichert" not in aufgerufen
