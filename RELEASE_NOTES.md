## Was ist neu in 1.0.63

**Neues Aussehen „Schiefer und Signal“**
- Programm, Web-Version und Website haben ein neues, ruhigeres Aussehen: heller grau-grüner Grund,
  dunkle Schrift, ein dunkler Hauptknopf je Ansicht und deutlich umrandete Eingabefelder. Alles ist
  auch bei hellem Licht und draußen am Handy gut lesbar.
- Noch nicht gespeicherte Zeilen sind kräftig gelb wie ein Absperrband. Disqualifiziert und Abbruch
  zeigen einen dunklen Haken (gespeichert, aber kein normales Ergebnis), der Abbruchgrund steht ganz
  lesbar in der Spalte „Abbruch“.
- Neue, besonders gut lesbare Schrift (Atkinson Hyperlegible Next). Die Null ist durchgestrichen,
  damit sie nicht mit dem Buchstaben O verwechselt wird.
- Im Menü „Ansicht“ heißt die Auswahl jetzt **„Design“**: Schiefer (Standard), Dunkel oder Hoher
  Kontrast. Die Wahl der Akzentfarbe und das Design „Hell“ gibt es nicht mehr; eine frühere Wahl
  wird automatisch zu „Schiefer“.
- **Zeitplan:** Bei wenigen Richtern werden die Spalten breiter. Neu ist **„Groß anzeigen“** je
  Richter: Die Spalte erscheint allein über die ganze Breite, praktisch bei großer Schrift oder
  vielen Richtern.

**Ergebnisse im Browser erfassen (Web-Version)**
- **Veröffentlichen direkt aus dem Programm:** Termine lassen sich über eine gesicherte Verbindung
  (HTTPS mit Prüfung des Server-Fingerabdrucks) ins Web stellen und die Ergebnisse von dort zurück
  in die Termin-Datei holen. Ein Bericht zeigt, was sich geändert hat.
- **Ergebnistabelle** im Browser wie in der Ergebniserfassung des Programms, auch am Handy mit fester
  Kopfzeile, sortiert nach Startnummer. Disqualifikation und Abbruch mit Grund lassen sich dort und
  auf der Seite je Teilnehmer eintragen.
- **Online-Bewertungsbogen** je Disziplin mit Notizfeld. Der Hauptknopf **„Speichern, nächster
  Start“** springt gleich zur nächsten Startnummer derselben Disziplin; darunter steht, wer als
  Nächstes kommt.
- Die Teilnehmerliste zeigt je Teilnehmer „offen“, „teilweise“, „bewertet“, „disqualifiziert“ oder
  „Abbruch“. Nach dem Speichern gibt es überall eine Bestätigung.
- Administratoren sehen, wer zuletzt etwas eingetragen hat. Alle benutzten Bewertungsbögen lassen sich
  als ein PDF herunterladen.
- Löschknöpfe sind rot umrandet, Fehlermeldungen haben ein Warnzeichen.
- Die Anleitung für den eigenen Server (`README_CONTAINER.md`) ist gründlich überarbeitet.

**Für dieses Update** bitte wie gewohnt das Programm vorher schließen und die neue Version
über die alte installieren. Deine Termine bleiben erhalten. Wer die Web-Version betreibt, holt das
neue Image wie in `README_CONTAINER.md` beschrieben.
