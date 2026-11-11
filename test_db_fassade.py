"""Prüft die Aufteilung der Datenschicht (seit 11.11.2026): db.py ist eine Fassade über die
Schichtmodule; die Module dürfen nur von unten nach oben aufeinander verweisen."""

import ast
import importlib
import pathlib
import unittest

import db

# Von unten nach oben: ein Modul darf nur Module weiter links importieren.
SCHICHTEN = ["db_verbindung", "db_stamm", "db_ergebnisse", "db_zeitplan", "db_termine", "db_web", "db_sync"]
ORDNER = pathlib.Path(__file__).resolve().parent


def _namen(modul_name: str) -> list[str]:
    baum = ast.parse((ORDNER / f"{modul_name}.py").read_text(encoding="utf-8"))
    namen = []
    for n in baum.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            namen.append(n.name)
        elif isinstance(n, ast.Assign):
            namen += [t.id for t in n.targets if isinstance(t, ast.Name)]
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            namen.append(n.target.id)
    return namen


class TestDbFassade(unittest.TestCase):
    def test_jeder_name_der_schichtmodule_steht_in_db(self):
        fehlend = []
        for modul_name in SCHICHTEN:
            modul = importlib.import_module(modul_name)
            for name in _namen(modul_name):
                if not hasattr(db, name):
                    fehlend.append(f"{modul_name}.{name}")
                elif callable(getattr(modul, name)) and getattr(db, name) is not getattr(modul, name):
                    fehlend.append(f"{modul_name}.{name} (anderes Objekt)")
        self.assertEqual(fehlend, [], "Neue Namen in der Fassade db.py eintragen")

    def test_kein_name_steht_in_zwei_schichtmodulen(self):
        gesehen = {}
        doppelt = []
        for modul_name in SCHICHTEN:
            for name in _namen(modul_name):
                if name in gesehen:
                    doppelt.append(f"{name}: {gesehen[name]} und {modul_name}")
                gesehen[name] = modul_name
        self.assertEqual(doppelt, [])

    def test_schichten_verweisen_nur_nach_unten(self):
        verstoesse = []
        for rang, modul_name in enumerate(SCHICHTEN):
            baum = ast.parse((ORDNER / f"{modul_name}.py").read_text(encoding="utf-8"))
            for n in ast.walk(baum):
                if isinstance(n, ast.ImportFrom) and n.module in SCHICHTEN:
                    if SCHICHTEN.index(n.module) >= rang:
                        verstoesse.append(f"{modul_name} importiert {n.module}")
                if isinstance(n, ast.ImportFrom) and n.module == "db":
                    verstoesse.append(f"{modul_name} importiert die Fassade db")
                if isinstance(n, ast.Import) and any(a.name == "db" for a in n.names):
                    verstoesse.append(f"{modul_name} importiert die Fassade db")
        self.assertEqual(verstoesse, [])


if __name__ == "__main__":
    unittest.main()
