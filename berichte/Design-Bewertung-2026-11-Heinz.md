# Bewertung „Beagle“ gegen „Schiefer und Signal“ durch die Persona Heinz (21.11.2026)

Auf Marcos Wunsch hat die Persona **Heinz** (E-A aus dem UX-Test 2026-11, P1 im UX-Test Web; 58,
Prüfungsleiter seit über zehn Jahren) die grafischen Änderungen beurteilt.

**Vorgehen:** Für jedes Bild gibt es zwei Aufnahmen, frisch erzeugt mit `tools/screenshots.py` und
`tools/web_screenshots.py`:
- „vorher“: aus dem letzten Commit `bdbef92` (Beagle, mit allen Änderungen aus dem UX-Test Web), in einem vorübergehenden Arbeitsordner;
- „nachher“: aus dem Arbeitsstand (Schiefer und Signal).

Insgesamt waren es zwölf Bildpaare: fünf Desktop, sieben Web. Heinz hat nur die Bilder gesehen und
nichts bedient. Die Bilder liegen nur im Scratchpad, nicht im Repo.

## Bericht von Heinz

### Kurzfazit

Ich würde mit dem neuen Aussehen arbeiten. Der Grund ist die Ergebniserfassung:
- Die gelbe Zeile „nicht gespeichert“ fällt mir sofort ins Auge.
- Die Eingabefelder haben klare Ränder.
- Es gibt pro Seite nur noch einen dunklen Knopf, also sehe ich, was der Hauptknopf ist.

Am Handy draußen helfen mir die dicken, schwarz umrandeten Punktfelder im Bewertungsbogen mehr als
die blassen Felder von früher. Das Alte war wärmer und gemütlicher, das Neue sieht eher nach
Werkzeug aus, und das ist mir am Prüfungstag lieber.

Es ist aber nicht überall besser:
- Der Zeitplan ist durch die breitere Schrift enger geworden.
- Die Null mit Strich und die Schreibmaschinen-Zahlen sehen an manchen Stellen merkwürdig aus.
- Dass beim Abbruch das Kreuz den „gespeichert“-Haken ersetzt, verunsichert mich.

### Bewertung je Bildpaar

| Bild | besser / gleich / schlechter | Was mir auffällt |
|---|---|---|
| handbuch_start | gleich | Heller und nüchterner, der dunkle „Neuen Termin anlegen…“ ist klar der Hauptknopf. Im Datum stört mich die Null mit Strich, sie sieht aus wie ein Durchmesserzeichen. |
| handbuch_teilnehmer | eher besser | Die Felder oben haben klare Ränder, und „Chip-Nr. fehlt“ ist jetzt rötlich und springt mehr ins Auge. Aber „Testuser10“ und „Version 1.0.62“ lesen sich mit der Null mit Strich holprig. |
| handbuch_ergebniserfassung | besser | Die nicht gespeicherte Zeile ist richtig gelb wie Absperrband, die sieht man auch im Augenwinkel. Die Punktfelder sind weiß mit Rand und deutlich als Eingabe erkennbar. Bei Abbruch und Disqualifiziert steht jetzt aber ein schwarzes × statt grünem Haken, und ich weiß nicht mehr, ob die Zeile gespeichert ist. „Abbruch: Verletzun…“ ist weiterhin abgeschnitten. |
| handbuch_zeitplan | schlechter | Die neue Schrift ist breiter, deshalb brechen die Blockzeilen öfter um. Beide Richterlisten brauchen jetzt einen Rollbalken, und ich sehe weniger vom Plan auf einmal. |
| handbuch_uebersicht | gleich | Die Zahlen sind klar. Der graue Kopfstreifen der Tabellen läuft über die ganze Breite, obwohl die Tabelle nur halb so breit ist. Das sieht unfertig aus. |
| handbuch_web_login | gleich (eher besser) | Die Felder sind deutlich umrandet, der Knopf ist dunkel und kräftig. |
| handbuch_web_teilnehmerliste | eher besser | Der Suchknopf ist kräftiger, die Felder sind klarer. „bewertet“ hat jetzt einen Rand und ist gut zu sehen. |
| handbuch_web_ergebnis_dk | besser | Die Felder sind kräftig umrandet und draußen besser zu treffen. Die Bereichsangaben „(0-60)“ wirken aber wie aus einer anderen Schrift. |
| handbuch_web_ergebnis_fehler | gleich | Die Fehlermeldung sieht praktisch aus wie vorher, rot und ohne Zeichen. Die eingetippte „45“ steht in Schreibmaschinenschrift. |
| handbuch_web_bewertungsbogen | besser, mit Vorbehalt | Die Punktzahlen sind groß und fett in dicken Rahmen, das kann der Richter auch in der Sonne lesen. „Speichern, nächster Start“ ist ein guter Gedanke, aber es steht nicht da, welcher Start der nächste ist. Jetzt sind es vier Knöpfe untereinander, und „Abbrechen“ sieht genauso aus wie „Nur speichern“. |
| handbuch_web_ergebnistabelle | besser | „Alle speichern“ ist als einziger Knopf dunkel, die Nebensachen sind nur umrandet. „noch kein Ergebnis“ in Gelb zeigt mir sofort, wo etwas fehlt. Die vielen weißen Kästchen (Felder und „Bogen“-Knöpfe) sehen sich aber sehr ähnlich. |
| handbuch_web_admin_termine | gleich | Der Hauptknopf ist dunkel, sonst hat sich kaum etwas geändert. „Löschen“ sieht immer noch genauso harmlos aus wie „Ergebnisse zurückholen“. |

### Noten vorher → nachher (Schulnoten)

| Bereich | vorher | nachher | Grund |
|---|---|---|---|
| Lesbarkeit | 2 | 2 | Die Texte sind klarer und die Ränder schärfer. Dafür stehen die Zahlen in Feldern in Schreibmaschinenschrift, und die Null mit Strich wirkt in Datum und Uhrzeit fremd. Der Zeitplan ist enger. |
| Orientierung | 2 | 2+ | Pro Seite gibt es einen dunklen Hauptknopf, das hilft. Im Bewertungsbogen sind es allerdings vier Knöpfe. |
| Zustand auf einen Blick | 3 | 2 | Gelb für „nicht gespeichert/offen“ ist ein großer Gewinn. Abzug gibt es für das ×, weil ich bei Abbruch und Disqualifiziert nicht sehe, ob gespeichert ist. |
| Tauglichkeit draußen (Web am Handy) | 3 | 2 | Kräftige schwarze Feldränder, große fette Punktzahlen und ein dunkler Knopf auf hellem Grund sind deutlich besser als Creme auf Creme. |
| Eindruck/Vertrauen | 2 | 2 | Das Neue wirkt sachlicher, wie ein Arbeitsgerät. Das Alte hatte mehr Charakter. Die Kleinigkeiten kosten ein bisschen. |

### Was mich stört

- **Null mit Strich:** Sie steht in Datum, Uhrzeit, Version und Namen.
- **Schreibmaschinen-Zahlen:** Punkte und Bereichsangaben wirken wie aus einer anderen Schrift.
- **× bei Abbruch/Disqualifiziert:** Ein × klingt für mich nach „Fehler“ oder „nicht gespeichert“.
- **Abbruch-Grund abgeschnitten:** „Abbruch: Verletzun…“ ist noch immer gekürzt.
- **Zeitplan enger:** Es gibt mehr Zeilenumbrüche, beide Spalten haben einen Rollbalken.
- **Übersicht:** Der graue Tabellenkopf läuft ins Leere.
- **Bewertungsbogen:**
  - vier Knöpfe, von denen drei gleich aussehen;
  - „Abbrechen“ fällt nicht als Gefahr auf;
  - es ist nicht zu sehen, wer als Nächstes kommt;
  - „Punktzahl (0-“ bricht vor „60)“ um.
- **Termin „Löschen“:** Der Knopf sieht harmlos aus.
- **Fehlermeldung im Web:** Sie hat kein Warnzeichen und ist bei Sonne blass.

### Wünsche (priorisiert)

1. Bei Abbruch und Disqualifiziert weiterhin sehen, dass gespeichert ist, z. B. „× Abbruch (gespeichert)“. Den Abbruch-Grund ganz lesbar machen.
2. Im Zeitplan wieder so viel auf einen Blick wie vorher.
3. Die Null mit Strich nur dort, wo Verwechslung droht, und Zahlen in derselben Schrift wie der Text.
4. Bei „Speichern, nächster Start“ zeigen, wer als Nächstes kommt. „Abbrechen“ sichtbar anders gestalten.
5. Gefährliche Knöpfe („Löschen“) und Fehlermeldungen im Web auffälliger machen.

## Einordnung durch die Sitzung

**Bestätigt:**

- **Null mit Strich:** Sie gehört zur Schrift. Atkinson Hyperlegible Next hat keine Variante ohne Strich; in der Datei gibt es nur `zero` und `zero.tf`, alle mit Strich. Abhilfe wäre nur eine andere Schrift oder hinnehmen.
- **„Schreibmaschinen-Zahlen“:** Das sind die gleich breiten Ziffern (`tabular-nums`). Im Web gelten sie für alle Zahlenfelder, am Desktop nur für die Punktezellen. Die „(0-60)“ in den Beschriftungen sind normale Schrift, wirken aber wegen der Null mit Strich fremd.
- **Zeitplan enger:** Das ist plausibel, weil die neue Schrift bei gleicher Punktgröße breiter läuft als Segoe UI. Es ist auf den Bildern sichtbar und noch nicht gemessen.
- **× bei Disqualifiziert/Abbruch:** Das war eine bewusste Entscheidung („kein grüner Haken neben Disqualifiziert“). Heinz liest das × aber als „nicht gespeichert“. Das ist ein echter Zielkonflikt.
- **Abgeschnittener Abbruch-Grund und Termin „Löschen“:** Beide gab es schon vor der Änderung; Heinz hat sie früher gemeldet.

**Marcos Entscheidung (21.11.2026):** Alle Wünsche sind erledigt oder entschieden (Arbeitsstand,
nicht committet).
- Die Wünsche 1, 2, 4 und 5 sind umgesetzt (Einzelheiten unten).
- Wunsch 3 bleibt so: Marco gefällt die Null mit Strich (Entscheidung C43).
- Zusätzlich hat Marco eine Großansicht je Richterspalte im Zeitplan gewünscht.

1. **Ergebniserfassung (Desktop):**
   - Disqualifiziert und Abbruch zeigen einen Haken in Tinte (= gespeichert, aber kein normales Ergebnis) und nur das kurze Wort „disqualifiziert“ bzw. „Abbruch“.
   - Der Grund steht in der Abbruch-Spalte daneben, alles zusammen im Tooltip.
   - „Abbruch, gespeichert“ wurde ausprobiert, aber bei 1400 px Fensterbreite wieder gekürzt.
2. **Zeitplan:**
   - Die Richterspalten wachsen in den freien Platz, höchstens 460 px.
   - Bei zwei Richtern stehen die Blockköpfe in einer Zeile, der Rollbalken entfällt.
   - Bei vielen Richtern bleibt die Mindestbreite von 300 px mit seitlichem Blättern.
4. **Web-Bogen:**
   - Unter „Speichern, nächster Start“ steht, wer als Nächstes kommt („Danach: Start-Nr. 2, …“). Beim letzten Start steht, wohin es danach geht.
   - „Abbrechen / Zurück (ohne Speichern)“ ist ein Textlink unter den Knöpfen statt eines Knopfs.
5. **Web, Löschen und Fehler:**
   - „Termin löschen“ und „Löschen“ bei den Benutzern sind rot umrandet mit roter Schrift.
   - Fehlermeldungen haben ein Warnzeichen und einen kräftigeren Rand; Konflikte zeigen dasselbe Zeichen in Tinte.

**Zusatz (Marco):** Im Zeitplan hat jede Richterspalte „Groß anzeigen“. Damit ist nur diese Spalte über die ganze Breite zu sehen, zum Ansehen und Einrichten, etwa bei „Sehr groß“ oder vielen Richtern; „Alle Richter zeigen“ führt zurück. „Richter hinzufügen“, „Automatisch verteilen“ und „Pause bei allen“ führen ebenfalls zurück zu allen Spalten.
