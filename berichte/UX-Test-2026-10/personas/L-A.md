# UX-Bericht L-A – Gerda (71, Laiin, mit Handbuch)

## 1. Persona und Vorgehen

Gerda, 71, ist langjähriges Vereinsmitglied und Hundefreundin. Eine Prüfung hat sie noch nie organisiert. Sie hat schlechte Augen und nutzt am PC sonst nur E-Mail und Internet. Begriffe wie Datei, Ordner, Import, Export, CSV oder ZIP kennt sie nicht, englische Wörter versteht sie kaum, und sie hat Angst, etwas kaputt zu machen.

**Variante A: Sie hat das Handbuch ausgedruckt** (`docs/HANDBUCH.md` mit Bildern) und arbeitet es Kapitel für Kapitel ab. Zu Beginn hat sie auch die README gelesen.

Einmal hat sie die Hilfe im Programm geöffnet, bei Aufgabe 6, weil sie wissen wollte, wie Startnummern vergeben werden. Die Hilfe ist ein dichter Fließtext und hat ihr nicht weitergeholfen.

**Testleiter-Hilfe** gab es bei Aufgabe 4: Gerda hätte allein nicht erkannt, dass ihre „Excel-Liste“ über „Formular-Import → CSV importieren…“ eingelesen wird. Außerdem habe ich die Dateiauswahl-Fenster als Testleiter bedient. Dort musste Gerda vom vorgeschlagenen Termine-Ordner in „Downloads“ bzw. auf den „USB-Stick“ wechseln.

Der Lauf wurde zweimal von außen unterbrochen (API-Limit bzw. Testleitung). Das ist kein Programmfehler.

## 2. Aufgaben-Übersicht

| Nr | Aufgabe | Ergebnis | Fehlversuche | Handbuch/Hilfe nötig? | Kommentar |
|---|---|---|---|---|---|
| 0 | Installation (gedanklich) | ~ | – | Ja (README/Kap. 2) | SmartScreen-Hinweis gut erklärt (bekannt/akzeptiert). Das Handbuch Kap. 2 sagt nur „Datei von der Release-Seite laden“. Dass sie dort unter „Assets“ steht (eine englische GitHub-Seite), steht nur in der README. Wo die Datei nach dem Herunterladen liegt, steht nirgends. Gerda bräuchte den Enkel. |
| 1 | Erststart, Prüfung anlegen | ✓ | 1 | Ja (Kap. 3) | Startbildschirm klar, blauer Knopf fällt auf. Datum „14.11.26“ abgelehnt, Meldung verständlich, aber ohne Beispiel. Im Dialog steht „Cancel“. Verband und Meldestelle blieben leer, dafür gab es keinen Hinweis. |
| 2 | Leeres Anmeldeformular | ~ | 0 | Ja (Kap. 5, Schritt 2) | Der Knopf ist leicht zu finden. Das PDF wird aber still im Termine-Ordner gespeichert. Die Bestätigung erscheint als kleine Zeile am unteren Rand, die über dem Hilfetext klebt. Gerda weiß danach nicht, wo die Datei ist und wie sie sie an eine E-Mail hängen soll. |
| 3 | Zwei Nachmeldungen | ~ | 0 | Ja (Kap. 4) | Die Maske öffnet zu klein (780×640). Die linken Felder sind nur etwa 45 px breit, Eingaben werden abgeschnitten angezeigt („uster“, „/laria“). Rechts sind Felder angeschnitten, unten gibt es einen Schiebebalken. Dass „Trümmer“ hier „ED + Trümmerfeld“ heißt, stand im Handbuch. |
| 4 | Mitgliederliste (CSV) übernehmen | ✗ → mit Testleiter-Hilfe ✓ | 1 („Aus anderem Termin importieren…“) | Ja, half aber nicht | Die Wörter „Mitgliederliste“ und „Excel“ kommen weder im Programm noch im Handbuch vor. „CSV importieren“ steht im Handbuch unter „Per KI“. Gerda hielt das für etwas mit künstlicher Intelligenz. Danach liefen alle 20 Einträge ohne Rückfrage durch, auch Klassen, die nicht angeboten werden (LK 3, Fläche LK 2 usw.). |
| 5 | Vier PDF-Anmeldungen einlesen | ~ | 0 (1 Absturz, s. F12) | Ja (Kap. 5) | 2 Formulare kamen durch, 2 wurden mit Grund abgelehnt (mehrere Prüfungen angekreuzt; Trümmer LK 3 nicht angeboten). Die Gründe sind verständlich. Gerda würde Pfeiffer und Quast anrufen. Der Hinweis „angebotene Prüfungen: Reiter Verwaltung…“ verleitet aber dazu, LK 3 einfach freizuschalten. |
| 6 | Startnummern vergeben/tauschen, Absage | ~ | 3 | Ja (Kap. 4 + „Ausprobieren“) | Es gibt keine automatische Vergabe. Bei 22 Personen hieß das 22-mal „Bearbeiten“, Haken entfernen, Nummer tippen, OK. Danach wird zuerst „1“ vorgeschlagen, obwohl die 1 schon vergeben ist, daher kam die Fehlermeldung. Doppelklick auf eine Zeile öffnet nichts. Eine Rückfrage kam mit „Yes/No“. Tauschen und „Keine Teilnahme“ waren dann einfach. |
| 7 | Zeitplan mit Mittagspause | ~ | 0 | Ja (Kap. 6) | Die drei Richter aus den Termindaten musste Gerda erneut anlegen und umbenennen. Vor „Automatisch verteilen“ kam eine Warnung mit „ERSETZT… gehen verloren“ und Yes/No, obwohl noch gar kein Plan existierte. Die Pause landet am Ende der Liste und musste mit „Hoch“ hochgeschoben werden. Je Richter sind nur etwa 4 Zeilen zu sehen. Das PDF ist sehr gut. |
| 8 | Ergebnisse (≥8 Starts, 1 Disqualifikation, DK) | ~ | 2 | Ja (Kap. 7) | 13 Starts eingetragen. Ein Wert über 60 wurde zunächst angenommen, erst beim Speichern kam „CHECK constraint failed: suche_truemmerfeld BETWEEN 0 AND 60“. Ein fehlender Anzeigewert wurde verständlich gemeldet. Die Zahlen in den Zellen sind unten abgeschnitten. Leere Zeilen zeigen „✓ gespeichert“. |
| 9 | Sieger ansehen | ✓ | 0 | Nein | Die Rangliste ist übersichtlich, Disqualifizierte und Nicht-Bestandene sind rot. |
| 10 | PDFs (Ergebnisliste, Bögen, Etiketten) | ~ | 0 | Ja (Kap. 9) | Die PDFs sehen gut und gut lesbar aus. Nach dem Speichern öffnet sich aber nichts. Es gibt nur eine kleine Statuszeile mit langem Pfad. Im Auswahlfenster für die Bögen steht „(bisheriges Verhalten)“. In der Ergebnisliste steht beim Disqualifizierten in der Spalte Platz „nB“. |
| 11 | Datensicherung auf USB | ~ | 0 | Ja (Kap. 10) | Die Begriffe „ZIP“ und „AES-256“ sind unverständlich. Vorgeschlagen wird der Benutzerordner, nicht ein USB-Laufwerk, das muss Gerda selbst finden. Die Erfolgsmeldung steht nur als kleine Zeile ganz unten. |
| 12 | Schließen, Neustart, Daten da? | ✓ | 0 | Nein | 24 Teilnehmer, Ergebnisse und Pausen sind noch da. Auf dem Startbildschirm muss die Zeile erst angeklickt werden, sonst ist „Öffnen“ grau (Doppelklick geht). |

## 3. Stolpersteine

### F1: Teilnehmer-Maske öffnet zu klein, Eingaben werden abgeschnitten angezeigt
- Schwere: erheblich
- Wo: Teilnehmer → „Teilnehmer hinzufügen…“ / „Bearbeiten…“
- Was passiert ist: Der Dialog öffnet mit 780×640 px. Die Felder in der Spalte „Hundeführer & Kontakt“ sind nur etwa 45 px breit, getippter Text erscheint als „uster“, „/laria“, „usen“. Rechts sind „Startnummer steht noch nicht fest“ und die „gesucht in“-Felder angeschnitten. Unten gibt es einen waagerechten Schiebebalken, „Prüfungsgebühr bezahlt“ und „Halter weicht ab“ sind halb verdeckt. Im Handbuch-Bild ist der Dialog etwa 1000 px breit und sieht ordentlich aus.
- O-Ton Persona: „Ich hab doch ‚Muster‘ geschrieben, da steht ‚uster‘. Hab ich mich vertippt? Soll ich das nochmal machen?“
- Screenshot: shots/08_tn_dialog.png, shots/09_maria_ausgefuellt.png, shots/19_ok_schliesst_nicht.png
- Vorschlag: Mindestgröße bzw. Startgröße so wählen, dass alle Felder ganz sichtbar sind. Linke Felder mitwachsen lassen.

### F2: Mitgliederliste (Excel/CSV) für Laien nicht auffindbar
- Schwere: blockierend (für diese Persona)
- Wo: Reiter „Formular-Import“, Handbuch Kap. 5
- Was passiert ist: Gerda suchte „Mitgliederliste übernehmen“. Zuerst klickte sie „Aus anderem Termin importieren…“ und bekam „Kein anderer Termin gefunden…“ mit grauem OK und „Cancel“. Der Reiter „Formular-Import“ besteht zum Großteil aus einem englisch-technischen KI-Prompt (snake_case-Spalten). „CSV importieren…“ ist im Handbuch nur beim KI-Weg erklärt. Dass ihre Excel-Datei eine „CSV“ ist, kann Gerda nicht wissen, weil Windows die Endung ausblendet.
- O-Ton Persona: „Prompt? KI? Das ist doch nicht meine Liste vom Schriftführer. Da ruf ich lieber meinen Enkel an.“
- Screenshot: shots/10_aus_anderem_termin.png, shots/11_formular_import.png
- Vorschlag: Einen eigenen Knopf bzw. Abschnitt „Teilnehmerliste aus Excel/Tabelle übernehmen“ anbieten, auch im Reiter „Teilnehmer“. Den Handbuch-Abschnitt nicht unter „KI“ verstecken. Den Prompt-Text einklappen.

### F3: Rohe Datenbank-Fehlermeldung beim Speichern von Punkten
- Schwere: erheblich
- Wo: Ergebniserfassung → „Alle Ergebnisse speichern“
- Was passiert ist: Bei Suche = 75 ließ sich der Wert eintippen, beim Speichern kam: „Klein, Klaus – Trümmerfeld: CHECK constraint failed: suche_truemmerfeld BETWEEN 0 AND 60“.
- O-Ton Persona: „Was ist denn ein ‚Tschäck Konstreint‘? Hab ich jetzt was kaputt gemacht?“
- Screenshot: shots/29_speichern_fehler.png
- Vorschlag: Klartext wie „Suche Trümmerfeld: nur 0 bis 60 Punkte möglich“ (so macht es die Web-Version bereits). Das Feld besser schon beim Eintippen rot markieren.

### F4: Englische Knöpfe „Yes/No“ und „Cancel“ in Programm-Rückfragen
- Schwere: erheblich (für diese Persona)
- Wo: Rückfrage „Nur ein Gegenstand bei ED“, „Automatisch verteilen“, alle Dialoge (Termin anlegen, Teilnehmer, Pause, Sicherung …) mit „Cancel“
- Was passiert ist: Gerade bei Warnungen („gehen dabei verloren“, „werden nicht gespeichert“) muss Gerda auf „Yes“ oder „No“ klicken.
- O-Ton Persona: „Yes ist Ja, glaub ich … und was ist ‚Cancel‘? Ich trau mich nicht.“
- Screenshot: shots/20_ed_gegenstand_rueckfrage.png, shots/24_auto_verteilen.png
- Vorschlag: Die Qt-Übersetzung für Standardknöpfe laden („Ja/Nein/Abbrechen“).

### F5: Startnummern müssen einzeln vergeben werden, Vorschlag ist eine schon vergebene Nummer
- Schwere: erheblich
- Wo: Teilnehmer → „Bearbeiten…“ → Haken „Startnummer steht noch nicht fest“
- Was passiert ist: Importierte Teilnehmer haben keine Startnummer. Eine Funktion „alle durchnummerieren“ gibt es nicht, also bei 22 Personen 22-mal den Dialog öffnen. Nimmt man den Haken heraus, steht dort „1“ (schon an Maria Muster vergeben), und OK bringt „Startnummer bereits vergeben“. Doppelklick auf die Zeile öffnet nichts, obwohl er auf dem Startbildschirm funktioniert.
- O-Ton Persona: „22 Mal dasselbe? Und warum schlägt er mir die 1 vor, wenn die schon weg ist?“
- Screenshot: shots/18_bearbeiten_ohne_nr.png, shots/16_tauschen.png
- Vorschlag: Die nächste freie Nummer vorschlagen. Einen Knopf „Startnummern automatisch vergeben“ (z. B. nach Klasse) anbieten. Doppelklick soll „Bearbeiten“ öffnen.

### F6: Rückfrage „Gegenstand 2 und 3 werden nicht gespeichert“ bei Daten, die Gerda nie eingegeben hat
- Schwere: gering
- Wo: „Bearbeiten…“ bei Nora Neumann (per PDF-Formular eingelesen, ED LK 2)
- Was passiert ist: Nach dem Import steht bei ihr „Bei ED ist nur ein Gegenstand vorgesehen“. Laut Handbuch betrifft dieser Hinweis nur „ältere Daten“. Beim ersten Speichern kam dann eine Yes/No-Rückfrage, dass Einträge verloren gehen.
- O-Ton Persona: „Ich hab da gar nichts eingetragen. Geht jetzt was verloren?“
- Screenshot: shots/20_ed_gegenstand_rueckfrage.png
- Vorschlag: Beim PDF-Import für ED nur einen Gegenstand übernehmen (das Formular hat für LK 2 zwei Felder) oder den Fall still lösen.

### F7: Nach dem Erzeugen eines PDFs passiert sichtbar nichts
- Schwere: erheblich
- Wo: Reiter „Export“ (alle PDF-Knöpfe), Anmeldeformular
- Was passiert ist: Das Dateifenster schlägt den Termine-Ordner vor. Nach „Speichern“ öffnet sich nichts, es erscheint kein Hinweisfenster (geoeffnet.log blieb leer). Die einzige Rückmeldung ist eine kleine Textzeile ganz unten mit langem Pfad, die beim Anmeldeformular sogar mit dem abgeschnittenen Hilfetext verschmilzt. „Ablageort öffnen“ ist nicht als nächster Schritt angeboten.
- O-Ton Persona: „Hat er's jetzt gemacht? Wo ist das denn? Wie krieg ich das in meine E-Mail?“
- Screenshot: shots/07_nach_anmeldeformular.png, shots/32_export_nach_pdfs.png
- Vorschlag: Nach dem Speichern ein Fenster „PDF gespeichert – [Öffnen] [Ordner zeigen] [OK]“ zeigen. Fürs Anmeldeformular den Ordner „Dokumente“ oder „Desktop“ vorschlagen.

### F8: Zeitplan-Vorschlag setzt einen Hund gleichzeitig bei drei Richtern ein
- Schwere: erheblich (fachliche Plausibilität, für Laien nicht erkennbar)
- Wo: Zeitplan → „Automatisch verteilen…“
- Was passiert ist: Maria Muster mit Bello (DK LK 1) steht um 09:00–09:10 bei Anna (Behältnis), Bernd (Fläche) und Clara (Trümmer) zugleich, ebenso alle DK LK 1. Thiel steht um 10:50 bei Anna und Bernd. Gerda hätte das ausgedruckt und verschickt.
- O-Ton Persona: „Sieht ordentlich aus, schön bunt. Das schick ich so raus.“
- Screenshot: shots/25_zeitplan_verteilt.png (PDF: home/SHS-Pruefungsprogramm/Termine/Zeitplan_2026-11-14.pdf)
- Vorschlag: Beim Verteilen DK-Disziplinen zeitlich versetzen oder Überschneidungen sichtbar warnen.

### F9: Zeitplan: Richter doppelt eintragen, Pause landet am Ende, Warnung ohne Grund
- Schwere: gering
- Wo: Reiter „Zeitplan“
- Was passiert ist: Die drei im Termin eingetragenen Richter werden nicht übernommen. Gerda musste „Richter hinzufügen“ 3× klicken und 3× „Umbenennen…“ verwenden. „Automatisch verteilen“ warnt, dass Pausen und Reihenfolgen „verloren“ gehen, obwohl noch nichts da ist. „Pause hinzufügen…“ hängt die Pause ans Ende an (11:10–11:55), eine Uhrzeit lässt sich nicht wählen, man muss sie mit „Hoch“ verschieben. Die Listen je Richter zeigen nur 3–4 Zeilen, während die Knöpfe viel Platz brauchen.
- O-Ton Persona: „Die Richter hab ich doch vorhin schon eingegeben!“
- Screenshot: shots/23_zeitplan.png, shots/25_zeitplan_verteilt.png, shots/26_pause_dialog.png
- Vorschlag: Richter 1–5 aus den Termindaten vorbelegen. Die Warnung nur zeigen, wenn es schon einen Plan gibt. Bei der Pause „nach Eintrag …/um Uhrzeit …“ wählbar machen. Mehr Höhe für die Liste.

### F10: Kleine, kontrastarme Schrift und versteckte Statusmeldungen
- Schwere: erheblich (für diese Persona)
- Wo: Reiterleiste, Tabellen-Kopfzeilen, Statuszeilen (Export, Datensicherung, Zeitplan)
- Was passiert ist: Die Reiternamen und Spaltenköpfe sind hellgrau und klein. Erfolgsmeldungen („Sicherung erstellt: …“, „Zeitplan-Startzeit gespeichert.“) erscheinen nur als kleine Textzeile am Fensterrand, bei 1957 px Fensterbreite weit weg vom gedrückten Knopf. In der Ergebniserfassung sind die eingetippten Zahlen unten angeschnitten und die Statusspalte zeigt nur „nicht …“.
- O-Ton Persona: „Ich seh da oben fast nichts, so hellgrau. Und ob das jetzt gesichert ist, weiß ich nicht.“
- Screenshot: shots/05_hauptfenster.png, shots/28_ergebnis_eingetragen.png, shots/35_sicherung_fertig.png
- Vorschlag: Mehr Kontrast und Schriftgröße (evtl. Ansicht „Große Schrift“). Wichtige Erfolge als Meldungsfenster zeigen. Zellenhöhe korrigieren.

### F11: Fachbegriffe und Technikwörter ohne Erklärung
- Schwere: gering
- Wo: überall
- Was passiert ist: Unerklärt bleiben „ZIP“, „AES-256“, „Prompt“, „KI-System“, „OMA-Export“, „Import“, „(bisheriges Verhalten)“ (Bögen-Auswahl), „Datei(en)“ und „TT.MM.JJJJ“ (ohne Beispiel „14.11.2026“). Leere Ergebniszeilen zeigen „✓ gespeichert“. Die Warnungen „⚠ Gegenstand fehlt“ stehen in jeder Zeile in Orange, und Gerda weiß nicht, ob sie handeln muss.
- O-Ton Persona: „Überall Warnungen, das sieht aus, als wär alles falsch.“
- Screenshot: shots/13_teilnehmer_nach_csv.png, shots/31_boegen_auswahl.png, shots/34_sicherung_dialog.png
- Vorschlag: Alltagssprache verwenden („Sicherungsdatei“, „Datum z. B. 14.11.2026“). Bei leeren Zeilen „noch kein Ergebnis“ statt „gespeichert“ anzeigen.

### F12: Absturz beim Einlesen von vier Anmeldungen (vermutlich Testumgebung)
- Schwere: unklar (nicht reproduzierbar)
- Wo: Formular-Import → „Anmeldeformulare (PDF) importieren…“
- Was passiert ist: Mein erster Klick auf den Knopf (per Text) öffnete scheinbar kein Fenster. Nach erneutem Klick und Auswahl aller 4 Dateien war das Programm beendet. programm_ausgabe.log war leer, die Daten blieben erhalten. Ein zweiter Versuch mit denselben 4 Dateien lief fehlerfrei durch. Wahrscheinlich ein Timing-Effekt der Testumgebung (zwei Dateifenster), aber nicht sicher auszuschließen.
- O-Ton Persona: „Weg ist es! Jetzt hab ich's kaputt gemacht.“
- Screenshot: –
- Vorschlag: Entwickler sollten prüfen, ob ein doppelter Knopfdruck zwei Dateidialoge öffnen kann.

### F13: Handbuch setzt Wissen voraus bzw. widerspricht sich
- Schwere: erheblich
- Wo: docs/HANDBUCH.md
- Was passiert ist:
  - Kap. 2: Kein Wort zu „Assets“, Download-Ordner oder Doppelklick auf die heruntergeladene Datei.
  - Kap. 3: Pfade wie `*.sqlite` und `JJJJ-MM-TT_Verein.sqlite` schrecken ab.
  - Kap. 4: Startnummern-Vergabe für importierte Teilnehmer steht nur im Abschnitt „Ausprobieren mit Beispieldaten“.
  - Kap. 5: Mitgliederlisten bzw. Excel werden nicht erwähnt.
  - Kap. 6: Der Kasten „Wichtig zu Entfernen“ rät „Fällt ein Teilnehmer aus, einfach im Reiter Teilnehmer löschen“. Das widerspricht der neuen Funktion „Keine Teilnahme“ (Kap. 4) und hätte Gerda zum Löschen von Herrn Hofmann verleitet.
  - Kap. 3: Verband und Meldestelle werden nur als „brauchst du für das Anmeldeformular“ erwähnt. Ohne sie bleibt der Formularkopf leer, und Gerda merkte das nicht.
  - Positiv: Die Reihenfolge in Kap. 1 („Ablauf“) ist eine gute Checkliste.
- O-Ton Persona: „Da steht ‚einfach löschen‘ … aber vorne steht ‚nicht löschen, keine Teilnahme‘. Was denn nun?“
- Screenshot: –
- Vorschlag: Kap. 6 an „Keine Teilnahme“ anpassen. Einen Abschnitt „Teilnehmerliste aus Excel übernehmen“ ergänzen. Ein Kapitel „Erste Prüfung Schritt für Schritt“ für Laien mit Klickfolgen anlegen. Bei der Installation die Download-Schritte bebildern.

## 4. Was gut lief
- Der Startbildschirm ist aufgeräumt, der blaue Hauptknopf zeigt, was zu tun ist.
- Die Datumsfehlermeldung kam sofort und ohne Datenverlust. Die Pflichtfelder sind mit * markiert.
- Die Ablehnungsgründe beim PDF-Import sind verständlich formuliert (mehrere Prüfungen angekreuzt, nicht angeboten, bereits vorhanden).
- „Startnummer tauschen…“ und „Keine Teilnahme“ funktionieren mit einem Klick. Herr Hofmann fehlt danach in Zeitplan und Ergebniserfassung, die Schaltfläche wechselt zu „Teilnahme wiederherstellen“.
- Die Ergebniserfassung zeigt gelbe Zeilen für ungespeicherte Werte. Disqualifiziert per Haken war einfach. Gespeichert wurde alles Gültige, auch wenn einzelne Zeilen fehlschlugen.
- Die Auswertung ist übersichtlich, mit Rot für nB/DISQ und „1. von 3“.
- Die PDFs (Zeitplan, Ergebnisliste, Etiketten, Bewertungsbögen mit vorausgefüllten Punkten) sind sauber, farbig und gut lesbar.
- Daten bleiben nach Schließen und Neustart vollständig erhalten. Die Datensicherung lief ohne Passwort problemlos.

## 5. Gesamturteil
- Schulnoten: Installation 3–4 / Erststart 3 / Turnierablauf 4 / gesamt 4
- „Würde ich am Prüfungstag allein damit klarkommen?“ **Nein.** Ergebnisse eintragen und die Rangliste ansehen könnte Gerda nach einer Einweisung schon. Die Vorbereitung schafft sie ohne Hilfe nicht: Excel-Liste einlesen, 22 Startnummern vergeben, PDFs wiederfinden und verschicken, Zeitplan prüfen. Englische Rückfragen und technische Fehlermeldungen verunsichern sie stark.
- Die 3 wichtigsten Wünsche:
  1. Alles auf Deutsch und in Alltagssprache: Ja/Nein/Abbrechen, Klartext statt „CHECK constraint“, keine ZIP/AES/Prompt-Begriffe ohne Erklärung.
  2. Startnummern automatisch vergeben und ein klarer Weg „Teilnehmerliste aus Excel übernehmen“.
  3. Nach jedem PDF bzw. jeder Sicherung ein deutliches Fenster „Gespeichert unter … [Öffnen] [Ordner zeigen]“. Größere, kontrastreichere Schrift und eine Teilnehmer-Maske, die vollständig sichtbar ist.

## 6. Grenzen dieses Tests
- Die Installation (Download, SmartScreen, Updates) wurde nur gedanklich nachvollzogen.
- Das Dateiauswahl-Fenster war ein englischer Qt-Ersatz und wurde von mir als Testleiter bedient. Ob Gerda im echten Windows-Dialog „Downloads“ oder den USB-Stick findet, ist nicht geprüft. Vermutlich wäre es schwierig, weil jeweils der Termine-Ordner bzw. Benutzerordner vorgeschlagen wird.
- Das Öffnen von PDFs oder Ordnern durch Windows war nicht sichtbar. Die PDFs habe ich direkt angesehen.
- Fenstergrößen hängen vom virtuellen Bildschirm (1920×1080) ab. Das Hauptfenster wurde zwischenzeitlich 1957 px breit, auf einem echten Laptop kann das anders aussehen.
- Den Absturz (F12) kann ich nicht sicher dem Programm zuordnen.
- Die Unterbrechungen des Laufs durch die Testleitung bzw. das API-Limit sind keine Programmfehler.
