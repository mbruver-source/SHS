"""Reine String-Logik-Tests fuer die Design-Erzeugung in desktop_darstellung.py - kein
Qt-Import noetig ausser dem, den desktop_darstellung.py selbst am Kopf schon mitbringt
(PySide6). Laeuft daher nur lokal, wenn PySide6 installiert ist - genau wie
die test_gui_*.py.

Erscheinungsbild „Schiefer und Signal“ (Marco 21.11.2026, berichte/Design-Richtung-2026-11.md):
drei Designs (Schiefer als Standard, Dunkel, Hoher Kontrast), der Akzent gehört zum Design;
die frühere Akzentfarb-Wahl und das Design „Hell“ sind entfallen."""

import unittest
from unittest import mock

import desktop_darstellung

# Referenz-Stylesheet des Standards (ohne den Kopfkommentar), Bildpfade auf /SHS/.
_REFERENZ_SCHIEFER = 'QMainWindow, QDialog {\n    background: #EEF0EC;\n}\nQWidget {\n    color: #1B2220;\n}\nQLabel {\n    color: #1B2220;\n}\n\n/* Reiter (Teilnehmer/Zeitplan/.../Datensicherung) */\nQTabWidget::pane {\n    border: 1px solid #C9CFCB;\n    background: #EEF0EC;\n    top: -1px;\n}\n/* Reiter durchsichtig: sonst übermalen sie die obere Rahmenlinie des Inhaltsbereichs\n(top: -1px), und die Linie erscheint nur in den Lücken (Marco, 16.10.2026). */\nQTabBar::tab {\n    background: transparent;\n    color: #4F5853;\n    padding: 8px 16px;\n    border: none;\n    border-bottom: 3px solid transparent;\n    margin-right: 2px;\n    font-weight: 600;\n}\nQTabBar::tab:selected {\n    color: #0F1513;\n    font-weight: 600;\n    border-bottom: 3px solid #2A3035;\n}\nQTabBar::tab:hover:!selected {\n    color: #0F1513;\n}\n\n/* Schaltflächen: neutral/sekundär als Standard; die jeweilige Haupt-Aktion eines\nReiters/Dialogs trägt objectName "primaerButton" (siehe z.B. TeilnehmerTab) und wird\nin der Akzentfarbe hervorgehoben - ebenso automatisch jeder Dialog-Default-Button (die "OK"-Schaltfläche\neiner QDialogButtonBox, über die Qt-eigene :default-Pseudoklasse, ohne dass jeder\nDialog einzeln angepasst werden muss). */\nQPushButton {\n    background: #FFFFFF;\n    color: #1B2220;\n    border: 1px solid #7A837E;\n    border-radius: 4px;\n    padding: 6px 14px;\n}\nQPushButton:hover {\n    background: #E4E8E5;\n}\nQPushButton:pressed {\n    background: #D6DCD8;\n}\nQPushButton:disabled {\n    color: #A3AAA6;\n    background: #F4F5F3;\n    border-color: #C9CFCB;\n}\nQPushButton#primaerButton, QPushButton:default:enabled {\n    background: #2A3035;\n    color: #FFFFFF;\n    border: 1px solid #2A3035;\n    font-weight: 600;\n}\nQPushButton#primaerButton:hover, QPushButton:default:enabled:hover {\n    background: #3B434A;\n    border-color: #3B434A;\n}\nQPushButton#primaerButton:pressed, QPushButton:default:enabled:pressed {\n    background: #1B2024;\n    border-color: #1B2024;\n}\n\n/* Eingabefelder */\nQLineEdit, QComboBox, QSpinBox, QDateEdit {\n    background: #FFFFFF;\n    border: 1px solid #7A837E;\n    border-radius: 4px;\n    padding: 4px 8px;\n    color: #1B2220;\n}\nQLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {\n    border: 1px solid #2A3035;\n    background: #EEF0EC;\n}\nQLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {\n    color: #A3AAA6;\n    background: #F4F5F3;\n}\nQComboBox::drop-down {\n    border: none;\n    width: 20px;\n}\n/* Ohne eigenes Bild zeichnet Qt bei gestaltetem Rahmen keinen Pfeil: Auswahlfelder sahen aus\nwie Textfelder und niemand erkannte, dass sie sich aufklappen lassen (Marco 12.11.2026). */\nQComboBox::down-arrow {\n    image: url("/SHS/pfeil_runter_1B2220.png");\n    width: 10px;\n    height: 10px;\n}\nQComboBox::down-arrow:disabled {\n    image: url("/SHS/pfeil_runter_A3AAA6.png");\n}\n/* Pfeilknöpfe der Zahlenfelder (Marco 01.11.2026, Erscheinungsbild „Beagle“): Sobald das\nFeld selbst einen Rahmen aus dem Stylesheet hat, zeichnet Qt die Knöpfe nur noch als flache\nKästchen ohne Pfeil. Deshalb eigene Knöpfe und Pfeile als Bild (_pfeile_bereitstellen()). */\nQSpinBox, QDateEdit {\n    padding-right: 22px;\n}\nQSpinBox::up-button, QDateEdit::up-button {\n    subcontrol-origin: border;\n    subcontrol-position: top right;\n    width: 20px;\n    border: none;\n    border-left: 1px solid #7A837E;\n    border-top-right-radius: 4px;\n    background: #FFFFFF;\n}\nQSpinBox::down-button, QDateEdit::down-button {\n    subcontrol-origin: border;\n    subcontrol-position: bottom right;\n    width: 20px;\n    border: none;\n    border-left: 1px solid #7A837E;\n    border-bottom-right-radius: 4px;\n    background: #FFFFFF;\n}\nQSpinBox::up-button:hover, QSpinBox::down-button:hover,\nQDateEdit::up-button:hover, QDateEdit::down-button:hover {\n    background: #E4E8E5;\n}\nQSpinBox::up-button:pressed, QSpinBox::down-button:pressed,\nQDateEdit::up-button:pressed, QDateEdit::down-button:pressed {\n    background: #D6DCD8;\n}\nQSpinBox::up-arrow, QDateEdit::up-arrow {\n    image: url("/SHS/pfeil_hoch_1B2220.png");\n    width: 10px;\n    height: 10px;\n}\nQSpinBox::down-arrow, QDateEdit::down-arrow {\n    image: url("/SHS/pfeil_runter_1B2220.png");\n    width: 10px;\n    height: 10px;\n}\nQSpinBox::up-arrow:disabled, QSpinBox::up-arrow:off,\nQDateEdit::up-arrow:disabled, QDateEdit::up-arrow:off {\n    image: url("/SHS/pfeil_hoch_A3AAA6.png");\n}\nQSpinBox::down-arrow:disabled, QSpinBox::down-arrow:off,\nQDateEdit::down-arrow:disabled, QDateEdit::down-arrow:off {\n    image: url("/SHS/pfeil_runter_A3AAA6.png");\n}\nQCheckBox {\n    color: #1B2220;\n    spacing: 6px;\n}\n\n/* Tabellen (Teilnehmer, Ergebniserfassung, Auswertung, Zeitplan, Terminübersicht) */\nQTableWidget {\n    background: #FFFFFF;\n    alternate-background-color: #F6F7F5;\n    gridline-color: #C9CFCB;\n    border: 1px solid #7A837E;\n    border-radius: 4px;\n    selection-background-color: #DCE2E5;\n    selection-color: #1B2220;\n}\nQTableWidget::item {\n    padding: 4px 6px;\n}\nQTableWidget::item:selected {\n    background: #DCE2E5;\n    color: #1B2220;\n}\nQHeaderView::section {\n    background: #F6F7F5;\n    color: #4F5853;\n    padding: 6px;\n    border: none;\n    border-bottom: 1px solid #7A837E;\n    font-weight: 600;\n}\nQTableCornerButton::section {\n    background: #F6F7F5;\n    border: none;\n    border-bottom: 1px solid #7A837E;\n}\n\nQScrollBar:vertical, QScrollBar:horizontal {\n    background: #EEF0EC;\n    border: none;\n}\nQScrollBar::handle {\n    background: #B9C1BC;\n    border-radius: 5px;\n}\nQScrollBar::handle:hover {\n    background: #98A19C;\n}\n\n/* Kopfbalken mit Beagle und Termin-Angaben (desktop_gemeinsam.KopfBalken), Menüleiste im\nselben Ton, Gruppen als helle Karten und der kurze Hinweis mit Hilfe-Symbol\n(desktop_gemeinsam.kurzer_hinweis) - Marco 01.11.2026, seit 21.11.2026 in Schiefer. Rand und\nHover im Kopf sind feste Farben statt durchscheinender, damit „Hoher Kontrast“ einen\nklaren weißen Rand bekommt. */\nQMenuBar {\n    background: #2A3035;\n    color: #F1F3F2;\n}\nQMenuBar::item {\n    background: transparent;\n    color: #F1F3F2;\n    padding: 4px 10px;\n}\nQMenuBar::item:selected {\n    background: #3B434A;\n}\n#kopfBalken {\n    background: #2A3035;\n}\n#kopfBalken QLabel {\n    color: #F1F3F2;\n    background: transparent;\n}\n#kopfBalken QLabel#kopfUnterzeile {\n    color: #B9C1BC;\n}\n#kopfBalken QPushButton {\n    background: transparent;\n    color: #F1F3F2;\n    border: 1px solid #6E777C;\n    border-radius: 4px;\n    padding: 6px 12px;\n}\n#kopfBalken QPushButton:hover {\n    background: #3B434A;\n}\n#kopfBalken QPushButton:pressed {\n    background: #3B434A;\n    border-color: #B9C1BC;\n}\n/* Gesperrt (z. B. „Anderen Termin öffnen…“ während der Demo): gestrichelter Rand, damit es\nauch in „Hoher Kontrast“ (Unterzeile ebenfalls weiß) erkennbar bleibt. */\n#kopfBalken QPushButton:disabled {\n    color: #B9C1BC;\n    border: 1px dashed #6E777C;\n}\nQGroupBox {\n    background: #FFFFFF;\n    border: 1px solid #C9CFCB;\n    border-radius: 6px;\n    margin-top: 18px;\n    padding: 12px 8px 8px 8px;\n}\nQGroupBox::title {\n    subcontrol-origin: margin;\n    subcontrol-position: top left;\n    left: 12px;\n    padding: 0 4px;\n    color: #2A3035;\n}\nQLabel#kurzHinweis {\n    color: #4F5853;\n}\n\nQCheckBox::indicator, QAbstractItemView::indicator {\n    width: 14px;\n    height: 14px;\n    border: 1px solid #4F5853;\n    border-radius: 3px;\n    background: #FFFFFF;\n}\nQCheckBox::indicator:hover, QAbstractItemView::indicator:hover {\n    border-color: #2A3035;\n}\nQCheckBox::indicator:checked, QAbstractItemView::indicator:checked {\n    background: #2A3035;\n    border-color: #2A3035;\n    image: url("/SHS/haken.png");\n}\nQCheckBox::indicator:disabled, QAbstractItemView::indicator:disabled {\n    background: #F4F5F3;\n    border-color: #C9CFCB;\n}\nQCheckBox::indicator:checked:disabled, QAbstractItemView::indicator:checked:disabled {\n    background: #A3AAA6;\n    border-color: #A3AAA6;\n    image: url("/SHS/haken_1B2220.png");\n}\n'


def _relative_leuchtdichte(hexfarbe: str) -> float:
    kanaele = []
    for i in (1, 3, 5):
        c = int(hexfarbe[i:i + 2], 16) / 255
        kanaele.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = kanaele
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _kontrast(farbe1: str, farbe2: str) -> float:
    hell, dunkel = sorted((_relative_leuchtdichte(farbe1), _relative_leuchtdichte(farbe2)), reverse=True)
    return (hell + 0.05) / (dunkel + 0.05)


class _Einstellungen:
    """QSettings-Ersatz: liefert einen festen gespeicherten Wert (None = nichts gespeichert)."""
    wert = None

    def __init__(self, *_args):
        pass

    def value(self, _schluessel, vorgabe=None):
        return vorgabe if _Einstellungen.wert is None else _Einstellungen.wert


class TestDesigns(unittest.TestCase):
    def _ohne_kopfkommentar(self, qss: str) -> str:
        ende = qss.index("*/") + len("*/")
        return qss[ende:].lstrip("\n")

    def test_standard_schiefer_referenz(self):
        # Die Bildpfade (Häkchen, Pfeile) zeigen hier auf einen festen Ordner.
        with mock.patch.object(desktop_darstellung, "_haken_pfad", lambda: "/SHS/haken.png"):
            qss = desktop_darstellung._erzeuge_qss()
        self.assertEqual(self._ohne_kopfkommentar(qss), _REFERENZ_SCHIEFER)

    def test_drei_designs_schiefer_ist_standard(self):
        self.assertEqual(set(desktop_darstellung._DESIGNS.keys()), {"schiefer", "dunkel", "kontrast"})
        self.assertEqual(desktop_darstellung._DESIGN_DEFAULT, "schiefer")
        self.assertEqual(desktop_darstellung._DESIGNS["schiefer"]["anzeigename"], "Schiefer (Standard)")
        self.assertEqual(desktop_darstellung._erzeuge_qss("schiefer"), desktop_darstellung._erzeuge_qss())
        # Die Akzentfarb-Wahl gibt es nicht mehr.
        self.assertFalse(hasattr(desktop_darstellung, "_THEMES"))
        self.assertFalse(hasattr(desktop_darstellung, "_gespeichertes_theme_lesen"))

    def test_kernfarben_der_richtung(self):
        d = desktop_darstellung._DESIGNS["schiefer"]
        self.assertEqual((d["HINTERGRUND"], d["TEXT"], d["KOPF"], d["AKZENT"], d["ungespeichert_bg"]),
                         ("#EEF0EC", "#1B2220", "#2A3035", "#2A3035", "#FFD43B"))

    def test_fruehere_designs_werden_schiefer(self):
        with mock.patch.object(desktop_darstellung, "QSettings", _Einstellungen):
            for gespeichert, erwartet in (("sand", "schiefer"), ("beagle", "schiefer"), ("hell", "schiefer"),
                                          ("dunkel", "dunkel"), ("kontrast", "kontrast"), (None, "schiefer"),
                                          ("gibt-es-nicht", "schiefer"), (["x"], "schiefer")):
                with self.subTest(gespeichert=gespeichert):
                    _Einstellungen.wert = gespeichert
                    self.assertEqual(desktop_darstellung._gespeichertes_design_lesen(), erwartet)

    def test_keine_marker_uebrig(self):
        for design in desktop_darstellung._DESIGNS:
            with self.subTest(design=design):
                self.assertNotIn("@@", desktop_darstellung._erzeuge_qss(design))

    def test_unbekanntes_design_faellt_auf_standard_zurueck(self):
        self.assertEqual(desktop_darstellung._erzeuge_qss("gibt-es-nicht"), desktop_darstellung._erzeuge_qss("schiefer"))

    def test_alle_designs_haben_dieselben_schluessel(self):
        erwartet = set(desktop_darstellung._DESIGNS["schiefer"].keys())
        for name, design in desktop_darstellung._DESIGNS.items():
            with self.subTest(design=name):
                self.assertEqual(set(design.keys()), erwartet)

    def test_haken_url_in_anfuehrungszeichen_und_listen_kaestchen(self):
        # Desktop-Prüfung 14.10.2026, Teil 9 Nr. 2 und 9.
        with mock.patch.object(desktop_darstellung, "_haken_pfad", lambda: "/SHS/haken.png"):
            for design, bild in (("schiefer", "/SHS/haken.png"), ("kontrast", "/SHS/haken.png"),
                                 ("dunkel", "/SHS/haken_1A1F22.png")):
                with self.subTest(design=design):
                    self.assertTrue(desktop_darstellung._DESIGNS[design]["eigene_haken"])
                    qss = desktop_darstellung._erzeuge_qss(design)
                    # Häkchen in der Schriftfarbe auf dem Akzent (im dunklen Design dunkel).
                    self.assertIn(f'image: url("{bild}")', qss)
                    self.assertIn("QAbstractItemView::indicator", qss)
        self.assertEqual(desktop_darstellung._qss_url('a\\b"c'), 'a\\\\b\\"c')

    def test_pfeile_der_zahlenfelder_je_design(self):
        with mock.patch.object(desktop_darstellung, "_haken_pfad", lambda: "/SHS/haken.png"):
            for name, d in desktop_darstellung._DESIGNS.items():
                with self.subTest(design=name):
                    qss = desktop_darstellung._erzeuge_qss(name)
                    self.assertIn(f'url("/SHS/pfeil_hoch_{d["TEXT_BUTTON"][1:]}.png")', qss)
                    self.assertIn(f'url("/SHS/pfeil_runter_{d["TEXT_DISABLED"][1:]}.png")', qss)
                    self.assertIn("QSpinBox::up-arrow", qss)
                    # Auswahlfelder brauchen einen eigenen Pfeil, sonst sieht man nicht, dass sie aufklappen.
                    self.assertIn("QComboBox::down-arrow {\n    image: url(", qss)

    def test_designs_unterscheiden_sich_im_hintergrund(self):
        self.assertIn("#1A1F22", desktop_darstellung._erzeuge_qss("dunkel"))
        self.assertIn("#EEF0EC", desktop_darstellung._erzeuge_qss("schiefer"))
        self.assertIn("background: #FFFFFF;", desktop_darstellung._erzeuge_qss("kontrast"))

    def test_reiter_und_spaltenkoepfe_gut_lesbar(self):
        # UX-Test 02.10.2026, U14: Laien fanden Reiternamen und Spaltenköpfe zu blass.
        for name, d in desktop_darstellung._DESIGNS.items():
            with self.subTest(design=name):
                self.assertGreaterEqual(_kontrast(d["TEXT_GEDAEMPFT"], d["HINTERGRUND"]), 5.5)
                self.assertGreaterEqual(_kontrast(d["TEXT_HEADER"], d["TABELLE_ALT"]), 4.5)

    def test_textkontrast_nach_wcag(self):
        for name, d in desktop_darstellung._DESIGNS.items():
            mindestens = 7.0 if name == "kontrast" else 4.5
            with self.subTest(design=name):
                self.assertGreaterEqual(_kontrast(d["TEXT"], d["HINTERGRUND"]), mindestens)
                self.assertGreaterEqual(_kontrast(d["TEXT"], d["KARTE"]), mindestens)
                self.assertGreaterEqual(_kontrast(d["TEXT_BUTTON"], d["FLAECHE"]), 4.5)
                self.assertGreaterEqual(_kontrast(d["TEXT"], d["ungespeichert_bg"]), 4.5)

    def test_raender_der_bedienelemente_sichtbar(self):
        # Richtung „Schiefer und Signal“: Felder und Knöpfe müssen sich auch draußen bzw. bei
        # hellem Licht abheben - mindestens 3:1 (WCAG 1.4.11) zu Fläche, Grund und Karte.
        for name, d in desktop_darstellung._DESIGNS.items():
            for flaeche in ("FLAECHE", "HINTERGRUND", "KARTE", "FLAECHE_HOVER"):
                with self.subTest(design=name, flaeche=flaeche):
                    self.assertGreaterEqual(_kontrast(d["RAND"], d[flaeche]), 3.0)

    def test_akzent_fuellung_und_schrift_darauf(self):
        for name, d in desktop_darstellung._DESIGNS.items():
            for fuellung in ("AKZENT", "AKZENT_HOVER", "AKZENT_PRESSED"):
                with self.subTest(design=name, fuellung=fuellung):
                    self.assertGreaterEqual(_kontrast(d["AKZENT_TEXT"], d[fuellung]), 4.5)
            with self.subTest(design=name, farbe="Akzent zum Grund"):
                # Hauptknopf, angehakte Box und Reiter-Linie heben sich vom Grund ab.
                self.assertGreaterEqual(_kontrast(d["AKZENT"], d["HINTERGRUND"]), 3.0)

    def test_gesperrter_haken_erkennbar(self):
        # Marco 21.11.2026 (Verifikation): eine gesperrte, angehakte Box zeigt ihr Häkchen in
        # HAKEN_AUS auf TEXT_DISABLED - vorher im dunklen Design nur 2,9:1.
        with mock.patch.object(desktop_darstellung, "_haken_pfad", lambda: "/SHS/haken.png"):
            for name, d in desktop_darstellung._DESIGNS.items():
                with self.subTest(design=name):
                    self.assertGreaterEqual(_kontrast(d["HAKEN_AUS"], d["TEXT_DISABLED"]), 4.5)
                    qss = desktop_darstellung._erzeuge_qss(name)
                    block = qss.split("QAbstractItemView::indicator:checked:disabled {", 1)[1].split("}", 1)[0]
                    self.assertIn(f'image: url("{desktop_darstellung._haken_pfad_fuer(d["HAKEN_AUS"])}")', block)

    def test_link_und_fokus_sichtbar(self):
        # LINK ist auch der Fokusrahmen von Eingabefeldern und Punktezellen.
        for name, d in desktop_darstellung._DESIGNS.items():
            for flaeche in ("HINTERGRUND", "KARTE", "FLAECHE", "ungespeichert_bg"):
                with self.subTest(design=name, flaeche=flaeche):
                    self.assertGreaterEqual(_kontrast(d["LINK"], d[flaeche]), 3.0)

    def test_auswahl_lesbar(self):
        for name, d in desktop_darstellung._DESIGNS.items():
            with self.subTest(design=name):
                self.assertGreaterEqual(_kontrast(d["TEXT"], d["AUSWAHL"]), 4.5)

    def test_semantische_farben_lesbar(self):
        for name, d in desktop_darstellung._DESIGNS.items():
            for farbe in ("ok", "warnung", "fehler", "gedaempft"):
                with self.subTest(design=name, farbe=farbe):
                    self.assertGreaterEqual(_kontrast(d[farbe], d["zeile_bg"]), 3.0)
            with self.subTest(design=name, farbe="warnung auf ungespeichert"):
                self.assertGreaterEqual(_kontrast(d["warnung"], d["ungespeichert_bg"]), 3.0)

    def test_kopf_und_gruppentitel_lesbar(self):
        for name, d in desktop_darstellung._DESIGNS.items():
            with self.subTest(design=name):
                self.assertGreaterEqual(_kontrast(d["KOPF_TEXT"], d["KOPF"]), 4.5)
                self.assertGreaterEqual(_kontrast(d["KOPF_TEXT2"], d["KOPF"]), 4.5)
                self.assertGreaterEqual(_kontrast(d["KOPF_TEXT"], d["KOPF_HOVER"]), 4.5)
                self.assertGreaterEqual(_kontrast(d["GRUPPE_TITEL"], d["HINTERGRUND"]), 4.5)
                self.assertGreaterEqual(_kontrast(d["GRUPPE_TITEL"], d["KARTE"]), 4.5)

    def test_hoher_kontrast_ohne_zwischentoene_im_kopf(self):
        d = desktop_darstellung._DESIGNS["kontrast"]
        self.assertEqual((d["KOPF"], d["KOPF_TEXT"], d["KOPF_RAND"]), ("#000000", "#FFFFFF", "#FFFFFF"))
        for name in desktop_darstellung._DESIGNS:
            with self.subTest(design=name):
                self.assertNotIn("rgba(", desktop_darstellung._erzeuge_qss(name))

    def test_kopf_regeln_im_stylesheet(self):
        qss = desktop_darstellung._erzeuge_qss()
        for selektor in ("QMenuBar {", "#kopfBalken {", "#kopfBalken QLabel#kopfUnterzeile",
                         "QGroupBox::title", "QLabel#kurzHinweis"):
            self.assertIn(selektor, qss)
        self.assertIn("background: #2A3035;", qss)  # Kopf in Schiefer
        # Trennlinien in Tabellen ruhiger als die Ränder der Bedienelemente.
        self.assertIn("gridline-color: #C9CFCB;", qss)


if __name__ == "__main__":
    unittest.main()
