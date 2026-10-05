## Was ist neu in 1.0.43

Diese Version lässt die **Demoprüfung von allein laufen**, schützt Ergebnisse beim Update
besser und härtet die Web-Version. Deine Termine bleiben beim Update erhalten – einfach die
neue Version über die alte installieren.

**Demoprüfung: automatisch weiter**
- Ist ein Schritt fertig, zählt der Knopf zehn Sekunden herunter („Weiter ▶ (10)“) und
  schaltet dann von allein weiter. So läuft die Demo auch ohne Zutun durch.
- Wer lieber selbst klickt, nimmt den Haken bei **„Automatisch weiter“** heraus.
- Der Countdown hält an, wenn du die Ergebnisliste über „PDF öffnen“ anschaust oder selbst
  in einem Fenster der Demo etwas eintippst. Ist eine Meldung des Programms offen, wartet er.
- Im letzten Schritt wartet die Demo, bis du auf „Fertig“ klickst.

**Update ohne Datenverlust**
- Ist das Programm beim Update geöffnet, schließt der Installer es jetzt regulär. Offene
  Ergebnisse werden dabei automatisch gespeichert.
- Lässt sich etwas nicht speichern, fragt das Programm nach. Verwirfst du die Änderungen
  nicht ausdrücklich, bleibt es offen, und der Installer meldet das. Vorher wurde es in
  diesem Fall hart beendet.
- Dasselbe gilt beim Abmelden oder Herunterfahren von Windows.

**Web-Version (Container)**
- Datenbank-Passwort, Session-Schlüssel und Einrichtungs-Code stehen nicht mehr in `.env`,
  sondern als Dateien im Ordner `secrets/`. **Bestehende Installationen müssen einmal
  umziehen**, siehe `README_CONTAINER.md`, Abschnitt „Geheimnisse“. Das Datenbank-Passwort
  muss dabei gleich bleiben.
- Die Images sind auf feste Versionen festgelegt; `compose.yaml` holt genau diese Version
  statt `latest`.
- Der Web-Container läuft mit nur lesbarem Dateisystem und ohne zusätzliche Rechte.

**Handbuch**
- Abschnitt „Demoprüfung“ ergänzt, Bilder auf 1.0.43 erneuert.
