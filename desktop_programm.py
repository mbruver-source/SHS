"""
Programm-Drumherum der Desktop-Oberfläche (aus app.py ausgelagert, offene Punkte O3,
19.10.2026): Versionsfenster mit Update-Prüfung über die GitHub-API, Beenden durch
Windows/Setup (Sitzungsende) und Schutz vor einem zweiten Programmstart.

Bewusst KEIN `import app`: Läuft das Programm als `python app.py` bzw. als EXE, lebt das
Hauptfenster im Modul `__main__` - ein `import app` würde eine zweite, getrennte Kopie
laden (vgl. desktop_demo.py). Was dieses Modul aus dem Hauptfenster braucht, bekommt es
als Argument; gemeinsame Helfer liegen in desktop_gemeinsam.py.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from db import termine_ordner
from desktop_gemeinsam import (
    _ja_nein,
    _ordner_zeigen,
    _url_oeffnen,
    absturzprotokoll_pfad,
    diagnose_text,
)

if TYPE_CHECKING:  # nur für die Typangaben, zur Laufzeit nie (siehe oben)
    from app import HauptFenster

try:
    # version.py wird von bump_version.py automatisch erzeugt (siehe dort) und ist daher
    # in einer frischen Arbeitskopie vor dem allerersten Build noch nicht vorhanden - der
    # Fallback verhindert, dass das Programm deswegen gar nicht erst startet.
    from version import VERSION
except ImportError:
    VERSION = "dev"


#: Adresse der GitHub-Releases-Seite (zum Herunterladen einer neueren Version) bzw. der
#: dazugehörigen GitHub-API (zum automatischen Prüfen, ob es eine gibt) - siehe
#: VersionDialog._updates_pruefen. Seit das Repository öffentlich ist, funktioniert die
#: API-Abfrage OHNE Zugangsdaten (bei einem privaten Repository wäre dafür ein
#: angemeldetes GitHub-Konto mit Zugriff nötig gewesen - deshalb öffnete der Button
#: früher nur die Releases-Seite im Browser zum manuellen Nachschauen).
GITHUB_RELEASES_URL = "https://github.com/mbruver-source/SHS/releases"
GITHUB_LATEST_RELEASE_API_URL = "https://api.github.com/repos/mbruver-source/SHS/releases/latest"


def _version_tupel(text: str) -> tuple[int, int, int] | None:
    """Wandelt eine Versionsnummer der Form 'X.Y.Z' (optional mit führendem 'v', wie in
    GitHub-Tag-Namen üblich) in ein vergleichbares Tupel um - liefert None bei
    unerwartetem Format, statt eine Exception zu werfen (z. B. falls GitHub künftig
    einmal einen anders benannten Pre-Release als "latest" führt)."""
    text = text.strip().lstrip("vV")
    teile = text.split(".")
    if len(teile) != 3:
        return None
    try:
        a, b, c = (int(t) for t in teile)
    except ValueError:
        return None
    return (a, b, c)


def _neueste_version_pruefen() -> tuple[str | None, str | None]:
    """Fragt die öffentliche GitHub-Releases-API nach der neuesten veröffentlichten
    Version - liefert (Versionsnummer-Text ohne führendes 'v', None) bei Erfolg bzw.
    (None, verständlicher Fehlertext) bei jedem Problem (kein Internet - z. B. im
    Vereinsnetz am Prüfungstag typischerweise ohne Internetzugang -, GitHub nicht
    erreichbar, noch kein Release vorhanden usw.), damit VersionDialog (Abfrage im
    Hintergrund-Thread, siehe _updates_pruefen) dem Nutzer in jedem Fall eine verständliche
    Rückmeldung zeigen kann, statt dass das Programm an dieser Stelle abstürzt."""
    import http.client
    import json
    import ssl
    import urllib.error
    import urllib.request

    anfrage = urllib.request.Request(
        GITHUB_LATEST_RELEASE_API_URL, headers={"Accept": "application/vnd.github+json"}
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=5) as antwort:
            daten = json.loads(antwort.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None, "Es wurde noch kein Release veröffentlicht."
        return None, f"GitHub antwortete mit Fehler {exc.code}."
    except (urllib.error.URLError, OSError) as exc:
        # Desktop-Prüfung 14.10.2026 (Teil 8 Nr. 5): ein Zertifikatsfehler ist kein fehlender
        # Internetzugang.
        if isinstance(exc, ssl.SSLError) or isinstance(getattr(exc, "reason", None), ssl.SSLError):
            return None, ("Die sichere Verbindung zu GitHub ließ sich nicht prüfen (Zertifikatsfehler, "
                          "z. B. falsche Uhrzeit am Rechner oder ein Firmen-Proxy).")
        return None, "Keine Verbindung zu GitHub möglich (kein Internetzugang?)."
    except (http.client.HTTPException, ValueError):
        # Teil 8 Nr. 1: abgebrochene/kaputte Antwort (IncompleteRead u. Ä.) bzw. kein JSON.
        return None, "Die Antwort von GitHub konnte nicht gelesen werden."

    if not isinstance(daten, dict):
        return None, "Die Antwort von GitHub konnte nicht gelesen werden."
    tag = str(daten.get("tag_name", "")).strip()
    if not tag:
        return None, "GitHub hat keine Versionsnummer geliefert."
    return tag.lstrip("vV"), None


class _UpdateBote(QObject):
    """Überbringt das Ergebnis der Update-Prüfung aus dem Hintergrund-Thread an das Fenster."""
    ergebnis = Signal(int, object)


class VersionDialog(QDialog):
    """Zeigt die aktuell laufende Programmversion (siehe VERSION oben, aus version.py -
    von bump_version.py bei jedem Release automatisch erzeugt) sowie einen Button, der
    per GitHub-API prüft, ob eine neuere Version veröffentlicht wurde (siehe
    _neueste_version_pruefen oben; im Hintergrund-Thread mit Gesamtzeitgrenze). Wird über
    den Version-Button im Hauptfenster geöffnet, in der Kopfzeile oben rechts (siehe
    HauptFenster._version_anzeigen)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Version")

        titel = QLabel("SHS Prüfungsprogramm")
        schrift = titel.font()
        schrift.setPointSize(schrift.pointSize() + 2)
        schrift.setBold(True)
        titel.setFont(schrift)

        version_zeile = QLabel(f"Version {VERSION}")
        version_zeile.setTextInteractionFlags(Qt.TextSelectableByMouse)

        hinweis = QLabel(
            "Der Button unten fragt beim Klick die GitHub-Releases-Seite dieses "
            "Programms ab und zeigt an, ob eine neuere Version verfügbar ist. Dafür "
            "wird kurz eine Internetverbindung gebraucht - ohne Internet (z. B. am "
            "Prüfungstag im Vereinsnetz) erscheint stattdessen ein entsprechender "
            "Hinweis."
        )
        hinweis.setWordWrap(True)

        self._update_lauf = 0
        self._update_bote = _UpdateBote(self)
        self._update_bote.ergebnis.connect(self._update_ergebnis)
        self._updates_btn = QPushButton("Nach Updates suchen")
        self._updates_btn.clicked.connect(self._updates_pruefen)

        self._ergebnis_zeile = QLabel("")
        self._ergebnis_zeile.setWordWrap(True)
        # Reiner Text statt Qts automatischer Rich-Text-Erkennung - der angezeigte Text
        # stammt aus der GitHub-API (tag_name), ein dort manipulierter Rich-Text-artiger
        # Inhalt soll im Label keinesfalls als HTML interpretiert werden.
        self._ergebnis_zeile.setTextFormat(Qt.PlainText)
        self._ergebnis_zeile.hide()

        self._download_btn = QPushButton("Neue Version herunterladen (GitHub öffnen)")
        self._download_btn.clicked.connect(self._releases_seite_oeffnen)
        self._download_btn.hide()

        seite_link_btn = QPushButton("Releases-Seite im Browser öffnen")
        seite_link_btn.clicked.connect(self._releases_seite_oeffnen)

        # Rückmeldung Marco 13.10.2026: Diagnose für Fehlermeldungen zum Kopieren statt eines
        # Dumps mit Termindaten (siehe desktop_gemeinsam.diagnose_text).
        fehler_hinweis = QLabel(
            "Für eine Fehlermeldung die Diagnose kopieren und einfügen – sie enthält Version, "
            "System und das Ende des Absturzprotokolls, aber keine Termin-Datei. Vor dem "
            "Einfügen kurz prüfen, ob Teilnehmerdaten darin stehen (z. B. in Fehlertexten)."
        )
        fehler_hinweis.setWordWrap(True)
        diagnose_btn = QPushButton("Diagnose kopieren")
        diagnose_btn.clicked.connect(self._diagnose_kopieren)
        protokoll_btn = QPushButton("Protokoll-Ordner öffnen")
        protokoll_btn.clicked.connect(lambda: _ordner_zeigen(str(absturzprotokoll_pfad()), self))
        protokoll_btn.setEnabled(absturzprotokoll_pfad() is not None)
        self._diagnose_status = QLabel("")
        diagnose_zeile = QHBoxLayout()
        diagnose_zeile.addWidget(diagnose_btn)
        diagnose_zeile.addWidget(protokoll_btn)
        diagnose_zeile.addWidget(self._diagnose_status)
        diagnose_zeile.addStretch()

        schliessen_btn = QPushButton("Schließen")
        schliessen_btn.clicked.connect(self.accept)
        schliessen_zeile = QHBoxLayout()
        schliessen_zeile.addWidget(seite_link_btn)
        schliessen_zeile.addStretch()
        schliessen_zeile.addWidget(schliessen_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(titel)
        layout.addWidget(version_zeile)
        layout.addSpacing(8)
        layout.addWidget(hinweis)
        layout.addWidget(self._updates_btn)
        layout.addWidget(self._ergebnis_zeile)
        layout.addWidget(self._download_btn)
        layout.addSpacing(8)
        layout.addWidget(fehler_hinweis)
        layout.addLayout(diagnose_zeile)
        layout.addSpacing(8)
        layout.addLayout(schliessen_zeile)

    def _diagnose_kopieren(self) -> None:
        QApplication.clipboard().setText(diagnose_text(VERSION))
        self._diagnose_status.setText("Diagnose kopiert.")

    # Desktop-Prüfung 14.10.2026 (Teil 8 Nr. 5): die Abfrage läuft in einem Hintergrund-Thread
    # (DNS und Verbindungsaufbau haben unter urllib keine Gesamtzeitgrenze und froren sonst das
    # Fenster ein); nach UPDATE_ZEITGRENZE_MS gilt sie als gescheitert, eine spätere Antwort
    # wird verworfen.
    UPDATE_ZEITGRENZE_MS = 15000

    def _updates_pruefen(self) -> None:
        import threading

        self._updates_btn.setEnabled(False)
        self._updates_btn.setText("Wird geprüft…")
        self._download_btn.hide()
        self._ergebnis_zeile.setText("")
        self._ergebnis_zeile.hide()
        self._update_lauf += 1
        lauf = self._update_lauf
        bote = self._update_bote

        def abfragen() -> None:
            try:
                ergebnis = _neueste_version_pruefen()
            except Exception as exc:  # noqa: BLE001 - jede Antwort soll im Fenster ankommen
                ergebnis = (None, f"Die Update-Prüfung ist fehlgeschlagen ({type(exc).__name__}).")
            try:
                bote.ergebnis.emit(lauf, ergebnis)
            except RuntimeError:  # Fenster inzwischen geschlossen
                pass

        threading.Thread(target=abfragen, daemon=True).start()
        # Mit dem Fenster als Kontext: schließt es vorher, verfällt der Timer.
        QTimer.singleShot(self.UPDATE_ZEITGRENZE_MS, self, lambda: self._update_ergebnis(
            lauf, (None, "GitHub hat nicht rechtzeitig geantwortet. Bitte später erneut versuchen.")))

    def _update_ergebnis(self, lauf: int, ergebnis) -> None:
        if lauf != self._update_lauf or self._updates_btn.isEnabled():
            return  # veraltet bzw. schon beantwortet (Zeitgrenze oder Antwort)
        neueste_version, fehler = ergebnis
        try:
            self._ergebnis_anzeigen(neueste_version, fehler)
        finally:
            # Teil 8 Nr. 1: der Knopf wird in jedem Fall wieder frei.
            self._updates_btn.setEnabled(True)
            self._updates_btn.setText("Nach Updates suchen")
            self._ergebnis_zeile.show()

    def _ergebnis_anzeigen(self, neueste_version: str | None, fehler: str | None) -> None:
        if fehler is not None:
            self._ergebnis_zeile.setText(fehler)
            return
        aktuell = _version_tupel(VERSION)
        neueste = _version_tupel(neueste_version)
        if aktuell is not None and neueste is not None:
            if neueste > aktuell:
                self._ergebnis_zeile.setText(f"Neue Version {neueste_version} verfügbar (installiert: {VERSION}).")
                self._download_btn.show()
            else:
                self._ergebnis_zeile.setText("Du hast bereits die neueste Version.")
        else:
            # Teil 8 Nr. 4: nicht vergleichbare Versionsnummer - neutral statt „neueste“.
            self._ergebnis_zeile.setText(
                f"Neueste veröffentlichte Version: {neueste_version} (installiert: {VERSION}).")
            self._download_btn.show()

    def _releases_seite_oeffnen(self) -> None:
        _url_oeffnen(self, QUrl(GITHUB_RELEASES_URL), GITHUB_RELEASES_URL)


_WM_ENDSESSION = 0x0016


class SitzungsendeFilter(QAbstractNativeEventFilter):
    """H-4 (dritte Verifikation 05.10.2026): Erkennt unter Windows ein abgebrochenes
    Abmelden/Herunterfahren (WM_ENDSESSION mit wParam=FALSE) und nimmt dann die Freigabe aus
    HauptFenster._sitzungsende_pruefen zurück. Qt meldet diesen Abbruch selbst nicht - ohne
    den Filter schlösse ein späteres Fenster-X ungeprüft, neue Eingaben gingen verloren."""

    def __init__(self, fenster: "HauptFenster"):
        super().__init__()
        self._fenster = fenster

    def nativeEventFilter(self, event_type, message):
        # Läuft für jede Windows-Nachricht: ein unerwarteter Fehler darf hier nie bis zur
        # Bedienung durchschlagen (PySide6 reicht ihn sonst an den gerade laufenden
        # Python-Code weiter) - im schlimmsten Fall bleibt eine Freigabe stehen.
        try:
            if bytes(event_type) == b"windows_generic_MSG" and int(message):
                # Erst hier importiert: ctypes.wintypes gibt es sinnvoll nur unter Windows
                # (die GUI-Tests der CI laufen unter Linux und importieren app.py).
                import ctypes.wintypes

                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == _WM_ENDSESSION and not msg.wParam:
                    self._fenster._beenden_freigegeben = False
        except Exception:
            pass
        return False, 0


# Kennung, an der das Setup ein laufendes Programm erkennt (installer.iss, AppMutex).
# NIE ändern ohne installer.iss mitzuziehen - test_app_gui prüft, dass beide gleich sind.
LAUF_MUTEX_NAME = "SHS-Pruefungsprogramm-Laufend"
# Zusätzlich im globalen Namensraum: erkennt auch ein Setup unter einem anderen Konto bzw.
# eine laufende App in einer anderen Windows-Sitzung (Empfehlung der Inno-Setup-Doku).
LAUF_MUTEX_NAMEN = (LAUF_MUTEX_NAME, "Global\\" + LAUF_MUTEX_NAME)
_lauf_mutex: list = []  # Handles bleiben bis Programmende offen


# Desktop-Prüfung 14.10.2026 (Teil 8 Nr. 6, Marcos Entscheidung): ein zweiter Programmstart
# wird erkannt (QLockFile, auf allen Systemen) und nur nach Rückfrage zugelassen - zwei
# Fenster am selben Termin überschreiben sich sonst gegenseitig.
ZWEITSTART_SPERRDATEI = "programm.lock"
_zweitstart_sperre: list = []


def zweitstart_pruefen(ordner=None) -> bool:
    """True, wenn das Programm starten soll (kein anderes Fenster offen oder Rückfrage mit
    „Ja“ beantwortet). Braucht eine QApplication. Lässt sich die Sperrdatei nicht anlegen
    (Ordner schreibgeschützt), startet das Programm ohne Rückfrage."""
    from PySide6.QtCore import QLockFile

    try:
        basis = ordner if ordner is not None else termine_ordner().parent
    except OSError:
        return True
    pfad = os.path.join(str(basis), ZWEITSTART_SPERRDATEI)
    sperre = QLockFile(pfad)
    sperre.setStaleLockTime(0)  # nur ein beendetes Programm gibt die Sperre frei, keine Zeitgrenze
    if sperre.tryLock(0):
        _zweitstart_sperre.append(sperre)  # bleibt bis zum Programmende gesperrt
        return True
    if sperre.error() != QLockFile.LockFailedError:
        return True
    return _ja_nein(
        None, "Programm läuft bereits",
        "Das SHS-Prüfungsprogramm ist schon geöffnet. Arbeiten zwei Fenster am selben Termin, "
        "können sich Änderungen gegenseitig überschreiben.\n\nTrotzdem ein weiteres Fenster öffnen?",
    )


def laufkennung_setzen() -> bool:
    """Meldet das laufende Programm unter Windows mit einem benannten Mutex an.

    Anlass (Update-Test 05.10.2026): Ein Virenscanner (McAfee) hielt die EXE ebenfalls offen.
    Den darf das Setup nicht schließen, deshalb verzichtete Inno Setup ganz auf das
    automatische Schließen über den Restart Manager - die laufende App blieb unerkannt
    offen, und das Ersetzen der EXE schlug mit „Zugriff verweigert“ fehl. Über `AppMutex`
    erkennt das Setup das laufende Programm unabhängig davon gleich zu Beginn und bittet,
    es zu schließen (dann mit dem normalen Auto-Speichern und der Rückfrage). True, wenn
    die Kennung gesetzt ist (mindestens der lokale Name; der globale ist eine Zugabe)."""
    if sys.platform != "win32" or _lauf_mutex:
        return bool(_lauf_mutex)
    try:
        import ctypes

        # Eigener Prototyp statt windll.kernel32.CreateMutexW.restype prozessweit zu ändern.
        erzeugen = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p)(
            ("CreateMutexW", ctypes.windll.kernel32)
        )
        for name in LAUF_MUTEX_NAMEN:
            handle = erzeugen(None, False, name)
            if handle:
                _lauf_mutex.append(handle)
    except Exception:  # noqa: BLE001 - ohne Kennung läuft das Programm trotzdem
        pass
    return bool(_lauf_mutex)


def sitzungsende_einrichten(app: QApplication, fenster: "HauptFenster") -> None:
    """H-4: Verbindet das Beenden durch Windows/Setup mit dem Hauptfenster - Ablehnen ist
    nur in commitDataRequest möglich, closeEvent kommt erst nach der Zusage (siehe
    HauptFenster._sitzungsende_pruefen). Unter Windows zusätzlich SitzungsendeFilter für
    ein abgebrochenes Abmelden; die Referenz am Fenster hält den Filter am Leben."""
    app.commitDataRequest.connect(fenster._sitzungsende_pruefen)
    if sys.platform == "win32":
        fenster._sitzungsende_filter = SitzungsendeFilter(fenster)
        app.installNativeEventFilter(fenster._sitzungsende_filter)
