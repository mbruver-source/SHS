"""Tests für db.py - Datenschicht + Zusammenspiel mit shs_core."""

import os
import pathlib
import sqlite3
import tempfile
import logging
import unittest
from contextlib import closing
from unittest.mock import MagicMock, patch

from db import (
    ALLE_PRUEFUNGEN,
    ANMELDEFORMULAR_HUENDIN,
    ANMELDEFORMULAR_KENNZEICHNUNG_CHIP,
    ANMELDEFORMULAR_KENNZEICHNUNG_TAETO,
    ANMELDEFORMULAR_PRUEFUNG_PRAEFIX,
    ANMELDEFORMULAR_RUEDE,
    ANMELDEFORMULAR_TEXTFELDER,
    NeuerTeilnehmer,
    anmeldeformular_gegenstand_feld,
    angebotene_pruefungen,
    pruefung_nach_kuerzel,
    pruefungen_als_text,
    TerminInfoPostgres,
    add_teilnehmer,
    add_zeitplan_pause,
    add_zeitplan_pruefungsblock,
    add_zeitplan_richter,
    admin_einrichten,
    aktualisiere_zeitplan_eintrag,
    alle_leistungsklassen,
    automatische_zeitplan_verteilung,
    benutzer_anlegen,
    benutzer_loeschen,
    berechne_auswertung,
    behaeltnis_bedarf_zeilentexte,
    berechne_behaeltnis_bedarf,
    berechne_teilnehmer_lk_uebersicht,
    berechne_zeitplan,
    berechne_zeitplan_bloecke,
    dateiname_vorschlagen,
    delete_teilnehmer,
    eintragen_ergebnis,
    ergebnisse_je_teilnehmer,
    erstelle_termin_postgres,
    exportiere_termin_nach_postgres,
    gegenstand_fuer_disziplin,
    get_ergebnis,
    get_teilnehmer,
    get_veranstaltung,
    gibt_es_admin,
    hat_erfasste_ergebnisse,
    importiere_ergebnisse_aus_postgres,
    importiere_ergebnisse_nach_startnummer,
    init_db,
    init_db_postgres,
    ist_jugendlicher,
    normalisiere_datum,
    datum_anzeige,
    kopiere_termin_daten,
    liste_benutzer,
    liste_termine,
    liste_termine_postgres,
    list_teilnehmer,
    list_zeitplan_eintraege,
    list_zeitplan_richter,
    loesche_termin_postgres,
    loesche_zeitplan_eintrag,
    loesche_zeitplan_richter,
    naechste_freie_startnummer,
    oeffne_termin_postgres,
    benutzer_stand,
    pruefe_login,
    pruefungsgebuehr_fuer_art,
    set_veranstaltung,
    setze_bezahlt,
    setze_ergebnis_status,
    setze_keine_teilnahme,
    tausche_startnummern,
    teilnehmer_fehlende_pflichtangaben,
    teilnehmer_gegenstand_hinweis,
    termine_ordner,
    umbenennen_zeitplan_richter,
    update_teilnehmer,
    verbinde_postgres_server,
    vergebene_startnummern,
    verschiebe_zeitplan_eintrag,
    verschiebe_zeitplan_richter,
    zeitplan_gruppen,
    zeitplan_gruppen_status,
    zeitplan_richter_aus_veranstaltung_anlegen,
    fehlende_startnummern_vergeben,
    naechste_freie_startnummer_im_bereich,
    pruefe_startnummer_bereiche,
    pruefungs_kuerzel,
    startnummer_bereiche,
    startnummer_bereiche_als_text,
    startnummer_bereichsgroesse,
    startnummern_zuruecksetzen,
    fehlende_startnummern_je_pruefung,
    bereiche_automatisch_berechnen,
    dk_mindestabstand,
    zeitplan_ueberschneidungen,
    add_zeitplan_pause_bei_allen,
)
from db_import import (
    importiere_anmeldeformular_pdf,
    importiere_teilnehmer_aus_csv,
    importiere_teilnehmer_aus_oma,
    importiere_teilnehmer_stammdaten,
    CSV_IMPORT_SPALTEN,
    exportiere_teilnehmer_csv,
    schreibe_csv_vorlage,
)
from shs_core import ABBRUCH_ABK, ABBRUCH_TEXT, DISQUALIFIZIERT_ABK, DISQUALIFIZIERT_TEXT


class TestDatenbank(unittest.TestCase):
    # Die folgenden drei Klassenattribute/-methoden werden von TestDatenbankPostgres
    # (siehe Dateiende) überschrieben, um genau dieselben Tests zusätzlich gegen eine
    # echte PostgreSQL-Datenbank laufen zu lassen - das stellt sicher, dass die
    # Kernlogik (nicht nur die SQLite-spezifische Desktop-Variante) für die geplante
    # Podman/Web-Version tatsächlich funktioniert, ohne den ganzen Testsatz zu duplizieren.

    # sqlite3 und psycopg2 werfen bei einer CHECK-/UNIQUE-Verletzung unterschiedliche
    # Exception-Typen.
    IntegrityErrorTyp = sqlite3.IntegrityError
    # Für die drei test_migration_*-Tests unten: die "id"-Spalten-DDL einer bewusst
    # ohne die neueren Zusatzspalten angelegten "teilnehmer"-Tabelle (simuliert eine
    # ältere Termin-Datei/-Datenbank) - siehe SCHEMA_POSTGRES in db.py für denselben
    # Unterschied im eigentlichen Schema.
    _ID_SPALTE_DDL = "INTEGER PRIMARY KEY AUTOINCREMENT"
    # Ebenfalls dialektabhängig: SQLite kennt bei DROP TABLE kein CASCADE (und braucht
    # auch keins, da Fremdschlüssel hier standardmäßig nicht erzwungen werden); bei
    # PostgreSQL hängt dagegen die "ergebnisse"-Tabelle per Fremdschlüssel an
    # "teilnehmer" - ohne CASCADE schlägt das DROP TABLE in _lege_alte_teilnehmer_tabelle_an()
    # unten dort mit "cannot drop table teilnehmer because other objects depend on it" fehl
    # (in der echten CI gegen einen echten PostgreSQL-Server gefunden, siehe Fortschritt.md).
    _DROP_TEILNEHMER_SQL_ZUSATZ = ""

    def setUp(self):
        # Jeder Test bekommt eine frische, temporäre Termin-Datei.
        fd, self.pfad = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        os.remove(self.pfad)  # init_db soll die Datei selbst neu anlegen
        self.conn = init_db(self.pfad)

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.pfad):
            os.remove(self.pfad)

    def _neu_verbinden(self):
        """Schließt die aktuelle Verbindung und öffnet eine neue auf dieselbe Termin-
        Datei (führt dabei die Migrationen erneut aus) - simuliert, dass die Anwendung
        eine bereits vorhandene, ältere Termin-Datei erneut öffnet. Aktualisiert
        self.conn (auch relevant für tearDown) und gibt die neue Verbindung zusätzlich
        zurück. Von TestDatenbankPostgres überschrieben (dort: neue Verbindung zur
        selben PostgreSQL-Datenbank statt Datei-Neuöffnen)."""
        self.conn.close()
        self.conn = init_db(self.pfad)
        return self.conn

    def _lege_alte_teilnehmer_tabelle_an(self, zusatz_spalten_sql: str = "") -> None:
        """Ersetzt die Tabelle 'teilnehmer' durch eine ältere Fassung ohne die später
        hinzugekommenen Spalten (simuliert eine vor deren Einführung angelegte Termin-
        Datei/-Datenbank) - für die drei test_migration_*-Tests unten. Die id-Spalte ist
        dialektabhängig (siehe _ID_SPALTE_DDL), alles andere ist Standard-SQL und für
        SQLite wie PostgreSQL identisch gültig."""
        self.conn.execute(f"DROP TABLE teilnehmer{self._DROP_TEILNEHMER_SQL_ZUSATZ}")
        # Bei PostgreSQL reißt das obige "DROP TABLE ... CASCADE" auch die Fremdschlüssel-
        # Constraint von "ergebnisse" auf "teilnehmer" mit ab (sie hängt als abhängiges
        # Objekt daran) - die Tabelle "ergebnisse" selbst bleibt dabei aber bestehen, nur
        # OHNE Fremdschlüssel, und würde das für den Rest des gemeinsam genutzten Postgres-
        # Testlaufs auch bleiben, da init_db()/init_db_postgres() sie nur bei Bedarf neu
        # anlegt ("CREATE TABLE IF NOT EXISTS" ist dann ein No-Op, solange die Tabelle noch
        # existiert). Ohne diese Fremdschlüssel-Constraint löscht delete_teilnehmer()
        # (verlässt sich vollständig auf ON DELETE CASCADE, siehe db.py) keine zugehörige
        # ergebnisse-Zeile mehr mit - das führte in der echten CI zu einem falschen
        # "1 != 0" in test_teilnehmer_loeschen_entfernt_auch_ergebnis weiter unten
        # (derselbe gemeinsam genutzte Postgres-Testlauf, alphabetisch nach diesem Test
        # ausgeführt, siehe Fortschritt.md). Deshalb "ergebnisse" hier ebenfalls verwerfen,
        # damit die anschließende _neu_verbinden() sie samt Fremdschlüssel sauber neu
        # anlegt. Unproblematisch für SQLite (dort entsteht durch das DROP TABLE oben
        # ohnehin nie eine echte FK-Constraint) und für beide Dialekte gültiges Standard-
        # SQL (kein CASCADE nötig, da nichts auf "ergebnisse" verweist).
        self.conn.execute("DROP TABLE ergebnisse")
        self.conn.execute(
            f"CREATE TABLE teilnehmer (id {self._ID_SPALTE_DDL}, "
            "nachname TEXT NOT NULL, vorname TEXT NOT NULL, verein TEXT, zwingername TEXT, "
            "rufname_hund TEXT NOT NULL, geschlecht TEXT, schulterhoehe_cm INTEGER, "
            "chip_nr TEXT, art TEXT NOT NULL, stufe INTEGER NOT NULL, disziplin TEXT, "
            "startnummer INTEGER UNIQUE, gegenstand_1 TEXT, gegenstand_2 TEXT, gegenstand_3 TEXT"
            f"{zusatz_spalten_sql})"
        )

    def _lege_alte_ergebnisse_tabelle_an(self) -> None:
        """Ersetzt die Tabelle 'ergebnisse' durch eine ältere Fassung ohne die Status-
        Spalten 'disqualifiziert'/'abbruch' (simuliert eine vor deren Einführung
        angelegte Termin-Datei/-Datenbank) - für
        test_migration_ergaenzt_disqualifiziert_abbruch_spalten_in_alter_ergebnisse_tabelle
        unten. Standard-SQL, für SQLite wie PostgreSQL identisch gültig (keine
        Autoincrement-Spalte hier, siehe _lege_alte_teilnehmer_tabelle_an oben)."""
        self.conn.execute("DROP TABLE ergebnisse")
        self.conn.execute(
            "CREATE TABLE ergebnisse ("
            "teilnehmer_id INTEGER PRIMARY KEY REFERENCES teilnehmer(id), "
            "suche_truemmerfeld INTEGER, anzeige_truemmerfeld INTEGER, "
            "suche_flaechensuche INTEGER, anzeige_flaechensuche INTEGER, "
            "suche_behaeltnis INTEGER, anzeige_behaeltnis INTEGER)"
        )
        self.conn.commit()

    def test_migration_ergaenzt_disqualifiziert_abbruch_spalten_in_alter_ergebnisse_tabelle(self):
        # Nutzerwunsch (21.09.): init_db muss die beiden neuen Status-Spalten in einer
        # bereits vorher angelegten Termin-Datei/-Datenbank nachträglich ergänzen, ohne
        # bestehende Ergebnis-Daten zu verlieren. Bestehende Ergebniszeilen gelten dabei
        # als "weder disqualifiziert noch Abbruch" (Default 0).
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Alt", vorname="Vorname", rufname_hund="Hund", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1,
        ))
        self._lege_alte_ergebnisse_tabelle_an()
        self.conn.execute(
            "INSERT INTO ergebnisse (teilnehmer_id, suche_truemmerfeld, anzeige_truemmerfeld) "
            "VALUES (?, ?, ?)",
            (tid, 58, 38),
        )
        self.conn.commit()

        conn = self._neu_verbinden()
        ergebnis = get_ergebnis(conn, tid)
        self.assertEqual(ergebnis["suche_truemmerfeld"], 58)
        self.assertEqual(ergebnis["anzeige_truemmerfeld"], 38)
        self.assertEqual(ergebnis["disqualifiziert"], 0)
        self.assertEqual(ergebnis["abbruch"], 0)
        # berechne_auswertung()/setze_ergebnis_status() funktionieren danach ganz normal weiter.
        fertig, _ausstehend = berechne_auswertung(conn)
        self.assertEqual(fertig[0].wertnote.abkuerzung, "V")
        setze_ergebnis_status(conn, tid, disqualifiziert=True, abbruch=False)
        self.assertEqual(get_ergebnis(conn, tid)["disqualifiziert"], 1)

    def test_veranstaltung_anlegen_und_lesen(self):
        self.assertIsNone(get_veranstaltung(self.conn))
        set_veranstaltung(self.conn, verein="SGV Köppern e.V.", datum="2026-09-19", ort="Köppern")
        v = get_veranstaltung(self.conn)
        self.assertEqual(v["verein"], "SGV Köppern e.V.")
        self.assertEqual(v["ort"], "Köppern")

        # Erneutes Setzen überschreibt statt einen zweiten Datensatz anzulegen
        set_veranstaltung(self.conn, verein="Anderer Verein", datum="2026-09-20")
        self.assertEqual(len(self.conn.execute("SELECT * FROM veranstaltung").fetchall()), 1)

    def test_veranstaltung_zusatzfelder_fuer_statistik(self):
        # Werden ohne die Zusatzfelder gesetzt: bleiben None statt zu fehlen.
        set_veranstaltung(self.conn, verein="SGV Köppern e.V.", datum="2026-09-19")
        v = get_veranstaltung(self.conn)
        self.assertIsNone(v["vereins_nr"])
        self.assertIsNone(v["pruefungsleiter"])
        self.assertIsNone(v["wertungsrichter_3"])

        set_veranstaltung(
            self.conn, verein="SGV Köppern e.V.", datum="2026-09-19",
            vereins_nr="19010", pruefungsnummer="P-2026-04",
            wertungsrichter_1="A. Muster", wertungsrichter_2="B. Beispiel",
            wertungsrichter_3="C. Vorbild", wertungsrichter_4="D. Vorlage", wertungsrichter_5="E. Original",
            pruefungsleiter="Katja Bruver",
        )
        v = get_veranstaltung(self.conn)
        self.assertEqual(v["vereins_nr"], "19010")
        self.assertEqual(v["pruefungsnummer"], "P-2026-04")
        self.assertEqual(v["wertungsrichter_1"], "A. Muster")
        self.assertEqual(v["wertungsrichter_2"], "B. Beispiel")
        self.assertEqual(v["wertungsrichter_3"], "C. Vorbild")
        self.assertEqual(v["wertungsrichter_4"], "D. Vorlage")
        self.assertEqual(v["wertungsrichter_5"], "E. Original")
        self.assertEqual(v["pruefungsleiter"], "Katja Bruver")

    def test_pruefungsgebuehr_je_art_ed_und_dk(self):
        # Ohne hinterlegte Gebühren liefert pruefungsgebuehr_fuer_art None statt zu fehlen.
        set_veranstaltung(self.conn, verein="SGV Köppern e.V.", datum="2026-09-19")
        v = get_veranstaltung(self.conn)
        self.assertIsNone(v["pruefungsgebuehr_ed"])
        self.assertIsNone(v["pruefungsgebuehr_dk"])
        self.assertIsNone(pruefungsgebuehr_fuer_art(v, "ED"))
        self.assertIsNone(pruefungsgebuehr_fuer_art(v, "DK"))

        # ED und DK können unterschiedliche Gebühren haben (Prüfungsleitungs-Übersicht).
        set_veranstaltung(
            self.conn, verein="SGV Köppern e.V.", datum="2026-09-19",
            pruefungsgebuehr_ed="12,00", pruefungsgebuehr_dk="18,00",
        )
        v = get_veranstaltung(self.conn)
        self.assertEqual(v["pruefungsgebuehr_ed"], "12,00")
        self.assertEqual(v["pruefungsgebuehr_dk"], "18,00")
        self.assertEqual(pruefungsgebuehr_fuer_art(v, "ED"), "12,00")
        self.assertEqual(pruefungsgebuehr_fuer_art(v, "DK"), "18,00")
        # pruefungsgebuehr_fuer_art kommt auch mit fehlender Veranstaltung klar.
        self.assertIsNone(pruefungsgebuehr_fuer_art(None, "ED"))

    def test_teilnehmer_lk_uebersicht_ohne_teilnehmer(self):
        # Ohne Teilnehmer sind alle Zähler 0 - insbesondere darf
        # leistungsrichter_benoetigt hier NICHT durch eine Division-durch-Null stolpern.
        ergebnis = berechne_teilnehmer_lk_uebersicht(self.conn)
        self.assertEqual(ergebnis["ed"][1], {
            "Trümmerfeld": 0, "Flächensuche": 0, "Behältnisstrecke": 0, "summe": 0, "abteilungen": 0,
        })
        self.assertEqual(ergebnis["ed_summe"], 0)
        self.assertEqual(ergebnis["dk"][1], {"summe": 0, "abteilungen": 0})
        self.assertEqual(ergebnis["dk_summe"], 0)
        self.assertEqual(ergebnis["teilnehmer_gesamt"], 0)
        self.assertEqual(ergebnis["abteilungen_gesamt"], 0)
        self.assertEqual(ergebnis["leistungsrichter_benoetigt"], 0)

    def test_teilnehmer_lk_uebersicht_gemischt(self):
        # Szenario aus der Original-Vorlage ("Übersicht Teilnehmer"): 13 ED-LK1-Teilnehmer
        # in Trümmerfeld, 2 DK-LK1- und 2 DK-LK2-Teilnehmer. Prüft insbesondere die
        # Abteilungen-Zählung (DK = 3 je Teilnehmer) und die daraus resultierende
        # Richterzahl.
        startnummer = 1
        for _ in range(13):
            add_teilnehmer(self.conn, NeuerTeilnehmer(
                nachname="Muster", vorname="ED", rufname_hund="Bello",
                art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=startnummer,
            ))
            startnummer += 1
        for _ in range(2):
            add_teilnehmer(self.conn, NeuerTeilnehmer(
                nachname="Muster", vorname="DK1", rufname_hund="Rex",
                art="DK", stufe=1, startnummer=startnummer,
            ))
            startnummer += 1
        for _ in range(2):
            add_teilnehmer(self.conn, NeuerTeilnehmer(
                nachname="Muster", vorname="DK2", rufname_hund="Luna",
                art="DK", stufe=2, startnummer=startnummer,
            ))
            startnummer += 1

        ergebnis = berechne_teilnehmer_lk_uebersicht(self.conn)
        self.assertEqual(ergebnis["ed"][1]["Trümmerfeld"], 13)
        self.assertEqual(ergebnis["ed"][1]["summe"], 13)
        self.assertEqual(ergebnis["ed"][1]["abteilungen"], 13)
        self.assertEqual(ergebnis["ed_summe"], 13)
        self.assertEqual(ergebnis["dk"][1]["summe"], 2)
        self.assertEqual(ergebnis["dk"][1]["abteilungen"], 6)
        self.assertEqual(ergebnis["dk"][2]["summe"], 2)
        self.assertEqual(ergebnis["dk"][2]["abteilungen"], 6)
        self.assertEqual(ergebnis["dk_summe"], 4)
        self.assertEqual(ergebnis["teilnehmer_gesamt"], 17)
        self.assertEqual(ergebnis["abteilungen_gesamt"], 25)
        self.assertEqual(ergebnis["leistungsrichter_benoetigt"], 1)

    def _behaeltnis_teilnehmer(self, eintraege):
        for startnummer, (stufe, art, disziplin) in enumerate(eintraege, start=1):
            add_teilnehmer(self.conn, NeuerTeilnehmer(
                nachname=f"T{startnummer}", vorname="X", rufname_hund="H",
                art=art, stufe=stufe, disziplin=disziplin, startnummer=startnummer,
            ))

    def test_behaeltnis_bedarf_ohne_teilnehmer(self):
        zeilen = berechne_behaeltnis_bedarf(self.conn)
        self.assertEqual(
            [z["bezeichnung"] for z in zeilen],
            ["LK 1", "LK 2", "LK 3 ohne separates Behältnis", "LK 3 mit separatem Behältnis"],
        )
        for z in zeilen:
            self.assertEqual((z["teilnehmer"], z["leer"], z["mit_gegenstand"], z["gesamt"]), (0, 0, 0, 0))
        self.assertEqual([z["material_verleitung"] for z in zeilen], [None, None, None, 0])

    def test_behaeltnis_bedarf_beispiel(self):
        # Abgenommenes Beispiel vom 25.09.: LK1 2, LK2 3, LK3 4 Teilnehmer mit
        # Behältnisstrecke. ED Trümmerfeld/Flächensuche zählen nicht mit, DK schon.
        self._behaeltnis_teilnehmer([
            (1, "ED", "Behältnisstrecke"), (1, "DK", None), (1, "ED", "Flächensuche"),
            (2, "ED", "Behältnisstrecke"), (2, "ED", "Behältnisstrecke"), (2, "DK", None),
            (3, "ED", "Behältnisstrecke"), (3, "ED", "Behältnisstrecke"), (3, "DK", None), (3, "DK", None),
            (3, "ED", "Trümmerfeld"),
        ])
        zeilen = berechne_behaeltnis_bedarf(self.conn)
        self.assertEqual(
            [(z["teilnehmer"], z["leer"], z["mit_gegenstand"], z["material_verleitung"], z["gesamt"]) for z in zeilen],
            [(2, 5, 2, None, 7), (3, 7, 3, None, 10), (4, 9, 4, None, 13), (4, 9, 4, 4, 17)],
        )
        self.assertEqual(behaeltnis_bedarf_zeilentexte(zeilen[3]),
                         ["LK 3 mit separatem Behältnis", "4", "9", "4", "4", "17"])
        self.assertEqual(behaeltnis_bedarf_zeilentexte(zeilen[0])[4], "–")

    def test_behaeltnis_bedarf_nur_lk2_belegt(self):
        # Unbelegte LK zeigen überall 0 (auch keine leeren Behältnisse).
        self._behaeltnis_teilnehmer([(2, "DK", None)])
        zeilen = berechne_behaeltnis_bedarf(self.conn)
        self.assertEqual([z["gesamt"] for z in zeilen], [0, 8, 0, 0])
        self.assertEqual(zeilen[1]["leer"], 7)

    def test_migration_ergaenzt_zusatzfelder_in_alter_termin_datei(self):
        # Simuliert eine Termin-Datei/-Datenbank, die vor Einführung der Zusatzfelder
        # angelegt wurde (Tabelle "veranstaltung" ohne diese Spalten) - erneutes Öffnen
        # (_neu_verbinden) muss sie nachträglich ergänzen, ohne bestehende Daten zu
        # verlieren. Die DDL hier kommt ohne AUTOINCREMENT aus und ist daher für SQLite
        # wie PostgreSQL unverändert gültig (siehe TestDatenbankPostgres für den
        # Postgres-Nachlauf dieses Tests).
        self.conn.execute("DROP TABLE veranstaltung")
        self.conn.execute(
            "CREATE TABLE veranstaltung (id INTEGER PRIMARY KEY CHECK (id = 1), "
            "verein TEXT NOT NULL, ort TEXT, datum TEXT NOT NULL)"
        )
        self.conn.execute(
            "INSERT INTO veranstaltung (id, verein, ort, datum) VALUES (1, 'Alt-Verein', 'Alt-Ort', '2025-01-01')"
        )
        self.conn.commit()

        conn = self._neu_verbinden()
        v = get_veranstaltung(conn)
        self.assertEqual(v["verein"], "Alt-Verein")
        self.assertIsNone(v["pruefungsnummer"])
        self.assertIsNone(v["pruefungsgebuehr_ed"])
        self.assertIsNone(v["pruefungsgebuehr_dk"])
        self.assertIsNone(v["wertungsrichter_5"])
        # Anmeldeformular-Angaben (Nutzerwunsch 28.09.2026) werden ebenso nachgerüstet.
        self.assertIsNone(v["verband"])
        self.assertIsNone(v["meldestelle"])
        self.assertIsNone(v["angebotene_pruefungen"])
        # set_veranstaltung funktioniert danach ganz normal weiter.
        set_veranstaltung(conn, verein="Alt-Verein", datum="2025-01-01", pruefungsnummer="P-1",
                          verband="BLV", meldestelle="Meldestelle X", angebotene_pruefungen="DK1")
        v = get_veranstaltung(conn)
        self.assertEqual(v["pruefungsnummer"], "P-1")
        self.assertEqual((v["verband"], v["meldestelle"], v["angebotene_pruefungen"]),
                         ("BLV", "Meldestelle X", "DK1"))

    def test_ed_teilnehmer_vollstaendiger_ablauf(self):
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Holst", vorname="Katrin", rufname_hund="Freda",
            art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=4,
        ))
        # Vor Ergebniseintragung: Teilnehmer erscheint als "ausstehend"
        fertig, ausstehend = berechne_auswertung(self.conn)
        self.assertEqual(len(fertig), 0)
        self.assertEqual(len(ausstehend), 1)

        eintragen_ergebnis(self.conn, tid, "Trümmerfeld", suche=58, anzeige=38)
        fertig, ausstehend = berechne_auswertung(self.conn)
        self.assertEqual(len(ausstehend), 0)
        self.assertEqual(len(fertig), 1)
        t = fertig[0]
        self.assertEqual(t.gesamtpunkte, 96)
        self.assertEqual(t.wertnote.abkuerzung, "V")
        self.assertEqual(t.platzierung, 1)
        self.assertEqual(t.von_startern, 1)

    def test_teilnehmer_ohne_ergebnisse_zeile_stuerzt_nicht_ab_sondern_gilt_als_ausstehend(self):
        """QS-Fund (19./20.09.): add_teilnehmer() legt normalerweise IMMER zusammen mit
        dem Teilnehmer eine passende Zeile in ergebnisse an (siehe dort) -
        berechne_auswertung() verließ sich bisher blind auf diese Invariante
        (ergebnis_rows[t["id"]]) und wäre mit einem harten KeyError für die GESAMTE
        Auswertung abgestürzt, sollte sie doch einmal verletzt sein. Hier absichtlich
        von Hand nachgestellt (z.B. wie durch einen künftigen Programmierfehler oder
        eine von Hand bearbeitete Termin-Datei), um zu prüfen, dass so ein Teilnehmer
        stattdessen einfach als "noch nicht vollständig bewertet" behandelt wird -
        ohne die Auswertung der ÜBRIGEN, korrekten Teilnehmer zu verhindern."""
        tid_kaputt = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Fehlerhaft", vorname="Otto", rufname_hund="Lücke",
            art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=97,
        ))
        self.conn.execute("DELETE FROM ergebnisse WHERE teilnehmer_id = ?", (tid_kaputt,))
        self.conn.commit()

        tid_ok = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Holst", vorname="Katrin", rufname_hund="Freda",
            art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=4,
        ))
        eintragen_ergebnis(self.conn, tid_ok, "Trümmerfeld", suche=58, anzeige=38)

        fertig, ausstehend = berechne_auswertung(self.conn)

        self.assertEqual(len(fertig), 1)
        self.assertEqual(fertig[0].name, "Holst, Katrin")
        self.assertEqual(len(ausstehend), 1)
        self.assertEqual(ausstehend[0]["nachname"], "Fehlerhaft")

    def test_dk_teilnehmer_braucht_alle_drei_disziplinen(self):
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Kleemann", vorname="Doris", rufname_hund="Dorie",
            art="DK", stufe=1, startnummer=13,
        ))
        eintragen_ergebnis(self.conn, tid, "Trümmerfeld", suche=50, anzeige=30)
        eintragen_ergebnis(self.conn, tid, "Flächensuche", suche=45, anzeige=28)
        # Behältnisstrecke fehlt noch -> weiterhin ausstehend
        fertig, ausstehend = berechne_auswertung(self.conn)
        self.assertEqual(len(fertig), 0)
        self.assertEqual(len(ausstehend), 1)

        eintragen_ergebnis(self.conn, tid, "Behältnisstrecke", suche=42, anzeige=30)  # 72, ebenfalls >= 70
        fertig, ausstehend = berechne_auswertung(self.conn)
        self.assertEqual(len(ausstehend), 0)
        self.assertEqual(fertig[0].gesamtpunkte, 50 + 30 + 45 + 28 + 42 + 30)  # 225
        self.assertEqual(fertig[0].wertnote.abkuerzung, "B")
        self.assertTrue(fertig[0].bestanden)

    def test_dk_mit_einer_disziplin_unter_70_punkten_ist_nicht_bestanden(self):
        # Regressionstest für den gemeldeten Fehler: beim DK muss JEDE der drei
        # Disziplinen für sich mindestens 70 Punkte erreichen, sonst ist die Prüfung
        # "nicht Bestanden" - unabhängig von einer hohen Gesamtpunktzahl.
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Vogel", vorname="Nils", rufname_hund="Rex",
            art="DK", stufe=1, startnummer=21,
        ))
        eintragen_ergebnis(self.conn, tid, "Trümmerfeld", suche=60, anzeige=40)      # 100 - top
        eintragen_ergebnis(self.conn, tid, "Flächensuche", suche=60, anzeige=40)     # 100 - top
        eintragen_ergebnis(self.conn, tid, "Behältnisstrecke", suche=35, anzeige=34)  # 69 - unter der Mindestpunktzahl

        fertig, ausstehend = berechne_auswertung(self.conn)
        self.assertEqual(len(ausstehend), 0)
        self.assertEqual(len(fertig), 1)
        ergebnis = fertig[0]
        self.assertEqual(ergebnis.gesamtpunkte, 269)  # rechnerisch würde die Summe für "Gut" reichen
        self.assertEqual(ergebnis.wertnote.notentext, "nicht Bestanden")
        self.assertEqual(ergebnis.wertnote.abkuerzung, "nB")
        self.assertFalse(ergebnis.bestanden)
        self.assertIsNone(ergebnis.platzierung)  # keine Platzierung für nicht bestandene Teilnehmer

    def test_ed_unter_70_punkten_ist_nicht_bestanden(self):
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Berger", vorname="Uwe", rufname_hund="Findus",
            art="ED", stufe=1, disziplin="Behältnisstrecke", startnummer=22,
        ))
        eintragen_ergebnis(self.conn, tid, "Behältnisstrecke", suche=35, anzeige=34)  # 69

        fertig, ausstehend = berechne_auswertung(self.conn)
        self.assertEqual(len(fertig), 1)
        ergebnis = fertig[0]
        self.assertEqual(ergebnis.gesamtpunkte, 69)
        self.assertFalse(ergebnis.bestanden)
        self.assertEqual(ergebnis.wertnote.abkuerzung, "nB")
        self.assertIsNone(ergebnis.platzierung)

    def test_nicht_bestandener_teilnehmer_zaehlt_trotzdem_bei_startern_mit(self):
        # Entspricht der Original-Rankingliste ("Anzahl Starter" zählt auch "nB" mit).
        a = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="A", vorname="A", rufname_hund="Hund A", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=30))
        b = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="B", vorname="B", rufname_hund="Hund B", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=31))
        eintragen_ergebnis(self.conn, a, "Trümmerfeld", suche=58, anzeige=38)  # 96, besteht
        eintragen_ergebnis(self.conn, b, "Trümmerfeld", suche=30, anzeige=30)  # 60, nicht bestanden

        fertig, ausstehend = berechne_auswertung(self.conn)
        by_id = {t.id: t for t in fertig}
        self.assertEqual(by_id[str(a)].platzierung, 1)
        self.assertEqual(by_id[str(a)].von_startern, 2)
        self.assertIsNone(by_id[str(b)].platzierung)
        self.assertEqual(by_id[str(b)].von_startern, 2)

    def test_rangfolge_ueber_mehrere_teilnehmer_getrennt_nach_lk(self):
        a = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="A", vorname="A", rufname_hund="Hund A", art="DK", stufe=1, startnummer=1))
        b = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="B", vorname="B", rufname_hund="Hund B", art="DK", stufe=1, startnummer=2))
        c = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="C", vorname="C", rufname_hund="Hund C", art="ED", stufe=2,
            disziplin="Flächensuche", startnummer=3))

        for tid, punkte in [(a, (60, 40)), (b, (50, 30))]:
            eintragen_ergebnis(self.conn, tid, "Trümmerfeld", *punkte)
            eintragen_ergebnis(self.conn, tid, "Flächensuche", *punkte)
            eintragen_ergebnis(self.conn, tid, "Behältnisstrecke", *punkte)
        eintragen_ergebnis(self.conn, c, "Flächensuche", suche=55, anzeige=35)

        fertig, ausstehend = berechne_auswertung(self.conn)
        self.assertEqual(len(ausstehend), 0)
        by_id = {t.id: t for t in fertig}
        # A (300 Punkte) vor B (240 Punkte) in DK LK 1
        self.assertEqual(by_id[str(a)].platzierung, 1)
        self.assertEqual(by_id[str(a)].von_startern, 2)
        self.assertEqual(by_id[str(b)].platzierung, 2)
        # C ist alleine in ED LK 2 Flächensuche -> eigener Platz 1, unabhängig von DK-Gruppe
        self.assertEqual(by_id[str(c)].platzierung, 1)
        self.assertEqual(by_id[str(c)].von_startern, 1)

    def test_disqualifiziert_bekommt_keine_aus_punkten_berechnete_wertnote(self):
        # Nutzerwunsch (21.09.): ein disqualifizierter Teilnehmer bekommt unabhängig von
        # ggf. doch vorhandenen Punktwerten KEINE aus Punkten berechnete Wertnote -
        # erscheint ähnlich einem "nicht bestanden"-Teilnehmer (keine Platzierung, zählt
        # aber als Starter mit), mit eigenem Status-Text statt Wertnote.
        a = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="A", vorname="A", rufname_hund="Hund A", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=50))
        b = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="B", vorname="B", rufname_hund="Hund B", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=51))
        eintragen_ergebnis(self.conn, a, "Trümmerfeld", suche=58, anzeige=38)  # 96, "V"
        # b hat (z.B. vor der Disqualifikation) noch Punktwerte eingetragen - diese
        # dürfen die Wertnote trotzdem nicht mehr beeinflussen.
        eintragen_ergebnis(self.conn, b, "Trümmerfeld", suche=58, anzeige=38)
        setze_ergebnis_status(self.conn, b, disqualifiziert=True, abbruch=False)

        fertig, ausstehend = berechne_auswertung(self.conn)
        self.assertEqual(len(ausstehend), 0)
        self.assertEqual(len(fertig), 2)
        by_id = {t.id: t for t in fertig}

        disq = by_id[str(b)]
        self.assertEqual(disq.wertnote.abkuerzung, DISQUALIFIZIERT_ABK)
        self.assertEqual(disq.wertnote.notentext, DISQUALIFIZIERT_TEXT)
        self.assertFalse(disq.bestanden)
        self.assertIsNone(disq.platzierung)
        self.assertEqual(disq.von_startern, 2)  # zählt trotzdem als Starter mit

        # A bleibt unbeeinflusst und bekommt weiterhin Platz 1.
        self.assertEqual(by_id[str(a)].platzierung, 1)
        self.assertEqual(by_id[str(a)].von_startern, 2)

    def test_abbruch_bekommt_keine_aus_punkten_berechnete_wertnote(self):
        # Analog zu Disqualifiziert oben, aber für den unabhängigen zweiten Status
        # "Abbruch" - hier ganz ohne eingetragene Punktwerte (Abbruch mitten in der
        # Prüfung, bevor überhaupt etwas eingetragen wurde).
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="C", vorname="C", rufname_hund="Hund C", art="DK", stufe=1, startnummer=52))
        setze_ergebnis_status(self.conn, tid, disqualifiziert=False, abbruch=True)

        fertig, ausstehend = berechne_auswertung(self.conn)
        self.assertEqual(len(ausstehend), 0)
        self.assertEqual(len(fertig), 1)
        ergebnis = fertig[0]
        self.assertEqual(ergebnis.wertnote.abkuerzung, ABBRUCH_ABK)
        self.assertEqual(ergebnis.wertnote.notentext, ABBRUCH_TEXT)
        self.assertFalse(ergebnis.bestanden)
        self.assertIsNone(ergebnis.platzierung)
        self.assertEqual(ergebnis.von_startern, 1)

    def test_setze_ergebnis_status_disqualifiziert_und_abbruch_sind_unabhaengig(self):
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="D", vorname="D", rufname_hund="Hund D", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=53))
        # Neu angelegter Teilnehmer: beide Status zunächst 0 (siehe SCHEMA-Default).
        ergebnis = get_ergebnis(self.conn, tid)
        self.assertEqual(ergebnis["disqualifiziert"], 0)
        self.assertEqual(ergebnis["abbruch"], 0)

        setze_ergebnis_status(self.conn, tid, disqualifiziert=True, abbruch=False)
        ergebnis = get_ergebnis(self.conn, tid)
        self.assertEqual(ergebnis["disqualifiziert"], 1)
        self.assertEqual(ergebnis["abbruch"], 0)

        # Zurücksetzen funktioniert ebenso (z.B. Checkbox in der GUI wieder deaktiviert).
        setze_ergebnis_status(self.conn, tid, disqualifiziert=False, abbruch=False)
        ergebnis = get_ergebnis(self.conn, tid)
        self.assertEqual(ergebnis["disqualifiziert"], 0)
        self.assertEqual(ergebnis["abbruch"], 0)

    def test_ergebnisse_je_teilnehmer_liefert_alle_zeilen_nach_id(self):
        self.assertEqual(ergebnisse_je_teilnehmer(self.conn), {})
        tid_mit = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="M", vorname="M", rufname_hund="Hund M", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=61))
        tid_ohne = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="O", vorname="O", rufname_hund="Hund O", art="DK", stufe=1,
            startnummer=62))
        eintragen_ergebnis(self.conn, tid_mit, "Trümmerfeld", 50, 30)

        alle = ergebnisse_je_teilnehmer(self.conn)
        self.assertEqual(set(alle), {tid_mit, tid_ohne})
        # Dieselben Zeilen wie beim Einzelabruf über get_ergebnis().
        self.assertEqual(alle[tid_mit], get_ergebnis(self.conn, tid_mit))
        self.assertEqual(alle[tid_ohne], get_ergebnis(self.conn, tid_ohne))
        self.assertEqual(alle[tid_mit]["suche_truemmerfeld"], 50)
        self.assertIsNone(alle[tid_ohne]["suche_truemmerfeld"])

    def test_check_constraint_ed_braucht_disziplin(self):
        with self.assertRaises(self.IntegrityErrorTyp):
            add_teilnehmer(self.conn, NeuerTeilnehmer(
                nachname="X", vorname="Y", rufname_hund="Z", art="ED", stufe=1, disziplin=None))

    def test_check_constraint_dk_darf_keine_disziplin_haben(self):
        with self.assertRaises(self.IntegrityErrorTyp):
            add_teilnehmer(self.conn, NeuerTeilnehmer(
                nachname="X", vorname="Y", rufname_hund="Z", art="DK", stufe=1, disziplin="Trümmerfeld"))

    def test_check_constraint_punktzahl_ausserhalb_bereich(self):
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="X", vorname="Y", rufname_hund="Z", art="ED", stufe=1, disziplin="Trümmerfeld"))
        with self.assertRaises(self.IntegrityErrorTyp):
            eintragen_ergebnis(self.conn, tid, "Trümmerfeld", suche=61, anzeige=10)  # max. 60

    def test_eintragen_ergebnis_mit_none_loescht_zuvor_eingetragenes_ergebnis(self):
        # Regressionstest: in der Ergebniserfassung ein zuvor gespeichertes Ergebnis
        # wieder leeren (beide Felder auf None) muss die Werte in der DB auf NULL
        # setzen, statt dass sie beim nächsten Laden wieder auftauchen.
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="X", vorname="Y", rufname_hund="Z", art="ED", stufe=1, disziplin="Trümmerfeld"))
        eintragen_ergebnis(self.conn, tid, "Trümmerfeld", suche=58, anzeige=38)

        eintragen_ergebnis(self.conn, tid, "Trümmerfeld", suche=None, anzeige=None)

        zeile = self.conn.execute(
            "SELECT suche_truemmerfeld, anzeige_truemmerfeld FROM ergebnisse WHERE teilnehmer_id = ?", (tid,)
        ).fetchone()
        self.assertIsNone(zeile["suche_truemmerfeld"])
        self.assertIsNone(zeile["anzeige_truemmerfeld"])

    def test_teilnehmer_bearbeiten(self):
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Alt", vorname="A", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1))
        update_teilnehmer(self.conn, tid, NeuerTeilnehmer(
            nachname="Neu", vorname="A", rufname_hund="H", art="ED", stufe=2,
            disziplin="Flächensuche", startnummer=1))
        geladen = get_teilnehmer(self.conn, tid)
        self.assertEqual(geladen["nachname"], "Neu")
        self.assertEqual(geladen["stufe"], 2)
        self.assertEqual(geladen["disziplin"], "Flächensuche")

    def test_teilnehmer_neuanlage_ist_standardmaessig_nicht_bezahlt(self):
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="A", vorname="A", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1))
        self.assertEqual(get_teilnehmer(self.conn, tid)["bezahlt"], 0)

    def test_gegenstand_zuordnung_ohne_zuweisung_ist_frei_kein_default(self):
        # Ohne explizite Zuordnung ("frei") liefert gegenstand_fuer_disziplin für KEINE
        # Disziplin einen Treffer - es gibt bewusst keine automatische Zuordnung nach
        # Position (früher: Gegenstand 1 immer Trümmerfeld usw.).
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="A", vorname="A", rufname_hund="H", art="DK", stufe=1, startnummer=1,
            gegenstand_1="Korken", gegenstand_2="Metall", gegenstand_3="Silber"))
        t = get_teilnehmer(self.conn, tid)
        self.assertIsNone(gegenstand_fuer_disziplin(t, "Trümmerfeld"))
        self.assertIsNone(gegenstand_fuer_disziplin(t, "Flächensuche"))
        self.assertIsNone(gegenstand_fuer_disziplin(t, "Behältnisstrecke"))

    def test_gegenstand_zuordnung_frei_waehlbar_unabhaengig_von_position(self):
        # Die Zuordnung ist frei wählbar - Gegenstand 2 kann z.B. der Trümmerfeld-Disziplin
        # zugeordnet werden, obwohl er an Position 2 (nicht 1) steht.
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="A", vorname="A", rufname_hund="H", art="DK", stufe=1, startnummer=1,
            gegenstand_1="Korken", gegenstand_1_disziplin="Behältnisstrecke",
            gegenstand_2="Metall", gegenstand_2_disziplin="Trümmerfeld",
            gegenstand_3="Silber",  # bleibt frei
        ))
        t = get_teilnehmer(self.conn, tid)
        self.assertEqual(gegenstand_fuer_disziplin(t, "Trümmerfeld"), "Metall")
        self.assertEqual(gegenstand_fuer_disziplin(t, "Behältnisstrecke"), "Korken")
        self.assertIsNone(gegenstand_fuer_disziplin(t, "Flächensuche"))

    def test_teilnehmer_bezahlt_ueber_neuanlage_und_bearbeiten_setzbar(self):
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="A", vorname="A", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1, bezahlt=True))
        self.assertEqual(get_teilnehmer(self.conn, tid)["bezahlt"], 1)

        update_teilnehmer(self.conn, tid, NeuerTeilnehmer(
            nachname="A", vorname="A", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1, bezahlt=False))
        self.assertEqual(get_teilnehmer(self.conn, tid)["bezahlt"], 0)

    def test_setze_bezahlt_aendert_nur_den_bezahlt_status(self):
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="A", vorname="A", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1))
        setze_bezahlt(self.conn, tid, True)
        geladen = get_teilnehmer(self.conn, tid)
        self.assertEqual(geladen["bezahlt"], 1)
        self.assertEqual(geladen["nachname"], "A")

        setze_bezahlt(self.conn, tid, False)
        self.assertEqual(get_teilnehmer(self.conn, tid)["bezahlt"], 0)

    # --- "keine Teilnahme" (Nutzerwunsch 02.10.2026) ---------------------------

    def _zwei_ed1_teilnehmer(self):
        a = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Anwesend", vorname="A", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1))
        b = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Fehlt", vorname="B", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=2))
        return a, b

    def test_setze_keine_teilnahme_filtert_nur_bei_nur_teilnehmende(self):
        a, b = self._zwei_ed1_teilnehmer()
        self.assertEqual(get_teilnehmer(self.conn, b)["keine_teilnahme"], 0)
        setze_keine_teilnahme(self.conn, b, True)
        self.assertEqual(get_teilnehmer(self.conn, b)["keine_teilnahme"], 1)
        self.assertEqual([t["id"] for t in list_teilnehmer(self.conn)], [a, b])
        self.assertEqual([t["id"] for t in list_teilnehmer(self.conn, nur_teilnehmende=True)], [a])
        # Startnummer bleibt reserviert.
        self.assertIn(2, vergebene_startnummern(self.conn))
        setze_keine_teilnahme(self.conn, b, False)
        self.assertEqual([t["id"] for t in list_teilnehmer(self.conn, nur_teilnehmende=True)], [a, b])

    def test_bearbeiten_setzt_keine_teilnahme_nicht_zurueck(self):
        _, b = self._zwei_ed1_teilnehmer()
        setze_keine_teilnahme(self.conn, b, True)
        update_teilnehmer(self.conn, b, NeuerTeilnehmer(
            nachname="Fehlt", vorname="Neu", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=2))
        self.assertEqual(get_teilnehmer(self.conn, b)["keine_teilnahme"], 1)

    def test_hat_erfasste_ergebnisse(self):
        a, b = self._zwei_ed1_teilnehmer()
        self.assertFalse(hat_erfasste_ergebnisse(self.conn, a))
        eintragen_ergebnis(self.conn, a, "Trümmerfeld", 50, 35)
        self.assertTrue(hat_erfasste_ergebnisse(self.conn, a))
        setze_ergebnis_status(self.conn, b, disqualifiziert=False, abbruch=True)
        self.assertTrue(hat_erfasste_ergebnisse(self.conn, b))
        setze_ergebnis_status(self.conn, b, disqualifiziert=True, abbruch=False)
        self.assertTrue(hat_erfasste_ergebnisse(self.conn, b))

    def test_keine_teilnahme_faellt_aus_auswertung_und_zaehlt_nicht_als_starter(self):
        a, b = self._zwei_ed1_teilnehmer()
        eintragen_ergebnis(self.conn, a, "Trümmerfeld", 50, 35)
        eintragen_ergebnis(self.conn, b, "Trümmerfeld", 55, 38)
        fertig, _ = berechne_auswertung(self.conn)
        self.assertEqual(fertig[0].von_startern, 2)

        setze_keine_teilnahme(self.conn, b, True)
        fertig, ausstehend = berechne_auswertung(self.conn)
        self.assertEqual([t.id for t in fertig], [str(a)])
        self.assertEqual(fertig[0].von_startern, 1)
        self.assertEqual(ausstehend, [])

        # Zurücknehmen: das gespeicherte Ergebnis ist wieder wirksam.
        setze_keine_teilnahme(self.conn, b, False)
        fertig, _ = berechne_auswertung(self.conn)
        self.assertEqual({t.id for t in fertig}, {str(a), str(b)})

    def test_keine_teilnahme_nicht_in_ausstehend_und_lk_uebersicht(self):
        a, b = self._zwei_ed1_teilnehmer()
        setze_keine_teilnahme(self.conn, b, True)
        _, ausstehend = berechne_auswertung(self.conn)
        self.assertEqual([t["id"] for t in ausstehend], [a])
        self.assertEqual(berechne_teilnehmer_lk_uebersicht(self.conn)["ed"][1]["Trümmerfeld"], 1)
        setze_keine_teilnahme(self.conn, a, True)
        self.assertEqual(alle_leistungsklassen(self.conn), [])

    def test_migration_ergaenzt_keine_teilnahme_spalte_in_alter_termin_datei(self):
        self._lege_alte_teilnehmer_tabelle_an()
        self.conn.execute(
            "INSERT INTO teilnehmer (nachname, vorname, rufname_hund, art, stufe, disziplin, startnummer) "
            "VALUES ('Alt', 'Vorname', 'Hund', 'ED', 1, 'Trümmerfeld', 1)"
        )
        self.conn.commit()

        conn = self._neu_verbinden()
        alt = list_teilnehmer(conn)[0]
        self.assertEqual(alt["keine_teilnahme"], 0)
        self.assertEqual(len(list_teilnehmer(conn, nur_teilnehmende=True)), 1)
        setze_keine_teilnahme(conn, alt["id"], True)
        self.assertEqual(list_teilnehmer(conn, nur_teilnehmende=True), [])

    def test_migration_ergaenzt_bezahlt_und_gegenstand_zuordnung_spalten_in_alter_termin_datei(self):
        # Simuliert eine Termin-Datei, die vor Einführung der Bezahlt-Markierung UND der
        # Gegenstand-Disziplin-Zuordnung angelegt wurde (Tabelle "teilnehmer" ohne diese
        # Spalten) - init_db muss sie nachträglich ergänzen, ohne bestehende Daten zu
        # verlieren. Bestehende Teilnehmer gelten dabei als "noch nicht bezahlt" und ihre
        # Gegenstände als "frei" (NULL), nicht als automatisch einer Disziplin zugeordnet.
        self._lege_alte_teilnehmer_tabelle_an()
        self.conn.execute(
            "INSERT INTO teilnehmer (nachname, vorname, rufname_hund, art, stufe, disziplin, startnummer, gegenstand_1) "
            "VALUES ('Alt', 'Vorname', 'Hund', 'ED', 1, 'Trümmerfeld', 1, 'Korken')"
        )
        self.conn.commit()

        conn = self._neu_verbinden()
        alt = list_teilnehmer(conn)[0]
        self.assertEqual(alt["nachname"], "Alt")
        self.assertEqual(alt["bezahlt"], 0)
        self.assertIsNone(alt["gegenstand_1_disziplin"])
        self.assertIsNone(gegenstand_fuer_disziplin(alt, "Trümmerfeld"))
        # setze_bezahlt/update_teilnehmer funktionieren danach ganz normal weiter.
        setze_bezahlt(conn, alt["id"], True)
        self.assertEqual(get_teilnehmer(conn, alt["id"])["bezahlt"], 1)
        update_teilnehmer(conn, alt["id"], NeuerTeilnehmer(
            nachname="Alt", vorname="Vorname", rufname_hund="Hund", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1, gegenstand_1="Korken", gegenstand_1_disziplin="Trümmerfeld",
        ))
        self.assertEqual(get_teilnehmer(conn, alt["id"])["gegenstand_1_disziplin"], "Trümmerfeld")

    def test_migration_ergaenzt_verwaltungs_und_kontaktfelder_in_alter_termin_datei(self):
        # Simuliert eine Termin-Datei, die vor Einführung der Verwaltungs-/Kontaktdaten
        # (Verband, Mitgliedsnummer, Wurftag, Straße, Hausnummer, PLZ, Ort, E-Mail,
        # Telefon) angelegt wurde - init_db muss sie nachträglich ergänzen, ohne
        # bestehende Daten zu verlieren. Bestehende Teilnehmer gelten dabei als ohne
        # hinterlegte Verwaltungs-/Kontaktdaten (NULL), nicht mit irgendeinem Default.
        self._lege_alte_teilnehmer_tabelle_an(", bezahlt INTEGER NOT NULL DEFAULT 0")
        self.conn.execute(
            "INSERT INTO teilnehmer (nachname, vorname, rufname_hund, art, stufe, disziplin, startnummer) "
            "VALUES ('Alt', 'Vorname', 'Hund', 'ED', 1, 'Trümmerfeld', 1)"
        )
        self.conn.commit()

        conn = self._neu_verbinden()
        alt = list_teilnehmer(conn)[0]
        self.assertEqual(alt["nachname"], "Alt")
        for spalte in (
            "verband", "mitgliedsnummer", "wurftag", "strasse", "hausnummer", "plz", "ort", "email", "telefon",
        ):
            self.assertIsNone(alt[spalte])
        # update_teilnehmer funktioniert danach ganz normal weiter, auch für die neuen Felder.
        update_teilnehmer(conn, alt["id"], NeuerTeilnehmer(
            nachname="Alt", vorname="Vorname", rufname_hund="Hund", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1, plz="61479", ort="Höppern",
        ))
        aktualisiert = get_teilnehmer(conn, alt["id"])
        self.assertEqual(aktualisiert["plz"], "61479")
        self.assertEqual(aktualisiert["ort"], "Höppern")

    def test_teilnehmer_verwaltungs_und_kontaktfelder_werden_gespeichert(self):
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Holst", vorname="Katrin", rufname_hund="Freda",
            art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=4,
            verband="VDH", mitgliedsnummer="12345", wurftag="2023-04-01",
            strasse="Hauptstraße", hausnummer="12a", plz="61479", ort="Höppern",
            email="katrin.holst@example.com", telefon="06171 123456",
        ))
        t = get_teilnehmer(self.conn, tid)
        self.assertEqual(t["verband"], "VDH")
        self.assertEqual(t["mitgliedsnummer"], "12345")
        self.assertEqual(t["wurftag"], "2023-04-01")
        self.assertEqual(t["strasse"], "Hauptstraße")
        self.assertEqual(t["hausnummer"], "12a")
        self.assertEqual(t["plz"], "61479")
        self.assertEqual(t["ort"], "Höppern")
        self.assertEqual(t["email"], "katrin.holst@example.com")
        self.assertEqual(t["telefon"], "06171 123456")

        # Alle neuen Felder sind optional - ohne Angabe bleiben sie NULL.
        tid2 = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Ohne", vorname="Zusatzdaten", rufname_hund="Bello",
            art="DK", stufe=2, startnummer=5,
        ))
        t2 = get_teilnehmer(self.conn, tid2)
        for spalte in (
            "verband", "mitgliedsnummer", "wurftag", "strasse", "hausnummer", "plz", "ort", "email", "telefon",
        ):
            self.assertIsNone(t2[spalte])

    def test_teilnehmer_rasse_tollwutimpfung_und_halter_werden_gespeichert(self):
        # Nutzerwunsch (20.09., Anmerkung zum Programm): Rasse/Tollwutimpfung stehen auf
        # dem echten Meldeformular, ebenso ein eigener Halter-Block ("falls abweichend
        # von Teilnehmer"), der bewusst NUR befüllt wird, wenn der Halter tatsächlich
        # eine andere Person als der Hundeführer ist.
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Holst", vorname="Katrin", rufname_hund="Freda",
            art="ED", stufe=1, disziplin="Trümmerfeld", startnummer=4,
            rasse="Labrador Retriever", tollwutimpfung_bis="2027-05-01",
            halter_vorname="Peter", halter_nachname="Holst",
            halter_strasse="Nebenweg", halter_hausnummer="3",
            halter_plz="61479", halter_ort="Höppern",
            halter_mitgliedsverein="SGV Köppern e.V.", halter_mitgliedsnummer="98765",
            halter_lu_nr="LU-42",
        ))
        t = get_teilnehmer(self.conn, tid)
        self.assertEqual(t["rasse"], "Labrador Retriever")
        self.assertEqual(t["tollwutimpfung_bis"], "2027-05-01")
        self.assertEqual(t["halter_vorname"], "Peter")
        self.assertEqual(t["halter_nachname"], "Holst")
        self.assertEqual(t["halter_strasse"], "Nebenweg")
        self.assertEqual(t["halter_hausnummer"], "3")
        self.assertEqual(t["halter_plz"], "61479")
        self.assertEqual(t["halter_ort"], "Höppern")
        self.assertEqual(t["halter_mitgliedsverein"], "SGV Köppern e.V.")
        self.assertEqual(t["halter_mitgliedsnummer"], "98765")
        self.assertEqual(t["halter_lu_nr"], "LU-42")

        # Ohne abweichenden Halter (Normalfall) bleiben alle Halter-Felder NULL.
        tid2 = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Ohne", vorname="Halter", rufname_hund="Bello", art="DK", stufe=2, startnummer=5,
        ))
        t2 = get_teilnehmer(self.conn, tid2)
        for spalte in (
            "rasse", "tollwutimpfung_bis", "halter_vorname", "halter_nachname", "halter_strasse",
            "halter_hausnummer", "halter_plz", "halter_ort", "halter_mitgliedsverein",
            "halter_mitgliedsnummer", "halter_lu_nr",
        ):
            self.assertIsNone(t2[spalte])

    def test_migration_ergaenzt_rasse_tollwutimpfung_und_halterfelder_in_alter_termin_datei(self):
        # Simuliert eine Termin-Datei von vor Einführung von Rasse/Tollwutimpfung/Halter-
        # Block (Tabelle "teilnehmer" mit allen ZUVOR bereits vorhandenen, aber ohne die
        # NEUEN Spalten) - init_db muss sie nachträglich ergänzen, ohne bestehende Daten
        # zu verlieren.
        self._lege_alte_teilnehmer_tabelle_an(
            ", bezahlt INTEGER NOT NULL DEFAULT 0, gegenstand_1_disziplin TEXT, "
            "gegenstand_2_disziplin TEXT, gegenstand_3_disziplin TEXT, verband TEXT, "
            "mitgliedsnummer TEXT, wurftag TEXT, strasse TEXT, hausnummer TEXT, plz TEXT, "
            "ort TEXT, email TEXT, telefon TEXT"
        )
        self.conn.execute(
            "INSERT INTO teilnehmer (nachname, vorname, rufname_hund, art, stufe, disziplin, startnummer) "
            "VALUES ('Alt', 'Vorname', 'Hund', 'ED', 1, 'Trümmerfeld', 1)"
        )
        self.conn.commit()

        conn = self._neu_verbinden()
        alt = list_teilnehmer(conn)[0]
        self.assertEqual(alt["nachname"], "Alt")
        for spalte in (
            "rasse", "tollwutimpfung_bis", "halter_vorname", "halter_nachname", "halter_strasse",
            "halter_hausnummer", "halter_plz", "halter_ort", "halter_mitgliedsverein",
            "halter_mitgliedsnummer", "halter_lu_nr",
        ):
            self.assertIsNone(alt[spalte])
        # update_teilnehmer funktioniert danach ganz normal weiter, auch für die neuen Felder.
        update_teilnehmer(conn, alt["id"], NeuerTeilnehmer(
            nachname="Alt", vorname="Vorname", rufname_hund="Hund", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1, rasse="Beagle", halter_vorname="Peter",
        ))
        aktualisiert = get_teilnehmer(conn, alt["id"])
        self.assertEqual(aktualisiert["rasse"], "Beagle")
        self.assertEqual(aktualisiert["halter_vorname"], "Peter")

    def test_migration_ergaenzt_geburtsdatum_spalte_in_alter_termin_datei(self):
        # Nutzerwunsch (21.09., Rückmeldung "Statistik/Jugendliche"): init_db muss das neue
        # Feld 'geburtsdatum' (Grundlage für ist_jugendlicher()) in einer bereits vorher
        # angelegten Termin-Datei/-Datenbank nachträglich ergänzen, ohne bestehende Daten
        # zu verlieren. Simuliert eine Termin-Datei von VOR dieser Migration, aber MIT den
        # bereits vorher vorhandenen Rasse/Tollwutimpfung/Halter-Feldern (die kamen früher
        # dazu, siehe vorheriger Test).
        self._lege_alte_teilnehmer_tabelle_an(
            ", bezahlt INTEGER NOT NULL DEFAULT 0, gegenstand_1_disziplin TEXT, "
            "gegenstand_2_disziplin TEXT, gegenstand_3_disziplin TEXT, verband TEXT, "
            "mitgliedsnummer TEXT, wurftag TEXT, strasse TEXT, hausnummer TEXT, plz TEXT, "
            "ort TEXT, email TEXT, telefon TEXT, rasse TEXT, tollwutimpfung_bis TEXT, "
            "halter_vorname TEXT, halter_nachname TEXT, halter_strasse TEXT, "
            "halter_hausnummer TEXT, halter_plz TEXT, halter_ort TEXT, "
            "halter_mitgliedsverein TEXT, halter_mitgliedsnummer TEXT, halter_lu_nr TEXT"
        )
        self.conn.execute(
            "INSERT INTO teilnehmer (nachname, vorname, rufname_hund, art, stufe, disziplin, startnummer) "
            "VALUES ('Alt', 'Vorname', 'Hund', 'ED', 1, 'Trümmerfeld', 1)"
        )
        self.conn.commit()

        conn = self._neu_verbinden()
        alt = list_teilnehmer(conn)[0]
        self.assertEqual(alt["nachname"], "Alt")
        self.assertIsNone(alt["geburtsdatum"])
        # update_teilnehmer funktioniert danach ganz normal weiter, auch für das neue Feld.
        update_teilnehmer(conn, alt["id"], NeuerTeilnehmer(
            nachname="Alt", vorname="Vorname", rufname_hund="Hund", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1, geburtsdatum="2010-05-01",
        ))
        self.assertEqual(get_teilnehmer(conn, alt["id"])["geburtsdatum"], "2010-05-01")

    def test_ist_jugendlicher_alterskriterium(self):
        # Nutzerwunsch (21.09.): unter 18 Jahre am Prüfungstag (Stichtag), nicht am
        # heutigen Tag - reine Datumsrechnung, braucht keine Datenbank.
        self.assertTrue(ist_jugendlicher("2010-01-01", "2026-09-19"))  # 16 Jahre
        self.assertFalse(ist_jugendlicher("2000-01-01", "2026-09-19"))  # 26 Jahre
        # Geburtstag ist genau der Stichtag: an diesem Tag bereits (gerade) volljährig.
        self.assertFalse(ist_jugendlicher("2008-09-19", "2026-09-19"))  # wird an diesem Tag 18
        # Einen Tag vor dem 18. Geburtstag noch minderjährig.
        self.assertTrue(ist_jugendlicher("2008-09-20", "2026-09-19"))
        # Fehlende/nicht lesbare Werte liefern sicher False statt eines Fehlers.
        self.assertFalse(ist_jugendlicher(None, "2026-09-19"))
        self.assertFalse(ist_jugendlicher("2010-01-01", None))
        self.assertFalse(ist_jugendlicher("keine-datumsangabe", "2026-09-19"))
        # Codeprüfung 22.09. (M5): ein Altbestand in TT.MM.JJJJ wird ebenfalls gelesen,
        # statt still als "nicht jugendlich" zu zählen.
        self.assertTrue(ist_jugendlicher("01.01.2010", "2026-09-19"))
        self.assertTrue(ist_jugendlicher("2010-01-01", "19.09.2026"))

    def test_importiere_teilnehmer_aus_csv_uebernimmt_und_normalisiert_datumsfelder(self):
        # Codeprüfung 22.09. (M5/M6): geburtsdatum wird jetzt importiert, TT.MM.JJJJ wird
        # in JJJJ-MM-TT umgewandelt, ein ungültiges Datum überspringt die Zeile.
        fd, pfad = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        with open(pfad, "w", newline="", encoding="utf-8") as f:
            f.write(
                "nachname,vorname,rufname_hund,art,stufe,disziplin,geburtsdatum,wurftag,tollwutimpfung_bis\n"
                "Jung,Jana,Rex,DK,1,,1.5.2010,01.04.2023,2027-05-01\n"
                "Falsch,Fritz,Bello,DK,1,,,,31.02.2027\n"
            )
        try:
            ergebnis = importiere_teilnehmer_aus_csv(self.conn, pfad)
            self.assertEqual(ergebnis.importiert, 1)
            self.assertEqual(len(ergebnis.fehler), 1)
            self.assertIn("Zeile 3", ergebnis.fehler[0])
            self.assertIn("Tollwutimpfung", ergebnis.fehler[0])
            jung = list_teilnehmer(self.conn)[0]
            self.assertEqual(jung["geburtsdatum"], "2010-05-01")
            self.assertEqual(jung["wurftag"], "2023-04-01")
            self.assertEqual(jung["tollwutimpfung_bis"], "2027-05-01")
        finally:
            os.remove(pfad)

    def test_beispiel_csv_auf_der_projektseite_importiert_fehlerfrei(self):
        # docs/beispiel_teilnehmer.csv wird auf der Projektseite, im Handbuch und in der
        # App-Hilfe zum Ausprobieren angeboten (27.09.2026) - sie muss zu CSV_IMPORT_SPALTEN
        # und den Prüfregeln passen, auch wenn sich diese später ändern.
        pfad = pathlib.Path(__file__).resolve().parent / "docs" / "beispiel_teilnehmer.csv"
        ergebnis = importiere_teilnehmer_aus_csv(self.conn, str(pfad))
        self.assertEqual(ergebnis.fehler, [])
        self.assertEqual(ergebnis.importiert, 20)
        teilnehmer = list_teilnehmer(self.conn)
        self.assertEqual(sum(t["art"] == "DK" for t in teilnehmer), 6)
        ed_kombinationen = {(t["stufe"], t["disziplin"]) for t in teilnehmer if t["art"] == "ED"}
        self.assertEqual(len(ed_kombinationen), 9)  # jede LK mit jeder Disziplin

    def test_importiere_teilnehmer_aus_csv_legt_teilnehmer_an(self):
        # Nutzerwunsch (20.09.): Meldeformulare per KI-System in eine CSV umwandeln lassen
        # (siehe FormularImportTab/_formular_import_prompt() in app.py) und diese CSV hier
        # importieren, statt Teilnehmer von Hand abzutippen.
        # Eigene temporäre Datei statt einer Ableitung aus self.pfad (das existiert bei
        # TestDatenbankPostgres nicht - dort setzt _PostgresBackendMixin.setUp() kein
        # self.pfad, da es dort keine SQLite-Datei gibt; die CSV-Datei selbst hat mit dem
        # jeweiligen Datenbank-Backend ohnehin nichts zu tun, siehe CI-Fund in Fortschritt.md).
        fd, pfad = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        with open(pfad, "w", newline="", encoding="utf-8") as f:
            f.write(
                "nachname,vorname,rufname_hund,art,stufe,disziplin,verein,rasse,halter_vorname\n"
                "Holst,Katrin,Freda,ED,1,Trümmerfeld,SGV Köppern e.V.,Labrador,\n"
                "Meier,Jan,Rex,DK,2,,SGV Köppern e.V.,,Peter Meier\n"
            )
        try:
            ergebnis = importiere_teilnehmer_aus_csv(self.conn, pfad)
            self.assertEqual(ergebnis.importiert, 2)
            self.assertEqual(ergebnis.fehler, [])
            teilnehmer = {t["nachname"]: t for t in list_teilnehmer(self.conn)}
            self.assertEqual(teilnehmer["Holst"]["art"], "ED")
            self.assertEqual(teilnehmer["Holst"]["disziplin"], "Trümmerfeld")
            self.assertEqual(teilnehmer["Holst"]["rasse"], "Labrador")
            self.assertEqual(teilnehmer["Meier"]["art"], "DK")
            self.assertIsNone(teilnehmer["Meier"]["disziplin"])
            self.assertEqual(teilnehmer["Meier"]["halter_vorname"], "Peter Meier")
        finally:
            os.remove(pfad)

    def test_importiere_teilnehmer_aus_csv_ueberspringt_fehlerhafte_zeile_und_importiert_rest(self):
        # Eigene temporäre Datei statt Ableitung aus self.pfad, siehe Kommentar im
        # vorigen Test.
        fd, pfad = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        with open(pfad, "w", newline="", encoding="utf-8") as f:
            f.write(
                "nachname,vorname,rufname_hund,art,stufe,disziplin\n"
                "Gut,Erster,Hund1,ED,1,Trümmerfeld\n"
                # Fehlt: rufname_hund
                ",Zweiter,,DK,1,\n"
                # Ungültige Art
                "Schlecht,Dritter,Hund3,XX,1,\n"
                "Gut,Vierter,Hund4,DK,3,\n"
            )
        try:
            ergebnis = importiere_teilnehmer_aus_csv(self.conn, pfad)
            self.assertEqual(ergebnis.importiert, 2)
            self.assertEqual(len(ergebnis.fehler), 2)
            self.assertIn("Zeile 3", ergebnis.fehler[0])
            self.assertIn("Zeile 4", ergebnis.fehler[1])
            namen = {t["nachname"] for t in list_teilnehmer(self.conn)}
            self.assertEqual(namen, {"Gut"})
        finally:
            os.remove(pfad)

    def test_importiere_teilnehmer_aus_csv_ueberspringt_ungueltiges_geschlecht(self):
        # Regression: geschlecht wurde bisher nicht validiert, sodass ein von einer KI
        # gelieferter Wert wie "weiblich" statt "Hündin"/"Rüde" eine sqlite3.IntegrityError
        # auslöste, die NICHT vom try/except ValueError abgefangen wurde - dadurch brach der
        # komplette Import ab, statt nur die eine Zeile zu überspringen (im Widerspruch zum
        # eigenen Docstring von importiere_teilnehmer_aus_csv()). Siehe Fortschritt.md.
        # Eigene temporäre Datei statt Ableitung aus self.pfad, siehe Kommentar im
        # ersten CSV-Import-Test oben.
        fd, pfad = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        with open(pfad, "w", newline="", encoding="utf-8") as f:
            f.write(
                "nachname,vorname,rufname_hund,art,stufe,disziplin,geschlecht\n"
                "Schlecht,Erster,Hund1,ED,1,Trümmerfeld,weiblich\n"
                "Gut,Zweiter,Hund2,DK,2,,Hündin\n"
            )
        try:
            ergebnis = importiere_teilnehmer_aus_csv(self.conn, pfad)
            self.assertEqual(ergebnis.importiert, 1)
            self.assertEqual(len(ergebnis.fehler), 1)
            self.assertIn("Zeile 2", ergebnis.fehler[0])
            self.assertIn("Geschlecht", ergebnis.fehler[0])
            namen = {t["nachname"] for t in list_teilnehmer(self.conn)}
            self.assertEqual(namen, {"Gut"})
        finally:
            os.remove(pfad)

    def test_importiere_teilnehmer_aus_csv_liest_windows_kodierung(self):
        # Eine mit Windows-ANSI statt UTF-8 gespeicherte CSV-Datei (auf deutschem Windows
        # beim "CSV speichern unter" in Excel der Standard). Ursprünglich (QS-Fund 21.09.)
        # ein Absturz, danach ein sauberer Abbruch mit Fehlermeldung; seit dem UX-Test
        # 02.10.2026 (U10/N1) wird die Datei stattdessen als Windows-1252 gelesen und
        # vollständig importiert - wie beim OMA-Import. Viele Zeilen, damit der Fall
        # "Sonderzeichen erst weit hinten in der Datei" mit abgedeckt ist.
        fd, pfad = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        with open(pfad, "wb") as f:
            # Komplett Windows-1252 wie Excel "CSV (Trennzeichen-getrennt)" (UX-Test U10).
            f.write("nachname,vorname,rufname_hund,art,stufe,disziplin\n".encode("cp1252"))
            for i in range(300):
                f.write(f"Gut{i},Vorname{i},Hund{i},ED,1,Trümmerfeld\n".encode("cp1252"))
            # Eine mit Windows-1252 statt UTF-8 kodierte Zeile (enthält ein ü als 0xFC,
            # in UTF-8 ungültig als Fortsetzungsbyte) - löst beim Lesen als UTF-8 einen
            # UnicodeDecodeError aus.
            f.write("Schlecht,Zweiter,H\xfcndchen,ED,1,Trümmerfeld\n".encode("cp1252"))
        try:
            ergebnis = importiere_teilnehmer_aus_csv(self.conn, pfad)
            # UX-Test 02.10.2026, U10/N1: nicht-UTF-8-Dateien (Excel "CSV (Trennzeichen-
            # getrennt)" speichert Windows-1252) werden jetzt als Windows-1252 gelesen,
            # statt mit einer Fehlermeldung abzubrechen - wie beim OMA-Import.
            self.assertEqual(ergebnis.fehler, [])
            self.assertEqual(ergebnis.importiert, 301)
            hunde = {t["rufname_hund"] for t in list_teilnehmer(self.conn)}
            self.assertIn("H\xfcndchen", hunde)
        finally:
            os.remove(pfad)

    def test_importiere_teilnehmer_aus_csv_mit_semikolon_wie_excel(self):
        # UX-Test 02.10.2026, U10: deutsches Excel trennt mit Semikolon.
        fd, pfad = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        with open(pfad, "w", newline="", encoding="cp1252") as f:
            f.write("nachname;vorname;rufname_hund;art;stufe;disziplin;verein\r\n")
            f.write("Müller;Jörg;Bärli;ED;1;Trümmerfeld;SV Köln, Süd\r\n")
        try:
            ergebnis = importiere_teilnehmer_aus_csv(self.conn, pfad)
        finally:
            os.remove(pfad)
        self.assertEqual((ergebnis.importiert, ergebnis.fehler), (1, []))
        t = list_teilnehmer(self.conn)[0]
        self.assertEqual((t["nachname"], t["rufname_hund"], t["verein"]), ("Müller", "Bärli", "SV Köln, Süd"))

    def test_teilnehmer_csv_export_und_wieder_import(self):
        # UX-Test 02.10.2026, N1: Export Excel-freundlich (Semikolon, BOM, TT.MM.JJJJ)
        # mit Startnummer/Bezahlt/Status; derselbe Export lässt sich wieder einlesen.
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Müller", vorname="Jörg", rufname_hund="Bärli", art="ED", stufe=2,
            disziplin="Flächensuche", startnummer=7, verein="SV Köln; Süd", wurftag="2021-03-12",
            bezahlt=True,
        ))
        abgesagt = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Abs", vorname="Age", rufname_hund="Sagt", art="DK", stufe=1,
        ))
        setze_keine_teilnahme(self.conn, abgesagt, True)
        fd, pfad = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            self.assertEqual(exportiere_teilnehmer_csv(self.conn, pfad), 2)
            with open(pfad, "rb") as f:
                roh = f.read()
            self.assertTrue(roh.startswith(b"\xef\xbb\xbf"))
            text = roh.decode("utf-8-sig")
            kopf = text.splitlines()[0]
            erste = next(z for z in text.splitlines() if "Müller" in z)
            self.assertTrue(kopf.startswith("startnummer;nachname;vorname;"))
            self.assertIn("12.03.2021", erste)
            self.assertIn('"SV Köln; Süd"', erste)
            self.assertTrue(erste.endswith(";ja;"))

            ziel = init_db(os.path.join(tempfile.mkdtemp(), "ziel.sqlite"))
            ergebnis = importiere_teilnehmer_aus_csv(ziel, pfad)
            self.assertEqual((ergebnis.importiert, ergebnis.fehler), (2, []))
            mueller = next(t for t in list_teilnehmer(ziel) if t["nachname"] == "Müller")
            self.assertEqual((mueller["verein"], mueller["wurftag"], mueller["disziplin"]),
                             ("SV Köln; Süd", "2021-03-12", "Flächensuche"))
            ziel.close()
        finally:
            os.remove(pfad)

    def test_csv_export_entschaerft_formeln_und_reimport_ist_verlustfrei(self):
        # Sicherheitsbefund N1 (Marco 03.10.2026: absichern): Werte, die Excel als Formel
        # ausführen würde, bekommen ein "'" vorangestellt; Telefonnummern bleiben; der
        # Re-Import entfernt das "'" wieder.
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="=HYPERLINK(\"http://x\")", vorname="@SUM(1)", rufname_hund="-Rex+1",
            art="ED", stufe=1, disziplin="Trümmerfeld", telefon="+49 170 1234567", verein="-",
            zwingername="'=x",
        ))
        fd, pfad = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            exportiere_teilnehmer_csv(self.conn, pfad)
            with open(pfad, encoding="utf-8-sig") as f:
                zeile = f.read().splitlines()[1]
            self.assertIn("'=HYPERLINK", zeile)
            self.assertIn(";'@SUM(1);", zeile)
            self.assertIn(";'-Rex+1;", zeile)
            self.assertIn(";+49 170 1234567;", zeile)
            ziel = init_db(os.path.join(tempfile.mkdtemp(), "ziel.sqlite"))
            importiere_teilnehmer_aus_csv(ziel, pfad)
            t = list_teilnehmer(ziel)[0]
            self.assertEqual((t["nachname"], t["vorname"], t["rufname_hund"], t["telefon"], t["zwingername"]),
                             ('=HYPERLINK("http://x")', "@SUM(1)", "-Rex+1", "+49 170 1234567", "'=x"))
            ziel.close()
        finally:
            os.remove(pfad)

    def test_csv_import_leere_datei_und_fuehrende_leerzeilen(self):
        fd, pfad = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            with open(pfad, "w", encoding="utf-8") as f:
                f.write("nachname;vorname;rufname_hund;art;stufe;disziplin\n")
            ergebnis = importiere_teilnehmer_aus_csv(self.conn, pfad)
            self.assertEqual(ergebnis.importiert, 0)
            self.assertTrue(any("keine Teilnehmerzeilen" in h for h in ergebnis.hinweise))

            with open(pfad, "w", encoding="utf-8") as f:
                f.write("\n\nnachname;vorname;rufname_hund;art;stufe;disziplin\n"
                        "A;B;C;ED;1;Trümmerfeld\nX;;Y;ED;1;Trümmerfeld\n")
            ergebnis = importiere_teilnehmer_aus_csv(self.conn, pfad)
            self.assertEqual(ergebnis.importiert, 1)
            # Zeilennummer bezieht sich auf die Datei (2 Leerzeilen + Kopf + 1 gute Zeile).
            self.assertTrue(ergebnis.fehler[0].startswith("Zeile 5 (X):"), ergebnis.fehler)
        finally:
            os.remove(pfad)

    def test_csv_vorlage_hat_nur_kopfzeile(self):
        fd, pfad = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            schreibe_csv_vorlage(pfad)
            with open(pfad, encoding="utf-8-sig") as f:
                self.assertEqual(f.read().splitlines(), [";".join(CSV_IMPORT_SPALTEN)])
        finally:
            os.remove(pfad)

    # OMA-Export (Nutzerwunsch 25.09.2026): Aufbau wie die Musterdatei
    # "OMA-ExportGeneric_Spürhundesport_MUSTER.csv" - Metazeile, Tabulator, Windows-1252,
    # mehrfach "RESERVE", "-" als Leerwert.
    OMA_KOPF = [
        "UeID", "Starter_Anrede", "Starter_Vorname", "Starter_Nachname", "Starter_Geburtstag",
        "Starter_EMail", "Starter_Verein", "Starter_Verband", "Starter_MitglNr", "Starter_Land",
    ] + ["RESERVE"] * 5 + [
        "Hund_Rufname", "Hund_Zwingername", "Hund_Rasse", "Hund_Geschlecht", "Hund_Wurftag",
        "Hund_ZBRegNr", "Hund_Chipnummer", "Hund_LBVerband", "Hund_LBNummer",
    ] + ["RESERVE"] * 5 + [
        "Meldung_Status", "Meldung_Mannschaft", "Meldung_Bezahlt", "Meldung_Startgeld",
        "Meldung_Kommentar",
    ] + ["RESERVE"] * 7 + ["SHS_Disziplinen"] + ["RESERVE"] * 5

    def _oma_zeile(self, **werte):
        standard = {
            "UeID": "100001", "Starter_Anrede": "0", "Starter_Vorname": "Max",
            "Starter_Nachname": "Mustermann", "Starter_Geburtstag": "15.06.1980",
            "Starter_EMail": "max@example.org", "Starter_Verein": "Hundesportverein Musterstadt e.V.",
            "Starter_Verband": "BLV", "Starter_MitglNr": "0000 1 234 5678", "Starter_Land": "DEU",
            "Hund_Rufname": "Bella", "Hund_Zwingername": "-", "Hund_Rasse": "Mix",
            "Hund_Geschlecht": "0", "Hund_Wurftag": "10.04.2021", "Hund_ZBRegNr": "-",
            "Hund_Chipnummer": "276000000000001", "Hund_LBVerband": "BLV", "Hund_LBNummer": "10001",
            "Meldung_Status": "1", "Meldung_Mannschaft": "", "Meldung_Bezahlt": "1",
            "Meldung_Startgeld": "15", "Meldung_Kommentar": "", "SHS_Disziplinen": "LK1 Trümmersuche",
        }
        standard.update(werte)
        return "\t".join(standard.get(spalte, "-") if spalte != "RESERVE" else "-" for spalte in self.OMA_KOPF)

    def _oma_datei(self, zeilen, kodierung="cp1252", kopf=None, zeilenende="\r\n", nach_metazeile=""):
        fd, pfad = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        inhalt = "[Spürhundesport,01.05.2027,Hundesportverein Musterstadt e.V. (BLV)]" + zeilenende + nach_metazeile
        inhalt += "\t".join(kopf or self.OMA_KOPF) + zeilenende
        inhalt += "".join(zeile + zeilenende for zeile in zeilen)
        with open(pfad, "wb") as f:
            f.write(inhalt.encode(kodierung))
        self.addCleanup(os.remove, pfad)
        return pfad

    def test_importiere_teilnehmer_aus_oma_uebernimmt_abgestimmte_felder(self):
        pfad = self._oma_datei([
            self._oma_zeile(),
            self._oma_zeile(UeID="100002", Hund_Rufname="Bruno", Hund_Zwingername="",
                            Hund_Rasse="Deutscher Schäferhund", Hund_Geschlecht="1",
                            Hund_Wurftag="20.08.2019", Hund_Chipnummer="276000000000002",
                            Hund_LBNummer="10002", SHS_Disziplinen="LK1 Flächensuche"),
        ])
        ergebnis = importiere_teilnehmer_aus_oma(self.conn, pfad)
        self.assertEqual((ergebnis.importiert, ergebnis.fehler, ergebnis.uebersprungen), (2, [], []))
        teilnehmer = {t["rufname_hund"]: t for t in list_teilnehmer(self.conn)}
        bella, bruno = teilnehmer["Bella"], teilnehmer["Bruno"]
        self.assertEqual(bella["vorname"], "Max")
        self.assertEqual(bella["nachname"], "Mustermann")
        self.assertEqual(bella["geburtsdatum"], "1980-06-15")
        self.assertEqual(bella["email"], "max@example.org")
        self.assertEqual(bella["verein"], "Hundesportverein Musterstadt e.V.")
        self.assertEqual(bella["verband"], "BLV")
        self.assertEqual(bella["mitgliedsnummer"], "0000 1 234 5678")
        self.assertIsNone(bella["zwingername"])  # "-" gilt als leer
        self.assertEqual(bella["rasse"], "Mix")
        self.assertEqual(bella["geschlecht"], "Hündin")
        self.assertEqual(bella["wurftag"], "2021-04-10")
        self.assertEqual(bella["chip_nr"], "276000000000001")
        self.assertEqual(bella["halter_lu_nr"], "10001")
        self.assertEqual((bella["art"], bella["stufe"], bella["disziplin"]), ("ED", 1, "Trümmerfeld"))
        self.assertEqual(bella["bezahlt"], 0)  # Meldung_Bezahlt wird bewusst ignoriert
        self.assertEqual(bruno["rasse"], "Deutscher Schäferhund")
        self.assertEqual(bruno["geschlecht"], "Rüde")
        self.assertEqual((bruno["art"], bruno["stufe"], bruno["disziplin"]), ("ED", 1, "Flächensuche"))

    def test_importiere_teilnehmer_aus_oma_ordnet_alle_disziplinen_zu(self):
        pfad = self._oma_datei([
            self._oma_zeile(Hund_Rufname="A", SHS_Disziplinen="LK2 Behältnissuche"),
            self._oma_zeile(Hund_Rufname="B", SHS_Disziplinen="LK3 Dreikampf"),
            self._oma_zeile(Hund_Rufname="C", SHS_Disziplinen="LK1 Mantrailing"),
            self._oma_zeile(Hund_Rufname="D", SHS_Disziplinen="LK4 Dreikampf"),
        ])
        ergebnis = importiere_teilnehmer_aus_oma(self.conn, pfad)
        self.assertEqual(ergebnis.importiert, 2)
        self.assertEqual(len(ergebnis.fehler), 2)
        self.assertIn("Zeile 5", ergebnis.fehler[0])
        self.assertIn("Disziplin", ergebnis.fehler[0])
        self.assertIn("Zeile 6", ergebnis.fehler[1])
        teilnehmer = {t["rufname_hund"]: t for t in list_teilnehmer(self.conn)}
        self.assertEqual((teilnehmer["A"]["art"], teilnehmer["A"]["stufe"], teilnehmer["A"]["disziplin"]),
                         ("ED", 2, "Behältnisstrecke"))
        self.assertEqual((teilnehmer["B"]["art"], teilnehmer["B"]["stufe"], teilnehmer["B"]["disziplin"]),
                         ("DK", 3, None))

    def test_importiere_teilnehmer_aus_oma_lehnt_nicht_angebotene_pruefung_ab(self):
        # UX-Test 02.10.2026, U4: wie der PDF-Import, sobald angebotene Prüfungen hinterlegt sind.
        set_veranstaltung(self.conn, verein="HSV", datum="2026-11-14",
                          angebotene_pruefungen=pruefungen_als_text(["DK1", "ED2-Behältnisstrecke"]))
        pfad = self._oma_datei([
            self._oma_zeile(Hund_Rufname="A", SHS_Disziplinen="LK2 Behältnissuche"),
            self._oma_zeile(Hund_Rufname="B", SHS_Disziplinen="LK3 Dreikampf"),
        ])
        ergebnis = importiere_teilnehmer_aus_oma(self.conn, pfad)
        self.assertEqual(ergebnis.importiert, 1)
        self.assertEqual(len(ergebnis.fehler), 1)
        self.assertIn("DK-LK 3 wird in diesem Termin nicht angeboten. Bitte mit dem Teilnehmer klären",
                      ergebnis.fehler[0])
        # UX-Nachtest N5: der Freischalt-Hinweis steht nur noch einmal in den Hinweisen.
        self.assertNotIn("Veranstaltungsdaten", ergebnis.fehler[0])
        self.assertEqual(len(ergebnis.hinweise), 1)
        self.assertIn("Veranstaltungsdaten bearbeiten", ergebnis.hinweise[0])
        self.assertEqual([t["rufname_hund"] for t in list_teilnehmer(self.conn)], ["A"])

    def test_importiere_teilnehmer_aus_csv_lehnt_nicht_angebotene_pruefung_ab(self):
        # UX-Test 02.10.2026, U4: CSV wie PDF - nicht angebotene Prüfungen werden abgelehnt.
        set_veranstaltung(self.conn, verein="HSV", datum="2026-11-14",
                          angebotene_pruefungen=pruefungen_als_text(["ED1-Trümmerfeld"]))
        fd, pfad = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        with open(pfad, "w", newline="", encoding="utf-8") as f:
            f.write(
                "nachname,vorname,rufname_hund,art,stufe,disziplin\n"
                "Holst,Katrin,Freda,ED,1,Trümmerfeld\n"
                "Meier,Jan,Rex,ED,3,Flächensuche\n"
            )
        try:
            ergebnis = importiere_teilnehmer_aus_csv(self.conn, pfad)
        finally:
            os.remove(pfad)
        self.assertEqual(ergebnis.importiert, 1)
        self.assertEqual(len(ergebnis.fehler), 1)
        # UX-Nachtest N5: Name in der Meldung, Freischalt-Hinweis nur einmal.
        self.assertIn("Zeile 3 (Jan Meier): Fläche LK 3 wird in diesem Termin nicht angeboten", ergebnis.fehler[0])
        self.assertNotIn("Formular eines anderen Termins", ergebnis.fehler[0])
        self.assertEqual(len(ergebnis.hinweise), 1)
        self.assertIn("Veranstaltungsdaten bearbeiten", ergebnis.hinweise[0])

    def test_csv_import_ueberspringt_bereits_gemeldete(self):
        """UX-Nachtest 03.10.2026, N1: dieselbe Datei zweimal -> keine Doppelten."""
        fd, pfad = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        with open(pfad, "w", newline="", encoding="utf-8") as f:
            f.write(
                "nachname,vorname,rufname_hund,art,stufe,disziplin\n"
                "Holst,Katrin,Freda,ED,1,Trümmerfeld\n"
                "Meier,Jan,Rex,DK,2,\n"
                "Meier,Jan,Rex,DK,2,\n"
            )
        try:
            erstes = importiere_teilnehmer_aus_csv(self.conn, pfad)
            zweites = importiere_teilnehmer_aus_csv(self.conn, pfad)
        finally:
            os.remove(pfad)
        self.assertEqual((erstes.importiert, len(erstes.uebersprungen)), (2, 1))  # Doppel in der Datei
        self.assertEqual((zweites.importiert, len(zweites.uebersprungen)), (0, 3))
        self.assertIn("Zeile 2 (Katrin Holst) mit Freda ist bereits gemeldet", zweites.uebersprungen[0])
        self.assertEqual(len(list_teilnehmer(self.conn)), 2)
        self.assertEqual(zweites.hinweise, [])

    def test_importiere_teilnehmer_aus_csv_ohne_angebote_prueft_nicht_und_weist_darauf_hin(self):
        # UX-Test 02.10.2026, U4 (Marco): ohne hinterlegte Angebote wird wie bisher alles
        # übernommen, aber mit Hinweis.
        fd, pfad = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        with open(pfad, "w", newline="", encoding="utf-8") as f:
            f.write("nachname,vorname,rufname_hund,art,stufe,disziplin\nMeier,Jan,Rex,ED,3,Flächensuche\n")
        try:
            ergebnis = importiere_teilnehmer_aus_csv(self.conn, pfad)
        finally:
            os.remove(pfad)
        self.assertEqual(ergebnis.importiert, 1)
        self.assertEqual(len(ergebnis.hinweise), 1)
        self.assertIn("keine angebotenen Prüfungen hinterlegt", ergebnis.hinweise[0])

    def test_importiere_teilnehmer_aus_oma_ungueltiges_geschlecht_ueberspringt_zeile(self):
        pfad = self._oma_datei([
            self._oma_zeile(Hund_Rufname="A", Hund_Geschlecht="2"),
            self._oma_zeile(Hund_Rufname="B", Hund_Geschlecht=""),
        ])
        ergebnis = importiere_teilnehmer_aus_oma(self.conn, pfad)
        self.assertEqual(ergebnis.importiert, 1)
        self.assertIn("Zeile 3", ergebnis.fehler[0])
        self.assertIn("Geschlecht", ergebnis.fehler[0])
        self.assertIsNone(list_teilnehmer(self.conn)[0]["geschlecht"])

    def test_importiere_teilnehmer_aus_oma_verband_nur_ersatzweise_aus_leistungsheft(self):
        pfad = self._oma_datei([
            self._oma_zeile(Hund_Rufname="A", Starter_Verband="DVG", Hund_LBVerband="BLV"),
            self._oma_zeile(Hund_Rufname="B", Starter_Verband="-", Hund_LBVerband="BLV"),
        ])
        importiere_teilnehmer_aus_oma(self.conn, pfad)
        teilnehmer = {t["rufname_hund"]: t for t in list_teilnehmer(self.conn)}
        self.assertEqual(teilnehmer["A"]["verband"], "DVG")
        self.assertEqual(teilnehmer["B"]["verband"], "BLV")

    def test_importiere_teilnehmer_aus_oma_ueberspringt_bereits_vorhandene_meldungen(self):
        pfad = self._oma_datei([self._oma_zeile(), self._oma_zeile(Starter_Vorname=" max ")])
        erster = importiere_teilnehmer_aus_oma(self.conn, pfad)
        self.assertEqual(erster.importiert, 1)  # zweite Zeile ist Dublette innerhalb der Datei
        self.assertEqual(len(erster.uebersprungen), 1)
        self.assertIn("Zeile 4", erster.uebersprungen[0])
        # Nachmeldung: gleicher Hund in anderer Disziplin ist eine neue Meldung.
        pfad2 = self._oma_datei([self._oma_zeile(), self._oma_zeile(SHS_Disziplinen="LK2 Trümmersuche")])
        zweiter = importiere_teilnehmer_aus_oma(self.conn, pfad2)
        self.assertEqual(zweiter.importiert, 1)
        self.assertEqual(len(zweiter.uebersprungen), 1)
        self.assertEqual(len(list_teilnehmer(self.conn)), 2)

    def test_importiere_teilnehmer_aus_oma_liest_auch_utf8(self):
        pfad = self._oma_datei([self._oma_zeile(Hund_Rasse="Deutscher Schäferhund")], kodierung="utf-8-sig")
        ergebnis = importiere_teilnehmer_aus_oma(self.conn, pfad)
        self.assertEqual(ergebnis.importiert, 1)
        self.assertEqual(list_teilnehmer(self.conn)[0]["rasse"], "Deutscher Schäferhund")

    def test_importiere_teilnehmer_aus_oma_lehnt_andere_datei_ab(self):
        pfad = self._oma_datei(["Holst,Katrin,Freda"], kopf=["nachname,vorname,rufname_hund"])
        ergebnis = importiere_teilnehmer_aus_oma(self.conn, pfad)
        self.assertEqual(ergebnis.importiert, 0)
        self.assertEqual(len(ergebnis.fehler), 1)
        self.assertIn("kein OMA-Export", ergebnis.fehler[0])
        self.assertEqual(list_teilnehmer(self.conn), [])

    # Randfälle aus der Verifikation vom 25.09.2026 (auf Marcos Wunsch behoben):

    def test_importiere_teilnehmer_aus_oma_riesiges_feld_bricht_nicht_ab(self):
        # Vorher: csv.Error "field larger than field limit" als unbehandelte Exception.
        pfad = self._oma_datei([self._oma_zeile(Meldung_Kommentar="x" * 200_000)])
        ergebnis = importiere_teilnehmer_aus_oma(self.conn, pfad)
        self.assertEqual((ergebnis.importiert, ergebnis.fehler), (1, []))

    def test_importiere_teilnehmer_aus_oma_nur_cr_und_leerzeile_nach_metazeile(self):
        # Vorher: irreführende Meldung "kein OMA-Export".
        for zeilenende, nach_metazeile in (("\r", ""), ("\n", ""), ("\r\n", "\r\n"), ("\r", "\r\r")):
            with self.subTest(zeilenende=repr(zeilenende), nach_metazeile=repr(nach_metazeile)):
                for t in list_teilnehmer(self.conn):
                    delete_teilnehmer(self.conn, t["id"])
                pfad = self._oma_datei([self._oma_zeile()], zeilenende=zeilenende, nach_metazeile=nach_metazeile)
                ergebnis = importiere_teilnehmer_aus_oma(self.conn, pfad)
                self.assertEqual((ergebnis.importiert, ergebnis.fehler), (1, []))

    def test_importiere_teilnehmer_aus_oma_meldet_abgeschnittene_zeile_verstaendlich(self):
        # Vorher: "unbekannte Disziplin ''" statt eines Hinweises auf die zu kurze Zeile.
        vollstaendig = self._oma_zeile(Hund_Rufname="A")
        abgeschnitten = "\t".join(self._oma_zeile(Hund_Rufname="B").split("\t")[:20])
        pfad = self._oma_datei([abgeschnitten, vollstaendig])
        ergebnis = importiere_teilnehmer_aus_oma(self.conn, pfad)
        self.assertEqual(ergebnis.importiert, 1)
        self.assertEqual(len(ergebnis.fehler), 1)
        self.assertIn("Zeile 3", ergebnis.fehler[0])
        self.assertIn("unvollständig", ergebnis.fehler[0])
        self.assertNotIn("Disziplin", ergebnis.fehler[0])

    def test_importiere_teilnehmer_aus_csv_riesiges_feld_bricht_sauber_ab(self):
        # Gleicher Randfall im bestehenden Formular-CSV-Import: sauberer Abbruch statt
        # unbehandelter csv.Error.
        fd, pfad = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        self.addCleanup(os.remove, pfad)
        with open(pfad, "w", newline="", encoding="utf-8") as f:
            f.write(
                "nachname,vorname,rufname_hund,art,stufe,disziplin\n"
                "Gut,Erster,Hund1,DK,1,\n"
                f"Gross,Zweiter,{'x' * 200_000},DK,1,\n"
            )
        ergebnis = importiere_teilnehmer_aus_csv(self.conn, pfad)
        self.assertEqual(ergebnis.importiert, 1)
        self.assertEqual(len(ergebnis.fehler), 1)
        self.assertIn("abgebrochen", ergebnis.fehler[0])

    def test_teilnehmer_loeschen_entfernt_auch_ergebnis(self):
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="X", vorname="Y", rufname_hund="Z", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1))
        delete_teilnehmer(self.conn, tid)
        self.assertIsNone(get_teilnehmer(self.conn, tid))
        # Spaltenname statt Positionsindex (row[0]): siehe vergebene_startnummern() in
        # db.py - dieselbe sqlite3.Row-vs-RealDictCursor-Falle, hier im Test gefunden statt
        # in db.py selbst (fiel erst beim echten CI-Lauf gegen PostgreSQL auf, siehe
        # Fortschritt.md).
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) AS anzahl FROM ergebnisse WHERE teilnehmer_id = ?", (tid,)
            ).fetchone()["anzahl"],
            0,
        )

    def test_startnummer_muss_eindeutig_sein(self):
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="A", vorname="A", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=5))
        with self.assertRaises(self.IntegrityErrorTyp):
            add_teilnehmer(self.conn, NeuerTeilnehmer(
                nachname="B", vorname="B", rufname_hund="H", art="ED", stufe=1,
                disziplin="Trümmerfeld", startnummer=5))

    def test_mehrere_teilnehmer_ohne_startnummer_erlaubt(self):
        # NULL ist in SQLite bei UNIQUE mehrfach erlaubt (kein Konflikt zwischen NULLs)
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="A", vorname="A", rufname_hund="H", art="ED", stufe=1, disziplin="Trümmerfeld"))
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="B", vorname="B", rufname_hund="H", art="ED", stufe=1, disziplin="Trümmerfeld"))
        self.assertEqual(len(list_teilnehmer(self.conn)), 2)

    def test_naechste_freie_startnummer(self):
        self.assertEqual(naechste_freie_startnummer(self.conn), 1)
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="A", vorname="A", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1))
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="B", vorname="B", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=2))
        self.assertEqual(naechste_freie_startnummer(self.conn), 3)

    def test_naechste_freie_startnummer_fuellt_luecken(self):
        a = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="A", vorname="A", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1))
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="B", vorname="B", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=3))
        delete_teilnehmer(self.conn, a)
        # Nummer 1 ist jetzt wieder frei (durch Löschen) und kleiner als eine neue "4"
        self.assertEqual(naechste_freie_startnummer(self.conn), 1)

    def test_vergebene_startnummern_ohne_eigene_beim_bearbeiten(self):
        tid = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="A", vorname="A", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=7))
        self.assertEqual(vergebene_startnummern(self.conn), {7})
        self.assertEqual(vergebene_startnummern(self.conn, ausser_teilnehmer_id=tid), set())

    def test_tausche_startnummern_vertauscht_beide_nummern(self):
        a = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="A", vorname="A", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1))
        b = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="B", vorname="B", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=2))
        tausche_startnummern(self.conn, a, b)
        self.assertEqual(get_teilnehmer(self.conn, a)["startnummer"], 2)
        self.assertEqual(get_teilnehmer(self.conn, b)["startnummer"], 1)

    def test_tausche_startnummern_funktioniert_wenn_einer_noch_keine_hat(self):
        # Regression/Nutzerwunsch (20.09.): das darf NICHT an der UNIQUE-Constraint
        # scheitern, auch wenn einer der beiden (oder beide) noch gar keine Startnummer
        # hat (None) - siehe tausche_startnummern() in db.py.
        a = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="A", vorname="A", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=5))
        b = add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="B", vorname="B", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld"))
        tausche_startnummern(self.conn, a, b)
        self.assertIsNone(get_teilnehmer(self.conn, a)["startnummer"])
        self.assertEqual(get_teilnehmer(self.conn, b)["startnummer"], 5)

    def test_teilnehmer_fehlende_pflichtangaben_leer_wenn_vollstaendig(self):
        # ED LK1: genau 1 Gegenstand in der gewählten Disziplin reicht.
        vollstaendig = dict(
            chip_nr="123", art="ED", stufe=1, disziplin="Flächensuche",
            gegenstand_1="Schlüsselbund", gegenstand_1_disziplin="Flächensuche",
            gegenstand_2=None, gegenstand_2_disziplin=None,
            gegenstand_3=None, gegenstand_3_disziplin=None,
        )
        self.assertEqual(teilnehmer_fehlende_pflichtangaben(vollstaendig), [])

    def test_teilnehmer_fehlende_pflichtangaben_ed_meldet_chipnr_und_gegenstand(self):
        unvollstaendig = dict(
            chip_nr=None, art="ED", stufe=2, disziplin="Trümmerfeld",
            gegenstand_1=None, gegenstand_1_disziplin=None,
            gegenstand_2=None, gegenstand_2_disziplin=None,
            gegenstand_3=None, gegenstand_3_disziplin=None,
        )
        self.assertEqual(
            teilnehmer_fehlende_pflichtangaben(unvollstaendig),
            ["Chip-Nr. fehlt", "Gegenstand fehlt"],
        )

    def test_teilnehmer_fehlende_pflichtangaben_ed_braucht_in_jeder_lk_genau_einen_gegenstand(self):
        # Abstimmung 23.09.: ED hat nur eine Suchdisziplin und daher unabhängig von der
        # Leistungsklasse genau einen Gegenstand (früher fälschlich LK-Zahl = Anzahl,
        # was bei LK2/LK3 nie erfüllbar war).
        for stufe in (1, 2, 3):
            with self.subTest(stufe=stufe):
                ein_gegenstand = dict(
                    chip_nr="1", art="ED", stufe=stufe, disziplin="Trümmerfeld",
                    gegenstand_1="Dose", gegenstand_1_disziplin="Trümmerfeld",
                    gegenstand_2=None, gegenstand_2_disziplin=None,
                    gegenstand_3=None, gegenstand_3_disziplin=None,
                )
                self.assertEqual(teilnehmer_fehlende_pflichtangaben(ein_gegenstand), [])
                self.assertIsNone(teilnehmer_gegenstand_hinweis(ein_gegenstand))

    def test_teilnehmer_gegenstand_hinweis_ed_bei_mehr_als_einem_gegenstand(self):
        # Altdaten: bei ED mehr als ein Gegenstand erfasst - nur Hinweis, kein Fehler.
        zwei = dict(
            chip_nr="1", art="ED", stufe=2, disziplin="Trümmerfeld",
            gegenstand_1="Dose", gegenstand_1_disziplin="Trümmerfeld",
            gegenstand_2="Schlüssel", gegenstand_2_disziplin=None,
            gegenstand_3=None, gegenstand_3_disziplin=None,
        )
        self.assertEqual(teilnehmer_fehlende_pflichtangaben(zwei), [])
        self.assertEqual(teilnehmer_gegenstand_hinweis(zwei), "Bei ED ist nur ein Gegenstand vorgesehen")

    def test_teilnehmer_gegenstand_hinweis_ed_gegenstand_einer_anderen_disziplin_zugeordnet(self):
        andere = dict(
            chip_nr="1", art="ED", stufe=1, disziplin="Trümmerfeld",
            gegenstand_1=None, gegenstand_1_disziplin=None,
            gegenstand_2="Dose", gegenstand_2_disziplin="Flächensuche",
            gegenstand_3=None, gegenstand_3_disziplin=None,
        )
        self.assertEqual(teilnehmer_fehlende_pflichtangaben(andere), [])
        self.assertEqual(teilnehmer_gegenstand_hinweis(andere), "Gegenstand der Suchdisziplin nicht zugeordnet")

    def test_teilnehmer_fehlende_pflichtangaben_dk_alles_frei_reicht_mindestanzahl(self):
        # Abstimmung 23.09.: Stehen bei DK alle Gegenstände auf "frei", reicht die
        # Mindestanzahl unterschiedlicher Gegenstände (LK1=1, LK2=2, LK3=3) - ohne jede
        # Meldung, auch ohne Info.
        leer = dict(
            chip_nr="1", art="DK",
            gegenstand_1=None, gegenstand_1_disziplin=None,
            gegenstand_2=None, gegenstand_2_disziplin=None,
            gegenstand_3=None, gegenstand_3_disziplin=None,
        )
        faelle = {
            1: dict(leer, stufe=1, gegenstand_1="X"),
            2: dict(leer, stufe=2, gegenstand_1="X", gegenstand_3="Y"),
            3: dict(leer, stufe=3, gegenstand_1="X", gegenstand_2="Y", gegenstand_3="Z"),
        }
        for stufe, teilnehmer in faelle.items():
            with self.subTest(stufe=stufe):
                self.assertEqual(teilnehmer_fehlende_pflichtangaben(teilnehmer), [])
                self.assertIsNone(teilnehmer_gegenstand_hinweis(teilnehmer))

        lk2_nur_einer = dict(leer, stufe=2, gegenstand_1="X")
        self.assertEqual(
            teilnehmer_fehlende_pflichtangaben(lk2_nur_einer),
            ["Gegenstände unvollständig (Dreikampf)"],
        )
        # Derselbe Text zweimal zählt als ein Gegenstand.
        lk2_zweimal_derselbe = dict(leer, stufe=2, gegenstand_1="X", gegenstand_2="X")
        self.assertEqual(
            teilnehmer_fehlende_pflichtangaben(lk2_zweimal_derselbe),
            ["Gegenstände unvollständig (Dreikampf)"],
        )

    def test_teilnehmer_fehlende_pflichtangaben_dk_lk3_braucht_drei_verschiedene_gegenstaende(self):
        # LK3-Regel (Klärung 16.09., Fortschritt.md): 3 unterschiedliche Gegenstände, je
        # einer Disziplin zugeordnet.
        nur_zwei_verschiedene = dict(
            chip_nr="1", art="DK", stufe=3,
            gegenstand_1="A", gegenstand_1_disziplin="Trümmerfeld",
            gegenstand_2="A", gegenstand_2_disziplin="Flächensuche",
            gegenstand_3="B", gegenstand_3_disziplin="Behältnisstrecke",
        )
        self.assertEqual(teilnehmer_fehlende_pflichtangaben(nur_zwei_verschiedene), ["Gegenstände unvollständig (Dreikampf)"])

        drei_verschiedene = dict(nur_zwei_verschiedene, gegenstand_2="C")
        self.assertEqual(teilnehmer_fehlende_pflichtangaben(drei_verschiedene), [])

    def test_teilnehmer_fehlende_pflichtangaben_dk_lk1_reicht_ein_gegenstand_fuer_alle_disziplinen(self):
        # LK1-Regel: derselbe Gegenstand-Text darf für alle 3 Disziplinen stehen, solange
        # jede der drei Disziplinen einem der drei Felder zugeordnet ist.
        lk1 = dict(
            chip_nr="1", art="DK", stufe=1,
            gegenstand_1="X", gegenstand_1_disziplin="Trümmerfeld",
            gegenstand_2="X", gegenstand_2_disziplin="Flächensuche",
            gegenstand_3="X", gegenstand_3_disziplin="Behältnisstrecke",
        )
        self.assertEqual(teilnehmer_fehlende_pflichtangaben(lk1), [])

        # Rückmeldung (22.09.): Gegenstand_3 hat weiterhin einen Text ("X"), steht aber
        # auf "gesucht in: frei" (disziplin=None) - das ist bewusst KEIN Fehler mehr
        # (die Zuordnung fehlt lediglich, der Gegenstand selbst ist ja erfasst), sondern
        # nur noch eine milde Info über teilnehmer_gegenstand_hinweis().
        nicht_alle_disziplinen_abgedeckt = dict(lk1, gegenstand_3_disziplin=None)
        self.assertEqual(teilnehmer_fehlende_pflichtangaben(nicht_alle_disziplinen_abgedeckt), [])
        self.assertEqual(
            teilnehmer_gegenstand_hinweis(nicht_alle_disziplinen_abgedeckt),
            "Gegenstände den Suchdisziplinen nicht vollständig zugeordnet",
        )

    def test_teilnehmer_gegenstand_hinweis_dk_mischfall_nur_info(self):
        # Abstimmung 23.09.: Sobald eine Disziplin ausgewählt ist, müssen alle 3 belegt
        # sein - ist die Mindestanzahl an Gegenständen erreicht, ist eine unvollständige
        # Zuordnung aber nur ein Hinweis, kein Fehler.
        mischfall = dict(
            chip_nr="1", art="DK", stufe=1,
            gegenstand_1="Schlüssel", gegenstand_1_disziplin="Trümmerfeld",
            gegenstand_2=None, gegenstand_2_disziplin=None,
            gegenstand_3=None, gegenstand_3_disziplin=None,
        )
        self.assertEqual(teilnehmer_fehlende_pflichtangaben(mischfall), [])
        self.assertEqual(
            teilnehmer_gegenstand_hinweis(mischfall),
            "Gegenstände den Suchdisziplinen nicht vollständig zugeordnet",
        )

        # LK2: zwei verschiedene Gegenstände erfasst, allen 3 Disziplinen aber nur einer
        # davon zugeordnet - Mindestanzahl erfüllt, Zuordnung unvollständig -> Info.
        lk2 = dict(
            chip_nr="1", art="DK", stufe=2,
            gegenstand_1="X", gegenstand_1_disziplin="Trümmerfeld",
            gegenstand_2="X", gegenstand_2_disziplin="Flächensuche",
            gegenstand_3="Y", gegenstand_3_disziplin=None,
        )
        self.assertEqual(teilnehmer_fehlende_pflichtangaben(lk2), [])
        self.assertEqual(
            teilnehmer_gegenstand_hinweis(lk2),
            "Gegenstände den Suchdisziplinen nicht vollständig zugeordnet",
        )

    def test_teilnehmer_gegenstand_hinweis_dk_lk1_mit_zwei_zuordnungen_ist_nur_info(self):
        # Abstimmung 23.09.: bei LK1 reicht ein Gegenstand - dass Gegenstand_3 leer ist,
        # ist daher kein Fehler mehr (früher: jedes leere Textfeld = Fehler), sondern nur
        # eine unvollständige Zuordnung (Behältnisstrecke fehlt) -> Info.
        lk1_ohne_dritten_text = dict(
            chip_nr="1", art="DK", stufe=1,
            gegenstand_1="X", gegenstand_1_disziplin="Trümmerfeld",
            gegenstand_2="X", gegenstand_2_disziplin="Flächensuche",
            gegenstand_3=None, gegenstand_3_disziplin=None,
        )
        self.assertEqual(teilnehmer_fehlende_pflichtangaben(lk1_ohne_dritten_text), [])
        self.assertEqual(
            teilnehmer_gegenstand_hinweis(lk1_ohne_dritten_text),
            "Gegenstände den Suchdisziplinen nicht vollständig zugeordnet",
        )

    def test_teilnehmer_gegenstand_hinweis_none_bei_echtem_dk_fehler(self):
        # Fehlt die Mindestanzahl an Gegenständen, ist das ein echter Fehler - die Info
        # entfällt dann (Fehler hat Vorrang).
        lk3_nur_zwei = dict(
            chip_nr="1", art="DK", stufe=3,
            gegenstand_1="X", gegenstand_1_disziplin="Trümmerfeld",
            gegenstand_2="Y", gegenstand_2_disziplin="Flächensuche",
            gegenstand_3=None, gegenstand_3_disziplin=None,
        )
        self.assertEqual(
            teilnehmer_fehlende_pflichtangaben(lk3_nur_zwei),
            ["Gegenstände unvollständig (Dreikampf)"],
        )
        self.assertIsNone(teilnehmer_gegenstand_hinweis(lk3_nur_zwei))

    def test_teilnehmer_gegenstand_hinweis_ed_bei_text_ohne_zuordnung(self):
        # ED-Variante desselben Falls: Text vorhanden, aber "gesucht in: frei".
        text_ohne_zuordnung = dict(
            chip_nr="1", art="ED", stufe=1, disziplin="Flächensuche",
            gegenstand_1="Schlüsselbund", gegenstand_1_disziplin=None,
            gegenstand_2=None, gegenstand_2_disziplin=None,
            gegenstand_3=None, gegenstand_3_disziplin=None,
        )
        self.assertEqual(teilnehmer_fehlende_pflichtangaben(text_ohne_zuordnung), [])
        self.assertEqual(
            teilnehmer_gegenstand_hinweis(text_ohne_zuordnung),
            "Gegenstand der Suchdisziplin nicht zugeordnet",
        )

    def test_teilnehmer_gegenstand_hinweis_none_wenn_vollstaendig_oder_echter_fehler(self):
        vollstaendig = dict(
            chip_nr="123", art="ED", stufe=1, disziplin="Flächensuche",
            gegenstand_1="Schlüsselbund", gegenstand_1_disziplin="Flächensuche",
            gegenstand_2=None, gegenstand_2_disziplin=None,
            gegenstand_3=None, gegenstand_3_disziplin=None,
        )
        self.assertIsNone(teilnehmer_gegenstand_hinweis(vollstaendig))

        text_fehlt = dict(vollstaendig, gegenstand_1=None, gegenstand_1_disziplin=None)
        self.assertIsNone(teilnehmer_gegenstand_hinweis(text_fehlt))

    def test_alle_leistungsklassen_sortiert_und_ohne_duplikate(self):
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="A", vorname="A", rufname_hund="H", art="DK", stufe=2, startnummer=1))
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="B", vorname="B", rufname_hund="H", art="DK", stufe=2, startnummer=2))
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="C", vorname="C", rufname_hund="H", art="ED", stufe=1,
            disziplin="Flächensuche", startnummer=3))
        self.assertEqual(
            alle_leistungsklassen(self.conn),
            ["DK LK 2", "ED LK 1 Flächensuche"],
        )

    def test_teilnehmer_liste_sortiert_nach_startnummer(self):
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Spät", vorname="X", rufname_hund="H1", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=9))
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Früh", vorname="Y", rufname_hund="H2", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=2))
        namen = [t["nachname"] for t in list_teilnehmer(self.conn)]
        self.assertEqual(namen, ["Früh", "Spät"])


def _ohne_kennung(konto):
    """pruefe_login()/benutzer_stand() liefern seit C-1 (03.10.2026) zusätzlich die
    Konto-Kennung für die Session - für Vergleiche der übrigen Felder ausblenden."""
    return None if konto is None else {k: v for k, v in konto.items() if k != "kennung"}


def test_konto_kennung_aendert_sich_bei_neuanlage_und_passwort():
    """C-1: gleiche Kennung für dasselbe Konto, neue bei Neuanlage unter gleichem Namen."""
    import db as _db

    zeile = {"benutzername": "Helfer", "erstellt_am": "2026-10-03T10:00:00", "passwort_hash": "pbkdf2:a$x$1"}
    gleich = dict(zeile, benutzername="helfer")
    anderer_hash = dict(zeile, passwort_hash="pbkdf2:a$y$2")
    assert _db._konto_kennung(zeile) == _db._konto_kennung(gleich)
    assert _db._konto_kennung(zeile) != _db._konto_kennung(anderer_hash)


class TestFremdeTriggerUndViews(unittest.TestCase):
    def test_trigger_und_views_werden_beim_oeffnen_entfernt(self):
        """Sicherheitsprüfung 03.10.2026, H-1 (Codex-Nachweis): ein fremder Trigger setzte
        eingetragene Ergebnisse still auf 0 - init_db entfernt Trigger/Views vorab."""
        import db as _db

        with tempfile.TemporaryDirectory() as ordner:
            pfad = os.path.join(ordner, "fremd.sqlite")
            conn = init_db(pfad)
            tid = add_teilnehmer(conn, NeuerTeilnehmer(
                nachname="A", vorname="B", rufname_hund="H", art="ED", stufe=1,
                disziplin="Flächensuche", startnummer=1))
            conn.execute(
                "CREATE TRIGGER manipulation AFTER UPDATE OF suche_flaechensuche ON ergebnisse "
                "BEGIN UPDATE ergebnisse SET suche_flaechensuche = 0 WHERE teilnehmer_id = NEW.teilnehmer_id; END"
            )
            conn.execute("CREATE VIEW sicht AS SELECT * FROM teilnehmer")
            conn.execute('CREATE TRIGGER "bös""er name" AFTER INSERT ON teilnehmer BEGIN SELECT 1; END')
            conn.commit()
            conn.close()

            conn = init_db(pfad)
            try:
                self.assertEqual(
                    _db.entfernte_fremdobjekte(),
                    ['trigger bös"er name', "trigger manipulation", "view sicht"],
                )
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type IN ('trigger','view')").fetchone()[0], 0
                )
                eintragen_ergebnis(conn, tid, "Flächensuche", 50, 30)
                self.assertEqual(get_ergebnis(conn, tid)["suche_flaechensuche"], 50)
            finally:
                conn.close()
            conn = init_db(pfad)  # sauber: nichts mehr zu entfernen
            conn.close()
            self.assertEqual(_db.entfernte_fremdobjekte(), [])


class TestCsvMeldungen(unittest.TestCase):
    def test_abgelehnte_zeilen_in_alltagssprache(self):
        """Vor-Build-Klärung 03.10.2026: keine "None"/Python-Listen in den Meldungen."""
        from db_import import _csv_zeile_zu_teilnehmer

        basis = {"nachname": "A", "vorname": "B", "rufname_hund": "H", "art": "ED", "stufe": "1"}
        with self.assertRaises(ValueError) as k:
            _csv_zeile_zu_teilnehmer(basis)
        self.assertEqual(
            str(k.exception),
            "Disziplin fehlt (bei Einzeldisziplin ED nötig) – bitte Trümmerfeld, Flächensuche "
            "oder Behältnisstrecke eintragen",
        )
        with self.assertRaises(ValueError) as k:
            _csv_zeile_zu_teilnehmer({**basis, "disziplin": "Trümmer"})
        self.assertIn("Disziplin „Trümmer“ ist ungültig", str(k.exception))
        with self.assertRaises(ValueError) as k:
            _csv_zeile_zu_teilnehmer({**basis, "art": "", "disziplin": "Trümmerfeld"})
        self.assertIn("Art fehlt – bitte ED (Einzeldisziplin) oder DK (Dreikampf)", str(k.exception))
        with self.assertRaises(ValueError) as k:
            _csv_zeile_zu_teilnehmer({**basis, "stufe": "4", "disziplin": "Trümmerfeld"})
        self.assertIn("Leistungsklasse „4“ ist ungültig – bitte 1, 2 oder 3", str(k.exception))
        for text in (str(k.exception),):
            self.assertNotIn("None", text)
            self.assertNotIn("[", text)


class TestPunktgrenzen(unittest.TestCase):
    def test_schema_passt_zu_gemeinsamen_punktgrenzen(self):
        """UX-Test U5a: Desktop und Web nutzen shs_core.SUCHE_MAX/ANZEIGE_MAX - die
        CHECK-Constraints der Datenbank müssen dieselben Grenzen haben."""
        import db

        for disziplin in ("truemmerfeld", "flaechensuche", "behaeltnis"):
            self.assertIn(f"suche_{disziplin} BETWEEN 0 AND {db.SUCHE_MAX}", " ".join(db.SCHEMA.split()))
            self.assertIn(f"anzeige_{disziplin} BETWEEN 0 AND {db.ANZEIGE_MAX}", " ".join(db.SCHEMA.split()))


class TestZeitplan(unittest.TestCase):
    """Tests für die Zeitplan-Verwaltung: Richter-Spuren mit frei sortierbaren
    Prüfungsblöcken/Pausen, Teilnehmer-Gruppierung, automatische Verteilung sowie die
    zeitliche Berechnung (Start-/Endzeiten je Zeile bzw. je Block)."""

    # Siehe TestDatenbank oben - von TestZeitplanPostgres (Dateiende) überschrieben.
    IntegrityErrorTyp = sqlite3.IntegrityError

    def setUp(self):
        fd, self.pfad = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        os.remove(self.pfad)
        self.conn = init_db(self.pfad)

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.pfad):
            os.remove(self.pfad)

    def _teilnehmer(self, art, stufe, disziplin=None, startnummer=None, nachname="X"):
        return add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname=nachname, vorname="Y", rufname_hund="H",
            art=art, stufe=stufe, disziplin=disziplin, startnummer=startnummer,
        ))

    def test_richter_anlegen_automatischer_name_und_reihenfolge(self):
        r1 = add_zeitplan_richter(self.conn)
        r2 = add_zeitplan_richter(self.conn)
        richter = list_zeitplan_richter(self.conn)
        self.assertEqual([r["id"] for r in richter], [r1, r2])
        self.assertEqual(richter[0]["name"], "Richter 1")
        self.assertEqual(richter[1]["name"], "Richter 2")
        self.assertEqual([r["reihenfolge"] for r in richter], [0, 1])

    def test_startnummer_bereiche_lesen_schreiben_und_pruefen(self):
        # UX-Test 02.10.2026, U1: Speicherform, Rundweg über set_/get_veranstaltung,
        # Überlappungs- und Gültigkeitsprüfung.
        bereiche = {"ED1-Trümmerfeld": (21, 40), "DK1": (1, 20)}
        text = startnummer_bereiche_als_text(bereiche)
        self.assertEqual(text, "DK1=1-20,ED1-Trümmerfeld=21-40")
        set_veranstaltung(self.conn, verein="HSV", datum="2026-11-14", startnummer_bereiche=text)
        self.assertEqual(startnummer_bereiche(get_veranstaltung(self.conn)), bereiche)
        self.assertIsNone(startnummer_bereiche_als_text({}))
        self.assertIsNone(pruefe_startnummer_bereiche(bereiche))
        fehler = pruefe_startnummer_bereiche({"DK1": (1, 20), "ED1-Trümmerfeld": (15, 30)})
        self.assertIn("DK-LK 1", fehler)
        self.assertIn("Trümmer LK 1", fehler)
        self.assertIn("ungültig", pruefe_startnummer_bereiche({"DK1": (10, 5)}))
        self.assertIn("ungültig", pruefe_startnummer_bereiche({"DK1": (0, 5)}))
        self.assertEqual(pruefungs_kuerzel("ED", 2, "Flächensuche"), "ED2-Flächensuche")
        self.assertEqual(pruefungs_kuerzel("DK", 3, None), "DK3")

    def test_fehlende_startnummern_vergeben(self):
        # UX-Test 02.10.2026, U1 (Marcos Entscheidungen): nur Teilnehmer ohne Nummer,
        # vergebene bleiben, "keine Teilnahme" übersprungen, ohne Bereich bzw. bei vollem
        # Bereich keine Nummer; Reihenfolge nach Prüfung, darin nach Name.
        set_veranstaltung(self.conn, verein="HSV", datum="2026-11-14",
                          startnummer_bereiche="DK1=1-3,ED1-Trümmerfeld=10-11")
        vorhanden = self._teilnehmer("DK", 1, startnummer=2, nachname="Alt")
        b = self._teilnehmer("DK", 1, nachname="Bauer")
        a = self._teilnehmer("DK", 1, nachname="Albrecht")
        abgesagt = self._teilnehmer("DK", 1, nachname="Abgesagt")
        setze_keine_teilnahme(self.conn, abgesagt, True)
        t1 = self._teilnehmer("ED", 1, "Trümmerfeld", nachname="T1")
        t2 = self._teilnehmer("ED", 1, "Trümmerfeld", nachname="T2")
        t3 = self._teilnehmer("ED", 1, "Trümmerfeld", nachname="T3")
        ohne = self._teilnehmer("ED", 2, "Flächensuche", nachname="Ohne")

        ergebnis = fehlende_startnummern_vergeben(self.conn)

        nummern = {t["id"]: t["startnummer"] for t in list_teilnehmer(self.conn)}
        self.assertEqual(nummern[vorhanden], 2)
        self.assertEqual(nummern[a], 1)
        self.assertEqual(nummern[b], 3)
        self.assertIsNone(nummern[abgesagt])
        self.assertEqual((nummern[t1], nummern[t2], nummern[t3]), (10, 11, None))
        self.assertIsNone(nummern[ohne])
        self.assertEqual(len(ergebnis.vergeben), 4)
        self.assertEqual([t["id"] for t in ergebnis.bereich_voll], [t3])
        self.assertEqual([t["id"] for t in ergebnis.ohne_bereich], [ohne])
        self.assertEqual(naechste_freie_startnummer_im_bereich(self.conn, (1, 3)), None)
        self.assertEqual(naechste_freie_startnummer_im_bereich(self.conn, (1, 3), ausser_teilnehmer_id=b), 3)

    def test_startnummern_zuruecksetzen(self):
        # Marco 09.10.2026: alle Startnummern auf einmal entfernen, danach neu vergeben.
        set_veranstaltung(self.conn, verein="HSV", datum="2026-11-14",
                          startnummer_bereiche="DK1=1-20")
        self._teilnehmer("DK", 1, startnummer=5, nachname="Bauer")
        self._teilnehmer("DK", 1, startnummer=7, nachname="Albrecht")
        self._teilnehmer("DK", 1, nachname="Ohne")

        self.assertEqual(startnummern_zuruecksetzen(self.conn), 2)
        self.assertEqual([t["startnummer"] for t in list_teilnehmer(self.conn)], [None, None, None])
        self.assertEqual(startnummern_zuruecksetzen(self.conn), 0)

        fehlende_startnummern_vergeben(self.conn)
        nummern = {t["nachname"]: t["startnummer"] for t in list_teilnehmer(self.conn)}
        self.assertEqual(nummern, {"Albrecht": 1, "Bauer": 2, "Ohne": 3})

    def test_startnummern_mit_pruefungsfilter(self):
        # Marco 09.10.2026: der Filter Art/LK schränkt Zurücksetzen und Vergabe auf eine
        # Prüfung ein; beim Zurücksetzen auch "keine Teilnahme". Nummern anderer Prüfungen
        # im Bereich bleiben belegt.
        set_veranstaltung(self.conn, verein="HSV", datum="2026-11-14",
                          startnummer_bereiche="DK1=1-5,ED1-Trümmerfeld=6-10")
        dk = self._teilnehmer("DK", 1, startnummer=1, nachname="DK")
        t1 = self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=6, nachname="T1")
        abgesagt = self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=7, nachname="Abgesagt")
        setze_keine_teilnahme(self.conn, abgesagt, True)
        fremd = self._teilnehmer("ED", 1, "Flächensuche", startnummer=8, nachname="Fremd")

        self.assertEqual(startnummern_zuruecksetzen(self.conn, "ED1-Trümmerfeld"), 2)
        nummern = {t["id"]: t["startnummer"] for t in list_teilnehmer(self.conn)}
        self.assertEqual((nummern[dk], nummern[t1], nummern[abgesagt], nummern[fremd]), (1, None, None, 8))

        dk_neu = self._teilnehmer("DK", 1, nachname="DK-Neu")
        t2 = self._teilnehmer("ED", 1, "Trümmerfeld", nachname="T2")
        ergebnis = fehlende_startnummern_vergeben(self.conn, "ED1-Trümmerfeld")
        nummern = {t["id"]: t["startnummer"] for t in list_teilnehmer(self.conn)}
        self.assertEqual((nummern[t1], nummern[t2]), (6, 7))
        self.assertIsNone(nummern[dk_neu])
        self.assertIsNone(nummern[abgesagt])
        self.assertEqual(len(ergebnis.vergeben), 2)
        self.assertEqual(fehlende_startnummern_je_pruefung(self.conn), [("DK1", 1)])

    def test_fehlende_startnummern_je_pruefung(self):
        self.assertEqual(fehlende_startnummern_je_pruefung(self.conn), [])
        self._teilnehmer("ED", 1, "Flächensuche", nachname="F")
        self._teilnehmer("ED", 1, "Trümmerfeld", nachname="T1")
        self._teilnehmer("ED", 1, "Trümmerfeld", nachname="T2")
        self._teilnehmer("DK", 2, nachname="DK")
        self._teilnehmer("DK", 1, startnummer=3, nachname="Mit")
        abgesagt = self._teilnehmer("DK", 3, nachname="Abgesagt")
        setze_keine_teilnahme(self.conn, abgesagt, True)
        self.assertEqual(
            fehlende_startnummern_je_pruefung(self.conn),
            [("DK2", 1), ("ED1-Trümmerfeld", 2), ("ED1-Flächensuche", 1)],
        )

    def test_bereiche_automatisch_berechnen(self):
        # Marco 09.10.2026: lückenlos ab 1 in der Reihenfolge der Prüfungen (nicht der
        # Eingabe), Anzahl je Prüfung, Anzahl 0 = kein Bereich.
        self.assertEqual(
            bereiche_automatisch_berechnen({"ED1-Flächensuche": 20, "ED1-Trümmerfeld": 20}),
            {"ED1-Trümmerfeld": (1, 20), "ED1-Flächensuche": (21, 40)},
        )
        bereiche = bereiche_automatisch_berechnen({"DK2": 10, "DK1": 0, "ED3-Behältnisstrecke": 5})
        self.assertEqual(bereiche, {"DK2": (1, 10), "ED3-Behältnisstrecke": (11, 15)})
        self.assertIsNone(pruefe_startnummer_bereiche(bereiche))
        self.assertEqual(bereiche_automatisch_berechnen({}), {})
        self.assertEqual(bereiche_automatisch_berechnen({"DK1": 999}), {"DK1": (1, 999)})
        with self.assertRaises(ValueError) as kontext:
            bereiche_automatisch_berechnen({"DK1": 500, "DK2": 500})
        self.assertIn("DK-LK 2", str(kontext.exception))

    def test_startnummer_bereichsgroesse_standard_und_gespeichert(self):
        self.assertEqual(startnummer_bereichsgroesse(None), 20)
        self.assertEqual(startnummer_bereichsgroesse({"startnummer_bereichsgroesse": "abc"}), 20)
        self.assertEqual(startnummer_bereichsgroesse({"startnummer_bereichsgroesse": "0"}), 20)
        set_veranstaltung(self.conn, verein="HSV", datum="2026-11-14", startnummer_bereichsgroesse="15")
        self.assertEqual(startnummer_bereichsgroesse(get_veranstaltung(self.conn)), 15)

    def _dk_teams(self, stufe, anzahl, start=1):
        return [self._teilnehmer("DK", stufe, startnummer=start + i, nachname=f"DK{stufe}-{i}") for i in range(anzahl)]

    def test_dk_mindestabstand_standard_und_gespeichert(self):
        # UX-Test 02.10.2026, U2: Standard 10 Minuten, ungültige Angaben fallen darauf zurück.
        self.assertEqual(dk_mindestabstand(None), 10)
        self.assertEqual(dk_mindestabstand({"dk_mindestabstand": "25"}), 25)
        self.assertEqual(dk_mindestabstand({"dk_mindestabstand": "abc"}), 10)
        set_veranstaltung(self.conn, verein="HSV", datum="2026-11-14", dk_mindestabstand="15")
        self.assertEqual(dk_mindestabstand(get_veranstaltung(self.conn)), 15)

    def test_ueberschneidung_bei_parallelen_dk_bloecken_wird_erkannt(self):
        # UX-Test 02.10.2026, U2: drei DK-Blöcke derselben LK gleichzeitig bei drei
        # Richtern (ohne Versatz) = jedes Team dreifach zur selben Zeit.
        self._dk_teams(1, 4)
        for disziplin in ("Trümmerfeld", "Flächensuche", "Behältnisstrecke"):
            add_zeitplan_pruefungsblock(self.conn, add_zeitplan_richter(self.conn), "DK", 1, disziplin, 10)
        konflikte = zeitplan_ueberschneidungen(self.conn)
        self.assertTrue(konflikte)
        self.assertTrue(all(k["gleichzeitig"] for k in konflikte))
        self.assertEqual({k["teilnehmer"]["nachname"] for k in konflikte}, {"DK1-0", "DK1-1", "DK1-2", "DK1-3"})

    def test_startversatz_rotiert_die_reihenfolge_im_block(self):
        self._dk_teams(1, 4)
        richter = add_zeitplan_richter(self.conn)
        block = add_zeitplan_pruefungsblock(self.conn, richter, "DK", 1, "Trümmerfeld", 10)
        self.conn.execute("UPDATE zeitplan_eintrag SET startversatz = 2 WHERE id = ?", (block,))
        self.conn.commit()
        namen = [z["teilnehmer"]["nachname"] for z in berechne_zeitplan(self.conn)[0]["zeilen"]]
        self.assertEqual(namen, ["DK1-2", "DK1-3", "DK1-0", "DK1-1"])

    def test_automatische_verteilung_ohne_ueberschneidungen(self):
        # UX-Test 02.10.2026, U2 (Szenario aus dem UX-Test): DK-Teams verschiedener LK plus
        # ED, 1-4 Richter - der Vorschlag darf kein Team gleichzeitig bzw. ohne
        # Mindestabstand an zwei Stellen ansetzen.
        self._dk_teams(1, 4, start=1)
        self._dk_teams(2, 2, start=10)
        self._dk_teams(3, 1, start=20)
        for i, disziplin in enumerate(("Trümmerfeld", "Flächensuche", "Behältnisstrecke") * 3):
            self._teilnehmer("ED", 1 + i % 3, disziplin, startnummer=30 + i, nachname=f"ED{i}")
        for richterzahl in (1, 2, 3, 4):
            with self.subTest(richter=richterzahl):
                for r in list_zeitplan_richter(self.conn):
                    self.conn.execute("DELETE FROM zeitplan_richter WHERE id = ?", (r["id"],))
                self.conn.commit()
                ids = [add_zeitplan_richter(self.conn) for _ in range(richterzahl)]
                automatische_zeitplan_verteilung(self.conn, ids, 10)
                self.assertEqual(zeitplan_ueberschneidungen(self.conn), [])
                # Jedes Team ist weiterhin vollständig eingeplant (DK = 3 Starts).
                starts = {}
                for spur in berechne_zeitplan(self.conn):
                    for zeile in spur["zeilen"]:
                        if zeile["typ"] == "pruefung" and zeile["teilnehmer"]:
                            starts[zeile["teilnehmer"]["nachname"]] = starts.get(zeile["teilnehmer"]["nachname"], 0) + 1
                self.assertEqual(starts["DK1-0"], 3)
                self.assertEqual(starts["DK3-0"], 3)
                self.assertEqual(starts["ED0"], 1)

    def test_automatische_verteilung_einzelnes_dk_team_bei_einem_richter(self):
        # Verifikation U2a: ein einzelnes DK-Team bei nur einem Richter braucht
        # Wartezeiten zwischen seinen drei Starts - ohne Überschneidung.
        self._dk_teams(1, 1)
        for abstand in ("10", "30"):
            with self.subTest(abstand=abstand):
                set_veranstaltung(self.conn, verein="HSV", datum="2026-11-14", dk_mindestabstand=abstand)
                for r in list_zeitplan_richter(self.conn):
                    self.conn.execute("DELETE FROM zeitplan_richter WHERE id = ?", (r["id"],))
                self.conn.commit()
                automatische_zeitplan_verteilung(self.conn, [add_zeitplan_richter(self.conn)], 10)
                self.assertEqual(zeitplan_ueberschneidungen(self.conn), [])

    def test_pause_nach_markiertem_eintrag_und_bei_allen_richtern(self):
        # UX-Test 02.10.2026, U9: Pause nach dem markierten Eintrag statt am Ende; gleiche
        # Pause bei allen Richtern vor dem ersten Block ab der Uhrzeit (kein Teilen).
        self._dk_teams(1, 3)
        self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=10, nachname="E1")
        r1, r2 = add_zeitplan_richter(self.conn), add_zeitplan_richter(self.conn)
        b1 = add_zeitplan_pruefungsblock(self.conn, r1, "DK", 1, "Trümmerfeld", 10)    # 09:00-09:30
        add_zeitplan_pruefungsblock(self.conn, r1, "ED", 1, "Trümmerfeld", 10)          # 09:30-09:40
        add_zeitplan_pruefungsblock(self.conn, r2, "ED", 1, "Trümmerfeld", 10)          # 09:00-09:10

        pause = add_zeitplan_pause(self.conn, r1, 15, "Kaffee", nach_eintrag_id=b1)
        self.assertEqual([e["id"] for e in list_zeitplan_eintraege(self.conn, r1)][1], pause)

        # UX-Nachtest N3: tatsächliche Startzeit je Richter statt nur der Anzahl.
        self.assertEqual(
            add_zeitplan_pause_bei_allen(self.conn, "09:05", 30, "Mittag"),
            [("Richter 1", "09:30"), ("Richter 2", "09:10")],
        )
        typen_r1 = [e["bezeichnung"] or e["disziplin"] for e in list_zeitplan_eintraege(self.conn, r1)]
        typen_r2 = [e["bezeichnung"] or e["disziplin"] for e in list_zeitplan_eintraege(self.conn, r2)]
        # r1: DK-Block läuft um 09:05 noch -> Mittag direkt danach (vor "Kaffee", der um 09:30 beginnt).
        self.assertEqual(typen_r1, ["Trümmerfeld", "Mittag", "Kaffee", "Trümmerfeld"])
        # r2: einziger Block beginnt vor 09:05 -> Mittag ans Ende.
        self.assertEqual(typen_r2, ["Trümmerfeld", "Mittag"])
        self.assertEqual(
            [e["reihenfolge"] for e in list_zeitplan_eintraege(self.conn, r1)], [0, 1, 2, 3]
        )

    def test_zeitplan_richter_aus_veranstaltung_anlegen(self):
        # UX-Test 02.10.2026, U8: Richter aus den Veranstaltungsdaten werden übernommen -
        # nur in einen leeren Zeitplan, leere Namen werden übersprungen.
        set_veranstaltung(self.conn, verein="HSV", datum="2026-11-14",
                          wertungsrichter_1="Anna Richter", wertungsrichter_2="  ",
                          wertungsrichter_3="Clara Christ")
        self.assertEqual(zeitplan_richter_aus_veranstaltung_anlegen(self.conn), 2)
        self.assertEqual([r["name"] for r in list_zeitplan_richter(self.conn)],
                         ["Anna Richter", "Clara Christ"])
        # Zweiter Aufruf ändert einen bestehenden Zeitplan nicht.
        self.assertEqual(zeitplan_richter_aus_veranstaltung_anlegen(self.conn), 0)
        self.assertEqual(len(list_zeitplan_richter(self.conn)), 2)

    def test_zeitplan_gruppen_ohne_keine_teilnahme(self):
        # Nutzerwunsch 02.10.2026: nicht erschienene Teilnehmer fallen aus dem Zeitplan.
        a = self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=1)
        b = self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=2)
        dk = self._teilnehmer("DK", 1, startnummer=3)
        setze_keine_teilnahme(self.conn, b, True)
        setze_keine_teilnahme(self.conn, dk, True)
        gruppen = zeitplan_gruppen(self.conn)
        self.assertEqual(len(gruppen), 1)
        self.assertEqual([t["id"] for t in gruppen[0]["teilnehmer"]], [a])

    def test_richter_eigener_name(self):
        add_zeitplan_richter(self.conn, name="Frau Muster")
        self.assertEqual(list_zeitplan_richter(self.conn)[0]["name"], "Frau Muster")

    def test_richter_umbenennen(self):
        rid = add_zeitplan_richter(self.conn, name="Alt")
        umbenennen_zeitplan_richter(self.conn, rid, "Neu")
        self.assertEqual(list_zeitplan_richter(self.conn)[0]["name"], "Neu")

    def test_richter_loeschen_rueckt_reihenfolge_nach(self):
        r1 = add_zeitplan_richter(self.conn, name="R1")
        r2 = add_zeitplan_richter(self.conn, name="R2")
        r3 = add_zeitplan_richter(self.conn, name="R3")
        loesche_zeitplan_richter(self.conn, r2)
        richter = list_zeitplan_richter(self.conn)
        self.assertEqual([r["id"] for r in richter], [r1, r3])
        self.assertEqual([r["reihenfolge"] for r in richter], [0, 1])

    def test_richter_loeschen_entfernt_auch_seine_eintraege(self):
        rid = add_zeitplan_richter(self.conn, name="R1")
        add_zeitplan_pause(self.conn, rid, dauer_minuten=15)
        loesche_zeitplan_richter(self.conn, rid)
        # Spaltenname statt Positionsindex - siehe Kommentar bei
        # test_teilnehmer_loeschen_entfernt_auch_ergebnis oben.
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) AS anzahl FROM zeitplan_eintrag").fetchone()["anzahl"], 0,
        )

    def test_richter_verschieben_vertauscht_nachbarn(self):
        r1 = add_zeitplan_richter(self.conn, name="R1")
        r2 = add_zeitplan_richter(self.conn, name="R2")
        verschiebe_zeitplan_richter(self.conn, r2, -1)
        richter = list_zeitplan_richter(self.conn)
        self.assertEqual([r["id"] for r in richter], [r2, r1])

    def test_richter_verschieben_am_rand_passiert_nichts(self):
        r1 = add_zeitplan_richter(self.conn, name="R1")
        add_zeitplan_richter(self.conn, name="R2")
        verschiebe_zeitplan_richter(self.conn, r1, -1)  # r1 ist schon vorne
        self.assertEqual(list_zeitplan_richter(self.conn)[0]["id"], r1)

    def test_pruefungsblock_und_pause_anlegen(self):
        rid = add_zeitplan_richter(self.conn)
        add_zeitplan_pruefungsblock(self.conn, rid, art="ED", stufe=1, disziplin="Trümmerfeld", dauer_minuten=10)
        add_zeitplan_pause(self.conn, rid, dauer_minuten=20, bezeichnung="Mittagspause")
        eintraege = list_zeitplan_eintraege(self.conn, rid)
        self.assertEqual(len(eintraege), 2)
        self.assertEqual(eintraege[0]["typ"], "pruefung")
        self.assertEqual(eintraege[0]["dauer_minuten"], 10)
        self.assertEqual(eintraege[1]["typ"], "pause")
        self.assertEqual(eintraege[1]["bezeichnung"], "Mittagspause")

    def test_eintrag_aktualisieren_dauer_und_bezeichnung(self):
        rid = add_zeitplan_richter(self.conn)
        eid = add_zeitplan_pause(self.conn, rid, dauer_minuten=15)
        aktualisiere_zeitplan_eintrag(self.conn, eid, dauer_minuten=30, bezeichnung="Kaffeepause")
        eintrag = list_zeitplan_eintraege(self.conn, rid)[0]
        self.assertEqual(eintrag["dauer_minuten"], 30)
        self.assertEqual(eintrag["bezeichnung"], "Kaffeepause")

    def test_eintrag_loeschen_rueckt_reihenfolge_nach(self):
        rid = add_zeitplan_richter(self.conn)
        e1 = add_zeitplan_pause(self.conn, rid, dauer_minuten=5, bezeichnung="A")
        e2 = add_zeitplan_pause(self.conn, rid, dauer_minuten=5, bezeichnung="B")
        e3 = add_zeitplan_pause(self.conn, rid, dauer_minuten=5, bezeichnung="C")
        loesche_zeitplan_eintrag(self.conn, e2)
        eintraege = list_zeitplan_eintraege(self.conn, rid)
        self.assertEqual([e["id"] for e in eintraege], [e1, e3])
        self.assertEqual([e["reihenfolge"] for e in eintraege], [0, 1])

    def test_eintrag_verschieben_vertauscht_nachbarn(self):
        rid = add_zeitplan_richter(self.conn)
        e1 = add_zeitplan_pause(self.conn, rid, dauer_minuten=5, bezeichnung="A")
        e2 = add_zeitplan_pause(self.conn, rid, dauer_minuten=5, bezeichnung="B")
        verschiebe_zeitplan_eintrag(self.conn, e2, -1)
        eintraege = list_zeitplan_eintraege(self.conn, rid)
        self.assertEqual([e["id"] for e in eintraege], [e2, e1])

    def test_check_constraint_pause_ohne_art_stufe_disziplin(self):
        rid = add_zeitplan_richter(self.conn)
        with self.assertRaises(self.IntegrityErrorTyp):
            self.conn.execute(
                "INSERT INTO zeitplan_eintrag (richter_id, reihenfolge, typ, art, dauer_minuten) "
                "VALUES (?, 0, 'pause', 'ED', 10)",
                (rid,),
            )

    def test_zeitplan_gruppen_ed_je_lk_und_disziplin(self):
        self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=1)
        self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=2)
        self._teilnehmer("ED", 2, "Flächensuche", startnummer=3)
        gruppen = zeitplan_gruppen(self.conn)
        self.assertEqual(len(gruppen), 2)
        truemmer_gruppe = next(g for g in gruppen if g["disziplin"] == "Trümmerfeld")
        self.assertEqual(len(truemmer_gruppe["teilnehmer"]), 2)

    def test_zeitplan_gruppen_dk_erscheint_in_allen_drei_disziplinen(self):
        self._teilnehmer("DK", 1, startnummer=1)
        gruppen = zeitplan_gruppen(self.conn)
        self.assertEqual(len(gruppen), 3)  # eine Gruppe je Disziplin für Stufe 1
        for g in gruppen:
            self.assertEqual(g["art"], "DK")
            self.assertEqual(len(g["teilnehmer"]), 1)

    def test_zeitplan_gruppen_ohne_teilnehmer_leer(self):
        self.assertEqual(zeitplan_gruppen(self.conn), [])

    def test_zeitplan_gruppen_status_markiert_eingeplant_und_offen(self):
        self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=1)
        self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=2)
        self._teilnehmer("ED", 2, "Flächensuche", startnummer=3)
        rid = add_zeitplan_richter(self.conn)
        add_zeitplan_pruefungsblock(self.conn, rid, art="ED", stufe=1, disziplin="Trümmerfeld", dauer_minuten=10)
        status = zeitplan_gruppen_status(self.conn)
        self.assertEqual(len(status), 2)
        truemmer = next(g for g in status if g["disziplin"] == "Trümmerfeld")
        flaeche = next(g for g in status if g["disziplin"] == "Flächensuche")
        self.assertTrue(truemmer["eingeplant"])
        self.assertEqual(truemmer["anzahl"], 2)
        self.assertFalse(flaeche["eingeplant"])
        self.assertEqual(flaeche["anzahl"], 1)

    def test_zeitplan_gruppen_status_eingeplant_unabhaengig_vom_richter(self):
        # Ein passender Block reicht aus, egal bei welchem Richter er liegt - die
        # Zuteilung der Teilnehmer erfolgt ohnehin live über Art/Stufe/Disziplin.
        self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=1)
        r1 = add_zeitplan_richter(self.conn, name="R1")
        r2 = add_zeitplan_richter(self.conn, name="R2")
        add_zeitplan_pruefungsblock(self.conn, r2, art="ED", stufe=1, disziplin="Trümmerfeld", dauer_minuten=10)
        status = zeitplan_gruppen_status(self.conn)
        self.assertEqual(len(status), 1)
        self.assertTrue(status[0]["eingeplant"])

    def test_zeitplan_gruppen_status_pause_zaehlt_nicht_als_eingeplant(self):
        self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=1)
        rid = add_zeitplan_richter(self.conn)
        add_zeitplan_pause(self.conn, rid, dauer_minuten=15, bezeichnung="Pause")
        status = zeitplan_gruppen_status(self.conn)
        self.assertEqual(len(status), 1)
        self.assertFalse(status[0]["eingeplant"])

    def test_zeitplan_gruppen_status_ohne_teilnehmer_leer(self):
        self.assertEqual(zeitplan_gruppen_status(self.conn), [])

    def test_automatische_verteilung_balanciert_last(self):
        # 6 ED-Teilnehmer in derselben Gruppe, 2 Richter -> sollte NICHT beide Blöcke
        # demselben Richter zuteilen, wenn ein zweiter unbelasteter Richter frei ist.
        for i in range(6):
            self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=i + 1)
        for i in range(2):
            self._teilnehmer("ED", 1, "Flächensuche", startnummer=i + 10)
        r1 = add_zeitplan_richter(self.conn, name="R1")
        r2 = add_zeitplan_richter(self.conn, name="R2")
        automatische_zeitplan_verteilung(self.conn, [r1, r2], standard_dauer_minuten=10)

        e1 = list_zeitplan_eintraege(self.conn, r1)
        e2 = list_zeitplan_eintraege(self.conn, r2)
        # Größere Gruppe (6 Trümmerfeld) geht an den zuerst freien Richter, die kleinere
        # (2 Flächensuche) an den anderen - insgesamt landet je ein Block pro Richter.
        self.assertEqual(len(e1) + len(e2), 2)
        self.assertEqual(len(e1), 1)
        self.assertEqual(len(e2), 1)

    def test_automatische_verteilung_ersetzt_vorherigen_plan(self):
        self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=1)
        rid = add_zeitplan_richter(self.conn)
        add_zeitplan_pause(self.conn, rid, dauer_minuten=99)  # alter, manuell angelegter Eintrag
        automatische_zeitplan_verteilung(self.conn, [rid], standard_dauer_minuten=10)
        eintraege = list_zeitplan_eintraege(self.conn, rid)
        self.assertEqual(len(eintraege), 1)
        self.assertEqual(eintraege[0]["typ"], "pruefung")

    def test_automatische_verteilung_ohne_richter_tut_nichts(self):
        self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=1)
        automatische_zeitplan_verteilung(self.conn, [], standard_dauer_minuten=10)  # darf nicht crashen

    def test_automatische_verteilung_rollt_bei_teilfehler_komplett_zurueck(self):
        # Fund "automatische_zeitplan_verteilung kann bei Teilfehler den kompletten
        # Zeitplan leeren" (Codeprüfung 21.09.): DELETE wurde vorher sofort committet,
        # die INSERTs erst am Ende - ein Fehler beim zweiten INSERT hätte den alten Plan
        # (schon gelöscht) UND den neuen (nur halb eingefügt) verloren. Simuliert den
        # Teilfehler über eine gefälschte zweite Gruppe mit ungültiger Stufe (verletzt die
        # CHECK-Constraint auf zeitplan_eintrag.stufe) - die erste Gruppe würde ohne den
        # Fix bereits erfolgreich eingefügt UND committet.
        self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=1)
        rid = add_zeitplan_richter(self.conn)
        add_zeitplan_pause(self.conn, rid, dauer_minuten=99, bezeichnung="Alter Plan")
        gefaelschte_gruppen = [
            {"art": "ED", "stufe": 1, "disziplin": "Trümmerfeld", "teilnehmer": [1]},
            {"art": "ED", "stufe": 99, "disziplin": "Trümmerfeld", "teilnehmer": [1]},
        ]

        with patch("db.zeitplan_gruppen", return_value=gefaelschte_gruppen):
            with self.assertRaises(self.IntegrityErrorTyp):
                automatische_zeitplan_verteilung(self.conn, [rid], standard_dauer_minuten=10)

        # Weder der alte Plan blieb committet gelöscht, noch ein halb-neuer zurück - der
        # Stand VOR diesem fehlgeschlagenen Aufruf ist unverändert erhalten.
        eintraege = list_zeitplan_eintraege(self.conn, rid)
        self.assertEqual(len(eintraege), 1)
        self.assertEqual(eintraege[0]["typ"], "pause")
        self.assertEqual(eintraege[0]["bezeichnung"], "Alter Plan")

    def test_berechne_zeitplan_kaskadiert_startzeiten(self):
        set_veranstaltung(self.conn, verein="V", datum="2026-09-19", zeitplan_start="09:00")
        self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=1, nachname="Erst")
        self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=2, nachname="Zweit")
        rid = add_zeitplan_richter(self.conn)
        add_zeitplan_pruefungsblock(self.conn, rid, art="ED", stufe=1, disziplin="Trümmerfeld", dauer_minuten=10)
        add_zeitplan_pause(self.conn, rid, dauer_minuten=15, bezeichnung="Pause")

        [plan] = berechne_zeitplan(self.conn)
        zeilen = plan["zeilen"]
        self.assertEqual(len(zeilen), 3)  # 2 Teilnehmer + 1 Pause
        self.assertEqual(zeilen[0]["start"].strftime("%H:%M"), "09:00")
        self.assertEqual(zeilen[0]["ende"].strftime("%H:%M"), "09:10")
        self.assertEqual(zeilen[0]["teilnehmer"]["nachname"], "Erst")
        self.assertEqual(zeilen[1]["start"].strftime("%H:%M"), "09:10")
        self.assertEqual(zeilen[1]["teilnehmer"]["nachname"], "Zweit")
        self.assertEqual(zeilen[2]["typ"], "pause")
        self.assertEqual(zeilen[2]["start"].strftime("%H:%M"), "09:20")
        self.assertEqual(zeilen[2]["ende"].strftime("%H:%M"), "09:35")

    def test_berechne_zeitplan_ohne_startzeit_verwendet_default(self):
        self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=1)
        rid = add_zeitplan_richter(self.conn)
        add_zeitplan_pruefungsblock(self.conn, rid, art="ED", stufe=1, disziplin="Trümmerfeld", dauer_minuten=10)
        [plan] = berechne_zeitplan(self.conn)
        self.assertEqual(plan["zeilen"][0]["start"].strftime("%H:%M"), "09:00")

    def test_berechne_zeitplan_je_richter_unabhaengig(self):
        set_veranstaltung(self.conn, verein="V", datum="2026-09-19", zeitplan_start="09:00")
        self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=1)
        self._teilnehmer("ED", 2, "Flächensuche", startnummer=2)
        r1 = add_zeitplan_richter(self.conn, name="R1")
        r2 = add_zeitplan_richter(self.conn, name="R2")
        add_zeitplan_pause(self.conn, r1, dauer_minuten=30, bezeichnung="Pause R1")
        add_zeitplan_pruefungsblock(self.conn, r1, art="ED", stufe=1, disziplin="Trümmerfeld", dauer_minuten=10)
        add_zeitplan_pruefungsblock(self.conn, r2, art="ED", stufe=2, disziplin="Flächensuche", dauer_minuten=10)

        plan = berechne_zeitplan(self.conn)
        plan1 = next(p for p in plan if p["richter"] == "R1")
        plan2 = next(p for p in plan if p["richter"] == "R2")
        # R1 hat vorher eine Pause -> Prüfungsblock beginnt erst um 09:30
        self.assertEqual(plan1["zeilen"][1]["start"].strftime("%H:%M"), "09:30")
        # R2 ohne Pause -> beginnt direkt um 09:00, unbeeinflusst von R1
        self.assertEqual(plan2["zeilen"][0]["start"].strftime("%H:%M"), "09:00")

    def test_berechne_zeitplan_bloecke_gesamtdauer_und_teilnehmerzahl(self):
        set_veranstaltung(self.conn, verein="V", datum="2026-09-19", zeitplan_start="09:00")
        self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=1)
        self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=2)
        self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=3)
        rid = add_zeitplan_richter(self.conn)
        add_zeitplan_pruefungsblock(self.conn, rid, art="ED", stufe=1, disziplin="Trümmerfeld", dauer_minuten=5)
        add_zeitplan_pause(self.conn, rid, dauer_minuten=10)

        [plan] = berechne_zeitplan_bloecke(self.conn)
        block, pause = plan["bloecke"]
        self.assertEqual(block["teilnehmer_anzahl"], 3)
        self.assertEqual(block["start"].strftime("%H:%M"), "09:00")
        self.assertEqual(block["ende"].strftime("%H:%M"), "09:15")  # 3 x 5 Minuten
        self.assertIsNone(pause["teilnehmer_anzahl"])
        self.assertEqual(pause["start"].strftime("%H:%M"), "09:15")
        self.assertEqual(pause["ende"].strftime("%H:%M"), "09:25")

    def test_berechne_zeitplan_beruecksichtigt_nachtraeglich_geloeschten_teilnehmer(self):
        # Start-/Endzeiten werden aus den AKTUELL erfassten Teilnehmern neu berechnet,
        # nicht aus einer beim Anlegen des Blocks "eingefrorenen" Anzahl.
        t1 = self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=1)
        self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=2)
        rid = add_zeitplan_richter(self.conn)
        add_zeitplan_pruefungsblock(self.conn, rid, art="ED", stufe=1, disziplin="Trümmerfeld", dauer_minuten=10)
        [plan_vorher] = berechne_zeitplan(self.conn)
        self.assertEqual(len(plan_vorher["zeilen"]), 2)

        delete_teilnehmer(self.conn, t1)
        [plan_nachher] = berechne_zeitplan(self.conn)
        self.assertEqual(len(plan_nachher["zeilen"]), 1)

    def test_berechne_zeitplan_traegt_richter_id_und_eintrag_id(self):
        # Für die Planungsansicht in der Oberfläche muss sich jede Zeile eindeutig auf
        # ihren Richter bzw. den zugrundeliegenden Prüfungsblock/die Pause zurückführen
        # lassen (Auswahl/Verschieben/Bearbeiten/Löschen wirkt auf den Block, nicht auf
        # die einzelne Teilnehmer-Zeile).
        self._teilnehmer("ED", 1, "Trümmerfeld", startnummer=1)
        rid = add_zeitplan_richter(self.conn, name="R1")
        block_id = add_zeitplan_pruefungsblock(self.conn, rid, art="ED", stufe=1, disziplin="Trümmerfeld", dauer_minuten=10)
        pause_id = add_zeitplan_pause(self.conn, rid, dauer_minuten=15)

        [plan] = berechne_zeitplan(self.conn)
        self.assertEqual(plan["richter_id"], rid)
        self.assertEqual(plan["zeilen"][0]["eintrag_id"], block_id)
        self.assertEqual(plan["zeilen"][1]["eintrag_id"], pause_id)

    def test_berechne_zeitplan_zeigt_platzhalterzeile_fuer_block_ohne_teilnehmer(self):
        # Ein bereits angelegter, aber (noch) leerer Prüfungsblock darf nicht spurlos aus
        # der Planungsansicht verschwinden - er bleibt als Platzhalterzeile (ohne
        # Teilnehmer, Dauer 0) sichtbar und damit weiterhin verschieb-/löschbar.
        set_veranstaltung(self.conn, verein="V", datum="2026-09-19", zeitplan_start="09:00")
        rid = add_zeitplan_richter(self.conn)
        block_id = add_zeitplan_pruefungsblock(self.conn, rid, art="ED", stufe=1, disziplin="Trümmerfeld", dauer_minuten=10)

        [plan] = berechne_zeitplan(self.conn)
        self.assertEqual(len(plan["zeilen"]), 1)
        zeile = plan["zeilen"][0]
        self.assertIsNone(zeile["teilnehmer"])
        self.assertEqual(zeile["eintrag_id"], block_id)
        self.assertEqual(zeile["start"], zeile["ende"])
        self.assertEqual(zeile["start"].strftime("%H:%M"), "09:00")


class TestTerminuebersicht(unittest.TestCase):
    """Tests für die Terminübersicht (Startdialog): Standardordner, Dateinamen-Vorschlag,
    Auflisten vorhandener Termine inkl. Umgang mit beschädigten Dateien."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.ordner = pathlib.Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_dateiname_vorschlagen_ersetzt_sonderzeichen(self):
        name = dateiname_vorschlagen("SGV Köppern e.V.", "2026-09-19")
        self.assertTrue(name.startswith("2026-09-19_"))
        self.assertTrue(name.endswith(".sqlite"))
        self.assertNotIn(" ", name)

    def test_dateiname_vorschlagen_mit_leeren_angaben(self):
        name = dateiname_vorschlagen("", "")
        self.assertEqual(name, "ohne-datum_Termin.sqlite")

    def test_termine_ordner_wird_im_benutzerprofil_angelegt(self):
        with patch.object(pathlib.Path, "home", return_value=self.ordner):
            ordner = termine_ordner()
        self.assertTrue(ordner.exists())
        self.assertEqual(ordner, self.ordner / "SHS-Pruefungsprogramm" / "Termine")

    def test_liste_termine_leerer_ordner(self):
        self.assertEqual(liste_termine(self.ordner), [])

    def test_liste_termine_zeigt_stammdaten_und_teilnehmerzahl(self):
        pfad = self.ordner / "2026-09-19_test.sqlite"
        conn = init_db(str(pfad))
        set_veranstaltung(
            conn, verein="SGV Köppern e.V.", datum="2026-09-19", ort="Köppern", vereins_nr="123",
            verband="HSVRM", startnummer_bereichsgroesse="25",
        )
        add_teilnehmer(conn, NeuerTeilnehmer(
            nachname="A", vorname="A", rufname_hund="H", art="ED", stufe=1, disziplin="Trümmerfeld"))
        conn.close()

        termine = liste_termine(self.ordner)
        self.assertEqual(len(termine), 1)
        self.assertEqual(termine[0].verein, "SGV Köppern e.V.")
        # Nutzerwunsch (20.09.): vereins_nr steht in TerminInfo zur Verfügung, damit sich
        # beim Anlegen eines neuen Termins Verein/Vereins-Nr./Ort vorschlagen lassen
        # (siehe StartDialog._neuer_termin in app.py).
        self.assertEqual(termine[0].vereins_nr, "123")
        # Marco, 28.09.2026: auch der Verband wird für den neuen Termin vorgeschlagen.
        self.assertEqual(termine[0].verband, "HSVRM")
        # Marco 09.10.2026: die Standardgröße der Startnummern-Bereiche ebenso.
        self.assertEqual(termine[0].startnummer_bereichsgroesse, "25")
        self.assertEqual(termine[0].datum, "2026-09-19")
        self.assertEqual(termine[0].anzahl_teilnehmer, 1)
        self.assertTrue(termine[0].lesbar)

    def test_liste_termine_alte_datei_ohne_verband_spalte(self):
        # liste_termine öffnet nur lesend, ohne Migration - eine Termin-Datei von vor dem
        # 28.09.2026 hat die Spalte "verband" noch nicht.
        pfad = self.ordner / "2025-05-01_alt.sqlite"
        with closing(sqlite3.connect(str(pfad))) as conn:
            conn.executescript(
                "CREATE TABLE veranstaltung (id INTEGER PRIMARY KEY, verein TEXT, ort TEXT, datum TEXT, vereins_nr TEXT);"
                "INSERT INTO veranstaltung VALUES (1, 'Alt-Verein', 'Ort', '2025-05-01', '9');"
                "CREATE TABLE teilnehmer (id INTEGER PRIMARY KEY);"
            )
        termine = liste_termine(self.ordner)
        self.assertEqual((termine[0].verein, termine[0].verband, termine[0].lesbar), ("Alt-Verein", None, True))

    def test_liste_termine_neueste_zuerst(self):
        for datum in ("2026-01-01", "2026-12-31", "2026-06-15"):
            conn = init_db(str(self.ordner / f"{datum}.sqlite"))
            set_veranstaltung(conn, verein="Verein", datum=datum)
            conn.close()
        termine = liste_termine(self.ordner)
        self.assertEqual([t.datum for t in termine], ["2026-12-31", "2026-06-15", "2026-01-01"])

    def test_liste_termine_zeigt_beschaedigte_datei_statt_abzustuerzen(self):
        (self.ordner / "kaputt.sqlite").write_text("das ist keine SQLite-Datenbank")
        termine = liste_termine(self.ordner)
        self.assertEqual(len(termine), 1)
        self.assertFalse(termine[0].lesbar)
        self.assertIsNone(termine[0].verein)

    def test_liste_termine_ignoriert_andere_dateitypen(self):
        (self.ordner / "notizen.txt").write_text("nicht relevant")
        self.assertEqual(liste_termine(self.ordner), [])


class TestDatumsfelder(unittest.TestCase):
    """Codeprüfung 22.09. (M5): Eingabe TT.MM.JJJJ oder JJJJ-MM-TT, Speicherform immer
    JJJJ-MM-TT, Anzeige TT.MM.JJJJ - reine Funktionen ohne Datenbank."""

    def test_normalisiere_datum_akzeptiert_beide_formate(self):
        self.assertEqual(normalisiere_datum("2026-09-27"), "2026-09-27")
        self.assertEqual(normalisiere_datum("27.09.2026"), "2026-09-27")
        self.assertEqual(normalisiere_datum(" 7.9.2026 "), "2026-09-07")
        self.assertIsNone(normalisiere_datum(""))
        self.assertIsNone(normalisiere_datum(None))
        self.assertEqual(normalisiere_datum("29.02.2024"), "2024-02-29")  # Schaltjahr
        with self.assertRaises(ValueError):
            normalisiere_datum("29.02.2025")

    def test_normalisiere_datum_lehnt_ungueltiges_ab(self):
        for ungueltig in ("31.02.2026", "2026/09/27", "27.09.26", "morgen", "2026-9-27", "20260927"):
            with self.subTest(ungueltig=ungueltig), self.assertRaises(ValueError):
                normalisiere_datum(ungueltig)

    def test_datum_anzeige(self):
        self.assertEqual(datum_anzeige("2026-09-07"), "07.09.2026")
        self.assertEqual(datum_anzeige(None), "")
        # Nicht lesbarer Altbestand bleibt sichtbar, damit er korrigiert werden kann.
        self.assertEqual(datum_anzeige("irgendwann"), "irgendwann")


class TestTerminSync(unittest.TestCase):
    """Testet die eigentliche Kopierlogik des Austauschs zwischen einer SQLite-Termin-
    Datei und einem PostgreSQL-Termin-Schema (kopiere_termin_daten/
    importiere_ergebnisse_nach_startnummer, siehe Abschnittskommentar "Austausch
    zwischen einer SQLite-Termin-Datei (Desktop) und einem PostgreSQL-Termin-Schema
    (Web)" in db.py) - bewusst mit ZWEI SQLite-Verbindungen statt einer echten
    PostgreSQL-Datenbank, da diese Funktionen dialektunabhängig sind (arbeiten nur über
    bereits getestete Funktionen/portables SQL) und dadurch überall ohne installiertes
    psycopg2 laufen. Die dünnen, tatsächlich an PostgreSQL gebundenen Wrapper-Funktionen
    exportiere_termin_nach_postgres/importiere_ergebnisse_aus_postgres selbst werden
    zusätzlich in TestTerminverwaltungPostgres weiter unten geprüft."""

    def setUp(self):
        self.quelle_pfad = self._neue_temp_datei()
        self.ziel_pfad = self._neue_temp_datei()
        self.quelle = init_db(self.quelle_pfad)
        self.ziel = init_db(self.ziel_pfad)

    def tearDown(self):
        self.quelle.close()
        self.ziel.close()
        for pfad in (self.quelle_pfad, self.ziel_pfad):
            if os.path.exists(pfad):
                os.remove(pfad)

    @staticmethod
    def _neue_temp_datei() -> str:
        fd, pfad = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        os.remove(pfad)  # init_db soll die Datei selbst neu anlegen
        return pfad

    def test_keine_teilnahme_wird_nicht_kopiert(self):
        # Nutzerwunsch 02.10.2026: nicht erschienene Teilnehmer gar nicht ins Web übertragen.
        add_teilnehmer(self.quelle, NeuerTeilnehmer(
            nachname="Da", vorname="A", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1))
        fehlt = add_teilnehmer(self.quelle, NeuerTeilnehmer(
            nachname="Fehlt", vorname="B", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=2))
        setze_keine_teilnahme(self.quelle, fehlt, True)

        kopiere_termin_daten(self.quelle, self.ziel)

        self.assertEqual([t["nachname"] for t in list_teilnehmer(self.ziel)], ["Da"])

    def test_rueckholen_laesst_keine_teilnahme_unberuehrt(self):
        # Hin- und Rückweg: der nicht übertragene Teilnehmer behält sein Desktop-Ergebnis,
        # der übertragene bekommt die Web-Ergebnisse.
        da = add_teilnehmer(self.quelle, NeuerTeilnehmer(
            nachname="Da", vorname="A", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1))
        fehlt = add_teilnehmer(self.quelle, NeuerTeilnehmer(
            nachname="Fehlt", vorname="B", rufname_hund="H", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=2))
        eintragen_ergebnis(self.quelle, fehlt, "Trümmerfeld", 40, 20)
        setze_keine_teilnahme(self.quelle, fehlt, True)
        kopiere_termin_daten(self.quelle, self.ziel)
        web_da = list_teilnehmer(self.ziel)[0]["id"]
        eintragen_ergebnis(self.ziel, web_da, "Trümmerfeld", 55, 35)

        bericht = importiere_ergebnisse_nach_startnummer(self.ziel, self.quelle)

        self.assertEqual(bericht.nicht_gefunden, [])
        self.assertEqual(get_ergebnis(self.quelle, da)["suche_truemmerfeld"], 55)
        self.assertEqual(get_ergebnis(self.quelle, fehlt)["suche_truemmerfeld"], 40)
        self.assertEqual(get_teilnehmer(self.quelle, fehlt)["keine_teilnahme"], 1)

    def test_kopiert_veranstaltung_und_teilnehmer(self):
        set_veranstaltung(
            self.quelle, verein="Testverein", ort="Testort", datum="2026-09-19",
            wertungsrichter_1="Richter A", wertungsrichter_5="Richter E",
            verband="BLV", meldestelle="Meldestelle X", angebotene_pruefungen="DK1,ED2-Trümmerfeld",
            startnummer_bereichsgroesse="25",
        )
        add_teilnehmer(self.quelle, NeuerTeilnehmer(
            nachname="Muster", vorname="Anna", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1, bezahlt=True,
        ))

        kopiere_termin_daten(self.quelle, self.ziel)

        veranstaltung = get_veranstaltung(self.ziel)
        self.assertEqual(veranstaltung["verein"], "Testverein")
        self.assertEqual(veranstaltung["wertungsrichter_1"], "Richter A")
        self.assertEqual(veranstaltung["wertungsrichter_5"], "Richter E")
        self.assertEqual(veranstaltung["verband"], "BLV")
        self.assertEqual(veranstaltung["meldestelle"], "Meldestelle X")
        self.assertEqual(veranstaltung["angebotene_pruefungen"], "DK1,ED2-Trümmerfeld")
        self.assertEqual(veranstaltung["startnummer_bereichsgroesse"], "25")  # Verifikation V2

        ziel_teilnehmer = list_teilnehmer(self.ziel)
        self.assertEqual(len(ziel_teilnehmer), 1)
        self.assertEqual(ziel_teilnehmer[0]["nachname"], "Muster")
        self.assertEqual(ziel_teilnehmer[0]["startnummer"], 1)
        self.assertTrue(ziel_teilnehmer[0]["bezahlt"])

    def test_kopiert_bereits_vorhandene_ergebnisse_mit(self):
        teilnehmer_id = add_teilnehmer(self.quelle, NeuerTeilnehmer(
            nachname="Muster", vorname="Anna", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1,
        ))
        eintragen_ergebnis(self.quelle, teilnehmer_id, "Trümmerfeld", 45, 25)

        id_zuordnung = kopiere_termin_daten(self.quelle, self.ziel)

        neue_id = id_zuordnung[teilnehmer_id]
        ergebnis = get_ergebnis(self.ziel, neue_id)
        self.assertEqual(ergebnis["suche_truemmerfeld"], 45)
        self.assertEqual(ergebnis["anzeige_truemmerfeld"], 25)

    def test_id_zuordnung_liefert_alte_und_neue_id(self):
        alte_id = add_teilnehmer(self.quelle, NeuerTeilnehmer(
            nachname="Muster", vorname="Anna", rufname_hund="Rex", art="DK", stufe=1, startnummer=1,
        ))
        id_zuordnung = kopiere_termin_daten(self.quelle, self.ziel)
        self.assertEqual(len(id_zuordnung), 1)
        neue_id = id_zuordnung[alte_id]
        self.assertIsNotNone(get_teilnehmer(self.ziel, neue_id))

    def test_import_ueberschreibt_ergebnisse_im_ziel_nach_startnummer(self):
        # Quelle simuliert den PostgreSQL-Stand nach der Prüfung, Ziel die lokale
        # SQLite-Datei mit demselben Teilnehmer (aber einer anderen internen ID, wie
        # nach einem echten Export/Import über zwei unabhängige Datenbanken).
        add_teilnehmer(self.quelle, NeuerTeilnehmer(
            nachname="Irrelevant", vorname="X", rufname_hund="Y", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=99,
        ))
        quelle_id = add_teilnehmer(self.quelle, NeuerTeilnehmer(
            nachname="Muster", vorname="Anna", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1,
        ))
        eintragen_ergebnis(self.quelle, quelle_id, "Trümmerfeld", 50, 30)

        ziel_id = add_teilnehmer(self.ziel, NeuerTeilnehmer(
            nachname="Muster", vorname="Anna", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1,
        ))

        bericht = importiere_ergebnisse_nach_startnummer(self.quelle, self.ziel)

        self.assertEqual(bericht.aktualisiert, 1)
        self.assertEqual(bericht.ohne_startnummer_uebersprungen, [])
        self.assertEqual(bericht.nicht_gefunden, ["99"])
        ergebnis = get_ergebnis(self.ziel, ziel_id)
        self.assertEqual(ergebnis["suche_truemmerfeld"], 50)
        self.assertEqual(ergebnis["anzeige_truemmerfeld"], 30)

    def test_import_uebergeht_teilnehmer_ohne_startnummer(self):
        add_teilnehmer(self.quelle, NeuerTeilnehmer(
            nachname="Ohne", vorname="Nummer", rufname_hund="Rex", art="DK", stufe=1,
        ))
        bericht = importiere_ergebnisse_nach_startnummer(self.quelle, self.ziel)
        self.assertEqual(bericht.aktualisiert, 0)
        self.assertEqual(bericht.ohne_startnummer_uebersprungen, ["Ohne, Nummer"])

    def test_export_und_import_end_zu_end_ueber_sqlite(self):
        """Simuliert den kompletten Export/Import-Ablauf rein mit SQLite (ohne die
        PostgreSQL-spezifische Terminverwaltung, die separat geprüft wird) - Teilnehmer
        kopieren, "am Prüfungstag" im Ziel Ergebnisse eintragen, danach zurück in die
        Quelle importieren."""
        add_teilnehmer(self.quelle, NeuerTeilnehmer(
            nachname="Muster", vorname="Anna", rufname_hund="Rex", art="DK", stufe=1, startnummer=1,
        ))
        kopiere_termin_daten(self.quelle, self.ziel)

        ziel_teilnehmer = list_teilnehmer(self.ziel)[0]
        for disziplin in ("Trümmerfeld", "Flächensuche", "Behältnisstrecke"):
            eintragen_ergebnis(self.ziel, ziel_teilnehmer["id"], disziplin, 40, 20)

        bericht = importiere_ergebnisse_nach_startnummer(self.ziel, self.quelle)
        self.assertEqual(bericht.aktualisiert, 1)

        quelle_teilnehmer = list_teilnehmer(self.quelle)[0]
        ergebnis = get_ergebnis(self.quelle, quelle_teilnehmer["id"])
        self.assertEqual(ergebnis["suche_truemmerfeld"], 40)
        self.assertEqual(ergebnis["suche_flaechensuche"], 40)
        self.assertEqual(ergebnis["suche_behaeltnis"], 40)

    def test_import_sammelt_fehler_und_macht_mit_naechstem_teilnehmer_weiter(self):
        # Fund "importiere_ergebnisse_nach_startnummer(): kein Teilbericht bei Fehler
        # mittendrin" (Codeprüfung 21.09.) - eintragen_ergebnis() committet pro
        # Teilnehmer einzeln; ein Fehler bei einem einzelnen Teilnehmer darf den Import
        # für die übrigen Teilnehmer nicht abbrechen, sondern landet im neuen
        # `fehler`-Feld des ImportBericht, während der nächste Teilnehmer trotzdem
        # übertragen wird.
        fehler_quelle_id = add_teilnehmer(self.quelle, NeuerTeilnehmer(
            nachname="Fehler", vorname="Eins", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1,
        ))
        eintragen_ergebnis(self.quelle, fehler_quelle_id, "Trümmerfeld", 40, 20)
        ok_quelle_id = add_teilnehmer(self.quelle, NeuerTeilnehmer(
            nachname="Muster", vorname="Anna", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=2,
        ))
        eintragen_ergebnis(self.quelle, ok_quelle_id, "Trümmerfeld", 45, 25)

        fehler_ziel_id = add_teilnehmer(self.ziel, NeuerTeilnehmer(
            nachname="Fehler", vorname="Eins", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1,
        ))
        ok_ziel_id = add_teilnehmer(self.ziel, NeuerTeilnehmer(
            nachname="Muster", vorname="Anna", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=2,
        ))

        # eintragen_ergebnis() für den Fehler-Teilnehmer im Ziel künstlich scheitern
        # lassen (simuliert z. B. einen zwischenzeitlichen DB-Fehler), für alle anderen
        # normal durchreichen - die echte, unveränderte Funktion bleibt über die lokal
        # importierte Referenz erreichbar (patch() ersetzt nur das Attribut im db-Modul).
        echtes_eintragen_ergebnis = eintragen_ergebnis

        def _eintragen_ergebnis_mit_fehler(conn, teilnehmer_id, disziplin, suche, anzeige):
            if teilnehmer_id == fehler_ziel_id:
                raise sqlite3.IntegrityError("simulierter Fehler")
            return echtes_eintragen_ergebnis(conn, teilnehmer_id, disziplin, suche, anzeige)

        with patch("db.eintragen_ergebnis", side_effect=_eintragen_ergebnis_mit_fehler):
            bericht = importiere_ergebnisse_nach_startnummer(self.quelle, self.ziel)

        self.assertEqual(bericht.aktualisiert, 1)
        self.assertEqual(bericht.fehler, ["Fehler, Eins"])
        self.assertEqual(bericht.nicht_gefunden, [])
        ergebnis_ok = get_ergebnis(self.ziel, ok_ziel_id)
        self.assertEqual(ergebnis_ok["suche_truemmerfeld"], 45)
        self.assertEqual(ergebnis_ok["anzeige_truemmerfeld"], 25)

    def test_import_uebernimmt_nichts_bei_abweichendem_teilnehmer(self):
        # Codeprüfung 22.09. (M2): Startnummern wurden nach dem Veröffentlichen in der
        # Termin-Datei getauscht - die Ergebnisse dürfen NICHT still beim jeweils anderen
        # Teilnehmer landen, sondern werden als Abweichung gemeldet.
        for nr, name, hund, punkte in [(1, "Muster", "Rex", (50, 30)), (2, "Beispiel", "Bello", (40, 20))]:
            tid = add_teilnehmer(self.quelle, NeuerTeilnehmer(
                nachname=name, vorname="A", rufname_hund=hund, art="ED", stufe=1,
                disziplin="Trümmerfeld", startnummer=nr,
            ))
            eintragen_ergebnis(self.quelle, tid, "Trümmerfeld", *punkte)
        ziel_ids = [
            add_teilnehmer(self.ziel, NeuerTeilnehmer(
                nachname=name, vorname="A", rufname_hund=hund, art="ED", stufe=1,
                disziplin="Trümmerfeld", startnummer=nr,
            ))
            for nr, name, hund in [(2, "Muster", "Rex"), (1, "Beispiel", "Bello")]
        ]

        bericht = importiere_ergebnisse_nach_startnummer(self.quelle, self.ziel)

        self.assertEqual(bericht.aktualisiert, 0)
        self.assertEqual(len(bericht.abweichungen), 2)
        self.assertIn("Nr. 1", bericht.abweichungen[0])
        self.assertIn("Muster, A (Rex, ED LK 1 Trümmerfeld)", bericht.abweichungen[0])
        self.assertIn("Beispiel, A (Bello, ED LK 1 Trümmerfeld)", bericht.abweichungen[0])
        for ziel_id in ziel_ids:
            ergebnis = get_ergebnis(self.ziel, ziel_id)
            self.assertIsNone(ergebnis["suche_truemmerfeld"])

    def test_import_erkennt_abweichung_bei_art_oder_leistungsklasse(self):
        quelle_id = add_teilnehmer(self.quelle, NeuerTeilnehmer(
            nachname="Muster", vorname="Anna", rufname_hund="Rex", art="ED", stufe=2,
            disziplin="Trümmerfeld", startnummer=1,
        ))
        eintragen_ergebnis(self.quelle, quelle_id, "Trümmerfeld", 50, 30)
        add_teilnehmer(self.ziel, NeuerTeilnehmer(
            nachname="Muster", vorname="Anna", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1,
        ))

        bericht = importiere_ergebnisse_nach_startnummer(self.quelle, self.ziel)

        self.assertEqual(bericht.aktualisiert, 0)
        self.assertEqual(len(bericht.abweichungen), 1)

    def test_import_ignoriert_gross_kleinschreibung_und_leerzeichen(self):
        quelle_id = add_teilnehmer(self.quelle, NeuerTeilnehmer(
            nachname=" muster ", vorname="Anna", rufname_hund="REX", art="DK", stufe=1, startnummer=1,
        ))
        eintragen_ergebnis(self.quelle, quelle_id, "Trümmerfeld", 50, 30)
        ziel_id = add_teilnehmer(self.ziel, NeuerTeilnehmer(
            nachname="Muster", vorname="Anna", rufname_hund="Rex", art="DK", stufe=1, startnummer=1,
        ))

        bericht = importiere_ergebnisse_nach_startnummer(self.quelle, self.ziel)

        self.assertEqual(bericht.aktualisiert, 1)
        self.assertEqual(bericht.abweichungen, [])
        self.assertEqual(get_ergebnis(self.ziel, ziel_id)["suche_truemmerfeld"], 50)

    def test_import_meldet_im_web_leere_disziplin_und_behaelt_zielwert(self):
        # Codeprüfung 22.09., G2: Disziplin im Web leer, in der Termin-Datei gefüllt - der
        # Wert der Termin-Datei bleibt erhalten, wird aber im Bericht gemeldet.
        quelle_id = add_teilnehmer(self.quelle, NeuerTeilnehmer(
            nachname="Muster", vorname="Anna", rufname_hund="Rex", art="DK", stufe=1, startnummer=5,
        ))
        eintragen_ergebnis(self.quelle, quelle_id, "Flächensuche", 50, 30)
        ziel_id = add_teilnehmer(self.ziel, NeuerTeilnehmer(
            nachname="Muster", vorname="Anna", rufname_hund="Rex", art="DK", stufe=1, startnummer=5,
        ))
        eintragen_ergebnis(self.ziel, ziel_id, "Trümmerfeld", 45, 30)

        bericht = importiere_ergebnisse_nach_startnummer(self.quelle, self.ziel)

        self.assertEqual(bericht.aktualisiert, 1)
        self.assertEqual(
            bericht.im_web_leer,
            ["Nr. 5 Muster, Anna – Trümmerfeld: in der Web-Erfassung leer, "
             "in der Termin-Datei 45/30 (beibehalten)"],
        )
        ergebnis = get_ergebnis(self.ziel, ziel_id)
        self.assertEqual(ergebnis["suche_truemmerfeld"], 45)
        self.assertEqual(ergebnis["anzeige_truemmerfeld"], 30)
        self.assertEqual(ergebnis["suche_flaechensuche"], 50)

    def test_import_im_web_leer_bleibt_leer_ohne_zielwert(self):
        # Beide Seiten leer bzw. Web gefüllt: kein Hinweis (Codeprüfung 22.09., G2).
        quelle_id = add_teilnehmer(self.quelle, NeuerTeilnehmer(
            nachname="Muster", vorname="Anna", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1,
        ))
        eintragen_ergebnis(self.quelle, quelle_id, "Trümmerfeld", 50, 30)
        ziel_id = add_teilnehmer(self.ziel, NeuerTeilnehmer(
            nachname="Muster", vorname="Anna", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1,
        ))
        eintragen_ergebnis(self.ziel, ziel_id, "Trümmerfeld", 10, 10)

        bericht = importiere_ergebnisse_nach_startnummer(self.quelle, self.ziel)

        self.assertEqual(bericht.im_web_leer, [])
        self.assertEqual(get_ergebnis(self.ziel, ziel_id)["suche_truemmerfeld"], 50)

    def test_import_im_web_leer_nicht_bei_abweichendem_teilnehmer(self):
        # Nicht zuordenbare Teilnehmer landen nur in `abweichungen`, nicht zusätzlich in
        # `im_web_leer` (Codeprüfung 22.09., G2).
        add_teilnehmer(self.quelle, NeuerTeilnehmer(
            nachname="Muster", vorname="Anna", rufname_hund="Rex", art="DK", stufe=1, startnummer=1,
        ))
        ziel_id = add_teilnehmer(self.ziel, NeuerTeilnehmer(
            nachname="Beispiel", vorname="Bea", rufname_hund="Bello", art="DK", stufe=1, startnummer=1,
        ))
        eintragen_ergebnis(self.ziel, ziel_id, "Trümmerfeld", 45, 30)

        bericht = importiere_ergebnisse_nach_startnummer(self.quelle, self.ziel)

        self.assertEqual(len(bericht.abweichungen), 1)
        self.assertEqual(bericht.im_web_leer, [])


class TestExportiereTerminNachPostgresFehlerpfad(unittest.TestCase):
    """Prüft den Fehlerpfad von exportiere_termin_nach_postgres() rein über Mocks für
    erstelle_termin_postgres/kopiere_termin_daten/loesche_termin_postgres/
    _setze_termin_suchpfad (keine echte PostgreSQL-Verbindung nötig - läuft daher auch
    ohne SHS_TEST_POSTGRES_DSN/psycopg2 lokal). Fund "Postgres-Export nicht atomar"
    (Codeprüfung 21.09.): bricht kopiere_termin_daten() mittendrin ab (dessen einzelne
    add_teilnehmer()/eintragen_ergebnis()-Aufrufe committen bereits, ein echtes Rollback
    ist also nicht mehr möglich), muss der gerade erst angelegte, dadurch nur teilweise
    befüllte Termin per loesche_termin_postgres() wieder vollständig entfernt werden,
    statt als scheinbar vollständiger Termin in der Web-Terminauswahl stehen zu bleiben -
    und die ursprüngliche Exception muss unverändert weiter nach oben gereicht werden."""

    def test_bereinigt_angefangenen_termin_bei_fehler_und_reicht_exception_weiter(self):
        neuer_termin = TerminInfoPostgres(
            id=42, schema_name="termin_42", verein=None, ort=None, datum=None,
            anzahl_teilnehmer=0, erstellt_am="2026-09-21T00:00:00Z",
        )
        # Nur rollback() wird direkt aufgerufen, alles andere geht an die Mocks.
        postgres_conn = MagicMock()
        sqlite_conn = object()

        with patch("db.erstelle_termin_postgres", return_value=neuer_termin) as mock_erstelle, \
             patch("db._setze_termin_suchpfad") as mock_suchpfad, \
             patch("db.kopiere_termin_daten", side_effect=RuntimeError("Verbindungsabbruch")) as mock_kopiere, \
             patch("db.loesche_termin_postgres") as mock_loesche, \
             patch("db.liste_termine_postgres") as mock_liste:
            with self.assertRaises(RuntimeError):
                exportiere_termin_nach_postgres(sqlite_conn, postgres_conn)

        mock_erstelle.assert_called_once_with(postgres_conn)
        mock_kopiere.assert_called_once_with(sqlite_conn, postgres_conn)
        # Der angefangene Termin wurde vollständig entfernt statt für die Web-Oberfläche
        # sichtbar zu bleiben.
        mock_loesche.assert_called_once_with(postgres_conn, "termin_42")
        # search_path: einmal auf das neue Schema (vor dem Kopieren), einmal zurück auf
        # "public" (vor der Bereinigung) - der Erfolgspfad danach (liste_termine_postgres,
        # also auch das dortige erneute Umschalten) wird NICHT mehr erreicht.
        mock_suchpfad.assert_any_call(postgres_conn, "termin_42")
        mock_suchpfad.assert_any_call(postgres_conn, "public")
        mock_liste.assert_not_called()

    def test_rollback_kommt_vor_der_bereinigung(self):
        # Codeprüfung 22.09. (M1): nach einem echten PostgreSQL-Fehler ist die Transaktion
        # abgebrochen - ohne vorheriges rollback() scheitert bereits das SET search_path
        # (InFailedSqlTransaction) und die Bereinigung läuft nie.
        neuer_termin = TerminInfoPostgres(
            id=42, schema_name="termin_42", verein=None, ort=None, datum=None,
            anzahl_teilnehmer=0, erstellt_am="2026-09-22T00:00:00Z",
        )
        reihenfolge = MagicMock()
        postgres_conn = reihenfolge.conn

        with patch("db.erstelle_termin_postgres", return_value=neuer_termin), \
             patch("db._setze_termin_suchpfad", reihenfolge.suchpfad), \
             patch("db.kopiere_termin_daten", side_effect=RuntimeError("PG-Fehler")), \
             patch("db.loesche_termin_postgres", reihenfolge.loesche):
            with self.assertRaises(RuntimeError):
                exportiere_termin_nach_postgres(object(), postgres_conn)

        namen = [aufruf[0] for aufruf in reihenfolge.mock_calls]
        self.assertIn("conn.rollback", namen)
        self.assertLess(namen.index("conn.rollback"), namen.index("loesche"))
        # Das Umschalten auf "public" vor der Bereinigung kommt ebenfalls erst nach dem
        # rollback() (das erste suchpfad-Umschalten auf das neue Schema liegt davor).
        self.assertEqual(namen[namen.index("conn.rollback") + 1], "suchpfad")

    def test_fehler_bei_bereinigung_verdeckt_nicht_die_urspruengliche_exception(self):
        neuer_termin = TerminInfoPostgres(
            id=42, schema_name="termin_42", verein=None, ort=None, datum=None,
            anzahl_teilnehmer=0, erstellt_am="2026-09-22T00:00:00Z",
        )
        with patch("db.erstelle_termin_postgres", return_value=neuer_termin), \
             patch("db._setze_termin_suchpfad"), \
             patch("db.kopiere_termin_daten", side_effect=RuntimeError("Ursprungsfehler")), \
             patch("db.loesche_termin_postgres", side_effect=ValueError("Bereinigung kaputt")):
            with self.assertRaises(RuntimeError) as kontext:
                exportiere_termin_nach_postgres(object(), MagicMock())
        self.assertEqual(str(kontext.exception), "Ursprungsfehler")


class TestTerminImportStammdaten(unittest.TestCase):
    """Testet importiere_teilnehmer_stammdaten() - 'Teilnehmer aus anderem Termin
    importieren' (Nutzerwunsch 20.09., siehe TerminImportDialog in app.py). Anders als
    kopiere_termin_daten() (siehe TestTerminSync oben, komplette 1:1-Übertragung für die
    Web-Sync) übernimmt diese Funktion gezielt nur eine Auswahl an Teilnehmern und nur
    deren Stammdaten - Startnummer/Gegenstände/Bezahlt-Status/Ergebnis bleiben immer
    zurückgesetzt, unabhängig davon, was die Quelle hatte."""

    def setUp(self):
        self.quelle_pfad = TestTerminSync._neue_temp_datei()
        self.ziel_pfad = TestTerminSync._neue_temp_datei()
        self.quelle = init_db(self.quelle_pfad)
        self.ziel = init_db(self.ziel_pfad)

    def tearDown(self):
        self.quelle.close()
        self.ziel.close()
        for pfad in (self.quelle_pfad, self.ziel_pfad):
            if os.path.exists(pfad):
                os.remove(pfad)

    def test_importiert_nur_ausgewaehlte_teilnehmer_mit_stammdaten(self):
        a = add_teilnehmer(self.quelle, NeuerTeilnehmer(
            nachname="Muster", vorname="Anna", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Trümmerfeld", verein="Testverein", chip_nr="123", rasse="Schäferhund",
            startnummer=1, bezahlt=True,
            gegenstand_1="Schlüsselbund", gegenstand_1_disziplin="Trümmerfeld",
        ))
        add_teilnehmer(self.quelle, NeuerTeilnehmer(
            nachname="Nicht", vorname="Gewollt", rufname_hund="Fido", art="ED", stufe=1,
            disziplin="Flächensuche",
        ))

        anzahl = importiere_teilnehmer_stammdaten(self.quelle, self.ziel, [a])

        self.assertEqual(anzahl, 1)
        ziel_teilnehmer = list_teilnehmer(self.ziel)
        self.assertEqual(len(ziel_teilnehmer), 1)  # nur der ausgewählte, nicht "Nicht Gewollt"
        importiert = ziel_teilnehmer[0]
        self.assertEqual(importiert["nachname"], "Muster")
        self.assertEqual(importiert["verein"], "Testverein")
        self.assertEqual(importiert["chip_nr"], "123")
        self.assertEqual(importiert["rasse"], "Schäferhund")
        self.assertEqual(importiert["art"], "ED")
        self.assertEqual(importiert["disziplin"], "Trümmerfeld")
        # Bewusst NICHT übernommen (Absprache mit dem Nutzer):
        self.assertIsNone(importiert["startnummer"])
        self.assertFalse(importiert["bezahlt"])
        self.assertIsNone(importiert["gegenstand_1"])
        self.assertIsNone(importiert["gegenstand_1_disziplin"])

    def test_bereits_vergebene_startnummer_in_quelle_blockiert_import_ins_ziel_nicht(self):
        # Regression: würde die Startnummer mitkopiert, könnte der Import an der
        # UNIQUE-Constraint im Ziel scheitern (z.B. wenn dort schon jemand dieselbe
        # Nummer hat) - da sie bewusst NICHT übernommen wird, kann das nicht passieren.
        add_teilnehmer(self.ziel, NeuerTeilnehmer(
            nachname="Schon", vorname="Da", rufname_hund="Bello", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1,
        ))
        quelle_id = add_teilnehmer(self.quelle, NeuerTeilnehmer(
            nachname="Neu", vorname="Dazu", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1,
        ))

        anzahl = importiere_teilnehmer_stammdaten(self.quelle, self.ziel, [quelle_id])

        self.assertEqual(anzahl, 1)
        self.assertEqual(len(list_teilnehmer(self.ziel)), 2)

    def test_nicht_mehr_vorhandene_id_wird_uebersprungen(self):
        anzahl = importiere_teilnehmer_stammdaten(self.quelle, self.ziel, [999])
        self.assertEqual(anzahl, 0)
        self.assertEqual(list_teilnehmer(self.ziel), [])


# --- Dieselben Tests zusätzlich gegen PostgreSQL (geplante Podman/Web-Version) --------
#
# TestTerminuebersicht oben bleibt bewusst NUR gegen SQLite: sie testet die
# Datei-Verwaltung (termine_ordner/liste_termine/dateiname_vorschlagen) - "ein Termin =
# eine Datei" ist ein Konzept der Desktop-Version (siehe Moduldocstring in db.py) und hat
# für eine gemeinsame PostgreSQL-Datenbank kein direktes Gegenstück; wie die Web-Version
# einzelne Termine in einer gemeinsamen Datenbank unterscheidet, ist eine eigene, noch zu
# klärende Design-Frage (nicht Teil dieser Umstellung).
#
# TestDatenbank und TestZeitplan dagegen decken die eigentliche Kernlogik ab (Teilnehmer,
# Ergebnisse, Zeitplan) - genau die Funktionen, die künftig sowohl von der SQLite-
# Desktop- als auch der PostgreSQL-Web-Version genutzt werden. Über die beiden
# Unterklassen unten laufen exakt dieselben Testmethoden zusätzlich gegen eine echte
# PostgreSQL-Datenbank, ohne den Testsatz zu duplizieren (siehe _PostgresBackendMixin).

try:
    import psycopg2
except ImportError:
    psycopg2 = None

_POSTGRES_TEST_DSN = os.environ.get("SHS_TEST_POSTGRES_DSN")


try:
    from pypdf import PdfReader as _PdfReader  # nur als Verfügbarkeitsprüfung
    from reportlab.pdfgen import canvas as _pdf_canvas
except ImportError:  # pragma: no cover - lokal ohne pypdf/reportlab
    _PdfReader = None
    _pdf_canvas = None


class TestPruefungsangebote(unittest.TestCase):
    """Nutzerwunsch 28.09.2026: Liste der im Anmeldeformular ankreuzbaren Prüfungen und
    deren Speicherform in veranstaltung.angebotene_pruefungen."""

    def test_alle_pruefungen_reihenfolge_und_kuerzel_eindeutig(self):
        self.assertEqual(len(ALLE_PRUEFUNGEN), 12)
        self.assertEqual([p.kuerzel for p in ALLE_PRUEFUNGEN[:4]], ["DK1", "DK2", "DK3", "ED1-Trümmerfeld"])
        self.assertEqual(len({p.kuerzel for p in ALLE_PRUEFUNGEN}), 12)
        dk2 = pruefung_nach_kuerzel("DK2")
        self.assertEqual((dk2.art, dk2.stufe, dk2.disziplin), ("DK", 2, None))
        flaeche3 = pruefung_nach_kuerzel("ED3-Flächensuche")
        self.assertEqual((flaeche3.art, flaeche3.stufe, flaeche3.disziplin), ("ED", 3, "Flächensuche"))
        self.assertIsNone(pruefung_nach_kuerzel("XY1"))

    def test_pruefungen_als_text_und_zurueck(self):
        # Reihenfolge folgt ALLE_PRUEFUNGEN, nicht der Eingabe; leere Auswahl -> None.
        text = pruefungen_als_text(["ED2-Trümmerfeld", "DK1"])
        self.assertEqual(text, "DK1,ED2-Trümmerfeld")
        self.assertIsNone(pruefungen_als_text([]))
        with self.assertRaises(ValueError):
            pruefungen_als_text(["DK1", "XY1"])
        self.assertEqual(
            [p.kuerzel for p in angebotene_pruefungen({"angebotene_pruefungen": text})],
            ["DK1", "ED2-Trümmerfeld"],
        )
        # Unbekannte Kürzel in der Datenbank werden ignoriert, fehlende Angabe -> leer.
        self.assertEqual(
            [p.kuerzel for p in angebotene_pruefungen({"angebotene_pruefungen": " XY1 , DK3 "})], ["DK3"]
        )
        self.assertEqual(angebotene_pruefungen({"angebotene_pruefungen": None}), [])
        self.assertEqual(angebotene_pruefungen(None), [])


@unittest.skipIf(_PdfReader is None or _pdf_canvas is None,
                 "pypdf/reportlab nicht installiert - Anmeldeformular-Import wird übersprungen")
class TestAnmeldeformularImport(unittest.TestCase):
    """Nutzerwunsch 28.09.2026: ausgefüllte Anmeldeformular-PDFs als Teilnehmer einlesen
    (db_import.importiere_anmeldeformular_pdf). Die Test-PDFs werden hier bewusst selbst mit
    reportlab (canvas.acroForm) und den Feldnamen aus db.py gebaut statt über
    pdf_export.erstelle_anmeldeformular_pdf() - so prüft der Test den Import unabhängig vom
    Formular-Layout, und der Rundlauf der Umlaut-Feldnamen (z. B. "pruefung_ED2-Trümmerfeld")
    durch reportlab + pypdf ist mit abgedeckt."""

    STANDARD_TEXTE = {
        "vorname": "Anna", "nachname": "Muster", "strasse": "Hauptstraße", "hausnummer": "5",
        "plz": "12345", "ort": "Musterstadt", "mitgliedsnummer": "M-1", "telefon": "0123 456",
        "email": "anna@example.org", "verein": "HSV Musterstadt", "verband": "BLV",
        "halter_vorname": "Bernd", "halter_nachname": "Halter", "halter_strasse": "Nebenweg",
        "halter_hausnummer": "7a", "halter_plz": "54321", "halter_ort": "Halterdorf",
        "halter_mitgliedsnummer": "H-2", "halter_mitgliedsverein": "SV Halterdorf",
        "halter_lu_nr": "LU-3", "zwingername": "vom Testhof", "rufname_hund": "Rex",
        "rasse": "Mischling", "wurftag": "01.02.2020", "schulterhoehe_cm": "45 cm",
        "tollwutimpfung_bis": "31.12.2027", "kennzeichnung_nr": "12345",
    }

    def setUp(self):
        fd, self.db_pfad = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        os.remove(self.db_pfad)
        self.conn = init_db(self.db_pfad)
        # Alle 12 Prüfungen angeboten - der Import lehnt nicht angebotene ab (Verifikation
        # 28.09.2026, Befund 1), siehe test_nicht_angebotene_pruefung_wird_abgelehnt.
        set_veranstaltung(
            self.conn, verein="HSV Musterstadt", datum="2026-11-14",
            angebotene_pruefungen=pruefungen_als_text([p.kuerzel for p in ALLE_PRUEFUNGEN]),
        )
        self.ordner = tempfile.mkdtemp()
        # Zweite Verifikation 28.09.2026, N4: pypdf meldet beim absichtlichen Befüllen mit
        # auto_regenerate=False bzw. beim Lesen einer Nicht-PDF Warnungen über logging -
        # erwartetes Verhalten dieser Tests, nur Rauschen im Testlauf.
        self._pypdf_logger = logging.getLogger("pypdf")
        self._pypdf_level = self._pypdf_logger.level
        self._pypdf_logger.setLevel(logging.ERROR)

    def tearDown(self):
        self._pypdf_logger.setLevel(self._pypdf_level)
        self.conn.close()
        os.remove(self.db_pfad)
        for name in os.listdir(self.ordner):
            os.remove(os.path.join(self.ordner, name))
        os.rmdir(self.ordner)

    def _pdf(self, dateiname, texte=None, haken=(), ohne_felder=False):
        """Baut ein ausfüllbares PDF: alle Textfelder aus ANMELDEFORMULAR_TEXTFELDER (plus
        Gegenstandsfelder LK 1-3), alle Prüfungs-/Kennzeichnungs-/Geschlechts-Checkboxen;
        `haken` = Feldnamen der angekreuzten Checkboxen."""
        pfad = os.path.join(self.ordner, dateiname)
        c = _pdf_canvas.Canvas(pfad)
        if ohne_felder:
            c.drawString(50, 750, "Kein Formular")
        else:
            form = c.acroForm
            werte = self.STANDARD_TEXTE if texte is None else texte
            textfelder = list(ANMELDEFORMULAR_TEXTFELDER) + [
                anmeldeformular_gegenstand_feld(stufe, n) for stufe in (1, 2, 3) for n in range(1, stufe + 1)
            ]
            for i, feld in enumerate(textfelder):
                form.textfield(name=feld, value=werte.get(feld, ""), x=20 + (i % 4) * 140,
                               y=780 - (i // 4) * 25, width=130, height=18)
            checkboxen = [ANMELDEFORMULAR_PRUEFUNG_PRAEFIX + p.kuerzel for p in ALLE_PRUEFUNGEN] + [
                ANMELDEFORMULAR_KENNZEICHNUNG_CHIP, ANMELDEFORMULAR_KENNZEICHNUNG_TAETO,
                ANMELDEFORMULAR_HUENDIN, ANMELDEFORMULAR_RUEDE,
            ]
            for i, feld in enumerate(checkboxen):
                form.checkbox(name=feld, checked=feld in haken, x=20 + (i % 8) * 60,
                              y=300 - (i // 8) * 30, size=14)
        c.showPage()
        c.save()
        return pfad

    def test_dreikampf_uebernimmt_alle_gegenstaende(self):
        # UX-Test 02.10.2026, U11: die Beschränkung auf einen Gegenstand gilt nur für ED.
        texte = dict(self.STANDARD_TEXTE, **{
            anmeldeformular_gegenstand_feld(2, 1): "Ball",
            anmeldeformular_gegenstand_feld(2, 2): "Leine",
        })
        pfad = self._pdf("dk.pdf", texte, haken=(ANMELDEFORMULAR_PRUEFUNG_PRAEFIX + "DK2",))
        ergebnis = importiere_anmeldeformular_pdf(self.conn, [pfad])
        self.assertEqual((ergebnis.importiert, ergebnis.hinweise), (1, []))
        t = list_teilnehmer(self.conn)[0]
        self.assertEqual((t["gegenstand_1"], t["gegenstand_2"]), ("Ball", "Leine"))

    def test_ed_nur_zweites_gegenstandsfeld_ausgefuellt(self):
        # UX-Test U11: bei ED zählt der erste AUSGEFÜLLTE Gegenstand, auch aus Feld 2.
        texte = dict(self.STANDARD_TEXTE, **{anmeldeformular_gegenstand_feld(2, 2): "Leine"})
        pfad = self._pdf("ed.pdf", texte, haken=(ANMELDEFORMULAR_PRUEFUNG_PRAEFIX + "ED2-Trümmerfeld",))
        ergebnis = importiere_anmeldeformular_pdf(self.conn, [pfad])
        self.assertEqual((ergebnis.importiert, ergebnis.hinweise), (1, []))
        t = list_teilnehmer(self.conn)[0]
        self.assertEqual((t["gegenstand_1"], t["gegenstand_2"]), ("Leine", None))

    def test_vollstaendiges_formular_wird_uebernommen(self):
        texte = dict(self.STANDARD_TEXTE, **{
            anmeldeformular_gegenstand_feld(2, 1): "Handschuh",
            anmeldeformular_gegenstand_feld(2, 2): " Schlüssel ",
            # Gegenstand in einem anderen LK-Block wird ignoriert.
            anmeldeformular_gegenstand_feld(3, 3): "Socke",
        })
        pfad = self._pdf("anna.pdf", texte, haken=(
            ANMELDEFORMULAR_PRUEFUNG_PRAEFIX + "ED2-Trümmerfeld",
            ANMELDEFORMULAR_HUENDIN, ANMELDEFORMULAR_KENNZEICHNUNG_TAETO,
        ))
        ergebnis = importiere_anmeldeformular_pdf(self.conn, [pfad])
        self.assertEqual((ergebnis.importiert, ergebnis.fehler, ergebnis.uebersprungen), (1, [], []))
        t = list_teilnehmer(self.conn)[0]
        self.assertEqual((t["art"], t["stufe"], t["disziplin"]), ("ED", 2, "Trümmerfeld"))
        self.assertEqual((t["vorname"], t["nachname"], t["rufname_hund"]), ("Anna", "Muster", "Rex"))
        self.assertEqual(t["geschlecht"], "Hündin")
        self.assertEqual(t["chip_nr"], "Täto 12345")
        self.assertEqual(t["schulterhoehe_cm"], 45)
        self.assertEqual(t["wurftag"], "2020-02-01")
        self.assertEqual(t["tollwutimpfung_bis"], "2027-12-31")
        self.assertEqual((t["strasse"], t["email"], t["verband"]), ("Hauptstraße", "anna@example.org", "BLV"))
        for spalte in ("halter_vorname", "halter_nachname", "halter_strasse", "halter_hausnummer",
                       "halter_plz", "halter_ort", "halter_mitgliedsnummer", "halter_mitgliedsverein",
                       "halter_lu_nr"):
            self.assertEqual(t[spalte], self.STANDARD_TEXTE[spalte], spalte)
        # UX-Test 02.10.2026, U11: bei Einzeldisziplin nur der erste Gegenstand, der zweite
        # wird im Import-Ergebnis als nicht übernommen genannt.
        self.assertEqual((t["gegenstand_1"], t["gegenstand_2"], t["gegenstand_3"]), ("Handschuh", None, None))
        self.assertEqual((t["gegenstand_1_disziplin"], t["gegenstand_2_disziplin"]), (None, None))
        self.assertEqual(len(ergebnis.hinweise), 1)
        self.assertIn("nicht übernommen „Schlüssel“", ergebnis.hinweise[0])

    def test_nicht_angebotene_pruefung_wird_abgelehnt(self):
        # Verifikation 28.09.2026, Befund 1: Formular eines anderen Termins / falscher Termin.
        set_veranstaltung(self.conn, verein="HSV Musterstadt", datum="2026-11-14",
                          angebotene_pruefungen=pruefungen_als_text(["DK1"]))
        pfad = self._pdf("alt.pdf", haken=(ANMELDEFORMULAR_PRUEFUNG_PRAEFIX + "ED2-Trümmerfeld",))
        ergebnis = importiere_anmeldeformular_pdf(self.conn, [pfad])
        self.assertEqual(ergebnis.importiert, 0)
        self.assertEqual(len(ergebnis.fehler), 1)
        self.assertIn("alt.pdf: Trümmer LK 2 wird in diesem Termin nicht angeboten", ergebnis.fehler[0])
        self.assertEqual(list_teilnehmer(self.conn), [])

    def test_zerlegte_umlaute_werden_normalisiert_und_als_dublette_erkannt(self):
        # Verifikation 28.09.2026, Befund 2: "Mu" + kombinierendes Trema (NFD) statt "Mü".
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Müller", vorname="Anna", rufname_hund="Rex", art="DK", stufe=1))
        from pypdf import PdfWriter

        def nfd_pdf(dateiname, pruefung):
            # reportlab kann den kombinierenden Umlaut nicht darstellen - der zerlegte Wert
            # wird deshalb wie von einem PDF-Programm nachträglich per pypdf gesetzt.
            pfad = self._pdf(dateiname, haken=(ANMELDEFORMULAR_PRUEFUNG_PRAEFIX + pruefung,))
            writer = PdfWriter(clone_from=pfad)
            writer.update_page_form_field_values(
                writer.pages[0], {"nachname": "Müller", "ort": "München"},
                auto_regenerate=False,
            )
            with open(pfad, "wb") as datei:
                writer.write(datei)
            return pfad

        pfad_dk = nfd_pdf("nfd_dk.pdf", "DK1")
        pfad_ed = nfd_pdf("nfd_ed.pdf", "ED1-Flächensuche")
        ergebnis = importiere_anmeldeformular_pdf(self.conn, [pfad_dk, pfad_ed])
        self.assertEqual(ergebnis.fehler, [])
        self.assertEqual(len(ergebnis.uebersprungen), 1)
        self.assertIn("nfd_dk.pdf", ergebnis.uebersprungen[0])
        neu = [t for t in list_teilnehmer(self.conn) if t["art"] == "ED"][0]
        self.assertEqual((neu["nachname"], neu["ort"]), ("Müller", "München"))

    def test_kreuz_nur_im_darstellungszustand_wird_erkannt(self):
        # Verifikation 28.09.2026, Befund 3: manche PDF-Programme setzen beim Ankreuzen nur
        # /AS des Widgets und lassen /V auf /Off.
        from pypdf import PdfWriter
        from pypdf.generic import NameObject

        pfad = self._pdf("as.pdf", haken=(ANMELDEFORMULAR_PRUEFUNG_PRAEFIX + "DK1",))
        writer = PdfWriter(clone_from=pfad)
        for annot in writer.pages[0]["/Annots"]:
            widget = annot.get_object()
            if widget.get("/T") in (ANMELDEFORMULAR_HUENDIN, ANMELDEFORMULAR_KENNZEICHNUNG_TAETO):
                an = [k for k in widget["/AP"]["/N"] if k != "/Off"][0]
                widget[NameObject("/AS")] = NameObject(an)
                self.assertEqual(widget.get("/V"), "/Off")
        with open(pfad, "wb") as datei:
            writer.write(datei)
        ergebnis = importiere_anmeldeformular_pdf(self.conn, [pfad])
        self.assertEqual(ergebnis.fehler, [])
        t = list_teilnehmer(self.conn)[0]
        self.assertEqual((t["geschlecht"], t["chip_nr"]), ("Hündin", "Täto 12345"))

    def test_termin_ohne_angebotene_pruefungen_eigene_meldung(self):
        # Zweite Verifikation 28.09.2026, N1.
        set_veranstaltung(self.conn, verein="HSV Musterstadt", datum="2026-11-14")
        pfad = self._pdf("anna.pdf", haken=(ANMELDEFORMULAR_PRUEFUNG_PRAEFIX + "DK1",))
        ergebnis = importiere_anmeldeformular_pdf(self.conn, [pfad])
        self.assertEqual(ergebnis.importiert, 0)
        self.assertIn("noch keine angebotenen Prüfungen hinterlegt", ergebnis.fehler[0])
        self.assertNotIn("anderen Termins", ergebnis.fehler[0])

    def test_unsaubere_annotationen_verhindern_den_import_nicht(self):
        # Zweite Verifikation 28.09.2026, L1: /Annots null bzw. null-Einträge und /Parent
        # null dürfen den /AS-Rückfallweg nicht zum Scheitern der ganzen Datei bringen.
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, NullObject

        haken = (ANMELDEFORMULAR_PRUEFUNG_PRAEFIX + "DK1", ANMELDEFORMULAR_RUEDE)
        pfad_kaputt = self._pdf("kaputt.pdf", haken=haken)
        writer = PdfWriter(clone_from=pfad_kaputt)
        annots = writer.pages[0]["/Annots"]
        annots.append(NullObject())
        annots.append(DictionaryObject({NameObject("/AS"): NameObject("/Yes"), NameObject("/Parent"): NullObject()}))
        with open(pfad_kaputt, "wb") as datei:
            writer.write(datei)

        pfad_ohne = self._pdf("ohne_annots.pdf", texte=dict(self.STANDARD_TEXTE, rufname_hund="Rex2"), haken=haken)
        writer = PdfWriter(clone_from=pfad_ohne)
        writer.pages[0][NameObject("/Annots")] = NullObject()
        with open(pfad_ohne, "wb") as datei:
            writer.write(datei)

        ergebnis = importiere_anmeldeformular_pdf(self.conn, [pfad_kaputt, pfad_ohne])
        self.assertEqual((ergebnis.importiert, ergebnis.fehler), (2, []))
        self.assertEqual({t["geschlecht"] for t in list_teilnehmer(self.conn)}, {"Rüde"})

    def test_chip_und_ruede_ohne_praefix_dk(self):
        pfad = self._pdf("bruno.pdf", haken=(
            ANMELDEFORMULAR_PRUEFUNG_PRAEFIX + "DK1", ANMELDEFORMULAR_RUEDE, ANMELDEFORMULAR_KENNZEICHNUNG_CHIP,
        ))
        ergebnis = importiere_anmeldeformular_pdf(self.conn, [pfad])
        self.assertEqual(ergebnis.fehler, [])
        t = list_teilnehmer(self.conn)[0]
        self.assertEqual((t["art"], t["stufe"], t["disziplin"]), ("DK", 1, None))
        self.assertEqual((t["geschlecht"], t["chip_nr"], t["gegenstand_1"]), ("Rüde", "12345", None))

    def test_keine_pruefung_angekreuzt(self):
        pfad = self._pdf("leer.pdf", haken=(ANMELDEFORMULAR_HUENDIN,))
        ergebnis = importiere_anmeldeformular_pdf(self.conn, [pfad])
        self.assertEqual(ergebnis.importiert, 0)
        self.assertEqual(ergebnis.fehler, ["leer.pdf: keine Prüfung angekreuzt"])

    def test_mehrere_pruefungen_angekreuzt(self):
        pfad = self._pdf("zwei.pdf", haken=(
            ANMELDEFORMULAR_PRUEFUNG_PRAEFIX + "DK1", ANMELDEFORMULAR_PRUEFUNG_PRAEFIX + "ED3-Flächensuche",
        ))
        ergebnis = importiere_anmeldeformular_pdf(self.conn, [pfad])
        self.assertEqual(ergebnis.importiert, 0)
        self.assertEqual(len(ergebnis.fehler), 1)
        self.assertTrue(ergebnis.fehler[0].startswith("zwei.pdf: mehrere Prüfungen angekreuzt"), ergebnis.fehler)
        self.assertIn("DK-LK 1", ergebnis.fehler[0])
        self.assertIn("Fläche LK 3", ergebnis.fehler[0])

    def test_huendin_und_ruede_angekreuzt(self):
        pfad = self._pdf("beide.pdf", haken=(
            ANMELDEFORMULAR_PRUEFUNG_PRAEFIX + "DK1", ANMELDEFORMULAR_HUENDIN, ANMELDEFORMULAR_RUEDE,
        ))
        ergebnis = importiere_anmeldeformular_pdf(self.conn, [pfad])
        self.assertEqual(ergebnis.fehler, ["beide.pdf: Hündin und Rüde sind beide angekreuzt"])
        self.assertEqual(list_teilnehmer(self.conn), [])

    def test_ungueltiges_datum_wird_gemeldet(self):
        pfad = self._pdf("datum.pdf", dict(self.STANDARD_TEXTE, wurftag="32.13.2020"),
                         haken=(ANMELDEFORMULAR_PRUEFUNG_PRAEFIX + "DK1",))
        ergebnis = importiere_anmeldeformular_pdf(self.conn, [pfad])
        self.assertEqual(ergebnis.importiert, 0)
        self.assertTrue(ergebnis.fehler[0].startswith("datum.pdf: Wurftag:"), ergebnis.fehler)

    def test_dubletten_in_datenbank_und_im_selben_aufruf_werden_uebersprungen(self):
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="muster", vorname="ANNA", rufname_hund="rex", art="DK", stufe=1, disziplin=None,
        ))
        haken_dk1 = (ANMELDEFORMULAR_PRUEFUNG_PRAEFIX + "DK1",)
        haken_ed = (ANMELDEFORMULAR_PRUEFUNG_PRAEFIX + "ED1-Behältnisstrecke",)
        pfade = [
            self._pdf("schon_da.pdf", haken=haken_dk1),
            self._pdf("neu.pdf", haken=haken_ed),
            self._pdf("neu_nochmal.pdf", haken=haken_ed),
        ]
        ergebnis = importiere_anmeldeformular_pdf(self.conn, pfade)
        self.assertEqual(ergebnis.importiert, 1)
        self.assertEqual(ergebnis.fehler, [])
        self.assertEqual(ergebnis.uebersprungen, [
            "schon_da.pdf: Anna Muster mit Rex ist bereits gemeldet",
            "neu_nochmal.pdf: Anna Muster mit Rex ist bereits gemeldet",
        ])
        self.assertEqual(len(list_teilnehmer(self.conn)), 2)

    def test_pdf_ohne_formularfelder_und_keine_pdf_werden_gemeldet_rest_importiert(self):
        ohne = self._pdf("ohne.pdf", ohne_felder=True)
        kaputt = os.path.join(self.ordner, "kaputt.pdf")
        with open(kaputt, "w", encoding="utf-8") as datei:
            datei.write("das ist keine PDF-Datei")
        fehlt = os.path.join(self.ordner, "gibt_es_nicht.pdf")
        gut = self._pdf("gut.pdf", haken=(ANMELDEFORMULAR_PRUEFUNG_PRAEFIX + "DK3",))
        ergebnis = importiere_anmeldeformular_pdf(self.conn, [ohne, kaputt, fehlt, gut])
        self.assertEqual(ergebnis.importiert, 1)
        self.assertEqual(len(ergebnis.fehler), 3)
        self.assertEqual(
            ergebnis.fehler[0],
            "ohne.pdf: die PDF enthält keine Formularfelder (kein ausfüllbares Anmeldeformular)",
        )
        self.assertTrue(ergebnis.fehler[1].startswith("kaputt.pdf: Datei ist keine lesbare PDF-Datei"))
        self.assertTrue(ergebnis.fehler[2].startswith("gibt_es_nicht.pdf: Datei ist keine lesbare PDF-Datei"))

    def test_fremdes_formular_wird_abgelehnt(self):
        pfad = os.path.join(self.ordner, "fremd.pdf")
        c = _pdf_canvas.Canvas(pfad)
        c.acroForm.textfield(name="irgendwas", value="x", x=50, y=700, width=100, height=18)
        c.showPage()
        c.save()
        ergebnis = importiere_anmeldeformular_pdf(self.conn, [pfad])
        self.assertEqual(
            ergebnis.fehler, ["fremd.pdf: die PDF ist kein SHS-Anmeldeformular (keine passenden Formularfelder)"]
        )


def _postgres_frische_termin_tabellen(dsn: str):
    """Liefert eine Verbindung mit FRISCH angelegten Termin-Tabellen - das Pendant zur
    neuen, temporären SQLite-Datei in TestDatenbank.setUp, denn die Postgres-
    Testdatenbank ist eine dauerhafte, über alle Tests (und Testläufe) hinweg gemeinsam
    genutzte Datenbank. Die Tabellen werden dafür verworfen und von init_db_postgres()
    neu angelegt (IDs beginnen damit auch wieder bei 1).

    Früher wurden sie nur per TRUNCATE geleert. Die test_migration_*-Tests ersetzen
    "teilnehmer"/"ergebnisse" aber durch ältere Fassungen OHNE die CHECK-Constraints -
    die blieben dann in der Datenbank stehen, sodass die test_check_constraint_*-Tests
    bei einem ZWEITEN Lauf gegen dieselbe Datenbank fehlschlugen (im ersten Lauf laufen
    sie alphabetisch vor den Migrationstests; Befund vom 27.09.2026, siehe
    Fortschritt.md). In der CI fiel das nie auf, weil der Service-Container dort immer
    frisch ist."""
    conn = init_db_postgres(dsn)
    conn.execute(
        "DROP TABLE IF EXISTS ergebnisse, teilnehmer, veranstaltung, zeitplan_eintrag, "
        "zeitplan_richter CASCADE"
    )
    conn.commit()
    conn.close()
    return init_db_postgres(dsn)


class _PostgresBackendMixin:
    """Lässt die von TestDatenbank/TestZeitplan geerbten Testmethoden zusätzlich gegen
    eine echte PostgreSQL-Datenbank laufen (siehe init_db_postgres() in db.py). Wird per
    Mehrfachvererbung VOR TestDatenbank/TestZeitplan eingemischt (siehe die beiden
    Klassen unten), sodass setUp/tearDown/IntegrityErrorTyp/_ID_SPALTE_DDL/_neu_verbinden
    von hier verwendet werden, alle test_*-Methoden aber unverändert von der jeweiligen
    Basisklasse geerbt werden.

    Übersprungen (nicht fehlgeschlagen), wenn keine Testdatenbank über die
    Umgebungsvariable SHS_TEST_POSTGRES_DSN verfügbar ist oder psycopg2 nicht installiert
    ist - lokal typischerweise beides der Fall, läuft aber in der CI gegen einen echten
    PostgreSQL-Service-Container (siehe tests.yml)."""

    IntegrityErrorTyp = psycopg2.IntegrityError if psycopg2 is not None else Exception
    _ID_SPALTE_DDL = "INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY"
    # Siehe Kommentar bei TestDatenbank._DROP_TEILNEHMER_SQL_ZUSATZ oben - PostgreSQL
    # erzwingt die Fremdschlüsselbeziehung von "ergebnisse" auf "teilnehmer", SQLite
    # (Standardeinstellung) nicht.
    _DROP_TEILNEHMER_SQL_ZUSATZ = " CASCADE"

    def setUp(self):
        if not _POSTGRES_TEST_DSN:
            self.skipTest(
                "SHS_TEST_POSTGRES_DSN nicht gesetzt - PostgreSQL-Tests übersprungen "
                "(z. B. lokal ohne laufenden Postgres-Server; läuft in der CI)"
            )
        if psycopg2 is None:
            self.skipTest("psycopg2 nicht installiert - PostgreSQL-Tests übersprungen")
        self.conn = _postgres_frische_termin_tabellen(_POSTGRES_TEST_DSN)

    def tearDown(self):
        if getattr(self, "conn", None) is not None:
            self.conn.close()

    def _neu_verbinden(self):
        self.conn.close()
        self.conn = init_db_postgres(_POSTGRES_TEST_DSN)
        return self.conn


class TestDatenbankPostgres(_PostgresBackendMixin, TestDatenbank):
    """Wiederholt sämtliche TestDatenbank-Tests gegen PostgreSQL statt SQLite -
    siehe _PostgresBackendMixin."""


class TestZeitplanPostgres(_PostgresBackendMixin, TestZeitplan):
    """Wiederholt sämtliche TestZeitplan-Tests gegen PostgreSQL statt SQLite -
    siehe _PostgresBackendMixin."""


# --- Terminverwaltung für PostgreSQL (mehrere Termine in einer gemeinsamen Datenbank) --
#
# Für verbinde_postgres_server()/erstelle_termin_postgres()/oeffne_termin_postgres()/
# liste_termine_postgres()/loesche_termin_postgres() (siehe dortige Kommentare in db.py)
# gibt es - anders als für TestDatenbank/TestZeitplan oben - kein SQLite-Gegenstück zum
# Wiederverwenden: "mehrere Termine in einer gemeinsamen Datenbank" ist ein Konzept, das
# bei der Desktop-Version (ein Termin = eine Datei) so nicht existiert. Eigene,
# eigenständige Tests, mit demselben Skip-Verhalten wie oben (kein SHS_TEST_POSTGRES_DSN/
# psycopg2 lokal -> übersprungen, läuft in der CI).

class TestTerminverwaltungPostgres(unittest.TestCase):
    def setUp(self):
        if not _POSTGRES_TEST_DSN:
            self.skipTest(
                "SHS_TEST_POSTGRES_DSN nicht gesetzt - PostgreSQL-Tests übersprungen "
                "(z. B. lokal ohne laufenden Postgres-Server; läuft in der CI)"
            )
        if psycopg2 is None:
            self.skipTest("psycopg2 nicht installiert - PostgreSQL-Tests übersprungen")
        self.conn = verbinde_postgres_server(_POSTGRES_TEST_DSN)
        self._registry_leeren()

    def tearDown(self):
        if getattr(self, "conn", None) is not None:
            self._registry_leeren()
            self.conn.close()

    def _registry_leeren(self):
        """Entfernt alle Termin-Schemas und Registry-Einträge eines evtl. vorigen
        Testlaufs, damit jeder Test mit einer leeren Registry beginnt - Pendant zur
        frischen, temporären SQLite-Datei in TestDatenbank.setUp()."""
        zeilen = self.conn.execute("SELECT schema_name FROM public.termin_registry").fetchall()
        for zeile in zeilen:
            self.conn.execute(f"DROP SCHEMA IF EXISTS {zeile['schema_name']} CASCADE")
        # "public." nicht weglassen: search_path zeigt hier ggf. noch auf das
        # zuletzt per oeffne_termin_postgres() geöffnete (und oben gerade
        # gelöschte!) Termin-Schema statt auf "public" - ein unqualifiziertes
        # "termin_registry" schlägt dann mit UndefinedTable fehl, weil "public"
        # nicht im search_path steht (in der echten CI gefunden, siehe
        # Fortschritt.md).
        self.conn.execute("DELETE FROM public.termin_registry")
        self.conn.commit()

    def test_verbindungsaufbau_wartet_nicht_auf_offene_fremde_transaktion(self):
        """Befund vom 27.09.2026: verbinde_postgres_server() führte bei JEDER Verbindung
        ALTER TABLE/CREATE INDEX aus und wartete dadurch unbegrenzt, solange eine andere
        Transaktion Sperren auf termin_registry/web_benutzer hielt. Hier hält self.conn
        genau solche Sperren (wie eine laufende Web-Anfrage); die zweite Verbindung
        bekommt ein lock_timeout von 2 s und würde mit LockNotAvailable scheitern, falls
        sie doch wieder eine Tabellensperre bräuchte. Das Timeout kommt über die
        libpq-Umgebungsvariable PGOPTIONS statt über die DSN - so funktioniert es mit
        URI- wie mit key=value-DSNs gleichermaßen."""
        self.conn.execute("LOCK TABLE public.termin_registry IN ACCESS SHARE MODE")
        self.conn.execute("LOCK TABLE public.web_benutzer IN ROW EXCLUSIVE MODE")
        try:
            with patch.dict(os.environ, {"PGOPTIONS": "-c lock_timeout=2000"}):
                zweite = verbinde_postgres_server(_POSTGRES_TEST_DSN)
            zweite.close()
        finally:
            self.conn.rollback()

    def test_zwei_termine_sind_voneinander_isoliert(self):
        a = erstelle_termin_postgres(self.conn)
        oeffne_termin_postgres(self.conn, a.schema_name)
        set_veranstaltung(self.conn, verein="Verein A", datum="2026-09-19")
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="Muster", vorname="Anna", rufname_hund="Rex", art="ED", stufe=1, disziplin="Trümmerfeld",
        ))

        b = erstelle_termin_postgres(self.conn)
        oeffne_termin_postgres(self.conn, b.schema_name)
        set_veranstaltung(self.conn, verein="Verein B", datum="2026-10-01")

        # Termin B sieht weder den Teilnehmer noch die Veranstaltungsdaten von Termin A
        self.assertEqual(list_teilnehmer(self.conn), [])
        self.assertEqual(get_veranstaltung(self.conn)["verein"], "Verein B")

        oeffne_termin_postgres(self.conn, a.schema_name)
        self.assertEqual(len(list_teilnehmer(self.conn)), 1)
        self.assertEqual(get_veranstaltung(self.conn)["verein"], "Verein A")

    def test_liste_termine_zeigt_verein_ort_datum_und_teilnehmerzahl_neueste_zuerst(self):
        a = erstelle_termin_postgres(self.conn)
        oeffne_termin_postgres(self.conn, a.schema_name)
        set_veranstaltung(self.conn, verein="Verein A", ort="Ort A", datum="2026-09-19")
        add_teilnehmer(self.conn, NeuerTeilnehmer(
            nachname="X", vorname="Y", rufname_hund="Z", art="DK", stufe=1,
        ))

        b = erstelle_termin_postgres(self.conn)
        oeffne_termin_postgres(self.conn, b.schema_name)
        set_veranstaltung(self.conn, verein="Verein B", ort="Ort B", datum="2026-10-01")

        termine = liste_termine_postgres(self.conn)
        self.assertEqual(len(termine), 2)
        self.assertEqual(termine[0].verein, "Verein B")  # neuestes Datum zuerst
        self.assertEqual(termine[0].ort, "Ort B")
        self.assertEqual(termine[0].anzahl_teilnehmer, 0)
        self.assertEqual(termine[1].verein, "Verein A")
        self.assertEqual(termine[1].anzahl_teilnehmer, 1)

    def test_loeschen_entfernt_nur_den_einen_termin(self):
        a = erstelle_termin_postgres(self.conn)
        oeffne_termin_postgres(self.conn, a.schema_name)
        set_veranstaltung(self.conn, verein="Verein A", datum="2026-09-19")

        b = erstelle_termin_postgres(self.conn)
        oeffne_termin_postgres(self.conn, b.schema_name)
        set_veranstaltung(self.conn, verein="Verein B", datum="2026-10-01")

        loesche_termin_postgres(self.conn, a.schema_name)

        termine = liste_termine_postgres(self.conn)
        self.assertEqual([t.schema_name for t in termine], [b.schema_name])

        vorhandene_schemas = {
            zeile["schema_name"]
            for zeile in self.conn.execute("SELECT schema_name FROM information_schema.schemata").fetchall()
        }
        self.assertNotIn(a.schema_name, vorhandene_schemas)

    def test_ungueltiger_schema_name_wird_abgelehnt(self):
        # Schützt davor, dass ein Schema-Name jemals ungeprüft in SET search_path/
        # CREATE/DROP SCHEMA landet (siehe _pruefe_schema_name in db.py).
        with self.assertRaises(ValueError):
            loesche_termin_postgres(self.conn, "public")
        with self.assertRaises(ValueError):
            loesche_termin_postgres(self.conn, "termin_1; DROP SCHEMA public CASCADE; --")
        with self.assertRaises(ValueError):
            oeffne_termin_postgres(self.conn, "nicht_erlaubt")


class TestBenutzerkontenPostgres(unittest.TestCase):
    """Prüft die globalen Web-Benutzerkonten (siehe db.py, Abschnitt "Benutzerkonten der
    Web-Version") gegen einen echten PostgreSQL-Server - abgelöst hat diese
    Benutzerverwaltung den früheren, hier bis vor Kurzem getesteten gemeinsamen
    Zugangscode je Termin (siehe Git-Historie dieser Datei). Dasselbe Skip-Verhalten wie
    TestTerminverwaltungPostgres oben (kein SHS_TEST_POSTGRES_DSN/psycopg2 lokal ->
    übersprungen, läuft in der CI)."""

    IntegrityErrorTyp = psycopg2.IntegrityError if psycopg2 is not None else Exception

    def setUp(self):
        if not _POSTGRES_TEST_DSN:
            self.skipTest(
                "SHS_TEST_POSTGRES_DSN nicht gesetzt - PostgreSQL-Tests übersprungen "
                "(z. B. lokal ohne laufenden Postgres-Server; läuft in der CI)"
            )
        if psycopg2 is None:
            self.skipTest("psycopg2 nicht installiert - PostgreSQL-Tests übersprungen")
        self.conn = verbinde_postgres_server(_POSTGRES_TEST_DSN)
        self.conn.execute("DELETE FROM public.web_benutzer")
        self.conn.commit()

    def tearDown(self):
        if getattr(self, "conn", None) is not None:
            # rollback() zuerst: einige Tests (z.B. test_doppelter_benutzername_wird_
            # abgelehnt) lösen absichtlich einen IntegrityError aus, um ihn zu prüfen -
            # PostgreSQL markiert die laufende Transaktion danach als abgebrochen, jeder
            # weitere Befehl auf derselben Verbindung schlägt dann mit
            # InFailedSqlTransaction fehl, bis zurückgerollt wurde (anders als SQLite,
            # das diese Einschränkung nicht kennt - deshalb fiel das hier erst beim
            # ersten echten Lauf gegen PostgreSQL auf). rollback() selbst ist auch ohne
            # abgebrochene Transaktion unschädlich.
            self.conn.rollback()
            self.conn.execute("DELETE FROM public.web_benutzer")
            self.conn.commit()
            self.conn.close()

    def test_ohne_konten_gibt_es_keinen_admin(self):
        self.assertFalse(gibt_es_admin(self.conn))

    def test_admin_einrichten_legt_ersten_admin_an(self):
        self.assertTrue(admin_einrichten(self.conn, "chef", "sicheres_passwort"))
        self.assertTrue(gibt_es_admin(self.conn))
        konto = pruefe_login(self.conn, "chef", "sicheres_passwort")
        self.assertEqual(_ohne_kennung(konto), {"benutzername": "chef", "ist_admin": True})
        # C-1 (03.10.2026): Konto-Kennung für die Session, gleich zu benutzer_stand().
        self.assertEqual(konto["kennung"], benutzer_stand(self.conn, "chef")["kennung"])

    def test_admin_einrichten_lehnt_zweiten_ersten_admin_ab(self):
        admin_einrichten(self.conn, "chef", "sicheres_passwort")
        self.assertFalse(admin_einrichten(self.conn, "chef2", "anderes_passwort"))
        # Das ursprüngliche Konto bleibt unverändert der einzige Administrator.
        self.assertEqual([b["benutzername"] for b in liste_benutzer(self.conn) if b["ist_admin"]], ["chef"])

    def test_pruefe_login_mit_falschem_passwort_liefert_none(self):
        admin_einrichten(self.conn, "chef", "sicheres_passwort")
        self.assertIsNone(pruefe_login(self.conn, "chef", "falsch"))

    def test_pruefe_login_mit_unbekanntem_benutzer_liefert_none(self):
        self.assertIsNone(pruefe_login(self.conn, "gibtsnicht", "irgendwas"))

    def test_benutzer_anlegen_ohne_adminrechte(self):
        admin_einrichten(self.conn, "chef", "sicheres_passwort")
        benutzer_anlegen(self.conn, "helfer", "helferpasswort")
        konto = pruefe_login(self.conn, "helfer", "helferpasswort")
        self.assertEqual(_ohne_kennung(konto), {"benutzername": "helfer", "ist_admin": False})

    def test_liste_benutzer_alphabetisch_ohne_passwort_hash(self):
        admin_einrichten(self.conn, "zeno", "sicheres_passwort")
        benutzer_anlegen(self.conn, "anna", "anderes_passwort")
        namen = [b["benutzername"] for b in liste_benutzer(self.conn)]
        self.assertEqual(namen, ["anna", "zeno"])
        self.assertNotIn("passwort_hash", liste_benutzer(self.conn)[0])

    def test_doppelter_benutzername_wird_abgelehnt(self):
        admin_einrichten(self.conn, "chef", "sicheres_passwort")
        with self.assertRaises(self.IntegrityErrorTyp):
            benutzer_anlegen(self.conn, "chef", "irgendein_passwort")

    def test_benutzername_der_sich_nur_in_gross_kleinschreibung_unterscheidet_wird_abgelehnt(self):
        """QS-Fund (19./20.09.): benutzername ist zwar PRIMARY KEY, das schützt aber nur
        vor exakt gleich geschriebenen Namen - pruefe_login() vergleicht beim Anmelden
        GROSS-/kleinschreibungs-UNABHÄNGIG (siehe dortiger Kommentar). Ohne den
        zusätzlichen Unique-Index auf LOWER(benutzername) (siehe
        _WEB_BENUTZER_INDEX_BENUTZERNAME_LOWER) könnten "chef" und "Chef" gleichzeitig
        als zwei getrennte Konten existieren, obwohl der Login sie nicht unterscheiden
        kann."""
        admin_einrichten(self.conn, "chef", "sicheres_passwort")
        with self.assertRaises(self.IntegrityErrorTyp):
            benutzer_anlegen(self.conn, "Chef", "irgendein_passwort")
        # rollback() zwischen den beiden Versuchen nötig - siehe Kommentar in tearDown()
        # oben: PostgreSQL markiert die Transaktion nach dem ersten absichtlich
        # ausgelösten IntegrityError als abgebrochen, jeder weitere Befehl auf derselben
        # Verbindung (auch der zweite benutzer_anlegen()-Versuch hier) schlägt sonst mit
        # InFailedSqlTransaction statt mit dem hier erwarteten IntegrityError fehl.
        self.conn.rollback()
        with self.assertRaises(self.IntegrityErrorTyp):
            benutzer_anlegen(self.conn, "CHEF", "irgendein_passwort")

    def test_benutzer_loeschen_entfernt_konto(self):
        admin_einrichten(self.conn, "chef", "sicheres_passwort")
        benutzer_anlegen(self.conn, "helfer", "helferpasswort")
        benutzer_loeschen(self.conn, "helfer")
        self.assertIsNone(pruefe_login(self.conn, "helfer", "helferpasswort"))

    def test_letzter_admin_kann_nicht_geloescht_werden(self):
        admin_einrichten(self.conn, "chef", "sicheres_passwort")
        with self.assertRaises(ValueError):
            benutzer_loeschen(self.conn, "chef")
        self.assertTrue(gibt_es_admin(self.conn))

    def test_einer_von_zwei_admins_kann_geloescht_werden(self):
        admin_einrichten(self.conn, "chef", "sicheres_passwort")
        benutzer_anlegen(self.conn, "chef2", "anderes_passwort", ist_admin=True)
        benutzer_loeschen(self.conn, "chef2")  # darf nicht werfen - "chef" bleibt Admin
        self.assertIsNone(pruefe_login(self.conn, "chef2", "anderes_passwort"))
        self.assertTrue(gibt_es_admin(self.conn))

    def test_login_ignoriert_gross_und_kleinschreibung_beim_benutzernamen(self):
        # Praxisfall: Der Benutzername wurde z. B. beim Anlegen als "Marco" gespeichert,
        # ein Mobilgerät schreibt beim späteren Anmelden aber automatisch den ersten
        # Buchstaben groß ("Autokapitalisierung") oder klein - der Login soll trotzdem
        # funktionieren, nur das Passwort bleibt GROSS-/kleinschreibungsempfindlich.
        admin_einrichten(self.conn, "Marco", "sicheres_passwort")
        self.assertEqual(
            _ohne_kennung(pruefe_login(self.conn, "marco", "sicheres_passwort")),
            {"benutzername": "Marco", "ist_admin": True},
        )
        self.assertEqual(
            _ohne_kennung(pruefe_login(self.conn, "MARCO", "sicheres_passwort")),
            {"benutzername": "Marco", "ist_admin": True},
        )
        self.assertIsNone(pruefe_login(self.conn, "Marco", "Sicheres_Passwort"))

    def test_gleichzeitiges_loeschen_beider_admins_laesst_mindestens_einen_uebrig(self):
        # QS-Review (19./20.09.): benutzer_loeschen() prüfte vorher "gibt es noch >1
        # Admin?" per einfachem COUNT(*) OHNE Sperre - zwei zeitgleiche Löschversuche
        # konnten beide denselben (noch nicht aktualisierten) Zählerstand sehen und am
        # Ende gemeinsam 0 statt mindestens 1 Administrator übrig lassen. Der Fix (SELECT
        # ... FOR UPDATE auf den Admin-Zeilen vor dem Zählen) wird hier mit zwei ECHTEN,
        # unabhängigen Verbindungen und einem threading.Barrier geprüft, das beide Threads
        # so gut wie gleichzeitig starten lässt - PostgreSQLs Zeilensperre serialisiert die
        # beiden Transaktionen dann so, dass der zweite Thread den bereits aktualisierten
        # Zählerstand sieht, statt den veralteten.
        import threading

        admin_einrichten(self.conn, "chef1", "sicheres_passwort")
        benutzer_anlegen(self.conn, "chef2", "anderes_passwort", ist_admin=True)

        start = threading.Barrier(2)
        ergebnisse: dict[str, str] = {}

        def loeschen(name: str, conn) -> None:
            start.wait(timeout=5)
            try:
                benutzer_loeschen(conn, name)
                ergebnisse[name] = "geloescht"
            except ValueError:
                ergebnisse[name] = "abgelehnt"
            finally:
                conn.close()

        conn_a = verbinde_postgres_server(_POSTGRES_TEST_DSN)
        conn_b = verbinde_postgres_server(_POSTGRES_TEST_DSN)
        t1 = threading.Thread(target=loeschen, args=("chef1", conn_a))
        t2 = threading.Thread(target=loeschen, args=("chef2", conn_b))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        # Genau einer der beiden gleichzeitigen Versuche darf durchgekommen sein - NIEMALS
        # beide (das wäre der alte Bug: 0 Admins übrig, niemand kann sich mehr einloggen).
        self.assertEqual(sorted(ergebnisse.values()), ["abgelehnt", "geloescht"])
        self.assertEqual(
            [b["benutzername"] for b in liste_benutzer(self.conn) if b["ist_admin"]],
            ["chef1"] if ergebnisse["chef1"] == "abgelehnt" else ["chef2"],
        )


class TestTerminSyncPostgres(unittest.TestCase):
    """Prüft die dünnen, tatsächlich an PostgreSQL gebundenen Wrapper-Funktionen
    exportiere_termin_nach_postgres()/importiere_ergebnisse_aus_postgres() end-zu-Ende
    gegen einen echten Server (die eigentliche Kopierlogik dahinter ist bereits
    dialektunabhängig in TestTerminSync oben geprüft, siehe dortigen Klassen-Docstring)."""

    def setUp(self):
        if not _POSTGRES_TEST_DSN:
            self.skipTest(
                "SHS_TEST_POSTGRES_DSN nicht gesetzt - PostgreSQL-Tests übersprungen "
                "(z. B. lokal ohne laufenden Postgres-Server; läuft in der CI)"
            )
        if psycopg2 is None:
            self.skipTest("psycopg2 nicht installiert - PostgreSQL-Tests übersprungen")
        self.conn = verbinde_postgres_server(_POSTGRES_TEST_DSN)
        self._registry_leeren()

        fd, self.sqlite_pfad = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        os.remove(self.sqlite_pfad)
        self.sqlite_conn = init_db(self.sqlite_pfad)

    def tearDown(self):
        if getattr(self, "sqlite_conn", None) is not None:
            self.sqlite_conn.close()
            if os.path.exists(self.sqlite_pfad):
                os.remove(self.sqlite_pfad)
        if getattr(self, "conn", None) is not None:
            self._registry_leeren()
            self.conn.close()

    def _registry_leeren(self):
        # Siehe ausführlicher Kommentar bei TestTerminverwaltungPostgres._registry_leeren
        # oben - "public." beim DELETE nicht weglassen.
        zeilen = self.conn.execute("SELECT schema_name FROM public.termin_registry").fetchall()
        for zeile in zeilen:
            self.conn.execute(f"DROP SCHEMA IF EXISTS {zeile['schema_name']} CASCADE")
        self.conn.execute("DELETE FROM public.termin_registry")
        self.conn.commit()

    def test_export_veroeffentlicht_termin(self):
        set_veranstaltung(self.sqlite_conn, verein="Testverein", datum="2026-09-19")
        add_teilnehmer(self.sqlite_conn, NeuerTeilnehmer(
            nachname="Muster", vorname="Anna", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1,
        ))

        termin = exportiere_termin_nach_postgres(self.sqlite_conn, self.conn)

        self.assertEqual(termin.verein, "Testverein")
        self.assertEqual(termin.anzahl_teilnehmer, 1)
        # Taucht danach in der Termin-Auswahl der Web-Oberfläche auf (kein Zugangscode
        # mehr - der Login läuft über die Benutzerkonten, siehe TestBenutzerkontenPostgres).
        self.assertIn(termin.schema_name, [t.schema_name for t in liste_termine_postgres(self.conn)])

    def test_export_und_import_end_zu_ende(self):
        teilnehmer_id = add_teilnehmer(self.sqlite_conn, NeuerTeilnehmer(
            nachname="Muster", vorname="Anna", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1,
        ))

        termin = exportiere_termin_nach_postgres(self.sqlite_conn, self.conn)

        # "Am Prüfungstag": ein Richter trägt über die (hier simulierte) Web-Oberfläche
        # ein Ergebnis für den Teilnehmer mit Startnummer 1 ein.
        oeffne_termin_postgres(self.conn, termin.schema_name)
        postgres_teilnehmer = list_teilnehmer(self.conn)[0]
        eintragen_ergebnis(self.conn, postgres_teilnehmer["id"], "Trümmerfeld", 48, 28)

        bericht = importiere_ergebnisse_aus_postgres(self.conn, termin.schema_name, self.sqlite_conn)

        self.assertEqual(bericht.aktualisiert, 1)
        ergebnis = get_ergebnis(self.sqlite_conn, teilnehmer_id)
        self.assertEqual(ergebnis["suche_truemmerfeld"], 48)
        self.assertEqual(ergebnis["anzeige_truemmerfeld"], 28)


class TestDemoDaten(unittest.TestCase):
    """Die erfundenen Daten der Demoprüfung (demo_daten.py) müssen zur Datenschicht passen
    und genau die Wertnoten ergeben, die die Erklärtexte in desktop_demo.py beschreiben."""

    def setUp(self):
        import demo_daten
        from db import fehlende_startnummern_vergeben, set_veranstaltung

        self.demo = demo_daten
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = init_db(os.path.join(self.tmp.name, "demo.sqlite"))
        set_veranstaltung(self.conn, **demo_daten.veranstaltung())
        self.ids = {}
        for eintrag in demo_daten.TEILNEHMER:
            tid = add_teilnehmer(self.conn, NeuerTeilnehmer(**eintrag["daten"]))
            self.ids[eintrag["daten"]["nachname"]] = tid
            for disziplin, (suche, anzeige) in eintrag.get("ergebnis", {}).items():
                eintragen_ergebnis(self.conn, tid, disziplin, suche, anzeige)
            if eintrag.get("status") == "dq":
                setze_ergebnis_status(self.conn, tid, True, False)
        self.vergabe = fehlende_startnummern_vergeben(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_jede_pruefung_ist_angeboten_und_alle_bekommen_eine_startnummer(self):
        from db import angebotene_pruefungen, get_veranstaltung, pruefungs_kuerzel

        angeboten = {p.kuerzel for p in angebotene_pruefungen(get_veranstaltung(self.conn))}
        for t in list_teilnehmer(self.conn):
            self.assertIn(pruefungs_kuerzel(t["art"], t["stufe"], t["disziplin"]), angeboten)
        self.assertEqual(len(self.vergabe.vergeben), len(self.demo.TEILNEHMER))
        self.assertEqual(self.vergabe.ohne_bereich, [])
        self.assertEqual(self.vergabe.bereich_voll, [])

    def test_punkte_liegen_in_den_grenzen(self):
        from shs_core import ANZEIGE_MAX, SUCHE_MAX

        for eintrag in self.demo.TEILNEHMER:
            for suche, anzeige in eintrag.get("ergebnis", {}).values():
                self.assertTrue(0 <= suche <= SUCHE_MAX and 0 <= anzeige <= ANZEIGE_MAX)

    def test_wertnoten_und_genau_ein_stechen(self):
        fertig, ausstehend = berechne_auswertung(self.conn)
        self.assertEqual(ausstehend, [])
        noten = {t.name.split(",")[0]: t.wertnote.abkuerzung for t in fertig}
        self.assertEqual(noten, {
            "Albers": "V", "Brandt": "V", "Claasen": "G", "Dietrich": "SG", "Ehlers": "nB",
            "Fischer": "DISQ", "Gerdes": "SG", "Hansen": "G",
        })
        offen = sorted(t.name.split(",")[0] for t in fertig if t.stechen == "offen")
        self.assertEqual(offen, ["Albers", "Brandt"])
        self.assertIn(self.demo.STECHEN_SIEGER, offen)

    def test_anmerkungen_zeigen_nur_die_fehlende_chip_nummer(self):
        """Die Erklärung zu Schritt 4 kündigt nur Hansens fehlende Chip-Nr. an - sonst darf
        die Spalte „Anmerkungen“ nichts zeigen (Verifikation 04.10.2026, Befund 1)."""
        from db import teilnehmer_fehlende_pflichtangaben, teilnehmer_gegenstand_hinweis

        for t in list_teilnehmer(self.conn):
            self.assertIsNone(teilnehmer_gegenstand_hinweis(t), t["nachname"])
            fehlend = teilnehmer_fehlende_pflichtangaben(t)
            if t["nachname"] == "Hansen":
                self.assertEqual(len(fehlend), 1)
                self.assertIn("Chip", fehlend[0])
            else:
                self.assertEqual(fehlend, [], t["nachname"])

    def test_chip_nummer_fehlt_nur_beim_hinweis_teilnehmer_und_ist_fiktiv(self):
        ohne_chip = [t["daten"]["nachname"] for t in self.demo.TEILNEHMER if not t["daten"].get("chip_nr")]
        self.assertEqual(ohne_chip, ["Hansen"])
        for eintrag in self.demo.TEILNEHMER:
            chip = eintrag["daten"].get("chip_nr")
            if chip:
                self.assertTrue(chip.startswith("999"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
