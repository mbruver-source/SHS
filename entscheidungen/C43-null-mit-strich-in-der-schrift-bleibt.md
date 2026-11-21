# C43: Null mit Strich in der Schrift der Oberfläche bleibt

- **Status:** akzeptiertes Restrisiko / abgelehnt
- **Bereich:** Sonstiges (Desktop und Web, Erscheinungsbild)
- **Datum:** 21.11.2026 (Marco)

## Entscheidung

Die Schrift der Oberfläche (Atkinson Hyperlegible Next, „Schiefer und Signal“) zeigt die Null überall
durchgestrichen, auch in Datum, Uhrzeit, Versionsnummer und Namen wie „Testuser10“. Das bleibt so.

## Grund

Marco gefällt es. Die durchgestrichene Null gehört zur Schrift: Sie unterscheidet 0 und O deutlich,
was bei Punkten und Chipnummern draußen hilft. Eine Null ohne Strich bietet die Schrift nicht (in der
Datei gibt es nur `zero` und `zero.tf`, beide mit Strich). Ändern ließe sich das nur mit einer anderen
Schrift.

Die Persona Heinz hatte in der Bewertung „Beagle“ gegen „Schiefer und Signal“ angemerkt, die Null
sehe in Datum und Uhrzeit wie ein Durchmesserzeichen aus (Wunsch 3).

## Wann neu bewerten

Wenn mehrere echte Nutzer über die Null stolpern oder die Schrift ohnehin gewechselt wird.

## Fundstellen

- `berichte/Design-Bewertung-2026-11-Heinz.md` (Wunsch 3, Einordnung)
- `Fortschritt.md` „21.11.2026: Wünsche 3 und 5, Großansicht im Zeitplan …“ (Entscheidung) und
  „21.11.2026: Bewertung durch die Persona Heinz …“ (Anlass)
- `schrift/README.md`
