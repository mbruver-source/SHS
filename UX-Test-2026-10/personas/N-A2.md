# UX-Bericht N-A2 – Julia, 42, Büro, mit Handbuch (Nachtest)

## 1. Persona und Vorgehen
Julia (42) nutzt E-Mail, Word, Excel-Grundlagen und Online-Banking sicher und richtet zum ersten Mal eine Prüfung aus. Sie arbeitet mit dem Handbuch (Startpunkt Kapitel 14 „Die erste Prüfung Schritt für Schritt“ plus Glossar Kapitel 15) und hat es parallel zu den Aufgaben gelesen. Das Programm wurde über Screenshots und Elementliste bedient. Nachtest: Vorab war nicht bekannt, was geändert wurde.

## 2. Aufgaben-Übersicht
| Nr | Aufgabe | Ergebnis | Fehlversuche | Handbuch/Hilfe nötig? | Kommentar |
|---|---|---|---|---|---|
| 0 | Installation (gedanklich) | ✓ | 0 | Kap. 2 | Release-Seite und Setup-Datei klar beschrieben. SmartScreen: bekannt/akzeptiert. |
| 1 | Prüfung anlegen | ✓ | 0 | Kap. 14 Schritt 1 | Maske breit genug. Bei „OK“ Rückfrage, weil Verband/Meldestelle leer waren (Ja/Nein, deutsch). Die Startnummern-Zeilen erscheinen nur für angehakte Prüfungen. Handbuch sagt „Dreikampf LK 1“, die Maske „DK-LK 1“. |
| 2 | Anmeldeformular erzeugen | ✓ | 0 | Schritt 2 | Dateiname und Ordner vorgeschlagen. Danach Meldung „Gespeichert unter …“ mit „PDF öffnen“ und „Ordner zeigen“. PDF sieht sinnvoll aus. |
| 3 | Zwei Nachmeldungen | ✓ | 0 | Schritt 3 | Maske groß und übersichtlich. Gegenstände nicht ausgefüllt, das steht als Anmerkung „Gegenstände noch offen“. |
| 4 | Mitgliederliste (CSV) | ✓ | 0 | Schritt 3 | Der Knopf ist an zwei Stellen leicht zu finden (Teilnehmer und Formular-Import). 12 importiert, 8 übersprungen mit Begründung. Danach Frage nach den Startnummern. |
| 5 | Vier PDF-Anmeldungen | ~ | 1 (Absturz) | Schritt 3 | Siehe F1. Danach 2 importiert, 2 mit klarer Begründung abgelehnt (Pfeiffer: zwei Prüfungen angekreuzt, Quast: LK 3 nicht angeboten). Julia würde die beiden anrufen. Hinweis zu Neumann („Leder“ übernommen, „Metall“ nicht) gut verständlich. |
| 6 | Startnummern tauschen, Absage | ✓ | 0 | Schritt 4/7 | Nummern wurden schon beim Import vergeben. „Herr Hofmann“ gibt es nicht, genommen wurde Peter Pohl. Tauschen: eine Zeile markieren, dann Auswahlliste. „Keine Teilnahme“ ist umkehrbar („Teilnahme wiederherstellen“). Doppelklick öffnet die Bearbeiten-Maske. |
| 7 | Zeitplan | ✓ | 0 | Schritt 5 | Richter standen schon als Spalten da. „Automatisch verteilen…“ ohne Überschneidungen. Mittagspause mit Haken bei allen Richtern auf einmal. |
| 8 | Ergebnisse (15 Starts, 1 Disq.) | ✓ | 1 (absichtlich 65/45,5) | Schritt 7 | Eine Zeile bewusst leer gelassen. Sie blieb „noch kein Ergebnis“. |
| 9 | Rangliste | ✓ | 0 | Schritt 8 | „1. von 4“ stimmt jetzt. Bei der unvollständigen Gruppe steht ein klarer Hinweis. |
| 10 | PDFs (Ergebnisliste, Bewertungsbögen, Etiketten) | ✓ | 0 | Schritt 6/8 | Jedes Mal Meldung mit Pfad. Bewertungsbögen fragen vorher nach den Gruppen. Inhalte brauchbar. |
| 11 | Datensicherung auf USB-Stick | ✓ | 0 | Schritt 9 | Ohne Fachwörter erklärt. Meldung mit Zielpfad. |
| 12 | Schließen und Neustart | ✓ | 0 | – | Schließen ohne Rückfrage. Nach dem Neustart waren alle Daten da (16 Teilnehmer, 14 Rangliste). |

## 3. Stolpersteine
### F1: Programmabsturz beim ersten PDF-Import
- Schwere: erheblich (wahrscheinlich Testumgebung)
- Wo: Formular-Import > „Anmeldeformulare (PDF) importieren…“, direkt nach Auswahl der vier Dateien
- Was passiert ist: Das Programm verschwand ohne Meldung. Das Absturzprotokoll nennt „Windows fatal exception: access violation“ beim Laden von pypdf/cryptography. Nach dem Neustart lief derselbe Import problemlos. Vermutlich ein Problem der Anaconda-Umgebung, im echten Setup eher nicht.
- O-Ton Julia: „Es ist einfach zu. Hoffentlich ist meine Arbeit noch da.“ (Sie war noch da.)
- Vorschlag: Beim nächsten Release-Test prüfen, ob die gebündelte EXE es auch macht.

### F2: Handbuchtext und Programmtext weichen leicht ab
- Schwere: gering
- Wo: Handbuch Schritt 1 und 3
- Beobachtung: Handbuch „Dreikampf LK 1“ gegenüber „DK-LK 1“ in der Maske. Handbuch Schritt 1 nennt „Veranstaltungsdaten bearbeiten…“, die Rückfrage beim Anlegen sagt „Termin bearbeiten…“. Das Handbuch erwähnt nicht, dass auch nach dem CSV-Import die Startnummern-Frage kommt.
- O-Ton: „Heißt das jetzt so oder so?“
- Vorschlag: Begriffe angleichen.

### F3: Mehrfachauswahl sperrt Knöpfe ohne Erklärung
- Schwere: gering
- Wo: Teilnehmer, zwei Zeilen markiert: „Startnummer tauschen…“, „Bearbeiten…“, „Löschen“ sind ausgegraut
- O-Ton: „Warum geht Tauschen nicht? Ich habe doch beide markiert.“ Erst nach Markieren einer Zeile ging es, der Dialog fragt dann nach dem Tauschpartner.
- Vorschlag: Tooltip „Nur eine Zeile markieren“. Das Handbuch erwähnt es nicht.

### F4: Importmeldungen nennen „Zeile 8“, nicht den Namen
- Schwere: gering
- Wo: Meldung „Import abgeschlossen“ (CSV)
- Beobachtung: Julia kennt die Zeilennummern der Excel-Datei nur, wenn sie sie öffnet. Die Meldung ist lang (8 Wiederholungen des gleichen Klammersatzes). Beim PDF-Import wird der Dateiname genannt, das ist besser.
- Vorschlag: Name statt Zeilennummer, Klammersatz nur einmal.

### F5: „45,5“ wird im Meldungstext als 45 gezeigt
- Schwere: gering
- Wo: „Alle Ergebnisse speichern“ bei zu hohen Punkten
- Beobachtung: Eingabe 65 und 45,5 ergibt die verständliche Meldung „Suche höchstens 60 Punkte (eingegeben: 65), Anzeige höchstens 40 Punkte (eingegeben: 45)“. Die Nachkommastelle wird weggelassen.
- Vorschlag: Eingegebenen Wert unverändert zeigen.

### F6: Mittagspause nicht exakt zur gewünschten Uhrzeit
- Schwere: kosmetisch
- Wo: Zeitplan > Pause hinzufügen (mit Haken „bei allen Richtern“, 10:00)
- Beobachtung: Die Pause wird zwischen Blöcken eingefügt (Anna 10:10, Bernd 10:00, Clara 10:20). Die Statuszeile sagt „um 10:00 eingefügt“. Liegt der Wunschzeitpunkt hinter dem Plan-Ende (12:00), landet die Pause am Ende. Handbuch Schritt 5 erwähnt das nicht.

## 4. Was gut lief
- Alle Programm-Dialoge deutsch (Ja/Nein/OK/Abbrechen).
- Teilnehmer-Maske öffnet breit und ohne Abschneiden.
- Nach jedem PDF eine Meldung mit Pfad und „Ordner zeigen“.
- Formular-Import mit Nummerierung 1/2/3 und Erklärtexten, CSV-Vorlage dabei.
- Zeitplan: Richter automatisch da, keine Dreikampf-Überschneidungen, Pause bei allen auf einmal.
- Ergebniserfassung: verständliche Fehlermeldung, „Keine Änderungen zu speichern.“, Status „✓ gespeichert“ nur bei echten Zeilen.
- Rangliste mit Hinweis auf offene Starter. Handbuch Kapitel 14 passt zum Programm, das Glossar hilft.

## 5. Gesamturteil
- Noten: Installation 2 / Erststart 1–2 / Turnierablauf 2 / gesamt 2.
- Allein am Prüfungstag klarkommen? Ja, mit Handbuch Kapitel 14 daneben. Der Absturz (F1) ist die einzige Sorge, falls er auch in der echten EXE vorkommt.
- Top-3-Wünsche: 1. Absturz beim PDF-Import absichern. 2. Begriffe zwischen Handbuch und Programm angleichen. 3. Importmeldungen kürzer und mit Namen.

## 6. Grenzen dieses Tests
Dateifenster ist ein Ersatz. Bewertungsbögen und Etiketten konnten nur als Text gelesen werden (kein Seitenrendering). Web-Version, SmartScreen und Updates wurden nicht getestet. Die Datumsmeldung wurde nicht ausgelöst. Der Reiter „Verwaltung“ wurde nicht geöffnet.

## 7. Nachtest-Abgleich
- U1 Startnummern einzeln / Doppelklick: **behoben**. „Fehlende Startnummern vergeben“ vergab mit einem Klick 14 bzw. 2 Nummern, Doppelklick öffnet die Bearbeiten-Maske.
- U2 Dreikampf-Teams bei mehreren Richtern gleichzeitig: **behoben**. Im Zeitplan standen die Teams jeweils zu unterschiedlichen Zeiten.
- U3 Teilnehmer-Maske zu schmal: **behoben**. Maske 1040x720, nichts abgeschnitten.
- U4 CSV-Import übernahm nicht angebotene Prüfungen: **behoben**. 8 Zeilen übersprungen mit Begründung (Meldung aber lang, siehe F4).
- U5 Technische Meldung / „45,5“ still zu 45: **teilweise**. Verständliche Meldung statt „CHECK constraint“, aber 45,5 wird in der Meldung als 45 angezeigt (F5).
- U6 Englische Knöpfe: **behoben**. Ja/Nein/OK/Abbrechen in allen Programm-Dialogen.
- U7 Kein Hinweis, wo die PDF liegt: **behoben**. Meldung „Gespeichert unter …“ mit „PDF öffnen“ und „Ordner zeigen“.
- U8 Richter nicht im Zeitplan: **behoben**. Alle drei Richter waren sofort Spalten.
- U9 Pausen am Ende / Mittagspause einzeln: **behoben**. Ein Dialog mit „Bei allen Richtern einfügen, um …“ (kleine Abweichung der Uhrzeit, F6).
- U10 Mitgliederliste schwer auffindbar: **behoben**. Knopf „Teilnehmerliste (Excel/CSV)…“ im Reiter Teilnehmer und eigener Block im Formular-Import.
- U11 Unklare Rückfrage bei zwei Gegenständen: **behoben**. Hinweis „bei Einzeldisziplin nur ein Gegenstand – übernommen „Leder“, nicht übernommen „Metall““.
- U12 Fenster zu klein: **behoben**. Hauptfenster 1916x1076. Die Startliste (600x380) ist klein, aber ausreichend.
- U13 Handbuch: **behoben**. Kapitel 14 und Glossar vorhanden, „Keine Teilnahme“ statt Löschen konsistent, Startnummern-Vergabe nach Import beschrieben (kleine Abweichungen, F2).
- U14 Fachwörter / ⚠ / Datumsmeldung: **teilweise**. CSV erklärt, Sicherung ohne Fachwörter, nur ein einziges ⚠ (Chip-Nr. fehlt). Die Datumsmeldung wurde **nicht erlebt**.
- K1 „✓ gespeichert“ bei leeren Zeilen: **behoben**. Leere Zeilen bleiben „noch kein Ergebnis“, dazu „Keine Änderungen zu speichern.“
- K7 Mehrfachmarkierung: **behoben**. Markieren mehrerer Zeilen geht, aber Tauschen/Bearbeiten sind dann ausgegraut ohne Erklärung (F3).
- K9 Rangliste „1. von 2“ unverständlich: **behoben**. „1. von 4“ stimmt, bei Lücken steht ein Hinweis mit dem Namen des offenen Starters.
