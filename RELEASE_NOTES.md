## Was ist neu in 1.0.48

Diese Version bündelt eine gründliche Prüfung der ganzen Desktop-Version: viele kleine
Verbesserungen in der Bedienung, verständlichere Meldungen und mehrere Sicherheitskorrekturen.

**Sicherer und robuster**
- Mehrere Sicherheitskorrekturen beim Umgang mit fremden Termin-Dateien, Sicherungen und PDFs.
- Termin-Dateien werden vor dem Öffnen geprüft. Eine beschädigte, fremde oder schreibgeschützte
  Datei ergibt eine verständliche Meldung, der bisherige Termin bleibt geöffnet.
- Ist das Programm schon geöffnet, fragt ein zweiter Start nach, ob wirklich ein weiteres
  Fenster aufgehen soll – zwei Fenster am selben Termin können sich gegenseitig überschreiben.
- Ein Schreibfehler (z. B. USB-Stick abgezogen) beendet nichts mehr: Die Eingaben bleiben im
  Fenster stehen, die Meldung sagt in Klartext, was los ist.

**Verständlichere Meldungen**
- Ist eine Datei noch in Excel oder einer PDF-Anzeige geöffnet, sagt die Meldung das jetzt –
  statt eines englischen Systemtextes.
- Lange Namenslisten nach einem Import zeigen höchstens 15 Namen, der Rest steht unter
  „Details“. So bleibt der OK-Knopf immer sichtbar.
- Nach einem abgebrochenen Import steht da, wie viele Teilnehmer schon übernommen wurden.

**Teilnehmer und Termine**
- Löschen von Teilnehmern und Terminen hat als Vorgabe „Nein“. Gelöschte Termine gehen in den
  **Papierkorb**.
- Beim Anlegen eines Termins wird der Speicherort geprüft; gibt es die Datei schon, kommt nur
  noch eine Frage, und bei „Nein“ bleiben alle Eingaben stehen.
- Rückfragen bei einer im Termin nicht angebotenen Prüfung und bei Geburtsdatum oder Wurftag in
  der Zukunft. Teilnehmer aus einem anderen Termin werden übernommen, auch wenn ihre Prüfung
  hier nicht angeboten wird – die Meldung nennt sie dann.
- Im Startdialog öffnet **Enter** den markierten Termin.

**Importe und Exporte**
- CSV: Dateien aus Excel werden besser erkannt (auch UTF-16 und Tabulator); verdorbene lange
  Nummern wie „2,76E+14“ werden gemeldet; Telefonnummern bleiben beim Export als Text erhalten.
- PDFs zeigen jetzt auch Zeichen wie „ł“, „ż“ oder „ř“ (neue Schrift DejaVu Sans), lange Namen
  brechen sauber um.
- Ein erneut eingelesenes Anmeldeformular heißt „bereits gemeldet“.

**Auswertung, Zeitplan und Ergebnisse**
- Stechen: Die Auswahl nennt Hund und Startnummer; vorgewählt ist „Stechen noch offen“.
- Die Zeitplan-Startzeit wird mit Enter bzw. beim Verlassen des Feldes gespeichert.
- Beim Wechsel aus der Ergebniserfassung mit ungespeicherten Änderungen gibt es eine klare
  Wahl: Speichern, Verwerfen oder Abbrechen.

**Datensicherung**
- Liegt der geöffnete Termin außerhalb des Termine-Ordners, fragt das Programm, ob er
  mitgesichert werden soll. Das Passwort beim Wiederherstellen hat jetzt wirklich drei Versuche.

**Darstellung, Demo und Kleinigkeiten**
- Das Design „Hell“ bleibt hell, auch wenn Windows auf dunkel steht.
- Die Demoprüfung zeigt ihr Erklärfenster zuverlässig im Bild.
- Die Update-Prüfung friert das Fenster nicht mehr ein.

**Für dieses Update** bitte wie gewohnt das Programm vorher schließen und die neue Version
über die alte installieren. Deine Termine bleiben erhalten.

## Was ist neu in 1.0.47

**Reiter „Export“ übersichtlicher**
- Der lange Erklärtext unter den Knöpfen ist weg. Stattdessen steht neben jedem Knopf in
  einer Zeile, was er erzeugt. Einzelheiten zeigt ein Hinweis, wenn die Maus kurz auf dem
  Knopf oder dem Text bleibt.

**Hilfe bei Fehlern**
- Tritt ein unerwarteter Fehler auf, erscheint jetzt ein Fenster „Unerwarteter Fehler“, statt
  dass das Programm still weiterläuft. Bereits gespeicherte Daten bleiben erhalten.
- Mit **„Fehlerbericht kopieren“** (im Fehlerfenster) bzw. **„Diagnose kopieren“** (Knopf
  „Version“) landen Programmversion, System und die letzten Einträge des Fehlerprotokolls in
  der Zwischenablage – zum Einfügen in eine Fehlermeldung. Dein Benutzername wird dabei
  ersetzt, Termin-Dateien sind nicht enthalten. Bitte vor dem Einfügen kurz durchsehen, ob
  Teilnehmerdaten darin stehen (z. B. in Fehlertexten). Es wird nichts automatisch verschickt.

**Kleinigkeiten**
- Ergebniserfassung: Die Spalte „Status“ nutzt wieder die volle Breite der Tabelle.
- Die Bilder im Handbuch sind einheitlich neu aufgenommen.

**Für dieses Update** bitte wie gewohnt das Programm vorher schließen und die neue Version
über die alte installieren. Deine Termine bleiben erhalten.

## Was ist neu in 1.0.46

**Startnummern schneller vergeben**
- **Bereiche automatisch festlegen:** In den Veranstaltungsdaten (Reiter „Verwaltung“ →
  „Veranstaltungsdaten bearbeiten…“) stellst du eine **Standardgröße je Prüfung** ein, zum
  Beispiel 20. Ein Klick auf „Bereiche automatisch festlegen“ verteilt die Nummern dann
  lückenlos ab 1 auf die angebotenen Prüfungen, etwa Trümmer LK 1 = 1–20 und
  Fläche LK 1 = 21–40. In der neuen Spalte „Anzahl“ kannst du einzelne Prüfungen größer
  oder kleiner machen. Die Standardgröße wird für den nächsten Termin vorgeschlagen.
- **Alle Startnummern zurücksetzen:** Neuer Knopf im Reiter „Teilnehmer“. Danach vergibt
  „Fehlende Startnummern vergeben…“ alle Nummern neu, z. B. nach geänderten Bereichen. Bitte
  nur vor der Prüfung nutzen, weil Zeitplan und Web-Abgleich an den Startnummern hängen.
- **Nur für eine Prüfung:** Ist im „Filter Art/LK“ eine Prüfung gewählt, wirken Zurücksetzen
  und Vergabe nur auf diese Prüfung. Die Meldungen nennen die Prüfung dann ausdrücklich.
- **Wer hat noch keine Nummer?** Unter den Knöpfen steht immer aktuell, in welchen Prüfungen
  noch Teilnehmer ohne Startnummer sind, z. B. „Ohne Startnummer: DK LK 2 (1)“.

**Handbuch**
- Neuer Hinweis in Kapitel 2: Was tun, wenn Chrome, Edge oder Firefox den Download der
  Setup-Datei blockiert.

**Für dieses Update** bitte wie gewohnt das Programm vorher schließen und die neue Version
über die alte installieren. Deine Termine bleiben erhalten.
