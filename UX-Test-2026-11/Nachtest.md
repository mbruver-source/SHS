# UX-Nachtest nach der Umsetzung (04.11.2026)

Gezielter Nachtest mit zwei Personas, nachdem die Funde aus dem [Bericht](Bericht.md) umgesetzt
waren (Aufgaben A1–A11, siehe [aufgaben.md](aufgaben.md)). Gleiches Steuerwerkzeug, gleiches
Szenario, Arbeitsstand nach 1.0.55. Die Personas kannten die Änderungen nicht. Ihre Funde aus dem
ersten Test haben sie erst nach dem Test als Abgleich bewertet.

- **Werner (L-B2):** Laie, ohne Handbuch – [personas/L-B2.md](personas/L-B2.md)
- **Tobias (N-B2):** normal, klickt Meldungen weg, ohne Handbuch – [personas/N-B2.md](personas/N-B2.md)

## Ergebnis

| | Installation | Erststart | Termin-Ablauf | **Gesamt** | Allein am Prüfungstag? |
|---|---|---|---|---|---|
| Werner, 1. Test | 3 | 2 | 2– | **2–** | Eher ja |
| **Werner, Nachtest** | 3 | 2+ | 2 | **2** | Eher ja (näher an Ja) |
| Tobias, 1. Test | 2 | 2 | 2 | **2** | Eher ja |
| **Tobias, Nachtest** | 2 | 1 | 2 | **2 (eher 1–2)** | **Ja** |

- **Keine Aufgabe gescheitert.**
  - Tobias: alle 16 Aufgaben ✓.
  - Werner: alles ohne Handbuch geschafft, nur Installation und Zeitplan mit Mühe; einmal brauchte er
    die Hilfe, um das Anmeldeformular zu finden.
- **Abgleich mit den alten Funden:**
  - Werner: 6 behoben, 2 weitgehend, 1 teilweise, 1 nicht erlebt.
  - Tobias: 5 behoben, 3 teilweise, 1 nicht behoben (Name der Sicherungsdatei, bewusst so
    gelassen), 1 nicht erlebt.
- **Ausdrücklich gelobt:**
  - Die Mittagspause landet nicht mehr am Ende.
  - Kein vorausgewählter Tauschpartner mehr.
  - Die Abbruch-Zelle ist als Auswahlfeld erkennbar.
  - Es gibt eine Erklärung bei zu hohen Punkten.
  - Schriftgröße, Lesezeit der Demo und der Hinweis „nur ein Gegenstand“ wirken.

## Neue bzw. verbliebene Funde

| Nr | Fund | Wer | Schwere |
|---|---|---|---|
| N1 | Nach „Automatisch verteilen…“ fehlt eine ausdrückliche Bestätigung „keine Überschneidungen“; grüne Haken heißen nur „eingeplant“ | Werner | mittel |
| N2 | Import-Meldung: Enter drückt „OK“, danach ist die Ablehnungsliste nicht mehr nachzulesen (der Kopierknopf ist nicht Vorgabe) | Tobias | mittel |
| N3 | „29 Ergebnis(se) gespeichert“ bei 16 Teilnehmern – zählt Disziplinen, wirkt wie doppelt | Werner | gering |
| N4 | Abbruch-Spalte zeigte den Grund abgeschnitten („letzung H“); Status zeigt bei DQ/Abbruch nur „gespeichert“ | Werner | gering (evtl. Testumgebung) |
| N5 | Versionsfenster: Fachwörter (Absturzprotokoll, Diagnose); Update-Suche nur hinter „Version …“; bei Tobias öffnete Enter „Lizenzen“ | beide | gering, Enter-Verhalten **am Gerät prüfen** (Code setzt den Anfangsfokus auf „Schließen“) |
| N6 | Datensicherung wirkt, als sei ein Passwort Pflicht | Werner | gering |
| N7 | Bei leerem Verband/Meldestelle steht die Rückfrage auf „Ja“, beim Formular keine zweite Warnung | Tobias | gering |
| N8 | ED: „Schlüsselbund, Socke“ in einem Feld wird ohne Nachfrage angenommen | Tobias | gering |
| N9 | Hilfe trotz Inhaltszeile noch lang; Sicherungsdateiname | Tobias | gering |

Diese Punkte fließen in die ToDo-Liste „Note 1“ ([note1-todos.md](note1-todos.md)) ein. Umgesetzt
ist davon nichts.
