# P1 – Heinz: Prüfungsleiter, Einrichtung der Web-Version (UX-Test Web, 19.11.2026) – TEIL 1

## 1. Kurzfazit
Mit README und Handbuch habe ich es geschafft: Server läuft, Administrator und zwei Richterkonten sind angelegt, der Termin ist im Web. Am Prüfungstag allein hinbekäme ich das, aber die Zertifikatswarnung und das Passwort-Spiel im Desktop-Dialog haben mich unnötig Nerven gekostet. Die Web-Oberfläche selbst war als Admin klar und aufgeräumt.

## 2. Aufgaben im Überblick
| Aufgabe | geschafft | Aktionen ungefähr | Note | Kernsatz |
|---|---|---|---|---|
| 1 Container einrichten | ja (mit Hürde Zertifikat) | ca. 15 | 2 | README gut; Warnung im Test-Browser nicht selbst bestätigbar. |
| 2 Im Web einrichten | ja | ca. 25 | 2 | Klar, aber keine Bestätigung nach "Benutzer anlegen". |
| 3 Termin veröffentlichen | ja | ca. 40 (Werkzeug-bedingt viele) | 2 | Fingerabdruck-Abgleich verständlich; Passwort wird doppelt verlangt. |

Durchschnitt: 2,0 (Gesamtnote Teil 1: 2).

## 3. Verlauf je Aufgabe
### Aufgabe 1: Container einrichten
- Getan: drei Secret-Dateien nach den PowerShell-Befehlen der README angelegt, `tools\zertifikat_erzeugen.ps1` ausgeführt (Fingerabdruck 03:7E:1B:96:...:9C:9D:EE, auch in `secrets\tls\fingerabdruck.txt`), `podman-compose up -d`; nach unter einer Minute alle drei Container "healthy".
- Gestutzt: Im Browser erschien zuerst nur ERR_CERT_AUTHORITY_INVALID, ohne Knopf zum Fortfahren. Die Warnung ließ sich im Test-Browser nicht selbst bestätigen; in einem normalen Browser wäre es "Erweitert" und "Weiter". Erst nachdem sie jemand im Browser bestätigt hatte, ging die Seite auf (Bildschirmfoto: Ersteinrichtung mit dem Beagle-Kopf, Desktop-Breite des Panes ca. 800 px).
- Unklar: README nennt nur Port 5443 (Hinweis des Testleiters: 6443); die Python-Befehle setzen Python im PATH voraus.
- Gut: Reihenfolge, fertige Befehle, verständliche Ausgabe des Zertifikat-Skripts.

### Aufgabe 2: Im Web einrichten
- Ersteinrichtung: Einrichtungs-Code aus `secrets\admin_setup_code.txt` gelesen (wie in der README), eingetragen, Benutzername heinz, Passwort zweimal. Seite "Termin wählen" erschien; oben stehen "Termine", "Benutzer", "Abmelden (heinz)".
- Unter "Benutzer" ruth und dennis angelegt (Rolle stand schon auf "Nur Eintragen (Ergebnisse erfassen)"). Nach "Benutzer anlegen" wurde das Formular leer, eine Erfolgsmeldung habe ich nicht gesehen; erst beim Herunterscrollen sah ich die Liste mit dennis, heinz (Administrator), ruth. Kurz dachte ich, es sei nichts passiert.
- Zugänge nach `uebergabe\zugaenge.md` geschrieben (Zettel-Stil).
- Passwörter sind im Formular nicht einsehbar (nur Punkte), dafür gibt es das zweite Feld; gut.
- Gut: Ersteinrichtungs-Text erklärt den Code mit Dateiname.

### Aufgabe 3: Termin veröffentlichen
- Desktop (Sandbox heinz, Termin direkt per Start geöffnet), Reiter "Datensicherung", Gruppe "Web-Version" mit "Ins Web veröffentlichen…", "Ergebnisse aus Web holen…", "Web-Verbindung…" (Bild: sandbox\heinz\bilder\0002_ds.png). Das Handbuch nannte genau diese Namen, das fand ich gleich.
- "Web-Verbindung…": Adresse, Benutzername, Passwort; "Fingerabdruck vom Server holen…" zeigte vier Zeilen Fingerabdruck, die ich mit der Ausgabe des Zertifikat-Skripts abgleichen konnte (stimmte), mit "Diesem Server vertrauen? Ja/Nein". Danach "Fingerabdruck bestätigt. Mit „OK“ speichern." "Verbindung testen": "Verbindung in Ordnung. Auf dem Server liegen 0 Termin(e)."
- Ich habe zunächst durch Fehlbedienung (Werkzeug) das Passwort in das Benutzernamen-Feld getippt ("heinz" plus das Passwort); das Programm ließ OK im Dialog ohne Hinweis zu, die Eingaben im Dialog waren danach nicht mehr änderbar, bis ich ihn schloss und neu öffnete. Das ist wahrscheinlich ein Werkzeug-Effekt, ich vermerke es nur.
- "Ins Web veröffentlichen…": Frage mit Terminname, 12 Teilnehmer; danach nochmals "Passwort für die Web-Version" (obwohl ich es schon im Dialog eingegeben hatte, "Passwort merken" war deaktiviert); dann "Der Termin ist veröffentlicht (12 Teilnehmer). Die Richter können jetzt im Web Ergebnisse erfassen."
- Browser: Seite "Termine" zeigt "Musterverein, Musterstadt, 05.12.2026 · 12 Teilnehmer · termin_1".

## 4. Übersichtlichkeit der Web-Oberfläche (Desktop, Admin)
- Orientierung: Note 2. Drei Links oben (Termine, Benutzer, Abmelden mit Namen) sind klar. "Termin wählen" nach dem Login ist für den Admin ohne Termin eine Sackgasse mit Hinweistext.
- Beschriftungen: Note 2. "Nur Eintragen (Ergebnisse erfassen)" und "Administrator" verständlich. Der Hinweis unter dem Upload nennt `%USERPROFILE%\SHS-Pruefungsprogramm\Termine`, der in meiner Sandbox nicht stimmt (nur Testumgebung).
- Lesbarkeit: Note 1-2, große Schrift, große Felder und Knöpfe.
- Rückmeldungen: Note 3. Keine sichtbare Bestätigung nach dem Anlegen eines Benutzers; "Löschen"-Knöpfe direkt neben jedem Benutzer (nicht ausprobiert, ob nachgefragt wird).
- Vertrauen: Note 2 für die Termine-Liste, die den Termin samt Teilnehmerzahl zeigt.

## 5. Texte der Dialoge und Meldungen (Desktop)
Note 2. Die Frage "Diesem Server vertrauen?" erklärt den Vergleich gut. "Zugangsdaten fehlen: Bitte Benutzername und Passwort eingeben." war verständlich. Der Text "Das Passwort wird bei jeder Verbindung eingegeben" war nicht erklärt: "Passwort merken" ist grau und der Grund nicht ersichtlich (Tooltip nicht gesucht).

## 6. Funde
F1 Zertifikatswarnung im Test-Browser nicht selbst bestätigbar – Aufgabe 1 – Blocker für den Test (Werkzeug) – In einem normalen Browser wäre es "Erweitert", "Weiter". Wunsch: README sollte beschreiben, wie die Warnung der gängigen Browser aussieht.
F2 README nennt nur Port 5443 und setzt Python im PATH voraus – Aufgabe 1 – Kleinigkeit – Wunsch: Hinweis auf Portänderung, Variante ohne Python.
F3 Keine sichtbare Erfolgsmeldung nach "Benutzer anlegen" – Aufgabe 2 – stört wenig – Wunsch: grüne Meldung "Benutzer ruth angelegt" oben, Liste direkt sichtbar.
F4 Passwort wird beim Veröffentlichen erneut abgefragt, obwohl es im Verbindungsdialog schon stand – Aufgabe 3 – stört wenig – Wunsch: Passwort aus dem Dialog für die Sitzung verwenden oder Hinweis im Dialog.
F5 Verbindungsdialog akzeptiert OK mit offensichtlich falschem Benutzernamen und leerem Passwort ohne Hinweis – Aufgabe 3 – Kleinigkeit (wahrscheinlich Werkzeug) – Wunsch: Warnung beim Speichern.
F6 Admin ohne Termin landet auf "Termin wählen" mit Hinweis – Aufgabe 2 – Kleinigkeit – Wunsch: direkt auf "Termine" weiterleiten.

## 7. Lob
README-Ablauf und Zertifikat-Skript, die klare Bedienung der Web-Seite, der Fingerabdruck-Dialog und die Rückmeldung "Der Termin ist veröffentlicht (12 Teilnehmer)", die Handbuchnamen der Knöpfe stimmen mit dem Programm überein.

---

# TEIL 2 (Aufgaben 5 und 6)

## 1. Kurzfazit Teil 2
Das Zurückholen ging in vier Klicks und der Bericht war verständlich; die Zahlen stimmen mit dem überein, was ich in der Tabelle sehe. Beim PDF-Download habe ich im Browser keine Rückmeldung gesehen und weiß nur durch Nachsehen im Download-Ordner, dass es ankam. Notizen vermisse ich im Desktop-Programm.

## 2. Aufgaben im Überblick
| Aufgabe | geschafft | Aktionen ungefähr | Note | Kernsatz |
|---|---|---|---|---|
| 5 Ergebnisse zurückholen | ja | ca. 20 | 2 | Klarer Bericht, Status-Änderungen namentlich genannt. |
| 6 Bögen als PDF | teilweise (Download ja, Anzeige nicht selbst gesehen) | ca. 12 | 3 | Keine Rückmeldung nach dem Klick; Dateiname ist eine Zufallszahl. |

Durchschnitt Teil 2: 2,5; über Teil 1 und 2 (2,0 und 2,5): 2,3.

## 3. Verlauf je Aufgabe
### Aufgabe 5: Ergebnisse aus dem Web zurückholen
- Desktop gestartet, Reiter "Datensicherung", "Ergebnisse aus Web holen…". Wieder die Passwortabfrage "Passwort für „heinz“ auf https://localhost:6443:" (kein Merken, siehe F4).
- Frage: "Ergebnisse von 12 Teilnehmern aus dem Web-Termin „gemerkter Termin [termin_1]“ in „Musterverein, Musterstadt, 2026-12-05“ übernehmen? ... Die Ergebnisse in dieser Termin-Datei werden mit dem Stand aus dem Web überschrieben ... Vorher legt das Programm eine automatische Kopie an." Verständlich und beruhigend (Kopie), nur "gemerkter Termin [termin_1]" klingt technisch.
- Bericht (Bild sandbox\heinz\bilder\0010_bericht.png): "9 Teilnehmer aktualisiert. 0 nicht übernommen (anderer Teilnehmer unter derselben Startnummer), 0 Startnummer(n) in dieser Datei nicht gefunden, 0 ohne Startnummer übersprungen, 2 Status (Disqualifikation/Abbruch) geändert, 0 Disziplin(en) im Web leer (Wert dieser Datei blieb), 0 Fehler." Darunter: "Nr. 6 Demo, Frank: ohne Status → disqualifiziert" und "Nr. 10 Probe, Jens: ohne Status → Abbruch (Krankheit)". Das konnte ich gut nachvollziehen.
- Ergebniserfassung (Bild 0011_erg.png): Nr. 6 mit Haken "Disqualifiziert", Status "disqualifiziert", keine Punkte; Nr. 10 Trümmerfeld 25/10, Abbruch-Spalte "Krankheit", Status "Abbruch: Krankheit"; Nr. 1 55/36, Nr. 2 45/30, Nr. 3 50/35, Nr. 4 48/33, Nr. 5 40/28; Nr. 7 (Dreikampf) nur Trümmerfeld 52/34; Nr. 12 (Dreikampf) Fläche 44/29 und Behältnis 47/31, Trümmerfeld leer; Nr. 8, 9, 11 "noch kein Ergebnis". Das ist für mich plausibel: 9 aktualisiert = 7 mit Punkten + Nr. 6 + Nr. 10, drei Teilnehmer ohne Eintrag. Dass bei zwei Dreikämpfern nur einzelne Disziplinen ausgefüllt sind, erkläre ich mir damit, dass die Richter nicht alles geschafft oder verteilt haben; die Meldung "0 Disziplin(en) im Web leer" widerspricht dem etwas, denn leere Disziplinen gibt es ja (Nr. 7, 12). Das fand ich verwirrend.
- Vermisst: Die Notizen aus dem Web (z. B. "Hund zeigt spät an" bei Nr. 7, wie ich sie im PDF sehe) erscheinen im Desktop-Programm nirgends, auch nicht im Bericht; das Handbuch sagt es ("Im Desktop-Programm werden sie noch nicht angezeigt"), aber ohne Notizen ist für mich nicht erkennbar, dass Ruth/Dennis etwas vermerkt haben.

### Aufgabe 6: Benutzte Bögen als PDF
- Im Web (Tab seed) war noch Dennis angemeldet (Handy-Ansicht, Seite "Beispiel, Bernd"); "Abmelden (dennis)", als heinz angemeldet. Oben jetzt zusätzlich "Termine" und "Benutzer".
- "Ergebnistabelle", Knopf "Benutzte Bögen als PDF" mit Text "Lädt alle Bewertungsbögen mit Eintragungen (Punkte, Disqualifikation, Abbruch oder Notiz) zum Speichern oder Ausdrucken herunter. Nicht gespeicherte Eingaben der Tabelle sind nicht enthalten ..." Nach dem Klick passierte sichtbar nichts: keine Meldung, kein Fortschritt, kein Hinweis auf Download. Ich wäre unsicher gewesen, ob es geklappt hat.
- Wohin: im Download-Ordner des Rechners liegt eine Datei `33354a65-a8f9-4d0e-b051-618f2b3a38ac.tmp` (80 KB). Der Name (Zufallszahl, Endung .tmp) ist für einen Vereinsverwalter nicht als Bogen erkennbar; ob das am Test-Browser-Pane oder am Programm liegt, kann ich nicht sagen (wahrscheinlich Werkzeug-Effekt).
- Inhalt (per Textauszug geprüft, nicht gedruckt): 12 Seiten A4, ein Bogen je Teilnehmer mit Eintragungen (Einzeldisziplinen eine Seite, Dreikämpfer zwei Seiten), mit Name, Hund, Verein, Punktzahl und Gesamtpunktzahl, Notiz-Zeile ("Notiz: Gegenstand in der Ecke gefunden", "Notiz: Hund zeigt spät an", "Notiz: Abbruch wegen Krankheit des Hundes"), Nr. 6 mit "Disqualifiziert (DISQ)". Gesehen habe ich das Layout nicht als Bild; ob ich ausdrucken würde, kann ich nur zum Teil beurteilen: Inhalt und Umfang sehen vollständig und vertraut aus (gleiche Struktur wie der Desktop-Bogen), ich würde ihn mit einem Probeausdruck prüfen. Zwei Seiten mit komplett leeren Feldern (Nr. 6, Nr. 12 Trümmerfeld) wirken für mich als Papier unnötig.

## 4. Übersichtlichkeit der Web-Oberfläche (Admin, Desktop-Browser, ca. 800 px)
- Orientierung 2: Kopfzeile mit Teilnehmer, Ergebnistabelle, Termin wechseln, Termine, Benutzer, Abmelden (heinz) bricht in zwei Zeilen um, bleibt aber lesbar; Unterseiten haben "← Zur Teilnehmerliste".
- Begriffe 2: "Benutzte Bögen als PDF", "Bogen", "Ergebnistabelle" sind mir als Prüfungsleiter geläufig. "Termin wechseln" und "Termine" nebeneinander sind verwechselbar.
- Lesbarkeit 2: Tabelle ist in Blöcke je Disziplin gegliedert, groß, Eingaben leicht zu treffen; man scrollt viel.
- Rückmeldungen 3: Keine sichtbare Rückmeldung beim PDF-Knopf; die Hinweistexte ("Erst speichern, dann filtern ...") sind gut.
- Vertrauen 2: Termine-Seite zeigt Teilnehmerzahl; Tabelle zeigt gespeicherte Werte.

## 5. Texte der Dialoge (Desktop) Teil 2
Note 2. Beschreibungstext vor dem Übernehmen und der Bericht mit Namen der Statusänderungen sind sehr gut. Unklar: "gemerkter Termin [termin_1]" und "0 Disziplin(en) im Web leer" bei erkennbar leeren Disziplinen.

## 6. Funde Teil 2
F7 Notizen der Richter kommen im Desktop-Programm nicht an bzw. werden nirgends angezeigt, im Bericht auch kein Hinweis auf vorhandene Notizen – Aufgabe 5 – stört – Wunsch: Anzahl/Anzeige der Notizen im Bericht oder in der Ergebniserfassung.
F8 Bericht sagt "0 Disziplin(en) im Web leer", obwohl bei Dreikämpfern Disziplinen leer sind – Aufgabe 5 – Kleinigkeit/verwirrend – Wunsch: Erklärung, was gemeint ist.
F9 Dialogtext "gemerkter Termin [termin_1]" – Aufgabe 5 – Kleinigkeit – Wunsch: Terminname und Datum statt interner Kennung.
F10 Keine sichtbare Rückmeldung nach Klick auf "Benutzte Bögen als PDF" – Aufgabe 6 – stört (evtl. Werkzeug) – Wunsch: Hinweis "Download gestartet / Datei BewertungsbogenXX.pdf".
F11 Heruntergeladene Datei hat den Namen einer Zufallszahl mit Endung .tmp – Aufgabe 6 – Blocker für Laien, wenn es nicht am Test-Browser liegt – Wunsch: sprechender Name wie "Bewertungsboegen_2026-12-05.pdf".
F12 PDF enthält Seiten ganz ohne Eintragungen für Dreikämpfer (Nr. 12 Trümmerfeld leer) – Aufgabe 6 – Kleinigkeit.
F13 Passwort wird bei jeder Web-Aktion im Desktop erneut abgefragt (veröffentlichen, zurückholen) – Aufgabe 5 – stört wenig (Werkzeug schaltet Tresor ab), vgl. F4.

## 7. Lob Teil 2
Der Rückhol-Bericht mit Namen und Statusübergängen, die automatische Kopie vor dem Überschreiben, und dass das PDF Notizen und Disqualifikation mitführt.
