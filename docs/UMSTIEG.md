# Umstieg von der LibreOffice-Datei

Diese Anleitung ist für Vereine, die ihre Prüfungen bisher mit der LibreOffice-Datei
**„SHS Prüfungsprogramm“** und den Serienbrief-Vorlagen für die Bewertungsbögen organisieren.

**Kurz gesagt:** Die Regeln bleiben gleich, der Ablauf wird einfacher. Du arbeitest nicht mehr
in Tabellenblättern und Formeln, sondern in Reitern mit Eingabemasken. Die Bewertungsbögen
entstehen direkt aus dem Programm, ohne Serienbrief.

## Was gleich bleibt

- **Wertnoten und Punktgrenzen** wurden 1:1 aus der Tabelle „Hilfstabelle Wertnote“
  übernommen:

  | Wertnote | Einzeldisziplin (ED, max. 100) | Dreikampf (DK, max. 300) |
  |---|---|---|
  | Vorzüglich (V) | ab 96 | ab 286 |
  | Sehr gut (SG) | ab 90 | ab 270 |
  | Gut (G) | ab 80 | ab 240 |
  | Befriedigend (B) | ab 70 | ab 210 |

- **Bestanden** ist nur, wer in **jeder** Disziplin mindestens 70 Punkte erreicht, bei DK
  also in allen drei. Sonst lautet das Ergebnis „nicht bestanden“ (nB), unabhängig von der
  Gesamtpunktzahl. Das entspricht genau der Formel in der alten Datei.
- **Rangliste** je Leistungsklasse wie bisher: Punktgleiche erhalten denselben Platz,
  „nicht bestanden“ bekommt keinen Platz, zählt aber bei der Anzahl der Starter mit.
- **Druckausgaben** wie Etiketten, Ergebnisliste und Statistik sind den bekannten Vorlagen
  nachgebaut. Der Bewertungsbogen hat denselben Aufbau wie die bisherigen Serienbrief-Vorlagen.

## Was sich ändert

| Bisher (LibreOffice) | Jetzt (SHS-Prüfungsprogramm) |
|---|---|
| Eine `.ods`-Datei je Termin kopieren und selbst verwalten | **Terminübersicht beim Start:** Termin anlegen, öffnen, löschen. Das Programm verwaltet die Dateien selbst. |
| „Mein Verein_Veranstaltung“ | Beim Anlegen des Termins bzw. Reiter **„Verwaltung“** → „Veranstaltungsdaten bearbeiten…“ |
| „Prüfungsteilnehmer“ (Stammdaten) | Reiter **„Teilnehmer“** mit Eingabemaske und Pflichtfeld-Prüfung |
| „Prüfungsteilnehmer“ (Punkte eintragen) | Reiter **„Ergebniserfassung“**, eine Zeile je Teilnehmer |
| „Übersicht Teilnehmer & LK“ | Reiter **„Übersicht“**, inklusive Bedarf an Leistungsrichtern |
| „Hilfstabelle Rankingliste“ | Reiter **„Auswertung“**, wird automatisch berechnet |
| „Statistikblatt 1+2“ | Reiter **„Export“** → Statistik (PDF) |
| „Druck_LU“, „Ergebnisliste für Verein“ | Reiter **„Export“** → Etiketten bzw. Ergebnisliste (PDF) |
| „Übertrag für Serienbriefe“ → `SHS Bewertungsbögen_Serienbrief.ods` → 12 Serienbrief-Vorlagen | Reiter **„Export“** → Bewertungsbögen (PDF). **Kein Kopieren und kein Serienbrief mehr.** |
| „Zeitplan“ (von Hand gepflegte Liste) | Reiter **„Zeitplan“**: Planung je Leistungsrichter mit automatischem Vorschlag, Zeiten werden berechnet |
| Datei selbst kopieren/sichern | Reiter **„Datensicherung“**: alle Termine als eine ZIP-Datei, auf Wunsch mit Passwort |

So sieht ein Bewertungsbogen aus, den das Programm direkt erzeugt, ohne Serienbrief:

<img src="bilder/bewertungsbogen.png" alt="Bewertungsbogen ED, Leistungsklasse 3, Trümmerfeld" width="480">

**Neu hinzugekommen:**

- Teilnehmer aus einem früheren Termin übernehmen (Reiter „Teilnehmer“ → „Aus anderem
  Termin importieren…“). Wer regelmäßig startet, muss nicht jedes Mal neu erfasst werden.
- Meldeformulare mit Hilfe einer KI einlesen (Reiter „Formular-Import“).
- Disqualifikation und Abbruch werden in der Ergebniserfassung eigens erfasst.
- Ergebniseingabe durch mehrere Richter gleichzeitig im Browser (optional, siehe
  [README_CONTAINER.md](../README_CONTAINER.md)).

**Weggefallen:** Ein Export zurück in eine Tabellenkalkulation (`.ods`/`.xlsx`) gibt es nicht.
Alle Ausgaben entstehen als PDF.

## Was mit deinen alten Daten passiert

Frühere Termine aus der LibreOffice-Datei werden **nicht** automatisch übernommen. Das ist
eine bewusste Entscheidung aus Datenschutzgründen: Teilnehmerdaten vergangener Prüfungen
sollen nicht ungeprüft mitwandern.

- **Alte `.ods`-Dateien** kannst du weiterhin mit LibreOffice öffnen, zum Nachschauen oder
  für Nachfragen. Löschen, sobald sie nicht mehr gebraucht werden.
- **Für einen neuen Termin** erfasst du die Teilnehmer im Programm: von Hand, über den
  Formular-Import aus den Meldeformularen oder ab dem zweiten Termin per Übernahme aus dem
  vorherigen.

## Empfohlener Umstieg in 5 Schritten

1. **Installieren:** Setup-Datei von der
   [Release-Seite](https://github.com/mbruver-source/SHS/releases/latest) laden und
   ausführen. Bei der Windows-Warnung „Weitere Informationen“ → „Trotzdem ausführen“.
2. **Probelauf mit einem vergangenen Termin:** Lege einen Testtermin an und trage einige
   Teilnehmer mit den Punkten einer bereits ausgewerteten Prüfung ein. Vergleiche Wertnoten
   und Rangliste mit der alten Datei. So siehst du selbst, dass die Ergebnisse
   übereinstimmen, und lernst das Programm ohne Zeitdruck kennen. Den Testtermin danach
   löschen.
3. **Druck testen:** Einen Bewertungsbogen und die Etiketten auf echtem Papier bzw.
   Klebeetiketten ausdrucken und prüfen, ob alles passt, bevor es am Prüfungstag darauf
   ankommt.
4. **Ersten echten Termin anlegen:** Veranstaltungsdaten eintragen, Teilnehmer erfassen,
   Zeitplan erstellen, Bewertungsbögen drucken.
5. **Am Prüfungstag:** Ergebnisse im Reiter „Ergebniserfassung“ eintragen und regelmäßig auf
   „Alle Ergebnisse speichern“ klicken. Danach Ergebnisliste, Etiketten und Statistik im
   Reiter „Export“ erzeugen. Zum Schluss eine **Datensicherung** erstellen.

Wenn du beim ersten echten Termin auf Nummer sicher gehen willst: Die alte Datei parallel
bereithalten. Nötig sollte das nicht sein.

## Häufige Fragen

**Brauche ich am Prüfungstag Internet?**
Nein. Das Programm arbeitet vollständig offline. Internet brauchst du nur für die
Update-Suche und für den (optionalen) Formular-Import per KI.

**Kann ich das Programm auf mehreren Rechnern nutzen?**
Ja. Übertragen kannst du die Termine über den Reiter „Datensicherung“: auf Rechner A eine
Sicherung erstellen, auf Rechner B wiederherstellen. Gleichzeitig am selben Termin arbeiten
geht mit der Desktop-App nicht, dafür gibt es die optionale Web-Version.

**Wo liegen meine Daten?**
Im Ordner `SHS-Pruefungsprogramm\Termine` in deinem Benutzerprofil
(z. B. `C:\Users\<Name>\SHS-Pruefungsprogramm\Termine`), eine Datei je Termin. Updates des
Programms lassen diesen Ordner unberührt.

**Was, wenn sich die Prüfungsordnung ändert?**
Die Punktgrenzen sind zentral an einer Stelle im Programm hinterlegt und lassen sich bei
Bedarf mit einem Update anpassen. Melde Änderungen bitte über die
[Issues](https://github.com/mbruver-source/SHS/issues).

**Wo finde ich Hilfe zur Bedienung?**
Im Programm oben über den Button **„Hilfe“**, mit einem Abschnitt je Reiter.

**Ich habe einen Fehler gefunden oder einen Wunsch.**
Bitte über die [Issues](https://github.com/mbruver-source/SHS/issues) melden, mit der
Programmversion (Button „Version“) und ohne echte Teilnehmerdaten.
