"""
Erste Eingabemaske (Prototyp) für das SHS-Prüfungsprogramm.

Hinweis: Diese Datei benötigt PySide6 (`pip install pyside6`). In der
Sandbox, in der dieser Prototyp entstanden ist, ließ sich PySide6 nicht
installieren (kein Zugriff auf das Paket über den dortigen Paketindex) -
der Code ist deshalb sorgfältig nach Qt-Vorbild geschrieben, konnte hier
aber nicht selbst gestartet und geklickt werden. Bitte beim ersten Start
in einer normalen Umgebung mit Internetzugang kurz gegentesten.

Deckt einen ersten End-to-End-Ablauf ab:
  1. Termin anlegen oder öffnen (eine .sqlite-Datei pro Veranstaltung)
  2. Teilnehmer erfassen, bearbeiten, löschen (mit Rückfrage). Startnummern werden
     gesammelt aus den Bereichen je Prüfung vergeben ("Fehlende Startnummern
     vergeben…", UX-Test U1) oder einzeln in der Maske; beim Speichern wird gegen
     bereits vergebene Startnummern geprüft (auch als Datenbank-Constraint
     abgesichert) - eine doppelte Vergabe ist so ausgeschlossen.
  3. Ergebnisse je Disziplin eintragen (Eingabefelder ohne Vorbelegung - ein leeres
     Feld gilt als "noch nicht eingetragen", damit es nicht versehentlich als
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

import datetime
import html
import os
import re
import sqlite3
import sys

from PySide6.QtCore import QAbstractNativeEventFilter, QItemSelectionModel, QRegularExpression, QUrl, Qt
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QDesktopServices,
    QRegularExpressionValidator,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from db import (
    ALLE_DISZIPLINEN,
    BEHAELTNIS_BEDARF_HINWEIS,
    BEHAELTNIS_BEDARF_SPALTEN,
    BEHAELTNIS_BEDARF_TITEL,
    DISZIPLIN_SPALTEN,
    add_teilnehmer,
    add_zeitplan_pause,
    add_zeitplan_pruefungsblock,
    add_zeitplan_richter,
    aktualisiere_zeitplan_eintrag,
    alle_leistungsklassen,
    angebotene_pruefungen,
    automatische_zeitplan_verteilung,
    behaeltnis_bedarf_zeilentexte,
    berechne_auswertung,
    berechne_behaeltnis_bedarf,
    berechne_teilnehmer_lk_uebersicht,
    berechne_zeitplan,
    berechne_zeitplan_bloecke,
    datum_anzeige,
    delete_teilnehmer,
    eintragen_ergebnis,
    ergebnisse_je_teilnehmer,
    get_teilnehmer,
    entfernte_fremdobjekte,
    get_veranstaltung,
    hat_erfasste_ergebnisse,
    init_db,
    leistungsklasse_label,
    liste_termine,
    list_teilnehmer,
    list_zeitplan_richter,
    loesche_zeitplan_eintrag,
    loesche_zeitplan_richter,
    pruefe_ergebnis_eingabe,
    set_veranstaltung,
    setze_bezahlt,
    setze_ergebnis_status,
    setze_stechen_sieger,
    setze_keine_teilnahme,
    tausche_startnummern,
    teilnehmer_fehlende_pflichtangaben,
    teilnehmer_gegenstand_hinweis,
    termine_ordner,
    umbenennen_zeitplan_richter,
    update_teilnehmer,
    vergebene_startnummern,
    verschiebe_zeitplan_eintrag,
    verschiebe_zeitplan_richter,
    zeitplan_gruppen_status,
    zeitplan_richter_aus_veranstaltung_anlegen,
    fehlende_startnummern_vergeben,
    startnummer_bereiche,
    dk_mindestabstand,
    zeitplan_ueberschneidungen,
    add_zeitplan_pause_bei_allen,
    list_zeitplan_eintraege,
)
from db_import import (
    CSV_IMPORT_SPALTEN,
    importiere_anmeldeformular_pdf,
    importiere_teilnehmer_aus_csv,
    importiere_teilnehmer_aus_oma,
    importiere_teilnehmer_stammdaten,
    exportiere_teilnehmer_csv,
    schreibe_csv_vorlage,
)
from db_sicherung import (
    PasswortFalschError,
    sicherung_erstellen,
    sicherung_inhalt,
    sicherung_wiederherstellen,
)
import pdf_export
from shs_core import (
    ABBRUCH_ABK,
    ABBRUCH_TEXT,
    ANZEIGE_MAX,
    DISQUALIFIZIERT_ABK,
    DISQUALIFIZIERT_TEXT,
    SUCHE_MAX,
    platz_text,
    stechen_gruppen,
)
from desktop_darstellung import (
    _darstellung_anwenden,
    _design_speichern,
    _DESIGNS,
    _farbe,
    _gespeichertes_design_lesen,
    _gespeichertes_theme_lesen,
    _theme_speichern,
    _THEMES,
)
from desktop_gemeinsam import (
    _ABBRUCH_SPALTE,
    _Ablageort,
    absturzprotokoll_einrichten,
    meldungsfenster_als_klartext,
    _aktualisiere_veranstaltung_feld,
    _ausdrucke_ordner,
    _datei_gespeichert_melden,
    _db_fehler_anzeigen,
    deutsche_qt_texte_laden,
    _DQ_SPALTE,
    _ERGEBNIS_SPALTEN_JE_DISZIPLIN,
    _ergebnis_spaltenbreiten_verteilen,
    _export_dateiname,
    _fehler_anzeigen,
    _import_ordner_merken,
    _import_startordner,
    _NumerischSortierbaresItem,
    _pdf_export_fehler_anzeigen,
    _pdf_speicherort_waehlen,
    _pfad_anzeige,
    _responsive_schriftgroesse,
    ResponsiveSchriftMixin,
    _STATUS_SPALTE,
    _zeitplan_pdf_exportieren,
    _zentrierte_zelle,
)
from desktop_dialoge import (
    BewertungsbogenAuswahlDialog,
    HilfeDialog,
    PauseDialog,
    PruefungsblockDialog,
    SicherungErstellenDialog,
    StartnummerTauschenDialog,
    TeilnehmerDialog,
    TerminImportDialog,
    VeranstaltungsDialog,
    _wiederherstellungsziele_planen,
)
from desktop_demo import DemoTour, demo_ohne_termin_ausfuehren, demo_reste_aufraeumen
try:
    # version.py wird von bump_version.py automatisch erzeugt (siehe dort) und ist daher
    # in einer frischen Arbeitskopie vor dem allerersten Build noch nicht vorhanden - der
    # Fallback verhindert, dass app.py deswegen gar nicht erst startet.
    from version import VERSION
except ImportError:
    VERSION = "dev"


def _fehlende_startnummern_vergeben_mit_meldung(parent, conn) -> None:
    """UX-Test 02.10.2026, U1: Sammelvergabe (db.fehlende_startnummern_vergeben) mit
    verständlicher Abschlussmeldung - wer hat eine Nummer bekommen, wer nicht und warum."""
    if not startnummer_bereiche(get_veranstaltung(conn)):
        QMessageBox.information(
            parent, "Keine Startnummern-Bereiche",
            "Bitte zuerst in den Veranstaltungsdaten (Reiter „Verwaltung“ → "
            "„Veranstaltungsdaten bearbeiten…“) je Prüfung einen Startnummern-Bereich "
            "eintragen, z. B. DK-LK 1: 1 bis 20.",
        )
        return
    ergebnis = fehlende_startnummern_vergeben(conn)

    def namen(liste):
        return "\n".join(f"{t['vorname']} {t['nachname']} – {leistungsklasse_label(t)}" for t in liste)

    text = f"{len(ergebnis.vergeben)} Startnummer(n) vergeben."
    if ergebnis.ohne_bereich:
        text += "\n\nKeine Nummer, weil für die Prüfung kein Bereich eingetragen ist:\n" + namen(ergebnis.ohne_bereich)
    if ergebnis.bereich_voll:
        text += "\n\nKeine Nummer, weil der Bereich der Prüfung voll ist:\n" + namen(ergebnis.bereich_voll)
    QMessageBox.information(parent, "Startnummern vergeben", text)


def _startnummern_nach_import_anbieten(parent, conn) -> None:
    """UX-Test 02.10.2026, U1: Nach einem Import fehlen die Startnummern meist - direkt
    anbieten, sie gesammelt zu vergeben."""
    ohne = [t for t in list_teilnehmer(conn, nur_teilnehmende=True) if t["startnummer"] is None]
    if not ohne:
        return
    if not startnummer_bereiche(get_veranstaltung(conn)):
        QMessageBox.information(
            parent, "Startnummern fehlen",
            f"{len(ohne)} Teilnehmer haben noch keine Startnummer. Für die gesammelte Vergabe "
            "(„Fehlende Startnummern vergeben…“ im Reiter „Teilnehmer“) zuerst je Prüfung einen "
            "Startnummern-Bereich in den Veranstaltungsdaten eintragen (Reiter „Verwaltung“).",
        )
        return
    antwort = QMessageBox.question(
        parent, "Startnummern fehlen",
        f"{len(ohne)} Teilnehmer haben noch keine Startnummer.\n\nJetzt „Fehlende "
        "Startnummern vergeben“? (Bereits vergebene Nummern bleiben unverändert.)",
    )
    if antwort == QMessageBox.Yes:
        _fehlende_startnummern_vergeben_mit_meldung(parent, conn)


def _teilnehmerliste_importieren(parent, conn) -> None:
    """CSV-/Excel-Teilnehmerliste einlesen - gemeinsam für den Reiter "Formular-Import" und
    den Knopf im Reiter "Teilnehmer" (UX-Test 02.10.2026, U10)."""
    pfad, _ = QFileDialog.getOpenFileName(parent, "Teilnehmerliste einlesen", _import_startordner(), "CSV-Datei (*.csv)")
    if not pfad:
        return
    _import_ordner_merken(pfad)
    try:
        ergebnis = importiere_teilnehmer_aus_csv(conn, pfad)
    except OSError as exc:
        QMessageBox.warning(parent, "Import fehlgeschlagen", f"Die Datei konnte nicht gelesen werden:\n{exc}")
        return
    text = f"{ergebnis.importiert} Teilnehmer importiert."
    if ergebnis.uebersprungen:
        # UX-Nachtest 03.10.2026, N1: bereits vorhandene Meldungen werden nicht doppelt angelegt.
        text += (
            f"\n\n{len(ergebnis.uebersprungen)} Meldung(en) bereits vorhanden, nicht erneut angelegt:\n"
            + "\n".join(ergebnis.uebersprungen)
        )
    if ergebnis.fehler:
        text += f"\n\n{len(ergebnis.fehler)} Zeile(n) übersprungen:\n" + "\n".join(ergebnis.fehler)
    if ergebnis.hinweise:
        text += "\n\nHinweis: " + "\n".join(ergebnis.hinweise)
    QMessageBox.information(parent, "Import abgeschlossen", text)
    if ergebnis.importiert:
        _startnummern_nach_import_anbieten(parent, conn)



def _klartext_tooltip(text: str) -> str:
    """Sicherheitsprüfung 03.10.2026, S-1: Tooltips deutet Qt automatisch als HTML, sobald
    der Text danach aussieht. Enthält er Namen aus Importen, wird er deshalb maskiert und
    ausdrücklich als Rich Text ausgezeichnet - so erscheint er immer wörtlich."""
    return "<qt>" + html.escape(text).replace("\n", "<br>") + "</qt>"


class TeilnehmerTab(QWidget):
    def __init__(self, conn, parent=None, pfad: str | None = None, ablageort: _Ablageort | None = None):
        super().__init__(parent)
        self.conn = conn
        # Nur für TerminImportDialog: der eigene Dateipfad wird aus der Terminauswahl dort
        # ausgeschlossen, damit man nicht "aus sich selbst" importieren kann.
        self._pfad = pfad
        # Gemeinsamer Ablageort mit den Tabs "Zeitplan"/"Export" (siehe _Ablageort weiter
        # oben) - der Direkt-Export-Button "Bewertungsbogen (PDF)…" unten nutzt denselben
        # zuletzt gewählten Ordner wie die übrigen PDF-Exporte.
        self._ablageort = ablageort if ablageort is not None else _Ablageort(
            os.path.dirname(pfad) if pfad else str(termine_ordner())
        )
        self._teilnehmer_ids: list[int] = []  # Zeile -> Teilnehmer-ID, parallel zur Tabelle
        self._teilnehmer_je_zeile: list[dict] = []  # Zeile -> Teilnehmer-Datensatz, für den Filter

        self.tabelle = QTableWidget(0, 8)
        self.tabelle.setHorizontalHeaderLabels(
            ["Start-Nr.", "Nachname", "Vorname", "Hund", "Art/LK", "Verein", "Bezahlt", "Anmerkungen"]
        )
        self.tabelle.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabelle.setSelectionBehavior(QTableWidget.SelectRows)
        # UX-Test 02.10.2026, K7: Mehrfachmarkierung (Strg/Umschalt) für "Bezahlt
        # umschalten" und "Keine Teilnahme"; die übrigen Knöpfe brauchen genau eine Zeile.
        self.tabelle.setSelectionMode(QTableWidget.ExtendedSelection)
        self.tabelle.itemSelectionChanged.connect(self._auswahl_geaendert)
        # UX-Test 02.10.2026, U1: Doppelklick auf eine Zeile öffnet "Bearbeiten…".
        self.tabelle.itemDoubleClicked.connect(lambda _item: self._teilnehmer_bearbeiten())
        # Letzte Spalte füllt den restlichen Platz, wenn das Fenster größer ist als
        # die Summe der (an den Inhalt angepassten) Spaltenbreiten.
        self.tabelle.horizontalHeader().setStretchLastSection(True)
        # Die von Qt automatisch links angezeigte Zeilennummerierung (1, 2, 3, ...) ist
        # keine echte, überschriebene Spalte und trägt keine zusätzliche Information (die
        # Start-Nr. steht bereits in der ersten echten Spalte) - deshalb ausgeblendet,
        # ebenso in der Ergebniserfassung (siehe ErgebnisTab).
        self.tabelle.verticalHeader().setVisible(False)
        # Nutzerwunsch (20.09., Anmerkung zum Programm): "Filtermöglichkeit gut - kann hier
        # ggf. noch Sortierungsoption ergänzt werden?" - Klick auf eine Spaltenüberschrift
        # sortiert danach (Qt-Bordmittel), erneuter Klick kehrt die Richtung um. Die
        # Sortierung bleibt über aktualisieren() hinweg erhalten (siehe _sortierung_gemerkt/
        # aktualisieren) - ohne das würde jede Änderung (Speichern, Bezahlt umschalten, ...)
        # kommentarlos auf die Standard-Sortierung zurückspringen. Start-Nr. (Spalte 0,
        # aufsteigend) als Vorgabe entspricht der bisherigen, unveränderten Reihenfolge.
        self.tabelle.setSortingEnabled(True)
        self.tabelle.horizontalHeader().sortIndicatorChanged.connect(self._sortierung_gemerkt)
        self._sortierspalte = 0
        self._sortierreihenfolge = Qt.AscendingOrder

        self.filter_combo = QComboBox()
        # Passt die Breite der Box an den längsten enthaltenen Eintrag an (z.B. lange
        # Art/LK-Bezeichnungen wie "ED LK 3 Behältnisstrecke"), statt Text abzuschneiden.
        self.filter_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.filter_combo.currentTextChanged.connect(self._filter_anwenden)

        self.filter_startnummer = QLineEdit()
        self.filter_startnummer.setPlaceholderText("z.B. 13")
        self.filter_startnummer.setMaximumWidth(80)
        self.filter_startnummer.textChanged.connect(self._filter_anwenden)

        # Nutzerwunsch (20.09.): zusätzlicher Filter nach Bezahlt-Status, z.B. um am
        # Anmeldetisch schnell zu sehen, wer noch nicht bezahlt hat. Feste drei Einträge
        # (anders als filter_combo oben) - keine Neubefüllung bei jedem aktualisieren() nötig.
        self.filter_bezahlt = QComboBox()
        self.filter_bezahlt.addItems(["Alle", "Bezahlt", "Nicht bezahlt"])
        self.filter_bezahlt.currentTextChanged.connect(self._filter_anwenden)

        # Als Attribut (wie vergeben_btn unten), damit die Demoprüfung den Knopf markieren kann.
        self.hinzufuegen_btn = hinzufuegen_btn = QPushButton("Teilnehmer hinzufügen…")
        hinzufuegen_btn.setObjectName("primaerButton")  # Haupt-Aktion dieses Reiters, siehe _QSS_TEMPLATE
        hinzufuegen_btn.clicked.connect(self._teilnehmer_hinzufuegen)

        self.bearbeiten_btn = QPushButton("Bearbeiten…")
        self.bearbeiten_btn.clicked.connect(self._teilnehmer_bearbeiten)
        self.bearbeiten_btn.setEnabled(False)

        self.loeschen_btn = QPushButton("Löschen")
        self.loeschen_btn.clicked.connect(self._teilnehmer_loeschen)
        self.loeschen_btn.setEnabled(False)

        # Schnelles Umschalten der Bezahlt-Markierung (z.B. am Anmeldetisch), ohne dafür
        # jedes Mal den kompletten Bearbeiten-Dialog öffnen zu müssen.
        self.bezahlt_btn = QPushButton("Bezahlt umschalten")
        self.bezahlt_btn.clicked.connect(self._bezahlt_umschalten)
        self.bezahlt_btn.setEnabled(False)

        # Nutzerwunsch (02.10.2026): nicht erschienene Teilnehmer als "keine Teilnahme"
        # markieren - bleiben hier ausgegraut sichtbar, fallen aber aus allen
        # nachgelagerten Prozessen/Wertungen heraus (siehe db.list_teilnehmer). Der Text
        # wechselt je nach Auswahl auf "Teilnahme wiederherstellen" (_auswahl_geaendert).
        self.teilnahme_btn = QPushButton("Keine Teilnahme")
        self.teilnahme_btn.clicked.connect(self._teilnahme_umschalten)
        self.teilnahme_btn.setEnabled(False)

        # Nutzerwunsch (20.09.): Startnummern zweier Teilnehmer direkt tauschen können,
        # statt eine gewünschte, bereits vergebene Nummer erst manuell an anderer Stelle
        # "freimachen" zu müssen.
        self.tauschen_btn = QPushButton("Startnummer tauschen…")
        self.tauschen_btn.clicked.connect(self._startnummer_tauschen)
        self.tauschen_btn.setEnabled(False)

        # UX-Test 02.10.2026, U1: Startnummern für alle ohne Nummer auf einmal vergeben.
        self.vergeben_btn = vergeben_btn = QPushButton("Fehlende Startnummern vergeben…")
        vergeben_btn.clicked.connect(self._fehlende_startnummern_vergeben)

        # Nutzerwunsch (20.09., Anmerkung zum Programm): "Teilnehmer müssen wieder einzeln
        # eingegeben werden [...] ist Option möglich, von anderem Termin importieren?" -
        # übernimmt gezielt Stammdaten (nicht Startnummer/Gegenstände/Bezahlt-Status/
        # Ergebnis) aus einem anderen, bereits vorhandenen Termin.
        import_btn = QPushButton("Aus anderem Termin importieren…")
        import_btn.clicked.connect(self._aus_anderem_termin_importieren)

        # UX-Test 02.10.2026, U10: die Excel-/CSV-Liste auch direkt hier einlesen können
        # (Laien suchten sie im Reiter "Teilnehmer" bzw. unter "Aus anderem Termin").
        liste_btn = QPushButton("Teilnehmerliste einlesen (Excel/CSV)…")
        # N8 (nach 1.0.40): eindeutig "einlesen" - der fast gleich benannte Export-Knopf im
        # Reiter "Export" heißt "Teilnehmerliste speichern (CSV, für Excel)…".
        liste_btn.setToolTip(
            "Eine Excel-Liste (als CSV gespeichert) mit einer Zeile je Teilnehmer einlesen. "
            "Speichern als CSV geht im Reiter „Export“."
        )
        liste_btn.clicked.connect(self._teilnehmerliste_importieren)

        # Nutzerwunsch (21.09.): "In Teilnehmerliste Absprung zu Bewertungsbögen erzeugen
        # einfügen?" - Entscheidung (Rückfrage beantwortet): Direkt-Button pro Teilnehmer
        # statt nur eines Links zum Export-Tab, erzeugt sofort den Bewertungsbogen für den
        # ausgewählten Teilnehmer (siehe _bewertungsbogen_exportieren unten).
        self.bewertungsbogen_btn = QPushButton("Bewertungsbogen (PDF)…")
        self.bewertungsbogen_btn.clicked.connect(self._bewertungsbogen_exportieren)
        self.bewertungsbogen_btn.setEnabled(False)

        # Vor-Build-Klärung 03.10.2026 (U12): zehn Knöpfe in einer Zeile waren auf kleinen
        # Laptops breiter als der Bildschirm - zweizeilig: oben die Arbeit am markierten
        # Teilnehmer, unten Startnummern und Importe.
        button_zeile = QHBoxLayout()
        for knopf in (hinzufuegen_btn, self.bearbeiten_btn, self.loeschen_btn, self.bezahlt_btn,
                      self.teilnahme_btn, self.bewertungsbogen_btn):
            button_zeile.addWidget(knopf)
        button_zeile.addStretch()
        button_zeile_2 = QHBoxLayout()
        for knopf in (self.tauschen_btn, vergeben_btn, import_btn, liste_btn):
            button_zeile_2.addWidget(knopf)
        button_zeile_2.addStretch()

        filter_zeile = QHBoxLayout()
        filter_zeile.addWidget(QLabel("Filter Art/LK:"))
        filter_zeile.addWidget(self.filter_combo)
        filter_zeile.addSpacing(16)
        filter_zeile.addWidget(QLabel("Filter Start-Nr.:"))
        filter_zeile.addWidget(self.filter_startnummer)
        filter_zeile.addSpacing(16)
        filter_zeile.addWidget(QLabel("Filter Bezahlt:"))
        filter_zeile.addWidget(self.filter_bezahlt)
        filter_zeile.addStretch()

        self.status_label = QLabel("")
        self.status_label.setTextFormat(Qt.PlainText)  # S-1: enthält Pfade/Namen
        self.status_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addLayout(filter_zeile)
        layout.addWidget(self.tabelle)
        layout.addLayout(button_zeile)
        layout.addLayout(button_zeile_2)
        layout.addWidget(self.status_label)

        self.aktualisieren()

    def _ausgewaehlte_ids(self) -> list[int]:
        """IDs aller markierten und sichtbaren Teilnehmer in Tabellenreihenfolge. Durch den
        Filter ausgeblendete Zeilen zählen nicht mit, auch wenn sie noch markiert sind
        (z. B. nach Strg+A) - sonst würden unsichtbare Teilnehmer mit umgeschaltet."""
        ids = []
        for index in sorted(self.tabelle.selectionModel().selectedRows(), key=lambda i: i.row()):
            if self.tabelle.isRowHidden(index.row()):
                continue
            item = self.tabelle.item(index.row(), 0)
            if item is not None:
                ids.append(item.data(Qt.UserRole))
        return ids

    def _ausgewaehlte_id(self) -> int | None:
        """ID des markierten Teilnehmers - None bei keiner oder mehreren markierten Zeilen."""
        ids = self._ausgewaehlte_ids()
        return ids[0] if len(ids) == 1 else None

    def _auswahl_wiederherstellen(self, ids: set[int]) -> None:
        """Markiert nach dem Neuaufbau der Tabelle wieder dieselben Teilnehmer (K7) - vorher
        blieb die Markierung auf der Zeilennummer stehen und sprang nach dem Speichern auf
        einen anderen Teilnehmer, sobald sich die Sortierung verschob."""
        modell = self.tabelle.selectionModel()
        modell.clearSelection()
        erste = True
        for row in range(self.tabelle.rowCount()):
            item = self.tabelle.item(row, 0)
            if item is None or item.data(Qt.UserRole) not in ids:
                continue
            index = self.tabelle.model().index(row, 0)
            if erste:
                modell.setCurrentIndex(index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
                erste = False
            else:
                modell.select(index, QItemSelectionModel.Select | QItemSelectionModel.Rows)

    def _sortierung_gemerkt(self, spalte: int, reihenfolge) -> None:
        """Merkt sich die zuletzt per Spaltenklick gewählte Sortierung, damit
        aktualisieren() sie nach einer Änderung (Speichern, Bezahlt umschalten, ...)
        erneut anwenden kann, statt stillschweigend auf Start-Nr. zurückzuspringen."""
        self._sortierspalte = spalte
        self._sortierreihenfolge = reihenfolge

    def _filter_anwenden(self) -> None:
        """Blendet Zeilen anhand des aktuellen Filters nur aus/ein (setRowHidden) -
        entspricht dem gleichnamigen Filter in der Ergebniserfassung (siehe ErgebnisTab).
        Arbeitet über die tatsächliche (ggf. per Spaltenklick sortierte) Zeilenreihenfolge
        der Tabelle statt über die Listenreihenfolge aus der Datenbank - die beiden
        stimmen nach einer Sortierung nicht mehr zwingend überein (siehe _teilnehmer_je_id
        in aktualisieren())."""
        filter_wert = self.filter_combo.currentText()
        filter_startnr = self.filter_startnummer.text().strip()
        filter_bezahlt = self.filter_bezahlt.currentText()
        for row in range(self.tabelle.rowCount()):
            item = self.tabelle.item(row, 0)
            t = self._teilnehmer_je_id.get(item.data(Qt.UserRole)) if item is not None else None
            if t is None:
                continue
            passt = (
                (filter_wert in ("Alle", "") or leistungsklasse_label(t) == filter_wert)
                and (not filter_startnr or str(t["startnummer"] or "") == filter_startnr)
                and (
                    filter_bezahlt == "Alle"
                    or (filter_bezahlt == "Bezahlt") == bool(t["bezahlt"])
                )
            )
            self.tabelle.setRowHidden(row, not passt)
        self._auswahl_geaendert()  # K7: ausgeblendete Markierungen zählen nicht

    def _auswahl_geaendert(self) -> None:
        ausgewaehlte = [self._teilnehmer_je_id.get(i) for i in self._ausgewaehlte_ids()]
        ausgewaehlte = [t for t in ausgewaehlte if t is not None]
        hat_auswahl = bool(ausgewaehlte)
        genau_einer = len(ausgewaehlte) == 1
        self.bearbeiten_btn.setEnabled(genau_einer)
        # UX-Nachtest 03.10.2026: Löschen wirkt auf alle markierten (N1); bei genau zwei
        # markierten tauscht "Startnummer tauschen…" diese beiden direkt (N2).
        self.loeschen_btn.setEnabled(hat_auswahl)
        self.bezahlt_btn.setEnabled(hat_auswahl)
        self.tauschen_btn.setEnabled(
            (genau_einer and len(self._teilnehmer_je_zeile) > 1) or len(ausgewaehlte) == 2
        )
        nur_einer = "Nur bei genau einem markierten Teilnehmer möglich." if len(ausgewaehlte) > 1 else ""
        self.bearbeiten_btn.setToolTip(nur_einer)
        self.bewertungsbogen_btn.setToolTip(nur_einer)
        self.tauschen_btn.setToolTip(
            "Einen Teilnehmer markieren und den Partner wählen – oder genau zwei markieren."
            if len(ausgewaehlte) > 2 else ""
        )
        # Bei Mehrfachmarkierung: "wiederherstellen" nur, wenn ALLE markierten bereits
        # "keine Teilnahme" sind - sonst werden alle markierten als nicht erschienen markiert.
        keine_teilnahme = hat_auswahl and all(t.get("keine_teilnahme") for t in ausgewaehlte)
        self.teilnahme_btn.setEnabled(hat_auswahl)
        self.teilnahme_btn.setText("Teilnahme wiederherstellen" if keine_teilnahme else "Keine Teilnahme")
        # Für nicht erschienene Teilnehmer gibt es keinen Bewertungsbogen mehr.
        self.bewertungsbogen_btn.setEnabled(genau_einer and not keine_teilnahme)

    def _namen_je_startnummer(self, ausser_teilnehmer_id: int | None = None) -> dict[int, str]:
        """Für die Warnmeldung bei doppelt vergebener Startnummer im TeilnehmerDialog -
        wer hat die Nummer bereits (Name statt nur 'ist schon vergeben')."""
        return {
            t["startnummer"]: f"{t['nachname']}, {t['vorname']}"
            for t in list_teilnehmer(self.conn)
            if t["startnummer"] is not None and t["id"] != ausser_teilnehmer_id
        }

    def _teilnehmer_hinzufuegen(self) -> None:
        dialog = TeilnehmerDialog(
            self,
            vergebene_nummern=vergebene_startnummern(self.conn),
            namen_je_startnummer=self._namen_je_startnummer(),
            bereiche=startnummer_bereiche(get_veranstaltung(self.conn)),
        )
        if dialog.exec() == QDialog.Accepted:
            try:
                add_teilnehmer(self.conn, dialog.ergebnis())
            except sqlite3.IntegrityError as exc:
                _fehler_anzeigen(self, exc)
                return
            self.aktualisieren()

    def _teilnehmer_bearbeiten(self) -> None:
        teilnehmer_id = self._ausgewaehlte_id()
        if teilnehmer_id is None:
            return
        aktuelle_daten = next(t for t in list_teilnehmer(self.conn) if t["id"] == teilnehmer_id)
        dialog = TeilnehmerDialog(
            self,
            vorhandener=aktuelle_daten,
            vergebene_nummern=vergebene_startnummern(self.conn, ausser_teilnehmer_id=teilnehmer_id),
            namen_je_startnummer=self._namen_je_startnummer(ausser_teilnehmer_id=teilnehmer_id),
            bereiche=startnummer_bereiche(get_veranstaltung(self.conn)),
        )
        if dialog.exec() == QDialog.Accepted:
            try:
                update_teilnehmer(self.conn, teilnehmer_id, dialog.ergebnis())
            except sqlite3.IntegrityError as exc:
                _fehler_anzeigen(self, exc)
                return
            self.aktualisieren()

    def _startnummer_tauschen(self) -> None:
        ids = self._ausgewaehlte_ids()
        if len(ids) == 2:
            self._zwei_markierte_tauschen(*ids)
            return
        teilnehmer_id = self._ausgewaehlte_id()
        if teilnehmer_id is None:
            return
        alle = list_teilnehmer(self.conn)
        aktuell = next(t for t in alle if t["id"] == teilnehmer_id)
        andere = [t for t in alle if t["id"] != teilnehmer_id]
        if not andere:
            return
        dialog = StartnummerTauschenDialog(self, aktuell, andere)
        if dialog.exec() == QDialog.Accepted:
            partner_id = dialog.ausgewaehlte_partner_id()
            partner = next((t for t in andere if t["id"] == partner_id), None)
            if partner is not None and aktuell["startnummer"] is None and partner["startnummer"] is None:
                # UX-Test 02.10.2026, U1: vorher schloss der Dialog ohne Wirkung und Hinweis.
                QMessageBox.information(
                    self, "Nichts zu tauschen",
                    "Beide Teilnehmer haben noch keine Startnummer. Startnummern vergibst du "
                    "mit „Fehlende Startnummern vergeben…“ oder über „Bearbeiten…“.",
                )
                return
            if partner_id is not None:
                try:
                    tausche_startnummern(self.conn, teilnehmer_id, partner_id)
                except sqlite3.IntegrityError as exc:
                    _fehler_anzeigen(self, exc)
                    return
                self.aktualisieren()

    def _zwei_markierte_tauschen(self, id_a: int, id_b: int) -> None:
        """UX-Nachtest 03.10.2026, N2: beide Personas markierten zum Tauschen zuerst beide
        Teilnehmer - das tauscht jetzt direkt (nach Rückfrage)."""
        a, b = get_teilnehmer(self.conn, id_a), get_teilnehmer(self.conn, id_b)
        if a is None or b is None:
            self.aktualisieren()
            return
        if a["startnummer"] is None and b["startnummer"] is None:
            QMessageBox.information(
                self, "Nichts zu tauschen",
                "Beide Teilnehmer haben noch keine Startnummer. Startnummern vergibst du "
                "mit „Fehlende Startnummern vergeben…“ oder über „Bearbeiten…“.",
            )
            return

        def beschreibung(t):
            nummer = f"Nr. {t['startnummer']}" if t["startnummer"] is not None else "ohne Nummer"
            return f"„{t['nachname']}, {t['vorname']}“ ({nummer})"

        antwort = QMessageBox.question(
            self, "Startnummern tauschen",
            f"Startnummern von {beschreibung(a)} und {beschreibung(b)} tauschen?",
        )
        if antwort != QMessageBox.Yes:
            return
        try:
            tausche_startnummern(self.conn, id_a, id_b)
        except sqlite3.IntegrityError as exc:
            _fehler_anzeigen(self, exc)
            return
        self.aktualisieren()

    def _fehlende_startnummern_vergeben(self) -> None:
        _fehlende_startnummern_vergeben_mit_meldung(self, self.conn)
        self.aktualisieren()

    def _teilnehmerliste_importieren(self) -> None:
        _teilnehmerliste_importieren(self, self.conn)
        self.aktualisieren()

    def _aus_anderem_termin_importieren(self) -> None:
        dialog = TerminImportDialog(self, self._pfad)
        try:
            if dialog.exec() == QDialog.Accepted:
                quelle = dialog.quelle_conn()
                ausgewaehlt = dialog.ausgewaehlte_ids()
                if quelle is None:
                    # Praktisch nur erreichbar, wenn die gewählte Quell-Termin-Datei
                    # zwischenzeitlich nicht mehr geöffnet werden konnte - statt
                    # kommentarlos abzubrechen, den Nutzer darüber informieren.
                    QMessageBox.warning(
                        self, "Import nicht möglich",
                        "Die gewählte Quell-Termin-Datei konnte nicht geöffnet werden."
                    )
                elif ausgewaehlt:
                    anzahl = importiere_teilnehmer_stammdaten(quelle, self.conn, ausgewaehlt)
                    self.aktualisieren()
                    QMessageBox.information(
                        self, "Import abgeschlossen", f"{anzahl} Teilnehmer importiert."
                    )
                    if anzahl:
                        _startnummern_nach_import_anbieten(self, self.conn)
                        self.aktualisieren()
        finally:
            # Die zweite, nur für den Import geöffnete Verbindung muss in jedem Fall
            # geschlossen werden - unabhängig davon, ob der Dialog akzeptiert oder
            # abgebrochen wurde.
            dialog.schliesse_quelle()

    def _bewertungsbogen_exportieren(self) -> None:
        """Erzeugt den Bewertungsbogen für genau den ausgewählten Teilnehmer (Nutzerwunsch
        21.09., siehe bewertungsbogen_btn oben) - nutzt dieselbe Kernfunktion
        (pdf_export.erstelle_bewertungsbogen_pdf) wie der bisherige Weg über den Reiter
        "Export" (dort weiterhin als Sammel-Export für alle Teilnehmer vorhanden)."""
        teilnehmer_id = self._ausgewaehlte_id()
        if teilnehmer_id is None:
            return
        aktuell = next((t for t in self._teilnehmer_je_zeile if t["id"] == teilnehmer_id), None)
        if aktuell is None:
            return
        start_teil = str(aktuell["startnummer"]) if aktuell["startnummer"] is not None else "ohne-Nr"
        vorschlag = f"Bewertungsbogen_{start_teil}_{aktuell['nachname']}.pdf"
        pfad = _pdf_speicherort_waehlen(self, self._ablageort, "Bewertungsbogen speichern", vorschlag)
        if not pfad:
            return
        try:
            pdf_export.erstelle_bewertungsbogen_pdf(self.conn, teilnehmer_id, pfad)
        except Exception as exc:
            _pdf_export_fehler_anzeigen(self, exc)
            return
        self.status_label.setText(f"Bewertungsbogen gespeichert: {_pfad_anzeige(pfad)}")
        _datei_gespeichert_melden(self, pfad, "Bewertungsbogen gespeichert")

    def _teilnehmer_loeschen(self) -> None:
        # K7-Verifikation: Namen aus den IDs statt aus currentRow() - bei Mehrfachmarkierung
        # (Strg-Klick) kann die aktuelle Zeile eine andere sein als die markierte.
        # UX-Nachtest 03.10.2026, N1: alle markierten auf einmal, mit EINER Rückfrage.
        teilnehmer = [t for t in (self._teilnehmer_je_id.get(i) for i in self._ausgewaehlte_ids()) if t is not None]
        if not teilnehmer:
            return
        namen = [f"„{t['nachname']}, {t['vorname']}“" for t in teilnehmer]
        if len(namen) == 1:
            frage = f"Teilnehmer {namen[0]} inklusive erfasstem Ergebnis wirklich unwiderruflich löschen?"
        else:
            liste = "\n".join(namen[:15]) + (f"\n… und {len(namen) - 15} weitere" if len(namen) > 15 else "")
            frage = (
                f"Diese {len(namen)} Teilnehmer inklusive erfasster Ergebnisse wirklich "
                f"unwiderruflich löschen?\n\n{liste}"
            )
        antwort = QMessageBox.question(self, "Teilnehmer löschen", frage)
        if antwort == QMessageBox.Yes:
            for t in teilnehmer:
                delete_teilnehmer(self.conn, t["id"])
            self.aktualisieren()

    def _bezahlt_umschalten(self) -> None:
        ids = set(self._ausgewaehlte_ids())
        aktuelle = [t for t in list_teilnehmer(self.conn) if t["id"] in ids]
        if not aktuelle:
            self.aktualisieren()
            return
        # K7: Bei Mehrfachmarkierung einheitlich - sind schon alle bezahlt, werden alle auf
        # "nicht bezahlt" gesetzt, sonst alle auf "bezahlt" (statt jede einzeln umzudrehen).
        neu_bezahlt = not all(t["bezahlt"] for t in aktuelle)
        try:
            for t in aktuelle:
                setze_bezahlt(self.conn, t["id"], neu_bezahlt)
        except sqlite3.IntegrityError as exc:
            _fehler_anzeigen(self, exc)
        self.aktualisieren()

    def _teilnahme_umschalten(self) -> None:
        aktuelle = [t for t in (get_teilnehmer(self.conn, i) for i in self._ausgewaehlte_ids()) if t is not None]
        if not aktuelle:  # zwischenzeitlich gelöscht - nur die Liste auffrischen
            self.aktualisieren()
            return
        # K7: wie _auswahl_geaendert - nur wenn alle markierten schon "keine Teilnahme"
        # sind, wird die Teilnahme wiederhergestellt, sonst werden alle markiert.
        neu_keine_teilnahme = not all(t.get("keine_teilnahme") for t in aktuelle)
        mit_ergebnissen = [
            f"{t['nachname']}, {t['vorname']}" for t in aktuelle
            if neu_keine_teilnahme and not t.get("keine_teilnahme") and hat_erfasste_ergebnisse(self.conn, t["id"])
        ]
        if mit_ergebnissen:
            if len(mit_ergebnissen) == 1:
                wer = f"Für „{mit_ergebnissen[0]}“ sind"
                subjekt = "der Teilnehmer"
            else:
                wer = "Für " + ", ".join(f"„{n}“" for n in mit_ergebnissen) + " sind"
                subjekt = "die Teilnehmer"
            antwort = QMessageBox.question(
                self,
                "Keine Teilnahme",
                f"{wer} bereits Ergebnisse erfasst. Sie bleiben gespeichert, "
                f"werden aber nicht mehr gewertet, solange {subjekt} als "
                "„keine Teilnahme“ markiert ist.\n\nTrotzdem markieren?",
            )
            if antwort != QMessageBox.Yes:
                return
        try:
            for t in aktuelle:
                setze_keine_teilnahme(self.conn, t["id"], neu_keine_teilnahme)
        except sqlite3.IntegrityError as exc:
            _fehler_anzeigen(self, exc)
        self.aktualisieren()

    def aktualisieren(self) -> None:
        gemerkte_auswahl = set(self._ausgewaehlte_ids())
        self.tabelle.clearSelection()
        teilnehmer = list_teilnehmer(self.conn)
        self._teilnehmer_ids = [t["id"] for t in teilnehmer]
        self._teilnehmer_je_zeile = teilnehmer
        # Für _filter_anwenden(): Zuordnung Teilnehmer-ID -> Datensatz, damit der Filter
        # über die tatsächliche (ggf. sortierte) Zeilenreihenfolge der Tabelle arbeiten
        # kann statt über die Listenreihenfolge aus der Datenbank (siehe _sortierung_gemerkt).
        self._teilnehmer_je_id = {t["id"]: t for t in teilnehmer}
        # Während der Neubefüllung die automatische Sortierung abschalten - sonst sortiert
        # Qt nach jedem einzelnen setItem() neu und die spaltenweise befüllten Zellen einer
        # Zeile landen versehentlich in unterschiedlichen (durcheinandergewürfelten) Zeilen.
        self.tabelle.setSortingEnabled(False)
        self.tabelle.setRowCount(len(teilnehmer))
        for row, t in enumerate(teilnehmer):
            werte = [
                str(t["startnummer"] or ""),
                t["nachname"],
                t["vorname"],
                t["rufname_hund"],
                leistungsklasse_label(t),
                t["verein"] or "",
                "✓ bezahlt" if t["bezahlt"] else "",
            ]
            for col, wert in enumerate(werte):
                if col == 0:
                    # Start-Nr.-Spalte: Sortierung soll numerisch erfolgen (2 vor 10), nicht
                    # alphabetisch wie bei reinem Text ("10" vor "2") - siehe
                    # _NumerischSortierbaresItem. Fehlende Startnummer (None) sortiert mit
                    # -1 vor allen echten (>=1) Startnummern, analog zum bisherigen
                    # NULL-zuerst-Verhalten von list_teilnehmer()s "ORDER BY startnummer".
                    item = _NumerischSortierbaresItem(
                        wert, t["startnummer"] if t["startnummer"] is not None else -1
                    )
                    # Stabile Zuordnung Tabellenzeile -> Teilnehmer-ID (siehe _ausgewaehlte_id/
                    # _filter_anwenden) - unverzichtbar, sobald per Spaltenklick sortiert wird
                    # und die Zeilenreihenfolge nicht mehr der Listenreihenfolge entspricht.
                    item.setData(Qt.UserRole, t["id"])
                else:
                    item = QTableWidgetItem(wert)
                self.tabelle.setItem(row, col, item)
            # Bezahlt-Spalte farblich hervorheben (dezentes Grün, siehe _QSS_TEMPLATE) -
            # nur die Textfarbe, der Zelleninhalt selbst bleibt wie zuvor ("" bei nicht
            # bezahlt), damit bestehende Tests darauf weiter verlassen können.
            if t["bezahlt"]:
                bezahlt_item = self.tabelle.item(row, 6)
                bezahlt_item.setForeground(_farbe("ok"))
                schrift = bezahlt_item.font()
                schrift.setBold(True)
                bezahlt_item.setFont(schrift)
            # Nutzerwunsch (20.09.): Warnhinweis, wenn Chip-Nr. oder die zur Leistungsklasse
            # passende Gegenstand-Zuordnung fehlt ("Kontrollbutton") - bewusst nur bei
            # fehlenden Angaben ein Hinweis, sonst bleibt die Zelle leer (die Ausnahme soll
            # auffallen, nicht der Normalfall). Rückmeldung (22.09.): der Fehler
            # "Gegenstände unvollständig" soll nur noch erscheinen, wenn ein
            # Gegenstand-Text tatsächlich fehlt - steht er auf "gesucht in: frei", ist das
            # kein Fehler mehr, sondern nur eine mildere Info (kleinere, nicht fette
            # Schrift statt orange/fett, damit sie sich klar vom echten Warnhinweis
            # unterscheidet und trotz Spaltenbreite lesbar bleibt). Ein echter Fehler hat
            # Vorrang vor der Info (siehe teilnehmer_gegenstand_hinweis()).
            # UX-Test 02.10.2026, U14 (Marco: nur die Chip-Nr. auffällig): Gegenstände
            # werden oft erst kurz vor dem Prüfungstag festgelegt - ein oranges ⚠ in fast
            # jeder Zeile wirkte auf Laien, als sei alles falsch. Sie erscheinen jetzt dezent
            # grau als "noch offen"; nur eine fehlende Chip-Nr. bleibt eine Warnung. Bei
            # "keine Teilnahme" entfallen die Gegenstands-Hinweise ganz (K7).
            fehlend = teilnehmer_fehlende_pflichtangaben(t)
            stark = [f for f in fehlend if f.startswith("Chip")]
            gegenstand_offen = [f for f in fehlend if not f.startswith("Chip")] and not t.get("keine_teilnahme")
            offen_text = "Gegenstände noch offen" if t["art"] == "DK" else "Gegenstand noch offen"
            offen_tooltip = (
                f"{offen_text} – kann bis zum Prüfungstag nachgetragen werden (Bearbeiten…)."
            )
            if stark:
                text = "⚠ " + "; ".join(stark) + (f"; {offen_text}" if gegenstand_offen else "")
                vollstaendig_item = QTableWidgetItem(text)
                vollstaendig_item.setForeground(_farbe("warnung"))
                vollstaendig_item.setToolTip(
                    "Fehlt noch: Chip-Nr. (wird am Prüfungstag zur Identifizierung gebraucht)."
                    + (f"\n{offen_tooltip}" if gegenstand_offen else "")
                )
                schrift = vollstaendig_item.font()
                schrift.setBold(True)
                vollstaendig_item.setFont(schrift)
            elif gegenstand_offen:
                vollstaendig_item = QTableWidgetItem(offen_text)
                vollstaendig_item.setForeground(_farbe("gedaempft"))
                vollstaendig_item.setToolTip(offen_tooltip)
            else:
                hinweis = teilnehmer_gegenstand_hinweis(t)
                vollstaendig_item = QTableWidgetItem(hinweis or "")
                if hinweis:
                    vollstaendig_item.setToolTip(hinweis)
                    schrift = vollstaendig_item.font()
                    schrift.setPointSize(max(schrift.pointSize() - 1, 1))
                    vollstaendig_item.setFont(schrift)
            self.tabelle.setItem(row, 7, vollstaendig_item)
            if t.get("keine_teilnahme"):
                # Nutzerwunsch (02.10.2026): nicht erschienene Teilnehmer ausgegraut und mit
                # Vermerk - überschreibt bewusst die Bezahlt-/Warnfarben dieser Zeile.
                vollstaendig_item.setText(
                    "keine Teilnahme" + (f"; {vollstaendig_item.text()}" if vollstaendig_item.text() else "")
                )
                for col in range(self.tabelle.columnCount()):
                    zelle = self.tabelle.item(row, col)
                    if zelle is not None:
                        zelle.setForeground(_farbe("gedaempft"))
                        schrift = zelle.font()
                        schrift.setItalic(True)
                        zelle.setFont(schrift)
        # Zuletzt per Spaltenklick gewählte Sortierung erneut anwenden (statt nach jeder
        # Änderung - Speichern, Bezahlt umschalten, ... - stillschweigend auf die
        # Standard-Sortierung nach Start-Nr. zurückzuspringen), bevor die interaktive
        # Sortierung wieder aktiviert wird.
        self.tabelle.sortItems(self._sortierspalte, self._sortierreihenfolge)
        self.tabelle.setSortingEnabled(True)
        # Spaltenbreiten an den tatsächlichen Inhalt anpassen, damit z.B. lange
        # Vereinsnamen oder LK-Bezeichnungen nicht abgeschnitten werden - danach
        # bleiben die Spalten weiterhin von Hand nachziehbar.
        self.tabelle.resizeColumnsToContents()
        self._auswahl_wiederherstellen(gemerkte_auswahl)
        self._auswahl_geaendert()

        # Filter-Auswahl beim Neuladen nach Möglichkeit beibehalten, statt immer auf
        # "Alle" zurückzuspringen (entspricht ErgebnisTab.aktualisieren).
        bisherige_auswahl = self.filter_combo.currentText()
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItem("Alle")
        # Bewusst aus der eigenen (ungefilterten) Liste statt alle_leistungsklassen(), das
        # nur teilnehmende Teilnehmer berücksichtigt - hier sollen auch Leistungsklassen
        # filterbar bleiben, in denen nur noch "keine Teilnahme"-Teilnehmer stehen.
        self.filter_combo.addItems(sorted({leistungsklasse_label(t) for t in teilnehmer}))
        index = self.filter_combo.findText(bisherige_auswahl)
        self.filter_combo.setCurrentIndex(index if index >= 0 else 0)
        self.filter_combo.blockSignals(False)
        self._filter_anwenden()


def _formular_import_prompt() -> str:
    """Baut den Kopier-Prompt für den Reiter 'Formular-Import' (siehe FormularImportTab)
    aus CSV_IMPORT_SPALTEN (db_import.py) - so können Prompt-Text und CSV-Parser
    (importiere_teilnehmer_aus_csv) nie auseinanderlaufen. Gedacht für ein beliebiges
    externes KI-System (z.B. Claude oder ChatGPT), dem der Nutzer diesen Text zusammen
    mit einem ausgefüllten Meldeformular übergibt - die Desktop-Anwendung selbst hat
    keinen eigenen KI-Zugriff (arbeitet komplett offline), siehe Fortschritt.md."""
    spalten = ", ".join(CSV_IMPORT_SPALTEN)
    return (
        "Du bekommst ein oder mehrere ausgefüllte SHS-Meldeformulare (als PDF, Word-"
        "Dokument oder Foto/Scan). Lies je Formular GENAU EINEN Teilnehmer heraus und gib "
        "das Ergebnis als CSV-Datei mit exakt dieser Kopfzeile aus (Komma-getrennt, "
        "UTF-8, Werte ggf. in Anführungszeichen falls sie ein Komma enthalten):\n\n"
        f"{spalten}\n\n"
        "Regeln:\n"
        "- Pro Formular genau eine Datenzeile. Mehrere Formulare ergeben mehrere Zeilen "
        "untereinander in derselben CSV.\n"
        "- nachname, vorname und rufname_hund sind Pflicht (rufname_hund = 'Rufname des "
        "Hundes' auf dem Formular). Ein Formular ohne diese Angaben bitte auslassen.\n"
        "- art/stufe/disziplin ergeben sich aus dem angekreuzten Kästchen oben auf dem "
        "Formular: 'DK-LK 1/2/3' -> art=DK, stufe=1/2/3, disziplin LEER lassen. "
        "'Trümmer LK n' -> art=ED, stufe=n, disziplin=Trümmerfeld. "
        "'Fläche LK n' -> art=ED, stufe=n, disziplin=Flächensuche. "
        "'Behältnisse LK n' -> art=ED, stufe=n, disziplin=Behältnisstrecke.\n"
        "- verein = Mitgliedsverein des Teilnehmers, verband = übergeordneter Verband "
        "(z.B. VDH), mitgliedsnummer = Mitgl.-Nr., wurftag = Wurfdatum des Hundes "
        "(JJJJ-MM-TT), tollwutimpfung_bis = 'Tollwutimpfung gültig bis' (JJJJ-MM-TT), "
        "geburtsdatum = Geburtsdatum des Hundeführers/der Hundeführerin, falls auf dem "
        "Formular angegeben (JJJJ-MM-TT), "
        "schulterhoehe_cm = Größe in cm (nur die Zahl), geschlecht = 'Hündin' oder "
        "'Rüde'.\n"
        "- Die halter_*-Spalten NUR befüllen, wenn das Formular den Abschnitt 'Falls "
        "abweichend von Teilnehmer - Angaben des Hundeeigentümers' ausgefüllt hat - sonst "
        "ALLE halter_*-Spalten in dieser Zeile leer lassen (halter_mitgliedsverein = "
        "'Mitgliedsverein' und halter_mitgliedsnummer = 'Mitgl.-Nr.' im Halter-"
        "Abschnitt).\n"
        "- Ein Feld ohne erkennbare Angabe auf dem Formular bleibt in der CSV leer - "
        "nicht raten oder freilassen mit einem Platzhalter wie 'unbekannt' füllen.\n"
        "- startnummer, gegenstand_1/2/3, gegenstand_1/2/3_disziplin und bezahlt stehen "
        "NICHT auf dem Meldeformular - diese Spalten entweder ganz weglassen oder leer "
        "lassen, sie werden im Programm separat vergeben.\n\n"
        "Gib NUR die CSV-Datei aus, ohne einleitenden oder abschließenden Text drumherum."
    )


class FormularImportTab(QWidget):
    """Hilft dabei, Teilnehmer aus einem ausgefüllten Meldeformular zu übernehmen, ohne
    die Angaben von Hand abtippen zu müssen (Nutzerwunsch 20.09., Anmerkung zum Programm,
    Abschnitt 'Teilnehmer'): ein vorformulierter Prompt (siehe _formular_import_prompt())
    lässt sich zusammen mit einem ausgefüllten Meldeformular an ein beliebiges externes
    KI-System übergeben, das daraus eine CSV-Datei mit den hier erwarteten Spalten
    erzeugt - diese CSV lässt sich anschließend direkt importieren. Läuft bewusst über
    einen Kopier-Prompt statt einer eingebauten KI-Anbindung, da die Desktop-Anwendung
    offline arbeitet und keinen eigenen KI-Zugriff hat.
    Nutzerwunsch 28.09.2026: Das vom Programm erzeugte, ausfüllbare Anmeldeformular (Reiter
    "Export") lässt sich ausgefüllt direkt einlesen - ganz ohne KI (siehe
    _anmeldeformulare_importieren)."""

    _KI_UMSCHALTER_TEXT = "Andere Meldeformulare (Foto, Scan, Word) über ein KI-System einlesen"

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn

        # UX-Test 02.10.2026, U10: drei Wege als eigene, kurz erklärte Abschnitte statt eines
        # langen Textes über einem dominanten KI-Prompt; der KI-Weg ist eingeklappt.
        def abschnitt(titel: str, erklaerung: str, *knoepfe: QPushButton) -> QGroupBox:
            box = QGroupBox(titel)
            text = QLabel(erklaerung)
            text.setWordWrap(True)
            zeile = QHBoxLayout()
            for knopf in knoepfe:
                zeile.addWidget(knopf)
            zeile.addStretch()
            inhalt = QVBoxLayout(box)
            inhalt.addWidget(text)
            inhalt.addLayout(zeile)
            return box

        anmeldeformular_btn = QPushButton("Anmeldeformulare (PDF) importieren…")
        anmeldeformular_btn.setObjectName("primaerButton")
        anmeldeformular_btn.clicked.connect(self._anmeldeformulare_importieren)

        import_btn = QPushButton("Teilnehmerliste einlesen (Excel/CSV)…")
        import_btn.clicked.connect(self._csv_importieren)
        vorlage_btn = QPushButton("Leere Vorlage (CSV) speichern…")
        vorlage_btn.clicked.connect(self._vorlage_speichern)

        oma_btn = QPushButton("OMA-Export importieren…")
        oma_btn.clicked.connect(self._oma_importieren)

        self.prompt_feld = QPlainTextEdit(_formular_import_prompt())
        self.prompt_feld.setReadOnly(True)
        self.prompt_feld.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        kopieren_btn = QPushButton("Prompt kopieren")
        kopieren_btn.clicked.connect(self._prompt_kopieren)
        self.status_label = QLabel("")
        self.status_label.setTextFormat(Qt.PlainText)  # S-1: enthält Pfade/Namen

        ki_anleitung = QLabel(
            "1. „Prompt kopieren“ klicken und den Text zusammen mit dem ausgefüllten "
            "Meldeformular (PDF, Word-Dokument oder Foto/Scan) einem KI-System übergeben "
            "(z. B. Claude oder ChatGPT).\n"
            "2. Die dabei erzeugte CSV-Datei oben unter „Teilnehmerliste aus Excel“ mit "
            "„Teilnehmerliste einlesen (Excel/CSV)…“ einlesen.\n"
            "Datenschutz: Die Formulare gehen dabei an den gewählten KI-Anbieter."
        )
        ki_anleitung.setWordWrap(True)
        ki_knopfzeile = QHBoxLayout()
        ki_knopfzeile.addWidget(kopieren_btn)
        ki_knopfzeile.addWidget(self.status_label)
        ki_knopfzeile.addStretch()
        self._ki_bereich = QWidget()
        ki_layout = QVBoxLayout(self._ki_bereich)
        ki_layout.setContentsMargins(0, 0, 0, 0)
        ki_layout.addWidget(ki_anleitung)
        ki_layout.addWidget(self.prompt_feld)
        ki_layout.addLayout(ki_knopfzeile)
        self._ki_bereich.setVisible(False)
        self._ki_umschalter = QPushButton("▸ " + self._KI_UMSCHALTER_TEXT)
        self._ki_umschalter.setCheckable(True)
        self._ki_umschalter.setFlat(True)
        self._ki_umschalter.setStyleSheet("text-align: left;")
        self._ki_umschalter.toggled.connect(self._ki_bereich_umschalten)

        layout = QVBoxLayout(self)
        layout.addWidget(abschnitt(
            "1. Ausgefüllte Anmeldeformulare (PDF) – empfohlen",
            "Das Anmeldeformular erzeugst du im Reiter „Export“ und verschickst es an die "
            "Teilnehmer. Die ausgefüllt zurückgeschickten PDF-Dateien hier einlesen – mehrere "
            "auf einmal möglich, bereits vorhandene Meldungen werden übersprungen.",
            anmeldeformular_btn,
        ))
        layout.addWidget(abschnitt(
            "2. Teilnehmerliste aus Excel (CSV-Datei)",
            "Eine Liste mit einer Zeile je Teilnehmer, z. B. vom Schriftführer. Die leere "
            "Vorlage enthält die passenden Spaltenüberschriften: in Excel ausfüllen, als "
            "„CSV“ speichern und hier einlesen.",
            import_btn, vorlage_btn,
        ))
        layout.addWidget(abschnitt(
            "3. Meldungen aus der OMA (Online-Meldeannahme)",
            "Den Meldungs-Export der OMA direkt einlesen – bereits vorhandene Meldungen werden "
            "übersprungen.",
            oma_btn,
        ))
        layout.addWidget(self._ki_umschalter)
        layout.addWidget(self._ki_bereich, 1)
        layout.addStretch()

    def _prompt_kopieren(self) -> None:
        QApplication.clipboard().setText(self.prompt_feld.toPlainText())
        self.status_label.setText("Prompt kopiert.")

    def _csv_importieren(self) -> None:
        _teilnehmerliste_importieren(self, self.conn)

    def _vorlage_speichern(self) -> None:
        """UX-Test 02.10.2026, U10: leere Excel-Vorlage mit den passenden Spalten."""
        vorschlag = os.path.join(_import_startordner(), "Teilnehmerliste_Vorlage.csv")
        pfad, _ = QFileDialog.getSaveFileName(self, "Vorlage speichern", vorschlag, "CSV-Datei (*.csv)")
        if not pfad:
            return
        try:
            schreibe_csv_vorlage(pfad)
        except OSError as exc:
            QMessageBox.warning(self, "Speichern fehlgeschlagen", f"Die Vorlage konnte nicht gespeichert werden:\n{exc}")
            return
        _datei_gespeichert_melden(self, pfad, "Vorlage gespeichert", datei_oeffnen_text="Datei öffnen")

    def _ki_bereich_umschalten(self, sichtbar: bool) -> None:
        self._ki_bereich.setVisible(sichtbar)
        self._ki_umschalter.setText(("▾ " if sichtbar else "▸ ") + self._KI_UMSCHALTER_TEXT)

    def _oma_importieren(self) -> None:
        """Übernimmt Meldungen aus einem OMA-Export (siehe importiere_teilnehmer_aus_oma in
        db.py) - ohne Umweg über den KI-Prompt."""
        pfad, _ = QFileDialog.getOpenFileName(
            self, "OMA-Export importieren", _import_startordner(), "OMA-Export (*.csv *.txt);;Alle Dateien (*)"
        )
        if not pfad:
            return
        _import_ordner_merken(pfad)
        try:
            ergebnis = importiere_teilnehmer_aus_oma(self.conn, pfad)
        except OSError as exc:
            QMessageBox.warning(self, "Import fehlgeschlagen", f"Die Datei konnte nicht gelesen werden:\n{exc}")
            return
        text = f"{ergebnis.importiert} Teilnehmer importiert."
        if ergebnis.uebersprungen:
            text += (
                f"\n\n{len(ergebnis.uebersprungen)} Meldung(en) bereits vorhanden, nicht erneut angelegt:\n"
                + "\n".join(ergebnis.uebersprungen)
            )
        if ergebnis.fehler:
            text += f"\n\n{len(ergebnis.fehler)} Zeile(n) übersprungen:\n" + "\n".join(ergebnis.fehler)
        if ergebnis.hinweise:
            text += "\n\nHinweis: " + "\n".join(ergebnis.hinweise)
        QMessageBox.information(self, "Import abgeschlossen", text)
        if ergebnis.importiert:
            _startnummern_nach_import_anbieten(self, self.conn)

    def _anmeldeformulare_importieren(self) -> None:
        """Liest ausgefüllte Anmeldeformulare (siehe pdf_export.erstelle_anmeldeformular_pdf)
        über db_import.importiere_anmeldeformular_pdf ein - eine Datei je Meldung, mehrere
        Dateien auf einmal wählbar (Nutzerwunsch 28.09.2026)."""
        pfade, _ = QFileDialog.getOpenFileNames(
            self, "Anmeldeformulare importieren", _import_startordner(), "Anmeldeformular (*.pdf)"
        )
        if not pfade:
            return
        _import_ordner_merken(pfade[0])
        # Kein try/except nötig: der Import fängt Lesefehler je Datei selbst ab und meldet
        # sie in ergebnis.fehler (Verifikation 28.09.2026, Befund 7a).
        ergebnis = importiere_anmeldeformular_pdf(self.conn, pfade)
        text = f"{ergebnis.importiert} Teilnehmer importiert."
        if ergebnis.uebersprungen:
            text += (
                f"\n\n{len(ergebnis.uebersprungen)} Meldung(en) bereits vorhanden, nicht erneut angelegt:\n"
                + "\n".join(ergebnis.uebersprungen)
            )
        if ergebnis.fehler:
            text += f"\n\n{len(ergebnis.fehler)} Datei(en) nicht importiert:\n" + "\n".join(ergebnis.fehler)
        if ergebnis.hinweise:
            text += "\n\nHinweis:\n" + "\n".join(ergebnis.hinweise)
        QMessageBox.information(self, "Import abgeschlossen", text)
        if ergebnis.importiert:
            _startnummern_nach_import_anbieten(self, self.conn)


# Höchstpunktzahlen je Disziplin (entsprechen den CHECK-Constraints in db.py). UX-Test
# 02.10.2026, U5: das Punktefeld ließ "65" als Zwischenstand beim Tippen zu - solche
# Werte werden deshalb sofort rot markiert und beim Speichern im Klartext abgelehnt, statt
# erst an der Datenbank mit "CHECK constraint failed" zu scheitern.
_SUCHE_MAX = SUCHE_MAX  # gemeinsame Konstanten aus shs_core (auch für die Web-Version)
_ANZEIGE_MAX = ANZEIGE_MAX


def _punkte_validator(parent) -> QRegularExpressionValidator:
    """Nur Ziffern (höchstens zwei) - unabhängig von der Spracheinstellung des Systems. Der
    QIntValidator nahm in englischer/Linux-Einstellung "," als Tausender-Trennzeichen an
    ("45," statt Hinweis; CI-Befund 03.10.2026). Werte über dem Maximum markiert
    _aktualisiere_zeilenstatus rot, das Speichern lehnt sie im Klartext ab (U5)."""
    return QRegularExpressionValidator(QRegularExpression(r"\d{0,2}"), parent)


class ErgebnisTab(QWidget):
    """Eine Zeile je Teilnehmer. Bei DK werden alle drei Disziplinen nebeneinander in
    derselben Zeile erfasst statt in drei getrennten Zeilen. Änderungen werden nicht
    mehr sofort pro Zeile gespeichert, sondern gesammelt über einen einzigen
    "Alle Ergebnisse speichern"-Button - noch nicht gespeicherte Zeilen werden dabei
    gelb hervorgehoben und im Status deutlich gekennzeichnet."""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        # Pro Tabellenzeile: Teilnehmer-Stammdaten, die aktiven Eingabefelder je Disziplin
        # und die zuletzt aus der DB geladenen (= gespeicherten) Werte je Disziplin -
        # der Vergleich der beiden liefert den "ungespeichert"-Status. Ein leeres Feld
        # bedeutet "noch nicht eingetragen" (None) - kein Platzhalterwert wie zuvor "-1",
        # damit die Felder ohne Vorbelegung wirklich leer erscheinen.
        self._teilnehmer_je_zeile: list[dict] = []
        self._boxen_je_zeile: list[dict[str, tuple[QLineEdit, QLineEdit]]] = []
        self._geladen_je_zeile: list[dict[str, tuple[int | None, int | None]]] = []
        # Nutzerwunsch (21.09.): analog zu den Punkte-Eingabefeldern oben, aber für die
        # beiden Status-Checkboxen "Disqualifiziert"/"Abbruch" je Zeile.
        self._status_boxen_je_zeile: list[tuple[QCheckBox, QCheckBox]] = []
        self._status_geladen_je_zeile: list[tuple[bool, bool]] = []

        spalten = ["Start-Nr.", "Name", "Hund", "Art/LK"]
        for disziplin in ALLE_DISZIPLINEN:
            spalten += [f"{disziplin}\nSuche (0-{_SUCHE_MAX})", f"{disziplin}\nAnzeige (0-{_ANZEIGE_MAX})"]
        spalten += ["Disqualifiziert", "Abbruch", "Status"]

        self.tabelle = QTableWidget(0, len(spalten))
        self.tabelle.setHorizontalHeaderLabels(spalten)
        self.tabelle.horizontalHeader().setStretchLastSection(True)
        # Nutzerwunsch (22.09.): Spaltenüberschriften sollen bei schmalen Spalten nicht
        # abgeschnitten werden. Qt rendert einen "\n" in einem Header-Label von sich aus
        # bereits mehrzeilig (sizeHint/Höhe passen sich automatisch an - kein QHeaderView-
        # API-Aufruf nötig, es gibt dort anders als bei QAbstractItemView kein setWordWrap()).
        # Die Disziplin-Header oben nutzen deshalb "\n" statt " – " als Trenner; die
        # Mindestspaltenbreite unten in _spaltenbreiten_anpassen orientiert sich entsprechend
        # an der jeweils breitesten Headerzeile statt an festen Platzhaltern.
        # Die von Qt automatisch links angezeigte Zeilennummerierung (1, 2, 3, ...) ist
        # keine echte, überschriebene Spalte und trägt keine zusätzliche Information (die
        # Start-Nr. steht bereits in der ersten echten Spalte) - deshalb ausgeblendet,
        # ebenso im Reiter "Teilnehmer" (siehe TeilnehmerTab).
        self.tabelle.verticalHeader().setVisible(False)
        # Nutzerwunsch (21.09., Rückmeldung zur Ergebniserfassung): "klappt gut, ggf. hier
        # auch Sortierungsfunktion" - Klick auf eine Spaltenüberschrift sortiert danach,
        # erneuter Klick auf dieselbe Spalte kehrt die Richtung um (wie in der
        # Teilnehmerliste, siehe TeilnehmerTab). WICHTIG: hier bewusst NICHT
        # setSortingEnabled(True)/sortIndicatorChanged wie dort, weil diese Tabelle die
        # Punkte-Eingabefelder über setCellWidget setzt (echte QLineEdit-Widgets) - Qts
        # eigene sortItems()-Sortierung verschiebt nur QTableWidgetItems, NICHT per
        # setCellWidget gesetzte Widgets, und würde die Eingabefelder von den falschen
        # Zeilen trennen. Stattdessen eine eigene Sortierlogik (siehe _spalte_geklickt/
        # _sortieren_und_neu_aufbauen), die vor dem Neuaufbau zuerst die aktuellen
        # (ggf. noch nicht gespeicherten) Werte je Teilnehmer-ID sichert.
        self.tabelle.horizontalHeader().sectionClicked.connect(self._spalte_geklickt)
        self._sortierspalte: int | None = None
        self._sortieraufsteigend = True

        self.filter_combo = QComboBox()
        # Passt die Breite der Box an den längsten enthaltenen Eintrag an (z.B. lange
        # Art/LK-Bezeichnungen wie "ED LK 3 Behältnisstrecke"), statt Text abzuschneiden.
        self.filter_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.filter_combo.currentTextChanged.connect(self._filter_anwenden)

        self.filter_startnummer = QLineEdit()
        self.filter_startnummer.setPlaceholderText("z.B. 13")
        self.filter_startnummer.setMaximumWidth(80)
        self.filter_startnummer.textChanged.connect(self._filter_anwenden)

        self.speichern_btn = speichern_btn = QPushButton("Alle Ergebnisse speichern")  # Attribut für die Demoprüfung
        speichern_btn.setObjectName("primaerButton")  # Haupt-Aktion dieses Reiters, siehe _QSS_TEMPLATE
        speichern_btn.clicked.connect(self.alle_speichern)
        # UX-Test 02.10.2026, K11: Strg+S speichert wie der Button - nur solange der Fokus
        # in diesem Reiter liegt (z. B. in einem Punktefeld). Über ein Lambda verbunden,
        # damit Tests alle_speichern() per monkeypatch ersetzen können.
        speichern_btn.setToolTip("Tastenkürzel: Strg+S")
        speichern_kuerzel = QShortcut(QKeySequence.Save, self)
        speichern_kuerzel.setContext(Qt.WidgetWithChildrenShortcut)
        speichern_kuerzel.activated.connect(lambda: self.alle_speichern())

        aktualisieren_btn = QPushButton("Liste aktualisieren")
        aktualisieren_btn.clicked.connect(self._aktualisieren_mit_rueckfrage)

        self.status_label = QLabel("")
        self.status_label.setTextFormat(Qt.PlainText)  # S-1: enthält Pfade/Namen

        filter_zeile = QHBoxLayout()
        filter_zeile.addWidget(QLabel("Filter Art/LK:"))
        filter_zeile.addWidget(self.filter_combo)
        filter_zeile.addSpacing(16)
        filter_zeile.addWidget(QLabel("Filter Start-Nr.:"))
        filter_zeile.addWidget(self.filter_startnummer)
        filter_zeile.addStretch()

        hinweis = QLabel(
            "Gelb hervorgehobene Zeilen enthalten noch nicht gespeicherte Änderungen. "
            "Der Filter blendet Zeilen nur aus, ungespeicherte Werte bleiben dabei erhalten."
        )
        hinweis.setWordWrap(True)

        button_zeile = QHBoxLayout()
        button_zeile.addWidget(speichern_btn)
        button_zeile.addWidget(aktualisieren_btn)
        button_zeile.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(filter_zeile)
        layout.addWidget(hinweis)
        layout.addWidget(self.tabelle)
        layout.addLayout(button_zeile)
        layout.addWidget(self.status_label)

        self.aktualisieren()

    def hat_ungespeicherte_aenderungen(self) -> bool:
        """True, wenn mindestens eine Zeile von den zuletzt geladenen/gespeicherten
        Werten abweicht - z.B. um beim Tabwechsel vor Datenverlust zu warnen."""
        for row in range(len(self._teilnehmer_je_zeile)):
            if self._zeile_ist_ungespeichert(row):
                return True
        return False

    def eingabefelder(self, teilnehmer_id: int):
        """(Zeile, Punktefelder je Disziplin, (Disqualifiziert-, Abbruch-Checkbox)) eines
        Teilnehmers oder None - für die Demoprüfung (desktop_demo), die die Felder sichtbar
        ausfüllt. Scrollt die Zeile dabei in den sichtbaren Bereich."""
        for row, t in enumerate(self._teilnehmer_je_zeile):
            if t["id"] == teilnehmer_id:
                self.tabelle.scrollTo(self.tabelle.model().index(row, 0))
                return row, self._boxen_je_zeile[row], self._status_boxen_je_zeile[row]
        return None

    def aktualisieren(self) -> None:
        """Baut die Tabelle komplett neu aus der Datenbank auf (verwirft dabei nicht
        gespeicherte Änderungen!) und aktualisiert den Filter. Wird beim ersten Öffnen
        sowie über "Liste aktualisieren" aufgerufen. Die zuletzt per Spaltenklick
        gewählte Sortierung bleibt dabei erhalten (siehe _zeilen_aufbauen)."""
        self._neu_laden()

    def _neu_laden(self, werte_override: dict | None = None, status_override: dict | None = None) -> None:
        """Gemeinsamer Kern von aktualisieren() (ohne Overrides) und
        aktualisieren_eingaben_erhalten() (mit den noch ungespeicherten Eingaben)."""
        self._teilnehmer_je_zeile = list_teilnehmer(self.conn, nur_teilnehmende=True)
        verworfen = self._zeilen_aufbauen(werte_override, status_override)
        # Codeprüfung 22.09., G9: list_teilnehmer() liefert immer die DB-Reihenfolge -
        # ohne erneutes Anwenden ging die per Spaltenklick gewählte Sortierung hier
        # verloren, während _sortierspalte/_sortieraufsteigend stehen blieben, sodass der
        # nächste Klick auf dieselbe Spalte die Richtung "umkehrte", obwohl die Tabelle gar
        # nicht (mehr) danach sortiert war. Erst nach dem Aufbau sortieren, weil einige
        # Sortierschlüssel (Punkte, DQ/Abbruch, Status) aus den Zeilen-Widgets gelesen
        # werden; die Werte stammen hier frisch aus der DB (bzw. aus den Overrides), es geht
        # also nichts verloren.
        if self._sortierspalte is not None:
            verworfen += self._sortieren_und_neu_aufbauen()

        # Filter-Auswahl beim Neuladen nach Möglichkeit beibehalten, statt immer auf
        # "Alle" zurückzuspringen.
        bisherige_auswahl = self.filter_combo.currentText()
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItem("Alle")
        self.filter_combo.addItems(alle_leistungsklassen(self.conn))
        index = self.filter_combo.findText(bisherige_auswahl)
        self.filter_combo.setCurrentIndex(index if index >= 0 else 0)
        self.filter_combo.blockSignals(False)

        self.status_label.setText("")
        self._filter_anwenden()
        self._verworfene_melden(verworfen)

    def _zeilen_aufbauen(
        self,
        werte_override: dict[int, dict[str, tuple[int | None, int | None]]] | None = None,
        status_override: dict[int, tuple[bool, bool]] | None = None,
    ) -> list[str]:
        """Baut die Tabellenzeilen aus `self._teilnehmer_je_zeile` (in dessen aktueller
        Reihenfolge) komplett neu auf - gemeinsam genutzt von _neu_laden() (also
        aktualisieren() ohne Overrides und aktualisieren_eingaben_erhalten()) und
        _sortieren_und_neu_aufbauen(). Overrides sind nur die echten, noch nicht
        gespeicherten Abweichungen je Teilnehmer-ID (siehe _eingaben_je_id); alles andere
        kommt frisch aus der DB. `werte_override`/`status_override` überschreiben dabei nur die ANGEZEIGTEN
        Werte - `_geladen_je_zeile`/`_status_geladen_je_zeile` bleiben trotzdem auf dem
        zuletzt aus der DB gelesenen (= gespeicherten) Stand, damit der
        "ungespeichert"-Vergleich (siehe _zeile_ist_ungespeichert) korrekt bleibt.

        Rückgabe: Teilnehmer, deren ungespeicherte Punkte verworfen wurden, weil inzwischen
        Disqualifiziert/Abbruch gespeichert ist (für _verworfene_melden)."""
        verworfen: list[str] = []
        ergebnis_rows = ergebnisse_je_teilnehmer(self.conn)
        werte_override = werte_override or {}
        status_override = status_override or {}

        self._boxen_je_zeile = []
        self._geladen_je_zeile = []
        self._status_boxen_je_zeile = []
        self._status_geladen_je_zeile = []

        self.tabelle.setRowCount(len(self._teilnehmer_je_zeile))
        for row, t in enumerate(self._teilnehmer_je_zeile):
            # .get() statt [] - dieselbe Absicherung wie in db.berechne_auswertung() (dort
            # als "Fix 10" dokumentiert): sollte die Teilnehmer/Ergebnisse-1:1-Invariante
            # doch einmal verletzt sein, führt das nur zu leeren Punktefeldern statt zu
            # einem Absturz des gesamten Tabs.
            aktuell = ergebnis_rows.get(t["id"], {})
            zutreffende_disziplinen = ALLE_DISZIPLINEN if t["art"] == "DK" else [t["disziplin"]]
            punkte_override = werte_override.get(t["id"], {})

            self.tabelle.setItem(row, 0, QTableWidgetItem(str(t["startnummer"] or "")))
            self.tabelle.setItem(row, 1, QTableWidgetItem(f"{t['nachname']}, {t['vorname']}"))
            self.tabelle.setItem(row, 2, QTableWidgetItem(t["rufname_hund"]))
            self.tabelle.setItem(row, 3, QTableWidgetItem(leistungsklasse_label(t)))

            boxen: dict[str, tuple[QLineEdit, QLineEdit]] = {}
            geladen: dict[str, tuple[int | None, int | None]] = {}
            for disziplin in ALLE_DISZIPLINEN:
                spalte_suche, spalte_anzeige = _ERGEBNIS_SPALTEN_JE_DISZIPLIN[disziplin]
                if disziplin not in zutreffende_disziplinen:
                    # Disziplin gilt für diesen Teilnehmer nicht (ED) - Zellen leer/gesperrt lassen.
                    # Rückmeldung 23.09.: setItem()/setRowCount() entfernen kein Cell-Widget
                    # eines früheren Aufbaus - nach einer Umstellung DK -> ED (oder wenn beim
                    # Sortieren eine ED-Zeile auf die Position einer DK-Zeile rutscht) blieb
                    # sonst das alte Punkte-Eingabefeld über dem "–" stehen und beschreibbar.
                    for spalte in (spalte_suche, spalte_anzeige):
                        self.tabelle.removeCellWidget(row, spalte)
                        leer = QTableWidgetItem("–")
                        leer.setFlags(leer.flags() & ~Qt.ItemIsEditable)
                        leer.setForeground(_farbe("gedaempft"))
                        self.tabelle.setItem(row, spalte, leer)
                    continue

                db_spalte_suche, db_spalte_anzeige = DISZIPLIN_SPALTEN[disziplin]
                suche_wert = aktuell.get(db_spalte_suche)
                anzeige_wert = aktuell.get(db_spalte_anzeige)
                angezeigt_suche, angezeigt_anzeige = punkte_override.get(
                    disziplin, (suche_wert, anzeige_wert)
                )

                # Leeres Feld = "noch nicht eingetragen" - ohne jede Vorbelegung (weder
                # "0" noch ein Platzhalterzeichen), damit ein versehentlich stehen
                # gelassenes Feld nicht als echte 0-Punkte-Bewertung gespeichert wird.
                suche_feld = QLineEdit()
                suche_feld.setValidator(_punkte_validator(suche_feld))
                suche_feld.setAlignment(Qt.AlignCenter)
                if angezeigt_suche is not None:
                    suche_feld.setText(str(angezeigt_suche))
                self.tabelle.setCellWidget(row, spalte_suche, suche_feld)

                anzeige_feld = QLineEdit()
                anzeige_feld.setValidator(_punkte_validator(anzeige_feld))
                anzeige_feld.setAlignment(Qt.AlignCenter)
                if angezeigt_anzeige is not None:
                    anzeige_feld.setText(str(angezeigt_anzeige))
                self.tabelle.setCellWidget(row, spalte_anzeige, anzeige_feld)

                suche_feld.textChanged.connect(lambda _text, r=row: self._aktualisiere_zeilenstatus(r))
                anzeige_feld.textChanged.connect(lambda _text, r=row: self._aktualisiere_zeilenstatus(r))
                # Abgelehnte Zeichen (z. B. das Komma in "45,5") nicht stillschweigend
                # schlucken, sondern einen Hinweis zeigen (UX-Test 02.10.2026, U5).
                suche_feld.inputRejected.connect(
                    lambda f=suche_feld: self._eingabe_abgelehnt(f, _SUCHE_MAX)
                )
                anzeige_feld.inputRejected.connect(
                    lambda f=anzeige_feld: self._eingabe_abgelehnt(f, _ANZEIGE_MAX)
                )

                boxen[disziplin] = (suche_feld, anzeige_feld)
                geladen[disziplin] = (suche_wert, anzeige_wert)

            self._boxen_je_zeile.append(boxen)
            self._geladen_je_zeile.append(geladen)

            # Disqualifiziert/Abbruch (Nutzerwunsch 21.09.): zwei unabhängige Checkboxen,
            # zentriert in ihrer Zelle über einen kleinen Container (QCheckBox selbst hat
            # keine eingebaute Zentrierung als Cell-Widget).
            db_disqualifiziert = bool(aktuell.get("disqualifiziert"))
            db_abbruch = bool(aktuell.get("abbruch"))
            angezeigt_dq, angezeigt_abbruch = status_override.get(
                t["id"], (db_disqualifiziert, db_abbruch)
            )

            dq_box = QCheckBox()
            dq_box.setChecked(angezeigt_dq)
            self.tabelle.setCellWidget(row, _DQ_SPALTE, _zentrierte_zelle(dq_box))

            abbruch_box = QCheckBox()
            abbruch_box.setChecked(angezeigt_abbruch)
            self.tabelle.setCellWidget(row, _ABBRUCH_SPALTE, _zentrierte_zelle(abbruch_box))

            dq_box.toggled.connect(lambda _checked, r=row: self._status_umgeschaltet(r))
            abbruch_box.toggled.connect(lambda _checked, r=row: self._status_umgeschaltet(r))

            self._status_boxen_je_zeile.append((dq_box, abbruch_box))
            self._status_geladen_je_zeile.append((db_disqualifiziert, db_abbruch))

            status_item = QTableWidgetItem("")
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            self.tabelle.setItem(row, _STATUS_SPALTE, status_item)

            # Punkteeingabe sperren/leeren, wenn Disqualifiziert/Abbruch bereits gesetzt
            # ist (auch direkt nach dem Aufbau, nicht erst bei der nächsten Umschaltung).
            if punkte_override and (angezeigt_dq or angezeigt_abbruch):
                # Ungespeicherte Punkte, aber inzwischen DQ/Abbruch in der DB - die Eingabe
                # wird verworfen; der Aufrufer meldet das (Marco, 02.10.2026).
                nummer = f"Nr. {t['startnummer']} – " if t["startnummer"] is not None else ""
                verworfen.append(f"{nummer}{t['nachname']}, {t['vorname']}")
            self._punkteeingabe_sperren(row, angezeigt_dq or angezeigt_abbruch)
            self._aktualisiere_zeilenstatus(row)

        # Spaltenbreiten (und Schriftgröße) an den tatsächlichen Inhalt UND die verfügbare
        # Fensterbreite anpassen - siehe _spaltenbreiten_anpassen().
        self._spaltenbreiten_anpassen()
        return verworfen

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._spaltenbreiten_anpassen()

    def showEvent(self, event) -> None:  # type: ignore[override]
        """Nutzerwunsch (22.09.): Ergebniserfassung soll bei maximiertem Fenster ohne
        horizontales Scrollen auf den Bildschirm passen. Ein resizeEvent allein reicht nicht,
        weil dieser Tab beim Maximieren des Fensters inaktiv (nicht die aktuell sichtbare
        QTabWidget-Seite) sein kann und dann kein zuverlässiges resizeEvent bekommt -
        showEvent fängt den späteren Wechsel zurück auf diesen Tab ab."""
        super().showEvent(event)
        self._spaltenbreiten_anpassen()

    def _spaltenbreiten_anpassen(self) -> None:
        """Passt Schriftgröße und Spaltenbreiten der Ergebnistabelle an die aktuell
        verfügbare Breite an (Nutzerwunsch 22.09.: bei maximiertem Fenster soll die Tabelle
        ohne horizontales Scrollen auf den Bildschirm passen). Die Schriftgröße wird ZUERST
        gesetzt, weil resizeColumnsToContents() danach bei genau dieser Schriftgröße misst.

        Wichtig: ResponsiveSchriftMixin (siehe dort) setzt bereits eine
        "QHeaderView::section { font-size: ... }"-Regel auf HauptFenster selbst - die
        kaskadiert auf JEDEN QHeaderView::section im Fenster, auch den dieser Tabelle. Ein
        reines setFont() auf den Header würde gegen diese geerbte Stylesheet-Regel verlieren,
        deshalb hier ein lokales Stylesheet direkt auf self.tabelle (überschreibt die von
        HauptFenster geerbte Regel nur für diese Tabelle, andere Tabs bleiben unberührt)."""
        breite = self.tabelle.viewport().width()
        pt = _responsive_schriftgroesse(breite, schmal=1000, breit=1600, pt_schmal=7.5, pt_breit=9.5)

        self.tabelle.setStyleSheet(
            f"QHeaderView::section {{ font-size: {pt:.1f}pt; }} "
            f"QTableWidget::item {{ font-size: {pt:.1f}pt; }}"
        )
        font = self.tabelle.font()
        font.setPointSizeF(pt)
        for boxen in self._boxen_je_zeile:
            for suche_feld, anzeige_feld in boxen.values():
                suche_feld.setFont(font)
                anzeige_feld.setFont(font)
        for dq_box, abbruch_box in self._status_boxen_je_zeile:
            dq_box.setFont(font)
            abbruch_box.setFont(font)

        self.tabelle.resizeColumnsToContents()

        # Spalten 0..(_STATUS_SPALTE-1): Start-Nr./Name/Hund/Art-LK, alle Disziplin-
        # Punktepaare sowie Disqualifiziert/Abbruch. Die Status-Spalte selbst bleibt außen
        # vor - die bekommt über setStretchLastSection den Restplatz, dafür wird ihr
        # längster möglicher Inhalt ("● nicht gespeichert", siehe _aktualisiere_zeilenstatus)
        # vorab von der verfügbaren Breite abgezogen, damit sie nicht auf (fast) 0
        # zusammengedrückt wird.
        status_minimum = self.tabelle.fontMetrics().horizontalAdvance("● nicht gespeichert") + 24
        breite_fuer_fixspalten = max(breite - status_minimum, 0)

        punktespalten = {c for paar in _ERGEBNIS_SPALTEN_JE_DISZIPLIN.values() for c in paar}
        minimum_punkte = max(self.tabelle.fontMetrics().horizontalAdvance("88") + 24, 56)

        # Nutzerwunsch (22.09.): Spaltenüberschriften sollen nicht mehr abgeschnitten
        # werden - die bisherigen Minima oben orientierten sich nur am Zelleninhalt
        # ("88" bzw. fix 44px für die Checkbox-Spalten), nicht am Headertext. Deshalb hier
        # zusätzlich je Spalte die Breite der längsten Headerzeile ermitteln (bei den
        # jetzt mehrzeiligen Disziplin-Headern mit "\n" die breitere der beiden Zeilen,
        # bei einzeiligen wie "Disqualifiziert"/"Abbruch" die volle Textbreite, da dort
        # mangels Leerzeichen kein Umbruch möglich ist) und als zusätzliche Untergrenze
        # verwenden.
        header_metriken = self.tabelle.horizontalHeader().fontMetrics()

        def header_zeilen_breite(spalte: int) -> int:
            text = self.tabelle.horizontalHeaderItem(spalte).text()
            return max(header_metriken.horizontalAdvance(zeile) for zeile in text.split("\n")) + 24

        natuerlich = [self.tabelle.columnWidth(c) for c in range(_STATUS_SPALTE)]
        minima = []
        # CI-Regression (22.09.): auf CI/Linux fallen die Schriftmetriken für Headertexte
        # teils ein paar Pixel breiter aus als lokal unter Windows - dort reichte die
        # Summe der obigen (headertext-basierten) Minima bei 1300px knapp nicht mehr aus,
        # obwohl lokal alles passte. harte_minima hält je Spalte den rein inhaltsbasierten
        # Wert von vor dieser Headertext-Erweiterung vor - als Fallback für
        # _ergebnis_spaltenbreiten_verteilen, falls die obigen Minima allein nicht reichen
        # (dann ggf. minimal abgeschnittener Headertext statt Scrollbalken, siehe dortige
        # Docstring-Erläuterung).
        harte_minima = []
        for c in range(_STATUS_SPALTE):
            if c in punktespalten:
                minima.append(max(minimum_punkte, header_zeilen_breite(c)))
                harte_minima.append(minimum_punkte)
            elif c in (_DQ_SPALTE, _ABBRUCH_SPALTE):
                minima.append(max(44, header_zeilen_breite(c)))
                harte_minima.append(44)
            else:
                # Start-Nr./Name/Hund/Art-LK: reiner Text ohne Eingabefeld, schrumpft nicht
                # unter die eigene natürliche Breite (soll nicht abgeschnitten werden).
                minima.append(natuerlich[c])
                harte_minima.append(natuerlich[c])

        ziel = _ergebnis_spaltenbreiten_verteilen(
            natuerlich, minima, breite_fuer_fixspalten, harte_minima
        )
        for c, w in enumerate(ziel):
            self.tabelle.setColumnWidth(c, w)
        # UX-Test 02.10.2026, K1: Zeilen mindestens so hoch wie ein Eingabefeld - sonst
        # wurden eingetippte Punkte unten abgeschnitten.
        feldhoehe = QLineEdit().sizeHint().height()
        kopf = self.tabelle.verticalHeader()
        if kopf.defaultSectionSize() < feldhoehe + 4:
            kopf.setDefaultSectionSize(feldhoehe + 4)

    def _spalte_geklickt(self, spalte: int) -> None:
        """Reagiert auf einen Klick auf eine Spaltenüberschrift: sortiert danach, erneuter
        Klick auf dieselbe Spalte kehrt die Richtung um (siehe Klassen-/Konstruktor-
        Docstring zur Begründung der eigenen Sortierlogik statt Qt-Bordmittel)."""
        if self._sortierspalte == spalte:
            self._sortieraufsteigend = not self._sortieraufsteigend
        else:
            self._sortierspalte = spalte
            self._sortieraufsteigend = True
        self._verworfene_melden(self._sortieren_und_neu_aufbauen())

    def _sortierschluessel_fuer_zeile(self, row: int, spalte: int):
        """Sortierschlüssel für Zeile `row` bezogen auf die VOR dem Sortieren gültige
        Zeilenreihenfolge (self._teilnehmer_je_zeile/_boxen_je_zeile/
        _status_boxen_je_zeile sind zu diesem Zeitpunkt noch nicht umsortiert)."""
        if spalte == 0:
            startnummer = self._teilnehmer_je_zeile[row]["startnummer"]
            return startnummer if startnummer is not None else -1
        if spalte == 1:
            t = self._teilnehmer_je_zeile[row]
            return f"{t['nachname']}, {t['vorname']}".lower()
        if spalte == 2:
            return self._teilnehmer_je_zeile[row]["rufname_hund"].lower()
        if spalte == 3:
            return leistungsklasse_label(self._teilnehmer_je_zeile[row]).lower()
        if spalte == _DQ_SPALTE:
            return self._status_boxen_je_zeile[row][0].isChecked()
        if spalte == _ABBRUCH_SPALTE:
            return self._status_boxen_je_zeile[row][1].isChecked()
        if spalte == _STATUS_SPALTE:
            item = self.tabelle.item(row, spalte)
            return item.text() if item is not None else ""
        for disziplin, (spalte_suche, spalte_anzeige) in _ERGEBNIS_SPALTEN_JE_DISZIPLIN.items():
            if spalte not in (spalte_suche, spalte_anzeige):
                continue
            boxen = self._boxen_je_zeile[row].get(disziplin)
            if boxen is None:
                return -1
            feld = boxen[0] if spalte == spalte_suche else boxen[1]
            wert = self._feldwert(feld)
            return wert if wert is not None else -1
        return ""

    def _sortieren_und_neu_aufbauen(self) -> list[str]:
        """Sortiert self._teilnehmer_je_zeile nach der zuletzt gewählten Spalte/Richtung
        und baut die Tabelle neu auf - sichert VORHER die aktuellen (ggf. noch nicht
        gespeicherten) Eingaben je Teilnehmer-ID, damit beim Neuaufbau keine ungespeicherte
        Eingabe verloren geht (siehe Klassen-/Konstruktor-Docstring)."""
        werte_je_id, status_je_id = self._eingaben_je_id()

        reihenfolge = sorted(
            range(len(self._teilnehmer_je_zeile)),
            key=lambda row: self._sortierschluessel_fuer_zeile(row, self._sortierspalte),
            reverse=not self._sortieraufsteigend,
        )
        self._teilnehmer_je_zeile = [self._teilnehmer_je_zeile[i] for i in reihenfolge]

        verworfen = self._zeilen_aufbauen(werte_je_id, status_je_id)
        self._filter_anwenden()
        return verworfen

    def _eingaben_je_id(self) -> tuple[dict, dict]:
        """Nur die tatsächlich noch NICHT gespeicherten Eingaben (Punkte je Disziplin,
        DQ/Abbruch-Häkchen) je Teilnehmer-ID - als Overrides für _zeilen_aufbauen().
        Bewusst nicht einfach alle angezeigten Werte: _zeilen_aufbauen() liest die
        gespeicherten Werte frisch aus der DB, ein unveränderter, aber veralteter
        Anzeigewert würde sonst als "ungespeichert" gelten und beim nächsten Speichern
        einen inzwischen anders gespeicherten Wert (z. B. aus dem Web zurückgeholte
        Ergebnisse) überschreiben oder löschen (Befund Nachprüfung 02.10.2026)."""
        werte_je_id: dict = {}
        status_je_id: dict = {}
        for row, t in enumerate(self._teilnehmer_je_zeile):
            dq_box, abbruch_box = self._status_boxen_je_zeile[row]
            status = (dq_box.isChecked(), abbruch_box.isChecked())
            if status != self._status_geladen_je_zeile[row]:
                status_je_id[t["id"]] = status
            if status[0] or status[1]:
                continue  # Punktefelder sind gesperrt/geleert - nichts zu übernehmen
            geladen = self._geladen_je_zeile[row]
            for disziplin, (suche_feld, anzeige_feld) in self._boxen_je_zeile[row].items():
                angezeigt = (self._feldwert(suche_feld), self._feldwert(anzeige_feld))
                if angezeigt != geladen[disziplin]:
                    werte_je_id.setdefault(t["id"], {})[disziplin] = angezeigt
        return werte_je_id, status_je_id

    def aktualisieren_eingaben_erhalten(self) -> None:
        """Lädt die Teilnehmerliste neu aus der Datenbank, behält dabei aber noch nicht
        gespeicherte Eingaben bei (Befund aus der Verifikation "keine Teilnahme",
        02.10.2026): Wurde beim Tabwechsel das Speichern abgelehnt, lud der Reiter vorher
        gar nicht neu - ein inzwischen als "keine Teilnahme" markierter (oder neu
        angelegter) Teilnehmer blieb bis "Liste aktualisieren" fälschlich drin bzw.
        fehlte. Eingaben zu Teilnehmern, die nicht mehr in der Liste stehen, entfallen."""
        self._neu_laden(*self._eingaben_je_id())

    def _verworfene_melden(self, verworfen: list[str]) -> None:
        """Hinweis, wenn beim Neuaufbau ungespeicherte Punkte verworfen wurden, weil für
        den Teilnehmer inzwischen Disqualifiziert/Abbruch gespeichert ist. Die Liste kommt
        als Rückgabewert aus _zeilen_aufbauen (kein Zwischenzustand im Objekt)."""
        if not verworfen:
            return
        namen = "\n".join(dict.fromkeys(verworfen))
        QMessageBox.information(
            self,
            "Eingaben verworfen",
            "Für folgende Teilnehmer ist inzwischen „Disqualifiziert“ oder „Abbruch“ "
            "gespeichert. Die noch nicht gespeicherten Änderungen an ihren Punkten wurden "
            "deshalb verworfen:\n\n"
            + namen,
        )

    def _aktualisieren_mit_rueckfrage(self) -> None:
        """Reagiert auf den "Liste aktualisieren"-Button: warnt vorher, falls dabei
        ungespeicherte Änderungen verloren gingen."""
        if self.hat_ungespeicherte_aenderungen():
            antwort = QMessageBox.question(
                self,
                "Ungespeicherte Änderungen",
                "Es gibt noch nicht gespeicherte Ergebnisse. Beim Aktualisieren gehen diese "
                "verloren.\n\nTrotzdem aktualisieren?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if antwort != QMessageBox.Yes:
                return
        self.aktualisieren()

    def _filter_anwenden(self) -> None:
        """Blendet Zeilen anhand des aktuellen Filters nur aus/ein (setRowHidden),
        statt die Tabelle neu aufzubauen - so bleiben noch nicht gespeicherte
        Eingaben in ausgeblendeten Zeilen erhalten."""
        filter_wert = self.filter_combo.currentText()
        filter_startnr = self.filter_startnummer.text().strip()
        for row, t in enumerate(self._teilnehmer_je_zeile):
            passt = (
                filter_wert in ("Alle", "") or leistungsklasse_label(t) == filter_wert
            ) and (not filter_startnr or str(t["startnummer"] or "") == filter_startnr)
            self.tabelle.setRowHidden(row, not passt)

    @staticmethod
    def _feldwert(feld: QLineEdit) -> int | None:
        """Liest ein Eingabefeld als Zahl - leer (oder ein durch die Validierung noch
        unvollständiger Zwischenzustand) ergibt None, entspricht also "noch nicht
        eingetragen", ohne dass dafür ein Platzhalterwert im Feld stehen müsste."""
        text = feld.text().strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            return None

    def _zeile_ist_ungespeichert(self, row: int) -> bool:
        dq_box, abbruch_box = self._status_boxen_je_zeile[row]
        status_geaendert = (dq_box.isChecked(), abbruch_box.isChecked()) != self._status_geladen_je_zeile[row]
        if dq_box.isChecked() or abbruch_box.isChecked():
            # Punkte-Felder sind gesperrt und geleert (siehe _punkteeingabe_sperren) - ihr
            # (leerer) Inhalt sagt nichts über einen noch zu speichernden Punkte-Stand aus,
            # sonst würde eine bereits gespeicherte Disqualifiziert-/Abbruch-Zeile mit
            # weiterhin in der DB stehenden Punkten dauerhaft als "nicht gespeichert"
            # markiert bleiben.
            return status_geaendert
        boxen = self._boxen_je_zeile[row]
        geladen = self._geladen_je_zeile[row]
        punkte_geaendert = any(
            (self._feldwert(suche_feld), self._feldwert(anzeige_feld)) != geladen[disziplin]
            for disziplin, (suche_feld, anzeige_feld) in boxen.items()
        )
        return punkte_geaendert or status_geaendert

    def _status_umgeschaltet(self, row: int) -> None:
        """Reagiert auf das Umschalten einer Disqualifiziert-/Abbruch-Checkbox: sperrt/
        leert bei Bedarf die Punkte-Eingabefelder dieser Zeile und aktualisiert den
        Gespeichert-Status. Beim Entsperren (Häkchen entfernt) werden die Felder zuvor
        wieder mit dem zuletzt aus der DB geladenen Stand befüllt statt leer zu bleiben -
        die zugehörigen Punkte wurden beim Sperren NICHT gelöscht (siehe alle_speichern),
        das Feld soll also wieder den tatsächlichen, in der DB stehenden Wert zeigen."""
        dq_box, abbruch_box = self._status_boxen_je_zeile[row]
        sperren = dq_box.isChecked() or abbruch_box.isChecked()
        if not sperren:
            geladen = self._geladen_je_zeile[row]
            for disziplin, (suche_feld, anzeige_feld) in self._boxen_je_zeile[row].items():
                suche_wert, anzeige_wert = geladen[disziplin]
                suche_feld.setText("" if suche_wert is None else str(suche_wert))
                anzeige_feld.setText("" if anzeige_wert is None else str(anzeige_wert))
        self._punkteeingabe_sperren(row, sperren)
        self._aktualisiere_zeilenstatus(row)

    def _punkteeingabe_sperren(self, row: int, sperren: bool) -> None:
        """Sperrt (und leert) die Punkte-Eingabefelder einer Zeile, solange Disqualifiziert
        oder Abbruch gesetzt ist - eine Punkteeingabe wäre dann ohnehin irrelevant, da
        berechne_auswertung() für einen solchen Teilnehmer keine aus Punkten berechnete
        Wertnote mehr bildet (siehe db.py). Rührt beim Entsperren den Feldinhalt bewusst
        NICHT an (siehe _status_umgeschaltet für die interaktive Wiederherstellung) - beim
        Neuaufbau der Tabelle (_zeilen_aufbauen) ist der Feldinhalt zu diesem Zeitpunkt
        bereits korrekt (ggf. inkl. einer noch nicht gespeicherten Eingabe aus
        werte_override) und darf nicht überschrieben werden."""
        for suche_feld, anzeige_feld in self._boxen_je_zeile[row].values():
            if sperren:
                suche_feld.setText("")
                anzeige_feld.setText("")
            suche_feld.setEnabled(not sperren)
            anzeige_feld.setEnabled(not sperren)

    def _eingabe_abgelehnt(self, feld: QLineEdit, maximum: int) -> None:
        """Hinweis, wenn der Validator ein Zeichen ablehnt (Komma, Buchstabe, dritte
        Ziffer) - sonst wirkt es, als würde die Eingabe einfach verschluckt."""
        hinweis = f"Nur ganze Punkte von 0 bis {maximum} eingeben (keine Kommazahlen)."
        QToolTip.showText(feld.mapToGlobal(feld.rect().bottomLeft()), hinweis, feld)
        # UX-Nachtest 03.10.2026, N6 (ersetzt den 8-Sekunden-Timer aus U5b): der Hinweis wurde
        # leicht übersehen - er steht jetzt orange und fett in der Statuszeile, bis die nächste
        # gültige Eingabe kommt. Die Hervorhebung steckt im Text selbst (Rich Text), damit
        # spätere Statusmeldungen sie nicht erben.
        self._eingabe_hinweis = (
            f'<span style="color:{_farbe("warnung").name()}; font-weight:bold;">{hinweis}</span>'
        )
        self.status_label.setText(self._eingabe_hinweis)

    def _eingabe_hinweis_ausblenden(self) -> None:
        """Nimmt den Komma-Hinweis wieder weg - nur, wenn dort noch der Hinweis steht."""
        hinweis = getattr(self, "_eingabe_hinweis", None)
        if hinweis is not None and self.status_label.text() == hinweis:
            self.status_label.setText("")
        self._eingabe_hinweis = None

    def _aktualisiere_zeilenstatus(self, row: int) -> None:
        """Färbt die Zeile gelb und setzt den Status-Text, solange sich mindestens ein
        Wert vom zuletzt gespeicherten Stand unterscheidet. Punktefelder mit einem Wert
        über dem Maximum bekommen zusätzlich einen roten Rahmen und einen Tooltip."""
        self._eingabe_hinweis_ausblenden()  # gültige Eingabe: Komma-Hinweis (U5b) weg
        ungespeichert = self._zeile_ist_ungespeichert(row)
        farbe = _farbe("ungespeichert_bg" if ungespeichert else "zeile_bg")
        maximum_je_feld = {}
        for suche_feld, anzeige_feld in self._boxen_je_zeile[row].values():
            maximum_je_feld[suche_feld] = _SUCHE_MAX
            maximum_je_feld[anzeige_feld] = _ANZEIGE_MAX

        for col in range(self.tabelle.columnCount()):
            widget = self.tabelle.cellWidget(row, col)
            if widget is not None:
                # Gilt sowohl für die Punkte-QLineEdit-Felder als auch für den Container
                # der Disqualifiziert-/Abbruch-Checkbox (siehe _zentrierte_zelle) -
                # QSS-Hintergrundfarbe funktioniert für beide Widget-Arten gleich.
                stil = f"background-color: {farbe.name()};" if ungespeichert else ""
                maximum = maximum_je_feld.get(widget)
                if maximum is not None:
                    wert = self._feldwert(widget)
                    zu_hoch = wert is not None and wert > maximum
                    if zu_hoch:
                        stil += f" border: 2px solid {_farbe('fehler').name()};"
                    widget.setToolTip(f"Höchstens {maximum} Punkte." if zu_hoch else "")
                widget.setStyleSheet(stil)
            else:
                item = self.tabelle.item(row, col)
                if item is not None:
                    item.setBackground(farbe)

        status_item = self.tabelle.item(row, _STATUS_SPALTE)
        if status_item is not None:
            if ungespeichert:
                status_item.setText("● nicht gespeichert")
                status_item.setForeground(_farbe("warnung"))
            elif self._zeile_ist_leer(row):
                # UX-Test 02.10.2026, K1: vorher stand auch bei noch leeren Zeilen
                # "✓ gespeichert" - das wirkte, als seien schon Ergebnisse eingetragen.
                status_item.setText("noch kein Ergebnis")
                status_item.setForeground(_farbe("gedaempft"))
            else:
                status_item.setText("✓ gespeichert")
                status_item.setForeground(_farbe("ok"))

    def _zeile_ist_leer(self, row: int) -> bool:
        """Weder Punkte noch Disqualifiziert/Abbruch - gespeichert oder eingegeben."""
        dq_box, abbruch_box = self._status_boxen_je_zeile[row]
        if dq_box.isChecked() or abbruch_box.isChecked() or any(self._status_geladen_je_zeile[row]):
            return False
        return all(
            self._feldwert(suche) is None and self._feldwert(anzeige) is None
            and self._geladen_je_zeile[row][disziplin] == (None, None)
            for disziplin, (suche, anzeige) in self._boxen_je_zeile[row].items()
        )

    def farben_auffrischen(self) -> None:
        """Färbt alle Zeilen nach einem Wechsel des Hintergrund-Designs neu - bewusst
        OHNE aktualisieren(), das die Tabelle aus der DB neu aufbauen und damit
        ungespeicherte Eingaben verwerfen würde."""
        for row in range(self.tabelle.rowCount()):
            for col in range(self.tabelle.columnCount()):
                item = self.tabelle.item(row, col)
                # "–"-Platzhalter für Disziplinen, die für diesen Teilnehmer nicht gelten.
                if item is not None and item.text() == "–" and not (item.flags() & Qt.ItemIsEditable):
                    item.setForeground(_farbe("gedaempft"))
            self._aktualisiere_zeilenstatus(row)

    def alle_speichern(self) -> None:
        """Speichert alle geänderten Zeilen der Tabelle auf einmal (unabhängig vom
        aktuellen Filter - auch ausgeblendete Zeilen werden mitgespeichert)."""
        gespeichert = 0
        fehler: list[str] = []

        for row, t in enumerate(self._teilnehmer_je_zeile):
            name = f"{t['nachname']}, {t['vorname']}"
            boxen = self._boxen_je_zeile[row]
            geladen = self._geladen_je_zeile[row]
            dq_box, abbruch_box = self._status_boxen_je_zeile[row]
            status_wert = (dq_box.isChecked(), abbruch_box.isChecked())
            punkte_gesperrt = status_wert[0] or status_wert[1]

            if not punkte_gesperrt:
                for disziplin, (suche_feld, anzeige_feld) in boxen.items():
                    suche_wert, anzeige_wert = self._feldwert(suche_feld), self._feldwert(anzeige_feld)
                    if (suche_wert, anzeige_wert) == geladen[disziplin]:
                        continue  # unverändert - nichts zu tun

                    if suche_wert is None and anzeige_wert is None:
                        # Beide Felder wurden geleert - vorher eingetragenes Ergebnis wird
                        # als gelöscht gespeichert (NULL in der DB), statt nur in der
                        # Tabelle leer auszusehen, aber beim nächsten Laden wieder
                        # aufzutauchen bzw. dauerhaft als "nicht gespeichert" markiert zu
                        # bleiben.
                        eintragen_ergebnis(self.conn, t["id"], disziplin, None, None)
                        geladen[disziplin] = (None, None)
                        gespeichert += 1
                        continue

                    # Codeprüfung 22.09., G6: gemeinsame Eingaberegel mit dem Web-Frontend
                    # (db.pruefe_ergebnis_eingabe) statt eigener Prüfung - eine halb
                    # ausgefüllte Disziplin wird weiterhin abgelehnt und bleibt ungespeichert.
                    eingabe_fehler = pruefe_ergebnis_eingabe(suche_wert, anzeige_wert)
                    if eingabe_fehler is not None:
                        fehler.append(f"{name} – {disziplin}: {eingabe_fehler}")
                        continue
                    zu_hoch = [
                        f"{teil} höchstens {maximum} Punkte (eingegeben: {wert})"
                        for teil, wert, maximum in (
                            ("Suche", suche_wert, _SUCHE_MAX), ("Anzeige", anzeige_wert, _ANZEIGE_MAX)
                        )
                        if wert > maximum
                    ]
                    if zu_hoch:
                        fehler.append(f"{name} – {disziplin}: " + ", ".join(zu_hoch))
                        continue

                    try:
                        eintragen_ergebnis(self.conn, t["id"], disziplin, suche_wert, anzeige_wert)
                    except sqlite3.IntegrityError as exc:
                        fehler.append(f"{name} – {disziplin}: {exc}")
                        continue

                    geladen[disziplin] = (suche_wert, anzeige_wert)
                    gespeichert += 1
            # Ist die Zeile gesperrt (Disqualifiziert/Abbruch), werden die (geleerten)
            # Punkte-Felder beim Speichern bewusst NICHT ausgewertet: eine ggf. weiterhin
            # in der DB stehende Punktzahl bleibt unangetastet (siehe
            # db.setze_ergebnis_status()-Docstring) - vorher wurden hier fälschlich beide
            # Felder als "geleert" erkannt und die echten Punkte dauerhaft gelöscht.

            if status_wert != self._status_geladen_je_zeile[row]:
                setze_ergebnis_status(self.conn, t["id"], status_wert[0], status_wert[1])
                self._status_geladen_je_zeile[row] = status_wert
                gespeichert += 1

            self._aktualisiere_zeilenstatus(row)

        if gespeichert:
            self.status_label.setText(f"{gespeichert} Ergebnis(se) gespeichert.")
        elif not fehler:
            self.status_label.setText("Keine Änderungen zu speichern.")

        if fehler:
            QMessageBox.warning(
                self,
                "Nicht alle Ergebnisse gespeichert",
                "Folgende Zeilen konnten nicht gespeichert werden (übrige wurden gespeichert):\n\n"
                + "\n".join(fehler),
            )


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


def _vorname_nachname(name: str) -> str:
    """"Nachname, Vorname" (Teilnehmerergebnis.name) -> "Vorname Nachname" (wie K2)."""
    nachname, _, vorname = name.partition(", ")
    return f"{vorname} {nachname}".strip()


def _stechen_offen_bestaetigen(parent, conn, leistungsklasse: str | None = None) -> bool:
    """S1 (Marco 03.10.2026): Rückfrage vor der Ergebnisliste, wenn ein Stechen um Platz 1
    noch offen ist (wie beim Zeitplan mit Überschneidungen). True = trotzdem erzeugen."""
    fertig, _ = berechne_auswertung(conn)
    offen = [
        lk for lk, g in stechen_gruppen(fertig).items()
        if all(t.stechen == "offen" for t in g) and (leistungsklasse is None or lk == leistungsklasse)
    ]
    if not offen:
        return True
    antwort = QMessageBox.question(
        parent, "Stechen offen",
        "In " + ", ".join(offen) + " sind mehrere punktgleich auf Platz 1 – das Stechen ist noch "
        "nicht eingetragen (Reiter „Auswertung“ → „Stechen-Sieger festlegen…“).\n\n"
        "Die Ergebnisliste trotzdem jetzt speichern? Dort steht dann „Stechen offen“.",
    )
    return antwort == QMessageBox.Yes


class AuswertungTab(QWidget):
    def __init__(self, conn, ablageort: _Ablageort | None = None, parent=None):
        super().__init__(parent)
        self.conn = conn
        # Für den Druck-Button (Nutzerwunsch 23.09.) - dasselbe Objekt wie in den Tabs
        # "Zeitplan"/"Export", wenn HauptFenster eines übergibt (siehe _Ablageort).
        self._ablageort = ablageort if ablageort is not None else _Ablageort(str(termine_ordner()))
        self._fertig: list = []
        self._ausstehend: list[dict] = []
        self._startnummer_je_id: dict[str, int | None] = {}
        self._rufname_hund_je_id: dict[str, str] = {}

        self.tabelle = QTableWidget(0, 7)
        self.tabelle.setHorizontalHeaderLabels(
            ["Start-Nr.", "Leistungsklasse", "Name", "Hund", "Gesamtpunkte", "Wertnote", "Platzierung"]
        )
        self.tabelle.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabelle.horizontalHeader().setStretchLastSection(True)
        # Zeilennummern links ausblenden - wie bereits bei TeilnehmerTab/ErgebnisTab, hier
        # bisher übersehen (Nutzerhinweis 20.09.).
        self.tabelle.verticalHeader().setVisible(False)

        self.filter_combo = QComboBox()
        # Passt die Breite der Box an den längsten enthaltenen Eintrag an (z.B. lange
        # Art/LK-Bezeichnungen wie "ED LK 3 Behältnisstrecke"), statt Text abzuschneiden.
        self.filter_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.filter_combo.currentTextChanged.connect(self._rendern)

        self.filter_startnummer = QLineEdit()
        self.filter_startnummer.setPlaceholderText("z.B. 13")
        self.filter_startnummer.setMaximumWidth(80)
        self.filter_startnummer.textChanged.connect(self._rendern)

        self.ausstehend_label = QLabel()
        # UX-Test 02.10.2026, U12: die Namensliste kann sehr lang werden - ohne Umbruch zog
        # dieses Label das ganze Hauptfenster über die Bildschirmbreite (~1800 px).
        self.ausstehend_label.setWordWrap(True)
        self.ausstehend_label.setTextFormat(Qt.PlainText)  # S-1: enthält Namen

        aktualisieren_btn = QPushButton("Auswertung neu berechnen")
        aktualisieren_btn.clicked.connect(self.aktualisieren)

        # Nutzerwunsch 23.09.: Rangliste direkt aus der Auswertung als PDF ausgeben (bisher
        # nur über Export -> Ergebnisliste). Übernimmt den Art/LK-Filter, bewusst NICHT den
        # Start-Nr.-Filter (Marcos Entscheidung).
        self.drucken_btn = QPushButton("Rangliste drucken (PDF)…")
        self.drucken_btn.clicked.connect(self._rangliste_drucken)
        # S1 (Marco 03.10.2026): Sieger eines Stechens bei Gleichstand um Platz 1 festlegen.
        self.stechen_btn = QPushButton("Stechen-Sieger festlegen…")
        self.stechen_btn.setToolTip("Bei Punktgleichheit auf Platz 1 entscheidet ein Stechen – hier den Sieger eintragen.")
        self.stechen_btn.clicked.connect(self._stechen_sieger_festlegen)

        self.status_label = QLabel("")
        self.status_label.setTextFormat(Qt.PlainText)  # S-1: enthält Pfade/Namen
        self.status_label.setWordWrap(True)  # enthält nach "Rangliste drucken" einen langen Pfad (U12)

        filter_zeile = QHBoxLayout()
        filter_zeile.addWidget(QLabel("Filter Art/LK:"))
        filter_zeile.addWidget(self.filter_combo)
        filter_zeile.addSpacing(16)
        filter_zeile.addWidget(QLabel("Filter Start-Nr.:"))
        filter_zeile.addWidget(self.filter_startnummer)
        filter_zeile.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(filter_zeile)
        layout.addWidget(self.tabelle)
        layout.addWidget(self.ausstehend_label)
        button_zeile = QHBoxLayout()
        button_zeile.addWidget(aktualisieren_btn)
        button_zeile.addWidget(self.drucken_btn)
        button_zeile.addWidget(self.stechen_btn)
        button_zeile.addStretch()
        layout.addLayout(button_zeile)
        layout.addWidget(self.status_label)

        self.aktualisieren()

    def _stechen_sieger_festlegen(self) -> None:
        """S1: je Gleichstand um Platz 1 den Stechen-Sieger wählen (oder offen lassen)."""
        gruppen = stechen_gruppen(self._fertig)
        if not gruppen:
            QMessageBox.information(self, "Kein Stechen", "Es gibt keinen Gleichstand um Platz 1.")
            return
        offen_text = "Stechen noch offen"
        eintraege, zuordnung = [], {}
        for lk, gruppe in gruppen.items():
            for t in gruppe:
                text = f"{lk}: {_vorname_nachname(t.name)} ({t.gesamtpunkte} Punkte)"
                eintraege.append(text)
                zuordnung[text] = (lk, int(t.id))
            text = f"{lk}: {offen_text}"
            eintraege.append(text)
            zuordnung[text] = (lk, None)
        aktuell = next(
            (i for i, e in enumerate(eintraege)
             if zuordnung[e][1] is not None and any(
                 t.stechen == "gewonnen" and int(t.id) == zuordnung[e][1] for g in gruppen.values() for t in g)),
            0,
        )
        auswahl, ok = QInputDialog.getItem(
            self, "Stechen-Sieger festlegen",
            "Wer hat das Stechen gewonnen? Er wird 1., die anderen Punktgleichen werden 2.",
            eintraege, aktuell, False,
        )
        if not ok:
            return
        lk, sieger = zuordnung[auswahl]
        setze_stechen_sieger(self.conn, sieger, [int(t.id) for t in gruppen[lk]])
        self.aktualisieren()

    def _gewaehlte_leistungsklasse(self) -> str | None:
        """Label der im Art/LK-Filter gewählten Leistungsklasse, None bei "Alle"."""
        filter_wert = self.filter_combo.currentText()
        return None if filter_wert in ("Alle", "") else filter_wert

    def _rangliste_drucken(self) -> None:
        leistungsklasse = self._gewaehlte_leistungsklasse()
        if not _stechen_offen_bestaetigen(self, self.conn, leistungsklasse):
            return
        praefix = "Ergebnisliste" if leistungsklasse is None else f"Ergebnisliste_{leistungsklasse.replace(' ', '_')}"
        pfad = _pdf_speicherort_waehlen(
            self, self._ablageort, "Rangliste speichern", _export_dateiname(self.conn, praefix)
        )
        if not pfad:
            return
        try:
            pdf_export.erstelle_ergebnisliste_pdf(self.conn, pfad, leistungsklasse)
        except Exception as exc:
            _pdf_export_fehler_anzeigen(self, exc)
            return
        self.status_label.setText(f"Rangliste gespeichert: {_pfad_anzeige(pfad)}")
        _datei_gespeichert_melden(self, pfad, "Rangliste gespeichert")

    def aktualisieren(self) -> None:
        """Berechnet die Auswertung aus der Datenbank neu und aktualisiert den Filter."""
        self._fertig, self._ausstehend = berechne_auswertung(self.conn)
        # Teilnehmerergebnis (shs_core) kennt keine Startnummer - für die Anzeige/den
        # Filter hier separat aus den Stammdaten nachschlagen.
        self._startnummer_je_id = {str(t["id"]): t["startnummer"] for t in list_teilnehmer(self.conn)}
        self._rufname_hund_je_id = {str(t["id"]): t["rufname_hund"] for t in list_teilnehmer(self.conn)}

        alle_labels = sorted({t.leistungsklasse for t in self._fertig} | {leistungsklasse_label(t) for t in self._ausstehend})
        bisherige_auswahl = self.filter_combo.currentText()
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItem("Alle")
        self.filter_combo.addItems(alle_labels)
        index = self.filter_combo.findText(bisherige_auswahl)
        self.filter_combo.setCurrentIndex(index if index >= 0 else 0)
        self.filter_combo.blockSignals(False)

        self._rendern()

    def _rendern(self) -> None:
        """Zeigt die zwischengespeicherte Auswertung gefiltert nach der aktuellen Filterauswahl an."""
        filter_wert = self.filter_combo.currentText()
        filter_startnr = self.filter_startnummer.text().strip()

        def passt(label: str, startnummer: int | None) -> bool:
            if filter_wert not in ("Alle", "") and label != filter_wert:
                return False
            if filter_startnr and str(startnummer or "") != filter_startnr:
                return False
            return True

        fertig_gefiltert = sorted(
            (t for t in self._fertig if passt(t.leistungsklasse, self._startnummer_je_id.get(t.id))),
            # nicht bestandene Teilnehmer (platzierung=None) einsortieren wir ans Ende
            # ihrer Leistungsklasse, statt sie mit Platz 1 zu verwechseln.
            key=lambda t: (t.leistungsklasse, t.platzierung is None, t.platzierung or 0),
        )
        ausstehend_gefiltert = [
            t for t in self._ausstehend if passt(leistungsklasse_label(t), t["startnummer"])
        ]

        # UX-Test 02.10.2026, K9 (Marco 03.10.: Hinweiszeile + Tooltip): "von x" zählt nur
        # Starter mit vollständigem Ergebnis - bei noch offenen Teilnehmern wirkte "1. von 2"
        # bei 5 gemeldeten wie ein Fehler.
        offen_je_lk: dict[str, int] = {}
        for t in self._ausstehend:
            offen_je_lk[leistungsklasse_label(t)] = offen_je_lk.get(leistungsklasse_label(t), 0) + 1

        self.tabelle.setRowCount(len(fertig_gefiltert))
        for row, t in enumerate(fertig_gefiltert):
            # Disqualifiziert/Abbruch (Nutzerwunsch 21.09.): db.berechne_auswertung() gibt
            # solchen Teilnehmern eine Platzhalter-Wertnote mit abkuerzung=DISQUALIFIZIERT_ABK/
            # ABBRUCH_ABK statt einer aus Punkten berechneten - hier ähnlich der bestehenden
            # "nicht bestanden"-Behandlung (keine Platzierung, zählt als Starter, rot
            # markiert über t.bestanden weiter unten), aber mit eigenem Text statt "nB"/
            # Wertnote.
            ist_disqualifiziert = t.wertnote.abkuerzung == DISQUALIFIZIERT_ABK
            ist_abbruch = t.wertnote.abkuerzung == ABBRUCH_ABK
            if ist_disqualifiziert or ist_abbruch:
                status_text = DISQUALIFIZIERT_TEXT if ist_disqualifiziert else ABBRUCH_TEXT
                wertnote_text = status_text
                punkte_text = "–"
            else:
                # nicht bestanden (mind. eine Disziplin unter 70 Punkten) -> keine
                # Platzierung, entspricht im Original dem Kürzel "nB" in der Rankingliste.
                status_text = "nB"
                wertnote_text = f"{t.wertnote.notentext} ({t.wertnote.abkuerzung})"
                punkte_text = str(t.gesamtpunkte)

            # S1 (03.10.2026): "(Stechen offen)" / "(nach Stechen)" über shs_core.platz_text.
            platz = platz_text(t) or f"{status_text} (von {t.von_startern} Startern)"
            werte = [
                str(self._startnummer_je_id.get(t.id) or ""),
                t.leistungsklasse,
                t.name,
                self._rufname_hund_je_id.get(t.id, ""),
                punkte_text,
                wertnote_text,
                platz,
            ]
            offen = offen_je_lk.get(t.leistungsklasse, 0)
            platz_tooltip = (
                f"„von {t.von_startern}“ zählt nur Starter mit vollständigem Ergebnis in {t.leistungsklasse}"
                + (f" – {offen} noch offen." if offen else ".")
            )
            for col, wert in enumerate(werte):
                item = QTableWidgetItem(wert)
                if not t.bestanden:
                    item.setForeground(_farbe("fehler"))
                if col == len(werte) - 1:
                    item.setToolTip(platz_tooltip)
                self.tabelle.setItem(row, col, item)
        self.tabelle.resizeColumnsToContents()

        von_je_lk = {t.leistungsklasse: t.von_startern for t in fertig_gefiltert}
        von_hinweise = [
            f"Hinweis {lk}: „von {von}“ zählt nur Starter mit vollständigem Ergebnis – "
            f"{offen_je_lk[lk]} noch offen."
            for lk, von in sorted(von_je_lk.items()) if offen_je_lk.get(lk)
        ]
        # S1 (Marco 03.10.2026): Gleichstand um Platz 1 -> Stechen.
        sichtbare_lk = set(von_je_lk)
        gruppen = {lk: g for lk, g in stechen_gruppen(self._fertig).items() if lk in sichtbare_lk}
        self.stechen_btn.setEnabled(bool(stechen_gruppen(self._fertig)))
        von_hinweise = [
            f"Stechen nötig in {lk}: "
            + ", ".join(_vorname_nachname(t.name) for t in g)
            + f" ({g[0].gesamtpunkte} Punkte) – danach „Stechen-Sieger festlegen…“."
            for lk, g in gruppen.items() if all(t.stechen == "offen" for t in g)
        ] + von_hinweise

        if ausstehend_gefiltert:
            # UX-Test 02.10.2026, K2: "Vorname Nachname; …" statt "Nachname, Vorname, …" -
            # das doppelt belegte Komma machte unklar, wo ein Name endet.
            namen = "; ".join(f"{t['vorname']} {t['nachname']}" for t in ausstehend_gefiltert)
            self.ausstehend_label.setText(
                "\n".join(von_hinweise + [f"Noch ohne vollständiges Ergebnis ({len(ausstehend_gefiltert)}): {namen}"])
            )
        else:
            # K9-Verifikation: Sind in der LK noch andere offen (z. B. Filter auf eine
            # Startnummer), nur der Hinweis - "alle vollständig" wirkte daneben widersprüchlich.
            self.ausstehend_label.setText(
                "\n".join(von_hinweise or ["Alle Teilnehmer (in diesem Filter) sind vollständig ausgewertet."])
            )


class TeilnehmerUebersichtTab(QWidget):
    """Zeigt Teilnehmerzahlen je Art/Leistungsklasse inkl. der ED-Disziplin-Aufschlüsselung
    sowie die daraus abgeleitete Anzahl benötigter Richter - entspricht der Sicht
    "Übersicht Teilnehmer" aus der ursprünglichen Excel-Vorlage (siehe Grobkonzept.md), hier
    mit "SH-R" durch den in diesem Programm sonst verwendeten Begriff "Richter"
    ersetzt. Datenquelle ist db.berechne_teilnehmer_lk_uebersicht() - wie bei AuswertungTab
    kein Zwischenspeicher, baut sich bei jedem Tabwechsel neu aus der DB auf. Darunter
    eine zweite Tabelle mit dem Behältnis-Bedarf der Behältnisstrecke je LK
    (db.berechne_behaeltnis_bedarf(), Nutzerwunsch 25.09.)."""

    _ZEILEN = [
        ("ed", 1, "ED LK 1"),
        ("ed", 2, "ED LK 2"),
        ("ed", 3, "ED LK 3"),
        ("dk", 1, "DK LK 1"),
        ("dk", 2, "DK LK 2"),
        ("dk", 3, "DK LK 3"),
    ]

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn

        self.tabelle = QTableWidget(6, 6)
        self.tabelle.setHorizontalHeaderLabels(
            ["Art / Leistungsklasse", "Teilnehmer", "Trümmerfeld", "Flächensuche", "Behältnisstrecke", "Abteilungen"]
        )
        self.tabelle.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabelle.horizontalHeader().setStretchLastSection(True)
        self.tabelle.verticalHeader().setVisible(False)

        self.teilnehmer_label = QLabel()
        self.teilnehmer_label.setStyleSheet("font-weight: bold;")
        self.abteilungen_label = QLabel()
        self.abteilungen_label.setStyleSheet("font-weight: bold;")
        self.richter_label = QLabel()
        self.richter_label.setStyleSheet("font-weight: bold;")

        self.behaeltnis_tabelle = QTableWidget(4, len(BEHAELTNIS_BEDARF_SPALTEN))
        self.behaeltnis_tabelle.setHorizontalHeaderLabels(BEHAELTNIS_BEDARF_SPALTEN)
        self.behaeltnis_tabelle.setEditTriggers(QTableWidget.NoEditTriggers)
        self.behaeltnis_tabelle.horizontalHeader().setStretchLastSection(True)
        self.behaeltnis_tabelle.verticalHeader().setVisible(False)
        behaeltnis_hinweis = QLabel(BEHAELTNIS_BEDARF_HINWEIS)
        behaeltnis_hinweis.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Übersicht Teilnehmer und LK"))
        layout.addWidget(self.tabelle)
        layout.addWidget(self.teilnehmer_label)
        layout.addWidget(self.abteilungen_label)
        layout.addWidget(self.richter_label)
        layout.addSpacing(12)
        layout.addWidget(QLabel(BEHAELTNIS_BEDARF_TITEL))
        layout.addWidget(self.behaeltnis_tabelle)
        layout.addWidget(behaeltnis_hinweis)

        self.aktualisieren()

    def aktualisieren(self) -> None:
        """Berechnet die Übersicht aus der Datenbank neu und aktualisiert Tabelle und
        Summenzeilen."""
        daten = berechne_teilnehmer_lk_uebersicht(self.conn)

        for row, (art, lk, bezeichnung) in enumerate(self._ZEILEN):
            if art == "ed":
                lk_daten = daten["ed"][lk]
                werte = [
                    bezeichnung,
                    str(lk_daten["summe"]),
                    str(lk_daten["Trümmerfeld"]),
                    str(lk_daten["Flächensuche"]),
                    str(lk_daten["Behältnisstrecke"]),
                    str(lk_daten["abteilungen"]),
                ]
            else:
                lk_daten = daten["dk"][lk]
                werte = [
                    bezeichnung,
                    str(lk_daten["summe"]),
                    "–",
                    "–",
                    "–",
                    str(lk_daten["abteilungen"]),
                ]
            for col, wert in enumerate(werte):
                self.tabelle.setItem(row, col, QTableWidgetItem(wert))
        self.tabelle.resizeColumnsToContents()

        self.teilnehmer_label.setText(f"Teilnehmer gesamt: {daten['teilnehmer_gesamt']}")
        self.abteilungen_label.setText(f"Abteilungen gesamt: {daten['abteilungen_gesamt']}")
        self.richter_label.setText(f"Anzahl benötigter Richter: {daten['leistungsrichter_benoetigt']}")

        for row, zeile in enumerate(berechne_behaeltnis_bedarf(self.conn)):
            for col, wert in enumerate(behaeltnis_bedarf_zeilentexte(zeile)):
                self.behaeltnis_tabelle.setItem(row, col, QTableWidgetItem(wert))
        self.behaeltnis_tabelle.resizeColumnsToContents()


class ZeitplanTab(QWidget):
    """Zeitplan-Planung: beliebig viele Richter-Spuren, jede mit einer frei
    sortierbaren Abfolge aus Prüfungsblöcken und Pausen (siehe db.py, Abschnitt
    "Zeitplan"). "Automatisch verteilen…" erzeugt über db.automatische_zeitplan_verteilung
    einen ausgewogenen Erstvorschlag über alle Richter, der danach beliebig von Hand
    angepasst werden kann: Reihenfolge ändern, Dauer je Block überschreiben, Pausen an
    beliebiger Stelle einfügen, Blöcke zwischen Richtern verschieben (löschen bei dem
    einen, neu anlegen beim anderen). Start-/Endzeiten werden nicht gespeichert, sondern
    bei jedem Aufbau dieses Tabs aus der Zeitplan-Startzeit und den aktuell erfassten
    Teilnehmern neu berechnet (siehe db.berechne_zeitplan) - ein nachträglich geänderter
    Teilnehmerstand wirkt sich dadurch automatisch aus, ohne dass der Zeitplan von Hand
    nachgezogen werden müsste. Die Spalten zeigen dabei jeden einzelnen Teilnehmer mit
    seiner berechneten Zeit (nicht nur den zusammengefassten Prüfungsblock) - Verschieben/
    Bearbeiten/Entfernen wirkt trotzdem auf den gesamten zugrundeliegenden Block, da die
    Zuteilung einzelner Teilnehmer zu einem Block automatisch aus den aktuellen
    Anmeldedaten folgt und nicht einzeln von Hand festgelegt wird."""

    def __init__(self, conn, ablageort: _Ablageort | None = None, parent=None):
        super().__init__(parent)
        self.conn = conn
        # Wird ein `ablageort` übergeben (siehe HauptFenster), ist es dasselbe Objekt wie
        # im Tab "Export" - ein dort gewählter Ordner gilt dann auch hier als Standard-
        # Speicherort für "Zeitplan (PDF)…", und umgekehrt.
        self._ablageort = ablageort if ablageort is not None else _Ablageort(str(termine_ordner()))
        # ID des zuletzt verschobenen/bearbeiteten Eintrags - nach jedem Neuaufbau der
        # Spalten (aktualisieren()) wird die dazugehörige Zeile wieder markiert, damit
        # "Hoch"/"Runter" mehrfach hintereinander geklickt werden kann, ohne den Eintrag
        # jedes Mal erneut in der Liste auswählen zu müssen.
        self._markierter_eintrag_id: int | None = None
        self._richter_uebernahme_erfolgt = False  # siehe aktualisieren() (U8)

        veranstaltung = get_veranstaltung(conn) or {}

        self.zeitplan_start = QLineEdit(veranstaltung.get("zeitplan_start") or "09:00")
        self.zeitplan_start.setPlaceholderText("HH:MM")
        self.zeitplan_start.setMaximumWidth(70)
        start_speichern_btn = QPushButton("Startzeit speichern")
        start_speichern_btn.clicked.connect(self._start_speichern)

        self.standard_dauer = QSpinBox()
        self.standard_dauer.setRange(1, 240)
        self.standard_dauer.setValue(10)
        self.standard_dauer.setSuffix(" Min.")

        # UX-Test 02.10.2026, U2: Mindestabstand zwischen zwei Starts desselben Teams
        # (DK-Disziplinen); gilt für "Automatisch verteilen…" und die Überschneidungs-
        # Markierung, je Termin gespeichert.
        self.mindestabstand = QSpinBox()
        self.mindestabstand.setRange(0, 240)
        self.mindestabstand.setSuffix(" Min.")
        self.mindestabstand.setToolTip(
            "Mindestabstand zwischen zwei Starts desselben Teams (z. B. Dreikampf: Pause für "
            "den Hund und Wegezeit zwischen den Disziplinen)."
        )
        self.mindestabstand.setValue(dk_mindestabstand(veranstaltung))
        self.mindestabstand.valueChanged.connect(self._mindestabstand_speichern)

        richter_hinzufuegen_btn = QPushButton("Richter hinzufügen")
        richter_hinzufuegen_btn.clicked.connect(self._richter_hinzufuegen)

        self.verteilen_btn = verteilen_btn = QPushButton("Automatisch verteilen…")  # Attribut für die Demoprüfung
        verteilen_btn.clicked.connect(self._automatisch_verteilen)

        export_btn = QPushButton("Zeitplan (PDF)…")
        export_btn.clicked.connect(self._pdf_exportieren)

        kopf_zeile = QHBoxLayout()
        kopf_zeile.addWidget(QLabel("Zeitplan-Start (HH:MM):"))
        kopf_zeile.addWidget(self.zeitplan_start)
        kopf_zeile.addWidget(start_speichern_btn)
        kopf_zeile.addSpacing(16)
        kopf_zeile.addWidget(QLabel("Standard-Prüfungsdauer:"))
        kopf_zeile.addWidget(self.standard_dauer)
        kopf_zeile.addSpacing(16)
        kopf_zeile.addWidget(QLabel("Mindestabstand Team:"))
        kopf_zeile.addWidget(self.mindestabstand)
        kopf_zeile.addSpacing(16)
        kopf_zeile.addWidget(richter_hinzufuegen_btn)
        kopf_zeile.addWidget(verteilen_btn)
        kopf_zeile.addStretch()
        kopf_zeile.addWidget(export_btn)

        hinweis = QLabel(
            "Je Richter eine eigene Spalte mit frei sortierbarer Abfolge aus "
            "Prüfungsblöcken und Pausen. \"Automatisch verteilen…\" erstellt einen "
            "ausgewogenen Erstvorschlag über ALLE angelegten Richter (ersetzt "
            "dabei deren bisherigen Zeitplan) - die \"Standard-Prüfungsdauer\" ist dabei "
            "nur ein Vorschlagswert und lässt sich je Block einzeln überschreiben. "
            "Pausendauer und -platzierung sind ebenso frei wählbar wie die Reihenfolge "
            "insgesamt, unabhängig je Richter."
        )
        hinweis.setWordWrap(True)

        self._spalten_layout = QHBoxLayout()
        spalten_container = QWidget()
        spalten_container.setLayout(self._spalten_layout)
        self._scroll = QScrollArea()
        self._scroll.setWidget(spalten_container)
        self._scroll.setWidgetResizable(True)

        # Feste Seitenleiste "Offene Starts" (Nutzerwunsch 21.09.: "ich tue mir etwas
        # schwer, ob ich von den benötigten Starts auch schon alles erwischt habe,
        # nachdem ich scrollen muss" - zeigt je Art/Leistungsklasse/Disziplin mit
        # Teilnehmern, ob dafür bereits ein Prüfungsblock angelegt wurde. Bewusst
        # AUSSERHALB von self._scroll platziert, damit sie beim horizontalen Scrollen durch
        # viele Richter-Spalten sichtbar bleibt statt mit-zu-scrollen.
        self._offene_starts_box = QGroupBox("Offene Starts")
        self._offene_starts_box.setMinimumWidth(230)
        self._offene_starts_box.setMaximumWidth(280)
        self._offene_starts_label = QLabel("")
        self._offene_starts_label.setWordWrap(True)
        self._offene_starts_label.setTextFormat(Qt.RichText)
        self._offene_starts_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        offene_starts_scroll = QScrollArea()
        offene_starts_scroll.setWidget(self._offene_starts_label)
        offene_starts_scroll.setWidgetResizable(True)
        offene_starts_layout = QVBoxLayout(self._offene_starts_box)
        offene_starts_layout.addWidget(offene_starts_scroll)

        inhalt_zeile = QHBoxLayout()
        inhalt_zeile.addWidget(self._scroll, stretch=1)
        inhalt_zeile.addWidget(self._offene_starts_box)

        self.status_label = QLabel("")
        self.status_label.setTextFormat(Qt.PlainText)  # S-1: enthält Pfade/Namen
        self.status_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Zeitplan"))
        layout.addLayout(kopf_zeile)
        layout.addWidget(hinweis)
        layout.addLayout(inhalt_zeile, stretch=1)
        layout.addWidget(self.status_label)

        self.aktualisieren()

    # --- Aufbau --------------------------------------------------------------

    def showEvent(self, event) -> None:  # type: ignore[override]
        """UX-Test 02.10.2026, U8: beim ERSTEN Anzeigen des Reiters (nicht schon beim
        Öffnen des Termins - das soll die Datei nicht verändern) die Richter aus den
        Veranstaltungsdaten als Spalten anlegen, solange der Zeitplan noch leer ist. Nur
        einmal je geöffnetem Termin, damit bewusst gelöschte Richter nicht wieder auftauchen."""
        super().showEvent(event)
        if not self._richter_uebernahme_erfolgt:
            self._richter_uebernahme_erfolgt = True
            if zeitplan_richter_aus_veranstaltung_anlegen(self.conn):
                self.aktualisieren()

    def aktualisieren(self) -> None:
        """Baut die Richter-Spalten komplett neu aus dem aktuellen Datenbankstand auf -
        kein Zwischenspeicher, damit z.B. ein nachträglich geänderter Teilnehmerstand
        sofort in den neu berechneten Start-/Endzeiten sichtbar wird."""
        veranstaltung = get_veranstaltung(self.conn) or {}
        if not self.zeitplan_start.hasFocus():
            self.zeitplan_start.setText(veranstaltung.get("zeitplan_start") or "09:00")

        while self._spalten_layout.count():
            item = self._spalten_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        richter_liste = list_zeitplan_richter(self.conn)
        namen_je_richter = {r["id"]: r["name"] for r in richter_liste}
        konflikte = zeitplan_ueberschneidungen(self.conn) if richter_liste else []
        # (Block, Team) -> Erklärung für die rote Markierung der betroffenen Zeilen.
        self._konflikt_hinweise: dict[tuple, str] = {}
        abstand = dk_mindestabstand(veranstaltung)
        for k in konflikte:
            for eigene, andere in ((k["erste"], k["zweite"]), (k["zweite"], k["erste"])):
                art = "gleichzeitig" if k["gleichzeitig"] else f"weniger als {abstand} Min. Abstand"
                self._konflikt_hinweise[(eigene["eintrag_id"], k["teilnehmer"]["id"])] = (
                    f"Überschneidung ({art}): steht um {andere['start'].strftime('%H:%M')} auch bei "
                    f"{namen_je_richter.get(andere['richter_id'], '?')} ({andere['disziplin']})."
                )
        if not richter_liste:
            hinweis = QLabel("Noch keine Richter angelegt - über „Richter hinzufügen“ starten.")
            hinweis.setWordWrap(True)
            self._spalten_layout.addWidget(hinweis)
        else:
            zeilen_je_richter_id = {plan["richter_id"]: plan["zeilen"] for plan in berechne_zeitplan(self.conn)}
            for richter in richter_liste:
                self._spalten_layout.addWidget(
                    self._richter_spalte(richter, zeilen_je_richter_id.get(richter["id"], []))
                )
        self._spalten_layout.addStretch()
        self._offene_starts_aktualisieren(konflikte, namen_je_richter)

    def _mindestabstand_speichern(self, wert: int) -> None:
        _aktualisiere_veranstaltung_feld(self.conn, dk_mindestabstand=str(wert))
        self.aktualisieren()

    def _offene_starts_aktualisieren(self, konflikte: list | None = None, namen_je_richter: dict | None = None) -> None:
        """Baut den Text der Seitenleiste "Offene Starts" aus zeitplan_gruppen_status()
        neu auf: eine Zeile je Art/Leistungsklasse/Disziplin mit mindestens einem
        Teilnehmer, grün mit Haken wenn bereits ein Prüfungsblock dafür angelegt wurde,
        sonst rot/fett hervorgehoben mit "noch offen"."""
        status_liste = zeitplan_gruppen_status(self.conn)
        if not status_liste:
            self._offene_starts_label.setText("Noch keine Teilnehmer erfasst.")
            return
        zeilen = []
        ok = _farbe("ok").name()
        fehler = _farbe("fehler").name()
        # UX-Test 02.10.2026, U2: Überschneidungen oben und auffällig - vorher war die
        # Seitenleiste auch bei doppelt eingeplanten Teams komplett grün.
        if konflikte:
            namen_je_richter = namen_je_richter or {}
            # Je Team zusammengefasst (statt je Paar): alle betroffenen Starts mit Richter.
            je_team: dict[int, tuple[dict, set]] = {}
            for k in konflikte:
                team, starts = je_team.setdefault(k["teilnehmer"]["id"], (k["teilnehmer"], set()))
                for zeile in (k["erste"], k["zweite"]):
                    starts.add((zeile["start"], namen_je_richter.get(zeile["richter_id"], "?")))
            zeilen.append(
                f'<span style="color:{fehler}; font-weight:bold;">⚠ Überschneidungen ({len(je_team)} Team(s))</span>'
            )
            for team, starts in je_team.values():
                nr = team["startnummer"] if team["startnummer"] is not None else "–"
                liste = ", ".join(f"{start.strftime('%H:%M')} {name}" for start, name in sorted(starts))
                # Sicherheitsprüfung 03.10.2026, S-1: Namen/Bezeichnungen maskieren (Rich Text).
                zeilen.append(
                    f'<span style="color:{fehler};">Nr. {nr} {html.escape(str(team["nachname"]))}: '
                    f'{html.escape(liste)}</span>'
                )
            zeilen.append("")
        for eintrag in status_liste:
            bezeichnung = f"{eintrag['art']} LK {eintrag['stufe']} – {eintrag['disziplin']}"
            if eintrag["eingeplant"]:
                zeilen.append(
                    f'<span style="color:{ok};">✓ {html.escape(bezeichnung)} ({eintrag["anzahl"]} Teilnehmer)</span>'
                )
            else:
                zeilen.append(
                    f'<span style="color:{fehler}; font-weight:bold;">'
                    f'✗ {html.escape(bezeichnung)} ({eintrag["anzahl"]} Teilnehmer) – noch offen</span>'
                )
        self._offene_starts_label.setText("<br>".join(zeilen))

    def _richter_spalte(self, richter: dict, zeilen: list) -> QGroupBox:
        richter_id = richter["id"]
        box = QGroupBox(richter["name"])
        box.setMinimumWidth(300)

        links_btn = QPushButton("◀")
        links_btn.setToolTip("Spalte nach links verschieben")
        links_btn.clicked.connect(lambda: self._richter_verschieben(richter_id, -1))
        rechts_btn = QPushButton("▶")
        rechts_btn.setToolTip("Spalte nach rechts verschieben")
        rechts_btn.clicked.connect(lambda: self._richter_verschieben(richter_id, 1))
        umbenennen_btn = QPushButton("Umbenennen…")
        umbenennen_btn.clicked.connect(lambda: self._richter_umbenennen(richter_id))

        kopf_zeile = QHBoxLayout()
        kopf_zeile.addWidget(links_btn)
        kopf_zeile.addWidget(rechts_btn)
        kopf_zeile.addWidget(umbenennen_btn)
        kopf_zeile.addStretch()

        liste = QListWidget()
        markierte_zeile = None
        # UX-Test 02.10.2026, U9: je Prüfungsblock eine fette Kopfzeile, die Teilnehmer
        # eingerückt darunter - so ist sichtbar, dass "Hoch"/"Runter"/"Entfernen" den ganzen
        # Block bewegen.
        zeilen_je_block: dict[int, list] = {}
        for zeile in zeilen:
            if zeile["typ"] == "pruefung":
                zeilen_je_block.setdefault(zeile["eintrag_id"], []).append(zeile)
        letzter_block = None
        for zeile in zeilen:
            if zeile["typ"] == "pruefung" and zeile["eintrag_id"] != letzter_block:
                block = zeilen_je_block[zeile["eintrag_id"]]
                anzahl = sum(1 for z in block if z["teilnehmer"] is not None)
                umfang = (
                    f"{anzahl} Teilnehmer, {block[0]['start'].strftime('%H:%M')}–{block[-1]['ende'].strftime('%H:%M')}"
                    if anzahl else "keine Teilnehmer gemeldet"
                )
                hinweise = [
                    self._konflikt_hinweise.get((z["eintrag_id"], z["teilnehmer"]["id"]))
                    for z in block if z["teilnehmer"] is not None
                ]
                hinweise = [h for h in hinweise if h]
                warnung = "⚠ " if hinweise else ""
                kopf = QListWidgetItem(
                    f"▸ {warnung}{zeile['art']} LK {zeile['stufe']} – {zeile['disziplin']}  ({umfang})"
                )
                kopf.setData(Qt.UserRole, zeile["eintrag_id"])
                schrift = kopf.font()
                schrift.setBold(True)
                kopf.setFont(schrift)
                if hinweise:
                    # Verifikation U9: Überschneidung auch an der Kopfzeile sichtbar machen.
                    kopf.setForeground(_farbe("fehler"))
                    kopf.setToolTip(f"{len(hinweise)} Team(s) dieses Blocks mit Überschneidung.")
                liste.addItem(kopf)
                if markierte_zeile is None and zeile["eintrag_id"] == self._markierter_eintrag_id:
                    markierte_zeile = liste.count() - 1
            letzter_block = zeile["eintrag_id"] if zeile["typ"] == "pruefung" else None
            if zeile["typ"] == "pruefung" and zeile["teilnehmer"] is None:
                continue  # leerer Block: nur die Kopfzeile
            item = self._zeile_listenelement(zeile)
            liste.addItem(item)
            if markierte_zeile is None and self._markierter_eintrag_id is not None and zeile["eintrag_id"] == self._markierter_eintrag_id:
                markierte_zeile = liste.count() - 1
        if markierte_zeile is not None:
            liste.setCurrentRow(markierte_zeile)

        hoch_btn = QPushButton("Hoch")
        hoch_btn.clicked.connect(lambda: self._eintrag_verschieben(liste, -1))
        runter_btn = QPushButton("Runter")
        runter_btn.clicked.connect(lambda: self._eintrag_verschieben(liste, 1))
        bearbeiten_btn = QPushButton("Bearbeiten…")
        bearbeiten_btn.clicked.connect(lambda: self._eintrag_bearbeiten(liste))
        entfernen_btn = QPushButton("Entfernen")
        entfernen_btn.clicked.connect(lambda: self._eintrag_entfernen(liste))

        # UX-Test 02.10.2026, U9: Knöpfe in zwei statt fünf Zeilen - mehr Höhe für die Liste.
        eintrag_buttons_1 = QHBoxLayout()
        eintrag_buttons_1.addWidget(hoch_btn)
        eintrag_buttons_1.addWidget(runter_btn)
        eintrag_buttons_1.addWidget(bearbeiten_btn)
        eintrag_buttons_1.addWidget(entfernen_btn)
        eintrag_buttons_2 = QHBoxLayout()

        block_btn = QPushButton("Prüfungsblock hinzufügen…")
        block_btn.clicked.connect(lambda: self._pruefungsblock_hinzufuegen(richter_id))
        pause_btn = QPushButton("Pause hinzufügen…")
        pause_btn.clicked.connect(lambda: self._pause_hinzufuegen(richter_id, liste))
        loeschen_btn = QPushButton("Richter löschen")
        loeschen_btn.clicked.connect(lambda: self._richter_loeschen(richter_id, richter["name"]))

        layout = QVBoxLayout(box)
        layout.addLayout(kopf_zeile)
        layout.addWidget(liste, stretch=1)
        eintrag_buttons_2.addWidget(block_btn)
        eintrag_buttons_2.addWidget(pause_btn)
        layout.addLayout(eintrag_buttons_1)
        layout.addLayout(eintrag_buttons_2)
        layout.addWidget(loeschen_btn)
        return box

    def _zeile_listenelement(self, zeile: dict) -> QListWidgetItem:
        """Eine Listenzeile je einzelnem Teilnehmer (bzw. je Pause) - "Hoch"/"Runter"/
        "Bearbeiten…"/"Entfernen" wirken trotzdem auf den zugrundeliegenden Prüfungsblock
        als Ganzes (siehe zeile["eintrag_id"]), da einzelne Teilnehmer nicht manuell
        umverteilt werden, sondern sich automatisch aus Art/Leistungsklasse/Disziplin des
        Blocks ergeben."""
        zeit = f"{zeile['start'].strftime('%H:%M')}–{zeile['ende'].strftime('%H:%M')}"
        if zeile["typ"] == "pause":
            text = f"{zeit}  Pause: {zeile['bezeichnung']}"
        else:
            # Block-Angaben stehen in der Kopfzeile darüber (siehe _richter_spalte, U9).
            t = zeile["teilnehmer"]
            startnr = t["startnummer"] if t["startnummer"] is not None else "–"
            text = f"      {zeit}  Nr. {startnr}  {t['nachname']}, {t['vorname']} ({t['rufname_hund']})"
        hinweis = None
        if zeile["typ"] == "pruefung" and zeile.get("teilnehmer") is not None:
            hinweis = getattr(self, "_konflikt_hinweise", {}).get((zeile["eintrag_id"], zeile["teilnehmer"]["id"]))
        if hinweis:
            text = "⚠ " + text
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, zeile["eintrag_id"])
        if hinweis:
            # UX-Test 02.10.2026, U2: betroffene Zeilen rot, Tooltip erklärt die Überschneidung.
            item.setForeground(_farbe("fehler"))
            item.setToolTip(_klartext_tooltip(hinweis))  # S-1: enthält Richternamen
        return item

    # --- Aktionen: Richter -----------------------------------------------------

    def _start_speichern(self) -> None:
        text = self.zeitplan_start.text().strip()
        try:
            datetime.datetime.strptime(text, "%H:%M")
        except ValueError:
            QMessageBox.warning(
                self, "Ungültige Uhrzeit",
                "Bitte die Zeitplan-Startzeit im Format HH:MM angeben (z.B. 09:00).",
            )
            return
        _aktualisiere_veranstaltung_feld(self.conn, zeitplan_start=text)
        self.status_label.setText("Zeitplan-Startzeit gespeichert.")
        self.aktualisieren()

    def _richter_hinzufuegen(self) -> None:
        try:
            add_zeitplan_richter(self.conn)
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        self.aktualisieren()

    def _richter_umbenennen(self, richter_id: int) -> None:
        aktueller_name = next((r["name"] for r in list_zeitplan_richter(self.conn) if r["id"] == richter_id), "")
        name, ok = QInputDialog.getText(self, "Richter umbenennen", "Name:", text=aktueller_name)
        if not ok or not name.strip():
            return
        try:
            umbenennen_zeitplan_richter(self.conn, richter_id, name.strip())
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        self.aktualisieren()

    def _richter_verschieben(self, richter_id: int, richtung: int) -> None:
        try:
            verschiebe_zeitplan_richter(self.conn, richter_id, richtung)
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        self.aktualisieren()

    def _richter_loeschen(self, richter_id: int, name: str) -> None:
        antwort = QMessageBox.question(
            self, "Richter löschen",
            f"„{name}“ samt allen dort eingeplanten Prüfungsblöcken/Pausen löschen?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if antwort != QMessageBox.Yes:
            return
        try:
            loesche_zeitplan_richter(self.conn, richter_id)
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        self.aktualisieren()

    def _automatisch_verteilen(self) -> None:
        richter = list_zeitplan_richter(self.conn)
        if not richter:
            QMessageBox.information(
                self, "Keine Richter",
                "Bitte zuerst mindestens einen Richter anlegen.",
            )
            return
        # UX-Test 02.10.2026, U9: nur warnen, wenn es schon einen Plan gibt, der verloren ginge.
        if any(list_zeitplan_eintraege(self.conn, r["id"]) for r in richter):
            antwort = QMessageBox.question(
                self, "Automatisch verteilen",
                "Erstellt einen ausgewogenen Vorschlag über ALLE angelegten Richter "
                "und ERSETZT dabei deren bisherigen Zeitplan (bereits eingefügte Pausen und "
                "von Hand geänderte Reihenfolgen gehen dabei verloren). Fortfahren?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if antwort != QMessageBox.Yes:
                return
        try:
            automatische_zeitplan_verteilung(
                self.conn, [r["id"] for r in richter], standard_dauer_minuten=self.standard_dauer.value(),
            )
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        self.status_label.setText("Automatischer Zeitplan-Vorschlag erstellt.")
        self.aktualisieren()

    # --- Aktionen: Einträge ------------------------------------------------

    def _pruefungsblock_hinzufuegen(self, richter_id: int) -> None:
        dialog = PruefungsblockDialog(self, standard_dauer_minuten=self.standard_dauer.value())
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            add_zeitplan_pruefungsblock(self.conn, richter_id, **dialog.werte())
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        self.aktualisieren()

    def _pause_hinzufuegen(self, richter_id: int, liste: QListWidget | None = None) -> None:
        dialog = PauseDialog(self, neu=True)
        if dialog.exec() != QDialog.Accepted:
            return
        markiert = liste.currentItem() if liste is not None else None
        try:
            if dialog.fuer_alle.isChecked():
                wunsch = dialog.uhrzeit.text().strip()
                eingefuegt = add_zeitplan_pause_bei_allen(self.conn, wunsch, **dialog.werte())
                abweichend = [(name, zeit) for name, zeit in eingefuegt if zeit != wunsch]
                if abweichend:
                    # UX-Nachtest 03.10.2026, N3: "um 12:00 eingefügt" stimmte nicht, wenn ein
                    # Plan vorher endet oder ein Block noch läuft - tatsächliche Zeiten nennen.
                    QMessageBox.information(
                        self, "Pause eingefügt",
                        "Die Pause beginnt nicht überall um " + wunsch + ":\n\n"
                        + "\n".join(f"{name or 'Richter'}: {zeit} Uhr" for name, zeit in eingefuegt)
                        + "\n\nEin laufender Prüfungsblock wird nicht geteilt; endet der Plan eines "
                        "Richters vorher, steht die Pause an seinem Ende.",
                    )
                self.status_label.setText(f"Pause bei {len(eingefuegt)} Richter(n) eingefügt.")
            else:
                # UX-Test 02.10.2026, U9: nach der markierten Zeile statt immer am Ende.
                nach = markiert.data(Qt.UserRole) if markiert is not None else None
                self._markierter_eintrag_id = add_zeitplan_pause(
                    self.conn, richter_id, nach_eintrag_id=nach, **dialog.werte()
                )
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        self.aktualisieren()

    def _eintrag_verschieben(self, liste: QListWidget, richtung: int) -> None:
        item = liste.currentItem()
        if item is None:
            return
        eintrag_id = item.data(Qt.UserRole)
        try:
            verschiebe_zeitplan_eintrag(self.conn, eintrag_id, richtung)
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        # Nach dem Neuaufbau bleibt derselbe Block markiert, damit "Hoch"/"Runter" auch
        # mehrfach hintereinander geklickt werden kann, ohne ihn jedes Mal neu auszuwählen.
        self._markierter_eintrag_id = eintrag_id
        self.aktualisieren()

    def _aktueller_eintrag(self, eintrag_id: int) -> dict | None:
        for plan in berechne_zeitplan_bloecke(self.conn):
            for eintrag in plan["bloecke"]:
                if eintrag["id"] == eintrag_id:
                    return eintrag
        return None

    def _eintrag_bearbeiten(self, liste: QListWidget) -> None:
        item = liste.currentItem()
        if item is None:
            QMessageBox.information(self, "Kein Eintrag ausgewählt", "Bitte zuerst einen Eintrag in der Liste auswählen.")
            return
        eintrag_id = item.data(Qt.UserRole)
        eintrag = self._aktueller_eintrag(eintrag_id)
        if eintrag is None:
            return

        try:
            if eintrag["typ"] == "pause":
                dialog = PauseDialog(self, dauer_minuten=eintrag["dauer_minuten"], bezeichnung=eintrag["bezeichnung"] or "")
                if dialog.exec() != QDialog.Accepted:
                    return
                werte = dialog.werte()
                aktualisiere_zeitplan_eintrag(self.conn, eintrag_id, dauer_minuten=werte["dauer_minuten"], bezeichnung=werte["bezeichnung"] or "Pause")
            else:
                neue_dauer, ok = QInputDialog.getInt(
                    self, "Prüfungsblock bearbeiten", "Dauer je Teilnehmer (Minuten):",
                    value=eintrag["dauer_minuten"], minValue=1, maxValue=240,
                )
                if not ok:
                    return
                aktualisiere_zeitplan_eintrag(self.conn, eintrag_id, dauer_minuten=neue_dauer)
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        self._markierter_eintrag_id = eintrag_id
        self.aktualisieren()

    def _eintrag_entfernen(self, liste: QListWidget) -> None:
        item = liste.currentItem()
        if item is None:
            QMessageBox.information(self, "Kein Eintrag ausgewählt", "Bitte zuerst einen Eintrag in der Liste auswählen.")
            return
        try:
            loesche_zeitplan_eintrag(self.conn, item.data(Qt.UserRole))
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        self._markierter_eintrag_id = None
        self.aktualisieren()

    # --- Export --------------------------------------------------------------

    def _pdf_exportieren(self) -> None:
        _zeitplan_pdf_exportieren(self, self.conn, self._ablageort, self.status_label)


class ExportTab(QWidget):
    """PDF-Ausgabe: Ergebnislisten, Statistik und Bewertungsbögen (siehe pdf_export.py).
    Liest bei jedem Klick direkt den aktuellen Datenbankstand, hält also nichts vor."""

    def __init__(self, conn, termin_pfad: str | None = None, ablageort: _Ablageort | None = None, parent=None):
        super().__init__(parent)
        self.conn = conn
        # Ablageort für Exporte: standardmäßig derselbe Ordner wie die Termin-Datei
        # (damit die Ausgaben beim jeweiligen Termin liegen); wählt der Nutzer beim
        # Speichern einen anderen Ordner, wird dieser für die nächsten Exporte übernommen.
        # Wird ein `ablageort` übergeben (siehe HauptFenster), ist es dasselbe Objekt wie
        # im Tab "Zeitplan" - ein dort gewählter Ordner gilt dann auch hier als Standard,
        # und umgekehrt.
        self._ablageort = ablageort if ablageort is not None else _Ablageort(
            os.path.dirname(termin_pfad) if termin_pfad else str(termine_ordner())
        )

        # Nutzerwunsch 28.09.2026: ausfüllbares Anmeldeformular statt der bisherigen
        # Word-Vorlage (siehe pdf_export.erstelle_anmeldeformular_pdf).
        teilnehmerliste_btn = QPushButton("Teilnehmerliste speichern (CSV, für Excel)…")
        teilnehmerliste_btn.clicked.connect(self._teilnehmerliste_exportieren)
        anmeldeformular_btn = QPushButton("Anmeldeformular (PDF)…")
        anmeldeformular_btn.clicked.connect(self._anmeldeformular_exportieren)

        self.ergebnisliste_btn = ergebnisliste_btn = QPushButton("Ergebnisliste (PDF)…")  # Attribut für die Demoprüfung
        ergebnisliste_btn.clicked.connect(self._ergebnisliste_exportieren)

        leere_ergebnisliste_btn = QPushButton("Ergebnisliste zum Ausfüllen (PDF, leer)…")
        leere_ergebnisliste_btn.clicked.connect(self._leere_ergebnisliste_exportieren)

        etiketten_btn = QPushButton("Etiketten (PDF)…")
        etiketten_btn.clicked.connect(self._etiketten_exportieren)

        statistik_btn = QPushButton("Statistik (PDF)…")
        statistik_btn.clicked.connect(self._statistik_exportieren)

        pruefungsleitung_btn = QPushButton("Übersicht für Prüfungsleitung (PDF)…")
        pruefungsleitung_btn.clicked.connect(self._pruefungsleitung_exportieren)

        # Nutzerwunsch (21.09.): Chip-Nr. steht zwar schon auf jedem Bewertungsbogen und
        # in der Übersicht für Prüfungsleitung, Marco bekommt aber weiterhin Nachfragen
        # anderer Vereinsmitglieder danach - eigener, kompakter Export zum Abgleich am
        # Prüfungstag (siehe pdf_export.erstelle_chipnummernliste_pdf).
        chipliste_btn = QPushButton("Chipnummernliste (PDF)…")
        chipliste_btn.clicked.connect(self._chipliste_exportieren)

        leistungsrichter_btn = QPushButton("Richter-Bedarf (PDF)…")
        leistungsrichter_btn.clicked.connect(self._leistungsrichter_exportieren)

        zeitplan_btn = QPushButton("Zeitplan (PDF)…")
        zeitplan_btn.clicked.connect(self._zeitplan_exportieren)

        boegen_btn = QPushButton("Bewertungsbögen – alle Teilnehmer (PDF)…")
        boegen_btn.clicked.connect(self._bewertungsboegen_exportieren)

        ablageort_btn = QPushButton("Ablageort öffnen")
        ablageort_btn.clicked.connect(self._ablageort_oeffnen)

        hinweis = QLabel(
            "Das \"Anmeldeformular\" ist ein ausfüllbares PDF zum Verteilen an die "
            "Teilnehmer: Veranstalter, Verband, Meldestelle, Datum und die ankreuzbaren "
            "Prüfungen kommen aus den Veranstaltungsdaten im Reiter \"Verwaltung\" (dort "
            "zuerst die angebotenen Prüfungen anhaken). Ausgefüllt zurückgeschickte "
            "Formulare lassen sich im Reiter \"Formular-Import\" direkt einlesen. "
            "Die Bewertungsbögen entsprechen den bisherigen Serienbrief-Vorlagen (Layout, "
            "Verleitungs-Hinweise und Punktebänder je Leistungsklasse/Disziplin). Bereits "
            "eingetragene Ergebnisse werden vorausgefüllt; noch offene Felder bleiben zum "
            "handschriftlichen Ausfüllen vor Ort leer. Für EINEN einzelnen Teilnehmer geht "
            "es schneller direkt über den Button \"Bewertungsbogen (PDF)…\" im Reiter "
            "\"Teilnehmer\"; der Button hier erzeugt weiterhin eine Sammel-PDF und fragt "
            "vorher ab, welche Art/Leistungsklasse(n) enthalten sein sollen (Standard: "
            "alle) - praktisch, wenn beim doppelseitigen Druck sonst ein anderes Team auf "
            "der Rückseite landen würde. Die \"Ergebnisliste zum Ausfüllen\" "
            "ist ein reines Formular (Start-Nr./Name/Verein vorausgefüllt, Platz/Punkte/"
            "Wertnote leer) - z.B. um die Ergebnisse zunächst auf Papier festzuhalten und "
            "erst später in die Ergebniserfassung zu übertragen. Der Button \"Etiketten "
            "(PDF)…\" erzeugt die Ergebnisse als Etiketten zum Ausschneiden (zwei Zeilen je "
            "Teilnehmer, ohne Titel/Überschriften) zum Bedrucken von Klebe-/Etikettenpapier; "
            "Teilnehmer ohne vollständiges Ergebnis erhalten dabei ebenfalls ein Etikett, "
            "die Punktzahl-Felder bleiben dort zum Nachtragen leer. Das Feld „SH-R“ auf "
            "jedem Etikett bleibt bewusst leer - Platzhalter zum Abstempeln/Unterschreiben. "
            "Die \"Übersicht für Prüfungsleitung\" zeigt je Teilnehmer die Stammdaten und "
            "die Prüfungsgebühr (je nach Art ED/DK). Die Spalte \"bezahlt?\" kommt aus dem "
            "digitalen Bezahlt-Status, \"Impfpass gültig bis\" aus dem Stammdatenfeld "
            "\"Tollwutimpfung gültig bis\" (Teilnehmer-Dialog) - fehlt das Datum oder ist "
            "es zum Prüfungstag bereits abgelaufen, erscheint die Zelle rot. Die "
            "\"Chipnummernliste\" ist ein kompakter Export nur mit "
            "Start-Nr./Name/Hund/Chip-Nr., sortiert nach Startnummer - z.B. zum Abgleich "
            "an einer Chip-Scanner-Station am Prüfungstag. Der \"Richter-Bedarf\" errechnet aus der Teilnehmerzahl "
            "(1 ED = 1 Einheit, 1 DK = 3 Einheiten, max. 36 Einheiten je Richter) die "
            "benötigte Richterzahl. Die \"Statistik\" zeigt unterhalb der Prädikat-Matrix "
            "zusätzlich, wie viele der vollständig bewerteten Teilnehmer je Art/"
            "Leistungsklasse zum Prüfungstag noch Jugendliche (unter 18 Jahre) waren - "
            "Grundlage ist das Geburtsdatum im Teilnehmer-Dialog. Der \"Zeitplan\" fasst "
            "den im gleichnamigen Tab geplanten Ablauf je Richter (eine Seite je Richter) "
            "zusammen. "
            "Vereins-Nr., Prüfungsnummer, Richter 1-5, Prüfungsleiter sowie die "
            "Prüfungsgebühr ED/DK - die im Kopf der Statistik-PDF bzw. in der Übersicht "
            "für Prüfungsleitung erscheinen - werden jetzt im Reiter \"Verwaltung\" "
            "gepflegt."
        )
        hinweis.setWordWrap(True)

        self.status_label = QLabel("")
        self.status_label.setTextFormat(Qt.PlainText)  # S-1: enthält Pfade/Namen
        self.status_label.setWordWrap(True)

        button_zeile = QHBoxLayout()
        button_zeile.addWidget(ablageort_btn)
        button_zeile.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("PDF-Ausgabe"))
        layout.addWidget(anmeldeformular_btn)
        layout.addWidget(ergebnisliste_btn)
        layout.addWidget(leere_ergebnisliste_btn)
        layout.addWidget(etiketten_btn)
        layout.addWidget(statistik_btn)
        layout.addWidget(pruefungsleitung_btn)
        layout.addWidget(chipliste_btn)
        layout.addWidget(leistungsrichter_btn)
        layout.addWidget(zeitplan_btn)
        layout.addWidget(boegen_btn)
        layout.addWidget(teilnehmerliste_btn)
        layout.addLayout(button_zeile)
        # UX-Test 02.10.2026, U7: Statuszeile direkt unter den Knöpfen; der lange Erklärtext
        # scrollt, statt bei wenig Höhe mit der Statuszeile zu überlappen.
        layout.addWidget(self.status_label)
        hinweis_scroll = QScrollArea()
        hinweis_scroll.setWidget(hinweis)
        hinweis_scroll.setWidgetResizable(True)
        hinweis_scroll.setFrameShape(QScrollArea.NoFrame)
        layout.addWidget(hinweis_scroll, 1)

    def aktualisieren(self) -> None:
        pass  # kein Zwischenspeicher - wird bei jedem Export frisch aus der DB gelesen

    def _export_dateiname(self, praefix: str) -> str:
        return _export_dateiname(self.conn, praefix)

    def _speicherort_waehlen(self, titel: str, vorschlag: str) -> str | None:
        return _pdf_speicherort_waehlen(self, self._ablageort, titel, vorschlag)

    def _ablageort_oeffnen(self) -> None:
        if os.path.basename(os.path.dirname(self._ablageort.pfad)) == "Ausdrucke":
            try:
                os.makedirs(self._ablageort.pfad, exist_ok=True)
            except OSError:
                pass  # Meldung "existiert nicht" folgt direkt darunter
        if not os.path.isdir(self._ablageort.pfad):
            QMessageBox.warning(
                self,
                "Ordner nicht gefunden",
                f"Der Ablageort „{self._ablageort.pfad}“ existiert nicht (mehr).",
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._ablageort.pfad))

    def _export_fehler_anzeigen(self, exc: Exception) -> None:
        _pdf_export_fehler_anzeigen(self, exc)

    def _pdf_export_ausfuehren(self, titel: str, dateiname_praefix: str, export_fn, status_text) -> None:
        """Gemeinsamer Ablauf für die PDF-Export-Buttons dieses Tabs: Speicherort wählen,
        export_fn(pfad) aufrufen, Fehler behandeln, Status setzen - vorher wortgleich in
        >8 fast identischen Methoden dieser Klasse dupliziert. `export_fn` bekommt den
        gewählten Pfad und darf optional ein Ergebnis zurückgeben (z.B. eine Anzahl);
        `status_text` ist entweder ein fester String oder eine Funktion
        Ergebnis -> String, für Fälle wie "N Bewertungsbögen gespeichert"."""
        pfad = self._speicherort_waehlen(titel, self._export_dateiname(dateiname_praefix))
        if not pfad:
            return
        try:
            ergebnis = export_fn(pfad)
        except Exception as exc:
            self._export_fehler_anzeigen(exc)
            return
        text = status_text(ergebnis) if callable(status_text) else status_text
        self.status_label.setText(f"{text}: {_pfad_anzeige(pfad)}")
        _datei_gespeichert_melden(self, pfad, text)

    def _teilnehmerliste_exportieren(self) -> None:
        """Nutzerwunsch 02.10.2026 (UX-Test, N1): alle Teilnehmer als Excel-freundliche CSV."""
        try:
            os.makedirs(self._ablageort.pfad, exist_ok=True)
        except OSError:
            pass
        vorschlag = os.path.join(self._ablageort.pfad, self._export_dateiname("Teilnehmerliste").replace(".pdf", ".csv"))
        pfad, _ = QFileDialog.getSaveFileName(self, "Teilnehmerliste speichern", vorschlag, "CSV-Datei (*.csv)")
        if not pfad:
            return
        try:
            anzahl = exportiere_teilnehmer_csv(self.conn, pfad)
        except OSError as exc:
            QMessageBox.critical(self, "Speichern fehlgeschlagen", f"Die Teilnehmerliste konnte nicht gespeichert werden:\n\n{exc}")
            return
        self._ablageort.pfad = os.path.dirname(pfad)
        self.status_label.setText(f"Teilnehmerliste ({anzahl} Teilnehmer) gespeichert: {_pfad_anzeige(pfad)}")
        _datei_gespeichert_melden(self, pfad, "Teilnehmerliste gespeichert", datei_oeffnen_text="In Excel öffnen")

    def _anmeldeformular_exportieren(self) -> None:
        # Ohne angebotene Prüfungen gäbe es nichts anzukreuzen (erstelle_anmeldeformular_pdf
        # wirft dann ValueError) - Hinweis deshalb schon VOR dem Speichern-Dialog statt
        # danach als irreführende "Export fehlgeschlagen (Zielpfad ...)"-Meldung.
        if not angebotene_pruefungen(get_veranstaltung(self.conn)):
            QMessageBox.information(
                self, "Keine Prüfungen ausgewählt",
                "Bitte zuerst in den Veranstaltungsdaten (Reiter „Verwaltung“, Button "
                "„Veranstaltungsdaten bearbeiten…“) die angebotenen Prüfungen auswählen.",
            )
            return
        self._pdf_export_ausfuehren(
            "Anmeldeformular speichern", "Anmeldeformular",
            lambda pfad: pdf_export.erstelle_anmeldeformular_pdf(self.conn, pfad),
            "Anmeldeformular gespeichert",
        )

    def _ergebnisliste_exportieren(self) -> None:
        if not _stechen_offen_bestaetigen(self, self.conn):
            return
        self._pdf_export_ausfuehren(
            "Ergebnisliste speichern", "Ergebnisliste",
            lambda pfad: pdf_export.erstelle_ergebnisliste_pdf(self.conn, pfad),
            "Ergebnisliste gespeichert",
        )

    def _etiketten_exportieren(self) -> None:
        self._pdf_export_ausfuehren(
            "Etiketten speichern", "Etiketten",
            lambda pfad: pdf_export.erstelle_ergebnisliste_etiketten_pdf(self.conn, pfad),
            "Etiketten gespeichert",
        )

    def _leere_ergebnisliste_exportieren(self) -> None:
        self._pdf_export_ausfuehren(
            "Ergebnisliste zum Ausfüllen speichern", "Ergebnisliste_leer",
            lambda pfad: pdf_export.erstelle_leere_ergebnisliste_pdf(self.conn, pfad),
            "Ergebnisliste zum Ausfüllen gespeichert",
        )

    def _statistik_exportieren(self) -> None:
        self._pdf_export_ausfuehren(
            "Statistik speichern", "Statistik",
            lambda pfad: pdf_export.erstelle_statistik_pdf(self.conn, pfad),
            "Statistik gespeichert",
        )

    def _pruefungsleitung_exportieren(self) -> None:
        self._pdf_export_ausfuehren(
            "Übersicht für Prüfungsleitung speichern", "Uebersicht_Pruefungsleitung",
            lambda pfad: pdf_export.erstelle_pruefungsleitung_uebersicht_pdf(self.conn, pfad),
            "Übersicht für Prüfungsleitung gespeichert",
        )

    def _chipliste_exportieren(self) -> None:
        self._pdf_export_ausfuehren(
            "Chipnummernliste speichern", "Chipnummernliste",
            lambda pfad: pdf_export.erstelle_chipnummernliste_pdf(self.conn, pfad),
            "Chipnummernliste gespeichert",
        )

    def _leistungsrichter_exportieren(self) -> None:
        self._pdf_export_ausfuehren(
            "Richter-Bedarf speichern", "Richter_Bedarf",
            lambda pfad: pdf_export.erstelle_leistungsrichter_bedarf_pdf(self.conn, pfad),
            "Richter-Bedarf gespeichert",
        )

    def _zeitplan_exportieren(self) -> None:
        _zeitplan_pdf_exportieren(self, self.conn, self._ablageort, self.status_label)

    def _bewertungsboegen_exportieren(self) -> None:
        # Nutzerwunsch (21.09.): Auswahl, welche LK/Disziplin gedruckt werden sollen (siehe
        # BewertungsbogenAuswahlDialog oben) - Standard bleibt "alle" (Dialog startet mit
        # allen Einträgen angehakt), Abbrechen bricht den kompletten Export ab.
        auswahl_dialog = BewertungsbogenAuswahlDialog(self, alle_leistungsklassen(self.conn))
        if auswahl_dialog.exec() != QDialog.Accepted:
            return
        erlaubte_labels = auswahl_dialog.ausgewaehlte_labels()

        self._pdf_export_ausfuehren(
            "Bewertungsbögen speichern", "Bewertungsboegen",
            lambda pfad: pdf_export.erstelle_alle_bewertungsboegen_pdf(self.conn, pfad, erlaubte_labels=erlaubte_labels),
            lambda anzahl: f"{anzahl} Bewertungsbögen gespeichert",
        )


class VerwaltungTab(QWidget):
    """Verwaltungsdaten der Veranstaltung: Verein/Ort/Datum und Zusatzangaben (Vereins-Nr.,
    Prüfungsnummer, Richter 1-5, Prüfungsleiter, Prüfungsgebühr ED/DK). War früher
    Teil des Reiters "Export" (erster Button dort), steht aber inhaltlich für sich und wurde
    deshalb in einen eigenen Reiter verschoben (siehe HauptFenster._termin_setzen)."""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn

        veranstaltung_btn = QPushButton("Veranstaltungsdaten bearbeiten…")
        veranstaltung_btn.setObjectName("primaerButton")  # einzige Aktion dieses Reiters, siehe _QSS_TEMPLATE
        veranstaltung_btn.clicked.connect(self._veranstaltung_bearbeiten)

        hinweis = QLabel(
            "Über \"Veranstaltungsdaten bearbeiten…\" lassen sich Verein, Ort und Datum "
            "sowie Vereins-Nr., Prüfungsnummer, Richter 1-5, Prüfungsleiter und die "
            "Prüfungsgebühr ED/DK nachtragen bzw. ändern - sie erscheinen im Kopf der "
            "Statistik-PDF bzw. in der Übersicht für Prüfungsleitung (siehe Reiter "
            "\"Export\") und stehen oft erst kurz vor dem Prüfungstag fest. Verband, "
            "Meldestelle und die angebotenen Prüfungen bestimmen Kopf und Ankreuzfelder des "
            "Anmeldeformulars (Reiter \"Export\")."
        )
        hinweis.setWordWrap(True)

        self.status_label = QLabel("")
        self.status_label.setTextFormat(Qt.PlainText)  # S-1: enthält Pfade/Namen
        self.status_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Verwaltung"))
        layout.addWidget(veranstaltung_btn)
        layout.addWidget(hinweis)
        layout.addStretch()
        layout.addWidget(self.status_label)

    def aktualisieren(self) -> None:
        pass  # kein Zwischenspeicher - liest bei jedem Öffnen des Dialogs frisch aus der DB

    def _veranstaltung_bearbeiten(self) -> None:
        aktuell = get_veranstaltung(self.conn) or {}
        dialog = VeranstaltungsDialog(self, vorbelegung=aktuell, bearbeiten=True)
        if dialog.exec() != QDialog.Accepted:
            return
        # Über den gemeinsamen Helfer statt direkt set_veranstaltung, damit das vom
        # Zeitplan-Tab gepflegte Feld zeitplan_start dabei erhalten bleibt (dieser Dialog
        # hat dafür bewusst kein eigenes Feld, siehe ZeitplanTab).
        _aktualisiere_veranstaltung_feld(self.conn, **dialog.veranstaltung_werte())
        self.status_label.setText("Veranstaltungsdaten gespeichert.")


class DatensicherungTab(QWidget):
    """Export/Import ALLER Termine als ZIP-Datei (optional passwortgeschützt), unabhängig
    vom gerade im Hauptfenster geöffneten Termin - Datengrundlage ist immer der komplette
    Termine-Ordner (termine_ordner()), nicht die aktuelle Datenbankverbindung self.conn
    der übrigen Tabs. Deckt den bisher fehlenden Datensicherungsweg ab: bislang ließ sich
    der Termine-Ordner nur manuell (Datei-Explorer) sichern."""

    def __init__(self, parent=None, aktueller_pfad: str | None = None, conn=None):
        super().__init__(parent)
        # Nur für den Dateinamen-Vorschlag (K10): Prüfungsdatum und Verein des geöffneten Termins.
        self.conn = conn
        # Nur zur Erkennung eines Namenskonflikts mit dem GERADE GEÖFFNETEN Termin beim
        # Wiederherstellen (siehe _sicherung_wiederherstellen/_konflikt_abfragen) - ein
        # Überschreiben dieser Datei würde mit der noch offenen sqlite3.Connection des
        # Hauptfensters kollidieren.
        self._aktueller_pfad = aktueller_pfad

        hinweis = QLabel(
            "Sichert bzw. liest ALLE Termine aus dem gemeinsamen Termine-Ordner "
            f"(„{termine_ordner()}“) als eine einzige Sicherungsdatei (Endung .zip) - nicht "
            "nur den gerade geöffneten Termin. Das Passwort einer geschützten Sicherung "
            "am besten getrennt von der Sicherungsdatei aufbewahren (z. B. nicht auf "
            "demselben USB-Stick)."
        )
        hinweis.setWordWrap(True)

        erstellen_btn = QPushButton("Sicherung erstellen…")
        erstellen_btn.clicked.connect(self._sicherung_erstellen)

        wiederherstellen_btn = QPushButton("Sicherung wiederherstellen…")
        wiederherstellen_btn.clicked.connect(self._sicherung_wiederherstellen)

        self.status_label = QLabel("")
        self.status_label.setTextFormat(Qt.PlainText)  # S-1: enthält Pfade/Namen
        self.status_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Datensicherung"))
        layout.addWidget(hinweis)
        layout.addWidget(erstellen_btn)
        layout.addWidget(wiederherstellen_btn)
        layout.addStretch()
        layout.addWidget(self.status_label)

    def aktualisieren(self) -> None:
        pass  # kein Zwischenspeicher - liest bei jeder Aktion frisch den Termine-Ordner

    def _dateiname_vorschlag(self) -> str:
        """UX-Test 02.10.2026, K10: Name mit Prüfungsdatum und Verein des geöffneten Termins,
        damit man die Sicherung später einer Prüfung zuordnen kann, z. B.
        "SHS-Sicherung_2026-11-14_Hundefreunde-Testhausen_erstellt-2026-10-03.zip"."""
        heute = datetime.date.today().isoformat()
        veranstaltung = get_veranstaltung(self.conn) if self.conn is not None else None
        if not veranstaltung:
            return f"SHS-Sicherung_{heute}.zip"
        verein = veranstaltung["verein"] or ""
        for umlaut, ersatz in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"), ("ß", "ss")):
            verein = verein.replace(umlaut, ersatz)
        teile = [
            re.sub(r"[^0-9-]", "", veranstaltung["datum"] or ""),
            re.sub(r"[^A-Za-z0-9]+", "-", verein).strip("-")[:40].strip("-"),
        ]
        mitte = "_".join(t for t in teile if t)
        return f"SHS-Sicherung_{mitte + '_' if mitte else ''}erstellt-{heute}.zip"

    def _sicherung_erstellen(self) -> None:
        dialog = SicherungErstellenDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        passwort = dialog.passwort()

        vorschlag = os.path.join(os.path.expanduser("~"), self._dateiname_vorschlag())
        pfad, _ = QFileDialog.getSaveFileName(self, "Sicherung speichern", vorschlag, "ZIP-Datei (*.zip)")
        if not pfad:
            return

        try:
            anzahl = sicherung_erstellen(pfad, passwort=passwort)
        except ValueError as exc:
            QMessageBox.warning(self, "Sicherung nicht möglich", str(exc))
            return
        except Exception as exc:  # breiter Fänger, z.B. Zielordner nicht beschreibbar
            QMessageBox.critical(
                self, "Sicherung fehlgeschlagen",
                f"Die Sicherung konnte nicht erstellt werden:\n\n{exc}",
            )
            return

        zusatz = ", passwortgeschützt" if passwort else ""
        self.status_label.setText(f"Sicherung erstellt: {_pfad_anzeige(pfad)} ({anzahl} Termin(e){zusatz}).")
        # UX-Test U7 (Marco 03.10.2026): auch hier ein Meldungsfenster statt nur der Statuszeile.
        _datei_gespeichert_melden(
            self, pfad, f"Sicherung erstellt ({anzahl} Termin(e){zusatz})", datei_oeffnen_text=None
        )

    def _sicherung_wiederherstellen(self) -> None:
        zip_pfad, _ = QFileDialog.getOpenFileName(
            self, "Sicherung auswählen", os.path.expanduser("~"), "ZIP-Datei (*.zip)"
        )
        if not zip_pfad:
            return

        passwort: str | None = None
        namen: list[str] | None = None
        for versuch in range(3):
            try:
                namen = sicherung_inhalt(zip_pfad, passwort=passwort)
                break
            except PasswortFalschError:
                titel = "Passwort erforderlich" if passwort is None else "Passwort falsch"
                text = "Diese Sicherung ist passwortgeschützt. Bitte Passwort eingeben:" if passwort is None \
                    else "Das Passwort war falsch. Bitte erneut eingeben:"
                eingabe, ok = QInputDialog.getText(self, titel, text, QLineEdit.Password)
                if not ok:
                    return
                passwort = eingabe
            except ValueError as exc:
                QMessageBox.warning(self, "Sicherung nicht lesbar", str(exc))
                return
        if namen is None:
            QMessageBox.warning(self, "Passwort falsch", "Das Passwort war auch beim dritten Versuch falsch. Abgebrochen.")
            return

        ordner = termine_ordner()
        vorhandene = {p.name for p in ordner.glob("*.sqlite")}
        offener_name = os.path.basename(self._aktueller_pfad) if self._aktueller_pfad else None

        entscheidungen, uebersprungen = _wiederherstellungsziele_planen(
            namen, vorhandene, ordner,
            lambda name: self._konflikt_abfragen(name, ist_offener_termin=(name == offener_name)),
        )

        if not entscheidungen:
            self.status_label.setText("Wiederherstellen abgebrochen: kein Termin ausgewählt.")
            return

        try:
            wiederhergestellt = sicherung_wiederherstellen(zip_pfad, entscheidungen, passwort=passwort)
        except Exception as exc:
            QMessageBox.critical(
                self, "Wiederherstellen fehlgeschlagen",
                f"Die Sicherung konnte nicht wiederhergestellt werden:\n\n{exc}",
            )
            return

        hinweis_uebersprungen = f", {uebersprungen} übersprungen" if uebersprungen else ""
        self.status_label.setText(
            f"{len(wiederhergestellt)} Termin(e) wiederhergestellt{hinweis_uebersprungen}. "
            "Neue Termine erscheinen in der Terminübersicht beim nächsten „Anderen Termin öffnen…“."
        )

    def _konflikt_abfragen(self, dateiname: str, ist_offener_termin: bool = False) -> str:
        """Fragt bei einem Namenskonflikt (Termin existiert bereits) nach, wie verfahren
        werden soll. Gibt "ueberschreiben", "kopie" oder "ueberspringen" zurück. Ist
        `dateiname` gerade der im Hauptfenster geöffnete Termin, wird "Überschreiben" gar
        nicht erst angeboten - die noch offene Datenbankverbindung würde damit kollidieren
        (auf Windows vermutlich mit einer schwer verständlichen Dateisperren-Fehlermeldung)."""
        box = QMessageBox(self)
        box.setTextFormat(Qt.PlainText)  # S-1: Dateiname nie als HTML deuten
        box.setWindowTitle("Termin bereits vorhanden")
        text = f"Der Termin „{dateiname}“ ist im Termine-Ordner bereits vorhanden.\n\nWie soll damit verfahren werden?"
        if ist_offener_termin:
            text += (
                "\n\nDieser Termin ist gerade im Hauptfenster geöffnet und kann deshalb "
                "nicht überschrieben werden - bitte zuerst als Kopie importieren oder "
                "überspringen."
            )
        box.setText(text)
        ueberschreiben_btn = None if ist_offener_termin else box.addButton("Überschreiben", QMessageBox.AcceptRole)
        kopie_btn = box.addButton("Als Kopie importieren", QMessageBox.ActionRole)
        ueberspringen_btn = box.addButton("Überspringen", QMessageBox.RejectRole)
        box.setDefaultButton(ueberspringen_btn)
        box.exec()

        geklickt = box.clickedButton()
        if ueberschreiben_btn is not None and geklickt is ueberschreiben_btn:
            return "ueberschreiben"
        if geklickt is kopie_btn:
            return "kopie"
        return "ueberspringen"


#: Adresse der GitHub-Releases-Seite (zum Herunterladen einer neueren Version) bzw. der
#: dazugehörigen GitHub-API (zum automatischen Prüfen, ob es eine gibt) - siehe
#: VersionDialog._updates_pruefen. Seit das Repository öffentlich ist, funktioniert die
#: API-Abfrage OHNE Zugangsdaten (bei einem privaten Repository wäre dafür ein
#: angemeldetes GitHub-Konto mit Zugriff nötig gewesen - deshalb öffnete der Button
#: früher nur die Releases-Seite im Browser zum manuellen Nachschauen).
GITHUB_RELEASES_URL = "https://github.com/mbruver-source/SHS/releases"
GITHUB_LATEST_RELEASE_API_URL = "https://api.github.com/repos/mbruver-source/SHS/releases/latest"


def _version_tupel(text: str) -> tuple[int, int, int] | None:
    """Wandelt eine Versionsnummer der Form 'X.Y.Z' (optional mit führendem 'v', wie in
    GitHub-Tag-Namen üblich) in ein vergleichbares Tupel um - liefert None bei
    unerwartetem Format, statt eine Exception zu werfen (z. B. falls GitHub künftig
    einmal einen anders benannten Pre-Release als "latest" führt)."""
    text = text.strip().lstrip("vV")
    teile = text.split(".")
    if len(teile) != 3:
        return None
    try:
        a, b, c = (int(t) for t in teile)
    except ValueError:
        return None
    return (a, b, c)


def _neueste_version_pruefen() -> tuple[str | None, str | None]:
    """Fragt die öffentliche GitHub-Releases-API nach der neuesten veröffentlichten
    Version - liefert (Versionsnummer-Text ohne führendes 'v', None) bei Erfolg bzw.
    (None, verständlicher Fehlertext) bei jedem Problem (kein Internet - z. B. im
    Vereinsnetz am Prüfungstag typischerweise ohne Internetzugang -, GitHub nicht
    erreichbar, noch kein Release vorhanden usw.), damit VersionDialog._updates_pruefen
    dem Nutzer in jedem Fall eine verständliche Rückmeldung zeigen kann, statt dass das
    Programm an dieser Stelle abstürzt."""
    import json
    import urllib.error
    import urllib.request

    anfrage = urllib.request.Request(
        GITHUB_LATEST_RELEASE_API_URL, headers={"Accept": "application/vnd.github+json"}
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=5) as antwort:
            daten = json.loads(antwort.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None, "Es wurde noch kein Release veröffentlicht."
        return None, f"GitHub antwortete mit Fehler {exc.code}."
    except (urllib.error.URLError, OSError):
        return None, "Keine Verbindung zu GitHub möglich (kein Internetzugang?)."
    except (ValueError, KeyError):
        return None, "Die Antwort von GitHub konnte nicht gelesen werden."

    tag = str(daten.get("tag_name", "")).strip()
    if not tag:
        return None, "GitHub hat keine Versionsnummer geliefert."
    return tag.lstrip("vV"), None


class VersionDialog(QDialog):
    """Zeigt die aktuell laufende Programmversion (siehe VERSION oben, aus version.py -
    von bump_version.py bei jedem Release automatisch erzeugt) sowie einen Button, der
    per GitHub-API prüft, ob eine neuere Version veröffentlicht wurde (siehe
    _neueste_version_pruefen oben). Wird über den Version-Button im Hauptfenster
    geöffnet, direkt neben "Hilfe" (siehe HauptFenster._version_anzeigen)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Version")

        titel = QLabel("SHS Prüfungsprogramm")
        schrift = titel.font()
        schrift.setPointSize(schrift.pointSize() + 2)
        schrift.setBold(True)
        titel.setFont(schrift)

        version_zeile = QLabel(f"Version {VERSION}")
        version_zeile.setTextInteractionFlags(Qt.TextSelectableByMouse)

        hinweis = QLabel(
            "Der Button unten fragt beim Klick die GitHub-Releases-Seite dieses "
            "Programms ab und zeigt an, ob eine neuere Version verfügbar ist. Dafür "
            "wird kurz eine Internetverbindung gebraucht - ohne Internet (z. B. am "
            "Prüfungstag im Vereinsnetz) erscheint stattdessen ein entsprechender "
            "Hinweis."
        )
        hinweis.setWordWrap(True)

        self._updates_btn = QPushButton("Nach Updates suchen")
        self._updates_btn.clicked.connect(self._updates_pruefen)

        self._ergebnis_zeile = QLabel("")
        self._ergebnis_zeile.setWordWrap(True)
        # Reiner Text statt Qts automatischer Rich-Text-Erkennung - der angezeigte Text
        # stammt aus der GitHub-API (tag_name), ein dort manipulierter Rich-Text-artiger
        # Inhalt soll im Label keinesfalls als HTML interpretiert werden.
        self._ergebnis_zeile.setTextFormat(Qt.PlainText)
        self._ergebnis_zeile.hide()

        self._download_btn = QPushButton("Neue Version herunterladen (GitHub öffnen)")
        self._download_btn.clicked.connect(self._releases_seite_oeffnen)
        self._download_btn.hide()

        seite_link_btn = QPushButton("Releases-Seite im Browser öffnen")
        seite_link_btn.clicked.connect(self._releases_seite_oeffnen)

        schliessen_btn = QPushButton("Schließen")
        schliessen_btn.clicked.connect(self.accept)
        schliessen_zeile = QHBoxLayout()
        schliessen_zeile.addWidget(seite_link_btn)
        schliessen_zeile.addStretch()
        schliessen_zeile.addWidget(schliessen_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(titel)
        layout.addWidget(version_zeile)
        layout.addSpacing(8)
        layout.addWidget(hinweis)
        layout.addWidget(self._updates_btn)
        layout.addWidget(self._ergebnis_zeile)
        layout.addWidget(self._download_btn)
        layout.addSpacing(8)
        layout.addLayout(schliessen_zeile)

    def _updates_pruefen(self) -> None:
        # Button während der (kurzen, durch den Timeout in _neueste_version_pruefen auf
        # wenige Sekunden begrenzten) Abfrage deaktivieren und "wird geprüft" anzeigen,
        # mit einem expliziten processEvents() dazwischen - ohne das bliebe die
        # Oberfläche bis zur Antwort optisch eingefroren, da die Abfrage selbst
        # synchron/blockierend läuft (kein eigener Hintergrund-Thread, für eine einzelne
        # kurze Anfrage auf Klick hin bewusst nicht nötig).
        self._updates_btn.setEnabled(False)
        self._updates_btn.setText("Wird geprüft…")
        self._download_btn.hide()
        self._ergebnis_zeile.setText("")
        self._ergebnis_zeile.hide()
        QApplication.processEvents()

        neueste_version, fehler = _neueste_version_pruefen()

        self._updates_btn.setEnabled(True)
        self._updates_btn.setText("Nach Updates suchen")
        self._ergebnis_zeile.show()

        if fehler is not None:
            self._ergebnis_zeile.setText(fehler)
            return

        aktuell = _version_tupel(VERSION)
        neueste = _version_tupel(neueste_version)
        if aktuell is not None and neueste is not None and neueste > aktuell:
            self._ergebnis_zeile.setText(f"Neue Version {neueste_version} verfügbar (installiert: {VERSION}).")
            self._download_btn.show()
        else:
            self._ergebnis_zeile.setText("Du hast bereits die neueste Version.")

    def _releases_seite_oeffnen(self) -> None:
        QDesktopServices.openUrl(QUrl(GITHUB_RELEASES_URL))


_WM_ENDSESSION = 0x0016


class SitzungsendeFilter(QAbstractNativeEventFilter):
    """H-4 (dritte Verifikation 05.10.2026): Erkennt unter Windows ein abgebrochenes
    Abmelden/Herunterfahren (WM_ENDSESSION mit wParam=FALSE) und nimmt dann die Freigabe aus
    HauptFenster._sitzungsende_pruefen zurück. Qt meldet diesen Abbruch selbst nicht - ohne
    den Filter schlösse ein späteres Fenster-X ungeprüft, neue Eingaben gingen verloren."""

    def __init__(self, fenster: "HauptFenster"):
        super().__init__()
        self._fenster = fenster

    def nativeEventFilter(self, event_type, message):
        # Läuft für jede Windows-Nachricht: ein unerwarteter Fehler darf hier nie bis zur
        # Bedienung durchschlagen (PySide6 reicht ihn sonst an den gerade laufenden
        # Python-Code weiter) - im schlimmsten Fall bleibt eine Freigabe stehen.
        try:
            if bytes(event_type) == b"windows_generic_MSG" and int(message):
                # Erst hier importiert: ctypes.wintypes gibt es sinnvoll nur unter Windows
                # (die GUI-Tests der CI laufen unter Linux und importieren app.py).
                import ctypes.wintypes

                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == _WM_ENDSESSION and not msg.wParam:
                    self._fenster._beenden_freigegeben = False
        except Exception:
            pass
        return False, 0


def sitzungsende_einrichten(app: QApplication, fenster: "HauptFenster") -> None:
    """H-4: Verbindet das Beenden durch Windows/Setup mit dem Hauptfenster - Ablehnen ist
    nur in commitDataRequest möglich, closeEvent kommt erst nach der Zusage (siehe
    HauptFenster._sitzungsende_pruefen). Unter Windows zusätzlich SitzungsendeFilter für
    ein abgebrochenes Abmelden; die Referenz am Fenster hält den Filter am Leben."""
    app.commitDataRequest.connect(fenster._sitzungsende_pruefen)
    if sys.platform == "win32":
        fenster._sitzungsende_filter = SitzungsendeFilter(fenster)
        app.installNativeEventFilter(fenster._sitzungsende_filter)


class HauptFenster(ResponsiveSchriftMixin, QMainWindow):
    def __init__(self, conn, pfad: str, demo: bool = False):
        super().__init__()
        self.resize(900, 600)
        # Laufende Demoprüfung (desktop_demo.DemoTour) oder None.
        self._demo_tour = None
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
        # Widget auf der (hier ungenutzten, leeren) QMenuBar wurde zunächst versucht,
        # blieb aber unsichtbar, weil eine Menüleiste ohne eigene Menüeinträge auf
        # vielen Windows-Stilen auf Höhe 0 kollabiert. Die Kopfzeile hier ist Teil des
        # normalen zentralen Layouts und daher zuverlässig sichtbar.
        hilfe_btn = QPushButton("❓ Hilfe")
        hilfe_btn.clicked.connect(self._hilfe_anzeigen)

        version_btn = QPushButton(f"ℹ️ Version {VERSION}")
        version_btn.clicked.connect(self._version_anzeigen)

        self._tabs = QTabWidget()
        self._tabs.currentChanged.connect(self._tab_gewechselt)
        self._vorheriger_tab_index = 0

        self.wechseln_btn = QPushButton("Anderen Termin öffnen…")
        self.wechseln_btn.clicked.connect(self._termin_wechseln)

        # Marcos Wunsch 04.10.2026: geführte Demoprüfung mit erfundenen Daten (desktop_demo).
        self.demo_btn = QPushButton("🎓 Demoprüfung")
        self.demo_btn.setToolTip(
            "Spielt einmal einen kompletten Prüfungstag mit erfundenen Daten vor – "
            "deine Termine bleiben unverändert."
        )
        self.demo_btn.clicked.connect(self._demo_starten)

        kopf_zeile = QHBoxLayout()
        kopf_zeile.addStretch()
        kopf_zeile.addWidget(self.wechseln_btn)
        kopf_zeile.addWidget(version_btn)
        kopf_zeile.addWidget(self.demo_btn)
        kopf_zeile.addWidget(hilfe_btn)

        zentral = QWidget()
        zentral_layout = QVBoxLayout(zentral)
        zentral_layout.addLayout(kopf_zeile)
        zentral_layout.addWidget(self._tabs)
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
        # GUI-Tests (test_app_gui.py) nicht mehr auf.
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

    def _auswahl_menue_aufbauen(self, menue, eintraege: dict, aktiv: str, slot) -> dict[str, QAction]:
        actions: dict[str, QAction] = {}
        gruppe = QActionGroup(self)
        gruppe.setExclusive(True)
        gruppe.triggered.connect(slot)
        for schluessel, daten in eintraege.items():
            action = QAction(daten["anzeigename"], self)
            action.setCheckable(True)
            action.setChecked(schluessel == aktiv)
            action.setData(schluessel)
            menue.addAction(action)
            gruppe.addAction(action)
            actions[schluessel] = action
        return actions

    def _theme_aktion_ausgeloest(self, action: QAction) -> None:
        self._theme_wechseln(action.data())

    def _design_aktion_ausgeloest(self, action: QAction) -> None:
        self._design_wechseln(action.data())

    def _theme_wechseln(self, theme_name: str) -> None:
        _theme_speichern(theme_name)
        _darstellung_anwenden(QApplication.instance())
        self._farben_auffrischen()

    def _design_wechseln(self, design_name: str) -> None:
        _design_speichern(design_name)
        _darstellung_anwenden(QApplication.instance())
        self._farben_auffrischen()

    def _farben_auffrischen(self) -> None:
        """Färbt Tabelleninhalte nach einem Darstellungswechsel neu. Teilnehmer,
        Auswertung und Zeitplan laden dafür neu (keine ungespeicherten Eingaben dort);
        die Ergebniserfassung färbt nur um, damit ungespeicherte Punkte erhalten bleiben."""
        for tab in (self.teilnehmer_tab, self.auswertung_tab, self.zeitplan_tab):
            tab.aktualisieren()
        self.ergebnis_tab.farben_auffrischen()

    def _hilfe_anzeigen(self) -> None:
        HilfeDialog(self).exec()

    def _version_anzeigen(self) -> None:
        VersionDialog(self).exec()

    def _demo_starten(self) -> None:
        """Startet die Demoprüfung (desktop_demo.DemoTour) im Temp-Ordner; der geöffnete
        Termin wird am Ende wiederhergestellt."""
        if self._demo_tour is not None:
            self._demo_tour.panel_zeigen()
            return
        if not self._ungespeicherte_ergebnisse_klaeren("Trotzdem die Demoprüfung starten"):
            return
        DemoTour(fenster=self).starten()

    def _demo_sperren(self, aktiv: bool) -> None:
        """Während der Demo kein Terminwechsel und kein zweiter Demo-Start."""
        self.demo_btn.setEnabled(not aktiv)
        self.wechseln_btn.setEnabled(not aktiv)

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
        _ungespeicherte_ergebnisse_klaeren (Terminwechsel, Demoprüfung) - nachgefragt, ob trotzdem beendet (und diese Änderungen
        verworfen) oder das Schließen abgebrochen werden soll, damit die fehlerhafte
        Zeile noch korrigiert werden kann. Vorbelegter Standard ist "Nein" (nicht
        schließen) - anders als bei den übrigen Ja/Nein-Rückfragen in diesem Fenster, wo
        der übliche Fall (Speichern) vorbelegt ist, ist hier der sicherere Standard das
        NICHT versehentliche Verwerfen von Daten.

        H-4: Hat _sitzungsende_pruefen das Beenden durch Windows/Setup gerade erlaubt
        (Qt ruft closeEvent erst danach über quit() auf), wird ohne zweite Prüfung
        geschlossen - sonst kämen Warnung und Rückfrage doppelt, und ein "Nein" würde das
        bereits zugesagte Beenden blockieren. Wird das Abmelden doch abgebrochen, nimmt
        SitzungsendeFilter die Freigabe zurück."""
        freigegeben = self._beenden_freigegeben
        self._beenden_freigegeben = False
        if freigegeben:
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
        (rueckfrage_moeglich=False) wird bei Resten nicht gefragt, sondern abgelehnt."""
        # Laufende Demoprüfung zuerst beenden: sie stellt den echten Termin wieder her (die
        # Prüfung unten gilt dann ihm) bzw. schließt ihr eigenes Fenster samt Demo-Termin.
        tour = self._demo_tour
        if tour is not None:
            tour.beenden()
            if tour.eigenes_fenster:
                return True
        if self.ergebnis_tab.hat_ungespeicherte_aenderungen():
            self.ergebnis_tab.alle_speichern()
            if self.ergebnis_tab.hat_ungespeicherte_aenderungen():
                if not rueckfrage_moeglich:
                    return False
                antwort = QMessageBox.question(
                    self,
                    "Nicht alle Ergebnisse gespeichert",
                    "Einige Ergebnisse konnten nicht automatisch gespeichert werden (siehe "
                    "vorherige Meldung).\n\nProgramm trotzdem beenden und diese ungespeicherten "
                    "Änderungen verwerfen?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                return antwort == QMessageBox.Yes
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
        """Verbindet das Fenster mit einem (neuen oder anfänglichen) Termin: setzt Titel
        und baut alle Tabs für diesen Termin neu auf. `demo`: Termin der Demoprüfung -
        Titel mit "DEMO", Reiter "Datensicherung" gesperrt (arbeitet auf den echten
        Terminen)."""
        self.conn = conn
        self.pfad = pfad
        praefix = "DEMO – " if demo else ""
        self.setWindowTitle(f"{praefix}SHS Prüfungsprogramm – {pfad}")

        veranstaltung = get_veranstaltung(conn)
        if veranstaltung:
            self.setWindowTitle(
                f"{praefix}SHS Prüfungsprogramm – {veranstaltung['verein']} ({datum_anzeige(veranstaltung['datum'])})"
            )

        self._tabs.blockSignals(True)
        while self._tabs.count():
            self._tabs.removeTab(0)

        # Ein gemeinsames _Ablageort-Objekt für die Tabs "Zeitplan" und "Export", damit ein
        # in einem der beiden Tabs bewusst gewählter Speicherort auch im jeweils anderen
        # als neuer Standard gilt (siehe _Ablageort oben).
        # UX-Test 02.10.2026, U7: PDFs standardmäßig in "Ausdrucke/<Termin>" statt
        # zwischen den Termin-Dateien.
        ablageort = _Ablageort(_ausdrucke_ordner(pfad) if pfad else str(termine_ordner()))

        self.teilnehmer_tab = TeilnehmerTab(conn, pfad=pfad, ablageort=ablageort)
        self.formular_import_tab = FormularImportTab(conn)
        self.zeitplan_tab = ZeitplanTab(conn, ablageort)
        self.ergebnis_tab = ErgebnisTab(conn)
        self.auswertung_tab = AuswertungTab(conn, ablageort)
        self.teilnehmer_uebersicht_tab = TeilnehmerUebersichtTab(conn)
        self.verwaltung_tab = VerwaltungTab(conn)
        self.export_tab = ExportTab(conn, pfad, ablageort)
        # Anders als die übrigen Tabs NICHT an conn/pfad gebunden - arbeitet immer auf dem
        # gesamten Termine-Ordner (siehe DatensicherungTab oben), wird aber trotzdem hier
        # neu aufgebaut, damit sie sich wie die anderen Tabs beim Terminwechsel verhält.
        # aktueller_pfad wird nur mitgegeben, damit ein Wiederherstellen den gerade
        # geöffneten Termin nicht versehentlich überschreibt (siehe DatensicherungTab).
        self.datensicherung_tab = DatensicherungTab(aktueller_pfad=pfad, conn=conn)

        self._tabs.addTab(self.teilnehmer_tab, "Teilnehmer")
        self._tabs.addTab(self.formular_import_tab, "Formular-Import")
        self._tabs.addTab(self.zeitplan_tab, "Zeitplan")
        self._tabs.addTab(self.ergebnis_tab, "Ergebniserfassung")
        self._tabs.addTab(self.auswertung_tab, "Auswertung")
        self._tabs.addTab(self.teilnehmer_uebersicht_tab, "Übersicht")
        self._tabs.addTab(self.verwaltung_tab, "Verwaltung")
        self._tabs.addTab(self.export_tab, "Export")
        self._tabs.addTab(self.datensicherung_tab, "Datensicherung")
        if demo:
            index = self._tabs.indexOf(self.datensicherung_tab)
            self._tabs.setTabEnabled(index, False)
            self._tabs.setTabToolTip(
                index, "Während der Demoprüfung gesperrt – dieser Reiter arbeitet mit deinen echten Terminen."
            )
        self._tabs.blockSignals(False)

        self._vorheriger_tab_index = 0

    def _termin_wechseln(self) -> None:
        """Öffnet den Startdialog erneut, damit ohne Neustart der Anwendung zu einem
        anderen Termin gewechselt werden kann."""
        if not self._ungespeicherte_ergebnisse_klaeren("Trotzdem den Termin wechseln"):
            return

        dialog = StartDialog(self, aktueller_pfad=self.pfad)
        if dialog.exec() != QDialog.Accepted:
            return
        if dialog.demo_angefordert:
            DemoTour(fenster=self).starten()
            return
        if not dialog.pfad:
            return

        neue_verbindung = init_db(dialog.pfad)
        _fremdobjekte_melden(self)
        alte_verbindung = self.conn
        self._termin_setzen(neue_verbindung, dialog.pfad)
        alte_verbindung.close()

    def _ungespeicherte_ergebnisse_klaeren(self, verwerfen_frage: str) -> bool:
        """Vor dem Verlassen des Termins (Terminwechsel, Demoprüfung): bei ungespeicherten
        Ergebnissen nachfragen und ggf. speichern. False = Vorgang abbrechen."""
        if self.ergebnis_tab.hat_ungespeicherte_aenderungen():
            antwort = QMessageBox.question(
                self,
                "Ungespeicherte Ergebnisse",
                "In der Ergebniserfassung gibt es noch nicht gespeicherte Änderungen.\n\nJetzt speichern?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if antwort == QMessageBox.Yes:
                self.ergebnis_tab.alle_speichern()
                # Codeprüfung 22.09., G3: wie in closeEvent - alle_speichern() kann nicht
                # jede Zeile speichern (z. B. nur Suche ODER Anzeige eingetragen). Ohne
                # erneute Prüfung ging der Wechsel trotzdem weiter und die nicht
                # gespeicherte Zeile beim Neuaufbau der Tabs still verloren. Standard ist
                # deshalb "Nein" (Wechsel abbrechen, Zeile korrigieren).
                if self.ergebnis_tab.hat_ungespeicherte_aenderungen():
                    antwort = QMessageBox.question(
                        self,
                        "Nicht alle Ergebnisse gespeichert",
                        "Einige Ergebnisse konnten nicht gespeichert werden (siehe vorherige "
                        f"Meldung).\n\n{verwerfen_frage} und diese ungespeicherten "
                        "Änderungen verwerfen?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No,
                    )
                    if antwort != QMessageBox.Yes:
                        return False
        return True

    def _tab_gewechselt(self, index: int) -> None:
        # Beim Verlassen der Ergebniserfassung mit noch nicht gespeicherten Änderungen
        # nachfragen, statt sie stillschweigend zu verwerfen.
        voriges_widget = self._tabs.widget(self._vorheriger_tab_index)
        if voriges_widget is self.ergebnis_tab and self.ergebnis_tab.hat_ungespeicherte_aenderungen():
            antwort = QMessageBox.question(
                self,
                "Ungespeicherte Ergebnisse",
                "In der Ergebniserfassung gibt es noch nicht gespeicherte Änderungen.\n\nJetzt speichern?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if antwort == QMessageBox.Yes:
                self.ergebnis_tab.alle_speichern()

        self._vorheriger_tab_index = index
        widget = self._tabs.widget(index)
        if widget is self.ergebnis_tab and self.ergebnis_tab.hat_ungespeicherte_aenderungen():
            # Speichern wurde bewusst abgelehnt - neu laden, ohne diese Eingaben zu
            # verwerfen (z. B. damit ein inzwischen als "keine Teilnahme" markierter
            # Teilnehmer verschwindet).
            self.ergebnis_tab.aktualisieren_eingaben_erhalten()
            return
        if hasattr(widget, "aktualisieren"):
            widget.aktualisieren()


class StartDialog(ResponsiveSchriftMixin, QDialog):
    """Startdialog: Übersicht aller vorhandenen Termine aus dem Standard-Ordner (siehe
    db.termine_ordner) zum Öffnen/Löschen, sowie neuen Termin anlegen oder eine
    Termin-Datei an anderer Stelle öffnen (z. B. von einem USB-Stick)."""

    def __init__(self, parent=None, aktueller_pfad: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("SHS Prüfungsprogramm")
        self.resize(600, 380)
        self.pfad: str | None = None
        # "🎓 Demoprüfung" gewählt - der Aufrufer startet dann die Demo (desktop_demo).
        self.demo_angefordert = False
        self._termine: list = []
        # Nur gesetzt, wenn der Dialog aus einem bereits offenen Hauptfenster heraus
        # ("Anderen Termin öffnen…") gestartet wurde - siehe _termin_loeschen.
        self._aktueller_pfad = aktueller_pfad

        self.tabelle = QTableWidget(0, 4)
        self.tabelle.setHorizontalHeaderLabels(["Datum", "Verein", "Ort", "Teilnehmer"])
        self.tabelle.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabelle.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabelle.setSelectionMode(QTableWidget.SingleSelection)
        self.tabelle.itemSelectionChanged.connect(self._auswahl_geaendert)
        self.tabelle.itemDoubleClicked.connect(lambda _item: self._termin_oeffnen())
        self.tabelle.horizontalHeader().setStretchLastSection(True)

        neu_btn = QPushButton("Neuen Termin anlegen…")
        neu_btn.setObjectName("primaerButton")  # Haupt-Aktion des Startdialogs, siehe _QSS_TEMPLATE
        neu_btn.clicked.connect(self._neuer_termin)
        self.oeffnen_btn = QPushButton("Öffnen")
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

        # UX-Test 02.10.2026, U14: Laien fanden das Design "Hoher Kontrast" nicht.
        hinweis = QLabel(
            f"Neue Termine werden standardmäßig unter {termine_ordner()} gespeichert.\n"
            "Tipp: Schrift zu blass? Im Programm oben im Menü „Ansicht“ → „Hintergrund“ → "
            "„Hoher Kontrast“ wählen."
        )
        hinweis.setWordWrap(True)

        demo_btn = QPushButton("🎓 Demoprüfung")
        demo_btn.setToolTip(
            "Spielt einmal einen kompletten Prüfungstag mit erfundenen Daten vor – "
            "deine Termine bleiben unverändert."
        )
        demo_btn.clicked.connect(self._demo_waehlen)
        # Steht im Layout als erster Knopf - ohne das bekäme er beim Öffnen den Fokus und
        # würde als Standard-Knopf (blau, Enter) hervorgehoben statt "Neuen Termin anlegen…".
        demo_btn.setAutoDefault(False)
        kopf_zeile = QHBoxLayout()
        willkommen = QLabel("Willkommen im SHS Prüfungsprogramm – bitte einen Termin wählen oder neu anlegen:")
        willkommen.setWordWrap(True)
        kopf_zeile.addWidget(willkommen, 1)
        kopf_zeile.addWidget(demo_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(kopf_zeile)
        layout.addWidget(self.tabelle)
        layout.addLayout(button_zeile)
        layout.addWidget(hinweis)

        self.tabelle.setFocus()  # wie vor dem Demo-Knopf: Fokus zuerst auf der Terminliste
        self._aktualisieren()
        self._schriftgroesse_anwenden()

    def _aktualisieren(self) -> None:
        self._termine = liste_termine()
        self.tabelle.setRowCount(len(self._termine))
        for row, t in enumerate(self._termine):
            werte = [
                datum_anzeige(t.datum) or "?",
                t.verein if t.lesbar else f"{t.dateiname} (nicht lesbar)",
                t.ort or "",
                str(t.anzahl_teilnehmer) if t.lesbar else "",
            ]
            for col, wert in enumerate(werte):
                self.tabelle.setItem(row, col, QTableWidgetItem(wert))
        # Spaltenbreiten an den tatsächlichen Inhalt anpassen, damit z.B. lange
        # Vereinsnamen nicht abgeschnitten werden - danach bleiben die Spalten
        # weiterhin von Hand nachziehbar.
        self.tabelle.resizeColumnsToContents()
        self._auswahl_geaendert()

    def _ausgewaehlter_termin(self):
        zeile = self.tabelle.currentRow()
        if 0 <= zeile < len(self._termine):
            return self._termine[zeile]
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
            }
        dialog = VeranstaltungsDialog(self, vorbelegung=vorbelegung)
        if dialog.exec() != QDialog.Accepted:
            return
        pfad = dialog.pfad_feld.text().strip()

        if os.path.exists(pfad):
            antwort = QMessageBox.question(
                self,
                "Datei existiert bereits",
                f"Die Datei „{pfad}“ existiert bereits.\n\nStattdessen als bestehenden Termin öffnen?",
            )
            if antwort != QMessageBox.Yes:
                return
            self.pfad = pfad
            self.accept()
            return

        conn = init_db(pfad)
        set_veranstaltung(conn, **dialog.veranstaltung_werte())
        conn.close()
        self.pfad = pfad
        self.accept()

    def _termin_oeffnen(self) -> None:
        termin = self._ausgewaehlter_termin()
        if termin is None:
            return
        if not termin.lesbar:
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
        antwort = QMessageBox.question(
            self,
            "Termin löschen",
            f"Termin „{termin.verein or termin.dateiname}“ ({datum_anzeige(termin.datum) or '?'}) inklusive aller "
            f"Teilnehmer- und Ergebnisdaten unwiderruflich löschen?\n\nDatei: {termin.pfad}",
        )
        if antwort != QMessageBox.Yes:
            return
        try:
            os.remove(termin.pfad)
        except OSError as exc:
            QMessageBox.critical(self, "Löschen fehlgeschlagen", str(exc))
            return
        self._aktualisieren()

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
        if start.exec() != QDialog.Accepted:
            return None
        if start.demo_angefordert:
            demo_ohne_termin_ausfuehren(HauptFenster)
            continue
        return start.pfad or None


def main() -> int:
    # T1 (Marco 03.10.2026): "--selbsttest [protokoll]" prüft die gebündelte EXE ohne
    # Fenster (CI nach dem PyInstaller-Build und nach der Installation; auch zur
    # Fehlersuche beim Nutzer). Siehe selbsttest.py.
    if "--selbsttest" in sys.argv:
        from selbsttest import fuehre_selbsttest_aus

        position = sys.argv.index("--selbsttest")
        return fuehre_selbsttest_aus(sys.argv[position + 1] if len(sys.argv) > position + 1 else None)
    absturzprotokoll_einrichten(VERSION)
    app = QApplication(sys.argv)
    meldungsfenster_als_klartext()  # S-1: Namen in Meldungen nie als HTML
    deutsche_qt_texte_laden(app)
    _darstellung_anwenden(app)
    # Reste früherer Demoprüfungen (z. B. eine beim Beenden noch geöffnete PDF) wegräumen.
    demo_reste_aufraeumen()

    pfad = _startdialog_schleife()
    if not pfad:
        return 0

    conn = init_db(pfad)
    _fremdobjekte_melden(None)

    fenster = HauptFenster(conn, pfad)
    sitzungsende_einrichten(app, fenster)
    # UX-Test 02.10.2026, U12: maximiert starten - bei 900x600 blieb für Tabellen und die
    # Zeitplan-Spalten zu wenig Platz.
    fenster.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
