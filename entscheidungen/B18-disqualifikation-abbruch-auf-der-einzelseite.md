# B18: Disqualifikation und Abbruch nur in der Web-Ergebnistabelle

- **Status:** überholt (19.11.2026, Marco)
- **Bereich:** Web
- **Datum:** 18.11.2026 (Marco)

> **Überholt am 19.11.2026 (Marco, UX-Test Web, Fund D1):** Ein Richter am Handy fand die
> Disqualifikation nicht (Note 4). Die Einzelseite hat jetzt Disqualifiziert und Abbruch mit Grund,
> mit denselben Regeln und denselben Hilfsfunktionen wie die Tabelle (Grund nötig, Sperre der
> Punkte, Konfliktprüfung des Status, keine Punkte in eine inzwischen fremd gesperrte Zeile). Die
> Punkte der Einzelseite werden sonst wie bisher je Disziplin nur geschrieben, wenn sie verändert
> wurden (C7). Siehe `Fortschritt.md` „19.11.2026: UX-Test Web U2“.

## Entscheidung

Disqualifikation und Abbruch (mit Grund) lassen sich im Web nur in der Ergebnistabelle (`/ergebnisse`)
erfassen. Die Einzelseite `/teilnehmer/<id>` bleibt bei den Punkten.

## Grund

Die Tabelle ist dem Desktop-Reiter „Ergebniserfassung“ nachgebaut, der dieselben Spalten hat. Eine
zweite Bedienung auf der Einzelseite würde die Sperrregel und die Konfliktprüfung doppeln.

## Wann neu bewerten

Wenn Richter am Handy die Einzelseite bevorzugen und dort Disqualifikation oder Abbruch vermissen.

## Fundstellen

- `Fortschritt.md`, Abschnitt „18.11.2026: Web-Ergebnistabelle und Rückimport von Disqualifikation/Abbruch (Marco)“
- `app_web.py` (Route `ergebnistabelle`, `ergebnis_erfassen`)
