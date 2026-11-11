"""
Erklärfenster und Markierung der geführten Demoprüfung (seit 11.11.2026 aus desktop_demo.py
ausgelagert, Code unverändert): DemoMarkierung rahmt das aktive Element, DemoPanel zeigt die
Erklärung mit den Knöpfen. Die Steuerung (DemoTour) steht in desktop_demo.py. Bewusst KEIN
`import app` (siehe desktop_programm.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import shiboken6
from PySide6.QtCore import QPoint, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QKeySequence, QPainter, QPalette, QPen, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from desktop_gemeinsam import (
    symbol_setzen,
)


@dataclass
class DemoSchritt:
    titel: str
    text: str
    #: Liefert beim Betreten des Schritts die einzelnen Teilaktionen, die nacheinander
    #: (mit kurzer Pause, damit man zusehen kann) ausgeführt werden.
    aktionen: Callable[[], list[Callable[[], None]]] | None = None


def _lebt(objekt) -> bool:
    return objekt is not None and shiboken6.isValid(objekt)


class DemoMarkierung(QWidget):
    """Farbiger Rahmen um das Element, an dem die Demo gerade arbeitet. Selbst gezeichnet
    (Akzentfarbe aus der Palette) statt per Stylesheet, damit die Stylesheets der Reiter
    (z. B. gelbe ungespeicherte Zeilen) und die Design-Tests unberührt bleiben. Lässt
    Mausklicks durch und folgt dem Ziel, falls es sich verschiebt. Mit `bereich` nur ein
    Ausschnitt des Ziels (in dessen Koordinaten), z. B. eine Tabellenzelle der
    Ergebniserfassung - die hat seit O8 kein eigenes Widget mehr. Liefert `bereich` ein
    leeres Rechteck oder None, bleibt die Markierung verborgen."""

    RAND = 4

    def __init__(self, ziel: QWidget, bereich: Callable[[], QRect | None] | None = None):
        super().__init__(ziel.window())
        self._ziel = ziel
        self._bereich = bereich
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
        ausschnitt = QRect(QPoint(0, 0), ziel.size())
        if self._bereich is not None:
            ausschnitt = self._bereich()
            if ausschnitt is None or ausschnitt.isEmpty():
                self.hide()
                return
        oben_links = ziel.mapTo(fenster, ausschnitt.topLeft())
        r = self.RAND
        self.setGeometry(QRect(oben_links, ausschnitt.size()).adjusted(-r, -r, r, r))
        self.show()
        self.raise_()

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        maler = QPainter(self)
        maler.setRenderHint(QPainter.Antialiasing)
        # Akzentfarbe (QPalette.Link) - Highlight ist in den hellen Designs die blasse
        # Auswahlfarbe und auf gelben Zeilen kaum zu sehen (Verifikation O9).
        maler.setPen(QPen(self.palette().color(QPalette.Link), 3))
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
    beenden_geklickt = Signal()  # Fenster geschlossen: ohne Rückfrage beenden
    beenden_angefragt = Signal()  # Knopf „Beenden“: erst nachfragen (Nachtest 2, N9)
    auto_weiter_umgeschaltet = Signal(bool)
    rueckblick_geoeffnet = Signal()
    rueckblick_beendet = Signal()
    schritt_zurueck_geklickt = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent, Qt.Tool)
        self.setWindowTitle("Demoprüfung")
        self._schliessen_erlaubt = False
        self._extra_aktion: Callable[[], None] | None = None
        self._letzter = False

        self._labels_aufbauen()
        self._knoepfe_aufbauen()
        self._layout_aufbauen()

    def _labels_aufbauen(self) -> None:
        self.schritt_label = QLabel()
        self.titel_label = QLabel()
        schrift = QFont(self.titel_label.font())
        schrift.setBold(True)
        schrift.setPointSizeF(schrift.pointSizeF() * 1.25)
        self.titel_label.setFont(schrift)
        self.text_label = QLabel()
        self.hinweis_label = QLabel()
        # Eigene Zeile statt hinweis_label (das z. B. den Speicherort der PDF zeigt).
        self.pause_label = QLabel("Automatisch weiter angehalten – weiter mit „Weiter“.")
        self.pause_label.setVisible(False)
        for label in (self.schritt_label, self.titel_label, self.text_label, self.hinweis_label, self.pause_label):
            label.setTextFormat(Qt.PlainText)
            label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.hinweis_label.setVisible(False)

    def _knoepfe_aufbauen(self) -> None:
        self.extra_btn = QPushButton()
        self.extra_btn.setVisible(False)
        self.extra_btn.clicked.connect(self._extra_ausfuehren)
        # Automatisch weiter (Marcos Wunsch 05.10.2026): gilt für die ganze Demo, wird
        # nicht über sie hinaus gespeichert.
        self.auto_box = QCheckBox("Automatisch weiter")
        self.auto_box.setChecked(True)
        from desktop_demo import DemoTour  # erst hier: desktop_demo importiert dieses Modul

        self.auto_box.setToolTip(
            "Ist ein Schritt fertig, geht es nach einer Lesezeit (mindestens "
            f"{DemoTour.AUTO_WEITER_S} Sekunden, bei langen Texten länger) von allein weiter."
        )
        # UX-Test 03.11.2026, X6: die Erklärung eines früheren Schritts noch einmal lesen; seit
        # UX-Test 2026-11 (T12) ab Schritt 4 „Schritt zurück“ (siehe zurueck_modus).
        self.zurueck_btn = QPushButton("Vorheriger Text")
        self.zurueck_btn.setToolTip("Zeigt die Erklärung des vorigen Schritts noch einmal – das automatische Weiter "
                                    "wartet solange.")
        self.zurueck_btn.setVisible(False)
        self.zurueck_btn.clicked.connect(self._zurueck_gedrueckt)
        self._echtes_zurueck = False  # siehe zurueck_modus
        self._verlauf: list[tuple[str, str, str]] = []
        self._rueckblick: int | None = None
        self._sichtbar_vor_rueckblick: tuple[bool, bool, bool] | None = None
        self.auto_box.toggled.connect(self.auto_weiter_umgeschaltet)
        self.beenden_btn = QPushButton("Beenden")
        self.beenden_btn.setToolTip("Demo abbrechen – der Demo-Termin wird gelöscht.")
        self.beenden_btn.clicked.connect(self.beenden_angefragt)
        self.weiter_btn = QPushButton("Weiter")
        self.weiter_btn.setObjectName("primaerButton")  # siehe _QSS_TEMPLATE
        # Symbol rechts vom Text (Pfeil nach vorn): Qt setzt das Icon bei umgekehrter
        # Leserichtung ans Ende; der Text selbst bleibt links nach rechts (Marco 01.11.2026,
        # Symbole statt „▶“/„✔“).
        self.weiter_btn.setLayoutDirection(Qt.RightToLeft)
        symbol_setzen(self.weiter_btn, "chevron-right", "#FFFFFF")
        self.weiter_btn.setDefault(True)
        self.weiter_btn.clicked.connect(self._weiter_gedrueckt)
        # setDefault wirkt nur in QDialog - das Erklärfenster ist ein QWidget (UX-Test
        # 03.11.2026: Enter bewirkte nichts).
        for taste in (Qt.Key_Return, Qt.Key_Enter):
            QShortcut(QKeySequence(taste), self, activated=self._enter_gedrueckt)

    def _layout_aufbauen(self) -> None:
        knopf_zeile = QHBoxLayout()
        knopf_zeile.addWidget(self.zurueck_btn)
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
        # Unterkante (Bildschirmkoordinate), an der das Fenster mit seinen Knöpfen stehen
        # bleibt, solange es nicht verschoben wird - siehe _im_bildschirm_halten.
        self._unten: int | None = None
        # True, solange das Programm selbst die Höhe anpasst (_groesse_anpassen) - nur dann
        # wird die Unterkante festgehalten, nicht wenn der Anwender am Rand zieht.
        self._eigene_groessenaenderung = False

    def anzeigen(self, nummer: int, anzahl: int, schritt: DemoSchritt, letzter: bool) -> None:
        # Nummer 0 = Begrüßung; die übrigen Schritte tragen ihre Nummer auch im Titel.
        self.schritt_label.setText(f"Schritt {nummer} von {anzahl}" if nummer else "Einführung")
        self.titel_label.setText(schritt.titel)
        self.text_label.setText(schritt.text)
        self._verlauf.append((self.schritt_label.text(), schritt.titel, schritt.text))
        self._rueckblick = None
        self._sichtbar_vor_rueckblick = None  # hinweis()/extra() unten setzen die Zeilen neu
        self.zurueck_btn.setVisible(len(self._verlauf) > 1)
        self.zurueck_btn.setEnabled(True)
        self.hinweis(None)
        self.extra(None)
        self._letzter = letzter
        self.countdown_anzeigen(None)
        self.angehalten_anzeigen(False)
        self.weiter_btn.setEnabled(True)
        self._groesse_anpassen()
        if not self._positioniert:
            self._positioniert = True
            self._in_ecke_setzen(rechts=True)
        self.show()
        # Erst nach show() kennt Qt den Fensterrahmen (Titelleiste) und damit die echte Höhe.
        self._im_bildschirm_halten()
        self.raise_()

    def countdown_anzeigen(self, sekunden: int | None) -> None:
        """Knopftext „Weiter (n)“ während des Countdowns, sonst „Weiter“ bzw. im letzten
        Schritt „Fertig“ (dort gibt es keinen Countdown) - mit Pfeil bzw. Haken als Symbol."""
        # Weiß auf der Akzentfarbe (primaerButton).
        symbol_setzen(self.weiter_btn, "check" if self._letzter else "chevron-right", "#FFFFFF")
        if self._letzter:
            self.weiter_btn.setText("Fertig")
        elif sekunden is None:
            self.weiter_btn.setText("Weiter")
        else:
            self.weiter_btn.setText(f"Weiter ({sekunden})")

    def _texte_zeigen(self, eintrag: tuple[str, str, str], rueckblick: bool) -> None:
        schritt, titel, text = eintrag
        self.schritt_label.setText(f"Rückblick – {schritt}" if rueckblick else schritt)
        self.titel_label.setText(titel)
        self.text_label.setText(text)
        # Hinweis- und Zusatzzeile gehören zum laufenden Schritt - im Rückblick ausblenden
        # (Verifikation A6, Befund 4), danach wie vorher zeigen.
        if rueckblick:
            if self._sichtbar_vor_rueckblick is None:
                self._sichtbar_vor_rueckblick = (self.hinweis_label.isVisible(), self.extra_btn.isVisible(),
                                                 self.pause_label.isVisible())
            for widget in (self.hinweis_label, self.extra_btn, self.pause_label):
                widget.setVisible(False)
        elif self._sichtbar_vor_rueckblick is not None:
            for widget, sichtbar in zip((self.hinweis_label, self.extra_btn, self.pause_label),
                                        self._sichtbar_vor_rueckblick):
                widget.setVisible(sichtbar)
            self._sichtbar_vor_rueckblick = None
        self._groesse_anpassen()

    def im_rueckblick(self) -> bool:
        return self._rueckblick is not None

    def zurueck_modus(self, echt: bool) -> None:
        """UX-Test 2026-11, T12 (Marco 04.11.2026, ersetzt R4): ab Schritt 4 spielt „Schritt
        zurück“ den vorigen Schritt wirklich noch einmal ab (der Stand davor wird
        wiederhergestellt). Bis Schritt 3 gibt es keinen früheren Schritt im Demo-Termin, dort
        bleibt „Vorheriger Text“."""
        self._echtes_zurueck = echt
        if echt:
            self.zurueck_btn.setText("Schritt zurück")
            self.zurueck_btn.setToolTip(
                "Nimmt den vorigen Schritt zurück und spielt ihn noch einmal ab (aus Schritt 10 "
                "und 11 zurück bis „Ergebnisse eintragen“)."
            )
        else:
            self.zurueck_btn.setText("Vorheriger Text")
            self.zurueck_btn.setToolTip("Zeigt die Erklärung des vorigen Schritts noch einmal – das automatische "
                                        "Weiter wartet solange.")

    def verlauf_kuerzen(self, anzahl: int) -> None:
        """Nach „Schritt zurück“: nur die Erklärungen der Schritte vor dem Ziel behalten."""
        del self._verlauf[anzahl:]

    def _zurueck_gedrueckt(self) -> None:
        if self._echtes_zurueck and self._rueckblick is None:
            self.schritt_zurueck_geklickt.emit()
        else:
            self._rueckblick_zeigen()

    def _rueckblick_zeigen(self) -> None:
        """Eine Erklärung weiter zurück; die Tour wartet solange (rueckblick_geoeffnet)."""
        aktuell = len(self._verlauf) - 1 if self._rueckblick is None else self._rueckblick
        if aktuell <= 0:
            return
        erster = self._rueckblick is None
        self._rueckblick = aktuell - 1
        self._texte_zeigen(self._verlauf[self._rueckblick], rueckblick=True)
        self.zurueck_btn.setEnabled(self._rueckblick > 0)
        if erster:
            self.rueckblick_geoeffnet.emit()
        self.weiter_btn.setText("Aktueller Schritt")

    def _rueckblick_beenden(self) -> None:
        if self._rueckblick is None:
            return
        self._rueckblick = None
        self._texte_zeigen(self._verlauf[-1], rueckblick=False)
        self.zurueck_btn.setEnabled(True)
        self.countdown_anzeigen(None)
        self.rueckblick_beendet.emit()

    def _weiter_gedrueckt(self) -> None:
        if self._rueckblick is not None:
            # Erst zurück zum laufenden Schritt, nicht gleich weiter.
            self._rueckblick_beenden()
            return
        self.weiter_geklickt.emit()

    def _enter_gedrueckt(self) -> None:
        # Enter löst wie unter Windows üblich den Knopf mit dem Fokus aus, sonst „Weiter“
        # (Verifikation A6, Befund 5).
        fokus = self.focusWidget()
        knopf = fokus if isinstance(fokus, QPushButton) and fokus.isVisible() else self.weiter_btn
        if knopf.isEnabled() and knopf.isVisible():
            knopf.click()

    def _zeile_zeigen(self, nummer: int, widget: QWidget, sichtbar: bool) -> None:
        """Hinweis-/Zusatz-/Pausenzeile zeigen oder ausblenden - im Rückblick erst bei der
        Rückkehr zum laufenden Schritt (Verifikation A6, Befund 4)."""
        if self._sichtbar_vor_rueckblick is not None:
            werte = list(self._sichtbar_vor_rueckblick)
            werte[nummer] = sichtbar
            self._sichtbar_vor_rueckblick = tuple(werte)
            return
        widget.setVisible(sichtbar)

    def angehalten_anzeigen(self, angehalten: bool) -> None:
        self._zeile_zeigen(2, self.pause_label, angehalten)
        self._groesse_anpassen()

    def hinweis(self, text: str | None) -> None:
        # Unsichtbare Umbruchstellen nach jedem Pfadtrenner: ein langer Speicherpfad bricht so
        # im Fenster um, statt rechts abgeschnitten zu werden (Marco 01.11.2026).
        anzeige = (text or "").replace("\\", "\\​").replace("/", "/​")
        self.hinweis_label.setText(anzeige)
        self._zeile_zeigen(0, self.hinweis_label, bool(text))
        self._groesse_anpassen()

    def extra(self, beschriftung: str | None, aktion: Callable[[], None] | None = None) -> None:
        self._extra_aktion = aktion
        self.extra_btn.setText(beschriftung or "")
        self._zeile_zeigen(1, self.extra_btn, bool(beschriftung))
        self._groesse_anpassen()

    def _groesse_anpassen(self) -> None:
        """Höhe passend zum Inhalt, Breite bleibt. Kommt während eines Schritts eine Zeile
        dazu (z. B. „Gespeichert unter …“), wächst das Fenster mit - sonst quetschte Qt den
        umbrechenden Erklärtext, er war mitten in der Zeile abgeschnitten (A4-Prüfung am
        echten Windows, Marco 01.11.2026). Bewusst nicht adjustSize(): das änderte je Schritt
        auch die Breite (und damit die Lage von „Weiter“) und machte das Fenster für einen
        langen Speicherpfad so breit, dass es rechts aus dem Bildschirm ragte. Die Unterkante
        hält danach resizeEvent/_im_bildschirm_halten fest."""
        hoehe = self.layout().totalHeightForWidth(self.width())
        if hoehe > 0 and hoehe != self.height():
            self._eigene_groessenaenderung = True
            try:
                self.resize(self.width(), max(hoehe, self.minimumSizeHint().height()))
            finally:
                self._eigene_groessenaenderung = False

    def fehler(self, text: str) -> None:
        # Verifikation A6, Befund 1: erst zurück zum fehlerhaften Schritt - sonst stand der
        # Fehler unter einem alten Text und kein Knopf führte zurück.
        if self._rueckblick is not None:
            self._rueckblick = None
            self._texte_zeigen(self._verlauf[-1], rueckblick=False)
        self.zurueck_btn.setVisible(False)
        self.hinweis(text)
        self.weiter_btn.setEnabled(False)

    def ausweichen(self, ziel: QWidget | None) -> None:
        """Rückt das Fenster in die andere untere Ecke, wenn es das markierte Element
        verdeckt - aber nur, wenn es dort das Element NICHT ebenfalls verdeckt (sonst
        sprang es bei großen Zielen wie Tabellen bei jedem Schritt hin und her,
        Desktop-Prüfung 14.10.2026, Teil 10 Nr. 2)."""
        if not _lebt(ziel) or not ziel.isVisible() or not self.isVisible():
            return
        ziel_rechteck = QRect(ziel.mapToGlobal(QPoint(0, 0)), ziel.size())
        if not self.frameGeometry().intersects(ziel_rechteck):
            return
        bildschirm = self.screen().availableGeometry()
        rechts = self.frameGeometry().center().x() < bildschirm.center().x()
        andere_ecke = QRect(self._ecke(rechts), self.frameGeometry().size())
        if not andere_ecke.intersects(ziel_rechteck):
            self._in_ecke_setzen(rechts=rechts)

    def _ecke(self, rechts: bool) -> QPoint:
        bildschirm = (self.parentWidget() or self).screen().availableGeometry()
        groesse = self.frameGeometry().size()
        x = bildschirm.right() - groesse.width() - 24 if rechts else bildschirm.left() + 24
        y = bildschirm.bottom() - groesse.height() - 48
        return QPoint(max(bildschirm.left(), x), max(bildschirm.top(), y))

    def _im_bildschirm_halten(self) -> None:
        """Unterkante verankern: Ändert sich die Höhe (anderer Schritt, „Gespeichert unter …“),
        wächst oder schrumpft das Fenster nach oben. Die Knöpfe unten, vor allem „Weiter“,
        bleiben so an derselben Stelle, statt dass man ihnen mit der Maus nachfahren muss
        (Marco 01.11.2026). Nie unter den Bildschirmrand bzw. die Taskleiste (Desktop-Prüfung
        14.10.2026, Teil 10 Nr. 1). Verschiebt der Anwender das Fenster, gilt dessen neue
        Unterkante (moveEvent)."""
        if not self._positioniert:
            return
        # Bildschirm, auf dem das Erklärfenster gerade steht (ggf. vom Anwender auf einen
        # zweiten Monitor gezogen).
        bildschirm = self.screen().availableGeometry()
        rahmen = self.frameGeometry()
        unten_max = bildschirm.bottom() - 48
        unten = min(self._unten if self._unten is not None else rahmen.bottom(), unten_max)
        oben = max(bildschirm.top(), unten - rahmen.height() + 1)
        if oben != rahmen.top():
            self.move(self.x(), oben)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if not self._eigene_groessenaenderung and self._positioniert:
            # Der Anwender zieht selbst am Rand: dort bleiben, die neue Unterkante gilt.
            self._unten = self.frameGeometry().bottom()
        self._im_bildschirm_halten()

    def moveEvent(self, event) -> None:  # type: ignore[override]
        super().moveEvent(event)
        if self._positioniert:
            self._unten = self.frameGeometry().bottom()

    def _in_ecke_setzen(self, rechts: bool) -> None:
        self.move(self._ecke(rechts))

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
