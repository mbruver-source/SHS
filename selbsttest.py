"""Selbsttest der fertigen Anwendung: `SHS-Pruefungsprogramm.exe --selbsttest [protokoll]`
(T1, mit Marco abgestimmt am 03.10.2026).

Prüft ohne sichtbares Fenster (Qt "offscreen") in einem temporären Ordner, ob alle
gebündelten Teile der ausgelieferten EXE funktionieren - genau das, was die Python-Tests
nicht abdecken können: fehlt in build.spec ein Modul, eine Schrift oder ein Qt-Plugin, sind
die Tests grün, die EXE scheitert aber erst beim Nutzer.

Die CI (build-installer.yml) startet damit die frisch gebaute EXE und zusätzlich die per
Installer still installierte EXE. Der Schalter bleibt auch in der ausgelieferten Version und
hilft bei der Fehlersuche beim Nutzer. Er berührt keine echten Termine: alles passiert in
einem Temp-Ordner, der danach gelöscht wird.

Ergebnis: Exit-Code 0 (alles OK) bzw. 1, dazu eine Protokolldatei (die EXE hat keine
Konsole) - Standard: %TEMP%\\shs_selbsttest.log.
"""
from __future__ import annotations

import faulthandler
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path


def fuehre_selbsttest_aus(protokoll_pfad: str | None = None) -> int:
    protokoll = Path(protokoll_pfad or Path(tempfile.gettempdir()) / "shs_selbsttest.log")
    zeilen: list[str] = []
    fehler = 0

    def schritt(name, funktion):
        nonlocal fehler
        try:
            ergebnis = funktion()
            zeilen.append(f"OK      {name}" + (f" ({ergebnis})" if ergebnis else ""))
        except Exception:  # noqa: BLE001 - jeder Fehler soll im Protokoll landen
            fehler += 1
            zeilen.append(f"FEHLER  {name}\n" + traceback.format_exc())

    ordner = Path(tempfile.mkdtemp(prefix="shs_selbsttest_"))
    # Harter Absturz (z. B. Qt fatal): faulthandler schreibt dann wenigstens den Stapel ins
    # Protokoll; die CI scheitert ohnehin am Exit-Code ungleich 0.
    absturz_datei = None
    faulthandler_vorher = faulthandler.is_enabled()
    try:
        protokoll.parent.mkdir(parents=True, exist_ok=True)
        absturz_datei = open(protokoll, "w", encoding="utf-8")
        absturz_datei.write("Selbsttest läuft - steht nur das hier, ist das Programm abgestürzt.\n")
        absturz_datei.flush()
        faulthandler.enable(file=absturz_datei)
    except OSError:
        absturz_datei = None
    try:
        from version import VERSION

        zeilen.append(f"SHS-Prüfungsprogramm {VERSION} - Selbsttest in {ordner}")
        _ablauf(schritt, ordner)
    except Exception:  # noqa: BLE001 - z. B. ein fehlendes Modul schon beim Import
        fehler += 1
        zeilen.append("FEHLER  Start\n" + traceback.format_exc())
    finally:
        if absturz_datei is not None:
            faulthandler.disable()
            absturz_datei.close()
            if faulthandler_vorher and sys.stderr is not None:  # z. B. unter pytest
                faulthandler.enable()
        shutil.rmtree(ordner, ignore_errors=True)

    zeilen.append("ERGEBNIS: " + ("alles OK" if fehler == 0 else f"{fehler} Fehler"))
    text = "\n".join(zeilen) + "\n"
    try:
        protokoll.write_text(text, encoding="utf-8")
    except OSError:
        pass
    if sys.stdout is not None:  # die EXE (console=False) hat keine Konsole
        try:
            sys.stdout.write(text)
        except Exception:  # noqa: BLE001
            pass
    return 0 if fehler == 0 else 1


def _offscreen_verfuegbar() -> bool:
    """Ist das Qt-Plugin "offscreen" vorhanden (in der EXE hängt das vom PyInstaller-Hook
    ab)? Sonst bleibt es bei der normalen Windows-Plattform - ein kurz sichtbares Fenster
    ist besser als ein Abbruch, weil Qt die erzwungene Plattform nicht findet."""
    try:
        from PySide6.QtCore import QLibraryInfo

        ordner = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)) / "platforms"
        return any(ordner.glob("*offscreen*"))
    except Exception:  # noqa: BLE001
        return False


def _ablauf(schritt, ordner: Path) -> None:
    if "QT_QPA_PLATFORM" not in os.environ and _offscreen_verfuegbar():
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    import db
    import db_import
    import db_sicherung
    import pdf_export

    pfad = ordner / "2026-11-14_Selbsttest.sqlite"
    conn = db.init_db(str(pfad))
    try:
        _schritte(schritt, ordner, pfad, conn, db, db_import, db_sicherung, pdf_export)
    finally:
        conn.close()  # sonst lässt sich der Temp-Ordner unter Windows nicht löschen


def _schritte(schritt, ordner, pfad, conn, db, db_import, db_sicherung, pdf_export) -> None:
    zustand: dict = {}

    def termin_anlegen():
        db.set_veranstaltung(
            conn, verein="Selbsttest-Verein", datum="2026-11-14", ort="Teststadt",
            verband="TEST", meldestelle="Test\nTestweg 1",
            angebotene_pruefungen=db.pruefungen_als_text([p.kuerzel for p in db.ALLE_PRUEFUNGEN]),
        )
        ed = db.add_teilnehmer(conn, db.NeuerTeilnehmer(
            nachname="Test", vorname="Erika", rufname_hund="Bello", art="ED", stufe=1,
            disziplin="Trümmerfeld", startnummer=1, gegenstand_1="Leder"))
        dk = db.add_teilnehmer(conn, db.NeuerTeilnehmer(
            nachname="Probe", vorname="Max", rufname_hund="Luna", art="DK", stufe=1, startnummer=2))
        db.eintragen_ergebnis(conn, ed, "Trümmerfeld", 58, 38)
        for disziplin in ("Trümmerfeld", "Flächensuche", "Behältnisstrecke"):
            db.eintragen_ergebnis(conn, dk, disziplin, 55, 35)
        richter = [db.add_zeitplan_richter(conn, "Richter A"), db.add_zeitplan_richter(conn, "Richter B")]
        db.automatische_zeitplan_verteilung(conn, richter, 10)
        fertig, _ = db.berechne_auswertung(conn)
        noten = sorted(t.wertnote.abkuerzung for t in fertig)
        if noten != ["SG", "V"]:
            raise AssertionError(f"unerwartete Wertnoten {noten}")
        zustand["ed"] = ed
        return "2 Teilnehmer, Auswertung V/SG"

    schritt("Termin, Teilnehmer, Ergebnisse, Zeitplan", termin_anlegen)

    def pdfs():
        ausgaben = {
            "Ergebnisliste": lambda p: pdf_export.erstelle_ergebnisliste_pdf(conn, p),
            "Etiketten": lambda p: pdf_export.erstelle_ergebnisliste_etiketten_pdf(conn, p),
            "Bewertungsbogen": lambda p: pdf_export.erstelle_bewertungsbogen_pdf(conn, zustand["ed"], p),
            "Statistik": lambda p: pdf_export.erstelle_statistik_pdf(conn, p),
            "Zeitplan": lambda p: pdf_export.erstelle_zeitplan_pdf(conn, p),
            "Anmeldeformular": lambda p: pdf_export.erstelle_anmeldeformular_pdf(conn, p),
        }
        for name, erzeugen in ausgaben.items():
            ziel = ordner / f"{name}.pdf"
            erzeugen(str(ziel))
            if ziel.stat().st_size < 500:
                raise AssertionError(f"{name}.pdf ist leer")
        return f"{len(ausgaben)} PDFs"

    schritt("PDF-Ausgaben (reportlab)", pdfs)

    def anmeldeformular_einlesen():
        # Leeres Formular: muss sauber als "keine Prüfung angekreuzt" abgelehnt werden -
        # beweist, dass pypdf in der EXE funktioniert.
        ergebnis = db_import.importiere_anmeldeformular_pdf(conn, [str(ordner / "Anmeldeformular.pdf")])
        if ergebnis.importiert != 0 or len(ergebnis.fehler) != 1:
            raise AssertionError(f"unerwartetes Ergebnis {ergebnis}")
        return "pypdf"

    schritt("Anmeldeformular einlesen (pypdf)", anmeldeformular_einlesen)

    def csv_hin_und_zurueck():
        ziel = ordner / "liste.csv"
        db_import.exportiere_teilnehmer_csv(conn, str(ziel))
        ergebnis = db_import.importiere_teilnehmer_aus_csv(conn, str(ziel))
        if ergebnis.importiert != 0 or len(ergebnis.uebersprungen) != 2:
            raise AssertionError(f"unerwartetes Ergebnis {ergebnis}")
        return "Export + Doppel-Erkennung"

    schritt("Teilnehmerliste CSV", csv_hin_und_zurueck)

    def sicherung():
        termine = ordner / "termine"
        termine.mkdir()
        shutil.copy(pfad, termine / pfad.name)
        zip_pfad = ordner / "sicherung.zip"
        db_sicherung.sicherung_erstellen(str(zip_pfad), passwort="Selbsttest-1", ordner=termine)
        ziel = ordner / "wiederhergestellt"
        ziel.mkdir()
        db_sicherung.sicherung_wiederherstellen(
            str(zip_pfad), {pfad.name: pfad.name}, passwort="Selbsttest-1", ordner=ziel
        )
        kopie = db.init_db(str(ziel / pfad.name))
        try:
            if len(db.list_teilnehmer(kopie)) != 2:
                raise AssertionError("Sicherung unvollständig")
        finally:
            kopie.close()
        return "mit Passwort (pyzipper)"

    conn.commit()
    schritt("Datensicherung erstellen und wiederherstellen", sicherung)

    def oberflaeche():
        from PySide6.QtWidgets import QApplication

        import app

        qapp = QApplication.instance() or QApplication(sys.argv[:1])
        app.deutsche_qt_texte_laden(qapp)
        app._darstellung_anwenden(qapp)
        fenster = app.HauptFenster(conn, str(pfad))
        try:
            fenster.show()
            for index in range(fenster._tabs.count()):
                fenster._tabs.setCurrentIndex(index)
                qapp.processEvents()
            reiter = fenster._tabs.count()
        finally:
            fenster.hide()
            fenster.deleteLater()
            qapp.processEvents()
        return f"{reiter} Reiter, Plattform {qapp.platformName()}"

    schritt("Oberfläche mit allen Reitern (PySide6)", oberflaeche)
