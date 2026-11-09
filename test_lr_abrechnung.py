"""Tests der Leistungsrichter-Abrechnung (lr_abrechnung.py, Marco 09.11.2026): Rechnen,
Eingaben lesen, Betrag in Worten, Speicherung in der Termin-Datei und die beiden PDFs."""

import json
import os
import sqlite3
import tempfile
import unittest
from decimal import Decimal

import db
import lr_abrechnung as lr


def _veranstaltung(**felder):
    basis = {"verein": "HSV", "datum": "2026-11-14", "wertungsrichter_1": "Anna Alt",
             "wertungsrichter_2": "Bernd Braun"}
    basis.update(felder)
    return basis


class TestZahlen(unittest.TestCase):
    def test_dezimal_lesen(self):
        self.assertEqual(lr.dezimal_lesen("0,35"), Decimal("0.35"))
        self.assertEqual(lr.dezimal_lesen("12.5"), Decimal("12.5"))
        self.assertEqual(lr.dezimal_lesen("1.234,5"), Decimal("1234.5"))
        self.assertEqual(lr.dezimal_lesen(" 50 "), Decimal("50"))
        for ungueltig in (None, "", "  ", "abc", "-1", "1,2,3", "NaN", "Infinity", "1e999999"):
            self.assertIsNone(lr.dezimal_lesen(ungueltig), ungueltig)

    def test_tausenderpunkt_bei_km_und_pauschale(self):
        self.assertEqual(lr.km_lesen("1.234"), Decimal("1234.0"))
        self.assertEqual(lr.km_lesen("1.234,5"), Decimal("1234.5"))
        self.assertEqual(lr.km_lesen("123.5"), Decimal("123.5"))
        self.assertEqual(lr.km_lesen("0.500"), Decimal("0.5"))
        self.assertIsNone(lr.km_lesen("12.345"))  # über der Obergrenze, keine stille Umdeutung
        self.assertEqual(lr.pauschale_lesen("1.000"), Decimal("1000.00"))
        self.assertEqual(lr.km_satz_lesen("0.355"), Decimal("0.355"))  # Satz: nie Tausender

    def test_obergrenzen(self):
        self.assertIsNone(lr.km_lesen("10000,1"))
        self.assertEqual(lr.km_lesen("10000"), Decimal("10000.0"))
        self.assertIsNone(lr.km_satz_lesen("10,01"))
        self.assertIsNone(lr.pauschale_lesen("10000,01"))

    def test_km_auf_eine_stelle_gerundet(self):
        self.assertEqual(lr.km_lesen("123,45"), Decimal("123.5"))
        self.assertEqual(lr.km_lesen("123,44"), Decimal("123.4"))

    def test_texte(self):
        self.assertEqual(lr.euro_text(Decimal("1234.5")), "1.234,50 €")
        self.assertEqual(lr.euro_text(Decimal("0.35")), "0,35 €")
        self.assertEqual(lr.km_text(Decimal("123.5")), "123,5")
        self.assertEqual(lr.eingabe_text(Decimal("50.00"), 2), "50")
        self.assertEqual(lr.eingabe_text(Decimal("0.35"), 2), "0,35")
        self.assertEqual(lr.eingabe_text(Decimal("123.5"), 1), "123,5")
        self.assertEqual(lr.eingabe_text(None, 1), "")


class TestRechnung(unittest.TestCase):
    def test_standardwerte(self):
        zeilen = lr.abrechnungszeilen(_veranstaltung())
        self.assertEqual([z.name for z in zeilen], ["Anna Alt", "Bernd Braun"])
        self.assertEqual(zeilen[0].km_satz, Decimal("0.35"))
        self.assertEqual(zeilen[0].pauschale, Decimal("50"))
        self.assertEqual(zeilen[0].summe, Decimal("50.00"))  # ohne km nur die Pauschale

    def test_beispiel_marco(self):
        """120 km x 0,35 € = 42,00 € plus 50 € Pauschale = 92,00 €."""
        eingaben = lr.richter_eingaben_als_text({1: {"km": "120"}})
        z = lr.abrechnungszeilen(_veranstaltung(lr_abrechnung=eingaben))[0]
        self.assertEqual(z.fahrtkosten, Decimal("42.00"))
        self.assertEqual(z.summe, Decimal("92.00"))

    def test_rundung_kaufmaennisch(self):
        # 123,5 km x 0,35 = 43,225 -> 43,23
        z = lr.abrechnungszeile(1, "A", Decimal("123.5"), Decimal("0.35"), Decimal("50"))
        self.assertEqual(z.fahrtkosten, Decimal("43.23"))
        self.assertEqual(z.summe, Decimal("93.23"))

    def test_satz_und_pauschale_des_termins_und_je_richter(self):
        v = _veranstaltung(
            lr_km_satz="0,40", lr_tagespauschale="60",
            lr_abrechnung=lr.richter_eingaben_als_text(
                {1: {"km": "100", "km_satz": "0,5", "pauschale": "0"}, 2: {"km": "100"}}),
        )
        a, b = lr.abrechnungszeilen(v)
        self.assertEqual((a.fahrtkosten, a.pauschale, a.summe), (Decimal("50.00"), Decimal("0.00"), Decimal("50.00")))
        self.assertEqual((b.fahrtkosten, b.pauschale, b.summe), (Decimal("40.00"), Decimal("60.00"), Decimal("100.00")))
        self.assertEqual(lr.gesamtsumme([a, b]), Decimal("150.00"))

    def test_ungueltige_termin_saetze_fallen_auf_standard_zurueck(self):
        v = _veranstaltung(lr_km_satz="abc", lr_tagespauschale="-5")
        self.assertEqual(lr.km_satz_des_termins(v), Decimal("0.35"))
        self.assertEqual(lr.pauschale_des_termins(v), Decimal("50"))

    def test_nur_richter_mit_namen_und_position_bleibt(self):
        v = _veranstaltung(wertungsrichter_1="", wertungsrichter_2="  ", wertungsrichter_4="Dora Dietz",
                           lr_abrechnung=lr.richter_eingaben_als_text({4: {"km": "10"}, 1: {"km": "99"}}))
        zeilen = lr.abrechnungszeilen(v)
        self.assertEqual([(z.nummer, z.name, z.km) for z in zeilen], [(4, "Dora Dietz", Decimal("10.0"))])
        # Umbenennen ändert die Beträge nicht
        v["wertungsrichter_4"] = "Dora Neu"
        self.assertEqual(lr.abrechnungszeilen(v)[0].km, Decimal("10.0"))

    def test_keine_richter(self):
        self.assertEqual(lr.abrechnungszeilen(None), [])
        self.assertEqual(lr.abrechnungszeilen({"verein": "x", "datum": "2026-01-01"}), [])
        self.assertEqual(lr.gesamtsumme([]), Decimal("0.00"))

    def test_beschaedigte_eingaben_ergeben_leere_eingaben(self):
        for roh in ("{kaputt", "[1, 2]", "null", '"text"', '{"x": {"km": "1"}}', '{"9": {"km": "1"}}',
                    '{"1": "text"}', json.dumps({"1": {"km": ["liste"]}})):
            eingaben = lr.richter_eingaben_lesen({"lr_abrechnung": roh})
            zeilen = lr.abrechnungszeilen(_veranstaltung(lr_abrechnung=roh))
            self.assertEqual([z.km for z in zeilen], [Decimal("0.0")] * 2, roh)
            self.assertIsInstance(eingaben, dict)

    def test_eingaben_als_text_laesst_leere_weg(self):
        self.assertIsNone(lr.richter_eingaben_als_text({}))
        self.assertIsNone(lr.richter_eingaben_als_text({1: {"km": "", "km_satz": " ", "pauschale": ""}}))
        text = lr.richter_eingaben_als_text({1: {"km": "5"}, 7: {"km": "5"}})
        self.assertEqual(list(json.loads(text)), ["1"])


class TestBetragInWorten(unittest.TestCase):
    def test_beispiele(self):
        faelle = {
            "0.00": "null Euro",
            "1.00": "ein Euro",
            "50.00": "fünfzig Euro",
            "92.00": "zweiundneunzig Euro",
            "100.00": "einhundert Euro",
            "101.00": "einhunderteins Euro".replace("eins Euro", "ein Euro"),
            "121.50": "einhunderteinundzwanzig Euro und fünfzig Cent",
            "1000.00": "eintausend Euro",
            "1001.01": "eintausendein Euro und ein Cent",
            "2345.67": "zweitausenddreihundertfünfundvierzig Euro und siebenundsechzig Cent",
            "11.11": "elf Euro und elf Cent",
            "16.17": "sechzehn Euro und siebzehn Cent",
            "30.06": "dreißig Euro und sechs Cent",
            "110000.00": "einhundertzehntausend Euro",
            "999999.99": "neunhundertneunundneunzigtausendneunhundertneunundneunzig Euro und neunundneunzig Cent",
        }
        for betrag, erwartet in faelle.items():
            self.assertEqual(lr.betrag_in_worten(Decimal(betrag)), erwartet, betrag)

    def test_zahl_in_worten_grenzen(self):
        self.assertEqual(lr.zahl_in_worten(1), "eins")
        self.assertEqual(lr.zahl_in_worten(21), "einundzwanzig")
        with self.assertRaises(ValueError):
            lr.zahl_in_worten(1_000_000)
        with self.assertRaises(ValueError):
            lr.zahl_in_worten(-1)

    def test_groesster_moeglicher_betrag_passt(self):
        groesste_zeile = lr.abrechnungszeile(1, "A", lr.MAX_KM, lr.MAX_KM_SATZ, lr.MAX_PAUSCHALE)
        self.assertTrue(lr.betrag_in_worten(groesste_zeile.summe))


class TestSpeicherung(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.pfad = os.path.join(self.ordner.name, "t.sqlite")
        self.conn = db.init_db(self.pfad)

    def tearDown(self):
        self.conn.close()
        self.ordner.cleanup()

    def test_speichern_und_lesen(self):
        eingaben = lr.richter_eingaben_als_text({1: {"km": "120,5", "pauschale": "25"}})
        db.set_veranstaltung(self.conn, verein="HSV", datum="2026-11-14", wertungsrichter_1="Anna Alt",
                             lr_km_satz="0,4", lr_tagespauschale="55", lr_abrechnung=eingaben)
        v = db.get_veranstaltung(self.conn)
        self.assertEqual((v["lr_km_satz"], v["lr_tagespauschale"], v["lr_abrechnung"]), ("0,4", "55", eingaben))
        z = lr.abrechnungszeilen(v)[0]
        self.assertEqual(z.km, Decimal("120.5"))
        self.assertEqual(z.pauschale, Decimal("25.00"))

    def test_neue_veranstaltung_hat_leere_saetze(self):
        db.set_veranstaltung(self.conn, verein="HSV", datum="2026-11-14")
        v = db.get_veranstaltung(self.conn)
        self.assertIsNone(v["lr_km_satz"])
        self.assertEqual(lr.km_satz_des_termins(v), Decimal("0.35"))

    def test_migration_alter_termin_datei(self):
        """Eine Termin-Datei ohne die drei neuen Spalten bekommt sie beim Öffnen (Standardwerte)."""
        self.conn.close()
        alt = sqlite3.connect(self.pfad)
        alt.execute("DROP TABLE veranstaltung")
        alt.execute("CREATE TABLE veranstaltung (id INTEGER PRIMARY KEY CHECK (id = 1), verein TEXT NOT NULL, "
                    "ort TEXT, datum TEXT NOT NULL)")
        alt.execute("INSERT INTO veranstaltung (id, verein, datum) VALUES (1, 'Alt', '2025-01-01')")
        alt.commit()
        alt.close()
        self.conn = db.init_db(self.pfad)
        v = db.get_veranstaltung(self.conn)
        self.assertEqual(v["verein"], "Alt")
        for spalte in ("lr_km_satz", "lr_tagespauschale", "lr_abrechnung"):
            self.assertIn(spalte, v)
            self.assertIsNone(v[spalte])
        self.assertEqual(lr.abrechnungszeilen(v), [])

    def test_aktualisiere_veranstaltung_feld_behaelt_abrechnung(self):
        from desktop_gemeinsam import _aktualisiere_veranstaltung_feld  # noqa: PLC0415
        eingaben = lr.richter_eingaben_als_text({1: {"km": "10"}})
        db.set_veranstaltung(self.conn, verein="HSV", datum="2026-11-14", lr_abrechnung=eingaben)
        _aktualisiere_veranstaltung_feld(self.conn, zeitplan_start="08:00")
        self.assertEqual(db.get_veranstaltung(self.conn)["lr_abrechnung"], eingaben)

    def test_termin_info_enthaelt_saetze_aber_keine_eingaben(self):
        db.set_veranstaltung(self.conn, verein="HSV", datum="2026-11-14", lr_km_satz="0,4",
                             lr_tagespauschale="55", lr_abrechnung='{"1": {"km": "9"}}')
        self.conn.commit()
        info = db._termin_info_lesen(db.Path(self.pfad))
        self.assertEqual((info.lr_km_satz, info.lr_tagespauschale), ("0,4", "55"))


class TestCsv(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.conn = db.init_db(os.path.join(self.ordner.name, "t.sqlite"))

    def tearDown(self):
        self.conn.close()
        self.ordner.cleanup()

    def _lesen(self, pfad):
        import csv  # noqa: PLC0415
        with open(pfad, newline="", encoding="utf-8-sig") as datei:
            return list(csv.reader(datei, delimiter=";"))

    def test_zeile_je_richter(self):
        from db_import import ABRECHNUNG_CSV_SPALTEN, exportiere_abrechnung_csv  # noqa: PLC0415
        db.set_veranstaltung(
            self.conn, verein="SGV Muster", datum="2026-11-14", wertungsrichter_1="Anna Alt",
            wertungsrichter_2="=HYPERLINK(\"x\")",
            lr_abrechnung=lr.richter_eingaben_als_text({1: {"km": "1.234,5"}, 2: {"km": "120"}}))
        pfad = os.path.join(self.ordner.name, "a.csv")
        self.assertEqual(exportiere_abrechnung_csv(self.conn, pfad), 2)
        zeilen = self._lesen(pfad)
        self.assertEqual(zeilen[0], ABRECHNUNG_CSV_SPALTEN)
        self.assertEqual(zeilen[1], ["14.11.2026", "Anna Alt", "Leistungsrichter SGV Muster 14.11.2026",
                                     "1234,5", "0,35", "432,08", "50,00", "482,08", "Ausgabe"])
        self.assertEqual(zeilen[2][3:], ["120,0", "0,35", "42,00", "50,00", "92,00", "Ausgabe"])
        self.assertTrue(zeilen[2][1].startswith("'"), zeilen[2][1])  # Formel entschärft

    def test_ohne_richter_nur_kopfzeile(self):
        from db_import import exportiere_abrechnung_csv  # noqa: PLC0415
        db.set_veranstaltung(self.conn, verein="HSV", datum="2026-11-14")
        pfad = os.path.join(self.ordner.name, "a.csv")
        self.assertEqual(exportiere_abrechnung_csv(self.conn, pfad), 0)
        self.assertEqual(len(self._lesen(pfad)), 1)


class TestPdf(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.conn = db.init_db(os.path.join(self.ordner.name, "t.sqlite"))

    def tearDown(self):
        self.conn.close()
        self.ordner.cleanup()

    def _text(self, pfad):
        try:
            from pypdf import PdfReader  # noqa: PLC0415
        except ImportError:
            self.skipTest("pypdf fehlt")
        return "\n".join(seite.extract_text() for seite in PdfReader(pfad).pages), len(PdfReader(pfad).pages)

    def _termin(self):
        db.set_veranstaltung(
            self.conn, verein="HSV <Test> & Co", datum="2026-11-14", ort="Musterstadt",
            wertungsrichter_1="Anna Alt", wertungsrichter_2="Bernd <b>Braun</b>",
            lr_abrechnung=lr.richter_eingaben_als_text({1: {"km": "120"}, 2: {"km": "80,5"}}))

    def test_uebersicht_und_quittungen(self):
        import pdf_export  # noqa: PLC0415
        self._termin()
        pfad = os.path.join(self.ordner.name, "a.pdf")
        pdf_export.erstelle_abrechnung_pdf(self.conn, pfad)
        text, seiten = self._text(pfad)
        self.assertEqual(seiten, 1)
        for erwartet in ("Abrechnung Leistungsrichter", "Anna Alt", "92,00 €", "42,00 €",
                         "Bernd <b>Braun</b>", "78,18 €", "Gesamt", "170,18 €"):
            self.assertIn(erwartet, text)
        pfad = os.path.join(self.ordner.name, "q.pdf")
        pdf_export.erstelle_quittungen_pdf(self.conn, pfad)
        text, seiten = self._text(pfad)
        self.assertEqual(seiten, 2)  # eine Seite je Richter
        for erwartet in ("Quittung", "zweiundneunzig Euro", "achtundsiebzig Euro und achtzehn Cent",
                         "Musterstadt", "HSV <Test> & Co", "Unterschrift des Empfängers", "120,0 km"):
            self.assertIn(erwartet, text)

    def test_quittung_nur_eines_richters(self):
        import pdf_export  # noqa: PLC0415
        self._termin()
        pfad = os.path.join(self.ordner.name, "q2.pdf")
        pdf_export.erstelle_quittungen_pdf(self.conn, pfad, nummer=2)
        text, seiten = self._text(pfad)
        self.assertEqual(seiten, 1)
        self.assertIn("Bernd <b>Braun</b>", text)
        self.assertNotIn("Anna Alt", text)

    def test_ohne_richter(self):
        import pdf_export  # noqa: PLC0415
        db.set_veranstaltung(self.conn, verein="HSV", datum="2026-11-14")
        for funktion in (pdf_export.erstelle_abrechnung_pdf, pdf_export.erstelle_quittungen_pdf):
            pfad = os.path.join(self.ordner.name, funktion.__name__ + ".pdf")
            funktion(self.conn, pfad)
            text, _ = self._text(pfad)
            self.assertIn("Keine Leistungsrichter eingetragen", text)

    def test_ohne_veranstaltung(self):
        import pdf_export  # noqa: PLC0415
        pfad = os.path.join(self.ordner.name, "x.pdf")
        pdf_export.erstelle_abrechnung_pdf(self.conn, pfad)
        pdf_export.erstelle_quittungen_pdf(self.conn, pfad)
        self.assertTrue(os.path.exists(pfad))


if __name__ == "__main__":
    unittest.main()


class TestCheckliste(unittest.TestCase):
    def test_lesen_und_speichern(self):
        import checkliste  # noqa: PLC0415
        self.assertEqual(checkliste.erledigte(None), set())
        self.assertEqual(checkliste.erledigte({"checkliste": None}), set())
        text = checkliste.als_text({"sicherung", "zeitplan", "unbekannt"})
        self.assertEqual(json.loads(text), ["zeitplan", "sicherung"])  # Reihenfolge der Checkliste
        self.assertEqual(checkliste.erledigte({"checkliste": text}), {"zeitplan", "sicherung"})
        self.assertIsNone(checkliste.als_text(set()))

    def test_beschaedigte_eintraege_ergeben_nichts(self):
        import checkliste  # noqa: PLC0415
        for roh in ("{kaputt", "{}", "null", '"zeitplan"', json.dumps([1, ["x"], None])):
            self.assertEqual(checkliste.erledigte({"checkliste": roh}), set(), roh)
        self.assertEqual(checkliste.erledigte({"checkliste": '["zeitplan", "gibt-es-nicht", 5]'}), {"zeitplan"})

    def test_kennungen_eindeutig(self):
        import checkliste  # noqa: PLC0415
        self.assertEqual(len(checkliste.ALLE_KENNUNGEN), len(set(checkliste.ALLE_KENNUNGEN)))

    def test_speicherung_und_migration(self):
        import checkliste  # noqa: PLC0415
        with tempfile.TemporaryDirectory() as ordner:
            pfad = os.path.join(ordner, "t.sqlite")
            conn = db.init_db(pfad)
            db.set_veranstaltung(conn, verein="HSV", datum="2026-11-14", checkliste=checkliste.als_text({"listen"}))
            self.assertEqual(checkliste.erledigte(db.get_veranstaltung(conn)), {"listen"})
            conn.execute("ALTER TABLE veranstaltung DROP COLUMN checkliste")
            conn.commit()
            conn.close()
            conn = db.init_db(pfad)  # alte Datei ohne die Spalte: wird ergänzt
            self.assertIsNone(db.get_veranstaltung(conn)["checkliste"])
            conn.close()


class TestChecklisteEigene(unittest.TestCase):
    def test_hinzufuegen_und_struktur(self):
        import checkliste  # noqa: PLC0415
        e = checkliste.eigene_lesen(None)
        e = checkliste.kategorie_hinzufuegen(e, "  Verein   intern ")
        e = checkliste.punkt_hinzufuegen(e, "e1", "Pokale")
        e = checkliste.punkt_hinzufuegen(e, "tag", "Tee kochen")
        v = {"checkliste_eigene": checkliste.eigene_als_text(e)}
        kategorien = checkliste.struktur(v)
        self.assertEqual([k.titel for k in kategorien][-1], "Verein intern")
        tag = next(k for k in kategorien if k.schluessel == "tag")
        self.assertEqual([(p.text, p.eigen) for p in tag.punkte][-1], ("Tee kochen", True))
        self.assertEqual([p.kennung for p in tag.punkte][:2], ["ergebnisse", "speichern"])  # feste zuerst
        self.assertEqual(kategorien[-1].punkte[0].kennung, "e2")

    def test_neue_kennung_ist_hoechste_vorhandene_plus_eins(self):
        import checkliste  # noqa: PLC0415
        e = checkliste.kategorie_hinzufuegen(checkliste.eigene_lesen(None), "A")
        e = checkliste.punkt_hinzufuegen(e, "e1", "x")
        e = checkliste.punkt_hinzufuegen(e, "e1", "y")
        self.assertEqual([p["id"] for p in e["punkte"]], ["e2", "e3"])
        e = checkliste.punkt_loeschen(e, "e2")
        e = checkliste.punkt_hinzufuegen(e, "e1", "z")
        self.assertEqual([p["id"] for p in e["punkte"]], ["e3", "e4"])  # keine Wiederverwendung hinter der höchsten

    def test_fehler_und_grenzen(self):
        import checkliste  # noqa: PLC0415
        e = checkliste.eigene_lesen(None)
        with self.assertRaises(ValueError):
            checkliste.kategorie_hinzufuegen(e, "   ")
        with self.assertRaises(ValueError):
            checkliste.punkt_hinzufuegen(e, "gibt-es-nicht", "x")
        with self.assertRaises(ValueError):
            checkliste.punkt_hinzufuegen(e, "tag", " ")
        for _ in range(checkliste.MAX_KATEGORIEN):
            e = checkliste.kategorie_hinzufuegen(e, "K")
        with self.assertRaises(ValueError):
            checkliste.kategorie_hinzufuegen(e, "zu viel")
        lang = checkliste.punkt_hinzufuegen(checkliste.eigene_lesen(None), "tag", "x" * 500)
        self.assertEqual(len(lang["punkte"][0]["text"]), checkliste.MAX_TEXT)

    def test_beschaedigte_eigene_daten(self):
        import checkliste  # noqa: PLC0415
        leer = {"kategorien": [], "punkte": [], "ausgeblendet": []}
        for roh in ("{kaputt", "[]", "null", '{"kategorien": "x", "punkte": 5}',
                    '{"punkte": [{"id": "e1", "kategorie": [1], "text": "x"}]}',
                    '{"punkte": [{"id": "e1", "kategorie": {"a": 1}, "text": "x"}]}',
                    '{"kategorien": [1, {"id": 5, "name": "x"}, {"id": "zeitplan", "name": "x"}]}'):
            self.assertEqual(checkliste.eigene_lesen({"checkliste_eigene": roh}), leer, roh)
        roh = ('{"kategorien": [{"id": "e1", "name": "A"}], "punkte": ['
               '{"id": "e2", "kategorie": "e1", "text": "ok"},'
               '{"id": "e3", "kategorie": "e9", "text": "ohne Kategorie"},'
               '{"id": "e1", "kategorie": "tag", "text": "doppelte Kennung"},'
               '{"id": "e4", "kategorie": "tag", "text": ""}]}')
        e = checkliste.eigene_lesen({"checkliste_eigene": roh})
        self.assertEqual([p["id"] for p in e["punkte"]], ["e2"])

    def test_erledigte_ignoriert_geloeschte_eigene(self):
        import checkliste  # noqa: PLC0415
        e = checkliste.punkt_hinzufuegen(checkliste.eigene_lesen(None), "tag", "x")
        v = {"checkliste_eigene": checkliste.eigene_als_text(e), "checkliste": '["e1", "e7", "zeitplan"]'}
        self.assertEqual(checkliste.erledigte(v), {"e1", "zeitplan"})

    def test_speicherung_und_migration(self):
        import checkliste  # noqa: PLC0415
        e = checkliste.punkt_hinzufuegen(checkliste.eigene_lesen(None), "tag", "x")
        with tempfile.TemporaryDirectory() as ordner:
            pfad = os.path.join(ordner, "t.sqlite")
            conn = db.init_db(pfad)
            db.set_veranstaltung(conn, verein="HSV", datum="2026-11-14",
                                 checkliste_eigene=checkliste.eigene_als_text(e))
            self.assertEqual(checkliste.eigene_lesen(db.get_veranstaltung(conn)), e)
            conn.execute("ALTER TABLE veranstaltung DROP COLUMN checkliste_eigene")
            conn.commit()
            conn.close()
            conn = db.init_db(pfad)
            self.assertIsNone(db.get_veranstaltung(conn)["checkliste_eigene"])
            conn.close()


class TestChecklisteAusblenden(unittest.TestCase):
    def test_ausblenden_und_struktur(self):
        import checkliste  # noqa: PLC0415
        e = checkliste.eigene_lesen(None)
        e = checkliste.ausblenden(e, "zeitplan")
        e = checkliste.ausblenden(e, "tag")  # ganze feste Kategorie
        e = checkliste.ausblenden(e, "zeitplan")  # doppelt: keine zweite Eintragung
        self.assertEqual(e["ausgeblendet"], ["zeitplan", "tag"])
        v = {"checkliste_eigene": checkliste.eigene_als_text(e)}
        kategorien = checkliste.struktur(v)
        self.assertNotIn("tag", [k.schluessel for k in kategorien])
        tage8 = next(k for k in kategorien if k.schluessel == "tage8")
        self.assertEqual([p.kennung for p in tage8.punkte], ["richter_kontakt", "zeitplan_aenderung"])
        self.assertNotIn("ergebnisse", checkliste.alle_kennungen(kategorien))
        self.assertEqual(checkliste.anzahl_ausgeblendet(e), 2)

    def test_ausgeblendete_haken_zaehlen_nicht(self):
        import checkliste  # noqa: PLC0415
        e = checkliste.ausblenden(checkliste.eigene_lesen(None), "zeitplan")
        v = {"checkliste_eigene": checkliste.eigene_als_text(e), "checkliste": '["zeitplan", "zahlungen"]'}
        self.assertEqual(checkliste.erledigte(v), {"zahlungen"})

    def test_alle_einblenden_behaelt_eigenes(self):
        import checkliste  # noqa: PLC0415
        e = checkliste.kategorie_hinzufuegen(checkliste.eigene_lesen(None), "Verein")
        e = checkliste.ausblenden(e, "kurz")
        e = checkliste.punkt_hinzufuegen(e, "e1", "Pokale")
        e = checkliste.alle_einblenden(e)
        self.assertEqual(e["ausgeblendet"], [])
        self.assertEqual([k["name"] for k in e["kategorien"]], ["Verein"])
        self.assertEqual(len(e["punkte"]), 1)

    def test_eigenes_wird_nicht_ausgeblendet_und_ausgeblendete_kategorie_nimmt_keine_punkte(self):
        import checkliste  # noqa: PLC0415
        e = checkliste.punkt_hinzufuegen(checkliste.kategorie_hinzufuegen(checkliste.eigene_lesen(None), "V"), "e1", "x")
        with self.assertRaises(ValueError):
            checkliste.ausblenden(e, "e1")  # eigene Kategorie: löschen statt ausblenden
        with self.assertRaises(ValueError):
            checkliste.ausblenden(e, "e2")
        with self.assertRaises(ValueError):
            checkliste.ausblenden(e, "gibt-es-nicht")
        e = checkliste.ausblenden(e, "tag")
        with self.assertRaises(ValueError):
            checkliste.punkt_hinzufuegen(e, "tag", "neuer Punkt")

    def test_andere_operationen_behalten_ausgeblendetes(self):
        import checkliste  # noqa: PLC0415
        e = checkliste.ausblenden(checkliste.eigene_lesen(None), "tag")
        e = checkliste.kategorie_hinzufuegen(e, "V")
        e = checkliste.punkt_hinzufuegen(e, "e1", "x")
        e = checkliste.punkt_loeschen(e, "e2")
        e = checkliste.kategorie_loeschen(e, "e1")
        self.assertEqual(e["ausgeblendet"], ["tag"])
        self.assertIsNotNone(checkliste.eigene_als_text(e))  # nur Ausgeblendetes wird gespeichert

    def test_beschaedigte_ausblendungen(self):
        import checkliste  # noqa: PLC0415
        roh = '{"ausgeblendet": ["tag", "tag", "gibt-es-nicht", 5, ["x"], "e1", "zeitplan"]}'
        self.assertEqual(checkliste.eigene_lesen({"checkliste_eigene": roh})["ausgeblendet"], ["tag", "zeitplan"])
        for roh in ('{"ausgeblendet": "tag"}', '{"ausgeblendet": null}', '{"ausgeblendet": {"tag": 1}}'):
            self.assertEqual(checkliste.eigene_lesen({"checkliste_eigene": roh})["ausgeblendet"], [], roh)
