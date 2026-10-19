"""Datensicherung: Export/Import aller Termin-Dateien als ZIP, optional passwortgeschützt.

Aus db.py ausgelagert (Codex-Architekturprüfung 27.09.2026). Baut auf db auf
(termine_ordner); db selbst importiert dieses Modul nicht, damit kein Ringimport entsteht.

Nutzt pyzipper (reines Python, keine kompilierten Zusatzabhängigkeiten) statt des
eingebauten zipfile-Moduls, da zipfile zwar passwortgeschützte ZIPs LESEN, aber keine
mit echter (AES-256-)Verschlüsselung SCHREIBEN kann. Ein Backup ohne Passwort wird
trotzdem mit dem einfacheren, garantiert überall (z.B. Windows-Explorer) kompatiblen
zipfile-Modul erzeugt.
"""

from __future__ import annotations

import lzma
import os
import sqlite3
import tempfile
import zipfile
import zlib
from contextlib import contextmanager, suppress
from pathlib import Path

import pyzipper

from db import oeffne_termin_lesend, termine_ordner


class PasswortFalschError(Exception):
    """Ein Sicherungs-ZIP ist passwortgeschützt und das angegebene Passwort fehlt oder
    ist falsch (siehe sicherung_inhalt()/sicherung_wiederherstellen())."""


class TeilweiseWiederhergestelltError(Exception):
    """Das Wiederherstellen ist abgebrochen, nachdem bereits einzelne Termin-Dateien
    ersetzt wurden. `geschrieben` nennt diese Zieldateinamen, `ursache` den eigentlichen
    Fehler (QS-Prüfung 07.10.2026, Befund 3: vorher ging die Liste mit der Ausnahme
    verloren und die Meldung klang, als sei nichts passiert)."""

    def __init__(self, geschrieben: list[str], ursache: BaseException):
        self.geschrieben = list(geschrieben)
        self.ursache = ursache
        super().__init__(
            f"{ursache}\n\nBereits wiederhergestellt (vorheriger Stand ersetzt): "
            + ", ".join(self.geschrieben)
        )


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
    # Desktop-Prüfung 14.10.2026 (Teil 7 Nr. 10): unter Windows ungültige Zeichen und
    # Steuerzeichen ablehnen.
    if any(zeichen in _UNGUELTIGE_ZEICHEN or ord(zeichen) < 32 for zeichen in name):
        return False
    return True


_UNGUELTIGE_ZEICHEN = frozenset(':*?"<>|')


def eindeutigen_dateinamen_finden(
    ordner: Path, gewuenschter_name: str, bereits_vergeben: set[str] | frozenset[str] = frozenset()
) -> str:
    """Hängt bei einem im Ordner bereits vergebenen Dateinamen einen Zähler an (z.B.
    'Termin (2).sqlite'), bis ein noch freier Name gefunden ist - für die Option "als
    Kopie importieren" beim Wiederherstellen einer Sicherung (siehe
    desktop_dialoge._wiederherstellungsziele_planen).

    `bereits_vergeben`: Namen, die noch nicht auf der Platte liegen, aber im selben
    Vorgang schon als Ziel eingeplant sind (Codeprüfung 22.09., G5: enthielt eine
    Sicherung "A.sqlite" und "A (2).sqlite", landeten sonst beide auf "A (2).sqlite" und
    einer überschrieb still den anderen). Siehe auch Sicherheitskorrektur Q-1
    (07.10.2026), Details folgen."""
    ordner = Path(ordner)
    vergeben = {n.casefold() for n in bereits_vergeben}

    def belegt(name: str) -> bool:
        return name.casefold() in vergeben or (ordner / name).exists()

    if not belegt(gewuenschter_name):
        return gewuenschter_name
    ziel = Path(gewuenschter_name)
    stamm, endung = ziel.stem, ziel.suffix
    zaehler = 2
    while belegt(f"{stamm} ({zaehler}){endung}"):
        zaehler += 1
    return f"{stamm} ({zaehler}){endung}"


# Endung der Rücksprung-Datei (Rollback-Journal) neben einer Termin-Datei.
_JOURNAL_ENDUNG = "-journal"


def _momentaufnahme(pfad: Path) -> bytes | None:
    """Stimmiger Stand einer Termin-Datei über die SQLite-Sicherungsfunktion (offene Punkte
    O1, Marco 18.10.2026): Die Quelle wird nur lesend geöffnet, der Stand landet in einer
    Datenbank im Arbeitsspeicher und wird von dort als Bytes geliefert - eine gerade
    laufende, nicht abgeschlossene Schreibtransaktion (z. B. einer zweiten
    Programminstanz) ist nicht enthalten, und es entsteht keine Temp-Datei mit
    Personendaten. None, wenn sich die Datei so nicht lesen lässt (beschädigt, keine
    SQLite-Datei, liegengebliebenes Journal, das nur schreibend zurückgespielt werden
    könnte, gerade von einer anderen Verbindung gesperrt) - dann sichert der Aufrufer die
    Datei roh.

    Die Lesesperre wird vorher mit einer eigenen Abfrage geholt: Connection.backup()
    wiederholt bei einer gesperrten Quelle sonst endlos, und die Sicherung hinge, solange
    eine andere Instanz (oder die eigene Verbindung) schreibt. So gilt die übliche Wartezeit
    der Verbindung, danach kommt ein Fehler und damit die Rohsicherung."""
    try:
        quelle = oeffne_termin_lesend(pfad)
    except sqlite3.Error:
        return None
    try:
        quelle.execute("BEGIN")
        quelle.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
        ziel = sqlite3.connect(":memory:")
        try:
            quelle.backup(ziel)
            return ziel.serialize()
        finally:
            ziel.close()
    except (sqlite3.Error, MemoryError):
        # Auch zu wenig Arbeitsspeicher für die Momentaufnahme: dann eben roh (streamend).
        return None
    finally:
        quelle.close()


def sicherung_erstellen(
    ziel_pfad: str, passwort: str | None = None, nur_dateien: list[str] | None = None, ordner: Path | None = None,
    zusaetzliche: list[str] | None = None, roh_gesichert: list[str] | None = None,
) -> int:
    """Erstellt ein ZIP-Backup der Termin-Dateien aus `ordner` (Standard: termine_ordner()).

    nur_dateien: optionale Liste von Dateinamen (nicht volle Pfade) - falls angegeben,
    werden nur diese gesichert, sonst ALLE *.sqlite-Dateien im Ordner.
    zusaetzliche: volle Pfade weiterer Termin-Dateien außerhalb von `ordner` (der geöffnete
    Termin, Desktop-Prüfung 14.10.2026, Teil 7 Nr. 1). Ist ihr Name im ZIP schon vergeben,
    bekommen sie einen Zähler wie beim Import als Kopie.
    passwort: falls angegeben (nicht leer), wird das ZIP AES-256-verschlüsselt.
    roh_gesichert: optionale Liste, in die die Namen (im ZIP) der Dateien geschrieben
    werden, die sich nicht als Termin lesen ließen und deshalb roh gesichert wurden.
    Gibt die Anzahl der gesicherten Termin-Dateien zurück.
    Wirft ValueError, falls es nichts zu sichern gibt.

    Jede Datei kommt als stimmige Momentaufnahme ins ZIP (siehe _momentaufnahme), nicht als
    Byte-Kopie der gerade geöffneten Datei. Lässt sie sich so nicht lesen, wird sie wie
    bisher roh gesichert, eine daneben liegende Rücksprung-Datei („-journal“) mit - in die
    Quelldatei wird dabei nie geschrieben (Marco 18.10.2026).

    Das ZIP entsteht zuerst als temporäre Datei im Zielordner und ersetzt erst nach dem
    vollständigen Schreiben per os.replace() die Zieldatei (QS-Prüfung 07.10.2026,
    Befund 2: vorher wurde direkt in ziel_pfad geschrieben - ein Abbruch, z. B. bei
    vollem USB-Stick, löschte eine gleichnamige ältere Sicherung und hinterließ ein
    gültig aussehendes ZIP mit nur einem Teil der Termine).
    """
    ordner = ordner or termine_ordner()
    dateien = sorted(p for p in ordner.glob("*.sqlite") if p.is_file())
    if nur_dateien is not None:
        gewaehlt = set(nur_dateien)
        dateien = [p for p in dateien if p.name in gewaehlt]
    eintraege = [(datei, datei.name) for datei in dateien]
    vergeben = {datei.name for datei in dateien}
    for pfad in zusaetzliche or []:
        pfad = Path(pfad)
        if any(_gleiche_datei(pfad, datei) for datei in dateien):
            continue
        name = eindeutigen_dateinamen_finden(ordner, _zip_name_fuer(pfad.name), bereits_vergeben=vergeben)
        vergeben.add(name)
        eintraege.append((pfad, name))
    if not eintraege:
        raise ValueError("Es gibt keine Termine zum Sichern.")

    ziel = Path(ziel_pfad)
    # Wie in sicherung_wiederherstellen(): im selben Ordner, damit os.replace() atomar ist.
    tmp_fd, tmp_pfad_str = tempfile.mkstemp(dir=ziel.parent, prefix=f".{ziel.name}.", suffix=".tmp")
    os.close(tmp_fd)
    roh: list[str] = []

    def eintraege_schreiben(zf) -> None:
        for datei, name in eintraege:
            daten = _momentaufnahme(datei)
            if daten is not None:
                zf.writestr(name, daten)
                continue
            zf.write(datei, arcname=name)
            journal = Path(f"{datei}{_JOURNAL_ENDUNG}")
            if journal.is_file():
                zf.write(journal, arcname=f"{name}{_JOURNAL_ENDUNG}")
            roh.append(name)

    try:
        if passwort:
            with pyzipper.AESZipFile(
                tmp_pfad_str, "w", compression=pyzipper.ZIP_LZMA, encryption=pyzipper.WZ_AES
            ) as zf:
                zf.setpassword(passwort.encode("utf-8"))
                eintraege_schreiben(zf)
        else:
            with zipfile.ZipFile(tmp_pfad_str, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                eintraege_schreiben(zf)
        os.replace(tmp_pfad_str, ziel)
    except BaseException:
        with suppress(FileNotFoundError):
            os.remove(tmp_pfad_str)
        raise
    if roh_gesichert is not None:
        roh_gesichert.extend(roh)
    return len(eintraege)


def _zip_name_fuer(name: str) -> str:
    """Name im ZIP für einen mitgesicherten Termin: endet auf .sqlite und besteht
    _ist_sicherer_dateiname - sonst böte das Wiederherstellen ihn nicht an."""
    if not name.lower().endswith(".sqlite"):
        name += ".sqlite"
    if not _ist_sicherer_dateiname(name):
        name = "".join("_" if z in _UNGUELTIGE_ZEICHEN or ord(z) < 32 else z for z in name)
        if not _ist_sicherer_dateiname(name):
            name = "Termin.sqlite"
    return name


def _gleiche_datei(a: Path, b: Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


_BESCHAEDIGT = (
    "Die Sicherung ist beschädigt: Eine Termin-Datei darin lässt sich nicht fehlerfrei "
    "lesen.\n\nTechnische Angabe: {}"
)


@contextmanager
def _zip_oeffnen(zip_pfad: str, passwort: str | None):
    """Öffnet ein Sicherungs-ZIP zum Lesen, setzt das Passwort und prüft die Obergrenzen
    (S-8). Übersetzt Passwortfehler - auch solche, die erst beim Lesen im with-Block
    auftreten - in PasswortFalschError und ein ungültiges ZIP in ValueError. Gemeinsam für
    sicherung_inhalt() und sicherung_wiederherstellen() (QS-Prüfung 07.10.2026, Befund 4).

    Lässt sich das ZIP öffnen, ein Eintrag aber nicht fehlerfrei lesen (Prüfsummen- oder
    Entpackfehler), lautet die Meldung "beschädigt" statt "keine gültige ZIP-Datei"
    (Marco 07.10.2026, Nachtrag zur Verifikation)."""
    geoeffnet = False
    try:
        with pyzipper.AESZipFile(zip_pfad) as zf:
            geoeffnet = True
            if passwort:
                zf.setpassword(passwort.encode("utf-8"))
            _zip_grenzen_pruefen(zf)
            yield zf
    except NotImplementedError as exc:
        # Teil 7 Nr. 11: Komprimierungs- bzw. Verschlüsselungsverfahren, das zipfile/pyzipper
        # nicht lesen (ZIP aus einem fremden Programm). Vor RuntimeError, deren Unterklasse
        # NotImplementedError ist.
        raise ValueError(
            "Die Sicherung nutzt ein Komprimierungs- oder Verschlüsselungsverfahren, das hier "
            f"nicht unterstützt wird ({exc})."
        ) from exc
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
        if geoeffnet:
            raise ValueError(_BESCHAEDIGT.format(exc)) from exc
        raise ValueError("Das ist keine gültige ZIP-Datei.") from exc
    except (zlib.error, lzma.LZMAError) as exc:
        raise ValueError(_BESCHAEDIGT.format(exc)) from exc


def sicherung_inhalt(zip_pfad: str, passwort: str | None = None) -> list[str]:
    """Liefert die Namen der Termin-Dateien (*.sqlite) in einem Sicherungs-ZIP, ohne sie
    zu entpacken - Grundlage für die Konflikterkennung vor dem eigentlichen
    Wiederherstellen (siehe sicherung_wiederherstellen() und desktop_verwaltung.py).

    Wirft PasswortFalschError, wenn das ZIP passwortgeschützt ist und `passwort` fehlt
    oder falsch ist; ValueError, wenn die Datei kein gültiges ZIP ist oder keine
    Termin-Dateien enthält.
    """
    with _zip_oeffnen(zip_pfad, passwort) as zf:
        # _ist_sicherer_dateiname() filtert Einträge mit Pfadanteilen (z.B.
        # '../../wichtig.sqlite') schon hier heraus, BEVOR sie dem Nutzer in der
        # Konflikt-Auswahl angezeigt werden (siehe Docstring dort).
        namen = [n for n in zf.namelist() if n.lower().endswith(".sqlite") and _ist_sicherer_dateiname(n)]
        if not namen:
            raise ValueError("Das ZIP enthält keine Termin-Dateien (.sqlite).")
        # Erzwingt die Passwortprüfung sofort (Lesen der ersten Datei), statt erst
        # beim eigentlichen Wiederherstellen mittendrin zu scheitern.
        zf.read(namen[0])
    return sorted(namen)


def _beiseitelegen(pfad: Path) -> str:
    """Benennt `pfad` in eine versteckte Datei im selben Ordner um und gibt deren Pfad zurück."""
    fd, beiseite = tempfile.mkstemp(dir=pfad.parent, prefix=f".{pfad.name}.", suffix=".alt")
    os.close(fd)
    try:
        os.replace(pfad, beiseite)
    except BaseException:
        with suppress(OSError):
            os.remove(beiseite)
        raise
    return beiseite


def _termin_ersetzen(ordner: Path, ziel: str, tmp_termin: str, tmp_journal: str | None) -> None:
    """Ersetzt `ordner/ziel` samt Rücksprung-Datei als Einheit (Marco 19.10.2026).

    Eine alte „<ziel>-journal“ wird immer entfernt - SQLite würde sie sonst beim nächsten
    Öffnen auf die neue Datei zurückspielen; mit `tmp_journal` kommt die aus dem ZIP an ihre
    Stelle. Die alten Dateien werden zuerst beiseitegelegt. Scheitert ein Schritt, kommen sie
    zurück und eine schon ersetzte neue Termin-Datei wird wieder entfernt: dann bleibt der
    bisherige Stand vollständig erhalten."""
    termin = ordner / ziel
    journal = ordner / f"{ziel}{_JOURNAL_ENDUNG}"
    beiseite: list[tuple[str, Path]] = []
    termin_ersetzt = False
    try:
        if journal.exists():
            beiseite.append((_beiseitelegen(journal), journal))
        # Ohne Journal ersetzt os.replace() die Termin-Datei atomar; mit Journal sind es zwei
        # Schritte, deshalb muss die alte Termin-Datei für den Rückweg erhalten bleiben.
        if tmp_journal is not None and termin.exists():
            beiseite.append((_beiseitelegen(termin), termin))
        os.replace(tmp_termin, termin)
        termin_ersetzt = True
        if tmp_journal is not None:
            os.replace(tmp_journal, journal)
    except BaseException:
        if termin_ersetzt and not any(original == termin for _, original in beiseite):
            with suppress(OSError):
                os.remove(termin)
        for alt, original in reversed(beiseite):
            os.replace(alt, original)
        raise
    for alt, _original in beiseite:
        with suppress(OSError):
            os.remove(alt)


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

    Enthält das ZIP zu einem gewählten Termin eine Rücksprung-Datei („<name>-journal“,
    siehe sicherung_erstellen: roh gesicherte Datei), wird sie als „<Zielname>-journal“
    mit zurückgeschrieben (offene Punkte O1, 19.10.2026) - direkt nach der Termin-Datei.
    Sie erscheint nicht in der Rückgabe. Enthält das ZIP keine, wird eine alte
    „<Zielname>-journal“ im Zielordner (etwa nach einem Absturz) beim Ersetzen gelöscht.
    Termin-Datei und Rücksprung-Datei werden als Einheit ersetzt (_termin_ersetzen): scheitert
    ein Schritt, bleibt der bisherige Stand dieses Termins samt Journal erhalten (Marco
    19.10.2026).

    Jede Datei wird ATOMAR geschrieben (temporäre Datei im selben Zielordner, danach
    os.replace()) statt direkt in die Zieldatei - bricht das Schreiben mittendrin ab
    (Absturz, Stromausfall, volle Platte während GENAU dieser Datei), bleibt entweder
    die alte Datei vollständig unverändert oder die neue vollständig geschrieben zurück,
    nie eine abgeschnittene/korrupte Datei mit einem dabei unwiederbringlich verlorenen
    bisherigen Terminstand (QS-Review 19./20.09.: vorher direktes Path.write_bytes() auf
    die Zieldatei selbst, ohne diese Absicherung).

    Zweiphasig (QS-Prüfung 07.10.2026, Befund 3): Zuerst werden ALLE gewählten Einträge
    in temporäre Dateien entpackt - Lese-, Passwort-, Prüfsummen- und Platzfehler treten
    hier auf, bevor irgendein vorhandener Termin ersetzt ist. Erst danach folgen die
    os.replace()-Aufrufe. Scheitert einer davon (z. B. weil die Datei unter Windows
    gesperrt ist), nennt TeilweiseWiederhergestelltError die schon ersetzten Termine.

    Wirft PasswortFalschError bei fehlendem oder falschem Passwort; ValueError bei einem
    ungültigen ZIP, überschrittenen Obergrenzen (S-8) oder einem unsicheren bzw.
    doppelten Zieldateinamen;
    TeilweiseWiederhergestelltError, wenn nach dem ersten Ersetzen ein Fehler auftritt.
    Andere Fehler (z. B. OSError) vor dem ersten Ersetzen werden unverändert
    weitergereicht - dann ist nichts geändert.
    """
    ordner = ordner or termine_ordner()
    # Zweite, unabhängige Absicherung gegen Path Traversal (siehe
    # _ist_sicherer_dateiname()) - auch wenn sicherung_inhalt() unsichere Namen bereits
    # vorher herausfiltert, verlässt sich diese Funktion hier nicht darauf, dass jeder
    # Aufrufer das auch tatsächlich vorschaltet. Ebenso werden doppelte Zielnamen
    # abgelehnt.
    gesehen: set[str] = set()
    for ziel in entscheidungen.values():
        if not _ist_sicherer_dateiname(ziel):
            raise ValueError(f"Unsicherer Zieldateiname: {ziel!r}")
        if ziel.casefold() in gesehen:
            raise ValueError(f"Zieldateiname mehrfach vergeben: {ziel!r}")
        gesehen.add(ziel.casefold())

    # (Zieldateiname, temporäre Termin-Datei, temporäre Rücksprung-Datei oder None)
    vorbereitet: list[tuple[str, str, str | None]] = []
    temporaere: list[str] = []
    try:
        with _zip_oeffnen(zip_pfad, passwort) as zf:
            vorhandene_eintraege = set(zf.namelist())

            def vorbereiten(quelle: str, ziel: str) -> str:
                daten = zf.read(quelle)
                # os.replace() ist nur innerhalb DESSELBEN Dateisystems atomar - die
                # temporäre Datei muss deshalb im selben Ordner liegen wie das Ziel, nicht
                # z.B. im System-Temp-Verzeichnis.
                tmp_fd, tmp_pfad_str = tempfile.mkstemp(dir=ordner, prefix=f".{ziel}.", suffix=".tmp")
                temporaere.append(tmp_pfad_str)
                with os.fdopen(tmp_fd, "wb") as tmp_datei:
                    tmp_datei.write(daten)
                return tmp_pfad_str

            for quelle, ziel in entscheidungen.items():
                tmp_termin = vorbereiten(quelle, ziel)
                # Roh gesicherte Datei mit Rücksprung-Datei (siehe sicherung_erstellen):
                # beide gehören zusammen, sonst ist der Stand womöglich widersprüchlich.
                # Der Name leitet sich aus dem oben geprüften Zielnamen ab.
                tmp_journal = None
                if f"{quelle}{_JOURNAL_ENDUNG}" in vorhandene_eintraege:
                    tmp_journal = vorbereiten(f"{quelle}{_JOURNAL_ENDUNG}", f"{ziel}{_JOURNAL_ENDUNG}")
                vorbereitet.append((ziel, tmp_termin, tmp_journal))

        geschrieben: list[str] = []
        for ziel, tmp_termin, tmp_journal in vorbereitet:
            try:
                _termin_ersetzen(ordner, ziel, tmp_termin, tmp_journal)
            except Exception as exc:
                if geschrieben:
                    raise TeilweiseWiederhergestelltError(geschrieben, exc) from exc
                raise
            geschrieben.append(ziel)
    finally:
        # Nach Erfolg sind alle temporären Dateien umbenannt; nach einem Fehler werden
        # die übrigen hier entfernt.
        for tmp_pfad_str in temporaere:
            with suppress(FileNotFoundError):
                os.remove(tmp_pfad_str)
    return geschrieben
