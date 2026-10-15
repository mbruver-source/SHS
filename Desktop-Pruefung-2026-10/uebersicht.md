# Desktop-Prüfung: Übersicht

Start mit `/desktop-pruefung <Nr>`. Katalog und Ablauf stehen in
`.claude/skills/desktop-pruefung/SKILL.md`.

| Teil | Bereich | Status | Datum | Commit | hoch | mittel | niedrig | optional | Umsetzung |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Teilnehmerliste | geprüft | 13.10.2026 | 25f9572 | 0 | 1 | 5 | 2 | abgearbeitet |
| 2 | Teilnehmer-Dialog und Veranstaltung | geprüft | 14.10.2026 | 485f258 | 0 | 0 | 7 | 8 | abgearbeitet |
| 3 | Ergebniserfassung | geprüft | 14.10.2026 | 6557190 | 0 | 2 | 3 | 4 | abgearbeitet |
| 4 | Auswertung, Übersicht und Zeitplan | geprüft | 14.10.2026 | 3d14c51 | 0 | 0 | 5 | 4 | abgearbeitet |
| 5 | Import | geprüft | 14.10.2026 | 87ea7e2 | 0 | 1 | 2 | 6 | abgearbeitet |
| 6 | Export und PDF | geprüft | 14.10.2026 | 0d65aff | 0 | 1 (Sicherheit) | 4 | 7 | abgearbeitet |
| 7 | Datensicherung, Start und Termine | geprüft | 14.10.2026 | 04881ed | 0 | 0 | 6 (1 Sicherheit) | 6 | abgearbeitet |
| 8 | Hauptfenster, Lebenszyklus, Version und Update | geprüft | 14.10.2026 | 0aa00df | 0 | 0 | 2 | 8 | abgearbeitet |
| 9 | Darstellung, Hilfe und Fehlerbehandlung | geprüft | 14.10.2026 | d903ee0 | 1 | 1 | 3 (1 Sicherheit) | 7 | abgearbeitet |
| 10 | Demoprüfung | geprüft | 14.10.2026 | 17f9176 | 0 | 1 | 6 | 4 | abgearbeitet |

Alle 10 Teile sind geprüft. Einziger Befund mit Schweregrad „hoch“: Teil 9 Nr. 1 (Design „Hell“
bei dunklem System-Farbschema unlesbar; hebt die Festlegung Fortschritt.md:1805f. auf).

## Sicherheitsbefunde (behoben, bis zum Release nur allgemein erwähnen)

- **Teil 6 Nr. 1** (mittel): Rest von S-4 in der PDF-Erzeugung; Teil 2 Nr. 8b geht darin auf.
- **Teil 7 Nr. 3** (niedrig, Verfügbarkeit): Startliste der Termine.
- **Teil 9 Nr. 3** (niedrig): Häkchen-Bild der Darstellung (nur Linux-Vorschau bzw. umgelegter
  Temp-Ordner).
- Weg zu beiden: fremde Termin-Dateien bzw. Sicherungen. Zweite Absicherung für Teil 6 Nr. 1:
  Plausibilitätsprüfung beim Öffnen (Teil 7, Einordnung).

## Vorgemerkte Hinweise (alle erledigt)

- Teil 8: `_termin_setzen` bleibt bei Teil 7 Nr. 4/9 gezählt; Titel „None ()“ ist Teil 8 Nr. 3;
  `_tab_gewechselt` während der Demo ohne Befund.
- Teil 9: Duplikatsperre bewusst zurückgestellt (Fortschritt.md 13.10.2026), kein Befund;
  `PermissionError` einheitlich = Teil 9 Nr. 6; Fehler in `main` = Teil 9 Nr. 7; `openUrl` =
  Teil 9 Nr. 10; Demo-Fehler im Protokoll bleibt Teil 10 Nr. 6 (Hilfsfunktion aus Teil 9 Nr. 5).

Hinweis Teil 10: als Cloud-Probelauf geplant, die Cloud-Ausführung griff nicht, beide Läufe
liefen lokal.

## Zusammen umsetzen

- **Schreibfehler/Rollback:** Teil 1 Nr. 7, Teil 3 Nr. 1, Teil 4 Nr. 4 und 5, Import-Stellen aus
  Teil 5; Schreibschutz beim Öffnen erkennen (Teil 7 Nr. 4, Schreibprobe `PRAGMA user_version`).
- **Öffnen fremder Dateien:** Teil 7 Nr. 4 (Öffnen absichern), Teil 7 Nr. 3 und 6
  (`liste_termine`, betrifft auch den Termin-Import-Dialog), Teil 1 Nr. 2 (Quelle beim
  Termin-Import schreibgeschützt öffnen, bestätigt in Teil 5).
- **Unbegrenzte Namenslisten:** Teil 1 Nr. 4 bei CSV-, OMA- und PDF-Import (Teil 5 Nr. 5).
- **Excel und Nummern:** Teil 5 Nr. 1 und der Export-Weg (Teil 6, Einordnung; Hinweis in Meldung
  und Handbuch, ggf. xlsx-Export); dazu Teil 6 Nr. 3 (Telefonnummern).
- **Sortierung:** Teil 3 Nr. 4 und Teil 6 Nr. 5 mit gemeinsamem Sortierschlüssel.
- **Liegengebliebene Dialoge:** Teil 2 Nr. 9, Teil 6 Nr. 8, Teil 7 (Start-, Sicherungs- und
  Konfliktdialog; Sicherungspasswort bleibt im Feld stehen), Teil 8 (`VersionDialog`,
  `HilfeDialog`, Boxen aus `meldungsfenster_als_klartext`) mit `deleteLater()`.
- **Fenstertitel:** Teil 2 Nr. 5 (Titel nach Bearbeiten) und Teil 8 Nr. 3 (Titel „None ()“) mit
  `_titel_aktualisieren()`, beim Umbau von `_termin_setzen` (Teil 7 Nr. 4/9).
- **Rückfrage ungespeicherte Änderungen:** Teil 8 Nr. 2 und Teil 10 Nr. 8 mit gemeinsamer
  Hilfsfunktion (Speichern/Verwerfen/Abbrechen).
- **Fehlerprotokoll und Klartext:** Teil 9 Nr. 5 (`fehler_protokollieren`), Nr. 6
  (`_klartext_fehler`), Nr. 4 und 8 (Rotation, Qt-Warnungen) mit Teil 10 Nr. 6 und den
  Einzelstellen aus Teil 5 Nr. 4, Teil 6 (CSV), Teil 7 (Sicherungs-ZIP).
- **Stylesheet:** Teil 9 Nr. 1, 2, 9 mit Parse-/Paletten-Tests (Nr. 12).
- **Mac-Rückmeldungstest:** Update-Prüfung auf CA-Zertifikate prüfen (Teil 8 Nr. 5).
- **Wartecursor:** Teil 6 Nr. 7, auch für Sicherung und Wiederherstellung (Teil 7).

## Entscheidungen offen

- Umgang mit nicht angebotenen Prüfungen beim Import aus einem anderen Termin und bei der
  Erfassung von Hand (Teil 1 Nr. 6; Teil 2 Nr. 13).
- Stechen bei gewachsener Gleichstandsgruppe (Teil 4 Nr. 1).
- „'“ vor Telefonnummern im CSV-Export (Teil 6 Nr. 3).

## Abarbeitung (14./15.10.2026, abgeschlossen)

Alle Befunde sind nach Marcos Entscheidungen in den Aufgaben A1–A19c abgearbeitet und lokal
committet (Liste mit Commits, Verbrauch und Restpunkten: `aufgaben.md`). Die drei
Sicherheitsbefunde sind behoben; die Abschluss-QS (`qs-sicherheit`) bestätigt das und fand einen
weiteren, niedrig eingestuften Punkt (A19a, behoben). `qs-korrektheit` fand drei Wechselwirkungen
zwischen den Aufgaben (A19b, behoben), `qs-wartbarkeit` nur Stilpunkte (A19c; größere Umbauten
zurückgestellt, siehe Fortschritt.md). Nicht gepusht - die Tests der Sicherheitsbefunde gehen erst
mit dem Release online.
