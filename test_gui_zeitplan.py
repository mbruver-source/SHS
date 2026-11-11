"""GUI-Tests: Reiter Zeitplan und Verteilung.

Fixtures und Hilfen stehen in gui_hilfen.py (Aufteilung von test_app_gui.py, 11.11.2026)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QMessageBox
from app import HauptFenster
from db import (
    add_zeitplan_pruefungsblock,
    add_zeitplan_richter,
    get_veranstaltung,
    set_veranstaltung,
)
from desktop_zeitplan import ZeitplanTab
from db import ALLE_DISZIPLINEN
from desktop_gemeinsam import symbol
from gui_hilfen import *  # noqa: F401,F403


def test_pause_bei_allen_meldet_abweichende_uhrzeit(qtbot, termin, monkeypatch):
    """UX-Nachtest 03.10.2026, N3: weicht die Uhrzeit ab, sagt es eine Meldung. Seit dem
    UX-Test 03.11.2026 (X1) bekommt ein Richter, der vorher fertig ist, keine Pause - die
    Meldung nennt das."""
    conn, _pfad = termin
    _teilnehmer_anlegen(conn, art="ED", stufe=1, disziplin="Trümmerfeld")
    set_veranstaltung(conn, verein="V", datum="2026-11-14", zeitplan_start="09:00")
    richter = add_zeitplan_richter(conn, "Anna")
    add_zeitplan_pruefungsblock(conn, richter, "ED", 1, "Trümmerfeld", 10)
    tab = ZeitplanTab(conn)
    qtbot.addWidget(tab)

    monkeypatch.setattr("desktop_zeitplan.PauseDialog", _pause_dialog_attrappe(30, "Mittag", uhrzeit="12:00"))
    meldungen = meldungen_sammeln(monkeypatch, "information")
    tab._pause_hinzufuegen(richter)
    assert meldungen and "bei keinem Richter steht ab 12:00 Uhr noch eine Prüfung" in meldungen[0]
    assert tab.status_label.text() == "Pause bei 0 Richter(n) eingefügt."

    # Ein zweiter Richter, dessen Plan um 12:00 noch läuft: gemischte Meldung.
    zweiter = add_zeitplan_richter(conn, "Bernd")
    add_zeitplan_pruefungsblock(conn, zweiter, "ED", 1, "Trümmerfeld", 200)  # 09:00-12:20
    meldungen.clear()
    tab._pause_hinzufuegen(zweiter)
    assert "Anna: keine Pause – keine Prüfung mehr ab 12:00 Uhr" in meldungen[0]
    assert "Bernd: 12:20 Uhr" in meldungen[0]


def test_pause_nach_startzeit_eingabe_geht_nicht_verloren(qtbot, conn, monkeypatch):
    """Abschluss-QS 15.10.2026 (K-1): Startzeit tippen und direkt „Pause hinzufügen…“ - der
    verzögerte Neuaufbau wartet auf den Dialog, und die Pause landet hinter der markierten
    Zeile."""
    from PySide6.QtWidgets import QApplication

    from db import add_zeitplan_richter, list_zeitplan_eintraege

    richter_id = add_zeitplan_richter(conn, "R1")
    tab = ZeitplanTab(conn)
    qtbot.addWidget(tab)
    tab.show()
    aufgebaut = []
    original = tab.aktualisieren
    monkeypatch.setattr(tab, "aktualisieren", lambda: (aufgebaut.append(True), original())[1])
    # Fokuswechsel durch den Klick: modaler Dialog offen -> noch kein Neuaufbau.
    modal = [object()]
    monkeypatch.setattr(QApplication, "activeModalWidget", lambda: modal[0])
    tab.zeitplan_start.setText("10:00")
    tab.zeitplan_start.editingFinished.emit()
    qtbot.wait(150)
    assert aufgebaut == []
    modal[0] = None
    qtbot.waitUntil(lambda: aufgebaut == [True], timeout=WARTEZEIT_MS)

    monkeypatch.setattr("desktop_zeitplan.PauseDialog", _pause_dialog_attrappe(15, "Pause"))
    tab._pause_hinzufuegen(richter_id, None)
    assert [e["typ"] for e in list_zeitplan_eintraege(conn, richter_id)] == ["pause"]


def test_zeitplan_eintrag_bearbeiten_ohne_blockplan(qtbot, conn, monkeypatch):
    """OFFEN.md B4 (19.10.2026): Bearbeiten liest den Eintrag direkt, statt den ganzen
    Blockplan zu berechnen; der Pausen-Dialog bekommt Dauer und Bezeichnung."""
    from PySide6.QtWidgets import QListWidget, QListWidgetItem

    from db import add_zeitplan_pause, add_zeitplan_pruefungsblock, add_zeitplan_richter, zeitplan_eintrag

    richter_id = add_zeitplan_richter(conn, "R1")
    block_id = add_zeitplan_pruefungsblock(conn, richter_id, "ED", 1, "Trümmerfeld", 7)
    pause_id = add_zeitplan_pause(conn, richter_id, 20, "Mittag")
    tab = ZeitplanTab(conn)
    qtbot.addWidget(tab)

    def _kein_blockplan(_conn):
        raise AssertionError("Blockplan beim Bearbeiten berechnet")

    # raising=False: das Modul importiert die Funktion nicht mehr; die Gegenprobe mit altem Code
    # schlägt dann hier an.
    monkeypatch.setattr("desktop_zeitplan.berechne_zeitplan_bloecke", _kein_blockplan, raising=False)
    monkeypatch.setattr(tab, "aktualisieren", lambda: None)
    vorbelegung = {}
    attrappe = _pause_dialog_attrappe(25, "Mittagspause")

    def _pause_dialog(*a, **k):
        vorbelegung.update(k)
        return attrappe(*a, **k)

    monkeypatch.setattr("desktop_zeitplan.PauseDialog", _pause_dialog)
    monkeypatch.setattr("desktop_zeitplan.QInputDialog.getInt", lambda *a, **k: (9, True))

    def _liste_mit(eintrag_id):
        liste = QListWidget()
        qtbot.addWidget(liste)
        item = QListWidgetItem("x")
        item.setData(Qt.UserRole, eintrag_id)
        liste.addItem(item)
        liste.setCurrentItem(item)
        return liste

    tab._eintrag_bearbeiten(_liste_mit(pause_id))
    assert vorbelegung == {"dauer_minuten": 20, "bezeichnung": "Mittag"}
    pause = zeitplan_eintrag(conn, pause_id)
    assert (pause["dauer_minuten"], pause["bezeichnung"]) == (25, "Mittagspause")

    tab._eintrag_bearbeiten(_liste_mit(block_id))
    assert zeitplan_eintrag(conn, block_id)["dauer_minuten"] == 9


def test_feste_pause_ueber_dialog_und_beim_verteilen(qtbot, termin, monkeypatch):
    """R-B20 (Marco 05.11.2026): „genau“ im Pause-Dialog und im Verteilen-Dialog legt die
    Pause mit fester Uhrzeit an; die Liste nennt sie, und beim Neu-Verteilen ist „genau“
    wieder angehakt."""
    from db import list_zeitplan_eintraege, list_zeitplan_richter
    from desktop_dialoge import VerteilenDialog

    conn, pfad = termin
    for nr in range(1, 4):
        _teilnehmer_anlegen(conn, nachname=f"T{nr}", startnummer=nr)
    richter_id = add_zeitplan_richter(conn)
    add_zeitplan_pruefungsblock(conn, richter_id, art="ED", stufe=1, disziplin="Flächensuche", dauer_minuten=10)
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    tab = fenster.zeitplan_tab
    meldungen_sammeln(monkeypatch, "information")

    # Pause-Dialog: Block 09:00-09:30; „genau“ um 09:25 - der Block lief schon 25 Minuten,
    # die Pause folgt danach, aber mit fester Uhrzeit gespeichert.
    monkeypatch.setattr("desktop_zeitplan.PauseDialog", _pause_dialog_attrappe(10, "Kaffee", uhrzeit="09:25", genau=True))
    tab._pause_hinzufuegen(richter_id)
    pause = list_zeitplan_eintraege(conn, richter_id)[-1]
    assert (pause["bezeichnung"], pause["fest_um"]) == ("Kaffee", "09:25")
    from PySide6.QtWidgets import QListWidget

    texte = [liste.item(i).text() for liste in tab.findChildren(QListWidget) for i in range(liste.count())]
    assert any("(fest um 09:25 Uhr)" in t for t in texte)

    # Verteilen mit „genau“: die Mittagspause bekommt die feste Uhrzeit ...
    gezeigt = []

    def _exec(dialog):
        gezeigt.append(dialog)
        dialog.mit_pause.setChecked(True)
        dialog.uhrzeit.setText("09:05")
        dialog.pause_genau.setChecked(True)
        return QDialog.Accepted

    monkeypatch.setattr(VerteilenDialog, "exec", _exec)
    tab._automatisch_verteilen()
    pausen = [e for r in list_zeitplan_richter(conn) for e in list_zeitplan_eintraege(conn, r["id"])
              if e["typ"] == "pause"]
    assert [(p["bezeichnung"], p["fest_um"]) for p in pausen] == [("Mittagspause", "09:05")]
    # ... und beim nächsten Verteilen ist „genau“ vorbelegt.
    monkeypatch.setattr(VerteilenDialog, "exec", lambda dialog: gezeigt.append(dialog) or QDialog.Rejected)
    tab._automatisch_verteilen()
    assert gezeigt[-1].pause_genau.isChecked() and gezeigt[-1].pause_fest()


def test_pause_dialog_beim_bearbeiten_ohne_felder_fuer_alle(qtbot):
    """OFFEN.md B4: Beim Bearbeiten legt der Dialog „Bei allen Richtern“/Uhrzeit nicht an."""
    from PySide6.QtWidgets import QCheckBox

    from desktop_dialoge import PauseDialog

    bearbeiten = PauseDialog(None, dauer_minuten=20, bezeichnung="Mittag")
    qtbot.addWidget(bearbeiten)
    assert bearbeiten.fuer_alle is None and bearbeiten.uhrzeit is None
    assert bearbeiten.findChildren(QCheckBox) == []
    bearbeiten._pruefen_und_akzeptieren()
    assert bearbeiten.result() == QDialog.Accepted
    assert bearbeiten.werte() == {"dauer_minuten": 20, "bezeichnung": "Mittag"}

    neu = PauseDialog(None, neu=True)
    qtbot.addWidget(neu)
    assert neu.fuer_alle is not None and len(neu.findChildren(QCheckBox)) == 2
    # R-B20: „genau“ nur zusammen mit „bei allen Richtern“
    assert not neu.genau.isEnabled()
    neu.fuer_alle.setChecked(True)
    assert neu.genau.isEnabled()


def test_zeitplan_startzeit_enter_verlassen_und_vereinheitlicht(qtbot, conn, monkeypatch):
    """Teil 4 Nr. 3 und 6: Enter bzw. Verlassen des Feldes speichert, „9:5“ wird „09:05“;
    eine ungültige Eingabe verhindert PDF und Verteilen."""
    tab = ZeitplanTab(conn)
    qtbot.addWidget(tab)
    tab.show()
    tab.zeitplan_start.setText("9:5")
    qtbot.keyClick(tab.zeitplan_start, Qt.Key_Return)
    assert get_veranstaltung(conn)["zeitplan_start"] == "09:05" and tab.zeitplan_start.text() == "09:05"

    tab.zeitplan_start.setText("10:30")
    tab.zeitplan_start.editingFinished.emit()
    assert get_veranstaltung(conn)["zeitplan_start"] == "10:30"

    # Verifikation A14: bei gedrückter Maustaste (Fokuswechsel durch Klick) erst nach dem
    # Loslassen neu aufbauen, sonst wäre der geklickte Knopf schon gelöscht.
    aufgebaut = []
    monkeypatch.setattr(tab, "aktualisieren", lambda: aufgebaut.append(True))
    gedrueckt = [Qt.LeftButton, Qt.NoButton]
    monkeypatch.setattr("app.QApplication.mouseButtons", lambda: gedrueckt.pop(0) if len(gedrueckt) > 1 else gedrueckt[0])
    tab.zeitplan_start.setText("11:00")
    tab.zeitplan_start.editingFinished.emit()
    assert aufgebaut == [] and get_veranstaltung(conn)["zeitplan_start"] == "11:00"
    qtbot.waitUntil(lambda: aufgebaut == [True], timeout=WARTEZEIT_MS)
    monkeypatch.undo()

    tab.zeitplan_start.setText("25:99")
    tab.zeitplan_start.editingFinished.emit()  # still: keine Meldung, nichts gespeichert
    assert get_veranstaltung(conn)["zeitplan_start"] == "11:00"
    warnungen = meldungen_sammeln(monkeypatch, "warning", merke="titel")
    ueberall_ersetzen(monkeypatch, "_zeitplan_pdf_exportieren", lambda *a: pytest.fail("kein PDF erwartet"))
    tab._pdf_exportieren()
    tab._automatisch_verteilen()
    assert warnungen == ["Ungültige Uhrzeit", "Ungültige Uhrzeit"]


def test_zeitplan_schreibfehler_beim_anzeigen_und_startzeit(qtbot, conn, monkeypatch):
    """Desktop-Prüfung 14.10.2026, Teil 4 Nr. 4: Richter-Übernahme beim ersten Anzeigen und
    „Startzeit speichern“ melden Schreibfehler statt des allgemeinen Fehlerfensters."""
    set_veranstaltung(conn, verein="SGV", datum="2026-11-14", wertungsrichter_1="Anna")
    meldungen = []
    ueberall_ersetzen(monkeypatch, "_db_fehler_anzeigen", lambda parent, exc, *a: meldungen.append(str(exc)))
    monkeypatch.setattr("desktop_zeitplan.zeitplan_richter_aus_veranstaltung_anlegen", _schreibfehler)
    ueberall_ersetzen(monkeypatch, "_aktualisiere_veranstaltung_feld", _schreibfehler)
    tab = ZeitplanTab(conn)
    qtbot.addWidget(tab)
    tab.show()
    tab.zeitplan_start.setText("10:00")
    tab._start_speichern()

    assert meldungen == ["attempt to write a readonly database"] * 2
    assert tab.status_label.text() != "Zeitplan-Startzeit gespeichert."


def test_zeitplan_kopf_in_zwei_zeilen(qtbot, conn):
    """Marco 05.11.2026 (nach 1.0.56): Die Kopfzeile des Zeitplans war bei Schrift „Sehr groß“
    breiter als ein 1536-px-Bildschirm. Die Knöpfe stehen jetzt in einer eigenen Zeile unter den
    Einstellungen."""
    tab = ZeitplanTab(conn)
    qtbot.addWidget(tab)
    tab.show()
    qtbot.waitExposed(tab)
    assert tab.verteilen_btn.y() > tab.zeitplan_start.y() + tab.zeitplan_start.height() // 2
    # Einstellungen in einer Zeile (die Felder sind unterschiedlich hoch, daher die Mitte)
    assert abs(tab.zeitplan_start.geometry().center().y() - tab.mindestabstand.geometry().center().y()) <= 3


def test_zeitplan_uebernimmt_richter_einmalig(qtbot, termin):
    """UX-Test 02.10.2026, U8: Beim Öffnen des Termins erscheinen die Richter aus den
    Veranstaltungsdaten als Spalten; bewusst gelöschte Richter tauchen nicht wieder auf."""
    from db import list_zeitplan_richter, loesche_zeitplan_richter

    conn, pfad = termin
    set_veranstaltung(conn, verein="HSV", datum="2026-11-14",
                      wertungsrichter_1="Anna Richter", wertungsrichter_2="Bernd Berger")

    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    # Bloßes Öffnen des Termins verändert die Datei nicht.
    assert list_zeitplan_richter(conn) == []

    fenster._tabs.setCurrentWidget(fenster.zeitplan_tab)
    assert [r["name"] for r in list_zeitplan_richter(conn)] == ["Anna Richter", "Bernd Berger"]

    for richter in list_zeitplan_richter(conn):
        loesche_zeitplan_richter(conn, richter["id"])
    fenster._tabs.setCurrentWidget(fenster.teilnehmer_tab)
    fenster._tabs.setCurrentWidget(fenster.zeitplan_tab)
    assert list_zeitplan_richter(conn) == []


def test_zeitplan_markiert_ueberschneidungen(qtbot, termin):
    """UX-Test 02.10.2026, U2b: betroffene Zeilen rot mit Warndreieck und Tooltip, Seitenleiste
    zeigt einen Warnbereich je Team; der Mindestabstand ist einstellbar und gespeichert."""
    from PySide6.QtWidgets import QListWidget

    conn, pfad = termin
    _dk_parallel_termin(conn)
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    tab = fenster.zeitplan_tab
    tab.aktualisieren()

    # Nur die aktuellen Spalten (ältere warten nach dem Neuaufbau noch auf deleteLater).
    spalten = [tab._spalten_layout.itemAt(i).widget() for i in range(tab._spalten_layout.count())]
    listen = [lw for spalte in spalten if spalte is not None for lw in spalte.findChildren(QListWidget)]
    zeilen = [lw.item(i) for lw in listen for i in range(lw.count())]
    warnsymbol = symbol("alert-triangle", "fehler").cacheKey()
    markiert = [z for z in zeilen if z.icon().cacheKey() == warnsymbol]
    teilnehmer = [z for z in markiert if not z.font().bold()]
    assert len(teilnehmer) == 6
    assert "gleichzeitig" in teilnehmer[0].toolTip()
    # Verifikation U9: auch die Blockköpfe der betroffenen Blöcke sind markiert.
    assert sum(1 for z in markiert if z.font().bold()) == 3
    seitenleiste = tab._offene_starts_label.text()
    assert "Überschneidungen (2 Team(s))" in seitenleiste
    assert "Nr. 1 Muster" in seitenleiste

    tab.mindestabstand.setValue(25)
    assert get_veranstaltung(conn)["dk_mindestabstand"] == "25"


def test_zeitplan_pdf_fragt_bei_ueberschneidungen(qtbot, termin, monkeypatch):
    """UX-Test 02.10.2026, U2b: vor dem Zeitplan-PDF eine Rückfrage, wenn Teams doppelt
    eingeplant sind; bei "Nein" wird nichts gespeichert."""
    conn, pfad = termin
    _dk_parallel_termin(conn)
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)

    fragen = []
    monkeypatch.setattr("desktop_gemeinsam.QMessageBox.question", lambda *a, **k: fragen.append(a[2]) or QMessageBox.No)
    dialoge = []
    monkeypatch.setattr("desktop_gemeinsam.QFileDialog.getSaveFileName", lambda *a, **k: dialoge.append(a) or ("", ""))

    fenster.zeitplan_tab._pdf_exportieren()

    assert len(fragen) == 1 and "Überschneidung" in fragen[0]
    assert dialoge == []


def test_zeitplan_blockkoepfe_und_warnung_nur_mit_plan(qtbot, termin, monkeypatch):
    """UX-Test 02.10.2026, U9: Blockköpfe mit Teilnehmerzahl über den eingerückten Teams;
    "Automatisch verteilen" fragt nur nach, wenn schon ein Plan existiert."""
    from PySide6.QtWidgets import QListWidget

    conn, pfad = termin
    _teilnehmer_anlegen(conn, nachname="A", startnummer=1)
    _teilnehmer_anlegen(conn, nachname="B", startnummer=2)
    add_zeitplan_richter(conn)
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    tab = fenster.zeitplan_tab

    # UX-Test 2026-11, T1: Die Warnung steht jetzt im Dialog „Automatisch verteilen“.
    dialoge = verteilen_dialog_bestaetigen(monkeypatch)
    meldungen_sammeln(monkeypatch, "information")
    tab._automatisch_verteilen()
    assert "ERSETZT" not in dialoge[-1].warnung.text()  # leerer Plan: keine Warnung
    tab._automatisch_verteilen()
    assert "ERSETZT" in dialoge[-1].warnung.text()  # jetzt gibt es einen Plan, der ersetzt würde

    spalten = [tab._spalten_layout.itemAt(i).widget() for i in range(tab._spalten_layout.count())]
    liste = next(lw for sp in spalten if sp is not None for lw in sp.findChildren(QListWidget))
    texte = [liste.item(i).text() for i in range(liste.count())]
    assert texte[0].startswith("Fläche LK 1  (2 Teilnehmer")
    assert liste.item(0).icon().cacheKey() == symbol("chevron-right", "TEXT_GEDAEMPFT").cacheKey()
    assert liste.item(0).font().bold()
    assert texte[1].lstrip().startswith("09:00") and "Nr. 1" in texte[1]


def test_verteilen_bestaetigung_zaehlt_pruefungen_und_teilnehmer(qtbot, termin, monkeypatch):
    """Nachtest 2, N10: Der Dreikampf zählt als eine Prüfung, jeder Teilnehmer einmal - vorher
    „4 Prüfung(en) mit 7 Start(s)“ bei 2 Prüfungen und 3 Teilnehmern."""
    conn, pfad = termin
    _teilnehmer_anlegen(conn, nachname="Ed", startnummer=1)
    _teilnehmer_anlegen(conn, nachname="Dk1", startnummer=2, art="DK", disziplin=None)
    _teilnehmer_anlegen(conn, nachname="Dk2", startnummer=3, art="DK", disziplin=None)
    add_zeitplan_richter(conn)
    add_zeitplan_richter(conn)
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    verteilen_dialog_bestaetigen(monkeypatch)
    meldungen = meldungen_sammeln(monkeypatch, "information")
    fenster.zeitplan_tab._automatisch_verteilen()
    assert meldungen[-1].startswith("Alle 2 Prüfungen mit 3 Teilnehmern sind eingeplant"), meldungen


def test_verteilen_bestaetigt_und_plant_mittagspause_ein(qtbot, termin, monkeypatch):
    """UX-Test 2026-11, T1: Nach dem Verteilen steht ausdrücklich „keine Überschneidungen“;
    die Mittagspause aus dem Dialog landet bei allen Richtern und ist beim Neu-Verteilen
    vorbelegt; „Abbrechen“ ändert nichts."""
    from db import berechne_zeitplan_bloecke, list_zeitplan_eintraege, list_zeitplan_richter
    from desktop_zeitplan import MITTAGSPAUSE

    conn, pfad = termin
    for nr in range(1, 13):
        _teilnehmer_anlegen(conn, nachname=f"T{nr}", startnummer=nr)
    add_zeitplan_richter(conn)
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    tab = fenster.zeitplan_tab

    dialoge = verteilen_dialog_bestaetigen(monkeypatch, pause=("10:00", 30))
    meldungen = meldungen_sammeln(monkeypatch, "information")
    tab._automatisch_verteilen()
    assert meldungen[-1].startswith("Die Prüfung mit 12 Teilnehmern ist eingeplant, und es gibt keine Überschneidungen.")
    # Um 10:00 läuft noch der Block - die Meldung nennt die tatsächliche Zeit (Abschluss-QS B11, K2).
    assert "Die Pause beginnt nicht überall um 10:00:\n\nRichter 1: 11:00 Uhr" in meldungen[-1]
    assert len(dialoge) == 1
    pausen = [b for spur in berechne_zeitplan_bloecke(conn) for b in spur["bloecke"] if b["typ"] == "pause"]
    assert [(p["bezeichnung"], p["dauer_minuten"]) for p in pausen] == [(MITTAGSPAUSE, 30)]

    # Neu verteilen: die Mittagspause ist vorbelegt (bleibt erhalten).
    vorbelegt = []
    monkeypatch.setattr("desktop_dialoge.VerteilenDialog.exec", lambda d: vorbelegt.append(
        (d.mit_pause.isChecked(), d.uhrzeit.text(), d.dauer_minuten.value())) or QDialog.Accepted)
    tab._automatisch_verteilen()
    assert vorbelegt == [(True, "10:00", 30)]  # Wunschzeit, nicht die tatsächliche Startzeit

    # Nach einem Neustart (neuer Reiter): Beginn und Dauer aus dem Plan.
    from desktop_zeitplan import ZeitplanTab

    frisch = ZeitplanTab(conn)
    qtbot.addWidget(frisch)
    pausen_start = next(b["start"].strftime("%H:%M") for spur in berechne_zeitplan_bloecke(conn)
                        for b in spur["bloecke"] if b["typ"] == "pause")
    assert frisch._mittagspause_vorschlag() == (pausen_start, 30) and pausen_start >= "10:00"
    pausen = [b for spur in berechne_zeitplan_bloecke(conn) for b in spur["bloecke"] if b["typ"] == "pause"]
    assert len(pausen) == 1

    # Abbrechen: Plan bleibt.
    vorher = [(e["id"]) for r in list_zeitplan_richter(conn) for e in list_zeitplan_eintraege(conn, r["id"])]
    verteilen_dialog_bestaetigen(monkeypatch, abbrechen=True)
    tab._automatisch_verteilen()
    assert [(e["id"]) for r in list_zeitplan_richter(conn) for e in list_zeitplan_eintraege(conn, r["id"])] == vorher


def test_verteilen_meldet_offene_starts(qtbot, termin, monkeypatch):
    """UX-Test 2026-11, T1: Bleibt etwas uneingeplant, sagt die Bestätigung das (Warnung)."""
    import desktop_zeitplan

    conn, pfad = termin
    _teilnehmer_anlegen(conn, nachname="A", startnummer=1)
    add_zeitplan_richter(conn)
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    tab = fenster.zeitplan_tab
    verteilen_dialog_bestaetigen(monkeypatch)
    monkeypatch.setattr(desktop_zeitplan, "zeitplan_gruppen_status",
                        lambda c: [{"eingeplant": False, "art": "ED", "stufe": 1, "disziplin": "Flächensuche", "anzahl": 1}])
    warnungen = meldungen_sammeln(monkeypatch, "warning")
    tab._automatisch_verteilen()
    assert warnungen == ["1 Prüfung noch nicht (ganz) eingeplant (siehe „Offene Starts“)."]

    # Überschneidungen werden genannt; eine Mittagspause nach Planende wird nicht eingefügt.
    monkeypatch.setattr(desktop_zeitplan, "zeitplan_gruppen_status",
                        lambda c: [{"eingeplant": True, "art": "ED", "stufe": 1, "disziplin": "Flächensuche", "anzahl": 1}])
    monkeypatch.setattr(tab, "aktualisieren", lambda: None)  # Seitenleiste braucht volle Konflikt-Daten
    monkeypatch.setattr(desktop_zeitplan, "zeitplan_ueberschneidungen",
                        lambda c: [{"teilnehmer": {"id": 1}}, {"teilnehmer": {"id": 1}}])
    verteilen_dialog_bestaetigen(monkeypatch, pause=("18:00", 30))
    tab._automatisch_verteilen()
    assert warnungen[-1].startswith("Überschneidungen bei 1 Team(s)")
    assert warnungen[-1].endswith("Keine Pause eingefügt – bei keinem Richter steht ab 18:00 Uhr noch eine Prüfung im Plan.")


def test_verteilen_nennt_tatsaechliche_pausenzeit_und_braucht_teilnehmer(qtbot, termin, monkeypatch):
    """Abschluss-QS B11, K2: Läuft um die Wunschzeit noch ein Block, nennt die Bestätigung die
    tatsächliche Startzeit der Mittagspause. K3: Ohne Teilnehmer gibt es nichts zu verteilen."""
    from db import berechne_zeitplan_bloecke

    conn, pfad = termin
    add_zeitplan_richter(conn)
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    tab = fenster.zeitplan_tab
    dialoge = verteilen_dialog_bestaetigen(monkeypatch, pause=("09:10", 30))
    meldungen = meldungen_sammeln(monkeypatch, "information")
    tab._automatisch_verteilen()
    assert meldungen == ["Noch keine Teilnehmer – nichts zu verteilen."] and dialoge == []

    for nr in range(1, 7):
        _teilnehmer_anlegen(conn, nachname=f"T{nr}", startnummer=nr)
    tab._automatisch_verteilen()
    beginn = next(b["start"].strftime("%H:%M") for spur in berechne_zeitplan_bloecke(conn)
                  for b in spur["bloecke"] if b["typ"] == "pause")
    assert beginn > "09:10"
    assert "Die Pause beginnt nicht überall um 09:10" in meldungen[-1]
    assert f"{beginn} Uhr" in meldungen[-1]

    # Beginnt die Pause überall zur Wunschzeit, steht die kurze Erfolgsmeldung da.
    monkeypatch.setattr("desktop_zeitplan.add_zeitplan_pause_bei_allen",
                        lambda *a, **k: [("Richter 1", "09:10")])
    tab._automatisch_verteilen()
    assert meldungen[-1].endswith("\n\nMittagspause (30 Min.) um 09:10 Uhr bei 1 Richter(n) eingeplant.")


def test_pause_bei_allen_hinweis_und_titel(qtbot, termin, monkeypatch):
    """Abschluss-QS B11: der gemeinsame Hinweis für beide Pausen-Wege; der Titel der Meldung
    bei „Pause bei allen Richtern“ bleibt „Pause eingefügt“ bzw. „Keine Pause eingefügt“."""
    import desktop_zeitplan
    from desktop_zeitplan import _pause_bei_allen_hinweis

    assert _pause_bei_allen_hinweis([], "12:00") == (0, "")
    assert _pause_bei_allen_hinweis([("A", "12:00"), ("B", "12:00")], "12:00") == (2, "")
    anzahl, text = _pause_bei_allen_hinweis([("A", "12:30"), ("", None)], "12:00")
    assert anzahl == 1 and "A: 12:30 Uhr" in text and "Richter: keine Pause – keine Prüfung mehr ab 12:00 Uhr" in text
    assert _pause_bei_allen_hinweis([("A", None)], "12:00")[1].startswith("Keine Pause eingefügt")

    conn, pfad = termin
    richter_id = add_zeitplan_richter(conn)
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    tab = fenster.zeitplan_tab
    titel = meldungen_sammeln(monkeypatch, "information", merke="titel")

    class _Dialog:
        def __init__(self, *a, **k):
            self.fuer_alle = type("C", (), {"isChecked": lambda s: True})()
            self.uhrzeit = type("T", (), {"text": lambda s: "12:00"})()
            self.genau = type("C", (), {"isChecked": lambda s: False})()

        def werte(self):
            return {"dauer_minuten": 30}

    monkeypatch.setattr(desktop_zeitplan, "PauseDialog", _Dialog)
    monkeypatch.setattr(desktop_zeitplan, "_ausfuehren", lambda d: QDialog.Accepted)
    for antwort, erwartet in (([("A", None)], "Keine Pause eingefügt"), ([("A", "12:30")], "Pause eingefügt")):
        monkeypatch.setattr(desktop_zeitplan, "add_zeitplan_pause_bei_allen", lambda *a, _r=antwort, **k: _r)
        tab._pause_hinzufuegen(richter_id)
        assert titel[-1] == erwartet


def test_zeitplan_richter_anlegen_umbenennen_verschieben_ueber_knoepfe(qtbot, conn, monkeypatch):
    """Abdeckung 01.11.2026 (B10): Richter anlegen, umbenennen (auch Abbrechen und leerer
    Name) und nach links/rechts verschieben über die Knöpfe; Datenbank und Spalten folgen."""
    tab = _zeitplan_tab(qtbot, conn)
    assert _zeitplan_titel(tab) == []

    # Nachtest 2 (N7): „Richter hinzufügen“ fragt den Namen ab - leer ergibt „Richter N“,
    # Abbrechen legt keinen an.
    namen = [("", True), ("  ", True), ("Herr Braun", False)]
    monkeypatch.setattr("desktop_zeitplan.QInputDialog.getText", lambda *a, **k: namen.pop(0))
    _knopf(tab, "Richter hinzufügen").click()
    _knopf(tab, "Richter hinzufügen").click()
    _knopf(tab, "Richter hinzufügen").click()
    assert _richter_namen(conn) == ["Richter 1", "Richter 2"]
    assert _zeitplan_titel(tab) == ["Richter 1", "Richter 2"]

    vorbelegt = []
    antworten = [("  Frau Weber  ", True), ("Anders", False), ("   ", True)]

    def _text(*_a, text="", **_k):
        vorbelegt.append(text)
        return antworten.pop(0)

    monkeypatch.setattr("desktop_zeitplan.QInputDialog.getText", _text)
    _knopf(_zeitplan_spalte(tab, "Richter 1"), "Umbenennen…").click()
    assert _richter_namen(conn) == ["Frau Weber", "Richter 2"]
    assert _zeitplan_titel(tab) == ["Frau Weber", "Richter 2"]
    _knopf(_zeitplan_spalte(tab, "Frau Weber"), "Umbenennen…").click()  # Abbrechen
    _knopf(_zeitplan_spalte(tab, "Frau Weber"), "Umbenennen…").click()  # nur Leerzeichen
    assert _richter_namen(conn) == ["Frau Weber", "Richter 2"]
    assert vorbelegt == ["Richter 1", "Frau Weber", "Frau Weber"] and antworten == []

    _symbolknopf(_zeitplan_spalte(tab, "Frau Weber"), "Spalte nach rechts verschieben").click()
    assert _richter_namen(conn) == ["Richter 2", "Frau Weber"]
    assert _zeitplan_titel(tab) == ["Richter 2", "Frau Weber"]
    _symbolknopf(_zeitplan_spalte(tab, "Frau Weber"), "Spalte nach rechts verschieben").click()  # schon ganz rechts
    assert _zeitplan_titel(tab) == ["Richter 2", "Frau Weber"]
    _symbolknopf(_zeitplan_spalte(tab, "Frau Weber"), "Spalte nach links verschieben").click()
    assert _richter_namen(conn) == ["Frau Weber", "Richter 2"]
    assert _zeitplan_titel(tab) == ["Frau Weber", "Richter 2"]


def test_richter_hinzufuegen_uebernimmt_den_eingegebenen_namen(qtbot, conn, monkeypatch):
    """Nachtest 2, N7 (Verifikation B15): ein eingegebener Name landet ohne Leerzeichen am
    Rand in der Datenbank und als Spaltentitel."""
    tab = _zeitplan_tab(qtbot, conn)
    monkeypatch.setattr("desktop_zeitplan.QInputDialog.getText", lambda *a, **k: (" Frau Lang ", True))
    _knopf(tab, "Richter hinzufügen").click()
    assert _richter_namen(conn) == ["Frau Lang"]
    assert _zeitplan_titel(tab) == ["Frau Lang"]


def test_zeitplan_richter_loeschen_nur_nach_rueckfrage(qtbot, conn, monkeypatch):
    """Abdeckung 01.11.2026 (B10): „Richter löschen“ fragt mit Vorgabe „Nein“; bei „Nein“
    bleibt alles, bei „Ja“ verschwinden Richter, Spalte und seine Einträge."""
    from db import list_zeitplan_eintraege

    r1 = add_zeitplan_richter(conn, "R1")
    r2 = add_zeitplan_richter(conn, "R2")
    add_zeitplan_pruefungsblock(conn, r1, "ED", 1, "Flächensuche", 10)
    add_zeitplan_pruefungsblock(conn, r2, "ED", 2, "Flächensuche", 10)
    tab = _zeitplan_tab(qtbot, conn)
    fragen = rueckfragen_sammeln(monkeypatch, QMessageBox.No, QMessageBox.Yes, merke="text_vorgabe")

    _knopf(_zeitplan_spalte(tab, "R1"), "Richter löschen").click()
    assert _richter_namen(conn) == ["R1", "R2"] and _zeitplan_titel(tab) == ["R1", "R2"]
    assert len(list_zeitplan_eintraege(conn, r1)) == 1

    _knopf(_zeitplan_spalte(tab, "R1"), "Richter löschen").click()
    assert _richter_namen(conn) == ["R2"] and _zeitplan_titel(tab) == ["R2"]
    assert conn.execute("SELECT COUNT(*) FROM zeitplan_eintrag WHERE richter_id = ?", (r1,)).fetchone()[0] == 0
    assert len(list_zeitplan_eintraege(conn, r2)) == 1
    assert len(fragen) == 2
    assert all("„R1“" in text and vorgabe == QMessageBox.No for text, vorgabe in fragen)


def test_zeitplan_pruefungsblock_hinzufuegen_mit_echtem_dialog(qtbot, conn, monkeypatch):
    """Abdeckung 01.11.2026 (B10): „Prüfungsblock hinzufügen…“ baut den echten Dialog mit
    der Standard-Prüfungsdauer auf, legt den Block mit den gewählten Werten an und zeigt
    ihn samt Teilnehmer; Abbrechen legt nichts an."""
    from db import list_zeitplan_eintraege
    from desktop_dialoge import PruefungsblockDialog

    r1 = add_zeitplan_richter(conn, "R1")
    _teilnehmer_anlegen(conn, stufe=2, nachname="Blockmann")
    tab = _zeitplan_tab(qtbot, conn)
    tab.standard_dauer.setValue(7)
    vorgaben = []

    def _ausfuellen(dialog):
        vorgaben.append(dialog.dauer_minuten.value())
        dialog.art.setCurrentText("ED")
        dialog.stufe.setCurrentText("2")
        dialog.disziplin.setCurrentText("Flächensuche")
        dialog.dauer_minuten.setValue(12)
        return QDialog.Accepted

    monkeypatch.setattr(PruefungsblockDialog, "exec", _ausfuellen)
    _knopf(_zeitplan_spalte(tab, "R1"), "Prüfungsblock hinzufügen…").click()

    assert vorgaben == [7]
    eintraege = list_zeitplan_eintraege(conn, r1)
    assert [(e["typ"], e["art"], e["stufe"], e["disziplin"], e["dauer_minuten"]) for e in eintraege] == [
        ("pruefung", "ED", 2, "Flächensuche", 12)
    ]
    liste = _zeitplan_liste(_zeitplan_spalte(tab, "R1"))
    texte = [liste.item(i).text() for i in range(liste.count())]
    assert len(texte) == 2
    assert texte[0].startswith("Fläche LK 2  (1 Teilnehmer")
    assert "Blockmann" in texte[1]

    monkeypatch.setattr(PruefungsblockDialog, "exec", lambda _dialog: QDialog.Rejected)
    _knopf(_zeitplan_spalte(tab, "R1"), "Prüfungsblock hinzufügen…").click()
    assert len(list_zeitplan_eintraege(conn, r1)) == 1


def test_zeitplan_eintrag_verschieben_bearbeiten_entfernen_ueber_knoepfe(qtbot, conn, monkeypatch):
    """Abdeckung 01.11.2026 (B10): Hoch/Runter (auch am Rand), Bearbeiten von Pause und
    Prüfungsblock (jeweils auch Abbrechen) und Entfernen über die Knöpfe einer Spalte; ohne
    markierte Zeile kommt ein Hinweis bzw. passiert nichts. „Entfernen“ fragt nach (Vorgabe
    „Nein“, Marcos Entscheidung 01.11.2026)."""
    from db import add_zeitplan_pause, list_zeitplan_eintraege, zeitplan_eintrag
    from desktop_dialoge import PauseDialog

    r1 = add_zeitplan_richter(conn, "R1")
    block = add_zeitplan_pruefungsblock(conn, r1, "ED", 1, "Flächensuche", 10)
    pause = add_zeitplan_pause(conn, r1, 20, "Mittag")
    _teilnehmer_anlegen(conn)
    tab = _zeitplan_tab(qtbot, conn)

    def _reihenfolge():
        return [e["id"] for e in list_zeitplan_eintraege(conn, r1)]

    def _spalte():
        return _zeitplan_spalte(tab, "R1")

    def _markieren(eintrag_id):
        liste = _zeitplan_liste(_spalte())
        zeile = next(i for i in range(liste.count()) if liste.item(i).data(Qt.UserRole) == eintrag_id)
        liste.setCurrentRow(zeile)

    def _markiert():
        item = _zeitplan_liste(_spalte()).currentItem()
        return item.data(Qt.UserRole) if item is not None else None

    # Ohne markierte Zeile.
    hinweise = meldungen_sammeln(monkeypatch, "information", merke="titel")
    assert _markiert() is None
    for text in ("Hoch", "Runter", "Bearbeiten…", "Entfernen"):
        _knopf(_spalte(), text).click()
    assert hinweise == ["Kein Eintrag ausgewählt"] * 2
    assert _reihenfolge() == [block, pause]

    # Hoch/Runter: die Pause bleibt nach dem Neuaufbau markiert.
    _markieren(pause)
    _knopf(_spalte(), "Hoch").click()
    assert _reihenfolge() == [pause, block] and _markiert() == pause
    _knopf(_spalte(), "Hoch").click()  # schon ganz oben
    assert _reihenfolge() == [pause, block] and _markiert() == pause
    _knopf(_spalte(), "Runter").click()
    assert _reihenfolge() == [block, pause] and _markiert() == pause

    # Pause bearbeiten (echter Dialog): leere Bezeichnung wird „Pause“; Abbrechen ändert nichts.
    vorbelegung = []

    def _pause_ausfuellen(dialog):
        vorbelegung.append((dialog.dauer_minuten.value(), dialog.bezeichnung.text()))
        dialog.dauer_minuten.setValue(30)
        dialog.bezeichnung.setText("")
        return QDialog.Accepted

    monkeypatch.setattr(PauseDialog, "exec", _pause_ausfuellen)
    _knopf(_spalte(), "Bearbeiten…").click()
    assert vorbelegung == [(20, "Mittag")]
    eintrag = zeitplan_eintrag(conn, pause)
    assert (eintrag["dauer_minuten"], eintrag["bezeichnung"]) == (30, "Pause")
    assert _markiert() == pause
    monkeypatch.setattr(PauseDialog, "exec", lambda _dialog: QDialog.Rejected)
    _knopf(_spalte(), "Bearbeiten…").click()
    assert zeitplan_eintrag(conn, pause)["dauer_minuten"] == 30

    # Prüfungsblock bearbeiten: neue Dauer je Teilnehmer; Abbrechen ändert nichts.
    abfragen = []
    antworten = [(25, True), (99, False)]

    def _zahl(*_a, value=None, **_k):
        abfragen.append(value)
        return antworten.pop(0)

    monkeypatch.setattr("desktop_zeitplan.QInputDialog.getInt", _zahl)
    _markieren(block)
    _knopf(_spalte(), "Bearbeiten…").click()
    assert zeitplan_eintrag(conn, block)["dauer_minuten"] == 25 and _markiert() == block
    _knopf(_spalte(), "Bearbeiten…").click()
    assert zeitplan_eintrag(conn, block)["dauer_minuten"] == 25
    assert abfragen == [10, 25]

    # Entfernen fragt nach; „Nein“ (die Vorgabe) lässt alles stehen.
    fragen = []

    def _antwort(antwort):
        def frage(*args, **_k):
            fragen.append((args[1], args[2], args[4]))
            return antwort
        monkeypatch.setattr("app.QMessageBox.question", frage)

    _markieren(pause)
    _antwort(QMessageBox.No)
    _knopf(_spalte(), "Entfernen").click()
    assert _reihenfolge() == [block, pause]
    titel, text, vorgabe = fragen[0]
    assert titel == "Eintrag entfernen" and "Pause: Pause" in text and vorgabe == QMessageBox.No
    # „Ja“: die Pause verschwindet aus Datenbank und Liste, danach ist nichts markiert.
    _markieren(pause)
    _antwort(QMessageBox.Yes)
    _knopf(_spalte(), "Entfernen").click()
    assert _reihenfolge() == [block]
    liste = _zeitplan_liste(_spalte())
    assert all("Pause" not in liste.item(i).text() for i in range(liste.count()))
    assert _markiert() is None
    assert hinweise == ["Kein Eintrag ausgewählt"] * 2


@pytest.mark.parametrize("db_funktion, aktion", _zeitplan_aktionen(), ids=[f for f, _ in _zeitplan_aktionen()])
def test_zeitplan_aktion_meldet_datenbankfehler(qtbot, conn, monkeypatch, db_funktion, aktion):
    """Abdeckung 01.11.2026 (B10): Scheitert eine Zeitplan-Aktion an der Datenbank (z. B.
    gesperrte Datei), erscheint „Datenbankfehler“, der Reiter baut nicht neu auf und der
    gespeicherte Stand bleibt unverändert."""
    import sqlite3

    from db import list_zeitplan_eintraege
    from desktop_dialoge import PruefungsblockDialog

    r1 = add_zeitplan_richter(conn, "R1")
    block = add_zeitplan_pruefungsblock(conn, r1, "ED", 1, "Flächensuche", 10)
    tab = _zeitplan_tab(qtbot, conn)
    liste = _zeitplan_liste(_zeitplan_spalte(tab, "R1"))
    liste.setCurrentRow(0)
    assert liste.currentItem().data(Qt.UserRole) == block

    def _gesperrt(*_a, **_k):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(f"desktop_zeitplan.{db_funktion}", _gesperrt)
    monkeypatch.setattr("desktop_zeitplan.QInputDialog.getText", lambda *a, **k: ("Neu", True))
    monkeypatch.setattr("desktop_zeitplan.QInputDialog.getInt", lambda *a, **k: (5, True))
    monkeypatch.setattr(PruefungsblockDialog, "exec", lambda _dialog: QDialog.Accepted)
    rueckfragen_beantworten(monkeypatch, QMessageBox.Yes)
    aufgebaut = []
    monkeypatch.setattr(tab, "aktualisieren", lambda: aufgebaut.append(True))
    fehler = meldungen_sammeln(monkeypatch, "critical", merke="titel")

    aktion(tab, r1, liste)

    assert fehler == ["Datenbankfehler"] and aufgebaut == []
    monkeypatch.undo()
    assert _richter_namen(conn) == ["R1"]
    eintraege = list_zeitplan_eintraege(conn, r1)
    assert [(e["id"], e["dauer_minuten"]) for e in eintraege] == [(block, 10)]


def test_pruefungsblock_dialog_werte_ok_und_abbrechen(qtbot):
    """Abdeckung 01.11.2026 (B10): PruefungsblockDialog übernimmt die Standarddauer, liefert
    die gewählten Werte (Leistungsklasse als Zahl) und begrenzt die Dauer auf 1-240 Min.
    Eine eigene Prüfung hat er nicht - „OK“ nimmt immer an, „Abbrechen“ lehnt ab."""
    from desktop_dialoge import PruefungsblockDialog

    dialog = PruefungsblockDialog(None, standard_dauer_minuten=7)
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "Prüfungsblock hinzufügen"
    assert [dialog.art.itemText(i) for i in range(dialog.art.count())] == ["ED", "DK"]
    assert [dialog.disziplin.itemText(i) for i in range(dialog.disziplin.count())] == list(ALLE_DISZIPLINEN)
    assert dialog.werte() == {"art": "ED", "stufe": 1, "disziplin": ALLE_DISZIPLINEN[0], "dauer_minuten": 7}

    dialog.art.setCurrentText("DK")
    dialog.stufe.setCurrentText("3")
    dialog.disziplin.setCurrentText(ALLE_DISZIPLINEN[-1])
    dialog.dauer_minuten.setValue(0)
    assert dialog.dauer_minuten.value() == 1
    dialog.dauer_minuten.setValue(500)
    assert dialog.dauer_minuten.value() == 240
    _dialog_knopf(dialog, QDialogButtonBox.Ok).click()
    assert dialog.result() == QDialog.Accepted
    assert dialog.werte() == {"art": "DK", "stufe": 3, "disziplin": ALLE_DISZIPLINEN[-1], "dauer_minuten": 240}

    abbrechen = PruefungsblockDialog(None)
    qtbot.addWidget(abbrechen)
    assert abbrechen.werte()["dauer_minuten"] == 10
    _dialog_knopf(abbrechen, QDialogButtonBox.Cancel).click()
    assert abbrechen.result() == QDialog.Rejected


def test_zeitplan_bloecke_lassen_sich_ziehen(qtbot, conn):
    """Marco 10.11.2026: Ziehen mit der Maus ordnet Blöcke um (wie „Hoch“/„Runter“)."""
    from db import add_zeitplan_pruefungsblock, add_zeitplan_richter, list_zeitplan_eintraege

    _teilnehmer_anlegen(conn, nachname="A", disziplin="Trümmerfeld", startnummer=1)
    _teilnehmer_anlegen(conn, nachname="B", disziplin="Flächensuche", startnummer=2)
    _teilnehmer_anlegen(conn, nachname="C", disziplin="Behältnisstrecke", startnummer=3)
    richter = add_zeitplan_richter(conn, "Erika")
    ids = [add_zeitplan_pruefungsblock(conn, richter, "ED", 1, d, 10)
           for d in ("Trümmerfeld", "Flächensuche", "Behältnisstrecke")]
    tab = ZeitplanTab(conn)
    qtbot.addWidget(tab)
    tab.show()
    tab._eintrag_ziehen(richter, ids[0], ids[2])  # erster Block an die Stelle des letzten
    assert [e["id"] for e in list_zeitplan_eintraege(conn, richter)] == [ids[1], ids[2], ids[0]]
    tab._eintrag_ziehen(richter, ids[0], ids[1])  # zurück nach vorn
    assert [e["id"] for e in list_zeitplan_eintraege(conn, richter)] == [ids[0], ids[1], ids[2]]
    tab._eintrag_ziehen(richter, ids[1], ids[1])  # auf sich selbst: nichts
    assert [e["id"] for e in list_zeitplan_eintraege(conn, richter)] == ids
