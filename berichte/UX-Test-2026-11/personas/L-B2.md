# UX-Nachtest 2026-11 – Persona L-B2 (Werner, 66)

## 1. Persona und Vorgehen

Werner, 66, Rentner, früher Kassenwart im Verein. Sitzt selten am PC, liest keine Anleitungen,
klickt herum, bis etwas passiert. Rote oder unverständliche Meldungen machen ihn nervös; mit CSV,
ZIP und „PDF-Import“ kann er wenig anfangen.

Quellen: **kein Handbuch** (auch nicht aus Verzweiflung geöffnet). Für die Installation nur die
Website `docs\index.html`. Im Programm: Demoprüfung, Tooltips und das Hilfe-Fenster (Knopf „Hilfe“,
diesmal schon bei Aufgabe 3 geöffnet, um das Anmeldeformular zu finden). Bedient wurde der neue
Arbeitsstand (Anzeige „Version 1.0.55“) über das Steuerwerkzeug, Kürzel LB2. Bildschirmfotos liegen
unter `C:\Users\Name\AppData\Local\Temp\uxt\LB2\bilder\`.

## 2. Aufgaben-Übersicht

| Nr | Aufgabe | Ergebnis | Fehlversuche | Handbuch/Hilfe nötig? | Kommentar |
|---|---|---|---|---|---|
| 0 | Installation (gedanklich) | ~ | – | Website | „Assets“ wird jetzt erklärt („= Dateien zum Herunterladen“), die SmartScreen-Warnung ist angekündigt und mit „Kaputt machen kannst du dabei nichts“ entschärft. „.exe“, Download-Blockade im Browser und „GitHub“ bleiben für Werner fremd. Update über den Knopf „Version …“ steht auf der Website, im Programm hätte er es nicht gesucht. |
| 1 | Erster Start, Demoprüfung | ✓ | 0 | nein | Demo-Knopf mit Doktorhut sofort sichtbar. Erster Text bleibt 40 Sekunden stehen, die übrigen 15–40 Sekunden je nach Länge – Werner kam meist mit. Bis „Fertig“ durchgesehen. |
| 2 | Termin anlegen | ✓ | 0 | nein | Fläche und Behältnisse erst nach dem Bildlauf. „Bereiche automatisch festlegen“ erledigt die Startnummern-Bereiche (1–20, 21–40 …). Die Rückfrage zu Verband/Meldestelle war verständlich; Werner hat „Nein“ gewählt und die Felder ausgefüllt. |
| 3 | Anmeldeformular | ✓ | 0 | Hilfe | Die Demo hatte das Formular nicht gezeigt. In der Hilfe (lange Textwand) stand „Reiter Export → Anmeldeformular (PDF)…“. Danach ein Klick, Speichern mit Vorschlag. |
| 4 | Zwei Nachmeldungen | ✓ | 0 | nein | Feld „Prüfung: Trümmer LK 2 – wird angeboten“ bestätigt die Wahl aus Art/LK/Disziplin. Bei ED steht jetzt „Bei einer Einzeldisziplin gibt es nur einen Gegenstand.“ – Werner schreibt „Schlüsselbund und Socke“ in das eine Feld. |
| 5 | Mitgliederliste (CSV) | ✓ | 0 | nein | Knopf im Reiter „Teilnehmer“. 12 übernommen, 8 übersprungen, jede mit Namen und Grund; „Was tun?“-Abschnitt und Knopf „Meldung kopieren und schließen“. Danach bot das Programm die Startnummern-Vergabe an. |
| 6 | Vier Anmelde-PDFs | ✓ | 0 | nein | Fenstertitel „mehrere mit Strg-Klick markieren“ – so ging es in einem Durchgang. Pfeiffer (zwei Prüfungen angekreuzt) und Quast (Fläche LK 3 nicht angeboten) abgelehnt, Grund verständlich. Werner würde beide anrufen. |
| 7 | Startnummern, Tausch, Absage | ✓ | 0 | nein | Bereiche standen schon. Tausch über „Startnummer tauschen…“ mit Auswahlliste, Pohl über „Keine Teilnahme“ (bleibt in der Liste mit „keine Teilnahme“). |
| 8 | Späte Nachmeldung | ✓ | 0 | nein | „Fehlende Startnummern vergeben…“ → Ziegler bekommt 44, sonst ändert sich nichts. |
| 9 | Zeitplan + PDF | ~ | 0 | nein | „Automatisch verteilen…“ ein Klick. Mittagspause für alle um 12:00 → klare Meldung, dass keine nötig ist. Ob der Plan überschneidungsfrei ist, sagt das Programm nicht ausdrücklich (nur grüne Haken bei „Offene Starts“). PDF gespeichert. |
| 10 | Ergebnisse eintragen | ✓ | 1 | nein | 65 → sofort Text unter der Tabelle „Rot umrandet, so nicht speicherbar …“. Disqualifiziert per Haken, Abbruch per Auswahlliste mit Pfeil. Meldung „29 Ergebnis(se) gespeichert.“ bei 16 Teilnehmern hat irritiert. |
| 11 | Rangliste + Stechen | ✓ | 0 | nein | Hinweis „Stechen nötig in ED LK 1 Trümmerfeld …“, Knopf, Auswahl, danach „1. von 4 (nach Stechen)“. |
| 12 | PDFs erzeugen | ✓ | 0 | nein | Ergebnisliste mit „(nach Stechen)“, „Abbr. … Abbruch wegen Verletzung des Hundes (ABBR)“ und „Disq.“. Bewertungsbögen (16) und Etiketten ohne Probleme. |
| 13 | Datensicherung | ✓ | 0 | nein | Ohne Passwort. Der Satz „Passwort getrennt von der Sicherung aufbewahren“ im Reiter hat Werner kurz verunsichert, der Dialog erklärt dann, dass das Passwort freiwillig ist. Kein USB-Stick in der Testumgebung. |
| 14 | Schließen und Neustart | ✓ | 0 | nein | Termin vorausgewählt, „Öffnen“ aktiv, Startseite zeigt „16 (+1 abgemeldet)“. Alles noch da, Stechen inklusive. |
| 15 | Eigenes Ausprobieren | ✓ | – | Hilfe | „Ansicht → Schriftgröße → Sehr groß“ gefunden und genutzt. Löschen eines Teilnehmers fragt nach („Nein“ vorgewählt). Version-Fenster mit Fachwörtern. |

## 3. Stolpersteine

### F1: Programm sagt nicht ausdrücklich, ob der Zeitplan überschneidungsfrei ist
- **Schwere:** mittel
- **Wo:** Reiter „Zeitplan“ nach „Automatisch verteilen…“
- **Was passiert ist:** Nach dem Klick steht unten nur „Automatischer Zeitplan-Vorschlag erstellt.“,
  rechts unter „Offene Starts“ grüne Haken („DK LK 1 – Behältnisstrecke (4 Teilnehmer)“ …). Die Haken
  heißen „eingeplant“, nicht „ohne Überschneidung“. Um sicherzugehen, hätte Werner die drei Spalten
  nebeneinander Zeile für Zeile vergleichen müssen (z. B. Quinn Quandt 09:00 bei Anna Richter,
  09:20 bei Bernd Berger, 09:40 bei Clara Christ). Das traut er sich nicht zu.
- **O-Ton:** „Schön bunt, aber hängt das jetzt so aus, oder steht einer zur selben Zeit an zwei Stellen? Sagt mir keiner.“
- **Bildschirmfoto:** `Bild LB2/0099`
- **Vorschlag:** Eine Zeile „Keine Überschneidungen – Plan kann ausgehängt werden“ (grün) bzw. die
  betroffenen Teams rot, gut sichtbar über dem Plan.

### F2: „29 Ergebnis(se) gespeichert.“ bei 16 Teilnehmern
- **Schwere:** gering
- **Wo:** Reiter „Ergebniserfassung“, Statuszeile nach „Alle Ergebnisse speichern“
- **Was passiert ist:** Gemeldet wurden 29 gespeicherte Ergebnisse, im Kopf steht „16 Teilnehmer“.
  Werner vermutet, dass etwas doppelt gespeichert wurde. (Gezählt werden offenbar Disziplinen.)
- **O-Ton:** „Neunundzwanzig? Ich hab doch nur sechzehn Leute. Hab ich da was doppelt eingetippt?“
- **Bildschirmfoto:** `Bild LB2/0278`
- **Vorschlag:** „Ergebnisse von 16 Teilnehmern gespeichert.“

### F3: Spalte „Abbruch“ zu schmal, der Grund ist abgeschnitten
- **Schwere:** gering
- **Wo:** Reiter „Ergebniserfassung“, Spalte „Abbruch“ (Normal-Schrift, erste Sitzung)
- **Was passiert ist:** Nach der Auswahl „Verletzung Hund“ stand in der Zelle nur „letzung H▾“,
  während die Spalte „Status“ rechts fast die halbe Breite einnimmt. Nach dem Neustart (mit
  „Sehr groß“) war die Spalte breit genug. Zusätzlich steht bei Ziegler (disqualifiziert) und Engel
  (Abbruch) in „Status“ nur „✓ gespeichert“ wie bei allen anderen.
- **O-Ton:** „‚letzung H‘ – was ist das denn? Ah, Verletzung. Hätte ruhig breiter sein können, da rechts ist doch Platz.“
- **Bildschirmfoto:** `Bild LB2/0278`, `…\0303.png`
- **Vorschlag:** Spalte „Abbruch“ so breit wie der längste Grund; in „Status“ „disqualifiziert“ /
  „Abbruch“ anzeigen.

### F4: Teilnehmerformular: Prüfung weiter aus drei Feldern zusammensetzen
- **Schwere:** gering
- **Wo:** „Teilnehmer erfassen“, Felder „Art*“, „Leistungsklasse*“, „Disziplin (nur bei ED)“
- **Was passiert ist:** Für „Trümmer LK 2“ muss Werner Art „ED“, Leistungsklasse „2“ und Disziplin
  „Trümmerfeld“ wählen. Neu ist die grüne Zeile „Prüfung: Trümmer LK 2 – wird angeboten“, die ihm
  bestätigt, dass er richtig liegt. Das hat gereicht, „ED“ kannte er aus der Demo.
- **O-Ton:** „Ah, da steht's ja grün: Trümmer LK 2 wird angeboten. Dann passt das.“
- **Bildschirmfoto:** `Bild LB2/0060`
- **Vorschlag:** Wie im ersten Test: eine Auswahlliste „Prüfung“ mit den angebotenen Prüfungen
  wäre für Laien noch einfacher.

### F5: Version-Fenster mit Fachwörtern, Update versteckt
- **Schwere:** gering
- **Wo:** Kopfbalken, Knopf „Version 1.0.55“
- **Was passiert ist:** Updates gibt es nur hinter „Version 1.0.55“. Im Fenster stehen
  „Diagnose kopieren“, „Ende des Absturzprotokolls“, „Protokoll-Ordner öffnen“, „GitHub“.
- **O-Ton:** „Absturzprotokoll? Ist der abgestürzt? Da mach ich lieber wieder zu.“
- **Bildschirmfoto:** `Bild LB2/0308`
- **Vorschlag:** Den oberen Teil („Nach Updates suchen“) groß, den Fehlermelde-Teil unter
  „Für Fehlermeldungen“ abgesetzt bzw. einklappbar.

### F6: Hilfe ist eine lange Textwand
- **Schwere:** gering
- **Wo:** Knopf „Hilfe“
- **Was passiert ist:** Werner suchte das Anmeldeformular. Die Hilfe beginnt mit Schrift- und
  Kontrast-Tipps und einem Inhaltsverzeichnis als Fließtext; die Antwort („Reiter Export →
  Anmeldeformular (PDF)…“) steht erst im Abschnitt „Formular-Import“. Gefunden hat er sie trotzdem.
- **O-Ton:** „Viel Text. Aber da steht's: Export. Na gut.“
- **Bildschirmfoto:** `Bild LB2/0036`
- **Vorschlag:** Inhaltsverzeichnis als anklickbare Sprungmarken; ggf. kurzer Abschnitt
  „Wie mache ich …?“ (Anmeldeformular, Sicherung, Pause …).

### F7: Hinweis im Reiter „Datensicherung“ wirkt, als bräuchte man ein Passwort
- **Schwere:** gering
- **Wo:** Reiter „Datensicherung“
- **Was passiert ist:** Dort steht „Sichert ALLE Termine in eine .zip-Datei … Passwort getrennt von
  der Sicherung aufbewahren.“ Werner hat kein Passwort und erschrak. Erst im Dialog stand, dass
  „Mit Passwort schützen“ freiwillig ist.
- **O-Ton:** „Welches Passwort denn? Ich hab nie eins vergeben!“
- **Bildschirmfoto:** `Bild LB2/0294`
- **Vorschlag:** „… auf Wunsch mit Passwort. Wer ein Passwort vergibt, bewahrt es getrennt auf.“
  Statt „.zip-Datei“ einfach „eine Sicherungsdatei“.

## 4. Was gut lief

- Demoprüfung: sofort auffindbar, diesmal mit Lesezeiten, die zu Werner passen. Danach kannte er
  Teilnehmer, Startnummern, Zeitplan, Ergebnisse, Disqualifikation, Abbruch, Stechen und Export.
- Startnummern: „Bereiche automatisch festlegen“ im Termin, nach jedem Import die Frage „Jetzt
  Fehlende Startnummern vergeben?“, die späte Nachmeldung bekommt die 44 im richtigen Bereich.
- Import-Meldungen (CSV und PDF): Namen, Zeile, Grund, „Was tun?“ und ein Kopier-Knopf. Gelbes
  Dreieck statt Rot – Werner blieb ruhig.
- Mehrere PDFs auf einmal dank Hinweis im Fenstertitel.
- Falsche Punktzahl: sofort ein Satz mit Name, Disziplin und erlaubtem Höchstwert.
- Mittagspause: klare Meldung „Keine Pause eingefügt – bei keinem Richter steht ab 12:00 Uhr noch
  eine Prüfung im Plan.“
- Stechen und Ergebnisliste vorbildlich, Abbruch und Disqualifikation stehen ausgeschrieben im PDF.
- Speichern-Fenster schlagen immer Ordner und Dateinamen vor; danach „Gespeichert unter …“ mit
  „PDF öffnen“ und „Ordner zeigen“.
- Schriftgröße jetzt im Menü „Ansicht“, Tipp dazu schon auf der Startseite.
- Neustart: alles da, Termin vorausgewählt, „16 (+1 abgemeldet)“.
- Löschen fragt nach, „Nein“ ist vorgewählt.

## 5. Neue Funktionen im Urteil der Persona

**Demoprüfung:** Hat beim Lernen am meisten geholfen. Der erste Text bleibt lange genug stehen,
die späteren richten sich nach der Länge. Werner hat fast alles mitbekommen; nur Schritt 5
(Startnummern) wechselte nach dem Ergebnis „8 Startnummern vergeben.“ recht zügig. Das
Anmeldeformular kam in der Demo nicht vor, dafür musste er die Hilfe öffnen.

**Startnummern-Bereiche/Vergabe:** Sehr gut. Ein Klick legt die Bereiche fest, das Programm bietet
die Vergabe nach jedem Import von selbst an und ändert vergebene Nummern nicht.

**Stechen:** Klar: Hinweistext mit Namen, Knopf, Auswahlliste, Ergebnis „(nach Stechen)“.

**Abbruch mit Grund:** Die Spalte ist jetzt als Auswahlliste mit Pfeil erkennbar, die Gründe sind
verständlich. Schade nur, dass der Grund in der schmalen Spalte abgeschnitten war (F3).

**Aussehen:** Dunkler Kopfbalken mit Hundekopf, Verein, Datum und Teilnehmerzahl hilft beim
Orientieren. Symbole (Haken, Warndreieck, Doktorhut) verständlich. „Sehr groß“ macht die Schrift
spürbar größer, Werner ist zufrieden.

**Fehlermeldungen allgemein:** Freundlich, auf Deutsch, mit Namen und Vorschlag. Keine hat Panik
ausgelöst. Kleine Ausreißer sind Zählweisen („29 Ergebnisse“) und Fachwörter im Version-Fenster.

## 6. Grenzen dieses Tests

- Installation nur gedanklich anhand der Website; SmartScreen und GitHub-Seite nicht wirklich gesehen.
- Englischer Qt-Ersatz für den Dateidialog; ob Werner den USB-Stick im echten Explorer-Dialog
  findet, ist nicht getestet. Die Strg-Klick-Mehrfachauswahl wurde per Befehl ausgeführt.
- Bedienung per Befehl statt Maus, kein Hover; „PDF öffnen“ öffnet nichts Sichtbares (PDF-Inhalt
  per Text gelesen).
- Lesegeschwindigkeit in der Demo ist gespielt; ausgewertet wurde, wie lange die Texte standen.
- „Nach Updates suchen“ nicht geklickt.
- Nach `schliessen` meldete das Werkzeug „DAS PROGRAMM IST NICHT MEHR DA“ – gewolltes Programmende,
  kein Absturz. Sonst keine Harness-Probleme.
- F3 (schmale Abbruch-Spalte) trat nur in der ersten Sitzung bei normaler Schrift auf; ob die
  Spaltenbreite am Fenster der Testumgebung liegt, ist offen (evtl. Testumgebung).

## 7. Gesamturteil

| Bereich | Note |
|---|---|
| Installation | 3 |
| Erststart | 2+ |
| Termin-Ablauf | 2 |
| Gesamt | 2 |

**Würde ich am Prüfungstag allein damit klarkommen?** **Eher ja** (näher an Ja als im ersten Test).
Alle Aufgaben ohne Handbuch geschafft, nur einmal die Hilfe gebraucht. Unsicher bleibt Werner beim
Zeitplan (ob er so aushängbar ist) und bei der Installation bzw. dem ersten Update – dafür würde er
weiter den Enkel anrufen.

**Die drei wichtigsten Wünsche:**
1. Beim Zeitplan ausdrücklich sagen „keine Überschneidungen“ (F1).
2. Erfassung: Abbruch-Spalte breit genug, Status „disqualifiziert/Abbruch“, Zählung nach Teilnehmern (F2, F3).
3. Version-Fenster entrümpeln: Update groß, Fehlermelde-Teil abgesetzt (F5).

## 8. Abgleich mit dem ersten Test

| Früherer Fund | Stand | Begründung |
|---|---|---|
| F1 Schrift nicht vergrößerbar | behoben | „Ansicht → Schriftgröße → Normal/Groß/Sehr groß“ vorhanden und wirksam, der Tipp auf der Startseite verweist korrekt darauf. |
| F2 Demo schaltet zu schnell weiter | weitgehend behoben | Erster Text 40 s, danach Lesezeit nach Textlänge (mind. 10 s); Werner kam fast überall mit, nur einzelne Ergebnis-Zeilen standen kurz. |
| F3 Rote Zelle ohne Erklärung | behoben | Sofort Text unter der Tabelle: „Rot umrandet, so nicht speicherbar - bitte korrigieren: Nr. 43 Neumann: Trümmerfeld Suche höchstens 60 Punkte (eingegeben: 65)“. |
| F4 Mittagspause landet um 10:40 | behoben | Meldung „Keine Pause eingefügt – bei keinem Richter steht ab 12:00 Uhr noch eine Prüfung im Plan.“, keine falsche Pause im Aushang. |
| F5 Prüfung aus drei Feldern | teilweise | Weiterhin Art/LK/Disziplin, aber Vorbelegung DK und grüne Bestätigungszeile „Prüfung: Trümmer LK 2 – wird angeboten“ machen es verständlich. |
| F6 Zweiter Gegenstand gesperrt ohne Erklärung | behoben | Bei ED steht „Bei einer Einzeldisziplin gibt es nur einen Gegenstand.“ (Werner schreibt beide trotzdem in ein Feld). |
| F7 Mehrere PDFs auf einmal unklar | behoben | Fenstertitel „mehrere mit Strg-Klick markieren“; alle vier in einem Durchgang, Startnummern-Frage nur einmal. Die Grammatik für genau 1 Teilnehmer wurde nicht erlebt. |
| F8 Abbruch-Spalte nicht anklickbar | behoben | Auswahlfeld mit Pfeil, ein Klick öffnet die Liste; neu nur die zu schmale Spalte (F3 dieses Tests). |
| F9 „Gegenstand … nicht zugeordnet“ unverständlich | nicht erlebt | Bei den eingelesenen PDF-Teilnehmern stand diesmal kein solcher Hinweis in „Anmerkungen“. |
| F10 Kleinere Ungereimtheiten | weitgehend behoben | Startseite „16 (+1 abgemeldet)“, Termin vorausgewählt, Import-Meldung mit „Meldung kopieren und schließen“; Update weiter nur hinter „Version …“ (F5 dieses Tests). |
