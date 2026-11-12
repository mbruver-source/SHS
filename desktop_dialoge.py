"""Dialoge der Desktop-Oberfläche (Teilnehmer, Startnummern tauschen, Termin-Import,
Zeitplan-Blöcke/Pausen, Bewertungsbögen, Datensicherung, Hilfe, Veranstaltung).

Aus app.py ausgelagert (Codex-Architekturprüfung 27.09.2026); rein interne Umstellung,
Aussehen und Verhalten sind unverändert. Die Abhängigkeiten laufen nur in eine Richtung:
app -> desktop_dialoge -> desktop_gemeinsam, app -> desktop_darstellung (jeweils -> db/
pdf_export); keines dieser Module importiert app.

Fassade (seit 11.11.2026): Der Code liegt in desktop_dialoge_basis, desktop_dialoge_teilnehmer,
desktop_dialoge_termin, desktop_dialoge_planung und desktop_hilfe; dieses Modul reicht alle Namen
weiter, damit `from desktop_dialoge import …` wie vorher funktioniert. Neue Namen hier eintragen.
"""

from __future__ import annotations

from desktop_dialoge_basis import (  # noqa: F401
    DIALOG_MAX_BREITE_ANTEIL,
    DIALOG_MAX_HOEHE_ANTEIL,
    _groesse_auf_bildschirm_begrenzen,
    _scrollflaeche,
    _speichern_vor_dem_schliessen,
)
from desktop_dialoge_teilnehmer import (  # noqa: F401
    StartnummerTauschenDialog,
    TeilnehmerDialog,
    _ANDERE_PRUEFUNG,
    _KLAMMERZUSATZ,
    _MEHRERE_GEGENSTAENDE,
    _MINDESTBREITE_TEXTFELD,
    _TEILNEHMER_DIALOG_GROESSE,
)
from desktop_dialoge_termin import (  # noqa: F401
    ErgebnisseSicherungDialog,
    SicherungErstellenDialog,
    SicherungTeilnehmerDialog,
    TerminImportDialog,
    VeranstaltungsDialog,
    _gleicher_pfad,
    _mit_sqlite_endung,
    _STANDARD_PRUEFUNGSGEBUEHR,
    _wiederherstellungsziele_planen,
)
from desktop_dialoge_planung import (  # noqa: F401
    BehaeltnisEtikettenDialog,
    BewertungsbogenAuswahlDialog,
    PauseDialog,
    PruefungsblockDialog,
    VerteilenDialog,
)
from desktop_hilfe import (  # noqa: F401
    HilfeDialog,
    _hilfe_anker,
    _HILFE_HTML,
    _hilfe_mit_inhaltsverzeichnis,
)
