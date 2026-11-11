# UX-Test 2026-11 – Bericht Persona N-A (Julia, 34)

## 1. Persona und Vorgehen

Julia, 34, Hundeführerin, organisiert zum ersten Mal eine Prüfung für ihren Verein. Kennt Prüfungen als
Teilnehmerin, nicht die Organisation. Normale PC-Kenntnisse (Office, Online-Banking). Gewissenhaft:
**mit Handbuch** – vor jeder neuen Aufgabe das passende Kapitel gelesen (Kap. 2, 3, 4, 5, 6, 7, 8, 10, 14, 15).

Quellen: `docs\HANDBUCH.md` (vor allem Kap. 14 „Die erste Prüfung Schritt für Schritt“ als Leitfaden),
Website `docs\index.html` (Installation), im Programm: Demoprüfung, Tooltips, Knopf „Hilfe“.
Bedienung über das Steuerwerkzeug (Kürzel NA), Programmversion 1.0.55.

## 2. Aufgaben-Übersicht

| Nr | Aufgabe | Ergebnis | Fehlversuche | Handbuch/Hilfe nötig? | Kommentar |
|---|---|---|---|---|---|
| 0 | Installation (gedanklich) | ✓ | 0 | Website + Handbuch Kap. 2 | Warnungen von Browser/SmartScreen gut erklärt; „Assets“ auf der Download-Seite ist ein fremdes Wort, wird aber genannt. Update-Weg klar. |
| 1 | Erster Start, Demoprüfung | ✓ | 0 | nein | Demo-Knopf sofort gesehen, lief selbstständig bis „Fertig“. Texte teils lang für 10 s Countdown (F3). |
| 2 | Termin anlegen | ✓ | 0 | Kap. 3 + 14 | „Bereiche automatisch festlegen“ gab sofort 1–20, 21–40 … – sehr angenehm. |
| 3 | Anmeldeformular | ✓ | 0 | Kap. 14 Schritt 2 | Export → Speichern → Fenster mit Pfad. Formular enthält nur die angebotenen Prüfungen. |
| 4 | Zwei Nachmeldungen | ~ | 0 | Kap. 4 (Gegenstände) | Maske übersichtlich. Bei Weber (ED) passen nur 1 von 2 Gegenständen – erst das Handbuch erklärt warum (F4). |
| 5 | Mitgliederliste CSV | ✓ | 0 | Kap. 5 | 12 übernommen, 8 abgelehnt mit Name und Grund („wird in diesem Termin nicht angeboten. Bitte mit dem Teilnehmer klären.“). |
| 6 | Vier Anmelde-PDFs | ✓ | 0 | Kap. 5 | Mehrfachauswahl klappte, Gründe klar (Pfeiffer: zwei Prüfungen angekreuzt; Quast: Fläche LK 3 nicht angeboten). Was danach zu tun ist, sagt die Meldung nur halb (F5). |
| 7 | Startnummern, Tausch, Absage | ✓ | 0 | Kap. 4, 14 | Vergabe nach Import per „Ja“, Tausch mit Strg-Klick + Rückfrage, „Keine Teilnahme“ – alles auf Anhieb. |
| 8 | Späte Nachmeldung Ziegler | ✓ | 0 | Kap. 4 (Erfassungsmaske) | Haken „Startnummer steht noch nicht fest“ weg → Programm schlägt 44 vor (nächste freie im Trümmer-LK-1-Bereich). Super. |
| 9 | Zeitplan + PDF | ~ | 0 | Kap. 6, 14 Schritt 5 | Automatisch verteilen ohne Überschneidungen. Mittagspause landet aber bei 10:40/10:20 am Planende und heißt im PDF trotzdem „Mittagspause“ (F1). |
| 10 | Ergebnisse eintragen | ✓ | 1 (Abbruch-Liste) | Kap. 7 | 65 wurde rot umrandet und beim Speichern klar abgelehnt. Disq.-Haken einfach. Abbruch-Spalte erst beim 2. Klick als Liste erkannt (F6). |
| 11 | Rangliste + Stechen | ✓ | 0 | Kap. 8 | Hinweis „Stechen nötig in …“ mit Knopfnamen; Auswahl im Fenster eindeutig. |
| 12 | PDFs + Prüfung Ergebnisliste | ✓ | 0 | Kap. 14 Schritt 8 | Ergebnisliste zeigt „1. von 4 (nach Stechen)“, „Abbr. … Abbruch wegen Verletzung des Hundes“, „Disq.“. |
| 13 | Datensicherung | ✓ | 0 | Kap. 10, 14 Schritt 9 | Sicherung ohne Passwort angelegt, Dateiname sprechend. |
| 14 | Neustart – alles da? | ✓ | 0 | nein | Termin in der Liste, Ergebnisse und Stechen erhalten. Teilnehmerzahl 17 vs. 16 irritiert kurz (F8). |
| 15 | Eigenes Ausprobieren | ✓ | 0 | Hilfe | Hoher Kontrast, Hilfe gelesen, Fehlermeldungen provoziert (Pflichtfelder, 31.02.). |

## 3. Stolpersteine

### F1: Mittagspause „um 12:00 bei allen Richtern“ landet um 10:40 bzw. 10:20 am Planende
- **Schwere:** mittel
- **Wo:** Reiter „Zeitplan“ → „Pause hinzufügen…“ → Haken „Bei allen Richtern einfügen, um 12:00“
- **Was passiert ist:** Der automatisch verteilte Plan endet bei allen Richtern vor 12 Uhr. Nach OK kam:
  „Die Pause beginnt nicht überall um 12:00: Anna Richter: 10:40 Uhr Bernd Berger: 10:40 Uhr Clara Christ:
  10:20 Uhr Ein laufender Prüfungsblock wird nicht geteilt; endet der Plan eines Richters vorher, steht die
  Pause an seinem Ende.“ Die Pause ist trotzdem eingefügt; im Zeitplan-PDF steht nun „10:40 – 11:25
  Mittagspause“ als letzter Eintrag. Eine Wahl („trotzdem einfügen / weglassen“) gab es nicht.
- **O-Ton:** „Mittagspause um zwanzig vor elf? Das häng ich so nicht aus – die Richter lachen mich aus. Die
  Meldung hat mir ja gesagt, dass es nicht passt, aber warum fügt er sie dann trotzdem ein?“
- **Bildschirmfoto:** `Bild NA/0090`
- **Vorschlag:** Endet der Plan vor der gewünschten Uhrzeit, fragen: „Der Plan endet schon um 10:40 –
  Pause trotzdem anhängen?“ (Ja/Nein), oder Pausen am Planende gar nicht anlegen.

### F2: Frisch importierte PDF-Anmeldung zeigt Hinweis „für ältere Daten“
- **Schwere:** mittel
- **Wo:** Reiter „Teilnehmer“, Spalte „Anmerkungen“, Zeile Neumann (aus `Anmeldung_Neumann.pdf`)
- **Was passiert ist:** Direkt nach dem PDF-Import stand bei Nina Neumann (ED LK 1 Trümmerfeld)
  „Gegenstand der Suchdisziplin nicht zugeordnet“. Das Handbuch erklärt diesen Hinweis als
  „ED (ältere Daten): Gegenstand ohne Zuordnung. Einmal öffnen und speichern behebt das.“ – sie ist aber
  keine alte Meldung, sondern gerade eben eingelesen. Bei den CSV-Teilnehmern steht dagegen
  „Gegenstand noch offen“.
- **O-Ton:** „Ältere Daten? Die hab ich doch gerade eingelesen. Muss ich jetzt jede PDF-Anmeldung einmal
  öffnen und speichern? Das steht nirgends im Import-Kapitel.“
- **Bildschirmfoto:** `Bild NA/0067`
- **Vorschlag:** Beim PDF-Import einer ED den Gegenstand gleich der ED-Disziplin zuordnen, oder Handbuch/
  Hinweis so formulieren, dass es auch nach einem Import gilt.

### F3: Demo-Countdown zu kurz für die langen Erklärtexte
- **Schwere:** gering
- **Wo:** Demoprüfung, Erklärfenster, Knopf „Weiter (10)“
- **Was passiert ist:** Einige Schritte haben sehr viel Text, z. B. Schritt 9 „Disqualifikation“ (rund 90
  Wörter inkl. vier Abbruchgründen) – laut Verlauf erschien er um 08:09:14, um 08:09:24 kam schon Schritt
  10. Ebenso Schritt 11 (Wertnoten-Grenzen ED und DK).
- **O-Ton:** „Ich war noch bei den Abbruchgründen, da war's schon weg. Ich hab dann gesehen, dass man den
  Haken ‚Automatisch weiter‘ rausnehmen kann – das hätte ich gleich am Anfang machen sollen.“
- **Bildschirmfoto:** `Bild NA/0003` (Demo läuft)
- **Vorschlag:** Countdown an die Textlänge koppeln (z. B. 10 s + 1 s je 10 Wörter) oder im
  Willkommensschritt deutlicher empfehlen, „Automatisch weiter“ für gründliches Lesen abzuschalten.

### F4: ED-Nachmeldung mit zwei Gegenständen – Felder 2 und 3 grau ohne Erklärung
- **Schwere:** gering
- **Wo:** „Teilnehmer erfassen“, Gegenstand 2/3 bei Art „ED“
- **Was passiert ist:** Martin Weber (Trümmer LK 2) hat „Schlüsselbund und Socke“ gemeldet. In der Maske
  sind Gegenstand 2 und 3 ausgegraut, ohne Tooltip oder Hinweis. Erst Handbuch Kap. 4 „Suchgegenstände“
  erklärt: bei ED immer genau ein Gegenstand. Ich habe nur „Schlüsselbund“ eingetragen.
- **O-Ton:** „Warum kann ich die Socke nicht eintragen? Ist das ein Fehler? – Ah, im Handbuch steht's:
  bei Einzeldisziplin nur einer. Dann muss ich Herrn Weber anrufen, welcher.“
- **Bildschirmfoto:** `Bild NA/0052`
- **Vorschlag:** Kurzer grauer Text oder Tooltip an den gesperrten Feldern: „Bei ED ist nur ein Gegenstand
  vorgesehen“.

### F5: Abgelehntes PDF (zwei Prüfungen angekreuzt) – unklar, wie es weitergeht
- **Schwere:** gering
- **Wo:** Formular-Import, Meldung „Import abgeschlossen“
- **Was passiert ist:** „Anmeldung_Pfeiffer.pdf: mehrere Prüfungen angekreuzt (Trümmer LK 1, Fläche LK 1)
  - je Formular ist nur eine Prüfung möglich“. Für Quast gibt es „Bitte mit dem Teilnehmer klären“, für
  Pfeiffer keinen Rat. Will er beides laufen, braucht er zwei Formulare – oder lege ich ihn zweimal von Hand
  an? Steht weder in der Meldung noch im Handbuch.
- **O-Ton:** „Okay, verstanden warum. Aber was mach ich jetzt – ihn zwei Formulare schicken lassen oder
  zweimal von Hand eintragen?“
- **Bildschirmfoto:** `Bild NA/0063`
- **Vorschlag:** Ergänzen: „Bitte nachfragen. Für zwei Prüfungen ein zweites Formular schicken lassen oder
  den Teilnehmer im Reiter ‚Teilnehmer‘ von Hand anlegen.“

### F6: Spalte „Abbruch“ sieht nicht wie eine Auswahlliste aus
- **Schwere:** gering
- **Wo:** Reiter „Ergebniserfassung“, Spalte „Abbruch“
- **Was passiert ist:** Die Zelle ist leer, ohne Pfeil oder Rahmen. Der erste Klick markierte nur, erst der
  zweite klappte „kein Abbruch / Ungehorsam / Verletzung Hund / Krankheit / Verletzung HF“ auf. Dank Demo
  wusste ich, dass es dort Gründe gibt.
- **O-Ton:** „Da ist ja nichts drin – ach, beim zweiten Klick kommt eine Liste. Ohne die Demo hätte ich das
  übersehen.“
- **Bildschirmfoto:** `Bild NA/0259`
- **Vorschlag:** Kleinen Pfeil oder grauen Platzhalter „kein Abbruch ▾“ in die Zelle; Liste beim ersten
  Klick öffnen.

### F7: Uneinheitliche Bezeichnungen der Prüfungen
- **Schwere:** gering
- **Wo:** Termin-Dialog vs. Listen/Filter
- **Was passiert ist:** Im Termin-Dialog heißt es „DK-LK 1“, „Trümmer LK 1“, „Fläche LK 1“, in Teilnehmerliste,
  Filter und Zeitplan „DK LK 1“, „ED LK 1 Trümmerfeld“, „ED LK 1 Flächensuche“; in den Importmeldungen
  wieder „Fläche LK 2“, „DK-LK 3“.
- **O-Ton:** „Ist ‚Trümmer LK 1‘ dasselbe wie ‚ED LK 1 Trümmerfeld‘? Ich glaub schon, aber einheitlich wär's
  einfacher.“
- **Bildschirmfoto:** `Bild NA/0026`, `…\0067.png`
- **Vorschlag:** Eine Schreibweise überall, z. B. „Trümmerfeld LK 1 (ED)“ und „Dreikampf LK 1 (DK)“.

### F8: Teilnehmerzahl im Startbildschirm 17, im Kopfbalken 16
- **Schwere:** gering
- **Wo:** Startbildschirm (Spalte „Teilnehmer“) vs. Kopfbalken im Hauptfenster
- **Was passiert ist:** Nach dem Neustart stand im Startbildschirm „17“, nach dem Öffnen im Kopfbalken
  „16 Teilnehmer“. Der Unterschied ist Peter Pohl („Keine Teilnahme“) – erklärt wird das nicht.
- **O-Ton:** „Fehlt mir jetzt einer? … Ach, Herr Pohl hat ja abgesagt. Hätte ich fast übersehen.“
- **Bildschirmfoto:** `Bild NA/0290`, `…\0291.png`
- **Vorschlag:** Gleich zählen oder „17 (1 abgesagt)“ anzeigen.

### F9: Hilfe und Handbuch widersprechen sich beim Löschen eines Termins
- **Schwere:** gering
- **Wo:** Knopf „Hilfe“, Abschnitt „Erste Schritte“
- **Was passiert ist:** Hilfe: „‚Löschen…‘ entfernt eine Termin-Datei unwiderruflich (mit Rückfrage)“.
  Handbuch Kap. 3: verschiebt den Termin in den Papierkorb, nur wenn das nicht geht, endgültig.
- **O-Ton:** „Was stimmt denn nun – Papierkorb oder weg für immer? Da wäre ich vorsichtig.“
- **Bildschirmfoto:** `Bild NA/0296`
- **Vorschlag:** Hilfetext an das Handbuch angleichen.

### F10: „Fehlende Angaben“ nennt alle Pflichtfelder statt der fehlenden
- **Schwere:** gering
- **Wo:** „Teilnehmer erfassen“ → OK mit nur Nachname
- **Was passiert ist:** „Nachname, Vorname und Rufname des Hundes sind Pflichtfelder.“ – obwohl der Nachname
  ausgefüllt war.
- **O-Ton:** „Den Nachnamen hab ich doch! Ach so, die anderen fehlen.“
- **Bildschirmfoto:** `Bild NA/0302`
- **Vorschlag:** „Bitte noch ausfüllen: Vorname, Rufname Hund“ und das erste leere Feld markieren.

### F11: Seitenleiste „Offene Starts“ zu schmal
- **Schwere:** gering
- **Wo:** Reiter „Zeitplan“, rechte Seitenleiste
- **Was passiert ist:** Bei drei Richtern bleibt rechts der Spalten viel Platz frei, die Seitenleiste ist schmal
  und bricht Einträge wie „DK LK 1 – Behältnisstrecke (4 Teilnehmer) – noch offen“ über zwei Zeilen um.
- **O-Ton:** „Lesbar, aber gequetscht – und daneben ist alles leer.“
- **Bildschirmfoto:** `Bild NA/0081`
- **Vorschlag:** Seitenleiste breiter oder in der Breite mitwachsen lassen.

## 4. Was gut lief

- **Kap. 14 des Handbuchs** ist ein echter roter Faden – ich bin fast nur damit durchgekommen.
- **Startnummern-Bereiche automatisch** im Termin-Dialog: ein Klick, fertig; Vergabe direkt nach dem Import
  mit „Ja“, und bei der späten Nachmeldung schlug die Maske gleich die passende Nummer 44 vor.
- **Importmeldungen** nennen Name, Zeile bzw. Datei und Grund; der Hinweis, wo man Prüfungen nachträgt,
  steht dabei.
- **Startnummer tauschen** mit Strg-Klick und klarer Rückfrage mit beiden Namen und Nummern.
- **Ergebniserfassung**: Zahlen eintippen, gelbe Zeilen, rote Umrandung bei 65, und die Meldung „Neumann,
  Nina – Trümmerfeld: Suche höchstens 60 Punkte (eingegeben: 65)“ – die übrigen wurden trotzdem gespeichert.
- **Stechen**: Hinweistext nennt die Beteiligten und den Knopfnamen, die Auswahl ist eindeutig, die Liste zeigt
  danach „1. von 4 (nach Stechen)“ – auch im PDF.
- Nach jedem PDF ein Fenster mit Pfad, „PDF öffnen“ und „Ordner zeigen“.
- Ungültiges Datum: „Wurftag: ‚31.02.2020‘ ist kein gültiges Datum – diesen Tag gibt es nicht“ – genau so
  versteht man es.

## 5. Neue Funktionen im Urteil der Persona

**Demoprüfung:** Sehr hilfreich. Ich habe danach gewusst, welche Reiter es gibt, dass Startnummern gesammelt
vergeben werden, dass es Abbruchgründe gibt und wo das Stechen eingetragen wird. Einziges Manko: bei
„Automatisch weiter“ sind einige Texte zu schnell weg (F3).

**Startnummern-Bereiche/Vergabe:** Das Beste am ganzen Programm. Bereiche automatisch, Vergabe nach Import,
Vorschlag der nächsten freien Nummer bei Nachmeldungen – ich musste nie selbst rechnen.

**Stechen:** Klar und schnell. Gut, dass das Programm selbst sagt, wo ein Stechen nötig ist.

**Abbruch mit Grund:** Fachlich genau richtig (Teilpunkte bleiben, Text „Abbruch wegen Verletzung des
Hundes“ im PDF). Die Spalte ist aber schwer als Auswahl zu erkennen (F6).

**Aussehen:** Der dunkle Kopfbalken mit Beagle, Verein, Datum, Ort und Teilnehmerzahl wirkt freundlich und
gibt Orientierung. Creme-Hintergrund angenehm; „Hoher Kontrast“ funktioniert sofort und sieht sauber aus.
Symbole an den Knöpfen oben sind dezent.

**Fehlermeldungen allgemein:** Meistens verständlich und mit Rat, was zu tun ist. Ausnahmen: die
Pflichtfeld-Meldung (F10) und die Pausen-Meldung, die ein Problem meldet und es trotzdem so macht (F1).

## 6. Grenzen dieses Tests

- Dateiauswahl war der englische Qt-Ersatzdialog (Testumgebung, kein Fund).
- „PDF öffnen“/„Ordner zeigen“ nicht ausprobiert; PDF-Inhalte per Textauszug gelesen – Layout, Farben und
  Etiketten-Inhalt nicht optisch geprüft.
- Kein USB-Stick vorhanden: Sicherung in den Download-Ordner gespeichert; Passwortschutz nicht ausprobiert.
- Demoprüfung über den Verlauf mitgelesen, nicht jeden Schritt am Bild verfolgt.
- Installation nur gedanklich anhand Website und Handbuch.
- Die Werkzeug-Ausgabe kürzt lange Texte und zeigte in der Seitenleiste „Offene Starts“ ein „✓“ vor „noch
  offen“ – laut Bildschirmfoto korrekt rot mit Kreuz (Harness-Darstellung, kein Fund).
- „schliessen“ des Hauptfensters meldet „DAS PROGRAMM IST NICHT MEHR DA“ – war beabsichtigtes Beenden.

## 7. Gesamturteil

| Bereich | Note |
|---|---|
| Installation | 2 |
| Erststart (inkl. Demo) | 2 |
| Termin-Ablauf | 2 |
| **Gesamt** | **2** |

**Würde ich am Prüfungstag allein damit klarkommen?** **Eher ja.** Mit dem Handbuch (Kap. 14) und der Demo
habe ich alles geschafft. Unsicher blieb ich nur bei Kleinigkeiten (Mittagspause, Gegenstände bei ED,
Hinweis bei der PDF-Meldung), die ich am Prüfungstag lieber nicht erst klären möchte.

**Die drei wichtigsten Wünsche:**
1. Mittagspause nicht stillschweigend ans Planende hängen, sondern fragen (F1).
2. Einheitliche Namen für die Prüfungen überall (F7) und kein „ältere Daten“-Hinweis nach frischem PDF-Import (F2).
3. Gesperrte/versteckte Bedienelemente erklären: ED-Gegenstand 2/3, Abbruch-Auswahl (F4, F6).
