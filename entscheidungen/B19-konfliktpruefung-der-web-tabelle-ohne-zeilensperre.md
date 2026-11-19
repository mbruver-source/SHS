# B19: Konfliktprüfung der Web-Ergebnistabelle ohne Zeilensperre

- **Status:** bewusst zurückgestellt
- **Bereich:** Web
- **Datum:** 18.11.2026 (Marco)

## Entscheidung

Die Ergebnistabelle vergleicht beim Speichern den aktuellen Datenbankstand mit dem geladenen Stand
(je Einheit: Punkte einer Disziplin, Disqualifiziert, Abbruch) und überschreibt bei Abweichung nichts.
Zwischen dem Lesen und dem Schreiben gibt es keine Zeilensperre (`FOR UPDATE`); ein Schreibvorgang
genau in diesem Zeitfenster könnte still überschrieben werden.

Ergänzung 18.11.2026: Dasselbe gilt für den Online-Bewertungsbogen. Fehlt in einer veralteten Seite oder
einer gebauten Anfrage das Feld `geladen_notiz_<id>`, wird die Notiz ohne Konfliktprüfung geschrieben
(festgehalten in `test_notiz_ohne_geladen_feld_wird_ohne_konfliktpruefung_geschrieben`). Punkte und Notiz
werden in getrennten Commits gespeichert; die Meldung nennt es.

## Grund

Das Zeitfenster ist sehr klein, wie schon auf der Einzelseite (siehe C7). Eine echte Sperre brauchte
Änderungen in der Datenschicht für SQLite und PostgreSQL. Der Nutzen ist gering, weil die Web-Version
selten genutzt wird (siehe B16).

## Wann neu bewerten

Mit B16, bevor die Web-Version regelmäßig mit mehreren Richtern gleichzeitig im Einsatz ist.

## Fundstellen

- `Fortschritt.md`, Abschnitt „18.11.2026: Web-Ergebnistabelle und Rückimport von Disqualifikation/Abbruch (Marco)“
- `entscheidungen/C07-gleichzeitiges-speichern.md`, `entscheidungen/B16-web-komponenten-insgesamt-zurueckgestellt.md`
