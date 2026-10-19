"""
Auswertung, Teilnehmerübersicht und Export der Desktop-Oberfläche (aus app.py ausgelagert,
offene Punkte O4, 19.10.2026): Reiter „Auswertung“ (Rangliste, Stechen), Teilnehmer-
übersicht je Leistungsklasse samt Behältnis-Bedarf und Reiter „Export“ (PDF-Ausdrucke,
CSV).

Bewusst KEIN `import app` (siehe desktop_programm.py): gemeinsame Helfer liegen in
desktop_gemeinsam.py.
"""

from __future__ import annotations

import os
import sqlite3

from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import pdf_export
from db import (
    alle_leistungsklassen,
    angebotene_pruefungen,
    BEHAELTNIS_BEDARF_HINWEIS,
    BEHAELTNIS_BEDARF_SPALTEN,
    BEHAELTNIS_BEDARF_TITEL,
    behaeltnis_bedarf_zeilentexte,
    berechne_auswertung,
    berechne_behaeltnis_bedarf,
    berechne_teilnehmer_lk_uebersicht,
    get_veranstaltung,
    leistungsklasse_label,
    list_teilnehmer,
    setze_stechen_sieger,
    termine_ordner,
)
from db_import import exportiere_teilnehmer_csv
from desktop_darstellung import _farbe
from desktop_dialoge import BewertungsbogenAuswahlDialog
from desktop_gemeinsam import (
    _Ablageort,
    _ausfuehren,
    _datei_exportieren,
    _db_fehler_anzeigen,
    _export_dateiname,
    _ja_nein,
    _pdf_exportieren,
    _pfad_anzeige,
    _url_oeffnen,
    _zeitplan_pdf_exportieren,
)
from shs_core import (
    ABBRUCH_ABK,
    ABBRUCH_TEXT,
    DISQUALIFIZIERT_ABK,
    DISQUALIFIZIERT_TEXT,
    platz_text,
    stechen_gruppen,
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
    return _ja_nein(
        parent, "Stechen offen",
        "In " + ", ".join(offen) + " sind mehrere punktgleich auf Platz 1 – das Stechen ist noch "
        "nicht eingetragen (Reiter „Auswertung“ → „Stechen-Sieger festlegen…“).\n\n"
        "Die Ergebnisliste trotzdem jetzt speichern? Dort steht dann „Stechen offen“.",
    )


def _eindeutige_texte(texte: list[str]) -> list[str]:
    """Hängt an mehrfach vorkommende Texte einen Zähler an („A [1]“, „A [2]“), damit eine
    Auswahl per Text eindeutig zugeordnet werden kann (Abschluss-QS 15.10.2026)."""
    gezaehlt: dict[str, int] = {}
    ergebnis = []
    for text in texte:
        if texte.count(text) > 1:
            gezaehlt[text] = gezaehlt.get(text, 0) + 1
            ergebnis.append(f"{text} [{gezaehlt[text]}]")
        else:
            ergebnis.append(text)
    return ergebnis


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

    def _stechen_bezeichnung(self, t) -> str:
        """Name mit Hund und Start-Nr. (Teil 4 Nr. 2), z. B. „Max Muster mit Ali (Nr. 1)“."""
        text = _vorname_nachname(t.name)
        hund = self._rufname_hund_je_id.get(str(t.id))
        nummer = self._startnummer_je_id.get(str(t.id))
        if hund:
            text += f" mit {hund}"
        if nummer is not None:
            text += f" (Nr. {nummer})"
        return text

    def _stechen_sieger_festlegen(self) -> None:
        """S1: je Gleichstand um Platz 1 den Stechen-Sieger wählen (oder offen lassen)."""
        gruppen = stechen_gruppen(self._fertig)
        if not gruppen:
            QMessageBox.information(self, "Kein Stechen", "Es gibt keinen Gleichstand um Platz 1.")
            return
        offen_text = "Stechen noch offen"
        # Desktop-Prüfung 14.10.2026 (Teil 4 Nr. 2): Einträge mit Hund und Start-Nr. (eine Person
        # mit zwei Hunden stand sonst zweimal gleich da), jeder Text eindeutig; ohne Sieger ist
        # „noch offen“ vorgewählt.
        eintraege, zuordnung = [], []
        aktuell = None
        for lk, gruppe in gruppen.items():
            for t in gruppe:
                if t.stechen == "gewonnen":
                    aktuell = len(eintraege)
                eintraege.append(f"{lk}: {self._stechen_bezeichnung(t)} ({t.gesamtpunkte} Punkte)")
                zuordnung.append((lk, int(t.id)))
            if aktuell is None:
                aktuell = len(eintraege)
            eintraege.append(f"{lk}: {offen_text}")
            zuordnung.append((lk, None))
        # QInputDialog liefert nur den Text - gleichlautende Einträge (gleicher Name und Hund,
        # ohne Start-Nr.) bekommen deshalb einen Zähler (Abschluss-QS 15.10.2026).
        eintraege = _eindeutige_texte(eintraege)
        auswahl, ok = QInputDialog.getItem(
            self, "Stechen-Sieger festlegen",
            "Wer hat das Stechen gewonnen? Er wird 1., die anderen Punktgleichen werden 2.",
            eintraege, aktuell, False,
        )
        if not ok:
            return
        lk, sieger = zuordnung[eintraege.index(auswahl)]
        try:
            setze_stechen_sieger(self.conn, sieger, [int(t.id) for t in gruppen[lk]])
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
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
        _pdf_exportieren(self, self._ablageort, self.status_label, "Rangliste speichern",
                         _export_dateiname(self.conn, praefix),
                         lambda pfad: pdf_export.erstelle_ergebnisliste_pdf(self.conn, pfad, leistungsklasse),
                         "Rangliste gespeichert")

    def aktualisieren(self) -> None:
        """Berechnet die Auswertung aus der Datenbank neu und aktualisiert den Filter."""
        self._fertig, self._ausstehend = berechne_auswertung(self.conn)
        # Teilnehmerergebnis (shs_core) kennt keine Startnummer - für die Anzeige/den
        # Filter hier separat aus den Stammdaten nachschlagen.
        stammdaten = list_teilnehmer(self.conn)
        self._startnummer_je_id = {str(t["id"]): t["startnummer"] for t in stammdaten}
        self._rufname_hund_je_id = {str(t["id"]): t["rufname_hund"] for t in stammdaten}

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
        alle_gruppen = stechen_gruppen(self._fertig)
        gruppen = {lk: g for lk, g in alle_gruppen.items() if lk in sichtbare_lk}
        self.stechen_btn.setEnabled(bool(alle_gruppen))
        von_hinweise = [
            f"Stechen nötig in {lk}: "
            + ", ".join(self._stechen_bezeichnung(t) for t in g)
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


# Desktop-Prüfung 14.10.2026 (Teil 5 Nr. 1 / Teil 6, Marcos Entscheidung): Hinweis nach dem
# CSV-Export, weil Excel beim Speichern Ziffernfolgen verändert.
_EXCEL_CSV_HINWEIS = (
    "Excel kürzt beim Speichern lange Nummern (Chip-Nr.) und entfernt führende Nullen (PLZ, "
    "Telefon). Zum Bearbeiten die Datei in Excel über Daten → Aus Text/CSV laden und diese "
    "Spalten dabei als Text festlegen."
)


class ExportTab(QWidget):
    """Reiter "Export" (Ausdrucke und Listen): PDFs wie Ergebnislisten, Statistik und
    Bewertungsbögen (siehe pdf_export.py) sowie die Teilnehmerliste als CSV. Liest bei jedem Klick direkt den aktuellen Datenbankstand, hält also nichts vor."""

    def __init__(self, conn, termin_pfad: str | None = None, ablageort: _Ablageort | None = None, parent=None):
        super().__init__(parent)
        self.conn = conn
        # Ablageort für Exporte: im Hauptfenster das gemeinsame Objekt aller Reiter
        # (Standard "Ausdrucke/<Termin>", siehe HauptFenster); wählt der Nutzer beim
        # Speichern einen anderen Ordner, gilt dieser für die nächsten Exporte in allen
        # Reitern. Der Rückfall auf den Ordner der Termin-Datei greift nur ohne Hauptfenster.
        self._ablageort = ablageort if ablageort is not None else _Ablageort(
            os.path.dirname(termin_pfad) if termin_pfad else str(termine_ordner())
        )

        teilnehmerliste_btn = QPushButton("Teilnehmerliste speichern (CSV, für Excel)…")
        teilnehmerliste_btn.clicked.connect(self._teilnehmerliste_exportieren)
        # Nutzerwunsch 28.09.2026: ausfüllbares Anmeldeformular statt der bisherigen
        # Word-Vorlage (siehe pdf_export.erstelle_anmeldeformular_pdf).
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

        # Rückmeldung Marco 13.10.2026: statt eines langen, unübersichtlichen Erklärtextes
        # unter den Knöpfen steht neben jedem Knopf eine kurze Zeile; Einzelheiten zeigt der
        # Tooltip an Knopf und Kurztext (ausführlich: Handbuch, Abschnitt "Export").
        knoepfe = [
            (anmeldeformular_btn,
             "Ausfüllbares Formular zum Verschicken; Kopf und Prüfungen aus dem Reiter „Verwaltung“",
             "Dort zuerst die angebotenen Prüfungen anhaken. Ausgefüllt zurückgeschickte "
             "Formulare im Reiter „Formular-Import“ einlesen."),
            (ergebnisliste_btn,
             "Rangliste mit Wertnoten je Leistungsklasse",
             "Platz, Start-Nr., Name, Gesamtpunkte und Wertnote. Teilnehmer, die nicht "
             "bestanden haben, stehen ohne Platz in der Liste."),
            (leere_ergebnisliste_btn,
             "Leeres Formular, um Ergebnisse erst auf Papier festzuhalten",
             "Start-Nr., Name und Verein sind vorausgefüllt, Platz, Punkte und Wertnote bleiben "
             "leer – zum späteren Übertragen in die Ergebniserfassung."),
            (etiketten_btn,
             "Ergebnisse zum Aufkleben, zwei Zeilen je Teilnehmer",
             "Für Klebe-/Etikettenpapier. Teilnehmer ohne vollständiges Ergebnis bekommen "
             "ebenfalls ein Etikett mit leeren Punktfeldern. Das Feld „SH-R“ bleibt zum "
             "Abstempeln bzw. Unterschreiben frei."),
            (statistik_btn,
             "Prädikat-Übersicht je Art/Leistungsklasse, inkl. Jugendliche",
             "Jugendliche: vollständig bewertete Teilnehmer unter 18 Jahren am Prüfungstag, "
             "nach dem Geburtsdatum im Teilnehmer-Dialog. Vereins-Nr., Prüfungsnummer, Richter und Prüfungsleiter im "
             "Kopf kommen aus dem Reiter „Verwaltung“."),
            (pruefungsleitung_btn,
             "Stammdaten, Gebühr, bezahlt?, Impfpass",
             "„bezahlt?“ kommt aus dem Bezahlt-Status, „Impfpass gültig bis“ aus der "
             "Tollwutimpfung im Teilnehmer-Dialog – rot, wenn das Datum fehlt oder am "
             "Prüfungstag abgelaufen ist. Die Gebühren ED/DK stehen im Reiter „Verwaltung“."),
            (chipliste_btn,
             "Start-Nr., Name, Hund, Chip-Nr. zum Abgleich am Prüfungstag",
             "Sortiert nach Startnummer, z. B. für eine Chip-Scanner-Station."),
            (leistungsrichter_btn,
             "Benötigte Richterzahl aus der Teilnehmerzahl",
             "1 ED = 1 Einheit, 1 DK = 3 Einheiten, höchstens 36 Einheiten je Richter."),
            (zeitplan_btn,
             "Ablauf aus dem Reiter „Zeitplan“, eine Seite je Richter",
             "Prüfungsblöcke mit Start- und Endzeit je Teilnehmer sowie die Pausen, farbig "
             "nach Art/Leistungsklasse."),
            (boegen_btn,
             "Sammel-PDF; vorher Auswahl der Leistungsklassen/Disziplinen. Einzelbogen: Reiter „Teilnehmer“",
             "Bereits eingetragene Ergebnisse sind vorausgefüllt, offene Felder bleiben zum "
             "Ausfüllen vor Ort leer. Die Auswahl hilft beim doppelseitigen Druck, damit kein "
             "anderes Team auf der Rückseite landet."),
            (teilnehmerliste_btn,
             "Alle Teilnehmer mit Stammdaten, für Excel (lässt sich wieder einlesen)",
             "Eine CSV-Datei mit Stammdaten, Startnummer, Bezahlt und „Keine Teilnahme“. Sie "
             "öffnet sich per Doppelklick in Excel und lässt sich im Reiter „Formular-Import“ "
             "wieder einlesen."),
        ]
        knopf_raster = QGridLayout()
        knopf_raster.setColumnStretch(1, 1)
        for zeile, (knopf, kurztext, tooltip) in enumerate(knoepfe):
            beschreibung = QLabel(kurztext)
            beschreibung.setWordWrap(True)
            knopf.setToolTip(tooltip)
            beschreibung.setToolTip(tooltip)
            knopf_raster.addWidget(knopf, zeile, 0)
            knopf_raster.addWidget(beschreibung, zeile, 1)

        self.status_label = QLabel("")
        self.status_label.setTextFormat(Qt.PlainText)  # S-1: enthält Pfade/Namen
        self.status_label.setWordWrap(True)

        button_zeile = QHBoxLayout()
        button_zeile.addWidget(ablageort_btn)
        button_zeile.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Ausdrucke und Listen"))
        layout.addLayout(knopf_raster)
        layout.addLayout(button_zeile)
        # UX-Test 02.10.2026, U7: Statuszeile direkt unter den Knöpfen.
        layout.addWidget(self.status_label)
        layout.addStretch()

    def aktualisieren(self) -> None:
        pass  # kein Zwischenspeicher - wird bei jedem Export frisch aus der DB gelesen

    def _export_dateiname(self, praefix: str) -> str:
        return _export_dateiname(self.conn, praefix)

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
                f"Der Ablageort „{_pfad_anzeige(self._ablageort.pfad)}“ existiert nicht (mehr).",
            )
            return
        _url_oeffnen(self, QUrl.fromLocalFile(self._ablageort.pfad), _pfad_anzeige(self._ablageort.pfad))

    def _pdf_export_ausfuehren(self, titel: str, dateiname_praefix: str, export_fn, status_text) -> None:
        """PDF-Export dieses Tabs mit dem Dateinamen-Präfix des Termins - der Ablauf selbst
        steht in desktop_gemeinsam._pdf_exportieren (gemeinsam für alle Reiter)."""
        _pdf_exportieren(self, self._ablageort, self.status_label, titel,
                         self._export_dateiname(dateiname_praefix), export_fn, status_text)

    def _teilnehmerliste_exportieren(self) -> None:
        """Nutzerwunsch 02.10.2026 (UX-Test, N1): alle Teilnehmer als Excel-freundliche CSV -
        über den gemeinsamen Exportablauf (H3, 15.10.2026)."""
        vorschlag = os.path.splitext(self._export_dateiname("Teilnehmerliste"))[0] + ".csv"
        _datei_exportieren(
            self, self._ablageort, self.status_label, "Teilnehmerliste speichern", vorschlag,
            lambda pfad: exportiere_teilnehmer_csv(self.conn, pfad),
            lambda anzahl: f"Teilnehmerliste ({anzahl} Teilnehmer) gespeichert",
            dateifilter="CSV-Datei (*.csv)", datei_art="CSV", datei_oeffnen_text="In Excel öffnen",
            hinweis=_EXCEL_CSV_HINWEIS, meldung_titel="Teilnehmerliste gespeichert",
        )

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
        if _ausfuehren(auswahl_dialog) != QDialog.Accepted:
            return
        erlaubte_labels = auswahl_dialog.ausgewaehlte_labels()

        self._pdf_export_ausfuehren(
            "Bewertungsbögen speichern", "Bewertungsboegen",
            lambda pfad: pdf_export.erstelle_alle_bewertungsboegen_pdf(self.conn, pfad, erlaubte_labels=erlaubte_labels),
            lambda anzahl: f"{anzahl} Bewertungsbögen gespeichert",
        )
