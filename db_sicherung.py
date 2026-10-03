"""Datensicherung: Export/Import aller Termin-Dateien als ZIP, optional passwortgeschützt.

Aus db.py ausgelagert (Codex-Architekturprüfung 27.09.2026). Baut auf db auf
(termine_ordner); db selbst importiert dieses Modul nicht, damit kein Ringimport entsteht.
"""

from __future__ import annotations

import os
import tempfile
import zipfile
from contextlib import suppress
from pathlib import Path

import pyzipper

from db import termine_ordner

# --- Datensicherung (Export/Import aller Termine als ZIP, optional passwortgeschützt) ---
#
# Nutzt pyzipper (reines Python, keine kompilierten Zusatzabhängigkeiten) statt des
# eingebauten zipfile-Moduls, da zipfile zwar passwortgeschützte ZIPs LESEN, aber keine
# mit echter (AES-256-)Verschlüsselung SCHREIBEN kann. Ein Backup ohne Passwort wird
# trotzdem mit dem einfacheren, garantiert überall (z.B. Windows-Explorer) kompatiblen
# zipfile-Modul erzeugt.


class PasswortFalschError(Exception):
    """Ein Sicherungs-ZIP ist passwortgeschützt und das angegebene Passwort fehlt oder
    ist falsch (siehe sicherung_inhalt()/sicherung_wiederherstellen())."""


# Sicherheitsprüfung 03.10.2026, S-8: Obergrenzen für Sicherungs-ZIPs. Ein präpariertes
# ZIP hätte sonst mit wenigen KB beim Entpacken Gigabytes erzeugen können ("ZIP-Bombe").
# Großzügig gewählt - ein Termin ist typischerweise unter 1 MB groß.
_MAX_ZIP_EINTRAEGE = 500
_MAX_DATEIGROESSE = 200 * 1024 * 1024  # je Termin-Datei
_MAX_GESAMTGROESSE = 1024 * 1024 * 1024  # alle Termin-Dateien zusammen

# S-8: Unter Windows reservierte Gerätenamen - "CON.sqlite" o. Ä. würde nicht als Datei,
# sondern auf ein Gerät geschrieben.
_WINDOWS_GERAETENAMEN = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


def _zip_grenzen_pruefen(zf) -> None:
    """S-8: Wirft ValueError, wenn das ZIP zu viele Einträge hat oder eine Termin-Datei
    bzw. alle zusammen ausgepackt die Obergrenzen überschreiten. Maßgeblich ist die im
    ZIP angegebene Originalgröße; zipfile/pyzipper liefern beim Lesen nie mehr Bytes als
    dort angegeben."""
    eintraege = zf.infolist()
    if len(eintraege) > _MAX_ZIP_EINTRAEGE:
        raise ValueError(
            f"Die Sicherung enthält mehr als {_MAX_ZIP_EINTRAEGE} Einträge - das ist keine "
            "mit diesem Programm erstellte Sicherung."
        )
    gesamt = 0
    for info in eintraege:
        if info.file_size > _MAX_DATEIGROESSE:
            raise ValueError(
                f"Die Datei „{info.filename}“ in der Sicherung ist ausgepackt größer als "
                f"{_MAX_DATEIGROESSE // (1024 * 1024)} MB - das ist keine gültige Termin-Datei."
            )
        gesamt += info.file_size
    if gesamt > _MAX_GESAMTGROESSE:
        raise ValueError(
            f"Die Sicherung ist ausgepackt größer als {_MAX_GESAMTGROESSE // (1024 * 1024 * 1024)} GB "
            "- das ist keine mit diesem Programm erstellte Sicherung."
        )


def _ist_sicherer_dateiname(name: str) -> bool:
    """Prüft, ob `name` ein "flacher" Dateiname ohne Pfadanteile ist - also ohne '/'
    oder '\\\\' und ohne '..'-Segmente. sicherung_erstellen() schreibt ZIP-Einträge
    immer nur mit ihrem reinen Dateinamen (arcname=datei.name, siehe dort), ein
    legitimes, von dieser App selbst erstelltes Backup enthält also nie etwas anderes.

    QS-Review (19./20.09., Path Traversal beim Backup-Import): Ohne diese Prüfung wurde
    ein ZIP-Eintragsname wie '../../irgendwas/wichtig.sqlite' unverändert als Zielname für
    os.replace() in sicherung_wiederherstellen() übernommen - ein präpariertes (nicht
    selbst erstelltes) Sicherungs-ZIP hätte damit beim "Wiederherstellen" eine Datei
    AUSSERHALB des Termine-Ordners schreiben/überschreiben können. Da ein solcher Name nie
    mit einer vorhandenen Termin-Datei im Zielordner übereinstimmt, wurde dabei sogar der
    Konflikt-Dialog übersprungen (Behandlung wie "neuer Termin", stiller
    Überschreibversuch). Wird sowohl in sicherung_inhalt() angewendet (unsichere Einträge
    tauchen erst gar nicht in der dem Nutzer angezeigten Liste auf) als auch sicherheitshalber
    nochmal in sicherung_wiederherstellen() direkt vor dem Schreiben geprüft."""
    if not name or name != os.path.basename(name):
        return False
    if "\\" in name or ".." in Path(name).parts:
        return False
    # S-8: Windows-Gerätenamen (auch mit Endung oder Leerzeichen vor dem Punkt).
    if name.split(".")[0].rstrip(" ").upper() in _WINDOWS_GERAETENAMEN:
        return False
    return True


def eindeutigen_dateinamen_finden(
    ordner: Path, gewuenschter_name: str, bereits_vergeben: set[str] | frozenset[str] = frozenset()
) -> str:
    """Hängt bei einem im Ordner bereits vergebenen Dateinamen einen Zähler an (z.B.
    'Termin (2).sqlite'), bis ein noch freier Name gefunden ist - für die Option "als
    Kopie importieren" beim Wiederherstellen einer Sicherung (siehe app.py).

    `bereits_vergeben`: Namen, die noch nicht auf der Platte liegen, aber im selben
    Vorgang schon als Ziel eingeplant sind (Codeprüfung 22.09., G5: enthielt eine
    Sicherung "A.sqlite" und "A (2).sqlite", landeten sonst beide auf "A (2).sqlite" und
    einer überschrieb still den anderen)."""
    ordner = Path(ordner)

    def belegt(name: str) -> bool:
        return name in bereits_vergeben or (ordner / name).exists()

    if not belegt(gewuenschter_name):
        return gewuenschter_name
    ziel = Path(gewuenschter_name)
    stamm, endung = ziel.stem, ziel.suffix
    zaehler = 2
    while belegt(f"{stamm} ({zaehler}){endung}"):
        zaehler += 1
    return f"{stamm} ({zaehler}){endung}"


def sicherung_erstellen(
    ziel_pfad: str, passwort: str | None = None, nur_dateien: list[str] | None = None, ordner: Path | None = None
) -> int:
    """Erstellt ein ZIP-Backup der Termin-Dateien aus `ordner` (Standard: termine_ordner()).

    nur_dateien: optionale Liste von Dateinamen (nicht volle Pfade) - falls angegeben,
    werden nur diese gesichert, sonst ALLE *.sqlite-Dateien im Ordner.
    passwort: falls angegeben (nicht leer), wird das ZIP AES-256-verschlüsselt.
    Gibt die Anzahl der gesicherten Termin-Dateien zurück.
    Wirft ValueError, falls es nichts zu sichern gibt.
    """
    ordner = ordner or termine_ordner()
    dateien = sorted(p for p in ordner.glob("*.sqlite") if p.is_file())
    if nur_dateien is not None:
        gewaehlt = set(nur_dateien)
        dateien = [p for p in dateien if p.name in gewaehlt]
    if not dateien:
        raise ValueError("Es gibt keine Termine zum Sichern.")

    if passwort:
        with pyzipper.AESZipFile(
            ziel_pfad, "w", compression=pyzipper.ZIP_LZMA, encryption=pyzipper.WZ_AES
        ) as zf:
            zf.setpassword(passwort.encode("utf-8"))
            for datei in dateien:
                zf.write(datei, arcname=datei.name)
    else:
        with zipfile.ZipFile(ziel_pfad, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for datei in dateien:
                zf.write(datei, arcname=datei.name)
    return len(dateien)


def sicherung_inhalt(zip_pfad: str, passwort: str | None = None) -> list[str]:
    """Liefert die Namen der Termin-Dateien (*.sqlite) in einem Sicherungs-ZIP, ohne sie
    zu entpacken - Grundlage für die Konflikterkennung vor dem eigentlichen
    Wiederherstellen (siehe sicherung_wiederherstellen() und app.py).

    Wirft PasswortFalschError, wenn das ZIP passwortgeschützt ist und `passwort` fehlt
    oder falsch ist; ValueError, wenn die Datei kein gültiges ZIP ist oder keine
    Termin-Dateien enthält.
    """
    try:
        with pyzipper.AESZipFile(zip_pfad) as zf:
            if passwort:
                zf.setpassword(passwort.encode("utf-8"))
            _zip_grenzen_pruefen(zf)
            # _ist_sicherer_dateiname() filtert Einträge mit Pfadanteilen (z.B.
            # '../../wichtig.sqlite') schon hier heraus, BEVOR sie dem Nutzer in der
            # Konflikt-Auswahl angezeigt werden (siehe Docstring dort).
            namen = [n for n in zf.namelist() if n.lower().endswith(".sqlite") and _ist_sicherer_dateiname(n)]
            if not namen:
                raise ValueError("Das ZIP enthält keine Termin-Dateien (.sqlite).")
            # Erzwingt die Passwortprüfung sofort (Lesen der ersten Datei), statt erst
            # beim eigentlichen Wiederherstellen mittendrin zu scheitern.
            zf.read(namen[0])
    except RuntimeError as exc:
        if "password" in str(exc).lower():
            raise PasswortFalschError(
                "Das Passwort ist falsch, oder die Datei ist passwortgeschützt und es "
                "wurde keines angegeben."
            ) from exc
        raise
    except (zipfile.BadZipFile, pyzipper.zipfile.BadZipFile) as exc:
        # pyzipper verwendet eine eigene, von zipfile GEERBTE/geforkte BadZipFile-Klasse
        # (pyzipper.zipfile.BadZipFile) statt der Standardbibliotheks-Klasse - beide
        # werden hier abgefangen, da AESZipFile ausschließlich die eigene wirft (per
        # echtem CI-Testlauf bestätigt).
        raise ValueError("Das ist keine gültige ZIP-Datei.") from exc
    return sorted(namen)


def sicherung_wiederherstellen(
    zip_pfad: str, entscheidungen: dict[str, str], passwort: str | None = None, ordner: Path | None = None
) -> list[str]:
    """Entpackt ausgewählte Termin-Dateien aus einem Sicherungs-ZIP in `ordner`
    (Standard: termine_ordner()).

    entscheidungen: {Dateiname im ZIP: Zieldateiname im Zielordner} - ein von
    sicherung_inhalt() gelieferter Name, der hier NICHT vorkommt, wird übersprungen
    (z.B. weil der Nutzer diesen Termin beim Konflikt-Dialog übersprungen hat). Bei
    Namensgleichheit mit einer vorhandenen Datei wird diese überschrieben; für "als Kopie
    importieren" vorher eindeutigen_dateinamen_finden() für einen freien Zielnamen
    verwenden. Gibt die Liste der tatsächlich geschriebenen Zieldateinamen zurück.

    Jede Datei wird ATOMAR geschrieben (temporäre Datei im selben Zielordner, danach
    os.replace()) statt direkt in die Zieldatei - bricht das Schreiben mittendrin ab
    (Absturz, Stromausfall, volle Platte während GENAU dieser Datei), bleibt entweder
    die alte Datei vollständig unverändert oder die neue vollständig geschrieben zurück,
    nie eine abgeschnittene/korrupte Datei mit einem dabei unwiederbringlich verlorenen
    bisherigen Terminstand (QS-Review 19./20.09.: vorher direktes Path.write_bytes() auf
    die Zieldatei selbst, ohne diese Absicherung).
    """
    ordner = ordner or termine_ordner()
    geschrieben: list[str] = []
    try:
        with pyzipper.AESZipFile(zip_pfad) as zf:
            if passwort:
                zf.setpassword(passwort.encode("utf-8"))
            # S-8: auch hier, falls ein Aufrufer sicherung_inhalt() nicht vorschaltet.
            _zip_grenzen_pruefen(zf)
            for quelle, ziel in entscheidungen.items():
                # Zweite, unabhängige Absicherung gegen Path Traversal (siehe
                # _ist_sicherer_dateiname()) - auch wenn sicherung_inhalt() unsichere
                # Namen bereits vorher herausfiltert, verlässt sich diese Funktion hier
                # nicht darauf, dass jeder Aufrufer das auch tatsächlich vorschaltet.
                if not _ist_sicherer_dateiname(ziel):
                    raise ValueError(f"Unsicherer Zieldateiname: {ziel!r}")
                daten = zf.read(quelle)
                ziel_pfad = ordner / ziel
                # os.replace() ist nur innerhalb DESSELBEN Dateisystems atomar - die
                # temporäre Datei muss deshalb im selben Ordner liegen wie das Ziel, nicht
                # z.B. im System-Temp-Verzeichnis.
                tmp_fd, tmp_pfad_str = tempfile.mkstemp(dir=ordner, prefix=f".{ziel}.", suffix=".tmp")
                try:
                    with os.fdopen(tmp_fd, "wb") as tmp_datei:
                        tmp_datei.write(daten)
                    os.replace(tmp_pfad_str, ziel_pfad)
                except BaseException:
                    with suppress(FileNotFoundError):
                        os.remove(tmp_pfad_str)
                    raise
                geschrieben.append(ziel)
    except RuntimeError as exc:
        if "password" in str(exc).lower():
            raise PasswortFalschError("Das Passwort ist falsch.") from exc
        raise
    return geschrieben
