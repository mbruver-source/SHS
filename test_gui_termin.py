"""GUI-Tests: Hauptfenster, Startdialog, Termine öffnen/wechseln/schließen, Sitzungsende, Sicherung.

Fixtures und Hilfen stehen in gui_hilfen.py (Aufteilung von test_app_gui.py, 11.11.2026)."""

from __future__ import annotations

import os
import sys
import pytest
from contextlib import closing
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel, QLineEdit, QMessageBox, QPushButton
from app import HauptFenster, StartDialog
from desktop_dialoge import TeilnehmerDialog, TerminImportDialog, VeranstaltungsDialog
from desktop_ergebnis import ErgebnisTab
from db import (
    ALLE_PRUEFUNGEN,
    NeuerTeilnehmer,
    TerminInfo,
    add_teilnehmer,
    add_zeitplan_pruefungsblock,
    add_zeitplan_richter,
    get_veranstaltung,
    init_db,
    list_teilnehmer,
    set_veranstaltung,
    setze_keine_teilnahme,
)
from desktop_dialoge import (
    DIALOG_MAX_HOEHE_ANTEIL,
    _wiederherstellungsziele_planen,
)
import desktop_programm
from desktop_verwaltung import DatensicherungTab, VerwaltungTab
from desktop_zeitplan import ZeitplanTab
from desktop_gemeinsam import _aktualisiere_veranstaltung_feld
from gui_hilfen import *  # noqa: F401,F403


def test_termine_ordner_ist_in_allen_modulen_geschuetzt(_termine_ordner_schuetzen):
    """Gegenprobe zum Schutz oben: kein Desktop-Modul (auch db und db_sicherung) nutzt im
    Test die echte Funktion termine_ordner; alle liefern den Temp-Ordner des Schutzes."""
    import importlib
    for modulname in DESKTOP_MODULE + ("db", "db_sicherung"):
        modul = importlib.import_module(modulname)
        if hasattr(modul, "termine_ordner"):
            assert modul.termine_ordner is not _ECHTER_TERMINE_ORDNER, modulname
            assert modul.termine_ordner() == _termine_ordner_schuetzen, modulname


# --- Zeitplan: Seitenleiste "Offene Starts" ------------------------------------------


def test_offene_starts_markiert_eingeplante_und_fehlende_gruppen(qtbot, conn):
    # Nutzerwunsch (21.09.): Überblick, welche benötigten Starts (Art/LK/Disziplin)
    # bereits als Prüfungsblock im Zeitplan stecken und welche noch fehlen, ohne durch
    # alle Richter-Spalten scrollen zu müssen (siehe zeitplan_gruppen_status in db.py).
    _teilnehmer_anlegen(conn, art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=1)
    _teilnehmer_anlegen(conn, art="ED", stufe=2, disziplin="Flächensuche", startnummer=2)
    richter_id = add_zeitplan_richter(conn)
    add_zeitplan_pruefungsblock(conn, richter_id, art="ED", stufe=1, disziplin="Trümmerfeld", dauer_minuten=10)

    tab = ZeitplanTab(conn)
    qtbot.addWidget(tab)

    text = tab._offene_starts_label.text()
    assert "Trümmer LK 1" in text
    assert "Fläche LK 2" in text
    assert "noch offen" in text
    # Die bereits eingeplante Gruppe ist NICHT als "noch offen" markiert.
    eingeplante_zeile = next(z for z in text.split("<br>") if "Trümmer LK 1" in z)
    assert "noch offen" not in eingeplante_zeile


def test_offene_starts_ohne_teilnehmer_zeigt_hinweis(qtbot, conn):
    tab = ZeitplanTab(conn)
    qtbot.addWidget(tab)
    assert tab._offene_starts_label.text() == "Noch keine Teilnehmer erfasst."


def test_sicherung_dateiname_nennt_umfang_und_tag(qtbot, conn):
    """UX-Test 2026-11, T11 (ersetzt K10): Der Name nennt „alle Termine“ statt Datum und
    Verein des geöffneten Termins - gesichert werden immer alle. T10: Der Hinweis im Reiter
    nennt das Passwort als freiwillig."""
    import datetime

    heute = datetime.date.today().isoformat()
    set_veranstaltung(conn, verein="SGV Köppern e.V.", datum="2026-11-14")
    tab = DatensicherungTab(conn=conn)
    qtbot.addWidget(tab)
    assert tab._dateiname_vorschlag() == f"SHS-Sicherung_{heute}_alle-Termine.zip"
    assert "Köppern" not in tab._dateiname_vorschlag()  # Verein des Termins nicht mehr im Namen
    texte = " ".join(label.text() for label in tab.findChildren(QLabel))
    assert "auf Wunsch mit Passwort" in texte
    assert "Passwort getrennt von der Sicherung aufbewahren" not in texte


@pytest.mark.parametrize(
    "version", sorted(os.listdir(_ALTDATEN)) if os.path.isdir(_ALTDATEN) else []
)
def test_altversion_oeffnet_im_hauptfenster_mit_allen_reitern(qtbot, tmp_path, version, monkeypatch):
    """T3 (Upgrade-Tests, 03.10.2026): Termin-Datei einer älteren Version (siehe
    test_altversionen.py) im Hauptfenster öffnen und jeden Reiter einmal anzeigen."""
    import shutil

    kopie = tmp_path / "termin.sqlite"
    shutil.copy(os.path.join(_ALTDATEN, version, "termin.sqlite"), kopie)
    rueckfragen_beantworten(monkeypatch, QMessageBox.No)
    conn = init_db(str(kopie))
    try:
        fenster = HauptFenster(conn, str(kopie))
        qtbot.addWidget(fenster)
        fenster.show()
        for index in range(fenster._tabs.count()):
            fenster._tabs.setCurrentIndex(index)
            qtbot.wait(10)
        assert fenster.teilnehmer_tab.tabelle.rowCount() == 7
    finally:
        conn.close()


def test_selbsttest_erfolg_und_fehlerfall(qtbot, tmp_path, monkeypatch):
    """T1 (Marco 03.10.2026): "--selbsttest" liefert 0 und ein Protokoll; scheitert ein
    Schritt (z. B. ein in der EXE fehlendes Modul), Exit-Code 1 mit Fehlerzeile."""
    import pdf_export
    import selbsttest

    protokoll = tmp_path / "ok.log"
    assert selbsttest.fuehre_selbsttest_aus(str(protokoll)) == 0
    text = protokoll.read_text(encoding="utf-8")
    assert "ERGEBNIS: alles OK" in text and "Oberfläche mit allen Reitern" in text

    def kaputt(*_a, **_k):
        raise ImportError("reportlab fehlt (simuliert)")

    monkeypatch.setattr(pdf_export, "erstelle_statistik_pdf", kaputt)
    protokoll = tmp_path / "fehler.log"
    assert selbsttest.fuehre_selbsttest_aus(str(protokoll)) == 1
    text = protokoll.read_text(encoding="utf-8")
    assert "FEHLER  PDF-Ausgaben" in text and "reportlab fehlt (simuliert)" in text
    assert "ERGEBNIS: 1 Fehler" in text


def test_selbsttest_schritt_symbole(qtbot, tmp_path, monkeypatch):
    """Erscheinungsbild „Beagle“ (Marco 01.11.2026): fehlen die SVGs im Bundle, meldet der
    Selbsttest das als Fehler."""
    import desktop_gemeinsam
    import selbsttest

    protokoll = tmp_path / "ok.log"
    selbsttest.fuehre_selbsttest_aus(str(protokoll))
    assert f"OK      Symbole ({len(desktop_gemeinsam.SYMBOL_NAMEN)} Symbole (QtSvg))" in protokoll.read_text(encoding="utf-8")

    monkeypatch.setattr(desktop_gemeinsam, "_symbol_zwischenspeicher", {})
    monkeypatch.setattr(desktop_gemeinsam, "symbol_pfad", lambda name: str(tmp_path / f"{name}.svg"))
    protokoll = tmp_path / "fehler.log"
    assert selbsttest.fuehre_selbsttest_aus(str(protokoll)) == 1
    text = protokoll.read_text(encoding="utf-8")
    assert "FEHLER  Symbole" in text and "check.svg" in text


def test_selbsttest_schritt_lizenztexte(qtbot, tmp_path, monkeypatch):
    """OFFEN B14 (Marco 01.11.2026): im Quellcode-Ordner fehlt THIRD_PARTY_LICENSES.txt nur
    als Hinweis; in der gebauten Fassung (sys.frozen) ist das ein Fehler, ebenso eine leere
    LICENSE."""
    import desktop_gemeinsam
    import selbsttest

    ordner = tmp_path / "bundle"
    ordner.mkdir()
    (ordner / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    monkeypatch.setattr(desktop_gemeinsam, "bundle_pfad", lambda *teile: str(ordner.joinpath(*teile)))

    def zeile(log):
        selbsttest.fuehre_selbsttest_aus(str(log))
        return next(z for z in log.read_text(encoding="utf-8").splitlines() if "Lizenztexte" in z)

    assert zeile(tmp_path / "quelle.log").startswith("OK      Lizenztexte (HINWEIS: THIRD_PARTY_LICENSES.txt fehlt")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert zeile(tmp_path / "gebaut.log") == "FEHLER  Lizenztexte"
    (ordner / "THIRD_PARTY_LICENSES.txt").write_text("Übersicht / Overview:\n", encoding="utf-8")
    assert zeile(tmp_path / "komplett.log") == "OK      Lizenztexte (LICENSE, THIRD_PARTY_LICENSES.txt)"
    (ordner / "LICENSE").write_text("", encoding="utf-8")
    assert zeile(tmp_path / "leer.log") == "FEHLER  Lizenztexte"


def test_fremdobjekte_meldung(qtbot, monkeypatch):
    """H-1: Nach dem Entfernen fremder Trigger/Views erscheint ein Hinweis, sonst nicht."""
    import app as app_modul

    meldungen = meldungen_sammeln(monkeypatch, "warning")
    monkeypatch.setattr(app_modul, "entfernte_fremdobjekte", lambda: [])
    app_modul._fremdobjekte_melden(None)
    assert meldungen == []
    monkeypatch.setattr(app_modul, "entfernte_fremdobjekte", lambda: ["trigger manipulation"])
    app_modul._fremdobjekte_melden(None)
    assert "trigger manipulation" in meldungen[0]


def test_bestehender_teilnehmer_im_dialog_zeigt_gespeicherte_zuordnung(qtbot, conn):
    _teilnehmer_anlegen(
        conn,
        art="DK",
        disziplin=None,
        gegenstand_1="Schlüsselbund",
        gegenstand_1_disziplin="Behältnisstrecke",
    )
    vorhandener = list_teilnehmer(conn)[0]

    dialog = TeilnehmerDialog(vorhandener=vorhandener)
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.gegenstand_1.text() == "Schlüsselbund"
    assert dialog.gegenstand_1_disziplin.currentText() == "Behältnisstrecke"
    # Nicht belegte Gegenstände zeigen "frei", nicht irgendeine Disziplin.
    assert dialog.gegenstand_2_disziplin.currentText() == "frei"


def test_bestehender_teilnehmer_im_dialog_zeigt_verwaltungs_und_kontaktfelder(qtbot, conn):
    _teilnehmer_anlegen(
        conn,
        verband="VDH",
        mitgliedsnummer="12345",
        wurftag="2023-04-01",
        strasse="Hauptstraße",
        hausnummer="12a",
        plz="61479",
        ort="Höppern",
        email="max.muster@example.com",
        telefon="06171 123456",
    )
    vorhandener = list_teilnehmer(conn)[0]

    dialog = TeilnehmerDialog(vorhandener=vorhandener)
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.verband.text() == "VDH"
    assert dialog.mitgliedsnummer.text() == "12345"
    assert dialog.wurftag.text() == "01.04.2023"  # Anzeige TT.MM.JJJJ (M5, 22.09.)
    assert dialog.strasse.text() == "Hauptstraße"
    assert dialog.hausnummer.text() == "12a"
    assert dialog.plz.text() == "61479"
    assert dialog.ort.text() == "Höppern"
    assert dialog.email.text() == "max.muster@example.com"
    assert dialog.telefon.text() == "06171 123456"


def test_bestehender_teilnehmer_mit_halter_zeigt_block_direkt_aufgeklappt(qtbot, conn):
    _teilnehmer_anlegen(
        conn,
        rasse="Beagle",
        tollwutimpfung_bis="2027-05-01",
        halter_vorname="Peter",
        halter_nachname="Muster",
        halter_mitgliedsverein="SGV Köppern e.V.",
    )
    vorhandener = list_teilnehmer(conn)[0]

    dialog = TeilnehmerDialog(vorhandener=vorhandener)
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.rasse.text() == "Beagle"
    assert dialog.tollwutimpfung_bis.text() == "01.05.2027"  # Anzeige TT.MM.JJJJ (M5, 22.09.)
    assert dialog.halter_weicht_ab.isChecked() is True
    assert dialog.gruppe_halter.isVisible() is True
    assert dialog.halter_vorname.text() == "Peter"
    assert dialog.halter_mitgliedsverein.text() == "SGV Köppern e.V."


def test_bestehender_teilnehmer_ohne_halter_zeigt_block_eingeklappt(qtbot, conn):
    _teilnehmer_anlegen(conn)
    vorhandener = list_teilnehmer(conn)[0]

    dialog = TeilnehmerDialog(vorhandener=vorhandener)
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.halter_weicht_ab.isChecked() is False
    assert dialog.gruppe_halter.isVisible() is False


# --- Ausfüllbares Anmeldeformular (Nutzerwunsch 28.09.2026) -------------------------
# Veranstaltungsdialog: Verband, Meldestelle, angebotene Prüfungen; Export-Button im
# Reiter "Ausdrucke/Export"; Import-Button im Reiter "Formular-Import".


def test_veranstaltungsdialog_anmeldeformular_felder_vorbelegt_und_auslesbar(qtbot):
    dialog = VeranstaltungsDialog(vorbelegung={
        "verein": "SGV", "datum": "2026-11-14", "verband": "HSVRM",
        "meldestelle": "Erika Muster\nmeldung@example.org",
        "angebotene_pruefungen": "DK1,ED2-Trümmerfeld",
    }, bearbeiten=True)
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.verband.text() == "HSVRM"
    assert dialog.meldestelle.toPlainText() == "Erika Muster\nmeldung@example.org"
    assert set(dialog.pruefung_checkboxen) == {p.kuerzel for p in ALLE_PRUEFUNGEN}
    angehakt = {k for k, cb in dialog.pruefung_checkboxen.items() if cb.isChecked()}
    assert angehakt == {"DK1", "ED2-Trümmerfeld"}
    assert dialog.pruefung_checkboxen["ED3-Flächensuche"].text() == "Fläche LK 3"

    dialog.pruefung_checkboxen["DK1"].setChecked(False)
    dialog.pruefung_checkboxen["ED3-Behältnisstrecke"].setChecked(True)
    assert dialog.angebotene_pruefungen_text() == "ED2-Trümmerfeld,ED3-Behältnisstrecke"
    dialog.meldestelle.setPlainText("  \n ")
    assert dialog.meldestelle_text() is None


def test_veranstaltung_bearbeiten_speichert_anmeldeformular_felder(qtbot, conn, monkeypatch):
    set_veranstaltung(conn, verein="SGV", datum="2026-11-14", zeitplan_start="09:00")

    def _exec_mit_eingaben(dialog):
        dialog.verband.setText("HSVRM")
        dialog.meldestelle.setPlainText("Erika Muster\nmeldung@example.org")
        dialog.pruefung_checkboxen["DK2"].setChecked(True)
        dialog.pruefung_checkboxen["ED1-Flächensuche"].setChecked(True)
        # Gespeichert wird beim OK im Dialog selbst (Rückruf), also OK auslösen.
        dialog._pruefen_und_akzeptieren()
        return dialog.result()

    monkeypatch.setattr(VeranstaltungsDialog, "exec", _exec_mit_eingaben)
    tab = VerwaltungTab(conn)
    qtbot.addWidget(tab)
    tab._veranstaltung_bearbeiten()

    gespeichert = get_veranstaltung(conn)
    assert gespeichert["verband"] == "HSVRM"
    assert gespeichert["meldestelle"] == "Erika Muster\nmeldung@example.org"
    assert gespeichert["angebotene_pruefungen"] == "DK2,ED1-Flächensuche"
    assert gespeichert["zeitplan_start"] == "09:00"

    # Eine Änderung aus einem anderen Tab (hier: Zeitplan-Start) darf die neuen Felder
    # nicht wieder leeren.
    _aktualisiere_veranstaltung_feld(conn, zeitplan_start="10:00")
    gespeichert = get_veranstaltung(conn)
    assert gespeichert["zeitplan_start"] == "10:00"
    assert gespeichert["verband"] == "HSVRM"
    assert gespeichert["meldestelle"] == "Erika Muster\nmeldung@example.org"
    assert gespeichert["angebotene_pruefungen"] == "DK2,ED1-Flächensuche"


@pytest.mark.parametrize("antwort, erwartet", [
    (b'{"tag_name": "v1.2.3"}', ("1.2.3", None)),
    (b"[]", (None, "Die Antwort von GitHub konnte nicht gelesen werden.")),
    (b"null", (None, "Die Antwort von GitHub konnte nicht gelesen werden.")),
    (b"{kaputt", (None, "Die Antwort von GitHub konnte nicht gelesen werden.")),
    ("unvollstaendig", (None, "Die Antwort von GitHub konnte nicht gelesen werden.")),
    ("ssl", (None, "Zertifikatsfehler")),
    ("offline", (None, "Keine Verbindung zu GitHub möglich (kein Internetzugang?).")),
    (404, (None, "Es wurde noch kein Release veröffentlicht.")),
    (403, (None, "GitHub antwortete mit Fehler 403.")),
    (b'{"name": "ohne Tag"}', (None, "GitHub hat keine Versionsnummer geliefert.")),
])
def test_neueste_version_pruefen_faengt_alle_antworten_ab(monkeypatch, antwort, erwartet):
    """Desktop-Prüfung 14.10.2026, Teil 8 Nr. 1, 5 und 9: jede Antwort ergibt eine Meldung."""

    import http.client
    import ssl
    import urllib.error
    import urllib.request

    def urlopen(_anfrage, timeout):
        if antwort == "unvollstaendig":
            return _Antwort(fehler=http.client.IncompleteRead(b"{"))
        if antwort == "ssl":
            raise urllib.error.URLError(ssl.SSLCertVerificationError("certificate verify failed"))
        if antwort == "offline":
            raise urllib.error.URLError(OSError("getaddrinfo failed"))
        if isinstance(antwort, int):
            raise urllib.error.HTTPError("https://api.github.com", antwort, "Fehler", {}, None)
        return _Antwort(antwort)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    version, fehler = desktop_programm._neueste_version_pruefen()
    assert version == erwartet[0]
    assert (fehler is None) == (erwartet[1] is None)
    if erwartet[1]:
        assert erwartet[1] in fehler


@pytest.mark.parametrize("antwort", [QMessageBox.No, QMessageBox.Yes])
def test_zweitstart_fragt_nach(qtbot, tmp_path, monkeypatch, antwort):
    """Teil 8 Nr. 6 (Marcos Entscheidung): ein zweiter Start fragt, sperrt aber nicht."""

    monkeypatch.setattr(desktop_programm, "_zweitstart_sperre", [])
    assert desktop_programm.zweitstart_pruefen(tmp_path) is True
    fragen = rueckfragen_sammeln(monkeypatch, antwort, merke="titel_vorgabe")
    assert desktop_programm.zweitstart_pruefen(tmp_path) is (antwort == QMessageBox.Yes)
    assert fragen == [("Programm läuft bereits", QMessageBox.No)]
    for sperre in desktop_programm._zweitstart_sperre:
        sperre.unlock()

    # Lässt sich keine Sperrdatei anlegen (z. B. Datei statt Ordner), startet es ohne Rückfrage.
    (tmp_path / "datei").write_text("x")
    assert desktop_programm.zweitstart_pruefen(tmp_path / "datei") is True and len(fragen) == 1


# --- Automatisches Speichern beim Beenden -------------------------------------------


def test_schliessen_speichert_automatisch_bei_ungespeicherten_aenderungen(qtbot, termin, monkeypatch):
    conn, pfad = termin
    set_veranstaltung(conn, verein="SGV Köppern e.V.", datum="2026-09-19")
    _teilnehmer_anlegen(conn)

    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)

    aufgerufen = {}
    # hat_ungespeicherte_aenderungen() liefert VOR alle_speichern() True, DANACH False -
    # entspricht einem erfolgreichen automatischen Speichern (closeEvent prüft seit dem
    # QS-Fund unten erneut NACH alle_speichern(), siehe dortiger Kommentar - ohne diesen
    # Zustandswechsel hier würde das eine echte, blockierende Rückfrage auslösen statt
    # nur das Auto-Save selbst zu prüfen, wie es dieser Test eigentlich soll).
    zustand = {"ungespeichert": True}
    monkeypatch.setattr(
        type(fenster.ergebnis_tab), "hat_ungespeicherte_aenderungen", lambda self: zustand["ungespeichert"]
    )

    def _speichern(self):
        aufgerufen.setdefault("gespeichert", True)
        zustand["ungespeichert"] = False

    monkeypatch.setattr(type(fenster.ergebnis_tab), "alle_speichern", _speichern)

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


def test_schliessen_fragt_nach_wenn_speichern_zeilen_uebrig_laesst_und_bricht_bei_nein_ab(qtbot, termin, monkeypatch):
    """QS-Fund (19./20.09.): bleiben nach dem automatischen Speichern noch Änderungen
    ungespeichert (z.B. eine Zeile mit nur einem befüllten Feld), darf das Fenster sich
    NICHT einfach trotzdem schließen - vorher ging die Warnung dabei spurlos zusammen mit
    dem Fenster verloren. Hier: Nutzer wählt "Nein" (nicht beenden) - das Fenster muss
    offen bleiben, damit die Zeile noch korrigiert werden kann."""
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()

    # alle_speichern() "gelingt" hier absichtlich nicht (Zustand bleibt ungespeichert) -
    # simuliert genau den Fall, den die bisherige Warnung in alle_speichern() selbst
    # anzeigt (z.B. nur ein Feld einer Zeile ausgefüllt).
    monkeypatch.setattr(type(fenster.ergebnis_tab), "hat_ungespeicherte_aenderungen", lambda self: True)
    monkeypatch.setattr(type(fenster.ergebnis_tab), "alle_speichern", lambda self: None)
    rueckfragen_beantworten(monkeypatch, QMessageBox.No)

    fenster.close()

    assert fenster.isVisible()


def test_schliessen_bei_schreibfehler_fragt_nach_statt_still_zu_verwerfen(qtbot, termin, monkeypatch):
    """Desktop-Prüfung 14.10.2026, Teil 3 Nr. 1: scheitert das Speichern an der Datei
    (schreibgeschützt, gesperrt), flog die Ausnahme aus closeEvent und das Fenster schloss
    ohne Nachfrage - die Ergebnisse waren verloren. Jetzt: eine Meldung, danach die
    vorhandene Nachfrage; bei "Nein" bleibt das Fenster offen."""
    conn, pfad = termin
    _teilnehmer_anlegen(conn, nachname="Zorn", startnummer=1, disziplin="Flächensuche")
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    tab = fenster.ergebnis_tab
    tab.punkte_eintragen(0, "Flächensuche", "58", "38")

    meldungen = []
    monkeypatch.setattr("desktop_ergebnis_speichern.eintragen_ergebnis", _schreibfehler)
    ueberall_ersetzen(monkeypatch, "_db_fehler_anzeigen", lambda parent, exc, *a: meldungen.append(str(exc)))
    rueckfragen_beantworten(monkeypatch, QMessageBox.No)

    fenster.close()

    assert fenster.isVisible()
    assert meldungen == ["attempt to write a readonly database"]
    assert tab.hat_ungespeicherte_aenderungen()
    assert not conn.in_transaction


def test_abmelden_bei_schreibfehler_bricht_ab_statt_zu_verwerfen(qtbot, termin, monkeypatch):
    """Desktop-Prüfung 14.10.2026, Teil 3 Nr. 1: Beim Windows-Abmelden flog die Ausnahme vor
    manager.cancel() heraus, das Abmelden lief weiter und die Ergebnisse waren verloren."""
    conn, pfad = termin
    _teilnehmer_anlegen(conn, nachname="Zorn", startnummer=1, disziplin="Flächensuche")
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.ergebnis_tab.punkte_eintragen(0, "Flächensuche", "58", "38")
    monkeypatch.setattr("desktop_ergebnis_speichern.eintragen_ergebnis", _schreibfehler)
    ueberall_ersetzen(monkeypatch, "_db_fehler_anzeigen", lambda *a, **k: None)
    # Für das Schließen beim Aufräumen des Tests: verwerfen statt modal zu warten.
    rueckfragen_beantworten(monkeypatch, QMessageBox.Yes)
    manager = _FakeSitzungsManager(interaktion=False)
    protokolliert = []
    monkeypatch.setattr("desktop_ergebnis_speichern.fehler_protokollieren", lambda exc: protokolliert.append(str(exc)))
    monkeypatch.setattr("desktop_ergebnis_speichern.meldung_protokollieren", lambda kopf, text: protokolliert.append(kopf))

    fenster._sitzungsende_pruefen(manager)

    assert manager.abgebrochen is True
    # OFFEN.md B5: ohne erlaubte Interaktion kein Fehlerfenster, der Grund steht im Protokoll.
    assert protokolliert == ["attempt to write a readonly database", "Speichern beim Sitzungsende"]


def test_sitzungsende_ohne_interaktion_zeigt_keine_eingabewarnung(qtbot, termin, monkeypatch):
    """OFFEN.md B5 (19.10.2026): Eine nicht speicherbare Eingabe beim Sitzungsende ohne
    erlaubte Interaktion öffnet keine Warnung; das Beenden wird abgelehnt, der Grund
    protokolliert."""
    conn, pfad = termin
    _teilnehmer_anlegen(conn, nachname="Zorn", startnummer=1, disziplin="Flächensuche")
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.ergebnis_tab.punkte_eintragen(0, "Flächensuche", "58", "")  # halb ausgefüllt

    def _kein_fenster(*a, **k):
        raise AssertionError("ohne erlaubte Interaktion darf kein Fenster erscheinen")

    monkeypatch.setattr("app.QMessageBox.warning", _kein_fenster)
    ueberall_ersetzen(monkeypatch, "_db_fehler_anzeigen", _kein_fenster)
    protokolliert = []
    monkeypatch.setattr("desktop_ergebnis_speichern.meldung_protokollieren", lambda kopf, text: protokolliert.append(text))
    manager = _FakeSitzungsManager(interaktion=False)

    fenster._sitzungsende_pruefen(manager)

    assert manager.abgebrochen is True
    # Nur Anzahl und Art, keine Namen: das Protokoll geht in die kopierbare Diagnose.
    assert len(protokolliert) == 1 and "1 Eingabe(n) nicht speicherbar" in protokolliert[0]
    assert "Zorn" not in protokolliert[0]
    # Feld wieder leeren, damit das Schließen beim Aufräumen nichts mehr zu melden hat.
    fenster.ergebnis_tab.punkte_eintragen(0, "Flächensuche", "", "")
    assert not fenster.ergebnis_tab.hat_ungespeicherte_aenderungen()


def test_neuer_termin_legt_datei_an_und_fragt_bei_vorhandener(qtbot, tmp_path, monkeypatch):
    from contextlib import closing

    monkeypatch.setattr("app.liste_termine", lambda: [])
    ueberall_ersetzen(monkeypatch, "termine_ordner", lambda: tmp_path)
    ziel = tmp_path / "termin.sqlite"

    def _exec(dialog):
        dialog.verein.setText("SGV")
        dialog.datum.setText("14.11.2026")
        dialog.verband.setText("HSVRM")
        dialog.meldestelle.setPlainText("x")
        dialog.pfad_feld.setText(str(ziel))
        dialog._pruefen_und_akzeptieren()
        return dialog.result()

    monkeypatch.setattr(VeranstaltungsDialog, "exec", _exec)
    fragen = rueckfragen_sammeln(monkeypatch, QMessageBox.Yes, merke="titel")

    start = StartDialog()
    qtbot.addWidget(start)
    start._neuer_termin()
    assert start.pfad == str(ziel)
    with closing(init_db(str(ziel))) as gelesen:
        assert get_veranstaltung(gelesen)["verein"] == "SGV"
    assert fragen == []

    zweiter = StartDialog()
    qtbot.addWidget(zweiter)
    zweiter._neuer_termin()
    assert fragen == ["Datei existiert bereits"]
    # Teil 2 Nr. 2: „Ja“ öffnet den vorhandenen Termin.
    assert zweiter.pfad == str(ziel) and zweiter.result() == QDialog.Accepted


def test_veranstaltung_bearbeiten_bleibt_bei_schreibfehler_offen(qtbot, conn, monkeypatch):
    set_veranstaltung(conn, verein="SGV", datum="2026-11-14", verband="HSVRM", meldestelle="x")
    meldungen = []
    monkeypatch.setattr("desktop_dialoge_basis._db_fehler_anzeigen", lambda parent, exc, *a: meldungen.append(str(exc)))
    ueberall_ersetzen(monkeypatch, "_aktualisiere_veranstaltung_feld", _schreibfehler)

    def _exec(dialog):
        dialog.verein.setText("Neuer Verein")
        dialog._pruefen_und_akzeptieren()
        return dialog.result()

    monkeypatch.setattr(VeranstaltungsDialog, "exec", _exec)
    tab = VerwaltungTab(conn)
    qtbot.addWidget(tab)
    tab._veranstaltung_bearbeiten()

    assert meldungen == ["attempt to write a readonly database"]
    assert get_veranstaltung(conn)["verein"] == "SGV"
    assert tab.status_label.text() != "Veranstaltungsdaten gespeichert."


def test_neuer_termin_speicherort_wird_geprueft(qtbot, tmp_path, monkeypatch):
    """Teil 2 Nr. 2: relativ, fehlende Endung, vorhandene Datei (eine Frage, bei „Nein“
    bleiben die Eingaben stehen), eindeutiger Vorschlag, Durchsuchen ohne Ersetzen-Frage."""
    (tmp_path / "2026-11-14_SGV-Koeppern.sqlite").write_bytes(b"")
    dialog = _neuer_termin_dialog(qtbot, tmp_path, monkeypatch)
    assert dialog.pfad_feld.text() == str(tmp_path / "2026-11-14_SGV-Koeppern (2).sqlite")
    warnungen = meldungen_sammeln(monkeypatch, "warning")
    fragen = rueckfragen_sammeln(monkeypatch, QMessageBox.No, merke="titel")

    dialog.pfad_feld.setText("termin.sqlite")
    dialog._pruefen_und_akzeptieren()
    assert "vollständigen Speicherort" in warnungen[-1] and dialog.result() == 0

    dialog.pfad_feld.setText(str(tmp_path) + os.sep)
    dialog._pruefen_und_akzeptieren()
    assert "Dateinamen" in warnungen[-1] and dialog.focusWidget() in (None, dialog.pfad_feld)

    dialog.pfad_feld.setText(str(tmp_path / "2026-11-14_SGV-Koeppern"))
    dialog._pruefen_und_akzeptieren()
    assert dialog.pfad_feld.text().endswith(".sqlite")
    assert fragen == ["Datei existiert bereits"] and dialog.result() == 0
    assert not dialog.bestehenden_oeffnen and dialog.verein.text() == "SGV Köppern"

    from PySide6.QtWidgets import QFileDialog

    optionen = []

    def speichern_dialog(*a, **k):
        optionen.append(k.get("options"))
        return str(tmp_path / "neu"), ""
    monkeypatch.setattr("desktop_dialoge_termin.QFileDialog.getSaveFileName", speichern_dialog)
    dialog._durchsuchen()
    assert dialog.pfad_feld.text() == str(tmp_path / "neu.sqlite")
    assert optionen == [QFileDialog.DontConfirmOverwrite]


def test_veranstaltungsdialog_zwischeneingabe_im_bereich(qtbot, monkeypatch):
    """Teil 2 Nr. 3: „20.“ ergibt eine deutsche Meldung mit Fokus auf dem Feld."""
    dialog = VeranstaltungsDialog(
        vorbelegung={"verein": "HSV", "datum": "2026-11-14", "angebotene_pruefungen": "DK1"}, bearbeiten=True)
    qtbot.addWidget(dialog)
    dialog.show()
    _beschriftung, von_feld, bis_feld = dialog.bereich_felder["DK1"]
    von_feld.setText("20.")
    bis_feld.setText("40")
    meldungen = meldungen_sammeln(monkeypatch, "warning")
    dialog._pruefen_und_akzeptieren()
    assert "„20.“ ist keine Startnummer (1–999)" in meldungen[0] and "invalid literal" not in meldungen[0]
    assert dialog.focusWidget() is von_feld and dialog.result() == 0


def test_veranstaltungsdialog_gebuehr_standard_nur_beim_anlegen(qtbot, tmp_path, monkeypatch):
    """Teil 2 Nr. 8a: ein geleertes Gebührfeld bleibt beim Bearbeiten leer."""
    bearbeiten = VeranstaltungsDialog(vorbelegung={"verein": "HSV", "datum": "2026-11-14",
                                                   "pruefungsgebuehr_ed": None, "pruefungsgebuehr_dk": "15,00"},
                                      bearbeiten=True)
    qtbot.addWidget(bearbeiten)
    assert bearbeiten.pruefungsgebuehr_ed.text() == "" and bearbeiten.pruefungsgebuehr_dk.text() == "15,00"
    neu = _neuer_termin_dialog(qtbot, tmp_path, monkeypatch)
    assert neu.pruefungsgebuehr_ed.text() == "12,00"


def test_aktualisiere_veranstaltung_feld_behaelt_alle_felder(conn):
    """Teil 2 Nr. 11: jede Spalte aus set_veranstaltung bleibt bei einer Einzeländerung erhalten."""
    import inspect

    import db

    felder = [n for n in inspect.signature(db.set_veranstaltung).parameters if n != "conn"]
    werte = {n: f"wert-{n}" for n in felder}
    werte.update(datum="2026-11-14", angebotene_pruefungen="DK1", startnummer_bereiche="DK1=1-20",
                 dk_mindestabstand="15", startnummer_bereichsgroesse="20", zeitplan_start="08:00")
    db.set_veranstaltung(conn, **werte)
    _aktualisiere_veranstaltung_feld(conn, zeitplan_start="10:00")
    gespeichert = get_veranstaltung(conn)
    assert gespeichert["zeitplan_start"] == "10:00"
    for name in felder:
        if name != "zeitplan_start":
            assert gespeichert[name] == werte[name], name


def test_neuer_termin_in_fehlendem_ordner_meldet_fehler_und_legt_nichts_an(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr("app.liste_termine", lambda: [])
    ueberall_ersetzen(monkeypatch, "termine_ordner", lambda: tmp_path)
    # Teil 2 Nr. 2: der fehlende Ordner fällt jetzt schon im Dialog auf.
    meldungen = meldungen_sammeln(monkeypatch, "warning")
    ziel = tmp_path / "fehlt" / "termin.sqlite"

    def _exec(dialog):
        dialog.verein.setText("SGV")
        dialog.datum.setText("14.11.2026")
        dialog.verband.setText("HSVRM")
        dialog.meldestelle.setPlainText("x")
        dialog.pfad_feld.setText(str(ziel))
        dialog._pruefen_und_akzeptieren()
        return dialog.result()

    monkeypatch.setattr(VeranstaltungsDialog, "exec", _exec)
    start = StartDialog()
    qtbot.addWidget(start)
    start._neuer_termin()

    assert meldungen
    assert start.result() != QDialog.Accepted
    assert not ziel.exists()


def test_mindestabstand_bei_schreibfehler_zeigt_gespeicherten_wert(qtbot, conn, monkeypatch):
    set_veranstaltung(conn, verein="SGV", datum="2026-11-14", dk_mindestabstand="20")
    tab = ZeitplanTab(conn)
    qtbot.addWidget(tab)
    ueberall_ersetzen(monkeypatch, "_aktualisiere_veranstaltung_feld", _schreibfehler)
    ueberall_ersetzen(monkeypatch, "_db_fehler_anzeigen", lambda *a, **k: None)

    tab.mindestabstand.setValue(35)

    assert tab.mindestabstand.value() == 20
    assert not tab.mindestabstand.keyboardTracking()


def test_schliessen_verwirft_bei_ja_trotz_uebrig_gebliebener_aenderungen(qtbot, termin, monkeypatch):
    """Gegenstück zum Test oben: wählt der Nutzer ausdrücklich "Ja" (trotzdem beenden),
    wird das respektiert und das Fenster schließt sich - die ungespeicherten Änderungen
    werden dann bewusst verworfen, statt das Beenden endlos zu verhindern."""
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()

    monkeypatch.setattr(type(fenster.ergebnis_tab), "hat_ungespeicherte_aenderungen", lambda self: True)
    monkeypatch.setattr(type(fenster.ergebnis_tab), "alle_speichern", lambda self: None)
    rueckfragen_beantworten(monkeypatch, QMessageBox.Yes)

    fenster.close()

    assert not fenster.isVisible()


def test_laufkennung_passt_zum_appmutex_im_installer():
    """Update-Test 05.10.2026: Das Setup erkennt das laufende Programm über AppMutex - der
    Name in installer.iss muss exakt LAUF_MUTEX_NAME aus desktop_programm.py sein."""
    import re

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "installer.iss"), encoding="utf-8") as datei:
        inhalt = datei.read()
    treffer = re.findall(r"^AppMutex=(.+)$", inhalt, re.MULTILINE)
    assert treffer == [",".join(desktop_programm.LAUF_MUTEX_NAMEN)]
    assert desktop_programm.LAUF_MUTEX_NAMEN[0] == desktop_programm.LAUF_MUTEX_NAME


@pytest.mark.skipif(sys.platform != "win32", reason="benannter Mutex nur unter Windows")
def test_laufkennung_setzen_legt_den_mutex_an(monkeypatch):
    import ctypes

    monkeypatch.setattr(desktop_programm, "_lauf_mutex", [])
    assert desktop_programm.laufkennung_setzen() is True
    assert desktop_programm.laufkennung_setzen() is True  # zweiter Aufruf legt keine neuen an
    assert len(desktop_programm._lauf_mutex) == 2  # lokal und global

    oeffnen = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p)(
        ("OpenMutexW", ctypes.windll.kernel32)
    )
    schliessen = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p)(("CloseHandle", ctypes.windll.kernel32))
    SYNCHRONIZE = 0x00100000
    try:
        for name in desktop_programm.LAUF_MUTEX_NAMEN:
            handle = oeffnen(SYNCHRONIZE, False, name)
            assert handle, f"Setup würde das laufende Programm über {name} nicht erkennen"
            schliessen(handle)
    finally:
        for handle in desktop_programm._lauf_mutex:
            schliessen(handle)


def test_sitzungsende_speichert_automatisch_und_erlaubt_beenden(qtbot, termin, monkeypatch):
    """H-4 (05.10.2026): Beim Beenden durch Windows/Setup ruft Qt 6 kein closeEvent auf,
    sondern commitDataRequest - auch dann muss automatisch gespeichert werden."""
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    zustand = {"ungespeichert": True, "gespeichert": False}
    monkeypatch.setattr(
        type(fenster.ergebnis_tab), "hat_ungespeicherte_aenderungen", lambda self: zustand["ungespeichert"]
    )

    def _speichern(self):
        zustand.update(gespeichert=True, ungespeichert=False)

    monkeypatch.setattr(type(fenster.ergebnis_tab), "alle_speichern", _speichern)
    manager = _FakeSitzungsManager(interaktion=True)

    fenster._sitzungsende_pruefen(manager)

    assert zustand["gespeichert"] is True
    assert manager.abgebrochen is False
    assert manager.freigegeben is True


def test_sitzungsende_mit_zusage_fragt_im_folgenden_closeevent_nicht_erneut(qtbot, termin, monkeypatch):
    """Zweite Verifikation 05.10.2026: Qt ruft nach der Zusage (WM_ENDSESSION -> quit())
    noch closeEvent auf. Ohne gemerkte Freigabe kämen Warnung und Rückfrage doppelt, und
    ein "Nein" würde das bereits zugesagte Beenden blockieren. Ein späteres Fenster-X nach
    Ablauf der Freigabe prüft wieder normal."""
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    monkeypatch.setattr(type(fenster.ergebnis_tab), "hat_ungespeicherte_aenderungen", lambda self: True)
    monkeypatch.setattr(type(fenster.ergebnis_tab), "alle_speichern", lambda self: None)
    antworten = [QMessageBox.Yes]

    def _frage(*a, **k):
        if not antworten:
            raise AssertionError("zweite Rückfrage nach bereits erteilter Zusage")
        return antworten.pop(0)

    monkeypatch.setattr("app.QMessageBox.question", _frage)
    manager = _FakeSitzungsManager(interaktion=True)

    fenster._sitzungsende_pruefen(manager)
    fenster.close()

    assert manager.abgebrochen is False
    assert not fenster.isVisible()

    # Die Freigabe gilt nur für dieses eine closeEvent: das nächste Fenster-X fragt wieder
    # (hier: "Nein" -> bleibt offen).
    fenster.show()
    antworten.append(QMessageBox.No)
    fenster.close()
    assert fenster.isVisible()
    assert fenster._beenden_freigegeben is False
    # Aufräumen: beim Teardown darf das Schließen nicht erneut blockieren.
    rueckfragen_beantworten(monkeypatch, QMessageBox.Yes)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-Nachrichten (WM_ENDSESSION)")
def test_abgebrochenes_abmelden_nimmt_die_freigabe_zurueck(qtbot, termin):
    """Dritte Verifikation 05.10.2026: Nach Zusage, aber abgebrochenem Abmelden
    (WM_ENDSESSION mit wParam=FALSE) darf ein späteres Fenster-X nicht ungeprüft schließen.
    Eingerichtet wie in main() (sitzungsende_einrichten) und mit echter Windows-Nachricht an
    das Fenster, damit auch ein Fehler beim Installieren des Filters auffällt."""
    import ctypes

    from desktop_programm import sitzungsende_einrichten

    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    qapp = QApplication.instance()
    if qapp.platformName() != "windows":
        pytest.skip("braucht die echte Windows-Plattform (nicht offscreen)")
    # Eigener Prototyp statt user32.SendMessageW.argtypes zu setzen - das gälte sonst für
    # den ganzen Testlauf.
    senden = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t)(
        ("SendMessageW", ctypes.windll.user32)
    )
    try:
        sitzungsende_einrichten(qapp, fenster)
        fenster.show()
        fenster._beenden_freigegeben = True
        senden(int(fenster.winId()), 0x0016, 0, 0x00000001)  # WM_ENDSESSION, wParam=FALSE, ENDSESSION_CLOSEAPP
        assert fenster._beenden_freigegeben is False
    finally:
        # Abräumen auch dann, wenn die Einrichtung mittendrin gescheitert ist.
        try:
            qapp.commitDataRequest.disconnect(fenster._sitzungsende_pruefen)
        except (RuntimeError, TypeError):
            pass
        filter_ = getattr(fenster, "_sitzungsende_filter", None)
        if filter_ is not None:
            qapp.removeNativeEventFilter(filter_)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-Nachrichten (WM_ENDSESSION)")
def test_sitzungsende_filter_ignoriert_echtes_beenden_und_unsinnige_nachrichten(qtbot, termin):
    """WM_ENDSESSION mit wParam=TRUE lässt die Freigabe stehen; ein Null-Zeiger oder ein
    fremder Ereignistyp darf keinen Fehler auslösen."""
    import ctypes
    import ctypes.wintypes

    from desktop_programm import SitzungsendeFilter

    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    filter_ = SitzungsendeFilter(fenster)
    msg = ctypes.wintypes.MSG()
    msg.message = 0x0016
    msg.wParam = 1
    fenster._beenden_freigegeben = True

    assert filter_.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg)) == (False, 0)
    assert filter_.nativeEventFilter(b"windows_generic_MSG", 0) == (False, 0)
    assert filter_.nativeEventFilter(b"xcb_generic_event_t", ctypes.addressof(msg)) == (False, 0)
    assert fenster._beenden_freigegeben is True


def test_sitzungsende_bricht_bei_resten_und_nein_ab(qtbot, termin, monkeypatch):
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    monkeypatch.setattr(type(fenster.ergebnis_tab), "hat_ungespeicherte_aenderungen", lambda self: True)
    monkeypatch.setattr(type(fenster.ergebnis_tab), "alle_speichern", lambda self: None)
    rueckfragen_beantworten(monkeypatch, QMessageBox.No)
    manager = _FakeSitzungsManager(interaktion=True)

    fenster._sitzungsende_pruefen(manager)

    assert manager.abgebrochen is True
    assert manager.freigegeben is True


def test_sitzungsende_ohne_rueckfrage_bricht_bei_resten_ohne_dialog_ab(qtbot, termin, monkeypatch):
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    monkeypatch.setattr(type(fenster.ergebnis_tab), "hat_ungespeicherte_aenderungen", lambda self: True)
    monkeypatch.setattr(type(fenster.ergebnis_tab), "alle_speichern", lambda self, meldungen=True: None)

    def _keine_rueckfrage(*a, **k):
        raise AssertionError("ohne erlaubte Interaktion darf keine Rückfrage erscheinen")

    monkeypatch.setattr("app.QMessageBox.question", _keine_rueckfrage)
    manager = _FakeSitzungsManager(interaktion=False)

    fenster._sitzungsende_pruefen(manager)

    assert manager.abgebrochen is True
    assert manager.freigegeben is False


def test_neuer_termin_schlaegt_verein_vereinsnr_ort_des_letzten_termins_vor(qtbot, monkeypatch, tmp_path):
    ueberall_ersetzen(monkeypatch, "termine_ordner", lambda: tmp_path)  # Teil 2 Nr. 15
    # Nutzerwunsch (20.09., Anmerkung "Anlage neuer Termin nachdem bereits Anlagen
    # erfolgt sind"): das Programm soll sich merken, welcher Verein gemeint ist, damit
    # die oberen 3 Eingaben (Verein/Vereins-Nr./Ort) beim Anlegen eines weiteren Termins
    # nicht erneut eingetippt werden müssen. Vorbelegung aus dem in der Terminübersicht
    # obersten (nach Datum neuesten) Termin - das Datum selbst wird bewusst NICHT
    # übernommen, da jeder Termin ein eigenes hat.
    letzter = TerminInfo(
        pfad="egal.sqlite", dateiname="egal.sqlite", verein="SGV Köppern e.V.",
        vereins_nr="123", ort="Köppern", datum="2026-09-19", anzahl_teilnehmer=5, lesbar=True,
        verband="HSVRM", startnummer_bereichsgroesse="25",
    )
    monkeypatch.setattr("app.liste_termine", lambda: [letzter])

    aufgezeichnete_vorbelegung = {}
    monkeypatch.setattr("app.VeranstaltungsDialog", _vorbelegung_aufzeichnen(aufgezeichnete_vorbelegung))

    dialog = StartDialog()
    qtbot.addWidget(dialog)
    dialog._neuer_termin()

    assert aufgezeichnete_vorbelegung == {
        "verein": "SGV Köppern e.V.",
        "vereins_nr": "123",
        "ort": "Köppern",
        # Marco, 28.09.2026: Verband wird übernommen, Meldestelle bewusst nicht.
        "verband": "HSVRM",
        # UX-Test U1: Startnummern-Bereiche werden ebenfalls übernommen (hier keine hinterlegt).
        "startnummer_bereiche": None,
        # Marco 09.10.2026: ebenso die Standardgröße der Bereiche.
        "startnummer_bereichsgroesse": "25",
        # Marco 09.11.2026: die Sätze der Leistungsrichter-Abrechnung ebenso (hier keine hinterlegt).
        "lr_km_satz": None,
        "lr_tagespauschale": None,
        "checkliste_eigene": None,
    }


def test_neuer_termin_ohne_bestehende_termine_zeigt_leere_vorbelegung(qtbot, monkeypatch, tmp_path):
    ueberall_ersetzen(monkeypatch, "termine_ordner", lambda: tmp_path)  # Teil 2 Nr. 15
    # Gegenprobe: ohne bereits vorhandene Termine (z. B. allererster Start) darf nichts
    # vorbelegt werden.
    monkeypatch.setattr("app.liste_termine", lambda: [])

    aufgezeichnete_vorbelegung = {"noch_nicht_aufgerufen": True}
    monkeypatch.setattr("app.VeranstaltungsDialog", _vorbelegung_aufzeichnen(aufgezeichnete_vorbelegung))

    dialog = StartDialog()
    qtbot.addWidget(dialog)
    dialog._neuer_termin()

    assert aufgezeichnete_vorbelegung == {}


def test_bestehender_teilnehmer_ohne_startnummer_zeigt_checkbox_aktiviert(qtbot, conn):
    _teilnehmer_anlegen(conn, startnummer=None)
    vorhandener = list_teilnehmer(conn)[0]
    dialog = TeilnehmerDialog(vorhandener=vorhandener, vergebene_nummern=set())
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.startnummer_unbekannt.isChecked()
    assert not dialog.startnummer.isEnabled()


def test_veranstaltungsdialog_datum_deutsch_anzeigen_und_iso_liefern(qtbot, monkeypatch):
    dialog = VeranstaltungsDialog(vorbelegung={"verein": "SGV", "datum": "2026-09-27"}, bearbeiten=True)
    qtbot.addWidget(dialog)
    assert dialog.datum.text() == "27.09.2026"

    dialog.datum.setText("3.10.2026")
    warnungen = []
    monkeypatch.setattr("app.QMessageBox.warning", lambda self, titel, text: warnungen.append(text))
    dialog._pruefen_und_akzeptieren()
    assert warnungen == []
    assert dialog.datum_iso() == "2026-10-03"

    # Altbestand in TT.MM.JJJJ: wird angezeigt und beim Speichern in ISO umgewandelt.
    altbestand = VeranstaltungsDialog(vorbelegung={"verein": "SGV", "datum": "27.09.2026"}, bearbeiten=True)
    qtbot.addWidget(altbestand)
    assert altbestand.datum.text() == "27.09.2026"
    assert altbestand.datum_iso() == "2026-09-27"

    dialog.datum.setText("2026/10/03")
    dialog.setResult(0)
    dialog._pruefen_und_akzeptieren()
    assert len(warnungen) == 1
    assert dialog.result() == 0


# --- Teilnehmer aus anderem Termin importieren (20.09.) ----------------------------
# Nutzerwunsch (Anmerkung zum Programm): "Teilnehmer müssen wieder einzeln eingegeben
# werden. → ist Option möglich, von anderem Termin importieren?" Geklärt: Auswahl per
# Checkbox-Liste, es werden nur Stammdaten übernommen (Startnummer/Gegenstände/Bezahlt-
# Status/Ergebnis bleiben zurückgesetzt), keine Dubletten-Prüfung.


def test_termin_import_dialog_listet_teilnehmer_und_importiert_auswahl(qtbot, tmp_path, monkeypatch):
    quelle_pfad = str(tmp_path / "quelle.sqlite")
    quelle_conn = init_db(quelle_pfad)
    add_teilnehmer(quelle_conn, NeuerTeilnehmer(
        nachname="Eins", vorname="A", rufname_hund="Hund1", art="ED", stufe=1, disziplin="Trümmerfeld"))
    add_teilnehmer(quelle_conn, NeuerTeilnehmer(
        nachname="Zwei", vorname="B", rufname_hund="Hund2", art="ED", stufe=1, disziplin="Flächensuche"))
    quelle_conn.close()

    termin_info = TerminInfo(
        pfad=quelle_pfad, dateiname="quelle.sqlite", verein="Testverein", vereins_nr=None,
        ort="Testort", datum="2026-01-01", anzahl_teilnehmer=2, lesbar=True,
    )
    monkeypatch.setattr("desktop_dialoge_termin.liste_termine", lambda: [termin_info])

    dialog = TerminImportDialog(None, aktueller_pfad=None)
    qtbot.addWidget(dialog)
    dialog.show()

    # Standardmäßig alle ausgewählt.
    assert dialog.teilnehmer_liste.count() == 2
    assert len(dialog.ausgewaehlte_ids()) == 2

    dialog.teilnehmer_liste.item(0).setCheckState(Qt.Unchecked)
    assert len(dialog.ausgewaehlte_ids()) == 1

    dialog.schliesse_quelle()


def test_termin_import_dialog_vermerkt_nicht_erschienene(qtbot, tmp_path, monkeypatch):
    """Offener Punkt 18.10.2026: Vermerk für „keine Teilnahme“ in der Quelle, weiter vorausgewählt."""
    quelle_pfad = str(tmp_path / "quelle.sqlite")
    quelle_conn = init_db(quelle_pfad)
    weg_id = add_teilnehmer(quelle_conn, NeuerTeilnehmer(
        nachname="Weg", vorname="A", rufname_hund="Hund1", art="ED", stufe=1, disziplin="Trümmerfeld"))
    add_teilnehmer(quelle_conn, NeuerTeilnehmer(
        nachname="Da", vorname="B", rufname_hund="Hund2", art="ED", stufe=1, disziplin="Flächensuche"))
    setze_keine_teilnahme(quelle_conn, weg_id, True)
    quelle_conn.close()
    termin_info = TerminInfo(
        pfad=quelle_pfad, dateiname="quelle.sqlite", verein="Testverein", vereins_nr=None,
        ort="Testort", datum="2026-01-01", anzahl_teilnehmer=2, lesbar=True,
    )
    monkeypatch.setattr("desktop_dialoge_termin.liste_termine", lambda: [termin_info])

    dialog = TerminImportDialog(None, aktueller_pfad=None)
    qtbot.addWidget(dialog)

    texte = [dialog.teilnehmer_liste.item(i).text() for i in range(dialog.teilnehmer_liste.count())]
    (weg,) = [tx for tx in texte if tx.startswith("Weg, A")]
    (da,) = [tx for tx in texte if tx.startswith("Da, B")]
    assert weg.endswith(" – im Quelltermin nicht erschienen")
    assert "nicht erschienen" not in da
    assert len(dialog.ausgewaehlte_ids()) == 2
    dialog.schliesse_quelle()


def test_termin_import_dialog_alte_quelle_ohne_keine_teilnahme(qtbot, tmp_path, monkeypatch):
    """Sehr alte Quelldateien haben die Spalte keine_teilnahme nicht - kein Vermerk, kein Fehler."""
    quelle_pfad = str(tmp_path / "quelle.sqlite")
    init_db(quelle_pfad).close()
    termin_info = TerminInfo(
        pfad=quelle_pfad, dateiname="quelle.sqlite", verein="Testverein", vereins_nr=None,
        ort="Testort", datum="2026-01-01", anzahl_teilnehmer=1, lesbar=True,
    )
    monkeypatch.setattr("desktop_dialoge_termin.liste_termine", lambda: [termin_info])
    alt = {"id": 1, "nachname": "Alt", "vorname": "A", "rufname_hund": "Rex",
           "art": "ED", "stufe": 1, "disziplin": "Trümmerfeld"}
    monkeypatch.setattr("desktop_dialoge_termin.list_teilnehmer", lambda conn: [alt])

    dialog = TerminImportDialog(None, aktueller_pfad=None)
    qtbot.addWidget(dialog)

    assert dialog.teilnehmer_liste.count() == 1
    assert dialog.teilnehmer_liste.item(0).text().startswith("Alt, A – Rex")
    assert "nicht erschienen" not in dialog.teilnehmer_liste.item(0).text()
    assert dialog.ausgewaehlte_ids() == [1]
    dialog.schliesse_quelle()


def test_termin_import_dialog_fehlende_spalte_erklaert(qtbot, tmp_path, monkeypatch):
    """Offener Punkt 18.10.2026: bei fehlender Spalte nicht nur „'nachname'“ anzeigen."""
    quelle_pfad = str(tmp_path / "quelle.sqlite")
    init_db(quelle_pfad).close()
    termin_info = TerminInfo(
        pfad=quelle_pfad, dateiname="quelle.sqlite", verein="Testverein", vereins_nr=None,
        ort="Testort", datum="2026-01-01", anzahl_teilnehmer=1, lesbar=True,
    )
    monkeypatch.setattr("desktop_dialoge_termin.liste_termine", lambda: [termin_info])
    monkeypatch.setattr("desktop_dialoge_termin.list_teilnehmer", lambda conn: [{"id": 1}])

    dialog = TerminImportDialog(None, aktueller_pfad=None)
    qtbot.addWidget(dialog)

    text = dialog.teilnehmer_liste.item(0).text()
    assert "nicht alle erwarteten Angaben" in text
    assert "KeyError: 'nachname'" in text
    assert not dialog.buttons.button(QDialogButtonBox.Ok).isEnabled()


def test_termin_import_dialog_eigener_termin_wird_ausgeschlossen(qtbot, monkeypatch):
    eigener = TerminInfo(
        pfad="eigen.sqlite", dateiname="eigen.sqlite", verein="Eigen", vereins_nr=None,
        ort="X", datum="2026-01-01", anzahl_teilnehmer=1, lesbar=True,
    )
    anderer = TerminInfo(
        pfad="anderer.sqlite", dateiname="anderer.sqlite", verein="Anderer", vereins_nr=None,
        ort="Y", datum="2026-01-02", anzahl_teilnehmer=1, lesbar=True,
    )
    monkeypatch.setattr("desktop_dialoge_termin.liste_termine", lambda: [eigener, anderer])

    dialog = TerminImportDialog(None, aktueller_pfad="eigen.sqlite")
    qtbot.addWidget(dialog)

    assert dialog.termin_combo.count() == 1
    assert "Anderer" in dialog.termin_combo.itemText(0)


def test_termin_import_dialog_schliesst_eigenen_termin_bei_anderer_schreibweise_aus(qtbot, monkeypatch, tmp_path):
    """Desktop-Prüfung 14.10.2026, Teil 1 Nr. 1: Qt liefert "/", liste_termine() "\\" - der
    eigene Termin erschien vorausgewählt im Dialog."""
    import db

    eigen = tmp_path / "eigen.sqlite"
    _termin_mit_teilnehmer(tmp_path / "alt.sqlite", "Alt", "2026-01-01", "Alt")
    _termin_mit_teilnehmer(eigen, "Eigen", "2026-12-01", "Eigen")
    monkeypatch.setattr("desktop_dialoge_termin.liste_termine", lambda: db.liste_termine(tmp_path))
    aktueller_pfad = str(eigen).replace("\\", "/")
    if os.name == "nt":
        aktueller_pfad = aktueller_pfad.upper()

    dialog = TerminImportDialog(None, aktueller_pfad=aktueller_pfad)
    qtbot.addWidget(dialog)

    assert dialog.termin_combo.count() == 1
    assert "Alt" in dialog.termin_combo.itemText(0)
    dialog.schliesse_quelle()


def test_termin_import_dialog_liest_schreibgeschuetzte_altdatei(qtbot, monkeypatch, tmp_path):
    """Desktop-Prüfung 14.10.2026, Teil 1 Nr. 2: die Quelle wird nur gelesen - auch eine
    schreibgeschützte Datei einer älteren Version, die init_db migrieren müsste, lässt sich
    verwenden, und die Datei bleibt unverändert."""
    import shutil
    import stat
    from pathlib import Path

    import db

    altdaten = sorted((Path(__file__).resolve().parent / "testdaten" / "altversionen").glob("*/termin.sqlite"))
    if not altdaten:
        pytest.skip("testdaten/altversionen fehlt")
    quelle = tmp_path / "alt.sqlite"
    shutil.copy(altdaten[0], quelle)
    inhalt = quelle.read_bytes()
    os.chmod(quelle, stat.S_IREAD)
    try:
        monkeypatch.setattr("desktop_dialoge_termin.liste_termine", lambda: db.liste_termine(tmp_path))
        dialog = TerminImportDialog(None, aktueller_pfad=None)
        qtbot.addWidget(dialog)
        assert dialog.termin_combo.count() == 1
        assert dialog.teilnehmer_liste.count() > 0
        assert dialog.ausgewaehlte_ids()
        assert dialog.buttons.button(QDialogButtonBox.Ok).isEnabled()
        dialog.schliesse_quelle()
    finally:
        os.chmod(quelle, stat.S_IREAD | stat.S_IWRITE)
    assert quelle.read_bytes() == inhalt


def test_termin_import_dialog_meldet_nicht_lesbare_quelle(qtbot, monkeypatch, tmp_path):
    """Kann die gewählte Quelle nicht gelesen werden, erscheint ein Hinweis in der Liste und
    OK ist gesperrt - statt eines allgemeinen Fehlerfensters."""
    weg = TerminInfo(
        pfad=str(tmp_path / "weg.sqlite"), dateiname="weg.sqlite", verein="Weg", vereins_nr=None,
        ort="Y", datum="2026-01-02", anzahl_teilnehmer=1, lesbar=True,
    )
    monkeypatch.setattr("desktop_dialoge_termin.liste_termine", lambda: [weg])

    dialog = TerminImportDialog(None, aktueller_pfad=None)
    qtbot.addWidget(dialog)

    assert dialog.teilnehmer_liste.count() == 1
    assert "nicht gelesen" in dialog.teilnehmer_liste.item(0).text()
    assert dialog.ausgewaehlte_ids() == []
    assert not dialog.buttons.button(QDialogButtonBox.Ok).isEnabled()
    assert dialog.quelle_conn() is None
    assert not (tmp_path / "weg.sqlite").exists()


def test_termin_import_dialog_prueft_quelle_mit_quick_check(qtbot, monkeypatch, tmp_path):
    """Offene Punkte O2 (Marco 18.10.2026): eine beschädigte Seite außerhalb der gelesenen
    Teilnehmer macht die Quelle im Import nicht lesbar."""
    import sqlite3
    pfad = tmp_path / "quelle.sqlite"
    with closing(init_db(str(pfad))) as c:
        set_veranstaltung(c, verein="Quelle", datum="2026-11-14")
        _teilnehmer_anlegen(c, nachname="Q")
        c.execute("CREATE TABLE notiz (text TEXT)")
        c.executemany("INSERT INTO notiz VALUES (?)", [("x" * 200,)] * 50)
        c.commit()
    _seite_beschaedigen(pfad, "notiz")
    with closing(sqlite3.connect(pfad)) as c:
        assert c.execute("SELECT COUNT(*) FROM teilnehmer").fetchone()[0] == 1
    info = TerminInfo(pfad=str(pfad), dateiname=pfad.name, verein="Quelle", vereins_nr=None,
                      ort=None, datum="2026-11-14", anzahl_teilnehmer=1, lesbar=True)
    monkeypatch.setattr("desktop_dialoge_termin.liste_termine", lambda: [info])

    dialog = TerminImportDialog(None, aktueller_pfad=None)
    qtbot.addWidget(dialog)

    assert dialog.teilnehmer_liste.count() == 1
    assert "beschädigt" in dialog.teilnehmer_liste.item(0).text()
    assert not dialog.buttons.button(QDialogButtonBox.Ok).isEnabled()
    assert dialog.quelle_conn() is None


def test_termin_import_dialog_nennt_schrittgrenze(qtbot, monkeypatch, tmp_path):
    """Offene Punkte O2: scheitert das Lesen der Quelle an der Schrittgrenze, heißt es
    „zu aufwendig“ statt eines technischen Abbruchs."""
    import db
    pfad = tmp_path / "quelle.sqlite"
    with closing(init_db(str(pfad))) as c:
        set_veranstaltung(c, verein="Quelle", datum="2026-11-14")
        _teilnehmer_anlegen(c, nachname="Q")
    info = TerminInfo(pfad=str(pfad), dateiname=pfad.name, verein="Quelle", vereins_nr=None,
                      ort=None, datum="2026-11-14", anzahl_teilnehmer=1, lesbar=True)
    monkeypatch.setattr("desktop_dialoge_termin.liste_termine", lambda: [info])
    monkeypatch.setattr("db_termine._LESE_SCHRITTWEITE", 1)
    monkeypatch.setattr("db_termine._LESE_HOECHSTSCHRITTE", 0)

    dialog = TerminImportDialog(None, aktueller_pfad=None)
    qtbot.addWidget(dialog)

    assert db.SCHRITTGRENZE_TEXT in dialog.teilnehmer_liste.item(0).text()
    assert not dialog.buttons.button(QDialogButtonBox.Ok).isEnabled()


@pytest.mark.parametrize("antwort", [QMessageBox.No, QMessageBox.Yes])
def test_ungewoehnlich_grosser_termin_fragt_vor_dem_oeffnen(qtbot, monkeypatch, tmp_path, antwort):
    """Offene Punkte O2 (Marco 18.10.2026): Rückfrage „ungewöhnlich groß, trotzdem öffnen?“;
    Nein bricht ohne weitere Meldung ab, Ja öffnet."""
    import app
    pfad = tmp_path / "gross.sqlite"
    with closing(init_db(str(pfad))) as c:
        set_veranstaltung(c, verein="Groß", datum="2026-11-14")
    monkeypatch.setattr("db_termine.TERMIN_GROESSE_GRENZE", 100)
    fragen = rueckfragen_sammeln(monkeypatch, antwort)
    monkeypatch.setattr("app.QMessageBox.warning", lambda *a, **_k: pytest.fail(f"Meldung: {a}"))

    conn = app._termin_oeffnen_mit_meldung(None, str(pfad))

    assert len(fragen) == 1
    assert "ungewöhnlich groß" in fragen[0]
    assert "Trotzdem öffnen?" in fragen[0]
    if antwort == QMessageBox.Yes:
        assert conn is not None
        conn.close()
    else:
        assert conn is None


def test_startdialog_zeigt_grund_und_oeffnet_zu_grosse_datei(qtbot, monkeypatch, tmp_path):
    """Offene Punkte O2: die Terminübersicht nennt den Grund; eine nur zu große Datei lässt
    sich trotzdem wählen (die Rückfrage folgt beim Öffnen), eine zu aufwendige nicht."""
    import db
    ueberall_ersetzen(monkeypatch, "termine_ordner", lambda: tmp_path)

    def info(name, grund):
        return TerminInfo(pfad=str(tmp_path / name), dateiname=name, verein=None, vereins_nr=None,
                          ort=None, datum=None, anzahl_teilnehmer=0, lesbar=False, grund=grund)

    monkeypatch.setattr("app.liste_termine", lambda: [info("gross.sqlite", db.GRUND_ZU_GROSS),
                                                      info("aufwendig.sqlite", db.GRUND_ZU_AUFWENDIG)])
    warnungen = meldungen_sammeln(monkeypatch, "warning")
    dialog = StartDialog()
    qtbot.addWidget(dialog)
    texte = [dialog.tabelle.item(z, 1).text() for z in range(dialog.tabelle.rowCount())]
    assert "gross.sqlite (ungewöhnlich groß)" in texte
    assert "aufwendig.sqlite (nicht lesbar: zu aufwendig zu prüfen)" in texte

    dialog.tabelle.selectRow(texte.index("aufwendig.sqlite (nicht lesbar: zu aufwendig zu prüfen)"))
    dialog._termin_oeffnen()
    assert dialog.result() != QDialog.Accepted
    assert len(warnungen) == 1 and "zu aufwendig zu prüfen" in warnungen[0]

    dialog.tabelle.selectRow(texte.index("gross.sqlite (ungewöhnlich groß)"))
    dialog._termin_oeffnen()
    assert dialog.result() == QDialog.Accepted
    assert dialog.pfad == str(tmp_path / "gross.sqlite")
    assert len(warnungen) == 1


def test_termin_import_dialog_prueft_wie_termin_oeffnen(qtbot, monkeypatch, tmp_path):
    """Abschluss-QS 15.10.2026 (A19c): Der Import-Dialog nutzt db.termin_lesend_pruefen -
    berechnete Spalten in einer Nebentabelle machen die Quelle nicht lesbar. Ein
    liegengebliebenes Journal wird nicht zurückgespielt (Marcos Entscheidung 15.10.2026):
    die Quelle gilt als nicht lesbar und bleibt unverändert."""
    import sqlite3
    import subprocess
    import sys

    def quelle(name):
        pfad = tmp_path / name
        with closing(init_db(str(pfad))) as c:
            set_veranstaltung(c, verein="Quelle", datum="2026-11-14")
            _teilnehmer_anlegen(c, nachname="Q")
        return pfad

    def dialog_fuer(pfad):
        info = TerminInfo(pfad=str(pfad), dateiname=pfad.name, verein="Quelle", vereins_nr=None,
                          ort=None, datum="2026-11-14", anzahl_teilnehmer=1, lesbar=True)
        monkeypatch.setattr("desktop_dialoge_termin.liste_termine", lambda: [info])
        dialog = TerminImportDialog(None, aktueller_pfad=None)
        qtbot.addWidget(dialog)
        return dialog

    gut = quelle("gut.sqlite")
    dialog = dialog_fuer(gut)
    assert dialog.ausgewaehlte_ids() and dialog.buttons.button(QDialogButtonBox.Ok).isEnabled()
    dialog.schliesse_quelle()

    neben = quelle("neben.sqlite")
    with closing(sqlite3.connect(str(neben))) as c:
        c.execute("CREATE TABLE extra (a, b TEXT GENERATED ALWAYS AS (upper(a)) VIRTUAL)")
        c.commit()
    dialog = dialog_fuer(neben)
    assert "nicht gelesen" in dialog.teilnehmer_liste.item(0).text()
    assert not dialog.buttons.button(QDialogButtonBox.Ok).isEnabled()
    assert dialog.quelle_conn() is None

    # Absturz mitten im Speichern, die Datei ist schon halb beschrieben (kleiner Cache). Ist
    # sie noch unverändert, liest SQLite lesend den alten Stand - auch ohne zu schreiben.
    journal = quelle("journal.sqlite")
    skript = (
        "import os, sqlite3, sys; c = sqlite3.connect(sys.argv[1]); "
        "c.execute(\"PRAGMA journal_mode=DELETE\"); c.execute(\"PRAGMA cache_size=2\"); c.execute('BEGIN'); "
        "c.execute(\"UPDATE veranstaltung SET verein = 'halb'\"); "
        "c.execute(\"INSERT INTO teilnehmer (nachname, vorname, rufname_hund, art, stufe) "
        "SELECT 'x', 'y', 'z', 'DK', 1 FROM (WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM n "
        "WHERE i < 3000) SELECT i FROM n)\"); os._exit(0)"
    )
    subprocess.run([sys.executable, "-c", skript, str(journal)], check=False)
    if not os.path.exists(f"{journal}-journal"):
        pytest.skip("kein Journal entstanden (Cache groß genug)")
    inhalt = journal.read_bytes()
    dialog = dialog_fuer(journal)
    assert "nicht gelesen" in dialog.teilnehmer_liste.item(0).text()
    assert not dialog.buttons.button(QDialogButtonBox.Ok).isEnabled()
    assert os.path.exists(f"{journal}-journal") and journal.read_bytes() == inhalt


def test_termin_import_dialog_ohne_anderen_termin_deaktiviert_ok(qtbot, monkeypatch):
    monkeypatch.setattr("desktop_dialoge_termin.liste_termine", lambda: [])

    dialog = TerminImportDialog(None, aktueller_pfad=None)
    qtbot.addWidget(dialog)

    assert not dialog.buttons.button(QDialogButtonBox.Ok).isEnabled()


def test_terminwechsel_zu_kaputter_datei_behaelt_den_termin(qtbot, termin, monkeypatch, tmp_path):
    """Desktop-Prüfung 14.10.2026, Teil 7 Nr. 4: eine nicht öffenbare Datei ergibt eine
    Meldung, der bisherige Termin bleibt samt Reitern verbunden."""
    conn, pfad = termin
    set_veranstaltung(conn, verein="Alt", datum="2026-11-14")
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    kaputt = tmp_path / "kaputt.sqlite"
    kaputt.write_bytes(b"keine Datenbank" * 20)
    monkeypatch.setattr(_StartDialogMitPfad, "pfad_vorgabe", str(kaputt))
    monkeypatch.setattr("app.StartDialog", _StartDialogMitPfad)
    meldungen = meldungen_sammeln(monkeypatch, "warning", merke="titel")

    fenster._termin_wechseln()

    assert meldungen == ["Termin lässt sich nicht öffnen"]
    assert fenster.conn is conn and fenster.pfad == pfad
    assert fenster._tabs.count() == 10
    assert "Alt" in fenster.windowTitle()


def test_terminwechsel_bei_fehler_im_reiteraufbau_bleibt_alles_wie_es_war(qtbot, termin, monkeypatch, tmp_path):
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    alter_reiter = fenster.ergebnis_tab
    ziel = tmp_path / "neu.sqlite"
    with closing(init_db(str(ziel))) as neu:
        set_veranstaltung(neu, verein="Neu", datum="2026-12-01")
    monkeypatch.setattr(_StartDialogMitPfad, "pfad_vorgabe", str(ziel))
    monkeypatch.setattr("app.StartDialog", _StartDialogMitPfad)
    meldungen_stumm(monkeypatch, "warning")

    def kaputt(*_a, **_k):
        raise KeyError("XX")

    monkeypatch.setattr("app.TeilnehmerUebersichtTab", kaputt)
    fenster._termin_wechseln()

    assert fenster.conn is conn
    assert fenster.ergebnis_tab is alter_reiter
    assert not fenster._tabs.signalsBlocked()
    conn.execute("SELECT 1")  # alte Verbindung noch offen


def test_terminwechsel_loescht_alte_reiter_und_setzt_titel(qtbot, termin, monkeypatch, tmp_path):
    """Teil 7 Nr. 9 und Teil 8 Nr. 3: alte Reiter bleiben nicht liegen; ohne Verein steht
    der Dateiname im Titel statt „None“."""
    from PySide6.QtCore import QCoreApplication, QEvent

    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    ziel = tmp_path / "ohne_verein.sqlite"
    init_db(str(ziel)).close()
    monkeypatch.setattr(_StartDialogMitPfad, "pfad_vorgabe", str(ziel))
    monkeypatch.setattr("app.StartDialog", _StartDialogMitPfad)
    for _ in range(3):
        fenster._termin_wechseln()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    assert len(fenster.findChildren(ErgebnisTab)) == 1
    assert "None" not in fenster.windowTitle()
    assert "ohne_verein.sqlite" in fenster.windowTitle()


def test_titel_nach_veranstaltung_bearbeiten(qtbot, termin, monkeypatch):
    """Teil 2 Nr. 5."""
    conn, pfad = termin
    set_veranstaltung(conn, verein="Alt", datum="2026-11-14", verband="V", meldestelle="M")
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)

    def _exec(dialog):
        dialog.verein.setText("Neuer Verein")
        dialog._pruefen_und_akzeptieren()
        return dialog.result()

    monkeypatch.setattr(VeranstaltungsDialog, "exec", _exec)
    fenster.verwaltung_tab._veranstaltung_bearbeiten()
    assert "Neuer Verein" in fenster.windowTitle()


def test_terminwechsel_abbrechen_bleibt_im_termin(qtbot, termin, monkeypatch):
    """Desktop-Prüfung 14.10.2026, Teil 8 Nr. 2: Esc bzw. "Abbrechen" (QMessageBox.Cancel)
    bricht den Terminwechsel ab, statt wie früher als "Nein" zu verwerfen."""
    fenster, fragen = _terminwechsel_vorbereiten(
        qtbot, termin, monkeypatch, [QMessageBox.Cancel], speichern_gelingt=True
    )

    fenster._termin_wechseln()

    assert fragen == ["Ungespeicherte Ergebnisse"]
    assert _StartDialogAttrappe.termin_geoeffnet == 0


def test_terminwechsel_rueckfrage_bietet_speichern_verwerfen_abbrechen(qtbot, termin, monkeypatch):
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    aufrufe = rueckfragen_sammeln(monkeypatch, QMessageBox.Cancel, merke="args")

    assert fenster._rueckfrage_ungespeichert(verwerfen=True) == "abbrechen"
    assert fenster._rueckfrage_ungespeichert(verwerfen=False) == "abbrechen"
    (_p, _titel, text_termin, knoepfe_termin, vorgabe), (_p2, _t2, text_reiter, knoepfe_reiter, _v2) = aufrufe
    assert knoepfe_termin == QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
    assert vorgabe == QMessageBox.Save
    assert "gehen dann verloren" in text_termin
    assert knoepfe_reiter == QMessageBox.Save | QMessageBox.No | QMessageBox.Cancel
    assert "ungespeichert in der Tabelle stehen" in text_reiter


def test_schliessen_nach_freigabe_speichert_neue_eingaben_still(qtbot, termin, monkeypatch):
    """Desktop-Prüfung 14.10.2026, Teil 8 Nr. 10 (Linux/X11)."""
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    zustand = {"ungespeichert": True, "gespeichert": 0}
    monkeypatch.setattr(type(fenster.ergebnis_tab), "hat_ungespeicherte_aenderungen",
                        lambda self: zustand["ungespeichert"])

    def _speichern(self):
        zustand["gespeichert"] += 1
        zustand["ungespeichert"] = False

    monkeypatch.setattr(type(fenster.ergebnis_tab), "alle_speichern", _speichern)
    fenster._beenden_freigegeben = True
    fenster.close()
    assert zustand["gespeichert"] == 1


def test_terminwechsel_bricht_ab_wenn_speichern_zeilen_uebrig_laesst_und_nein(qtbot, termin, monkeypatch):
    fenster, fragen = _terminwechsel_vorbereiten(
        qtbot, termin, monkeypatch, [QMessageBox.Yes, QMessageBox.No], speichern_gelingt=False
    )

    fenster._termin_wechseln()

    assert fragen == ["Ungespeicherte Ergebnisse", "Nicht alle Ergebnisse gespeichert"]
    assert _StartDialogAttrappe.termin_geoeffnet == 0


def test_terminwechsel_geht_bei_ja_trotz_uebrig_gebliebener_aenderungen_weiter(qtbot, termin, monkeypatch):
    fenster, fragen = _terminwechsel_vorbereiten(
        qtbot, termin, monkeypatch, [QMessageBox.Yes, QMessageBox.Yes], speichern_gelingt=False
    )

    fenster._termin_wechseln()

    assert len(fragen) == 2
    assert _StartDialogAttrappe.termin_geoeffnet == 1


def test_terminwechsel_fragt_nicht_erneut_wenn_speichern_gelingt(qtbot, termin, monkeypatch):
    fenster, fragen = _terminwechsel_vorbereiten(
        qtbot, termin, monkeypatch, [QMessageBox.Yes], speichern_gelingt=True
    )

    fenster._termin_wechseln()

    assert fragen == ["Ungespeicherte Ergebnisse"]
    assert _StartDialogAttrappe.termin_geoeffnet == 1


def test_terminwechsel_fragt_nicht_wenn_der_startdialog_abgebrochen_wird(qtbot, termin, monkeypatch):
    """Offener Punkt 18.10.2026: die Rückfrage kommt erst nach der Auswahl im Startdialog."""
    fenster, fragen = _terminwechsel_vorbereiten(qtbot, termin, monkeypatch, [], speichern_gelingt=True)
    monkeypatch.setattr(_StartDialogAttrappe, "ergebnis", QDialog.Rejected)

    fenster._termin_wechseln()

    assert fragen == []
    assert _StartDialogAttrappe.geoeffnet == 1
    assert _StartDialogAttrappe.termin_geoeffnet == 0


@pytest.mark.parametrize(
    "neu, papierkorb_klappt", [(True, True), (True, False), (True, "fehler"), (False, True)]
)
def test_terminwechsel_abgebrochen_entfernt_eben_angelegten_termin(
    qtbot, termin, monkeypatch, tmp_path, neu, papierkorb_klappt
):
    """Marco 18.10.2026: neu angelegter Termin, dann „Abbrechen“ bei der Rückfrage - die leere
    Datei kommt in den Papierkorb (mit Hinweis). Ein gewählter vorhandener Termin bleibt."""
    fenster, fragen = _terminwechsel_vorbereiten(
        qtbot, termin, monkeypatch, [QMessageBox.Cancel], speichern_gelingt=True
    )
    datei = tmp_path / "neu.sqlite"
    init_db(str(datei)).close()
    monkeypatch.setattr(_StartDialogAttrappe, "pfad_vorgabe", str(datei))
    monkeypatch.setattr(_StartDialogAttrappe, "neu", neu)
    verschoben = []

    def _papierkorb(pfad):
        verschoben.append(pfad)
        if papierkorb_klappt == "fehler":
            raise PermissionError(13, "Zugriff verweigert", pfad)
        if papierkorb_klappt:
            os.remove(pfad)
        return papierkorb_klappt

    monkeypatch.setattr(_StartDialogAttrappe, "_in_papierkorb", staticmethod(_papierkorb), raising=False)
    hinweise = meldungen_sammeln(monkeypatch, "information", merke="titel_text")

    fenster._termin_wechseln()

    assert fragen == ["Ungespeicherte Ergebnisse"]
    assert _StartDialogAttrappe.termin_geoeffnet == 0
    if not neu:
        assert verschoben == [] and hinweise == [] and datei.exists()
    elif papierkorb_klappt is True:
        assert verschoben == [str(datei)] and not datei.exists()
        assert [titel for titel, _ in hinweise] == ["Neuer Termin entfernt"]
        assert "neu.sqlite" in hinweise[0][1]
    else:
        assert datei.exists()
        assert [titel for titel, _ in hinweise] == ["Neuer Termin bleibt"]
        assert "nicht in den Papierkorb" in hinweise[0][1] and "neu.sqlite" in hinweise[0][1]


def test_startdialog_merkt_neu_angelegten_termin(qtbot, monkeypatch, tmp_path):
    """Nur ein eben angelegter Termin gilt als neu, nicht ein gewählter vorhandener."""
    monkeypatch.setattr("app.liste_termine", lambda: [])
    for angelegt, bestehend, erwartet in ((True, False, True), (False, True, False)):
        dialog = StartDialog()
        qtbot.addWidget(dialog)

        class _Veranstaltung:
            def __init__(self, *a, **k):
                self.termin_angelegt = angelegt
                self.bestehenden_oeffnen = bestehend
                self.pfad_feld = QLineEdit(str(tmp_path / "x.sqlite"))

        monkeypatch.setattr("app.VeranstaltungsDialog", _Veranstaltung)
        ueberall_ersetzen(monkeypatch, "_ausfuehren", lambda d: QDialog.Accepted)
        dialog._neuer_termin()
        assert dialog.neu_angelegt is erwartet


def test_terminwechsel_zur_demo_fragt_nicht_vorab(qtbot, termin, monkeypatch):
    """Offener Punkt 18.10.2026: bei der Demo fragt deren Schritt 2 selbst - hier keine Frage."""
    fenster, fragen = _terminwechsel_vorbereiten(qtbot, termin, monkeypatch, [], speichern_gelingt=True)
    monkeypatch.setattr(_StartDialogAttrappe, "demo", True)
    gestartet = []

    class _Tour:
        def __init__(self, fenster):
            gestartet.append(fenster)

        def starten(self):
            pass

    monkeypatch.setattr("app.DemoTour", _Tour)

    fenster._termin_wechseln()

    assert fragen == []
    assert gestartet == [fenster]
    assert _StartDialogAttrappe.termin_geoeffnet == 0


# --- Codeprüfung 22.09., G4: Geschlecht "nicht angegeben" im TeilnehmerDialog ---------


def test_neuer_teilnehmer_startet_ohne_geschlecht(qtbot):
    dialog = TeilnehmerDialog(vergebene_nummern=set())
    qtbot.addWidget(dialog)

    assert dialog.geschlecht.currentText() == "–"
    assert dialog.ergebnis().geschlecht is None

    dialog.geschlecht.setCurrentText("Rüde")
    assert dialog.ergebnis().geschlecht == "Rüde"


# --- Codeprüfung 22.09., G5: Wiederherstellen "als Kopie" ohne doppelte Zieldateien ----


@pytest.mark.parametrize("namen", [
    ["A.sqlite", "A (2).sqlite"],
    ["A (2).sqlite", "A.sqlite"],
])
def test_wiederherstellen_kopie_kollidiert_nicht_mit_anderem_zip_eintrag(tmp_path, namen):
    (tmp_path / "A.sqlite").write_bytes(b"")

    entscheidungen, uebersprungen = _wiederherstellungsziele_planen(
        namen, {"A.sqlite"}, tmp_path, lambda name: "kopie"
    )

    assert entscheidungen == {"A.sqlite": "A (3).sqlite", "A (2).sqlite": "A (2).sqlite"}
    assert uebersprungen == 0


def test_wiederherstellen_mehrere_kopien_und_ueberschreiben_gemischt(tmp_path):
    for name in ("A.sqlite", "B.sqlite", "C.sqlite"):
        (tmp_path / name).write_bytes(b"")
    aktionen = {"A.sqlite": "kopie", "B.sqlite": "ueberschreiben", "C.sqlite": "ueberspringen"}
    namen = ["A.sqlite", "B.sqlite", "C.sqlite", "A (2).sqlite", "A (3).sqlite", "B (2).sqlite"]

    entscheidungen, uebersprungen = _wiederherstellungsziele_planen(
        namen, set(aktionen), tmp_path, lambda name: aktionen[name]
    )

    assert entscheidungen == {
        "A.sqlite": "A (4).sqlite",
        "B.sqlite": "B.sqlite",
        "A (2).sqlite": "A (2).sqlite",
        "A (3).sqlite": "A (3).sqlite",
        "B (2).sqlite": "B (2).sqlite",
    }
    assert uebersprungen == 1
    # Kern von G5: keine zwei ZIP-Einträge landen auf derselben Zieldatei.
    assert len(set(entscheidungen.values())) == len(entscheidungen)


def test_wiederherstellen_offener_termin_ausserhalb_des_ordners_ist_kein_konflikt_mit_sich(qtbot, tmp_path, monkeypatch):
    """Teil 7 Nr. 1: eine gleichnamige Datei im Termine-Ordner ist nicht der geöffnete
    Termin vom USB-Stick - „Überschreiben“ bleibt also erlaubt."""
    ordner = tmp_path / "Termine"
    ordner.mkdir()
    (ordner / "Pruefung.sqlite").write_bytes(b"")
    stick = tmp_path / "Stick"
    stick.mkdir()
    ueberall_ersetzen(monkeypatch, "termine_ordner", lambda: ordner)
    monkeypatch.setattr("app.QFileDialog.getOpenFileName", lambda *a, **k: ("sicherung.zip", ""))
    monkeypatch.setattr("desktop_verwaltung.sicherung_inhalt", lambda *a, **k: ["pruefung.sqlite"])
    tab = DatensicherungTab(aktueller_pfad=str(stick / "Pruefung.sqlite"))
    qtbot.addWidget(tab)
    abgefragt = []
    monkeypatch.setattr(
        tab, "_konflikt_abfragen",
        lambda name, ist_offener_termin=False: abgefragt.append((name, ist_offener_termin)) or "ueberspringen",
    )
    tab._sicherung_wiederherstellen()
    assert abgefragt == [("pruefung.sqlite", False)]


@pytest.mark.parametrize("eingaben, gefunden", [
    (["", "falsch1", "falsch2", "richtig"], True),
    (["falsch1", "falsch2", "falsch3"], False),
])
def test_wiederherstellen_passwortschleife_prueft_drei_passwoerter(qtbot, tmp_path, monkeypatch, eingaben, gefunden):
    """Teil 7 Nr. 2 und Nr. 11: einmal ohne, dann drei Passwörter - auch das dritte wird
    geprüft; eine leere Eingabe kostet keinen Versuch. Danach ein Meldungsfenster."""
    from db_sicherung import PasswortFalschError

    ueberall_ersetzen(monkeypatch, "termine_ordner", lambda: tmp_path)
    monkeypatch.setattr("app.QFileDialog.getOpenFileName", lambda *a, **k: ("sicherung.zip", ""))
    geprueft = []

    def inhalt(_pfad, passwort=None):
        geprueft.append(passwort)
        if passwort != "richtig":
            raise PasswortFalschError("falsch")
        return ["neu.sqlite"]

    abfragen = list(eingaben)
    monkeypatch.setattr("desktop_verwaltung.sicherung_inhalt", inhalt)
    monkeypatch.setattr("desktop_verwaltung.QInputDialog.getText", lambda *a, **k: (abfragen.pop(0), True))
    monkeypatch.setattr("desktop_verwaltung.sicherung_wiederherstellen", lambda *a, **k: ["neu.sqlite"])
    meldungen = meldungen_sammeln(monkeypatch, "warning", merke="titel")
    monkeypatch.setattr("app.QMessageBox.information", lambda *a, **k: meldungen.append(a[1]))
    tab = DatensicherungTab()
    qtbot.addWidget(tab)

    tab._sicherung_wiederherstellen()

    if gefunden:
        assert geprueft == [None, "falsch1", "falsch2", "richtig"]
        assert meldungen == ["Wiederherstellen abgeschlossen"]
    else:
        assert geprueft == [None, "falsch1", "falsch2", "falsch3"]
        assert meldungen == ["Passwort falsch"]
    assert abfragen == []


def test_wiederherstellen_nicht_lesbare_sicherung_meldet_klartext(qtbot, monkeypatch):
    """Verifikation A9 / Teil 7 Nr. 11: Datei inzwischen weg -> Meldung statt Fehlerfenster."""
    def weg(*_a, **_k):
        raise FileNotFoundError(2, "No such file or directory", "sicherung.zip")

    monkeypatch.setattr("app.QFileDialog.getOpenFileName", lambda *a, **k: ("sicherung.zip", ""))
    monkeypatch.setattr("desktop_verwaltung.sicherung_inhalt", weg)
    meldungen = meldungen_sammeln(monkeypatch, "warning")
    tab = DatensicherungTab()
    qtbot.addWidget(tab)
    tab._sicherung_wiederherstellen()
    assert "nicht gefunden" in meldungen[0]


@pytest.mark.parametrize("knopf, erwartet", [
    ("Mitsichern", "mit"), ("Ohne ihn fortfahren", "ohne"), ("Abbrechen", None),
])
def test_sicherung_fragt_bei_termin_ausserhalb_des_ordners(qtbot, conn, tmp_path, monkeypatch, knopf, erwartet):
    """Teil 7 Nr. 1 (Marcos Entscheidung): Rückfrage Mitsichern / Ohne ihn / Abbrechen;
    ohne ihn nennt der Dateiname weder Datum noch Verein des Termins."""
    set_veranstaltung(conn, verein="HSV", datum="2026-11-14")
    ordner = tmp_path / "Termine"
    ordner.mkdir()
    termin_pfad = tmp_path / "Stick" / "termin.sqlite"
    termin_pfad.parent.mkdir()
    termin_pfad.write_bytes(b"")
    ueberall_ersetzen(monkeypatch, "termine_ordner", lambda: ordner)
    monkeypatch.setattr(QMessageBox, "exec", lambda box: 0)
    monkeypatch.setattr(QMessageBox, "clickedButton",
                        lambda box: next(b for b in box.buttons() if b.text() == knopf))

    class _Dialog:
        def __init__(self, _parent):
            pass

        def exec(self):
            return QDialog.Accepted

        def passwort(self):
            return None

    vorschlaege, aufrufe = [], []
    monkeypatch.setattr("desktop_verwaltung.SicherungErstellenDialog", _Dialog)
    monkeypatch.setattr("app.QFileDialog.getSaveFileName",
                        lambda _p, _t, vorschlag, _f: vorschlaege.append(vorschlag) or (str(tmp_path / "s.zip"), ""))
    monkeypatch.setattr("desktop_verwaltung.sicherung_erstellen", lambda pfad, **k: aufrufe.append(k) or 1)
    ueberall_ersetzen(monkeypatch, "_datei_gespeichert_melden", lambda *a, **k: None)
    tab = DatensicherungTab(aktueller_pfad=str(termin_pfad), conn=conn)
    qtbot.addWidget(tab)

    tab._sicherung_erstellen()

    if erwartet is None:
        assert aufrufe == []
        return
    assert aufrufe[0]["zusaetzliche"] == ([str(termin_pfad)] if erwartet == "mit" else [])
    # Seit UX-Test 2026-11 (T11) nennt der Name „alle-Termine“ statt des geöffneten Termins.
    assert os.path.basename(vorschlaege[0]).endswith("_alle-Termine.zip")


@pytest.mark.parametrize("roh", [[], ["kaputt.sqlite"]])
def test_sicherung_nennt_roh_gesicherte_dateien(qtbot, tmp_path, monkeypatch, gespeichert_meldungen, roh):
    """Offene Punkte O1 (Marco 18.10.2026): nicht lesbare Dateien werden roh gesichert und
    in der Meldung genannt."""
    ueberall_ersetzen(monkeypatch, "termine_ordner", lambda: tmp_path)

    class _Dialog:
        def __init__(self, _parent):
            pass

        def exec(self):
            return QDialog.Accepted

        def passwort(self):
            return None

    def _sichern(pfad, roh_gesichert, **_k):
        roh_gesichert.extend(roh)
        return 2

    monkeypatch.setattr("desktop_verwaltung.SicherungErstellenDialog", _Dialog)
    monkeypatch.setattr("app.QFileDialog.getSaveFileName", lambda *a: (str(tmp_path / "s.zip"), ""))
    monkeypatch.setattr("desktop_verwaltung.sicherung_erstellen", _sichern)
    monkeypatch.setattr("app.QMessageBox.critical", lambda *a, **k: pytest.fail("Sicherung gescheitert"))
    tab = DatensicherungTab()
    qtbot.addWidget(tab)

    tab._sicherung_erstellen()

    assert gespeichert_meldungen[-1][1] == "Sicherung erstellt (2 Termin(e))"
    if roh:
        assert "• kaputt.sqlite" in meldungen_hinweise[-1]
        assert "nicht als Termin lesen" in meldungen_hinweise[-1]
    else:
        assert meldungen_hinweise[-1] is None


def test_sicherung_ohne_rueckfrage_wenn_termin_im_ordner(qtbot, tmp_path, monkeypatch):
    ueberall_ersetzen(monkeypatch, "termine_ordner", lambda: tmp_path)
    (tmp_path / "termin.sqlite").write_bytes(b"")
    tab = DatensicherungTab(aktueller_pfad=str(tmp_path / "termin.sqlite"))
    qtbot.addWidget(tab)
    assert tab._mitsichern_abfragen() == []


@pytest.mark.parametrize("papierkorb", [True, False])
def test_termin_loeschen_vorgabe_nein_papierkorb_und_auswahl_leer(qtbot, tmp_path, monkeypatch, papierkorb):
    """Teil 7 Nr. 5 (Marcos Entscheidung): Vorgabe „Nein“, Papierkorb; ohne Papierkorb erst
    nach eigener Rückfrage endgültig; danach ist nichts mehr markiert."""
    start = _startdialog_mit_terminen(qtbot, tmp_path, monkeypatch)
    # Teil 7 Nr. 11: ohne Verein steht der Dateiname da.
    assert start.tabelle.item(1, 1).text() == "b.sqlite"
    papierkorb_pfade = []
    fragen = rueckfragen_sammeln(monkeypatch, QMessageBox.Yes, merke="titel_vorgabe")

    def in_papierkorb(pfad):
        papierkorb_pfade.append(pfad)
        if papierkorb:
            os.remove(pfad)
        return papierkorb  # PySide6 6.11 liefert ein reines bool

    monkeypatch.setattr("app.QFile.moveToTrash", in_papierkorb)
    start.tabelle.selectRow(0)

    start._termin_loeschen()

    assert not (tmp_path / "a.sqlite").exists()
    assert papierkorb_pfade == [str(tmp_path / "a.sqlite")]
    erwartet = [("Termin löschen", QMessageBox.No)] + ([] if papierkorb else [("Kein Papierkorb", QMessageBox.No)])
    assert fragen == erwartet
    assert start.tabelle.currentRow() == -1 and not start.loeschen_btn.isEnabled()


def test_termin_loeschen_nein_behaelt_datei(qtbot, tmp_path, monkeypatch):
    start = _startdialog_mit_terminen(qtbot, tmp_path, monkeypatch)
    rueckfragen_beantworten(monkeypatch, QMessageBox.No)
    monkeypatch.setattr("app.QFile.moveToTrash", lambda pfad: pytest.fail("darf nicht löschen"))
    start.tabelle.selectRow(0)
    start._termin_loeschen()
    assert (tmp_path / "a.sqlite").exists()


def test_startdialog_markiert_einzigen_termin(qtbot, tmp_path, monkeypatch):
    """UX-Test 03.11.2026, X15: Bei genau einem lesbaren Termin ist er gleich markiert und
    „Öffnen“ aktiv; bei zwei Terminen bleibt die Auswahl leer."""
    start = _startdialog_mit_terminen(qtbot, tmp_path, monkeypatch)
    assert not start.oeffnen_btn.isEnabled()  # zwei Termine: keine Vorauswahl
    (tmp_path / "b.sqlite").unlink()
    start._aktualisieren()
    assert start.tabelle.currentRow() == 0 and start.oeffnen_btn.isEnabled()


def test_startdialog_enter_oeffnet_markierten_termin(qtbot, tmp_path, monkeypatch):
    """Teil 7 Nr. 8: Enter in der Liste öffnet den markierten Termin statt „Neuen Termin
    anlegen…“."""
    start = _startdialog_mit_terminen(qtbot, tmp_path, monkeypatch)
    neu = []
    monkeypatch.setattr(start, "_neuer_termin", lambda: neu.append(True))
    start.show()
    start.tabelle.selectRow(1)
    start.tabelle.setFocus()
    qtbot.keyClick(start.tabelle, Qt.Key_Return)
    assert start.pfad == str(tmp_path / "b.sqlite") and neu == []


def test_wiederherstellen_unvollstaendig_nennt_ersetzte_termine(qtbot, tmp_path, monkeypatch):
    """QS-Prüfung 07.10.2026, Befund 3: Bricht das Wiederherstellen nach dem ersten
    ersetzten Termin ab, nennt das Meldungsfenster die schon ersetzten Termine."""
    from db_sicherung import TeilweiseWiederhergestelltError

    ueberall_ersetzen(monkeypatch, "termine_ordner", lambda: tmp_path)
    monkeypatch.setattr("app.QFileDialog.getOpenFileName", lambda *a, **k: ("sicherung.zip", ""))
    monkeypatch.setattr("desktop_verwaltung.sicherung_inhalt", lambda *a, **k: ["a.sqlite", "b.sqlite"])

    def wiederherstellen_mit_abbruch(*a, **k):
        raise TeilweiseWiederhergestelltError(["a.sqlite"], PermissionError("Datei gesperrt"))

    monkeypatch.setattr("desktop_verwaltung.sicherung_wiederherstellen", wiederherstellen_mit_abbruch)
    meldungen = meldungen_sammeln(monkeypatch, "critical", merke="titel_text")
    tab = DatensicherungTab()
    qtbot.addWidget(tab)

    tab._sicherung_wiederherstellen()

    assert len(meldungen) == 1
    titel, text = meldungen[0]
    assert titel == "Wiederherstellen unvollständig"
    assert "Datei gesperrt" in text
    assert "a.sqlite" in text
    assert "b.sqlite" not in text
    assert "unvollständig: 1 Termin(e)" in tab.status_label.text()


def test_termin_dialog_zweispaltig_und_so_hoch_wie_sein_inhalt(qtbot):
    """Nachtest 2, N14: Prüfungen und Startnummern-Bereiche stehen rechts neben den Eckdaten,
    und der Dialog ist so hoch wie sein Inhalt (höchstens 90 % des Bildschirms) - vorher lagen
    „Behältnisse“, „Fläche“ und die Bereiche unter dem Bildlauf."""
    from PySide6.QtCore import QPoint, QSize
    from PySide6.QtWidgets import QScrollArea
    from desktop_dialoge import VeranstaltungsDialog, _groesse_auf_bildschirm_begrenzen

    class _Inhalt:
        def ensurePolished(self):
            pass

        def sizeHint(self):
            return QSize(500, 600)

    probe = QDialog()
    qtbot.addWidget(probe)
    frei = probe.screen().availableGeometry()
    _groesse_auf_bildschirm_begrenzen(probe, 300, 200, inhalt=_Inhalt(), hoehe_nach_inhalt=True)
    assert probe.height() == min(710, int(frei.height() * DIALOG_MAX_HOEHE_ANTEIL))
    _groesse_auf_bildschirm_begrenzen(probe, 300, 200, inhalt=_Inhalt())
    assert probe.height() == min(200, int(frei.height() * DIALOG_MAX_HOEHE_ANTEIL))  # Teilnehmer-Dialog: wie bisher

    dialog = VeranstaltungsDialog(None)
    qtbot.addWidget(dialog)
    inhalt = dialog.findChild(QScrollArea).widget()
    verein_rechts = dialog.verein.mapTo(inhalt, QPoint(dialog.verein.width(), 0)).x()
    assert dialog.gruppe_pruefungen.mapTo(inhalt, QPoint(0, 0)).x() > verein_rechts
    assert dialog.gruppe_bereiche.mapTo(inhalt, QPoint(0, 0)).x() > verein_rechts


def test_offene_starts_seitenleiste_passt_fuer_lange_zeilen(qtbot, conn):
    """Nachtest 2, N14: Die Seitenleiste ist so breit wie die längste mögliche Zeile
    („DK LK 3 – Behältnisstrecke (99 Teilnehmer)“), vorher brach sie um."""
    tab = ZeitplanTab(conn)
    qtbot.addWidget(tab)
    noetig = tab._offene_starts_label.fontMetrics().horizontalAdvance(tab._LAENGSTE_OFFENE_ZEILE)
    frei = tab.screen().availableGeometry().width()
    # Anforderung N14 mit fester Zahl (lange Zeilen passen, soweit der Bildschirm reicht) ...
    assert tab._offene_starts_box.minimumWidth() >= min(noetig + 40, max(280, int(frei * tab.SEITENLEISTE_MIN_ANTEIL)))
    # ... und die genaue Formel.
    breite = noetig + tab.SEITENLEISTE_ZUSCHLAG
    assert tab._offene_starts_box.minimumWidth() == max(280, min(breite, int(frei * tab.SEITENLEISTE_MIN_ANTEIL)))
    assert tab._offene_starts_box.maximumWidth() >= min(breite, max(360, int(frei * tab.SEITENLEISTE_MAX_ANTEIL)))

    # Verifikation B19: nach einem Wechsel der Schrift (Stylesheet) neu gemessen - mit der
    # neuen Schrift (gemessen wird erst, wenn sie angekommen ist).
    gemessen = []
    echt = tab._seitenleiste_breite_anpassen
    tab._seitenleiste_breite_anpassen = lambda: gemessen.append(
        tab._offene_starts_label.fontMetrics().horizontalAdvance(tab._LAENGSTE_OFFENE_ZEILE)) or echt()
    tab.setStyleSheet("QLabel { font-size: 20pt; }")
    qtbot.waitUntil(lambda: bool(gemessen), timeout=2000)
    assert max(gemessen) > noetig


def test_neuer_termin_hinweis_bei_leerem_verband_und_meldestelle(qtbot, monkeypatch, tmp_path):
    """UX-Test 02.10.2026, K6: nur beim Anlegen, Speichern bleibt möglich."""
    ueberall_ersetzen(monkeypatch, "termine_ordner", lambda: tmp_path)  # Teil 2 Nr. 15
    dialog = VeranstaltungsDialog(vorbelegung={"verein": "HSV", "datum": "2026-11-14"})
    qtbot.addWidget(dialog)
    dialog.pfad_feld.setText(str(tmp_path / "t.sqlite"))
    fragen = []
    antwort = [QMessageBox.No]
    vorgaben = []
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: fragen.append(a[2]) or vorgaben.append(a[4]) or antwort[0])
    akzeptiert = []
    monkeypatch.setattr(dialog, "accept", lambda: akzeptiert.append(True))

    dialog._pruefen_und_akzeptieren()
    assert "Verband und Meldestelle sind leer" in fragen[-1]
    # UX-Test 2026-11, T7 (Marco 04.11.2026): Vorgabe jetzt „Nein“ (vorher „Ja“, 15.10.2026).
    assert vorgaben[-1] == QMessageBox.No
    assert not akzeptiert

    dialog.verband.setText("HSVRM")
    antwort[0] = QMessageBox.Yes
    dialog._pruefen_und_akzeptieren()
    assert fragen[-1].startswith("Meldestelle ist leer und fehlt")
    assert akzeptiert

    # Beim Bearbeiten kein Hinweis.
    fragen.clear()
    bearbeitet = VeranstaltungsDialog(vorbelegung={"verein": "HSV", "datum": "2026-11-14"}, bearbeiten=True)
    qtbot.addWidget(bearbeitet)
    monkeypatch.setattr(bearbeitet, "accept", lambda: None)
    bearbeitet._pruefen_und_akzeptieren()
    assert not fragen


def test_veranstaltungsdialog_startnummer_bereiche(qtbot, monkeypatch):
    """UX-Test 02.10.2026, U1b: Bereichsfelder nur für angebotene Prüfungen (ohne Angebot
    alle), Vorbelegung, Prüfung auf halbe Angaben und Überschneidungen."""
    dialog = VeranstaltungsDialog(
        vorbelegung={"verein": "HSV", "datum": "2026-11-14",
                     "angebotene_pruefungen": "DK1,ED1-Trümmerfeld",
                     "startnummer_bereiche": "DK1=1-20"},
        bearbeiten=True,
    )
    qtbot.addWidget(dialog)
    dialog.show()

    sichtbar = [k for k, (label, _v, _b) in dialog.bereich_felder.items() if label.isVisible()]
    assert sichtbar == ["DK1", "ED1-Trümmerfeld"]
    assert dialog.bereich_felder["DK1"][1].text() == "1"
    assert dialog.bereich_felder["DK1"][2].text() == "20"

    meldungen = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: meldungen.append(a[2]))
    akzeptiert = []
    monkeypatch.setattr(dialog, "accept", lambda: akzeptiert.append(True))

    dialog.bereich_felder["ED1-Trümmerfeld"][1].setText("15")
    dialog._pruefen_und_akzeptieren()
    assert "„von“ UND „bis“" in meldungen[-1]

    dialog.bereich_felder["ED1-Trümmerfeld"][2].setText("30")
    dialog._pruefen_und_akzeptieren()
    assert "überschneiden sich" in meldungen[-1]
    assert not akzeptiert

    dialog.bereich_felder["ED1-Trümmerfeld"][1].setText("21")
    dialog._pruefen_und_akzeptieren()
    assert akzeptiert == [True]
    assert dialog.startnummer_bereiche_text() == "DK1=1-20,ED1-Trümmerfeld=21-30"

    # Ohne angehakte Prüfungen sind alle 12 Zeilen sichtbar.
    for checkbox in dialog.pruefung_checkboxen.values():
        checkbox.setChecked(False)
    assert all(label.isVisible() for label, _v, _b in dialog.bereich_felder.values())


def test_veranstaltungsdialog_bereiche_automatisch_festlegen(qtbot, monkeypatch):
    """Marco 09.10.2026: Standardgröße, Anzahl je Prüfung, Automatik überschreibt alle
    von/bis-Felder der angebotenen Prüfungen lückenlos ab 1; Standardgröße wird gespeichert."""
    dialog = VeranstaltungsDialog(
        vorbelegung={"verein": "HSV", "datum": "2026-11-14",
                     "angebotene_pruefungen": "ED1-Trümmerfeld,ED1-Flächensuche,ED2-Flächensuche",
                     "startnummer_bereiche": "ED1-Flächensuche=50-59",
                     "startnummer_bereichsgroesse": "15"},
        bearbeiten=True,
    )
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.standard_groesse.value() == 15
    # Anzahl aus dem vorhandenen Bereich, sonst Standardgröße
    assert dialog.anzahl_felder["ED1-Flächensuche"].value() == 10
    assert dialog.anzahl_felder["ED1-Trümmerfeld"].value() == 15
    assert dialog.anzahl_felder["ED1-Trümmerfeld"].isVisible()
    assert not dialog.anzahl_felder["DK1"].isVisible()

    dialog.standard_groesse.setValue(20)
    qtbot.mouseClick(dialog.standard_uebernehmen_btn, Qt.MouseButton.LeftButton)
    assert {f.value() for f in dialog.anzahl_felder.values()} == {20}
    dialog.anzahl_felder["ED2-Flächensuche"].setValue(0)  # "keine" = kein Bereich
    qtbot.mouseClick(dialog.automatisch_btn, Qt.MouseButton.LeftButton)
    assert dialog.startnummer_bereiche_text() == "ED1-Trümmerfeld=1-20,ED1-Flächensuche=21-40"
    assert dialog.bereich_felder["ED2-Flächensuche"][1].text() == ""

    meldungen = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: meldungen.append(a[2]))
    dialog.anzahl_felder["ED1-Trümmerfeld"].setValue(990)
    qtbot.mouseClick(dialog.automatisch_btn, Qt.MouseButton.LeftButton)
    assert "999" in meldungen[-1]
    assert dialog.startnummer_bereiche_text() == "ED1-Trümmerfeld=1-20,ED1-Flächensuche=21-40"

    assert dialog.veranstaltung_werte()["startnummer_bereichsgroesse"] == "20"

    # Verifikation V1: von Hand geänderte von/bis-Felder ziehen die Anzahl mit.
    dialog.anzahl_felder["ED1-Trümmerfeld"].setValue(20)
    bis_feld = dialog.bereich_felder["ED1-Trümmerfeld"][2]
    bis_feld.clear()
    qtbot.keyClicks(bis_feld, "12")
    assert dialog.anzahl_felder["ED1-Trümmerfeld"].value() == 12
    qtbot.mouseClick(dialog.automatisch_btn, Qt.MouseButton.LeftButton)
    assert dialog.startnummer_bereiche_text() == "ED1-Trümmerfeld=1-12,ED1-Flächensuche=13-32"

    # Verifikation C: von und bis von Hand geleert -> Anzahl "keine", Bereich bleibt weg.
    von_feld = dialog.bereich_felder["ED1-Trümmerfeld"][1]
    for feld in (von_feld, bis_feld):
        feld.selectAll()
        qtbot.keyClick(feld, Qt.Key.Key_Delete)
    assert dialog.anzahl_felder["ED1-Trümmerfeld"].value() == 0
    qtbot.mouseClick(dialog.automatisch_btn, Qt.MouseButton.LeftButton)
    assert dialog.startnummer_bereiche_text() == "ED1-Flächensuche=1-20"


def test_startdialog_schleife_zeigt_nach_demo_wieder_den_startdialog(monkeypatch):
    import app

    ablauf = []

    class _StartAttrappe:
        aufrufe = 0

        def __init__(self, *args, **kwargs):
            type(self).aufrufe += 1
            self.demo_angefordert = type(self).aufrufe == 1
            self.pfad = None if self.demo_angefordert else "termin.sqlite"

        def exec(self):
            return QDialog.Accepted

    monkeypatch.setattr("app.StartDialog", _StartAttrappe)
    monkeypatch.setattr("app.demo_ohne_termin_ausfuehren", lambda fabrik: ablauf.append(fabrik))

    assert app._startdialog_schleife() == "termin.sqlite"
    assert ablauf == [HauptFenster]
    assert _StartAttrappe.aufrufe == 2


def test_veranstaltungsdialog_liefert_alle_werte_fuer_set_veranstaltung(qtbot):
    import inspect

    dialog = VeranstaltungsDialog(vorbelegung={"verein": "V", "datum": "2026-10-04"}, bearbeiten=True)
    qtbot.addWidget(dialog)

    werte = dialog.veranstaltung_werte()

    assert werte["verein"] == "V" and werte["datum"] == "2026-10-04"
    assert set(werte) <= set(inspect.signature(set_veranstaltung).parameters) - {"conn"}


@pytest.mark.parametrize("knopf, erwartet, uebersprungen", [
    ("Überschreiben", {"Pruefung.sqlite": "Aus Sicherung", "Neu.sqlite": "Neu"}, False),
    ("Als Kopie importieren",
     {"Pruefung.sqlite": "Bestand", "Pruefung (2).sqlite": "Aus Sicherung", "Neu.sqlite": "Neu"}, False),
    ("Überspringen", {"Pruefung.sqlite": "Bestand", "Neu.sqlite": "Neu"}, True),
    (None, {"Pruefung.sqlite": "Bestand", "Neu.sqlite": "Neu"}, True),  # Esc bzw. Fenster geschlossen
], ids=["ueberschreiben", "kopie", "ueberspringen", "geschlossen"])
def test_wiederherstellen_konflikt_rueckfrage_entscheidet_ueber_zieldateien(
    qtbot, tmp_path, monkeypatch, _termine_ordner_schuetzen, knopf, erwartet, uebersprungen,
):
    """Abdeckung 01.11.2026 (B10): echte Sicherung, im Termine-Ordner ein gleichnamiger
    Termin. Die Rückfrage bietet Überschreiben / Als Kopie / Überspringen (Vorgabe
    Überspringen); nur „Überschreiben“ ersetzt den vorhandenen Termin, sonst bleibt er
    erhalten. Der Termin ohne Konflikt wird immer ohne Rückfrage übernommen."""
    termine = _termine_ordner_schuetzen
    zip_pfad = _sicherung_mit_namenskonflikt(tmp_path, termine)
    monkeypatch.setattr("app.QFileDialog.getOpenFileName", lambda *a, **k: (zip_pfad, ""))
    gefragt = _konflikt_box_ersetzen(monkeypatch, knopf)
    meldungen = meldungen_sammeln(monkeypatch, "information", merke="titel_text")
    monkeypatch.setattr("app.QMessageBox.critical", lambda *a, **k: pytest.fail(f"Fehlermeldung: {a[1:3]}"))
    tab = DatensicherungTab()
    qtbot.addWidget(tab)

    tab._sicherung_wiederherstellen()

    assert len(gefragt) == 1
    titel, text, knoepfe, vorgabe = gefragt[0]
    assert titel == "Termin bereits vorhanden" and "„Pruefung.sqlite“" in text
    assert knoepfe == sorted(["Überschreiben", "Als Kopie importieren", "Überspringen"])
    assert vorgabe == "Überspringen"
    assert _vereine_im_ordner(termine) == erwartet
    anzahl = 1 if uebersprungen else 2
    zusatz = ", 1 übersprungen" if uebersprungen else ""
    assert meldungen == [("Wiederherstellen abgeschlossen", f"{anzahl} Termin(e) wiederhergestellt{zusatz}. "
                          "Neue Termine erscheinen in der Terminübersicht beim nächsten „Anderen Termin öffnen…“.")]
    assert tab.status_label.text() == meldungen[0][1]


def test_wiederherstellen_konflikt_mit_offenem_termin_bietet_kein_ueberschreiben(
    qtbot, tmp_path, monkeypatch, _termine_ordner_schuetzen,
):
    """Abdeckung 01.11.2026 (B10): Ist der gleichnamige Termin gerade geöffnet, fehlt
    „Überschreiben“ samt Hinweis; „Als Kopie importieren“ lässt den offenen Termin
    unverändert."""
    termine = _termine_ordner_schuetzen
    zip_pfad = _sicherung_mit_namenskonflikt(tmp_path, termine)
    monkeypatch.setattr("app.QFileDialog.getOpenFileName", lambda *a, **k: (zip_pfad, ""))
    gefragt = _konflikt_box_ersetzen(monkeypatch, "Als Kopie importieren")
    meldungen_stumm(monkeypatch, "information")
    monkeypatch.setattr("app.QMessageBox.critical", lambda *a, **k: pytest.fail(f"Fehlermeldung: {a[1:3]}"))
    offen_pfad = termine / "Pruefung.sqlite"
    with closing(init_db(str(offen_pfad))) as offen:
        tab = DatensicherungTab(aktueller_pfad=str(offen_pfad), conn=offen)
        qtbot.addWidget(tab)

        tab._sicherung_wiederherstellen()

        assert get_veranstaltung(offen)["verein"] == "Bestand"
    _titel, text, knoepfe, vorgabe = gefragt[0]
    assert knoepfe == sorted(["Als Kopie importieren", "Überspringen"]) and vorgabe == "Überspringen"
    assert "gerade im Hauptfenster geöffnet" in text
    assert _vereine_im_ordner(termine) == {
        "Pruefung.sqlite": "Bestand", "Pruefung (2).sqlite": "Aus Sicherung", "Neu.sqlite": "Neu",
    }


def test_sicherung_erstellen_dialog_prueft_passwort(qtbot, monkeypatch):
    """Abdeckung 01.11.2026 (B10): SicherungErstellenDialog - ohne Häkchen gesperrte
    Passwortfelder und kein Passwort; mit Häkchen bleibt er bei fehlendem oder
    abweichendem Passwort mit Warnung offen und nimmt erst gleiche Eingaben an."""
    from desktop_dialoge import SicherungErstellenDialog

    warnungen = meldungen_sammeln(monkeypatch, "warning", merke="titel")

    ohne = SicherungErstellenDialog(None)
    qtbot.addWidget(ohne)
    assert not ohne.passwort_feld.isEnabled() and not ohne.passwort_wiederholen_feld.isEnabled()
    ohne.passwort_feld.setText("wird ignoriert")
    _dialog_knopf(ohne, QDialogButtonBox.Ok).click()
    assert ohne.result() == QDialog.Accepted and ohne.passwort() is None and warnungen == []

    mit = SicherungErstellenDialog(None)
    qtbot.addWidget(mit)
    angenommen = []
    mit.accepted.connect(lambda: angenommen.append(True))
    mit.passwort_checkbox.setChecked(True)
    assert mit.passwort_feld.isEnabled() and mit.passwort_wiederholen_feld.isEnabled()
    ok = _dialog_knopf(mit, QDialogButtonBox.Ok)
    ok.click()
    assert warnungen == ["Passwort fehlt"] and angenommen == []
    mit.passwort_feld.setText("geheim")
    mit.passwort_wiederholen_feld.setText("anders")
    ok.click()
    assert warnungen == ["Passwort fehlt", "Passwörter unterschiedlich"] and angenommen == []
    assert mit.result() != QDialog.Accepted
    mit.passwort_wiederholen_feld.setText("geheim")
    ok.click()
    assert angenommen == [True] and mit.result() == QDialog.Accepted
    assert mit.passwort() == "geheim" and len(warnungen) == 2

    # Häkchen wieder weg: kein Passwort, die Felder sind wieder gesperrt.
    mit.passwort_checkbox.setChecked(False)
    assert mit.passwort() is None and not mit.passwort_feld.isEnabled()

    abbrechen = SicherungErstellenDialog(None)
    qtbot.addWidget(abbrechen)
    _dialog_knopf(abbrechen, QDialogButtonBox.Cancel).click()
    assert abbrechen.result() == QDialog.Rejected


def test_startdialog_mit_kopfbalken_und_symbolen(qtbot, monkeypatch, tmp_path):
    ueberall_ersetzen(monkeypatch, "termine_ordner", lambda: tmp_path)
    monkeypatch.setattr("app.liste_termine", lambda: [])
    dialog = StartDialog()
    qtbot.addWidget(dialog)
    assert dialog.kopf.titel_label.text() == "SHS-Prüfungsprogramm"
    assert dialog.kopf.unterzeile_label.text() == "Prüfungen im Spürhundsport verwalten"
    assert dialog.kopf.bild_label.width() == 52
    knoepfe = {b.text(): b for b in dialog.findChildren(QPushButton)}
    assert not knoepfe["Neuen Termin anlegen…"].icon().isNull()
    assert not knoepfe["Öffnen"].icon().isNull()
    assert knoepfe["Demoprüfung"].parent() is dialog.kopf
    assert any(label.text() == "Termin wählen oder neu anlegen:" for label in dialog.findChildren(QLabel))


def test_hauptfenster_hat_abrechnungsreiter_vor_der_verwaltung(qtbot, termin):
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    titel = [fenster._tabs.tabText(i) for i in range(fenster._tabs.count())]
    assert titel.index("Abrechnung Leistungsrichter") == titel.index("Verwaltung") - 1


def test_neuer_termin_dialog_reicht_saetze_durch(qtbot):
    dialog = VeranstaltungsDialog(vorbelegung={"verein": "HSV", "lr_km_satz": "0,4", "lr_tagespauschale": "55"})
    qtbot.addWidget(dialog)
    werte = dialog.veranstaltung_werte()
    assert (werte["lr_km_satz"], werte["lr_tagespauschale"]) == ("0,4", "55")
    leer = VeranstaltungsDialog(vorbelegung={"verein": "HSV"})
    qtbot.addWidget(leer)
    assert "lr_km_satz" not in leer.veranstaltung_werte()


def test_neuer_termin_dialog_reicht_eigene_checkliste_durch(qtbot):
    dialog = VeranstaltungsDialog(vorbelegung={"verein": "HSV", "checkliste_eigene": '{"kategorien": [], "punkte": []}'})
    qtbot.addWidget(dialog)
    assert "checkliste_eigene" in dialog.veranstaltung_werte()
    assert "checkliste" not in dialog.veranstaltung_werte()  # Haken werden nie übernommen


def test_startdialog_hat_menues_ansicht_und_hilfe(qtbot):
    from PySide6.QtWidgets import QMenuBar

    dialog = StartDialog()
    qtbot.addWidget(dialog)
    menues = [a.text().replace("&", "") for a in dialog.findChildren(QMenuBar)[0].actions()]
    assert menues == ["Ansicht", "Hilfe"]
    assert set(dialog._schrift_actions) and set(dialog._design_actions) and set(dialog._theme_actions)


def test_hauptfenster_kuerzel_und_startdialog_suche_sortierung(qtbot, termin, monkeypatch):
    conn, pfad = termin
    _teilnehmer_anlegen(conn, nachname="Albers", startnummer=1)
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()
    fenster._reiter_per_kuerzel(1)
    assert fenster._tabs.currentIndex() == 1
    fenster._tabs.setCurrentWidget(fenster.teilnehmer_tab)
    fenster._suche_fokussieren()
    # focusWidget statt hasFocus: das Fenster ist im Testlauf nicht unbedingt das aktive Fenster
    assert fenster.focusWidget() is fenster.teilnehmer_tab.filter_name
    geoeffnet = []
    monkeypatch.setattr(fenster.teilnehmer_tab, "_teilnehmer_hinzufuegen", lambda: geoeffnet.append(1))
    fenster.teilnehmer_tab.hinzufuegen_btn.clicked.disconnect()
    fenster.teilnehmer_tab.hinzufuegen_btn.clicked.connect(lambda: geoeffnet.append(1))
    fenster._tabs.setCurrentIndex(3)
    fenster._neuer_teilnehmer_per_kuerzel()
    assert geoeffnet == [1] and fenster._tabs.currentWidget() is fenster.teilnehmer_tab


def test_startdialog_suche_und_sortierung(qtbot, monkeypatch):
    """Marco 10.11.2026: Terminliste durchsuchen und per Spaltenklick sortieren; die Auswahl
    gehört danach zum richtigen Termin."""
    from db import TerminInfo

    def termin(verein, ort, datum, anzahl):
        return TerminInfo(pfad=f"/x/{verein}.sqlite", dateiname=f"{verein}.sqlite", verein=verein, vereins_nr=None,
                          ort=ort, datum=datum, anzahl_teilnehmer=anzahl, lesbar=True)

    termine = [termin("SV Zeta", "Aachen", "2026-11-14", 5), termin("SV Alpha", "Zeven", "2026-10-03", 30),
               termin("SV Mitte", "Bonn", "2025-05-01", 12)]
    monkeypatch.setattr("app.liste_termine", lambda: list(termine))
    dialog = StartDialog()
    qtbot.addWidget(dialog)
    spalte = lambda n: [dialog.tabelle.item(r, n).text() for r in range(dialog.tabelle.rowCount())]  # noqa: E731
    assert spalte(1) == ["SV Zeta", "SV Alpha", "SV Mitte"]  # Standard: wie geliefert (neueste oben)
    dialog._spalte_geklickt(1)
    assert spalte(1) == ["SV Alpha", "SV Mitte", "SV Zeta"]
    dialog._spalte_geklickt(1)
    assert spalte(1) == ["SV Zeta", "SV Mitte", "SV Alpha"]
    dialog._spalte_geklickt(3)  # Teilnehmerzahl numerisch
    assert spalte(3) == ["5", "12", "30"]
    dialog.tabelle.selectRow(2)
    assert dialog._ausgewaehlter_termin().verein == "SV Alpha"
    dialog.suche_feld.setText("bonn")
    assert spalte(1) == ["SV Mitte"]
    dialog.suche_feld.setText("")
    assert len(spalte(1)) == 3


def test_laufwerksart_erkennt_usb_stick_und_netzlaufwerk(monkeypatch):
    """Marco 10.11.2026: Hinweis, wenn der Termin auf einem USB-Stick oder Netzlaufwerk liegt."""
    import types

    import desktop_gemeinsam

    assert desktop_gemeinsam.laufwerksart("") is None
    arten = {"C:\\": 3, "E:\\": 2, "Z:\\": 4}
    attrappe = types.SimpleNamespace(
        kernel32=types.SimpleNamespace(GetDriveTypeW=lambda wurzel: arten.get(wurzel, 0)))
    monkeypatch.setattr(desktop_gemeinsam.os, "name", "nt")
    monkeypatch.setattr(desktop_gemeinsam.os.path, "abspath", lambda p: p)
    monkeypatch.setattr(desktop_gemeinsam.os.path, "splitdrive", lambda p: (p[:2], p[2:]))
    monkeypatch.setattr("ctypes.windll", attrappe, raising=False)
    assert desktop_gemeinsam.laufwerksart(r"C:\Termine\a.sqlite") is None
    assert "USB-Stick" in desktop_gemeinsam.laufwerksart(r"E:\Termine\a.sqlite")
    assert desktop_gemeinsam.laufwerksart(r"Z:\a.sqlite") == "Netzlaufwerk"
    assert desktop_gemeinsam.laufwerksart(r"\\server\freigabe\a.sqlite") == "Netzlaufwerk"
    # Langpfade: feste Platte bleibt ohne Hinweis, Stick und UNC werden erkannt
    assert desktop_gemeinsam.laufwerksart(r"\\?\C:\Termine\a.sqlite") is None
    assert "USB-Stick" in desktop_gemeinsam.laufwerksart(r"\\?\E:\Termine\a.sqlite")
    assert desktop_gemeinsam.laufwerksart(r"\\?\UNC\server\freigabe\a.sqlite") == "Netzlaufwerk"


def test_hauptfenster_auto_sicherung_nur_im_echten_lauf(qtbot, termin, tmp_path, monkeypatch):
    conn, pfad = termin
    aufrufe = []
    monkeypatch.setattr("app.auto_sicherung_erstellen", lambda c, p: aufrufe.append(p))
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    assert aufrufe == []  # Tests und Demo schreiben nichts
    fenster.auto_sicherung_aktiv = True
    fenster.auto_sicherung_anlegen()
    assert aufrufe == [pfad]
    fenster._demo_termin = True
    fenster.auto_sicherung_anlegen()
    assert aufrufe == [pfad]  # Demo-Termin wird nicht gesichert


def test_hauptfenster_sicherung_beim_beenden_ohne_abstand_und_hinweis(qtbot, termin, monkeypatch):
    import app

    conn, pfad = termin
    aufrufe = []
    monkeypatch.setattr(
        "app.auto_sicherung_erstellen", lambda c, p, **kw: aufrufe.append(kw))
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.auto_sicherung_aktiv = True
    app._auto_sicherung_beim_beenden(fenster)
    assert aufrufe == [{"mindestabstand_sekunden": 0}]  # beim Beenden immer sichern

    meldungen = []
    monkeypatch.setattr(app.QMessageBox, "information", lambda *a, **k: meldungen.append(a[1]))
    monkeypatch.setattr(app, "laufwerksart", lambda p: "USB-Stick (Wechseldatenträger)")
    fenster.laufwerk_hinweis_zeigen()
    assert len(meldungen) == 1 and "USB-Stick" in meldungen[0]
    fenster._demo_termin = True
    fenster.laufwerk_hinweis_zeigen()
    assert len(meldungen) == 1  # in der Demo kein Hinweis


def _fenster_mit_teilnehmer(qtbot, termin):
    conn, pfad = termin
    _teilnehmer_anlegen(conn, nachname="Albers", startnummer=1)
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    tab = fenster.teilnehmer_tab
    tab.show()
    tab.tabelle.selectRow(0)
    return fenster, tab


def test_beenden_fragt_nach_loeschen_solange_rueckgaengig_offen(qtbot, termin, monkeypatch):
    """Marco 12.11.2026: Rückfrage beim Beenden nur, solange ein Löschen noch zurückgenommen werden kann."""
    fenster, tab = _fenster_mit_teilnehmer(qtbot, termin)
    fragen = []
    antwort = {"ja": True}
    ueberall_ersetzen(monkeypatch, "_ja_nein", lambda parent, titel, text: fragen.append(titel) or antwort["ja"])

    # Ohne Löschen: keine Rückfrage (Wissende werden nicht genervt).
    assert fenster._beenden_vorbereiten() is True and fragen == []

    tab._teilnehmer_loeschen()  # „Teilnehmer löschen“ bestätigt (Ersatz oben)
    assert tab.loeschung_noch_rueckgaengig()
    fragen.clear()
    antwort["ja"] = False
    assert fenster._beenden_vorbereiten() is False and fragen == ["Beenden nach dem Löschen"]
    antwort["ja"] = True
    assert fenster._beenden_vorbereiten() is True

    # Beim Beenden durch Windows/Setup keine Rückfrage und kein Blockieren.
    fragen.clear()
    assert fenster._beenden_vorbereiten(rueckfrage_moeglich=False) is True and fragen == []

    # Nach „Rückgängig“ oder einer anderen Aktion ist nichts mehr offen.
    tab._rueckgaengig_ausfuehren()
    assert not tab.loeschung_noch_rueckgaengig()
    fragen.clear()
    assert fenster._beenden_vorbereiten() is True and fragen == []


def test_andere_aktion_ersetzt_geloeschten_vermerk(qtbot, termin, monkeypatch):
    fenster, tab = _fenster_mit_teilnehmer(qtbot, termin)
    ueberall_ersetzen(monkeypatch, "_ja_nein", lambda *a, **k: True)
    tab._teilnehmer_loeschen()
    assert tab.loeschung_noch_rueckgaengig()
    tab._rueckgaengig_merken("Anderes", lambda: "")
    assert not tab.loeschung_noch_rueckgaengig()


@pytest.mark.werksstandard
def test_sicherung_vor_loeschen_per_schalter(qtbot, termin, monkeypatch):
    """Marco 12.11.2026: Schalter im Menü „Einstellungen“, Standard an."""
    import desktop_gemeinsam

    fenster, tab = _fenster_mit_teilnehmer(qtbot, termin)
    aufrufe = []
    monkeypatch.setattr(fenster, "auto_sicherung_anlegen", lambda **kw: aufrufe.append(kw))
    ueberall_ersetzen(monkeypatch, "_ja_nein", lambda *a, **k: True)
    action = fenster._sicherung_vor_loeschen_action
    assert action.isCheckable() and action.isChecked()  # Standard an
    assert desktop_gemeinsam._sicherung_vor_loeschen_lesen()

    tab._teilnehmer_loeschen()
    assert aufrufe == [{"vor_loeschen": True}]

    tab._rueckgaengig_ausfuehren()
    tab.tabelle.selectRow(0)
    action.setChecked(False)  # speichert die Einstellung
    assert not desktop_gemeinsam._sicherung_vor_loeschen_lesen()
    tab._teilnehmer_loeschen()
    assert aufrufe == [{"vor_loeschen": True}]  # Schalter aus: keine weitere Sicherung


@pytest.mark.werksstandard
def test_ohne_nachfrage_menue_und_reiter_bleiben_gleich(qtbot, termin):
    """Marco 12.11.2026: „Dateien ohne Nachfrage speichern“ steht im Menü „Einstellungen“ und im
    Reiter „Ausdrucke/Export“ - beides ist dieselbe, gespeicherte Einstellung."""
    from desktop_gemeinsam import _ohne_nachfrage_lesen

    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    aktion, kaestchen = fenster._ohne_nachfrage_action, fenster.export_tab.ohne_nachfrage_check
    assert aktion.isChecked() and kaestchen.isChecked() and _ohne_nachfrage_lesen()  # Standard an

    aktion.setChecked(False)  # Menü -> Reiter und Speicher
    assert not kaestchen.isChecked() and not _ohne_nachfrage_lesen()
    kaestchen.setChecked(True)  # Reiter -> Menü und Speicher
    assert aktion.isChecked() and _ohne_nachfrage_lesen()

    kaestchen.setChecked(False)
    fenster._termin_setzen(conn, pfad)  # neue Reiter lesen die Einstellung und bleiben mit dem Menü verbunden
    neu = fenster.export_tab.ohne_nachfrage_check
    assert neu is not kaestchen and not neu.isChecked() and not aktion.isChecked()
    aktion.setChecked(True)
    assert neu.isChecked() and _ohne_nachfrage_lesen()
