---
name: desktop-pruefung
description: Kritische Prüfung der Desktopversion des SHS-Prüfungsprogramms in 10 einzeln startbaren Teilen (Agenten-Typ desktop-pruefer, Opus 5.5, Effort hoch, mit Gegenprüfung). Aufruf /desktop-pruefung <Nr> für einen Teil, ohne Nummer für den Stand.
---

# Desktop-Prüfung in Teilen

Die Desktopversion wird nach Funktionsbereichen in 10 Teilen geprüft. Jeder Teil wird einzeln
gestartet, damit ein Lauf gründlich bleibt. Den Prüfer stellt der Agenten-Typ `desktop-pruefer`
(`.claude/agents/desktop-pruefer.md`).

Berichtsordner: `_unveroeffentlicht/desktop-pruefung/` (per `.gitignore` ausgeschlossen, siehe
CLAUDE.md "Sicherheitsfunde erst nach dem Release veröffentlichen").

## Aufruf

- `/desktop-pruefung <Nr>`: Teil Nr. 1 bis 10 prüfen (Ablauf unten).
- `/desktop-pruefung` ohne Nummer oder mit `uebersicht`: `uebersicht.md` im Berichtsordner
  lesen, den Stand aller Teile zeigen und den nächsten offenen Teil vorschlagen. Fehlt die
  Datei, ist noch kein Teil geprüft.

## Teilekatalog

Zeilenangaben sind ungefähr (Stand 1.0.47). Maßgeblich sind die Klassen- und Funktionsnamen.
Abkürzungen: `dlg` = `desktop_dialoge.py`, `gem` = `desktop_gemeinsam.py`.

| Teil | Bereich | Code | Bezug und Tests |
|---|---|---|---|
| 1 | Teilnehmerliste | `app.py` Hilfen Z. 235–330 (`_pruefung_bezeichnung`, `_fehlende_startnummern_vergeben_mit_meldung`, `_startnummern_nach_import_anbieten`, `_teilnehmerliste_importieren`, `_klartext_tooltip`), `TeilnehmerTab`; dlg `StartnummerTauschenDialog`, `TerminImportDialog` | db Teilnehmer- und Startnummernfunktionen, `db_import.importiere_teilnehmer_stammdaten`; `test_app_gui.py`, `test_db.py` (`TestDatenbank`, `TestTerminImportStammdaten`) |
| 2 | Teilnehmer-Dialog und Veranstaltung | dlg `TeilnehmerDialog`, `VeranstaltungsDialog`; `app.py` `VerwaltungTab`; gem `_aktualisiere_veranstaltung_feld`, Feld- und Tabellenhelfer (Z. 355–459, ohne die Ergebnis-Spaltenkonstanten) | db Veranstaltung, Startnummernbereiche, Datumsfunktionen; `test_db.py` (`TestPruefungsangebote`, `TestDatumsfelder`) |
| 3 | Ergebniserfassung | `app.py` `_punkte_validator`, `ErgebnisTab`; gem `_responsive_schriftgroesse`, `_ergebnis_spaltenbreiten_verteilen`, `ResponsiveSchriftMixin`, Ergebnis-Spaltenkonstanten (`_ERGEBNIS_SPALTEN_JE_DISZIPLIN`, `_DQ_SPALTE`, `_ABBRUCH_SPALTE`, `_STATUS_SPALTE`) | db Ergebnisfunktionen, `shs_core.py`; `test_app_gui.py`, `test_shs_core.py` |
| 4 | Auswertung, Übersicht und Zeitplan | `app.py` `_fremdobjekte_melden`, `_vorname_nachname`, `_stechen_offen_bestaetigen`, `AuswertungTab`, `TeilnehmerUebersichtTab`, `ZeitplanTab`; dlg `PruefungsblockDialog`, `PauseDialog`; gem `_zeitplan_pdf_exportieren` | db Auswertung und Zeitplan, `shs_core.py`; `test_db.py` (`TestZeitplan`), `test_bewertung_referenz.py` |
| 5 | Import | `app.py` `_formular_import_prompt`, `FormularImportTab`; gem `_import_startordner`, `_import_ordner_merken`; `db_import.py` (Importfunktionen) | `test_db.py` (`TestCsvMeldungen`, `TestAnmeldeformularImport`) |
| 6 | Export und PDF | `app.py` `ExportTab`; dlg `BewertungsbogenAuswahlDialog`; gem `_Ablageort`, `_export_dateiname`, `_ausdrucke_ordner`, `_pfad_anzeige`, `_ordner_zeigen`, `_pdf_speicherort_waehlen`, `_datei_gespeichert_melden`, `_pdf_export_fehler_anzeigen`; `pdf_export.py` aus Sicht der Desktopaufrufe; `db_import.exportiere_teilnehmer_csv` | `test_pdf_export.py` |
| 7 | Datensicherung, Start und Termine | `app.py` `DatensicherungTab` (mit Wiederherstellung und Konfliktabfrage), `StartDialog`, `_startdialog_schleife`, `HauptFenster._termin_setzen`/`_termin_wechseln`; dlg `SicherungErstellenDialog`, `_wiederherstellungsziele_planen`; `db_sicherung.py` | `test_backup.py`, `test_altversionen.py`, `test_db.py` (`TestTerminuebersicht`) |
| 8 | Hauptfenster, Lebenszyklus, Version und Update | `app.py` Kopf Z. 1–234, `HauptFenster` (Reiteraufbau, Menüs, Tabwechsel, `closeEvent`), `SitzungsendeFilter`, `laufkennung_setzen`, `sitzungsende_einrichten`, `_version_tupel`, `_neueste_version_pruefen`, `VersionDialog`, `main()`; `selbsttest.py` | `test_app_gui.py` (Schließen, Sitzungsende, Mutex, Selbsttest) |
| 9 | Darstellung, Hilfe und Fehlerbehandlung | `desktop_darstellung.py`; dlg `HilfeDialog`; gem `_fehler_anzeigen`, `_db_fehler_anzeigen`, Übersetzung/Qt-Texte, `programmsymbol*`, `meldungsfenster_als_klartext`, Absturzprotokoll, `_kurzpfad`, `_ohne_benutzerpfad`, `diagnose_text`, `_fehlerbild`, Fehlerfenster | `test_theme.py`, `test_app_gui.py` (Fehlerfenster, Diagnose) |
| 10 | Demoprüfung | `desktop_demo.py`, `demo_daten.py`; `app.py` `_demo_starten`, `_demo_sperren`, `StartDialog._demo_waehlen` | `test_app_gui.py` (Demo), `test_db.py` (`TestDemoDaten`) |

## Ablauf für einen Teil

Lege eine kurze Aufgabenliste an und arbeite sie ab.

1. **Prüfen:** Agent `desktop-pruefer` starten. Der Auftrag enthält: "Prüfmodus", Nummer und
   Bereich des Teils, die Code- und Testangaben aus dem Katalog in vollem Wortlaut und die
   Bitte um eine nummerierte Befundliste nach den Regeln des Agenten. Nur einen Agenten
   gleichzeitig laufen lassen.
2. **Gegenprüfen:** Hat der Prüfer Befunde gemeldet, einen zweiten `desktop-pruefer` im
   Gegenprüf-Modus starten. Er bekommt die vollständige Befundliste und prüft jeden Befund.
   Ohne Befunde entfällt der Schritt.
3. **Bericht:** `_unveroeffentlicht/desktop-pruefung/teil-NN.md` schreiben (NN zweistellig):
   - Kopf mit Teil, Bereich, Datum und Commit (`git rev-parse --short HEAD`);
   - bestätigte Befunde nach Schweregrad, mit allen Angaben des Prüfers und dem Urteil der
     Gegenprüfung (bei geändertem Schweregrad den neuen verwenden);
   - verworfene Befunde nur kurz, mit Begründung.

   Danach `uebersicht.md` im selben Ordner aktualisieren oder anlegen. Sie enthält eine Tabelle
   mit allen 10 Teilen: Status (offen/geprüft), Datum, Commit, Anzahl bestätigter Befunde je
   Schweregrad und Bearbeitungsstand mit Marco.
4. **Melden:** Marco die bestätigten Befunde knapp zusammenfassen (wichtigste zuerst) und
   den Bericht nennen. Jeder Befund wird einzeln mit ihm besprochen. Code wird erst nach
   seinem ausdrücklichen Go geändert, auch nicht "nebenbei".
5. **Fortschritt.md:** Nur allgemein vermerken, z. B. "Desktop-Prüfung Teil 3
   (Ergebniserfassung) durchgeführt, 5 bestätigte Befunde, Bericht unveröffentlicht".
   Bei Sicherheitsfunden keine betroffene Stelle, keinen Angriffsweg und keine Nachstellung
   nennen. Diese Dokumentationsänderung darf committet werden. Der Berichtsordner wird nicht
   committet.

## Hinweise

- Bricht ein Agent wegen eines Limits ab, fortsetzen (SendMessage an denselben Agenten)
  statt neu starten.
- Liegt zwischen zwei Teilen ein neuer Release, gilt der Katalog weiter. Zeilenangaben können
  sich verschieben, die Namen bleiben maßgeblich. Wird ein Bereich umgebaut, den Katalog hier
  nachziehen.
- Teile, die schon geprüft sind, nur nach Rückfrage bei Marco erneut prüfen und den alten
  Bericht dann nicht überschreiben, sondern mit Datum ergänzen.
