"""Tests für den _PostgresConnection/_PostgresCursor-Kompatibilitäts-Layer in db.py
(siehe dortiger Modul-Docstring und die Kommentare bei SCHEMA_POSTGRES).

Anders als test_db.py (siehe dortige TestDatenbankPostgres/TestZeitplanPostgres) braucht
dieses Modul KEINEN echten PostgreSQL-Server und kein installiertes psycopg2 - stattdessen
wird die rohe psycopg2-Verbindung/der Cursor per unittest.mock ersetzt. Das prüft gezielt
die reine Übersetzungslogik des Wrappers (Platzhalter '?'->'%s', automatisches
'RETURNING id' für die drei betroffenen Tabellen, lastrowid-Emulation, Delegation von
executescript/commit/close) - unabhängig davon, ob in der jeweiligen Umgebung überhaupt
eine PostgreSQL-Anbindung verfügbar ist. Lief lokal bereits gegen einen echten
PostgreSQL-16-Server (siehe Entwicklungs-Notizen); diese Tests sichern die
Übersetzungslogik dauerhaft ab, ohne dafür einen Server zu benötigen."""

import unittest
from unittest.mock import MagicMock

import db


class TestPostgresConnectionWrapper(unittest.TestCase):
    def setUp(self):
        self.roh_conn = MagicMock()
        self.roh_cursor = MagicMock()
        self.roh_conn.cursor.return_value = self.roh_cursor
        self.conn = db._PostgresConnection(self.roh_conn)

    def test_insert_in_lastrowid_tabelle_bekommt_returning_und_platzhalter_uebersetzt(self):
        self.roh_cursor.fetchone.return_value = {"id": 42}
        cur = self.conn.execute("INSERT INTO teilnehmer (nachname) VALUES (?)", ("X",))
        gesendetes_sql, gesendete_params = self.roh_cursor.execute.call_args[0]
        self.assertEqual(gesendetes_sql, "INSERT INTO teilnehmer (nachname) VALUES (%s) RETURNING id")
        self.assertEqual(gesendete_params, ("X",))
        self.assertEqual(cur.lastrowid, 42)

    def test_insert_in_andere_tabelle_bekommt_kein_returning(self):
        cur = self.conn.execute("INSERT INTO ergebnisse (teilnehmer_id) VALUES (?)", (1,))
        gesendetes_sql, _ = self.roh_cursor.execute.call_args[0]
        self.assertEqual(gesendetes_sql, "INSERT INTO ergebnisse (teilnehmer_id) VALUES (%s)")
        self.assertIsNone(cur.lastrowid)

    def test_mehrzeiliges_insert_mit_fuehrendem_whitespace_wird_erkannt(self):
        # So schreibt add_teilnehmer() sein INSERT tatsächlich (mehrzeiliger String mit
        # führendem Newline/Einrückung) - die Erkennung darf daran nicht scheitern.
        sql = """
        INSERT INTO teilnehmer (
            nachname, vorname
        ) VALUES (?, ?)
        """
        self.roh_cursor.fetchone.return_value = {"id": 1}
        self.conn.execute(sql, ("A", "B"))
        gesendetes_sql, _ = self.roh_cursor.execute.call_args[0]
        self.assertTrue(gesendetes_sql.rstrip().endswith("RETURNING id"))

    def test_update_bekommt_kein_returning_obwohl_tabelle_in_der_liste_ist(self):
        self.conn.execute("UPDATE teilnehmer SET bezahlt = ? WHERE id = ?", (1, 1))
        gesendetes_sql, _ = self.roh_cursor.execute.call_args[0]
        self.assertNotIn("RETURNING", gesendetes_sql)

    def test_bereits_vorhandenes_returning_wird_nicht_doppelt_angehaengt(self):
        self.roh_cursor.fetchone.return_value = {"id": 1, "nachname": "X"}
        self.conn.execute("INSERT INTO teilnehmer (nachname) VALUES (?) RETURNING id, nachname", ("X",))
        gesendetes_sql, _ = self.roh_cursor.execute.call_args[0]
        self.assertEqual(gesendetes_sql.count("RETURNING"), 1)

    def test_executescript_leitet_an_execute_weiter(self):
        self.conn.executescript(db.SCHEMA_POSTGRES)
        self.roh_cursor.execute.assert_called_once_with(db.SCHEMA_POSTGRES)

    def test_commit_und_close_delegieren_an_die_rohe_verbindung(self):
        self.conn.commit()
        self.roh_conn.commit.assert_called_once()
        self.conn.close()
        self.roh_conn.close.assert_called_once()

    def test_rollback_delegiert_an_die_rohe_verbindung(self):
        # Gebraucht z.B. in test_db.TestBenutzerkontenPostgres.tearDown(), um nach einem
        # in einem Test absichtlich ausgelösten IntegrityError die von PostgreSQL als
        # abgebrochen markierte Transaktion zurückzusetzen, bevor die nächste Abfrage auf
        # derselben Verbindung läuft (siehe dortiger Kommentar).
        self.conn.rollback()
        self.roh_conn.rollback.assert_called_once()

    def test_fetchone_und_fetchall_delegieren_an_den_rohen_cursor(self):
        self.roh_cursor.fetchone.return_value = {"id": 1}
        self.roh_cursor.fetchall.return_value = [{"id": 1}, {"id": 2}]
        cur = self.conn.execute("SELECT * FROM teilnehmer")
        self.assertEqual(cur.fetchone(), {"id": 1})
        self.assertEqual(cur.fetchall(), [{"id": 1}, {"id": 2}])


class TestVorhandeneSpaltenPostgresZweig(unittest.TestCase):
    """_vorhandene_spalten() muss für eine _PostgresConnection (kein sqlite3.Connection)
    über information_schema.columns statt PRAGMA table_info gehen - siehe db.py."""

    def test_nutzt_information_schema_columns_mit_spaltenname_statt_positionsindex(self):
        roh_conn = MagicMock()
        roh_cursor = MagicMock()
        roh_conn.cursor.return_value = roh_cursor
        roh_cursor.fetchall.return_value = [{"column_name": "id"}, {"column_name": "verein"}]
        conn = db._PostgresConnection(roh_conn)

        spalten = db._vorhandene_spalten(conn, "veranstaltung")

        self.assertEqual(spalten, {"id", "verein"})
        gesendetes_sql, gesendete_params = roh_cursor.execute.call_args[0]
        self.assertIn("information_schema.columns", gesendetes_sql)
        self.assertEqual(gesendete_params, ("veranstaltung",))


if __name__ == "__main__":
    unittest.main()
