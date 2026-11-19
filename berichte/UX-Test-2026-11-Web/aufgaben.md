# Aufgabenliste: abgespeckter UX-Test der Web-Entwicklungen (19.11.2026)

Mit Marco am 19.11.2026 abgestimmt. Arbeitsweise nach dem Skill `aufgaben-abarbeitung` (Loop), aber ohne
Commits: Es entstehen nur Berichte (`berichte/UX-Test-2026-11-Web/`) und ein Test-Stack außerhalb des Repos.
Alle Funde sind Beobachtungen und Vorschläge, keine Umsetzungen; jeder Punkt wird danach einzeln mit Marco
besprochen.

## Rahmen

- **Pause ab 07:55 Uhr (Marco):** Ab 07:55 keine Arbeit, keine neuen Agents, Loop mit `ScheduleWakeup(stop: true)`
  beenden. Marco startet den Loop danach wieder per Hand. Aufgabe, die bis 07:55 nicht fertig wird: nicht
  anfangen, sondern in der nächsten Runde (Status „offen“). Läuft etwas bei 07:55, fertig machen bzw. sauber
  auf „läuft“ festhalten (siehe Fortsetzungsnotiz unten).
- **Limit:** `~/.claude/shs-limit.json` ist veraltet (5. November, `rate_limits: null`), die Statuszeile liefert
  in der Desktop-App offenbar keine Werte. Deshalb: kleine Schritte, je Runde ein Agent, Meldung an Marco nach
  jeder Aufgabe. Schätzung S ≈ 15 %, M ≈ 20 %, L ≈ 30 % des 5-h-Fensters.
- **Test-Stack getrennt:** Ordner `C:\Users\mbruv\Documents\Claude\UX-Test-Web\` (außerhalb des Repos, nie
  committen), Compose-Projekt `shsux`, Ports 6443 (HTTPS) und 6432 (Datenbank), eigene Zugangsdaten und eigenes
  Image-Tag. Marcos laufender Stack (`shs-pruefungsprogramm-git_*`, Port 5443) bleibt unberührt und wird am Ende
  auf Unverändertheit geprüft.
- **Personas** entscheiden nur nach Bildschirm, Beschriftungen und Meldungen; Quellcode und Projektnotizen sind
  tabu (Container-Aufgabe: nur `README_CONTAINER.md` und Handbuch, wenn die Persona es hat).
- **Web** im eingebauten Browser (Handy 375 px, Tablet 768 px, Desktop). **Desktop** über ein neues
  Steuerwerkzeug (Qt offscreen, eigenes Profil, eigene Einstellungen, Windows-Tresor abgeschaltet), nur im
  Arbeitsordner, nicht im Repo.

## Szenario (6 Aufgaben)

1. Container einrichten (README_CONTAINER.md, Test-Stack real) und Web aufrufen (Zertifikatswarnung).
2. Admin im Web einrichten (Ersteinrichtung mit Code), zwei Richter-Konten anlegen.
3. Desktop: Web-Verbindung einrichten (Fingerabdruck abgleichen), Termin ins Web veröffentlichen.
4. Richter erfassen im Web: Gruppe A über den **Online-Bewertungsbogen** (Punkte, Notiz), Gruppe B **nur
   Punkte** (Tabelle bzw. Einzelseite).
5. Ergebnisse aus Web in die Desktop-Datei zurückholen, Bericht lesen.
6. Sammel-PDF „Benutzte Bögen als PDF“ herunterladen.

Bewertet wird die Übersichtlichkeit der Web-Oberfläche (Orientierung, Beschriftungen, Fehlermeldungen, Tabelle
gegen Bogen am Handy/Tablet), Verständlichkeit der Texte und Dialoge und Stolperstellen im README.

## Personas

| Kürzel | Persona | Rolle | Handbuch | Geräte |
|---|---|---|---|---|
| P1 | Heinz, 58, Prüfungsleiter | Admin, erfahren | ja | Desktop |
| P2 | Julia, 34, organisiert zum ersten Mal | Admin, normal | nein | Desktop |
| P3 | Richterin (erfahren) | Richterin „eintragen“ | nein | Tablet |
| P4 | Richter am Handy (Laie, klickt herum) | Richter „eintragen“ | nein | Handy |

Ablauf auf einem Stack: P1 Aufgaben 1–3 (legt zwei Richter-Konten an), P3 Aufgabe 4 Gruppe A (Bogen), P4
Aufgabe 4 Gruppe B (nur Punkte), P1 Aufgaben 5–6. Danach Stack zurücksetzen, P2 Aufgaben 1–3, 5–6 (die
Richtereintragungen werden für P2 per Skript eingespielt, damit P2 sich auf die Admin-Sicht konzentriert).

## Statustabelle

| Nr | Aufgabe | Größe | Status | Limit vorher → nachher | Bemerkung |
|---|---|---|---|---|---|
| T1 | Test-Stack bauen und Rauchtest (Ordner, Ports 6443/6432, Zugangsdaten, Image, Zertifikat) | L | erledigt (06:28) | Limit unbekannt | Ordner `Claude\UX-Test-Web\shsux`, Notizen `stack-notizen.md`; Rauchtest ok (58 s Build mit Cache, 202 MB), zurückgesetzt, Marcos Stack unverändert (geprüft) |
| T2 | Steuerwerkzeug für die Desktop-App (offscreen) bauen und Rauchtest (Web-Verbindung öffnen, Bild, Tabwechsel) | L | erledigt (06:44) | Limit unbekannt | `Claude\UX-Test-Web\steuer\` (steuer.py, README-steuer.md), Rauchtest mit Bildern ok; **Vorfall:** früher Lauf schrieb einmal `HKCU\Software\SHS-Pruefungsprogramm\Desktop\fenster` (QSettings.setDefaultFormat wirkt bei `QSettings(org, app)` nicht), sofort behoben und den Schlüssel wieder entfernt; danach Registry, Programmordner, Windows-Tresor (cmdkey) und Repo vorher/nachher unverändert (Beweise `steuer\beweise\`) |
| T3 | Testdaten (Demo-Termin-Datei, 12 erfundene Teilnehmer), Aufgabenkarten und Berichtsvorlage je Persona | M | erledigt (06:46) | Limit unbekannt | Karten in `Claude\UX-Test-Web\karten\` (00-regeln, P1–P4, berichtsvorlage), Termine in den Sandboxen `heinz`, `julia` |
| T4 | P1 Heinz: Aufgaben 1–3 | M | erledigt (07:04), Durchschnitt Teil 1: 2,0; Funde F1–F6 (Zertifikatswarnung, README-Port/Python im PATH, keine Erfolgsmeldung nach „Benutzer anlegen“, Passwort wird beim Veröffentlichen erneut abgefragt, OK mit leerem Passwort, Admin ohne Termin landet auf „Termin wählen“) | Warnung im Tab `seed` von Marco bestätigt; nur dieser Tab gilt, nie schließen; Zugänge in `uebergabe\zugaenge.md` | Limit unbekannt | Aufgabe 1 geschafft (Container laufen, `curl -k` 200). Der eingebaute Browser lehnt das selbstsignierte Zertifikat ab (ERR_CERT_AUTHORITY_INVALID), nur Marco kann im Browser-Pane einmal „Weiter“ wählen. Vorläufiger Bericht `personas/P1-Heinz.md` (F1, F2). Persona-Agent `a3f5ec5daa03f2917` mit SendMessage fortsetzen |
| T5 | P3 Richterin am Tablet: Aufgabe 4 Gruppe A (Bogen) | M | erledigt (07:13) | Limit unbekannt | Durchschnitt ca. 2,3; alle 4 Bögen eingetragen, nach Neuanmeldung da; Haupt-Funde: Bogen schwer zu finden (nur Knopf „Bogen“ in der Tabelle, Einzelseite wirkt wie „der“ Bogen), Höchstwert 84 → kaum sichtbare Fehlermeldung, Tabelle am Tablet breiter als der Bildschirm, Teilnehmerliste zeigt #7 „offen“/#10 „bewertet“ ohne Erklärung; Bericht `personas/P3-Ruth.md` |
| T6 | P4 Richter am Handy: Aufgabe 4 Gruppe B (nur Punkte) | M | erledigt (07:17) | Limit unbekannt | Durchschnitt 2,6; Punkte am Handy einfach; Haupt-Funde: Disqualifikation nur in der Tabelle ganz rechts, Einzelseite ohne Disqualifikation, kein „Grund“-Feld, trotz Hinweistext; keine Bestätigung nach Speichern auf der Einzelseite, Liste zeigt „bewertet“ statt „disqualifiziert“; Tabelle am Handy breit, Hinweis „Eingaben gehen verloren“ schreckt vom Bogen ab; Lob für die rote Meldung bei vergessener Anzeige; Bericht `personas/P4-Dennis.md`; im Tab `seed` ist Dennis angemeldet |
| T7 | P1 Heinz: Aufgaben 5–6 | S | erledigt (07:14) | Limit unbekannt | Teil 2 Durchschnitt 2,5, gesamt 2,3; Rückhol-Bericht stimmt; PDF-Download ohne sichtbare Rückmeldung, Datei als `<GUID>.tmp` im Download-Ordner (Werkzeug oder Programm? Header liefert den richtigen Namen, vermutlich Browser-Pane); PDF 12 Seiten mit Notizen; Funde F7–F13 (Notizen nicht im Desktop und nicht im Bericht erwähnt, „0 Disziplin(en) im Web leer“, „gemerkter Termin [termin_1]“ technisch, Passwort bei jeder Web-Aktion erneut, leere Seiten im PDF, Kopfzeile bricht um) |
| T8 | P2 Julia: Aufgaben 1–3, 5–6 (Stack zurückgesetzt) | M | Teil 1 erledigt (07:22, Durchschnitt 2,0, Funde F1–F9), Richterdaten eingespielt (07:25, `scratchpad\seed_richter.py`, wie Ruth und Dennis), Teil 2 läuft (07:26) | Limit unbekannt | Persona-Agent `adc83019faba852f3`; Stack zurückgesetzt mit `secrets\tls` behalten (Zertifikatsbestätigung im Tab `seed`) |
| T9 | Gesamtbericht, Aufräumen, Prüfung „Marcos Stack unverändert“, Fortschritt.md | M | erledigt (07:30) | Limit unbekannt | `Bericht.md`; Marcos Stack unverändert (alle drei Container „Up … healthy“, Port 5443); Test-Stack `shsux` läuft noch (zum Ansehen), Aufräumen: Befehle in `Claude\UX-Test-Web\stack-notizen.md`; Julia gesamt 2,3 (Teil 2: Funde F10–F18) |

## Fortsetzungsnotiz

(Hier trägt jede Runde den Stand ein, damit die nächste Runde nach der Pause nahtlos weitermacht.)

- 19.11.2026 06:25: Plan und Liste angelegt, noch nichts gestartet.
- 19.11.2026 06:55: T1 bis T3 erledigt, T4 blockiert. Der Test-Stack `shsux` LÄUFT (Port 6443, Container
  `shsux_db_1/_web_1/_proxy_1`, Einrichtungs-Code in `shsux\secrets\admin_setup_code.txt`). Marco muss einmal im
  Browser-Pane `https://localhost:6443` öffnen und die Zertifikatswarnung bestätigen. Danach: `navigate
  https://localhost:6443/` muss die Ersteinrichtung zeigen, dann den Persona-Agenten `a3f5ec5daa03f2917` per
  SendMessage mit „weiter mit Aufgabe 2 und 3, Warnung ist bestätigt“ fortsetzen. Reihenfolge danach: T5 Ruth,
  T6 Dennis, T7 Heinz Teil 2, T8 Julia (Stack vorher zurücksetzen: `podman-compose -p shsux down -v`, Secrets und
  `tls` neu), T9 Bericht. Marcos Stack (5443) nicht anfassen.
