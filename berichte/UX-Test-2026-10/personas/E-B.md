# UX-Bericht E-B – Sabine (erfahrene Meldestelle, ohne Handbuch)

## 1. Persona und Vorgehen
Sabine, 45, macht seit Jahren die Meldestelle und kennt alle Fachbegriffe. Am PC ist sie sehr sicher (Excel, Fachsoftware), liest keine Anleitungen und erwartet die üblichen Bedienkonventionen.
Variante B, also ohne Handbuch. Die Installation habe ich über die Website (`docs/index.html`) und die GitHub-Release-Seite gedanklich durchgespielt. Erststart und Turnier habe ich echt bedient.

Hilfe und Handbuch habe ich zweimal gebraucht:
- **Hilfe-Knopf im Programm (1×), Aufgabe 6:** Ich habe gesucht, wie importierte Teilnehmer Startnummern bekommen. Der Hilfetext sagt nur „Die Startnummer wird automatisch vorgeschlagen“, und das gilt nur für neu erfasste Teilnehmer. Der Text ist lang, das Fenster klein (560×520). Scrollen ließ sich in der Testumgebung nicht prüfen.
- **docs/HANDBUCH.md (1×), Aufgabe 6:** Davor hatte ich drei erfolglose Versuche: „Startnummer tauschen…“ mit zwei markierten Zeilen, den Reiter Verwaltung und die Hilfe. Per Suche nach „Startnummer“ im Handbuch habe ich bestätigt bekommen, dass es nur einzeln über „Bearbeiten…“ geht. Eine Sammelvergabe gibt es nicht.

## 2. Aufgaben-Übersicht
| Nr | Aufgabe | Ergebnis | Fehlversuche | Handbuch/Hilfe nötig? | Kommentar |
|---|---|---|---|---|---|
| 0 | Installation (gedanklich) | ✓ | 0 | nein | Die Website erklärt Download, SmartScreen und Updates knapp und klar. Die Release-Seite selbst ist nackt: keine Beschreibung, nur „Full Changelog“, Assets zugeklappt. SmartScreen ist bekannt/akzeptiert. |
| 1 | Erststart, Prüfung anlegen | ✓ | 1 | nein | „14.11.26“ wurde mit klarer Meldung abgelehnt, danach ging es sofort. |
| 2 | Leeres Anmeldeformular | ✓ | 0 | nein | Liegt im Reiter Export, dort sofort gefunden. Das PDF ist sauber, nur die eigenen angebotenen Prüfungen sind ankreuzbar. Nach dem Speichern kommt keine Rückmeldung. |
| 3 | 2 Nachmeldungen von Hand | ✓ | 0 | nein | Der Dialog ist sehr eng (siehe F5). |
| 4 | Mitgliederliste CSV | ✓ | 0 | nein | 20 importiert. Fünf davon sind LK-3-Starts, die gar nicht angeboten werden, und das wurde ohne Warnung übernommen (F8). |
| 5 | 4 PDF-Anmeldungen | ~ | 1 (Absturz) | nein | Beim ersten Versuch mit allen 4 Dateien ist das Programm abgestürzt (F1). Danach gingen 2 durch, 2 wurden mit verständlicher Begründung abgelehnt. Meine Entscheidung: Pfeiffer anrufen und fragen, welche Prüfung sie will (beide angekreuzt). Quast anrufen, denn Trümmer LK 3 wird nicht angeboten. |
| 6 | Startnummern, Tausch, Absage | ~ | 3 | Hilfe + Handbuch | Startnummern musste ich 22× einzeln über Bearbeiten vergeben (F2). Tausch und „Keine Teilnahme“ waren danach einfach. |
| 7 | Zeitplan 9:00 mit Mittagspause | ~ | 1 | nein | „Automatisch verteilen“ funktioniert, setzt aber DK-Hunde gleichzeitig bei drei Richtern an (F3). Die Pause landet am Ende und muss hochgeschoben werden (F9). Die Richter aus den Termindaten werden nicht übernommen (F10). |
| 8 | Ergebnisse (≥8, 1 Disq., DK) | ✓ | 2 | nein | 13 Starts eingetragen. Eine Fehleingabe (65) ergab eine technische Fehlermeldung (F4). „45,5“ wurde stillschweigend zu 45 (F11). Strg+S wirkte nicht. |
| 9 | Rangliste | ✓ | 0 | nein | Reiter Auswertung, übersichtlich: Platzierung „1. von 3“, nB und Disq. sind klar markiert. |
| 10 | Ergebnisliste, Bögen, Etiketten | ✓ | 0 | nein | Alle PDFs sind brauchbar. Es gibt nirgends eine Erfolgsmeldung und kein Angebot zum Öffnen (F6). |
| 11 | Datensicherung USB | ✓ | 1 | nein | Die abweichende Passwort-Wiederholung wurde sauber abgefangen. Eine Erfolgsmeldung mit Pfad ist da. |
| 12 | Schließen, Neustart | ✓ | 0 | nein | Alles war wieder da. Beim Schließen mit halb eingetragenem Ergebnis kam eine gute Warnung. |

## 3. Stolpersteine

### F1: Absturz beim Import von 4 PDF-Anmeldungen
- Schwere: erheblich (Ursache unklar, nicht reproduzierbar)
- Wo: Formular-Import → „Anmeldeformulare (PDF) importieren…“, alle 4 Dateien auf einmal gewählt
- Was passiert ist: Nach der Dateiwahl hat sich das Programm sofort ohne Meldung beendet. `programm_ausgabe.log` ist leer (0 Byte), auch in `harness.log` gibt es keinen Hinweis. Kurz davor hatte ein Klick auf den Knopf per Text zunächst kein Dateifenster geöffnet. Erst der zweite Klick öffnete es, danach kam der Absturz. Möglicherweise waren zwei Dateifenster gestapelt, das kann auch an der Testumgebung liegen. Danach habe ich das Programm neu gestartet und es weiter versucht. Die Dateien einzeln, zu zweit und alle 4 auf einmal liefen ohne Absturz. Bis dahin erfasste Daten (22 TN) waren nicht verloren.
- O-Ton: „Weg. Einfach weg. Hoffentlich ist meine Liste noch da.“
- Screenshot: shots/12_pdf_import.png (Zustand davor)
- Vorschlag: Mit Logging prüfen, ob ein doppelt geöffneter Datei-Dialog oder der Mehrfach-Import einen unbehandelten Fehler auslöst. Unbehandelte Ausnahmen in eine Logdatei schreiben.

### F2: Keine Sammelvergabe von Startnummern
- Schwere: erheblich
- Wo: Reiter Teilnehmer, nach CSV- und PDF-Import
- Was passiert ist: Alle 22 importierten Teilnehmer haben keine Startnummer. Einen Knopf „Startnummern vergeben“ gibt es nicht. Pro Person musste ich markieren → Bearbeiten → Häkchen „steht noch nicht fest“ entfernen → Nummer tippen → OK, rund 100 Aktionen. Nach dem Entfernen des Häkchens steht im Feld „1“ und nicht die nächste freie Nummer. Ergebnis: „Die Startnummer 1 ist bereits einem anderen Teilnehmer zugeteilt…“. Nach dem Speichern springt außerdem die Markierung auf den nächsten Namen an derselben Position, weil die Liste neu sortiert wird.
- O-Ton: „Das ist doch Excel-Arbeit von vor zwanzig Jahren. Ich will einmal ‚durchnummerieren nach LK‘ drücken.“
- Screenshot: shots/17_tauschen_dialog.png, shots/21_bearbeiten_bauer.png
- Vorschlag: Knopf „Startnummern vergeben…“ (fortlaufend, optional nach Art/LK sortiert, nur für TN ohne Nummer). Beim Entfernen des Häkchens die nächste freie Nummer vorschlagen.

### F3: Automatischer Zeitplan setzt DK-Hunde gleichzeitig bei mehreren Richtern an
- Schwere: erheblich
- Wo: Zeitplan → „Automatisch verteilen…“, auch im Zeitplan-PDF
- Was passiert ist: Maria Muster (DK LK 1) steht um 09:00–09:10 bei Anna Richter (Behältnis), bei Bernd Berger (Fläche) und bei Clara Christ (Trümmer). Bei Otto, Pohl und Quandt ist es genauso. Thiel (DK LK 3) steht nach dem Einfügen der Pause um 11:35 bei zwei Richtern. Es gibt keinerlei Warnung, unter „Offene Starts“ ist alles grün ✓.
- O-Ton: „Der Hund kann ja nicht an drei Orten gleichzeitig suchen. Den Vorschlag kann ich so nicht aushängen.“
- Screenshot: shots/28_zeitplan_verteilt.png, Zeitplan-PDF
- Vorschlag: DK-Teilbereiche eines Hundes zeitlich versetzen und Überschneidungen pro Startnummer farbig markieren oder warnen.

### F4: Technische Datenbankmeldung bei Punktzahl über Maximum
- Schwere: erheblich
- Wo: Ergebniserfassung → „Alle Ergebnisse speichern“
- Was passiert ist: Ich habe 65 in „Trümmerfeld Suche (0-60)“ eingegeben. Das Feld nimmt den Wert ohne Hinweis an. Erst beim Speichern kommt: „Frank, Florian – Trümmerfeld: CHECK constraint failed: suche_truemmerfeld BETWEEN 0 AND 60“.
- O-Ton: „CHECK constraint? Ich weiß, was gemeint ist, aber meine Kollegin nicht.“
- Screenshot: shots/32_speichern_65.png
- Vorschlag: Eingabe direkt im Feld begrenzen oder rot markieren. Meldung im Klartext: „Suche Trümmerfeld: höchstens 60 Punkte“.

### F5: Teilnehmer-Dialog zu eng, Felder abgeschnitten
- Schwere: erheblich (betrifft jede Erfassung und Prüfung)
- Wo: „Teilnehmer erfassen/bearbeiten“ (780×640)
- Was passiert ist: Die linke Spalte (Name, Verein, Anschrift) hat nur etwa 45 px breite Felder. Inhalte wie „onrad“, „rdorf“, „e.org“ sind nicht lesbar. Die rechte Spalte ist abgeschnitten, es gibt einen waagrechten Scrollbalken. Den Haken „Prüfungsgebühr bezahlt“ sieht man nur halb.
- O-Ton: „Ich muss ja jedes Feld anklicken, um zu sehen, was drinsteht.“
- Screenshot: shots/07_teilnehmer_dialog.png, shots/23_ok_reagiert_nicht.png
- Vorschlag: Dialog breiter starten oder die beiden Spalten untereinander anordnen, Mindestbreite für Textfelder.

### F6: Keine Rückmeldung nach PDF-Export
- Schwere: gering
- Wo: Export (alle PDF-Knöpfe), Zeitplan (PDF), Rangliste drucken
- Was passiert ist: Nach „Save“ kommt keine Meldung, kein Öffnen und kein „Ordner öffnen?“ (`geoeffnet.log` blieb leer). Die Sicherung zeigt dagegen „Sicherung erstellt: …“. Vorgeschlagen wird immer der Termine-Ordner und nicht etwa „Dokumente“.
- O-Ton: „Hat er's jetzt gemacht oder nicht?“
- Vorschlag: Kurze Meldung „PDF gespeichert unter … [Öffnen] [Ordner öffnen]“.

### F7: Hauptfenster breiter als der Bildschirm
- Schwere: gering
- Wo: Hauptfenster, sobald die Teilnehmerliste gefüllt ist
- Was passiert ist: Das Fenster ist von 1196 auf 1957 px Breite angewachsen (Bildschirm 1920), der Hilfe-Knopf liegt am Rand. Zugleich ist es nur 600 px hoch. Im Zeitplan sind die Richterlisten deshalb nur 3 bis 4 Zeilen hoch, die Knöpfe nehmen den meisten Platz ein.
- Screenshot: shots/25_keine_teilnahme.png, shots/28_zeitplan_verteilt.png
- Vorschlag: Fenstergröße an den Bildschirm koppeln oder maximiert starten, Anmerkungsspalte umbrechen statt verbreitern.

### F8: CSV-Import übernimmt nicht angebotene Prüfungen ohne Warnung
- Schwere: gering
- Wo: Formular-Import → CSV importieren
- Was passiert ist: Fünf Starts in LK 3 (DK und ED), die gar nicht angeboten werden, wurden ohne Hinweis importiert. Der PDF-Import lehnt genau so etwas mit guter Begründung ab (Quast). Das ist inkonsequent.
- O-Ton: „Moment, wir bieten doch gar kein LK 3 an. Warum stehen die jetzt drin?“
- Vorschlag: Gleiche Prüfung wie beim PDF-Import, mindestens als Warnung im Abschlussbericht.

### F9: Pause wird ans Ende angehängt statt hinter die Markierung
- Schwere: gering
- Wo: Zeitplan → Pause hinzufügen… (eine Zeile war markiert)
- Was passiert ist: Die Mittagspause landete als letzter Eintrag. Ich musste sie dreimal per „Hoch“ verschieben, und das für jeden der drei Richter. Die Uhrzeiten rechnen danach korrekt mit, das ist gut.
- Vorschlag: Hinter dem markierten Eintrag einfügen. Optional „Pause für alle Richter um …“.

### F10: Richter aus den Termindaten werden im Zeitplan nicht verwendet
- Schwere: gering
- Wo: Zeitplan → Richter hinzufügen
- Was passiert ist: Im Termin sind Anna Richter, Bernd Berger und Clara Christ hinterlegt. Der Zeitplan meldet trotzdem „Noch keine Richter angelegt“, und „Richter hinzufügen“ erzeugt „Richter 1“. Ich musste dreimal umbenennen.
- O-Ton: „Die hab ich doch beim Anlegen schon eingetragen!“
- Vorschlag: Spalten mit den Namen aus den Veranstaltungsdaten vorbelegen.

### F11: Kommazahl wird stillschweigend abgeschnitten
- Schwere: gering
- Wo: Ergebniserfassung
- Was passiert ist: Aus der Eingabe „45,5“ wurde ohne Hinweis 45.
- Vorschlag: Ungültige Zeichen sichtbar ablehnen (Hinweis „nur ganze Punkte“).

### F12: Englische Knöpfe und Entwicklersprache in Programm-Dialogen
- Schwere: kosmetisch
- Wo: Alle Programm-Dialoge („Cancel“), Rückfragen („Yes“/„No“, z. B. „Nur ein Gegenstand bei ED“, „Automatisch verteilen“, „Beenden“). Bewertungsbögen-Auswahl: „Standardmäßig sind alle angehakt (bisheriges Verhalten)“.
- Vorschlag: Ja/Nein/Abbrechen auf Deutsch. „(bisheriges Verhalten)“ streichen.

### F13: Kleinigkeiten
- Schwere: kosmetisch/gering
- Doppelklick auf eine Teilnehmerzeile öffnet nichts. Im Startdialog funktioniert Doppelklick dagegen (in der Testumgebung beobachtet).
- Strg+S speichert in der Ergebniserfassung nicht (in der Testumgebung beobachtet).
- Ein einmaliger Klick auf OK im Bearbeiten-Dialog hat nicht geschlossen, erst der zweite (1× bei 22 Vorgängen, evtl. Testumgebung).
- „Rangliste drucken (PDF)…“ schlägt den Dateinamen „Ergebnisliste_…“ vor und erzeugt dieselbe Datei wie Export → Ergebnisliste. Zwei Namen für dasselbe sind verwirrend.
- Leere Ergebniszeilen zeigen „✓ gespeichert“, obwohl nichts eingetragen ist. Die Statusspalte ist abgeschnitten („● nicht …“).
- „Noch ohne vollständiges Ergebnis: Graf, Greta, Iske, Ina, …“: Bei Kommas zwischen Nachname und Vorname und zwischen den Personen sieht man nicht, wo ein Name endet.
- Etikett für Albrecht (nB) zeigt „Gesamt: 65“ ohne nB-Kennzeichnung.
- Meldestelle bleibt auf dem Formular leer, wenn man sie beim Anlegen nicht einträgt. Es gibt dazu keinen Hinweis.
- Mehrfachmarkierung in der Teilnehmerliste graut alle Knöpfe aus (auch „Bezahlt umschalten“).

## 4. Was gut lief
- Die Website erklärt Installation, SmartScreen und Updates in drei Sätzen.
- Der Termin-Dialog ist vollständig, die angebotenen Prüfungen sind ankreuzbar. Die Datumsfehlermeldung ist klar und nennt das Format.
- Das Anmeldeformular-PDF ist professionell und enthält nur die angebotenen Prüfungen.
- Die Ablehnungsgründe beim PDF-Import sind vorbildlich: „mehrere Prüfungen angekreuzt (Trümmer LK 1, Fläche LK 1)“, „Trümmer LK 3 wird in diesem Termin nicht angeboten – Formular eines anderen Termins?“. Duplikate werden erkannt.
- Die Warnspalte „Anmerkungen“ (Chip fehlt, Gegenstand fehlt) ist praxisnah.
- „Keine Teilnahme“ und „Teilnahme wiederherstellen“ funktionieren mit einem Klick. Der Teilnehmer bleibt sichtbar und wird im Zeitplan und in der Ergebniserfassung ausgelassen.
- „Startnummer tauschen“ mit Klartext-Auswahlliste funktioniert.
- Die Ergebniserfassung als Tabelle ist schnell. Nicht relevante Felder sind ausgegraut, ungespeicherte Zeilen sind gelb.
- Auswertung und Ergebnisliste sind übersichtlich: „1. von 3“, nB und Disq. klar.
- Die Bewertungsbögen sind mit Punkten vorausgefüllt, die Etiketten sind brauchbar.
- Die Sicherung mit Passwort hat eine gute Prüfung und eine Erfolgsmeldung mit Pfad.
- Schließen mit nicht speicherbaren Ergebnissen führt zu Warnung und Rückfrage. Die übrigen Daten werden automatisch gespeichert, nach dem Neustart war alles da.

## 5. Gesamturteil
- Schulnoten: Installation 2, Erststart 2, Turnierablauf 3, gesamt 3+
- „Würde ich am Prüfungstag allein damit klarkommen?“ – **Ja, mit Einschränkung.** Ergebniserfassung und Auswertung am Prüfungstag selbst laufen gut. Die Vorbereitung kostet unnötig Zeit (Startnummern einzeln). Den automatischen Zeitplan würde ich so nicht aushängen, weil DK-Hunde doppelt belegt sind. Den müsste ich von Hand umbauen, und das ist mit den kleinen Listen mühsam. Der einmalige Absturz beim Import hätte mich nervös gemacht.
- Die 3 wichtigsten Wünsche:
  1. Startnummern auf einen Klick vergeben (fortlaufend und nach LK).
  2. Zeitplan-Vorschlag ohne Überschneidungen pro Hund, mit Warnung bei Konflikten.
  3. Verständliche Fehlermeldungen und Eingabeprüfung direkt im Feld (Punkte-Maximum), deutsche Ja/Nein-Knöpfe, Rückmeldung nach jedem PDF-Export.

## 6. Grenzen dieses Tests
- Die Installation habe ich nur gedanklich nachvollzogen. SmartScreen, Installer-Dialoge, Startmenü-Eintrag und „Nach Updates suchen“ habe ich nicht gesehen.
- Das Dateifenster war ein englischer Qt-Ersatz. Ob der echte Windows-Dialog „.pdf“ automatisch anhängt, ist ungeprüft.
- Den Hilfetext konnte ich nicht scrollen, ich habe nur den Anfang gesehen.
- Fenster maximieren, Mausrad, Rechtsklick-Menüs, Spaltensortierung per Klick und Tastenkürzel (Strg+S, Entf) ließen sich nur eingeschränkt oder gar nicht prüfen. Die Beobachtungen dazu in F13 sind unter Vorbehalt.
- Der Absturz (F1) ist nicht reproduzierbar. Ein Zusammenhang mit der Testumgebung (verzögertes Dateifenster) ist möglich.
- PDFs habe ich nur angesehen, nicht gedruckt. Ob die Etiketten auf echte Bögen passen, ist ungeprüft.
