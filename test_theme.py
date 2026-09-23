"""Reine String-Logik-Tests fuer die Theme-Erzeugung in app.py - kein Qt-Import
noetig ausser dem, den app.py selbst am Kopf schon mitbringt (PySide6). Laeuft daher
nur lokal, wenn PySide6 installiert ist - genau wie test_app_gui.py."""

import unittest

import app


class TestThemes(unittest.TestCase):
    def _ohne_kopfkommentar(self, qss: str) -> str:
        ende = qss.index("*/") + len("*/")
        return qss[ende:].lstrip("\n")

    def test_blau_ist_regressionsfrei_zum_bisherigen_aussehen(self):
        erwartet = 'QMainWindow, QDialog {\n    background: #FFFFFF;\n}\nQWidget {\n    color: #1B2430;\n}\nQLabel {\n    color: #1B2430;\n}\n\n/* Reiter (Teilnehmer/Zeitplan/.../Datensicherung sowie der Hilfe-Dialog) */\nQTabWidget::pane {\n    border: 1px solid #E4E8EE;\n    background: #FFFFFF;\n    top: -1px;\n}\nQTabBar::tab {\n    background: #FFFFFF;\n    color: #6B7686;\n    padding: 8px 16px;\n    border: none;\n    border-bottom: 2px solid transparent;\n    margin-right: 2px;\n}\nQTabBar::tab:selected {\n    color: #16233E;\n    font-weight: 600;\n    border-bottom: 2px solid #2F6FED;\n}\nQTabBar::tab:hover:!selected {\n    color: #16233E;\n}\n\n/* Schaltflächen: neutral/sekundär als Standard; die jeweilige Haupt-Aktion eines\nReiters/Dialogs trägt objectName "primaerButton" (siehe z.B. TeilnehmerTab) und wird\nblau hervorgehoben - ebenso automatisch jeder Dialog-Default-Button (die "OK"-Schaltfläche\neiner QDialogButtonBox, über die Qt-eigene :default-Pseudoklasse, ohne dass jeder\nDialog einzeln angepasst werden muss). */\nQPushButton {\n    background: #F1F4F8;\n    color: #2A3342;\n    border: 1px solid #E4E8EE;\n    border-radius: 6px;\n    padding: 6px 14px;\n}\nQPushButton:hover {\n    background: #E7ECF3;\n}\nQPushButton:pressed {\n    background: #DCE3EC;\n}\nQPushButton:disabled {\n    color: #A7B0BD;\n    background: #F6F8FA;\n    border-color: #EDF0F4;\n}\nQPushButton#primaerButton, QPushButton:default:enabled {\n    background: #2F6FED;\n    color: #FFFFFF;\n    border: 1px solid #2F6FED;\n    font-weight: 600;\n}\nQPushButton#primaerButton:hover, QPushButton:default:enabled:hover {\n    background: #2A63D6;\n    border-color: #2A63D6;\n}\nQPushButton#primaerButton:pressed, QPushButton:default:enabled:pressed {\n    background: #2558BF;\n    border-color: #2558BF;\n}\n\n/* Eingabefelder */\nQLineEdit, QComboBox, QSpinBox, QDateEdit {\n    background: #F1F4F8;\n    border: 1px solid #E4E8EE;\n    border-radius: 6px;\n    padding: 4px 8px;\n    color: #1B2430;\n}\nQLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {\n    border: 1px solid #2F6FED;\n    background: #FFFFFF;\n}\nQLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {\n    color: #A7B0BD;\n    background: #F6F8FA;\n}\nQComboBox::drop-down {\n    border: none;\n    width: 20px;\n}\nQCheckBox {\n    color: #1B2430;\n    spacing: 6px;\n}\n\n/* Tabellen (Teilnehmer, Ergebniserfassung, Auswertung, Zeitplan, Terminübersicht) */\nQTableWidget {\n    background: #FFFFFF;\n    alternate-background-color: #FBFCFD;\n    gridline-color: #E4E8EE;\n    border: 1px solid #E4E8EE;\n    border-radius: 6px;\n    selection-background-color: #EAF1FF;\n    selection-color: #1B2430;\n}\nQTableWidget::item {\n    padding: 4px 6px;\n}\nQTableWidget::item:selected {\n    background: #EAF1FF;\n    color: #1B2430;\n}\nQHeaderView::section {\n    background: #FBFCFD;\n    color: #8A94A6;\n    padding: 6px;\n    border: none;\n    border-bottom: 1px solid #E4E8EE;\n    font-weight: 600;\n}\nQTableCornerButton::section {\n    background: #FBFCFD;\n    border: none;\n    border-bottom: 1px solid #E4E8EE;\n}\n\nQScrollBar:vertical, QScrollBar:horizontal {\n    background: #FFFFFF;\n    border: none;\n}\nQScrollBar::handle {\n    background: #D8DEE7;\n    border-radius: 5px;\n}\nQScrollBar::handle:hover {\n    background: #C3CBD8;\n}\n'
        self.assertEqual(self._ohne_kopfkommentar(app._erzeuge_qss("blau")), erwartet)

    def test_keine_marker_uebrig(self):
        for schluessel in app._THEMES:
            qss = app._erzeuge_qss(schluessel)
            self.assertNotIn("@@", qss)

    def test_unbekanntes_theme_faellt_auf_default_zurueck(self):
        self.assertEqual(app._erzeuge_qss("nicht-vorhanden"), app._erzeuge_qss(app._THEME_DEFAULT))

    def test_drei_themes_vorhanden(self):
        self.assertEqual(set(app._THEMES.keys()), {"blau", "gruen", "violett"})


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
        self.assertEqual(set(app._DESIGNS.keys()), {"hell", "sand", "dunkel", "kontrast"})

    def test_hell_ist_standard_und_identisch_zum_bisherigen(self):
        self.assertEqual(app._DESIGN_DEFAULT, "hell")
        for theme in app._THEMES:
            self.assertEqual(app._erzeuge_qss(theme, "hell"), app._erzeuge_qss(theme))

    def test_keine_marker_uebrig_in_allen_kombinationen(self):
        for theme in app._THEMES:
            for design in app._DESIGNS:
                with self.subTest(theme=theme, design=design):
                    self.assertNotIn("@@", app._erzeuge_qss(theme, design))

    def test_alle_designs_haben_dieselben_schluessel(self):
        erwartet = set(app._DESIGNS["hell"].keys())
        for name, design in app._DESIGNS.items():
            with self.subTest(design=name):
                self.assertEqual(set(design.keys()), erwartet)

    def test_unbekanntes_design_faellt_auf_hell_zurueck(self):
        self.assertEqual(app._erzeuge_qss("blau", "gibt-es-nicht"), app._erzeuge_qss("blau", "hell"))

    def test_designs_unterscheiden_sich_im_hintergrund(self):
        self.assertIn("#1E2228", app._erzeuge_qss("blau", "dunkel"))
        self.assertIn("#FBF8F3", app._erzeuge_qss("blau", "sand"))

    def test_dunkles_design_mischt_auswahlfarbe(self):
        qss = app._erzeuge_qss("blau", "dunkel")
        self.assertNotIn(app._THEMES["blau"]["akzent_hell"], qss)
        self.assertIn(app._mische("#2F6FED", "#1E2228", app._AUSWAHL_MISCHANTEIL_DUNKEL), qss)

    def test_mische(self):
        self.assertEqual(app._mische("#FFFFFF", "#000000", 1.0), "#FFFFFF")
        self.assertEqual(app._mische("#FFFFFF", "#000000", 0.0), "#000000")
        self.assertEqual(app._mische("#FF0000", "#0000FF", 0.5), "#800080")

    def test_textkontrast_nach_wcag(self):
        for name, d in app._DESIGNS.items():
            mindestens = 7.0 if name == "kontrast" else 4.5
            with self.subTest(design=name):
                self.assertGreaterEqual(_kontrast(d["TEXT"], d["HINTERGRUND"]), mindestens)
                self.assertGreaterEqual(_kontrast(d["TEXT_BUTTON"], d["FLAECHE"]), 4.5)
                self.assertGreaterEqual(_kontrast(d["TEXT"], d["ungespeichert_bg"]), 4.5)

    def test_semantische_farben_lesbar(self):
        for name, d in app._DESIGNS.items():
            for farbe in ("ok", "warnung", "fehler", "gedaempft"):
                with self.subTest(design=name, farbe=farbe):
                    self.assertGreaterEqual(_kontrast(d[farbe], d["zeile_bg"]), 3.0)
            with self.subTest(design=name, farbe="warnung auf ungespeichert"):
                self.assertGreaterEqual(_kontrast(d["warnung"], d["ungespeichert_bg"]), 3.0)

    def test_auswahl_lesbar_in_allen_kombinationen(self):
        for theme_name, theme in app._THEMES.items():
            for name, d in app._DESIGNS.items():
                with self.subTest(theme=theme_name, design=name):
                    self.assertGreaterEqual(_kontrast(d["TEXT"], app._auswahlfarbe(theme, d)), 4.5)


if __name__ == "__main__":
    unittest.main()
