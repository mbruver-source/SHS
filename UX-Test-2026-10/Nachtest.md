# UX-Nachtest vor dem Build 1.0.40 (03.10.2026)

Gezielter Nachtest mit zwei Personas, nachdem die Funde des ersten Tests ([Bericht.md](Bericht.md))
umgesetzt waren. Marco hatte am 03.10. entschieden: zwei Personas statt aller sechs.

## Methode

- Dieselbe Bedien-Harness und dasselbe Turnier-Szenario wie beim ersten Test. Die Harness ist an
  den aktuellen Programmstart angepasst: deutsche Qt-Texte, maximiert, Absturzprotokoll.
- **Werner (L-B2):** Laie, ohne Handbuch.
- **Julia (N-A2):** normale Nutzerin, mit Handbuch, ausdrücklich mit dem neuen Kapitel 14.
- Die Personas wussten nicht, was geändert wurde. Die damaligen Funde haben sie erst nach dem
  Test als Checkliste bewertet.
- Die Agents liefen diesmal auf Sonnet statt auf dem Modell des ersten Tests. Das ist beim
  Vergleich zu bedenken.
- Einzelberichte: [personas/L-B2.md](personas/L-B2.md), [personas/N-A2.md](personas/N-A2.md).

## Ergebnis auf einen Blick

| | Installation | Erststart | Termin-Ablauf | **Gesamt** | Allein am Prüfungstag? |
|---|---|---|---|---|---|
| Werner (L-B), 1. Test | 3 | 2 | 4 | **3–4** | Nein |
| **Werner (L-B2), Nachtest** | 2 | 2 | 2–3 | **2–3** | Eher nein* |
| Julia (N-A), 1. Test | 2 | 2 | 3 | **3+** | Eher ja |
| **Julia (N-A2), Nachtest** | 2 | 1–2 | 2 | **2** | **Ja**, mit Kapitel 14 |

\* Werners „Nein“ begründet sich vor allem mit dem PDF-Speicherfehler und den Programmabbrüchen.
Beides sind Effekte der Testumgebung (siehe unten). Ohne sie bewertet er den Ablauf als „jetzt
gut zu bewältigen“.

**Aufgabe × Persona** (✓ geschafft · ~ mit Mühe · ✗ allein nicht geschafft; vorher → nachher)

| Nr | Aufgabe | L-B → L-B2 | N-A → N-A2 |
|---|---|---|---|
| 0 | Installation (gedanklich) | ~ → ✓ | ✓ → ✓ |
| 1 | Termin anlegen | ✓ → ✓ | ✓ → ✓ |
| 2 | Anmeldeformular | ✓ → ~ (Testumgebung) | ✓ → ✓ |
| 3 | Nachmeldungen von Hand | ~ → ✓ | ~ → ✓ |
| 4 | Mitgliederliste (CSV) | ~ → ✓ | ✓ → ✓ |
| 5 | Anmelde-PDFs | ✓ → ✓ | ✓ → ~ (Absturz, Testumgebung) |
| 6 | Startnummern, Tausch, Absage | **✗** → ~ | ~ → ✓ |
| 7 | Zeitplan mit Pause | ~ → ✓ | ~ → ✓ |
| 8 | Ergebnisse, Disqualifikation | ~ → ✓ | ✓ → ✓ |
| 9 | Rangliste | ✓ → ✓ | ✓ → ✓ |
| 10 | PDFs | ✓ → ✓ | ✓ → ✓ |
| 11 | Datensicherung | ✓ → ✓ | ✓ → ✓ |
| 12 | Neustart, alles da? | ✓ → ✓ | ✓ → ✓ |

**Abgleich der damaligen Funde** (Bewertung der Personas):

- **Werner:** 10 behoben, 5 teilweise (U1, U5, U9, U14, K7), 1 nicht erlebt (K1), 0 nicht behoben.
- **Julia:** behoben sind U1–U4, U6–U13, K1, K7 und K9; teilweise U5 und U14; 0 nicht behoben.

„Teilweise“ heißt fast immer: Der Punkt ist behoben, aber es gibt einen kleinen Rest. Diese
Reste stehen unten als neue Funde.

## Effekte der Testumgebung (geprüft, kein Programmfehler)

- **„PDF konnte nicht erstellt werden … [Errno 2]“ (Werner):** Der Pfad in der Test-Sandbox war
  266 Zeichen lang, Windows erlaubt höchstens 260. Der vorgeschlagene Ordner wird angelegt. Im
  echten Profil ist derselbe Pfad etwa 119 Zeichen lang. Julia lief in einer Sandbox mit kurzem
  Pfad und hatte das Problem nicht.
- **Programmabbrüche (Werner 3×, Julia 1×):** Laut Absturzprotokoll passieren sie jeweils beim
  Aufräumen des Speichers („Garbage-collecting“), teils mitten im Code der Harness. Das ist
  dasselbe Muster wie beim ersten Test (P1). Marcos Gegenprobe in der echten App (03.10.) lief
  ohne Absturz. Das neue Absturzprotokoll hat seinen Zweck erfüllt: Die Ursache war sofort
  nachvollziehbar.

## Neue Funde (Marco 03.10.: alle für 1.0.40 freigegeben und umgesetzt, siehe Fortschritt.md)

| # | Fund | Wer | Schwere |
|---|---|---|---|
| N1 | Der CSV-Import erkennt keine Doppelten: Dieselbe Datei zweimal eingelesen ergibt alle doppelt, ohne Warnung. PDF- und OMA-Import überspringen bereits Vorhandene. Löschen geht nur einzeln. | L-B2 | erheblich |
| N2 | Bei zwei markierten Zeilen sind „Startnummer tauschen…“, „Bearbeiten…“ und „Löschen“ ohne Erklärung ausgegraut. Beide Personas markierten für den Tausch zuerst beide Teilnehmer. | beide | gering |
| N3 | Die Pause „bei allen Richtern um 12:00“ landet am Planende (z. B. 10:30), wenn der Plan vorher endet. Die Meldung sagt trotzdem „um 12:00 eingefügt“. | beide | gering |
| N4 | Texte: Die Rückfrage beim Anlegen nennt „Termin bearbeiten…“, der Knopf heißt aber „Veranstaltungsdaten bearbeiten…“ (Reiter „Verwaltung“). Kap. 14 schreibt „Dreikampf LK 1“, die Maske „DK-LK 1“. Kap. 14 erwähnt die Startnummern-Frage nach dem CSV-Import nicht. | N-A2 | gering |
| N5 | Die Import-Meldung wiederholt den Klammertext „Nur falls die Prüfung doch angeboten werden soll …“ in jeder Zeile und nennt „Zeile 8“ statt des Namens ([Bild](bilder/nachtest_01_csv_meldung.png)). | beide | kosmetisch |
| N6 | Der Hinweis „Nur ganze Punkte …“ bei „45,5“ wird leicht übersehen: Er steht kurz in der Statuszeile und im Tooltip, übernommen wird 45. | beide | gering |
| N7 | Restliche Fachwörter: „TN“ in „Offene Starts“, „.zip“, „SH-R“ (Etikett), „Meldestelle“. Das Glossar erklärt die meisten. | L-B2 | kosmetisch |

## Was gut lief (beide)

- Das Programm startet groß, die Teilnehmer-Maske ist vollständig lesbar, alle Knöpfe sind deutsch.
- Startnummern: Doppelklick öffnet die Maske, und nach dem Import kommt die Frage „Jetzt
  vergeben?“. Bei Julia waren die Nummern damit gleich nach dem Import vergeben.
- Der CSV-Import ist leicht zu finden und meldet nicht angebotene Prüfungen mit Grund.
- Zeitplan: Die Richter sind schon da, es gibt keine Überschneidungen, die Pause wird bei allen
  Richtern in einem Schritt eingefügt.
- Verständliche Meldungen: Punkte über 60/40, Datumsformat mit Beispiel, „Gespeichert unter …“
  mit „PDF öffnen“ und „Ordner zeigen“.
- Rangliste „1. von 4“ mit Hinweis bei offenen Startern.
- Kapitel 14 stimmt laut Julia in Reihenfolge und Beschriftung weitgehend mit dem Programm
  überein, und das Glossar hilft.
