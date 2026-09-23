"""Erzeugt docs/HANDBUCH.pdf aus docs/HANDBUCH.md.

Ablauf: Markdown -> HTML (Python-Paket ``markdown``) mit Druck-CSS -> PDF über den
Headless-Modus von Microsoft Edge bzw. Google Chrome (``--print-to-pdf``). Nach jeder
Änderung an HANDBUCH.md oder den Bildern in docs/bilder erneut ausführen:

    python tools/handbuch_pdf.py

Voraussetzungen: ``pip install markdown`` (in Anaconda bereits enthalten) und Edge oder
Chrome. Abweichender Browser-Pfad über die Umgebungsvariable SHS_PDF_BROWSER.
Nur ein Entwickler-Werkzeug - gehört nicht zum Programm und wird nicht mit ausgeliefert.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown
from markdown.extensions.toc import slugify_unicode

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
QUELLE = DOCS / "HANDBUCH.md"
ZIEL = DOCS / "HANDBUCH.pdf"

_BROWSER_KANDIDATEN = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/usr/bin/microsoft-edge",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
)

# Druck-CSS: A4, jedes Kapitel (h2) auf neuer Seite, Bilder nie über die Seitenbreite
# hinaus und nicht über einen Seitenumbruch zerschnitten.
CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
body { font-family: "Segoe UI", Arial, sans-serif; font-size: 10.5pt; line-height: 1.45; color: #1b1f24; }
h1 { font-size: 22pt; color: #1f4fa3; margin: 0 0 6pt 0; }
h2 { font-size: 15pt; color: #1f4fa3; border-bottom: 1.5pt solid #1f4fa3; padding-bottom: 2pt;
     margin-top: 18pt; break-after: avoid; }
h2:not(:first-of-type) { break-before: page; }
h3 { font-size: 12pt; margin-top: 12pt; break-after: avoid; }
p, li { orphans: 3; widows: 3; }
img { max-width: 100%; border: 0.75pt solid #c9ced6; break-inside: avoid; display: block; margin: 6pt auto; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0; break-inside: avoid; font-size: 9.5pt; }
th, td { border: 0.75pt solid #c9ced6; padding: 3pt 5pt; vertical-align: top; text-align: left; }
th { background: #eef2f8; }
blockquote { margin: 8pt 0; padding: 4pt 10pt; background: #fff7e6; border-left: 3pt solid #e0a100; }
code { font-family: Consolas, monospace; font-size: 9.5pt; background: #f2f4f7; padding: 0 2pt; }
a { color: #1f4fa3; text-decoration: none; }
hr { display: none; }
"""


def browser_finden() -> str:
    eigener = os.environ.get("SHS_PDF_BROWSER")
    if eigener:
        return eigener
    for kandidat in _BROWSER_KANDIDATEN:
        if Path(kandidat).exists():
            return kandidat
    raise SystemExit(
        "Kein Edge/Chrome gefunden - Pfad über die Umgebungsvariable SHS_PDF_BROWSER angeben."
    )


def html_erzeugen() -> str:
    inhalt = markdown.markdown(
        QUELLE.read_text(encoding="utf-8"),
        extensions=["tables", "toc", "sane_lists"],
        # Gleiche Anker wie auf GitHub (Umlaute bleiben erhalten), damit die
        # Inhaltsverzeichnis-Links auch im PDF funktionieren.
        extension_configs={"toc": {"slugify": slugify_unicode}},
    )
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<base href="{DOCS.as_uri()}/">
<title>Benutzerhandbuch SHS-Prüfungsprogramm</title>
<style>{CSS}</style></head>
<body>{inhalt}</body></html>"""


def main() -> int:
    browser = browser_finden()
    with tempfile.TemporaryDirectory() as tmp:
        html = Path(tmp) / "HANDBUCH_druck.html"
        html.write_text(html_erzeugen(), encoding="utf-8")
        subprocess.run(
            [browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
             f"--print-to-pdf={ZIEL}", html.as_uri()],
            check=True, capture_output=True, timeout=120,
        )
    print(f"PDF erzeugt: {ZIEL} ({ZIEL.stat().st_size} Bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
