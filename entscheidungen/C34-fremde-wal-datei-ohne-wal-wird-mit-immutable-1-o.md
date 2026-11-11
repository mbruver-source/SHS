# C34: Fremde WAL-Datei ohne `-wal` wird mit `immutable=1` ohne Sperre gelesen

- **Status:** akzeptiertes Restrisiko / abgelehnt
- **Bereich:** C. Akzeptierte Restrisiken und abgelehnte Punkte: nicht erneut melden
- **Seit:** 19.10.2026

## Entscheidung

Fremde WAL-Datei ohne `-wal` wird mit `immutable=1` ohne Sperre gelesen: Checkpoint eines fremden Werkzeugs genau währenddessen kann Mischstand/„beschädigt“ ergeben

## Fundstellen

- `historie/2026-10.md`, Abschnitt „19.10.2026: V7 `-wal`/`-shm` beim lesenden Öffnen B6 (Verbesserungen, automatische Abarbeitung)“
- (V7)

Neue Entscheidungen bitte nach `entscheidungen/VORLAGE.md` anlegen und in `OFFEN.md` eintragen.
