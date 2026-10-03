# UX-Bericht L-B2 – Werner, 71, Kassenwart a. D. (Nachtest, ohne Handbuch)

## 1. Persona und Vorgehen
Werner, selten am PC, liest Meldungen wörtlich. Ohne Handbuch; Startpunkt war die Webseite (docs/index.html). Das Handbuch wurde NICHT geöffnet. Die Programm-Hilfe („❓ Hilfe“) wurde einmal am Ende angesehen (lesbar, aber lang). Installation nur gedanklich. Das Szenario wurde komplett durchgespielt; Hofmann existiert in den Testdaten nicht, stellvertretend wurde Herr Pohl auf „Keine Teilnahme“ gesetzt.

## 2. Aufgaben-Übersicht
| Nr | Aufgabe | Ergebnis | Fehlversuche | Handbuch/Hilfe nötig? | Kommentar |
|----|---------|----------|--------------|-----------------------|-----------|
| 0 | Installation (gedanklich) | ✓ | 0 | nein | Webseite klar: „Aktuelle Version herunterladen“, SmartScreen-Hinweis steht da. Updates über „ℹ️ Version“ erklärt. Werner würde den Enkel rufen, aber machbar. |
| 1 | Prüfung anlegen | ✓ | 1 (Datum „14.11.26“) | nein | Fenster öffnet groß. Datumsfehler-Meldung nennt Beispiel „14.11.2026“. Rückfrage zu Verband/Meldestelle mit „Ja/Nein“ deutsch, aber Werner kennt „Verband“/„Meldestelle“ nicht genau. |
| 2 | Leeres Anmeldeformular | ~ | 1 | nein | Man muss auf „Export“ kommen (Hinweis im Reiter Formular-Import hilft). Beim Speichern mit dem vorgeschlagenen Ordner kam „PDF konnte nicht erstellt werden … No such file or directory“ (Ordner `Ausdrucke\2026-11-14_…` existiert nicht). Erst nach Wahl eines anderen Ordners ging es; dann klare Meldung „Gespeichert unter: …“. |
| 3 | Zwei Nachmeldungen | ✓ | 0 | nein | Maske jetzt breit, nichts abgeschnitten. Art/LK/Disziplin verständlich. |
| 4 | Mitgliederliste (CSV) | ✓ | 0 | nein | Knopf „Teilnehmerliste (Excel/CSV)…“ im Reiter Teilnehmer mit Tooltip, plus Reiter „Formular-Import“ mit Erklärung. Meldung listet übersprungene Zeilen mit Grund. Aber: zweiter Import derselben Datei erzeugte stillschweigend Doppelte (siehe F2). |
| 5 | Vier PDF-Anmeldungen | ✓ | 0 | nein | 2 importiert; Pfeiffer (zwei Prüfungen angekreuzt) und Quast (Prüfung nicht angeboten) mit klarem Grund abgelehnt, Neumann mit verständlichem Hinweis. Werner würde die beiden anrufen. |
| 6 | Startnummern tauschen / Absage | ~ | 2 | nein | Doppelklick öffnet jetzt „Bearbeiten“. Gesammelte Vergabe nur nach Eintragen von Bereichen unter Verwaltung (Meldung erklärt es); danach ein Klick für alle. Tauschen: Der Knopf ist bei zwei markierten Zeilen ausgegraut (nur eine markieren, dann Partner in Liste wählen) – ohne Erklärung. „Keine Teilnahme“ klappt. |
| 7 | Zeitplan 9:00 mit Mittagspause | ✓ | 0 | nein | Richter sind schon eingetragen. „Automatisch verteilen…“ ohne Rückfrage, Teams ohne Überschneidung. Pause mit Haken „Bei allen Richtern einfügen“ geht in einem Zug. |
| 8 | Ergebnisse (15 Starts, 1 DQ) | ✓ | 1 (70 Punkte) | nein | Verständliche Meldung „Suche höchstens 60 Punkte (eingegeben: 70)“. |
| 9 | Rangliste | ✓ | 0 | nein | „1. von 4“ stimmt mit den Startern (Absager nicht mitgezählt). |
| 10 | PDFs | ✓ | 0 | nein | Ergebnisliste, 15 Bewertungsbögen, Etiketten erzeugt, jeweils mit Pfad-Meldung. Inhalt (Text geprüft) brauchbar. |
| 11 | Datensicherung | ✓ | 0 | nein | Ohne Passwort, Meldung „Gespeichert unter: …“. |
| 12 | Programm schließen | ✓ | 0 | nein | Daten waren nach Neustart wieder da. |

## 3. Stolpersteine
### F1: Vorgeschlagener PDF-Ordner existiert nicht
- Schwere: erheblich (Vorbehalt: das echte Windows-Dialog kann sich anders verhalten)
- Wo: Export > Anmeldeformular / Ergebnisliste (Vorschlag `...\Termine\Ausdrucke\2026-11-14_Hundefreunde-Testhausen\...`)
- Was passiert ist: Bei Bestätigung des Vorschlags „PDF konnte nicht erstellt werden – Der Export ist fehlgeschlagen (z.B. Zielpfad nicht schreibbar oder Datei gerade in einem anderen Programm geöffnet): [Errno 2] No such file or directory: …“
- O-Ton: „Ich hab doch nur auf Speichern gedrückt. Was habe ich falsch gemacht?“
- Screenshot: shots/08_nach_pdf.png
- Vorschlag: Ordner vor dem Dialog automatisch anlegen; Fehlermeldung ohne „Errno“.

### F2: CSV-Import prüft nicht auf Doppelte
- Schwere: erheblich
- Wo: Teilnehmer > „Teilnehmerliste (Excel/CSV)…“
- Was passiert ist: Dieselbe Datei ein zweites Mal gewählt (nach einem Programmabbruch unsicher, ob es geklappt hatte) → „12 Teilnehmer importiert“, danach 26 statt 14 Zeilen, ohne Warnung. Beim PDF-Import steht „bereits vorhandene Meldungen werden übersprungen“, hier nicht. Löschen geht nur einzeln (bei Mehrfachauswahl ausgegraut), 12 Mal mit Rückfrage.
- O-Ton: „Jetzt sind alle doppelt – und ich muss jeden einzeln wegmachen?“
- Vorschlag: gleiche Doppel-Erkennung wie beim PDF-Import; „Löschen“ auch für mehrere Zeilen.

### F3: Programm beendete sich dreimal plötzlich
- Schwere: erheblich (Ursache offen; evtl. Testumgebung)
- Wo: nach Dateiauswahl im CSV-Import, beim Löschen (8. Löschung in Folge) und nach Enter im PDF-Speichern-Dialog (Etiketten, direkt nach einer Fehlermeldung).
- Was passiert ist: „Programm ist beendet“, kein Hinweis. Daten waren nach Neustart vorhanden (der CSV-Import war schon durchgelaufen).
- O-Ton: „Es ist einfach zugegangen. Ist jetzt alles weg?“
- Vorschlag: Absturzursache ansehen (Log ging beim Neustart verloren).

### F4: „45,5“ wird still zu 45
- Schwere: gering/erheblich
- Wo: Ergebniserfassung, Trümmerfeld Suche (Frank)
- Was passiert ist: Eingabe „45,5“; gespeichert und angezeigt „45“, Gesamt 75. Keine Meldung.
- Vorschlag: Meldung „nur ganze Punkte“ oder halbe Punkte zulassen.

### F5: Mittagspause „um 12:00“ landet bei 10:30
- Schwere: gering
- Wo: Zeitplan > Pause hinzufügen mit Haken „Bei allen Richtern“
- Was passiert ist: Statusmeldung „Pause bei 3 Richter(n) um 12:00 eingefügt.“, in der Liste steht aber „10:30–11:15 Pause: Mittagspause“ (Zeitplan endet schon vor 12:00, daher hinten angehängt).
- O-Ton: „Ich wollte 12 Uhr, da steht halb elf?“
- Vorschlag: Meldung mit tatsächlicher Uhrzeit oder Hinweis „Zeitplan endet vorher“.

### F6: „Startnummer tauschen“ ausgegraut bei zwei markierten Zeilen
- Schwere: gering
- Wo: Teilnehmer
- O-Ton: „Ich hab beide markiert und der Knopf geht nicht.“ (Es muss nur eine Person markiert sein, der Partner kommt in einem kleinen Fenster; das Fenster ist winzig, aber lesbar.)
- Screenshot: shots/17_tausch.png

### F7: Lange Importmeldung und Doppelmeldung
- Schwere: kosmetisch
- Wo: CSV-Import „Import abgeschlossen“ (8 Zeilen, jeweils gleicher Klammertext „Nur falls die Prüfung doch angeboten werden soll …“), danach sofort zweite Meldung „Startnummern fehlen“.
- Screenshot: shots/12_csv.png
- Vorschlag: Klammertext nur einmal, beide Meldungen zusammenfassen.

### F8: Restliche Fachwörter
- Schwere: kosmetisch
- „TN“ in „Offene Starts“, „.zip“ im Sicherungstext, „SH-R“ auf Etikett, „Gegenstand“/„gesucht in“ in der Maske.

## 4. Was gut lief
- Fenster beim Start groß, Teilnehmermaske vollständig sichtbar.
- Datumsmeldung mit Beispiel; deutsche Ja/Nein-Knöpfe.
- Hinweise im Reiter „Formular-Import“ zeigen den Weg (Anmeldeformular erzeugen im Export).
- Klare Ablehnungsgründe beim PDF-Import.
- Richter im Zeitplan automatisch, Pause für alle Richter in einem Schritt.
- Punkte-Fehlermeldung verständlich; ungespeicherte Zeilen werden angezeigt.
- Nach jedem PDF/Backup „Gespeichert unter: …“ mit vollem Pfad.
- Rangliste „1. von 4“ nachvollziehbar.

## 5. Gesamturteil
- Schulnote: Installation 2, Erststart 2, Turnierablauf 2-3, gesamt 2-3
- „Würde ich am Prüfungstag allein damit klarkommen?“ – Nein, eher mit Hilfe des Enkels: Der Fehler beim Speichern der PDFs im vorgeschlagenen Ordner, die unerklärten Programmabbrüche und das Doppel-Importieren würden Werner stark verunsichern. Sonst ist der Ablauf jetzt gut zu bewältigen.
- Wünsche: (1) Vorschlagsordner anlegen / keine „Errno“-Meldung, (2) Doppel-Erkennung beim CSV-Import und Mehrfach-Löschen, (3) Programmabstürze klären; Hinweis bei Komma-Punkten.

## 6. Grenzen dieses Tests
Dateiauswahl ist ein Qt-Ersatz (F1 evtl. nur dort); PDFs nur als Text geprüft (kein Viewer); „PDF/Ordner öffnen“ nicht sichtbar; die Programmabbrüche (F3) könnten von der Harness stammen; SmartScreen/Installation nur gedanklich; kein Hofmann in den Daten.

## 7. Nachtest-Abgleich
- U1 Startnummern einzeln / Doppelklick: teilweise – Doppelklick öffnet nun die Zeile und „Fehlende Startnummern vergeben…“ vergibt gesammelt, setzt aber vorher Bereiche unter Verwaltung voraus (Meldung erklärt es).
- U2 Automatisch verteilen, Dreikampf-Teams: behoben – im Plan keine Überschneidungen der Teams erlebt.
- U3 Teilnehmer-Maske zu schmal: behoben – Maske öffnet breit, nichts abgeschnitten.
- U4 CSV-Import nicht angebotene Prüfungen: behoben – Zeilen werden mit Grund als übersprungen gemeldet (nur lang und wiederholend).
- U5 CHECK-constraint / „45,5“: teilweise – Meldung bei 70 ist verständlich, „45,5“ wird aber weiter still zu 45.
- U6 Englische Knöpfe: behoben – „Ja/Nein“, „OK“ in allen Programm-Dialogen.
- U7 PDF-Speichern ohne Rückmeldung: behoben – jedes Mal „Gespeichert unter: …“ mit Pfad.
- U8 Richter nicht im Zeitplan: behoben – Anna, Bernd, Clara waren sofort als Spalten da.
- U9 Zeitplan-Bedienung/Mittagspause: teilweise – „Bei allen Richtern einfügen“ spart Arbeit, doch die Pause landete bei 10:30 statt 12:00 (F5).
- U10 Mitgliederliste einlesen nicht auffindbar: behoben – Knopf mit Tooltip im Reiter Teilnehmer und Erklärung im Reiter Formular-Import.
- U11 PDF Einzeldisziplin mit zwei Gegenständen: behoben – Hinweis „übernommen Leder, nicht übernommen Metall“ ist verständlich.
- U12 Fenster zu klein beim Start: behoben – Hauptfenster beim Start fast Vollbild, Termin-Dialog groß.
- U14 Fachwörter/Warnungen/Datumsmeldung: teilweise – Datumsmeldung mit Beispiel, AES/Prompt nicht mehr gesehen, wenige ⚠; aber „.zip“, „TN“, „SH-R“ und das Wort „Meldestelle“ bleiben.
- K1 „✓ gespeichert“ bei leeren Zeilen: nicht erlebt – alle Zeilen befüllt (nur der Disqualifizierte war leer, korrekt).
- K7 Mehrfach markieren: teilweise – Markieren und „Bezahlt umschalten“/„Keine Teilnahme“ gehen, „Löschen“ und „Tauschen“ nicht.
- K9 Rangliste „1. von 2“: behoben – „von N Startern“ stimmt mit den Teilnehmern; Absager nicht mitgezählt.
