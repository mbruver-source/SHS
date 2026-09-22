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
  2. Teilnehmer erfassen, bearbeiten, löschen (mit Rückfrage). Die Startnummer
     wird bei Neuanlage automatisch auf die kleinste freie Nummer vorgeschlagen
     und beim Speichern gegen bereits vergebene Startnummern geprüft (auch als
     Datenbank-Constraint abgesichert) - eine doppelte Vergabe ist so
     ausgeschlossen.
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
import os
import sqlite3
import sys

from PySide6.QtCore import QSettings, QUrl, Qt
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QColor,
    QDesktopServices,
    QIntValidator,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
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
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from db import (
    ALLE_DISZIPLINEN,
    CSV_IMPORT_SPALTEN,
    DISZIPLIN_SPALTEN,
    NeuerTeilnehmer,
    add_teilnehmer,
    add_zeitplan_pause,
    add_zeitplan_pruefungsblock,
    add_zeitplan_richter,
    aktualisiere_zeitplan_eintrag,
    alle_leistungsklassen,
    automatische_zeitplan_verteilung,
    berechne_auswertung,
    berechne_teilnehmer_lk_uebersicht,
    berechne_zeitplan,
    berechne_zeitplan_bloecke,
    dateiname_vorschlagen,
    delete_teilnehmer,
    eindeutigen_dateinamen_finden,
    eintragen_ergebnis,
    get_veranstaltung,
    importiere_teilnehmer_aus_csv,
    importiere_teilnehmer_stammdaten,
    init_db,
    leistungsklasse_label,
    liste_termine,
    list_teilnehmer,
    list_zeitplan_richter,
    loesche_zeitplan_eintrag,
    loesche_zeitplan_richter,
    naechste_freie_startnummer,
    PasswortFalschError,
    set_veranstaltung,
    setze_bezahlt,
    setze_ergebnis_status,
    sicherung_erstellen,
    sicherung_inhalt,
    sicherung_wiederherstellen,
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
)
import pdf_export
from shs_core import ABBRUCH_ABK, ABBRUCH_TEXT, DISQUALIFIZIERT_ABK, DISQUALIFIZIERT_TEXT

try:
    # version.py wird von bump_version.py automatisch erzeugt (siehe dort) und ist daher
    # in einer frischen Arbeitskopie vor dem allerersten Build noch nicht vorhanden - der
    # Fallback verhindert, dass app.py deswegen gar nicht erst startet.
    from version import VERSION
except ImportError:
    VERSION = "dev"


def _aktualisiere_veranstaltung_feld(conn, **overrides) -> None:
    """Aktualisiert einzelne Veranstaltungs-Felder, ohne die übrigen (z.B. von einem
    anderen Tab gepflegten) Felder zu überschreiben - set_veranstaltung ersetzt sonst bei
    jedem Aufruf den kompletten Datensatz, da es keine partiellen Updates kennt."""
    aktuell = get_veranstaltung(conn) or {}
    werte = {
        "verein": aktuell.get("verein") or "",
        "datum": aktuell.get("datum") or "",
        "ort": aktuell.get("ort"),
        "vereins_nr": aktuell.get("vereins_nr"),
        "pruefungsnummer": aktuell.get("pruefungsnummer"),
        "wertungsrichter_1": aktuell.get("wertungsrichter_1"),
        "wertungsrichter_2": aktuell.get("wertungsrichter_2"),
        "wertungsrichter_3": aktuell.get("wertungsrichter_3"),
        "wertungsrichter_4": aktuell.get("wertungsrichter_4"),
        "wertungsrichter_5": aktuell.get("wertungsrichter_5"),
        "pruefungsleiter": aktuell.get("pruefungsleiter"),
        "pruefungsgebuehr_ed": aktuell.get("pruefungsgebuehr_ed"),
        "pruefungsgebuehr_dk": aktuell.get("pruefungsgebuehr_dk"),
        "zeitplan_start": aktuell.get("zeitplan_start"),
    }
    werte.update(overrides)
    set_veranstaltung(conn, **werte)


class _Ablageort:
    """Gemeinsamer, veränderlicher Ablageort für alle PDF-Export-Buttons EINES Termins
    (Tabs "Zeitplan" und "Export") - ein einzelnes, von beiden Tabs geteiltes Objekt statt
    je ein eigener String pro Tab. Wählt der Nutzer beim Speichern bewusst einen anderen
    Ordner, gilt dieser dadurch sofort auch als neuer Standard-Speicherort im jeweils
    ANDEREN Tab, statt dass beide unabhängig voneinander ihren eigenen (dann ggf.
    unterschiedlichen) Ablageort verfolgen."""

    def __init__(self, pfad: str):
        self.pfad = pfad


def _export_dateiname(conn, praefix: str) -> str:
    veranstaltung = get_veranstaltung(conn)
    datum = (veranstaltung or {}).get("datum") or ""
    return f"{praefix}_{datum}.pdf" if datum else f"{praefix}.pdf"


def _pdf_speicherort_waehlen(parent, ablageort: _Ablageort, titel: str, vorschlag_dateiname: str) -> str | None:
    vorschlag_pfad = os.path.join(ablageort.pfad, vorschlag_dateiname)
    pfad, _ = QFileDialog.getSaveFileName(parent, titel, vorschlag_pfad, "PDF-Datei (*.pdf)")
    if not pfad:
        return None
    # Merkt sich den zuletzt gewählten Ordner (siehe _Ablageort oben), damit sowohl der
    # nächste Speichern-Dialog in DIESEM Tab als auch im jeweils anderen Tab dorthin
    # zeigen, falls der Nutzer bewusst woanders gespeichert hat.
    ablageort.pfad = os.path.dirname(pfad)
    return pfad


def _pdf_export_fehler_anzeigen(parent, exc: Exception) -> None:
    QMessageBox.critical(
        parent, "PDF konnte nicht erstellt werden",
        f"Der Export ist fehlgeschlagen (z.B. Zielpfad nicht schreibbar oder Datei "
        f"gerade in einem anderen Programm geöffnet):\n\n{exc}",
    )


def _zeitplan_pdf_exportieren(parent, conn, ablageort: "_Ablageort", status_label: QLabel) -> None:
    """Gemeinsame Umsetzung für den Zeitplan-PDF-Export - vorher wortgleich in
    ZeitplanTab._pdf_exportieren und ExportTab._zeitplan_exportieren dupliziert."""
    pfad = _pdf_speicherort_waehlen(parent, ablageort, "Zeitplan speichern", _export_dateiname(conn, "Zeitplan"))
    if not pfad:
        return
    try:
        pdf_export.erstelle_zeitplan_pdf(conn, pfad)
    except Exception as exc:
        _pdf_export_fehler_anzeigen(parent, exc)
        return
    status_label.setText(f"Zeitplan gespeichert: {pfad}")


def _responsive_schriftgroesse(breite: int, schmal: int = 480, breit: int = 900, pt_schmal: float = 8.0, pt_breit: float = 10.0) -> float:
    """Berechnet eine Schriftgröße (pt) zwischen pt_schmal und pt_breit, linear nach
    der Fensterbreite interpoliert - damit Beschriftungen (Spaltenköpfe, Filter- und
    Hinweistexte) bei kleineren Fenstern nicht abgeschnitten werden, sondern lesbar
    kleiner dargestellt werden, statt der Anwendung eine Mindestbreite vorzuschreiben."""
    if breite <= schmal:
        return pt_schmal
    if breite >= breit:
        return pt_breit
    anteil = (breite - schmal) / (breit - schmal)
    return pt_schmal + anteil * (pt_breit - pt_schmal)


class ResponsiveSchriftMixin:
    """Mixin für Fenster/Dialoge: passt bei jeder Größenänderung die Schriftgröße von
    Spaltenköpfen und Beschriftungen (QLabel) an die aktuelle Fensterbreite an (siehe
    _responsive_schriftgroesse) - Tabellen und Formularfelder selbst bleiben in normaler
    Größe, nur die Beschriftungen schrumpfen bei kleinen Fenstern, statt abgeschnitten
    zu werden."""

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._schriftgroesse_anwenden()

    def _schriftgroesse_anwenden(self) -> None:
        pt = _responsive_schriftgroesse(self.width())
        self.setStyleSheet(f"QHeaderView::section {{ font-size: {pt:.1f}pt; }} QLabel {{ font-size: {pt:.1f}pt; }}")


def _fehler_anzeigen(parent, exc: Exception) -> None:
    """Zeigt einen Datenbankfehler (z.B. verletzte Fachregel) als Dialog statt die App abstürzen zu lassen."""
    QMessageBox.critical(
        parent,
        "Eingabe konnte nicht gespeichert werden",
        f"Die Daten verletzen eine Fachregel und wurden nicht gespeichert:\n\n{exc}",
    )


def _db_fehler_anzeigen(parent, exc: Exception) -> None:
    """Zeigt einen unerwarteten Datenbankfehler (z.B. gesperrte Datei, voller Datenträger) als
    Dialog statt die App abstürzen zu lassen - für einfache Aktionen ohne eigene
    Fachregel-Prüfung (Richter/Zeitplan verwalten u.ä.), bei denen ein sqlite3.Error bisher
    unbehandelt durchschlug."""
    QMessageBox.critical(
        parent,
        "Datenbankfehler",
        f"Die Änderung konnte nicht gespeichert werden:\n\n{exc}",
    )


# Auswahlwert für "diesem Gegenstand ist (noch) keine Disziplin zugeordnet" - bewusst kein
# Eintrag aus ALLE_DISZIPLINEN, damit er sich eindeutig von einer echten Zuordnung
# unterscheidet. Wird als NULL in der Datenbank abgelegt (siehe db.NeuerTeilnehmer).
_GEGENSTAND_ZUORDNUNG_FREI = "frei"


def _zuordnung_oder_none(combo: QComboBox) -> str | None:
    text = combo.currentText()
    return None if text == _GEGENSTAND_ZUORDNUNG_FREI else text


def _gegenstand_zeile(feld: QLineEdit, zuordnung: QComboBox) -> QWidget:
    """Kombiniert ein Gegenstand-Textfeld mit seiner Disziplin-Zuordnung (frei/Trümmerfeld/
    Flächensuche/Behältnisstrecke) zu einer gemeinsamen Formularzeile."""
    zeile = QHBoxLayout()
    zeile.setContentsMargins(0, 0, 0, 0)
    zeile.addWidget(feld, 2)
    zeile.addWidget(QLabel("gesucht in:"))
    zeile.addWidget(zuordnung, 1)
    widget = QWidget()
    widget.setLayout(zeile)
    return widget


def _startnummer_zeile(feld: QSpinBox, unbekannt: QCheckBox) -> QWidget:
    """Kombiniert das Startnummer-Feld mit dem Häkchen 'Startnummer steht noch nicht
    fest' zu einer gemeinsamen Formularzeile (Nutzerwunsch 20.09.: Startnummer soll bei
    der Ersterfassung kein Pflichtfeld mehr sein müssen)."""
    zeile = QHBoxLayout()
    zeile.setContentsMargins(0, 0, 0, 0)
    zeile.addWidget(feld, 1)
    zeile.addWidget(unbekannt, 2)
    widget = QWidget()
    widget.setLayout(zeile)
    return widget


class TeilnehmerDialog(ResponsiveSchriftMixin, QDialog):
    """Formular zur Neuanlage eines Teilnehmers."""

    def __init__(
        self, parent=None, vorhandener: dict | None = None, vergebene_nummern: set[int] | None = None,
        naechste_nummer: int = 1, namen_je_startnummer: dict[int, str] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Teilnehmer bearbeiten" if vorhandener else "Teilnehmer erfassen")
        # Bereits vergebene Startnummern (beim Bearbeiten ohne die eigene) - für
        # die Dubletten-Prüfung beim Speichern.
        self._vergebene_nummern = vergebene_nummern or set()
        # Nur für die Warnmeldung bei doppelter Startnummer: wer hat sie schon (Name), damit
        # der Hinweis konkret wird statt nur "ist bereits vergeben" zu sagen.
        self._namen_je_startnummer = namen_je_startnummer or {}

        self._felder_erstellen(naechste_nummer)
        self._layout_aufbauen()

        self._art_geaendert(self.art.currentText())
        if vorhandener:
            self._vorbelegung_uebernehmen(vorhandener)

        self._halter_sichtbarkeit_aktualisieren(self.halter_weicht_ab.isChecked())
        self._startnummer_verfuegbarkeit_aktualisieren(self.startnummer_unbekannt.isChecked())
        self._schriftgroesse_anwenden()

    def _felder_erstellen(self, naechste_nummer: int) -> None:
        """Legt alle Eingabe-Widgets als Attribute an (noch ohne Layout/Vorbelegung -
        siehe _layout_aufbauen/_vorbelegung_uebernehmen)."""
        self.nachname = QLineEdit()
        self.vorname = QLineEdit()
        # Nutzerwunsch (21.09., Rückmeldung "Statistik/Jugendliche"): Geburtsdatum des
        # Hundeführers/der Hundeführerin, um Jugendliche (unter 18 Jahre am Prüfungstag)
        # in der Statistik-PDF gesondert auszuweisen (siehe db.ist_jugendlicher()).
        # Gleiche freie Text-Konvention wie die übrigen Datumsfelder im Projekt
        # (wurftag/tollwutimpfung_bis) statt eines QDateEdit-Widgets - im Projekt gibt es
        # bislang an keiner Stelle ein echtes Datumsauswahl-Widget als Vorbild.
        self.geburtsdatum = QLineEdit()
        self.geburtsdatum.setPlaceholderText("JJJJ-MM-TT")
        self.verein = QLineEdit()
        self.verband = QLineEdit()
        self.mitgliedsnummer = QLineEdit()
        self.zwingername = QLineEdit()
        self.rufname_hund = QLineEdit()
        self.geschlecht = QComboBox()
        self.geschlecht.addItems(["Hündin", "Rüde"])
        self.schulterhoehe = QSpinBox()
        self.schulterhoehe.setRange(0, 100)
        self.chip_nr = QLineEdit()
        self.rasse = QLineEdit()
        self.wurftag = QLineEdit()
        self.wurftag.setPlaceholderText("JJJJ-MM-TT")
        self.tollwutimpfung_bis = QLineEdit()
        self.tollwutimpfung_bis.setPlaceholderText("JJJJ-MM-TT")
        self.strasse = QLineEdit()
        self.hausnummer = QLineEdit()
        self.plz = QLineEdit()
        self.ort = QLineEdit()
        self.email = QLineEdit()
        self.telefon = QLineEdit()
        self.startnummer = QSpinBox()
        self.startnummer.setRange(1, 999)
        self.startnummer.setValue(naechste_nummer)  # Vorschlag bei Neuanlage; wird unten bei Bearbeiten überschrieben
        # Nutzerwunsch (20.09., Anmerkung zum Programm): "Vergabe der Startnummern als
        # Pflichtfeld finde ich hier noch nicht so gut, ich weiß ggf. nicht was alles an
        # Meldungen kommt" - die Startnummer kann jetzt offen gelassen werden (startnummer
        # bleibt dann NULL, wie von db.py ohnehin schon unterstützt) und später nachgetragen
        # werden.
        self.startnummer_unbekannt = QCheckBox("Startnummer steht noch nicht fest")
        self.startnummer_unbekannt.toggled.connect(self._startnummer_verfuegbarkeit_aktualisieren)

        self.art = QComboBox()
        self.art.addItems(["ED", "DK"])
        self.art.currentTextChanged.connect(self._art_geaendert)

        self.stufe = QComboBox()
        self.stufe.addItems(["1", "2", "3"])

        self.disziplin = QComboBox()
        self.disziplin.addItems(ALLE_DISZIPLINEN)

        # Je Gegenstand ein Freitextfeld PLUS eine Zuordnung, für welche Disziplin er
        # gesucht wird ("frei" = keiner bestimmten Disziplin zugeordnet - bewusst OHNE
        # Vorbelegung auf eine der drei Disziplinen, siehe _gegenstand_zeile unten).
        self.gegenstand_1 = QLineEdit()
        self.gegenstand_2 = QLineEdit()
        self.gegenstand_3 = QLineEdit()
        self.gegenstand_1_disziplin = QComboBox()
        self.gegenstand_2_disziplin = QComboBox()
        self.gegenstand_3_disziplin = QComboBox()
        for zuordnung in (self.gegenstand_1_disziplin, self.gegenstand_2_disziplin, self.gegenstand_3_disziplin):
            zuordnung.addItem(_GEGENSTAND_ZUORDNUNG_FREI)
            zuordnung.addItems(ALLE_DISZIPLINEN)

        self.bezahlt = QCheckBox("Prüfungsgebühr bezahlt")

        # Nutzerwunsch (20.09., Anmerkung zum Programm): Halter (Hundeeigentümer) und
        # Hundeführer (der/die oben mit Nachname/Vorname erfasste Person) können laut
        # Meldeformular abweichen - auf dem Formular ein eigener Abschnitt "falls
        # abweichend von Teilnehmer". Deshalb hier bewusst NUR bei Bedarf sichtbar (per
        # Checkbox), statt für jeden Teilnehmer 9 zusätzliche, meist leere Felder
        # anzuzeigen - im Normalfall (Halter = Hundeführer) bleibt der komplette Block
        # verborgen und alle halter_*-Felder in der Datenbank NULL.
        self.halter_weicht_ab = QCheckBox("Halter weicht vom Hundeführer ab")
        self.halter_weicht_ab.toggled.connect(self._halter_sichtbarkeit_aktualisieren)
        self.halter_vorname = QLineEdit()
        self.halter_nachname = QLineEdit()
        self.halter_strasse = QLineEdit()
        self.halter_hausnummer = QLineEdit()
        self.halter_plz = QLineEdit()
        self.halter_ort = QLineEdit()
        self.halter_mitgliedsverein = QLineEdit()
        self.halter_mitgliedsnummer = QLineEdit()
        self.halter_lu_nr = QLineEdit()

    def _layout_aufbauen(self) -> None:
        """Ordnet die in _felder_erstellen angelegten Widgets in Formularen/Gruppen an und
        setzt das Dialog-Layout (Gesamtinhalt scrollbar, siehe Kommentare unten)."""
        # Zwei Spalten nebeneinander statt einer langen Liste untereinander - bei allen
        # Feldern (inkl. der neuen Verwaltungs-/Kontaktfelder) ging das Fenster sonst in
        # der Höhe über den Bildschirm hinaus, ohne dass sich der Dialog scrollen ließ.
        # Links: Angaben zu Hundeführer/Verein/Anschrift/Kontakt (der/die Meldende).
        # Rechts: Angaben zu Hund und Prüfungsmeldung. Siehe auch Mockup-Absprache mit
        # Marco. Ein möglicher abweichender Halter bekommt einen eigenen, dritten Block
        # darunter (siehe gruppe_halter unten) statt hier mit hineinzumischen.
        form_links = QFormLayout()
        form_links.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form_links.addRow("Nachname*", self.nachname)
        form_links.addRow("Vorname*", self.vorname)
        form_links.addRow("Geburtsdatum (JJJJ-MM-TT)", self.geburtsdatum)
        form_links.addRow("Verein", self.verein)
        form_links.addRow("Verband", self.verband)
        form_links.addRow("Mitgliedsnummer", self.mitgliedsnummer)
        form_links.addRow("Straße", self.strasse)
        form_links.addRow("Hausnummer", self.hausnummer)
        form_links.addRow("PLZ", self.plz)
        form_links.addRow("Ort", self.ort)
        form_links.addRow("E-Mail", self.email)
        form_links.addRow("Telefonnummer", self.telefon)

        gruppe_links = QGroupBox("Hundeführer && Kontakt")
        gruppe_links.setLayout(form_links)

        form_rechts = QFormLayout()
        form_rechts.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form_rechts.addRow("Zwingername", self.zwingername)
        form_rechts.addRow("Rufname Hund*", self.rufname_hund)
        form_rechts.addRow("Rasse", self.rasse)
        form_rechts.addRow("Geschlecht", self.geschlecht)
        form_rechts.addRow("Widerristhöhe (cm)", self.schulterhoehe)
        form_rechts.addRow("Chip-Nr.", self.chip_nr)
        form_rechts.addRow("Wurftag (JJJJ-MM-TT)", self.wurftag)
        form_rechts.addRow("Tollwutimpfung gültig bis (JJJJ-MM-TT)", self.tollwutimpfung_bis)
        form_rechts.addRow("Startnummer", _startnummer_zeile(self.startnummer, self.startnummer_unbekannt))
        form_rechts.addRow("Art*", self.art)
        form_rechts.addRow("Leistungsklasse*", self.stufe)
        form_rechts.addRow("Disziplin (nur bei ED)", self.disziplin)
        form_rechts.addRow("Gegenstand 1", _gegenstand_zeile(self.gegenstand_1, self.gegenstand_1_disziplin))
        form_rechts.addRow("Gegenstand 2", _gegenstand_zeile(self.gegenstand_2, self.gegenstand_2_disziplin))
        form_rechts.addRow("Gegenstand 3", _gegenstand_zeile(self.gegenstand_3, self.gegenstand_3_disziplin))
        form_rechts.addRow("", self.bezahlt)

        gruppe_rechts = QGroupBox("Hund && Prüfung")
        gruppe_rechts.setLayout(form_rechts)

        # CI-Fund (21.09., echter Nutzertest): OHNE Stretch-Faktoren bekommt die linke
        # Spalte (weniger/kürzere Pflichtfelder) von QHBoxLayout viel zu wenig Platz
        # zugeteilt, sobald die rechte Spalte (mehr/breitere Felder wie das Datumsfeld
        # "Tollwutimpfung gültig bis") ihren natürlichen Platzbedarf einfordert - die
        # Eingabefelder links liefen dadurch sichtbar ab ("uver" statt "Bruver"). Mit
        # gleichem Stretch-Faktor (1:1) bekommen beide Spalten unabhängig von ihrem
        # jeweiligen Inhalt die Hälfte der verfügbaren Breite.
        spalten_zeile = QHBoxLayout()
        spalten_zeile.addWidget(gruppe_links, 1)
        spalten_zeile.addWidget(gruppe_rechts, 1)

        form_halter = QFormLayout()
        form_halter.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form_halter.addRow("Vorname", self.halter_vorname)
        form_halter.addRow("Name", self.halter_nachname)
        form_halter.addRow("Straße", self.halter_strasse)
        form_halter.addRow("Hausnummer", self.halter_hausnummer)
        form_halter.addRow("PLZ", self.halter_plz)
        form_halter.addRow("Ort", self.halter_ort)
        form_halter.addRow("Mitgliedsverein", self.halter_mitgliedsverein)
        form_halter.addRow("Mitgl.-Nr.", self.halter_mitgliedsnummer)
        form_halter.addRow("LU-Nr.", self.halter_lu_nr)

        self.gruppe_halter = QGroupBox("Halter (falls abweichend vom Hundeführer)")
        self.gruppe_halter.setLayout(form_halter)
        self.gruppe_halter.setVisible(False)  # nur bei Bedarf eingeblendet, siehe oben

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._pruefen_und_akzeptieren)
        buttons.rejected.connect(self.reject)

        # CI-Fund (21.09., echter Nutzertest): mit aufgeklapptem Halter-Block (siehe
        # gruppe_halter oben) reichte die feste Startgröße nicht mehr aus - der Block war
        # nicht komplett einsehbar und OK/Abbrechen lagen außerhalb des Bildschirms, ohne
        # Möglichkeit zu scrollen. Deshalb jetzt der komplette Formularinhalt (beide Spalten
        # + Halter-Block) in einem QScrollArea (Muster wie bereits in TerminZeitplanTab
        # verwendet) - nur OK/Abbrechen bleiben fest am unteren Rand, immer erreichbar,
        # unabhängig von Fenstergröße oder aufgeklapptem Halter-Block.
        inhalt_layout = QVBoxLayout()
        inhalt_layout.addLayout(spalten_zeile)
        inhalt_layout.addWidget(self.halter_weicht_ab)
        inhalt_layout.addWidget(self.gruppe_halter)
        inhalt_container = QWidget()
        inhalt_container.setLayout(inhalt_layout)

        inhalt_scroll = QScrollArea()
        inhalt_scroll.setWidget(inhalt_container)
        inhalt_scroll.setWidgetResizable(True)

        layout = QVBoxLayout(self)
        layout.addWidget(inhalt_scroll, 1)
        layout.addWidget(buttons)

        # Feste, bewusst gewählte Startgröße statt automatischer (zu hoher) Größe durch
        # die vielen Felder - passt dadurch auch auf kleinere Bildschirme (der Inhalt
        # scrollt jetzt bei Bedarf, siehe oben, statt abgeschnitten zu werden). Der Dialog
        # bleibt frei in der Größe änderbar UND jetzt auch maximierbar (CI-Fund 21.09.:
        # QDialog zeigt standardmäßig keinen Maximieren-Button, obwohl der Nutzer bei
        # einer Menge Felder/aufgeklapptem Halter-Block mehr Platz braucht als die
        # Startgröße bietet).
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
        self.resize(780, 640)

    def _vorbelegung_uebernehmen(self, vorhandener: dict) -> None:
        """Übernimmt beim Bearbeiten eines vorhandenen Teilnehmers dessen Werte in die
        zuvor per _felder_erstellen angelegten Eingabefelder."""
        self.nachname.setText(vorhandener["nachname"])
        self.vorname.setText(vorhandener["vorname"])
        self.geburtsdatum.setText(vorhandener["geburtsdatum"] or "")
        self.verein.setText(vorhandener["verein"] or "")
        self.verband.setText(vorhandener["verband"] or "")
        self.mitgliedsnummer.setText(vorhandener["mitgliedsnummer"] or "")
        self.strasse.setText(vorhandener["strasse"] or "")
        self.hausnummer.setText(vorhandener["hausnummer"] or "")
        self.plz.setText(vorhandener["plz"] or "")
        self.ort.setText(vorhandener["ort"] or "")
        self.email.setText(vorhandener["email"] or "")
        self.telefon.setText(vorhandener["telefon"] or "")
        self.zwingername.setText(vorhandener["zwingername"] or "")
        self.rufname_hund.setText(vorhandener["rufname_hund"])
        if vorhandener["geschlecht"]:
            self.geschlecht.setCurrentText(vorhandener["geschlecht"])
        self.schulterhoehe.setValue(vorhandener["schulterhoehe_cm"] or 0)
        self.chip_nr.setText(vorhandener["chip_nr"] or "")
        self.rasse.setText(vorhandener["rasse"] or "")
        self.wurftag.setText(vorhandener["wurftag"] or "")
        self.tollwutimpfung_bis.setText(vorhandener["tollwutimpfung_bis"] or "")
        if vorhandener["startnummer"] is not None:
            self.startnummer.setValue(vorhandener["startnummer"])
        else:
            self.startnummer_unbekannt.setChecked(True)
        self.art.setCurrentText(vorhandener["art"])
        self.stufe.setCurrentText(str(vorhandener["stufe"]))
        if vorhandener["disziplin"]:
            self.disziplin.setCurrentText(vorhandener["disziplin"])
        self.gegenstand_1.setText(vorhandener["gegenstand_1"] or "")
        self.gegenstand_2.setText(vorhandener["gegenstand_2"] or "")
        self.gegenstand_3.setText(vorhandener["gegenstand_3"] or "")
        self.gegenstand_1_disziplin.setCurrentText(vorhandener["gegenstand_1_disziplin"] or _GEGENSTAND_ZUORDNUNG_FREI)
        self.gegenstand_2_disziplin.setCurrentText(vorhandener["gegenstand_2_disziplin"] or _GEGENSTAND_ZUORDNUNG_FREI)
        self.gegenstand_3_disziplin.setCurrentText(vorhandener["gegenstand_3_disziplin"] or _GEGENSTAND_ZUORDNUNG_FREI)
        self.bezahlt.setChecked(bool(vorhandener["bezahlt"]))
        # Ein Halter-Datensatz gilt als "abweichend" hinterlegt, sobald mindestens
        # eines der halter_*-Felder gesetzt ist - dann Block gleich aufklappen, statt
        # bereits erfasste Angaben hinter der Checkbox zu verstecken.
        halter_felder = {
            "halter_vorname": self.halter_vorname, "halter_nachname": self.halter_nachname,
            "halter_strasse": self.halter_strasse, "halter_hausnummer": self.halter_hausnummer,
            "halter_plz": self.halter_plz, "halter_ort": self.halter_ort,
            "halter_mitgliedsverein": self.halter_mitgliedsverein,
            "halter_mitgliedsnummer": self.halter_mitgliedsnummer, "halter_lu_nr": self.halter_lu_nr,
        }
        for spalte, feld in halter_felder.items():
            feld.setText(vorhandener[spalte] or "")
        self.halter_weicht_ab.setChecked(any(vorhandener[spalte] for spalte in halter_felder))

    def _halter_sichtbarkeit_aktualisieren(self, abweichend: bool) -> None:
        self.gruppe_halter.setVisible(abweichend)

    def _startnummer_verfuegbarkeit_aktualisieren(self, unbekannt: bool) -> None:
        self.startnummer.setEnabled(not unbekannt)

    def _art_geaendert(self, art: str) -> None:
        # Disziplin ist nur bei Einzeldisziplin (ED) relevant/erlaubt
        self.disziplin.setEnabled(art == "ED")

    def _pruefen_und_akzeptieren(self) -> None:
        if not self.nachname.text().strip() or not self.vorname.text().strip() or not self.rufname_hund.text().strip():
            QMessageBox.warning(self, "Fehlende Angaben", "Nachname, Vorname und Rufname des Hundes sind Pflichtfelder.")
            return
        if not self.startnummer_unbekannt.isChecked() and self.startnummer.value() in self._vergebene_nummern:
            nummer = self.startnummer.value()
            inhaber = self._namen_je_startnummer.get(nummer)
            zusatz = f" (aktuell: {inhaber})" if inhaber else ""
            QMessageBox.warning(
                self, "Startnummer bereits vergeben",
                f"Die Startnummer {nummer} ist bereits einem anderen Teilnehmer zugeteilt{zusatz}.\n\n"
                "Bitte eine andere Startnummer wählen, das Häkchen „Startnummer steht noch nicht "
                "fest“ setzen, oder die beiden Startnummern anschließend über „Startnummer "
                "tauschen…“ in der Teilnehmerliste direkt miteinander tauschen.",
            )
            return
        # QS-Review (19./20.09.): Jede Disziplin darf nur EINEM der drei Gegenstand-Felder
        # zugeordnet sein - sonst würde gegenstand_fuer_disziplin() (db.py) für diese
        # Disziplin nur den ersten der beiden Treffer liefern und der zweite Gegenstand
        # spurlos verschwinden (z.B. auf dem Bewertungsbogen). Das ist unabhängig von der
        # Leistungsklasse: dass DERSELBE Gegenstand für mehrere Disziplinen gesucht wird
        # (z.B. LK1: 1 Gegenstand in allen 3 Disziplinen, LK2: 1 Gegenstand in bis zu 2
        # Disziplinen), bildet man ab, indem man den GLEICHEN Text in mehrere Gegenstand-
        # Felder einträgt, jedes davon mit einer ANDEREN Disziplin-Zuordnung - das bleibt
        # hier ausdrücklich erlaubt und wird von dieser Prüfung nicht angerührt. Verboten ist
        # nur, dieselbe Disziplin zweimal zu vergeben (siehe Absprache mit Marco).
        vergebene_disziplinen = [
            d for d in (
                self.gegenstand_1_disziplin.currentText(),
                self.gegenstand_2_disziplin.currentText(),
                self.gegenstand_3_disziplin.currentText(),
            )
            if d != _GEGENSTAND_ZUORDNUNG_FREI
        ]
        doppelt_vergeben = sorted({d for d in vergebene_disziplinen if vergebene_disziplinen.count(d) > 1})
        if doppelt_vergeben:
            QMessageBox.warning(
                self, "Gegenstand-Zuordnung doppelt vergeben",
                "Zwei der drei Gegenstände sind derselben Disziplin zugeordnet: "
                f"{', '.join(doppelt_vergeben)}.\n\n"
                "Jede Disziplin darf nur einem der drei Gegenstand-Felder zugeordnet werden. "
                "Soll derselbe Gegenstand in mehreren Disziplinen gesucht werden, bitte den "
                "gleichen Text in mehrere Gegenstand-Felder eintragen und dort jeweils eine "
                "andere Disziplin zuordnen.",
            )
            return
        self.accept()

    def ergebnis(self) -> NeuerTeilnehmer:
        return NeuerTeilnehmer(
            nachname=self.nachname.text().strip(),
            vorname=self.vorname.text().strip(),
            rufname_hund=self.rufname_hund.text().strip(),
            art=self.art.currentText(),
            stufe=int(self.stufe.currentText()),
            disziplin=self.disziplin.currentText() if self.art.currentText() == "ED" else None,
            verein=self.verein.text().strip() or None,
            zwingername=self.zwingername.text().strip() or None,
            geschlecht=self.geschlecht.currentText(),
            schulterhoehe_cm=self.schulterhoehe.value() or None,
            chip_nr=self.chip_nr.text().strip() or None,
            rasse=self.rasse.text().strip() or None,
            tollwutimpfung_bis=self.tollwutimpfung_bis.text().strip() or None,
            geburtsdatum=self.geburtsdatum.text().strip() or None,
            startnummer=None if self.startnummer_unbekannt.isChecked() else self.startnummer.value(),
            gegenstand_1=self.gegenstand_1.text().strip() or None,
            gegenstand_2=self.gegenstand_2.text().strip() or None,
            gegenstand_3=self.gegenstand_3.text().strip() or None,
            gegenstand_1_disziplin=_zuordnung_oder_none(self.gegenstand_1_disziplin),
            gegenstand_2_disziplin=_zuordnung_oder_none(self.gegenstand_2_disziplin),
            gegenstand_3_disziplin=_zuordnung_oder_none(self.gegenstand_3_disziplin),
            bezahlt=self.bezahlt.isChecked(),
            verband=self.verband.text().strip() or None,
            mitgliedsnummer=self.mitgliedsnummer.text().strip() or None,
            wurftag=self.wurftag.text().strip() or None,
            strasse=self.strasse.text().strip() or None,
            hausnummer=self.hausnummer.text().strip() or None,
            plz=self.plz.text().strip() or None,
            ort=self.ort.text().strip() or None,
            email=self.email.text().strip() or None,
            telefon=self.telefon.text().strip() or None,
            # Nur übernehmen, wenn die Checkbox aktiv ist - so bleibt ein versehentlich
            # eingetragener und dann per Checkbox wieder verworfener Halter-Text nicht
            # trotzdem in der Datenbank hängen (siehe _halter_sichtbarkeit_aktualisieren).
            halter_vorname=self.halter_vorname.text().strip() or None if self.halter_weicht_ab.isChecked() else None,
            halter_nachname=self.halter_nachname.text().strip() or None if self.halter_weicht_ab.isChecked() else None,
            halter_strasse=self.halter_strasse.text().strip() or None if self.halter_weicht_ab.isChecked() else None,
            halter_hausnummer=self.halter_hausnummer.text().strip() or None if self.halter_weicht_ab.isChecked() else None,
            halter_plz=self.halter_plz.text().strip() or None if self.halter_weicht_ab.isChecked() else None,
            halter_ort=self.halter_ort.text().strip() or None if self.halter_weicht_ab.isChecked() else None,
            halter_mitgliedsverein=(
                self.halter_mitgliedsverein.text().strip() or None if self.halter_weicht_ab.isChecked() else None
            ),
            halter_mitgliedsnummer=(
                self.halter_mitgliedsnummer.text().strip() or None if self.halter_weicht_ab.isChecked() else None
            ),
            halter_lu_nr=self.halter_lu_nr.text().strip() or None if self.halter_weicht_ab.isChecked() else None,
        )


class StartnummerTauschenDialog(QDialog):
    """Tauscht die Startnummer eines Teilnehmers mit der eines anderen - löst gezielt das
    in der Anmerkung vom 20.09. geschilderte Problem, dass man eine gewünschte, bereits
    vergebene Startnummer bisher erst manuell an anderer Stelle 'freimachen' musste,
    bevor man sie neu vergeben konnte. Führt selbst keine Feldprüfung durch - die eigentliche
    Vertauschung übernimmt db.tausche_startnummern() atomar."""

    def __init__(self, parent, teilnehmer: dict, andere_teilnehmer: list[dict]):
        super().__init__(parent)
        self.setWindowTitle("Startnummer tauschen")
        eigene_nummer = teilnehmer["startnummer"]
        eigene_anzeige = str(eigene_nummer) if eigene_nummer is not None else "keine"
        hinweis = QLabel(
            f"Startnummer von {teilnehmer['nachname']}, {teilnehmer['vorname']} "
            f"(aktuell: {eigene_anzeige}) tauschen mit:"
        )
        hinweis.setWordWrap(True)

        self.partner_combo = QComboBox()
        for t in sorted(andere_teilnehmer, key=lambda t: (t["startnummer"] is None, t["startnummer"] or 0)):
            nummer_anzeige = str(t["startnummer"]) if t["startnummer"] is not None else "keine"
            self.partner_combo.addItem(
                f"{t['nachname']}, {t['vorname']} (Start-Nr. {nummer_anzeige})", t["id"]
            )

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(hinweis)
        layout.addWidget(self.partner_combo)
        layout.addWidget(buttons)

    def ausgewaehlte_partner_id(self) -> int | None:
        return self.partner_combo.currentData()


class TerminImportDialog(QDialog):
    """Übernimmt ausgewählte Teilnehmer-STAMMDATEN aus einem anderen Termin in den aktuell
    geöffneten (Nutzerwunsch 20.09., Anmerkung zum Programm: 'Teilnehmer müssen wieder
    einzeln eingegeben werden [...] ist Option möglich, von anderem Termin importieren?').
    Öffnet dafür kurzzeitig eine ZWEITE, separate Verbindung zur gewählten Quell-Termin-
    Datei (siehe _termin_gewaehlt/schliesse_quelle) - der aktuell geöffnete Termin (in
    dessen Tab dieser Dialog geöffnet wurde) bleibt davon komplett unberührt, es wird
    ausschließlich per db.importiere_teilnehmer_stammdaten() gezielt in ihn hinein
    geschrieben. Bewusst NICHT wiederverwendet wird kopiere_termin_daten() (Web-Sync) - die
    kopiert einen kompletten Termin 1:1 inkl. Startnummer/Ergebnis/Bezahlt-Status, hier soll
    aber gezielt nur eine Auswahl an dauerhaften Stammdaten übernommen werden (Absprache mit
    dem Nutzer)."""

    def __init__(self, parent, aktueller_pfad: str | None):
        super().__init__(parent)
        self.setWindowTitle("Teilnehmer aus anderem Termin importieren")
        self.resize(560, 480)
        self._quelle_conn: sqlite3.Connection | None = None
        self._termine = [t for t in liste_termine() if t.lesbar and t.pfad != aktueller_pfad]

        self.termin_combo = QComboBox()
        for t in self._termine:
            self.termin_combo.addItem(
                f"{t.verein or '(ohne Verein)'} – {t.datum} ({t.anzahl_teilnehmer} Teilnehmer)"
            )
        self.termin_combo.currentIndexChanged.connect(self._termin_gewaehlt)

        self.teilnehmer_liste = QListWidget()

        alle_btn = QPushButton("Alle auswählen")
        alle_btn.clicked.connect(lambda: self._alle_umschalten(Qt.Checked))
        keine_btn = QPushButton("Keine auswählen")
        keine_btn.clicked.connect(lambda: self._alle_umschalten(Qt.Unchecked))
        auswahl_zeile = QHBoxLayout()
        auswahl_zeile.addWidget(alle_btn)
        auswahl_zeile.addWidget(keine_btn)
        auswahl_zeile.addStretch()

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        if not self._termine:
            layout.addWidget(QLabel("Kein anderer Termin gefunden, aus dem importiert werden könnte."))
            self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)
        else:
            layout.addWidget(QLabel("Termin, aus dem importiert werden soll:"))
            layout.addWidget(self.termin_combo)
            layout.addWidget(QLabel(
                "Zu importierende Teilnehmer (nur Stammdaten - Startnummer, Gegenstände, "
                "Bezahlt-Status und Ergebnis werden bewusst NICHT übernommen):"
            ))
            layout.addLayout(auswahl_zeile)
            layout.addWidget(self.teilnehmer_liste)
        layout.addWidget(self.buttons)

        if self._termine:
            self._termin_gewaehlt(0)

    def _termin_gewaehlt(self, index: int) -> None:
        if self._quelle_conn is not None:
            self._quelle_conn.close()
            self._quelle_conn = None
        self.teilnehmer_liste.clear()
        if not (0 <= index < len(self._termine)):
            return
        self._quelle_conn = init_db(self._termine[index].pfad)
        for t in list_teilnehmer(self._quelle_conn):
            text = f"{t['nachname']}, {t['vorname']} – {t['rufname_hund']} ({leistungsklasse_label(t)})"
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            item.setData(Qt.UserRole, t["id"])
            self.teilnehmer_liste.addItem(item)

    def _alle_umschalten(self, zustand) -> None:
        for row in range(self.teilnehmer_liste.count()):
            self.teilnehmer_liste.item(row).setCheckState(zustand)

    def ausgewaehlte_ids(self) -> list[int]:
        return [
            self.teilnehmer_liste.item(row).data(Qt.UserRole)
            for row in range(self.teilnehmer_liste.count())
            if self.teilnehmer_liste.item(row).checkState() == Qt.Checked
        ]

    def quelle_conn(self) -> sqlite3.Connection | None:
        return self._quelle_conn

    def schliesse_quelle(self) -> None:
        """Muss vom Aufrufer nach exec() gerufen werden (egal ob akzeptiert oder
        abgebrochen), damit die zweite, nur für den Import geöffnete Verbindung nicht
        offen bleibt."""
        if self._quelle_conn is not None:
            self._quelle_conn.close()
            self._quelle_conn = None


class _NumerischSortierbaresItem(QTableWidgetItem):
    """QTableWidgetItem für die Start-Nr.-Spalte der Teilnehmerliste: sortiert nach einem
    echten Zahlenwert (2 vor 10) statt nach dem angezeigten Text ("10" vor "2").

    Der naheliegendere Ansatz - `item.setData(Qt.DisplayRole, zahl)` und sich auf Qts
    eingebauten Vergleich (QTableWidgetItem.operator<, liest Qt.DisplayRole) zu verlassen
    - sortiert in einem echten CI-Lauf (PySide6/Qt6) NICHT numerisch, sondern weiterhin
    rein alphabetisch (per CI-Fund am 20.09. entdeckt, siehe Fortschritt.md; lokal ohne
    installiertes PySide6 nicht überprüfbar gewesen). Stattdessen hier `__lt__` direkt
    überschrieben - das ist der Vergleich, den `QTableWidget.sortItems()`/`sortByColumn()`
    tatsächlich aufruft, unabhängig von Datenrollen-Feinheiten."""

    def __init__(self, text: str, sortierwert: int) -> None:
        super().__init__(text)
        self._sortierwert = sortierwert

    def __lt__(self, other) -> bool:  # noqa: D105 - siehe Klassen-Docstring
        if isinstance(other, _NumerischSortierbaresItem):
            return self._sortierwert < other._sortierwert
        return super().__lt__(other)


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
            ["Start-Nr.", "Nachname", "Vorname", "Hund", "Art/LK", "Verein", "Bezahlt", "Vollständig"]
        )
        self.tabelle.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabelle.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabelle.setSelectionMode(QTableWidget.SingleSelection)
        self.tabelle.itemSelectionChanged.connect(self._auswahl_geaendert)
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

        hinzufuegen_btn = QPushButton("Teilnehmer hinzufügen…")
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

        # Nutzerwunsch (20.09.): Startnummern zweier Teilnehmer direkt tauschen können,
        # statt eine gewünschte, bereits vergebene Nummer erst manuell an anderer Stelle
        # "freimachen" zu müssen.
        self.tauschen_btn = QPushButton("Startnummer tauschen…")
        self.tauschen_btn.clicked.connect(self._startnummer_tauschen)
        self.tauschen_btn.setEnabled(False)

        # Nutzerwunsch (20.09., Anmerkung zum Programm): "Teilnehmer müssen wieder einzeln
        # eingegeben werden [...] ist Option möglich, von anderem Termin importieren?" -
        # übernimmt gezielt Stammdaten (nicht Startnummer/Gegenstände/Bezahlt-Status/
        # Ergebnis) aus einem anderen, bereits vorhandenen Termin.
        import_btn = QPushButton("Aus anderem Termin importieren…")
        import_btn.clicked.connect(self._aus_anderem_termin_importieren)

        # Nutzerwunsch (21.09.): "In Teilnehmerliste Absprung zu Bewertungsbögen erzeugen
        # einfügen?" - Entscheidung (Rückfrage beantwortet): Direkt-Button pro Teilnehmer
        # statt nur eines Links zum Export-Tab, erzeugt sofort den Bewertungsbogen für den
        # ausgewählten Teilnehmer (siehe _bewertungsbogen_exportieren unten).
        self.bewertungsbogen_btn = QPushButton("Bewertungsbogen (PDF)…")
        self.bewertungsbogen_btn.clicked.connect(self._bewertungsbogen_exportieren)
        self.bewertungsbogen_btn.setEnabled(False)

        button_zeile = QHBoxLayout()
        button_zeile.addWidget(hinzufuegen_btn)
        button_zeile.addWidget(self.bearbeiten_btn)
        button_zeile.addWidget(self.loeschen_btn)
        button_zeile.addWidget(self.bezahlt_btn)
        button_zeile.addWidget(self.tauschen_btn)
        button_zeile.addWidget(import_btn)
        button_zeile.addWidget(self.bewertungsbogen_btn)
        button_zeile.addStretch()

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
        self.status_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addLayout(filter_zeile)
        layout.addWidget(self.tabelle)
        layout.addLayout(button_zeile)
        layout.addWidget(self.status_label)

        self.aktualisieren()

    def _ausgewaehlte_id(self) -> int | None:
        zeile = self.tabelle.currentRow()
        item = self.tabelle.item(zeile, 0)
        return item.data(Qt.UserRole) if item is not None else None

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

    def _auswahl_geaendert(self) -> None:
        hat_auswahl = self._ausgewaehlte_id() is not None
        self.bearbeiten_btn.setEnabled(hat_auswahl)
        self.loeschen_btn.setEnabled(hat_auswahl)
        self.bezahlt_btn.setEnabled(hat_auswahl)
        self.tauschen_btn.setEnabled(hat_auswahl and len(self._teilnehmer_je_zeile) > 1)
        self.bewertungsbogen_btn.setEnabled(hat_auswahl)

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
            naechste_nummer=naechste_freie_startnummer(self.conn),
            namen_je_startnummer=self._namen_je_startnummer(),
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
        )
        if dialog.exec() == QDialog.Accepted:
            try:
                update_teilnehmer(self.conn, teilnehmer_id, dialog.ergebnis())
            except sqlite3.IntegrityError as exc:
                _fehler_anzeigen(self, exc)
                return
            self.aktualisieren()

    def _startnummer_tauschen(self) -> None:
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
            if partner_id is not None:
                try:
                    tausche_startnummern(self.conn, teilnehmer_id, partner_id)
                except sqlite3.IntegrityError as exc:
                    _fehler_anzeigen(self, exc)
                    return
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
        self.status_label.setText(f"Bewertungsbogen gespeichert: {pfad}")

    def _teilnehmer_loeschen(self) -> None:
        teilnehmer_id = self._ausgewaehlte_id()
        if teilnehmer_id is None:
            return
        zeile = self.tabelle.currentRow()
        name = f"{self.tabelle.item(zeile, 1).text()}, {self.tabelle.item(zeile, 2).text()}"
        antwort = QMessageBox.question(
            self,
            "Teilnehmer löschen",
            f"Teilnehmer „{name}“ inklusive erfasstem Ergebnis wirklich unwiderruflich löschen?",
        )
        if antwort == QMessageBox.Yes:
            delete_teilnehmer(self.conn, teilnehmer_id)
            self.aktualisieren()

    def _bezahlt_umschalten(self) -> None:
        teilnehmer_id = self._ausgewaehlte_id()
        if teilnehmer_id is None:
            return
        aktuell = next(t for t in list_teilnehmer(self.conn) if t["id"] == teilnehmer_id)
        try:
            setze_bezahlt(self.conn, teilnehmer_id, not aktuell["bezahlt"])
        except sqlite3.IntegrityError as exc:
            _fehler_anzeigen(self, exc)
            return
        self.aktualisieren()

    def aktualisieren(self) -> None:
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
                bezahlt_item.setForeground(QColor("#1E8E5A"))
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
            fehlend = teilnehmer_fehlende_pflichtangaben(t)
            if fehlend:
                vollstaendig_item = QTableWidgetItem("⚠ " + "; ".join(fehlend))
                vollstaendig_item.setForeground(QColor("#b56a00"))
                vollstaendig_item.setToolTip("Fehlt noch: " + "; ".join(fehlend))
                schrift = vollstaendig_item.font()
                schrift.setBold(True)
                vollstaendig_item.setFont(schrift)
            else:
                hinweis = teilnehmer_gegenstand_hinweis(t)
                vollstaendig_item = QTableWidgetItem(hinweis or "")
                if hinweis:
                    vollstaendig_item.setToolTip(hinweis)
                    schrift = vollstaendig_item.font()
                    schrift.setPointSize(max(schrift.pointSize() - 1, 1))
                    vollstaendig_item.setFont(schrift)
            self.tabelle.setItem(row, 7, vollstaendig_item)
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
        self._auswahl_geaendert()

        # Filter-Auswahl beim Neuladen nach Möglichkeit beibehalten, statt immer auf
        # "Alle" zurückzuspringen (entspricht ErgebnisTab.aktualisieren).
        bisherige_auswahl = self.filter_combo.currentText()
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItem("Alle")
        self.filter_combo.addItems(alle_leistungsklassen(self.conn))
        index = self.filter_combo.findText(bisherige_auswahl)
        self.filter_combo.setCurrentIndex(index if index >= 0 else 0)
        self.filter_combo.blockSignals(False)
        self._filter_anwenden()


def _formular_import_prompt() -> str:
    """Baut den Kopier-Prompt für den Reiter 'Formular-Import' (siehe FormularImportTab)
    aus CSV_IMPORT_SPALTEN (db.py) - so können Prompt-Text und CSV-Parser
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
    offline arbeitet und keinen eigenen KI-Zugriff hat."""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn

        anleitung = QLabel(
            "1. Prompt unten kopieren und zusammen mit dem ausgefüllten Meldeformular "
            "(PDF, Word-Dokument oder Foto/Scan) einem KI-System übergeben (z. B. Claude "
            "oder ChatGPT).\n"
            "2. Die dabei erzeugte CSV-Datei hier importieren - neue Teilnehmer erscheinen "
            "danach im Reiter „Teilnehmer“."
        )
        anleitung.setWordWrap(True)

        self.prompt_feld = QPlainTextEdit(_formular_import_prompt())
        self.prompt_feld.setReadOnly(True)
        self.prompt_feld.setLineWrapMode(QPlainTextEdit.WidgetWidth)

        kopieren_btn = QPushButton("Prompt kopieren")
        kopieren_btn.clicked.connect(self._prompt_kopieren)
        self.status_label = QLabel("")

        import_btn = QPushButton("CSV importieren…")
        import_btn.setObjectName("primaerButton")
        import_btn.clicked.connect(self._csv_importieren)

        button_zeile = QHBoxLayout()
        button_zeile.addWidget(kopieren_btn)
        button_zeile.addWidget(self.status_label)
        button_zeile.addStretch()
        button_zeile.addWidget(import_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(anleitung)
        layout.addWidget(self.prompt_feld)
        layout.addLayout(button_zeile)

    def _prompt_kopieren(self) -> None:
        QApplication.clipboard().setText(self.prompt_feld.toPlainText())
        self.status_label.setText("Prompt kopiert.")

    def _csv_importieren(self) -> None:
        pfad, _ = QFileDialog.getOpenFileName(self, "CSV importieren", "", "CSV-Datei (*.csv)")
        if not pfad:
            return
        try:
            ergebnis = importiere_teilnehmer_aus_csv(self.conn, pfad)
        except OSError as exc:
            QMessageBox.warning(self, "Import fehlgeschlagen", f"Die Datei konnte nicht gelesen werden:\n{exc}")
            return
        text = f"{ergebnis.importiert} Teilnehmer importiert."
        if ergebnis.fehler:
            text += f"\n\n{len(ergebnis.fehler)} Zeile(n) übersprungen:\n" + "\n".join(ergebnis.fehler)
        QMessageBox.information(self, "Import abgeschlossen", text)


FARBE_UNGESPEICHERT = QColor("#fff3cd")   # dezentes Gelb - Zeile hat noch nicht gespeicherte Änderungen
FARBE_GESPEICHERT = QColor("white")


def _zentrierte_zelle(widget: QWidget) -> QWidget:
    """Bettet `widget` (z.B. eine QCheckBox) in einen kleinen Container mit zentriertem
    Layout ein - als setCellWidget-Inhalt einer QTableWidget-Zelle, da eine QCheckBox
    allein dort automatisch linksbündig erscheint. Siehe ErgebnisTab (Disqualifiziert-/
    Abbruch-Spalten)."""
    zelle = QWidget()
    # Ein einfaches QWidget malt seinen per Stylesheet gesetzten Hintergrund (siehe
    # _aktualisiere_zeilenstatus) standardmäßig NICHT selbst - anders als z.B. QLineEdit,
    # das seinen Hintergrund ohnehin über den Stil zeichnet. WA_StyledBackground schaltet
    # das für dieses Widget gezielt ein.
    zelle.setAttribute(Qt.WA_StyledBackground, True)
    layout = QHBoxLayout(zelle)
    layout.addWidget(widget)
    layout.setAlignment(Qt.AlignCenter)
    layout.setContentsMargins(0, 0, 0, 0)
    return zelle

# Spaltenreihenfolge in der Ergebniserfassung: je Disziplin ein Such-/Anzeigeleistungs-Paar,
# alle drei nebeneinander in einer Zeile - bei DK sind alle drei aktiv, bei ED nur die
# jeweils zutreffende (die anderen beiden Spalten bleiben leer/gesperrt).
_ERGEBNIS_SPALTEN_JE_DISZIPLIN = {
    disziplin: (3 + 2 * i, 3 + 2 * i + 1) for i, disziplin in enumerate(ALLE_DISZIPLINEN)
}
# Nutzerwunsch (21.09.): zwei zusätzliche Spalten für die unabhängigen Status
# "Disqualifiziert"/"Abbruch", vor der bestehenden Status-Spalte (die den
# gespeichert/nicht-gespeichert-Hinweis dieser Zeile zeigt, siehe _aktualisiere_zeilenstatus).
_DQ_SPALTE = 3 + 2 * len(ALLE_DISZIPLINEN)
_ABBRUCH_SPALTE = _DQ_SPALTE + 1
_STATUS_SPALTE = _ABBRUCH_SPALTE + 1


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

        spalten = ["Start-Nr.", "Name", "Art/LK"]
        for disziplin in ALLE_DISZIPLINEN:
            spalten += [f"{disziplin} – Suche (0-60)", f"{disziplin} – Anzeige (0-40)"]
        spalten += ["Disqualifiziert", "Abbruch", "Status"]

        self.tabelle = QTableWidget(0, len(spalten))
        self.tabelle.setHorizontalHeaderLabels(spalten)
        self.tabelle.horizontalHeader().setStretchLastSection(True)
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

        speichern_btn = QPushButton("Alle Ergebnisse speichern")
        speichern_btn.setObjectName("primaerButton")  # Haupt-Aktion dieses Reiters, siehe _QSS_TEMPLATE
        speichern_btn.clicked.connect(self.alle_speichern)

        aktualisieren_btn = QPushButton("Liste aktualisieren")
        aktualisieren_btn.clicked.connect(self._aktualisieren_mit_rueckfrage)

        self.status_label = QLabel("")

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

    def aktualisieren(self) -> None:
        """Baut die Tabelle komplett neu aus der Datenbank auf (verwirft dabei nicht
        gespeicherte Änderungen!) und aktualisiert den Filter. Wird beim ersten Öffnen
        sowie über "Liste aktualisieren" aufgerufen. Die zuletzt per Spaltenklick
        gewählte Sortierung bleibt dabei erhalten (siehe _zeilen_aufbauen)."""
        self._teilnehmer_je_zeile = list_teilnehmer(self.conn)
        self._zeilen_aufbauen()

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

    def _zeilen_aufbauen(
        self,
        werte_override: dict[int, dict[str, tuple[int | None, int | None]]] | None = None,
        status_override: dict[int, tuple[bool, bool]] | None = None,
    ) -> None:
        """Baut die Tabellenzeilen aus `self._teilnehmer_je_zeile` (in dessen aktueller
        Reihenfolge) komplett neu auf - gemeinsam genutzt von aktualisieren() (frisch aus
        der DB, keine Overrides) und _sortieren_und_neu_aufbauen() (Overrides = die vor
        dem Sortieren gesicherten, ggf. noch nicht gespeicherten Eingaben je Teilnehmer-
        ID). `werte_override`/`status_override` überschreiben dabei nur die ANGEZEIGTEN
        Werte - `_geladen_je_zeile`/`_status_geladen_je_zeile` bleiben trotzdem auf dem
        zuletzt aus der DB gelesenen (= gespeicherten) Stand, damit der
        "ungespeichert"-Vergleich (siehe _zeile_ist_ungespeichert) korrekt bleibt."""
        ergebnis_rows = {
            r["teilnehmer_id"]: dict(r)
            for r in self.conn.execute("SELECT * FROM ergebnisse").fetchall()
        }
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
            self.tabelle.setItem(row, 2, QTableWidgetItem(leistungsklasse_label(t)))

            boxen: dict[str, tuple[QLineEdit, QLineEdit]] = {}
            geladen: dict[str, tuple[int | None, int | None]] = {}
            for disziplin in ALLE_DISZIPLINEN:
                spalte_suche, spalte_anzeige = _ERGEBNIS_SPALTEN_JE_DISZIPLIN[disziplin]
                if disziplin not in zutreffende_disziplinen:
                    # Disziplin gilt für diesen Teilnehmer nicht (ED) - Zellen leer/gesperrt lassen.
                    for spalte in (spalte_suche, spalte_anzeige):
                        leer = QTableWidgetItem("–")
                        leer.setFlags(leer.flags() & ~Qt.ItemIsEditable)
                        leer.setForeground(QColor("gray"))
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
                suche_feld.setValidator(QIntValidator(0, 60, suche_feld))
                suche_feld.setAlignment(Qt.AlignCenter)
                if angezeigt_suche is not None:
                    suche_feld.setText(str(angezeigt_suche))
                self.tabelle.setCellWidget(row, spalte_suche, suche_feld)

                anzeige_feld = QLineEdit()
                anzeige_feld.setValidator(QIntValidator(0, 40, anzeige_feld))
                anzeige_feld.setAlignment(Qt.AlignCenter)
                if angezeigt_anzeige is not None:
                    anzeige_feld.setText(str(angezeigt_anzeige))
                self.tabelle.setCellWidget(row, spalte_anzeige, anzeige_feld)

                suche_feld.textChanged.connect(lambda _text, r=row: self._aktualisiere_zeilenstatus(r))
                anzeige_feld.textChanged.connect(lambda _text, r=row: self._aktualisiere_zeilenstatus(r))

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
            self._punkteeingabe_sperren(row, angezeigt_dq or angezeigt_abbruch)
            self._aktualisiere_zeilenstatus(row)

        # Spaltenbreiten an den tatsächlichen Inhalt/Spaltenkopf anpassen, damit z.B.
        # lange Namen oder LK-Bezeichnungen nicht abgeschnitten werden - danach bleiben
        # die Spalten weiterhin von Hand nachziehbar.
        self.tabelle.resizeColumnsToContents()

    def _spalte_geklickt(self, spalte: int) -> None:
        """Reagiert auf einen Klick auf eine Spaltenüberschrift: sortiert danach, erneuter
        Klick auf dieselbe Spalte kehrt die Richtung um (siehe Klassen-/Konstruktor-
        Docstring zur Begründung der eigenen Sortierlogik statt Qt-Bordmittel)."""
        if self._sortierspalte == spalte:
            self._sortieraufsteigend = not self._sortieraufsteigend
        else:
            self._sortierspalte = spalte
            self._sortieraufsteigend = True
        self._sortieren_und_neu_aufbauen()

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

    def _sortieren_und_neu_aufbauen(self) -> None:
        """Sortiert self._teilnehmer_je_zeile nach der zuletzt gewählten Spalte/Richtung
        und baut die Tabelle neu auf - sichert VORHER die aktuellen (ggf. noch nicht
        gespeicherten) Eingaben je Teilnehmer-ID, damit beim Neuaufbau keine ungespeicherte
        Eingabe verloren geht (siehe Klassen-/Konstruktor-Docstring)."""
        werte_je_id = {
            t["id"]: {
                disziplin: (self._feldwert(suche_feld), self._feldwert(anzeige_feld))
                for disziplin, (suche_feld, anzeige_feld) in self._boxen_je_zeile[row].items()
            }
            for row, t in enumerate(self._teilnehmer_je_zeile)
        }
        status_je_id = {
            t["id"]: (dq_box.isChecked(), abbruch_box.isChecked())
            for t, (dq_box, abbruch_box) in zip(self._teilnehmer_je_zeile, self._status_boxen_je_zeile)
        }

        reihenfolge = sorted(
            range(len(self._teilnehmer_je_zeile)),
            key=lambda row: self._sortierschluessel_fuer_zeile(row, self._sortierspalte),
            reverse=not self._sortieraufsteigend,
        )
        self._teilnehmer_je_zeile = [self._teilnehmer_je_zeile[i] for i in reihenfolge]

        self._zeilen_aufbauen(werte_je_id, status_je_id)
        self._filter_anwenden()

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

    def _aktualisiere_zeilenstatus(self, row: int) -> None:
        """Färbt die Zeile gelb und setzt den Status-Text, solange sich mindestens ein
        Wert vom zuletzt gespeicherten Stand unterscheidet."""
        ungespeichert = self._zeile_ist_ungespeichert(row)
        farbe = FARBE_UNGESPEICHERT if ungespeichert else FARBE_GESPEICHERT

        for col in range(self.tabelle.columnCount()):
            widget = self.tabelle.cellWidget(row, col)
            if widget is not None:
                # Gilt sowohl für die Punkte-QLineEdit-Felder als auch für den Container
                # der Disqualifiziert-/Abbruch-Checkbox (siehe _zentrierte_zelle) -
                # QSS-Hintergrundfarbe funktioniert für beide Widget-Arten gleich.
                widget.setStyleSheet(
                    f"background-color: {farbe.name()};" if ungespeichert else ""
                )
            else:
                item = self.tabelle.item(row, col)
                if item is not None:
                    item.setBackground(farbe)

        status_item = self.tabelle.item(row, _STATUS_SPALTE)
        if status_item is not None:
            if ungespeichert:
                status_item.setText("● nicht gespeichert")
                status_item.setForeground(QColor("#b56a00"))
            else:
                status_item.setText("✓ gespeichert")
                status_item.setForeground(QColor("#1f8a3d"))

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

                    if suche_wert is None or anzeige_wert is None:
                        fehler.append(f"{name} – {disziplin}: bitte sowohl Suche als auch Anzeige eintragen")
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


class AuswertungTab(QWidget):
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._fertig: list = []
        self._ausstehend: list[dict] = []
        self._startnummer_je_id: dict[str, int | None] = {}

        self.tabelle = QTableWidget(0, 6)
        self.tabelle.setHorizontalHeaderLabels(
            ["Start-Nr.", "Leistungsklasse", "Name", "Gesamtpunkte", "Wertnote", "Platzierung"]
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

        aktualisieren_btn = QPushButton("Auswertung neu berechnen")
        aktualisieren_btn.clicked.connect(self.aktualisieren)

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
        layout.addWidget(aktualisieren_btn)

        self.aktualisieren()

    def aktualisieren(self) -> None:
        """Berechnet die Auswertung aus der Datenbank neu und aktualisiert den Filter."""
        self._fertig, self._ausstehend = berechne_auswertung(self.conn)
        # Teilnehmerergebnis (shs_core) kennt keine Startnummer - für die Anzeige/den
        # Filter hier separat aus den Stammdaten nachschlagen.
        self._startnummer_je_id = {str(t["id"]): t["startnummer"] for t in list_teilnehmer(self.conn)}

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

            if t.platzierung is None:
                platz_text = f"{status_text} (von {t.von_startern} Startern)"
            else:
                platz_text = f"{t.platzierung}. von {t.von_startern}"
            werte = [
                str(self._startnummer_je_id.get(t.id) or ""),
                t.leistungsklasse,
                t.name,
                punkte_text,
                wertnote_text,
                platz_text,
            ]
            for col, wert in enumerate(werte):
                item = QTableWidgetItem(wert)
                if not t.bestanden:
                    item.setForeground(QColor("red"))
                self.tabelle.setItem(row, col, item)
        self.tabelle.resizeColumnsToContents()

        if ausstehend_gefiltert:
            namen = ", ".join(f"{t['nachname']}, {t['vorname']}" for t in ausstehend_gefiltert)
            self.ausstehend_label.setText(f"Noch ohne vollständiges Ergebnis ({len(ausstehend_gefiltert)}): {namen}")
        else:
            self.ausstehend_label.setText("Alle Teilnehmer (in diesem Filter) sind vollständig ausgewertet.")


class TeilnehmerUebersichtTab(QWidget):
    """Zeigt Teilnehmerzahlen je Art/Leistungsklasse inkl. der ED-Disziplin-Aufschlüsselung
    sowie die daraus abgeleitete Anzahl benötigter Richter - entspricht der Sicht
    "Übersicht Teilnehmer" aus der ursprünglichen Excel-Vorlage (siehe Grobkonzept.md), hier
    mit "SH-R" durch den in diesem Programm sonst verwendeten Begriff "Richter"
    ersetzt. Datenquelle ist db.berechne_teilnehmer_lk_uebersicht() - wie bei AuswertungTab
    kein Zwischenspeicher, baut sich bei jedem Tabwechsel neu aus der DB auf."""

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

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Übersicht Teilnehmer und LK"))
        layout.addWidget(self.tabelle)
        layout.addWidget(self.teilnehmer_label)
        layout.addWidget(self.abteilungen_label)
        layout.addWidget(self.richter_label)

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


class PruefungsblockDialog(ResponsiveSchriftMixin, QDialog):
    """Formular zum Hinzufügen eines Prüfungsblocks in einer Richter-Spur des
    Zeitplans. Anders als bei der Teilnehmererfassung ist die Disziplin hier auch bei DK
    Pflicht: ein Dreikampf-Teilnehmer durchläuft die drei Disziplinen nacheinander, im
    Zeitplan also als drei getrennte Blöcke (ggf. auf unterschiedliche Richter/Zeiten
    verteilt) - die Disziplin am Block sagt, welche der drei das jeweils ist."""

    def __init__(self, parent=None, standard_dauer_minuten: int = 10):
        super().__init__(parent)
        self.setWindowTitle("Prüfungsblock hinzufügen")

        self.art = QComboBox()
        self.art.addItems(["ED", "DK"])

        self.stufe = QComboBox()
        self.stufe.addItems(["1", "2", "3"])

        self.disziplin = QComboBox()
        self.disziplin.addItems(ALLE_DISZIPLINEN)

        self.dauer_minuten = QSpinBox()
        self.dauer_minuten.setRange(1, 240)
        self.dauer_minuten.setValue(standard_dauer_minuten)
        self.dauer_minuten.setSuffix(" Min.")

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.addRow("Art*", self.art)
        form.addRow("Leistungsklasse*", self.stufe)
        form.addRow("Disziplin*", self.disziplin)
        form.addRow("Dauer je Teilnehmer*", self.dauer_minuten)

        hinweis = QLabel(
            "Der Block deckt automatisch ALLE aktuell erfassten Teilnehmer der gewählten "
            "Art/Leistungsklasse/Disziplin ab (bei DK: alle Teilnehmer dieser "
            "Leistungsklasse, unabhängig von der hier gewählten Disziplin) - die Dauer "
            "gilt je Teilnehmer, die Gesamtdauer des Blocks ergibt sich daraus automatisch."
        )
        hinweis.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hinweis)
        layout.addWidget(buttons)
        self._schriftgroesse_anwenden()

    def werte(self) -> dict:
        return {
            "art": self.art.currentText(),
            "stufe": int(self.stufe.currentText()),
            "disziplin": self.disziplin.currentText(),
            "dauer_minuten": self.dauer_minuten.value(),
        }


class PauseDialog(ResponsiveSchriftMixin, QDialog):
    """Formular zum Hinzufügen/Bearbeiten einer Pause in einer Richter-Spur."""

    def __init__(self, parent=None, dauer_minuten: int = 15, bezeichnung: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Pause")

        self.dauer_minuten = QSpinBox()
        self.dauer_minuten.setRange(1, 480)
        self.dauer_minuten.setValue(dauer_minuten)
        self.dauer_minuten.setSuffix(" Min.")

        self.bezeichnung = QLineEdit(bezeichnung)
        self.bezeichnung.setPlaceholderText("z.B. Mittagspause (optional, Standard: „Pause“)")

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.addRow("Dauer*", self.dauer_minuten)
        form.addRow("Bezeichnung", self.bezeichnung)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self._schriftgroesse_anwenden()

    def werte(self) -> dict:
        return {
            "dauer_minuten": self.dauer_minuten.value(),
            "bezeichnung": self.bezeichnung.text().strip() or None,
        }


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

        richter_hinzufuegen_btn = QPushButton("Richter hinzufügen")
        richter_hinzufuegen_btn.clicked.connect(self._richter_hinzufuegen)

        verteilen_btn = QPushButton("Automatisch verteilen…")
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
        self.status_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Zeitplan"))
        layout.addLayout(kopf_zeile)
        layout.addWidget(hinweis)
        layout.addLayout(inhalt_zeile, stretch=1)
        layout.addWidget(self.status_label)

        self.aktualisieren()

    # --- Aufbau --------------------------------------------------------------

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
        self._offene_starts_aktualisieren()

    def _offene_starts_aktualisieren(self) -> None:
        """Baut den Text der Seitenleiste "Offene Starts" aus zeitplan_gruppen_status()
        neu auf: eine Zeile je Art/Leistungsklasse/Disziplin mit mindestens einem
        Teilnehmer, grün mit Haken wenn bereits ein Prüfungsblock dafür angelegt wurde,
        sonst rot/fett hervorgehoben mit "noch offen"."""
        status_liste = zeitplan_gruppen_status(self.conn)
        if not status_liste:
            self._offene_starts_label.setText("Noch keine Teilnehmer erfasst.")
            return
        zeilen = []
        for eintrag in status_liste:
            bezeichnung = f"{eintrag['art']} LK {eintrag['stufe']} – {eintrag['disziplin']}"
            if eintrag["eingeplant"]:
                zeilen.append(
                    f'<span style="color:#2e7d32;">✓ {bezeichnung} ({eintrag["anzahl"]} TN)</span>'
                )
            else:
                zeilen.append(
                    '<span style="color:#c62828; font-weight:bold;">'
                    f'✗ {bezeichnung} ({eintrag["anzahl"]} TN) – noch offen</span>'
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
        for zeile in zeilen:
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

        eintrag_buttons_1 = QHBoxLayout()
        eintrag_buttons_1.addWidget(hoch_btn)
        eintrag_buttons_1.addWidget(runter_btn)
        eintrag_buttons_2 = QHBoxLayout()
        eintrag_buttons_2.addWidget(bearbeiten_btn)
        eintrag_buttons_2.addWidget(entfernen_btn)

        block_btn = QPushButton("Prüfungsblock hinzufügen…")
        block_btn.clicked.connect(lambda: self._pruefungsblock_hinzufuegen(richter_id))
        pause_btn = QPushButton("Pause hinzufügen…")
        pause_btn.clicked.connect(lambda: self._pause_hinzufuegen(richter_id))
        loeschen_btn = QPushButton("Richter löschen")
        loeschen_btn.clicked.connect(lambda: self._richter_loeschen(richter_id, richter["name"]))

        layout = QVBoxLayout(box)
        layout.addLayout(kopf_zeile)
        layout.addWidget(liste, stretch=1)
        layout.addLayout(eintrag_buttons_1)
        layout.addLayout(eintrag_buttons_2)
        layout.addWidget(block_btn)
        layout.addWidget(pause_btn)
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
        elif zeile["teilnehmer"] is None:
            text = f"{zeit}  {zeile['art']} LK {zeile['stufe']} – {zeile['disziplin']}  (noch keine Teilnehmer gemeldet)"
        else:
            t = zeile["teilnehmer"]
            startnr = t["startnummer"] if t["startnummer"] is not None else "–"
            text = (
                f"{zeit}  {zeile['art']} LK {zeile['stufe']} – {zeile['disziplin']}  "
                f"Nr. {startnr}  {t['nachname']}, {t['vorname']} ({t['rufname_hund']})"
            )
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, zeile["eintrag_id"])
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

    def _pause_hinzufuegen(self, richter_id: int) -> None:
        dialog = PauseDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            add_zeitplan_pause(self.conn, richter_id, **dialog.werte())
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


class BewertungsbogenAuswahlDialog(QDialog):
    """Auswahl, welche Art/Leistungsklasse(n)/Disziplin(en) in die Sammel-PDF "alle
    Bewertungsbögen" aufgenommen werden (Nutzerwunsch 21.09., Marcos eigener Lösungs-
    vorschlag: "ggf. auch nur Auswählbar, welche LK/Disziplin ich gedruckt haben will?" -
    Hintergrund: bei doppelseitigem Druck der kompletten Sammel-PDF landet sonst auf der
    Rückseite eines Blatts ggf. ein anderes ED-Team). Standard = alle Einträge angehakt
    (heutiges Verhalten bleibt Default) - an dasselbe Checkbox-Listen-Muster wie
    TerminImportDialog oben angelehnt."""

    def __init__(self, parent, labels: list[str]):
        super().__init__(parent)
        self.setWindowTitle("Bewertungsbögen – Auswahl LK/Disziplin")
        self.resize(420, 420)

        self.liste = QListWidget()
        for label in labels:
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.liste.addItem(item)

        alle_btn = QPushButton("Alle auswählen")
        alle_btn.clicked.connect(lambda: self._alle_umschalten(Qt.Checked))
        keine_btn = QPushButton("Keine auswählen")
        keine_btn.clicked.connect(lambda: self._alle_umschalten(Qt.Unchecked))
        auswahl_zeile = QHBoxLayout()
        auswahl_zeile.addWidget(alle_btn)
        auswahl_zeile.addWidget(keine_btn)
        auswahl_zeile.addStretch()

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        if not labels:
            self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Welche Art/Leistungsklasse(n) sollen in die Sammel-PDF aufgenommen werden? "
            "Standardmäßig sind alle angehakt (bisheriges Verhalten)."
            if labels else "Keine Teilnehmer erfasst."
        ))
        layout.addLayout(auswahl_zeile)
        layout.addWidget(self.liste)
        layout.addWidget(self.buttons)

    def _alle_umschalten(self, zustand) -> None:
        for row in range(self.liste.count()):
            self.liste.item(row).setCheckState(zustand)

    def ausgewaehlte_labels(self) -> set[str]:
        return {
            self.liste.item(row).text()
            for row in range(self.liste.count())
            if self.liste.item(row).checkState() == Qt.Checked
        }


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

        ergebnisliste_btn = QPushButton("Ergebnisliste (PDF)…")
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
        self.status_label.setWordWrap(True)

        button_zeile = QHBoxLayout()
        button_zeile.addWidget(ablageort_btn)
        button_zeile.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("PDF-Ausgabe"))
        layout.addWidget(ergebnisliste_btn)
        layout.addWidget(leere_ergebnisliste_btn)
        layout.addWidget(etiketten_btn)
        layout.addWidget(statistik_btn)
        layout.addWidget(pruefungsleitung_btn)
        layout.addWidget(chipliste_btn)
        layout.addWidget(leistungsrichter_btn)
        layout.addWidget(zeitplan_btn)
        layout.addWidget(boegen_btn)
        layout.addLayout(button_zeile)
        layout.addWidget(hinweis)
        layout.addStretch()
        layout.addWidget(self.status_label)

    def aktualisieren(self) -> None:
        pass  # kein Zwischenspeicher - wird bei jedem Export frisch aus der DB gelesen

    def _export_dateiname(self, praefix: str) -> str:
        return _export_dateiname(self.conn, praefix)

    def _speicherort_waehlen(self, titel: str, vorschlag: str) -> str | None:
        return _pdf_speicherort_waehlen(self, self._ablageort, titel, vorschlag)

    def _ablageort_oeffnen(self) -> None:
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
        self.status_label.setText(f"{text}: {pfad}")

    def _ergebnisliste_exportieren(self) -> None:
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
            "\"Export\") und stehen oft erst kurz vor dem Prüfungstag fest."
        )
        hinweis.setWordWrap(True)

        self.status_label = QLabel("")
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
        _aktualisiere_veranstaltung_feld(
            self.conn,
            verein=dialog.verein.text().strip(),
            datum=dialog.datum.text().strip(),
            ort=dialog.ort.text().strip() or None,
            vereins_nr=dialog.vereins_nr.text().strip() or None,
            pruefungsnummer=dialog.pruefungsnummer.text().strip() or None,
            wertungsrichter_1=dialog.wertungsrichter_1.text().strip() or None,
            wertungsrichter_2=dialog.wertungsrichter_2.text().strip() or None,
            wertungsrichter_3=dialog.wertungsrichter_3.text().strip() or None,
            wertungsrichter_4=dialog.wertungsrichter_4.text().strip() or None,
            wertungsrichter_5=dialog.wertungsrichter_5.text().strip() or None,
            pruefungsleiter=dialog.pruefungsleiter.text().strip() or None,
            pruefungsgebuehr_ed=dialog.pruefungsgebuehr_ed.text().strip() or None,
            pruefungsgebuehr_dk=dialog.pruefungsgebuehr_dk.text().strip() or None,
        )
        self.status_label.setText("Veranstaltungsdaten gespeichert.")


class SicherungErstellenDialog(QDialog):
    """Fragt vor dem Erstellen einer Sicherung ab, ob das ZIP mit einem Passwort
    geschützt werden soll (Checkbox, Passwortfeld standardmäßig deaktiviert) - siehe
    DatensicherungTab._sicherung_erstellen. Ohne Häkchen entsteht ein normales,
    unverschlüsseltes ZIP."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sicherung erstellen")

        self.passwort_checkbox = QCheckBox("Mit Passwort schützen")

        self.passwort_feld = QLineEdit()
        self.passwort_feld.setEchoMode(QLineEdit.Password)
        self.passwort_feld.setEnabled(False)

        self.passwort_wiederholen_feld = QLineEdit()
        self.passwort_wiederholen_feld.setEchoMode(QLineEdit.Password)
        self.passwort_wiederholen_feld.setEnabled(False)

        self.passwort_checkbox.toggled.connect(self.passwort_feld.setEnabled)
        self.passwort_checkbox.toggled.connect(self.passwort_wiederholen_feld.setEnabled)

        formular = QFormLayout()
        formular.addRow("Passwort:", self.passwort_feld)
        formular.addRow("Passwort wiederholen:", self.passwort_wiederholen_feld)

        hinweis = QLabel(
            "Sichert ALLE Termine aus dem gemeinsamen Termine-Ordner in eine einzige "
            "ZIP-Datei (nicht nur den aktuell geöffneten Termin). Mit Passwort entsteht "
            "eine AES-256-verschlüsselte ZIP-Datei - das Passwort wird nicht gespeichert "
            "und lässt sich nachträglich nicht wiederherstellen, also gut aufbewahren."
        )
        hinweis.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._pruefen_und_akzeptieren)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(hinweis)
        layout.addWidget(self.passwort_checkbox)
        layout.addLayout(formular)
        layout.addWidget(buttons)

    def _pruefen_und_akzeptieren(self) -> None:
        if self.passwort_checkbox.isChecked():
            if not self.passwort_feld.text():
                QMessageBox.warning(self, "Passwort fehlt", "Bitte ein Passwort eingeben oder das Häkchen entfernen.")
                return
            if self.passwort_feld.text() != self.passwort_wiederholen_feld.text():
                QMessageBox.warning(self, "Passwörter unterschiedlich", "Die beiden Passwort-Eingaben stimmen nicht überein.")
                return
        self.accept()

    def passwort(self) -> str | None:
        """Gibt das eingegebene Passwort zurück, oder None, wenn kein Passwortschutz
        gewünscht wurde."""
        if self.passwort_checkbox.isChecked():
            return self.passwort_feld.text()
        return None


class DatensicherungTab(QWidget):
    """Export/Import ALLER Termine als ZIP-Datei (optional passwortgeschützt), unabhängig
    vom gerade im Hauptfenster geöffneten Termin - Datengrundlage ist immer der komplette
    Termine-Ordner (termine_ordner()), nicht die aktuelle Datenbankverbindung self.conn
    der übrigen Tabs. Deckt den bisher fehlenden Datensicherungsweg ab: bislang ließ sich
    der Termine-Ordner nur manuell (Datei-Explorer) sichern."""

    def __init__(self, parent=None, aktueller_pfad: str | None = None):
        super().__init__(parent)
        # Nur zur Erkennung eines Namenskonflikts mit dem GERADE GEÖFFNETEN Termin beim
        # Wiederherstellen (siehe _sicherung_wiederherstellen/_konflikt_abfragen) - ein
        # Überschreiben dieser Datei würde mit der noch offenen sqlite3.Connection des
        # Hauptfensters kollidieren.
        self._aktueller_pfad = aktueller_pfad

        hinweis = QLabel(
            "Sichert bzw. liest ALLE Termine aus dem gemeinsamen Termine-Ordner "
            f"(„{termine_ordner()}“) als eine einzige ZIP-Datei - nicht nur den gerade "
            "geöffneten Termin. Für eine Sicherung mit Passwort empfiehlt es sich, das "
            "Passwort getrennt von der ZIP-Datei selbst aufzubewahren (z.B. nicht im "
            "selben Ordner)."
        )
        hinweis.setWordWrap(True)

        erstellen_btn = QPushButton("Sicherung erstellen (ZIP)…")
        erstellen_btn.clicked.connect(self._sicherung_erstellen)

        wiederherstellen_btn = QPushButton("Sicherung wiederherstellen (ZIP)…")
        wiederherstellen_btn.clicked.connect(self._sicherung_wiederherstellen)

        self.status_label = QLabel("")
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

    def _sicherung_erstellen(self) -> None:
        dialog = SicherungErstellenDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        passwort = dialog.passwort()

        heute = datetime.date.today().isoformat()
        vorschlag = os.path.join(os.path.expanduser("~"), f"SHS-Sicherung_{heute}.zip")
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
        self.status_label.setText(f"Sicherung erstellt: {pfad} ({anzahl} Termin(e){zusatz}).")

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

        entscheidungen: dict[str, str] = {}
        uebersprungen = 0
        for name in namen:
            if name not in vorhandene:
                entscheidungen[name] = name
                continue
            aktion = self._konflikt_abfragen(name, ist_offener_termin=(name == offener_name))
            if aktion == "ueberschreiben":
                entscheidungen[name] = name
            elif aktion == "kopie":
                entscheidungen[name] = eindeutigen_dateinamen_finden(ordner, name)
            else:  # "ueberspringen"
                uebersprungen += 1

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


# Allgemeine Bedienungshilfe (ein Abschnitt je Reiter) - Inhalt mit dem Nutzer vorab
# abgestimmt, bevor er hier fest eingebaut wurde. Als einfaches HTML statt reinem Text,
# damit sich die Abschnittsüberschriften im Hilfe-Fenster (siehe HilfeDialog) klar vom
# Fließtext abheben.
_HILFE_HTML = """
<h2>Hilfe – SHS Prüfungsprogramm</h2>

<h3>Erste Schritte</h3>
<p>Beim Programmstart zeigt die Terminübersicht alle vorhandenen Termine mit Datum, Verein,
Ort und Teilnehmerzahl. Über "Neuen Termin anlegen…" legst du Verein/Ort/Datum (und optional
weitere Angaben) fest – der Dateiname wird automatisch vorgeschlagen. Einen vorhandenen
Termin öffnest du per Doppelklick oder "Öffnen"; "Löschen…" entfernt eine Termin-Datei
unwiderruflich (mit Rückfrage). Im Hauptfenster kannst du über "Anderen Termin öffnen…"
jederzeit wechseln.</p>

<h3>Reiter "Teilnehmer"</h3>
<p>Liste aller gemeldeten Teilnehmer. "Teilnehmer hinzufügen…" öffnet die Erfassungsmaske:
Stammdaten, Verband/Mitgliedsnummer, Anschrift (Straße/Hausnummer/PLZ/Ort) und Kontaktdaten
(E-Mail/Telefon) sowie Wurftag des Hundes - alles optional, außer den mit * markierten
Pflichtfeldern. Dazu Art (ED/DK), Leistungsklasse, bei ED die Disziplin, bis zu drei
Suchgegenstände.
Hinter jedem Gegenstand legst du per Auswahlfeld fest, für welche Disziplin er gilt ("frei",
wenn keine Zuordnung nötig ist) – das steuert, wo er später auf dem Bewertungsbogen
erscheint. Die Startnummer wird automatisch vorgeschlagen. "Bezahlt umschalten" setzt den
Zahlungsstatus des markierten Teilnehmers, ohne den ganzen Dialog zu öffnen. Der Filter
Art/LK bzw. Start-Nr. (wie in der Ergebniserfassung) blendet Zeilen nur aus.</p>

<h3>Reiter "Zeitplan"</h3>
<p>Plant den Tagesablauf je Richter. Startzeit oben festlegen, dann je Richter eine
Spalte mit "Prüfungsblock hinzufügen…" oder "Pause hinzufügen…". Reihenfolge mit
"Hoch"/"Runter" anpassen. "Automatisch verteilen…" erstellt einen ausbalancierten Vorschlag
(ersetzt den bisherigen Plan der gewählten Richter, mit Rückfrage) – danach frei von Hand
änderbar. Start-/Endzeiten berechnen sich automatisch. Die Seitenleiste "Offene Starts"
zeigt je Art/Leistungsklasse/Disziplin, ob dafür schon ein Prüfungsblock angelegt wurde
(grün) oder noch fehlt (rot, "noch offen") – bleibt auch beim seitlichen Scrollen durch
viele Richter-Spalten sichtbar. "Zeitplan (PDF)…" exportiert eine Seite je Richter.</p>
<p><b>Wichtig zu "Entfernen":</b> Ein Prüfungsblock speichert nur Art/Leistungsklasse/
Disziplin und die Dauer je Teilnehmer – WER genau darin geprüft wird, wird bei jeder
Anzeige automatisch aus den aktuellen Teilnehmerdaten ermittelt, nicht einzeln gespeichert.
"Entfernen" löscht deshalb immer den GANZEN Block (alle darin zusammengefassten
Teilnehmer), nicht nur einen einzelnen Teilnehmer. Fällt z. B. ein Teilnehmer kurzfristig
aus (Krankmeldung), muss im Zeitplan nichts angefasst werden: einfach im Reiter
"Teilnehmer" austragen – der Block bleibt bestehen und zeigt beim nächsten Öffnen des
Zeitplans automatisch einen Teilnehmer (und entsprechend weniger Zeit) weniger.</p>

<h3>Reiter "Ergebniserfassung"</h3>
<p>Eine Zeile je Teilnehmer, bei DK alle drei Disziplinen nebeneinander. Suchleistung (0–60)
und Anzeigeleistung (0–40) eintragen. Noch nicht gespeicherte Zeilen werden gelb markiert.
"Alle Ergebnisse speichern" sichert alle Änderungen auf einmal. Der Filter blendet nur aus,
ungespeicherte Eingaben gehen dabei nicht verloren. Um ein bereits gespeichertes Ergebnis
wieder zu entfernen, beide Felder (Suche und Anzeige) leeren und anschließend speichern –
ist nur eines der beiden Felder leer, gilt das als unvollständig und wird beim Speichern
zurückgewiesen.</p>

<h3>Reiter "Auswertung"</h3>
<p>Zeigt die berechnete Rangliste je Leistungsklasse mit Wertnote. Filter nach
Art/Leistungsklasse und Startnummer. "Nicht bestanden" wird rot markiert und erhält keine
Platzzahl, zählt aber bei den Startern mit. "Auswertung neu berechnen" aktualisiert die
Anzeige.</p>

<h3>Reiter "Verwaltung"</h3>
<p>"Veranstaltungsdaten bearbeiten…" ändert Verein/Ort/Datum sowie Vereins-Nr.,
Prüfungsnummer, Richter 1-5, Prüfungsleiter und Prüfungsgebühr ED/DK nachträglich –
diese Angaben stehen oft erst kurz vor dem Prüfungstag fest und erscheinen im Kopf der
Statistik-PDF bzw. in der Übersicht für Prüfungsleitung (siehe Reiter "Export").</p>

<h3>Reiter "Export"</h3>
<p>Alle PDF-Ausgaben an einer Stelle: Ergebnisliste, leere Ergebnisliste zum Ausfüllen,
Etiketten, Statistik, Übersicht für Prüfungsleitung, Richter-Bedarf, Zeitplan sowie
alle Bewertungsbögen gesammelt. "Ablageort öffnen" zeigt den Ordner der zuletzt gespeicherten
PDFs im Explorer – alle Exporte (auch im Zeitplan-Tab) teilen sich denselben Speicherort.</p>

<h3>Reiter "Datensicherung"</h3>
<p>Sichert bzw. liest ALLE Termine aus dem gemeinsamen Termine-Ordner als eine ZIP-Datei
– nicht nur den gerade geöffneten Termin. "Sicherung erstellen (ZIP)…" fragt zunächst,
ob die Datei mit einem Passwort geschützt werden soll (dann AES-256-verschlüsselt),
danach den Speicherort. "Sicherung wiederherstellen (ZIP)…" fragt bei Bedarf nach dem
Passwort und bei jedem bereits vorhandenen Termin, ob überschrieben, als Kopie
importiert oder übersprungen werden soll. Ein vergessenes Passwort lässt sich nicht
wiederherstellen – gut aufbewahren.</p>

<h3>Versionsanzeige</h3>
<p>Der Button "Version" neben "Hilfe" zeigt die aktuell installierte Version. "Nach
Updates suchen" prüft dort per Klick automatisch (über GitHub), ob eine neuere Version
veröffentlicht wurde, und zeigt bei Bedarf einen Download-Button an – dafür wird kurz
eine Internetverbindung gebraucht, ohne Internet erscheint stattdessen ein entsprechender
Hinweis. Eine automatische Prüfung im Hintergrund beim Programmstart ist bewusst nicht
eingebaut.</p>
"""


class HilfeDialog(QDialog):
    """Allgemeine Bedienungshilfe in einem eigenen, scrollbaren Fenster - ein Abschnitt je
    Reiter (siehe _HILFE_HTML oben). Wird über den Hilfe-Button im Hauptfenster geöffnet
    (siehe HauptFenster._hilfe_anzeigen)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hilfe")
        self.resize(560, 520)

        anzeige = QTextBrowser()
        anzeige.setHtml(_HILFE_HTML)
        anzeige.setOpenExternalLinks(False)

        schliessen_btn = QPushButton("Schließen")
        schliessen_btn.clicked.connect(self.accept)
        schliessen_zeile = QHBoxLayout()
        schliessen_zeile.addStretch()
        schliessen_zeile.addWidget(schliessen_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(anzeige)
        layout.addLayout(schliessen_zeile)


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


class HauptFenster(ResponsiveSchriftMixin, QMainWindow):
    def __init__(self, conn, pfad: str):
        super().__init__()
        self.resize(900, 600)
        self._theme_menue_aufbauen()

        # Hilfe-Button oben rechts im Fenster, direkt neben "Anderen Termin öffnen…" -
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

        wechseln_btn = QPushButton("Anderen Termin öffnen…")
        wechseln_btn.clicked.connect(self._termin_wechseln)
        kopf_zeile = QHBoxLayout()
        kopf_zeile.addStretch()
        kopf_zeile.addWidget(wechseln_btn)
        kopf_zeile.addWidget(version_btn)
        kopf_zeile.addWidget(hilfe_btn)

        zentral = QWidget()
        zentral_layout = QVBoxLayout(zentral)
        zentral_layout.addLayout(kopf_zeile)
        zentral_layout.addWidget(self._tabs)
        self.setCentralWidget(zentral)

        self._termin_setzen(conn, pfad)
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
        ansicht_menue = self.menuBar().addMenu("&Ansicht")
        theme_menue = ansicht_menue.addMenu("Theme")

        self._theme_actions: dict[str, QAction] = {}
        gruppe = QActionGroup(self)
        gruppe.setExclusive(True)
        gruppe.triggered.connect(self._theme_aktion_ausgeloest)

        aktives_theme = _gespeichertes_theme_lesen()
        for schluessel, daten in _THEMES.items():
            action = QAction(daten["anzeigename"], self)
            action.setCheckable(True)
            action.setChecked(schluessel == aktives_theme)
            action.setData(schluessel)
            theme_menue.addAction(action)
            gruppe.addAction(action)
            self._theme_actions[schluessel] = action

    def _theme_aktion_ausgeloest(self, action: QAction) -> None:
        self._theme_wechseln(action.data())

    def _theme_wechseln(self, theme_name: str) -> None:
        QApplication.instance().setStyleSheet(_erzeuge_qss(theme_name))
        _theme_speichern(theme_name)

    def _hilfe_anzeigen(self) -> None:
        HilfeDialog(self).exec()

    def _version_anzeigen(self) -> None:
        VersionDialog(self).exec()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Speichert automatisch noch nicht gespeicherte Ergebnisse, bevor das Programm
        beendet wird - auf Wunsch des Nutzers, damit beim Schließen (z.B. über das
        Fenster-X) nichts verloren geht, ohne dass dafür extra nachgefragt werden muss
        (anders als beim Tabwechsel/Terminwechsel, wo weiterhin gefragt wird, siehe
        _tab_gewechselt/_termin_wechseln oben).

        QS-Fund (19./20.09.): alle_speichern() kann NICHT jede Zeile speichern - z.B.
        wenn nur eines von zwei zusammengehörigen Feldern ausgefüllt ist, zeigt es zwar
        eine Warnung, lässt die betroffene Zeile aber ungespeichert. Vorher schloss sich
        das Fenster direkt danach TROTZDEM (event.accept() ohne erneute Prüfung) - die
        Warnung verschwand zusammen mit dem Fenster, ohne dass die Änderung je gespeichert
        wurde und ohne dass der Nutzer noch die Möglichkeit gehabt hätte, sie zu
        korrigieren. Nach dem Speicherversuch wird deshalb erneut geprüft: bleiben
        Änderungen ungespeichert übrig, wird - genau wie bei _tab_gewechselt/
        _termin_wechseln - nachgefragt, ob trotzdem beendet (und diese Änderungen
        verworfen) oder das Schließen abgebrochen werden soll, damit die fehlerhafte
        Zeile noch korrigiert werden kann. Vorbelegter Standard ist "Nein" (nicht
        schließen) - anders als bei den übrigen Ja/Nein-Rückfragen in diesem Fenster, wo
        der übliche Fall (Speichern) vorbelegt ist, ist hier der sicherere Standard das
        NICHT versehentliche Verwerfen von Daten."""
        if self.ergebnis_tab.hat_ungespeicherte_aenderungen():
            self.ergebnis_tab.alle_speichern()
            if self.ergebnis_tab.hat_ungespeicherte_aenderungen():
                antwort = QMessageBox.question(
                    self,
                    "Nicht alle Ergebnisse gespeichert",
                    "Einige Ergebnisse konnten nicht automatisch gespeichert werden (siehe "
                    "vorherige Meldung).\n\nProgramm trotzdem beenden und diese ungespeicherten "
                    "Änderungen verwerfen?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if antwort != QMessageBox.Yes:
                    event.ignore()
                    return
        event.accept()

    def _termin_setzen(self, conn, pfad: str) -> None:
        """Verbindet das Fenster mit einem (neuen oder anfänglichen) Termin: setzt Titel
        und baut alle Tabs für diesen Termin neu auf."""
        self.conn = conn
        self.pfad = pfad
        self.setWindowTitle(f"SHS Prüfungsprogramm – {pfad}")

        veranstaltung = get_veranstaltung(conn)
        if veranstaltung:
            self.setWindowTitle(
                f"SHS Prüfungsprogramm – {veranstaltung['verein']} ({veranstaltung['datum']})"
            )

        self._tabs.blockSignals(True)
        while self._tabs.count():
            self._tabs.removeTab(0)

        # Ein gemeinsames _Ablageort-Objekt für die Tabs "Zeitplan" und "Export", damit ein
        # in einem der beiden Tabs bewusst gewählter Speicherort auch im jeweils anderen
        # als neuer Standard gilt (siehe _Ablageort oben).
        ablageort = _Ablageort(os.path.dirname(pfad) if pfad else str(termine_ordner()))

        self.teilnehmer_tab = TeilnehmerTab(conn, pfad=pfad, ablageort=ablageort)
        self.formular_import_tab = FormularImportTab(conn)
        self.zeitplan_tab = ZeitplanTab(conn, ablageort)
        self.ergebnis_tab = ErgebnisTab(conn)
        self.auswertung_tab = AuswertungTab(conn)
        self.teilnehmer_uebersicht_tab = TeilnehmerUebersichtTab(conn)
        self.verwaltung_tab = VerwaltungTab(conn)
        self.export_tab = ExportTab(conn, pfad, ablageort)
        # Anders als die übrigen Tabs NICHT an conn/pfad gebunden - arbeitet immer auf dem
        # gesamten Termine-Ordner (siehe DatensicherungTab oben), wird aber trotzdem hier
        # neu aufgebaut, damit sie sich wie die anderen Tabs beim Terminwechsel verhält.
        # aktueller_pfad wird nur mitgegeben, damit ein Wiederherstellen den gerade
        # geöffneten Termin nicht versehentlich überschreibt (siehe DatensicherungTab).
        self.datensicherung_tab = DatensicherungTab(aktueller_pfad=pfad)

        self._tabs.addTab(self.teilnehmer_tab, "Teilnehmer")
        self._tabs.addTab(self.formular_import_tab, "Formular-Import")
        self._tabs.addTab(self.zeitplan_tab, "Zeitplan")
        self._tabs.addTab(self.ergebnis_tab, "Ergebniserfassung")
        self._tabs.addTab(self.auswertung_tab, "Auswertung")
        self._tabs.addTab(self.teilnehmer_uebersicht_tab, "Übersicht")
        self._tabs.addTab(self.verwaltung_tab, "Verwaltung")
        self._tabs.addTab(self.export_tab, "Export")
        self._tabs.addTab(self.datensicherung_tab, "Datensicherung")
        self._tabs.blockSignals(False)

        self._vorheriger_tab_index = 0

    def _termin_wechseln(self) -> None:
        """Öffnet den Startdialog erneut, damit ohne Neustart der Anwendung zu einem
        anderen Termin gewechselt werden kann."""
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

        dialog = StartDialog(self, aktueller_pfad=self.pfad)
        if dialog.exec() != QDialog.Accepted or not dialog.pfad:
            return

        neue_verbindung = init_db(dialog.pfad)
        alte_verbindung = self.conn
        self._termin_setzen(neue_verbindung, dialog.pfad)
        alte_verbindung.close()

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
            # Speichern wurde bewusst abgelehnt - keinen automatischen Reload auslösen,
            # der diese Eingaben sonst sofort wieder verwerfen würde.
            return
        if hasattr(widget, "aktualisieren"):
            widget.aktualisieren()


#: Vorschlag für die Prüfungsgebühr, solange noch keine eigene hinterlegt wurde (siehe
#: VeranstaltungsDialog unten) - frei änderbar je Termin, dient nur als Startwert.
_STANDARD_PRUEFUNGSGEBUEHR = "12,00"


class VeranstaltungsDialog(ResponsiveSchriftMixin, QDialog):
    """Abfrage der Veranstaltungs-Stammdaten - entweder beim Neuanlegen eines Termins
    (inklusive Speicherort, der aus Verein + Datum vorgeschlagen wird und sich anpasst,
    solange der Nutzer ihn nicht selbst geändert hat) oder zum nachträglichen Bearbeiten
    eines bereits geöffneten Termins (ohne Speicherort-Feld, mit den bisherigen Werten
    vorbelegt). Die Zusatzfelder (Vereins-Nr., Prüfungsnummer, Richter 1-5,
    Prüfungsleiter) sind rein optional und werden nur für die Statistik-PDF gebraucht
    (siehe pdf_export.erstelle_statistik_pdf) - sie stehen oft erst kurz vor oder am
    Prüfungstag fest, daher lassen sie sich jederzeit nachträglich ergänzen/ändern. Die
    Prüfungsgebühr ED/DK wird für die "Übersicht für Prüfungsleitung"-PDF gebraucht
    (siehe pdf_export.erstelle_pruefungsleitung_uebersicht_pdf) und ist mit einem
    Standardwert vorbelegt, der sich pro Termin überschreiben lässt."""

    def __init__(self, parent=None, vorbelegung: dict | None = None, bearbeiten: bool = False):
        super().__init__(parent)
        self._bearbeiten = bearbeiten
        self.setWindowTitle("Veranstaltungsdaten bearbeiten" if bearbeiten else "Neuen Termin anlegen")
        vorbelegung = vorbelegung or {}

        def feld(name: str) -> QLineEdit:
            return QLineEdit(vorbelegung.get(name) or "")

        def geld_feld(name: str) -> QLineEdit:
            return QLineEdit(vorbelegung.get(name) or _STANDARD_PRUEFUNGSGEBUEHR)

        self.verein = feld("verein")
        self.ort = feld("ort")
        self.datum = feld("datum")
        self.datum.setPlaceholderText("JJJJ-MM-TT")
        self.vereins_nr = feld("vereins_nr")
        self.pruefungsnummer = feld("pruefungsnummer")
        self.wertungsrichter_1 = feld("wertungsrichter_1")
        self.wertungsrichter_2 = feld("wertungsrichter_2")
        self.wertungsrichter_3 = feld("wertungsrichter_3")
        self.wertungsrichter_4 = feld("wertungsrichter_4")
        self.wertungsrichter_5 = feld("wertungsrichter_5")
        self.pruefungsleiter = feld("pruefungsleiter")
        self.pruefungsgebuehr_ed = geld_feld("pruefungsgebuehr_ed")
        self.pruefungsgebuehr_dk = geld_feld("pruefungsgebuehr_dk")

        form = QFormLayout()
        # Eingabefelder wachsen mit der Dialogbreite mit, statt bei einer
        # Fenstervergrößerung auf ihrer ursprünglichen Größe stehen zu bleiben.
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.addRow("Austragender Verein*", self.verein)
        form.addRow("Vereins-Nr.", self.vereins_nr)
        form.addRow("Ort", self.ort)
        form.addRow("Datum* (JJJJ-MM-TT)", self.datum)
        form.addRow("Prüfungsnummer", self.pruefungsnummer)
        form.addRow("Prüfungsleiter", self.pruefungsleiter)
        form.addRow("Richter 1", self.wertungsrichter_1)
        form.addRow("Richter 2", self.wertungsrichter_2)
        form.addRow("Richter 3", self.wertungsrichter_3)
        form.addRow("Richter 4", self.wertungsrichter_4)
        form.addRow("Richter 5", self.wertungsrichter_5)
        form.addRow("Prüfungsgebühr ED (€)", self.pruefungsgebuehr_ed)
        form.addRow("Prüfungsgebühr DK (€)", self.pruefungsgebuehr_dk)

        if not bearbeiten:
            self.pfad_feld = QLineEdit()
            self._pfad_manuell_geaendert = False
            self.pfad_feld.textEdited.connect(self._pfad_manuell_markieren)
            self.verein.textChanged.connect(self._pfad_vorschlagen)
            self.datum.textChanged.connect(self._pfad_vorschlagen)
            self._pfad_vorschlagen()

            durchsuchen_btn = QPushButton("Durchsuchen…")
            durchsuchen_btn.clicked.connect(self._durchsuchen)
            pfad_zeile = QHBoxLayout()
            pfad_zeile.addWidget(self.pfad_feld)
            pfad_zeile.addWidget(durchsuchen_btn)
            form.addRow("Speicherort*", pfad_zeile)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._pruefen_und_akzeptieren)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self._schriftgroesse_anwenden()

    def _pfad_manuell_markieren(self, _text: str) -> None:
        self._pfad_manuell_geaendert = True

    def _pfad_vorschlagen(self) -> None:
        if self._pfad_manuell_geaendert:
            return
        name = dateiname_vorschlagen(self.verein.text().strip(), self.datum.text().strip())
        self.pfad_feld.setText(str(termine_ordner() / name))

    def _durchsuchen(self) -> None:
        pfad, _ = QFileDialog.getSaveFileName(self, "Speicherort wählen", self.pfad_feld.text(), "SHS-Termin (*.sqlite)")
        if pfad:
            self.pfad_feld.setText(pfad)
            self._pfad_manuell_geaendert = True

    def _pruefen_und_akzeptieren(self) -> None:
        if not self.verein.text().strip() or not self.datum.text().strip():
            QMessageBox.warning(self, "Angaben unvollständig", "Bitte Verein und Datum angeben.")
            return
        if not self._bearbeiten and not self.pfad_feld.text().strip():
            QMessageBox.warning(self, "Angaben unvollständig", "Bitte einen Speicherort angeben.")
            return
        self.accept()


class StartDialog(ResponsiveSchriftMixin, QDialog):
    """Startdialog: Übersicht aller vorhandenen Termine aus dem Standard-Ordner (siehe
    db.termine_ordner) zum Öffnen/Löschen, sowie neuen Termin anlegen oder eine
    Termin-Datei an anderer Stelle öffnen (z. B. von einem USB-Stick)."""

    def __init__(self, parent=None, aktueller_pfad: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("SHS Prüfungsprogramm")
        self.resize(600, 380)
        self.pfad: str | None = None
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

        hinweis = QLabel(f"Neue Termine werden standardmäßig unter {termine_ordner()} gespeichert.")
        hinweis.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Willkommen im SHS Prüfungsprogramm – bitte einen Termin wählen oder neu anlegen:"))
        layout.addWidget(self.tabelle)
        layout.addLayout(button_zeile)
        layout.addWidget(hinweis)

        self._aktualisieren()
        self._schriftgroesse_anwenden()

    def _aktualisieren(self) -> None:
        self._termine = liste_termine()
        self.tabelle.setRowCount(len(self._termine))
        for row, t in enumerate(self._termine):
            werte = [
                t.datum or "?",
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
        set_veranstaltung(
            conn,
            verein=dialog.verein.text().strip(),
            datum=dialog.datum.text().strip(),
            ort=dialog.ort.text().strip() or None,
            vereins_nr=dialog.vereins_nr.text().strip() or None,
            pruefungsnummer=dialog.pruefungsnummer.text().strip() or None,
            wertungsrichter_1=dialog.wertungsrichter_1.text().strip() or None,
            wertungsrichter_2=dialog.wertungsrichter_2.text().strip() or None,
            wertungsrichter_3=dialog.wertungsrichter_3.text().strip() or None,
            wertungsrichter_4=dialog.wertungsrichter_4.text().strip() or None,
            wertungsrichter_5=dialog.wertungsrichter_5.text().strip() or None,
            pruefungsleiter=dialog.pruefungsleiter.text().strip() or None,
            pruefungsgebuehr_ed=dialog.pruefungsgebuehr_ed.text().strip() or None,
            pruefungsgebuehr_dk=dialog.pruefungsgebuehr_dk.text().strip() or None,
        )
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
            f"Termin „{termin.verein or termin.dateiname}“ ({termin.datum or '?'}) inklusive aller "
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

    def _andere_datei_oeffnen(self) -> None:
        pfad, _ = QFileDialog.getOpenFileName(self, "Termin öffnen", str(termine_ordner()), "SHS-Termin (*.sqlite)")
        if pfad:
            self.pfad = pfad
            self.accept()


_QSS_TEMPLATE = """
/* "Modern/Minimal"-Erscheinungsbild (siehe Design-Mockup-Vergleich): kühles Grau-Blau,
ein einzelner Akzentton (je gewähltem Theme, siehe _THEMES/_erzeuge_qss() unten -
@@AKZENT@@/@@AKZENT_HOVER@@/@@AKZENT_PRESSED@@/@@AKZENT_HELL@@ sind Platzhalter, die vor
dem Anwenden per str.replace() durch die Theme-Hexwerte ersetzt werden; str.format() geht
hier nicht, da das Stylesheet selbst voller literaler {}-Blockklammern ist), ruhige
Flächen statt vieler Rahmen/Schatten. Global über QApplication.setStyleSheet() gesetzt
(siehe main() unten) - HauptFenster & Dialoge setzen zusätzlich per ResponsiveSchriftMixin
eine eigene, nähere QHeaderView::section-/QLabel-Regel NUR für font-size bei
Größenänderung; das überschreibt hier absichtlich nichts anderes, da beide Regelsätze
unterschiedliche Eigenschaften des Selektors setzen. */

QMainWindow, QDialog {
    background: #FFFFFF;
}
QWidget {
    color: #1B2430;
}
QLabel {
    color: #1B2430;
}

/* Reiter (Teilnehmer/Zeitplan/.../Datensicherung sowie der Hilfe-Dialog) */
QTabWidget::pane {
    border: 1px solid #E4E8EE;
    background: #FFFFFF;
    top: -1px;
}
QTabBar::tab {
    background: #FFFFFF;
    color: #6B7686;
    padding: 8px 16px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-right: 2px;
}
QTabBar::tab:selected {
    color: #16233E;
    font-weight: 600;
    border-bottom: 2px solid @@AKZENT@@;
}
QTabBar::tab:hover:!selected {
    color: #16233E;
}

/* Schaltflächen: neutral/sekundär als Standard; die jeweilige Haupt-Aktion eines
Reiters/Dialogs trägt objectName "primaerButton" (siehe z.B. TeilnehmerTab) und wird
blau hervorgehoben - ebenso automatisch jeder Dialog-Default-Button (die "OK"-Schaltfläche
einer QDialogButtonBox, über die Qt-eigene :default-Pseudoklasse, ohne dass jeder
Dialog einzeln angepasst werden muss). */
QPushButton {
    background: #F1F4F8;
    color: #2A3342;
    border: 1px solid #E4E8EE;
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton:hover {
    background: #E7ECF3;
}
QPushButton:pressed {
    background: #DCE3EC;
}
QPushButton:disabled {
    color: #A7B0BD;
    background: #F6F8FA;
    border-color: #EDF0F4;
}
QPushButton#primaerButton, QPushButton:default:enabled {
    background: @@AKZENT@@;
    color: #FFFFFF;
    border: 1px solid @@AKZENT@@;
    font-weight: 600;
}
QPushButton#primaerButton:hover, QPushButton:default:enabled:hover {
    background: @@AKZENT_HOVER@@;
    border-color: @@AKZENT_HOVER@@;
}
QPushButton#primaerButton:pressed, QPushButton:default:enabled:pressed {
    background: @@AKZENT_PRESSED@@;
    border-color: @@AKZENT_PRESSED@@;
}

/* Eingabefelder */
QLineEdit, QComboBox, QSpinBox, QDateEdit {
    background: #F1F4F8;
    border: 1px solid #E4E8EE;
    border-radius: 6px;
    padding: 4px 8px;
    color: #1B2430;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {
    border: 1px solid @@AKZENT@@;
    background: #FFFFFF;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
    color: #A7B0BD;
    background: #F6F8FA;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QCheckBox {
    color: #1B2430;
    spacing: 6px;
}

/* Tabellen (Teilnehmer, Ergebniserfassung, Auswertung, Zeitplan, Terminübersicht) */
QTableWidget {
    background: #FFFFFF;
    alternate-background-color: #FBFCFD;
    gridline-color: #E4E8EE;
    border: 1px solid #E4E8EE;
    border-radius: 6px;
    selection-background-color: @@AKZENT_HELL@@;
    selection-color: #1B2430;
}
QTableWidget::item {
    padding: 4px 6px;
}
QTableWidget::item:selected {
    background: @@AKZENT_HELL@@;
    color: #1B2430;
}
QHeaderView::section {
    background: #FBFCFD;
    color: #8A94A6;
    padding: 6px;
    border: none;
    border-bottom: 1px solid #E4E8EE;
    font-weight: 600;
}
QTableCornerButton::section {
    background: #FBFCFD;
    border: none;
    border-bottom: 1px solid #E4E8EE;
}

QScrollBar:vertical, QScrollBar:horizontal {
    background: #FFFFFF;
    border: none;
}
QScrollBar::handle {
    background: #D8DEE7;
    border-radius: 5px;
}
QScrollBar::handle:hover {
    background: #C3CBD8;
}
"""

_THEME_DEFAULT = "blau"

# Drei Akzentfarb-Themes (keine Hell/Dunkel-Umschaltung, nur der Akzentton wechselt -
# alle übrigen Farben in _QSS_TEMPLATE bleiben je Theme identisch). "blau" entspricht
# bit-für-bit dem bisherigen, fest verdrahteten Erscheinungsbild (siehe test_theme.py).
_THEMES: dict[str, dict[str, str]] = {
    "blau": {
        "anzeigename": "Blau (Standard)",
        "akzent": "#2F6FED",
        "akzent_hover": "#2A63D6",
        "akzent_pressed": "#2558BF",
        "akzent_hell": "#EAF1FF",
    },
    "gruen": {
        "anzeigename": "Grün",
        "akzent": "#1E8E5A",
        "akzent_hover": "#1A7A4D",
        "akzent_pressed": "#166741",
        "akzent_hell": "#E7F3EC",
    },
    "violett": {
        "anzeigename": "Violett",
        "akzent": "#6B4FBB",
        "akzent_hover": "#5F45A8",
        "akzent_pressed": "#523B92",
        "akzent_hell": "#EEEAF8",
    },
}


def _erzeuge_qss(theme_name: str) -> str:
    """Setzt die Akzentfarb-Platzhalter in _QSS_TEMPLATE für das gewählte Theme ein."""
    theme = _THEMES.get(theme_name, _THEMES[_THEME_DEFAULT])
    text = _QSS_TEMPLATE
    text = text.replace("@@AKZENT_HOVER@@", theme["akzent_hover"])
    text = text.replace("@@AKZENT_PRESSED@@", theme["akzent_pressed"])
    text = text.replace("@@AKZENT_HELL@@", theme["akzent_hell"])
    text = text.replace("@@AKZENT@@", theme["akzent"])
    return text


_SETTINGS_ORG = "SHS-Pruefungsprogramm"
_SETTINGS_APP = "Desktop"
_SETTINGS_KEY_THEME = "darstellung/theme"


def _gespeichertes_theme_lesen() -> str:
    """Liest das zuletzt gewählte Theme pro Windows-Benutzer (QSettings/Registry)."""
    einstellungen = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
    wert = einstellungen.value(_SETTINGS_KEY_THEME, _THEME_DEFAULT)
    return wert if wert in _THEMES else _THEME_DEFAULT


def _theme_speichern(theme_name: str) -> None:
    QSettings(_SETTINGS_ORG, _SETTINGS_APP).setValue(_SETTINGS_KEY_THEME, theme_name)


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(_erzeuge_qss(_gespeichertes_theme_lesen()))

    start = StartDialog()
    if start.exec() != QDialog.Accepted or not start.pfad:
        return 0

    conn = init_db(start.pfad)

    fenster = HauptFenster(conn, start.pfad)
    fenster.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
