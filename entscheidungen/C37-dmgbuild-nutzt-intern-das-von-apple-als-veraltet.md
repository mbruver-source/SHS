# C37: dmgbuild nutzt intern das von Apple als veraltet geführte `hdiutil udifrez`

- **Status:** akzeptiertes Restrisiko / abgelehnt
- **Bereich:** C. Akzeptierte Restrisiken und abgelehnte Punkte: nicht erneut melden
- **Seit:** 01.11.2026

## Entscheidung

dmgbuild nutzt intern das von Apple als veraltet geführte `hdiutil udifrez`; fällt es weg, schlägt der dmg-Schritt fehl und wird dann ersetzt

## Fundstellen

- `Fortschritt.md`, Abschnitt „01.11.2026: Lizenzen im Versionsfenster und Lizenzseite im Installer (Marco)“
- `Fortschritt.md`, Abschnitt „01.11.2026: Durchgang aller offenen Punkte mit Marco“

Neue Entscheidungen bitte nach `entscheidungen/VORLAGE.md` anlegen und in `OFFEN.md` eintragen.
