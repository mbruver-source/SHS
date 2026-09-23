<!--
Hinweis: Dieses Projekt nimmt keine Pull Requests von Dritten an.
Fehler und Wünsche bitte als Issue melden:
https://github.com/mbruver-source/SHS/issues/new/choose
Hintergrund: .github/CONTRIBUTING.md
Die Vorlage unten ist für die eigenen PRs des Maintainers gedacht.
-->

## Was ändert sich?

<!-- Kurze Beschreibung der Änderung und warum sie nötig ist. -->

Bezug: #

## Checkliste

- [ ] Lokale Tests laufen durch
      (`python -m unittest test_db test_db_postgres_wrapper test_backup test_pdf_export test_app_web test_bump_version test_shs_core`).
- [ ] Keine echten Teilnehmerdaten in Code, Tests oder Screenshots.
- [ ] Versionsnummer **nicht** geändert (das passiert erst beim Build per `bump_version.py`).
- [ ] `Fortschritt.md` ist ergänzt.
