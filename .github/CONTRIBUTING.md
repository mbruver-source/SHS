# Mitwirken am SHS-Prüfungsprogramm

Danke, dass du das Programm verbessern möchtest! Die größte Hilfe sind gute Rückmeldungen
aus der Praxis: Was funktioniert nicht, was fehlt, was ist umständlich?

## So kannst du beitragen: über Issues

Alle Beiträge laufen über [Issues](https://github.com/mbruver-source/SHS/issues/new/choose).
Dort gibt es zwei Vorlagen:

- **„Fehler melden“** – etwas funktioniert nicht wie erwartet.
- **„Idee / Wunsch“** – ein Vorschlag für eine neue Funktion oder eine Verbesserung.

Damit eine Meldung schnell bearbeitet werden kann:

1. Vorher kurz ins [Benutzerhandbuch](../docs/HANDBUCH.md) schauen – vielleicht ist das
   Verhalten dort schon erklärt.
2. Die **Programmversion** angeben (steht oben rechts auf dem Button „Version“) und ob es um
   das **Desktop-Programm** oder die **Web-Version** geht.
3. Die **Schritte** beschreiben, die zum Problem führen, und was du stattdessen erwartet
   hättest. Ein Screenshot hilft oft sehr.
4. **Keine echten Teilnehmerdaten** (Namen, Adressen, Chipnummern) in Text oder Screenshots.

Bitte auf Deutsch schreiben – das Programm richtet sich an deutschsprachige Vereine.

## Pull Requests

Der Code wird vom Maintainer selbst gepflegt. **Pull Requests von Dritten werden nicht
übernommen** – auch nicht für kleine Korrekturen. Unaufgefordert geöffnete Pull Requests
werden mit der Bitte geschlossen, das Anliegen als Issue zu melden. Das ist nicht böse
gemeint: So bleibt der Code aus einer Hand, und jede Änderung wird zusammen mit den
Tests und der Änderungshistorie ([Fortschritt.md](../Fortschritt.md)) sauber nachgezogen.

## Sicherheitslücken

Sicherheitslücken bitte **nicht** als öffentliches Issue melden, sondern wie in
[SECURITY.md](SECURITY.md) beschrieben.

## Selbst am Code ausprobieren

Das Programm steht unter der [MIT-Lizenz](../LICENSE). Du darfst es jederzeit forken, für
deinen Verein anpassen und weitergeben. Zum Einstieg:

- Architektur und Module: [Architektur.md](../Architektur.md)
- Entwicklungsumgebung und Tests: Abschnitt „Für Entwickler“ in der [README](../README.md)
- Installer bauen: [README_INSTALLER.md](../README_INSTALLER.md)

Nach `pip install -r requirements.txt -r requirements-dev.txt` laufen die meisten Tests
auch ohne PySide6-Oberfläche und PostgreSQL:

```
python -m unittest test_db test_db_postgres_wrapper test_backup test_pdf_export test_app_web test_bump_version test_shs_core
```

Wenn du dabei etwas findest, das auch anderen Vereinen hilft, ist ein Issue mit deiner
Idee sehr willkommen.

Bitte beachte dabei die [Verhaltensregeln](CODE_OF_CONDUCT.md).
