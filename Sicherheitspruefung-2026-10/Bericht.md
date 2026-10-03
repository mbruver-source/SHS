# Sicherheits-Codeprüfung SHS-Prüfungsprogramm (03.10.2026)

Marco hat die Prüfung beauftragt. Sie lief als Codeprüfung mit drei Prüfern, jeder mit einem
eigenen Bereich, nacheinander und nur lesend:

| Prüfer | Bereich | Einzelbericht |
|---|---|---|
| 1 | Web und Server (Flask, PostgreSQL, Container) | [pruefer1_web.md](pruefer1_web.md) |
| 2 | Desktop und Dateiformate (Importe, Sicherungen, PDF, Oberfläche) | [pruefer2_desktop.md](pruefer2_desktop.md) |
| 3 | Build, CI und Lieferkette (Workflows, Installer, Abhängigkeiten) | [pruefer3_build.md](pruefer3_build.md) |

Geprüft wurde der Arbeitsstand nach 1.0.40, einschließlich T1–T3 und S1. Nicht erneut
gemeldet wurden die bewusst akzeptierten Punkte: kein Upload-Limit und kein Brute-Force-Schutz
beim Web-Login, fehlende Code-Signierung, keine automatische Update-Prüfung.

**Ergebnis: kein kritischer und kein hoher Fund.** Drei Funde sind mittel, sieben gering, dazu
kommen Hinweise. Bereits früher behobene Punkte haben die Prüfer ohne Befund nachgeprüft:
Path Traversal beim Sicherungs-Import, CSRF, CSV-Formeln beim Export, Rollenprüfung,
SQL-Injection über Schema-Namen und Download-Token.

## Funde (zusammengeführt, nach Schwere)

| ID | Schwere | Fund | Stelle | Quelle |
|---|---|---|---|---|
| S-1 | mittel | Zeitplan-Seitenleiste („Offene Starts“, „⚠ Überschneidungen“) setzt Teilnehmer- und Richternamen **ohne Maskierung als Rich Text** ein. Ein präparierter Name aus einem Import (z. B. mit `<img src="\\server\…">`) könnte beim Anzeigen eine Netzwerkverbindung auslösen (Windows-Anmeldedaten-Hash) bzw. die Anzeige verfälschen. Aus dem Code bestätigt. | `app.py` ~2557–2577 | P2-1 |
| S-2 | mittel | Die Platzhalter aus `.env.example` (Session-Schlüssel, Einrichtungscode) werden **unverändert akzeptiert**. Wer die Vorlage nicht anpasst, betreibt die Web-Version mit öffentlich bekanntem Schlüssel; Session-Cookies ließen sich fälschen. | `app_web.py` (Start), `.env.example` | P1-1 |
| S-3 | mittel | **CI-Härtung:** Der Build-Job hat `contents: write`. Actions werden nur über bewegliche Tags eingebunden (u. a. `softprops/action-gh-release`), PyInstaller und Inno Setup werden ohne feste Version geholt, `packages: write` gilt im Container-Workflow für den ganzen Workflow. | `.github/workflows/*.yml` | P3-1 |
| S-4 | gering–mittel | In **7 PDF-Titeln** fehlt die Maskierung (`_p_wert`) für Vereins- bzw. Richternamen. Ein Name mit `<` o. Ä. lässt den PDF-Export **abbrechen**; lokal bestätigt. | `pdf_export.py` 638, 878, 1182, 1268, 1325, 1499, 1506/1508 | P2-2 |
| S-5 | gering | Die Web-App nutzt das **Eigentümerkonto** der Datenbank statt eines Kontos mit minimalen Rechten. | `compose.yaml`, `db.py` | P1-3 |
| S-6 | gering | Es fehlen Sicherheits-Header (z. B. `X-Frame-Options`, `Content-Security-Policy`) und `Cache-Control: no-store`; **Abmelden per GET**. | `app_web.py` | P1-4 |
| S-7 | gering | Beim „Ergebnisse zurückholen“ kann die temporäre Upload-Datei in Fehlerfällen liegen bleiben. | `app_web.py` | P1-5 |
| S-8 | gering | Sicherungs-ZIP: **keine Grenze für Größe oder Anzahl** der Einträge (wird komplett in den Speicher gelesen); Windows-Sondernamen (`CON`, `:`) werden nicht ausgeschlossen. | `db_sicherung.py` | P2-3 |
| S-9 | gering | `${{ github.ref_name }}` steht direkt im PowerShell-Skript. Ein präparierter Tag-Name könnte Befehle ausführen; setzt allerdings Schreibrechte am Repo voraus. | `build-installer.yml` 69/72 | P3-2 |
| S-10 | gering | `sync_termin.py` nimmt das Datenbank-Passwort über `--dsn` auf der Kommandozeile entgegen. Es ist dann in der Prozessliste und im Verlauf sichtbar. | `sync_termin.py`, Doku | P3-3 |

**Hinweise (keine Schwachstelle im engeren Sinn):**
- H-1: Fremde Termin-Dateien werden ohne `PRAGMA trusted_schema=OFF` und ohne Prüfung auf
  Trigger, Views und `integrity_check` geöffnet. Trigger aus einer fremden Datei blieben
  erhalten (P1-6, P2-4).
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
