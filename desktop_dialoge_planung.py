"""
Dialoge für Zeitplan und Ausdrucke: Prüfungsblock, Pause, automatisch verteilen, Bewertungsbogen- und Etiketten-Auswahl.

Aus desktop_dialoge.py ausgelagert (11.11.2026), Code unverändert; desktop_dialoge.py bleibt als
Fassade. Bewusst KEIN `import app` (siehe desktop_programm.py).
"""

from __future__ import annotations
import datetime
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)
from db import (
    ALLE_DISZIPLINEN,
)
from desktop_gemeinsam import (
    ResponsiveSchriftMixin,
)


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

    def __init__(self, parent=None, dauer_minuten: int = 15, bezeichnung: str = "", neu: bool = False):
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

        # UX-Test 02.10.2026, U9: beim Hinzufügen wahlweise dieselbe Pause bei allen
        # Richtern zu einer Uhrzeit (z. B. Mittagspause); sonst nach der markierten Zeile.
        # Beim Bearbeiten gibt es beide Felder nicht (OFFEN.md B4, 19.10.2026).
        self.fuer_alle: QCheckBox | None = None
        self.uhrzeit: QLineEdit | None = None
        self.genau: QCheckBox | None = None
        if neu:
            self.fuer_alle = QCheckBox("Bei allen Richtern einfügen, um")
            self.uhrzeit = QLineEdit("12:00")
            self.uhrzeit.setPlaceholderText("HH:MM")
            self.uhrzeit.setMaximumWidth(70)
            self.uhrzeit.setEnabled(False)
            self.fuer_alle.toggled.connect(self.uhrzeit.setEnabled)
            alle_zeile = QHBoxLayout()
            alle_zeile.addWidget(self.fuer_alle)
            alle_zeile.addWidget(self.uhrzeit)
            alle_zeile.addWidget(QLabel("Uhr"))
            alle_zeile.addStretch()
            form.addRow(alle_zeile)
            # R-B20 (Marco 05.11.2026): Pause genau zur Uhrzeit, mit Lücke davor.
            self.genau = QCheckBox("genau um diese Uhrzeit beginnen (sonst direkt nach dem Block davor)")
            self.genau.setEnabled(False)
            self.fuer_alle.toggled.connect(self.genau.setEnabled)
            form.addRow(self.genau)
            hinweis = QLabel(
                "Ohne Haken wird die Pause nach der in der Liste markierten Zeile eingefügt "
                "(sonst am Ende). Mit Haken je Richter vor dem ersten Block ab dieser Uhrzeit; "
                "wer vorher schon fertig ist, bekommt keine Pause. Mit „genau“ beginnt sie genau "
                "zur Uhrzeit: Ein Block, der erst kurz vorher (weniger als 15 Minuten) begonnen hätte, "
                "rückt dahinter, davor bleibt eine Lücke; ein länger laufender Block wird nicht geteilt."
            )
            hinweis.setWordWrap(True)
            form.addRow(hinweis)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._pruefen_und_akzeptieren)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self._schriftgroesse_anwenden()

    def _pruefen_und_akzeptieren(self) -> None:
        if self.fuer_alle is not None and self.fuer_alle.isChecked():
            try:
                datetime.datetime.strptime(self.uhrzeit.text().strip(), "%H:%M")
            except ValueError:
                QMessageBox.warning(self, "Ungültige Uhrzeit", "Bitte die Uhrzeit als HH:MM eingeben, z. B. 12:00.")
                return
        self.accept()

    def werte(self) -> dict:
        return {
            "dauer_minuten": self.dauer_minuten.value(),
            "bezeichnung": self.bezeichnung.text().strip() or None,
        }


class VerteilenDialog(ResponsiveSchriftMixin, QDialog):
    """UX-Test 2026-11, T1 (Marco 04.11.2026): „Automatisch verteilen…“ mit optionaler
    Mittagspause. Sie wird nach dem Verteilen bei allen Richtern eingefügt (wie „Pause bei
    allen Richtern“). Steht im bisherigen Plan schon eine Mittagspause, ist sie vorbelegt -
    so bleibt sie beim Neu-Verteilen erhalten. `ersetzt_plan`: Warnung, dass der bisherige
    Plan ersetzt wird (vorher eine eigene Rückfrage, UX-Test 02.10.2026, U9)."""

    def __init__(self, parent=None, ersetzt_plan: bool = False, pause: tuple[str, int] | None = None,
                 pause_fest: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Automatisch verteilen")

        text = QLabel(
            "Erstellt einen ausgewogenen Vorschlag über ALLE angelegten Richter."
            + (" Der bisherige Zeitplan wird dabei ERSETZT (eingefügte Pausen und von Hand "
               "geänderte Reihenfolgen gehen verloren)." if ersetzt_plan else "")
        )
        text.setWordWrap(True)
        self.warnung = text

        self.mit_pause = QCheckBox("Mittagspause einplanen um")
        self.uhrzeit = QLineEdit(pause[0] if pause else "12:00")
        self.uhrzeit.setPlaceholderText("HH:MM")
        self.uhrzeit.setMaximumWidth(70)
        self.dauer_minuten = QSpinBox()
        self.dauer_minuten.setRange(5, 240)
        self.dauer_minuten.setValue(pause[1] if pause else 45)
        self.dauer_minuten.setSuffix(" Min.")
        self.mit_pause.toggled.connect(self.uhrzeit.setEnabled)
        self.mit_pause.toggled.connect(self.dauer_minuten.setEnabled)
        self.mit_pause.setChecked(pause is not None)
        self.uhrzeit.setEnabled(pause is not None)
        self.dauer_minuten.setEnabled(pause is not None)
        pause_zeile = QHBoxLayout()
        pause_zeile.addWidget(self.mit_pause)
        pause_zeile.addWidget(self.uhrzeit)
        pause_zeile.addWidget(QLabel("Uhr für"))
        pause_zeile.addWidget(self.dauer_minuten)
        pause_zeile.addStretch()
        # R-B20 (Marco 05.11.2026): Mittagspause genau zur Uhrzeit, mit Lücke davor.
        self.pause_genau = QCheckBox("genau um diese Uhrzeit beginnen (sonst direkt nach dem Block davor)")
        self.pause_genau.setChecked(pause_fest)
        self.pause_genau.setEnabled(pause is not None)
        self.mit_pause.toggled.connect(self.pause_genau.setEnabled)
        pause_hinweis = QLabel("Je Richter vor dem ersten Block ab dieser Uhrzeit; wer vorher schon "
                               "fertig ist, bekommt keine Pause. Mit „genau“ beginnt sie genau zur "
                               "Uhrzeit: Ein Block, der erst kurz vorher (weniger als 15 Minuten) "
                               "begonnen hätte, rückt dahinter, davor bleibt eine Lücke; ein länger "
                               "laufender Block wird nicht geteilt.")
        pause_hinweis.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Verteilen")
        buttons.accepted.connect(self._pruefen_und_akzeptieren)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(text)
        layout.addLayout(pause_zeile)
        layout.addWidget(self.pause_genau)
        layout.addWidget(pause_hinweis)
        layout.addWidget(buttons)
        self._schriftgroesse_anwenden()

    def _pruefen_und_akzeptieren(self) -> None:
        if self.mit_pause.isChecked():
            try:
                datetime.datetime.strptime(self.uhrzeit.text().strip(), "%H:%M")
            except ValueError:
                QMessageBox.warning(self, "Ungültige Uhrzeit", "Bitte die Uhrzeit als HH:MM eingeben, z. B. 12:00.")
                self.uhrzeit.setFocus()
                return
        self.accept()

    def pause(self) -> tuple[str, int] | None:
        """(Uhrzeit „HH:MM“, Dauer in Minuten) oder None ohne Mittagspause."""
        if not self.mit_pause.isChecked():
            return None
        uhrzeit = datetime.datetime.strptime(self.uhrzeit.text().strip(), "%H:%M").strftime("%H:%M")
        return uhrzeit, self.dauer_minuten.value()

    def pause_fest(self) -> bool:
        """R-B20: Mittagspause genau zur Uhrzeit (mit Lücke davor)."""
        return self.mit_pause.isChecked() and self.pause_genau.isChecked()


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

        # Wunsch 10.11.2026: beim Dreikampf wahlweise ein Blatt je Disziplin (drei Stapel für
        # die Richter) statt des 2-Seiten-Bogens je Teilnehmer; ED bleibt unverändert.
        self.je_disziplin = QCheckBox("Dreikampf: ein Blatt je Disziplin (Trümmerfeld, Fläche, Behältnis)")
        self.je_disziplin.setToolTip(
            "Statt des 2-Seiten-Bogens bekommt jeder Dreikampf-Teilnehmer drei Blätter, nach "
            "Disziplin sortiert: erst alle Trümmerfeld-Blätter, dann alle Flächensuche, dann alle "
            "Behältnisstrecke - jeder Richter bekommt seinen Stapel. Einzeldisziplinen bleiben unverändert.")

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        # Desktop-Prüfung 14.10.2026 (Teil 6 Nr. 6): OK nur mit mindestens einem Haken - sonst
        # entstand ein leeres PDF mit „0 Bewertungsbögen gespeichert“.
        self.liste.itemChanged.connect(lambda _item: self._ok_aktualisieren())
        self._ok_aktualisieren()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Welche Art/Leistungsklasse(n) sollen in die Sammel-PDF aufgenommen werden? "
            "Standardmäßig sind alle angehakt."
            if labels else "Keine Teilnehmer erfasst."
        ))
        layout.addLayout(auswahl_zeile)
        layout.addWidget(self.liste)
        layout.addWidget(self.je_disziplin)
        layout.addWidget(self.buttons)

    def _alle_umschalten(self, zustand) -> None:
        for row in range(self.liste.count()):
            self.liste.item(row).setCheckState(zustand)

    def _ok_aktualisieren(self) -> None:
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(bool(self.ausgewaehlte_labels()))

    def ausgewaehlte_labels(self) -> set[str]:
        return {
            self.liste.item(row).text()
            for row in range(self.liste.count())
            if self.liste.item(row).checkState() == Qt.Checked
        }


class BehaeltnisEtikettenDialog(QDialog):
    """Einstellungen für die Etiketten der Behältnisse (Wunsch 10.11.2026): Größe der
    Klebefelder in mm, Ränder und ob die Etiketten auf einen Etikettenbogen (Raster, ohne
    Linien) oder auf normales Papier (mit Schnittlinien) gedruckt werden."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Etiketten für Behältnisse")

        self.bogen = QRadioButton("Etikettenbogen (Klebeetiketten, ohne Linien)")
        self.papier = QRadioButton("Normales Papier (mit Schnittlinien zum Ausschneiden)")
        self.bogen.setChecked(True)

        def feld(wert: float, minimum: float, maximum: float) -> QDoubleSpinBox:
            box = QDoubleSpinBox()
            box.setRange(minimum, maximum)
            box.setDecimals(1)
            box.setSuffix(" mm")
            box.setValue(wert)
            return box

        self.breite = feld(70, 30, 200)
        self.hoehe = feld(37, 20, 280)
        self.rand_links = feld(0, 0, 100)
        self.rand_oben = feld(0, 0, 100)
        self.hinweis = QLabel("")
        self.hinweis.setWordWrap(True)
        # Befund C: die Ränder nur beim Umschalten vorbelegen, solange der Nutzer sie nicht selbst geändert hat.
        self._rand_von_hand = False
        self._rand_wird_gesetzt = False
        self.papier.toggled.connect(self._papier_umgeschaltet)
        for box in (self.rand_links, self.rand_oben):
            box.valueChanged.connect(self._rand_geaendert)
        for box in (self.breite, self.hoehe, self.rand_links, self.rand_oben):
            box.valueChanged.connect(self._hinweis_aktualisieren)

        form = QFormLayout()
        form.addRow("Breite eines Etiketts", self.breite)
        form.addRow("Höhe eines Etiketts", self.hoehe)
        form.addRow("Rand links", self.rand_links)
        form.addRow("Rand oben", self.rand_oben)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Ein Etikett je Hund mit Behältnisstrecke: Startnummer, Name, Hund, "
                                "Prüfung und Gegenstand."))
        layout.addWidget(self.bogen)
        layout.addWidget(self.papier)
        layout.addLayout(form)
        layout.addWidget(self.hinweis)
        layout.addWidget(self.buttons)
        self._hinweis_aktualisieren()

    def _rand_geaendert(self, *_args) -> None:
        if not self._rand_wird_gesetzt:
            self._rand_von_hand = True

    def _papier_umgeschaltet(self, papier: bool) -> None:
        # Auf normalem Papier brauchen die Etiketten einen Druckrand, auf dem Bogen sitzen sie am Raster.
        if not self._rand_von_hand:
            self._rand_wird_gesetzt = True
            for box in (self.rand_links, self.rand_oben):
                box.setValue(10 if papier else 0)
            self._rand_wird_gesetzt = False
        self._hinweis_aktualisieren()

    def spalten_zeilen(self) -> tuple[int, int]:
        return (int((210 - self.rand_links.value() + 0.01) // self.breite.value()),
                int((297 - self.rand_oben.value() + 0.01) // self.hoehe.value()))

    def _hinweis_aktualisieren(self, *_args) -> None:
        spalten, zeilen = self.spalten_zeilen()
        self.hinweis.setText(
            f"{spalten} x {zeilen} = {spalten * zeilen} Etiketten je A4-Seite." if spalten and zeilen
            else "Das Etikett ist größer als die Seite.")
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(bool(spalten and zeilen))
