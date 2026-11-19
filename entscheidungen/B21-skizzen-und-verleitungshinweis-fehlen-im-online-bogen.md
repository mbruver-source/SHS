# B21: Online-Bewertungsbogen ohne Skizzen und ohne Verleitungs-Hinweis

- **Status:** bewusst zurückgestellt
- **Bereich:** Web
- **Datum:** 18.11.2026 (Marco)

## Entscheidung

Der Online-Bewertungsbogen (`/bewertungsbogen/<id>/<disziplin>`) hat nicht die Skizzen des Papierbogens
(Position des Gegenstands, Kammer-Nr. beim Behältnis) und nicht den Verleitungs-Hinweis. Stattdessen gibt
es ein Notizfeld (siehe B20).

## Grund

Zeichnen und Ankreuzen auf einer Skizze brauchen JavaScript, das die Sicherheitsrichtlinie der Web-Version
bewusst verbietet (`script-src 'none'`). Die Angaben gibt es außerdem nicht als Datenbankfelder.

## Wann neu bewerten

Wenn die Position des Gegenstands strukturiert erfasst werden soll (eigene Felder, z. B. Auswahl der
Behältnis-Nr.) oder die Sicherheitsrichtlinie sich ändert.

## Fundstellen

- `Fortschritt.md`, Abschnitt „18.11.2026: Online-Bewertungsbogen im Web mit Notizfeld (Marco)“
- `pdf_export._bewertungsabschnitt` (Papierbogen), `templates/bewertungsbogen.html`
