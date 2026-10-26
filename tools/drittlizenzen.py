"""Stellt THIRD_PARTY_LICENSES.txt zusammen: die Lizenzen aller Fremdkomponenten, die mit dem
Programm ausgeliefert werden (Marco 25.10.2026).

    python tools/drittlizenzen.py desktop <ziel.txt>
    python tools/drittlizenzen.py web <ziel.txt>

"desktop" geht von requirements.txt aus (Installer, .app, AppImage/.deb), "web" von
requirements-postgres.txt und requirements-web.txt (Container-Image). Ausgehend davon
werden die Abhängigkeiten der installierten Pakete verfolgt und je Paket Version, Lizenz und
die mitgelieferten Lizenzdateien aufgenommen, dazu die Lizenz der Python-Laufzeit.

Die Datei wird beim Build erzeugt statt eingecheckt, weil sie zu den Paketversionen der
jeweiligen Build-Umgebung passen muss: build.spec ruft das Skript für die Desktop-Builds auf,
das Containerfile für das Image.

Findet sich für ein Paket keine Lizenzdatei, bricht das Skript ab, damit kein Build mit
unvollständigen Lizenzangaben entsteht. Die Wheels von PySide6/Shiboken6 enthalten nur den
Text der kommerziellen Qt-Lizenz; für die hier geltende LGPL-3.0 stehen deren Text und der
der GPL-3.0 in lizenzen/ (Texte von gnu.org).
"""
from __future__ import annotations

import hashlib
import re
import sys
import sysconfig
from importlib import metadata
from pathlib import Path

try:
    from packaging.requirements import Requirement
except ImportError:  # Rückfall, falls packaging nicht eigenständig installiert ist
    from pip._vendor.packaging.requirements import Requirement

PROJEKT = Path(__file__).resolve().parent.parent
REPO = "https://github.com/mbruver-source/SHS"

VARIANTEN = {
    "desktop": ["requirements.txt"],
    "web": ["requirements-postgres.txt", "requirements-web.txt"],
}
# Zusätzlich mitgelieferte Dateien, die nicht aus einem Python-Paket stammen.
EIGENE_DATEIEN = {
    "desktop": [("DejaVu-Schriften (PDF-Ausgabe)", "fonts/LICENSE-DejaVu.txt")],
    "web": [],
}
# Alle Teilpakete von PySide6 (Essentials, Addons, Pdf, WebEngine ...) und Shiboken6. Ihre Wheels
# enthalten nur den Text der kommerziellen Qt-Lizenz, die hier nicht gilt; der wird weggelassen.
QT_PAKET = re.compile(r"^(pyside6|shiboken6)(-|$)")
QT_HINWEIS = f"""\
PySide6, Shiboken6 und das darin enthaltene Qt 6 (The Qt Company Ltd. und andere) stehen unter
der GNU Lesser General Public License Version 3 (LGPL-3.0). Ihr Text steht am Ende dieser
Datei, ebenso der Text der GPL-3.0, auf der die LGPL-3.0 aufbaut.
Quellcode: https://code.qt.io/ und https://download.qt.io/official_releases/QtForPython/
Qt enthält seinerseits Komponenten Dritter, deren Lizenzen hier aufgeführt sind:
https://doc.qt.io/qt-6/licenses-used-in-qt.html
Das SHS-Prüfungsprogramm nutzt Qt unverändert. Wer die Qt-Bibliotheken durch eine eigene
Version ersetzen möchte, kann das Programm aus dem offenen Quellcode ({REPO})
mit PyInstaller selbst bauen (siehe README_INSTALLER.md)."""
# Zusatzhinweise für Pakete, die fremde Bibliotheken ohne eigene Lizenzdatei mitbringen.
HINWEISE = {
    "psycopg2-binary": """Das Binärpaket psycopg2-binary bringt zusätzlich die PostgreSQL-Clientbibliothek libpq
(PostgreSQL License, https://www.postgresql.org/about/licence/) und OpenSSL (Apache-2.0,
https://www.openssl.org/source/license.html) mit, unter Linux außerdem weitere
Systembibliotheken (u. a. Kerberos, OpenLDAP, Cyrus SASL), jeweils unter ihren eigenen
Lizenzen. Quellcode: https://github.com/psycopg/psycopg2""",
}
# Unter Windows enthält Pythons LICENSE.txt auch die Lizenzen der mitgelieferten Bibliotheken,
# unter macOS und Linux ist es nur der PSF-Text (Verifikation 25.10.2026, Befund 1).
PYTHON_BIBLIOTHEKEN_HINWEIS = """\
Python bringt unter macOS und Linux weitere Bibliotheken mit, die mit dem Programm ausgeliefert
werden, u. a. OpenSSL (Apache-2.0), libffi (MIT), SQLite (gemeinfrei), zlib (zlib-Lizenz),
bzip2 (BSD-artig), xz/liblzma (gemeinfrei/BSD) und expat (MIT). Ihre Lizenztexte stehen unter
https://docs.python.org/3/license.html ("Licenses and Acknowledgements for Incorporated
Software")."""
CONTAINER_HINWEIS = """\
Das Container-Image baut auf dem offiziellen Image python:3.11-slim (Debian) auf. Die Lizenzen
der darin enthaltenen Debian-Pakete stehen im Image unter /usr/share/doc/<paket>/copyright."""
LIZENZ_DATEINAME = re.compile(r"(LICEN[CS]E|COPYING|NOTICE)", re.IGNORECASE)
TRENNER = "=" * 78


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _gilt(req: Requirement, extras: frozenset[str]) -> bool:
    """Gilt die Angabe auf dieser Plattform (Marker), ggf. für eines der angeforderten Extras?"""
    if req.marker is None:
        return True
    return any(req.marker.evaluate({"extra": extra}) for extra in extras | {""})


def _wurzeln(variante: str) -> list[Requirement]:
    wurzeln = []
    for datei in VARIANTEN[variante]:
        for zeile in (PROJEKT / datei).read_text(encoding="utf-8").splitlines():
            zeile = zeile.split("#", 1)[0].strip()
            if zeile:
                req = Requirement(zeile)
                if _gilt(req, frozenset()):
                    wurzeln.append(req)
    return wurzeln


def _pakete(wurzeln: list[Requirement]) -> dict[str, metadata.Distribution]:
    """Alle installierten Pakete, die von den Wurzeln aus gebraucht werden, samt der
    Abhängigkeiten angeforderter Extras (z. B. "Flask[async]")."""
    gefunden: dict[str, metadata.Distribution] = {}
    besucht: set[tuple[str, frozenset[str]]] = set()
    fehlend: set[str] = set()
    offen = [(req.name, frozenset(req.extras)) for req in wurzeln]
    while offen:
        name, extras = offen.pop()
        if (_norm(name), extras) in besucht:
            continue
        besucht.add((_norm(name), extras))
        try:
            verteilung = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            fehlend.add(name)
            continue
        gefunden[_norm(name)] = verteilung
        for angabe in verteilung.requires or []:
            req = Requirement(angabe)
            if _gilt(req, extras):
                offen.append((req.name, frozenset(req.extras)))
    if fehlend:
        raise SystemExit("Nicht installiert: " + ", ".join(sorted(fehlend))
                         + " - zuerst die passenden requirements*.txt installieren")
    return gefunden


def _lizenz_bezeichnung(verteilung: metadata.Distribution) -> str:
    md = verteilung.metadata
    if md.get("License-Expression"):
        return md["License-Expression"]
    text = (md.get("License") or "").strip()
    if text and "\n" not in text and len(text) <= 80:
        return text
    klassen = [k.split("::")[-1].strip() for k in md.get_all("Classifier") or []
               if k.startswith("License ::")]
    return ", ".join(klassen) or "siehe Lizenztext"


def _lizenz_texte(verteilung: metadata.Distribution, qt: bool) -> list[tuple[str, str]]:
    texte = []
    for datei in verteilung.files or []:
        if qt and "commercial" in datei.name.lower():
            continue
        if LIZENZ_DATEINAME.search(datei.name) and not datei.name.endswith((".py", ".pyc")):
            pfad = Path(verteilung.locate_file(datei))
            if pfad.is_file():
                texte.append((str(datei), pfad.read_text(encoding="utf-8", errors="replace")))
    return texte


def _python_lizenz() -> str:
    kandidaten = [
        Path(sys.base_prefix) / "LICENSE.txt",            # Windows (python.org)
        Path(sysconfig.get_path("stdlib")) / "LICENSE.txt",  # Linux, macOS, Container
        Path(sys.base_prefix) / "LICENSE_PYTHON.txt",     # Anaconda
    ]
    for pfad in kandidaten:
        if pfad.is_file():
            return pfad.read_text(encoding="utf-8", errors="replace")
    raise SystemExit("Lizenztext der Python-Laufzeit nicht gefunden: "
                     + ", ".join(map(str, kandidaten)))


def _abschnitt(titel: str, kopf: list[str], texte: list[str]) -> str:
    teile = [TRENNER, titel, TRENNER, *kopf, ""]
    for text in texte:
        teile += [text.rstrip(), ""]
    return "\n".join(teile)


def erzeugen(variante: str) -> str:
    python_texte = [_python_lizenz()]
    if variante == "web":
        python_texte.insert(0, CONTAINER_HINWEIS)
    elif sys.platform != "win32":
        python_texte.insert(0, PYTHON_BIBLIOTHEKEN_HINWEIS)
    abschnitte = [
        "Lizenzen der Komponenten Dritter im SHS-Prüfungsprogramm\n"
        "Third-party licenses of the SHS-Prüfungsprogramm\n\n"
        f"Das SHS-Prüfungsprogramm selbst steht unter der MIT-Lizenz (LICENSE, {REPO}).\n"
        "Es enthält die folgenden Komponenten Dritter, jeweils unter ihrer eigenen Lizenz.\n",
        _abschnitt(f"Python {sys.version.split()[0]}",
                   ["Lizenz: PSF-2.0 (Python Software Foundation License)"],
                   python_texte),
    ]
    ohne_lizenz = []
    gesehen: dict[str, str] = {}  # Prüfsumme -> Paket, in dem der Text zuerst steht
    qt_dabei = False
    for name, verteilung in sorted(_pakete(_wurzeln(variante)).items()):
        kopf = [f"Version: {verteilung.version}",
                f"Lizenz: {_lizenz_bezeichnung(verteilung)}"]
        if verteilung.metadata.get("Home-page"):
            kopf.append(f"Projekt: {verteilung.metadata['Home-page']}")
        qt = bool(QT_PAKET.match(name))
        texte = []
        for datei, text in _lizenz_texte(verteilung, qt):
            pruefsumme = hashlib.sha256(text.encode()).hexdigest()
            if pruefsumme in gesehen:
                texte.append(f"[{datei}: gleicher Text wie bei {gesehen[pruefsumme]}]")
            else:
                gesehen[pruefsumme] = verteilung.metadata["Name"]
                texte.append(f"--- {datei} ---\n{text}")
        if qt:
            qt_dabei = True
            texte.insert(0, QT_HINWEIS)
        elif name in HINWEISE:
            texte.insert(0, HINWEISE[name])
        elif not texte:
            ohne_lizenz.append(verteilung.metadata["Name"])
        abschnitte.append(_abschnitt(verteilung.metadata["Name"], kopf, texte))
    if ohne_lizenz:
        raise SystemExit("Keine Lizenzdatei gefunden für: " + ", ".join(ohne_lizenz)
                         + " - Lizenztext in tools/drittlizenzen.py ergänzen")
    for titel, datei in EIGENE_DATEIEN[variante]:
        abschnitte.append(_abschnitt(titel, [], [(PROJEKT / datei).read_text(encoding="utf-8")]))
    if qt_dabei:
        for titel, datei in [("GNU Lesser General Public License, Version 3", "LGPL-3.0.txt"),
                             ("GNU General Public License, Version 3", "GPL-3.0.txt")]:
            text = (PROJEKT / "lizenzen" / datei).read_text(encoding="utf-8")
            abschnitte.append(_abschnitt(titel, [], [text]))
    return "\n\n".join(abschnitte)


def main(argumente: list[str]) -> None:
    if len(argumente) != 2 or argumente[0] not in VARIANTEN:
        raise SystemExit(__doc__)
    ziel = Path(argumente[1])
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(erzeugen(argumente[0]), encoding="utf-8", newline="\n")
    print(f"{ziel} geschrieben")


if __name__ == "__main__":
    main(sys.argv[1:])
