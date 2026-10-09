---
name: shs-build
description: Checkliste für einen neuen Build des SHS-Prüfungsprogramms. Nur verwenden, wenn Marco ausdrücklich einen Build anfordert ("jetzt neuen Build erzeugen" o. ä.), nie von sich aus.
---

# Build des SHS-Prüfungsprogramms

Die Regeln dazu stehen in `CLAUDE.md` (Abschnitt Build-/Versionsdisziplin). Diese Checkliste
setzt sie Schritt für Schritt um. Python lokal: `C:\Users\mbruv\anaconda3\python.exe`
(im Folgenden `PY`).

Lege für die Schritte eine Aufgabenliste an und hake sie einzeln ab.

## 1. Offene Punkte klären (vor allem anderen)

- In `Fortschritt.md` alle Abschnitte seit dem letzten Build lesen: Was ist gesammelt, was
  ist als offen markiert?
- Verifikation über alles seit dem letzten Build (Agenten-Typ `verifikation`).
- Jede Auffälligkeit, auch Kleinigkeiten wie veraltete Kommentare oder Test-Robustheit,
  Marco vorlegen: umsetzen, bewusst zurückstellen oder verwerfen. **Erst nach seiner
  Entscheidung weiter.** Nicht bauen, solange ein Punkt ungeklärt ist.
- Offene Sicherheitsfunde: Commit-Nachrichten, Kommentare, `Fortschritt.md` und
  `RELEASE_NOTES.md` nur allgemein formulieren. Berichte bleiben in `_unveroeffentlicht/`.

## 2. Dokumente und Screenshots nachziehen (vor dem Versionsbump)

- `docs/HANDBUCH.md`: neue oder geänderte Funktionen und Bedienung.
- `docs/bilder/`: Desktop-Screenshots mit `PY tools/screenshots.py` neu erzeugen (alle 15
  Bilder, feste Testdaten; einzelne mit `--nur name1,name2`, Namen siehe `BILDER` im Skript).
  Danach jedes geänderte Bild ansehen (`git status docs/bilder`). Neue Oberflächen im Skript
  ergänzen statt Ad-hoc-Code zu schreiben. Von Hand bleiben: Web-Bilder,
  `handbuch_anmeldeformular`, `bewertungsbogen`, `handbuch_edge_download`. Geht ein Bild
  nicht, Marco fragen, statt ohne zu bauen. Bei Änderungen an `handbuch_zeitplan.png` die
  `og:image`-Angaben der Website prüfen.
- `Architektur.md`, `README*.md`.
- `RELEASE_NOTES.md`: Abschnitt „Was ist neu in X.Y.Z“ für die kommende Version, in
  verständlicher Sprache für Vereinsmitglieder.

## 3. Version und Handbuch-PDF

1. `PY bump_version.py` (zieht `version.txt`, `version_info.txt`, `version.py`,
   „Stand: Version …“ im Handbuch und den Image-Tag in `compose.yaml` nach).
2. `PY tools/screenshots.py` noch einmal, damit die Bilder die neue Versionsnummer zeigen.
3. `PY tools/handbuch_pdf.py` erzeugt `docs/HANDBUCH.pdf` neu.

## 4. Tests

```
PY -m unittest test_db test_db_postgres_wrapper test_backup test_pdf_export test_app_web test_bump_version test_shs_core test_bewertung_referenz test_altversionen
```

Schlägt etwas fehl: nicht committen, Marco das Ergebnis zeigen.

## 5. Build-Commit

- `Fortschritt.md`: Abschnitt „Version X.Y.Z“ mit den gebündelten Änderungen.
- Commit mit Attribution-Footer aus dem System-Reminder.

## 6. Altdaten der neuen Version (eigener Commit)

1. `PY tools/altdaten_erzeugen.py --aktuell`
2. `PY -m unittest test_altversionen`
3. Neue Dateien unter `testdaten/altversionen/` als eigenen Commit (Marcos Entscheidung T3).

## 7. Abschluss

- **Nicht pushen und nicht taggen.** Marco die Befehle nennen:
  ```
  git push
  git tag vX.Y.Z
  git push --tags
  ```
- Hinweis an Marco: Nach dem Tag-Lauf unter „Actions“ prüfen, ob alle Jobs grün sind, auch
  `build-macos` (2x) und `build-linux`. Ein Fehler dort hält das Release nicht auf, dann
  fehlen nur die betroffenen Dateien (.dmg, AppImage, .deb) im Release.
- Hinweis an Marco: Quellcode-Spiegel `SHS-Pruefungsprogramm-Quellcode` und, falls
  geändert, `Fortschritt.md`/`Architektur.md`/`Grobkonzept.md` in der claude.ai-Ablage
  „SHS“ nachziehen.
