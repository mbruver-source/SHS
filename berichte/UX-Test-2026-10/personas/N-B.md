# UX-Bericht N-B – Tobias (Kassenwart, ohne Handbuch)

## 1. Persona und Vorgehen

Tobias, 41, Kassenwart, war bei Prüfungen bisher nur Helfer. Er kennt Outlook, Word und etwas Excel, liest ungern lange Texte, probiert lieber aus und klickt Meldungen schnell mit „OK“ weg.
Variante **B (ohne Handbuch)**:
- **Installation:** nur über die Website (`docs/index.html`) und die GitHub-Release-Seite durchgespielt. README und Handbuch waren dafür nicht nötig.
- **Hilfe im Programm (❓ Hilfe):** einmal benutzt, bei Aufgabe 6 (Startnummern). Zuvor gab es 2 Fehlversuche: „Startnummer tauschen…“ bei Teilnehmern ohne Nummer, danach Suche im Reiter „Verwaltung“. Die Hilfe beantwortet die Frage nicht. Sie sagt nur, dass die Startnummer „automatisch vorgeschlagen“ wird, und schreibt beim Beispiel-CSV „danach im Reiter Teilnehmer die Startnummern vergeben“, aber nicht, wie.
- **Handbuch (`docs/HANDBUCH.md`):** einmal geöffnet, nach 3 erfolglosen Versuchen (zusätzlich zu den beiden oben: „Bearbeiten…“ bei Bauer, abgelehnt wegen doppelter Nr.). Zweck: herausfinden, wie importierte Teilnehmer Startnummern bekommen. Ergebnis (Zeile 295): einzeln über „Bearbeiten…“. Es gibt keine Sammelvergabe.
- Hinweis: Das Programm wurde zweimal von der Testleitung unterbrochen und neu gestartet. Das ist kein Programmfehler.

## 2. Aufgaben-Übersicht

| Nr | Aufgabe | Ergebnis | Fehlversuche | Handbuch/Hilfe nötig? | Kommentar |
|----|---------|----------|--------------|------------------------|-----------|
| 0 | Installation (gedanklich) | ~ | 0 | nein | Website führt gut zur Download-Seite, die Schritte und die SmartScreen-Warnung sind erklärt (bekannt/akzeptiert). Die Release-Seite hat praktisch keine Release-Notes (nur der Link „v1.0.38...v1.0.39“). Tobias weiß nicht, was neu ist. Die Assets-Liste lud beim Abruf erst mit Fehlermeldung (vermutlich GitHub, nicht das Programm). |
| 1 | Erststart + Prüfung anlegen | ✓ | 1 | nein | Startfenster ist klar. Das Datum „14.11.26“ wird mit einer verständlichen Meldung abgelehnt. „Behältnisse/Fläche“-Haken liegen unterhalb der Scrollkante. |
| 2 | Leeres Anmeldeformular | ✓ | 0 | nein | Im Reiter „Export“ sofort gefunden, das PDF ist sauber. Die Bestätigung ist nur eine kleine Statuszeile, die den Hinweistext überlappt. |
| 3 | Zwei Nachmeldungen von Hand | ~ | 0 | nein | Funktioniert, aber die Erfassungsmaske ist gequetscht: Felder links sind etwa 45 px breit, Text wird abgeschnitten, horizontaler Scrollbalken. |
| 4 | CSV-Mitgliederliste | ✓ (mit Folgefehler) | 1 | nein | Zuerst „Aus anderem Termin importieren…“ probiert (falscher Weg). Danach Reiter „Formular-Import“ → „CSV importieren…“ problemlos. **Aber:** Teilnehmer in nicht angebotenen Prüfungen (LK 3, ED LK 2 Fläche/Behältnis) werden ohne jeden Hinweis übernommen. |
| 5 | 4 PDF-Anmeldungen | ~ | 1 | nein | Beim ersten Versuch (4 Dateien zugleich) beendete sich das Programm ohne Meldung. Das ließ sich danach nicht wiederholen, siehe F12. Danach: 2 importiert, Pfeiffer (2 Prüfungen) und Quast (LK 3) mit klaren Gründen abgelehnt. Pfeiffer von Hand erfasst, Quast würde ich anrufen. |
| 6 | Startnummern / Tausch / Absage | ~ | 3 | **Hilfe + Handbuch** | Für 22 importierte Teilnehmer gibt es keine Startnummern und keine Sammelvergabe: 22-mal „Bearbeiten…“. Tauschen und „Keine Teilnahme“ funktionieren dann einwandfrei. |
| 7 | Zeitplan 9:00 + Mittagspause | ~ | 1 | nein | Die Richter aus dem Termin werden nicht übernommen (anlegen + 3× umbenennen). Pause muss je Richter einzeln angelegt werden. Hoch/Runter springt blockweise. **Automatischer Vorschlag plant dieselben DK-Hunde gleichzeitig bei 3 Richtern ein.** |
| 8 | Ergebnisse (≥ 8 Starts, 1 Disq, DK) | ✓ | 2 | nein | Tabelle ist gut verständlich (Bereiche 0–60/0–40 stehen dabei). Verwechselte Suche/Anzeige → technische Datenbank-Fehlermeldung. Halbe DK-Eingabe → gute Meldung. |
| 9 | Rangliste | ✓ | 0 | nein | Klar, mit Wertnote und Platz. |
| 10 | Ergebnisliste, Bögen, Etiketten (PDF) | ✓ | 0 | nein | Alle drei erzeugt und brauchbar. Ein Programmende beim Etiketten-Speichern war nicht reproduzierbar (F12). |
| 11 | Datensicherung auf USB | ✓ | 0 | nein | Einfach. Ohne Passwort ist es mit einem Klick erledigt, die Erfolgsmeldung steht nur ganz unten in einer Statuszeile. |
| 12 | Schließen + Neustart | ✓ | 0 | nein | Alles noch da, auch ein ungespeichertes Ergebnis wurde beim Schließen automatisch gesichert. |

## 3. Stolpersteine

### F1: Automatischer Zeitplan plant denselben Hund gleichzeitig bei mehreren Richtern
- Schwere: **erheblich**
- Wo: Reiter „Zeitplan“ → „Automatisch verteilen…“ (3 Richter)
- Was passiert ist: Der Vorschlag setzt die DK-LK-1-Teams (Muster/Bello, Otto/Oona, Otto/Odin, Pohl, Quandt) von 09:00 bis 09:50 **gleichzeitig** bei Anna Richter (Behältnis), Bernd Berger (Fläche) und Clara Christ (Trümmer) ein. Ebenso Roth/Rocky um 10:20 bei Anna Richter (DK LK 2 Trümmer) und bei Clara Christ (DK LK 2 Fläche) sowie Thiel/Tyson um 10:50 bei zwei Richtern. Weder in der Ansicht noch im PDF gibt es eine Warnung, die Seitenleiste zeigt alles grün „✓“.
- O-Ton: „Super, alles grün … Moment, Maria Muster soll um 9 Uhr an drei Stellen gleichzeitig sein?“ (fällt erst beim Durchlesen des PDFs auf)
- Screenshot: shots/42_zeitplan_vorschlag.png (PDF: home/SHS-Pruefungsprogramm/Termine/Zeitplan_2026-11-14.pdf)
- Vorschlag: Beim Verteilen die DK-Disziplinen eines Teams zeitlich versetzen oder Überschneidungen (gleiche Start-Nr. zur gleichen Zeit) rot markieren.

### F2: Keine Sammelvergabe von Startnummern nach Import
- Schwere: **erheblich**
- Wo: Reiter „Teilnehmer“ nach CSV/PDF-Import
- Was passiert ist: 22 importierte Teilnehmer haben keine Startnummer. „Startnummer tauschen…“ bietet „(Start-Nr. keine)“ an. Hilfe und Verwaltung erklären nichts, das Handbuch sagt: einzeln über „Bearbeiten…“. Wer dort das Häkchen „Startnummer steht noch nicht fest“ entfernt, bekommt **1** vorgeschlagen, obwohl die 1 schon vergeben ist. Die Fehlermeldung „Startnummer bereits vergeben“ ist dafür sehr gut. Nach dem Speichern springt die Markierung auf einen anderen Teilnehmer.
- O-Ton: „22-mal Bearbeiten, Haken weg, Nummer tippen? Das mache ich doch nicht am Abend vor der Prüfung.“
- Screenshot: shots/22_tauschen_ohne_nr.png, shots/31_startnr_doppelt.png
- Vorschlag: Knopf „Startnummern vergeben…“ (fortlaufend, z. B. nach Art/LK). Beim Entfernen des Häkchens die kleinste freie Nummer vorschlagen.

### F3: CSV-Import übernimmt nicht angebotene Prüfungen ohne Hinweis
- Schwere: **erheblich**
- Wo: Reiter „Formular-Import“ → „CSV importieren…“
- Was passiert ist: Meldung nur „20 Teilnehmer importiert.“ Darunter sind ED LK 3, DK LK 3, ED LK 2 Fläche/Behältnis, die am 14.11. gar nicht angeboten werden. Sie landen auch im Zeitplan, in den Bewertungsbögen und auf den Etiketten. Der PDF-Import lehnt genau das dagegen ab („Trümmer LK 3 wird in diesem Termin nicht angeboten“). Das ist uneinheitlich.
- O-Ton: „20 importiert, prima.“ (Fehler bleibt unbemerkt)
- Screenshot: shots/14_csv_ergebnis.png, shots/15_teilnehmer_nach_csv.png
- Vorschlag: Gleiche Prüfung wie beim PDF-Import, mindestens als Warnung („7 Teilnehmer in nicht angebotenen Prüfungen – trotzdem übernehmen?“) und als ⚠ in „Anmerkungen“.

### F4: Technische Datenbank-Meldung bei verwechselter Suche/Anzeige
- Schwere: erheblich (für diese Persona)
- Wo: Reiter „Ergebniserfassung“ → „Alle Ergebnisse speichern“
- Was passiert ist: Bei Klein/Fee wurde 35 als Suche und 55 als Anzeige eingetippt (vertauscht). Das Feld nimmt 55 an, ohne Markierung. Beim Speichern kommt: „Klein, Klaus – Trümmerfeld: CHECK constraint failed: anzeige_truemmerfeld BETWEEN 0 AND 40“. Die übrigen Zeilen wurden gespeichert, die Zeile bleibt „● nicht gespeichert“ (gut).
- O-Ton: „CHECK constraint … was? Ist jetzt was kaputt?“ Er klickt OK, und nur wer die gelbe Zeile bemerkt, korrigiert.
- Screenshot: shots/46_speichern_fehler.png
- Vorschlag: Klartext wie bei der DK-Meldung („Anzeige darf höchstens 40 sein – Suche und Anzeige vertauscht?“), das Feld sofort beim Tippen rot markieren. Ähnlich wurde „45,5“ stillschweigend zu „45“.

### F5: Anmeldeformulare eines anderen Termins werden teils still übernommen
- Schwere: gering
- Wo: „Anmeldeformulare (PDF) importieren…“
- Was passiert ist: Alle vier PDFs stammen vom Formular „DEMO Hundefreunde Musterstadt, 03.10.2026“. Neumann und Otto wurden ohne Hinweis in den Termin 14.11. Testhausen übernommen, nur Quast fiel wegen LK 3 auf. Bei Neumann wurden zwei Gegenstände für ED eingelesen, beim „Bearbeiten“ kam dann „Nur ein Gegenstand bei ED … Trotzdem speichern? Yes/No“. Mit Yes ging „Metall“ verloren.
- O-Ton: „Dass das ein Formular von einem anderen Verein war, hab ich gar nicht gemerkt.“
- Screenshot: shots/34_ed_gegenstand_frage.png
- Vorschlag: Veranstalter/Datum des Formulars mit dem Termin vergleichen und warnen.

### F6: Teilnehmer-Erfassungsmaske gequetscht
- Schwere: erheblich
- Wo: Dialog „Teilnehmer erfassen/bearbeiten“
- Was passiert ist: Die linke Spalte (Name, Verein, Adresse) hat winzige Eingabefelder, Text wird abgeschnitten („nrad“ statt „Conrad“, „rdorf“). Rechts ist „Startnummer steht noch nic…“ abgeschnitten, unten ein horizontaler Scrollbalken. „Prüfungsgebühr bezahlt“ und „Halter weicht ab“ liegen halb unter der Kante.
- O-Ton: „Ich sehe gar nicht, was ich da reingetippt habe.“
- Screenshot: shots/09_teilnehmer_dialog.png, shots/33_conrad_ok_haengt.png
- Vorschlag: Dialog größer öffnen bzw. Felder mit Mindestbreite, einspaltig oder mit Reitern.

### F7: Richter aus dem Termin werden im Zeitplan nicht übernommen
- Schwere: gering
- Wo: Reiter „Zeitplan“
- Was passiert ist: Anna Richter, Bernd Berger und Clara Christ sind beim Termin eingetragen. Im Zeitplan steht „Noch keine Richter angelegt“, „Richter hinzufügen“ erzeugt „Richter 1“, danach muss man jeden über „Umbenennen…“ umbenennen. Die Mittagspause muss je Richter separat angelegt werden und landet am Ende. „Hoch/Runter“ springt je Block über mehrere Zeilen (3→6→9→11), was überrascht, weil die Liste Einzelzeilen zeigt.
- O-Ton: „Die hab ich doch schon eingetippt!“
- Screenshot: shots/37_zeitplan.png, shots/40_umbenennen.png
- Vorschlag: Richter aus den Veranstaltungsdaten vorbelegen. „Pause für alle Richter um …“ anbieten.

### F8: Englische Knöpfe in Programmdialogen
- Schwere: gering
- Wo: alle Dialoge („Cancel“), Rückfragen („Yes“/„No“)
- Was passiert ist: Die Oberfläche ist deutsch, aber z. B. „Nur ein Gegenstand bei ED … Trotzdem speichern?“ hat „Yes/No“ und „Automatisch verteilen“ ebenfalls. Bei Tobias' Schnellklick-Verhalten zählt jede Sekunde Lesezeit.
- Screenshot: shots/41_auto_verteilen.png, shots/34_ed_gegenstand_frage.png
- Vorschlag: Qt-Übersetzung laden bzw. „Ja/Nein/Abbrechen“.

### F9: Erfolgsmeldungen nur als kleine Statuszeile, teils überlappend
- Schwere: gering
- Wo: Reiter „Export“ und „Datensicherung“
- Was passiert ist: Nach dem Speichern des Anmeldeformulars steht „Anmeldeformular gespeichert: C:/…“ über dem Hilfetext, die Zeilen überlappen sich sichtbar. Bei der Sicherung steht „Sicherung erstellt …“ ganz unten am Fensterrand.
- Screenshot: shots/08_anmeldeformular_ok.png, shots/52_sicherung_ok.png
- Vorschlag: Kurze Meldung mit Knopf „Ordner öffnen“ bzw. Statuszeile ohne Überlappung.

### F10: Hauptfenster ändert je Reiter seine Breite
- Schwere: gering
- Wo: Hauptfenster, Reiter „Verwaltung“ / „Zeitplan“ / „Datensicherung“
- Was passiert ist: Die Fensterbreite springt von 1196 auf 1957 px (breiter als der 1920er-Bildschirm, „Hilfe“ rutscht an den Rand) und später auf 1324 px. Vermutlich wächst das Fenster mit langen Hinweistexten.
- Screenshot: shots/23_verwaltung.png
- Vorschlag: Hinweistexte umbrechen, Fenstergröße stabil halten.

### F11: Gefährliche Schnell-OK-Stellen
- Schwere: gering
- Wo: Sicherung, ED-Gegenstand-Rückfrage, Speichern mit Fehlern
- Beobachtung:
  - „Mit Passwort schützen“ ist standardmäßig aus. Mit einem OK liegen Teilnehmerdaten (Adressen, Telefon) unverschlüsselt auf dem USB-Stick.
  - „Trotzdem speichern? Yes“ verwirft den zweiten Gegenstand kommentarlos.
  - „Nicht alle Ergebnisse gespeichert – OK“: Wer die gelbe Zeile übersieht, hat ein fehlendes Ergebnis.
  - Positiv: „Automatisch verteilen“ und „Startnummer bereits vergeben“ warnen deutlich.
- Vorschlag: Bei Sicherung auf Wechseldatenträger zum Passwort raten. Nach „nicht gespeichert“ zur betroffenen Zeile springen.

### F12: Zwei nicht reproduzierbare Programmenden ohne Meldung
- Schwere: unklar (vermutlich Testumgebung)
- Wo: direkt nach Auswahl im Dateifenster (1× PDF-Import mit 4 Dateien, 1× „Etiketten speichern“ als dritter Export in schneller Folge)
- Was passiert ist: Das Programm war plötzlich beendet, `programm_ausgabe.log` war leer, es gab keinen Traceback. Bereits gespeicherte Daten waren beim Neustart vollständig da. Wiederholung derselben Aktion nach Neustart lief beide Male fehlerfrei. Weil das Dateifenster in der Testumgebung ersetzt ist, ist eine Ursache in der Testumgebung wahrscheinlich.
- Vorschlag: Bei Bedarf mit echtem Windows-Dateidialog gegenprüfen.

### F13: Kleinigkeiten
- Schwere: kosmetisch
- Beobachtungen:
  - Ergebniserfassung zeigt vor jeder Eingabe „✓ gespeichert“ (gemeint: nichts offen).
  - „von 2“ in der Rangliste DK LK 1, obwohl 5 gemeldet (zählt nur gewertete).
  - Namenslisten „Graf, Greta, Iske, Ina, …“ sind schwer lesbar (Komma doppelt belegt).
  - Etikett „Pfeiffer, Paul, , Pepper“ (leerer Verein).
  - „Standardmäßig sind alle angehakt (bisheriges Verhalten)“: Entwicklersprache.
  - Anmeldeformular hat für LK 2 zwei Gegenstandsfelder, auch für ED-Starter (dort nur einer erlaubt).
  - Ort „Testhausen“ erscheint nicht auf dem Anmeldeformular.

## 4. Was gut lief
- Das Startfenster und „Neuen Termin anlegen“ sind selbsterklärend. Der Dateiname wird automatisch und korrekt nachgezogen.
- Datumsfehler- und Doppel-Startnummer-Meldungen sagen klar, was zu tun ist.
- PDF-Import-Bericht: verständliche Gründe pro Datei, Duplikate werden erkannt („Nora Neumann mit Nala ist bereits gemeldet“).
- „Keine Teilnahme“ und „Startnummer tauschen“ sind je ein Klick und eindeutig. Hofmann verschwindet korrekt aus Zeitplan, Erfassung und Etiketten.
- Die Ergebniserfassung zeigt die Punktebereiche (0–60 / 0–40) in den Spaltenköpfen. Das hilft gegen die Verwechslung Suche/Anzeige, gelbe Markierung für Ungespeichertes.
- Disqualifikation per Haken sperrt die Punktefelder, und die Auswertung rechnet sofort.
- Die PDFs (Ergebnisliste, Etiketten, Bewertungsbögen, Zeitplan) sehen ordentlich aus und sind direkt verwendbar.
- Ungespeicherte Ergebnisse werden beim Schließen automatisch gesichert. Nach dem Neustart war alles da.
- Die Hilfe im Programm ist ausführlich und gut gegliedert (nur eben ohne Antwort zur Startnummern-Vergabe).

## 5. Gesamturteil
- Schulnoten:
  - Installation: **2-** (gute Website, magere Release-Notes; SmartScreen bekannt/akzeptiert)
  - Erststart: **2**
  - Turnierablauf: **3-** (Startnummern-Mühe, gefährlicher Zeitplan-Vorschlag, CSV ohne Prüfung)
  - Gesamt: **3**
- „Würde ich am Prüfungstag allein damit klarkommen?“ – **Eher ja, mit Einschränkung.** Ergebnisse eintragen, Rangliste und Drucken schafft Tobias allein. Die Vorbereitung (Startnummern für Importe, Zeitplan) würde er ohne Hilfe falsch oder sehr mühsam machen. Den Doppelbelegungs-Fehler im automatischen Zeitplan hätte er wahrscheinlich erst am Prüfungstag bemerkt.
- Die 3 wichtigsten Wünsche:
  1. Automatischer Zeitplan ohne gleichzeitige Einplanung desselben Teams, plus sichtbare Warnung bei Überschneidungen.
  2. Knopf „Startnummern automatisch vergeben“ (und beim Entfernen des Häkchens die nächste freie Nummer vorschlagen).
  3. CSV-Import prüft angebotene Prüfungen wie der PDF-Import. Verständliche Meldungen statt „CHECK constraint failed“.

## 6. Grenzen dieses Tests
- Das Dateiauswahl-Fenster ist ein englischer Qt-Ersatz. Ob die zwei Programmenden (F12) auch mit dem echten Windows-Dialog auftreten, ist offen.
- „PDF öffnen“/„Ordner öffnen“ und der echte Download, die Installation sowie SmartScreen konnten nicht erlebt werden. Die GitHub-Assets-Liste war im Abruf nicht sichtbar (Ladefehler der Seite), Dateinamen sind daher nur von der Website bekannt.
- Bildschirm ist virtuell, und das Hauptfenster war nur 600 px hoch. Ob die engen Listen im Zeitplan und der gequetschte Teilnehmerdialog auch bei maximiertem Fenster so wirken, ist nicht sicher.
- Mausrad, Drag & Drop, Tooltips beim Überfahren und Tastenkürzel ließen sich nur eingeschränkt nutzen. Hilfetext konnte nur per Pfeiltaste gescrollt werden.
- Die Startnummern-Vergabe für 20 Teilnehmer lief per Skript-Schleife. Die echte Bearbeitungszeit eines Menschen (geschätzt 15–20 Min.) ist daher geschätzt.
- Einmal traf ein Klick per Text versehentlich ein anderes Element (Testumgebungs-Artefakt, nicht bewertet).
