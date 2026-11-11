"""Reine String-Logik-Tests fuer die Theme-Erzeugung in desktop_darstellung.py - kein
Qt-Import noetig ausser dem, den desktop_darstellung.py selbst am Kopf schon mitbringt
(PySide6). Laeuft daher nur lokal, wenn PySide6 installiert ist - genau wie
die test_gui_*.py."""

import unittest
from unittest import mock

import desktop_darstellung


class TestThemes(unittest.TestCase):
    def _ohne_kopfkommentar(self, qss: str) -> str:
        ende = qss.index("*/") + len("*/")
        return qss[ende:].lstrip("\n")

    def test_standard_lohbraun_beagle_referenz(self):
        # Erscheinungsbild „Beagle“ (Marco 01.11.2026): Standard ist Lohbraun auf Beagle. Die
        # Bildpfade (Häkchen, Pfeile) zeigen hier auf einen festen Ordner.
        erwartet = 'QMainWindow, QDialog {\n    background: #FBF8F3;\n}\nQWidget {\n    color: #2B2620;\n}\nQLabel {\n    color: #2B2620;\n}\n\n/* Reiter (Teilnehmer/Zeitplan/.../Datensicherung) */\nQTabWidget::pane {\n    border: 1px solid #E2D9CB;\n    background: #FBF8F3;\n    top: -1px;\n}\n/* Reiter durchsichtig: sonst übermalen sie die obere Rahmenlinie des Inhaltsbereichs\n(top: -1px), und die Linie erscheint nur in den Lücken (Marco, 16.10.2026). */\nQTabBar::tab {\n    background: transparent;\n    color: #5E5549;\n    padding: 8px 16px;\n    border: none;\n    border-bottom: 3px solid transparent;\n    margin-right: 2px;\n    font-weight: 600;\n}\nQTabBar::tab:selected {\n    color: #1F1A15;\n    font-weight: 600;\n    border-bottom: 3px solid #8C5A32;\n}\nQTabBar::tab:hover:!selected {\n    color: #1F1A15;\n}\n\n/* Schaltflächen: neutral/sekundär als Standard; die jeweilige Haupt-Aktion eines\nReiters/Dialogs trägt objectName "primaerButton" (siehe z.B. TeilnehmerTab) und wird\nin der Akzentfarbe hervorgehoben - ebenso automatisch jeder Dialog-Default-Button (die "OK"-Schaltfläche\neiner QDialogButtonBox, über die Qt-eigene :default-Pseudoklasse, ohne dass jeder\nDialog einzeln angepasst werden muss). */\nQPushButton {\n    background: #F2ECE2;\n    color: #3A3229;\n    border: 1px solid #E2D9CB;\n    border-radius: 6px;\n    padding: 6px 14px;\n}\nQPushButton:hover {\n    background: #EAE2D5;\n}\nQPushButton:pressed {\n    background: #E1D7C7;\n}\nQPushButton:disabled {\n    color: #B3A898;\n    background: #F6F2EB;\n    border-color: #ECE6DB;\n}\nQPushButton#primaerButton, QPushButton:default:enabled {\n    background: #8C5A32;\n    color: #FFFFFF;\n    border: 1px solid #8C5A32;\n    font-weight: 600;\n}\nQPushButton#primaerButton:hover, QPushButton:default:enabled:hover {\n    background: #7A4E2B;\n    border-color: #7A4E2B;\n}\nQPushButton#primaerButton:pressed, QPushButton:default:enabled:pressed {\n    background: #6A4325;\n    border-color: #6A4325;\n}\n\n/* Eingabefelder */\nQLineEdit, QComboBox, QSpinBox, QDateEdit {\n    background: #F2ECE2;\n    border: 1px solid #E2D9CB;\n    border-radius: 6px;\n    padding: 4px 8px;\n    color: #2B2620;\n}\nQLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {\n    border: 1px solid #8C5A32;\n    background: #FBF8F3;\n}\nQLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {\n    color: #B3A898;\n    background: #F6F2EB;\n}\nQComboBox::drop-down {\n    border: none;\n    width: 20px;\n}\n/* Pfeilknöpfe der Zahlenfelder (Marco 01.11.2026, Erscheinungsbild „Beagle“): Sobald das\nFeld selbst einen Rahmen aus dem Stylesheet hat, zeichnet Qt die Knöpfe nur noch als flache\nKästchen ohne Pfeil. Deshalb eigene Knöpfe und Pfeile als Bild (_pfeile_bereitstellen()). */\nQSpinBox, QDateEdit {\n    padding-right: 22px;\n}\nQSpinBox::up-button, QDateEdit::up-button {\n    subcontrol-origin: border;\n    subcontrol-position: top right;\n    width: 20px;\n    border: none;\n    border-left: 1px solid #E2D9CB;\n    border-top-right-radius: 6px;\n    background: #F2ECE2;\n}\nQSpinBox::down-button, QDateEdit::down-button {\n    subcontrol-origin: border;\n    subcontrol-position: bottom right;\n    width: 20px;\n    border: none;\n    border-left: 1px solid #E2D9CB;\n    border-bottom-right-radius: 6px;\n    background: #F2ECE2;\n}\nQSpinBox::up-button:hover, QSpinBox::down-button:hover,\nQDateEdit::up-button:hover, QDateEdit::down-button:hover {\n    background: #EAE2D5;\n}\nQSpinBox::up-button:pressed, QSpinBox::down-button:pressed,\nQDateEdit::up-button:pressed, QDateEdit::down-button:pressed {\n    background: #E1D7C7;\n}\nQSpinBox::up-arrow, QDateEdit::up-arrow {\n    image: url("/SHS/pfeil_hoch_3A3229.png");\n    width: 10px;\n    height: 10px;\n}\nQSpinBox::down-arrow, QDateEdit::down-arrow {\n    image: url("/SHS/pfeil_runter_3A3229.png");\n    width: 10px;\n    height: 10px;\n}\nQSpinBox::up-arrow:disabled, QSpinBox::up-arrow:off,\nQDateEdit::up-arrow:disabled, QDateEdit::up-arrow:off {\n    image: url("/SHS/pfeil_hoch_B3A898.png");\n}\nQSpinBox::down-arrow:disabled, QSpinBox::down-arrow:off,\nQDateEdit::down-arrow:disabled, QDateEdit::down-arrow:off {\n    image: url("/SHS/pfeil_runter_B3A898.png");\n}\nQCheckBox {\n    color: #2B2620;\n    spacing: 6px;\n}\n\n/* Tabellen (Teilnehmer, Ergebniserfassung, Auswertung, Zeitplan, Terminübersicht) */\nQTableWidget {\n    background: #FBF8F3;\n    alternate-background-color: #FCFAF6;\n    gridline-color: #E2D9CB;\n    border: 1px solid #E2D9CB;\n    border-radius: 6px;\n    selection-background-color: #F3E7D9;\n    selection-color: #2B2620;\n}\nQTableWidget::item {\n    padding: 4px 6px;\n}\nQTableWidget::item:selected {\n    background: #F3E7D9;\n    color: #2B2620;\n}\nQHeaderView::section {\n    background: #FCFAF6;\n    color: #5E5549;\n    padding: 6px;\n    border: none;\n    border-bottom: 1px solid #E2D9CB;\n    font-weight: 600;\n}\nQTableCornerButton::section {\n    background: #FCFAF6;\n    border: none;\n    border-bottom: 1px solid #E2D9CB;\n}\n\nQScrollBar:vertical, QScrollBar:horizontal {\n    background: #FBF8F3;\n    border: none;\n}\nQScrollBar::handle {\n    background: #DCD2C3;\n    border-radius: 5px;\n}\nQScrollBar::handle:hover {\n    background: #C9BCA8;\n}\n\n/* Kopfbalken mit Beagle und Termin-Angaben (desktop_gemeinsam.KopfBalken), Menüleiste im\nselben Ton, Gruppen als helle Karten und der kurze Hinweis mit Hilfe-Symbol\n(desktop_gemeinsam.kurzer_hinweis) - Marco 01.11.2026, Erscheinungsbild „Beagle“. Rand und\nHover im Kopf sind feste Farben statt durchscheinender, damit „Hoher Kontrast“ einen\nklaren weißen Rand bekommt. */\nQMenuBar {\n    background: #2F2B27;\n    color: #F4EEE4;\n}\nQMenuBar::item {\n    background: transparent;\n    color: #F4EEE4;\n    padding: 4px 10px;\n}\nQMenuBar::item:selected {\n    background: #4B4641;\n}\n#kopfBalken {\n    background: #2F2B27;\n}\n#kopfBalken QLabel {\n    color: #F4EEE4;\n    background: transparent;\n}\n#kopfBalken QLabel#kopfUnterzeile {\n    color: #CDBFA9;\n}\n#kopfBalken QPushButton {\n    background: transparent;\n    color: #F4EEE4;\n    border: 1px solid #6A6560;\n    border-radius: 6px;\n    padding: 6px 12px;\n}\n#kopfBalken QPushButton:hover {\n    background: #4B4641;\n}\n#kopfBalken QPushButton:pressed {\n    background: #4B4641;\n    border-color: #CDBFA9;\n}\n/* Gesperrt (z. B. „Anderen Termin öffnen…“ während der Demo): gestrichelter Rand, damit es\nauch in „Hoher Kontrast“ (Unterzeile ebenfalls weiß) erkennbar bleibt. */\n#kopfBalken QPushButton:disabled {\n    color: #CDBFA9;\n    border: 1px dashed #6A6560;\n}\nQGroupBox {\n    background: #FFFDF9;\n    border: 1px solid #E2D9CB;\n    border-radius: 8px;\n    margin-top: 18px;\n    padding: 12px 8px 8px 8px;\n}\nQGroupBox::title {\n    subcontrol-origin: margin;\n    subcontrol-position: top left;\n    left: 12px;\n    padding: 0 4px;\n    color: #6A4325;\n}\nQLabel#kurzHinweis {\n    color: #5E5549;\n}\n\nQCheckBox::indicator, QAbstractItemView::indicator {\n    width: 14px;\n    height: 14px;\n    border: 1px solid #5E5549;\n    border-radius: 3px;\n    background: #F2ECE2;\n}\nQCheckBox::indicator:hover, QAbstractItemView::indicator:hover {\n    border-color: #8C5A32;\n}\nQCheckBox::indicator:checked, QAbstractItemView::indicator:checked {\n    background: #8C5A32;\n    border-color: #8C5A32;\n    image: url("/SHS/haken.png");\n}\nQCheckBox::indicator:disabled, QAbstractItemView::indicator:disabled {\n    background: #F6F2EB;\n    border-color: #ECE6DB;\n}\nQCheckBox::indicator:checked:disabled, QAbstractItemView::indicator:checked:disabled {\n    background: #B3A898;\n    border-color: #B3A898;\n}\n'
        with mock.patch.object(desktop_darstellung, "_haken_pfad", lambda: "/SHS/haken.png"):
            qss = desktop_darstellung._erzeuge_qss(desktop_darstellung._THEME_DEFAULT)
        self.assertEqual(self._ohne_kopfkommentar(qss), erwartet)

    def test_blau_behaelt_seine_farben(self):
        qss = desktop_darstellung._erzeuge_qss("blau", "hell")
        for farbe in ("#2F6FED", "#2A63D6", "#2558BF", "#EAF1FF", "#FFFFFF", "#1B2430"):
            self.assertIn(farbe, qss)

    def test_keine_marker_uebrig(self):
        for schluessel in desktop_darstellung._THEMES:
            qss = desktop_darstellung._erzeuge_qss(schluessel)
            self.assertNotIn("@@", qss)

    def test_unbekanntes_theme_faellt_auf_default_zurueck(self):
        self.assertEqual(desktop_darstellung._erzeuge_qss("nicht-vorhanden"), desktop_darstellung._erzeuge_qss(desktop_darstellung._THEME_DEFAULT))

    def test_vier_themes_lohbraun_ist_standard(self):
        self.assertEqual(set(desktop_darstellung._THEMES.keys()), {"lohbraun", "blau", "gruen", "violett"})
        self.assertEqual(desktop_darstellung._THEME_DEFAULT, "lohbraun")
        self.assertEqual(desktop_darstellung._THEMES["lohbraun"]["anzeigename"], "Lohbraun (Standard)")
        self.assertEqual(desktop_darstellung._THEMES["blau"]["anzeigename"], "Blau")

    def test_weisse_schrift_auf_lohbraun_lesbar(self):
        # Nur das neue Theme - die älteren Akzente (z. B. Grün) bleiben unverändert.
        theme = desktop_darstellung._THEMES["lohbraun"]
        for schluessel in ("akzent", "akzent_hover", "akzent_pressed"):
            with self.subTest(farbe=schluessel):
                self.assertGreaterEqual(_kontrast("#FFFFFF", theme[schluessel]), 4.5)


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


class TestDesigns(unittest.TestCase):
    def test_vier_designs_vorhanden(self):
        # Marco 01.11.2026: „Beagle“ ersetzt „Warm / Sand“.
        self.assertEqual(set(desktop_darstellung._DESIGNS.keys()), {"beagle", "hell", "dunkel", "kontrast"})

    def test_beagle_ist_standard(self):
        self.assertEqual(desktop_darstellung._DESIGN_DEFAULT, "beagle")
        self.assertEqual(desktop_darstellung._DESIGNS["beagle"]["anzeigename"], "Beagle (Standard)")
        self.assertEqual(desktop_darstellung._DESIGNS["hell"]["anzeigename"], "Hell")
        for theme in desktop_darstellung._THEMES:
            self.assertEqual(desktop_darstellung._erzeuge_qss(theme, "beagle"), desktop_darstellung._erzeuge_qss(theme))

    def test_gespeichertes_sand_wird_beagle(self):
        class _Einstellungen:
            wert = None

            def __init__(self, *_args):
                pass

            def value(self, _schluessel, vorgabe=None):
                return vorgabe if _Einstellungen.wert is None else _Einstellungen.wert

        with mock.patch.object(desktop_darstellung, "QSettings", _Einstellungen):
            for gespeichert, erwartet in (("sand", "beagle"), ("hell", "hell"), ("dunkel", "dunkel"),
                                          (None, "beagle"), ("gibt-es-nicht", "beagle"), (["x"], "beagle")):
                with self.subTest(gespeichert=gespeichert):
                    _Einstellungen.wert = gespeichert
                    self.assertEqual(desktop_darstellung._gespeichertes_design_lesen(), erwartet)
            # Akzentfarben: eine frühere Wahl bleibt, ohne Wahl gilt Lohbraun.
            for gespeichert, erwartet in (("blau", "blau"), (None, "lohbraun"), ("rot", "lohbraun"), (["x"], "lohbraun")):
                with self.subTest(theme=gespeichert):
                    _Einstellungen.wert = gespeichert
                    self.assertEqual(desktop_darstellung._gespeichertes_theme_lesen(), erwartet)

    def test_keine_marker_uebrig_in_allen_kombinationen(self):
        for theme in desktop_darstellung._THEMES:
            for design in desktop_darstellung._DESIGNS:
                with self.subTest(theme=theme, design=design):
                    self.assertNotIn("@@", desktop_darstellung._erzeuge_qss(theme, design))

    def test_haken_url_in_anfuehrungszeichen_und_listen_kaestchen(self):
        # Desktop-Prüfung 14.10.2026, Teil 9 Nr. 2 und 9.
        for design in ("beagle", "dunkel", "kontrast"):
            with self.subTest(design=design):
                self.assertTrue(desktop_darstellung._DESIGNS[design]["eigene_haken"])
                qss = desktop_darstellung._erzeuge_qss("blau", design)
                self.assertIn('image: url("', qss)
                self.assertIn("QAbstractItemView::indicator", qss)
        # "hell" behält den nativen Haken (Marco 01.11.2026: Schalter eigene_haken).
        self.assertFalse(desktop_darstellung._DESIGNS["hell"]["eigene_haken"])
        self.assertNotIn("QAbstractItemView::indicator", desktop_darstellung._erzeuge_qss("blau", "hell"))
        self.assertEqual(desktop_darstellung._qss_url('a\\b"c'), 'a\\\\b\\"c')

    def test_pfeile_der_zahlenfelder_je_design(self):
        with mock.patch.object(desktop_darstellung, "_haken_pfad", lambda: "/SHS/haken.png"):
            for name, d in desktop_darstellung._DESIGNS.items():
                with self.subTest(design=name):
                    qss = desktop_darstellung._erzeuge_qss("lohbraun", name)
                    self.assertIn(f'url("/SHS/pfeil_hoch_{d["TEXT_BUTTON"][1:]}.png")', qss)
                    self.assertIn(f'url("/SHS/pfeil_runter_{d["TEXT_DISABLED"][1:]}.png")', qss)
                    self.assertIn("QSpinBox::up-arrow", qss)

    def test_alle_designs_haben_dieselben_schluessel(self):
        erwartet = set(desktop_darstellung._DESIGNS["hell"].keys())
        for name, design in desktop_darstellung._DESIGNS.items():
            with self.subTest(design=name):
                self.assertEqual(set(design.keys()), erwartet)

    def test_unbekanntes_design_faellt_auf_standard_zurueck(self):
        self.assertEqual(desktop_darstellung._erzeuge_qss("blau", "gibt-es-nicht"), desktop_darstellung._erzeuge_qss("blau", "beagle"))

    def test_designs_unterscheiden_sich_im_hintergrund(self):
        self.assertIn("#1E2228", desktop_darstellung._erzeuge_qss("blau", "dunkel"))
        self.assertIn("#FBF8F3", desktop_darstellung._erzeuge_qss("blau", "beagle"))
        self.assertIn("#FFFFFF", desktop_darstellung._erzeuge_qss("blau", "hell"))

    def test_dunkles_design_mischt_auswahlfarbe(self):
        qss = desktop_darstellung._erzeuge_qss("blau", "dunkel")
        self.assertNotIn(desktop_darstellung._THEMES["blau"]["akzent_hell"], qss)
        self.assertIn(desktop_darstellung._mische("#2F6FED", "#1E2228", desktop_darstellung._AUSWAHL_MISCHANTEIL_DUNKEL), qss)

    def test_mische(self):
        self.assertEqual(desktop_darstellung._mische("#FFFFFF", "#000000", 1.0), "#FFFFFF")
        self.assertEqual(desktop_darstellung._mische("#FFFFFF", "#000000", 0.0), "#000000")
        self.assertEqual(desktop_darstellung._mische("#FF0000", "#0000FF", 0.5), "#800080")

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
                self.assertGreaterEqual(_kontrast(d["TEXT_BUTTON"], d["FLAECHE"]), 4.5)
                self.assertGreaterEqual(_kontrast(d["TEXT"], d["ungespeichert_bg"]), 4.5)

    def test_semantische_farben_lesbar(self):
        for name, d in desktop_darstellung._DESIGNS.items():
            for farbe in ("ok", "warnung", "fehler", "gedaempft"):
                with self.subTest(design=name, farbe=farbe):
                    self.assertGreaterEqual(_kontrast(d[farbe], d["zeile_bg"]), 3.0)
            with self.subTest(design=name, farbe="warnung auf ungespeichert"):
                self.assertGreaterEqual(_kontrast(d["warnung"], d["ungespeichert_bg"]), 3.0)

    def test_kopf_und_gruppentitel_lesbar(self):
        # Erscheinungsbild „Beagle“ (Marco 01.11.2026): Kopfbalken, Unterzeile, Gruppentitel.
        for name, d in desktop_darstellung._DESIGNS.items():
            with self.subTest(design=name):
                self.assertGreaterEqual(_kontrast(d["KOPF_TEXT"], d["KOPF"]), 4.5)
                self.assertGreaterEqual(_kontrast(d["KOPF_TEXT2"], d["KOPF"]), 4.5)
                self.assertGreaterEqual(_kontrast(d["KOPF_TEXT"], d["KOPF_HOVER"]), 4.5)
                self.assertGreaterEqual(_kontrast(d["GRUPPE_TITEL"], d["HINTERGRUND"]), 4.5)
                self.assertGreaterEqual(_kontrast(d["TEXT"], d["KARTE"]), 4.5)

    def test_hoher_kontrast_ohne_zwischentoene_im_kopf(self):
        d = desktop_darstellung._DESIGNS["kontrast"]
        self.assertEqual((d["KOPF"], d["KOPF_TEXT"], d["KOPF_RAND"]), ("#000000", "#FFFFFF", "#FFFFFF"))
        for name in desktop_darstellung._DESIGNS:
            with self.subTest(design=name):
                self.assertNotIn("rgba(", desktop_darstellung._erzeuge_qss("lohbraun", name))

    def test_kopf_regeln_im_stylesheet(self):
        qss = desktop_darstellung._erzeuge_qss("lohbraun")
        for selektor in ("QMenuBar {", "#kopfBalken {", "#kopfBalken QLabel#kopfUnterzeile",
                         "QGroupBox::title", "QLabel#kurzHinweis"):
            self.assertIn(selektor, qss)
        self.assertIn("background: #2F2B27;", qss)  # Kopf in Anthrazit
        self.assertIn("color: #6A4325;", qss)  # Gruppentitel lohbraun

    def test_auswahl_lesbar_in_allen_kombinationen(self):
        for theme_name, theme in desktop_darstellung._THEMES.items():
            for name, d in desktop_darstellung._DESIGNS.items():
                with self.subTest(theme=theme_name, design=name):
                    self.assertGreaterEqual(_kontrast(d["TEXT"], desktop_darstellung._auswahlfarbe(theme, d)), 4.5)


if __name__ == "__main__":
    unittest.main()
