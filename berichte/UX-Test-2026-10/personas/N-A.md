# UX-Bericht N-A – Julia (normales Vereinsmitglied, mit Handbuch)

## 1. Persona und Vorgehen

Julia, 34, Hundeführerin. Sie organisiert zum ersten Mal eine SHS-Prüfung. Am PC kennt sie E-Mail,
Word und Online-Banking. Bei Wörtern wie „CSV“, „Import“ oder „Datenbank“ ist sie unsicher, und wenn
etwas „überschrieben“ oder „gelöscht“ werden könnte, wird sie vorsichtig.
Variante A: Vor dem Start hat Julia `README.md` und das komplette `docs/HANDBUCH.md` gelesen. Die
Kapitel 1–10 hat sie gründlich gelesen, die Kapitel 11/12 (Web) nur überflogen. Bilder hat sie sich
angesehen (Termin-Dialog, Teilnehmer-Dialog DK).
Nachgeschlagen hat sie unterwegs bei
- „Startnummern vergeben“ (Kap. 4 und „Ausprobieren mit Beispieldaten“),
- „Anmeldeformular“ (Kap. 5),
- „Pause im Zeitplan“ (Kap. 6).
Die Hilfe im Programm (❓) hat sie einmal geöffnet, als sie nach einer Sammel-Vergabe von
Startnummern suchte. Dort stand nichts dazu.

**Urteil zum Handbuch:** Insgesamt gut verständlich. Die Tabelle in Kap. 1 („Wann / Was / Wo“) ist für
Julia der wertvollste Teil, weil sie den roten Faden liefert. Die Kapitel folgen den Reitern im Programm
und nicht ihrem Arbeitsablauf. Das Anmeldeformular steht zum Beispiel unter „5. Formular-Import“, erzeugt
wird es aber im Reiter „Export“. Fachsprache, die Julia stocken ließ: „CSV“, „UTF-8-kodiert“,
„Stammdaten“, „AES-256“, „`*.sqlite`“, „ältere Daten“, „Prompt“. Die Bilder helfen. Das Bild vom
Teilnehmer-Dialog zeigt aber ein deutlich breiteres Fenster als das, das bei ihr aufging (siehe F2).
Was im Handbuch fehlt:
- wie man **viele Startnummern auf einmal** vergibt (es gibt dafür nur den Umweg über 22× „Bearbeiten…“);
- dass Richter, die schon beim Termin eingetragen sind, im Zeitplan noch einmal angelegt werden müssen;
- dass eine Mitgliederliste vom Schriftführer über „CSV importieren…“ eingelesen wird. Das Handbuch
  beschreibt den CSV-Import nur im Zusammenhang mit der KI.

## 2. Aufgaben-Übersicht

| Nr | Aufgabe | Ergebnis | Fehlversuche | Handbuch/Hilfe nötig? | Kommentar |
|---|---|---|---|---|---|
| 0 | Installation (gedanklich) | ✓ | 0 | ja (README, Kap. 2) | Die SmartScreen-Anleitung ist klar (bekannt/akzeptiert). „Assets“ auf GitHub ist ein Fremdwort, mit dem Dateinamen im README aber lösbar. |
| 1 | Erststart, Prüfung anlegen | ✓ | 1 | ja (Kap. 3) | Datum „14.11.26“ wurde abgelehnt, die Meldung ist verständlich. Den Verband hat Julia leer gelassen, weil sie ihn nicht kannte. Es kam kein Hinweis. |
| 2 | Leeres Anmeldeformular | ✓ | 0 | ja (Kap. 5) | Wird unter „Export“ gefunden. Gespeichert wird in den versteckten Termine-Ordner (siehe F7). Das PDF ist gut. |
| 3 | Zwei Nachmeldungen von Hand | ~ | 0 | nein | Der Dialog ist zu schmal, man sieht nicht, was man tippt (F2). |
| 4 | Mitgliederliste (CSV) übernehmen | ✓ | 0 | ja (Kap. 5) | „20 Teilnehmer importiert“. Teilnehmer für nicht angebotene Prüfungen (LK 3 usw.) wurden stillschweigend übernommen (F4). |
| 5 | 4 Anmeldungs-PDFs einlesen | ✓ | 0 | nein | 2 ok, 2 mit klarem Grund abgelehnt. Alle vier Formulare stammen von einem anderen Verein/Termin, trotzdem kam kein Hinweis (F5). |
| 6 | Startnummern vergeben, tauschen, Absage | ~ | 3 | ja (Kap. 4 + Hilfe) | Es gibt keine Sammel-Vergabe, also 22× Dialog (F1). Der Tausch und „Keine Teilnahme“ sind dagegen vorbildlich. |
| 7 | Zeitplan 9:00 mit Mittagspause | ~ | 1 | ja (Kap. 6) | Richter mussten neu angelegt und umbenannt werden (F6). Die Pause landet am Ende (F9). Der Vorschlag setzt denselben DK-Hund gleichzeitig bei 3 Richtern an (F3). |
| 8 | Ergebnisse (11 Starts, 1 Disq., 2 DK) | ✓ | 2 (absichtlich) | nein | Gelbe Markierung super. Bei einem Wert über 60 kommt eine technische Datenbankmeldung (F8). |
| 9 | Rangliste ansehen | ✓ | 0 | nein | Gut verständlich, Rot für nB/Disq. |
| 10 | Ergebnisliste, Bögen, Etiketten (PDF) | ✓ | 1 | nein | Beim ersten Speichern der Etiketten war das Programm weg (F10, nicht reproduzierbar). PDFs gut. |
| 11 | Datensicherung auf USB-Stick | ✓ | 1 (absichtlich) | ja (Kap. 10) | Funktioniert. Die Erfolgsmeldung ist leicht zu übersehen (F12). |
| 12 | Schließen, neu starten, alles da? | ✓ | 0 | nein | Alle Daten waren noch da. „Öffnen“ ist ausgegraut, bis man den Termin anklickt (gering). |

## 3. Stolpersteine

### F1: Keine Möglichkeit, Startnummern für viele Teilnehmer auf einmal zu vergeben
- Schwere: erheblich
- Wo: Reiter „Teilnehmer“, „Bearbeiten…“ / „Startnummer tauschen…“
- Was passiert ist: Nach CSV- und PDF-Import hatten 22 Teilnehmer keine Startnummer. Im Programm gibt es
  dafür keine Funktion. „Startnummer tauschen…“ bei Herrn Bauer zeigt „(aktuell: keine)“. Das Handbuch
  schreibt nur: „über ‚Bearbeiten…‘ die Startnummern … vergeben“. Pro Person waren 5 Schritte nötig:
  Zeile markieren, Bearbeiten, Haken „Startnummer steht noch nicht fest“ entfernen, Nummer eintippen, OK.
  Das ergibt rund 110 Klicks. Dazu kommt: Nach dem Entfernen des Hakens steht im Feld die „1“ (schon
  vergeben) statt der nächsten freien Nummer. Ergebnis: Meldung „Die Startnummer 1 ist bereits einem
  anderen Teilnehmer zugeteilt (aktuell: Muster, Maria)“. Ein Doppelklick auf eine Teilnehmerzeile öffnet
  den Bearbeiten-Dialog nicht. Bei Neumann (aus PDF-Import) kam zusätzlich die Rückfrage
  „Nur ein Gegenstand bei ED … Trotzdem speichern?“ mit den Knöpfen „Yes/No“.
- O-Ton Persona: „Muss ich das jetzt wirklich für jeden einzeln machen? Gibt's da keinen Knopf
  ‚durchnummerieren‘? Und warum schlägt er mir die 1 vor, die hat doch schon Maria?“
- Screenshot: shots/14_tausch_ohne_nr.png, shots/16_bearbeiten_ohne_nr.png, shots/17_nur_ein_gegenstand.png
- Vorschlag: Ein Knopf „Startnummern vergeben…“ (fehlende Nummern fortlaufend, optional sortiert nach
  Art/LK). Beim Entfernen des Hakens die kleinste freie Nummer vorschlagen. Doppelklick = Bearbeiten.

### F2: Teilnehmer-Dialog zu schmal, Eingabefelder links abgeschnitten
- Schwere: erheblich (mit Vorbehalt Testumgebung)
- Wo: „Teilnehmer hinzufügen…“ / „Bearbeiten…“
- Was passiert ist: Der Dialog öffnet mit 780×640. Die Felder Nachname, Vorname, Verein usw. sind nur
  etwa 45 px breit. Beim Tippen sieht man „uster“, „/Iaria“, „usen“. Die rechte Spalte ist abgeschnitten
  („Startnummer steht noch nic…“), unten gibt es eine waagerechte Scrollleiste, „Prüfungsgebühr bezahlt“
  und „Halter weicht ab“ liegen außerhalb des Sichtbereichs. Im Handbuch-Bild ist der Dialog ca. 1000 px
  breit und gut lesbar.
- O-Ton Persona: „Ich sehe gar nicht, ob ich ‚Muster‘ richtig geschrieben habe. Wo ist denn das
  Häkchen für bezahlt?“
- Screenshot: shots/08_tn_dialog.png, shots/09_maria_dk.png
- Vorschlag: Mindestbreite des Dialogs bzw. der linken Felder festlegen (etwa wie im Handbuch-Bild).

### F3: Zeitplan-Vorschlag setzt denselben DK-Hund gleichzeitig bei mehreren Richtern an
- Schwere: erheblich
- Wo: Reiter „Zeitplan“, „Automatisch verteilen…“, Zeitplan-PDF
- Was passiert ist: Maria Muster/Bello steht um 09:00–09:10 bei Anna Richter (Behältnis), Bernd Berger
  (Fläche) und Clara Christ (Trümmer) gleichzeitig. Das gilt auch für Otto, Pohl und Quandt
  (09:10–09:50). Thiel stand um 10:50 bei zwei Richtern. Es gibt keine Warnung. Julia hat es erst im PDF
  gemerkt.
- O-Ton Persona: „Moment, Maria kann doch nicht um neun an drei Stellen gleichzeitig sein? Muss ich das
  jetzt von Hand umsortieren? Wie denn?“
- Screenshot: shots/23_zeitplan_verteilt.png (und Zeitplan_2026-11-14.pdf)
- Vorschlag: DK-Blöcke beim Verteilen zeitlich versetzen, oder Überschneidungen pro Startnummer farbig
  markieren bzw. warnen. Falls das gleichzeitige Ansetzen fachlich gewollt ist (Rotation), braucht es
  eine kurze Erklärung im Handbuch.

### F4: CSV-Import übernimmt ohne Hinweis Teilnehmer für Prüfungen, die nicht angeboten werden
- Schwere: erheblich
- Wo: Reiter „Formular-Import“, „CSV importieren…“
- Was passiert ist: Angeboten sind nur DK LK 1/2, Trümmer LK 1/2, Fläche LK 1 und Behältnisse LK 1. Die
  Mitgliederliste enthielt ED LK 3, DK LK 3, Fläche LK 2 und Behältnisse LK 2. Ergebnis: „20 Teilnehmer
  importiert.“ Alle sind drin, auch im Zeitplan und auf den Bögen. Beim PDF-Import wurde dagegen
  „Trümmer LK 3 wird in diesem Termin nicht angeboten“ sauber abgelehnt.
- O-Ton Persona: „Hat geklappt, 20 Leute, prima.“ (Dass LK 3 gar nicht angeboten wird, fiel ihr erst
  bei den roten Einträgen in „Offene Starts“ im Zeitplan auf.)
- Screenshot: shots/11_csv_ergebnis.png, shots/12_teilnehmer_nach_csv.png
- Vorschlag: Nach dem Import auflisten, welche Zeilen eine nicht angebotene Prüfung haben (übernehmen
  oder nicht?), oder in der Spalte „Anmerkungen“ „⚠ Prüfung nicht ausgeschrieben“ anzeigen.

### F5: PDF-Import akzeptiert Formulare eines anderen Veranstalters/Termins
- Schwere: gering
- Wo: „Anmeldeformulare (PDF) importieren…“
- Was passiert ist: Alle vier PDFs sind Formulare von „DEMO Hundefreunde Musterstadt“ (Datum 03.10.2026
  bzw. 14.06.2026). Neumann und Otto wurden ohne Hinweis übernommen. Abgelehnt wurde nur, was nicht
  angeboten ist. Das Handbuch sagt „aus demselben Termin“, das prüft das Programm aber offenbar nicht.
  Die Meldungen zu Pfeiffer (zwei Prüfungen angekreuzt) und Quast (LK 3 nicht angeboten) waren dagegen
  sehr verständlich. Julia würde Herrn Pfeiffer anrufen und ihn dann von Hand anlegen. Herrn Quast würde
  sie absagen.
- O-Ton Persona: „Ah, Herr Pfeiffer hat zwei Kreuze gemacht. Klar, ruf ich an.“
- Screenshot: shots/13_pdf_import_ergebnis.png
- Vorschlag: Bei abweichendem Veranstalter oder Datum im Formular einen Hinweis in der Import-Übersicht
  anzeigen (nicht ablehnen).

### F6: Richter aus den Veranstaltungsdaten werden im Zeitplan nicht verwendet
- Schwere: gering
- Wo: Reiter „Zeitplan“, „Richter hinzufügen“
- Was passiert ist: Beim Anlegen hat Julia „Anna Richter, Bernd Berger, Clara Christ“ als Richter 1–3
  eingetragen. Im Zeitplan stand: „Noch keine Richter angelegt“. „Richter hinzufügen“ erzeugt
  „Richter 1“, danach war jeweils „Umbenennen…“ nötig: 3× zwei Dialoge.
- O-Ton Persona: „Die hab ich doch schon eingetippt! Warum heißt der jetzt ‚Richter 1‘?“
- Screenshot: shots/20_zeitplan_leer.png, shots/21_richter1.png
- Vorschlag: Richter aus den Veranstaltungsdaten als Spalten vorschlagen bzw. als Namen vorbelegen.

### F7: Gespeicherte PDFs landen im versteckten Termine-Ordner, nicht dort, wo man sie zum Mailen sucht
- Schwere: gering
- Wo: Reiter „Export“ (alle PDF-Knöpfe), Dateifenster
- Was passiert ist: Das Dateifenster schlägt `…\SHS-Pruefungsprogramm\Termine` vor. Julia klickt einfach
  „Speichern“ und weiß später beim Anhängen an eine E-Mail nicht, wo die Datei liegt. Der Pfad steht
  zwar unten in einer langen Statuszeile, die überlappt aber mit dem Erklärtext darüber (siehe
  Screenshot). Den „Ablageort öffnen“-Knopf hat sie erst später entdeckt. Auch beim Import öffnet das
  Dateifenster im Termine-Ordner statt in „Downloads“.
- O-Ton Persona: „Wo ist das Formular jetzt hin? Ich will das doch an alle mailen.“
- Screenshot: shots/07_nach_formular.png
- Vorschlag: Beim Anmeldeformular „Dokumente“ oder „Desktop“ vorschlagen, beim Import „Downloads“.
  Nach dem Speichern eine kleine Meldung „Gespeichert – Ordner öffnen?“ zeigen.

### F8: Technische Datenbank-Fehlermeldung bei zu hohem Punktwert
- Schwere: erheblich (Vertrauen am Prüfungstag)
- Wo: Reiter „Ergebniserfassung“, „Alle Ergebnisse speichern“
- Was passiert ist: Julia hat bei Conrad „Suche 70“ eingetragen. Das Feld zeigt keinen Fehler an. Beim
  Speichern kam: „Conrad, Carla – Behältnisstrecke: CHECK constraint failed: suche_behaeltnis BETWEEN 0
  AND 60“. Die zweite Meldung in derselben Box („Bitte Suche UND Anzeige eintragen …“) ist dagegen
  vorbildlich.
- O-Ton Persona: „CHECK constraint? Hab ich was kaputt gemacht? … Ach, 60 ist das Maximum.“
- Screenshot: shots/27_speichern_fehler.png
- Vorschlag: Klartext wie im Web („Suchleistung …: nur Werte von 0 bis 60 möglich“), möglichst schon
  beim Tippen das Feld rot markieren.

### F9: Pause wird am Ende angehängt statt nach der markierten Zeile, und muss je Richter einzeln angelegt werden
- Schwere: gering
- Wo: Reiter „Zeitplan“, „Pause hinzufügen…“
- Was passiert ist: Julia markiert den Block um 09:40 und klickt „Pause hinzufügen…“. Die Mittagspause
  landet als letzter Eintrag (11:10–11:55). Sie musste sie per „Hoch“ dreimal nach oben schieben. Für
  jeden Richter ist eine eigene Pause nötig. Außerdem sind die Zeitplan-Listen sehr klein (nur 2 Zeilen
  sichtbar, waagerecht gescrollt), was die Übersicht erschwert (Fensterhöhe 600 px in der
  Testumgebung).
- O-Ton Persona: „Warum ist die Pause jetzt ganz unten? Und für die anderen zwei nochmal?“
- Screenshot: shots/23_zeitplan_verteilt.png, shots/24_pause_dialog.png
- Vorschlag: Pause nach der markierten Zeile einfügen. Optional „Pause für alle Richter um HH:MM“.

### F10: Programm war beim Speichern der Etiketten plötzlich weg (nicht reproduzierbar)
- Schwere: erheblich, falls echt (vermutlich Testumgebung)
- Wo: Reiter „Export“, „Etiketten (PDF)…“, „Save“
- Was passiert ist: Direkt nach „Ergebnisliste“ und dann „Etiketten“ → „Save“ war das Programm
  beendet. Es gab keine Fehlermeldung, `programm_ausgabe.log` war leer, und eine Etiketten-Datei wurde
  nicht erzeugt. Nach dem Neustart waren alle Daten erhalten. Dieselbe Aktion lief danach fehlerfrei.
- O-Ton Persona: „Huch, wo ist das Programm hin? Sind meine Ergebnisse weg?“ (Sie waren noch da.)
- Screenshot: keiner möglich
- Vorschlag: In der Testumgebung gegenprüfen. Falls echt: Fehlerprotokoll und Absturzmeldung.

### F11: Englische Knöpfe „Yes/No“ und „Cancel“ in Programm-Dialogen
- Schwere: kosmetisch
- Wo: „Automatisch verteilen“, „Nur ein Gegenstand bei ED“, alle Eingabedialoge („Cancel“)
- O-Ton Persona: „Yes oder No – na gut, verstehe ich schon.“
- Screenshot: shots/22_auto_verteilen.png, shots/17_nur_ein_gegenstand.png
- Vorschlag: „Ja/Nein/Abbrechen“.

### F12: Kleinigkeiten in Texten und Meldungen
- Schwere: kosmetisch
- Datumsmeldung nennt zusätzlich „oder JJJJ-MM-TT“. Das verwirrt eher, als dass es hilft
  (shots/03_datum_falsch.png).
- „Noch ohne vollständiges Ergebnis: Iske, Ina, Jäger, Jan, Klein, Katrin …“: Durch die Kommas weiß man
  nicht, wo eine Person aufhört (Auswertung und Ergebnisliste-PDF).
- Im Ergebnisliste-PDF steht beim disqualifizierten Dorn in der Platz-Spalte „nB“. Am Bildschirm heißt
  es dagegen „Disqualifiziert“.
- Bei leeren Ergebniszeilen steht „✓ gespeichert“, was so wirkt, als sei schon etwas eingetragen.
  Die Spalte „Status“ wird zu „nicht …“ abgeschnitten.
- Bewertungsbogen-Auswahl: „(bisheriges Verhalten)“ ist Entwicklersprache.
- Datensicherung: Der Erfolg steht nur in der Statuszeile ganz unten (shots/33_sicherung_ok.png).
  „AES-256“ sagt Julia nichts.
- Hinweis „Bei ED ist nur ein Gegenstand vorgesehen“ bei einem frisch importierten Formular, obwohl das
  Handbuch „ältere Daten“ sagt.
- Termin anlegen ohne „Verband“: Das Anmeldeformular zeigt „Verband:“ leer, ohne Hinweis vorher.

## 4. Was gut lief

- Der Erststart ist sehr klar: ein Fenster, ein blauer Knopf „Neuen Termin anlegen…“, und der Speicherort
  wird automatisch vorgeschlagen und passt sich dem Datum an.
- Das Anmeldeformular-PDF ist sauber, zeigt nur die angebotenen Prüfungen und ist ausfüllbar.
- Die Ablehnungsgründe beim PDF-Import sind vorbildlich und konkret.
- „Startnummer tauschen…“ und „Keine Teilnahme“ sind genau das, was man braucht: Hofmann ist grau,
  kursiv und mit „keine Teilnahme“ markiert, verschwindet aus Zeitplan und Ergebniserfassung, und der Knopf
  wechselt zu „Teilnahme wiederherstellen“.
- Die Spalte „Anmerkungen“ zeigt gut, was noch fehlt (Chip, Gegenstand).
- Ergebniserfassung: Gelbe Zeilen mit „nicht gespeichert“, „–“ bei nicht relevanten Disziplinen,
  „Disqualifiziert“ sperrt die Felder, und fehlerhafte Zeilen werden einzeln gemeldet, während der Rest
  gespeichert wird.
- Die Rangliste ist sofort verständlich, nicht bestanden und disqualifiziert sind rot.
- PDFs (Zeitplan farbig je Block, Ergebnisliste, Etiketten, Bewertungsbögen mit vorausgefüllten Punkten)
  sehen professionell aus.
- Die Datensicherung mit Passwort-Wiederholung und klarer Fehlermeldung funktioniert, und die Eingaben
  bleiben stehen.
- Nach dem Neustart war alles erhalten.

## 5. Gesamturteil

- Schulnoten: Installation **2** (gut beschrieben, SmartScreen bekannt/akzeptiert) / Erststart **2** /
  Turnierablauf **3** / gesamt **3+**
- „Würde ich am Prüfungstag allein damit klarkommen?“ – **Eher ja.** Ergebnisse eintragen, Rangliste
  und Ausdrucke klappen gut. Die Vorbereitung (Startnummern, Zeitplan-Überschneidungen beim Dreikampf,
  Teilnehmer für nicht angebotene Prüfungen) hätte Julia ohne einen Anruf beim alten Prüfungsleiter
  aber nicht sicher hinbekommen. Am Prüfungstag selbst würde eine Meldung wie „CHECK constraint failed“
  sie verunsichern.
- Die 3 wichtigsten Wünsche:
  1. Startnummern auf einen Klick vergeben (und beim Bearbeiten die nächste freie vorschlagen).
  2. Ein Zeitplan-Vorschlag ohne gleichzeitige Starts desselben Hundes, oder zumindest eine Warnung.
  3. Klartext-Fehlermeldungen und ein Hinweis bei Teilnehmern für nicht angebotene Prüfungen (CSV-Import).

## 6. Grenzen dieses Tests

- Die Installation habe ich nur gedanklich durchgespielt (SmartScreen, Download-Seite nicht echt erlebt).
- Das Dateifenster war ein englischer Qt-Ersatz. Ob Julia im echten Explorer-Dialog leichter in
  „Downloads“ oder zum USB-Stick findet, ließ sich nicht prüfen. Den Ordner `USB-Stick` habe ich per
  Bash angelegt.
- „PDF öffnen“ und „Ablageort öffnen“ zeigen hier nichts. Die PDFs habe ich direkt angesehen.
- Fenstergrößen (Teilnehmer-Dialog 780×640, Hauptfenster 600 px hoch) können auf einem echten Bildschirm
  bzw. bei anderer Skalierung abweichen (F2, F9).
- Der Absturz F10 trat nur einmal auf, die Ursache (Programm oder Testumgebung) ist unklar.
- Die Web-Version war nicht Teil des Tests.
- Die Startnummern-Vergabe für 22 Personen lief per Schleife. Die Zahl der Klicks ist also gezählt, die
  Ermüdung eines echten Menschen nicht erlebt.
