"""
Hilfefenster mit Suchfeld, Inhaltsverzeichnis und dem Hilfetext (_HILFE_HTML).

Aus desktop_dialoge.py ausgelagert (11.11.2026), Code unverändert; desktop_dialoge.py bleibt als
Fassade. Bewusst KEIN `import app` (siehe desktop_programm.py).
"""

from __future__ import annotations
import re
from PySide6.QtCore import QRegularExpression, QTimer
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)


# Allgemeine Bedienungshilfe (ein Abschnitt je Reiter) - Inhalt mit dem Nutzer vorab
# abgestimmt, bevor er hier fest eingebaut wurde. Als einfaches HTML statt reinem Text,
# damit sich die Abschnittsüberschriften im Hilfe-Fenster (siehe HilfeDialog) klar vom
# Fließtext abheben.
_HILFE_HTML = """
<h2>Hilfe – SHS Prüfungsprogramm</h2>
<p><b>Schrift zu klein?</b> Menü „Ansicht“ → „Schriftgröße“ → „Groß“ oder „Sehr groß“.
<b>Schrift zu blass?</b> Menü „Ansicht“ → „Hintergrund“ → „Hoher Kontrast“ (schwarz auf weiß,
größere Kontraste). Die Wahl bleibt gespeichert. Alles noch größer (unter Windows):
Einstellungen → System → Anzeige → „Skalierung“, z. B. 125 % wählen.</p>

<h3>Erste Schritte</h3>
<p>Beim Programmstart zeigt die Terminübersicht alle vorhandenen Termine mit Datum, Verein,
Ort und Teilnehmerzahl. Über "Neuen Termin anlegen…" legst du Verein/Ort/Datum (und optional
weitere Angaben) fest – der Dateiname wird automatisch vorgeschlagen. Einen vorhandenen
Termin öffnest du per Doppelklick oder "Öffnen"; "Löschen…" verschiebt eine Termin-Datei
nach einer Rückfrage in den Papierkorb (gibt es keinen, fragt das Programm vor dem endgültigen
Löschen noch einmal). Im Hauptfenster kannst du über "Anderen Termin öffnen…"
jederzeit wechseln.</p>

<h3>Demoprüfung</h3>
<p>Der Knopf "Demoprüfung" mit dem Doktorhut (oben rechts im Hauptfenster und im Startbildschirm) spielt
einmal einen kompletten Prüfungstag mit erfundenen Daten vor: Termin anlegen, Teilnehmer,
Startnummern, Bezahlt, Zeitplan, Ergebnisse, Disqualifikation, Auswertung mit Stechen und
die Ergebnisliste als PDF. Das Programm klickt selbst, ein kleines Fenster erklärt jeden
Schritt; du drückst nur "Weiter" ("Weiter" füllt einen laufenden Schritt auch sofort fertig
aus). Der Demo-Termin liegt in einem temporären Ordner und wird am Ende gelöscht (eine dann
noch im PDF-Programm geöffnete Ergebnisliste beim nächsten Programmstart) – deine Termine
bleiben unberührt, der Reiter "Datensicherung" ist
währenddessen gesperrt. "Beenden" bricht jederzeit ab.</p>

<h3>Reiter "Teilnehmer"</h3>
<p>Liste aller gemeldeten Teilnehmer. "Teilnehmer hinzufügen…" öffnet die Erfassungsmaske:
Stammdaten, Verband/Mitgliedsnummer, Anschrift (Straße/Hausnummer/PLZ/Ort) und Kontaktdaten
(E-Mail/Telefon) sowie Wurftag des Hundes - alles optional, außer den mit * markierten
Pflichtfeldern. Dazu Art (ED/DK), Leistungsklasse, bei ED die Disziplin und die
Suchgegenstände. Startnummern vergibst du gesammelt mit „Fehlende Startnummern vergeben…“ (Bereiche je Prüfung in den Veranstaltungsdaten) oder einzeln über „Bearbeiten…“.</p>
<p><b>Gegenstände:</b> Hinter jedem Gegenstand legst du bei "gesucht in" fest, für welche
Disziplin er gilt – das steuert, wo er auf dem Bewertungsbogen erscheint. Bei ED gibt es in
jeder Leistungsklasse genau einen Gegenstand: nur Gegenstand 1 ist eingabebereit, "gesucht in"
folgt automatisch der ED-Disziplin. Bei DK sind mindestens 1 (LK1), 2 (LK2) bzw. 3 (LK3)
verschiedene Gegenstände nötig. Alle auf "frei" zu lassen ist in Ordnung; ordnest du
Disziplinen zu, sollten alle drei belegt sein (derselbe Gegenstand darf in mehreren Feldern
stehen, jede Disziplin aber nur einmal vorkommen).</p>
<p><b>Spalte "Anmerkungen":</b> Die Warnung "Chip-Nr. fehlt" (orange, mit Warndreieck) solltest du vor dem
Prüfungstag beheben. Graue Hinweise wie "Gegenstand noch offen" sind nur Erinnerungen –
Gegenstände können bis zum Prüfungstag nachgetragen werden.</p>
<p>"Bezahlt umschalten" setzt den Zahlungsstatus aller markierten Teilnehmer, ohne den ganzen
Dialog zu öffnen. "Keine Teilnahme" markiert einen nicht erschienenen Teilnehmer: Er bleibt
grau in der Liste, fällt aber aus Zeitplan, Ergebniserfassung, Auswertung und allen
Ausdrucken außer der Übersicht für die Prüfungsleitung heraus (erfasste Ergebnisse bleiben
gespeichert; "Teilnahme wiederherstellen" macht es rückgängig). "Startnummer tauschen…"
tauscht die Nummern zweier Teilnehmer.
"Aus anderem Termin importieren…" übernimmt Stammdaten aus einem früheren Termin (ohne
Startnummer, Gegenstände, Bezahlt-Status und Ergebnis). "Bewertungsbogen (PDF)…" erzeugt den
Bogen nur für den markierten Teilnehmer (beim Dreikampf wahlweise zwei Seiten oder drei
Blätter, eins je Disziplin). Die Filter Art/LK, Start-Nr. und Bezahlt sowie das Suchfeld
"Suche" (Name, Vorname oder Hund, ein Teilwort genügt) blenden Zeilen nur aus. Ein Rechtsklick auf eine
Zeile öffnet ein Menü mit denselben Aktionen wie die Knöpfe. "Rückgängig" (Strg+Z) nimmt das letzte
Löschen von Teilnehmern oder "Alle Startnummern zurücksetzen…" zurück; "Ablageort öffnen" zeigt den
Ordner des Bewertungsbogens.</p>

<h3>Reiter "Formular-Import"</h3>
<p>Das leere Formular erzeugst du auch hier mit "Leeres Anmeldeformular (PDF)…".</p>
<p><b>Ausfüllbares Anmeldeformular (empfohlen):</b> Importieren lässt sich nur das
Anmeldeformular, das dieses Programm selbst erzeugt (Reiter "Ausdrucke/Export" → "Anmeldeformular
(PDF)…"), und zwar aus demselben Termin. Die Teilnehmer füllen es am Rechner aus, kreuzen
genau eine Prüfung an und speichern es (nicht "Drucken → Als PDF", dabei gehen die Felder
verloren). "Anmeldeformulare (PDF) importieren…" liest die zurückgeschickten Dateien ein,
mehrere auf einmal; bereits vorhandene Meldungen werden übersprungen, abgelehnte Dateien mit
Grund aufgelistet (z. B. mehrere Prüfungen angekreuzt oder eine im Termin nicht angebotene
Prüfung).</p>
<p><b>Teilnehmerliste aus Excel:</b> "Leere Vorlage (CSV) speichern…" liefert die passenden
Spalten; in Excel ausfüllen, als CSV speichern und mit "Teilnehmerliste einlesen (Excel/CSV)…" einlesen (denselben
Knopf gibt es auch im Reiter "Teilnehmer"). Komma/Semikolon und die Excel-
Kodierung werden erkannt.</p>
<p>"OMA-Export importieren…" übernimmt den Meldungs-Export der Online-Meldeannahme direkt.</p>
<p><b>Andere Meldeformulare</b> (Word, Foto/Scan, handschriftlich) mit Hilfe eines KI-Assistenten
(unten aufklappen): "Prompt kopieren", Prompt und Formulare an den KI-Assistenten geben, die
erzeugte CSV-Datei mit "Teilnehmerliste einlesen (Excel/CSV)…" einlesen. Jede Zeile wird ein neuer Teilnehmer (ohne Startnummer,
Gegenstände und Bezahlt-Status); fehlerhafte Zeilen werden mit Grund aufgelistet und
übersprungen. Achtung Datenschutz: Die Formulare gehen dabei an den gewählten KI-Anbieter.</p>
<p>Zum Ausprobieren gibt es eine Beispieldatei mit 20 erfundenen Teilnehmern auf der
Projektseite: https://mbruver-source.github.io/SHS/beispiel_teilnehmer.csv (danach im Reiter
"Teilnehmer" die Startnummern vergeben).</p>

<h3>Reiter "Zeitplan"</h3>
<p>Blöcke und Pausen lassen sich auch mit der Maus an eine andere Stelle derselben Spalte ziehen
(statt "Hoch"/"Runter"); "Ablageort öffnen" zeigt den Ordner des Zeitplan-PDFs.</p>
<p>Plant den Tagesablauf je Richter. Startzeit oben festlegen, dann je Richter eine
Spalte mit "Prüfungsblock hinzufügen…" oder "Pause hinzufügen…" (nach der markierten Zeile;
wahlweise bei allen Richtern zu einer Uhrzeit, z. B. Mittagspause; mit "genau um diese Uhrzeit
beginnen" beginnt sie fest zur Uhrzeit, ein erst kurz vorher begonnener Block rückt dahinter und
davor bleibt eine Lücke – auch bei "Automatisch verteilen…" wählbar). Reihenfolge mit
"Hoch"/"Runter" anpassen – sie wirken auf den ganzen Block (fette Kopfzeile). "Automatisch verteilen…" erstellt einen ausbalancierten Vorschlag
(ersetzt den bisherigen Plan aller Richter, mit Rückfrage) – danach frei von Hand
änderbar. Start-/Endzeiten berechnen sich automatisch. Die Seitenleiste "Offene Starts"
zeigt je Art/Leistungsklasse/Disziplin, ob dafür schon ein Prüfungsblock angelegt wurde
(grün) oder noch fehlt (rot, "noch offen") – bleibt auch beim seitlichen Scrollen durch
viele Richter-Spalten sichtbar. Dreikampf-Teams setzt der Vorschlag nie gleichzeitig an und
hält den "Mindestabstand Team" ein; steht ein Team doch doppelt (z. B. nach dem Verschieben),
sind die Zeilen rot mit einem Warndreieck markiert und oben in der Seitenleiste aufgeführt.
"Zeitplan (PDF)…" exportiert eine Seite je Richter.</p>
<p><b>Wichtig zu "Entfernen":</b> Ein Prüfungsblock speichert nur Art/Leistungsklasse/
Disziplin und die Dauer je Teilnehmer – WER genau darin geprüft wird, wird bei jeder
Anzeige automatisch aus den aktuellen Teilnehmerdaten ermittelt, nicht einzeln gespeichert.
"Entfernen" löscht deshalb nach einer Rückfrage immer den GANZEN Block (alle darin
zusammengefassten Teilnehmer), nicht nur einen einzelnen Teilnehmer. Fällt z. B. ein Teilnehmer kurzfristig
aus (Krankmeldung), muss im Zeitplan nichts angefasst werden: im Reiter "Teilnehmer"
mit "Keine Teilnahme" markieren (nicht löschen) – der Block bleibt bestehen und zeigt beim
nächsten Öffnen des Zeitplans automatisch einen Teilnehmer (und entsprechend weniger Zeit)
weniger.</p>

<h3>Reiter "Ergebniserfassung"</h3>
<p>Eine Zeile je Teilnehmer, bei DK alle drei Disziplinen nebeneinander. Suchleistung (0–60)
und Anzeigeleistung (0–40) eintragen. Noch nicht gespeicherte Zeilen werden gelb markiert.
"Alle Ergebnisse speichern" sichert alle Änderungen auf einmal. Der Filter blendet nur aus,
ungespeicherte Eingaben gehen dabei nicht verloren. Um ein bereits gespeichertes Ergebnis
wieder zu entfernen, beide Felder (Suche und Anzeige) leeren und anschließend speichern –
ist nur eines der beiden Felder leer, gilt das als unvollständig und wird beim Speichern
zurückgewiesen. "Disqualifiziert" ankreuzen leert und sperrt die Punktefelder. Bei "Abbruch"
den Grund wählen (Ungehorsam, Verletzung Hund, Krankheit, Verletzung HF): die Punktefelder
bleiben offen für die Teilbewertung (bei Ungehorsam die abgebrochene Disziplin leer lassen,
sonst einen fehlenden Teil mit 0 eintragen).
Beim Schließen des Programms werden ungespeicherte Ergebnisse automatisch gespeichert.
Das Suchfeld "Suche" findet Teilnehmer nach Name oder Hund; "Bewertungsbogen (PDF)…" erzeugt den
Bogen der aktuellen Zeile. Rechtsklick (auch unter den Zeilen) zeigt dazu "Alle Ergebnisse
speichern" und "Liste aktualisieren".</p>

<h3>Reiter "Auswertung"</h3>
<p>Zeigt die berechnete Rangliste je Leistungsklasse mit Wertnote. Filter nach
Art/Leistungsklasse und Startnummer, Suche nach Name oder Hund; ein Klick auf eine Spaltenüberschrift
sortiert die Tabelle. "Bewertungsbogen (PDF)…" (auch per Rechtsklick) erzeugt den Bogen der markierten
Zeile. "Nicht bestanden" wird rot markiert und erhält keine
Platzzahl, zählt aber bei den Startern mit. "Auswertung neu berechnen" aktualisiert die
Anzeige. "Rangliste drucken (PDF)…" speichert die Rangliste als PDF - ist im Filter eine
Art/Leistungsklasse gewählt, nur diese, sonst alle (der Startnummer-Filter wird dabei nicht
berücksichtigt). Sind mehrere punktgleich auf Platz 1, steht dort "Stechen offen": nach dem
Stechen mit "Stechen-Sieger festlegen…" den Sieger wählen - er wird 1., die anderen 2.
Für Prüfungen ab dem 01.01.2027 (voraussichtlich neue Prüfungsordnung) entfällt das Stechen:
Punktgleiche teilen sich dann Platz 1, der Knopf "Stechen-Sieger festlegen…" fehlt.</p>

<h3>Reiter "Übersicht"</h3>
<p>Teilnehmerzahlen je Art/Leistungsklasse und Disziplin, die Zahl der Abteilungen und die
Anzahl benötigter Richter (1 ED = 1 Einheit, 1 DK = 3 Einheiten, höchstens 36 Einheiten je
Richter). Darunter die benötigten Behältnisse der Behältnisstrecke je LK (ED Behältnisstrecke
+ DK): leere einmal je LK, eines mit Gegenstand je Teilnehmer, in LK3 wahlweise zusätzlich ein
separates Behältnis für die Material-Verleitung je Teilnehmer. Die gleiche Tabelle steht auch
in der Richter-Bedarf-PDF, die du mit "Richter-Bedarf (PDF)…" gleich hier erzeugst.</p>

<h3>Reiter "Abrechnung Leistungsrichter"</h3>
<p>Rechnet die Vergütung der Leistungsrichter (Richter 1-5 aus den Veranstaltungsdaten, nur
mit eingetragenem Namen) ab: Fahrtkosten = Kilometer (Gesamtstrecke Hin und zurück) mal Satz je
Kilometer, dazu die Tagespauschale. Standard sind 0,35 € je km und 50 € Tagespauschale; beide
Werte lassen sich oben für den Termin ändern. In jeder Zeile stehen sie vorbelegt und lassen sich
dort für diesen Richter überschreiben. Kilometer dürfen mit Tausenderpunkt stehen (1.234 =
1234). Die Eingaben werden beim Verlassen des Felds gespeichert. "Übersicht als PDF…" erzeugt die
Gesamtübersicht, "Export als CSV…" eine Liste (eine Zeile je Richter, Art "Ausgabe") für ein
Vereinstool mit Ein- und Ausgaben, der Knopf "Quittung…" in der Zeile eine Quittung für genau diesen Richter zum
Unterschreiben. "Ablageort öffnen" zeigt den Ordner der PDFs.</p>

<h3>Reiter "Verwaltung"</h3>
<p>Unter dem Knopf steht die Checkliste zum Prüfungstermin: der Ablauf von "Wochen vorher" bis
"Zum Schluss" in einzelnen Schritten zum Abhaken. Der Knopf "Checkliste" oben im Fenster springt von jedem Reiter hierher und klappt die erste Kategorie mit
offenen Punkten auf. Die Kategorien lassen sich auf- und zuklappen (beim Öffnen sind sie zugeklappt). Die Haken werden sofort je Termin
gespeichert, "Alle Haken entfernen" setzt sie (nach Rückfrage) zurück. Mit "Punkt hinzufügen…" (in jeder
Kategorie) und "Kategorie hinzufügen…" legst du eigene Punkte und Kategorien an; sie lassen sich über ✕
bzw. "Kategorie löschen" wieder entfernen. Eigene Kategorien und Punkte werden beim Anlegen eines neuen
Termins aus dem letzten Termin vorgeschlagen, die Haken nicht. Vorgegebene Punkte und Kategorien, die du nicht
brauchst, blendest du mit ✕ bzw. "Kategorie ausblenden" für diesen Termin aus (sie zählen dann nicht mit);
"Ausgeblendetes zeigen" holt alles zurück. Auch das Ausblenden wird für einen neuen Termin vorgeschlagen.
"Checkliste (PDF)…" unter der Liste druckt sie mit dem aktuellen Stand der Haken.</p>
<p>"Veranstaltungsdaten bearbeiten…" ändert Verein/Ort/Datum sowie Vereins-Nr.,
Prüfungsnummer, Richter 1-5, Prüfungsleiter und Prüfungsgebühr ED/DK nachträglich –
diese Angaben stehen oft erst kurz vor dem Prüfungstag fest und erscheinen im Kopf der
Statistik-PDF bzw. in der Übersicht für Prüfungsleitung (siehe Reiter "Ausdrucke/Export").
Verband, Meldestelle und die angebotenen Prüfungen bestimmen Kopf und Ankreuzfelder des
Anmeldeformulars.</p>

<h3>Reiter "Ausdrucke/Export"</h3>
<p>Neben jedem Knopf steht in einer Zeile, was er erzeugt; Einzelheiten zeigt der Hinweis,
wenn die Maus kurz darauf bleibt. Alle PDF-Ausgaben an einer Stelle: ausfüllbares Anmeldeformular (siehe Reiter
"Formular-Import"), Ergebnisliste, leere Ergebnisliste zum Ausfüllen,
Etiketten, Statistik, Übersicht für Prüfungsleitung, Chipnummernliste, Abrechnung der Leistungsrichter,
Checkliste, Richter-Bedarf, Zeitplan sowie
alle Bewertungsbögen gesammelt. "Teilnehmerliste speichern (CSV, für Excel)…" speichert alle Teilnehmer
mit Stammdaten als Excel-Liste (lässt sich auch wieder einlesen). PDFs landen standardmäßig im
Ordner "Ausdrucke" des Termins; nach dem Speichern zeigt ein Fenster, wo die Datei liegt.
"Ablageort öffnen" zeigt den Ordner im Dateimanager (Explorer bzw. Finder) – alle Exporte (auch im Zeitplan-Tab) teilen
sich denselben Speicherort. Mit dem Haken "Dateien ohne Nachfrage im Ablageort speichern" entfällt die Frage
nach dem Speicherort in allen Reitern; eine vorhandene Datei wird nie überschrieben, sondern bekommt " (2)"
im Namen.</p>

<h3>Reiter "Datensicherung"</h3>
<p>Sichert bzw. liest ALLE Termine aus dem gemeinsamen Termine-Ordner als eine Sicherungsdatei
– nicht nur den gerade geöffneten Termin. "Sicherung erstellen…" fragt zunächst,
ob die Datei mit einem Passwort geschützt werden soll (freiwillig; dann wird sie
verschlüsselt), danach den Speicherort. "Sicherung wiederherstellen…" fragt bei Bedarf nach dem
Passwort und bei jedem bereits vorhandenen Termin, ob überschrieben, als Kopie
importiert oder übersprungen werden soll. Wer ein Passwort vergibt: Ein vergessenes Passwort
lässt sich nicht wiederherstellen – gut aufbewahren.</p>
<p>Als Speicherort am besten einen USB-Stick oder ein anderes Laufwerk wählen und den Stick
getrennt vom Rechner aufbewahren – eine Sicherung auf demselben Rechner hilft nicht, wenn
dieser ausfällt.</p>
<p>Zusätzlich legt das Programm beim Öffnen und beim Beenden eines Termins selbst eine Kopie im Ordner
"Auto-Sicherung" neben dem Termine-Ordner ab (je Termin die letzten zehn). Sie ersetzt die Sicherung
nicht und enthält alle Teilnehmerdaten unverschlüsselt; der Ordner darf von Hand geleert werden.
Gelöschte Teilnehmer holt der Knopf "Aus Sicherung holen…" im Reiter "Teilnehmer" aus diesen Kopien zurück
(auch nach dem Beenden); vor jedem Löschen entsteht eine Kopie, wenn der Schalter im Menü "Einstellungen" an ist.
Der Knopf zeigt bei eingeschaltetem Schalter nur diese Kopien vor dem Löschen, bei ausgeschaltetem die normalen.
"Ergebnisse aus automatischer Kopie wiederherstellen…" (hier im Reiter "Datensicherung") zeigt alle Kopien des
geöffneten Termins und setzt per Haken einzelne Ergebniswerte (eine Disziplin, Disqualifiziert, Abbruch,
Stechen-Sieger) auf den Stand der Kopie zurück; die jetzigen Werte werden dabei überschrieben.
Liegt ein Termin auf einem Wechseldatenträger (USB-Stick, SD-Karte) oder Netzlaufwerk, weist das Programm
beim Start und beim Terminwechsel darauf hin, ihn nicht abzuziehen. Externe USB-Festplatten meldet Windows
als feste Platte, dafür erscheint kein Hinweis.</p>

<h3>Versionsanzeige</h3>
<p>Der Button "Version" oben rechts (zwischen "Anderen Termin öffnen…" und
"Demoprüfung") bzw. das Menü "Hilfe → Version und Lizenzen" zeigt die aktuell installierte
Version. "Hilfe → Nach Updates suchen…" öffnet das Fenster und sucht gleich. "Nach
Updates suchen" prüft dort per Klick automatisch (über GitHub), ob eine neuere Version
veröffentlicht wurde, und zeigt bei Bedarf einen Download-Button an – dafür wird kurz
eine Internetverbindung gebraucht, ohne Internet erscheint stattdessen ein entsprechender
Hinweis. Eine automatische Prüfung im Hintergrund beim Programmstart ist bewusst nicht
eingebaut.</p>
<p>Nur für eine Fehlermeldung (Bereich "Für Fehlermeldungen"): "Diagnose kopieren" legt Version, System und das Ende des
Absturzprotokolls in die Zwischenablage (dein Benutzername wird dabei ersetzt; vor dem
Einfügen kurz prüfen, ob Teilnehmerdaten darin stehen). "Protokoll-Ordner öffnen" zeigt die
Datei. Bei einem unerwarteten Fehler erscheint ein Fenster mit denselben Möglichkeiten.</p>

<h3>Diese Hilfe</h3>
<p>Der Knopf "Hilfe" oben und F1 (am Mac Cmd+?) öffnen die Hilfe beim Abschnitt des Reiters, in
dem du gerade bist. Oben im Suchfeld ein Wort eingeben (Strg+F springt dorthin): Gesucht wird
nach ganzen Wörtern und Wortanfängen, "USB" findet also "USB-Stick". Erst wenn es so nichts
gibt, zählen auch Stellen mitten im Wort. Alle Treffer werden orange markiert, Enter oder
"Weiter" springt zum nächsten.</p>

<h3>Tastenkürzel</h3>
<p><b>Überall:</b> F1 (am Mac Cmd+?) – Hilfe zum aktuellen Reiter. In der Hilfe: Strg+F
(am Mac Cmd+F) – ins Suchfeld.</p>
<p><b>Hauptfenster:</b> Strg+N legt einen Teilnehmer an (springt zum Reiter "Teilnehmer"), Strg+F springt ins
Suchfeld des Reiters (im Startbildschirm in die Terminsuche), Strg+1 bis Strg+9 wechseln den Reiter.</p>
<p><b>Reiter "Teilnehmer":</b> Strg-Klick bzw. Umschalt-Klick markiert mehrere Zeilen, Strg+A alle
sichtbaren. Entf löscht die markierten Teilnehmer (nach Rückfrage), Strg+Z macht das (oder "Alle Startnummern
zurücksetzen…") rückgängig. Doppelklick auf eine Zeile öffnet "Bearbeiten…".</p>
<p><b>Reiter "Ergebniserfassung":</b> Zelle markieren und die Zahl tippen – sie ersetzt den
Wert; F2 (am Mac Enter) oder Doppelklick ändert ihn. Enter übernimmt, Esc verwirft die Eingabe.
Tab bzw. Umschalt+Tab springt zur nächsten bzw. vorigen Eingabe. Die Leertaste setzt das
Häkchen bei "Disqualifiziert" und klappt bei "Abbruch" die Liste auf. Entf bzw. die Rücktaste
leert die Zelle oder nimmt den Abbruch zurück. Strg+S (am Mac Cmd+S) speichert alle
Ergebnisse.</p>
<p>In Rückfragen wählt Enter die vorgegebene Antwort (bei allem, was Daten ändert, "Nein"),
Esc bricht ab.</p>

<h3>Aussehen (Menü "Ansicht")</h3>
<p>Unter "Hintergrund" wählst du das Design: Beagle (Standard, warme Creme-Töne), Hell,
Dunkel oder Hoher Kontrast. Unter "Akzentfarbe" legst du die Farbe der Haupt-Schaltflächen und
Markierungen fest (Lohbraun als Standard, Blau, Grün, Violett). Beides lässt sich frei
kombinieren, wirkt sofort und wird gespeichert; noch nicht gespeicherte Ergebnisse bleiben dabei
erhalten. Im Design Dunkel bleibt das Fenster des Systems zum Öffnen/Speichern von Dateien unter
Windows hell.</p>
<p>Der dunkle Balken oben zeigt Verein, Datum, Ort und die Zahl der Teilnehmer des geöffneten
Termins. Steht hinter einer kurzen grauen Erklärung ein Fragezeichen-Symbol, erscheint der
ausführliche Text, wenn du die Maus darüber hältst.</p>

<h3>Einstellungen (Menü "Einstellungen")</h3>
<p>Im Hauptfenster gibt es neben "Ansicht" und "Hilfe" das Menü "Einstellungen" mit zwei Schaltern.
Beide werden gespeichert und gelten beim nächsten Start weiter:</p>
<ul>
<li><b>Vor dem Löschen von Teilnehmern eine Sicherung anlegen</b> (Standard: aus): Vor jedem Löschen
entsteht eine Kopie des Termins im Ordner "Auto-Sicherung" (getrennt von den normalen Kopien, die letzten
fünf je Termin; normales Starten und Beenden verdrängt sie nicht). Daraus holt "Aus Sicherung holen…" im
Reiter "Teilnehmer" gelöschte Teilnehmer zurück, auch nach dem Beenden des Programms.</li>
<li><b>Dateien ohne Nachfrage im Ablageort speichern</b> (Standard: aus): Alle PDFs und Dateien
landen mit dem vorgeschlagenen Namen im Ablageort, ohne nach dem Speicherort zu fragen. Dieselbe
Einstellung steht auch als Haken im Reiter "Ausdrucke/Export".</li>
</ul>
<p>Unabhängig davon fragt das Programm beim Beenden nach, wenn gerade Teilnehmer gelöscht wurden und
"Rückgängig" das noch zurücknehmen könnte.</p>

<h3>Ausführliches Handbuch</h3>
<p>Ein ausführliches Benutzerhandbuch mit Screenshots (auch als PDF zum Ausdrucken) steht auf
der Projektseite bei GitHub (github.com/mbruver-source/SHS, Datei docs/HANDBUCH.md). Dort
kannst du über "Issues" auch Fehler melden oder Wünsche äußern – am besten mit der
Diagnose aus dem Fenster "Version" (siehe oben).</p>
"""


def _hilfe_mit_inhaltsverzeichnis(html: str) -> str:
    """UX-Test 03.11.2026, X14: Die Hilfe war eine lange Textwand. Vor den ersten Abschnitt
    kommt ein Inhaltsverzeichnis mit Sprungmarken auf jede Zwischenüberschrift (h3)."""
    titel = re.findall(r"<h3>(.*?)</h3>", html)
    if not titel:
        return html
    nummern = iter(range(len(titel)))
    html = re.sub(r"<h3>(.*?)</h3>",
                  lambda m: f'<h3><a name="abschnitt{next(nummern)}"></a>{m.group(1)}</h3>', html)
    verzeichnis = "<p><b>Inhalt:</b> " + " · ".join(
        f'<a href="#abschnitt{nummer}">{text}</a>' for nummer, text in enumerate(titel)
    ) + "</p>"
    erster = html.index("<h3>")
    return html[:erster] + verzeichnis + html[erster:]


def _hilfe_anker(abschnitt: str) -> str | None:
    """Sprungmarke („abschnittN“, siehe _hilfe_mit_inhaltsverzeichnis) der ersten
    Zwischenüberschrift, die `abschnitt` enthält - oder None."""
    for nummer, titel in enumerate(re.findall(r"<h3>(.*?)</h3>", _HILFE_HTML)):
        if abschnitt in titel:
            return f"abschnitt{nummer}"
    return None


class HilfeDialog(QDialog):
    """Allgemeine Bedienungshilfe in einem eigenen, scrollbaren Fenster - ein Abschnitt je
    Reiter (siehe _HILFE_HTML oben). Der Knopf „Hilfe“, F1 und „Hilfe → Hilfe anzeigen“ öffnen
    sie gleich beim Abschnitt des aktuellen Reiters (`abschnitt`; UX-Test 2026-11, T8, für den
    Knopf seit dem Nachtest 2, N6). Das Suchfeld oben markiert alle Treffer und springt mit
    Enter bzw. „Weiter“ zum nächsten (T8). Gesucht wird zuerst nach ganzen Wörtern und
    Wortanfängen („USB“ fand sonst „ausbalancierten“, N6)."""

    def __init__(self, parent=None, abschnitt: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Hilfe")
        self.resize(560, 520)

        self.anzeige = anzeige = QTextBrowser()
        anzeige.setHtml(_hilfe_mit_inhaltsverzeichnis(_HILFE_HTML))
        anzeige.setOpenExternalLinks(False)

        self._muster: QRegularExpression | None = None  # Suchmuster der aktuellen Treffer
        self.suchfeld = QLineEdit()
        self.suchfeld.setPlaceholderText("In der Hilfe suchen, z. B. „Startnummer“ oder „Pause“")
        self.suchfeld.setClearButtonEnabled(True)
        self.suchfeld.textChanged.connect(self._treffer_markieren)
        self.suchfeld.returnPressed.connect(self.weitersuchen)
        # Namen für Bildschirmleser (Barrierefreiheit): Feld und Anzeige haben keinen eigenen Text.
        self.suchfeld.setAccessibleName("In der Hilfe suchen")
        self.anzeige.setAccessibleName("Hilfetext")
        weiter_btn = QPushButton("Weiter")
        weiter_btn.setAutoDefault(False)
        weiter_btn.clicked.connect(self.weitersuchen)
        self.treffer_label = QLabel("")
        such_zeile = QHBoxLayout()
        such_zeile.addWidget(self.suchfeld, 1)
        such_zeile.addWidget(weiter_btn)
        such_zeile.addWidget(self.treffer_label)
        QShortcut(QKeySequence.Find, self, activated=self.suchfeld.setFocus)

        schliessen_btn = QPushButton("Schließen")
        schliessen_btn.setAutoDefault(False)  # Enter im Suchfeld sucht weiter
        schliessen_btn.clicked.connect(self.accept)
        schliessen_zeile = QHBoxLayout()
        schliessen_zeile.addStretch()
        schliessen_zeile.addWidget(schliessen_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(such_zeile)
        layout.addWidget(anzeige)
        layout.addLayout(schliessen_zeile)

        anker = _hilfe_anker(abschnitt) if abschnitt else None
        if anker is not None:
            # Erst nach dem Layout springen - vorher kennt der Browser seine Höhe nicht.
            QTimer.singleShot(0, self, lambda: anzeige.scrollToAnchor(anker))

    def _fundstellen(self, muster: QRegularExpression) -> list[QTextCursor]:
        """Alle Treffer von `muster` im Hilfetext, in Textreihenfolge."""
        fundstellen = []
        cursor = self.anzeige.document().find(muster)
        while not cursor.isNull():
            fundstellen.append(cursor)
            cursor = self.anzeige.document().find(muster, cursor)
        return fundstellen

    def _treffer_markieren(self, text: str) -> None:
        self._muster = None
        fundstellen = []
        wortteile = False
        suchtext = text.strip()
        if suchtext:
            optionen = (QRegularExpression.CaseInsensitiveOption
                        | QRegularExpression.UseUnicodePropertiesOption)
            escaped = QRegularExpression.escape(suchtext)
            # N6: zuerst ganze Wörter und Wortanfänge, erst ohne Treffer auch Wortteile. Beginnt
            # der Suchtext nicht mit einem Buchstaben oder einer Ziffer (z. B. „(“), gibt es
            # keinen Wortanfang - dann gleich überall suchen.
            wortanfang = suchtext[0].isalnum()
            muster_liste = [QRegularExpression(escaped, optionen)]
            if wortanfang:
                muster_liste.insert(0, QRegularExpression(rf"(?<!\w){escaped}", optionen))
            for muster in muster_liste:
                fundstellen = self._fundstellen(muster)
                if fundstellen:
                    self._muster = muster
                    break
                wortteile = wortanfang
        format_ = QTextCharFormat()
        format_.setBackground(QColor("#ff9f1c"))  # N6: kräftiges Orange statt blassem Gelb
        format_.setForeground(QColor("#000000"))
        format_.setFontWeight(QFont.Bold)
        markierungen = []
        for cursor in fundstellen:
            auswahl = QTextBrowser.ExtraSelection()
            auswahl.cursor = cursor
            auswahl.format = format_
            markierungen.append(auswahl)
        self.anzeige.setExtraSelections(markierungen)
        if not suchtext:
            self.treffer_label.setText("")
        elif markierungen:
            self.treffer_label.setText(
                f"{len(markierungen)} Treffer" + (" (in Wörtern)" if wortteile else "")
            )
            # Beim Tippen ab Anfang den ersten Treffer zeigen.
            self.anzeige.moveCursor(QTextCursor.Start)
            self.anzeige.find(self._muster)
        else:
            self.treffer_label.setText("nichts gefunden")

    def weitersuchen(self) -> None:
        if self._muster is None:
            return  # ohne Treffer nicht an den Anfang springen (Verifikation B6)
        if not self.anzeige.find(self._muster):
            # Am Ende von vorn weitersuchen.
            self.anzeige.moveCursor(QTextCursor.Start)
            self.anzeige.find(self._muster)
