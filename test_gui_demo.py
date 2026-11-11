"""GUI-Tests: Geführte Demoprüfung (desktop_demo.py).

Fixtures und Hilfen stehen in gui_hilfen.py (Aufteilung von test_app_gui.py, 11.11.2026)."""

from __future__ import annotations

import datetime
import os
import pytest
from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QLineEdit, QMessageBox, QPushButton
from app import HauptFenster, StartDialog
from desktop_gemeinsam import _ERGEBNIS_SPALTEN_JE_DISZIPLIN
from db import (
    NeuerTeilnehmer,
    add_teilnehmer,
    get_ergebnis,
    get_veranstaltung,
    list_teilnehmer,
)
from desktop_gemeinsam import symbol
from gui_hilfen import *  # noqa: F401,F403


def test_demo_markiert_die_ergebniszelle(qtbot, termin):
    """O8: die Demo markiert das Zellenrechteck (keine Eingabe-Widgets mehr)."""
    conn, pfad = termin
    tid = _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._tabs.setCurrentWidget(fenster.ergebnis_tab)
    from desktop_demo import DemoTour

    tour = DemoTour(fenster)
    spalte = _ERGEBNIS_SPALTEN_JE_DISZIPLIN["Flächensuche"][0]
    tour._ergebniszelle_markieren(tid, spalte)
    markierung = tour._markierung
    zelle = fenster.ergebnis_tab.zellrechteck(0, spalte)
    rand = markierung.RAND
    assert markierung.isVisible()
    assert markierung.size() == zelle.size() + QSize(2 * rand, 2 * rand)
    oben_links = fenster.ergebnis_tab.tabelle.viewport().mapTo(fenster, zelle.topLeft())
    assert markierung.pos() == oben_links - QPoint(rand, rand)
    markierung.entfernen()


def test_demo_button_im_hauptfenster_startet_demo(qtbot, termin, monkeypatch):
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    gestartet = []

    class _TourAttrappe:
        def __init__(self, fenster=None, fenster_fabrik=None):
            gestartet.append(fenster)

        def starten(self):
            gestartet.append("gestartet")

    monkeypatch.setattr("app.DemoTour", _TourAttrappe)
    knoepfe = [b for b in fenster.findChildren(QPushButton) if b.text() == "Demoprüfung"]
    assert len(knoepfe) == 1 and knoepfe[0].isVisible()

    qtbot.mouseClick(knoepfe[0], Qt.MouseButton.LeftButton)

    assert gestartet == [fenster, "gestartet"]


def test_demo_button_im_startdialog(qtbot, monkeypatch, tmp_path):
    ueberall_ersetzen(monkeypatch, "termine_ordner", lambda: tmp_path)  # Teil 2 Nr. 15
    monkeypatch.setattr("app.liste_termine", lambda: [])
    dialog = StartDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    knoepfe = [b for b in dialog.findChildren(QPushButton) if b.text() == "Demoprüfung"]
    assert len(knoepfe) == 1

    qtbot.mouseClick(knoepfe[0], Qt.MouseButton.LeftButton)

    assert dialog.demo_angefordert is True
    assert dialog.result() == QDialog.Accepted


@pytest.mark.parametrize("heute", [datetime.date(2026, 12, 31), datetime.date(2027, 1, 2)])
def test_demopruefung_kompletter_durchlauf_aus_hauptfenster(qtbot, termin, demo_umgebung, monkeypatch, heute):
    """Die Demo spielt "heute" - PO1 (PO_01012027.md): vor dem Stichtag mit Stechen, danach
    ohne (Schritt 12 erklärt dann nur)."""
    import types

    import desktop_demo

    class _Datum(datetime.date):
        @classmethod
        def today(cls):
            return heute

    monkeypatch.setattr(desktop_demo, "datetime", types.SimpleNamespace(date=_Datum))
    from db import (
        berechne_auswertung,
        list_zeitplan_eintraege,
        list_zeitplan_richter,
        pruefungs_kuerzel,
        startnummer_bereiche,
    )

    temp, termine = demo_umgebung
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._tabs.setCurrentWidget(fenster.zeitplan_tab)
    alter_index = fenster._tabs.currentIndex()

    fenster._demo_starten()
    tour = fenster._demo_tour
    assert tour is not None
    demo_ordner = os.path.dirname(tour.pfad)
    assert os.path.dirname(demo_ordner) == str(temp)
    # Teil 10 Nr. 9: Der Demo-Knopf holt während der Demo das Erklärfenster zurück.
    assert not fenster.wechseln_btn.isEnabled()
    assert "Erklärfenster" in fenster.demo_btn.text()
    gesehen = []

    def pruefen(titel):
        gesehen.append(titel.split(".")[0] if titel[0].isdigit() else "")
        demo_conn = tour.conn
        if titel.startswith("2."):
            assert fenster.conn is demo_conn
            assert fenster.windowTitle().startswith("DEMO – ")
            assert not fenster._tabs.isTabEnabled(fenster._tabs.indexOf(fenster.datensicherung_tab))
        elif titel.startswith("4."):
            assert len(list_teilnehmer(demo_conn)) == 8
        elif titel.startswith("5."):
            bereiche = startnummer_bereiche(get_veranstaltung(demo_conn))
            for t in list_teilnehmer(demo_conn):
                von, bis = bereiche[pruefungs_kuerzel(t["art"], t["stufe"], t["disziplin"])]
                assert t["startnummer"] is not None and von <= t["startnummer"] <= bis
        elif titel.startswith("6."):
            offen = [t["nachname"] for t in list_teilnehmer(demo_conn) if not t["bezahlt"]]
            assert offen == ["Hansen"]
        elif titel.startswith("7."):
            richter = list_zeitplan_richter(demo_conn)
            assert [r["name"] for r in richter] == ["Erika Beispiel", "Hans Probe"]
            assert any(list_zeitplan_eintraege(demo_conn, r["id"]) for r in richter)
        elif titel.startswith("10."):
            assert not fenster.ergebnis_tab.hat_ungespeicherte_aenderungen()
        elif titel.startswith("12."):
            fertig, ausstehend = berechne_auswertung(demo_conn)
            assert ausstehend == []
            assert sorted(t.wertnote.abkuerzung for t in fertig) == ["DISQ", "G", "G", "SG", "SG", "V", "V", "nB"]
            if heute.year < 2027:
                assert [t.name for t in fertig if t.stechen == "gewonnen"] == ["Albers, Anna"]
            else:
                assert all(t.stechen is None for t in fertig)
                assert sorted(t.name for t in fertig if t.platzierung == 1 and t.wertnote.abkuerzung == "V") == [
                    "Albers, Anna", "Brandt, Ben"]
            assert get_veranstaltung(demo_conn)["datum"] == heute.isoformat()
        elif titel.startswith("13."):
            assert tour.pdf_pfad and os.path.isfile(tour.pdf_pfad)
            assert tour.pdf_pfad.startswith(demo_ordner)

    _demo_bis(tour, None, pruefen)

    assert gesehen == [""] + [str(n) for n in range(1, 18)]
    assert fenster._demo_tour is None
    assert fenster.conn is conn and fenster.pfad == pfad
    assert fenster._tabs.currentIndex() == alter_index
    assert not fenster.windowTitle().startswith("DEMO")
    assert fenster._tabs.isTabEnabled(fenster._tabs.indexOf(fenster.datensicherung_tab))
    assert fenster.demo_btn.isEnabled() and fenster.wechseln_btn.isEnabled()
    assert not os.path.exists(demo_ordner)
    assert list(termine.iterdir()) == []
    conn.execute("SELECT 1")  # echter Termin weiterhin offen


def test_demo_bereiche_passen_zur_anzahl_und_schritt_3_nennt_pruefung():
    """Nachtest 2, N9: je 20 Nummern wie bei „Anzahl 20“; Schritt 3 spricht vom Feld
    „Prüfung“ statt von „Art und Leistungsklasse“, die die Maske nicht mehr zeigt."""
    import demo_daten
    import desktop_demo
    from db import pruefung_nach_kuerzel

    assert all(bis - von + 1 == 20 for von, bis in demo_daten.PRUEFUNGEN.values())

    class _Attrappe:
        """Statt einer laufenden DemoTour: liefert für die Aktionen nur Platzhalter."""
        eigenes_fenster = False

        def __getattr__(self, _name):
            return lambda *a, **k: []

    schritt = next(s for s in desktop_demo.DemoTour._schritte_aufbauen(_Attrappe())
                   if s.titel.startswith("3."))
    assert "Art und Leistungsklasse" not in schritt.text
    assert "Feld „Prüfung“" in schritt.text
    assert f"„{pruefung_nach_kuerzel('ED1-Trümmerfeld').bezeichnung}“" in schritt.text
    assert f"„{pruefung_nach_kuerzel('DK1').bezeichnung}“" in schritt.text


def test_demo_ruht_waehrend_der_beenden_rueckfrage(qtbot, termin, demo_umgebung, monkeypatch):
    """Verifikation B17: Während der Rückfrage zu „Beenden“ tippt die Demo nicht weiter; nach
    „Nein“ läuft der Schritt zu Ende und die Demo bis zum Schluss."""
    import desktop_demo

    monkeypatch.setattr(desktop_demo.DemoTour, "TEMPO", 1)  # Pausen zwischen den Aktionen
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._demo_starten()
    tour = fenster._demo_tour
    tour.weiter()  # Schritt 1: der Termin-Dialog wird ausgefüllt
    qtbot.waitUntil(lambda: tour._timer.isActive(), timeout=WARTEZEIT_MS)
    waehrend = []

    def _frage(*_a, **_k):
        offen = len(tour._offen)
        qtbot.wait(1500)  # länger als jede Pause zwischen zwei Aktionen
        waehrend.append((offen, len(tour._offen), tour._timer.isActive()))
        return QMessageBox.No

    monkeypatch.setattr(QMessageBox, "question", _frage)
    tour._panel.beenden_btn.click()
    assert waehrend and waehrend[0][0] == waehrend[0][1] and not waehrend[0][2]
    assert not tour.ist_beendet and tour._timer.isActive()
    monkeypatch.setattr(desktop_demo.DemoTour, "TEMPO", 0)
    qtbot.waitUntil(lambda: not tour._offen, timeout=WARTEZEIT_MS)
    tour.beenden()


def test_demopruefung_beenden_mitten_in_der_ergebniserfassung(qtbot, termin, demo_umgebung, monkeypatch):
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._demo_starten()
    tour = fenster._demo_tour
    _demo_bis(tour, "8.")
    assert fenster.ergebnis_tab.hat_ungespeicherte_aenderungen()
    demo_ordner = os.path.dirname(tour.pfad)

    # Nachtest 2 (N9): „Beenden“ fragt nach (Vorgabe „Nein“); „Nein“ lässt die Demo weiterlaufen.
    antworten, vorgaben = [QMessageBox.No, QMessageBox.Yes], []
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: vorgaben.append(a[4]) or antworten.pop(0))
    qtbot.mouseClick(tour._panel.beenden_btn, Qt.MouseButton.LeftButton)
    assert not tour.ist_beendet and fenster._demo_tour is tour
    assert vorgaben == [QMessageBox.No]
    qtbot.mouseClick(tour._panel.beenden_btn, Qt.MouseButton.LeftButton)

    assert tour.ist_beendet and fenster._demo_tour is None
    assert fenster.conn is conn
    assert not fenster.ergebnis_tab.hat_ungespeicherte_aenderungen()
    assert not os.path.exists(demo_ordner)


def test_demo_schritt_zurueck_spielt_den_vorigen_schritt_neu_ab(qtbot, termin, demo_umgebung):
    """UX-Test 2026-11, T12 (Marco 04.11.2026, ersetzt R4): „Schritt zurück“ stellt den Stand vor
    dem vorigen Schritt wieder her und spielt ihn noch einmal ab - auch ungespeicherte
    Ergebnisse werden zurückgenommen. Vor dem Demo-Termin bleibt es bei „Vorheriger Text“; die
    Demo läuft danach bis zum Ende."""
    from db import list_teilnehmer

    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._demo_starten()
    tour = fenster._demo_tour
    panel = tour._panel

    _demo_bis(tour, "3.")
    assert panel.zurueck_btn.text() == "Vorheriger Text"  # beim Anlegen des Termins nur Text
    _demo_bis(tour, "5.")
    assert panel.zurueck_btn.text() == "Schritt zurück"
    assert all(t["startnummer"] is not None for t in list_teilnehmer(tour.conn))

    # Zurück aus Schritt 5: Schritt 4 läuft neu, die Startnummern sind wieder weg. Enter danach
    # nimmt nicht noch einen Schritt zurück (Fokus auf „Weiter“, Verifikation B9).
    panel.zurueck_btn.setFocus()
    panel.zurueck_btn.click()
    assert tour._schritte[tour._index].titel.startswith("4.")
    assert panel.focusWidget() is panel.weiter_btn
    anzahl = len(list_teilnehmer(tour.conn))
    assert anzahl and all(t["startnummer"] is None for t in list_teilnehmer(tour.conn))
    assert len(panel._verlauf) == tour._index + 1

    # Ungespeicherte Ergebnisse (Schritt 8/9) werden mit zurückgenommen, auch bei einer offenen
    # Schreib-Transaktion.
    _demo_bis(tour, "9.")
    assert fenster.ergebnis_tab.hat_ungespeicherte_aenderungen()
    tour.conn.execute("UPDATE veranstaltung SET ort = 'offen'")
    panel.zurueck_btn.click()
    assert panel.weiter_btn.isEnabled()
    assert tour._schritte[tour._index].titel.startswith("8.")
    assert len(list_teilnehmer(tour.conn)) == anzahl

    # Danach läuft die Demo normal bis zum Ende (inkl. Speichern und PDF).
    _demo_bis(tour, None)
    assert tour.ist_beendet and fenster.conn is conn and tour._stand == {}


def test_demo_schritt_zurueck_nach_ungespeicherten_ergebnissen(qtbot, termin, demo_umgebung):
    """Abschluss-QS B11, K1: Zwischen „Ergebnisse eintragen“ und „Speichern“ stehen die Punkte
    nur in der Tabelle - „Schritt zurück“ aus Schritt 10 und 11 geht deshalb zu Schritt 8, und
    die Demo findet danach wie gewohnt das Stechen und läuft bis zum Ende."""
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._demo_starten()
    tour = fenster._demo_tour
    panel = tour._panel

    for von in ("10.", "11."):
        _demo_bis(tour, von)
        panel.zurueck_btn.click()
        assert tour._schritte[tour._index].titel.startswith("8.")
    _demo_bis(tour, "12.")
    panel.zurueck_btn.click()  # Ziel nach dem Speichern: der vorige Schritt
    assert tour._schritte[tour._index].titel.startswith("11.")
    _demo_bis(tour, None)
    assert tour.ist_beendet


def test_demopruefung_endet_beim_schliessen_des_fensters(qtbot, termin, demo_umgebung):
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._demo_starten()
    tour = fenster._demo_tour
    _demo_bis(tour, "3.")  # Teilnehmer-Dialog ist offen
    demo_ordner = os.path.dirname(tour.pfad)

    assert fenster.close()

    assert tour.ist_beendet
    assert fenster.conn is conn
    assert not os.path.exists(demo_ordner)


def test_demopruefung_aus_startdialog_mit_eigenem_fenster(qtbot, demo_umgebung):
    from desktop_demo import DemoTour

    tour = DemoTour(fenster_fabrik=HauptFenster)
    beendet = []
    tour.beendet.connect(lambda: beendet.append(True))
    tour.starten()
    fenster = tour._fenster
    assert fenster.isVisible() and fenster._demo_tour is tour
    assert fenster.windowTitle().startswith("DEMO – ")
    demo_ordner = os.path.dirname(tour.pfad)

    _demo_bis(tour, None)

    assert beendet == [True]
    assert not fenster.isVisible()
    assert not os.path.exists(demo_ordner)


def test_demopruefung_erklaerfenster_zeigt_nur_klartext(qtbot, termin, demo_umgebung):
    """S-1: Texte im Erklärfenster werden nie als HTML gedeutet."""
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._demo_starten()
    tour = fenster._demo_tour
    labels = tour._panel.findChildren(QLabel)
    assert labels and all(label.textFormat() == Qt.PlainText for label in labels)
    tour.beenden()


def test_demo_ohne_termin_eigene_schleife_endet_beim_schliessen_ueber_das_x(qtbot, demo_umgebung):
    """Verifikation 04.10.2026, Befund 4: Start aus dem Startdialog (eigene Ereignisschleife)
    und Schließen des Demo-Fensters über das X - die Schleife endet, der Temp-Ordner ist
    weg und quitOnLastWindowClosed ist wiederhergestellt."""
    from PySide6.QtCore import QTimer

    from desktop_demo import demo_ohne_termin_ausfuehren

    temp, _termine = demo_umgebung
    anwendung = QApplication.instance()
    vorher = anwendung.quitOnLastWindowClosed()
    fenster = []

    def fabrik(conn, pfad, demo=False):
        neues = HauptFenster(conn, pfad, demo=demo)
        fenster.append(neues)
        QTimer.singleShot(0, neues.close)  # läuft erst in der Schleife der Demo
        return neues

    demo_ohne_termin_ausfuehren(fabrik)

    assert len(fenster) == 1
    assert fenster[0]._demo_tour is None
    assert anwendung.quitOnLastWindowClosed() == vorher
    assert list(temp.iterdir()) == []


def test_demo_fragt_in_schritt_2_nach_ungespeicherten_ergebnissen_im_eigenen_termin(
    qtbot, termin, demo_umgebung, monkeypatch
):
    """Verifikation 04.10.2026, Befund 5: Während Schritt 1 im eigenen Termin eingetippte
    Ergebnisse gehen beim Umschalten auf den Demo-Termin nicht still verloren."""
    conn, pfad = termin
    tid = add_teilnehmer(conn, NeuerTeilnehmer(
        nachname="Echt", vorname="Erika", rufname_hund="Bello", art="ED", stufe=1, disziplin="Trümmerfeld"))
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._demo_starten()
    tour = fenster._demo_tour
    _demo_bis(tour, "1.")
    ergebnis_tab = fenster.ergebnis_tab
    ergebnis_tab.punkte_eintragen(ergebnis_tab.zeile_von(tid), "Trümmerfeld", "50", "30")
    fragen = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: fragen.append(a[1]) or QMessageBox.Yes)

    tour.weiter()

    assert fragen == ["Ungespeicherte Ergebnisse"]
    assert get_ergebnis(conn, tid)["suche_truemmerfeld"] == 50
    assert fenster.conn is tour.conn
    tour.beenden()


def test_demo_tippt_zeichen_fuer_zeichen_und_weiter_fuehrt_sofort_zu_ende(qtbot, termin, demo_umgebung, monkeypatch):
    import demo_daten
    import desktop_demo

    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._demo_starten()
    tour = fenster._demo_tour
    monkeypatch.setattr(desktop_demo.DemoTour, "TEMPO", 1.0)

    tour.weiter()  # Schritt 1 beginnt zu tippen
    dialog = tour._dialog
    verein = demo_daten.VERANSTALTUNG["verein"]
    assert dialog.verein.text() != verein  # erst ein Teil getippt
    qtbot.waitUntil(lambda: len(dialog.verein.text()) >= 3, timeout=WARTEZEIT_MS)
    assert verein.startswith(dialog.verein.text())

    tour._alles_sofort()

    assert dialog.verein.text() == verein
    assert dialog.meldestelle.toPlainText() == demo_daten.VERANSTALTUNG["meldestelle"]
    tour.beenden()


def test_demo_haelt_in_schritt_2_an_wenn_ergebnisse_im_eigenen_termin_nicht_speicherbar(
    qtbot, termin, demo_umgebung, monkeypatch
):
    """Gegenprüfung 04.10.2026, Befund 5: „Nein“ auf „Trotzdem weitermachen?“ hält die Demo
    an; nach „Beenden“ ist der eigene Termin mit den Eingaben wieder da."""
    conn, pfad = termin
    tid = add_teilnehmer(conn, NeuerTeilnehmer(
        nachname="Echt", vorname="Erika", rufname_hund="Bello", art="ED", stufe=1, disziplin="Trümmerfeld"))
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._demo_starten()
    tour = fenster._demo_tour
    _demo_bis(tour, "1.")
    ergebnis_tab = fenster.ergebnis_tab
    ergebnis_tab.punkte_eintragen(ergebnis_tab.zeile_von(tid), "Trümmerfeld", suche="50")  # nur Suche - lässt sich nicht speichern
    fragen = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *a, **k: fragen.append(a[1]) or (QMessageBox.Yes if len(fragen) == 1 else QMessageBox.No),
    )

    tour.weiter()

    assert fragen == ["Ungespeicherte Ergebnisse", "Nicht alle Ergebnisse gespeichert"]
    assert not tour._panel.weiter_btn.isEnabled()
    assert "Die Demo hält hier an" in tour._panel.hinweis_label.text()
    assert fenster.conn is conn  # noch nicht auf den Demo-Termin umgeschaltet

    tour.beenden()

    assert fenster.conn is conn
    assert fenster.ergebnis_tab.hat_ungespeicherte_aenderungen()  # Eingabe nicht verloren
    assert fenster.demo_btn.isEnabled() and fenster.wechseln_btn.isEnabled()


@pytest.mark.parametrize("antwort, angehalten", [(QMessageBox.Cancel, True), (QMessageBox.Discard, False)])
def test_demo_schritt_2_abbrechen_oder_verwerfen(qtbot, termin, demo_umgebung, monkeypatch, antwort, angehalten):
    """Desktop-Prüfung 14.10.2026, Teil 8 Nr. 2 / Teil 10 Nr. 8: Beim Demo-Start wird nicht
    mehr gefragt; in Schritt 2 hält „Abbrechen“ die Demo an, „Verwerfen“ schaltet ohne
    Speichern auf den Demo-Termin um."""
    conn, pfad = termin
    tid = add_teilnehmer(conn, NeuerTeilnehmer(
        nachname="Echt", vorname="Erika", rufname_hund="Bello", art="ED", stufe=1, disziplin="Trümmerfeld"))
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    ergebnis_tab = fenster.ergebnis_tab
    ergebnis_tab.punkte_eintragen(ergebnis_tab.zeile_von(tid), "Trümmerfeld", "50", "30")
    fragen = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: fragen.append(a[1]) or antwort)

    fenster._demo_starten()
    assert fragen == []  # keine Rückfrage beim Start
    tour = fenster._demo_tour
    _demo_bis(tour, "1.")
    tour.weiter()

    assert fragen == ["Ungespeicherte Ergebnisse"]
    if angehalten:
        assert fenster.conn is conn
        assert "Die Demo hält hier an" in tour._panel.hinweis_label.text()
    else:
        assert fenster.conn is not conn
    tour.beenden()
    assert get_ergebnis(conn, tid)["suche_truemmerfeld"] is None  # nie gespeichert


def test_demo_erklaerfenster_bleibt_im_bildschirm_und_springt_nicht_doppelt(
    qtbot, termin, demo_umgebung, monkeypatch
):
    """Desktop-Prüfung 14.10.2026, Teil 10 Nr. 1 und 2: in jedem Schritt vollständig im
    verfügbaren Bildschirmbereich, und je „Weiter“ höchstens ein Ortswechsel."""
    import desktop_demo
    from PySide6.QtWidgets import QWidget

    verschiebungen = []

    def zaehlen(panel, *args):
        verschiebungen.append(args)
        QWidget.move(panel, *args)

    monkeypatch.setattr(desktop_demo.DemoPanel, "move", zaehlen)
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._demo_starten()
    tour = fenster._demo_tour
    while not tour.ist_beendet and tour._index + 1 < len(tour._schritte):
        verschiebungen.clear()
        tour.weiter()
        titel = tour._schritte[tour._index].titel
        panel = tour._panel
        bildschirm = panel.screen().availableGeometry()
        assert panel.frameGeometry().bottom() <= bildschirm.bottom(), titel
        assert panel.frameGeometry().top() >= bildschirm.top(), titel
        assert len(verschiebungen) <= 2, (titel, verschiebungen)  # höchstens Ausweichen + Verankern
    tour.beenden()


def test_demo_erklaerfenster_waechst_mit_dem_hinweis(qtbot):
    """A4-Prüfung am echten Windows (Marco 01.11.2026): kam während eines Schritts
    „Gespeichert unter …“ samt „PDF öffnen“ dazu, wuchs das Fenster nicht mit und der
    Erklärtext war mitten in der Zeile abgeschnitten."""
    import desktop_demo
    from PySide6.QtWidgets import QWidget

    eltern = QWidget()
    qtbot.addWidget(eltern)
    panel = desktop_demo.DemoPanel(eltern)
    schritt = desktop_demo.DemoSchritt("13. Ergebnisliste als PDF", "Erklärung mit vielen Wörtern. " * 25)
    panel.anzeigen(13, 15, schritt, letzter=False)
    qtbot.waitExposed(panel)
    hoehe_vorher, breite_vorher = panel.height(), panel.width()
    panel.hinweis("Gespeichert unter: C:\\Users\\Name\\AppData\\Local\\Temp\\shs_demo_abc\\"
                  "Hundefreunde-Musterstadt\\Ergebnisliste_2026-11-01.pdf")
    panel.extra("PDF öffnen", lambda: None)
    qtbot.wait(50)
    assert panel.height() > hoehe_vorher
    assert panel.width() == breite_vorher  # nicht breiter (sonst ragte es rechts hinaus)
    text = panel.text_label
    assert text.height() >= text.heightForWidth(text.width())
    panel.schliessen()


def test_demo_weiter_knopf_bleibt_an_derselben_stelle(qtbot, termin, demo_umgebung):
    """Marco 01.11.2026 (in 1.0.52 beobachtet): Erklärfenster änderten je Schritt Größe und
    Lage, man musste „Weiter“ jedes Mal mit der Maus suchen. Jetzt bleiben Unterkante und
    Breite fest, das Fenster wächst nach oben - solange es nicht ausweichen muss."""
    from PySide6.QtCore import QPoint

    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._demo_starten()
    tour = fenster._demo_tour
    panel = tour._panel
    panel.ausweichen = lambda ziel: None  # nur die Größenänderung prüfen, nicht das Ausweichen
    lagen, hoehen = set(), set()
    while not tour.ist_beendet and tour._index + 1 < len(tour._schritte) - 1:
        tour.weiter()
        rechts_unten = panel.weiter_btn.mapToGlobal(QPoint(panel.weiter_btn.width(), panel.weiter_btn.height()))
        lagen.add((rechts_unten.x(), rechts_unten.y()))
        hoehen.add(panel.height())
    tour.beenden()
    assert len(hoehen) > 1  # die Schritte sind unterschiedlich lang ...
    assert len(lagen) == 1, lagen  # ... „Weiter“ steht trotzdem immer an derselben Stelle


def test_demo_erklaerfenster_bleibt_wo_der_anwender_es_hinschiebt(qtbot):
    """Marco 01.11.2026: verschiebt der Anwender das Erklärfenster oder zieht es selbst am
    unteren Rand größer, gilt die neue Unterkante - das Programm schiebt es nicht zurück."""
    import desktop_demo
    from PySide6.QtWidgets import QWidget

    eltern = QWidget()
    qtbot.addWidget(eltern)
    panel = desktop_demo.DemoPanel(eltern)
    kurz = desktop_demo.DemoSchritt("1. Kurz", "Wenig Text.")
    lang = desktop_demo.DemoSchritt("2. Lang", "Erklärung mit vielen Wörtern. " * 25)
    panel.anzeigen(1, 2, kurz, letzter=False)
    qtbot.waitExposed(panel)
    frei = panel.screen().availableGeometry()
    # Vom Anwender nach links gezogen, Unterkante 100 px über dem Bildschirmrand (Platz zum
    # Wachsen nach oben und für die 30 px weiter unten).
    panel.move(frei.left() + 40, frei.bottom() - 100 - panel.frameGeometry().height())
    unten = panel.frameGeometry().bottom()
    assert unten - 400 > frei.top()
    panel.anzeigen(2, 2, lang, letzter=False)
    assert panel.frameGeometry().bottom() == unten  # wächst nach oben, Unterkante bleibt
    # Selbst am unteren Rand größer gezogen: bleibt so, die neue Unterkante gilt.
    panel.resize(panel.width(), panel.height() + 30)
    assert panel.frameGeometry().bottom() == unten + 30
    panel.anzeigen(1, 2, kurz, letzter=False)
    assert panel.frameGeometry().bottom() == unten + 30
    panel.schliessen()


def test_demo_schritt_4_prueft_eigene_eingaben(qtbot, termin, demo_umgebung, monkeypatch):
    """Teil 10 Nr. 3: unvollständige eigene Eingaben im Demo-Dialog halten die Demo mit
    Hinweis an, statt einen Teilnehmer ohne Pflichtangaben zu speichern."""
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._demo_starten()
    tour = fenster._demo_tour
    _demo_bis(tour, "3.")
    tour._alles_sofort()
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    tour._dialog.vorname.setText("")
    tour.weiter()
    assert "lassen sich so nicht übernehmen" in tour._panel.hinweis_label.text()
    assert not tour._panel.weiter_btn.isEnabled()
    tour.beenden()


def test_demo_holt_den_reiter_nach_vorn(qtbot, termin, demo_umgebung):
    """Teil 10 Nr. 4: hat der Anwender zwischendurch den Reiter gewechselt, zeigt der
    nächste Schritt wieder den richtigen."""
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._demo_starten()
    tour = fenster._demo_tour
    _demo_bis(tour, "3.")
    tour._alles_sofort()
    fenster._tabs.setCurrentWidget(fenster.zeitplan_tab)
    tour.weiter()  # Schritt 4 "Weitere Meldungen"
    assert fenster._tabs.currentWidget() is fenster.teilnehmer_tab
    tour.beenden()


def test_demo_knopf_holt_erklaerfenster_zurueck(qtbot, termin, demo_umgebung, monkeypatch):
    """Teil 10 Nr. 9."""
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._demo_starten()
    tour = fenster._demo_tour
    tour._panel.hide()
    fenster.demo_btn.click()
    assert tour._panel.isVisible()
    tour.beenden()
    assert fenster.demo_btn.text() == "Demoprüfung"


def test_demo_startfehler_im_startdialog_weg_fuehrt_zurueck(qtbot, monkeypatch):
    """Teil 10 Nr. 5: Startfehler aus dem Startdialog beendet nicht mehr das Programm."""
    import app as app_modul

    aufrufe = []

    class _Start:
        def __init__(self):
            aufrufe.append("start")
            self.demo_angefordert = len(aufrufe) == 1
            self.pfad = None

        def exec(self):
            return QDialog.Accepted if len(aufrufe) == 1 else QDialog.Rejected

    def kaputt(_fabrik):
        raise OSError(28, "No space left on device")

    meldungen = []
    monkeypatch.setattr(app_modul, "StartDialog", _Start)
    monkeypatch.setattr(app_modul, "demo_ohne_termin_ausfuehren", kaputt)
    monkeypatch.setattr(app_modul.QMessageBox, "warning", lambda *a, **k: meldungen.append(a[1]))

    assert app_modul._startdialog_schleife() is None
    assert meldungen == ["Demoprüfung nicht möglich"]
    assert aufrufe == ["start", "start"]


def test_demo_startfehler_meldet_und_behaelt_den_termin(qtbot, termin, demo_umgebung, monkeypatch):
    """Teil 10 Nr. 5: Startfehler ergibt eine Meldung, keine Statusmeldung „beendet“."""
    import desktop_demo

    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)

    def kaputt(*_a, **_k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(desktop_demo, "init_db", kaputt)
    meldungen = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: meldungen.append(a[1]))
    fenster._demo_starten()
    assert meldungen == ["Demoprüfung nicht möglich"]
    assert fenster.conn is conn
    assert "Demoprüfung beendet" not in fenster.statusBar().currentMessage()
    assert fenster.wechseln_btn.isEnabled()


def test_demo_beenden_gibt_knoepfe_auch_nach_fehler_frei(qtbot, termin, demo_umgebung, monkeypatch):
    """Gegenprüfung 04.10.2026, Befund 4."""
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._demo_starten()
    tour = fenster._demo_tour
    _demo_bis(tour, "3.")
    demo_ordner = os.path.dirname(tour.pfad)

    def _kaputt(*args, **kwargs):
        raise RuntimeError("simulierter Fehler")

    monkeypatch.setattr(fenster, "_termin_setzen", _kaputt)
    with pytest.raises(RuntimeError):
        tour.beenden()

    assert fenster.demo_btn.isEnabled() and fenster.wechseln_btn.isEnabled()
    assert not os.path.exists(demo_ordner)
    assert not tour._panel.isVisible()


def test_demo_wartezeit_waechst_mit_der_textlaenge(qtbot, termin, demo_umgebung, monkeypatch):
    """UX-Test 03.11.2026, X6: bei langen Erklärtexten mehr als die 10 s, höchstens 40 s."""
    import desktop_demo

    import math

    tour = _demo_mit_countdown(qtbot, termin, monkeypatch, sekunden=10)
    je_wort = 0.35
    monkeypatch.setattr(desktop_demo.DemoTour, "LESEZEIT_JE_WORT_S", je_wort)
    hoechstens = desktop_demo.DemoTour.LESEZEIT_MAX_S
    schritt = tour._schritte[tour._index]
    woerter = len(f"{schritt.titel} {schritt.text}".split())
    assert woerter * je_wort > 10  # Begrüßung ist lang
    assert tour._wartezeit() == max(10, min(hoechstens, math.ceil(woerter * je_wort)))
    monkeypatch.setattr(schritt, "text", "kurz")
    assert tour._wartezeit() == 10
    tour.beenden()


def test_demo_vorheriger_text_haelt_an_und_kehrt_zurueck(qtbot, termin, demo_umgebung, monkeypatch):
    """UX-Test 03.11.2026, X6 (Marco: nur Text zurück): „Vorheriger Text“ zeigt die frühere
    Erklärung und hält das automatische Weiter an; „Aktueller Schritt“ führt zurück, ohne
    weiterzuschalten. Enter wirkt wie „Weiter“."""
    tour = _demo_mit_countdown(qtbot, termin, monkeypatch, sekunden=3)
    panel = tour._panel
    assert not panel.zurueck_btn.isVisible()
    tour.weiter()
    assert tour._index == 1 and panel.zurueck_btn.isVisible()
    aktueller_titel = panel.titel_label.text()

    panel.zurueck_btn.click()
    assert panel.schritt_label.text().startswith("Rückblick")
    assert panel.titel_label.text() == tour._schritte[0].titel
    assert not tour._countdown.isActive()
    assert panel.weiter_btn.text() == "Aktueller Schritt"

    panel.weiter_btn.click()
    assert tour._index == 1 and panel.titel_label.text() == aktueller_titel
    # Verifikation A6, Befund 2: danach zählt der Countdown wieder (Schritt ist fertig).
    assert tour._countdown.isActive() and not panel.pause_label.isVisible()

    # Verdrahtung des Kürzels selbst (offscreen kommt ein simulierter Tastendruck nicht
    # verlässlich beim Fenster-Kürzel an).
    (enter,) = [k for k in panel.findChildren(QShortcut) if k.key() == QKeySequence(Qt.Key_Return)]
    enter.activated.emit()
    assert tour._index == 2
    tour.beenden()


def test_demo_rueckblick_randfaelle(qtbot, termin, demo_umgebung, monkeypatch):
    """Verifikation A6, Befunde 1, 3, 4, 5: Fehler im Rückblick führt zum aktuellen Schritt
    zurück; „Automatisch weiter“ umschalten startet keinen Countdown über altem Text; die
    Hinweiszeile des laufenden Schritts ist im Rückblick ausgeblendet; Enter löst den
    fokussierten Knopf aus."""
    tour = _demo_mit_countdown(qtbot, termin, monkeypatch, sekunden=3)
    panel = tour._panel
    tour.weiter()
    tour.weiter()
    assert tour._index == 2
    panel.hinweis("Gespeichert unter X")
    panel.zurueck_btn.click()
    assert not panel.hinweis_label.isVisible()
    panel.zurueck_btn.click()  # zwei Schritte zurück, dann gesperrt
    assert panel.titel_label.text() == tour._schritte[0].titel and not panel.zurueck_btn.isEnabled()

    panel.auto_box.setChecked(False)
    panel.auto_box.setChecked(True)
    assert not tour._countdown.isActive()

    panel.fehler("Kaputt")
    assert panel.titel_label.text() == tour._schritte[2].titel
    assert "Kaputt" in panel.hinweis_label.text() and not panel.zurueck_btn.isVisible()
    tour.beenden()


def test_demo_enter_loest_fokussierten_knopf_aus(qtbot, termin, demo_umgebung, monkeypatch):
    tour = _demo_mit_countdown(qtbot, termin, monkeypatch, sekunden=3)
    panel = tour._panel
    tour.weiter()
    panel.zurueck_btn.setFocus()
    monkeypatch.setattr(panel, "focusWidget", lambda: panel.zurueck_btn)
    panel._enter_gedrueckt()
    assert tour._index == 1 and panel.im_rueckblick()
    tour.beenden()


def test_demo_zaehlt_nach_fertigem_schritt_herunter_und_schaltet_weiter(qtbot, termin, demo_umgebung, monkeypatch):
    """Marcos Wunsch 05.10.2026: Ist ein Schritt fertig, zählt „Weiter“ herunter und
    schaltet dann von allein weiter (Tick hier direkt statt nach je 1 s)."""
    tour = _demo_mit_countdown(qtbot, termin, monkeypatch, sekunden=3)
    assert tour._index == 0 and tour._countdown.isActive()
    assert tour._panel.weiter_btn.text() == "Weiter (3)"

    tour._countdown_tick()
    assert tour._panel.weiter_btn.text() == "Weiter (2)"
    tour._countdown_tick()
    tour._countdown_tick()

    assert tour._index == 1
    # Neuer Schritt fertig (TEMPO 0) -> frischer Countdown.
    assert tour._countdown.isActive() and tour._panel.weiter_btn.text() == "Weiter (3)"
    tour.beenden()


def test_demo_countdown_startet_erst_wenn_der_schritt_fertig_ist(qtbot, termin, demo_umgebung, monkeypatch):
    import desktop_demo

    monkeypatch.setattr(desktop_demo.DemoTour, "TEMPO", 1.0)
    tour = _demo_mit_countdown(qtbot, termin, monkeypatch)
    tour._countdown_stoppen()
    tour._schritt_zeigen(1)  # „1. Neuen Termin anlegen“ tippt mit Pausen
    assert tour._offen and not tour._countdown.isActive()
    assert tour._panel.weiter_btn.text() == "Weiter"

    tour._alles_sofort()

    assert not tour._offen and tour._countdown.isActive()
    tour.beenden()


def test_demo_klick_auf_weiter_waehrend_des_countdowns_geht_genau_einen_schritt(qtbot, termin, demo_umgebung, monkeypatch):
    tour = _demo_mit_countdown(qtbot, termin, monkeypatch)
    tour._countdown_tick()

    qtbot.mouseClick(tour._panel.weiter_btn, Qt.MouseButton.LeftButton)

    assert tour._index == 1
    assert tour._rest == 3 and tour._panel.weiter_btn.text() == "Weiter (3)"
    tour.beenden()


def test_demo_automatisch_weiter_abschaltbar(qtbot, termin, demo_umgebung, monkeypatch):
    tour = _demo_mit_countdown(qtbot, termin, monkeypatch)
    assert tour._panel.auto_box.isChecked()

    tour._panel.auto_box.setChecked(False)
    assert not tour._countdown.isActive() and tour._panel.weiter_btn.text() == "Weiter"
    tour.weiter()
    assert tour._index == 1 and not tour._countdown.isActive()

    tour._panel.auto_box.setChecked(True)
    assert tour._countdown.isActive()
    tour.beenden()


def test_demo_kein_countdown_im_letzten_schritt_und_nach_fehler(qtbot, termin, demo_umgebung, monkeypatch):
    tour = _demo_mit_countdown(qtbot, termin, monkeypatch)
    _demo_bis(tour, "17.")
    assert not tour._countdown.isActive()
    assert tour._panel.weiter_btn.text() == "Fertig"
    tour.beenden()

    tour = _demo_mit_countdown(qtbot, termin, monkeypatch)
    protokolliert, angezeigt = [], []
    monkeypatch.setattr("desktop_gemeinsam.fehler_protokollieren", protokolliert.append)
    panel_fehler = tour._panel.fehler
    monkeypatch.setattr(tour._panel, "fehler", lambda text: (angezeigt.append(text), panel_fehler(text)))
    fehler = KeyError("Albers")
    tour._fehler_zeigen(fehler)
    # Teil 10 Nr. 6: unerwartete Fehler mit Typ anzeigen und ins Protokoll.
    assert protokolliert == [fehler] and "KeyError: 'Albers'" in angezeigt[0]
    assert not tour._countdown.isActive() and not tour._panel.weiter_btn.isEnabled()
    tour._panel.auto_box.setChecked(False)
    tour._panel.auto_box.setChecked(True)
    assert not tour._countdown.isActive()
    tour.beenden()


def test_demo_pdf_oeffnen_haelt_den_countdown_an(qtbot, termin, demo_umgebung, monkeypatch):
    geoeffnet = []
    monkeypatch.setattr("desktop_gemeinsam.QDesktopServices.openUrl", lambda url: geoeffnet.append(url) or True)
    tour = _demo_mit_countdown(qtbot, termin, monkeypatch)
    _demo_bis(tour, "13.")
    assert tour._countdown.isActive() and tour._panel.extra_btn.isVisible()

    qtbot.mouseClick(tour._panel.extra_btn, Qt.MouseButton.LeftButton)

    assert len(geoeffnet) == 1
    assert not tour._countdown.isActive() and tour._panel.weiter_btn.text() == "Weiter"
    # Verifikation 05.10.2026, Punkt 4: sichtbarer Hinweis, warum es nicht weitergeht.
    assert not tour._panel.pause_label.isHidden()
    assert "angehalten" in tour._panel.pause_label.text()
    # Der Speicherort-Hinweis bleibt dabei stehen.
    assert "Gespeichert unter" in tour._panel.hinweis_label.text()

    tour.weiter()
    assert tour._index == 14 and tour._panel.pause_label.isHidden() and tour._countdown.isActive()
    tour.beenden()


def test_demo_countdown_wartet_solange_ein_sperrendes_fenster_offen_ist(qtbot, termin, demo_umgebung, monkeypatch):
    """Verifikation 05.10.2026, Befund 1: Öffnet der Anwender selbst ein modales Fenster,
    darf die Demo darunter nicht weiterlaufen."""
    tour = _demo_mit_countdown(qtbot, termin, monkeypatch, sekunden=2)
    modal = {"offen": True}
    monkeypatch.setattr("desktop_demo.QApplication.activeModalWidget", lambda: object() if modal["offen"] else None)

    for _ in range(5):
        tour._countdown_tick()
    # Zahl steht; nach dem Schließen bleiben mindestens AUTO_WEITER_NACH_MODAL_S (3).
    assert tour._index == 0 and tour._panel.weiter_btn.text() == "Weiter (3)"

    modal["offen"] = False
    tour._countdown_tick()  # erster Tick danach startet nur den Takt neu
    assert tour._panel.weiter_btn.text() == "Weiter (3)"
    tour._countdown_tick()
    tour._countdown_tick()
    assert tour._index == 0
    tour._countdown_tick()
    assert tour._index == 1
    tour.beenden()


def test_demo_eigene_eingabe_im_demo_dialog_haelt_den_countdown_an(qtbot, termin, demo_umgebung, monkeypatch):
    """Verifikation 05.10.2026, Punkt 5: Tippt der Anwender selbst in den Dialog der Demo,
    greift das automatische Weiter nicht mitten in seine Eingabe ein."""
    tour = _demo_mit_countdown(qtbot, termin, monkeypatch)
    tour.weiter()  # „1. Neuen Termin anlegen“ - Dialog offen, Schritt fertig (TEMPO 0)
    assert tour._dialog is not None and tour._countdown.isActive()
    feld = tour._dialog.findChildren(QLineEdit)[0]

    # Reine Umschalttasten (z. B. Alt für Alt+Tab) sind keine Eingabe.
    for taste in (Qt.Key.Key_Alt, Qt.Key.Key_Shift, Qt.Key.Key_Control):
        qtbot.keyClick(feld, taste)
    assert tour._countdown.isActive() and not tour._angehalten

    qtbot.keyClick(feld, Qt.Key.Key_A)

    assert not tour._countdown.isActive() and tour._angehalten
    assert not tour._panel.pause_label.isHidden()
    # Bewusst wieder anhaken hebt das Anhalten auf.
    tour._panel.auto_box.setChecked(False)
    tour._panel.auto_box.setChecked(True)
    assert tour._countdown.isActive() and tour._panel.pause_label.isHidden()
    tour.beenden()


def test_demo_entfernt_ihren_ereignisfilter_beim_beenden(qtbot, termin, demo_umgebung, monkeypatch):
    entfernt = []
    tour = _demo_mit_countdown(qtbot, termin, monkeypatch)
    original = QApplication.instance().removeEventFilter
    monkeypatch.setattr(
        QApplication.instance(), "removeEventFilter", lambda obj: entfernt.append(obj) or original(obj)
    )

    tour.beenden()

    assert tour in entfernt


def test_demo_beenden_waehrend_des_countdowns(qtbot, termin, demo_umgebung, monkeypatch):
    tour = _demo_mit_countdown(qtbot, termin, monkeypatch)
    assert tour._countdown.isActive()

    tour.beenden()

    assert tour.ist_beendet and not tour._countdown.isActive()
    tour._countdown_tick()  # ein verspäteter Tick darf nichts mehr auslösen
    assert tour.ist_beendet


def test_demo_weiter_ueberschreibt_tempo_nicht(qtbot, termin, demo_umgebung):
    """Gegenprüfung 04.10.2026, Befund 3: TEMPO bleibt ein Klassenwert."""
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._demo_starten()
    tour = fenster._demo_tour
    tour.weiter()
    tour.weiter()
    assert "TEMPO" not in vars(tour)
    tour.beenden()


def test_demo_reste_aufraeumen_loescht_nur_alte_demo_ordner(demo_umgebung):
    import time

    from desktop_demo import demo_reste_aufraeumen

    temp, _termine = demo_umgebung
    alt = temp / "shs_demo_alt"
    jung = temp / "shs_demo_jung"
    fremd = temp / "anderes_programm"
    for ordner in (alt, jung, fremd):
        ordner.mkdir()
        (ordner / "Ergebnisliste.pdf").write_bytes(b"%PDF")
    vor_zwei_stunden = time.time() - 2 * 3600
    for ordner in (alt, fremd):
        os.utime(ordner, (vor_zwei_stunden, vor_zwei_stunden))

    demo_reste_aufraeumen()

    assert not alt.exists()
    assert jung.exists() and fremd.exists()


def test_demo_weiter_knopf_symbol_rechts(qtbot):
    from PySide6.QtWidgets import QWidget

    from desktop_demo import DemoPanel

    eltern = QWidget()
    qtbot.addWidget(eltern)
    panel = DemoPanel(eltern)
    assert panel.windowTitle() == "Demoprüfung"
    assert panel.weiter_btn.layoutDirection() == Qt.RightToLeft
    assert panel.weiter_btn.icon().cacheKey() == symbol("chevron-right", "#FFFFFF").cacheKey()
    panel._letzter = True
    panel.countdown_anzeigen(None)
    assert panel.weiter_btn.text() == "Fertig"
    assert panel.weiter_btn.icon().cacheKey() == symbol("check", "#FFFFFF").cacheKey()
