"""AGENTS.md ist der aus CLAUDE.md erzeugte Spiegel für Codex-Sitzungen.

Maßgeblich ist CLAUDE.md. Nach Änderungen dort AGENTS.md neu erzeugen:

    python test_agents_spiegel.py --schreiben

Der Test schlägt fehl, wenn beide Dateien auseinanderlaufen, und auch, wenn eine der
Ersetzungen unten in CLAUDE.md nicht mehr greift (dann diese Tabelle anpassen).
"""
import sys
import unittest
from pathlib import Path

_ORDNER = Path(__file__).resolve().parent

_KOPF_ZUSATZ = (
    "Diese Datei ist der Spiegel von `CLAUDE.md` für Codex. Maßgeblich ist `CLAUDE.md`; sie wird\n"
    "daraus mit `python test_agents_spiegel.py --schreiben` erzeugt, nicht von Hand gepflegt.\n"
    "\n"
)

_SPIEGEL_BULLET = (
    "- **`AGENTS.md`** ist der Spiegel dieser Datei für Codex-Sitzungen und wird aus ihr erzeugt:\n"
    "  nach Änderungen hier `python test_agents_spiegel.py --schreiben` ausführen (der Test\n"
    "  `test_agents_spiegel` schlägt sonst fehl).\n"
)

_AGENTEN_SATZ = (
    "liefern Befunde nur als Antwort; Berichte legt die Hauptsitzung ab (Sicherheitsberichte in\n"
    "`_unveroeffentlicht/`).\n"
)

_ERSETZUNGEN = [
    ("# SHS-Prüfungsprogramm - Hinweise für Claude-Sitzungen\n\n",
     "# SHS-Prüfungsprogramm - Hinweise für Codex-Sitzungen\n\n" + _KOPF_ZUSATZ),
    (_SPIEGEL_BULLET, ""),
    (_AGENTEN_SATZ,
     _AGENTEN_SATZ + "Codex kennt diese Dateien nicht; dort die Texte als Auftrag für die jeweilige Rolle\n"
     "verwenden.\n"),
    ("(in Claude Code als Skill `shs-build`)", "(in Claude Code als Skill `shs-build`; Codex liest die Datei direkt)"),
]


def erzeuge_agents_text(claude_text):
    """Leitet den Inhalt von AGENTS.md aus dem von CLAUDE.md ab."""
    text = claude_text
    for alt, neu in _ERSETZUNGEN:
        if text.count(alt) != 1:
            raise ValueError(f"Ersetzung greift nicht genau einmal: {alt[:60]!r}")
        text = text.replace(alt, neu)
    return text


def _lesen(name):
    return (_ORDNER / name).read_text(encoding="utf-8")


class TestAgentsSpiegel(unittest.TestCase):
    def test_agents_ist_aus_claude_erzeugt(self):
        erwartet = erzeuge_agents_text(_lesen("CLAUDE.md"))
        self.assertEqual(
            _lesen("AGENTS.md"), erwartet,
            "AGENTS.md weicht von CLAUDE.md ab - `python test_agents_spiegel.py --schreiben` ausführen")


if __name__ == "__main__":
    if "--schreiben" in sys.argv:
        ziel = _ORDNER / "AGENTS.md"
        with open(ziel, "w", encoding="utf-8", newline="\n") as f:
            f.write(erzeuge_agents_text(_lesen("CLAUDE.md")))
        print("AGENTS.md geschrieben")
    else:
        unittest.main()
