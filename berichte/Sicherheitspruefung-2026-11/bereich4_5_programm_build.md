# Bereiche 4 und 5: Programm/System sowie Build, CI und Lieferkette

Durchsicht der Hauptsitzung (nicht durch einen Prüf-Agenten), Stand HEAD e557b0f (1.0.61), 13.11.2026.
Nur gelesen, nichts nachgestellt außer der SQLite-Version der EXE (siehe Bericht, D-2). Kein Fund, nur
Hinweise. `build-container.yml`, `Containerfile` und `compose.yaml` waren nicht Gegenstand.

## Gelesen

- `desktop_programm.py` ganz (Update-Prüfung, Lizenzfenster, Sitzungsende, Zweitstart).
- `desktop_gemeinsam.py`: `_url_oeffnen`, `_ordner_zeigen`, Einstellungen, Absturzprotokoll,
  `_ohne_benutzerpfad`, `diagnose_text`, `fehlerfenster_zeigen`.
- `selbsttest.py` (Einstieg), `desktop_demo.py` (`demo_reste_aufraeumen`), `db_termine.termine_ordner`.
- `.github/workflows/build-installer.yml`, `tests.yml`, `installer.iss`, `build.spec`,
  `tools/linux_pakete.sh`, `requirements.txt`, `requirements-dev.txt`, `requirements-postgres.txt`.
- Repo-Einstellungen auf GitHub, lesend über `gh api`.

## Hinweise

| Kennung | Hinweis | Stelle |
|---|---|---|
| P-1 | `--selbsttest` ohne Pfad schreibt nach `<Temp>/shs_selbsttest.log` (fester Name, `open(…, "w")`). Unter Linux ist `/tmp` gemeinsam; ein anderer lokaler Benutzer könnte dort vorab einen Link ablegen. Übliche Distributionen blockieren das (`protected_symlinks`), und der Selbsttest läuft nur von Hand bzw. in der CI. Unter Windows ist der Temp-Ordner je Benutzer. | `selbsttest.py:34`, `:54` |
| L-1 | Repo ohne Regeln für Tags und Zweige: `rulesets` leer, `main` ungeschützt. Ein Tag `v*` löst Build und Release aus. Bei nur einem Konto mit Schreibrecht heißt das: Der Schutz der Lieferkette hängt allein an diesem Konto (2FA). Ein Tag-Regelsatz für `v*` kostet nichts. | GitHub-Einstellungen |
| L-3 | Secret Scanning und Push Protection sind aus (für öffentliche Repos kostenlos). `sha_pinning_required` für Actions ist aus; einschalten würde die S-3-Regel (Actions auf Commit-Hash) erzwingen. | GitHub-Einstellungen |
| L-4 | `tests.yml` checkt ohne `persist-credentials: false` aus (im Installer-Workflow gesetzt). Das Token hat nur Leserechte, der Nutzen ist gering. | `tests.yml:75`, `:119` |
| L-5 | `ISCC installer.iss /DMyAppVersion=${{ steps.version.outputs.version }}`: Der Inhalt von `version.txt` wird direkt ins Skript eingesetzt (wie S-9, dort für den Tag behoben). Voraussetzung wäre Schreibrecht am Repo; bei Tag-Builds prüft der Schritt davor das Format, bei `workflow_dispatch` nicht. | `build-installer.yml:131` |
| L-6 | bandit konnte nicht neu laufen (lokal nicht installiert; der Bericht vom 01.11.2026 zeigt auf die inzwischen zerlegte `db.py`). Ersatzweise hat die Hauptsitzung alle zusammengesetzten SQL-Stellen per Suche durchgesehen (siehe Bericht). Am 14.11.2026 nachgeholt: `bandit-2026-11-14.md`, kein Fund. | `bandit-2026-11-01.md` |

## Ohne Befund

- **Update-Prüfung:** feste HTTPS-Adresse der GitHub-API, Standard-Zertifikatsprüfung, Zeitgrenze,
  Hintergrund-Thread; das Ergebnis wird nur als Klartext angezeigt, es wird nichts heruntergeladen oder
  ausgeführt. Der Knopf öffnet die feste Release-Seite.
- **`explorer /select,"<pfad>"`:** ohne Shell, nur für vorhandene Dateien; Windows-Dateinamen können
  kein `"` enthalten.
- **Absturzprotokoll und Diagnose:** im Benutzerprofil, begrenzt, Benutzerpfad und -name werden ersetzt,
  nichts wird verschickt; der Hinweis auf mögliche Teilnehmerdaten steht im Fenster.
- **Demo-Reste aufräumen:** `rmtree` folgt keinen Links und kann fremde Ordner in `/tmp` nicht löschen.
- **Einstellungen (QSettings):** nur eigene Werte des Benutzers, gegen feste Listen geprüft.
- **CI:** Leserechte als Standard, Schreibrecht nur im Release-Job, der keinen Build-Code ausführt;
  Actions auf Commit-Hashes; PyInstaller, Inno Setup, dmgbuild, appimagetool und Runtime mit festen
  Versionen bzw. Prüfsummen; S-9 (Tag-Name über Umgebungsvariable, Formatprüfung) greift;
  `tests.yml` läuft bei Pull Requests ohne Geheimnisse; erste Beiträge aus Forks brauchen Freigabe.
- **Installer:** Installation ohne Adminrechte möglich, kein Dienst, keine Dateizuordnung, kein
  `[Code]`-Abschnitt; Termine liegen außerhalb des Programmordners.
- **Bereits entschieden, nicht neu:** keine Hash-Lock-Datei und kein Dependabot (Marco, 05.10.2026),
  Code-Signatur (B8), Python 3.11 (B13), Adresse im `.deb` (C32).
