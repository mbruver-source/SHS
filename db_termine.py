"""
Terminübersicht, sicheres Öffnen und Lesen von Termin-Dateien (Desktop).

Aus db.py ausgelagert (11.11.2026, Schichtenaufteilung); db.py bleibt als Fassade und reicht alle
Namen weiter. Code unverändert. Siehe Architektur.md.
"""

from __future__ import annotations
import os
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from db_verbindung import (
    init_db,
    JOURNAL_ENDUNG,
    journal_hat_verweis,
    JOURNAL_VERWEIS_TEXT,
    JournalMitVerweis,
    pruefe_fremdschluessel,
    pruefe_journal_ohne_verweis,
    termin_werte_verletzt,
    _soll_spalten,
)


# --- Terminübersicht -----------------------------------------------------------
#
# Jeder Termin ist eine eigenständige .sqlite-Datei (siehe Moduldocstring). Damit die
# Prüfungsleitung nicht bei jedem Start manuell zu einer Datei navigieren muss, legt das
# Programm neue Termine standardmäßig in einem festen Ordner im Benutzerprofil ab und
# kann diesen Ordner beim Start als Übersichtsliste anzeigen (öffnen/löschen). Termine,
# die anderswo liegen (z. B. auf einem USB-Stick), lassen sich weiterhin über einen
# normalen Datei-öffnen-Dialog einbinden - die Übersicht ist eine Erleichterung, keine
# Einschränkung.

def termine_ordner() -> Path:
    """Standard-Speicherort für Termin-Dateien - wird bei Bedarf angelegt. Liegt im
    Benutzerprofil (nicht neben dem Programm selbst), damit er unabhängig vom
    Installationsort ist und ein Update der Anwendung (siehe Installer) die
    vorhandenen Termine unberührt lässt."""
    ordner = Path.home() / "SHS-Pruefungsprogramm" / "Termine"
    ordner.mkdir(parents=True, exist_ok=True)
    return ordner

@dataclass
class TerminInfo:
    """Eintrag für die Terminübersicht im Startdialog. `vereins_nr` steht zusätzlich zu
    den in der Tabelle angezeigten Spalten bereit, damit sich beim Anlegen eines neuen
    Termins Verein/Vereins-Nr./Ort des zuletzt angelegten Termins vorschlagen lassen
    (Nutzerwunsch 20.09., siehe VeranstaltungsDialog in desktop_dialoge_termin.py und
    StartDialog._neuer_termin in app.py) - erspart die erneute Eingabe, wenn ohnehin derselbe Verein gemeint ist."""
    pfad: str
    dateiname: str
    verein: str | None
    vereins_nr: str | None
    ort: str | None
    datum: str | None
    anzahl_teilnehmer: int
    lesbar: bool  # False = Datei vorhanden, aber nicht als Termin-Datenbank lesbar
    # Marco, 28.09.2026 (Befund 7c): der Verband wird beim neuen Termin ebenfalls
    # vorgeschlagen, die Meldestelle bewusst nicht. None bei alten Termin-Dateien, die die
    # Spalte noch nicht haben (liste_termine öffnet nur lesend, ohne Migration).
    verband: str | None = None
    # UX-Test 02.10.2026, U1: Startnummern-Bereiche werden beim neuen Termin vom letzten
    # Termin übernommen (Marco: "je Termin, mit Übernahme").
    startnummer_bereiche: str | None = None
    # Marco 09.10.2026: die Standardgröße der Bereiche ebenfalls übernehmen.
    startnummer_bereichsgroesse: str | None = None
    # Marco 09.11.2026: die Sätze der Leistungsrichter-Abrechnung ebenfalls übernehmen
    # (die Eingaben je Richter nicht).
    lr_km_satz: str | None = None
    lr_tagespauschale: str | None = None
    # Marco 09.11.2026: eigene Kategorien und Punkte der Checkliste (ohne Haken) ebenfalls.
    checkliste_eigene: str | None = None
    # UX-Test 03.11.2026, X13: davon mit „Keine Teilnahme“ (in anzahl_teilnehmer enthalten).
    anzahl_abgemeldet: int = 0
    # Offene Punkte O2 (Marco 18.10.2026): kurzer Grund bei lesbar=False, wenn er nicht
    # „beschädigt“ ist - GRUND_ZU_GROSS oder GRUND_ZU_AUFWENDIG.
    grund: str | None = None

    @property
    def teilnehmend(self) -> int:
        """Teilnehmende ohne Abgemeldete - dieselbe Zahl wie im Kopfbalken des Termins."""
        return self.anzahl_teilnehmer - self.anzahl_abgemeldet

    @property
    def teilnehmer_anzeige(self) -> str:
        """„16“ bzw. „16 (+1 abgemeldet)“."""
        return (f"{self.teilnehmend} (+{self.anzahl_abgemeldet} abgemeldet)" if self.anzahl_abgemeldet
                else str(self.teilnehmend))

# Schrittgrenze (in Einheiten von _LESE_SCHRITTWEITE SQLite-Arbeitsschritten) für das
# Lesen der Stammdaten einer Termin-Datei in liste_termine(); ein normaler Termin braucht
# nur einen Bruchteil davon.
_LESE_SCHRITTWEITE = 1000

_LESE_HOECHSTSCHRITTE = 1000

# Offene Punkte O2 (Marco 18.10.2026): eigene Termine sind deutlich kleiner als 1 MB. Eine
# größere Datei wird in Terminübersicht und Import nicht gelesen (die Übersicht zeigt sie als
# „ungewöhnlich groß“), beim Öffnen erscheint eine Rückfrage (TerminUngewoehnlichGross).
TERMIN_GROESSE_GRENZE = 50 * 1024 * 1024

GRUND_ZU_GROSS = "zu groß"

GRUND_ZU_AUFWENDIG = "zu aufwendig zu prüfen"

SCHRITTGRENZE_TEXT = (
    "Die Datei ist zu groß bzw. zu aufwendig zu prüfen. Sie stammt vermutlich nicht aus "
    "diesem Programm und wird deshalb nicht gelesen."
)

def _megabyte(groesse: int) -> str:
    """MB mit einer Nachkommastelle (Komma), damit knapp über der Grenze nicht „50 MB“ steht."""
    return f"{groesse / (1024 * 1024):.1f}".replace(".", ",")

class TerminZuGross(sqlite3.DatabaseError):
    """Die Datei ist größer als TERMIN_GROESSE_GRENZE und wird nur lesend nicht geprüft
    (Terminübersicht, Import). Unterklasse von sqlite3.DatabaseError, damit sie dort wie eine
    nicht lesbare Datei behandelt wird; der Text ist für den Nutzer bestimmt."""

def ist_schrittgrenze(exc: BaseException) -> bool:
    """True, wenn die Abfrage an der Begrenzung aus lesen_begrenzen scheiterte (und nicht an
    einer beschädigten Datei)."""
    return isinstance(exc, sqlite3.OperationalError) and "interrupted" in str(exc).lower()

def _groesse_pruefen(pfad: str | Path) -> None:
    groesse = os.path.getsize(pfad)
    if groesse > TERMIN_GROESSE_GRENZE:
        raise TerminZuGross(
            f"Die Datei ist ungewöhnlich groß ({_megabyte(groesse)} MB) und wird deshalb nicht "
            "gelesen. Ein Termin ist sonst deutlich kleiner als 1 MB."
        )

def _ist_wal_ohne_wal_datei(pfad: Path) -> bool:
    """True, wenn der SQLite-Kopf WAL-Modus anzeigt (Bytes 18/19 = 2) und keine "-wal"-Datei
    daneben liegt. Lesefehler zählen als False (dann öffnet SQLite wie bisher und meldet selbst)."""
    try:
        with open(pfad, "rb") as datei:
            kopf = datei.read(20)
        if len(kopf) < 20 or kopf[18] != 2 or kopf[19] != 2:
            return False
        return not os.path.exists(str(pfad) + "-wal")
    except OSError:
        return False

def oeffne_termin_lesend(pfad: str | Path) -> sqlite3.Connection:
    """Öffnet eine Termin-Datei nur lesend (ohne init_db: keine Migration, kein Schreiben).
    Der Pfad wird als korrekt kodierte file:-URI übergeben, damit Zeichen wie "#" oder "%"
    im Datei- oder Ordnernamen nicht als URI-Bestandteile gelesen werden. Bewusst ohne
    Authority-Teil (nicht Path.as_uri()), weil SQLite "file://server/..." ablehnt -
    UNC-Pfade (\\\\server\\freigabe\\...) werden als "file:////server/..." übergeben.

    Eine fremde Datei im WAL-Modus ohne "-wal" daneben wird mit immutable=1 geöffnet: sonst
    legt SQLite auch beim nur lesenden Zugriff "-wal"/"-shm" an und lässt sie liegen (OFFEN.md
    B6, 19.10.2026). Liegt eine "-wal" daneben, muss ihr Inhalt mitgelesen werden - dann wie
    bisher. Eigene Termin-Dateien laufen mit Rollback-Journal und sind nie betroffen.
    Restrisiko: immutable liest ohne Sperre - öffnet ein fremdes Werkzeug die Datei genau
    während des Lesens und schreibt per Checkpoint in die Hauptdatei, kann ein Mischstand
    oder SQLITE_CORRUPT entstehen (von Marco am 19.10.2026 akzeptiert, OFFEN.md C34).

    Liegt neben der Datei ein Journal mit Verweis auf eine weitere Datei, wird sie nicht
    geöffnet (JournalMitVerweis, Sicherheitskorrektur D-2)."""
    pruefe_journal_ohne_verweis(pfad)
    posix = str(Path(pfad).absolute()).replace("\\", "/")
    if posix.startswith("//"):
        posix = "//" + posix
    elif not posix.startswith("/"):
        posix = "/" + posix
    uri = "file:" + quote(posix, safe="/:") + "?mode=ro"
    if _ist_wal_ohne_wal_datei(Path(pfad)):
        uri += "&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def _text_oder_none(wert) -> str | None:
    """Wert aus einer fremden Termin-Datei für die Terminübersicht als Text (None bleibt None)."""
    return None if wert is None else str(wert)

def lesen_begrenzen(conn: sqlite3.Connection) -> None:
    """Begrenzt die Arbeit, die SQLite auf dieser (fremden) Verbindung leisten darf - danach
    bricht die laufende Abfrage mit sqlite3.OperationalError ab. Mit
    conn.set_progress_handler(None, 0) wieder aufheben."""
    schritte = [0]

    def _begrenzen() -> int:
        schritte[0] += 1
        return 1 if schritte[0] > _LESE_HOECHSTSCHRITTE else 0

    conn.set_progress_handler(_begrenzen, _LESE_SCHRITTWEITE)

def pruefe_termin_aufbau(conn: sqlite3.Connection) -> None:
    """Wirft sqlite3.DatabaseError, wenn die Datei nicht wie eine Termin-Datei aufgebaut
    ist: veranstaltung und teilnehmer müssen gewöhnliche Tabellen sein, keine Tabelle darf
    berechnete Spalten haben, und die Datei darf keine Fremdschlüssel enthalten, die das Programm
    nicht selbst anlegt (D-7)."""
    tabellen = [zeile[0] for zeile in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    if not {"veranstaltung", "teilnehmer"} <= set(tabellen):
        raise sqlite3.DatabaseError("keine Termin-Datei")
    for tabelle in tabellen:
        # Spalte "hidden" in table_xinfo: 2/3 = berechnete (GENERATED) Spalte. Name als
        # Parameter - er stammt aus der fremden Datei.
        if any(zeile[6] in (2, 3) for zeile in conn.execute("SELECT * FROM pragma_table_xinfo(?)", (tabelle,))):
            raise sqlite3.DatabaseError("keine Termin-Datei")
    pruefe_fremdschluessel(conn)  # D-7: keine Fremdschlüssel-Aktionen, die das Programm nicht kennt

class KopieMitFremdobjekten(sqlite3.DatabaseError):
    """Die Datei enthält Ansichten oder Trigger, die das Programm nie anlegt (Sicherheitskorrektur
    D-6); der Text ist für den Nutzer bestimmt."""

def pruefe_ohne_fremdobjekte(conn: sqlite3.Connection) -> None:
    """Wirft KopieMitFremdobjekten, wenn die Datei Ansichten oder Trigger enthält. Eigene
    Termin-Dateien haben nie welche (init_db entfernt sie); eine Ansicht kann beim Lesen mehr
    Daten erzeugen, als die Datei groß ist."""
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type IN ('view', 'trigger') LIMIT 1").fetchone():
        raise KopieMitFremdobjekten(
            "Die Kopie enthält Ansichten oder Trigger, die das Programm nie anlegt, und wird deshalb nicht gelesen."
        )

def termin_lesend_pruefen(pfad: str | Path, ohne_fremdobjekte: bool = False) -> sqlite3.Connection:
    """Öffnet eine fremde Termin-Datei nur lesend und prüft ihren Aufbau - gemeinsame
    Reihenfolge für Terminübersicht und Termin-Import (Abschluss-QS 15.10.2026, A19c;
    termin_oeffnen folgt ihr ebenso, erlaubt aber zusätzlich eine Datei ohne Tabellen):
    lesend öffnen, Arbeit begrenzen, Aufbau prüfen. Die Begrenzung bleibt
    gesetzt (aufheben mit conn.set_progress_handler(None, 0)). Ein liegengebliebenes Journal
    spielt der Aufrufer vorher zurück oder nicht; ohne Zurückspielen scheitert das Öffnen.
    Bei einem Fehler wird die Verbindung geschlossen. Eine Datei über
    TERMIN_GROESSE_GRENZE ergibt TerminZuGross (offene Punkte O2). `ohne_fremdobjekte`: Dateien mit
    Ansichten oder Triggern werden abgelehnt (KopieMitFremdobjekten; die Dialoge für Kopien)."""
    _groesse_pruefen(pfad)
    conn = oeffne_termin_lesend(pfad)
    try:
        lesen_begrenzen(conn)
        pruefe_termin_aufbau(conn)
        if ohne_fremdobjekte:
            pruefe_ohne_fremdobjekte(conn)
    except BaseException:
        conn.close()
        raise
    return conn

def termin_unversehrt_pruefen(conn: sqlite3.Connection) -> None:
    """PRAGMA quick_check auf einer Verbindung aus termin_lesend_pruefen: findet auch
    beschädigte Seiten, an denen Aufbauprüfung und erste Abfragen noch vorbeikommen. Wirft
    sqlite3.DatabaseError (Text mit „malformed“, also Klartext „beschädigt“)."""
    if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise sqlite3.DatabaseError("database disk image is malformed (quick_check)")

def _termin_info_lesen(pfad: Path) -> TerminInfo:
    with closing(termin_lesend_pruefen(pfad)) as conn:
        v = conn.execute("SELECT * FROM veranstaltung WHERE id = 1").fetchone()
        anzahl = int(conn.execute("SELECT COUNT(*) FROM teilnehmer").fetchone()[0])
        # UX-Test 03.11.2026, X13: Abgemeldete getrennt zählen (der Kopfbalken zählt nur die
        # Teilnehmenden). Alte Dateien ohne die Spalte werden hier nur lesend geöffnet.
        spalten = {zeile[1] for zeile in conn.execute("PRAGMA table_info(teilnehmer)").fetchall()}
        abgemeldet = int(conn.execute(
            "SELECT COUNT(*) FROM teilnehmer WHERE COALESCE(keine_teilnahme, 0) <> 0").fetchone()[0]
        ) if "keine_teilnahme" in spalten else 0

    def feld(name: str) -> str | None:
        return _text_oder_none(v[name]) if v is not None and name in v.keys() else None

    return TerminInfo(
        pfad=str(pfad),
        dateiname=pfad.name,
        verein=feld("verein"),
        vereins_nr=feld("vereins_nr"),
        ort=feld("ort"),
        datum=feld("datum"),
        anzahl_teilnehmer=anzahl,
        anzahl_abgemeldet=abgemeldet,
        lesbar=True,
        verband=feld("verband"),
        startnummer_bereiche=feld("startnummer_bereiche"),
        startnummer_bereichsgroesse=feld("startnummer_bereichsgroesse"),
        lr_km_satz=feld("lr_km_satz"),
        lr_tagespauschale=feld("lr_tagespauschale"),
        checkliste_eigene=feld("checkliste_eigene"),
    )

class TerminNichtOeffenbar(Exception):
    """Die Datei lässt sich nicht als Termin öffnen; der Text ist für den Nutzer bestimmt."""

class TerminUngewoehnlichGross(TerminNichtOeffenbar):
    """termin_oeffnen ohne groesse_bestaetigt bei einer Datei über TERMIN_GROESSE_GRENZE: der
    Aufrufer fragt nach und öffnet bei Ja mit groesse_bestaetigt=True erneut (offene Punkte
    O2). Unterklasse, damit ein Aufrufer ohne Rückfrage wenigstens die Meldung zeigt."""

    def __init__(self, groesse: int):
        self.megabyte = _megabyte(groesse)
        super().__init__(
            f"Die Termin-Datei ist ungewöhnlich groß ({self.megabyte} MB). Ein Termin ist sonst "
            "deutlich kleiner als 1 MB."
        )

def _journal_zurueckspielen(pfad) -> None:
    """Liegt neben der Datei noch ein Rollback-Journal (Absturz oder Stromausfall mitten im
    Speichern), lässt sich die Datei nur lesend nicht öffnen. Ein kurzes Öffnen mit
    Schreibrecht lässt SQLite den angefangenen Vorgang zurückrollen - dabei läuft kein Code
    aus der Datei. Danach sind die zuletzt gespeicherten Daten wieder lesbar
    (Desktop-Prüfung 14.10.2026).

    Ein Journal mit Verweis auf eine weitere Datei wird nie zurückgespielt (Sicherheitskorrektur
    D-2); die Datei lässt sich dann nicht lesen und erscheint als nicht lesbar."""
    journal = f"{pfad}{JOURNAL_ENDUNG}"
    if not os.path.exists(journal) or journal_hat_verweis(journal):
        return
    try:
        with closing(sqlite3.connect(str(pfad))) as conn:
            conn.execute("PRAGMA schema_version").fetchone()
    except sqlite3.Error:
        pass

_UNBEKANNTE_WERTE_TEXT = (
    "Die Termin-Datei enthält Werte, die das Programm nicht kennt (z. B. eine unbekannte "
    "Prüfungsart, Leistungsklasse oder Punktzahl) oder ihr fehlen Spalten. Sie stammt "
    "vermutlich nicht aus diesem Programm oder wurde verändert und wird deshalb nicht geöffnet."
)

def _termin_werte_pruefen(conn: sqlite3.Connection) -> None:
    """Plausibilitätsprüfung beim Öffnen (Desktop-Prüfung 14.10.2026, Teil 7 Nr. 4 und
    Einordnung): fehlende Spalten oder Werte außerhalb der erlaubten Bereiche ließen sonst
    den Aufbau der Reiter oder einzelne Ausgaben mitten drin scheitern. Vergleiche immer
    binär und mit Typprüfung, damit fremde Spaltendefinitionen (Sortierregel, Datentyp)
    nichts durchlassen."""
    for tabelle, soll in _soll_spalten().items():
        ist = {z[1] for z in conn.execute(f'PRAGMA table_info("{tabelle}")')}
        if not soll <= ist:
            raise TerminNichtOeffenbar(_UNBEKANNTE_WERTE_TEXT)
    # Die Abfragen selbst stehen in db_verbindung.termin_werte_verletzt (seit D-6 gemeinsam mit dem
    # Zurückholen aus einer Kopie genutzt).
    if termin_werte_verletzt(conn):
        raise TerminNichtOeffenbar(_UNBEKANNTE_WERTE_TEXT)

def termin_oeffnen(pfad: str, groesse_bestaetigt: bool = False) -> sqlite3.Connection:
    """Öffnet einen Termin für das Hauptfenster - mit Prüfungen (Desktop-Prüfung 14.10.2026,
    Teil 7 Nr. 4; eine fehlende Datei ergibt TerminNichtOeffenbar statt eines neuen, leeren
    Termins). Die ersten laufen nur lesend, bevor die Datei beschrieben wird; die
    Wertebereiche werden nach init_db geprüft (eine dann abgelehnte Datei hat also schon das
    aktuelle Schema):
    - keine SQLite-Datei oder beschädigt -> TerminNichtOeffenbar;
    - SQLite-Datei eines anderen Programms (ohne Termin-Tabellen) -> TerminNichtOeffenbar,
      statt ihr ungefragt das Schema hinzuzufügen; eine leere Datei ist erlaubt (neuer Termin);
    - berechnete Spalten werden nicht übernommen;
    - nach init_db eine Schreibprobe (PRAGMA user_version), damit ein schreibgeschützter
      Termin sofort auffällt und nicht erst beim ersten Speichern (Marcos Entscheidung
      14.10.2026; der Änderungszeitstempel der Datei ändert sich dabei);
    - Plausibilitätsprüfung der Wertebereiche.
    Offene Punkte O2 (Marco 18.10.2026): über TERMIN_GROESSE_GRENZE ohne groesse_bestaetigt
    -> TerminUngewoehnlichGross (Rückfrage beim Aufrufer); scheitert die lesende Prüfung an
    der Schrittgrenze, nennt die Meldung das statt „beschädigt“. Mit groesse_bestaetigt
    entfällt die Schrittgrenze - sonst scheiterte eine große Datei trotz „Ja“ meist doch an
    ihr (Marco 19.10.2026, QS O11)."""
    if not os.path.exists(pfad):
        # Abschluss-QS 15.10.2026 (K-3): eine inzwischen gelöschte/verschobene Datei nicht still
        # als leeren Termin neu anlegen - neue Termine legt StartDialog._neuer_termin an.
        raise TerminNichtOeffenbar("Die Termin-Datei wurde nicht gefunden (gelöscht oder verschoben?).")
    try:
        pruefe_journal_ohne_verweis(pfad)  # D-2: vor jedem Öffnen mit Schreibrecht
    except JournalMitVerweis as exc:
        raise TerminNichtOeffenbar(JOURNAL_VERWEIS_TEXT) from exc
    groesse = os.path.getsize(pfad)
    if groesse > TERMIN_GROESSE_GRENZE and not groesse_bestaetigt:
        raise TerminUngewoehnlichGross(groesse)
    if groesse > 0:
        _journal_zurueckspielen(pfad)
        try:
            # Gleiche Reihenfolge wie termin_lesend_pruefen; nur eine SQLite-Datei ganz ohne
            # Tabellen ist hier erlaubt (neuer Termin), deshalb die Aufbauprüfung nur mit Tabellen.
            with closing(oeffne_termin_lesend(pfad)) as pruef:
                if not groesse_bestaetigt:
                    lesen_begrenzen(pruef)
                if pruef.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' LIMIT 1").fetchone():
                    pruefe_termin_aufbau(pruef)
                if pruef.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise sqlite3.DatabaseError("quick_check")
        except sqlite3.DatabaseError as exc:
            if ist_schrittgrenze(exc):
                raise TerminNichtOeffenbar(SCHRITTGRENZE_TEXT) from exc
            raise TerminNichtOeffenbar(
                "Die Datei ist keine Termin-Datei des SHS-Prüfungsprogramms oder sie ist beschädigt."
            ) from exc
    try:
        conn = init_db(pfad)
    except sqlite3.Error as exc:
        if "readonly" in str(exc).lower():
            raise TerminNichtOeffenbar(
                "Die Termin-Datei ist schreibgeschützt (z. B. schreibgeschützter USB-Stick oder "
                "Dateieigenschaften „Schreibgeschützt“) und müsste beim Öffnen angepasst werden. "
                "Bitte die Datei an einen beschreibbaren Ort kopieren und dort öffnen."
            ) from exc
        raise
    try:
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        conn.execute(f"PRAGMA user_version = {version}")
        _termin_werte_pruefen(conn)
    except sqlite3.OperationalError as exc:
        conn.close()
        if "readonly" in str(exc).lower():
            raise TerminNichtOeffenbar(
                "Die Termin-Datei ist schreibgeschützt (z. B. schreibgeschützter USB-Stick oder "
                "Dateieigenschaften „Schreibgeschützt“). Ergebnisse ließen sich nicht speichern - "
                "bitte die Datei an einen beschreibbaren Ort kopieren und dort öffnen."
            ) from exc
        raise
    except BaseException:
        conn.close()
        raise
    return conn

def liste_termine(ordner: Path | None = None) -> list[TerminInfo]:
    """Listet alle Termin-Dateien (*.sqlite) in `ordner` (Standard: termine_ordner())
    mit ihren Stammdaten, neueste zuerst. Eine beschädigte oder fremde Datei lässt die
    Übersicht nicht abstürzen, sondern taucht mit lesbar=False auf - jede Datei wird für
    sich und nur lesend geöffnet (Desktop-Prüfung 14.10.2026)."""
    ordner = ordner or termine_ordner()
    ergebnisse: list[TerminInfo] = []
    for pfad in sorted(ordner.glob("*.sqlite")):
        _journal_zurueckspielen(pfad)
        try:
            ergebnisse.append(_termin_info_lesen(pfad))
        except (sqlite3.Error, IndexError, KeyError, TypeError, ValueError, OverflowError) as exc:
            if isinstance(exc, TerminZuGross):
                grund = GRUND_ZU_GROSS
            elif ist_schrittgrenze(exc):
                grund = GRUND_ZU_AUFWENDIG
            else:
                grund = None
            ergebnisse.append(TerminInfo(
                pfad=str(pfad), dateiname=pfad.name, verein=None, vereins_nr=None, ort=None,
                datum=None, anzahl_teilnehmer=0, lesbar=False, grund=grund,
            ))
    ergebnisse.sort(key=lambda t: (t.datum or "", t.dateiname), reverse=True)
    return ergebnisse

_UMSCHRIFT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})

def dateiname_slug(text: str, max_laenge: int = 40) -> str:
    """Text (z. B. Vereinsname) als Teil eines Dateinamens: Umlaute umgeschrieben, alles
    außer Buchstaben/Ziffern als „-“, höchstens `max_laenge` Zeichen. Gemeinsam für den
    Termin- und den Sicherungs-Dateinamen (Desktop-Prüfung 14.10.2026, Teil 2 Nr. 10)."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", (text or "").translate(_UMSCHRIFT)).strip("-")
    return slug[:max_laenge].strip("-")

def dateiname_vorschlagen(verein: str, datum: str) -> str:
    """Schlägt einen Dateinamen für einen neuen Termin aus Verein + Datum vor,
    z. B. '2026-09-19_SGV-Koeppern-e-V.sqlite' für „SGV Köppern e.V.“."""
    slug = dateiname_slug(verein) or "Termin"
    datum_teil = re.sub(r"[^0-9-]", "", datum or "") or "ohne-datum"
    return f"{datum_teil}_{slug}.sqlite"
