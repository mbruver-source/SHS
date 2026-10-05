"""Geführte Demoprüfung (Marcos Wunsch 04.10.2026): Das Programm spielt einmal einen
kompletten Prüfungstag mit erfundenen Daten vor - Termin anlegen, Teilnehmer, Startnummern,
Bezahlt, Zeitplan, Ergebnisse, Auswertung, Stechen, Ergebnisliste - und erklärt in einem
kleinen Fenster je Schritt, was gerade passiert und warum. Der Anwender klickt nur „Weiter“
- oder lässt die Demo laufen: Ist ein Schritt fertig, geht es nach 10 Sekunden von allein
weiter (Marcos Wunsch 05.10.2026, abschaltbar über „Automatisch weiter“).

Sicherheit der echten Daten: Die Demo arbeitet ausschließlich in einem eigenen
Temp-Ordner (tempfile.mkdtemp, nie im Termine-Ordner) und löscht ihn am Ende wieder. Der
Reiter "Datensicherung" (arbeitet immer auf dem echten Termine-Ordner) ist währenddessen
gesperrt (siehe HauptFenster._termin_setzen).

Bewusst KEIN `import app`: Läuft das Programm als `python app.py` bzw. als EXE, lebt das
Hauptfenster im Modul `__main__` - ein `import app` würde eine zweite, getrennte Kopie
aller Klassen laden. Das Hauptfenster (bzw. für den Start aus dem Startdialog eine
Fenster-Fabrik) wird deshalb übergeben; die Reiter-Methoden werden über diese Instanz
aufgerufen.

Die Demo umgeht alle modalen Rückfragen und Meldungsfenster der Reiter (die würden den
Ablauf blockieren) und zeigt das Ergebnis stattdessen im Erklärfenster.
"""

from __future__ import annotations

import datetime
import os
import random
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import shiboken6
from PySide6.QtCore import QEvent, QEventLoop, QObject, QPoint, QRect, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import demo_daten
import pdf_export
from db import (
    NeuerTeilnehmer,
    add_teilnehmer,
    automatische_zeitplan_verteilung,
    berechne_auswertung,
    dateiname_vorschlagen,
    fehlende_startnummern_vergeben,
    get_veranstaltung,
    init_db,
    list_zeitplan_richter,
    set_veranstaltung,
    setze_stechen_sieger,
    startnummer_bereiche,
    termine_ordner,
    vergebene_startnummern,
    zeitplan_richter_aus_veranstaltung_anlegen,
)
from desktop_dialoge import TeilnehmerDialog, VeranstaltungsDialog
from desktop_gemeinsam import _ausdrucke_ordner, _export_dateiname, _pfad_anzeige

#: Präfix der Temp-Ordner - alte Reste (z. B. nach einem Absturz) werden beim nächsten
#: Start aufgeräumt, siehe demo_reste_aufraeumen.
DEMO_ORDNER_PRAEFIX = "shs_demo_"


class DemoFehler(Exception):
    """Ein Schritt ließ sich nicht vorführen (z. B. weil im Dialog etwas geändert wurde) -
    der Text erscheint im Erklärfenster."""


@dataclass
class DemoSchritt:
    titel: str
    text: str
    #: Liefert beim Betreten des Schritts die einzelnen Teilaktionen, die nacheinander
    #: (mit kurzer Pause, damit man zusehen kann) ausgeführt werden.
    aktionen: Callable[[], list[Callable[[], None]]] | None = None


def demo_reste_aufraeumen(alter_sekunden: int = 3600) -> None:
    """Löscht Demo-Temp-Ordner früherer Läufe (z. B. wenn eine PDF beim Beenden noch
    geöffnet war und der Ordner deshalb liegen blieb). Läuft bei jedem Programmstart (siehe
    app.main) und vor jeder Demo. Nur Ordner, die älter als eine Stunde sind - eine gerade
    laufende Demo in einem zweiten Programmfenster bleibt so unangetastet."""
    grenze = time.time() - alter_sekunden
    try:
        eintraege = list(Path(tempfile.gettempdir()).glob(f"{DEMO_ORDNER_PRAEFIX}*"))
    except OSError:
        return
    for ordner in eintraege:
        try:
            if ordner.is_dir() and ordner.stat().st_mtime < grenze:
                shutil.rmtree(ordner, ignore_errors=True)
        except OSError:
            continue


def _liegt_im_termine_ordner(pfad: str) -> bool:
    try:
        Path(pfad).resolve().relative_to(termine_ordner().resolve())
        return True
    except ValueError:
        return False


def _lebt(objekt) -> bool:
    return objekt is not None and shiboken6.isValid(objekt)


class DemoMarkierung(QWidget):
    """Farbiger Rahmen um das Element, an dem die Demo gerade arbeitet. Selbst gezeichnet
    (Akzentfarbe aus der Palette) statt per Stylesheet, damit die Stylesheets der Reiter
    (z. B. gelbe ungespeicherte Zeilen) und die Design-Tests unberührt bleiben. Lässt
    Mausklicks durch und folgt dem Ziel, falls es sich verschiebt."""

    RAND = 4

    def __init__(self, ziel: QWidget):
        super().__init__(ziel.window())
        self._ziel = ziel
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self._timer = QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self.ausrichten)
        self._timer.start()
        self.ausrichten()

    def ausrichten(self) -> None:
        ziel = self._ziel
        fenster = self.parentWidget()
        if not _lebt(ziel) or fenster is None or not ziel.isVisible() or ziel.window() is not fenster:
            self.hide()
            return
        oben_links = ziel.mapTo(fenster, QPoint(0, 0))
        r = self.RAND
        self.setGeometry(QRect(oben_links, ziel.size()).adjusted(-r, -r, r, r))
        self.show()
        self.raise_()

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        maler = QPainter(self)
        maler.setRenderHint(QPainter.Antialiasing)
        maler.setPen(QPen(self.palette().color(QPalette.Highlight), 3))
        maler.setBrush(Qt.NoBrush)
        maler.drawRoundedRect(QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5), 6, 6)

    def entfernen(self) -> None:
        self._timer.stop()
        self.hide()
        self.deleteLater()


class DemoPanel(QWidget):
    """Nicht-modales Erklärfenster der Demo: Schritt-Zähler, Überschrift, Erklärung und
    die Knöpfe „Weiter“/„Beenden“ (optional ein Zusatzknopf, z. B. „PDF öffnen“). Alle
    Texte als reiner Text (S-1: nie als HTML deuten)."""

    weiter_geklickt = Signal()
    beenden_geklickt = Signal()
    auto_weiter_umgeschaltet = Signal(bool)

    def __init__(self, parent: QWidget):
        super().__init__(parent, Qt.Tool)
        self.setWindowTitle("🎓 Demoprüfung")
        self._schliessen_erlaubt = False
        self._extra_aktion: Callable[[], None] | None = None
        self._letzter = False

        self.schritt_label = QLabel()
        self.titel_label = QLabel()
        schrift = QFont(self.titel_label.font())
        schrift.setBold(True)
        schrift.setPointSizeF(schrift.pointSizeF() * 1.25)
        self.titel_label.setFont(schrift)
        self.text_label = QLabel()
        self.hinweis_label = QLabel()
        # Eigene Zeile statt hinweis_label (das z. B. den Speicherort der PDF zeigt).
        self.pause_label = QLabel("Automatisch weiter angehalten – weiter mit „Weiter ▶“.")
        self.pause_label.setVisible(False)
        for label in (self.schritt_label, self.titel_label, self.text_label, self.hinweis_label, self.pause_label):
            label.setTextFormat(Qt.PlainText)
            label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.hinweis_label.setVisible(False)

        self.extra_btn = QPushButton()
        self.extra_btn.setVisible(False)
        self.extra_btn.clicked.connect(self._extra_ausfuehren)
        # Automatisch weiter (Marcos Wunsch 05.10.2026): gilt für die ganze Demo, wird
        # nicht über sie hinaus gespeichert.
        self.auto_box = QCheckBox("Automatisch weiter")
        self.auto_box.setChecked(True)
        self.auto_box.setToolTip(
            f"Ist ein Schritt fertig, geht es nach {DemoTour.AUTO_WEITER_S} Sekunden von allein weiter."
        )
        self.auto_box.toggled.connect(self.auto_weiter_umgeschaltet)
        self.beenden_btn = QPushButton("Beenden")
        self.beenden_btn.setToolTip("Demo abbrechen – der Demo-Termin wird gelöscht.")
        self.beenden_btn.clicked.connect(self.beenden_geklickt)
        self.weiter_btn = QPushButton("Weiter ▶")
        self.weiter_btn.setObjectName("primaerButton")  # siehe _QSS_TEMPLATE
        self.weiter_btn.setDefault(True)
        self.weiter_btn.clicked.connect(self.weiter_geklickt)

        knopf_zeile = QHBoxLayout()
        knopf_zeile.addWidget(self.extra_btn)
        knopf_zeile.addWidget(self.auto_box)
        knopf_zeile.addStretch()
        knopf_zeile.addWidget(self.beenden_btn)
        knopf_zeile.addWidget(self.weiter_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self.schritt_label)
        layout.addWidget(self.titel_label)
        layout.addWidget(self.text_label, 1)
        layout.addWidget(self.hinweis_label)
        layout.addWidget(self.pause_label)
        layout.addLayout(knopf_zeile)
        self.setMinimumWidth(440)
        self.resize(480, 320)
        self._positioniert = False

    def anzeigen(self, nummer: int, anzahl: int, schritt: DemoSchritt, letzter: bool) -> None:
        # Nummer 0 = Begrüßung; die übrigen Schritte tragen ihre Nummer auch im Titel.
        self.schritt_label.setText(f"Schritt {nummer} von {anzahl}" if nummer else "Einführung")
        self.titel_label.setText(schritt.titel)
        self.text_label.setText(schritt.text)
        self.hinweis(None)
        self.extra(None)
        self._letzter = letzter
        self.countdown_anzeigen(None)
        self.angehalten_anzeigen(False)
        self.weiter_btn.setEnabled(True)
        self.adjustSize()
        if not self._positioniert:
            self._positioniert = True
            self._in_ecke_setzen(rechts=True)
        self.show()
        self.raise_()

    def countdown_anzeigen(self, sekunden: int | None) -> None:
        """Knopftext „Weiter ▶ (n)“ während des Countdowns, sonst „Weiter ▶“ bzw. im
        letzten Schritt „Fertig ✔“ (dort gibt es keinen Countdown)."""
        if self._letzter:
            self.weiter_btn.setText("Fertig ✔")
        elif sekunden is None:
            self.weiter_btn.setText("Weiter ▶")
        else:
            self.weiter_btn.setText(f"Weiter ▶ ({sekunden})")

    def angehalten_anzeigen(self, angehalten: bool) -> None:
        self.pause_label.setVisible(angehalten)

    def hinweis(self, text: str | None) -> None:
        self.hinweis_label.setText(text or "")
        self.hinweis_label.setVisible(bool(text))

    def extra(self, beschriftung: str | None, aktion: Callable[[], None] | None = None) -> None:
        self._extra_aktion = aktion
        self.extra_btn.setText(beschriftung or "")
        self.extra_btn.setVisible(bool(beschriftung))

    def fehler(self, text: str) -> None:
        self.hinweis(text)
        self.weiter_btn.setEnabled(False)

    def ausweichen(self, ziel: QWidget | None) -> None:
        """Rückt das Fenster in die andere untere Ecke, wenn es das markierte Element
        verdeckt."""
        if not _lebt(ziel) or not ziel.isVisible() or not self.isVisible():
            return
        ziel_rechteck = QRect(ziel.mapToGlobal(QPoint(0, 0)), ziel.size())
        if self.frameGeometry().intersects(ziel_rechteck):
            bildschirm = self.screen().availableGeometry()
            self._in_ecke_setzen(rechts=self.frameGeometry().center().x() < bildschirm.center().x())

    def _in_ecke_setzen(self, rechts: bool) -> None:
        bildschirm = (self.parentWidget() or self).screen().availableGeometry()
        groesse = self.frameGeometry().size()
        x = bildschirm.right() - groesse.width() - 24 if rechts else bildschirm.left() + 24
        y = bildschirm.bottom() - groesse.height() - 48
        self.move(max(bildschirm.left(), x), max(bildschirm.top(), y))

    def _extra_ausfuehren(self) -> None:
        if self._extra_aktion is not None:
            self._extra_aktion()

    def schliessen(self) -> None:
        self._schliessen_erlaubt = True
        self.close()
        self.deleteLater()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        # Schließen über das X des Fensters = Demo beenden.
        if not self._schliessen_erlaubt:
            self.beenden_geklickt.emit()
        event.accept()


# Tasten, die allein keine Eingabe sind (siehe DemoTour.eventFilter).
_NUR_UMSCHALTTASTEN = frozenset(
    (Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Meta, Qt.Key.Key_AltGr, Qt.Key.Key_CapsLock)
)


class DemoTour(QObject):
    """Steuert die Demo: legt den Demo-Termin im Temp-Ordner an, führt die Schritte aus
    und räumt am Ende (oder bei „Beenden“/Fenster schließen) alles wieder ab.

    Zwei Einstiege:
    - aus dem Hauptfenster (`fenster`): der bisher geöffnete Termin bleibt offen und wird
      am Ende wiederhergestellt;
    - aus dem Startdialog (`fenster_fabrik`, noch kein Termin offen): die Demo öffnet ein
      eigenes Hauptfenster und schließt es am Ende wieder."""

    beendet = Signal()

    #: Tempo wie von Hand (Marcos Wunsch 04.10.2026): Texte werden Zeichen für Zeichen
    #: getippt, zwischen zwei Arbeitsschritten (Feld wechseln, Teilnehmer anlegen, Knopf)
    #: gibt es eine kurze Pause. TEMPO skaliert alle Pausen - Tests setzen 0, dann läuft
    #: alles sofort. „Weiter“ führt einen laufenden Schritt jederzeit sofort zu Ende.
    TEMPO = 1.0
    PAUSE_MS = 600
    #: Automatisch weiter (Marcos Wunsch 05.10.2026): so viele Sekunden nach dem Ende eines
    #: Schritts (alle Aktionen ausgeführt) geht es von allein weiter; 0 = aus (Tests).
    AUTO_WEITER_S = 10
    #: Nach einem geschlossenen sperrenden Fenster bleiben mindestens so viele Sekunden.
    AUTO_WEITER_NACH_MODAL_S = 3
    TASTE_MS = (55, 140)  # je Zeichen, leicht schwankend wie beim echten Tippen

    def __init__(self, fenster=None, fenster_fabrik=None):
        super().__init__()
        if fenster is None and fenster_fabrik is None:
            raise ValueError("DemoTour braucht ein Hauptfenster oder eine Fenster-Fabrik")
        self._fenster = fenster
        self._fenster_fabrik = fenster_fabrik
        self.eigenes_fenster = fenster is None
        self._ordner: Path | None = None
        self.pfad: str | None = None
        self.conn = None
        self._alt_conn = None
        self._alt_pfad: str | None = None
        self._alt_tab = 0
        self._panel: DemoPanel | None = None
        self._dialog: QDialog | None = None
        self._markierung: DemoMarkierung | None = None
        self._ziel: QWidget | None = None
        self._ids: dict[str, int] = {}
        self._schritte: list[DemoSchritt] = []
        self._index = -1
        self._offen: list[Callable[[], None]] = []
        self.ist_beendet = False
        self._sofort = False  # siehe _alles_sofort
        self.pdf_pfad: str | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._naechste_aktion)
        self._countdown = QTimer(self)
        self._countdown.setInterval(1000)
        self._countdown.timeout.connect(self._countdown_tick)
        self._rest = 0
        self._modal_wartet = False  # siehe _countdown_tick
        # Für den laufenden Schritt angehalten („PDF öffnen“, eigene Eingabe im Demo-Dialog).
        self._angehalten = False

    # --- Start / Ende ---------------------------------------------------------

    def starten(self) -> None:
        demo_reste_aufraeumen()
        self._ordner = Path(tempfile.mkdtemp(prefix=DEMO_ORDNER_PRAEFIX))
        try:
            self._starten()
        except Exception:
            # Verifikation 04.10.2026, Befund 2: auch bei einem Fehler beim Start keine
            # offene Verbindung und keinen Temp-Ordner zurücklassen.
            self.beenden()
            raise

    def _starten(self) -> None:
        datum = datetime.date.today().isoformat()
        self.pfad = str(self._ordner / dateiname_vorschlagen(demo_daten.VERANSTALTUNG["verein"], datum))
        if _liegt_im_termine_ordner(self.pfad):  # darf nie passieren - echte Termine schützen
            raise RuntimeError("Demo-Termin läge im Termine-Ordner - Demo abgebrochen.")
        self.conn = init_db(self.pfad)

        if self.eigenes_fenster:
            self._fenster = self._fenster_fabrik(self.conn, self.pfad, demo=True)
            self._fenster.showMaximized()
        else:
            self._alt_conn = self._fenster.conn
            self._alt_pfad = self._fenster.pfad
            self._alt_tab = self._fenster._tabs.currentIndex()
        self._fenster._demo_tour = self
        self._fenster._demo_sperren(True)

        self._panel = DemoPanel(self._fenster)
        self._panel.weiter_geklickt.connect(self.weiter)
        self._panel.beenden_geklickt.connect(self.beenden)
        self._panel.auto_weiter_umgeschaltet.connect(self._auto_weiter_umgeschaltet)
        # Eigene Eingaben im Demo-Dialog erkennen (siehe eventFilter).
        QApplication.instance().installEventFilter(self)
        self._schritte = self._schritte_aufbauen()
        self._schritt_zeigen(0)

    def panel_zeigen(self) -> None:
        if _lebt(self._panel):
            self._panel.show()
            self._panel.raise_()
            self._panel.activateWindow()

    def weiter(self) -> None:
        if self.ist_beendet:
            return
        self._countdown_stoppen()
        # Läuft der aktuelle Schritt noch, wird er sofort zu Ende geführt.
        self._alles_sofort()
        if self.ist_beendet or (self._panel is not None and not self._panel.weiter_btn.isEnabled()):
            return
        if self._index + 1 >= len(self._schritte):
            self.beenden()
            return
        self._schritt_zeigen(self._index + 1)

    def beenden(self) -> None:
        """Bricht ab bzw. schließt die Demo ab: stellt den vorherigen Termin wieder her
        (bzw. schließt das Demo-Fenster) und löscht den Demo-Termin samt Ausdrucken.
        Mehrfacher Aufruf ist unschädlich."""
        if self.ist_beendet:
            return
        self.ist_beendet = True
        self._timer.stop()
        self._countdown.stop()
        if QApplication.instance() is not None:
            QApplication.instance().removeEventFilter(self)
        self._offen.clear()
        fenster = self._fenster if _lebt(self._fenster) else None
        try:
            self._markieren(None)
            self._dialog_schliessen()
            if fenster is not None:
                fenster._demo_tour = None
                if self.eigenes_fenster:
                    fenster.hide()
                    fenster.deleteLater()
                else:
                    if fenster.conn is self.conn and self._alt_conn is not None:
                        fenster._termin_setzen(self._alt_conn, self._alt_pfad)
                        fenster._tabs.setCurrentIndex(self._alt_tab)
        finally:
            # Gegenprüfung 04.10.2026, Befund 4: Knöpfe auch nach einem Fehler oben wieder
            # freigeben, sonst bliebe der Terminwechsel bis zum Neustart gesperrt.
            if fenster is not None and not self.eigenes_fenster and _lebt(fenster):
                fenster._demo_sperren(False)
            # Verifikation 04.10.2026, Befund 2: Aufräumen auch dann, wenn oben etwas
            # schiefgeht - sonst blieben Verbindung, Temp-Ordner und Erklärfenster zurück.
            if self.conn is not None:
                try:
                    self.conn.close()  # unter Windows Voraussetzung für das Löschen
                except Exception:  # noqa: BLE001
                    pass
            rest_geblieben = False
            if self._ordner is not None:
                shutil.rmtree(self._ordner, ignore_errors=True)
                # Z. B. eine noch im PDF-Programm geöffnete Ergebnisliste (Windows sperrt sie).
                rest_geblieben = self._ordner.exists()
            if fenster is not None and not self.eigenes_fenster and _lebt(fenster):
                fenster.statusBar().showMessage(
                    "Demoprüfung beendet – der Demo-Termin wurde gelöscht."
                    + (" Eine noch geöffnete Datei wird beim nächsten Programmstart aufgeräumt." if rest_geblieben else ""),
                    10000,
                )
            if _lebt(self._panel):
                self._panel.schliessen()
            self.beendet.emit()

    # --- Ablauf ----------------------------------------------------------------

    def _schritt_zeigen(self, index: int) -> None:
        self._countdown_stoppen()
        self._angehalten = False
        self._index = index
        schritt = self._schritte[index]
        self._panel.anzeigen(index, len(self._schritte) - 1, schritt, index == len(self._schritte) - 1)
        self._offen = []
        if schritt.aktionen is not None:
            try:
                self._offen = list(schritt.aktionen())
            except Exception as exc:  # noqa: BLE001 - jeder Fehler erscheint im Erklärfenster
                self._fehler_zeigen(exc)
                return
        self._naechste_aktion()

    def _naechste_aktion(self) -> None:
        while self._offen and not self.ist_beendet:
            aktion = self._offen.pop(0)
            try:
                aktion()
            except Exception as exc:  # noqa: BLE001
                self._fehler_zeigen(exc)
                return
            pause = 0 if self._sofort else int(getattr(aktion, "pause_ms", self.PAUSE_MS) * self.TEMPO)
            if self._offen and pause > 0:
                self._timer.start(pause)
                return
        if not self.ist_beendet:
            self._panel_ausweichen()
            self._countdown_starten()

    def _alles_sofort(self) -> None:
        # Eigener Merker statt TEMPO zu überschreiben - sonst bliebe TEMPO danach als
        # Instanzattribut hängen und eine spätere Änderung an DemoTour.TEMPO wirkte nicht.
        self._timer.stop()
        self._sofort = True
        try:
            self._naechste_aktion()
        finally:
            self._sofort = False

    def _fehler_zeigen(self, exc: Exception) -> None:
        self._offen.clear()
        self._timer.stop()
        self._countdown_stoppen()
        text = str(exc) if isinstance(exc, DemoFehler) else f"Dieser Schritt ließ sich nicht vorführen: {exc}"
        if _lebt(self._panel):
            self._panel.fehler(text + "\n\nBitte „Beenden“ drücken – der Demo-Termin wird dabei gelöscht.")

    # --- Automatisch weiter (Marcos Wunsch 05.10.2026) ------------------------

    def _countdown_starten(self) -> None:
        """Startet nach einem fertigen Schritt den Countdown bis zum automatischen
        „Weiter“ - nicht im letzten Schritt, nicht nach einem Fehler (Knopf gesperrt) und
        nicht bei abgehaktem „Automatisch weiter“."""
        self._countdown.stop()
        if (
            self.ist_beendet
            or self.AUTO_WEITER_S <= 0
            or not _lebt(self._panel)
            or self._index + 1 >= len(self._schritte)
            or not self._panel.weiter_btn.isEnabled()
            or not self._panel.auto_box.isChecked()
            or self._angehalten
        ):
            return
        self._rest = self.AUTO_WEITER_S
        self._modal_wartet = False
        self._panel.countdown_anzeigen(self._rest)
        self._countdown.start()

    def _countdown_stoppen(self) -> None:
        self._countdown.stop()
        self._modal_wartet = False
        if _lebt(self._panel):
            self._panel.countdown_anzeigen(None)

    def _countdown_tick(self) -> None:
        # Hat der Anwender selbst ein sperrendes Fenster offen (Meldung, Teilnehmer
        # bearbeiten …), wartet die Demo - sonst liefe sie darunter ungesehen weiter und das
        # Erklärfenster wäre gesperrt (Verifikation 05.10.2026). Die eigenen Dialoge der
        # Demo sind nicht-modal und stören hier nicht.
        if QApplication.activeModalWidget() is not None:
            # Danach nicht fast ohne Vorwarnung weiterschalten (Verifikation 05.10.2026).
            self._modal_wartet = True
            if self._rest < self.AUTO_WEITER_NACH_MODAL_S:
                self._rest = self.AUTO_WEITER_NACH_MODAL_S
                if _lebt(self._panel):
                    self._panel.countdown_anzeigen(self._rest)
            return
        if self._modal_wartet:
            # Erster Tick nach dem Schließen: Takt neu starten statt zu zählen, damit
            # wirklich volle AUTO_WEITER_NACH_MODAL_S Sekunden bleiben.
            self._modal_wartet = False
            self._countdown.start()
            return
        self._rest -= 1
        if self._rest <= 0:
            self._countdown_stoppen()
            self.weiter()
        elif _lebt(self._panel):
            self._panel.countdown_anzeigen(self._rest)

    def _auto_weiter_umgeschaltet(self, an: bool) -> None:
        # Bewusst wieder angehakt hebt auch ein Anhalten auf; neu gestartet wird aber nur,
        # wenn der aktuelle Schritt schon fertig ist.
        self._angehalten = False
        if _lebt(self._panel):
            self._panel.angehalten_anzeigen(False)
        if an and not self._offen:
            self._countdown_starten()
        else:
            self._countdown_stoppen()

    def _countdown_anhalten(self) -> None:
        """Hält das automatische Weiter für den laufenden Schritt an und sagt das im
        Erklärfenster (nur, wenn es überhaupt eingeschaltet ist)."""
        if self._angehalten or self.ist_beendet or not _lebt(self._panel):
            return
        self._angehalten = True
        self._countdown_stoppen()
        letzter = self._index + 1 >= len(self._schritte)
        if self._panel.auto_box.isChecked() and self.AUTO_WEITER_S > 0 and not letzter:
            self._panel.angehalten_anzeigen(True)

    def _pdf_oeffnen(self, ziel: str) -> None:
        # Beim Anschauen der PDF soll die Demo nicht weiterlaufen.
        self._countdown_anhalten()
        QDesktopServices.openUrl(QUrl.fromLocalFile(ziel))

    def eventFilter(self, obj, event) -> bool:  # type: ignore[override]
        """Tippt oder klickt der Anwender selbst in einen Dialog der Demo (Termin in
        Schritt 1, Teilnehmer in Schritt 3), hält das automatische Weiter an - sonst griffe
        es mitten in seine Eingabe ein. Die Demo selbst erzeugt keine Tasten- oder
        Mausereignisse (sie setzt Texte direkt), daher reicht die Art des Ereignisses.
        Reine Umschalttasten (Alt, Strg, Umschalt …, z. B. für Alt+Tab) zählen nicht."""
        typ = event.type()
        if typ == QEvent.KeyPress and event.key() in _NUR_UMSCHALTTASTEN:
            return False
        if (
            typ in (QEvent.KeyPress, QEvent.MouseButtonPress)
            and _lebt(self._dialog)
            and isinstance(obj, QWidget)
            and (obj is self._dialog or self._dialog.isAncestorOf(obj))
        ):
            self._countdown_anhalten()
        return False

    # --- Hilfsfunktionen ------------------------------------------------------

    def _markieren(self, ziel: QWidget | None) -> None:
        if _lebt(self._markierung):
            self._markierung.entfernen()
        self._markierung = None
        self._ziel = ziel
        if _lebt(ziel):
            self._sichtbar_machen(ziel)
            self._markierung = DemoMarkierung(ziel)

    def _panel_ausweichen(self) -> None:
        if _lebt(self._panel):
            self._panel.ausweichen(self._ziel if _lebt(self._ziel) else None)

    @staticmethod
    def _sichtbar_machen(widget: QWidget) -> None:
        """Scrollt umgebende Bereiche (Dialog-Inhalt, Tabellen) so, dass das Element zu
        sehen ist."""
        eltern = widget.parentWidget()
        while eltern is not None:
            if isinstance(eltern, QScrollArea) and eltern.widget() is not None and eltern.widget().isAncestorOf(widget):
                eltern.ensureWidgetVisible(widget)
            eltern = eltern.parentWidget()

    def _reiter_zeigen(self, widget: QWidget) -> None:
        """Wechselt den Reiter - vorher ungespeicherte Ergebnisse speichern, damit die
        Rückfrage „Jetzt speichern?“ beim Verlassen der Ergebniserfassung nicht erscheint."""
        fenster = self._fenster
        if fenster.ergebnis_tab.hat_ungespeicherte_aenderungen():
            fenster.ergebnis_tab.alle_speichern()
        fenster._tabs.setCurrentWidget(widget)

    def _dialog_zeigen(self, dialog: QDialog) -> None:
        """Zeigt einen Dialog der Demo nicht-modal; OK/Abbrechen sind gesperrt, weil die
        Demo selbst weitermacht."""
        self._dialog_schliessen()
        self._dialog = dialog
        knoepfe = dialog.findChild(QDialogButtonBox)
        if knoepfe is not None:
            knoepfe.setEnabled(False)
        dialog.show()
        bildschirm = self._fenster.screen().availableGeometry()
        dialog.move(bildschirm.left() + 40, bildschirm.top() + 40)
        if _lebt(self._panel):
            self._panel.raise_()

    def _dialog_ok_knopf(self) -> QWidget | None:
        knoepfe = self._dialog.findChild(QDialogButtonBox) if _lebt(self._dialog) else None
        return knoepfe.button(QDialogButtonBox.Ok) if knoepfe is not None else None

    def _dialog_schliessen(self) -> None:
        if _lebt(self._dialog):
            self._dialog.hide()
            self._dialog.deleteLater()
        self._dialog = None

    def _eintragen(self, feld: QWidget, wert) -> list[Callable[[], None]]:
        """Teilaktionen für ein Feld: markieren, dann Texte Zeichen für Zeichen tippen
        (Auswahllisten und Haken in einem Schritt)."""
        if not isinstance(feld, (QLineEdit, QPlainTextEdit)):
            def waehlen() -> None:
                self._markieren(feld)
                if isinstance(feld, QComboBox):
                    feld.setCurrentText(wert)
                else:  # Checkbox
                    feld.setChecked(wert)
            return [waehlen]

        setzen = feld.setText if isinstance(feld, QLineEdit) else feld.setPlainText

        def fokus() -> None:
            self._markieren(feld)
            setzen("")
        fokus.pause_ms = self.PAUSE_MS // 2

        aktionen: list[Callable[[], None]] = [fokus]
        for laenge in range(1, len(wert) + 1):
            taste = (lambda teil=wert[:laenge]: setzen(teil))
            taste.pause_ms = random.randint(*self.TASTE_MS)
            aktionen.append(taste)
        aktionen[-1].pause_ms = self.PAUSE_MS
        return aktionen

    def _markieren_aktion(self, ziel_fn: Callable[[], QWidget | None]) -> Callable[[], None]:
        return lambda: self._markieren(ziel_fn())

    # --- Die einzelnen Schritte ----------------------------------------------

    def _schritte_aufbauen(self) -> list[DemoSchritt]:
        zurueck = (
            "Danach bist du wieder in deinem vorherigen Termin."
            if not self.eigenes_fenster else "Danach siehst du wieder den Startbildschirm."
        )
        return [
            DemoSchritt(
                "Willkommen zur Demoprüfung",
                "Die Demo spielt einen kompletten Prüfungstag einmal vor: vom Anlegen des "
                "Termins über Teilnehmer, Zeitplan und Ergebnisse bis zur Ergebnisliste.\n\n"
                "Das Programm klickt und tippt selbst. Ist ein Schritt fertig, geht es nach "
                f"{self.AUTO_WEITER_S} Sekunden von allein weiter – oder du drückst „Weiter“. Wer selbst "
                "bestimmen will, nimmt den Haken bei „Automatisch weiter“ heraus. Ein farbiger "
                "Rahmen zeigt jeweils, wo gerade gearbeitet wird. Wer es eilig hat: „Weiter“ "
                "füllt einen laufenden Schritt sofort fertig aus.\n\n"
                "Alle Namen und Daten sind erfunden. Der Demo-Termin liegt in einem "
                "temporären Ordner und wird am Ende gelöscht – deine echten Termine bleiben "
                "unberührt. „Beenden“ bricht jederzeit ab.",
            ),
            DemoSchritt(
                "1. Neuen Termin anlegen",
                "Jede Prüfung beginnt mit einem Termin. Im Startbildschirm öffnet „Neuen "
                "Termin anlegen…“ dieses Fenster.\n\n"
                "Pflicht sind nur Verein und Datum – daraus entsteht der Dateiname. Richter "
                "und Prüfungsleiter erscheinen später im Zeitplan und auf den Ausdrucken. "
                "Verband und Meldestelle stehen im Kopf des Anmeldeformulars.\n\n"
                "„Angebotene Prüfungen“ legt fest, was die Teilnehmer auf dem Anmeldeformular "
                "ankreuzen können. Die Startnummern-Bereiche sorgen dafür, dass man jeder "
                "Nummer ansieht, zu welcher Prüfung sie gehört.\n\n"
                "Normalerweise liegt die Termin-Datei im Termine-Ordner – die Demo nutzt "
                "einen temporären Ordner.",
                self._aktionen_termin_dialog,
            ),
            DemoSchritt(
                "2. Termin gespeichert",
                "Mit OK prüft das Programm die Angaben und legt den Termin an. Ein Termin ist "
                "genau eine Datei – darin steht alles: Teilnehmer, Zeitplan und Ergebnisse.\n\n"
                "Oben siehst du jetzt die Reiter, durch die die Demo der Reihe nach geht. "
                "Den Reiter „Datensicherung“ hat die Demo gesperrt, weil er immer mit deinen "
                "echten Terminen arbeitet.",
                self._aktionen_termin_speichern,
            ),
            DemoSchritt(
                "3. Einen Teilnehmer erfassen",
                "Im Reiter „Teilnehmer“ öffnet „Teilnehmer hinzufügen…“ die Erfassungsmaske.\n\n"
                "Wichtig sind Art und Leistungsklasse: ED ist eine Einzeldisziplin "
                "(Trümmerfeld, Flächensuche oder Behältnisstrecke), DK der Dreikampf aus allen "
                "drei. Bei ED gibt es genau einen Suchgegenstand.\n\n"
                "Die Startnummer bleibt hier bewusst offen – sie wird gleich für alle "
                "gemeinsam vergeben.",
                self._aktionen_teilnehmer_dialog,
            ),
            DemoSchritt(
                "4. Weitere Meldungen",
                "Die übrigen Meldungen kommen dazu. In der Praxis tippt man sie selten ab: "
                "Meist kommen sie über das ausfüllbare Anmeldeformular (PDF) oder eine "
                "Excel-Liste – beides liest der Reiter „Formular-Import“ ein.\n\n"
                "Achte auf die Spalte „Anmerkungen“: Bei Hugo Hansen fehlt die Chip-Nummer. "
                "Solche orangefarbenen Warnungen sollten vor dem Prüfungstag geklärt sein.",
                self._aktionen_weitere_teilnehmer,
            ),
            DemoSchritt(
                "5. Startnummern vergeben",
                "„Fehlende Startnummern vergeben…“ verteilt die Nummern auf einen Schlag: je "
                "Prüfung lückenlos aus dem im Termin hinterlegten Bereich, innerhalb der "
                "Prüfung nach Namen sortiert.\n\n"
                "Bereits vergebene Nummern ändert das Programm nie – kommen später Meldungen "
                "dazu, einfach erneut drücken.",
                self._aktionen_startnummern,
            ),
            DemoSchritt(
                "6. Wer hat bezahlt?",
                "„Bezahlt umschalten“ setzt den Zahlungsstatus für alle markierten "
                "Teilnehmer, ohne die Erfassungsmaske zu öffnen – praktisch am Anmeldetisch.\n\n"
                "Mit dem Filter „Bezahlt“ siehst du sofort, wer noch offen ist: hier Hugo "
                "Hansen.",
                self._aktionen_bezahlt,
            ),
            DemoSchritt(
                "7. Zeitplan",
                "Der Reiter „Zeitplan“ legt für jeden Richter aus den Termindaten eine Spalte "
                "an. „Automatisch verteilen…“ macht daraus einen ausgewogenen Vorschlag.\n\n"
                "Dreikampf-Teams laufen dabei nie gleichzeitig bei zwei Richtern und halten "
                "den Mindestabstand ein. Der Vorschlag lässt sich danach von Hand ändern, "
                "Start- und Endzeiten rechnet das Programm selbst. Die Seitenleiste "
                "„Offene Starts“ zeigt, ob jede Prüfung eingeplant ist.",
                self._aktionen_zeitplan,
            ),
            DemoSchritt(
                "8. Ergebnisse eintragen",
                "Am Prüfungstag kommen die Punkte in die Ergebniserfassung: je Disziplin die "
                "Suchleistung (0–60) und die Anzeigeleistung (0–40). Beim Dreikampf stehen "
                "alle drei Disziplinen nebeneinander in einer Zeile.\n\n"
                "Gelbe Zeilen sind noch nicht gespeichert.",
                self._aktionen_ergebnisse,
            ),
            DemoSchritt(
                "9. Disqualifikation",
                "Wird ein Team disqualifiziert oder bricht ab, setzt man den Haken "
                "„Disqualifiziert“ bzw. „Abbruch“. Die Punktefelder werden dann geleert und "
                "gesperrt.\n\n"
                "Das Team bekommt keine Wertnote und keinen Platz, zählt aber bei der Zahl "
                "der Starter mit.",
                self._aktionen_disqualifikation,
            ),
            DemoSchritt(
                "10. Speichern",
                "Erst „Alle Ergebnisse speichern“ (oder Strg+S) schreibt die Eingaben in die "
                "Termin-Datei – die gelbe Markierung verschwindet.\n\n"
                "Vergisst man es doch einmal, fragt das Programm beim Reiterwechsel nach. "
                "Beim Schließen des Programms speichert es automatisch.",
                self._aktionen_speichern,
            ),
            DemoSchritt(
                "11. Auswertung",
                "Die Auswertung rechnet Wertnoten und Plätze je Leistungsklasse selbst aus. "
                "ED (höchstens 100 Punkte): ab 96 Vorzüglich, ab 90 Sehr Gut, ab 80 Gut, ab "
                "70 Befriedigend. Dreikampf (höchstens 300): ab 286, 270, 240 bzw. 210 – und "
                "in jeder Disziplin mindestens 70 Punkte.\n\n"
                "Darunter heißt es „nicht Bestanden“ (rot, ohne Platz). Anna Albers und Ben "
                "Brandt sind mit je 96 Punkten gleichauf auf Platz 1 – dort steht "
                "„Stechen offen“.",
                self._aktionen_auswertung,
            ),
            DemoSchritt(
                "12. Stechen",
                "Bei Gleichstand auf Platz 1 entscheidet ein Stechen auf dem Platz. Das "
                "Ergebnis trägt man mit „Stechen-Sieger festlegen…“ ein: Der Sieger wird 1., "
                "die anderen werden 2.\n\n"
                "In der Demo gewinnt Anna Albers.",
                self._aktionen_stechen,
            ),
            DemoSchritt(
                "13. Ergebnisliste als PDF",
                "Im Reiter „Export“ liegen alle Ausdrucke: Ergebnisliste, Etiketten, "
                "Statistik, Bewertungsbögen, Zeitplan und mehr.\n\n"
                "Normalerweise fragt das Programm, wo die Datei hin soll (Standard: Ordner "
                "„Ausdrucke“ neben dem Termin). Die Demo hat die Ergebnisliste schon "
                "erzeugt – „PDF öffnen“ zeigt sie dir. Auch diese Datei wird am Ende gelöscht "
                "(ist sie dann noch im PDF-Programm geöffnet: beim nächsten Programmstart).",
                self._aktionen_pdf,
            ),
            DemoSchritt(
                "14. Richter am Tablet",
                "Bei größeren Prüfungen müssen die Ergebnisse nicht am Rechner der "
                "Prüfungsleitung eingetippt werden: Der Termin lässt sich im Web "
                "veröffentlichen, die Richter tragen ihre Punkte dann am Tablet oder Handy "
                "im Browser ein, und die Ergebnisse werden anschließend in den Termin "
                "übernommen.\n\n"
                "Wie das geht, steht im Handbuch in den Kapiteln „Für Richter: Ergebnisse im "
                "Browser eintragen“ und „Für die Prüfungsleitung: Termin im Web "
                "veröffentlichen“.",
                self._aktionen_nichts_markieren,
            ),
            DemoSchritt(
                "15. Demo-Termin löschen",
                "Das war ein kompletter Prüfungstag.\n\n"
                "Mit „Fertig“ wird der Demo-Termin samt Ergebnisliste gelöscht (eine noch im "
                "PDF-Programm geöffnete Ergebnisliste beim nächsten Programmstart). " + zurueck + "\n\n"
                "Echte Termine löschst du im Startbildschirm über „Löschen…“ – vorher am "
                "besten im Reiter „Datensicherung“ eine Sicherung erstellen.",
                self._aktionen_nichts_markieren,
            ),
        ]

    def _aktionen_nichts_markieren(self) -> list[Callable[[], None]]:
        return [lambda: self._markieren(None)]

    def _aktionen_termin_dialog(self) -> list[Callable[[], None]]:
        dialog = VeranstaltungsDialog(self._fenster)
        # Speicherort fest auf den Temp-Ordner - der automatische Vorschlag würde sonst in
        # den Termine-Ordner zeigen. Gespeichert wird ohnehin in self.pfad (siehe unten).
        dialog._pfad_manuell_geaendert = True
        dialog.pfad_feld.setText(_pfad_anzeige(self.pfad))
        dialog.pfad_feld.setReadOnly(True)
        self._dialog_zeigen(dialog)

        werte = demo_daten.VERANSTALTUNG
        aktionen = [
            *self._eintragen(dialog.verein, werte["verein"]),
            *self._eintragen(dialog.vereins_nr, werte["vereins_nr"]),
            *self._eintragen(dialog.ort, werte["ort"]),
            *self._eintragen(dialog.datum, datetime.date.today().strftime("%d.%m.%Y")),
            *self._eintragen(dialog.pruefungsnummer, werte["pruefungsnummer"]),
            *self._eintragen(dialog.pruefungsleiter, werte["pruefungsleiter"]),
            *self._eintragen(dialog.wertungsrichter_1, werte["wertungsrichter_1"]),
            *self._eintragen(dialog.wertungsrichter_2, werte["wertungsrichter_2"]),
            *self._eintragen(dialog.verband, werte["verband"]),
            *self._eintragen(dialog.meldestelle, werte["meldestelle"]),
        ]
        for kuerzel in demo_daten.PRUEFUNGEN:
            aktionen += self._eintragen(dialog.pruefung_checkboxen[kuerzel], True)
        for kuerzel, (von, bis) in demo_daten.PRUEFUNGEN.items():
            _beschriftung, von_feld, bis_feld = dialog.bereich_felder[kuerzel]
            aktionen += self._eintragen(von_feld, str(von))
            aktionen += self._eintragen(bis_feld, str(bis))
        aktionen.append(self._markieren_aktion(self._dialog_ok_knopf))
        return aktionen

    def _aktionen_termin_speichern(self) -> list[Callable[[], None]]:
        def speichern() -> None:
            dialog = self._dialog
            if not _lebt(dialog) or not isinstance(dialog, VeranstaltungsDialog):
                raise DemoFehler("Das Fenster „Neuen Termin anlegen“ ist nicht mehr offen.")
            # Dieselbe Prüfung wie beim Klick auf OK (zeigt bei vollständigen Angaben
            # keine Rückfrage).
            dialog._pruefen_und_akzeptieren()
            if dialog.result() != QDialog.Accepted:
                raise DemoFehler(
                    "Die Angaben im Fenster „Neuen Termin anlegen“ wurden verändert und sind "
                    "nicht vollständig – die Demo kann hier nicht weitermachen."
                )
            # Verifikation 04.10.2026, Befund 5: Wurden während Schritt 1 im eigenen Termin
            # noch Ergebnisse eingetippt, wie beim Terminwechsel nachfragen statt sie beim
            # Umschalten auf den Demo-Termin stillschweigend zu verwerfen.
            if not self.eigenes_fenster and not self._fenster._ungespeicherte_ergebnisse_klaeren(
                "Trotzdem mit der Demoprüfung weitermachen"
            ):
                raise DemoFehler(
                    "Die Demo kann hier nicht weitermachen: In deinem Termin gibt es Ergebnisse, "
                    "die sich nicht speichern ließen. Nach „Beenden“ bist du wieder in deinem "
                    "Termin, die Eingaben sind noch da und lassen sich korrigieren."
                )
            set_veranstaltung(self.conn, **dialog.veranstaltung_werte())
            self._dialog_schliessen()
            self._fenster._termin_setzen(self.conn, self.pfad, demo=True)
            self._fenster._tabs.setCurrentWidget(self._fenster.teilnehmer_tab)
            self._markieren(self._fenster._tabs.tabBar())

        return [speichern]

    def _aktionen_teilnehmer_dialog(self) -> list[Callable[[], None]]:
        fenster = self._fenster
        tab = fenster.teilnehmer_tab
        self._reiter_zeigen(tab)

        def oeffnen() -> None:
            self._markieren(tab.hinzufuegen_btn)

        def dialog_zeigen() -> None:
            # Dieselben Angaben wie TeilnehmerTab._teilnehmer_hinzufuegen.
            dialog = TeilnehmerDialog(
                tab,
                vergebene_nummern=vergebene_startnummern(self.conn),
                namen_je_startnummer={},
                bereiche=startnummer_bereiche(get_veranstaltung(self.conn)),
            )
            self._dialog_zeigen(dialog)
            daten = demo_daten.TEILNEHMER[0]["daten"]
            self._offen[:0] = [
                *self._eintragen(dialog.nachname, daten["nachname"]),
                *self._eintragen(dialog.vorname, daten["vorname"]),
                *self._eintragen(dialog.verein, daten["verein"]),
                *self._eintragen(dialog.rufname_hund, daten["rufname_hund"]),
                *self._eintragen(dialog.chip_nr, daten["chip_nr"]),
                *self._eintragen(dialog.art, daten["art"]),
                *self._eintragen(dialog.stufe, str(daten["stufe"])),
                *self._eintragen(dialog.disziplin, daten["disziplin"]),
                *self._eintragen(dialog.gegenstand_1, daten["gegenstand_1"]),
                self._markieren_aktion(self._dialog_ok_knopf),
            ]

        return [oeffnen, dialog_zeigen]

    def _aktionen_weitere_teilnehmer(self) -> list[Callable[[], None]]:
        tab = self._fenster.teilnehmer_tab

        def ersten_speichern() -> None:
            dialog = self._dialog
            if _lebt(dialog) and isinstance(dialog, TeilnehmerDialog):
                neu = dialog.ergebnis()
            else:  # Dialog wurde vom Anwender geschlossen - mit den Demodaten weiter
                neu = NeuerTeilnehmer(**demo_daten.TEILNEHMER[0]["daten"])
            self._dialog_schliessen()
            self._ids[neu.nachname] = add_teilnehmer(self.conn, neu)
            tab.aktualisieren()
            self._markieren(tab.tabelle)

        def anlegen(daten: dict) -> Callable[[], None]:
            def aktion() -> None:
                self._ids[daten["nachname"]] = add_teilnehmer(self.conn, NeuerTeilnehmer(**daten))
                tab.aktualisieren()
            return aktion

        return [ersten_speichern] + [anlegen(t["daten"]) for t in demo_daten.TEILNEHMER[1:]]

    def _aktionen_startnummern(self) -> list[Callable[[], None]]:
        tab = self._fenster.teilnehmer_tab

        def vergeben() -> None:
            # Direkt statt über den Knopf - der zeigt danach ein Meldungsfenster.
            ergebnis = fehlende_startnummern_vergeben(self.conn)
            tab.aktualisieren()
            self._panel.hinweis(f"{len(ergebnis.vergeben)} Startnummern vergeben.")
            self._markieren(tab.tabelle)

        return [lambda: self._markieren(tab.vergeben_btn), vergeben]

    def _aktionen_bezahlt(self) -> list[Callable[[], None]]:
        tab = self._fenster.teilnehmer_tab

        def markieren_und_umschalten() -> None:
            bezahlt = {tid for name, tid in self._ids.items() if name != demo_daten.NICHT_BEZAHLT}
            tab._auswahl_wiederherstellen(bezahlt)
            self._markieren(tab.bezahlt_btn)

        def umschalten() -> None:
            tab._bezahlt_umschalten()
            tab.tabelle.clearSelection()
            self._markieren(tab.tabelle)

        return [
            markieren_und_umschalten,
            umschalten,
            *self._eintragen(tab.filter_bezahlt, "Nicht bezahlt"),
        ]

    def _aktionen_zeitplan(self) -> list[Callable[[], None]]:
        fenster = self._fenster
        fenster.teilnehmer_tab.filter_bezahlt.setCurrentText("Alle")
        tab = fenster.zeitplan_tab

        def zeigen() -> None:
            zeitplan_richter_aus_veranstaltung_anlegen(self.conn)
            self._reiter_zeigen(tab)
            tab.aktualisieren()
            self._markieren(tab.verteilen_btn)

        def verteilen() -> None:
            # Direkt statt über den Knopf - bei schon vorhandenem Plan käme eine Rückfrage.
            richter = list_zeitplan_richter(self.conn)
            if not richter:
                raise DemoFehler("Im Zeitplan sind keine Richter angelegt.")
            automatische_zeitplan_verteilung(
                self.conn, [r["id"] for r in richter], standard_dauer_minuten=tab.standard_dauer.value(),
            )
            tab.status_label.setText("Automatischer Zeitplan-Vorschlag erstellt.")
            tab.aktualisieren()

        return [zeigen, verteilen]

    def _aktionen_ergebnisse(self) -> list[Callable[[], None]]:
        tab = self._fenster.ergebnis_tab
        self._reiter_zeigen(tab)
        aktionen: list[Callable[[], None]] = []
        for eintrag in demo_daten.TEILNEHMER:
            nachname = eintrag["daten"]["nachname"]
            for disziplin, (suche, anzeige) in eintrag.get("ergebnis", {}).items():
                for index, wert in ((0, suche), (1, anzeige)):
                    aktionen += self._punkte_eintragen(nachname, disziplin, index, wert)
        return aktionen

    def _punkte_eintragen(self, nachname: str, disziplin: str, index: int, wert: int) -> list[Callable[[], None]]:
        """Tippt eine Punktzahl Ziffer für Ziffer. Das Feld wird jedes Mal frisch gesucht -
        baut der Anwender die Tabelle zwischendurch neu auf („Liste aktualisieren“), sind
        die alten Felder weg."""
        def feld() -> QLineEdit:
            felder = self._fenster.ergebnis_tab.eingabefelder(self._ids[nachname])
            if felder is None or disziplin not in felder[1]:
                raise DemoFehler(f"Die Zeile von {nachname} ist in der Ergebniserfassung nicht zu finden.")
            return felder[1][disziplin][index]

        def fokus() -> None:
            eingabe = feld()
            self._markieren(eingabe)
            eingabe.setText("")
        fokus.pause_ms = self.PAUSE_MS // 3

        text = str(wert)
        aktionen: list[Callable[[], None]] = [fokus]
        for laenge in range(1, len(text) + 1):
            taste = (lambda teil=text[:laenge]: feld().setText(teil))
            taste.pause_ms = random.randint(*self.TASTE_MS)
            aktionen.append(taste)
        aktionen[-1].pause_ms = self.PAUSE_MS // 2
        return aktionen

    def _aktionen_disqualifikation(self) -> list[Callable[[], None]]:
        def aktion() -> None:
            nachname = next(t["daten"]["nachname"] for t in demo_daten.TEILNEHMER if t.get("status") == "dq")
            felder = self._fenster.ergebnis_tab.eingabefelder(self._ids[nachname])
            if felder is None:
                raise DemoFehler(f"Die Zeile von {nachname} ist in der Ergebniserfassung nicht zu finden.")
            dq_box = felder[2][0]
            self._markieren(dq_box.parentWidget() or dq_box)
            dq_box.setChecked(True)
        return [aktion]

    def _aktionen_speichern(self) -> list[Callable[[], None]]:
        tab = self._fenster.ergebnis_tab

        def speichern() -> None:
            tab.alle_speichern()
            if tab.hat_ungespeicherte_aenderungen():
                raise DemoFehler("Nicht alle Ergebnisse ließen sich speichern (siehe Meldung).")
            self._markieren(tab.tabelle)

        return [lambda: self._markieren(tab.speichern_btn), speichern]

    def _aktionen_auswertung(self) -> list[Callable[[], None]]:
        tab = self._fenster.auswertung_tab

        def zeigen() -> None:
            self._reiter_zeigen(tab)
            self._markieren(tab.tabelle)

        return [zeigen]

    def _aktionen_stechen(self) -> list[Callable[[], None]]:
        tab = self._fenster.auswertung_tab

        def festlegen() -> None:
            # Direkt statt über den Knopf - der fragt den Sieger in einem Dialog ab.
            fertig, _ausstehend = berechne_auswertung(self.conn)
            gruppe = [int(t.id) for t in fertig if t.stechen == "offen"]
            sieger = self._ids.get(demo_daten.STECHEN_SIEGER)
            if sieger not in gruppe:
                raise DemoFehler("In der Auswertung ist kein offenes Stechen zu finden.")
            setze_stechen_sieger(self.conn, sieger, gruppe)
            tab.aktualisieren()
            self._markieren(tab.tabelle)

        return [lambda: self._markieren(tab.stechen_btn), festlegen]

    def _aktionen_pdf(self) -> list[Callable[[], None]]:
        tab = self._fenster.export_tab

        def zeigen() -> None:
            self._reiter_zeigen(tab)
            self._markieren(tab.ergebnisliste_btn)

        def erzeugen() -> None:
            # Direkt statt über den Knopf - der fragt nach dem Speicherort und zeigt danach
            # ein Meldungsfenster.
            ordner = _ausdrucke_ordner(self.pfad)
            os.makedirs(ordner, exist_ok=True)
            ziel = os.path.join(ordner, _export_dateiname(self.conn, "Ergebnisliste"))
            pdf_export.erstelle_ergebnisliste_pdf(self.conn, ziel)
            self.pdf_pfad = ziel
            self._panel.hinweis(f"Gespeichert unter: {_pfad_anzeige(ziel)}")
            self._panel.extra("PDF öffnen", lambda: self._pdf_oeffnen(ziel))

        return [zeigen, erzeugen]


def demo_ohne_termin_ausfuehren(fenster_fabrik) -> None:
    """Startet die Demo aus dem Startdialog (noch kein Hauptfenster offen) und wartet, bis
    sie beendet ist - danach zeigt main() wieder den Startdialog."""
    anwendung = QApplication.instance()
    vorher = anwendung.quitOnLastWindowClosed()
    # Sonst würde das Schließen des Demo-Fensters die ganze Anwendung beenden.
    anwendung.setQuitOnLastWindowClosed(False)
    schleife = QEventLoop()
    tour = DemoTour(fenster_fabrik=fenster_fabrik)
    tour.beendet.connect(schleife.quit)
    try:
        tour.starten()
        if not tour.ist_beendet:
            schleife.exec()
    finally:
        tour.beenden()
        anwendung.setQuitOnLastWindowClosed(vorher)
