"""GUI-Tests: Reiter Ergebniserfassung (desktop_ergebnis.py).

Fixtures und Hilfen stehen in gui_hilfen.py (Aufteilung von test_app_gui.py, 11.11.2026)."""

from __future__ import annotations

import os
import sys
import pytest
from contextlib import closing
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton
from app import HauptFenster
from desktop_dialoge import TeilnehmerDialog
import desktop_ergebnis_speichern
import desktop_ergebnis_zellen
from desktop_ergebnis import ErgebnisTab
from desktop_gemeinsam import _ERGEBNIS_SPALTEN_JE_DISZIPLIN, _ergebnis_spaltenbreiten_verteilen
from db import (
    NeuerTeilnehmer,
    eintragen_ergebnis,
    get_ergebnis,
    init_db,
    pruefe_ergebnis_eingabe,
    set_veranstaltung,
    setze_ergebnis_status,
    setze_keine_teilnahme,
    update_teilnehmer,
)
from db import ALLE_DISZIPLINEN
from desktop_gemeinsam import _ABBRUCH_SPALTE, _DQ_SPALTE, _STATUS_SPALTE, symbol
from gui_hilfen import *  # noqa: F401,F403


def test_ergebnis_tab_laedt_nach_abgelehntem_speichern_neu_und_behaelt_eingaben(qtbot, termin, monkeypatch):
    # Befund aus der Verifikation (02.10.2026): beim Zurückwechseln mit abgelehntem
    # Speichern blieb ein inzwischen als "keine Teilnahme" markierter Teilnehmer stehen.
    conn, pfad = termin
    set_veranstaltung(conn, verein="SGV Köppern e.V.", datum="2026-09-19")
    _teilnehmer_anlegen(conn, nachname="Da", startnummer=1)
    fehlt = _teilnehmer_anlegen(conn, nachname="Fehlt", startnummer=2)

    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._tabs.setCurrentWidget(fenster.ergebnis_tab)
    ergebnis_tab = fenster.ergebnis_tab
    zeile_da = _ergebnis_zeile(ergebnis_tab, "Da")
    ergebnis_tab.punkte_eintragen(zeile_da, "Flächensuche", "50", "30")
    assert ergebnis_tab.hat_ungespeicherte_aenderungen()

    rueckfragen_beantworten(monkeypatch, QMessageBox.No)
    fenster._tabs.setCurrentWidget(fenster.teilnehmer_tab)
    setze_keine_teilnahme(conn, fehlt, True)
    fenster._tabs.setCurrentWidget(ergebnis_tab)

    assert _ergebnis_nachnamen(ergebnis_tab) == ["Da"]
    assert ergebnis_tab.punkte(0, "Flächensuche") == ("50", "30")
    assert ergebnis_tab.hat_ungespeicherte_aenderungen()


def test_ergebnis_tab_neuladen_ueberschreibt_zwischenzeitliche_ergebnisse_nicht(qtbot, termin, monkeypatch):
    # Befund Nachprüfung (02.10.2026): beim Neuladen mit erhaltenen Eingaben dürfen nur
    # wirklich geänderte Werte übernommen werden - sonst würde ein unberührter, veralteter
    # Anzeigewert ein inzwischen gespeichertes Ergebnis (z. B. aus dem Web zurückgeholt)
    # beim nächsten Speichern löschen.
    conn, pfad = termin
    set_veranstaltung(conn, verein="SGV Köppern e.V.", datum="2026-09-19")
    _teilnehmer_anlegen(conn, nachname="Bearbeitet", startnummer=1)
    unberuehrt = _teilnehmer_anlegen(conn, nachname="Unberuehrt", startnummer=2)
    dq = _teilnehmer_anlegen(conn, nachname="Dq", startnummer=3)

    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._tabs.setCurrentWidget(fenster.ergebnis_tab)
    ergebnis_tab = fenster.ergebnis_tab

    def zeile(nachname):
        return _ergebnis_zeile(ergebnis_tab, nachname)

    ergebnis_tab.punkte_eintragen(zeile("Bearbeitet"), "Flächensuche", "50", "30")
    ergebnis_tab.status_setzen(zeile("Dq"), dq=True)

    rueckfragen_beantworten(monkeypatch, QMessageBox.No)
    fenster._tabs.setCurrentWidget(fenster.teilnehmer_tab)
    # Inzwischen kommt für den unberührten Teilnehmer ein Ergebnis in die DB.
    eintragen_ergebnis(conn, unberuehrt, "Flächensuche", 55, 35)
    fenster._tabs.setCurrentWidget(ergebnis_tab)

    assert ergebnis_tab.punkte(zeile("Unberuehrt"), "Flächensuche") == ("55", "35")
    assert not ergebnis_tab.zeile_ungespeichert(zeile("Unberuehrt"))
    assert ergebnis_tab.zeile_ungespeichert(zeile("Bearbeitet"))
    assert ergebnis_tab.status(zeile("Dq"))[0]

    ergebnis_tab.alle_speichern()
    assert get_ergebnis(conn, unberuehrt)["suche_flaechensuche"] == 55
    assert get_ergebnis(conn, dq)["disqualifiziert"] == 1


def test_ergebnis_tab_sortieren_ueberschreibt_zwischenzeitliche_ergebnisse_nicht(qtbot, conn, monkeypatch):
    # Wie oben, aber über den Sortier-Pfad (Spaltenklick) statt über den Tabwechsel.
    hinweise = meldungen_sammeln(monkeypatch, "information")
    _teilnehmer_anlegen(conn, nachname="Bearbeitet", startnummer=1)
    unberuehrt = _teilnehmer_anlegen(conn, nachname="Unberuehrt", startnummer=2)
    tab = ErgebnisTab(conn)
    qtbot.addWidget(tab)
    tab.show()

    def zeile(nachname):
        return _ergebnis_zeile(tab, nachname)

    tab.punkte_eintragen(zeile("Bearbeitet"), "Flächensuche", "50", "30")
    eintragen_ergebnis(conn, unberuehrt, "Flächensuche", 55, 35)

    tab._spalte_geklickt(1)

    assert tab.punkte(zeile("Unberuehrt"), "Flächensuche") == ("55", "35")
    assert not tab.zeile_ungespeichert(zeile("Unberuehrt"))
    assert tab.punkte(zeile("Bearbeitet"), "Flächensuche") == ("50", "30")

    tab.alle_speichern()
    assert get_ergebnis(conn, unberuehrt)["suche_flaechensuche"] == 55
    assert hinweise == []


def test_ergebnis_tab_meldet_verworfene_eingabe_auch_beim_sortieren(qtbot, conn, monkeypatch):
    tid = _teilnehmer_anlegen(conn, nachname="Getippt", startnummer=7)
    tab = ErgebnisTab(conn)
    qtbot.addWidget(tab)
    tab.show()
    tab.punkte_eintragen(0, "Flächensuche", "50", "30")
    hinweise = meldungen_sammeln(monkeypatch, "information")
    setze_ergebnis_status(conn, tid, disqualifiziert=False, abbruch=True)

    tab._spalte_geklickt(1)

    assert len(hinweise) == 1
    assert "Nr. 7 – Getippt, Max" in hinweise[0]
    assert tab.status(0)[1]


def test_ergebnis_tab_kein_hinweis_bei_selbst_gesetztem_dq(qtbot, termin, monkeypatch):
    # Selbst (ungespeichert) angehakte DQ: keine Meldung, das Häkchen bleibt erhalten.
    conn, pfad = termin
    set_veranstaltung(conn, verein="SGV Köppern e.V.", datum="2026-09-19")
    tid = _teilnehmer_anlegen(conn, nachname="Selbst", startnummer=1)
    eintragen_ergebnis(conn, tid, "Flächensuche", 50, 30)

    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._tabs.setCurrentWidget(fenster.ergebnis_tab)
    ergebnis_tab = fenster.ergebnis_tab
    ergebnis_tab.status_setzen(0, dq=True)

    rueckfragen_beantworten(monkeypatch, QMessageBox.No)
    hinweise = meldungen_sammeln(monkeypatch, "information")
    fenster._tabs.setCurrentWidget(fenster.teilnehmer_tab)
    fenster._tabs.setCurrentWidget(ergebnis_tab)

    assert hinweise == []
    assert ergebnis_tab.status(0)[0]
    assert ergebnis_tab.hat_ungespeicherte_aenderungen()
    assert get_ergebnis(conn, tid)["suche_flaechensuche"] == 50


def test_ergebnis_tab_meldet_verworfene_eingabe_bei_zwischenzeitlichem_dq(qtbot, termin, monkeypatch):
    # Marco (02.10.2026): ungespeicherte Punkte, die wegen eines inzwischen gespeicherten
    # DQ/Abbruch verworfen werden, nicht stillschweigend verschwinden lassen.
    conn, pfad = termin
    set_veranstaltung(conn, verein="SGV Köppern e.V.", datum="2026-09-19")
    tid = _teilnehmer_anlegen(conn, nachname="Getippt", startnummer=1)

    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._tabs.setCurrentWidget(fenster.ergebnis_tab)
    ergebnis_tab = fenster.ergebnis_tab
    ergebnis_tab.punkte_eintragen(0, "Flächensuche", "50", "30")

    rueckfragen_beantworten(monkeypatch, QMessageBox.No)
    hinweise = meldungen_sammeln(monkeypatch, "information")
    fenster._tabs.setCurrentWidget(fenster.teilnehmer_tab)
    setze_ergebnis_status(conn, tid, disqualifiziert=True, abbruch=False)
    fenster._tabs.setCurrentWidget(ergebnis_tab)

    assert len(hinweise) == 1
    assert "Getippt, Max" in hinweise[0]
    assert ergebnis_tab.status(0)[0]
    assert not ergebnis_tab.hat_ungespeicherte_aenderungen()
    assert get_ergebnis(conn, tid)["suche_flaechensuche"] is None


def test_ergebnis_tab_tabwechsel_ohne_aenderung_baut_nicht_neu(qtbot, termin):
    # Lasttest 16.10.2026: der Neuaufbau kostet bei 1000 Teilnehmern rund 5 s.
    conn, pfad = termin
    _teilnehmer_anlegen(conn, nachname="Da", startnummer=1)
    fenster, ergebnis_tab = _fenster_auf_ergebnis_tab(qtbot, conn, pfad)
    aufbau_vorher = ergebnis_tab.aufbau_kennung

    _hin_und_zurueck(fenster)

    assert ergebnis_tab.aufbau_kennung == aufbau_vorher


def test_ergebnis_tab_tabwechsel_baut_nach_aenderung_neu(qtbot, termin):
    # Änderung über dieselbe Verbindung (z. B. ein anderer Reiter).
    conn, pfad = termin
    tid = _teilnehmer_anlegen(conn, nachname="Da", startnummer=1)
    fenster, ergebnis_tab = _fenster_auf_ergebnis_tab(qtbot, conn, pfad)

    fenster._tabs.setCurrentWidget(fenster.teilnehmer_tab)
    eintragen_ergebnis(conn, tid, "Flächensuche", 55, 35)
    fenster._tabs.setCurrentWidget(ergebnis_tab)

    assert ergebnis_tab.punkte(0, "Flächensuche") == ("55", "35")


def test_ergebnis_tab_tabwechsel_erkennt_aenderung_ueber_andere_verbindung(qtbot, termin):
    # Änderung über eine zweite Verbindung (z. B. eine zweite Programminstanz).
    conn, pfad = termin
    tid = _teilnehmer_anlegen(conn, nachname="Da", startnummer=1)
    fenster, ergebnis_tab = _fenster_auf_ergebnis_tab(qtbot, conn, pfad)

    fenster._tabs.setCurrentWidget(fenster.teilnehmer_tab)
    with closing(init_db(pfad)) as andere:
        eintragen_ergebnis(andere, tid, "Flächensuche", 44, 22)
    fenster._tabs.setCurrentWidget(ergebnis_tab)

    assert ergebnis_tab.punkte(0, "Flächensuche") == ("44", "22")


def test_ergebnis_tab_nach_eigenem_speichern_kein_neuaufbau(qtbot, termin):
    conn, pfad = termin
    tid = _teilnehmer_anlegen(conn, nachname="Da", startnummer=1)
    fenster, ergebnis_tab = _fenster_auf_ergebnis_tab(qtbot, conn, pfad)
    ergebnis_tab.punkte_eintragen(0, "Flächensuche", "50", "30")
    aufbau_vorher = ergebnis_tab.aufbau_kennung
    ergebnis_tab.alle_speichern()

    _hin_und_zurueck(fenster)

    assert ergebnis_tab.aufbau_kennung == aufbau_vorher
    assert not ergebnis_tab.hat_ungespeicherte_aenderungen()
    assert get_ergebnis(conn, tid)["suche_flaechensuche"] == 50


def test_ergebnis_tab_speichern_nach_fremder_aenderung_baut_beim_tabwechsel_neu(qtbot, termin):
    # Hat sich die DB vor dem Speichern anderweitig geändert, zeigt die Tabelle nach dem
    # Speichern nicht alles aktuell - der nächste Tabwechsel muss neu aufbauen.
    conn, pfad = termin
    _teilnehmer_anlegen(conn, nachname="Da", startnummer=1)
    fremd = _teilnehmer_anlegen(conn, nachname="Fremd", startnummer=2)
    fenster, ergebnis_tab = _fenster_auf_ergebnis_tab(qtbot, conn, pfad)

    def zeile(nachname):
        return _ergebnis_zeile(ergebnis_tab, nachname)

    ergebnis_tab.punkte_eintragen(zeile("Da"), "Flächensuche", "50", "30")
    eintragen_ergebnis(conn, fremd, "Flächensuche", 41, 21)
    ergebnis_tab.alle_speichern()

    _hin_und_zurueck(fenster)

    assert ergebnis_tab.punkte(zeile("Fremd"), "Flächensuche") == ("41", "21")


@pytest.mark.parametrize("sammeln_ab", [200, 1])
def test_ergebnis_tab_fremder_commit_waehrend_des_speicherns_baut_beim_tabwechsel_neu(
    qtbot, termin, monkeypatch, sammeln_ab
):
    """Restlücke vom 16.10.2026: Eine andere Verbindung (z. B. zweite Programminstanz)
    committet, während „Alle speichern“ läuft. Der eigene Stand darf dann nicht als aktuell
    gelten (data_version geändert) - der nächste Tabwechsel baut neu auf und zeigt die
    fremde Änderung. Soll-Verhalten laut Marco 18.10.2026: so wie heute, keine Meldung.
    Mit 200 einzeln committet, mit 1 in einer Transaktion (dort kann ein fremder Commit nur
    vor dem ersten eigenen Schreiben landen, sonst hielte die Datei die Sperre)."""
    conn, pfad = termin
    da = _teilnehmer_anlegen(conn, nachname="Da", startnummer=1)
    fremd = _teilnehmer_anlegen(conn, nachname="Fremd", startnummer=2)
    monkeypatch.setattr("desktop_ergebnis_speichern._SAMMELSPEICHERN_UEBER_TEILNEHMER", sammeln_ab)
    fenster, ergebnis_tab = _fenster_auf_ergebnis_tab(qtbot, conn, pfad)

    def zeile(nachname):
        return _ergebnis_zeile(ergebnis_tab, nachname)

    ergebnis_tab.punkte_eintragen(zeile("Da"), "Flächensuche", "50", "30")
    aufbau_vorher = ergebnis_tab.aufbau_kennung
    echt = desktop_ergebnis_speichern.eintragen_ergebnis
    with closing(init_db(pfad)) as andere:

        def mit_fremdem_commit(conn_, tid, *a, **k):
            # Erst die andere Verbindung, dann das eigene Schreiben - nach stand_vorher.
            if tid == da:
                eintragen_ergebnis(andere, fremd, "Flächensuche", 41, 21)
            echt(conn_, tid, *a, **k)

        monkeypatch.setattr("desktop_ergebnis_speichern.eintragen_ergebnis", mit_fremdem_commit)
        ergebnis_tab.alle_speichern()

    assert get_ergebnis(conn, da)["suche_flaechensuche"] == 50
    assert not ergebnis_tab.hat_ungespeicherte_aenderungen()
    _hin_und_zurueck(fenster)

    assert ergebnis_tab.aufbau_kennung != aufbau_vorher  # neu aufgebaut
    assert ergebnis_tab.punkte(zeile("Fremd"), "Flächensuche") == ("41", "21")
    assert ergebnis_tab.punkte(zeile("Da"), "Flächensuche") == ("50", "30")


def test_ergebnis_tab_speichern_bei_gesperrter_datei_bleibt_im_fehlerweg(qtbot, termin, monkeypatch):
    # Verifikation 16.10.2026: die Abfrage des Datenstands darf den Fehlerweg von
    # alle_speichern (Desktop-Prüfung Teil 3 Nr. 1) nicht umgehen.
    conn, pfad = termin
    _teilnehmer_anlegen(conn, nachname="Da", startnummer=1)
    fenster, ergebnis_tab = _fenster_auf_ergebnis_tab(qtbot, conn, pfad)
    meldungen = []
    ueberall_ersetzen(monkeypatch, "_db_fehler_anzeigen", lambda *a, **k: meldungen.append(a[1]))
    conn.execute("PRAGMA busy_timeout = 0")

    with closing(init_db(pfad)) as andere:
        andere.execute("BEGIN EXCLUSIVE")
        ergebnis_tab.alle_speichern()  # ohne Änderungen: darf nicht werfen
        ergebnis_tab.punkte_eintragen(0, "Flächensuche", "50", "30")
        ergebnis_tab.alle_speichern()
        andere.rollback()

    assert len(meldungen) == 1
    assert ergebnis_tab.hat_ungespeicherte_aenderungen()


def test_ergebnis_tab_nach_speichern_mit_ergebnissortierung_baut_neu(qtbot, termin):
    # Sortierung nach einer Ergebnisspalte wendet erst ein Neuaufbau neu an - wie vorher.
    conn, pfad = termin
    _teilnehmer_anlegen(conn, nachname="Da", startnummer=1)
    fenster, ergebnis_tab = _fenster_auf_ergebnis_tab(qtbot, conn, pfad)
    ergebnis_tab._spalte_geklickt(_STATUS_SPALTE)
    ergebnis_tab.punkte_eintragen(0, "Flächensuche", "50", "30")
    ergebnis_tab.alle_speichern()
    aufbau_vorher = ergebnis_tab.aufbau_kennung

    _hin_und_zurueck(fenster)

    assert ergebnis_tab.aufbau_kennung != aufbau_vorher


def test_ergebnis_tab_tabwechsel_ohne_neuaufbau_blendet_hinweise_aus(qtbot, termin):
    conn, pfad = termin
    _teilnehmer_anlegen(conn, nachname="Da", startnummer=1)
    fenster, ergebnis_tab = _fenster_auf_ergebnis_tab(qtbot, conn, pfad)
    qtbot.keyClicks(ergebnis_tab.zelle_bearbeiten(0, "Flächensuche", "suche"), ",")
    assert not ergebnis_tab.hinweis_label.isHidden()

    _hin_und_zurueck(fenster)

    assert ergebnis_tab.hinweis_label.isHidden()


def test_alle_speichern_bis_200_teilnehmer_behaelt_gespeicherte_zeilen(qtbot, termin, monkeypatch):
    # Bisheriges Verhalten (Desktop-Prüfung Teil 3 Nr. 1): Commit je Ergebnis.
    conn, ergebnis_tab, erster, meldungen = _zwei_eingaben_mit_fehler_beim_zweiten(
        qtbot, termin, monkeypatch, sammeln_ab=200
    )

    assert get_ergebnis(conn, erster)["suche_flaechensuche"] == 50
    assert not ergebnis_tab.zeile_ungespeichert(0)
    assert ergebnis_tab.zeile_ungespeichert(1)
    assert "Bereits gespeicherte Zeilen bleiben erhalten" in meldungen[0]
    # UX-Test 2026-11, R-B1 (c): gezählt wird nur der Teilnehmer vor dem Fehler.
    assert ergebnis_tab.status_label.text() == (
        "Speichern abgebrochen – 1 Teilnehmer gespeichert, die übrigen nicht."
    )


def test_alle_speichern_ueber_schwelle_speichert_bei_fehler_nichts(qtbot, termin, monkeypatch):
    # Lasttest 16.10.2026: oberhalb der Schwelle eine Transaktion - ganz oder gar nicht.
    conn, ergebnis_tab, erster, meldungen = _zwei_eingaben_mit_fehler_beim_zweiten(
        qtbot, termin, monkeypatch, sammeln_ab=1
    )

    assert get_ergebnis(conn, erster)["suche_flaechensuche"] is None
    assert not conn.in_transaction
    assert ergebnis_tab.zeile_ungespeichert(0)
    assert ergebnis_tab.zeile_ungespeichert(1)
    assert "Es wurde nichts gespeichert" in meldungen[0]
    assert ergebnis_tab.status_label.text() == "Speichern abgebrochen – nichts gespeichert."


def test_alle_speichern_ueber_schwelle_speichert_alles_in_einer_transaktion(qtbot, termin, monkeypatch):
    conn, pfad = termin
    erster = _teilnehmer_anlegen(conn, nachname="Erster", startnummer=1)
    zweiter = _teilnehmer_anlegen(conn, nachname="Zweiter", startnummer=2)
    monkeypatch.setattr("desktop_ergebnis_speichern._SAMMELSPEICHERN_UEBER_TEILNEHMER", 1)
    fenster, ergebnis_tab = _fenster_auf_ergebnis_tab(qtbot, conn, pfad)
    for zeile, (suche, anzeige) in enumerate([("50", "30"), ("44", "22")]):
        ergebnis_tab.punkte_eintragen(zeile, "Flächensuche", suche, anzeige)
    ergebnis_tab.status_setzen(1, abbruch=True)  # Abbruch beim Zweiten
    commits = []
    monkeypatch.setattr("desktop_ergebnis_speichern.setze_ergebnis_status", _commit_zaehlen(commits, setze_ergebnis_status))
    monkeypatch.setattr("desktop_ergebnis_speichern.eintragen_ergebnis", _commit_zaehlen(commits, eintragen_ergebnis))

    ergebnis_tab.alle_speichern()

    assert commits == [False, False]
    assert not conn.in_transaction
    with closing(init_db(pfad)) as andere:
        assert get_ergebnis(andere, erster)["suche_flaechensuche"] == 50
        assert get_ergebnis(andere, zweiter)["abbruch"] == 1
    assert not ergebnis_tab.hat_ungespeicherte_aenderungen()


def test_alle_speichern_ueber_schwelle_laesst_bei_unerwartetem_fehler_keine_transaktion_offen(
    qtbot, termin, monkeypatch
):
    # Verifikation 16.10.2026: auch eine Ausnahme ohne Datenbankbezug darf keine halbe
    # Transaktion hinterlassen, die der nächste Commit einer anderen Aktion festschreibt.
    conn, pfad = termin
    erster = _teilnehmer_anlegen(conn, nachname="Erster", startnummer=1)
    _teilnehmer_anlegen(conn, nachname="Zweiter", startnummer=2)
    monkeypatch.setattr("desktop_ergebnis_speichern._SAMMELSPEICHERN_UEBER_TEILNEHMER", 1)
    rueckfragen_beantworten(monkeypatch, QMessageBox.No)
    fenster, ergebnis_tab = _fenster_auf_ergebnis_tab(qtbot, conn, pfad)
    for zeile in range(2):
        ergebnis_tab.punkte_eintragen(zeile, "Flächensuche", "50", "30")
    aufrufe = []
    echt = ergebnis_tab._aktualisiere_zeilenstatus

    def zweite_zeile_scheitert(row):
        aufrufe.append(row)
        if len(aufrufe) == 2:
            raise RuntimeError("unerwartet")
        echt(row)

    monkeypatch.setattr(ergebnis_tab, "_aktualisiere_zeilenstatus", zweite_zeile_scheitert)

    with pytest.raises(RuntimeError):
        ergebnis_tab.alle_speichern()

    assert not conn.in_transaction
    assert get_ergebnis(conn, erster)["suche_flaechensuche"] is None
    monkeypatch.setattr(ergebnis_tab, "_aktualisiere_zeilenstatus", echt)
    assert ergebnis_tab.zeile_ungespeichert(0)


def test_alle_speichern_ueber_schwelle_bricht_bei_integrity_error_ganz_ab(qtbot, termin, monkeypatch):
    # Verifikation 16.10.2026: ein IntegrityError (hier der echte CHECK der Datenbank) rollt
    # im Sammelmodus über db._mit_rollback alles zurück - die Meldung nennt den Teilnehmer.
    conn, pfad = termin
    erster = _teilnehmer_anlegen(conn, nachname="Erster", startnummer=1)
    zweiter = _teilnehmer_anlegen(conn, nachname="Zweiter", startnummer=2)
    monkeypatch.setattr("desktop_ergebnis_speichern._SAMMELSPEICHERN_UEBER_TEILNEHMER", 1)
    rueckfragen_beantworten(monkeypatch, QMessageBox.No)
    fenster, ergebnis_tab = _fenster_auf_ergebnis_tab(qtbot, conn, pfad)
    for zeile in range(2):
        ergebnis_tab.punkte_eintragen(zeile, "Flächensuche", "50", "30")
    echt = desktop_ergebnis_speichern.eintragen_ergebnis

    def zweiter_verletzt_check(conn_, tid, disziplin, suche, anzeige, **k):
        echt(conn_, tid, disziplin, 99 if tid == zweiter else suche, anzeige, **k)

    meldungen = []
    monkeypatch.setattr("desktop_ergebnis_speichern.eintragen_ergebnis", zweiter_verletzt_check)
    ueberall_ersetzen(monkeypatch, "_db_fehler_anzeigen", lambda parent, exc, einleitung: meldungen.append(einleitung))

    ergebnis_tab.alle_speichern()

    assert get_ergebnis(conn, erster)["suche_flaechensuche"] is None
    assert not conn.in_transaction
    assert ergebnis_tab.zeile_ungespeichert(0)
    assert ergebnis_tab.zeile_ungespeichert(1)
    assert "Es wurde nichts gespeichert" in meldungen[0]
    assert "Zweiter, Max – Flächensuche" in meldungen[0]


def test_gesperrte_disziplin_ist_in_der_auswahlliste_sichtbar_abgesetzt(qtbot):
    """Marco 10.11.2026: mit dem Stylesheet sah man gesperrte Einträge nicht - sie müssen in der
    geöffneten Liste blasser (Farbe) und kursiv gezeichnet werden."""
    dialog = TeilnehmerDialog(vergebene_nummern=set())
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.art.setCurrentText("DK")
    dialog.gegenstand_1_disziplin.setCurrentText("Trümmerfeld")
    combo = dialog.gegenstand_2_disziplin
    modell = combo.model()
    gesperrt = modell.item(combo.findText("Trümmerfeld"))
    frei = modell.item(combo.findText("Flächensuche"))
    assert gesperrt.foreground().style() != Qt.NoBrush and frei.foreground().style() == Qt.NoBrush
    assert gesperrt.font().italic() and not frei.font().italic()
    assert gesperrt.toolTip() and not frei.toolTip()
    # Wird die Sperre aufgehoben, verschwindet auch die Darstellung wieder.
    dialog.gegenstand_1_disziplin.setCurrentText("frei")
    entsperrt = modell.item(combo.findText("Trümmerfeld"))
    assert entsperrt.foreground().style() == Qt.NoBrush and not entsperrt.font().italic()


# --- Ergebniserfassung: Ergebnis wieder löschen (beide Felder leeren) --------------
# Regressionstest für den gemeldeten Fehler: ein bereits gespeichertes Ergebnis ließ
# sich nicht mehr löschen - "Alle Ergebnisse speichern" tat beim Leeren beider Felder
# einer Zeile nichts (weder DB-Update noch Statuswechsel), die Zeile blieb dauerhaft
# gelb "nicht gespeichert" markiert, egal wie oft gespeichert wurde.


def test_ergebnis_loeschen_durch_leeren_beider_felder_wird_gespeichert(qtbot, termin):
    conn, pfad = termin
    tid = _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    eintragen_ergebnis(conn, tid, "Flächensuche", suche=45, anzeige=28)

    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()

    ergebnis_tab = fenster.ergebnis_tab
    assert ergebnis_tab.punkte(0, "Flächensuche") == ("45", "28")

    ergebnis_tab.punkte_eintragen(0, "Flächensuche", "", "")
    assert ergebnis_tab.zeile_ungespeichert(0)

    speichern_btn = next(
        b for b in fenster.findChildren(QPushButton) if b.text() == "Alle Ergebnisse speichern"
    )
    qtbot.mouseClick(speichern_btn, Qt.MouseButton.LeftButton)

    # In der DB wirklich gelöscht (NULL), nicht nur optisch leer in der Tabelle.
    zeile = conn.execute(
        "SELECT suche_flaechensuche, anzeige_flaechensuche FROM ergebnisse WHERE teilnehmer_id = ?", (tid,)
    ).fetchone()
    assert zeile["suche_flaechensuche"] is None
    assert zeile["anzeige_flaechensuche"] is None

    # Zeile gilt jetzt als gespeichert (nicht mehr dauerhaft gelb markiert) und der
    # Status-Text bestätigt das Speichern statt "Keine Änderungen zu speichern".
    assert not ergebnis_tab.zeile_ungespeichert(0)
    assert "gespeichert" in ergebnis_tab.status_label.text().lower()
    assert "keine änderungen" not in ergebnis_tab.status_label.text().lower()


def test_ergebnis_nur_ein_feld_geleert_zeigt_fehlermeldung_statt_stillem_datenverlust(qtbot, termin, monkeypatch):
    """Wird nur eines der beiden Felder geleert (statt beider), bleibt das weiterhin ein
    Fehler ("bitte sowohl Suche als auch Anzeige eintragen") statt stillschweigend
    gespeichert zu werden - ein einzelner Wert allein wäre kein gültiges Ergebnis."""
    conn, pfad = termin
    tid = _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    eintragen_ergebnis(conn, tid, "Flächensuche", suche=45, anzeige=28)

    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()

    ergebnis_tab = fenster.ergebnis_tab
    ergebnis_tab.punkte_eintragen(0, "Flächensuche", suche="")

    warnung_gezeigt = {}

    def _warnung(*args, **kwargs):
        warnung_gezeigt["ja"] = True
        warnung_gezeigt["text"] = args[2]

    monkeypatch.setattr("app.QMessageBox.warning", _warnung)

    speichern_btn = next(
        b for b in fenster.findChildren(QPushButton) if b.text() == "Alle Ergebnisse speichern"
    )
    qtbot.mouseClick(speichern_btn, Qt.MouseButton.LeftButton)

    assert warnung_gezeigt.get("ja") is True
    # Codeprüfung 22.09., G6: Meldung kommt aus der gemeinsamen Regel db.pruefe_ergebnis_eingabe
    # (dieselbe wie im Web-Frontend), weiterhin mit Name und Disziplin der betroffenen Zeile.
    assert "Muster, Max – Flächensuche: " + pruefe_ergebnis_eingabe(None, 28) in warnung_gezeigt["text"]
    # Der alte Wert bleibt in der DB unverändert (Anzeige-Feld war ja noch gültig
    # gefüllt, aber ohne Gegenstück nicht speicherbar).
    zeile = conn.execute(
        "SELECT suche_flaechensuche, anzeige_flaechensuche FROM ergebnisse WHERE teilnehmer_id = ?", (tid,)
    ).fetchone()
    assert zeile["suche_flaechensuche"] == 45
    assert zeile["anzeige_flaechensuche"] == 28


# --- Ergebniserfassung: Responsive Spaltenbreiten/Schriftgröße ----------------------
# Nutzerwunsch (22.09.): die Tabelle ist inzwischen so breit (13 Spalten), dass sie je nach
# Bildschirmgröße nicht auf einen Blick sichtbar ist, sondern nach rechts gescrollt werden
# muss - Schriftgröße und Spaltenbreiten sollen sich so an die Fensterbreite anpassen, dass
# bei maximiertem Fenster kein horizontales Scrollen mehr nötig ist (siehe
# _spaltenbreiten_anpassen/_ergebnis_spaltenbreiten_verteilen).


def test_ergebnis_spaltenbreiten_keine_stauchung_wenn_platz_reicht():
    natuerlich = [80, 200, 120]
    minima = [56, 56, 56]
    ziel = _ergebnis_spaltenbreiten_verteilen(natuerlich, minima, 1000)
    assert ziel == natuerlich


def test_ergebnis_spaltenbreiten_stauchen_proportional_bei_ueberlauf():
    natuerlich = [100, 200, 300]
    minima = [10, 10, 10]
    ziel = _ergebnis_spaltenbreiten_verteilen(natuerlich, minima, 300)
    assert sum(ziel) <= 300
    # Verhältnis bleibt erhalten (ungefähr, wegen Rundung): doppelt/dreifach so breit wie
    # die erste Spalte bleibt auch nach dem Stauchen doppelt/dreifach so breit.
    assert ziel[1] == pytest.approx(2 * ziel[0], abs=1)
    assert ziel[2] == pytest.approx(3 * ziel[0], abs=1)


def test_ergebnis_spaltenbreiten_respektiert_minimum_auch_bei_extremem_ueberlauf():
    natuerlich = [100, 200, 300]
    minima = [80, 150, 250]
    ziel = _ergebnis_spaltenbreiten_verteilen(natuerlich, minima, 100)
    # Bei so wenig Platz reicht selbst das Stauchen auf die Minima nicht aus - die Minima
    # werden trotzdem nicht unterschritten, ein Scrollbalken ist dann der akzeptierte
    # Fallback (kein Fehler).
    assert ziel == minima


def test_ergebnis_spaltenbreiten_spalten_mit_minimum_gleich_natuerlich_schrumpfen_nicht():
    """QS-Fund (22.09., Verifikations-Subagent): eine Spalte, deren Minimum bereits ihrer
    natürlichen Breite entspricht (z.B. Start-Nr./Name/Hund/Art-LK - reiner Text, der nicht
    schrumpfen soll), darf trotzdem NICHT mit ihrer vollen natürlichen Breite in die globale
    Stauchungsfaktor-Berechnung einfließen - sonst bekommen die tatsächlich schrumpfbaren
    Spalten (Punkte/Checkbox) zu wenig abgezogen und die Summe überschreitet weiterhin die
    verfügbare Breite (hier ursprünglich gefunden: die reservierte Mindestbreite der
    gestreckten Status-Spalte wurde dadurch nicht zuverlässig eingehalten)."""
    natuerlich = [200, 100, 100]
    minima = [200, 20, 20]  # Spalte 0: Minimum == natürliche Breite, schrumpft nie
    ziel = _ergebnis_spaltenbreiten_verteilen(natuerlich, minima, 250)
    assert ziel[0] == 200
    assert sum(ziel) <= 250
    assert ziel[1] == ziel[2]  # gleiche natürliche Breite -> gleich behandelt


def test_ergebnis_spaltenbreiten_rundung_ueberschreitet_budget_nicht():
    """Regressionstest für den CI-Fehlschlag von
    test_ergebnis_tabelle_passt_bei_typischer_maximierter_breite_ohne_scrollbalken (22.09.):
    round() je Spalte kann die Summe der Zielbreiten über verfuegbare_breite hinausschieben,
    wenn keine offene Spalte dabei ihr Minimum erreicht (hier: 2.7 rundet je Spalte auf 3,
    keine der 10 Spalten hat mit Minimum 0 einen Grund zu fixieren)."""
    natuerlich = [3] * 10
    minima = [0] * 10
    ziel = _ergebnis_spaltenbreiten_verteilen(natuerlich, minima, 27)
    assert sum(ziel) <= 27
    assert all(w >= 0 for w in ziel)


def test_ergebnis_spaltenbreiten_ohne_harte_minima_bleibt_scrollbalken_fallback():
    """Ohne harte_minima (Standardfall, `None`) bleibt das Verhalten exakt wie vorher: reicht
    selbst minimum_breiten nicht aus, sind die Minima das Ergebnis - ein Scrollbalken bleibt
    der akzeptierte Fallback."""
    natuerlich = [100, 100]
    minima = [90, 90]
    ziel = _ergebnis_spaltenbreiten_verteilen(natuerlich, minima, 178)
    assert ziel == minima


def test_ergebnis_spaltenbreiten_faellt_bei_knappem_minimum_auf_harte_minima_zurueck():
    """Regressionstest für die CI-Regression (22.09.), die nach dem obigen Rundungsfix
    weiter auftrat: auf CI/Linux fielen Schriftmetriken ein paar Pixel breiter aus als
    lokal unter Windows, sodass selbst minimum_breiten (headertext-basiert) bei 1300px knapp
    nicht mehr reichte. Reichen die weichen Minima (minimum_breiten) nicht aus, aber die
    übergebenen harte_minima (inhaltsbasiert, ohne Kopfzeilen-Padding-Reserve) schon, wird
    darauf zurückgefallen statt sofort auf den Scrollbalken-Fallback."""
    natuerlich = [100, 100]
    minima = [90, 90]  # weiche Minima: Summe 180 > verfügbare Breite 178 - reicht knapp nicht
    harte_minima = [70, 70]  # inhaltsbasierte Minima: Summe 140 <= 178
    ziel = _ergebnis_spaltenbreiten_verteilen(natuerlich, minima, 178, harte_minima)
    assert sum(ziel) <= 178
    assert all(w >= 70 for w in ziel)


def test_ergebnis_spaltenbreiten_harte_minima_reicht_ebenfalls_nicht_bleibt_bei_harte_minima():
    """Reicht selbst harte_minima nicht aus (extrem schmales Fenster), bleiben die
    harte_minima das Ergebnis - der Scrollbalken-Fallback greift dann trotzdem, aber nicht
    schlimmer als ohne harte_minima."""
    natuerlich = [100, 100]
    minima = [90, 90]
    harte_minima = [70, 70]
    ziel = _ergebnis_spaltenbreiten_verteilen(natuerlich, minima, 100, harte_minima)
    assert ziel == harte_minima


def test_ergebnis_tabelle_passt_bei_typischer_maximierter_breite_ohne_scrollbalken(qtbot, conn):
    _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    tab = ErgebnisTab(conn)
    qtbot.addWidget(tab)
    tab.resize(1300, 800)
    tab.show()
    qtbot.waitExposed(tab)

    assert tab.tabelle.horizontalScrollBar().maximum() == 0


def test_ergebnis_tabelle_status_spalte_fuellt_breite_auch_nach_neuaufbau():
    """Marco 09.10.2026: Bei breitem Fenster bekommt die Status-Spalte den Restplatz - auch
    nach einem Neuaufbau ohne Größenänderung (Speichern, "Liste aktualisieren"). Vorher
    blieb rechts eine graue Lücke, bis man das Fenster in der Größe änderte. Läuft in einem
    eigenen Prozess, weil der Fehler nur mit echten Windows-Schriftmaßen auftrat: Der Import
    von tools/screenshots setzt QT_QPA_FONTDIR auf den Windows-Schriftenordner, und Qt lädt
    Schriften erst bei Bedarf. Ohne diesen Ordner (z. B. Linux-CI) tritt der Fehler nicht
    auf; die Prüfungen laufen trotzdem."""
    import subprocess

    repo = os.path.dirname(os.path.abspath(__file__))
    lauf = subprocess.run(
        [sys.executable, "-c", _STATUS_SPALTE_PRUEFUNG], cwd=repo,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": repo}, timeout=120,
    )
    assert lauf.returncode == 0, lauf.stderr[-3000:]
    summe, viewport, status, inhalt = map(int, lauf.stdout.split()[-4:])
    assert summe >= viewport, (summe, viewport)
    assert status > inhalt


def test_ergebnis_tabelle_schrumpft_punktespalten_nicht_unter_minimum_bei_schmalem_fenster(qtbot, conn):
    _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    tab = ErgebnisTab(conn)
    qtbot.addWidget(tab)
    tab.resize(700, 800)
    tab.show()
    qtbot.waitExposed(tab)

    suche_spalte, _anzeige_spalte = _ERGEBNIS_SPALTEN_JE_DISZIPLIN["Flächensuche"]
    # Bei dieser Breite ist ein Scrollbalken erwartet/akzeptabel - hier wird nur geprüft,
    # dass die Punkte-Eingabespalte dabei nicht unter ihr Minimum schrumpft.
    assert tab.tabelle.columnWidth(suche_spalte) >= 56


# Hinweis: dass Spalten bei genügend Platz NICHT über ihre natürliche Breite hinaus
# aufgebläht werden (Restplatz geht stattdessen an die gestreckte Status-Spalte), ist
# bereits durch test_ergebnis_spaltenbreiten_keine_stauchung_wenn_platz_reicht oben auf
# reiner Funktionsebene abgedeckt.
#
# Nutzerwunsch (22.09.): die Kopfzeilen dieser Tabelle (z.B. "Flächensuche – Suche
# (0-60)") wurden früher bei schmalem Fenster über ihr Spaltenminimum hinaus
# zusammengedrückt und dabei abgeschnitten dargestellt, weil das Spaltenminimum nur am
# Zelleninhalt ("88" bzw. fix 44px), nicht am Headertext bemessen war. Behoben durch:
# zweizeilige Headertexte je Disziplin-Spalte (get "\n" statt " – " als Trenner - Qt
# rendert das von sich aus mehrzeilig, siehe ErgebnisTab.__init__) und
# _spaltenbreiten_anpassen bemisst das Spaltenminimum jetzt zusätzlich an der breitesten
# Headerzeile (siehe header_zeilen_breite() dort). Ein eigener GUI-Test dafür bräuchte
# Pixel-genaue Text-/Schriftmetrik-Annahmen und wäre kaum wartbar - die Kernlogik
# (Minimum je Spalte) bleibt bewusst nur über die bestehenden Funktionstests von
# _ergebnis_spaltenbreiten_verteilen abgedeckt.


# --- Ergebniserfassung: Sortierung per Spaltenklick ---------------------------------
# Nutzerwunsch (21.09., Rückmeldung "klappt gut, ggf. hier auch Sortierungsfunktion").
# WICHTIG anders als bei TeilnehmerTab (siehe unten): die Zeilenlisten von ErgebnisTab
# (Teilnehmer, geladene Werte …) hängen an der Zeilennummer - Qts eigene
# sortItems()-Sortierung würde nur die Zellen verschieben und Eingaben von der falschen
# Zeile trennen. ErgebnisTab verwendet deshalb eine eigene Sortierlogik
# (_spalte_geklickt, hier über das sectionClicked-Signal wie bei einem echten Klick auf
# die Spaltenüberschrift ausgelöst), die hier gezielt getestet wird - insbesondere, dass
# dabei keine ungespeicherte Eingabe verloren geht.


def test_ergebnis_spaltenklick_sortiert_nach_name(qtbot, conn):
    _teilnehmer_anlegen(conn, nachname="Zorn", startnummer=1, disziplin="Flächensuche")
    _teilnehmer_anlegen(conn, nachname="Adler", startnummer=2, disziplin="Flächensuche")
    tab = ErgebnisTab(conn)
    qtbot.addWidget(tab)
    tab.show()

    tab.tabelle.horizontalHeader().sectionClicked.emit(1)  # Spalte 1 = Name

    assert tab.tabelle.item(0, 1).text() == "Adler, Max"
    assert tab.tabelle.item(1, 1).text() == "Zorn, Max"

    # Erneuter Klick auf dieselbe Spalte kehrt die Richtung um.
    tab.tabelle.horizontalHeader().sectionClicked.emit(1)
    assert tab.tabelle.item(0, 1).text() == "Zorn, Max"
    assert tab.tabelle.item(1, 1).text() == "Adler, Max"


def test_ergebnis_zeigt_hund_und_sortiert_danach(qtbot, conn):
    """Nutzerwunsch: eigene Spalte "Hund" zwischen "Name" und "Art/LK", befüllt mit
    rufname_hund - hier sowohl die Anzeige als auch die Sortierbarkeit geprüft (analog zu
    test_ergebnis_spaltenklick_sortiert_nach_name für die Name-Spalte)."""
    _teilnehmer_anlegen(conn, nachname="Zorn", startnummer=1, rufname_hund="Zeus", disziplin="Flächensuche")
    _teilnehmer_anlegen(conn, nachname="Adler", startnummer=2, rufname_hund="Bello", disziplin="Flächensuche")
    tab = ErgebnisTab(conn)
    qtbot.addWidget(tab)
    tab.show()

    # Vor jeder Sortierung: Spalte 2 zeigt den jeweiligen Hundenamen, Spalte 3 die Art/LK.
    assert tab.tabelle.item(0, 2).text() == "Zeus"
    assert tab.tabelle.item(1, 2).text() == "Bello"
    assert tab.tabelle.item(0, 3).text() == "Fläche LK 1"
    assert tab.tabelle.item(1, 3).text() == "Fläche LK 1"

    tab.tabelle.horizontalHeader().sectionClicked.emit(2)  # Spalte 2 = Hund

    assert tab.tabelle.item(0, 2).text() == "Bello"
    assert tab.tabelle.item(1, 2).text() == "Zeus"

    # Erneuter Klick auf dieselbe Spalte kehrt die Richtung um.
    tab.tabelle.horizontalHeader().sectionClicked.emit(2)
    assert tab.tabelle.item(0, 2).text() == "Zeus"
    assert tab.tabelle.item(1, 2).text() == "Bello"


def test_ergebnis_umstellung_dk_auf_ed_sperrt_fremde_disziplinen(qtbot, conn):
    """Rückmeldung 23.09.: nach Umstellung eines DK-Teilnehmers auf ED blieben in der
    laufenden Sitzung die alten Eingabefelder der nicht mehr zutreffenden Disziplinen
    stehen (setItem() entfernt kein Cell-Widget), erst ein Neustart behob es."""
    teilnehmer_id = _teilnehmer_anlegen(conn, art="DK", stufe=1, disziplin=None)
    tab = ErgebnisTab(conn)
    qtbot.addWidget(tab)
    tab.show()

    update_teilnehmer(
        conn,
        teilnehmer_id,
        NeuerTeilnehmer(
            nachname="Muster", vorname="Max", rufname_hund="Bello",
            art="ED", stufe=1, disziplin="Flächensuche", startnummer=1,
        ),
    )
    tab.aktualisieren()

    _ed_zeile_hat_nur_eigene_eingabefelder(tab, 0, "Flächensuche")


def test_ergebnis_sortierung_laesst_keine_dk_eingabefelder_in_ed_zeile(qtbot, conn):
    """Wie oben, aber über den Sortierpfad: rutscht eine ED-Zeile auf die Position einer
    zuvor dort aufgebauten DK-Zeile, dürfen deren Eingabefelder nicht stehen bleiben."""
    _teilnehmer_anlegen(conn, nachname="Zorn", art="DK", stufe=1, disziplin=None, startnummer=1)
    _teilnehmer_anlegen(conn, nachname="Adler", disziplin="Flächensuche", startnummer=2)
    tab = ErgebnisTab(conn)
    qtbot.addWidget(tab)
    tab.show()
    assert tab.tabelle.item(0, 1).text() == "Zorn, Max"

    tab.tabelle.horizontalHeader().sectionClicked.emit(1)  # Spalte 1 = Name

    assert tab.tabelle.item(0, 1).text() == "Adler, Max"
    _ed_zeile_hat_nur_eigene_eingabefelder(tab, 0, "Flächensuche")


def test_ergebnis_sortierung_verliert_keine_ungespeicherte_eingabe(qtbot, conn):
    """Kern des technischen Fallstricks (siehe Modulkommentar oben): eine noch nicht
    gespeicherte Eingabe in einem Punkte-Feld darf beim Sortieren weder verloren gehen
    noch auf der falschen Zeile landen."""
    _teilnehmer_anlegen(conn, nachname="Zorn", startnummer=1, disziplin="Flächensuche")
    _teilnehmer_anlegen(conn, nachname="Adler", startnummer=2, disziplin="Flächensuche")
    tab = ErgebnisTab(conn)
    qtbot.addWidget(tab)
    tab.show()

    # Zorn (vor der Sortierung Zeile 0) bekommt eine noch nicht gespeicherte Eingabe.
    tab.punkte_eintragen(0, "Flächensuche", "58", "38")
    assert tab.zeile_ungespeichert(0)

    tab.tabelle.horizontalHeader().sectionClicked.emit(1)  # nach Name sortieren

    # Zorn steht jetzt in Zeile 1 (Adler < Zorn) - die Eingabe muss ihm gefolgt sein.
    assert tab.tabelle.item(0, 1).text() == "Adler, Max"
    assert tab.tabelle.item(1, 1).text() == "Zorn, Max"
    assert tab.punkte(1, "Flächensuche") == ("58", "38")
    assert tab.zeile_ungespeichert(1)
    # Adler (jetzt Zeile 0) hat weiterhin keine Eingabe.
    assert not tab.zeile_ungespeichert(0)

    # Die ungespeicherte Eingabe lässt sich nach der Sortierung ganz normal speichern.
    tab.alle_speichern()
    assert not tab.zeile_ungespeichert(1)


# --- Ergebniserfassung: Disqualifiziert/Abbruch ---------------------------------------
# Nutzerwunsch (21.09.): zwei unabhängige Checkboxen je Zeile, die bei Aktivierung die
# Punkte-Eingabefelder dieser Zeile sperren/leeren.


def test_ergebnis_disqualifiziert_sperrt_und_leert_punkteeingabe(qtbot, conn):
    _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    tab = ErgebnisTab(conn)
    qtbot.addWidget(tab)
    tab.show()

    tab.punkte_eintragen(0, "Flächensuche", "58", "38")

    tab.status_setzen(0, dq=True)

    assert tab.punkte(0, "Flächensuche") == ("", "")
    assert tab.zelle_gesperrt(0, "Flächensuche")

    # Wieder abwählen gibt die Felder wieder frei - befüllt sie dabei mit dem zuletzt aus
    # der DB geladenen Stand (hier leer, da die Eingabe oben nie gespeichert wurde; siehe
    # test_ergebnis_disqualifiziert_loescht_gespeicherte_punkte_nicht für den Fall mit
    # bereits gespeicherten Punkten).
    tab.status_setzen(0, dq=False)
    assert not tab.zelle_gesperrt(0, "Flächensuche")
    assert tab.punkte(0, "Flächensuche") == ("", "")


def test_ergebnis_disqualifiziert_und_abbruch_werden_unabhaengig_gespeichert(qtbot, conn):
    tid = _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    tab = ErgebnisTab(conn)
    qtbot.addWidget(tab)
    tab.show()

    tab.status_setzen(0, dq=True)
    assert tab.zeile_ungespeichert(0)

    tab.alle_speichern()

    ergebnis = get_ergebnis(conn, tid)
    assert ergebnis["disqualifiziert"] == 1
    assert ergebnis["abbruch"] == 0
    assert not tab.zeile_ungespeichert(0)

    # Nach dem "Liste aktualisieren" bleibt der gespeicherte Status sichtbar gesetzt.
    tab.aktualisieren()
    assert tab.status(0) == (True, False)


def test_ergebnis_disqualifiziert_bleibt_beim_sortieren_und_laedt_gesperrte_felder(qtbot, conn):
    # Kombiniert Sortierung und Status: eine (noch nicht gespeicherte) Disqualifiziert-
    # Markierung muss dieselbe Behandlung wie ungespeicherte Punktwerte erfahren -
    # sowohl der Checkbox-Zustand als auch die daraus folgende Felder-Sperre.
    _teilnehmer_anlegen(conn, nachname="Zorn", startnummer=1, disziplin="Flächensuche")
    _teilnehmer_anlegen(conn, nachname="Adler", startnummer=2, disziplin="Flächensuche")
    tab = ErgebnisTab(conn)
    qtbot.addWidget(tab)
    tab.show()

    tab.status_setzen(0, dq=True)  # Zorn, vor der Sortierung Zeile 0

    tab.tabelle.horizontalHeader().sectionClicked.emit(1)  # nach Name sortieren

    assert tab.tabelle.item(1, 1).text() == "Zorn, Max"
    assert tab.status(1)[0]
    assert tab.zelle_gesperrt(1, "Flächensuche")


def test_ergebnis_disqualifiziert_loescht_gespeicherte_punkte_nicht(qtbot, conn):
    # QS-Fund (Codeprüfung 21.09.): Punkte eintragen+speichern -> Disqualifiziert
    # ankreuzen+speichern -> Häkchen wieder entfernen durfte NICHT dazu führen, dass die
    # ursprünglichen Punkte aus der DB gelöscht werden (setze_ergebnis_status() dokumentiert
    # ausdrücklich, dass eine ggf. weiterhin in suche_*/anzeige_*-Spalten stehende Punktzahl
    # unangetastet bleibt - das wurde vorher durch alle_speichern() verletzt).
    tid = _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    tab = ErgebnisTab(conn)
    qtbot.addWidget(tab)
    tab.show()

    tab.punkte_eintragen(0, "Flächensuche", "58", "38")
    tab.alle_speichern()
    ergebnis = get_ergebnis(conn, tid)
    assert ergebnis["suche_flaechensuche"] == 58
    assert ergebnis["anzeige_flaechensuche"] == 38

    tab.status_setzen(0, dq=True)
    tab.alle_speichern()
    # Direkt nach dem Speichern einer gesperrten Zeile gilt sie als gespeichert - die
    # (leeren, gesperrten) Punktefelder dürfen die Zeile nicht dauerhaft als "nicht
    # gespeichert" markieren.
    assert not tab.zeile_ungespeichert(0)

    ergebnis = get_ergebnis(conn, tid)
    assert ergebnis["disqualifiziert"] == 1
    assert ergebnis["suche_flaechensuche"] == 58
    assert ergebnis["anzeige_flaechensuche"] == 38

    tab.status_setzen(0, dq=False)
    assert tab.punkte(0, "Flächensuche") == ("58", "38")

    # Erneutes Speichern OHNE weitere Eingabe darf die wiederhergestellten Werte nicht
    # versehentlich als "unverändert" verwerfen oder erneut löschen.
    tab.alle_speichern()
    ergebnis = get_ergebnis(conn, tid)
    assert ergebnis["disqualifiziert"] == 0
    assert ergebnis["suche_flaechensuche"] == 58
    assert ergebnis["anzeige_flaechensuche"] == 38


# --- Codeprüfung 22.09., G9: Sortierung der Ergebniserfassung übersteht "aktualisieren" --


def test_ergebnis_sortierung_bleibt_nach_aktualisieren_erhalten(qtbot, conn):
    _teilnehmer_anlegen(conn, nachname="Zorn", startnummer=1, disziplin="Flächensuche")
    _teilnehmer_anlegen(conn, nachname="Adler", startnummer=2, disziplin="Flächensuche")
    _teilnehmer_anlegen(conn, nachname="Meier", startnummer=3, disziplin="Flächensuche")
    tab = ErgebnisTab(conn)
    qtbot.addWidget(tab)
    tab.show()

    def namen():
        return [tab.tabelle.item(row, 1).text() for row in range(tab.tabelle.rowCount())]

    tab.tabelle.horizontalHeader().sectionClicked.emit(1)  # Name aufsteigend
    assert namen() == ["Adler, Max", "Meier, Max", "Zorn, Max"]

    tab.aktualisieren()
    assert namen() == ["Adler, Max", "Meier, Max", "Zorn, Max"]
    # Die Eingabefelder gehören nach dem erneuten Sortieren weiterhin zur richtigen Zeile.
    assert tab.teilnehmer_der_zeile(0)["nachname"] == "Adler"

    # Nächster Klick auf dieselbe Spalte kehrt die (tatsächlich sichtbare) Richtung um.
    tab.tabelle.horizontalHeader().sectionClicked.emit(1)
    assert namen() == ["Zorn, Max", "Meier, Max", "Adler, Max"]

    tab.aktualisieren()
    assert namen() == ["Zorn, Max", "Meier, Max", "Adler, Max"]


def test_ergebnistabelle_sehr_gross_nur_maximiert_voll(qtbot, termin, darstellung_speicher):
    """Marcos Entscheidung R6 (UX-Test 03.11.2026): bei „Sehr groß“ nutzt die Ergebnistabelle
    nicht maximiert nur Faktor 1,15, maximiert den vollen Faktor 1,3."""
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    # Der Offscreen-Bildschirm ist kleiner als das Testfenster - das Einpassen nach dem
    # Schriftwechsel (05.11.2026) würde es sonst verkleinern.
    fenster._an_bildschirm_anpassen = lambda: None
    fenster.resize(1400, 820)
    fenster.show()
    fenster._tabs.setCurrentWidget(fenster.ergebnis_tab)
    fenster._schrift_actions["normal"].trigger()
    tab = fenster.ergebnis_tab
    tab._spaltenbreiten_anpassen()
    normal_pt = tab._tabelle_pt

    fenster._schrift_actions["sehr_gross"].trigger()
    tab._spaltenbreiten_anpassen()
    assert tab._tabelle_pt == pytest.approx(normal_pt * 1.15, abs=0.15)

    echtes_is_maximized = fenster.isMaximized
    fenster.isMaximized = lambda: True  # offscreen-Maximieren ändert die Breite nicht verlässlich
    try:
        # Verifikation A3b/A5b, Befund 1: unter Windows kommt das resizeEvent vor dem
        # Zustandswechsel - erst der WindowStateChange darf neu rechnen.
        fenster.changeEvent(QEvent(QEvent.WindowStateChange))
        qtbot.waitUntil(lambda: tab._tabelle_pt == pytest.approx(normal_pt * 1.3, abs=0.15), timeout=2000)
    finally:
        fenster.isMaximized = echtes_is_maximized
        fenster._schrift_actions["normal"].trigger()


def test_strg_s_speichert_in_der_ergebniserfassung(qtbot, termin, monkeypatch):
    """UX-Test 02.10.2026, K11: Strg+S löst in der Ergebniserfassung "Alle Ergebnisse
    speichern" aus, solange der Fokus im Reiter liegt."""
    conn, pfad = termin
    set_veranstaltung(conn, verein="SGV Köppern e.V.", datum="2026-09-19")
    _teilnehmer_anlegen(conn)

    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    tab = fenster.ergebnis_tab
    fenster._tabs.setCurrentWidget(tab)

    aufrufe = []
    monkeypatch.setattr(type(tab), "alle_speichern", lambda self: aufrufe.append(True))

    # Verdrahtung unabhängig vom Fensterfokus (Verbesserungen V1, 19.10.2026): genau ein
    # Strg+S-Kürzel am Reiter, nur gültig, solange der Fokus in diesem Reiter liegt.
    kuerzel = [k for k in tab.findChildren(QShortcut) if k.key() == QKeySequence(QKeySequence.Save)]
    assert len(kuerzel) == 1
    assert kuerzel[0].context() == Qt.WidgetWithChildrenShortcut
    kuerzel[0].activated.emit()
    assert aufrufe == [True]
    aufrufe.clear()

    # Der echte Tastenweg geht nur, wenn das Fenster aktiv wird - mit echter Plattform hat
    # oft ein anderes Fenster den Fokus, dann bleibt es bei der Prüfung oben.
    fenster.activateWindow()
    tab.tabelle.setFocus()
    try:
        qtbot.waitUntil(lambda: fenster.isActiveWindow() and tab.tabelle.hasFocus(), timeout=2000)
    except qtbot.TimeoutError:
        if QApplication.platformName() == "offscreen":
            raise  # offscreen (CI) muss der echte Tastenweg immer gehen
        pytest.skip("Fenster wird nicht aktiv (anderes Fenster hat den Fokus); Verdrahtung oben geprüft")
    qtbot.keyClick(tab.tabelle, Qt.Key_S, Qt.ControlModifier)
    if not aufrufe and QApplication.platformName() != "offscreen":
        # Windows lässt ein Fenster im Hintergrund nicht in den Vordergrund (Foreground-Lock):
        # Qt hält es für aktiv, das Betriebssystem stellt die Taste aber nicht zu.
        pytest.skip("Tastenkürzel erreicht das Fenster nicht (Vordergrund gesperrt); Verdrahtung oben geprüft")
    assert aufrufe == [True]

    # Fokus in einer Punktezelle beim Bearbeiten - typischer Fall beim Tippen.
    punktefeld = tab.zelle_bearbeiten(0, tab.erfassbare_disziplinen(0)[0], "suche")
    qtbot.keyClick(punktefeld, Qt.Key_S, Qt.ControlModifier)
    assert aufrufe == [True, True]

    # In einem anderen Reiter löst Strg+S nicht aus.
    fenster._tabs.setCurrentWidget(fenster.teilnehmer_tab)
    fenster.teilnehmer_tab.setFocus()
    qtbot.keyClick(fenster.teilnehmer_tab, Qt.Key_S, Qt.ControlModifier)
    assert aufrufe == [True, True]


def test_punkte_ueber_maximum_rot_und_klartext_beim_speichern(qtbot, termin, monkeypatch):
    """UX-Test 02.10.2026, U5: "65" bei höchstens 60 wird sofort markiert und beim
    Speichern im Klartext abgelehnt statt mit "CHECK constraint failed"."""
    conn, pfad = termin
    _teilnehmer_anlegen(conn, disziplin="Flächensuche")

    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    tab = fenster.ergebnis_tab

    qtbot.keyClicks(tab.zelle_bearbeiten(0, "Flächensuche", "suche"), "65")
    qtbot.keyClicks(tab.zelle_bearbeiten(0, "Flächensuche", "anzeige"), "30")
    assert tab.punkte(0, "Flächensuche") == ("65", "30")
    assert tab.zellzustand(0, "Flächensuche", "suche")["zu_hoch"]
    assert tab.zellzustand(0, "Flächensuche", "suche")["tooltip"] == "Höchstens 60 Punkte."
    assert not tab.zellzustand(0, "Flächensuche", "anzeige")["zu_hoch"]

    meldungen = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: meldungen.append(a[2]))
    tab.alle_speichern()

    assert len(meldungen) == 1
    assert "Suche höchstens 60 Punkte (eingegeben: 65)" in meldungen[0]
    assert "CHECK" not in meldungen[0]
    assert tab.zeile_ungespeichert(0)

    tab.punkte_eintragen(0, "Flächensuche", suche="55")
    assert not tab.zellzustand(0, "Flächensuche", "suche")["zu_hoch"]


def test_komma_in_punktefeld_gibt_hinweis(qtbot, termin):
    """UX-Test 02.10.2026, U5: "45,5" wird nicht stillschweigend zu 45 - abgelehnte
    Zeichen erzeugen einen Hinweis."""
    conn, pfad = termin
    _teilnehmer_anlegen(conn, disziplin="Flächensuche")

    # Englische Spracheinstellung wie in der CI (Linux): dort galt "," früher als
    # Tausender-Trennzeichen und wurde angenommen. Jetzt unabhängig von der Sprache abgelehnt.
    from PySide6.QtCore import QLocale

    vorher = QLocale()
    QLocale.setDefault(QLocale(QLocale.English, QLocale.UnitedStates))
    try:
        fenster = HauptFenster(conn, pfad)
        qtbot.addWidget(fenster)
        fenster.show()
        tab = fenster.ergebnis_tab
        qtbot.keyClicks(tab.zelle_bearbeiten(0, "Flächensuche", "suche"), "45,5")
    finally:
        QLocale.setDefault(vorher)

    # Nachtest 2 (N8): eine Eingabe mit abgelehntem Zeichen wird nicht übernommen.
    assert tab.punkte(0, "Flächensuche")[0] == ""
    # N6 (UX-Nachtest): bleibt hervorgehoben stehen - seit X8 (03.11.2026), bis die nächste
    # Zelle bearbeitet wird; eine Eingabe von außen (punkte_eintragen) nimmt ihn ebenfalls weg.
    # Desktop-Prüfung 14.10.2026, Teil 3 Nr. 2: als Klartext in einem eigenen Label, die
    # Hervorhebung kommt aus dessen Stylesheet (vorher stand rohes HTML in der Statuszeile).
    assert tab.hinweis_label.text().startswith("Nur ganze Punkte von 0 bis 60 eingeben (keine Kommazahlen)")
    assert tab.hinweis_label.textFormat() == Qt.PlainText
    assert "<" not in tab.hinweis_label.text()
    assert "font-weight: bold" in tab.hinweis_label.styleSheet()
    assert not tab.hinweis_label.isHidden()
    tab.punkte_eintragen(0, "Flächensuche", suche="4")
    assert tab.hinweis_label.text() == ""
    assert tab.hinweis_label.isHidden()


def test_ergebnis_infozellen_nicht_editierbar_und_sortierpfeil(qtbot, conn):
    """Desktop-Prüfung 14.10.2026, Teil 3 Nr. 3 und 7; seit O8 (19.10.2026) über die
    Zell-Flags statt über abgeschaltete Bearbeitung: Info- und Statuszellen lassen sich
    nicht bearbeiten, auch nicht durch Lostippen."""
    _teilnehmer_anlegen(conn, nachname="Zorn", startnummer=1)
    tab = ErgebnisTab(conn)
    qtbot.addWidget(tab)
    for spalte in (0, 1, 2, 3, _STATUS_SPALTE):
        assert not tab.spalte_bearbeitbar(0, spalte)
    tab.tabelle.setCurrentCell(0, 1)
    qtbot.keyClick(tab.tabelle, Qt.Key_7)
    assert tab.tabelle.item(0, 1).text() == "Zorn, Max"
    assert tab.tabelle.indexWidget(tab.tabelle.currentIndex()) is None
    kopf = tab.tabelle.horizontalHeader()
    tab._spalte_geklickt(1)
    assert kopf.sortIndicatorSection() == 1 and kopf.sortIndicatorOrder() == Qt.AscendingOrder
    tab._spalte_geklickt(1)
    assert kopf.sortIndicatorOrder() == Qt.DescendingOrder


def test_ergebnis_lostippen_ersetzt_wert_und_enter_bleibt_in_der_zelle(qtbot, conn):
    tid = _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    eintragen_ergebnis(conn, tid, "Flächensuche", 17, 20)
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    spalte = _ERGEBNIS_SPALTEN_JE_DISZIPLIN["Flächensuche"][0]
    tab.tabelle.setCurrentCell(0, spalte)

    qtbot.keyClick(tab.tabelle, Qt.Key_4)
    editor = tab.tabelle.indexWidget(tab.tabelle.currentIndex())
    assert editor is not None and editor.text() == "4"  # „17“ ersetzt, nicht ergänzt
    qtbot.keyClick(editor, Qt.Key_2)
    qtbot.keyClick(editor, Qt.Key_Return)

    # Qt übernimmt per verzögertem Aufruf - danach ist der Wert drin, ohne dass punkte()
    # selbst übernehmen müsste.
    qtbot.waitUntil(lambda: tab.tabelle.indexWidget(tab.tabelle.currentIndex()) is None, timeout=WARTEZEIT_MS)
    assert tab.tabelle.item(0, spalte).text() == "42"
    assert (tab.tabelle.currentRow(), tab.tabelle.currentColumn()) == (0, spalte)
    assert tab.punkte(0, "Flächensuche") == ("42", "20")
    assert tab.zeile_ungespeichert(0)


def test_ergebnis_tab_springt_nur_durch_bedienbare_zellen(qtbot, conn):
    """Suche → Anzeige → DQ → Abbruch → nächste Zeile; „–“, Info- und Statusspalte werden
    übersprungen, ebenso gesperrte Punkte und ausgeblendete Zeilen."""
    _teilnehmer_anlegen(conn, nachname="Erster", startnummer=1, disziplin="Trümmerfeld")
    _teilnehmer_anlegen(conn, nachname="Zweiter", startnummer=2, disziplin="Trümmerfeld")
    _teilnehmer_anlegen(conn, nachname="Dritter", startnummer=3, disziplin="Trümmerfeld")
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    suche, anzeige = _ERGEBNIS_SPALTEN_JE_DISZIPLIN["Trümmerfeld"]
    tab.status_setzen(1, dq=True)  # Zweiter: Punkte gesperrt
    tab.tabelle.setCurrentCell(0, suche)

    besucht = []
    for _ in range(7):
        qtbot.keyClick(tab.tabelle, Qt.Key_Tab)
        tab.tabelle.offenen_editor_beenden()
        besucht.append((tab.tabelle.currentRow(), tab.tabelle.currentColumn()))

    assert besucht == [
        (0, anzeige), (0, _DQ_SPALTE), (0, _ABBRUCH_SPALTE),
        (1, _DQ_SPALTE), (1, _ABBRUCH_SPALTE),
        (2, suche), (2, anzeige),
    ]
    # Umschalt+Tab zurück; eine ausgeblendete Zeile wird übersprungen.
    tab.tabelle.setRowHidden(1, True)
    tab.tabelle.setCurrentCell(2, suche)
    qtbot.keyClick(tab.tabelle, Qt.Key_Backtab, Qt.ShiftModifier)
    tab.tabelle.offenen_editor_beenden()
    assert (tab.tabelle.currentRow(), tab.tabelle.currentColumn()) == (0, _ABBRUCH_SPALTE)


def test_ergebnis_tab_in_dk_zeile_wechselt_zur_naechsten_disziplin(qtbot, conn):
    _teilnehmer_anlegen(conn, art="DK", disziplin=None)
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    erste, zweite = ALLE_DISZIPLINEN[0], ALLE_DISZIPLINEN[1]
    tab.tabelle.setCurrentCell(0, _ERGEBNIS_SPALTEN_JE_DISZIPLIN[erste][1])
    qtbot.keyClick(tab.tabelle, Qt.Key_Tab)
    tab.tabelle.offenen_editor_beenden()
    assert tab.tabelle.currentColumn() == _ERGEBNIS_SPALTEN_JE_DISZIPLIN[zweite][0]


def test_ergebnis_tab_aus_offenem_feld_uebernimmt_und_oeffnet_die_naechste_zelle(qtbot, conn):
    _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    editor = tab.zelle_bearbeiten(0, "Flächensuche", "suche")
    qtbot.keyClicks(editor, "50")
    qtbot.keyClick(editor, Qt.Key_Tab)
    assert tab.tabelle.currentColumn() == _ERGEBNIS_SPALTEN_JE_DISZIPLIN["Flächensuche"][1]
    assert tab.tabelle.indexWidget(tab.tabelle.currentIndex()) is not None  # Anzeige gleich offen
    assert tab.tabelle.item(0, _ERGEBNIS_SPALTEN_JE_DISZIPLIN["Flächensuche"][0]).text() == "50"


def test_ergebnis_umschalt_tab_am_anfang_verlaesst_die_tabelle(qtbot, conn):
    _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    editor = tab.zelle_bearbeiten(0, "Flächensuche", "suche")
    qtbot.keyClicks(editor, "7")
    qtbot.keyClick(editor, Qt.Key_Backtab, Qt.ShiftModifier)
    assert tab.tabelle.indexWidget(tab.tabelle.currentIndex()) is None  # nicht neu geöffnet
    assert tab.punkte(0, "Flächensuche")[0] == "7"


def test_ergebnis_strg_tab_wechselt_den_reiter(qtbot, termin):
    """O8: Tab-Navigation in der Tabelle darf Strg+Tab (Reiterwechsel) nicht schlucken."""
    conn, pfad = termin
    _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._tabs.setCurrentWidget(fenster.ergebnis_tab)
    index_vorher = fenster._tabs.currentIndex()
    tab = fenster.ergebnis_tab
    tab.tabelle.setCurrentCell(0, _ERGEBNIS_SPALTEN_JE_DISZIPLIN["Flächensuche"][0])
    qtbot.keyClick(tab.tabelle, Qt.Key_Tab, Qt.ControlModifier)
    assert fenster._tabs.currentIndex() != index_vorher


def test_ergebnis_entf_leert_die_markierte_punktezelle(qtbot, conn):
    """Verifikation O9: wie früher im Eingabefeld leert Entf/Rücktaste die Zelle direkt."""
    tid = _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    eintragen_ergebnis(conn, tid, "Flächensuche", 50, 30)
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    suche, anzeige = _ERGEBNIS_SPALTEN_JE_DISZIPLIN["Flächensuche"]
    tab.tabelle.setCurrentCell(0, suche)
    qtbot.keyClick(tab.tabelle, Qt.Key_Delete)
    tab.tabelle.setCurrentCell(0, anzeige)
    qtbot.keyClick(tab.tabelle, Qt.Key_Backspace)
    assert tab.punkte(0, "Flächensuche") == ("", "")
    assert tab.zeile_ungespeichert(0)
    # Info-Zellen bleiben unberührt.
    name = tab.tabelle.item(0, 1).text()
    tab.tabelle.setCurrentCell(0, 1)
    qtbot.keyClick(tab.tabelle, Qt.Key_Delete)
    assert tab.tabelle.item(0, 1).text() == name != ""


def test_ergebnis_leertaste_schaltet_haekchen(qtbot, conn):
    # Seit R7 (01.11.2026) ist nur noch „Disqualifiziert“ ein Häkchen.
    _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    tab.tabelle.setCurrentCell(0, _DQ_SPALTE)

    qtbot.keyClick(tab.tabelle, Qt.Key_Space)
    assert tab.status(0) == (True, False)
    assert tab.zelle_gesperrt(0, "Flächensuche")
    qtbot.keyClick(tab.tabelle, Qt.Key_Space)
    assert tab.status(0) == (False, False)
    assert not tab.zelle_gesperrt(0, "Flächensuche")


def test_ergebnis_abbruch_mit_grund_laesst_punkte_offen_und_speichert(qtbot, conn):
    """R7 (Marco 01.11.2026): Abbruchgrund per Auswahlliste; mit Grund bleiben die Punkte
    eingebbar (Teilbewertung), gespeichert werden Grund und Punkte."""
    from db import berechne_auswertung, ergebnisse_je_teilnehmer

    tid = _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    assert [tab.tabelle.item(0, _ABBRUCH_SPALTE).text()] == [""]

    _abbruch_auswahl(qtbot, tab, 0, "Verletzung Hund")
    assert tab.status(0) == (False, True)
    assert tab.abbruch_grund(0) == "verletzung_hund"
    assert tab.tabelle.item(0, _ABBRUCH_SPALTE).text() == "Verletzung Hund"
    assert not tab.zelle_gesperrt(0, "Flächensuche")
    tab.punkte_eintragen(0, "Flächensuche", suche=30, anzeige=10)
    assert tab.zeile_ungespeichert(0)
    tab.alle_speichern(meldungen=False)
    assert not tab.zeile_ungespeichert(0)

    e = ergebnisse_je_teilnehmer(conn)[tid]
    assert (e["abbruch"], e["abbruch_grund"], e["suche_flaechensuche"], e["anzeige_flaechensuche"]) == (
        1, "verletzung_hund", 30, 10)
    (t,), _ = berechne_auswertung(conn)
    assert (t.wertnote.notentext, t.gesamtpunkte, t.platzierung) == ("Abbruch wegen Verletzung des Hundes", 40, None)

    # Neu geladen: Grund steht wieder da; Entf nimmt den Abbruch zurück.
    tab.aktualisieren()
    assert tab.abbruch_grund(0) == "verletzung_hund"
    tab.tabelle.setCurrentCell(0, _ABBRUCH_SPALTE)
    qtbot.keyClick(tab.tabelle, Qt.Key_Delete)
    assert tab.status(0) == (False, False)
    assert tab.zeile_ungespeichert(0)


def test_ergebnis_alter_abbruch_ohne_grund_bleibt_gesperrt(qtbot, conn):
    """R7: Ein Abbruch aus Daten vor R7 (ohne Grund) sperrt die Punkte weiter; die
    Auswahlliste bietet ihn nur für diese Zeile an, ein Grund hebt die Sperre auf."""
    tid = _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    eintragen_ergebnis(conn, tid, "Flächensuche", 40, 30)
    setze_ergebnis_status(conn, tid, False, True)
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    assert tab.abbruch_grund(0) == "ohne_grund"
    assert tab.tabelle.item(0, _ABBRUCH_SPALTE).text() == "Abbruch"
    assert tab.zelle_gesperrt(0, "Flächensuche")

    _abbruch_auswahl(qtbot, tab, 0, "Krankheit")
    assert not tab.zelle_gesperrt(0, "Flächensuche")
    assert tab.punkte(0, "Flächensuche") == ("40", "30")  # gespeicherte Punkte wieder da


def test_ergebnis_abbruchgrund_nach_punkten_behaelt_eingaben(qtbot, conn):
    """Verifikation R7, Befund 1: erst Punkte eintragen, dann den Grund wählen bzw. wechseln
    oder zurücknehmen - die ungespeicherten Punkte bleiben stehen."""
    _teilnehmer_anlegen(conn, art="DK", disziplin=None)
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    tab.punkte_eintragen(0, "Trümmerfeld", suche=55, anzeige=35)
    tab.punkte_eintragen(0, "Flächensuche", suche=50, anzeige=30)

    _abbruch_auswahl(qtbot, tab, 0, "Ungehorsam")
    assert tab.punkte(0, "Trümmerfeld") == ("55", "35")
    assert tab.punkte(0, "Flächensuche") == ("50", "30")
    _abbruch_auswahl(qtbot, tab, 0, "Verletzung HF")
    assert tab.abbruch_grund(0) == "verletzung_hf"
    assert tab.punkte(0, "Trümmerfeld") == ("55", "35")
    _abbruch_auswahl(qtbot, tab, 0, "kein Abbruch")
    assert tab.status(0) == (False, False)
    assert tab.punkte(0, "Flächensuche") == ("50", "30")

    # DQ sperrt und leert weiterhin; danach kommt der gespeicherte (leere) Stand zurück.
    tab.status_setzen(0, dq=True)
    assert tab.zelle_gesperrt(0, "Trümmerfeld")
    tab.status_setzen(0, dq=False)
    assert tab.punkte(0, "Trümmerfeld") == ("", "")


def test_ergebnis_abbruchliste_pfeiltaste_uebernimmt_nichts(qtbot, conn):
    """Verifikation R7, Befund 2: Im zugeklappten Feld wählt eine Pfeiltaste keinen Grund
    aus, sondern klappt die Liste auf."""
    from PySide6.QtWidgets import QComboBox

    _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    tab.tabelle.setCurrentCell(0, _ABBRUCH_SPALTE)
    qtbot.keyClick(tab.tabelle, Qt.Key_Space)
    (combo,) = tab.tabelle.viewport().findChildren(QComboBox)
    combo.hidePopup()
    qtbot.keyClick(combo, Qt.Key_Down)
    assert combo.currentIndex() == 0
    assert tab.abbruch_grund(0) is None
    assert tab.tabelle.viewport().findChildren(QComboBox) == [combo]  # Editor noch offen
    combo.hidePopup()


def test_ergebnis_abbruchliste_modifier_und_kuerzel_klappen_nicht_auf(qtbot, conn):
    """Vor-Build-Verifikation 1.0.55, Befund 4: Umschalt/Strg/Alt allein und Kürzel wie
    Strg+S klappen die Liste nicht auf, eine Pfeiltaste schon."""
    from PySide6.QtWidgets import QComboBox

    _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    tab.tabelle.setCurrentCell(0, _ABBRUCH_SPALTE)
    qtbot.keyClick(tab.tabelle, Qt.Key_Space)
    (combo,) = [c for c in tab.tabelle.viewport().findChildren(QComboBox) if c.isVisible()]
    combo.hidePopup()
    aufgeklappt = []
    combo.showPopup = lambda: aufgeklappt.append(True)
    for taste in (Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt):
        qtbot.keyClick(combo, taste)
    qtbot.keyClick(combo, Qt.Key_S, Qt.ControlModifier)
    assert aufgeklappt == []
    qtbot.keyClick(combo, Qt.Key_Down)
    assert aufgeklappt == [True]
    assert tab.abbruch_grund(0) is None


def test_ergebnis_abbruchliste_enter_uebernimmt_grund(qtbot, conn):
    """Nachprüfung R7: Leertaste klappt die Liste auf, Pfeiltasten wählen, erst Enter
    übernimmt den Grund und schließt die Auswahl."""
    from PySide6.QtWidgets import QComboBox

    _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    tab.tabelle.setCurrentCell(0, _ABBRUCH_SPALTE)
    qtbot.keyClick(tab.tabelle, Qt.Key_Space)
    qtbot.wait(50)
    (combo,) = [c for c in tab.tabelle.viewport().findChildren(QComboBox) if c.isVisible()]
    liste = combo.view()
    qtbot.keyClick(liste, Qt.Key_Down)
    qtbot.keyClick(liste, Qt.Key_Down)
    assert tab.abbruch_grund(0) is None  # Blättern übernimmt nichts
    qtbot.keyClick(liste, Qt.Key_Return)
    qtbot.wait(50)
    assert tab.abbruch_grund(0) == "verletzung_hund"
    assert tab.tabelle.state() != tab.tabelle.State.EditingState


def test_ergebnis_abbruch_oeffnet_mit_einem_klick(qtbot, conn):
    """UX-Test 03.11.2026, X5: Der ERSTE Klick in die Abbruch-Zelle öffnet die Auswahl (vorher
    markierte er nur); die leere Zelle erklärt sich per Tooltip, ein Grund steht voll darin."""
    from PySide6.QtWidgets import QComboBox

    _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    tab.tabelle.setCurrentCell(0, 0)  # eine andere Zelle ist markiert
    item = tab.tabelle.item(0, _ABBRUCH_SPALTE)
    assert "auswählen" in item.toolTip()
    qtbot.mouseClick(tab.tabelle.viewport(), Qt.LeftButton, pos=tab.zellrechteck(0, _ABBRUCH_SPALTE).center())
    qtbot.wait(50)
    combos = [c for c in tab.tabelle.viewport().findChildren(QComboBox) if c.isVisible()]
    assert len(combos) == 1
    combos[0].hidePopup()
    tab.status_setzen(0, abbruch="verletzung_hund")
    assert tab.tabelle.item(0, _ABBRUCH_SPALTE).toolTip() == "Abbruch wegen Verletzung des Hundes"


def test_ergebnis_status_nennt_dq_und_abbruch(qtbot, conn):
    """UX-Test 2026-11, T3: Der Status zeigt nach dem Speichern „disqualifiziert“ bzw. den
    Abbruch mit Grund statt nur „gespeichert“."""
    _teilnehmer_anlegen(conn, nachname="A", startnummer=1, disziplin="Flächensuche")
    _teilnehmer_anlegen(conn, nachname="B", startnummer=2, disziplin="Flächensuche")
    _teilnehmer_anlegen(conn, nachname="C", startnummer=3, disziplin="Flächensuche")
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    tab.status_setzen(0, dq=True)
    tab.status_setzen(1, abbruch="verletzung_hund")
    tab.punkte_eintragen(2, "Flächensuche", suche=50, anzeige=30)
    assert tab.tabelle.item(0, _STATUS_SPALTE).text() == "nicht gespeichert"
    tab.alle_speichern(meldungen=False)

    texte = [tab.tabelle.item(z, _STATUS_SPALTE).text() for z in range(3)]
    assert texte == ["disqualifiziert", "Abbruch: Verletzung Hund", "gespeichert"]
    assert tab.tabelle.item(1, _STATUS_SPALTE).toolTip() == "gespeichert: Abbruch: Verletzung Hund"
    assert tab.tabelle.item(2, _STATUS_SPALTE).toolTip() == ""
    tab.aktualisieren()  # neu geladen
    assert tab.tabelle.item(0, _STATUS_SPALTE).text() == "disqualifiziert"


def test_ergebnis_speichermeldung_zaehlt_teilnehmer(qtbot, conn):
    """UX-Test 2026-11, T3: „29 Ergebnis(se) gespeichert“ bei 16 Teilnehmern wirkte doppelt -
    gezählt werden jetzt Teilnehmer, auch wenn je Teilnehmer mehrere Disziplinen und ein
    Abbruch gespeichert werden."""
    _teilnehmer_anlegen(conn, nachname="A", startnummer=1, art="DK", disziplin=None)
    _teilnehmer_anlegen(conn, nachname="B", startnummer=2, disziplin="Flächensuche")
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    for disziplin in ("Trümmerfeld", "Flächensuche", "Behältnisstrecke"):
        tab.punkte_eintragen(0, disziplin, suche=50, anzeige=30)
    tab.status_setzen(0, abbruch="krankheit")
    tab.punkte_eintragen(1, "Flächensuche", suche=50, anzeige=30)
    tab.alle_speichern(meldungen=False)
    assert tab.status_label.text() == "2 Teilnehmer gespeichert."


def test_ergebnis_abbruch_spalte_fasst_jeden_grund(qtbot, conn):
    """UX-Test 2026-11, T3: Im Nachtest stand „letzung H“ - die Spalte fasst den längsten
    Grund samt Rand und Pfeil, schmal wie breit."""
    _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    for breite in (900, 1600):
        tab.resize(breite, 600)
        tab._spaltenbreiten_anpassen()
        metrik = tab.tabelle.fontMetrics()
        from shs_core import ABBRUCH_GRUENDE

        laengster = max(metrik.horizontalAdvance(text) for text, _ in ABBRUCH_GRUENDE.values())
        from desktop_ergebnis import _AbbruchDelegate

        assert tab.tabelle.columnWidth(_ABBRUCH_SPALTE) >= laengster + _AbbruchDelegate.PLATZ_NEBEN_TEXT


def test_ergebnis_zu_hoch_schon_beim_tippen(qtbot, conn):
    """UX-Test 2026-11, T4 (C24 teilweise erledigt): Ein Wert über dem Maximum wird schon im offenen
    Eingabefeld rot umrandet und erklärt; ein gültiger Wert nimmt beides wieder weg. Den
    Komma-Hinweis (X8) lässt das Weitertippen stehen."""
    _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    editor = tab.zelle_bearbeiten(0, "Flächensuche", "suche")
    qtbot.keyClicks(editor, "65")
    assert editor.isVisible()  # noch nicht übernommen
    assert "border: 2px solid" in editor.styleSheet()
    assert tab.hinweis_label.isVisible()
    assert tab.hinweis_label.text().startswith("Höchstens 60 Punkte - 65 ist zu hoch")
    qtbot.keyClick(editor, Qt.Key_Backspace)
    assert "border" not in editor.styleSheet()
    assert not tab.hinweis_label.isVisible()

    # Übernehmen: der Hinweis vom Tippen weicht dem roten Klartext unter der Tabelle (X7).
    qtbot.keyClicks(editor, "9")  # "69"
    assert tab.hinweis_label.isVisible()
    qtbot.keyClick(editor, Qt.Key_Return)
    qtbot.waitUntil(lambda: tab.tabelle.indexWidget(tab.tabelle.currentIndex()) is None, timeout=WARTEZEIT_MS)
    assert not tab.hinweis_label.isVisible()
    assert tab.zellzustand(0, "Flächensuche", "suche")["zu_hoch"]
    assert tab.zu_hoch_label.isVisible()

    # Komma-Hinweis bleibt beim Weitertippen stehen.
    editor = tab.zelle_bearbeiten(0, "Flächensuche", "anzeige")
    qtbot.keyClicks(editor, "3,0")
    assert tab.hinweis_label.text().startswith("Nur ganze Punkte")

    # Verifikation B1: „6,5“ - aus der 5 wird 65. Beide Hinweise stehen da, und nach der
    # Rücktaste bleibt der Komma-Hinweis (X8) stehen.
    editor = tab.zelle_bearbeiten(0, "Flächensuche", "suche")
    editor.clear()
    qtbot.keyClicks(editor, "6,5")
    assert editor.text() == "65"
    zeilen = tab.hinweis_label.text().split("\n")
    assert zeilen[0].startswith("Höchstens 60 Punkte") and zeilen[1].startswith("Nur ganze Punkte")
    qtbot.keyClick(editor, Qt.Key_Backspace)
    assert tab.hinweis_label.isVisible()
    assert tab.hinweis_label.text().startswith("Nur ganze Punkte")

    # Escape verwirft die Eingabe - der Hinweis vom Tippen geht mit.
    qtbot.keyClicks(editor, "5")
    assert tab.hinweis_label.text().startswith("Höchstens")
    qtbot.keyClick(editor, Qt.Key_Escape)
    qtbot.waitUntil(lambda: tab.tabelle.indexWidget(tab.tabelle.currentIndex()) is None, timeout=WARTEZEIT_MS)
    assert "Höchstens" not in tab.hinweis_label.text()


def test_ergebnis_wert_ueber_maximum_zeigt_klartext(qtbot, conn):
    """UX-Test 03.11.2026, X7: zum roten Rahmen ein sichtbarer Text, der nach der Korrektur
    wieder verschwindet."""
    _teilnehmer_anlegen(conn, nachname="Erster", startnummer=1, disziplin="Flächensuche")
    _teilnehmer_anlegen(conn, nachname="Zweiter", startnummer=2, disziplin="Flächensuche")
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    tab.punkte_eintragen(0, "Flächensuche", suche="65", anzeige="30")
    assert not tab.zu_hoch_label.isHidden()
    assert "Nr. 1 Erster: Flächensuche Suche höchstens 60 Punkte (eingegeben: 65)" in tab.zu_hoch_label.text()
    # Zweite Zeile zu hoch, erste korrigiert: der Hinweis bleibt für die zweite (Verifikation A2, 1).
    tab.punkte_eintragen(1, "Flächensuche", anzeige="45", suche="30")
    tab.punkte_eintragen(0, "Flächensuche", suche="50")
    assert "Erster" not in tab.zu_hoch_label.text()
    assert "Nr. 2 Zweiter: Flächensuche Anzeige höchstens 40 Punkte (eingegeben: 45)" in tab.zu_hoch_label.text()
    # Ein Komma in einer anderen Zelle verdrängt ihn nicht (Befund 4), Bearbeiten einer anderen
    # Zelle auch nicht.
    qtbot.keyClicks(tab.zelle_bearbeiten(0, "Flächensuche", "anzeige"), "3,")
    assert not tab.hinweis_label.isHidden()
    assert not tab.zu_hoch_label.isHidden()
    tab.zelle_bearbeiten(0, "Flächensuche", "suche")
    assert tab.hinweis_label.isHidden()
    assert not tab.zu_hoch_label.isHidden()
    tab.punkte_eintragen(1, "Flächensuche", anzeige="35")
    assert tab.zu_hoch_label.isHidden()


def test_ergebnis_zu_hoch_hinweis_nach_neuaufbau(qtbot, conn):
    """Verifikation A2, Befund 3: Nach einem Neuaufbau ohne die betroffene Zeile darf kein
    alter X7-Hinweis stehen bleiben."""
    _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    tab.punkte_eintragen(0, "Flächensuche", suche="65", anzeige="30")
    assert not tab.zu_hoch_label.isHidden()
    tab.aktualisieren()  # verwirft die ungespeicherte Eingabe
    assert tab.zu_hoch_label.isHidden()


def test_komma_hinweis_bleibt_nach_der_naechsten_ziffer(qtbot, conn):
    """UX-Test 03.11.2026, X8: Bei "4,5" nahm die "5" den Hinweis sofort wieder weg - aus 4,5
    wurde unbemerkt 45. Jetzt bleibt er bis zur nächsten bearbeiteten Zelle."""
    _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    editor = tab.zelle_bearbeiten(0, "Flächensuche", "suche")
    qtbot.keyClicks(editor, "4,5")
    assert editor.text() == "45"
    assert not tab.hinweis_label.isHidden()
    assert "der bisherige Wert bleibt" in tab.hinweis_label.text()
    qtbot.keyClick(editor, Qt.Key_Return)
    assert not tab.hinweis_label.isHidden()  # Übernehmen lässt ihn stehen
    tab.zelle_bearbeiten(0, "Flächensuche", "anzeige")
    assert tab.hinweis_label.isHidden()


def test_punkte_mit_abgelehntem_zeichen_werden_nicht_uebernommen(qtbot, conn):
    """Nachtest 2, N8 (Marco 04.11.2026): Aus „4,5“ wurde 45 und überschrieb den alten Wert.
    Jetzt bleibt der alte Wert, die Statuszeile sagt es, und der Hinweis nennt den Grund.
    Wer das Feld leert und neu tippt, dessen Eingabe gilt wieder."""
    tid = _teilnehmer_anlegen(conn, disziplin="Flächensuche", startnummer=7)
    eintragen_ergebnis(conn, tid, "Flächensuche", 47, 20)
    tab = _ergebnis_tab_gezeigt(qtbot, conn)

    editor = tab.zelle_bearbeiten(0, "Flächensuche", "suche")
    qtbot.keyClicks(editor, "4,5")
    assert "(keine Kommazahlen)" in tab.hinweis_label.text()
    qtbot.keyClick(editor, Qt.Key_Return)
    assert tab.punkte(0, "Flächensuche")[0] == "47"
    assert tab.status_label.text().startswith("Nr. 7 Muster: Eingabe nicht übernommen")
    assert "„47“" in tab.status_label.text()

    editor = tab.zelle_bearbeiten(0, "Flächensuche", "suche")
    qtbot.keyClicks(editor, "4x")
    assert "(keine Buchstaben)" in tab.hinweis_label.text()
    editor.clear()  # Feld geleert: die neue Eingabe gilt
    qtbot.keyClicks(editor, "48")
    qtbot.keyClick(editor, Qt.Key_Return)
    assert tab.punkte(0, "Flächensuche")[0] == "48"

    editor = tab.zelle_bearbeiten(0, "Flächensuche", "anzeige")
    qtbot.keyClicks(editor, "123")
    assert "(höchstens zwei Ziffern)" in tab.hinweis_label.text()

    # Der erste Grund bleibt („4,55“ ist ein Komma-Fehler, kein Ziffern-Fehler).
    editor = tab.zelle_bearbeiten(0, "Flächensuche", "suche")
    qtbot.keyClicks(editor, "4,55")
    assert "(keine Kommazahlen)" in tab.hinweis_label.text()
    # Speichern mit offenem Feld: die Meldung geht nicht unter (Verifikation B14).
    tab.alle_speichern()
    assert tab.punkte(0, "Flächensuche")[0] == "48"
    assert tab.status_label.text().startswith("Nr. 7 Muster: Eingabe nicht übernommen")

    # Ein abgelehntes erstes Zeichen bei markiertem Wert fällt nur weg - die Zahl danach gilt.
    editor = tab.zelle_bearbeiten(0, "Flächensuche", "suche")
    qtbot.keyClicks(editor, ",44")
    qtbot.keyClick(editor, Qt.Key_Return)
    assert tab.punkte(0, "Flächensuche")[0] == "44"


def test_komma_hinter_einstelligem_wert_wird_nicht_uebernommen(qtbot, conn):
    """QS B22, K1: Steht schon „4“ in der Zelle und wird hinter der 4 „,5“ getippt, darf nicht
    45 gespeichert werden - die 4 bleibt, die Statuszeile meldet die Verwerfung. Ist der Wert
    dagegen noch ganz markiert, ersetzt die Zahl nach dem Komma ihn wie gewohnt."""
    tid = _teilnehmer_anlegen(conn, disziplin="Flächensuche", startnummer=7)
    eintragen_ergebnis(conn, tid, "Flächensuche", 4, 20)
    tab = _ergebnis_tab_gezeigt(qtbot, conn)

    editor = tab.zelle_bearbeiten(0, "Flächensuche", "suche")
    assert editor.selectedText() == "4"
    qtbot.keyClick(editor, Qt.Key_End)
    qtbot.keyClicks(editor, ",5")
    assert "(keine Kommazahlen)" in tab.hinweis_label.text()
    qtbot.keyClick(editor, Qt.Key_Return)
    assert tab.punkte(0, "Flächensuche")[0] == "4"
    assert tab.status_label.text().startswith("Nr. 7 Muster: Eingabe nicht übernommen")
    qtbot.keyClick(editor, Qt.Key_Escape)  # Enter lässt das Feld offen

    editor = tab.zelle_bearbeiten(0, "Flächensuche", "suche")
    qtbot.keyClicks(editor, ",5")  # Wert noch markiert: das Komma fällt weg, die 5 ersetzt
    qtbot.keyClick(editor, Qt.Key_Return)
    assert tab.punkte(0, "Flächensuche")[0] == "5"


def test_ablehnungsgrund_je_zeichen():
    """QS B22, W4: der Grund im Hinweis, ohne Oberfläche geprüft."""
    from desktop_ergebnis import _ablehnungsgrund

    assert _ablehnungsgrund("7") == "höchstens zwei Ziffern"
    assert _ablehnungsgrund(",") == _ablehnungsgrund(".") == "keine Kommazahlen"
    assert _ablehnungsgrund("x") == _ablehnungsgrund("Ä") == "keine Buchstaben"
    assert _ablehnungsgrund("-") == _ablehnungsgrund("") == "nur Ziffern"
    from desktop_ergebnis_zellen import _EINGEFUEGT
    assert _ablehnungsgrund(_EINGEFUEGT) == "nur ganze Zahlen einfügen"


def test_ergebnis_abbruch_spalte_zeigt_den_ganzen_grund(qtbot, termin):
    """Nachtest 2, N1/N2: Die Abbruch-Spalte ist auch bei leeren Zellen so breit wie der
    längste Grund, und die Status-Spalte ragt bei großer Schrift nicht über den Rand."""
    from PySide6.QtGui import QFontMetrics
    from PySide6.QtWidgets import QStyleOptionViewItem

    import desktop_darstellung
    import desktop_gemeinsam
    from shs_core import ABBRUCH_GRUENDE

    conn, pfad = termin
    for nr in range(1, 5):
        _teilnehmer_anlegen(conn, nachname=f"T{nr}", startnummer=nr, art="DK", disziplin=None)
    laengster_code = max(ABBRUCH_GRUENDE, key=lambda k: len(ABBRUCH_GRUENDE[k][0]))
    tab = ErgebnisTab(conn)
    qtbot.addWidget(tab)
    tab.status_setzen(0, abbruch=laengster_code)
    tab.alle_speichern()  # Status „Abbruch: <längster Grund>“
    laengster = ABBRUCH_GRUENDE[laengster_code][0]
    for faktor in (1.0, 1.15):  # Normal, Groß
        desktop_darstellung._schrift_faktor = faktor
        try:
            tab.resize(1900, 700)
            tab.show()
            qtbot.waitExposed(tab)
            tab._tabelle_pt = None
            tab._spaltenbreiten_anpassen()
            t = tab.tabelle
            opt = QStyleOptionViewItem()
            t.initViewItemOption(opt)
            noetig = QFontMetrics(opt.font).horizontalAdvance(laengster) + desktop_ergebnis_zellen._AbbruchDelegate.PLATZ_NEBEN_TEXT
            assert t.columnWidth(desktop_gemeinsam._ABBRUCH_SPALTE) >= noetig
            assert sum(t.columnWidth(c) for c in range(t.columnCount())) <= t.viewport().width()
        finally:
            desktop_darstellung._schrift_faktor = 1.0


def test_ergebnis_klick_in_die_haekchenzelle_schaltet(qtbot, conn):
    _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    mitte = tab.zellrechteck(0, _DQ_SPALTE).center()
    qtbot.mouseClick(tab.tabelle.viewport(), Qt.LeftButton, pos=mitte)
    assert tab.status(0) == (True, False)


def test_ergebnis_offenes_eingabefeld_geht_beim_speichern_nicht_verloren(qtbot, conn):
    tid = _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    tab.punkte_eintragen(0, "Flächensuche", anzeige="30")
    editor = tab.zelle_bearbeiten(0, "Flächensuche", "suche")
    qtbot.keyClicks(editor, "55")
    assert tab.tabelle.indexWidget(tab.tabelle.currentIndex()) is editor  # noch nicht übernommen

    tab.alle_speichern()

    assert get_ergebnis(conn, tid)["suche_flaechensuche"] == 55
    assert not tab.hat_ungespeicherte_aenderungen()


def test_ergebnis_offenes_eingabefeld_uebersteht_den_designwechsel(qtbot, conn, monkeypatch):
    """QS 19.10.2026: Ein Designwechsel per Maus nimmt dem Feld den Fokus nicht; das Umfärben
    der Zelle lud bisher den alten Wert ins offene Feld zurück."""
    import desktop_darstellung as darstellung
    tid = _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    tab.punkte_eintragen(0, "Flächensuche", anzeige="30")
    editor = tab.zelle_bearbeiten(0, "Flächensuche", "suche")
    qtbot.keyClicks(editor, "55")
    monkeypatch.setattr(darstellung, "_aktives_design", "dunkel")

    tab.farben_auffrischen()

    assert editor.text() == "55"
    tab.alle_speichern()
    assert get_ergebnis(conn, tid)["suche_flaechensuche"] == 55


def test_ergebnis_offenes_eingabefeld_zaehlt_als_ungespeichert(qtbot, conn):
    _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    tab = _ergebnis_tab_gezeigt(qtbot, conn)
    qtbot.keyClicks(tab.zelle_bearbeiten(0, "Flächensuche", "suche"), "5")
    assert tab.hat_ungespeicherte_aenderungen()  # z. B. Rückfrage beim Reiterwechsel/Schließen


def test_ergebnis_sortierung_nach_name_mit_umlauten(qtbot, conn):
    """Desktop-Prüfung 14.10.2026, Teil 3 Nr. 4: „Ötzi“ gehört nicht hinter „Zorn“."""
    for nummer, name in enumerate(("Zorn", "Ötzi", "ebert", "Adler", "Älter"), start=1):
        _teilnehmer_anlegen(conn, nachname=name, startnummer=nummer)
    tab = ErgebnisTab(conn)
    qtbot.addWidget(tab)
    tab._spalte_geklickt(1)
    assert _ergebnis_nachnamen(tab) == ["Adler", "Älter", "ebert", "Ötzi", "Zorn"]
    tab.aktualisieren()  # Sortierung bleibt beim Neuladen (nur ein Aufbau)
    assert _ergebnis_nachnamen(tab) == ["Adler", "Älter", "ebert", "Ötzi", "Zorn"]


def test_ergebnis_meldet_verworfene_eingabe_nach_disziplinwechsel(qtbot, conn, monkeypatch):
    """Desktop-Prüfung 14.10.2026, Teil 3 Nr. 5: ungespeicherte Punkte zur alten Disziplin
    verschwanden nach einem Disziplinwechsel ohne Hinweis."""
    tid = _teilnehmer_anlegen(conn, nachname="Wechsel", startnummer=3, disziplin="Flächensuche")
    tab = ErgebnisTab(conn)
    qtbot.addWidget(tab)
    tab.punkte_eintragen(0, "Flächensuche", "50", "30")
    conn.execute("UPDATE teilnehmer SET disziplin = 'Trümmerfeld' WHERE id = ?", (tid,))
    conn.commit()
    hinweise = meldungen_sammeln(monkeypatch, "information")

    tab.aktualisieren_eingaben_erhalten()

    assert len(hinweise) == 1
    assert "Nr. 3 – Wechsel, Max (Flächensuche: Disziplin inzwischen geändert)" in hinweise[0]
    assert not tab.hat_ungespeicherte_aenderungen()


def test_ergebnis_meldet_person_mit_mehreren_gruenden_nur_einmal(qtbot, conn, monkeypatch):
    """Offener Punkt 18.10.2026: Disziplinwechsel und DQ zugleich - eine Zeile je Person,
    beide Gründe in einer Klammer."""
    tid = _teilnehmer_anlegen(conn, nachname="Doppelt", startnummer=4, disziplin="Flächensuche")
    tab = ErgebnisTab(conn)
    qtbot.addWidget(tab)
    tab.punkte_eintragen(0, "Flächensuche", "50", "30")
    conn.execute("UPDATE teilnehmer SET disziplin = 'Trümmerfeld' WHERE id = ?", (tid,))
    conn.commit()
    setze_ergebnis_status(conn, tid, disqualifiziert=True, abbruch=False)
    hinweise = meldungen_sammeln(monkeypatch, "information")

    tab.aktualisieren_eingaben_erhalten()

    assert len(hinweise) == 1
    assert hinweise[0].count("Doppelt, Max") == 1
    assert (
        "Nr. 4 – Doppelt, Max (Flächensuche: Disziplin inzwischen geändert; "
        "inzwischen „Disqualifiziert“ oder „Abbruch“ gespeichert)"
    ) in hinweise[0]


def test_ergebnis_meldet_mehrere_alte_disziplinen_in_einer_zeile(qtbot, conn, monkeypatch):
    """Offener Punkt 18.10.2026: DK -> ED mit Eingaben in zwei Disziplinen ergibt eine Zeile."""
    tid = _teilnehmer_anlegen(conn, nachname="Umgestellt", startnummer=5, art="DK", disziplin=None)
    tab = ErgebnisTab(conn)
    qtbot.addWidget(tab)
    for disziplin in ("Flächensuche", "Trümmerfeld"):
        tab.punkte_eintragen(0, disziplin, "50", "30")
    conn.execute("UPDATE teilnehmer SET art = 'ED', disziplin = 'Behältnisstrecke' WHERE id = ?", (tid,))
    conn.commit()
    hinweise = meldungen_sammeln(monkeypatch, "information")

    tab.aktualisieren_eingaben_erhalten()

    assert len(hinweise) == 1
    assert hinweise[0].count("Umgestellt, Max") == 1
    zeile = next(z for z in hinweise[0].splitlines() if "Umgestellt, Max" in z)
    assert "Flächensuche: Disziplin inzwischen geändert" in zeile
    assert "Trümmerfeld: Disziplin inzwischen geändert" in zeile


def test_ergebniserfassung_leere_zeile_zeigt_noch_kein_ergebnis(qtbot, termin):
    """UX-Test 02.10.2026, K1: leere Zeilen zeigen "noch kein Ergebnis" statt
    "gespeichert"; nach dem Speichern eines Ergebnisses "gespeichert" mit Haken-Symbol."""
    from desktop_gemeinsam import _STATUS_SPALTE

    conn, pfad = termin
    _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    tab = fenster.ergebnis_tab
    assert tab.tabelle.item(0, _STATUS_SPALTE).text() == "noch kein Ergebnis"
    assert tab.tabelle.item(0, _STATUS_SPALTE).icon().isNull()
    tab.punkte_eintragen(0, "Flächensuche", "50", "30")
    assert tab.tabelle.item(0, _STATUS_SPALTE).text() == "nicht gespeichert"
    assert tab.tabelle.item(0, _STATUS_SPALTE).icon().cacheKey() == symbol("device-floppy", "warnung").cacheKey()
    tab.alle_speichern()
    assert tab.tabelle.item(0, _STATUS_SPALTE).text() == "gespeichert"
    assert tab.tabelle.item(0, _STATUS_SPALTE).icon().cacheKey() == symbol("check", "ok").cacheKey()


def test_alle_symbole_ergeben_ein_bild():
    import desktop_gemeinsam as gemeinsam

    for name in gemeinsam.SYMBOL_NAMEN:
        icon = gemeinsam.symbol(name, "#123456")
        assert not icon.isNull(), name
        assert not icon.pixmap(16, 16).isNull(), name
    # Fehlende Datei: leeres Icon statt Fehler.
    assert gemeinsam.symbol("gibt-es-nicht").isNull()
    assert gemeinsam.symbol_png("gibt-es-nicht") is None
