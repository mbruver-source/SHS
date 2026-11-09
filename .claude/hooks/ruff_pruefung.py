"""PostToolUse-Hook: prüft eine geänderte .py-Datei mit ruff auf echte Fehler.

Nur Syntaxfehler und undefinierte Namen (E9, F63, F7, F82); der Bestand ist dafür sauber.
Stil-Regeln sind bewusst nicht dabei (der Bestand hat dort mehrere hundert Treffer).
Bei Treffern Exit-Code 2: die Meldung geht dann an Claude zurück.
"""

import json
import subprocess
import sys

try:
    pfad = json.load(sys.stdin).get("tool_input", {}).get("file_path", "")
except ValueError:
    sys.exit(0)

if not pfad.endswith(".py"):
    sys.exit(0)

try:
    ergebnis = subprocess.run(
        ["ruff", "check", "--select", "E9,F63,F7,F82", "--output-format", "concise", pfad],
        capture_output=True, text=True, timeout=30,
    )
except (OSError, subprocess.SubprocessError):
    sys.exit(0)  # ruff fehlt oder hängt: nie den Arbeitsablauf blockieren

if ergebnis.returncode != 0:
    sys.stderr.write(ergebnis.stdout or ergebnis.stderr)
    sys.exit(2)
