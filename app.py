"""
Desktop-Oberfläche (PySide6) des SHS-Prüfungsprogramms: Hauptfenster mit allen Reitern,
Startdialog, Versionsfenster und Programmstart (`main`). Überblick siehe Architektur.md.

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

import contextlib
import os
import sqlite3
import sys
import traceback

from PySide6.QtCore import QEvent, QFile, QItemSelectionModel, QRegularExpression, Qt
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
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from db import (
    ALLE_DISZIPLINEN,
    DISZIPLIN_SPALTEN,
    add_teilnehmer,
    alle_leistungsklassen,
    angebotene_pruefungen,
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
    sortierschluessel_text,
    termin_oeffnen,
    TerminNichtOeffenbar,
    TerminUngewoehnlichGross,
    GRUND_ZU_GROSS,
    pruefe_ergebnis_eingabe,
    set_veranstaltung,
    setze_bezahlt,
    setze_ergebnis_status,
    setze_keine_teilnahme,
    tausche_startnummern,
    teilnehmer_fehlende_pflichtangaben,
    teilnehmer_gegenstand_hinweis,
    termine_ordner,
    update_teilnehmer,
    vergebene_startnummern,
    fehlende_startnummern_vergeben,
    fehlende_startnummern_je_pruefung,
    pruefung_nach_kuerzel,
    pruefungs_kuerzel,
    ALLE_PRUEFUNGEN,
    startnummer_bereiche,
    startnummern_zuruecksetzen,
)
from db_import import (
    CSV_IMPORT_SPALTEN,
    importiere_anmeldeformular_pdf,
    importiere_teilnehmer_aus_csv,
    importiere_teilnehmer_aus_oma,
    importiere_teilnehmer_stammdaten,
    nicht_angebotene,
    schreibe_csv_vorlage,
)
import pdf_export
from shs_core import (
    ANZEIGE_MAX,
    SUCHE_MAX,
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
    _fehlertext,
    _klartext_fehler,
    fehler_protokollieren,
    fehlerfenster_zeigen,
    qt_meldungen_protokollieren,
    _Ablageort,
    absturzprotokoll_einrichten,
    fehlerfenster_einrichten,
    meldungsfenster_als_klartext,
    programmsymbol,
    _ausdrucke_ordner,
    _datei_gespeichert_melden,
    _db_fehler_anzeigen,
    _ja_nein,
    deutsche_qt_texte_laden,
    _DQ_SPALTE,
    _ERGEBNIS_SPALTEN_JE_DISZIPLIN,
    _ergebnis_spaltenbreiten_verteilen,
    _dateiname_teil,
    _fehler_anzeigen,
    _import_ordner_merken,
    _import_startordner,
    _NumerischSortierbaresItem,
    _pdf_exportieren,
    _ausfuehren,
    _wartecursor,
    _pfad_anzeige,
    _responsive_schriftgroesse,
    ResponsiveSchriftMixin,
    _STATUS_SPALTE,
    _zentrierte_zelle,
)
from desktop_dialoge import (
    HilfeDialog,
    StartnummerTauschenDialog,
    TeilnehmerDialog,
    TerminImportDialog,
    VeranstaltungsDialog,
)
from desktop_demo import DemoTour, demo_ohne_termin_ausfuehren, demo_reste_aufraeumen
from desktop_auswertung import AuswertungTab, ExportTab, TeilnehmerUebersichtTab
from desktop_zeitplan import ZeitplanTab
from desktop_verwaltung import DatensicherungTab, VerwaltungTab
from desktop_programm import VERSION, VersionDialog, laufkennung_setzen, sitzungsende_einrichten, zweitstart_pruefen


def _pruefung_bezeichnung(kuerzel: str) -> str:
    """Bezeichnung einer Prüfung wie im Filter Art/LK (db.leistungsklasse_label)."""
    pruefung = pruefung_nach_kuerzel(kuerzel)
    if pruefung is None:
        return kuerzel
    return leistungsklasse_label({"art": pruefung.art, "stufe": pruefung.stufe, "disziplin": pruefung.disziplin})


def _fehlende_startnummern_vergeben_mit_meldung(
    parent, conn, pruefung: str | None = None, bezeichnung: str | None = None
) -> None:
    """UX-Test 02.10.2026, U1: Sammelvergabe (db.fehlende_startnummern_vergeben) mit
    verständlicher Abschlussmeldung - wer hat eine Nummer bekommen, wer nicht und warum.
    Mit `pruefung`/`bezeichnung` nur für diese Prüfung (Filter Art/LK, Marco 09.10.2026)."""
    if not startnummer_bereiche(get_veranstaltung(conn)):
        QMessageBox.information(
            parent, "Keine Startnummern-Bereiche",
            "Bitte zuerst in den Veranstaltungsdaten (Reiter „Verwaltung“ → "
            "„Veranstaltungsdaten bearbeiten…“) je Prüfung einen Startnummern-Bereich "
            "eintragen, z. B. DK-LK 1: 1 bis 20.",
        )
        return
    try:
        ergebnis = fehlende_startnummern_vergeben(conn, pruefung)
    except sqlite3.Error as exc:
        _db_fehler_anzeigen(parent, exc)
        return

    def namen(liste):
        return [f"{t['vorname']} {t['nachname']} – {leistungsklasse_label(t)}" for t in liste]

    wo = f" in „{bezeichnung}“" if bezeichnung else ""
    _meldung_mit_listen(parent, "Startnummern vergeben", f"{len(ergebnis.vergeben)} Startnummer(n){wo} vergeben.", [
        ("Keine Nummer, weil für die Prüfung kein Bereich eingetragen ist:", namen(ergebnis.ohne_bereich)),
        ("Keine Nummer, weil der Bereich der Prüfung voll ist:", namen(ergebnis.bereich_voll)),
    ])


# Desktop-Prüfung 14.10.2026 (Teil 1 Nr. 4, Teil 5 Nr. 5): lange Namenslisten machten die
# Meldung höher als den Bildschirm (OK-Knopf nicht mehr sichtbar) - jetzt höchstens so viele
# Einträge je Liste, die vollständige Liste steht unter „Details“.
_MELDUNG_LISTE_MAX = 15


def _meldung_mit_listen(parent, titel: str, einleitung: str, abschnitte: list[tuple[str, list[str]]]) -> None:
    """Informationsmeldung aus `einleitung` und Abschnitten (Überschrift, Einträge); leere
    Abschnitte entfallen. Ist eine Liste länger als _MELDUNG_LISTE_MAX, wird sie gekürzt
    und die vollständige Fassung über „Details“ angeboten."""
    kurz = voll = einleitung
    gekuerzt = False
    for ueberschrift, eintraege in abschnitte:
        if not eintraege:
            continue
        zeilen = list(eintraege[:_MELDUNG_LISTE_MAX])
        if len(eintraege) > _MELDUNG_LISTE_MAX:
            zeilen.append(f"… und {len(eintraege) - _MELDUNG_LISTE_MAX} weitere (siehe „Details“)")
            gekuerzt = True
        kurz += f"\n\n{ueberschrift}\n" + "\n".join(zeilen)
        voll += f"\n\n{ueberschrift}\n" + "\n".join(eintraege)
    if not gekuerzt:
        QMessageBox.information(parent, titel, kurz)
        return
    box = QMessageBox(parent)
    box.setTextFormat(Qt.PlainText)
    box.setIcon(QMessageBox.Information)
    box.setWindowTitle(titel)
    box.setText(kurz)
    box.setDetailedText(voll)
    box.setStandardButtons(QMessageBox.Ok)
    _ausfuehren(box)


def _import_ergebnis_melden(parent, ergebnis, fehler_ueberschrift: str = "Zeile(n) übersprungen:") -> None:
    """Gemeinsame Abschlussmeldung für CSV-, OMA- und Anmeldeformular-Import (Teil 5 Nr. 5)."""
    _meldung_mit_listen(parent, "Import abgeschlossen", f"{ergebnis.importiert} Teilnehmer importiert.", [
        # UX-Nachtest 03.10.2026, N1: bereits vorhandene Meldungen werden nicht doppelt angelegt.
        (f"{len(ergebnis.uebersprungen)} Meldung(en) bereits vorhanden, nicht erneut angelegt:",
         ergebnis.uebersprungen),
        (f"{len(ergebnis.fehler)} {fehler_ueberschrift}", ergebnis.fehler),
        ("Hinweis:", ergebnis.hinweise),
    ])


_NICHTS_ZU_TAUSCHEN = ("Beide Teilnehmer haben noch keine Startnummer. Startnummern vergibst du "
                       "mit „Fehlende Startnummern vergeben…“ oder über „Bearbeiten…“.")


def _teilnehmerzahl(conn) -> int | None:
    try:
        return len(list_teilnehmer(conn))
    except sqlite3.Error:
        return None


def _startnummern_nach_import_anbieten(parent, conn) -> None:
    """UX-Test 02.10.2026, U1: Nach einem Import fehlen die Startnummern meist - direkt
    anbieten, sie gesammelt zu vergeben. Bewusst immer für alle Prüfungen, auch wenn im
    Reiter "Teilnehmer" ein Filter Art/LK gesetzt ist (Marco 09.10.2026)."""
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
    if _ja_nein(
        parent, "Startnummern fehlen",
        f"{len(ohne)} Teilnehmer haben noch keine Startnummer.\n\nJetzt „Fehlende "
        "Startnummern vergeben“? (Bereits vergebene Nummern bleiben unverändert.)",
        vorgabe_ja=True,
    ):
        _fehlende_startnummern_vergeben_mit_meldung(parent, conn)


def _import_db_fehler_melden(parent, exc: sqlite3.Error, conn=None, vorher: int | None = None,
                             einleitung: str = "Der Import wurde abgebrochen.") -> None:
    """Schreibfehler der Termin-Datei mitten in einem Import (Desktop-Prüfung 14.10.2026):
    die bis dahin übernommenen Teilnehmer bleiben gespeichert (Commit je Zeile). Mit `conn`
    und `vorher` (Teilnehmerzahl vor dem Import) nennt die Meldung, wie viele es sind (aus A4)."""
    nachher = _teilnehmerzahl(conn) if conn is not None and vorher is not None else None
    if nachher is not None:
        n = nachher - vorher
        anzahl = (f"{n} Teilnehmer wurde bis dahin übernommen und bleibt gespeichert" if n == 1 else
                  f"{n} Teilnehmer wurden bis dahin übernommen und bleiben gespeichert")
    else:
        anzahl = "Bereits übernommene Teilnehmer bleiben gespeichert"
    _db_fehler_anzeigen(
        parent, exc, f"{einleitung} {anzahl} - bitte die Teilnehmerliste prüfen, bevor die Datei "
        "erneut eingelesen wird.",
    )


def _teilnehmerliste_importieren(parent, conn) -> None:
    """CSV-/Excel-Teilnehmerliste einlesen - gemeinsam für den Reiter "Formular-Import" und
    den Knopf im Reiter "Teilnehmer" (UX-Test 02.10.2026, U10)."""
    pfad, _ = QFileDialog.getOpenFileName(parent, "Teilnehmerliste einlesen", _import_startordner(), "CSV- oder Textdatei (*.csv *.txt)")
    if not pfad:
        return
    _import_ordner_merken(pfad)
    vorher = _teilnehmerzahl(conn)
    try:
        ergebnis = importiere_teilnehmer_aus_csv(conn, pfad)
    except OSError as exc:
        QMessageBox.warning(parent, "Import fehlgeschlagen",
                            f"Die Datei konnte nicht gelesen werden.\n\n{_klartext_fehler(exc)}")
        return
    except sqlite3.Error as exc:
        _import_db_fehler_melden(parent, exc, conn, vorher)
        return
    if ergebnis.abbruch:
        QMessageBox.warning(parent, "Import nicht möglich", ergebnis.abbruch)
        return
    _import_ergebnis_melden(parent, ergebnis)
    if ergebnis.importiert:
        _startnummern_nach_import_anbieten(parent, conn)


class TeilnehmerTab(QWidget):
    def __init__(self, conn, parent=None, pfad: str | None = None, ablageort: _Ablageort | None = None):
        super().__init__(parent)
        self.conn = conn
        # Nur für TerminImportDialog: der eigene Dateipfad wird aus der Terminauswahl dort
        # ausgeschlossen, damit man nicht "aus sich selbst" importieren kann.
        self._pfad = pfad
        # Gemeinsamer Ablageort mit den übrigen Reitern (siehe _Ablageort) - der Direkt-Export-Button "Bewertungsbogen (PDF)…" unten nutzt denselben
        # zuletzt gewählten Ordner wie die übrigen PDF-Exporte.
        self._ablageort = ablageort if ablageort is not None else _Ablageort(
            os.path.dirname(pfad) if pfad else str(termine_ordner())
        )
        # Teilnehmer in DB-Reihenfolge (die Tabelle ist sortierbar - die ID einer Zeile steht
        # in deren UserRole); der Filter nutzt _teilnehmer_je_id.
        self._teilnehmer_je_zeile: list[dict] = []

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

        # UX-Test 02.10.2026, U1: Startnummern für alle ohne Nummer auf einmal vergeben -
        # seit 09.10.2026 bei gesetztem Filter Art/LK nur für diese Prüfung.
        self.vergeben_btn = vergeben_btn = QPushButton("Fehlende Startnummern vergeben…")
        vergeben_btn.clicked.connect(self._fehlende_startnummern_vergeben)

        # Marco 09.10.2026: alle Startnummern auf einmal entfernen (bei gesetztem Filter
        # Art/LK nur die dieser Prüfung), z. B. um sie nach geänderten Bereichen mit
        # "Fehlende Startnummern vergeben…" neu zu vergeben.
        self.zuruecksetzen_btn = QPushButton("Alle Startnummern zurücksetzen…")
        self.zuruecksetzen_btn.clicked.connect(self._alle_startnummern_zuruecksetzen)

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
        for knopf in (self.tauschen_btn, vergeben_btn, self.zuruecksetzen_btn, import_btn, liste_btn):
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
        # Marco 09.10.2026: immer aktueller Hinweis, in welchen Prüfungen noch Teilnehmer
        # ohne Startnummer sind (unabhängig vom Filter, ohne "keine Teilnahme").
        self.startnummern_hinweis = QLabel("")
        self.startnummern_hinweis.setTextFormat(Qt.PlainText)
        self.startnummern_hinweis.setWordWrap(True)
        layout.addWidget(self.startnummern_hinweis)
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
            angebotene={p.kuerzel for p in angebotene_pruefungen(get_veranstaltung(self.conn))},
            stichtag=(get_veranstaltung(self.conn) or {}).get("datum"),
            # Gespeichert wird im Dialog vor dem Schließen - scheitert es, bleiben die
            # Eingaben stehen (Desktop-Prüfung 14.10.2026, Teil 2 Nr. 1).
            speichern=lambda d: add_teilnehmer(self.conn, d.ergebnis()),
        )
        if _ausfuehren(dialog) == QDialog.Accepted:
            self.aktualisieren()

    def _teilnehmer_bearbeiten(self) -> None:
        teilnehmer_id = self._ausgewaehlte_id()
        if teilnehmer_id is None:
            return
        aktuelle_daten = get_teilnehmer(self.conn, teilnehmer_id)
        if aktuelle_daten is None:  # inzwischen gelöscht
            self.aktualisieren()
            return
        dialog = TeilnehmerDialog(
            self,
            vorhandener=aktuelle_daten,
            vergebene_nummern=vergebene_startnummern(self.conn, ausser_teilnehmer_id=teilnehmer_id),
            namen_je_startnummer=self._namen_je_startnummer(ausser_teilnehmer_id=teilnehmer_id),
            bereiche=startnummer_bereiche(get_veranstaltung(self.conn)),
            angebotene={p.kuerzel for p in angebotene_pruefungen(get_veranstaltung(self.conn))},
            stichtag=(get_veranstaltung(self.conn) or {}).get("datum"),
            speichern=lambda d: update_teilnehmer(self.conn, teilnehmer_id, d.ergebnis()),
        )
        if _ausfuehren(dialog) == QDialog.Accepted:
            self.aktualisieren()

    def _startnummer_tauschen(self) -> None:
        ids = self._ausgewaehlte_ids()
        if len(ids) == 2:
            self._zwei_markierte_tauschen(*ids)
            return
        teilnehmer_id = self._ausgewaehlte_id()
        if teilnehmer_id is None:
            return
        aktuell = get_teilnehmer(self.conn, teilnehmer_id)
        if aktuell is None:  # inzwischen gelöscht
            self.aktualisieren()
            return
        andere = [t for t in list_teilnehmer(self.conn) if t["id"] != teilnehmer_id]
        if not andere:
            return
        dialog = StartnummerTauschenDialog(self, aktuell, andere)
        if _ausfuehren(dialog) == QDialog.Accepted:
            partner_id = dialog.ausgewaehlte_partner_id()
            partner = next((t for t in andere if t["id"] == partner_id), None)
            if partner is not None and aktuell["startnummer"] is None and partner["startnummer"] is None:
                # UX-Test 02.10.2026, U1: vorher schloss der Dialog ohne Wirkung und Hinweis.
                QMessageBox.information(self, "Nichts zu tauschen", _NICHTS_ZU_TAUSCHEN)
                return
            if partner_id is not None:
                try:
                    tausche_startnummern(self.conn, teilnehmer_id, partner_id)
                except sqlite3.IntegrityError as exc:
                    _fehler_anzeigen(self, exc)
                    return
                except sqlite3.Error as exc:
                    _db_fehler_anzeigen(self, exc)
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
            QMessageBox.information(self, "Nichts zu tauschen", _NICHTS_ZU_TAUSCHEN)
            return

        def beschreibung(t):
            nummer = f"Nr. {t['startnummer']}" if t["startnummer"] is not None else "ohne Nummer"
            return f"„{t['nachname']}, {t['vorname']}“ ({nummer})"

        if not _ja_nein(
            self, "Startnummern tauschen",
            f"Startnummern von {beschreibung(a)} und {beschreibung(b)} tauschen?",
        ):
            return
        try:
            tausche_startnummern(self.conn, id_a, id_b)
        except sqlite3.IntegrityError as exc:
            _fehler_anzeigen(self, exc)
            return
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        self.aktualisieren()

    def _gefilterte_pruefung(self) -> tuple[str | None, str | None]:
        """(Kürzel, Bezeichnung) der im Filter Art/LK gewählten Prüfung oder (None, None)
        bei "Alle" - schränkt Zurücksetzen und Vergabe ein (Marco 09.10.2026). Die
        Zuordnung läuft über die feste Prüfungsliste; passt keine Prüfung, kommt
        (None, Filtertext) zurück und die Aufrufer brechen ab, statt still auf "Alle"
        auszuweichen (Verifikation A)."""
        filter_wert = self.filter_combo.currentText()
        if filter_wert in ("Alle", ""):
            return None, None
        for pruefung in ALLE_PRUEFUNGEN:
            if _pruefung_bezeichnung(pruefung.kuerzel) == filter_wert:
                return pruefung.kuerzel, filter_wert
        return None, filter_wert

    def _gefilterte_pruefung_oder_meldung(self) -> tuple[str | None, str | None] | None:
        pruefung, bezeichnung = self._gefilterte_pruefung()
        if bezeichnung and pruefung is None:
            QMessageBox.warning(
                self, "Unbekannte Prüfung",
                f"Zum Filter „{bezeichnung}“ gehört keine bekannte Prüfung. Bitte den Filter "
                "Art/LK auf „Alle“ oder eine andere Prüfung stellen.",
            )
            return None
        return pruefung, bezeichnung

    def _startnummern_hinweis_aktualisieren(self) -> None:
        fehlend = [
            f"{_pruefung_bezeichnung(kuerzel)} ({anzahl})"
            for kuerzel, anzahl in fehlende_startnummern_je_pruefung(self.conn)
        ]
        self.startnummern_hinweis.setText(
            f"Ohne Startnummer: {', '.join(fehlend)}" if fehlend else ""
        )
        self.startnummern_hinweis.setVisible(bool(fehlend))

    def _fehlende_startnummern_vergeben(self) -> None:
        filter_pruefung = self._gefilterte_pruefung_oder_meldung()
        if filter_pruefung is None:
            return
        _fehlende_startnummern_vergeben_mit_meldung(self, self.conn, *filter_pruefung)
        self.aktualisieren()

    def _alle_startnummern_zuruecksetzen(self) -> None:
        filter_pruefung = self._gefilterte_pruefung_oder_meldung()
        if filter_pruefung is None:
            return
        pruefung, bezeichnung = filter_pruefung
        anzahl = sum(
            1 for t in self._teilnehmer_je_id.values()
            if t["startnummer"] is not None
            and (pruefung is None or pruefungs_kuerzel(t["art"], t["stufe"], t["disziplin"]) == pruefung)
        )
        wo = f" in „{bezeichnung}“" if bezeichnung else ""
        if not anzahl:
            QMessageBox.information(
                self, "Startnummern zurücksetzen", f"Es ist noch keine Startnummer{wo} vergeben."
            )
            return
        wer = f"der Teilnehmer in „{bezeichnung}“" if bezeichnung else "ALLER Teilnehmer"
        if not _ja_nein(
            self, "Startnummern zurücksetzen",
            f"Die Startnummern {wer} ({anzahl}) werden entfernt. Neu vergeben "
            "kannst du sie danach mit „Fehlende Startnummern vergeben…“.\n\n"
            "Achtung: Die Reihenfolge im Zeitplan richtet sich nach den Startnummern, und "
            "im Web erfasste Ergebnisse werden beim Zurückholen über die Startnummer "
            "zugeordnet. Nach einer Veröffentlichung im Web daher nicht mehr umnummerieren.\n\n"
            "Fortfahren?",
        ):
            return
        try:
            entfernt = startnummern_zuruecksetzen(self.conn, pruefung)
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        self.aktualisieren()
        self.status_label.setText(f"{entfernt} Startnummer(n){wo} zurückgesetzt.")

    def _teilnehmerliste_importieren(self) -> None:
        _teilnehmerliste_importieren(self, self.conn)
        self.aktualisieren()

    def _aus_anderem_termin_importieren(self) -> None:
        dialog = TerminImportDialog(self, self._pfad)
        try:
            if _ausfuehren(dialog) == QDialog.Accepted:
                quelle = dialog.quelle_conn()
                ausgewaehlt = dialog.ausgewaehlte_ids()
                if quelle is None:
                    # Rückfallebene: Der Dialog sperrt OK bereits, wenn die Quelle nicht
                    # gelesen werden konnte - statt kommentarlos abzubrechen, trotzdem
                    # informieren.
                    QMessageBox.warning(
                        self, "Import nicht möglich",
                        "Die gewählte Quell-Termin-Datei konnte nicht geöffnet werden."
                    )
                elif ausgewaehlt:
                    vorher = _teilnehmerzahl(self.conn)
                    try:
                        # Vor dem Import lesen: so gilt ein Lesefehler hier noch als Abbruch.
                        uebernommen = [t for t in (get_teilnehmer(quelle, i) for i in ausgewaehlt) if t is not None]
                        anzahl = importiere_teilnehmer_stammdaten(quelle, self.conn, ausgewaehlt)
                    except sqlite3.Error as exc:
                        # Lese- oder Schreibfehler mitten im Import: bereits übernommene
                        # Teilnehmer bleiben (Commit je Teilnehmer) und sind nach dem
                        # Aktualisieren sichtbar.
                        self.aktualisieren()
                        _import_db_fehler_melden(
                            self, exc, self.conn, vorher,
                            einleitung="Der Import aus dem anderen Termin wurde abgebrochen.",
                        )
                        return
                    self.aktualisieren()
                    # Teil 1 Nr. 6 (Marcos Entscheidung): übernehmen, aber auf hier nicht
                    # angebotene Prüfungen hinweisen.
                    try:
                        fremde = nicht_angebotene(self.conn, uebernommen)
                    except sqlite3.Error:
                        fremde = []  # nur der Hinweis entfällt, der Import ist gespeichert
                    _meldung_mit_listen(self, "Import abgeschlossen", f"{anzahl} Teilnehmer importiert.", [
                        (f"{len(fremde)} Teilnehmer in hier nicht angebotenen Prüfungen – bitte die "
                         "Leistungsklasse anpassen („Bearbeiten…“) oder die Prüfung in den "
                         "Veranstaltungsdaten anbieten:",
                         [f"{t['nachname']}, {t['vorname']} – {leistungsklasse_label(t)}" for t in fremde]),
                    ])
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
        vorschlag = f"Bewertungsbogen_{start_teil}_{_dateiname_teil(aktuell['nachname'])}.pdf"
        _pdf_exportieren(self, self._ablageort, self.status_label, "Bewertungsbogen speichern", vorschlag,
                         lambda pfad: pdf_export.erstelle_bewertungsbogen_pdf(self.conn, teilnehmer_id, pfad),
                         "Bewertungsbogen gespeichert")

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
        # Desktop-Prüfung 14.10.2026 (Teil 1 Nr. 3): Vorgabe „Nein“ - sonst löschte
        # Strg+A, „Löschen“, Enter alle sichtbaren Teilnehmer.
        if _ja_nein(self, "Teilnehmer löschen", frage):
            try:
                for t in teilnehmer:
                    delete_teilnehmer(self.conn, t["id"])
            except sqlite3.Error as exc:
                _db_fehler_anzeigen(self, exc, "Nicht alle Teilnehmer konnten gelöscht werden.")
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
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
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
            if not _ja_nein(
                self,
                "Keine Teilnahme",
                f"{wer} bereits Ergebnisse erfasst. Sie bleiben gespeichert, "
                f"werden aber nicht mehr gewertet, solange {subjekt} als "
                "„keine Teilnahme“ markiert ist.\n\nTrotzdem markieren?",
            ):
                return
        try:
            for t in aktuelle:
                setze_keine_teilnahme(self.conn, t["id"], neu_keine_teilnahme)
        except sqlite3.IntegrityError as exc:
            _fehler_anzeigen(self, exc)
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
        self.aktualisieren()

    def aktualisieren(self) -> None:
        gemerkte_auswahl = set(self._ausgewaehlte_ids())
        self.tabelle.clearSelection()
        teilnehmer = list_teilnehmer(self.conn)
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
        self._startnummern_hinweis_aktualisieren()


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
        "Hundes' auf dem Formular). Fehlt eine davon, das Formular trotzdem als Zeile "
        "ausgeben (das Feld leer) - der Import meldet dann, was fehlt.\n"
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
        "- chip_nr = Chip- bzw. Tätowiernummer; ist nur 'Tätowierung' angekreuzt, 'Täto ' "
        "vor die Nummer setzen (z. B. 'Täto ABC123').\n"
        "- Ein Feld ohne erkennbare Angabe auf dem Formular bleibt in der CSV leer - nicht "
        "raten und keinen Platzhalter wie 'unbekannt' eintragen.\n"
        "- startnummer und bezahlt vergibt das Programm selbst; Gegenstände werden über "
        "diesen Weg nicht übernommen (im Programm nachtragen).\n\n"
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
            QMessageBox.warning(self, "Speichern fehlgeschlagen",
                                f"Die Vorlage konnte nicht gespeichert werden.\n\n{_klartext_fehler(exc)}")
            return
        _datei_gespeichert_melden(self, pfad, "Vorlage gespeichert", datei_oeffnen_text="Datei öffnen")

    def _ki_bereich_umschalten(self, sichtbar: bool) -> None:
        self._ki_bereich.setVisible(sichtbar)
        self._ki_umschalter.setText(("▾ " if sichtbar else "▸ ") + self._KI_UMSCHALTER_TEXT)

    def _oma_importieren(self) -> None:
        """Übernimmt Meldungen aus einem OMA-Export (siehe importiere_teilnehmer_aus_oma in
        db_import.py) - ohne Umweg über den KI-Prompt."""
        pfad, _ = QFileDialog.getOpenFileName(
            self, "OMA-Export importieren", _import_startordner(), "OMA-Export (*.csv *.txt);;Alle Dateien (*)"
        )
        if not pfad:
            return
        _import_ordner_merken(pfad)
        vorher = _teilnehmerzahl(self.conn)
        try:
            ergebnis = importiere_teilnehmer_aus_oma(self.conn, pfad)
        except OSError as exc:
            QMessageBox.warning(self, "Import fehlgeschlagen",
                                f"Die Datei konnte nicht gelesen werden.\n\n{_klartext_fehler(exc)}")
            return
        except sqlite3.Error as exc:
            _import_db_fehler_melden(self, exc, self.conn, vorher)
            self.aktualisieren()
            return
        _import_ergebnis_melden(self, ergebnis)
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
        # Lesefehler je Datei fängt der Import selbst ab und meldet sie in ergebnis.fehler
        # (Verifikation 28.09.2026, Befund 7a); hier bleiben nur Schreibfehler der Termin-Datei.
        vorher = _teilnehmerzahl(self.conn)
        try:
            ergebnis = importiere_anmeldeformular_pdf(self.conn, pfade)
        except sqlite3.Error as exc:
            _import_db_fehler_melden(self, exc, self.conn, vorher)
            self.aktualisieren()
            return
        _import_ergebnis_melden(self, ergebnis, "Datei(en) nicht importiert:")
        if ergebnis.importiert:
            _startnummern_nach_import_anbieten(self, self.conn)


# Höchstpunktzahlen je Disziplin (entsprechen den CHECK-Constraints in db.py). UX-Test
# 02.10.2026, U5: das Punktefeld ließ "65" als Zwischenstand beim Tippen zu - solche
# Werte werden deshalb sofort rot markiert und beim Speichern im Klartext abgelehnt, statt
# erst an der Datenbank mit "CHECK constraint failed" zu scheitern.


def _punkte_validator(parent) -> QRegularExpressionValidator:
    """Nur Ziffern (höchstens zwei) - unabhängig von der Spracheinstellung des Systems. Der
    QIntValidator nahm in englischer/Linux-Einstellung "," als Tausender-Trennzeichen an
    ("45," statt Hinweis; CI-Befund 03.10.2026). Werte über dem Maximum markiert
    _aktualisiere_zeilenstatus rot, das Speichern lehnt sie im Klartext ab (U5)."""
    return QRegularExpressionValidator(QRegularExpression(r"\d{0,2}"), parent)


# Spalten der Ergebnistabelle, deren Sortierschlüssel nur aus den Stammdaten kommt.
_SORTIERSPALTEN_AUS_STAMMDATEN = (0, 1, 2, 3)

# Lasttest 16.10.2026 (Marcos Entscheidung): Bei mehr Teilnehmern speichert "Alle speichern"
# in EINER Transaktion statt mit einem Commit je Ergebnis (bei 1000 Teilnehmern 2,9 s -> 0,6 s).
# Ein Datenbankfehler speichert dann gar nichts; bis einschließlich dieser Zahl bleibt es beim
# bisherigen Verhalten, bei dem schon gespeicherte Zeilen erhalten bleiben.
_SAMMELSPEICHERN_UEBER_TEILNEHMER = 200


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
            spalten += [f"{disziplin}\nSuche (0-{SUCHE_MAX})", f"{disziplin}\nAnzeige (0-{ANZEIGE_MAX})"]
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
        # Infospalten (Start-Nr., Name, Hund, Prüfung) sind nur Anzeige, und Tab springt
        # von Eingabefeld zu Eingabefeld statt durch die Zellen (Desktop-Prüfung
        # 14.10.2026, Teil 3 Nr. 3).
        self.tabelle.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabelle.setTabKeyNavigation(False)
        # Sortierpfeil wie im Teilnehmer-Reiter (Teil 3 Nr. 7) - die Richtung setzt
        # _spalte_geklickt selbst, weil die Sortierung hier eigene Logik hat.
        self.tabelle.horizontalHeader().setSortIndicatorShown(True)
        self.tabelle.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
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
        self._feldhoehe: int | None = None  # einmal bestimmt, siehe _zeilen_aufbauen
        self._tabelle_pt: float | None = None  # zuletzt gesetzte Schriftgröße, siehe _spaltenbreiten_anpassen
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
        self.status_label.setTextFormat(Qt.PlainText)  # S-1: Meldungen immer als Klartext
        # Eigenes Label für den Komma-Hinweis (N6): orange und fett über ein Stylesheet statt
        # Rich Text im status_label, das seit S-1 nur Klartext zeigt (Desktop-Prüfung
        # 14.10.2026, Teil 3 Nr. 2 - vorher stand das rohe <span…> in der Statuszeile).
        self.hinweis_label = QLabel("")
        self.hinweis_label.setTextFormat(Qt.PlainText)
        self.hinweis_label.setWordWrap(True)
        self.hinweis_label.hide()
        self._eingabe_hinweis: str | None = None

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
        layout.addWidget(self.hinweis_label)
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

    def aktualisieren_falls_geaendert(self) -> None:
        """Wie aktualisieren(), aber nur, wenn sich die Datenbank seit dem letzten Aufbau
        geändert hat (für den Tabwechsel). Lasttest 16.10.2026: Der Neuaufbau kostet bei
        1000 Teilnehmern rund 5 s, weil jede Zeile eigene Eingabefelder bekommt."""
        stand = self._datenstand()
        if stand is not None and stand == self._geladener_datenstand:
            # Wie nach einem Neuaufbau: alte Status- und Komma-Hinweise ausblenden.
            self.status_label.setText("")
            self._eingabe_hinweis_ausblenden()
            return
        self.aktualisieren()

    def _datenstand(self) -> tuple[int, int] | None:
        """Kennung des Datenstands: total_changes zählt die geänderten Zeilen über diese
        Verbindung (auch aus anderen Reitern, zurückgerollte eingeschlossen), PRAGMA
        data_version die Commits anderer Verbindungen (z. B. einer zweiten
        Programminstanz). None, wenn die Datei gerade nicht lesbar ist (gesperrt, Stick
        abgezogen) - dann wird wie bisher neu aufgebaut, Fehler meldet der Neuaufbau."""
        try:
            return self.conn.total_changes, self.conn.execute("PRAGMA data_version").fetchone()[0]
        except sqlite3.Error:
            return None

    def _neu_laden(self, werte_override: dict | None = None, status_override: dict | None = None) -> None:
        """Gemeinsamer Kern von aktualisieren() (ohne Overrides) und
        aktualisieren_eingaben_erhalten() (mit den noch ungespeicherten Eingaben)."""
        # Vor dem Lesen merken, damit eine Änderung während des Aufbaus beim nächsten
        # Tabwechsel noch einen Neuaufbau auslöst.
        self._geladener_datenstand = self._datenstand()
        self._teilnehmer_je_zeile = list_teilnehmer(self.conn, nur_teilnehmende=True)
        if self._sortierspalte in _SORTIERSPALTEN_AUS_STAMMDATEN:
            # Sortierung nach Stammdaten: vor dem Aufbau sortieren, dann nur EIN Aufbau
            # (Desktop-Prüfung 14.10.2026, Teil 3 Nr. 6).
            self._teilnehmer_je_zeile.sort(
                key=lambda t: self._sortierschluessel_teilnehmer(t, self._sortierspalte),
                reverse=not self._sortieraufsteigend,
            )
        verworfen = self._zeilen_aufbauen(werte_override, status_override)
        # Codeprüfung 22.09., G9: list_teilnehmer() liefert immer die DB-Reihenfolge -
        # ohne erneutes Anwenden ging die per Spaltenklick gewählte Sortierung hier
        # verloren, während _sortierspalte/_sortieraufsteigend stehen blieben, sodass der
        # nächste Klick auf dieselbe Spalte die Richtung "umkehrte", obwohl die Tabelle gar
        # nicht (mehr) danach sortiert war. Erst nach dem Aufbau sortieren, weil einige
        # Sortierschlüssel (Punkte, DQ/Abbruch, Status) aus den Zeilen-Widgets gelesen
        # werden; die Werte stammen hier frisch aus der DB (bzw. aus den Overrides), es geht
        # also nichts verloren.
        if self._sortierspalte is not None and self._sortierspalte not in _SORTIERSPALTEN_AUS_STAMMDATEN:
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
        Disqualifiziert/Abbruch gespeichert oder die Disziplin geändert ist - je Eintrag mit
        Grund (für _verworfene_melden)."""
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
            nummer = f"Nr. {t['startnummer']} – " if t["startnummer"] is not None else ""
            # Gründe für verworfene Eingaben dieser Person; am Zeilenende zu einem einzigen
            # Eintrag zusammengeführt (offener Punkt 18.10.2026: sonst stünde sie mehrfach da).
            gruende: list[str] = []
            for disziplin in punkte_override:
                if disziplin not in zutreffende_disziplinen:
                    # Teil 3 Nr. 5: Disziplin inzwischen geändert - die Eingabe zur alten
                    # Disziplin hat keinen Platz mehr und wird gemeldet statt still verworfen.
                    gruende.append(f"{disziplin}: Disziplin inzwischen geändert")

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
                    lambda f=suche_feld: self._eingabe_abgelehnt(f, SUCHE_MAX)
                )
                anzeige_feld.inputRejected.connect(
                    lambda f=anzeige_feld: self._eingabe_abgelehnt(f, ANZEIGE_MAX)
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
                gruende.append("inzwischen „Disqualifiziert“ oder „Abbruch“ gespeichert")
            if gruende:
                verworfen.append(f"{nummer}{t['nachname']}, {t['vorname']} ({'; '.join(gruende)})")
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

        # Stylesheet nur bei geänderter Schriftgröße neu setzen (Teil 3 Nr. 6).
        if self._tabelle_pt != round(pt, 1):
            self._tabelle_pt = round(pt, 1)
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
        # vor - die bekommt den Restplatz (setStretchLastSection und ausdrücklich unten,
        # siehe "Restplatz ausdrücklich an die Status-Spalte"), dafür wird ihr
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
        # Restplatz ausdrücklich an die Status-Spalte (Marco 09.10.2026): setStretchLastSection
        # streckt nur bei einer Größenänderung neu. Nach einem Neuaufbau ohne Größenänderung
        # (Speichern, "Liste aktualisieren") blieb sie sonst bei ihrer Inhaltsbreite stehen,
        # und bei breiten Fenstern stand rechts eine graue Lücke.
        rest = breite - sum(ziel)
        if rest > self.tabelle.columnWidth(_STATUS_SPALTE):
            self.tabelle.setColumnWidth(_STATUS_SPALTE, rest)
        # UX-Test 02.10.2026, K1: Zeilen mindestens so hoch wie ein Eingabefeld - sonst
        # wurden eingetippte Punkte unten abgeschnitten.
        if self._feldhoehe is None:
            self._feldhoehe = QLineEdit().sizeHint().height()
        feldhoehe = self._feldhoehe
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
        self.tabelle.horizontalHeader().setSortIndicator(
            spalte, Qt.AscendingOrder if self._sortieraufsteigend else Qt.DescendingOrder
        )
        self._verworfene_melden(self._sortieren_und_neu_aufbauen())

    @staticmethod
    def _sortierschluessel_teilnehmer(t: dict, spalte: int):
        """Schlüssel der Stammdaten-Spalten (Start-Nr., Name, Hund, Prüfung); Namen nach
        deutscher Gewohnheit (db.sortierschluessel_text, Teil 3 Nr. 4)."""
        if spalte == 0:
            return t["startnummer"] if t["startnummer"] is not None else -1
        if spalte == 1:
            return sortierschluessel_text(f"{t['nachname']}, {t['vorname']}")
        if spalte == 2:
            return sortierschluessel_text(t["rufname_hund"])
        return sortierschluessel_text(leistungsklasse_label(t))

    def _sortierschluessel_fuer_zeile(self, row: int, spalte: int):
        """Sortierschlüssel für Zeile `row` bezogen auf die VOR dem Sortieren gültige
        Zeilenreihenfolge (self._teilnehmer_je_zeile/_boxen_je_zeile/
        _status_boxen_je_zeile sind zu diesem Zeitpunkt noch nicht umsortiert)."""
        if spalte in _SORTIERSPALTEN_AUS_STAMMDATEN:
            return self._sortierschluessel_teilnehmer(self._teilnehmer_je_zeile[row], spalte)
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
        den Teilnehmer inzwischen Disqualifiziert/Abbruch gespeichert oder die Disziplin
        geändert ist (Grund steht je Eintrag dabei). Die Liste kommt als Rückgabewert aus
        _zeilen_aufbauen (kein Zwischenzustand im Objekt)."""
        if not verworfen:
            return
        namen = "\n".join(dict.fromkeys(verworfen))
        QMessageBox.information(
            self,
            "Eingaben verworfen",
            "Folgende noch nicht gespeicherte Punkte wurden verworfen:\n\n" + namen,
        )

    def _aktualisieren_mit_rueckfrage(self) -> None:
        """Reagiert auf den "Liste aktualisieren"-Button: warnt vorher, falls dabei
        ungespeicherte Änderungen verloren gingen."""
        if self.hat_ungespeicherte_aenderungen():
            if not _ja_nein(
                self,
                "Ungespeicherte Änderungen",
                "Es gibt noch nicht gespeicherte Ergebnisse. Beim Aktualisieren gehen diese "
                "verloren.\n\nTrotzdem aktualisieren?",
            ):
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
        # leicht übersehen - er steht orange und fett über der Statuszeile, bis die nächste
        # gültige Eingabe kommt. Seit der Desktop-Prüfung (14.10.2026, Teil 3 Nr. 2) in einem
        # eigenen Label als Klartext mit Stylesheet, damit Statusmeldungen davon unberührt
        # bleiben und kein Rich Text nötig ist.
        self._eingabe_hinweis = hinweis
        self.hinweis_label.setStyleSheet(f"color: {_farbe('warnung').name()}; font-weight: bold;")
        self.hinweis_label.setText(hinweis)
        self.hinweis_label.show()

    def _eingabe_hinweis_ausblenden(self) -> None:
        """Nimmt den Komma-Hinweis wieder weg - nur, wenn dort noch der Hinweis steht."""
        if self._eingabe_hinweis is not None:
            self.hinweis_label.clear()
            self.hinweis_label.hide()
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
            maximum_je_feld[suche_feld] = SUCHE_MAX
            maximum_je_feld[anzeige_feld] = ANZEIGE_MAX

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
                    tooltip = f"Höchstens {maximum} Punkte." if zu_hoch else ""
                    if widget.toolTip() != tooltip:
                        widget.setToolTip(tooltip)
                # Nur bei Änderung setzen: setStyleSheet ist teuer und lief bei jedem Aufbau
                # und Speichern für tausende Felder (Lasttest 16.10.2026).
                if widget.styleSheet() != stil:
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

    def _sammelspeichern_zuruecknehmen(self, geladen_vorher: list, status_geladen_vorher: list) -> None:
        """Rollt ein gescheitertes Sammelspeichern zurück und setzt die Tabelle auf den
        Stand davor: alle Eingaben gelten wieder als ungespeichert."""
        with contextlib.suppress(sqlite3.Error):
            self.conn.rollback()
        self._geladen_je_zeile = geladen_vorher
        self._status_geladen_je_zeile = status_geladen_vorher
        for zeile in range(len(self._teilnehmer_je_zeile)):
            self._aktualisiere_zeilenstatus(zeile)

    def alle_speichern(self) -> None:
        """Speichert alle geänderten Zeilen der Tabelle auf einmal (unabhängig vom
        aktuellen Filter - auch ausgeblendete Zeilen werden mitgespeichert). Bei mehr als
        _SAMMELSPEICHERN_UEBER_TEILNEHMER Teilnehmern in einer Transaktion (ganz oder gar
        nicht), sonst mit einem Commit je Ergebnis."""
        gespeichert = 0
        fehler: list[str] = []
        # Stand die Tabelle vor dem Speichern auf dem aktuellen Datenstand, entspricht sie
        # danach wieder der Datenbank - der nächste Tabwechsel muss dann nicht neu aufbauen.
        # Ausnahme: Sortierung nach einer Ergebnisspalte, die ein Neuaufbau neu anwenden würde.
        stand_vorher = self._datenstand()
        tabelle_war_aktuell = (
            stand_vorher is not None
            and stand_vorher == self._geladener_datenstand
            and self._sortierspalte in (None, *_SORTIERSPALTEN_AUS_STAMMDATEN)
        )
        gesammelt = len(self._teilnehmer_je_zeile) > _SAMMELSPEICHERN_UEBER_TEILNEHMER
        if gesammelt:
            # Für den Fehlerfall: dann gilt wieder der Stand vor dem Speichern.
            geladen_vorher = [dict(geladen) for geladen in self._geladen_je_zeile]
            status_geladen_vorher = list(self._status_geladen_je_zeile)

        # Desktop-Prüfung 14.10.2026, Teil 3 Nr. 1: Ein Schreibfehler der Datenbank
        # (schreibgeschützt, gesperrt, Stick abgezogen) bricht beim ersten Mal ab - die
        # übrigen Eingaben bleiben als ungespeichert stehen, sodass die Nachfrage beim
        # Beenden bzw. Terminwechsel greift, statt dass eine Ausnahme sie überspringt.
        # Im Sammelmodus (siehe _SAMMELSPEICHERN_UEBER_TEILNEHMER) wird dabei alles
        # zurückgerollt, und alle Eingaben bleiben ungespeichert stehen.
        db_fehler: sqlite3.Error | None = None
        try:
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
                            eintragen_ergebnis(self.conn, t["id"], disziplin, None, None, commit=not gesammelt)
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
                                ("Suche", suche_wert, SUCHE_MAX), ("Anzeige", anzeige_wert, ANZEIGE_MAX)
                            )
                            if wert > maximum
                        ]
                        if zu_hoch:
                            fehler.append(f"{name} – {disziplin}: " + ", ".join(zu_hoch))
                            continue

                        try:
                            eintragen_ergebnis(
                                self.conn, t["id"], disziplin, suche_wert, anzeige_wert, commit=not gesammelt
                            )
                        except sqlite3.IntegrityError as exc:
                            fehler.append(f"{name} – {disziplin}: {exc}")
                            if gesammelt:
                                # eintragen_ergebnis hat die ganze offene Transaktion
                                # zurückgerollt (db._mit_rollback) - also Abbruch wie unten.
                                raise
                            continue

                        geladen[disziplin] = (suche_wert, anzeige_wert)
                        gespeichert += 1
                # Ist die Zeile gesperrt (Disqualifiziert/Abbruch), werden die (geleerten)
                # Punkte-Felder beim Speichern bewusst NICHT ausgewertet: eine ggf. weiterhin
                # in der DB stehende Punktzahl bleibt unangetastet (siehe
                # db.setze_ergebnis_status()-Docstring) - vorher wurden hier fälschlich beide
                # Felder als "geleert" erkannt und die echten Punkte dauerhaft gelöscht.

                if status_wert != self._status_geladen_je_zeile[row]:
                    setze_ergebnis_status(
                        self.conn, t["id"], status_wert[0], status_wert[1], commit=not gesammelt
                    )
                    self._status_geladen_je_zeile[row] = status_wert
                    gespeichert += 1

                self._aktualisiere_zeilenstatus(row)
            if gesammelt:
                self.conn.commit()
        except sqlite3.Error as exc:
            db_fehler = exc
            if gesammelt:
                self._sammelspeichern_zuruecknehmen(geladen_vorher, status_geladen_vorher)
                gespeichert = 0
            else:
                self._aktualisiere_zeilenstatus(row)
        except BaseException:
            # Unerwarteter Fehler (kein Datenbankfehler): im Sammelmodus keine halbe
            # Transaktion offen lassen, die der nächste Commit einer anderen Aktion
            # festschreiben würde.
            if gesammelt:
                self._sammelspeichern_zuruecknehmen(geladen_vorher, status_geladen_vorher)
            raise

        if tabelle_war_aktuell and db_fehler is None:
            stand_nachher = self._datenstand()
            # Eigene Commits ändern nur total_changes. Hat eine andere Verbindung während
            # des Speicherns geschrieben (data_version geändert), bleibt der alte Stand
            # gemerkt, und der nächste Tabwechsel baut neu auf.
            if stand_nachher is not None and stand_nachher[1] == stand_vorher[1]:
                self._geladener_datenstand = stand_nachher

        if db_fehler is not None:
            if gesammelt:
                self.status_label.setText("Speichern abgebrochen – nichts gespeichert.")
                einleitung = (
                    "Die Ergebnisse konnten nicht gespeichert werden. Es wurde nichts gespeichert, "
                    "alle Eingaben stehen weiter in der Tabelle."
                )
            else:
                self.status_label.setText(
                    f"Speichern abgebrochen – {gespeichert} Ergebnis(se) gespeichert, die übrigen nicht."
                )
                einleitung = (
                    "Die Ergebnisse konnten nicht (vollständig) gespeichert werden. Bereits gespeicherte "
                    "Zeilen bleiben erhalten, die übrigen Eingaben stehen weiter in der Tabelle."
                )
            if fehler:
                # Eine einzige Meldung (Desktop-Prüfung 14.10.2026): Eingabefehler, die vor dem
                # Abbruch auffielen, gehören mit hinein.
                einleitung += "\n\nAußerdem fehlerhafte Eingaben:\n" + "\n".join(fehler)
            _db_fehler_anzeigen(self, db_fehler, einleitung)
        elif gespeichert:
            self.status_label.setText(f"{gespeichert} Ergebnis(se) gespeichert.")
        elif not fehler:
            self.status_label.setText("Keine Änderungen zu speichern.")

        if fehler and db_fehler is None:
            QMessageBox.warning(
                self,
                "Nicht alle Ergebnisse gespeichert",
                "Folgende Zeilen konnten nicht gespeichert werden (übrige wurden gespeichert):\n\n"
                + "\n".join(fehler),
            )


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
        # Widget auf der (damals noch leeren) QMenuBar wurde zunächst versucht,
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

    def _farben_auffrischen(self) -> None:
        """Färbt Tabelleninhalte nach einem Darstellungswechsel neu. Teilnehmer,
        Auswertung und Zeitplan laden dafür neu (keine ungespeicherten Eingaben dort);
        die Ergebniserfassung färbt nur um, damit ungespeicherte Punkte erhalten bleiben."""
        for tab in (self.teilnehmer_tab, self.auswertung_tab, self.zeitplan_tab):
            tab.aktualisieren()
        self.ergebnis_tab.farben_auffrischen()

    def _hilfe_anzeigen(self) -> None:
        _ausfuehren(HilfeDialog(self))

    def _version_anzeigen(self) -> None:
        _ausfuehren(VersionDialog(self))

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
        self.demo_btn.setText("🎓 Erklärfenster zeigen" if aktiv else "🎓 Demoprüfung")
        self.demo_btn.setToolTip(
            "Holt das Erklärfenster der laufenden Demoprüfung wieder nach vorn." if aktiv else self._demo_tooltip
        )

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
                return _ja_nein(
                    self,
                    "Nicht alle Ergebnisse gespeichert",
                    "Nicht alle Ergebnisse konnten automatisch gespeichert werden (siehe "
                    "vorherige Meldung).\n\nProgramm trotzdem beenden und diese ungespeicherten "
                    "Änderungen verwerfen?",
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
            ("formular_import_tab", "Formular-Import", lambda: FormularImportTab(conn)),
            ("zeitplan_tab", "Zeitplan", lambda: ZeitplanTab(conn, ablageort)),
            ("ergebnis_tab", "Ergebniserfassung", lambda: ErgebnisTab(conn)),
            ("auswertung_tab", "Auswertung", lambda: AuswertungTab(conn, ablageort)),
            ("teilnehmer_uebersicht_tab", "Übersicht", lambda: TeilnehmerUebersichtTab(conn)),
            ("verwaltung_tab", "Verwaltung", lambda: VerwaltungTab(conn)),
            ("export_tab", "Export", lambda: ExportTab(conn, pfad, ablageort)),
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
        self.setWindowTitle(fenstertitel)

        self._vorheriger_tab_index = 0

    def _titel_aktualisieren(self) -> None:
        """Fenstertitel aus Verein und Datum; fehlt der Verein (fremde Datei), der Dateiname
        statt „None“ (Desktop-Prüfung 14.10.2026, Teil 8 Nr. 3). Auch nach „Veranstaltungs-
        daten bearbeiten…“ aufgerufen (Teil 2 Nr. 5)."""
        self.setWindowTitle(_fenstertitel(self.conn, self.pfad, getattr(self, "_demo_termin", False)))

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
        self.resize(600, 380)
        self.pfad: str | None = None
        # "🎓 Demoprüfung" gewählt - der Aufrufer startet dann die Demo (desktop_demo).
        self.demo_angefordert = False
        # True, wenn `pfad` eben erst über „Neuen Termin anlegen“ entstanden ist - siehe
        # HauptFenster._neu_angelegten_termin_entfernen.
        self.neu_angelegt = False
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
        # Teil 7 Nr. 8: Enter in der Liste öffnet den markierten Termin (sonst griffe der
        # Standardknopf „Neuen Termin anlegen…“).
        self.tabelle.installEventFilter(self)
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
                (t.verein or t.dateiname) if t.lesbar
                else f"{t.dateiname} (nicht lesbar{': ' + t.grund if t.grund else ''})",
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

    def eventFilter(self, obj, event) -> bool:  # type: ignore[override]
        if (obj is self.tabelle and event.type() == QEvent.KeyPress
                and event.key() in (Qt.Key_Return, Qt.Key_Enter) and self._ausgewaehlter_termin() is not None):
            self._termin_oeffnen()
            return True
        return super().eventFilter(obj, event)

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
                # Marco 09.10.2026: die Standardgröße der Bereiche ebenso.
                "startnummer_bereichsgroesse": letzter.startnummer_bereichsgroesse,
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
        fenster.showMaximized()
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
