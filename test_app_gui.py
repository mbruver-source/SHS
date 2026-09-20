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

Hinweis (aus einem echten CI-Fehlschlag gelernt): Widgets, an denen per `qtbot.mouseClick`
tatsächlich geklickt wird, müssen vorher mit `.show()` sichtbar gemacht werden - ohne
`.show()` hat ein Klick auf eine (noch nie gezeigte) QCheckBox im ersten CI-Lauf nicht
zuverlässig ausgelöst, vermutlich weil Qt die genaue Klickfläche des Kästchens erst nach
einem Layout-/Show-Durchlauf kennt. Ein einfacher Konstruktor-Aufruf ohne Klick braucht
das nicht zwingend, schadet aber auch nicht - hier der Einfachheit halber überall gesetzt.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton

from app import (
    VERSION,
    _QSS_MODERN_MINIMAL,
    AuswertungTab,
    HauptFenster,
    HilfeDialog,
    TeilnehmerDialog,
    TeilnehmerTab,
    TeilnehmerUebersichtTab,
    VersionDialog,
)
from db import NeuerTeilnehmer, add_teilnehmer, eintragen_ergebnis, init_db, list_teilnehmer, set_veranstaltung


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


# --- Erscheinungsbild "Modern/Minimal" (siehe Design-Mockup-Vergleich) --------------
# Der Stylesheet-Text selbst wird nicht pixelgenau geprüft (das könnte nur ein
# Screenshot-Vergleich leisten) - hier nur, dass er tatsächlich gesetzt wird (main(),
# nicht separat testbar ohne den echten Startdialog durchzuklicken) und dass die als
# Haupt-Aktion vorgesehenen Buttons den dafür vorgesehenen objectName tragen, über den
# _QSS_MODERN_MINIMAL sie hervorhebt.


def test_qss_modern_minimal_enthaelt_kernselektoren():
    assert "QTabBar::tab:selected" in _QSS_MODERN_MINIMAL
    assert "QPushButton#primaerButton" in _QSS_MODERN_MINIMAL
    assert "#2F6FED" in _QSS_MODERN_MINIMAL  # Akzentfarbe


def test_teilnehmer_hinzufuegen_ist_primaerbutton(qtbot, conn):
    tab = TeilnehmerTab(conn)
    qtbot.addWidget(tab)
    # Der einzige Button mit diesem objectName in diesem Tab ist "Teilnehmer hinzufügen…".
    gefunden = [b for b in tab.findChildren(QPushButton) if b.objectName() == "primaerButton"]
    assert len(gefunden) == 1
    assert gefunden[0].text() == "Teilnehmer hinzufügen…"


# --- Zeilennummern-Spalte ausgeblendet (in allen drei Tabellen-Tabs einheitlich) ----
# Nutzerhinweis (20.09.): bei der Auswertung waren die Zeilennummern links noch sichtbar,
# obwohl sie bei Teilnehmer und Ergebniserfassung bereits ausgeblendet sind - jetzt überall
# konsistent versteckt (verticalHeader().setVisible(False)).


def test_auswertung_tabelle_zeigt_keine_zeilennummern(qtbot, conn):
    tab = AuswertungTab(conn)
    qtbot.addWidget(tab)
    assert not tab.tabelle.verticalHeader().isVisible()


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


# --- Bezahlt-Markierung -------------------------------------------------------------


def test_bezahlt_button_ist_erst_nach_auswahl_einer_zeile_aktiv(qtbot, conn):
    _teilnehmer_anlegen(conn)
    tab = TeilnehmerTab(conn)
    qtbot.addWidget(tab)
    tab.show()

    assert not tab.bezahlt_btn.isEnabled()
    tab.tabelle.selectRow(0)
    assert tab.bezahlt_btn.isEnabled()


def test_bezahlt_umschalten_per_klick_aendert_datenbank_und_tabelle(qtbot, conn):
    _teilnehmer_anlegen(conn)
    tab = TeilnehmerTab(conn)
    qtbot.addWidget(tab)
    tab.show()
    tab.tabelle.selectRow(0)

    assert list_teilnehmer(conn)[0]["bezahlt"] == 0
    assert tab.tabelle.item(0, 6).text() == ""

    qtbot.mouseClick(tab.bezahlt_btn, Qt.MouseButton.LeftButton)

    assert list_teilnehmer(conn)[0]["bezahlt"] == 1
    assert "bezahlt" in tab.tabelle.item(0, 6).text()


def test_filter_bezahlt_blendet_zeilen_nach_status_aus(qtbot, conn):
    # Nutzerwunsch (20.09.): Filter nach Bezahlt-Status, z.B. um am Anmeldetisch schnell
    # zu sehen, wer noch nicht bezahlt hat.
    _teilnehmer_anlegen(conn, nachname="Bezahlt", startnummer=1, bezahlt=True)
    _teilnehmer_anlegen(conn, nachname="Offen", startnummer=2, bezahlt=False)
    tab = TeilnehmerTab(conn)
    qtbot.addWidget(tab)

    # "Alle" (Vorbelegung): beide Zeilen sichtbar.
    assert not tab.tabelle.isRowHidden(0)
    assert not tab.tabelle.isRowHidden(1)

    tab.filter_bezahlt.setCurrentText("Bezahlt")
    assert not tab.tabelle.isRowHidden(0)
    assert tab.tabelle.isRowHidden(1)

    tab.filter_bezahlt.setCurrentText("Nicht bezahlt")
    assert tab.tabelle.isRowHidden(0)
    assert not tab.tabelle.isRowHidden(1)

    tab.filter_bezahlt.setCurrentText("Alle")
    assert not tab.tabelle.isRowHidden(0)
    assert not tab.tabelle.isRowHidden(1)


def test_bezahlt_checkbox_im_teilnehmer_dialog(qtbot):
    dialog = TeilnehmerDialog(vergebene_nummern=set())
    qtbot.addWidget(dialog)
    dialog.show()
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
    dialog.show()
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
    dialog.show()
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


def test_doppelte_disziplin_zuordnung_wird_beim_speichern_abgelehnt(qtbot, monkeypatch):
    """QS-Review (19./20.09.): Werden zwei der drei Gegenstand-Felder derselben Disziplin
    zugeordnet, würde gegenstand_fuer_disziplin() (db.py) für diese Disziplin nur den
    ersten Treffer liefern - der zweite Gegenstand verschwindet dann spurlos, z.B. auf dem
    Bewertungsbogen. Das muss beim Speichern verhindert werden, unabhängig vom
    eingetragenen Gegenstand-Text."""
    dialog = TeilnehmerDialog(vergebene_nummern=set())
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.nachname.setText("Muster")
    dialog.vorname.setText("Max")
    dialog.rufname_hund.setText("Bello")
    dialog.gegenstand_1.setText("Schlüsselbund")
    dialog.gegenstand_1_disziplin.setCurrentText("Trümmerfeld")
    dialog.gegenstand_2.setText("Korken")
    dialog.gegenstand_2_disziplin.setCurrentText("Trümmerfeld")

    warnung_gezeigt = {}
    monkeypatch.setattr(
        "app.QMessageBox.warning",
        lambda *a, **k: warnung_gezeigt.setdefault("ja", True),
    )

    dialog._pruefen_und_akzeptieren()

    assert warnung_gezeigt.get("ja") is True
    assert dialog.result() == 0  # Dialog wurde NICHT akzeptiert (QDialog.Rejected/0)


def test_gleicher_gegenstand_in_mehreren_disziplinen_bleibt_erlaubt(qtbot, monkeypatch):
    """Absprache mit Marco zu Finding #4: derselbe physische Gegenstand darf weiterhin für
    mehrere Disziplinen gesucht werden (z.B. DK LK1: ein Gegenstand in allen 3 Disziplinen,
    LK2: ein Gegenstand in bis zu 2 Disziplinen) - das bildet man ab, indem man denselben
    Text in mehrere Gegenstand-Felder einträgt, jeweils mit EINER ANDEREN Disziplin-
    Zuordnung. Nur die doppelte DISZIPLIN-Zuordnung ist verboten, nicht der doppelte Text."""
    dialog = TeilnehmerDialog(vergebene_nummern=set())
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.nachname.setText("Muster")
    dialog.vorname.setText("Max")
    dialog.rufname_hund.setText("Bello")
    dialog.gegenstand_1.setText("Schlüsselbund")
    dialog.gegenstand_1_disziplin.setCurrentText("Trümmerfeld")
    dialog.gegenstand_2.setText("Schlüsselbund")
    dialog.gegenstand_2_disziplin.setCurrentText("Flächensuche")
    dialog.gegenstand_3.setText("Schlüsselbund")
    dialog.gegenstand_3_disziplin.setCurrentText("Behältnisstrecke")

    warnung_gezeigt = {}
    monkeypatch.setattr(
        "app.QMessageBox.warning",
        lambda *a, **k: warnung_gezeigt.setdefault("ja", True),
    )

    dialog._pruefen_und_akzeptieren()

    assert warnung_gezeigt.get("ja") is None
    assert dialog.result() == 1  # Dialog wurde akzeptiert (QDialog.Accepted/1)


def test_bestehender_teilnehmer_im_dialog_zeigt_gespeicherte_zuordnung(qtbot, conn):
    _teilnehmer_anlegen(
        conn,
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
    assert dialog.wurftag.text() == "2023-04-01"
    assert dialog.strasse.text() == "Hauptstraße"
    assert dialog.hausnummer.text() == "12a"
    assert dialog.plz.text() == "61479"
    assert dialog.ort.text() == "Höppern"
    assert dialog.email.text() == "max.muster@example.com"
    assert dialog.telefon.text() == "06171 123456"


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


# --- Version-Button ---------------------------------------------------------------


def test_version_button_ist_sichtbar_und_oeffnet_versiondialog(qtbot, termin, monkeypatch):
    """Analog zu test_hilfe_button_...: der Version-Button neben "Hilfe" existiert,
    ist sichtbar, zeigt die aktuelle Version im Text und öffnet den VersionDialog."""
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.show()

    version_buttons = [b for b in fenster.findChildren(QPushButton) if b.text() == f"ℹ️ Version {VERSION}"]
    assert len(version_buttons) == 1
    version_btn = version_buttons[0]
    assert version_btn.isVisible()
    assert version_btn.height() > 0

    geoeffnet = {}
    monkeypatch.setattr(VersionDialog, "exec", lambda self: geoeffnet.setdefault("ja", True))

    qtbot.mouseClick(version_btn, Qt.MouseButton.LeftButton)

    assert geoeffnet.get("ja") is True


def test_versiondialog_zeigt_aktuelle_version(qtbot):
    dialog = VersionDialog()
    qtbot.addWidget(dialog)
    dialog.show()

    texte = [w.text() for w in dialog.findChildren(QLabel)]
    assert any(VERSION in t for t in texte)


def test_versiondialog_update_button_zeigt_neuere_version_mit_download_button(qtbot, monkeypatch):
    """Seit das Repository öffentlich ist, prüft der "Nach Updates suchen"-Button per
    GitHub-API automatisch, statt nur die Releases-Seite zu öffnen (siehe
    _neueste_version_pruefen/VersionDialog._updates_pruefen in app.py) - hier mit einer
    gefakten Antwort ("es gibt eine neuere Version"), damit der Test ohne echten
    Netzwerkzugriff läuft."""
    import app

    dialog = VersionDialog()
    qtbot.addWidget(dialog)
    dialog.show()

    neuere_version = ".".join(str(t + 1) for t in app._version_tupel(VERSION)[:1]) + ".0.0"
    monkeypatch.setattr(app, "_neueste_version_pruefen", lambda: (neuere_version, None))
    assert not dialog._download_btn.isVisible()

    update_buttons = [b for b in dialog.findChildren(QPushButton) if b.text() == "Nach Updates suchen"]
    assert len(update_buttons) == 1
    qtbot.mouseClick(update_buttons[0], Qt.MouseButton.LeftButton)

    assert neuere_version in dialog._ergebnis_zeile.text()
    assert dialog._download_btn.isVisible()

    geoeffnete_urls = []
    monkeypatch.setattr(app.QDesktopServices, "openUrl", lambda url: geoeffnete_urls.append(url.toString()))
    qtbot.mouseClick(dialog._download_btn, Qt.MouseButton.LeftButton)
    assert geoeffnete_urls == [app.GITHUB_RELEASES_URL]


def test_versiondialog_update_button_zeigt_hinweis_wenn_aktuell(qtbot, monkeypatch):
    import app

    dialog = VersionDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    monkeypatch.setattr(app, "_neueste_version_pruefen", lambda: (VERSION, None))

    update_btn = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Nach Updates suchen")
    qtbot.mouseClick(update_btn, Qt.MouseButton.LeftButton)

    assert "bereits die neueste Version" in dialog._ergebnis_zeile.text()
    assert not dialog._download_btn.isVisible()


def test_versiondialog_update_button_zeigt_fehler_ohne_internet(qtbot, monkeypatch):
    """_neueste_version_pruefen() fängt Netzwerkfehler selbst ab und liefert einen
    Fehlertext statt einer Exception (siehe dortiger Docstring) - der Dialog zeigt diesen
    Text dann einfach an, statt abzustürzen."""
    import app

    dialog = VersionDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    monkeypatch.setattr(
        app, "_neueste_version_pruefen", lambda: (None, "Keine Verbindung zu GitHub möglich (kein Internetzugang?).")
    )

    update_btn = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Nach Updates suchen")
    qtbot.mouseClick(update_btn, Qt.MouseButton.LeftButton)

    assert "Keine Verbindung" in dialog._ergebnis_zeile.text()
    assert not dialog._download_btn.isVisible()


def test_versiondialog_releases_seite_button_oeffnet_browser_ohne_netzwerkzugriff(qtbot, monkeypatch):
    """Der separate Link "Releases-Seite im Browser öffnen" bleibt als manueller
    Rückfallweg bestehen (z. B. falls die automatische Prüfung fehlschlägt) und ruft
    dabei NIE die GitHub-API auf, sondern öffnet direkt den Browser."""
    import app

    dialog = VersionDialog()
    qtbot.addWidget(dialog)
    dialog.show()

    aufgerufen = {}
    monkeypatch.setattr(app, "_neueste_version_pruefen", lambda: aufgerufen.setdefault("ja", True))
    geoeffnete_urls = []
    monkeypatch.setattr(app.QDesktopServices, "openUrl", lambda url: geoeffnete_urls.append(url.toString()))

    seite_btn = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Releases-Seite im Browser öffnen")
    qtbot.mouseClick(seite_btn, Qt.MouseButton.LeftButton)

    assert geoeffnete_urls == [app.GITHUB_RELEASES_URL]
    assert "ja" not in aufgerufen


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
    monkeypatch.setattr("app.QMessageBox.question", lambda *a, **k: QMessageBox.No)

    fenster.close()

    assert fenster.isVisible()


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
    monkeypatch.setattr("app.QMessageBox.question", lambda *a, **k: QMessageBox.Yes)

    fenster.close()

    assert not fenster.isVisible()


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
    suche_feld, anzeige_feld = ergebnis_tab._boxen_je_zeile[0]["Flächensuche"]
    assert suche_feld.text() == "45"
    assert anzeige_feld.text() == "28"

    suche_feld.clear()
    anzeige_feld.clear()
    assert ergebnis_tab._zeile_ist_ungespeichert(0)

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
    assert not ergebnis_tab._zeile_ist_ungespeichert(0)
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
    suche_feld, _anzeige_feld = ergebnis_tab._boxen_je_zeile[0]["Flächensuche"]
    suche_feld.clear()

    warnung_gezeigt = {}
    monkeypatch.setattr(
        "app.QMessageBox.warning",
        lambda *a, **k: warnung_gezeigt.setdefault("ja", True),
    )

    speichern_btn = next(
        b for b in fenster.findChildren(QPushButton) if b.text() == "Alle Ergebnisse speichern"
    )
    qtbot.mouseClick(speichern_btn, Qt.MouseButton.LeftButton)

    assert warnung_gezeigt.get("ja") is True
    # Der alte Wert bleibt in der DB unverändert (Anzeige-Feld war ja noch gültig
    # gefüllt, aber ohne Gegenstück nicht speicherbar).
    zeile = conn.execute(
        "SELECT suche_flaechensuche, anzeige_flaechensuche FROM ergebnisse WHERE teilnehmer_id = ?", (tid,)
    ).fetchone()
    assert zeile["suche_flaechensuche"] == 45
    assert zeile["anzeige_flaechensuche"] == 28
