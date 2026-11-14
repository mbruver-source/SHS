# Sicherheitsprüfung SHS-Prüfungsprogramm, Desktop (13.11.2026)

Marco hat die Prüfung beauftragt, ausdrücklich ohne Web-Teil und Container. Geprüft wurde der Stand
HEAD e557b0f (Version 1.0.61), nur lesend; am Repo wurde nichts geändert.

**Veröffentlicht am 14.11.2026, nach dem Release 1.0.62.** Dieser Bericht nennt nur Funde, die in
1.0.62 behoben sind (Stand siehe letzter Abschnitt). Weitere Beobachtungen, die nicht behoben sind,
und die Nachstellungs-Skripte sind nicht veröffentlicht.

## Umfang

| Bereich | Inhalt | Geprüft durch | Einzelbericht |
|---|---|---|---|
| 1 | Fremde Termin-Dateien, Sicherungen, automatische Kopien (Datenschicht) | Prüf-Agent `qs-sicherheit` | [bereich1_datenschicht.md](bereich1_datenschicht.md) |
| 2 | Importe (CSV, OMA, Formular-PDF, anderer Termin) und Export | Prüf-Agent `qs-sicherheit` | [bereich2_importe_export.md](bereich2_importe_export.md) |
| 3 | Darstellung in Qt und PDF-Erzeugung | Prüf-Agent `qs-sicherheit` | [bereich3_darstellung_pdf.md](bereich3_darstellung_pdf.md) |
| 4, 5 | Programm/System (Update, Protokoll, Selbsttest) sowie Build, CI, Lieferkette | Hauptsitzung | [bereich4_5_programm_build.md](bereich4_5_programm_build.md) |

Nicht geprüft: `app_web.py`, `templates/`, `db_web.py`, `db_sync.py`, `sync_termin.py`, `Containerfile`,
`compose.yaml`, `build-container.yml`, PostgreSQL-Pfade. Nicht getestet: Verhalten unter Windows 10,
macOS und Linux; Netzpfade (UNC) in Bildverweisen; Auswertung von CSV-Zellen in Excel/LibreOffice.

Nicht erneut gemeldet wurden die Punkte aus `OFFEN.md` Abschnitt B und C und die Oktober-Funde mit
wirksamer Korrektur.

## Ergebnis

**Kein kritischer und kein hoher Fund.** Vier Funde sind mittel, zehn gering, dazu kommen Hinweise.
Niemand kann über diese Wege Programmcode ausführen. Es geht um veränderte oder gelöschte Daten, um
eine gelöschte Datei außerhalb des Programms (D-2) und um Störungen des Ablaufs.

Fast alle Funde setzen voraus, dass die Prüfungsleitung eine präparierte Datei eines Dritten annimmt
(Termin-Datei, Sicherung, CSV, Anmeldeformular). D-5 tritt auch ohne böse Absicht ein.

Die Korrekturen aus dem Oktober (S-1, S-4, H-1, S-8, S-9, CSV-Formeln) haben die Zerlegung der Module
vom 11.11.2026 überstanden. Die neuen Funde liegen überwiegend in Code, der seit dem 03.10.2026
dazugekommen ist (automatische Kopie, Zurückholen aus Kopien, Rückgängig, Abrechnung, Speichern ohne
Nachfrage), und in Lücken neben den damaligen Korrekturen.

## Funde nach Schwere

Spalte „Gegenprüfung“: „Lauf wiederholt“ heißt, die Hauptsitzung hat das Nachstell-Skript des Prüfers
selbst ausgeführt und dasselbe Ergebnis erhalten; die Skripte rufen die echten Funktionen des Programms
auf, mit umgelenktem Termine-Ordner und erfundenen Daten.

| ID | Schwere | Fund | Stelle | Gegenprüfung |
|---|---|---|---|---|
| D-2 | mittel | Ein präpariertes Rücksprung-Journal neben einer Termin-Datei (auch aus einem Sicherungs-ZIP) lässt SQLite beim Zurückspielen **eine beliebige Datei des Benutzers löschen**, ohne Meldung. Der Pfad muss dem Angreifer bekannt sein, nicht jeder Dateiinhalt wird gelöscht. | `db_termine.py:278-290`, `db_sicherung.py:603-604` | Mit der SQLite-Bibliothek der installierten EXE 1.0.61 (**3.45.1**) bestätigt: drei von vier Testdateien gelöscht. Mit SQLite 3.53.4 tritt es nicht auf. |
| D-1 | mittel | **Spaltennamen einer fremden Termin-Datei landen im SQL** von `teilnehmer_wiederherstellen`. „Rückgängig“ nach einem Löschen oder „Aus Sicherung holen…“ überschreibt dann still die Ergebnisse aller Teilnehmer. Die H-1-Korrektur (Trigger und Views entfernen) erfasst das nicht. | `db_stamm.py:446-461` | Code gelesen, Lauf wiederholt |
| D-5 | mittel | **Automatische Kopien hängen nur am Dateinamen.** Eine gleichnamige fremde Termin-Datei (anderer Ordner, auch andere Groß-/Kleinschreibung) verdrängt durch die Rotation die Kopien des eigenen Termins und wird im eigenen Termin als „Kopie dieses Termins“ angeboten; fremde Ergebnisse lassen sich so übernehmen. Geht über B15 hinaus und braucht keinen Angreifer. | `db_sicherung.py:230`, `:239-273`, `db_stamm.py:425-432`, `db_ergebnisse.py:104-133` | Lauf wiederholt |
| I-5 | mittel (untere Grenze) | **Überlange importierte Werte** (ab 1000 bzw. 3000 Zeichen, z. B. aus einem Anmeldeformular) lassen die Sammel-Ausdrucke des ganzen Termins mit einem Programmfehler scheitern; die Meldung nennt weder Teilnehmer noch Feld. | `db_import.py:210-219`, `:694-696`, `db_stamm.py:163-194` | Ausgabe des Laufs gelesen |
| D-7 | gering | Fremdschlüssel-Regeln und Vorgabewerte fremder Zusatzspalten überleben `init_db`: Löschen eines Platzhalter-Teilnehmers löscht alle anderen mit. Gleiche Klasse wie H-1. | `db_verbindung.py:558-567`, `:587-590` | Lauf wiederholt |
| D-6 | gering | Werte aus Kopien werden ohne Typprüfung übernommen (Kommazahl, BLOB); danach lässt sich der **eigene Termin nicht mehr öffnen**. Voraussetzung ist eine präparierte Datei im Ordner `Auto-Sicherung`. | `db_ergebnisse.py:148-154`, `db_stamm.py:450-461`, `db_termine.py:192-203` | Lauf wiederholt |
| D-3 | gering | Die Größengrenze für Sicherungs-ZIPs (S-8) prüft nur die angegebene Größe; entpackt wird der ganze Datenstrom (unter 1 KB ZIP belegt über 600 MB Arbeitsspeicher), schon bei der Auswahl der Datei. | `db_sicherung.py:68-91`, `:467`, `:587` | nur Bericht des Prüfers |
| I-3 | gering | Das Datum der Veranstaltung aus einer fremden Termin-Datei geht unbereinigt in den Dateinamen. Mit „ohne Nachfrage speichern“ (Standard seit 12.11.2026) entsteht der Export **außerhalb des Ablageorts**, bei der Teilnehmerliste mit Personendaten. Nichts wird überschrieben, die Endung bleibt `.pdf`/`.csv`. | `desktop_gemeinsam.py:101-104`, `:284-291`, `db_termine.py:349` | Lauf wiederholt |
| I-4 | gering | Die Abrechnungs-CSV (neu seit 09.11.2026) schreibt die Spalte „Datum“ ohne Formelschutz. | `db_import.py:1014`, `:1022` | Lauf wiederholt |
| I-1 | gering | Eine sehr große Zahl bei „Schulterhöhe“ (CSV oder Formular) bricht den ganzen Import-Stapel mit „Unerwarteter Fehler“ ab; folgende Dateien werden nicht gelesen. | `db_import.py:257-263`, `:435-436`, `:851-852` | nur Bericht des Prüfers |
| I-2 | gering | Drei reguläre Ausdrücke laufen auf fremden Werten quadratisch: Ein Formular von rund 400 KB lässt das Fenster hochgerechnet etwa 13 Minuten hängen. | `db_import.py:757`, `:136`, `desktop_gemeinsam.py:98` | nur Bericht des Prüfers |
| I-6 | gering | Die Abschlussmeldung des Imports übernimmt fremde Werte ungekürzt und mit Zeilenumbrüchen: vorgetäuschte Meldungszeilen, Fenster weit größer als der Bildschirm. | `db_import.py:173-185`, `desktop_import_meldungen.py:93-128` | nur Bericht des Prüfers |
| D-8, A-1 | gering | Zwei Tooltips deuten Namen als HTML (wie S-1 im Oktober): „Rückgängig“ mit dem Nachnamen, „Quittung…“ mit dem Richternamen. Ein Bildverweis lädt eine lokale Datei; ein Netzpfad wurde bewusst nicht getestet. Ein breiter Lauf über 2955 Widgets fand keine weitere Stelle. | `desktop_rueckgaengig.py:32`, `desktop_abrechnung.py:210` | Lauf wiederholt (D-8), Code gelesen (A-1) |

## Hinweise (keine Schwachstelle im engeren Sinn)

| ID | Hinweis |
|---|---|
| D-4 | Der Filter für Windows-Gerätenamen im Sicherungs-ZIP lässt Hochziffern (`COM¹`), `CONIN$`/`CONOUT$` und Punkt/Leerzeichen am Ende durch; unter Windows 11 ohne Wirkung, über die Oberfläche nicht erreichbar. |
| I-7 | Unsichtbare Zeichen und Steuerzeichen in Namen werden gespeichert; die Dublettenerkennung lässt sich damit umgehen. |
| I-8 | Der CSV-Formelschutz sieht nicht hinter unsichtbare Zeichen am Zellanfang; ob eine Tabellenkalkulation dann rechnet, ist nicht belegt. |
| I-9 | Importe laufen ohne Größengrenze und ohne Wartecursor im Fenster-Thread (PDF mit 5,9 MB: 66 s). Die fehlende Grenze stand schon im Oktober-Bericht. |
| P-1 | Selbsttest-Protokoll mit festem Namen im gemeinsamen `/tmp` (Linux). Nur Störung durch einen zweiten lokalen Benutzer. |
| L-1, L-3 | GitHub-Einstellungen: keine Regeln für Tags und `main`, Secret Scanning aus, Festlegung der Actions auf Commit-Hashes nicht erzwungen. Der Schutz der Lieferkette hing allein am GitHub-Konto. |
| L-4, L-5 | Zwei kleine Härtungen in den Workflows (`persist-credentials`, `version.txt` direkt im Skript). |
| L-6 | bandit lief nicht neu (lokal nicht installiert); am 14.11.2026 nachgeholt, siehe `bandit-2026-11-14.md`. |

## Zusammenhänge

- **D-1, D-7 und H-1 haben dieselbe Wurzel:** Eine fremde Termin-Datei darf mehr mitbringen, als das
  Programm kennt (Zusatzspalten mit beliebigen Namen, Regeln und Vorgabewerten). Eine gemeinsame
  Korrektur wäre, beim Öffnen nur das eigene Schema zuzulassen oder die Daten in eine frische Datei zu
  übernehmen. Das war im Oktober der Vorschlag der Zweitprüfung zu H-1.
- **D-5 ist die Voraussetzung für D-1 Weg b** (Schaden am eigenen Termin über eine Kopie der fremden
  Datei) und macht D-6 leichter erreichbar.
- **I-3 und I-4** entstehen beide, weil das Datum einer fremden Termin-Datei beim Öffnen nur als Text
  geprüft wird.
- **I-5 entschärft I-2, I-6 und I-9 mit:** Eine Längengrenze beim Import nimmt den regulären Ausdrücken,
  der Abschlussmeldung und den Ausdrucken die übergroßen Werte.
- **D-8 und A-1** lassen sich mit einer gemeinsamen Hilfsfunktion und einem Test über alle Widgets
  dauerhaft schließen.

## Abgleich durch die Hauptsitzung

- **SQL aus Textbausteinen im ganzen Umfang** (Suche über `db*.py` ohne `db_web`/`db_sync`,
  `desktop_*.py`, `pdf_export.py`, `app.py` und die übrigen Programm-Module; bandit lief nicht): Nur
  `db_stamm.py:451` und `:459` (D-1) setzen Namen aus Daten ein. Alle anderen Stellen nehmen Namen aus
  Konstanten: `db_ergebnisse.py:152`, `:189`, `db_termine.py:298`, `:315`, `:344`, `:349`, `:411`,
  `db_verbindung.py:436`, `:460`; `db_verbindung.py:564` quotet den fremden Namen. `db_zeitplan.py` und
  alle `desktop_*.py` enthalten kein zusammengesetztes SQL.
- **Abgrenzung zu akzeptierten Punkten:** C28 ist laut Historie ein einzelner Bedienungs-Grenzfall
  beim Wiederherstellen, keine allgemeine Freigabe für präparierte Sicherungen; D-2 und D-3 sind damit
  neu. C9 P1 („Laufzeit bei sehr langen Wörtern“) betrifft das Erzeugen des Anmeldeformulars; I-2 und
  I-5 grenzen daran an, liegen aber im Import und in den übrigen Ausdrucken. B15 betrifft nur
  Terminnamen, die selbst auf das Datumsmuster enden; D-5 geht darüber hinaus. Ob Marco I-2/I-5 als
  von C9 mit abgedeckt ansieht, ist seine Entscheidung.
- **Einstufung von D-2:** „Kein hoher Fund“ hängt daran, dass D-2 als mittel gewertet ist, obwohl es
  eine Datei außerhalb des Programms löscht. Gründe für mittel: Der Angreifer muss den vollständigen
  Pfad kennen, nicht jeder Dateiinhalt wird gelöscht, es wird kein Code ausgeführt und nichts
  ausgelesen. Für eine höhere Einstufung spricht: Es genügt, eine zugeschickte Sicherung
  wiederherzustellen, und es gibt keine Meldung. Die Gewichtung liegt bei Marco.
- **Version der geprüften EXE:** Das Selbsttest-Protokoll nennt 1.0.61; ihre SQLite-Bibliothek ist
  3.45.1 (aus Python 3.11 der CI).

## Nachstellung

Die Nachstellungs-Skripte sind nicht veröffentlicht. Alle Daten waren erfunden; kein Lauf hat den
echten Termine-Ordner berührt. Für D-2 wurde die installierte EXE einmal mit `--selbsttest` gestartet,
um ihre SQLite-Bibliothek zu ermitteln.

## Stand nach Version 1.0.62

Alle Funde dieses Berichts sind in Version 1.0.62 behoben; jeder wurde einzeln mit Marco besprochen
und nach seinem Go umgesetzt, danach von einem unabhängigen Prüf-Agenten gegengeprüft, und die ganze
Testsuite lief grün (1312 bestanden, 0 fehlgeschlagen).

| Fund | Umsetzung in 1.0.62 |
|---|---|
| D-2 | Eine Termin-Datei, Kopie oder Sicherung mit Rücksprung-Journal, das auf eine weitere Datei verweist, wird nicht geöffnet. Die Terminübersicht nennt den Grund. Marco führt D-2 als **Härtung**. |
| D-1, D-7 | Beim Zurückholen werden nur bekannte Spalten übernommen und quotiert; beim Öffnen werden fremde Fremdschlüssel-Regeln abgelehnt. |
| D-5 | Kopien werden nach Verein und Datum geprüft, nicht vorgewählt und beim Übernehmen nachgefragt; Ergebnisse werden zusätzlich über den Namen abgeglichen. |
| D-6 | Werte aus Kopien werden vor dem Speichern wie beim Öffnen geprüft. |
| D-3, D-4 | Die Größengrenze gilt für den entpackten Datenstrom (auch LZMA/BZIP2, auch bei verschlüsselten Sicherungen); die Prüfung der Dateinamen ist strenger. |
| I-1 bis I-9 | Längengrenzen und Prüfung der Schulterhöhe beim Anlegen und Bearbeiten, Grenzen für Listen (2 MB) und Formulare (5 MB), Bereinigung von Datum und Dateinamen, Formelschutz auch in der Abrechnung, Bereinigung unsichtbarer Zeichen, gekürzte Meldungen, Wartecursor. |
| D-8, A-1 | Tooltips mit fremden Namen werden als Klartext angezeigt. |
| P-1 | Das Selbsttest-Protokoll liegt im Benutzerordner statt im gemeinsamen `/tmp`. |
| L-1, L-3 | Regelsätze für Release-Tags (`v*`) und `main`, Secret Scanning und Push Protection eingeschaltet, Festlegung der Actions auf Commit-Hashes erzwungen. |
| L-4, L-5 | Workflows gehärtet. |
| L-6 | bandit nachgeholt, kein Fund. |
