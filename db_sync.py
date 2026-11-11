"""
Austausch zwischen einer SQLite-Termin-Datei (Desktop) und PostgreSQL (Web).

Aus db.py ausgelagert (11.11.2026, Schichtenaufteilung); db.py bleibt als Fassade und reicht alle
Namen weiter. Code unverändert. Siehe Architektur.md.
"""

from __future__ import annotations
import sqlite3
from contextlib import suppress
from dataclasses import dataclass, field

from db_ergebnisse import (
    eintragen_ergebnis,
    get_ergebnis,
    leistungsklasse_label,
)
from db_stamm import (
    add_teilnehmer,
    get_veranstaltung,
    list_teilnehmer,
    NeuerTeilnehmer,
    set_veranstaltung,
)
from db_verbindung import (
    DISZIPLIN_SPALTEN,
)
from db_web import (
    erstelle_termin_postgres,
    liste_termine_postgres,
    loesche_termin_postgres,
    oeffne_termin_postgres,
    TerminInfoPostgres,
    _setze_termin_suchpfad,
)


# --- Austausch zwischen einer SQLite-Termin-Datei (Desktop) und einem PostgreSQL-
# Termin-Schema (Web) ---------------------------------------------------------
#
# Für die geplante V1 der Web-Version ("nur Ergebniseingabe", siehe Chatverlauf) wird ein
# Termin weiterhin ganz normal in der Desktop-Version angelegt/geplant (Teilnehmer,
# Zeitplan, ...) und erst VOR dem Prüfungstag als eigener PostgreSQL-Termin
# "veröffentlicht" (exportiere_termin_nach_postgres) - danach tragen mehrere Richter
# gleichzeitig über die Web-Oberfläche Ergebnisse ein. NACH der Prüfung werden diese
# Ergebnisse zurück in dieselbe SQLite-Datei geholt (importiere_ergebnisse_aus_postgres),
# damit PDF-Export/Auswertung/Zeitplan wie bisher in der Desktop-Version weiterlaufen -
# die PostgreSQL-Datenbank ist also nur für den Prüfungstag selbst "die Wahrheit", davor
# und danach bleibt es die SQLite-Datei. Siehe sync_termin.py für das Kommandozeilen-
# Werkzeug, das diese beiden Funktionen aufruft.
#
# Die eigentliche Kopierlogik (kopiere_termin_daten/importiere_ergebnisse_nach_startnummer)
# ist bewusst dialektunabhängig gehalten - sie arbeitet ausschließlich über bereits
# vorhandene, für beide Datenbanken getestete Funktionen (add_teilnehmer, eintragen_ergebnis,
# ...) bzw. portables SQL. Dadurch lässt sie sich, genau wie die übrige Kernlogik dieses
# Moduls, vollständig mit zwei SQLite-Verbindungen automatisiert testen, ohne dass dafür
# psycopg2 installiert sein müsste (siehe TestTerminSync in test_db.py) - nur die dünnen
# Wrapper-Funktionen exportiere_termin_nach_postgres/importiere_ergebnisse_aus_postgres
# selbst binden sich an eine echte PostgreSQL-Verbindung.


def kopiere_termin_daten(quelle_conn, ziel_conn) -> dict[int, int]:
    """Kopiert Veranstaltungsdaten und alle Teilnehmer (inkl. bereits vorhandener
    Ergebnisse, falls schon welche eingetragen waren) von quelle_conn nach ziel_conn.

    ziel_conn sollte auf ein leeres Schema/eine leere Datenbank zeigen (z. B. direkt nach
    erstelle_termin_postgres()) - vorhandene Teilnehmer dort werden NICHT gelöscht, die
    kopierten kommen einfach hinzu. Liefert die Zuordnung alte Teilnehmer-ID (in
    quelle_conn) -> neue Teilnehmer-ID (in ziel_conn)."""
    veranstaltung = get_veranstaltung(quelle_conn)
    if veranstaltung:
        set_veranstaltung(
            ziel_conn,
            verein=veranstaltung["verein"],
            datum=veranstaltung["datum"],
            ort=veranstaltung.get("ort"),
            vereins_nr=veranstaltung.get("vereins_nr"),
            pruefungsnummer=veranstaltung.get("pruefungsnummer"),
            wertungsrichter_1=veranstaltung.get("wertungsrichter_1"),
            wertungsrichter_2=veranstaltung.get("wertungsrichter_2"),
            wertungsrichter_3=veranstaltung.get("wertungsrichter_3"),
            wertungsrichter_4=veranstaltung.get("wertungsrichter_4"),
            wertungsrichter_5=veranstaltung.get("wertungsrichter_5"),
            pruefungsleiter=veranstaltung.get("pruefungsleiter"),
            pruefungsgebuehr_ed=veranstaltung.get("pruefungsgebuehr_ed"),
            pruefungsgebuehr_dk=veranstaltung.get("pruefungsgebuehr_dk"),
            zeitplan_start=veranstaltung.get("zeitplan_start"),
            verband=veranstaltung.get("verband"),
            meldestelle=veranstaltung.get("meldestelle"),
            angebotene_pruefungen=veranstaltung.get("angebotene_pruefungen"),
            startnummer_bereiche=veranstaltung.get("startnummer_bereiche"),
            dk_mindestabstand=veranstaltung.get("dk_mindestabstand"),
            startnummer_bereichsgroesse=veranstaltung.get("startnummer_bereichsgroesse"),
            lr_km_satz=veranstaltung.get("lr_km_satz"),
            lr_tagespauschale=veranstaltung.get("lr_tagespauschale"),
            lr_abrechnung=veranstaltung.get("lr_abrechnung"),
            checkliste=veranstaltung.get("checkliste"),
            checkliste_eigene=veranstaltung.get("checkliste_eigene"),
        )

    id_zuordnung: dict[int, int] = {}
    for alt in list_teilnehmer(quelle_conn, nur_teilnehmende=True):
        neu = NeuerTeilnehmer(
            nachname=alt["nachname"], vorname=alt["vorname"], rufname_hund=alt["rufname_hund"],
            art=alt["art"], stufe=alt["stufe"], disziplin=alt["disziplin"],
            verein=alt.get("verein"), zwingername=alt.get("zwingername"), geschlecht=alt.get("geschlecht"),
            schulterhoehe_cm=alt.get("schulterhoehe_cm"), chip_nr=alt.get("chip_nr"),
            startnummer=alt.get("startnummer"),
            gegenstand_1=alt.get("gegenstand_1"), gegenstand_2=alt.get("gegenstand_2"),
            gegenstand_3=alt.get("gegenstand_3"),
            gegenstand_1_disziplin=alt.get("gegenstand_1_disziplin"),
            gegenstand_2_disziplin=alt.get("gegenstand_2_disziplin"),
            gegenstand_3_disziplin=alt.get("gegenstand_3_disziplin"),
            bezahlt=bool(alt.get("bezahlt")),
            verband=alt.get("verband"), mitgliedsnummer=alt.get("mitgliedsnummer"), wurftag=alt.get("wurftag"),
            strasse=alt.get("strasse"), hausnummer=alt.get("hausnummer"), plz=alt.get("plz"), ort=alt.get("ort"),
            email=alt.get("email"), telefon=alt.get("telefon"),
            rasse=alt.get("rasse"), tollwutimpfung_bis=alt.get("tollwutimpfung_bis"),
            geburtsdatum=alt.get("geburtsdatum"),
            halter_vorname=alt.get("halter_vorname"), halter_nachname=alt.get("halter_nachname"),
            halter_strasse=alt.get("halter_strasse"), halter_hausnummer=alt.get("halter_hausnummer"),
            halter_plz=alt.get("halter_plz"), halter_ort=alt.get("halter_ort"),
            halter_mitgliedsverein=alt.get("halter_mitgliedsverein"),
            halter_mitgliedsnummer=alt.get("halter_mitgliedsnummer"), halter_lu_nr=alt.get("halter_lu_nr"),
        )
        neue_id = add_teilnehmer(ziel_conn, neu)
        id_zuordnung[alt["id"]] = neue_id

        alte_ergebnisse = get_ergebnis(quelle_conn, alt["id"])
        if alte_ergebnisse:
            for disziplin, (spalte_suche, spalte_anzeige) in DISZIPLIN_SPALTEN.items():
                suche, anzeige = alte_ergebnisse[spalte_suche], alte_ergebnisse[spalte_anzeige]
                if suche is not None or anzeige is not None:
                    eintragen_ergebnis(ziel_conn, neue_id, disziplin, suche, anzeige)

    return id_zuordnung

def exportiere_termin_nach_postgres(sqlite_conn: sqlite3.Connection, postgres_conn) -> TerminInfoPostgres:
    """Veröffentlicht einen bestehenden SQLite-Termin (Desktop) als neuen, eigenständigen
    PostgreSQL-Termin (eigenes Schema, siehe erstelle_termin_postgres) für die
    Mehrbenutzer-Ergebniserfassung am Prüfungstag - Veranstaltungsdaten und alle
    Teilnehmer (inkl. bereits vorhandener Ergebnisse) werden dabei übernommen. Der
    veröffentlichte Termin taucht danach in der Termin-Auswahl der Web-Oberfläche auf
    ('/termin-waehlen' in app_web.py, nach dem Login mit einem Benutzerkonto - siehe
    sync_termin.py).

    Der SQLite-Termin bleibt dabei unverändert (reiner Export, keine Rückwirkung) - erst
    nach der Prüfung holt importiere_ergebnisse_aus_postgres() die dort eingetragenen
    Ergebnisse zurück."""
    neuer_termin = erstelle_termin_postgres(postgres_conn)
    # erstelle_termin_postgres() setzt den search_path am Ende bewusst zurück auf
    # "public" (siehe dortiger Kommentar) - ohne dieses erneute Umschalten würde
    # kopiere_termin_daten() alle Daten in die falschen (gemeinsam genutzten)
    # "public"-Tabellen schreiben statt in das neue Termin-Schema (in der echten CI
    # gefunden: IndexError beim anschließenden Import, weil das neue Schema leer
    # blieb, siehe Fortschritt.md).
    _setze_termin_suchpfad(postgres_conn, neuer_termin.schema_name)
    try:
        kopiere_termin_daten(sqlite_conn, postgres_conn)
    except Exception:
        # kopiere_termin_daten() committet über add_teilnehmer()/eintragen_ergebnis() PRO
        # TEILNEHMER einzeln (diese beiden Funktionen committen selbst - so gewollt für den
        # normalen Desktop-Einzelbetrieb, siehe dortige Kommentare). Bricht das Kopieren
        # mittendrin ab, sind dadurch bereits mehrere Teilnehmer committet - ein echtes
        # Rollback des bisher Kopierten ist an dieser Stelle also nicht mehr möglich.
        # Stattdessen KOMPENSIERENDE Bereinigung: den gerade erst angelegten, dadurch nur
        # teilweise befüllten Termin komplett wieder entfernen, statt ihn als scheinbar
        # vollständigen Termin in der Web-Terminauswahl stehen zu lassen (siehe Fund
        # "Postgres-Export nicht atomar", Codeprüfung 21.09.). Die ursprüngliche Exception
        # wird danach unverändert weitergereicht, damit der Aufrufer (sync_termin.py/
        # app_web.py) den Fehlschlag wie bisher meldet.
        #
        # rollback() ZUERST (Codeprüfung 22.09., M1): war die Ursache ein echter
        # PostgreSQL-Fehler, ist die laufende Transaktion abgebrochen und JEDER weitere
        # Befehl - auch schon das SET search_path - scheitert mit InFailedSqlTransaction;
        # die Bereinigung wäre dann nie gelaufen. rollback() und Bereinigung sind außerdem
        # abgesichert, damit ein Fehler dabei (z. B. Verbindung weg) nicht die
        # ursprüngliche Exception verdeckt.
        with suppress(Exception):
            postgres_conn.rollback()
            _setze_termin_suchpfad(postgres_conn, "public")
            loesche_termin_postgres(postgres_conn, neuer_termin.schema_name)
        raise
    postgres_conn.commit()
    # anzahl_teilnehmer/verein/ort/datum in erstelle_termin_postgres()s Rückgabe waren noch
    # leer/0 (vor dem Kopieren) - aktuellen Stand für die Rückgabe nachladen.
    _setze_termin_suchpfad(postgres_conn, "public")
    aktuelle = [t for t in liste_termine_postgres(postgres_conn) if t.schema_name == neuer_termin.schema_name]
    return aktuelle[0] if aktuelle else neuer_termin

@dataclass
class ImportBericht:
    """Ergebnis von importiere_ergebnisse_nach_startnummer()/importiere_ergebnisse_aus_postgres() -
    zur Anzeige/Protokollierung nach einem Import (siehe sync_termin.py)."""
    aktualisiert: int
    # "Nachname, Vorname" von Teilnehmern in der Quelle ohne Startnummer - können nicht
    # zugeordnet werden (Zuordnung erfolgt ausschließlich über die Startnummer, siehe
    # importiere_ergebnisse_nach_startnummer).
    ohne_startnummer_uebersprungen: list[str]
    # Startnummern aus der Quelle, zu denen es im Ziel keinen Teilnehmer mit derselben
    # Startnummer gibt (z. B. wenn ein Teilnehmer nach dem Export noch umbenannt/gelöscht
    # oder die Startnummer geändert wurde).
    nicht_gefunden: list[str]
    # "Nachname, Vorname" von Teilnehmern, bei denen eintragen_ergebnis() fehlgeschlagen ist
    # (z. B. eine defekte Zieldatenbank-Verbindung mittendrin im Import) - der Import bricht
    # dafür NICHT komplett ab (siehe importiere_ergebnisse_nach_startnummer unten), macht
    # stattdessen mit dem nächsten Teilnehmer weiter, analog zum bereits etablierten Muster
    # in importiere_teilnehmer_aus_csv(). Default leer, damit bestehende Aufrufstellen (die
    # dieses Feld nicht setzen) unverändert funktionieren.
    fehler: list[str] = field(default_factory=list)
    # Startnummer gefunden, aber offensichtlich ein ANDERER Teilnehmer (Nachname, Hund,
    # Art/LK/Disziplin weichen ab - z. B. Startnummern nach dem Veröffentlichen getauscht
    # oder falsche Termin-Datei hochgeladen). Ergebnis wird dann NICHT übernommen
    # (Codeprüfung 22.09., M2, Marcos Entscheidung), sondern hier mit beiden Namen gemeldet.
    abweichungen: list[str] = field(default_factory=list)
    # Disziplinen zuordenbarer Teilnehmer, die in der Web-Erfassung (Quelle) leer, in der
    # Termin-Datei (Ziel) aber bereits gefüllt sind - der Wert der Termin-Datei bleibt
    # dabei unverändert erhalten (Codeprüfung 22.09., G2, Marcos Entscheidung: Verhalten
    # beibehalten, aber sichtbar melden, damit ein im Web versehentlich nicht erfasstes
    # oder bewusst gelöschtes Ergebnis nicht unbemerkt bleibt).
    im_web_leer: list[str] = field(default_factory=list)

def _teilnehmer_merkmale(t: dict) -> tuple:
    """Vergleichsschlüssel für importiere_ergebnisse_nach_startnummer(): Nachname, Rufname
    des Hundes, Art, Leistungsklasse und (nur ED) Disziplin - Groß-/Kleinschreibung und
    Leerzeichen am Rand werden ignoriert."""
    def norm(wert) -> str:
        return (wert or "").strip().casefold()

    return (
        norm(t.get("nachname")),
        norm(t.get("rufname_hund")),
        t.get("art"),
        t.get("stufe"),
        t.get("disziplin") if t.get("art") == "ED" else None,
    )

def _teilnehmer_kurztext(t: dict) -> str:
    return f"{t['nachname']}, {t['vorname']} ({t.get('rufname_hund') or '-'}, {leistungsklasse_label(t)})"

def importiere_ergebnisse_nach_startnummer(quelle_conn, ziel_conn) -> ImportBericht:
    """Kernlogik: überträgt für jeden Teilnehmer in quelle_conn mit gesetzter Startnummer
    die dort eingetragenen Ergebnisse auf den Teilnehmer mit DERSELBEN Startnummer in
    ziel_conn. Zuordnung über die Startnummer statt über die interne ID, da beide
    Datenbanken beim Export unabhängig voneinander vergebene IDs bekommen haben (siehe
    kopiere_termin_daten oben) - die Startnummer ist das einzige beiden Seiten gemeinsame,
    eindeutige Merkmal. Überschreibt dabei die Ergebnisse im Ziel vollständig mit dem
    Stand der Quelle (nach der Prüfung gilt die Web-Erfassung als maßgeblich).

    eintragen_ergebnis() committet pro Teilnehmer einzeln (siehe dortiger Kommentar) - ein
    Fehler bei einem einzelnen Teilnehmer (z. B. ein zwischenzeitlicher DB-Fehler) bricht
    den Import für die übrigen Teilnehmer deshalb NICHT ab, analog zum bereits etablierten
    Muster in importiere_teilnehmer_aus_csv(): der Name landet stattdessen im `fehler`-Feld
    des zurückgegebenen ImportBericht, der Import macht mit dem nächsten Teilnehmer weiter.

    Plausibilitätsprüfung (Codeprüfung 22.09., M2): passt der Teilnehmer mit derselben
    Startnummer im Ziel nicht zur Quelle (siehe _teilnehmer_merkmale), wird NICHTS
    übertragen - sonst landeten Ergebnisse nach einem Startnummerntausch oder bei einer
    falschen Datei still beim falschen Teilnehmer. Meldung im `abweichungen`-Feld.

    Ausnahme vom vollständigen Überschreiben: eine in der Quelle komplett leere Disziplin
    (Suche UND Anzeige None) wird nicht übertragen, ein Wert im Ziel bleibt also erhalten -
    solche Fälle landen seit Codeprüfung 22.09., G2 im `im_web_leer`-Feld."""
    ziel_nach_startnummer = {
        t["startnummer"]: t for t in list_teilnehmer(ziel_conn) if t.get("startnummer") is not None
    }
    aktualisiert = 0
    ohne_startnummer: list[str] = []
    nicht_gefunden: list[str] = []
    fehler: list[str] = []
    abweichungen: list[str] = []
    im_web_leer: list[str] = []
    for quelle_teilnehmer in list_teilnehmer(quelle_conn):
        startnummer = quelle_teilnehmer.get("startnummer")
        name = f"{quelle_teilnehmer['nachname']}, {quelle_teilnehmer['vorname']}"
        if startnummer is None:
            ohne_startnummer.append(name)
            continue
        ziel_teilnehmer = ziel_nach_startnummer.get(startnummer)
        if ziel_teilnehmer is None:
            nicht_gefunden.append(str(startnummer))
            continue
        if _teilnehmer_merkmale(quelle_teilnehmer) != _teilnehmer_merkmale(ziel_teilnehmer):
            abweichungen.append(
                f"Nr. {startnummer}: Web {_teilnehmer_kurztext(quelle_teilnehmer)} ≠ "
                f"Termin-Datei {_teilnehmer_kurztext(ziel_teilnehmer)}"
            )
            continue
        ziel_id = ziel_teilnehmer["id"]
        ergebnis = get_ergebnis(quelle_conn, quelle_teilnehmer["id"]) or {}
        # Codeprüfung 22.09., G2: Stand der Termin-Datei VOR dem Übertragen, um Disziplinen
        # zu melden, die im Web leer sind, im Ziel aber einen (beibehaltenen) Wert haben.
        ziel_ergebnis = get_ergebnis(ziel_conn, ziel_id) or {}
        hat_wert = False
        try:
            for disziplin, (spalte_suche, spalte_anzeige) in DISZIPLIN_SPALTEN.items():
                suche, anzeige = ergebnis.get(spalte_suche), ergebnis.get(spalte_anzeige)
                if suche is not None or anzeige is not None:
                    eintragen_ergebnis(ziel_conn, ziel_id, disziplin, suche, anzeige)
                    hat_wert = True
                else:
                    ziel_suche = ziel_ergebnis.get(spalte_suche)
                    ziel_anzeige = ziel_ergebnis.get(spalte_anzeige)
                    if ziel_suche is not None or ziel_anzeige is not None:
                        im_web_leer.append(
                            f"Nr. {startnummer} {name} – {disziplin}: in der Web-Erfassung "
                            f"leer, in der Termin-Datei "
                            f"{'-' if ziel_suche is None else ziel_suche}/"
                            f"{'-' if ziel_anzeige is None else ziel_anzeige} (beibehalten)"
                        )
        except Exception:
            fehler.append(name)
            continue
        if hat_wert:
            aktualisiert += 1
    return ImportBericht(
        aktualisiert=aktualisiert,
        ohne_startnummer_uebersprungen=ohne_startnummer,
        nicht_gefunden=nicht_gefunden,
        fehler=fehler,
        abweichungen=abweichungen,
        im_web_leer=im_web_leer,
    )

def importiere_ergebnisse_aus_postgres(postgres_conn, schema_name: str, sqlite_conn: sqlite3.Connection) -> ImportBericht:
    """Holt nach der Prüfung die über die Web-Oberfläche eingetragenen Ergebnisse aus dem
    angegebenen PostgreSQL-Termin-Schema zurück in die lokale SQLite-Termin-Datei (siehe
    sync_termin.py) - Gegenstück zu exportiere_termin_nach_postgres()."""
    oeffne_termin_postgres(postgres_conn, schema_name)
    return importiere_ergebnisse_nach_startnummer(postgres_conn, sqlite_conn)
