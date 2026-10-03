# Sicherheits-Codeprüfung SHS-Prüfungsprogramm (03.10.2026)

Marco hat die Prüfung beauftragt. Sie lief als Codeprüfung mit drei Prüfern, jeder mit einem
eigenen Bereich, nacheinander und nur lesend:

| Prüfer | Bereich | Einzelbericht |
|---|---|---|
| 1 | Web und Server (Flask, PostgreSQL, Container) | [pruefer1_web.md](pruefer1_web.md) |
| 2 | Desktop und Dateiformate (Importe, Sicherungen, PDF, Oberfläche) | [pruefer2_desktop.md](pruefer2_desktop.md) |
| 3 | Build, CI und Lieferkette (Workflows, Installer, Abhängigkeiten) | [pruefer3_build.md](pruefer3_build.md) |
| Codex | Zweitprüfung: Quellcode + Nachweis in lokaler Testinstanz mit Testdaten (Auftrag Marco) | [codex_bericht.md](codex_bericht.md) |

Geprüft wurde der Arbeitsstand nach 1.0.40, einschließlich T1–T3 und S1. Nicht erneut
gemeldet wurden die bewusst akzeptierten Punkte: kein Upload-Limit und kein Brute-Force-Schutz
beim Web-Login, fehlende Code-Signierung, keine automatische Update-Prüfung.

**Ergebnis nach Zusammenführung mit der Codex-Prüfung: kein kritischer und kein hoher Fund.**
Sechs Funde sind mittel, fünf gering, dazu kommen Hinweise. Ein früherer Fund (S-7) ist nicht
bestätigt. Codex hat die Funde, wo möglich, lokal nachgestellt (Spalte „Nachweis“), nur in
einem Temp-Ordner mit erfundenen Daten und ohne externe Ziele. Dass die Repo-Dateien
unverändert blieben, hat es per Hash-Vergleich bestätigt. Bereits früher behobene Punkte haben die Prüfer ohne Befund nachgeprüft:
Path Traversal beim Sicherungs-Import, CSRF, CSV-Formeln beim Export, Rollenprüfung,
SQL-Injection über Schema-Namen und Download-Token.

## Funde (zusammengeführt mit Codex, nach Schwere)

| ID | Schwere | Fund | Stelle | Nachweis |
|---|---|---|---|---|
| C-1 | mittel | **Neu (Codex):** Eine alte Web-Sitzung übernimmt ein unter **gleichem Benutzernamen neu angelegtes Konto**. Die Sitzung speichert nur den Namen, keine feste Konto-ID. Wird ein Konto gelöscht und unter demselben Namen neu angelegt (z. B. als Admin), erhält das alte Cookie dessen Rechte. | `app_web.py` 226–247, 358–364; `db.py` 2549–2574 | lokal reproduziert: Ein altes Richter-Cookie erhielt nach der Neuanlage als Admin Zugriff auf die Adminseite und konnte ein Konto anlegen |
| S-1 | mittel | Die Zeitplan-Seitenleiste setzt Teilnehmer- und Richternamen **ohne Maskierung als Rich Text** ein. Codex hat belegt, dass dadurch HTML-Markup ausgeführt und ein **lokales Bild** im Programm angezeigt wird. Ein Netzwerkzugriff (UNC) wurde nicht getestet. | `app.py` ~2457, 2565–2579 | lokal reproduziert |
| S-2 | mittel | Die Platzhalter aus `.env.example` (Session-Schlüssel, Einrichtungscode) werden **unverändert akzeptiert**. Mit dem öffentlich bekannten Beispielschlüssel ließ sich ein Admin-Cookie fälschen. | `app_web.py` 153, 202, 328–340; `.env.example` | lokal reproduziert (bei unverändertem Beispielschlüssel) |
| S-3 | mittel | **CI-Härtung:** zu weite Rechte (`contents: write`, `packages: write`); Actions sind über bewegliche Tags eingebunden, PyInstaller und Inno Setup ohne feste Version. | `.github/workflows/*.yml` | statisch bestätigt |
| S-4 | mittel *(vorher gering–mittel)* | In **7 PDF-Titeln** fehlt die Maskierung (`_p_wert`). Ein präparierter Vereins- oder Richtername kann **eine lokale Bilddatei ins PDF einbetten**, die bei Weitergabe des PDFs sichtbar wird, oder den Export abbrechen. Ein Netzwerkabruf kam lokal nicht zustande. | `pdf_export.py` 638, 878, 1182, 1268, 1325, 1499, 1506–1509 | lokal reproduziert |
| H-1 | mittel *(vorher Hinweis)* | **Trigger in fremden Termin-Dateien bleiben aktiv:** Eine präparierte Termin-Datei mit Trigger hat ein später regulär eingetragenes Ergebnis still verändert (50 → 0). `trusted_schema=OFF` allein reicht nicht. Vorschlag: Trigger und Views beim Öffnen fremder Dateien ablehnen bzw. entfernen. | `db.py` 569–578 | lokal reproduziert |
| S-5 | gering | Die Web-App nutzt das **Eigentümerkonto** der Datenbank. | `compose.yaml` 18, 49 | statisch bestätigt |
| S-6 | gering | Es fehlen Sicherheits-Header (`X-Frame-Options`/CSP, `nosniff`) und `Cache-Control: no-store`; Abmelden läuft **per GET**. | `app_web.py` | lokal reproduziert (HTTP-Antworten) |
| S-8 | gering | Sicherungs-ZIP: **keine Grenze für Größe oder Anzahl** der Einträge (4 KB komprimiert ergaben 4 MB); `CON.sqlite` wird nicht abgelehnt. Korrektur zum ersten Bericht: Der Doppelpunkt-Name (ADS) wird bereits abgewiesen. | `db_sicherung.py` 33–53, 125–135, 186–195 | lokal reproduziert (begrenzt) |
| S-9 | gering | `${{ github.ref_name }}` steht direkt im PowerShell-Skript. Ein Tag wie `v$(7+7)` wird ausgewertet. Voraussetzung sind Schreibrechte am Repo. | `build-installer.yml` 69/72 | lokal teil-reproduziert |
| S-10 | gering | `sync_termin.py --dsn` nimmt das Passwort auf der Kommandozeile entgegen. | `sync_termin.py` | statisch bestätigt |
| S-7 | – | Temp-Datei beim Zurückholen bleibt liegen: Fehlerpfade räumen auf bzw. die Datei ist per Token registriert. | `app_web.py` 629–657 | **von Codex nicht bestätigt** |

**Hinweise (keine Schwachstelle im engeren Sinn):**
- H-1: jetzt als Fund oben eingestuft (Codex-Nachweis).
- H-2: Container-Images und Abhängigkeiten der Web-Version sind nicht auf feste Versionen
  gepinnt (P1-7).
- H-3: Das Datenbank-Passwort steht im Klartext in der Umgebung des Containers (P1-8).
- H-4: Der Installer schließt eine laufende App beim Update ohne Rückfrage
  (`CloseApplications=force`, P3-Hinweis).

**Bereits bewusst entschieden, nicht neu:**
- P1-2 „Klartext-HTTP, kein `SESSION_COOKIE_SECURE`“. Die Web-Version läuft laut der
  Entscheidung zur ersten Ausbaustufe nur im Vereinsnetz am Prüfungstag, ohne eigenes HTTPS
  (Fortschritt.md, Abschnitt Web-Version und Fix 7).

## Weiteres Vorgehen
Die Funde werden einzeln mit Marco besprochen: umsetzen, zurückstellen oder verwerfen.
Umgesetzt wird nichts ohne sein ausdrückliches Go.
