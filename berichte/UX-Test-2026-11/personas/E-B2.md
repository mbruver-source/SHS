# UX-Nachtest 2 2026-11 – Persona E-B2 (Sabine, 45)

## 1. Persona und Vorgehen

Sabine macht seit Jahren die Meldestelle ihres Vereins. Sie kann sehr gut mit Excel umgehen, kennt die Prüfungsabläufe, liest keine Anleitungen und probiert zügig aus. Von Tabellen erwartet sie Excel-Verhalten: Mehrfachauswahl mit Strg/Shift, Tab/Enter, Strg+A, Strg+S, Entf.

Quellen:
- **Handbuch: nein**, zu keinem Zeitpunkt geöffnet.
- Website `docs/index.html`: nur die Abschnitte „Installation“ und „Updates“.
- Hilfe im Programm (Knopf „Hilfe“): einmal in Aufgabe 15, mit dem neuen Suchfeld.
- Demoprüfung (Aufgabe 1), diesmal vollständig mitgelesen (Schritte 1–15).

Programm: Entwicklungsstand mit Versionsanzeige „1.0.55“, gesteuert über `ux.py` mit dem Kürzel EB2 und einer frischen Sandbox. Die Bilder liegen lokal unter `C:\Users\mbruv\AppData\Local\Temp\uxt\EB2\bilder\`.

## 2. Aufgaben-Übersicht

| Nr | Aufgabe | Ergebnis | Fehlversuche | Handbuch/Hilfe nötig? | Kommentar |
|---|---|---|---|---|---|
| 0 | Installation (gedanklich) | ✓ | 0 | nein (Website) | Download über „Assets“, Browser-Warnung (Strg+J → Behalten) und SmartScreen („Weitere Informationen“ → „Trotzdem ausführen“) stehen kurz auf der Website. Das Update geht über den Knopf „Version …“ → „Nach Updates suchen“, die neue Version einfach drüber installieren. |
| 1 | Erster Start, Demoprüfung | ✓ | 0 | nein | Knopf „Demoprüfung“ oben rechts auf dem Startbildschirm. 15 Schritte mit Lesezeit, am Ende löscht „Fertig“ den Demo-Termin. |
| 2 | Termin anlegen | ✓ | 0 | nein | Alles in einem Dialog. „Bereiche automatisch festlegen“ ergab 1–20, 21–40 … 101–120. Im Kopfbalken steht danach „Sa 14.11.2026“ mit Wochentag. |
| 3 | Anmeldeformular | ✓ | 0 | nein | Reiter „Export“ → „Anmeldeformular (PDF)…“. Im Kopf stehen Verband und Meldestelle, angeboten sind nur die 6 Prüfungen. |
| 4 | Zwei Nachmeldungen | ✓ | 0 | nein | Bei ED erscheint jetzt der Hinweis „Bei einer Einzeldisziplin gibt es nur einen Gegenstand.“ Sabine nahm deshalb nur „Schlüsselbund“. |
| 5 | Mitgliederliste CSV | ✓ | 0 | nein | 12 übernommen, 8 übersprungen, jeweils mit Zeile, Name und Grund sowie einem Abschnitt „Was tun?“. |
| 6 | Vier Anmelde-PDFs | ✓ | 0 | nein | Shift-Klick im Dateifenster wählte alle vier aus. 2 importiert, 2 abgelehnt („mehrere Prüfungen angekreuzt“, „Fläche LK 3 wird nicht angeboten – Formular eines anderen Termins?“). |
| 7 | Startnummern, Tausch, Absage | ✓ | 0 | nein | Das Programm bot nach dem Import selbst an, Startnummern zu vergeben. Tausch per Strg-Klick auf zwei Zeilen mit Rückfrage, „Keine Teilnahme“ in einem Klick. |
| 8 | Späte Nachmeldung | ✓ | 0 | nein | Ziegler bekam mit „Fehlende Startnummern vergeben…“ die 44. Alle anderen Nummern blieben gleich. |
| 9 | Zeitplan + PDF | ✓ | 0 | nein | „Automatisch verteilen…“ mit Haken bei Mittagspause meldete „…keine Überschneidungen. Keine Pause eingefügt – bei keinem Richter steht ab 12:00 Uhr noch eine Prüfung im Plan.“ (Plan endet 10:40). PDF gespeichert. |
| 10 | Ergebnisse eintragen | ✓ | 0 | nein | Wie in Excel: Zelle anklicken, tippen, Tab. 65 wurde sofort rot umrandet und unten erklärt. „Disqualifiziert“ mit einem Klick, „Abbruch“ öffnet die Liste mit einem Klick. Gespeichert mit Strg+S. |
| 11 | Rangliste + Stechen | ✓ | 0 | nein | Hinweis „Stechen nötig in ED LK 1 Trümmerfeld … – danach ‚Stechen-Sieger festlegen…‘“. Dorn danach „1. von 4 (nach Stechen)“. |
| 12 | PDFs erzeugen | ✓ | 0 | nein | Ergebnisliste, 16 Bewertungsbögen, Etiketten. Die Ergebnisliste zeigt „1. von 4 (nach Stechen)“, „Abbr. … Abbruch wegen Verletzung des Hundes (ABBR)“ und „Disq. … Disqualifiziert (DISQ)“. |
| 13 | Datensicherung | ✓ | 0 | nein | Reiter „Datensicherung“ → „Sicherung erstellen…“, ohne Passwort. „Sichert ALLE Termine“ steht deutlich da. |
| 14 | Schließen, Neustart | ✓ | 0 | nein | Startbildschirm: „16 (+1 abgemeldet)“. Ergebnisse, Stechen, Zeitplan und Tausch waren alle noch da. |
| 15 | Eigenes Ausprobieren | ✓ | – | Hilfe gelesen | Strg+A und Entf, „Löschen“ mit allen markiert (Rückfrage, Standard „Nein“), Hilfe-Suche, Design „Dunkel“, „abc“ und „4,5“ in Punktzellen, zweistellige Jahreszahl, Pause bei allen Richtern um 12:00. |

## 3. Stolpersteine

### F1: „4,5“ in einer Punktzelle wird zu 45, jetzt mit Hinweis
- **Schwere:** gering bis mittel
- **Wo:** Reiter „Ergebniserfassung“, Weber, Trümmerfeld Suche (vorher 47)
- **Was passiert ist:** Sabine tippte „4,5“ und drückte Enter. In der Zelle stand danach **45**, als „nicht gespeichert“ markiert. Darunter erschien neu: „Nur ganze Punkte von 0 bis 60 eingeben (keine Kommazahlen) - das Zeichen wurde nicht übernommen, bitte den Wert in der Zelle prüfen.“ Der richtige Wert 47 war trotzdem überschrieben. Ohne den Blick nach unten hätte sie es nicht gemerkt.
- **O-Ton:** „Okay, jetzt sagt er’s wenigstens. Aber warum macht er aus 4,5 einfach 45? Dann lieber gar nix übernehmen und den alten Wert lassen.“
- **Bildschirmfoto:** kein eigenes, Zustand im Werkzeug: „Z11: … | 45 | 31 | … | nicht gespeichert“. Danach wieder auf 47 gesetzt (`Bild EB2/0276`).
- **Vorschlag der Persona:** Bei Komma oder Punkt die ganze Eingabe verwerfen und den alten Wert stehen lassen, oder die Zelle rot markieren wie bei der 65.

### F2: Prüfungsnamen sind je nach Stelle verschieden geschrieben
- **Schwere:** gering
- **Wo:** Termin-Dialog, Teilnehmer-Dialog und Anmeldeformular gegenüber Teilnehmerliste, Filter, Ergebniserfassung und Auswertung
- **Was passiert ist:** Im Termin- und Teilnehmer-Dialog heißt es „DK-LK 1“ und „Trümmer LK 2“, im Anmeldeformular „Trümmer LK 2“. In allen Tabellen und Filtern steht dagegen „DK LK 1“ und „ED LK 2 Trümmerfeld“. Ausgewählt hatte Sabine „Trümmer LK 2“, in der Liste stand dann „ED LK 2 Trümmerfeld“.
- **O-Ton:** „Ich such im Filter nach ‚Trümmer LK 2‘ und find’s nicht, das heißt da ‚ED LK 2 Trümmerfeld‘. Man versteht’s, aber einheitlich wär schöner, gerade wenn ich das in Excel weiterverarbeite.“
- **Bildschirmfoto:** `Bild EB2/0049` (Dialog), Zustand nach Speichern (Liste)
- **Vorschlag der Persona:** Überall dieselbe Schreibweise verwenden, z. B. „Trümmer LK 2 (ED)“.

### F3: Tastenkürzel stehen nirgends gesammelt, die Hilfe-Suche findet sie nicht
- **Schwere:** gering
- **Wo:** Knopf „Hilfe“, Suchfeld
- **Was passiert ist:** Die Suche nach „Tastenkürzel“ ergab „nichts gefunden“. Dass Strg+S speichert, steht nur im Tooltip des Speichern-Knopfs, „Tab springt … Enter übernimmt … Entf leert“ nur in der Demo (Schritt 8). Ob es sonst Kürzel gibt, z. B. Entf zum Löschen von Teilnehmern, blieb offen.
- **O-Ton:** „Ich hätt gern einmal alle Kürzel auf einen Blick. Ich arbeite mit der Tastatur, nicht mit der Maus.“
- **Bildschirmfoto:** `Bild EB2/0256`
- **Vorschlag der Persona:** Ein kurzer Abschnitt „Tastenkürzel“ in der Hilfe.

### F4: Entf in der Teilnehmerliste tut nichts
- **Schwere:** gering
- **Wo:** Reiter „Teilnehmer“, Tabelle, alle mit Strg+A markiert, dann Entf
- **Was passiert ist:** Strg+A markierte alle Zeilen. Entf löschte nichts und zeigte auch keine Rückfrage. Über den Knopf „Löschen“ kam dagegen eine gute Rückfrage mit Namensliste, „Nein“ war vorausgewählt.
- **O-Ton:** „Na gut, da ist er vorsichtig, auch nicht schlecht. In Excel hätt ich jetzt gelöscht.“
- **Bildschirmfoto:** `Bild EB2/0253`, `Bild EB2/0254`
- **Vorschlag der Persona:** Entf darf die Lösch-Rückfrage öffnen. Die ist ja da und steht auf „Nein“.

### F5: Hinweis bei Buchstaben spricht von „Kommazahlen“
- **Schwere:** gering
- **Wo:** Reiter „Ergebniserfassung“, Bauer, Fläche Suche
- **Was passiert ist:** Auf „abc“ und Enter kam: „Nur ganze Punkte von 0 bis 60 eingeben (keine Kommazahlen) - das Zeichen wurde nicht übernommen …“. Die Zelle behielt richtig ihre 50.
- **O-Ton:** „Kommazahl hab ich gar nicht getippt. Passt schon, ich weiß, was gemeint ist.“
- **Bildschirmfoto:** `Bild EB2/0268`
- **Vorschlag der Persona:** „Nur ganze Zahlen von 0 bis 60“ reicht.

### F6: Mittagspause genau um 12:00 mit Lücke davor geht nicht
- **Schwere:** gering
- **Wo:** Reiter „Zeitplan“ → „Pause hinzufügen…“ mit „Bei allen Richtern einfügen, um 12:00“
- **Was passiert ist:** Es kam „Keine Pause eingefügt – bei keinem Richter steht ab 12:00 Uhr noch eine Prüfung im Plan.“ Das ist ehrlich und hängt nichts Falsches aus. Eine feste Pause um 12:00, etwa für das Mittagessen aller Helfer, kann man so aber nicht in den Aushang setzen.
- **O-Ton:** „Okay, wir sind um 10:40 fertig, dann gibt’s eh keine Pause. Passt für heute.“
- **Bildschirmfoto:** `Bild EB2/0282`
- **Vorschlag der Persona:** Höchstens als Wunsch: eine Option „trotzdem um 12:00 (mit Lücke)“.

### F7: Abbruch-Grund in der Spalte abgeschnitten
- **Schwere:** gering
- **Wo:** Reiter „Ergebniserfassung“, Spalte „Abbruch“, Engel
- **Was passiert ist:** In der Auswahl stand „Verletzung H…“. Die Statusspalte daneben zeigt den Grund aber vollständig: „Abbruch: Verletzung Hund“.
- **O-Ton:** „Steht ja rechts nochmal ganz. Ist nur Kosmetik.“
- **Bildschirmfoto:** `Bild EB2/0262`
- **Vorschlag der Persona:** Die Spalte etwas breiter machen.

## 4. Was gut lief

- **Excel-artige Bedienung:** Shift-Klick im Dateifenster, Strg-Klick und Strg+A in der Teilnehmerliste, Tab von Zelle zu Zelle, Strg+S zum Speichern. Die Ergebnisse von 16 Teams ohne einen einzigen Umweg.
- **Sofortprüfung der Punkte:** 65 wurde gleich rot umrandet, mit dem Text „Rot umrandet, so nicht speicherbar - bitte korrigieren: Nr. 43 Neumann: Trümmerfeld Suche höchstens 60 Punkte (eingegeben: 65)“.
- **Import-Meldungen** mit Name, Grund und „Was tun?“. Der Text bleibt im Reiter „Formular-Import“ unter „Letzter Import“ nachlesbar und hat einen Kopier-Knopf.
- **Nachfrage „Startnummern fehlen – jetzt vergeben?“** nach jedem Import. Sabine sagte erst „Nein“, weil noch PDFs kamen, und beim zweiten Mal „Ja“.
- **ED-Hinweis im Teilnehmer-Dialog**, sobald eine Einzeldisziplin gewählt ist.
- **„Keine Teilnahme“:** Pohl fällt aus Zeitplan und Kopfzahl heraus, im Startbildschirm steht „16 (+1 abgemeldet)“.
- **Zeitplan-Rückmeldung** „Alle 10 Prüfung(en) mit 28 Start(s) sind eingeplant, und es gibt keine Überschneidungen“. Die Seitenleiste „Offene Starts“ hat grüne Haken.
- **Lösch-Rückfrage** mit Namensliste, „Nein“ ist vorausgewählt.
- **Zweistellige Jahreszahl** „14.11.26“ wird beim Verlassen des Feldes zu „14.11.2026“.
- **Neustart:** alles war wieder da.

## 5. Neue Funktionen im Urteil der Persona

**Demoprüfung:** Sabine hat sie diesmal komplett mitgelesen. Die Texte sind knapp und praxisnah, etwa „Bereits vergebene Nummern ändert das Programm nie“ oder „Tab springt zur nächsten Zelle, Enter übernimmt die Zahl, Entf leert die Zelle“, dazu der Hinweis auf die orangefarbenen Anmerkungen. Danach wusste sie, wo alles liegt. Den echten Termin hat sie ohne Handbuch komplett durchgezogen. Die automatische Lesezeit von mindestens 10 Sekunden passt für sie.

**Startnummern-Bereiche/Vergabe:** Sehr gut. Bereiche automatisch, Vergabe auf einen Klick, späte Nachmeldung passt in die Lücke 44, nichts verrutscht. Unten in der Liste steht „Ohne Startnummer: …“ als Kontrolle.

**Stechen:** Klar geführt. Der Hinweistext nennt die Namen und den Knopf, die Auswahl ist eindeutig, in Auswertung und Ergebnisliste steht „(nach Stechen)“.

**Abbruch mit Grund:** Die Auswahl öffnet jetzt mit einem Klick. Die Teilpunkte bleiben drin, die Ergebnisliste zeigt „Abbruch wegen Verletzung des Hundes (ABBR)“. Nur der Grund ist in der Spalte abgeschnitten (F7).

**Aussehen:** Der dunkle Kopfbalken mit Verein, Wochentag, Datum, Ort und Teilnehmerzahl hilft bei der Orientierung. Die Beagle-Farben sind ruhig, „Dunkel“ ist gut lesbar und wirkt sofort. Die Symbole (Haken bei „gespeichert“, Diskette bei „nicht gespeichert“, Häkchen bei „Offene Starts“) erklären sich selbst.

**Fehlermeldungen allgemein:** Deutlich besser als erwartet: konkret, mit Name, Wert und Abhilfe, und meist sofort statt erst beim Speichern. Klein bleiben das Komma (F1) und die Wortwahl bei Buchstaben (F5).

## 6. Grenzen dieses Tests

- Das Dateifenster war der englische Qt-Ersatz, das wird nicht bewertet. Einen USB-Stick gab es nicht, die Sicherung liegt im Home-Ordner der Sandbox.
- Die Demoprüfung lief mit „Automatisch weiter“. Die Texte habe ich über `verlauf` gelesen, alle 15 Schritte vollständig.
- Kein Hover und keine Maus. Sortieren per Klick auf Spaltenköpfe und die Zwischenablage (Strg+C/Strg+V in Tabellen) habe ich nicht geprüft.
- Die Abbruch-Auswahl ist eine eingebettete Liste. `zelle` öffnete sie, gewählt wurde mit `auswahl`. Ein Mensch hätte einmal geklickt.
- Ein `doppelzelle` auf die Abbruch-Spalte zeigte zunächst keine sichtbare Änderung, vermutlich weil der zweite Klick die Liste wieder schloss (evtl. Testumgebung).
- `schliessen` auf dem Hauptfenster meldete „DAS PROGRAMM IST NICHT MEHR DA“. Das ist hier das gewollte Beenden, kein Absturz.
- Ob die Teilnehmer aus dem PDF-Import (Ostermann, Neumann) zu Recht ohne Verein in der Liste stehen, hängt am Inhalt der Test-PDFs und wurde nicht geprüft.
- Am Ende stand das Design auf „Dunkel“ (Aufgabe 15).

## 7. Gesamturteil

| Bereich | Note (Nachtest 2) | Note erster Test (E-B) |
|---|---|---|
| Installation | 2 | 2 |
| Erststart (inkl. Demo) | 1 | 1–2 |
| Termin-Ablauf | 1–2 | 2 |
| **gesamt** | **1–2** | **2** |

**Würde ich am Prüfungstag allein damit klarkommen?** **Ja.** Alle 15 Aufgaben gingen ohne Handbuch und ohne Fehlversuch. Die Tabellen verhalten sich wie in Excel, und falsche Punkte fallen jetzt sofort auf.

**Die drei wichtigsten Wünsche:**
1. Eine Eingabe mit Komma nicht zu 45 umbauen, sondern verwerfen oder rot markieren (F1).
2. Die Prüfungen überall gleich benennen (F2).
3. Eine kurze Übersicht der Tastenkürzel in der Hilfe, und Entf öffnet die Lösch-Rückfrage (F3, F4).

## 8. Abgleich mit dem ersten Test

| Früherer Fund | Stand | Begründung |
|---|---|---|
| F1: Komma wird still entfernt, aus „4,5“ wird 45 | teilweise | Es erscheint jetzt ein Hinweis („keine Kommazahlen – das Zeichen wurde nicht übernommen, bitte den Wert in der Zelle prüfen“). Der Wert wird aber weiterhin zu 45 und überschreibt die vorherige 47 (siehe F1 oben). |
| F2: Mittagspause „12:00 bei allen“ landet um 10:40 im Aushang | weitgehend | Es wird keine falsche Pause mehr eingesetzt. Die Meldung erklärt klar, dass ab 12:00 keine Prüfung mehr im Plan steht. Eine feste 12:00-Pause mit Lücke geht weiterhin nicht (jetzt nur noch ein Wunsch, F6). |
| F3: 65 erst beim Speichern bemängelt | behoben | Die Zelle wird sofort rot umrandet, darunter steht „Rot umrandet, so nicht speicherbar … höchstens 60 Punkte (eingegeben: 65)“. |
| F4: Unverständliche Anmerkung „Gegenstand der Suchdisziplin nicht zugeordnet“ | behoben | Neumann aus dem PDF-Import hatte keine Anmerkung mehr. Die übrigen Anmerkungen („Gegenstand noch offen“, „Chip-Nr. fehlt“) sind verständlich. |
| F5: Gegenstand 2 bei ED ohne Erklärung ausgegraut | behoben | Die Felder 2/3 verschwinden, dafür steht im Dialog: „Bei einer Einzeldisziplin gibt es nur einen Gegenstand.“ |
| F6: „14.11.26“ abgelehnt | behoben | Wird beim Verlassen des Feldes automatisch zu „14.11.2026“ (in „Veranstaltungsdaten bearbeiten“ geprüft). |
| F7: Teilnehmerzahl Startbildschirm 17 und Kopfbalken 16 | behoben | Der Startbildschirm zeigt „16 (+1 abgemeldet)“, der Kopfbalken „16 Teilnehmer“. |
| F8: Abbruch-Spalte erst per Doppelklick | behoben | Die Zelle hat ein Pfeilchen, ein Einfachklick öffnet die Auswahl. |
| F9: Hilfe ohne Suche | behoben | Die Hilfe hat ein Suchfeld mit „Weiter“ und ein Inhaltsverzeichnis. Nur „Tastenkürzel“ findet die Suche nicht (neuer kleiner Fund F3). |

**Zählung:** 7 behoben, 1 weitgehend, 1 teilweise, 0 nicht behoben, 0 nicht erlebt.
