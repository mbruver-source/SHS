# B12: `app.py` nicht weiter aufteilen **Überholt am 11.11.2026

- **Status:** überholt
- **Bereich:** B. Bewusst zurückgestellt (Marcos Entscheidung)
- **Datum:** 18.10.2026

## Entscheidung

`app.py` nicht weiter aufteilen **Überholt am 11.11.2026 (Marco):** Teilnehmer-, Formular-Import- und Ergebnis-Reiter liegen jetzt in `desktop_teilnehmer.py`, `desktop_formular.py`, `desktop_ergebnis.py`; `app.py` hat nur noch Hauptfenster, StartDialog und `main`. Weitere Zerlegung der großen Klassen (`ErgebnisTab`, `TeilnehmerTab`, `DemoTour`) und von `db.py` ist der nächste Schritt (Entscheidung steht aus)

## Fundstellen

- Fortschritt.md (11.11.2026, Code-Struktur)

Neue Entscheidungen bitte nach `entscheidungen/VORLAGE.md` anlegen und in `OFFEN.md` eintragen.
