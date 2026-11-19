# P2 – Julia: organisiert zum ersten Mal, Admin, ohne Handbuch  (UX-Test Web, 19.11.2026)

Stand: Teil 1 (Aufgaben 1 bis 3). Teil 2 (Aufgaben 5 und 6) folgt nach den Richter-Eintragungen.

## 1. Kurzfazit
Mit der README habe ich den Container und die Web-Seite zum Laufen gebracht, die zwei Richterkonten angelegt und
den Termin vom Desktop-Programm ins Web veröffentlicht. Alles hat am Ende geklappt, aber an zwei Stellen hätte ich
ohne die README-Schritte (Geheimnisse, Zertifikat) nicht gewusst, was zu tun ist. Die Oberfläche selbst führt gut:
Ersteinrichtung, Benutzerverwaltung und die Dialoge im Desktop sind verständlich. Am Prüfungstag würde ich das
allein hinbekommen, wenn die README-Anleitung vor mir liegt; ohne sie nicht.

## 2. Aufgaben im Überblick
| Aufgabe | geschafft (ja / teilweise / nein) | Aktionen ungefähr | Note (1-5) | Kernsatz |
|---|---|---|---|---|
| 1 Container einrichten und Web aufrufen | ja | ca. 15 | 2 | README ist vollständig, aber lang; der Weg „Geheimnisse, Zertifikat, up“ ist nur über Textstellen verteilt auffindbar. |
| 2 Admin einrichten, Konten ruth und dennis | ja | ca. 30 | 2 | Klar geführt; es fehlt eine sichtbare Bestätigung nach dem Anlegen. |
| 3 Desktop-Verbindung und Termin veröffentlichen | ja | ca. 45 (davon ca. 15 verloren, siehe F6) | 2 | Gute Dialogtexte, der Fingerabdruck-Vergleich ist verständlich; Passwort musste ich zweimal eingeben. |
| Gesamt | ja | ca. 90 | 2 | Machbar für Nicht-Profis mit README. |

## 3. Verlauf je Aufgabe
### Aufgabe 1: Container einrichten und Web aufrufen
- Erwartet: ein Befehl, danach läuft es. Die README sagt: erst Geheimnisse, dann Zertifikat, dann `podman-compose up -d`.
- Getan: README gelesen (lang, 345 Zeilen). Im Ordner `secrets\` lag schon `tls\`. Die drei Dateien mit den
  PowerShell-Befehlen der README erzeugt (dort steht `python`; auf meinem Rechner heißt es nicht überall so, ich
  habe meinen vollständigen Python-Pfad genommen). `tools\zertifikat_erzeugen.ps1` laufen lassen: Meldung
  „Es gibt bereits ein Zertifikat - es wird NICHT ueberschrieben (mit -Erneuern ersetzen).“ und der Fingerabdruck
  (hier gut: die Meldung zeigt ihn trotzdem an). `.env` aus `.env.example` kopiert (optional), `podman-compose up -d`.
  Das Bauen/Starten dauerte etwa eine Minute; danach alle drei Dienste „healthy“.
- Gestutzt: Die README nennt überall Port 5443; ich musste an den Hinweis denken, dass mein Port 6443 ist (die
  `compose.yaml` hatte das schon). Ein Zettel „im Browser: Adresse und Port“ fehlt am Ende der Einrichtung.
- Browser: `https://localhost:6443/` zeigte sofort die Ersteinrichtung (Bild des Tabs). Die Zertifikatswarnung
  war im Tab schon bestätigt, ich kann nicht beurteilen, wie verständlich sie ist (nicht bewertbar).
- Nicht verstanden: Die README erwähnt `Fortschritt.md` und `Architektur.md`; für mich als Vereinsmitglied
  unbekannte Dateien (Kleinigkeit).
- Gut: Das Skript sagt, was es tut und was es nicht überschreibt, und zeigt den Fingerabdruck an.

### Aufgabe 2: Administrator einrichten, Richterkonten
- Erwartet: ein Formular, in dem ich mich als Administrator anlege.
- Getan: Ersteinrichtung mit Einrichtungs-Code aus `secrets\admin_setup_code.txt` (Text auf der Seite nannte die
  Datei, hilfreich), Benutzername `julia`, Passwort zweimal. Danach Seite „Termin wählen“ mit dem Hinweis, dass
  noch kein Termin veröffentlicht ist. Oben „Termine | Benutzer | Abmelden (julia)“. „Benutzer“ → „Benutzer
  verwalten“: Benutzername, Passwort, wiederholen, Rolle (schon auf „Nur Eintragen (Ergebnisse erfassen)“
  vorbelegt). ruth und dennis angelegt. Zettel in `uebergabe\zugaenge-julia.md`.
- Gestutzt: Nach „Benutzer anlegen“ wird das Formular leer, oben steht keine Meldung wie „ruth wurde angelegt“.
  Ich musste nach unten scrollen, um die Liste zu sehen (Bildschirmfoto im Browser, nicht abgelegt). Beim ersten
  Konto war ich einen Moment unsicher, ob es geklappt hat.
- Gestutzt: Der Einrichtungs-Code und die Passwortfelder zeigen nur Punkte; beim Tippen eines langen, zufälligen
  Codes sehe ich nicht, ob ich mich vertippt habe (keine „Anzeigen“-Option).
- Nicht verstanden: Nichts Wörtliches. „Termin wählen … Aktuell ist kein Termin veröffentlicht … (alternativ per
  `sync_termin.py export`, siehe README_CONTAINER.md)“ ist für mich als Vereinsfrau Fachsprache.
- Gut: Rolle schon richtig vorbelegt; Liste mit Rollen unter dem Formular; „Löschen“ je Zeile klar beschriftet.

### Aufgabe 3: Desktop verbinden und veröffentlichen
- Erwartet: irgendwo „Web“ im Menü.
- Getan: Programm gestartet (Termin direkt geöffnet; über das Werkzeug mit `--termin`, nicht über „Anderen Termin
  öffnen…“). Ich schaute zuerst auf „Ergebniserfassung“ (ein Reiter, der nach Web klingt, ist aber die lokale
  Tabelle), dann auf „Datensicherung“: dort die Gruppe „Web-Version“ mit „Ins Web veröffentlichen…“,
  „Ergebnisse aus Web holen…“, „Web-Verbindung…“ (Bild `sandbox\julia\bilder\0002_ds.png`). Klick auf
  „Ins Web veröffentlichen…“ → Meldung „Für die Web-Version fehlen noch Adresse, Benutzername und der bestätigte
  Fingerabdruck des Servers. Sie werden jetzt abgefragt.“ → Dialog „Web-Verbindung“ (`0004_verb1.png`).
  Adresse `https://localhost:6443`, Benutzername `julia`, Passwort. „Fingerabdruck vom Server holen…“ → Frage
  „Fingerabdruck bestätigen“ mit vier Zeilen; ich habe sie mit dem Ausdruck des README-Skripts (und der Datei
  `secrets\tls\fingerabdruck.txt`) verglichen: gleich, „Ja“. „Verbindung testen“ → „Verbindung in Ordnung. Auf dem
  Server liegen 0 Termin(e).“ OK. Wieder „Ins Web veröffentlichen…“ → Frage mit Zusammenfassung (12 Teilnehmer,
  „Diese Termin-Datei bleibt unverändert“) → „Ja“ → Passwortabfrage → „Der Termin ist veröffentlicht
  (12 Teilnehmer). Die Richter können jetzt im Web Ergebnisse erfassen.“ Im Web unter „Termine“ steht der Termin
  mit „12 Teilnehmer · termin_1“.
- Gestutzt: (a) Ich habe das Passwort in den Dialog getippt, danach beim Veröffentlichen noch einmal in einem
  weiteren Fenster („Passwort für die Web-Version“) – „Passwort merken“ ist ausgegraut (das gehört zur
  Testumgebung, in der Praxis wäre es wohl anders). (b) Einmal landete mein Passwort aus Versehen im Feld
  „Benutzername“ (Fehlklick auf „Passwort merken“); ich merkte es, weil dort „juliaMuster…“ stand. Danach nahmen
  die Felder des Dialogs keine Eingaben mehr an (Tippen, Strg+A, Klick auf Feld ohne Wirkung); ich musste „Abbrechen“
  wählen und den Dialog neu öffnen – alles neu eingeben, Fingerabdruck erneut holen. Ich weiß nicht, ob das ein
  Programmfehler oder eine Eigenheit des Prüfwerkzeugs ist (Funde F5/F6; Verlust ca. 15 Aktionen).
- Nicht verstanden (wörtlich): „Übertragen werden die Veranstaltungsdaten und 12 teilnehmende Teilnehmer samt
  bereits eingetragener Ergebnisse.“ – „teilnehmende Teilnehmer“ klingt doppelt. „Fingerabdruck des
  Serverzertifikats (SHA-256)“ – SHA-256 sagt mir nichts, ich habe es ignoriert.
- Gut: Dass das Programm von sich aus sagt, was fehlt, und den Dialog öffnet. Der Fingerabdruck wird mit
  Hinweis „Vergleiche den Fingerabdruck mit dem, den dir der Betreiber des Servers nennt“ erklärt und in
  vier Gruppen zu je 8 Bytes gesetzt, das ließ sich gut vergleichen. Die Erfolgsmeldung nennt das nächste.

## 4. Übersichtlichkeit der Web-Oberfläche (Desktop-Breite, Fenster etwa 800 px breit)
- Orientierung: Note 2. Oben Navigation „Termine | Benutzer | Abmelden (julia)“, mein Name steht daneben, das
  hilft. Es gibt keine Brotkrumen; „zurück“ geht über die Leiste. Die Seite „Termin wählen“ als erste Seite nach
  Ersteinrichtung ist logisch.
- Beschriftungen: Note 2. „Ersteinrichtung“, „Benutzer verwalten“, „Termin veröffentlichen“ verständlich. „Nur
  Eintragen (Ergebnisse erfassen)“ sehr gut erklärt. Der Begriff „Termin“ für die ganze Prüfung ist mir
  fremd, aber das Programm bleibt konsequent dabei.
- Lesbarkeit/Bedienbarkeit: Note 2. Große Schrift, große Felder, braune Knöpfe gut erkennbar. Das Fenster ist
  schmal (etwa 800 px), die Seite ist einspaltig; man scrollt viel. Nicht getestet: Handy/Tablet.
- Rückmeldungen: Note 3. Nach „Benutzer anlegen“ keine Bestätigung oben (F1); bei der Ersteinrichtung gibt es die
  Abmelden-Leiste als Erfolgszeichen, das reicht dort.
- Vertrauen: Note 2. Die Verbindung ist https, die Seite führt mich durch die Schritte; ob der Termin online
  ist, sehe ich unter „Termine“ klar.

## 5. Texte der Dialoge und Meldungen (Desktop)
Note 2. Sehr hilfreich: „Für die Web-Version fehlen noch Adresse, Benutzername und der bestätigte Fingerabdruck
des Servers. Sie werden jetzt abgefragt.“ / „Verbindung in Ordnung. Auf dem Server liegen 0 Termin(e).“ /
„Der Termin ist veröffentlicht (12 Teilnehmer). Die Richter können jetzt im Web Ergebnisse erfassen.“
Weniger gut: „teilnehmende Teilnehmer“, „SHA-256“-Fachwort, der kleine Dialog „Web-Verbindung“ hat viel leere
Fläche unten.

## 6. Funde
F1 Nach „Benutzer anlegen“ fehlt eine sichtbare Meldung („ruth wurde angelegt“); man sieht den Erfolg nur in der
Liste unten, die man erst suchen muss – Web, Benutzer verwalten – stört (Kleinigkeit-mittel) – Wunsch: Meldung
oben, Liste direkt sichtbar.
F2 Passwort- und Einrichtungs-Code-Felder ohne „Anzeigen“-Schalter; langer Zufallscode, Vertippen unsichtbar – Web
Ersteinrichtung – Kleinigkeit – Wunsch: Auge-Symbol.
F3 README nennt Port 5443; dass man bei abweichendem Port auch im Zertifikatsschritt nichts ändern muss, steht
nirgends – README_CONTAINER – Kleinigkeit.
F4 README: Anweisung „python -c …“ passt nicht auf jedem Windows-Rechner (python nicht im PATH); die Skripte
sollten Alternativen nennen – README Geheimnisse – stört.
F5 Datensicherung-Dialog „Web-Verbindung“: Hinweis „Passwort merken“ ausgegraut ohne Erklärung, warum – Desktop –
Kleinigkeit (Testumgebung).
F6 Nach einem Fehlgriff (Passwort im Feld „Benutzername“) reagierten die Eingabefelder im Dialog „Web-Verbindung“
auf keine Eingabe mehr; nur „Abbrechen“ und Neuöffnen half – Desktop – stört (kann auch am Prüfwerkzeug liegen,
nicht reproduziert).
F7 „teilnehmende Teilnehmer“ in der Frage „Ins Web veröffentlichen“ – Desktop – Kleinigkeit.
F8 Das Passwort muss beim Veröffentlichen ein zweites Mal eingegeben werden – Desktop – Kleinigkeit (hängt am
deaktivierten Tresor der Testumgebung).
F9 „Web“ findet man nicht auf dem Startbildschirm; es steckt im Reiter „Datensicherung“ (und nicht bei „Ergebnis­-
erfassung“). Ich habe zwei Reiter probiert, bis ich es fand – Desktop – Kleinigkeit-mittel – Wunsch: Hinweis im
Reiter Ergebniserfassung oder eigener Reiter „Web“.

## 7. Lob
- Der Dialog führt mich selbstständig zum Ziel („Sie werden jetzt abgefragt“).
- Der Fingerabdruck-Vergleich ist verständlich erklärt.
- Die Benutzer-Rolle ist schon richtig vorbelegt.
- „Verbindung testen“ mit Termin-Anzahl gibt Sicherheit, dass der Server der richtige ist.
- Die Erfolgsmeldung nach dem Veröffentlichen sagt klar, was jetzt geht.

---

# TEIL 2 (Aufgaben 5 und 6)

## T2.1 Kurzfazit
Das Zurückholen hat geklappt und die Meldungen sind ausführlich, nur teilweise schwer zu lesen. Dass die
Richter etwas eingetragen haben, sehe ich in beiden Programmen; was sie dazu notiert haben, sehe ich nur im
PDF, nicht im Desktop. Den Weg zu den Bögen im Web fand ich nur über die Ergebnistabelle; ob der Download
angekommen ist, zeigte mir der Browser nicht an. Am Prüfungstag allein schaffe ich das, würde aber bei „9 von
12“ nachfragen.

## T2.2 Aufgaben im Überblick (Teil 2)
| Aufgabe | geschafft | Aktionen ungefähr | Note (1-5) | Kernsatz |
|---|---|---|---|---|
| 5 Ergebnisse zurückholen, Bericht verstehen | ja | ca. 15 | 2 | Meldungen genau, aber „12 Teilnehmer“ und „9 aktualisiert“ passen für mich nicht zusammen; Notizen fehlen im Desktop. |
| 6 Benutzte Bögen als PDF laden | ja (Download unsichtbar) | ca. 12 | 3 | Der Knopf ist gut erklärt, aber nach dem Klick passiert vor meinen Augen nichts. |
| Web-Übersicht Admin (Termine, Ergebnistabelle) | teilweise | ca. 10 | 3 | Ich sehe Zahlen, aber nicht „wer hat was wann eingetragen“. |

Gesamtnote P2 (Teil 1 + Teil 2): Aufgaben 2, 2, 2, 2, 3, Web-Admin 3 -> **2,3, gerundet 2** (Notendurchschnitt 2,33).

## T2.3 Verlauf je Aufgabe
### Aufgabe 5: Ergebnisse aus dem Web holen
- Erwartet: ein Knopf „Ergebnisse holen“, danach sind die Werte in meiner Tabelle.
- Getan: Programm gestartet, Reiter „Datensicherung“ -> „Ergebnisse aus Web holen…“ (Bild
  `sandbox\julia\bilder\0014_h1.png`). Passwortabfrage „Passwort für „julia“ auf https://localhost:6443:“
  (zum zweiten Mal; Passwort wird nicht gemerkt). Dann die Frage (Bild `0014/0015`):
  „Ergebnisse von 12 Teilnehmern aus dem Web-Termin „gemerkter Termin [termin_1]“ in „Musterverein, Musterstadt,
  2026-12-05“ übernehmen? … Die Ergebnisse in dieser Termin-Datei werden mit dem Stand aus dem Web überschrieben
  (zugeordnet über die Startnummer). Disqualifikation und Abbruch werden übernommen: Der Web-Stand ersetzt die
  Werte der Datei, auch ein hier gesetzter Status wird dabei zurückgenommen, wenn er im Web nicht gesetzt ist.
  Vorher legt das Programm eine automatische Kopie an.“ -> „Ja“.
  Ergebnisfenster „Ergebnisse aus dem Web übernommen“ (`0015_h2.png`): „9 Teilnehmer aktualisiert. 0 nicht
  übernommen (anderer Teilnehmer unter derselben Startnummer), 0 Startnummer(n) in dieser Datei nicht gefunden,
  0 ohne Startnummer übersprungen, 2 Status (Disqualifikation/Abbruch) geändert, 0 Disziplin(en) im Web leer
  (Wert dieser Datei blieb), 0 Fehler.“ und darunter „Nr. 6 Demo, Frank: ohne Status -> disqualifiziert“,
  „Nr. 10 Probe, Jens: ohne Status -> Abbruch (Krankheit)“ sowie ein Hinweis, dass der Web-Stand die Werte der Datei
  ersetzt. Dann Reiter „Ergebniserfassung“ (`0016_erg.png`): Nr. 1 bis 5 mit Werten, Nr. 6 „disqualifiziert“ (Haken),
  Nr. 7 nur Trümmerfeld 52/34, Nr. 10 Trümmerfeld 25/10 mit „Abbruch: Krankheit“, Nr. 12 zwei Disziplinen,
  Nr. 8, 9 und 11 „noch kein Ergebnis“; alle anderen „gespeichert“.
- Plausibilität: Neun Zeilen mit Werten (die Zahl 9 stimmt mit den Zeilen überein), Disqualifikation und Abbruch
  sind sichtbar und passen zu den „2 Status geändert“. Warum Nr. 7 und Nr. 12 nur einen Teil der Disziplinen haben
  und 8, 9, 11 gar nichts, kann ich nicht erklären: Wurden sie nicht geprüft, hat jemand vergessen zu speichern?
  Ich kenne die Zettel nicht. Die Notizen der Richter (die ich nur im PDF fand) stehen im Desktop nirgends; ich
  habe sie beim Durchsehen der Ergebnistabelle vermisst, besonders bei der Disqualifikation Nr. 6 (kein Grund
  erkennbar).
- Gestutzt: „Ergebnisse von 12 Teilnehmern … übernehmen“ und dann „9 Teilnehmer aktualisiert“ - ich dachte, es sei
  etwas verloren gegangen, bis ich die leeren Zeilen sah. Der Satz „Disqualifikation und Abbruch werden übernommen:
  Der Web-Stand ersetzt die Werte der Datei, auch ein hier gesetzter Status wird dabei zurückgenommen“ ist lang und
  trifft mich als Verantwortliche mit Sorge („wird zurückgenommen?“). Ebenso „gemerkter Termin [termin_1]“ - was ist
  ein gemerkter Termin?
- Gut: Bericht nennt jede Zahl einzeln, auch die Nullen, und führt die Statusänderungen namentlich auf; vorher wird
  eine automatische Kopie angekündigt.

### Aufgabe 6: Benutzte Bewertungsbögen als PDF aus dem Web
- Erwartet: ein Knopf in der Nähe der Ergebnisse.
- Getan: Im Tab seed „Termine“ (Admin-Seite: Termin veröffentlichen, Ergebnisse zurückholen, Löschen), dort aber
  keine Ergebnisse und kein Bogen. Titel/Logo klicken tat nichts. Adresse `/` zeigte „Anmelden“, obwohl oben
  „Abmelden (julia)“ stand (F10). Über `https://localhost:6443/termin-waehlen` (die Adresse kannte ich aus der
  Ersteinrichtung) kam ich zur Navigation „Teilnehmer | Ergebnistabelle | Termin wechseln | Termine | Benutzer |
  Abmelden (julia)“. „Ergebnistabelle“ -> Kasten „Benutzte Bögen als PDF - Lädt alle Bewertungsbögen mit
  Eintragungen (Punkte, Disqualifikation, Abbruch oder Notiz) zum Speichern oder Ausdrucken herunter. Nicht
  gespeicherte Eingaben der Tabelle sind nicht enthalten: erst „Alle speichern“.“ Geklickt.
- Download: Im Browserfenster sah ich keine Reaktion (kein Download-Hinweis, keine Leiste, Seite unverändert). Ich
  wusste nicht, ob es geklappt hat. (Werkzeug-Befund: im Download-Ordner des Rechners lag danach eine Datei
  mit zufälligem Namen und Endung `.tmp`, 80 kB, Zeit passt zum Klick; ich habe sie dort als PDF mit 12 Seiten
  gelesen. Echte Nutzer sehen den Dateinamen im Browser; hier nicht beurteilbar.)
- PDF-Inhalt (Textauszug): „Bewertungsbogen SHS – Spürhundsport“, je Disziplin eine Seite mit Start-Nr., Name,
  Hund, Punkten (Suche/Anzeige), Gesamtpunktzahl und Wertungsnoten. Seite 1: Nr. 1 Trümmerfeld 55/36 = 91, „Notiz:
  Gegenstand in der Ecke gefunden“; Seite 6: Nr. 6 „Disqualifiziert (DISQ)“; Seite 7: Nr. 7 „Notiz: Hund zeigt spät
  an“; Seite 10: Nr. 10 „Abbruch wegen Krankheit“. 12 Seiten für 9 Teilnehmer (Doppelseiten bei Nr. 7, 10, 12),
  die Notizen sind hier lesbar - das hatte ich im Desktop vermisst. Layout nicht visuell geprüft (nur Textauszug).
- Gestutzt: Ich weiß nicht, ob „alle benutzten Bögen“ wirklich alle sind: Nr. 8, 9, 11 fehlen zu Recht, aber dass Nr. 7
  nur eine Disziplin hat, bleibt unklar.
- Gut: Der Kasten sagt, was enthalten ist, und dass vorher gespeichert werden muss.

## T2.4 Übersichtlichkeit der Web-Oberfläche aus Admin-Sicht (Fenster etwa 800 px, Desktop-Voreinstellung)
- Orientierung: Note 3. Im Zusammenhang mit meinem Wunsch, die Ergebnisse zu sehen, brauchte ich mehrere Versuche:
  „Termine“ führt nur zur Verwaltung, die Ergebnistabelle erreiche ich über „Termin wählen“ bzw. die Navigation
  nach Termin-Wahl. Die Navigation selbst ist ab dann gut (zwei Zeilen, klare Wörter).
- Beschriftungen: Note 2. „Ergebnistabelle“, „Bogen“, „Disqualifiziert“, „Abbruch“, Status „bewertet“ /
  „noch kein Ergebnis“ sind verständlich. „Alle speichern“ plus der lange Hinweistext ist ausführlich, aber
  beruhigend.
- Lesbarkeit: Note 3. Die Tabelle ist am schmalen Fenster breiter als der Bildschirm und muss seitlich geschoben
  werden; Spalten „Disqualifiziert“, „Abbruch“ und Status sieht man erst nach dem Schieben (`Bilder im Browser`),
  Sortierung nach Disziplin gruppiert (DK-Teilnehmer erscheinen zuerst: #7, #8, #11, #9, #10).
- Rückmeldungen: Note 3. Kein „wer hat das eingetragen“, keine Uhrzeit, kein Hinweis auf zuletzt geänderte
  Zeilen; als Admin sehe ich nur den aktuellen Stand, nicht welcher Richter was geändert hat. Beim Download-Knopf
  keine sichtbare Rückmeldung (F11).
- Vertrauen: Note 3. Der Stand ist da, aber ich kann ihn nicht ohne Weiteres mit dem Desktop vergleichen; die
  automatische Kopie vor dem Zurückholen gibt Sicherheit.

## T2.5 Texte der Dialoge und Meldungen (Desktop, Teil 2)
Note 3. Sehr genau („0 Disziplin(en) im Web leer (Wert dieser Datei blieb)“), aber mit viel Fachsprache und
Klammer-Pluralen („Termin(e)“, „Startnummer(n)“, „Disziplin(en)“); der Satz zum Status-Zurücknehmen ist schwer
verständlich.

## T2.6 Funde (Fortsetzung)
F10 Startseite `/` zeigt „Anmelden“, obwohl oben „Abmelden (julia)“ steht und ich angemeldet bin – Web – stört
(verwirrt, man glaubt, abgemeldet zu sein) – Wunsch: bei bestehender Anmeldung gleich zur Termin-/Teilnehmerseite.
F11 „Benutzte Bögen als PDF“: nach dem Klick keine sichtbare Rückmeldung im Browser (kein Hinweis „Datei wird
geladen“/Dateiname); im Download-Ordner liegt die Datei unter zufälligem Namen mit Endung `.tmp` – Web (der
Dateiname kann Eigenheit des Prüfbrowsers sein, nicht prüfbar) – stört – Wunsch: sprechender Dateiname, z. B.
`Bewertungsboegen_2026-12-05.pdf`.
F12 Notizen der Richter erscheinen im Desktop nirgends (nur im PDF), auch nicht bei Disqualifikation – Desktop,
Ergebniserfassung – stört – Wunsch: Notiz sichtbar (Tooltip/Spalte), zumindest bei Disqualifikation/Abbruch.
F13 Meldung vor dem Zurückholen: „Ergebnisse von 12 Teilnehmern … übernehmen?“ aber danach „9 Teilnehmer
aktualisiert“ – Desktop – stört (macht unsicher) – Wunsch: „9 von 12 Teilnehmern haben Ergebnisse; 3 noch ohne“.
F14 „gemerkter Termin [termin_1]“ in der Zurückholen-Frage ist unverständlich – Desktop – Kleinigkeit.
F15 Satz zur Status-Rücknahme („auch ein hier gesetzter Status wird dabei zurückgenommen“) lang und
beunruhigend – Desktop – Kleinigkeit – Wunsch: kürzer, mit Beispiel.
F16 Als Admin ist nicht erkennbar, welcher Richter was eingetragen hat und wann – Web Ergebnistabelle –
Kleinigkeit-mittel – Wunsch: „zuletzt geändert von … um …“.
F17 „Termine“ in der Navigation führt zur Verwaltung, nicht zur Terminübersicht mit den Ergebnissen; der Weg
zur Ergebnistabelle ist für Admins nicht naheliegend – Web – Kleinigkeit-mittel.
F18 Passwort musste auch beim Zurückholen wieder getippt werden (wie F8) – Kleinigkeit (Testumgebung).

## T2.7 Lob (Teil 2)
- Genaue Zahlen im Bericht, auch Nullen, und die Statusänderungen mit Namen.
- Automatische Kopie vor dem Überschreiben ist angekündigt.
- Der PDF-Kasten sagt, was enthalten ist und was man vorher tun muss.
- Das PDF enthält die Notizen und sieht nach Auszug vollständig aus (12 Seiten für 9 Teilnehmer).
