"""GUI-Tests: Reiter Verwaltung, Abrechnung Leistungsrichter und Checkliste.

Fixtures und Hilfen stehen in gui_hilfen.py (Aufteilung von test_app_gui.py, 11.11.2026)."""

from __future__ import annotations

import os
from app import HauptFenster
from desktop_dialoge import TeilnehmerDialog
from db import (
    get_veranstaltung,
    set_veranstaltung,
)
from desktop_verwaltung import VerwaltungTab
from gui_hilfen import *  # noqa: F401,F403


# --- Verwaltungs-/Kontaktdaten (Verband, Mitgliedsnummer, Wurftag, Anschrift, E-Mail,
# Telefon) ----------------------------------------------------------------------------


def test_verwaltungs_und_kontaktfelder_werden_im_dialog_erfasst(qtbot):
    dialog = TeilnehmerDialog(vergebene_nummern=set())
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.nachname.setText("Muster")
    dialog.vorname.setText("Max")
    dialog.rufname_hund.setText("Bello")
    dialog.verband.setText("VDH")
    dialog.mitgliedsnummer.setText("12345")
    dialog.wurftag.setText("2023-04-01")
    dialog.strasse.setText("Hauptstraße")
    dialog.hausnummer.setText("12a")
    dialog.plz.setText("61479")
    dialog.ort.setText("Höppern")
    dialog.email.setText("max.muster@example.com")
    dialog.telefon.setText("06171 123456")

    ergebnis = dialog.ergebnis()
    assert ergebnis.verband == "VDH"
    assert ergebnis.mitgliedsnummer == "12345"
    assert ergebnis.wurftag == "2023-04-01"
    assert ergebnis.strasse == "Hauptstraße"
    assert ergebnis.hausnummer == "12a"
    assert ergebnis.plz == "61479"
    assert ergebnis.ort == "Höppern"
    assert ergebnis.email == "max.muster@example.com"
    assert ergebnis.telefon == "06171 123456"


def test_verwaltungs_und_kontaktfelder_bleiben_ohne_eingabe_leer(qtbot):
    dialog = TeilnehmerDialog(vergebene_nummern=set())
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.nachname.setText("Muster")
    dialog.vorname.setText("Max")
    dialog.rufname_hund.setText("Bello")

    ergebnis = dialog.ergebnis()
    for feld in ("verband", "mitgliedsnummer", "wurftag", "strasse", "hausnummer", "plz", "ort", "email", "telefon"):
        assert getattr(ergebnis, feld) is None


def test_abrechnung_tab_zeigt_nur_eingetragene_richter_und_rechnet(qtbot, conn):
    import json
    from desktop_abrechnung import AbrechnungTab

    _abrechnung_termin(conn)
    tab = AbrechnungTab(conn)
    qtbot.addWidget(tab)
    assert tab.tabelle.rowCount() == 2
    assert [tab.tabelle.item(r, 0).text() for r in range(2)] == ["Anna Alt", "Carla Claus"]
    assert tab.tabelle.item(0, 5).text() == "50,00 €"  # ohne Kilometer nur die Pauschale
    tab.tabelle.item(0, 1).setText("120")
    assert tab.tabelle.item(0, 4).text() == "42,00 €"
    assert tab.tabelle.item(0, 5).text() == "92,00 €"
    assert tab.gesamt_label.text() == "Gesamtsumme: 142,00 €"
    # gespeichert in der Termin-Datei, gehört zur Position 1
    assert json.loads(get_veranstaltung(conn)["lr_abrechnung"]) == {"1": {"km": "120"}}


def test_abrechnung_tab_saetze_aenderbar(qtbot, conn):
    from desktop_abrechnung import AbrechnungTab

    _abrechnung_termin(conn)
    tab = AbrechnungTab(conn)
    qtbot.addWidget(tab)
    tab.tabelle.item(0, 1).setText("100")
    tab.km_satz_feld.setText("0,40")
    tab.km_satz_feld.editingFinished.emit()
    tab.pauschale_feld.setText("60")
    tab.pauschale_feld.editingFinished.emit()
    assert get_veranstaltung(conn)["lr_km_satz"] == "0,4"
    assert get_veranstaltung(conn)["lr_tagespauschale"] == "60"
    assert tab.tabelle.item(0, 5).text() == "100,00 €"
    # je Richter überschreiben, leer = wieder Satz des Termins
    tab.tabelle.item(0, 3).setText("0")
    assert tab.tabelle.item(0, 5).text() == "40,00 €"
    tab.tabelle.item(0, 3).setText("")
    assert tab.tabelle.item(0, 5).text() == "100,00 €"
    tab.km_satz_feld.setText("")
    tab.km_satz_feld.editingFinished.emit()
    assert get_veranstaltung(conn)["lr_km_satz"] is None
    assert tab.tabelle.item(0, 5).text() == "95,00 €"


def test_abrechnung_tab_ungueltige_eingabe_bleibt_ohne_wirkung(qtbot, conn):
    from desktop_abrechnung import AbrechnungTab

    _abrechnung_termin(conn)
    tab = AbrechnungTab(conn)
    qtbot.addWidget(tab)
    tab.tabelle.item(0, 1).setText("100")
    tab.tabelle.item(0, 1).setText("viel")
    assert tab.tabelle.item(0, 1).text() == "100"
    assert "keine gültige Zahl" in tab.status_label.text()
    tab.km_satz_feld.setText("-3")
    tab.km_satz_feld.editingFinished.emit()
    assert get_veranstaltung(conn)["lr_km_satz"] is None
    assert tab.km_satz_feld.text() == "0,35"  # zurück auf den gültigen Wert
    assert "keine gültige Zahl" in tab.status_label.text()


def test_abrechnung_tab_ohne_richter_und_aktualisieren(qtbot, conn):
    from desktop_abrechnung import AbrechnungTab

    set_veranstaltung(conn, verein="HSV", datum="2026-11-14")
    tab = AbrechnungTab(conn)
    qtbot.addWidget(tab)
    tab.show()
    assert not tab.tabelle.isVisible() and tab.leer_label.isVisible()
    assert not tab.uebersicht_btn.isEnabled()
    # Richter werden im Reiter Verwaltung nachgetragen: aktualisieren() übernimmt sie
    _abrechnung_termin(conn)
    tab.aktualisieren()
    assert tab.tabelle.isVisible() and tab.tabelle.rowCount() == 2
    assert tab.uebersicht_btn.isEnabled()


def test_abrechnung_tab_saetze_sind_je_zeile_vorbelegt(qtbot, conn):
    from desktop_abrechnung import AbrechnungTab

    _abrechnung_termin(conn)
    tab = AbrechnungTab(conn)
    qtbot.addWidget(tab)
    assert [tab.tabelle.item(r, 2).text() for r in range(2)] == ["0,35", "0,35"]
    assert [tab.tabelle.item(r, 3).text() for r in range(2)] == ["50", "50"]
    # Termin-Satz ändern: Zeilen ohne eigenen Wert folgen
    tab.km_satz_feld.setText("0,4")
    tab.km_satz_feld.editingFinished.emit()
    assert tab.tabelle.item(0, 2).text() == "0,4"
    # eigener Wert nur bei Abweichung gespeichert; derselbe Wert wie der Termin-Satz folgt ihm
    tab.tabelle.item(0, 2).setText("0,5")
    tab.tabelle.item(1, 2).setText("0,4")
    import json
    assert json.loads(get_veranstaltung(conn)["lr_abrechnung"]) == {"1": {"km_satz": "0,5"}}
    tab.tabelle.item(0, 3).setText("")  # leeren = zurück auf den Wert des Termins
    assert tab.tabelle.item(0, 3).text() == "50"


def test_abrechnung_tab_quittung_je_richter_getrennt(qtbot, conn, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QPushButton

    from desktop_abrechnung import AbrechnungTab

    _abrechnung_termin(conn)
    ziele = []
    monkeypatch.setattr("desktop_gemeinsam.QFileDialog.getSaveFileName",
                        lambda _p, _t, vorschlag, _f: ziele.append(os.path.basename(vorschlag)) or (str(tmp_path / f"q{len(ziele)}.pdf"), ""))
    ueberall_ersetzen(monkeypatch, "_datei_gespeichert_melden", lambda *a, **k: None)
    tab = AbrechnungTab(conn)
    qtbot.addWidget(tab)
    assert not hasattr(tab, "quittungen_btn")  # keine gesamte Quittungsliste
    for reihe in range(2):
        knopf = tab.tabelle.cellWidget(reihe, 6)
        assert isinstance(knopf, QPushButton) and knopf.text() == "Quittung…"
        assert tab.tabelle.rowHeight(reihe) >= knopf.sizeHint().height()  # Beschriftung nicht abgeschnitten
        assert tab.tabelle.columnWidth(6) >= knopf.sizeHint().width() + 16
        knopf.click()
    assert ziele == ["Quittung_Anna Alt_2026-11-14.pdf", "Quittung_Carla Claus_2026-11-14.pdf"]
    try:
        from pypdf import PdfReader
    except ImportError:
        return
    for datei, name in (("q1.pdf", "Anna Alt"), ("q2.pdf", "Carla Claus")):
        leser = PdfReader(str(tmp_path / datei))
        assert len(leser.pages) == 1
        assert name in leser.pages[0].extract_text()


def test_abrechnung_tab_uebersicht_und_ablageort_oeffnen(qtbot, conn, tmp_path, monkeypatch):
    from desktop_abrechnung import AbrechnungTab
    from desktop_gemeinsam import _Ablageort

    _abrechnung_termin(conn)
    monkeypatch.setattr("desktop_gemeinsam.QFileDialog.getSaveFileName",
                        lambda *a, **k: (str(tmp_path / "a.pdf"), ""))
    ueberall_ersetzen(monkeypatch, "_datei_gespeichert_melden", lambda *a, **k: None)
    geoeffnet = []
    monkeypatch.setattr("desktop_gemeinsam._url_oeffnen", lambda _p, url, _a: geoeffnet.append(url.toLocalFile()) or True)
    tab = AbrechnungTab(conn, _Ablageort(str(tmp_path)))
    qtbot.addWidget(tab)
    tab.uebersicht_btn.click()
    assert (tmp_path / "a.pdf").stat().st_size > 0
    monkeypatch.setattr("desktop_gemeinsam.QFileDialog.getSaveFileName",
                        lambda *a, **k: (str(tmp_path / "a.csv"), ""))
    tab.csv_btn.click()
    inhalt = (tmp_path / "a.csv").read_text(encoding="utf-8-sig")
    assert "Anna Alt" in inhalt and "Carla Claus" in inhalt and inhalt.count("Ausgabe") == 2
    # Reihenfolge der Knöpfe: Übersicht, CSV, Ablageort
    knoepfe = [tab.uebersicht_btn, tab.csv_btn, tab.ablageort_btn]
    assert [k.text() for k in knoepfe] == ["Übersicht als PDF…", "Export als CSV…", "Ablageort öffnen"]
    tab.show()
    qtbot.waitExposed(tab)
    assert knoepfe[0].geometry().x() < knoepfe[1].geometry().x() < knoepfe[2].geometry().x()
    tab.ablageort_btn.click()
    assert [os.path.normpath(p) for p in geoeffnet] == [os.path.normpath(str(tmp_path))]
    # fehlender Ordner: Meldung statt Öffnen
    warnungen = []
    monkeypatch.setattr("desktop_gemeinsam.QMessageBox.warning", lambda *a, **k: warnungen.append(a[1]))
    tab2 = AbrechnungTab(conn, _Ablageort(str(tmp_path / "gibt-es-nicht")))
    qtbot.addWidget(tab2)
    tab2.ablageort_btn.click()
    assert warnungen == ["Ordner nicht gefunden"] and len(geoeffnet) == 1


# --- Checkliste im Reiter Verwaltung (Marco 09.11.2026) ----------------------------------------


def test_verwaltung_checkliste_haken_werden_je_termin_gespeichert(qtbot, conn, monkeypatch):
    import checkliste

    set_veranstaltung(conn, verein="HSV", datum="2026-11-14", zeitplan_start="08:00")
    tab = VerwaltungTab(conn)
    qtbot.addWidget(tab)
    assert tab.checkliste_stand.text() == f"0 von {len(checkliste.ALLE_KENNUNGEN)} erledigt"
    assert set(tab.checkliste_felder) == set(checkliste.ALLE_KENNUNGEN)
    tab.checkliste_felder["zeitplan"].setChecked(True)
    tab.checkliste_felder["anmeldeformular"].setChecked(True)
    v = get_veranstaltung(conn)
    assert checkliste.erledigte(v) == {"zeitplan", "anmeldeformular"}
    assert v["zeitplan_start"] == "08:00"  # andere Veranstaltungsfelder bleiben erhalten
    assert tab.checkliste_stand.text().startswith("2 von")
    # neu aufgebaut (anderer Reiter, Terminwechsel): Haken kommen aus der Datenbank
    neu = VerwaltungTab(conn)
    qtbot.addWidget(neu)
    assert neu.checkliste_felder["zeitplan"].isChecked() and not neu.checkliste_felder["listen"].isChecked()
    # Veranstaltungsdaten bearbeiten ändert die Haken nicht
    from desktop_gemeinsam import _aktualisiere_veranstaltung_feld
    _aktualisiere_veranstaltung_feld(conn, ort="Musterstadt")
    assert checkliste.erledigte(get_veranstaltung(conn)) == {"zeitplan", "anmeldeformular"}


def test_verwaltung_checkliste_zuruecksetzen_fragt_nach(qtbot, conn, monkeypatch):
    from PySide6.QtWidgets import QPushButton

    set_veranstaltung(conn, verein="HSV", datum="2026-11-14")
    tab = VerwaltungTab(conn)
    qtbot.addWidget(tab)
    tab.checkliste_felder["zeitplan"].setChecked(True)
    knopf = next(b for b in tab.findChildren(QPushButton) if b.text() == "Alle Haken entfernen")
    antworten = iter([False, True])
    monkeypatch.setattr("desktop_verwaltung._ja_nein", lambda *a, **k: next(antworten))
    knopf.click()  # Nein: bleibt
    assert tab.checkliste_felder["zeitplan"].isChecked()
    knopf.click()  # Ja: weg, auch in der Datenbank
    assert not tab.checkliste_felder["zeitplan"].isChecked()
    assert get_veranstaltung(conn)["checkliste"] is None


def test_verwaltung_checkliste_kategorien_stehen_zugeklappt_und_klappen_auf(qtbot, conn):
    import checkliste

    tab = _checkliste_tab(qtbot, conn)
    schluessel = [k[0] for k in checkliste.CHECKLISTE]
    assert list(tab.checkliste_koepfe) == schluessel
    assert all(tab.checkliste_inhalte[k].isHidden() for k in schluessel)  # Standard: zugeklappt
    assert tab.checkliste_koepfe["vorher"].text() == "Wochen vorher  (0 von 2)"
    tab.checkliste_koepfe["vorher"].click()
    assert not tab.checkliste_inhalte["vorher"].isHidden()
    assert tab.checkliste_inhalte["meldungen"].isHidden()
    tab.checkliste_felder["anmeldeformular"].setChecked(True)
    assert tab.checkliste_koepfe["vorher"].text() == "Wochen vorher  (1 von 2)"
    tab.checkliste_koepfe["vorher"].click()
    assert tab.checkliste_inhalte["vorher"].isHidden()


def test_verwaltung_checkliste_eigene_kategorie_und_punkte(qtbot, conn, monkeypatch):
    import checkliste

    tab = _checkliste_tab(qtbot, conn)
    antworten = iter([("Verein", True), ("Pokale besorgen", True), ("Urkunden drucken", True), ("Tee kochen", True)])
    monkeypatch.setattr("desktop_verwaltung.QInputDialog.getText", lambda *a, **k: next(antworten))
    tab._checkliste_kategorie_hinzufuegen()
    assert list(tab.checkliste_koepfe)[-1] == "e1"
    assert tab.checkliste_koepfe["e1"].text() == "Verein  (0 von 0)"
    tab._checkliste_punkt_hinzufuegen("e1")
    tab._checkliste_punkt_hinzufuegen("e1")
    tab._checkliste_punkt_hinzufuegen("tag")  # auch in einer festen Kategorie
    assert not tab.checkliste_inhalte["e1"].isHidden()  # beim Hinzufügen aufgeklappt
    assert tab.checkliste_koepfe["e1"].text() == "Verein  (0 von 2)"
    assert tab.checkliste_koepfe["tag"].text() == "Am Prüfungstag  (0 von 3)"
    assert tab.checkliste_stand.text() == "0 von 21 erledigt"
    tab.checkliste_felder["e3"].setChecked(True)  # Urkunden drucken
    neu = VerwaltungTab(conn)  # neu geöffnet: alles aus der Datenbank
    qtbot.addWidget(neu)
    assert neu.checkliste_felder["e3"].isChecked() and not neu.checkliste_felder["e2"].isChecked()
    assert checkliste.erledigte(get_veranstaltung(conn)) == {"e3"}
    assert neu.checkliste_inhalte["e1"].isHidden()  # Zustand auf/zu gilt nur für die Sitzung des Reiters


def test_verwaltung_checkliste_eigenes_loeschen(qtbot, conn, monkeypatch):
    import checkliste

    tab = _checkliste_tab(qtbot, conn)
    antworten = iter([("Verein", True), ("Pokale", True), ("Urkunden", True)])
    monkeypatch.setattr("desktop_verwaltung.QInputDialog.getText", lambda *a, **k: next(antworten))
    tab._checkliste_kategorie_hinzufuegen()
    tab._checkliste_punkt_hinzufuegen("e1")
    tab._checkliste_punkt_hinzufuegen("e1")
    tab.checkliste_felder["e2"].setChecked(True)
    tab.checkliste_felder["zeitplan"].setChecked(True)
    fragen = iter([False, True, True])
    monkeypatch.setattr("desktop_verwaltung._ja_nein", lambda *a, **k: next(fragen))
    tab._checkliste_punkt_loeschen("e2")  # Nein
    assert "e2" in tab.checkliste_felder
    tab._checkliste_punkt_loeschen("e2")  # Ja: Punkt und sein Haken sind weg, feste Haken bleiben
    assert "e2" not in tab.checkliste_felder and "e3" in tab.checkliste_felder
    assert checkliste.erledigte(get_veranstaltung(conn)) == {"zeitplan"}
    tab._checkliste_kategorie_loeschen("e1")  # samt Punkten
    assert "e1" not in tab.checkliste_koepfe and "e3" not in tab.checkliste_felder
    assert get_veranstaltung(conn)["checkliste_eigene"] is None


def test_verwaltung_checkliste_leere_eingabe_und_grenzen(qtbot, conn, monkeypatch):
    tab = _checkliste_tab(qtbot, conn)
    monkeypatch.setattr("desktop_verwaltung.QInputDialog.getText", lambda *a, **k: ("   ", True))
    tab._checkliste_kategorie_hinzufuegen()
    assert get_veranstaltung(conn)["checkliste_eigene"] is None
    monkeypatch.setattr("desktop_verwaltung.QInputDialog.getText", lambda *a, **k: ("Neu", False))
    tab._checkliste_kategorie_hinzufuegen()  # abgebrochen
    assert get_veranstaltung(conn)["checkliste_eigene"] is None


def test_kopfknopf_checkliste_springt_zur_checkliste(qtbot, termin):
    conn, pfad = termin
    set_veranstaltung(conn, verein="HSV", datum="2026-11-14")
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    assert fenster.checkliste_btn.text() == "Checkliste"
    fenster._tabs.setCurrentWidget(fenster.ergebnis_tab)
    fenster.checkliste_btn.click()
    assert fenster._tabs.currentWidget() is fenster.verwaltung_tab
    tab = fenster.verwaltung_tab
    # erste Kategorie mit offenen Punkten ist aufgeklappt, die übrigen bleiben zu
    assert not tab.checkliste_inhalte["vorher"].isHidden()
    assert tab.checkliste_inhalte["meldungen"].isHidden()
    # alle Punkte der ersten Kategorie erledigt: der Knopf klappt die nächste auf
    tab.checkliste_felder["veranstaltung"].setChecked(True)
    tab.checkliste_felder["anmeldeformular"].setChecked(True)
    tab.checkliste_koepfe["vorher"].click()  # zuklappen
    fenster._tabs.setCurrentWidget(fenster.auswertung_tab)
    fenster.checkliste_btn.click()
    assert tab.checkliste_inhalte["vorher"].isHidden()
    assert not tab.checkliste_inhalte["meldungen"].isHidden()


def test_verwaltung_checkliste_vorgegebenes_ausblenden_und_wieder_einblenden(qtbot, conn, monkeypatch):
    import checkliste

    tab = _checkliste_tab(qtbot, conn)
    assert not tab.checkliste_einblenden_btn.isEnabled()
    tab.checkliste_felder["zeitplan"].setChecked(True)
    fragen = iter([False, True, True])
    monkeypatch.setattr("desktop_verwaltung._ja_nein", lambda *a, **k: next(fragen))
    tab._checkliste_ausblenden("zeitplan", "Punkt")  # Nein: bleibt
    assert "zeitplan" in tab.checkliste_felder
    tab._checkliste_ausblenden("zeitplan", "Punkt")  # Ja: weg samt Haken
    assert "zeitplan" not in tab.checkliste_felder
    assert tab.checkliste_koepfe["tage8"].text() == "8 Tage vorher  (0 von 2)"
    assert tab.checkliste_stand.text() == "0 von 17 erledigt"
    assert tab.checkliste_einblenden_btn.isEnabled()
    assert tab.checkliste_einblenden_btn.text() == "Ausgeblendetes zeigen (1)"
    tab._checkliste_ausblenden("tag", "Kategorie")  # ganze Kategorie
    assert "tag" not in tab.checkliste_koepfe and "ergebnisse" not in tab.checkliste_felder
    assert checkliste.eigene_lesen(get_veranstaltung(conn))["ausgeblendet"] == ["zeitplan", "tag"]
    # neu geöffnet: bleibt ausgeblendet, der Haken ist verschwunden
    neu = VerwaltungTab(conn)
    qtbot.addWidget(neu)
    assert "tag" not in neu.checkliste_koepfe and "zeitplan" not in neu.checkliste_felder
    neu._checkliste_alle_einblenden()
    assert "tag" in neu.checkliste_koepfe and "zeitplan" in neu.checkliste_felder
    assert not neu.checkliste_felder["zeitplan"].isChecked()
    assert not neu.checkliste_einblenden_btn.isEnabled()
    assert get_veranstaltung(conn)["checkliste_eigene"] is None


def test_verwaltung_checkliste_knoepfe_je_art(qtbot, conn):
    from PySide6.QtWidgets import QPushButton

    tab = _checkliste_tab(qtbot, conn)
    texte = [b.text() for b in tab.findChildren(QPushButton)]
    assert texte.count("Kategorie ausblenden") == 7  # eine je fester Kategorie
    assert "Kategorie löschen" not in texte
