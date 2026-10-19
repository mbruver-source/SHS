"""
Reiter „Zeitplan“ der Desktop-Oberfläche (aus app.py ausgelagert, offene Punkte O5,
19.10.2026): Richter-Spuren mit frei sortierbaren Prüfungsblöcken und Pausen, automatische
Verteilung, Überschneidungsprüfung und PDF-Ausgabe. Die Planungslogik selbst steht in db.py
(Abschnitt Zeitplan).

Bewusst KEIN `import app` (siehe desktop_programm.py): gemeinsame Helfer liegen in
desktop_gemeinsam.py.
"""

from __future__ import annotations

import datetime
import html
import sqlite3

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from db import (
    add_zeitplan_pause,
    add_zeitplan_pause_bei_allen,
    add_zeitplan_pruefungsblock,
    add_zeitplan_richter,
    aktualisiere_zeitplan_eintrag,
    automatische_zeitplan_verteilung,
    berechne_zeitplan,
    dk_mindestabstand,
    get_veranstaltung,
    list_zeitplan_eintraege,
    list_zeitplan_richter,
    loesche_zeitplan_eintrag,
    loesche_zeitplan_richter,
    termine_ordner,
    umbenennen_zeitplan_richter,
    verschiebe_zeitplan_eintrag,
    verschiebe_zeitplan_richter,
    zeitplan_eintrag,
    zeitplan_gruppen_status,
    zeitplan_richter_aus_veranstaltung_anlegen,
    zeitplan_ueberschneidungen,
)
from desktop_darstellung import _farbe
from desktop_dialoge import PauseDialog, PruefungsblockDialog
from desktop_gemeinsam import (
    _Ablageort,
    _aktualisiere_veranstaltung_feld,
    _ausfuehren,
    _db_fehler_anzeigen,
    _ja_nein,
    _zeitplan_pdf_exportieren,
)


def _klartext_tooltip(text: str) -> str:
    """Sicherheitsprüfung 03.10.2026, S-1: Tooltips deutet Qt automatisch als HTML, sobald
    der Text danach aussieht. Enthält er Namen aus Importen, wird er deshalb maskiert und
    ausdrücklich als Rich Text ausgezeichnet - so erscheint er immer wörtlich."""
    return "<qt>" + html.escape(text).replace("\n", "<br>") + "</qt>"


class ZeitplanTab(QWidget):
    """Zeitplan-Planung: beliebig viele Richter-Spuren, jede mit einer frei
    sortierbaren Abfolge aus Prüfungsblöcken und Pausen (siehe db.py, Abschnitt
    "Zeitplan"). "Automatisch verteilen…" erzeugt über db.automatische_zeitplan_verteilung
    einen ausgewogenen Erstvorschlag über alle Richter, der danach beliebig von Hand
    angepasst werden kann: Reihenfolge ändern, Dauer je Block überschreiben, Pausen an
    beliebiger Stelle einfügen, Blöcke zwischen Richtern verschieben (löschen bei dem
    einen, neu anlegen beim anderen). Start-/Endzeiten werden nicht gespeichert, sondern
    bei jedem Aufbau dieses Tabs aus der Zeitplan-Startzeit und den aktuell erfassten
    Teilnehmern neu berechnet (siehe db.berechne_zeitplan) - ein nachträglich geänderter
    Teilnehmerstand wirkt sich dadurch automatisch aus, ohne dass der Zeitplan von Hand
    nachgezogen werden müsste. Die Spalten zeigen dabei jeden einzelnen Teilnehmer mit
    seiner berechneten Zeit (nicht nur den zusammengefassten Prüfungsblock) - Verschieben/
    Bearbeiten/Entfernen wirkt trotzdem auf den gesamten zugrundeliegenden Block, da die
    Zuteilung einzelner Teilnehmer zu einem Block automatisch aus den aktuellen
    Anmeldedaten folgt und nicht einzeln von Hand festgelegt wird."""

    def __init__(self, conn, ablageort: _Ablageort | None = None, parent=None):
        super().__init__(parent)
        self.conn = conn
        # Wird ein `ablageort` übergeben (siehe HauptFenster), ist es dasselbe Objekt wie
        # im Tab "Export" - ein dort gewählter Ordner gilt dann auch hier als Standard-
        # Speicherort für "Zeitplan (PDF)…", und umgekehrt.
        self._ablageort = ablageort if ablageort is not None else _Ablageort(str(termine_ordner()))
        # ID des zuletzt verschobenen/bearbeiteten Eintrags - nach jedem Neuaufbau der
        # Spalten (aktualisieren()) wird die dazugehörige Zeile wieder markiert, damit
        # "Hoch"/"Runter" mehrfach hintereinander geklickt werden kann, ohne den Eintrag
        # jedes Mal erneut in der Liste auswählen zu müssen.
        self._markierter_eintrag_id: int | None = None
        self._richter_uebernahme_erfolgt = False  # siehe aktualisieren() (U8)

        veranstaltung = get_veranstaltung(conn) or {}

        self.zeitplan_start = QLineEdit(veranstaltung.get("zeitplan_start") or "09:00")
        self.zeitplan_start.setPlaceholderText("HH:MM")
        self.zeitplan_start.setMaximumWidth(70)
        start_speichern_btn = QPushButton("Startzeit speichern")
        start_speichern_btn.clicked.connect(self._start_speichern)
        # Desktop-Prüfung 14.10.2026 (Teil 4 Nr. 3): Enter speichert, und eine gültige Eingabe
        # wird beim Verlassen des Feldes übernommen - sonst setzte der nächste Neuaufbau sie
        # still zurück bzw. das PDF begann zur alten Zeit.
        self.zeitplan_start.returnPressed.connect(self._start_speichern)
        self.zeitplan_start.editingFinished.connect(lambda: self._start_uebernehmen(still=True))
        self._konflikt_hinweise: dict[tuple, str] = {}

        self.standard_dauer = QSpinBox()
        self.standard_dauer.setRange(1, 240)
        self.standard_dauer.setValue(10)
        self.standard_dauer.setSuffix(" Min.")

        # UX-Test 02.10.2026, U2: Mindestabstand zwischen zwei Starts desselben Teams
        # (DK-Disziplinen); gilt für "Automatisch verteilen…" und die Überschneidungs-
        # Markierung, je Termin gespeichert.
        self.mindestabstand = QSpinBox()
        self.mindestabstand.setRange(0, 240)
        self.mindestabstand.setSuffix(" Min.")
        self.mindestabstand.setToolTip(
            "Mindestabstand zwischen zwei Starts desselben Teams (z. B. Dreikampf: Pause für "
            "den Hund und Wegezeit zwischen den Disziplinen)."
        )
        self.mindestabstand.setValue(dk_mindestabstand(veranstaltung))
        # Erst nach Abschluss der Eingabe speichern, nicht bei jedem Tastendruck
        # (Desktop-Prüfung 14.10.2026, Teil 4 Nr. 7).
        self.mindestabstand.setKeyboardTracking(False)
        self.mindestabstand.valueChanged.connect(self._mindestabstand_speichern)

        richter_hinzufuegen_btn = QPushButton("Richter hinzufügen")
        richter_hinzufuegen_btn.clicked.connect(self._richter_hinzufuegen)

        self.verteilen_btn = verteilen_btn = QPushButton("Automatisch verteilen…")  # Attribut für die Demoprüfung
        verteilen_btn.clicked.connect(self._automatisch_verteilen)

        export_btn = QPushButton("Zeitplan (PDF)…")
        export_btn.clicked.connect(self._pdf_exportieren)

        kopf_zeile = QHBoxLayout()
        kopf_zeile.addWidget(QLabel("Zeitplan-Start (HH:MM):"))
        kopf_zeile.addWidget(self.zeitplan_start)
        kopf_zeile.addWidget(start_speichern_btn)
        kopf_zeile.addSpacing(16)
        kopf_zeile.addWidget(QLabel("Standard-Prüfungsdauer:"))
        kopf_zeile.addWidget(self.standard_dauer)
        kopf_zeile.addSpacing(16)
        kopf_zeile.addWidget(QLabel("Mindestabstand Team:"))
        kopf_zeile.addWidget(self.mindestabstand)
        kopf_zeile.addSpacing(16)
        kopf_zeile.addWidget(richter_hinzufuegen_btn)
        kopf_zeile.addWidget(verteilen_btn)
        kopf_zeile.addStretch()
        kopf_zeile.addWidget(export_btn)

        hinweis = QLabel(
            "Je Richter eine eigene Spalte mit frei sortierbarer Abfolge aus "
            "Prüfungsblöcken und Pausen. \"Automatisch verteilen…\" erstellt einen "
            "ausgewogenen Erstvorschlag über ALLE angelegten Richter (ersetzt "
            "dabei deren bisherigen Zeitplan) - die \"Standard-Prüfungsdauer\" ist dabei "
            "nur ein Vorschlagswert und lässt sich je Block einzeln überschreiben. "
            "Pausendauer und -platzierung sind ebenso frei wählbar wie die Reihenfolge "
            "insgesamt, unabhängig je Richter."
        )
        hinweis.setWordWrap(True)

        self._spalten_layout = QHBoxLayout()
        spalten_container = QWidget()
        spalten_container.setLayout(self._spalten_layout)
        self._scroll = QScrollArea()
        self._scroll.setWidget(spalten_container)
        self._scroll.setWidgetResizable(True)

        # Feste Seitenleiste "Offene Starts" (Nutzerwunsch 21.09.: "ich tue mir etwas
        # schwer, ob ich von den benötigten Starts auch schon alles erwischt habe,
        # nachdem ich scrollen muss" - zeigt je Art/Leistungsklasse/Disziplin mit
        # Teilnehmern, ob dafür bereits ein Prüfungsblock angelegt wurde. Bewusst
        # AUSSERHALB von self._scroll platziert, damit sie beim horizontalen Scrollen durch
        # viele Richter-Spalten sichtbar bleibt statt mit-zu-scrollen.
        self._offene_starts_box = QGroupBox("Offene Starts")
        self._offene_starts_box.setMinimumWidth(230)
        self._offene_starts_box.setMaximumWidth(280)
        self._offene_starts_label = QLabel("")
        self._offene_starts_label.setWordWrap(True)
        self._offene_starts_label.setTextFormat(Qt.RichText)
        self._offene_starts_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        offene_starts_scroll = QScrollArea()
        offene_starts_scroll.setWidget(self._offene_starts_label)
        offene_starts_scroll.setWidgetResizable(True)
        offene_starts_layout = QVBoxLayout(self._offene_starts_box)
        offene_starts_layout.addWidget(offene_starts_scroll)

        inhalt_zeile = QHBoxLayout()
        inhalt_zeile.addWidget(self._scroll, stretch=1)
        inhalt_zeile.addWidget(self._offene_starts_box)

        self.status_label = QLabel("")
        self.status_label.setTextFormat(Qt.PlainText)  # S-1: enthält Pfade/Namen
        self.status_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Zeitplan"))
        layout.addLayout(kopf_zeile)
        layout.addWidget(hinweis)
        layout.addLayout(inhalt_zeile, stretch=1)
        layout.addWidget(self.status_label)

        self.aktualisieren()

    # --- Aufbau --------------------------------------------------------------

    def showEvent(self, event) -> None:  # type: ignore[override]
        """UX-Test 02.10.2026, U8: beim ERSTEN Anzeigen des Reiters (nicht schon beim
        Öffnen des Termins - das soll die Datei nicht verändern) die Richter aus den
        Veranstaltungsdaten als Spalten anlegen, solange der Zeitplan noch leer ist. Nur
        einmal je geöffnetem Termin, damit bewusst gelöschte Richter nicht wieder auftauchen."""
        super().showEvent(event)
        if not self._richter_uebernahme_erfolgt:
            self._richter_uebernahme_erfolgt = True
            try:
                angelegt = zeitplan_richter_aus_veranstaltung_anlegen(self.conn)
            except sqlite3.Error as exc:
                _db_fehler_anzeigen(
                    self, exc, "Die Richter aus den Veranstaltungsdaten konnten nicht in den "
                    "Zeitplan übernommen werden.",
                )
                return
            if angelegt:
                self.aktualisieren()

    def aktualisieren(self) -> None:
        """Baut die Richter-Spalten komplett neu aus dem aktuellen Datenbankstand auf -
        kein Zwischenspeicher, damit z.B. ein nachträglich geänderter Teilnehmerstand
        sofort in den neu berechneten Start-/Endzeiten sichtbar wird."""
        veranstaltung = get_veranstaltung(self.conn) or {}
        if not self.zeitplan_start.hasFocus():
            self.zeitplan_start.setText(veranstaltung.get("zeitplan_start") or "09:00")

        while self._spalten_layout.count():
            item = self._spalten_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        richter_liste = list_zeitplan_richter(self.conn)
        namen_je_richter = {r["id"]: r["name"] for r in richter_liste}
        konflikte = zeitplan_ueberschneidungen(self.conn) if richter_liste else []
        # (Block, Team) -> Erklärung für die rote Markierung der betroffenen Zeilen.
        self._konflikt_hinweise: dict[tuple, str] = {}
        abstand = dk_mindestabstand(veranstaltung)
        for k in konflikte:
            for eigene, andere in ((k["erste"], k["zweite"]), (k["zweite"], k["erste"])):
                art = "gleichzeitig" if k["gleichzeitig"] else f"weniger als {abstand} Min. Abstand"
                self._konflikt_hinweise[(eigene["eintrag_id"], k["teilnehmer"]["id"])] = (
                    f"Überschneidung ({art}): steht um {andere['start'].strftime('%H:%M')} auch bei "
                    f"{namen_je_richter.get(andere['richter_id'], '?')} ({andere['disziplin']})."
                )
        if not richter_liste:
            hinweis = QLabel("Noch keine Richter angelegt - über „Richter hinzufügen“ starten.")
            hinweis.setWordWrap(True)
            self._spalten_layout.addWidget(hinweis)
        else:
            zeilen_je_richter_id = {plan["richter_id"]: plan["zeilen"] for plan in berechne_zeitplan(self.conn)}
            for richter in richter_liste:
                self._spalten_layout.addWidget(
                    self._richter_spalte(richter, zeilen_je_richter_id.get(richter["id"], []))
                )
        self._spalten_layout.addStretch()
        self._offene_starts_aktualisieren(konflikte, namen_je_richter)

    def _mindestabstand_speichern(self, wert: int) -> None:
        try:
            _aktualisiere_veranstaltung_feld(self.conn, dk_mindestabstand=str(wert))
        except sqlite3.Error as exc:
            # Feld auf den gespeicherten Wert zurücksetzen, damit Anzeige und Datei
            # übereinstimmen (Desktop-Prüfung 14.10.2026, Teil 4 Nr. 4).
            self.mindestabstand.blockSignals(True)
            self.mindestabstand.setValue(dk_mindestabstand(get_veranstaltung(self.conn)))
            self.mindestabstand.blockSignals(False)
            _db_fehler_anzeigen(self, exc)
            return
        self.aktualisieren()

    def _offene_starts_aktualisieren(self, konflikte: list | None = None, namen_je_richter: dict | None = None) -> None:
        """Baut den Text der Seitenleiste "Offene Starts" aus zeitplan_gruppen_status()
        neu auf: eine Zeile je Art/Leistungsklasse/Disziplin mit mindestens einem
        Teilnehmer, grün mit Haken wenn bereits ein Prüfungsblock dafür angelegt wurde,
        sonst rot/fett hervorgehoben mit "noch offen"."""
        status_liste = zeitplan_gruppen_status(self.conn)
        if not status_liste:
            self._offene_starts_label.setText("Noch keine Teilnehmer erfasst.")
            return
        zeilen = []
        ok = _farbe("ok").name()
        fehler = _farbe("fehler").name()
        # UX-Test 02.10.2026, U2: Überschneidungen oben und auffällig - vorher war die
        # Seitenleiste auch bei doppelt eingeplanten Teams komplett grün.
        if konflikte:
            namen_je_richter = namen_je_richter or {}
            # Je Team zusammengefasst (statt je Paar): alle betroffenen Starts mit Richter.
            je_team: dict[int, tuple[dict, set]] = {}
            for k in konflikte:
                team, starts = je_team.setdefault(k["teilnehmer"]["id"], (k["teilnehmer"], set()))
                for zeile in (k["erste"], k["zweite"]):
                    starts.add((zeile["start"], namen_je_richter.get(zeile["richter_id"], "?")))
            zeilen.append(
                f'<span style="color:{fehler}; font-weight:bold;">⚠ Überschneidungen ({len(je_team)} Team(s))</span>'
            )
            for team, starts in je_team.values():
                nr = team["startnummer"] if team["startnummer"] is not None else "–"
                liste = ", ".join(f"{start.strftime('%H:%M')} {name}" for start, name in sorted(starts))
                # Sicherheitsprüfung 03.10.2026, S-1: Namen/Bezeichnungen maskieren (Rich Text).
                zeilen.append(
                    f'<span style="color:{fehler};">Nr. {nr} {html.escape(str(team["nachname"]))}: '
                    f'{html.escape(liste)}</span>'
                )
            zeilen.append("")
        for eintrag in status_liste:
            bezeichnung = f"{eintrag['art']} LK {eintrag['stufe']} – {eintrag['disziplin']}"
            if eintrag["eingeplant"]:
                zeilen.append(
                    f'<span style="color:{ok};">✓ {html.escape(bezeichnung)} ({eintrag["anzahl"]} Teilnehmer)</span>'
                )
            else:
                zeilen.append(
                    f'<span style="color:{fehler}; font-weight:bold;">'
                    f'✗ {html.escape(bezeichnung)} ({eintrag["anzahl"]} Teilnehmer) – noch offen</span>'
                )
        self._offene_starts_label.setText("<br>".join(zeilen))

    def _richter_spalte(self, richter: dict, zeilen: list) -> QGroupBox:
        richter_id = richter["id"]
        box = QGroupBox(richter["name"])
        box.setMinimumWidth(300)

        links_btn = QPushButton("◀")
        links_btn.setToolTip("Spalte nach links verschieben")
        links_btn.clicked.connect(lambda: self._richter_verschieben(richter_id, -1))
        rechts_btn = QPushButton("▶")
        rechts_btn.setToolTip("Spalte nach rechts verschieben")
        rechts_btn.clicked.connect(lambda: self._richter_verschieben(richter_id, 1))
        umbenennen_btn = QPushButton("Umbenennen…")
        umbenennen_btn.clicked.connect(lambda: self._richter_umbenennen(richter_id))

        kopf_zeile = QHBoxLayout()
        kopf_zeile.addWidget(links_btn)
        kopf_zeile.addWidget(rechts_btn)
        kopf_zeile.addWidget(umbenennen_btn)
        kopf_zeile.addStretch()

        liste = QListWidget()
        markierte_zeile = None
        # UX-Test 02.10.2026, U9: je Prüfungsblock eine fette Kopfzeile, die Teilnehmer
        # eingerückt darunter - so ist sichtbar, dass "Hoch"/"Runter"/"Entfernen" den ganzen
        # Block bewegen.
        zeilen_je_block: dict[int, list] = {}
        for zeile in zeilen:
            if zeile["typ"] == "pruefung":
                zeilen_je_block.setdefault(zeile["eintrag_id"], []).append(zeile)
        letzter_block = None
        for zeile in zeilen:
            if zeile["typ"] == "pruefung" and zeile["eintrag_id"] != letzter_block:
                block = zeilen_je_block[zeile["eintrag_id"]]
                anzahl = sum(1 for z in block if z["teilnehmer"] is not None)
                umfang = (
                    f"{anzahl} Teilnehmer, {block[0]['start'].strftime('%H:%M')}–{block[-1]['ende'].strftime('%H:%M')}"
                    if anzahl else "keine Teilnehmer gemeldet"
                )
                hinweise = [
                    self._konflikt_hinweise.get((z["eintrag_id"], z["teilnehmer"]["id"]))
                    for z in block if z["teilnehmer"] is not None
                ]
                hinweise = [h for h in hinweise if h]
                warnung = "⚠ " if hinweise else ""
                kopf = QListWidgetItem(
                    f"▸ {warnung}{zeile['art']} LK {zeile['stufe']} – {zeile['disziplin']}  ({umfang})"
                )
                kopf.setData(Qt.UserRole, zeile["eintrag_id"])
                schrift = kopf.font()
                schrift.setBold(True)
                kopf.setFont(schrift)
                if hinweise:
                    # Verifikation U9: Überschneidung auch an der Kopfzeile sichtbar machen.
                    kopf.setForeground(_farbe("fehler"))
                    kopf.setToolTip(f"{len(hinweise)} Team(s) dieses Blocks mit Überschneidung.")
                liste.addItem(kopf)
                if markierte_zeile is None and zeile["eintrag_id"] == self._markierter_eintrag_id:
                    markierte_zeile = liste.count() - 1
            letzter_block = zeile["eintrag_id"] if zeile["typ"] == "pruefung" else None
            if zeile["typ"] == "pruefung" and zeile["teilnehmer"] is None:
                continue  # leerer Block: nur die Kopfzeile
            item = self._zeile_listenelement(zeile)
            liste.addItem(item)
            if markierte_zeile is None and self._markierter_eintrag_id is not None and zeile["eintrag_id"] == self._markierter_eintrag_id:
                markierte_zeile = liste.count() - 1
        if markierte_zeile is not None:
            liste.setCurrentRow(markierte_zeile)

        hoch_btn = QPushButton("Hoch")
        hoch_btn.clicked.connect(lambda: self._eintrag_verschieben(liste, -1))
        runter_btn = QPushButton("Runter")
        runter_btn.clicked.connect(lambda: self._eintrag_verschieben(liste, 1))
        bearbeiten_btn = QPushButton("Bearbeiten…")
        bearbeiten_btn.clicked.connect(lambda: self._eintrag_bearbeiten(liste))
        entfernen_btn = QPushButton("Entfernen")
        entfernen_btn.clicked.connect(lambda: self._eintrag_entfernen(liste))

        # UX-Test 02.10.2026, U9: Knöpfe in zwei statt fünf Zeilen - mehr Höhe für die Liste.
        eintrag_buttons_1 = QHBoxLayout()
        eintrag_buttons_1.addWidget(hoch_btn)
        eintrag_buttons_1.addWidget(runter_btn)
        eintrag_buttons_1.addWidget(bearbeiten_btn)
        eintrag_buttons_1.addWidget(entfernen_btn)
        eintrag_buttons_2 = QHBoxLayout()

        block_btn = QPushButton("Prüfungsblock hinzufügen…")
        block_btn.clicked.connect(lambda: self._pruefungsblock_hinzufuegen(richter_id))
        pause_btn = QPushButton("Pause hinzufügen…")
        pause_btn.clicked.connect(lambda: self._pause_hinzufuegen(richter_id, liste))
        loeschen_btn = QPushButton("Richter löschen")
        loeschen_btn.clicked.connect(lambda: self._richter_loeschen(richter_id, richter["name"]))

        layout = QVBoxLayout(box)
        layout.addLayout(kopf_zeile)
        layout.addWidget(liste, stretch=1)
        eintrag_buttons_2.addWidget(block_btn)
        eintrag_buttons_2.addWidget(pause_btn)
        layout.addLayout(eintrag_buttons_1)
        layout.addLayout(eintrag_buttons_2)
        layout.addWidget(loeschen_btn)
        return box

    def _zeile_listenelement(self, zeile: dict) -> QListWidgetItem:
        """Eine Listenzeile je einzelnem Teilnehmer (bzw. je Pause) - "Hoch"/"Runter"/
        "Bearbeiten…"/"Entfernen" wirken trotzdem auf den zugrundeliegenden Prüfungsblock
        als Ganzes (siehe zeile["eintrag_id"]), da einzelne Teilnehmer nicht manuell
        umverteilt werden, sondern sich automatisch aus Art/Leistungsklasse/Disziplin des
        Blocks ergeben."""
        zeit = f"{zeile['start'].strftime('%H:%M')}–{zeile['ende'].strftime('%H:%M')}"
        if zeile["typ"] == "pause":
            text = f"{zeit}  Pause: {zeile['bezeichnung']}"
        else:
            # Block-Angaben stehen in der Kopfzeile darüber (siehe _richter_spalte, U9).
            t = zeile["teilnehmer"]
            startnr = t["startnummer"] if t["startnummer"] is not None else "–"
            text = f"      {zeit}  Nr. {startnr}  {t['nachname']}, {t['vorname']} ({t['rufname_hund']})"
        hinweis = None
        if zeile["typ"] == "pruefung" and zeile.get("teilnehmer") is not None:
            hinweis = self._konflikt_hinweise.get((zeile["eintrag_id"], zeile["teilnehmer"]["id"]))
        if hinweis:
            text = "⚠ " + text
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, zeile["eintrag_id"])
        if hinweis:
            # UX-Test 02.10.2026, U2: betroffene Zeilen rot, Tooltip erklärt die Überschneidung.
            item.setForeground(_farbe("fehler"))
            item.setToolTip(_klartext_tooltip(hinweis))  # S-1: enthält Richternamen
        return item

    # --- Aktionen: Richter -----------------------------------------------------

    def _start_speichern(self) -> None:
        self._start_uebernehmen(still=False)

    def _start_uebernehmen(self, still: bool) -> bool:
        """Speichert die Startzeit aus dem Feld, falls sie von der gespeicherten abweicht, in
        einheitlicher Schreibweise HH:MM (Teil 4 Nr. 6: „9:5“ wurde sonst so gespeichert).
        Liefert False bei ungültiger Eingabe; `still`: dann ohne Meldung (beim Verlassen des
        Feldes)."""
        text = self.zeitplan_start.text().strip()
        try:
            zeit = datetime.datetime.strptime(text, "%H:%M").strftime("%H:%M")
        except ValueError:
            if not still:
                QMessageBox.warning(
                    self, "Ungültige Uhrzeit",
                    "Bitte die Zeitplan-Startzeit im Format HH:MM angeben (z.B. 09:00).",
                )
                self.zeitplan_start.setFocus()
            return False
        try:
            gespeichert = (get_veranstaltung(self.conn) or {}).get("zeitplan_start") or "09:00"
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return False
        if zeit == gespeichert and text == zeit:
            if not still:
                self.status_label.setText("Zeitplan-Startzeit gespeichert.")
            return True
        try:
            _aktualisiere_veranstaltung_feld(self.conn, zeitplan_start=zeit)
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return False
        self.zeitplan_start.setText(zeit)
        self.status_label.setText("Zeitplan-Startzeit gespeichert.")
        if still:
            # Verifikation A14: Das Feld verliert den Fokus meist durch einen Mausklick - ein
            # sofortiger Neuaufbau löschte den gerade gedrückten Knopf einer Richter-Spalte.
            self._nach_mausklick_aktualisieren()
        else:
            self.aktualisieren()
        return True

    def _nach_mausklick_aktualisieren(self) -> None:
        # Abschluss-QS 15.10.2026 (K-1): auch warten, solange der Klick einen modalen Dialog
        # geöffnet hat (z. B. „Pause hinzufügen…“) - dessen Aufrufer greift danach noch auf
        # seine Spalte zu.
        if QApplication.mouseButtons() != Qt.NoButton or QApplication.activeModalWidget() is not None:
            # Mit dem Reiter als Kontext: wird er inzwischen (Terminwechsel) gelöscht, verfällt
            # der Timer.
            QTimer.singleShot(50, self, self._nach_mausklick_aktualisieren)
            return
        try:
            self.aktualisieren()
        except sqlite3.ProgrammingError:
            pass  # Verbindung schon geschlossen (Terminwechsel) - der neue Reiter baut selbst auf

    def _richter_hinzufuegen(self) -> None:
        try:
            add_zeitplan_richter(self.conn)
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        self.aktualisieren()

    def _richter_umbenennen(self, richter_id: int) -> None:
        aktueller_name = next((r["name"] for r in list_zeitplan_richter(self.conn) if r["id"] == richter_id), "")
        name, ok = QInputDialog.getText(self, "Richter umbenennen", "Name:", text=aktueller_name)
        if not ok or not name.strip():
            return
        try:
            umbenennen_zeitplan_richter(self.conn, richter_id, name.strip())
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        self.aktualisieren()

    def _richter_verschieben(self, richter_id: int, richtung: int) -> None:
        try:
            verschiebe_zeitplan_richter(self.conn, richter_id, richtung)
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        self.aktualisieren()

    def _richter_loeschen(self, richter_id: int, name: str) -> None:
        if not _ja_nein(
            self, "Richter löschen",
            f"„{name}“ samt allen dort eingeplanten Prüfungsblöcken/Pausen löschen?",
        ):
            return
        try:
            loesche_zeitplan_richter(self.conn, richter_id)
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        self.aktualisieren()

    def verteilen_ohne_rueckfrage(self) -> bool:
        """Kern von „Automatisch verteilen…“ ohne Rückfragen - auch von der Demoprüfung
        genutzt (Desktop-Prüfung 14.10.2026, Teil 10 Nr. 10). True = Vorschlag erstellt."""
        richter = list_zeitplan_richter(self.conn)
        if not richter:
            return False
        try:
            automatische_zeitplan_verteilung(
                self.conn, [r["id"] for r in richter], standard_dauer_minuten=self.standard_dauer.value(),
            )
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return False
        self.status_label.setText("Automatischer Zeitplan-Vorschlag erstellt.")
        self.aktualisieren()
        return True

    def _automatisch_verteilen(self) -> None:
        if not self._start_uebernehmen(still=False):  # Teil 4 Nr. 3: zur eingetippten Startzeit
            return
        richter = list_zeitplan_richter(self.conn)
        if not richter:
            QMessageBox.information(
                self, "Keine Richter",
                "Bitte zuerst mindestens einen Richter anlegen.",
            )
            return
        # UX-Test 02.10.2026, U9: nur warnen, wenn es schon einen Plan gibt, der verloren ginge.
        if any(list_zeitplan_eintraege(self.conn, r["id"]) for r in richter):
            if not _ja_nein(
                self, "Automatisch verteilen",
                "Erstellt einen ausgewogenen Vorschlag über ALLE angelegten Richter "
                "und ERSETZT dabei deren bisherigen Zeitplan (bereits eingefügte Pausen und "
                "von Hand geänderte Reihenfolgen gehen dabei verloren). Fortfahren?",
            ):
                return
        self.verteilen_ohne_rueckfrage()

    # --- Aktionen: Einträge ------------------------------------------------

    def _pruefungsblock_hinzufuegen(self, richter_id: int) -> None:
        dialog = PruefungsblockDialog(self, standard_dauer_minuten=self.standard_dauer.value())
        if _ausfuehren(dialog) != QDialog.Accepted:
            return
        try:
            add_zeitplan_pruefungsblock(self.conn, richter_id, **dialog.werte())
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        self.aktualisieren()

    def _pause_hinzufuegen(self, richter_id: int, liste: QListWidget | None = None) -> None:
        # Markierte Zeile vor dem Dialog lesen - die Spalte kann währenddessen neu aufgebaut
        # werden (Abschluss-QS 15.10.2026, K-1).
        markiert_item = liste.currentItem() if liste is not None else None
        nach_id = markiert_item.data(Qt.UserRole) if markiert_item is not None else None
        dialog = PauseDialog(self, neu=True)
        if _ausfuehren(dialog) != QDialog.Accepted:
            return
        try:
            if dialog.fuer_alle.isChecked():
                # Teil 4 Nr. 6: „9:20“ wie „09:20“ (die Prüfung im Dialog lässt beides zu).
                wunsch = datetime.datetime.strptime(dialog.uhrzeit.text().strip(), "%H:%M").strftime("%H:%M")
                eingefuegt = add_zeitplan_pause_bei_allen(self.conn, wunsch, **dialog.werte())
                abweichend = [(name, zeit) for name, zeit in eingefuegt if zeit != wunsch]
                if abweichend:
                    # UX-Nachtest 03.10.2026, N3: "um 12:00 eingefügt" stimmte nicht, wenn ein
                    # Plan vorher endet oder ein Block noch läuft - tatsächliche Zeiten nennen.
                    QMessageBox.information(
                        self, "Pause eingefügt",
                        "Die Pause beginnt nicht überall um " + wunsch + ":\n\n"
                        + "\n".join(f"{name or 'Richter'}: {zeit} Uhr" for name, zeit in eingefuegt)
                        + "\n\nEin laufender Prüfungsblock wird nicht geteilt; endet der Plan eines "
                        "Richters vorher, steht die Pause an seinem Ende.",
                    )
                self.status_label.setText(f"Pause bei {len(eingefuegt)} Richter(n) eingefügt.")
            else:
                # UX-Test 02.10.2026, U9: nach der markierten Zeile statt immer am Ende.
                nach = nach_id
                self._markierter_eintrag_id = add_zeitplan_pause(
                    self.conn, richter_id, nach_eintrag_id=nach, **dialog.werte()
                )
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        self.aktualisieren()

    def _eintrag_verschieben(self, liste: QListWidget, richtung: int) -> None:
        item = liste.currentItem()
        if item is None:
            return
        eintrag_id = item.data(Qt.UserRole)
        try:
            verschiebe_zeitplan_eintrag(self.conn, eintrag_id, richtung)
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        # Nach dem Neuaufbau bleibt derselbe Block markiert, damit "Hoch"/"Runter" auch
        # mehrfach hintereinander geklickt werden kann, ohne ihn jedes Mal neu auszuwählen.
        self._markierter_eintrag_id = eintrag_id
        self.aktualisieren()

    def _eintrag_bearbeiten(self, liste: QListWidget) -> None:
        item = liste.currentItem()
        if item is None:
            QMessageBox.information(self, "Kein Eintrag ausgewählt", "Bitte zuerst einen Eintrag in der Liste auswählen.")
            return
        eintrag_id = item.data(Qt.UserRole)
        try:
            eintrag = zeitplan_eintrag(self.conn, eintrag_id)
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        if eintrag is None:
            return

        try:
            if eintrag["typ"] == "pause":
                dialog = PauseDialog(self, dauer_minuten=eintrag["dauer_minuten"], bezeichnung=eintrag["bezeichnung"] or "")
                if _ausfuehren(dialog) != QDialog.Accepted:
                    return
                werte = dialog.werte()
                aktualisiere_zeitplan_eintrag(self.conn, eintrag_id, dauer_minuten=werte["dauer_minuten"], bezeichnung=werte["bezeichnung"] or "Pause")
            else:
                neue_dauer, ok = QInputDialog.getInt(
                    self, "Prüfungsblock bearbeiten", "Dauer je Teilnehmer (Minuten):",
                    value=eintrag["dauer_minuten"], minValue=1, maxValue=240,
                )
                if not ok:
                    return
                aktualisiere_zeitplan_eintrag(self.conn, eintrag_id, dauer_minuten=neue_dauer)
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        self._markierter_eintrag_id = eintrag_id
        self.aktualisieren()

    def _eintrag_entfernen(self, liste: QListWidget) -> None:
        item = liste.currentItem()
        if item is None:
            QMessageBox.information(self, "Kein Eintrag ausgewählt", "Bitte zuerst einen Eintrag in der Liste auswählen.")
            return
        try:
            loesche_zeitplan_eintrag(self.conn, item.data(Qt.UserRole))
        except sqlite3.Error as exc:
            _db_fehler_anzeigen(self, exc)
            return
        self._markierter_eintrag_id = None
        self.aktualisieren()

    # --- Export --------------------------------------------------------------

    def _pdf_exportieren(self) -> None:
        if not self._start_uebernehmen(still=False):  # Teil 4 Nr. 3: zur eingetippten Startzeit
            return
        _zeitplan_pdf_exportieren(self, self.conn, self._ablageort, self.status_label)
