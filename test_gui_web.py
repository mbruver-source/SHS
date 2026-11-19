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
    return speicher


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


@pytest.mark.parametrize("faktor", [1.0, 1.3, 1.6, 2.0])
def test_dialog_bei_grosser_schrift_nichts_abgeschnitten(qtbot, faktor):
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
    assert "2 teilnehmende" in meldungen.fragen[0][1] and ADRESSE in meldungen.fragen[0][1]
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
    assert "1 teilnehmende" in meldungen.fragen[0][1] and "(1)" in meldungen.fragen[0][1]
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
    assert len(berichte) == 1 and "1 Teilnehmer aktualisiert" in berichte[0].findChildren(QLabel)[0].text()
    assert "Disqualifikation und Abbruch werden übernommen" in meldungen.fragen[0][1]
    assert "ersetzt die Werte der Datei" in meldungen.fragen[0][1]


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
    assert "termin_1" in meldungen.fragen[0][1]  # der Web-Termin wird im Bestätigungstext genannt
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
    assert zusammenfassung.startswith("3 Teilnehmer aktualisiert")
    for erwartet in ("Ohne, Nummer", "99", "Fehler, Name", "Nr. 5", "Trümmerfeld", "Disqualifikation und Abbruch"):
        assert erwartet in einzelheiten
    leer = desktop_web.bericht_text(ImportBericht(0, [], [], [], [], []))[1]
    assert leer.startswith("Hinweis: Disqualifikation")
    assert "werden aus dem Web übernommen" in leer
    mit_status = ImportBericht(1, [], [], status_geaendert=["Nr. 2 Muster, Anna: ohne Status → disqualifiziert"])
    zusammenfassung, einzelheiten = desktop_web.bericht_text(mit_status)
    assert "1 Status (Disqualifikation/Abbruch) geändert" in zusammenfassung
    assert "Nr. 2 Muster, Anna: ohne Status → disqualifiziert" in einzelheiten
