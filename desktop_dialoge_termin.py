"""
Dialoge rund um den Termin: Veranstaltungsdaten, Termin-Import, Sicherung erstellen.

Aus desktop_dialoge.py ausgelagert (11.11.2026), Code unverändert; desktop_dialoge.py bleibt als
Fassade. Bewusst KEIN `import app` (siehe desktop_programm.py).
"""

from __future__ import annotations
import os
import re
import sqlite3
from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from db import (
    ALLE_PRUEFUNGEN,
    angebotene_pruefungen,
    bereiche_automatisch_berechnen,
    dateiname_vorschlagen,
    datum_anzeige,
    leistungsklasse_label,
    liste_termine,
    list_teilnehmer,
    normalisiere_datum,
    pruefe_startnummer_bereiche,
    pruefungen_als_text,
    startnummer_bereiche,
    startnummer_bereiche_als_text,
    startnummer_bereichsgroesse,
    termin_lesend_pruefen,
    termin_unversehrt_pruefen,
    termine_ordner,
)
from db_sicherung import (
    eindeutigen_dateinamen_finden,
)
from desktop_gemeinsam import (
    _ja_nein,
    fehlende_formularangaben,
    fehlende_formularangaben_satz,
    _klartext_fehler,
    ResponsiveSchriftMixin,
)
from desktop_dialoge_basis import (
    _groesse_auf_bildschirm_begrenzen,
    _scrollflaeche,
    _speichern_vor_dem_schliessen,
)


def _gleicher_pfad(pfad_a: str | None, pfad_b: str | None) -> bool:
    """Vergleicht zwei Pfade unabhängig von "/" bzw. "\\" und (unter Windows) von der
    Groß-/Kleinschreibung."""
    if not pfad_a or not pfad_b:
        return False
    return os.path.normcase(os.path.abspath(pfad_a)) == os.path.normcase(os.path.abspath(pfad_b))


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
        # Desktop-Prüfung 14.10.2026, Teil 1 Nr. 1: Qt liefert Pfade mit "/", liste_termine()
        # mit "\" - der geöffnete Termin muss trotzdem sicher ausgeschlossen sein.
        self._termine = [
            t for t in liste_termine() if t.lesbar and not _gleicher_pfad(t.pfad, aktueller_pfad)
        ]

        self.termin_combo = QComboBox()
        for t in self._termine:
            self.termin_combo.addItem(
                f"{t.verein or '(ohne Verein)'} – {datum_anzeige(t.datum)} – "
                + (f"{t.teilnehmend} Teilnehmer, +{t.anzahl_abgemeldet} abgemeldet"
                   if t.anzahl_abgemeldet else f"{t.anzahl_teilnehmer} Teilnehmer")
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
        ok_knopf = self.buttons.button(QDialogButtonBox.Ok)
        if not (0 <= index < len(self._termine)):
            return
        # Die Quelle wird nur gelesen (Desktop-Prüfung 14.10.2026, Teil 1 Nr. 2): kein
        # init_db, also keine Migration und kein Schreiben in den anderen Termin - auch
        # schreibgeschützte Dateien älterer Versionen lassen sich so verwenden. Die Auswahl
        # spielt ein Journal nicht zurück (Marcos Entscheidung 15.10.2026); ist die Datei schon
        # halb beschrieben, gilt sie als nicht lesbar. Die Terminliste aus liste_termine hat
        # liegengebliebene Journale wie im Startdialog schon beim Öffnen des Dialogs
        # zurückgespielt - das betrifft also nur ein Journal, das erst danach entsteht.
        try:
            self._quelle_conn = termin_lesend_pruefen(self._termine[index].pfad)
            # Offene Punkte O2 (Marco 18.10.2026): nur hier, nicht in der Terminübersicht
            # (der Start bleibt schnell).
            termin_unversehrt_pruefen(self._quelle_conn)
            eintraege = []
            for t in list_teilnehmer(self._quelle_conn):
                text = f"{t['nachname']}, {t['vorname']} – {t['rufname_hund']} ({leistungsklasse_label(t)})"
                # Nur ein Vermerk (Marco 18.10.2026): übernommen werden ohnehin nur die
                # Stammdaten. .get, weil sehr alte Quelldateien die Spalte nicht haben.
                if t.get("keine_teilnahme"):
                    text += " – im Quelltermin nicht erschienen"
                eintraege.append((text, t["id"]))
            self._quelle_conn.set_progress_handler(None, 0)
        except (sqlite3.Error, OSError, KeyError, IndexError, TypeError, ValueError) as exc:
            self.schliesse_quelle()
            if isinstance(exc, (sqlite3.Error, OSError)):
                grund = _klartext_fehler(exc).replace(chr(10) * 2, " ")
            else:
                # Fehlende Spalte o. Ä. in der fremden Datei: str(KeyError) wäre nur der
                # Schlüssel (offener Punkt 18.10.2026). Kein Programmfehler, daher auch kein
                # Eintrag ins Absturzprotokoll.
                grund = (
                    "Die Datei enthält nicht alle erwarteten Angaben "
                    f"(Technisch: {type(exc).__name__}: {exc})."
                )
            hinweis = QListWidgetItem(
                f"Die Teilnehmer dieses Termins konnten nicht gelesen werden. {grund}\n"
                "Bitte einen anderen Termin wählen."
            )
            hinweis.setFlags(Qt.NoItemFlags)
            self.teilnehmer_liste.addItem(hinweis)
            ok_knopf.setEnabled(False)
            return
        for text, teilnehmer_id in eintraege:
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            item.setData(Qt.UserRole, teilnehmer_id)
            self.teilnehmer_liste.addItem(item)
        ok_knopf.setEnabled(True)

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
            "Sichert ALLE Termine in eine einzige Sicherungsdatei (nicht nur den gerade "
            "geöffneten Termin) - z. B. auf einen USB-Stick. Mit Passwort wird die "
            "Sicherungsdatei verschlüsselt, sodass niemand ohne Passwort die Teilnehmerdaten "
            "lesen kann. Das Passwort wird nicht gespeichert und lässt sich nicht "
            "wiederherstellen - bitte gut aufbewahren."
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
    (entscheidungen, anzahl_uebersprungen) für db_sicherung.sicherung_wiederherstellen().
    `aktion_fuer(name)` wird nur bei einem Namenskonflikt aufgerufen und liefert
    "ueberschreiben", "kopie" oder "ueberspringen" (siehe DatensicherungTab._konflikt_abfragen).

    Codeprüfung 22.09., G5: Die Kopie-Namen werden bewusst erst NACH allen Rückfragen
    vergeben und dabei alle schon eingeplanten Zielnamen (auch die auf sich selbst
    abgebildeten, also neue und zu überschreibende Einträge) als belegt übergeben. Sonst
    konnten zwei ZIP-Einträge auf dieselbe Zieldatei landen - z. B. enthält die Sicherung
    "A.sqlite" (vorhanden, als Kopie -> "A (2).sqlite") UND ein noch nicht vorhandenes
    "A (2).sqlite", und einer überschrieb still den anderen. Die Reihenfolge der Einträge
    im ZIP spielt durch die zweite Runde keine Rolle mehr.

    Sicherheitskorrektur Q-1 (07.10.2026), Details folgen."""
    vorhandene_namen = {n.casefold(): n for n in vorhandene}
    entscheidungen: dict[str, str] = {}
    als_kopie: list[str] = []
    uebersprungen = 0
    for name in namen:
        vorhandener_name = vorhandene_namen.get(name.casefold())
        if vorhandener_name is None:
            if name.casefold() in {ziel.casefold() for ziel in entscheidungen.values()}:
                als_kopie.append(name)
            else:
                entscheidungen[name] = name
            continue
        aktion = aktion_fuer(name)
        if aktion == "ueberschreiben":
            entscheidungen[name] = vorhandener_name
        elif aktion == "kopie":
            als_kopie.append(name)
        else:  # "ueberspringen"
            uebersprungen += 1
    for name in als_kopie:
        # Die vorhandenen Namen ausdrücklich als belegt mitgeben (Q-1).
        entscheidungen[name] = eindeutigen_dateinamen_finden(
            ordner, name, bereits_vergeben=set(entscheidungen.values()) | set(vorhandene_namen.values())
        )
    return entscheidungen, uebersprungen


#: Vorschlag für die Prüfungsgebühr, solange noch keine eigene hinterlegt wurde (siehe
#: VeranstaltungsDialog unten) - frei änderbar je Termin, dient nur als Startwert.
_STANDARD_PRUEFUNGSGEBUEHR = "12,00"


def _mit_sqlite_endung(pfad: str) -> str:
    return pfad if not pfad or pfad.lower().endswith(".sqlite") else pfad + ".sqlite"


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
    Standardwert vorbelegt, der sich pro Termin überschreiben lässt.
    Nutzerwunsch 28.09.2026: Verband, Meldestelle und die angebotenen Prüfungen erscheinen
    im ausfüllbaren Anmeldeformular (siehe pdf_export.erstelle_anmeldeformular_pdf) - nur
    die hier angehakten Prüfungen sind dort ankreuzbar."""

    def __init__(self, parent=None, vorbelegung: dict | None = None, bearbeiten: bool = False,
                 speichern=None):
        super().__init__(parent)
        self._bearbeiten = bearbeiten
        # Rückruf speichern(dialog), siehe _speichern_vor_dem_schliessen.
        self._speichern = speichern
        self.setWindowTitle("Veranstaltungsdaten bearbeiten" if bearbeiten else "Neuen Termin anlegen")
        vorbelegung = vorbelegung or {}
        self._lr_saetze = {name: vorbelegung.get(name) for name in ("lr_km_satz", "lr_tagespauschale", "checkliste_eigene")}

        self._felder_erstellen(vorbelegung, bearbeiten)
        self._pruefungsgruppe_aufbauen(vorbelegung)
        self._bereichsgruppe_aufbauen(vorbelegung)
        form = self._formular_aufbauen(bearbeiten)
        self._layout_aufbauen(form)

    def _felder_erstellen(self, vorbelegung: dict, bearbeiten: bool) -> None:
        """Eingabefelder der Veranstaltungsdaten (mit Vorbelegung)."""

        def feld(name: str) -> QLineEdit:
            return QLineEdit(vorbelegung.get(name) or "")

        def geld_feld(name: str) -> QLineEdit:
            # Teil 2 Nr. 8a: Standardgebühr nur beim Anlegen - ein bewusst geleertes Feld
            # bleibt beim Bearbeiten leer.
            return QLineEdit(vorbelegung.get(name) or ("" if bearbeiten else _STANDARD_PRUEFUNGSGEBUEHR))

        self.verein = feld("verein")
        self.ort = feld("ort")
        self.datum = QLineEdit(datum_anzeige(vorbelegung.get("datum")))
        self.datum.setPlaceholderText("TT.MM.JJJJ")
        # UX-Test 03.11.2026, X15: „14.11.26“ wurde abgelehnt - beim Verlassen des Felds zu
        # 14.11.2026 ergänzen (nur hier, ein Prüfungstermin liegt nie im 20. Jahrhundert).
        self.datum.editingFinished.connect(self._jahr_ergaenzen)
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
        self.verband = feld("verband")
        self.meldestelle = QPlainTextEdit(vorbelegung.get("meldestelle") or "")
        self.meldestelle.setPlaceholderText("z. B. Name, Anschrift, E-Mail-Adresse")
        self.meldestelle.setTabChangesFocus(True)
        self.meldestelle.setFixedHeight(self.meldestelle.fontMetrics().lineSpacing() * 4 + 12)

    def _pruefungsgruppe_aufbauen(self, vorbelegung: dict) -> None:
        # Ankreuzbare Prüfungen des Anmeldeformulars, angeordnet wie dort: je Art/Disziplin
        # eine Zeile (DK, Trümmer, Behältnisse, Fläche), je Leistungsklasse eine Spalte.
        vorher_angeboten = {p.kuerzel for p in angebotene_pruefungen(vorbelegung)}
        self.pruefung_checkboxen: dict[str, QCheckBox] = {}
        self.gruppe_pruefungen = QGroupBox("Angebotene Prüfungen (für das Anmeldeformular)")
        pruefungen_raster = QGridLayout(self.gruppe_pruefungen)
        for i, pruefung in enumerate(ALLE_PRUEFUNGEN):
            checkbox = QCheckBox(pruefung.bezeichnung)
            checkbox.setChecked(pruefung.kuerzel in vorher_angeboten)
            self.pruefung_checkboxen[pruefung.kuerzel] = checkbox
            pruefungen_raster.addWidget(checkbox, i // 3, i % 3)

    def _bereichsgruppe_aufbauen(self, vorbelegung: dict) -> None:
        # UX-Test 02.10.2026, U1: Startnummern-Bereich je Prüfung für "Fehlende
        # Startnummern vergeben…". Nur für angebotene Prüfungen sichtbar (sind keine
        # angehakt, für alle 12) - Marcos Entscheidung 03.10.2026.
        vorher_bereiche = startnummer_bereiche(vorbelegung)
        self.bereich_felder: dict[str, tuple[QLabel, QLineEdit, QLineEdit]] = {}
        self.gruppe_bereiche = QGroupBox("Startnummern-Bereiche (für „Fehlende Startnummern vergeben…“)")
        bereiche_raster = QGridLayout(self.gruppe_bereiche)
        # Marco 09.10.2026: Bereiche aus einer Anzahl je Prüfung automatisch festlegen
        # (Standardgröße, je Prüfung änderbar), lückenlos ab 1 in der Reihenfolge der
        # Prüfungen. Die Anzahl je Prüfung wird nicht gespeichert, sondern beim Öffnen aus
        # dem vorhandenen Bereich abgeleitet.
        self.standard_groesse = QSpinBox()
        self.standard_groesse.setRange(1, 999)
        self.standard_groesse.setValue(startnummer_bereichsgroesse(vorbelegung))
        self.standard_uebernehmen_btn = QPushButton("Für alle übernehmen")
        self.standard_uebernehmen_btn.clicked.connect(self._standardgroesse_uebernehmen)
        self.automatisch_btn = QPushButton("Bereiche automatisch festlegen")
        self.automatisch_btn.clicked.connect(self._bereiche_automatisch_festlegen)
        # Zwei Zeilen statt einer: in einer Zeile war die Gruppe breiter als der Dialog
        # (waagerechte Scrollleiste, Marco 09.10.2026).
        groesse_zeile = QHBoxLayout()
        groesse_zeile.addWidget(QLabel("Standardgröße je Prüfung:"))
        groesse_zeile.addWidget(self.standard_groesse)
        groesse_zeile.addStretch(1)
        knopf_zeile = QHBoxLayout()
        knopf_zeile.addWidget(self.standard_uebernehmen_btn)
        knopf_zeile.addWidget(self.automatisch_btn)
        knopf_zeile.addStretch(1)
        bereiche_raster.addLayout(groesse_zeile, 0, 0, 1, 5)
        bereiche_raster.addLayout(knopf_zeile, 1, 0, 1, 5)
        bereiche_raster.addWidget(QLabel("Prüfung"), 2, 0)
        bereiche_raster.addWidget(QLabel("Anzahl"), 2, 1)
        bereiche_raster.addWidget(QLabel("von"), 2, 2)
        bereiche_raster.addWidget(QLabel("bis"), 2, 3)
        self.anzahl_felder: dict[str, QSpinBox] = {}
        for zeile, pruefung in enumerate(ALLE_PRUEFUNGEN, start=3):
            beschriftung = QLabel(pruefung.bezeichnung)
            anzahl_feld = QSpinBox()
            anzahl_feld.setRange(0, 999)
            anzahl_feld.setSpecialValueText("keine")
            anzahl_feld.setValue(self.standard_groesse.value())
            von_feld, bis_feld = QLineEdit(), QLineEdit()
            for nummer_feld in (von_feld, bis_feld):
                nummer_feld.setValidator(QIntValidator(1, 999, nummer_feld))  # wie Startnummer-Feld
                nummer_feld.setMaximumWidth(80)
            if pruefung.kuerzel in vorher_bereiche:
                von, bis = vorher_bereiche[pruefung.kuerzel]
                von_feld.setText(str(von))
                bis_feld.setText(str(bis))
                if 1 <= bis - von + 1 <= 999:
                    anzahl_feld.setValue(bis - von + 1)
            bereiche_raster.addWidget(beschriftung, zeile, 0)
            bereiche_raster.addWidget(anzahl_feld, zeile, 1)
            bereiche_raster.addWidget(von_feld, zeile, 2)
            bereiche_raster.addWidget(bis_feld, zeile, 3)
            self.bereich_felder[pruefung.kuerzel] = (beschriftung, von_feld, bis_feld)
            self.anzahl_felder[pruefung.kuerzel] = anzahl_feld
            # Verifikation V1 (Marco 09.10.2026): von Hand geänderte von/bis-Felder ziehen
            # die Anzahl mit, damit ein späteres "automatisch festlegen" sie beibehält.
            for nummer_feld in (von_feld, bis_feld):
                nummer_feld.textEdited.connect(
                    lambda _text, kuerzel=pruefung.kuerzel: self._anzahl_aus_bereich(kuerzel)
                )
        bereiche_raster.setColumnStretch(4, 1)
        bereiche_hinweis = QLabel(
            "Nur für die oben angehakten Prüfungen (ohne Haken: alle). Bereiche abgewählter "
            "Prüfungen werden beim Speichern entfernt. Leer lassen = keine automatische Vergabe. "
            "„Bereiche automatisch festlegen“ überschreibt die von/bis-Felder aller angebotenen "
            "Prüfungen: lückenlos ab 1, "
            "je Prüfung so viele Nummern wie unter „Anzahl“ (Anzahl „keine“ = kein Bereich)."
        )
        bereiche_hinweis.setWordWrap(True)
        bereiche_raster.addWidget(bereiche_hinweis, len(ALLE_PRUEFUNGEN) + 3, 0, 1, 5)
        for checkbox in self.pruefung_checkboxen.values():
            checkbox.toggled.connect(self._bereichszeilen_anpassen)
        self._bereichszeilen_anpassen()

    def _formular_aufbauen(self, bearbeiten: bool) -> QFormLayout:
        """Linke Spalte: Eckdaten (und beim Anlegen der Speicherort)."""
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
        form.addRow("Verband", self.verband)
        form.addRow("Meldestelle", self.meldestelle)

        # Teil 2 Nr. 2: Speicherort vor dem Anlegen prüfen; die Demo schaltet das ab (ihr
        # Termin liegt fest im Demo-Ordner und existiert schon).
        self.pfad_pruefen = True
        self.bestehenden_oeffnen = False
        if not bearbeiten:
            self.pfad_feld = QLineEdit()
            self._pfad_manuell_geaendert = False
            self.pfad_feld.textEdited.connect(self._pfad_manuell_markieren)
            self.verein.textChanged.connect(self._pfad_vorschlagen)
            self.datum.textChanged.connect(self._pfad_vorschlagen)
            self._pfad_vorschlagen()

            self.durchsuchen_btn = QPushButton("Durchsuchen…")
            self.durchsuchen_btn.clicked.connect(self._durchsuchen)
            pfad_zeile = QHBoxLayout()
            pfad_zeile.addWidget(self.pfad_feld)
            pfad_zeile.addWidget(self.durchsuchen_btn)
            form.addRow("Speicherort*", pfad_zeile)
        return form

    def _layout_aufbauen(self, form: QFormLayout) -> None:
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._pruefen_und_akzeptieren)
        buttons.rejected.connect(self.reject)

        # Mit Meldestelle und Prüfungsauswahl (28.09.2026) wurde der Dialog für kleinere
        # Bildschirme zu hoch - Inhalt deshalb wie im TeilnehmerDialog in einem
        # QScrollArea, OK/Abbrechen bleiben fest am unteren Rand erreichbar.
        # Nachtest 2 (N14): zweispaltig - links die Eckdaten, rechts Prüfungen und
        # Startnummern-Bereiche; „Behältnisse“, „Fläche“ und die Bereiche lagen sonst unter dem
        # Bildlauf. Die Höhe richtet sich nach dem Inhalt (höchstens 90 % des Bildschirms).
        links = QVBoxLayout()
        links.addLayout(form)
        links.addStretch()
        rechts = QVBoxLayout()
        rechts.addWidget(self.gruppe_pruefungen)
        rechts.addWidget(self.gruppe_bereiche)
        rechts.addStretch()  # überschüssige Höhe nicht auf die Prüfungsauswahl verteilen
        inhalt_layout = QHBoxLayout()
        inhalt_layout.addLayout(links, 1)
        inhalt_layout.addSpacing(12)
        inhalt_layout.addLayout(rechts, 1)
        inhalt_container = QWidget()
        inhalt_container.setLayout(inhalt_layout)
        inhalt_scroll = _scrollflaeche(inhalt_container)

        layout = QVBoxLayout(self)
        layout.addWidget(inhalt_scroll, 1)
        layout.addWidget(buttons)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)
        _groesse_auf_bildschirm_begrenzen(self, 1000, 700, inhalt=inhalt_container, hoehe_nach_inhalt=True)
        self.verein.setFocus()
        self._schriftgroesse_anwenden()

    def veranstaltung_werte(self) -> dict:
        """Alle Eingaben als Argumente für db.set_veranstaltung bzw.
        _aktualisiere_veranstaltung_feld (nach _pruefen_und_akzeptieren aufrufen) - vorher
        wortgleich in StartDialog._neuer_termin und VerwaltungTab._veranstaltung_bearbeiten,
        jetzt auch von der Demoprüfung genutzt."""
        werte = dict(
            verein=self.verein.text().strip(),
            datum=self.datum_iso(),
            ort=self.ort.text().strip() or None,
            vereins_nr=self.vereins_nr.text().strip() or None,
            pruefungsnummer=self.pruefungsnummer.text().strip() or None,
            wertungsrichter_1=self.wertungsrichter_1.text().strip() or None,
            wertungsrichter_2=self.wertungsrichter_2.text().strip() or None,
            wertungsrichter_3=self.wertungsrichter_3.text().strip() or None,
            wertungsrichter_4=self.wertungsrichter_4.text().strip() or None,
            wertungsrichter_5=self.wertungsrichter_5.text().strip() or None,
            pruefungsleiter=self.pruefungsleiter.text().strip() or None,
            pruefungsgebuehr_ed=self.pruefungsgebuehr_ed.text().strip() or None,
            pruefungsgebuehr_dk=self.pruefungsgebuehr_dk.text().strip() or None,
            verband=self.verband.text().strip() or None,
            meldestelle=self.meldestelle_text(),
            angebotene_pruefungen=self.angebotene_pruefungen_text(),
            startnummer_bereiche=self.startnummer_bereiche_text(),
            startnummer_bereichsgroesse=str(self.standard_groesse.value()),
        )
        # Marco 09.11.2026: Sätze der Leistungsrichter-Abrechnung stehen nicht im Dialog; sie
        # werden nur durchgereicht (Vorschlag aus dem letzten Termin beim Anlegen).
        werte.update({name: wert for name, wert in self._lr_saetze.items() if wert})
        return werte

    def meldestelle_text(self) -> str | None:
        """Meldestelle (mehrzeilig) in Speicherform; None, wenn leer."""
        return self.meldestelle.toPlainText().strip() or None

    def angebotene_pruefungen_text(self) -> str | None:
        """Angehakte Prüfungen in Speicherform (siehe db.pruefungen_als_text)."""
        return pruefungen_als_text([k for k, cb in self.pruefung_checkboxen.items() if cb.isChecked()])

    def _sichtbare_bereich_kuerzel(self) -> list[str]:
        angehakt = [k for k, cb in self.pruefung_checkboxen.items() if cb.isChecked()]
        return angehakt or list(self.pruefung_checkboxen)

    def _bereichszeilen_anpassen(self, _checked: bool = False) -> None:
        sichtbar = set(self._sichtbare_bereich_kuerzel())
        for kuerzel, widgets in self.bereich_felder.items():
            for widget in (*widgets, self.anzahl_felder[kuerzel]):
                widget.setVisible(kuerzel in sichtbar)

    def _anzahl_aus_bereich(self, kuerzel: str) -> None:
        _beschriftung, von_feld, bis_feld = self.bereich_felder[kuerzel]
        if not von_feld.text().strip() and not bis_feld.text().strip():
            # Verifikation C: Bereich von Hand entfernt -> beim automatischen Festlegen
            # nicht wieder anlegen.
            self.anzahl_felder[kuerzel].setValue(0)
            return
        try:
            anzahl = int(bis_feld.text()) - int(von_feld.text()) + 1
        except ValueError:
            return
        if 1 <= anzahl <= 999:
            self.anzahl_felder[kuerzel].setValue(anzahl)

    def _standardgroesse_uebernehmen(self) -> None:
        for anzahl_feld in self.anzahl_felder.values():
            anzahl_feld.setValue(self.standard_groesse.value())

    def _bereiche_automatisch_festlegen(self) -> None:
        """Füllt die von/bis-Felder der sichtbaren Prüfungen lückenlos aus ihrer Anzahl
        (Marco 09.10.2026: überschreibt alle bisherigen Bereiche)."""
        sichtbar = self._sichtbare_bereich_kuerzel()
        try:
            bereiche = bereiche_automatisch_berechnen(
                {kuerzel: self.anzahl_felder[kuerzel].value() for kuerzel in sichtbar}
            )
        except ValueError as fehler:
            QMessageBox.warning(self, "Startnummern-Bereiche", str(fehler))
            return
        for kuerzel in sichtbar:
            _beschriftung, von_feld, bis_feld = self.bereich_felder[kuerzel]
            von, bis = bereiche.get(kuerzel, ("", ""))
            von_feld.setText(str(von))
            bis_feld.setText(str(bis))

    def _startnummer_bereiche_lesen(self) -> dict[str, tuple[int, int]]:
        """Eingetragene Bereiche der sichtbaren Prüfungen. Wirft ValueError mit einem
        Text für den Nutzer, wenn nur "von" oder nur "bis" ausgefüllt ist."""
        bereiche: dict[str, tuple[int, int]] = {}
        for kuerzel in self._sichtbare_bereich_kuerzel():
            beschriftung, von_feld, bis_feld = self.bereich_felder[kuerzel]
            von, bis = von_feld.text().strip(), bis_feld.text().strip()
            if not von and not bis:
                continue
            if not von or not bis:
                self._bereich_fehler_feld = bis_feld if von else von_feld
                raise ValueError(f"{beschriftung.text()}: bitte „von“ UND „bis“ eintragen oder beide leer lassen.")
            # Teil 2 Nr. 3: Zwischeneingaben wie „20.“ ergaben sonst eine englische Meldung.
            werte = []
            for text, nummer_feld in ((von, von_feld), (bis, bis_feld)):
                try:
                    werte.append(int(text))
                except ValueError:
                    self._bereich_fehler_feld = nummer_feld
                    raise ValueError(f"{beschriftung.text()}: „{text}“ ist keine Startnummer (1–999).") from None
            bereiche[kuerzel] = (werte[0], werte[1])
        return bereiche

    def startnummer_bereiche_text(self) -> str | None:
        """Bereiche in Speicherform (siehe db.startnummer_bereiche_als_text) - bereits in
        _pruefen_und_akzeptieren geprüft."""
        return startnummer_bereiche_als_text(self._startnummer_bereiche_lesen())

    def datum_iso(self) -> str:
        """Eingegebenes Datum in Speicherform JJJJ-MM-TT (bereits in
        _pruefen_und_akzeptieren geprüft, siehe db.normalisiere_datum)."""
        return normalisiere_datum(self.datum.text()) or ""

    def _pfad_manuell_markieren(self, _text: str) -> None:
        self._pfad_manuell_geaendert = True

    def _jahr_ergaenzen(self) -> None:
        treffer = re.fullmatch(r"\s*(\d{1,2})\.(\d{1,2})\.(\d{2})\s*", self.datum.text())
        if treffer:
            tag, monat, jahr = treffer.groups()
            self.datum.setText(f"{int(tag):02d}.{int(monat):02d}.20{jahr}")

    def _pfad_vorschlagen(self) -> None:
        if self._pfad_manuell_geaendert:
            return
        # Solange das Datum (noch) nicht lesbar ist, z. B. mitten in der Eingabe, den Text
        # unverändert verwenden - sobald es passt, landet JJJJ-MM-TT im Dateinamen.
        try:
            datum = normalisiere_datum(self.datum.text()) or ""
        except ValueError:
            datum = self.datum.text().strip()
        ordner = termine_ordner()
        # Teil 2 Nr. 2: bei gleichem Verein und Datum nicht die vorhandene Datei vorschlagen.
        name = eindeutigen_dateinamen_finden(ordner, dateiname_vorschlagen(self.verein.text().strip(), datum))
        self.pfad_feld.setText(str(ordner / name))

    def _durchsuchen(self) -> None:
        # Ob eine vorhandene Datei gemeint ist, fragt _pruefen_und_akzeptieren (eine Frage statt
        # zwei sich widersprechender).
        pfad, _ = QFileDialog.getSaveFileName(self, "Speicherort wählen", self.pfad_feld.text(),
                                              "SHS-Termin (*.sqlite)", options=QFileDialog.DontConfirmOverwrite)
        if pfad:
            self.pfad_feld.setText(_mit_sqlite_endung(pfad))
            self._pfad_manuell_geaendert = True

    def _speicherort_pruefen(self) -> bool:
        """Teil 2 Nr. 2: Pfad absolut, Ordner vorhanden, Endung .sqlite (sonst erscheint der
        Termin nie im Startdialog), Datei noch nicht vorhanden - gibt es sie schon, wird
        gefragt, ob stattdessen dieser Termin geöffnet werden soll."""
        eingabe = self.pfad_feld.text().strip()
        pfad = _mit_sqlite_endung(eingabe)
        self.pfad_feld.setText(pfad)
        if eingabe.endswith(("/", "\\")) or os.path.isdir(pfad):
            QMessageBox.warning(self, "Speicherort", "Bitte zum Ordner auch einen Dateinamen angeben.")
        elif not os.path.isabs(pfad):
            QMessageBox.warning(self, "Speicherort", "Bitte einen vollständigen Speicherort angeben, "
                                "z. B. über „Durchsuchen…“.")
        elif not os.path.isdir(os.path.dirname(pfad)):
            QMessageBox.warning(self, "Speicherort", f"Den Ordner gibt es nicht:\n{os.path.dirname(pfad)}")
        elif os.path.exists(pfad):
            if _ja_nein(
                self, "Datei existiert bereits",
                f"Die Datei „{pfad}“ existiert bereits.\n\nStattdessen als bestehenden Termin öffnen? "
                "(„Nein“: zurück, um einen anderen Speicherort zu wählen.)",
            ):
                self.bestehenden_oeffnen = True
                self.accept()
                return False
        else:
            return True
        self.pfad_feld.setFocus()
        return False

    def _pruefen_und_akzeptieren(self) -> None:
        self._jahr_ergaenzen()  # auch bei Enter direkt im Datumsfeld
        if not self.verein.text().strip() or not self.datum.text().strip():
            QMessageBox.warning(self, "Angaben unvollständig", "Bitte Verein und Datum angeben.")
            (self.verein if not self.verein.text().strip() else self.datum).setFocus()
            return
        try:
            normalisiere_datum(self.datum.text())
        except ValueError as fehler:
            QMessageBox.warning(self, "Ungültiges Datum", f"Datum: {fehler}")
            self.datum.setFocus()
            return
        if not self._bearbeiten and not self.pfad_feld.text().strip():
            QMessageBox.warning(self, "Angaben unvollständig", "Bitte einen Speicherort angeben.")
            self.pfad_feld.setFocus()
            return
        if not self._bearbeiten and self.pfad_pruefen and not self._speicherort_pruefen():
            return
        self._bereich_fehler_feld = None
        try:
            bereich_fehler = pruefe_startnummer_bereiche(self._startnummer_bereiche_lesen())
        except ValueError as fehler:
            bereich_fehler = str(fehler)
        if bereich_fehler:
            QMessageBox.warning(self, "Startnummern-Bereiche", bereich_fehler)
            if self._bereich_fehler_feld is not None:
                self._bereich_fehler_feld.setFocus()
            return
        # UX-Test 02.10.2026, K6: Beim Anlegen darauf hinweisen, dass leere Angaben auf dem
        # Anmeldeformular fehlen - Speichern bleibt trotzdem möglich. UX-Test 2026-11, T7 (Marco
        # 04.11.2026): Vorgabe „Nein“ - wer Enter drückt, trägt die Angaben nach, statt ein
        # Formular ohne Meldestelle zu bekommen.
        fehlend = fehlende_formularangaben(self.verband.text(), self.meldestelle_text())
        if not self._bearbeiten and fehlend:
            if not _ja_nein(
                self, "Angaben für das Anmeldeformular",
                fehlende_formularangaben_satz(fehlend) + " für die Teilnehmer.\n\n"
                "Du kannst das auch später im Reiter „Verwaltung“ über „Veranstaltungsdaten "
                "bearbeiten…“ nachtragen.\n\n"
                "Trotzdem jetzt speichern?",
            ):
                (self.verband if "Verband" in fehlend else self.meldestelle).setFocus()
                return
        if not _speichern_vor_dem_schliessen(self, self._speichern):
            return
        self.accept()
