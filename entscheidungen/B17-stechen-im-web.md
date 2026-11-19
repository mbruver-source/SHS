# B17: Stechen im Web

- **Status:** bewusst zurückgestellt
- **Bereich:** Web
- **Datum:** 18.11.2026 (Marco)

## Entscheidung

Das Stechen (Auswahl des Siegers bei Gleichstand um Platz 1) wird im Web nicht erfasst. Es bleibt im
Reiter „Auswertung“ des Desktops, wie dort auch heute (der Desktop-Reiter „Ergebniserfassung“ kennt
kein Stechen).

## Grund

Das Stechen braucht die Rangliste (`berechne_auswertung`, Gleichstandsgruppen) und eine eigene
Bedienung. Die neue Web-Ergebnistabelle ist dem Desktop-Reiter „Ergebniserfassung“ nachgebaut und hat
dort ebenfalls weder Summe noch Platz. Ab 01.01.2027 entfällt das Stechen nach der neuen
Prüfungsordnung ohnehin (siehe `PO_01012027.md`). Das Stechen wird beim Zurückholen aus dem Web nicht
übertragen.

## Wann neu bewerten

Wenn das Stechen im Web gewünscht wird und der Termin noch vor dem 01.01.2027 liegt, sonst nie.

## Fundstellen

- `Fortschritt.md`, Abschnitt „18.11.2026: Web-Ergebnistabelle und Rückimport von Disqualifikation/Abbruch (Marco)“
- `desktop_auswertung.py` (Stechen), `db_ergebnisse.setze_stechen_sieger`, `shs_core.stechen_gilt`
