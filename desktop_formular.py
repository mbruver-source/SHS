"""
Reiter Formular-Import (ausgefüllte Anmeldeformulare und KI-Listen einlesen), seit 11.11.2026
aus app.py ausgelagert. Bewusst KEIN `import app` (siehe desktop_programm.py).
"""
from __future__ import annotations

import datetime
import os
import sqlite3

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from db import (
    termine_ordner,
)
from db_import import (
    CSV_IMPORT_SPALTEN,
    importiere_anmeldeformular_pdf,
    importiere_teilnehmer_aus_oma,
    schreibe_csv_vorlage,
)
from desktop_gemeinsam import zugaengliche_namen_setzen
from desktop_gemeinsam import (
    _klartext_fehler,
    _Ablageort,
    _anmeldeformular_pdf_speichern,
    _datei_gespeichert_melden,
    _import_ordner_merken,
    _import_startordner,
    symbol_setzen,
)
from desktop_import_meldungen import (
    _import_db_fehler_melden,
    _import_ergebnis_melden,
    _ohne_startnummer_ids,
    _startnummern_nach_import_anbieten,
    _teilnehmerliste_importieren,
    _teilnehmerzahl,
)


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
        "Formular: 'DK LK 1/2/3' -> art=DK, stufe=1/2/3, disziplin LEER lassen. "
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
    "Ausdrucke/Export") lässt sich ausgefüllt direkt einlesen - ganz ohne KI (siehe
    _anmeldeformulare_importieren)."""

    _KI_UMSCHALTER_TEXT = "Andere Meldeformulare (Foto, Scan, Word) über ein KI-System einlesen"

    def __init__(self, conn, parent=None, ablageort: _Ablageort | None = None):
        super().__init__(parent)
        self.conn = conn
        self._ablageort = ablageort if ablageort is not None else _Ablageort(str(termine_ordner()))

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
        # Marco 10.11.2026 (UI-Abgleich): das leere Formular lässt sich auch hier erzeugen,
        # nicht nur im Reiter „Ausdrucke/Export“.
        self.leeres_formular_btn = QPushButton("Leeres Anmeldeformular (PDF)…")
        self.leeres_formular_btn.setToolTip(
            "Das ausfüllbare Formular zum Verschicken an die Teilnehmer (wie im Reiter „Ausdrucke/Export“)")
        self.leeres_formular_btn.clicked.connect(self._leeres_formular_speichern)
        self.formular_status_label = QLabel("")
        self.formular_status_label.setTextFormat(Qt.PlainText)  # enthält Pfade
        self.formular_status_label.setWordWrap(True)

        import_btn = QPushButton("Teilnehmerliste einlesen (Excel/CSV)…")
        import_btn.clicked.connect(self._csv_importieren)
        vorlage_btn = QPushButton("Leere Vorlage (CSV) speichern…")
        vorlage_btn.clicked.connect(self._vorlage_speichern)

        oma_btn = QPushButton("OMA-Export importieren…")
        oma_btn.clicked.connect(self._oma_importieren)

        self._ki_bereich_aufbauen()
        self._letzter_import_aufbauen()
        zugaengliche_namen_setzen(self, {
            "prompt_feld": "Prompt für das KI-System (zum Kopieren)",
            "letzter_import_text": "Ergebnis des letzten Imports",
        })

        layout = QVBoxLayout(self)
        layout.addWidget(abschnitt(
            "1. Ausgefüllte Anmeldeformulare (PDF) – empfohlen",
            "Das Anmeldeformular erzeugst du im Reiter „Ausdrucke/Export“ und verschickst es an die "
            "Teilnehmer. Die ausgefüllt zurückgeschickten PDF-Dateien hier einlesen – mehrere "
            "auf einmal möglich, bereits vorhandene Meldungen werden übersprungen.",
            anmeldeformular_btn, self.leeres_formular_btn,
        ))
        layout.addWidget(self.formular_status_label)
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
        layout.addWidget(self.letzter_import)
        layout.addWidget(self._ki_umschalter)
        layout.addWidget(self._ki_bereich, 1)
        layout.addStretch()

    def _ki_bereich_aufbauen(self) -> None:
        """Eingeklappter Bereich „Mit KI-System einlesen“ (Prompt, Anleitung, Umschalter)."""
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
        self._ki_umschalter = QPushButton(self._KI_UMSCHALTER_TEXT)
        symbol_setzen(self._ki_umschalter, "chevron-right")
        self._ki_umschalter.setCheckable(True)
        self._ki_umschalter.setFlat(True)
        # setFlat allein wirkt nicht, die allgemeine QPushButton-Regel des Stylesheets malt
        # sonst Fläche und Rahmen (Marco 01.11.2026) - deshalb hier ausdrücklich ohne beides.
        self._ki_umschalter.setStyleSheet(
            "QPushButton { text-align: left; background: transparent; border: none; padding: 4px 2px; }"
            "QPushButton:hover { text-decoration: underline; }"
        )
        self._ki_umschalter.toggled.connect(self._ki_bereich_umschalten)

    def _letzter_import_aufbauen(self) -> None:
        # UX-Test 2026-11, T2: Ergebnis des letzten Imports (bis zum nächsten bzw. bis zum
        # Terminwechsel, nur im Speicher), siehe _letzten_import_zeigen.
        self.letzter_import = QGroupBox("Letzter Import")
        self.letzter_import_text = QPlainTextEdit()
        self.letzter_import_text.setReadOnly(True)
        self.letzter_import_text.setMaximumHeight(160)
        letzter_kopieren_btn = QPushButton("Kopieren")
        letzter_kopieren_btn.setToolTip("Den ganzen Text z. B. in eine E-Mail an die Teilnehmer einfügen.")
        letzter_kopieren_btn.clicked.connect(self._letzten_import_kopieren)
        self.letzter_import_status = QLabel("")
        letzter_zeile = QHBoxLayout()
        letzter_zeile.addWidget(letzter_kopieren_btn)
        letzter_zeile.addWidget(self.letzter_import_status)
        letzter_zeile.addStretch()
        letzter_layout = QVBoxLayout(self.letzter_import)
        letzter_layout.addWidget(self.letzter_import_text)
        letzter_layout.addLayout(letzter_zeile)
        self.letzter_import.setVisible(False)

    def _prompt_kopieren(self) -> None:
        QApplication.clipboard().setText(self.prompt_feld.toPlainText())
        self.status_label.setText("Prompt kopiert.")

    def letzten_import_zeigen(self, text: str) -> None:
        uhrzeit = datetime.datetime.now().strftime("%H:%M")
        self.letzter_import.setTitle(f"Letzter Import ({uhrzeit} Uhr)")
        self.letzter_import_text.setPlainText(text)
        self.letzter_import_status.setText("")
        self.letzter_import.setVisible(True)

    def _letzten_import_kopieren(self) -> None:
        QApplication.clipboard().setText(self.letzter_import_text.toPlainText())
        self.letzter_import_status.setText("Kopiert.")

    def _csv_importieren(self) -> None:
        _teilnehmerliste_importieren(self, self.conn)

    def _leeres_formular_speichern(self) -> None:
        _anmeldeformular_pdf_speichern(self, self.conn, self._ablageort, self.formular_status_label)

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
        symbol_setzen(self._ki_umschalter, "chevron-down" if sichtbar else "chevron-right")

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
        vorher_ohne = _ohne_startnummer_ids(self.conn)
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
            _startnummern_nach_import_anbieten(self, self.conn, vorher_ohne)

    def _anmeldeformulare_importieren(self) -> None:
        """Liest ausgefüllte Anmeldeformulare (siehe pdf_export.erstelle_anmeldeformular_pdf)
        über db_import.importiere_anmeldeformular_pdf ein - eine Datei je Meldung, mehrere
        Dateien auf einmal wählbar (Nutzerwunsch 28.09.2026)."""
        pfade, _ = QFileDialog.getOpenFileNames(
            # UX-Test 03.11.2026, X15: dass mehrere Dateien auf einmal gehen, stand nirgends.
            self, "Anmeldeformulare importieren (mehrere mit Strg-Klick markieren)", _import_startordner(),
            "Anmeldeformular (*.pdf)"
        )
        if not pfade:
            return
        _import_ordner_merken(pfade[0])
        # Lesefehler je Datei fängt der Import selbst ab und meldet sie in ergebnis.fehler
        # (Verifikation 28.09.2026, Befund 7a); hier bleiben nur Schreibfehler der Termin-Datei.
        vorher = _teilnehmerzahl(self.conn)
        vorher_ohne = _ohne_startnummer_ids(self.conn)
        try:
            ergebnis = importiere_anmeldeformular_pdf(self.conn, pfade)
        except sqlite3.Error as exc:
            _import_db_fehler_melden(self, exc, self.conn, vorher)
            self.aktualisieren()
            return
        _import_ergebnis_melden(self, ergebnis, "Datei(en) nicht importiert:")
        if ergebnis.importiert:
            _startnummern_nach_import_anbieten(self, self.conn, vorher_ohne)
