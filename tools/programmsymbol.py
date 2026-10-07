"""Erzeugt das Programmsymbol aus einem Foto (Marco 07.10.2026: Beagle-Foto als
Buntstift-Zeichnung, Entwurf "K2").

    python tools/programmsymbol.py <foto.jpg>

Schreibt nach symbol/:
  - programmsymbol.png  (512 x 512, Fenster-Symbol, Linux, Website)
  - programmsymbol.ico  (16-256 px, Windows-EXE und Installer)
  - programmsymbol.icns (macOS-App)
und docs/favicon.png (180 x 180, Website, auch als Apple-Touch-Icon).

Das Foto selbst liegt nicht im Repo; das Ergebnis wird eingecheckt. Der Ausschnitt ist auf
das ursprüngliche Foto (1293 x 1370 px) abgestimmt, siehe AUSSCHNITT.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

ZIEL = Path(__file__).resolve().parent.parent / "symbol"
FAVICON = Path(__file__).resolve().parent.parent / "docs" / "favicon.png"
AUSSCHNITT = (40, 20, 1293, 1273)  # ganzer Kopf samt Ohren, quadratisch
PAPIER = (250, 247, 240)
ARBEITSGROESSE = 1280
GROESSE = 1024


def _skizze(bild: Image.Image, radius: float) -> Image.Image:
    """Bleistift-Linien: Graustufen durch das weichgezeichnete Negativ teilen (Farbabwedeln)."""
    grau = ImageOps.grayscale(bild)
    negativ = ImageOps.invert(grau).filter(ImageFilter.GaussianBlur(radius))
    nenner = ImageOps.invert(negativ).point(lambda w: max(1, w))
    g, n = grau.load(), nenner.load()
    ergebnis = Image.new("L", grau.size)
    e = ergebnis.load()
    for y in range(grau.size[1]):
        for x in range(grau.size[0]):
            e[x, y] = min(255, g[x, y] * 255 // n[x, y])
    return ImageEnhance.Contrast(ergebnis).enhance(1.6)


def _ausblendmaske(groesse: int) -> Image.Image:
    """Weiche Ellipse um den Kopf: innen die Zeichnung, außen Papier."""
    maske = Image.new("L", (groesse, groesse), 0)
    ImageDraw.Draw(maske).ellipse((groesse * 0.04, 0, groesse * 0.96, groesse * 1.08), fill=255)
    return maske.filter(ImageFilter.GaussianBlur(groesse * 0.05))


def symbol_erzeugen(foto_pfad: str) -> Image.Image:
    foto = Image.open(foto_pfad).convert("RGB")
    kopf = foto.crop(AUSSCHNITT).resize((ARBEITSGROESSE, ARBEITSGROESSE), Image.LANCZOS)
    linien = _skizze(kopf, radius=20)
    farbe = ImageEnhance.Color(kopf.filter(ImageFilter.GaussianBlur(8))).enhance(0.8)
    farbe = Image.blend(Image.new("RGB", farbe.size, PAPIER), farbe, 0.55)
    zeichnung = ImageChops.multiply(farbe, Image.merge("RGB", (linien, linien, linien)))
    zeichnung = Image.composite(zeichnung, Image.new("RGB", zeichnung.size, PAPIER),
                                _ausblendmaske(ARBEITSGROESSE))
    zeichnung = zeichnung.resize((GROESSE, GROESSE), Image.LANCZOS)

    rand, radius = GROESSE * 16 // 512, GROESSE * 104 // 512
    ecken = Image.new("L", (GROESSE, GROESSE), 0)
    ImageDraw.Draw(ecken).rounded_rectangle((rand, rand, GROESSE - rand, GROESSE - rand), radius=radius, fill=255)
    ergebnis = Image.new("RGBA", (GROESSE, GROESSE), (0, 0, 0, 0))
    ergebnis.paste(zeichnung, (0, 0), ecken)
    ImageDraw.Draw(ergebnis).rounded_rectangle(
        (rand, rand, GROESSE - rand, GROESSE - rand), radius=radius,
        outline=(200, 190, 170, 255), width=GROESSE // 128)
    return ergebnis


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    symbol = symbol_erzeugen(sys.argv[1])
    ZIEL.mkdir(exist_ok=True)
    symbol.resize((512, 512), Image.LANCZOS).save(ZIEL / "programmsymbol.png", optimize=True)
    symbol.save(ZIEL / "programmsymbol.ico",
                sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    symbol.save(ZIEL / "programmsymbol.icns")
    symbol.resize((180, 180), Image.LANCZOS).save(FAVICON, optimize=True)
    print(f"{FAVICON.name}: {FAVICON.stat().st_size} Bytes")
    for datei in sorted(ZIEL.iterdir()):
        print(f"{datei.name}: {datei.stat().st_size} Bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
