# UX-Test 2026-11 – Persona L-B (Werner, 66)

## 1. Persona und Vorgehen

Werner, 66, Rentner, früher Kassenwart im Verein. Sitzt selten am PC, liest keine Anleitungen,
probiert Knöpfe aus, bis etwas passiert. Rote oder unverständliche Meldungen machen ihn nervös.
CSV, ZIP, PDF-Import und Datei-Dialog sind ihm kaum geläufig.

Quellen: **kein Handbuch** (auch nicht aus Verzweiflung geöffnet). Für die Installation nur die
Website `docs/index.html`, im Programm die Demoprüfung, Tooltips und das Hilfe-Fenster (Knopf „Hilfe“,
erst bei Aufgabe 15 geöffnet). Bedient wurde Version 1.0.55 über das Steuerwerkzeug (Kürzel LB).
Bilder liegen nur lokal (siehe Bericht, Abschnitt 1).

## 2. Aufgaben-Übersicht

| Nr | Aufgabe | Ergebnis | Fehlversuche | Handbuch/Hilfe nötig? | Kommentar |
|---|---|---|---|---|---|
| 0 | Installation (gedanklich) | ~ | – | Website | „Assets“, „.exe“ und die SmartScreen-Warnung schrecken ab. Dass die Warnung angekündigt wird, beruhigt. Das Update über „Version …“ hätte Werner allein nicht gefunden. |
| 1 | Erster Start, Demoprüfung | ~ | 0 | nein | Der Demo-Knopf ist sofort zu sehen. Die Demo lief vollständig durch, aber nach 10 Sekunden geht es weiter, und die langen Texte schafft Werner in der Zeit nicht. |
| 2 | Termin anlegen | ✓ | 0 | nein | Fläche und Behältnisse standen erst nach dem Bildlauf da. „Bereiche automatisch festlegen“ hat sehr geholfen. Die Rückfrage zu Verband/Meldestelle war verständlich. |
| 3 | Anmeldeformular | ✓ | 0 | nein | Aus der Demo wusste Werner, dass „Export“ der richtige Reiter ist. |
| 4 | Zwei Nachmeldungen | ~ | 1 | nein | Aus „Trümmer LK 2“ werden im Formular drei Felder (Art ED, LK 2, Disziplin Trümmerfeld). Für den zweiten Gegenstand ist das Feld gesperrt. Werner hat dann „Schlüsselbund und Socke“ in ein Feld geschrieben. |
| 5 | Mitgliederliste (CSV) | ✓ | 0 | nein | Der Knopf steht direkt im Reiter „Teilnehmer“. Die Meldung mit den 8 übersprungenen Zeilen ist klar, verschwindet aber nach OK, ohne dass sich die Liste festhalten lässt. |
| 6 | Vier Anmelde-PDFs | ~ | 0 | nein | Werner wusste nicht, wie man mehrere Dateien gleichzeitig markiert, und hat die PDFs einzeln eingelesen. Nach jeder Datei kam erneut die Frage nach den Startnummern. Die zwei Ablehnungen waren verständlich begründet. |
| 7 | Startnummern, Tausch, Absage | ✓ | 0 | nein | Die Bereiche standen schon im Termin. „Startnummer tauschen…“ und „Keine Teilnahme“ waren leicht zu finden. |
| 8 | Späte Nachmeldung | ✓ | 0 | nein | Nach „Fehlende Startnummern vergeben…“ bekam Ziegler Nr. 44, die anderen Nummern blieben unverändert. |
| 9 | Zeitplan + PDF | ~ | 0 | nein | „Automatisch verteilen…“ lief ohne Probleme. Die Mittagspause um 12:00 Uhr landete stattdessen um 10:40 bzw. 10:20 Uhr und steht so auch im Aushang. Ob es Überschneidungen gibt, konnte Werner selbst nicht beurteilen. |
| 10 | Ergebnisse eintragen | ~ | 2 | nein | Bei der 65 erschien nur ein roter Rahmen, ohne Text. Die Erklärung kam erst beim Speichern. In die Spalte „Abbruch“ kam Werner erst per Doppelklick. |
| 11 | Rangliste + Stechen | ✓ | 0 | nein | Das Programm zeigt den Hinweis „Stechen nötig …“ samt Knopf, und die Auswahl ist eindeutig. |
| 12 | PDFs erzeugen | ✓ | 0 | nein | Ergebnisliste mit „(nach Stechen)“ und „Abbruch wegen Verletzung des Hundes (ABBR)“ korrekt. |
| 13 | Datensicherung | ✓ | 0 | nein | Ohne Passwort, weil Werner Angst hat, es zu vergessen. Gespeichert wurde im vorgeschlagenen Ordner (kein USB-Stick in der Testumgebung). |
| 14 | Schließen und Neustart | ✓ | 1 | nein | Alle Daten waren noch da. „Öffnen“ ist ausgegraut, bis man eine Zeile anklickt. Auf der Startseite stehen 17 Teilnehmer, im Termin 16. |
| 15 | Eigenes Ausprobieren | ~ | – | Hilfe | Eine größere Schrift gibt es nicht, obwohl die Hilfe „Schrift … zu klein?“ anspricht. Die Hilfe ist eine lange Textwand. Die provozierten Meldungen waren freundlich. |

## 3. Stolpersteine

### F1: Schrift lässt sich nicht vergrößern, obwohl die Hilfe es andeutet
- **Schwere:** erheblich
- **Wo:** Menü „Ansicht“ → „Hintergrund“, Text auf der Startseite, Hilfe-Fenster
- **Was passiert ist:** Auf der Startseite steht „Tipp: Schrift zu blass? Im Programm oben im Menü
  „Ansicht“ → „Hintergrund“ → „Hoher Kontrast“ wählen.“ In der Hilfe heißt es sogar „Schrift zu
  blass oder zu klein? Menü „Ansicht“ → „Hintergrund“ → „Hoher Kontrast““. Nach der Umstellung ist
  alles schwarz auf weiß, die Schrift aber genauso klein wie vorher. Das Menü „Ansicht“ hat nur
  „Hintergrund“ und „Akzentfarbe“, eine Schriftgröße lässt sich nirgends einstellen. Auf der
  Startseite gibt es außerdem gar kein Menü „Ansicht“, obwohl der Tipp dort darauf verweist.
- **O-Ton:** „Da steht ‚zu klein?‘, ich klick das an, und es ist immer noch so klein. Ich muss mit der Nase an den Bildschirm.“
- **Bildschirmfoto:** `Bild LB/0316`, `…\0001.png`
- **Vorschlag:** Unter „Ansicht“ einen Punkt „Schrift größer / kleiner“ anbieten oder den Hinweis
  auf „zu klein“ streichen.

### F2: Demo schaltet für langsame Leser zu schnell weiter
- **Schwere:** mittel
- **Wo:** Fenster „Demoprüfung“
- **Was passiert ist:** Jeder Schritt erklärt auf 60–90 Wörtern, was passiert, und schaltet nach
  „Weiter (10)“ von allein weiter. Mehrere Schritte (z. B. 9 „Disqualifikation“, 11 „Auswertung“)
  liefen weiter, bevor Werner fertig gelesen hatte. Dass man den Haken „Automatisch weiter“
  herausnehmen kann, steht im ersten, ebenfalls langen Text, und auch der war schon weg.
- **O-Ton:** „Halt, halt, ich war noch gar nicht fertig! Jetzt ist der nächste Text da.“
- **Bildschirmfoto:** `Bild LB/0002`
- **Vorschlag:** Den automatischen Wechsel standardmäßig ausschalten oder die Wartezeit nach der
  Textlänge richten. Mindestens im ersten Schritt nicht automatisch weiterschalten.

### F3: Ungültige Punktzahl wird beim Tippen nur rot umrandet, ohne Erklärung
- **Schwere:** mittel
- **Wo:** Reiter „Ergebniserfassung“, Zelle „Trümmerfeld Suche (0-60)“
- **Was passiert ist:** Werner trägt laut Zettel 65 ein. Die Zelle bekommt nur einen roten Rahmen,
  in der Statusspalte steht „nicht gespeichert“ wie bei allen anderen Zeilen. Erst beim Klick auf
  „Alle Ergebnisse speichern“ erscheint das Fenster „Nicht alle Ergebnisse gespeichert“ mit dem
  Text „Folgende Zeilen konnten nicht gespeichert werden (übrige wurden gespeichert): Neumann,
  Nina – Trümmerfeld: Suche höchstens 60 Punkte (eingegeben: 65)“. Die Meldung selbst ist gut
  verständlich, kommt aber spät und mit gelbem Warndreieck.
- **O-Ton:** „Rot? Hab ich was kaputt gemacht? … Ach so, höchstens 60. Das hätte er mir auch gleich sagen können.“
- **Bildschirmfoto:** `Bild LB/0117`, `…\0281.png`
- **Vorschlag:** Schon beim Verlassen der Zelle einen kurzen Hinweis zeigen, in der Statusspalte
  „Suche höchstens 60“ statt „nicht gespeichert“.

### F4: Mittagspause „um 12:00“ landet um 10:40 und steht so im Aushang
- **Schwere:** mittel
- **Wo:** Reiter „Zeitplan“ → „Pause hinzufügen…“ mit Haken „Bei allen Richtern einfügen, um 12:00“
- **Was passiert ist:** Der Plan ist um 10:40 Uhr fertig. Nach OK kam die Meldung „Die Pause
  beginnt nicht überall um 12:00: Anna Richter: 10:40 Uhr Bernd Berger: 10:40 Uhr Clara Christ:
  10:20 Uhr … endet der Plan eines Richters vorher, steht die Pause an seinem Ende.“ Die PDF zeigt
  „10:40 – 11:25 Mittagspause“. Werner versteht nicht, warum aus 12 Uhr 10:40 Uhr wurde. Dass
  er die Pause gar nicht braucht, sagt ihm das Programm nicht. Er lässt sie stehen.
- **O-Ton:** „Ich hab 12 Uhr gesagt. Mittagspause um zwanzig vor elf, da lachen mich die Richter aus.“
- **Bildschirmfoto:** `Bild LB/0109`
- **Vorschlag:** Endet der Plan vor der Pausenzeit, die Pause nicht einfügen bzw. fragen:
  „Der Plan endet schon um 10:40 – Pause trotzdem anhängen?“

### F5: Eine Prüfung wie „Trümmer LK 2“ muss im Teilnehmerformular aus drei Feldern zusammengesetzt werden
- **Schwere:** mittel
- **Wo:** „Teilnehmer erfassen“, Felder „Art*“, „Leistungsklasse*“, „Disziplin (nur bei ED)“
- **Was passiert ist:** Im Termin heißen die Prüfungen „Trümmer LK 2“, „DK-LK 1“ usw. Im
  Teilnehmerformular muss Werner daraus Art „ED“, Leistungsklasse „2“ und Disziplin
  „Trümmerfeld“ machen. „ED“ kannte er nur aus der Demo. Vorbelegt ist ED/1/Trümmerfeld. Wer
  nichts ändert, meldet also unbemerkt für Trümmer LK 1. Angeboten werden im Formular auch nicht
  angebotene Kombinationen.
- **O-Ton:** „Wo steht denn hier Trümmer LK 2? Was ist ED?“
- **Bildschirmfoto:** `Bild LB/0042`
- **Vorschlag:** Eine Auswahlliste „Prüfung“ mit genau den angebotenen Prüfungen (wie im Termin
  benannt).

### F6: Zweiter Gegenstand bei Einzeldisziplin gesperrt, ohne Erklärung
- **Schwere:** gering
- **Wo:** „Teilnehmer erfassen“, Felder „Gegenstand 2/3“
- **Was passiert ist:** Martin Weber hat „Schlüsselbund und Socke“ gemeldet. Die Felder
  Gegenstand 2 und 3 sind ausgegraut, einen Hinweis gibt es im Formular nicht. Die Erklärung
  („Bei ED gibt es … genau einen Gegenstand“) steht nur in der Hilfe und im Demotext. Werner
  hat beide Gegenstände in Feld 1 geschrieben.
- **O-Ton:** „Da geht nur einer rein. Dann schreib ich halt beide in eins.“
- **Bildschirmfoto:** `Bild LB/0042`
- **Vorschlag:** Neben den gesperrten Feldern kurz „bei ED nur ein Gegenstand“ anzeigen.

### F7: Mehrere PDFs auf einmal einlesen – wie, steht nirgends
- **Schwere:** gering
- **Wo:** Reiter „Formular-Import“ → „Anmeldeformulare (PDF) importieren…“
- **Was passiert ist:** Laut Text sind „mehrere auf einmal möglich“, aber wie man mehrere Dateien
  markiert (Strg-Taste), steht nirgends. Werner hat vier Durchgänge gemacht. Nach jedem
  erfolgreichen Einlesen kam erneut das Fenster „Startnummern fehlen“ mit dem Text „1 Teilnehmer
  haben noch keine Startnummer …“.
- **O-Ton:** „Mehrere auf einmal? Ich kann doch nur eins anklicken.“
- **Bildschirmfoto:** `Bild LB/0072`
- **Vorschlag:** Den Satz „Mehrere Dateien mit gedrückter Strg-Taste anklicken“ ergänzen. Die
  Grammatik „1 Teilnehmer hat“ korrigieren.

### F8: Spalte „Abbruch“ sieht nicht anklickbar aus
- **Schwere:** gering
- **Wo:** Reiter „Ergebniserfassung“, Spalte „Abbruch“
- **Was passiert ist:** Die Zelle ist leer, ohne Rahmen oder Pfeil. Ein einfacher Klick zeigte
  keine Auswahl, erst ein Doppelklick öffnete die Liste „kein Abbruch / Ungehorsam / Verletzung
  Hund / …“ (evtl. Testumgebung: Mausklick per Befehl).
- **O-Ton:** „Wo trag ich denn ein, dass die Emma sich die Pfote verletzt hat?“
- **Bildschirmfoto:** `Bild LB/0279`
- **Vorschlag:** In der leeren Zelle „kein Abbruch ▾“ anzeigen, damit man sieht, dass dort eine
  Auswahl ist.

### F9: Hinweis „Gegenstand der Suchdisziplin nicht zugeordnet“ unverständlich
- **Schwere:** gering
- **Wo:** Reiter „Teilnehmer“, Spalte „Anmerkungen“ bei Nina Neumann (aus PDF eingelesen)
- **Was passiert ist:** Der Hinweis erscheint ohne Erklärung, was zu tun ist.
- **O-Ton:** „Nicht zugeordnet? Muss ich da was machen oder nicht?“
- **Bildschirmfoto:** `Bild LB/0328`
- **Vorschlag:** In einfachen Worten schreiben, z. B. „Gegenstand passt nicht zur Disziplin –
  bitte prüfen“, mit Tooltip.

### F10: Kleinere Ungereimtheiten
- **Schwere:** gering
- **Wo:** Startbildschirm, Import-Meldung, Version-Fenster
- **Was passiert ist:**
  - Auf der Startseite steht „17“ Teilnehmer, im Termin „16 Teilnehmer“ (der Abgesagte zählt nur
    auf der Startseite mit).
  - „Öffnen“ ist ausgegraut, solange keine Zeile markiert ist, obwohl es nur einen Termin gibt.
  - Nach dem CSV-Import verschwindet die Liste der 8 übersprungenen Meldungen mit OK. Werner hätte
    sie gern ausgedruckt oder kopiert.
  - Updates findet man hinter dem Knopf „Version 1.0.55“, dort ist von der
    „GitHub-Releases-Seite“ die Rede.
- **O-Ton:** „Die acht Namen muss ich mir jetzt abschreiben, bevor ich OK drücke.“
- **Bildschirmfoto:** `…\0309.png`, `…\0065.png`, `…\0325.png`
- **Vorschlag:** Die Zahlen angleichen. Einen einzelnen Termin vorauswählen. In der
  Import-Meldung einen Knopf „Kopieren/Drucken“ anbieten. Einen eigenen Knopf
  „Nach Updates suchen“ statt „Version“.

## 4. Was gut lief

- Der Knopf „Demoprüfung“ ist auf der Startseite sofort zu sehen. Die Demo hat gezeigt, welche
  Reiter es gibt und in welcher Reihenfolge man sie benutzt. Ohne sie hätte Werner „Export“,
  „Stechen“ und „Abbruch“ nicht gefunden.
- „Bereiche automatisch festlegen“ im Termin: ein Klick, und jede Prüfung hat ihren Bereich.
- „Fehlende Startnummern vergeben…“ verändert bestehende Nummern nicht. Die späte Nachmeldung
  bekam die 44 im richtigen Bereich.
- „Keine Teilnahme“: Der Abgesagte bleibt grau in der Liste und fehlt in Zeitplan und Ergebnissen.
- Die Fehlermeldungen sind freundlich und konkret: Datum („bitte z. B. 14.11.2026 eingeben“),
  nicht angebotene Prüfungen mit Namen und Zeile, abgelehnte PDFs mit Grund, „Bitte zuerst einen
  Eintrag in der Liste auswählen.“ Keine davon hat Werner in Panik versetzt.
- Das Stechen ist vorbildlich: Hinweis „Stechen nötig …“ mit Namen, ein Knopf, eine Auswahl, danach
  „1. von 4 (nach Stechen)“.
- Speichern-Fenster schlagen immer einen sinnvollen Dateinamen und Ordner vor, Werner musste nur
  „Speichern“ drücken.
- Nach dem Neustart war alles noch da.

## 5. Neue Funktionen im Urteil der Persona

**Demoprüfung:** Hat beim Lernen am meisten geholfen. Werner wusste danach, wo Export, Stechen
und Abbruch zu finden sind. Für ihn liefen die Schritte aber zu schnell (F2). Den Haken
„Automatisch weiter“ hätte er gebraucht, hat ihn aber nicht bemerkt.

**Startnummern-Bereiche/Vergabe:** Sehr gut. „Bereiche automatisch festlegen“ und „Fehlende
Startnummern vergeben…“ erledigen alles, und die Rückfrage nach dem Import bietet die Vergabe von
selbst an. Werner musste nichts rechnen.

**Stechen:** Klar und einfach. Das Programm sagt, dass ein Stechen nötig ist, und wer es gewonnen
hat, wählt man aus einer Liste.

**Abbruch mit Grund:** Fachlich gut (Grund steht ausgeschrieben in Rangliste und PDF). Die Spalte
ist aber schwer zu finden bzw. zu öffnen (F8).

**Aussehen:** Der dunkle Kopfbalken mit Hundekopf, Verein, Datum und Teilnehmerzahl gefällt Werner
und hilft beim Orientieren. „Hoher Kontrast“ ist gut lesbar, die Schrift bleibt aber zu klein
(F1). Die Symbole (Warndreieck bei „Chip-Nr. fehlt“, grüne Haken bei „Offene Starts“) versteht er.

**Fehlermeldungen allgemein:** Ganz überwiegend freundlich, auf Deutsch und mit konkretem Vorschlag.
Nur der rote Rahmen ohne Text (F3) und einige Fachbegriffe in Hinweisen (F9, „GitHub-Releases“)
haben Werner unsicher gemacht.

## 6. Grenzen dieses Tests

- Die Installation wurde nur gedanklich anhand der Website bewertet. SmartScreen-Warnung, Download-
  Blockade und „Assets“-Liste auf GitHub hat Werner also nicht wirklich gesehen.
- Statt des Windows-Explorer-Dialogs kam der englische Qt-Ersatzdialog. Ob Werner den USB-Stick
  im echten Dialog findet, ist nicht getestet. Mehrfachauswahl wäre im echten Dialog genauso
  unbekannt.
- Bedienung per Befehl statt Maus. Kein Mausrad und kein Hover. Bei F8 kann der einfache Klick an
  der Testumgebung liegen.
- „Nach Updates suchen“ wurde nicht geklickt (kein echter Update-Test).
- Lesegeschwindigkeit bei der Demo: Werners zu langsames Lesen ist gespielt. Gezählt hat, wie viel
  Text in 10 Sekunden zu lesen ist.
- Harness-Probleme: keine. Nach `schliessen` meldete das Werkzeug „DAS PROGRAMM IST NICHT MEHR DA“.
  Das war das gewünschte Programmende, kein Absturz.

## 7. Gesamturteil

| Bereich | Note |
|---|---|
| Installation | 3 |
| Erststart | 2 |
| Termin-Ablauf | 2– |
| Gesamt | 2– |

**Würde ich am Prüfungstag allein damit klarkommen?** **Eher ja.** Mit der Demo im Kopf hat Werner
alle Aufgaben ohne Handbuch geschafft, teils mit Umwegen. Unsicher bleibt er bei kleinen Schriften,
beim Zeitplan (Pause, Überschneidungen beurteilen) und bei Meldungen ohne Text (roter Rahmen). Für
die Installation und das erste Update würde er den Enkel anrufen.

**Die drei wichtigsten Wünsche:**
1. Schriftgröße im Menü „Ansicht“ einstellbar machen (F1).
2. Demo langsamer, ohne automatisches Weiterschalten oder Wartezeit nach Textlänge (F2).
3. Im Teilnehmerformular die Prüfung direkt aus den angebotenen Prüfungen wählen („Trümmer LK 2“),
   statt Art/LK/Disziplin einzeln (F5).
