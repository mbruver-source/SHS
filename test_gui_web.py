"""GUI-Tests: Web-Anbindung der Desktop-Oberfläche (desktop_web.py, Knöpfe im Reiter Datensicherung).

Das Netzwerk ist durch einen Ersatz-Client ersetzt (kein Zugriff nach außen), der Windows-Tresor durch
einen Speicher im Arbeitsspeicher; die Einstellungen (QSettings) landen dank conftest.py in einer
temporären Datei. Fixtures und Hilfen stehen in gui_hilfen.py."""

from __future__ import annotations

import os
import sqlite3
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel, QMessageBox

import desktop_web
import web_sync
from app import HauptFenster
import web_tresor
from db import get_ergebnis, list_teilnehmer
from desktop_verwaltung import DatensicherungTab
from desktop_web import WebBerichtDialog, WebEinstellungen, WebVerbindungsDialog
from gui_hilfen import *  # noqa: F401,F403
from gui_hilfen import _teilnehmer_anlegen

FINGERABDRUCK = "ab" * 32
ADRESSE = "https://shs.example.org"


@pytest.fixture(autouse=True)
def tresor(monkeypatch):
    """Windows-Tresor im Arbeitsspeicher."""
    speicher: dict[str, str] = {}
    monkeypatch.setattr(web_tresor, "_ist_windows", lambda: True)
    monkeypatch.setattr(web_tresor, "passwort_lesen", lambda adresse: speicher.get(adresse))
    monkeypatch.setattr(web_tresor, "passwort_speichern",
                        lambda adresse, benutzer, passwort: speicher.__setitem__(adresse, passwort) or True)
    monkeypatch.setattr(web_tresor, "passwort_loeschen", lambda adresse: speicher.pop(adresse, None) is None or True)
    desktop_web.passwort_vergessen()  # Passwort im Arbeitsspeicher (E4) nicht von Test zu Test mitnehmen
    yield speicher
    desktop_web.passwort_vergessen()


@pytest.fixture
def meldungen(monkeypatch):
    """Zeichnet Meldungsfenster auf; Rückfragen werden der Reihe nach aus `antworten` beantwortet (Ja,
    wenn leer)."""
    zustand = SimpleNamespace(information=[], warning=[], critical=[], fragen=[], antworten=[])

    def melden(art):
        return lambda parent, titel, text, *a, **k: getattr(zustand, art).append((titel, text))

    for art in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, art, melden(art))

    def frage(parent, titel, text, *a, **k):
        zustand.fragen.append((titel, text))
        antwort = zustand.antworten.pop(0) if zustand.antworten else True
        return QMessageBox.Yes if antwort else QMessageBox.No

    monkeypatch.setattr(QMessageBox, "question", frage)
    return zustand


@pytest.fixture
def web(monkeypatch):
    """Ersatz für web_sync.WebClient; `web` hält die Aufrufe und steuert die Antworten."""
    zustand = SimpleNamespace(
        erzeugt=[], anmeldungen=[], hochgeladen=[], geholt=[], anmelde_fehler=[],
        termine=[], ergebnisse=[], veroeffentlicht=({"schema_name": "termin_5", "anzahl_teilnehmer": 1}, None),
        ergebnisse_fehler=None,
    )

    class _Client:
        def __init__(self, adresse, fingerabdruck):
            zustand.erzeugt.append((adresse, fingerabdruck))

        def anmelden(self, benutzer, passwort):
            zustand.anmeldungen.append((benutzer, passwort))
            if zustand.anmelde_fehler:
                raise zustand.anmelde_fehler.pop(0)

        def termine(self):
            return zustand.termine

        def veroeffentlichen(self, pfad):
            verbindung = sqlite3.connect(pfad)
            try:
                namen = [z[0] for z in verbindung.execute("SELECT nachname FROM teilnehmer ORDER BY id")]
            finally:
                verbindung.close()
            zustand.hochgeladen.append((os.path.basename(pfad), pfad, namen))
            return zustand.veroeffentlicht

        def ergebnisse(self, schema):
            zustand.geholt.append(schema)
            if zustand.ergebnisse_fehler:
                raise zustand.ergebnisse_fehler
            return zustand.ergebnisse

    monkeypatch.setattr(web_sync, "WebClient", _Client)
    return zustand


@pytest.fixture
def sicherungen(monkeypatch):
    aufrufe = []
    ergebnis = {"pfad": "kopie.sqlite"}
    monkeypatch.setattr(
        desktop_web, "auto_sicherung_erstellen",
        lambda conn, pfad, **kwargs: aufrufe.append(kwargs) or ergebnis["pfad"])
    return SimpleNamespace(aufrufe=aufrufe, ergebnis=ergebnis)


@pytest.fixture
def berichte(monkeypatch):
    gezeigt = []
    monkeypatch.setattr(WebBerichtDialog, "exec", lambda dialog: gezeigt.append(dialog) or 0)
    return gezeigt


def _eingerichtet():
    desktop_web.einstellungen_speichern(WebEinstellungen(ADRESSE, "admin", FINGERABDRUCK))


def _tab(qtbot, termin, **kwargs):
    conn, pfad = termin
    tab = DatensicherungTab(aktueller_pfad=pfad, conn=conn, **kwargs)
    qtbot.addWidget(tab)
    return tab


# --- Knöpfe --------------------------------------------------------------------------------------

def test_knoepfe_sind_da_und_im_normalfall_aktiv(qtbot, termin):
    tab = _tab(qtbot, termin)
    assert tab.web_veroeffentlichen_btn.text() == "Ins Web veröffentlichen…"
    assert tab.web_holen_btn.text() == "Ergebnisse aus Web holen…"
    assert tab.web_verbindung_btn.text() == "Web-Verbindung…"
    assert tab.web_veroeffentlichen_btn.isEnabled() and tab.web_holen_btn.isEnabled()


def test_knoepfe_in_demo_und_ohne_datei_gesperrt(qtbot, termin):
    demo = _tab(qtbot, termin, demo=True)
    assert not demo.web_veroeffentlichen_btn.isEnabled() and not demo.web_holen_btn.isEnabled()
    assert "Demo" in demo.web_holen_btn.toolTip()
    ohne = DatensicherungTab(aktueller_pfad=None, conn=None)
    qtbot.addWidget(ohne)
    assert not ohne.web_veroeffentlichen_btn.isEnabled()


def test_demo_ablauf_meldet_und_ruft_nichts_auf(qtbot, termin, meldungen, web):
    tab = _tab(qtbot, termin, demo=True)
    desktop_web.termin_veroeffentlichen(tab)
    assert meldungen.information and web.erzeugt == []


def test_ergebniserfassung_nennt_den_weg_zur_web_version(qtbot, termin):
    # UX-Test Web 19.11.2026 (A5): die Web-Knöpfe wurden in der Ergebniserfassung gesucht.
    from desktop_ergebnis import ErgebnisTab
    tab = ErgebnisTab(termin[0])
    qtbot.addWidget(tab)
    assert "Reiter „Datensicherung“, Gruppe „Web-Version“" in tab.erklaerung_label.text()


def test_hauptfenster_laedt_nach_dem_holen_neu(qtbot, termin, monkeypatch):
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    aufrufe = []
    monkeypatch.setattr(fenster.ergebnis_tab, "aktualisieren", lambda: aufrufe.append("ergebnis"))
    fenster.datensicherung_tab.ergebnisse_aus_web_uebernommen.emit()
    assert aufrufe == ["ergebnis"]
    assert fenster.datensicherung_tab.web_holen_btn.isEnabled()


# --- Einstellungen -------------------------------------------------------------------------------

def test_einstellungen_und_zuordnung_runden_sich(qtbot, tmp_path):
    assert not desktop_web.einstellungen_lesen().vollstaendig()
    _eingerichtet()
    e = desktop_web.einstellungen_lesen()
    assert (e.adresse, e.benutzer, e.fingerabdruck) == (ADRESSE, "admin", FINGERABDRUCK) and e.vollstaendig()
    datei = str(tmp_path / "a.sqlite")
    assert desktop_web.zuordnung_lesen(ADRESSE, datei) is None
    desktop_web.zuordnung_speichern(ADRESSE, datei, "termin_3")
    assert desktop_web.zuordnung_lesen(ADRESSE, datei) == "termin_3"
    assert desktop_web.zuordnung_lesen(ADRESSE, str(tmp_path / "b.sqlite")) is None
    assert desktop_web.zuordnung_lesen("https://anders.example.org", datei) is None
    desktop_web.zuordnung_vergessen(ADRESSE, datei)
    assert desktop_web.zuordnung_lesen(ADRESSE, datei) is None


def test_passwort_steht_nie_in_den_einstellungen(qtbot, monkeypatch, tresor, meldungen):
    monkeypatch.setattr(web_sync, "hole_fingerabdruck", lambda adresse: FINGERABDRUCK)
    dialog = WebVerbindungsDialog(None, WebEinstellungen())
    qtbot.addWidget(dialog)
    dialog.adresse_feld.setText("shs.example.org")
    dialog.benutzer_feld.setText("admin")
    dialog.passwort_feld.setText("Geheim-123")
    dialog.fingerabdruck_btn.click()
    dialog._uebernehmen()
    from PySide6.QtCore import QSettings
    import desktop_darstellung
    einstellungen = QSettings(desktop_darstellung._SETTINGS_ORG, desktop_darstellung._SETTINGS_APP)
    assert all("Geheim-123" not in str(einstellungen.value(k)) for k in einstellungen.allKeys())
    assert tresor == {ADRESSE: "Geheim-123"}


# --- Dialog „Web-Verbindung…“ --------------------------------------------------------------------

def test_dialog_fingerabdruck_holen_bestaetigen_und_speichern(qtbot, monkeypatch, meldungen):
    monkeypatch.setattr(web_sync, "hole_fingerabdruck", lambda adresse: FINGERABDRUCK)
    dialog = WebVerbindungsDialog(None, WebEinstellungen())
    qtbot.addWidget(dialog)
    assert "Noch nicht bestätigt" in dialog.fingerabdruck_label.text()
    dialog.adresse_feld.setText("shs.example.org")
    dialog.benutzer_feld.setText("admin")
    dialog.fingerabdruck_btn.click()
    assert dialog.fingerabdruck_label.text().startswith("AB:AB:AB")
    titel, text = meldungen.fragen[0]
    assert "AB:AB" in text and "vertrauen" in text
    dialog._uebernehmen()
    assert dialog.result() == QDialog.Accepted
    e = desktop_web.einstellungen_lesen()
    assert (e.adresse, e.fingerabdruck) == (ADRESSE, FINGERABDRUCK)


def test_dialog_verlangt_https_und_fingerabdruck(qtbot, monkeypatch, meldungen):
    aufrufe = []
    monkeypatch.setattr(web_sync, "hole_fingerabdruck", lambda adresse: aufrufe.append(adresse) or FINGERABDRUCK)
    dialog = WebVerbindungsDialog(None, WebEinstellungen())
    qtbot.addWidget(dialog)
    dialog.adresse_feld.setText("http://shs.example.org")
    dialog.fingerabdruck_btn.click()
    assert aufrufe == [] and "https://" in meldungen.warning[-1][1]
    dialog.adresse_feld.setText(ADRESSE)
    dialog.benutzer_feld.setText("admin")
    dialog._uebernehmen()  # ohne Fingerabdruck
    assert dialog.result() != QDialog.Accepted and "Fingerabdruck" in meldungen.warning[-1][0]
    assert not desktop_web.einstellungen_lesen().vollstaendig()


def test_dialog_adresswechsel_verwirft_den_fingerabdruck(qtbot):
    dialog = WebVerbindungsDialog(None, WebEinstellungen(ADRESSE, "admin", FINGERABDRUCK))
    qtbot.addWidget(dialog)
    assert dialog.fingerabdruck_label.text().startswith("AB:AB")
    dialog.adresse_feld.setText("https://anderer-server.example.org")
    assert "Noch nicht bestätigt" in dialog.fingerabdruck_label.text()


def test_dialog_geaenderter_fingerabdruck_wird_deutlich_gewarnt(qtbot, monkeypatch, meldungen):
    monkeypatch.setattr(web_sync, "hole_fingerabdruck", lambda adresse: "cd" * 32)
    dialog = WebVerbindungsDialog(None, WebEinstellungen(ADRESSE, "admin", FINGERABDRUCK))
    qtbot.addWidget(dialog)
    meldungen.antworten.append(False)
    dialog.fingerabdruck_btn.click()
    assert "ANDEREN" in meldungen.fragen[0][1] and "abhört" in meldungen.fragen[0][1]
    assert dialog.fingerabdruck_label.text().startswith("AB:AB")  # abgelehnt: der alte bleibt


def test_sicherheitskorrektur_s_u14(qtbot, monkeypatch, meldungen, web, tresor):
    # Sicherheitskorrektur S-U14 (Details nach dem Release).
    _eingerichtet()
    tresor[ADRESSE] = "fuer-den-alten-server"
    monkeypatch.setattr(web_sync, "hole_fingerabdruck", lambda adresse: "cd" * 32)
    dialog = WebVerbindungsDialog(None, desktop_web.einstellungen_lesen())
    qtbot.addWidget(dialog)
    assert "gespeichert" in dialog.passwort_feld.placeholderText()
    dialog.fingerabdruck_btn.click()  # Warnung mit Ja beantwortet
    assert ADRESSE not in tresor
    assert "neu eingeben" in dialog.status_label.text()
    assert dialog.passwort_feld.placeholderText() == ""
    dialog.test_btn.click()  # ohne Eingabe keine Anmeldung
    assert web.anmeldungen == []


def test_gleicher_fingerabdruck_behaelt_das_tresor_passwort(qtbot, monkeypatch, meldungen, tresor):
    _eingerichtet()
    tresor[ADRESSE] = "bleibt"
    # gleicher Fingerabdruck, nur anders geschrieben
    monkeypatch.setattr(web_sync, "hole_fingerabdruck", lambda adresse: FINGERABDRUCK)
    dialog = WebVerbindungsDialog(None, WebEinstellungen(ADRESSE, "admin", ":".join(["AB"] * 32)))
    qtbot.addWidget(dialog)
    dialog.fingerabdruck_btn.click()
    assert tresor == {ADRESSE: "bleibt"}
    assert "neu eingeben" not in dialog.status_label.text()


def test_neuer_fingerabdruck_nach_adresse_hin_und_zurueck(qtbot, monkeypatch, meldungen, tresor):
    _eingerichtet()
    tresor[ADRESSE] = "fuer-den-alten-server"
    monkeypatch.setattr(web_sync, "hole_fingerabdruck", lambda adresse: "cd" * 32)
    dialog = WebVerbindungsDialog(None, desktop_web.einstellungen_lesen())
    qtbot.addWidget(dialog)
    dialog.adresse_feld.setText("https://anderer-server.example.org")
    dialog.adresse_feld.setText(ADRESSE)
    dialog.fingerabdruck_btn.click()
    assert "ANDEREN" in meldungen.fragen[-1][1]  # gegen den gespeicherten verglichen
    assert ADRESSE not in tresor
    dialog.reject()  # Abbrechen: Tresor bleibt leer, Einstellungen behalten den alten Fingerabdruck
    assert desktop_web.einstellungen_lesen().fingerabdruck == FINGERABDRUCK


def test_neuer_fingerabdruck_nicht_uebernommen_wenn_tresor_nicht_loescht(qtbot, monkeypatch, meldungen, tresor):
    _eingerichtet()
    tresor[ADRESSE] = "fuer-den-alten-server"
    monkeypatch.setattr(web_tresor, "passwort_loeschen", lambda adresse: False)
    monkeypatch.setattr(web_sync, "hole_fingerabdruck", lambda adresse: "cd" * 32)
    dialog = WebVerbindungsDialog(None, desktop_web.einstellungen_lesen())
    qtbot.addWidget(dialog)
    dialog.fingerabdruck_btn.click()
    assert meldungen.warning and "nicht übernommen" in meldungen.warning[-1][1]
    assert dialog.fingerabdruck_label.text().startswith("AB:AB")
    # QS U19: auch „Gespeichertes Passwort vergessen“ meldet das Scheitern ehrlich statt „entfernt“
    dialog.vergessen_btn.click()
    assert "ließ sich nicht" in dialog.status_label.text()
    assert "entfernt." not in dialog.status_label.text()


def test_tresor_eintrag_ohne_bekannten_fingerabdruck_wird_entfernt(qtbot, monkeypatch, meldungen, tresor):
    desktop_web.einstellungen_speichern(WebEinstellungen("https://anderer-server.example.org", "admin", FINGERABDRUCK))
    tresor[ADRESSE] = "rest-von-frueher"
    monkeypatch.setattr(web_sync, "hole_fingerabdruck", lambda adresse: "cd" * 32)
    dialog = WebVerbindungsDialog(None, WebEinstellungen(ADRESSE, "admin", ""))
    qtbot.addWidget(dialog)
    dialog.fingerabdruck_btn.click()
    assert ADRESSE not in tresor
    assert "neu eingeben" in dialog.status_label.text()


def test_neuer_fingerabdruck_ohne_tresor(qtbot, monkeypatch, meldungen):
    monkeypatch.setattr(web_tresor, "_ist_windows", lambda: False)
    _eingerichtet()
    monkeypatch.setattr(web_sync, "hole_fingerabdruck", lambda adresse: "cd" * 32)
    dialog = WebVerbindungsDialog(None, desktop_web.einstellungen_lesen())
    qtbot.addWidget(dialog)
    dialog.fingerabdruck_btn.click()
    assert dialog.fingerabdruck_label.text().startswith("CD:CD")
    assert dialog.status_label.text() == "Fingerabdruck bestätigt. Mit „OK“ speichern."


def test_neuer_fingerabdruck_abgelehnt_behaelt_das_tresor_passwort(qtbot, monkeypatch, meldungen, tresor):
    _eingerichtet()
    tresor[ADRESSE] = "bleibt"
    monkeypatch.setattr(web_sync, "hole_fingerabdruck", lambda adresse: "cd" * 32)
    dialog = WebVerbindungsDialog(None, desktop_web.einstellungen_lesen())
    qtbot.addWidget(dialog)
    meldungen.antworten.append(False)
    dialog.fingerabdruck_btn.click()
    assert tresor == {ADRESSE: "bleibt"}


def test_dialog_testen_vergessen_und_fehler(qtbot, monkeypatch, meldungen, web, tresor):
    dialog = WebVerbindungsDialog(None, WebEinstellungen(ADRESSE, "admin", FINGERABDRUCK))
    qtbot.addWidget(dialog)
    dialog.test_btn.click()  # ohne Passwort
    assert meldungen.warning and web.erzeugt == []
    web.termine = [{"schema_name": "termin_1"}]
    dialog.passwort_feld.setText("pw-test")
    dialog.test_btn.click()
    assert web.anmeldungen == [("admin", "pw-test")]
    assert "in Ordnung" in dialog.status_label.text() and "1 Termin" in dialog.status_label.text()
    web.anmelde_fehler.append(web_sync.AnmeldeFehler("Benutzername oder Passwort falsch", 401))
    dialog.test_btn.click()
    assert "fehlgeschlagen" in dialog.status_label.text() and "falsch" in meldungen.warning[-1][1]
    tresor[ADRESSE] = "gemerkt"
    dialog.vergessen_btn.click()
    assert ADRESSE not in tresor


def test_dialog_ohne_tresor_bietet_kein_merken_an(qtbot, monkeypatch):
    monkeypatch.setattr(web_tresor, "_ist_windows", lambda: False)
    dialog = WebVerbindungsDialog(None, WebEinstellungen())
    qtbot.addWidget(dialog)
    assert not dialog.merken_check.isEnabled() and not dialog.merken_check.isChecked()


def _dialog_passt(dialog, qapp):
    """Nichts abgeschnitten: kein waagerechter Bildlauf nötig, umbrechende Beschriftungen haben ihre volle
    Höhe, OK/Abbrechen liegen im Dialog, und der Dialog passt auf den Bildschirm."""
    dialog.show()
    qapp.processEvents()
    assert dialog._inhalt.minimumSizeHint().width() <= dialog._scroll.viewport().width()
    for label in dialog.findChildren(QLabel):
        if label.text() and label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width()) - 2, label.text()
    assert dialog.fingerabdruck_label.wordWrap()
    frei = qapp.primaryScreen().availableGeometry()
    assert dialog.width() <= frei.width() and dialog.height() <= frei.height()
    knoepfe = dialog.findChild(QDialogButtonBox)
    assert dialog.rect().contains(knoepfe.geometry())


@pytest.mark.parametrize("stufe", ["normal", "gross", "sehr_gross"])
def test_dialog_bei_schriftstufen_nichts_abgeschnitten(qtbot, darstellung_speicher, stufe):
    """Mit der Schriftstufen-Mechanik des Projekts (Ansicht -> Schriftgröße)."""
    import desktop_darstellung

    qapp = QApplication.instance()
    darstellung_speicher["schrift"] = stufe
    desktop_darstellung._darstellung_anwenden(qapp)
    dialog = WebVerbindungsDialog(None, WebEinstellungen(ADRESSE, "admin", FINGERABDRUCK))
    qtbot.addWidget(dialog)
    _dialog_passt(dialog, qapp)


@pytest.mark.parametrize("ohne_tresor", [False, True])
@pytest.mark.parametrize("faktor", [1.0, 1.3, 1.6, 2.0])
def test_dialog_bei_grosser_schrift_nichts_abgeschnitten(qtbot, monkeypatch, faktor, ohne_tresor):
    if ohne_tresor:  # zusätzliche Erklärung unter dem Haken (UX-Test Web 19.11.2026, E6)
        monkeypatch.setattr(web_tresor, "_ist_windows", lambda: False)
    qapp = QApplication.instance()
    vorher = qapp.font()
    schrift = qapp.font()
    schrift.setPointSizeF(vorher.pointSizeF() * faktor)
    qapp.setFont(schrift)
    try:
        dialog = WebVerbindungsDialog(None, WebEinstellungen(ADRESSE, "admin", FINGERABDRUCK))
        qtbot.addWidget(dialog)
        _dialog_passt(dialog, qapp)
    finally:
        qapp.setFont(vorher)


@pytest.mark.parametrize("faktor", [1.0, 2.0])
def test_passwortabfrage_ohne_tresor_bricht_den_hinweis_um(qtbot, monkeypatch, faktor):
    monkeypatch.setattr(web_tresor, "_ist_windows", lambda: False)
    qapp = QApplication.instance()
    vorher = qapp.font()
    schrift = qapp.font()
    schrift.setPointSizeF(vorher.pointSizeF() * faktor)
    qapp.setFont(schrift)
    try:
        dialog = desktop_web._PasswortDialog(None, "admin", ADRESSE)
        qtbot.addWidget(dialog)
        dialog.show()
        qapp.processEvents()
        hinweis = dialog.behalten_hinweis
        assert hinweis.wordWrap() and hinweis.height() >= hinweis.heightForWidth(hinweis.width()) - 2
        frei = qapp.primaryScreen().availableGeometry()
        assert dialog.width() <= frei.width()
    finally:
        qapp.setFont(vorher)


# --- Ins Web veröffentlichen ---------------------------------------------------------------------

def test_veroeffentlichen_laedt_kopie_hoch_und_merkt_zuordnung(qtbot, termin, web, meldungen, tresor):
    conn, pfad = termin
    _teilnehmer_anlegen(conn, nachname="Muster", startnummer=1)
    _teilnehmer_anlegen(conn, nachname="Zweiter", startnummer=2)
    _eingerichtet()
    tresor[ADRESSE] = "pw-gespeichert"
    web.veroeffentlicht = ({"schema_name": "termin_9", "anzahl_teilnehmer": 2}, "Am selben Datum gibt es schon einen Termin.")
    tab = _tab(qtbot, termin)

    desktop_web.termin_veroeffentlichen(tab)

    assert web.erzeugt == [(ADRESSE, FINGERABDRUCK)]
    assert web.anmeldungen == [("admin", "pw-gespeichert")]
    name, kopie_pfad, namen = web.hochgeladen[0]
    assert name == "termin.sqlite" and namen == ["Muster", "Zweiter"]
    assert not os.path.exists(kopie_pfad), "Die temporäre Kopie muss danach gelöscht sein"
    assert "2 Teilnehmer samt" in meldungen.fragen[0][1] and ADRESSE in meldungen.fragen[0][1]
    assert "teilnehmende Teilnehmer" not in meldungen.fragen[0][1]  # UX-Test Web 19.11.2026, E3
    assert desktop_web.zuordnung_lesen(ADRESSE, pfad) == "termin_9"
    titel, text = meldungen.warning[0]
    assert "selben Datum" in text and "bitte beachten" in titel
    assert "veröffentlicht" in tab.status_label.text()


def test_veroeffentlichen_nennt_nicht_teilnehmende(qtbot, termin, web, meldungen):
    from db import setze_keine_teilnahme
    conn, pfad = termin
    _teilnehmer_anlegen(conn, nachname="Da", startnummer=1)
    fehlt = _teilnehmer_anlegen(conn, nachname="Fehlt", startnummer=2)
    setze_keine_teilnahme(conn, fehlt, True)
    _eingerichtet()
    meldungen.antworten.append(False)
    desktop_web.termin_veroeffentlichen(_tab(qtbot, termin))
    assert "1 Teilnehmer samt" in meldungen.fragen[0][1] and "(1)" in meldungen.fragen[0][1]
    assert web.erzeugt == []  # „Nein“: nichts gesendet


def test_veroeffentlichen_fragt_passwort_und_merkt_es(qtbot, termin, web, meldungen, tresor, monkeypatch):
    _teilnehmer_anlegen(termin[0], startnummer=1)
    _eingerichtet()

    def exec_(dialog):
        dialog.passwort_feld.setText("neu-eingegeben")
        dialog.merken_check.setChecked(True)
        return QDialog.Accepted

    monkeypatch.setattr(desktop_web._PasswortDialog, "exec", exec_)
    desktop_web.termin_veroeffentlichen(_tab(qtbot, termin))
    assert web.anmeldungen == [("admin", "neu-eingegeben")]
    assert tresor == {ADRESSE: "neu-eingegeben"}


# --- Passwort im Arbeitsspeicher bis Programmende (UX-Test Web 19.11.2026, E4) -------------------

def _passwort_abfrage_zaehlen(monkeypatch, passwort="nur-im-speicher", merken=False):
    abfragen = []

    def exec_(dialog):
        abfragen.append(dialog)
        dialog.passwort_feld.setText(passwort)
        dialog.merken_check.setChecked(merken)
        return QDialog.Accepted

    monkeypatch.setattr(desktop_web._PasswortDialog, "exec", exec_)
    return abfragen


def test_passwort_ohne_merken_wird_bis_programmende_behalten(qtbot, termin, web, meldungen, tresor, monkeypatch):
    _teilnehmer_anlegen(termin[0], startnummer=1)
    _eingerichtet()
    abfragen = _passwort_abfrage_zaehlen(monkeypatch)
    desktop_web.termin_veroeffentlichen(_tab(qtbot, termin))
    desktop_web.termin_veroeffentlichen(_tab(qtbot, termin))
    assert len(abfragen) == 1  # beim zweiten Mal nicht erneut gefragt
    assert [a[1] for a in web.anmeldungen] == ["nur-im-speicher", "nur-im-speicher"]
    assert tresor == {}  # nie im Tresor


def test_passwort_im_speicher_gilt_nur_fuer_dieselbe_verbindung(qtbot, termin, web, meldungen, tresor, monkeypatch):
    _teilnehmer_anlegen(termin[0], startnummer=1)
    _eingerichtet()
    abfragen = _passwort_abfrage_zaehlen(monkeypatch)
    desktop_web.termin_veroeffentlichen(_tab(qtbot, termin))
    # anderer Fingerabdruck (z. B. neues Zertifikat bestätigt): das gemerkte Passwort gilt nicht mehr
    desktop_web.einstellungen_speichern(WebEinstellungen(ADRESSE, "admin", "cd" * 32))
    desktop_web.termin_veroeffentlichen(_tab(qtbot, termin))
    desktop_web.einstellungen_speichern(WebEinstellungen(ADRESSE, "anderer", FINGERABDRUCK))
    desktop_web.termin_veroeffentlichen(_tab(qtbot, termin))
    assert len(abfragen) == 3


def test_passwort_im_speicher_wird_bei_401_und_terminwechsel_vergessen(qtbot, termin, web, meldungen, tresor, monkeypatch):
    _teilnehmer_anlegen(termin[0], startnummer=1)
    _eingerichtet()
    abfragen = _passwort_abfrage_zaehlen(monkeypatch)
    desktop_web.termin_veroeffentlichen(_tab(qtbot, termin))
    web.anmelde_fehler.append(web_sync.AnmeldeFehler("Anmeldung abgelehnt", 401))  # z. B. Passwort geändert
    desktop_web.termin_veroeffentlichen(_tab(qtbot, termin))
    assert len(abfragen) == 2
    assert desktop_web._passwort_aus_speicher(desktop_web.einstellungen_lesen()) == "nur-im-speicher"
    # Terminwechsel im Hauptfenster (app._termin_setzen) verwirft es
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    assert desktop_web._passwort_aus_speicher(desktop_web.einstellungen_lesen()) is None


def test_im_dialog_eingetipptes_passwort_wird_nicht_erneut_abgefragt(qtbot, termin, web, meldungen, tresor, monkeypatch):
    monkeypatch.setattr(web_sync, "hole_fingerabdruck", lambda adresse: FINGERABDRUCK)
    dialog = WebVerbindungsDialog(None, WebEinstellungen())
    qtbot.addWidget(dialog)
    dialog.adresse_feld.setText(ADRESSE)
    dialog.benutzer_feld.setText("admin")
    dialog.passwort_feld.setText("aus-dem-dialog")
    dialog.merken_check.setChecked(False)
    dialog.fingerabdruck_btn.click()
    dialog._uebernehmen()
    assert tresor == {}
    _teilnehmer_anlegen(termin[0], startnummer=1)
    abfragen = _passwort_abfrage_zaehlen(monkeypatch)
    desktop_web.termin_veroeffentlichen(_tab(qtbot, termin))
    assert abfragen == [] and web.anmeldungen == [("admin", "aus-dem-dialog")]
    # Der Dialog zeigt es als gemerkt an; „vergessen“ verwirft es auch im Arbeitsspeicher.
    dialog2 = WebVerbindungsDialog(None, desktop_web.einstellungen_lesen())
    qtbot.addWidget(dialog2)
    assert "bis zum Beenden gemerkt" in dialog2.passwort_feld.placeholderText()
    dialog2.vergessen_btn.click()
    assert desktop_web._passwort_aus_speicher(desktop_web.einstellungen_lesen()) is None


def test_passwort_im_speicher_steht_nicht_in_meldungen_und_einstellungen(qtbot, termin, web, meldungen, tresor, monkeypatch):
    _teilnehmer_anlegen(termin[0], startnummer=1)
    _eingerichtet()
    _passwort_abfrage_zaehlen(monkeypatch, passwort="Geheim-xyz")
    desktop_web.termin_veroeffentlichen(_tab(qtbot, termin))  # gemerkt (nur Arbeitsspeicher)
    web.anmelde_fehler.append(RuntimeError("Serverfehler"))
    desktop_web.termin_veroeffentlichen(_tab(qtbot, termin))
    alle = [t for art in (meldungen.information, meldungen.warning, meldungen.critical) for _, t in art]
    assert alle and all("Geheim-xyz" not in t for t in alle)
    from PySide6.QtCore import QSettings
    import desktop_darstellung
    einstellungen = QSettings(desktop_darstellung._SETTINGS_ORG, desktop_darstellung._SETTINGS_APP)
    assert all("Geheim-xyz" not in str(einstellungen.value(k)) for k in einstellungen.allKeys())
    assert tresor == {}


def test_abgelehntes_passwort_bleibt_nach_abbruch_vergessen(qtbot, termin, web, meldungen, tresor, monkeypatch):
    _teilnehmer_anlegen(termin[0], startnummer=1)
    _eingerichtet()
    _passwort_abfrage_zaehlen(monkeypatch)
    desktop_web.termin_veroeffentlichen(_tab(qtbot, termin))
    web.anmelde_fehler.append(web_sync.AnmeldeFehler("Anmeldung abgelehnt", 401))
    monkeypatch.setattr(desktop_web._PasswortDialog, "exec", lambda dialog: QDialog.Rejected)  # Abbrechen
    desktop_web.termin_veroeffentlichen(_tab(qtbot, termin))
    assert desktop_web._passwort_aus_speicher(desktop_web.einstellungen_lesen()) is None


def _dialog_mit_gemerktem_passwort(qtbot, monkeypatch, passwort="gemerkt-1"):
    monkeypatch.setattr(web_tresor, "_ist_windows", lambda: False)  # ohne Tresor: nur Arbeitsspeicher
    e = WebEinstellungen(ADRESSE, "admin", FINGERABDRUCK)
    desktop_web.einstellungen_speichern(e)
    desktop_web._passwort_merken(e, passwort)
    dialog = WebVerbindungsDialog(None, e)
    qtbot.addWidget(dialog)
    return dialog


def test_uebernehmen_behaelt_gemerktes_bei_gleicher_verbindung(qtbot, monkeypatch):
    dialog = _dialog_mit_gemerktem_passwort(qtbot, monkeypatch)
    assert "bis zum Beenden gemerkt" in dialog.passwort_feld.placeholderText()
    dialog._uebernehmen()
    assert desktop_web._passwort_aus_speicher(desktop_web.einstellungen_lesen()) == "gemerkt-1"
    assert desktop_web.passwort_im_speicher()
    desktop_web.passwort_vergessen()
    assert not desktop_web.passwort_im_speicher()


def test_uebernehmen_verwirft_gemerktes_bei_anderem_benutzer(qtbot, monkeypatch):
    dialog = _dialog_mit_gemerktem_passwort(qtbot, monkeypatch)
    dialog.benutzer_feld.setText("jemand-anders")
    assert dialog.passwort_feld.placeholderText() == ""  # Platzhalter folgt der Eingabe
    assert not dialog.passwort_hinweis.isHidden()
    dialog._uebernehmen()
    e = desktop_web.einstellungen_lesen()
    assert e.benutzer == "jemand-anders"
    assert desktop_web._passwort_aus_speicher(e) is None
    assert not desktop_web.passwort_im_speicher()


def test_verbindungstest_mit_abgelehntem_gemerkten_passwort_vergisst_es(qtbot, monkeypatch, meldungen, web):
    dialog = _dialog_mit_gemerktem_passwort(qtbot, monkeypatch)
    web.anmelde_fehler.append(web_sync.AnmeldeFehler("Benutzername oder Passwort falsch", 401))
    dialog.test_btn.click()
    assert web.anmeldungen == [("admin", "gemerkt-1")]
    assert not desktop_web.passwort_im_speicher()
    assert dialog.passwort_feld.placeholderText() == ""


def test_dialog_hinweis_bei_leerem_passwort_und_ohne_tresor(qtbot, monkeypatch):
    # Heinz F5: Hinweis, wenn kein Passwort eingetragen und keines bekannt ist; E6: sichtbare Erklärung
    dialog = WebVerbindungsDialog(None, WebEinstellungen(ADRESSE, "admin", FINGERABDRUCK))
    qtbot.addWidget(dialog)
    assert not dialog.passwort_hinweis.isHidden()
    dialog.passwort_feld.setText("x")
    assert dialog.passwort_hinweis.isHidden()
    # Mit Tresor und gesetztem Haken kein Hinweis; wird der Haken abgewählt, steht da, dass das Passwort
    # bis zum Beenden behalten wird (Sicherheitsprüfung U8, G-1).
    assert dialog.behalten_hinweis.isHidden()
    dialog.merken_check.setChecked(False)
    assert not dialog.behalten_hinweis.isHidden() and "bis zum Beenden" in dialog.behalten_hinweis.text()
    monkeypatch.setattr(web_tresor, "_ist_windows", lambda: False)
    ohne = WebVerbindungsDialog(None, WebEinstellungen(ADRESSE, "admin", FINGERABDRUCK))
    qtbot.addWidget(ohne)
    assert "nicht möglich" in ohne.merken_check.text()
    assert "keinen Windows-Tresor" in ohne.behalten_hinweis.text() and not ohne.behalten_hinweis.isHidden()
    abfrage = desktop_web._PasswortDialog(None, "admin", ADRESSE)
    qtbot.addWidget(abfrage)
    assert not abfrage.behalten_hinweis.isHidden()


def test_tresor_passwort_wird_nicht_zusaetzlich_im_speicher_gehalten(qtbot, termin, web, meldungen, tresor, monkeypatch):
    # Sicherheitsprüfung U8, G-2: keine zweite, langlebige Kopie eines Tresor-Passworts.
    _teilnehmer_anlegen(termin[0], startnummer=1)
    _eingerichtet()
    tresor[ADRESSE] = "aus-dem-tresor"
    desktop_web.termin_veroeffentlichen(_tab(qtbot, termin))
    assert web.anmeldungen == [("admin", "aus-dem-tresor")]
    assert not desktop_web.passwort_im_speicher()
    del tresor[ADRESSE]
    _passwort_abfrage_zaehlen(monkeypatch, passwort="neu-im-tresor", merken=True)
    desktop_web.termin_veroeffentlichen(_tab(qtbot, termin))
    assert tresor == {ADRESSE: "neu-im-tresor"} and not desktop_web.passwort_im_speicher()


def test_sitzung_behaelt_die_herkunft_des_passworts(qtbot, termin, web, meldungen, tresor, monkeypatch):
    # QS U13 (Nachbesserung zu U8, siehe Fortschritt.md)
    _eingerichtet()
    tresor[ADRESSE] = "aus-dem-tresor"
    parent = _tab(qtbot, termin)
    sitzung = desktop_web._Sitzung()
    for _ in range(2):
        ok, _erg = desktop_web.mit_web_anmeldung(parent, lambda client: None, "Test", sitzung)
        assert ok
        assert not desktop_web.passwort_im_speicher()
    assert web.anmeldungen == [("admin", "aus-dem-tresor")] * 2
    # eben im Dialog eingegeben und in den Tresor gelegt
    del tresor[ADRESSE]
    _passwort_abfrage_zaehlen(monkeypatch, passwort="neu-im-tresor", merken=True)
    sitzung = desktop_web._Sitzung()
    for _ in range(2):
        assert desktop_web.mit_web_anmeldung(parent, lambda client: None, "Test", sitzung)[0]
        assert not desktop_web.passwort_im_speicher()
    assert tresor == {ADRESSE: "neu-im-tresor"}
    # abgelehnt im zweiten Aufruf: der Tresor-Eintrag wird verworfen
    web.anmelde_fehler.append(web_sync.AnmeldeFehler("Benutzername oder Passwort falsch", 401))
    _passwort_abfrage_zaehlen(monkeypatch, passwort="danach-eingegeben", merken=False)
    assert desktop_web.mit_web_anmeldung(parent, lambda client: None, "Test", sitzung)[0]
    assert ADRESSE not in tresor


def test_verbindungstest_401_verwirft_das_tresor_passwort(qtbot, meldungen, web, tresor):
    # Sicherheitsprüfung U8, H-1: das abgelehnte Passwort wird dort verworfen, woher es kam.
    tresor[ADRESSE] = "falsch-im-tresor"
    dialog = WebVerbindungsDialog(None, WebEinstellungen(ADRESSE, "admin", FINGERABDRUCK))
    qtbot.addWidget(dialog)
    web.anmelde_fehler.append(web_sync.AnmeldeFehler("Benutzername oder Passwort falsch", 401))
    dialog.test_btn.click()
    assert ADRESSE not in tresor
    assert dialog.passwort_feld.placeholderText() == ""


def test_verbindungstest_401_nach_anmeldung_verwirft_nichts(qtbot, meldungen, web, tresor, monkeypatch):
    tresor[ADRESSE] = "richtig"
    dialog = WebVerbindungsDialog(None, WebEinstellungen(ADRESSE, "admin", FINGERABDRUCK))
    qtbot.addWidget(dialog)
    monkeypatch.setattr(web_sync.WebClient, "termine",
                        lambda self: (_ for _ in ()).throw(web_sync.AnmeldeFehler("Sitzung abgelaufen", 401)))
    dialog.test_btn.click()
    assert tresor == {ADRESSE: "richtig"}


def test_dialog_nimmt_nach_fehlgriff_weiter_eingaben_an(qtbot):
    # E5 nachgestellt: Passwort versehentlich ins Feld Benutzername, dann korrigiert (Tastatur).
    from PySide6.QtCore import Qt
    dialog = WebVerbindungsDialog(None, WebEinstellungen())
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.keyClicks(dialog.benutzer_feld, "Geheim-123")
    dialog.benutzer_feld.selectAll()
    qtbot.keyClick(dialog.benutzer_feld, Qt.Key_Backspace)
    qtbot.keyClicks(dialog.benutzer_feld, "admin")
    qtbot.keyClicks(dialog.passwort_feld, "Geheim-123")
    qtbot.keyClicks(dialog.adresse_feld, "https://shs.example.org")
    assert dialog.benutzer_feld.text() == "admin"
    assert dialog.passwort_feld.text() == "Geheim-123"
    assert dialog.adresse_feld.text() == "https://shs.example.org"
    assert dialog.benutzer_feld.isEnabled() and dialog.passwort_feld.isEnabled()


def test_falsches_gespeichertes_passwort_wird_vergessen_und_neu_erfragt(qtbot, termin, web, meldungen, tresor, monkeypatch):
    _teilnehmer_anlegen(termin[0], startnummer=1)
    _eingerichtet()
    tresor[ADRESSE] = "alt-und-falsch"
    web.anmelde_fehler.append(web_sync.AnmeldeFehler("Anmeldung abgelehnt", 401))
    texte = []

    def exec_(dialog):
        texte.append(dialog.findChildren(QLabel)[0].text())
        dialog.passwort_feld.setText("richtig")
        dialog.merken_check.setChecked(False)
        return QDialog.Accepted

    monkeypatch.setattr(desktop_web._PasswortDialog, "exec", exec_)
    desktop_web.termin_veroeffentlichen(_tab(qtbot, termin))
    assert [a[1] for a in web.anmeldungen] == ["alt-und-falsch", "richtig"]
    assert "vergessen" in texte[0]
    assert ADRESSE not in tresor  # das falsche ist weg, das neue wurde nicht gemerkt


def test_zertifikatsfehler_wird_als_warnung_gezeigt_und_bricht_ab(qtbot, termin, web, meldungen, tresor):
    _teilnehmer_anlegen(termin[0], startnummer=1)
    _eingerichtet()
    tresor[ADRESSE] = "pw"
    web.anmelde_fehler.append(web_sync.ZertifikatFehler("ACHTUNG: Zertifikat stimmt nicht. NICHTS gesendet."))
    tab = _tab(qtbot, termin)
    desktop_web.termin_veroeffentlichen(tab)
    assert meldungen.critical and "ACHTUNG" in meldungen.critical[0][1]
    assert web.hochgeladen == [] and desktop_web.zuordnung_lesen(ADRESSE, tab.aktueller_pfad) is None


def test_ohne_einrichtung_wird_die_verbindung_abgefragt(qtbot, termin, web, meldungen, monkeypatch):
    _teilnehmer_anlegen(termin[0], startnummer=1)
    monkeypatch.setattr(WebVerbindungsDialog, "exec", lambda dialog: QDialog.Rejected)
    desktop_web.termin_veroeffentlichen(_tab(qtbot, termin))
    assert meldungen.information and "Fingerabdruck" in meldungen.information[0][1]
    assert web.erzeugt == [] and meldungen.fragen == []


# --- Ergebnisse aus Web holen --------------------------------------------------------------------

def _web_eintrag(conn, ergebnis):
    return dict(list_teilnehmer(conn)[0], ergebnis=ergebnis)


def test_holen_mit_zuordnung_sichert_vorher_und_arbeitet_ein(qtbot, termin, web, meldungen, sicherungen, berichte, tresor):
    conn, pfad = termin
    teilnehmer_id = _teilnehmer_anlegen(conn, startnummer=1)
    _eingerichtet()
    tresor[ADRESSE] = "pw"
    desktop_web.zuordnung_speichern(ADRESSE, pfad, "termin_9")
    web.ergebnisse = [_web_eintrag(conn, {"suche_flaechensuche": 50, "anzeige_flaechensuche": 30})]
    tab = _tab(qtbot, termin)
    signale = []
    tab.ergebnisse_aus_web_uebernommen.connect(lambda: signale.append(1))

    assert desktop_web.ergebnisse_aus_web_holen(tab) is True

    assert web.geholt == ["termin_9"]
    assert sicherungen.aufrufe == [{"mindestabstand_sekunden": 0}]
    ergebnis = get_ergebnis(conn, teilnehmer_id)
    assert (ergebnis["suche_flaechensuche"], ergebnis["anzeige_flaechensuche"]) == (50, 30)
    assert signale == [1]
    assert len(berichte) == 1 and "1 Teilnehmer geändert, 0 unverändert" in berichte[0].findChildren(QLabel)[0].text()
    assert "Das gilt auch für Disqualifikation und Abbruch" in meldungen.fragen[0][1]
    assert "überschrieben" in meldungen.fragen[0][1]
    # E3: keine interne Kennung in der Rückfrage; ohne Terminliste ein verständlicher Ersatz
    assert "termin_9" not in meldungen.fragen[0][1]
    assert "zuletzt veröffentlichter Termin dieser Datei" in meldungen.fragen[0][1]


def test_zweites_holen_ohne_aenderung_behaelt_die_zuordnung(qtbot, termin, web, meldungen, sicherungen, berichte, tresor):
    # Verifikation U9: Ohne neue Web-Änderung ist „aktualisiert“ 0; weicht dabei ein Teilnehmer ab, darf
    # das nicht als „es passte kein Teilnehmer“ gelten (die übrigen passen, nur unverändert).
    conn, pfad = termin
    _teilnehmer_anlegen(conn, nachname="Muster", startnummer=1)
    _teilnehmer_anlegen(conn, nachname="Zweiter", startnummer=2)
    _eingerichtet()
    tresor[ADRESSE] = "pw"
    desktop_web.zuordnung_speichern(ADRESSE, pfad, "termin_9")
    passend, abweichend = list_teilnehmer(conn)
    web.ergebnisse = [dict(passend, ergebnis={}), dict(abweichend, nachname="Ganz anders", ergebnis={})]
    tab = _tab(qtbot, termin)
    assert desktop_web.ergebnisse_aus_web_holen(tab) is True
    assert desktop_web.zuordnung_lesen(ADRESSE, pfad) == "termin_9"
    assert tab.status_label.text() == "Ergebnisse aus dem Web übernommen: 0 Teilnehmer geändert, 1 unverändert."


def test_holen_ersatztext_wenn_die_terminliste_scheitert(qtbot, termin, web, meldungen, sicherungen, berichte, tresor, monkeypatch):
    conn, pfad = termin
    _teilnehmer_anlegen(conn, startnummer=1)
    _eingerichtet()
    tresor[ADRESSE] = "pw"
    desktop_web.zuordnung_speichern(ADRESSE, pfad, "termin_9")
    web.ergebnisse = [_web_eintrag(conn, {"suche_flaechensuche": 50, "anzeige_flaechensuche": 30})]
    monkeypatch.setattr(web_sync.WebClient, "termine",
                        lambda self: (_ for _ in ()).throw(web_sync.ServerFehler("kaputt", 500)))
    assert desktop_web.ergebnisse_aus_web_holen(_tab(qtbot, termin)) is True
    assert "„zuletzt veröffentlichter Termin dieser Datei“" in meldungen.fragen[0][1]


def test_holen_nennt_den_gemerkten_termin_mit_namen(qtbot, termin, web, meldungen, sicherungen, berichte, tresor):
    # UX-Test Web 19.11.2026 (E3): statt „gemerkter Termin [termin_9]“ Verein, Ort und Datum.
    conn, pfad = termin
    _teilnehmer_anlegen(conn, startnummer=1)
    _eingerichtet()
    tresor[ADRESSE] = "pw"
    desktop_web.zuordnung_speichern(ADRESSE, pfad, "termin_9")
    web.termine = [{"schema_name": "termin_9", "verein": "Musterverein", "ort": "Musterstadt",
                    "datum": "2026-11-14", "anzahl_teilnehmer": 1}]
    web.ergebnisse = [_web_eintrag(conn, {"suche_flaechensuche": 50, "anzeige_flaechensuche": 30})]
    assert desktop_web.ergebnisse_aus_web_holen(_tab(qtbot, termin)) is True
    assert "„Musterverein, Musterstadt, 14.11.2026“" in meldungen.fragen[0][1]
    assert len(web.anmeldungen) == 1  # Ergebnisse und Terminliste in einer Anmeldung


def test_holen_ohne_zuordnung_bietet_terminliste_an(qtbot, termin, web, meldungen, sicherungen, berichte, tresor, monkeypatch):
    conn, pfad = termin
    _teilnehmer_anlegen(conn, startnummer=1)
    _eingerichtet()
    tresor[ADRESSE] = "pw"
    web.termine = [
        {"schema_name": "termin_1", "verein": "Anderer", "ort": "X", "datum": "2026-01-01", "anzahl_teilnehmer": 4},
        {"schema_name": "termin_2", "verein": "Mein Verein", "ort": "Y", "datum": "2026-12-12", "anzahl_teilnehmer": 7},
    ]
    from db import set_veranstaltung
    set_veranstaltung(conn, verein="Mein Verein", datum="2026-12-12")
    web.ergebnisse = [_web_eintrag(conn, {"suche_flaechensuche": 50, "anzeige_flaechensuche": 30})]
    angebot = {}

    def getitem(parent, titel, text, items, current, editable):
        angebot.update(items=items, current=current)
        return items[1], True

    monkeypatch.setattr(desktop_web.QInputDialog, "getItem", getitem)
    tab = _tab(qtbot, termin)

    assert desktop_web.ergebnisse_aus_web_holen(tab) is True

    assert angebot["current"] == 1 and "termin_2" in angebot["items"][1]  # passender Termin vorgewählt
    assert web.geholt == ["termin_2"]
    assert len(web.anmeldungen) == 2 and web.anmeldungen[0] == web.anmeldungen[1]  # ein Passwort, zwei Anfragen
    assert desktop_web.zuordnung_lesen(ADRESSE, pfad) == "termin_2"


def test_holen_abbruch_bei_der_terminwahl(qtbot, termin, web, meldungen, sicherungen, tresor, monkeypatch):
    _teilnehmer_anlegen(termin[0], startnummer=1)
    _eingerichtet()
    tresor[ADRESSE] = "pw"
    web.termine = [{"schema_name": "termin_1", "verein": "V", "ort": "O", "datum": "d", "anzahl_teilnehmer": 1}]
    monkeypatch.setattr(desktop_web.QInputDialog, "getItem", lambda *a: ("", False))
    assert desktop_web.ergebnisse_aus_web_holen(_tab(qtbot, termin)) is False
    assert web.geholt == [] and sicherungen.aufrufe == []


def test_holen_nicht_bestaetigt_aendert_nichts(qtbot, termin, web, meldungen, sicherungen, tresor):
    conn, pfad = termin
    teilnehmer_id = _teilnehmer_anlegen(conn, startnummer=1)
    _eingerichtet()
    tresor[ADRESSE] = "pw"
    desktop_web.zuordnung_speichern(ADRESSE, pfad, "termin_9")
    web.ergebnisse = [_web_eintrag(conn, {"suche_flaechensuche": 50, "anzeige_flaechensuche": 30})]
    meldungen.antworten.append(False)
    assert desktop_web.ergebnisse_aus_web_holen(_tab(qtbot, termin)) is False
    assert sicherungen.aufrufe == []
    assert (get_ergebnis(conn, teilnehmer_id) or {}).get("suche_flaechensuche") is None


@pytest.mark.parametrize("fortfahren", [False, True])
def test_holen_misslungene_sicherung_wird_nachgefragt(qtbot, termin, web, meldungen, sicherungen, berichte, tresor, fortfahren):
    conn, pfad = termin
    teilnehmer_id = _teilnehmer_anlegen(conn, startnummer=1)
    _eingerichtet()
    tresor[ADRESSE] = "pw"
    desktop_web.zuordnung_speichern(ADRESSE, pfad, "termin_9")
    web.ergebnisse = [_web_eintrag(conn, {"suche_flaechensuche": 50, "anzeige_flaechensuche": 30})]
    sicherungen.ergebnis["pfad"] = None
    meldungen.antworten.extend([True, fortfahren])  # 1. Übernehmen?  2. Ohne Kopie fortfahren?
    ergebnis = desktop_web.ergebnisse_aus_web_holen(_tab(qtbot, termin))
    assert ergebnis is fortfahren
    assert "Sicherung nicht möglich" in meldungen.fragen[1][0]
    wert = (get_ergebnis(conn, teilnehmer_id) or {}).get("suche_flaechensuche")
    assert wert == (50 if fortfahren else None)


def test_holen_unbekannter_termin_loescht_die_zuordnung(qtbot, termin, web, meldungen, sicherungen, tresor):
    conn, pfad = termin
    _teilnehmer_anlegen(conn, startnummer=1)
    _eingerichtet()
    tresor[ADRESSE] = "pw"
    desktop_web.zuordnung_speichern(ADRESSE, pfad, "termin_gone")
    web.ergebnisse_fehler = web_sync.ServerFehler("unbekannt", 404)
    assert desktop_web.ergebnisse_aus_web_holen(_tab(qtbot, termin)) is False
    assert desktop_web.zuordnung_lesen(ADRESSE, pfad) is None
    assert "nicht mehr" in meldungen.information[-1][1]


def test_holen_fehler_der_liste_wird_gemeldet(qtbot, termin, web, meldungen, sicherungen, tresor):
    conn, pfad = termin
    _teilnehmer_anlegen(conn, startnummer=1)
    _eingerichtet()
    tresor[ADRESSE] = "pw"
    desktop_web.zuordnung_speichern(ADRESSE, pfad, "termin_9")
    web.ergebnisse = "kein Listenformat"
    assert desktop_web.ergebnisse_aus_web_holen(_tab(qtbot, termin)) is False
    assert "unerwartetes Format" in meldungen.warning[-1][1]


def test_holen_ungespeicherte_eingaben_werden_geklaert(qtbot, termin, web, meldungen, sicherungen, tresor, monkeypatch):
    conn, pfad = termin
    _teilnehmer_anlegen(conn, startnummer=1)
    _eingerichtet()
    fragen = []

    class _Fenster:
        def _ungespeicherte_ergebnisse_klaeren(self, frage, ohne_speichern=None):
            fragen.append(frage)
            return False

    tab = _tab(qtbot, termin)
    monkeypatch.setattr(tab, "window", lambda: _Fenster())
    assert desktop_web.ergebnisse_aus_web_holen(tab) is False
    desktop_web.termin_veroeffentlichen(tab)
    assert len(fragen) == 2 and web.erzeugt == []


def test_401_nach_erfolgreicher_anmeldung_loescht_das_passwort_nicht(qtbot, termin, web, meldungen, sicherungen, tresor):
    conn, pfad = termin
    _teilnehmer_anlegen(conn, startnummer=1)
    _eingerichtet()
    tresor[ADRESSE] = "richtig"
    desktop_web.zuordnung_speichern(ADRESSE, pfad, "termin_9")
    web.ergebnisse_fehler = web_sync.AnmeldeFehler("Token abgelaufen", 401)
    assert desktop_web.ergebnisse_aus_web_holen(_tab(qtbot, termin)) is False
    assert tresor[ADRESSE] == "richtig" and "Token abgelaufen" in meldungen.warning[-1][1]


def test_falscher_servertermin_wird_nicht_gemerkt(qtbot, termin, web, meldungen, sicherungen, berichte, tresor, monkeypatch):
    conn, pfad = termin
    _teilnehmer_anlegen(conn, nachname="Muster", startnummer=1)
    _eingerichtet()
    tresor[ADRESSE] = "pw"
    web.termine = [{"schema_name": "termin_1", "verein": "V", "ort": "O", "datum": "d", "anzahl_teilnehmer": 1}]
    web.ergebnisse = [dict(list_teilnehmer(conn)[0], nachname="Ganz anders", ergebnis={"suche_flaechensuche": 50, "anzeige_flaechensuche": 30})]
    monkeypatch.setattr(desktop_web.QInputDialog, "getItem", lambda parent, t, x, items, c, e: (items[0], True))
    tab = _tab(qtbot, termin)
    assert desktop_web.ergebnisse_aus_web_holen(tab) is True
    # der Web-Termin wird im Bestätigungstext genannt - mit Namen, ohne interne Kennung (E3)
    assert "„V, O, d“" in meldungen.fragen[0][1] and "termin_1" not in meldungen.fragen[0][1]
    assert desktop_web.zuordnung_lesen(ADRESSE, pfad) is None
    assert "nicht gemerkt" in tab.status_label.text()


def test_hochladen_ist_nicht_abbrechbar(qtbot):
    from PySide6.QtWidgets import QPushButton

    dialoge = []
    ursprung = desktop_web._WarteDialog.exec

    def exec_(dialog):
        dialoge.append(dialog)
        dialog.reject()  # Esc/X: wird ignoriert, das Fenster bleibt bis zur Antwort
        assert dialog.abbrechbar is False
        return ursprung(dialog)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(desktop_web._WarteDialog, "exec", exec_)
        assert desktop_web.im_hintergrund(None, "Warte", lambda: 5, abbrechbar=False) == (5, None)
    assert dialoge[0].findChildren(QPushButton) == []


def test_rueckfrage_ungespeichert_nennt_den_richtigen_vorgang(qtbot, termin, monkeypatch):
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    monkeypatch.setattr(fenster.ergebnis_tab, "hat_ungespeicherte_aenderungen", lambda: True)
    texte = rueckfragen_sammeln(monkeypatch, QMessageBox.Cancel)
    assert fenster._ungespeicherte_ergebnisse_klaeren("Trotzdem", ohne_speichern="holt die Web-Ergebnisse,") is False
    assert "„Verwerfen“ holt die Web-Ergebnisse," in texte[0] and "wechselt" not in texte[0]
    assert fenster._ungespeicherte_ergebnisse_klaeren("Trotzdem") is False
    assert "„Verwerfen“ wechselt ohne Speichern" in texte[1]  # Terminwechsel unverändert


# --- Bericht -------------------------------------------------------------------------------------

def test_bericht_text_nennt_alle_gruppen():
    from db import ImportBericht

    bericht = ImportBericht(
        aktualisiert=3, ohne_startnummer_uebersprungen=["Ohne, Nummer"], nicht_gefunden=["99"],
        fehler=["Fehler, Name"], abweichungen=["Nr. 5: Web A ≠ Termin-Datei B"], im_web_leer=["Nr. 1 X – Trümmerfeld: leer"])
    zusammenfassung, einzelheiten = desktop_web.bericht_text(bericht)
    assert zusammenfassung.startswith("3 Teilnehmer geändert, 0 unverändert.")
    assert "1 Disziplin(en) im Web leer, in dieser Datei gefüllt" in zusammenfassung
    for erwartet in ("Ohne, Nummer", "99", "Fehler, Name", "Nr. 5", "Trümmerfeld", "Disqualifikation und Abbruch"):
        assert erwartet in einzelheiten
    leer, leer_einzeln = desktop_web.bericht_text(ImportBericht(0, [], [], [], [], [], unveraendert=12))
    # UX-Test Web 19.11.2026 (E2): nur vorkommende Sonderfälle, keine „0 … leer“-Aufzählung
    assert leer == "0 Teilnehmer geändert, 12 unverändert."
    assert leer_einzeln.startswith("Hinweis: Disqualifikation")
    assert "werden aus dem Web übernommen" in leer_einzeln
    mit_notizen = desktop_web.bericht_text(ImportBericht(2, [], [], unveraendert=1, notizen_uebernommen=3))
    assert "3 Notiz(en) zum Bewertungsbogen übernommen (sichtbar im PDF-Bewertungsbogen)." in mit_notizen[0]
    assert "im Desktop-Programm werden sie nicht angezeigt" in mit_notizen[1]
    geloescht = desktop_web.bericht_text(ImportBericht(1, [], [], notizen_geloescht=1))[0]
    assert "1 Notiz(en) im Web gelöscht und in der Datei entfernt." in geloescht and "übernommen" not in geloescht
    mit_status = ImportBericht(1, [], [], status_geaendert=["Nr. 2 Muster, Anna: ohne Status → disqualifiziert"])
    zusammenfassung, einzelheiten = desktop_web.bericht_text(mit_status)
    assert "1 Status (Disqualifikation/Abbruch) geändert" in zusammenfassung
    assert "Nr. 2 Muster, Anna: ohne Status → disqualifiziert" in einzelheiten
