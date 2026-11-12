# Fortschritt: SHS-Prüfungsprogramm-Ablösung

**Laufende Historie (ab 11.2026).** Ältere Monate stehen unverändert in `historie/` (Übersicht: `historie/README.md`). Zum Nachlesen eines früheren Beschlusses dort suchen (`git grep -i "Stichwort" -- historie`); den aktuellen Stand liefern `OFFEN.md`, `Architektur.md` und `entscheidungen/`.

## 01.11.2026: Lizenzen im Versionsfenster und Lizenzseite im Installer (Marco)

Marcos Rückmeldung: (1) Im Versionsfenster fehlt eine Übersicht über die Lizenzen (war als
OFFEN B14 zurückgestellt). (2) Bei der Installation wird die MIT-Lizenz nicht abgefragt, anders
als z. B. bei OneDrive. Entscheidungen im Planmodus: eigenes Lizenzfenster, Installer zeigt den
englischen MIT-Originaltext, `LICENSE` in alle Pakete, Lizenz-Link in der Web-Fußzeile und
Lizenzvereinbarung beim Öffnen der Mac-.dmg.

- `tools/drittlizenzen.py`: `THIRD_PARTY_LICENSES.txt` beginnt jetzt mit „Übersicht /
  Overview“, eine Zeile je Komponente (Name Version - Lizenz), danach wie bisher die Volltexte.
  Für PySide6/Shiboken6 steht fest `LGPL-3.0-only`, nicht die in den Metadaten mit angebotene
  kommerzielle Lizenz. Neuer Test in `test_drittlizenzen.py`.
- Desktop (`desktop_programm.py`): Das Versionsfenster zeigt „Lizenz: MIT (© 2026 Marco)“ und
  den Button „Lizenzen anzeigen“. Der öffnet `LizenzDialog`: `LICENSE`, darunter
  `THIRD_PARTY_LICENSES.txt`, schreibgeschützt in Festbreitenschrift. Fehlt eine Datei (etwa
  beim Start aus dem Quellcode), steht dort ein Hinweis statt eines Fehlers. Pfade über das neue
  `bundle_pfad()` in `desktop_gemeinsam.py`. `build.spec` bündelt jetzt auch `LICENSE`.
  `selbsttest.py` hat den Schritt „Lizenztexte“: In der gebauten Fassung müssen beide Dateien
  da sein, aus dem Quellstand gibt es für die Drittlizenz-Datei nur einen Hinweis. Drei neue
  GUI-Tests.
- Windows-Installer: `LicenseFile=LICENSE` zeigt die Seite „Lizenzvereinbarung“ mit
  „Ich akzeptiere die Vereinbarung“ (Texte aus German.isl). Inno zeigt sie bei jedem Lauf, also
  auch bei Updates. `LICENSE` wird als `LICENSE.txt` in den Programmordner gelegt.
  `README_INSTALLER.md` nachgezogen.
- Linux (`tools/linux_pakete.sh`): `.deb` legt `LICENSE` als `/usr/share/doc/shs-pruefungsprogramm/copyright`
  ab (Debian-Konvention), das AppImage beide Lizenzdateien unter `usr/share/doc/…`.
- macOS (`build-installer.yml`, neu `tools/dmg_einstellungen.py`): Die .dmg entsteht mit
  `dmgbuild==1.6.7` statt `hdiutil create` und enthält eine Lizenzvereinbarung (englischer Text,
  deutsche Buttons auf deutschen Macs) sowie `LICENSE.txt` und `THIRD_PARTY_LICENSES.txt`.
  dmgbuild wird erst nach dem PyInstaller-Build installiert und taucht deshalb nicht in der
  Drittlizenz-Liste auf. Der Schritt prüft per `hdiutil udifderez`, dass die Lizenz-Ressource
  drin ist. Das Einbinden für den Selbsttest beantwortet die Lizenzfrage mit `yes` (per
  Prozess-Substitution wegen `pipefail`) und `PAGER=cat`. Hinweis: dmgbuild nutzt intern
  `hdiutil udifrez`, das Apple als veraltet führt; fällt es weg, schlägt der dmg-Schritt fehl.
  Nur in der CI prüfbar, siehe OFFEN A9.
- Container: `LICENSE` liegt jetzt unter `/app/LICENSE`.
- Web (`app_web.py`, neu `templates/lizenzen.html`): Die öffentliche Seite `/lizenzen` (ohne
  Anmeldung) zeigt `LICENSE` und `THIRD_PARTY_LICENSES.txt`, autoescaped. Fehlt eine Datei,
  erscheint ein Hinweis statt eines Fehlers. Die Fußzeile aller Seiten hat den Link „Lizenzen“.
  Sechs neue Tests (`TestLizenzseite`).
- Doku: `docs/HANDBUCH.md` (Lizenzseite im Setup, Lizenz in der .dmg, Lizenzen im
  Versionsfenster), `Architektur.md`, `OFFEN.md` (B14 gestrichen, A9 neu). Das Versionsfenster
  hat keinen eigenen Handbuch-Screenshot, deshalb sind keine Bilder neu aufzunehmen.
- Tests lokal: die Unittest-Suite mit 693 Tests ist grün (175 übersprungen); `test_app_gui.py`
  und `test_theme.py` sind grün (417 bestanden). Die Gegenprobe ohne den Programmcode ergibt
  fehlschlagende neue Tests (Web 6, GUI 3, Drittlizenzen 1).
- Kein Commit des Programmcodes und kein Versionsbump, bis Marco einen Build anfordert. Vorher
  muss der CI-Probelauf auf einem Branch laufen (A9), wie bei A8 am 26.10.2026.
- Verifikation (Agent `verifikation`): keine funktionalen Fehler. Direkt nachgezogen:
  `UML.md` (`LizenzDialog`, Kante vom `VersionDialog`, Mermaid lokal geprüft),
  `README_INSTALLER.md` (dmgbuild, Lizenzdateien in .dmg/.deb/AppImage) und `app_web.py`
  (liest die Lizenzdateien wie die Desktopversion mit `errors="replace"`).
  Weitere Punkte aus der Verifikation, mit Marco geklärt:
  - Web-Screenshots: Marco wollte sie neu aufnehmen lassen. Keines der fünf Bilder
    `docs/bilder/handbuch_web_*.png` zeigt aber die Fußzeile, sie liegt jeweils unterhalb des
    Ausschnitts. Neu aufnehmen ändert also nichts; die Bilder bleiben.
  - dmgbuild (Marco: Variante B): Neben `dmgbuild==1.6.7` sind jetzt auch dessen Abhängigkeiten
    fest, `ds_store==1.3.3` und `mac_alias==2.2.3`. Alle drei sind auf PyPI seit Monaten
    veröffentlicht. Prüfsummen (Variante C) bewusst nicht, weil jedes Update neue Prüfsummen
    bräuchte.
  - Zur Kenntnis: `/lizenzen` prüft die Sitzung nicht gegen die Datenbank. Bei einer veralteten
    Sitzung zeigt die Seite noch die Navigation, die Links dahinter prüfen die Sitzung wieder.
  - CI-Probelauf (A9, Marco ok): Der Stand liegt als Commit auf dem Branch `lizenzen`, nicht auf
    `main`. Marco pusht ihn und startet `build-installer.yml` darauf.

## 01.11.2026: CI-Probelauf der Lizenz-Änderungen (A9 erledigt)

- Marco hat den Branch `lizenzen` (Commit `0f98bb7`) gepusht und `build-installer.yml` darauf
  gestartet (Lauf 41295326815). Alle vier Build-Jobs sind grün, `release` wie vorgesehen
  übersprungen.
- Belege aus dem Protokoll:
  - Windows: Inno meldet „Reading file (LicenseFile)“ und packt `LICENSE` ein; der Selbsttest
    der .exe und der still installierten Fassung zeigt „OK Lizenztexte“.
  - macOS (Apple Silicon und Intel): dmgbuild 1.6.7 mit ds_store 1.3.3 und mac_alias 2.2.3
    installiert, die Prüfung auf die Lizenz-Ressource besteht, und die App aus der
    eingebundenen .dmg läuft durch den Selbsttest. Das Einbinden trotz Lizenzabfrage
    funktioniert also nicht-interaktiv.
  - Linux: „OK Lizenztexte“ im gebauten Ordner, im AppImage und im installierten .deb.
- Die Push-Läufe `Container bauen` und `Tests` (Linux-Job) sind ebenfalls grün.
- OFFEN.md A9 ist gestrichen. Noch nicht von Hand angesehen: die Lizenzseite im echten
  Windows-Setup und die Lizenzabfrage beim Öffnen der .dmg am Mac (gehört zu A1).

## 01.11.2026: Durchgang aller offenen Punkte mit Marco

Marco ist jeden Punkt aus `OFFEN.md` einzeln durchgegangen. Was sich an seinem Windows-Rechner
prüfen ließ, hat die Sitzung dort selbst geprüft, mit Testdaten in einem Temp-Ordner und
nie mit den echten Terminen. Werkzeuge (coverage, bandit, pypdfium2) liefen in einer eigenen
venv im Scratchpad, das Anaconda-Python blieb unverändert.

**Entscheidungen**
- **A1** bleibt offen und umfasst jetzt auch die Lizenzabfrage beim Öffnen der .dmg. **A2**
  bleibt offen.
- **A5** (Papierkorb) und **A7** (Praxistests vom September) sind gestrichen.
- **A10** ist neu: Die Lizenzseite im echten Windows-Setup sieht Marco beim nächsten Update.
- **B3, B7, B8, B9, B11, B12, B13** bleiben unverändert zurückgestellt.
- **B10:** Abdeckungsmessung und bandit kommen jetzt dran, der Rest bleibt zurückgestellt.
- **C36** (`/lizenzen` bei veralteter Sitzung) und **C37** (`hdiutil udifrez` in dmgbuild) sind
  neu als akzeptierte Restrisiken eingetragen.

**A3, Design „Hell“ bei „Apps: dunkel“: erledigt.**
- Windows wurde kurz auf „Apps: dunkel“ gestellt (Registry `AppsUseLightTheme`, per
  `try/finally` zurückgesetzt und nachgeprüft).
- Das Programm lief mit der echten Windows-Darstellung. Hauptfenster, Tabellen, Kontextmenü,
  Aufklappliste, Zeitplan und Hilfe sind hell und gut lesbar. Qt meldet für das Programm das
  helle Farbschema.

**A4, Erklärfenster der Demo: erledigt.**
- In keinem der 16 Schritte ragt das Fenster in die Taskleiste. Gemessen wurde der Rahmen
  gegen `availableGeometry`, mit Bildschirmfotos.
- Dabei fiel auf: In Schritt 13 war der Erklärtext mitten in der Zeile abgeschnitten. Das
  Fenster wuchs nicht mit, als „Gespeichert unter …“ und „PDF öffnen“ dazukamen. Behoben in
  `DemoPanel._groesse_anpassen`: nur die Höhe passt sich an. Mit `adjustSize()` wurde das
  Fenster für den langen Pfad so breit, dass es rechts aus dem Bildschirm ragte.
- **Marcos Beobachtung (in 1.0.52):** Das Fenster ändert je Schritt Größe und Lage, und man
  muss „Weiter“ jedes Mal suchen. Ursache: Die Oberkante blieb fest, und `adjustSize()` änderte
  Höhe und Breite.
- **Jetzt:** Die Unterkante ist verankert (`_unten`, `moveEvent`), die Breite bleibt fest, und
  das Fenster wächst nach oben.
  - Am echten Bildschirm steht „Weiter“ in allen Schritten auf (1450, 741). Nur „Fertig ✔“ im
    letzten Schritt ist schmaler.
  - Verschiebt der Anwender das Fenster oder zieht es am Rand größer, gilt die neue Unterkante.
    Den Hinweis dazu gab die Verifikation.
  - Das Ausweichen in die andere Ecke, wenn das Fenster das gezeigte Element verdeckt,
    bleibt wie bisher.
- Rest, schon vorher vorhanden: Ein Abschnitt des Speicherpfads ohne Umbruchmöglichkeit kann
  rechts leicht angeschnitten sein.

**A6, PDF-Schrift: Bildschirmteil erledigt, Papierausdruck bleibt offen (A6 angepasst).**
- Alle zehn PDF-Arten wurden mit Sonderzeichen-Testdaten erzeugt (polnisch, tschechisch,
  dänisch, türkisch, vietnamesisch, griechisch) und als Bild angesehen. Alle Zeichen sind
  richtig, eingebettet ist DejaVu.
- Vier Layout-Befunde, alle von Marco zur Umsetzung freigegeben:
  1. **Ergebnisliste zum Ausfüllen:** Die Vereinsspalte wurde schon bei üblichen Namen
     winzig, sehr lange liefen über den Rand in „Gesamtpunkte“. Marco wählte „kombiniert“:
     erst bis 7,5 pt verkleinern, dann in der Zelle umbrechen. Das hebt die Entscheidung vom
     21.09. auf, die nur verkleinerte (mindestens 5,5 pt).
  2. **Bewertungsbogen:** Bei „Widerristhöhe:“ rutschte der Doppelpunkt in eine eigene Zeile.
     Die Beschriftungsspalte ist jetzt 28 statt 26 mm breit, die Wertspalte 60 statt 62 mm.
  3. **Doppelnamen:** Sie wurden mitten im Wort getrennt („Müller-Lüdensc|heidt“). Jetzt
     trennt reportlab am vorhandenen Bindestrich (`embeddedHyphenation`, zentral für alle
     Stile).
  4. **Etiketten:** Ein langer austragender Verein brauchte drei Zeilen und reichte bis an
     die Schnittlinie. Jetzt wird er bis 6,5 pt verkleinert, bis er zweizeilig passt
     (`_etikett_verein_stil`). Das hilft schon bei üblichen Namen wie „Gebrauchshundeverein
     Köppern e. V.“. Sehr lange Namen bleiben dreizeilig, passen aber in die Etikettenhöhe.

**B10, Abdeckung und bandit: erledigt.**
- **Abdeckung lokal 91 %** (Bericht `berichte/Abdeckung-2026-11.md`). Marco gab alle drei
  empfohlenen Lücken frei; sie sind als GUI-Tests geschlossen:
  - Zeitplan-Bearbeitung über die Knöpfe: 80 % → 96 %;
  - Konflikt-Rückfrage beim Wiederherstellen einer Sicherung: `desktop_verwaltung` 81 % → 90 %;
  - drei nie aufgebaute Dialoge: `desktop_dialoge` 89 % → 98 %.
- Die Tests fanden keinen Fehler. Eine Auffälligkeit gab es: „Entfernen“ im Zeitplan löschte
  einen Prüfungsblock ohne Rückfrage. Marco: Rückfrage ergänzen. Jetzt „Eintrag entfernen“ mit
  Vorgabe „Nein“, wie bei „Richter löschen“.
- **bandit 1.9.4** über alle Programm-Module: 23 Hinweise. Nach Prüfung am Code gibt es keinen
  Fund mit Handlungsbedarf (Fehlalarme bzw. bewusst so). Der Bericht liegt in
  `_unveroeffentlicht/bandit-2026-11-01.md`.

**Tests und Prüfung**
- Neu sind 4+1 PDF-Tests, 3 Demo-Tests, die Abdeckungstests (22 Läufe) und die Rückfrage
  beim Entfernen.
- Jede Gegenprobe ohne die jeweilige Änderung schlägt fehl.
- Lokal grün: 697 Unittests (175 übersprungen) sowie 441 GUI-Tests mit `test_theme.py`
  (1 übersprungen, 1 xfail).
- Verifikation (Agent `verifikation`): kein funktionaler Fehler. Nachgezogen wurden Docstrings,
  das Ziehen am Rand des Erklärfensters, ein Test, dass die Etiketten-PDF den neuen Stil nutzt,
  und ein Test für das vom Anwender verschobene Fenster.
- Programmcode (`pdf_export.py`, `desktop_demo.py`, `desktop_zeitplan.py`) und Tests bleiben bis
  zum nächsten Build uncommittet. Committet sind nur `OFFEN.md`, `Fortschritt.md` und
  `berichte/Abdeckung-2026-11.md`.
- `docs/HANDBUCH.md` und die Programmhilfe nennen die Rückfrage beim Entfernen, das Handbuch die feste Lage von „Weiter“. Neue Bilder sind vor dem Build nicht nötig. `handbuch_demo.png` zeigt das
  Erklärfenster unverändert an derselben Ecke.

## 01.11.2026: Neues Erscheinungsbild „Beagle“ (Marco)

**Anlass:** Marco empfand die Oberfläche als „langweilig, steril und KI-mäßig“. Die Analyse
nannte fünf Ursachen:
- keine Identität (der Beagle nur als Taskleisten-Symbol, der Termin nur im Fenstertitel);
- das generische Standardblau #2F6FED;
- Emojis als Symbole;
- gleichförmige Knöpfe;
- viele Erklärabsätze in der Oberfläche.

**Vorgehen:**
- **Phase 1:** Entwürfe nur im Scratchpad, zwei Varianten als Bilder neben dem heutigen
  Stand.
- **Marco wählte** Variante A „Beagle“ ohne Einzelwünsche. Lohbraun wird Standard, Blau,
  Grün und Violett bleiben wählbar. „Beagle“ ersetzt den Hintergrund „Warm / Sand“. Die Web-Version
  zieht mit. Alles kommt zusammen mit den heute schon wartenden Korrekturen in einen Build.

**Desktop**
- **Farben und Designs** (`desktop_darstellung.py`):
  - neues Theme `lohbraun` („Lohbraun (Standard)“, #8C5A32);
  - neues Design `beagle` („Beagle (Standard)“, Creme #FBF8F3, Kopf Anthrazit #2F2B27). Es
    ersetzt `sand`; ein gespeichertes `sand` wird zu `beagle`;
  - „Hell“ (ohne Zusatz), „Dunkel“ und „Hoher Kontrast“ bleiben und bekommen eigene Kopffarben;
  - neue Schlüssel KOPF, KOPF_TEXT, KOPF_TEXT2, KOPF_RAND, KOPF_HOVER, KARTE, GRUPPE_TITEL sowie
    der Schalter `eigene_haken`;
  - Gruppen erscheinen als Karten mit braunem Titel, die Reiter-Linie ist 3 px breit;
  - Zahlenfelder haben eigene Pfeile;
  - ein nicht als Text gespeicherter Registry-Wert ergibt jetzt den Standard statt eines
    TypeError.
- **Kopfbalken** (`KopfBalken` in `desktop_gemeinsam.py`):
  - links der Beagle, rund, dann Verein, darunter Datum · Ort · Teilnehmerzahl (in der Demo mit
    „DEMO“ davor);
  - rechts die Knöpfe mit Symbolen;
  - er aktualisiert sich beim Terminwechsel, nach dem Bearbeiten der Veranstaltung, beim
    Reiterwechsel und nach Änderungen an Teilnehmern;
  - das Startfenster hat ihn ebenfalls („SHS-Prüfungsprogramm – Prüfungen im Spürhundsport
    verwalten“).
- **Symbole statt Emojis:**
  - Tabler Icons 3.49.0 (MIT, unverändert) liegen im neuen Ordner `symbole/`, werden je Design
    eingefärbt (`symbol()`, `symbol_html()`), über `build.spec` gebündelt und in
    `THIRD_PARTY_LICENSES.txt` aufgeführt (Desktop und Web);
  - der Selbsttest hat den neuen Schritt „Symbole“;
  - ersetzt wurden die Emojis in Kopf- und Demo-Knöpfen, an „bezahlt“, an der Chip-Warnung, im
    Speicher-Status, in den Zeitplan-Pfeilen und -Blockköpfen, in den „Offenen Starts“ und am
    KI-Umschalter.
- **Kurze Hinweise:** Zeitplan, Verwaltung und Datensicherung zeigen statt langer Absätze eine
  Zeile mit „?“; der volle Text steht im Tooltip (`kurzer_hinweis()`).

**Web**
- Der Kopf zeigt den Beagle (`static/beagle.png`, 96 px), den Verein und darunter Datum · Ort.
  Das gilt für die Teilnehmerliste und, neu, für die Ergebnisseite.
- Farben wie am Desktop, Karten mit leichtem Schatten, „bewertet“ mit Haken.
- Die Navigation trennt per Abstand statt mit „·“, weil bei Umbruch am Tablet sonst ein Punkt
  allein am Zeilenende stand.
- Das Containerfile kopiert `static/` und die Tabler-Lizenz.

**Tests, Prüfung, Doku**
- **Tests:**
  - `test_theme.py`: Referenz-Stylesheet für den neuen Standard, Umzug sand→beagle, Kontraste
    der neuen Farben in allen Designs;
  - `test_app_gui.py`: 16 neue Tests (Kopfbalken, Symbole, kurze Hinweise, Umfärben beim
    Designwechsel, Selbsttest „Symbole“), Emoji-Texte angepasst;
  - `test_app_web.py`: `TestErscheinungsbild` mit 7 Tests;
  - `test_drittlizenzen.py`: Tabler in der Übersicht.
- **Ergebnis:** Lokal grün, 704 Unittests und 465 GUI-Tests. Der Selbsttest aus dem
  Quellstand ist vollständig OK, einschließlich „Symbole“.
- **Am echten Windows angesehen:** alle vier Hintergründe mit Lohbraun; alle lesbar.
- **Bilder:** Alle 20 Handbuch-Bilder sind neu.
  - Die 15 Desktop-Bilder entstanden mit `tools/screenshots.py`.
  - Die 5 Web-Bilder entstanden aus dem Testaufbau von `test_app_web.py` (SQLite statt
    PostgreSQL), aufgenommen mit Edge headless in den bisherigen Größen. Das Skript dafür lag
    nur im Scratchpad.
- **Doku:**
  - `docs/HANDBUCH.md`: Kopfbalken, „?“-Hinweise, Menü „Ansicht“, Emoji-Namen entfernt;
  - README, `docs/index.html` (geht erst mit dem Release online), `Architektur.md`
    (`symbole/`, `static/`, neue Helfer), `UML.md` (`KopfBalken`, Mermaid geprüft).
- Programmcode und Bilder bleiben bis zum Build uncommittet.
- **Verifikation** (Agent `verifikation`): kein funktionaler Fehler.
  - **Direkt nachgezogen:**
    - Handbuch („Weiter“/„Fertig“ ohne Zeichen);
    - ein Theme-Wert, der kein Text ist, ergibt den Standard (wie beim Design), mit Test;
    - Test für ein nicht schreibbares Symbol-Bild: Die Zeitplan-Seitenleiste fällt auf die
      Zeichen ✓/✗ zurück;
    - die 7 ungenutzten SVGs entfernt (es bleiben 12);
    - veraltete Kommentare (Akzentfarbe statt „blau“, Termin auf der Ergebnisseite,
      Abhängigkeiten von `desktop_gemeinsam`), Typangabe `_pfeil_farben`, UML-Signatur.
  - **Bewusst so gelassen:** `PySide6.QtSvg` wird auf Modulebene importiert, damit PyInstaller
    es sicher mitnimmt; fehlt es, startet das Programm nicht, und der Selbsttest der
    gebauten Fassung fällt das vorher auf. Die Komponentendiagramme zeigen die Abhängigkeit
    `desktop_gemeinsam` → `desktop_darstellung` nicht; sie waren schon vorher nicht
    vollständig.
- **Lokal nicht prüfbar:** PyInstaller-Build und Container-Build. Beides prüft die CI beim
  nächsten Build bzw. Probelauf; der Selbsttest-Schritt „Symbole“ zeigt dabei, ob QtSvg und
  die SVGs gebündelt sind.
- **Build-Vorbereitung 1.0.53 (Marco):**
  - **Vorher umgesetzt:** vier ältere Kleinigkeiten, die auf den neuen Bildern sichtbar waren:
    - Zeitplan-Listen brechen lange Blockköpfe um;
    - das Startfenster hat keine Zeilennummern mehr;
    - der KI-Umschalter ist wirklich flach;
    - lange Pfade im Demo-Erklärfenster bekommen Umbruchstellen.
    Dazu ein gemeinsamer Test.
  - **So belassen:** QtSvg-Import auf Modulebene, Diagramme, Kurztexte, Symbole,
    Kopffarben, Web-Datum ohne Wochentag.
  - **CI-Probelauf vor dem Tag:** Marco pusht `main` ohne Tag und startet „Installer bauen“
    per „Run workflow“. Getaggt wird erst, wenn alles grün ist.

## Version 1.0.53

**Gebündelt sind** (Details in den Abschnitten vom 01.11.2026 oben):
- **Lizenzen:** Lizenzfenster im Versionsfenster, Lizenzseite im Windows-Setup,
  Lizenzvereinbarung in der .dmg, `LICENSE` in allen Paketen, Web-Seite `/lizenzen`.
- **Durchgang der offenen Punkte:**
  - PDF-Layout: Vereinsspalte, Widerristhöhe, Bindestrich-Trennung, Etiketten;
  - Erklärfenster der Demo: Text vollständig, „Weiter“ an fester Stelle;
  - Rückfrage beim Entfernen im Zeitplan;
  - neue Tests für Zeitplan, Datensicherung und Dialoge.
- **Neues Erscheinungsbild „Beagle“** für Desktop und Web, dazu vier Kleinigkeiten aus der
  Build-Vorbereitung.
- `RELEASE_NOTES.md` ist neu geschrieben, die Version ist erhöht, und alle 20 Handbuch-Bilder
  sowie `docs/HANDBUCH.pdf` sind neu.
- **Tests lokal:** 704 Unittests (175 übersprungen) und 466 GUI-Tests grün.
- Vor dem Tag folgt der CI-Probelauf auf `main`; siehe die Build-Vorbereitung oben.
- **CI-Probelauf 1.0.53, erster Versuch:** Der Job `test-windows` schlug in
  `test_screenshot_skript_erzeugt_alle_bilder` fehl. Alle 15 Bilder entstanden, das Skript
  endete aber mit 0xC0000005 (Zugriffsverletzung beim Beenden von Python).
  - **Nachgestellt** mit Python 3.12 und PySide6 6.12.0 (wie in der CI) in einer eigenen venv
    im Scratchpad. Der Absturz trat in etwa jedem zweiten Lauf auf, nur beim Startfenster-Bild
    und erst seit dem neuen Erscheinungsbild. Der Stand davor stürzte in 10 Läufen nie ab.
  - **Ausgeschlossen:** Symbol-Zwischenspeicher, Kopfbalken, Symbole, QtSvg-Import,
    Stylesheet-Bilder und Design (auch „Hell“ stürzt ab).
  - **Ursache:** Ohne Ereignisschleife löscht `deleteLater()` die Fenster nie. Sie blieben bis
    zum Aufräumen von Python nach der QApplication liegen.
  - **Behebung:** `tools/screenshots.py` löscht am Ende alle Fenster und fährt Qt geordnet
    herunter (`_sauber_beenden`). Danach endeten 8 von 8 Läufen sauber.
  - **Das Programm selbst ist nicht betroffen:** Der echte Ablauf (Startfenster mit Terminen,
    Hauptfenster, Schließen) und der Selbsttest endeten unter PySide6 6.12 jeweils 6 bis 8
    Mal sauber.

## 01.11.2026: 1.0.53 ausgeliefert

- **CI-Probelauf:** Marco hat den Branch `probe-1.0.53` mit dem Nachtrag `9aad480` gepusht.
  „Installer bauen“ (41315235161) und „Tests“ waren grün, `test-windows` eingeschlossen.
- **Danach** hat Marco `main` gepusht, `v1.0.53` getaggt und den Probe-Branch gelöscht.
- **Tag-Lauf:** „Installer bauen“ (41316999967) ist mit allen Jobs grün: build, build-macos
  für Apple Silicon und Intel, build-linux, release. „Tests“ und „Container bauen“ sind
  ebenfalls grün.
- **Release v1.0.53** ist veröffentlicht mit Setup, zwei .dmg, AppImage und .deb.
- **Selbsttests:** Jeder meldet „OK Symbole“, unter Windows, auf beiden Macs und unter Linux
  (gebauter Ordner, AppImage, .deb). QtSvg und die SVGs sind also überall gebündelt.
- **Mit dem Release ist auch die Website online:** Handbuch, Bilder und neuer Look.
- **Offen:**
  - A10: Lizenzseite beim nächsten Update im echten Setup ansehen;
  - A1 (Mac/Linux, jetzt auch die .dmg-Lizenzabfrage);
  - Quellcode-Spiegel und claude.ai-Ablage nachziehen.

## 01.11.2026: A10 erledigt, Quellcode-Spiegel auf 1.0.53

- Marco hat die Lizenzseite im echten Windows-Setup von 1.0.53 angesehen: erledigt.
  `OFFEN.md` A10 ist gestrichen.
- `SHS-Pruefungsprogramm-Quellcode` ist nach der bisherigen Regel nachgezogen: alle Dateien aus
  Git außer `.claude/`, die Workflows zusätzlich im Wurzelordner. Im Spiegel wurde nichts
  gelöscht.
- **22 Dateien sind neu:**
  - `symbole/` (14);
  - `static/beagle.png`, `templates/lizenzen.html`, `tools/dmg_einstellungen.py`,
    `berichte/Abdeckung-2026-11.md`;
  - `testdaten/altversionen/v1.0.53/` (4).
- **61 Dateien sind geändert**, dazu `build-installer.yml` im Wurzelordner. Der Byte-Abgleich
  danach ist identisch.
- Die claude.ai-Ablage „SHS“ kann diese Sitzung nicht erreichen. Marco lädt dort
  `Fortschritt.md` und `Architektur.md` neu hoch (`Grobkonzept.md` ist unverändert).
- Marco hat die claude.ai-Ablage „SHS“ aktualisiert. Damit ist 1.0.53 vollständig abgeschlossen.

## 01.11.2026: Kleine Überraschung für Kenner (Marco)

- Auf Marcos Wunsch bewusst nirgends sonst dokumentiert, Details im Code (`desktop_beagle.py`,
  eingebunden im HauptFenster). Verifiziert, die Punkte der Verifikation sind umgesetzt.

## Version 1.0.54

- Kleine Erweiterung der Desktop-Oberfläche (siehe Abschnitt oben); Release Notes bewusst
  allgemein.
- Version erhöht, Handbuch-Bilder und `docs/HANDBUCH.pdf` mit der neuen Versionsnummer neu.
- **Tests lokal:** 704 Unittests (175 übersprungen) und 473 GUI-Tests grün.
- Vor dem Tag folgt ein CI-Probelauf auf `probe-1.0.54`.

## 01.11.2026: 1.0.54 ausgeliefert, Quellcode-Spiegel auf 1.0.54

- Marco hat den Probelauf auf `probe-1.0.54` grün abgeschlossen, `main` gepusht und
  `v1.0.54` getaggt.
  - Release v1.0.54 ist mit allen 5 Dateien veröffentlicht.
  - „Installer bauen“ (41325434595), „Tests“ und „Container bauen“ sind grün.
  - Der Probe-Branch ist gelöscht.
- `SHS-Pruefungsprogramm-Quellcode` ist nach der bisherigen Regel nachgezogen: alle Dateien aus
  Git außer `.claude/`, die Workflows zusätzlich im Wurzelordner. Im Spiegel wurde nichts
  gelöscht.
- 5 Dateien sind neu (`desktop_beagle.py`, `testdaten/altversionen/v1.0.54/` mit 4 Dateien),
  22 sind geändert. Der Byte-Abgleich danach ist identisch.
- Die claude.ai-Ablage „SHS“ kann diese Sitzung nicht erreichen. Marco lädt dort
  `Fortschritt.md` neu hoch; `Architektur.md` und `Grobkonzept.md` sind unverändert.

## 01.11.2026: ToDo-Liste PO_01012027 (neue Prüfungsordnung, Marco)

- Ab 01.01.2027 kommt voraussichtlich eine neue PO. Die nötigen Anpassungen sammelt die neue
  Datei `PO_01012027.md`, auf die `OFFEN.md` (Abschnitt PO), `CLAUDE.md` und `AGENTS.md` verweisen.
- Punkt PO1: Das Stechen bei Gleichstand um Platz 1 (S1, 03.10.2026) entfällt. Marcos Entscheidungen:
  - Die Umschaltung erfolgt über das Veranstaltungsdatum (ab 01.01.2027 gilt die neue PO), ältere
    Prüfungen behalten ihr Stechen. Die Vorbereitung kann deshalb schon jetzt eingebaut werden.
  - Die Gleichstandsregel der neuen PO ist noch unbekannt. Bis dahin gilt ein geteilter Platz 1.
- Die Umsetzung ist geplant (Ablauf in `PO_01012027.md`) und erfolgt in einem eigenen Schritt.

## 01.11.2026: PO1 umgesetzt: Stechen entfällt ab 01.01.2027 (vorbereitet, noch inaktiv)

- `shs_core.py`: `PO_2027_STICHTAG` und `stechen_gilt(datum)` sind neu (ohne Datum gilt weiter das
  Stechen). `berechne_rangliste(..., mit_stechen=True)` lässt bei `False` den Stechen-Block weg,
  dann gilt geteilter Platz 1 (1., 1., 3.). `stechen_gruppen()` liefert nur noch Gruppen mit
  Stechen-Vermerk, ohne Stechen also nichts.
- `db.py`: `stechen_gilt_fuer_veranstaltung(conn)` liest das Veranstaltungsdatum, ein unlesbares
  Datum zählt wie keines. `berechne_auswertung()` übergibt das Ergebnis. Schema und Migration sind
  unverändert, ein gespeicherter `stechen_sieger` wird ab der neuen PO nur nicht ausgewertet.
- Desktop: Der Knopf „Stechen-Sieger festlegen…“ ist ab der neuen PO ausgeblendet. Hinweis und
  Rückfrage vor dem Druck entfallen über `stechen_gruppen()` von selbst. Hilfetext ist ergänzt.
- Demo (Marcos Entscheidung): Sie spielt weiter „heute“ und nutzt dieses Datum jetzt durchgehend
  (`self._heute`). Ab 01.01.2027 erklärt Schritt 12 den geteilten Platz 1 statt einen Sieger
  einzutragen. Ohne diese Änderung wäre die Demo ab 2027 bei Schritt 12 mit „kein offenes Stechen“
  abgebrochen.
- PDF und Weboberfläche brauchen keine eigene Änderung (`platz_text()` ohne Vermerk).
- Dokumentation: `docs/HANDBUCH.md` (Auswertung, Glossar), `Architektur.md`, `UML.md` (Mermaid
  mit mmdc geprüft) und `PO_01012027.md` sind nachgezogen. Handbuch-Screenshots sind nicht
  betroffen, weil sich vor dem Stichtag nichts Sichtbares ändert.
- Tests: Stichtag-Grenzen, Rangliste mit und ohne Stechen (`test_shs_core`), Demodaten auf beiden
  Seiten des Stichtags samt ignoriertem Sieger (`test_db`, der bisherige Demo-Stechen-Test ist jetzt
  fest auf den 31.12.2026 datiert, sonst wäre er ab 2027 rot geworden), PDF-Ergebnisliste ab 2027
  (`test_pdf_export`), Auswertung ab 2027 ohne Knopf und Rückfrage sowie der Demo-Durchlauf für
  31.12.2026 und 02.01.2027 (`test_app_gui`). Die Gegenprobe mit umgedrehtem Datumsvergleich
  scheitert wie erwartet.
- **Tests lokal:** 710 Unittests (175 übersprungen) und 476 GUI-Tests grün.
- Nicht committet und nicht ausgeliefert, bis Marco einen Build anfordert.
- Verifikation (Subagent `verifikation`): kein Logikfehler, 710 Unittests und 477 GUI-Tests grün.
  Alle vier Kleinpunkte setzt Marco um (01.11.2026): fehlendes Leerzeichen in `shs_core.py`,
  Handbuch-Demoliste mit „(bei Prüfungen bis Ende 2026)“, neutraler Demo-Text ab 2027 („entfällt
  das Stechen“ statt „gilt die neue Prüfungsordnung“, Schritttitel „12. Stechen“ bleibt) und ein
  Test für ein unlesbares Veranstaltungsdatum.

## 01.11.2026: Abgleich der aktuellen PO (01.07.2022) mit dem Programm

- Marco hat die VDH-Spürhundesport-PO vom 01.07.2022 bereitgestellt. Sie liegt nur lokal in
  `_unveroeffentlicht/PO/` (öffentliches Repo, fremdes Dokument).
- Der Regelkatalog R1–R24 steht in `PO_01012027.md`. Je Regel sind Fundstelle, Umsetzung im
  Programm und Status eingetragen.
- Ergebnis: Bewertung, Punktgrenzen, Prüfungsarten, Behältnis-Anzahl, 36 Abteilungen je Richter
  und das Anmeldeformular passen. Die Notengrenzen stehen nicht in der PO, sie stammen aus den
  Bewertungsbögen.
- Viele organisatorische Regeln sind bewusst nicht abgebildet. Die Prüfungsleitung regelt sie selbst,
  zum Beispiel Mindestalter, 2 Hunde je Hundeführer, 8 Teilnehmer und läufige Hündinnen.
- Marcos Entscheidungen:
  - R4: Die PO kennt kein Stechen (gleich platzieren, frei gewordene Plätze nicht vergeben).
    Das Stechen bleibt trotzdem bis Ende 2026 und entfällt ab 01.01.2027 wie in PO1 geplant.
  - R5: Ein Team startet nur in einem Wettkampf. „Alle Starts“ in der PO meint die drei Teile
    eines Dreikampfs. Das Programm setzt das schon um, weil eine Disqualifikation für den ganzen
    Start gilt.
- Noch offen: R7 (Abbruch wegen Verletzung/Krankheit mit Teilbewertung) und, ob einzelne
  „nicht abgebildet“-Punkte als Hinweis sinnvoll wären. Außerdem sind die Seiten 23–24 der PO ein
  Entwurfsanhang (Sozialverträglichkeit, Siegerehrung, Teilnahmebedingungen mit Fragezeichen).
  Laut Marco sind das keine Vorarbeiten zur neuen PO.
- Marco 01.11.2026: R7 (Abbruchgründe mit Teilbewertung) wird schon jetzt eingebaut, unabhängig
  von der neuen PO. Die fachlichen Rückfragen dazu folgen vor der Umsetzung.

## 01.11.2026: R7 umgesetzt: Abbruchgründe mit Teilbewertung (PO II.3.4/II.3.5)

- Marcos Entscheidungen:
  - Gründe: Ungehorsam, Verletzung Hund, Krankheit, Verletzung HF, mit dem Eintrag laut PO.
  - Teilbewertung: Die bis dahin eingetragenen Punkte werden samt Summe gezeigt, nie bestanden,
    keine Note, kein Platz.
  - Ungehorsam: Fertige Disziplinen behalten ihre Punkte, die abgebrochene bleibt leer.
  - Eingabe: Auswahlliste statt Häkchen.
- Daten: neue Spalte `ergebnisse.abbruch_grund` mit CHECK auf die vier Codes. Der CHECK gilt
  nur in neu angelegten Termin-Dateien, denn die Migration über `_ERGEBNISSE_NEUE_SPALTEN`
  ergänzt nur die Spalte. Für bestehende Dateien prüfen `setze_ergebnis_status` und die Leser,
  die unbekannte Codes als „ohne Grund“ behandeln. `abbruch` bleibt zusätzlich 1, damit ältere Versionen „Abbruch“
  zeigen. `setze_ergebnis_status(..., abbruch_grund=)` prüft den Code.
  `berechne_auswertung()` bildet mit Grund eine Teilbewertung (`Wertnote.teilbewertung`,
  Summe über `_teilpunkte`, leere Felder 0, Text aus `shs_core.ABBRUCH_GRUENDE`).
  Disqualifiziert geht weiter vor.
- Daten vor R7 (Abbruch ohne Grund) bleiben wie bisher: Punkte gesperrt, „–“. In der
  Auswahlliste heißt das „Abbruch (ohne Grund)“ und wird nur in solchen Zeilen angeboten.
- Desktop-Erfassung (`app.py`): `_AbbruchItem`/`_AbbruchDelegate` (Auswahlliste, Leertaste öffnet
  sie, Entf nimmt den Abbruch zurück). Gesperrt sind die Punkte nur noch bei Disqualifiziert und
  Abbruch ohne Grund (`_punkte_gesperrt`). Die Spalte ist breiter („Verletzung Hund“).
- Auswertung und PDFs: Punkte und Eintrag laut PO in Auswertung, Ergebnisliste und Bewertungsbogen
  (ED: „35 Punkte – Abbruch wegen Krankheit (ABBR)“, DK-GESAMT: Summe mit Eintrag). Etiketten
  zeigen die Teilpunkte je Disziplin. Im Gesamtfeld bleibt „ABBR“, weil eine Summe im 7-pt-Feld
  umbrechen würde. Die Statistik zählt weiter eine Zeile „Abbruch“.
- Web: unverändert (C5, Status nur am Desktop). Zurückholen übernimmt weiter nur Punkte.
- Tests: Teilbewertung DK/ED, Vorrang DQ, ungültiger Code, CHECK (`test_db`, auch PostgreSQL in
  der CI), Ergebnisliste, Etiketten und Bewertungsbögen (`test_pdf_export`), Altdaten-Spalte seit
  1.0.55 (`test_altversionen`), Auswahlliste, offene Punkte, Speichern, Neuladen, Entf und alter
  Abbruch ohne Grund (`test_app_gui`). Der Leertasten-Test prüft jetzt die DQ-Spalte. Die
  Gegenprobe (Teilbewertung bzw. offene Punkte abgeschaltet) scheitert wie erwartet.
- **Tests lokal:** 717 Unittests (177 übersprungen) und 478 GUI-Tests grün.
- Vor dem Build: Handbuch-Screenshot der Ergebniserfassung neu aufnehmen, weil die Abbruch-Spalte
  jetzt Text statt Häkchen zeigt.
- Verifikation (Subagent `verifikation`): Marco hat alle Befunde zur Umsetzung freigegeben
  (01.11.2026).
  - 1 (hoch): Wer erst Punkte eintrug und dann einen Grund wählte, verlor die ungespeicherten
    Punkte. `_status_umgeschaltet` füllt jetzt nur beim Übergang gesperrt → entsperrt aus der
    DB auf.
  - 2: Pfeiltasten, Buchstaben und Mausrad im zugeklappten Feld übernehmen keinen Grund mehr
    (`_AbbruchAuswahl`). Die Liste klappt gleich auf, übernommen wird mit Enter oder Klick.
  - 3: Demo-Schritt 9 beschreibt Auswahlliste und Teilbewertung.
  - 4: Die UML-Diagramme zeigen `_AbbruchItem`/`_AbbruchDelegate`.
  - 5: Der CHECK gilt nur in neuen Dateien (oben klargestellt).
  - 7: Typangaben, Kommentare und Docstrings in `app.py` sind berichtigt.
  - 8: Die Abbruch-Spalte ist breiter, damit die offene Auswahlliste Platz hat.
  - 9: Die GESAMT-Zeile im DK-Bogen ist senkrecht mittig ausgerichtet.
  - 6 (Marcos Entscheidung): Suche und Anzeige gehören auch bei einer Teilbewertung zusammen.
    Ein fehlender Teil wird mit 0 eingetragen, Handbuch und Hilfetext sagen das.
  - Neue Tests: „erst Punkte, dann Grund wählen/wechseln/zurücknehmen“ und „Pfeiltaste im
    zugeklappten Feld übernimmt nichts“. Die Gegenprobe für beide Befunde scheitert wie erwartet.
  - **Tests lokal danach:** 717 Unittests (177 übersprungen) und 480 GUI-Tests grün, UML mit mmdc
    geprüft.
- Nachprüfung (Subagent `verifikation`): Befunde 1–9 sind korrekt behoben, kein neuer Fehler.
  Die drei Kleinigkeiten setzt Marco um:
  - Handbuch: Satz zu Tab bei aufgeklappter Liste (der erste Tab schließt nur die Liste);
  - zwei veraltete Kommentare in `app.py`;
  - GUI-Test „Enter in der aufgeklappten Liste übernimmt den Grund“.
  - Alle drei sind umgesetzt. Danach waren 481 GUI-Tests grün, die Gegenprobe zum Enter-Test
    scheitert wie erwartet.

## 01.11.2026: Projektwebseite an das Erscheinungsbild „Beagle“ angeglichen (Marco)

- `docs/assets/site.css`:
  - Farben aus Programm und Weboberfläche: Creme #FBF8F3, Lohbraun #8C5A32, dunkles Lohbraun
    #6A4325 für Links und Wertnoten, Kopf Anthrazit #2F2B27;
  - warme dunkle Variante;
  - Kopf in Anthrazit mit 3-px-Lohbraun-Linie;
  - Funktionen als Karten mit leichtem Schatten.
- Der runde Beagle (`docs/assets/beagle.png`, Kopie von `static/beagle.png`) ersetzt das Kürzel
  „SHS“ im Kopf aller fünf Seiten. Die Behältnis-Seite (3D-Werkzeug) behält ihren eigenen Stil.
- Kontraste nach WCAG geprüft: hell mindestens 5,5:1, dunkel mindestens 7,1:1.
- Vorher/Nachher hell, dunkel und Handy mit Edge headless angesehen.
- Commit aa21fc6 ist gepusht. Das ist eine reine Website-Änderung, das Design ist seit 1.0.53
  ausgeliefert. `docs/HANDBUCH.md` blieb bewusst draußen, weil die Datei die noch nicht
  ausgelieferten R7-Änderungen enthält.

## 01.11.2026: Vor-Build-Verifikation 1.0.55 und Marcos Entscheidungen

- Die Verifikation über alles seit 1.0.54 findet keinen Logikfehler. Marco hat alle Auffälligkeiten
  zur Umsetzung freigegeben:
  - 1 + 2: Alle Desktop-Screenshots werden neu aufgenommen. In den Testdaten von
    `tools/screenshots.py` hat Greta (ED LK 2 Fläche) einen Abbruch „Verletzung Hund“ mit
    Teilpunkten.
  - 3: R6 im Regelkatalog ist jetzt „umgesetzt (über R7)“.
  - 4: In der Abbruch-Liste klappen Umschalt, Strg, Alt allein und Kürzel mit Strg/Alt die Liste
    nicht mehr auf, sie werden durchgereicht (Strg+S, Umschalt+Tab). Neuer GUI-Test.
  - 5: `QTimer.singleShot` hat das Auswahlfeld als Kontextobjekt.
  - 6: GUI-Test für die Teilbewertung im Reiter „Auswertung“.
  - 7: `tools/altdaten_erzeugen.py`: Emil bekommt ab 1.0.55 einen Abbruch „Verletzung Hund“ mit
    Teilbewertung (neuer `kann`-Schlüssel `abbruchgrund`). `test_altversionen` prüft das, ältere
    Altdaten bleiben „ausstehend“.
  - 8: Der Selbsttest legt einen dritten Teilnehmer mit Abbruch und Grund an und druckt dessen
    Bewertungsbogen. Erwartet werden V/SG/ABBR, die CSV- und Sicherungsprüfungen zählen jetzt 3.
  - 9 + 10: `Architektur.md` und das UML-Klassendiagramm kennen `_AbbruchItem`,
    `_AbbruchDelegate` und `_AbbruchAuswahl` (Mermaid geprüft).
  - 11: Drei veraltete Kommentare in `db.py` und `desktop_auswertung.py` sind berichtigt.
  - 12: Die Restpunkte sind oben als erledigt vermerkt.
  - 13: Die Release Notes nennen die Etiketten.
- Die Gegenproben für die neuen Tests zu 4 und 6 scheitern wie erwartet.

## Version 1.0.55

- **R7 Abbruchgründe mit Teilbewertung** nach der PO (Ungehorsam, Verletzung Hund, Krankheit,
  Verletzung HF), Auswahlliste in der Ergebniserfassung, Teilpunkte auf Auswertung, Ergebnisliste,
  Bewertungsbogen und Etiketten. Neue Spalte `ergebnisse.abbruch_grund`.
- **PO1:** Ab Veranstaltungsdatum 01.01.2027 entfällt das Stechen um Platz 1 (vorbereitet,
  bis dahin wirkungslos).
- **Regelkatalog** aktuelle PO ↔ Programm in `PO_01012027.md`.
- Alle Befunde der Vor-Build-Verifikation sind umgesetzt (siehe Abschnitt oben).
- Die Version ist erhöht. Alle 15 Desktop-Screenshots sind neu, darunter die Ergebniserfassung
  mit der Abbruch-Auswahlliste und die Auswertung mit Teilbewertung. `docs/HANDBUCH.pdf` ist
  neu, `RELEASE_NOTES.md` ist neu geschrieben.
- **Tests lokal:** 717 Unittests (177 übersprungen) und 483 GUI-Tests grün, UML mit mmdc geprüft.
- Vor dem Tag folgt ein CI-Probelauf auf `probe-1.0.55`.

## 01.11.2026: 1.0.55 ausgeliefert, Quellcode-Spiegel auf 1.0.55

- Marco hat den Probelauf grün abgeschlossen, `main` gepusht und `v1.0.55` getaggt.
  - Das Release v1.0.55 ist mit allen 5 Dateien veröffentlicht (Windows-Setup, 2× .dmg,
    AppImage, .deb).
  - „Installer bauen“, „Tests“ und „Container bauen“ sind grün.
  - Der Branch `probe-1.0.55` besteht noch (Löschen ist Marcos Aktion).
- `PO_01012027.md` (PO1, R6, R7) und `OFFEN.md` stehen auf „ausgeliefert mit 1.0.55“.
- `SHS-Pruefungsprogramm-Quellcode` ist nach der bisherigen Regel nachgezogen: alle Dateien aus
  Git außer `.claude/`, die Workflows zusätzlich im Wurzelordner, im Spiegel nichts gelöscht.
  - 6 Dateien sind neu: `PO_01012027.md`, `docs/assets/beagle.png` und
    `testdaten/altversionen/v1.0.55/` mit 4 Dateien.
  - 45 Dateien sind geändert.
  - Der Byte-Abgleich danach ist identisch.
- Die claude.ai-Ablage „SHS“ kann diese Sitzung nicht erreichen. Marco lädt dort
  `Fortschritt.md` und `Architektur.md` neu hoch (`Grobkonzept.md` ist unverändert).

## 03.11.2026: UX-Test 1.0.55 mit sechs Personas (nur Dokumentation, kein Code geändert)

Marcos Wunsch: Seit dem UX-Test vom Oktober hat sich viel geändert, deshalb ein neuer Test.

- **Rahmen (mit Marco abgestimmt):**
  - Alle sechs Personas wie im Oktober (je Gruppe mit und ohne Handbuch), nacheinander wegen des
    Nutzungslimits.
  - Zusätzlich im Szenario: Demoprüfung bis zum Ende, Stechen und Abbruch mit Grund,
    Startnummern-Bereiche und eine späte Nachmeldung.
  - Desktop-App 1.0.55 echt bedient, unsichtbar (Qt offscreen 1920×1080) in einer Sandbox je
    Persona. Das Steuerwerkzeug ist neu gebaut und liegt nur im Scratchpad, nicht im Repo.
  - Installation nur gedanklich. Ergebnis: ein Bericht, keine Code-Änderungen.
- **Ablauf:**
  - Nach dem ersten Lauf (Heinz) wurden Fehler des Werkzeugs behoben: Umlaute (QTest-ASSERT),
    Zeitplan-Reiter, Häkchen, Tabelleneingabe. Heinz' gemeldeter „Absturz bei Umlauten“ war ein
    Werkzeugfehler; er hat die Zeitplan-Aufgabe danach nachgeholt.
  - Ab Julia schrieb das Werkzeug die Demo-Texte in Echtzeit mit.
  - Gerda wurde nach einem API-Limit fortgesetzt, nicht neu gestartet.
  - Danach habe ich zusammengeführt und die Hauptfunde gegen Code, `OFFEN.md` und den Oktober-Test
    abgeglichen. Der Agent `verifikation` hat den Bericht geprüft (717 Unittests grün). Seine
    31 Korrekturen sind eingearbeitet, u. a.:
    - X1 ist N3 aus dem Nachtest;
    - X8 ist N6, und der Komma-Hinweis verschwindet mit der nächsten Ziffer;
    - X3 ist ein echter Kleinfehler und ein Rest von U11;
    - Zählungen und der Oktober-Abgleich sind berichtigt.
- **Abschottung geprüft:** Echte Termine und die Registry-Darstellung sind unverändert; die
  Einstellungen der Personas landeten in Sandbox-Dateien. Im Repo wurde während des Tests nichts
  geändert.
- **Ablage:** `berichte/UX-Test-2026-11/` mit `Bericht.md` und `personas/` (6 Einzelberichte, lokale Pfade
  anonymisiert). Die Bildschirmfotos bleiben lokal, weil viele den Benutzerpfad zeigen.
- **Noten gesamt:** Erfahrene 2 / 2, Normale 2 / 2, Laien 2–3 / 2– (Oktober: 3+ / 3+, 3+ / 3,
  4 / 3–4).
  - Alle sechs würden den Prüfungstag eher allein schaffen; kein ✗.
  - Am häufigsten „mit Mühe“: Mittagspause (6/6) und ED-Gegenstände (5/6).

## Rubrik ux_test_2026_11 – Aufgabenliste (angelegt 03.11.2026)

Alle Punkte aus `berichte/UX-Test-2026-11/Bericht.md`. Wie beim Oktober-Test: erst alle Punkte einzeln mit
Marco planen (umsetzen / zurückstellen / verwerfen), dann einzeln umsetzen.

**Planung 03.11.2026 (Marco):** Alle Punkte werden umgesetzt, ausgenommen ist die Code-Signatur
(X16, mit dem Installer derzeit nicht lösbar). Abarbeitung limitgesteuert nach dem Skill
`aufgaben-abarbeitung`; Aufgabenliste A1–A12 mit Größen und Entscheidungen in
`berichte/UX-Test-2026-11/aufgaben.md`. Entscheidungen:
- X1: Erreicht der Plan eines Richters die Pausenzeit nicht, bekommt er keine Pause; die Meldung
  nennt, bei wem sie fehlt. Das ersetzt N3.
- X12: Die erste angebotene Prüfung wird vorbelegt, dazu Klartext „angeboten / nicht angeboten“.
- X6: „Vorigen Text zeigen“ statt eines echten Zurück, dazu der Countdown nach Textlänge.
- Zum Schluss ein Nachtest mit zwei Personas.

| Nr | Punkt | Status |
|---|---|---|
| X1 | Mittagspause „um 12:00 bei allen Richtern“ landet am Planende, wenn der Plan früher endet (6/6); öffnet die Nachtest-Entscheidung N3 neu | umgesetzt (A4, Arbeitsstand) |
| X2 | Schrift nicht vergrößerbar; Hilfe „Schrift zu blass oder zu klein? → Hoher Kontrast“ verspricht es; Starttipp verweist auf Menü „Ansicht“, das im Startfenster fehlt (Laien, erheblich) | umgesetzt (A5, Arbeitsstand) |
| X3 | Hinweis „Gegenstand der Suchdisziplin nicht zugeordnet“ direkt nach PDF-Import einer ED-Meldung – echter Kleinfehler (Disziplin bleibt leer), berührt Entscheidung 28.09.; Handbuch „ältere Daten“ (5/6) | umgesetzt (A1, Arbeitsstand) |
| X4 | ED: Gegenstand 2/3 gesperrt ohne Erklärung; zwei Gegenstände landen in Feld 1 (6/6) | umgesetzt (A3, Arbeitsstand) |
| X5 | Spalte „Abbruch“: keine erkennbare Auswahlliste, öffnet erst beim zweiten Klick (Handbuch sagt ein Klick); Spalte zu schmal („Verletzun…“) | umgesetzt (A2, Arbeitsstand) |
| X6 | Demo: 10-s-Countdown zu kurz für 45–90 Wörter, kein „Zurück“, Enter ohne Wirkung (4/6) | umgesetzt (A6, Arbeitsstand) |
| X7 | Punktwert > 60 beim Tippen nur roter Rahmen ohne sichtbaren Text (3/6, teils Testumgebung) | umgesetzt (A2, Arbeitsstand) |
| X8 | „4,5“ wird zu 45; der Komma-Hinweis verschwindet mit der nächsten Ziffer (Wiederholung N6, Gegenprobe am Gerät) | umgesetzt (A2, Arbeitsstand) |
| X9 | „Startnummer tauschen“ (ein Teilnehmer markiert): Partner vorausgewählt, Enter tauscht falsch | umgesetzt (A7, Arbeitsstand) |
| X10 | Übersprungene Import-Meldungen nach „OK“ nicht mehr nachlesbar; Pfeiffer-Meldung ohne Rat | umgesetzt (A8, Arbeitsstand) |
| X11 | Startnummer außerhalb des Bereichs ohne Hinweis angenommen | umgesetzt (A3, Arbeitsstand) |
| X12 | Teilnehmerformular: Prüfung aus Art/LK/Disziplin zusammensetzen, Vorbelegung ED/1/Trümmer, auch nicht angebotene Kombinationen; uneinheitliche Prüfungsnamen | umgesetzt (A3, Arbeitsstand) |
| X13 | Teilnehmerzahl Startbildschirm 17 ≠ Kopfbalken 16 (6/6) | umgesetzt (A7, Arbeitsstand) |
| X14 | Hilfe: lange Textwand ohne Suche; Hilfe und Handbuch widersprechen sich beim Termin-Löschen | umgesetzt (A9, Arbeitsstand) |
| X15 | Kleinigkeiten (Liste im Bericht, Abschnitt 3) | umgesetzt (A9, Arbeitsstand) |
| X16 | Installation für Laien (Browser-/SmartScreen-Warnung, „Assets“, Update-Weg); Code-Signatur ist zurückgestellt (B8) | umgesetzt ohne Signatur (A10, Arbeitsstand) |

### ux_test_2026_11 A1 (X3) – umgesetzt (03.11.2026)

- **Problem:** Nach dem Einlesen eines Anmelde-PDFs mit Einzeldisziplin stand sofort „Gegenstand
  der Suchdisziplin nicht zugeordnet“ in der Teilnehmerliste (5 von 6 Personas). Der Import
  speicherte die Gegenstände nach der Entscheidung vom 28.09. als „frei“.
- **Lösung:** Bei ED wird der eine übernommene Gegenstand gleich der ED-Disziplin zugeordnet, wie im
  Teilnehmer-Dialog (`db_import.py`, `_anmeldeformular_zu_teilnehmer`). Bei DK bleibt er frei.
  Nebeneffekt: Der Bewertungsbogen zeigt bei ED nach dem PDF-Import jetzt den Gegenstand.
- **Handbuch:** Der Hinweis gilt jetzt für ältere Daten oder PDFs, die mit einer älteren Version
  eingelesen wurden. Bei „Übernommen“ steht die ED-Zuordnung.
- **Tests:** `test_vollstaendiges_formular_wird_uebernommen` prüft Zuordnung und keinen Hinweis,
  `test_ed_nur_zweites_gegenstandsfeld_ausgefuellt` die Zuordnung aus Feld 2, neu ist
  `test_dk_gegenstaende_bleiben_frei`. Gegenprobe ohne Fix: 1 Fehlschlag wie erwartet. Lokal
  718 Unittests grün.
- **Verifikation** (Agent `verifikation`): Code korrekt, CSV/OMA nicht betroffen (übernehmen keine
  Gegenstände), 38 gefilterte GUI-Tests grün. Ihre Kleinpunkte (Handbuch Z. ~454, Kommentar,
  versionsfreie Formulierung, Test für Feld 2) sind eingearbeitet.

### ux_test_2026_11 A2 (X5, X7, X8) – umgesetzt (03.11.2026)

- **X5 Abbruch-Zelle:**
  - Sie ist jetzt als Auswahlfeld gezeichnet: umrandet wie die Punktefelder, Dreieck rechts,
    gelb in ungespeicherten Zeilen (`_AbbruchDelegate.paint`).
  - Die Auswahl öffnet schon beim ersten Klick (`ErgebnisTab._abbruch_mit_einem_klick` an
    `tabelle.clicked`).
  - Tooltip mit vollem Grund bzw. „Klicken: Abbruch mit Grund auswählen“.
  - Die Spalte ist 12 px breiter.
- **X7 Wert über dem Maximum:**
  - Zum roten Rahmen kommt ein eigenes rotes Label unter den Knöpfen: „Rot umrandet, so nicht
    speicherbar - bitte korrigieren: Nr. 1 Muster: Flächensuche Suche höchstens 60 Punkte
    (eingegeben: 65)“.
  - Gemerkt wird je Teilnehmer-ID (`_zu_hoch_merken`, übersteht Sortieren), es zeigt höchstens
    drei Einträge und wird beim Neuaufbau geleert.
- **X8 Komma:**
  - Der Hinweis bleibt stehen, bis die nächste Zelle bearbeitet wird. Vorher nahm die nächste
    Ziffer ihn weg; bei „4,5“ wurde unbemerkt 45 daraus.
  - Der Text ergänzt „bitte den Wert in der Zelle prüfen“.
- **Handbuch** (Ergebniserfassung) und **UML** (`_AbbruchDelegate.paint`, Ablauf) angepasst,
  Mermaid mit mmdc geprüft.
- **Tests:** drei neue GUI-Tests:
  - ein Klick öffnet, Tooltip;
  - Klartext mit zwei Zeilen, Komma nebenher, Bearbeiten anderer Zellen;
  - Komma-Hinweis bleibt nach der nächsten Ziffer.
  Dazu kommt ein Test für den Neuaufbau, ein bestehender Test ist angepasst. Die Gegenprobe ohne
  Fix scheitert dreimal. Lokal laufen 488 GUI- und 718 Unittests grün.
- **Verifikation** (Agent `verifikation`): Ihre Befunde sind eingearbeitet:
  - X7 als eigenes Label je Teilnehmer statt eines gemeinsamen Hinweises; das behebt mehrere rote
    Zeilen, Tabwechsel, Neuaufbau und das Überschreiben durch den Komma-Hinweis;
  - gelbe Füllung, Kommentare, Handbuchtext, UML, Name im Hinweis.
  - Nicht eigens getestet: ein Doppelklick auf die Abbruch-Zelle (der erste Klick öffnet schon) –
    beim nächsten Gerätetest ansehen.
- Vor dem nächsten Build ist der Screenshot `handbuch_ergebniserfassung` neu nötig.

### ux_test_2026_11 A3 (X4, X11, X12) – umgesetzt (03.11.2026)

- **X12** (Marcos Entscheidung R2, „vorbelegen + markieren“):
  - Ein neuer Teilnehmer beginnt mit der ersten im Termin angebotenen Prüfung statt mit
    ED/1/Trümmerfeld.
  - Unter „Disziplin“ steht im Klartext „Prüfung: Trümmer LK 2 – wird angeboten“ (grün) bzw.
    „– in diesem Termin NICHT angeboten“ (rot). Ohne hinterlegtes Angebot steht nur der Name.
  - Die drei Felder bleiben.
- **X4:** Bei ED erklären ein Hinweis unter Gegenstand 1 und ein Tooltip an Gegenstand 2/3, warum
  diese gesperrt sind.
- **X11:**
  - Eine Startnummer außerhalb des Bereichs der gewählten Prüfung wird nur nach Rückfrage
    gespeichert (Vorgabe Nein).
  - Die Rückfrage kommt nach „Prüfung nicht angeboten“ und beim Bearbeiten nur, wenn sich
    Nummer oder Prüfung geändert haben.
  - Ist der Bereich voll, schlägt das Programm weiterhin die kleinste freie Nummer insgesamt vor
    und fragt dann beim Speichern nach. Das ist bewusst so gelassen.
- **Weitere Stellen:**
  - `tools/screenshots.py` übergibt das Angebot, damit das Handbuchbild „wird angeboten“ zeigt.
  - Das Handbuch (Erfassungsmaske, Suchgegenstände) ist angepasst.
- **Tests:** 6 neue GUI-Tests:
  - Vorbelegung und Hinweis;
  - ED-Hinweis und Tooltip;
  - Bereich ja/nein;
  - Bearbeiten behält die Prüfung und fragt nur nach einer Änderung;
  - ohne Bereich keine Rückfrage, „Ja“ speichert;
  - Hinweis ohne Angebot.
  Die Gegenprobe scheitert dreifach. Lokal 495 GUI- und 718 Unittests grün.
- **Verifikation** (Agent `verifikation`): Die Befunde sind eingearbeitet (Reihenfolge der
  Rückfragen, Rückfrage nur nach einer Änderung, Kürzel einheitlich, Screenshot-Werkzeug,
  Handbuch, Tests). Ein Handbuchsatz ohne Entscheidung („trägst du den ersten ein“) ist wieder
  gestrichen.
- **Offen als Rückfrage:** Reichen Hinweis und Tooltip für X4, oder sollen die gesperrten Felder
  zusätzlich deutlicher aussehen oder bei ED ganz ausgeblendet werden?
- Vor dem nächsten Build neu nötig: `handbuch_teilnehmer_dialog_ed` und
  `handbuch_teilnehmer_dialog_dk`.

### ux_test_2026_11 A4 (X1) – umgesetzt (03.11.2026)

- **Marcos Entscheidung R3** („Dann weglassen“, ersetzt die Nachtest-Entscheidung N3 „Pause am
  Planende + Meldung“): Ist ein Richter vor der gewünschten Pausenzeit schon fertig (letzter
  Eintrag endet ≤ Uhrzeit) oder hat er keinen Plan, bekommt er bei „Bei allen Richtern einfügen“
  keine Pause mehr. Ein laufender Block bekommt sie weiter direkt danach.
- **Code:** `db.add_zeitplan_pause_bei_allen` liefert je Richter (Name, Startzeit oder None).
  `desktop_zeitplan._pause_hinzufuegen` meldet:
  - wenn niemand eine Pause bekommt: „Keine Pause eingefügt – bei allen Richtern endet der Plan
    schon vor 12:00 Uhr“;
  - sonst je Richter die Zeit bzw. „keine Pause – der Plan endet schon vor … Uhr“.
  Der Hinweis im Pausen-Dialog ist ergänzt.
- **Handbuch:** Kap. Zeitplan und Kap. 14 (Schritt Mittagspause) angepasst. Der Screenshot
  bleibt (im Bild bekommen beide Richter weiter eine Pause).
- **Tests:**
  - `test_pause_bei_allen_laesst_fertige_richter_aus` (Daten, auch Postgres-Klasse):
    fertig/ohne Plan/genau zum Planende;
  - der GUI-Test deckt die Meldung „keine Pause“ und den gemischten Fall ab.
  Die Gegenprobe scheitert wie erwartet. Lokal 495 GUI- und 720 Unittests grün.
- **Verifikation** (Agent `verifikation`): in Ordnung; Hinweistext, Meldung für „niemand“,
  Testkommentar und Typangabe eingearbeitet. Bewusst nicht geändert (selten):
  - Ein leerer Block genau zur Uhrzeit am Planende zählt noch als „nicht fertig“.
  - Der Uhrzeitvergleich über `.time()` würde bei einem Plan über Mitternacht falsch werten
    (schon vorher so).

### ux_test_2026_11 A5 (X2) – umgesetzt (03.11.2026)

- **Problem:** Die Schrift ließ sich nicht vergrößern. Die Hilfe versprach „Schrift zu blass
  oder zu klein? → Hoher Kontrast“, das ändert aber nur die Farben. Der Starttipp verwies auf
  das Menü „Ansicht“, das es im Startfenster nicht gibt (beide Laien-Personas, erheblich).
- **Lösung:**
  - Neues Untermenü „Ansicht → Schriftgröße“ mit Normal / Groß / Sehr groß (Faktor
    1,0 / 1,15 / 1,3), gespeichert in QSettings unter `darstellung/schrift`.
  - `desktop_darstellung._darstellung_anwenden` merkt beim ersten Aufruf die Systemschrift
    (Windows Segoe UI 9) und setzt die Anwendungsschrift auf Basis × Faktor. Das schaukelt
    nicht auf, „Normal“ stellt den Ausgangswert exakt wieder her.
  - `desktop_gemeinsam._responsive_schriftgroesse` (Beschriftungen, Kopfbalken,
    Ergebnistabelle) rechnet mit dem Faktor.
  - `HauptFenster._schrift_wechseln` stößt Beschriftungen und Ergebnistabelle sofort neu an.
  - Hilfe und Starttipp sind berichtigt. Die Hilfe nennt zusätzlich die Windows-Skalierung,
    das Handbuch (Aussehen) beschreibt die dritte Einstellung.
  - `tools/screenshots.py` erzwingt „Normal“, die Test-Fixture `darstellung_speicher` stellt
    die Schrift wieder her.
- **Tests:** neuer GUI-Test (Menü, Speichern, Faktor, Anwendungsschrift und Beschriftungen
  wachsen und gehen zurück). Lokal 496 GUI- und 720 Unittests grün. Sichtprüfung „Sehr groß“
  (Teilnehmer, Ergebniserfassung) in Ordnung.
- **Verifikation** (Agent `verifikation`): Code in Ordnung, Randfälle geprüft (Basis-Schrift,
  kein Aufschaukeln, Dialoge, StartDialog, Testisolation, ungültige Registry-Werte).
  Kleinpunkte (Windows-Hinweis nur „unter Windows“, Docstrings) eingearbeitet. Bewusst gelassen:
  - Der Titel eines gerade laufenden Demo-Fensters wächst erst bei der nächsten Demo mit.
  - Ändert Windows die Systemschrift zur Laufzeit, gilt der neue Wert erst nach einem Neustart.
- **Offen als Rückfrage R6:** Bei „Sehr groß“ und einem nicht maximierten Fenster (1400 px)
  werden die Kopfzeilen der Ergebniserfassung abgeschnitten (bestehende Regel `harte_minima`
  vom 22.09.). Das Handbuch rät zum Maximieren. Alternative: Faktor nur für die Ergebnistabelle
  auf 1,15 begrenzen.
- Vor dem nächsten Build prüfen, ob ein Handbuchbild das aufgeklappte Menü „Ansicht“ zeigt.

### ux_test_2026_11 A6 (X6) – umgesetzt (03.11.2026)

- **Problem:** Die Demo schaltete nach 10 s weiter, viele Erklärtexte haben 45–90 Wörter. Es
  gab kein Zurück, Enter bewirkte nichts (4 von 6 Personas).
- **Lösung** (Marcos Entscheidung R4, „nur Text zurück“):
  - Die Wartezeit richtet sich nach der Textlänge (`DemoTour._wartezeit`: 0,35 s je Wort,
    mindestens `AUTO_WEITER_S` = 10 s, höchstens 40 s; tatsächlich 13–31 s je Schritt).
  - Neuer Knopf „Vorheriger Text“ im Erklärfenster: Er blättert nur die Erklärungen zurück,
    die Demo selbst läuft nur vorwärts. Während des Rückblicks pausiert der Countdown, die
    Hinweis- und Zusatzzeilen des laufenden Schritts sind ausgeblendet, und „Weiter“ heißt
    „Aktueller Schritt“ und führt zurück. Danach zählt der Countdown wieder.
  - Enter wirkt im Erklärfenster wie „Weiter“, bzw. auf den Knopf mit dem Fokus (QShortcut;
    `setDefault` wirkt nur in QDialog).
  - Einführungstext, Tooltip, Modul-Docstring, Handbuch (Demoprüfung) und `Architektur.md`
    sind angepasst. `tools/screenshots.py` friert den Countdown auf die echte Wartezeit ein.
- **Tests:** 4 neue GUI-Tests:
  - Wartezeit nach Textlänge;
  - Rückblick hält an, kehrt zurück, Countdown läuft wieder, Enter-Kürzel;
  - Randfälle (Fehler im Rückblick, Häkchen umschalten, Hinweiszeile, zwei Schritte zurück);
  - Enter auf dem fokussierten Knopf.
  Die Gegenprobe scheitert 4-fach. Lokal laufen 500 GUI- und 720 Unittests grün.
- **Verifikation** (Agent `verifikation`): Befunde 1–5 und 7–10 sind eingearbeitet:
  - eigene Signale für Beginn und Ende des Rückblicks statt dauerhaftem Anhalten;
  - ein Fehler führt zum aktuellen Schritt zurück;
  - kein Countdown über altem Text;
  - Zeilen im Rückblick ausgeblendet;
  - Enter auf dem Fokus-Knopf;
  - Tests und Doku.
  Bewusst gelassen: Der Knopf „Aktueller Schritt“ behält den Vorwärtspfeil.
- Vor dem nächsten Build ist der Screenshot `handbuch_demo` neu nötig (neuer Knopf, echte
  Wartezeit).

### ux_test_2026_11 A7 (X9, X13) – umgesetzt (03.11.2026)

- **X9:** Im Dialog „Startnummer tauschen“ (ein Teilnehmer markiert) ist kein Partner mehr
  vorausgewählt. Die Liste zeigt „– bitte Partner wählen –“, „OK“ ist erst nach einer Wahl
  aktiv, Enter schließt bei gesperrtem OK nichts. Vorher tauschte Enter mit dem ersten Eintrag
  der Liste.
- **X13:**
  - Der Startbildschirm zählt wie der Kopfbalken nur Teilnehmende und zeigt Abgemeldete als
    Zusatz („16 (+1 abgemeldet)“).
  - `TerminInfo` hat dazu `anzahl_abgemeldet` und `teilnehmer_anzeige`. `_termin_info_lesen`
    zählt `COALESCE(keine_teilnahme,0) <> 0`, wie `list_teilnehmer(nur_teilnehmende=True)`.
    Alte Dateien ohne die Spalte ergeben 0.
  - Die Terminauswahl beim Import zeigt „16 Teilnehmer, +1 abgemeldet“.
  - Die Terminliste zählte bisher alle Gemeldeten (Fortschritt ~Z. 2975). Das ist hiermit
    geändert, wie im Plan vom 03.11. vorgeschlagen.
- **Handbuch:** Startbildschirm (Zählweise) und Tauschen („OK“ erst nach der Wahl).
- **Tests:**
  - Daten: Zählung mit Abgemeldeten, Anzeige, alte Datei;
  - GUI: keine Vorauswahl, OK gesperrt, Enter wirkungslos.
  Die Gegenprobe scheitert wie erwartet. Lokal laufen 500 GUI- und 721 Unittests grün.
- **Verifikation** (Agent `verifikation`): in Ordnung. Die Kleinpunkte sind eingearbeitet:
  Zählung wie im Kopfbalken, Property ans Klassenende, Importtext ohne doppelte Klammern,
  Testzusätze.
- **Nicht geändert:** Die Web-Admin- und Terminauswahl-Seiten sowie `sync_termin.py` zeigen
  weiter die Gesamtzahl (Postgres-Variante, nicht Teil des UX-Tests).
- Vor dem nächsten Build ist der Screenshot `handbuch_start` neu nötig (zeigt jetzt
  „(+1 abgemeldet)“).

### ux_test_2026_11 A8 (X10) – umgesetzt (03.11.2026)

- **Problem:** Die Liste abgelehnter bzw. übersprungener Import-Meldungen war nach „OK“ weg. Das
  Symbol war immer „i“, auch bei Ablehnungen, und für Pfeiffer (zwei Prüfungen angekreuzt)
  fehlte der Rat, was zu tun ist. Dazu kamen „1 Teilnehmer haben“ und eine Startnummern-Rückfrage
  nach jedem Einzelimport.
- **Lösung** (`app.py`):
  - `_meldung_mit_listen` kann ein Warnsymbol (`warnung`) und den Knopf „Meldung kopieren und
    schließen“ (`kopieren`, Zwischenablage mit den ungekürzten Listen). OK bleibt Vorgabe, Esc
    schließt (`setEscapeButton`).
  - `_import_ergebnis_melden`: Warnsymbol bei Ablehnungen, ein Abschnitt „Was tun?“
    (`_RAT_BEI_ABLEHNUNG`), Kopierknopf bei Ablehnungen oder Duplikaten.
  - `_startnummern_nach_import_anbieten(…, vorher_ohne)`: Die Rückfrage kommt nur, wenn der
    Import neue Teilnehmer ohne Nummer gebracht hat (`_ohne_startnummer_ids` vor dem Import, an
    allen vier Aufrufern). Die Meldung steht in der Einzahl „hat“.
- **Handbuch** (Abschnitt Import-Meldungen) ergänzt.
- **Tests:**
  - neu: Warnung, Rat und Kopieren samt Esc-Knopf, nur Duplikate; Rückfrage nur bei neuen,
    Einzahl;
  - angepasst: vier Import-Tests über `import_meldungen_sammeln`, Stub-Signatur der
    autouse-Fixture.
  Die Gegenprobe scheitert. Lokal 502 GUI- und 721 Unittests grün.
- **Verifikation** (Agent `verifikation`): Ein echter Fehler (Esc schloss das Fenster mit
  Zusatzknopf nicht) ist behoben. Außerdem: Knopftext „Meldung kopieren und schließen“ statt
  „Liste kopieren“ (er schließt und kopiert die ganze Meldung) und ein neutralerer Rat, der auch
  ganz abgelehnte Dateien abdeckt. Nicht eigens getestet ist der Rückfall `vorher_ohne=None`
  (alte Rückfrage).

### ux_test_2026_11: Rückfragen R5 und R6 entschieden (Marco 03.11.2026)

- **R5 (X4):** Bei ED werden Gegenstand 2 und 3 samt Zuordnung **ausgeblendet** statt nur
  gesperrt; der Hinweis unter Gegenstand 1 bleibt (Aufgabe A3b).
- **R6 (X2):** Bei „Sehr groß“ nutzt die Ergebnistabelle nur Faktor 1,15, **solange das
  Hauptfenster nicht maximiert ist**; maximiert gilt der volle Faktor (Aufgabe A5b).

### ux_test_2026_11 A3b (R5) und A5b (R6) – umgesetzt (03.11.2026)

- **A3b (X4, Marcos Entscheidung R5):**
  - Im Teilnehmer-Dialog werden Gegenstand 2 und 3 bei ED samt Beschriftung ausgeblendet
    (`QFormLayout.setRowVisible`) statt nur gesperrt. Der Hinweis unter Gegenstand 1 bleibt.
  - Stehen bei ED noch Texte in den unsichtbaren Feldern (Altdaten, Wechsel DK → ED), nennt die
    Rückfrage beim Speichern sie jetzt („Gegenstand 2: Korken“).
- **A5b (X2, Marcos Entscheidung R6):**
  - Bei „Sehr groß“ nutzt die Ergebnistabelle nur Faktor 1,15, solange das Hauptfenster nicht
    maximiert ist (`_ERGEBNIS_FAKTOR_NICHT_MAXIMIERT`).
  - Unter Windows kommt beim Maximieren das resizeEvent vor dem Zustandswechsel.
    `HauptFenster.changeEvent` rechnet bei `WindowStateChange` deshalb noch einmal nach.
- **Handbuch:** ED-Gegenstände „ausgeblendet“, Bildunterschrift „nur Gegenstand 1 sichtbar“.
- **Tests:**
  - Ausblenden bei ED/DK;
  - Rückfrage nennt die ausgeblendeten Texte;
  - Faktor 1,15 bzw. 1,3, Neuberechnung bei WindowStateChange.
  Die Gegenprobe scheitert. Lokal laufen alle GUI- und Unittests grün.
- **Verifikation** (Agent `verifikation`): Ein echter Fehler (falscher Fensterzustand beim
  Maximieren unter Windows) ist behoben. Außerdem eingearbeitet: der UX-Randfall der
  unsichtbaren Texte (Rückfrage nennt sie), veraltete Kommentare, die Bildunterschrift und
  try/finally im Test.
- Vor dem nächsten Build ist der Screenshot `handbuch_teilnehmer_dialog_ed` neu nötig.

### ux_test_2026_11 A9 (X14, X15) – umgesetzt (03.11.2026)

- **Hilfe (X14):**
  - Vor dem ersten Abschnitt steht ein Inhaltsverzeichnis mit Sprungmarken auf alle 14
    Zwischenüberschriften (`_hilfe_mit_inhaltsverzeichnis`).
  - „Löschen…“ verschiebt in den Papierkorb (statt „unwiderruflich“).
  - „Automatisch verteilen“ ersetzt den Plan aller Richter.
  - „Bezahlt umschalten“ wirkt auf alle markierten Teilnehmer.
  - Doppelte Abschnitte gab es nicht (Werkzeugeffekt im Test).
- **Kleinigkeiten (X15):**
  - Die Pflichtfeld-Meldung nennt nur die fehlenden Felder, mit den sichtbaren Feldnamen.
  - Termin-Datum: „14.11.26“ wird beim Verlassen des Felds bzw. beim OK zu 14.11.2026 ergänzt.
  - Versionsfenster: „Schließen“ ist Vorgabe, Enter schließt (vorher öffnete Enter
    „Lizenzen“).
  - „Offene Starts“ im Zeitplan ist 280–360 px breit (vorher 230–280).
  - Tooltip am Anmeldeformular: „Im Reiter „Verwaltung“ über „Veranstaltungsdaten
    bearbeiten…“ …“ statt „Dort“.
  - Startbildschirm: Bei genau einem lesbaren Termin ist er gleich markiert, „Öffnen“ ist
    aktiv.
  - Der Dateidialog für Anmelde-PDFs sagt, dass mehrere Dateien mit Strg-Klick gehen.
- **Bewusst unverändert** (Plan): der Name der Sicherungsdatei und die sofortige Spalte bei
  „Richter hinzufügen“. Installationstexte und „GitHub-Releases-Seite“ kommen in A10.
- **Handbuch:** zweistelliges Jahr beim Termin-Datum.
- **Tests:** `test_a9_kleinigkeiten` (Pflichtfelder mit einem und zwei fehlenden Feldern, Datum,
  Inhaltsverzeichnis, Hilfetexte, Versionsfenster) und `test_startdialog_markiert_einzigen_termin`.
  Die Gegenprobe scheitert. Lokal laufen 505 GUI- und 721 Unittests grün (Volltest durch die
  Verifikation).
- **Verifikation** (Agent `verifikation`): in Ordnung. Die Kleinpunkte sind eingearbeitet
  (Feldname „Rufname Hund“, Tooltip mit Knopfname, Hilfe zu „Bezahlt umschalten“,
  Mehrfachauswahl-Hinweis, Handbuch, Tests). Die Breite von „Offene Starts“ prüft der Nachtest
  bzw. der Screenshot `handbuch_zeitplan` noch einmal.

### ux_test_2026_11 A10 (X16) – umgesetzt (03.11.2026, ohne Code-Signatur)

- **Website (`docs/index.html`):**
  - Erklärt, wo „Assets“ steht und welche Datei man unter Windows nimmt.
  - Zeigt das Edge-Bild zur Browserwarnung.
  - Ein Absatz beruhigt: Die Warnungen sind normal und kommen nur einmal.
  - Der Update-Weg nennt den Knopf „Version …“ (mit i-Symbol) und den vollen Knopftext.
  - **Geht erst mit dem nächsten Release online** (Regel 07.10.).
- **Handbuch Kap. 2:** beginnt mit „Kurz für Einsteiger (Windows)“ in vier Schritten und sagt
  „Download-Seite“ statt „Release-Seite“. Die README ist angeglichen.
- **Programm:**
  - Im Versionsfenster heißt es „Download-Seite dieses Programms (bei GitHub)“ statt
    „GitHub-Releases-Seite“, der Knopf heißt „Download-Seite im Browser öffnen“.
  - Der Knopf „Version …“ hat den Tooltip „Version anzeigen und nach Updates suchen“.
- **Nicht lösbar ohne Signatur:** Die Warnungen selbst bleiben (B8, Marco 03.11.: mit dem
  Installer derzeit nicht lösbar).
- **Verifikation** (Agent `verifikation`): Im Kern in Ordnung. Eingearbeitet sind der
  Knopfname, das Bild auf der Website, der volle Knopftext und der gekürzte Link. Werners
  Wunsch nach einem eigenen Knopf „Nach Updates suchen“ kommt in die Note-1-Liste (A13).
  Tests: 721 Unittests, gefilterte GUI-Tests grün.

### ux_test_2026_11 A11 – Abschluss-QS, Rolle Korrektheit (04.11.2026)

- **Prüfung:** Agent `qs-korrektheit` über `git diff 37bb744..HEAD -- '*.py'` (A1–A10), mit dem
  Schwerpunkt auf dem Zusammenspiel der Änderungen. Lokal 721 Unittests und 506 GUI-Tests grün.
- **Behoben:**
  - Versionsfenster (Regression aus A9): Enter auf einem fokussierten Knopf („Nach Updates
    suchen“) schloss das Fenster. Jetzt ist der Anfangsfokus auf „Schließen“, AutoDefault der
    übrigen Knöpfe bleibt. Der Test prüft Enter auf „Nach Updates suchen“.
  - Demo: Der Tooltip und das Handbuch zu „Vorheriger Text“ sagen jetzt „das automatische
    Weiter wartet“. Ein laufender Schritt läuft weiter, wie umgesetzt.
  - Pause „bei allen Richtern“: neutraler Text „keine Prüfung mehr ab … Uhr“ bzw. „bei keinem
    Richter steht ab … Uhr noch eine Prüfung im Plan“. Er stimmt auch für Richter ohne Plan.
- **Zur Kenntnis, nicht geändert:**
  - Die Demo übergibt dem Teilnehmer-Dialog kein Angebot (zeigt nur den grauen
    Prüfungsnamen).
  - Ein Schriftwechsel rechnet die Ergebnistabelle eines zweiten Demo-Hauptfensters erst bei
    der nächsten Größenänderung neu.

### ux_test_2026_11 A11 – Abschluss-QS abgeschlossen (04.11.2026)

- **Sicherheit** (Agent `qs-sicherheit`): keine Befunde. Neue Labels und Meldungen sind
  Klartext (S-1), der Registry-Wert `darstellung/schrift` wird geprüft, die Zählung in
  `_termin_info_lesen` bleibt in der Lesegrenze.
- **Wartbarkeit** (Agent `qs-wartbarkeit`), umgesetzt:
  - `TerminInfo.teilnehmend` als gemeinsame Zahl für Startbildschirm und Termin-Import;
  - `_gegenstand_zeilen` wird früh gesetzt statt per `getattr`;
  - der Faktor der Ergebnistabelle ist an die Stufe „Groß“ gekoppelt.
- **Optional, zur Entscheidung durch Marco (Rückfrage R7):**
  - eine Hilfsfunktion „alle Schriften neu anwenden“ in `ResponsiveSchriftMixin` statt der
    Schleife in `app.py`;
  - Konstanten für die Pfeil- und Feldmaße in `_AbbruchDelegate.paint`;
  - `t["…"]` statt `t.get` in `_zu_hoch_merken`;
  - eine gemeinsame Abfrage „ohne Startnummer“;
  - `re.sub` im Hilfe-Inhaltsverzeichnis;
  - feste Sollwerte im Lesezeit-Test;
  - Befundnummern in Code-Kommentaren (Projektstil bisher so);
  - Web- und Postgres-Terminübersicht zählen weiter alle Gemeldeten;
  - die Demo übergibt dem Teilnehmer-Dialog kein Angebot.
- **Vor dem nächsten Build neu aufzunehmen** (`tools/screenshots.py`):
  - `handbuch_ergebniserfassung` (Abbruch-Feld mit Pfeil);
  - `handbuch_teilnehmer_dialog_ed` (Hinweis, Gegenstand 2/3 ausgeblendet);
  - `handbuch_teilnehmer_dialog_dk` (Zeile „Prüfung: … – wird angeboten“);
  - `handbuch_demo` („Vorheriger Text“, echte Wartezeit);
  - `handbuch_start` („(+1 abgemeldet)“);
  - `handbuch_zeitplan` (Breite „Offene Starts“ prüfen).
  Danach `docs/HANDBUCH.pdf`. Die Website-Änderungen (A10) gehen erst mit dem Release online.
- **Tests nach den Nacharbeiten:** gefilterte GUI-Tests und `test_db` grün. Der volle Lauf kommt
  vor dem Build.

### ux_test_2026_11 A12 – Nachtest mit zwei Personas (04.11.2026)

- Werner (Laie, ohne Handbuch) und Tobias (normal, ohne Handbuch), gleiches Szenario, neuer
  Arbeitsstand. Bericht `berichte/UX-Test-2026-11/Nachtest.md`, Einzelberichte `personas/L-B2.md` und
  `N-B2.md`.
- **Noten gesamt:** Werner 2– → 2, Tobias 2 → 2 (eher 1–2), Erststart mit Demo bei Tobias 1.
  Tobias würde den Prüfungstag allein schaffen, Werner „eher ja, näher an Ja“. Kein ✗.
- **Abgleich:** Die meisten alten Funde sind behoben (Werner 6 + 2 weitgehend, Tobias 5).
  Neue bzw. verbliebene Punkte N1–N9 (u. a. fehlende Bestätigung „keine Überschneidungen“,
  Enter in der Import-Meldung, Disziplin-Zählung beim Speichern) gehen in die Note-1-Liste.
- **Am Gerät prüfen:** Bei Tobias öffnete Enter im Versionsfenster „Lizenzen“. Der Code setzt
  seit der Abschluss-QS den Anfangsfokus auf „Schließen“; möglicherweise ein Effekt der
  Testumgebung.

### ux_test_2026_11 A13 – ToDo-Liste „Note 1“ (04.11.2026)

- Marcos Auftrag vom 03.11.: `berichte/UX-Test-2026-11/note1-todos.md` mit T1–T15. Für jeden Punkt stehen
  dort die Personas, die Größe und ob eine Entscheidung nötig ist. Nichts davon ist umgesetzt.
- **Kern:** Erfahrene und Normale erreichen mit T1–T4, T6 und T8 voraussichtlich eine 1. Für
  Laien bleibt die Installation ohne Code-Signatur bzw. Store-Verteilung (T13) bei 3.
- **Entscheidungen Marco (04.11.2026):** T1 Bestätigung + Pausenfeld im Verteilen-Dialog; T4
  sofort beim Tippen markieren (C24 damit erledigt); T5 eine Auswahl „Prüfung“ (ersetzt R2); T7
  Vorgabe „Nein“ + zweite Warnung; T11 sprechender Dateiname; T12 echtes Zurück in der Demo
  (ersetzt R4); T13 bebilderte Kurzanleitung als PDF; T14 alles umsetzen (R7 erledigt). Details in
  `note1-todos.md`, Abschnitt „Entscheidungen“. Noch nichts umgesetzt.
- Abarbeitung als B1–B12 in `berichte/UX-Test-2026-11/aufgaben-note1.md` (Skill `aufgaben-abarbeitung`).

### ux_test_2026_11 B1 – Ergebniserfassung, T3 und T4 (04.11.2026)

- **Status (T3):** Nach dem Speichern steht „disqualifiziert“ bzw. „Abbruch: <Grund>“ (ohne Grund
  „Abbruch“) statt nur „gespeichert“, mit Tooltip für schmale Spalten
  (`ErgebnisTab._gespeicherter_status_text`).
- **Speichermeldung (T3):** zählt Teilnehmer („2 Teilnehmer gespeichert.“), nicht mehr
  Disziplinen und Statusänderungen; ebenso die Abbruch-Meldung und das Protokoll.
  `tools/screenshots.py` angepasst.
- **Abbruch-Spalte (T3):** Mindestbreite aus dem längsten Grund der Liste; reicht der Platz nicht,
  endet der Text mit „…“ statt beidseitig abgeschnitten. Die Gegenprobe zeigt: die Breite reichte
  schon vorher – das „letzung H“ im Nachtest lag vermutlich an der Testumgebung. Der Test sichert
  die Breite bei schmalem und breitem Fenster ab.
- **Zu hoch beim Tippen (T4, C24 teilweise erledigt):** Das offene Eingabefeld bekommt bei einem
  Wert über dem Maximum sofort einen roten Rahmen, dazu Tooltip und roter Hinweis
  „Höchstens 60 Punkte - 65 ist zu hoch …“. Ein gültiger Wert nimmt beides weg; nach dem
  Übernehmen übernimmt der bisherige rote Klartext (X7). Der Komma-Hinweis (X8) bleibt davon
  unberührt. Gelb erscheint weiterhin erst nach dem Übernehmen (C24 in `OFFEN.md` angepasst).
- Handbuch („Ergebniserfassung“) nachgezogen; Screenshot `handbuch_ergebniserfassung` vor dem
  Build ohnehin auf der Liste.
- Tests: 4 neue GUI-Tests; Gegenprobe: 3 scheitern ohne die Änderung (die Breiten-Prüfung ist
  reine Absicherung).
- **Verifikation (Agent `verifikation`), behoben:** Bei „6,5“ überschrieb der Hinweis vom Tippen
  den Komma-Hinweis, nach Rücktaste oder Enter war keiner mehr da – jetzt stehen beide
  untereinander (`_hinweise_zeigen`), der Komma-Hinweis bleibt. Escape nimmt den Hinweis vom
  Tippen mit weg (`closeEditor`). `UML.md` („n Teilnehmer gespeichert“) und die Angabe „C24
  teilweise erledigt“ in Kommentar und Test angeglichen.
- **Nicht geändert (Rückfrage R-B1 in `aufgaben-note1.md`):** Ein Designwechsel bei offenem
  Eingabefeld lässt dessen roten Rahmen bis zum nächsten Tastendruck in der alten Farbe. Sortieren
  nach „Status“ gruppiert jetzt „Abbruch: …“ und „disqualifiziert“ eigens. Ein Test für die
  Zählung nach einem Datenbankfehler mitten im Speichern fehlt (die Logik ist geprüft).
- Tests: 721 Unittests, 510 GUI-Tests grün (vor der Nacharbeit), danach die betroffenen 119
  GUI-Tests grün.


### ux_test_2026_11 B2 – ED-Gegenstand und Meldestelle, T6 und T7 (04.11.2026)

- **T6:** Bei ED fragt der Teilnehmer-Dialog nach („… sieht nach mehreren Gegenständen aus“,
  Vorgabe Nein, Fokus auf Gegenstand 1), wenn Gegenstand 1 Komma, Semikolon, „/“, „+“, „&“ oder
  „und/oder/sowie/u.“ enthält. Klammerzusätze wie „Ball (rot, klein)“ zählen nicht. Beim
  Bearbeiten nur nach einer Änderung von Text oder Prüfung (auch DK → ED).
- **T7:** Die Rückfrage bei leerem Verband/Meldestelle beim Anlegen des Termins hat jetzt die
  Vorgabe „Nein“ (vorher „Ja“, Marco 15.10.2026). Beim Erzeugen des Anmeldeformulars warnt das
  Programm noch einmal, solange Verband oder Meldestelle fehlen (Vorgabe Nein; bei fehlender
  Meldestelle mit dem Satz, dass die Teilnehmer sonst nicht wissen, wohin).
- **Verifikation:** ohne Befund; die optionalen Punkte (Klammerzusatz, „sowie“/„u.“, eigener
  Titel der Rückfrage, Wechsel DK → ED, Handbuch im ED-Abschnitt, weitere Testfälle) gleich mit
  umgesetzt. Bewusst gelassen: „Tennisball 1/2“ fragt nach (mit „Ja“ erledigt).
- Handbuch (Kapitel 3 Veranstaltungsdaten, Kapitel 4 Suchgegenstände, FAQ) nachgezogen. Web nicht
  betroffen.
- Tests: 5 neue bzw. erweiterte GUI-Tests, ein bestehender auf Vorgabe „Nein“ umgestellt;
  Gegenprobe scheitert ohne die Änderung. 721 Unittests, 517 GUI-Tests grün; nach der Nacharbeit
  die betroffenen 89 GUI-Tests grün.

### ux_test_2026_11 B3 – Version, Datensicherung, T9 bis T11 (04.11.2026)

- **T9:** Neues Menü **„Hilfe“** mit „Hilfe anzeigen“, „Nach Updates suchen…“ (öffnet das
  Versionsfenster und startet die Suche sofort) und „Version und Lizenzen“. Im Versionsfenster
  stehen „Diagnose kopieren“ und „Protokoll-Ordner öffnen“ im Bereich „Für Fehlermeldungen“ mit
  einem Satz, dass das nur zum Melden eines Fehlers nötig ist.
- **Enter im Versionsfenster (Nachtest N5):** echter Fehler, nicht die Testumgebung. Der
  Anfangsfokus auf „Schließen“ (A11) wurde vor dem Zeigen gesetzt und griff nicht, der Fokus lag
  auf „Lizenzen anzeigen“. Jetzt in `showEvent`; der Test prüft Fokus und Enter am gezeigten
  Fenster. Die Prüfung am Gerät ist damit erledigt.
- **T10:** Hinweis im Reiter „Datensicherung“: „… – auf Wunsch mit Passwort.“ statt „Passwort
  getrennt von der Sicherung aufbewahren“; der Tooltip nennt das Passwort freiwillig.
- **T11:** Dateiname `SHS-Sicherung_<Tag der Sicherung>_alle-Termine.zip` (ersetzt K10 mit Datum
  und Verein des geöffneten Termins, der nur einen Termin vermuten ließ). Eine Variante mit
  Terminnamen gibt es nicht, weil immer alle Termine gesichert werden.
- Handbuch (Installation/Update, Datensicherung, Fehlermeldung) nachgezogen. Screenshots vor dem
  Build: `handbuch_datensicherung` (Hinweistext) und alle Bilder des Hauptfensters, weil die
  Menüleiste jetzt „Hilfe“ zeigt; vom Versionsfenster gibt es kein Bild.
- **Verifikation, behoben:** Ein Klick auf „Nach Updates suchen“ und danach Enter kopierte die
  Diagnose (Qt schob den Fokus beim Sperren weiter) – jetzt liegt er während der Suche auf
  „Schließen“, danach wieder auf dem Suchknopf. Hilfe im Programm (Datensicherung, Version),
  Docstring, Kommentar und `UML.md` nachgezogen; Dateiname in der Reihenfolge des Auftrags
  (Datum vor Umfang).
- Tests: 3 neue GUI-Tests, 2 angepasst; Gegenprobe: alle 4 neuen bzw. geänderten scheitern ohne
  die Änderung.

### ux_test_2026_11 B7 – Kleinigkeiten aus der Abschluss-QS, T14 / R7 (04.11.2026)

Marco 04.11.2026: „alles umsetzen“. Umgesetzt:
- `ResponsiveSchriftMixin.alle_neu_anwenden()` statt der Schleife in `_schrift_wechseln`; rechnet
  auch die Ergebnistabelle eines zweiten Hauptfensters (Demo) neu.
- `_AbbruchDelegate`: Konstanten für Rand, Ecke, Pfeil und Texteinzug (`PLATZ_NEBEN_TEXT`).
- `_zu_hoch_merken`: `t["…"]` statt `t.get`.
- Gemeinsame Abfrage `db.teilnehmer_ohne_startnummer(conn, pruefung=None)` für die Vergabe, den
  Hinweis im Reiter „Teilnehmer“ und die Rückfrage nach einem Import.
- Hilfe-Inhaltsverzeichnis mit `re.sub` statt Ersetzen je Titel.
- Lesezeit-Test rechnet mit `LESEZEIT_MAX_S` und `math.ceil` statt fester Zahlen.
- Web-/PostgreSQL-Terminübersicht (`liste_termine_postgres`) zählt nur Teilnehmende wie am
  Desktop (`COALESCE(keine_teilnahme, 0) = 0`); der PostgreSQL-Test prüft das (nur in der CI).
- Demo übergibt dem Teilnehmer-Dialog Angebot und Prüfungsdatum (zeigt „… – wird angeboten“).

Nicht umgesetzt, Rückfrage R-B7: „Befundnummern in Code-Kommentaren“ – sie zu entfernen träfe das
ganze Projekt und nähme die Verbindung zu `Fortschritt.md`; bisher Projektstil.

Tests: 2 neue GUI-Tests, 2 angepasst, PostgreSQL-Test erweitert; Gegenprobe: die neuen scheitern
ohne die Änderung. 721 Unittests, 529 GUI-Tests grün.

- **Verifikation:** ohne Fehler. Nachgezogen: Die PostgreSQL-Übersicht prüft vorher, ob ein
  altes, nie geöffnetes Termin-Schema die Spalte `keine_teilnahme` schon hat (sonst wie bisher
  alle zählen); positiver Fall im Test für `teilnehmer_ohne_startnummer`.

### ux_test_2026_11 B4 – Import-Ablehnungen nachlesbar, T2 (04.11.2026)

- Im Reiter „Formular-Import“ steht nach einem Import der Bereich **„Letzter Import (HH:MM Uhr)“**
  mit der vollständigen Abschlussmeldung (importiert, bereits vorhanden, abgelehnt, Rat,
  Hinweise) und dem Knopf „Kopieren“. Er bleibt bis zum nächsten Import bzw. Terminwechsel, nur
  im Speicher. Gilt auch für CSV- und Termin-Import aus dem Reiter „Teilnehmer“
  (`_letzten_import_zeigen`, gemeinsamer Text über `_meldungstext_voll`). Der Rat bei Ablehnung
  nennt den Bereich.
- Verifikation: ohne Fehler; Test-Docstring, zweiter Import und Text des Rats nachgezogen,
  Querverweis im Handbuch Kapitel 5.
- **Rückfrage R-B4:** Bei Abbruch oder Datenbankfehler mitten im Import bleibt im Bereich das
  Ergebnis des vorigen Imports stehen (an der Uhrzeit erkennbar). Vorschlag: so lassen.
- Tests: 1 neuer GUI-Test, 1 erweitert; Gegenprobe scheitert ohne die Änderung. 721 Unittests,
  530 GUI-Tests grün; nach der Nacharbeit die Import-Tests grün.

### ux_test_2026_11 B5 – Zeitplan: Bestätigung und Mittagspause, T1 (04.11.2026)

- **Dialog „Automatisch verteilen“** (`VerteilenDialog`) statt der bisherigen Rückfrage: nennt das
  Ersetzen eines vorhandenen Plans und bietet „Mittagspause einplanen um [12:00] Uhr für [45]
  Min.“ an. Die Pause wird nach dem Verteilen wie „Pause bei allen Richtern“ eingefügt
  (Bezeichnung „Mittagspause“). Beim Neu-Verteilen ist sie vorbelegt: die zuletzt gewählte
  Wunschzeit bzw. (nach einem Neustart) Beginn und Dauer der Mittagspause im Plan.
- **Bestätigung (Nachtest N1):** „Alle Prüfungen sind eingeplant, und es gibt keine
  Überschneidungen.“ samt Zeile zur Mittagspause; sonst eine Warnung mit der Zahl offener
  Prüfungen bzw. betroffener Teams. Die Demo nutzt weiter `verteilen_ohne_rueckfrage` ohne
  Fenster.
- Handbuch (Kapitel Zeitplan und Schritt-für-Schritt) nachgezogen. Screenshot `handbuch_zeitplan`
  steht ohnehin auf der Liste; der neue Dialog hat kein eigenes Bild.
- Tests: 2 neue GUI-Tests, 1 angepasst (Hilfsfunktion `verteilen_dialog_bestaetigen`);
  Gegenprobe scheitert ohne die Änderung. 721 Unittests, 532 GUI-Tests grün.
- **Verifikation:** ohne Fehler (297 Pausen-Varianten ohne neue Überschneidung nachgestellt).
  Nachgezogen: Meldung nennt Zahl der Prüfungen und Starts; Vorbelegung nimmt die Dauer aus
  dem Plan und die Uhrzeit aus dem letzten Wunsch; `UML.md` (Abschnitt Zeitplan), Kommentar in
  der Demo, Tests für Vorbelegung nach Neustart, Überschneidungs-Warnung und „keine Pause“.

### ux_test_2026_11 B6 – Hilfe mit Suche und F1, T8 (04.11.2026)

- **Suchfeld** oben im Hilfefenster (`HilfeDialog`): markiert alle Treffer gelb (ExtraSelections),
  zeigt die Trefferzahl bzw. „nichts gefunden“, Enter oder „Weiter“ springt zum nächsten, am Ende
  wieder von vorn; Strg+F setzt den Fokus ins Feld. Enter schließt das Fenster nicht mehr.
- **F1** („Hilfe → Hilfe anzeigen“) öffnet die Hilfe beim Abschnitt des aktuellen Reiters
  (`HauptFenster._hilfe_zum_reiter`, `_hilfe_anker`); der Knopf „Hilfe“ öffnet sie wie bisher oben.
  Neuer Hilfe-Abschnitt „Diese Hilfe“.
- Handbuch (Einleitung, Schluss der Schritt-für-Schritt-Anleitung) nachgezogen.
- Tests: 2 neue GUI-Tests (Suche, F1 je Reiter); Gegenprobe scheitert ohne die Änderung.
  721 Unittests, 534 GUI-Tests grün.
- **Verifikation:** ohne Fehler. Nachgezogen: Enter ohne Treffer springt nicht mehr an den
  Anfang; der F1-Test prüft den sichtbaren Abschnitt; Hinweis auf Cmd+? am Mac. Zur Kenntnis:
  „Weiter“ sucht ab dem letzten Treffer (Qt-Verhalten), die Inhaltszeile zählt als Treffer
  mit; die Demo läuft hinter der Hilfe weiter (wie bisher, OFFEN C14). Kein Hilfe-Screenshot.

### ux_test_2026_11 B8 – Auswahl „Prüfung“ im Teilnehmer-Dialog, T5 (04.11.2026)

- Marcos Entscheidung (ersetzt R2): eine Auswahl **„Prüfung*“** mit den angebotenen Prüfungen in
  der Schreibweise des Anmeldeformulars (`Pruefungsangebot.bezeichnung`, z. B. „Trümmer LK 1“)
  und dem Eintrag **„andere Prüfung …“**, der Art/LK/Disziplin einblendet. Art/LK/Disziplin
  bleiben die gespeicherte Grundlage; die Auswahl folgt ihnen (auch beim Bearbeiten: nicht
  angebotene Prüfung → „andere Prüfung …“ mit sichtbaren Feldern). Ohne Angebot im Termin
  entfällt die Auswahl. Vorbelegung mit der ersten angebotenen Prüfung (R2) bleibt.
- Die Demo wählt die Prüfung über die Auswahl (Rückfall auf Art/LK/Disziplin, wenn sie nicht
  angeboten ist).
- „Prüfungsnamen überall einheitlich“: im Dialog umgesetzt (gleiche Bezeichnung wie Anmeldeformular
  und Hinweiszeile). Teilnehmerliste und Auswertung zeigen weiter „ED LK 1 – …“ – siehe
  Rückfrage R-B8.
- Handbuch („Die Erfassungsmaske“) nachgezogen. Screenshots `handbuch_teilnehmer_dialog_ed` und
  `_dk` stehen ohnehin auf der Liste (zeigen jetzt die Auswahl).
- Tests: 2 neue GUI-Tests; Gegenprobe scheitert ohne die Änderung. 721 Unittests, 536 GUI-Tests
  grün.
- **Verifikation:** ohne Fehler. Nachgezogen: Die Hinweiszeile „Prüfung: … – wird angeboten“
  steht nur noch zusammen mit Art/LK/Disziplin (sonst doppelt); der Demo-Rückfall wählt zuerst
  „andere Prüfung …“; Test prüft die ED-Zuordnung von Gegenstand 1. Zur Kenntnis: Altdaten ED
  ohne Disziplin zeigen die erste Disziplin (wie bisher, nur weniger sichtbar).

### ux_test_2026_11 B9 – Demo mit echtem Zurück, T12 (04.11.2026)

- Marcos Entscheidung (ersetzt R4 „nur Text zurück“): **„Schritt zurück“** im Erklärfenster
  nimmt ab Schritt 4 den letzten Schritt zurück und spielt ihn neu ab. Dazu merkt sich die Demo
  zu Beginn jedes Schritts im Demo-Termin dessen Stand als SQLite-Kopie im Speicher
  (`DemoTour._stand_merken`, `sqlite3.Connection.backup`). Zurück: laufenden Schritt abbrechen,
  Demo-Dialog schließen, Stand wiederherstellen, alle Reiter neu aufbauen
  (`_termin_setzen` - auch ungespeicherte Ergebnisse gehören zum zurückgenommenen Schritt),
  Erklärungsverlauf kürzen, Schritt neu abspielen. Beim Beenden werden die Kopien geschlossen.
- Bis Schritt 3 (Begrüßung, Termin anlegen, Termin gespeichert, erster Teilnehmer) gibt es
  keinen früheren Schritt im Demo-Termin; dort bleibt **„Vorheriger Text“** (Rückblick wie
  bisher). Der Knopf heißt je nach Schritt passend.
- Begrüßungstext und Handbuch (Demoprüfung) nachgezogen.
- Tests: 1 neuer GUI-Test (zurück aus Schritt 5 und 9, danach bis zum Ende); Gegenprobe scheitert
  ohne die Änderung; die bisherigen Rückblick-Tests laufen unverändert. 721 Unittests,
  537 GUI-Tests grün.
- **Verifikation, behoben:** Enter nach „Schritt zurück“ nahm gleich den nächsten Schritt zurück
  (Fokus blieb auf dem Knopf) – jetzt Fokus auf „Weiter“. Eine offene Schreib-Transaktion ließ
  das Zurückschreiben scheitern – jetzt vorher `rollback`. Scheitert die Kopie zu Beginn eines
  Schritts, fehlt nur für ihn „Schritt zurück“. Zurück aus Schritt 5 nimmt für Schritt 4 die
  Demodaten statt eigener Eingaben aus Schritt 3 (vertretbar). `Architektur.md`, `UML.md`
  (Zustandsdiagramm Demo), Kommentare und Texte nachgezogen.

### ux_test_2026_11 B10 – Kurzanleitung Installation als PDF, T13 (04.11.2026)

- Neue Kurzanleitung `docs/INSTALLATION_KURZ.md` → `docs/INSTALLATION_KURZ.pdf` (mit Bildern 3 Seiten, große
  Schrift): Download-Seite, richtige Datei, Browser-Warnung (Edge mit dem vorhandenen Bild,
  Chrome, Firefox), Windows-Warnung („Weitere Informationen“ → „Trotzdem ausführen“),
  Installationsprogramm („Nur für mich“, Lizenz, Weiter, Fertigstellen; Angaben aus
  `installer.iss` geprüft), Demoprüfung und Updates.
- `tools/handbuch_pdf.py --kurzanleitung` erzeugt das PDF (eigenes Druck-CSS ohne Seitenumbruch
  je Kapitel); in der Build-Checkliste (`shs-build`) ergänzt. Erzeugen über PowerShell (siehe
  Memory).
- Verlinkt im Handbuch (Kapitel 2) und auf der Website (Abschnitt Installation). Die Website geht
  erst mit dem Release online (Regel 07.10.2026).
- **Nicht umgesetzt, Rückfrage R-B10:** Bilder der Chrome-Download-Warnung und der
  SmartScreen-Meldung. Echte Bildschirmfotos kann die Sitzung nicht aufnehmen, nachgestellte
  Windows-Fenster wären irreführend. Vorschlag: Marco nimmt beide beim nächsten Download auf
  (`docs/bilder/handbuch_chrome_download.png`, `handbuch_smartscreen.png`), dann werden sie
  eingebunden. Signatur/Store bleibt B8 (OFFEN).
- **Verifikation:** ohne Fehler; nachgezogen: Knopf „Installieren“ vor „Fertigstellen“, Ausweg bei
  Firefox, klare Meldung bei unbekannten Angaben in `tools/handbuch_pdf.py`.
- **Nachtrag (Marco 04.11.2026, R-B10 teilweise):** Marco hat die SmartScreen-Meldung aufgenommen
  (`docs/bilder/handbuch_smartscreen_1.png` vor, `_2.png` nach „Weitere Informationen“). Beide in
  die Kurzanleitung, das zweite ins Handbuch (Kapitel 2) eingebunden. Der Titel der Meldung heißt
  heute „Der Computer wurde durch Windows geschützt“ – Handbuch, Kurzanleitung, Website,
  `README.md` und `README_INSTALLER.md` nennen ihn jetzt (alter Titel als Hinweis). Chrome warnte
  beim Download nicht mehr (die Datei hat inzwischen genug Ruf); ein Chrome-Bild fehlt weiter.
- **Marco 04.11.2026:** Chrome (Erweiterter Schutz) warnt seit dem öffentlichen Repo auch bei neuen
  Versionen nicht mehr. Ein Chrome-Bild entfällt; der Chrome-Hinweis bleibt für den Fall der
  Fälle in Kurzanleitung und Handbuch. R-B10 damit erledigt.

### ux_test_2026_11 B11 – Abschluss-QS über B1–B10 (04.11.2026)

QS mit drei Rollen über `git diff aa84240..HEAD` (nacheinander, je ein Subagent):

- **Sicherheit:** kein Befund (SQL nur mit festen Texten, Meldungen und Import-Texte als Klartext,
  Sicherungsname ohne Nutzerdaten, Regex linear, „Schritt zurück“ nur auf der Demo-Datenbank,
  PDF-Werkzeug ohne Shell).
- **Korrektheit:** drei Befunde, **nicht umgesetzt** – nach `CLAUDE.md` erst nach Marcos Go
  (Rückfragen Q1–Q3 in `berichte/UX-Test-2026-11/aufgaben-note1.md`):
  - K1 (mittel): Demo – „Schritt zurück“ aus Schritt 10 oder 11 stellt einen Stand ohne die in
    Schritt 8 nur getippten (noch ungespeicherten) Punkte wieder her; Schritt 12 findet dann
    kein Stechen, die Demo kommt nicht ans Ende.
  - K2 (niedrig–mittel): „Automatisch verteilen“ mit Mittagspause meldet immer die Wunschzeit,
    auch wenn die Pause bei einem Richter erst nach einem laufenden Block liegt.
  - K3 (niedrig): „Automatisch verteilen“ ohne Teilnehmer meldet „Alle 0 Prüfung(en) … eingeplant“.
- **Wartbarkeit:** Programmcode-Punkte als Rückfrage Q4 (doppelte Pausen-Meldelogik im Zeitplan,
  veralteter Modul-Docstring in `desktop_demo.py`, doppelte Verband/Meldestelle-Prüfung,
  Kommentar mitten im `_ja_nein`-Aufruf, Konstantenplatz, Testschärfe beim Sicherungsnamen,
  „Letzter Import“ aus `app.py` auslagern, Mittagspause am Namen erkannt). Doku-Punkte gleich
  erledigt:
  - `docs/HANDBUCH.md`: Zitat der Verteil-Bestätigung an den echten Text angeglichen; Menü „Hilfe“
    (Hilfe anzeigen/F1, Nach Updates suchen…, Version und Lizenzen) beschrieben.
  - `README_INSTALLER.md`, `README_CONTAINER.md`: `tools/handbuch_pdf.py --kurzanleitung` und
    `docs/INSTALLATION_KURZ.pdf` in Build-Schritten und Checkliste.
  - `Architektur.md`: `VerteilenDialog`, Hilfe mit Suche/F1, Auswahl „Prüfung“, „Letzter Import“,
    Punkte-Prüfung beim Tippen, Menü „Hilfe“, Zeile für `tools/handbuch_pdf.py`.
  - `CLAUDE.md`/`AGENTS.md`: Zeilenzahlen (app.py ≈ 4100, db.py ≈ 3700, desktop_dialoge.py ≈ 2200).
- **R-B1 (c):** Test `test_alle_speichern_bis_200_teilnehmer_behaelt_gespeicherte_zeilen` prüft jetzt
  auch die Meldung „Speichern abgebrochen – 1 Teilnehmer gespeichert, die übrigen nicht.“
  (sichert vorhandenes Verhalten, keine Gegenprobe).
- **Testlauf:** 721 Unittests OK (178 übersprungen), 537 GUI-Tests grün (1 übersprungen, 1 xfail).
- **Screenshots vor dem nächsten Build:** alle 15 Bilder neu (`tools/screenshots.py`), weil das
  neue Menü „Hilfe“ in jedem Hauptfenster-Bild steht; inhaltlich geändert besonders
  `handbuch_ergebniserfassung`/`ergebniserfassung` (Status, Zählung), `handbuch_teilnehmer_dialog_ed`/
  `_dk` (Auswahl „Prüfung“), `handbuch_zeitplan`/`zeitplan`, `handbuch_datensicherung` (Text),
  `handbuch_formular_import` („Letzter Import“), `handbuch_demo`, `handbuch_start`. Danach
  `docs/HANDBUCH.pdf` und `docs/INSTALLATION_KURZ.pdf` neu erzeugen.

### ux_test_2026_11 B13 – Q1–Q4 aus der Abschluss-QS (04.11.2026, Marcos Go)

- **Q1 (K1):** Demo – „Schritt zurück“ aus Schritt 10 und 11 geht zurück zu Schritt 8
  („Ergebnisse eintragen“), weil die Punkte erst in Schritt 10 gespeichert werden; vorher fehlten
  sie danach, und die Demo fand kein Stechen (`DemoTour._zurueck_ziel`). Tooltip, Handbuch,
  `Architektur.md` und `UML.md` nachgezogen.
- **Q2 (K2):** Mittagspause aus „Automatisch verteilen…“ nennt die tatsächlichen Zeiten je Richter,
  wenn um die Wunschzeit noch ein Block läuft. Gemeinsamer Helfer `_pause_bei_allen_hinweis` für
  diesen Weg und „Pause bei allen Richtern“ (Texte und Titel dort unverändert).
- **Q3 (K3):** „Automatisch verteilen…“ ohne Teilnehmer: „Noch keine Teilnehmer – nichts zu verteilen.“
- **Q4:** Modul-Docstring der Demo, `ERSTER_SCHRITT_IM_TERMIN` bei den Klassenkonstanten,
  `fehlende_formularangaben`/`_satz` in `desktop_gemeinsam.py` für Termin-Dialog und
  Formular-Export (Texte gleich), Kommentar aus dem `_ja_nein`-Aufruf gezogen, Kommentar zu
  `MITTAGSPAUSE` (von Hand so benannte Pause gilt bewusst mit), Sicherungsname-Test prüft „Verein
  nicht im Namen“. Das zweite `aktualisieren()` nach dem Einfügen der Mittagspause bleibt (nötig).
- **Tests:** neu `test_demo_schritt_zurueck_nach_ungespeicherten_ergebnissen`,
  `test_verteilen_nennt_tatsaechliche_pausenzeit_und_braucht_teilnehmer`,
  `test_pause_bei_allen_hinweis_und_titel`; zwei bestehende Zeitplan-Tests an das richtige
  Verhalten angepasst (einer hatte die falsche Wunschzeit-Meldung erwartet). Gegenprobe: ohne die
  Änderung scheitern die vier betroffenen Tests. 721 Unittests, 539 GUI-Tests grün (vor den
  Nachträgen der Verifikation; danach die betroffenen 52 gezielt grün).
- **Verifikation:** kein Verhaltensfehler; Nachträge (Doku, Tooltip, Tests für Erfolgsmeldung und
  Titel) eingearbeitet.
- **Nachtest (B12):** Heinz (E-A2) vor dieser Änderung fertig, Bericht
  `berichte/UX-Test-2026-11/personas/E-A2.md` (gesamt 1– statt 2); die übrigen Personas testen den Stand mit B13.

### ux_test_2026_11 B12 – Nachtest 2 mit fünf Personas (04.11.2026)

Bericht `berichte/UX-Test-2026-11/Nachtest2.md`, Einzelberichte `personas/E-A2`, `E-B2`, `N-A2`, `L-A2`, `L-B3`.

- **Gesamtnoten (vorher):** Heinz 1– (2), Sabine 1–2 (2), Julia 1 (2), Gerda 2+ (2–3), Werner 2+ (2).
  Termin-Ablauf bei allen 1 bis 1–2; alle fünf kommen am Prüfungstag allein klar. Die Laien
  bremst nur noch die Installation (3 bzw. 3+, ohne Code-Signatur nicht lösbar, B8).
- **Abgleich früherer Funde:** 45 behoben, 7 weitgehend, 4 teilweise, 2 nicht behoben (Prüfungsnamen
  R-B8, „Richter hinzufügen“ ohne Namen), 1 nicht erlebt.
- **Neue/verbliebene Funde N1–N16** (Liste in `Nachtest2.md`), nichts umgesetzt – zur Entscheidung
  an Marco. Wichtigste: abgeschnittener Abbruchgrund (alle 5), Schrift „Groß“ schneidet die
  Erfassung ab, Kurzanleitung ohne GitHub- und Setup-Bild, Startnummer-Tausch zwischen Prüfungen
  ohne Warnung, Demo-Schritt 3 erwähnt noch „Art und Leistungsklasse“ (seit B8 veraltet).
- **Harness:** frische Sandboxen brauchen `home\Downloads` mit den Testdaten (vorher anlegen);
  vereinzelt `PermissionError` auf Antwortdateien.
- **Nachtrag (Marco 04.11.2026, N3 teilweise):** Marco hat die Edge-Download-Warnung von 1.0.55
  aufgenommen (`docs/bilder/handbuch_edge_download_1.png` Warnung mit „Mehr anzeigen“, `_2.png`
  Fenster mit Pfeil neben „Löschen“ → „Trotzdem beibehalten“). Ersetzt das alte Bild (1.0.45, Weg
  über „…“ → „Beibehalten“). Kurzanleitung, Handbuch, Website und `README_INSTALLER.md` beschreiben
  den neuen Weg (alter Weg als Hinweis für ältere Edge-Versionen). Offen bei N3: Setup-Bild
  („Nur für mich“) von Marco, GitHub-Bild und Website-Knopf in B21.
- **Nachtrag (Marco 04.11.2026, N3):** Setup-Bilder von 1.0.55 (Lizenz, Bereit zur Installation,
  Fertigstellen) als `docs/bilder/handbuch_setup_1` bis `_3.png` in der Kurzanleitung, Schritt 5 als
  nummerierte Liste. Die Frage „Nur für mich“ kam bei Marcos Update nicht (Inno Setup merkt sich den
  Modus); die Kurzanleitung sagt jetzt „beim ersten Mal“. Kein Bild davon – bei einer
  Neuinstallation nachholen, falls gewünscht. Offen bei N3 nur noch GitHub-Bild und Website-Knopf (B21).

### ux_test_2026_11 B14 – Ergebniserfassung: Abbruch-Spalte, große Schrift, Komma (Nachtest 2 N1, N2, N8; 04.11.2026)

- **N1:** Die Abbruch-Spalte ist so breit wie der längste Grund. Ursache: Reichte der Platz,
  gab `_ergebnis_spaltenbreiten_verteilen` die natürlichen Breiten zurück; bei leeren Zellen
  misst `resizeColumnsToContents` aber nur die Kopfzeile („Verletzu…“). Die natürlichen Breiten
  werden jetzt auf die Minima angehoben.
- **N2:** Bei Schrift „Groß“ kein waagerechter Bildlauf mehr: Die Status-Spalte behielt die
  Inhaltsbreite für „Abbruch: <Grund>“ (seit T3) und ragte über den Rand; jetzt bekommt sie
  immer den Rest (mindestens 40 px, Text endet mit „…“, Tooltip und Abbruch-Spalte zeigen den
  Grund ganz). Der Teilnehmer-Dialog wird mindestens so breit wie sein Formular
  (`_groesse_auf_bildschirm_begrenzen(…, inhalt=)`, höchstens 95 % des Bildschirms); gemessen mit
  Windows-Schriften bei „Groß“ 1114 statt 1040 px, ohne Bildlauf.
- **N8:** Eine Punkteingabe mit abgelehntem Zeichen (Komma, Buchstabe, dritte Ziffer) wird nicht
  übernommen, der bisherige Wert bleibt; der Hinweis nennt den (ersten) Grund, die Statuszeile
  meldet „Nr. X Name: Eingabe nicht übernommen …“, auch beim Speichern mit offenem Feld.
  Feld leeren macht die Eingabe wieder gültig. Ein abgelehntes erstes Zeichen bei noch
  markiertem Wert fällt nur weg (die Zahl danach ersetzt den Wert wie gewohnt). Handbuch Kap. 7
  und `UML.md` (Sequenz „Ergebnisse erfassen“) nachgezogen.
- **Tests:** neu `test_punkte_mit_abgelehntem_zeichen_werden_nicht_uebernommen`,
  `test_dialoggroesse_richtet_sich_nach_dem_inhalt`, `test_ergebnis_abbruch_spalte_zeigt_den_ganzen_grund`;
  zwei Komma-Tests an das neue Verhalten angepasst. Gegenprobe: ohne die Änderung scheitern bzw.
  hängen die neuen Tests. 721 Unittests, alle GUI-Tests grün.
- **Verifikation:** Befund „Meldung geht beim Speichern unter“ und „abgelehntes erstes Zeichen
  blockiert die nachgetippte Zahl“ behoben; Tests für Status-Spalte mit Abbruch, Verdrahtung des
  Dialogs und ersten Grund ergänzt; Kommentar und UML nachgezogen.

### ux_test_2026_11 B15 – Tausch-Warnung, Richtername, Zurücksetzen, Entf (Nachtest 2 N4, N7, N13, N15; 04.11.2026)

- **N4:** „Startnummer tauschen…“ fragt bei verschiedenen Prüfungen nach (Vorgabe „Nein“): Die
  Nummern liegen danach außerhalb ihrer Bereiche; die Rückfrage nennt Prüfung und Bereich beider
  Teilnehmer und gespeicherte Ergebnisse. Bei gleicher Prüfung tauscht der Dialog wie bisher ohne
  weitere Frage, bei zwei markierten bleibt es bei der einen Rückfrage (mit Warnung). Danach meldet
  die Statuszeile „Nr. X und Y getauscht.“ bzw. „Nr. X von A an B übertragen.“ Beide Wege laufen
  über `TeilnehmerTab._tauschen_nach_rueckfrage`.
- **N7:** „Richter hinzufügen“ fragt gleich den Namen ab (leer = „Richter N“, Abbrechen legt
  keinen an). Das Zeitplan-PDF lässt Richter ohne Einträge weg; hat keiner Einträge, steht nur ein
  Hinweis darin.
- **N13:** Die Rückfrage bei „Alle Startnummern zurücksetzen…“ nennt, wie viele der Betroffenen
  schon Ergebnisse haben; Vorgabe bleibt „Nein“. Abweichung von der Entscheidung: Ob ein Termin im
  Web veröffentlicht ist, steht nicht in der Termin-Datei (die Veröffentlichung lädt eine Kopie
  hoch). Der Web-Satz steht deshalb weiter da, aber nur noch als „Nur falls der Termin schon im
  Web veröffentlicht ist: …“ – Rückfrage an Marco in der Aufgabenliste.
- **N15:** Entf in der Teilnehmerliste wirkt wie „Löschen“ (`QShortcut`, nur bei Fokus in der
  Liste), mit der bestehenden Rückfrage (Vorgabe „Nein“); Tooltip am Knopf.
- Handbuch (Teilnehmer-Knöpfe, Zeitplan) nachgezogen.
- **Tests:** neu `test_tausch_zwischen_pruefungen_fragt_mit_bereichen_nach`,
  `test_tausch_an_teilnehmer_ohne_nummer_meldet_uebertragung`,
  `test_entf_in_teilnehmerliste_loescht_nach_rueckfrage`,
  `test_startnummern_zuruecksetzen_nennt_ergebnisse`, `test_zeitplan_pdf_laesst_richter_ohne_eintraege_weg`;
  angepasst: Richter-Knöpfe (Namensabfrage), Zeitplan-PDF mit leerem Richter, Tausch über den
  Dialog (Statuszeile). Gegenprobe: ohne die Änderung scheitern alle neuen und angepassten
  Tests. 722 Unittests, alle GUI-Tests grün (547).
- **Verifikation:** „außerhalb der Bereiche“ steht nur noch, wo es stimmt (nicht ohne Nummer oder
  Bereich, und nicht, wenn der Tausch über Kreuz liegende Nummern zurückbringt); Statuszeile mit
  „Nachname, Vorname“; Handbuch-Absatz zum Zurücksetzen angeglichen; Tests für Name mit OK,
  fehlenden Bereich und zwei Ergebnisse ergänzt. Rückfragen R-B15 (Web-Status, Entf am Mac) in
  der Aufgabenliste.

### ux_test_2026_11 B16 – Hilfe, Gegenstand-Texte, Rat bei Ablehnung (Nachtest 2 N6, N11, N12; 04.11.2026)

- **N6:** Der Knopf „Hilfe“ öffnet wie F1 beim Abschnitt des aktuellen Reiters (Tooltip „Hilfe zum
  aktuellen Reiter (F1)“; `HauptFenster._hilfe_anzeigen` entfällt). Die Suche findet zuerst ganze
  Wörter und Wortanfänge (`QRegularExpression` mit `(?<!\w)`, Unicode); nur ohne solche Treffer
  zählen Wortteile, die Trefferzahl sagt dann „(in Wörtern)“. Treffer kräftig orange und fett statt
  blassgelb. Neuer Hilfe-Abschnitt „Tastenkürzel“ (überall, Teilnehmer, Ergebniserfassung,
  Rückfragen), im Abschnitt „Datensicherung“ der Rat zum USB-Stick; Handbuch Kap. 13 bekommt eine
  Tabelle „Tastenkürzel“.
- **N11:** Der Spaltenkopf „Anmerkungen“ erklärt per Tooltip orange (beheben) und grau (Erinnerung,
  „Gegenstand noch offen“ = Gegenstände noch nicht eingetragen, bis zum Prüfungstag über
  „Bearbeiten…“ nachtragen). CSV- und OMA-Import nennen als letzten Hinweis, dass die Gegenstände
  nachzutragen sind. Zurückgestellt: der Satz „weiteren Gegenstand ggf. unter Anmerkungen notieren“
  in der ED-Rückfrage – ein Feld „Anmerkungen“ gibt es im Dialog nicht (Rückfrage R-B16).
- **N12:** `db_import.rat_bei_ablehnung` ordnet jedem Ablehnungsgrund einen konkreten Rat zu
  (mehrere/keine Prüfung angekreuzt, nicht angeboten, keine Angebote hinterlegt, Hündin und Rüde,
  kein Anmeldeformular, defekte oder nicht lesbare Datei, unbekannte Prüfung, fehlende oder
  ungültige Angabe); die Importmeldung zeigt ihn als „→ Rat: …“ in eigener Zeile unter dem
  Eintrag. Der allgemeine Abschnitt „Was tun?“ bleibt.
- **Tests:** neu `test_hilfe_suche_bevorzugt_wortanfaenge_und_kennt_tastenkuerzel`,
  `test_hilfe_knopf_oeffnet_beim_aktuellen_reiter`, `test_spalte_anmerkungen_erklaert_gegenstand_noch_offen`,
  `test_rat_bei_ablehnung_je_grund`; erweitert: Importmeldung mit Rat, drei Import-Tests um den
  Gegenstände-Hinweis.
  Gegenprobe: ohne die Änderung scheitern alle neuen und erweiterten Tests. 723 Unittests, alle
  GUI-Tests grün (552).
- **Verifikation:** Strg+Tab aus den Tastenkürzel-Listen genommen – Tabellen (außer der
  Ergebniserfassung) verbrauchen die Taste selbst, „überall“ stimmte nicht. Der Rat wird nur im Grund
  gesucht (ohne Zeile/Datei und ohne Werte in „…“), „ist ungültig“ vor „fehlt“, neuer Rat für
  ungültige Daten, Rat bei „nicht angeboten“ nennt auch das Freischalten. Suchtexte, die mit einem
  Sonderzeichen beginnen, suchen gleich überall. Handbuch-Tabelle um Doppelklick ergänzt; Tests für
  Weitersuchen, Umlaut, Sonderzeichen und die übrigen Räte.

### ux_test_2026_11 B17 – Demo-Texte und Beenden, Zählung nach dem Verteilen (Nachtest 2 N9, N10; 04.11.2026)

- **N9:** Demo-Schritt 3 spricht vom Feld „Prüfung“ („Trümmer LK 1“ = ED, „DK-LK 1“ = Dreikampf)
  statt von „Art und Leistungsklasse“, die die Maske seit B8 nur bei „andere Prüfung …“ zeigt. Die
  Demo-Bereiche sind je 20 Nummern (1–20, 21–40, 41–60, 61–80) wie bei „Anzahl 20“. Der Knopf
  „Beenden“ fragt nach (Vorgabe „Nein“, neues Signal `DemoPanel.beenden_angefragt`). Solange die
  Rückfrage offen ist, ruht die Demo (kein Tippen, kein Countdown); nach „Nein“ geht der Schritt
  weiter, ein laufender Countdown beginnt neu. Das Schließen des Erklärfensters beendet weiterhin
  ohne Rückfrage. Die Prüfungsnamen in Schritt 3 kommen aus `ALLE_PRUEFUNGEN` (passt nach B18).
- **N10:** Die Bestätigung nach „Automatisch verteilen“ zählt Prüfungen (der Dreikampf als eine)
  und Teilnehmer statt Disziplin-Gruppen und Starts: „Alle 6 Prüfungen mit 16 Teilnehmern sind
  eingeplant …“, bei einer Prüfung „Die Prüfung mit … ist eingeplant …“. Die Warnung „noch nicht
  (ganz) eingeplant“ zählt ebenso (`desktop_zeitplan._anzahl_pruefungen`); UML (Demo-Zustände)
  nennt die Rückfrage. Handbuch (Demoprüfung, Zeitplan, Kap. 14)
  nachgezogen.
- **Tests:** neu `test_verteilen_bestaetigung_zaehlt_pruefungen_und_teilnehmer`,
  `test_demo_bereiche_passen_zur_anzahl_und_schritt_3_nennt_pruefung`; erweitert:
  `test_demopruefung_beenden_mitten_in_der_ergebniserfassung` (Rückfrage, „Nein“ läuft weiter);
  angepasst: Mittagspausen-Test (neuer Wortlaut). Nach der Verifikation dazu
  `test_demo_ruht_waehrend_der_beenden_rueckfrage`. Gegenprobe: ohne die Änderung scheitern die
  neuen und angepassten Tests. 723 Unittests, alle GUI-Tests grün.

### ux_test_2026_11 B18 – Prüfungsnamen überall einheitlich (Nachtest 2 N5; 04.11.2026)

- **N5 (ersetzt R-B8):** Eine Schreibweise für jede Prüfung, wie auf dem Anmeldeformular: „DK LK 1“,
  „Trümmer LK 2“, „Behältnisse LK 3“, „Fläche LK 1“ – in Teilnehmerliste, Filtern,
  Ergebniserfassung, Auswertung, Übersicht, Zeitplan, Meldungen, Web-Erfassung und allen PDFs
  (Ergebnislisten, Etiketten, Statistik-Schlüssel, Zeitplan). Vorher „ED LK 2 Trümmerfeld“ bzw.
  „DK-LK 1“ auf dem Formular.
  - Zentral: `db.pruefung_bezeichnung` (aus `ALLE_PRUEFUNGEN.bezeichnung`, dort jetzt „DK LK n“
    statt „DK-LK n“), `leistungsklasse_label` ruft sie auf. Zeitplan-Blöcke über
    `db.zeitplan_bezeichnung` („Fläche LK 1“, beim Dreikampf „DK LK 1 – Trümmerfeld“).
  - Sortiert wird in der Reihenfolge des Formulars (DK, Trümmer, Behältnisse, Fläche, je LK 1–3,
    `db.pruefung_sortierschluessel`) statt alphabetisch – sonst stünde „Behältnisse“ vor „DK“.
  - Etiketten nutzen dieselbe Bezeichnung (die eigene Kurzform „ED LK 3 Behältnis“ entfällt).
  - Bewusst unverändert: der Bewertungsbogen (Vorlage des Verbands, „LK 1“ / „ED - LK 1“), die
    Spaltenköpfe der Statistik-PDF (Vorlage) und die Übersicht je Leistungsklasse („ED LK 1“ fasst
    alle Einzeldisziplinen einer LK zusammen, keine einzelne Prüfung). Gespeichert wird keine
    Bezeichnung (Stechen, Angebote und Bereiche laufen über Kürzel bzw. IDs), alte Termine
    brauchen deshalb keine Umstellung.
  - Handbuch nachgezogen; die Bildschirmfotos zeigen noch die alten Namen und werden vor dem
    nächsten Build ohnehin neu aufgenommen.
- **Tests:** rund 45 erwartete Texte in den Tests auf die neuen Namen umgestellt; neu
  `test_pruefungsbezeichnung_wie_im_anmeldeformular`, `test_etikett_pruefungsfeld_bleibt_einzeilig`,
  `test_teilnehmerliste_ordnet_pruefungen_wie_das_formular`, Formular-Reihenfolge in
  `test_alle_leistungsklassen_sortiert_und_ohne_duplikate`. Gegenprobe: ohne die Änderung in
  `db.py` scheitern die neuen und umgestellten Tests. 725 Unittests, alle GUI-Tests grün.
- **Verifikation:** Die Formular-Reihenfolge gilt jetzt auch in der Ergebnistabelle der
  Auswertung, den Etiketten, den „von x“-Hinweisen, beim Stechen (`shs_core.berechne_rangliste`
  und `stechen_gruppen` mit optionalem `sortierschluessel`) und beim Spaltenklick in der
  Teilnehmerliste (`desktop_gemeinsam._PruefungSortierbaresItem`); Rückfallname im Import über
  `pruefung_bezeichnung`; veraltete Beispiele in Kommentaren angepasst. R-B8 als erledigt vermerkt.

### ux_test_2026_11 B19 – Termin-Dialog ohne Bildlauf, Seitenleiste „Offene Starts“ (Nachtest 2 N14; 04./05.11.2026)

- **Termin-Dialog:** zweispaltig – links die Eckdaten (Verein bis Meldestelle, Speicherort),
  rechts „Angebotene Prüfungen“ und „Startnummern-Bereiche“. Die Höhe richtet sich nach dem
  Inhalt (`_groesse_auf_bildschirm_begrenzen(…, hoehe_nach_inhalt=True)`, höchstens 90 % des
  Bildschirms), die Breite wie seit B14 nach dem Formular. Gemessen mit Windows-Schriften auf
  1920×1080: Schrift „Normal“ 1009×951 ohne Bildlauf; „Groß“ 1191×972 mit 10 px Bildlauf nur,
  solange keine Prüfung angehakt ist (dann stehen alle 12 Bereichszeilen da), „Sehr groß“ 64 px.
  Mit angehakten Prüfungen (z. B. 3) überall 0. Auf 1366×768 greift die Kappung (Bildlauf 233 px
  bei „Normal“ ohne Haken, mit 3 Haken 0). Der Teilnehmer-Dialog behält seine feste Höhe.
- **Seitenleiste „Offene Starts“:** Breite nach der längsten eingeplanten Zeile („DK LK 3 –
  Behältnisstrecke (99 Teilnehmer)“) in der aktuellen Schrift (`ZeitplanTab._seitenleiste_breite_anpassen`,
  bei jedem `aktualisieren()` und nach einem Schrift-/Stylesheet-Wechsel über `changeEvent`), statt
  fest 280–360 px. Offene Zeilen (fett, „– noch offen“) dürfen umbrechen. Auf kleinen Bildschirmen
  höchstens ein Fünftel (Minimum) bzw. ein Viertel (Maximum) der Breite, mindestens die bisherigen
  280–360 px: gemessen auf 1366 bei „Sehr groß“ mit drei Richtern kein waagerechter Bildlauf, auf
  1920 die volle Breite.
- Handbuch (Termin anlegen) und `tools/screenshots.py` (Bild `handbuch_termin_anlegen` jetzt
  1080×900, ganzes Fenster) nachgezogen; das Bild selbst wird vor dem nächsten Build neu
  aufgenommen.
- **Tests:** neu `test_termin_dialog_zweispaltig_und_so_hoch_wie_sein_inhalt`,
  `test_offene_starts_seitenleiste_passt_fuer_lange_zeilen` (auch Neumessung nach Schriftwechsel).
  Gegenprobe: ohne die Änderung scheitern beide. Alle GUI-Tests grün (558).
- **Verifikation:** Neumessung nach Schriftwechsel, Obergrenze für kleine Bildschirme, Docstring
  und Screenshot-Werkzeug bereinigt. Zur Kenntnis: In der Demo verdeckt das Erklärfenster auf
  1366 px unten rechts einen Teil des breiteren Termin-Dialogs (auf 1920 nicht) – bei der
  Sichtprüfung vor dem Build ansehen.

### ux_test_2026_11 B20 – Pause zu fester Uhrzeit: zurückgestellt (Nachtest 2 N16; 05.11.2026)

- Nicht umgesetzt: Ein Prüfungsblock umfasst im Datenmodell immer alle Teams einer Prüfung
  (`_teilnehmer_fuer_pruefungseintrag` filtert live nach Art/LK/Disziplin, nur mit Startversatz).
  Einen laufenden Block zur Pausenzeit zu teilen, braucht ein neues Feld je Block samt Migration
  (SQLite, PostgreSQL) und neue Regeln für Verschieben/Entfernen und „Offene Starts“. Nach
  `CLAUDE.md` (Datenmodell-Entscheidungen zuerst klären) und der Vorgabe im Auftrag („bei
  Unklarheit zurückstellen und fragen“) zurückgestellt; Rückfrage R-B20 mit drei Möglichkeiten in
  `berichte/UX-Test-2026-11/aufgaben-note1.md` (Vorschlag: feste Pause mit Lücke davor, ohne Teilen).

### ux_test_2026_11 B21 – Kurzanleitung: Website-Knopf und GitHub-Bild (Nachtest 2 N3; 05.11.2026)

- `docs/INSTALLATION_KURZ.md` Schritt 1 nennt zuerst die Website (mbruver-source.github.io/SHS)
  mit dem Knopf „Aktuelle Version herunterladen“, dann die direkte Adresse; Schritt 2 zeigt das
  neue Bild `docs/bilder/handbuch_github_assets.png` (Kasten „Assets“ der Release-Seite 1.0.55,
  Setup-Datei rot eingerahmt). Aufgenommen mit Edge headless (`--virtual-time-budget=15000`,
  sonst lädt die Asset-Liste nicht) und mit PIL ausgeschnitten. Handbuch Kap. 2 („Kurz für
  Einsteiger“) ebenso. `INSTALLATION_KURZ.pdf` neu erzeugt (5 Seiten, 8 Bilder).
- Das Bild zeigt die Versionsnummer 1.0.55. Vor einem Build zeigt die Release-Seite immer noch
  die vorige Version (Verifikation B21) – das ist in Ordnung, der Text sagt „statt … steht dort die
  Versionsnummer“. Neu aufgenommen wird es nur bei sichtbaren Änderungen an GitHub; der Ablauf
  steht in der Build-Checkliste (`.claude/skills/shs-build/SKILL.md`) und im Kopf von
  `tools/screenshots.py`. Offen als R-B21: das Bild auch auf der Website (`index.html`) zeigen? Setup- und Edge-Bilder hat Marco am 04.11. geliefert (siehe B12/N3).

### ux_test_2026_11 B22 – Abschluss 2: QS über B14–B21 (05.11.2026)

- QS mit `qs-korrektheit`, `qs-sicherheit`, `qs-wartbarkeit` nacheinander über
  `git diff 2fa38a3..HEAD`. Sicherheit: keine Befunde. Korrektheit: K1 (mittel, Kommazahl hinter
  einem einstelligen Wert wird als Zehnfaches übernommen). Wartbarkeit: W1–W10 (zwei mittel:
  Sortierschlüssel an vielen Stellen, eine vergessen; Punkteingabe als Property-Zustandsautomat).
  Alle Befunde mit Vorschlag in `berichte/UX-Test-2026-11/aufgaben-note1.md` („Abschluss 2“) – umgesetzt
  wird erst nach Marcos Entscheidung je Befund.
- Doku abgeglichen: Zeilenzahlen in `CLAUDE.md`/`AGENTS.md` (app.py rund 4300), `Architektur.md`
  (Prüfungsbezeichnungen und Sortierung in `db.py`, Rat je Ablehnungsgrund in `db_import.py`).
- Offene Rückfragen aus B15–B21: R-B15 (Web-Status, Entf am Mac), R-B16 (ED-Satz „Anmerkungen“),
  R-B20 (Pause zu fester Uhrzeit, Datenmodell), R-B21 (GitHub-Bild auf der Website).
- Vor dem nächsten Build: Screenshots neu (W10), `HANDBUCH.pdf`, Sichtprüfung Demo auf 1366 px.

### ux_test_2026_11 B23 – Punkteingabe: Komma hinter einem Wert, eigenes Eingabefeld (QS B22 K1, W4; 05.11.2026)

- **K1:** Stand „4“ in der Zelle und wurde mit dem Cursor hinter der 4 „,5“ getippt, galt das
  Komma als harmloses erstes Zeichen „bei markiertem Wert“, und 45 wurde gespeichert. Jetzt gilt
  die Ausnahme nur, wenn vor dem Tastendruck noch nichts getippt UND der Wert ganz markiert (oder
  das Feld leer) war – gemerkt vor der Verarbeitung, denn beim Ablehnen ist die Markierung schon
  weg. Sonst wird die Zelle verworfen, die 4 bleibt, die Statuszeile meldet es.
- **W4:** Der Zustand der Ablehnung liegt in `app._PunkteFeld(QLineEdit)` als Attribute
  (`getippt`, `abgelehnt`, `abgelehnt_grund`, `letzte_taste`, `ersetzt_noch_den_wert()`,
  `ablehnen()`) statt in vier Qt-Properties; der Grund kommt aus der reinen Funktion
  `app._ablehnungsgrund(zeichen)`. Das letzte Zeichen merkt sich das Feld selbst
  (`keyPressEvent`), der Delegate-Eventfilter nicht mehr.
- **Tests:** neu `test_komma_hinter_einstelligem_wert_wird_nicht_uebernommen`,
  `test_ablehnungsgrund_je_zeichen`. Gegenprobe: ohne die Änderung scheitern beide. Alle GUI-Tests
  grün (560).
- **Verifikation:** Randfälle (Klick mitten in den Wert, Teilmarkierung, Strg+V, mehrere abgelehnte
  Zeichen, Tab, Leeren) geprüft, alle sicher. Nachgezogen: Einfügen per Tastenkürzel nennt den Grund
  „nur ganze Zahlen einfügen“ statt eines Grunds nach der Taste; Docstring, direkter Attributzugriff.
  Bewusst so gelassen: Nach Entf/Rücktaste auf dem markierten Wert gilt „,5“ als Ablehnung (Feld
  ist dann schon „getippt“), direkt auf dem markierten Wert ersetzt die 5 – beides sicher.

### ux_test_2026_11 B24 – Prüfungsbezeichnung und Sortierung zentral (QS B22 W1–W3, W8; 05.11.2026)

- **W1:** `db.sortiere_pruefungen(bezeichnungen)` an allen Stellen, die Prüfungsnamen sortieren
  (Filter Teilnehmer/Auswertung, `alle_leistungsklassen`, Ergebnisliste, Bewertungsbögen,
  Richter-Bedarf); der Schlüssel `pruefung_sortierschluessel` bleibt für zusammengesetzte
  Sortierungen. Die Demo übergibt ihn jetzt auch an `stechen_gruppen`. In `shs_core` ist der
  Parameter typisiert (`Callable[[str], object] | None`).
- **W2:** `db.pruefung_nach_bezeichnung` (Dict wie `pruefung_nach_kuerzel`); genutzt vom Filter im
  Teilnehmer-Reiter und von der Statistik-Spaltenbreite; der Sortierschlüssel nutzt ein Dict statt
  einer Schleife.
- **W3:** Rückfall in `db_import._angebot_pruefen` vereinfacht (nur `pruefung_bezeichnung`).
- **W8:** neue Imports einsortiert, überzählige Leerzeile in `pdf_export.py` entfernt, nicht mehr
  gebrauchter Import `ALLE_PRUEFUNGEN` in `app.py` und `pdf_export.py` entfernt.
- **Tests:** `test_pruefungsbezeichnung_wie_im_anmeldeformular` um `sortiere_pruefungen` und
  `pruefung_nach_bezeichnung` erweitert (Gegenprobe: scheitert ohne die Änderung). 726 Unittests,
  alle GUI-Tests grün (560).

### ux_test_2026_11 B25 – Tausch-Logik ausgelagert, Docstrings, Tests (QS B22 W5–W7; 05.11.2026)

- **W5:** Die Zählung „wie viele Nummern lägen nach dem Tausch außerhalb ihres Bereichs“ steht als
  `db.nummern_ausserhalb_nach_tausch(bereiche, a, b)` in der Datenschicht (ohne Qt) und hat einen
  eigenen Test; `TeilnehmerTab._tausch_warnung` baut nur noch den Text.
- **W6:** Docstring `HilfeDialog` neu (Knopf, F1 und Menü öffnen beim Reiter), Kommentar im
  `TeilnehmerDialog` neu umbrochen, `_fundstellen` mit Docstring, Suchmuster als Liste statt
  verschachteltem Tupel-Ausdruck.
- **W7:** Faktoren benannt: `desktop_dialoge.DIALOG_MAX_BREITE_ANTEIL`/`DIALOG_MAX_HOEHE_ANTEIL`,
  `ZeitplanTab.SEITENLEISTE_ZUSCHLAG`/`_MIN_ANTEIL`/`_MAX_ANTEIL`; die Tests nutzen die Konstanten
  statt Zahlen. Der Demo-Test prüft den echten Text von Schritt 3 (über `_schritte_aufbauen` mit einer
  Attrappe) statt des Quelltexts; der Dialoggrößen-Test nutzt `monkeypatch`.
- **Tests:** neu `test_nummern_ausserhalb_nach_tausch` (Gegenprobe: scheitert ohne die Änderung).
  728 Unittests, alle GUI-Tests grün (560); nach der Verifikation die Seitenleisten- und Demo-Tests
  wieder um die eigentliche Anforderung ergänzt (Mindestbreite ≥ Textbreite, „Feld „Prüfung““).

### ux_test_2026_11 B26 – Feste Pause mit Lücke davor (R-B20, Nachtest 2 N16; 05.11.2026)

- **Entscheidung Marco 05.11.2026:** Option (b) aus R-B20 statt Teilen; auf Rückfrage zum um die
  Pausenzeit laufenden Block „je nach Restzeit“: Hätte er weniger als 15 Minuten vorher begonnen,
  rückt er als Ganzes hinter die Pause (Lücke davor), sonst folgt die Pause nach ihm. (Ohne diese
  Regel hätte „genau“ nie etwas bewirkt – die Blöcke folgen lückenlos aufeinander.)
- **Daten:** neue Spalte `zeitplan_eintrag.fest_um` („HH:MM“, nur Pausen; Migration über
  `_ZEITPLAN_EINTRAG_NEUE_SPALTEN`, gilt für SQLite und PostgreSQL). Die Berechnung
  (`_zeitplan_zeilen`, `berechne_zeitplan_bloecke`) lässt eine Pause mit fester Uhrzeit frühestens
  dann beginnen (`_pausen_beginn`); eine unlesbare Angabe aus einer fremden Datei zählt nicht.
- **Einfügen:** `add_zeitplan_pause_bei_allen(…, fest=True)` setzt `fest_um` und schiebt die Pause
  vor einen Prüfungsblock, der zur Pausenzeit erst weniger als `FESTE_PAUSE_SCHWELLE_MINUTEN` (15)
  laufen würde. Wer vorher fertig ist, bekommt wie bisher keine Pause.
- **Oberfläche:** Haken „genau um diese Uhrzeit beginnen“ im Pause-Dialog (nur mit „Bei allen
  Richtern“) und im Verteilen-Dialog (beim Neu-Verteilen vorbelegt, wenn die Mittagspause eine
  feste Uhrzeit hat); die Liste zeigt „(fest um … Uhr)“. Handbuch Kap. 6 ergänzt.
- **Tests:** neu `test_feste_pause_ruckt_kurz_vorher_begonnenen_block_dahinter`,
  `test_feste_pause_teilt_keinen_laenger_laufenden_block`, `test_feste_pause_ueber_dialog_und_beim_verteilen`;
  Pause-Dialog-Test und Attrappen um „genau“ erweitert.
  Gegenprobe: ohne die Änderung scheitern die neuen Tests. 732 Unittests, alle GUI-Tests grün (561).
- **Verifikation:** keine Fehler. Nachgezogen: `db.feste_pausenzeit` prüft den Wert einmal (Anzeige
  „(fest um …)“ nur bei lesbarem Wert), Vorschlag beim Neu-Verteilen nimmt die feste Uhrzeit,
  Handbuch nennt Bearbeiten/Verschieben, Test für unlesbare Werte. Zurückgestellt als R-B26:
  Mitternacht, Mindestabstands-Wartezeit vor einer festen Pause, feste Uhrzeit beim Bearbeiten.

### ux_test_2026_11 – Rückfragen R-B15, R-B16, R-B21, R-B26 entschieden (05.11.2026)

- Marco: wie vorgeschlagen. R-B15 (Web-Satz „nur falls veröffentlicht“, Entf am Mac) und R-B26
  (Mitternacht, Wartezeit vor fester Pause, feste Uhrzeit beim Bearbeiten) bleiben so.
- R-B16: Die ED-Rückfrage „Mehrere Gegenstände bei ED?“ sagt jetzt „einen weiteren bitte mit dem
  Teilnehmer klären“ (kein neues Feld).
- R-B21: Das GitHub-Bild (`handbuch_github_assets.png`) steht auch auf der Website im Abschnitt
  Installation (`docs/index.html`) – geht nach der Website-Regel erst mit dem nächsten Release online.
- Damit sind alle Rückfragen aus dem UX-Test 2026-11 beantwortet; offen bleibt vor dem nächsten
  Build W10 (Screenshots neu, `HANDBUCH.pdf`, Sichtprüfung Demo auf 1366 px).

## Version 1.0.56

- **UX-Test 2026-11** mit Nachtest (B1–B26, Aufgabenliste `berichte/UX-Test-2026-11/aufgaben-note1.md`):
  einheitliche Prüfungsnamen wie im Anmeldeformular samt Formular-Reihenfolge; Auswahl „Prüfung“
  im Teilnehmer-Dialog; Ergebniserfassung mit Markierung zu hoher Werte beim Tippen, Ablehnung von
  Komma/Buchstaben (alter Wert bleibt), Status- und Abbruch-Spalte; Zeitplan mit Bestätigung nach
  dem Verteilen, Mittagspause im Verteilen-Dialog, fester Pausenzeit mit Lücke davor (neue Spalte
  `zeitplan_eintrag.fest_um`), Richtername beim Anlegen, breiterer Seitenleiste; Teilnehmer mit
  Entf = Löschen und Tausch-Warnung; Import mit „Letzter Import“ und Rat je Ablehnungsgrund;
  zweispaltiger Termin-Dialog; Hilfe mit Suche, F1/Knopf beim Reiter und Tastenkürzeln; Demo mit
  echtem „Schritt zurück“ und Rückfrage bei „Beenden“; Kurzanleitung Installation als PDF.
- Zwei Abschluss-QS (B11, B22) mit drei Rollen, alle Befunde umgesetzt bzw. von Marco entschieden;
  Vor-Build-Verifikation ohne Einwände, ihre Kleinigkeiten nach Marcos Entscheidung umgesetzt
  (feste Pause in Hilfe, Architektur.md, UML.md) bzw. akzeptiert (OFFEN.md C38–C40).
- Die Version ist erhöht. Alle 15 Desktop-Screenshots sind neu (neue Prüfungsnamen, zweispaltiger
  Termin-Dialog, jetzt 1080×680), `docs/HANDBUCH.pdf` und `docs/INSTALLATION_KURZ.pdf` neu,
  `RELEASE_NOTES.md` neu geschrieben, `OFFEN.md` nachgezogen.
- **Tests lokal:** 734 Unittests (183 übersprungen) und 561 GUI-Tests grün, UML mit mmdc geprüft.
- Website-Änderungen (Kurzanleitung, GitHub-Bild) gehen mit diesem Release online.

## 05.11.2026: 1.0.56 ausgeliefert, Quellcode-Spiegel auf 1.0.56

- Marco hat `main` gepusht und `v1.0.56` getaggt (Tag auf 6b5a004); alle Workflows grün.
- `SHS-Pruefungsprogramm-Quellcode` ist nach der bisherigen Regel nachgezogen: alle Dateien aus
  Git außer `.claude/`, die Workflows zusätzlich im Wurzelordner, im Spiegel nichts gelöscht.
  - 33 Dateien sind neu: die UX-Test-Berichte unter `berichte/UX-Test-2026-11/`, die Kurzanleitung
    (`docs/INSTALLATION_KURZ.md`/`.pdf`), neun Handbuch-Bilder (Edge, Setup, SmartScreen,
    GitHub-Assets) und `testdaten/altversionen/v1.0.56/` mit 4 Dateien.
  - 53 Dateien sind geändert.
  - Der Byte-Abgleich danach ist identisch (330 Dateien).
- Die claude.ai-Ablage „SHS“ kann diese Sitzung nicht erreichen. Marco lädt dort
  `Fortschritt.md` und `Architektur.md` neu hoch (`Grobkonzept.md` ist unverändert).

## 05.11.2026: Zeitplan bei großer Schrift rechts abgeschnitten (Meldung nach 1.0.56)

- **Meldung Marco:** Bei „Groß“ und „Sehr groß“ ist der Zeitplan rechts teilweise abgeschnitten; nach
  dem Wechsel zurück auf „Normal“ braucht es Minimieren/Maximieren für die richtige Ansicht.
- **Ursache (gemessen mit Windows-Schriften, 1536 px wie Full HD bei 125 %):** Die Kopfzeile des
  Zeitplans war eine Zeile mit 1338/1482/1636 px Mindestbreite (Normal/Groß/Sehr groß). Bei „Sehr
  groß“ wurde das Fenster breiter als der Bildschirm, bei „Groß“ war es sehr knapp; das maximierte
  Fenster schrumpfte nach dem Zurückschalten nicht von selbst.
- **Behebung:** Einstellungen (Start, Dauer, Mindestabstand) und Knöpfe (Richter hinzufügen,
  Automatisch verteilen, Zeitplan-PDF) in zwei Zeilen – Zeitplan-Reiter jetzt 1023/1126 px bei
  Groß/Sehr groß. Nach jedem Darstellungswechsel (Schrift, Design, Akzent) passen sich alle
  Hauptfenster (auch das der Demo) wieder an den Bildschirm an (`HauptFenster._an_bildschirm_anpassen`:
  maximiert neu maximieren, sonst verkleinern und verschieben; nichts tun, wenn die Mindestgröße
  ohnehin nicht passt). Screenshot `handbuch_zeitplan`/`zeitplan` neu.
- **Tests:** neu `test_zeitplan_kopf_in_zwei_zeilen`, `test_fenster_passt_sich_nach_schriftwechsel_dem_bildschirm_an`;
  `test_ergebnistabelle_sehr_gross_nur_maximiert_voll` schaltet das Einpassen ab (Offscreen-Bildschirm
  kleiner als das Testfenster). Gegenprobe: ohne die Änderung scheitern die neuen Tests. Alle
  GUI-Tests grün (564). Verifikation eingearbeitet (alle Fenster, Rahmen und Position, alle
  Darstellungswechsel, kein Sprung ohne Wirkung).
- **Reiter „Teilnehmer“ (Marco: anpassen):** Auf 1366 px bei „Sehr groß“ war die untere Knopfzeile
  mit 1331 px zu breit (Reiter 1349 px, Fenster 1373 > 1362 px). „Startnummer tauschen…“ steht jetzt
  oben bei den Knöpfen für die markierten Teilnehmer; Reiter 1181 px, Fenster 1205 px – passt.
  `test_teilnehmer_knopfleiste_zweizeilig` angepasst (Gegenprobe: scheitert mit der alten
  Anordnung), Screenshot `handbuch_teilnehmer` neu. Alle GUI-Tests grün (564). Gemessen sind damit
  alle Reiter bei „Sehr groß“ auf 1366 px höchstens 1181 px breit.

## Version 1.0.57

- **Große Schrift (Meldung Marco nach 1.0.56):** Zeitplan-Kopf in zwei Zeilen, „Startnummer
  tauschen…“ in die obere Knopfzeile des Teilnehmer-Reiters; alle Reiter passen bei „Sehr groß“
  auf 1366 px. Nach jedem Darstellungswechsel passen sich alle Hauptfenster wieder an den
  Bildschirm an (`HauptFenster._an_bildschirm_anpassen`).
- Vor-Build-Verifikation ohne Einwände; auf Marcos Entscheidung `_an_bildschirm_anpassen` im
  Klassendiagramm (`UML.md`) ergänzt, mit mmdc geprüft.
- Die Version ist erhöht, alle 15 Desktop-Screenshots neu, `docs/HANDBUCH.pdf` und
  `docs/INSTALLATION_KURZ.pdf` neu, `RELEASE_NOTES.md` neu geschrieben.
- **Tests lokal:** 734 Unittests (183 übersprungen) und 564 GUI-Tests grün.

## 05.11.2026: 1.0.57 ausgeliefert, Quellcode-Spiegel auf 1.0.57

- Marco hat `main` gepusht und `v1.0.57` getaggt (Tag auf c5a1db9); alle Workflows grün.
- `SHS-Pruefungsprogramm-Quellcode` ist nach der bisherigen Regel nachgezogen (alle Dateien aus Git
  außer `.claude/`, die Workflows zusätzlich im Wurzelordner, im Spiegel nichts gelöscht): 4 Dateien
  neu (`testdaten/altversionen/v1.0.57/`), 24 geändert; der Byte-Abgleich danach ist identisch
  (334 Dateien).
- Die claude.ai-Ablage „SHS“ kann diese Sitzung nicht erreichen. Marco lädt dort `Fortschritt.md`
  neu hoch (`Architektur.md` und `Grobkonzept.md` sind seit 1.0.56 unverändert).

## CLAUDE.md überarbeitet (09.11.2026, nur Dokumentation, nichts committet)

Prüfung der `CLAUDE.md` mit Marco, alle Punkte umgesetzt:

- Widerspruch aufgelöst: "KEIN Commit bis Build" gilt mit zwei Ausnahmen (reine Doku-Änderungen,
  Ablauf `aufgaben-abarbeitung` committet je Aufgabe lokal, nie gepusht).
- Verweis auf die private Memory "Lokales Python" ersetzt durch den Pfad zum Anaconda-Python.
- Zeilenzahlen der Module entfernt (stehen in `Architektur.md`, veralten sonst).
- Cowork-Altlasten gestrichen (Einleitung "Sitzungsablauf", Geräte-Brücke, Byte-Abgleich);
  der Hinweis zur verwaisten `index.lock` bleibt als eine Zeile.
- Build-Regeln gekürzt, Datumsstempel entfernt, Agenten-Aufzählung durch Verweis ersetzt.
- Neu: Zeile zu Sprache/Commit-Stil/Shell. `AGENTS.md` wird jetzt aus `CLAUDE.md` erzeugt
  (`python test_agents_spiegel.py --schreiben`); `test_agents_spiegel.py` prüft den Gleichstand.
- Hintergrund der gestrichenen "Anlass"-Sätze: Bei 1.0.35 wurde der Handbuch-Screenshot erst
  nach dem Build erneuert und musste auf den nächsten Build warten (daher "Dokumente und
  Screenshots vor dem Build"). 1.0.37 wurde gebaut, obwohl die Verifikation noch zwei kleine
  Punkte gemeldet hatte; sie kamen als Nachtrag-Commit, zwei Build-Durchläufe statt einem
  (daher "Offene Punkte vor dem Build klären").

## Version 1.0.58: Abrechnung Leistungsrichter, Checkliste, Reiter „Ausdrucke/Export“ (09.11.2026)

Marcos Wunsch: neuer Reiter und neue Funktion „Abrechnung Leistungsrichter“ mit 0,35 € je
Kilometer und 50 € Tagespauschale je Leistungsrichter, beide Werte Standard und änderbar.
Befragung mit Marco, Entscheidungen:

- **Nur Desktop** (Web bleibt bei der Ergebniserfassung). Neuer Reiter zwischen „Übersicht“ und
  „Verwaltung“ (`desktop_abrechnung.py`, `AbrechnungTab`).
- **Richter:** Wertungsrichter 1–5 der Veranstaltungsdaten, nur mit eingetragenem Namen (keine
  leeren Zeilen), keine Prüfungsleiter oder Helfer. Die Eingaben hängen an der Position 1–5: eine
  Umbenennung lässt die Beträge stehen.
- **Kilometer:** von Hand je Richter, Gesamtstrecke Hin und zurück, eine Nachkommastelle. Es gibt
  keine Entfernungsberechnung.
- **Rechnung:** Fahrtkosten = km × Satz, kaufmännisch auf Cent gerundet; Summe = Fahrtkosten +
  Pauschale (einmal je Richter, ein Termin = ein Prüfungstag). Satz und Pauschale gelten je Termin
  (Standard 0,35 / 50) und sind je Richter überschreibbar (leer = Satz des Termins). Obergrenzen
  gegen Tippfehler: 10.000 km, 10 €/km, 10.000 € Pauschale.
- **Ausgabe:** PDF-Gesamtübersicht (`pdf_export.erstelle_abrechnung_pdf`) und eine Quittung je
  Richter, eine Seite je Richter, in einem PDF (`erstelle_quittungen_pdf`): Betrag, Betrag in
  Worten, von (Verein), für (Prüfung, Datum, Ort, km × Satz, Pauschale), Empfänger, Ort/Datum und
  Unterschrift von Hand. Kein CSV, keine Anschrift/IBAN auf der Quittung (Nicht-Ziele).
- **Daten:** drei neue Spalten in `veranstaltung` (`lr_km_satz`, `lr_tagespauschale`,
  `lr_abrechnung` = JSON je Position), Migration über `_VERANSTALTUNG_NEUE_SPALTEN`, Sync nach
  PostgreSQL (`kopiere_termin_daten`) nimmt sie mit. Beim Anlegen eines neuen Termins werden nur die
  Sätze vom letzten Termin vorgeschlagen (`TerminInfo`), nicht die Eingaben je Richter.
- Rechenlogik ohne Qt und DB in `lr_abrechnung.py` (Decimal, Betrag in Worten, tolerantes Lesen
  beschädigter JSON-Eingaben); `dezimal_lesen` lehnt Exponenten, Vorzeichen, NaN und Infinity ab.
- Verifikation (Agent `verifikation`): keine Codefehler. Auf Marcos Entscheidung liest der Parser bei Kilometern und Pauschale einen Punkt mit genau drei Ziffern dahinter als Tausendertrenner („1.234“ = 1234, „0.355“ bleibt dezimal); der Satz je km nie. Ein Termin-Satz mit mehr als zwei Nachkommastellen (nur durch Bearbeiten der Datei möglich) wird bewusst nicht gesondert behandelt. `UML.md` nachgezogen.
- **Änderung nach Marcos Demo-Rückmeldung (09.11.2026):** Satz und Pauschale stehen in jeder Zeile mit den Werten des Termins vorbelegt (gespeichert wird je Richter nur eine Abweichung; die Zeile folgt sonst dem Termin-Satz). Quittungen nur je Richter über den Knopf „Quittung…“ in der Zeile (eigenes PDF, `erstelle_quittungen_pdf(…, nummer=…)`), der Sammelknopf „Quittungen als PDF…“ entfällt. Neuer Knopf „Ablageort öffnen“.
- **CSV-Export (Marco 09.11.2026):** Knopf „Export als CSV…“ zwischen „Übersicht als PDF…“ und „Ablageort öffnen“ (`db_import.exportiere_abrechnung_csv`): UTF-8 mit BOM, Trenner `;`, eine Zeile je Richter mit Datum, Empfänger, Verwendungszweck, Kilometer, Satz je km, Fahrtkosten, Tagespauschale, Betrag (Dezimalkomma, ohne Tausenderpunkt und Währungszeichen) und Art „Ausgabe“; Namen mit Schutz vor CSV-Formeln. Das Zielformat des Vereinstools ist nicht bekannt, die Spalten sind unsere Wahl.
- **Reiter umbenannt (Marco 09.11.2026):** „Export“ heißt jetzt „Ausdrucke/Export“ (Reiterbeschriftung, Hilfeabschnitt, Verweise in Meldungen, Demo, Handbuch und Umstiegshilfe). Der Screenshot `handbuch_export.png` zeigt noch die alte Beschriftung und entsteht beim Build neu. Die Berichte unter `UX-Test-*` bleiben als Historie unverändert.
- **Checkliste zum Abhaken (Marco 09.11.2026):** Im Reiter „Verwaltung“ steht unter dem Knopf der Ablauf aus Handbuch Kapitel 1 als Liste mit Kästchen (`checkliste.py`, 7 Abschnitte, 18 Schritte). Die Haken werden sofort je Termin gespeichert (neue Spalte `veranstaltung.checkliste`, JSON-Liste stabiler Kennungen; Migration, PostgreSQL-Sync, wird beim neuen Termin nicht übernommen). „Alle Haken entfernen“ fragt nach (Vorgabe Nein). Die Schritte sind meine Aufteilung der sieben Zeilen aus Kapitel 1 plus „Leistungsrichter abgerechnet“; Marco hat die Texte noch nicht gesehen.
- **Knopf „Checkliste“ im Kopfbalken (Marco 09.11.2026):** springt von jedem Reiter zum Reiter „Verwaltung“ (`HauptFenster._zur_checkliste`, `VerwaltungTab.zur_checkliste`), klappt die erste Kategorie mit offenen Punkten auf und setzt den Fokus darauf; während der Demoprüfung (Reiter gesperrt) ohne Wirkung. Ohne eigenes Symbol (nutzt „check“ aus den vorhandenen Tabler-Symbolen).
- **Checkliste erweitert (Marco 09.11.2026):** Jede Kategorie ist auf- und zuklappbar und beim Öffnen des Reiters zugeklappt (Überschrift mit „x von y“; der Auf-/Zu-Zustand gilt nur für die Sitzung des Reiters). Eigene Kategorien („Kategorie hinzufügen…“) und eigene Punkte („Punkt hinzufügen…“ in jeder Kategorie, auch den festen) sind möglich, eigene Einträge lassen sich löschen (nach Rückfrage; Kategorie samt Punkten), feste nicht. Speicherung: neue Spalte `veranstaltung.checkliste_eigene` (JSON, eigene Kennungen `e1`, `e2` …, höchstens 20 Kategorien, 200 Punkte, 60/120 Zeichen); eigene Kategorien und Punkte (ohne Haken) werden beim neuen Termin aus dem letzten vorgeschlagen (`TerminInfo`). Eigene Kennungen werden nach dem Löschen eines Punkts mit der höchsten Nummer wiederverwendet, die Haken gelöschter Punkte entfallen dabei mit.
- Verifikation vor dem Build (Agent `verifikation`): ein echter Fehler (Absturz beim Lesen beschädigter eigener Checkliste-Daten mit nicht hashbarem `kategorie`) behoben und mit Tests abgesichert; Handbuch (Kapitel 1 und 9, Screenshots `handbuch_abrechnung`, `handbuch_verwaltung`), `Architektur.md`, `UML.md` (Komponenten, Klassen, Gesamtablauf; mit mmdc geprüft) und README nachgezogen; Kommentare mit der alten Reiterbezeichnung angepasst. Nicht behandelt, weil nur per Dateibearbeitung möglich: ein Termin-Satz mit mehr als zwei Nachkommastellen wird gerechnet, aber auf zwei Stellen gerundet angezeigt.
- Tests: `test_lr_abrechnung.py` (Rechnen, Worte, Speicherung, Migration, PDFs),
  `test_app_gui.py` (sieben Tests am Ende: Reiter, Sätze, ungültige Eingabe, Export, Reihenfolge,
  Dialog).
- **Noch offen vor dem Build:** Handbuch (Kapitel 9 oder eigener Abschnitt), Screenshot des neuen
  Reiters in `docs/bilder/` (`tools/screenshots.py`), `README*.md` prüfen. Die Hilfe (F1) hat den
  Abschnitt schon.

## 09.11.2026: 1.0.58 ausgeliefert, Quellcode-Spiegel auf 1.0.58

- Marco hat `main` gepusht und `v1.0.58` getaggt (Tag auf 918dad9, die Website-Änderung `c4afc2a` liegt danach auf `main`); alle Workflows sind durchgelaufen (Marcos Meldung).
- `SHS-Pruefungsprogramm-Quellcode` ist nach der bisherigen Regel nachgezogen (alle Dateien aus Git außer `.claude/`, die Workflows zusätzlich im Wurzelordner, im Spiegel nichts gelöscht): 11 Dateien neu, 42 geändert; der Byte-Abgleich danach ist identisch (345 Dateien).
- Die claude.ai-Ablage „SHS“ kann diese Sitzung nicht erreichen. Marco lädt dort `Fortschritt.md` und `Architektur.md` neu hoch (`Grobkonzept.md` ist unverändert).

## Nach 1.0.58 (09.11.2026, Arbeitsstand, nichts committet): Reiterbezeichnungen fett, Checkliste Vorgaben ausblenden

- **Reiterbezeichnungen fett:** alle Reiter der Hauptleiste in Stärke 600 (bisher nur der gewählte). Das Stylesheet-Referenzstück in `test_theme.py` ist angepasst, neuer Test `test_reiterbezeichnungen_sind_fett`. Die Screenshots in `docs/bilder/` zeigen noch die alte Schrift und entstehen beim nächsten Build neu. Offen: ob „fett“ nur die Reiterleiste oder auch die Kategorien-Überschriften der Checkliste meinte (die waren schon fett).
- **Checkliste, Vorgaben ausblenden:** vorgegebene Punkte (✕ hinter dem Punkt) und Kategorien („Kategorie ausblenden“) lassen sich für den Termin ausblenden, mit Rückfrage. Ausgeblendetes wird nicht angezeigt und nicht mitgezählt, der Haken darauf entfällt; „Ausgeblendetes zeigen (n)“ stellt alles wieder her. Gespeichert im JSON `veranstaltung.checkliste_eigene` unter `ausgeblendet`, wird beim neuen Termin mit den eigenen Einträgen vorgeschlagen. Vorgegebene Einträge werden nie gelöscht.

## Version 1.0.59: Reiter fett, Checkliste Vorgaben ausblenden (09.11.2026)

- Gebündelt: die Änderungen aus „Nach 1.0.58“ (Reiterbezeichnungen fett, Checkliste: Vorgaben und Kategorien für den Termin ausblenden). „Fett“ gilt als erledigt für die Reiterleiste; der Punkt zu den Kategorien-Überschriften entfällt.
- Nacharbeit aus der Verifikation: Die Rückfrage „Kategorie ausblenden“ nennt, dass eigene Punkte darin gespeichert bleiben, aber ebenfalls ausgeblendet sind. `Architektur.md` beschreibt das Ausblenden in `checkliste.py`.
- Handbuch, Screenshots, Handbuch-PDF und Kurzanleitung neu erzeugt, `RELEASE_NOTES.md` neu geschrieben.
- Tests: Suite 779 OK (183 übersprungen), Checkliste/Theme-GUI-Tests 75 bestanden. Beobachten: `test_teilnehmer_dialog_startgroesse_und_feldbreite` war im GUI-Gesamtlauf einmal rot, einzeln grün (vermutlich reihenfolgeabhängig).

## 09.11.2026: Quellcode-Spiegel auf 1.0.59, künftig automatisch beim Build

- `SHS-Pruefungsprogramm-Quellcode` auf den Stand des Build-Commits gebracht (alle Dateien aus Git außer `.claude/`, Workflows zusätzlich im Wurzelordner, nichts gelöscht); Byte-Abgleich ohne Abweichung.
- Marco: Den Spiegel zieht die Sitzung künftig beim Build selbst nach. In `CLAUDE.md` und `.claude/skills/shs-build/SKILL.md` festgehalten.

## 09.11.2026: 1.0.59 ausgeliefert

- Marco hat `main` gepusht und `v1.0.59` getaggt; alle Workflows sind grün (Marcos Meldung). Der Quellcode-Spiegel stand schon auf 1.0.59. Offen für Marco: claude.ai-Ablage „SHS“ (`Fortschritt.md`, `Architektur.md`) neu hochladen.

## 10.11.2026: Rückmeldung eines Prüfungsteilnehmers (zwei Punkte), nur analysiert, Umsetzung folgt am Laptop

Quelle: WhatsApp-Nachricht an Marco mit zwei Fotos (Teilnehmer-Dialog DK LK 2, Bewertungsbogen). Nichts umgesetzt, nichts gebaut.

1. **Teilnehmer-Dialog, DK: schon vergebene Disziplin beim nächsten Gegenstand sperren.** Heute stehen bei Gegenstand 1–3 je eine Combo „gesucht in“ (frei/Trümmerfeld/Flächensuche/Behältnisstrecke), alle mit allen Einträgen; eine doppelte Vergabe wird erst beim Speichern bemängelt (`desktop_dialoge.py`, Warnung „Gegenstand-Zuordnung doppelt vergeben“). Wunsch: wer eine Disziplin in einer Zeile gewählt hat, kann sie in den anderen beiden Zeilen nicht mehr wählen.
   - Umsetzung: in `desktop_dialoge.py` bei Änderung einer der drei Combos (`currentTextChanged`) in den beiden anderen Combos die Einträge der gewählten Disziplin per Qt-Item-Modell deaktivieren (`model().item(i).setEnabled(False)`); „frei“ bleibt immer wählbar. Auch nach dem Laden eines vorhandenen Teilnehmers (Zeilen ~517–519) und beim Wechsel ED↔DK (`_gegenstand_felder_aktualisieren`) neu anwenden. Die Speichern-Prüfung bleibt als Sicherung.
   - Entschieden (Marco 10.11.2026): Die Disziplin bleibt in den anderen Zeilen sichtbar, ist aber ausgegraut und nicht auswählbar. Web-Erfassung hat diese Felder nicht, bleibt unberührt. Test in `test_app_gui.py` ergänzen, Handbuch/Screenshot des Dialogs prüfen.
2. **Bewertungsbogen, Seite 2: Startnummer anzeigen.** Seite 1 zeigt oben rechts das Feld „Start-Nr.“; die DK-Seite 2 (`_dk_folgeseiten_kopf` in `pdf_export.py`, „LK x / HF / Hund“) hat keins. Wunsch: Startnummer auch dort, damit die lose Rückseite eindeutig zuzuordnen ist.
   - Umsetzung: `_dk_folgeseiten_kopf` um eine dritte Spalte mit derselben „Start-Nr.“-Box wie in `_bewertungsbogen_story` erweitern (Breiten z. B. 25 / 101 / 44 mm, Summe 170 mm), damit lange Namen nicht umbrechen und Seite 2 nicht auf eine dritte Seite rutscht. Das Feld bei fehlender Startnummer leer lassen wie auf Seite 1. Test in `test_pdf_export.py` (Startnummer kommt zweimal im Text vor), Handbuch-/Website-Bilder des Bogens prüfen.

### Nachtrag 10.11.2026: Idee von Marco, DK-Bögen zusätzlich pro Disziplin ausgeben (nur analysiert)

- Wunsch: Beim Dreikampf optional **ein Blatt je Disziplin** statt des 2-Seiten-Bogens, damit jeder Richter gleich sein passendes Paket (nur Trümmer, nur Fläche oder nur Behältnis) bekommt. Als **zusätzliche Auswahl** neben dem bisherigen Bogen, nicht als Ersatz.
- Bestand: `erstelle_alle_bewertungsboegen_pdf` (Auswahl über `BewertungsbogenAuswahlDialog`, Aufruf in `desktop_auswertung.py`) setzt je Teilnehmer `_bewertungsbogen_story` zusammen: Seite 1 = Kopf, Stammdaten, Trümmerfeld, Fußzeile; Seite 2 = Folgekopf, Fläche, Behältnis, GESAMT. Die Abschnitte kommen schon einzeln aus `_bewertungsabschnitt`.
- Umsetzungsskizze: neuer Modus (z. B. `je_disziplin`) in `erstelle_alle_bewertungsboegen_pdf` bzw. eine zweite Funktion; Sortierung erst alle Trümmer-Blätter nach Startnummer, dann alle Fläche, dann alle Behältnis (ergibt drei Stapel). Jedes Blatt braucht Start-Nr., LK, HF, Hund und Gegenstand dieser Disziplin (Kopf wie Seite 1, Start-Nr. wie im Punkt oben). Dialog um die Wahl „Bogen je Teilnehmer / je Disziplin“ erweitern; Tests in `test_pdf_export.py`, Handbuch und Screenshot des Dialogs.
- **Offene Fragen an Marco:** (1) Fläche und Behältnis je ein eigenes Blatt (heute teilen sie sich Seite 2)? (2) Soll die GESAMT-Zeile mit Wertungsnoten-Tabelle auf einem eigenen Blatt je Teilnehmer entstehen oder entfällt sie (Gesamtpunkte rechnet das Programm)? (3) Wertungsnoten-Tabelle auf jedem Disziplin-Blatt oder wie heute nur beim Trümmerfeld/Behältnis? (4) Nur DK oder auch ED (dort ohnehin ein Blatt)?
- **Entschieden (Marco 10.11.2026):** (1) Fläche und Behältnis bekommen je ein eigenes Blatt, also drei Blätter je DK-Teilnehmer. (2) Die GESAMT-Zeile entfällt im Modus „je Disziplin“. (4) Nur DK, ED bleibt unverändert. Der bisherige 2-Seiten-Bogen bleibt als andere Auswahl erhalten. **Noch offen:** (3) Wertungsnoten-Tabelle auf jedem Blatt oder wie heute (nur Trümmer und Behältnis, nicht Fläche).
- **Entschieden (Marco 10.11.2026), Punkt (3):** Die Wertungsnoten-Tabelle steht im Modus „je Disziplin“ auf jedem der drei Blätter, jeweils unten. Damit sind alle Fragen zu den Disziplin-Blättern geklärt; Umsetzung folgt am Laptop.

### Idee 10.11.2026 (Marco, nur gesammelt, nicht entschieden): Etiketten zur Beschriftung von Gläsern

- Gedanke: Etiketten für die Gläser (Startnummer, Name, Disziplin, Hund), untereinander zum Ausschneiden und Aufkleben, mit wählbarer Größe der Klebefelder.
- Anknüpfung: Die vorhandenen Ergebnis-Etiketten (`erstelle_ergebnisliste_etiketten_pdf`, feste Größe `ETIKETT_BREITE_MM` x `ETIKETT_HOEHE_MM`, gestrichelte Schnittlinie) sind das Vorbild; ein neuer Export bräuchte eigene Maße, die der Nutzer einstellt (Breite/Höhe in mm, evtl. mehrere Etiketten nebeneinander als Raster).
- Offene Fragen: Welche Gläser genau (Geruchsproben, Gegenstände, Proben je Disziplin)? Ein Etikett je Teilnehmer oder je Teilnehmer und Disziplin (bei DK dreimal)? Gewünschte Größen/Vorlagenbogen (z. B. Avery-Raster)? Mit Gegenstand-Text? Sortierung nach Startnummer oder nach Disziplin (passend zu den Disziplin-Blättern)?
- **Antworten Marco 10.11.2026 (Glas-Etiketten):** Die Gläser sind Behältnisse zum Einsammeln der Gegenstände. Ein Etikett je Hund/Teilnehmer. Raster: „sowohl als auch“, also sowohl Etikettenbogen mit festem Raster als auch normales Papier mit Schnittlinien (beides als Auswahl). Offen: ob der Gegenstand-Text aufs Etikett soll; bei der Antwort „3“ ist unklar, ob damit die dritte Frage gemeint war oder drei Gegenstände je Behältnis (bei DK je Teilnehmer drei Gegenstände).
- **Klarstellung Marco 10.11.2026:** Das „3“ war die Antwort auf die dritte Frage: sowohl Klebeetiketten (Bogen mit festem Raster) als auch normales Papier mit Schnittlinien, als Auswahl. Offen bleibt nur, ob der Gegenstand-Text aufs Etikett soll.
- **Marco 10.11.2026:** „2. Ja“, von mir als Antwort auf die Frage nach dem Gegenstand-Text gelesen: Der Gegenstand-Text kommt aufs Etikett (Startnummer, Name, Disziplin, Hund, Gegenstand). Falls „2“ die frühere Frage 2 (ein Etikett je Teilnehmer oder je Teilnehmer und Disziplin) meinte, bei der Umsetzung nachfragen.

## 10.11.2026: Umsetzung der Rückmeldungen eines Prüfungsteilnehmers und Marcos Ideen (Arbeitsstand, kein Build, keine neue Version)

- **Entschieden zu den Glas-Etiketten (Marco, 10.11.2026):** Die Etiketten sind nur für die Behältnisse gedacht (Gegenstände einsammeln), ein Etikett je Hund mit dem einen Gegenstand der Behältnisstrecke. Damit ist die Frage „je Teilnehmer oder je Disziplin“ erledigt.
- **DK-Dialog:** eine bei einem Gegenstand gewählte Disziplin ist bei den anderen beiden ausgegraut und nicht wählbar (`_vergebene_disziplinen_sperren` in `desktop_dialoge.py`); „frei“ bleibt wählbar, bei ED keine Sperre, die Prüfung „doppelt vergeben“ beim Speichern bleibt. Tests in `test_app_gui.py`.
- **Bewertungsbogen Seite 2:** Kasten „Start-Nr.“ oben rechts (`_startnummer_box`, `_dk_folgeseiten_kopf` in `pdf_export.py`), Seite 2 bleibt bei zwei Seiten. Test in `test_pdf_export.py`.
- **DK je Disziplin:** `erstelle_alle_bewertungsboegen_pdf(..., je_disziplin=True)` und Häkchen im Auswahldialog „Bewertungsbögen“: je DK-Teilnehmer drei Blätter, sortiert erst alle Trümmer, dann Fläche, dann Behältnis, ohne GESAMT-Zeile, Wertungsnoten-Tabelle unten auf jedem Blatt; ED unverändert und vorweg.
- **Etiketten für Behältnisse:** neuer Knopf „Etiketten Behältnisse (PDF)…“ im Reiter Ausdrucke/Export (`erstelle_behaeltnis_etiketten_pdf`, `BehaeltnisEtikettenDialog`): ein Etikett je Hund mit Behältnisstrecke (DK und ED Behältnisstrecke) mit Start-Nr., Name, Hund, Prüfung und Gegenstand der Behältnisstrecke. Größe der Klebefelder und Ränder einstellbar (Standard 70 x 37 mm), wahlweise Etikettenbogen (Raster, ohne Linien) oder normales Papier mit Schnittlinien.
- **Vor dem Build noch zu tun:** Handbuch (`docs/HANDBUCH.md`), Screenshots (Teilnehmer-Dialog, Auswahl Bewertungsbögen, neuer Etiketten-Dialog, Reiter Ausdrucke), Hilfe (F1), `Architektur.md`; Marco testet vorher mit den Muster-PDFs.
- **Nacharbeit aus der Verifikation (Marco: alle Befunde umsetzen):** A) Behältnis-Etiketten passen die Schrift an die Etikettenhöhe an, der Gegenstand steht gleich unter der Startnummer, Hund und Prüfung teilen sich unter 28 mm eine Zeile, Mindesthöhe im Dialog 20 mm; B) bei ED steht die Disziplin nicht mehr doppelt im Label; C) der Etiketten-Dialog überschreibt vom Nutzer gesetzte Ränder nicht mehr; D) der OK-Knopf-Zugriff im Dialog ist vereinfacht; G) neue Tests (kleine Höhe, 0 Teilnehmer, mehrere Seiten, geladener Teilnehmer, Häkchen „je Disziplin“). E (Schutz gegen zu große Etiketten bleibt als Absicherung) und F (Vorname hinter „…“ bei sehr langen Namen) bewusst unverändert. H) `docs/HANDBUCH.md`, `Architektur.md`, `UML.md` nachgezogen; Screenshots und F1-Hilfe bleiben vor dem Build offen.
- **Demo:** Die Demodaten (`demo_daten.py`) haben bei den beiden Dreikampf-Teams jetzt alle drei Gegenstände den Disziplinen zugeordnet, damit die Behältnis-Etiketten einen Gegenstand zeigen; der Demo-Schritt 13 (Ausdrucke) nennt die neuen Ausdrucke.

## 10.11.2026: Demoprüfung an den Stand 1.0.58/1.0.59 angepasst (Arbeitsstand, nichts committet)

- Marco: „aktualisiere die Demo-Version“, gewählt: Demoprüfung an den Programmstand anpassen.
- `desktop_demo.py`: zwei neue Schritte nach dem PDF-Schritt – „14. Abrechnung der Leistungsrichter“ (Reiter zeigen, Tabelle und „Übersicht als PDF…“ markieren) und „15. Checkliste zum Prüfungstermin“ (Reiter „Verwaltung“, `zur_checkliste()`); „Richter am Tablet“ ist jetzt Schritt 16, „Demo-Termin löschen“ Schritt 17.
- `docs/HANDBUCH.md`: Ablaufliste der Demoprüfung um beide Schritte ergänzt. `test_app_gui.py`: Schrittzahl 17 statt 15. 49 Demo-Tests grün.
- Offen: kein Versionsbump/Build; Screenshot `handbuch_demo.png` zeigt Schritt 8 und bleibt unverändert; HANDBUCH.pdf entsteht erst beim Build.

## 10.11.2026: Klick-Test-Demo `SHS-Demo-vor-Build` aktualisiert (Arbeitsstand, nichts committet)

- Marco meinte mit „Demo-Version“ den Ordner `C:\Users\mbruv\Documents\SHS-Demo-vor-Build` (nicht nur die Demoprüfung im Programm).
- `demo_erzeugen.py`: Dreikampf-Teams (Gerdes, Hansen, Ivers) mit drei zugeordneten Gegenständen, ED-Teams mit Gegenstand-Zuordnung; Termine neu erzeugt.
- `Checkliste.md` neu (Stand 10.11.2026: DK-Sperre, Startnummer Seite 2, Bögen je Disziplin, Behältnis-Etiketten, Abrechnung, Checkliste, Demoprüfung mit 17 Schritten); die alte Liste liegt als `Checkliste_2026-10-15.md` daneben.
- Marco klickt die Liste noch durch; kein Build, kein Versionsbump.

- **Nachbesserung DK-Sperre (Marco 10.11.2026, Screenshot):** Im geöffneten Auswahlfeld „gesucht in“ waren gesperrte Disziplinen nicht von wählbaren zu unterscheiden (das Stylesheet zeichnet gesperrte Listeneinträge nicht von selbst blasser). `_vergebene_disziplinen_sperren` setzt jetzt zusätzlich Farbe (`TEXT_DISABLED`), Kursivschrift und einen Tooltip an den gesperrten Einträgen und nimmt beides bei Entsperrung zurück. Test in `test_app_gui.py`.

- **Bewertungsbogen je Disziplin auch im Reiter Teilnehmer (Marco 10.11.2026):** „Bewertungsbogen (PDF)…“ fragt bei einem Dreikampf-Teilnehmer „Zwei Seiten / Drei Blätter (je Disziplin) / Abbrechen“ (`app.py`, `_bewertungsbogen_exportieren`); `pdf_export.erstelle_bewertungsbogen_pdf(..., je_disziplin=False)`. ED fragt nicht. Tests in `test_pdf_export.py` und `test_app_gui.py`, Handbuch und F1-Hilfe ergänzt. Der Klick-Test-Liste (`SHS-Demo-vor-Build\Checkliste.md`, B) fehlt dieser Punkt noch.

## 10.11.2026: Abgleich der Oberfläche – gleiche Funktionen an allen passenden Stellen (Marco: „setze alle Punkte um“, Arbeitsstand, nichts committet)

Auslöser: „Bewertungsbogen bei den Teilnehmern“ fehlte die Wahl „drei Blätter“ (siehe oben); Marco bat, die Oberfläche auf ähnliche Lücken zu prüfen, und ließ danach alle acht gefundenen Punkte umsetzen:

1. **Leeres Anmeldeformular im Reiter „Formular-Import“** (`leeres_formular_btn`); die Logik steht jetzt gemeinsam in `desktop_gemeinsam._anmeldeformular_pdf_speichern` (auch für den Export-Reiter).
2. **„Ablageort öffnen“** auch in Teilnehmer, Zeitplan, Auswertung und Formular-Import-Export (gemeinsam `_ablageort_ordner_oeffnen`; Export-Reiter und Abrechnung rufen sie ebenfalls auf, Tests patchen jetzt `desktop_gemeinsam._url_oeffnen`).
3. **Suchfeld „Suche“ (Name, Vorname, Hund; Teilwörter, alle Wörter müssen vorkommen)** in Teilnehmer, Ergebniserfassung und Auswertung (`_name_passt`).
4. **„Bewertungsbogen (PDF)…“ auch in Ergebniserfassung und Auswertung** für die aktuelle bzw. markierte Zeile; gemeinsame Funktion `_bewertungsbogen_fuer_teilnehmer` (mit der Frage zwei Seiten / drei Blätter beim Dreikampf).
5. **Export-Reiter: „Abrechnung Leistungsrichter (PDF)…“ und „Checkliste (PDF)…“** (neu: `pdf_export.erstelle_checkliste_pdf`, „[x]“/„[ ]“ je Punkt, Kategorien mit Zähler). Knopfanzahl im Export-Reiter jetzt 14.
6. **„Rangliste drucken“ vs. „Ergebnisliste“:** Es ist dieselbe PDF (`erstelle_ergebnisliste_pdf`), die Auswertung filtert nur nach Art/LK. Tooltip am Knopf erklärt das jetzt.
7. **Startbildschirm mit Menüs „Ansicht“ (Hintergrund, Akzentfarbe, Schriftgröße) und „Hilfe“** (`StartDialog._menue_aufbauen`, gemeinsame Modulfunktion `_auswahl_menue_aufbauen`); der Hinweistext dort angepasst.
8. **Rechtsklickmenü** in Teilnehmerliste (alle Aktionen), Ergebniserfassung (Bewertungsbogen) und Auswertung (Bewertungsbogen, Stechen) über `_kontextmenue_aus_knoepfen` (spiegelt die Knöpfe samt Sperrzustand).

Tests in `test_app_gui.py` (Block „UI-Abgleich 10.11.2026“) und `test_pdf_export.py` (Checkliste). Handbuch ergänzt. **Noch zu tun vor dem Build:** Screenshots der geänderten Reiter (Teilnehmer, Ergebniserfassung, Auswertung, Zeitplan, Formular-Import, Ausdrucke/Export, Startbildschirm) neu aufnehmen, F1-Hilfetexte der Reiter durchsehen, Klick-Test (`SHS-Demo-vor-Build\Checkliste.md`).

## 10.11.2026: Weitere Bedienungs-Verbesserungen (Marco: „alle beheben“, Arbeitsstand, nichts committet)

Aus der zweiten Prüfung („was die Bedienung erschwert“), alle acht Punkte:

1. **Speichern ohne Nachfrage:** Haken „Dateien ohne Nachfrage im Ablageort speichern“ im Reiter Ausdrucke/Export (QSettings `export/ohne_nachfrage`, gilt für alle Reiter); `_speicherort_waehlen` nimmt dann den vorgeschlagenen Namen im Ablageort, `_freier_dateipfad` hängt „ (2)“ an, nie überschreiben.
2. **Fenster merken:** Hauptfenster startet weiter maximiert; wurde es zuletzt in normaler Größe benutzt, kommt es mit Größe und Lage zurück (`_fenster_zeigen_wie_zuletzt`, `_fenstergeometrie_merken` über `aboutToQuit`). Spaltenbreiten werden bewusst **nicht** gemerkt (die Spalten passen sich dem Inhalt und der Schriftgröße automatisch an).
3. **Startbildschirm:** Suchfeld (Verein, Ort, Datum) und Sortierung per Spaltenklick; Auswahl und Öffnen laufen über `_angezeigt` statt `_termine`.
4. **Auswertung sortierbar** (Spaltenklick, numerisch für Start-Nr., Punkte, Platz; Klasse in Prüfungsreihenfolge).
5. **Zeitplan:** Blöcke und Pausen per Maus ziehen (`_BlockListe`, `ZeitplanTab._eintrag_ziehen`); das eigentliche Ziehen mit der Maus ist nur im Handtest prüfbar, die Umordnung selbst ist getestet.
6. **Tastenkürzel:** Strg+N, Strg+F, Strg+1…9 im Hauptfenster, Strg+F im Startbildschirm, Strg+Z im Reiter Teilnehmer.
7. **Rückgängig** (eine Ebene) im Reiter Teilnehmer für Löschen (mit Ergebnis, gleiche ID) und Startnummern zurücksetzen (`db.teilnehmer_sichern/-wiederherstellen`, `startnummern_wiederherstellen`; vergebene Nummern bleiben leer).
8. **Rechtsklickmenü** der Ergebniserfassung um „Alle Ergebnisse speichern“ und „Liste aktualisieren“ erweitert.

Dazu Befunde der Verifikation: Rechtsklick auf leere Fläche zeigt kein Menü mehr; Leerzeichen in `desktop_auswertung.py`. Neu: `conftest.py` leitet QSettings in den Tests in einen Temp-Ordner (vorher schrieben die Tests in die echten Benutzereinstellungen). Tests und Handbuch ergänzt. Vor dem Build noch: Screenshots, F1-Texte, Klick-Test.

- **Nacharbeit nach der Verifikation der zweiten Runde (10.11.2026):** „Rückgängig“ gilt jetzt auch, wenn das Löschen mitten in der Liste scheitert (die schon gelöschten lassen sich zurückholen). DB-Tests für `teilnehmer_sichern`/`teilnehmer_wiederherstellen`/`startnummern_wiederherstellen` in `test_db.py` (laufen in der CI auch gegen PostgreSQL). Ein Hänger im Gesamtlauf kam von den Strg+1…9-Kürzeln: Ein Lambda mit `self` hielt das Hauptfenster am Leben, die Tests schlossen es erst beim Aufräumen mit noch ersetzten Funktionen; jetzt `sender()` mit Property. **Offen:** `UML.md`/`Architektur.md` kennen die neuen gemeinsamen Hilfen (`desktop_gemeinsam`), „Rückgängig“, `_BlockListe` und das Startdialog-Menü noch nicht.

## 10.11.2026: Restliche Angleichungen (Marco: „alles anpassen“, Arbeitsstand, nichts committet)

- **Übersicht:** „Richter-Bedarf (PDF)…“ und „Ablageort öffnen“ im Reiter (`TeilnehmerUebersichtTab(conn, ablageort=…)`). **Verwaltung:** „Checkliste (PDF)…“ und „Ablageort öffnen“ unter der Checkliste (`VerwaltungTab(conn, ablageort=…)`).
- **Web:** Suche nach Name oder Hund auf der Teilnehmerliste (`/teilnehmer?q=…`), bewusst als GET-Formular ohne JavaScript, weil die Sicherheitsrichtlinie `script-src 'none'` setzt; unveränderte Richtlinie, Eingabe wird maskiert (Test).
- **F1-Hilfe** der Reiter Teilnehmer, Formular-Import, Zeitplan, Ergebniserfassung, Auswertung, Übersicht, Verwaltung, Ausdrucke/Export und die Tastenkürzel nachgezogen; **Handbuch**, **Architektur.md**, **UML.md** (nur Mermaid-Mitglieder ergänzt, nicht neu gerendert), **Demo-Texte** (Schritte 3, 6, 13) ergänzt.
- **Bewusst nicht gemacht:** Screenshots der geänderten Reiter - die werden laut Build-Disziplin ohnehin nach dem Versionsbump mit der neuen Version aufgenommen.

## 10.11.2026: Automatische Kopie des Termins und Hinweis bei USB-Stick/Netzlaufwerk (Marco, Arbeitsstand, nichts committet)

- **Auto-Sicherung:** `db_sicherung.auto_sicherung_erstellen` legt beim Öffnen eines Termins, danach beim Beenden (`aboutToQuit`) eine konsistente Kopie (SQLite-`backup`) im Ordner `Auto-Sicherung` neben `Termine` ab; je Termin bleiben die letzten 10, Mindestabstand 10 Minuten. Fehler (Datenträger voll, Stick abgezogen) ergeben nur `None` und stören die Arbeit nie; PostgreSQL wird übergangen (dort sichert der Server). Nur im echten Programmlauf (`HauptFenster.auto_sicherung_aktiv`, von `main()` gesetzt), nie in Tests oder der Demo.
- **Laufwerkshinweis:** `desktop_gemeinsam.laufwerksart` erkennt unter Windows USB-Stick und Netzlaufwerk (`GetDriveTypeW`, UNC-Pfade); `HauptFenster.laufwerk_hinweis_zeigen` weist beim Start einmal darauf hin (nicht in der Demo).
- **Tests:** `TestAutoSicherung` in `test_backup.py` (Inhalt/Begrenzung, Mindestabstand, Fehler), zwei GUI-Tests; `conftest.py` räumt den QSettings-Ordner auf, leert die Einstellungen vor jedem GUI-Test und schließt hängende modale Fenster nach 20 s mit Fehlermeldung (Marke `langsam`). Der Test `startgroesse_und_feldbreite` prüfte fälschlich die feste Startbreite; der Dialog wächst absichtlich mit seinem Inhalt und wird nur durch den Bildschirm (95 %) begrenzt - Test angepasst.
- **Stand:** unittest-Module 753 Tests OK, GUI-Suite 614 bestanden. **Nacharbeit nach der Verifikation:** Kopie beim Beenden ohne Mindestabstand, misslungene Kopie wird gelöscht, Hinweis auch beim Terminwechsel, Langpfade (`\?`) nicht mehr als Netzlaufwerk, Tests ergänzt, Architektur.md und Handbuch nachgezogen. **Offen:** Hinweisfenster nicht von Hand auf echtem Stick geprüft.

- **Demo langsamer (Marco 10.11.2026):** Der Erklärtext der Demoprüfung läuft langsamer durch: automatisches Weiter frühestens nach 15 s (vorher 10), Lesezeit 0,6 s je Wort (vorher 0,35), höchstens 60 s (vorher 40); `DemoTour.AUTO_WEITER_S`, `LESEZEIT_JE_WORT_S`, `LESEZEIT_MAX_S`. Das Tipptempo der Demo blieb unverändert. 49 Demo-Tests OK.

## Version 1.0.60: Bewertungsbögen/Etiketten, Auto-Sicherung, Bedienung (10.11.2026)

- Gebündelt: DK-Sperre im Teilnehmer-Dialog, Startnummer auf Seite 2 des Bewertungsbogens, Bögen je Disziplin (Sammel-PDF und Einzelbogen), Etiketten für Behältnisse, Abgleich der Oberfläche (Suche, Ablageort öffnen, Bewertungsbogen je Zeile, Rechtsklickmenüs, Start-Menüs), Bedienverbesserungen (ohne Nachfrage speichern, Fenster merken, Sortierung, Zeitplan ziehen, Kürzel, Rückgängig), Web-Suche, automatische Kopie des Termins samt Laufwerkshinweis, langsamere Demoprüfung, Test-Wächter in `conftest.py`.
- Vor dem Build geklärt (Marco 10.11.2026): Marke `langsam` bleibt liegen (OFFEN B14), Startgrößen-Test geprüft nur noch die Bildschirmgrenze, Glob-Randfall der Auto-Sicherung zurückgestellt (B15), Hinweisfenster am echten Stick offen (A7). Nachgezogen: F1-Hilfe, Handbuch (inkl. Datenschutz-Hinweis zum Ordner Auto-Sicherung), UML.md (Ablauf Auto-Kopie; ein Klammerfehler im Ablaufdiagramm 3 behoben, alle 13 Diagramme rendern), Architektur.md.
- Tests: 753 unittest OK (186 übersprungen, PostgreSQL nur in der CI), GUI-Suite 614 bestanden, 1 Skip (Vordergrundsperre), 1 xfail. Screenshots und HANDBUCH.pdf/INSTALLATION_KURZ.pdf mit 1.0.60 neu erzeugt.

## 10.11.2026: Quellcode-Spiegel auf 1.0.60

- `SHS-Pruefungsprogramm-Quellcode` auf den Stand von 1.0.60 gebracht (351 Dateien, 52 neu kopiert, Workflows zusätzlich in der Wurzel, Byte-Abgleich ohne Abweichung). Gebaut, nicht gepusht und nicht getaggt. Offen für Marco: Push, Tag, Actions prüfen, claude.ai-Ablage „SHS“ (`Fortschritt.md`, `Architektur.md`) neu hochladen.

## 11.11.2026: CI-Fehler PostgreSQL bei „Rückgängig“ behoben

- Die CI meldete zwei Fehler in `test_db.py` (`TestZeitplanPostgres`): `teilnehmer_wiederherstellen` fügte die alte ID ein, in PostgreSQL ist `teilnehmer.id` aber `GENERATED ALWAYS AS IDENTITY`. Jetzt `OVERRIDING SYSTEM VALUE` nur bei `_PostgresConnection` (`db.py`); SQLite unverändert. Zusätzlich ein Wrapper-Test ohne Server (`test_db_postgres_wrapper.py`) und ein positionaler Spaltenzugriff im DB-Test durch Spaltennamen ersetzt.
- Lokal erstmals gegen einen echten PostgreSQL-16-Container (Podman, `SHS_TEST_POSTGRES_DSN`) geprüft: alle 754 Tests der unittest-Module grün, 1 übersprungen. Das Tag `v1.0.60` muss auf den Stand mit diesem Fix zeigen (Marco, Neu-Taggen wegen Namensbereinigung und CI-Fehler).

## 11.11.2026: Code-Struktur (Bewertung auf Best Practices, Marco: Punkte 1 und 3 umsetzen, Arbeitsstand, nichts committet)

- **Anlass:** Bewertung der Anwendung auf Best Practices und Design. Befunde: zu lange Funktionen, zu große Klassen und Dateien, riesige GUI-Testdatei. Marco entschied: Funktionen zerlegen und `app.py`/Tests aufteilen umsetzen; stilles Überschreiben beim gleichzeitigen Speichern im Web und alle Web-Komponenten zurückgestellt (`OFFEN.md` B16); größere Klassen und frühere Entscheidungen folgen als nächster Schritt.
- **Funktionen zerlegt (Verhalten unverändert):** `db._dk_bloecke_entzerren` (Klasse `_DkEntzerrer`, `_dk_reihenfolge_auflockern`, `_konflikt_schluessel`), `TeilnehmerDialog._pruefen_und_akzeptieren` (acht `…_pruefen`-Methoden, gleiche Reihenfolge und Meldungen), `ErgebnisTab.alle_speichern` (`_zeile_speichern`, `_punkte_der_zeile_speichern`, `_speichern_melden`). Unabhängige Verifikation: keine Abweichung.
- **`app.py` aufgeteilt (B12 überholt):** `desktop_teilnehmer.py` (Reiter Teilnehmer und Import-Meldehilfen), `desktop_formular.py` (Formular-Import), `desktop_ergebnis.py` (Ergebniserfassung); Code unverändert verschoben (4264 → rund 1320 Zeilen in `app.py`). Einzige Codeänderung: `_letzten_import_zeigen` prüft per `hasattr` statt `isinstance`, um einen Importkreis zu vermeiden.
- **Tests aufgeteilt:** `test_app_gui.py` (rund 10 000 Zeilen) heißt jetzt `test_gui_demo/ergebnis/teilnehmer/termin/auswertung/zeitplan/darstellung/verwaltung.py`; Fixtures und Hilfen in `gui_hilfen.py` (per `from gui_hilfen import *`). Patch-Ziele der Tests auf die neuen Module umgestellt (`ueberall_ersetzen` kennt die neuen Module). 593 GUI-Tests wie zuvor.
- **Prüfung:** Gesamtlauf der SHS Test Suite vor und nach dem Umbau: 1244 bestanden, 0 fehlgeschlagen, 189 übersprungen.
- **Erledigt (11.11.2026, nach dem Umbau):** Die SHS Test Suite (eigenes Repo, Commit `d0d50fd`) kennt die acht `test_gui_*.py` in Beschreibungstabelle und `LANGSAM`. Kontrolle im Projekt: `--kompakt` 1248 bestanden, 0 fehlgeschlagen, 189 übersprungen; `--schnell` 656 bestanden (alle GUI-Dateien ausgelassen). (Skill `desktop-pruefung`: Zeilenangaben entfernt und Modulnamen angepasst, siehe unten.)

## 11.11.2026: Dokumentation umgebaut (Marco: Vorschläge zur Dokumentationsmenge umsetzen, Arbeitsstand, nichts committet)

- **`Fortschritt.md` nach Monaten geteilt:** September und Oktober 2026 stehen unverändert in `historie/2026-09.md` und `historie/2026-10.md` (Zeilenabgleich: keine Zeile verloren); `Fortschritt.md` enthält nur noch den laufenden Monat (ab 01.11.2026). `historie/README.md` ist die Übersicht. Regel in `CLAUDE.md`: Historie nicht komplett lesen, sondern mit `git grep` durchsuchen; am Monatsende den Monat nach `historie/` verschieben.
- **Berichte** (Sicherheit, UX-Test 2026-10/11, Desktop-Prüfung, QS, Verbesserungen, Offene-Punkte, Abdeckung) liegen jetzt in `berichte/` (per `git mv`, Pfade in den Dokumenten angepasst, relative Links zwischen den Berichten funktionieren weiter).
- **Entscheidungen als Einzeldokumente:** `entscheidungen/` mit `VORLAGE.md`, `README.md` und 50 Dokumenten (B* und C* der `OFFEN.md`), erzeugt aus den Tabellenzeilen (Text unverändert). In `OFFEN.md` ist die Nummer ein Link; die Fundstellen nennen statt Zeilennummern (`F:6474`) Datei und Abschnittstitel. Die Zuordnung der alten Zeilen zu Abschnitten ist nachträglich gemacht; weil die alten Zeilenangaben „ungefähr“ waren, kann ein Abschnitt knapp danebenliegen. Der ausführliche Grund steht weiter in der Historie und wird bei der nächsten Berührung des Punktes in den Abschnitt „Grund“ des Dokuments nachgetragen.
- **`Architektur.md`, Abschnitt 2:** Modultabelle auf einen Satz je Modul gekürzt (rund 33 KB → 20 KB insgesamt); die ausführlichen Zeilen sind unverändert in `Modulreferenz.md`.
- **Zeilenverweise ersetzt:** `OFFEN.md` und der Skill `desktop-pruefung` verweisen nicht mehr auf Zeilennummern. Im Skill `shs-build` steht, dass im Quellcode-Spiegel nach den Verschiebungen Altdateien liegen, die nur mit Marcos Ja gelöscht werden.
- **Klassenzerlegung, Schritte 1 bis 3 (Plan mit Marco abgestimmt, Arbeitsstand):** `desktop_ergebnis_zellen.py` (Zellen, Delegates, Tabelle, aus `desktop_ergebnis.py`), `desktop_import_meldungen.py` (Import-Meldehilfen, aus `desktop_teilnehmer.py`), `desktop_demo_panel.py` (`DemoPanel`, `DemoMarkierung`, `DemoSchritt`) und `desktop_demo_schritte.py` (Schrittliste und Aktionen als Mixin von `DemoTour`, aus `desktop_demo.py`). Code unverändert verschoben; Syntaxbaum-Vergleich: keine Funktion verloren oder geändert, einzige Abweichung ein Import in `DemoPanel.__init__` (sonst Importkreis). Größen: `desktop_ergebnis.py` 1975 → 1471, `desktop_teilnehmer.py` 1228 → 1012, `desktop_demo.py` 1700 → 684 Zeilen. Test Suite weiter 1244 bestanden, 0 fehlgeschlagen. Beobachtung: `test_entf_in_teilnehmerliste_loescht_nach_rueckfrage` schlägt einzeln ausgeführt fehl (auch im unveränderten Stand vom HEAD), im Gesamtlauf besteht er; abhängig von Fensterfokus und Reihenfolge, nicht vom Umbau. Schritt 7 siehe unten (Schritte 5 und 6 ebenfalls).
- **Klassenzerlegung, Schritt 4 (Arbeitsstand):** Lange Methoden in Bauschritte zerlegt, Code und Reihenfolge unverändert. `TeilnehmerTab.__init__` (229 Zeilen) → `_tabelle_aufbauen`, `_filter_aufbauen`, `_knoepfe_aufbauen`, `_rueckgaengig_aufbauen`, `_layout_aufbauen`; `TeilnehmerTab.aktualisieren` (143) → `_zeile_fuellen`, `_anmerkungen_item`, `_filter_combo_neu_befuellen`. `ErgebnisTab.__init__` (186) → fünf Bauschritte; `_zeilen_fuellen` (103) → `_zeile_fuellen`, `_punktezellen_fuellen`, `_statuszellen_fuellen`; `_spaltenbreiten_anpassen` (123) → `_tabellenschrift_anpassen`, `_spaltenminima`. `TeilnehmerDialog._felder_erstellen` (107) → drei Feldgruppen, `_layout_aufbauen` (127) → `_gruppe_hundefuehrer`, `_gruppe_hund_pruefung`, `_gruppe_halter_aufbauen`. Lokale Variablen, die von mehreren Bauschritten gebraucht werden, sind Attribute geworden (`_import_btn`, `_liste_btn` in `TeilnehmerTab`). Textvergleich vorher/nachher: nur die erwarteten Unterschiede. Test Suite: 1244 bestanden, 0 fehlgeschlagen. Noch über 80 Zeilen (nicht im Umfang von Schritt 4): `VeranstaltungsDialog.__init__`, `ExportTab.__init__`, `ZeitplanTab.__init__` und `_richter_spalte`, `AuswertungTab._rendern` und `__init__`, `FormularImportTab.__init__`, `VersionDialog.__init__`, `StartDialog.__init__`, `DatensicherungTab._sicherung_wiederherstellen`, `DemoPanel.__init__`, `AbrechnungTab.__init__` sowie `_schritte_aufbauen` (reine Schrittliste).
- **Geprüft:** Alle relativen Links in den Markdown-Dateien (ohne `docs/`) lösen auf; `test_agents_spiegel`, `test_bump_version` und `test_drittlizenzen` grün.
- **Klassenzerlegung, Schritt 5 (Arbeitsstand):** (a) `desktop_rueckgaengig.py` mit `RueckgaengigSpeicher`: der Zustand der einen Rückgängig-Ebene und der Knopf sind aus `TeilnehmerTab` herausgelöst, Ausführen und Meldungen bleiben dort. (b) `desktop_ergebnis_speichern.py`: Speichern der Ergebniserfassung als Mixin von `ErgebnisTab` (Methoden unverändert, Syntaxbaum-Vergleich ohne Abweichung); als Mixin statt als eigene Klasse, weil die Methoden rund 15 Zustände des Reiters brauchen und eine Hilfsklasse dieselbe Kopplung nur über `tab.…` ausgedrückt hätte. `desktop_ergebnis.py` 1471 → 1289 Zeilen. Rund 20 Patch-Ziele in den Tests umgestellt. (c) Countdown der `DemoTour` bewusst NICHT ausgelagert: er hängt an acht Zustandsvariablen der Tour (`_index`, `_offen`, `_angehalten`, `_modal_wartet`, `_rest`, Panel), über 30 Teststellen und `tools/screenshots.py` greifen auf `tour._countdown`, `_countdown_tick` und `_wartezeit` zu; Nutzen (60 Zeilen) steht in keinem Verhältnis. Test Suite: 1244 bestanden, 0 fehlgeschlagen. Dazu ein Test für `RueckgaengigSpeicher` (`test_gui_teilnehmer.py`) und der Eintrag im Klassendiagramm der `UML.md`; Verifikations-Subagent ohne Befund.
- **Klassenzerlegung, Schritt 6 (Arbeitsstand): `db.py` als Fassade über sieben Schichtmodule.** `db_verbindung` (Schicht 0, 665 Zeilen), `db_stamm` (1, 639), `db_ergebnisse`, `db_zeitplan`, `db_termine` (2: 609, 696, 466), `db_web` (3, 508), `db_sync` (4, 330); `db.py` hat noch 292 Zeilen und reicht alle Namen weiter (vorher 3953). Entscheidung Marco: Fassade statt Paket. Die Analyse fand vier Kreise zwischen den alten Abschnitten; sie lösten sich durch Zusammenlegen (Veranstaltung/Teilnehmer/Startnummern; Zeitplan/Überschneidungen) und das Verschieben von `dk_mindestabstand` (mit `STANDARD_MINDESTABSTAND`) nach `db_stamm` und `sortierschluessel_text` nach `db_verbindung`. Alle 215 Definitionen sind per Syntaxbaum-Vergleich unverändert; `dir(db)` ist vor und nach dem Umbau gleich (auch die stdlib-Namen). Neue Datei `test_db_fassade.py` (jeder Name der Schichtmodule steht in `db`, kein Name doppelt, Schichten verweisen nur nach unten). **Folge für Tests:** `patch("db.NAME")` erreicht Aufrufe innerhalb der Datenschicht nicht mehr; 30 Stellen (`test_db.py` 23, `test_app_web.py` 7) nutzen jetzt `db_testhilfen.patch_db`, drei `monkeypatch`-Stellen in `test_gui_termin.py` zeigen auf `db_termine`. **`Containerfile`:** `COPY` nennt die sieben neuen Dateien ausdrücklich (nicht `db_*.py`, damit `db_import.py`/`db_sicherung.py` nicht ins Web-Image kommen); der Web-Import wurde mit genau diesen Dateien geprüft, ein echter Image-Bau steht noch aus (CI beim Release). **Prüfung:** Test Suite 1248 bestanden, 0 fehlgeschlagen; zusätzlich alle Datenbank-, Web- und Sicherungstests gegen einen Wegwerf-PostgreSQL-16-Container (Podman, Port 55432, danach gestoppt): 614 Tests ohne Auslassung grün.
- **Klassenzerlegung, Schritt 7: frühere Entscheidungen durchgesehen (Marco: alle Empfehlungen umsetzen, Arbeitsstand).** (1) Alle Web-Entscheidungen (B7, B16, C1 bis C7, C36) tragen „Wann neu bewerten: vor dem nächsten Einsatz der Web-Version“. (2) B13 hat die Wiedervorlage Juni 2027. (3) B10 aufgeteilt in erledigt, offen Desktop (Generalprobe, Barrierefreiheit) und offen Web. (4) B14 erledigt: Die Marke `langsam` steht an den zwei Tests, die über 10 Sekunden brauchen (`test_ergebnistabelle_sehr_gross_nur_maximiert_voll`, `test_screenshot_skript_erzeugt_alle_bilder`; alle anderen GUI-Tests unter 8 s). (5) 15 Einzeldokumente für Kleinigkeiten (C12, C13, C16 bis C20, C22 bis C25, C32, C33, C39, C40) zu `entscheidungen/K01-bekannte-kleinigkeiten.md` zusammengelegt; die Nummern bleiben in `OFFEN.md`. (6) Der Fokus-Test `test_entf_in_teilnehmerliste_loescht_nach_rueckfrage` ist behoben (kein B17 nötig): einzeln ausgeführt griff das Entf-Kürzel erst, nachdem Qt die Ereignisse zum Anzeigen und Fokussieren abgearbeitet hatte; der Test wartet jetzt 200 ms vor dem Tastendruck, mehrfach einzeln und im Dateilauf grün. Die drei breiten Fehlerfänger ohne Begründung (`desktop_programm.py` Ereignisfilter, `db_import.py` PDF-Annotation, `desktop_demo.py` Aufräumen) tragen jetzt einen Grund im Kommentar; von 53 breiten Handlern verschlucken zehn den Fehler, alle mit Begründung.
- **Quellcode-Spiegel und Demo-Version aktualisiert (Marco: ja):** Spiegel `SHS-Pruefungsprogramm-Quellcode` auf den Stand von `main` gebracht (69 Dateien neu, 19 aktualisiert, Byte-Abgleich ohne Abweichung), 65 verschobene Altdateien gelöscht (vorher als identisch mit `berichte/` bzw. ersetzt belegt), `berichte/` ergänzt, `__pycache__`, `gui_vorschau.html` und `docs/bilder/handbuch_edge_download.png` entfernt; `.env`, `secrets/` und die Workflows in der Wurzel blieben. Demo-Version (`SHS-Demo-vor-Build`, außerhalb des Repos): `demo_erzeugen.py` lief mit der Fassade ohne Fehler und hat beide Demo-Termine neu erzeugt (Rauchtest: Hauptfenster lädt den Demo-Termin, alle 10 Reiter ohne Fehler); `Checkliste.md` auf Stand 11.11.2026 mit neuem Abschnitt G (Regressionstest der umgebauten Bereiche), die bisherige Liste liegt als `Checkliste_2026-11-10.md` daneben. Offen: Marco klickt die Liste durch; kein Build, kein Versionsbump.
- **Push, Dialog-Aufteilung und restliche lange Methoden (Marco: erst pushen, dann 2 und 4; Arbeitsstand):** Die fünf Commits sind nach `origin/main` gepusht; die CI (Tests unter Linux und Windows mit PostgreSQL, Container-Bau mit den neuen `db_*.py`) war grün. **Punkt 2:** `desktop_dialoge.py` (2515 Zeilen) ist eine Fassade über `desktop_dialoge_basis` (82 Zeilen), `desktop_dialoge_teilnehmer` (934), `desktop_dialoge_termin` (779), `desktop_dialoge_planung` (411) und `desktop_hilfe` (426); 28 Definitionen per Syntaxbaum unverändert, 14 Patch-Ziele in den Tests umgestellt, `DESKTOP_MODULE` kennt die neuen Module. **Punkt 4:** Alle Methoden über 80 Zeilen zerlegt außer `_schritte_aufbauen` (reine Schrittliste): `VeranstaltungsDialog.__init__`, `ZeitplanTab.__init__` und `_richter_spalte`, `AuswertungTab.__init__` und `_rendern`, `FormularImportTab.__init__`, `VersionDialog.__init__`, `StartDialog.__init__`, `DatensicherungTab._sicherung_wiederherstellen`, `DemoPanel.__init__`, `AbrechnungTab.__init__`; `ExportTab.__init__` ist dabei datengetrieben (Tabelle `_AUSDRUCK_KNOEPFE` mit Beschriftung, Methode, Kurztext und Tooltip je Knopf) statt 160 Zeilen Einzelaufbau. Test Suite: 1248 bestanden, 0 fehlgeschlagen.
- **Barrierefreiheit umgesetzt (Marco 11.11.2026, Arbeitsstand; B9 und B11 bleiben zurückgestellt):** Neuer Test `test_gui_barrierefreiheit.py` (7 Tests): Jedes bedienbare Element der zehn Reiter und von sechs Dialogen hat einen Namen für Bildschirmleser (Text, `accessibleName` oder zugeordnetes Beschriftungsfeld) und ist mit der Tastatur erreichbar; Tab-Durchlauf (`focusNextChild`) erreicht alle sichtbaren Bedienelemente der Reiter und der Dialoge Teilnehmer, Veranstaltung, Version und Hilfe (Negativkontrolle: ein nicht fokussierbares Element wird als unerreichbar gemeldet). Die erste Messung fand rund 90 Elemente ohne Namen; behoben in `TeilnehmerTab`, `ErgebnisTab`, `AuswertungTab`, `TeilnehmerUebersichtTab`, `AbrechnungTab`, `ZeitplanTab` (auch die beiden Symbolknöpfe „Spalte nach links/rechts verschieben“ und die Blockliste je Richter), `FormularImportTab`, `HilfeDialog`, `StartDialog`, `TeilnehmerDialog` (Startnummer, Gegenstände und Zuordnungen) und `VeranstaltungsDialog` (Speicherort, Standardgröße, Anzahl/von/bis je Prüfung). Hilfsfunktion `desktop_gemeinsam.zugaengliche_namen_setzen`. Handbuch: Abschnitt „Bedienung ohne Maus und mit Bildschirmleser“. **Nicht geprüft:** Klang und Bedienbarkeit mit einem echten Bildschirmleser (NVDA, Narrator), Farbe als einziger Hinweis in einzelnen Anzeigen (die Ergebniserfassung hat zusätzlich eine Status-Spalte), weitere Dialoge (Termin-Import, Verteilen, Bewertungsbogen-Auswahl, Sicherung). Test Suite: 1255 bestanden, 0 fehlgeschlagen.
- **Barrierefreiheit, Nachbesserung nach der Verifikation:** Docstring von `TeilnehmerDialog._layout_aufbauen` wieder an erster Stelle; die Abbruch-Auswahl in der Ergebnistabelle (`_AbbruchAuswahl`) hat jetzt den Namen „Abbruchgrund“; Handbuchsatz auf das Belegte eingeschränkt (Rechtsklick-Menüs in den Listen und Ziehen im Zeitplan haben Knopf-Entsprechungen). **Bekannte Lücken des Tests:** er prüft keine Zellen-Editoren der Ergebnistabelle (Punktefelder, Häkchen „Disqualifiziert“), keine Menüs, keine Reiterleiste, den Quittungsknopf je Zeile der Abrechnung (gleicher Text in jeder Zeile), die Reihenfolge der Tab-Taste (nur Tastaturfallen) und die selten genutzten Dialoge (Prüfungsblock, Verteilen, Bewertungsbogen-Auswahl, Etiketten, Sicherung, Import).
- **Löschen und Beenden (Marco 12.11.2026, Arbeitsstand):** (1) Rückfrage beim Beenden, aber nur solange nach einem Löschen von Teilnehmern „Rückgängig“ noch offen ist („Du hast Teilnehmer gelöscht. Nach dem Beenden lässt sich das nicht mehr rückgängig machen“, Vorgabe „Nein“); ohne Löschen keine Frage, beim Beenden durch Windows/Setup ebenfalls nicht (`HauptFenster._beenden_vorbereiten`, `TeilnehmerTab.loeschung_noch_rueckgaengig`). Eine andere gemerkte Aktion oder „Rückgängig“ hebt den Vermerk auf. (2) Sicherung vor dem Löschen nur per Schalter: neues Menü „Einstellungen“ mit „Vor dem Löschen von Teilnehmern eine Sicherung anlegen“ (Standard aus, gespeichert per QSettings); an stellt vor jedem Löschen eine Kopie in `Auto-Sicherung` an (über `auto_sicherung_anlegen`, also nur im echten Programmlauf, nicht in Demo und Tests; es bleiben wie bisher die letzten 10 je Termin). Drei neue Tests in `test_gui_termin.py`; Handbuch (Teilnehmer-Reiter), `UML.md` und `Architektur.md` ergänzt; die Klick-Checkliste in `SHS-Demo-vor-Build` (außerhalb des Repos) hat dafür den neuen Abschnitt I. Hinweis: Mit dem Schalter an verdrängen viele Löschvorgänge die älteren der 10 Kopien je Termin (auch die vom Beenden); schlägt die Kopie fehl, wird still protokolliert und trotzdem gelöscht (die Sicherung ist keine Garantie). Test für den Pfad Windows/Setup über `_sitzungsende_pruefen` und für den Terminwechsel fehlt. Begründung: Wissende sollen nicht bei jedem Löschen gebremst werden.
- **Gelöschte Teilnehmer aus der Sicherung zurückholen (Marco 12.11.2026, Arbeitsstand):** Marco fand nach „Haken rein, Teilnehmer gelöscht, Programm beendet, Neustart“ keinen Weg zurück: die Kopien in `Auto-Sicherung` wurden angelegt, aber nirgends gelesen. Neu: Knopf „Aus Sicherung holen…“ im Reiter Teilnehmer (neben „Rückgängig“), Dialog `SicherungTeilnehmerDialog` (`desktop_dialoge_termin.py`) listet die Kopien des Termins (neueste zuerst, `db_sicherung.auto_sicherungen_zu_termin`) und je Kopie die Teilnehmer, die im Termin fehlen (`db_stamm.fehlende_teilnehmer`, Vergleich über die ID, die wegen AUTOINCREMENT nie neu vergeben wird). Anfangs ist nichts angekreuzt. Zurückgeholt wird mit den vorhandenen Funktionen `teilnehmer_sichern`/`teilnehmer_wiederherstellen` (Ergebnis, gleiche ID; ist die Startnummer inzwischen vergeben, bleibt sie leer). Die Kopie wird nur lesend geöffnet und geprüft (`termin_lesend_pruefen`, wie beim Termin-Import). Zwei Tests in `test_gui_teilnehmer.py`; Handbuch, Hilfe, `Architektur.md`, `Modulreferenz.md`, `UML.md` ergänzt. Grenze: Es geht nur, wenn vor dem Löschen eine Kopie entstanden ist (beim Öffnen/Beenden, Mindestabstand 10 Minuten, oder vor dem Löschen bei eingeschaltetem Schalter).
- **Aus Sicherung holen, Nachbesserung nach der Verifikation:** (1) Fehler behoben: Klammern im Terminnamen (`[` `]`) wurden im Dateimuster der Kopien als Platzhalter gelesen, der Dialog fand dann keine Kopie, und die Begrenzung auf 10 Kopien griff bei solchen Terminen nicht; jetzt `glob.escape` in `auto_sicherung_erstellen` und `auto_sicherungen_zu_termin`. (2) Der Knopf ist bei PostgreSQL gesperrt (dort gibt es keine Kopien). (3) Drei Tests: Klammern, Umlaute, fremde Dateien und Fantasiedatum im Ordner; beschädigte Kopie (Hinweis, Verbindung zu); Knopf bei PostgreSQL. Test Suite 1263 bestanden, 0 fehlgeschlagen. **Bewusst offen:** `SicherungTeilnehmerDialog` steht nicht in `test_gui_barrierefreiheit.py` (Teil der bekannten Lücke „weitere Dialoge“, Hinweiszeilen sind für Tastatur nicht anwählbar); Layout der Statuszeile mit drei Knöpfen bei „Sehr groß“ nicht gemessen; eine Absicherung gegen eine offen gebliebene Kopien-Verbindung, falls der Dialog anderswo ohne `schliesse_quelle` genutzt würde; `fehlende_teilnehmer` hat keinen eigenen Test in `test_db.py` (nur über die Oberfläche).
- **Einstellung „Dateien ohne Nachfrage im Ablageort speichern“ auch im Menü (Marco 12.11.2026, Option B):** Der Eintrag steht jetzt zusätzlich im Menü „Einstellungen“ (neben „Vor dem Löschen … Sicherung“) und bleibt im Reiter „Ausdrucke/Export“. Beide sind dieselbe gespeicherte Einstellung und gleichen sich in beide Richtungen ab (`HauptFenster._ohne_nachfrage_aus_menue`, `_ohne_nachfrage_vom_reiter`), auch nach einem Terminwechsel (neue Reiter). Ein Test in `test_gui_termin.py`; Handbuch und Demo-Checkliste ergänzt.
- **Menü „Einstellungen“ in Hilfe und Handbuch (Marco 12.11.2026):** Eigener Abschnitt „Einstellungen (Menü „Einstellungen“)“ in der eingebauten Hilfe (`desktop_hilfe.py`, nach „Aussehen“) und im Handbuch (Kapitel 13, vor „Bedienung ohne Maus“): die zwei Schalter mit Standard und Wirkung, Verweis auf „Aus Sicherung holen…“ und auf die Rückfrage beim Beenden nach einem Löschen.
- **„Aus Sicherung holen…“: sinnvolle Vorauswahl und erkennbare Klappliste (Marco 12.11.2026):** Nach Löschen und Neustart war die neueste Kopie (entsteht beim Beenden) schon ohne den Gelöschten, die passende Kopie lag eine weiter unten und die Klappliste war nicht als solche erkennbar. Jetzt zählt der Dialog je Kopie vorab, wer im Termin fehlt, schreibt es in die Liste („– 1 Teilnehmer fehlt“, „– niemand fehlt“, „– nicht lesbar“) und wählt die neueste Kopie mit Fehlenden vor. Der Text über der Liste nennt das Aufklappen mit dem Pfeil. Neuer Test `test_sicherung_dialog_waehlt_juengste_kopie_mit_fehlenden_vor`. Offen: ob die Kopie beim Beenden nach einem Löschen überhaupt die vorherige Kopie überschreiben/verdrängen darf (Rotation 10); Screenshot des Dialogs für das Handbuch gibt es noch nicht.
