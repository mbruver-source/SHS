"""
Kleine Überraschung für Kenner (Marco 01.11.2026): Zehn schnelle Klicks auf den Beagle im
Kopfbalken des Hauptfensters lassen ihn wachsen und in viele kleine Beagles zerspringen,
die durchs Fenster fliegen, am unteren Rand hüpfen und nach 20 Sekunden verschwinden.

Bewusst nirgends dokumentiert (Handbuch, Hilfe, Release Notes) - nur hier und als Vermerk
in Fortschritt.md. Das Programm bleibt währenddessen voll bedienbar: Die Überlagerung lässt
alle Klicks durch.

Bewusst KEIN `import app` (vgl. desktop_programm.py): Das Hauptfenster kommt als Argument.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass

from PySide6.QtCore import QElapsedTimer, QEvent, QObject, QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QPainter, QPixmap, QRegion
from PySide6.QtWidgets import QWidget

from desktop_gemeinsam import beagle_rund

#: Klicks bis zur Überraschung und längste Pause zwischen zwei Klicks (Sekunden).
KLICKS = 10
KLICK_PAUSE_S = 1.5

DAUER_S = 20.0
WACHSEN_S = 0.8
AUSBLENDEN_AB_S = 17.0
START_GROESSE = 40
GROSS = 250
TEILCHEN = 40
SCHWERKRAFT = 1400.0  # Pixel je Sekunde²
DAEMPFUNG_BODEN = 0.55
DAEMPFUNG_WAND = 0.6


@dataclass
class _Teilchen:
    x: float
    y: float
    vx: float
    vy: float
    winkel: float
    drehung: float
    groesse: float
    bild: QPixmap


class BeagleExplosion(QWidget):
    """Durchsichtige Überlagerung über dem ganzen Hauptfenster: erst wächst der Beagle vom
    Kopfbalken in die Fenstermitte, dann zerspringt er in kleine Beagles mit Schwerkraft.
    Nach DAUER_S verschwindet sie von selbst. `_schritt(dt)` lässt sich in Tests direkt
    aufrufen, statt 20 Sekunden zu warten."""

    def __init__(self, fenster: QWidget, start: QPointF, seed: int | None = None):
        super().__init__(fenster)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.beendet = False
        self._zufall = random.Random(seed)
        self._start = QPointF(start)
        self._zeit = 0.0
        self._teilchen: list[_Teilchen] = []
        # Bild nur in dieser Instanz, nicht modulweit (QPixmap überlebt sonst die
        # QApplication bis zum Aufräumen von Python, siehe tools/screenshots.py).
        self._bild: QPixmap = beagle_rund(GROSS)
        self._uhr = QElapsedTimer()
        self._takt = QTimer(self)
        if self._bild.isNull():
            # Ohne Programmsymbol gibt es nichts zu zeigen - gar nicht erst starten.
            self.beendet = True
            self.deleteLater()
            return
        self.setGeometry(fenster.rect())
        fenster.installEventFilter(self)
        self._takt.setInterval(16)
        self._takt.timeout.connect(self._ticken)
        self.show()
        self.raise_()
        self._uhr.start()
        self._takt.start()

    # --- Ablauf ------------------------------------------------------------------------

    def _ticken(self) -> None:
        # Die vergangene Zeit vollständig in kleinen Schritten nachholen: So endet alles nach
        # 20 echten Sekunden, auch wenn ein Takt länger dauert, und die Physik bleibt ruhig.
        dt = self._uhr.restart() / 1000.0
        vorher = self._bereich()
        while dt > 0 and not self.beendet:
            teil = min(dt, 0.02)
            self._schritt(teil)
            dt -= teil
        if not self.beendet:
            # Nur um die Beagles herum neu zeichnen (alte und neue Lage): Die Überlagerung ist
            # durchsichtig, ein update() des Ganzen zeichnete 20 s lang bei jedem Takt auch
            # alle Tabellen darunter neu (Verifikation 01.11.2026).
            self.update(vorher.united(self._bereich()))

    def _bereich(self) -> QRegion:
        """Fläche, die die Beagles gerade belegen (großzügig wegen der Drehung)."""
        if self._zeit < WACHSEN_S:
            lage, groesse = self._wachstum()
            kreise = [(lage.x(), lage.y(), groesse)]
        else:
            kreise = [(t.x, t.y, t.groesse) for t in self._teilchen]
        bereich = QRegion()
        for x, y, groesse in kreise:
            halb = groesse * 0.75 + 2
            bereich = bereich.united(QRect(round(x - halb), round(y - halb), round(2 * halb), round(2 * halb)))
        return bereich

    def _schritt(self, dt: float) -> None:
        if self.beendet:
            return
        vorher = self._zeit
        self._zeit += dt
        if vorher < WACHSEN_S <= self._zeit:
            self._zerspringen()
        if self._zeit >= WACHSEN_S:
            self._bewegen(dt)
        if self._zeit >= DAUER_S:
            self._beenden()

    def _mitte(self) -> QPointF:
        return QPointF(self.width() / 2, self.height() / 2)

    def _wachstum(self) -> tuple[QPointF, float]:
        """Lage und Größe des wachsenden Beagles (weich auslaufend)."""
        p = min(1.0, self._zeit / WACHSEN_S)
        p = 1 - (1 - p) ** 3
        mitte = self._mitte()
        lage = QPointF(self._start.x() + (mitte.x() - self._start.x()) * p,
                       self._start.y() + (mitte.y() - self._start.y()) * p)
        return lage, START_GROESSE + (GROSS - START_GROESSE) * p

    def _zerspringen(self) -> None:
        mitte = self._mitte()
        z = self._zufall
        verhaeltnis = self._bild.devicePixelRatio()
        for _ in range(TEILCHEN):
            groesse = z.uniform(22, 60)
            # Je Teilchen einmal passend verkleinert - jeden Takt 40-mal aus der großen
            # Vorlage zu skalieren, war zu langsam.
            klein = self._bild.scaled(round(groesse * verhaeltnis), round(groesse * verhaeltnis),
                                      Qt.KeepAspectRatio, Qt.SmoothTransformation)
            klein.setDevicePixelRatio(verhaeltnis)
            richtung = z.uniform(0, 2 * math.pi)
            tempo = z.uniform(300, 900)
            abstand = z.uniform(0, GROSS * 0.3)
            self._teilchen.append(_Teilchen(
                x=mitte.x() + math.cos(richtung) * abstand,
                y=mitte.y() + math.sin(richtung) * abstand,
                vx=math.cos(richtung) * tempo,
                vy=math.sin(richtung) * tempo - 250,  # leicht nach oben
                winkel=z.uniform(0, 360),
                drehung=z.uniform(-360, 360),
                groesse=groesse,
                bild=klein,
            ))

    def _bewegen(self, dt: float) -> None:
        breite, hoehe = self.width(), self.height()
        for t in self._teilchen:
            r = t.groesse / 2
            t.vy += SCHWERKRAFT * dt
            t.x += t.vx * dt
            t.y += t.vy * dt
            t.winkel += t.drehung * dt
            if t.y > hoehe - r:
                t.y = hoehe - r
                t.vy = -t.vy * DAEMPFUNG_BODEN
                t.vx *= 0.8
                t.drehung *= 0.7
                if abs(t.vy) < 60:  # kleine Hüpfer kommen zur Ruhe
                    t.vy = 0.0
            if t.y < r and t.vy < 0:  # Decke (Marco 01.11.2026)
                t.y, t.vy = r, -t.vy * DAEMPFUNG_WAND
            if t.x < r:
                t.x, t.vx = r, -t.vx * DAEMPFUNG_WAND
            elif t.x > breite - r:
                t.x, t.vx = breite - r, -t.vx * DAEMPFUNG_WAND

    def deckkraft(self) -> float:
        if self._zeit < AUSBLENDEN_AB_S:
            return 1.0
        return max(0.0, (DAUER_S - self._zeit) / (DAUER_S - AUSBLENDEN_AB_S))

    def _beenden(self) -> None:
        self.beendet = True
        self._takt.stop()
        self.parentWidget().removeEventFilter(self)
        self.hide()
        self.deleteLater()

    # --- Qt ----------------------------------------------------------------------------

    def eventFilter(self, beobachtet, ereignis) -> bool:  # type: ignore[override]
        if beobachtet is self.parentWidget() and ereignis.type() == QEvent.Resize:
            self.setGeometry(beobachtet.rect())
        return False

    def _zeichnen(self, maler: QPainter, bild: QPixmap, x: float, y: float, groesse: float,
                  winkel: float) -> None:
        maler.save()
        maler.translate(x, y)
        maler.rotate(winkel)
        maler.drawPixmap(QRectF(-groesse / 2, -groesse / 2, groesse, groesse), bild, QRectF(bild.rect()))
        maler.restore()

    def paintEvent(self, _ereignis) -> None:  # type: ignore[override]
        if self._bild.isNull():
            return
        maler = QPainter(self)
        maler.setRenderHint(QPainter.Antialiasing)
        maler.setRenderHint(QPainter.SmoothPixmapTransform)
        maler.setOpacity(self.deckkraft())
        if self._zeit < WACHSEN_S:
            lage, groesse = self._wachstum()
            self._zeichnen(maler, self._bild, lage.x(), lage.y(), groesse, 0.0)
        else:
            for t in self._teilchen:
                self._zeichnen(maler, t.bild, t.x, t.y, t.groesse, t.winkel)
        maler.end()


class BeagleKlickZaehler(QObject):
    """Zählt Linksklicks auf `bild` (den Beagle im Kopfbalken). Nach KLICKS schnellen
    Klicks (höchstens KLICK_PAUSE_S dazwischen) startet die BeagleExplosion über
    `fenster`; während sie läuft, startet keine zweite. Die Klicks selbst gehen normal
    weiter. `uhr` ist austauschbar (Tests)."""

    def __init__(self, fenster: QWidget, bild: QWidget, uhr=time.monotonic):
        # Das Fenster nur als Qt-Eltern, keine eigene Python-Referenz: Fenster -> Zähler ->
        # Fenster wäre ein Kreis, der ein geschlossenes Hauptfenster bis zur nächsten
        # Speicherbereinigung am Leben hielte.
        super().__init__(fenster)
        self._bild = bild
        self._uhr = uhr
        self._anzahl = 0
        self._letzter = -math.inf
        self.explosion: BeagleExplosion | None = None
        bild.installEventFilter(self)

    def eventFilter(self, beobachtet, ereignis) -> bool:  # type: ignore[override]
        if (beobachtet is self._bild and ereignis.type() == QEvent.MouseButtonPress
                and ereignis.button() == Qt.LeftButton):
            self.klick()
        return False

    def klick(self) -> None:
        jetzt = self._uhr()
        if jetzt - self._letzter > KLICK_PAUSE_S:
            self._anzahl = 0
        self._letzter = jetzt
        self._anzahl += 1
        if self._anzahl < KLICKS:
            return
        self._anzahl = 0
        if self.explosion is not None and not self.explosion.beendet:
            return
        fenster = self.parent()
        mitte = self._bild.mapTo(fenster, self._bild.rect().center())
        self.explosion = BeagleExplosion(fenster, QPointF(mitte))
