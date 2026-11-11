"""
Teilnehmer-Dialog und Startnummern tauschen.

Aus desktop_dialoge.py ausgelagert (11.11.2026), Code unverändert; desktop_dialoge.py bleibt als
Fassade. Bewusst KEIN `import app` (siehe desktop_programm.py).
"""

from __future__ import annotations
import datetime
import re
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from db import (
    ALLE_DISZIPLINEN,
    ALLE_PRUEFUNGEN,
    NeuerTeilnehmer,
    datum_anzeige,
    datum_oder_none,
    normalisiere_datum,
    pruefung_nach_kuerzel,
    pruefungs_kuerzel,
)
from desktop_darstellung import _farbe
from desktop_gemeinsam import zugaengliche_namen_setzen
from desktop_gemeinsam import (
    _ja_nein,
    _gegenstand_zeile,
    _GEGENSTAND_ZUORDNUNG_FREI,
    _GESCHLECHT_UNBEKANNT,
    ResponsiveSchriftMixin,
    _startnummer_zeile,
    _zuordnung_oder_none,
)
from desktop_dialoge_basis import (
    _groesse_auf_bildschirm_begrenzen,
    _scrollflaeche,
    _speichern_vor_dem_schliessen,
)


# UX-Test 02.10.2026, U3 (Rubrik ux_test_2026_10): Startgröße der Teilnehmer-Maske und
# Mindestbreite ihrer Textfelder links.
_TEILNEHMER_DIALOG_GROESSE = (1040, 720)


_MINDESTBREITE_TEXTFELD = 170


#: UX-Test 2026-11, T5: letzter Eintrag der Auswahl „Prüfung“ - blendet Art/LK/Disziplin ein.
_ANDERE_PRUEFUNG = "andere Prüfung …"


# UX-Test 2026-11, T6: Trennzeichen, die bei ED auf mehrere Gegenstände in einem Feld deuten.
# Klammerzusätze wie „Ball (rot, klein)“ zählen nicht (_KLAMMERZUSATZ wird vorher entfernt).
_MEHRERE_GEGENSTAENDE = re.compile(r"[,;/+&]|\s(und|oder|sowie|u\.)\s", re.IGNORECASE)


_KLAMMERZUSATZ = re.compile(r"\([^)]*\)")


class TeilnehmerDialog(ResponsiveSchriftMixin, QDialog):
    """Formular zum Erfassen und Bearbeiten eines Teilnehmers."""

    def __init__(
        self, parent=None, vorhandener: dict | None = None, vergebene_nummern: set[int] | None = None,
        namen_je_startnummer: dict[int, str] | None = None,
        bereiche: dict[str, tuple[int, int]] | None = None,
        speichern=None,
        angebotene: set[str] | None = None,
        stichtag: str | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Teilnehmer bearbeiten" if vorhandener else "Teilnehmer erfassen")
        # Kürzel der im Termin angebotenen Prüfungen (leer/None: keine Rückfrage), Teil 2 Nr. 13.
        self._angebotene = angebotene or set()
        # Prüfungsdatum des Termins (JJJJ-MM-TT) als Bezug für die Zukunftsprüfung von
        # Geburtsdatum/Wurftag; fehlt oder ist es nicht lesbar, gilt das heutige Datum.
        self._stichtag = stichtag
        # Rückruf speichern(dialog), siehe _speichern_vor_dem_schliessen.
        self._speichern = speichern
        # Bereits vergebene Startnummern (beim Bearbeiten ohne die eigene) - für
        # die Dubletten-Prüfung beim Speichern.
        self._vergebene_nummern = vergebene_nummern or set()
        # Nur für die Warnmeldung bei doppelter Startnummer: wer hat sie schon (Name), damit
        # der Hinweis konkret wird statt nur "ist bereits vergeben" zu sagen.
        self._namen_je_startnummer = namen_je_startnummer or {}
        # UX-Test 02.10.2026, U1: Startnummern-Bereiche je Prüfung (db.startnummer_bereiche)
        # für den Vorschlag beim Entfernen des Hakens "steht noch nicht fest".
        self._bereiche = bereiche or {}
        # Vorschlag nur für Teilnehmer ohne eigene Nummer - eine vorhandene Nummer wird beim
        # Hin- und Herschalten des Hakens nicht durch einen Vorschlag ersetzt.
        self._ohne_eigene_nummer = vorhandener is None or vorhandener.get("startnummer") is None
        self._vorschlag_aktiv = False  # erst nach dem Aufbau, siehe Ende von __init__
        self._letzter_vorschlag: int | None = None

        # Zeilen „Gegenstand 2/3“ (R5) - vor dem Layout-Aufbau noch leer; die Auswahllisten
        # rufen _gegenstand_felder_aktualisieren schon in _felder_erstellen auf.
        self._gegenstand_zeilen: list[QWidget] = []
        self._felder_erstellen()
        self._layout_aufbauen()

        self._art_geaendert(self.art.currentText())
        if vorhandener:
            self._vorbelegung_uebernehmen(vorhandener)
            # Die Vorbelegung setzt auch die gespeicherte Zuordnung von Gegenstand 1 -
            # bei ED danach wieder fest auf die ED-Disziplin stellen.
            self._gegenstand_felder_aktualisieren()
        else:
            # UX-Test 02.10.2026, U1 (Marco): kein Startnummer-Vorschlag bei der Neuanlage -
            # Nummern werden gesammelt ("Fehlende Startnummern vergeben…") oder bewusst
            # einzeln vergeben.
            self.startnummer_unbekannt.setChecked(True)
            # UX-Test 03.11.2026, X12 (Marco: vorbelegen + markieren): mit der ersten im
            # Termin angebotenen Prüfung beginnen statt immer mit ED/1/Trümmerfeld.
            erste = next((p for p in ALLE_PRUEFUNGEN if p.kuerzel in self._angebotene), None)
            if erste is not None:
                self.art.setCurrentText(erste.art)
                self.stufe.setCurrentText(str(erste.stufe))
                if erste.disziplin:
                    self.disziplin.setCurrentText(erste.disziplin)

        # Stand beim Öffnen (X11: Bereichs-Rückfrage nur nach einer Änderung).
        self._gespeicherte_nummer_und_pruefung = (
            (vorhandener.get("startnummer"), self._gewaehlte_pruefung()) if vorhandener else None
        )
        self._gespeicherter_gegenstand_1 = self.gegenstand_1.text().strip() if vorhandener else None
        self._pruefung_auswahl_fuellen()
        for auswahl in (self.art, self.stufe, self.disziplin):
            auswahl.currentTextChanged.connect(self._pruefung_hinweis_aktualisieren)
            auswahl.currentTextChanged.connect(self._pruefung_auswahl_nachfuehren)
        self._pruefung_hinweis_aktualisieren()
        self._halter_sichtbarkeit_aktualisieren(self.halter_weicht_ab.isChecked())
        self._startnummer_verfuegbarkeit_aktualisieren(self.startnummer_unbekannt.isChecked())
        self._vorschlag_aktiv = True
        # Ändert sich danach die Prüfung, den (noch unveränderten) Vorschlag mitziehen.
        for auswahl in (self.art, self.stufe, self.disziplin):
            auswahl.currentTextChanged.connect(self._vorschlag_nachfuehren)
        self._schriftgroesse_anwenden()
        self.nachname.setFocus()  # Teil 2 Nr. 6

    def _felder_erstellen(self) -> None:
        """Legt alle Eingabe-Widgets als Attribute an (noch ohne Layout/Vorbelegung -
        siehe _layout_aufbauen/_vorbelegung_uebernehmen)."""
        self._stammfelder_erstellen()
        self._pruefungsfelder_erstellen()
        self._halterfelder_erstellen()

    def _stammfelder_erstellen(self) -> None:
        """Hundeführer, Hund, Anschrift, Kontakt und Startnummer."""
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
        # Nutzerwunsch (20.09., Anmerkung zum Programm): "Vergabe der Startnummern als
        # Pflichtfeld finde ich hier noch nicht so gut, ich weiß ggf. nicht was alles an
        # Meldungen kommt" - die Startnummer kann jetzt offen gelassen werden (startnummer
        # bleibt dann NULL, wie von db.py ohnehin schon unterstützt) und später nachgetragen
        # werden.
        self.startnummer_unbekannt = QCheckBox("Startnummer steht noch nicht fest")
        self.startnummer_unbekannt.toggled.connect(self._startnummer_verfuegbarkeit_aktualisieren)

    def _pruefungsfelder_erstellen(self) -> None:
        """Prüfung, Art/Leistungsklasse/Disziplin, Gegenstände und Bezahlt."""
        # UX-Test 2026-11, T5 (Marco 04.11.2026, ersetzt R2): eine Auswahl „Prüfung“ mit den im
        # Termin angebotenen Prüfungen in der Schreibweise des Anmeldeformulars. Art/LK/Disziplin
        # bleiben die Grundlage; sichtbar nur über „andere Prüfung …“ bzw. ohne Angebot.
        self.pruefung_auswahl = QComboBox()

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
            # Rückmeldung 10.11.2026: eine schon vergebene Disziplin ist bei den anderen
            # Gegenständen ausgegraut und nicht wählbar.
            zuordnung.currentTextChanged.connect(self._vergebene_disziplinen_sperren)

        # UX-Test 03.11.2026, X12: Klartext, welche Prüfung Art/LK/Disziplin ergeben und ob der
        # Termin sie anbietet; X4: warum Gegenstand 2/3 bei ED fehlen (seit R5 ausgeblendet).
        self.pruefung_hinweis = QLabel("")
        self.pruefung_hinweis.setTextFormat(Qt.PlainText)
        self.pruefung_hinweis.setWordWrap(True)
        self.gegenstand_hinweis = QLabel("Bei einer Einzeldisziplin gibt es nur einen Gegenstand.")
        self.gegenstand_hinweis.setTextFormat(Qt.PlainText)
        self.gegenstand_hinweis.setWordWrap(True)

        self.bezahlt = QCheckBox("Prüfungsgebühr bezahlt")

    def _halterfelder_erstellen(self) -> None:
        """Felder des abweichenden Halters."""
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
        # Namen für Bildschirmleser: diese Felder stehen in Zeilen ohne eigenes Beschriftungsfeld
        # (Startnummer neben der Checkbox, Gegenstand neben der Zuordnung).
        zugaengliche_namen_setzen(self, {
            "startnummer": "Startnummer",
            "gegenstand_1": "Gegenstand 1", "gegenstand_1_disziplin": "Gegenstand 1 gesucht in Disziplin",
            "gegenstand_2": "Gegenstand 2", "gegenstand_2_disziplin": "Gegenstand 2 gesucht in Disziplin",
            "gegenstand_3": "Gegenstand 3", "gegenstand_3_disziplin": "Gegenstand 3 gesucht in Disziplin",
        })
        # Zwei Spalten nebeneinander statt einer langen Liste untereinander - bei allen
        # Feldern (inkl. der neuen Verwaltungs-/Kontaktfelder) ging das Fenster sonst in
        # der Höhe über den Bildschirm hinaus, ohne dass sich der Dialog scrollen ließ.
        # Links: Angaben zu Hundeführer/Verein/Anschrift/Kontakt (der/die Meldende).
        # Rechts: Angaben zu Hund und Prüfungsmeldung. Siehe auch Mockup-Absprache mit
        # Marco. Ein möglicher abweichender Halter bekommt einen eigenen, dritten Block
        # darunter (siehe _gruppe_halter_aufbauen) statt hier mit hineinzumischen.
        gruppe_links = self._gruppe_hundefuehrer()
        gruppe_rechts = self._gruppe_hund_pruefung()

        # CI-Fund (21.09., echter Nutzertest): OHNE Stretch-Faktoren bekommt die linke
        # Spalte (weniger/kürzere Pflichtfelder) von QHBoxLayout viel zu wenig Platz
        # zugeteilt, sobald die rechte Spalte (mehr/breitere Felder wie das Datumsfeld
        # "Tollwutimpfung gültig bis") ihren natürlichen Platzbedarf einfordert - die
        # Eingabefelder links liefen dadurch sichtbar ab ("uver" statt "Bruver"). Mit
        # gleichem Stretch-Faktor (1:1) bekommen beide Spalten unabhängig von ihrem
        # jeweiligen Inhalt die Hälfte der verfügbaren Breite.
        # UX-Test 02.10.2026, U3: trotz 1:1-Aufteilung blieben die linken Felder bei der
        # alten Startgröße nur ~45 px breit ("uster" statt "Muster"), weil die rechte
        # Spalte ihren Mindestplatz zuerst bekommt. Mindestbreite für die Textfelder links -
        # notfalls scrollt der Dialog waagerecht, statt Eingaben abzuschneiden.
        for feld in gruppe_links.findChildren(QLineEdit):
            feld.setMinimumWidth(_MINDESTBREITE_TEXTFELD)
        spalten_zeile = QHBoxLayout()
        spalten_zeile.addWidget(gruppe_links, 1)
        spalten_zeile.addWidget(gruppe_rechts, 1)

        self._gruppe_halter_aufbauen()

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

        inhalt_scroll = _scrollflaeche(inhalt_container)

        layout = QVBoxLayout(self)
        layout.addWidget(inhalt_scroll, 1)
        layout.addWidget(buttons)

        # Bewusst gewählte Startgröße statt automatischer (zu hoher) Größe durch die vielen
        # Felder, bei großer Schrift mindestens so breit wie das Formular (Nachtest 2, N2) -
        # passt dadurch auch auf kleinere Bildschirme (der Inhalt scrollt bei Bedarf, siehe
        # oben, statt abgeschnitten zu werden). Der Dialog bleibt frei in der Größe änderbar
        # UND auch maximierbar (CI-Fund 21.09.: QDialog zeigt standardmäßig keinen
        # Maximieren-Button, obwohl der Nutzer bei vielen Feldern/aufgeklapptem Halter-Block
        # mehr Platz braucht als die Startgröße bietet).
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
        # UX-Test 02.10.2026, U3: größere Startgröße (vorher 780x640), begrenzt auf den
        # verfügbaren Bildschirm, damit OK/Abbrechen auch auf kleinen Laptops sichtbar bleiben.
        _groesse_auf_bildschirm_begrenzen(self, *_TEILNEHMER_DIALOG_GROESSE, inhalt=inhalt_container)

    def _gruppe_hundefuehrer(self) -> QGroupBox:
        """Linke Spalte: Hundeführer und Kontakt."""
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
        return gruppe_links

    def _gruppe_hund_pruefung(self) -> QGroupBox:
        """Rechte Spalte: Hund und Prüfungsmeldung (setzt _gegenstand_zeilen und _form_rechts)."""
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
        form_rechts.addRow("Prüfung*", self.pruefung_auswahl)
        form_rechts.addRow("Art*", self.art)
        form_rechts.addRow("Leistungsklasse*", self.stufe)
        form_rechts.addRow("Disziplin (nur bei ED)", self.disziplin)
        form_rechts.addRow("", self.pruefung_hinweis)
        form_rechts.addRow("Gegenstand 1", _gegenstand_zeile(self.gegenstand_1, self.gegenstand_1_disziplin))
        form_rechts.addRow("", self.gegenstand_hinweis)
        # Marcos Entscheidung R5 (UX-Test 03.11.2026, X4): bei ED ausgeblendet statt nur gesperrt.
        self._gegenstand_zeilen = [
            _gegenstand_zeile(self.gegenstand_2, self.gegenstand_2_disziplin),
            _gegenstand_zeile(self.gegenstand_3, self.gegenstand_3_disziplin),
        ]
        form_rechts.addRow("Gegenstand 2", self._gegenstand_zeilen[0])
        form_rechts.addRow("Gegenstand 3", self._gegenstand_zeilen[1])
        self._form_rechts = form_rechts
        form_rechts.addRow("", self.bezahlt)

        gruppe_rechts = QGroupBox("Hund && Prüfung")
        gruppe_rechts.setLayout(form_rechts)
        return gruppe_rechts

    def _gruppe_halter_aufbauen(self) -> None:
        """Dritter Block: abweichender Halter (setzt gruppe_halter, anfangs ausgeblendet)."""
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
        self.gruppe_halter.setVisible(False)  # nur bei Bedarf eingeblendet, siehe _layout_aufbauen

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
        # (seit R5 ausgeblendeten) Feld zu verstecken.
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
        if not unbekannt and self._vorschlag_aktiv and self._ohne_eigene_nummer:
            self._letzter_vorschlag = self._startnummer_vorschlag()
            self.startnummer.setValue(self._letzter_vorschlag)

    def _vorschlag_nachfuehren(self, _text: str = "") -> None:
        """Neue Prüfung gewählt: Steht im Feld noch der zuletzt vorgeschlagene Wert (also
        nicht von Hand geändert), den Vorschlag für die neue Prüfung übernehmen."""
        if (
            not self.startnummer_unbekannt.isChecked() and self._ohne_eigene_nummer
            and self._letzter_vorschlag is not None and self.startnummer.value() == self._letzter_vorschlag
        ):
            self._letzter_vorschlag = self._startnummer_vorschlag()
            self.startnummer.setValue(self._letzter_vorschlag)

    def _startnummer_vorschlag(self) -> int:
        """Kleinste freie Nummer im Bereich der gewählten Prüfung (UX-Test U1, statt
        immer "1"); ohne Bereich bzw. bei vollem Bereich die kleinste freie insgesamt."""
        bereich = self._bereiche.get(self._gewaehlte_pruefung())
        if bereich is not None:
            frei = next((n for n in range(bereich[0], bereich[1] + 1) if n not in self._vergebene_nummern), None)
            if frei is not None:
                return frei
        n = 1
        while n in self._vergebene_nummern:
            n += 1
        return n

    def _art_geaendert(self, art: str) -> None:
        # Disziplin ist nur bei Einzeldisziplin (ED) relevant/erlaubt
        self.disziplin.setEnabled(art == "ED")
        self._gegenstand_felder_aktualisieren()

    def _vergebene_disziplinen_sperren(self, *_args) -> None:
        """Eine Disziplin, die bei einem Gegenstand gewählt ist, ist in den Auswahlen der
        anderen beiden Gegenstände ausgegraut und nicht wählbar ("frei" bleibt immer
        wählbar). Bei ED (nur ein Gegenstand, feste Zuordnung) gibt es nichts zu sperren.
        Die Prüfung "doppelt vergeben" beim Speichern bleibt als Sicherung bestehen."""
        combos = (self.gegenstand_1_disziplin, self.gegenstand_2_disziplin, self.gegenstand_3_disziplin)
        ist_ed = self.art.currentText() == "ED"
        for combo in combos:
            vergeben = set() if ist_ed else {
                andere.currentText() for andere in combos
                if andere is not combo and andere.currentText() != _GEGENSTAND_ZUORDNUNG_FREI
            }
            modell = combo.model()
            gesperrt_farbe = QBrush(_farbe("TEXT_DISABLED"))
            kursiv = QFont(combo.font())
            kursiv.setItalic(True)
            for index in range(combo.count()):
                item = modell.item(index)
                if item is None:
                    continue
                frei = combo.itemText(index) not in vergeben
                item.setEnabled(frei)
                # Mit dem Stylesheet zeichnet Qt gesperrte Einträge der Auswahlliste nicht
                # von selbst abgesetzt (Marco 10.11.2026): Farbe, Kursivschrift und Hinweis.
                if frei:
                    item.setData(None, Qt.ForegroundRole)
                    item.setData(None, Qt.FontRole)
                    item.setToolTip("")
                else:
                    item.setForeground(gesperrt_farbe)
                    item.setFont(kursiv)
                    item.setToolTip("Schon bei einem anderen Gegenstand gewählt")

    def _gegenstand_felder_aktualisieren(self, *_args) -> None:
        """Abstimmung mit Marco (23.09.): ED hat nur eine Suchdisziplin und damit
        unabhängig von der Leistungsklasse genau einen Gegenstand. Bei ED ist daher nur
        Gegenstand 1 eingabebereit, sein "gesucht in" folgt fest der gewählten
        ED-Disziplin (automatische Zuordnung); Gegenstand 2/3 sind ausgeblendet (R5). Bei DK
        sind alle drei Felder samt Zuordnung frei wählbar."""
        ist_ed = self.art.currentText() == "ED"
        for widget in (
            self.gegenstand_2, self.gegenstand_2_disziplin,
            self.gegenstand_3, self.gegenstand_3_disziplin,
        ):
            widget.setEnabled(not ist_ed)
            # UX-Test 03.11.2026, X4: gesperrt ohne Erklärung - jetzt mit Grund.
            widget.setToolTip("Bei einer Einzeldisziplin gibt es nur einen Gegenstand." if ist_ed else "")
        self.gegenstand_hinweis.setVisible(ist_ed)
        # R5: Zeilen „Gegenstand 2/3“ samt Beschriftung bei ED ausblenden (vor dem Layout-Aufbau
        # gibt es sie noch nicht).
        for zeile in self._gegenstand_zeilen:
            self._form_rechts.setRowVisible(zeile, not ist_ed)
        self.gegenstand_1_disziplin.setEnabled(not ist_ed)
        if ist_ed:
            self.gegenstand_1_disziplin.setCurrentText(self.disziplin.currentText())
        elif getattr(self, "_gegenstand_1_fest_zugeordnet", False):
            # Wechsel ED -> DK: die nur automatisch gesetzte ED-Zuordnung nicht als
            # scheinbar bewusste DK-Zuordnung stehen lassen, sondern wieder auf "frei".
            self.gegenstand_1_disziplin.setCurrentText(_GEGENSTAND_ZUORDNUNG_FREI)
        self._gegenstand_1_fest_zugeordnet = ist_ed
        self._vergebene_disziplinen_sperren()

    def _pruefung_auswahl_fuellen(self) -> None:
        """T5: angebotene Prüfungen plus „andere Prüfung …“; ohne Angebot im Termin entfällt die
        Auswahl, und Art/LK/Disziplin stehen wie bisher da."""
        for p in ALLE_PRUEFUNGEN:
            if p.kuerzel in self._angebotene:
                self.pruefung_auswahl.addItem(p.bezeichnung, p.kuerzel)
        self.pruefung_auswahl.addItem(_ANDERE_PRUEFUNG, None)
        self._form_rechts.setRowVisible(self.pruefung_auswahl, bool(self._angebotene))
        self._pruefung_auswahl_nachfuehren()
        # Beim Bearbeiten einer nicht angebotenen Prüfung steht gleich „andere Prüfung …“ da.
        self._pruefung_details_zeigen(not self._angebotene or self.pruefung_auswahl.currentData() is None)
        self.pruefung_auswahl.currentIndexChanged.connect(self._pruefung_auswahl_geaendert)

    def _pruefung_details_zeigen(self, sichtbar: bool) -> None:
        # Die Hinweiszeile nur zusammen mit Art/LK/Disziplin - sonst wiederholte sie die
        # Auswahl darüber (Verifikation B8).
        for feld in (self.art, self.stufe, self.disziplin, self.pruefung_hinweis):
            self._form_rechts.setRowVisible(feld, sichtbar)

    def _pruefung_auswahl_geaendert(self, _index: int) -> None:
        kuerzel = self.pruefung_auswahl.currentData()
        pruefung = pruefung_nach_kuerzel(kuerzel) if kuerzel else None
        if pruefung is None:  # „andere Prüfung …“
            self._pruefung_details_zeigen(True)
            return
        self.art.setCurrentText(pruefung.art)
        self.stufe.setCurrentText(str(pruefung.stufe))
        if pruefung.disziplin:
            self.disziplin.setCurrentText(pruefung.disziplin)
        self._pruefung_details_zeigen(False)

    def _pruefung_auswahl_nachfuehren(self, *_args) -> None:
        """Art/LK/Disziplin geändert (auch von außen, z. B. Vorbelegung): die passende
        angebotene Prüfung bzw. „andere Prüfung …“ zeigen, ohne die Felder umzuschalten."""
        index = self.pruefung_auswahl.findData(self._gewaehlte_pruefung())
        if index < 0:
            index = self.pruefung_auswahl.count() - 1
            self._pruefung_details_zeigen(True)  # nicht angeboten: Felder sichtbar lassen
        if index != self.pruefung_auswahl.currentIndex():
            self.pruefung_auswahl.blockSignals(True)
            self.pruefung_auswahl.setCurrentIndex(index)
            self.pruefung_auswahl.blockSignals(False)

    def _gewaehlte_pruefung(self) -> str:
        art = self.art.currentText()
        return pruefungs_kuerzel(art, int(self.stufe.currentText()), self.disziplin.currentText() if art == "ED" else None)

    def _pruefung_hinweis_aktualisieren(self, *_args) -> None:
        """UX-Test 03.11.2026, X12: zeigt die gewählte Prüfung im Klartext und ob der Termin
        sie anbietet (ohne hinterlegtes Angebot nur den Namen)."""
        kuerzel = self._gewaehlte_pruefung()
        pruefung = pruefung_nach_kuerzel(kuerzel)
        name = pruefung.bezeichnung if pruefung else kuerzel
        if not self._angebotene:
            text, farbe = f"Prüfung: {name}", "gedaempft"
        elif kuerzel in self._angebotene:
            text, farbe = f"Prüfung: {name} – wird angeboten", "ok"
        else:
            text, farbe = f"Prüfung: {name} – in diesem Termin NICHT angeboten", "fehler"
        self.pruefung_hinweis.setText(text)
        self.pruefung_hinweis.setStyleSheet(f"color: {_farbe(farbe).name()};")

    # Die Prüfungen laufen der Reihe nach; jede liefert True, wenn der Dialog weitermachen
    # darf, und False, wenn sie ihn mit einer Meldung/Rückfrage offen gehalten hat.

    def _pflichtfelder_pruefen(self) -> bool:
        pflicht = ((self.nachname, "Nachname"), (self.vorname, "Vorname"), (self.rufname_hund, "Rufname Hund"))
        leer = [(feld, name) for feld, name in pflicht if not feld.text().strip()]
        if not leer:
            return True
        # UX-Test 03.11.2026, X15: nur die fehlenden Felder nennen.
        namen = [name for _feld, name in leer]
        text = (f"Bitte noch „{namen[0]}“ ausfüllen." if len(namen) == 1
                else "Bitte noch ausfüllen: " + ", ".join(f"„{n}“" for n in namen) + ".")
        QMessageBox.warning(self, "Fehlende Angaben", text)
        leer[0][0].setFocus()
        return False

    def _datumsfelder_pruefen(self) -> bool:
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
                return False
        return True

    def _zukunftsdaten_pruefen(self) -> bool:
        # Desktop-Prüfung 14.10.2026 (Teil 2 Nr. 12): Tippfehler wie 2085 statt 2005 ergäben
        # ein negatives Alter (und zählten in der Statistik als jugendlich) - Rückfrage.
        pruefungstag = datum_oder_none(self._stichtag)
        grenze = pruefungstag.isoformat() if pruefungstag else datetime.date.today().isoformat()
        bezug = "nach dem Prüfungsdatum" if pruefungstag else "in der Zukunft"
        for bezeichnung, feld in (("Geburtsdatum", self.geburtsdatum), ("Wurftag", self.wurftag)):
            wert = normalisiere_datum(feld.text())
            if wert and wert > grenze:
                if not _ja_nein(
                    self, "Datum in der Zukunft",
                    f"{bezeichnung} {datum_anzeige(wert)} liegt {bezug}. Trotzdem speichern?",
                ):
                    feld.setFocus()
                    return False
        return True

    def _startnummer_frei_pruefen(self) -> bool:
        if self.startnummer_unbekannt.isChecked() or self.startnummer.value() not in self._vergebene_nummern:
            return True
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
        return False

    def _pruefung_angeboten_pruefen(self, kuerzel: str, name: str) -> bool:
        # Teil 2 Nr. 13 (Marcos Entscheidung): nicht angebotene Prüfung nur nach Rückfrage.
        if not self._angebotene or kuerzel in self._angebotene:
            return True
        if _ja_nein(
            self, "Prüfung nicht angeboten",
            f"„{name}“ wird in diesem Termin nicht angeboten (Veranstaltungsdaten). Trotzdem speichern?",
        ):
            return True
        self.stufe.setFocus()
        return False

    def _startnummernbereich_pruefen(self, kuerzel: str, name: str) -> bool:
        # UX-Test 03.11.2026, X11: Nummer außerhalb des Bereichs der gewählten Prüfung nur nach
        # Rückfrage (Hinweis, keine Sperre - Bereiche sind eine Ordnungshilfe). Beim Bearbeiten
        # nur, wenn sich Nummer oder Prüfung geändert haben - sonst käme sie bei jeder
        # Adressänderung wieder (Verifikation A3, Befund 5).
        bereich = self._bereiche.get(kuerzel)
        nummer = None if self.startnummer_unbekannt.isChecked() else self.startnummer.value()
        geaendert = (nummer, kuerzel) != self._gespeicherte_nummer_und_pruefung
        if nummer is None or bereich is None or not geaendert or bereich[0] <= nummer <= bereich[1]:
            return True
        if _ja_nein(
            self, "Startnummer außerhalb des Bereichs",
            f"Die Startnummer {nummer} liegt außerhalb des Bereichs {bereich[0]}–{bereich[1]} "
            f"für „{name}“. Trotzdem speichern?",
        ):
            return True
        self.startnummer.setFocus()
        return False

    def _ed_gegenstaende_pruefen(self, kuerzel: str) -> bool:
        """Bei ED: verworfene Gegenstände 2/3 und mehrere Gegenstände in Feld 1 nur nach
        Rückfrage (Vorgabe „Nein“)."""
        if self.art.currentText() != "ED":
            return True
        if self.gegenstand_2.text().strip() or self.gegenstand_3.text().strip():
            # Seit R5 sind die Felder bei ED ausgeblendet - die verworfenen Texte deshalb
            # nennen (Verifikation A3b/A5b, Befund 3).
            verworfen = "\n".join(
                f"Gegenstand {nummer}: {feld.text().strip()}"
                for nummer, feld in ((2, self.gegenstand_2), (3, self.gegenstand_3)) if feld.text().strip()
            )
            if not _ja_nein(
                self, "Nur ein Gegenstand bei ED",
                "Bei einer Einzeldisziplin (ED) gibt es nur einen Gegenstand. Diese Einträge "
                f"werden nicht gespeichert:\n\n{verworfen}\n\nTrotzdem speichern?",
            ):
                return False
        # UX-Test 2026-11, T6: „Schlüsselbund, Socke“ in Gegenstand 1 wurde bei ED ohne Nachfrage
        # angenommen. Rückfrage nur nach einer Änderung (wie X11), Vorgabe Nein.
        # Auch nach einem Wechsel der Prüfung (z. B. DK → ED), nicht nur nach geändertem Text.
        gegenstand = self.gegenstand_1.text().strip()
        gespeichert = (self._gespeicherter_gegenstand_1,
                       self._gespeicherte_nummer_und_pruefung and self._gespeicherte_nummer_und_pruefung[1])
        if ((gegenstand, kuerzel) != gespeichert
                and _MEHRERE_GEGENSTAENDE.search(_KLAMMERZUSATZ.sub("", gegenstand))):
            if not _ja_nein(
                self, "Mehrere Gegenstände bei ED?",
                f"„{gegenstand}“ sieht nach mehreren Gegenständen aus. Bei einer Einzeldisziplin "
                # R-B16 (Marco 05.11.2026): sagen, was mit dem zweiten Gegenstand geschieht.
                "(ED) gibt es nur einen Gegenstand – einen weiteren bitte mit dem Teilnehmer "
                "klären.\n\nTrotzdem so speichern?",
            ):
                self.gegenstand_1.setFocus()
                return False
        return True

    def _gegenstand_zuordnung_pruefen(self) -> bool:
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
        if self.art.currentText() == "ED":
            return True
        # Teil 2 Nr. 4: nur Gegenstände mit Text zählen - wie in db.gegenstand_fuer_disziplin.
        vergebene_disziplinen = [
            zuordnung.currentText() for text_feld, zuordnung in (
                (self.gegenstand_1, self.gegenstand_1_disziplin),
                (self.gegenstand_2, self.gegenstand_2_disziplin),
                (self.gegenstand_3, self.gegenstand_3_disziplin),
            )
            if text_feld.text().strip() and zuordnung.currentText() != _GEGENSTAND_ZUORDNUNG_FREI
        ]
        doppelt_vergeben = sorted({d for d in vergebene_disziplinen if vergebene_disziplinen.count(d) > 1})
        if not doppelt_vergeben:
            return True
        QMessageBox.warning(
            self, "Gegenstand-Zuordnung doppelt vergeben",
            "Zwei der drei Gegenstände sind derselben Disziplin zugeordnet: "
            f"{', '.join(doppelt_vergeben)}.\n\n"
            "Jede Disziplin darf nur einem der drei Gegenstand-Felder zugeordnet werden. "
            "Soll derselbe Gegenstand in mehreren Disziplinen gesucht werden, bitte den "
            "gleichen Text in mehrere Gegenstand-Felder eintragen und dort jeweils eine "
            "andere Disziplin zuordnen.",
        )
        return False

    def _pruefen_und_akzeptieren(self) -> None:
        if not (self._pflichtfelder_pruefen() and self._datumsfelder_pruefen()
                and self._zukunftsdaten_pruefen() and self._startnummer_frei_pruefen()):
            return
        kuerzel = self._gewaehlte_pruefung()
        pruefung = pruefung_nach_kuerzel(kuerzel)
        name = pruefung.bezeichnung if pruefung else kuerzel
        if not (self._pruefung_angeboten_pruefen(kuerzel, name)
                and self._startnummernbereich_pruefen(kuerzel, name)
                and self._ed_gegenstaende_pruefen(kuerzel)
                and self._gegenstand_zuordnung_pruefen()):
            return
        if not _speichern_vor_dem_schliessen(self, self._speichern):
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
            gegenstand_1_disziplin=_zuordnung_oder_none(self.gegenstand_1_disziplin) if self.gegenstand_1.text().strip() else None,
            gegenstand_2_disziplin=_zuordnung_oder_none(self.gegenstand_2_disziplin) if self.gegenstand_2.text().strip() else None,
            gegenstand_3_disziplin=_zuordnung_oder_none(self.gegenstand_3_disziplin) if self.gegenstand_3.text().strip() else None,
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
        hinweis.setTextFormat(Qt.PlainText)  # S-1: Name nie als HTML deuten
        hinweis.setWordWrap(True)

        self.partner_combo = QComboBox()
        for t in sorted(andere_teilnehmer, key=lambda t: (t["startnummer"] is None, t["startnummer"] or 0)):
            nummer_anzeige = str(t["startnummer"]) if t["startnummer"] is not None else "keine"
            self.partner_combo.addItem(
                f"{t['nachname']}, {t['vorname']} (Start-Nr. {nummer_anzeige})", t["id"]
            )
        # UX-Test 03.11.2026, X9: kein Partner vorausgewählt - Enter tauschte sonst mit dem
        # erstbesten Teilnehmer der Liste. „OK“ erst nach einer Wahl.
        self.partner_combo.setPlaceholderText("– bitte Partner wählen –")
        self.partner_combo.setCurrentIndex(-1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        ok_btn = buttons.button(QDialogButtonBox.Ok)
        ok_btn.setEnabled(False)
        self.partner_combo.currentIndexChanged.connect(lambda i: ok_btn.setEnabled(i >= 0))

        layout = QVBoxLayout(self)
        layout.addWidget(hinweis)
        layout.addWidget(self.partner_combo)
        layout.addWidget(buttons)

    def ausgewaehlte_partner_id(self) -> int | None:
        return self.partner_combo.currentData()
