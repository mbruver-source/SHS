"""
Zellen, Delegates und Tabelle der Ergebniserfassung (seit 11.11.2026 aus desktop_ergebnis.py
ausgelagert, Code unverändert): Punkte-/Haken-/Abbruch-Zellen, ihre Delegates, das Punktefeld
und die Tabelle. Der Reiter selbst (ErgebnisTab) steht in desktop_ergebnis.py. Bewusst KEIN
`import app` (siehe desktop_programm.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QEvent,
    QModelIndex,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QRegularExpression,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QBrush,
    QPainter,
    QPalette,
    QPen,
    QPolygonF,
    QRegularExpressionValidator,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QAbstractItemDelegate,
    QAbstractItemView,
    QApplication,
    QComboBox,
    QLineEdit,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
)

from shs_core import (
    ABBRUCH_GRUENDE,
)
from desktop_darstellung import (
    _farbe,
)
from desktop_gemeinsam import (
    _ERGEBNIS_SPALTEN_JE_DISZIPLIN,
)

if TYPE_CHECKING:  # nur für die Typangabe; ein echter Import wäre ein Importkreis
    from desktop_ergebnis import ErgebnisTab

# Höchstpunktzahlen je Disziplin (entsprechen den CHECK-Constraints in db.py). UX-Test
# 02.10.2026, U5: das Punktefeld ließ "65" als Zwischenstand beim Tippen zu - solche
# Werte werden deshalb sofort rot markiert und beim Speichern im Klartext abgelehnt, statt
# erst an der Datenbank mit "CHECK constraint failed" zu scheitern.


def _punkte_validator(parent) -> QRegularExpressionValidator:
    """Nur Ziffern (höchstens zwei) - unabhängig von der Spracheinstellung des Systems. Der
    QIntValidator nahm in englischer/Linux-Einstellung "," als Tausender-Trennzeichen an
    ("45," statt Hinweis; CI-Befund 03.10.2026). Werte über dem Maximum markiert
    _aktualisiere_zeilenstatus rot, das Speichern lehnt sie im Klartext ab (U5)."""
    return QRegularExpressionValidator(QRegularExpression(r"\d{0,2}"), parent)


# Spalten der Ergebnistabelle, deren Sortierschlüssel nur aus den Stammdaten kommt.
_SORTIERSPALTEN_AUS_STAMMDATEN = (0, 1, 2, 3)

# --- Ergebniserfassung ohne Widget je Zelle (offene Punkte O8, 19.10.2026) -------------
# Die Zellen sind QTableWidgetItems, gezeichnet von zwei Delegates; ein Eingabefeld entsteht
# nur beim Bearbeiten. Ein Widget je Zelle war bei 1000 Teilnehmern zu langsam (Lasttest).

_PUNKTESPALTEN = frozenset(c for paar in _ERGEBNIS_SPALTEN_JE_DISZIPLIN.values() for c in paar)
# Rollen der Punktezellen, gesetzt von ErgebnisTab._aktualisiere_zeilenstatus.
_ZU_HOCH_ROLLE = Qt.UserRole + 1
_UNGESPEICHERT_ROLLE = Qt.UserRole + 2
# Das allgemeine Feld-Stylesheet (desktop_darstellung, padding 4px 8px) ist für eine
# Tabellenzelle zu groß - die Ziffern würden abgeschnitten.
_PUNKTE_EDITOR_STIL = "padding: 0px 2px;"


def _info_item(text: str) -> QTableWidgetItem:
    """Nur-Anzeige-Zelle (Start-Nr., Name, Hund, Prüfung, Status, „–“)."""
    item = QTableWidgetItem(text)
    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
    return item


class _PunkteItem(QTableWidgetItem):
    """Punktezelle: der Text ist der eingetragene Wert ("" = noch nicht eingetragen).
    Gesperrt (Disqualifiziert/Abbruch) über das Flag ItemIsEnabled - isEnabled/setEnabled
    wie beim früheren Eingabefeld, damit die Zeilenlogik unverändert bleibt."""

    def __init__(self, text: str = ""):
        super().__init__(text)
        self.setTextAlignment(Qt.AlignCenter)
        self.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)

    def isEnabled(self) -> bool:  # noqa: N802 - wie QWidget
        return bool(self.flags() & Qt.ItemIsEnabled)

    def setEnabled(self, an: bool) -> None:  # noqa: N802
        flags = self.flags()
        self.setFlags(flags | Qt.ItemIsEnabled if an else flags & ~Qt.ItemIsEnabled)


class _HakenItem(QTableWidgetItem):
    """Disqualifiziert-Zelle mit Häkchen; isChecked/setChecked wie bei QCheckBox (Abbruch
    seit R7: _AbbruchItem)."""

    def __init__(self, an: bool):
        super().__init__("")
        self.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
        self.setChecked(an)

    def isChecked(self) -> bool:  # noqa: N802
        return self.checkState() == Qt.Checked

    def setChecked(self, an: bool) -> None:  # noqa: N802
        self.setCheckState(Qt.Checked if an else Qt.Unchecked)


#: R7 (Marco 01.11.2026): Abbruch aus Daten vor R7, ohne Grund - verhält sich wie bisher
#: (Punkte gesperrt, keine Teilbewertung) und wird in der Auswahlliste nur dann angeboten.
_ABBRUCH_OHNE_GRUND = "ohne_grund"


def _abbruch_bezeichnung(grund: str | None) -> str:
    if not grund:
        return ""
    if grund == _ABBRUCH_OHNE_GRUND:
        return "Abbruch"
    return ABBRUCH_GRUENDE[grund][0]


def _abbruch_grund_aus_db(ergebnis: dict) -> str | None:
    """Grund wie in der Tabelle: None (kein Abbruch), Code aus ABBRUCH_GRUENDE oder
    _ABBRUCH_OHNE_GRUND für einen Abbruch ohne (gültigen) Grund."""
    if not ergebnis.get("abbruch"):
        return None
    grund = ergebnis.get("abbruch_grund")
    return grund if grund in ABBRUCH_GRUENDE else _ABBRUCH_OHNE_GRUND


class _AbbruchItem(QTableWidgetItem):
    """Abbruch-Zelle (R7, Marco 01.11.2026): leer oder ein Grund aus ABBRUCH_GRUENDE, gewählt
    über eine Auswahlliste (_AbbruchDelegate). isChecked/setChecked wie bei _HakenItem:
    irgendein Abbruch gesetzt bzw. Abbruch ohne Grund setzen/entfernen."""

    def __init__(self, grund: str | None):
        super().__init__("")
        self.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
        self.setTextAlignment(Qt.AlignCenter)
        self.setGrund(grund)

    def grund(self) -> str | None:
        return self.data(Qt.UserRole) or None

    def setGrund(self, grund: str | None) -> None:  # noqa: N802
        self.setData(Qt.UserRole, grund or "")
        self.setText(_abbruch_bezeichnung(grund))
        # UX-Test 03.11.2026, X5: voller Grund als Tooltip (die Spalte kann ihn abschneiden),
        # bei leerer Zelle der Hinweis, dass sich hier eine Auswahl öffnet.
        self.setToolTip(ABBRUCH_GRUENDE[grund][1] if grund in ABBRUCH_GRUENDE
                        else ("Abbruch ohne Grund" if grund else "Klicken: Abbruch mit Grund auswählen"))

    def isChecked(self) -> bool:  # noqa: N802
        return self.grund() is not None

    def setChecked(self, an: bool) -> None:  # noqa: N802
        if not an:
            self.setGrund(None)
        elif self.grund() is None:
            self.setGrund(_ABBRUCH_OHNE_GRUND)


class _AbbruchAuswahl(QComboBox):
    """Auswahlliste des Abbruchgrunds (R7, Verifikation Befund 2): Im zugeklappten Feld
    blättern Pfeiltasten, Bild-Tasten, Buchstaben und das Mausrad NICHT durch die Gründe -
    sonst würde jede Zwischenstufe sofort übernommen. Sie klappen die Liste auf; übernommen
    wird erst die Wahl in der Liste (Klick oder Enter)."""

    def keyPressEvent(self, event):  # noqa: N802
        # Durchreichen: Übernehmen/Abbrechen/Weiterspringen, reine Umschalt-/Strg-/Alt-Tasten
        # und Kürzel mit Strg/Alt (z. B. Strg+S, Umschalt+Tab) - Vor-Build-Verifikation 1.0.55,
        # Befund 4. Alt+Pfeil runter klappt die Liste wie gewohnt über Qt selbst auf.
        if (event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Escape, Qt.Key_Tab, Qt.Key_Backtab,
                            Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_AltGr)
                or event.modifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)):
            super().keyPressEvent(event)
            return
        self.showPopup()

    def wheelEvent(self, event):  # noqa: N802
        event.ignore()


class _AbbruchDelegate(QStyledItemDelegate):
    """Auswahlliste für den Abbruchgrund (R7). Sie klappt beim Öffnen gleich auf; die Wahl
    in der Liste gilt sofort (wie ein Häkchen)."""

    # Maße der gezeichneten Zelle in Pixeln (UX-Test 2026-11, T14). RAND wie bei den
    # Punktezellen; TEXT_RECHTS lässt Platz für das Dreieck. _spaltenbreiten_anpassen rechnet
    # mit PLATZ_NEBEN_TEXT.
    RAND = 2.5
    ECKE = 4
    PFEIL_ABSTAND = 10  # Mitte des Dreiecks vom rechten Rand
    PFEIL_HALBE_BREITE = 4
    TEXT_LINKS = 4
    TEXT_RECHTS = 18
    PLATZ_NEBEN_TEXT = 2 * RAND + TEXT_LINKS + TEXT_RECHTS

    def paint(self, painter, option, index):  # noqa: N802
        # UX-Test 03.11.2026, X5: wie ein zugeklapptes Auswahlfeld zeichnen (umrandet wie die
        # Punktefelder, Dreieck rechts) - vorher sah eine leere Zelle wie ein leeres Kästchen aus.
        if not (index.flags() & Qt.ItemIsEnabled and index.flags() & Qt.ItemIsEditable):
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ""
        widget = opt.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, widget)
        feld = QRectF(opt.rect).adjusted(self.RAND, self.RAND, -self.RAND, -self.RAND)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        fokus = bool(opt.state & QStyle.State_HasFocus)
        painter.setPen(QPen(opt.palette.color(QPalette.Link), 2) if fokus else QPen(_farbe("RAND"), 1))
        # Gelb wie die Punktefelder, solange die Zeile ungespeichert ist (_zeilenstatus_setzen
        # setzt den Zeilenhintergrund auf jede Zelle).
        hintergrund = index.data(Qt.BackgroundRole)
        ungespeichert = isinstance(hintergrund, QBrush) and hintergrund.color() == _farbe("ungespeichert_bg")
        painter.setBrush(_farbe("ungespeichert_bg") if ungespeichert else _farbe("FLAECHE"))
        painter.drawRoundedRect(feld, self.ECKE, self.ECKE)
        textfarbe = opt.palette.color(QPalette.Text)
        cx, cy = feld.right() - self.PFEIL_ABSTAND, feld.center().y()
        b = self.PFEIL_HALBE_BREITE
        painter.setPen(Qt.NoPen)
        painter.setBrush(textfarbe)
        painter.drawPolygon(QPolygonF([QPointF(cx - b, cy - 2), QPointF(cx + b, cy - 2), QPointF(cx, cy + 3)]))
        if text:
            painter.setFont(opt.font)
            painter.setPen(textfarbe)
            textfeld = feld.adjusted(self.TEXT_LINKS, 0, -self.TEXT_RECHTS, 0)
            # UX-Test 2026-11, T3: reicht der Platz nicht, endet der Grund mit „…“ statt
            # beidseitig abgeschnitten („letzung H“); der Tooltip nennt ihn vollständig.
            text = painter.fontMetrics().elidedText(text, Qt.ElideRight, int(textfeld.width()))
            painter.drawText(textfeld, int(Qt.AlignCenter), text)
        painter.restore()

    def createEditor(self, parent, option, index):  # noqa: N802
        combo = _AbbruchAuswahl(parent)
        combo.addItem("kein Abbruch", "")
        for code, (text, eintrag) in ABBRUCH_GRUENDE.items():
            combo.addItem(text, code)
            combo.setItemData(combo.count() - 1, eintrag, Qt.ToolTipRole)
        if index.data(Qt.UserRole) == _ABBRUCH_OHNE_GRUND:
            combo.addItem("Abbruch (ohne Grund)", _ABBRUCH_OHNE_GRUND)
        combo.activated.connect(lambda _i: (self.commitData.emit(combo), self.closeEditor.emit(combo)))
        # Mit Kontextobjekt: Wird das Feld vorher geschlossen, entfällt der Aufruf (Befund 5).
        QTimer.singleShot(0, combo, lambda: combo.isVisible() and combo.showPopup())
        return combo

    def setEditorData(self, editor, index):  # noqa: N802
        editor.setCurrentIndex(max(editor.findData(index.data(Qt.UserRole) or ""), 0))

    def setModelData(self, editor, model, index):  # noqa: N802
        grund = editor.currentData() or ""
        if grund == (index.data(Qt.UserRole) or ""):
            return
        model.setData(index, grund, Qt.UserRole)
        model.setData(index, _abbruch_bezeichnung(grund), Qt.DisplayRole)


#: Merker in _PunkteFeld.letzte_taste für Einfügen per Tastenkürzel (Verifikation B23).
_EINGEFUEGT = "<einfügen>"


def _ablehnungsgrund(zeichen: str) -> str:
    """Grund für ein vom Validator abgelehntes Zeichen einer Punktezelle (Nachtest 2, N8) -
    ohne Qt, damit einzeln testbar (QS B22, W4)."""
    if zeichen == _EINGEFUEGT:
        return "nur ganze Zahlen einfügen"
    if zeichen.isdigit():
        return "höchstens zwei Ziffern"
    if zeichen in (",", "."):
        return "keine Kommazahlen"
    if zeichen.isalpha():
        return "keine Buchstaben"
    return "nur Ziffern"


class _PunkteFeld(QLineEdit):
    """Eingabefeld einer Punktezelle mit dem Zustand der Ablehnung (Nachtest 2, N8) als
    Attribute statt als Qt-Properties (QS B22, W4):

    - `getippt`: der Anwender hat schon etwas eingegeben (isModified gilt während der
      Ablehnung bereits als True, deshalb ein eigener Merker);
    - `abgelehnt`/`abgelehnt_grund`: ein Zeichen wurde abgelehnt - die Zelle wird dann nicht
      übernommen; wer das Feld leert, dessen neue Eingabe gilt wieder;
    - `letzte_taste`: das zuletzt getippte Zeichen, für den Grund im Hinweis."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.getippt = False
        self.abgelehnt = False
        self.abgelehnt_grund: str | None = None
        self.letzte_taste = ""
        self._vorher_ganz_markiert = True
        self.textEdited.connect(self._getippt_merken)
        self.textChanged.connect(self._leeren_hebt_ablehnung_auf)

    def _getippt_merken(self, _text: str) -> None:
        self.getippt = True

    def _leeren_hebt_ablehnung_auf(self, text: str) -> None:
        if not text:
            self.abgelehnt = False

    def keyPressEvent(self, event) -> None:  # noqa: N802
        # Vor der Verarbeitung merken: inputRejected kommt aus der Basisklasse, und dann ist die
        # Markierung schon aufgehoben.
        # Beim Einfügen (Strg+V/Cmd+V) zählt nicht die Taste, sondern der eingefügte Text.
        self.letzte_taste = _EINGEFUEGT if event.matches(QKeySequence.Paste) else event.text()
        self._vorher_ganz_markiert = not self.text() or self.selectedText() == self.text()
        super().keyPressEvent(event)

    def ersetzt_noch_den_wert(self) -> bool:
        """True, solange ein Zeichen den bisherigen Wert noch ganz ersetzen würde: noch nichts
        getippt UND das Feld leer oder ganz markiert. QS B22, K1: Mit dem Cursor hinter einer
        vorhandenen „4“ war „,5“ sonst ein harmloses erstes Zeichen, und es wurde 45 gespeichert."""
        return not self.getippt and self._vorher_ganz_markiert

    def ablehnen(self, grund: str) -> None:
        """Merkt die Ablehnung; der erste Grund bleibt (bei „4,55“ ist das Komma aussagekräftig)."""
        if not self.abgelehnt:
            self.abgelehnt_grund = grund
        self.abgelehnt = True


class _PunkteDelegate(QStyledItemDelegate):
    """Zeichnet eine Punktezelle wie ein umrandetes Eingabefeld (roter Rahmen über dem
    Maximum, gelb solange ungespeichert, leer und ohne Rahmen auf abgesetzter Fläche wenn
    gesperrt) und öffnet zum Bearbeiten ein _PunkteFeld (QLineEdit) mit _punkte_validator. Lostippen
    ersetzt den Wert."""

    def __init__(self, tab: "ErgebnisTab"):
        super().__init__(tab.tabelle)
        self._tab = tab
        # T4: auch Escape (ohne Übernehmen) nimmt den Hinweis vom Tippen weg.
        self.closeEditor.connect(lambda *_: tab._zu_hoch_beim_tippen_ausblenden())

    def createEditor(self, parent, option, index):  # noqa: N802
        editor = _PunkteFeld(parent)
        editor.setValidator(_punkte_validator(editor))
        editor.setAlignment(Qt.AlignCenter)
        editor.setStyleSheet(_PUNKTE_EDITOR_STIL)
        maximum = self._tab._maximum_der_spalte(index.column())
        # Abgelehnte Zeichen (z. B. das Komma in "45,5") nicht stillschweigend schlucken,
        # sondern einen Hinweis zeigen (UX-Test 02.10.2026, U5). UX-Test 03.11.2026, X8: Er
        # bleibt stehen, bis die nächste Zelle bearbeitet wird - vorher nahm ihn die nächste
        # Ziffer gleich wieder weg, bei "4,5" also die "5", und aus 4,5 wurde unbemerkt 45.
        self._tab._eingabe_hinweis_ausblenden()
        # Nachtest 2 (N8, Marco 04.11.2026): nach einem abgelehnten Zeichen wird die Zelle nicht
        # übernommen - aus „4,5“ wurde sonst 45 und überschrieb den alten Wert (Zustand in
        # _PunkteFeld).
        editor.inputRejected.connect(lambda: self._tab._eingabe_abgelehnt(editor, maximum))
        # UX-Test 2026-11, T4 (Marco 04.11.2026, C24 teilweise erledigt): ein zu hoher Wert wird
        # schon beim Tippen rot umrandet und erklärt, nicht erst nach dem Übernehmen.
        editor.textChanged.connect(lambda text: self._tab._wert_beim_tippen_pruefen(editor, maximum, text))
        return editor

    def setEditorData(self, editor, index):  # noqa: N802
        # Qt ruft das bei jeder Änderung der Zelle erneut auf, etwa wenn ein Designwechsel
        # den Hintergrund neu setzt - eine schon getippte Zahl darf das nicht überschreiben
        # (QS 19.10.2026).
        if editor.isModified():
            return
        editor.setText(index.data(Qt.EditRole) or "")
        editor.selectAll()  # Lostippen ersetzt den Wert (Marco 18.10.2026)

    def setModelData(self, editor, model, index):  # noqa: N802
        # Nach dem Übernehmen übernimmt das zu_hoch_label (X7) den Hinweis vom Tippen (T4).
        self._tab._zu_hoch_beim_tippen_ausblenden()
        text = editor.text()
        if (index.data(Qt.EditRole) or "") == text:
            return
        if editor.abgelehnt:
            self._tab._eingabe_verworfen(index.row(), index.data(Qt.EditRole) or "")
            return
        self._tab._aus_editor = True
        try:
            model.setData(index, text, Qt.EditRole)
        finally:
            self._tab._aus_editor = False

    def updateEditorGeometry(self, editor, option, index):  # noqa: N802
        editor.setGeometry(option.rect)

    def eventFilter(self, editor, event):  # noqa: N802
        # Strg+Tab gehört dem Reiterwechsel (QTabWidget), nicht der Zellnavigation; die
        # Übernahme des Feldes erledigt dann hat_ungespeicherte_aenderungen.
        if (event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Tab, Qt.Key_Backtab)
                and event.modifiers() & Qt.ControlModifier):
            return False
        return super().eventFilter(editor, event)

    def paint(self, painter, option, index):
        if not index.flags() & Qt.ItemIsEditable:
            super().paint(painter, option, index)  # „–“ für eine ED-fremde Disziplin: schlichter Text
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        widget = opt.widget
        style = widget.style() if widget is not None else QApplication.style()
        text = opt.text
        opt.text = ""
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, widget)  # Zellhintergrund, Auswahl

        # Farben wie beim Eingabefeld im Stylesheet (desktop_darstellung, „Eingabefelder“:
        # FLAECHE/RAND, Fokus in der Akzentfarbe - die steht in QPalette.Link; Highlight ist
        # nur die blasse Auswahlfarbe). Gesperrte Zellen (DQ/Abbruch) sind eine deutlich
        # abgesetzte Fläche ohne Rahmen - FLAECHE_DISABLED war in Hell/Sand kaum von einer
        # leeren Zelle zu unterscheiden (Marco 19.10.2026).
        aktiv = bool(index.flags() & Qt.ItemIsEnabled)
        if not aktiv:
            fuellung = _farbe("gesperrt_bg")
        elif index.data(_UNGESPEICHERT_ROLLE):
            fuellung = _farbe("ungespeichert_bg")
        else:
            fuellung = _farbe("FLAECHE")
        if index.data(_ZU_HOCH_ROLLE):
            stift = QPen(_farbe("fehler"), 2)
        elif opt.state & QStyle.State_HasFocus:
            stift = QPen(opt.palette.color(QPalette.Link), 2)
        elif aktiv:
            stift = QPen(_farbe("RAND"), 1)
        else:
            stift = QPen(Qt.NoPen)
        feld = QRectF(opt.rect).adjusted(2.5, 2.5, -2.5, -2.5)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(stift)
        painter.setBrush(fuellung)
        painter.drawRoundedRect(feld, 4, 4)
        if aktiv and text:
            painter.setFont(opt.font)  # Schrift der Tabelle wie in den Info-Spalten
            painter.setPen(opt.palette.color(QPalette.Text))
            painter.drawText(feld, Qt.AlignCenter, text)
        painter.restore()


class _HakenDelegate(QStyledItemDelegate):
    """Häkchen mittig in der Zelle (Disqualifiziert). Umschalten per Klick in die
    Zelle oder mit der Leertaste; gesperrt nur, wenn die Zelle nicht aktiv ist."""

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        widget = opt.widget
        style = widget.style() if widget is not None else QApplication.style()
        indikator = style.subElementRect(QStyle.SE_ItemViewItemCheckIndicator, opt, widget)
        haken = QStyleOptionViewItem(opt)
        opt.features &= ~QStyleOptionViewItem.HasCheckIndicator
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, widget)
        rechteck = QRect(QPoint(0, 0), indikator.size())
        rechteck.moveCenter(option.rect.center())
        haken.rect = rechteck
        haken.state = (haken.state & ~QStyle.State_HasFocus) | (
            QStyle.State_On if opt.checkState == Qt.Checked else QStyle.State_Off
        )
        style.drawPrimitive(QStyle.PE_IndicatorItemViewItemCheck, haken, painter, widget)

    def editorEvent(self, event, model, option, index):  # noqa: N802
        flags = index.flags()
        if not (flags & Qt.ItemIsUserCheckable) or not (flags & Qt.ItemIsEnabled):
            return False
        typ = event.type()
        if typ == QEvent.MouseButtonDblClick:
            return event.button() == Qt.LeftButton
        if typ == QEvent.MouseButtonRelease:
            if event.button() != Qt.LeftButton or not option.rect.contains(event.position().toPoint()):
                return False
        elif typ == QEvent.KeyPress:
            if event.key() not in (Qt.Key_Space, Qt.Key_Select):
                return False
        else:
            return False
        an = Qt.CheckState(index.data(Qt.CheckStateRole)) == Qt.Checked
        return model.setData(index, (Qt.Unchecked if an else Qt.Checked).value, Qt.CheckStateRole)


class _ErgebnisTabelle(QTableWidget):
    """Tabelle der Ergebniserfassung: Tab/Umschalt+Tab springen nur durch bedienbare Zellen
    (Punkte, Disqualifiziert, Abbruch) - Suche → Anzeige → nächste Disziplin → DQ →
    Abbruch → nächste Zeile; Info-Spalten, „–“, gesperrte und ausgeblendete Zeilen werden
    übersprungen (Desktop-Prüfung 14.10.2026, Teil 3 Nr. 3)."""

    def _bedienbar(self, row: int, col: int) -> bool:
        if self.isRowHidden(row):
            return False
        item = self.item(row, col)
        if item is None:
            return False
        flags = item.flags()
        return bool(flags & Qt.ItemIsEnabled) and bool(flags & (Qt.ItemIsEditable | Qt.ItemIsUserCheckable))

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() in (Qt.Key_Tab, Qt.Key_Backtab) and event.modifiers() & Qt.ControlModifier:
            event.ignore()  # Strg+Tab: Reiter wechseln wie vor O8
            return
        if (event.key() in (Qt.Key_Delete, Qt.Key_Backspace) and not event.modifiers()
                and self.state() != QAbstractItemView.State.EditingState):
            # Entf/Rücktaste leeren eine markierte Punktezelle direkt - wie früher im
            # Eingabefeld (Verifikation O9).
            item = self.currentItem()
            if isinstance(item, _AbbruchItem):
                item.setGrund(None)  # R7: Entf nimmt den Abbruch zurück
                event.accept()
                return
            if item is not None and item.flags() & Qt.ItemIsEditable and item.flags() & Qt.ItemIsEnabled:
                item.setText("")
                event.accept()
                return
        super().keyPressEvent(event)

    def moveCursor(self, aktion, modifiers):  # noqa: N802
        if aktion not in (QAbstractItemView.CursorAction.MoveNext, QAbstractItemView.CursorAction.MovePrevious):
            return super().moveCursor(aktion, modifiers)
        aktuell = self.currentIndex()
        spalten, zeilen = self.columnCount(), self.rowCount()
        pos = aktuell.row() * spalten + aktuell.column() if aktuell.isValid() else -1
        schritt = 1 if aktion == QAbstractItemView.CursorAction.MoveNext else -1
        pos += schritt
        while 0 <= pos < zeilen * spalten:
            row, col = divmod(pos, spalten)
            if self._bedienbar(row, col):
                return self.model().index(row, col)
            pos += schritt
        # Keine weitere bedienbare Zelle: ungültiger Index - Tab bzw. Umschalt+Tab verlässt
        # dann die Tabelle, auch aus einem offenen Feld (sonst öffnete Qt dieselbe Zelle neu).
        return QModelIndex()

    def offenen_editor_beenden(self, uebernehmen: bool = True) -> None:
        """Schließt ein offenes Eingabefeld; mit `uebernehmen` gilt die getippte Zahl vorher
        als eingetragen (vor Speichern, Reiterwechsel, Schließen, Strg+S - die zuletzt
        getippte Zahl darf nie verloren gehen)."""
        index = self.currentIndex()
        editor = self.indexWidget(index) if index.isValid() else None
        if editor is None:
            return
        if uebernehmen:
            self.commitData(editor)
        self.closeEditor(editor, QAbstractItemDelegate.NoHint)
