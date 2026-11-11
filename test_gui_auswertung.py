"""GUI-Tests: Auswertung, Export, PDF-Ausdrucke und Bewertungsbögen.

Fixtures und Hilfen stehen in gui_hilfen.py (Aufteilung von test_app_gui.py, 11.11.2026)."""

from __future__ import annotations

import os
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox, QLabel, QMessageBox, QPushButton
import db as _db_modul
from app import HauptFenster
from desktop_ergebnis import ErgebnisTab
from desktop_teilnehmer import TeilnehmerTab
from db import (
    eintragen_ergebnis,
    set_veranstaltung,
    setze_ergebnis_status,
)
from desktop_dialoge import (
    BewertungsbogenAuswahlDialog,
)
import desktop_auswertung
from desktop_auswertung import AuswertungTab, ExportTab, TeilnehmerUebersichtTab
from desktop_verwaltung import VerwaltungTab
from desktop_zeitplan import ZeitplanTab
from gui_hilfen import *  # noqa: F401,F403


# --- Zeilennummern-Spalte ausgeblendet (in allen drei Tabellen-Tabs einheitlich) ----
# Nutzerhinweis (20.09.): bei der Auswertung waren die Zeilennummern links noch sichtbar,
# obwohl sie bei Teilnehmer und Ergebniserfassung bereits ausgeblendet sind - jetzt überall
# konsistent versteckt (verticalHeader().setVisible(False)).


def test_auswertung_tabelle_zeigt_keine_zeilennummern(qtbot, conn):
    tab = AuswertungTab(conn)
    qtbot.addWidget(tab)
    assert not tab.tabelle.verticalHeader().isVisible()


def test_auswertung_zeigt_hund_zwischen_name_und_gesamtpunkte(qtbot, conn):
    """Nutzerwunsch: eigene Spalte "Hund" zwischen "Name" und "Gesamtpunkte", befüllt mit
    rufname_hund - Teilnehmerergebnis (shs_core) kennt dieses Feld selbst nicht, AuswertungTab
    schlägt es analog zur Startnummer separat über die Teilnehmer-Stammdaten nach."""
    tid = _teilnehmer_anlegen(conn, nachname="Holst", rufname_hund="Freda", disziplin="Flächensuche")
    eintragen_ergebnis(conn, tid, "Flächensuche", suche=58, anzeige=38)

    tab = AuswertungTab(conn)
    qtbot.addWidget(tab)

    assert tab.tabelle.horizontalHeaderItem(3).text() == "Hund"
    assert tab.tabelle.item(0, 2).text() == "Holst, Max"
    assert tab.tabelle.item(0, 3).text() == "Freda"
    assert tab.tabelle.item(0, 4).text() == "96"


@pytest.mark.parametrize("filter_wert, erwartete_lk, erwarteter_name", [
    ("Alle", None, "Ergebnisliste.pdf"),
    ("Fläche LK 1", "Fläche LK 1", "Ergebnisliste_Fläche_LK_1.pdf"),
])
def test_auswertung_druck_button_uebernimmt_lk_filter(
    qtbot, conn, monkeypatch, tmp_path, filter_wert, erwartete_lk, erwarteter_name
):
    """Nutzerwunsch 23.09.: Druck-Button im Auswertungs-Tab gibt die Rangliste als PDF aus,
    mit dem gesetzten Art/LK-Filter (Start-Nr.-Filter bewusst nicht)."""
    tid = _teilnehmer_anlegen(conn, disziplin="Flächensuche", startnummer=7)
    eintragen_ergebnis(conn, tid, "Flächensuche", suche=58, anzeige=38)
    tab = AuswertungTab(conn)
    qtbot.addWidget(tab)
    tab.filter_combo.setCurrentText(filter_wert)
    tab.filter_startnummer.setText("99")  # darf den Druck nicht beeinflussen

    vorschlaege = []
    ziel_pfad = tmp_path / "rangliste.pdf"

    def dialog(_parent, _titel, vorschlag, _filter):
        vorschlaege.append(os.path.basename(vorschlag))
        return str(ziel_pfad), "PDF-Datei (*.pdf)"

    aufrufe = []
    monkeypatch.setattr("app.QFileDialog.getSaveFileName", dialog)
    monkeypatch.setattr(
        "app.pdf_export.erstelle_ergebnisliste_pdf",
        lambda c, pfad, leistungsklasse=None: aufrufe.append((pfad, leistungsklasse)),
    )

    qtbot.mouseClick(tab.drucken_btn, Qt.MouseButton.LeftButton)

    assert vorschlaege == [erwarteter_name]
    assert aufrufe == [(str(ziel_pfad), erwartete_lk)]
    assert str(ziel_pfad) in tab.status_label.text()


# --- Übersicht Teilnehmer und LK -----------------------------------------------------


def test_uebersicht_zeigt_teilnehmerzahlen_und_leistungsrichter_bedarf(qtbot, conn):
    # 13 ED-Teilnehmer LK1/Trümmerfeld + 2 DK-Teilnehmer LK1 + 2 DK-Teilnehmer LK2
    # -> 17 Teilnehmer gesamt, Abteilungen = 13*1 + 4*3 = 25, Richter = ceil(25/36) = 1.
    startnummer = 1
    for _ in range(13):
        _teilnehmer_anlegen(
            conn, art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=startnummer
        )
        startnummer += 1
    for _ in range(2):
        _teilnehmer_anlegen(conn, art="DK", stufe=1, disziplin=None, startnummer=startnummer)
        startnummer += 1
    for _ in range(2):
        _teilnehmer_anlegen(conn, art="DK", stufe=2, disziplin=None, startnummer=startnummer)
        startnummer += 1

    tab = TeilnehmerUebersichtTab(conn)
    qtbot.addWidget(tab)

    assert tab.teilnehmer_label.text() == "Teilnehmer gesamt: 17"
    assert tab.abteilungen_label.text() == "Abteilungen gesamt: 25"
    assert tab.richter_label.text() == "Anzahl benötigter Richter: 1"

    # ED LK 1 (Zeile 0): 13 Teilnehmer, alle Trümmerfeld, 13 Abteilungen.
    assert tab.tabelle.item(0, 0).text() == "ED LK 1"
    assert tab.tabelle.item(0, 1).text() == "13"
    assert tab.tabelle.item(0, 2).text() == "13"
    assert tab.tabelle.item(0, 5).text() == "13"

    # DK LK 1 (Zeile 3): 2 Teilnehmer, 6 Abteilungen, keine Disziplin-Aufschlüsselung.
    assert tab.tabelle.item(3, 0).text() == "DK LK 1"
    assert tab.tabelle.item(3, 1).text() == "2"
    assert tab.tabelle.item(3, 2).text() == "–"
    assert tab.tabelle.item(3, 5).text() == "6"

    # DK LK 2 (Zeile 4): 2 Teilnehmer, 6 Abteilungen.
    assert tab.tabelle.item(4, 1).text() == "2"
    assert tab.tabelle.item(4, 5).text() == "6"

    # Behältnis-Tabelle: nur DK laufen hier die Behältnisstrecke (ED ist Trümmerfeld).
    # LK1: 5 leer + 2 = 7, LK2: 7 leer + 2 = 9, LK3 unbelegt = 0.
    assert tab.behaeltnis_tabelle.item(0, 0).text() == "LK 1"
    assert tab.behaeltnis_tabelle.item(0, 1).text() == "2"
    assert tab.behaeltnis_tabelle.item(0, 4).text() == "–"
    assert tab.behaeltnis_tabelle.item(0, 5).text() == "7"
    assert tab.behaeltnis_tabelle.item(1, 5).text() == "9"
    assert tab.behaeltnis_tabelle.item(3, 0).text() == "LK 3 mit separatem Behältnis"
    assert tab.behaeltnis_tabelle.item(3, 4).text() == "0"
    assert tab.behaeltnis_tabelle.item(3, 5).text() == "0"


def test_stechen_gleiche_person_mit_zwei_hunden_und_vorgabe_offen(qtbot, conn, monkeypatch):
    """Desktop-Prüfung 14.10.2026, Teil 4 Nr. 2: Einträge unterscheidbar, gespeichert wird der
    gewählte Hund, und ohne Sieger ist „Stechen noch offen“ vorgewählt."""
    ali = _teilnehmer_anlegen(conn, rufname_hund="Ali", disziplin="Trümmerfeld", startnummer=1)
    bello = _teilnehmer_anlegen(conn, rufname_hund="Bello", disziplin="Trümmerfeld", startnummer=2)
    eintragen_ergebnis(conn, ali, "Trümmerfeld", 58, 37)
    eintragen_ergebnis(conn, bello, "Trümmerfeld", 55, 40)
    tab = AuswertungTab(conn)
    qtbot.addWidget(tab)
    tab.aktualisieren()
    angezeigt = {}

    def waehlen(_p, _t, _l, eintraege, index, _e):
        angezeigt.update(eintraege=eintraege, index=index)
        return next(e for e in eintraege if "mit Ali" in e), True

    monkeypatch.setattr("desktop_auswertung.QInputDialog.getItem", waehlen)
    tab._stechen_sieger_festlegen()
    assert len(set(angezeigt["eintraege"])) == len(angezeigt["eintraege"]) == 3
    assert angezeigt["eintraege"][angezeigt["index"]].endswith("Stechen noch offen")
    gewonnen = {r[0] for r in conn.execute(
        "SELECT t.rufname_hund FROM teilnehmer t JOIN ergebnisse e ON e.teilnehmer_id = t.id WHERE e.stechen_sieger = 1")}
    assert gewonnen == {"Ali"}


def test_eindeutige_texte_fuer_die_stechen_auswahl():
    """Abschluss-QS 15.10.2026: auch drei gleichlautende Einträge werden eindeutig."""

    assert desktop_auswertung._eindeutige_texte(["A", "B", "A", "A"]) == ["A [1]", "B", "A [2]", "A [3]"]
    assert desktop_auswertung._eindeutige_texte(["A", "B"]) == ["A", "B"]


def test_auswertung_stechen_hinweis_sieger_und_rueckfrage(qtbot, conn, monkeypatch):
    """S1 (Marco 03.10.2026): Gleichstand um Platz 1 -> Hinweis + "Stechen offen", Sieger
    über "Stechen-Sieger festlegen…", Rückfrage vor der Rangliste solange offen."""
    a = _teilnehmer_anlegen(conn, nachname="Anna", vorname="A", disziplin="Trümmerfeld", startnummer=1)
    b = _teilnehmer_anlegen(conn, nachname="Ben", vorname="B", disziplin="Trümmerfeld", startnummer=2)
    eintragen_ergebnis(conn, a, "Trümmerfeld", 58, 37)
    eintragen_ergebnis(conn, b, "Trümmerfeld", 55, 40)
    tab = AuswertungTab(conn)
    qtbot.addWidget(tab)
    tab.aktualisieren()

    platz_spalte = tab.tabelle.columnCount() - 1
    plaetze = {tab.tabelle.item(r, 2).text(): tab.tabelle.item(r, platz_spalte).text() for r in range(tab.tabelle.rowCount())}
    assert set(plaetze.values()) == {"1. von 2 (Stechen offen)"}
    assert ("Stechen nötig in Trümmer LK 1: A Anna mit Bello (Nr. 1), B Ben mit Bello (Nr. 2) (95 Punkte)"
            in tab.ausstehend_label.text())
    assert tab.stechen_btn.isEnabled()

    # Rückfrage vor dem Druck; "Nein" bricht ab, bevor ein Dateifenster kommt.
    fragen = rueckfragen_sammeln(monkeypatch, QMessageBox.No)
    monkeypatch.setattr("desktop_gemeinsam._speicherort_waehlen", lambda *x, **k: pytest.fail("kein Dateifenster erwartet"))
    tab._rangliste_drucken()
    assert "Stechen" in fragen[0]

    # Sieger festlegen: Ben.
    def waehlen(_p, _t, _l, eintraege, _i, _e):
        return next(e for e in eintraege if "B Ben" in e), True

    monkeypatch.setattr("desktop_auswertung.QInputDialog.getItem", waehlen)
    tab._stechen_sieger_festlegen()
    plaetze = {tab.tabelle.item(r, 2).text(): tab.tabelle.item(r, platz_spalte).text() for r in range(tab.tabelle.rowCount())}
    assert plaetze == {"Ben, B": "1. von 2 (nach Stechen)", "Anna, A": "2. von 2"}
    assert "Stechen nötig" not in tab.ausstehend_label.text()


def test_auswertung_ab_neuer_po_ohne_stechen(qtbot, conn, monkeypatch):
    """PO1 (PO_01012027.md): Veranstaltung ab 01.01.2027 -> geteilter Platz 1, kein Hinweis,
    kein Knopf, keine Rückfrage vor der Rangliste."""
    set_veranstaltung(conn, verein="SGV Köppern e.V.", datum="2027-01-02")
    a = _teilnehmer_anlegen(conn, nachname="Anna", vorname="A", disziplin="Trümmerfeld", startnummer=1)
    b = _teilnehmer_anlegen(conn, nachname="Ben", vorname="B", disziplin="Trümmerfeld", startnummer=2)
    eintragen_ergebnis(conn, a, "Trümmerfeld", 58, 37)
    eintragen_ergebnis(conn, b, "Trümmerfeld", 55, 40)
    tab = AuswertungTab(conn)
    qtbot.addWidget(tab)
    tab.show()
    tab.aktualisieren()

    platz_spalte = tab.tabelle.columnCount() - 1
    plaetze = {tab.tabelle.item(r, platz_spalte).text() for r in range(tab.tabelle.rowCount())}
    assert plaetze == {"1. von 2"}
    assert "Stechen" not in tab.ausstehend_label.text()
    assert not tab.stechen_btn.isVisible()

    # Keine Rückfrage zum Stechen: es geht direkt zur Dateiauswahl (hier abgebrochen).
    fragen = rueckfragen_sammeln(monkeypatch, QMessageBox.No)
    gewaehlt = []
    monkeypatch.setattr("desktop_gemeinsam._speicherort_waehlen", lambda *x, **k: gewaehlt.append(1))
    tab._rangliste_drucken()
    assert fragen == [] and gewaehlt == [1]

    # Vor dem Stichtag ist der Knopf wieder da.
    set_veranstaltung(conn, verein="SGV Köppern e.V.", datum="2026-12-31")
    tab.aktualisieren()
    assert tab.stechen_btn.isVisible() and tab.stechen_btn.isEnabled()


def test_bewertungsbogen_dialog_je_disziplin_haekchen(qtbot):
    from desktop_dialoge import BewertungsbogenAuswahlDialog
    dialog = BewertungsbogenAuswahlDialog(None, ["DK LK 1"])
    qtbot.addWidget(dialog)
    assert not dialog.je_disziplin.isChecked()  # Standard: bisheriger 2-Seiten-Bogen
    dialog.je_disziplin.setChecked(True)
    assert dialog.je_disziplin.isChecked()


def test_export_tab_anmeldeformular_ohne_angebotene_pruefungen_zeigt_hinweis(qtbot, conn, monkeypatch):
    set_veranstaltung(conn, verein="SGV", datum="2026-11-14")
    hinweise = []
    monkeypatch.setattr("app.QMessageBox.information", lambda parent, titel, text: hinweise.append(text))
    monkeypatch.setattr(
        "desktop_gemeinsam.QFileDialog.getSaveFileName",
        lambda *a, **k: pytest.fail("Speichern-Dialog darf ohne angebotene Prüfungen nicht erscheinen"),
    )
    tab = ExportTab(conn)
    qtbot.addWidget(tab)
    tab.show()

    qtbot.mouseClick(
        next(b for b in tab.findChildren(QPushButton) if b.text() == "Anmeldeformular (PDF)…"),
        Qt.MouseButton.LeftButton,
    )
    assert len(hinweise) == 1
    assert "angebotenen Prüfungen" in hinweise[0]


def test_export_tab_anmeldeformular_erzeugt_pdf(qtbot, conn, tmp_path, monkeypatch):
    set_veranstaltung(conn, verein="SGV", datum="2026-11-14", angebotene_pruefungen="DK1",
                      verband="HSVRM", meldestelle="Erika Muster")
    ziel = tmp_path / "Anmeldeformular.pdf"
    monkeypatch.setattr("desktop_gemeinsam.QFileDialog.getSaveFileName", lambda *a, **k: (str(ziel), ""))
    tab = ExportTab(conn)
    qtbot.addWidget(tab)
    tab.show()

    qtbot.mouseClick(
        next(b for b in tab.findChildren(QPushButton) if b.text() == "Anmeldeformular (PDF)…"),
        Qt.MouseButton.LeftButton,
    )
    assert ziel.exists()
    assert tab.status_label.text().startswith("Anmeldeformular gespeichert")


def test_export_tab_jeder_knopf_hat_kurztext_und_tooltip(qtbot, conn):
    """Rückmeldung 13.10.2026: statt eines langen Erklärtextes steht neben jedem Export-Knopf
    ein Kurztext; Einzelheiten zeigt der Tooltip an Knopf und Kurztext."""
    tab = ExportTab(conn)
    qtbot.addWidget(tab)
    tab.show()

    knoepfe = [b for b in tab.findChildren(QPushButton) if b.text() != "Ablageort öffnen"]
    assert len(knoepfe) == 14  # +2: Abrechnung und Checkliste (10.11.2026)
    for knopf in knoepfe:
        assert knopf.toolTip(), knopf.text()
        rechts = [
            label for label in tab.findChildren(QLabel)
            if label.isVisible() and label.text() and label.toolTip() == knopf.toolTip()
            and abs(label.y() - knopf.y()) < knopf.height() and label.x() > knopf.x()
        ]
        assert len(rechts) == 1, knopf.text()


def test_pdf_exportfehler_unterscheidet_datei_und_programmfehler(qtbot, monkeypatch):
    """Teil 9 Nr. 5: nur ein Dateifehler wird auf Zielpfad/geöffnete Datei geschoben."""
    import desktop_gemeinsam

    meldungen, protokolliert = [], []
    monkeypatch.setattr(desktop_gemeinsam.QMessageBox, "critical", lambda *a, **k: meldungen.append(a[2]))
    monkeypatch.setattr(desktop_gemeinsam, "fehler_protokollieren", protokolliert.append)

    desktop_gemeinsam._export_fehler_anzeigen(None, PermissionError(13, "Permission denied", "x.pdf"))
    assert "konnte nicht gespeichert werden" in meldungen[-1] and "anderen Programm" in meldungen[-1]
    assert protokolliert == []

    desktop_gemeinsam._export_fehler_anzeigen(None, KeyError("Albers"))
    assert "Programmfehler (KeyError: 'Albers')" in meldungen[-1]
    assert "anderen Programm" not in meldungen[-1] and len(protokolliert) == 1


def test_export_tab_anmeldeformular_warnt_ohne_meldestelle(qtbot, conn, tmp_path, monkeypatch):
    """UX-Test 2026-11, T7: Beim Erzeugen des Formulars ohne Meldestelle noch einmal warnen
    (Vorgabe Nein); „Nein“ erzeugt nichts."""
    set_veranstaltung(conn, verein="SGV", datum="2026-11-14", angebotene_pruefungen="DK1", verband="HSVRM")
    ziel = tmp_path / "Anmeldeformular.pdf"
    monkeypatch.setattr("desktop_gemeinsam.QFileDialog.getSaveFileName", lambda *a, **k: (str(ziel), ""))
    fragen, vorgaben = [], []
    antwort = [QMessageBox.No]
    monkeypatch.setattr("app.QMessageBox.question",
                        lambda *a, **k: fragen.append(a[2]) or vorgaben.append(a[4]) or antwort[0])
    tab = ExportTab(conn)
    qtbot.addWidget(tab)
    tab._anmeldeformular_exportieren()
    assert fragen and fragen[0].startswith("Meldestelle ist leer") and "wohin" in fragen[0]
    assert vorgaben[0] == QMessageBox.No
    assert not ziel.exists()
    antwort[0] = QMessageBox.Yes
    tab._anmeldeformular_exportieren()
    assert ziel.exists()

    # Verifikation B2: nur der Verband fehlt bzw. beides fehlt.
    set_veranstaltung(conn, verein="SGV", datum="2026-11-14", angebotene_pruefungen="DK1", meldestelle="E. Muster")
    tab._anmeldeformular_exportieren()
    assert fragen[-1].startswith("Verband ist leer und fehlt") and "wohin" not in fragen[-1]
    set_veranstaltung(conn, verein="SGV", datum="2026-11-14", angebotene_pruefungen="DK1")
    tab._anmeldeformular_exportieren()
    assert fragen[-1].startswith("Verband und Meldestelle sind leer und fehlen")


# --- Bewertungsbogen-Direkt-Export aus der Teilnehmerliste (21.09.) ----------------
# Nutzerwunsch: "In Teilnehmerliste Absprung zu Bewertungsbögen erzeugen einfügen?" -
# Entscheidung (Rückfrage beantwortet): Direkt-Button pro Teilnehmer statt nur eines
# Links zum Export-Tab.


def test_bewertungsbogen_btn_aktiviert_sich_erst_bei_auswahl(qtbot, conn):
    _teilnehmer_anlegen(conn)
    tab = TeilnehmerTab(conn)
    qtbot.addWidget(tab)
    tab.show()

    assert not tab.bewertungsbogen_btn.isEnabled()
    tab.tabelle.selectRow(0)
    assert tab.bewertungsbogen_btn.isEnabled()


def test_bewertungsbogen_direktexport_erzeugt_pdf_fuer_ausgewaehlten_teilnehmer(qtbot, conn, tmp_path, monkeypatch):
    _teilnehmer_anlegen(conn, nachname="Eins", startnummer=1)
    _teilnehmer_anlegen(conn, nachname="Zwei", startnummer=2)
    tab = TeilnehmerTab(conn)
    qtbot.addWidget(tab)
    tab.show()

    zeile_zwei = next(row for row, t in enumerate(tab._teilnehmer_je_zeile) if t["nachname"] == "Zwei")
    tab.tabelle.selectRow(zeile_zwei)

    ziel_pfad = tmp_path / "bogen.pdf"
    monkeypatch.setattr("app.QFileDialog.getSaveFileName", lambda *a, **k: (str(ziel_pfad), "PDF-Datei (*.pdf)"))

    qtbot.mouseClick(tab.bewertungsbogen_btn, Qt.MouseButton.LeftButton)

    assert ziel_pfad.exists()

    # Teil 1 Nr. 5: Sonderzeichen im Nachnamen ergeben einen flachen, gültigen Dateinamen.
    conn.execute("UPDATE teilnehmer SET nachname = 'Meier/Schulz: Zwei' WHERE nachname = 'Zwei'")
    conn.commit()
    tab.aktualisieren()
    from db import get_teilnehmer

    zeile = next(row for row in range(tab.tabelle.rowCount())
                 if get_teilnehmer(conn, tab.tabelle.item(row, 0).data(Qt.UserRole))["nachname"].startswith("Meier"))
    tab.tabelle.selectRow(zeile)
    vorschlaege = []
    monkeypatch.setattr("desktop_gemeinsam._speicherort_waehlen", lambda _p, _a, _t, vorschlag, *_f: vorschlaege.append(vorschlag))
    qtbot.mouseClick(tab.bewertungsbogen_btn, Qt.MouseButton.LeftButton)
    assert vorschlaege == ["Bewertungsbogen_2_Meier-Schulz-Zwei.pdf"]
    assert "gespeichert" in tab.status_label.text()
    assert str(ziel_pfad) in tab.status_label.text()


def test_bewertungsbogen_direktexport_dreikampf_fragt_nach_der_form(qtbot, conn, tmp_path, monkeypatch):
    """Wunsch 10.11.2026: Beim Dreikampf fragt der Knopf, ob zwei Seiten oder drei Blätter
    (je Disziplin) erzeugt werden; Abbrechen erzeugt nichts, ED fragt nicht."""
    from PySide6.QtWidgets import QMessageBox
    from pypdf import PdfReader

    _teilnehmer_anlegen(conn, nachname="Drei", art="DK", disziplin=None, startnummer=1)
    _teilnehmer_anlegen(conn, nachname="Ed", startnummer=2)
    tab = TeilnehmerTab(conn)
    qtbot.addWidget(tab)
    tab.show()
    ziel_pfad = tmp_path / "bogen.pdf"
    monkeypatch.setattr("app.QFileDialog.getSaveFileName", lambda *a, **k: (str(ziel_pfad), "PDF-Datei (*.pdf)"))
    zeile_dk = next(r for r, t in enumerate(tab._teilnehmer_je_zeile) if t["nachname"] == "Drei")
    zeile_ed = next(r for r, t in enumerate(tab._teilnehmer_je_zeile) if t["nachname"] == "Ed")

    gewaehlt = []

    def waehle(text):
        def exec_(box):
            gewaehlt.append(box)
            box._antwort = next(b for b in box.buttons() if b.text() == text)
        return exec_

    for text, seiten in (("Drei Blätter (je Disziplin)", 3), ("Zwei Seiten", 2)):
        monkeypatch.setattr(QMessageBox, "exec", waehle(text))
        monkeypatch.setattr(QMessageBox, "clickedButton", lambda box: box._antwort)
        ziel_pfad.unlink(missing_ok=True)
        tab.tabelle.selectRow(zeile_dk)
        qtbot.mouseClick(tab.bewertungsbogen_btn, Qt.MouseButton.LeftButton)
        assert len(PdfReader(str(ziel_pfad)).pages) == seiten

    ziel_pfad.unlink()
    monkeypatch.setattr(QMessageBox, "exec", waehle("Abbrechen"))
    qtbot.mouseClick(tab.bewertungsbogen_btn, Qt.MouseButton.LeftButton)
    assert not ziel_pfad.exists()

    anzahl = len(gewaehlt)
    tab.tabelle.selectRow(zeile_ed)
    qtbot.mouseClick(tab.bewertungsbogen_btn, Qt.MouseButton.LeftButton)
    assert len(gewaehlt) == anzahl and ziel_pfad.exists()  # ED: keine Rückfrage


# --- Auswahl, welche LK/Disziplin in die Bewertungsbögen-Sammel-PDF sollen (21.09.) -
# Nutzerwunsch: "Das PDF enthält jetzt alle LK + Disziplinen. Auf einmal ein
# Doppelseitiger Druck führt dann dazu, dass ich bei den ED auf der Rückseite ein
# anderes Team habe. [...] ggf. auch nur Auswählbar, welche LK/Disziplin ich gedruckt
# haben will?" Standard = alle angehakt (heutiges Verhalten bleibt Default).


def test_bewertungsbogen_auswahl_dialog_standardmaessig_alle_angehakt(qtbot):
    dialog = BewertungsbogenAuswahlDialog(None, ["DK LK 1", "Trümmer LK 2"])
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.ausgewaehlte_labels() == {"DK LK 1", "Trümmer LK 2"}

    dialog.liste.item(0).setCheckState(Qt.Unchecked)
    assert dialog.ausgewaehlte_labels() == {"Trümmer LK 2"}

    # Desktop-Prüfung 14.10.2026, Teil 6 Nr. 6: OK nur mit mindestens einem Haken.
    ok = dialog.buttons.button(QDialogButtonBox.Ok)
    dialog._alle_umschalten(Qt.Unchecked)
    assert not ok.isEnabled()
    dialog.liste.item(1).setCheckState(Qt.Checked)
    assert ok.isEnabled()


def test_pdf_exportieren_meldet_fehler_ohne_statusmeldung(qtbot, tmp_path, monkeypatch, gespeichert_meldungen):
    """Teil 6 Nr. 11/12: der gemeinsame Ablauf meldet einen Fehler und setzt keinen Status."""
    import desktop_gemeinsam
    from PySide6.QtWidgets import QLabel

    monkeypatch.setattr(desktop_gemeinsam, "_speicherort_waehlen", lambda *a: str(tmp_path / "x.pdf"))
    fehler = []
    monkeypatch.setattr(desktop_gemeinsam, "_export_fehler_anzeigen", lambda _p, exc, *_a: fehler.append(exc))
    status = QLabel("alt")

    def kaputt(_pfad):
        raise PermissionError(13, "Permission denied")

    desktop_gemeinsam._pdf_exportieren(None, None, status, "Titel", "x.pdf", kaputt, "gespeichert")
    assert len(fehler) == 1 and status.text() == "alt" and not gespeichert_meldungen
    desktop_gemeinsam._pdf_exportieren(None, None, status, "Titel", "x.pdf", lambda _p: 3, lambda n: f"{n} Bögen")
    assert status.text().startswith("3 Bögen:") and gespeichert_meldungen[-1][1] == "3 Bögen"


def test_bewertungsbogen_auswahl_dialog_ohne_teilnehmer_deaktiviert_ok(qtbot):
    dialog = BewertungsbogenAuswahlDialog(None, [])
    qtbot.addWidget(dialog)
    assert not dialog.buttons.button(QDialogButtonBox.Ok).isEnabled()


def test_auswertung_zeigt_teilbewertung(qtbot, conn):
    """Vor-Build-Verifikation 1.0.55, Befund 6: Der Reiter „Auswertung“ zeigt bei einem
    Abbruch mit Grund die Teilpunkte und den Eintrag laut PO statt „–“."""
    tid = _teilnehmer_anlegen(conn, disziplin="Flächensuche")
    eintragen_ergebnis(conn, tid, "Flächensuche", 30, 10)
    setze_ergebnis_status(conn, tid, False, True, abbruch_grund="krankheit")
    tab = AuswertungTab(conn)
    qtbot.addWidget(tab)
    tab.aktualisieren()
    zeile = [tab.tabelle.item(0, c).text() for c in range(tab.tabelle.columnCount())]
    assert "40" in zeile
    assert "Abbruch wegen Krankheit" in zeile
    assert "–" not in zeile
    assert zeile[-1].startswith("Abbruch (von 1 Starter")


def test_lange_namensliste_in_auswertung_verbreitert_fenster_nicht(qtbot, termin):
    """UX-Test 02.10.2026, U12: Die Liste "Noch ohne vollständiges Ergebnis" bricht um,
    statt das Hauptfenster über die Bildschirmbreite zu ziehen."""
    conn, pfad = termin
    for i in range(40):
        _teilnehmer_anlegen(conn, nachname=f"Langername{i:02d}", vorname="Vorname", startnummer=i + 1)

    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    tab = fenster.auswertung_tab
    tab.aktualisieren()

    assert tab.ausstehend_label.wordWrap()
    assert tab.status_label.wordWrap()
    assert tab.ausstehend_label.minimumSizeHint().width() < 600


def test_pdf_speichern_meldet_ort_und_nutzt_ausdrucke_ordner(qtbot, termin, monkeypatch, gespeichert_meldungen):
    """UX-Test 02.10.2026, U7: Standard-Ablageort ist "Ausdrucke/<Termin>" neben der
    Termin-Datei (wird beim Speichern angelegt); nach dem Speichern erscheint eine Meldung
    und die Statuszeile zeigt den Pfad in Windows-Schreibweise."""
    conn, pfad = termin
    set_veranstaltung(conn, verein="SGV Köppern e.V.", datum="2026-09-19")
    _teilnehmer_anlegen(conn)

    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    export_tab = fenster.export_tab
    erwartet = os.path.join(os.path.dirname(os.path.abspath(pfad)), "Ausdrucke",
                            os.path.splitext(os.path.basename(pfad))[0])
    assert export_tab._ablageort.pfad == erwartet

    vorschlaege = []

    def dialog(_parent, _titel, vorschlag, _filter):
        vorschlaege.append(vorschlag)
        return vorschlag.replace("\\", "/"), "PDF-Datei (*.pdf)"

    monkeypatch.setattr("desktop_gemeinsam.QFileDialog.getSaveFileName", dialog)
    monkeypatch.setattr("app.pdf_export.erstelle_ergebnisliste_pdf", lambda c, p, *a, **k: None)

    export_tab._ergebnisliste_exportieren()

    assert os.path.isdir(erwartet)
    assert os.path.dirname(vorschlaege[0]) == erwartet
    assert len(gespeichert_meldungen) == 1
    assert gespeichert_meldungen[0][1] == "Ergebnisliste gespeichert"
    # Pfad in der Schreibweise des Systems (Windows "\\", Linux "/") - CI läuft unter Linux.
    assert export_tab.status_label.text().split(": ", 1)[1] == os.path.normpath(
        os.path.join(erwartet, "Ergebnisliste_2026-09-19.pdf")
    )


def test_auswertung_namensliste_vorname_nachname(qtbot, termin):
    """UX-Test 02.10.2026, K2: "Vorname Nachname; …" statt "Nachname, Vorname, …"."""
    conn, pfad = termin
    _teilnehmer_anlegen(conn, nachname="Graf", vorname="Greta", startnummer=1)
    _teilnehmer_anlegen(conn, nachname="Iske", vorname="Ina", startnummer=2)
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.auswertung_tab.aktualisieren()
    assert "Greta Graf; Ina Iske" in fenster.auswertung_tab.ausstehend_label.text()


def test_auswertung_erklaert_von_x_bei_offenen(qtbot, conn):
    """UX-Test 02.10.2026, K9: Hinweiszeile + Tooltip, solange jemand in der LK offen ist."""
    fertig = _teilnehmer_anlegen(conn, nachname="Fertig", startnummer=1)
    eintragen_ergebnis(conn, fertig, "Flächensuche", 60, 40)
    _teilnehmer_anlegen(conn, nachname="Offen1", startnummer=2)
    _teilnehmer_anlegen(conn, nachname="Offen2", startnummer=3)
    tab = AuswertungTab(conn)
    qtbot.addWidget(tab)
    tab.aktualisieren()

    lk = tab.tabelle.item(0, 1).text()
    platz = tab.tabelle.item(0, tab.tabelle.columnCount() - 1)
    assert platz.text() == "1. von 1"
    assert "nur Starter mit vollständigem Ergebnis" in platz.toolTip()
    assert "2 noch offen" in platz.toolTip()
    assert f"Hinweis {lk}: „von 1“ zählt nur Starter mit vollständigem Ergebnis – 2 noch offen." in (
        tab.ausstehend_label.text()
    )


def test_bewertungsbogen_auch_in_ergebniserfassung_und_auswertung(qtbot, conn, tmp_path, monkeypatch):
    from pypdf import PdfReader

    tid = _teilnehmer_anlegen(conn, nachname="Albers", startnummer=1)
    _db_modul.eintragen_ergebnis(conn, tid, "Flächensuche", 50, 30)
    ziel = tmp_path / "bogen.pdf"
    monkeypatch.setattr("app.QFileDialog.getSaveFileName", lambda *a, **k: (str(ziel), "PDF-Datei (*.pdf)"))
    ergebnis_tab, auswertung_tab = ErgebnisTab(conn), AuswertungTab(conn)
    for tab in (ergebnis_tab, auswertung_tab):
        qtbot.addWidget(tab)
        tab.show()
        assert not tab.bewertungsbogen_btn.isEnabled()  # noch keine Zeile gewählt
        tab.tabelle.setCurrentCell(0, 0)
        assert tab.bewertungsbogen_btn.isEnabled()
        ziel.unlink(missing_ok=True)
        qtbot.mouseClick(tab.bewertungsbogen_btn, Qt.MouseButton.LeftButton)
        assert len(PdfReader(str(ziel)).pages) >= 1


def test_ablageort_knopf_in_teilnehmer_zeitplan_auswertung_und_formular_import(qtbot, conn, monkeypatch):
    geoeffnet = []
    monkeypatch.setattr("desktop_gemeinsam._url_oeffnen", lambda _p, url, _a: geoeffnet.append(url.toLocalFile()) or True)
    from desktop_gemeinsam import _Ablageort

    ablageort = _Ablageort(str(__import__('pathlib').Path(conn.execute("PRAGMA database_list").fetchone()[2]).parent))
    for tab in (TeilnehmerTab(conn, ablageort=ablageort), ZeitplanTab(conn, ablageort),
                AuswertungTab(conn, ablageort), ExportTab(conn, None, ablageort)):
        qtbot.addWidget(tab)
        tab.show()
        knopf = tab.ablageort_btn if hasattr(tab, "ablageort_btn") else next(
            b for b in tab.findChildren(QPushButton) if b.text() == "Ablageort öffnen")
        assert knopf.isVisible()
        knopf.click()
    assert len(geoeffnet) == 4


def test_export_tab_hat_abrechnung_und_checkliste(qtbot, conn, tmp_path, monkeypatch):
    from pypdf import PdfReader

    set_veranstaltung(conn, verein="SGV", datum="2026-11-14", wertungsrichter_1="Erika Beispiel")
    tab = ExportTab(conn)
    qtbot.addWidget(tab)
    tab.show()
    ziele = []

    def waehle(*_a, **_k):
        ziel = tmp_path / f"datei{len(ziele)}.pdf"
        ziele.append(ziel)
        return str(ziel), "PDF-Datei (*.pdf)"

    monkeypatch.setattr("desktop_gemeinsam.QFileDialog.getSaveFileName", waehle)
    for text, inhalt in (("Abrechnung Leistungsrichter (PDF)…", "Erika Beispiel"), ("Checkliste (PDF)…", "Punkten erledigt")):
        knopf = next(b for b in tab.findChildren(QPushButton) if b.text() == text)
        knopf.click()
        seite = PdfReader(str(ziele[-1])).pages[0].extract_text()
        assert inhalt in seite


def test_auswertung_und_startdialog_sortierung_per_spaltenklick(qtbot, conn):
    for nr, (name, punkte) in enumerate([("Albers", 40), ("Brandt", 55), ("Claasen", 48)], start=1):
        tid = _teilnehmer_anlegen(conn, nachname=name, startnummer=nr)
        _db_modul.eintragen_ergebnis(conn, tid, "Flächensuche", punkte, 30)
    tab = AuswertungTab(conn)
    qtbot.addWidget(tab)
    tab.show()
    namen = lambda: [tab.tabelle.item(r, 2).text() for r in range(tab.tabelle.rowCount())]  # noqa: E731
    standard = namen()
    tab._spalte_geklickt(4)  # Gesamtpunkte aufsteigend
    assert [n.split(",")[0] for n in namen()] == ["Albers", "Claasen", "Brandt"]
    tab._spalte_geklickt(4)  # absteigend
    assert [n.split(",")[0] for n in namen()] == ["Brandt", "Claasen", "Albers"]
    assert sorted(namen()) == sorted(standard)
    # ID bleibt an der Zeile (Bewertungsbogen der angeklickten Zeile)
    tab.tabelle.setCurrentCell(0, 0)
    ids = {tab._teilnehmer_id_der_aktuellen_zeile()}
    assert None not in ids


def test_druckknoepfe_in_uebersicht_und_verwaltung(qtbot, conn, tmp_path, monkeypatch):
    """Marco 10.11.2026: Richter-Bedarf (Übersicht) und Checkliste (Verwaltung) lassen sich direkt
    im eigenen Reiter als PDF speichern; „Ablageort öffnen“ ist dort ebenfalls da."""
    from pypdf import PdfReader

    from desktop_gemeinsam import _Ablageort

    set_veranstaltung(conn, verein="SGV", datum="2026-11-14")
    _teilnehmer_anlegen(conn, nachname="Albers", startnummer=1)
    ablageort = _Ablageort(str(tmp_path))
    geoeffnet = []
    monkeypatch.setattr("desktop_gemeinsam._url_oeffnen", lambda _p, url, _a: geoeffnet.append(url.toLocalFile()) or True)
    ziele = []

    def waehle(*_a, **_k):
        ziel = tmp_path / f"datei{len(ziele)}.pdf"
        ziele.append(ziel)
        return str(ziel), "PDF-Datei (*.pdf)"

    monkeypatch.setattr("desktop_gemeinsam.QFileDialog.getSaveFileName", waehle)
    uebersicht = TeilnehmerUebersichtTab(conn, ablageort=ablageort)
    verwaltung = VerwaltungTab(conn, ablageort=ablageort)
    for tab in (uebersicht, verwaltung):
        qtbot.addWidget(tab)
        tab.show()
        assert tab.ablageort_btn.isVisible()
        tab.ablageort_btn.click()
    assert len(geoeffnet) == 2
    uebersicht.richterbedarf_btn.click()
    assert "Richter" in PdfReader(str(ziele[-1])).pages[0].extract_text()
    verwaltung.checkliste_pdf_btn.click()
    assert "Checkliste zum Prüfungstermin" in PdfReader(str(ziele[-1])).pages[0].extract_text()
