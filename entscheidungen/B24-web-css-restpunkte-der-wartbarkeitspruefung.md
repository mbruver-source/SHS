# B24: Web-CSS-Restpunkte der Wartbarkeitsprüfung

- **Status:** bewusst zurückgestellt
- **Bereich:** Web
- **Datum:** 21.11.2026 (Marco, Build-Vorbereitung 1.0.63)

## Entscheidung

Drei Kleinigkeiten aus der Wartbarkeitsprüfung des UX-Tests Web bleiben vorerst liegen:

- `textarea` und `select` haben eigene Regeln statt der gemeinsamen Eingabefeld-Regel in
  `templates/base.html`.
- `admin_benutzer.html` und `admin_termine.html` setzen Abstände und Trennlinien noch über
  `style`-Attribute.
- Einige CSS-Tests in `test_app_web.py` prüfen nur Teilzeichenketten des Stylesheets.

## Grund

Kein Fehler für Nutzer, nur Aufräumarbeit; der Build mit dem neuen Erscheinungsbild sollte nicht
darauf warten.

## Wann neu bewerten

Beim nächsten größeren Umbau der Web-Templates.

## Fundstellen

- `berichte/UX-Test-2026-11-Web/aufgaben-umsetzung.md`, „Vor dem Push / Build von Marco zu entscheiden“
- `Fortschritt.md` „Version 1.0.63“
