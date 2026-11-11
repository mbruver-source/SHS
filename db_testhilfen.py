"""Test-Hilfe für die aufgeteilte Datenschicht (nur für Tests, wird nicht ausgeliefert).

Seit 11.11.2026 liegt der Code von db.py in den Schichtmodulen db_verbindung, db_stamm,
db_ergebnisse, db_zeitplan, db_termine, db_web und db_sync; db.py ist nur noch eine Fassade.
Ein Aufruf innerhalb der Datenschicht schlägt den Namen im Modul nach, in dem er steht
(oder in das er importiert wurde). Ein `patch("db.NAME")` auf die Fassade erreicht ihn deshalb
nicht. `patch_db` ersetzt den Namen in der Fassade und in jedem Schichtmodul, das ihn hat.
"""

from __future__ import annotations

import contextlib
import importlib
from unittest import mock

MODULE = (
    "db", "db_verbindung", "db_stamm", "db_ergebnisse", "db_zeitplan", "db_termine", "db_web", "db_sync",
)


class patch_db:  # noqa: N801 - heißt wie mock.patch
    """Wie `mock.patch("db.NAME", new, **kwargs)`, aber in allen Datenschicht-Modulen, die den Namen
    haben. Als Kontextmanager (`with patch_db(...) as ersatz`) oder mit start()/stop() benutzbar;
    der Ersatz ist wie bei `mock.patch` ein MagicMock mit `kwargs`, wenn `new` fehlt."""

    def __init__(self, name: str, new=mock.DEFAULT, **kwargs):
        self._name = name
        self._new = mock.MagicMock(**kwargs) if new is mock.DEFAULT else new
        self._stapel: contextlib.ExitStack | None = None

    def start(self):
        stapel = contextlib.ExitStack()
        gefunden = False
        for modulname in MODULE:
            modul = importlib.import_module(modulname)
            if hasattr(modul, self._name):
                stapel.enter_context(mock.patch.object(modul, self._name, self._new))
                gefunden = True
        if not gefunden:
            stapel.close()
            raise AttributeError(f"{self._name} gibt es in keinem Datenschicht-Modul")
        self._stapel = stapel
        return self._new

    def stop(self) -> None:
        if self._stapel is not None:
            self._stapel.close()
            self._stapel = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *_exc) -> None:
        self.stop()
