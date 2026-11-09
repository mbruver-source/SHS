---
name: feature-done
description: Abschluss einer für Nutzer sichtbaren Funktion im SHS-Prüfungsprogramm - Tests, Demo-Daten, Handbuch, README, Screenshots und Website zum Stand der Änderung nachziehen. Kein Commit und kein Build; offene Punkte werden Marco vorgelegt.
---

# Funktion abschließen

Die Regeln stehen in `CLAUDE.md` (Fertig-Definition für Funktionen, Build-/Versionsdisziplin).
Python lokal: `C:\Users\mbruv\anaconda3\python.exe` (im Folgenden `PY`). Dateien mit
Edit/Write ändern, nicht mit Skript-Ersetzungen.

1. **Tests:** `PY "C:\Users\mbruv\Documents\Claude\SHS Test Suite\run_tests.py" --kompakt`
   (ohne `--installation`). Fehler beheben, bis der Lauf grün ist. Neue Tests
   plattformunabhängig (`pathlib`/`os.path`, die CI läuft auch unter Linux).
2. **Demo-Daten:** `demo_daten.py` und `desktop_demo.py` um die neue Funktion ergänzen, wenn
   sie in der Demoprüfung vorkommen sollte. Nur erfundene Daten, nie echte Namen,
   E-Mail-Adressen oder Chipnummern.
3. **Handbuch und README:** `docs/HANDBUCH.md` und `README*.md` zur neuen Funktion nachziehen.
   Das Handbuch-PDF wird erst beim Build erzeugt (`shs-build`, Schritt 3), hier nicht.
4. **Screenshots:** betroffene Bilder mit `PY tools/screenshots.py --nur name1,name2` neu
   aufnehmen und ansehen (`git status docs/bilder`). Neue Oberflächen im Skript ergänzen.
   Nach dem Versionsbump beim Build noch einmal aufnehmen, damit sie die neue Version zeigen.
5. **Website (`docs/`):** Seiten zu diesem Bereich im Arbeitsstand anpassen, aber nicht
   separat pushen: Änderungen zu neuen Funktionen gehen erst mit dem Release online.
6. **`Fortschritt.md`:** Eintrag zur Funktion mit den geänderten Dateien.
7. **Abschluss:** Kein Commit, kein Versionsbump, kein Build, kein Tag (Ausnahmen laut
   `CLAUDE.md`: reine Dokumentationsänderungen, Ablauf `aufgaben-abarbeitung`). Offene
   Punkte als nummerierte Liste mit Empfehlung (umsetzen / zurückstellen / verwerfen)
   Marco vorlegen und auf seine Entscheidung warten.
