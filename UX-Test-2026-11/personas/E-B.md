# UX-Test 2026-11 – Bericht Persona E-B (Sabine, 45)

## 1. Persona und Vorgehen

Sabine macht seit Jahren die Meldestelle ihres Vereins. Sie kann Excel sehr gut, kennt die Prüfungsabläufe, liest keine Anleitungen und probiert zügig aus. Sie erwartet, dass sich Tabellen wie in Excel bedienen lassen: Mehrfachauswahl mit Strg/Shift, Tab/Enter, Strg+A, Strg+S, Entf.

Quellen:
- **Handbuch: nein**, zu keinem Zeitpunkt geöffnet.
- Website `docs/index.html`: nur der Abschnitt „Installation“ und „Updates“.
- Hilfe im Programm (Knopf „Hilfe“): einmal am Ende in Aufgabe 15 gelesen.
- Demoprüfung (Aufgabe 1).

Programm: Version 1.0.55, gesteuert über das Werkzeug `ux.py` (Kürzel EB). Bilder liegen nur lokal (siehe Bericht, Abschnitt 1).

## 2. Aufgaben-Übersicht

| Nr | Aufgabe | Ergebnis | Fehlversuche | Handbuch/Hilfe nötig? | Kommentar |
|---|---|---|---|---|---|
| 0 | Installation (gedanklich) | ✓ | 0 | nein (Website reicht) | Download, SmartScreen-Hinweis und Update-Weg stehen kurz und klar auf der Website. |
| 1 | Erster Start, Demoprüfung | ✓ | 0 | nein | Knopf „Demoprüfung“ sofort gesehen. 15 Schritte mit Erklärtext; Knopf „Fertig“ löscht den Demo-Termin. |
| 2 | Termin anlegen | ✓ | 1 | nein | „14.11.26“ wurde abgelehnt, mit „14.11.2026“ ging es. „Bereiche automatisch festlegen“ war ein Volltreffer. |
| 3 | Anmeldeformular | ✓ | 0 | nein | Reiter „Export“ → „Anmeldeformular (PDF)…“. PDF enthält Kopf und nur die angebotenen Prüfungen. |
| 4 | Zwei Nachmeldungen | ~ | 1 | nein | Bei ED ist Gegenstand 2 ausgegraut. Sabine hat „Schlüsselbund, Socke“ zusammen in Feld 1 geschrieben. |
| 5 | Mitgliederliste CSV | ✓ | 0 | nein | 12 übernommen, 8 übersprungen, jeweils mit Namen und Grund („wird in diesem Termin nicht angeboten“). |
| 6 | Vier Anmelde-PDFs | ✓ | 0 | nein | Mehrfachauswahl mit Strg+A klappte. Beide Fehler (zwei Prüfungen angekreuzt; Fläche LK 3 nicht angeboten) waren klar benannt. |
| 7 | Startnummern, Tausch, Absage | ✓ | 0 | nein | Strg-Klick auf zwei Zeilen, dann „Startnummer tauschen…“ mit Rückfrage. „Keine Teilnahme“ in einem Klick. |
| 8 | Späte Nachmeldung | ✓ | 0 | nein | „Fehlende Startnummern vergeben…“ gab Ziegler die 44, die anderen Nummern blieben gleich. |
| 9 | Zeitplan + PDF | ~ | 0 | nein | Automatischer Vorschlag ohne Überschneidungen. Die Mittagspause „12:00 bei allen Richtern“ steht aber um 10:40 bzw. 10:20 im Aushang (F2). |
| 10 | Ergebnisse eintragen | ✓ | 2 | nein | Eintragen wie in Excel (Zelle anklicken, tippen, Tab). Den Tippfehler 65 hat erst „Speichern“ erkannt. Für die Abbruch-Auswahl war ein Doppelklick nötig. |
| 11 | Rangliste + Stechen | ✓ | 0 | nein | Hinweis „Stechen nötig in …“ und Knopf „Stechen-Sieger festlegen…“ direkt darunter; danach steht „1. von 4 (nach Stechen)“. |
| 12 | PDFs erzeugen | ✓ | 0 | nein | Ergebnisliste, Bewertungsbögen (16) und Etiketten erzeugt. Ergebnisliste zeigt „(nach Stechen)“, „Abbr. … Abbruch wegen Verletzung des Hundes (ABBR)“ und „Disq.“. |
| 13 | Datensicherung | ✓ | 0 | nein | Reiter „Datensicherung“, ohne Passwort gesichert. Der Hinweis „sichert ALLE Termine“ ist deutlich. |
| 14 | Schließen, Neustart | ✓ | 0 | nein | Alles war wieder da: Tausch, „keine Teilnahme“, Stechen, Ergebnisse. Beim Schließen kam keine Rückfrage, war aber auch nicht nötig. |
| 15 | Eigenes Ausprobieren | ✓ | – | Hilfe gelesen | Strg+A mit „Bezahlt umschalten“ für alle, dunkles Design, Hilfe, falsche Eingaben provoziert (F1). |

## 3. Stolpersteine

### F1: Komma in einer Punktzelle wird stillschweigend entfernt, aus „4,5“ wird 45
- **Schwere:** mittel
- **Wo:** Reiter „Ergebniserfassung“, Punktezelle (Weber, Trümmerfeld Suche, vorher 47)
- **Was passiert ist:** Sabine tippte im Ausprobier-Teil „4,5“ in die Zelle und drückte Enter. In der Zelle stand danach **45**, als „nicht gespeichert“ markiert. Eine Meldung oder einen Hinweis gab es nicht. Der vorher richtige Wert 47 war damit überschrieben, und das unauffällig. Buchstaben („abc“) wurden dagegen einfach nicht angenommen, die Zelle behielt ihren Wert.
- **O-Ton:** „Hä? Ich tipp 4,5 und da steht 45? In Excel krieg ich wenigstens ’ne Meldung. Wenn mir das am Prüfungstag bei ’nem Komma-Vertipper passiert, merk ich das nie.“
- **Bildschirmfoto:** kein eigenes; Zustand im Werkzeug „Z11: … | 45 | 31 | … | nicht gespeichert“.
- **Vorschlag der Persona:** Ein Komma oder Punkt sollte zu einer Meldung führen („Nur ganze Punkte 0–60“), statt das Zeichen still zu entfernen.

### F2: Die Mittagspause „bei allen Richtern um 12:00“ landet um 10:40 im Aushang
- **Schwere:** mittel
- **Wo:** Reiter „Zeitplan“ → „Pause hinzufügen…“ mit Haken „Bei allen Richtern einfügen, um 12:00“, danach „Zeitplan (PDF)…“
- **Was passiert ist:** Der Plan aller Richter endet vor 12 Uhr. Das Programm meldete: „Die Pause beginnt nicht überall um 12:00: Anna Richter: 10:40 Uhr Bernd Berger: 10:40 Uhr Clara Christ: 10:20 Uhr Ein laufender Prüfungsblock wird nicht geteilt; endet der Plan eines Richters vorher, steht die Pause an seinem Ende.“ Im Zeitplan-PDF steht danach „10:40 11:25 Mittagspause“.
- **O-Ton:** „Gut, dass er’s sagt. Aber so häng ich das nicht aus, da denken die Leute, um 10:40 gibt’s Essen. Ich will 12 Uhr, und wenn vorher nichts ist, dann ist halt Leerlauf.“
- **Bildschirmfoto:** `Bild EB/0159`
- **Vorschlag der Persona:** Die Pause zur gewünschten Uhrzeit setzen, auch wenn davor eine Lücke entsteht. Oder in der Meldung fragen: „Pause trotzdem um 12:00 (mit Lücke) oder direkt am Planende?“

### F3: Ein unzulässiger Punktwert (65) wird erst beim Speichern bemängelt
- **Schwere:** gering bis mittel
- **Wo:** Reiter „Ergebniserfassung“, Neumann, Trümmerfeld Suche
- **Was passiert ist:** 65 ließ sich ohne Rückmeldung tippen. Erst nach Strg+S kam: „Folgende Zeilen konnten nicht gespeichert werden (übrige wurden gespeichert): Neumann, Nina – Trümmerfeld: Suche höchstens 60 Punkte (eingegeben: 65)“. Die Meldung selbst ist klar.
- **O-Ton:** „Die Spalte heißt doch ‚Suche (0-60)‘, dann soll er mich die 65 gar nicht erst tippen lassen. Wie Datenüberprüfung in Excel halt.“
- **Bildschirmfoto:** `Bild EB/0270`
- **Vorschlag der Persona:** Die Zelle sofort rot markieren oder den Wert gleich beim Verlassen der Zelle zurückweisen.

### F4: Unverständliche Anmerkung „Gegenstand der Suchdisziplin nicht zugeordnet“
- **Schwere:** gering bis mittel
- **Wo:** Reiter „Teilnehmer“, Spalte „Anmerkungen“, Nina Neumann (aus dem PDF-Import)
- **Was passiert ist:** In der Liste stand die Anmerkung, anfangs abgeschnitten („Gegenstand der Suchdisziplin nicht zugeo …“). Im Bearbeiten-Dialog war für Sabine kein Fehler zu sehen: Gegenstand 1 ist ausgefüllt, „gesucht in“ ist ausgegraut. Was sie tun soll, blieb offen.
- **O-Ton:** „Was will der von mir? Da steht doch ein Gegenstand drin. Und ändern kann ich das ‚gesucht in‘ auch nicht.“
- **Bildschirmfoto:** `Bild EB/0334` (Zeile 43)
- **Vorschlag der Persona:** Im Dialog genau das betroffene Feld markieren und sagen, was zu tun ist. Oder es beim Speichern automatisch richtigstellen.

### F5: Bei ED ist Gegenstand 2 ohne Erklärung ausgegraut
- **Schwere:** gering
- **Wo:** Dialog „Teilnehmer erfassen“, Martin Weber (Trümmer LK 2, zwei Gegenstände laut Meldung)
- **Was passiert ist:** Gegenstand 2 und 3 sind ausgegraut, ohne Tooltip und ohne Hinweis im Dialog. Sabine schrieb deshalb „Schlüsselbund, Socke“ in Feld 1. Die Erklärung („Bei ED gibt es in jeder Leistungsklasse genau einen Gegenstand“) steht nur in der Hilfe und als Satz im Anmeldeformular.
- **O-Ton:** „Der hat zwei Sachen gemeldet, wo soll ich die Socke hinschreiben? Dann halt beides in eins.“
- **Bildschirmfoto:** `Bild EB/0101`
- **Vorschlag der Persona:** Ein Tooltip oder grauer Text am Feld: „Bei Einzeldisziplin nur ein Gegenstand“.

### F6: „14.11.26“ wird abgelehnt, die Vorschau hatte es aber schon verstanden
- **Schwere:** gering
- **Wo:** Dialog „Neuen Termin anlegen“, Feld Datum
- **Was passiert ist:** Der vorgeschlagene Speicherort zeigte schon `141126_Hundefreunde-Testhausen.sqlite`. Bei OK kam trotzdem: „Datum: „14.11.26“ ist kein gültiges Datum – bitte z. B. 14.11.2026 eingeben (TT.MM.JJJJ)“.
- **O-Ton:** „Excel versteht 14.11.26 auch. Na gut, die Meldung sagt wenigstens, wie’s geht.“
- **Bildschirmfoto:** `Bild EB/0090`
- **Vorschlag der Persona:** Zweistellige Jahreszahlen als 20xx übernehmen.

### F7: Teilnehmerzahl im Startbildschirm (17) und im Kopfbalken (16) verschieden
- **Schwere:** gering
- **Wo:** Startbildschirm, Terminliste; Kopfbalken im Hauptfenster
- **Was passiert ist:** Nach dem Neustart stand in der Terminliste „17“, im Kopfbalken danach „16 Teilnehmer“. Der Unterschied ist Peter Pohl („keine Teilnahme“), das steht aber nirgends dabei.
- **O-Ton:** „17 oder 16? Ah, der Pohl. Könnte man ja dazuschreiben.“
- **Bildschirmfoto:** kein eigenes (Zustand nach `start`)
- **Vorschlag der Persona:** Beide Stellen gleich zählen, oder „16 (+1 keine Teilnahme)“ schreiben.

### F8: Die Abbruch-Spalte reagiert erst auf Doppelklick
- **Schwere:** gering
- **Wo:** Reiter „Ergebniserfassung“, Spalte „Abbruch“
- **Was passiert ist:** „Disqualifiziert“ wechselt mit einem Klick. Ein Einfachklick auf „Abbruch“ tat dagegen nichts Sichtbares, erst ein Doppelklick öffnete die Auswahl (kein Abbruch / Ungehorsam / Verletzung Hund / Krankheit / Verletzung HF).
- **O-Ton:** „Ah, Doppelklick. Wie in Excel bei der Dropdown-Zelle, nur dass da ein Pfeilchen dran ist.“
- **Bildschirmfoto:** `Bild EB/0297`
- **Vorschlag der Persona:** Einen Pfeil an der Zelle zeigen oder die Auswahl schon beim Einfachklick öffnen.

### F9: Die Hilfe ist ein langer Fließtext ohne Suche
- **Schwere:** gering
- **Wo:** Knopf „Hilfe“
- **Was passiert ist:** Ein langes Textfeld mit allen Reitern hintereinander, ohne Inhaltsverzeichnis zum Anspringen und ohne Suchfeld. Inhaltlich ist alles drin, auch die Erklärung zu F5.
- **O-Ton:** „Das les ich nicht von oben bis unten. Strg+F wär schön.“
- **Bildschirmfoto:** `Bild EB/0332`
- **Vorschlag der Persona:** Ein Suchfeld oder anklickbare Kapitel. Noch besser: Hilfe-Knopf je Reiter, der direkt die passende Stelle zeigt.

## 4. Was gut lief

- **Excel-artige Bedienung:** Mehrfachauswahl mit Strg-Klick und Strg+A in der Teilnehmerliste und im Dateifenster. Mit Tab von Zelle zu Zelle in der Ergebniserfassung, Strg+S speichert. Die Ergebnisse von 16 Teams waren so in wenigen Minuten drin.
- **Klare Importmeldungen:** Jede abgelehnte Zeile oder Datei steht mit Name und Grund da. Die Meldung sagt auch, wo man nachträglich eine Prüfung anbietet.
- **„Bereiche automatisch festlegen“** im Termin-Dialog. Danach fragt das Programm nach dem Import selbst, ob es Startnummern vergeben soll.
- **Nachmeldung:** Neue Teilnehmer stehen auf „Startnummer steht noch nicht fest“, „Fehlende Startnummern vergeben…“ setzt sie passend in den Bereich. Unten steht immer „Ohne Startnummer: …“.
- **Startnummern tauschen** mit Rückfrage, die beide Namen und Nummern nennt.
- **„Keine Teilnahme“:** Der Teilnehmer bleibt grau und kursiv in der Liste und fällt aus Zeitplan und Auswertung heraus.
- **Rückfrage beim Reiterwechsel** mit ungespeicherten Ergebnissen, mit „Speichern / Nein / Abbrechen“.
- **Export-Reiter:** Neben jedem Knopf steht ein Satz, was er erzeugt. Dateinamen werden sinnvoll vorgeschlagen, die Meldung danach nennt den Speicherort.
- Neustart: alle Daten waren wieder da.

## 5. Neue Funktionen im Urteil der Persona

**Demoprüfung:** Den Knopf mit dem Doktorhut findet man sofort. Die Erklärtexte sind kurz und genau richtig, zum Beispiel „Tab springt zur nächsten Zelle, Enter übernimmt die Zahl, Entf leert die Zelle“ oder der Hinweis auf „Stechen-Sieger festlegen…“. Daraus hat Sabine gelernt, wo „Startnummer tauschen“, „Keine Teilnahme“ und die Ergebniserfassung sind, und dass ungespeicherte Zeilen gelb sind. Die 10 Sekunden je Schritt sind ihr eher zu flott, man kann das aber ausschalten. Fazit: hat geholfen, ein Handbuch brauchte sie danach nicht.

**Startnummern-Bereiche und Vergabe:** Sehr gut. Bereiche automatisch lückenlos ab 1 in 20er-Schritten. Fehlende Nummern werden nachvergeben, ohne vorhandene zu verändern.

**Stechen:** Gut gelöst. Der Text „Stechen nötig in ED LK 1 Trümmerfeld: … – danach ‚Stechen-Sieger festlegen…‘“ führt direkt zum Knopf. Die Auswahl ist eindeutig, Ergebnisliste und Auswertung zeigen „(nach Stechen)“.

**Abbruch mit Grund:** Fachlich passend, die Gründe sind gut gewählt. Die Teilpunkte bleiben erhalten, in der Liste steht „Abbruch wegen Verletzung des Hundes“. Einziger Haken ist der Doppelklick (F8).

**Aussehen:** Der dunkle Kopfbalken mit Verein, Datum, Ort und Teilnehmerzahl hilft bei der Orientierung. Die warmen Beagle-Farben sind angenehm, „Dunkel“ ist gut lesbar. Das Warndreieck bei „Chip-Nr. fehlt“ fällt sofort auf, das Häkchen bei „bezahlt“ ebenso.

**Fehlermeldungen allgemein:** Meist konkret, mit Name, Wert und Abhilfe, etwa beim Datum, beim Import oder beim zu hohen Punktwert. Schwächen: Manche Prüfungen kommen spät (F3), manche Eingaben werden still verändert (F1), und manche Anmerkungen sagen nicht, was zu tun ist (F4).

## 6. Grenzen dieses Tests

- Das Dateifenster war der englische Qt-Ersatz; das wird nicht bewertet. Einen USB-Stick gab es nicht, die Sicherung liegt im Home-Ordner.
- **Demoprüfung:** Das Steuerwerkzeug braucht für jede Zustandsabfrage mehrere Sekunden. Die Demo lief mit „Automatisch weiter“ deshalb schneller durch, als ich mitlesen konnte. Die Erklärtexte der Schritte 2 bis 7 (Teilnehmer, Startnummern, Bezahlt, Zeitplan …) habe ich nicht gesehen, nur Schritt 1 und 8 bis 15. In echt hätte Sabine mitgelesen oder den Haken herausgenommen. Das liegt am Werkzeug, nicht am Programm.
- Kein Hover, keine Maus. Spaltenköpfe (Sortieren wie in Excel) ließen sich mit dem Werkzeug nicht anklicken. Ob Sortieren per Klick auf die Spaltenköpfe geht, ist deshalb **ungeprüft**. Der Pfeil „Start-Nr.▲“ im Kopf deutet darauf hin.
- Die Zwischenablage (Strg+C aus Tabellen, Meldungstext kopieren) wurde nicht geprüft.
- `schliessen` auf dem Hauptfenster meldete „DAS PROGRAMM IST NICHT MEHR DA“. Das ist hier das gewollte Beenden, kein Absturz.

## 7. Gesamturteil

| Bereich | Note |
|---|---|
| Installation | 2 |
| Erststart (inkl. Demo) | 1–2 |
| Termin-Ablauf | 2 |
| **gesamt** | **2** |

**Würde ich am Prüfungstag allein damit klarkommen?** **Ja.** Ohne Handbuch ging alles, die Abläufe sind wie bisher und die Tabellen verhalten sich fast wie Excel. Aufpassen muss man bei den Punkteingaben (F1, F3).

**Die drei wichtigsten Wünsche:**
1. Ungültige Punkte sofort beim Tippen anzeigen und Zeichen nie still verändern (F1, F3).
2. Mittagspause wirklich zur gewählten Uhrzeit, auch mit Lücke davor (F2).
3. Anmerkungen und ausgegraute Felder erklären, was zu tun ist (F4, F5), und eine Hilfe mit Suche bzw. je Reiter (F9).
