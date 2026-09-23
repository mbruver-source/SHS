# Sicherheitsrichtlinie

## Unterstützte Versionen

Sicherheitskorrekturen gibt es nur für die **jeweils aktuelle Version**
([Releases](https://github.com/mbruver-source/SHS/releases/latest)). Bitte vor einer Meldung
prüfen, ob das Problem auch dort noch auftritt.

- Desktop-Programm: im Programm über **Version → „Nach Updates suchen“** aktualisieren.
- Web-Version: aktuellen Quellcode holen und neu bauen (`podman-compose up --build -d`)
  oder das veröffentlichte Image ziehen (`podman-compose pull`), siehe
  [README_CONTAINER.md](../README_CONTAINER.md).

## Sicherheitslücke melden

Bitte Sicherheitslücken **nicht als öffentliches Issue** melden, damit sie nicht ausgenutzt
werden können, bevor eine Korrektur verfügbar ist.

1. **Bevorzugt:** über GitHub im Reiter
   [**Security → „Report a vulnerability“**](https://github.com/mbruver-source/SHS/security/advisories/new).
   Die Meldung ist nur für dich und den Maintainer sichtbar.
2. **Alternativ:** per E-Mail an [m.bruver@gmail.com](mailto:m.bruver@gmail.com) mit dem
   Betreff „SHS Sicherheit“.

Hilfreich sind:

- betroffene Programmversion und ob Desktop-Programm, Web-Version oder Installer betroffen ist,
- die Schritte, mit denen sich das Problem nachvollziehen lässt,
- deine Einschätzung, was ein Angreifer damit erreichen könnte.

**Bitte keine echten Teilnehmerdaten** mitschicken – Beispieldaten reichen.

## Was danach passiert

Das Projekt wird ehrenamtlich gepflegt, feste Fristen gibt es daher nicht. In der Regel:

- bekommst du **innerhalb einer Woche** eine Eingangsbestätigung,
- wird die Lücke in einer neuen Version behoben,
- wirst du auf Wunsch in den Release-Notizen als Finder genannt.

Eine Belohnung (Bug-Bounty) gibt es nicht.

## Geltungsbereich

- das Desktop-Programm und der Windows-Installer,
- die Web-Version samt Container (`Containerfile`, `compose.yaml`),
- die Datensicherung (ZIP-Dateien, optional mit Passwort).

Die Web-Version ist für den Betrieb **im lokalen Netz des Vereins** gedacht und nicht dafür,
direkt aus dem Internet erreichbar zu sein (siehe [README_CONTAINER.md](../README_CONTAINER.md)).
