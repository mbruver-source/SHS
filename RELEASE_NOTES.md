## Was ist neu in 1.0.52

Diese Version bringt vor allem kleinere Verbesserungen und Korrekturen im Hintergrund.

**Teilnehmerliste aus Excel/CSV**
- Listen, die mit älteren Programmversionen gespeichert wurden, werden wieder genau eingelesen.
  Bisher konnte bei manchen Telefonnummern (z. B. „+49 170 …“) oder einem einzelnen „-“ ein
  Hochkomma zu viel stehen bleiben.
- Der Hinweis „Telefonnummer ohne führende 0, vermutlich von Excel entfernt“ kommt erst bei
  langen Nummern ab 9 Ziffern. Ortsnummern ohne Vorwahl lösen ihn nicht mehr aus.

**Zeitplan**
- Einen Prüfungsblock oder eine Pause zu bearbeiten geht bei großen Zeitplänen schneller.

**Fehlerberichte**
- Im kopierten Fehlerbericht bleibt der Text lesbar, auch wenn der Windows-Benutzername sehr
  kurz ist (z. B. „max“). Der Name wird dann nur in Ordnerpfaden unkenntlich gemacht.
- Tritt derselbe Fehler an verschiedenen Stellen im Programm auf, erscheint je Stelle ein
  eigenes Fehlerfenster. Das hilft bei der Fehlersuche.

**Abmelden und Herunterfahren**
- Erlaubt das System beim Abmelden oder Herunterfahren keine Rückfragen (vor allem unter macOS
  und Linux), erscheinen keine Meldungsfenster mehr, die dabei hängen bleiben könnten.
  Ergebnisse werden wie bisher automatisch gespeichert. Klappt das nicht, hält das Programm
  das Beenden an, und der Grund steht im Protokoll.

**Termin-Dateien aus anderen Programmen**
- Wird eine Termin-Datei angezeigt, importiert oder gesichert, die ein anderes Programm in
  einem besonderen Speichermodus abgelegt hat, bleiben keine Zusatzdateien („-wal“, „-shm“)
  mehr daneben liegen. Solche Dateien lassen sich jetzt auch von schreibgeschützten
  Datenträgern lesen.

**Lizenzen**
- Dem Programm liegt jetzt die Datei `THIRD_PARTY_LICENSES.txt` bei, mit den Lizenzen aller
  mitgelieferten Fremdbausteine (u. a. Python, Qt, reportlab). Unter Windows liegt sie im
  Programmordner, unter macOS im .dmg, unter Linux (.deb) unter
  `/usr/share/doc/shs-pruefungsprogramm/`.

**Intern**
- Die automatischen Tests laufen jetzt zusätzlich unter Windows.

**Für dieses Update** bitte wie gewohnt das Programm vorher schließen und die neue Version
über die alte installieren. Deine Termine bleiben erhalten.
