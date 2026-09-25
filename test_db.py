"""Tests für db.py - Datenschicht + Zusammenspiel mit shs_core."""

import os
import pathlib
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from db import (
    NeuerTeilnehmer,
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
    berechne_teilnehmer_lk_uebersicht,
    berechne_zeitplan,
    berechne_zeitplan_bloecke,
    dateiname_vorschlagen,
    delete_teilnehmer,
    eintragen_ergebnis,
    erstelle_termin_postgres,
    exportiere_termin_nach_postgres,
    gegenstand_fuer_disziplin,
    get_ergebnis,
    get_teilnehmer,
    get_veranstaltung,
    gibt_es_admin,
    importiere_ergebnisse_aus_postgres,
    importiere_ergebnisse_nach_startnummer,
    importiere_teilnehmer_aus_csv,
    importiere_teilnehmer_aus_oma,
    importiere_teilnehmer_stammdaten,
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
    pruefe_login,
    pruefungsgebuehr_fuer_art,
    set_veranstaltung,
    setze_bezahlt,
    setze_ergebnis_status,
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
        # set_veranstaltung funktioniert danach ganz normal weiter.
        set_veranstaltung(conn, verein="Alt-Verein", datum="2025-01-01", pruefungsnummer="P-1")
        self.assertEqual(get_veranstaltung(conn)["pruefungsnummer"], "P-1")

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

    def test_importiere_teilnehmer_aus_csv_bricht_bei_falscher_kodierung_sauber_ab(self):
        # QS-Fund (Codeprüfung 21.09.): eine mit Windows-ANSI statt UTF-8 gespeicherte
        # CSV-Datei (auf deutschem Windows beim "CSV speichern unter" in Excel der
        # Standard) löste beim Weiterlesen einen UnicodeDecodeError AUSSERHALB der
        # zeilenweisen try/except-Behandlung aus - der Import brach dadurch komplett mit
        # einer unbehandelten Exception ab statt "nur die fehlerhafte Zeile zu
        # überspringen" (siehe Docstring). Jetzt: sauberer Abbruch mit verständlicher
        # Fehlermeldung statt Absturz; bereits verarbeitete Zeilen bleiben importiert.
        #
        # Genug gültige Zeilen VOR der fehlerhaften, um den internen Lesepuffer von
        # TextIOWrapper (io.DEFAULT_BUFFER_SIZE = 8192 Byte) zu überschreiten - sonst
        # würde Python den ungültigen Byte bereits beim Decodieren des ERSTEN Puffer-
        # Blocks bemerken, bevor auch nur eine Zeile daraus ausgeliefert wurde, und der
        # Test würde fälschlich "0 importiert" statt des eigentlich interessanten
        # Verhaltens (Teilimport + sauberer Abbruch) prüfen.
        fd, pfad = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        with open(pfad, "wb") as f:
            f.write("nachname,vorname,rufname_hund,art,stufe,disziplin\n".encode("utf-8"))
            for i in range(300):
                f.write(f"Gut{i},Vorname{i},Hund{i},ED,1,Trümmerfeld\n".encode("utf-8"))
            # Eine mit Windows-1252 statt UTF-8 kodierte Zeile (enthält ein ü als 0xFC,
            # in UTF-8 ungültig als Fortsetzungsbyte) - löst beim Lesen als UTF-8 einen
            # UnicodeDecodeError aus.
            f.write("Schlecht,Zweiter,H\xfcndchen,ED,1,Trümmerfeld\n".encode("cp1252"))
        try:
            ergebnis = importiere_teilnehmer_aus_csv(self.conn, pfad)
            self.assertGreater(ergebnis.importiert, 0)
            self.assertEqual(len(ergebnis.fehler), 1)
            self.assertIn("UTF-8", ergebnis.fehler[0])
            namen = {t["nachname"] for t in list_teilnehmer(self.conn)}
            self.assertNotIn("Schlecht", namen)
            self.assertEqual(len(namen), ergebnis.importiert)
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
            conn, verein="SGV Köppern e.V.", datum="2026-09-19", ort="Köppern", vereins_nr="123"
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
        self.assertEqual(termine[0].datum, "2026-09-19")
        self.assertEqual(termine[0].anzahl_teilnehmer, 1)
        self.assertTrue(termine[0].lesbar)

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

    def test_kopiert_veranstaltung_und_teilnehmer(self):
        set_veranstaltung(
            self.quelle, verein="Testverein", ort="Testort", datum="2026-09-19",
            wertungsrichter_1="Richter A", wertungsrichter_5="Richter E",
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


def _postgres_testdaten_leeren(conn) -> None:
    """Setzt die PostgreSQL-Testdatenbank vor jedem Test zurück. Anders als bei SQLite,
    wo jeder Test automatisch eine frische, temporäre Datei bekommt (siehe
    TestDatenbank.setUp), ist die Postgres-Testdatenbank eine dauerhafte, über alle Tests
    hinweg gemeinsam genutzte Datenbank. RESTART IDENTITY sorgt zusätzlich dafür, dass
    neu vergebene IDs - wie bei einer frischen SQLite-Datei - wieder bei 1 anfangen."""
    conn.execute(
        "TRUNCATE TABLE ergebnisse, teilnehmer, veranstaltung, zeitplan_eintrag, "
        "zeitplan_richter RESTART IDENTITY CASCADE"
    )
    conn.commit()


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
        self.conn = init_db_postgres(_POSTGRES_TEST_DSN)
        _postgres_testdaten_leeren(self.conn)

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
        self.assertEqual(konto, {"benutzername": "chef", "ist_admin": True})

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
        self.assertEqual(konto, {"benutzername": "helfer", "ist_admin": False})

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
            pruefe_login(self.conn, "marco", "sicheres_passwort"),
            {"benutzername": "Marco", "ist_admin": True},
        )
        self.assertEqual(
            pruefe_login(self.conn, "MARCO", "sicheres_passwort"),
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
