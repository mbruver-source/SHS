# B10: Weitere Testarten

- **Status:** bewusst zurückgestellt
- **Bereich:** B. Bewusst zurückgestellt (Marcos Entscheidung)
- **Datum:** 03.10.2026

## Entscheidung

Weitere Testarten, Stand 11.11.2026:

- **Erledigt:** Windows in der CI (19.10.2026, V2), Abdeckung und bandit (01.11.2026).
- **Offen, Desktop:** Generalprobe (kompletter Prüfungstag mit Probedaten).
- **Teilweise erledigt (11.11.2026), Barrierefreiheit:** Namen für Bildschirmleser und Tab-Erreichbarkeit sind umgesetzt und werden von `test_gui_barrierefreiheit.py` geprüft. Offen bleibt die Prüfung mit einem echten Bildschirmleser (NVDA, Narrator), Farbe als einziger Hinweis und die selten genutzten Dialoge.
- **Offen, Web (gehört zu B16):** gleichzeitige Web-Eingaben, ZAP/XSS-Prüfung.

## Wann neu bewerten

Die Desktop-Punkte vor dem nächsten großen Release; die Web-Punkte mit B16.

## Fundstellen

- `historie/2026-10.md`, Abschnitt „03.10.2026: Ergänzende Testarten T1–T3 vorgemerkt (nur Dokumentation, kein Code geändert)“
- `Fortschritt.md`, Abschnitt „01.11.2026: Durchgang aller offenen Punkte mit Marco“

Neue Entscheidungen bitte nach `entscheidungen/VORLAGE.md` anlegen und in `OFFEN.md` eintragen.
