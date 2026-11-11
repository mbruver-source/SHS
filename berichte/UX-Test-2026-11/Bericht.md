# UX-Test mit Personas – SHS-Prüfungsprogramm 1.0.55 (03.11.2026)

Zweiter vollständiger UX-Test nach dem vom 02.10.2026 ([UX-Test-2026-10/Bericht.md](../UX-Test-2026-10/Bericht.md), damals 1.0.39).
Seitdem kamen unter anderem die Demoprüfung, Stechen, Abbruch mit Grund, Startnummern-Bereiche und
das Erscheinungsbild „Beagle“ hinzu. Geprüft wurde wieder nicht, ob das Programm richtig rechnet,
sondern **wie es sich bedienen lässt**.

Alle Funde unten sind **Beobachtungen und Vorschläge, keine Umsetzungen**. Jeder Punkt wird einzeln
mit Marco besprochen.

## 1. Methode

Rahmen mit Marco am 03.11.2026 abgestimmt: alle sechs Personas wie im Oktober, nacheinander (Limit),
zusätzlich Demoprüfung, Stechen/Abbruch-Grund und Startnummern-Bereiche.

| Gruppe | A – mit Handbuch | B – ohne Handbuch |
|---|---|---|
| **Erfahren** | Heinz, 58, Prüfungsleiter seit über 10 Jahren | Sabine, 45, Meldestelle, Excel-Profi |
| **Normal** | Julia, 34, organisiert zum ersten Mal | Tobias, 41, Kassenwart, klickt Meldungen weg |
| **Laie** | Gerda, 71, hat das Handbuch ausgedruckt | Werner, 66, klickt herum, gerät leicht in Panik |

- **Bedienung:** Die echte Desktop-App 1.0.55 lief unsichtbar (Qt offscreen, 1920×1080) in einer
  abgeschotteten Sandbox je Persona: eigener Benutzerordner, eigene Einstellungen statt Registry,
  eigener TEMP-Ordner. Ein Steuerwerkzeug (nur im Scratchpad, nicht im Repo) übersetzte Befehle in
  echte Klicks und Tasteneingaben. Die Personas entschieden nur anhand von Bildschirmfotos,
  Beschriftungen und Meldungen; Quellcode und Projektnotizen waren tabu.
- **Installation** nur gedanklich (A: README/Handbuch Kap. 2, B: Website).
- **Szenario** (für alle gleich), 16 Aufgaben:
  - 0 Installation, 1 Erststart und **Demoprüfung bis zum Ende**, 2 Termin anlegen (14.11.2026,
    Hundefreunde Testhausen, 3 Richter; DK LK 1/2, Trümmer LK 1/2, Fläche LK 1, Behältnisse LK 1);
  - 3 Anmeldeformular, 4 zwei Nachmeldungen von Hand, 5 Mitgliederliste (CSV, 20 Meldungen, 8 davon
    für nicht angebotene Prüfungen), 6 vier Anmelde-PDFs (zwei fehlerhaft);
  - 7 **Startnummern-Bereiche**, Vergabe, Tausch, Absage; 8 späte Nachmeldung mit passender Nummer;
  - 9 Zeitplan ab 9:00 mit Mittagspause 12:00–12:45; 10 Ergebnisse nach Richterzettel mit
    Schreibfehler (65), Disqualifikation und **Abbruch mit Grund**; 11 Rangliste mit **Stechen**;
  - 12 PDFs, 13 Datensicherung, 14 Neustart, 15 freies Ausprobieren.
- **Ablauf:** Personas nacheinander. Nach dem ersten Lauf (Heinz) wurden Fehler des Steuerwerkzeugs
  behoben (Umlaute, Zeitplan-Reiter, Häkchen, Tabelleneingabe); Heinz hat Aufgabe 9 danach
  nachgeholt. Ab Julia schrieb das Werkzeug die Demo-Texte in Echtzeit mit (`verlauf`), weil die
  Personas langsamer „lesen“ als ein Mensch.
- **Grenzen:**
  - Das Dateiauswahl-Fenster ist ein englischer Qt-Ersatz statt des Windows-Explorer-Dialogs.
  - „PDF öffnen“/„Ordner zeigen“ öffnen nichts Sichtbares; PDFs wurden als Text geprüft.
  - Kein Mauszeiger: Tooltips von Tabellenzellen und Meldungen in der Statuszeile sah das Werkzeug
    nicht. Wo ein Fund daran liegen kann, steht das unten.
  - Bildschirm mit 96 dpi; die Windows-Skalierung (125 %/150 %) wurde nicht getestet.
  - Das Szenario hat nur 18 Starts. Der Plan endet deshalb um 10:40 – das prägt Fund X1.
- **Abschottung geprüft:** echte Termine unter `%USERPROFILE%\SHS-Pruefungsprogramm\Termine` und die
  Darstellungs-Einstellungen in der Registry unverändert; im Repo wurde während des Tests nichts
  geändert.
- **Ablage:** dieser Bericht, die sechs Einzelberichte in [personas/](personas/). Die Bildschirmfotos
  (Verweise „Bild EA/0457“) liegen nur lokal, weil viele den lokalen Benutzerpfad zeigen.

## 2. Ergebnis auf einen Blick

| | Installation | Erststart | Termin-Ablauf | **Gesamt** | Allein am Prüfungstag? | Gesamt Okt. 2026 |
|---|---|---|---|---|---|---|
| Heinz (E-A) | 2 | 2 | 2 | **2** | Eher ja | 3+ |
| Sabine (E-B) | 2 | 1–2 | 2 | **2** | Ja | 3+ |
| Julia (N-A) | 2 | 2 | 2 | **2** | Eher ja | 3+ (Nachtest 2) |
| Tobias (N-B) | 2 | 2 | 2 | **2** | Eher ja | 3 |
| Gerda (L-A) | 4 | 2 | 2– | **2–3** | Eher ja (mit Handbuch) | 4 |
| Werner (L-B) | 3 | 2 | 2– | **2–** | Eher ja | 3–4 (Nachtest 2–3) |

**Kurzfazit**

- Deutlich besser als im Oktober: **alle sechs** würden den Prüfungstag eher allein schaffen, auch
  die Laien. Im Oktober hieß es bei beiden Laien noch „Nein“. (Heinz sagte im Oktober „Ja“, jetzt
  „Eher ja“ – wegen der Mittagspause und der schmalen Abbruch-Spalte, bei besserer Note.)
- **Keine Aufgabe ist gescheitert** (kein ✗). Am häufigsten „mit Mühe“: Mittagspause (Aufgabe 9,
  alle sechs) und ED-Gegenstände (Aufgabe 4, fünf von sechs).
- **Startnummern, Importe, Stechen, PDFs, Sicherung** liefen bei allen ohne fremde Hilfe (die
  Abbruch-Zelle siehe X5) – die Hauptbaustellen vom Oktober (U1 Startnummern, U2 Doppelbelegung,
  U4 CSV-Prüfung) sind erledigt.
- Für Laien bleiben: **kleine Schrift** ohne Vergrößerung, die **Installation** (Browser- und
  SmartScreen-Warnungen) und die **zu schnell weiterschaltende Demo**.

**Aufgabe × Persona** (✓ geschafft · ~ mit Mühe · ✗ allein nicht geschafft)

| Nr | Aufgabe | E-A | E-B | N-A | N-B | L-A | L-B |
|---|---|---|---|---|---|---|---|
| 0 | Installation (gedanklich) | ✓ | ✓ | ✓ | ✓ | ~ | ~ |
| 1 | Erststart, Demoprüfung | ~ | ✓ | ✓ | ✓ | ✓ | ~ |
| 2 | Termin anlegen | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 3 | Anmeldeformular | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 4 | Nachmeldungen von Hand | ✓ | ~ | ~ | ~ | ~ | ~ |
| 5 | Mitgliederliste (CSV) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 6 | Anmelde-PDFs | ✓ | ✓ | ✓ | ✓ | ✓ | ~ |
| 7 | Startnummern, Tausch, Absage | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 8 | Späte Nachmeldung | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 9 | Zeitplan mit Pause | ~ | ~ | ~ | ~ | ~ | ~ |
| 10 | Ergebnisse, DQ, Abbruch | ~* | ✓ | ✓ | ✓ | ~ | ~ |
| 11 | Rangliste, Stechen | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 12 | PDFs | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 13 | Datensicherung | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 14 | Neustart, alles da? | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 15 | Freies Ausprobieren | ✓ | ✓ | ✓ | ✓ | ~ | ~ |

\* Heinz' „~“ bei 10 kam teils von der Tabelleneingabe des Steuerwerkzeugs im ersten Lauf
(inzwischen behoben), teils von der zu schmalen Abbruch-Spalte (X5).

**Mit oder ohne Handbuch?** Die B-Personas brauchten weder Handbuch noch Hilfe. Für Gerda war das
ausgedruckte Handbuch der Rettungsanker (Installation, Zeitplan). Werner hat von der **Demoprüfung**
am meisten gelernt: Danach wusste er, wo Export, Stechen und Abbruch zu finden sind.

## 3. Funde (zusammengeführt, nach Schwere)

„Betroffen“ zählt die Personas, die den Punkt selbst erlebt und gemeldet haben. Wo nötig, ist der Fund
mit dem Code und mit `OFFEN.md` abgeglichen.

### Erheblich (für Laien)

**X2 – Schrift lässt sich nicht vergrößern, die Hilfe verspricht es** · betroffen 2/6 (beide Laien), Schwere erheblich
- **Problem:** Die Hilfe sagt „**Schrift zu blass oder zu klein?** Menü ‚Ansicht‘ → ‚Hintergrund‘ →
  ‚Hoher Kontrast‘“ (`desktop_dialoge.py:1188`). Das ändert nur die Farben, nicht die Größe. Der Tipp
  auf der Startseite verweist auf das Menü „Ansicht“, das es im Startfenster nicht gibt (nur im
  Hauptfenster).
- **Code-Abgleich:** Es gibt keine Einstellung für die Schriftgröße (nur die automatische Anpassung
  an die Fenstergröße).
- **Einschränkung:** Die Windows-Skalierung (Anzeigeeinstellungen 125 %/150 %) wirkt im echten Windows
  auf das ganze Programm, wurde aber nicht getestet.
- **Vorgeschichte:** „Große Schrift“ war im Oktober (U14) als optional geplant und wurde nicht
  umgesetzt.
- **Vorschläge:** Text der Hilfe berichtigen und auf die Windows-Skalierung verweisen; optional
  „Ansicht → Schriftgröße“ (normal/groß/sehr groß); den Starttipp präzisieren: „im Hauptfenster
  (nach dem Öffnen eines Termins)“.

### Mittel

**X1 – Mittagspause „um 12:00 bei allen Richtern“ landet am Planende** · betroffen 6/6
- **Problem:** Mit „Pause hinzufügen…“ und „Bei allen Richtern einfügen, um 12:00“ endet der Plan
  schon um 10:40 (Clara 10:20). Die Pause wird ans Ende gehängt: 10:40–11:25 bzw. 10:20–11:05. Eine
  Meldung („Die Pause beginnt nicht überall um 12:00 …“) erscheint, die Pause wird trotzdem
  eingefügt, und im Aushang-PDF steht „10:40 – 11:25 Mittagspause“ als letzte Zeile. Tobias hat die
  Meldung weggeklickt, Gerda wusste nicht, ob sie die Pause löschen darf.
- **Dazu (Heinz):** „Automatisch verteilen…“ fragt nicht nach einer Pause; ein erneutes Verteilen
  entfernt eingefügte Pausen.
- **Einordnung:** Genau dieser Fall kam schon im Nachtest vor (**N3**, 03.10.). Marco hat sich damals
  für eine Meldung mit den Uhrzeiten statt einer Verhaltensänderung entschieden – die Vorschläge
  unten öffnen diese Entscheidung neu. Im Test entsteht der Fall auch durch das kleine Szenario
  (18 Starts); bei einer Prüfung, die über 12:00 hinausgeht, stünde die Pause richtig.
- **Vorschläge der Personas:** Endet der Plan vor der Pausenzeit, nachfragen („Der Plan endet schon
  um 10:40 – Pause trotzdem anhängen?“), die Pause weglassen, oder sie um 12:00 mit Lücke davor
  setzen (E-B).

**X3 – Hinweis „Gegenstand der Suchdisziplin nicht zugeordnet“ direkt nach dem PDF-Import** · betroffen 5/6
- **Problem:** Neumann (ED, Trümmer LK 1, aus dem Anmelde-PDF) zeigt sofort diesen Hinweis in
  „Anmerkungen“. Im Bearbeiten-Fenster steht alles richtig; nach einmal Öffnen und Speichern ist er
  weg. Das Handbuch erklärt den Hinweis nur für „ältere Daten“.
- **Code-Abgleich:** Der PDF-Import speichert die Gegenstände bewusst als „frei“
  (`db_import.py:732–734`, `gegenstand_N_disziplin = None`). Für ED meldet
  `db.teilnehmer_gegenstand_hinweis` (`db.py:1688`) das dann als nicht zugeordnet – obwohl es bei
  ED nur eine Disziplin gibt. Der Docstring in `db.py` (~1617) sagt selbst, „nicht zugeordnet“
  betreffe nur Altdaten. **Echter Kleinfehler** (bei den Demo-Daten wurde dasselbe Symptom am 04.10.
  so behoben).
- **Hinweis:** Die Speicherung „als frei“ ist Marcos Entscheidung vom 28.09. (`db_import.py:564–568`);
  sie zielte erkennbar auf DK. Ein Fix für ED berührt diese Entscheidung. Rest von **U11**: Das
  Handbuch (Kap. Teilnehmer, „ED (ältere Daten)“) wurde im Oktober nicht angepasst.
- **Vorschlag:** Beim PDF-Import einer ED-Meldung den Gegenstand gleich der ED-Disziplin zuordnen.

**X4 – ED: Gegenstand 2/3 gesperrt, ohne Erklärung** · betroffen 6/6
- **Problem:** Bei Weber (Trümmer LK 2, zwei Gegenstände gemeldet) sind die Felder 2 und 3 grau, aber
  kaum von offenen Feldern zu unterscheiden; ein Grund steht nicht da. Sabine, Tobias und Werner
  schrieben beide Gegenstände in Feld 1 – das wird kommentarlos angenommen. Julia fand die Erklärung
  erst im Handbuch. Heinz vermisst zusätzlich ein Notizfeld.
- **Vorschläge:** Kurzer Text oder Tooltip „Bei Einzeldisziplin nur ein Gegenstand“, gesperrte
  Felder deutlicher grau oder ausblenden.

**X5 – Spalte „Abbruch“: sieht nicht nach Auswahlliste aus, geht erst beim zweiten Klick auf** · betroffen 6/6 (zweiter Klick 5/6, Breite E-A)
- **Problem:** Die Zelle sieht leer aus, ohne Pfeil. Ein Klick markiert nur, erst der zweite Klick
  bzw. Doppelklick öffnet die Liste. Bei Heinz war die Spalte zu schmal: „Verletzun…“ – ob
  „Verletzung Hund“ oder „Verletzung HF“, war nicht zu sehen.
- **Code-Abgleich:** Bearbeitungsauslöser `SelectedClicked | DoubleClicked` (`app.py:1800–1803`),
  Auswahlliste über `_AbbruchDelegate` (`app.py:1504`). Echtes Programmverhalten, keine Testumgebung
  (wie N-B und L-B vermuteten). Das Handbuch (Kap. Ergebniserfassung) sagt, „Leertaste (oder ein
  Klick)“ klappe die Liste auf – widerspricht dem Code.
- **Vorschläge:** Pfeil bzw. „– bitte wählen –“ anzeigen, mit einem Klick öffnen; Spalte breit
  genug für den längsten Grund oder Tooltip mit dem vollen Text.

**X6 – Demoprüfung schaltet zu schnell weiter** · betroffen 4/6 (E-B nennt es „eher zu flott“, schreibt es aber dem Werkzeug zu)
- **Problem:** Jeder Schritt steht nach dem Fertigwerden 10 s; viele Erklärtexte haben 45–90 Wörter
  (Schritt 9 rund 90). Laut Echtzeit-Mitschnitt stehen die Schritte 2, 5, 9, 11, 12 (Stechen) und 13
  nur 10–11 s. Den Haken „Automatisch weiter“ übersieht Werner. Es gibt kein „Zurück“, Enter im
  Demo-Fenster bewirkt nichts.
- **Abgrenzung:** C16 (Countdown steht nach einer Meldung kurz weiter) ist ein anderer Punkt.
- **Vorschläge:** Countdown an die Textlänge koppeln (z. B. 4 s je 10 Wörter, mindestens 10 s), oder
  „Automatisch weiter“ standardmäßig aus; „Zurück“-Knopf; Enter = Weiter.

**X7 – Ungültiger Punktwert (65) beim Tippen nur rot umrandet** · betroffen 3/6 (E-B, N-B, L-B)
- **Problem:** Bei Tobias und Werner kam ein roter Rahmen ohne Text, Sabine bemerkte beim Tippen gar
  nichts; die klare Meldung „Suche höchstens 60 Punkte (eingegeben: 65)“ kommt erst beim Speichern.
- **Einordnung:** Am Feld steht ein Tooltip „Höchstens 60 Punkte.“ (`app.py:2657`, U5 03.10.), den das
  Steuerwerkzeug ohne Mauszeiger nicht zeigt – teilweise Testumgebung. C24 (Rahmen erst nach dem
  Übernehmen) ist akzeptiert; neu ist nur die fehlende sichtbare Erklärung.
- **Vorschlag:** Den Text zusätzlich in der Statuszeile oder unter der Tabelle zeigen.

**X8 – Komma in einer Punktzelle: aus „4,5“ wird 45** · betroffen 1/6 (E-B)
- **Problem:** Sabine überschrieb einen richtigen Wert (47) mit „4,5“; übrig blieb 45, ohne
  sichtbare Meldung.
- **Code-Abgleich:** Bei abgelehnten Zeichen erscheint ein oranger Hinweis über der Statuszeile
  („Nur ganze Punkte … keine Kommazahlen“, `app.py:2601–2614`, auch an der neuen Zelleneingabe).
  Die nächste getippte Ziffer blendet ihn aber sofort wieder aus (`textEdited` →
  `_eingabe_hinweis_ausblenden`, `app.py:1554`). Bei „4,5“ verschwindet er also mit der „5“ –
  Sabines Beobachtung ist sehr wahrscheinlich echt. Gegenprobe am echten Gerät.
- **Vorgeschichte:** Wiederholung von **N6** aus dem Nachtest (03.10.), gleiches Beispiel.

**X9 – „Startnummer tauschen“: Partner ist schon vorausgewählt** · betroffen 1/6 (N-B)
- **Problem:** Im Dialog steht der nächste Teilnehmer der Liste schon ausgewählt. Enter hätte Otto mit
  Pohl statt mit Quandt getauscht. (Sind genau zwei Teilnehmer markiert, wird seit N2 direkt
  getauscht; Tobias hatte nur einen markiert.)
- **Vorschlag:** Keinen Partner vorauswählen oder „OK“ erst nach einer Auswahl freigeben.

**X10 – Übersprungene Meldungen nach dem Import nicht mehr nachlesbar** · betroffen 2/6 (N-B, L-B)
- **Problem:** Die Liste der übersprungenen CSV-/PDF-Meldungen ist nach „OK“ weg (Werner: „muss ich
  mir abschreiben“). Für Pfeiffer (zwei Prüfungen angekreuzt) fehlt außerdem der Rat, was zu tun ist
  (N-A, L-A).
- **Vorschläge:** „Liste kopieren/speichern“ in der Meldung; beim Ablehnungsgrund einen Satz wie
  „Bitte beim Teilnehmer nachfragen und von Hand erfassen“.

**X11 – Startnummer außerhalb des Bereichs wird kommentarlos angenommen** · betroffen 1/6 (E-A)
- **Problem:** 150 für Trümmer LK 1 (Bereich 41–60) wird ohne Hinweis gespeichert; doppelte Nummern
  lehnt das Programm dagegen vorbildlich ab.
- **Vorschlag:** Hinweis (keine Sperre): „Liegt außerhalb des Bereichs 41–60 für Trümmer LK 1“.

**X12 – Prüfung im Teilnehmerformular aus drei Feldern zusammensetzen** · betroffen 1/6 (L-B)
- **Problem:** „Trümmer LK 2“ heißt im Formular Art ED + Leistungsklasse 2 + Disziplin Trümmerfeld;
  vorbelegt ist ED/1/Trümmerfeld, man meldet leicht unbemerkt falsch; angeboten werden auch
  Kombinationen, die der Termin nicht anbietet. Julia nennt zusätzlich die
  uneinheitlichen Namen („Trümmer LK 1“ im Termin, „ED LK 1 Trümmerfeld“ in Listen).
- **Vorschlag:** Eine Auswahlliste „Prüfung“ mit den angebotenen Prüfungen in derselben Schreibweise
  wie im Termin.

### Gering

- **X13 – Teilnehmerzahl:** Startbildschirm 17, Kopfbalken 16 (Pohl mit „Keine Teilnahme“ zählt nur
  im Startbildschirm) – 6/6. Die Terminliste zählt bewusst alle Gemeldeten (Fortschritt.md, ~Z. 2975);
  neu ist nur, dass der Kopfbalken anders zählt. Einheitlich zählen oder „16 (+1 abgemeldet)“.
- **X14 – Hilfe:** langer Fließtext ohne Suche und Gliederung (E-B, N-B, L-B). N-B meinte doppelte
  Abschnitte zu sehen – im Hilfetext gibt es keine (14 eindeutige Überschriften), vermutlich ein
  Effekt des Werkzeugs. Die Hilfe sagt, „Löschen…“ entferne einen Termin unwiderruflich, das Handbuch
  nennt den Papierkorb (N-A).
- **X15 – Kleinigkeiten:**
  - „14.11.26“ wird abgelehnt, obwohl die Dateinamen-Vorschau es schon erkannt hatte (E-B); die
    Meldung mit Beispiel ist seit U14 bewusst so gestaltet.
  - Die Hilfe spricht beim automatischen Verteilen von den „gewählten Richtern“, die Rückfrage von
    „ALLE“ (E-A, `desktop_dialoge.py:1265`).
  - Blaues „i“ in der Importmeldung, obwohl Dateien abgelehnt wurden; Hilfe „markierten
    Teilnehmers“ gegen Handbuch „alle markierten“ (E-A).
  - „1 Teilnehmer haben“ und die erneute Startnummern-Frage nach jedem Einzelimport (L-B).
  - Fachwort „GitHub-Releases-Seite“ (L-B).
  - „Fehlende Angaben“ nennt alle Pflichtfelder statt nur der fehlenden (N-A).
  - Seitenleiste „Offene Starts“ im Zeitplan zu schmal (N-A).
  - Der Name der Sicherungsdatei klingt nach einem Termin, enthält aber alle (E-A, N-B).
  - Enter im Versionsfenster öffnet „Lizenzen“ statt zu schließen (N-B).
  - „Richter hinzufügen“ legt sofort eine Spalte an; ein leerer Richter wird eine eigene Seite im
    Zeitplan-PDF (E-A; Löschen über „Richter löschen“ mit Rückfrage geht).
  - Tooltip „Dort zuerst …“ am Anmeldeformular-Knopf sagt nicht, wo „dort“ ist (L-A).
  - „Öffnen“ im Startbildschirm bleibt ausgegraut, obwohl nur ein Termin da ist (L-A, L-B).
  - Dass man mehrere PDFs auf einmal markieren kann, steht nirgends (L-B).
- **X16 – Installation für Laien:** Browserwarnung („Gefährliche Datei behalten“), SmartScreen,
  „Assets“ und „.exe“ auf der Release-Seite schrecken ab; Werner hätte den Update-Weg über
  „Version …“ allein nicht gefunden (L-A 4, L-B 3). Bekannt seit Oktober; die Code-Signatur ist
  zurückgestellt (B8).

## 4. Was gut lief

- **Importe:** CSV und PDFs nennen Zeile, Name und Grund verständlich; nicht angebotene Prüfungen
  werden übersprungen. Direkt danach die Frage „Jetzt fehlende Startnummern vergeben?“.
- **Startnummern-Bereiche automatisch festlegen:** ein Klick, danach saubere Nummern; die späte
  Nachmeldung bekam passend die nächste freie Nummer im richtigen Bereich (alle 6).
- **Enter-sicher:** Riskante Rückfragen (Löschen, Neu verteilen, Aktualisieren mit ungespeicherten
  Eingaben) stehen auf „Nein“ – Tobias' Enter-Reflex hat nichts kaputt gemacht.
- **Tauschen und Absage:** Strg-Klick auf zwei Teilnehmer + „Startnummer tauschen…“, „Keine
  Teilnahme“ mit einem Klick, die Person bleibt grau in der Liste.
- **Zeitplan-Vorschlag** ohne Überschneidungen, abgesagte Teilnehmer automatisch heraus.
- **Stechen:** Hinweis mit Namen unter der Tabelle, Dialog im Klartext, „(nach Stechen)“ in
  Auswertung und Ergebnisliste.
- **Abbruch mit Grund und Teilpunkten** in Auswertung und Ergebnisliste nachvollziehbar.
- **Doppelte Startnummer** wird abgelehnt; die Punkte-Meldung beim Speichern ist klar.
- **Excel-Gefühl** für Sabine: Strg-/Shift-Auswahl, Strg+A, Tab, Strg+S.
- **PDFs, Sicherung, Neustart** ohne Datenverlust und mit „Gespeichert unter: …“.
- **Erscheinungsbild:** Kopfbalken mit Beagle und Termin, Farben und Symbole überwiegend positiv
  bewertet; Gerda fand die beigen Felder kontrastarm.

## 5. Neue Funktionen im Urteil der Personas

| Funktion | Urteil |
|---|---|
| Demoprüfung | Für Laien der beste Einstieg (Werner, Gerda). Inhalt verständlich, Tempo zu hoch (X6). |
| Startnummern-Bereiche | Einhellig gelobt; Wünsche: Hinweis bei Nummer außerhalb des Bereichs (X11), keine Vorauswahl beim Tauschen (X9). |
| Stechen | Ohne Hilfe gefunden und richtig festgehalten (6/6). |
| Abbruch mit Grund | Fachlich klar; die Zelle ist schwer als Auswahlliste zu erkennen (X5). |
| Aussehen „Beagle“ | Positiv; Laien wünschen größere Schrift (X2). |
| Fehlermeldungen | Meist deutsch, konkret, mit Namen. Kritisiert: roter Rahmen ohne Text (X7), Pflichtfeld- und Pausen-Meldung (X15, X1), „Suchdisziplin nicht zugeordnet“ (X3), „i“-Symbol bei abgelehnten Dateien (X15). |

## 6. Abgleich mit dem Oktober-Test

Keiner der Oktober-Funde tritt in der damaligen Form wieder auf. Reste bzw. Wiederholungen:
- **U9/N3 → X1:** Pause am Planende, wenn der Plan früher endet (Nachtest-Entscheidung: Meldung).
- **U5/N6 → X8:** Komma in Punktzellen; dazu X7 (Erklärung erst beim Speichern).
- **U11 → X3:** Hinweis „nicht zugeordnet“ nach PDF-Import, Handbuch „ältere Daten“.
- **U14 → X2:** Fachwörter kaum noch ein Thema; geblieben ist die Schriftgröße („große Schrift“ war
  im Oktober als optional geplant und wurde nicht umgesetzt).

## 7. Steuerwerkzeug (für künftige Tests)

Nur im Scratchpad dieser Sitzung (`ux_server.py`, `ux.py`), nicht im Repo. Lehren daraus:
- QTest-Tasteneingaben brechen bei Umlauten mit einem ASSERT ab – Umlaute als echte KeyEvents senden.
- Python-Hüllen der Kind-Elemente eines Qt-Dateidialogs werden ungültig, sobald die Hülle des Dialogs
  verschwindet – Fenster-Hüllen festhalten.
- Ein QTimer wird nicht erneut ausgelöst, solange sein Slot in einer Modal-Schleife hängt – den
  Abfragetakt als Kette von `singleShot` bauen.
- Demo-Texte in Echtzeit mitschreiben; Statuszeile und Zell-Tooltips sind noch nicht erfasst.
