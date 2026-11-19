# B22: Sammel-PDF der Bögen ohne Obergrenze und ohne Hintergrundlauf

- **Status:** bewusst zurückgestellt
- **Bereich:** Web
- **Datum:** 18.11.2026 (Marco)

## Entscheidung

`GET /ergebnisse/boegen.pdf` („Benutzte Bögen als PDF“) erzeugt die PDF synchron in einem Server-Thread
(waitress). Es gibt keine Obergrenze für die Zahl der Bögen und keinen Hintergrundauftrag.

## Grund

Gemessen (Verifikation 18.11.2026): etwa 0,11 s je Dreikampf-Teilnehmer, 100 Teilnehmer mit Notiz in ca. 11 s,
500 in ca. 110 s, Speicherspitze ca. 75 MB, PDF ca. 3 MB. Bei einem realistischen Termin (unter 100
Teilnehmer) ist das vertretbar; mit Filter nach Art/LK wird es kürzer. Wiederholtes Klicken könnte mehrere
Threads binden. Die Route verlangt Anmeldung (Administrator oder Eintrag-Rolle), nicht angemeldet erreicht
sie niemand. Ein Hintergrundauftrag oder eine Obergrenze wäre eigener Umbau (Zwischenspeicher, Abfrage).

## Wann neu bewerten

Wenn Termine mit deutlich mehr als 100 Teilnehmern im Web ausgedruckt werden oder der Server bei der PDF-Erzeugung
spürbar hängt (dann Obergrenze je Aufruf oder Erzeugung im Hintergrund).

## Fundstellen

- `Fortschritt.md`, Abschnitt „18.11.2026: Online-Bewertungsbogen im Web mit Notizfeld (Marco)“
- `app_web.py` (`ergebnis_boegen_pdf`), `pdf_export.erstelle_alle_bewertungsboegen_pdf`
