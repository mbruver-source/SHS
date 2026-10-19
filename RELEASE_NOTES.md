## Was ist neu in 1.0.51

Diese Version macht die Ergebniserfassung schneller und einfacher zu bedienen und die
Datensicherung zuverlässiger.

**Ergebniserfassung**
- Deutlich schneller bei großen Prüfungen: Mit 1000 Teilnehmern dauern Reiterwechsel,
  Sortieren und ein Wechsel der Ansicht jetzt weniger als eine halbe Sekunde statt mehrerer
  Sekunden, und das Programm braucht viel weniger Arbeitsspeicher.
- Einfachere Eingabe: Zelle anklicken und die Zahl tippen, sie ersetzt den bisherigen Wert.
  **Tab** springt zur nächsten Zelle, **Enter** übernimmt die Zahl, **Entf** leert die Zelle,
  die **Leertaste** setzt das Häkchen bei „Disqualifiziert“ bzw. „Abbruch“.
- Nach „Disqualifiziert“ oder „Abbruch“ sind die gesperrten Punktezellen jetzt in allen
  Designs deutlich zu erkennen.
- Eine gerade getippte Zahl geht nicht mehr verloren, wenn man währenddessen die Ansicht
  wechselt.
- Werden beim Neuladen Eingaben verworfen, steht jede Person nur noch in einer Zeile mit allen
  Gründen.

**Datensicherung**
- Jeder Termin kommt mit seinem zuletzt gespeicherten Stand in die Sicherung, auch der gerade
  geöffnete.
- Lässt sich eine Datei nicht als Termin lesen, wird sie unverändert mitgesichert, und die
  Meldung nennt sie.
- Das Wiederherstellen ist robuster: Klappt es bei einem Termin nicht, bleibt dessen bisheriger
  Stand vollständig erhalten.

**Termine öffnen und importieren**
- Eine ungewöhnlich große Termin-Datei (über 50 MB) erscheint in der Terminliste als
  „(ungewöhnlich groß)“. Vor dem Öffnen fragt das Programm nach.
- Beim Import aus einem anderen Termin wird die gewählte Datei zusätzlich auf Beschädigungen
  geprüft. Fehlen in ihr Angaben, sagt der Dialog das verständlich. Teilnehmer, die im anderen
  Termin nicht erschienen sind, tragen einen Vermerk.
- Geburtsdatum und Wurftag werden gegen das Prüfungsdatum geprüft statt gegen das heutige
  Datum.
- Beim Wechsel des Termins fragt das Programm erst nach ungespeicherten Ergebnissen, wenn ein
  anderer Termin gewählt ist. Ein dabei neu angelegter, leerer Termin kommt bei „Abbrechen“ in
  den Papierkorb.

**Web-Erfassung**
- Ohne veröffentlichten Termin erklärt die Seite „Termin wählen“, wo man ihn veröffentlicht.
- Das Passwortfeld der Anmeldung sieht aus wie die übrigen Eingabefelder.

**Demoprüfung und Handbuch**
- Die Demoprüfung erklärt die neue Bedienung der Ergebniserfassung.
- Das Handbuch ist entsprechend aktualisiert.

**Für dieses Update** bitte wie gewohnt das Programm vorher schließen und die neue Version
über die alte installieren. Deine Termine bleiben erhalten.
