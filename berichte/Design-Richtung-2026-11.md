# Design-Richtung „Schiefer und Signal“ (21.11.2026)

Ergebnis eines Design-Gesprächs mit Marco (Skill `frontend-design`). Die Richtung ist abgestimmt,
umgesetzt ist noch nichts. Sie löst später das Erscheinungsbild „Beagle“ (01.11.2026) ab.
Die Website unter `docs/` folgt erst nach der Anwendung.

**Grundlage:**
- Screenshots aus 1.0.62 in `docs/bilder/`.
- Der Web-Stand nach dem UX-Test ist nur in den Templates geprüft. `templates/bewertungsbogen.html`
  hat weiterhin zwei gleich starke Speicher-Knöpfe und neun Stammdatenzeilen.
- Die Kontrastwerte sind nach WCAG 2.x berechnet.

## Gegenstand, Zielgruppen, Hauptaufgabe (von Marco bestätigt)

Das SHS-Prüfungsprogramm ist ein kostenloses Werkzeug für die Prüfungsleitung im Spürhundsport.
Jeder Verein kann es nutzen. Es reicht von der Meldung über Zeitplan und Bewertungsbogen bis zu
Wertnote und Rangliste.

| Rang | Wer | Wo und wie | Hauptaufgabe |
|---|---|---|---|
| 1 | Richter (Web) | am Handy draußen, in Sonne und Regen, oft einhändig, zwischen zwei Starts | je Start zwei Zahlen fehlerfrei eintragen und sicher wissen, dass sie gespeichert sind |
| 2 | Prüfungsleitung/Meldestelle (Desktop) | am Laptop im Vereinsheim oder im Zelt, am Prüfungstag unter Zeitdruck | den Tag im Griff behalten: wer startet wann, was fehlt, was ist ungespeichert |
| 3 | andere Vereine (Website) | am Schreibtisch, abwägend | entscheiden, ob sie von der LibreOffice-Datei umsteigen |

Der Richter am Handy ist der Prüfstein: Was in der Sonne funktioniert, funktioniert auch am Laptop.

## Kritik am Erscheinungsbild „Beagle“

„Beagle“ hat das Standardblau, die Emojis und die fehlende Identität behoben, also die Anlässe
vom 01.11.2026. Vier Schwächen bleiben:

1. **Die Farbwahl ist selbst ein Klischee.** Creme-Fläche, warmes Braun als Akzent und runde
   Karten mit weichem Schatten sind ein verbreiteter Standard-Look generierter Oberflächen. Die
   Farbe kommt vom Fell des Hundes, nicht aus dem Sport.
2. **Die Kanten verschwinden draußen.** Kartenrand #E2D9CB auf #FBF8F3 hat 1,32 : 1, das
   Eingabefeld #F2ECE2 auf #FBF8F3 am Desktop 1,11 : 1, die Status-Pille „bewertet“ auf der Karte
   1,14 : 1. Für Bedienelemente gilt mindestens 3 : 1. Der Text ist mit 6,9 : 1 gut.
3. **Ein Akzent für alles bedeutet nichts.** Knöpfe, Links, Reiter, Haken und Fokus sind alle
   lohbraun. Das Warn-Orange #A15C00 liegt zum Akzent #8C5A32 bei 1,12 : 1. „Nicht gespeichert“
   sieht deshalb aus wie ein normaler Knopf. Im Web-Bogen stehen außerdem zwei gleich starke
   Hauptknöpfe nebeneinander.
4. **Die wichtigsten Daten sind am kleinsten.** Die Punktzahlen stehen im Bogen in normaler
   Größe unter neun Zeilen Stammdaten. Am Desktop wirken Tabellen, Kopf und Knöpfe gleich laut.

Verworfen wurde Richtung A „Markierungsband“: Tanne mit Warnwesten-Orange als Aktionsfarbe.
Grund: Das Orange der Aktion (#C4410B) und das Grün für „gespeichert“ (#2A7A47) sind gleich
hell (1,03 : 1) und für Rot-Grün-Schwache kaum zu unterscheiden. Übernommen wird nur das
Absperrband-Gelb für „ungespeichert“.

## Was Marco entschieden hat und was offen ist

Von Marco gewählt (21.11.2026):
- Richtung B „Schiefer und Signal“ mit Absperrband-Gelb aus A.
- Umfang „Bausteine, eine Identität“: Farben, Schrift, Felder, Knöpfe, Status und Zahlen. Die
  Akzentwahl entfällt. Es bleiben der Standard, „Dunkel“ und „Hoher Kontrast“, die beiden
  letzten aus B abgeleitet.
- Schrift Atkinson Hyperlegible Next.
- Marke: das Programm dezent, Verein und Termin prominent.
- Der Beagle bleibt als Bild. Wo er erscheint, wurde in der zweiten Runde entschieden (unten).
- Im Web-Bogen soll die Hauptaktion „Speichern, nächster Start“ sein.

In einer zweiten Runde entschieden:
- Der Beagle bleibt wie heute rund links im Kopf.
- Bogen-Kopf und Seitenkopf werden nicht umgebaut. Das Layout bleibt.
- „Nächster Start“ ist die nächste Startnummer mit dieser Disziplin, ob bewertet oder nicht.
  „Speichern, nächster Start“ ist damit eine neue Funktion, keine reine Gestaltung.

Noch offen, bei der Umsetzung kurz bestätigen: Was geschieht nach der letzten Startnummer?
Vorschlag: zurück zur Liste mit der Meldung „Gespeichert“.

## Abgestimmte Richtung: B „Schiefer und Signal“ mit Absperrband-Gelb

Leitidee: ein ruhiges Werkzeug in Gelände- und Betontönen. Farbe ist ausschließlich Information.
Signalfarben kommen aus dem Prüfungsgelände (Warnweste, Absperrband) und erscheinen nur dort, wo
etwas fehlt oder noch nicht gespeichert ist.

### Farben (Standard, hell)

| Name | Hex | Rolle | Kontrast (WCAG) |
|---|---|---|---|
| Beton | #EEF0EC | Grund | Tinte darauf 14,1 : 1 |
| Weiß | #FFFFFF | Karten, Eingabefelder | Tinte darauf 16,5 : 1 |
| Tinte | #1B2220 | Text, Rahmen der Zahlenfelder | – |
| Schiefer | #2A3035 | Kopf, der eine Hauptknopf je Ansicht, Fokus | Weiß darauf 13,4 : 1; zum Grund 11,6 : 1 |
| Signal | #D9480F | Balken und Symbole „fehlt/ungespeichert“ | 3,75 : 1 zum Grund, 4,3 : 1 zu Weiß (nur Flächen, Balken, große Schrift) |
| Absperrband | #FFD43B | Fläche „noch nicht gespeichert“ (Web-Bogen, Desktop-Zeile) | Tinte darauf 11,4 : 1 |

Ergänzende Werte:
- Feldrand #7A837E (3,9 : 1 zu Weiß, 3,4 : 1 zum Grund).
- Gedämpfter Text #4F5853 (6,4 : 1 zum Grund).
- Kopftext #F1F3F2 und #B9C1BC (12,0 bzw. 7,3 : 1 auf Schiefer).
- Gespeichert #2A7A47 (4,6 : 1 zum Grund).
- Signal als kleine Schrift: dunkler #B33A0A (6,0 : 1 zu Weiß).

Regeln:
- Absperrband-Gelb hebt sich vom Grund kaum ab (1,24 : 1). Es erscheint deshalb immer mit einem
  Signal-Balken am Rand oder mit dunklem Rahmen, nie als Fläche allein.
- **Ungespeichert und gespeichert werden nicht über Orange und Grün unterschieden.** Signal
  #D9480F und Gespeichert #2A7A47 sind gleich hell (1,23 : 1, die dunkle Signal-Schrift 1,13 : 1),
  also dieselbe Schwäche wie bei A. Den Unterschied tragen die Absperrband-Fläche, das Symbol und
  das Wort. Gespeichert hat keine Fläche, nur Haken und Wort in Grün.
- **Disqualifiziert** wird nicht in Rot neben Signal-Orange gezeigt (1,5 : 1 zueinander). Es
  erscheint in Tinte mit eigenem Symbol und Wort.
- **Eingabefehler** (Rot #B3261E) stehen im selben Formular wie Signal-Hinweise. Sie
  unterscheiden sich durch Ort und Form: Ein Fehler steht direkt am Feld (roter Feldrahmen,
  Text unter dem Feld, Fehlersymbol). Der Signal-Hinweis „ungespeichert“ ist ein Balken mit gelber
  Fläche über dem Hauptknopf.
- Jeder Status trägt Symbol und Wort, nie Farbe allein.
- **Fokus:** auf hellen Flächen ein 2-px-Rahmen in Schiefer mit Abstand. Auf Schiefer (Kopf,
  Hauptknopf) ein Rahmen in Absperrband-Gelb (9,4 : 1 auf Schiefer).
- Lohbraun entfällt als Akzent. Auch die Akzentwahl (Blau, Grün, Violett) und die Hintergrundwahl
  entfallen. Es bleiben der Standard sowie „Dunkel“ und „Hoher Kontrast“, beide aus dieser Logik
  abgeleitet: Schiefer-Flächen, dieselben Rollen für Signal und Absperrband, Werte bei der
  Umsetzung über die Kontrasttests in `test_theme.py`. Eine gespeicherte alte Wahl wird zum
  Standard umgezogen, wie damals `sand` → `beagle`.

### Schrift

**Atkinson Hyperlegible Next** für Desktop, Web und Website: eine Familie, Ziffern mit festen
Breiten (`tabular-nums`). Sie wurde für Lesbarkeit unter schlechten Bedingungen entworfen. Sie
soll 1/7, 3/8 und 0/O klar unterscheiden, was für Punktzahlen draußen entscheidend ist. Das ist
an den Schriftdateien zu prüfen.

Zusätzlich zu prüfen:
- Enthält die Familie Ziffern mit festen Breiten?
- Lassen sie sich in Qt (PySide6) einschalten?
- Andernfalls: Gibt es eine Ausweichlösung, etwa die Mono-Variante nur für Zahlenfelder?

- Sie wird mitgeliefert wie DejaVu für die PDFs. Externe Quellen sind ausgeschlossen: CSP im Web,
  und die Website lädt nichts von Dritten.
- Vor der Übernahme prüfen: Lizenz (erwartet SIL OFL 1.1), Eintrag in `lizenzen/` und
  `test_drittlizenzen`, Bündelung in `build.spec` und im Container, Laden über
  `QFontDatabase.addApplicationFont`.
- Die PDFs bleiben vorerst bei DejaVu Sans Condensed.
- Schriftgrößen-Einstellung und „Hoher Kontrast“ müssen mit der neuen Schrift weiter
  funktionieren.

### Layout-Prinzipien

1. **Die eine mutige Stelle sind die Zahlen.** Punktzahlfelder sind groß (am Handy etwa 30–34 px),
   haben einen kräftigen dunklen Rahmen (1,5–2 px Tinte) und feste Ziffernbreiten, wie Kästchen
   auf dem Klemmbrett. Alles drumherum bleibt ruhig.
2. **Je Ansicht genau ein Hauptknopf** in Schiefer. Weitere Aktionen sind sekundär oder Links.
3. **Bewertungsbogen am Handy:**
   - Hauptaktion „Speichern, nächster Start“ (gewählt), darunter „Nur speichern“ und „Zur
     Tabelle“ als Links.
   - „Nächster Start“ ist die nächste Startnummer mit dieser Disziplin, ob bewertet oder nicht.
   - Der Bogen-Kopf mit seinen Stammdaten bleibt wie heute (Marco: kein Layout-Umbau).
4. **Kopf bleibt im Aufbau wie heute.** Der Beagle bleibt rund links, daneben Verein und Termin.
   Er bekommt nur die neuen Farben (Schiefer) und die neue Schrift.
5. **Kleinere Radien (4–6 px), keine weichen Schatten.** Karten nur dort, wo sie etwas abgrenzen.
   Dichte Listen bekommen Zeilen mit Linien.
6. **Linksbündig.** Zustände am Desktop (Ergebnistabelle, Zeitplan) verwenden dieselben Farben
   und Symbole wie im Web.

## Ausblick Website (`docs/`)

Die Website übernimmt Farben, Schrift und Prinzipien, sobald die Anwendung umgestellt ist. Die
dunkle Variante wird aus „Dunkel“ abgeleitet. Ein eigenes Gespräch dazu folgt. Website-Änderungen
gehen erst mit dem Release online, das das neue Erscheinungsbild enthält.

## Nächste Schritte (erst nach Marcos Go)

1. Lizenz und Bündelung der Schrift prüfen.
2. Werte für „Dunkel“ und „Hoher Kontrast“ ableiten und gegen `test_theme.py` prüfen.
3. Umsetzung je Bereich (Desktop `desktop_darstellung.py`, Web `templates/base.html`) mit Tests.
   Danach Screenshots, Handbuch und Website. Kein Build ohne Anforderung.
