"""GUI-Tests: Darstellung, Hilfe, Version, Beagle, Fehlerfenster und Protokoll.

Fixtures und Hilfen stehen in gui_hilfen.py (Aufteilung von test_app_gui.py, 11.11.2026)."""

from __future__ import annotations

import os
import sys
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QFont, QKeySequence, QPalette
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel, QMenu, QMessageBox, QPushButton
from app import HauptFenster, StartDialog
from desktop_dialoge import HilfeDialog, TeilnehmerDialog, VeranstaltungsDialog
from db import (
    NeuerTeilnehmer,
    add_zeitplan_richter,
    list_teilnehmer,
    set_veranstaltung,
    setze_keine_teilnahme,
    update_teilnehmer,
)
from desktop_darstellung import _darstellung_anwenden, _erzeuge_qss
from desktop_dialoge import (
    DIALOG_MAX_BREITE_ANTEIL,
    DIALOG_MAX_HOEHE_ANTEIL,
    _wiederherstellungsziele_planen,
)
import desktop_programm
from desktop_programm import VERSION, VersionDialog
from desktop_verwaltung import DatensicherungTab
from desktop_gemeinsam import symbol
from gui_hilfen import *  # noqa: F401,F403


# --- Erscheinungsbild "Modern/Minimal" (siehe Design-Mockup-Vergleich) --------------
# Der Stylesheet-Text selbst wird nicht pixelgenau geprüft (das könnte nur ein
# Screenshot-Vergleich leisten) - hier nur, dass er tatsächlich gesetzt wird (main(),
# nicht separat testbar ohne den echten Startdialog durchzuklicken) und dass die als
# Haupt-Aktion vorgesehenen Buttons den dafür vorgesehenen objectName tragen, über den
# _erzeuge_qss() (siehe app.py, mehrere Themes über _THEMES) sie hervorhebt.


def test_qss_modern_minimal_enthaelt_kernselektoren():
    qss_blau = _erzeuge_qss("blau")
    assert "QTabBar::tab:selected" in qss_blau
    assert "QPushButton#primaerButton" in qss_blau
    assert "#2F6FED" in qss_blau  # Akzentfarbe des Themes "blau"
    assert "#8C5A32" in _erzeuge_qss("lohbraun")  # Standard seit Marco 01.11.2026


def test_programmsymbol_und_selbsttest_schritt(qtbot, tmp_path, monkeypatch):
    """Programmsymbol (Beagle, Marco 07.10.2026): die PNG wird geladen, .ico und .icns für
    Windows bzw. macOS liegen daneben. Fehlt die PNG (z. B. nicht in build.spec/datas),
    meldet der Selbsttest das als Fehler."""
    from PySide6.QtCore import QSize

    import desktop_gemeinsam
    import selbsttest

    symbol = desktop_gemeinsam.programmsymbol()
    assert not symbol.isNull()
    assert symbol.actualSize(QSize(512, 512)) == QSize(512, 512)
    ordner = os.path.dirname(desktop_gemeinsam.programmsymbol_pfad())
    for endung in ("ico", "icns"):
        assert os.path.getsize(os.path.join(ordner, f"programmsymbol.{endung}")) > 10_000

    monkeypatch.setattr(desktop_gemeinsam, "programmsymbol_pfad", lambda: str(tmp_path / "fehlt.png"))
    protokoll = tmp_path / "symbol.log"
    assert selbsttest.fuehre_selbsttest_aus(str(protokoll)) == 1
    assert "FEHLER  Programmsymbol" in protokoll.read_text(encoding="utf-8")


@pytest.mark.parametrize("wechsel, speichern, auswahl", [
    ("_design_wechseln", "app._design_speichern", "kontrast"),
    ("_theme_wechseln", "app._theme_speichern", "gruen"),
])
def test_ansicht_wechseln_zeigt_wartecursor(qtbot, termin, monkeypatch, wechsel, speichern, auswahl):
    # Lasttest 16.10.2026: bei 1000 Teilnehmern dauert der Wechsel rund 3 s.
    from PySide6.QtCore import Qt as QtCore_Qt
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    gespeichert = []
    cursor_waehrenddessen = []

    def cursor_merken(*_a, **_k):
        cursor = QApplication.overrideCursor()
        cursor_waehrenddessen.append(cursor.shape() if cursor is not None else None)

    # Speichern abgeklemmt: der Test darf die echte Einstellung (Registry) nicht ändern.
    monkeypatch.setattr(speichern, gespeichert.append)
    monkeypatch.setattr("app._darstellung_anwenden", cursor_merken)
    monkeypatch.setattr(fenster, "_farben_auffrischen", cursor_merken)

    getattr(fenster, wechsel)(auswahl)

    assert gespeichert == [auswahl]
    assert cursor_waehrenddessen == [QtCore_Qt.WaitCursor, QtCore_Qt.WaitCursor]
    assert QApplication.overrideCursor() is None


# --- Hilfe-Button ---------------------------------------------------------------


def test_hilfe_suche_markiert_und_springt_weiter(qtbot):
    """UX-Test 2026-11, T8: Das Suchfeld markiert alle Treffer, Enter springt zum nächsten
    und am Ende wieder an den Anfang; ohne Treffer steht „nichts gefunden“."""
    dialog = HilfeDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.suchfeld.setText("Startnummer")
    treffer = len(dialog.anzeige.extraSelections())
    assert treffer > 2 and dialog.treffer_label.text() == f"{treffer} Treffer"
    erste = dialog.anzeige.textCursor().selectionStart()
    qtbot.keyClick(dialog.suchfeld, Qt.Key_Return)
    zweite = dialog.anzeige.textCursor().selectionStart()
    assert zweite > erste and dialog.isVisible()  # Enter schließt das Fenster nicht
    for _ in range(treffer - 1):
        dialog.weitersuchen()
    assert dialog.anzeige.textCursor().selectionStart() == erste  # wieder von vorn
    dialog.suchfeld.setText("xyzgibtsnicht")
    assert dialog.anzeige.extraSelections() == [] and dialog.treffer_label.text() == "nichts gefunden"
    vorher = dialog.anzeige.textCursor().position()
    dialog.weitersuchen()  # ohne Treffer kein Sprung an den Anfang
    assert dialog.anzeige.textCursor().position() == vorher
    dialog.suchfeld.clear()
    assert dialog.treffer_label.text() == ""


def test_hilfe_suche_bevorzugt_wortanfaenge_und_kennt_tastenkuerzel(qtbot):
    """Nachtest 2, N6: „USB“ findet „USB-Stick“, nicht „ausbalancierten“; erst ohne solche
    Treffer zählen Wortteile. Abschnitt „Tastenkürzel“ und USB-Stick bei der Sicherung."""
    from desktop_dialoge import _HILFE_HTML, _hilfe_anker

    dialog = HilfeDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.suchfeld.setText("usb")
    treffer = [a.cursor.selectedText() for a in dialog.anzeige.extraSelections()]
    assert treffer and all(t == "USB" for t in treffer)
    assert dialog.treffer_label.text() == f"{len(treffer)} Treffer"
    text = dialog.anzeige.toPlainText()
    for auswahl in dialog.anzeige.extraSelections():
        davor = text[auswahl.cursor.selectionStart() - 1]
        assert not davor.isalnum()  # Wortanfang
    assert dialog.anzeige.extraSelections()[0].format.fontWeight() == QFont.Bold

    dialog.suchfeld.setText("alancier")  # nur mitten im Wort vorhanden
    assert dialog.anzeige.extraSelections()
    assert dialog.treffer_label.text().endswith("(in Wörtern)")
    stellen = [a.cursor.selectionStart() for a in dialog.anzeige.extraSelections()]
    assert dialog.anzeige.textCursor().selectionStart() == stellen[0]
    dialog.weitersuchen()
    erwartet = stellen[1] if len(stellen) > 1 else stellen[0]  # sonst wieder von vorn
    assert dialog.anzeige.textCursor().selectionStart() == erwartet
    assert dialog.anzeige.textCursor().selectedText().lower() == "alancier"

    # Umlaut am Wortanfang, Groß/Klein egal
    dialog.suchfeld.setText("ÜBERALL")
    assert dialog.treffer_label.text().endswith("Treffer")
    # Sonderzeichen am Anfang: kein Wortanfang, kein Fehler, kein „(in Wörtern)“
    dialog.suchfeld.setText("(")
    assert dialog.anzeige.extraSelections() and dialog.treffer_label.text().endswith("Treffer")
    dialog.suchfeld.setText("c++")
    assert dialog.treffer_label.text() == "nichts gefunden"

    assert _hilfe_anker("Tastenkürzel") is not None
    assert "USB-Stick" in _HILFE_HTML.split('<h3>Reiter "Datensicherung"</h3>')[1].split("<h3>")[0]


def test_hilfe_knopf_oeffnet_beim_aktuellen_reiter(qtbot, termin, monkeypatch):
    """Nachtest 2, N6: Der Knopf „Hilfe“ öffnet wie F1 beim Abschnitt des Reiters."""
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    abschnitte = []
    echt = HilfeDialog.__init__

    def _init(self, parent=None, abschnitt=None):
        abschnitte.append(abschnitt)
        echt(self, parent, abschnitt)

    monkeypatch.setattr(HilfeDialog, "__init__", _init)
    monkeypatch.setattr(HilfeDialog, "exec", lambda self: 0)
    fenster._tabs.setCurrentWidget(fenster.zeitplan_tab)
    next(b for b in fenster.findChildren(QPushButton) if b.text() == "Hilfe").click()
    assert abschnitte == ['Reiter "Zeitplan"']


def test_f1_oeffnet_hilfe_beim_aktuellen_reiter(qtbot, termin, monkeypatch):
    """UX-Test 2026-11, T8: F1 („Hilfe → Hilfe anzeigen“) öffnet die Hilfe beim Abschnitt des
    aktuellen Reiters; jeder Reiter hat einen Abschnitt."""
    from desktop_dialoge import _hilfe_anker

    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    for i in range(fenster._tabs.count()):
        assert _hilfe_anker(f'Reiter "{fenster._tabs.tabText(i)}"') is not None, fenster._tabs.tabText(i)

    gezeigt = []

    def _exec(dialog):
        from PySide6.QtCore import QPoint

        dialog.show()
        qtbot.waitUntil(lambda: dialog.anzeige.verticalScrollBar().value() > 0, timeout=WARTEZEIT_MS)
        # Oben im sichtbaren Bereich steht der Abschnitt des Reiters (nicht ein Nachbar).
        oben = dialog.anzeige.cursorForPosition(QPoint(10, 10)).block().text()
        gezeigt.append(oben)
        return 0

    monkeypatch.setattr(HilfeDialog, "exec", _exec)
    fenster._tabs.setCurrentWidget(fenster.zeitplan_tab)
    aktion = next(a for m in fenster.menuBar().findChildren(QMenu) if m.title() == "&Hilfe"
                  for a in m.actions() if a.text() == "Hilfe anzeigen")
    assert aktion.shortcut() == QKeySequence(QKeySequence.HelpContents)
    aktion.trigger()
    assert gezeigt == ['Reiter "Zeitplan"']


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

    hilfe_buttons = [b for b in fenster.findChildren(QPushButton) if b.text() == "Hilfe"]
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

    version_buttons = [b for b in fenster.findChildren(QPushButton) if b.text() == f"Version {VERSION}"]
    assert len(version_buttons) == 1
    version_btn = version_buttons[0]
    assert version_btn.isVisible()
    assert version_btn.height() > 0

    geoeffnet = {}
    monkeypatch.setattr(VersionDialog, "exec", lambda self: geoeffnet.setdefault("ja", True))

    qtbot.mouseClick(version_btn, Qt.MouseButton.LeftButton)

    assert geoeffnet.get("ja") is True


def test_version_tupel_und_neutrale_meldung(qtbot, monkeypatch):
    """Teil 8 Nr. 4: nicht vergleichbare Versionen ergeben eine neutrale Meldung."""

    assert desktop_programm._version_tupel("v1.0.47") == (1, 0, 47)
    for text in ("1.1", "2.0.0-rc1", "dev"):
        assert desktop_programm._version_tupel(text) is None
    monkeypatch.setattr(desktop_programm, "_neueste_version_pruefen", lambda: ("2.0.0-rc1", None))
    dialog = VersionDialog()
    qtbot.addWidget(dialog)
    dialog._updates_pruefen()
    qtbot.waitUntil(lambda: dialog._updates_btn.isEnabled(), timeout=WARTEZEIT_MS)
    assert dialog._ergebnis_zeile.text().startswith("Neueste veröffentlichte Version: 2.0.0-rc1")
    assert not dialog._download_btn.isHidden()


def test_update_pruefung_zeitgrenze_und_fehler_geben_den_knopf_frei(qtbot, monkeypatch):
    """Teil 8 Nr. 1 und 5: hängt die Abfrage, meldet das Fenster nach der Zeitgrenze; eine
    spätere Antwort wird verworfen. Eine Ausnahme gibt den Knopf ebenfalls frei."""

    import threading

    freigabe = threading.Event()
    monkeypatch.setattr(desktop_programm, "_neueste_version_pruefen", lambda: freigabe.wait(5) and ("9.9.9", None))
    monkeypatch.setattr(VersionDialog, "UPDATE_ZEITGRENZE_MS", 100)
    dialog = VersionDialog()
    qtbot.addWidget(dialog)
    dialog._updates_pruefen()
    assert not dialog._updates_btn.isEnabled()
    qtbot.waitUntil(lambda: dialog._updates_btn.isEnabled(), timeout=WARTEZEIT_MS)
    assert "nicht rechtzeitig" in dialog._ergebnis_zeile.text()
    freigabe.set()
    qtbot.wait(200)
    assert "nicht rechtzeitig" in dialog._ergebnis_zeile.text()

    def kaputt():
        raise AttributeError("x")

    monkeypatch.setattr(desktop_programm, "_neueste_version_pruefen", kaputt)
    monkeypatch.setattr(VersionDialog, "UPDATE_ZEITGRENZE_MS", 15000)
    dialog._updates_pruefen()
    qtbot.waitUntil(lambda: dialog._updates_btn.isEnabled(), timeout=WARTEZEIT_MS)
    assert "fehlgeschlagen (AttributeError)" in dialog._ergebnis_zeile.text()

    # Eine Antwort aus einem früheren Lauf wird verworfen, auch wenn gerade wieder geprüft wird.
    monkeypatch.setattr(desktop_programm, "_neueste_version_pruefen", lambda: freigabe.wait(5) and ("9.9.9", None))
    freigabe.clear()
    dialog._updates_pruefen()
    dialog._update_ergebnis(dialog._update_lauf - 1, ("8.8.8", None))
    assert not dialog._updates_btn.isEnabled() and "8.8.8" not in dialog._ergebnis_zeile.text()
    freigabe.set()
    qtbot.waitUntil(lambda: dialog._updates_btn.isEnabled(), timeout=WARTEZEIT_MS)


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

    neuere_version = ".".join(str(t + 1) for t in desktop_programm._version_tupel(VERSION)[:1]) + ".0.0"
    monkeypatch.setattr(desktop_programm, "_neueste_version_pruefen", lambda: (neuere_version, None))
    assert not dialog._download_btn.isVisible()

    update_buttons = [b for b in dialog.findChildren(QPushButton) if b.text() == "Nach Updates suchen"]
    assert len(update_buttons) == 1
    qtbot.mouseClick(update_buttons[0], Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: dialog._updates_btn.isEnabled(), timeout=WARTEZEIT_MS)  # Abfrage läuft im Hintergrund

    assert neuere_version in dialog._ergebnis_zeile.text()
    assert dialog._download_btn.isVisible()

    geoeffnete_urls = []
    monkeypatch.setattr(app.QDesktopServices, "openUrl", lambda url: geoeffnete_urls.append(url.toString()) or True)
    qtbot.mouseClick(dialog._download_btn, Qt.MouseButton.LeftButton)
    assert geoeffnete_urls == [desktop_programm.GITHUB_RELEASES_URL]


def test_versiondialog_update_button_zeigt_hinweis_wenn_aktuell(qtbot, monkeypatch):
    dialog = VersionDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    monkeypatch.setattr(desktop_programm, "_neueste_version_pruefen", lambda: (VERSION, None))

    update_btn = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Nach Updates suchen")
    qtbot.mouseClick(update_btn, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: dialog._updates_btn.isEnabled(), timeout=WARTEZEIT_MS)  # Abfrage läuft im Hintergrund

    assert "bereits die neueste Version" in dialog._ergebnis_zeile.text()
    assert not dialog._download_btn.isVisible()


def test_versiondialog_update_button_zeigt_fehler_ohne_internet(qtbot, monkeypatch):
    """_neueste_version_pruefen() fängt Netzwerkfehler selbst ab und liefert einen
    Fehlertext statt einer Exception (siehe dortiger Docstring) - der Dialog zeigt diesen
    Text dann einfach an, statt abzustürzen."""

    dialog = VersionDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    monkeypatch.setattr(
        desktop_programm, "_neueste_version_pruefen", lambda: (None, "Keine Verbindung zu GitHub möglich (kein Internetzugang?).")
    )

    update_btn = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Nach Updates suchen")
    qtbot.mouseClick(update_btn, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: dialog._updates_btn.isEnabled(), timeout=WARTEZEIT_MS)  # Abfrage läuft im Hintergrund

    assert "Keine Verbindung" in dialog._ergebnis_zeile.text()
    assert not dialog._download_btn.isVisible()


def test_versiondialog_releases_seite_button_oeffnet_browser_ohne_netzwerkzugriff(qtbot, monkeypatch):
    """Der separate Link "Download-Seite im Browser öffnen" bleibt als manueller
    Rückfallweg bestehen (z. B. falls die automatische Prüfung fehlschlägt) und ruft
    dabei NIE die GitHub-API auf, sondern öffnet direkt den Browser."""
    import app

    dialog = VersionDialog()
    qtbot.addWidget(dialog)
    dialog.show()

    aufgerufen = {}
    monkeypatch.setattr(desktop_programm, "_neueste_version_pruefen", lambda: aufgerufen.setdefault("ja", True))
    geoeffnete_urls = []
    monkeypatch.setattr(app.QDesktopServices, "openUrl", lambda url: geoeffnete_urls.append(url.toString()) or True)

    seite_btn = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Download-Seite im Browser öffnen")
    qtbot.mouseClick(seite_btn, Qt.MouseButton.LeftButton)

    assert geoeffnete_urls == [desktop_programm.GITHUB_RELEASES_URL]
    assert "ja" not in aufgerufen


def test_versiondialog_enter_schliesst_nach_dem_zeigen(qtbot):
    """UX-Test 2026-11, T9: Im Nachtest öffnete Enter „Lizenzen“ - nach dem Zeigen liegt der
    Fokus auf „Schließen“, Enter schließt das Fenster."""
    dialog = VersionDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    schliessen = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Schließen")
    assert dialog.focusWidget() is schliessen
    qtbot.keyClick(dialog.focusWidget(), Qt.Key_Return)
    assert dialog.result() == QDialog.Accepted


def test_versiondialog_enter_nach_updatesuche_kopiert_keine_diagnose(qtbot, monkeypatch):
    """Verifikation B3: Nach einem Klick auf „Nach Updates suchen“ lag der Fokus beim Sperren auf
    „Diagnose kopieren“ - Enter kopierte dann die Diagnose. Jetzt während der Suche auf
    „Schließen“, danach wieder auf dem Suchknopf."""
    import threading

    freigabe = threading.Event()
    monkeypatch.setattr(desktop_programm, "_neueste_version_pruefen",
                        lambda: (freigabe.wait(5), (VERSION, None))[1])
    dialog = VersionDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    dialog._updates_btn.setFocus()
    qtbot.mouseClick(dialog._updates_btn, Qt.MouseButton.LeftButton)
    assert dialog.focusWidget() is dialog._schliessen_btn
    freigabe.set()
    qtbot.waitUntil(lambda: dialog._updates_btn.isEnabled(), timeout=WARTEZEIT_MS)
    assert dialog.focusWidget() is dialog._updates_btn
    assert dialog._diagnose_status.text() == ""


def test_versiondialog_fehlerknoepfe_in_eigenem_bereich(qtbot):
    """UX-Test 2026-11, T9: Diagnose und Protokoll-Ordner stehen im Bereich „Für Fehlermeldungen“."""
    from PySide6.QtWidgets import QGroupBox

    dialog = VersionDialog()
    qtbot.addWidget(dialog)
    bereich = next(g for g in dialog.findChildren(QGroupBox) if g.title() == "Für Fehlermeldungen")
    knoepfe = {b.text() for b in bereich.findChildren(QPushButton)}
    assert knoepfe == {"Diagnose kopieren", "Protokoll-Ordner öffnen"}


def test_hilfe_menue_nach_updates_suchen_prueft_sofort(qtbot, termin, monkeypatch):
    """UX-Test 2026-11, T9: „Hilfe → Nach Updates suchen…“ öffnet das Versionsfenster und
    startet die Suche gleich."""
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    monkeypatch.setattr(desktop_programm, "_neueste_version_pruefen", lambda: (VERSION, None))
    geoeffnet = []

    def _exec(dialog):
        geoeffnet.append(dialog)
        qtbot.waitUntil(lambda: "neueste Version" in dialog._ergebnis_zeile.text(), timeout=WARTEZEIT_MS)
        return 0

    monkeypatch.setattr(VersionDialog, "exec", _exec)
    hilfe = next(m for m in fenster.menuBar().findChildren(QMenu) if m.title() == "&Hilfe")
    aktionen = {a.text(): a for a in hilfe.actions()}
    assert set(aktionen) == {"Hilfe anzeigen", "Nach Updates suchen…", "Version und Lizenzen"}
    aktionen["Nach Updates suchen…"].trigger()
    assert len(geoeffnet) == 1

    # Die beiden anderen Einträge öffnen Hilfe bzw. Versionsfenster (ohne Suche).
    monkeypatch.setattr(VersionDialog, "exec", lambda dialog: geoeffnet.append(dialog) or 0)
    aktionen["Version und Lizenzen"].trigger()
    assert len(geoeffnet) == 2 and geoeffnet[-1]._updates_btn.isEnabled()
    hilfe_geoeffnet = []
    monkeypatch.setattr(HilfeDialog, "exec", lambda dialog: hilfe_geoeffnet.append(dialog) or 0)
    aktionen["Hilfe anzeigen"].trigger()
    assert len(hilfe_geoeffnet) == 1


def test_versiondialog_lizenz_zeile_und_button_oeffnet_lizenzdialog(qtbot, monkeypatch):
    """OFFEN B14 (Marco 01.11.2026): das Versionsfenster nennt die MIT-Lizenz, der Button
    "Lizenzen anzeigen" öffnet das Lizenzfenster."""
    dialog = VersionDialog()
    qtbot.addWidget(dialog)
    assert any(l.text() == "Lizenz: MIT (© 2026 Marco)" for l in dialog.findChildren(QLabel))

    geoeffnet = []
    monkeypatch.setattr(desktop_programm.LizenzDialog, "exec", lambda self: geoeffnet.append(self) or QDialog.Accepted)
    lizenz_btn = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Lizenzen anzeigen")
    qtbot.mouseClick(lizenz_btn, Qt.MouseButton.LeftButton)

    assert len(geoeffnet) == 1
    assert isinstance(geoeffnet[0], desktop_programm.LizenzDialog)
    assert geoeffnet[0].windowTitle() == "Lizenzen"


def test_lizenzdialog_zeigt_eigene_lizenz_und_fremdkomponenten(qtbot, tmp_path, monkeypatch):
    """OFFEN B14: oben die echte LICENSE aus dem Repo, darunter THIRD_PARTY_LICENSES.txt;
    fehlt diese (Quellcode-Fassung), steht dort ein Hinweis statt eines Fehlers."""
    monkeypatch.setattr(desktop_programm, "_drittlizenzen_pfad", lambda: str(tmp_path / "fehlt.txt"))
    dialog = desktop_programm.LizenzDialog()
    qtbot.addWidget(dialog)
    text = dialog.text_feld.toPlainText()
    assert dialog.text_feld.isReadOnly()
    assert "MIT License" in text and "Copyright (c) 2026 Marco" in text
    assert "THIRD_PARTY_LICENSES.txt) wird beim Bauen des Programms erzeugt" in text
    assert text.index("MIT License") < text.index("THIRD_PARTY_LICENSES.txt")

    drittlizenzen = tmp_path / "THIRD_PARTY_LICENSES.txt"
    drittlizenzen.write_text("Übersicht / Overview:\n  PySide6 6.9.0 - LGPL-3.0\n<b>kein HTML</b>\n", encoding="utf-8")
    monkeypatch.setattr(desktop_programm, "_drittlizenzen_pfad", lambda: str(drittlizenzen))
    dialog = desktop_programm.LizenzDialog()
    qtbot.addWidget(dialog)
    text = dialog.text_feld.toPlainText()
    assert "Übersicht / Overview:\n  PySide6 6.9.0 - LGPL-3.0" in text
    assert "<b>kein HTML</b>" in text
    assert "wird beim Bauen des Programms erzeugt" not in text

    monkeypatch.setattr(desktop_programm, "_lizenz_pfad", lambda: str(tmp_path))  # Ordner: OSError
    dialog = desktop_programm.LizenzDialog()
    qtbot.addWidget(dialog)
    assert "Der Lizenztext (LICENSE) fehlt" in dialog.text_feld.toPlainText()


def test_klartext_fuer_typische_datenbankfehler():
    import sqlite3 as _sqlite3

    from desktop_gemeinsam import _klartext_fehler

    assert "schreibgeschützt" in _klartext_fehler(_sqlite3.OperationalError("attempt to write a readonly database"))
    assert "gesperrt" in _klartext_fehler(_sqlite3.OperationalError("database is locked"))
    assert "voll" in _klartext_fehler(_sqlite3.OperationalError("database or disk is full"))
    assert "Ordner fehlt" in _klartext_fehler(_sqlite3.OperationalError("unable to open database file"))
    assert "(Technisch: database is locked)" in _klartext_fehler(_sqlite3.OperationalError("database is locked"))
    assert _klartext_fehler(_sqlite3.OperationalError("no such table: x")) == "no such table: x"
    assert _klartext_fehler(ValueError("readonly")) == "readonly"


def test_klartext_fuer_typische_dateifehler():
    """Teil 9 Nr. 6, Teil 5 Nr. 4: Dateifehler in Klartext, Pfad ohne doppelte Backslashes."""
    import errno

    from desktop_gemeinsam import _klartext_fehler

    pfad = os.path.join("C:" + os.sep, "Ordner", "liste.csv")
    gesperrt = _klartext_fehler(PermissionError(errno.EACCES, "Permission denied", pfad))
    assert "in einem anderen Programm geöffnet" in gesperrt
    assert f"(Technisch: Permission denied: {os.path.normpath(pfad)})" in gesperrt
    assert "\\\\" not in gesperrt
    assert "nicht gefunden" in _klartext_fehler(FileNotFoundError(errno.ENOENT, "No such file", pfad))
    assert _klartext_fehler(OSError(errno.ENOSPC, "No space left on device")).startswith("Der Datenträger ist voll.")
    assert _klartext_fehler(OSError(errno.EIO, "I/O error")) == "I/O error"


def test_fehlertext_protokolliert_nur_programmfehler(monkeypatch):
    """Teil 9 Nr. 5: breite Fänger nennen bei Programmfehlern den Typ und schreiben sie ins
    Protokoll; Datei- und Datenbankfehler sind erwartbar."""
    import desktop_gemeinsam

    protokolliert = []
    monkeypatch.setattr(desktop_gemeinsam, "fehler_protokollieren", protokolliert.append)
    programmfehler = KeyError("Albers")
    text = desktop_gemeinsam._fehlertext(programmfehler)
    assert "KeyError: 'Albers'" in text and "Diagnose kopieren" in text
    assert protokolliert == [programmfehler]

    assert "anderen Programm" in desktop_gemeinsam._fehlertext(PermissionError(13, "Permission denied"))
    assert protokolliert == [programmfehler]


def test_url_oeffnen_meldet_fehlschlag(qtbot, monkeypatch):
    """Teil 9 Nr. 10: liefert openUrl False, kommt eine Meldung mit dem Pfad."""
    import desktop_gemeinsam

    meldungen = []
    monkeypatch.setattr(desktop_gemeinsam.QMessageBox, "warning", lambda *a, **k: meldungen.append(a[2]))
    monkeypatch.setattr(desktop_gemeinsam.QDesktopServices, "openUrl", lambda url: False)
    assert desktop_gemeinsam._url_oeffnen(None, desktop_gemeinsam.QUrl("https://example.org"),
                                          "https://example.org") is False
    assert meldungen and "https://example.org" in meldungen[0]

    monkeypatch.setattr(desktop_gemeinsam.QDesktopServices, "openUrl", lambda url: True)
    assert desktop_gemeinsam._url_oeffnen(None, desktop_gemeinsam.QUrl("https://example.org"), "x") is True
    assert len(meldungen) == 1


def test_reiterwechsel_bei_schreibfehler_wechselt_trotzdem(qtbot, termin, monkeypatch):
    """Der Reiterwechsel läuft trotz Schreibfehler weiter; die Eingaben bleiben ungespeichert
    stehen (vorher blieb _vorheriger_tab_index stehen und der neue Reiter lud nicht neu)."""
    conn, pfad = termin
    _teilnehmer_anlegen(conn, nachname="Zorn", startnummer=1, disziplin="Flächensuche")
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    tab = fenster.ergebnis_tab
    fenster._tabs.setCurrentWidget(tab)
    tab.punkte_eintragen(0, "Flächensuche", "58", "38")
    monkeypatch.setattr("desktop_ergebnis_speichern.eintragen_ergebnis", _schreibfehler)
    ueberall_ersetzen(monkeypatch, "_db_fehler_anzeigen", lambda *a, **k: None)
    rueckfragen_beantworten(monkeypatch, QMessageBox.Yes)

    fenster._tabs.setCurrentIndex(0)

    assert fenster._vorheriger_tab_index == 0
    assert tab.hat_ungespeicherte_aenderungen()


def test_dialoge_fokus_und_groesse(qtbot, tmp_path, monkeypatch):
    """Teil 2 Nr. 6 und 7: Fokus im ersten Eingabefeld (auch nach der Pflichtfeld-Meldung),
    Veranstaltungsdialog auf den Bildschirm begrenzt."""
    teilnehmer = TeilnehmerDialog(vergebene_nummern=set())
    qtbot.addWidget(teilnehmer)
    teilnehmer.show()
    assert teilnehmer.focusWidget() is teilnehmer.nachname
    teilnehmer.nachname.setText("Muster")
    meldungen_stumm(monkeypatch, "warning")
    teilnehmer._pruefen_und_akzeptieren()
    assert teilnehmer.focusWidget() is teilnehmer.vorname

    veranstaltung = _neuer_termin_dialog(qtbot, tmp_path, monkeypatch)
    veranstaltung.show()
    assert veranstaltung.focusWidget() is veranstaltung.verein
    frei = veranstaltung.screen().availableGeometry()
    assert veranstaltung.height() <= int(frei.height() * DIALOG_MAX_HOEHE_ANTEIL) + 1


def test_a9_kleinigkeiten(qtbot, monkeypatch):
    """UX-Test 03.11.2026, X14/X15: Pflichtfeld-Meldung nennt nur die fehlenden Felder,
    „14.11.26“ wird zu 14.11.2026, die Hilfe hat ein Inhaltsverzeichnis und nennt den
    Papierkorb, das Versionsfenster schließt mit Enter."""
    from desktop_dialoge import _HILFE_HTML, _hilfe_mit_inhaltsverzeichnis
    from desktop_programm import VersionDialog as _VersionDialog

    dialog = TeilnehmerDialog(vergebene_nummern=set())
    qtbot.addWidget(dialog)
    dialog.nachname.setText("Muster")
    warnungen = meldungen_sammeln(monkeypatch, "warning")
    dialog._pruefen_und_akzeptieren()
    assert warnungen == ["Bitte noch ausfüllen: „Vorname“, „Rufname Hund“."]
    dialog.vorname.setText("Max")
    warnungen.clear()
    dialog._pruefen_und_akzeptieren()
    assert warnungen == ["Bitte noch „Rufname Hund“ ausfüllen."]

    termin_dialog = VeranstaltungsDialog(vorbelegung={"verein": "HSV", "datum": "2026-11-14"}, bearbeiten=True)
    qtbot.addWidget(termin_dialog)
    termin_dialog.datum.setText("14.11.26")
    termin_dialog._jahr_ergaenzen()
    assert termin_dialog.datum.text() == "14.11.2026"

    html = _hilfe_mit_inhaltsverzeichnis(_HILFE_HTML)
    assert "<b>Inhalt:</b>" in html and 'href="#abschnitt0"' in html and 'name="abschnitt0"' in html
    assert "Papierkorb" in _HILFE_HTML and "unwiderruflich" not in _HILFE_HTML
    assert "gewählten Richter" not in _HILFE_HTML

    version = _VersionDialog()
    qtbot.addWidget(version)
    schliessen = next(b for b in version.findChildren(QPushButton) if b.text() == "Schließen")
    assert schliessen.isDefault()
    # Abschluss-QS A11: Enter auf einem anderen fokussierten Knopf löst diesen aus, nicht „Schließen“.
    geklickt = []
    updates = next(b for b in version.findChildren(QPushButton) if b.text() == "Nach Updates suchen")
    updates.clicked.disconnect()
    updates.clicked.connect(lambda: geklickt.append(True))
    version.show()
    updates.setFocus()
    qtbot.keyClick(updates, Qt.Key_Return)
    assert geklickt and version.result() == 0


def test_ja_nein_setzt_vorgabe_und_wertet_antwort_aus(monkeypatch):
    """Abschluss-QS 15.10.2026 (A19c): gemeinsamer Helfer für Ja/Nein-Rückfragen - Vorgabe
    „Nein“, außer ausdrücklich „Ja“ gewünscht; nur „Ja“ ergibt True."""
    import desktop_gemeinsam

    aufrufe = []
    antwort = [QMessageBox.Yes]
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: aufrufe.append(a) or antwort[0])

    assert desktop_gemeinsam._ja_nein(None, "Titel", "Text?") is True
    assert aufrufe[-1] == (None, "Titel", "Text?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    assert desktop_gemeinsam._ja_nein(None, "T", "X", vorgabe_ja=True) is True
    assert aufrufe[-1][4] == QMessageBox.Yes
    for antwort[0] in (QMessageBox.No, QMessageBox.Cancel, QMessageBox.NoButton):  # Esc/Schließen
        assert desktop_gemeinsam._ja_nein(None, "T", "X") is False


def test_dialoge_werden_nach_exec_freigegeben_und_wartecursor_zurueckgesetzt(qtbot, monkeypatch):
    """Desktop-Prüfung 14.10.2026, Teil 2 Nr. 9, Teil 6 Nr. 7/8: Dialoge bleiben nicht als
    Kinder liegen; der Wartecursor wird auch bei einem Fehler zurückgesetzt."""
    import app
    from PySide6.QtWidgets import QApplication, QWidget

    import desktop_gemeinsam

    eltern = QWidget()
    qtbot.addWidget(eltern)
    dialog = QDialog(eltern)
    monkeypatch.setattr(dialog, "exec", lambda: QDialog.Accepted)
    assert desktop_gemeinsam._ausfuehren(dialog) == QDialog.Accepted
    qtbot.waitUntil(lambda: not eltern.findChildren(QDialog), timeout=WARTEZEIT_MS)

    # Echte Aufrufstelle: das Versionsfenster bleibt nicht als Kind des Hauptfensters liegen.
    monkeypatch.setattr(VersionDialog, "exec", lambda self: QDialog.Rejected)
    fenster = QWidget()
    qtbot.addWidget(fenster)
    app.HauptFenster._version_anzeigen(fenster)
    qtbot.waitUntil(lambda: not fenster.findChildren(VersionDialog), timeout=WARTEZEIT_MS)

    with pytest.raises(RuntimeError):
        with desktop_gemeinsam._wartecursor():
            assert QApplication.overrideCursor() is not None
            raise RuntimeError("Export kaputt")
    assert QApplication.overrideCursor() is None


def test_reiterwechsel_abbrechen_bleibt_in_der_ergebniserfassung(qtbot, termin, monkeypatch):
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster._tabs.setCurrentWidget(fenster.ergebnis_tab)
    monkeypatch.setattr(type(fenster.ergebnis_tab), "hat_ungespeicherte_aenderungen", lambda self: True)
    rueckfragen_beantworten(monkeypatch, QMessageBox.Cancel)

    fenster._tabs.setCurrentWidget(fenster.teilnehmer_tab)

    assert fenster._tabs.currentWidget() is fenster.ergebnis_tab
    assert fenster._tabs.widget(fenster._vorheriger_tab_index) is fenster.ergebnis_tab


# --- Sicherheitskorrektur Q-1 (07.10.2026), Details folgen ----


@pytest.mark.parametrize("aktion, ziel", [("ueberschreiben", "Pruefung.sqlite"), ("kopie", "pruefung (2).sqlite")])
def test_q1_wiederherstellen_konflikt_wird_abgefragt(tmp_path, aktion, ziel):
    (tmp_path / "Pruefung.sqlite").write_bytes(b"")
    abgefragt = []

    def aktion_fuer(name):
        abgefragt.append(name)
        return aktion

    entscheidungen, _ = _wiederherstellungsziele_planen(
        ["pruefung.sqlite"], {"Pruefung.sqlite"}, tmp_path, aktion_fuer
    )

    assert abgefragt == ["pruefung.sqlite"]
    assert entscheidungen == {"pruefung.sqlite": ziel}


def test_q1_offener_termin_wird_erkannt(qtbot, tmp_path, monkeypatch):
    (tmp_path / "Pruefung.sqlite").write_bytes(b"")
    ueberall_ersetzen(monkeypatch, "termine_ordner", lambda: tmp_path)
    monkeypatch.setattr("app.QFileDialog.getOpenFileName", lambda *a, **k: ("sicherung.zip", ""))
    monkeypatch.setattr("desktop_verwaltung.sicherung_inhalt", lambda *a, **k: ["pruefung.sqlite"])
    tab = DatensicherungTab(aktueller_pfad=str(tmp_path / "Pruefung.sqlite"))
    qtbot.addWidget(tab)
    abgefragt = []
    monkeypatch.setattr(
        tab, "_konflikt_abfragen",
        lambda name, ist_offener_termin=False: abgefragt.append((name, ist_offener_termin)) or "ueberspringen",
    )

    tab._sicherung_wiederherstellen()

    assert abgefragt == [("pruefung.sqlite", True)]


def test_q1_wiederherstellen_neue_eintraege_kollidieren_nicht(tmp_path):
    entscheidungen, _ = _wiederherstellungsziele_planen(
        ["A.sqlite", "a.sqlite"], set(), tmp_path, lambda name: pytest.fail("keine Rückfrage erwartet")
    )

    assert entscheidungen == {"A.sqlite": "A.sqlite", "a.sqlite": "a (2).sqlite"}


def test_ansicht_menue_schriftgroesse_vergroessert_und_bleibt_gespeichert(qtbot, termin, darstellung_speicher):
    """UX-Test 03.11.2026, X2: „Ansicht → Schriftgröße“ vergrößert die Anwendungsschrift und
    die an die Breite angepassten Beschriftungen; „Normal“ stellt den Ausgangswert wieder her."""
    import desktop_darstellung as darstellung

    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.resize(1400, 820)
    fenster.show()
    assert set(fenster._schrift_actions) == {"normal", "gross", "sehr_gross"}
    assert fenster._schrift_actions["normal"].isChecked()
    _darstellung_anwenden(QApplication.instance())
    basis = QApplication.instance().font().pointSizeF()
    label_pt = fenster._schrift_pt

    fenster._schrift_actions["sehr_gross"].trigger()
    assert darstellung_speicher["schrift"] == "sehr_gross"
    assert darstellung.schrift_faktor() == 1.3
    assert QApplication.instance().font().pointSizeF() == pytest.approx(basis * 1.3, abs=0.1)
    assert fenster._schrift_pt == pytest.approx(label_pt * 1.3, abs=0.1)

    fenster._schrift_actions["normal"].trigger()
    assert QApplication.instance().font().pointSizeF() == pytest.approx(basis, abs=0.1)
    assert fenster._schrift_pt == pytest.approx(label_pt, abs=0.1)


def test_ansicht_menue_hat_hintergrund_und_akzentfarbe(qtbot, termin, darstellung_speicher):
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)

    assert set(fenster._design_actions) == {"beagle", "hell", "dunkel", "kontrast"}
    assert set(fenster._theme_actions) == {"lohbraun", "blau", "gruen", "violett"}
    assert fenster._design_actions["hell"].isChecked()
    assert fenster._theme_actions["blau"].isChecked()


def test_designwechsel_setzt_stylesheet_und_speichert(qtbot, termin, darstellung_speicher):
    import desktop_darstellung as darstellung

    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    qapp = QApplication.instance()

    fenster._design_actions["dunkel"].trigger()
    assert darstellung_speicher["design"] == "dunkel"
    assert qapp.styleSheet() == _erzeuge_qss("blau", "dunkel")
    assert darstellung._aktueller_stil.lower() == "fusion"
    assert darstellung._aktives_design == "dunkel"

    fenster._theme_actions["gruen"].trigger()
    assert darstellung_speicher["theme"] == "gruen"
    assert qapp.styleSheet() == _erzeuge_qss("gruen", "dunkel")

    fenster._design_actions["hell"].trigger()
    assert qapp.styleSheet() == _erzeuge_qss("gruen", "hell")
    assert darstellung._aktives_design == "hell"
    assert darstellung._aktueller_stil == darstellung._ursprung_stil


def test_designwechsel_behaelt_ungespeicherte_ergebnisse(qtbot, termin, darstellung_speicher):
    """Die Ergebniserfassung wird beim Designwechsel nur umgefärbt, nicht neu geladen -
    eine noch nicht gespeicherte Eingabe bleibt erhalten und bekommt die neue Farbe."""
    import desktop_darstellung as darstellung

    conn, pfad = termin
    _teilnehmer_anlegen(conn, nachname="Zorn", startnummer=1, disziplin="Flächensuche")
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    tab = fenster.ergebnis_tab

    tab.punkte_eintragen(0, "Flächensuche", "58", "38")
    assert tab.zeile_ungespeichert(0)

    fenster._design_actions["dunkel"].trigger()

    assert tab.punkte(0, "Flächensuche") == ("58", "38")
    assert tab.zeile_ungespeichert(0)
    dunkel_gelb = darstellung._DESIGNS["dunkel"]["ungespeichert_bg"].lower()
    assert tab.zellzustand(0, "Flächensuche", "suche")["hintergrund"] == dunkel_gelb


def test_rueckweg_zu_hell_stellt_ursprungsstil_her(qtbot, termin, darstellung_speicher, monkeypatch):
    """Unter offscreen ist der Ursprungsstil ohnehin "fusion" - damit der Rückweg
    Dunkel -> Hell wirklich einen Stilwechsel prüft, wird hier "windows" als
    Ursprungsstil vorgegeben (auf allen Plattformen verfügbar)."""
    import desktop_darstellung as darstellung

    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    qapp = QApplication.instance()
    darstellung._darstellung_anwenden(qapp)  # Ursprung erfassen
    monkeypatch.setattr(darstellung, "_ursprung_stil", "windows")

    fenster._design_actions["dunkel"].trigger()
    assert darstellung._aktueller_stil == "fusion"
    fenster._design_actions["hell"].trigger()
    assert darstellung._aktueller_stil == "windows"
    qapp.setStyleSheet("")
    assert qapp.style().name().lower() == "windows"


def test_design_ohne_beschreibbaren_hakenordner_startet_trotzdem(darstellung_speicher, monkeypatch, tmp_path):
    """Kann das Häkchen-Bild nicht geschrieben werden, darf das weder den Start noch den
    Designwechsel abbrechen."""
    import desktop_darstellung as darstellung

    unmoeglich = tmp_path / "datei_statt_ordner"
    unmoeglich.write_text("x")
    monkeypatch.setattr(darstellung, "_haken_pfad", lambda: str(unmoeglich / "unter" / "haken.png"))
    darstellung_speicher["design"] = "dunkel"

    darstellung._darstellung_anwenden(QApplication.instance())

    assert darstellung._aktives_design == "dunkel"
    assert QApplication.instance().styleSheet() == _erzeuge_qss("blau", "dunkel")


def test_hell_bleibt_hell_bei_dunklem_systemschema(darstellung_speicher):
    """Desktop-Prüfung 14.10.2026, Teil 9 Nr. 1: Bei dunklem System-Farbschema ("Apps:
    dunkel") lieferte "hell" dunkle Scrollbereiche/Listen mit fast schwarzer Schrift. "hell"
    setzt jetzt eine feste helle Palette, egal welche Palette vorher galt."""
    import desktop_darstellung as darstellung
    from PySide6.QtGui import QColor

    qapp = QApplication.instance()
    dunkel = QPalette()
    for rolle, farbe in ((QPalette.Window, "#1e1e1e"), (QPalette.Base, "#2d2d2d"),
                         (QPalette.WindowText, "#ffffff"), (QPalette.Text, "#ffffff")):
        dunkel.setColor(rolle, QColor(farbe))
    qapp.setPalette(dunkel)
    darstellung_speicher["design"] = "hell"

    darstellung._darstellung_anwenden(qapp)

    palette = qapp.palette()
    assert palette.color(QPalette.Window).lightness() > 200
    assert palette.color(QPalette.Base).lightness() > 200
    assert palette.color(QPalette.WindowText).lightness() < 100
    assert palette.color(QPalette.Text).lightness() < 100
    hinweise = qapp.styleHints()
    if hasattr(Qt, "ColorScheme") and hasattr(hinweise, "setColorScheme"):
        darstellung_speicher["design"] = "dunkel"
        darstellung._darstellung_anwenden(qapp)
        assert qapp.palette().color(QPalette.Base).lightness() < 100


def test_stylesheet_parst_mit_sonderzeichen_im_hakenpfad(qtbot, darstellung_speicher, monkeypatch):
    """Desktop-Prüfung 14.10.2026, Teil 9 Nr. 2: Ein Umlaut oder Apostroph im Pfad des
    Häkchen-Bildes ließ Qt ohne Anführungszeichen das ganze Stylesheet verwerfen ("Could not
    parse application stylesheet") - für alle 12 Kombinationen prüfen."""
    import desktop_darstellung as darstellung
    from PySide6.QtCore import qInstallMessageHandler
    from PySide6.QtWidgets import QCheckBox, QListWidget, QListWidgetItem

    monkeypatch.setattr(darstellung, "_haken_pfad", lambda: "C:/Users/Jürgen O'Brien (x)/SHS/haken.png")
    meldungen = []
    alter_handler = qInstallMessageHandler(lambda _art, _kontext, text: meldungen.append(text))
    qapp = QApplication.instance()
    try:
        for theme in darstellung._THEMES:
            for design in darstellung._DESIGNS:
                qapp.setStyleSheet(darstellung._erzeuge_qss(theme, design))
                box = QCheckBox("x")
                liste = QListWidget()
                eintrag = QListWidgetItem("y", liste)
                eintrag.setCheckState(Qt.Checked)
                qtbot.addWidget(box)
                qtbot.addWidget(liste)
                box.ensurePolished()
                liste.ensurePolished()
                assert not [m for m in meldungen if "Could not parse" in m], (theme, design, meldungen)
    finally:
        qInstallMessageHandler(alter_handler)


def test_haken_bild_wird_je_lauf_neu_geschrieben(darstellung_speicher, monkeypatch, tmp_path):
    """Desktop-Prüfung 14.10.2026, Teil 9 Nr. 3: eine schon vorhandene Datei wird nicht
    ungeprüft übernommen, sondern beim ersten Bedarf im Lauf ersetzt."""
    import desktop_darstellung as darstellung
    from PySide6.QtGui import QImage

    ziel = tmp_path / "SHS" / "haken.png"
    ziel.parent.mkdir()
    ziel.write_bytes(b"fremd")
    monkeypatch.setattr(darstellung, "_haken_pfad", lambda: str(ziel).replace("\\", "/"))
    monkeypatch.setattr(darstellung, "_haken_geschrieben", False)

    darstellung._haken_bild_bereitstellen()

    bild = QImage(str(ziel))
    assert not bild.isNull() and bild.width() == 32
    assert list(ziel.parent.iterdir()) == [ziel]
    assert darstellung._haken_geschrieben


def test_haken_bild_fehlschlag_hinterlaesst_keine_zwischendatei(darstellung_speicher, monkeypatch, tmp_path):
    """Scheitert das Ersetzen, bleibt keine .tmp-Datei liegen und der nächste Designwechsel
    versucht es erneut."""
    import desktop_darstellung as darstellung

    ziel = tmp_path / "haken.png"
    monkeypatch.setattr(darstellung, "_haken_pfad", lambda: str(ziel).replace("\\", "/"))
    monkeypatch.setattr(darstellung, "_haken_geschrieben", False)

    def ersetzen_scheitert(_quelle, _ziel):
        raise OSError("gesperrt")

    monkeypatch.setattr(darstellung.os, "replace", ersetzen_scheitert)
    darstellung._haken_bild_bereitstellen()

    assert list(tmp_path.iterdir()) == []
    assert not darstellung._haken_geschrieben


def test_standardknoepfe_deutsch(qapp):
    """UX-Test 02.10.2026, U6: Standardknöpfe erscheinen deutsch (Ja/Nein/Abbrechen), auch
    ohne mitgelieferte qtbase_de.qm; andere Texte bleiben unverändert."""
    import desktop_gemeinsam
    from PySide6.QtCore import QCoreApplication

    vorher = list(desktop_gemeinsam._installierte_uebersetzer)
    try:
        desktop_gemeinsam.deutsche_qt_texte_laden(qapp)
        box = QMessageBox()
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        assert sorted(b.text() for b in box.buttons()) == ["&Ja", "&Nein"]
        knoepfe = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        assert sorted(b.text() for b in knoepfe.buttons()) == ["Abbrechen", "OK"]
        assert QCoreApplication.translate("IrgendeinKontext", "Hallo") == "Hallo"
    finally:
        for uebersetzer in desktop_gemeinsam._installierte_uebersetzer[len(vorher):]:
            qapp.removeTranslator(uebersetzer)
        desktop_gemeinsam._installierte_uebersetzer[:] = vorher


def test_absturzprotokoll_schreibt_start_und_unbehandelte_fehler(tmp_path, monkeypatch):
    """UX-Test 02.10.2026, P1: Startzeile und unbehandelte Fehler landen im
    Absturzprotokoll; eine zu große Datei beginnt von vorn."""
    import faulthandler
    import sys

    import desktop_gemeinsam

    aktiviert = {}
    # pytest hat faulthandler selbst aktiv - hier nur den Aufruf prüfen, nicht umbiegen.
    monkeypatch.setattr(faulthandler, "enable", lambda **kw: aktiviert.update(kw))
    monkeypatch.setattr(sys, "excepthook", lambda *a: None)
    monkeypatch.setattr(desktop_gemeinsam, "_ABSTURZPROTOKOLL_MAX_BYTES", 200)
    monkeypatch.setattr(desktop_gemeinsam, "_absturzprotokoll_datei", None)
    monkeypatch.setattr(desktop_gemeinsam, "_absturzprotokoll_pfad", None)

    alt = tmp_path / desktop_gemeinsam.ABSTURZPROTOKOLL_DATEINAME
    alt.write_text("x" * 500, encoding="utf-8")

    pfad = desktop_gemeinsam.absturzprotokoll_einrichten("9.9.9", ordner=tmp_path)
    assert pfad == alt
    # Teil 9 Nr. 4: die zu große Datei wird zur .alt-Datei statt geleert zu werden.
    rotiert = tmp_path / desktop_gemeinsam.ABSTURZPROTOKOLL_ALT_DATEINAME
    assert rotiert.read_text(encoding="utf-8") == "x" * 500
    assert aktiviert["file"] is desktop_gemeinsam._absturzprotokoll_datei

    try:
        raise RuntimeError("Testfehler P1")
    except RuntimeError:
        sys.excepthook(*sys.exc_info())
    desktop_gemeinsam._absturzprotokoll_datei.close()

    inhalt = pfad.read_text(encoding="utf-8")
    assert "x" * 500 not in inhalt
    assert "Version 9.9.9" in inhalt
    assert "RuntimeError: Testfehler P1" in inhalt

    # "Diagnose kopieren" nimmt kurz nach der Rotation das Ende der alten Datei mit.
    assert "x" * 500 in desktop_gemeinsam.diagnose_text("9.9.9")


def test_absturzprotokoll_zaehlt_wiederholungen_und_begrenzt_den_lauf(tmp_path, monkeypatch):
    """Teil 9 Nr. 4: ein wiederkehrender gleicher Fehler steht nur einmal im Protokoll (beim
    Programmende mit Anzahl), und ein Lauf schreibt höchstens _PROTOKOLL_LAUF_MAX_BYTES."""
    import desktop_gemeinsam

    datei = open(tmp_path / "protokoll.txt", "w", encoding="utf-8")
    monkeypatch.setattr(desktop_gemeinsam, "_absturzprotokoll_datei", datei)
    for _ in range(250):
        desktop_gemeinsam.fehler_protokollieren(KeyError("Albers"))
    desktop_gemeinsam._protokoll_eintrag("Qt-Meldung", "QPainter::begin: Paint device returned engine == 0")
    desktop_gemeinsam._wiederholungen_schreiben(datei)

    monkeypatch.setattr(desktop_gemeinsam, "_PROTOKOLL_LAUF_MAX_ZEICHEN", 2000)
    for nummer in range(100):
        desktop_gemeinsam._protokoll_eintrag("Qt-Meldung", f"Warnung {nummer} " + "y" * 50)
    datei.close()

    inhalt = (tmp_path / "protokoll.txt").read_text(encoding="utf-8")
    assert inhalt.count("KeyError: 'Albers'") == 2  # Eintrag + Zeile in der Zusammenfassung
    assert "249× wiederholt: KeyError: 'Albers'" in inhalt
    assert "QPainter::begin" in inhalt
    assert "Protokoll für diesen Programmlauf voll, weitere Einträge" in inhalt
    assert "Warnung 99" not in inhalt and len(inhalt) < 3000


def test_absturzprotokoll_qt_meldungen_eigene_grenze_und_kein_selbstblock(tmp_path, monkeypatch):
    """Verifikation A9: Qt-Meldungen verdrängen keinen späteren Fehler, und ein Eintrag, der
    während des Schreibens im selben Thread entsteht, blockiert nicht."""
    import desktop_gemeinsam

    datei = open(tmp_path / "protokoll.txt", "w", encoding="utf-8")
    monkeypatch.setattr(desktop_gemeinsam, "_absturzprotokoll_datei", datei)
    monkeypatch.setattr(desktop_gemeinsam, "_PROTOKOLL_QT_MAX_ZEICHEN", 500)
    for nummer in range(50):
        desktop_gemeinsam._protokoll_eintrag("Qt-Meldung", f"Warnung {nummer}", qt_meldung=True)

    class _Schreiber:
        """Simuliert eine Qt-Warnung, die beim Schreiben im selben Thread entsteht."""
        def write(self, text):
            desktop_gemeinsam._protokoll_eintrag("Qt-Meldung", "verschachtelt", qt_meldung=True)
            datei.write(text)

        def flush(self):
            datei.flush()

    monkeypatch.setattr(desktop_gemeinsam, "_absturzprotokoll_datei", _Schreiber())
    desktop_gemeinsam.fehler_protokollieren(RuntimeError("später echter Fehler"))
    datei.close()
    inhalt = (tmp_path / "protokoll.txt").read_text(encoding="utf-8")
    assert "weitere Qt-Meldungen entfallen" in inhalt and "Warnung 49" not in inhalt
    assert "RuntimeError: später echter Fehler" in inhalt and "verschachtelt" not in inhalt


def test_qt_warnungen_landen_im_absturzprotokoll(qtbot, tmp_path, monkeypatch):
    """Teil 9 Nr. 8: Qt-Warnungen gehen im installierten Programm nicht mehr verloren;
    Debug-Meldungen bleiben draußen."""
    from PySide6.QtCore import qDebug, qInstallMessageHandler, qWarning

    import desktop_gemeinsam

    datei = open(tmp_path / "protokoll.txt", "w", encoding="utf-8")
    monkeypatch.setattr(desktop_gemeinsam, "_absturzprotokoll_datei", datei)
    alter_handler = desktop_gemeinsam.qt_meldungen_protokollieren()
    try:
        qWarning("Could not parse application stylesheet")
        qDebug("nur Debug")
    finally:
        qInstallMessageHandler(alter_handler)
    datei.close()
    inhalt = (tmp_path / "protokoll.txt").read_text(encoding="utf-8")
    assert "Qt-Meldung" in inhalt and "Could not parse application stylesheet" in inhalt
    assert "nur Debug" not in inhalt


def test_absturzprotokoll_ohne_schreibrecht_startet_trotzdem(tmp_path):
    """Kann das Protokoll nicht angelegt werden, liefert die Funktion None, statt den
    Programmstart abzubrechen."""
    import desktop_gemeinsam

    unmoeglich = tmp_path / "datei_statt_ordner"
    unmoeglich.write_text("x")
    assert desktop_gemeinsam.absturzprotokoll_einrichten("9.9.9", ordner=unmoeglich) is None


def test_diagnose_text_ohne_benutzerpfad_und_mit_protokollende(tmp_path, monkeypatch):
    """Rückmeldung 13.10.2026: Diagnose zum Kopieren - Version, System, Ende des
    Absturzprotokolls; der Benutzerordner erscheint nur als "~", der Benutzername als
    "<Benutzer>" - auch in repr()-Schreibweise und anderer Groß-/Kleinschreibung."""
    from pathlib import Path

    import desktop_gemeinsam

    heim = tmp_path / "Benutzer" / "MaxMuster"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: heim))
    monkeypatch.setenv("USERNAME", "MaxMuster")
    protokoll = heim / "SHS-Pruefungsprogramm" / desktop_gemeinsam.ABSTURZPROTOKOLL_DATEINAME
    protokoll.parent.mkdir(parents=True)
    protokoll.write_text(
        "alte Zeile\n" * 100
        + f'File "{heim}\\x.py", line 1\n'
        + f"FileNotFoundError: {str(heim / 'x.db')!r}\n"
        + f"{str(heim).lower()}\\klein.txt und {heim.as_posix()}/vor.txt\n"
        + "RuntimeError: zuletzt (Benutzer maxmuster)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(desktop_gemeinsam, "_absturzprotokoll_pfad", protokoll)

    text = desktop_gemeinsam.diagnose_text("9.9.9", fehler="Traceback: aktueller Fehler")
    assert "Version: 9.9.9" in text
    assert "Aktueller Fehler:\nTraceback: aktueller Fehler" in text
    assert "RuntimeError: zuletzt (Benutzer <Benutzer>)" in text
    assert text.count("alte Zeile") < 100
    assert "maxmuster" not in text.lower()
    # repr() verdoppelt unter Windows die Backslashes ('C:\\Users\\…'), unter Linux/macOS
    # bleibt es bei "/" - erwartet wird jeweils "~" an Stelle des Heimordners.
    repr_erwartet = repr(str(heim / "x.db"))[1:-1].replace(repr(str(heim))[1:-1], "~")
    assert repr_erwartet.startswith("~") and repr_erwartet in text
    assert "~\\klein.txt" in text and "~/vor.txt" in text

    monkeypatch.setattr(desktop_gemeinsam, "_absturzprotokoll_pfad", tmp_path / "fehlt.txt")
    assert "(nicht lesbar)" in desktop_gemeinsam.diagnose_text("9.9.9")


def test_kurzer_benutzername_nur_in_pfaden_ersetzt(tmp_path, monkeypatch):
    """OFFEN.md B1 (19.10.2026): Ein kurzer Name wie "max" wird nur als Ordnername ersetzt,
    nicht in gleichlautendem Text ("max(", "Maxwert"); ab 6 Zeichen auch im Freitext."""
    from pathlib import Path

    import desktop_gemeinsam

    heim = tmp_path / "Users" / "max"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: heim))
    monkeypatch.setenv("USERNAME", "max")
    monkeypatch.setenv("USER", "max")
    monkeypatch.setattr(desktop_gemeinsam, "_kurzpfad", lambda pfad: None)
    text = desktop_gemeinsam._ohne_benutzerpfad(
        f"{heim}\\x.py\nwert = max(a, b) bei Max\nD:\\Daten\\max\\y.db und /home/MAX\nmax\n"
        f"Kein Zugriff auf {heim}.\n{chr(92).join(['D:', 'max', 'y.db'])!r} /home/max.bak")
    zeilen = text.split("\n")
    assert zeilen[0] == "~\\x.py"
    assert zeilen[1] == "wert = max(a, b) bei Max"
    assert zeilen[2] == "D:\\Daten\\<Benutzer>\\y.db und /home/<Benutzer>"
    assert zeilen[3] == "max"
    # Pfad am Satzende (Verifikation 19.10.2026): der Name darf nicht stehen bleiben
    assert "max" not in zeilen[4].lower() and zeilen[4].endswith("<Benutzer>.")
    # repr()-Form mit verdoppelten Backslashes und Ordner mit Endung
    assert "max" not in zeilen[5].lower() and zeilen[5].count("<Benutzer>") == 2

    monkeypatch.setenv("USERNAME", "muster")
    monkeypatch.setenv("USER", "muster")
    assert desktop_gemeinsam._ohne_benutzerpfad("von muster gemeldet") == "von <Benutzer> gemeldet"


def test_diagnose_text_fuehrt_fehler_aus_dem_protokoll_nicht_doppelt_auf(tmp_path, monkeypatch):
    import desktop_gemeinsam

    fehler = "Traceback (most recent call last):\nRuntimeError: steht schon im Protokoll\n"
    protokoll = tmp_path / desktop_gemeinsam.ABSTURZPROTOKOLL_DATEINAME
    protokoll.write_text("--- Start ---\nUnbehandelter Fehler:\n" + fehler, encoding="utf-8")
    monkeypatch.setattr(desktop_gemeinsam, "_absturzprotokoll_pfad", protokoll)

    text = desktop_gemeinsam.diagnose_text("9.9.9", fehler=fehler)
    assert "Aktueller Fehler:" not in text
    assert text.count("RuntimeError: steht schon im Protokoll") == 1

    monkeypatch.setattr(desktop_gemeinsam, "_absturzprotokoll_pfad", None)
    assert "Aktueller Fehler:" in desktop_gemeinsam.diagnose_text("9.9.9", fehler=fehler)


def test_fehlerfenster_bei_unbehandeltem_fehler_nur_einmal_gleichzeitig(fehlerfenster_hook, monkeypatch):
    """Rückmeldung 13.10.2026: unbehandelte Fehler erscheinen zusätzlich als Fenster; der
    bisherige Hook (Absturzprotokoll) läuft weiter zuerst, und ein Fehler während das
    Fenster offen ist, öffnet kein zweites."""
    import desktop_gemeinsam

    protokolliert, fenster = fehlerfenster_hook
    innen = []

    def zeigen(version, fehler, parent=None):
        fenster.append(fehler)
        _fehler_melden(ValueError("zweiter Fehler"))
        innen.append(desktop_gemeinsam._fehlerfenster_offen)

    monkeypatch.setattr(desktop_gemeinsam, "fehlerfenster_zeigen", zeigen)
    _fehler_melden(RuntimeError("erster Fehler"))

    assert protokolliert == ["erster Fehler", "zweiter Fehler"]
    assert len(fenster) == 1 and "RuntimeError: erster Fehler" in fenster[0]
    assert innen == [True]
    assert desktop_gemeinsam._fehlerfenster_offen is False


def test_fehlerfenster_wiederkehrender_fehler_nur_einmal_je_sitzung(fehlerfenster_hook):
    """Verifikation 13.10.2026: ein ständig wiederkehrender Fehler (z. B. im Timer) darf
    nicht nach jedem OK das nächste Fenster öffnen; ein anderes Fehlerbild schon."""
    protokolliert, fenster = fehlerfenster_hook
    for _ in range(3):
        _fehler_melden(RuntimeError("immer wieder"))
    _fehler_melden(RuntimeError("andere Stelle"), zeile=1)
    _fehler_melden(KeyError("anderer Typ"))

    assert len(protokolliert) == 5
    assert len(fenster) == 3


def test_fehlerfenster_je_aufrufweg_ein_fenster(fehlerfenster_hook):
    """OFFEN.md B2 (19.10.2026): Das Fehlerbild ist Typ plus ganzer Aufrufweg. Derselbe Fehler
    in einer Hilfsfunktion, erreicht über zwei Wege, zeigt zwei Fenster; die Wiederholung über
    denselben Weg (z. B. ein Timer) bleibt bei einem."""
    protokolliert, fenster = fehlerfenster_hook
    for _ in range(3):
        _ueber_weg_melden(_weg_a)
    _ueber_weg_melden(_weg_b)
    _ueber_weg_melden(_weg_b)

    assert len(protokolliert) == 5
    assert len(fenster) == 2


def test_fehlerfenster_nicht_bei_abbruch_ohne_app_oder_im_nebenthread(fehlerfenster_hook, monkeypatch):
    import threading

    import desktop_gemeinsam

    protokolliert, fenster = fehlerfenster_hook
    _fehler_melden(KeyboardInterrupt())

    nebenthread = threading.Thread(target=_fehler_melden, args=(RuntimeError("im Thread"),))
    nebenthread.start()
    nebenthread.join()

    monkeypatch.setattr(QApplication, "instance", staticmethod(lambda: None))
    assert desktop_gemeinsam._fehlerfenster_offen is False
    _fehler_melden(RuntimeError("ohne App"))

    assert len(protokolliert) == 3
    assert fenster == []


def test_fehlerfenster_fehler_beim_anzeigen_und_im_bisherigen_hook_werden_geschluckt(qtbot, monkeypatch):
    import desktop_gemeinsam

    def kaputter_hook(*_a):
        raise OSError("keine Konsole")

    def kaputtes_fenster(*_a, **_k):
        raise RuntimeError("Fenster kaputt")

    monkeypatch.setattr(sys, "excepthook", kaputter_hook)
    monkeypatch.setattr(desktop_gemeinsam, "_gezeigte_fehler", set())
    monkeypatch.setattr(desktop_gemeinsam, "fehlerfenster_zeigen", kaputtes_fenster)
    desktop_gemeinsam.fehlerfenster_einrichten("9.9.9")

    _fehler_melden(ValueError("Original"))  # darf selbst nichts auslösen
    assert desktop_gemeinsam._fehlerfenster_offen is False
    assert len(desktop_gemeinsam._gezeigte_fehler) == 1


def test_fehlerfenster_kopieren_schliesst_nicht_und_fuellt_zwischenablage(qtbot, monkeypatch):
    import desktop_gemeinsam

    monkeypatch.setattr(desktop_gemeinsam, "_absturzprotokoll_pfad", None)
    beobachtet = {}

    def exec_(box):
        box.show()
        knopf = next(b for b in box.buttons() if b.text() == "Fehlerbericht kopieren")
        knopf.click()
        beobachtet["sichtbar_nach_klick"] = box.isVisible()
        beobachtet["knoepfe"] = [b.text() for b in box.buttons()]
        beobachtet["format"] = box.textFormat()
        box.close()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", exec_)
    desktop_gemeinsam.fehlerfenster_zeigen("9.9.9", "RuntimeError: <b>Name</b>")

    assert beobachtet["sichtbar_nach_klick"]
    assert "Protokoll-Ordner öffnen" not in beobachtet["knoepfe"]
    assert beobachtet["format"] == Qt.PlainText
    zwischenablage = QApplication.clipboard().text()
    assert "Version: 9.9.9" in zwischenablage and "RuntimeError: <b>Name</b>" in zwischenablage


def test_fehlerfenster_protokoll_ordner_oeffnen(qtbot, tmp_path, monkeypatch):
    import desktop_gemeinsam

    protokoll = tmp_path / desktop_gemeinsam.ABSTURZPROTOKOLL_DATEINAME
    protokoll.write_text("", encoding="utf-8")
    monkeypatch.setattr(desktop_gemeinsam, "_absturzprotokoll_pfad", protokoll)
    gezeigt = []
    monkeypatch.setattr(desktop_gemeinsam, "_ordner_zeigen", lambda pfad, parent=None: gezeigt.append(pfad))

    def exec_(box):
        next(b for b in box.buttons() if b.text() == "Protokoll-Ordner öffnen").click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", exec_)
    desktop_gemeinsam.fehlerfenster_zeigen("9.9.9", "RuntimeError: x")
    assert gezeigt == [str(protokoll)]


def test_version_dialog_diagnose_kopieren_und_protokoll_ordner(qtbot, tmp_path, monkeypatch):
    import desktop_gemeinsam

    monkeypatch.setattr(desktop_gemeinsam, "_absturzprotokoll_pfad", None)
    dialog = VersionDialog()
    qtbot.addWidget(dialog)
    knoepfe = {b.text(): b for b in dialog.findChildren(QPushButton)}
    assert not knoepfe["Protokoll-Ordner öffnen"].isEnabled()
    knoepfe["Diagnose kopieren"].click()
    assert QApplication.clipboard().text().startswith("SHS-Prüfungsprogramm – Diagnose")
    assert dialog._diagnose_status.text() == "Diagnose kopiert."

    protokoll = tmp_path / desktop_gemeinsam.ABSTURZPROTOKOLL_DATEINAME
    protokoll.write_text("", encoding="utf-8")
    monkeypatch.setattr(desktop_gemeinsam, "_absturzprotokoll_pfad", protokoll)
    gezeigt = []
    monkeypatch.setattr(desktop_programm, "_ordner_zeigen", lambda pfad, parent=None: gezeigt.append(pfad))
    dialog = VersionDialog()
    qtbot.addWidget(dialog)
    ordner_btn = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Protokoll-Ordner öffnen")
    assert ordner_btn.isEnabled()
    ordner_btn.click()
    assert gezeigt == [str(protokoll)]


def test_schriftwechsel_rechnet_alle_ergebnistabellen_neu(qtbot, termin, monkeypatch):
    """UX-Test 2026-11, T14 (Abschluss-QS A11): Der Schriftwechsel rechnet auch die
    Ergebnistabelle eines zweiten Hauptfensters (Demo) neu."""
    conn, pfad = termin
    erstes = HauptFenster(conn, pfad)
    zweites = HauptFenster(conn, pfad)
    for fenster in (erstes, zweites):
        qtbot.addWidget(fenster)
        fenster.show()
    aufrufe = []
    for fenster in (erstes, zweites):
        monkeypatch.setattr(fenster.ergebnis_tab, "_spaltenbreiten_anpassen",
                            lambda f=fenster: aufrufe.append(f))
    monkeypatch.setattr("app._schriftstufe_speichern", lambda stufe: None)
    monkeypatch.setattr("app.HauptFenster._darstellung_neu_anwenden", lambda self: None)
    erstes._schrift_wechseln("normal")
    assert erstes in aufrufe and zweites in aufrufe


def test_dialoggroesse_richtet_sich_nach_dem_inhalt(qtbot, monkeypatch):
    """Nachtest 2, N2: Bei Schrift „Groß“ war das Formular breiter als die feste Startgröße
    des Teilnehmer-Dialogs - die Breite richtet sich jetzt nach dem Inhalt (höchstens 95 %
    des Bildschirms)."""
    from PySide6.QtCore import QSize
    from desktop_dialoge import _groesse_auf_bildschirm_begrenzen

    class _Inhalt:
        def ensurePolished(self):
            pass

        def sizeHint(self):
            return QSize(500, 100)

    dialog = QDialog()
    qtbot.addWidget(dialog)
    _groesse_auf_bildschirm_begrenzen(dialog, 300, 200, inhalt=_Inhalt())
    frei = dialog.screen().availableGeometry().width()
    assert dialog.width() == min(600, int(frei * DIALOG_MAX_BREITE_ANTEIL))
    _groesse_auf_bildschirm_begrenzen(dialog, 300, 200)
    assert dialog.width() == min(300, int(frei * DIALOG_MAX_BREITE_ANTEIL))

    # Der Teilnehmer-Dialog misst sein Formular (Verdrahtung).
    from PySide6.QtWidgets import QScrollArea
    import desktop_dialoge_teilnehmer

    gemessen = []
    echt = desktop_dialoge_teilnehmer._groesse_auf_bildschirm_begrenzen
    monkeypatch.setattr(desktop_dialoge_teilnehmer, "_groesse_auf_bildschirm_begrenzen",
                        lambda d, b, h, inhalt=None, **k: gemessen.append(inhalt) or echt(d, b, h, inhalt=inhalt, **k))
    teilnehmer_dialog = desktop_dialoge_teilnehmer.TeilnehmerDialog(None)
    qtbot.addWidget(teilnehmer_dialog)
    assert gemessen == [teilnehmer_dialog.findChild(QScrollArea).widget()]


def test_fenster_passt_sich_nach_schriftwechsel_dem_bildschirm_an(qtbot, termin, monkeypatch):
    """Marco 05.11.2026 (nach 1.0.56): War das Fenster breiter als der Bildschirm, blieb es das
    nach dem Wechsel zurück auf „Normal“ - erst Minimieren/Maximieren half. Jetzt passt es sich
    an: maximiert über erneutes Maximieren, sonst durch Verkleinern und Verschieben; passt die
    Mindestgröße gar nicht, geschieht nichts."""
    from PySide6.QtCore import QRect, QSize

    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    frei = fenster.screen().availableGeometry()
    monkeypatch.setattr(fenster, "minimumSizeHint", lambda: QSize(100, 100))
    zu_gross = QRect(frei.x(), frei.y(), frei.width() + 200, frei.height())
    monkeypatch.setattr(fenster, "frameGeometry", lambda: zu_gross)
    aufrufe = []
    monkeypatch.setattr(fenster, "isMaximized", lambda: True)
    monkeypatch.setattr(fenster, "showNormal", lambda: aufrufe.append("normal"))
    monkeypatch.setattr(fenster, "showMaximized", lambda: aufrufe.append("maximiert"))
    fenster._an_bildschirm_anpassen()
    assert aufrufe == ["normal", "maximiert"]

    # Mindestgröße passt nicht in den Bildschirm: kein Sprung ohne Wirkung.
    aufrufe.clear()
    monkeypatch.setattr(fenster, "minimumSizeHint", lambda: QSize(frei.width() + 50, 100))
    fenster._an_bildschirm_anpassen()
    assert aufrufe == []

    # Nicht maximiert: verkleinern und in den freien Bereich schieben.
    monkeypatch.setattr(fenster, "minimumSizeHint", lambda: QSize(100, 100))
    monkeypatch.setattr(fenster, "isMaximized", lambda: False)
    gesetzt = {}
    monkeypatch.setattr(fenster, "resize", lambda b, h: gesetzt.update(groesse=(b, h)))
    monkeypatch.setattr(fenster, "move", lambda x, y: gesetzt.update(ort=(x, y)))
    # Der Rahmen folgt dem Verkleinern (wie beim echten Fenster); Rand wie gemessen.
    rand = (zu_gross.width() - fenster.width(), zu_gross.height() - fenster.height())
    monkeypatch.setattr(fenster, "frameGeometry", lambda: QRect(
        frei.x() + 300, frei.y(),
        gesetzt["groesse"][0] + rand[0] if "groesse" in gesetzt else zu_gross.width(),
        gesetzt["groesse"][1] + rand[1] if "groesse" in gesetzt else zu_gross.height()))
    fenster._an_bildschirm_anpassen()
    assert gesetzt["groesse"][0] <= frei.width()
    assert gesetzt["ort"][0] >= frei.x()

    # Passt schon: nichts tun.
    gesetzt.clear()
    monkeypatch.setattr(fenster, "frameGeometry", lambda: QRect(frei.x(), frei.y(), 200, 200))
    fenster._an_bildschirm_anpassen()
    assert gesetzt == {} and aufrufe == []

    # Jeder Darstellungswechsel stößt die Anpassung an.
    angestossen = []
    monkeypatch.setattr(fenster, "_an_bildschirm_anpassen", lambda: angestossen.append(True))
    monkeypatch.setattr("app._schriftstufe_speichern", lambda stufe: None)
    fenster._schrift_wechseln("normal")
    qtbot.waitUntil(lambda: bool(angestossen), timeout=2000)


def test_seitenleiste_maskiert_namen(qtbot, termin):
    """Sicherheitsprüfung 03.10.2026, S-1: Namen aus Importen/fremden Dateien landen im
    Rich Text der Seitenleiste nur maskiert - kein eingeschleustes Markup (z. B. <img>)."""
    conn, pfad = termin
    _dk_parallel_termin(conn)
    otto = next(t for t in list_teilnehmer(conn) if t["nachname"] == "Otto")
    update_teilnehmer(conn, otto["id"], NeuerTeilnehmer(
        nachname='<img src="x.png">Otto', vorname="Max", rufname_hund="Bello", art="DK", stufe=1,
        startnummer=2))
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    tab = fenster.zeitplan_tab
    tab.aktualisieren()
    text = tab._offene_starts_label.text()
    assert "&lt;img" in text
    # Einzige echte Bilder: die eigenen Symbole (symbol_png, Marco 01.11.2026).
    import re
    bilder = re.findall(r'<img src="([^"]*)"', text)
    assert bilder and all("/symbole/" in quelle and quelle.endswith(".png") for quelle in bilder)
    assert '<img src="x.png"' not in text


def test_meldungsfenster_zeigen_reinen_text(monkeypatch):
    """S-1: Standard-Meldungsfenster deuten Texte (mit Namen) nie als HTML."""
    from desktop_gemeinsam import meldungsfenster_als_klartext

    for name in ("question", "information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, name, getattr(QMessageBox, name))
    monkeypatch.setattr(QMessageBox, "_shs_klartext", False, raising=False)
    meldungsfenster_als_klartext()
    gesehen = []

    def ausfuehren(box):
        gesehen.append((box.textFormat(), box.text()))
        return int(QMessageBox.StandardButton.Yes)

    monkeypatch.setattr(QMessageBox, "exec", ausfuehren)
    antwort = QMessageBox.question(None, "Löschen", 'Teilnehmer „<img src="x">“ löschen?')
    assert antwort == QMessageBox.Yes
    QMessageBox.warning(None, "Hinweis", "<b>fett</b>")
    assert [f for f, _t in gesehen] == [Qt.PlainText, Qt.PlainText]


def test_klartext_tooltip_maskiert_namen():
    """S-1: Tooltips mit Richternamen zeigen Markup wörtlich statt es auszuführen."""
    from desktop_zeitplan import _klartext_tooltip

    tooltip = _klartext_tooltip('Gleichzeitig bei <img src="//server/x.png">\nzweite Zeile')
    assert "<img" not in tooltip
    assert "&lt;img" in tooltip
    assert tooltip.startswith("<qt>") and "<br>" in tooltip


@pytest.mark.langsam
def test_screenshot_skript_erzeugt_alle_bilder(tmp_path, monkeypatch):
    """Marco 09.10.2026: tools/screenshots.py erzeugt alle Desktop-Bilder fürs Handbuch.
    Läuft in einem eigenen Prozess, weil das Skript Qt global einrichtet (Schrift,
    Übersetzer, Design) - das darf die übrigen GUI-Tests nicht beeinflussen."""
    import subprocess
    from pathlib import Path

    from PySide6.QtGui import QImage

    repo = Path(__file__).resolve().parent
    # Der Import setzt QT_QPA_FONTDIR. Erst setzen, dann löschen: so merkt sich monkeypatch
    # auch "war vorher nicht da" und stellt Umgebung und sys.modules nach dem Test wieder
    # her (delenv/delitem allein merken sich einen fehlenden Eintrag nicht).
    monkeypatch.setenv("QT_QPA_FONTDIR", "")
    monkeypatch.delenv("QT_QPA_FONTDIR")
    monkeypatch.setitem(sys.modules, "screenshots", None)
    monkeypatch.delitem(sys.modules, "screenshots")
    monkeypatch.syspath_prepend(str(repo / "tools"))
    import screenshots

    umgebung = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    lauf = subprocess.run(
        [sys.executable, str(repo / "tools" / "screenshots.py"), "--ziel", str(tmp_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=umgebung, timeout=300,
    )
    assert lauf.returncode == 0, lauf.stderr[-3000:]
    for name, (breite, hoehe) in screenshots.BILD_DATEIEN.items():
        bild = QImage(str(tmp_path / f"{name}.png"))
        assert not bild.isNull(), f"{name}.png fehlt"
        assert (bild.width(), bild.height()) == (breite, hoehe), name


# --- Erscheinungsbild „Beagle“: Kopfbalken, Symbole, kurze Hinweise (Marco 01.11.2026) ------


def test_kopfbalken_zeigt_termin_und_aktualisiert_teilnehmerzahl(qtbot, termin, monkeypatch):
    conn, pfad = termin
    set_veranstaltung(conn, "Musterverein", "2026-11-14", ort="Musterstadt")
    _teilnehmer_anlegen(conn, nachname="Eins", startnummer=1)
    nicht_da = _teilnehmer_anlegen(conn, nachname="Zwei", startnummer=2)
    setze_keine_teilnahme(conn, nicht_da, True)
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)

    kopf = fenster.kopf
    assert kopf.objectName() == "kopfBalken"
    assert kopf.titel_label.text() == "Musterverein"
    # Nur Teilnehmende zählen („keine Teilnahme“ nicht).
    assert kopf.unterzeile_label.text() == "Sa 14.11.2026  ·  Musterstadt  ·  1 Teilnehmer"
    assert not kopf.bild_label.pixmap().isNull()

    # Anlegen über den Reiter „Teilnehmer“ - der Kopf zählt sofort mit.
    def _anlegen(_dialog):
        _teilnehmer_anlegen(conn, nachname="Drei", startnummer=3)
        return QDialog.Accepted

    ueberall_ersetzen(monkeypatch, "_ausfuehren", _anlegen)
    fenster.teilnehmer_tab._teilnehmer_hinzufuegen()
    assert kopf.unterzeile_label.text().endswith("2 Teilnehmer")

    # Geänderte Veranstaltungsdaten (Reiter „Verwaltung“) landen ebenfalls im Kopf.
    set_veranstaltung(conn, "Anderer Verein", "2026-11-15", ort="Neustadt")
    fenster.verwaltung_tab.veranstaltung_geaendert.emit()
    assert kopf.titel_label.text() == "Anderer Verein"
    assert kopf.unterzeile_label.text().startswith("So 15.11.2026  ·  Neustadt")


def test_kopfbalken_aktualisiert_beim_reiterwechsel(qtbot, termin):
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    assert fenster.kopf.unterzeile_label.text().endswith("0 Teilnehmer")
    _teilnehmer_anlegen(conn, nachname="Still", startnummer=1)  # z. B. aus dem Formular-Import
    fenster._tabs.setCurrentWidget(fenster.zeitplan_tab)
    assert fenster.kopf.unterzeile_label.text().endswith("1 Teilnehmer")


def test_kopfbalken_knoepfe_mit_symbolen_und_demo_kennzeichnung(qtbot, termin):
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad, demo=True)
    qtbot.addWidget(fenster)
    texte = {b.text(): b for b in fenster.kopf.findChildren(QPushButton)}
    assert set(texte) == {"Anderen Termin öffnen…", "Checkliste", f"Version {VERSION}", "Demoprüfung", "Hilfe"}
    assert all(not knopf.icon().isNull() for knopf in texte.values())
    assert fenster.kopf.unterzeile_label.text().startswith("DEMO")


def test_kopf_unterzeile_fehlende_und_unlesbare_angaben():
    from desktop_gemeinsam import kopf_unterzeile

    assert kopf_unterzeile("2026-11-14", "Ort", 8) == "Sa 14.11.2026  ·  Ort  ·  8 Teilnehmer"
    assert kopf_unterzeile("2026-11-14", "Ort", 8, demo=True).startswith("DEMO  ·  Sa 14.11.2026")
    assert kopf_unterzeile(None, None, 0) == "0 Teilnehmer"
    assert kopf_unterzeile("31.02.2026", "", 1) == "31.02.2026  ·  1 Teilnehmer"


def test_kopfbalken_titel_reiner_text(qtbot):
    """S-1: Vereinsname aus der Termin-Datei nie als HTML deuten."""
    from desktop_gemeinsam import KopfBalken

    kopf = KopfBalken()
    qtbot.addWidget(kopf)
    kopf.termin_setzen('<img src="x.png">Verein', "2026-11-14", "<b>Ort</b>", 1)
    assert kopf.titel_label.textFormat() == Qt.PlainText
    assert kopf.unterzeile_label.textFormat() == Qt.PlainText


def test_jedes_verwendete_symbol_ist_aufgefuehrt():
    """Jeder Name, den der Code an symbol()/symbol_setzen()/symbol_html()/knopf_hinzufuegen()
    übergibt, steht in SYMBOL_NAMEN - die prüft der Selbsttest der gebauten Fassung - und
    liegt in symbole/."""
    import re
    from pathlib import Path

    import desktop_gemeinsam as gemeinsam

    ordner = Path(__file__).resolve().parent
    muster = re.compile(
        r'(?:symbol|symbol_html|symbol_png)\(\s*"([a-z-]+)"'
        r'|(?:symbol_setzen|knopf_hinzufuegen)\([^,()]+,\s*"([a-z-]+)"'
    )
    namen = set()
    for datei in [ordner / "app.py", *ordner.glob("desktop_*.py")]:
        for treffer in muster.findall(datei.read_text(encoding="utf-8")):
            namen.update(n for n in treffer if n)
    # Dazu die Namen, die erst zur Laufzeit gewählt werden ("a" if … else "b").
    assert {"chevron-down", "chevron-right", "check", "school"} <= namen
    assert namen <= set(gemeinsam.SYMBOL_NAMEN), namen - set(gemeinsam.SYMBOL_NAMEN)
    for name in gemeinsam.SYMBOL_NAMEN:
        assert (ordner / "symbole" / f"{name}.svg").is_file(), name


def test_symbol_png_schreibt_bild_im_programmordner():
    from pathlib import Path

    import desktop_darstellung as darstellung
    import desktop_gemeinsam as gemeinsam
    from PySide6.QtGui import QImage

    pfad = gemeinsam.symbol_png("check", "#2E7D32", 14)
    assert pfad is not None
    assert Path(pfad).parent.parent == Path(darstellung._haken_pfad()).parent
    bild = QImage(pfad)
    assert not bild.isNull() and bild.width() == 28
    assert 'width="14"' in gemeinsam.symbol_html("check", "#2E7D32", 14)


def test_kleinigkeiten_vor_dem_build_1_0_53(qtbot, conn, monkeypatch, tmp_path):
    """Marco 01.11.2026 (Build-Vorbereitung): Startfenster ohne Zeilennummern, Zeitplan-
    Listen brechen lange Blockköpfe um, der KI-Umschalter ist flach, ein langer Pfad im
    Demo-Erklärfenster bekommt Umbruchstellen."""
    import desktop_demo
    from PySide6.QtWidgets import QListWidget, QWidget

    monkeypatch.setattr("app.liste_termine", lambda: [])
    start = StartDialog()
    qtbot.addWidget(start)
    assert not start.tabelle.verticalHeader().isVisible() and start.tabelle.verticalHeader().isHidden()

    add_zeitplan_richter(conn, "R1")
    tab = _zeitplan_tab(qtbot, conn)
    listen = tab.findChildren(QListWidget)
    assert listen and all(l.wordWrap() and l.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff for l in listen)

    fenster = HauptFenster(conn, str(tmp_path / "x.sqlite"))
    qtbot.addWidget(fenster)
    stil = fenster.formular_import_tab._ki_umschalter.styleSheet()
    assert "background: transparent" in stil and "border: none" in stil

    eltern = QWidget()
    qtbot.addWidget(eltern)
    panel = desktop_demo.DemoPanel(eltern)
    panel.hinweis("Gespeichert unter: C:\\Users\\Name\\Ergebnisliste.pdf")
    assert panel.hinweis_label.text() == "Gespeichert unter: C:\\\u200bUsers\\\u200bName\\\u200bErgebnisliste.pdf"
    panel.schliessen()


def test_symbol_png_ohne_schreibrecht_faellt_auf_text_zurueck(qtbot, conn, monkeypatch):
    """Verifikation 01.11.2026: Lässt sich das Symbol-Bild nicht schreiben (z. B. Ordner
    schreibgeschützt), liefert symbol_png None, symbol_html "" - und die Seitenleiste des
    Zeitplans zeigt wieder die Textzeichen statt eines kaputten Bildes."""
    import desktop_darstellung as darstellung
    import desktop_gemeinsam as gemeinsam

    monkeypatch.setattr(darstellung, "_bild_speichern", lambda *_a, **_k: False)
    monkeypatch.setattr(gemeinsam, "_symbol_png_geschrieben", set())
    assert gemeinsam.symbol_png("check", "#123456", 14) is None
    assert gemeinsam.symbol_html("check", "#123456", 14) == ""
    _teilnehmer_anlegen(conn)
    tab = _zeitplan_tab(qtbot, conn)
    text = tab._offene_starts_label.text()
    assert "✗ " in text and "<img" not in text


def test_kurze_hinweise_mit_vollem_tooltip(qtbot, termin):
    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    erwartet = {
        fenster.zeitplan_tab: "Je Richter eine eigene Spalte mit frei sortierbarer Abfolge",
        fenster.verwaltung_tab: "Über „Veranstaltungsdaten bearbeiten…“ lassen sich Verein",
        fenster.datensicherung_tab: "Sichert bzw. liest ALLE Termine aus dem gemeinsamen Termine-Ordner",
    }
    for tab, anfang in erwartet.items():
        hinweise = tab.findChildren(QLabel, "kurzHinweis")
        assert len(hinweise) == 1, tab
        hinweis = hinweise[0]
        assert len(hinweis.text()) < 140 and len(hinweis.text()) * 2 < len(hinweis.toolTip())
        assert anfang in hinweis.toolTip()
        symbol_label = hinweis.parent().findChild(QLabel, "kurzHinweisSymbol")
        assert symbol_label.toolTip() == hinweis.toolTip()
        assert not symbol_label.pixmap().isNull()
    # Der volle Text ist maskiert, damit Qt ihn als umbrechenden Rich Text zeigt.
    from desktop_gemeinsam import kurzer_hinweis
    huelle = kurzer_hinweis("kurz", "a <b> & c")
    qtbot.addWidget(huelle)
    assert huelle.findChild(QLabel, "kurzHinweis").toolTip() == "<p>a &lt;b&gt; &amp; c</p>"


def test_designwechsel_faerbt_kopf_und_knopfsymbole_um(qtbot, termin, darstellung_speicher):
    import desktop_darstellung as darstellung

    conn, pfad = termin
    darstellung._darstellung_anwenden(QApplication.instance())  # gespeichert: "hell"
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    wechseln = fenster.wechseln_btn
    hell_kopf = darstellung._DESIGNS["hell"]["KOPF_TEXT"]
    assert wechseln.icon().cacheKey() == symbol("folder-open", hell_kopf).cacheKey()

    fenster._design_actions["kontrast"].trigger()
    assert wechseln.icon().cacheKey() == symbol("folder-open", "#FFFFFF").cacheKey()
    ki = fenster.formular_import_tab._ki_umschalter
    kontrast_knopf = darstellung._DESIGNS["kontrast"]["TEXT_BUTTON"]
    assert ki.icon().cacheKey() == symbol("chevron-right", kontrast_knopf).cacheKey()
    hilfe = fenster.zeitplan_tab.findChild(QLabel, "kurzHinweisSymbol")
    assert hilfe.property("shsSymbolFarbe") == "TEXT_GEDAEMPFT"


def test_zahlenfeld_pfeile_werden_geschrieben(darstellung_speicher):
    import desktop_darstellung as darstellung
    from PySide6.QtGui import QImage

    darstellung_speicher["design"] = "dunkel"
    darstellung._darstellung_anwenden(QApplication.instance())
    farbe = darstellung._DESIGNS["dunkel"]["TEXT_BUTTON"]
    for richtung in ("hoch", "runter"):
        bild = QImage(darstellung._pfeil_pfad(richtung, farbe))
        assert not bild.isNull() and bild.width() == 20
    assert darstellung._pfeil_pfad("hoch", farbe) in QApplication.instance().styleSheet()


def test_beagle_zehn_schnelle_klicks_starten_die_ueberraschung(qtbot, termin, monkeypatch):
    import desktop_beagle

    fenster, zaehler, jetzt = _beagle_fenster(qtbot, termin, monkeypatch)
    _beagle_klicks(qtbot, fenster, jetzt, 9)
    assert zaehler.explosion is None
    _beagle_klicks(qtbot, fenster, jetzt, 1)
    explosion = zaehler.explosion
    assert isinstance(explosion, desktop_beagle.BeagleExplosion) and explosion.isVisible()
    assert explosion.testAttribute(Qt.WA_TransparentForMouseEvents)  # Programm bleibt bedienbar
    assert explosion.geometry() == fenster.rect()
    # Während sie läuft, startet keine zweite.
    _beagle_klicks(qtbot, fenster, jetzt, 10)
    assert zaehler.explosion is explosion
    explosion._takt.stop()


def test_beagle_zoegern_setzt_die_zaehlung_zurueck(qtbot, termin, monkeypatch):
    fenster, zaehler, jetzt = _beagle_fenster(qtbot, termin, monkeypatch)
    _beagle_klicks(qtbot, fenster, jetzt, 9)
    _beagle_klicks(qtbot, fenster, jetzt, 1, pause=2.0)  # zu lange gewartet: zählt als erster
    assert zaehler.explosion is None
    _beagle_klicks(qtbot, fenster, jetzt, 9)
    assert zaehler.explosion is not None
    zaehler.explosion._takt.stop()


def test_beagle_teilchen_bleiben_im_fenster_und_alles_verschwindet_nach_20_s(qtbot, termin):
    """Boden, Wände und (Marco 01.11.2026) Decke halten die Teilchen im Fenster."""
    import desktop_beagle

    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.resize(900, 600)
    fenster.show()
    explosion = desktop_beagle.BeagleExplosion(fenster, QPointF(30, 30), seed=7)
    explosion._takt.stop()  # Zeit von Hand vorgeben
    explosion._schritt(0.4)
    assert explosion._teilchen == [] and explosion.deckkraft() == 1.0
    explosion._schritt(0.5)  # über 0,8 s: zersprungen
    assert len(explosion._teilchen) == desktop_beagle.TEILCHEN
    for _ in range(int(16 / 0.02)):
        explosion._schritt(0.02)
    for t in explosion._teilchen:
        r = t.groesse / 2
        assert r - 0.01 <= t.x <= explosion.width() - r + 0.01
        assert r - 0.01 <= t.y <= explosion.height() - r + 0.01
    assert explosion.deckkraft() == 1.0
    explosion._schritt(2.0)  # 18,9 s: blendet aus
    assert 0.0 < explosion.deckkraft() < 1.0
    explosion._schritt(1.5)
    assert explosion.beendet and not explosion.isVisible()


def test_beagle_zaehler_haengt_am_kopfbild_des_hauptfensters(qtbot, termin):
    import desktop_beagle

    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    zaehler = fenster._beagle_zaehler
    assert isinstance(zaehler, desktop_beagle.BeagleKlickZaehler)
    assert zaehler._bild is fenster.kopf.bild_label and zaehler.parent() is fenster
    for _ in range(desktop_beagle.KLICKS):
        zaehler.klick()
    assert zaehler.explosion is not None
    zaehler.explosion._takt.stop()


def test_beagle_zaehler_haelt_das_hauptfenster_nicht_am_leben(qtbot, termin):
    """Fenster -> Zähler -> Fenster als Python-Referenz hielt geschlossene Hauptfenster bis zur
    nächsten Speicherbereinigung am Leben (fiel in anderen Tests auf)."""
    import gc
    import weakref

    import desktop_beagle

    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    zaehler = fenster._beagle_zaehler
    for _ in range(desktop_beagle.KLICKS):
        zaehler.klick()
    zaehler.explosion._takt.stop()
    ref = weakref.ref(fenster)
    gc.disable()
    try:
        del fenster, zaehler
        assert ref() is None
    finally:
        gc.enable()


def test_beagle_langer_takt_groessenaenderung_neustart_und_ohne_bild(qtbot, termin, monkeypatch):
    """Verifikation 01.11.2026: Ein einziger langer Takt (z. B. hängendes System) beendet
    die Explosion trotzdem nach 20 s; eine Größenänderung des Fensters nimmt sie mit; nach
    dem Ende lässt sie sich neu starten; ohne Programmsymbol startet sie gar nicht."""
    import desktop_beagle
    from PySide6.QtGui import QPixmap

    conn, pfad = termin
    fenster = HauptFenster(conn, pfad)
    qtbot.addWidget(fenster)
    fenster.resize(900, 600)
    fenster.show()
    zaehler = fenster._beagle_zaehler
    for _ in range(desktop_beagle.KLICKS):
        zaehler.klick()
    explosion = zaehler.explosion
    explosion._takt.stop()
    explosion._schritt(1.0)
    fenster.resize(700, 500)
    assert explosion.geometry() == fenster.rect()
    explosion._schritt(0.02)
    assert all(t.x <= explosion.width() - t.groesse / 2 + 0.01 for t in explosion._teilchen)

    class _LangeUhr:
        def restart(self):
            return 25_000  # Millisekunden in einem einzigen Takt

    explosion._uhr = _LangeUhr()
    explosion._ticken()
    assert explosion.beendet and not explosion.isVisible()

    for _ in range(desktop_beagle.KLICKS):
        zaehler.klick()
    assert zaehler.explosion is not explosion and not zaehler.explosion.beendet
    zaehler.explosion._takt.stop()

    monkeypatch.setattr(desktop_beagle, "beagle_rund", lambda groesse: QPixmap())
    leer = desktop_beagle.BeagleExplosion(fenster, QPointF(10, 10))
    assert leer.beendet and not leer._takt.isActive() and not leer.isVisible()


def test_reiterbezeichnungen_sind_fett():
    from desktop_darstellung import _erzeuge_qss, _DESIGN_DEFAULT, _THEME_DEFAULT

    qss = _erzeuge_qss(_THEME_DEFAULT, _DESIGN_DEFAULT)
    block = qss.split("QTabBar::tab {", 1)[1].split("}", 1)[0]
    assert "font-weight: 600" in block
