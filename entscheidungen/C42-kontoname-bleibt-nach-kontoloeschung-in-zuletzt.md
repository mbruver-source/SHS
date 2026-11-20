# C42: Kontoname bleibt nach dem Löschen eines Web-Kontos in „zuletzt …“

- **Status:** akzeptiertes Restrisiko / abgelehnt
- **Bereich:** Web
- **Datum:** 20.11.2026 (Marco, Hinweis aus der QS-Sicherheitsprüfung in U13)

## Entscheidung

Wird ein Web-Konto gelöscht, bleiben seine Einträge in der Tabelle `web_aenderungen` (Admin-Zeile „zuletzt
<Konto>, …“ in der Ergebnistabelle) stehen, bis der Termin auf dem Server gelöscht wird.

## Grund

So bleibt nachvollziehbar, wer eingetragen hat, auch wenn das Konto inzwischen weg ist. Nur Admins sehen die
Angabe, sie geht nie in die Termin-Datei, und sie verschwindet mit dem Termin auf dem Server.

## Wann neu bewerten

Wenn Konten echter Personen langfristig auf dem Server bleiben sollen oder eine Löschpflicht greift.

## Fundstellen

- `Fortschritt.md` „20.11.2026: UX-Test Web U12 …“, „U13 …“, „Rückfragen aus dem UX-Test Web geklärt“
- `db_web.py` (`web_aenderungen`), `app_web.py` (`_zuletzt_texte`)
