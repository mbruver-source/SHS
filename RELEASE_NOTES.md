## Was ist neu in 1.0.62

**Sicherer beim Einlesen fremder Dateien**
- Das Programm prüft Termin-Dateien, Sicherungen, automatische Kopien, Listen (CSV/OMA) und
  Anmeldeformulare (PDF) jetzt strenger, bevor es etwas daraus übernimmt. Eine Datei, die nicht
  zu diesem Programm passt, wird mit einer verständlichen Meldung abgelehnt, statt Fehler zu
  verursachen. Deine eigenen Dateien öffnen und speichern wie bisher.
- **Grenzen beim Einlesen:** Listen dürfen höchstens 2 MB, Anmeldeformulare höchstens 5 MB groß
  sein. Textfelder haben Höchstlängen (Namen 100, übrige Texte 200 Zeichen), die Schulterhöhe liegt
  zwischen 1 und 100 cm. Eine Zeile mit einem zu langen Wert wird mit dem Feldnamen als Fehler
  gemeldet, der Rest der Liste wird importiert. Das gilt auch im Teilnehmer-Dialog und bei den
  Veranstaltungsdaten.
- Beim Import großer Dateien zeigt das Programm einen Wartecursor.

**Kopien und Sicherungen**
- Passen Verein oder Datum einer Kopie nicht zum geöffneten Termin, wird sie nicht vorgewählt, und
  das Programm fragt beim Übernehmen noch einmal nach (auch bei „Aus Sicherung holen…“).
- In der Terminübersicht steht jetzt ein eigener Grund, wenn sich ein Termin nicht öffnen lässt,
  weil er mit einer unbekannten Journal-Datei verbunden ist.
- Beim Zurückholen von Ergebnissen aus einer Kopie wird der Teilnehmer über seinen Namen
  abgeglichen, nicht nur über die Nummer.

**Weitere Änderungen**
- Namen und Texte aus fremden Dateien werden in Meldungen und Tooltips immer als Text angezeigt.
- Dateinamen beim Speichern von Ausdrucken sind sicherer gebildet und begrenzt.
- Hilfe (F1) und Handbuch sind an die Änderungen angepasst.

**Für dieses Update** bitte wie gewohnt das Programm vorher schließen und die neue Version
über die alte installieren. Deine Termine bleiben erhalten.
