# UX-Bericht L-B – Werner (66, Laie am PC, ohne Handbuch)

## 1. Persona und Vorgehen
Werner, 66, Rentner, frisch im Vorstand. Hat Hunde, kennt aber die SHS-Fachbegriffe (DK, ED, LK, Disziplin) nicht. Am PC nutzt er E-Mail, Wetter-App und Solitaire. Ordner und Dateipfade überfordern ihn, englische Wörter versteht er nicht, und bei unerwarteten Fenstern bekommt er Angst und drückt „Abbrechen“ oder „Nein“.

- Variante B, also ohne Handbuch. Für die Installation dienten die Website `docs/index.html` und die GitHub-Release-Seite (per WebFetch) als Startpunkt.
- **Hilfe im Programm** (Knopf „❓ Hilfe“) einmal bei Aufgabe 6 genutzt (Startnummern), nach zwei erfolglosen Versuchen.
- **Handbuch** (`docs/HANDBUCH.md`) einmal bei Aufgabe 6 geöffnet, nach drei erfolglosen Versuchen (Tauschen, Reiter Verwaltung, Hilfe). Gesucht wurde nur nach „Startnummer“.
- Das Programm lief unsichtbar und wurde über den Test-Harness bedient. Bewertet wurde nur, was auf dem Bildschirm stand (Screenshots angesehen).
- Eine Unterbrechung des Testlaufs kam von außen (Testleitung bzw. API-Limit) und ist kein Programmfehler. Das Programm lief dabei weiter.
- **Testleiter-Hilfe:** Werner hätte seine 22 Teilnehmer ohne Startnummer nicht ohne fremde Hilfe nummeriert. Die 22 Bearbeiten-Dialoge habe ich als Testleiter per Skript abgearbeitet. Die Abläufe danach sind echt getestet.

## 2. Aufgaben-Übersicht
| Nr | Aufgabe | Ergebnis | Fehlversuche | Handbuch/Hilfe nötig? | Kommentar |
|---|---|---|---|---|---|
| 0 | Installation (gedanklich) | ~ | 1 | nein | Die Website erklärt Datei, SmartScreen und Updates gut. Die GitHub-Seite ist englisch („Assets“, „Source code (zip)“), und die Dateiliste lädt erst nachträglich. Werner würde vermutlich die Enkelin fragen. |
| 1 | Erststart, Prüfung anlegen | ✓ | 1 | nein | Datum „14.11.26“ abgelehnt. Die Meldung ist verständlich, die Eingaben bleiben erhalten. |
| 2 | Leeres Anmeldeformular | ✓ | 0 | nein | Im Reiter „Export“ gefunden. Das PDF wird im Termine-Ordner gespeichert. „Wo ist das jetzt hin?“ (Pfad nur unten als Statuszeile) |
| 3 | Zwei Nachmeldungen von Hand | ~ | 0 | nein | Geschafft, aber die linken Eingabefelder sind winzig. Man sieht „uster“ statt „Muster“. |
| 4 | Mitgliederliste (CSV) | ~ | 0 | nein | Werner klickt auf den blauen Knopf „CSV importieren…“. Das Dateifenster öffnet im Termine-Ordner statt in Downloads. Der Import selbst klappt (20 Teilnehmer). |
| 5 | 4 PDF-Anmeldungen | ✓ | 0 | nein | 2 importiert, 2 mit klarem Grund abgelehnt. Pfeiffer nach „Anruf“ von Hand erfasst, Quast nicht angenommen. |
| 6 | Startnummern tauschen, Absage | ✗ allein / ✓ mit Hilfe | 3 | Hilfe + Handbuch | Für Importierte gibt es keine Startnummern und keinen Knopf zum Vergeben. Zwei Leute „ohne Nummer“ zu tauschen tut gar nichts, ohne jede Meldung. „Keine Teilnahme“ klappt sofort. |
| 7 | Zeitplan 9:00 + Mittagspause | ~ | 2 | nein | Die Richter aus dem Termin werden nicht übernommen. Die Pause landet am Ende, und „Hoch/Runter“ springt blockweise. Die DK-Hunde sind zur gleichen Zeit bei drei Richtern eingeplant. |
| 8 | Ergebnisse (9 Starts, 1 Disq., 2 DK) | ~ | 1 | nein | Die Tabelle ist gut. Bei 65 statt max. 60 kommt die rohe Datenbank-Meldung „CHECK constraint failed …“. |
| 9 | Rangliste ansehen | ✓ | 0 | nein | Reiter „Auswertung“, klar mit Platz und Wertnote. |
| 10 | Ergebnisliste, Bögen, Etiketten | ✓ | 0 | nein | Alle drei PDFs ließen sich erzeugen und sind brauchbar. Kleinigkeiten: „SH-R“ wird nirgends erklärt, „Pfeiffer, Paul, , Pepper“. |
| 11 | Datensicherung auf USB-Stick | ✓ | 0 | nein | Funktioniert. Erfolg wird nur als kleine Statuszeile angezeigt, Begriffe „ZIP“ und „AES-256“. |
| 12 | Schließen + Neustart | ✓ | 0 | nein | Ohne Rückfrage geschlossen, beim Neustart war alles noch da. |

## 3. Stolpersteine

### F1: Für importierte Teilnehmer gibt es keine Startnummern und keinen Weg, sie gesammelt zu vergeben
- Schwere: **blockierend** für Werner
- Wo: Reiter „Teilnehmer“, nach CSV-Import (20 TN) und PDF-Import (2 TN)
- Was passiert ist: Alle importierten Teilnehmer stehen ohne Startnummer in der Liste. Es gibt keinen Knopf wie „Startnummern vergeben“. Die Hilfe sagt nur „Die Startnummer wird automatisch vorgeschlagen“ (bei Handeingabe) bzw. „danach im Reiter ‚Teilnehmer‘ die Startnummern vergeben“, ohne zu sagen wie. Erst das Handbuch erklärt es: jeden Teilnehmer einzeln mit „Bearbeiten…“ öffnen, den Haken „Startnummer steht noch nicht fest“ entfernen und eine Nummer eintippen. Für 22 Personen sind das 22 Dialoge. Das vorgeschlagene Feld zeigt nach dem Haken-Entfernen „1“ (schon vergeben). Erst dann kommt die (gute) Meldung „Die Startnummer 1 ist bereits einem anderen Teilnehmer zugeteilt (aktuell: Muster, Maria)…“.
- O-Ton Persona: „Wieso haben die keine Nummer? Muss ich das jetzt bei jedem einzeln machen? Da sitz ich ja bis heute Abend.“
- Screenshot: shots/12_teilnehmerliste.png, shots/19_bearbeiten_bauer.png, shots/20_startnr_vergeben.png
- Vorschlag: Knopf „Fehlende Startnummern vergeben“ (fortlaufend, ggf. nach Art/LK sortiert). Außerdem sollte nach dem Import ein Hinweis kommen: „20 Teilnehmer importiert – noch ohne Startnummer. Jetzt vergeben?“

### F2: „Startnummer tauschen“ bei zwei Teilnehmern ohne Nummer tut nichts
- Schwere: erheblich
- Wo: Teilnehmer → „Startnummer tauschen…“
- Was passiert ist: Ich habe Bauer markiert, im Dialog „Engel, Eva (Start-Nr. keine)“ gewählt und OK geklickt. Danach erschien keine Meldung, das Fenster ging zu, und nichts hatte sich geändert.
- O-Ton: „Hat's jetzt geklappt? Da steht immer noch nix.“
- Screenshot: shots/14_tauschen_ohne_nr.png
- Vorschlag: Meldung „Beide haben noch keine Startnummer – zuerst Startnummern vergeben“, oder Einträge ohne Nummer im Dialog gar nicht anbieten.

### F3: Zeitplan teilt einem DK-Hund drei Richter zur gleichen Uhrzeit zu
- Schwere: erheblich (würde am Prüfungstag platzen, Werner merkt es vorher nicht)
- Wo: Zeitplan → „Automatisch verteilen…“
- Was passiert ist: Bei Anna Richter, Bernd Berger und Clara Christ steht jeweils „09:00–09:10 … Nr. 1 Muster, Maria (Bello)“, nur mit unterschiedlicher Disziplin. Dasselbe gilt für Otto, Pohl und Quandt. Dieselbe Hündin und derselbe Hundeführer sind also gleichzeitig auf drei Plätzen. Das Programm warnt nicht.
- O-Ton: (merkt es nicht) „Sieht ordentlich aus.“
- Screenshot: shots/28_zeitplan_verteilt.png
- Vorschlag: Beim automatischen Verteilen dieselbe Startnummer zeitlich versetzen, oder Überschneidungen rot markieren. (Fachlich bitte prüfen, ob das gewollt ist.)

### F4: Richter aus den Termindaten werden im Zeitplan nicht übernommen
- Schwere: erheblich
- Wo: Reiter „Zeitplan“
- Was passiert ist: Beim Anlegen hatte ich drei Richter eingetragen. Im Zeitplan steht trotzdem „Noch keine Richter angelegt - über ‚Richter hinzufügen‘ starten.“ „Automatisch verteilen…“ meldet „Bitte zuerst mindestens einen Richter anlegen.“ „Richter hinzufügen“ legt „Richter 1“ an, der Name muss über „Umbenennen…“ einzeln nachgetragen werden.
- O-Ton: „Die hab ich doch schon eingetippt! Warum fragt der nochmal?“
- Screenshot: shots/24_zeitplan.png, shots/25_auto_ohne_richter.png, shots/26_richter_hinzu.png
- Vorschlag: Richter 1–5 aus den Veranstaltungsdaten automatisch als Spalten vorschlagen bzw. mit Namen übernehmen.

### F5: Eingabefelder links im Teilnehmer-Dialog sind winzig
- Schwere: erheblich
- Wo: Dialog „Teilnehmer erfassen/bearbeiten“, linke Spalte „Hundeführer & Kontakt“
- Was passiert ist: Die Felder Nachname, Vorname, Verein usw. sind nur etwa 45 Pixel breit. Nach der Eingabe sieht man „uster“, „/laria“, „usen“. Unten erscheint ein waagerechter Rollbalken, und rechts ist „Startnummer steht noch nic…“ abgeschnitten. Das Fenster ist 780×640 groß.
- O-Ton: „Hab ich mich vertippt? Da steht ‚uster‘.“
- Screenshot: shots/08_teilnehmer_dialog.png, shots/09_maria_dk.png
- Vorschlag: Die linke Spalte breiter machen bzw. den Dialog größer öffnen, sodass kein waagerechter Rollbalken nötig ist.

### F6: Rohe Datenbank-Fehlermeldung bei zu hoher Punktzahl
- Schwere: erheblich
- Wo: Ergebniserfassung → „Alle Ergebnisse speichern“
- Was passiert ist: Ich habe 65 in „Trümmerfeld Suche (0-60)“ eingetragen. Das Feld nimmt den Wert ohne Warnung an. Erst beim Speichern kommt: „Albrecht, Anna – Trümmerfeld: CHECK constraint failed: suche_truemmerfeld BETWEEN 0 AND 60“. Gut ist, dass die anderen Zeilen gespeichert werden und die fehlerhafte Zeile markiert bleibt.
- O-Ton: „Tschek konstreint? Hab ich jetzt was kaputt gemacht?“
- Screenshot: shots/34_speichern_fehler.png
- Vorschlag: Klartext wie „Suche Trümmerfeld: höchstens 60 Punkte (eingegeben: 65)“, am besten schon beim Verlassen des Feldes.

### F7: Englische Knöpfe „Yes/No/Cancel“ in Programm-Dialogen
- Schwere: erheblich für diese Persona
- Wo: z. B. „Automatisch verteilen“ (Yes/No), „Nur ein Gegenstand bei ED“ (Yes/No), alle Eingabedialoge (OK/Cancel)
- Was passiert ist: Die Rückfrage „…ERSETZT dabei deren bisherigen Zeitplan (… gehen dabei verloren). Fortfahren?“ mit „Yes/No“ hat Werner erschreckt, er klickte erst „No“. Die Warnung „Nur ein Gegenstand bei ED … Trotzdem speichern?“ erschien bei einer reinen Startnummern-Änderung an einem PDF-importierten Teilnehmer (Neumann). Zwei Gegenstände kamen aus ihrem Formular.
- O-Ton: „Jes? No? Ich will nix verlieren!“
- Screenshot: shots/22_yes_no_englisch.png, shots/27_auto_dialog.png
- Vorschlag: Knöpfe auf Deutsch („Ja/Nein/Abbrechen“). Bei der Auto-Verteilung, wenn noch kein Plan existiert, gar nicht von „verloren“ sprechen. Den PDF-Import bei ED nur einen Gegenstand übernehmen lassen.

### F8: Zeitplan-Spalten zeigen nur 2 Zeilen, Pause verschiebt sich blockweise
- Schwere: erheblich
- Wo: Reiter „Zeitplan“
- Was passiert ist: Die Liste je Richter ist ein kleines Kästchen mit etwa 2 sichtbaren Zeilen und waagerechtem Rollbalken (Fenster 1253×600). „Pause hinzufügen…“ hängt die Pause ans Ende (11:20). Siebenmal „Hoch“ schiebt sie bis 09:00 an den Anfang („Mittagspause 09:00–09:45“). Einmal „Runter“ springt fünf Einträge weiter, weil ein Block wie ein Eintrag zählt. Die Pause gilt nur für einen Richter, für die anderen beiden muss man sie wiederholen.
- O-Ton: „Mittagspause um neun? Und wieso springt das so?“
- Screenshot: shots/28_zeitplan_verteilt.png, shots/30_zeitplan_pause.png
- Vorschlag: Listen höher machen. Im Pausen-Dialog ein Feld „ab Uhrzeit“ anbieten, und eine Option „für alle Richter“.

### F9: Dateifenster schlagen meist den versteckten Termine-Ordner vor
- Schwere: gering (für Werner erheblich)
- Wo: Anmeldeformular speichern, CSV importieren, Ergebnisliste/Bögen/Etiketten speichern
- Was passiert ist: Zum Speichern wird `…\SHS-Pruefungsprogramm\Termine` vorgeschlagen, beim CSV-Import ebenfalls statt „Downloads“. Den Speicherort sieht man danach nur als lange Pfad-Statuszeile, die teilweise abgeschnitten ist. Beim PDF-Import danach war Downloads vorausgewählt (der letzte Ordner wird gemerkt, das ist gut).
- O-Ton: „Und wo find ich das jetzt, wenn ich das mailen will?“
- Screenshot: shots/06_anmeldeformular_dialog.png, shots/07_nach_anmeldeformular.png
- Vorschlag: Für Ausgaben „Dokumente“ oder „Desktop“ vorschlagen, für Importe „Downloads“. Nach dem Speichern ein kleines Fenster mit „Ordner öffnen“ und „PDF öffnen“ zeigen.

### F10: CSV-Import übernimmt nicht angebotene Prüfungen ohne Hinweis
- Schwere: gering
- Wo: Formular-Import → „CSV importieren…“
- Was passiert ist: Teilnehmer in Trümmer LK 3, Fläche LK 2/3, Behältnisse LK 2/3 und DK LK 3 wurden ohne Hinweis importiert, obwohl der Termin sie nicht anbietet. Der PDF-Import lehnt dagegen „Trümmer LK 3 wird in diesem Termin nicht angeboten“ ab. PDF-Formulare eines anderen Veranstalters und Datums („DEMO Hundefreunde Musterstadt“, 03.10.2026) wurden außerdem ohne Hinweis übernommen.
- O-Ton: (merkt es nicht)
- Screenshot: shots/12_teilnehmerliste.png
- Vorschlag: Nach dem CSV-Import eine Liste „nicht angebotene Prüfungen“ zeigen. Beim PDF-Import auf einen abweichenden Veranstalter oder ein abweichendes Datum hinweisen.

### F11: Orange Warnungen in fast jeder Zeile
- Schwere: gering
- Wo: Teilnehmerliste, Spalte „Anmerkungen“
- Was passiert ist: Bei fast allen steht „⚠ Gegenstand fehlt“ oder „⚠ Gegenstände unvollständig (Dreikampf)“. Werner weiß nicht, was ein „Gegenstand“ ist und ob das schlimm ist.
- O-Ton: „Überall Warnungen – hab ich was falsch gemacht?“
- Screenshot: shots/23_keine_teilnahme.png
- Vorschlag: Ein Tooltip oder Hinweis „Suchgegenstand (z. B. Leder, Holz) – kann bis zum Prüfungstag nachgetragen werden“.

### F12: Doppelklick auf einen Teilnehmer öffnet nichts
- Schwere: gering (eventuell Grenze der Testumgebung)
- Wo: Teilnehmerliste
- Was passiert ist: Doppelklick auf Zeile oder Namenspalte hatte keine Wirkung, erst „Bearbeiten…“ öffnet den Dialog. Im Startfenster öffnet der Doppelklick den Termin dagegen schon.
- Vorschlag: Doppelklick = Bearbeiten.

### F13: Kleinigkeiten (kosmetisch)
- „Status ✓ gespeichert“ steht in der Ergebniserfassung auch bei noch leeren Zeilen. Das wirkt, als wären schon Ergebnisse da (shots/31_ergebnisse.png).
- Im Dialog „Bewertungsbögen – Auswahl“ steht „(bisheriges Verhalten)“, das ist Entwicklersprache (shots/36_boegen_auswahl.png).
- Etiketten: „SH-R“ wird nicht erklärt. Ohne Verein erscheint „Pfeiffer, Paul, , Pepper“.
- Ergebnisliste: Beim Disqualifizierten steht in der Spalte Platz „nB“, in der Spalte Wertnote „Disqualifiziert (DISQ)“.
- Auswertung: „Noch ohne vollständiges Ergebnis: Graf, Greta, Iske, Ina, …“ ist schwer lesbar (Kommas zwischen Nach- und Vorname und zwischen Personen).
- Die Datumsmeldung „bitte TT.MM.JJJJ oder JJJJ-MM-TT“ ist für Laien kryptisch. Besser wäre ein Beispiel: „z. B. 14.11.2026“.
- Beim Anlegen sind „Verband“ und „Meldestelle“ ohne Erklärung. Werner ließ sie leer, im Anmeldeformular fehlen sie dann.
- Das Hauptfenster wird beim Reiterwechsel immer breiter (1196 → 1253 → 1406 px).
- Datensicherung: Der Erfolg wird nur als Statuszeile angezeigt, es gibt kein Bestätigungsfenster. „ZIP“ und „AES-256“ versteht Werner nicht.

## 4. Was gut lief
- Startfenster und „Neuen Termin anlegen…“ sind sofort verständlich, ebenso die Pflichtfelder mit *.
- Fehlermeldungen behalten die Eingaben (Datum, Ergebnisse), man verliert nichts.
- Die angebotenen Prüfungen lassen sich als Haken direkt beim Anlegen auswählen, das Anmeldeformular enthält dann nur diese. Das PDF sieht professionell aus.
- Der PDF-Import mit Mehrfachauswahl zeigt eine sehr klare Liste mit Gründen, warum eine Datei abgelehnt wurde.
- Die Meldung „Startnummer bereits vergeben“ nennt die Person und drei Lösungswege.
- „Keine Teilnahme“ geht mit einem Klick, der Knopf wird zu „Teilnahme wiederherstellen“, und die Person ist aus Zeitplan und Ergebniserfassung verschwunden.
- Die Ergebniserfassung ist übersichtlich: Nicht zutreffende Felder sind mit „–“ gesperrt, „Disqualifiziert“ graut die Punkte aus, und ungespeicherte Zeilen sind gelb markiert.
- Die Auswertung bzw. Rangliste ist sofort verständlich (Platz „1. von 2“, Wertnote ausgeschrieben).
- Alle PDFs ließen sich mit einem Klick und sinnvollem Dateinamen erzeugen.
- Beenden geht ohne Rückfragen, beim Neustart ist alles da, und der Termin ist in der Liste.
- Die Website erklärt Installation, SmartScreen und Updates in einfachem Deutsch.

## 5. Gesamturteil
- Schulnoten: **Installation 3** (Website gut, GitHub-Seite englisch), **Erststart 2**, **Turnierablauf 4** (Startnummern, Zeitplan, Fehlermeldungen), **gesamt 3–4**
- „Würde ich am Prüfungstag allein damit klarkommen?“ – **Nein.** Die Ergebniseingabe am Tag selbst würde Werner schaffen. Die Vorbereitung aber nicht: Startnummern für die importierte Liste vergeben und einen sinnvollen Zeitplan mit Richtern und Pause bauen. Ohne Anruf beim Vorgänger oder einen Blick ins Handbuch hätte er dort aufgegeben. Dass DK-Hunde dreifach gleichzeitig eingeplant sind, würde erst am Prüfungstag auffallen.
- Die 3 wichtigsten Wünsche:
  1. Ein Knopf „Fehlende Startnummern vergeben“ mit Hinweis direkt nach dem Import (F1, F2).
  2. Zeitplan: Richter aus den Termindaten übernehmen, keine Doppelbelegung eines Hundes, Pause zu einer Uhrzeit und für alle Richter einfügen (F3, F4, F8).
  3. Alles auf Deutsch und laienverständlich: Ja/Nein statt Yes/No, keine Datenbank-Meldungen, breitere Eingabefelder (F5, F6, F7).

## 6. Grenzen dieses Tests
- Die Installation wurde nur gedanklich durchgespielt. Download, SmartScreen und Startmenü-Verknüpfung wurden nicht echt erlebt (SmartScreen ist bekannt und akzeptiert).
- Das Dateiauswahl-Fenster war ein englischer Qt-Ersatz. Bewertet wurden nur die vorgeschlagenen Ordner und Dateinamen.
- PDFs „öffnen“ und Ordner „öffnen“ zeigen hier nichts an. Die PDFs habe ich direkt gelesen. Die Bewertungsbögen konnte ich nur als Text prüfen, nicht als Bild (kein PDF-Renderer verfügbar).
- Die Fenstergröße war 1196–1406×600 auf einem virtuellen 1920×1080-Bildschirm. Maximieren war nicht möglich. Die engen Zeitplan-Listen (F8) und die winzigen Felder (F5) könnten bei maximiertem Fenster weniger schlimm sein. F5 tritt aber in einem Dialog fester Größe auf.
- Die Hilfe ließ sich nur mit Pfeiltasten rollen (Grenze des Harness).
- F12 (Doppelklick) kann eine Grenze des Harness sein.
- Die 22 Startnummern-Vergaben liefen als Testleiter-Hilfe per Skript, nicht im echten Tempo von Werner (geschätzt 15–20 Minuten).
- Die externe Unterbrechung des Laufs war kein Programmfehler. Es gab keinen Absturz.
