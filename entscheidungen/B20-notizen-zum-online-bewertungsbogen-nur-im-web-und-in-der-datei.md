# B20: Notizen zum Online-Bewertungsbogen nur im Web und in der Termin-Datei

- **Status:** bewusst zurückgestellt
- **Bereich:** Web | Daten | Desktop
- **Datum:** 18.11.2026 (Marco)

## Entscheidung

Die Notiz je Teilnehmer und Disziplin (max. 500 Zeichen, Spalten `notiz_truemmerfeld`,
`notiz_flaechensuche`, `notiz_behaeltnis`) wird im Web erfasst, beim Veröffentlichen mitgenommen und
beim „Ergebnisse aus Web holen“ in die Termin-Datei übernommen (Web-Stand führt, fehlt der Schlüssel in
der Server-Antwort, bleibt die Notiz der Datei). **Nachtrag 18.11.2026 (Marco):** Auf dem PDF-Bewertungsbogen
erscheint die Notiz jetzt, wenn eine vorhanden ist (klein in der rechten Spalte der Positionszeile, höchstens
4 Zeilen, gekürzt mit „…“ und Hinweis „vollständig im Web“; `pdf_export._notiz_block`). Das gilt für den
Desktop-Bogen wie für das Sammel-PDF „Benutzte Bögen als PDF“ im Web. In der Desktop-Oberfläche
(Ergebnisreiter) wird sie noch nicht angezeigt. „Ergebnisse aus automatischer Kopie wiederherstellen“ holt Notizen nicht
einzeln zurück (`ERGEBNIS_WERTE` kennt sie nicht); beim Wiederherstellen eines gelöschten Teilnehmers
bleiben sie erhalten.

## Grund

Das Notizfeld ersetzt online die Freitext-Angaben des Papierbogens. Die Anzeige in der Desktop-Oberfläche ist
eigener Aufwand (Oberfläche, Tests) und war nicht verlangt; auf dem PDF-Bogen reichte der Platz neben der Skizze.

## Wann neu bewerten

Wenn die Notizen in der Desktop-Oberfläche sichtbar sein sollen. Stellen: `desktop_ergebnis.py`
(ErgebnisTab, neben den Punkten je Disziplin), `db_ergebnisse.ERGEBNIS_WERTE`. Die PDF-Anzeige ist erledigt.

## Fundstellen

- `Fortschritt.md`, Abschnitt „18.11.2026: Online-Bewertungsbogen im Web mit Notizfeld (Marco)“
- `db_ergebnisse.setze_notiz`, `db_sync._ergebnisse_einarbeiten`
