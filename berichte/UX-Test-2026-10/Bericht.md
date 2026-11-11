# UX-Test mit Personas – SHS-Prüfungsprogramm 1.0.39 (02.10.2026)

Geprüft wurde nicht, ob das Programm richtig rechnet, sondern **wie es sich benutzen lässt**: von der Installation über die erste Inbetriebnahme bis zu einem kompletten Prüfungstermin. Getestet haben sechs KI-Test-Personas in drei Erfahrungsstufen, je eine mit und eine ohne Handbuch.

Alle Funde unten sind **Beobachtungen und Vorschläge, keine Umsetzungen**. Jeder Punkt wird einzeln mit Marco besprochen.

## 1. Methode

| Gruppe | A – mit Handbuch | B – ohne Handbuch |
|---|---|---|
| **Erfahren** | Heinz, 58, Prüfungsleiter seit über 10 Jahren (OMA, Excel) | Sabine, 45, Meldestelle, Excel-Profi, liest keine Anleitungen |
| **Normal** | Julia, 34, Hundeführerin, organisiert zum ersten Mal | Tobias, 41, Kassenwart, klickt Meldungen schnell weg |
| **Laie** | Gerda, 71, selten am PC, hat das Handbuch ausgedruckt | Werner, 66, Rentner, klickt herum, gerät leicht in Panik |

### So wurde getestet

- **Installation:** nur gedanklich nachvollzogen. Persona A ging über README und Handbuch Kap. 2, Persona B über die Website (`docs/index.html`) und die GitHub-Release-Seite.
- **Erststart und Termin:** Die echte Desktop-App (Stand 1.0.39) wurde bedient. Sie lief unsichtbar in einer abgeschotteten Testumgebung mit eigenem Benutzerordner je Persona.
  - Ein kleines Steuerwerkzeug übersetzte Befehle in Klicks und Tastatureingaben.
  - Die Personas entschieden nur anhand von Screenshots, Beschriftungen und Meldungstexten. Quellcode war tabu.
- **Szenario (für alle gleich):**
  - Prüfung am 14.11.2026 für „Hundefreunde Testhausen“, 3 Richter, angeboten DK LK 1/2, Trümmer LK 1/2, Fläche LK 1, Behältnisse LK 1.
  - Aufgaben in dieser Reihenfolge:
    1. Termin anlegen
    2. Anmeldeformular erzeugen
    3. 2 Nachmeldungen von Hand
    4. Mitgliederliste (CSV, 20 Teilnehmer) übernehmen
    5. 4 Anmelde-PDFs einlesen, davon 2 absichtlich fehlerhaft
    6. Startnummern tauschen und eine Absage als „Keine Teilnahme“ erfassen
    7. Zeitplan ab 9:00 mit Mittagspause
    8. Ergebnisse eintragen, eine Disqualifikation
    9. Rangliste ansehen
    10. PDFs erzeugen (Ergebnisliste, Bewertungsbögen, Etiketten)
    11. Datensicherung anlegen
    12. Neustart
- **Grenzen:**
  - Bedient wurde per Skript statt mit der Maus.
  - Das Dateiauswahl-Fenster war ein englischer Qt-Ersatz statt des Windows-Explorer-Dialogs.
  - „PDF/Ordner öffnen“ war nicht sichtbar.
  - Virtueller Bildschirm 1920×1080.
  - Wo eine Beobachtung an der Testumgebung liegen könnte, ist das unten vermerkt.
- **Abschottung geprüft:** Echte Termine in `%USERPROFILE%\SHS-Pruefungsprogramm\Termine` und die Darstellungs-Einstellungen in der Registry blieben unverändert. Im Repo wurde während des Tests nichts geändert.

## 2. Ergebnis auf einen Blick

| | Installation | Erststart | Termin-Ablauf | **Gesamt** | Allein am Prüfungstag? |
|---|---|---|---|---|---|
| Heinz (E-A) | 2 | 2 | 3 | **3+** | Ja – Vorbereitung mühsam |
| Sabine (E-B) | 2 | 2 | 3 | **3+** | Ja, mit Einschränkung |
| Julia (N-A) | 2 | 2 | 3 | **3+** | Eher ja |
| Tobias (N-B) | 2- | 2 | 3- | **3** | Eher ja, mit Einschränkung |
| Gerda (L-A) | 3–4 | 3 | 4 | **4** | Nein |
| Werner (L-B) | 3 | 2 | 4 | **3–4** | Nein |

**Kurzfazit je Gruppe**

- **Erfahrene** kommen gut durch und loben vieles:
  - Termin anlegen, PDF-Import mit klaren Ablehnungsgründen, „Keine Teilnahme“, Startnummern-Tausch, Ergebniserfassung, alle PDFs.
  - Sie ärgern sich über Fleißarbeit (Startnummern einzeln) und darüber, dass der automatische Zeitplan nicht aushängbar ist.
- **Normale Nutzer** schaffen den Prüfungstag selbst. Bei der Vorbereitung (Startnummern, Zeitplan, nicht angebotene Prüfungen aus der CSV) machen sie ohne Hilfe Fehler oder brauchen sehr lange. Der Doppelbelegungs-Fehler im Zeitplan wäre Tobias erst am Prüfungstag aufgefallen.
- **Laien** schaffen die Ergebniseingabe nach einer Einweisung, die Vorbereitung nicht. Am meisten verunsichern sie:
  - englische Knöpfe;
  - die technische Datenbankmeldung;
  - fehlende Rückmeldung nach dem Speichern („Wo ist das jetzt hin?“);
  - die zu schmale Teilnehmer-Maske;
  - Fachwörter (CSV, ZIP, AES-256, Prompt).

**Aufgabe × Persona** (✓ geschafft · ~ mit Mühe · ✗ allein nicht geschafft)

| Nr | Aufgabe | E-A | E-B | N-A | N-B | L-A | L-B |
|---|---|---|---|---|---|---|---|
| 0 | Installation (gedanklich) | ✓ | ✓ | ✓ | ~ | ~ | ~ |
| 1 | Erststart, Termin anlegen | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 2 | Anmeldeformular | ✓ | ✓ | ✓ | ✓ | ~ | ✓ |
| 3 | Nachmeldungen von Hand | ~ | ✓ | ~ | ~ | ~ | ~ |
| 4 | Mitgliederliste (CSV) | ✓ | ✓ | ✓ | ✓ | **✗** | ~ |
| 5 | Anmelde-PDFs einlesen | ✓ | ~ | ✓ | ~ | ~ | ✓ |
| 6 | Startnummern, Tausch, Absage | ~ | ~ | ~ | ~ | ~ | **✗** |
| 7 | Zeitplan mit Pause | ~ | ~ | ~ | ~ | ~ | ~ |
| 8 | Ergebnisse, Disqualifikation | ✓ | ✓ | ✓ | ✓ | ~ | ~ |
| 9 | Rangliste | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 10 | PDFs | ✓ | ✓ | ✓ | ✓ | ~ | ✓ |
| 11 | Datensicherung | ✓ | ✓ | ✓ | ✓ | ~ | ✓ |
| 12 | Neustart, alles da? | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

**Mit oder ohne Handbuch?** Die Oberfläche ist weitgehend selbsterklärend. Alle drei B-Personas (ohne Handbuch) brauchten Hilfe und Handbuch **nur bei einer einzigen Frage**: Wie bekommen importierte Teilnehmer Startnummern? Dafür schlugen sie erst in der Programm-Hilfe und dann im Handbuch nach.
- Die Hilfe im Programm beantwortet das nicht.
- Das Handbuch sagt nur „einzeln über Bearbeiten…“.

Das Handbuch hat den A-Personas bei den Hauptproblemen also nicht geholfen. Bei Gerda hätte es sogar zu einem Fehler verleitet (siehe U13).

## 3. Funde (zusammengeführt, nach Schwere)

„Betroffen“ zählt die Personas, die den Punkt selbst erlebt und gemeldet haben. Ein Punkt, den alle sechs melden, wiegt schwerer als einer, der nur Laien trifft. Der Code-Abgleich wurde nachträglich gemacht, um Testumgebungs-Artefakte auszuschließen.

### Erheblich

**U1 – Startnummern lassen sich nur einzeln vergeben** · betroffen 6/6 · Bild 02
- **Problem:**
  - Nach CSV- und PDF-Import hatten 22 Teilnehmer keine Startnummer. Je Person waren 5 Schritte nötig (markieren, „Bearbeiten…“, Haken „steht noch nicht fest“ entfernen, Nummer tippen, OK), insgesamt etwa 90–110 Klicks.
  - Nach dem Entfernen des Hakens schlägt das Feld **„1“** vor, obwohl die 1 schon vergeben ist. Dann folgt eine (gute) Fehlermeldung.
  - Ein **Doppelklick** auf eine Teilnehmerzeile öffnet nichts. Code-Abgleich: Nur der Startdialog hat einen Doppelklick-Handler.
  - „Startnummer tauschen…“ zwischen zwei Teilnehmern ohne Nummer schließt ohne Meldung und ohne Wirkung (L-B).
- **Vorschläge der Personas:**
  - Knopf „Fehlende Startnummern vergeben…“, fortlaufend, optional nach Art/LK.
  - Nach dem Import fragen: „Jetzt vergeben?“
  - Nächste freie Nummer vorschlagen.
  - Doppelklick = Bearbeiten.

**U2 – „Automatisch verteilen“ setzt DK-Teams gleichzeitig bei mehreren Richtern an** · betroffen 6/6 · Bild 04
- **Problem:**
  - Beispiel: Muster/Bello steht 09:00–09:10 parallel bei Anna Richter (Behältnis), Bernd Berger (Fläche) und Clara Christ (Trümmer). Das gilt für alle DK-LK-1-Teams, teils auch für DK LK 2/3.
  - Es gibt keine Warnung. Die Seitenleiste „Offene Starts“ ist komplett grün, das PDF übernimmt den Plan unverändert.
  - Laien hätten den Plan so verschickt („Sieht ordentlich aus, schön bunt“).
  - Code-Abgleich: `db.automatische_zeitplan_verteilung` (db.py:1734) verteilt Blöcke je Art/LK/Disziplin rein nach Auslastung. Die drei DK-Disziplinen derselben Teams beginnen dadurch gleichzeitig.
- **Hintergrund:** Laut Fortschritt.md (14.09.) durchläuft ein DK-Hund die drei Disziplinen nacheinander. Gleichzeitige Starts sind fachlich also nicht gemeint. Der automatische Plan ist ausdrücklich „nur ein Vorschlag, frei änderbar“. Der Fund bleibt trotzdem: Der Vorschlag ist so nicht verwendbar, und es gibt keine Warnung.
- **Vorschlag:** DK-Disziplinen eines Teams zeitlich versetzen, oder Überschneidungen je Startnummer rot markieren.

**U3 – Teilnehmer-Maske öffnet zu schmal, Eingaben sind abgeschnitten** · betroffen 6/6 · Bild 01, 02
- **Problem:**
  - Der Dialog startet mit **780×640**, festgelegt in `desktop_dialoge.py:300`.
  - Die linke Spalte (Name, Vorname, Verein, Anschrift) hat nur etwa 45 px breite Felder. Man sieht „uster“ statt „Muster“.
  - Rechts ist „Startnummer steht noch nic…“ abgeschnitten, unten erscheint ein waagerechter Rollbalken. „Prüfungsgebühr bezahlt“ und „Halter weicht ab“ sind halb verdeckt.
  - Der Handbuch-Screenshot zeigt den Dialog deutlich breiter (ca. 1000 px), dort sieht er gut aus.
  - Der Dialog ist maximierbar und hat eine Scrollfläche (`desktop_dialoge.py:284/299`). Wer ihn vergrößert, sieht alles. Keine Persona kam aber darauf, und die Erfassung beginnt mit abgeschnittenem Text.
- **Bekannt, Wiederauftreten:** Genau dieses Symptom („Bruver“ erschien als „uver“) wurde am 21.09. schon gemeldet. Behoben wurde es mit einer 50/50-Aufteilung, Scrollfläche und Maximieren-Knopf (Fortschritt.md ~Zeile 300). In der Testumgebung tritt es bei der Startgröße 780×640 trotzdem wieder auf. Gegenprobe in der echten App empfohlen.
- **Vorschlag:** Größere Startgröße oder Mindestbreite der Felder.

**U4 – CSV-/OMA-Import prüft die angebotenen Prüfungen nicht, der PDF-Import schon** · betroffen 6/6 · Bild 06
- **Problem:**
  - Die CSV brachte ED LK 3, DK LK 3, Fläche/Behältnisse LK 2 ohne jeden Hinweis in den Termin („20 Teilnehmer importiert.“).
  - Diese Teilnehmer landen in Zeitplan, Bewertungsbögen und Etiketten.
  - Der PDF-Import lehnt genau das mit guter Begründung ab. Das ist uneinheitlich.
- **Vorschlag:** Gleiche Prüfung wie beim PDF-Import, mindestens als Warnung oder Rückfrage. Dazu „⚠ Prüfung nicht angeboten“ in der Spalte „Anmerkungen“.

**U5 – Technische Datenbankmeldung bei Punkten außerhalb des Bereichs** · betroffen 6/6 · Bild 08
- **Problem:**
  - „65“ im Feld „Suche (0-60)“ lässt sich eintippen. Code-Abgleich: Der `QIntValidator(0, 60)` lässt zweistellige Zwischenwerte zu.
  - Beim Speichern erscheint dann „CHECK constraint failed: suche_truemmerfeld BETWEEN 0 AND 60“.
  - Laien denken, sie hätten etwas kaputt gemacht („Tschek konstreint?“).
  - „45,5“ wird ohne Hinweis zu 45 (E-B).
  - Positiv: Die übrigen Zeilen werden gespeichert, die fehlerhafte bleibt gelb.
- **Vorschlag:** Klartext wie in der Web-Version („Suche Trümmerfeld: nur 0 bis 60 Punkte möglich“), das Feld schon beim Verlassen rot markieren.

**U6 – Englische Standardknöpfe „Yes/No/Cancel“ in Programm-Dialogen** · betroffen 6/6 · Bild 09
- **Problem:**
  - Betroffen sind alle Rückfragen (z. B. „Automatisch verteilen“, „Nur ein Gegenstand bei ED“, „Jetzt speichern?“) und alle Eingabedialoge („Cancel“).
  - Code-Abgleich: Es wird keine deutsche Qt-Übersetzung (`QTranslator`/`qtbase_de`) geladen.
  - **Bekannt:** Seit dem 22./23.09. steht das als offener Punkt in Fortschritt.md („OK/Cancel-Buttons der Dialoge sind englisch“). Der Test zeigt, wie stark das Laien trifft.
  - Für Laien ist das gerade bei Warnungen („gehen dabei verloren“) ein echtes Hindernis („Ich trau mich nicht“).
- **Vorschlag:** Qt-Übersetzung laden, damit „Ja/Nein/Abbrechen“ erscheint.

**U7 – Nach dem Speichern von PDFs fehlt eine sichtbare Rückmeldung, der Speicherort ist schwer zu finden** · betroffen 6/6
- **Problem:**
  - Nach „Speichern“ erscheint nur eine kleine Statuszeile mit langem Pfad. Im Reiter „Export“ überlappt sie sogar den Erklärtext.
  - Direkt nach dem Speichern gibt es kein „PDF öffnen / Ordner öffnen“-Angebot. Im Reiter „Export“ gibt es zwar den Knopf „Ablageort öffnen“, den fanden die meisten Personas aber nicht oder erst später.
  - Vorgeschlagen wird immer der Termine-Datenordner. Beim CSV-Import startet das Dateifenster ebenfalls dort statt in „Downloads“.
  - O-Ton: „Wo ist das Formular jetzt hin? Ich will das doch an alle mailen.“
  - Die Datensicherung meldet den Erfolg ebenfalls nur als Statuszeile mit Pfad. Erfahrene fanden das ausreichend, Laien übersahen es.
- **Vorschlag:**
  - Meldung „Gespeichert unter … [Öffnen] [Ordner zeigen]“.
  - Für Ausgaben „Dokumente“ oder einen Unterordner „Ausdrucke“ vorschlagen, für Importe „Downloads“ bzw. den zuletzt genutzten Ordner.

### Gering

**U8 – Richter aus den Veranstaltungsdaten werden im Zeitplan nicht übernommen** · betroffen 6/6 · Bild 05
- **Problem:** Trotz eingetragener Richter 1–3 meldet der Zeitplan „Noch keine Richter angelegt“. „Richter hinzufügen“ erzeugt „Richter 1“, danach muss man dreimal umbenennen.
- **Vorschlag:** Spalten aus den Veranstaltungsdaten vorbelegen.

**U9 – Bedienung des Zeitplans** · betroffen 6/6
- **Problem:**
  - „Pause hinzufügen…“ hängt die Pause immer ans Ende, auch wenn eine Zeile markiert ist.
  - „Hoch/Runter“ springt blockweise, obwohl die Liste Einzelzeilen zeigt (einmal stand die Mittagspause um 09:00).
  - Die Pause muss für jeden Richter einzeln angelegt werden. **Bewusste Entscheidung:** Laut Fortschritt.md (14.09.) werden Pausen absichtlich unabhängig je Richter geplant. Der Wunsch „für alle Richter“ würde diese Entscheidung neu öffnen.
  - Vor „Automatisch verteilen“ warnt das Programm „…gehen dabei verloren“, auch wenn noch gar kein Plan existiert.
  - Die Listen zeigen nur 2–4 Zeilen.
- **Vorschlag:**
  - Pause nach der markierten Zeile oder „ab Uhrzeit“ einfügen.
  - Optional, siehe bewusste Entscheidung oben: „für alle Richter“.
  - Warnung nur zeigen, wenn schon ein Plan existiert.

**U10 – Mitgliederliste (Excel/CSV) ist für Laien nicht auffindbar** · betroffen 3/6 (L-A blockierend, N-B, N-A über das Handbuch) · Bild 07
- **Problem:**
  - Das Wort „Mitgliederliste/Excel“ kommt weder im Programm noch im Handbuch vor.
  - „CSV importieren…“ ist im Handbuch nur beim KI-Weg beschrieben.
  - Der Reiter „Formular-Import“ wird optisch vom KI-Prompt dominiert.
  - Zwei Personas versuchten zuerst „Aus anderem Termin importieren…“.
- **Vorschlag:** Eigener Abschnitt bzw. Knopf „Teilnehmerliste aus Excel/Tabelle übernehmen“, Prompt-Text einklappen.

**U11 – PDF-Anmeldung ED LK 2 mit zwei Gegenständen** · betroffen 5/6 (E-B nennt die Rückfrage nur als Beispiel)
- **Problem:**
  - Das Formular bietet für LK 2 zwei Gegenstandsfelder, auch für ED.
  - Beim nächsten „Bearbeiten“ (z. B. nur Startnummer setzen) kommt deshalb die Rückfrage „Nur ein Gegenstand bei ED … Trotzdem speichern? Yes/No“. „Yes“ verwirft den zweiten Gegenstand kommentarlos.
  - Das Handbuch erklärt den Hinweis als Folge „älterer Daten“.
  - Außerdem: Formulare eines anderen Veranstalters oder Datums werden übernommen, solange die Prüfung angeboten wird (3/6). **Bereits entschieden:** Das war Befund 1 der Verifikation zu 1.0.38. Marco hat am 28.09. als Abhilfe die Prüfung „angeboten?“ gewählt (Fortschritt.md ~Zeile 2781). Hier nur zur Information.

**U12 – Fenstergrößen** · betroffen 6/6
- **Problem:**
  - Das Hauptfenster startet laut Code mit 900×600 (`app.py`, `resize(900, 600)`). Der Inhalt verbreitert es sofort auf etwa 1200 px, je nach Reiter bis auf 1957 px, also breiter als ein 1920er-Bildschirm.
  - Die Höhe bleibt bei 600, im Zeitplan bleibt deshalb kaum Platz für die Listen.
- **Vorbehalt:** Bei maximiertem Fenster ist das teils entschärft.
- **Vorschlag:** Startgröße an den Bildschirm koppeln oder maximiert starten, lange Hinweistexte umbrechen.

**U13 – Handbuch: Widerspruch und Lücken** · Lücken melden alle 3 A-Personas, den Widerspruch E-A und L-A
- Kap. 6 (Zeitplan, `docs/HANDBUCH.md:343-344`) rät: „Fällt ein Teilnehmer aus, einfach im Reiter ‚Teilnehmer‘ löschen“. Das widerspricht der neuen Funktion „Keine Teilnahme“ (Kap. 4) und hätte Gerda zum Löschen verleitet.
- Die Startnummern-Vergabe für importierte Teilnehmer steht nur im Abschnitt „Ausprobieren mit Beispieldaten“.
- Der CSV-Import einer Mitgliederliste fehlt (siehe U10).
- README (Zeile 29: „Version → Nach Updates suchen“) und Handbuch („ℹ️ Version …“-Knopf) beschreiben den Update-Weg leicht unterschiedlich.
- Fachwörter (CSV, UTF-8, Stammdaten, AES-256, `*.sqlite`) bremsen Laien.
- Vorschlag der Laien-Persona: ein Kapitel „Erste Prüfung Schritt für Schritt“.

**U14 – Verständlichkeit für Laien** · betroffen L-A, L-B, teils N
- **Problem:**
  - Reiternamen und Spaltenköpfe sind hellgrau und klein (schwacher Kontrast). Ein Design „Hoher Kontrast“ gibt es bereits unter „Ansicht“, keine Laien-Persona hat es aber gefunden. Es ist also ein Auffindbarkeitsproblem, keine fehlende Funktion.
  - Unerklärte Begriffe: „ZIP“, „AES-256“, „Prompt“, „OMA-Export“, „SH-R“.
  - Die Datumsmeldung nennt „TT.MM.JJJJ oder JJJJ-MM-TT“ ohne Beispiel.
  - Fast jede Teilnehmerzeile zeigt in Orange „⚠ Gegenstand fehlt“. Das beunruhigt („Überall Warnungen, das sieht aus, als wär alles falsch“), obwohl es bis zum Prüfungstag nachgetragen werden kann.
- **Vorschlag:**
  - „Hoher Kontrast“ und ggf. „Große Schrift“ leichter auffindbar machen.
  - Alltagssprache verwenden.
  - Hinweis als Tooltip „kann bis zum Prüfungstag nachgetragen werden“.

### Kosmetisch / Kleinigkeiten

Gesammelt aus mehreren Berichten. Wo viele Personas betroffen sind, steht die Zahl dabei:
- **Ergebniserfassung (6/6):** Leere Zeilen zeigen „✓ gespeichert“. Die Statusspalte ist abgeschnitten („● nicht …“), und Zahlen in den Zellen sind unten angeschnitten (L-A).
- **Namenslisten (5/6)** „Graf, Greta, Iske, Ina, …“: Das Komma ist doppelt belegt, man erkennt nicht, wo ein Name endet.
- **Ergebnisliste-PDF:** Beim Disqualifizierten steht in der Spalte Platz „nB“ statt „Disq.“. Eine Überschrift steht allein am Seitenende.
- **Bewertungsbögen-Auswahl (6/6):** „(bisheriges Verhalten)“ ist Entwicklersprache.
- **Etiketten:** „Pfeiffer, Paul, , Pepper“ bei leerem Verein. Beim nB-Teilnehmer steht „Gesamt: 65“ ohne Kennzeichnung.
- **Termin anlegen (5/6):** Bleiben Verband/Meldestelle leer, fehlen sie ohne Hinweis im Anmeldeformular. Der Ort erscheint nicht auf dem Formular (N-B).
- **Teilnehmerliste:**
  - Eine Mehrfachmarkierung graut alle Knöpfe aus, auch „Bezahlt umschalten“.
  - Nach dem Speichern springt die Markierung auf einen anderen Teilnehmer, weil die Liste neu sortiert wird (E-B, N-B).
  - Ein Teilnehmer mit „Keine Teilnahme“ zeigt weiter „⚠ Gegenstand fehlt“ (E-A, sichtbar in Bild 11).
- **PDF-Import, Ablehnungsgrund „nicht angeboten“:** Der Hinweis auf „Reiter Verwaltung“ verleitet Laien dazu, die Prüfung einfach freizuschalten (L-A).
- **Rangliste:** „von 2“, obwohl 5 gemeldet sind. Gezählt werden nur gewertete Teilnehmer (N-B).
- **Datensicherung:** Der Dateiname nimmt das Tagesdatum statt des Prüfungsdatums.
- **Strg+S** speichert in der Ergebniserfassung nicht (E-B, unter Vorbehalt der Testumgebung).
- **GitHub-Release-Seite:** Es gibt keine Release-Notes („Was ist neu?“). „Assets“ ist englisch und standardmäßig zugeklappt.

## 4. Nicht eindeutig – Gegenprobe empfohlen

**P1 – Stille Programmenden direkt nach einer Dateiauswahl** (5 von 6 Personas, je 1–2-mal)
- **Was passierte:**
  - Das Programm beendete sich jeweils ohne Meldung, mit leerem Protokoll.
  - Auslöser waren der PDF-Import mit 4 Dateien auf einmal oder „Etiketten (PDF)…“ kurz nach einem anderen Export.
  - Es ließ sich nicht reproduzieren, die gespeicherten Daten blieben erhalten.
  - Ungespeicherte Ergebniseingaben gingen in einem Fall verloren (E-A).
- **Befund** (nachträglich von der Testleitung erhoben, nicht aus den Persona-Berichten):
  - Das Windows-Ereignisprotokoll (Anwendung, Ereignis 1000, 02.10.2026 21:17) zeigt einen Heap-Fehler (`0xc0000374`, ntdll.dll) im Python-Prozess der Testumgebung.
  - Ein Isolationstest nur des Ersatz-Dateifensters (Skript im temporären Testordner, 3 × 40 Durchläufe mit Ordnerwechsel und Mehrfachauswahl) lief ohne Absturz.
  - Die Ursache ist also offen: Zusammenspiel von Steuerwerkzeug und Qt ist wahrscheinlich, ein Programmfehler ist aber nicht ausgeschlossen.
- **Empfehlung:** Einmal in der echten installierten App mit dem Windows-Dateidialog gegenprüfen: 4 Anmelde-PDFs auf einmal importieren, dann direkt nacheinander Ergebnisliste und Etiketten speichern.

**P2 – „Ungespeicherte Ergebnisse – Jetzt speichern?“ erschien nach „No“ erneut** (nur E-A, einmal)
- Möglicherweise ein Artefakt der Testumgebung. Mit echtem Mausklick gegenprüfen.

## 5. Was gut lief (von fast allen genannt)

- **Startbildschirm und „Neuen Termin anlegen“:** klar, mit blauem Hauptknopf. Der Dateiname wird automatisch vorgeschlagen. Datumsfehler werden ohne Datenverlust gemeldet.
- **Anmeldeformular-PDF:** professionell, ausfüllbar, nur mit den angebotenen Prüfungen.
- **PDF-Import (Bild 10):** vorbildliche Ablehnungsgründe („mehrere Prüfungen angekreuzt“, „wird in diesem Termin nicht angeboten – Formular eines anderen Termins?“). Duplikate werden erkannt.
- **„Keine Teilnahme“ (Bild 11) und „Startnummer tauschen…“:** je ein Klick, eindeutig, sauber in Zeitplan, Ergebniserfassung und Etiketten berücksichtigt.
- **Meldung „Startnummer bereits vergeben“:** nennt den Inhaber und die Lösungswege.
- **Spalte „Anmerkungen“:** zeigt praxisnah, was noch fehlt (für Laien allerdings zu laut, siehe U14).
- **Ergebniserfassung:** tabellarisch und schnell. Nicht zutreffende Felder sind gesperrt, „Disqualifiziert“ sperrt die Punkte, ungespeicherte Zeilen sind gelb. Fehlerhafte Zeilen blockieren die übrigen nicht.
- **Auswertung:** sofort verständlich („1. von 3“, nB/Disq. in Rot).
- **PDFs** (Zeitplan farbig, Ergebnisliste, Etiketten, vorausgefüllte Bewertungsbögen): direkt verwendbar.
- **Datensicherung:** Die Passwortprüfung ist gut, die Eingaben bleiben bei Fehlern stehen.
- **Schließen und Neustart:** Beim Schließen wird automatisch gespeichert bzw. gewarnt. Nach dem Neustart waren bei allen sechs Personas alle Daten vollständig da.
- **Website:** erklärt Installation, SmartScreen und Updates in einfachem Deutsch.

## 6. Bekannte, bewusst akzeptierte Punkte (nicht als neu gewertet)

- **SmartScreen-Warnung** (Signierung ausstehend): von den Personas erwähnt, als bekannt markiert.
- **Bereits mit Marco entschieden, im Bericht daher nur als Erlebnis erwähnt:**
  - Pausen je Richter unabhängig (14.09.);
  - Prüfung „angeboten?“ als Schutz gegen fremde Formulare (28.09.);
  - Passwortschutz der Sicherung als freiwillige Checkbox (Tobias hätte ihn lieber standardmäßig an, weil Adressdaten auf einen USB-Stick gehen);
  - „Rangliste drucken (PDF)…“ in der Auswertung (23.09., übernimmt den Art/LK-Filter und ist deshalb keine Doppelung des Exports).
- **Bereits bekannt, aber noch offen:**
  - englische Standardknöpfe (U6);
  - Teilnehmer-Maske, Fix vom 21.09. (U3).
- Die Web-Version war nicht Teil des Tests.

## 7. Anhang

- Einzelberichte der sechs Personas: `personas/E-A.md` … `personas/L-B.md`. Die darin genannten Screenshot-Pfade (`shots/…`) verweisen auf die temporäre Testumgebung. Archiviert sind nur die Bilder in `bilder/`.
- **Bilder:**
  - `01` Teilnehmer-Maske eng
  - `02` Startnummer einzeln (Bearbeiten-Dialog)
  - `04` Zeitplan DK parallel
  - `05` Zeitplan ohne Richter
  - `06` CSV-Import ohne Hinweis
  - `07` Reiter Formular-Import
  - `08` CHECK-constraint-Meldung
  - `09` Yes/No-Rückfrage
  - `10` PDF-Import-Gründe (positiv)
  - `11` „Keine Teilnahme“ (positiv)
