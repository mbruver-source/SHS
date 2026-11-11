"""
Reiter „Abrechnung Leistungsrichter“ der Desktop-Oberfläche (Marco, 09.11.2026): je
Leistungsrichter des Termins Kilometer (Gesamtstrecke Hin und zurück) und Tagespauschale,
Fahrtkosten und Summe, dazu PDF-Übersicht und Quittungen. Die Rechenregeln und die
Speicherform stehen in lr_abrechnung.py, die PDFs in pdf_export.py.

Bewusst KEIN `import app` (siehe desktop_programm.py): gemeinsame Helfer liegen in
desktop_gemeinsam.py.
"""

from __future__ import annotations

import os

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import pdf_export
from db import get_veranstaltung
from db_import import exportiere_abrechnung_csv
from desktop_gemeinsam import zugaengliche_namen_setzen
from desktop_gemeinsam import (
    _aktualisiere_veranstaltung_feld,
    _Ablageort,
    _ablageort_ordner_oeffnen,
    _datei_exportieren,
    _db_fehler_anzeigen,
    _dateiname_teil,
    _export_dateiname,
    _pdf_exportieren,
    kurzer_hinweis,
)
from lr_abrechnung import (
    KM_SATZ_STANDARD,
    TAGESPAUSCHALE_STANDARD,
    abrechnungszeilen,
    eingabe_text,
    euro_text,
    gesamtsumme,
    km_lesen,
    km_satz_des_termins,
    km_satz_lesen,
    pauschale_des_termins,
    pauschale_lesen,
    richter_eingaben_als_text,
    richter_eingaben_lesen,
)

# Spalten der Tabelle
_SP_NAME, _SP_KM, _SP_SATZ, _SP_PAUSCHALE, _SP_FAHRT, _SP_SUMME, _SP_QUITTUNG = range(7)
_EINGABE_FELDER = {_SP_KM: "km", _SP_SATZ: "km_satz", _SP_PAUSCHALE: "pauschale"}
_EINGABE_NAMEN = {"km": "Kilometer", "km_satz": "Satz je km", "pauschale": "Tagespauschale"}
_LESER = {"km": km_lesen, "km_satz": km_satz_lesen, "pauschale": pauschale_lesen}
_STELLEN = {"km": 1, "km_satz": 2, "pauschale": 2}


class AbrechnungTab(QWidget):
    """Abrechnung der Leistungsrichter: Eingaben werden beim Verlassen eines Felds in den
    Veranstaltungsdaten des Termins gespeichert."""

    def __init__(self, conn, ablageort: _Ablageort | None = None, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._ablageort = ablageort or _Ablageort("")
        self._aufbau = False  # True, solange die Tabelle befüllt wird (kein Speichern)

        saetze = self._saetze_aufbauen()
        self._tabelle_aufbauen()
        knoepfe = self._knoepfe_aufbauen()
        zugaengliche_namen_setzen(self, {
            "tabelle": "Abrechnung Leistungsrichter",
            "km_satz_feld": "Vergütung je Kilometer in Euro",
            "pauschale_feld": "Tagespauschale je Richter in Euro",
        })
        self._layout_aufbauen(saetze, knoepfe)
        self.aktualisieren()

    def _saetze_aufbauen(self) -> QHBoxLayout:
        """Felder für Kilometersatz und Tagespauschale des Termins."""
        self.km_satz_feld = QLineEdit()
        self.km_satz_feld.setMaximumWidth(110)
        self.km_satz_feld.editingFinished.connect(lambda: self._satz_geaendert("lr_km_satz"))
        self.pauschale_feld = QLineEdit()
        self.pauschale_feld.setMaximumWidth(110)
        self.pauschale_feld.editingFinished.connect(lambda: self._satz_geaendert("lr_tagespauschale"))

        saetze = QHBoxLayout()
        saetze.addWidget(QLabel("Vergütung je km (€):"))
        saetze.addWidget(self.km_satz_feld)
        saetze.addSpacing(16)
        saetze.addWidget(QLabel("Tagespauschale je Richter (€):"))
        saetze.addWidget(self.pauschale_feld)
        saetze.addStretch()
        return saetze

    def _tabelle_aufbauen(self) -> None:
        self.tabelle = QTableWidget(0, 7)
        self.tabelle.setHorizontalHeaderLabels(
            ["Leistungsrichter", "Kilometer (Hin und zurück)", "Satz je km (€)", "Tagespauschale (€)",
             "Fahrtkosten", "Summe", "Quittung"])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.tabelle.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabelle.horizontalHeader().setSectionResizeMode(_SP_NAME, QHeaderView.ResizeToContents)
        # Breite der Quittungsspalte richtet sich nach dem Knopf (ResizeToContents sieht Zellen-
        # Widgets nicht), siehe aktualisieren()
        self.tabelle.horizontalHeader().setSectionResizeMode(_SP_QUITTUNG, QHeaderView.Fixed)
        self.tabelle.itemChanged.connect(self._zelle_geaendert)

        self.leer_label = QLabel(
            "Keine Leistungsrichter eingetragen. Die Namen stehen in der Verwaltung unter "
            "„Veranstaltungsdaten bearbeiten…“ (Richter 1–5).")
        self.leer_label.setWordWrap(True)
        self.gesamt_label = QLabel("")
        self.gesamt_label.setObjectName("abrechnungGesamt")

    def _knoepfe_aufbauen(self) -> QHBoxLayout:
        self.uebersicht_btn = QPushButton("Übersicht als PDF…")
        self.uebersicht_btn.clicked.connect(self._uebersicht_exportieren)
        self.csv_btn = QPushButton("Export als CSV…")
        self.csv_btn.setToolTip(
            "Eine Zeile je Richter (Datum, Empfänger, Verwendungszweck, Kilometer, Satz, "
            "Fahrtkosten, Tagespauschale, Betrag, Art „Ausgabe“) für ein Vereinstool mit Ein- "
            "und Ausgaben.")
        self.csv_btn.clicked.connect(self._csv_exportieren)
        self.ablageort_btn = QPushButton("Ablageort öffnen")
        self.ablageort_btn.clicked.connect(self._ablageort_oeffnen)
        knoepfe = QHBoxLayout()
        knoepfe.addWidget(self.uebersicht_btn)
        knoepfe.addWidget(self.csv_btn)
        knoepfe.addWidget(self.ablageort_btn)
        knoepfe.addStretch()
        return knoepfe

    def _layout_aufbauen(self, saetze: QHBoxLayout, knoepfe: QHBoxLayout) -> None:
        hinweis = kurzer_hinweis(
            "Kilometer als Gesamtstrecke eintragen; Satz und Pauschale je Richter bleiben leer, "
            "wenn der Satz des Termins gilt (er steht dann vorbelegt in der Zeile).",
            "Fahrtkosten = Kilometer × Satz je km, Summe = Fahrtkosten + Tagespauschale (auf Cent "
            f"gerundet). Standardwerte: {KM_SATZ_STANDARD} € je km und {TAGESPAUSCHALE_STANDARD} € "
            "Tagespauschale; beide lassen sich für den Termin und je Richter ändern. Es erscheinen "
            "nur Richter mit eingetragenem Namen. Die Eingaben gehören zur Position (Richter 1–5): "
            "wird ein Richter umbenannt, bleiben die Beträge stehen.",
        )
        self.status_label = QLabel("")
        self.status_label.setTextFormat(Qt.PlainText)  # enthält Namen
        self.status_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Abrechnung Leistungsrichter"))
        layout.addLayout(saetze)
        layout.addWidget(hinweis)
        layout.addWidget(self.leer_label)
        layout.addWidget(self.tabelle, 1)
        layout.addWidget(self.gesamt_label)
        layout.addLayout(knoepfe)
        layout.addWidget(self.status_label)

    # --- Anzeige -------------------------------------------------------------

    def aktualisieren(self) -> None:
        """Liest alles frisch aus der Datenbank (die Richternamen kommen aus dem Reiter
        Verwaltung)."""
        veranstaltung = get_veranstaltung(self.conn) or {}
        self._aufbau = True
        try:
            # Die Sätze des Termins stehen in den Feldern (Standard 0,35 und 50, wenn nichts
            # gespeichert ist), nicht nur als blasser Platzhalter.
            self.km_satz_feld.setText(eingabe_text(km_satz_des_termins(veranstaltung), 2))
            self.pauschale_feld.setText(eingabe_text(pauschale_des_termins(veranstaltung), 2))
            self.km_satz_feld.setPlaceholderText(KM_SATZ_STANDARD)
            self.pauschale_feld.setPlaceholderText(TAGESPAUSCHALE_STANDARD)
            eingaben = richter_eingaben_lesen(veranstaltung)
            zeilen = abrechnungszeilen(veranstaltung)
            termin_satz = eingabe_text(km_satz_des_termins(veranstaltung), 2)
            termin_pauschale = eingabe_text(pauschale_des_termins(veranstaltung), 2)
            self.tabelle.setRowCount(len(zeilen))
            for reihe, z in enumerate(zeilen):
                eintrag = eingaben.get(z.nummer, {})
                name = QTableWidgetItem(z.name)
                name.setFlags(Qt.ItemIsEnabled)
                name.setData(Qt.UserRole, z.nummer)
                self.tabelle.setItem(reihe, _SP_NAME, name)
                for spalte, feld in _EINGABE_FELDER.items():
                    # Satz und Pauschale sind mit den Werten des Termins vorbelegt
                    vorgabe = {"km": "", "km_satz": termin_satz, "pauschale": termin_pauschale}[feld]
                    zelle = QTableWidgetItem(eintrag.get(feld) or vorgabe)
                    zelle.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    zelle.setToolTip({
                        "km": "Gesamtstrecke Hin und zurück in Kilometern",
                        "km_satz": f"Satz des Termins: {termin_satz} € (Eingabe überschreibt ihn für diesen Richter)",
                        "pauschale": f"Pauschale des Termins: {termin_pauschale} € (Eingabe überschreibt sie für diesen Richter)",
                    }[feld])
                    self.tabelle.setItem(reihe, spalte, zelle)
                self._betraege_setzen(reihe, z)
                knopf = QPushButton("Quittung…")
                knopf.setToolTip(f"Quittung für {z.name} als PDF speichern")
                knopf.clicked.connect(lambda _=False, nummer=z.nummer, name=z.name: self._quittung_exportieren(nummer, name))
                self.tabelle.setCellWidget(reihe, _SP_QUITTUNG, knopf)
                self.tabelle.setColumnWidth(_SP_QUITTUNG, max(
                    self.tabelle.columnWidth(_SP_QUITTUNG), knopf.sizeHint().width() + 32,
                    self.tabelle.horizontalHeader().sectionSizeHint(_SP_QUITTUNG) + 16))
                # Zeile so hoch wie der Knopf samt Rand, sonst wird seine Beschriftung abgeschnitten
                self.tabelle.setRowHeight(reihe, max(self.tabelle.rowHeight(reihe), knopf.sizeHint().height() + 12))
            self.tabelle.setVisible(bool(zeilen))
            self.leer_label.setVisible(not zeilen)
            self.uebersicht_btn.setEnabled(bool(zeilen))
            self.csv_btn.setEnabled(bool(zeilen))
            self._gesamt_setzen(zeilen)
        finally:
            self._aufbau = False

    def _betraege_setzen(self, reihe: int, z) -> None:
        for spalte, wert in ((_SP_FAHRT, z.fahrtkosten), (_SP_SUMME, z.summe)):
            zelle = QTableWidgetItem(euro_text(wert))
            zelle.setFlags(Qt.ItemIsEnabled)
            zelle.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tabelle.setItem(reihe, spalte, zelle)

    def _gesamt_setzen(self, zeilen) -> None:
        self.gesamt_label.setText(
            f"Gesamtsumme: {euro_text(gesamtsumme(zeilen))}" if zeilen else "")

    # --- Eingaben speichern --------------------------------------------------

    def _speichern(self, **felder) -> bool:
        try:
            _aktualisiere_veranstaltung_feld(self.conn, **felder)
        except Exception as exc:  # noqa: BLE001 - Datenbankfehler als Meldung statt Absturz
            _db_fehler_anzeigen(self, exc)
            return False
        return True

    def _satz_geaendert(self, spalte: str) -> None:
        feld = self.km_satz_feld if spalte == "lr_km_satz" else self.pauschale_feld
        leser = km_satz_lesen if spalte == "lr_km_satz" else pauschale_lesen
        name = "Vergütung je km" if spalte == "lr_km_satz" else "Tagespauschale"
        text = feld.text().strip()
        wert = leser(text) if text else None
        if text and wert is None:
            self.status_label.setText(
                f"{name}: „{text}“ ist keine gültige Zahl (0 bis "
                f"{'10' if spalte == 'lr_km_satz' else '10.000'}). Der alte Wert bleibt.")
            self.aktualisieren()
            return
        standard = Decimal(KM_SATZ_STANDARD.replace(",", ".") if spalte == "lr_km_satz" else TAGESPAUSCHALE_STANDARD)
        # Der Standardwert wird nicht gespeichert: so bleibt ein Termin ohne eigene Sätze ohne sie.
        gespeichert = eingabe_text(wert, 2) if wert is not None and wert != standard else None
        if self._speichern(**{spalte: gespeichert}):
            self.status_label.setText(f"{name} gespeichert." if gespeichert else
                                      f"{name}: Standardwert wird verwendet.")
        self.aktualisieren()

    def _zelle_geaendert(self, zelle: QTableWidgetItem) -> None:
        if self._aufbau or zelle.column() not in _EINGABE_FELDER:
            return
        feld = _EINGABE_FELDER[zelle.column()]
        nummer = self.tabelle.item(zelle.row(), _SP_NAME).data(Qt.UserRole)
        text = zelle.text().strip()
        wert = _LESER[feld](text) if text else None
        veranstaltung = get_veranstaltung(self.conn) or {}
        eingaben = richter_eingaben_lesen(veranstaltung)
        if text and wert is None:
            self.status_label.setText(
                f"{_EINGABE_NAMEN[feld]} von {self.tabelle.item(zelle.row(), _SP_NAME).text()}: "
                f"„{text}“ ist keine gültige Zahl. Der alte Wert bleibt.")
            self.aktualisieren()
            return
        # Der Wert des Termins wird nicht je Richter gespeichert: die Zeile folgt dann einer
        # späteren Änderung des Termin-Satzes.
        if feld == "km_satz" and wert == km_satz_des_termins(veranstaltung):
            wert = None
        elif feld == "pauschale" and wert == pauschale_des_termins(veranstaltung):
            wert = None
        eingaben.setdefault(nummer, {})[feld] = eingabe_text(wert, _STELLEN[feld])
        if self._speichern(lr_abrechnung=richter_eingaben_als_text(eingaben)):
            self.status_label.setText("")
        self.aktualisieren()

    # --- Export --------------------------------------------------------------

    def _uebersicht_exportieren(self) -> None:
        _pdf_exportieren(
            self, self._ablageort, self.status_label, "Abrechnung speichern",
            _export_dateiname(self.conn, "Abrechnung_Leistungsrichter"),
            lambda pfad: pdf_export.erstelle_abrechnung_pdf(self.conn, pfad),
            "Abrechnung gespeichert")

    def _csv_exportieren(self) -> None:
        vorschlag = os.path.splitext(_export_dateiname(self.conn, "Abrechnung_Leistungsrichter"))[0] + ".csv"
        _datei_exportieren(
            self, self._ablageort, self.status_label, "Abrechnung als CSV speichern", vorschlag,
            lambda pfad: exportiere_abrechnung_csv(self.conn, pfad),
            lambda anzahl: f"Abrechnung ({anzahl} Richter) als CSV gespeichert",
            dateifilter="CSV-Datei (*.csv)", datei_art="CSV", datei_oeffnen_text="In Excel öffnen",
            meldung_titel="Abrechnung gespeichert")

    def _quittung_exportieren(self, nummer: int, name: str) -> None:
        """Quittung eines einzelnen Richters als eigenes PDF."""
        _pdf_exportieren(
            self, self._ablageort, self.status_label, "Quittung speichern",
            _export_dateiname(self.conn, f"Quittung_{_dateiname_teil(name)}"),
            lambda pfad: pdf_export.erstelle_quittungen_pdf(self.conn, pfad, nummer),
            f"Quittung für {name} gespeichert")

    def _ablageort_oeffnen(self) -> None:
        _ablageort_ordner_oeffnen(self, self._ablageort)
