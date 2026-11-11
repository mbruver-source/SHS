# UX-Nachtest 2 nach den Aufgaben „Note 1“ (04.11.2026)

Nachtest mit fünf Personas nach der Umsetzung der ToDo-Liste [note1-todos.md](note1-todos.md)
(Aufgaben B1–B11, siehe [aufgaben-note1.md](aufgaben-note1.md)). Gleiches Steuerwerkzeug, gleiches
Szenario (Aufgaben 0–15), Arbeitsstand nach 1.0.55. Heinz testete vor B13 (Q1–Q4 aus der
Abschluss-QS), alle anderen mit B13. Die Personas kannten die Änderungen nicht und haben ihre
früheren Funde erst nach dem Test abgeglichen.

- **Heinz (E-A2):** erfahren, mit Handbuch – [personas/E-A2.md](personas/E-A2.md)
- **Sabine (E-B2):** erfahren, Excel-Profi, ohne Handbuch – [personas/E-B2.md](personas/E-B2.md)
- **Julia (N-A2):** organisiert zum ersten Mal, mit Handbuch – [personas/N-A2.md](personas/N-A2.md)
- **Gerda (L-A2):** Laiin, Handbuch und Kurzanleitung ausgedruckt – [personas/L-A2.md](personas/L-A2.md)
- **Werner (L-B3):** Laie, ohne Handbuch (dritter Durchgang) – [personas/L-B3.md](personas/L-B3.md)

## Ergebnis

| Persona | Installation | Erststart | Termin-Ablauf | **Gesamt** | **Gesamt vorher** | Allein am Prüfungstag? |
|---|---|---|---|---|---|---|
| Heinz | 2 (2) | 1 (2) | 1 (2) | **1–** | 2 | Ja |
| Sabine | 2 (2) | 1 (1–2) | 1–2 (2) | **1–2** | 2 | Ja |
| Julia | 2 (2) | 1 (2) | 1 (2) | **1** | 2 | Ja |
| Gerda | 3 (4) | 2+ (2) | 1– (2–) | **2+** | 2–3 | Ja (mit Handbuch) |
| Werner | 3+ (3) | 2+ (2+) | 1– (2) | **2+** | 2 (Nachtest 1), 2– (1. Test) | Ja (vorher „Eher ja“) |

In Klammern die Noten des vorigen Tests.

- **Alle fünf kommen allein klar**, keine Aufgabe gescheitert. Nur Gerda hatte bei der
  Installation ein „~“ (englische GitHub-Seite).
- **Termin-Ablauf:** bei allen 1 bis 1–2. Damit ist das Ziel „Note 1“ für den Prüfungstag
  erreicht.
- **Gesamtnote:** Erfahrene und Normale liegen bei 1 bis 1–2. Die Laien liegen bei 2+, gebremst
  von der Installation (3 bzw. 3+). Die Warnungen von Browser und Windows bleiben ohne
  Code-Signatur (B8, offen).
- **Abgleich mit den früheren Funden:** 45 behoben, 7 weitgehend, 4 teilweise, 2 nicht behoben,
  1 nicht erlebt.
  - Nicht behoben: einheitliche Prüfungsnamen (Julia, R-B8 bewusst so gelassen) und
    „Richter hinzufügen“ ohne Namen (Heinz).

| Persona | behoben | weitgehend | teilweise | nicht behoben | nicht erlebt |
|---|---|---|---|---|---|
| Heinz | 10 | 1 | 1 | 1 | – |
| Sabine | 7 | 1 | 1 | – | – |
| Julia | 8 | 1 | 1 | 1 | – |
| Gerda | 8 | 2 | – | – | – |
| Werner | 12 | 2 | 1 | – | 1 |

- **Ausdrücklich gelobt:**
  - die Bestätigung „keine Überschneidungen“ nach dem Verteilen, mit Mittagspause im Dialog;
  - die Auswahl „Prüfung“ im Teilnehmer-Dialog;
  - die Punkte, die beim Tippen sofort rot werden;
  - „N Teilnehmer gespeichert“;
  - die Demo mit Lesezeit und „Schritt zurück“;
  - „Letzter Import“ zum Nachlesen;
  - die Hilfe mit Suche und F1.

## Neue bzw. verbliebene Funde (zusammengefasst)

Nach Schwere und Zahl der Personas sortiert. Nichts davon ist umgesetzt, die Punkte gehen zur
Entscheidung an Marco.

| Nr | Fund | Personas | Schwere |
|---|---|---|---|
| N1 | Abbruchgrund in der Zelle abgeschnitten („Verletzung H…“). Die Spalte „Status“ zeigt ihn ganz. Bei Schrift „Groß“ ist auch der Status abgeschnitten. | alle 5 | mittel |
| N2 | Schrift „Groß“: Die Erfassungsmaske bekommt trotz maximiertem Fenster eine waagerechte Bildlaufleiste und ist rechts abgeschnitten. | Gerda, Heinz | mittel |
| N3 | Kurzanleitung: Kein Bild der GitHub-Seite mit „Assets“ und keins vom Setup („Nur für mich“). Die Adresse muss man abtippen, der Download-Knopf der Website wird nicht erwähnt. Das Edge-Bild zeigt „1.0.45“. | Gerda | mittel |
| N4 | „Startnummer tauschen…“ zwischen zwei Prüfungen warnt nicht, dass die Nummern danach außerhalb ihrer Bereiche liegen, auch nicht bei gespeicherten Ergebnissen. Nach dem Tausch kommt keine Bestätigung. | Julia, Werner | mittel |
| N5 | Prüfungsnamen uneinheitlich („Trümmer LK 2“ / „ED LK 2 Trümmerfeld“, „DK-LK 1“ / „DK LK 1“). R-B8 war „so lassen“. | Heinz, Sabine, Julia, Gerda | gering |
| N6 | Hilfe: Der Knopf „Hilfe“ öffnet ganz oben, F1 und das Menü beim Reiter. Die Suche findet Wortteile („USB“ → „ausbalancierten“). „USB-Stick“ und „Tastenkürzel“ kommen nicht vor. Der Treffer ist blass markiert. | Heinz, Julia, Werner, Sabine, Gerda | gering |
| N7 | „Richter hinzufügen“ fragt nicht nach dem Namen. Ein leerer „Richter 4“ steht als eigene Seite im Zeitplan-PDF. | Heinz | gering |
| N8 | „4,5“ in einer Punktzelle wird zu 45. Bei Buchstaben spricht der Hinweis von „Kommazahlen“. | Sabine | gering |
| N9 | Demo: Schritt 3 spricht noch von „Art und Leistungsklasse“, die Maske hat aber nur noch das Feld „Prüfung“ (B8). „Anzahl 20“ passt nicht zu den Bereichen 1–19, 21–39. „Beenden“ fragt nicht nach. | Gerda, Heinz | gering |
| N10 | Bestätigung nach dem Verteilen zählt den Dreikampf je Disziplin („10 Prüfung(en) mit 28 Start(s)“ bei 6 angebotenen Prüfungen und 16 Teilnehmern). | Gerda | gering |
| N11 | Gegenstände: Die ED-Rückfrage sagt nicht, wohin der zweite Gegenstand soll. Ein freies Notizfeld fehlt. „Gegenstand noch offen“ ist nicht erklärt. Die CSV-Meldung sagt nicht, dass Gegenstände nachzutragen sind. | Gerda, Heinz, Werner, Julia | gering |
| N12 | Abgelehntes PDF mit zwei angekreuzten Prüfungen (Pfeiffer): Ein konkreter Rat fehlt, nur der allgemeine Abschnitt „Was tun?“ ist da. | Julia, Gerda | gering |
| N13 | „Alle Startnummern zurücksetzen…“ spricht vom Web, obwohl nichts veröffentlicht ist, und nennt vorhandene Ergebnisse nicht. | Werner | gering |
| N14 | Termin-Dialog: „Behältnisse“, „Fläche“ und die Startnummern-Bereiche sind erst nach dem Bildlauf zu sehen. Die Seitenleiste „Offene Starts“ ist schmal. | Julia | gering |
| N15 | Entf in der Teilnehmerliste tut nichts (aus Excel gewohnt). | Sabine | gering |
| N16 | Eine feste Mittagspause um 12:00 mit Lücke davor geht nicht. Die Meldung „Keine Pause eingefügt …“ ist ehrlich, es bleibt ein Wunsch. | Sabine | gering |
| – | Verband wird zweimal angemahnt (Termin, Anmeldeformular). Das ist so gewollt (T7), kein Handlungsbedarf. | Werner | – |

## Grenzen dieses Tests

- Gleiche Testumgebung wie bisher: Qt offscreen, englischer Dateidialog, Bedienung per Befehl,
  Installation nur gedanklich.
- **Harness:**
  - In der ersten frischen Sandbox (EA2) fehlte `home\Downloads`. Heinz hat ihn angelegt, für die
    übrigen war er vorbereitet.
  - Zweimal gab es einen `PermissionError` auf eine Antwortdatei, der nächste Befehl lief normal.
  - Einmal kam „Programm läuft bereits“ beim sofortigen Neustart.
  - Einmal hatten sich die Element-Nummern verschoben, dadurch ein Fehlklick auf „Beenden“ in der
    Demo.
- Heinz testete den Stand vor B13. Die Demo-Korrektur „Schritt zurück“ aus Schritt 10/11 hat er
  nicht erlebt.
