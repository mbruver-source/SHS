# Grobkonzept: Ablösung des SHS-Prüfungsprogramms durch eine eigene Anwendung

Stand: 10.09.2026
Grundlage: Analyse von `SHS Prüfungsprogramm_V2026.ods` (13 Tabellenblätter, 86.574 Zellen, 64.242 Formeln), `SHS Bewertungsbögen_Serienbrief.ods` (Datenquelle für den Seriendruck) sowie der 12 zugehörigen Serienbrief-Vorlagen (.odt, je eine pro Leistungsklasse/Disziplin-Kombination)

## 1. Ausgangslage

Das bestehende Prüfungsprogramm ist eine LibreOffice-Calc-Datei zur Verwaltung von Spürhundsport-Prüfungen (SHS) für einen Verein. Es deckt den gesamten Ablauf ab: Teilnehmer anlegen, Ergebnisse je Disziplin (Trümmerfeld, Flächensuche, Behältnisstrecke) eintragen, Wertnoten und Rangliste automatisch berechnen, Statistiken führen, Druckausgaben und Serienbriefdaten erzeugen.

Die Analyse zeigt: Die Geschäftslogik ist inhaltlich klein und klar (nur 10 unterschiedliche Formelfunktionen, keine Makros), wurde aber tausendfach als nahezu identische Formel pro Zeile dupliziert – u. a. 25.200 Formeln allein für die Rangbildung und 28.804 für die Statistik. Das macht die Datei schwer wartbar (eine Regeländerung muss in hunderten Zellen nachgezogen werden), fehleranfällig bei manueller Bearbeitung und für mehrere gleichzeitige Bearbeiter (z. B. am Prüfungstag) ungeeignet.

Ziel dieses Grobkonzepts ist, den fachlichen Inhalt der Tabelle in eine wartbare Anwendung zu überführen, ohne den bewährten Ablauf für die Vereinsmitglieder zu verändern.

## 2. Fachliche Entitäten (aus den Tabellenblättern abgeleitet)

| Entität | Herkunft im Original | Wesentliche Felder |
|---|---|---|
| Verein/Veranstaltung | "Mein Verein_Veranstaltung" | Vereinsname, Ort, Datum der Prüfung |
| Teilnehmer | "Prüfungsteilnehmer" | Vor-/Nachname Hundeführer, Verein, Zwingername & Rufname Hund, Leistungsklasse (LK 1–3), Disziplin-Kürzel (z. B. ED/DK) |
| Ergebnis je Disziplin | "Prüfungsteilnehmer", "Übersicht Teilnehmer & LK" | Punkte Trümmerfeld, Flächensuche, Behältnisstrecke |
| Wertnoten-Schwellenwerte | "Hilfstabelle Wertnote" | Punktbereich → Note (vorzüglich/sehr gut/gut/befriedigend/ungenügend), getrennt nach Einzeldisziplin/Dreikampf |
| Rangliste | "Hilfstabelle Rankingliste" | Platzierung je Leistungsklasse, abgeleitet aus Gesamtpunktzahl |
| Statistik | "Statistikblatt 1+2 von 2 für SHS-R" | Aggregierte Kennzahlen über alle Teilnehmer/Klassen |
| Ausgabedokumente | "Druck_LU", "Übertrag für Serienbriefe", "Ergebnisliste für Verein" | Druckfertige Ergebnislisten, Datenexport für Serienbriefe/Urkunden |
| Zeitplan | "Zeitplan" | Ablaufplan des Prüfungstags |
| Bewertungsbogen | `SHS Bewertungsbögen_Serienbrief.ods` | Je Teilnehmer: Ident-Nummer, Datum, Verein, Name Hundeführer, Zwingername/Rufname Hund, Hündin/Rüde, Schulterhöhe, Chip-Nr., Leistungsklasse, Gegenstand 1–3 (Suchobjekte je Disziplin), Startnummer |

Die Wertnoten-Schwellenwerte sind aktuell **hart in Formeln verdrahtet** (jede IF-Kette enthält die Punktgrenzen direkt). Da sich die Regeln laut Rückmeldung aktuell nicht ändern, reicht es, die Schwellenwerte als einmalig gepflegte, klar benannte Konstanten im Code zu hinterlegen (nicht als editierbare Oberfläche) – das hält die Logik trotzdem an einer Stelle wartbar, ohne unnötige Konfigurationsoberfläche zu bauen.

Der Bewertungsbogen-Workflow läuft heute manuell: Daten werden aus "Übertrag für Serienbriefe" kopiert, in die passende Tabelle von `SHS Bewertungsbögen_Serienbrief.ods` eingefügt und darüber ein Serienbrief-Dokument befüllt. Dieser Zwischenschritt entfällt in der neuen Anwendung vollständig – die Bögen werden direkt aus der Datenbank heraus, gefiltert nach Leistungsklasse/Disziplin, erzeugt.

**Aufbau der Bewertungsbögen (aus den 12 Vorlagen ermittelt):** Jeder Bogen ist ein leeres, vor der Prüfung ausgedrucktes Formular, das der Richter während der Prüfung von Hand ausfüllt (Suchleistung/Anzeigeleistung in Punkten, Position des Gegenstands). Kopf: Titel "Bewertungsbogen SHS – Spürhundsport", Leistungsklasse (ED-LK 1–3 oder DK-LK 1–3), Start-Nummer, Name Hundeführer, Hund (Zwingername/Rufname), Verein, Widerristhöhe, Geschlecht, Chip-Nr., Datum, sowie die zu suchenden Gegenstände 1–3 (Anzahl je nach Leistungsklasse: LK 1 ein Pflichtgegenstand, LK 2 zwei, LK 3 drei). Je Disziplin (Trümmerfeld, Flächensuche, Behältnisstrecke) folgt ein Bewertungsblock mit Suchleistung (max. 60 P.), Anzeigeleistung (max. 40 P.), Punktzahl-Feldern, einem Skizzenfeld "Position Gegenstand" (bei Behältnisstrecke stattdessen 6 nummerierte Kammern) und einer Gesamtpunktzahl-Box; dazu unten eine Wertungsnoten-Referenztabelle (V/SG/G/B/nB mit Punktgrenzen) als Gedächtnisstütze für den Richter. Bei Einzeldisziplin-Bögen (ED) enthält der Bogen nur eine Seite mit dem jeweiligen Disziplin-Block, bei Dreikampf-Bögen (DK) alle drei Disziplinen auf getrennten Seiten. Die 12 Vorlagen unterscheiden sich untereinander nur in Leistungsklasse/Disziplin-Beschriftung und Seitenzahl, nicht im grundsätzlichen Aufbau – die neue Anwendung kann sie daher mit einer einzigen parametrisierten Vorlage (Layout + Disziplin-Block als wiederverwendbare Komponente) abdecken, statt 12 separate Dokumente zu pflegen.

## 3. Rahmenbedingungen (geklärt)

- **Nutzung:** ausschließlich durch die Prüfungsleitung, eine Person, keine gleichzeitige Mehrbenutzer-Eingabe nötig.
- **Wertnoten-Regeln:** ändern sich aktuell nicht – werden als feste Konstanten im Code hinterlegt statt als separat pflegbare Konfigurationsoberfläche.
- **Altdaten:** werden aus Datenschutzgründen nicht übernommen. Die Anwendung muss aber mehrere Termine/Veranstaltungen mit jeweils eigenen, getrennten Datenständen unterstützen.
- **Verteilung:** die Anwendung soll über einen Installer an andere weitergegeben werden können; der Installer soll alle notwendigen Komponenten enthalten (kein separates Python o. Ä. beim Nutzer vorausgesetzt).

## 4. Vorgeschlagene Architektur

**Sprache/Stack:** Python als Grundlage der Logik, aber mit **Desktop-Oberfläche statt Weboberfläche** – da nur eine Person lokal arbeitet und ein sauberer Installer gewünscht ist, ist eine echte Desktop-Anwendung passender als ein lokaler Webserver mit Browser-Umweg. Empfehlung: **PySide6 (Qt für Python)** für die Oberfläche – sehr reife, gut aussehende Tabellen-/Formular-Komponenten, genau richtig für die tabellenlastige Erfassung und Übersichten dieser Anwendung. Dazu `pandas` für Gruppierungen/Rangbildung, `SQLite` als Datenhaltung, `reportlab` oder `weasyprint` für Druckausgaben, Statistik-Reports und die Bewertungsbögen (ersetzt den Serienbrief-Umweg vollständig durch direkte PDF-Erzeugung aus der Datenbank).

**Installer:** Die App wird mit `PyInstaller` zu einer eigenständigen ausführbaren Datei gebündelt (Python-Laufzeit + alle Bibliotheken inklusive), anschließend mit einem Installer-Werkzeug wie **Inno Setup** (Windows) zu einem klassischen Setup-Programm verpackt (Startmenüeintrag, Deinstallation, o. Ä.). Damit deckt der Installer wirklich alle Komponenten ab – ein Vereinsmitglied muss nichts weiter installieren.

**Mehrere Termine/Daten:** Jede Veranstaltung bekommt eine eigene, in sich abgeschlossene SQLite-Datenbankdatei (vergleichbar mit "eine Datei pro Prüfungstermin" heute). Beim Start zeigt die Anwendung eine Übersicht bestehender Termine mit der Möglichkeit, einen neuen anzulegen, einen bestehenden zu öffnen – oder eine Termin-Datei vollständig zu löschen. Letzteres ist wichtig für den Datenschutz: Teilnehmerdaten eines abgeschlossenen Termins lassen sich damit gezielt und vollständig entfernen, ohne andere Termine zu berühren.

**Module:**

1. *Terminverwaltung* – Termine/Veranstaltungen anlegen, öffnen, löschen (neu, ersetzt das bisherige "eine Datei pro Termin manuell verwalten")
2. *Stammdaten* – Verein/Veranstaltung anlegen, Teilnehmer erfassen (ersetzt "Mein Verein_Veranstaltung", "Prüfungsteilnehmer")
3. *Ergebniserfassung* – Punkte je Disziplin eintragen, Wertnote wird automatisch berechnet (ersetzt Formellogik in "Prüfungsteilnehmer")
4. *Auswertung* – Übersicht je Leistungsklasse, Rangliste, Statistik (ersetzt "Übersicht Teilnehmer & LK", "Hilfstabelle Rankingliste", "Statistikblatt 1+2")
5. *Ausgabe* – Druckansicht/PDF für Ergebnislisten und Bewertungsbögen, direkt aus der Datenbank gefiltert nach Leistungsklasse/Disziplin (ersetzt "Druck_LU", "Übertrag für Serienbriefe", "Ergebnisliste für Verein" **und** `SHS Bewertungsbögen_Serienbrief.ods` samt der 12 .odt-Serienbrief-Vorlagen komplett). Die Bewertungsbögen werden dabei als eine parametrisierte HTML/CSS-Vorlage (Rendering über `weasyprint`) gebaut, aus der sich alle 12 Varianten durch Einsetzen von Leistungsklasse, Disziplin(en) und Teilnehmerdaten erzeugen lassen – Layout, Tabellen und die Wertungsnoten-Referenztabelle entsprechen dabei exakt den vorliegenden Originalvorlagen.
6. *Zeitplan-Planung* – ersetzt das Tabellenblatt "Zeitplan" (Zeile 25 oben). Bei der Umsetzung stellte sich heraus, dass dieses Blatt im Original entgegen der ursprünglichen Annahme KEINE eigene Berechnungslogik enthielt, sondern nur eine von Hand erstellte, außerhalb der Tabelle gepflegte Liste anzeigte (Power-Query-Import einer manuell gepflegten CSV-Datei) – der Ablaufplan wurde also komplett manuell geplant, nicht errechnet. Die neue Anwendung bietet stattdessen ein eigenes, neu entworfenes Planungsmodul: beliebig viele Leistungsrichter-Spuren mit frei sortierbarer Abfolge aus Prüfungsblöcken und Pausen, wahlweise per automatischem Verteilungsvorschlag (ausgewogen nach Teilnehmerzahl je Richter) oder komplett von Hand. Details siehe `Fortschritt.md`.

**Migration/Übergang:** Ein Export nach ODS/XLSX bleibt optional möglich (über `openpyxl`/`odfpy`), falls jemand die gewohnte Tabellenansicht zum Ansehen oder Weiterverteilen braucht. Die Datenpflege selbst findet aber vollständig in der neuen Anwendung statt.

## 5. Nächster Schritt

Alle für das Grobkonzept benötigten Unterlagen liegen jetzt vor. Vorschlag: Zunächst einen Prototyp für das Kernstück bauen – Notenberechnung und Rangbildung anhand der Daten aus "Hilfstabelle Wertnote" und "Hilfstabelle Rankingliste" – und gegen ein paar Beispieldatensätze aus der Originaldatei gegenprüfen, um sicherzustellen, dass die Ergebnisse exakt übereinstimmen. Darauf aufbauend die Erfassungsoberfläche, die Terminverwaltung und die Ausgabeformate (Ergebnislisten, Statistik, Bewertungsbögen) ergänzen.

(Fortschritt und Testergebnisse siehe `Fortschritt.md`)
