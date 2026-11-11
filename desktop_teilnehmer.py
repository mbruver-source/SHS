"""
Reiter Teilnehmer der Desktop-Oberfläche samt den Hilfen für Meldungen nach Importen
(seit 11.11.2026 aus app.py ausgelagert). Bewusst KEIN `import app` (siehe
desktop_programm.py): gemeinsame Helfer liegen in desktop_gemeinsam.py.
"""
from __future__ import annotations

import os
import sqlite3

from PySide6.QtCore import (
    QItemSelectionModel,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from db import (
    add_teilnehmer,
    angebotene_pruefungen,
    delete_teilnehmer,
    get_teilnehmer,
    get_veranstaltung,
    hat_erfasste_ergebnisse,
    leistungsklasse_label,
    list_teilnehmer,
    nummern_ausserhalb_nach_tausch,
    pruefung_nach_bezeichnung,
    sortiere_pruefungen,
    setze_bezahlt,
    setze_keine_teilnahme,
    tausche_startnummern,
    teilnehmer_fehlende_pflichtangaben,
    teilnehmer_gegenstand_hinweis,
    termine_ordner,
    update_teilnehmer,
    vergebene_startnummern,
    fehlende_startnummern_je_pruefung,
    pruefungs_kuerzel,
    startnummer_bereiche,
    startnummern_wiederherstellen,
    startnummern_zuruecksetzen,
    teilnehmer_sichern,
    teilnehmer_wiederherstellen,
)
from db_import import (
    importiere_teilnehmer_stammdaten,
    nicht_angebotene,
)
from desktop_darstellung import (
    _farbe,
)
from desktop_gemeinsam import (
    _Ablageort,
    _ablageort_ordner_oeffnen,
    _bewertungsbogen_fuer_teilnehmer,
    _kontextmenue_aus_knoepfen,
    _name_passt,
    _db_fehler_anzeigen,
    _ja_nein,
    _fehler_anzeigen,
    _NumerischSortierbaresItem,
    _PruefungSortierbaresItem,
    _ausfuehren,
    symbol,
)
from desktop_rueckgaengig import RueckgaengigSpeicher
from desktop_import_meldungen import (
    _fehlende_startnummern_vergeben_mit_meldung,
    _import_db_fehler_melden,
    _letzten_import_zeigen,
    _meldung_mit_listen,
    _meldungstext_voll,
    _NICHTS_ZU_TAUSCHEN,
    _ohne_startnummer_ids,
    _pruefung_bezeichnung,
    _startnummern_nach_import_anbieten,
    _teilnehmerliste_importieren,
    _teilnehmerzahl,
)
from desktop_dialoge import (
    StartnummerTauschenDialog,
    TeilnehmerDialog,
    TerminImportDialog,
)




class TeilnehmerTab(QWidget):
    # Bei jedem Neuladen der Liste (Teilnehmer angelegt, gelöscht, „keine Teilnahme“ …) -
    # das Hauptfenster aktualisiert damit die Teilnehmerzahl im Kopfbalken.
    teilnehmer_geaendert = Signal()

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

        self._tabelle_aufbauen()
        self._filter_aufbauen()
        self._knoepfe_aufbauen()
        self._rueckgaengig_aufbauen()
        self._layout_aufbauen()
        self.aktualisieren()

    def _tabelle_aufbauen(self) -> None:
        self.tabelle = QTableWidget(0, 8)
        self.tabelle.setHorizontalHeaderLabels(
            ["Start-Nr.", "Nachname", "Vorname", "Hund", "Art/LK", "Verein", "Bezahlt", "Anmerkungen"]
        )
        # Nachtest 2 (N11): was „Gegenstand noch offen“ heißt, stand nur am einzelnen Eintrag.
        self.tabelle.horizontalHeaderItem(7).setToolTip(
            "Orange mit Warndreieck: vor dem Prüfungstag beheben (z. B. „Chip-Nr. fehlt“).\n"
            "Grau: nur eine Erinnerung – „Gegenstand noch offen“ heißt, die zu suchenden "
            "Gegenstände sind noch nicht eingetragen. Sie können bis zum Prüfungstag über "
            "„Bearbeiten…“ nachgetragen werden."
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

    def _filter_aufbauen(self) -> None:
        self.filter_combo = QComboBox()
        # Passt die Breite der Box an den längsten enthaltenen Eintrag an (z.B. lange
        # Art/LK-Bezeichnungen wie "Behältnisse LK 3"), statt Text abzuschneiden.
        self.filter_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.filter_combo.currentTextChanged.connect(self._filter_anwenden)

        self.filter_startnummer = QLineEdit()
        self.filter_startnummer.setPlaceholderText("z.B. 13")
        self.filter_startnummer.setMaximumWidth(80)
        self.filter_startnummer.textChanged.connect(self._filter_anwenden)

        # Marco 10.11.2026 (UI-Abgleich): Suche nach Name oder Hund (Teilwort genügt).
        self.filter_name = QLineEdit()
        self.filter_name.setPlaceholderText("Name oder Hund")
        self.filter_name.setMaximumWidth(160)
        self.filter_name.setClearButtonEnabled(True)
        self.filter_name.textChanged.connect(self._filter_anwenden)

        # Nutzerwunsch (20.09.): zusätzlicher Filter nach Bezahlt-Status, z.B. um am
        # Anmeldetisch schnell zu sehen, wer noch nicht bezahlt hat. Feste drei Einträge
        # (anders als filter_combo oben) - keine Neubefüllung bei jedem aktualisieren() nötig.
        self.filter_bezahlt = QComboBox()
        self.filter_bezahlt.addItems(["Alle", "Bezahlt", "Nicht bezahlt"])
        self.filter_bezahlt.currentTextChanged.connect(self._filter_anwenden)

    def _knoepfe_aufbauen(self) -> None:
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
        # Nachtest 2 (N15, Marco 04.11.2026): Entf in der Liste wirkt wie „Löschen“ (aus Excel
        # gewohnt) - mit derselben Rückfrage, Vorgabe „Nein“.
        self.loeschen_btn.setToolTip("Tastenkürzel: Entf")
        entf_kuerzel = QShortcut(QKeySequence.Delete, self.tabelle)
        entf_kuerzel.setContext(Qt.WidgetShortcut)
        entf_kuerzel.activated.connect(self._teilnehmer_loeschen)

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
        self._import_btn = import_btn = QPushButton("Aus anderem Termin importieren…")
        import_btn.clicked.connect(self._aus_anderem_termin_importieren)

        # UX-Test 02.10.2026, U10: die Excel-/CSV-Liste auch direkt hier einlesen können
        # (Laien suchten sie im Reiter "Teilnehmer" bzw. unter "Aus anderem Termin").
        self._liste_btn = liste_btn = QPushButton("Teilnehmerliste einlesen (Excel/CSV)…")
        # N8 (nach 1.0.40): eindeutig "einlesen" - der fast gleich benannte Export-Knopf im
        # Reiter "Ausdrucke/Export" heißt "Teilnehmerliste speichern (CSV, für Excel)…".
        liste_btn.setToolTip(
            "Eine Excel-Liste (als CSV gespeichert) mit einer Zeile je Teilnehmer einlesen. "
            "Speichern als CSV geht im Reiter „Ausdrucke/Export“."
        )
        liste_btn.clicked.connect(self._teilnehmerliste_importieren)

        # Nutzerwunsch (21.09.): "In Teilnehmerliste Absprung zu Bewertungsbögen erzeugen
        # einfügen?" - Entscheidung (Rückfrage beantwortet): Direkt-Button pro Teilnehmer
        # statt nur eines Links zum Export-Tab, erzeugt sofort den Bewertungsbogen für den
        # ausgewählten Teilnehmer (siehe _bewertungsbogen_exportieren unten).
        self.bewertungsbogen_btn = QPushButton("Bewertungsbogen (PDF)…")
        self.bewertungsbogen_btn.clicked.connect(self._bewertungsbogen_exportieren)
        self.bewertungsbogen_btn.setEnabled(False)

    def _rueckgaengig_aufbauen(self) -> None:
        # Marco 10.11.2026 (UI-Abgleich): wie bei den übrigen Reitern mit PDF-Export; eigene
        # Zeile, damit die beiden Knopfzeilen oben bei großer Schrift nicht breiter werden.
        # Marco 10.11.2026 (UI-Abgleich): Löschen und Startnummern zurücksetzen ließen sich nicht
        # zurücknehmen - eine Ebene „Rückgängig“ (Strg+Z in diesem Reiter).
        self.rueckgaengig_btn = QPushButton("Rückgängig")
        self._rueckgaengig = RueckgaengigSpeicher(self.rueckgaengig_btn)
        self.rueckgaengig_btn.clicked.connect(self._rueckgaengig_ausfuehren)
        rueckgaengig_kuerzel = QShortcut(QKeySequence.Undo, self)
        rueckgaengig_kuerzel.setContext(Qt.WidgetWithChildrenShortcut)
        rueckgaengig_kuerzel.activated.connect(
            lambda: self.rueckgaengig_btn.isEnabled() and self._rueckgaengig_ausfuehren())
        self.ablageort_btn = QPushButton("Ablageort öffnen")
        self.ablageort_btn.setToolTip("Zeigt den Ordner, in dem der Bewertungsbogen gespeichert wird")
        self.ablageort_btn.clicked.connect(lambda: _ablageort_ordner_oeffnen(self, self._ablageort))
        # Rechtsklick auf eine Zeile (Marco 10.11.2026): dieselben Aktionen wie die Knöpfe.
        _kontextmenue_aus_knoepfen(self.tabelle, [
            self.hinzufuegen_btn, None, self.bearbeiten_btn, self.bewertungsbogen_btn, None,
            self.bezahlt_btn, self.teilnahme_btn, self.tauschen_btn, None, self.loeschen_btn,
            self.rueckgaengig_btn,
        ], allgemein=(self.hinzufuegen_btn, self.rueckgaengig_btn))

    def _layout_aufbauen(self) -> None:
        # Vor-Build-Klärung 03.10.2026 (U12): zehn Knöpfe in einer Zeile waren auf kleinen
        # Laptops breiter als der Bildschirm - zweizeilig: oben die Arbeit am markierten
        # Teilnehmer, unten Startnummern und Importe. Nach 1.0.56 (Marco 05.11.2026): „Startnummer
        # tauschen…“ oben - die untere Zeile war bei Schrift „Sehr groß“ mit 1331 px zu breit für
        # einen 1366-px-Bildschirm; der Tausch wirkt ohnehin auf die markierten Teilnehmer.
        button_zeile = QHBoxLayout()
        for knopf in (self.hinzufuegen_btn, self.bearbeiten_btn, self.loeschen_btn, self.bezahlt_btn,
                      self.teilnahme_btn, self.tauschen_btn, self.bewertungsbogen_btn):
            button_zeile.addWidget(knopf)
        button_zeile.addStretch()
        button_zeile_2 = QHBoxLayout()
        for knopf in (self.vergeben_btn, self.zuruecksetzen_btn, self._import_btn, self._liste_btn):
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
        filter_zeile.addSpacing(16)
        filter_zeile.addWidget(QLabel("Suche:"))
        filter_zeile.addWidget(self.filter_name)
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
        status_zeile = QHBoxLayout()
        status_zeile.addWidget(self.status_label, 1)
        status_zeile.addWidget(self.rueckgaengig_btn, 0, Qt.AlignTop)
        status_zeile.addWidget(self.ablageort_btn, 0, Qt.AlignTop)
        layout.addLayout(status_zeile)

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
        filter_name = self.filter_name.text()
        for row in range(self.tabelle.rowCount()):
            item = self.tabelle.item(row, 0)
            t = self._teilnehmer_je_id.get(item.data(Qt.UserRole)) if item is not None else None
            if t is None:
                continue
            passt = (
                (filter_wert in ("Alle", "") or leistungsklasse_label(t) == filter_wert)
                and (not filter_startnr or str(t["startnummer"] or "") == filter_startnr)
                and _name_passt(filter_name, t["nachname"], t["vorname"], t["rufname_hund"])
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
            if partner is not None:
                # Der Dialog ist schon die Bestätigung - gefragt wird nur bei verschiedenen
                # Prüfungen (Nachtest 2, N4).
                self._tauschen_nach_rueckfrage(aktuell, partner, immer_fragen=False)

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
        self._tauschen_nach_rueckfrage(a, b, immer_fragen=True)

    def _tausch_warnung(self, a: dict, b: dict) -> str | None:
        """Nachtest 2 (N4, Marco 04.11.2026): Warnung, wenn die beiden in verschiedenen
        Prüfungen starten. Nennt die Bereiche, ob eine Nummer danach außerhalb ihres Bereichs
        liegt, und gespeicherte Ergebnisse; None bei gleicher Prüfung."""
        kuerzel = [pruefungs_kuerzel(t["art"], t["stufe"], t["disziplin"]) for t in (a, b)]
        if kuerzel[0] == kuerzel[1]:
            return None
        bereiche = startnummer_bereiche(get_veranstaltung(self.conn))

        def pruefung(k):
            bereich = bereiche.get(k)
            spanne = f"Bereich {bereich[0]}–{bereich[1]}" if bereich else "kein Bereich festgelegt"
            return f"{_pruefung_bezeichnung(k)}, {spanne}"

        # Außerhalb nur, wo es stimmt (Verifikation B15, siehe db.nummern_ausserhalb_nach_tausch).
        ausserhalb = nummern_ausserhalb_nach_tausch(bereiche, a, b)
        einleitung = "Achtung: Die beiden starten in verschiedenen Prüfungen"
        if ausserhalb == 2:
            einleitung += " – nach dem Tausch liegen beide Nummern außerhalb ihrer Startnummern-Bereiche"
        elif ausserhalb == 1:
            einleitung += " – nach dem Tausch liegt eine Nummer außerhalb ihres Startnummern-Bereichs"
        zeilen = [
            f"{einleitung}:",
            *(f"• {t['nachname']}, {t['vorname']}: {pruefung(k)}" for t, k in zip((a, b), kuerzel)),
        ]
        mit_ergebnis = [f"„{t['nachname']}, {t['vorname']}“" for t in (a, b)
                        if hat_erfasste_ergebnisse(self.conn, t["id"])]
        if mit_ergebnis:
            zeilen.append(
                f"Für {' und '.join(mit_ergebnis)} {'sind' if len(mit_ergebnis) == 1 else 'sind jeweils'} "
                "schon Ergebnisse gespeichert. Sie bleiben beim Teilnehmer, stehen danach aber "
                "unter der neuen Startnummer."
            )
        return "\n".join(zeilen)

    def _tauschen_nach_rueckfrage(self, a: dict, b: dict, *, immer_fragen: bool) -> None:
        """Tauscht nach Rückfrage (Vorgabe „Nein“) und meldet das Ergebnis in der Statuszeile
        (N4). Ohne immer_fragen wird nur bei verschiedenen Prüfungen gefragt."""
        def beschreibung(t):
            nummer = f"Nr. {t['startnummer']}" if t["startnummer"] is not None else "ohne Nummer"
            return f"„{t['nachname']}, {t['vorname']}“ ({nummer})"

        warnung = self._tausch_warnung(a, b)
        if immer_fragen or warnung:
            frage = f"Startnummern von {beschreibung(a)} und {beschreibung(b)} tauschen?"
            if warnung:
                frage += f"\n\n{warnung}\n\nTrotzdem tauschen?"
            if not _ja_nein(self, "Startnummern tauschen", frage):
                return
        try:
            tausche_startnummern(self.conn, a["id"], b["id"])
        except sqlite3.IntegrityError as exc:
            _fehler_anzeigen(self, exc)
            return
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        self.aktualisieren()
        nr_a, nr_b = a["startnummer"], b["startnummer"]
        if nr_a is not None and nr_b is not None:
            meldung = f"Nr. {nr_a} und {nr_b} getauscht."
        else:
            alt, neu = (a, b) if nr_a is not None else (b, a)
            meldung = (f"Nr. {alt['startnummer']} von {alt['nachname']}, {alt['vorname']} an "
                       f"{neu['nachname']}, {neu['vorname']} übertragen.")
        self.status_label.setText(meldung)

    def _gefilterte_pruefung(self) -> tuple[str | None, str | None]:
        """(Kürzel, Bezeichnung) der im Filter Art/LK gewählten Prüfung oder (None, None)
        bei "Alle" - schränkt Zurücksetzen und Vergabe ein (Marco 09.10.2026). Die
        Zuordnung läuft über die feste Prüfungsliste; passt keine Prüfung, kommt
        (None, Filtertext) zurück und die Aufrufer brechen ab, statt still auf "Alle"
        auszuweichen (Verifikation A)."""
        filter_wert = self.filter_combo.currentText()
        if filter_wert in ("Alle", ""):
            return None, None
        pruefung = pruefung_nach_bezeichnung(filter_wert)
        return (pruefung.kuerzel if pruefung is not None else None), filter_wert

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
        betroffen = [
            t for t in self._teilnehmer_je_id.values()
            if t["startnummer"] is not None
            and (pruefung is None or pruefungs_kuerzel(t["art"], t["stufe"], t["disziplin"]) == pruefung)
        ]
        anzahl = len(betroffen)
        wo = f" in „{bezeichnung}“" if bezeichnung else ""
        if not anzahl:
            QMessageBox.information(
                self, "Startnummern zurücksetzen", f"Es ist noch keine Startnummer{wo} vergeben."
            )
            return
        wer = f"der Teilnehmer in „{bezeichnung}“" if bezeichnung else "ALLER Teilnehmer"
        # Nachtest 2 (N13, Marco 04.11.2026): vorhandene Ergebnisse ausdrücklich nennen. Ob der
        # Termin im Web veröffentlicht ist, weiß die Termin-Datei nicht (die Veröffentlichung
        # lädt eine Kopie hoch) - der Web-Satz gilt deshalb nur „falls“.
        mit_ergebnis = sum(1 for t in betroffen if hat_erfasste_ergebnisse(self.conn, t["id"]))
        ergebnis_satz = (
            f"{mit_ergebnis} von ihnen {'hat' if mit_ergebnis == 1 else 'haben'} schon "
            "gespeicherte Ergebnisse. Die Ergebnisse bleiben beim Teilnehmer, stehen danach "
            "aber ohne Startnummer da.\n\n"
            if mit_ergebnis else ""
        )
        if not _ja_nein(
            self, "Startnummern zurücksetzen",
            f"Die Startnummern {wer} ({anzahl}) werden entfernt. Neu vergeben "
            "kannst du sie danach mit „Fehlende Startnummern vergeben…“.\n\n"
            f"{ergebnis_satz}"
            "Die Reihenfolge im Zeitplan richtet sich nach den Startnummern. Nur falls der "
            "Termin schon im Web veröffentlicht ist: Dort erfasste Ergebnisse werden beim "
            "Zurückholen über die Startnummer zugeordnet - dann nicht mehr umnummerieren.\n\n"
            "Fortfahren?",
        ):
            return
        vorher = {t["id"]: t["startnummer"] for t in betroffen}
        try:
            entfernt = startnummern_zuruecksetzen(self.conn, pruefung)
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        self._rueckgaengig_merken(
            f"Zurücksetzen von {entfernt} Startnummer(n)",
            lambda: f"{startnummern_wiederherstellen(self.conn, vorher)} Startnummer(n) wiederhergestellt.")
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
                    vorher_ohne = _ohne_startnummer_ids(self.conn)
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
                    einleitung = f"{anzahl} Teilnehmer importiert."
                    abschnitte = [
                        (f"{len(fremde)} Teilnehmer in hier nicht angebotenen Prüfungen – bitte die "
                         "Leistungsklasse anpassen („Bearbeiten…“) oder die Prüfung in den "
                         "Veranstaltungsdaten anbieten:",
                         [f"{t['nachname']}, {t['vorname']} – {leistungsklasse_label(t)}" for t in fremde]),
                    ]
                    _letzten_import_zeigen(self, _meldungstext_voll(einleitung, abschnitte))
                    _meldung_mit_listen(self, "Import abgeschlossen", einleitung, abschnitte)
                    if anzahl:
                        _startnummern_nach_import_anbieten(self, self.conn, vorher_ohne)
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
        "Ausdrucke/Export" (dort weiterhin als Sammel-Export für alle Teilnehmer vorhanden)."""
        teilnehmer_id = self._ausgewaehlte_id()
        if teilnehmer_id is None:
            return
        _bewertungsbogen_fuer_teilnehmer(self, self.conn, self._ablageort, self.status_label, teilnehmer_id)

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
            geloescht: list = []  # gesichert, bevor gelöscht wird - auch bei einem Abbruch mittendrin
            try:
                for t in teilnehmer:
                    sicherung = teilnehmer_sichern(self.conn, t["id"])
                    delete_teilnehmer(self.conn, t["id"])
                    if sicherung:
                        geloescht.append(sicherung)
            except sqlite3.Error as exc:
                _db_fehler_anzeigen(self, exc, "Nicht alle Teilnehmer konnten gelöscht werden.")
            if geloescht:
                self._rueckgaengig_merken(
                    f"Löschen von {len(geloescht)} Teilnehmer(n)" if len(geloescht) > 1
                    else f"Löschen von „{geloescht[0]['teilnehmer']['nachname']}“",
                    lambda: self._teilnehmer_zurueckholen(geloescht))
            self.aktualisieren()

    def _rueckgaengig_merken(self, beschreibung: str, aktion) -> None:
        """Merkt die letzte rückgängig zu machende Aktion (eine Ebene, Marco 10.11.2026)."""
        self._rueckgaengig.merken(beschreibung, aktion)

    def _rueckgaengig_ausfuehren(self) -> None:
        eintrag = self._rueckgaengig.entnehmen()
        if eintrag is None:
            return
        beschreibung, aktion = eintrag
        try:
            meldung = aktion()
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc, "Das ließ sich nicht rückgängig machen.")
            return
        self.aktualisieren()
        self.status_label.setText(f"Rückgängig: {beschreibung}. {meldung}".strip())

    def _teilnehmer_zurueckholen(self, sicherungen: list) -> str:
        zahl = sum(1 for s in sicherungen if teilnehmer_wiederherstellen(self.conn, s))
        ohne_nr = [s["teilnehmer"]["nachname"] for s in sicherungen
                   if s["teilnehmer"].get("startnummer") is not None
                   and (get_teilnehmer(self.conn, s["teilnehmer"]["id"]) or {}).get("startnummer") is None]
        hinweis = f" Ohne Startnummer, weil die Nummer inzwischen vergeben ist: {', '.join(ohne_nr)}." if ohne_nr else ""
        return f"{zahl} Teilnehmer wiederhergestellt.{hinweis}"

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
        self.teilnehmer_geaendert.emit()
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
            self._zeile_fuellen(row, t)
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
        self._filter_combo_neu_befuellen(teilnehmer)
        self._filter_anwenden()
        self._startnummern_hinweis_aktualisieren()

    def _zeile_fuellen(self, row: int, t: dict) -> None:
        """Füllt eine Tabellenzeile mit den Daten eines Teilnehmers (Zellen, Bezahlt-Markierung,
        Anmerkungen, Ausgrauen bei „keine Teilnahme“)."""
        werte = [
            str(t["startnummer"] or ""),
            t["nachname"],
            t["vorname"],
            t["rufname_hund"],
            leistungsklasse_label(t),
            t["verein"] or "",
            "bezahlt" if t["bezahlt"] else "",
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
            elif col == 4:
                item = _PruefungSortierbaresItem(wert)  # N5: Reihenfolge des Formulars
            else:
                item = QTableWidgetItem(wert)
            self.tabelle.setItem(row, col, item)
        # Bezahlt-Spalte farblich hervorheben (dezentes Grün, siehe _QSS_TEMPLATE) -
        # nur die Textfarbe, der Zelleninhalt selbst bleibt wie zuvor ("" bei nicht
        # bezahlt), damit bestehende Tests darauf weiter verlassen können. Haken als
        # Symbol statt „✓“ (Marco 01.11.2026, Erscheinungsbild „Beagle“).
        if t["bezahlt"]:
            bezahlt_item = self.tabelle.item(row, 6)
            bezahlt_item.setIcon(symbol("check", "ok"))
            bezahlt_item.setForeground(_farbe("ok"))
            schrift = bezahlt_item.font()
            schrift.setBold(True)
            bezahlt_item.setFont(schrift)
        vollstaendig_item = self._anmerkungen_item(t)
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

    @staticmethod
    def _anmerkungen_item(t: dict) -> QTableWidgetItem:
        """Zelle der Spalte „Anmerkungen“ (Hinweise auf fehlende Angaben)."""
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
        # werden oft erst kurz vor dem Prüfungstag festgelegt - ein oranges Warnzeichen in fast
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
            text = "; ".join(stark) + (f"; {offen_text}" if gegenstand_offen else "")
            vollstaendig_item = QTableWidgetItem(text)
            vollstaendig_item.setIcon(symbol("alert-triangle", "warnung"))
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
        return vollstaendig_item

    def _filter_combo_neu_befuellen(self, teilnehmer: list[dict]) -> None:
        # Filter-Auswahl beim Neuladen nach Möglichkeit beibehalten, statt immer auf
        # "Alle" zurückzuspringen (entspricht ErgebnisTab.aktualisieren).
        bisherige_auswahl = self.filter_combo.currentText()
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItem("Alle")
        # Bewusst aus der eigenen (ungefilterten) Liste statt alle_leistungsklassen(), das
        # nur teilnehmende Teilnehmer berücksichtigt - hier sollen auch Leistungsklassen
        # filterbar bleiben, in denen nur noch "keine Teilnahme"-Teilnehmer stehen.
        self.filter_combo.addItems(sortiere_pruefungen({leistungsklasse_label(t) for t in teilnehmer}))
        index = self.filter_combo.findText(bisherige_auswahl)
        self.filter_combo.setCurrentIndex(index if index >= 0 else 0)
        self.filter_combo.blockSignals(False)
