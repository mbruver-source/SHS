# B14: Marke `langsam` in `conftest.py` ist an keinem Test angebracht

- **Status:** erledigt (11.11.2026)
- **Bereich:** B. Bewusst zurückgestellt (Marcos Entscheidung)
- **Datum:** 10.11.2026

## Entscheidung

Marke `langsam` in `conftest.py` war an keinem Test angebracht.

**Erledigt 11.11.2026:** Nach der Aufteilung der GUI-Tests gemessen: nur zwei Tests brauchen über 10 Sekunden und tragen jetzt die Marke (`test_ergebnistabelle_sehr_gross_nur_maximiert_voll`, `test_screenshot_skript_erzeugt_alle_bilder`). `pytest -m "not langsam"` lässt sie aus.

## Fundstellen

- `Fortschritt.md`, Abschnitt „10.11.2026: Automatische Kopie des Termins und Hinweis bei USB-Stick/Netzlaufwerk“

Neue Entscheidungen bitte nach `entscheidungen/VORLAGE.md` anlegen und in `OFFEN.md` eintragen.
