"""
Reiter Ergebniserfassung (Tabelle mit Delegates, Speichern, Abbruchgründe), seit 11.11.2026
aus app.py ausgelagert. Bewusst KEIN `import app` (siehe desktop_programm.py).
"""
from __future__ import annotations

import contextlib
import sqlite3

from PySide6.QtCore import (
    QRect,
    Qt,
)
from PySide6.QtGui import (
    QBrush,
    QIcon,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from db import (
    ALLE_DISZIPLINEN,
    DISZIPLIN_SPALTEN,
    alle_leistungsklassen,
    ergebnisse_je_teilnehmer,
    leistungsklasse_label,
    list_teilnehmer,
    sortierschluessel_text,
    pruefung_sortierschluessel,
    termine_ordner,
)
from shs_core import (
    ABBRUCH_GRUENDE,
    ANZEIGE_MAX,
    SUCHE_MAX,
)
from desktop_darstellung import (
    _farbe,
    _SCHRIFTSTUFEN,
    schrift_faktor,
)
from desktop_ergebnis_speichern import _ErgebnisSpeichernMixin
from desktop_ergebnis_zellen import (
    _ABBRUCH_OHNE_GRUND,
    _PUNKTE_EDITOR_STIL,
    _PUNKTESPALTEN,
    _SORTIERSPALTEN_AUS_STAMMDATEN,
    _UNGESPEICHERT_ROLLE,
    _ZU_HOCH_ROLLE,
    _abbruch_bezeichnung,
    _abbruch_grund_aus_db,
    _ablehnungsgrund,
    _AbbruchDelegate,
    _AbbruchItem,
    _ErgebnisTabelle,
    _HakenDelegate,
    _HakenItem,
    _info_item,
    _PunkteDelegate,
    _PunkteFeld,
    _PunkteItem,
)
from desktop_gemeinsam import (
    _ABBRUCH_SPALTE,
    _Ablageort,
    _ablageort_ordner_oeffnen,
    _bewertungsbogen_fuer_teilnehmer,
    _kontextmenue_aus_knoepfen,
    _name_passt,
    _ja_nein,
    _DQ_SPALTE,
    _ERGEBNIS_SPALTEN_JE_DISZIPLIN,
    _ergebnis_spaltenbreiten_verteilen,
    _responsive_schriftgroesse,
    _STATUS_SPALTE,
    symbol,
)


#: R6: höchster Schriftfaktor der Ergebnistabelle bei nicht maximiertem Fenster.
#: Gekoppelt an die Stufe „Groß“, damit eine Änderung dort hier mitwirkt.
_ERGEBNIS_FAKTOR_NICHT_MAXIMIERT = _SCHRIFTSTUFEN["gross"]["faktor"]


class ErgebnisTab(_ErgebnisSpeichernMixin, QWidget):
    """Eine Zeile je Teilnehmer. Bei DK werden alle drei Disziplinen nebeneinander in
    derselben Zeile erfasst statt in drei getrennten Zeilen. Änderungen werden nicht
    mehr sofort pro Zeile gespeichert, sondern gesammelt über einen einzigen
    "Alle Ergebnisse speichern"-Button - noch nicht gespeicherte Zeilen werden dabei
    gelb hervorgehoben und im Status deutlich gekennzeichnet."""

    def __init__(self, conn, parent=None, ablageort: _Ablageort | None = None):
        super().__init__(parent)
        self.conn = conn
        self._ablageort = ablageort if ablageort is not None else _Ablageort(str(termine_ordner()))
        # Pro Tabellenzeile: Teilnehmer-Stammdaten, die Punktezellen je Disziplin
        # und die zuletzt aus der DB geladenen (= gespeicherten) Werte je Disziplin -
        # der Vergleich der beiden liefert den "ungespeichert"-Status. Ein leeres Feld
        # bedeutet "noch nicht eingetragen" (None) - kein Platzhalterwert wie zuvor "-1",
        # damit die Felder ohne Vorbelegung wirklich leer erscheinen.
        self._teilnehmer_je_zeile: list[dict] = []
        # Seit O8 (19.10.2026) Zellen statt Eingabefelder, siehe _PunkteItem/_HakenItem.
        self._boxen_je_zeile: list[dict[str, tuple[_PunkteItem, _PunkteItem]]] = []
        self._geladen_je_zeile: list[dict[str, tuple[int | None, int | None]]] = []
        # Nutzerwunsch (21.09.): analog zu den Punktezellen oben, aber für "Disqualifiziert"
        # (Häkchen) und "Abbruch" (Auswahlliste mit Grund, R7) je Zeile; geladen als
        # (Disqualifiziert, Abbruchgrund oder None).
        self._status_boxen_je_zeile: list[tuple[_HakenItem, _AbbruchItem]] = []
        self._status_geladen_je_zeile: list[tuple[bool, str | None]] = []
        # Zählt jeden Neuaufbau der Zeilen (offene Punkte O7): Tests prüfen damit „nicht neu
        # aufgebaut“, ohne sich auf einzelne Eingabe-Widgets zu verlassen.
        self.aufbau_kennung = 0
        # Interne Änderungen an Zellen (Aufbau, Färben, Sperren) lösen keine Reaktion aus;
        # _aus_editor markiert eine Übernahme aus dem Eingabefeld (siehe _zelle_geaendert).
        self._intern_tiefe = 0
        self._aus_editor = False

        self._tabelle_aufbauen()
        self._filter_aufbauen()
        self._knoepfe_aufbauen()
        self._hinweise_aufbauen()
        self._layout_aufbauen()
        self.aktualisieren()

    def _tabelle_aufbauen(self) -> None:
        spalten = ["Start-Nr.", "Name", "Hund", "Art/LK"]
        for disziplin in ALLE_DISZIPLINEN:
            spalten += [f"{disziplin}\nSuche (0-{SUCHE_MAX})", f"{disziplin}\nAnzeige (0-{ANZEIGE_MAX})"]
        spalten += ["Disqualifiziert", "Abbruch", "Status"]

        self.tabelle = _ErgebnisTabelle(0, len(spalten))
        self.tabelle.setHorizontalHeaderLabels(spalten)
        self.tabelle.horizontalHeader().setStretchLastSection(True)
        # Nutzerwunsch (22.09.): Spaltenüberschriften sollen bei schmalen Spalten nicht
        # abgeschnitten werden. Qt rendert einen "\n" in einem Header-Label von sich aus
        # bereits mehrzeilig (sizeHint/Höhe passen sich automatisch an - kein QHeaderView-
        # API-Aufruf nötig, es gibt dort anders als bei QAbstractItemView kein setWordWrap()).
        # Die Disziplin-Header oben nutzen deshalb "\n" statt " – " als Trenner; die
        # Mindestspaltenbreite in _spaltenminima (von _spaltenbreiten_anpassen) orientiert sich entsprechend
        # an der jeweils breitesten Headerzeile statt an festen Platzhaltern.
        # Die von Qt automatisch links angezeigte Zeilennummerierung (1, 2, 3, ...) ist
        # keine echte, überschriebene Spalte und trägt keine zusätzliche Information (die
        # Start-Nr. steht bereits in der ersten echten Spalte) - deshalb ausgeblendet,
        # ebenso im Reiter "Teilnehmer" (siehe TeilnehmerTab).
        self.tabelle.verticalHeader().setVisible(False)
        # Infospalten (Start-Nr., Name, Hund, Prüfung) sind nur Anzeige (Flags ohne
        # ItemIsEditable). Bearbeiten (O8, Marco 18.10.2026): in einer markierten Zelle
        # lostippen, Doppelklick, zweiter Klick oder F2; Enter übernimmt und bleibt in der
        # Zelle, die Leertaste schaltet das Häkchen „Disqualifiziert“ bzw. klappt die
        # Abbruch-Auswahlliste auf (R7). Tab springt durch die bedienbaren Zellen
        # (siehe _ErgebnisTabelle.moveCursor).
        self.tabelle.setEditTriggers(
            QAbstractItemView.AnyKeyPressed | QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked | QAbstractItemView.EditKeyPressed
        )
        self.tabelle.setTabKeyNavigation(True)
        self.tabelle.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabelle.setSelectionBehavior(QAbstractItemView.SelectItems)
        punkte_delegate = _PunkteDelegate(self)
        for spalte in sorted(_PUNKTESPALTEN):
            self.tabelle.setItemDelegateForColumn(spalte, punkte_delegate)
        haken_delegate = _HakenDelegate(self.tabelle)
        self.tabelle.setItemDelegateForColumn(_DQ_SPALTE, haken_delegate)
        self.tabelle.setItemDelegateForColumn(_ABBRUCH_SPALTE, _AbbruchDelegate(self.tabelle))
        # UX-Test 03.11.2026, X5: Die Abbruch-Auswahl öffnet schon beim ERSTEN Klick (vorher
        # markierte der erste Klick nur, 5 von 6 Personas suchten danach).
        self.tabelle.clicked.connect(self._abbruch_mit_einem_klick)
        self.tabelle.itemChanged.connect(self._zelle_geaendert)
        # Sortierpfeil wie im Teilnehmer-Reiter (Teil 3 Nr. 7) - die Richtung setzt
        # _spalte_geklickt selbst, weil die Sortierung hier eigene Logik hat.
        self.tabelle.horizontalHeader().setSortIndicatorShown(True)
        self.tabelle.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
        # Nutzerwunsch (21.09., Rückmeldung zur Ergebniserfassung): "klappt gut, ggf. hier
        # auch Sortierungsfunktion" - Klick auf eine Spaltenüberschrift sortiert danach,
        # erneuter Klick auf dieselbe Spalte kehrt die Richtung um (wie in der
        # Teilnehmerliste, siehe TeilnehmerTab). Bewusst NICHT setSortingEnabled(True) wie
        # dort: die Zeilenlisten (_teilnehmer_je_zeile, _geladen_je_zeile …) hängen an der
        # Zeilennummer. Eigene Sortierlogik (siehe _spalte_geklickt/
        # _sortieren_und_neu_aufbauen), die vor dem Neuaufbau zuerst die aktuellen
        # (ggf. noch nicht gespeicherten) Werte je Teilnehmer-ID sichert.
        self.tabelle.horizontalHeader().sectionClicked.connect(self._spalte_geklickt)
        self._sortierspalte: int | None = None
        self._feldhoehe: int | None = None  # einmal bestimmt, siehe _zeilen_aufbauen
        self._tabelle_pt: float | None = None  # zuletzt gesetzte Schriftgröße, siehe _spaltenbreiten_anpassen
        self._sortieraufsteigend = True

    def _filter_aufbauen(self) -> None:
        self.filter_combo = QComboBox()
        # Passt die Breite der Box an den längsten enthaltenen Eintrag an (z.B. lange
        # Art/LK-Bezeichnungen wie "Behältnisse LK 3"), statt Text abzuschneiden.
        self.filter_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.filter_combo.currentTextChanged.connect(self._filter_anwenden)

        self.filter_startnummer = QLineEdit()
        self.filter_startnummer.setPlaceholderText("z.B. 13")
        self.filter_startnummer.setMaximumWidth(80)
        self.filter_startnummer.textChanged.connect(self._filter_anwenden)

        # Marco 10.11.2026 (UI-Abgleich): Suche nach Name oder Hund, wie im Reiter Teilnehmer.
        self.filter_name = QLineEdit()
        self.filter_name.setPlaceholderText("Name oder Hund")
        self.filter_name.setMaximumWidth(160)
        self.filter_name.setClearButtonEnabled(True)
        self.filter_name.textChanged.connect(self._filter_anwenden)

    def _knoepfe_aufbauen(self) -> None:
        self.speichern_btn = speichern_btn = QPushButton("Alle Ergebnisse speichern")  # Attribut für die Demoprüfung
        speichern_btn.setObjectName("primaerButton")  # Haupt-Aktion dieses Reiters, siehe _QSS_TEMPLATE
        # Lambda: clicked(bool) würde sonst als meldungen=False ankommen.
        speichern_btn.clicked.connect(lambda: self.alle_speichern())
        # UX-Test 02.10.2026, K11: Strg+S speichert wie der Button - nur solange der Fokus
        # in diesem Reiter liegt (z. B. in einem Punktefeld). Über ein Lambda verbunden,
        # damit Tests alle_speichern() per monkeypatch ersetzen können.
        speichern_btn.setToolTip("Tastenkürzel: Strg+S")
        speichern_kuerzel = QShortcut(QKeySequence.Save, self)
        speichern_kuerzel.setContext(Qt.WidgetWithChildrenShortcut)
        speichern_kuerzel.activated.connect(lambda: self.alle_speichern())

        self.aktualisieren_btn = aktualisieren_btn = QPushButton("Liste aktualisieren")
        aktualisieren_btn.clicked.connect(self._aktualisieren_mit_rueckfrage)
        # Marco 10.11.2026 (UI-Abgleich): Bewertungsbogen der Zeile, in der man gerade steht,
        # wie im Reiter Teilnehmer.
        self.bewertungsbogen_btn = QPushButton("Bewertungsbogen (PDF)…")
        self.bewertungsbogen_btn.setToolTip("Bewertungsbogen für den Teilnehmer der aktuellen Zeile")
        self.bewertungsbogen_btn.setEnabled(False)
        self.bewertungsbogen_btn.clicked.connect(self._bewertungsbogen_exportieren)
        self.ablageort_btn = QPushButton("Ablageort öffnen")
        self.ablageort_btn.clicked.connect(lambda: _ablageort_ordner_oeffnen(self, self._ablageort))
        self.tabelle.currentCellChanged.connect(lambda *_: self._bewertungsbogen_knopf_aktualisieren())
        _kontextmenue_aus_knoepfen(
            self.tabelle, [self.bewertungsbogen_btn, None, speichern_btn, aktualisieren_btn],
            allgemein=(speichern_btn, aktualisieren_btn))

    def _hinweise_aufbauen(self) -> None:
        self.status_label = QLabel("")
        self.status_label.setTextFormat(Qt.PlainText)  # S-1: Meldungen immer als Klartext
        # Eigenes Label für den Komma-Hinweis (N6): orange und fett über ein Stylesheet statt
        # Rich Text im status_label, das seit S-1 nur Klartext zeigt (Desktop-Prüfung
        # 14.10.2026, Teil 3 Nr. 2 - vorher stand das rohe <span…> in der Statuszeile).
        self.hinweis_label = QLabel("")
        self.hinweis_label.setTextFormat(Qt.PlainText)
        self.hinweis_label.setWordWrap(True)
        self.hinweis_label.hide()
        self._eingabe_hinweis: str | None = None
        self._zu_hoch_hinweis: str | None = None  # Hinweis vom Tippen (T4), siehe _hinweise_zeigen
        # N8: Meldung einer verworfenen Eingabe - alle_speichern stellt sie seiner eigenen voran.
        self._verworfen_meldung: str | None = None
        # UX-Test 03.11.2026, X7: eigenes Label für Werte über dem Maximum (je Teilnehmer-ID).
        self.zu_hoch_label = QLabel("")
        self.zu_hoch_label.setTextFormat(Qt.PlainText)
        self.zu_hoch_label.setWordWrap(True)
        self.zu_hoch_label.hide()
        self._zu_hoch_je_teilnehmer: dict[int, str] = {}

    def _layout_aufbauen(self) -> None:
        filter_zeile = QHBoxLayout()
        filter_zeile.addWidget(QLabel("Filter Art/LK:"))
        filter_zeile.addWidget(self.filter_combo)
        filter_zeile.addSpacing(16)
        filter_zeile.addWidget(QLabel("Filter Start-Nr.:"))
        filter_zeile.addWidget(self.filter_startnummer)
        filter_zeile.addSpacing(16)
        filter_zeile.addWidget(QLabel("Suche:"))
        filter_zeile.addWidget(self.filter_name)
        filter_zeile.addStretch()

        hinweis = QLabel(
            "Gelb hervorgehobene Zeilen enthalten noch nicht gespeicherte Änderungen. "
            "Der Filter blendet Zeilen nur aus, ungespeicherte Werte bleiben dabei erhalten."
        )
        hinweis.setWordWrap(True)

        button_zeile = QHBoxLayout()
        button_zeile.addWidget(self.speichern_btn)
        button_zeile.addWidget(self.aktualisieren_btn)
        button_zeile.addWidget(self.bewertungsbogen_btn)
        button_zeile.addWidget(self.ablageort_btn)
        button_zeile.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(filter_zeile)
        layout.addWidget(hinweis)
        layout.addWidget(self.tabelle)
        layout.addLayout(button_zeile)
        layout.addWidget(self.zu_hoch_label)
        layout.addWidget(self.hinweis_label)
        layout.addWidget(self.status_label)

    def hat_ungespeicherte_aenderungen(self) -> bool:
        """True, wenn mindestens eine Zeile von den zuletzt geladenen/gespeicherten
        Werten abweicht - z.B. um beim Tabwechsel vor Datenverlust zu warnen. Ein offenes
        Eingabefeld wird vorher übernommen."""
        self.tabelle.offenen_editor_beenden()
        for row in range(len(self._teilnehmer_je_zeile)):
            if self._zeile_ist_ungespeichert(row):
                return True
        return False

    # --- Zellwert-Schnittstelle (offene Punkte O7, 19.10.2026) ------------------------
    # Für Tests, Demoprüfung und Screenshots: Werte und Zustände je Zeile und Disziplin,
    # ohne die Darstellung der Zellen zu kennen. `feld` ist "suche" oder "anzeige"; Punkte
    # sind Texte wie in der Eingabe ("" = noch nicht eingetragen). Eine Disziplin, die in der
    # Zeile nicht erfasst wird (ED: nur die eigene), ergibt KeyError.

    _FELDER = ("suche", "anzeige")

    def zeilenanzahl(self) -> int:
        return len(self._teilnehmer_je_zeile)

    def teilnehmer_der_zeile(self, zeile: int) -> dict:
        """Stammdaten des Teilnehmers in `zeile` (Reihenfolge wie angezeigt)."""
        return self._teilnehmer_je_zeile[zeile]

    def zeile_von(self, teilnehmer_id: int) -> int | None:
        """Tabellenzeile eines Teilnehmers oder None, wenn er nicht in der Liste steht (z. B.
        „keine Teilnahme“). Per Filter ausgeblendete Zeilen werden gefunden."""
        return next((row for row, t in enumerate(self._teilnehmer_je_zeile) if t["id"] == teilnehmer_id), None)

    def zeile_zeigen(self, zeile: int) -> None:
        """Scrollt die Zeile in den sichtbaren Bereich (Demoprüfung)."""
        self.tabelle.scrollTo(self.tabelle.model().index(zeile, 0))

    def erfassbare_disziplinen(self, zeile: int) -> list[str]:
        """Disziplinen, für die die Zeile Punktezellen hat (ED: nur die eigene, DK: alle)."""
        return list(self._boxen_je_zeile[zeile])

    def spalte_bearbeitbar(self, zeile: int, spalte: int) -> bool:
        """Sieht in der Tabelle selbst nach, ob die Zelle eine Punktezelle ist (Flag
        ItemIsEditable; eine DQ/Abbruch-Sperre ändert daran nichts). Für ED-fremde
        Disziplinen („–“) muss das False sein - auch nachdem eine Zeile von DK auf ED
        umgestellt oder umsortiert wurde."""
        item = self.tabelle.item(zeile, spalte)
        return item is not None and bool(item.flags() & Qt.ItemIsEditable)

    def zellrechteck(self, zeile: int, spalte: int) -> QRect:
        """Rechteck der Zelle in Koordinaten von tabelle.viewport() (Demoprüfung)."""
        return self.tabelle.visualRect(self.tabelle.model().index(zeile, spalte))

    def _punktefeld(self, zeile: int, disziplin: str, feld: str) -> _PunkteItem:
        return self._boxen_je_zeile[zeile][disziplin][self._FELDER.index(feld)]

    def punkte(self, zeile: int, disziplin: str) -> tuple[str, str]:
        """(Suche, Anzeige) wie angezeigt (ein offenes Eingabefeld wird vorher übernommen)."""
        self.tabelle.offenen_editor_beenden()
        suche_feld, anzeige_feld = self._boxen_je_zeile[zeile][disziplin]
        return suche_feld.text(), anzeige_feld.text()

    def punkte_eintragen(self, zeile: int, disziplin: str, suche: str | int | None = None,
                         anzeige: str | int | None = None) -> None:
        """Trägt Punkte ein wie eine Eingabe des Anwenders (None = Feld unverändert lassen).
        Der Wert gilt sofort als übernommen; Gültigkeitsprüfung beim Tippen siehe
        zelle_bearbeiten."""
        self.tabelle.offenen_editor_beenden()
        for feld, wert in (("suche", suche), ("anzeige", anzeige)):
            if wert is not None:
                self._punktefeld(zeile, disziplin, feld).setText(str(wert))

    def status(self, zeile: int) -> tuple[bool, bool]:
        """(Disqualifiziert, Abbruch) wie angezeigt."""
        dq_box, abbruch_box = self._status_boxen_je_zeile[zeile]
        return dq_box.isChecked(), abbruch_box.isChecked()

    def abbruch_grund(self, zeile: int) -> str | None:
        """R7: angezeigter Abbruchgrund (Code aus ABBRUCH_GRUENDE, "ohne_grund" oder None)."""
        return self._status_boxen_je_zeile[zeile][1].grund()

    def status_setzen(self, zeile: int, dq: bool | None = None, abbruch: bool | str | None = None) -> None:
        """Setzt Disqualifiziert/Abbruch wie ein Klick des Anwenders (None = unverändert).
        `abbruch` als Code aus ABBRUCH_GRUENDE wählt einen Grund (R7), True/False wie ein
        Häkchen (True = Abbruch ohne Grund)."""
        self.tabelle.offenen_editor_beenden()
        dq_box, abbruch_box = self._status_boxen_je_zeile[zeile]
        if dq is not None:
            dq_box.setChecked(dq)
        if isinstance(abbruch, str):
            abbruch_box.setGrund(abbruch)
        elif abbruch is not None:
            abbruch_box.setChecked(abbruch)

    def _status_der_zeile(self, row: int) -> tuple[bool, str | None]:
        """(Disqualifiziert, Abbruchgrund) wie angezeigt - Vergleichsform zu
        _status_geladen_je_zeile (R7)."""
        dq_box, abbruch_box = self._status_boxen_je_zeile[row]
        return dq_box.isChecked(), abbruch_box.grund()

    @staticmethod
    def _punkte_gesperrt(status: tuple[bool, str | None]) -> bool:
        """Punkte gesperrt bei Disqualifiziert und Abbruch ohne Grund; mit Grund gilt eine
        Teilbewertung, die Punkte bleiben eingebbar (R7, Marco 01.11.2026)."""
        return bool(status[0]) or status[1] == _ABBRUCH_OHNE_GRUND

    def zelle_gesperrt(self, zeile: int, disziplin: str) -> bool:
        """True, solange BEIDE Punktezellen der Disziplin wegen Disqualifiziert/Abbruch
        gesperrt sind (leer sind sie dann ebenfalls, siehe punkte())."""
        return not any(f.isEnabled() for f in self._boxen_je_zeile[zeile][disziplin])

    def zeile_ungespeichert(self, zeile: int) -> bool:
        """True, wenn die Zeile vom zuletzt gespeicherten Stand abweicht (gelb markiert)."""
        self.tabelle.offenen_editor_beenden()
        return self._zeile_ist_ungespeichert(zeile)

    def zellzustand(self, zeile: int, disziplin: str, feld: str) -> dict:
        """Darstellungszustand einer Punktezelle: `zu_hoch` (roter Rahmen), `tooltip` und
        `hintergrund` (Farbe der Markierung „ungespeichert“ als „#rrggbb“, kleingeschrieben;
        None, solange die Zeile nicht ungespeichert ist)."""
        self.tabelle.offenen_editor_beenden()
        item = self._punktefeld(zeile, disziplin, feld)
        return {
            "zu_hoch": bool(item.data(_ZU_HOCH_ROLLE)),
            "tooltip": item.toolTip(),
            "hintergrund": item.background().color().name().lower() if item.data(_UNGESPEICHERT_ROLLE) else None,
        }

    def zelle_bearbeiten(self, zeile: int, disziplin: str, feld: str) -> QLineEdit:
        """Macht die Punktezelle zur aktuellen Zelle, öffnet ihr Eingabefeld und gibt es mit
        Fokus zurück - für Tastatur-Tests (Validator, Komma-Hinweis, Tab/Enter). Nur für
        Tasten und Fokus gedacht, Werte über punkte()/punkte_eintragen()."""
        item = self._punktefeld(zeile, disziplin, feld)
        self.tabelle.scrollToItem(item)
        self.tabelle.setCurrentItem(item)
        self.tabelle.editItem(item)
        editor = self.tabelle.indexWidget(self.tabelle.model().index(item.row(), item.column()))
        if editor is None:
            raise ValueError(f"Zelle {disziplin}/{feld} in Zeile {zeile} lässt sich nicht bearbeiten (gesperrt?)")
        editor.setFocus()
        return editor

    def aktualisieren(self) -> None:
        """Baut die Tabelle komplett neu aus der Datenbank auf (verwirft dabei nicht
        gespeicherte Änderungen!) und aktualisiert den Filter. Wird beim ersten Öffnen
        sowie über "Liste aktualisieren" aufgerufen. Die zuletzt per Spaltenklick
        gewählte Sortierung bleibt dabei erhalten (siehe _zeilen_aufbauen)."""
        self._neu_laden()

    def aktualisieren_falls_geaendert(self) -> None:
        """Wie aktualisieren(), aber nur, wenn sich die Datenbank seit dem letzten Aufbau
        geändert hat (für den Tabwechsel). Lasttest 16.10.2026: Der Neuaufbau kostete bei
        1000 Teilnehmern rund 5 s (damals ein Eingabefeld je Zelle; seit O8 deutlich weniger,
        siehe Fortschritt.md)."""
        stand = self._datenstand()
        if stand is not None and stand == self._geladener_datenstand:
            # Wie nach einem Neuaufbau: alte Status- und Komma-Hinweise ausblenden.
            self.status_label.setText("")
            self._eingabe_hinweis_ausblenden()
            return
        self.aktualisieren()

    def _datenstand(self) -> tuple[int, int] | None:
        """Kennung des Datenstands: total_changes zählt die geänderten Zeilen über diese
        Verbindung (auch aus anderen Reitern, zurückgerollte eingeschlossen), PRAGMA
        data_version die Commits anderer Verbindungen (z. B. einer zweiten
        Programminstanz). None, wenn die Datei gerade nicht lesbar ist (gesperrt, Stick
        abgezogen) - dann wird wie bisher neu aufgebaut, Fehler meldet der Neuaufbau."""
        try:
            return self.conn.total_changes, self.conn.execute("PRAGMA data_version").fetchone()[0]
        except sqlite3.Error:
            return None

    def _neu_laden(self, werte_override: dict | None = None, status_override: dict | None = None) -> None:
        """Gemeinsamer Kern von aktualisieren() (ohne Overrides) und
        aktualisieren_eingaben_erhalten() (mit den noch ungespeicherten Eingaben)."""
        # Vor dem Lesen merken, damit eine Änderung während des Aufbaus beim nächsten
        # Tabwechsel noch einen Neuaufbau auslöst.
        self._geladener_datenstand = self._datenstand()
        self._teilnehmer_je_zeile = list_teilnehmer(self.conn, nur_teilnehmende=True)
        if self._sortierspalte in _SORTIERSPALTEN_AUS_STAMMDATEN:
            # Sortierung nach Stammdaten: vor dem Aufbau sortieren, dann nur EIN Aufbau
            # (Desktop-Prüfung 14.10.2026, Teil 3 Nr. 6).
            self._teilnehmer_je_zeile.sort(
                key=lambda t: self._sortierschluessel_teilnehmer(t, self._sortierspalte),
                reverse=not self._sortieraufsteigend,
            )
        verworfen = self._zeilen_aufbauen(werte_override, status_override)
        # Codeprüfung 22.09., G9: list_teilnehmer() liefert immer die DB-Reihenfolge -
        # ohne erneutes Anwenden ging die per Spaltenklick gewählte Sortierung hier
        # verloren, während _sortierspalte/_sortieraufsteigend stehen blieben, sodass der
        # nächste Klick auf dieselbe Spalte die Richtung "umkehrte", obwohl die Tabelle gar
        # nicht (mehr) danach sortiert war. Erst nach dem Aufbau sortieren, weil einige
        # Sortierschlüssel (Punkte, DQ/Abbruch, Status) aus den Zeilen-Widgets gelesen
        # werden; die Werte stammen hier frisch aus der DB (bzw. aus den Overrides), es geht
        # also nichts verloren.
        if self._sortierspalte is not None and self._sortierspalte not in _SORTIERSPALTEN_AUS_STAMMDATEN:
            verworfen += self._sortieren_und_neu_aufbauen()

        # Filter-Auswahl beim Neuladen nach Möglichkeit beibehalten, statt immer auf
        # "Alle" zurückzuspringen.
        bisherige_auswahl = self.filter_combo.currentText()
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItem("Alle")
        self.filter_combo.addItems(alle_leistungsklassen(self.conn))
        index = self.filter_combo.findText(bisherige_auswahl)
        self.filter_combo.setCurrentIndex(index if index >= 0 else 0)
        self.filter_combo.blockSignals(False)

        self.status_label.setText("")
        self._filter_anwenden()
        self._verworfene_melden(verworfen)

    def _zeilen_aufbauen(
        self,
        werte_override: dict[int, dict[str, tuple[int | None, int | None]]] | None = None,
        status_override: dict[int, tuple[bool, str | None]] | None = None,
    ) -> list[str]:
        """Baut die Tabellenzeilen aus `self._teilnehmer_je_zeile` (in dessen aktueller
        Reihenfolge) komplett neu auf - gemeinsam genutzt von _neu_laden() (also
        aktualisieren() ohne Overrides und aktualisieren_eingaben_erhalten()) und
        _sortieren_und_neu_aufbauen(). Overrides sind nur die echten, noch nicht
        gespeicherten Abweichungen je Teilnehmer-ID (siehe _eingaben_je_id); alles andere
        kommt frisch aus der DB. `werte_override`/`status_override` überschreiben dabei nur die ANGEZEIGTEN
        Werte - `_geladen_je_zeile`/`_status_geladen_je_zeile` bleiben trotzdem auf dem
        zuletzt aus der DB gelesenen (= gespeicherten) Stand, damit der
        "ungespeichert"-Vergleich (siehe _zeile_ist_ungespeichert) korrekt bleibt.

        Rückgabe: Teilnehmer, deren ungespeicherte Punkte verworfen wurden, weil inzwischen
        Disqualifiziert/Abbruch gespeichert oder die Disziplin geändert ist - je Eintrag mit
        Grund (für _verworfene_melden)."""
        verworfen: list[str] = []
        ergebnis_rows = ergebnisse_je_teilnehmer(self.conn)
        werte_override = werte_override or {}
        status_override = status_override or {}
        # Ein noch offenes Eingabefeld gehört zur alten Zeilenbelegung; übernommen ist es
        # (wo nötig) schon über _eingaben_je_id.
        self.tabelle.offenen_editor_beenden(uebernehmen=False)
        with self._intern():
            verworfen = self._zeilen_fuellen(ergebnis_rows, werte_override, status_override)
        # Spaltenbreiten (und Schriftgröße) an den tatsächlichen Inhalt UND die verfügbare
        # Fensterbreite anpassen - siehe _spaltenbreiten_anpassen().
        self._spaltenbreiten_anpassen()
        return verworfen

    @contextlib.contextmanager
    def _intern(self):
        """Zellen ändern, ohne dass _zelle_geaendert darauf reagiert."""
        self._intern_tiefe += 1
        try:
            yield
        finally:
            self._intern_tiefe -= 1

    def _zelle_geaendert(self, item: QTableWidgetItem) -> None:
        """Eine Eingabe des Anwenders (Eingabefeld übernommen, Häkchen geklickt) bzw. von
        punkte_eintragen/status_setzen."""
        if self._intern_tiefe:
            return
        row, col = item.row(), item.column()
        if not 0 <= row < len(self._boxen_je_zeile):
            return
        if col in (_DQ_SPALTE, _ABBRUCH_SPALTE):
            self._status_umgeschaltet(row)
        elif col in _PUNKTESPALTEN:
            # Die Übernahme aus dem Eingabefeld ist keine neue Eingabe - ein Komma-Hinweis
            # von gerade eben bleibt stehen (er geht, wenn die nächste Zelle bearbeitet wird).
            self._aktualisiere_zeilenstatus(row, hinweis_ausblenden=not self._aus_editor)

    @staticmethod
    def _maximum_der_spalte(spalte: int) -> int:
        return SUCHE_MAX if any(spalte == paar[0] for paar in _ERGEBNIS_SPALTEN_JE_DISZIPLIN.values()) else ANZEIGE_MAX

    def _zeilen_fuellen(self, ergebnis_rows, werte_override, status_override) -> list[str]:
        """Kern von _zeilen_aufbauen (läuft unter _intern)."""
        verworfen: list[str] = []
        self._boxen_je_zeile = []
        self._geladen_je_zeile = []
        self._status_boxen_je_zeile = []
        self._status_geladen_je_zeile = []
        self.aufbau_kennung += 1
        # X7: neu aufbauen - jede Zeile meldet sich beim Füllen selbst wieder an.
        self._zu_hoch_je_teilnehmer.clear()
        self._zu_hoch_label_zeigen()

        self.tabelle.setRowCount(len(self._teilnehmer_je_zeile))
        for row, t in enumerate(self._teilnehmer_je_zeile):
            eintrag = self._zeile_fuellen(row, t, ergebnis_rows, werte_override, status_override)
            if eintrag is not None:
                verworfen.append(eintrag)
        return verworfen

    def _zeile_fuellen(self, row: int, t: dict, ergebnis_rows, werte_override, status_override) -> str | None:
        """Füllt eine Zeile; liefert den Eintrag für die Meldung „verworfene Eingaben“ oder None."""
        # .get() statt [] - dieselbe Absicherung wie in db.berechne_auswertung() (dort
        # als "Fix 10" dokumentiert): sollte die Teilnehmer/Ergebnisse-1:1-Invariante
        # doch einmal verletzt sein, führt das nur zu leeren Punktefeldern statt zu
        # einem Absturz des gesamten Tabs.
        aktuell = ergebnis_rows.get(t["id"], {})
        zutreffende_disziplinen = ALLE_DISZIPLINEN if t["art"] == "DK" else [t["disziplin"]]
        punkte_override = werte_override.get(t["id"], {})
        nummer = f"Nr. {t['startnummer']} – " if t["startnummer"] is not None else ""
        # Gründe für verworfene Eingaben dieser Person; am Zeilenende zu einem einzigen
        # Eintrag zusammengeführt (offener Punkt 18.10.2026: sonst stünde sie mehrfach da).
        gruende: list[str] = []
        for disziplin in punkte_override:
            if disziplin not in zutreffende_disziplinen:
                # Teil 3 Nr. 5: Disziplin inzwischen geändert - die Eingabe zur alten
                # Disziplin hat keinen Platz mehr und wird gemeldet statt still verworfen.
                gruende.append(f"{disziplin}: Disziplin inzwischen geändert")

        self.tabelle.setItem(row, 0, _info_item(str(t["startnummer"] or "")))
        self.tabelle.setItem(row, 1, _info_item(f"{t['nachname']}, {t['vorname']}"))
        self.tabelle.setItem(row, 2, _info_item(t["rufname_hund"]))
        self.tabelle.setItem(row, 3, _info_item(leistungsklasse_label(t)))

        boxen, geladen = self._punktezellen_fuellen(row, aktuell, zutreffende_disziplinen, punkte_override)
        self._boxen_je_zeile.append(boxen)
        self._geladen_je_zeile.append(geladen)

        angezeigt_dq, angezeigt_abbruch = self._statuszellen_fuellen(row, t, aktuell, status_override)

        # Punkteeingabe sperren/leeren, wenn Disqualifiziert/Abbruch bereits gesetzt
        # ist (auch direkt nach dem Aufbau, nicht erst bei der nächsten Umschaltung).
        if punkte_override and self._punkte_gesperrt((angezeigt_dq, angezeigt_abbruch)):
            # Ungespeicherte Punkte, aber inzwischen DQ/Abbruch in der DB - die Eingabe
            # wird verworfen; der Aufrufer meldet das (Marco, 02.10.2026).
            gruende.append("inzwischen „Disqualifiziert“ oder „Abbruch“ gespeichert")
        eintrag = f"{nummer}{t['nachname']}, {t['vorname']} ({'; '.join(gruende)})" if gruende else None
        self._punkteeingabe_sperren(row, self._punkte_gesperrt((angezeigt_dq, angezeigt_abbruch)))
        self._aktualisiere_zeilenstatus(row)
        return eintrag

    def _punktezellen_fuellen(
        self, row: int, aktuell: dict, zutreffende_disziplinen, punkte_override: dict
    ) -> tuple[dict[str, tuple[_PunkteItem, _PunkteItem]], dict[str, tuple[int | None, int | None]]]:
        """Punktezellen (Suche/Anzeige je Disziplin) einer Zeile; liefert die Zellen und die
        aus der Datenbank geladenen Werte je Disziplin."""
        boxen: dict[str, tuple[_PunkteItem, _PunkteItem]] = {}
        geladen: dict[str, tuple[int | None, int | None]] = {}
        for disziplin in ALLE_DISZIPLINEN:
            spalte_suche, spalte_anzeige = _ERGEBNIS_SPALTEN_JE_DISZIPLIN[disziplin]
            if disziplin not in zutreffende_disziplinen:
                # Disziplin gilt für diesen Teilnehmer nicht (ED) - nicht bearbeitbares „–“.
                # Rückmeldung 23.09.: nach einer Umstellung DK -> ED (oder wenn beim
                # Sortieren eine ED-Zeile auf die Position einer DK-Zeile rutscht) darf
                # keine Punktezelle des früheren Aufbaus stehen bleiben - setItem ersetzt
                # die Zelle vollständig (siehe spalte_bearbeitbar).
                for spalte in (spalte_suche, spalte_anzeige):
                    leer = _info_item("–")
                    leer.setForeground(_farbe("gedaempft"))
                    self.tabelle.setItem(row, spalte, leer)
                continue

            db_spalte_suche, db_spalte_anzeige = DISZIPLIN_SPALTEN[disziplin]
            suche_wert = aktuell.get(db_spalte_suche)
            anzeige_wert = aktuell.get(db_spalte_anzeige)
            angezeigt_suche, angezeigt_anzeige = punkte_override.get(
                disziplin, (suche_wert, anzeige_wert)
            )

            # Leeres Feld = "noch nicht eingetragen" - ohne jede Vorbelegung (weder
            # "0" noch ein Platzhalterzeichen), damit ein versehentlich stehen
            # gelassenes Feld nicht als echte 0-Punkte-Bewertung gespeichert wird.
            suche_feld = _PunkteItem("" if angezeigt_suche is None else str(angezeigt_suche))
            self.tabelle.setItem(row, spalte_suche, suche_feld)
            anzeige_feld = _PunkteItem("" if angezeigt_anzeige is None else str(angezeigt_anzeige))
            self.tabelle.setItem(row, spalte_anzeige, anzeige_feld)

            boxen[disziplin] = (suche_feld, anzeige_feld)
            geladen[disziplin] = (suche_wert, anzeige_wert)
        return boxen, geladen

    def _statuszellen_fuellen(self, row: int, t: dict, aktuell: dict, status_override: dict) -> tuple[bool, str | None]:
        """Zellen Disqualifiziert, Abbruch und Status einer Zeile; liefert die angezeigten Werte
        (Disqualifiziert, Abbruchgrund)."""
        # Disqualifiziert/Abbruch (Nutzerwunsch 21.09.): zwei unabhängige Status -
        # Disqualifiziert als Häkchen (_HakenDelegate), Abbruch mit Grund (R7,
        # _AbbruchItem/_AbbruchDelegate).
        db_disqualifiziert = bool(aktuell.get("disqualifiziert"))
        db_abbruch = _abbruch_grund_aus_db(aktuell)  # R7: Grund statt Häkchen
        angezeigt_dq, angezeigt_abbruch = status_override.get(
            t["id"], (db_disqualifiziert, db_abbruch)
        )

        dq_box = _HakenItem(angezeigt_dq)
        self.tabelle.setItem(row, _DQ_SPALTE, dq_box)
        abbruch_box = _AbbruchItem(angezeigt_abbruch)
        self.tabelle.setItem(row, _ABBRUCH_SPALTE, abbruch_box)

        self._status_boxen_je_zeile.append((dq_box, abbruch_box))
        self._status_geladen_je_zeile.append((db_disqualifiziert, db_abbruch))

        self.tabelle.setItem(row, _STATUS_SPALTE, _info_item(""))
        return angezeigt_dq, angezeigt_abbruch

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._spaltenbreiten_anpassen()

    def showEvent(self, event) -> None:  # type: ignore[override]
        """Nutzerwunsch (22.09.): Ergebniserfassung soll bei maximiertem Fenster ohne
        horizontales Scrollen auf den Bildschirm passen. Ein resizeEvent allein reicht nicht,
        weil dieser Tab beim Maximieren des Fensters inaktiv (nicht die aktuell sichtbare
        QTabWidget-Seite) sein kann und dann kein zuverlässiges resizeEvent bekommt -
        showEvent fängt den späteren Wechsel zurück auf diesen Tab ab."""
        super().showEvent(event)
        self._spaltenbreiten_anpassen()

    def _spaltenbreiten_anpassen(self) -> None:
        """Passt Schriftgröße und Spaltenbreiten der Ergebnistabelle an die aktuell
        verfügbare Breite an (Nutzerwunsch 22.09.: bei maximiertem Fenster soll die Tabelle
        ohne horizontales Scrollen auf den Bildschirm passen). Die Schriftgröße wird ZUERST
        gesetzt, weil resizeColumnsToContents() danach bei genau dieser Schriftgröße misst.

        Wichtig: ResponsiveSchriftMixin (siehe dort) setzt bereits eine
        "QHeaderView::section { font-size: ... }"-Regel auf HauptFenster selbst - die
        kaskadiert auf JEDEN QHeaderView::section im Fenster, auch den dieser Tabelle. Ein
        reines setFont() auf den Header würde gegen diese geerbte Stylesheet-Regel verlieren,
        deshalb hier ein lokales Stylesheet direkt auf self.tabelle (überschreibt die von
        HauptFenster geerbte Regel nur für diese Tabelle, andere Tabs bleiben unberührt)."""
        breite = self.tabelle.viewport().width()
        self._tabellenschrift_anpassen(breite)
        self.tabelle.resizeColumnsToContents()

        # Spalten 0..(_STATUS_SPALTE-1): Start-Nr./Name/Hund/Art-LK, alle Disziplin-
        # Punktepaare sowie Disqualifiziert/Abbruch. Die Status-Spalte selbst bleibt außen
        # vor - die bekommt den Restplatz (setStretchLastSection und ausdrücklich unten,
        # siehe "Restplatz ausdrücklich an die Status-Spalte"), dafür wird ihr
        # längster möglicher Inhalt ("nicht gespeichert" mit Symbol, siehe _aktualisiere_zeilenstatus)
        # vorab von der verfügbaren Breite abgezogen, damit sie nicht auf (fast) 0
        # zusammengedrückt wird.
        # + Symbol (16) mit Abstand und Zellenrand. Ein längerer Status („Abbruch: <Grund>“, T3)
        # endet bei wenig Platz mit „…“; der Grund steht ganz in der Spalte „Abbruch“ und im
        # Tooltip (Nachtest 2, N2).
        status_minimum = self.tabelle.fontMetrics().horizontalAdvance("nicht gespeichert") + 16 + 44
        breite_fuer_fixspalten = max(breite - status_minimum, 0)

        natuerlich, minima, harte_minima = self._spaltenminima()

        # Nachtest 2 (N1): Ist die Zelle leer, misst resizeColumnsToContents nur die Kopfzeile -
        # die Abbruch-Spalte blieb dann so schmal („Verletzu…“), solange der Platz ohnehin reichte.
        natuerlich = [max(n, m) for n, m in zip(natuerlich, minima)]
        ziel = _ergebnis_spaltenbreiten_verteilen(
            natuerlich, minima, breite_fuer_fixspalten, harte_minima
        )
        for c, w in enumerate(ziel):
            self.tabelle.setColumnWidth(c, w)
        # Restplatz ausdrücklich an die Status-Spalte (Marco 09.10.2026): setStretchLastSection
        # streckt nur bei einer Größenänderung neu. Nach einem Neuaufbau ohne Größenänderung
        # (Speichern, "Liste aktualisieren") blieb sie sonst bei ihrer Inhaltsbreite stehen,
        # und bei breiten Fenstern stand rechts eine graue Lücke.
        # Nachtest 2 (N2): auch schmaler als ihr Inhalt (Text endet dann mit „…“) - sonst behielt
        # sie die Breite von resizeColumnsToContents und ragte über den Rand.
        rest = breite - sum(ziel)
        self.tabelle.setColumnWidth(_STATUS_SPALTE, max(rest, 40))
        # UX-Test 02.10.2026, K1: Zeilen mindestens so hoch wie ein Eingabefeld - sonst
        # wurden eingetippte Punkte unten abgeschnitten.
        if self._feldhoehe is None:
            self._feldhoehe = QLineEdit().sizeHint().height()
        feldhoehe = self._feldhoehe
        kopf = self.tabelle.verticalHeader()
        if kopf.defaultSectionSize() < feldhoehe + 4:
            kopf.setDefaultSectionSize(feldhoehe + 4)

    def _tabellenschrift_anpassen(self, breite: int) -> None:
        """Schriftgröße der Tabelle (Kopf, Zellen) nach der verfügbaren Breite, siehe
        _spaltenbreiten_anpassen."""
        pt = _responsive_schriftgroesse(breite, schmal=1000, breit=1600, pt_schmal=7.5, pt_breit=9.5)
        # Marcos Entscheidung R6 (UX-Test 03.11.2026, X2): bei „Sehr groß“ nur Faktor 1,15,
        # solange das Fenster nicht maximiert ist - sonst schnitten die Kopfzeilen ab.
        faktor = schrift_faktor()
        if faktor > _ERGEBNIS_FAKTOR_NICHT_MAXIMIERT and not self.window().isMaximized():
            pt = pt / faktor * _ERGEBNIS_FAKTOR_NICHT_MAXIMIERT

        # Stylesheet nur bei geänderter Schriftgröße neu setzen (Teil 3 Nr. 6).
        if self._tabelle_pt != round(pt, 1):
            self._tabelle_pt = round(pt, 1)
            self.tabelle.setStyleSheet(
                f"QHeaderView::section {{ font-size: {pt:.1f}pt; }} "
                f"QTableWidget::item {{ font-size: {pt:.1f}pt; }}"
            )
            # Schrift der Tabelle selbst: gilt für die Delegates und das Eingabefeld beim
            # Bearbeiten (früher eine setFont-Schleife über alle Eingabefelder).
            font = self.tabelle.font()
            font.setPointSizeF(pt)
            self.tabelle.setFont(font)

    def _spaltenminima(self) -> tuple[list[int], list[int], list[int]]:
        """Natürliche Breiten, Mindestbreiten und „harte“ Mindestbreiten der Spalten vor der
        Status-Spalte (Eingabe für _ergebnis_spaltenbreiten_verteilen)."""
        punktespalten = {c for paar in _ERGEBNIS_SPALTEN_JE_DISZIPLIN.values() for c in paar}
        minimum_punkte = max(self.tabelle.fontMetrics().horizontalAdvance("88") + 24, 56)

        # Nutzerwunsch (22.09.): Spaltenüberschriften sollen nicht mehr abgeschnitten
        # werden - die bisherigen Minima (Zelleninhalt) orientierten sich nur am Zelleninhalt
        # ("88" bzw. fix 44px für die Checkbox-Spalten), nicht am Headertext. Deshalb hier
        # zusätzlich je Spalte die Breite der längsten Headerzeile ermitteln (bei den
        # jetzt mehrzeiligen Disziplin-Headern mit "\n" die breitere der beiden Zeilen,
        # bei einzeiligen wie "Disqualifiziert"/"Abbruch" die volle Textbreite, da dort
        # mangels Leerzeichen kein Umbruch möglich ist) und als zusätzliche Untergrenze
        # verwenden.
        header_metriken = self.tabelle.horizontalHeader().fontMetrics()

        def header_zeilen_breite(spalte: int) -> int:
            text = self.tabelle.horizontalHeaderItem(spalte).text()
            return max(header_metriken.horizontalAdvance(zeile) for zeile in text.split("\n")) + 24

        natuerlich = [self.tabelle.columnWidth(c) for c in range(_STATUS_SPALTE)]
        minima = []
        # CI-Regression (22.09.): auf CI/Linux fallen die Schriftmetriken für Headertexte
        # teils ein paar Pixel breiter aus als lokal unter Windows - dort reichte die
        # Summe der obigen (headertext-basierten) Minima bei 1300px knapp nicht mehr aus,
        # obwohl lokal alles passte. harte_minima hält je Spalte den rein inhaltsbasierten
        # Wert von vor dieser Headertext-Erweiterung vor - als Fallback für
        # _ergebnis_spaltenbreiten_verteilen, falls die obigen Minima allein nicht reichen
        # (dann ggf. minimal abgeschnittener Headertext statt Scrollbalken, siehe dortige
        # Docstring-Erläuterung).
        harte_minima = []
        for c in range(_STATUS_SPALTE):
            if c in punktespalten:
                minima.append(max(minimum_punkte, header_zeilen_breite(c)))
                harte_minima.append(minimum_punkte)
            elif c == _DQ_SPALTE:
                minima.append(max(44, header_zeilen_breite(c)))
                harte_minima.append(44)
            elif c == _ABBRUCH_SPALTE:
                # R7: Platz für den Grund ("Verletzung Hund").
                # + Pfeil der offenen Auswahlliste (Verifikation R7, Befund 8).
                # UX-Test 03.11.2026, X5: + Platz für den Pfeil der zugeklappten Zelle.
                # UX-Test 2026-11, T3: längster Grund aus der Liste statt eines festen Textes.
                abbruch_breite = max(
                    self.tabelle.fontMetrics().horizontalAdvance(text) for text, _ in ABBRUCH_GRUENDE.values()
                ) + 48
                minima.append(max(abbruch_breite, header_zeilen_breite(c)))
                harte_minima.append(abbruch_breite)
            else:
                # Start-Nr./Name/Hund/Art-LK: reiner Text ohne Eingabefeld, schrumpft nicht
                # unter die eigene natürliche Breite (soll nicht abgeschnitten werden).
                minima.append(natuerlich[c])
                harte_minima.append(natuerlich[c])
        return natuerlich, minima, harte_minima

    def _spalte_geklickt(self, spalte: int) -> None:
        """Reagiert auf einen Klick auf eine Spaltenüberschrift: sortiert danach, erneuter
        Klick auf dieselbe Spalte kehrt die Richtung um (siehe Klassen-/Konstruktor-
        Docstring zur Begründung der eigenen Sortierlogik statt Qt-Bordmittel)."""
        if self._sortierspalte == spalte:
            self._sortieraufsteigend = not self._sortieraufsteigend
        else:
            self._sortierspalte = spalte
            self._sortieraufsteigend = True
        self.tabelle.horizontalHeader().setSortIndicator(
            spalte, Qt.AscendingOrder if self._sortieraufsteigend else Qt.DescendingOrder
        )
        self._verworfene_melden(self._sortieren_und_neu_aufbauen())

    @staticmethod
    def _sortierschluessel_teilnehmer(t: dict, spalte: int):
        """Schlüssel der Stammdaten-Spalten (Start-Nr., Name, Hund, Prüfung); Namen nach
        deutscher Gewohnheit (db.sortierschluessel_text, Teil 3 Nr. 4)."""
        if spalte == 0:
            return t["startnummer"] if t["startnummer"] is not None else -1
        if spalte == 1:
            return sortierschluessel_text(f"{t['nachname']}, {t['vorname']}")
        if spalte == 2:
            return sortierschluessel_text(t["rufname_hund"])
        return pruefung_sortierschluessel(leistungsklasse_label(t))

    def _sortierschluessel_fuer_zeile(self, row: int, spalte: int):
        """Sortierschlüssel für Zeile `row` bezogen auf die VOR dem Sortieren gültige
        Zeilenreihenfolge (self._teilnehmer_je_zeile/_boxen_je_zeile/
        _status_boxen_je_zeile sind zu diesem Zeitpunkt noch nicht umsortiert)."""
        if spalte in _SORTIERSPALTEN_AUS_STAMMDATEN:
            return self._sortierschluessel_teilnehmer(self._teilnehmer_je_zeile[row], spalte)
        if spalte == _DQ_SPALTE:
            return self._status_boxen_je_zeile[row][0].isChecked()
        if spalte == _ABBRUCH_SPALTE:
            return self._status_boxen_je_zeile[row][1].text()
        if spalte == _STATUS_SPALTE:
            item = self.tabelle.item(row, spalte)
            return item.text() if item is not None else ""
        for disziplin, (spalte_suche, spalte_anzeige) in _ERGEBNIS_SPALTEN_JE_DISZIPLIN.items():
            if spalte not in (spalte_suche, spalte_anzeige):
                continue
            boxen = self._boxen_je_zeile[row].get(disziplin)
            if boxen is None:
                return -1
            feld = boxen[0] if spalte == spalte_suche else boxen[1]
            wert = self._feldwert(feld)
            return wert if wert is not None else -1
        return ""

    def _sortieren_und_neu_aufbauen(self) -> list[str]:
        """Sortiert self._teilnehmer_je_zeile nach der zuletzt gewählten Spalte/Richtung
        und baut die Tabelle neu auf - sichert VORHER die aktuellen (ggf. noch nicht
        gespeicherten) Eingaben je Teilnehmer-ID, damit beim Neuaufbau keine ungespeicherte
        Eingabe verloren geht (siehe Klassen-/Konstruktor-Docstring)."""
        werte_je_id, status_je_id = self._eingaben_je_id()

        reihenfolge = sorted(
            range(len(self._teilnehmer_je_zeile)),
            key=lambda row: self._sortierschluessel_fuer_zeile(row, self._sortierspalte),
            reverse=not self._sortieraufsteigend,
        )
        self._teilnehmer_je_zeile = [self._teilnehmer_je_zeile[i] for i in reihenfolge]

        verworfen = self._zeilen_aufbauen(werte_je_id, status_je_id)
        self._filter_anwenden()
        return verworfen

    def _eingaben_je_id(self) -> tuple[dict, dict]:
        """Nur die tatsächlich noch NICHT gespeicherten Eingaben (Punkte je Disziplin,
        DQ-Häkchen/Abbruchgrund) je Teilnehmer-ID - als Overrides für _zeilen_aufbauen().
        Bewusst nicht einfach alle angezeigten Werte: _zeilen_aufbauen() liest die
        gespeicherten Werte frisch aus der DB, ein unveränderter, aber veralteter
        Anzeigewert würde sonst als "ungespeichert" gelten und beim nächsten Speichern
        einen inzwischen anders gespeicherten Wert (z. B. aus dem Web zurückgeholte
        Ergebnisse) überschreiben oder löschen (Befund Nachprüfung 02.10.2026)."""
        self.tabelle.offenen_editor_beenden()
        werte_je_id: dict = {}
        status_je_id: dict = {}
        for row, t in enumerate(self._teilnehmer_je_zeile):
            status = self._status_der_zeile(row)
            if status != self._status_geladen_je_zeile[row]:
                status_je_id[t["id"]] = status
            if self._punkte_gesperrt(status):
                continue  # Punktefelder sind gesperrt/geleert - nichts zu übernehmen
            geladen = self._geladen_je_zeile[row]
            for disziplin, (suche_feld, anzeige_feld) in self._boxen_je_zeile[row].items():
                angezeigt = (self._feldwert(suche_feld), self._feldwert(anzeige_feld))
                if angezeigt != geladen[disziplin]:
                    werte_je_id.setdefault(t["id"], {})[disziplin] = angezeigt
        return werte_je_id, status_je_id

    def aktualisieren_eingaben_erhalten(self) -> None:
        """Lädt die Teilnehmerliste neu aus der Datenbank, behält dabei aber noch nicht
        gespeicherte Eingaben bei (Befund aus der Verifikation "keine Teilnahme",
        02.10.2026): Wurde beim Tabwechsel das Speichern abgelehnt, lud der Reiter vorher
        gar nicht neu - ein inzwischen als "keine Teilnahme" markierter (oder neu
        angelegter) Teilnehmer blieb bis "Liste aktualisieren" fälschlich drin bzw.
        fehlte. Eingaben zu Teilnehmern, die nicht mehr in der Liste stehen, entfallen."""
        self._neu_laden(*self._eingaben_je_id())

    def _verworfene_melden(self, verworfen: list[str]) -> None:
        """Hinweis, wenn beim Neuaufbau ungespeicherte Punkte verworfen wurden, weil für
        den Teilnehmer inzwischen Disqualifiziert/Abbruch gespeichert oder die Disziplin
        geändert ist (Grund steht je Eintrag dabei). Die Liste kommt als Rückgabewert aus
        _zeilen_aufbauen (kein Zwischenzustand im Objekt)."""
        if not verworfen:
            return
        namen = "\n".join(dict.fromkeys(verworfen))
        QMessageBox.information(
            self,
            "Eingaben verworfen",
            "Folgende noch nicht gespeicherte Punkte wurden verworfen:\n\n" + namen,
        )

    def _aktualisieren_mit_rueckfrage(self) -> None:
        """Reagiert auf den "Liste aktualisieren"-Button: warnt vorher, falls dabei
        ungespeicherte Änderungen verloren gingen."""
        if self.hat_ungespeicherte_aenderungen():
            if not _ja_nein(
                self,
                "Ungespeicherte Änderungen",
                "Es gibt noch nicht gespeicherte Ergebnisse. Beim Aktualisieren gehen diese "
                "verloren.\n\nTrotzdem aktualisieren?",
            ):
                return
        self.aktualisieren()

    def _filter_anwenden(self) -> None:
        """Blendet Zeilen anhand des aktuellen Filters nur aus/ein (setRowHidden),
        statt die Tabelle neu aufzubauen - so bleiben noch nicht gespeicherte
        Eingaben in ausgeblendeten Zeilen erhalten."""
        filter_wert = self.filter_combo.currentText()
        filter_startnr = self.filter_startnummer.text().strip()
        filter_name = self.filter_name.text()
        for row, t in enumerate(self._teilnehmer_je_zeile):
            passt = (
                filter_wert in ("Alle", "") or leistungsklasse_label(t) == filter_wert
            ) and (not filter_startnr or str(t["startnummer"] or "") == filter_startnr) and _name_passt(
                filter_name, t["nachname"], t["vorname"], t["rufname_hund"])
            self.tabelle.setRowHidden(row, not passt)
        self._bewertungsbogen_knopf_aktualisieren()

    def _teilnehmer_der_aktuellen_zeile(self) -> dict | None:
        row = self.tabelle.currentRow()
        if row < 0 or row >= len(self._teilnehmer_je_zeile) or self.tabelle.isRowHidden(row):
            return None
        return self._teilnehmer_je_zeile[row]

    def _bewertungsbogen_knopf_aktualisieren(self) -> None:
        self.bewertungsbogen_btn.setEnabled(self._teilnehmer_der_aktuellen_zeile() is not None)

    def _bewertungsbogen_exportieren(self) -> None:
        t = self._teilnehmer_der_aktuellen_zeile()
        if t is not None:
            _bewertungsbogen_fuer_teilnehmer(self, self.conn, self._ablageort, self.status_label, t["id"])

    @staticmethod
    def _feldwert(feld: QTableWidgetItem) -> int | None:
        """Liest eine Punktezelle als Zahl - leer (oder ein durch die Validierung noch
        unvollständiger Zwischenzustand) ergibt None, entspricht also "noch nicht
        eingetragen", ohne dass dafür ein Platzhalterwert im Feld stehen müsste."""
        text = feld.text().strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            return None

    def _zeile_ist_ungespeichert(self, row: int) -> bool:
        status = self._status_der_zeile(row)
        status_geaendert = status != self._status_geladen_je_zeile[row]
        if self._punkte_gesperrt(status):
            # Punkte-Felder sind gesperrt und geleert (siehe _punkteeingabe_sperren) - ihr
            # (leerer) Inhalt sagt nichts über einen noch zu speichernden Punkte-Stand aus,
            # sonst würde eine bereits gespeicherte Disqualifiziert-/Abbruch-Zeile mit
            # weiterhin in der DB stehenden Punkten dauerhaft als "nicht gespeichert"
            # markiert bleiben.
            return status_geaendert
        boxen = self._boxen_je_zeile[row]
        geladen = self._geladen_je_zeile[row]
        punkte_geaendert = any(
            (self._feldwert(suche_feld), self._feldwert(anzeige_feld)) != geladen[disziplin]
            for disziplin, (suche_feld, anzeige_feld) in boxen.items()
        )
        return punkte_geaendert or status_geaendert

    def _status_umgeschaltet(self, row: int) -> None:
        """Reagiert auf eine Änderung von Disqualifiziert (Häkchen) bzw. Abbruch
        (Auswahlliste, R7): sperrt/leert bei Bedarf die Punktezellen dieser Zeile und
        aktualisiert den Gespeichert-Status. Nur beim Übergang gesperrt -> entsperrt werden
        die Felder zuvor wieder mit dem zuletzt aus der DB geladenen Stand befüllt statt leer
        zu bleiben - die Punkte wurden beim Sperren NICHT gelöscht (siehe alle_speichern).
        Bleibt die Zeile offen (z. B. ein Abbruchgrund gewählt oder gewechselt), bleiben
        ungespeicherte Eingaben unangetastet (Verifikation R7, Befund 1)."""
        sperren = self._punkte_gesperrt(self._status_der_zeile(row))
        war_gesperrt = not any(f.isEnabled() for paar in self._boxen_je_zeile[row].values() for f in paar)
        with self._intern():
            if not sperren and war_gesperrt:
                geladen = self._geladen_je_zeile[row]
                for disziplin, (suche_feld, anzeige_feld) in self._boxen_je_zeile[row].items():
                    suche_wert, anzeige_wert = geladen[disziplin]
                    suche_feld.setText("" if suche_wert is None else str(suche_wert))
                    anzeige_feld.setText("" if anzeige_wert is None else str(anzeige_wert))
            self._punkteeingabe_sperren(row, sperren)
            self._aktualisiere_zeilenstatus(row)

    def _punkteeingabe_sperren(self, row: int, sperren: bool) -> None:
        """Sperrt (und leert) die Punktezellen einer Zeile, solange Disqualifiziert
        oder ein Abbruch ohne Grund gesetzt ist (mit Grund gilt die Teilbewertung, R7) -
        eine Punkteeingabe wäre dann ohnehin irrelevant, da
        berechne_auswertung() für einen solchen Teilnehmer keine aus Punkten berechnete
        Wertnote mehr bildet (siehe db.py). Rührt beim Entsperren den Feldinhalt bewusst
        NICHT an (siehe _status_umgeschaltet für die interaktive Wiederherstellung) - beim
        Neuaufbau der Tabelle (_zeilen_aufbauen) ist der Feldinhalt zu diesem Zeitpunkt
        bereits korrekt (ggf. inkl. einer noch nicht gespeicherten Eingabe aus
        werte_override) und darf nicht überschrieben werden."""
        with self._intern():
            for suche_feld, anzeige_feld in self._boxen_je_zeile[row].values():
                if sperren:
                    suche_feld.setText("")
                    anzeige_feld.setText("")
                suche_feld.setEnabled(not sperren)
                anzeige_feld.setEnabled(not sperren)

    def _eingabe_abgelehnt(self, feld: "_PunkteFeld", maximum: int) -> None:
        """Hinweis, wenn der Validator ein Zeichen ablehnt (Komma, Buchstabe, dritte
        Ziffer) - sonst wirkt es, als würde die Eingabe einfach verschluckt. Seit dem Nachtest 2
        (N8) wird die Zelle dann nicht übernommen; der Hinweis nennt den Grund."""
        if feld.ersetzt_noch_den_wert():
            # Noch nichts getippt und der Wert ganz markiert: das Zeichen fällt einfach weg, die
            # Zahl danach ersetzt den Wert wie gewohnt - nur der Hinweis erscheint (Verifikation
            # B14). Steht der Cursor hinter dem Wert, gilt das nicht (QS B22, K1).
            feld.selectAll()
            hinweis = (f"Nur ganze Punkte von 0 bis {maximum} eingeben - das Zeichen wurde nicht "
                       "übernommen.")
        else:
            feld.ablehnen(_ablehnungsgrund(feld.letzte_taste))
            hinweis = (f"Nur ganze Punkte von 0 bis {maximum} eingeben ({feld.abgelehnt_grund}) - diese "
                       "Eingabe wird nicht übernommen, der bisherige Wert bleibt. Feld leeren oder Esc "
                       "und neu eingeben.")
        QToolTip.showText(feld.mapToGlobal(feld.rect().bottomLeft()), hinweis, feld)
        # UX-Nachtest 03.10.2026, N6 (ersetzt den 8-Sekunden-Timer aus U5b): der Hinweis wurde
        # leicht übersehen - er steht orange und fett über der Statuszeile, seit dem UX-Test
        # 03.11.2026 (X8) bis die nächste Zelle bearbeitet wird. Seit der Desktop-Prüfung
        # (14.10.2026, Teil 3 Nr. 2) in einem eigenen Label als Klartext mit Stylesheet, damit
        # Statusmeldungen davon unberührt bleiben und kein Rich Text nötig ist.
        self._eingabe_hinweis = hinweis
        self._hinweise_zeigen()

    def _eingabe_verworfen(self, zeile: int, bisher: str) -> None:
        """N8: Meldung in der Statuszeile, wenn eine Zelle mit abgelehntem Zeichen nicht
        übernommen wurde - der Hinweis darüber verschwindet mit der nächsten Zelle."""
        t = self._teilnehmer_je_zeile[zeile]
        nr = t.get("startnummer")
        wer = f"Nr. {nr} {t['nachname']}" if nr is not None else t["nachname"]
        self._verworfen_meldung = (
            f"{wer}: Eingabe nicht übernommen (unzulässiges Zeichen) - es bleibt "
            + (f"„{bisher}“." if bisher else "das leere Feld.")
        )
        self.status_label.setText(self._verworfen_meldung)

    def _wert_beim_tippen_pruefen(self, feld: QLineEdit, maximum: int, text: str) -> None:
        """T4: roter Rahmen am offenen Eingabefeld und Klartext, solange der getippte Wert über
        dem Maximum liegt. Die Eingabe bleibt möglich (beim Speichern wird sie abgelehnt)."""
        if text.isdigit() and int(text) > maximum:
            feld.setStyleSheet(f"{_PUNKTE_EDITOR_STIL} border: 2px solid {_farbe('fehler').name()};")
            hinweis = f"Höchstens {maximum} Punkte - {text} ist zu hoch und lässt sich so nicht speichern."
            QToolTip.showText(feld.mapToGlobal(feld.rect().bottomLeft()), hinweis, feld)
            self._zu_hoch_hinweis = hinweis
            self._hinweise_zeigen()
        else:
            feld.setStyleSheet(_PUNKTE_EDITOR_STIL)
            self._zu_hoch_beim_tippen_ausblenden()

    def _zu_hoch_beim_tippen_ausblenden(self) -> None:
        """Nimmt nur den Hinweis aus _wert_beim_tippen_pruefen weg; ein Komma-Hinweis (X8) bleibt
        stehen - bei „6,5“ wird aus der 5 erst 65, danach muss der Komma-Hinweis noch da sein."""
        if self._zu_hoch_hinweis is not None:
            self._zu_hoch_hinweis = None
            self._hinweise_zeigen()

    def _hinweise_zeigen(self) -> None:
        """Zeigt den Hinweis vom Tippen (rot) und den Komma-Hinweis (orange) im hinweis_label,
        beide untereinander, wenn beides zutrifft."""
        texte = [t for t in (self._zu_hoch_hinweis, self._eingabe_hinweis) if t is not None]
        if not texte:
            self.hinweis_label.clear()
            self.hinweis_label.hide()
            return
        farbe = _farbe("fehler" if self._zu_hoch_hinweis is not None else "warnung")
        self.hinweis_label.setStyleSheet(f"color: {farbe.name()}; font-weight: bold;")
        self.hinweis_label.setText("\n".join(texte))
        self.hinweis_label.show()

    def _eingabe_hinweis_ausblenden(self) -> None:
        """Nimmt den Komma-Hinweis und den Hinweis vom Tippen wieder weg."""
        if self._eingabe_hinweis is not None or self._zu_hoch_hinweis is not None:
            self._eingabe_hinweis = None
            self._zu_hoch_hinweis = None
            self._hinweise_zeigen()

    def _aktualisiere_zeilenstatus(self, row: int, hinweis_ausblenden: bool = True) -> None:
        """Färbt die Zeile gelb und setzt den Status-Text, solange sich mindestens ein
        Wert vom zuletzt gespeicherten Stand unterscheidet. Punktezellen mit einem Wert
        über dem Maximum bekommen zusätzlich einen roten Rahmen (_ZU_HOCH_ROLLE, gezeichnet
        von _PunkteDelegate) und einen Tooltip."""
        if hinweis_ausblenden:
            self._eingabe_hinweis_ausblenden()  # neue Eingabe von außen: Komma-Hinweis (U5b) weg
        with self._intern():
            self._zeilenstatus_setzen(row)
        self._zu_hoch_merken(row)

    def _abbruch_mit_einem_klick(self, index) -> None:
        if index.column() != _ABBRUCH_SPALTE:
            return
        flags = index.flags()
        if flags & Qt.ItemIsEnabled and flags & Qt.ItemIsEditable:
            self.tabelle.edit(index)

    def _zu_hoch_merken(self, row: int) -> None:
        """UX-Test 03.11.2026, X7: Zum roten Rahmen eines Werts über dem Maximum gehört ein
        sichtbarer Klartext (vorher nur Tooltip und erst beim Speichern eine Meldung). Gemerkt
        je Teilnehmer-ID (übersteht Sortieren), angezeigt im eigenen zu_hoch_label - getrennt
        vom Komma-Hinweis, damit sich beide nicht gegenseitig überschreiben."""
        if not (0 <= row < len(self._teilnehmer_je_zeile) and row < len(self._boxen_je_zeile)):
            return
        t = self._teilnehmer_je_zeile[row]
        zu_hoch = []
        for disziplin in self._boxen_je_zeile[row]:
            for teil, spalte, maximum in zip(
                ("Suche", "Anzeige"), _ERGEBNIS_SPALTEN_JE_DISZIPLIN[disziplin], (SUCHE_MAX, ANZEIGE_MAX)
            ):
                item = self.tabelle.item(row, spalte)
                if item is not None and item.data(_ZU_HOCH_ROLLE):
                    zu_hoch.append(f"{disziplin} {teil} höchstens {maximum} Punkte "
                                   f"(eingegeben: {self._feldwert(item)})")
        if zu_hoch:
            nummer = t["startnummer"]
            wer = f"Nr. {nummer} {t['nachname']}" if nummer is not None else t["nachname"]
            self._zu_hoch_je_teilnehmer[t["id"]] = f"{wer}: " + ", ".join(zu_hoch)
        elif self._zu_hoch_je_teilnehmer.pop(t["id"], None) is None:
            return
        self._zu_hoch_label_zeigen()

    def _zu_hoch_label_zeigen(self) -> None:
        eintraege = list(self._zu_hoch_je_teilnehmer.values())
        if not eintraege:
            self.zu_hoch_label.clear()
            self.zu_hoch_label.hide()
            return
        if len(eintraege) > 3:
            eintraege = eintraege[:3] + [f"… und {len(eintraege) - 3} weitere"]
        self.zu_hoch_label.setStyleSheet(f"color: {_farbe('fehler').name()}; font-weight: bold;")
        self.zu_hoch_label.setText("Rot umrandet, so nicht speicherbar - bitte korrigieren: "
                                   + "; ".join(eintraege))
        self.zu_hoch_label.show()

    def _zeilenstatus_setzen(self, row: int) -> None:
        ungespeichert = self._zeile_ist_ungespeichert(row)
        pinsel = QBrush(_farbe("ungespeichert_bg" if ungespeichert else "zeile_bg"))
        maximum_je_spalte = {}
        for disziplin in self._boxen_je_zeile[row]:
            spalte_suche, spalte_anzeige = _ERGEBNIS_SPALTEN_JE_DISZIPLIN[disziplin]
            maximum_je_spalte[spalte_suche] = SUCHE_MAX
            maximum_je_spalte[spalte_anzeige] = ANZEIGE_MAX

        for col in range(self.tabelle.columnCount()):
            item = self.tabelle.item(row, col)
            if item is None:
                continue
            # Nur bei Änderung setzen - jede Änderung löst ein Neuzeichnen aus.
            if item.background() != pinsel:
                item.setBackground(pinsel)
            maximum = maximum_je_spalte.get(col)
            if maximum is not None:
                wert = self._feldwert(item)
                zu_hoch = wert is not None and wert > maximum
                if bool(item.data(_ZU_HOCH_ROLLE)) != zu_hoch:
                    item.setData(_ZU_HOCH_ROLLE, zu_hoch)
                if bool(item.data(_UNGESPEICHERT_ROLLE)) != ungespeichert:
                    item.setData(_UNGESPEICHERT_ROLLE, ungespeichert)
                tooltip = f"Höchstens {maximum} Punkte." if zu_hoch else ""
                if item.toolTip() != tooltip:
                    item.setToolTip(tooltip)

        status_item = self.tabelle.item(row, _STATUS_SPALTE)
        if status_item is not None:
            # Symbol statt „●“/„✓“ vor dem Text (Marco 01.11.2026, Erscheinungsbild „Beagle“).
            tooltip = ""
            if ungespeichert:
                status_item.setText("nicht gespeichert")
                status_item.setIcon(symbol("device-floppy", "warnung"))
                status_item.setForeground(_farbe("warnung"))
            elif self._zeile_ist_leer(row):
                # UX-Test 02.10.2026, K1: vorher stand auch bei noch leeren Zeilen
                # "gespeichert" - das wirkte, als seien schon Ergebnisse eingetragen.
                status_item.setText("noch kein Ergebnis")
                status_item.setIcon(QIcon())
                status_item.setForeground(_farbe("gedaempft"))
            else:
                text = self._gespeicherter_status_text(row)
                status_item.setText(text)
                status_item.setIcon(symbol("check", "ok"))
                status_item.setForeground(_farbe("ok"))
                if text != "gespeichert":
                    tooltip = f"gespeichert: {text}"  # die Spalte kann schmal sein
            if status_item.toolTip() != tooltip:
                status_item.setToolTip(tooltip)

    def _gespeicherter_status_text(self, row: int) -> str:
        """UX-Test 2026-11, T3: Disqualifiziert und Abbruch stehen ausdrücklich im Status -
        vorher stand dort nur „gespeichert“, und die Zeile wirkte wie ein normales Ergebnis."""
        disqualifiziert, grund = self._status_geladen_je_zeile[row]
        if disqualifiziert:
            return "disqualifiziert"
        if grund == _ABBRUCH_OHNE_GRUND:
            return "Abbruch"
        if grund:
            return f"Abbruch: {_abbruch_bezeichnung(grund)}"
        return "gespeichert"

    def _zeile_ist_leer(self, row: int) -> bool:
        """Weder Punkte noch Disqualifiziert/Abbruch - gespeichert oder eingegeben."""
        dq_box, abbruch_box = self._status_boxen_je_zeile[row]
        if dq_box.isChecked() or abbruch_box.isChecked() or any(self._status_geladen_je_zeile[row]):
            return False
        return all(
            self._feldwert(suche) is None and self._feldwert(anzeige) is None
            and self._geladen_je_zeile[row][disziplin] == (None, None)
            for disziplin, (suche, anzeige) in self._boxen_je_zeile[row].items()
        )

    def farben_auffrischen(self) -> None:
        """Färbt alle Zeilen nach einem Wechsel des Hintergrund-Designs neu - bewusst
        OHNE aktualisieren(), das die Tabelle aus der DB neu aufbauen und damit
        ungespeicherte Eingaben verwerfen würde."""
        for row in range(self.tabelle.rowCount()):
            for col in range(self.tabelle.columnCount()):
                item = self.tabelle.item(row, col)
                # "–"-Platzhalter für Disziplinen, die für diesen Teilnehmer nicht gelten.
                if item is not None and item.text() == "–" and not (item.flags() & Qt.ItemIsEditable):
                    with self._intern():
                        item.setForeground(_farbe("gedaempft"))
            self._aktualisiere_zeilenstatus(row)

