# B18: Disqualifikation und Abbruch nur in der Web-Ergebnistabelle

- **Status:** bewusst zurückgestellt
- **Bereich:** Web
- **Datum:** 18.11.2026 (Marco)

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
