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
import sqlite3

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QInputDialog,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import checkliste
from db import get_veranstaltung, termine_ordner
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
    _db_fehler_anzeigen,
    _ja_nein,
    _fehlertext,
    _klartext_fehler,
    _pfad_anzeige,
    _wartecursor,
    fehler_protokollieren,
    kurzer_hinweis,
)


class VerwaltungTab(QWidget):
    """Verwaltungsdaten der Veranstaltung: Verein/Ort/Datum und Zusatzangaben (Vereins-Nr.,
    Prüfungsnummer, Richter 1-5, Prüfungsleiter, Prüfungsgebühr ED/DK). War früher
    Teil des Reiters "Ausdrucke/Export" (erster Button dort), steht aber inhaltlich für sich und wurde
    deshalb in einen eigenen Reiter verschoben (siehe HauptFenster._termin_setzen)."""

    # Nach dem Speichern der Veranstaltungsdaten - das Hauptfenster aktualisiert den Titel.
    veranstaltung_geaendert = Signal()

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn

        veranstaltung_btn = QPushButton("Veranstaltungsdaten bearbeiten…")
        veranstaltung_btn.setObjectName("primaerButton")  # einzige Aktion dieses Reiters, siehe _QSS_TEMPLATE
        veranstaltung_btn.clicked.connect(self._veranstaltung_bearbeiten)

        # Kurz mit Hilfe-Symbol, der volle Text im Tooltip (Marco 01.11.2026).
        hinweis = kurzer_hinweis(
            "Verein, Ort, Datum, Richter, Gebühren, angebotene Prüfungen und Startnummern-"
            "Bereiche – erscheinen in den PDFs und im Anmeldeformular.",
            "Über „Veranstaltungsdaten bearbeiten…“ lassen sich Verein, Ort und Datum "
            "sowie Vereins-Nr., Prüfungsnummer, Richter 1-5, Prüfungsleiter und die "
            "Prüfungsgebühr ED/DK nachtragen bzw. ändern - sie erscheinen im Kopf der "
            "Statistik-PDF bzw. in der Übersicht für Prüfungsleitung (siehe Reiter "
            "„Ausdrucke/Export“) und stehen oft erst kurz vor dem Prüfungstag fest. Verband, "
            "Meldestelle und die angebotenen Prüfungen bestimmen Kopf und Ankreuzfelder des "
            "Anmeldeformulars (Reiter „Ausdrucke/Export“), die Startnummern-Bereiche die Vergabe der "
            "Startnummern.",
        )

        self.status_label = QLabel("")
        self.status_label.setTextFormat(Qt.PlainText)  # S-1: enthält Pfade/Namen
        self.status_label.setWordWrap(True)

        # Checkliste zum Abhaken (Marco 09.11.2026): der Ablauf eines Termins in aufklappbaren
        # Kategorien (Standard: alle zugeklappt), je Termin gespeichert, mit eigenen Kategorien
        # und Punkten.
        self._checkliste_laedt = False
        self._checkliste_offen: set[str] = set()  # aufgeklappte Kategorien (nur für diese Sitzung)
        self._checkliste_signatur = None
        self._checkliste_kategorien: list[checkliste.Kategorie] = []
        self.checkliste_felder: dict[str, QCheckBox] = {}
        self.checkliste_koepfe: dict[str, QToolButton] = {}
        self.checkliste_inhalte: dict[str, QWidget] = {}
        self.checkliste_stand = QLabel("")
        kategorie_btn = QPushButton("Kategorie hinzufügen…")
        kategorie_btn.clicked.connect(self._checkliste_kategorie_hinzufuegen)
        zuruecksetzen_btn = QPushButton("Alle Haken entfernen")
        zuruecksetzen_btn.clicked.connect(self._checkliste_zuruecksetzen)
        self._checkliste_inhalt = QWidget()
        self._checkliste_liste = QVBoxLayout(self._checkliste_inhalt)
        bildlauf = self._checkliste_bildlauf = QScrollArea()
        bildlauf.setWidgetResizable(True)
        bildlauf.setWidget(self._checkliste_inhalt)
        kopf = QHBoxLayout()
        kopf.addWidget(QLabel("Checkliste zum Prüfungstermin"))
        kopf.addWidget(self.checkliste_stand)
        kopf.addStretch()
        kopf.addWidget(kategorie_btn)
        kopf.addWidget(zuruecksetzen_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Verwaltung"))
        layout.addWidget(veranstaltung_btn)
        layout.addWidget(hinweis)
        layout.addLayout(kopf)
        layout.addWidget(bildlauf, 1)
        layout.addWidget(self.status_label)
        self.aktualisieren()

    def aktualisieren(self) -> None:
        """Liest die Checkliste frisch aus der Datenbank (die Veranstaltungsdaten selbst werden
        bei jedem Öffnen des Dialogs frisch gelesen)."""
        veranstaltung = get_veranstaltung(self.conn)
        kategorien = checkliste.struktur(veranstaltung)
        if kategorien != self._checkliste_kategorien:
            self._checkliste_aufbauen(kategorien)
        erledigt = checkliste.erledigte(veranstaltung)
        self._checkliste_laedt = True
        try:
            for kennung, feld in self.checkliste_felder.items():
                feld.setChecked(kennung in erledigt)
        finally:
            self._checkliste_laedt = False
        self._checkliste_stand_anzeigen(erledigt)

    def zur_checkliste(self) -> None:
        """Zeigt die Checkliste: klappt die erste Kategorie mit offenen Punkten auf (sind alle
        erledigt, bleibt der Zustand) und setzt den Fokus darauf."""
        self.aktualisieren()
        erledigt = checkliste.erledigte(get_veranstaltung(self.conn))
        for kat in self._checkliste_kategorien:
            if any(p.kennung not in erledigt for p in kat.punkte):
                kopf = self.checkliste_koepfe[kat.schluessel]
                if not kopf.isChecked():
                    kopf.setChecked(True)  # klappt auf (und merkt es für diese Sitzung)
                kopf.setFocus()
                self._checkliste_bildlauf.ensureWidgetVisible(kopf)
                return
        self.checkliste_stand.setFocus()

    def _checkliste_aufbauen(self, kategorien: list) -> None:
        """Baut Kategorien und Punkte neu auf (nur wenn sich die Struktur geändert hat)."""
        self._checkliste_kategorien = kategorien
        liste = self._checkliste_liste
        while liste.count():
            eintrag = liste.takeAt(0)
            if eintrag.widget() is not None:
                eintrag.widget().setParent(None)
                eintrag.widget().deleteLater()
        self.checkliste_felder.clear()
        self.checkliste_koepfe.clear()
        self.checkliste_inhalte.clear()
        for kat in kategorien:
            kopf = QToolButton()
            kopf.setCheckable(True)
            kopf.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            kopf.setStyleSheet("font-weight: bold; text-align: left;")
            kopf.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            inhalt = QWidget()
            zeilen = QVBoxLayout(inhalt)
            zeilen.setContentsMargins(28, 0, 0, 8)
            for punkt in kat.punkte:
                zeile = QHBoxLayout()
                feld = QCheckBox(punkt.text)
                feld.toggled.connect(lambda _an: self._checkliste_geaendert())
                self.checkliste_felder[punkt.kennung] = feld
                zeile.addWidget(feld, 1)
                if punkt.eigen:
                    loeschen = QToolButton()
                    loeschen.setText("✕")
                    loeschen.setToolTip("Diesen eigenen Punkt löschen")
                    loeschen.clicked.connect(lambda _=False, k=punkt.kennung: self._checkliste_punkt_loeschen(k))
                    zeile.addWidget(loeschen)
                zeilen.addLayout(zeile)
            fuss = QHBoxLayout()
            neu_btn = QPushButton("Punkt hinzufügen…")
            neu_btn.clicked.connect(lambda _=False, k=kat.schluessel: self._checkliste_punkt_hinzufuegen(k))
            fuss.addWidget(neu_btn)
            if kat.eigen:
                weg_btn = QPushButton("Kategorie löschen")
                weg_btn.clicked.connect(lambda _=False, k=kat.schluessel: self._checkliste_kategorie_loeschen(k))
                fuss.addWidget(weg_btn)
            fuss.addStretch()
            zeilen.addLayout(fuss)
            offen = kat.schluessel in self._checkliste_offen
            inhalt.setVisible(offen)
            kopf.setChecked(offen)
            kopf.setArrowType(Qt.DownArrow if offen else Qt.RightArrow)
            kopf.toggled.connect(lambda an, k=kat.schluessel, i=inhalt, b=kopf: self._checkliste_klappen(k, i, b, an))
            self.checkliste_koepfe[kat.schluessel] = kopf
            self.checkliste_inhalte[kat.schluessel] = inhalt
            liste.addWidget(kopf)
            liste.addWidget(inhalt)
        liste.addStretch()

    def _checkliste_klappen(self, schluessel: str, inhalt: QWidget, kopf: QToolButton, auf: bool) -> None:
        inhalt.setVisible(auf)
        kopf.setArrowType(Qt.DownArrow if auf else Qt.RightArrow)
        if auf:
            self._checkliste_offen.add(schluessel)
        else:
            self._checkliste_offen.discard(schluessel)

    def _checkliste_stand_anzeigen(self, erledigt: set[str]) -> None:
        alle = checkliste.alle_kennungen(self._checkliste_kategorien)
        self.checkliste_stand.setText(f"{len(erledigt & set(alle))} von {len(alle)} erledigt")
        for kat in self._checkliste_kategorien:
            kennungen = {p.kennung for p in kat.punkte}
            self.checkliste_koepfe[kat.schluessel].setText(
                f"{kat.titel}  ({len(erledigt & kennungen)} von {len(kennungen)})")

    def _checkliste_geaendert(self) -> None:
        if self._checkliste_laedt:
            return
        erledigt = {k for k, feld in self.checkliste_felder.items() if feld.isChecked()}
        reihenfolge = checkliste.alle_kennungen(self._checkliste_kategorien)
        if self._checkliste_speichern(checkliste=checkliste.als_text(erledigt, reihenfolge)):
            self._checkliste_stand_anzeigen(erledigt)

    def _checkliste_speichern(self, **felder) -> bool:
        try:
            _aktualisiere_veranstaltung_feld(self.conn, **felder)
        except Exception as exc:  # noqa: BLE001 - Datenbankfehler als Meldung statt Absturz
            _db_fehler_anzeigen(self, exc)
            self.aktualisieren()
            return False
        return True

    def _checkliste_eigene_aendern(self, aenderung, **weitere) -> None:
        """Wendet `aenderung(eigene)` auf die eigenen Kategorien/Punkte an und speichert; die
        Haken gelöschter Punkte entfallen mit."""
        veranstaltung = get_veranstaltung(self.conn)
        try:
            eigene = aenderung(checkliste.eigene_lesen(veranstaltung))
        except ValueError as fehler:
            self.status_label.setText(str(fehler))
            return
        nach = dict(veranstaltung or {}, checkliste_eigene=checkliste.eigene_als_text(eigene))
        gueltig = checkliste.alle_kennungen(checkliste.struktur(nach))
        felder = {"checkliste_eigene": nach["checkliste_eigene"],
                  "checkliste": checkliste.als_text(checkliste.erledigte(veranstaltung), gueltig)}
        felder.update(weitere)
        if self._checkliste_speichern(**felder):
            self.aktualisieren()

    def _checkliste_kategorie_hinzufuegen(self) -> None:
        name, ok = QInputDialog.getText(self, "Kategorie hinzufügen", "Name der neuen Kategorie:")
        if ok and name.strip():
            self._checkliste_eigene_aendern(lambda e: checkliste.kategorie_hinzufuegen(e, name))

    def _checkliste_punkt_hinzufuegen(self, schluessel: str) -> None:
        text, ok = QInputDialog.getText(self, "Punkt hinzufügen", "Text des neuen Punkts:")
        if ok and text.strip():
            self._checkliste_offen.add(schluessel)
            self._checkliste_eigene_aendern(lambda e: checkliste.punkt_hinzufuegen(e, schluessel, text))

    def _checkliste_punkt_loeschen(self, kennung: str) -> None:
        if _ja_nein(self, "Punkt löschen", "Diesen eigenen Punkt der Checkliste löschen?"):
            self._checkliste_eigene_aendern(lambda e: checkliste.punkt_loeschen(e, kennung))

    def _checkliste_kategorie_loeschen(self, schluessel: str) -> None:
        if _ja_nein(self, "Kategorie löschen", "Diese eigene Kategorie mit allen ihren Punkten löschen?"):
            self._checkliste_offen.discard(schluessel)
            self._checkliste_eigene_aendern(lambda e: checkliste.kategorie_loeschen(e, schluessel))

    def _checkliste_zuruecksetzen(self) -> None:
        if not any(feld.isChecked() for feld in self.checkliste_felder.values()):
            return
        if not _ja_nein(self, "Haken entfernen", "Alle Haken der Checkliste dieses Termins entfernen?"):
            return
        for feld in self.checkliste_felder.values():
            feld.setChecked(False)  # speichert über _checkliste_geaendert

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

        # Kurz mit Hilfe-Symbol, der volle Text im Tooltip (Marco 01.11.2026). Das Wichtigste
        # - es sind ALLE Termine - steht in der kurzen Zeile.
        hinweis = kurzer_hinweis(
            # UX-Test 2026-11, T10: „Passwort getrennt aufbewahren“ klang, als sei ein Passwort
            # Pflicht (Werner erschrak) - es ist freiwillig.
            "Sichert ALLE Termine in eine Sicherungsdatei bzw. stellt sie daraus wieder her – "
            "auf Wunsch mit Passwort.",
            "Sichert bzw. liest ALLE Termine aus dem gemeinsamen Termine-Ordner "
            f"(„{termine_ordner()}“) als eine einzige Sicherungsdatei (Endung .zip) - nicht "
            "nur den gerade geöffneten Termin. Ein Passwort ist freiwillig. Wer eines vergibt, "
            "bewahrt es am besten getrennt von der Sicherungsdatei auf (z. B. nicht auf "
            "demselben USB-Stick).",
        )

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

    @staticmethod
    def _dateiname_vorschlag() -> str:
        """UX-Test 2026-11, T11 (Marco 04.11.2026): Tag und Umfang der Sicherung, z. B.
        "SHS-Sicherung_2026-11-04_alle-Termine.zip" (nach Datum sortierbar). Vorher (K10, 02.10.2026) standen Datum und
        Verein des geöffneten Termins im Namen - das wirkte, als sei nur dieser gesichert."""
        return f"SHS-Sicherung_{datetime.date.today().isoformat()}_alle-Termine.zip"

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

        vorschlag = os.path.join(os.path.expanduser("~"), self._dateiname_vorschlag())
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
