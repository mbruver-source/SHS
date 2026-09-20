"""Tests für db.py - Datenschicht + Zusammenspiel mit shs_core."""

import os
import pathlib
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from db import (
    NeuerTeilnehmer,
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
    init_db,
    init_db_postgres,
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
    termine_ordner,
    umbenennen_zeitplan_richter,
    update_teilnehmer,
    verbinde_postgres_server,
    vergebene_startnummern,
    verschiebe_zeitplan_eintrag,
    verschiebe_zeitplan_richter,
    zeitplan_gruppen,
)


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

        set_veranstaltung(
            self.conn, verein="SGV Köppern e.V.", datum="2026-09-19",
            vereins_nr="19010", pruefungsnummer="P-2026-04",
            wertungsrichter_1="A. Muster", wertungsrichter_2="B. Beispiel",
            pruefungsleiter="Katja Bruver",
        )
        v = get_veranstaltung(self.conn)
        self.assertEqual(v["vereins_nr"], "19010")
        self.assertEqual(v["pruefungsnummer"], "P-2026-04")
        self.assertEqual(v["wertungsrichter_1"], "A. Muster")
        self.assertEqual(v["wertungsrichter_2"], "B. Beispiel")
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
    """Tests für die Zeitplan-Verwaltung: Leistungsrichter-Spuren mit frei sortierbaren
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
        self.assertEqual(richter[0]["name"], "Leistungsrichter 1")
        self.assertEqual(richter[1]["name"], "Leistungsrichter 2")
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
        set_veranstaltung(conn, verein="SGV Köppern e.V.", datum="2026-09-19", ort="Köppern")
        add_teilnehmer(conn, NeuerTeilnehmer(
            nachname="A", vorname="A", rufname_hund="H", art="ED", stufe=1, disziplin="Trümmerfeld"))
        conn.close()

        termine = liste_termine(self.ordner)
        self.assertEqual(len(termine), 1)
        self.assertEqual(termine[0].verein, "SGV Köppern e.V.")
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
            wertungsrichter_1="Richter A",
        )
        add_teilnehmer(self.quelle, NeuerTeilnehmer(
            nachname="Muster", vorname="Anna", rufname_hund="Rex", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1, bezahlt=True,
        ))

        kopiere_termin_daten(self.quelle, self.ziel)

        veranstaltung = get_veranstaltung(self.ziel)
        self.assertEqual(veranstaltung["verein"], "Testverein")
        self.assertEqual(veranstaltung["wertungsrichter_1"], "Richter A")

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
