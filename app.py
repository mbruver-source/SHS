"""
Desktop-Oberfläche (PySide6) des SHS-Prüfungsprogramms: Hauptfenster, Startdialog und
Programmstart (`main`). Die Reiter, Dialoge und Hilfen liegen in den Modulen desktop_*.py
(seit 19.10.2026; die Reiter Teilnehmer, Formular-Import und Ergebniserfassung seit 11.11.2026
in desktop_teilnehmer.py, desktop_formular.py und desktop_ergebnis.py);
Überblick siehe Architektur.md.

Deckt einen ersten End-to-End-Ablauf ab:
  1. Termin anlegen oder öffnen (eine .sqlite-Datei pro Veranstaltung)
  2. Teilnehmer erfassen, bearbeiten, löschen (mit Rückfrage). Startnummern werden
     gesammelt aus den Bereichen je Prüfung vergeben ("Fehlende Startnummern
     vergeben…", UX-Test U1) oder einzeln in der Maske; beim Speichern wird gegen
     bereits vergebene Startnummern geprüft (auch als Datenbank-Constraint
     abgesichert) - eine doppelte Vergabe ist so ausgeschlossen.
  3. Ergebnisse je Disziplin eintragen (Zellen ohne Vorbelegung - eine leere
     Zelle gilt als "noch nicht eingetragen", damit sie nicht versehentlich als
     0-Punkte-Bewertung gespeichert wird), filterbar nach Art/Leistungsklasse(/
     Disziplin) und nach Startnummer
  4. Auswertung (Wertnote + Rangliste) ansehen, ebenfalls filterbar nach
     Art/Leistungsklasse(/Disziplin) und nach Startnummer

Verletzt eine Eingabe eine Fachregel aus der Datenbank (z. B. Punktzahl
außerhalb des gültigen Bereichs oder eine doppelt vergebene Startnummer),
erscheint ein Fehlerdialog statt eines Absturzes.

Die Berechnungslogik selbst steckt vollständig in shs_core.py/db.py und ist
dort unabhängig von der Oberfläche getestet - dieses Fenster ruft sie nur auf.
"""

from __future__ import annotations

import contextlib
import os
import sqlite3
import sys
import traceback

from PySide6.QtCore import (
    QEvent,
    QFile,
    QSettings,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QDesktopServices,  # noqa: F401 - Tests ersetzen app.QDesktopServices.openUrl
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from db import (
    datum_anzeige,
    entfernte_fremdobjekte,
    get_veranstaltung,
    init_db,
    liste_termine,
    list_teilnehmer,
    termin_oeffnen,
    TerminNichtOeffenbar,
    TerminUngewoehnlichGross,
    GRUND_ZU_GROSS,
    set_veranstaltung,
    termine_ordner,
)
from db_sicherung import auto_sicherung_erstellen
import pdf_export  # noqa: F401 - Tests ersetzen app.pdf_export.*
from desktop_darstellung import (
    _SETTINGS_APP,
    _SETTINGS_ORG,
    _darstellung_anwenden,
    _design_speichern,
    _DESIGNS,
    _gespeichertes_design_lesen,
    _gespeicherte_schriftstufe_lesen,
    _gespeichertes_theme_lesen,
    _schriftstufe_speichern,
    _SCHRIFTSTUFEN,
    _theme_speichern,
    _THEMES,
)
from desktop_gemeinsam import zugaengliche_namen_setzen
from desktop_gemeinsam import (
    _ohne_nachfrage_lesen,
    _ohne_nachfrage_speichern,
    _sicherung_vor_loeschen_lesen,
    _sicherung_vor_loeschen_speichern,
    _fehlertext,
    _klartext_fehler,
    fehler_protokollieren,
    fehlerfenster_zeigen,
    qt_meldungen_protokollieren,
    _Ablageort,
    absturzprotokoll_einrichten,
    fehlerfenster_einrichten,
    laufwerksart,
    meldungsfenster_als_klartext,
    programmsymbol,
    _ausdrucke_ordner,
    _ja_nein,
    deutsche_qt_texte_laden,
    _ausfuehren,
    _wartecursor,
    _pfad_anzeige,
    ResponsiveSchriftMixin,
    KopfBalken,
    symbol_setzen,
    symbole_auffrischen,
)
from desktop_dialoge import (
    HilfeDialog,
    VeranstaltungsDialog,
)
from desktop_beagle import BeagleKlickZaehler
from desktop_demo import DemoTour, demo_ohne_termin_ausfuehren, demo_reste_aufraeumen
from desktop_auswertung import AuswertungTab, ExportTab, TeilnehmerUebersichtTab
from desktop_abrechnung import AbrechnungTab
from desktop_zeitplan import ZeitplanTab
from desktop_verwaltung import DatensicherungTab, VerwaltungTab
from desktop_programm import VERSION, VersionDialog, laufkennung_setzen, sitzungsende_einrichten, zweitstart_pruefen
from desktop_teilnehmer import TeilnehmerTab
from desktop_formular import FormularImportTab
from desktop_ergebnis import ErgebnisTab


def _fenstertitel(conn, pfad: str | None, demo: bool) -> str:
    """Titel aus Verein und Datum, ohne Verein der Dateiname (Teil 8 Nr. 3)."""
    praefix = "DEMO – " if demo else ""
    veranstaltung = get_veranstaltung(conn) or {}
    name = str(veranstaltung.get("verein") or os.path.basename(pfad or "") or "Termin")
    datum = datum_anzeige(str(veranstaltung["datum"])) if veranstaltung.get("datum") else ""
    return f"{praefix}SHS Prüfungsprogramm – {name}" + (f" ({datum})" if datum else "")


def _termin_oeffnen_mit_meldung(parent, pfad: str):
    """Öffnet einen Termin über db.termin_oeffnen; lässt er sich nicht öffnen (keine
    Termin-Datei, beschädigt, schreibgeschützt, unbekannte Werte), erscheint eine
    verständliche Meldung und das Ergebnis ist None - der bisherige Termin bzw. der
    Startdialog bleibt (Desktop-Prüfung 14.10.2026, Teil 7 Nr. 4). Bei einer ungewöhnlich
    großen Datei wird vorher nachgefragt (offene Punkte O2, Marco 18.10.2026)."""
    try:
        try:
            return termin_oeffnen(pfad)
        except TerminUngewoehnlichGross as exc:
            antwort = QMessageBox.question(
                parent, "Ungewöhnlich große Termin-Datei",
                f"„{os.path.basename(pfad)}“: {exc}\n\nTrotzdem öffnen?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if antwort != QMessageBox.Yes:
                return None
            return termin_oeffnen(pfad, groesse_bestaetigt=True)
    except TerminNichtOeffenbar as exc:
        meldung = str(exc)
    except (sqlite3.Error, OSError) as exc:
        fehler_protokollieren(exc)
        meldung = _klartext_fehler(exc)
    QMessageBox.warning(parent, "Termin lässt sich nicht öffnen", f"„{os.path.basename(pfad)}“:\n\n{meldung}")
    return None


def _fremdobjekte_melden(parent) -> None:
    """Sicherheitsprüfung 03.10.2026, H-1: Hinweis, wenn init_db() aus der gerade geöffneten
    Termin-Datei fremde Datenbank-Regeln (Trigger/Views) entfernt hat."""
    entfernt = entfernte_fremdobjekte()
    if entfernt:
        QMessageBox.warning(
            parent, "Termin-Datei bereinigt",
            "Die Termin-Datei enthielt unerwartete Datenbank-Regeln, die das Programm selbst nie "
            "anlegt. Sie wurden zur Sicherheit entfernt:\n\n" + "\n".join(entfernt[:10])
            + ("\n…" if len(entfernt) > 10 else "")
            + "\n\nDie Teilnehmer und Ergebnisse selbst sind unverändert. Stammt die Datei "
            "nicht von dir, prüfe die Ergebnisse bitte kurz.",
        )


def _auswahl_menue_aufbauen(besitzer, menue, eintraege: dict, aktiv: str, slot) -> dict[str, QAction]:
    """Menü mit genau einer wählbaren Möglichkeit (Hintergrund, Akzentfarbe, Schriftgröße) -
    gemeinsam für das Hauptfenster und den Startbildschirm (Marco 10.11.2026)."""
    actions: dict[str, QAction] = {}
    gruppe = QActionGroup(besitzer)
    gruppe.setExclusive(True)
    gruppe.triggered.connect(slot)
    for schluessel, daten in eintraege.items():
        action = QAction(daten["anzeigename"], besitzer)
        action.setCheckable(True)
        action.setChecked(schluessel == aktiv)
        action.setData(schluessel)
        menue.addAction(action)
        gruppe.addAction(action)
        actions[schluessel] = action
    return actions


class HauptFenster(ResponsiveSchriftMixin, QMainWindow):
    def __init__(self, conn, pfad: str, demo: bool = False):
        super().__init__()
        self.resize(900, 600)
        # Laufende Demoprüfung (desktop_demo.DemoTour) oder None.
        self._demo_tour = None
        self.auto_sicherung_aktiv = False
        # H-4: True, sobald _sitzungsende_pruefen das Beenden durch Windows/Setup erlaubt
        # hat - das folgende closeEvent prüft dann nicht erneut. Ein abgebrochenes Abmelden
        # setzt es über SitzungsendeFilter zurück.
        self._beenden_freigegeben = False
        self._theme_menue_aufbauen()

        # Hilfe-Button ganz rechts in der Kopfzeile (davor "Anderen Termin öffnen…",
        # "Version" und "Demoprüfung") -
        # optisch in der Nähe der nativen Minimieren/Maximieren/Schließen-Schaltflächen
        # des Betriebssystems. Ein Button lässt sich in Qt nicht direkt IN die native
        # Titelleiste selbst setzen (die gehört dem Betriebssystem). Hinweis: ein Ecken-
        # Widget auf der (damals noch leeren) QMenuBar wurde zunächst versucht,
        # blieb aber unsichtbar, weil eine Menüleiste ohne eigene Menüeinträge auf
        # vielen Windows-Stilen auf Höhe 0 kollabiert. Die Kopfzeile hier ist Teil des
        # normalen zentralen Layouts und daher zuverlässig sichtbar.
        # Seit dem Erscheinungsbild „Beagle“ (Marco 01.11.2026) ein dunkler Kopfbalken mit
        # dem Beagle, Verein und Termin-Angaben (KopfBalken); Symbole statt Emojis.
        hilfe_btn = QPushButton("Hilfe")
        # Nachtest 2 (N6): wie F1 beim Abschnitt des aktuellen Reiters, nicht ganz oben.
        hilfe_btn.setToolTip("Hilfe zum aktuellen Reiter (F1)")
        hilfe_btn.clicked.connect(self._hilfe_zum_reiter)

        version_btn = QPushButton(f"Version {VERSION}")
        # UX-Test 03.11.2026, X16: Werner fand den Update-Weg nicht.
        version_btn.setToolTip("Version anzeigen und nach Updates suchen")
        version_btn.clicked.connect(self._version_anzeigen)

        self._tabs = QTabWidget()
        self._tabs.currentChanged.connect(self._tab_gewechselt)
        self._vorheriger_tab_index = 0

        self.wechseln_btn = QPushButton("Anderen Termin öffnen…")
        self.wechseln_btn.clicked.connect(self._termin_wechseln)

        # Marcos Wunsch 04.10.2026: geführte Demoprüfung mit erfundenen Daten (desktop_demo).
        self.demo_btn = QPushButton("Demoprüfung")
        self.demo_btn.setToolTip(
            "Spielt einmal einen kompletten Prüfungstag mit erfundenen Daten vor – "
            "deine Termine bleiben unverändert."
        )
        self.demo_btn.clicked.connect(self._demo_starten)

        # Marco 09.11.2026: von jedem Reiter direkt zur Checkliste im Reiter „Verwaltung“.
        self.checkliste_btn = QPushButton("Checkliste")
        self.checkliste_btn.setToolTip("Springt zur Checkliste zum Prüfungstermin (Reiter „Verwaltung“)")
        self.checkliste_btn.clicked.connect(self._zur_checkliste)

        self.kopf = KopfBalken()
        self.kopf.knopf_hinzufuegen(self.wechseln_btn, "folder-open")
        self.kopf.knopf_hinzufuegen(self.checkliste_btn, "check")
        self.kopf.knopf_hinzufuegen(version_btn, "info-circle")
        self.kopf.knopf_hinzufuegen(self.demo_btn, "school")
        self.kopf.knopf_hinzufuegen(hilfe_btn, "help-circle")
        self._beagle_zaehler = BeagleKlickZaehler(self, self.kopf.bild_label)  # siehe desktop_beagle

        # Kopfbalken randlos über die ganze Breite, die Reiter mit Abstand darunter.
        reiter_huelle = QWidget()
        reiter_layout = QVBoxLayout(reiter_huelle)
        reiter_layout.setContentsMargins(10, 10, 10, 10)
        reiter_layout.addWidget(self._tabs)

        zentral = QWidget()
        zentral_layout = QVBoxLayout(zentral)
        zentral_layout.setContentsMargins(0, 0, 0, 0)
        zentral_layout.setSpacing(0)
        zentral_layout.addWidget(self.kopf)
        zentral_layout.addWidget(reiter_huelle, 1)
        self.setCentralWidget(zentral)

        self._termin_setzen(conn, pfad, demo=demo)
        self._schriftgroesse_anwenden()

    def _theme_menue_aufbauen(self) -> None:
        # Eine einzige Verbindung auf QActionGroup.triggered (statt einer eigenen
        # lambda-Verbindung pro Action in der Schleife) - eine pro-Action-lambda, die
        # `self` einfängt, hat beim Schließen/Zerstören des Fensters in Tests
        # (qtbot-Teardown) zu einem Hänger geführt (vermutlich ein PySide6-Problem mit
        # der Verbindungs-Buchhaltung bei lambda-Slots + Objektzerstörung). Das hier
        # verwendete Muster (ein einziger, echter gebundener Methodenaufruf, das Theme
        # über QAction.data() statt über eine eingefangene Schleifenvariable
        # identifiziert) ist der Qt-übliche Weg für QActionGroups und tritt in den
        # GUI-Tests (test_gui_*.py) nicht mehr auf.
        # Dasselbe Muster gilt für beide Untermenüs (Hintergrund + Akzentfarbe).
        ansicht_menue = self.menuBar().addMenu("&Ansicht")
        self._design_actions = self._auswahl_menue_aufbauen(
            ansicht_menue.addMenu("Hintergrund"), _DESIGNS, _gespeichertes_design_lesen(),
            self._design_aktion_ausgeloest,
        )
        self._theme_actions = self._auswahl_menue_aufbauen(
            ansicht_menue.addMenu("Akzentfarbe"), _THEMES, _gespeichertes_theme_lesen(),
            self._theme_aktion_ausgeloest,
        )
        # UX-Test 03.11.2026, X2: Schrift vergrößern (vorher nur „Hoher Kontrast“, der die
        # Größe nicht ändert - die Hilfe versprach es trotzdem).
        self._schrift_actions = self._auswahl_menue_aufbauen(
            ansicht_menue.addMenu("Schriftgröße"), _SCHRIFTSTUFEN, _gespeicherte_schriftstufe_lesen(),
            self._schrift_aktion_ausgeloest,
        )
        # Marco 12.11.2026: Wer weiß, was er tut, soll nicht bei jedem Löschen gebremst werden -
        # die Sicherung vor dem Löschen ist deshalb ein Schalter (Standard aus).
        einstellungen_menue = self.menuBar().addMenu("&Einstellungen")
        self._sicherung_vor_loeschen_action = einstellungen_menue.addAction(
            "Vor dem Löschen von Teilnehmern eine Sicherung anlegen")
        self._sicherung_vor_loeschen_action.setCheckable(True)
        self._sicherung_vor_loeschen_action.setChecked(_sicherung_vor_loeschen_lesen())
        self._sicherung_vor_loeschen_action.toggled.connect(_sicherung_vor_loeschen_speichern)
        self._sicherung_vor_loeschen_action.setToolTip(
            "Legt vor jedem Löschen eine Kopie des Termins im Ordner „Auto-Sicherung“ an "
            "(die letzten 10 je Termin).")
        # Marco 12.11.2026: dieselbe Einstellung wie das Kästchen im Reiter „Ausdrucke/Export“,
        # damit alle Schalter an einem Ort zu finden sind; beide bleiben gleich (siehe
        # _ohne_nachfrage_aus_menue / _ohne_nachfrage_vom_reiter).
        self._ohne_nachfrage_action = einstellungen_menue.addAction(
            "Dateien ohne Nachfrage im Ablageort speichern")
        self._ohne_nachfrage_action.setCheckable(True)
        self._ohne_nachfrage_action.setChecked(_ohne_nachfrage_lesen())
        self._ohne_nachfrage_action.setToolTip(
            "Gilt für alle Reiter mit PDF-Export. Der Dateiname kommt aus dem Vorschlag; eine "
            "vorhandene Datei wird nie überschrieben, sondern bekommt „ (2)“ im Namen.")
        self._ohne_nachfrage_action.toggled.connect(self._ohne_nachfrage_aus_menue)
        # UX-Test 2026-11, T9: Die Update-Suche stand nur hinter dem Knopf „Version …“ - Werner
        # suchte sie in einem Menü.
        hilfe_menue = self.menuBar().addMenu("&Hilfe")
        # T8: F1 öffnet die Hilfe beim Abschnitt des aktuellen Reiters.
        hilfe_menue.addAction("Hilfe anzeigen", QKeySequence.HelpContents, self._hilfe_zum_reiter)
        hilfe_menue.addAction("Nach Updates suchen…", self._updates_suchen)
        hilfe_menue.addAction("Version und Lizenzen", self._version_anzeigen)
        self._kuerzel_einrichten()

    def _kuerzel_einrichten(self) -> None:
        """Tastenkürzel (Marco 10.11.2026, UI-Abgleich: es gab nur Entf, Strg+S und F1):
        Strg+F springt ins Suchfeld des Reiters, Strg+N legt einen Teilnehmer an, Strg+1 bis
        Strg+9 wechseln den Reiter."""
        QShortcut(QKeySequence.Find, self, activated=self._suche_fokussieren)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self._neuer_teilnehmer_per_kuerzel)
        for nummer in range(1, 10):
            kuerzel = QShortcut(QKeySequence(f"Ctrl+{nummer}"), self)
            kuerzel.setProperty("reiter_index", nummer - 1)
            # Kein Lambda mit self: das hielte das Hauptfenster über einen Verweis am Leben
            # (Tests schließen es dann erst beim Aufräumen, mit noch ersetzten Funktionen).
            kuerzel.activated.connect(self._reiter_kuerzel_ausgeloest)

    def _suche_fokussieren(self) -> None:
        feld = getattr(self._tabs.currentWidget(), "filter_name", None)
        if feld is not None:
            feld.setFocus()
            feld.selectAll()

    def _neuer_teilnehmer_per_kuerzel(self) -> None:
        index = self._tabs.indexOf(self.teilnehmer_tab)
        if self._demo_tour is not None or index < 0 or not self._tabs.isTabEnabled(index):
            return  # z. B. während der Demoprüfung gesperrt
        self._tabs.setCurrentIndex(index)
        self.teilnehmer_tab.hinzufuegen_btn.click()

    def _reiter_kuerzel_ausgeloest(self) -> None:
        index = self.sender().property("reiter_index") if self.sender() is not None else None
        if index is not None:
            self._reiter_per_kuerzel(int(index))

    def _reiter_per_kuerzel(self, index: int) -> None:
        if 0 <= index < self._tabs.count() and self._tabs.isTabEnabled(index):
            self._tabs.setCurrentIndex(index)

    def _auswahl_menue_aufbauen(self, menue, eintraege: dict, aktiv: str, slot) -> dict[str, QAction]:
        return _auswahl_menue_aufbauen(self, menue, eintraege, aktiv, slot)

    def _theme_aktion_ausgeloest(self, action: QAction) -> None:
        self._theme_wechseln(action.data())

    def _design_aktion_ausgeloest(self, action: QAction) -> None:
        self._design_wechseln(action.data())

    def _schrift_aktion_ausgeloest(self, action: QAction) -> None:
        self._schrift_wechseln(action.data())

    def _schrift_wechseln(self, stufe: str) -> None:
        _schriftstufe_speichern(stufe)
        self._darstellung_neu_anwenden()
        # Die an die Fensterbreite angepassten Beschriftungen und die Ergebnistabelle
        # rechnen ihre Größe nur bei Größenänderungen neu - hier einmal anstoßen, in allen
        # Fenstern (auch einem zweiten Hauptfenster der Demo, Abschluss-QS A11).
        ResponsiveSchriftMixin.alle_neu_anwenden()

    def _an_bildschirm_anpassen(self) -> None:
        """Marco 05.11.2026 (nach 1.0.56): War das Fenster bei großer Schrift breiter als der
        Bildschirm geworden, blieb es das nach dem Zurückschalten - erst Minimieren/Maximieren
        half. Passt das Fenster wieder in den freien Bereich, falls es größer ist (mit Rahmen) -
        sofern seine Mindestgröße überhaupt hineinpasst, sonst wäre es ein Sprung ohne Wirkung."""
        bildschirm = self.screen() or QApplication.primaryScreen()
        if bildschirm is None:
            return
        frei = bildschirm.availableGeometry()
        rahmen = self.frameGeometry()
        if frei.contains(rahmen):
            return
        rand_breite, rand_hoehe = rahmen.width() - self.width(), rahmen.height() - self.height()
        mindest = self.minimumSizeHint()
        if mindest.width() + rand_breite > frei.width() or mindest.height() + rand_hoehe > frei.height():
            return
        if self.isMaximized():
            # Ein maximiertes Fenster übernimmt die Bildschirmgröße erst nach erneutem Maximieren.
            self.showNormal()
            self.showMaximized()
            return
        self.resize(min(self.width(), frei.width() - rand_breite), min(self.height(), frei.height() - rand_hoehe))
        rahmen = self.frameGeometry()
        self.move(min(max(rahmen.x(), frei.x()), frei.right() - rahmen.width() + 1),
                  min(max(rahmen.y(), frei.y()), frei.bottom() - rahmen.height() + 1))

    def _theme_wechseln(self, theme_name: str) -> None:
        _theme_speichern(theme_name)
        self._darstellung_neu_anwenden()

    def _design_wechseln(self, design_name: str) -> None:
        _design_speichern(design_name)
        self._darstellung_neu_anwenden()

    def _darstellung_neu_anwenden(self) -> None:
        # Lasttest 16.10.2026: Qt gestaltet dabei jedes Widget neu - bei 1000 Teilnehmern
        # rund 3 s (vor allem die Zellen der Ergebniserfassung), daher der Wartecursor.
        with _wartecursor():
            _darstellung_anwenden(QApplication.instance())
            self._farben_auffrischen()
            self.kopf.farben_aktualisieren()
            # Übrige Knöpfe mit Symbol (Zeitplan-Pfeile, Formular-Import, Demo-Fenster).
            symbole_auffrischen(self)
        # Nach dem Neu-Layout alle Hauptfenster (auch das der Demo) wieder auf den Bildschirm
        # einpassen - Schrift, Design und Akzent ändern Mindestbreiten (nach 1.0.56).
        for fenster in QApplication.topLevelWidgets():
            if isinstance(fenster, HauptFenster):
                QTimer.singleShot(0, fenster, fenster._an_bildschirm_anpassen)

    def _farben_auffrischen(self) -> None:
        """Färbt Tabelleninhalte nach einem Darstellungswechsel neu. Teilnehmer,
        Auswertung und Zeitplan laden dafür neu (keine ungespeicherten Eingaben dort);
        die Ergebniserfassung färbt nur um, damit ungespeicherte Punkte erhalten bleiben."""
        for tab in (self.teilnehmer_tab, self.auswertung_tab, self.zeitplan_tab):
            tab.aktualisieren()
        self.ergebnis_tab.farben_auffrischen()

    def _hilfe_zum_reiter(self) -> None:
        reiter = self._tabs.tabText(self._tabs.currentIndex()).replace("&", "")
        _ausfuehren(HilfeDialog(self, abschnitt=f'Reiter "{reiter}"'))

    def _zur_checkliste(self) -> None:
        """Wechselt zum Reiter „Verwaltung“ und zeigt dort die Checkliste (klappt die erste
        Kategorie mit offenen Punkten auf)."""
        index = self._tabs.indexOf(self.verwaltung_tab)
        if index < 0 or not self._tabs.isTabEnabled(index):
            return  # z. B. während der Demoprüfung gesperrt
        self._tabs.setCurrentIndex(index)
        self.verwaltung_tab.zur_checkliste()

    def _version_anzeigen(self) -> None:
        _ausfuehren(VersionDialog(self))

    def _updates_suchen(self) -> None:
        _ausfuehren(VersionDialog(self, updates_sofort_suchen=True))

    def _demo_starten(self) -> None:
        """Startet die Demoprüfung (desktop_demo.DemoTour) im Temp-Ordner; der geöffnete
        Termin wird am Ende wiederhergestellt."""
        if self._demo_tour is not None:
            # Während der Demo holt der Knopf das Erklärfenster zurück (Teil 10 Nr. 9).
            self._demo_tour.panel_zeigen()
            return
        # Keine Rückfrage beim Start (Desktop-Prüfung 14.10.2026, Teil 10 Nr. 8): verworfen
        # wird erst beim Umschalten auf den Demo-Termin in Schritt 2, und dort fragt die Demo
        # nach (desktop_demo, Verifikation 04.10.2026, Befund 5).
        try:
            DemoTour(fenster=self).starten()
        except Exception as exc:  # noqa: BLE001 - z. B. Temp-Ordner voll/nicht beschreibbar
            # Desktop-Prüfung 14.10.2026, Teil 10 Nr. 5: verständliche Meldung statt des
            # allgemeinen Fehlerfensters; starten() hat schon aufgeräumt.
            QMessageBox.warning(self, "Demoprüfung nicht möglich",
                                f"Die Demoprüfung konnte nicht gestartet werden.\n\n{_fehlertext(exc)}")

    def _demo_sperren(self, aktiv: bool) -> None:
        """Während der Demo kein Terminwechsel und kein zweiter Demo-Start; der Demo-Knopf
        holt stattdessen das Erklärfenster zurück, falls es verdeckt oder verschoben ist
        (Desktop-Prüfung 14.10.2026, Teil 10 Nr. 9)."""
        self.wechseln_btn.setEnabled(not aktiv)
        if not hasattr(self, "_demo_tooltip"):
            self._demo_tooltip = self.demo_btn.toolTip()
        self.demo_btn.setText("Erklärfenster zeigen" if aktiv else "Demoprüfung")
        self.demo_btn.setToolTip(
            "Holt das Erklärfenster der laufenden Demoprüfung wieder nach vorn." if aktiv else self._demo_tooltip
        )

    def changeEvent(self, event) -> None:  # noqa: N802
        # R6 (Verifikation A3b/A5b, Befund 1): Unter Windows kommt beim Maximieren das
        # resizeEvent, bevor isMaximized() umspringt - die Ergebnistabelle rechnete dann mit
        # dem alten Zustand. Nach dem Zustandswechsel deshalb noch einmal anpassen.
        if event.type() == QEvent.WindowStateChange and hasattr(self, "ergebnis_tab"):
            QTimer.singleShot(0, self, self.ergebnis_tab._spaltenbreiten_anpassen)
        super().changeEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Speichert automatisch noch nicht gespeicherte Ergebnisse, bevor das Programm
        beendet wird - auf Wunsch des Nutzers, damit beim Schließen (z.B. über das
        Fenster-X) nichts verloren geht, ohne dass dafür extra nachgefragt werden muss
        (anders als beim Tabwechsel/Terminwechsel, wo weiterhin gefragt wird, siehe
        _tab_gewechselt/_ungespeicherte_ergebnisse_klaeren unten).

        QS-Fund (19./20.09.): alle_speichern() kann NICHT jede Zeile speichern - z.B.
        wenn nur eines von zwei zusammengehörigen Feldern ausgefüllt ist, zeigt es zwar
        eine Warnung, lässt die betroffene Zeile aber ungespeichert. Vorher schloss sich
        das Fenster direkt danach TROTZDEM (event.accept() ohne erneute Prüfung) - die
        Warnung verschwand zusammen mit dem Fenster, ohne dass die Änderung je gespeichert
        wurde und ohne dass der Nutzer noch die Möglichkeit gehabt hätte, sie zu
        korrigieren. Nach dem Speicherversuch wird deshalb erneut geprüft: bleiben
        Änderungen ungespeichert übrig, wird - genau wie bei
        _ungespeicherte_ergebnisse_klaeren (Terminwechsel, Demoprüfung) - nachgefragt, ob
        trotzdem beendet (und diese Änderungen
        verworfen) oder das Schließen abgebrochen werden soll, damit die fehlerhafte
        Zeile noch korrigiert werden kann. Vorbelegter Standard ist "Nein" (nicht
        schließen), wie bei allen Rückfragen, die Änderungen verwerfen würden; bei der
        ersten Rückfrage "Speichern/Verwerfen/Abbrechen" ist "Speichern" vorbelegt.

        H-4: Hat _sitzungsende_pruefen das Beenden durch Windows/Setup gerade erlaubt
        (Qt ruft closeEvent erst danach über quit() auf), wird ohne zweite Prüfung
        geschlossen - sonst kämen Warnung und Rückfrage doppelt, und ein "Nein" würde das
        bereits zugesagte Beenden blockieren. Wird das Abmelden doch abgebrochen, nimmt
        SitzungsendeFilter die Freigabe zurück."""
        freigegeben = self._beenden_freigegeben
        self._beenden_freigegeben = False
        if freigegeben:
            # Desktop-Prüfung 14.10.2026, Teil 8 Nr. 10: Unter X11 kann das Abmelden nach der
            # Freigabe doch abgebrochen werden; inzwischen getippte Ergebnisse dann still
            # mitspeichern statt sie zu verlieren (unter Windows ist das ein No-op).
            if self.ergebnis_tab.hat_ungespeicherte_aenderungen():
                self.ergebnis_tab.alle_speichern()
            event.accept()
            return
        if self._beenden_vorbereiten():
            event.accept()
        else:
            event.ignore()

    def _beenden_vorbereiten(self, rueckfrage_moeglich: bool = True) -> bool:
        """Gemeinsame Logik für closeEvent und das Beenden durch Windows/Setup
        (_sitzungsende_pruefen): Demoprüfung beenden, ungespeicherte Ergebnisse automatisch
        speichern, bei Resten nachfragen. True = Beenden erlaubt. Ohne erlaubte Rückfrage
        (rueckfrage_moeglich=False) erscheint auch beim Speichern keine Meldung, und bei Resten
        wird nicht gefragt, sondern abgelehnt."""
        # Laufende Demoprüfung zuerst beenden: sie stellt den echten Termin wieder her (die
        # Prüfung unten gilt dann ihm) bzw. schließt ihr eigenes Fenster samt Demo-Termin.
        tour = self._demo_tour
        if tour is not None:
            tour.beenden()
            if tour.eigenes_fenster:
                return True
        if self.ergebnis_tab.hat_ungespeicherte_aenderungen():
            if rueckfrage_moeglich:
                self.ergebnis_tab.alle_speichern()
            else:  # keine Meldungsfenster, die das System nicht erlaubt (OFFEN.md B5)
                self.ergebnis_tab.alle_speichern(meldungen=False)
            if self.ergebnis_tab.hat_ungespeicherte_aenderungen():
                if not rueckfrage_moeglich:
                    return False
                return _ja_nein(
                    self,
                    "Nicht alle Ergebnisse gespeichert",
                    "Nicht alle Ergebnisse konnten automatisch gespeichert werden (siehe "
                    "vorherige Meldung).\n\nProgramm trotzdem beenden und diese ungespeicherten "
                    "Änderungen verwerfen?",
                )
        # Marco 12.11.2026: Ein Löschen lässt sich nach dem Beenden nicht mehr zurücknehmen
        # („Rückgängig“ gilt nur bis dahin). Gefragt wird nur, solange es noch offen ist - nicht
        # bei jedem Beenden - und nie beim Beenden durch Windows/Setup (keine Meldungsfenster).
        if rueckfrage_moeglich and self.teilnehmer_tab.loeschung_noch_rueckgaengig():
            return _ja_nein(
                self,
                "Beenden nach dem Löschen",
                "Du hast Teilnehmer gelöscht. Nach dem Beenden lässt sich das nicht mehr "
                "rückgängig machen.\n\nProgramm trotzdem beenden?",
            )
        return True

    def _sitzungsende_pruefen(self, manager) -> None:
        """Handler für QGuiApplication.commitDataRequest (siehe main()).

        Sicherheitshinweis H-4 (Verifikation 05.10.2026): Schließt Windows die App beim
        Abmelden oder das Setup beim Update (Restart Manager), fragt Qt 6 bei
        WM_QUERYENDSESSION nur über dieses Signal, ob beendet werden darf. closeEvent kommt
        erst danach (WM_ENDSESSION -> quit()), wenn die Zusage schon gegeben ist - ein
        Ablehnen ist nur hier möglich. Hier läuft deshalb dieselbe Logik wie beim
        Fenster-X; bleibt etwas ungespeichert und wird nicht ausdrücklich verworfen, lehnt
        manager.cancel() das Beenden ab (Setup meldet dann, dass die App noch läuft, weil
        installer.iss CloseApplications=yes statt force nutzt). Bei Zusage merkt sich das
        Fenster die Freigabe, damit das folgende closeEvent nicht erneut fragt (siehe
        SitzungsendeFilter für den abgebrochenen Fall)."""
        rueckfrage = manager.allowsInteraction()
        try:
            self._beenden_freigegeben = self._beenden_vorbereiten(rueckfrage_moeglich=rueckfrage)
            if not self._beenden_freigegeben:
                manager.cancel()
        finally:
            if rueckfrage:
                manager.release()

    def _termin_setzen(self, conn, pfad: str, demo: bool = False) -> None:
        """Verbindet das Fenster mit einem (neuen oder anfänglichen) Termin: baut alle Tabs
        für diesen Termin neu auf und setzt den Titel. `demo`: Termin der Demoprüfung -
        Titel mit "DEMO", Reiter "Datensicherung" gesperrt (arbeitet auf den echten
        Terminen).

        Desktop-Prüfung 14.10.2026, Teil 7 Nr. 4 und 9: Erst werden die neuen Reiter
        vollständig aufgebaut und der Titel berechnet; scheitert das, bleibt das Fenster
        unverändert (Ausnahme an den Aufrufer). Erst danach wird ausgetauscht, und die alten Reiter werden gelöscht statt
        bei jedem Terminwechsel liegen zu bleiben."""
        # Ein gemeinsames _Ablageort-Objekt für alle Reiter mit Exporten (Teilnehmer,
        # Auswertung, Zeitplan, Export), damit ein bewusst gewählter Speicherort überall als
        # neuer Standard gilt (siehe _Ablageort).
        # UX-Test 02.10.2026, U7: PDFs standardmäßig in "Ausdrucke/<Termin>" statt
        # zwischen den Termin-Dateien.
        ablageort = _Ablageort(_ausdrucke_ordner(pfad) if pfad else str(termine_ordner()))
        fabriken = [
            ("teilnehmer_tab", "Teilnehmer", lambda: TeilnehmerTab(conn, pfad=pfad, ablageort=ablageort)),
            ("formular_import_tab", "Formular-Import", lambda: FormularImportTab(conn, ablageort=ablageort)),
            ("zeitplan_tab", "Zeitplan", lambda: ZeitplanTab(conn, ablageort)),
            ("ergebnis_tab", "Ergebniserfassung", lambda: ErgebnisTab(conn, ablageort=ablageort)),
            ("auswertung_tab", "Auswertung", lambda: AuswertungTab(conn, ablageort)),
            ("teilnehmer_uebersicht_tab", "Übersicht", lambda: TeilnehmerUebersichtTab(conn, ablageort=ablageort)),
            ("abrechnung_tab", "Abrechnung Leistungsrichter", lambda: AbrechnungTab(conn, ablageort)),
            ("verwaltung_tab", "Verwaltung", lambda: VerwaltungTab(conn, ablageort=ablageort)),
            ("export_tab", "Ausdrucke/Export", lambda: ExportTab(conn, pfad, ablageort)),
            # Anders als die übrigen Tabs NICHT an conn/pfad gebunden - arbeitet immer auf dem
            # gesamten Termine-Ordner (siehe DatensicherungTab oben), wird aber trotzdem hier
            # neu aufgebaut, damit sie sich wie die anderen Tabs beim Terminwechsel verhält.
            # aktueller_pfad wird nur mitgegeben, damit ein Wiederherstellen den gerade
            # geöffneten Termin nicht versehentlich überschreibt (siehe DatensicherungTab).
            ("datensicherung_tab", "Datensicherung", lambda: DatensicherungTab(aktueller_pfad=pfad, conn=conn)),
        ]
        neue: list[tuple[str, str, QWidget]] = []
        try:
            for attribut, titel, fabrik in fabriken:
                neue.append((attribut, titel, fabrik()))
        except BaseException:
            for _attribut, _titel, widget in neue:
                widget.deleteLater()
            raise

        try:
            fenstertitel = _fenstertitel(conn, pfad, demo)
        except BaseException:
            for _attribut, _titel, widget in neue:
                widget.deleteLater()
            raise

        # Ab hier nur noch Austausch.
        self.conn = conn
        self.pfad = pfad
        self._demo_termin = demo
        self.auto_sicherung_anlegen()
        self._tabs.blockSignals(True)
        try:
            while self._tabs.count():
                alt = self._tabs.widget(0)
                self._tabs.removeTab(0)
                alt.deleteLater()
            for attribut, titel, widget in neue:
                setattr(self, attribut, widget)
                self._tabs.addTab(widget, titel)
            if demo:
                index = self._tabs.indexOf(self.datensicherung_tab)
                self._tabs.setTabEnabled(index, False)
                self._tabs.setTabToolTip(
                    index, "Während der Demoprüfung gesperrt – dieser Reiter arbeitet mit deinen echten Terminen."
                )
        finally:
            self._tabs.blockSignals(False)
        self.verwaltung_tab.veranstaltung_geaendert.connect(self._titel_aktualisieren)
        self.teilnehmer_tab.teilnehmer_geaendert.connect(self._kopf_aktualisieren)
        self.export_tab.ohne_nachfrage_check.toggled.connect(self._ohne_nachfrage_vom_reiter)
        self._ohne_nachfrage_action.setChecked(self.export_tab.ohne_nachfrage_check.isChecked())
        self.setWindowTitle(fenstertitel)
        self._kopf_aktualisieren()

        self._vorheriger_tab_index = 0

    def _ohne_nachfrage_aus_menue(self, an: bool) -> None:
        """Menü „Einstellungen“ geändert: speichern und das Kästchen im Reiter angleichen."""
        _ohne_nachfrage_speichern(an)
        kaestchen = self.export_tab.ohne_nachfrage_check
        if kaestchen.isChecked() != an:
            kaestchen.setChecked(an)

    def _ohne_nachfrage_vom_reiter(self, an: bool) -> None:
        """Kästchen im Reiter geändert (es speichert selbst): Menüeintrag angleichen."""
        if self._ohne_nachfrage_action.isChecked() != an:
            self._ohne_nachfrage_action.setChecked(an)

    def _titel_aktualisieren(self) -> None:
        """Fenstertitel aus Verein und Datum; fehlt der Verein (fremde Datei), der Dateiname
        statt „None“ (Desktop-Prüfung 14.10.2026, Teil 8 Nr. 3). Auch nach „Veranstaltungs-
        daten bearbeiten…“ aufgerufen (Teil 2 Nr. 5)."""
        self.setWindowTitle(_fenstertitel(self.conn, self.pfad, getattr(self, "_demo_termin", False)))
        self._kopf_aktualisieren()

    def _kopf_aktualisieren(self) -> None:
        """Kopfbalken: Verein (ohne Verein der Dateiname wie im Fenstertitel), Datum, Ort und
        Zahl der Teilnehmenden (ohne „keine Teilnahme“). Nach Terminwechsel, „Veranstaltungs-
        daten bearbeiten…“ und bei jedem Reiterwechsel (Teilnehmer angelegt/gelöscht)."""
        veranstaltung = get_veranstaltung(self.conn) or {}
        verein = veranstaltung.get("verein") or os.path.basename(self.pfad or "") or "Termin"
        anzahl = len(list_teilnehmer(self.conn, nur_teilnehmende=True))
        self.kopf.termin_setzen(verein, veranstaltung.get("datum"), veranstaltung.get("ort"),
                                anzahl, getattr(self, "_demo_termin", False))

    def laufwerk_hinweis_zeigen(self) -> None:
        """Liegt der Termin auf einem USB-Stick oder Netzlaufwerk, einmal darauf hinweisen
        (Marco 10.11.2026): Abziehen oder Verbindungsverlust stören das Speichern erst spät."""
        art = laufwerksart(self.pfad)
        if not art or getattr(self, "_demo_termin", False):
            return
        QMessageBox.information(
            self, f"Termin auf einem {art}",
            f"Der Termin liegt auf einem {art}:\n{self.pfad}\n\n"
            "Solange das Programm geöffnet ist, den Datenträger nicht abziehen und die Verbindung "
            "nicht trennen - Änderungen könnten sonst verloren gehen. Eine automatische Kopie des Termins "
            "legt das Programm zusätzlich auf diesem Rechner ab.")

    def auto_sicherung_anlegen(self, ohne_mindestabstand: bool = False) -> None:
        """Automatische Kopie des Termins (Marco 10.11.2026) - nur im echten Programmlauf
        (`auto_sicherung_aktiv`, von main() gesetzt; Tests und Demo schreiben nichts).
        Beim Beenden `ohne_mindestabstand`: der Stand der Sitzung wird immer gesichert."""
        if not self.auto_sicherung_aktiv or getattr(self, "_demo_termin", False):
            return
        try:
            if ohne_mindestabstand:
                auto_sicherung_erstellen(self.conn, self.pfad, mindestabstand_sekunden=0)
            else:
                auto_sicherung_erstellen(self.conn, self.pfad)
        except Exception as exc:  # noqa: BLE001 - eine Sicherung darf die Arbeit nie stören
            fehler_protokollieren(exc)

    def _termin_wechseln(self) -> None:
        """Öffnet den Startdialog erneut, damit ohne Neustart der Anwendung zu einem
        anderen Termin gewechselt werden kann.

        Die Rückfrage nach ungespeicherten Ergebnissen kommt erst nach der Auswahl im
        Startdialog (offener Punkt 18.10.2026): bei „Abbrechen“ im Dialog wird gar nicht
        gefragt, und bei der Demo fragt deren Schritt 2 selbst (sonst käme die Frage zweimal)."""
        dialog = StartDialog(self, aktueller_pfad=self.pfad)
        if _ausfuehren(dialog) != QDialog.Accepted:
            return
        if dialog.demo_angefordert:
            try:
                DemoTour(fenster=self).starten()
            except Exception as exc:  # noqa: BLE001 - wie in _demo_starten (Teil 10 Nr. 5)
                QMessageBox.warning(self, "Demoprüfung nicht möglich",
                                    f"Die Demoprüfung konnte nicht gestartet werden.\n\n{_fehlertext(exc)}")
            return
        if not dialog.pfad:
            return
        if not self._ungespeicherte_ergebnisse_klaeren("Trotzdem den Termin wechseln"):
            if getattr(dialog, "neu_angelegt", False):
                self._neu_angelegten_termin_entfernen(dialog.pfad)
            return

        neue_verbindung = _termin_oeffnen_mit_meldung(self, dialog.pfad)
        if neue_verbindung is None:
            return  # bisheriger Termin bleibt geöffnet
        _fremdobjekte_melden(self)
        alte_verbindung = self.conn
        try:
            self._termin_setzen(neue_verbindung, dialog.pfad)
        except Exception as exc:  # noqa: BLE001
            # Aufbau der Reiter gescheitert: _termin_setzen hat noch nichts ausgetauscht.
            neue_verbindung.close()
            fehler_protokollieren(exc)
            QMessageBox.warning(
                self, "Termin lässt sich nicht öffnen",
                f"„{os.path.basename(dialog.pfad)}“ ließ sich nicht anzeigen - die Datei enthält "
                "Angaben, die das Programm nicht verarbeiten kann. Der bisherige Termin bleibt "
                "geöffnet. (Details stehen im Absturzprotokoll, siehe Version → Diagnose kopieren.)",
            )
            return
        alte_verbindung.close()
        if self.auto_sicherung_aktiv:
            self.laufwerk_hinweis_zeigen()  # auch beim Wechsel auf einen Termin auf Stick/Netzlaufwerk

    def _neu_angelegten_termin_entfernen(self, pfad: str) -> None:
        """Der Startdialog hat den Termin eben erst angelegt, der Wechsel wurde dann bei der
        Rückfrage abgebrochen: die leere Datei kommt in den Papierkorb, statt liegen zu
        bleiben (Marco 18.10.2026). Klappt das nicht, bleibt sie liegen; der Hinweis nennt
        den Ort (sie kann außerhalb des Termine-Ordners liegen)."""
        name = os.path.basename(pfad)
        try:
            entfernt = StartDialog._in_papierkorb(pfad)
        except OSError:
            entfernt = False
        # Ist die Datei inzwischen ohnehin weg (z. B. FileNotFoundError), gilt sie als entfernt.
        entfernt = entfernt or not os.path.exists(pfad)
        if entfernt:
            text = f"Der eben neu angelegte Termin „{name}“ wurde wieder entfernt (Papierkorb)."
        else:
            text = (
                f"Der eben neu angelegte Termin „{name}“ ließ sich nicht in den Papierkorb "
                f"verschieben. Die leere Datei bleibt unter „{_pfad_anzeige(pfad)}“ und kann "
                "gelöscht werden (im Termine-Ordner auch über den Startdialog)."
            )
        QMessageBox.information(self, "Neuer Termin entfernt" if entfernt else "Neuer Termin bleibt", text)

    def _rueckfrage_ungespeichert(self, verwerfen: bool) -> str:
        """Gemeinsame Rückfrage bei ungespeicherten Ergebnissen (Desktop-Prüfung 14.10.2026,
        Teil 8 Nr. 2): "speichern", "weiter" (ohne Speichern) oder "abbrechen". Esc und das
        Fenster-X bedeuten Abbrechen. `verwerfen`: ob "ohne Speichern" die Eingaben verliert
        (Termin-/Demowechsel) oder sie nur ungespeichert stehen bleiben (Reiterwechsel) - das
        steht ausdrücklich im Text, weil derselbe Knopf sonst Verschiedenes bedeutet."""
        if verwerfen:
            text = (
                "In der Ergebniserfassung gibt es noch nicht gespeicherte Änderungen.\n\n"
                "„Speichern“ speichert sie jetzt. „Verwerfen“ wechselt ohne Speichern – die "
                "Änderungen gehen dann verloren. „Abbrechen“ bleibt im aktuellen Termin."
            )
            knoepfe = QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
        else:
            text = (
                "In der Ergebniserfassung gibt es noch nicht gespeicherte Änderungen.\n\n"
                "Jetzt speichern? Bei „Nein“ bleiben sie ungespeichert in der Tabelle stehen. "
                "„Abbrechen“ bleibt in der Ergebniserfassung."
            )
            knoepfe = QMessageBox.Save | QMessageBox.No | QMessageBox.Cancel
        antwort = QMessageBox.question(self, "Ungespeicherte Ergebnisse", text, knoepfe, QMessageBox.Save)
        # Yes/No zusätzlich, damit ältere Ja/Nein-Attrappen in Tests weiter passen.
        if antwort in (QMessageBox.Save, QMessageBox.Yes):
            return "speichern"
        if antwort in (QMessageBox.Discard, QMessageBox.No):
            return "weiter"
        return "abbrechen"

    def _ungespeicherte_ergebnisse_klaeren(self, verwerfen_frage: str) -> bool:
        """Vor dem Verlassen des Termins (Terminwechsel, Demoprüfung): bei ungespeicherten
        Ergebnissen nachfragen und ggf. speichern. False = Vorgang abbrechen."""
        if self.ergebnis_tab.hat_ungespeicherte_aenderungen():
            antwort = self._rueckfrage_ungespeichert(verwerfen=True)
            if antwort == "abbrechen":
                return False
            if antwort == "speichern":
                self.ergebnis_tab.alle_speichern()
                # Codeprüfung 22.09., G3: wie in closeEvent - alle_speichern() kann nicht
                # jede Zeile speichern (z. B. nur Suche ODER Anzeige eingetragen). Ohne
                # erneute Prüfung ging der Wechsel trotzdem weiter und die nicht
                # gespeicherte Zeile beim Neuaufbau der Tabs still verloren. Standard ist
                # deshalb "Nein" (Wechsel abbrechen, Zeile korrigieren).
                if self.ergebnis_tab.hat_ungespeicherte_aenderungen():
                    if not _ja_nein(
                        self,
                        "Nicht alle Ergebnisse gespeichert",
                        "Nicht alle Ergebnisse konnten gespeichert werden (siehe vorherige "
                        f"Meldung).\n\n{verwerfen_frage} und diese ungespeicherten "
                        "Änderungen verwerfen?",
                    ):
                        return False
        return True

    def _tab_gewechselt(self, index: int) -> None:
        # Beim Verlassen der Ergebniserfassung mit noch nicht gespeicherten Änderungen
        # nachfragen, statt sie stillschweigend zu verwerfen.
        voriges_widget = self._tabs.widget(self._vorheriger_tab_index)
        if voriges_widget is self.ergebnis_tab and self.ergebnis_tab.hat_ungespeicherte_aenderungen():
            antwort = self._rueckfrage_ungespeichert(verwerfen=False)
            if antwort == "abbrechen":
                # In der Ergebniserfassung bleiben (ohne erneute Rückfrage).
                self._tabs.blockSignals(True)
                self._tabs.setCurrentIndex(self._vorheriger_tab_index)
                self._tabs.blockSignals(False)
                return
            if antwort == "speichern":
                self.ergebnis_tab.alle_speichern()

        self._vorheriger_tab_index = index
        # Teilnehmerzahl im Kopfbalken (z. B. nach dem Anlegen im Reiter „Teilnehmer“).
        self._kopf_aktualisieren()
        widget = self._tabs.widget(index)
        if widget is self.ergebnis_tab and self.ergebnis_tab.hat_ungespeicherte_aenderungen():
            # Speichern wurde bewusst abgelehnt - neu laden, ohne diese Eingaben zu
            # verwerfen (z. B. damit ein inzwischen als "keine Teilnahme" markierter
            # Teilnehmer verschwindet).
            self.ergebnis_tab.aktualisieren_eingaben_erhalten()
            return
        if widget is self.ergebnis_tab:
            self.ergebnis_tab.aktualisieren_falls_geaendert()
            return
        if hasattr(widget, "aktualisieren"):
            widget.aktualisieren()


def _termin_datei_anlegen(dialog) -> None:
    """Rückruf für VeranstaltungsDialog beim Anlegen: legt die Termin-Datei an, solange
    sie noch nicht existiert (ob eine vorhandene Datei geöffnet werden soll, hat der Dialog
    schon gefragt; entsteht sie erst danach, wird nichts angelegt und nichts geöffnet). Scheitert das Anlegen (z. B. Ordner fehlt, Datenträger schreibgeschützt),
    wird eine halb angelegte Datei wieder entfernt und der Fehler an den Dialog gemeldet,
    der dann mit allen Eingaben offen bleibt (Desktop-Prüfung 14.10.2026)."""
    pfad = dialog.pfad_feld.text().strip()
    if os.path.exists(pfad):
        return
    try:
        conn = init_db(pfad)
        try:
            set_veranstaltung(conn, **dialog.veranstaltung_werte())
        finally:
            conn.close()
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(pfad)
        raise
    dialog.termin_angelegt = True


class StartDialog(ResponsiveSchriftMixin, QDialog):
    """Startdialog: Übersicht aller vorhandenen Termine aus dem Standard-Ordner (siehe
    db.termine_ordner) zum Öffnen/Löschen, sowie neuen Termin anlegen oder eine
    Termin-Datei an anderer Stelle öffnen (z. B. von einem USB-Stick)."""

    def __init__(self, parent=None, aktueller_pfad: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("SHS Prüfungsprogramm")
        self.resize(640, 440)
        self.pfad: str | None = None
        # "Demoprüfung" gewählt - der Aufrufer startet dann die Demo (desktop_demo).
        self.demo_angefordert = False
        # True, wenn `pfad` eben erst über „Neuen Termin anlegen“ entstanden ist - siehe
        # HauptFenster._neu_angelegten_termin_entfernen.
        self.neu_angelegt = False
        self._termine: list = []
        # Nur gesetzt, wenn der Dialog aus einem bereits offenen Hauptfenster heraus
        # ("Anderen Termin öffnen…") gestartet wurde - siehe _termin_loeschen.
        self._aktueller_pfad = aktueller_pfad

        button_zeile = self._liste_und_knoepfe_aufbauen()
        self._kopf_und_layout_aufbauen(button_zeile)

    def _liste_und_knoepfe_aufbauen(self) -> QHBoxLayout:
        """Terminliste mit Suche und die Knopfzeile (Neu, Öffnen, Löschen, andere Datei)."""
        self.tabelle = QTableWidget(0, 4)
        self.tabelle.setHorizontalHeaderLabels(["Datum", "Verein", "Ort", "Teilnehmer"])
        self.tabelle.verticalHeader().setVisible(False)  # keine Zeilennummern „1“, „2“ (Marco 01.11.2026)
        self.tabelle.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabelle.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabelle.setSelectionMode(QTableWidget.SingleSelection)
        self.tabelle.itemSelectionChanged.connect(self._auswahl_geaendert)
        self.tabelle.itemDoubleClicked.connect(lambda _item: self._termin_oeffnen())
        # Teil 7 Nr. 8: Enter in der Liste öffnet den markierten Termin (sonst griffe der
        # Standardknopf „Neuen Termin anlegen…“).
        self.tabelle.installEventFilter(self)
        self.tabelle.horizontalHeader().setStretchLastSection(True)
        # Marco 10.11.2026 (UI-Abgleich): bei vielen Terminen Suche (Verein, Ort, Datum) und
        # Sortierung per Klick auf die Spaltenüberschrift; Standard bleibt „neueste oben“.
        self._angezeigt: list = []
        self._sortspalte: int | None = None
        self._sortaufsteigend = True
        self.tabelle.horizontalHeader().setSectionsClickable(True)
        self.tabelle.horizontalHeader().sectionClicked.connect(self._spalte_geklickt)
        self.suche_feld = QLineEdit()
        self.suche_feld.setPlaceholderText("Suche nach Verein, Ort oder Datum")
        self.suche_feld.setClearButtonEnabled(True)
        self.suche_feld.textChanged.connect(lambda _text: self._aktualisieren())
        QShortcut(QKeySequence.Find, self, activated=self.suche_feld.setFocus)
        zugaengliche_namen_setzen(self, {
            "tabelle": "Terminliste",
            "suche_feld": "Suche nach Verein, Ort oder Datum",
        })

        neu_btn = QPushButton("Neuen Termin anlegen…")
        neu_btn.setObjectName("primaerButton")  # Haupt-Aktion des Startdialogs, siehe _QSS_TEMPLATE
        symbol_setzen(neu_btn, "plus", "#FFFFFF")  # weiß auf der Akzentfarbe
        neu_btn.clicked.connect(self._neuer_termin)
        self.oeffnen_btn = QPushButton("Öffnen")
        symbol_setzen(self.oeffnen_btn, "folder-open")
        self.oeffnen_btn.clicked.connect(self._termin_oeffnen)
        self.oeffnen_btn.setEnabled(False)
        self.loeschen_btn = QPushButton("Löschen…")
        self.loeschen_btn.clicked.connect(self._termin_loeschen)
        self.loeschen_btn.setEnabled(False)
        andere_datei_btn = QPushButton("Andere Termin-Datei öffnen…")
        andere_datei_btn.clicked.connect(self._andere_datei_oeffnen)

        button_zeile = QHBoxLayout()
        button_zeile.addWidget(neu_btn)
        button_zeile.addWidget(self.oeffnen_btn)
        button_zeile.addWidget(self.loeschen_btn)
        button_zeile.addStretch()
        button_zeile.addWidget(andere_datei_btn)
        return button_zeile

    def _kopf_und_layout_aufbauen(self, button_zeile: QHBoxLayout) -> None:
        """Hinweis, Kopfbalken mit Demo-Knopf und das Gesamtlayout."""
        # UX-Test 02.10.2026, U14: Laien fanden das Design "Hoher Kontrast" nicht.
        hinweis = QLabel(
            f"Neue Termine werden standardmäßig unter {termine_ordner()} gespeichert.\n"
            "Tipp: Schrift zu klein oder zu blass? Oben im Menü "
            "„Ansicht“ → „Schriftgröße“ bzw. „Hintergrund“ → „Hoher Kontrast“ wählen."
        )
        hinweis.setWordWrap(True)

        demo_btn = QPushButton("Demoprüfung")
        demo_btn.setToolTip(
            "Spielt einmal einen kompletten Prüfungstag mit erfundenen Daten vor – "
            "deine Termine bleiben unverändert."
        )
        demo_btn.clicked.connect(self._demo_waehlen)
        # Steht im Layout als erster Knopf - ohne das bekäme er beim Öffnen den Fokus und
        # würde als Standard-Knopf (Akzentfarbe, Enter) hervorgehoben statt "Neuen Termin anlegen…".
        demo_btn.setAutoDefault(False)
        # Kopfbalken wie im Hauptfenster, mit größerem Beagle (Marco 01.11.2026,
        # Erscheinungsbild „Beagle“); die Begrüßung darunter nur noch kurz.
        self.kopf = KopfBalken("SHS-Prüfungsprogramm", "Prüfungen im Spürhundsport verwalten", bildgroesse=52)
        self.kopf.knopf_hinzufuegen(demo_btn, "school")
        willkommen = QLabel("Termin wählen oder neu anlegen:")
        willkommen.setWordWrap(True)

        innen = QVBoxLayout()
        innen.setContentsMargins(12, 10, 12, 10)
        innen.addWidget(willkommen)
        innen.addWidget(self.suche_feld)
        innen.addWidget(self.tabelle)
        innen.addLayout(button_zeile)
        innen.addWidget(hinweis)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setMenuBar(self._menue_aufbauen())
        layout.addWidget(self.kopf)
        layout.addLayout(innen, 1)

        self.tabelle.setFocus()  # wie vor dem Demo-Knopf: Fokus zuerst auf der Terminliste
        self._aktualisieren()
        self._schriftgroesse_anwenden()

    def _menue_aufbauen(self) -> QMenuBar:
        """Menüs „Ansicht“ und „Hilfe“ wie im Hauptfenster (Marco 10.11.2026, UI-Abgleich: im
        Startbildschirm ließen sich Schrift und Hintergrund nicht einstellen)."""
        leiste = QMenuBar(self)
        ansicht_menue = leiste.addMenu("&Ansicht")
        self._design_actions = _auswahl_menue_aufbauen(
            self, ansicht_menue.addMenu("Hintergrund"), _DESIGNS, _gespeichertes_design_lesen(),
            lambda action: self._darstellung_wechseln(_design_speichern, action.data()))
        self._theme_actions = _auswahl_menue_aufbauen(
            self, ansicht_menue.addMenu("Akzentfarbe"), _THEMES, _gespeichertes_theme_lesen(),
            lambda action: self._darstellung_wechseln(_theme_speichern, action.data()))
        self._schrift_actions = _auswahl_menue_aufbauen(
            self, ansicht_menue.addMenu("Schriftgröße"), _SCHRIFTSTUFEN, _gespeicherte_schriftstufe_lesen(),
            lambda action: self._darstellung_wechseln(_schriftstufe_speichern, action.data()))
        hilfe_menue = leiste.addMenu("&Hilfe")
        hilfe_menue.addAction("Hilfe anzeigen", QKeySequence.HelpContents, lambda: _ausfuehren(HilfeDialog(self)))
        hilfe_menue.addAction("Nach Updates suchen…",
                              lambda: _ausfuehren(VersionDialog(self, updates_sofort_suchen=True)))
        hilfe_menue.addAction("Version und Lizenzen", lambda: _ausfuehren(VersionDialog(self)))
        return leiste

    def _darstellung_wechseln(self, speichern, wert: str) -> None:
        speichern(wert)
        with _wartecursor():
            _darstellung_anwenden(QApplication.instance())
            self.kopf.farben_aktualisieren()
            symbole_auffrischen(self)
        ResponsiveSchriftMixin.alle_neu_anwenden()

    def _spalte_geklickt(self, spalte: int) -> None:
        self._sortaufsteigend = not self._sortaufsteigend if self._sortspalte == spalte else True
        self._sortspalte = spalte
        self._aktualisieren(neu_lesen=False)

    @staticmethod
    def _termin_anzeigename(t) -> str:
        return (t.verein or t.dateiname) if t.lesbar else t.dateiname

    def _termine_anzeigen(self) -> list:
        """Die Termine nach Suchtext gefiltert und nach der gewählten Spalte sortiert."""
        woerter = self.suche_feld.text().casefold().split()
        termine = [
            t for t in self._termine
            if all(w in " ".join(str(x) for x in (self._termin_anzeigename(t), t.ort, datum_anzeige(t.datum), t.datum)
                                 if x).casefold() for w in woerter)
        ]
        if self._sortspalte is not None:
            schluessel = {
                0: lambda t: t.datum or "",
                1: lambda t: self._termin_anzeigename(t).casefold(),
                2: lambda t: (t.ort or "").casefold(),
                3: lambda t: t.teilnehmend if t.lesbar else -1,
            }[self._sortspalte]
            termine.sort(key=schluessel, reverse=not self._sortaufsteigend)
        return termine

    def _aktualisieren(self, neu_lesen: bool = True) -> None:
        if neu_lesen:
            self._termine = liste_termine()
        self._angezeigt = self._termine_anzeigen()
        self.tabelle.setRowCount(len(self._angezeigt))
        for row, t in enumerate(self._angezeigt):
            werte = [
                datum_anzeige(t.datum) or "?",
                (t.verein or t.dateiname) if t.lesbar
                # Eine nur zu große Datei lässt sich nach Rückfrage öffnen (Marco 19.10.2026).
                else f"{t.dateiname} (ungewöhnlich groß)" if t.grund == GRUND_ZU_GROSS
                else f"{t.dateiname} (nicht lesbar{': ' + t.grund if t.grund else ''})",
                t.ort or "",
                t.teilnehmer_anzeige if t.lesbar else "",
            ]
            for col, wert in enumerate(werte):
                self.tabelle.setItem(row, col, QTableWidgetItem(wert))
        # Spaltenbreiten an den tatsächlichen Inhalt anpassen, damit z.B. lange
        # Vereinsnamen nicht abgeschnitten werden - danach bleiben die Spalten
        # weiterhin von Hand nachziehbar.
        self.tabelle.resizeColumnsToContents()
        # UX-Test 03.11.2026, X15: Bei genau einem Termin diesen gleich markieren - „Öffnen“
        # war sonst ausgegraut, obwohl es nur einen gibt.
        if len(self._angezeigt) == 1 and self._angezeigt[0].lesbar:
            self.tabelle.selectRow(0)
        self._auswahl_geaendert()

    def eventFilter(self, obj, event) -> bool:  # type: ignore[override]
        if (obj is self.tabelle and event.type() == QEvent.KeyPress
                and event.key() in (Qt.Key_Return, Qt.Key_Enter) and self._ausgewaehlter_termin() is not None):
            self._termin_oeffnen()
            return True
        return super().eventFilter(obj, event)

    def _ausgewaehlter_termin(self):
        zeile = self.tabelle.currentRow()
        if 0 <= zeile < len(self._angezeigt):
            return self._angezeigt[zeile]
        return None

    def _auswahl_geaendert(self) -> None:
        hat_auswahl = self._ausgewaehlter_termin() is not None
        self.oeffnen_btn.setEnabled(hat_auswahl)
        self.loeschen_btn.setEnabled(hat_auswahl)

    def _neuer_termin(self) -> None:
        # Nutzerwunsch (20.09., Anmerkung Punkt 2): Verein/Vereins-Nr./Ort müssen nicht
        # jedes Mal neu eingetippt werden, wenn ohnehin wieder derselbe Verein gemeint
        # ist - Vorbelegung aus dem in der Terminübersicht obersten (nach Datum
        # neuesten) Termin, sofern schon einer existiert. Bleibt jederzeit überschreibbar,
        # das Datum selbst wird bewusst NICHT übernommen.
        vorbelegung = {}
        if self._termine:
            letzter = self._termine[0]
            vorbelegung = {
                "verein": letzter.verein,
                "vereins_nr": letzter.vereins_nr,
                "ort": letzter.ort,
                # Marco, 28.09.2026: Verband ebenfalls übernehmen, Meldestelle NICHT
                # (die wechselt je Termin).
                "verband": letzter.verband,
                # UX-Test U1 (Marco 03.10.2026): Startnummern-Bereiche ebenfalls übernehmen.
                "startnummer_bereiche": letzter.startnummer_bereiche,
                # Marco 09.10.2026: die Standardgröße der Bereiche ebenso.
                "startnummer_bereichsgroesse": letzter.startnummer_bereichsgroesse,
                # Marco 09.11.2026: die Sätze der Leistungsrichter-Abrechnung ebenso.
                "lr_km_satz": letzter.lr_km_satz,
                "lr_tagespauschale": letzter.lr_tagespauschale,
                # Marco 09.11.2026: eigene Kategorien/Punkte der Checkliste (ohne Haken).
                "checkliste_eigene": letzter.checkliste_eigene,
            }
        dialog = VeranstaltungsDialog(self, vorbelegung=vorbelegung, speichern=_termin_datei_anlegen)
        if _ausfuehren(dialog) != QDialog.Accepted:
            return
        pfad = dialog.pfad_feld.text().strip()

        # Desktop-Prüfung 14.10.2026 (Teil 2 Nr. 2): ob eine vorhandene Datei geöffnet werden
        # soll, hat der Dialog schon gefragt - bei „Nein“ bleiben dort die Eingaben stehen.
        # Geöffnet wird nur der angelegte bzw. der bewusst gewählte vorhandene Termin.
        if dialog.bestehenden_oeffnen or getattr(dialog, "termin_angelegt", False):
            self.pfad = pfad
            self.neu_angelegt = getattr(dialog, "termin_angelegt", False) and not dialog.bestehenden_oeffnen
            self.accept()

    def _termin_oeffnen(self) -> None:
        termin = self._ausgewaehlter_termin()
        if termin is None:
            return
        # Eine nur zu große Datei darf trotzdem geöffnet werden - die Rückfrage stellt
        # _termin_oeffnen_mit_meldung (offene Punkte O2).
        if not termin.lesbar and termin.grund != GRUND_ZU_GROSS:
            if termin.grund:
                QMessageBox.warning(self, "Datei nicht lesbar",
                                    f"„{termin.dateiname}“ ist {termin.grund} und lässt sich nicht als Termin-Datei lesen.")
            else:
                QMessageBox.warning(self, "Datei beschädigt", f"„{termin.dateiname}“ lässt sich nicht als Termin-Datei lesen.")
            return
        self.pfad = termin.pfad
        self.accept()

    def _termin_loeschen(self) -> None:
        termin = self._ausgewaehlter_termin()
        if termin is None:
            return
        if self._aktueller_pfad and os.path.abspath(termin.pfad) == os.path.abspath(self._aktueller_pfad):
            QMessageBox.warning(
                self, "Termin gerade geöffnet",
                "Dieser Termin ist gerade im Hauptfenster geöffnet und kann deshalb nicht "
                "gelöscht werden. Bitte zuerst einen anderen Termin öffnen oder das "
                "Programm schließen.",
            )
            return
        # Desktop-Prüfung 14.10.2026 (Teil 7 Nr. 5, Marcos Entscheidung): Vorgabe „Nein“ und
        # Löschen in den Papierkorb; ohne Papierkorb endgültig nach eigener Rückfrage.
        bezeichnung = f"„{termin.verein or termin.dateiname}“ ({datum_anzeige(termin.datum) or '?'})"
        if not _ja_nein(
            self,
            "Termin löschen",
            f"Termin {bezeichnung} inklusive aller Teilnehmer- und Ergebnisdaten in den Papierkorb "
            f"verschieben?\n\nDatei: {_pfad_anzeige(termin.pfad)}",
        ):
            return
        try:
            if not self._in_papierkorb(termin.pfad):
                if not _ja_nein(
                    self,
                    "Kein Papierkorb",
                    f"Der Termin {bezeichnung} lässt sich nicht in den Papierkorb verschieben (z. B. "
                    "auf einem USB-Stick oder Netzlaufwerk ohne Papierkorb, oder die Datei ist in "
                    "einem anderen Programm geöffnet). Endgültig löschen?",
                ):
                    return
                os.remove(termin.pfad)
        except OSError as exc:
            QMessageBox.critical(self, "Löschen fehlgeschlagen",
                                 f"Der Termin konnte nicht gelöscht werden.\n\n{_klartext_fehler(exc)}")
            return
        self._aktualisieren()
        # Danach ist nichts markiert - ein zweites „Löschen…“ + Enter träfe sonst den nächsten.
        self.tabelle.setCurrentItem(None)
        self.tabelle.clearSelection()
        self._auswahl_geaendert()

    @staticmethod
    def _in_papierkorb(pfad: str) -> bool:
        if not os.path.exists(pfad):
            raise FileNotFoundError(2, "No such file or directory", pfad)
        # PySide6 liefert hier je nach Version ein bool oder (bool, Pfad im Papierkorb).
        ergebnis = QFile.moveToTrash(pfad)
        return bool(ergebnis[0] if isinstance(ergebnis, tuple) else ergebnis)

    def _demo_waehlen(self) -> None:
        self.demo_angefordert = True
        self.accept()

    def _andere_datei_oeffnen(self) -> None:
        pfad, _ = QFileDialog.getOpenFileName(self, "Termin öffnen", str(termine_ordner()), "SHS-Termin (*.sqlite)")
        if pfad:
            self.pfad = pfad
            self.accept()


def _startdialog_schleife() -> str | None:
    """Zeigt den Startdialog, bis ein Termin gewählt oder abgebrochen wurde (None). Eine
    dort gestartete Demoprüfung läuft in einem eigenen Fenster; danach erscheint der
    Startdialog wieder."""
    while True:
        start = StartDialog()
        if _ausfuehren(start) != QDialog.Accepted:
            return None
        if start.demo_angefordert:
            try:
                demo_ohne_termin_ausfuehren(HauptFenster)
            except Exception as exc:  # noqa: BLE001
                # Teil 10 Nr. 5: Startfehler der Demo beendet nicht mehr das ganze Programm,
                # es geht zurück zum Startdialog.
                QMessageBox.warning(None, "Demoprüfung nicht möglich",
                                    f"Die Demoprüfung konnte nicht gestartet werden.\n\n{_fehlertext(exc)}")
            continue
        return start.pfad or None


_GEOMETRIE_SCHLUESSEL = "fenster/geometrie"
_MAXIMIERT_SCHLUESSEL = "fenster/maximiert"


def _auto_sicherung_beim_beenden(fenster) -> None:
    try:
        fenster.auto_sicherung_anlegen(ohne_mindestabstand=True)
    except RuntimeError:
        pass  # Fenster schon zerstört


def _fenstergeometrie_merken(fenster: QMainWindow) -> None:
    """Merkt Größe und Lage des Hauptfensters für den nächsten Start (Marco 10.11.2026)."""
    try:
        einstellungen = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        einstellungen.setValue(_MAXIMIERT_SCHLUESSEL, fenster.isMaximized())
        if not fenster.isMaximized():
            einstellungen.setValue(_GEOMETRIE_SCHLUESSEL, fenster.saveGeometry())
    except RuntimeError:
        pass  # Fenster schon zerstört


def _fenster_zeigen_wie_zuletzt(fenster: QMainWindow) -> None:
    """Maximiert (Standard, UX-Test 02.10.2026, U12) - hat der Anwender das Fenster zuletzt
    in normaler Größe benutzt, mit dieser Größe und Lage."""
    einstellungen = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
    maximiert = einstellungen.value(_MAXIMIERT_SCHLUESSEL, True) in (True, "true", "True", 1, "1")
    geometrie = einstellungen.value(_GEOMETRIE_SCHLUESSEL)
    if not maximiert and geometrie and fenster.restoreGeometry(geometrie):
        fenster.show()
        fenster._an_bildschirm_anpassen()
    else:
        fenster.showMaximized()


def main() -> int:
    # T1 (Marco 03.10.2026): "--selbsttest [protokoll]" prüft die gebündelte EXE ohne
    # Fenster (CI nach dem PyInstaller-Build und nach der Installation; auch zur
    # Fehlersuche beim Nutzer). Siehe selbsttest.py.
    if "--selbsttest" in sys.argv:
        from selbsttest import fuehre_selbsttest_aus

        position = sys.argv.index("--selbsttest")
        return fuehre_selbsttest_aus(sys.argv[position + 1] if len(sys.argv) > position + 1 else None)
    absturzprotokoll_einrichten(VERSION)
    laufkennung_setzen()  # für das Setup (AppMutex), siehe dort
    app = QApplication(sys.argv)
    # Fenster-, Taskleisten- und Dock-Symbol. Unter Linux (Wayland) ordnet die Desktop-
    # Umgebung das Fenster über den Namen der .desktop-Datei (AppImage/.deb) ihrem Symbol zu.
    app.setWindowIcon(programmsymbol())
    app.setDesktopFileName("shs-pruefungsprogramm")
    meldungsfenster_als_klartext()  # S-1: Namen in Meldungen nie als HTML
    fehlerfenster_einrichten(VERSION)  # unerwartete Fehler zusätzlich als Fenster zeigen
    qt_meldungen_protokollieren()
    deutsche_qt_texte_laden(app)
    _darstellung_anwenden(app)
    # Reste früherer Demoprüfungen (z. B. eine beim Beenden noch geöffnete PDF) wegräumen.
    if not zweitstart_pruefen():
        return 0
    demo_reste_aufraeumen()

    try:
        while True:
            pfad = _startdialog_schleife()
            if not pfad:
                return 0
            conn = _termin_oeffnen_mit_meldung(None, pfad)
            if conn is not None:
                break  # sonst zurück zum Startdialog
        _fremdobjekte_melden(None)

        fenster = HauptFenster(conn, pfad)
        sitzungsende_einrichten(app, fenster)
        # UX-Test 02.10.2026, U12: maximiert starten - bei 900x600 blieb für Tabellen und die
        # Zeitplan-Spalten zu wenig Platz.
        _fenster_zeigen_wie_zuletzt(fenster)
        fenster.auto_sicherung_aktiv = True
        fenster.auto_sicherung_anlegen()
        QTimer.singleShot(0, fenster.laufwerk_hinweis_zeigen)
        app.aboutToQuit.connect(lambda: _fenstergeometrie_merken(fenster))
        app.aboutToQuit.connect(lambda: _auto_sicherung_beim_beenden(fenster))
    except Exception as exc:  # noqa: BLE001 - Desktop-Prüfung 14.10.2026, Teil 9 Nr. 7
        fehler_protokollieren(exc)
        fehlerfenster_zeigen(
            VERSION, "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            programm_endet=True,
        )
        return 1
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
