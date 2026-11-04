# ToDo-Liste „Note 1 bei allen Personas“ (04.11.2026)

Marcos Auftrag vom 03.11.2026 (Aufgabe A13): Was muss sich noch ändern, damit alle sechs
Personas das Programm mit **1** bewerten? Grundlage sind alle Einzelberichte des ersten Tests
(`personas/E-A … L-B`), der Nachtest (`Nachtest.md`, `personas/L-B2`, `N-B2`) und die
Abschluss-QS. **Nichts davon ist umgesetzt** – die Liste dient zur Besprechung.

## Stand und Abstand zur 1

| Persona | Gesamt 1. Test | Nachtest | Was fehlt vor allem zur 1 |
|---|---|---|---|
| Heinz (E-A) | 2 | – | Pause im automatischen Verteilen (T1), Abbruch-Spalte (T3), echtes Zurück in der Demo (T12) |
| Sabine (E-B) | 2 | – | Punkte sofort beim Tippen prüfen (T4), Hilfe mit Suche bzw. je Reiter (T8) |
| Julia (N-A) | 2 | – | einheitliche Prüfungsnamen bzw. eine Auswahl „Prüfung“ (T5) |
| Tobias (N-B) | 2 | 2 (eher 1–2) | Ablehnungen nachlesbar (T2), Warnung ohne Meldestelle (T7), mehrere Gegenstände in einem Feld (T6) |
| Gerda (L-A) | 2–3 | – | Installation (T13), gesperrte Felder/Auswahlzellen eindeutiger (weitgehend erledigt, Nachtest nötig) |
| Werner (L-B) | 2– | 2 | Zeitplan-Bestätigung (T1), Erfassung: Status/Zählung (T3), Update-Weg und Fachwörter (T9), Sicherung (T10), Installation (T13) |

Heinz, Sabine, Julia und Gerda wurden nur im ersten Test befragt. Viele ihrer Wünsche sind
inzwischen umgesetzt (Schrift, Pause, Abbruch-Feld, Erklärungen). Ein Nachtest mit ihnen würde
zeigen, wie nah sie schon an der 1 sind (T15).

## ToDos (nach Wirkung sortiert)

| Nr | ToDo | Personas | Größe | Entscheidung nötig? |
|---|---|---|---|---|
| T1 | **Zeitplan:** nach „Automatisch verteilen…“ ausdrücklich bestätigen: „Keine Überschneidungen, alle Starts eingeplant“. Im Verteilen-Dialog optional eine Mittagspause angeben, die beim Neu-Verteilen erhalten bleibt | E-A, N-A, L-B2 | M | ja – Pause im Verteilen-Dialog ist neu |
| T2 | **Import-Ablehnungen dauerhaft nachlesbar:** Im Reiter „Formular-Import“ einen Bereich „Letzter Import“ mit der vollständigen Liste (abgelehnt, bereits vorhanden, Hinweise) und „Kopieren“; bleibt bis zum nächsten Import | N-B, N-B2 | M | nein |
| T3 | **Ergebniserfassung:** Spalte „Status“ zeigt „disqualifiziert“ bzw. „Abbruch: Verletzung Hund“; die Speichermeldung zählt Teilnehmer statt Disziplinen („16 Teilnehmer gespeichert“); Abbruch-Spalte am echten Gerät auf Breite prüfen | E-A, L-B2 | S | nein |
| T4 | **Punkte sofort prüfen:** Werte über dem Maximum schon beim Tippen ablehnen bzw. sofort mit Text markieren (statt erst beim Übernehmen) | E-B | S | ja – berührt das akzeptierte Restrisiko C24 |
| T5 | **Teilnehmerformular:** eine Auswahlliste „Prüfung“ mit den angebotenen Prüfungen in der Schreibweise des Termins statt Art/LK/Disziplin; Prüfungsnamen überall einheitlich | L-B, N-A | L | ja – Alternative zu R2 |
| T6 | **ED, mehrere Gegenstände in einem Feld:** Komma/„und“ in Gegenstand 1 erkennen und nachfragen | N-B2, E-B | S | nein |
| T7 | **Anmeldeformular ohne Meldestelle:** beim Erzeugen des Formulars noch einmal warnen; Vorgabe der Rückfrage beim Termin-Anlegen auf „Nein“ | N-B2 | S | ja – Vorgabe ändern |
| T8 | **Hilfe:** Suchfeld und F1 bzw. „?“ öffnet den Abschnitt des aktuellen Reiters | E-B, N-B2 | M | nein |
| T9 | **Version/Updates:** Menüpunkt „Hilfe → Nach Updates suchen“; Diagnose- und Protokoll-Knöpfe im Versionsfenster in einen Bereich „Für Fehlermeldungen“ verschieben; Enter-Verhalten am Gerät prüfen (Nachtest: Enter öffnete „Lizenzen“) | L-B, L-B2, N-B2 | S | nein |
| T10 | **Datensicherung:** Text „auf Wunsch mit Passwort“ statt „.zip … Passwort getrennt aufbewahren“ | L-B2 | S | nein |
| T11 | **Name der Sicherungsdatei:** z. B. `SHS-Sicherung_2026-11-14_alle-Termine.zip` | N-B, N-B2 | S | ja – bisher bewusst gelassen |
| T12 | **Demo mit echtem Zurück** (Schritt zurückspielen) | E-A | L | ja – R4 hatte „nur Text zurück“ gewählt |
| T13 | **Installation für Laien:** Die Browser- und SmartScreen-Warnungen verschwinden nur mit Code-Signatur. Alternativen: Verteilung über den Microsoft Store oder winget (eigene Signatur dort), oder eine bebilderte Kurzanleitung als PDF zum Ausdrucken | L-A, L-B | L | ja – B8, mit dem Installer derzeit nicht lösbar |
| T14 | **Kleinigkeiten aus der QS (R7):** Stilpunkte der Wartbarkeits-QS; Web- und Postgres-Übersicht zählt noch alle Gemeldeten; die Demo zeigt die Angebotsmarkierung nicht | – | S | ja – R7 |
| T15 | **Nachtest mit Heinz, Sabine, Julia und Gerda** nach T1–T10 | alle | L | – |

## Einschätzung

- **Erfahrene und Normale (Heinz, Sabine, Julia, Tobias):** Mit T1–T4, T6 und T8 ist eine 1
  realistisch. Tobias liegt schon bei „eher 1–2“.
- **Laien (Gerda, Werner):** Der Termin-Ablauf kann mit T1, T3, T9 und T10 eine 1–2 erreichen.
  Die **Installation** bleibt ohne T13 (Signatur bzw. Store) bei 3. Eine glatte Gesamt-1 ist für
  Laien deshalb nur mit einer Lösung für T13 zu erwarten.
- **Empfohlene Reihenfolge:**
  1. T3, T6, T9, T10 (klein, ohne Entscheidung);
  2. T2 und T8;
  3. die Entscheidungen zu T1, T4, T5, T7, T11, T12;
  4. danach der Nachtest T15.
