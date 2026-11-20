# B23: Regel-Funktionen der Web-Version nicht in ein eigenes Modul ausgelagert

- **Status:** bewusst zurückgestellt
- **Bereich:** Web
- **Datum:** 20.11.2026 (Marco, Aufräumpaket aus der QS-Wartbarkeitsprüfung in U13)

## Entscheidung

Die reinen Regel-Funktionen in `app_web.py` (z. B. `_punkte_gesperrt`, `_abbruch_fehler`, `_extern_gesperrt`,
`_einheit_entscheiden`, `_wert_entscheiden`, `_listen_status`, `_vor_wann`, `_zuletzt_texte`) bleiben vorerst in
`app_web.py` und werden nicht in ein Modul `web_regeln.py` ausgelagert. Das übrige Aufräumpaket ist umgesetzt
(U16–U18).

## Grund

Die Funktionen sind nach U16 im Block „Gemeinsame Regeln“ gebündelt und über die Flask-Tests abgedeckt; der Umzug
brächte vor allem Ordnung (`app_web.py` hat rund 2300 Zeilen), aber viele geänderte Importe und Tests ohne neuen
Nutzen für die Anwender.

## Wann neu bewerten

Bei der nächsten größeren Änderung an der Web-Version oder wenn `app_web.py` weiter deutlich wächst.

## Fundstellen

- `Fortschritt.md` „20.11.2026: Rückfragen aus dem UX-Test Web geklärt (Marco)“, „UX-Test Web U16 …“
- `berichte/UX-Test-2026-11-Web/aufgaben-umsetzung.md`, Aufräumpaket
