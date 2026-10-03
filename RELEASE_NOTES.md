## Was ist neu in 1.0.41

Diese Version bringt das **Stechen** bei Punktgleichheit auf Platz 1, eindeutigere Knöpfe
für die Teilnehmerliste und viele Verbesserungen bei der Sicherheit. Deine Termine bleiben
beim Update erhalten – einfach die neue Version über die alte installieren.

**Stechen bei Punktgleichheit**
- Sind mehrere Teilnehmer einer Prüfung punktgleich auf **Platz 1**, zeigt die Auswertung
  „1. (Stechen offen)“ und darunter, in welcher Prüfung ein Stechen nötig ist.
- Nach dem Stechen wählst du mit **„Stechen-Sieger festlegen…“** den Sieger. Er wird
  „1. (nach Stechen)“, die anderen werden 2. – auch in Rangliste und Ergebnisliste (PDF).
- Ist ein Stechen noch offen, fragt das Programm vor dem Drucken nach.

**Teilnehmerliste: eindeutige Knöpfe**
- Einlesen heißt jetzt **„Teilnehmerliste einlesen (Excel/CSV)…“** (Reiter „Teilnehmer“
  und „Formular-Import“), Speichern heißt **„Teilnehmerliste speichern (CSV, für Excel)…“**
  (Reiter „Export“). Vorher waren beide Namen kaum zu unterscheiden.

**Sicherheit**
- Termin-Dateien und Sicherungen aus fremder Hand werden beim Öffnen geprüft: Versteckte
  Datenbank-Befehle, die Ergebnisse verändern könnten, entfernt das Programm und meldet das.
- Sicherungen mit unsinnig großen oder zu vielen Dateien werden abgelehnt.
- Namen mit Sonderzeichen (z. B. spitzen Klammern) erscheinen in Fenstern und PDFs immer
  genau so, wie sie eingegeben wurden.
- Web-Version:
  - Nach dem Löschen und Neuanlegen eines Benutzers gilt eine alte Anmeldung nicht mehr.
  - Der Start mit den Beispiel-Passwörtern aus `.env.example` wird verweigert.
  - Zusätzliche Schutzmaßnahmen im Browser.
  - Abmelden ist besser abgesichert.

**Im Hintergrund**
- Jeder Installer wird vor der Veröffentlichung automatisch gestartet, installiert und
  getestet.
- Die Bewertung wird mit festen Referenzfällen geprüft. Außerdem wird bei jeder Version
  getestet, dass Termine und Sicherungen aus älteren Versionen weiter sauber geöffnet werden.

**Handbuch**
- Abschnitt zum Stechen in Kapitel 8 und im Glossar, neue Bilder.
