"""
Datenschicht für das SHS-Prüfungsprogramm (Prototyp).

Entwurfsentscheidung (siehe Grobkonzept): Jede Veranstaltung/Termin ist eine
eigene, in sich abgeschlossene SQLite-Datei - die Datei selbst entspricht
also dem heutigen "eine .ods-Datei pro Prüfungstermin". Löschen eines Termins
bedeutet einfach: diese Datei löschen (kein Aufräumen über Tabellen nötig) -
das war die geforderte, gezielte Löschmöglichkeit aus Datenschutzgründen.

Enthält reine Datenhaltung + die Verbindung zur Kernlogik aus shs_core.py
(Notenberechnung, Rangbildung). Keine GUI-Abhängigkeiten - lässt sich
unabhängig von PySide6 testen.

Zweite Datenbank-Anbindung (für die geplante Podman/Web-Version mit
Mehrbenutzerzugriff): init_db_postgres() öffnet dieselbe fachliche Datenbank auf
PostgreSQL statt SQLite. Damit dafür keine zweite Fassung jeder einzelnen
Datenfunktion gepflegt werden muss, geben init_db()/init_db_postgres() jeweils ein
Objekt zurück, das dieselbe (kleine) Teilmenge der sqlite3.Connection-Schnittstelle
anbietet (execute/executescript/commit/close, '?'-Platzhalter, dict-artige Zeilen) -
siehe _PostgresConnection in db_verbindung.py. Alle Funktionen ab DISZIPLIN_SPALTEN sind
deshalb bewusst weiterhin mit `conn: sqlite3.Connection` typisiert (das ist die
Desktop-Verbindungsart, für die dieses Modul ursprünglich geschrieben wurde), obwohl sie
zur Laufzeit unverändert auch mit einer PostgreSQL-Verbindung funktionieren - dank
`from __future__ import annotations` wird diese Typisierung nicht ausgewertet, sie dient
nur der Dokumentation des ursprünglichen Anwendungsfalls.

Fassade (seit 11.11.2026): Der Code liegt in den Schichtmodulen db_verbindung, db_stamm,
db_ergebnisse, db_zeitplan, db_termine, db_web und db_sync (Abhängigkeiten nur von unten nach oben,
siehe Architektur.md). Dieses Modul reicht alle Namen weiter, damit `from db import …` und
`db.<Name>` wie vorher funktionieren. Neue Namen hier eintragen.
"""

from __future__ import annotations

import datetime
import functools
import hashlib
import math
import os
import re
import secrets
import sqlite3
import unicodedata
from contextlib import closing, suppress
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote
from shs_core import (
    ABBRUCH_ABK,
    ABBRUCH_TEXT,
    DISQUALIFIZIERT_ABK,
    DISQUALIFIZIERT_TEXT,
    ANZEIGE_MAX,
    SUCHE_MAX,
    Teilnehmerergebnis,
    Wertnote,
    berechne_rangliste,
    berechne_wertnote_dk,
    berechne_wertnote_ed,
    stechen_gilt,
    ABBRUCH_GRUENDE,
)

from db_verbindung import (  # noqa: F401
    ALLE_DISZIPLINEN,
    ALLE_PRUEFUNGEN,
    angebotene_pruefungen,
    anmeldeformular_gegenstand_feld,
    ANMELDEFORMULAR_HUENDIN,
    ANMELDEFORMULAR_KENNZEICHNUNG_CHIP,
    ANMELDEFORMULAR_KENNZEICHNUNG_TAETO,
    ANMELDEFORMULAR_PRUEFUNG_PRAEFIX,
    ANMELDEFORMULAR_RUEDE,
    ANMELDEFORMULAR_TEXTFELDER,
    ANMELDEFORMULAR_UNTERSCHRIFT_DATUM,
    ANMELDEFORMULAR_VOLLJAEHRIG_JA,
    ANMELDEFORMULAR_VOLLJAEHRIG_NEIN,
    DISZIPLIN_SPALTEN,
    entfernte_fremdobjekte,
    init_db,
    init_db_postgres,
    JOURNAL_ENDUNG,
    journal_daten_haben_verweis,
    journal_hat_verweis,
    JOURNAL_VERWEIS_TEXT,
    JournalMitVerweis,
    KopieWerteUnzulaessig,
    pruefe_fremdschluessel,
    pruefe_journal_ohne_verweis,
    pruefe_werte_der_kopie,
    pruefung_nach_bezeichnung,
    pruefung_nach_kuerzel,
    pruefungen_als_text,
    Pruefungsangebot,
    SCHEMA,
    SCHEMA_POSTGRES,
    sortierschluessel_text,
    termin_werte_verletzt,
    UNZULAESSIGE_KOPIE_WERTE_TEXT,
    _ENTFERNTE_FREMDOBJEKTE,  # Abzug: Zustand lebt in db_verbindung, nicht über db.… lesen
    _ERGEBNISSE_NEUE_SPALTEN,
    _FORMULAR_POSITION,
    _fremde_trigger_und_views_entfernen,
    _INSERT_TABELLE_RE,
    _JOURNAL_VERWEIS_KENNUNG,
    _LASTROWID_TABELLEN,
    _migriere_ergebnisse_spalten,
    _migriere_spalten,
    _migriere_teilnehmer_spalten,
    _migriere_veranstaltung_spalten,
    _migriere_zeitplan_spalten,
    _mit_rollback,
    _PLATZHALTER_ODER_STRING_RE,
    _PostgresConnection,
    _PostgresCursor,
    _PRUEFUNG_NACH_BEZEICHNUNG,
    _PRUEFUNG_NACH_KUERZEL,
    _fremdschluessel,
    _richte_schema_im_aktuellen_suchpfad_ein,
    _soll_fremdschluessel,
    _soll_spalten,
    _TEILNEHMER_NEUE_SPALTEN,
    _uebersetze_platzhalter,
    _VERANSTALTUNG_NEUE_SPALTEN,
    _vorhandene_spalten,
    _ZEITPLAN_EINTRAG_NEUE_SPALTEN,
)
from db_stamm import (  # noqa: F401
    add_teilnehmer,
    bereiche_automatisch_berechnen,
    datum_anzeige,
    datum_oder_none,
    delete_teilnehmer,
    dk_mindestabstand,
    fehlende_startnummern_je_pruefung,
    fehlende_startnummern_vergeben,
    fehlende_teilnehmer,
    FELD_LAENGEN,
    get_teilnehmer,
    get_veranstaltung,
    HOECHSTE_STARTNUMMER,
    lies_datum,
    list_teilnehmer,
    naechste_freie_startnummer,
    naechste_freie_startnummer_im_bereich,
    NeuerTeilnehmer,
    normalisiere_datum,
    nummern_ausserhalb_nach_tausch,
    pruefe_startnummer_bereiche,
    pruefe_teilnehmer_werte,
    pruefe_veranstaltung_werte,
    pruefungs_kuerzel,
    pruefungsgebuehr_fuer_art,
    SCHULTERHOEHE_MAX,
    SCHULTERHOEHE_MIN,
    set_veranstaltung,
    setze_bezahlt,
    setze_keine_teilnahme,
    STANDARD_BEREICHSGROESSE,
    STANDARD_MINDESTABSTAND,
    startnummer_bereiche,
    startnummer_bereiche_als_text,
    startnummer_bereichsgroesse,
    startnummern_wiederherstellen,
    startnummern_zuruecksetzen,
    StartnummernVergabe,
    tausche_startnummern,
    VERANSTALTUNG_LAENGEN,
    teilnehmer_ohne_startnummer,
    teilnehmer_sichern,
    teilnehmer_wiederherstellen,
    update_teilnehmer,
    vergebene_startnummern,
    _DATUM_DEUTSCH_MUSTER,
    _DATUM_ISO_MUSTER,
    _FELD_LAENGEN,
    _spalten_fuer_einfuegen,
    _spaltenliste,
    _teilnehmer_kuerzel,
)
from db_ergebnisse import (  # noqa: F401
    alle_leistungsklassen,
    BEHAELTNIS_BEDARF_HINWEIS,
    BEHAELTNIS_BEDARF_SPALTEN,
    BEHAELTNIS_BEDARF_TITEL,
    behaeltnis_bedarf_zeilentexte,
    BEHAELTNIS_POSITIONEN,
    berechne_auswertung,
    berechne_behaeltnis_bedarf,
    berechne_teilnehmer_lk_uebersicht,
    eintragen_ergebnis,
    ergebnis_unterschiede,
    ergebnis_werte_wiederherstellen,
    ergebnis_wert_text,
    ERGEBNIS_WERTE,
    ergebnisse_je_teilnehmer,
    gegenstand_fuer_disziplin,
    get_ergebnis,
    hat_erfasste_ergebnisse,
    ist_jugendlicher,
    JUGENDLICHE_ALTERSGRENZE,
    leistungsklasse_label,
    LR_EINHEITEN_JE_ART,
    LR_EINHEITEN_PRO_RICHTER,
    pruefe_ergebnis_eingabe,
    pruefung_bezeichnung,
    pruefung_sortierschluessel,
    setze_ergebnis_status,
    setze_stechen_sieger,
    sortiere_pruefungen,
    stechen_gilt_fuer_veranstaltung,
    teilnehmer_fehlende_pflichtangaben,
    teilnehmer_gegenstand_hinweis,
    zeitplan_bezeichnung,
    _disziplin_punkte,
    _dk_gegenstand_status,
    _ed_gegenstand_status,
    _GEGENSTAND_FELDER,
    _teilnehmer_schluessel,
    _teilpunkte,
    _wertnote,
)
from db_zeitplan import (  # noqa: F401
    add_zeitplan_pause,
    add_zeitplan_pause_bei_allen,
    add_zeitplan_pruefungsblock,
    add_zeitplan_richter,
    aktualisiere_zeitplan_eintrag,
    automatische_zeitplan_verteilung,
    berechne_zeitplan,
    berechne_zeitplan_bloecke,
    FESTE_PAUSE_SCHWELLE_MINUTEN,
    feste_pausenzeit,
    list_zeitplan_eintraege,
    list_zeitplan_richter,
    loesche_zeitplan_eintrag,
    loesche_zeitplan_richter,
    umbenennen_zeitplan_richter,
    verschiebe_zeitplan_eintrag,
    verschiebe_zeitplan_richter,
    WARTEZEIT_BEZEICHNUNG,
    zeitplan_eintrag,
    zeitplan_gruppen,
    zeitplan_gruppen_status,
    zeitplan_richter_aus_veranstaltung_anlegen,
    zeitplan_ueberschneidungen,
    _dk_bloecke_entzerren,
    _dk_reihenfolge_auflockern,
    _DkEntzerrer,
    _konflikt_schluessel,
    _pause_an_position_einfuegen,
    _pausen_beginn,
    _teilnehmer_fuer_pruefungseintrag,
    _ueberschneidungen_in_zeilen,
    _zeitplan_startzeit,
    _zeitplan_zeilen,
)
from db_termine import (  # noqa: F401
    dateiname_slug,
    dateiname_vorschlagen,
    GRUND_ZU_AUFWENDIG,
    GRUND_ZU_GROSS,
    ist_schrittgrenze,
    KopieMitFremdobjekten,
    lesen_begrenzen,
    liste_termine,
    oeffne_termin_lesend,
    pruefe_ohne_fremdobjekte,
    pruefe_termin_aufbau,
    SCHRITTGRENZE_TEXT,
    TERMIN_GROESSE_GRENZE,
    termin_lesend_pruefen,
    termin_oeffnen,
    termin_unversehrt_pruefen,
    termine_ordner,
    TerminInfo,
    TerminNichtOeffenbar,
    TerminUngewoehnlichGross,
    TerminZuGross,
    _groesse_pruefen,
    _ist_wal_ohne_wal_datei,
    _journal_zurueckspielen,
    _LESE_HOECHSTSCHRITTE,
    _LESE_SCHRITTWEITE,
    _megabyte,
    _termin_info_lesen,
    _termin_werte_pruefen,
    _text_oder_none,
    _UMSCHRIFT,
    _UNBEKANNTE_WERTE_TEXT,
)
from db_web import (  # noqa: F401
    admin_einrichten,
    benutzer_anlegen,
    benutzer_loeschen,
    benutzer_stand,
    erstelle_termin_postgres,
    gibt_es_admin,
    liste_benutzer,
    liste_termine_postgres,
    loesche_termin_postgres,
    oeffne_termin_postgres,
    pruefe_login,
    TerminInfoPostgres,
    verbinde_postgres_server,
    _DUMMY_PASSWORT_HASH,  # Abzug: Zustand lebt in db_web, nicht über db.… lesen
    _jetzt_iso,
    _konto_kennung,
    _pruefe_schema_name,
    _SCHEMA_NAME_MUSTER,
    _setze_termin_suchpfad,
    _WEB_BENUTZER_INDEX_BENUTZERNAME_LOWER,
    _WEB_BENUTZER_SCHEMA,
)
from db_sync import (  # noqa: F401
    exportiere_termin_nach_postgres,
    ImportBericht,
    importiere_ergebnisse_aus_postgres,
    importiere_ergebnisse_nach_startnummer,
    kopiere_termin_daten,
    _teilnehmer_kurztext,
    _teilnehmer_merkmale,
)
