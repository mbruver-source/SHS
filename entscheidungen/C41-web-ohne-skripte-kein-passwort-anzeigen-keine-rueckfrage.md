# C41: Web ohne Skripte – kein „Passwort anzeigen“, keine Rückfrage vor dem Verlassen

- **Status:** akzeptiertes Restrisiko / abgelehnt
- **Bereich:** Web
- **Datum:** 20.11.2026 (Marco, Rückfragen aus dem UX-Test Web)

## Entscheidung

Die Web-Version bleibt ohne JavaScript (Sicherheitsrichtlinie `script-src 'none'`). Deshalb gibt es an den
Passwortfeldern keinen Schalter „Passwort anzeigen“ (Fund F3; sichtbar ist nur der Einrichtungs-Code) und keine
Rückfrage, wenn man die Ergebnistabelle mit ungespeicherten Eingaben verlässt (Fund C3). Stattdessen: „Passwort
wiederholen“ beim Anlegen, „Bogen“ speichert vorher alle Eingaben der Tabelle, und ein Hinweis unter dem Filter
sagt, dass „Filtern“, „Alle anzeigen“ und die Navigation ungespeicherte Eingaben verwerfen.

## Grund

Ein eingebettetes Skript müsste per Hash in der Sicherheitsrichtlinie freigegeben werden – eine
Sicherheitsänderung mit eigener Prüfung für zwei Komfortfunktionen. Die Ersatzlösungen decken den häufigsten Fall
(Tippfehler beim Anlegen, Bogen aus der Tabelle öffnen) ab.

## Wann neu bewerten

Wenn die Web-Version ohnehin Skripte bekommt oder Richter im Einsatz wiederholt Eingaben durch Verlassen der
Tabelle verlieren.

## Fundstellen

- `Fortschritt.md` „20.11.2026: Rückfragen aus dem UX-Test Web geklärt (Marco)“, „19.11.2026: UX-Test Web U4“, „U6“
- `berichte/UX-Test-2026-11-Web/aufgaben-umsetzung.md`, Rückfragen F3 und C3
