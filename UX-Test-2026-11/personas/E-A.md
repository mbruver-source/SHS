# UX-Test 2026-11 – Bericht Persona E-A (Heinz, 58)

## 1. Persona und Vorgehen

Heinz ist seit über zehn Jahren Prüfungsleiter. Bisher hat er mit der OMA und Excel gearbeitet. Fachlich kennt er sich bestens aus, am PC ist er routiniert, bei Fleißarbeit aber ungeduldig. Er hat **das Handbuch** (`docs\HANDBUCH.md`) und schlägt gezielt nach, wenn er etwas nicht direkt findet. Genutzt hat er:

- **Handbuch:** Kapitel 2 (Installation/Update), 3 (Startbildschirm, Demo, Termin anlegen), 4 (Teilnehmer, Startnummern, Suchgegenstände), 6 (Zeitplan) und 7 (Ergebniserfassung).
- **Website** `docs\index.html`: Abschnitte Installation und Updates.
- **Hilfe im Programm:** in Aufgabe 15 gelesen.

Bedient hat er das Programm (Version 1.0.55) über das Steuerwerkzeug.

## 2. Aufgaben-Übersicht

| Nr | Aufgabe | Ergebnis | Fehlversuche | Handbuch/Hilfe nötig? | Kommentar |
|---|---|---|---|---|---|
| 0 | Installation (gedanklich) | ✓ | 0 | Website + Handbuch Kap. 2 | SmartScreen- und Browserwarnung gut erklärt. Update-Weg klar („Version …“ → „Nach Updates suchen“). |
| 1 | Erster Start, Demoprüfung | ~ | 2 | nein | Demo sofort gefunden. Drei Schritte (2, 7 Zeitplan, 12 Stechen) sind ihm durch das automatische Weiterschalten durchgerutscht, ein „Zurück“ gibt es nicht. Das Stechen hat er hinterher im Reiter „Auswertung“ nachgesehen. |
| 2 | Termin anlegen | ✓ | 0 (Harness: 3) | Handbuch-Bild bestätigt | „Bereiche automatisch festlegen“ ist sehr gut. Häkchen ließen sich erst per Leertaste setzen (Harness, s. Abschnitt 6). |
| 3 | Anmeldeformular | ✓ | 0 | nein | Reiter „Export“, ein Klick, fertig. Formular enthält nur die angebotenen Prüfungen. |
| 4 | Zwei Nachmeldungen | ✓ | 0 (Harness: 2) | Handbuch „Suchgegenstände“ | Vogel problemlos. Bei Weber (ED LK 2) lässt sich nur ein Gegenstand eintragen, die „Socke“ hat keinen Platz. Die beiden Abstürze beim Tippen von Umlauten lagen an der Testtastatur, s. Abschnitt 6. |
| 5 | Mitgliederliste CSV | ✓ | 0 | nein | 12 übernommen, 8 übersprungen, jeweils mit Namen und Grund. |
| 6 | Vier Anmelde-PDFs | ✓ | 0 | nein | Beide Fehler erkannt: Pfeiffer hat zwei Prüfungen angekreuzt, Quast hat Fläche LK 3 (nicht angeboten). |
| 7 | Startnummern, Tausch, Absage | ✓ | 0 | nein | Abfrage nach dem Import, Tausch mit Strg-Klick, „Keine Teilnahme“: alles in einem Rutsch. |
| 8 | Späte Nachmeldung Ziegler | ✓ | 0 | nein | Häkchen raus, Programm schlägt Nr. 44 vor (nächste freie im Trümmer-LK-1-Bereich). |
| 9 | Zeitplan + Mittagspause + PDF | ~ | 0 (Nachtest nach Harness-Reparatur) | Handbuch Kap. 6 | Automatischer Plan ohne Überschneidungen. Leere Spalte „Richter 4“ über „Richter löschen“ mit Rückfrage entfernt. Mittagspause per „Pause hinzufügen…“ → „Bei allen Richtern einfügen, um 12:00“ eingetragen. Weil der Plan um 10:40 endet, hängt das Programm die Pause ans Ende (10:40–11:25 bzw. 10:20–11:05). So steht es auch im PDF (F4). PDF mit 3 Seiten gespeichert. |
| 10 | Ergebnisse eintragen | ~ | 3 (Harness) | Handbuch Kap. 7 | Disqualifikation, Abbruch mit Grund und die 65 → 48 haben funktioniert. Die Meldung zur 65 ist gut. Die Abbruch-Auswahl ist zu schmal. |
| 11 | Rangliste, Stechen | ✓ | 0 | nein (aus der Demo bekannt) | „Stechen offen“ samt Hinweistext, Dialog mit Klartextnamen, danach „1. von 4 (nach Stechen)“. |
| 12 | PDFs erzeugen | ✓ | 0 | nein | Ergebnisliste enthält „(nach Stechen)“, „Abbruch wegen Verletzung des Hundes (ABBR)“ und „Disqualifiziert (DISQ)“. Bewertungsbögen und Etiketten in Ordnung. |
| 13 | Datensicherung | ✓ | 0 | nein | Verständlich. Der Dateiname führt etwas in die Irre (s. F9). |
| 14 | Schließen und Neustart | ✓ | 0 | nein | Alles da: Ergebnisse, Stechen, Abbruch, „keine Teilnahme“. |
| 15 | Eigene Erkundung | ✓ | 0 | Hilfe gelesen | Hoher Kontrast wirkt gut. Doppelte Startnummer wird klar abgelehnt. Eine Startnummer außerhalb des Bereichs wird dagegen kommentarlos angenommen (F5). |

## 3. Stolpersteine

*(F1 „Absturz bei Umlauten“ aus dem ersten Durchlauf ist entfallen: Es war ein Fehler der Testtastatur, siehe Abschnitt 6.)*

### F2: Abbruch-Grund in der Ergebniserfassung abgeschnitten: „Verletzun…“
- **Schwere:** mittel
- **Wo:** Reiter „Ergebniserfassung“, Spalte „Abbruch“ (Theme Beagle)
- **Was passiert ist:** Nach der Auswahl stand in der Zelle nur „Verletzun…“, beim Aufklappen vorher „kein Ab…“. Ob „Verletzung Hund“ oder „Verletzung HF“ gewählt war, ließ sich nicht erkennen. Erst die Auswertung („Abbruch wegen Verletzung des Hundes“) und eine spätere Ansicht in Hoher Kontrast (dort breiter) haben es bestätigt.
- **O-Ton:** „Hund oder Hundeführer? Das ist ja wohl ein Unterschied! Die Spalte ist viel zu schmal.“
- **Bildschirmfoto:** `Bild EA/0409` (Ausschnitt rechts unten), `0405.png`
- **Vorschlag:** Spalte „Abbruch“ breiter machen oder Kurzformen ohne gemeinsamen Anfang verwenden („Verl. Hund“ / „Verl. HF“).

### F3: Demo schaltet weiter, bevor man fertig gelesen hat, und hat kein „Zurück“
- **Schwere:** mittel
- **Wo:** Demoprüfung, Erklärfenster
- **Was passiert ist:** Mit „Automatisch weiter“ (Standard) sind Schritt 2, Schritt 7 (Zeitplan) und Schritt 12 (Stechen) durchgelaufen, während Heinz noch Schritt 11 bzw. das Hauptfenster angeschaut hat. Zurückblättern geht nicht. Das Stechen hat er sich danach selbst im Reiter „Auswertung“ angesehen. Der Haken bei „Automatisch weiter“ hilft, aber erst wenn man es gemerkt hat.

  **Nachtest in Echtzeit:** Die Demo lief ohne Eingriff, die Zeiten stammen aus `verlauf`. Schritte mit kurzer Aktion stehen nur 10–11 Sekunden:
  - Schritt 2 (ca. 60 Wörter): 10 s
  - Schritt 5 (ca. 45 Wörter): 11 s
  - Schritt 9 Disqualifikation (ca. 75 Wörter): 10 s
  - Schritt 11 Auswertung (ca. 70 Wörter): 10 s
  - Schritt 12 Stechen: 11 s
  - Schritt 13 (ca. 85 Wörter): 10 s

  Bei normalem Lesetempo braucht man für 60–85 Wörter rund 20–30 s, und zwar ohne nebenbei im Hauptfenster zuzuschauen. Ausreichend Zeit gibt es nur bei Schritten mit langer Aktion (Schritt 1: 48 s, Schritt 3: 23 s). Der Fund gilt damit auch ohne die Verzögerung des Werkzeugs.
- **O-Ton:** „Zack, schon wieder weiter. Das Stechen wollte ich doch gerade sehen. Gibt's da kein Zurück?“
- **Bildschirmfoto:** `Bild EA/0040`
- **Vorschlag:** einen Knopf „Zurück“ bzw. „Schritt wiederholen“. Den Countdown an die Textlänge koppeln (bei langen Texten 20–30 s) oder „Automatisch weiter“ standardmäßig ausschalten.

### F4: Zeitplan: „Mittagspause um 12:00“ landet am Planende, „Automatisch verteilen“ kennt keine Pausen
- **Schwere:** mittel
- **Wo:** Reiter „Zeitplan“, „Automatisch verteilen…“
- **Was passiert ist:**
  - Beim ersten Klick entstand der Vorschlag ohne jede Rückfrage.
  - Beim zweiten Klick kam die Rückfrage: „…ERSETZT dabei deren bisherigen Zeitplan (bereits eingefügte Pausen und von Hand geänderte Reihenfolgen gehen dabei verloren). Fortfahren?“
  - Die Mittagspause muss also immer nachträglich und nach jedem Neu-Verteilen erneut eingetragen werden.
  - **Nachtest:** Den Dialog „Pause“ hat Heinz schnell gefunden und verstanden. Er hat Dauer 45 Min., Bezeichnung „Mittagspause“ und den Haken „Bei allen Richtern einfügen, um 12:00 Uhr“ gesetzt. Das Programm meldete dann: „Die Pause beginnt nicht überall um 12:00: Anna Richter: 10:40 Uhr Bernd Berger: 10:40 Uhr Clara Christ: 10:20 Uhr …“.
  - Im Zeitplan-PDF zum Aushängen steht deshalb als letzte Zeile „10:40 – 11:25 Mittagspause“ (Clara: 10:20 – 11:05). Laut Handbuch ist das so gewollt („endet der Plan eines Richters vor dieser Uhrzeit, steht die Pause an seinem Ende“).
  - Überschneidungen wurden keine angezeigt, das PDF hat 3 Seiten.
  - Die Hilfe sagt „ersetzt den bisherigen Plan der gewählten Richter“, die Rückfrage dagegen „ALLE angelegten Richter“.
- **O-Ton:** „Mittagspause ist doch immer. Warum kann ich die nicht gleich beim Verteilen angeben? Sonst ist sie beim nächsten Verteilen wieder weg. Und eine Mittagspause um zwanzig vor elf als letzte Zeile, das hängt mir doch keiner aus. Wenn alle vorher fertig sind, soll das Programm das sagen und die Pause weglassen.“
- **Bildschirmfoto:** `Bild EA/0163`, `0457.png` (Dialog „Pause“), `0461.png` (Meldung „Pause eingefügt“)
- **Vorschlag:** In „Automatisch verteilen…“ eine feste Pause abfragen (z. B. 12:00–12:45 für alle) oder vorhandene „Pausen bei allen Richtern“ beim Neu-Verteilen erhalten. Endet der Plan eines Richters vor der Pausenzeit, die Pause weglassen oder nachfragen. Hilfetext angleichen.

### F5: Startnummer außerhalb des Bereichs wird kommentarlos angenommen
- **Schwere:** mittel
- **Wo:** „Teilnehmer bearbeiten“, Feld „Startnummer“
- **Was passiert ist:** Ziegler (Trümmer LK 1, Bereich 41–60) bekam Startnummer 150 (eigentlich Fläche-LK-1-Bereich 101–120 oder ganz außerhalb). Das Programm speicherte ohne Hinweis. Eine doppelte Nummer (41) wurde dagegen vorbildlich abgelehnt: „Die Startnummer 41 ist bereits einem anderen Teilnehmer zugeteilt (aktuell: Albrecht, Anna)…“.
- **O-Ton:** „Bei der doppelten Nummer passt es auf, bei der falschen Nummer nicht? Die Bereiche hab ich doch extra festgelegt.“
- **Bildschirmfoto:** `Bild EA/0444` (Meldung zur doppelten Nummer). Für die 150 gibt es kein Foto, weil keine Meldung kam.
- **Vorschlag:** Eine Rückfrage, wenn die Nummer außerhalb des Bereichs der Prüfung liegt („Nr. 150 liegt nicht im Bereich Trümmer LK 1 (41–60). Trotzdem speichern?“).

### F6: ED LK 2: Formular hat zwei Gegenstandsfelder, Maske nur eines
- **Schwere:** gering
- **Wo:** Anmeldeformular (PDF) und Erfassungsmaske
- **Was passiert ist:** Das erzeugte Anmeldeformular hat unter „LK 2:“ zwei Gegenstandsfelder (mit dem Hinweis, bei ED nur den ersten anzugeben). In der Maske ist bei ED nur „Gegenstand 1“ aktiv, „Gegenstand 2/3“ sind ausgegraut. Für Webers zweiten Gegenstand („Socke“) gibt es auch kein Anmerkungsfeld. Laut Handbuch ist das gewollt („in jeder Leistungsklasse genau einen Gegenstand“).
- **O-Ton:** „Gut, ED ist ein Gegenstand, das weiß ich. Aber wo schreib ich mir hin, dass der Weber noch eine Socke mitbringt?“
- **Bildschirmfoto:** `Bild EA/0083`
- **Vorschlag:** Ein freies Notizfeld je Teilnehmer.

### F7: Hinweis „Gegenstand der Suchdisziplin nicht zugeo…“ bei frisch importierter PDF-Meldung
- **Schwere:** gering
- **Wo:** Reiter „Teilnehmer“, Spalte „Anmerkungen“, Nina Neumann (aus PDF importiert)
- **Was passiert ist:** Der Text ist abgeschnitten. Laut Handbuch betrifft der Hinweis „ältere Daten“, Neumann wurde aber gerade eben per PDF eingelesen.
- **O-Ton:** „Was soll ich da jetzt machen? Die Meldung ist doch neu.“
- **Bildschirmfoto:** `Bild EA/0412` (Liste; Text laut Zustand)
- **Vorschlag:** Den Gegenstand beim PDF-Import gleich der Disziplin zuordnen, Spalte breiter oder Tooltip mit Volltext.

### F8: „Richter hinzufügen“ legt sofort eine Spalte an, leerer Richter landet als eigene Seite im Zeitplan-PDF
- **Schwere:** gering
- **Wo:** Reiter „Zeitplan“
- **Was passiert ist:** Ein Klick auf „Richter hinzufügen“ erzeugte ohne Namensabfrage sofort die Spalte „Richter 4“. Beim Zeitplan-PDF kam eine 4. Seite „Zeitplan – Richter 4 … Noch keine Prüfungsblöcke/Pausen für diesen Richter eingeplant.“ ohne Rückfrage. (Ausgelöst hat den Klick der Harness-Umweg aus Abschnitt 6, die Wirkung selbst ist aber echt.) Im Nachtest ließ sich die Spalte über „Richter löschen“ problemlos entfernen. Die Rückfrage lautete „„Richter 4“ samt allen dort eingeplanten Prüfungsblöcken/Pausen löschen?“.
- **O-Ton:** „Eine leere Seite für einen Richter, den es gar nicht gibt? Das druck ich doch nicht aus.“
- **Bildschirmfoto:** `Bild EA/0158`
- **Vorschlag:** Beim Hinzufügen gleich nach dem Namen fragen. Leere Richter im PDF weglassen oder vorher nachfragen.

### F9: Kleinigkeiten bei Texten und Zahlen
- **Schwere:** gering
- **Wo / Was:**
  - Startbildschirm: Der Tipp „Im Programm oben im Menü ‚Ansicht‘ …“ zeigt auf ein Menü, das es im Startbildschirm gar nicht gibt (`0001.png`).
  - Startbildschirm: Die Liste zeigt **17** Teilnehmer, der Kopfbalken im Termin **16** (Pohl mit „keine Teilnahme“ zählt einmal mit, einmal nicht).
  - Der Dateiname der Sicherung „SHS-Sicherung_2026-11-14_Hundefreunde-Testhausen_…zip“ klingt nach einem einzelnen Termin, obwohl laut Text ALLE Termine gesichert werden (`0431.png`).
  - Hilfe: „‚Bezahlt umschalten‘ setzt den Zahlungsstatus des markierten Teilnehmers“, laut Handbuch aber für alle markierten.
  - Meldung beim PDF-Import: Ein blaues Info-„i“, obwohl zwei Dateien abgelehnt wurden (`0137.png`).
- **O-Ton:** „17 oder 16, was denn nun?“
- **Vorschlag:** Texte angleichen. Teilnehmerzahl einheitlich (z. B. „16 (+1 abgesagt)“). Neutraler Sicherungsname, z. B. „SHS-Sicherung_alle-Termine_2026-11-03.zip“.

## 4. Was gut lief

- **Import der Meldungen:** CSV und PDFs werden mit Namen, Zeilennummer und klarem Grund übersprungen, z. B. „Anmeldung_Pfeiffer.pdf: mehrere Prüfungen angekreuzt (Trümmer LK 1, Fläche LK 1) - je Formular ist nur eine Prüfung möglich“. Gleich danach fragt das Programm, ob die Startnummern vergeben werden sollen.
- **Startnummern-Bereiche automatisch festlegen:** Ein Klick, und DK LK 1 = 1–20, DK LK 2 = 21–40 usw.
- **Nachmeldung:** Das Programm schlägt die nächste freie Nummer im richtigen Bereich vor (44). Die übrigen Nummern bleiben unverändert.
- **Startnummer tauschen** mit Strg-Klick und Klartext-Rückfrage, „Keine Teilnahme“ mit einem Klick, die Person bleibt grau in der Liste.
- **Zeitplan-Vorschlag** ohne Überschneidungen. Pohl ist automatisch raus, „Offene Starts“ grün.
- **Ergebniserfassung:** Gelbe Zeilen und ein roter Rahmen bei 65. Beim Speichern die klare Meldung „Neumann, Nina – Trümmerfeld: Suche höchstens 60 Punkte (eingegeben: 65)“. Beim Beenden mit ungültigem Wert fragt das Programm nach, statt still zu verwerfen.
- **Stechen:** Hinweistext mit Namen, Dialog mit Klartext, Anzeige „(nach Stechen)“ in Auswertung und Ergebnisliste.
- **Datensicherung** in drei Klicks, die Passwort-Erklärung ist verständlich.
- **Neustart:** Alles war noch da.
- **OMA-Import vorhanden:** Für Heinz ein dickes Plus.

## 5. Neue Funktionen im Urteil der Persona

**Demoprüfung:** Hat geholfen. Danach wusste Heinz, wo Startnummern, Stechen-Knopf und Export liegen, und musste in Aufgabe 11 nicht mehr suchen. Das automatische Weiterschalten ist für einen, der genau hinschaut, aber zu schnell, und ein „Zurück“ fehlt (F3).

**Startnummern-Bereiche und Vergabe:** Das beste Stück für ihn. Automatisch festlegen, nach dem Import vergeben, Nachzügler bekommt die nächste Nummer im Bereich. Nur die fehlende Bereichsprüfung bei Handeingabe stört (F5).

**Stechen:** Klar und schnell, „Stechen offen“ fällt sofort auf. In der Ergebnisliste steht „1. von 4 (nach Stechen)“, so gehört sich das.

**Abbruch mit Grund:** Fachlich richtig (Teilbewertung, Text laut PO in der Ergebnisliste: „Abbruch wegen Verletzung des Hundes (ABBR)“). In der Erfassung ist die Spalte aber zu schmal (F2).

**Aussehen:** Der dunkle Kopfbalken mit Beagle, Verein, Datum und Teilnehmerzahl gefällt ihm, man sieht immer, in welchem Termin man ist. Die Farben sind ruhig. Hoher Kontrast ist sehr gut lesbar, „für draußen auf dem Platz genau richtig“.

**Fehlermeldungen allgemein:** Meist vorbildlich. Sie nennen Namen, Werte und den nächsten Schritt (doppelte Startnummer, 65 Punkte, nicht angebotene Prüfung). Schwächen: keine Meldung bei einer Startnummer außerhalb des Bereichs, und das „i“-Symbol bei abgelehnten Dateien.

## 6. Grenzen dieses Tests

- **Umlaute (ehemals F1):** Im ersten Durchlauf stürzte das Programm beim Tippen von „Schlüsselbund“ (Feld „Gegenstand 1“) und „Müller“ (Feld „Nachname“) ab. Der begonnene Teilnehmer Weber ging dabei verloren, und Heinz musste „Schluesselbund“ eintragen. Laut Protokoll war das ein Fehler der Testtastatur (Qt-ASSERT in qasciikey.cpp). Im Nachtest mit dem reparierten Werkzeug ließen sich beide Wörter ohne Absturz tippen (danach „Abbrechen“). Es ist also **kein Programmfehler**.
- **Die folgenden vier Punkte stammen aus dem ersten Durchlauf und sind im Werkzeug inzwischen behoben.** Aufgabe 9 wurde danach vollständig nachgetestet.
- **Reiter „Zeitplan“ nicht bedienbar:** Sobald der Reiter offen ist, scheitert jede Zustandsabfrage mit „Harness-Fehler beim Zustand: … TypeError: columnCount(const QModelIndex &parent) const is a private method.“
  - Mehrdeutige Knöpfe („Pause hinzufügen…“ gibt es je Richter) lassen sich deshalb nicht ansprechen.
  - Die Mittagspause und das manuelle Bearbeiten konnten nicht getestet werden.
  - Bei Versuchen per Tastatur (Tab/Leertaste) wurden versehentlich „Richter hinzufügen“ und einmal „Startzeit speichern“ ausgelöst.
  - Den Reiter verlassen ging nur über „Anderen Termin öffnen…“ und erneutes Öffnen.
- **Häkchen im Dialog „Neuen Termin anlegen“:** Einige Häkchen (DK-LK 1/2, Fläche LK 1) reagierten nicht auf `klick`, nur auf die Leertaste. Wohl ein Problem mit der Klickposition im scrollbaren Bereich.
- **Tastaturfokus nach Meldungsfenstern:** Nach einer Meldung kamen Tastendrücke in der Ergebnistabelle nicht mehr an („Kein Element hat den Tastaturfokus“). Abhilfe war ein Neustart des Programms.
- **Zahlen in der Ergebnistabelle:** `tippe` übernimmt in Tabellenzellen nur das erste Zeichen, deshalb musste jede Ziffer einzeln mit `taste` eingegeben werden.
- **Sonstiges:**
  - Ein vorübergehender Harness-Fehler kam während der Demo.
  - Das englische Dateiauswahlfenster und „PDF öffnen“ ohne Wirkung sind wie im Briefing angekündigt.
  - Kein echter USB-Stick, die Sicherung liegt im Home-Ordner.
  - Die Update-Suche wurde nicht ausgelöst (Internet).
  - Die Rückfrage „… already exists. Do you want to replace it?“ beim Überschreiben des Zeitplan-PDFs ist englisch. Das liegt am Qt-Ersatzdialog der Testumgebung.
  - Mit den wenigen Testteilnehmern endet der Plan um 10:40. Eine Mittagspause mitten im Plan um 12:00 konnte deshalb nicht entstehen (Testdaten).

## 7. Gesamturteil

| Bereich | Note |
|---|---|
| Installation (gedanklich) | 2 |
| Erststart (inkl. Demo) | 2 |
| Termin-Ablauf (Aufgaben 2–14) | 2 |
| Gesamt | 2 |

**Würde ich am Prüfungstag allein damit klarkommen?** **Eher ja.** Anlegen, Meldungen, Startnummern, Ergebnisse, Stechen und Ausdrucke liefen fast ohne Handbuch. Den Zeitplan samt Mittagspause hat Heinz im Nachtest ohne Handbuch geschafft. Er muss aber selbst kontrollieren, ob die Pause wirklich um 12:00 liegt: Endet der Plan früher, hängt das Programm sie ans Ende, und beim Neu-Verteilen geht sie verloren. Dazu kommt die abgeschnittene Abbruch-Anzeige.

**Die drei wichtigsten Wünsche:**
1. Spalte „Abbruch“ breit genug, damit „Verletzung Hund“ und „Verletzung HF“ unterscheidbar sind.
2. Mittagspause gleich in „Automatisch verteilen…“ angeben, und sie soll beim Neu-Verteilen erhalten bleiben.
3. Warnung, wenn eine Startnummer von Hand außerhalb des Bereichs ihrer Prüfung gesetzt wird. Dazu eine Demo mit „Zurück“-Knopf.
