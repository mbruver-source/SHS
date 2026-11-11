"""Geführte Demoprüfung (Marcos Wunsch 04.10.2026): Das Programm spielt einmal einen
kompletten Prüfungstag mit erfundenen Daten vor - Termin anlegen, Teilnehmer, Startnummern,
Bezahlt, Zeitplan, Ergebnisse, Auswertung, Stechen, Ergebnisliste - und erklärt in einem
kleinen Fenster je Schritt, was gerade passiert und warum. Der Anwender klickt nur „Weiter“
- oder lässt die Demo laufen: Ist ein Schritt fertig, geht es nach einer Lesezeit je nach
Textlänge (mindestens 10 s, höchstens 40 s) von allein weiter (Marcos Wunsch 05.10.2026,
abschaltbar über „Automatisch weiter“). In den Schritten 1 bis 3 zeigt „Vorheriger Text“
frühere Erklärungen noch einmal (UX-Test 03.11.2026, X6); ab Schritt 4 nimmt „Schritt zurück“
den vorigen Schritt zurück und spielt ihn neu ab (UX-Test 2026-11, T12).

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
import math
import random
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QEvent, QEventLoop, QObject, QRect, Qt, QTimer, QUrl, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QWidget,
)

import demo_daten
from db import (
    dateiname_vorschlagen,
    init_db,
    termine_ordner,
)
from desktop_demo_panel import DemoMarkierung, DemoPanel, DemoSchritt, _lebt
from desktop_demo_schritte import DemoFehler, _DemoSchritteMixin
from shs_core import stechen_gilt
from desktop_gemeinsam import (
    _fehlertext,
    _ja_nein,
    _pfad_anzeige,
    _url_oeffnen,
)

#: Präfix der Temp-Ordner - alte Reste (z. B. nach einem Absturz) werden beim nächsten
#: Start aufgeräumt, siehe demo_reste_aufraeumen.
DEMO_ORDNER_PRAEFIX = "shs_demo_"


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


# Tasten, die allein keine Eingabe sind (siehe DemoTour.eventFilter).
_NUR_UMSCHALTTASTEN = frozenset(
    (Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Meta, Qt.Key.Key_AltGr, Qt.Key.Key_CapsLock)
)


class DemoTour(_DemoSchritteMixin, QObject):
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
    AUTO_WEITER_S = 15
    #: UX-Test 03.11.2026, X6: 10 s reichten für lange Erklärtexte (bis ~90 Wörter) nicht.
    #: Die Wartezeit wächst mit der Textlänge (Lesezeit je Wort), höchstens LESEZEIT_MAX_S.
    #: Marco 10.11.2026: Der Text soll langsamer durchlaufen (vorher 10 s, 0,35 s je Wort, 40 s).
    LESEZEIT_JE_WORT_S = 0.6
    LESEZEIT_MAX_S = 60
    #: Nach einem geschlossenen sperrenden Fenster bleiben mindestens so viele Sekunden.
    AUTO_WEITER_NACH_MODAL_S = 3
    #: Index des ersten Schritts, der im Demo-Termin spielt (nach „Termin gespeichert“) - ab
    #: hier gibt es einen Stand, den „Schritt zurück“ wiederherstellen kann (T12).
    ERSTER_SCHRITT_IM_TERMIN = 3
    TASTE_MS = (55, 140)  # je Zeichen, leicht schwankend wie beim echten Tippen

    def __init__(self, fenster=None, fenster_fabrik=None):
        super().__init__()
        if fenster is None and fenster_fabrik is None:
            raise ValueError("DemoTour braucht ein Hauptfenster oder eine Fenster-Fabrik")
        self._fenster = fenster
        self._fenster_fabrik = fenster_fabrik
        self.eigenes_fenster = fenster is None
        self._ordner: Path | None = None
        self._gestartet = False  # erst nach erfolgreichem Start (Statusmeldung beim Beenden)
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
        # T12: Stand des Demo-Termins zu Beginn jedes Schritts (Kopie im Speicher), damit
        # „Schritt zurück“ ihn wiederherstellen kann.
        self._stand: dict[int, sqlite3.Connection] = {}

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
        heute = self._heute = datetime.date.today()
        # PO1 (PO_01012027.md): Die Demo findet "heute" statt - ab der neuen PO (01.01.2027)
        # ohne Stechen. Schritte 11/12 richten sich danach.
        self._mit_stechen = stechen_gilt(heute)
        datum = heute.isoformat()
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
        self._panel.beenden_angefragt.connect(self._beenden_nach_rueckfrage)
        self._panel.auto_weiter_umgeschaltet.connect(self._auto_weiter_umgeschaltet)
        # Rückblick (X6): Countdown nur pausieren, nicht dauerhaft anhalten - danach zählt er
        # wieder, sofern der Schritt fertig ist (Verifikation A6, Befund 2).
        self._panel.rueckblick_geoeffnet.connect(self._countdown_stoppen)
        self._panel.rueckblick_beendet.connect(self._nach_rueckblick)
        self._panel.schritt_zurueck_geklickt.connect(self.schritt_zurueck)
        # Eigene Eingaben im Demo-Dialog erkennen (siehe eventFilter).
        QApplication.instance().installEventFilter(self)
        self._schritte = self._schritte_aufbauen()
        self._schritt_zeigen(0)
        self._gestartet = True

    def panel_zeigen(self) -> None:
        if _lebt(self._panel):
            self._panel.show()
            self._panel.raise_()
            self._panel.activateWindow()

    def weiter(self) -> None:
        if self.ist_beendet:
            return
        self._countdown_stoppen()
        # Läuft der aktuelle Schritt noch, wird er sofort zu Ende geführt. Ist er schon fertig,
        # nichts erneut ausführen (sonst sprang das Erklärfenster vor jedem Schritt doppelt,
        # Teil 10 Nr. 2).
        if self._offen:
            self._alles_sofort()
        if self.ist_beendet or (self._panel is not None and not self._panel.weiter_btn.isEnabled()):
            return
        if self._index + 1 >= len(self._schritte):
            self.beenden()
            return
        self._schritt_zeigen(self._index + 1)

    def _beenden_nach_rueckfrage(self) -> None:
        """Nachtest 2 (N9, Marco 04.11.2026): Der Knopf „Beenden“ liegt neben „Weiter“ - ein
        Fehlklick beendete die Demo sofort, und sie begann danach von vorn. Jetzt mit Rückfrage
        (Vorgabe „Nein“). Solange sie offen ist, ruht die Demo: kein Tippen, kein Countdown
        (Verifikation B17). Nach „Nein“ geht der Schritt weiter, ein laufender Countdown beginnt
        neu."""
        if self.ist_beendet:
            return
        lief = self._countdown.isActive()
        tippte = self._timer.isActive()
        self._timer.stop()
        self._countdown_stoppen()
        if _ja_nein(
            self._panel, "Demoprüfung beenden",
            "Die Demoprüfung wirklich beenden? Der Demo-Termin wird gelöscht, beim nächsten "
            "Start beginnt die Demo wieder bei Schritt 1.",
        ):
            self.beenden()
        elif not self.ist_beendet:
            if tippte and self._offen:
                self._timer.start(0)
            elif lief:
                self._nach_rueckblick()  # Countdown wie nach dem Rückblick neu starten

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
            self._staende_verwerfen(0)
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
            if fenster is not None and not self.eigenes_fenster and _lebt(fenster) and self._gestartet:
                # Nur wenn die Demo wirklich lief (Teil 10 Nr. 5).
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
        if index >= self.ERSTER_SCHRITT_IM_TERMIN:
            try:
                self._stand_merken(index)
            except sqlite3.Error:
                # Ohne Kopie gibt es nur für diesen Schritt kein „Schritt zurück“ (Verifikation B9).
                self._staende_verwerfen(index)
        self._panel.anzeigen(index, len(self._schritte) - 1, schritt, index == len(self._schritte) - 1)
        self._panel.zurueck_modus(index > self.ERSTER_SCHRITT_IM_TERMIN)
        self._offen = []
        if schritt.aktionen is not None:
            try:
                self._offen = list(schritt.aktionen())
            except Exception as exc:  # noqa: BLE001 - jeder Fehler erscheint im Erklärfenster
                self._fehler_zeigen(exc)
                return
        self._naechste_aktion()

    def _stand_merken(self, index: int) -> None:
        self._staende_verwerfen(index)
        self.conn.commit()
        kopie = sqlite3.connect(":memory:")
        self.conn.backup(kopie)
        self._stand[index] = kopie

    def _staende_verwerfen(self, ab_index: int) -> None:
        for index in [i for i in self._stand if i >= ab_index]:
            self._stand.pop(index).close()

    def schritt_zurueck(self) -> None:
        """UX-Test 2026-11, T12: den laufenden Schritt abbrechen, den Stand vor dem vorigen
        Schritt wiederherstellen und diesen noch einmal abspielen."""
        ziel = self._zurueck_ziel()
        if self.ist_beendet or ziel < self.ERSTER_SCHRITT_IM_TERMIN or ziel not in self._stand:
            return
        self._timer.stop()
        self._countdown_stoppen()
        self._offen.clear()
        try:
            self._markieren(None)
            self._dialog_schliessen()
            # Offene Änderungen gehören zum zurückgenommenen Schritt - und eine offene
            # Schreib-Transaktion ließe das Zurückschreiben scheitern (Verifikation B9).
            self.conn.rollback()
            self._stand[ziel].backup(self.conn)
            # Alle Reiter neu aus der Datei aufbauen - auch ungespeicherte Ergebnisse gehören zum
            # zurückgenommenen Schritt.
            self._fenster._termin_setzen(self.conn, self.pfad, demo=True)
        except Exception as exc:  # noqa: BLE001 - jeder Fehler erscheint im Erklärfenster
            self._fehler_zeigen(exc)
            return
        self._panel.verlauf_kuerzen(ziel)
        self._schritt_zeigen(ziel)
        # Sonst nähme Enter (Knopf mit Fokus) gleich den nächsten Schritt zurück (Verifikation B9).
        self._panel.weiter_btn.setFocus()

    def _zurueck_ziel(self) -> int:
        """Schritt, zu dem „Schritt zurück“ springt: der vorige - außer zwischen „Ergebnisse
        eintragen“ und „Speichern“. Dort stehen die Punkte nur ungespeichert in der Tabelle, der
        Stand vor dem vorigen Schritt enthielte sie nicht, und die Demo fände später kein
        Stechen. Dann geht es zurück zu „Ergebnisse eintragen“ (Abschluss-QS B11, K1)."""
        ziel = self._index - 1
        aktionen = [schritt.aktionen for schritt in self._schritte]
        try:
            ergebnisse = aktionen.index(self._aktionen_ergebnisse)
            speichern = aktionen.index(self._aktionen_speichern)
        except ValueError:
            return ziel
        return ergebnisse if ergebnisse < ziel <= speichern else ziel

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
        if isinstance(exc, DemoFehler):
            text = str(exc)
        else:
            # Desktop-Prüfung 14.10.2026 (Teil 10 Nr. 6): Datei-/Datenbankfehler in Klartext,
            # Programmfehler samt Traceback ins Absturzprotokoll und mit ihrem Typ.
            text = f"Dieser Schritt ließ sich nicht vorführen.\n\n{_fehlertext(exc)}"
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
            or self._panel.im_rueckblick()  # Verifikation A6, Befund 3
        ):
            return
        self._rest = self._wartezeit()
        self._modal_wartet = False
        self._panel.countdown_anzeigen(self._rest)
        self._countdown.start()

    def _nach_rueckblick(self) -> None:
        if not self._offen:
            self._countdown_starten()

    def _wartezeit(self) -> int:
        """Sekunden bis zum automatischen Weiter: mindestens AUTO_WEITER_S, bei langen Texten
        die Lesezeit (UX-Test 03.11.2026, X6)."""
        schritt = self._schritte[self._index]
        woerter = len(f"{schritt.titel} {schritt.text}".split())
        lesezeit = min(self.LESEZEIT_MAX_S, math.ceil(woerter * self.LESEZEIT_JE_WORT_S))
        return max(self.AUTO_WEITER_S, lesezeit)

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
        _url_oeffnen(self._panel if _lebt(self._panel) else None, QUrl.fromLocalFile(ziel), _pfad_anzeige(ziel))

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

    def _markieren(self, ziel: QWidget | None, bereich: Callable[[], QRect | None] | None = None) -> None:
        if _lebt(self._markierung):
            self._markierung.entfernen()
        self._markierung = None
        self._ziel = ziel
        if _lebt(ziel):
            self._sichtbar_machen(ziel)
            self._markierung = DemoMarkierung(ziel, bereich)

    def _ergebniszelle_markieren(self, teilnehmer_id: int, spalte: int) -> None:
        """Markiert eine Zelle der Ergebniserfassung (O8: Rechteck statt Eingabe-Widget).
        Die Zeile wird bei jedem Ausrichten neu gesucht, falls die Tabelle neu aufgebaut
        oder umsortiert wurde."""
        tab = self._fenster.ergebnis_tab

        def bereich() -> QRect | None:
            row = tab.zeile_von(teilnehmer_id)
            return None if row is None else tab.zellrechteck(row, spalte)

        self._markieren(tab.tabelle.viewport(), bereich)

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
        Rückfrage beim Verlassen der Ergebniserfassung nicht erscheint. Bleibt trotzdem
        etwas ungespeichert (eigene, nicht speicherbare Eingabe), wird ohne Rückfrage
        gewechselt; die Eingaben bleiben ungespeichert stehen (sonst könnte ein „Abbrechen“
        die Demo auf dem falschen Reiter weiterlaufen lassen)."""
        fenster = self._fenster
        if fenster._tabs.currentWidget() is widget:
            return
        if fenster.ergebnis_tab.hat_ungespeicherte_aenderungen():
            fenster.ergebnis_tab.alle_speichern()
        if fenster.ergebnis_tab.hat_ungespeicherte_aenderungen():
            fenster._tabs.blockSignals(True)
            fenster._tabs.setCurrentWidget(widget)
            fenster._tabs.blockSignals(False)
            fenster._vorheriger_tab_index = fenster._tabs.currentIndex()
            if widget is not fenster.ergebnis_tab and hasattr(widget, "aktualisieren"):
                widget.aktualisieren()
            return
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
