# Abgespeckter UX-Test der Web-Entwicklungen (19.11.2026)

Getestet wurden die Neuerungen seit 1.0.62 (Arbeitsstand, noch nicht ausgeliefert): Container mit HTTPS-Proxy,
Ersteinrichtung und Konten im Web, **Veröffentlichen aus dem Desktop**, **Ergebnistabelle** und **Online-Bewertungsbogen**
im Web, **Zurückholen** (inkl. Disqualifikation, Abbruch, Notizen) und **Sammel-PDF** der Bögen. Geprüft wurde nicht,
ob das Programm richtig rechnet, sondern **wie es sich bedienen lässt** und **wie übersichtlich die Web-Oberfläche ist**.

Alle Funde sind **Beobachtungen und Vorschläge, keine Umsetzungen**. Jeder Punkt wird einzeln mit Marco besprochen.

## 1. Methode

- **Vier erfundene Personas** (Einzelberichte in [personas/](personas/)):

| Persona | Rolle | Gerät | Aufgaben | Gesamtnote |
|---|---|---|---|---|
| P1 Heinz, 58 | Prüfungsleiter, erfahren, mit Handbuch | Desktop | 1–3, 5–6 | **2,3** (Teil 1: 2,0; Teil 2: 2,5) |
| P2 Julia, 34 | Organisation zum ersten Mal, ohne Handbuch | Desktop | 1–3, 5–6 | **2,3** (Teil 1: 2,0) |
| P3 Ruth, 52 | Wertungsrichterin, **Online-Bewertungsbogen** | Tablet 768 px | 4 (Gruppe A) | **2,3** |
| P4 Dennis, 29 | Richter-Helfer, Laie, **nur Punkte** | Handy 375 px | 4 (Gruppe B) | **2,6** |

- **Szenario (6 Aufgaben):** 1 Container einrichten (README), 2 Admin und zwei Richterkonten im Web, 3 Desktop: Web-Verbindung
  (Fingerabdruck) und Termin veröffentlichen, 4 Richter erfassen (Bogen bzw. nur Punkte, mit absichtlichen Patzern: 84 statt 48,
  54 statt 45, vergessene Anzeige), 5 Zurückholen und Bericht lesen, 6 Sammel-PDF.
- **Umgebung:** echter Container-Stack (Port 6443, getrennt von Marcos Stack), Web im eingebauten Browser, Desktop-App echt,
  aber über ein Steuerwerkzeug (Qt offscreen, eigenes Profil, Windows-Tresor aus). Personas entschieden nur nach Bildschirm,
  Beschriftung und Meldung.
- **Grenzen:** Die Zertifikatswarnung konnte der Test-Browser nicht selbst bestätigen (Marco tat es einmal; deshalb gibt es dazu
  keine Persona-Wertung). „Passwort merken“ ist im Test abgeschaltet (Tresor). Ob der Download als `.tmp` ankommt, liegt
  vermutlich am Test-Browser (der Server sendet den richtigen Namen, geprüft). Handy/Tablet nur mit Ruth und Dennis, Admin-Sicht
  nur am Desktop. Windows-Skalierung nicht getestet.
- **Abschottung:** Marcos Stack (Port 5443) und seine Daten blieben unberührt (geprüft). Beim Bau des Steuerwerkzeugs legte ein
  früher Lauf einmal einen Registry-Schlüssel an; sofort entfernt, danach Registry, Programmordner, Windows-Anmeldeinformationen
  und Repo unverändert (Fingerabdruck-Vergleich in `steuer\beweise\`).

## 2. Ergebnis auf einen Blick

- Alle vier Personas haben ihre Aufgaben **im Kern geschafft** (Container, Konten, Veröffentlichen, Erfassen, Zurückholen).
  Nach Abmelden und Anmelden waren alle Eingaben noch da; der Rückhol-Bericht stimmte mit der Ergebniserfassung überein.
- Die Noten liegen zwischen **2,0 und 2,6**. Am schwächsten: **Disqualifikation am Handy (4)**, **Tabelle am Handy (4)**,
  **PDF-Download (3)**, **Rückmeldungen (3)**.

### Übersichtlichkeit der Web-Oberfläche (Schulnoten der Personas)

| Gesichtspunkt | Heinz (Admin) | Julia (Admin) | Ruth (Tablet) | Dennis (Handy) |
|---|---|---|---|---|
| Orientierung | 2 | 2 | 2 | 2 |
| Beschriftungen und Begriffe | 2 | 2 | 2 | 3 |
| Lesbarkeit/Bedienbarkeit am Gerät | 2 | 2 | 2 (Bogen), 3–4 (Tabelle) | 1–2 (Einzelseite), **4** (Tabelle) |
| Rückmeldungen (gespeichert? Fehler?) | 3 | 3 | 3 | 3 |
| Vertrauen (sind meine Eingaben sicher?) | 2 | 2 | 2 | 3 |

**Kernaussage:** Die Einzelseite je Person und der Bogen sind am Gerät gut zu bedienen. Schwach sind **Wege und Rückmeldungen**:
Der Bogen ist schwer zu finden, die Tabelle ist am Handy/Tablet zu breit, und vieles wird nur still gespeichert oder falsch
benannt („bewertet“ statt „disqualifiziert“).

## 3. Funde nach Themen (zusammengefasst, mit Quelle)

Schwere: **stört** (kostet Zeit oder Vertrauen), **Kleinigkeit**. Ein Blocker trat nur im Test-Browser auf (Zertifikat, Download-Name).
„im Code bestätigt“ heißt: Ich habe die Aussage beim Zusammenstellen gegen den Quellcode geprüft.

### A. Orientierung und Wege
| Nr | Fund | Quelle | Schwere |
|---|---|---|---|
| A1 | **Der vollständige Bewertungsbogen** (Notiz, Abbruch, Disqualifikation) ist nur über den kleinen Knopf „Bogen“ in der Ergebnistabelle erreichbar; die Einzelseite aus der Teilnehmerliste wirkt wie „der“ Bogen, hat aber nichts davon | Ruth F1 | stört (fast Blocker) |
| A2 | Startseite `/` zeigt das **Anmeldeformular, obwohl man angemeldet ist** (Kopfleiste zeigt „Abmelden“) – im Code bestätigt (`login` leitet Angemeldete nicht weiter) | Julia F10 | stört |
| A3 | Admin: „Termine“ (Verwaltung) und „Termin wechseln“ liegen nebeneinander und sind verwechselbar; der Weg zur Ergebnistabelle ist nicht naheliegend; Admin ohne Termin landet auf „Termin wählen“ | Heinz, Julia F17, Heinz F6 | stört wenig |
| A4 | Kopfleiste wandert beim Scrollen weg (Tablet) | Ruth F6 | Kleinigkeit |
| A5 | Im Desktop ist „Web“ nicht auf Anhieb zu finden (Julia suchte unter „Ergebniserfassung“, es liegt in „Datensicherung“) | Julia F9 | stört wenig |

### B. Rückmeldungen und Vertrauen
| Nr | Fund | Quelle | Schwere |
|---|---|---|---|
| B1 | Keine Erfolgsmeldung nach „Benutzer anlegen“ | Heinz F3, Julia F1 | stört wenig |
| B2 | Einzelseite: nach „Speichern“ keine Bestätigung, nur die Liste; dort „bewertet“ auch bei Disqualifikation, „offen“ trotz gespeicherter Disziplin, „bewertet“ bei Abbruch | Dennis F3/F4, Ruth F3 | stört |
| B3 | „1 Zeile(n) gespeichert.“ ist technisch und steht oben, die Seite springt nicht dorthin | Ruth F9, Dennis F6 | stört |
| B4 | Höchstwert überschritten (84 bei 60): die Fehlermeldung war für Ruth nicht lesbar (nur Rahmen am Feld) | Ruth F2 | stört (Beobachtung, nicht nachgestellt) |
| B5 | **Sammel-PDF:** nach dem Klick keine sichtbare Rückmeldung, Datei kommt als `<Zufallszahl>.tmp` (vermutlich Test-Browser) | Heinz F10/F11, Julia F11 | stört (offen: Browser oder Programm) |
| B6 | Admin sieht nicht, welcher Richter wann was eingetragen hat | Julia F16 | Kleinigkeit/Wunsch |

### C. Tabelle am Handy und Tablet
| Nr | Fund | Quelle | Schwere |
|---|---|---|---|
| C1 | Tabelle breiter als der Bildschirm, viel Wischen, Disziplin-Überschrift verschwindet, Bogen-Knopf klein | Ruth F4, Dennis F5 | stört |
| C2 | Zeilen nach Art/LK statt nach Startnummer sortiert | Dennis F5 | stört |
| C3 | Hinweis „nicht gespeicherte Eingaben gehen verloren“ bei „Bogen“ schreckt ab; Wunsch: vorher fragen | Dennis F7 | Kleinigkeit/stört |
| C4 | Nach dem Filtern liegt die Zeile unter dem Falz | Ruth F8 | Kleinigkeit |

### D. Disqualifikation, Abbruch, Bogen
| Nr | Fund | Quelle | Schwere |
|---|---|---|---|
| D1 | **Disqualifikation nur in der Tabelle**, als Kästchen ganz rechts; auf der Einzelseite fehlt sie (so beschlossen, B18) | Dennis F1 (Note 4) | stört |
| D2 | Der Hinweistext spricht von „Grund“, eine Disqualifikation hat aber keinen Grund; Dennis suchte ihn vergeblich (der Text meint den Abbruch) | Dennis F2 | stört (Textfrage) |
| D3 | Abbruch-Auswahl: Antippen einer Option übernahm im Test nicht, Pfeiltaste ging (vermutlich Werkzeug, nicht nachgestellt); „Verletzung HF“ unerklärt; Erklärtext klein über dem Notizfeld | Ruth F5/F10, Dennis F8 | Kleinigkeit/offen |
| D4 | „Zu suchender Gegenstand: nicht hinterlegt“ im Bogenkopf unklar | Ruth F7 | Kleinigkeit |

### E. Desktop: Dialoge, Bericht, Notizen
| Nr | Fund | Quelle | Schwere |
|---|---|---|---|
| E1 | **Notizen kommen im Desktop nicht sichtbar an** (nur im PDF) und der Bericht erwähnt sie nicht (so beschlossen, B20) | Heinz F7, Julia F12 | stört |
| E2 | Frage nennt „12 Teilnehmer“, Bericht „9 aktualisiert“ (neue Zählung: nur wirklich Geänderte) – verunsichert; „0 Disziplin(en) im Web leer“ widerspricht sichtbar leeren Disziplinen bei Dreikämpfern | Julia F13, Heinz F8 | stört wenig |
| E3 | „gemerkter Termin [termin_1]“ (interne Kennung statt Name und Datum); langer, beunruhigender Satz zur Status-Rücknahme; „12 teilnehmende Teilnehmer“ | Heinz F9, Julia F14/F15/F7 | Kleinigkeit |
| E4 | Passwort wird beim Veröffentlichen und Zurückholen **erneut abgefragt**, auch wenn es im Dialog stand (Tresor im Test aus; offen, ob ohne Tresor die Sitzung das Passwort halten sollte) | Heinz F4/F13, Julia F8/F18 | stört wenig |
| E5 | Dialog „Web-Verbindung“ nahm nach einem Fehlgriff (Passwort im falschen Feld) keine Eingaben mehr an; nicht reproduziert, vermutlich Werkzeug | Julia F6, Heinz F5 | offen |

### F. Container und README
| Nr | Fund | Quelle | Schwere |
|---|---|---|---|
| F1 | README nennt nur Port 5443; `python -c …` passt nicht auf jedem Windows (kein Python im PATH) | Heinz F2, Julia F3/F4 | Kleinigkeit |
| F2 | Zertifikatswarnung: README sollte beschreiben, wie sie in gängigen Browsern aussieht und wie man sie bestätigt | Heinz F1 | stört wenig |
| F3 | Passwort- und Einrichtungs-Code-Felder ohne „Anzeigen“-Schalter (langer Code, Vertippen unsichtbar) | Julia F2 | Kleinigkeit |
| F4 | Aus dem Stack-Aufbau: Fingerabdruck erscheint nur ohne Umleitung; Skriptmeldung mit ae/ue statt Umlauten; Proxy erst nach etwa 30 s gesund; `podman-compose` meldet harmlose Ausgaben als roten Fehler in PowerShell 5.1 (siehe `Claude\UX-Test-Web\stack-notizen.md`) | Stack-Aufbau | Kleinigkeit |

### G. Sammel-PDF
| Nr | Fund | Quelle | Schwere |
|---|---|---|---|
| G1 | Dreikampf-Bögen ohne Eintragungen erzeugen leere Seiten (12 Seiten für 9 Teilnehmer) | Heinz F12 | Kleinigkeit |

## 4. Lob (alle Personas)
- „Gespeichert.“ samt Gesamtpunktzahl und Status direkt im Bogen; „Speichern und zurück zur Tabelle“ mit erhaltenem Filter; exakter Startnummer-Filter.
- Die rote Meldung bei vergessener Anzeige („Bitte Suche UND Anzeige eintragen …“) mit stehengebliebener Suche; Korrigieren (54 → 45) problemlos.
- Einzelseite je Person am Handy sauber; Bogen passt am Tablet ohne Zoomen.
- Ersteinrichtung führt gut, Rolle „Nur Eintragen“ vorbelegt; Dialogtexte der Web-Verbindung führen zum Ziel; die Rückfrage vor dem
  Zurückholen (mit automatischer Kopie) ist verständlich; der Rückhol-Bericht stimmte mit der Ergebniserfassung überein.
- Alle Eingaben waren nach Abmelden/Anmelden noch da (Vertrauen).

## 5. Vorschlag zur Besprechung
Nach Gewicht, je Punkt einzeln mit Marco (umsetzen / zurückstellen / verwerfen):
1. **A1, A2, B2/B3, C1/C2, D1/D2** (Wege, Rückmeldungen, Handy-Tabelle, Disqualifikation): größter Nutzen für den Prüfungstag.
2. **E1–E4** (Desktop-Texte und Bericht): kleine Textarbeit.
3. **B4, B5, D3, E5** zuerst nachstellen (unklar, ob Programm oder Test-Werkzeug), dann entscheiden.
4. **F1–F4, G1, Rest** als Kleinigkeiten bündeln.

## 6. Ablage
Dieser Bericht, die vier Einzelberichte in [personas/](personas/), die Aufgabenliste [aufgaben.md](aufgaben.md). Außerhalb des Repos
(nicht committen): `Claude\UX-Test-Web\` mit Test-Stack `shsux`, Steuerwerkzeug, Karten, Bildschirmfotos (zeigen teils lokale Pfade),
Zugangsdaten der Testrichter (erfunden) und `stack-notizen.md`. Aufräumen des Test-Stacks: Befehle in `stack-notizen.md`.
