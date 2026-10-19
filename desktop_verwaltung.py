"""
Reiter „Verwaltung“ und „Datensicherung“ der Desktop-Oberfläche (aus app.py ausgelagert,
offene Punkte O6, 19.10.2026): Veranstaltungsdaten bearbeiten sowie Sicherungen der
Termin-Dateien erstellen und wiederherstellen (Logik in db_sicherung.py).

Bewusst KEIN `import app` (siehe desktop_programm.py): gemeinsame Helfer liegen in
desktop_gemeinsam.py.
"""

from __future__ import annotations

import datetime
import os
import re
import sqlite3

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from db import dateiname_slug, get_veranstaltung, termine_ordner
from db_sicherung import (
    PasswortFalschError,
    sicherung_erstellen,
    sicherung_inhalt,
    sicherung_wiederherstellen,
    TeilweiseWiederhergestelltError,
)
from desktop_dialoge import (
    _wiederherstellungsziele_planen,
    SicherungErstellenDialog,
    VeranstaltungsDialog,
)
from desktop_gemeinsam import (
    _aktualisiere_veranstaltung_feld,
    _ausfuehren,
    _datei_gespeichert_melden,
    _fehlertext,
    _klartext_fehler,
    _pfad_anzeige,
    _wartecursor,
    fehler_protokollieren,
)


class VerwaltungTab(QWidget):
    """Verwaltungsdaten der Veranstaltung: Verein/Ort/Datum und Zusatzangaben (Vereins-Nr.,
    Prüfungsnummer, Richter 1-5, Prüfungsleiter, Prüfungsgebühr ED/DK). War früher
    Teil des Reiters "Export" (erster Button dort), steht aber inhaltlich für sich und wurde
    deshalb in einen eigenen Reiter verschoben (siehe HauptFenster._termin_setzen)."""

    # Nach dem Speichern der Veranstaltungsdaten - das Hauptfenster aktualisiert den Titel.
    veranstaltung_geaendert = Signal()

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn

        veranstaltung_btn = QPushButton("Veranstaltungsdaten bearbeiten…")
        veranstaltung_btn.setObjectName("primaerButton")  # einzige Aktion dieses Reiters, siehe _QSS_TEMPLATE
        veranstaltung_btn.clicked.connect(self._veranstaltung_bearbeiten)

        hinweis = QLabel(
            "Über „Veranstaltungsdaten bearbeiten…“ lassen sich Verein, Ort und Datum "
            "sowie Vereins-Nr., Prüfungsnummer, Richter 1-5, Prüfungsleiter und die "
            "Prüfungsgebühr ED/DK nachtragen bzw. ändern - sie erscheinen im Kopf der "
            "Statistik-PDF bzw. in der Übersicht für Prüfungsleitung (siehe Reiter "
            "„Export“) und stehen oft erst kurz vor dem Prüfungstag fest. Verband, "
            "Meldestelle und die angebotenen Prüfungen bestimmen Kopf und Ankreuzfelder des "
            "Anmeldeformulars (Reiter „Export“), die Startnummern-Bereiche die Vergabe der "
            "Startnummern."
        )
        hinweis.setWordWrap(True)

        self.status_label = QLabel("")
        self.status_label.setTextFormat(Qt.PlainText)  # S-1: enthält Pfade/Namen
        self.status_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Verwaltung"))
        layout.addWidget(veranstaltung_btn)
        layout.addWidget(hinweis)
        layout.addStretch()
        layout.addWidget(self.status_label)

    def aktualisieren(self) -> None:
        pass  # kein Zwischenspeicher - liest bei jedem Öffnen des Dialogs frisch aus der DB

    def _veranstaltung_bearbeiten(self) -> None:
        aktuell = get_veranstaltung(self.conn) or {}
        # Über den gemeinsamen Helfer statt direkt set_veranstaltung, damit das vom
        # Zeitplan-Tab gepflegte Feld zeitplan_start dabei erhalten bleibt (dieser Dialog
        # hat dafür bewusst kein eigenes Feld, siehe ZeitplanTab). Gespeichert wird im
        # Dialog vor dem Schließen (Desktop-Prüfung 14.10.2026, Teil 2 Nr. 1).
        dialog = VeranstaltungsDialog(
            self, vorbelegung=aktuell, bearbeiten=True,
            speichern=lambda d: _aktualisiere_veranstaltung_feld(self.conn, **d.veranstaltung_werte()),
        )
        if _ausfuehren(dialog) != QDialog.Accepted:
            return
        self.status_label.setText("Veranstaltungsdaten gespeichert.")
        self.veranstaltung_geaendert.emit()


class DatensicherungTab(QWidget):
    """Export/Import ALLER Termine als ZIP-Datei (optional passwortgeschützt), unabhängig
    vom gerade im Hauptfenster geöffneten Termin - Datengrundlage ist immer der komplette
    Termine-Ordner (termine_ordner()), nicht die aktuelle Datenbankverbindung self.conn
    der übrigen Tabs. Deckt den bisher fehlenden Datensicherungsweg ab: bislang ließ sich
    der Termine-Ordner nur manuell (Datei-Explorer) sichern."""

    def __init__(self, parent=None, aktueller_pfad: str | None = None, conn=None):
        super().__init__(parent)
        # Nur für den Dateinamen-Vorschlag (K10): Prüfungsdatum und Verein des geöffneten Termins.
        self.conn = conn
        # Nur zur Erkennung eines Namenskonflikts mit dem GERADE GEÖFFNETEN Termin beim
        # Wiederherstellen (siehe _sicherung_wiederherstellen/_konflikt_abfragen) - ein
        # Überschreiben dieser Datei würde mit der noch offenen sqlite3.Connection des
        # Hauptfensters kollidieren.
        self._aktueller_pfad = aktueller_pfad

        hinweis = QLabel(
            "Sichert bzw. liest ALLE Termine aus dem gemeinsamen Termine-Ordner "
            f"(„{termine_ordner()}“) als eine einzige Sicherungsdatei (Endung .zip) - nicht "
            "nur den gerade geöffneten Termin. Das Passwort einer geschützten Sicherung "
            "am besten getrennt von der Sicherungsdatei aufbewahren (z. B. nicht auf "
            "demselben USB-Stick)."
        )
        hinweis.setWordWrap(True)

        erstellen_btn = QPushButton("Sicherung erstellen…")
        erstellen_btn.clicked.connect(self._sicherung_erstellen)

        wiederherstellen_btn = QPushButton("Sicherung wiederherstellen…")
        wiederherstellen_btn.clicked.connect(self._sicherung_wiederherstellen)

        self.status_label = QLabel("")
        self.status_label.setTextFormat(Qt.PlainText)  # S-1: enthält Pfade/Namen
        self.status_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Datensicherung"))
        layout.addWidget(hinweis)
        layout.addWidget(erstellen_btn)
        layout.addWidget(wiederherstellen_btn)
        layout.addStretch()
        layout.addWidget(self.status_label)

    def aktualisieren(self) -> None:
        pass  # kein Zwischenspeicher - liest bei jeder Aktion frisch den Termine-Ordner

    def _dateiname_vorschlag(self, mit_termin: bool = True) -> str:
        """UX-Test 02.10.2026, K10: Name mit Prüfungsdatum und Verein des geöffneten Termins,
        damit man die Sicherung später einer Prüfung zuordnen kann, z. B.
        "SHS-Sicherung_2026-11-14_Hundefreunde-Testhausen_erstellt-2026-10-03.zip".
        `mit_termin=False`: der geöffnete Termin ist nicht in der Sicherung (Teil 7 Nr. 1)."""
        heute = datetime.date.today().isoformat()
        veranstaltung = get_veranstaltung(self.conn) if self.conn is not None and mit_termin else None
        if not veranstaltung:
            return f"SHS-Sicherung_{heute}.zip"
        teile = [
            re.sub(r"[^0-9-]", "", veranstaltung["datum"] or ""),
            dateiname_slug(veranstaltung["verein"] or ""),
        ]
        mitte = "_".join(t for t in teile if t)
        return f"SHS-Sicherung_{mitte + '_' if mitte else ''}erstellt-{heute}.zip"

    def _offener_termin_im_ordner(self) -> bool:
        """Liegt der geöffnete Termin im Termine-Ordner (bzw. ist keiner geöffnet)?"""
        if not self._aktueller_pfad:
            return True
        ordner = os.path.dirname(os.path.abspath(self._aktueller_pfad))
        try:
            return os.path.samefile(ordner, termine_ordner())
        except OSError:
            return os.path.normcase(ordner) == os.path.normcase(os.path.abspath(termine_ordner()))

    def _mitsichern_abfragen(self) -> list[str] | None:
        """Desktop-Prüfung 14.10.2026 (Teil 7 Nr. 1, Marcos Entscheidung): Liegt der geöffnete
        Termin außerhalb des Termine-Ordners (z. B. auf einem USB-Stick), wäre er nicht in der
        Sicherung - deshalb fragen. Liefert die zusätzlich zu sichernden Pfade ([] = ohne ihn)
        oder None bei Abbruch."""
        if self._offener_termin_im_ordner() or not os.path.isfile(self._aktueller_pfad):
            return []
        box = QMessageBox(self)
        box.setTextFormat(Qt.PlainText)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Geöffneter Termin außerhalb des Termine-Ordners")
        box.setText(
            "Der geöffnete Termin liegt nicht im Termine-Ordner und wäre deshalb nicht in der "
            f"Sicherung:\n{_pfad_anzeige(self._aktueller_pfad)}\n\nTermine-Ordner: "
            f"{_pfad_anzeige(str(termine_ordner()))}"
        )
        mit_btn = box.addButton("Mitsichern", QMessageBox.AcceptRole)
        ohne_btn = box.addButton("Ohne ihn fortfahren", QMessageBox.ActionRole)
        box.addButton("Abbrechen", QMessageBox.RejectRole)
        box.setDefaultButton(mit_btn)
        _ausfuehren(box)
        if box.clickedButton() is mit_btn:
            return [self._aktueller_pfad]
        if box.clickedButton() is ohne_btn:
            return []
        return None

    def _sicherung_erstellen(self) -> None:
        zusaetzliche = self._mitsichern_abfragen()
        if zusaetzliche is None:
            return
        dialog = SicherungErstellenDialog(self)
        if _ausfuehren(dialog) != QDialog.Accepted:
            return
        passwort = dialog.passwort()

        mit_termin = self._offener_termin_im_ordner() or bool(zusaetzliche)
        vorschlag = os.path.join(os.path.expanduser("~"), self._dateiname_vorschlag(mit_termin))
        pfad, _ = QFileDialog.getSaveFileName(self, "Sicherung speichern", vorschlag, "ZIP-Datei (*.zip)")
        if not pfad:
            return

        roh_gesichert: list[str] = []
        try:
            with _wartecursor():
                anzahl = sicherung_erstellen(
                    pfad, passwort=passwort, zusaetzliche=zusaetzliche, roh_gesichert=roh_gesichert
                )
        except ValueError as exc:
            QMessageBox.warning(self, "Sicherung nicht möglich", str(exc))
            return
        except Exception as exc:  # breiter Fänger, z.B. Zielordner nicht beschreibbar
            QMessageBox.critical(
                self, "Sicherung fehlgeschlagen",
                f"Die Sicherung konnte nicht erstellt werden.\n\n{_fehlertext(exc)}",
            )
            return

        zusatz = ", passwortgeschützt" if passwort else ""
        self.status_label.setText(f"Sicherung erstellt: {_pfad_anzeige(pfad)} ({anzahl} Termin(e){zusatz}).")
        # UX-Test U7 (Marco 03.10.2026): auch hier ein Meldungsfenster statt nur der Statuszeile.
        # Offene Punkte O1 (Marco 18.10.2026): Dateien, die sich nicht als Termin lesen ließen,
        # sind roh gesichert - das soll der Anwender wissen.
        hinweis = None
        if roh_gesichert:
            hinweis = (
                "Diese Dateien ließen sich nicht als Termin lesen und wurden unverändert "
                "(samt einer eventuell vorhandenen Rücksprung-Datei) mitgesichert:\n"
                + "\n".join(f"• {name}" for name in roh_gesichert)
            )
        _datei_gespeichert_melden(
            self, pfad, f"Sicherung erstellt ({anzahl} Termin(e){zusatz})", datei_oeffnen_text=None,
            hinweis=hinweis,
        )

    def _sicherung_wiederherstellen(self) -> None:
        zip_pfad, _ = QFileDialog.getOpenFileName(
            self, "Sicherung auswählen", os.path.expanduser("~"), "ZIP-Datei (*.zip)"
        )
        if not zip_pfad:
            return

        passwort: str | None = None
        namen: list[str] | None = None
        # Desktop-Prüfung 14.10.2026 (Teil 7 Nr. 2): einmal ohne und dreimal mit Passwort -
        # vorher wurde das dritte eingegebene Passwort nie geprüft.
        for versuch in range(4):
            try:
                namen = sicherung_inhalt(zip_pfad, passwort=passwort)
                break
            except PasswortFalschError:
                if versuch == 3:
                    break
                titel = "Passwort erforderlich" if passwort is None else "Passwort falsch"
                text = "Diese Sicherung ist passwortgeschützt. Bitte Passwort eingeben:" if passwort is None \
                    else "Das Passwort war falsch. Bitte erneut eingeben:"
                eingabe = ""
                while not eingabe:
                    eingabe, ok = QInputDialog.getText(self, titel, text, QLineEdit.Password)
                    if not ok:
                        return
                    # Teil 7 Nr. 11: leere Eingabe kostet keinen Versuch.
                    titel, text = "Passwort fehlt", "Bitte ein Passwort eingeben:"
                passwort = eingabe
            except ValueError as exc:
                QMessageBox.warning(self, "Sicherung nicht lesbar", str(exc))
                return
            except OSError as exc:
                QMessageBox.warning(self, "Sicherung nicht lesbar",
                                    f"Die Sicherung konnte nicht gelesen werden.\n\n{_klartext_fehler(exc)}")
                return
        if namen is None:
            QMessageBox.warning(self, "Passwort falsch", "Das Passwort war auch beim dritten Versuch falsch. Abgebrochen.")
            return

        ordner = termine_ordner()
        vorhandene = {p.name for p in ordner.glob("*.sqlite")}
        # Sicherheitskorrektur Q-1 (07.10.2026), Details folgen. Teil 7 Nr. 1: nur, wenn der
        # geöffnete Termin auch wirklich im Termine-Ordner liegt (sonst ist eine gleichnamige
        # Datei dort eine andere).
        offener_name = (os.path.basename(self._aktueller_pfad).casefold()
                        if self._aktueller_pfad and self._offener_termin_im_ordner() else None)

        entscheidungen, uebersprungen = _wiederherstellungsziele_planen(
            namen, vorhandene, ordner,
            lambda name: self._konflikt_abfragen(name, ist_offener_termin=(name.casefold() == offener_name)),
        )

        if not entscheidungen:
            self.status_label.setText("Wiederherstellen abgebrochen: kein Termin ausgewählt.")
            return

        try:
            with _wartecursor():
                wiederhergestellt = sicherung_wiederherstellen(zip_pfad, entscheidungen, passwort=passwort)
        except TeilweiseWiederhergestelltError as exc:
            # QS-Prüfung 07.10.2026, Befund 3: nennen, was schon ersetzt ist.
            ursache = _klartext_fehler(exc.ursache) if isinstance(exc.ursache, BaseException) else exc.ursache
            QMessageBox.critical(
                self, "Wiederherstellen unvollständig",
                "Die Sicherung wurde nur teilweise wiederhergestellt:\n\n"
                f"{ursache}\n\n"
                "Diese Termine sind bereits aus der Sicherung übernommen:\n"
                + "\n".join(f"  • {name}" for name in exc.geschrieben),
            )
            self.status_label.setText(
                f"Wiederherstellen unvollständig: {len(exc.geschrieben)} Termin(e) wiederhergestellt."
            )
            return
        except Exception as exc:
            # Teil 9 Nr. 5: ins Absturzprotokoll - außer bei erwartbaren Datei- und
            # Prüffehlern. Eine beschädigte Sicherung ist dabei kein Programmfehler, deshalb
            # ohne den Hinweis aus _fehlertext.
            if not isinstance(exc, (OSError, sqlite3.Error, ValueError)):
                fehler_protokollieren(exc)
                beschreibung = f"{type(exc).__name__}: {exc}"
            else:
                beschreibung = _klartext_fehler(exc)
            QMessageBox.critical(
                self, "Wiederherstellen fehlgeschlagen",
                f"Die Sicherung konnte nicht wiederhergestellt werden.\n\n{beschreibung}",
            )
            return

        hinweis_uebersprungen = f", {uebersprungen} übersprungen" if uebersprungen else ""
        text = (
            f"{len(wiederhergestellt)} Termin(e) wiederhergestellt{hinweis_uebersprungen}. "
            "Neue Termine erscheinen in der Terminübersicht beim nächsten „Anderen Termin öffnen…“."
        )
        self.status_label.setText(text)
        # Teil 7 Nr. 11: wie beim Erstellen ein Meldungsfenster statt nur der Statuszeile.
        QMessageBox.information(self, "Wiederherstellen abgeschlossen", text)

    def _konflikt_abfragen(self, dateiname: str, ist_offener_termin: bool = False) -> str:
        """Fragt bei einem Namenskonflikt (Termin existiert bereits) nach, wie verfahren
        werden soll. Gibt "ueberschreiben", "kopie" oder "ueberspringen" zurück. Ist
        `dateiname` gerade der im Hauptfenster geöffnete Termin, wird "Überschreiben" gar
        nicht erst angeboten - die noch offene Datenbankverbindung würde damit kollidieren
        (auf Windows vermutlich mit einer schwer verständlichen Dateisperren-Fehlermeldung)."""
        box = QMessageBox(self)
        box.setTextFormat(Qt.PlainText)  # S-1: Dateiname nie als HTML deuten
        box.setWindowTitle("Termin bereits vorhanden")
        text = f"Der Termin „{dateiname}“ ist im Termine-Ordner bereits vorhanden.\n\nWie soll damit verfahren werden?"
        if ist_offener_termin:
            text += (
                "\n\nDieser Termin ist gerade im Hauptfenster geöffnet und kann deshalb "
                "nicht überschrieben werden - bitte zuerst als Kopie importieren oder "
                "überspringen."
            )
        box.setText(text)
        ueberschreiben_btn = None if ist_offener_termin else box.addButton("Überschreiben", QMessageBox.AcceptRole)
        kopie_btn = box.addButton("Als Kopie importieren", QMessageBox.ActionRole)
        ueberspringen_btn = box.addButton("Überspringen", QMessageBox.RejectRole)
        box.setDefaultButton(ueberspringen_btn)
        _ausfuehren(box)

        geklickt = box.clickedButton()
        if ueberschreiben_btn is not None and geklickt is ueberschreiben_btn:
            return "ueberschreiben"
        if geklickt is kopie_btn:
            return "kopie"
        return "ueberspringen"
