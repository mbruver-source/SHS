"""Dialoge der Desktop-Oberfläche (Teilnehmer, Startnummern tauschen, Termin-Import,
Zeitplan-Blöcke/Pausen, Bewertungsbögen, Datensicherung, Hilfe, Veranstaltung).

Aus app.py ausgelagert (Codex-Architekturprüfung 27.09.2026); rein interne Umstellung,
Aussehen und Verhalten sind unverändert. Die Abhängigkeiten laufen nur in eine Richtung:
app -> desktop_dialoge -> desktop_gemeinsam, app -> desktop_darstellung (jeweils -> db/
pdf_export); keines dieser Module importiert app.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from db import (
    ALLE_DISZIPLINEN,
    NeuerTeilnehmer,
    dateiname_vorschlagen,
    datum_anzeige,
    init_db,
    leistungsklasse_label,
    liste_termine,
    list_teilnehmer,
    normalisiere_datum,
    termine_ordner,
)
from db_sicherung import (
    eindeutigen_dateinamen_finden,
)
from desktop_gemeinsam import (
    _gegenstand_zeile,
    _GEGENSTAND_ZUORDNUNG_FREI,
    _GESCHLECHT_UNBEKANNT,
    ResponsiveSchriftMixin,
    _startnummer_zeile,
    _zuordnung_oder_none,
)


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
            # Die Vorbelegung setzt auch die gespeicherte Zuordnung von Gegenstand 1 -
            # bei ED danach wieder fest auf die ED-Disziplin stellen.
            self._gegenstand_felder_aktualisieren()

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
        self.geburtsdatum.setPlaceholderText("TT.MM.JJJJ")
        self.verein = QLineEdit()
        self.verband = QLineEdit()
        self.mitgliedsnummer = QLineEdit()
        self.zwingername = QLineEdit()
        self.rufname_hund = QLineEdit()
        self.geschlecht = QComboBox()
        # Codeprüfung 22.09., G4: leerer erster Eintrag, damit neue Teilnehmer ohne
        # Angabe starten statt still auf "Hündin" (siehe _GESCHLECHT_UNBEKANNT).
        self.geschlecht.addItems([_GESCHLECHT_UNBEKANNT, "Hündin", "Rüde"])
        self.schulterhoehe = QSpinBox()
        self.schulterhoehe.setRange(0, 100)
        self.chip_nr = QLineEdit()
        self.rasse = QLineEdit()
        self.wurftag = QLineEdit()
        self.wurftag.setPlaceholderText("TT.MM.JJJJ")
        self.tollwutimpfung_bis = QLineEdit()
        self.tollwutimpfung_bis.setPlaceholderText("TT.MM.JJJJ")
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
        self.disziplin.currentTextChanged.connect(self._gegenstand_felder_aktualisieren)

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
        form_links.addRow("Geburtsdatum (TT.MM.JJJJ)", self.geburtsdatum)
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
        form_rechts.addRow("Wurftag (TT.MM.JJJJ)", self.wurftag)
        form_rechts.addRow("Tollwutimpfung gültig bis (TT.MM.JJJJ)", self.tollwutimpfung_bis)
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
        self.geburtsdatum.setText(datum_anzeige(vorhandener["geburtsdatum"]))
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
        # Codeprüfung 22.09., G4: geschlecht NULL bleibt bewusst auf "–" stehen.
        self.geschlecht.setCurrentText(vorhandener["geschlecht"] or _GESCHLECHT_UNBEKANNT)
        self.schulterhoehe.setValue(vorhandener["schulterhoehe_cm"] or 0)
        self.chip_nr.setText(vorhandener["chip_nr"] or "")
        self.rasse.setText(vorhandener["rasse"] or "")
        self.wurftag.setText(datum_anzeige(vorhandener["wurftag"]))
        self.tollwutimpfung_bis.setText(datum_anzeige(vorhandener["tollwutimpfung_bis"]))
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
        # Altdaten bei ED (Abstimmung 23.09.: ED hat nur Gegenstand 1): Steht der einzige
        # Gegenstand in Feld 2 oder 3, ihn nach Feld 1 holen, statt ihn in einem
        # ausgegrauten Feld zu verstecken.
        if vorhandener["art"] == "ED" and not self.gegenstand_1.text():
            for feld in (self.gegenstand_2, self.gegenstand_3):
                if feld.text():
                    self.gegenstand_1.setText(feld.text())
                    feld.clear()
                    break
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
        self._gegenstand_felder_aktualisieren()

    def _gegenstand_felder_aktualisieren(self, *_args) -> None:
        """Abstimmung mit Marco (23.09.): ED hat nur eine Suchdisziplin und damit
        unabhängig von der Leistungsklasse genau einen Gegenstand. Bei ED ist daher nur
        Gegenstand 1 eingabebereit, sein "gesucht in" folgt fest der gewählten
        ED-Disziplin (automatische Zuordnung); Gegenstand 2/3 sind ausgegraut. Bei DK
        sind alle drei Felder samt Zuordnung frei wählbar."""
        ist_ed = self.art.currentText() == "ED"
        for widget in (
            self.gegenstand_2, self.gegenstand_2_disziplin,
            self.gegenstand_3, self.gegenstand_3_disziplin,
        ):
            widget.setEnabled(not ist_ed)
        self.gegenstand_1_disziplin.setEnabled(not ist_ed)
        if ist_ed:
            self.gegenstand_1_disziplin.setCurrentText(self.disziplin.currentText())
        elif getattr(self, "_gegenstand_1_fest_zugeordnet", False):
            # Wechsel ED -> DK: die nur automatisch gesetzte ED-Zuordnung nicht als
            # scheinbar bewusste DK-Zuordnung stehen lassen, sondern wieder auf "frei".
            self.gegenstand_1_disziplin.setCurrentText(_GEGENSTAND_ZUORDNUNG_FREI)
        self._gegenstand_1_fest_zugeordnet = ist_ed

    def _pruefen_und_akzeptieren(self) -> None:
        if not self.nachname.text().strip() or not self.vorname.text().strip() or not self.rufname_hund.text().strip():
            QMessageBox.warning(self, "Fehlende Angaben", "Nachname, Vorname und Rufname des Hundes sind Pflichtfelder.")
            return
        # Codeprüfung 22.09. (M5): Datumsfelder prüfen, bevor ergebnis() sie umwandelt -
        # TT.MM.JJJJ und JJJJ-MM-TT sind erlaubt, alles andere bleibt im Dialog stehen.
        for bezeichnung, feld in (
            ("Geburtsdatum", self.geburtsdatum), ("Wurftag", self.wurftag),
            ("Tollwutimpfung gültig bis", self.tollwutimpfung_bis),
        ):
            try:
                normalisiere_datum(feld.text())
            except ValueError as fehler:
                QMessageBox.warning(self, "Ungültiges Datum", f"{bezeichnung}: {fehler}")
                feld.setFocus()
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
        # Bei ED greift die Prüfung nicht: dort zählt nur Gegenstand 1 mit fester
        # Zuordnung, Gegenstand 2/3 werden gar nicht gespeichert (Abstimmung 23.09.).
        ist_ed = self.art.currentText() == "ED"
        if ist_ed and (self.gegenstand_2.text().strip() or self.gegenstand_3.text().strip()):
            antwort = QMessageBox.question(
                self, "Nur ein Gegenstand bei ED",
                "Bei einer Einzeldisziplin (ED) gibt es nur einen Gegenstand. Die Einträge "
                "in Gegenstand 2 und 3 werden nicht gespeichert.\n\nTrotzdem speichern?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if antwort != QMessageBox.Yes:
                return
        vergebene_disziplinen = [] if ist_ed else [
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

    def _gegenstaende_ergebnis(self) -> dict:
        if self.art.currentText() == "ED":
            text = self.gegenstand_1.text().strip() or None
            return dict(
                gegenstand_1=text,
                gegenstand_1_disziplin=self.disziplin.currentText() if text else None,
                gegenstand_2=None, gegenstand_2_disziplin=None,
                gegenstand_3=None, gegenstand_3_disziplin=None,
            )
        return dict(
            gegenstand_1=self.gegenstand_1.text().strip() or None,
            gegenstand_2=self.gegenstand_2.text().strip() or None,
            gegenstand_3=self.gegenstand_3.text().strip() or None,
            gegenstand_1_disziplin=_zuordnung_oder_none(self.gegenstand_1_disziplin),
            gegenstand_2_disziplin=_zuordnung_oder_none(self.gegenstand_2_disziplin),
            gegenstand_3_disziplin=_zuordnung_oder_none(self.gegenstand_3_disziplin),
        )

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
            geschlecht=(
                None if self.geschlecht.currentText() == _GESCHLECHT_UNBEKANNT
                else self.geschlecht.currentText()
            ),
            schulterhoehe_cm=self.schulterhoehe.value() or None,
            chip_nr=self.chip_nr.text().strip() or None,
            rasse=self.rasse.text().strip() or None,
            tollwutimpfung_bis=normalisiere_datum(self.tollwutimpfung_bis.text()),
            geburtsdatum=normalisiere_datum(self.geburtsdatum.text()),
            startnummer=None if self.startnummer_unbekannt.isChecked() else self.startnummer.value(),
            # Bei ED nur Gegenstand 1, automatisch der ED-Disziplin zugeordnet (23.09.).
            **self._gegenstaende_ergebnis(),
            bezahlt=self.bezahlt.isChecked(),
            verband=self.verband.text().strip() or None,
            mitgliedsnummer=self.mitgliedsnummer.text().strip() or None,
            wurftag=normalisiere_datum(self.wurftag.text()),
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
                f"{t.verein or '(ohne Verein)'} – {datum_anzeige(t.datum)} ({t.anzahl_teilnehmer} Teilnehmer)"
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


def _wiederherstellungsziele_planen(namen, vorhandene, ordner, aktion_fuer) -> tuple[dict[str, str], int]:
    """Legt für jede Termin-Datei einer Sicherung den Zieldateinamen fest und liefert
    (entscheidungen, anzahl_uebersprungen) für db.sicherung_wiederherstellen().
    `aktion_fuer(name)` wird nur bei einem Namenskonflikt aufgerufen und liefert
    "ueberschreiben", "kopie" oder "ueberspringen" (siehe DatensicherungTab._konflikt_abfragen).

    Codeprüfung 22.09., G5: Die Kopie-Namen werden bewusst erst NACH allen Rückfragen
    vergeben und dabei alle schon eingeplanten Zielnamen (auch die auf sich selbst
    abgebildeten, also neue und zu überschreibende Einträge) als belegt übergeben. Sonst
    konnten zwei ZIP-Einträge auf dieselbe Zieldatei landen - z. B. enthält die Sicherung
    "A.sqlite" (vorhanden, als Kopie -> "A (2).sqlite") UND ein noch nicht vorhandenes
    "A (2).sqlite", und einer überschrieb still den anderen. Die Reihenfolge der Einträge
    im ZIP spielt durch die zweite Runde keine Rolle mehr."""
    entscheidungen: dict[str, str] = {}
    als_kopie: list[str] = []
    uebersprungen = 0
    for name in namen:
        if name not in vorhandene:
            entscheidungen[name] = name
            continue
        aktion = aktion_fuer(name)
        if aktion == "ueberschreiben":
            entscheidungen[name] = name
        elif aktion == "kopie":
            als_kopie.append(name)
        else:  # "ueberspringen"
            uebersprungen += 1
    for name in als_kopie:
        entscheidungen[name] = eindeutigen_dateinamen_finden(
            ordner, name, bereits_vergeben=set(entscheidungen.values())
        )
    return entscheidungen, uebersprungen


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
Pflichtfeldern. Dazu Art (ED/DK), Leistungsklasse, bei ED die Disziplin und die
Suchgegenstände. Die Startnummer wird automatisch vorgeschlagen.</p>
<p><b>Gegenstände:</b> Hinter jedem Gegenstand legst du bei "gesucht in" fest, für welche
Disziplin er gilt – das steuert, wo er auf dem Bewertungsbogen erscheint. Bei ED gibt es in
jeder Leistungsklasse genau einen Gegenstand: nur Gegenstand 1 ist eingabebereit, "gesucht in"
folgt automatisch der ED-Disziplin. Bei DK sind mindestens 1 (LK1), 2 (LK2) bzw. 3 (LK3)
verschiedene Gegenstände nötig. Alle auf "frei" zu lassen ist in Ordnung; ordnest du
Disziplinen zu, sollten alle drei belegt sein (derselbe Gegenstand darf in mehreren Feldern
stehen, jede Disziplin aber nur einmal vorkommen).</p>
<p><b>Spalte "Anmerkungen":</b> Warnungen mit ⚠ (z. B. "Chip-Nr. fehlt", "Gegenstand fehlt",
"Gegenstände unvollständig (Dreikampf)") solltest du vor dem Prüfungstag beheben; kleine
Hinweise ohne ⚠ sind nur Erinnerungen.</p>
<p>"Bezahlt umschalten" setzt den Zahlungsstatus des markierten Teilnehmers, ohne den ganzen
Dialog zu öffnen. "Startnummer tauschen…" tauscht die Nummern zweier Teilnehmer.
"Aus anderem Termin importieren…" übernimmt Stammdaten aus einem früheren Termin (ohne
Startnummer, Gegenstände, Bezahlt-Status und Ergebnis). "Bewertungsbogen (PDF)…" erzeugt den
Bogen nur für den markierten Teilnehmer. Die Filter Art/LK, Start-Nr. und Bezahlt blenden
Zeilen nur aus.</p>

<h3>Reiter "Formular-Import"</h3>
<p>Liest Meldeformulare (PDF, Word, Foto) mit Hilfe eines KI-Assistenten ein: "Prompt
kopieren", Prompt und Formulare an den KI-Assistenten geben, die erzeugte CSV-Datei mit
"CSV importieren…" einlesen. Jede Zeile wird ein neuer Teilnehmer (ohne Startnummer,
Gegenstände und Bezahlt-Status); fehlerhafte Zeilen werden mit Grund aufgelistet und
übersprungen. Achtung Datenschutz: Die Formulare gehen dabei an den gewählten KI-Anbieter.</p>
<p>Zum Ausprobieren gibt es eine Beispieldatei mit 20 erfundenen Teilnehmern auf der
Projektseite: https://mbruver-source.github.io/SHS/beispiel_teilnehmer.csv (danach im Reiter
"Teilnehmer" die Startnummern vergeben).</p>

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
zurückgewiesen. "Disqualifiziert" bzw. "Abbruch" ankreuzen leert und sperrt die Punktefelder.
Beim Schließen des Programms werden ungespeicherte Ergebnisse automatisch gespeichert.</p>

<h3>Reiter "Auswertung"</h3>
<p>Zeigt die berechnete Rangliste je Leistungsklasse mit Wertnote. Filter nach
Art/Leistungsklasse und Startnummer. "Nicht bestanden" wird rot markiert und erhält keine
Platzzahl, zählt aber bei den Startern mit. "Auswertung neu berechnen" aktualisiert die
Anzeige. "Rangliste drucken (PDF)…" speichert die Rangliste als PDF - ist im Filter eine
Art/Leistungsklasse gewählt, nur diese, sonst alle (der Startnummer-Filter wird dabei nicht
berücksichtigt).</p>

<h3>Reiter "Übersicht"</h3>
<p>Teilnehmerzahlen je Art/Leistungsklasse und Disziplin, die Zahl der Abteilungen und die
Anzahl benötigter Richter (1 ED = 1 Einheit, 1 DK = 3 Einheiten, höchstens 36 Einheiten je
Richter). Darunter die benötigten Behältnisse der Behältnisstrecke je LK (ED Behältnisstrecke
+ DK): leere einmal je LK, eines mit Gegenstand je Teilnehmer, in LK3 wahlweise zusätzlich ein
separates Behältnis für die Material-Verleitung je Teilnehmer. Die gleiche Tabelle steht auch
in der Richter-Bedarf-PDF.</p>

<h3>Reiter "Verwaltung"</h3>
<p>"Veranstaltungsdaten bearbeiten…" ändert Verein/Ort/Datum sowie Vereins-Nr.,
Prüfungsnummer, Richter 1-5, Prüfungsleiter und Prüfungsgebühr ED/DK nachträglich –
diese Angaben stehen oft erst kurz vor dem Prüfungstag fest und erscheinen im Kopf der
Statistik-PDF bzw. in der Übersicht für Prüfungsleitung (siehe Reiter "Export").</p>

<h3>Reiter "Export"</h3>
<p>Alle PDF-Ausgaben an einer Stelle: Ergebnisliste, leere Ergebnisliste zum Ausfüllen,
Etiketten, Statistik, Übersicht für Prüfungsleitung, Chipnummernliste, Richter-Bedarf,
Zeitplan sowie
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

<h3>Aussehen (Menü "Ansicht")</h3>
<p>Unter "Hintergrund" wählst du das Design: Hell (Standard), Warm / Sand, Dunkel oder Hoher
Kontrast. Unter "Akzentfarbe" legst du die Farbe der Haupt-Schaltflächen und Markierungen fest
(Blau, Grün, Violett). Beides lässt sich frei kombinieren, wirkt sofort und wird gespeichert;
noch nicht gespeicherte Ergebnisse bleiben dabei erhalten. Im Design Dunkel bleibt das
Windows-Fenster zum Öffnen/Speichern von Dateien hell.</p>

<h3>Ausführliches Handbuch</h3>
<p>Ein ausführliches Benutzerhandbuch mit Screenshots (auch als PDF zum Ausdrucken) steht auf
der Projektseite bei GitHub (github.com/mbruver-source/SHS, Datei docs/HANDBUCH.md). Dort
kannst du über "Issues" auch Fehler melden oder Wünsche äußern.</p>
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
        self.datum = QLineEdit(datum_anzeige(vorbelegung.get("datum")))
        self.datum.setPlaceholderText("TT.MM.JJJJ")
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
        form.addRow("Datum* (TT.MM.JJJJ)", self.datum)
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

    def datum_iso(self) -> str:
        """Eingegebenes Datum in Speicherform JJJJ-MM-TT (bereits in
        _pruefen_und_akzeptieren geprüft, siehe db.normalisiere_datum)."""
        return normalisiere_datum(self.datum.text()) or ""

    def _pfad_manuell_markieren(self, _text: str) -> None:
        self._pfad_manuell_geaendert = True

    def _pfad_vorschlagen(self) -> None:
        if self._pfad_manuell_geaendert:
            return
        # Solange das Datum (noch) nicht lesbar ist, z. B. mitten in der Eingabe, den Text
        # unverändert verwenden - sobald es passt, landet JJJJ-MM-TT im Dateinamen.
        try:
            datum = normalisiere_datum(self.datum.text()) or ""
        except ValueError:
            datum = self.datum.text().strip()
        name = dateiname_vorschlagen(self.verein.text().strip(), datum)
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
        try:
            normalisiere_datum(self.datum.text())
        except ValueError as fehler:
            QMessageBox.warning(self, "Ungültiges Datum", f"Datum: {fehler}")
            self.datum.setFocus()
            return
        if not self._bearbeiten and not self.pfad_feld.text().strip():
            QMessageBox.warning(self, "Angaben unvollständig", "Bitte einen Speicherort angeben.")
            return
        self.accept()
