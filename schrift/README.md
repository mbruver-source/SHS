# Schrift der Oberfläche

Die TTF-Dateien in diesem Ordner sind unveränderte Schnitte von **Atkinson Hyperlegible Next**:

- Quelle: <https://github.com/googlefonts/atkinson-hyperlegible-next>, Ordner `fonts/ttf/`,
  Stand Commit `7925f50f649b3813257faf2f4c0b381011f434f1` (geladen am 21.11.2026)
- Schnitte: Regular, Italic, SemiBold, Bold (die Oberfläche nutzt normal, kursiv, halbfett
  und fett)
- Lizenz: SIL Open Font License 1.1, Text in `LICENSE-Atkinson-Hyperlegible-Next.txt`
  (Copyright 2020-2024 The Atkinson Hyperlegible Next Project Authors)

Die Schrift wurde für gute Lesbarkeit unter schlechten Bedingungen entworfen und unterscheidet
ähnliche Zeichen (1/7, 3/8, 0/O) deutlich. Das Programm lädt sie beim Start
(`desktop_darstellung._programmschrift_anwenden`). Ihre Ziffern sind normalerweise
unterschiedlich breit; nur in den Punktezellen der Ergebniserfassung schaltet das Programm
Ziffern gleicher Breite ein (OpenType `tnum`, `desktop_darstellung.ziffern_gleich_breit`),
damit die Punkte untereinander stehen. Fehlt der Ordner oder lässt sich eine Datei nicht laden,
bleibt die Systemschrift.

Die Web-Version liefert eine Kopie von Regular und SemiBold samt Lizenz aus `static/schrift/`
aus (`templates/base.html`, `@font-face`, nur vom eigenen Server); halbfett und fett nutzen dort
beide SemiBold. Die Projekt-Website hat eine weitere Kopie (Regular, SemiBold, Bold samt Lizenz) in
`docs/assets/schrift/` (`docs/assets/site.css`). Die PDFs verwenden weiter DejaVu (`fonts/`). Dieser Ordner liegt bewusst nicht in
`fonts/`, das vollständig ins Web-Image kopiert wird - das Web braucht nur die zwei Schnitte.

Eingeführt mit dem Erscheinungsbild „Schiefer und Signal“ (Marco 21.11.2026,
`berichte/Design-Richtung-2026-11.md`).
