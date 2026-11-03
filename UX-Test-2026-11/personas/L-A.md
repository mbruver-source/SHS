# UX-Test 2026-11 – Bericht L-A (Gerda, 71, mit ausgedrucktem Handbuch)

## 1. Persona und Vorgehen

Gerda ist 71 und seit vielen Jahren im Verein. Am PC schreibt sie E-Mails und schaut Fotos an. Sie liest jede Meldung wörtlich und hat Angst, etwas kaputt zu machen. Das Handbuch (`docs\HANDBUCH.md`) hat sie ausgedruckt und arbeitet es Schritt für Schritt durch, vor allem Kapitel 14 „Die erste Prüfung Schritt für Schritt“, dazu Kapitel 3 bis 7 und das Glossar. Die Installation hat sie gedanklich mit Kapitel 2 und der Website (`docs\index.html`) durchgespielt. Die Hilfe im Programm hat sie in Aufgabe 15 geöffnet. Das Programm hat sie über das Steuerwerkzeug bedient.

## 2. Aufgaben-Übersicht

| Nr | Aufgabe | Ergebnis | Fehlversuche | Handbuch/Hilfe nötig? | Kommentar |
|---|---|---|---|---|---|
| 0 | Installation (gedanklich) | ~ | – | ja (Kap. 2) | Die Browser-Warnungen („Gefährliche Datei behalten“, „Trotzdem ausführen“) machen ihr Angst. Ohne den Ausdruck hätte sie abgebrochen und den Enkel angerufen. Das Update über „Version …“ ist verständlich. |
| 1 | Erster Start, Demoprüfung ganz ansehen | ✓ | 0 | nein (Knopf ist gut sichtbar) | Die Demo lief bis „Fertig“ durch. 10 Sekunden je Schritt sind für lange Texte knapp (siehe F6). |
| 2 | Termin anlegen | ✓ | 0 | ja (Kap. 14, Schritt 1) | „Bereiche automatisch festlegen“ hat sofort sinnvolle Bereiche vergeben. |
| 3 | Anmeldeformular erzeugen | ✓ | 0 | ja (Kap. 14, Schritt 2) | Ging problemlos. |
| 4 | Zwei Nachmeldungen von Hand | ~ | 1 | ja (Kap. 4, Suchgegenstände) | Bei Weber (ED) ließ sich „Socke“ nicht eintragen, weil Gegenstand 2 gesperrt ist. Erst das Handbuch hat erklärt, warum. Im Fenster selbst steht kein Hinweis. |
| 5 | Mitgliederliste (CSV) | ✓ | 0 | ja (Kap. 5) | Die Meldung nennt 8 nicht angebotene Prüfungen mit Namen und dem Rat „Bitte mit dem Teilnehmer klären“. Das war klar. |
| 6 | Vier Anmelde-PDFs | ✓ | 0 | ja (Mehrfachauswahl mit Strg) | Beide Fehler wurden erkannt: Pfeiffer hat zwei Prüfungen angekreuzt, Quast hat Fläche LK 3 gewählt, die nicht angeboten wird. Danach stand bei Neumann eine rätselhafte Anmerkung (F3). |
| 7 | Startnummern, Tausch, Absage Pohl | ✓ | 0 | ja (Strg-Klick, „Keine Teilnahme“) | Die Bereiche gab es schon aus Aufgabe 2. Tausch und „Keine Teilnahme“ gingen leicht. |
| 8 | Späte Nachmeldung Ziegler | ✓ | 0 | ja (Kap. 4, Erfassungsmaske) | Nach dem Entfernen des Hakens „Startnummer steht noch nicht fest“ schlug das Programm Nr. 44 im Trümmer-LK-1-Bereich vor. |
| 9 | Zeitplan mit Mittagspause, PDF | ~ | 0 | ja (Kap. 14, Schritt 5) | Der Plan ist um 10:40 Uhr fertig. Die „Mittagspause 12:00“ landete deshalb um 10:20 bzw. 10:40 Uhr am Planende (F2). Überschneidungen gab es keine. |
| 10 | Ergebnisse, Disqualifikation, Abbruch | ~ | 2 | ja (Kap. 7) | Die 65 wurde erst beim Speichern abgelehnt; die Meldung war klar. Die Abbruch-Zelle sieht nach einem leeren Kästchen aus und öffnet sich erst beim zweiten Klick (F4). |
| 11 | Rangliste und Stechen | ✓ | 0 | nein | Der Hinweis „Stechen nötig … danach ‚Stechen-Sieger festlegen…‘“ führt direkt zum Ziel. |
| 12 | PDFs erzeugen, Ergebnisliste prüfen | ✓ | 0 | ja (Kap. 9) | Die Ergebnisliste zeigt „1. von 4 (nach Stechen)“, „Abbr. … Abbruch wegen Verletzung des Hundes (ABBR)“ und „Disq.“. |
| 13 | Datensicherung | ✓ | 0 | ja (Kap. 10) | Ohne Passwort gesichert, weil sie Angst hat, es zu vergessen. Den Speicherort hat sie nicht geändert (USB-Stick siehe Grenzen). |
| 14 | Neustart, alles noch da? | ✓ | 1 | nein | Alles war noch da. „Öffnen“ blieb ausgegraut, bis sie die Zeile angeklickt hatte. Die Startseite zeigt 17 Teilnehmer, der Kopfbalken 16 (F7). |
| 15 | Eigenes Ausprobieren | ~ | – | Hilfe gelesen | Gerda wollte eine größere Schrift. Es gibt nur „Hoher Kontrast“, die Schrift bleibt gleich klein (F1). Die Rückfrage beim Löschen ist vorbildlich. |

## 3. Stolpersteine

### F1: Schrift lässt sich nicht vergrößern, die Hilfe verspricht es aber
- **Schwere:** erheblich
- **Wo:** Menü „Ansicht“ → „Hintergrund“, Hilfe-Fenster, Hinweis auf dem Startbildschirm
- **Was passiert ist:** Die Hilfe beginnt mit „Schrift zu blass oder zu klein? Menü ‚Ansicht‘ → ‚Hintergrund‘ → ‚Hoher Kontrast‘“. Gerda hat „Hoher Kontrast“ gewählt. Der Kontrast wird besser, die Schrift bleibt aber genauso klein. Eine Einstellung für die Schriftgröße gibt es nicht. Im großen Fenster (über 1900 Pixel breit) sind Tabellen und Knöpfe sehr klein beschriftet.
- **O-Ton:** „Da steht ‚zu klein?‘, und dann wird es nur schwarz-weiß. Ich brauche meine Lesebrille trotzdem, und auch mit der muss ich ganz nah ran.“
- **Bildschirmfoto:** `Bild LA/0303`, `…\0007.png`
- **Vorschlag:** Unter „Ansicht“ einen Punkt „Schriftgröße“ (normal / groß / sehr groß) anbieten. Solange es den nicht gibt, in der Hilfe nicht „zu klein“ versprechen.

### F2: Die „Mittagspause um 12:00“ landet um 10:20 Uhr
- **Schwere:** mittel
- **Wo:** Reiter „Zeitplan“ → „Pause hinzufügen…“ → Haken „Bei allen Richtern einfügen, um 12:00 Uhr“
- **Was passiert ist:** Der Plan ist um 10:40 Uhr fertig. Die Meldung lautete: „Die Pause beginnt nicht überall um 12:00: Anna Richter: 10:40 Uhr / Bernd Berger: 10:40 Uhr / Clara Christ: 10:20 Uhr. Ein laufender Prüfungsblock wird nicht geteilt; endet der Plan eines Richters vorher, steht die Pause an seinem Ende.“ Im Plan steht jetzt zum Beispiel „10:20–11:05 Pause: Mittagspause“. So landet es auch im Aushang-PDF. Gerda wusste nicht, ob sie die Pause wieder entfernen soll oder darf.
- **O-Ton:** „Eine Mittagspause um zwanzig nach zehn? Die Richter sind doch dann schon fertig. Und jetzt steht das so auf dem Zettel für den Aushang. Mache ich das wieder weg, oder geht dann was kaputt?“
- **Bildschirmfoto:** `Bild LA/0098`
- **Vorschlag:** Ist der Plan vor der Uhrzeit fertig, gar keine Pause einfügen und das sagen, zum Beispiel: „Bei allen Richtern ist der Plan vor 12:00 Uhr beendet – keine Pause nötig.“ Oder fragen, ob die Pause trotzdem rein soll.

### F3: Rätselhafte Anmerkung nach dem PDF-Import
- **Schwere:** mittel
- **Wo:** Reiter „Teilnehmer“, Spalte „Anmerkungen“ bei Neumann (aus der PDF-Anmeldung)
- **Was passiert ist:** Direkt nach dem Import stand dort „Gegenstand der Suchdisziplin nicht zugeordnet“. Im Bearbeiten-Fenster steht bei „gesucht in“ aber schon „Trümmerfeld“. Das Handbuch erklärt die Anmerkung nur für „ED (ältere Daten)“ mit dem Rat „Einmal öffnen und speichern behebt das“. Der Import war aber ganz neu. Nach „OK“ war die Anmerkung tatsächlich weg.
- **O-Ton:** „Was habe ich denn da falsch gemacht? Im Fenster steht doch Trümmerfeld. Und im Heft steht ‚ältere Daten‘, das ist doch gerade erst gekommen.“
- **Bildschirmfoto:** `Bild LA/0073`
- **Vorschlag:** Beim Import einer Einzeldisziplin den Gegenstand gleich der Disziplin zuordnen. Dann gibt es den Hinweis gar nicht erst.

### F4: Die Abbruch-Zelle sieht nicht nach Auswahlliste aus
- **Schwere:** mittel
- **Wo:** Reiter „Ergebniserfassung“, Spalte „Abbruch“
- **Was passiert ist:** In der Zelle steht nur ein leeres, flaches Kästchen ohne Pfeil. Der erste Klick markiert die Zelle bloß. Erst der zweite Klick öffnet die Liste „kein Abbruch / Ungehorsam / Verletzung Hund / Krankheit / Verletzung HF“. Das Handbuch sagt: „Die Leertaste (oder ein Klick) … klappt bei ‚Abbruch‘ die Auswahlliste auf.“
- **O-Ton:** „Ich hab draufgeklickt, und es kam nichts. Im Heft steht, ein Klick reicht. Erst beim zweiten Mal ging das Menü auf.“
- **Bildschirmfoto:** `Bild LA/0273`
- **Vorschlag:** In die Zelle ein kleines Pfeilsymbol und den Text „kein Abbruch“ setzen. Die Liste sollte schon beim ersten Klick aufgehen.

### F5: Gesperrte Felder ohne Erklärung (Gegenstand bei ED)
- **Schwere:** mittel
- **Wo:** „Teilnehmer erfassen“, Gegenstand 2 und 3 bei einer Einzeldisziplin (ED)
- **Was passiert ist:** Laut Meldung hatte Weber zwei Gegenstände („Schlüsselbund und Socke“). Gegenstand 2 ließ sich nicht anklicken. Gesperrte und offene Felder haben fast denselben beigen Farbton, und im Fenster steht kein Hinweis, warum ein Feld gesperrt ist. Erst das Handbuch erklärt „bei ED genau ein Gegenstand“. Gerda hat nur „Schlüsselbund“ eingetragen und sich notiert, nachzufragen.
- **O-Ton:** „Das Kästchen sieht aus wie die anderen, aber ich komm nicht rein. Ist da was kaputt?“
- **Bildschirmfoto:** `Bild LA/0036`
- **Vorschlag:** Gesperrte Felder deutlich grau zeigen. Neben Gegenstand 2 und 3 einen kurzen Text: „Bei Einzeldisziplin nur ein Gegenstand“.

### F6: 10 Sekunden je Demo-Schritt sind für lange Texte knapp
- **Schwere:** gering
- **Wo:** Demoprüfung, Erklärfenster, „Automatisch weiter“
- **Was passiert ist:** Schritte wie „11. Auswertung“ haben rund 70 Wörter mit Punktgrenzen. Nach 10 Sekunden ging es weiter. Gerda hätte den Haken „Automatisch weiter“ herausnehmen können. Sie traute sich aber nicht, weil sie dachte, dann bleibe die Demo stehen.
- **O-Ton:** „Ich war noch beim zweiten Satz, da war schon das Nächste da.“
- **Bildschirmfoto:** `Bild LA/0002`
- **Vorschlag:** Die Wartezeit an die Textlänge anpassen. Oder gleich am Anfang fragen: „Möchtest du selbst weiterklicken?“

### F7: Verschiedene Teilnehmerzahlen
- **Schwere:** gering
- **Wo:** Startbildschirm („17“) und Kopfbalken („16 Teilnehmer“)
- **Was passiert ist:** Peter Pohl ist mit „Keine Teilnahme“ markiert. Der Startbildschirm zählt ihn mit, der Kopfbalken nicht.
- **O-Ton:** „Vorhin 16, jetzt 17. Ist da einer doppelt reingerutscht?“
- **Bildschirmfoto:** `Bild LA/0298`
- **Vorschlag:** Überall gleich zählen, oder „17 (1 abgesagt)“ schreiben.

### F8: Tooltip „Dort zuerst …“ ohne Bezug
- **Schwere:** gering
- **Wo:** Reiter „Export“, Tooltip am Knopf „Anmeldeformular (PDF)…“
- **Was passiert ist:** Der Tooltip beginnt mit „Dort zuerst die angebotenen Prüfungen anhaken.“ Wo „dort“ ist, steht nur in der Zeile daneben („aus dem Reiter ‚Verwaltung‘“).
- **O-Ton:** „Dort? Wo dort?“
- **Bildschirmfoto:** `Bild LA/0031`
- **Vorschlag:** „Im Reiter ‚Verwaltung‘ zuerst die angebotenen Prüfungen anhaken.“

### F9: „Öffnen“ bleibt ausgegraut, obwohl nur ein Termin da ist
- **Schwere:** gering
- **Wo:** Startbildschirm nach dem Neustart
- **Was passiert ist:** Es gibt nur einen Termin, trotzdem ist „Öffnen“ ausgegraut, bis die Zeile angeklickt ist.
- **O-Ton:** „Warum geht Öffnen nicht? Ach so, erst draufklicken.“
- **Bildschirmfoto:** `Bild LA/0298`
- **Vorschlag:** Den obersten (neuesten) Termin schon beim Start markieren.

### F10: Für Pfeiffer fehlt der Rat, was zu tun ist
- **Schwere:** gering
- **Wo:** Meldung „Import abgeschlossen“ nach dem PDF-Import
- **Was passiert ist:** Bei Quast steht „Bitte mit dem Teilnehmer klären“. Bei Pfeiffer steht nur „mehrere Prüfungen angekreuzt (Trümmer LK 1, Fläche LK 1) - je Formular ist nur eine Prüfung möglich“, ohne Rat und ohne Punkt am Satzende.
- **O-Ton:** „Und was mach ich jetzt mit der Frau Pfeiffer? Anrufen, nehme ich an.“
- **Bildschirmfoto:** `Bild LA/0068`
- **Vorschlag:** Auch hier ergänzen: „Bitte nachfragen, welche Prüfung gemeint ist, und den Teilnehmer von Hand anlegen.“

## 4. Was gut lief

- Der Knopf „Demoprüfung“ ist sofort zu sehen. Die Demo zeigt den ganzen Ablauf in der richtigen Reihenfolge und räumt danach selbst auf.
- Kapitel 14 im Handbuch passt Schritt für Schritt zum Programm. Die fett gedruckten Knopfnamen stimmen mit den Knöpfen im Programm überein.
- „Bereiche automatisch festlegen“ vergibt mit einem Klick vernünftige Startnummern-Bereiche. Die Frage „Jetzt Fehlende Startnummern vergeben?“ nach jedem Import nimmt Gerda die Entscheidung ab.
- Die Import-Meldungen nennen Namen und Grund in klarem Deutsch.
- Beim Tausch der Startnummern nennt die Rückfrage beide Namen samt Nummern. Beim Löschen steht der Standard auf „Nein“, und das Wort „unwiderruflich“ ist deutlich.
- Die Meldung zur falschen Punktzahl war eindeutig: „Neumann, Nina – Trümmerfeld: Suche höchstens 60 Punkte (eingegeben: 65)“. Die übrigen Zeilen wurden trotzdem gespeichert.
- Die Gelb-Markierung „nicht gespeichert“ und der grüne Haken „gespeichert“ sind gut verständlich.
- Nach jedem PDF erscheint ein Fenster mit „Gespeichert unter …“, „PDF öffnen“ und „Ordner zeigen“.
- Nach dem Neustart war alles noch da, auch das Ergebnis des Stechens.

## 5. Neue Funktionen im Urteil der Persona

**Demoprüfung:** Sie hat sehr geholfen. Gerda wusste danach, in welcher Reihenfolge die Reiter drankommen und was „Stechen“ und „Abbruch“ im Programm bedeuten. Die Texte waren ihr teils zu lang für 10 Sekunden. Den farbigen Rahmen fand sie gut.

**Startnummern-Bereiche und Vergabe:** Das war für Gerda die angenehmste Überraschung. Bereiche gab es per Knopf, die Nummern per „Ja“. Bei der Nachmeldung kam die passende Nummer 44 von selbst. Dass der Knopf „Bereiche automatisch festlegen“ „überschreibt“, stand klein darunter. Das hat ihr kurz Angst gemacht, war beim neuen Termin aber unkritisch.

**Stechen:** Klar geführt. Der Hinweistext nennt den Knopf, und das Auswahlfenster nennt beide Teams mit Punkten. In der Ergebnisliste steht „(nach Stechen)“.

**Abbruch mit Grund:** Fachlich gut, die Ergebnisliste schreibt den Grund aus. Die Zelle in der Erfassung ist aber schwer als Auswahl zu erkennen (F4).

**Aussehen:** Der dunkle Kopfbalken mit dem Beagle gefällt ihr („wie ein Vereinsabzeichen“), und Datum, Ort und Zahl stehen oben gut lesbar. Die beigen Felder sind aber kontrastarm. Gesperrte und offene Felder sehen fast gleich aus, und die Schrift ist zu klein (F1, F5). „Hoher Kontrast“ hilft beim Kontrast, nicht bei der Größe.

**Fehlermeldungen allgemein:** Sie sind meist höflich, konkret und nennen Namen. Sie sind kein Fachchinesisch, mit wenigen Ausnahmen wie „Suchdisziplin nicht zugeordnet“ (F3).

## 6. Grenzen dieses Tests

- Das Dateifenster war der englische Qt-Ersatz („Look in“, „File name“, „Save“) statt des Windows-Explorers. Ob Gerda im echten Explorer ihren USB-Stick findet, wurde nicht geprüft. Gesichert wurde deshalb am vorgeschlagenen Ort.
- „PDF öffnen“ und „Ordner zeigen“ öffnen in der Testumgebung nichts. Die Ergebnisliste wurde als Text gelesen.
- Bedient wurde per Befehl statt Maus. Tooltips standen im Zustand, ein Hover war nicht nötig. Deshalb lässt sich nicht sagen, ob Gerda die Tooltips in echt überhaupt gefunden hätte.
- „Programm ist nicht mehr da“ nach dem Schließen über das X in Aufgabe 14 war gewollt (Programmende) und ist kein Absturz.
- Die Installation wurde nur gedanklich durchgespielt.
- Kein Harness-Fehler aufgetreten. Die Demo lief vollständig im Auto-Modus durch.
- Die Mehrfachauswahl im Dateifenster (Strg-Klick) und das Zellen-Tippen geschahen per Befehl. Ob Gerda mit der Maus Strg-Klick schafft, ist offen.

## 7. Gesamturteil

| Bereich | Note |
|---|---|
| Installation | 4 (die Warnungen schrecken ab; ohne den Ausdruck hätte sie abgebrochen) |
| Erststart | 2 (Demo-Knopf sofort da, Demo hilfreich) |
| Termin-Ablauf | 2– (mit Handbuch fast alles geschafft; Pause, Abbruch-Zelle und ED-Gegenstand haben gehakt) |
| Gesamt | 2–3 |

**„Würde ich am Prüfungstag allein damit klarkommen?“** – **Eher ja**, mit dem ausgedruckten Handbuch daneben. Die Ergebniserfassung und die Ausdrucke gingen gut. Unsicher wäre sie bei allem, was vom Normalfall abweicht (Pause außerhalb des Plans, gesperrte Felder), und bei der kleinen Schrift auf dem Vereins-Laptop.

**Die drei wichtigsten Wünsche:**
1. Eine einstellbare Schriftgröße unter „Ansicht“ (F1).
2. Keine „Mittagspause“ am Planende einfügen, wenn der Plan vor der Uhrzeit endet (F2).
3. Gesperrte Felder und Auswahlzellen eindeutig erkennbar machen, mit einem kurzen Grund (F4, F5).
