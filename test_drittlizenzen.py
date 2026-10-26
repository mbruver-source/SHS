"""Tests für tools/drittlizenzen.py (THIRD_PARTY_LICENSES.txt, Marco 25.10.2026).

Statt echter Pakete liegen nachgebaute dist-info-Ordner in einem Temp-Ordner; die Suche
metadata.distribution() wird darauf umgelenkt. So hängen die Tests nicht davon ab, welche
Pakete in der Testumgebung installiert sind.
"""
import importlib.util
import tempfile
import unittest
from importlib import metadata
from pathlib import Path
from unittest import mock

_PFAD = Path(__file__).resolve().parent / "tools" / "drittlizenzen.py"
_SPEC = importlib.util.spec_from_file_location("drittlizenzen", _PFAD)
drittlizenzen = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(drittlizenzen)
Requirement = drittlizenzen.Requirement

MIT = "MIT License\n\nCopyright (c) Beispiel\n"


class TestDrittlizenzen(unittest.TestCase):
    def setUp(self):
        self._ordner = tempfile.TemporaryDirectory()
        self.ordner = Path(self._ordner.name)
        self.pakete = {}
        umlenkung = mock.patch.object(drittlizenzen.metadata, "distribution", self._distribution)
        umlenkung.start()
        self.addCleanup(umlenkung.stop)
        # Pythons LICENSE.txt fehlt z. B. beim System-Python von Debian/Ubuntu.
        python_lizenz = mock.patch.object(drittlizenzen, "_python_lizenz",
                                          return_value="PSF-Lizenz (Attrappe)\n")
        python_lizenz.start()
        self.addCleanup(python_lizenz.stop)
        self.addCleanup(self._ordner.cleanup)

    def _distribution(self, name):
        try:
            return self.pakete[drittlizenzen._norm(name)]
        except KeyError:
            raise metadata.PackageNotFoundError(name) from None

    def paket(self, name, requires=(), lizenzen=None, kopf=""):
        """Legt <name>-1.0.dist-info mit METADATA, RECORD und Lizenzdateien an."""
        info = self.ordner / f"{name}-1.0.dist-info"
        info.mkdir()
        zeilen = ["Metadata-Version: 2.1", f"Name: {name}", "Version: 1.0"]
        zeilen += [f"Requires-Dist: {angabe}" for angabe in requires]
        (info / "METADATA").write_text("\n".join(zeilen) + "\n" + kopf, encoding="utf-8")
        record = [f"{info.name}/METADATA,,"]
        for dateiname, text in (lizenzen or {}).items():
            (info / dateiname).write_text(text, encoding="utf-8")
            record.append(f"{info.name}/{dateiname},,")
        (info / "RECORD").write_text("\n".join(record) + "\n", encoding="utf-8")
        self.pakete[drittlizenzen._norm(name)] = metadata.PathDistribution(info)

    def erzeugen(self, *zeilen):
        with mock.patch.object(drittlizenzen, "_wurzeln",
                               return_value=[Requirement(z) for z in zeilen]):
            return drittlizenzen.erzeugen("web")

    def test_abhaengigkeiten_marker_und_extras(self):
        self.paket("haupt", requires=[
            "basis",
            'nur-mit-extra; extra == "zusatz"',
            'nie-hier; sys_platform == "keine-plattform"',
        ], lizenzen={"LICENSE": MIT})
        self.paket("basis", lizenzen={"LICENSE.txt": "BSD Basis\n"})
        self.paket("nur-mit-extra", lizenzen={"LICENSE": "Extra-Lizenz\n"})

        ohne = drittlizenzen._pakete([Requirement("haupt")])
        self.assertEqual(set(ohne), {"haupt", "basis"})
        mit = drittlizenzen._pakete([Requirement("haupt[zusatz]")])
        self.assertEqual(set(mit), {"haupt", "basis", "nur-mit-extra"})

    def test_fehlendes_paket_klare_meldung(self):
        self.paket("haupt", requires=["fehlt-noch"], lizenzen={"LICENSE": MIT})
        with self.assertRaises(SystemExit) as fehler:
            drittlizenzen._pakete([Requirement("haupt")])
        self.assertIn("Nicht installiert: fehlt-noch", str(fehler.exception))

    def test_paket_ohne_lizenzdatei_bricht_ab(self):
        self.paket("ohne-lizenz")
        with self.assertRaises(SystemExit) as fehler:
            self.erzeugen("ohne-lizenz")
        self.assertIn("Keine Lizenzdatei gefunden für: ohne-lizenz", str(fehler.exception))

    def test_doppelter_text_verweist_auf_erstes_paket(self):
        self.paket("aaa", lizenzen={"LICENSE": MIT})
        self.paket("bbb", lizenzen={"LICENSE": MIT})
        text = self.erzeugen("aaa", "bbb")
        self.assertEqual(text.count("Copyright (c) Beispiel"), 1)
        self.assertIn("LICENSE: gleicher Text wie bei aaa]", text)

    def test_qt_ohne_kommerzielle_lizenz_mit_lgpl_und_gpl(self):
        self.paket("PySide6_Essentials",
                   lizenzen={"LicenseRef-Qt-Commercial.txt": "Qt kommerziell\n"})
        text = self.erzeugen("PySide6_Essentials")
        self.assertNotIn("Qt kommerziell", text)
        self.assertIn("GNU Lesser General Public License Version 3 (LGPL-3.0)", text)
        self.assertIn("GNU LESSER GENERAL PUBLIC LICENSE", text)
        self.assertIn("GNU GENERAL PUBLIC LICENSE", text)

    def test_ohne_qt_keine_gpl_texte(self):
        self.paket("aaa", lizenzen={"LICENSE": MIT})
        text = self.erzeugen("aaa")
        self.assertNotIn("GNU LESSER GENERAL PUBLIC LICENSE", text)
        self.assertIn("Lizenz: siehe Lizenztext", text)
        self.assertIn(drittlizenzen.CONTAINER_HINWEIS, text)

    def test_lizenzbezeichnung_aus_metadaten(self):
        self.paket("aaa", lizenzen={"LICENSE": MIT}, kopf="License-Expression: MIT\n")
        self.assertIn("Lizenz: MIT\n", self.erzeugen("aaa"))

    def test_python_hinweis_nur_ausserhalb_von_windows(self):
        self.paket("aaa", lizenzen={"LICENSE": MIT})
        for plattform, erwartet in [("win32", False), ("linux", True), ("darwin", True)]:
            with self.subTest(plattform=plattform), \
                    mock.patch.object(drittlizenzen.sys, "platform", plattform), \
                    mock.patch.object(drittlizenzen, "_wurzeln",
                                      return_value=[Requirement("aaa")]):
                text = drittlizenzen.erzeugen("desktop")
                self.assertEqual(drittlizenzen.PYTHON_BIBLIOTHEKEN_HINWEIS in text, erwartet)

    def test_wurzeln_aus_den_requirements_dateien(self):
        namen = {req.name for req in drittlizenzen._wurzeln("desktop")}
        self.assertIn("PySide6", namen)
        namen = {req.name for req in drittlizenzen._wurzeln("web")}
        self.assertEqual(namen, {"psycopg2-binary", "Flask", "waitress"})


if __name__ == "__main__":
    unittest.main()
