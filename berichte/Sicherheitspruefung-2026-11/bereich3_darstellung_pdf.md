# Bereich 3: Darstellung und Ausgabe (Qt-Oberfläche, PDF)

Rohergebnis des Prüfers (Agenten-Typ `qs-sicherheit`), Stand HEAD e557b0f (1.0.61), 13.11.2026. Der Lauf
wurde einmal durch das Nutzungslimit unterbrochen und fortgesetzt. Die Skripte sind nicht veröffentlicht.

Ergebnis: ein Befund (A-1, gering), gleichartig zu D-8. Die Korrekturen S-1 und S-4 greifen an allen
geprüften Stellen, alle 18 PDF-Exporte geben Markup als Text aus.

## A-1 (gering): Tooltip des Knopfs „Quittung…“ zeigt den Richternamen als Rich Text

- Stelle: `desktop_abrechnung.py:210` (`knopf.setToolTip(f"Quittung für {z.name} als PDF speichern")`).
- Herkunft: `z.name` aus `lr_abrechnung.abrechnungszeilen()`, also `veranstaltung.wertungsrichter_1`
  bis `_5` (fremde Termin-Datei, Sicherung oder Termin-Dialog).
- Weg: Richtername `<img src="PFAD">`; Termin öffnen, Reiter „Abrechnung Leistungsrichter“, Maus über
  „Quittung…“: Qt deutet den Tooltip als HTML.
- Auswirkung: Markup verfälscht den Tooltip, `<img src>` lädt eine lokale Bilddatei. Netzpfad nicht
  getestet (Vermutung wie bei S-1: ein UNC-Pfad würde einen Zugriff auslösen).
- Nachgestellt: `b3\a2_quittung_tooltip.py` (`Qt.mightBeRichText`: True, Dokumenthöhe 48 px statt
  22 px). Der breite Nachweis `a1_qt_scan.py` meldet dieselbe Stelle für alle fünf Richter-Zeilen, es
  ist der einzige Treffer im ganzen Lauf.
- Vorschlag: `_klartext_tooltip` aus `desktop_zeitplan.py:108` nach `desktop_gemeinsam.py` ziehen und
  für `desktop_abrechnung.py:210` und `desktop_rueckgaengig.py:31` nutzen. Dazu ein Test, der für alle
  Widgets eines mit Markup gefüllten Termins prüft, dass kein Tooltip mit Datenwert `mightBeRichText`
  erfüllt (`b3\scan.py` taugt als Vorlage).

## Regression geprüft

- S-1 (Qt) greift: `meldungsfenster_als_klartext` (`desktop_gemeinsam.py:1205`) wird in `app.py:1347`
  vor dem ersten Fenster aufgerufen; zur Laufzeit haben `warning`, `information`, `critical`,
  `question` `PlainText`, der Informativtext ebenfalls. Sieben selbst gebaute `QMessageBox`: fünf mit
  Datenbezug setzen `PlainText` (`desktop_gemeinsam.py:207`, `:1567`,
  `desktop_import_meldungen.py:115`, `desktop_verwaltung.py:491`, `:676`), eine ist die Fabrik
  (`:1218`), `desktop_gemeinsam.py:364` hat nur festen Text. `QInputDialog`: alle sechs Aufrufe mit
  festen Beschriftungen. Zeitplan-Seitenleiste: bewusst `RichText`, alle Datenwerte mit `html.escape`
  (`desktop_zeitplan.py:461–474`), Listen-Tooltip über `_klartext_tooltip` (`:628`). `KopfBalken`,
  `kurzer_hinweis`, Status-Labels: Klartext bzw. maskiert.
- S-4 (PDF) greift: alle Titel mit Verein und Datum über `_p_wert` und `_datum_kurz`
  (`pdf_export.py:880`, `1145`, `1453`, `1539`, `1596`, `1688`, `1927`, `1938`). `_datum_lang` gibt
  ein nicht lesbares Datum roh zurück, der einzige Aufrufer (`:1270`) maskiert. `_datum_kurz` und
  `_euro_text` maskieren auch nicht lesbare Werte.

## Ohne Befund geprüft

**Breiter Nachweis Qt** (`a1_qt_scan.py`, `a1_weiter.py`, `scan.py`): Demo-Termin, in dem per SQL alle
freien Textspalten Markup enthalten, geöffnet über `termin_oeffnen`; zweiter Lauf zusätzlich mit Markup
in Datums- und Zahlenfeldern. 2955 Widgets (Label-Text und Format, Tooltip, WhatsThis, StatusTip,
Tabellen-/Listen-/Baum-/Combo-Einträge, Kopfzeilen, Reiter, `QAction`, `QTextEdit`-HTML, Stylesheets).
Erfasst: Hauptfenster mit allen 10 Reitern (vor und nach Löschen/Ergebnisänderung), `StartDialog`,
`VeranstaltungsDialog`, `TeilnehmerDialog` (ED und DK), `StartnummerTauschenDialog`,
`TerminImportDialog`, die drei Sicherungs-Dialoge, `PauseDialog`, `VerteilenDialog`,
`BewertungsbogenAuswahlDialog`, `BehaeltnisEtikettenDialog`, `HilfeDialog`, `VersionDialog`,
`LizenzDialog`, `DemoPanel`. Der Wert kam in 125 Zellen, 137 Listeneinträgen, 138 Eingabefeldern,
16 Combo-Einträgen, 35 Gruppentiteln, 7 Labels und 2 Fenstertiteln an, überall als Klartext.

Nur statisch gelesen: Meldungen, die erst durch Bedienung entstehen; die laufende Demo-Tour; Formular-
und PDF-Import mit echter Datei; Zustände „Überschneidung im Zeitplan“ und „Stechen-Sieger festlegen“;
eigene Checklistenpunkte und Abrechnungseingaben in der Oberfläche.

**Weitere Qt-Punkte:** keine weiteren Tooltips mit Daten; `setWhatsThis`/`setStatusTip` kommen nicht
vor; keine Delegates mit `QTextDocument`, kein `QPrinter`, kein `insertHtml`; Stylesheets ohne Nutzer-
oder Termin-Text (Werte aus `QSettings` gegen feste Listen geprüft); `openUrl` nur mit lokalen Pfaden
gerade gespeicherter Dateien und der festen Release-Adresse; Hilfe-Dialog nur fester Text, Sucheingabe
über `QRegularExpression.escape`, externe Links abgeschaltet (C14); Demo-Panel `PlainText`.

Nebenbei (Darstellung, kein Sicherheitsfund): Ein `&` in einem Richternamen (Gruppentitel im Zeitplan)
oder in einem eigenen Checklistenpunkt wird als Tastenkürzel gedeutet und unterstrichen.

**Breiter Nachweis PDF** (`b1_pdf.py`): Marken `<b>Zn z</b>` in allen freien Textfeldern, eigener
Checklistenpunkt, Abrechnungseingaben; zweiter Lauf zusätzlich in Datums-, Gebühren- und Zeitfeldern.
18 Exporte: Bewertungsbogen ED, DK, DK je Disziplin; alle Bewertungsbögen; Behältnis-Etiketten;
Ergebnisliste; Ergebnis-Etiketten; leere Ergebnisliste; Statistik; Übersicht Prüfungsleitung;
Chipnummernliste; Richterbedarf; Abrechnung; Checkliste; Quittungen (alle und einzeln); Zeitplan;
Anmeldeformular. Jede Marke steht wörtlich im PDF, kein Export brach ab, kein Bild eingebettet. Nicht
aufgerufen: Ergebnisliste je einzelner Leistungsklasse, Etiketten mit anderen Maßen, Filterauswahl der
Sammel-Bewertungsbögen, Ergebnisse mit Abbruchgrund und Stechen-Hinweis.

**Anmeldeformular (AcroForm):** 41 reine Text- und Ankreuzfelder ohne `/A`, `/AA`, `/JS`,
`/OpenAction`; Feldnamen fest bzw. gegen `ALLE_PRUEFUNGEN` gefiltert; Veranstaltungsdaten per
`drawString`.

**Metadaten, Bilder, Schriften:** nur das Anmeldeformular setzt Titel (fest) und Autor (Vereinsname);
keine Personendaten in Metadaten; kein Pfad aus Daten; nichts gefunden, was reportlab über „lange
Werte“ hinaus hängen lässt.

Offen geblieben: Bedienabläufe mit Meldungsfenstern und die Demo-Tour nur statisch; Netzpfade nicht
getestet.
