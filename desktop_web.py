"""
Web-Anbindung der Desktop-Oberfläche (Marco 18.11.2026): Termin ins Web veröffentlichen und die dort
erfassten Ergebnisse zurückholen. Die Netzwerkarbeit (HTTPS mit Zertifikat-Pinning) steckt in
web_sync.py, das Passwort liegt im Windows-Tresor (web_tresor.py); dieses Modul enthält Einstellungen,
Dialoge und die beiden Abläufe. Bewusst KEIN `import app` (siehe desktop_programm.py).

Einstellungen (QSettings, Gruppe „web“): Adresse, Benutzername, Fingerabdruck des Serverzertifikats und
je Termin-Datei die Zuordnung zum Termin auf dem Server (schema_name). Nie das Passwort.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
import threading
from dataclasses import dataclass

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QSettings

import desktop_darstellung
import web_sync
import web_tresor
from db import ImportBericht, get_veranstaltung, importiere_ergebnisse_aus_liste, list_teilnehmer
from db_sicherung import auto_sicherung_erstellen
from desktop_dialoge_basis import _groesse_auf_bildschirm_begrenzen, _scrollflaeche
from desktop_gemeinsam import _ausfuehren, _db_fehler_anzeigen, _ja_nein, _wartecursor, fehler_protokollieren


# --- Einstellungen -------------------------------------------------------------------------------

@dataclass
class WebEinstellungen:
    adresse: str = ""
    benutzer: str = ""
    fingerabdruck: str = ""  # SHA-256 des Serverzertifikats, 64 Hexzeichen (klein)

    def vollstaendig(self) -> bool:
        return bool(self.adresse and self.benutzer and self.fingerabdruck)


def _einstellungen() -> QSettings:
    return QSettings(desktop_darstellung._SETTINGS_ORG, desktop_darstellung._SETTINGS_APP)


def einstellungen_lesen() -> WebEinstellungen:
    e = _einstellungen()
    return WebEinstellungen(
        adresse=str(e.value("web/adresse", "") or ""),
        benutzer=str(e.value("web/benutzer", "") or ""),
        fingerabdruck=str(e.value("web/fingerabdruck", "") or ""),
    )


def einstellungen_speichern(neu: WebEinstellungen) -> None:
    e = _einstellungen()
    e.setValue("web/adresse", neu.adresse)
    e.setValue("web/benutzer", neu.benutzer)
    e.setValue("web/fingerabdruck", neu.fingerabdruck)


def _zuordnung_schluessel(adresse: str, pfad: str) -> str:
    roh = adresse + "\n" + os.path.normcase(os.path.abspath(pfad))
    return "web/zuordnung/" + hashlib.sha256(roh.encode("utf-8")).hexdigest()[:32]


def zuordnung_lesen(adresse: str, pfad: str) -> str | None:
    """Der gemerkte Termin auf dem Server (schema_name) zu dieser Termin-Datei und diesem Server."""
    wert = str(_einstellungen().value(_zuordnung_schluessel(adresse, pfad), "") or "")
    return wert or None


def zuordnung_speichern(adresse: str, pfad: str, schema_name: str) -> None:
    _einstellungen().setValue(_zuordnung_schluessel(adresse, pfad), schema_name)


def zuordnung_vergessen(adresse: str, pfad: str) -> None:
    _einstellungen().remove(_zuordnung_schluessel(adresse, pfad))


# --- Arbeit im Hintergrund -----------------------------------------------------------------------

class _Abgebrochen(Exception):
    """Der Nutzer hat das Warten abgebrochen."""


class _Bote(QObject):
    fertig = Signal(object, object)


class _WarteDialog(QDialog):
    """Wartefenster; ohne `abbrechbar` lässt es sich weder per Esc noch per Fenster-X schließen."""

    abbrechbar = True

    def reject(self) -> None:
        if self.abbrechbar:
            super().reject()


def im_hintergrund(parent, text: str, aufgabe, abbrechbar: bool = True):
    """Führt `aufgabe()` in einem Hintergrund-Thread aus, damit das Fenster nicht einfriert (Muster
    wie VersionDialog._updates_pruefen), und zeigt solange ein Wartefenster mit „Abbrechen“. Liefert
    (Ergebnis, None) oder (None, Ausnahme); bei Abbruch (None, _Abgebrochen). Die Aufgabe darf keine
    Qt-Objekte anfassen. Eine nach dem Abbruch eintreffende Antwort wird verworfen. Ist die Aufgabe
    nicht abbrechbar (Hochladen: der Server legt den Termin sonst womöglich trotzdem an), gibt es
    keinen Abbrechen-Knopf."""
    dialog = _WarteDialog(parent)
    dialog.abbrechbar = abbrechbar
    dialog.setWindowTitle("Bitte warten")
    dialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    beschriftung = QLabel(text)
    beschriftung.setWordWrap(True)
    beschriftung.setTextFormat(Qt.PlainText)
    layout = QVBoxLayout(dialog)
    layout.addWidget(beschriftung)
    if abbrechbar:
        abbrechen = QPushButton("Abbrechen")
        abbrechen.clicked.connect(dialog.reject)
        zeile = QHBoxLayout()
        zeile.addStretch()
        zeile.addWidget(abbrechen)
        layout.addLayout(zeile)
    dialog.setMinimumWidth(360)

    zustand: dict = {}
    bote = _Bote(dialog)

    def angekommen(ergebnis, fehler) -> None:
        zustand["antwort"] = (ergebnis, fehler)
        dialog.accept()

    bote.fertig.connect(angekommen)

    def arbeiten() -> None:
        try:
            ergebnis, fehler = aufgabe(), None
        except BaseException as exc:  # noqa: BLE001 - jede Antwort soll im Fenster ankommen
            ergebnis, fehler = None, exc
        try:
            bote.fertig.emit(ergebnis, fehler)
        except RuntimeError:  # Fenster inzwischen geschlossen
            pass

    threading.Thread(target=arbeiten, daemon=True).start()
    _ausfuehren(dialog)
    return zustand.get("antwort", (None, _Abgebrochen()))


# --- Meldungen -----------------------------------------------------------------------------------

def _fehler_melden(parent, fehler: BaseException, titel: str = "Web-Verbindung") -> None:
    """Zeigt einen Fehler der Web-Verbindung. Der Text enthält nie Passwort oder Token."""
    if isinstance(fehler, web_sync.ZertifikatFehler):
        QMessageBox.critical(parent, "Zertifikat stimmt nicht", fehler.meldung)
    elif isinstance(fehler, web_sync.WebFehler):
        QMessageBox.warning(parent, titel, fehler.meldung)
    else:
        fehler_protokollieren(fehler)
        QMessageBox.warning(
            parent, titel,
            f"Programmfehler ({type(fehler).__name__}). Bitte über den Knopf „Version“ → „Diagnose "
            "kopieren“ melden.")


# --- Dialoge -------------------------------------------------------------------------------------

def _merken_text() -> str:
    """Beschriftung des Hakens „Passwort merken“ (siehe _behalten_hinweis)."""
    if web_tresor.verfuegbar():
        return "Passwort merken (im Windows-Tresor)"
    return "Passwort merken (auf diesem Rechner nicht möglich)"


def _behalten_hinweis(merken_check: QCheckBox) -> QLabel:
    """Sichtbare Erklärung unter dem Haken „Passwort merken“. UX-Test Web 19.11.2026 (E6): Ohne Windows-
    Tresor war der Haken nur ausgegraut, die Erklärung stand bloß im Tooltip. Sicherheitsprüfung U8: auch
    bei bewusst abgewähltem Haken steht da, dass das Programm das Passwort bis zum Beenden behält (E4) -
    sichtbar, solange der Haken nicht gesetzt ist."""
    if web_tresor.verfuegbar():
        text = ("Ohne Haken behält das Programm das Passwort nur bis zum Beenden (oder bis zum Wechsel des "
                "Termins) und fragt danach wieder.")
    else:
        text = ("Auf diesem Rechner gibt es keinen Windows-Tresor. Das Programm behält das Passwort deshalb nur "
                "bis zum Beenden (oder bis zum Wechsel des Termins) und fragt danach wieder.")
    hinweis = QLabel(text)
    hinweis.setWordWrap(True)
    hinweis.setVisible(not merken_check.isChecked())
    merken_check.toggled.connect(lambda gesetzt: hinweis.setVisible(not gesetzt))
    return hinweis


class _PasswortDialog(QDialog):
    """Fragt das Passwort ab, wenn keines im Tresor liegt (oder es nicht mehr stimmt)."""

    def __init__(self, parent, benutzer: str, adresse: str, hinweis: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Passwort für die Web-Version")
        text = f"Passwort für „{benutzer}“ auf {adresse}:"
        if hinweis:
            text = hinweis + "\n\n" + text
        beschriftung = QLabel(text)
        beschriftung.setWordWrap(True)
        beschriftung.setTextFormat(Qt.PlainText)
        self.passwort_feld = QLineEdit()
        self.passwort_feld.setEchoMode(QLineEdit.Password)
        self.merken_check = QCheckBox(_merken_text())
        self.merken_check.setChecked(web_tresor.verfuegbar())
        self.merken_check.setEnabled(web_tresor.verfuegbar())
        knoepfe = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        knoepfe.accepted.connect(self._pruefen)
        knoepfe.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(beschriftung)
        layout.addWidget(self.passwort_feld)
        layout.addWidget(self.merken_check)
        self.behalten_hinweis = _behalten_hinweis(self.merken_check)
        layout.addWidget(self.behalten_hinweis)
        layout.addWidget(knoepfe)
        self.setMinimumWidth(380)

    def showEvent(self, event) -> None:  # type: ignore[override]
        """Qt bemisst die Höhe umbrechender Zeilen vorab für eine geschätzte Breite; bei großer
        Schrift war der Hinweis unter dem Haken dann unten abgeschnitten (CI unter Linux,
        21.11.2026). Nach dem Anzeigen kennt der Dialog seine Breite: Höhe dafür nachziehen."""
        super().showEvent(event)
        hoehe = self.layout().totalHeightForWidth(self.width())
        if hoehe > self.height():
            self.resize(self.width(), hoehe)

    def _pruefen(self) -> None:
        if not self.passwort_feld.text():
            QMessageBox.warning(self, "Passwort fehlt", "Bitte das Passwort eingeben.")
            return
        self.accept()


def _fingerabdruck_text(hexwert: str) -> str:
    return web_sync.fingerabdruck_anzeige(hexwert)


# Woher das Passwort für „Verbindung testen“ kam (WebVerbindungsDialog._passwort_fuer_test).
_QUELLE_EINGABE, _QUELLE_TRESOR, _QUELLE_SPEICHER = "eingabe", "tresor", "speicher"


class WebVerbindungsDialog(QDialog):
    """„Web-Verbindung…“: Adresse, Benutzername, Passwort und Fingerabdruck des Serverzertifikats. Der
    Server nutzt ein selbstsigniertes Zertifikat: beim ersten Verbinden wird sein Fingerabdruck angezeigt
    und muss bestätigt werden (Trust on first use); danach vergleicht das Programm bei jeder Verbindung,
    bevor es etwas sendet."""

    def __init__(self, parent=None, einstellungen: WebEinstellungen | None = None):
        super().__init__(parent)
        self.setWindowTitle("Web-Verbindung")
        e = einstellungen or einstellungen_lesen()
        self._alte_adresse = e.adresse
        self._fingerabdruck: str | None = e.fingerabdruck or None
        self._fp_adresse: str | None = e.adresse or None

        einleitung = QLabel(
            "Zugang zum SHS-Web-Server, auf dem Termine veröffentlicht und Ergebnisse erfasst werden. "
            "Es sind nur verschlüsselte Verbindungen (https://) erlaubt, und es kann sich nur ein "
            "Administrator-Konto anmelden."
        )
        einleitung.setWordWrap(True)

        self.adresse_feld = QLineEdit(e.adresse)
        self.adresse_feld.setPlaceholderText("https://shs.example.org")
        self.benutzer_feld = QLineEdit(e.benutzer)
        self.passwort_feld = QLineEdit()
        self.passwort_feld.setEchoMode(QLineEdit.Password)
        self._passwort_bekannt = False  # siehe _passwort_stand_aktualisieren
        self._tresor_stand: dict[str, bool] = {}  # siehe _im_tresor
        self.merken_check = QCheckBox(_merken_text())
        self.merken_check.setChecked(web_tresor.verfuegbar())
        self.merken_check.setEnabled(web_tresor.verfuegbar())
        # UX-Test Web 19.11.2026 (Heinz F5): Hinweis direkt im Dialog statt eines weiteren Meldungsfensters.
        self.passwort_hinweis = QLabel(
            "Ohne Passwort hier fragt das Programm beim ersten Veröffentlichen oder Zurückholen danach.")
        self.passwort_hinweis.setWordWrap(True)
        self.passwort_feld.textChanged.connect(self._passwort_hinweis_anzeigen)

        self.fingerabdruck_label = QLabel()
        self.fingerabdruck_label.setTextFormat(Qt.PlainText)
        self.fingerabdruck_label.setWordWrap(True)
        self.fingerabdruck_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.fingerabdruck_label.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.fingerabdruck_btn = QPushButton("Fingerabdruck vom Server holen…")
        self.fingerabdruck_btn.clicked.connect(self._fingerabdruck_holen)
        self.test_btn = QPushButton("Verbindung testen")
        self.test_btn.clicked.connect(self._testen)
        self.vergessen_btn = QPushButton("Gespeichertes Passwort vergessen")
        self.vergessen_btn.clicked.connect(self._vergessen)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.PlainText)

        formular = QFormLayout()
        formular.setRowWrapPolicy(QFormLayout.WrapLongRows)
        formular.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        formular.addRow("Adresse:", self.adresse_feld)
        formular.addRow("Benutzername:", self.benutzer_feld)
        formular.addRow("Passwort:", self.passwort_feld)
        formular.addRow("", self.passwort_hinweis)
        formular.addRow("", self.merken_check)
        self.behalten_hinweis = _behalten_hinweis(self.merken_check)
        formular.addRow("", self.behalten_hinweis)
        formular.addRow("Fingerabdruck des Serverzertifikats (SHA-256):", self.fingerabdruck_label)

        knoepfe = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        knoepfe.accepted.connect(self._uebernehmen)
        knoepfe.rejected.connect(self.reject)

        # Wie die übrigen Formular-Dialoge (desktop_dialoge_basis): Inhalt in einer Scrollfläche, die
        # Startgröße richtet sich nach dem Platzbedarf des Inhalts (auch bei großer Schrift) und wird
        # nur durch den Bildschirm begrenzt - keine feste Pixelbreite.
        inhalt = QWidget()
        inhalt_layout = QVBoxLayout(inhalt)
        inhalt_layout.addWidget(einleitung)
        inhalt_layout.addLayout(formular)
        inhalt_layout.addWidget(self.fingerabdruck_btn)
        inhalt_layout.addWidget(self.test_btn)
        inhalt_layout.addWidget(self.vergessen_btn)
        inhalt_layout.addWidget(self.status_label)
        inhalt_layout.addStretch()
        self._inhalt = inhalt
        self._scroll = _scrollflaeche(inhalt)
        layout = QVBoxLayout(self)
        layout.addWidget(self._scroll, 1)
        layout.addWidget(knoepfe)
        _groesse_auf_bildschirm_begrenzen(self, 520, 420, inhalt=inhalt, hoehe_nach_inhalt=True)
        self._fingerabdruck_anzeigen()
        self._passwort_stand_aktualisieren()
        self.adresse_feld.textChanged.connect(self._adresse_geaendert)
        # Die Adresse erst nach abgeschlossener Eingabe neu bewerten (liest den Tresor), den Benutzer
        # sofort (nur Arbeitsspeicher, der Tresor-Stand je Adresse ist zwischengespeichert).
        self.adresse_feld.editingFinished.connect(self._passwort_stand_aktualisieren)
        self.benutzer_feld.textChanged.connect(self._passwort_stand_aktualisieren)

    # -- Hilfen
    def _im_tresor(self, adresse: str) -> bool:
        """Liegt für die Adresse ein Passwort im Tresor? Je Adresse nur einmal gelesen (Sicherheitsprüfung
        U8: keine Klartextkopie bei jedem Tastendruck); das gelesene Passwort wird sofort verworfen."""
        if not web_tresor.verfuegbar():
            return False
        if adresse not in self._tresor_stand:
            self._tresor_stand[adresse] = web_tresor.passwort_lesen(adresse) is not None
        return self._tresor_stand[adresse]

    def _passwort_hinweis_anzeigen(self, _text: str = "") -> None:
        self.passwort_hinweis.setVisible(not self.passwort_feld.text() and not self._passwort_bekannt)

    def _passwort_stand_aktualisieren(self, _text: str = "") -> None:
        """Platzhalter und Hinweis nach dem, was für die GERADE eingetragene Verbindung bekannt ist
        (Tresor oder Arbeitsspeicher); ändern sich Adresse, Benutzer oder Fingerabdruck im Dialog,
        gilt ein gemerktes Passwort nicht mehr (siehe _uebernehmen)."""
        adresse = self._adresse_normal()
        gespeichert = bool(adresse) and self._im_tresor(adresse)
        im_speicher = bool(adresse) and _passwort_aus_speicher(self._eingegebene_verbindung(adresse)) is not None
        if gespeichert:
            self.passwort_feld.setPlaceholderText("gespeichert – leer lassen, um es zu behalten")
        elif im_speicher:
            self.passwort_feld.setPlaceholderText("bis zum Beenden gemerkt – leer lassen, um es zu behalten")
        else:
            self.passwort_feld.setPlaceholderText("")
        self._passwort_bekannt = gespeichert or im_speicher
        self._passwort_hinweis_anzeigen()

    def _fingerabdruck_anzeigen(self) -> None:
        if self._fingerabdruck:
            self.fingerabdruck_label.setText(_fingerabdruck_text(self._fingerabdruck))
        else:
            self.fingerabdruck_label.setText("Noch nicht bestätigt – bitte „Fingerabdruck vom Server holen…“.")

    def _adresse_normal(self, melden: bool = False) -> str | None:
        try:
            return web_sync.adresse_pruefen(self.adresse_feld.text())
        except web_sync.AdressFehler as fehler:
            if melden:
                QMessageBox.warning(self, "Adresse", fehler.meldung)
            return None

    def _adresse_geaendert(self, _text: str) -> None:
        """Ein bestätigter Fingerabdruck gilt nur für die Adresse, für die er geholt wurde."""
        if self._fingerabdruck and self._adresse_normal() != self._fp_adresse:
            self._fingerabdruck = None
            self._fingerabdruck_anzeigen()
            self.status_label.setText("Die Adresse wurde geändert: der Fingerabdruck muss neu geholt und bestätigt werden.")
        # Platzhalter/Hinweis erst nach abgeschlossener Eingabe (editingFinished), siehe __init__.

    def _eingegebene_verbindung(self, adresse: str) -> WebEinstellungen:
        """Die gerade im Dialog eingetragene Verbindung (Adresse wie angegeben, Benutzer, bestätigter
        Fingerabdruck) - Schlüssel für das Passwort im Arbeitsspeicher."""
        return WebEinstellungen(adresse, self.benutzer_feld.text().strip(), self._fingerabdruck or "")

    def _passwort_fuer_test(self, adresse: str) -> tuple[str | None, str]:
        """(Passwort, Quelle) mit Quelle _QUELLE_EINGABE, _QUELLE_TRESOR oder _QUELLE_SPEICHER - damit ein
        abgelehntes Passwort genau dort verworfen wird, woher es kam (Sicherheitsprüfung U8)."""
        eingabe = self.passwort_feld.text()
        if eingabe:
            return eingabe, _QUELLE_EINGABE
        gespeichert = web_tresor.passwort_lesen(adresse) if web_tresor.verfuegbar() else None
        if gespeichert is not None:
            return gespeichert, _QUELLE_TRESOR
        return _passwort_aus_speicher(self._eingegebene_verbindung(adresse)), _QUELLE_SPEICHER

    # -- Aktionen
    def _fingerabdruck_holen(self) -> None:
        """Holt den Fingerabdruck vom Server, lässt ihn bestätigen (mit Warnung, wenn er abweicht) und
        verwirft dann ein Tresor-Passwort, das zu einem anderen Fingerabdruck gehört."""
        adresse = self._adresse_normal(melden=True)
        if adresse is None:
            return
        ergebnis, fehler = im_hintergrund(
            self, "Verbindung zum Server wird aufgebaut (es werden keine Daten gesendet)…",
            lambda: web_sync.hole_fingerabdruck(adresse))
        if isinstance(fehler, _Abgebrochen):
            return
        if fehler is not None:
            _fehler_melden(self, fehler)
            return
        hexwert = ergebnis
        bisher = self._bisherige_fingerabdruecke(adresse)
        anders = bool(bisher) and web_sync.fingerabdruck_normalisieren(hexwert) not in bisher
        # Sicherheitskorrektur S-U14 (Details nach dem Release).
        tresor_rest = not bisher and self._im_tresor(adresse)
        if anders:
            text = (
                "ACHTUNG: Der Server meldet einen ANDEREN Fingerabdruck als bisher gespeichert. Das "
                "passiert, wenn sein Zertifikat erneuert wurde - oder wenn jemand die Verbindung "
                "abhört. Bitte beim Betreiber des Servers nachfragen, ob der neue Fingerabdruck stimmt.\n\n"
                f"Neu:\n{_fingerabdruck_text(hexwert)}\n\nBisher:\n"
                + "\n".join(_fingerabdruck_text(fp) for fp in sorted(bisher))
                + "\n\nDen neuen Fingerabdruck übernehmen?")
        else:
            text = (
                f"Der Server {adresse} hat dieses Zertifikat:\n\n{_fingerabdruck_text(hexwert)}\n\n"
                "Vergleiche den Fingerabdruck mit dem, den dir der Betreiber des Servers nennt. Nur wenn "
                "beide übereinstimmen, dem Server vertrauen.\n\nDiesem Server vertrauen?")
        if not _ja_nein(self, "Fingerabdruck bestätigen", text):
            return
        war_im_tresor = False
        if anders or tresor_rest:
            war_im_tresor = self._im_tresor(adresse)
            if not self._tresor_passwort_verwerfen(adresse):
                return
        self._fingerabdruck = hexwert
        self._fp_adresse = adresse
        self._fingerabdruck_anzeigen()
        self._passwort_stand_aktualisieren()
        self.status_label.setText(
            "Fingerabdruck bestätigt. Das gespeicherte Passwort gehörte zum bisherigen Fingerabdruck und wurde "
            "entfernt - bitte neu eingeben. Mit „OK“ speichern." if war_im_tresor
            else "Fingerabdruck bestätigt. Mit „OK“ speichern.")

    def _tresor_passwort_verwerfen(self, adresse: str) -> bool:
        """Teil der Sicherheitskorrektur S-U14 (Details nach dem Release). False (mit Meldung), wenn das
        Entfernen aus dem Tresor scheitert."""
        if not web_tresor.verfuegbar():
            return True
        if not web_tresor.passwort_loeschen(adresse):
            QMessageBox.warning(
                self, "Passwort nicht entfernt",
                "Das gespeicherte Passwort dieses Servers ließ sich nicht aus dem Windows-Tresor entfernen. "
                "Der neue Fingerabdruck wurde deshalb nicht übernommen. Bitte zuerst „Gespeichertes "
                "Passwort vergessen“ versuchen.")
            return False
        self._tresor_stand[adresse] = False
        return True

    def _bisherige_fingerabdruecke(self, adresse: str) -> set[str]:
        """Für diese Adresse bisher bestätigte Fingerabdrücke (gespeichert und im Dialog), normalisiert."""
        kandidaten = []
        gespeichert = einstellungen_lesen()
        if gespeichert.adresse == adresse:
            kandidaten.append(gespeichert.fingerabdruck)
        if self._fp_adresse == adresse and self._fingerabdruck:
            kandidaten.append(self._fingerabdruck)
        return {fp for fp in map(web_sync.fingerabdruck_normalisieren, kandidaten) if fp}

    def _testen(self) -> None:
        adresse = self._adresse_normal(melden=True)
        if adresse is None:
            return
        if not self._fingerabdruck or self._fp_adresse != adresse:
            QMessageBox.warning(self, "Fingerabdruck fehlt", "Bitte zuerst den Fingerabdruck holen und bestätigen.")
            return
        benutzer = self.benutzer_feld.text().strip()
        passwort, quelle = self._passwort_fuer_test(adresse)
        if not benutzer or not passwort:
            QMessageBox.warning(self, "Zugangsdaten fehlen", "Bitte Benutzername und Passwort eingeben.")
            return
        fingerabdruck = self._fingerabdruck
        angemeldet = []

        def pruefen():
            client = web_sync.WebClient(adresse, fingerabdruck)
            client.anmelden(benutzer, passwort)
            angemeldet.append(True)
            return len(client.termine())

        anzahl, fehler = im_hintergrund(self, "Verbindung wird getestet…", pruefen)
        if isinstance(fehler, _Abgebrochen):
            return
        if fehler is not None:
            self.status_label.setText("Verbindungstest fehlgeschlagen.")
            # Nur ein 401 der ANMELDUNG heißt „Passwort falsch“ (wie in mit_web_anmeldung). Ein abgelehntes
            # gemerktes Passwort wird dort verworfen, woher es kam (E4, Sicherheitsprüfung U8).
            if isinstance(fehler, web_sync.AnmeldeFehler) and fehler.status == 401 and not angemeldet:
                if quelle == _QUELLE_SPEICHER:
                    passwort_vergessen()
                elif quelle == _QUELLE_TRESOR:
                    web_tresor.passwort_loeschen(adresse)
                    self._tresor_stand.pop(adresse, None)
                self._passwort_stand_aktualisieren()
            _fehler_melden(self, fehler)
            return
        self.status_label.setText(f"Verbindung in Ordnung. Auf dem Server liegen {anzahl} Termin(e).")

    def _vergessen(self) -> None:
        adresse = self._adresse_normal() or self._alte_adresse
        im_speicher = passwort_im_speicher()
        passwort_vergessen()  # E4: auch das im Arbeitsspeicher gehaltene Passwort
        self._tresor_stand.clear()
        self._passwort_bekannt = False
        self.passwort_feld.clear()
        self.passwort_feld.setPlaceholderText("")
        self._passwort_hinweis_anzeigen()
        if not adresse or not web_tresor.verfuegbar():
            self.status_label.setText("Das gemerkte Passwort wurde vergessen." if im_speicher
                                      else "Es ist kein Passwort gespeichert.")
            return
        if not web_tresor.passwort_loeschen(adresse):
            # QS U19: ehrlich melden statt „entfernt“ (sonst Kreislauf mit dem Hinweis aus _fingerabdruck_holen).
            self.status_label.setText(
                "Das gespeicherte Passwort ließ sich nicht aus dem Windows-Tresor entfernen. Bitte in der "
                "Windows-Anmeldeinformationsverwaltung (Windows-Anmeldeinformationen) den Eintrag dieses "
                "Servers löschen.")
            return
        self.status_label.setText("Das gespeicherte Passwort wurde aus dem Windows-Tresor entfernt"
                                  + (" und das bis zum Beenden gemerkte vergessen." if im_speicher else "."))

    def _uebernehmen(self) -> None:
        adresse = self._adresse_normal(melden=True)
        if adresse is None:
            return
        benutzer = self.benutzer_feld.text().strip()
        if not benutzer:
            QMessageBox.warning(self, "Benutzername fehlt", "Bitte den Benutzernamen eingeben.")
            return
        if not self._fingerabdruck or self._fp_adresse != adresse:
            QMessageBox.warning(
                self, "Fingerabdruck fehlt",
                "Bitte zuerst „Fingerabdruck vom Server holen…“ und bestätigen - ohne ihn kann das "
                "Programm nicht prüfen, ob es mit dem richtigen Server spricht.")
            return
        if self._alte_adresse and self._alte_adresse != adresse and web_tresor.verfuegbar():
            web_tresor.passwort_loeschen(self._alte_adresse)  # nicht beim alten Server liegen lassen
        neu = WebEinstellungen(adresse, benutzer, self._fingerabdruck)
        alt_passwort = _passwort_aus_speicher(neu)  # None, wenn sich die Verbindung geändert hat
        einstellungen_speichern(neu)
        passwort = self.passwort_feld.text()
        im_tresor = False
        if web_tresor.verfuegbar():
            if not self.merken_check.isChecked():
                web_tresor.passwort_loeschen(adresse)
            elif passwort:
                im_tresor = web_tresor.passwort_speichern(adresse, benutzer, passwort)
                if not im_tresor:
                    QMessageBox.information(
                        self, "Passwort nicht gespeichert",
                        "Das Passwort ließ sich nicht im Windows-Tresor speichern. Das Programm behält es "
                        "bis zum Beenden und fragt danach wieder.")
        # E4: ein hier eingetipptes Passwort gilt bis zum Programmende (nur im Arbeitsspeicher), außer es
        # liegt jetzt im Tresor (keine zweite Kopie, Sicherheitsprüfung U8); bei geänderten
        # Verbindungsdaten wird ein früher gemerktes verworfen.
        _passwort_merken(neu, "" if im_tresor else (passwort or alt_passwort or ""))
        self.accept()


# --- Zugang für die Abläufe ----------------------------------------------------------------------

class _Sitzung:
    """Merkt das Passwort für die Dauer eines Ablaufs, damit er nicht zweimal danach fragt."""

    def __init__(self):
        self.passwort: str | None = None
        self.aus_tresor = False  # liegt das Passwort im Windows-Tresor (siehe mit_web_anmeldung)


# --- Passwort im Arbeitsspeicher (UX-Test Web 19.11.2026, E4, Marco) -----------------------------
#
# Ohne „Passwort merken“ (oder ohne Windows-Tresor) fragte das Programm bei JEDEM Veröffentlichen und
# Zurückholen erneut nach dem Passwort, auch wenn es eben im Dialog „Web-Verbindung“ stand. Jetzt hält
# es das Passwort bis zum Programmende im Arbeitsspeicher - nie auf der Platte, nie in Einstellungen,
# Protokollen oder Meldungen. Es gilt nur für genau die Verbindung (Adresse, Benutzer, Fingerabdruck),
# mit der es eingegeben wurde, und wird verworfen bei: Terminwechsel (passwort_vergessen() aus
# app._termin_setzen), geänderten Verbindungsdaten, „Gespeichertes Passwort vergessen“ und wenn der
# Server die Anmeldung ablehnt (401). Zugriff nur über die Funktionen unten (lesen, merken, vergessen,
# passwort_im_speicher); nur der GUI-Thread benutzt sie.

_passwort_speicher: tuple[tuple[str, str, str], str] | None = None


def _verbindungs_schluessel(e: WebEinstellungen) -> tuple[str, str, str]:
    return (e.adresse, e.benutzer, web_sync.fingerabdruck_normalisieren(e.fingerabdruck) or "")


def _passwort_aus_speicher(e: WebEinstellungen) -> str | None:
    if _passwort_speicher is None or _passwort_speicher[0] != _verbindungs_schluessel(e):
        return None
    return _passwort_speicher[1]


def _passwort_merken(e: WebEinstellungen, passwort: str) -> None:
    global _passwort_speicher
    _passwort_speicher = (_verbindungs_schluessel(e), passwort) if passwort else None


def passwort_vergessen() -> None:
    """Verwirft das im Arbeitsspeicher gehaltene Passwort (z. B. beim Terminwechsel)."""
    global _passwort_speicher
    _passwort_speicher = None


def passwort_im_speicher() -> bool:
    """Hält das Programm gerade ein Passwort im Arbeitsspeicher (für irgendeine Verbindung)?"""
    return _passwort_speicher is not None


def verbindung_einrichten(parent) -> WebEinstellungen | None:
    """Öffnet „Web-Verbindung…“; liefert die gespeicherten Einstellungen oder None bei Abbruch."""
    if _ausfuehren(WebVerbindungsDialog(parent)) != QDialog.Accepted:
        return None
    return einstellungen_lesen()


def einstellungen_sicherstellen(parent) -> WebEinstellungen | None:
    e = einstellungen_lesen()
    if e.vollstaendig() and web_sync.fingerabdruck_normalisieren(e.fingerabdruck):
        return e
    QMessageBox.information(
        parent, "Web-Verbindung einrichten",
        "Für die Web-Version fehlen noch Adresse, Benutzername und der bestätigte Fingerabdruck des "
        "Servers. Sie werden jetzt abgefragt.")
    e = verbindung_einrichten(parent)
    return e if e is not None and e.vollstaendig() else None


def mit_web_anmeldung(parent, aufgabe, wartetext: str, sitzung: _Sitzung | None = None,
                      abbrechbar: bool = True):
    """Meldet sich am Server an und führt `aufgabe(client)` im Hintergrund aus. Liefert (True, Ergebnis)
    oder (False, None) nach Abbruch bzw. gemeldetem Fehler (die Meldung ist dann schon gezeigt).
    Das Passwort kommt aus dem Windows-Tresor, sonst aus dem Arbeitsspeicher (bis Programmende gemerkt,
    siehe _passwort_speicher), sonst aus einer Abfrage; ein abgelehntes gespeichertes
    Passwort wird vergessen und neu abgefragt (höchstens dreimal)."""
    e = einstellungen_sicherstellen(parent)
    if e is None:
        return False, None
    sitzung = sitzung or _Sitzung()
    passwort = sitzung.passwort
    aus_tresor = sitzung.aus_tresor if passwort is not None else False
    if passwort is None:
        passwort = web_tresor.passwort_lesen(e.adresse)
        aus_tresor = passwort is not None
    if passwort is None:
        passwort = _passwort_aus_speicher(e)  # E4: bis Programmende im Arbeitsspeicher
    merken_neu = False
    hinweis = ""
    for _versuch in range(3):
        if passwort is None:
            dialog = _PasswortDialog(parent, e.benutzer, e.adresse, hinweis)
            if _ausfuehren(dialog) != QDialog.Accepted:
                return False, None
            passwort = dialog.passwort_feld.text()
            merken_neu = dialog.merken_check.isChecked() and web_tresor.verfuegbar()
            aus_tresor = False
        aktuelles = passwort

        angemeldet = []

        def arbeit(adresse=e.adresse, fingerabdruck=e.fingerabdruck, benutzer=e.benutzer, pw=aktuelles,
                   angemeldet=angemeldet):
            client = web_sync.WebClient(adresse, fingerabdruck)
            client.anmelden(benutzer, pw)
            angemeldet.append(True)
            return aufgabe(client)

        ergebnis, fehler = im_hintergrund(parent, wartetext, arbeit, abbrechbar)
        if fehler is None:
            sitzung.passwort = passwort
            im_tresor = aus_tresor or (merken_neu and web_tresor.passwort_speichern(e.adresse, e.benutzer, passwort))
            sitzung.aus_tresor = bool(im_tresor)
            # E4: nur behalten, was NICHT im Tresor liegt - keine zweite, langlebige Kopie eines
            # Tresor-Passworts im Arbeitsspeicher (Sicherheitsprüfung U8).
            _passwort_merken(e, "" if im_tresor else passwort)
            return True, ergebnis
        if isinstance(fehler, _Abgebrochen):
            return False, None
        # Nur ein 401 der ANMELDUNG heißt „Passwort falsch“; ein späteres 401 (Token) vergisst nichts.
        if isinstance(fehler, web_sync.AnmeldeFehler) and fehler.status == 401 and not angemeldet:
            if aus_tresor:
                web_tresor.passwort_loeschen(e.adresse)
                hinweis = "Das gespeicherte Passwort wurde nicht angenommen und vergessen."
            else:
                hinweis = "Das Passwort wurde nicht angenommen."
            passwort = None
            sitzung.passwort = None
            sitzung.aus_tresor = False
            passwort_vergessen()
            continue
        _fehler_melden(parent, fehler)
        return False, None
    QMessageBox.warning(parent, "Anmeldung fehlgeschlagen", "Die Anmeldung ist mehrfach fehlgeschlagen. Bitte „Web-Verbindung…“ prüfen.")
    return False, None


# --- Bericht -------------------------------------------------------------------------------------

def bericht_text(bericht: ImportBericht) -> tuple[str, str]:
    """(Zusammenfassung, Einzelheiten) des Ergebnis-Imports aus dem Web, als reiner Text.

    UX-Test Web 19.11.2026 (E1, E2): Die Zusammenfassung nennt „geändert / unverändert“ (gezählt werden nur
    Teilnehmer, bei denen sich in der Datei etwas geändert hat - die Frage davor nennt alle aus dem Web),
    die übernommenen und die im Web gelöschten Notizen und nur die Sonderfälle, die tatsächlich vorkamen; „im Web leer“ heißt: im
    Web leer, in der Datei aber gefüllt (sonst widersprach „0 … leer“ den sichtbar leeren Disziplinen)."""
    saetze = [f"{bericht.aktualisiert} Teilnehmer geändert, {bericht.unveraendert} unverändert."]
    if bericht.notizen_uebernommen:
        saetze.append(f"{bericht.notizen_uebernommen} Notiz(en) zum Bewertungsbogen übernommen "
                      "(sichtbar im PDF-Bewertungsbogen).")
    if bericht.notizen_geloescht:
        saetze.append(f"{bericht.notizen_geloescht} Notiz(en) im Web gelöscht und in der Datei entfernt.")
    sonderfaelle = [
        (len(bericht.status_geaendert), "Status (Disqualifikation/Abbruch) geändert"),
        (len(bericht.abweichungen), "nicht übernommen (anderer Teilnehmer unter derselben Startnummer)"),
        (len(bericht.nicht_gefunden), "Startnummer(n) in dieser Datei nicht gefunden"),
        (len(bericht.ohne_startnummer_uebersprungen), "ohne Startnummer übersprungen"),
        (len(bericht.im_web_leer), "Disziplin(en) im Web leer, in dieser Datei gefüllt (Wert der Datei blieb)"),
        (len(bericht.fehler), "Fehler"),
    ]
    vorhanden = [f"{anzahl} {text}" for anzahl, text in sonderfaelle if anzahl]
    if vorhanden:
        saetze.append("Außerdem: " + ", ".join(vorhanden) + ".")
    zusammenfassung = " ".join(saetze)
    teile = []

    def abschnitt(titel: str, eintraege) -> None:
        if eintraege:
            teile.append(titel + "\n" + "\n".join(f"  • {eintrag}" for eintrag in eintraege))

    abschnitt("Nicht übernommen - anderer Teilnehmer unter dieser Startnummer:", bericht.abweichungen)
    abschnitt("Disqualifikation/Abbruch aus dem Web übernommen (Stand der Datei ersetzt):", bericht.status_geaendert)
    abschnitt("Im Web leer, in der Termin-Datei gefüllt (Wert der Datei beibehalten):", bericht.im_web_leer)
    abschnitt("Startnummern, die es in dieser Termin-Datei nicht gibt:", bericht.nicht_gefunden)
    abschnitt("Ohne Startnummer übersprungen:", bericht.ohne_startnummer_uebersprungen)
    abschnitt("Fehler:", bericht.fehler)
    teile.append(
        "Hinweis: Disqualifikation und Abbruch (mit Grund) werden aus dem Web übernommen; der Web-Stand "
        "ersetzt die Werte der Datei.")
    if bericht.notizen_uebernommen:
        teile.append("Die Notizen der Richter stehen auf dem Bewertungsbogen (PDF), im Desktop-Programm werden "
                     "sie nicht angezeigt.")
    return zusammenfassung, "\n\n".join(teile)


class WebBerichtDialog(QDialog):
    """Zeigt den Bericht des Ergebnis-Imports (Zusammenfassung oben, Einzelheiten scrollbar)."""

    def __init__(self, parent, bericht: ImportBericht, titel_zusatz: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Ergebnisse aus dem Web übernommen")
        zusammenfassung, einzelheiten = bericht_text(bericht)
        kopf = QLabel((titel_zusatz + "\n\n" if titel_zusatz else "") + zusammenfassung)
        kopf.setWordWrap(True)
        kopf.setTextFormat(Qt.PlainText)
        self.text_feld = QPlainTextEdit()
        self.text_feld.setReadOnly(True)
        self.text_feld.setPlainText(einzelheiten)
        schliessen = QPushButton("Schließen")
        schliessen.clicked.connect(self.accept)
        schliessen.setDefault(True)
        zeile = QHBoxLayout()
        zeile.addStretch()
        zeile.addWidget(schliessen)
        layout = QVBoxLayout(self)
        layout.addWidget(kopf)
        layout.addWidget(self.text_feld, 1)
        layout.addLayout(zeile)
        self.resize(640, 480)


# --- Abläufe -------------------------------------------------------------------------------------

def _termin_titel(conn) -> str:
    v = get_veranstaltung(conn) or {}
    teile = [str(v.get(feld) or "").strip() for feld in ("verein", "ort", "datum")]
    return ", ".join(t for t in teile if t) or "(ohne Angaben)"


def _vorbedingungen(tab, ohne_speichern: str = "fährt fort") -> bool:
    """Demo und Termine ohne Datei (PostgreSQL) sind ausgeschlossen; ungespeicherte Eingaben der
    Ergebniserfassung werden geklärt. False = Vorgang abbrechen."""
    if getattr(tab, "demo", False):
        QMessageBox.information(tab, "Demoprüfung", "In der Demoprüfung ist die Web-Verbindung gesperrt.")
        return False
    if not tab.aktueller_pfad or not hasattr(tab.conn, "backup"):
        QMessageBox.information(tab, "Web-Verbindung", "Das geht nur mit einem Termin als Datei (SQLite).")
        return False
    klaeren = getattr(tab.window(), "_ungespeicherte_ergebnisse_klaeren", None)
    if klaeren is not None and not klaeren("Trotzdem fortfahren", ohne_speichern=ohne_speichern):
        return False
    return True


def termin_veroeffentlichen(tab) -> None:
    """„Ins Web veröffentlichen…“: konsistente Kopie der Termin-Datei hochladen und den Termin auf dem
    Server der Datei zuordnen."""
    if not _vorbedingungen(tab, "lädt den gespeicherten Stand hoch,"):
        return
    e = einstellungen_sicherstellen(tab)
    if e is None:
        return
    alle = list_teilnehmer(tab.conn)
    teilnehmende = [t for t in alle if not t.get("keine_teilnahme")]
    text = (
        f"Termin „{_termin_titel(tab.conn)}“ auf {e.adresse} veröffentlichen?\n\n"
        f"Übertragen werden die Veranstaltungsdaten und {len(teilnehmende)} Teilnehmer samt "
        "bereits eingetragener Ergebnisse. Als „keine Teilnahme“ markierte Teilnehmer "
        f"({len(alle) - len(teilnehmende)}) werden nicht übernommen.\n\n"
        "Auf dem Server entsteht ein eigener Termin; diese Termin-Datei bleibt unverändert. Die Ergebnisse "
        "holst du nach der Prüfung mit „Ergebnisse aus Web holen…“ zurück.")
    if not _ja_nein(tab, "Ins Web veröffentlichen", text):
        return
    with tempfile.TemporaryDirectory(prefix="shs_web_", ignore_cleanup_errors=True) as ordner:
        kopie = os.path.join(ordner, "termin.sqlite")
        try:
            with _wartecursor():
                ziel = sqlite3.connect(kopie)
                try:
                    tab.conn.backup(ziel)
                finally:
                    ziel.close()
        except (OSError, sqlite3.Error) as exc:
            _db_fehler_anzeigen(tab, exc, "Von der Termin-Datei ließ sich keine Kopie zum Hochladen anlegen.")
            return
        begonnen = []

        def hochladen(client):
            begonnen.append(True)
            return client.veroeffentlichen(kopie)

        ok, antwort = mit_web_anmeldung(
            tab, hochladen, "Der Termin wird hochgeladen - bitte nicht abbrechen…", abbrechbar=False)
    if not ok:
        if begonnen:
            tab.status_label.setText(
                "Das Veröffentlichen wurde nicht bestätigt. Bei einer Zeitüberschreitung kann der Termin auf "
                "dem Server trotzdem angelegt sein - bitte dort prüfen, bevor erneut veröffentlicht wird.")
        return
    termin, hinweis = antwort
    zuordnung_speichern(e.adresse, tab.aktueller_pfad, termin["schema_name"])
    meldung = (
        f"Der Termin ist veröffentlicht ({termin.get('anzahl_teilnehmer', len(teilnehmende))} Teilnehmer). "
        "Die Richter können jetzt im Web Ergebnisse erfassen.")
    tab.status_label.setText("Ins Web veröffentlicht.")
    if hinweis:
        QMessageBox.warning(tab, "Ins Web veröffentlicht - bitte beachten", meldung + "\n\nHinweis des Servers:\n" + hinweis)
    else:
        QMessageBox.information(tab, "Ins Web veröffentlicht", meldung)


def _termin_waehlen(tab, termine: list[dict]) -> tuple[str, str] | None:
    """Auswahl des Servertermins, wenn die Datei noch keinem zugeordnet ist."""
    if not termine:
        QMessageBox.information(tab, "Ergebnisse aus Web holen", "Auf dem Server ist kein Termin veröffentlicht.")
        return None
    v = get_veranstaltung(tab.conn) or {}
    namen, vorbelegt = [], 0
    for i, t in enumerate(termine):
        # Die Kennung in [] unterscheidet gleichnamige Termine; der Name ohne sie steht in der Rückfrage.
        namen.append(f"{_servertermin_name(t)} ({t.get('anzahl_teilnehmer', '?')} Teilnehmer) [{t['schema_name']}]")
        if (str(t.get("datum") or "") == str(v.get("datum") or "")
                and str(t.get("verein") or "").casefold() == str(v.get("verein") or "").casefold()):
            vorbelegt = i
    auswahl, ok = QInputDialog.getItem(
        tab, "Termin auf dem Server wählen",
        "Dieser Termin-Datei ist noch kein Termin auf dem Server zugeordnet. Welcher ist es?",
        namen, vorbelegt, False)
    if not ok:
        return None
    gewaehlt = termine[namen.index(auswahl)]
    return gewaehlt["schema_name"], _servertermin_name(gewaehlt)


def _servertermin_name(t: dict) -> str:
    """„Verein, Ort, TT.MM.JJJJ“ eines Termins auf dem Server (UX-Test Web 19.11.2026, E3: statt der
    internen Kennung „termin_1“)."""
    datum = str(t.get("datum") or "")
    teile = datum.split("-")
    if len(teile) == 3 and all(teil.isdigit() for teil in teile):
        datum = f"{teile[2]}.{teile[1]}.{teile[0]}"
    return f"{t.get('verein') or '?'}, {t.get('ort') or '-'}, {datum or '-'}"


def ergebnisse_aus_web_holen(tab) -> bool:
    """„Ergebnisse aus Web holen…“: lädt die Ergebnisse des zugeordneten Servertermins und arbeitet sie
    per Startnummer in die geöffnete Termin-Datei ein (vorher automatische Sicherung). True, wenn
    übernommen wurde."""
    if not _vorbedingungen(tab, "holt die Web-Ergebnisse,"):
        return False
    e = einstellungen_sicherstellen(tab)
    if e is None:
        return False
    sitzung = _Sitzung()
    schema = zuordnung_lesen(e.adresse, tab.aktueller_pfad)
    bezeichnung = None  # Name des Servertermins (E3), beim gemerkten Termin aus der Terminliste
    if schema is None:
        ok, termine = mit_web_anmeldung(tab, lambda client: client.termine(), "Die Terminliste wird geladen…", sitzung)
        if not ok:
            return False
        wahl = _termin_waehlen(tab, termine)
        if wahl is None:
            return False
        schema, bezeichnung = wahl
    def laden(client, s=schema, name_holen=bezeichnung is None):
        try:
            liste = client.ergebnisse(s)
        except web_sync.ServerFehler as fehler:
            if fehler.status == 404:
                return None, None  # der Termin ist auf dem Server nicht (mehr) vorhanden
            raise
        name = None
        if name_holen:
            try:
                name = next((_servertermin_name(t) for t in client.termine() if t.get("schema_name") == s), None)
            except web_sync.WebFehler:
                name = None  # nur für den Text der Rückfrage - ohne Namen geht es auch
        return liste, name

    ok, antwort = mit_web_anmeldung(tab, laden, "Die Ergebnisse werden geladen…", sitzung)
    if not ok:
        return False
    liste, name = antwort
    if bezeichnung is None:
        bezeichnung = name or "zuletzt veröffentlichter Termin dieser Datei"
    if liste is None:
        zuordnung_vergessen(e.adresse, tab.aktueller_pfad)
        QMessageBox.information(
            tab, "Ergebnisse aus Web holen",
            "Den gemerkten Termin gibt es auf dem Server nicht mehr. Die Zuordnung wurde gelöscht - bitte "
            "„Ergebnisse aus Web holen…“ erneut wählen und den Termin neu aussuchen.")
        return False

    text = (
        f"Ergebnisse von {len(liste)} Teilnehmern aus dem Web-Termin „{bezeichnung}“ in "
        f"„{_termin_titel(tab.conn)}“ übernehmen?\n\n"
        "Die Ergebnisse in dieser Termin-Datei werden mit dem Stand aus dem Web überschrieben "
        "(zugeordnet über die Startnummer). Das gilt auch für Disqualifikation und Abbruch. "
        "Vorher legt das Programm eine automatische Kopie an.")
    if not _ja_nein(tab, "Ergebnisse aus Web holen", text):
        return False
    if auto_sicherung_erstellen(tab.conn, tab.aktueller_pfad, mindestabstand_sekunden=0) is None:
        if not _ja_nein(
                tab, "Sicherung nicht möglich",
                "Die automatische Kopie vor dem Überschreiben ließ sich nicht anlegen (Datenträger voll "
                "oder nicht beschreibbar?).\n\nOhne Kopie trotzdem fortfahren? Die jetzigen Ergebnisse "
                "lassen sich danach nicht wiederherstellen."):
            return False
    try:
        with _wartecursor():
            bericht = importiere_ergebnisse_aus_liste(tab.conn, liste)
    except ValueError as exc:
        QMessageBox.warning(tab, "Ergebnisse aus Web holen", str(exc))
        return False
    except Exception as exc:  # noqa: BLE001 - z. B. gesperrte Datei; je Teilnehmer wird einzeln gespeichert
        _db_fehler_anzeigen(tab, exc, "Die Ergebnisse konnten nicht (vollständig) übernommen werden.")
        tab.ergebnisse_aus_web_uebernommen.emit()
        return False
    # „Es passte kein Teilnehmer“ nur, wenn keiner zugeordnet werden konnte - seit „aktualisiert“ nur
    # wirklich Geändertes zählt, zählen unverändert passende Teilnehmer ausdrücklich mit (sonst vergaß
    # ein zweites Zurückholen ohne neue Web-Änderung die Zuordnung, sobald ein Teilnehmer abwich).
    if bericht.aktualisiert == 0 and bericht.unveraendert == 0 and (bericht.abweichungen or bericht.nicht_gefunden):
        # Vermutlich der falsche Servertermin: nicht merken, beim nächsten Mal neu wählen lassen.
        zuordnung_vergessen(e.adresse, tab.aktueller_pfad)
        tab.status_label.setText(
            "Nichts übernommen - es passte kein Teilnehmer. Der gewählte Web-Termin wurde nicht gemerkt; "
            "beim nächsten Mal kann ein anderer gewählt werden.")
    else:
        zuordnung_speichern(e.adresse, tab.aktueller_pfad, schema)
        tab.status_label.setText(
            f"Ergebnisse aus dem Web übernommen: {bericht.aktualisiert} Teilnehmer geändert, "
            f"{bericht.unveraendert} unverändert.")
    tab.ergebnisse_aus_web_uebernommen.emit()
    _ausfuehren(WebBerichtDialog(tab, bericht))
    return True
