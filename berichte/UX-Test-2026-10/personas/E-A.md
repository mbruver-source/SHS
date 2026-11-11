# UX-Bericht E-A – Heinz (erfahrener Prüfungsleiter, mit Handbuch)

## 1. Persona und Vorgehen
Heinz, 58, organisiert seit über 10 Jahren SHS- und Rettungshundeprüfungen, bisher mit OMA und Excel. Er kennt alle Fachbegriffe und arbeitet routiniert am PC, ist aber ungeduldig.
Variante A: Vor dem Start hat er `README.md` und `docs/HANDBUCH.md` gelesen (Kapitel 1–5 genau, 6–10 quer, 13 FAQ).
Während der Arbeit hat er im Handbuch nachgeschlagen:
- zur Vergabe von Startnummern (Kap. 4),
- zum Zeitplan (Kap. 6),
- zu Ergebnissen, Disqualifikation und Speichern (Kap. 7),
- zur Datensicherung (Kap. 10).

Die Hilfe im Programm hat er einmal geöffnet, als er nach einer Massenvergabe der Startnummern suchte (ohne Erfolg).

## 2. Aufgaben-Übersicht
| Nr | Aufgabe | Ergebnis | Fehlversuche | Handbuch/Hilfe nötig? | Kommentar |
|---|---|---|---|---|---|
| 0 | Installation (gedanklich) | ✓ | 0 | README/Handbuch Kap. 2 | Klar beschrieben, SmartScreen-Hinweis vorhanden (bekannt/akzeptiert). Kleine Abweichung: README sagt „Version → Nach Updates suchen“, Handbuch „ℹ️ Version …“ oben rechts. Im Programm ist es ein Knopf, kein Menü |
| 1 | Erststart, Prüfung anlegen | ✓ | 1 | nein | „14.11.26“ wird abgelehnt, die Meldung ist klar. Richter und Prüfungsleiter direkt im Dialog eingetragen |
| 2 | Leeres Anmeldeformular | ✓ | 0 | Kap. 5 (vorab gelesen) | PDF ist gut. Leere Meldestelle wird ohne Warnung gedruckt |
| 3 | 2 Nachmeldungen von Hand | ~ | 0 | nein | Erfassungsmaske: linke Spalte stark gequetscht, Namen abgeschnitten (F1) |
| 4 | Mitgliederliste CSV | ✓ | 0 | Kap. 5 | 20 Teilnehmer importiert. Teilnehmer in nicht angebotenen Prüfungen wurden ohne Hinweis übernommen (F3) |
| 5 | 4 PDF-Anmeldungen | ✓ | 1 (Absturz, s. F12) | Kap. 5 | 2 importiert, 2 mit verständlichem Grund abgelehnt (Pfeiffer: 2 Prüfungen angekreuzt, Quast: Trümmer LK 3 nicht angeboten). Entscheidung: Pfeiffer anrufen, welche Prüfung gemeint ist, und dann von Hand anlegen. Quast mitteilen, dass LK 3 nicht angeboten wird |
| 6 | Startnummern vergeben, Bauer/Engel tauschen, Hofmann „keine Teilnahme“ | ~ | 2 | Kap. 4 + Hilfe | Tauschen und „Keine Teilnahme“ sind sehr gut. Aber für 22 Teilnehmer ohne Nummer musste jeder einzeln über „Bearbeiten…“ bearbeitet werden (F2) |
| 7 | Zeitplan 9:00 mit Mittagspause | ~ | 2 | Kap. 6 | Richter aus den Termindaten werden nicht übernommen (F5). Der automatische Plan setzt denselben DK-Hund gleichzeitig bei 3 Richtern ein (F4). Pause wird immer ans Ende gehängt (F6) |
| 8 | Ergebnisse (≥8 Starts, 1 Disqualifikation, DK) | ✓ | 2 | Kap. 7 | 12 Starts erfasst, Pohl disqualifiziert. Englische Fehlermeldung aus der Datenbank (F7). „No“-Schleife beim Reiterwechsel (F8) |
| 9 | Rangliste | ✓ | 0 | nein | Übersichtlich, rot markiert für nB/Disq |
| 10 | Ergebnisliste, Bewertungsbögen, Etiketten | ✓ | 1 (Absturz, s. F12) | Kap. 9 | Brauchbare PDFs. Kleinigkeiten in F10 |
| 11 | Datensicherung auf „USB-Stick“ | ✓ | 1 | Kap. 10 | Passwortfehler wird gut abgefangen. Bestätigung nur als Statuszeile |
| 12 | Schließen, Neustart, Daten prüfen | ✓ | 0 | nein | Rangliste, Zeitplan und Mittagspause waren nach dem Neustart vollständig da |

## 3. Stolpersteine

### F1: Erfassungsmaske „Teilnehmer erfassen/bearbeiten“ – linke Spalte gequetscht
- Schwere: erheblich
- Wo: Dialog „Teilnehmer erfassen“ / „Teilnehmer bearbeiten“ (780×640)
- Was passiert ist:
  - Die Felder Nachname, Vorname, Verein, E-Mail usw. sind nur etwa 45 px breit. Eingegebener Text ist abgeschnitten („uster“, „/laria“, „usen“).
  - Die rechte Spalte ist rechts abgeschnitten („Startnummer steht noch nic“).
  - Es erscheint eine horizontale Scrollleiste.
  - „Prüfungsgebühr bezahlt“ und „Halter weicht ab“ liegen unterhalb des sichtbaren Bereichs.
- O-Ton: „Ich seh ja gar nicht, was ich da tippe – hab ich ‚Muster‘ richtig geschrieben?“
- Screenshot: shots/07_teilnehmer_dialog.png, shots/08_maria_ausgefuellt.png, shots/20_nach_ok.png
- Vorschlag: Dialog größer öffnen oder die Spalten gleichmäßig verteilen, die Feldbreite links mindestens an den Inhalt anpassen.

### F2: Keine Massenvergabe von Startnummern
- Schwere: erheblich
- Wo: Reiter Teilnehmer
- Was passiert ist:
  - Nach CSV- und PDF-Import hatten 22 Teilnehmer keine Startnummer. Handbuch und Hilfe nennen nur „Bearbeiten…“.
  - Je Teilnehmer: markieren, „Bearbeiten…“, Haken „steht noch nicht fest“ entfernen, Nummer tippen, OK. Das sind rund 90 Klicks.
  - Doppelklick und Enter auf eine Zeile öffnen die Maske NICHT.
  - Nach dem Entfernen des Hakens schlägt das Feld „1“ vor, obwohl 1 schon vergeben ist. Erst beim Speichern kommt „Startnummer bereits vergeben“. Die Meldung selbst ist gut und nennt den Inhaber.
  - Ein Teilnehmer aus dem PDF-Import (Neumann, ED) hatte zwei Gegenstände. Beim Speichern kam die Rückfrage „Nur ein Gegenstand bei ED … Trotzdem speichern?“ mit den englischen Knöpfen „Yes/No“, obwohl man Gegenstand 2 ausgegraut gar nicht sehen oder ändern kann.
- O-Ton: „Bei 60 Startern sitz ich da eine Stunde. Ich will ‚Startnummern vergeben – nach Klasse sortiert ab 1‘ drücken.“
- Screenshot: shots/17_bearbeiten_ohne_nr.png, shots/18_startnr_vergeben.png, shots/21_ed_zwei_gegenstaende.png
- Vorschlag: Knopf „Startnummern automatisch vergeben…“ (z. B. nach Art/LK/Disziplin oder Zeitplan-Reihenfolge, nur für Teilnehmer ohne Nummer). Doppelklick auf eine Zeile soll „Bearbeiten“ öffnen. Nach dem Entfernen des Hakens die nächste freie Nummer vorschlagen.

### F3: CSV-Import übernimmt nicht angebotene Prüfungen ohne Hinweis (anders als der PDF-Import)
- Schwere: erheblich
- Wo: Formular-Import → „CSV importieren…“
- Was passiert ist:
  - Angeboten waren nur DK 1/2, Trümmer 1/2, Fläche 1 und Behältnisse 1.
  - Die CSV brachte trotzdem ED LK 3 (alle Disziplinen), ED LK 2 Fläche/Behältnis und DK LK 3 ohne jede Warnung ins Programm. Sie erscheinen danach im Zeitplan, in der Auswertung und in den Bögen.
  - Der PDF-Import lehnt dasselbe dagegen ab („wird in diesem Termin nicht angeboten“).
  - Die Teilnehmerliste hat keine Anmerkung „Prüfung nicht angeboten“.
- O-Ton: „Moment, LK 3 bieten wir doch gar nicht an – warum hab ich jetzt Thiel im Zeitplan?“
- Screenshot: shots/14_teilnehmerliste.png
- Vorschlag: Beim CSV/OMA-Import warnen oder nachfragen. In „Anmerkungen“ ein ⚠ „Prüfung im Termin nicht angeboten“ anzeigen.

### F4: „Automatisch verteilen“ plant denselben DK-Hund gleichzeitig bei drei Richtern
- Schwere: erheblich
- Wo: Reiter Zeitplan → „Automatisch verteilen…“, ebenso im Zeitplan-PDF
- Was passiert ist:
  - Muster/Bello ist um 09:00–09:10 gleichzeitig bei Anna Richter (Behältnis), Bernd Berger (Fläche) und Clara Christ (Trümmer) eingeplant. Das gilt für alle fünf DK-LK-1-Teams.
  - DK LK 2 (Roth, Schulz) ist um 09:50 bei Bernd und Clara gleichzeitig eingeplant.
  - Es gibt keinen Hinweis auf Überschneidungen.
- O-Ton: „Der Bello kann sich doch nicht dreiteilen. Den Plan kann ich so nicht an die Richter schicken.“
- Screenshot: shots/26_zeitplan_verteilt.png (Zeitplan_2026-11-14.pdf)
- Vorschlag: DK-Teams versetzt rotieren lassen oder wenigstens Überschneidungen eines Teams farbig markieren und warnen.

### F5: Richter aus den Termindaten werden im Zeitplan nicht übernommen
- Schwere: gering
- Wo: Reiter Zeitplan
- Was passiert ist: Beim Anlegen waren Richter 1–3 eingetragen. Der Zeitplan meldet trotzdem „Noch keine Richter angelegt“. „Richter hinzufügen“ legt „Richter 1“ an, jeder muss einzeln umbenannt werden (3× Dialog).
- O-Ton: „Die Namen hab ich doch vorhin schon eingetippt.“
- Screenshot: shots/24_zeitplan_leer.png
- Vorschlag: Spalten mit den Richternamen aus „Veranstaltungsdaten“ vorbelegen oder per Knopf übernehmen.

### F6: Pause landet immer am Ende; „Hoch/Runter“ springt blockweise
- Schwere: gering
- Wo: Zeitplan → „Pause hinzufügen…“
- Was passiert ist:
  - Ich hatte die Zeile 8 markiert. Die Pause wurde trotzdem ans Ende gehängt.
  - „Hoch“ verschiebt um ganze Blöcke, obwohl die Liste einzelne Teilnehmerzeilen zeigt. Nach 6× „Hoch“ stand die Pause oben, danach 2× „Runter“.
  - Die Mittagspause muss für jeden Richter einzeln angelegt werden.
  - Die Listen zeigen bei Fensterhöhe 600 nur etwa 4 Zeilen.
- O-Ton: „Ich hab doch die Zeile markiert – warum hängt der die Pause hinten an?“
- Screenshot: shots/27_pause_dialog.png, shots/26_zeitplan_verteilt.png
- Vorschlag: Pause nach der markierten Zeile einfügen. Option „Mittagspause für alle Richter um 12:00“ anbieten.

### F7: Technische Datenbank-Meldung bei Punkten außerhalb des Bereichs
- Schwere: gering
- Wo: Ergebniserfassung → „Alle Ergebnisse speichern“
- Was passiert ist: Bei Suche = 65 kam die Meldung „Klein, Klaus – Trümmerfeld: CHECK constraint failed: suche_truemmerfeld BETWEEN 0 AND 60“. Die zweite Meldung („Bitte Suche UND Anzeige eintragen …“) ist dagegen verständlich. Hinweis: Die Testumgebung setzt Text direkt. Ob ein echter Nutzer „65“ überhaupt tippen kann, ist offen.
- O-Ton: „CHECK constraint – was will der von mir?“
- Screenshot: shots/30_speichern_fehler.png
- Vorschlag: „Suche Trümmerfeld muss zwischen 0 und 60 liegen“. Das Feld direkt rot markieren.

### F8: Rückfrage „Ungespeicherte Ergebnisse“ erscheint nach „No“ immer wieder
- Schwere: gering (eventuell Testumgebung)
- Wo: Wechsel von Ergebniserfassung zu Auswertung mit einer ungespeicherten Zeile
- Was passiert ist: Auf „Jetzt speichern?“ habe ich 3× „No“ geklickt, die Frage kam jedes Mal wieder. Erst Escape führte weiter. Knöpfe englisch „Yes/No“, ebenso bei „Automatisch verteilen“.
- O-Ton: „Nein heißt nein!“
- Screenshot: shots/32_auswertung.png, shots/33_nein_schleife.png
- Vorschlag: Prüfen, ob „Nein“ mehrfach ausgelöst wird. Knöpfe „Ja/Nein“ bzw. „Speichern / Verwerfen / Abbrechen“ beschriften.

### F9: Layout-Überlappung im Reiter Export
- Schwere: kosmetisch
- Wo: Reiter Export, Fenster 1196×600
- Was passiert ist: Der Erklärungstext ist abgeschnitten. Die Statuszeile „Anmeldeformular gespeichert: C:/Users/…“ liegt über dem Erklärungstext, der Pfad steht mit Schrägstrichen „/“.
- O-Ton: „Da steht Text über Text.“
- Screenshot: shots/06_nach_anmeldeformular.png
- Vorschlag: Erklärung in einen scrollbaren Bereich oder Tooltip legen. Pfad im Windows-Format anzeigen, Knopf „PDF öffnen“ anbieten.

### F10: Kleinigkeiten in Listen und PDFs
- Schwere: kosmetisch
- Ergebnisliste-PDF:
  - Der disqualifizierte Pohl steht in der Platz-Spalte als „nB“ statt „Disq.“.
  - Die Überschrift „ED LK 2 Trümmerfeld“ steht allein am Seitenende, die Tabelle beginnt erst auf Seite 2.
- „Noch ohne vollständiges Ergebnis: Conrad, Carla, Graf, Greta …“: Nachname und Vorname sind mit Komma getrennt, Personen ebenfalls. Man kann nicht erkennen, wer wer ist.
- Ergebniserfassung:
  - Leere Zeilen zeigen „✓ gespeichert“, obwohl nichts eingetragen ist.
  - Der Status ist zu „● nicht …“ abgeschnitten.
- Abgemeldeter Teilnehmer (Hofmann): zeigt weiter „⚠ Gegenstand fehlt“.
- Auswahl der Bewertungsbögen: Text „(bisheriges Verhalten)“ ist Entwicklersprache.
- Nach Hofmanns Abmeldung: Das Handbuch, Kap. 6, rät noch „Fällt ein Teilnehmer aus, einfach im Reiter ‚Teilnehmer‘ löschen“. Das widerspricht der neuen Funktion „Keine Teilnahme“.
- Screenshot: shots/31_disqualifiziert.png, shots/34_boegen_auswahl.png, Ergebnisliste_2026-11-14.pdf
- Vorschlag: Je Punkt anpassen. Namen z. B. als „Carla Conrad; Greta Graf“ schreiben.

### F11: Speicherorte – PDFs landen im Termine-Datenordner, Import-Dialoge beginnen dort
- Schwere: gering
- Wo: alle Export-Dialoge, „CSV importieren…“
- Was passiert ist:
  - Alle PDFs schlägt das Programm im Ordner `SHS-Pruefungsprogramm\Termine` neben der .sqlite vor.
  - „CSV importieren“ öffnet ebenfalls dort, nicht in Downloads. Der PDF-Import öffnete dagegen Downloads.
  - Die Datensicherung enthält die PDFs nicht. Das ist richtig so, steht aber nirgends.
  - Der Sicherungsname schlägt das heutige Datum vor, nicht das Prüfungsdatum.
- O-Ton: „Wo find ich die PDFs nachher? Zwischen den Datenbankdateien?“
- Vorschlag: Unterordner „Ausdrucke“ je Termin anlegen. Importdialoge in Downloads bzw. dem zuletzt genutzten Ordner öffnen.

### F12: Zwei Abstürze ohne Fehlermeldung (nicht reproduzierbar)
- Schwere: erheblich, falls echt (eventuell Testumgebung)
- Wo:
  - (a) „Anmeldeformulare (PDF) importieren…“ mit 4 Dateien gleichzeitig;
  - (b) „Etiketten (PDF)…“ → Save direkt nach dem Ergebnislisten-Export.
- Was passiert ist:
  - Das Programm war ohne Meldung weg, `programm_ausgabe.log` war leer.
  - Beim Neustart war alles bis zum letzten Speichern da. Der Import aus (a) war nicht ausgeführt, die ungespeicherte Ergebniseingabe für Quandt war verloren.
  - Beim Wiederholen trat der Fehler beide Male nicht auf. Auch 4 Dateien gleichzeitig liefen danach fehlerfrei.
- Vorschlag: Entwickler sollten die Ursache prüfen (Absturzprotokoll).

### Bewertung Handbuch
- Gut gegliedert, Kapitel 1 (Ablaufplan) ist für einen Prüfungsleiter ideal. Den Formular-Import und die Gründe für Ablehnungen erklärt es sehr genau, die Meldungen stimmen mit dem Programm überein.
- Lücken bzw. Abweichungen:
  - Wie man nach einem Import schnell Startnummern vergibt, steht nirgends (nur „über ‚Bearbeiten…‘“ im Beispielabschnitt).
  - Kap. 4 nennt den Hinweis „Bei ED ist nur ein Gegenstand vorgesehen“ nur für „ältere Daten“. Er entsteht aber auch bei frischem PDF-Import, weil das Formular für LK 2 zwei Gegenstandsfelder hat.
  - Kap. 6 („Teilnehmer löschen“) widerspricht „Keine Teilnahme“.
  - Kap. 6 erwähnt nicht, dass Pausen ans Ende angehängt werden und Hoch/Runter blockweise springt.
  - Kap. 6 erwähnt nicht, dass Richter aus der Verwaltung nicht übernommen werden.
  - README vs. Handbuch: Update-Menü unterschiedlich beschrieben.

## 4. Was gut lief
- Der Startbildschirm ist klar, und der Speicherort wird angezeigt.
- Termin anlegen:
  - Alles in einem Dialog.
  - Der Dateiname wird automatisch vorgeschlagen.
  - Datumsfehler werden klar gemeldet.
- Das Anmeldeformular-PDF ist sauber und zeigt nur die angebotenen Prüfungen. Gegenüber Word ein großer Fortschritt.
- Beim PDF-Import sind die Ablehnungsgründe hervorragend verständlich, und doppelte Meldungen werden erkannt.
- „Startnummer tauschen…“ und „Keine Teilnahme“ funktionieren genau wie gewünscht. Hofmann fällt sauber aus Zeitplan und Bögen heraus.
- Spalte „Anmerkungen“ mit ⚠ zeigt auf einen Blick, was fehlt.
- Ergebniserfassung:
  - Tabellarisch, schnell, und bei ED sind die anderen Disziplinen gesperrt.
  - „Disqualifiziert“ sperrt die Felder.
  - Gelbe Zeilen kennzeichnen ungespeicherte Eingaben.
  - Teilweise Speicherfehler blockieren die übrigen Zeilen nicht.
- Auswertung: Rangliste mit Wertnote und „1. von 4“ sofort sichtbar, nB/Disq in Rot.
- Etiketten, Bewertungsbögen (31 Seiten, vorausgefüllt) und Zeitplan-PDF (farbige Blöcke) sind direkt brauchbar.
- Datensicherung mit Passwort:
  - Tippfehler im Passwort werden erkannt, und die Eingaben bleiben stehen.
  - Nach dem Neustart waren alle Daten vollständig da.

## 5. Gesamturteil
- Schulnoten: Installation 2 / Erststart 2 / Turnierablauf 3 / gesamt 3+
- „Würde ich am Prüfungstag allein damit klarkommen?“ – **Ja**, für Ergebniserfassung, Rangliste und Ausdrucke ohne Weiteres. Die Vorbereitung würde ich aber nicht am Tag selbst machen wollen:
  - Die Startnummern sind Fleißarbeit.
  - Den automatischen Zeitplan müsste ich für DK komplett von Hand umbauen.
  - Der gequetschte Teilnehmerdialog nervt bei jeder Korrektur.
- Die 3 wichtigsten Wünsche:
  1. Startnummern auf einen Klick vergeben (für alle ohne Nummer, sortiert nach Klasse/Zeitplan). Doppelklick auf eine Zeile öffnet „Bearbeiten“.
  2. Zeitplan ohne Überschneidungen: DK-Teams rotieren lassen, Richter aus den Termindaten übernehmen, Mittagspause für alle Richter zu einer Uhrzeit.
  3. Erfassungsmaske für Teilnehmer lesbar machen (Feldbreiten). Warnung, wenn importierte Teilnehmer in nicht angebotenen Prüfungen stehen.

## 6. Grenzen dieses Tests
- Das Dateiauswahl-Fenster ist ein Ersatz. Bewertet wurden nur der vorgeschlagene Ordner und der Dateiname.
- „PDF öffnen“ bzw. „Ordner öffnen“ waren nicht sichtbar. PDFs habe ich direkt angesehen, das Bewertungsbogen-PDF nur als Text (31 Seiten).
- Fenstergröße: Das Hauptfenster hatte 1196×600 bzw. 1957×600. Einige Platzprobleme (Zeitplan-Listen, Export-Text) können bei maximiertem Fenster auf 1080 Höhe geringer sein. F1 (Teilnehmerdialog) betrifft dagegen einen Dialog mit fester Größe.
- Eingaben werden per Harness gesetzt. Ob Zahlenfelder in echt „65“ zulassen (F7) und ob die „No“-Schleife (F8) bei echtem Mausklick auftritt, ist offen.
- Die zwei Abstürze (F12) sind nicht reproduzierbar, eine Ursache in der Testumgebung ist möglich.
- Installation, Updates, Hilfe-Links und die Web-Version wurden nicht echt getestet.
