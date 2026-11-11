# UX-Test 2026-11 – Persona N-B (Tobias, 41, Kassenwart)

## 1. Persona und Vorgehen

Tobias ist Kassenwart und hat die Prüfung „übernommen“, weil sonst keiner wollte. Er hat normale
PC-Kenntnisse und wenig Geduld. Meldungen liest er nur an und bestätigt sie meist mit Enter bzw. dem
vorausgewählten Knopf. Nachgeschaut wird erst, wenn etwas offensichtlich schiefgeht.

Quellen: **kein Handbuch**. Für die Installation (Aufgabe 0) nur die Website `docs/index.html`, im
Programm die Demoprüfung, Tooltips und einmal kurz die „Hilfe“ (Aufgabe 15). Das Handbuch wurde zu
keinem Zeitpunkt geöffnet. Bedient wurde über das Steuerwerkzeug, Kürzel NB. Dialoge hat Tobias bewusst
oft mit `taste enter` bestätigt, um zu prüfen, was der vorausgewählte Knopf bewirkt.

## 2. Aufgaben-Übersicht

| Nr | Aufgabe | Ergebnis | Fehlversuche | Handbuch/Hilfe nötig? | Kommentar |
|---|---|---|---|---|---|
| 0 | Installation (gedanklich) | ✓ | 0 | nein (Website) | Website erklärt Download, SmartScreen-Warnung und Update kurz und klar. |
| 1 | Erster Start, Demoprüfung | ✓ | 1 | nein | Demo sofort gefunden (Knopf oben rechts). Enter im Demo-Fenster bewirkt nichts (F6). |
| 2 | Termin anlegen | ✓ | 0 | nein | „Bereiche automatisch festlegen“ ist ein Volltreffer. Rückfrage zu fehlendem Verband/Meldestelle mit Enter übergangen. |
| 3 | Anmeldeformular | ✓ | 0 | nein | Export → erster Knopf, Enter, fertig. |
| 4 | Zwei Nachmeldungen | ~ | 0 | nein | Bei Weber (ED) gibt es nur ein Gegenstandsfeld. Tobias schrieb „Schlüsselbund, Socke“ hinein, das Programm nahm es kommentarlos an (F4). |
| 5 | Mitgliederliste CSV | ✓ | 0 | nein | 12 importiert, 8 übersprungen, jeweils mit Grund. Nach dem Wegklicken ist die Liste aber weg (F3). |
| 6 | Vier Anmelde-PDFs | ✓ | 0 | nein | Gründe gut erkennbar: Pfeiffer hat zwei Prüfungen angekreuzt, Quast hat Fläche LK 3 gewählt, die nicht angeboten wird. |
| 7 | Startnummern, Tauschen, Absage | ✓ | 0 | nein | Nummern schon beim Import per „Ja“ vergeben. Tauschen und „Keine Teilnahme“ ohne Suchen gefunden. Im Tausch-Dialog ist allerdings ein falscher Partner vorausgewählt (F2). |
| 8 | Späte Nachmeldung Ziegler | ✓ | 0 | nein | „Fehlende Startnummern vergeben…“ gab Nr. 44, die anderen Nummern blieben unverändert. |
| 9 | Zeitplan + PDF | ~ | 0 | nein | Automatisch verteilen geht problemlos. Die Mittagspause „um 12:00 bei allen“ landet aber um 10:20 bzw. 10:40 (F1). |
| 10 | Ergebnisse eintragen | ✓ | 2 | nein | 65 wurde zuerst angenommen und nur rot umrandet, erst beim Speichern kam die Meldung (F5). Die Abbruch-Spalte braucht einen Doppelklick (F7). |
| 11 | Rangliste + Stechen | ✓ | 0 | nein | Hinweis „Stechen nötig…“ und der Knopf daneben sind selbsterklärend. |
| 12 | PDFs erzeugen | ✓ | 0 | nein | Ergebnisliste zeigt „1. von 4 (nach Stechen)“, „Abbr.“ mit Grund und „Disq.“. |
| 13 | Datensicherung | ✓ | 0 | nein | Enter → ohne Passwort → Speichern. Der Dateiname nennt nur einen Termin, obwohl alle gesichert werden (F9). |
| 14 | Schließen + Neustart | ✓ | 0 | nein | Alles noch da. Der Startbildschirm zeigt 17 Teilnehmer, der Kopfbalken 16 (F8). |
| 15 | Eigenes Ausprobieren | ✓ | 0 | Hilfe kurz | Hilfe ist eine lange Textwand (F10). Ansicht → Dunkel funktioniert. Lösch- und Ersetzen-Rückfragen stehen sicher auf „Nein“. |

## 3. Stolpersteine

### F1: Mittagspause „bei allen Richtern um 12:00“ landet um 10:20 bzw. 10:40
- **Schwere:** mittel
- **Wo:** Reiter „Zeitplan“ → „Pause hinzufügen…“ → Haken „Bei allen Richtern einfügen, um 12:00 Uhr“
- **Was passiert ist:** Der Plan endet bei allen Richtern vor 12 Uhr (10:20 bzw. 10:40). Nach OK kam:
  „Die Pause beginnt nicht überall um 12:00: Anna Richter: 10:40 Uhr Bernd Berger: 10:40 Uhr Clara
  Christ: 10:20 Uhr Ein laufender Prüfungsblock wird nicht geteilt; endet der Plan eines Richters
  vorher, steht die Pause an seinem Ende.“ Tobias hat das mit Enter weggeklickt. Im Zeitplan-PDF steht
  jetzt „10:40 – 11:25 Mittagspause“ bzw. „10:20 – 11:05“. Das soll ausgehängt werden.
- **O-Ton:** „Mittagspause um zwanzig nach zehn? Das häng ich so nicht ans Brett, da lachen die mich aus.
  Ich hab doch 12 Uhr eingetippt!“
- **Bildschirmfoto:** `Bild NB/0093`
- **Vorschlag der Persona:** Wenn der Plan vor der Pause endet, keine Pause einfügen und das deutlich
  sagen („Plan endet schon um 10:40, keine Mittagspause nötig“). Alternativ fragen, ob die Pause trotzdem
  um 12:00 stehen soll.

### F2: „Startnummer tauschen“ hat einen beliebigen Partner vorausgewählt
- **Schwere:** mittel
- **Wo:** Reiter „Teilnehmer“ → „Startnummer tauschen…“
- **Was passiert ist:** Otto war markiert. Im Dialog „Startnummer von Otto, Olga (aktuell: 1) tauschen
  mit:“ war „Pohl, Peter (Start-Nr. 2)“ schon ausgewählt, der Fokus lag auf der Liste. Ein Enter hätte
  Otto mit Pohl getauscht statt mit Quandt. Tobias hat hier ausnahmsweise hingeschaut und Quandt
  gewählt. Bei seiner sonstigen Enter-Gewohnheit wäre der Tausch falsch gelaufen, ohne dass er es merkt.
- **O-Ton:** „Hoppla, der will mit Pohl tauschen? Hätte ich fast durchgedrückt.“
- **Bildschirmfoto:** `Bild NB/0074`
- **Vorschlag der Persona:** Nichts vorauswählen („– bitte wählen –“) und OK erst freigeben, wenn ein
  Partner gewählt ist. Oder: Sind zwei Teilnehmer markiert, diese beiden direkt tauschen.

### F3: Liste der übersprungenen Meldungen ist nach dem Wegklicken weg
- **Schwere:** mittel
- **Wo:** „Teilnehmerliste einlesen (Excel/CSV)…“ → Fenster „Import abgeschlossen“; ebenso beim PDF-Import
- **Was passiert ist:** Die Meldung nennt acht übersprungene Zeilen mit Namen und Grund („Zeile 8
  (Greta Graf): Fläche LK 2 wird in diesem Termin nicht angeboten. Bitte mit dem Teilnehmer klären.“
  usw.). Tobias drückte sofort Enter, danach kam direkt die nächste Frage („14 Teilnehmer haben noch
  keine Startnummer…“). Wem er absagen muss, findet er nirgends mehr im Programm.
- **O-Ton:** „Da stand irgendwas von acht Leuten … wer war das nochmal? Jetzt muss ich die CSV
  durchgucken.“
- **Bildschirmfoto:** `Bild NB/0060`
- **Vorschlag der Persona:** Einen Knopf „Liste kopieren/speichern“ in die Meldung setzen oder die
  abgelehnten Meldungen irgendwo im Programm aufbewahren (z. B. im Reiter „Formular-Import“: „Zuletzt
  abgelehnt“).

### F4: Zwei Gegenstände bei ED – nur ein Feld, das Programm nimmt alles stillschweigend an
- **Schwere:** gering
- **Wo:** „Teilnehmer erfassen“, Art ED, „Gegenstand 1“
- **Was passiert ist:** Laut Nachmeldung hat Weber zwei Gegenstände (Schlüsselbund und Socke). Bei ED
  ist nur „Gegenstand 1“ aktiv, also schrieb Tobias „Schlüsselbund, Socke“ in das Feld. Es kam kein
  Hinweis. Dass bei ED genau ein Gegenstand gilt, steht nur in der Hilfe und kurz in der Demo.
- **O-Ton:** „Gibt halt nur ein Feld, dann kommt eben beides rein. Passt schon.“
- **Bildschirmfoto:** `Bild NB/0057`
- **Vorschlag der Persona:** Neben dem Feld kurz „ED: genau ein Gegenstand“ anzeigen. Bei Komma oder
  „und“ im Feld einmal nachfragen.

### F5: Ungültige Punktzahl (65 > 60) wird beim Tippen nur rot umrandet
- **Schwere:** gering
- **Wo:** Reiter „Ergebniserfassung“, Spalte „Trümmerfeld Suche (0-60)“
- **Was passiert ist:** 65 eingetippt und Tab gedrückt. Die Zelle bekam einen roten Rahmen, sonst geschah
  nichts. Erst bei „Alle Ergebnisse speichern“ kam: „Folgende Zeilen konnten nicht gespeichert werden
  (übrige wurden gespeichert): Neumann, Nina – Trümmerfeld: Suche höchstens 60 Punkte (eingegeben:
  65)“. Diese Meldung ist gut und eindeutig. Den roten Rahmen hat Tobias allerdings übersehen.
- **O-Ton:** „Ah, beim Speichern meckert er. Okay, das ist fair – aber hätte er mir auch gleich sagen können.“
- **Bildschirmfoto:** `Bild NB/0219`, `…\0229.png`
- **Vorschlag der Persona:** Beim Verlassen der Zelle einen kurzen Hinweis in der Statuszeile oder als
  Tooltip zeigen („höchstens 60“).

### F6: Enter im Demo-Fenster bewirkt nichts
- **Schwere:** gering
- **Wo:** Fenster „Demoprüfung“, Einführung
- **Was passiert ist:** Der Fokus liegt auf dem Haken „Automatisch weiter“. Enter wirkte weder auf
  „Weiter“ noch auf etwas anderes, der Countdown lief einfach weiter.
- **O-Ton:** „Enter … nix. Na gut, wartet er halt.“
- **Bildschirmfoto:** `Bild NB/0003`
- **Vorschlag der Persona:** „Weiter“ als Standardknopf festlegen.

### F7: Abbruch-Grund – die Zelle sieht nicht nach Auswahlliste aus
- **Schwere:** gering
- **Wo:** Reiter „Ergebniserfassung“, Spalte „Abbruch“
- **Was passiert ist:** Ein Klick in die Zelle zeigte nur ein leeres, graues Kästchen ohne erkennbaren
  Pfeil. Erst ein Doppelklick öffnete die Liste (kein Abbruch / Ungehorsam / Verletzung Hund / Krankheit /
  Verletzung HF). Ohne die Demo hätte Tobias nicht gewusst, dass dort etwas auszuwählen ist.
  (evtl. Testumgebung: Bedienung per Befehl statt Maus)
- **O-Ton:** „Leeres Kästchen … ach, Doppelklick. Hätte man auch dranschreiben können.“
- **Bildschirmfoto:** `Bild NB/0223`
- **Vorschlag der Persona:** In der leeren Zelle „– kein Abbruch – ▾“ anzeigen.

### F8: Teilnehmerzahl Startbildschirm (17) ≠ Kopfbalken (16)
- **Schwere:** gering
- **Wo:** Startbildschirm-Liste vs. dunkler Kopfbalken im Termin
- **Was passiert ist:** Nach dem Neustart zeigte die Terminliste „17“, im Termin stand „16 Teilnehmer“.
  Der Unterschied ist vermutlich Pohl mit „keine Teilnahme“, beschriftet ist das nirgends.
- **O-Ton:** „17 oder 16? Fehlt da einer?“
- **Bildschirmfoto:** `Bild NB/0255`
- **Vorschlag der Persona:** Beide Stellen gleich zählen oder „16 (+1 abgesagt)“ anzeigen.

### F9: Sicherungsdatei heißt nach einem Termin, enthält aber alle
- **Schwere:** gering
- **Wo:** Reiter „Datensicherung“ → „Sicherung erstellen…“ → Dateiname
- **Was passiert ist:** Vorgeschlagen wurde „SHS-Sicherung_2026-11-14_Hundefreunde-Testhausen_erstellt-2026-11-03.zip“,
  der Text davor sagt aber „Sichert ALLE Termine“. Bei mehreren Terminen führt der Name in die Irre.
- **O-Ton:** „Ist das jetzt nur die Testhausen-Prüfung? Egal, Hauptsache gesichert.“
- **Bildschirmfoto:** `Bild NB/0252`
- **Vorschlag der Persona:** Dateiname „SHS-Sicherung_alle-Termine_2026-11-03.zip“.

### F10: Hilfe ist eine lange Textwand, Enter im Versionsfenster öffnet „Lizenzen“
- **Schwere:** gering
- **Wo:** Knopf „Hilfe“; Knopf „Version 1.0.55“
- **Was passiert ist:** Die Hilfe ist ein einziger langer Text ohne Inhaltsverzeichnis und ohne Suche.
  Teile wiederholen sich am Ende (Demoprüfung, Teilnehmer, Zeitplan usw. stehen doppelt). Im
  Versionsfenster liegt der Fokus auf „Lizenzen anzeigen“: Ein Enter zum Schließen öffnete das
  Lizenzfenster.
- **O-Ton:** „Das ist ja ein Roman. Und warum steht das doppelt drin?“ / „Ich wollte zumachen, nicht
  Lizenzen lesen.“
- **Bildschirmfoto:** `Bild NB/0260`, `…\0271.png`
- **Vorschlag der Persona:** Hilfe mit anklickbaren Überschriften pro Reiter. Im Versionsfenster
  „Schließen“ als Standardknopf.

## 4. Was gut lief

- **Enter-sicher:** Die riskanten Rückfragen („Teilnehmer … wirklich unwiderruflich löschen?“, „Automatisch
  verteilen … ERSETZT … Fortfahren?“, „Ungespeicherte Änderungen … Trotzdem aktualisieren?“) stehen auf
  **Nein**. Tobias’ Enter-Reflex hat deshalb nichts kaputt gemacht. Einmal ist er versehentlich auf
  „Liste aktualisieren“ gekommen, das Nein hat seine Eingaben gerettet.
- **Startnummern:** „Bereiche automatisch festlegen“ (1–20, 21–40 …) plus die Rückfrage nach jedem
  Import („Jetzt Fehlende Startnummern vergeben?“) führten ohne Nachdenken zu sauberen Nummern. Die
  Nachmeldung bekam passend die 44.
- **Import-Meldungen** nennen Zeile, Name und Grund in verständlichem Deutsch.
- **„Keine Teilnahme“** wirkt auf einen Klick und nimmt den Teilnehmer überall heraus (Zeitplan,
  Ergebnisse, Auswertung).
- **Stechen:** Der Hinweis unter der Tabelle nennt die Beteiligten und den Knopf. Der Dialog steht
  standardmäßig auf „Stechen noch offen“, ein Enter richtet also keinen Schaden an.
- **Export:** Neben jedem Knopf steht ein Satz Erklärung. Dateinamen und Ordner werden vorgeschlagen,
  Enter genügt.
- **Speichern:** Strg+S funktioniert. Die gelbe Markierung und „nicht gespeichert“ sind gut sichtbar.
  Nach dem Neustart war alles vorhanden.

## 5. Neue Funktionen im Urteil der Persona

**Demoprüfung:** Der Knopf ist sofort zu sehen. Tobias hat die ganze Demo laufen lassen, ohne selbst
etwas zu tun, und das hat ihm am meisten gebracht. Der Ablauf (Termin → Teilnehmer → Startnummern →
Zeitplan → Ergebnisse → Stechen → PDF) saß danach. Ohne die Demo hätte er die Abbruch-Auswahl und das
Stechen nicht so schnell gefunden. Die Texte sind lang, aber das automatische Weiterschalten nach
10 Sekunden passt zu ihm.

**Startnummern-Bereiche/Vergabe:** Das ist die beste Funktion. Ein Knopf legt die Bereiche fest, die
Nummern werden nach dem Import angeboten, und Nachmeldungen bringen nichts durcheinander. Nur der
vorausgewählte Partner beim Tauschen ist eine Falle (F2).

**Stechen:** Klar und sicher. „1. von 4 (nach Stechen)“ steht auch in der Ergebnisliste.

**Abbruch mit Grund:** Die Wirkung ist gut, in Auswertung und PDF steht „Abbruch wegen Verletzung des
Hundes“. Die Eingabe ist allerdings versteckt (F7).

**Aussehen:** Kopfbalken mit Hund, Verein, Datum und Teilnehmerzahl wirkt aufgeräumt, das Braun ist
angenehm. „Dunkel“ funktioniert sofort. Die Symbole (Doktorhut, Ordner, Info) sind dezent, aber
verständlich.

**Fehlermeldungen allgemein:** Verständlich und mit Namen und Grund. Dass beim Import nach dem
Wegklicken nichts mehr nachzulesen ist (F3) und dass die Punktegrenze erst beim Speichern geprüft wird
(F5), stört einen Wegklicker wie Tobias am meisten.

## 6. Grenzen dieses Tests

- Dateidialoge waren der englische Qt-Ersatz. PDFs wurden nicht geöffnet, sondern als Text gelesen.
- Bedienung per Befehl. Die Abbruch-Zelle ließ sich erst per `doppelzelle` aufklappen, mit echter Maus
  verhält sich das evtl. anders (F7).
- Einmal hat sich die Element-ID nach dem Schließen der Abbruch-Auswahlliste verschoben, dadurch wurde
  „Liste aktualisieren“ statt „Alle Ergebnisse speichern“ geklickt. Das war ein Bedienfehler im
  Steuerwerkzeug, kein Programmfehler. Die Rückfrage stand korrekt auf Nein.
- Installation und Update nur gedanklich anhand der Website. „Nach Updates suchen“ wurde nicht geklickt.
- Ein USB-Stick war nicht vorhanden, die Sicherung landete im Benutzerordner.

## 7. Gesamturteil

| Bereich | Note |
|---|---|
| Installation (laut Website) | 2 |
| Erststart / Demo | 2 |
| Termin-Ablauf | 2 |
| Gesamt | 2 |

Zur Installation: Die Website erklärt Download, „Behalten“ und „Trotzdem ausführen“ knapp. Update heißt
laut Website „Version …“ → „Nach Updates suchen“ und dann drüberinstallieren. Die Warnung „nicht digital
signiert“ verunsichert etwas.

**Würde ich am Prüfungstag allein damit klarkommen?** **Eher ja.** Ergebnisse, Disqualifikation,
Stechen und Ausdrucke liefen problemlos. Unsicher bleibt der Aushang-Zeitplan wegen der Mittagspause
zur falschen Uhrzeit, außerdem muss er sich merken, wen der Import abgelehnt hat.

**Die drei wichtigsten Wünsche:**
1. Die Mittagspause soll da stehen, wo ich sie hinschreibe, oder gar nicht (F1).
2. Beim Startnummern-Tausch nichts vorauswählen (F2).
3. Abgelehnte Import-Meldungen später noch nachlesen können (F3).
