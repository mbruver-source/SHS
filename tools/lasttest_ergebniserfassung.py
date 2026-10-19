"""Lasttest der Ergebniserfassung (offene Punkte O10, 19.10.2026).

    python tools/lasttest_ergebniserfassung.py                 # 1000 Teilnehmer, 3 Läufe
    python tools/lasttest_ergebniserfassung.py --teilnehmer 200 --laeufe 5
    python tools/lasttest_ergebniserfassung.py --repo C:\\temp\\alter_stand   # anderen Stand messen

Legt in einem temporären Ordner einen Termin mit gemischten Prüfungen an (alle 12 Angebote:
ED 1–3 je Disziplin, DK 1–3; rund die Hälfte mit Ergebnissen, ein paar Disqualifizierte) und
misst offscreen mit dem echten Hauptfenster (Median aus mehreren Läufen):
- Termin öffnen (Hauptfenster aufbauen),
- erster Wechsel in die Ergebniserfassung, Reiterwechsel ohne und mit Neuaufbau,
- Sortieren per Spaltenklick,
- 50 Ergebnisse eintragen und „Alle speichern“,
- Ansichtswechsel (Hintergrund-Design, ohne die Auswahl zu speichern),
- zusätzlichen Arbeitsspeicher (RSS, falls psutil installiert ist).

Mit --repo lässt sich ein anderer Programmstand messen (z. B. ein per `git worktree add`
ausgecheckter älterer Commit). Ziele aus Marcos Entscheidung vom 18.10.2026: Ansichtswechsel
unter 0,3 s, Reiterwechsel mit Neuaufbau und Sortieren unter 0,5 s.
Nur ein Entwickler-Werkzeug - gehört nicht zum Programm und wird nicht mit ausgeliefert.
"""
from __future__ import annotations

import argparse
import os
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _argumente(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--teilnehmer", type=int, default=1000)
    parser.add_argument("--laeufe", type=int, default=3)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, float]:
    args = _argumente(argv)
    sys.path.insert(0, str(args.repo.resolve()))
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    qapp = QApplication.instance() or QApplication([])
    import app
    import db
    import desktop_darstellung

    try:
        import psutil
        prozess = psutil.Process()
    except ImportError:
        prozess = None

    def warten():
        # deleteLater läuft nur in der Ereignisschleife - ohne das sammeln sich alte Widgets.
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        qapp.processEvents()

    def zeit(fn) -> float:
        start = time.perf_counter()
        fn()
        warten()
        return time.perf_counter() - start

    # Design-Auswahl nicht in die Einstellungen des Rechners schreiben bzw. von dort lesen.
    design = {"name": "hell"}
    desktop_darstellung._gespeichertes_design_lesen = lambda: design["name"]
    desktop_darstellung._gespeichertes_theme_lesen = lambda: desktop_darstellung._THEME_DEFAULT
    if hasattr(app, "_gespeichertes_design_lesen"):
        app._gespeichertes_design_lesen = desktop_darstellung._gespeichertes_design_lesen

    angebote = [("ED", stufe, d) for d in db.ALLE_DISZIPLINEN for stufe in (1, 2, 3)]
    angebote += [("DK", stufe, None) for stufe in (1, 2, 3)]
    ordner = Path(tempfile.mkdtemp(prefix="shs_lasttest_"))
    pfad = str(ordner / f"Lasttest-{args.teilnehmer}.sqlite")
    conn = db.init_db(pfad)
    db.set_veranstaltung(conn, verein="Lasttest", datum="2026-11-14")
    erster = None  # (Teilnehmer-ID, Disziplin) für die Änderung „von außen“
    for i in range(args.teilnehmer):
        art, stufe, disziplin = angebote[i % len(angebote)]
        tid = db.add_teilnehmer(conn, db.NeuerTeilnehmer(
            nachname=f"Muster{i:04d}", vorname="Max", rufname_hund=f"Hund{i}", art=art, stufe=stufe,
            disziplin=disziplin, startnummer=i + 1))
        erster = erster or (tid, disziplin or db.ALLE_DISZIPLINEN[0])
        if i % 2 == 0:
            for d in ([disziplin] if disziplin else db.ALLE_DISZIPLINEN):
                db.eintragen_ergebnis(conn, tid, d, 40 + i % 20, 20 + i % 20)
        elif i % 97 == 0:
            db.setze_ergebnis_status(conn, tid, True, False)
    speicher_vorher = prozess.memory_info().rss if prozess else None

    werte: dict[str, list[float]] = {}

    def merken(name, sekunden):
        werte.setdefault(name, []).append(sekunden)

    for lauf in range(args.laeufe):
        fenster_halter = {}
        merken("Termin öffnen (Hauptfenster)", zeit(lambda: fenster_halter.setdefault("f", app.HauptFenster(conn, pfad))))
        fenster = fenster_halter["f"]
        fenster.resize(1600, 900)
        fenster.show()
        warten()
        tab = fenster.ergebnis_tab
        merken("Erster Wechsel in die Ergebniserfassung", zeit(lambda: fenster._tabs.setCurrentWidget(tab)))
        merken("Reiterwechsel ohne Änderung", zeit(lambda: (fenster._tabs.setCurrentWidget(fenster.teilnehmer_tab),
                                                             fenster._tabs.setCurrentWidget(tab))))
        fenster._tabs.setCurrentWidget(fenster.teilnehmer_tab)
        db.eintragen_ergebnis(conn, erster[0], erster[1], 41 + lauf, 21)  # Änderung -> Neuaufbau
        merken("Reiterwechsel mit Neuaufbau", zeit(lambda: fenster._tabs.setCurrentWidget(tab)))
        merken("Sortieren (Spaltenklick Name)", zeit(lambda: tab._spalte_geklickt(1)))

        def eintragen_und_speichern():
            for zeile in range(0, min(100, tab.zeilenanzahl()), 2):
                disziplin = tab.erfassbare_disziplinen(zeile)[0]
                if not tab.zelle_gesperrt(zeile, disziplin):
                    tab.punkte_eintragen(zeile, disziplin, 30 + lauf, 15)
            tab.alle_speichern()

        merken("50 Ergebnisse eintragen + Alle speichern", zeit(eintragen_und_speichern))

        def ansicht_wechseln():
            design["name"] = "dunkel" if design["name"] == "hell" else "hell"
            fenster._darstellung_neu_anwenden()

        merken("Ansichtswechsel (Hintergrund)", zeit(ansicht_wechseln))
        if prozess and lauf == 0:
            werte["Zusätzlicher Arbeitsspeicher (MB)"] = [(prozess.memory_info().rss - speicher_vorher) / 1e6]
        fenster.close()
        fenster.deleteLater()
        warten()

    conn.close()
    shutil.rmtree(ordner, ignore_errors=True)
    ergebnis = {name: statistics.median(liste) for name, liste in werte.items()}
    print(f"Lasttest Ergebniserfassung, {args.teilnehmer} Teilnehmer, {args.laeufe} Läufe ({args.repo})")
    for name, wert in ergebnis.items():
        print(f"  {name:45s} {wert:8.2f}")
    return ergebnis


if __name__ == "__main__":
    main()
