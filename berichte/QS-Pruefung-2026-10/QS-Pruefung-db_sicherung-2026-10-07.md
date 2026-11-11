# QS-Prüfung db_sicherung.py (07.10.2026)

Workflow qs-pruefung (Sicherheit/Korrektheit/Wartbarkeit + Gegenprüfung). Alle bestätigten Befunde sind in 1.0.45 behoben (Nr. 6 wurde verworfen); veröffentlicht nach dem Release (07.10.2026).

## Bestätigt

### 1. Beim Wiederherstellen wird eine vorhandene Termin-Datei ohne Rückfrage überschrieben, wenn sich der Name nur in Groß-/Kleinschreibung unterscheidet (Windows)

- Rolle: Sicherheit, Schweregrad: niedrig
- Stelle: desktop_dialoge.py:1012

Ablauf: app.py:3429 baut `vorhandene = {p.name for p in ordner.glob("*.sqlite")}` aus den Namen, wie sie auf der Platte stehen. Bei der Konfliktprüfung in desktop_dialoge.py:1012 (`if name not in vorhandene`) wird groß-/kleinschreibungsabhängig verglichen. db_sicherung.sicherung_wiederherstellen() (db_sicherung.py:236/244) schreibt danach mit `os.replace(tmp, ordner / ziel)`. Unter Windows (NTFS, Groß-/Kleinschreibung egal), der Hauptplattform der Desktop-App, trifft das dieselbe Datei. Angriffsweg: Ein präpariertes oder fremdes Sicherungs-ZIP enthält etwa den Eintrag `Pruefung_2026.SQLITE` oder `pruefung_2026.sqlite`, während lokal `Pruefung_2026.sqlite` liegt. Der Eintrag besteht `_ist_sicherer_dateiname()` und den `.lower().endswith(".sqlite")`-Filter in sicherung_inhalt() (db_sicherung.py:177). Er gilt als „neuer Termin“, der Konflikt-Dialog mit Überschreiben/Kopie/Überspringen erscheint nicht, und der vorhandene Termin samt Ergebnis- und Personendaten wird ersetzt. Das ist dieselbe Wirkung, die der Docstring in db_sicherung.py:85-88 für den früheren Path-Traversal-Fund beschreibt („Konflikt-Dialog übersprungen ... stiller Überschreibversuch“), jetzt aber innerhalb des Termine-Ordners. Dasselbe passiert ohne Angreifer, wenn eine Sicherung von einem anderen Rechner stammt oder eine Datei im Explorer umbenannt wurde. Folgefehler: `bereits_vergeben` in eindeutigen_dateinamen_finden() (db_sicherung.py:115) vergleicht ebenfalls mit Groß-/Kleinschreibung. Dadurch können zwei ZIP-Einträge, etwa die Kopie `A (2).sqlite` und der neue Eintrag `a (2).sqlite`, auf dieselbe Datei zielen, und einer überschreibt den anderen still. Den gerade geöffneten Termin schützt Windows vermutlich dadurch, dass os.replace() bei offener SQLite-Datei fehlschlägt. Das ist nicht praktisch nachgestellt, sondern nur aus dem Sharing-Modus von SQLite abgeleitet. Voraussetzung ist, dass der Nutzer die ZIP-Datei selbst auswählt; es gibt keinen Fernangriff. Deshalb niedrig. Erwartet: Jeder Name, der unter Windows eine vorhandene Datei trifft, löst den Konflikt-Dialog aus.

**Vorschlag:** Konflikterkennung ohne Unterscheidung von Groß-/Kleinschreibung: in app.py `vorhandene` als Zuordnung `name.casefold() -> echter Name` aufbauen und in _wiederherstellungsziele_planen() mit `name.casefold()` vergleichen. Dabei auch `offener_name` per casefold vergleichen. In eindeutigen_dateinamen_finden() `bereits_vergeben` ebenfalls per casefold prüfen. Zusätzlich kann sicherung_wiederherstellen() als zweite Absicherung (analog zu _ist_sicherer_dateiname) Ziele ablehnen, die nur per casefold doppelt vorkommen. Regressionstest in test_backup.py mit einem ZIP-Eintrag, der sich nur in Groß-/Kleinschreibung von einer vorhandenen Datei unterscheidet.

**Gegenprüfung:** Am Code und in einer Nachstellung unter Windows bestätigt. app.py:3429 vergleicht `vorhandene` mit Groß-/Kleinschreibung, ebenso desktop_dialoge.py:1012. Im Zielordner lag 'Pruefung.sqlite' (Inhalt ALT), im ZIP stand 'pruefung.sqlite'. sicherung_wiederherstellen() hat die Datei ohne Konflikt-Dialog ersetzt: Der Ordner enthält danach nur noch 'pruefung.sqlite' mit Inhalt NEU. Der behauptete Fehler im Kern stimmt also. Einschränkung: Der genannte Folgefehler bei `bereits_vergeben`/eindeutigen_dateinamen_finden() ist schon in Fortschritt.md (Abschnitt G5, Zeile 1436) als bewusst nicht umgesetzter Restpunkt notiert: „kein casefold-Vergleich unter Windows. Praktisch ausgeschlossen, weil die App selbst nie solche ZIPs erzeugt“. Dieser Teil wird deshalb verworfen. Der Hauptpunkt ist eine andere und schwerere Wirkung: Der Konflikt-Dialog fällt bei einer vorhandenen Datei weg, und diese wird ohne Rückfrage überschrieben. Die G5-Begründung deckt ihn aber teilweise ab, denn ohne präpariertes ZIP müsste der Nutzer die Datei vorher nur in der Schreibweise umbenannt haben. Vor der Umsetzung sollte Marco klären, ob er diesen Punkt unter den G5-Restpunkt fasst. Einstufung niedrig ist angemessen.

### 2. Sicherung erstellen schreibt direkt in die Zieldatei: Bei einem Abbruch ist die alte Sicherung weg und es bleibt eine gültig aussehende Teil-Sicherung zurück

- Rolle: Korrektheit, Schweregrad: mittel
- Stelle: db_sicherung.py:146

sicherung_erstellen() öffnet ziel_pfad direkt im Modus "w" (Zeile 147 bzw. 154). Damit wird eine vorhandene Datei sofort geleert. Der with-Block schreibt das Inhaltsverzeichnis des ZIPs auch dann, wenn eine Ausnahme auftritt. Ablauf: Der Dateiname-Vorschlag enthält nur das Tagesdatum (app.py:3368). Eine zweite Sicherung am selben Tag überschreibt deshalb nach der Qt-Rückfrage die erste. Scheitert das Schreiben beim zweiten Termin, etwa weil der USB-Stick voll ist oder eine Termin-Datei gesperrt ist, dann (1) ist die vorherige Sicherung verloren und (2) liegt unter demselben Namen ein ZIP mit Inhaltsverzeichnis, das nur die bis dahin geschriebenen Termine enthält. Nachgestellt mit 2 Termin-Dateien, die vorhandene alt.zip ist 254 Bytes groß, zipfile.ZipFile.write wirft beim 2. Aufruf OSError(28): Danach ist alt.zip 125 Bytes groß und sicherung_inhalt() liefert ohne Fehler ['B.sqlite']. Eine spätere Wiederherstellung aus dieser Datei bringt also still nur einen Teil der Termine zurück. Der Nutzer hat zwar einmal die Meldung „Sicherung fehlgeschlagen“ gesehen, die Datei selbst ist aber nicht als unvollständig erkennbar. Erwartet wird, dass entweder die alte Sicherung unverändert bleibt oder keine Zieldatei existiert, aber nie eine unvollständige, gültig aussehende Sicherung. Für die Wiederherstellung ist dieses Verhalten schon atomar umgesetzt (Fix 2, 19./20.09.), für das Erstellen nicht.

**Vorschlag:** Wie in sicherung_wiederherstellen() vorgehen: das ZIP in eine temporäre Datei im Zielordner schreiben (tempfile.mkstemp(dir=Path(ziel_pfad).parent, suffix='.tmp')). Erst nach erfolgreichem Schließen des ZIPs os.replace(tmp, ziel_pfad) ausführen, bei jeder Ausnahme die temporäre Datei löschen. Dazu einen Test in test_backup.py, analog zu test_abbruch_beim_schreiben_laesst_vorhandene_datei_unveraendert: zipfile.ZipFile.write wirft beim zweiten Aufruf, danach prüfen, dass die vorhandene Ziel-ZIP byte-gleich geblieben ist und keine .tmp-Datei übrig ist.

**Gegenprüfung:** In der Nachstellung bestätigt. sicherung_erstellen() öffnet ziel_pfad direkt mit "w" (Zeilen 147/154), und ZipFile.__exit__ schreibt das Inhaltsverzeichnis auch bei einer Ausnahme. Ablauf: alt.zip mit A und B, 218 Bytes. Danach eine zweite Sicherung auf denselben Pfad, bei der der 2. write()-Aufruf OSError(28) wirft. Ergebnis: alt.zip ist 120 Bytes groß, und sicherung_inhalt() liefert ohne Fehler ['A.sqlite']. Die alte Sicherung ist also weg, und eine unvollständige Sicherung sieht gültig aus. Fortschritt.md enthält dazu weder eine Entscheidung noch ein akzeptiertes Restrisiko; Fix 2 betraf nur das Wiederherstellen. Einstufung mittel ist vertretbar, weil eine Sicherung still unvollständig ist.

### 3. Abbruch beim Wiederherstellen mehrerer Termine: Bereits überschriebene Termine werden nicht gemeldet, die Fehlermeldung klingt nach „nichts passiert“

- Rolle: Korrektheit, Schweregrad: niedrig
- Stelle: db_sicherung.py:228

sicherung_wiederherstellen() schreibt jede Datei einzeln atomar. Bricht die Schleife bei Datei n ab (OSError, z. B. Platte voll, Datei gesperrt, CRC-Fehler eines Eintrags → BadZipFile), dann sind die Dateien 1..n-1 schon endgültig ersetzt. Die Liste `geschrieben` geht mit der Ausnahme verloren. app.py:3443-3448 zeigt nur „Die Sicherung konnte nicht wiederhergestellt werden“. Nachgestellt: Im Zielordner liegen B.sqlite (Inhalt 'ALT-B') und 'Prüfung Köln.sqlite' (Inhalt 'ALT-K'). Beide sollen per „Überschreiben“ wiederhergestellt werden, os.replace scheitert beim 2. Aufruf mit OSError(28). Ergebnis: B.sqlite enthält den Stand aus der Sicherung, 'Prüfung Köln.sqlite' den alten Stand, und die Meldung erwähnt nicht, dass B.sqlite bereits überschrieben ist. Der Nutzer hält den Vorgang für wirkungslos, obwohl ein aktueller Terminstand durch einen älteren Sicherungsstand ersetzt wurde. Erwartet wird, dass die Meldung nennt, welche Termine schon wiederhergestellt bzw. überschrieben wurden. Alternativ alles vorher in temporäre Dateien entpacken und erst danach ersetzen.

**Vorschlag:** Entweder zweiphasig arbeiten: zuerst alle gewählten Einträge in temporäre Dateien im Zielordner entpacken (dabei treten Lese-, CRC- und Plattenplatz-Fehler auf), erst danach alle os.replace() ausführen und bei Fehlern in Phase 1 alle temporären Dateien löschen. Oder die bereits geschriebenen Namen an der Ausnahme mitgeben, z. B. als Attribut einer eigenen Ausnahme, und in app.py:3443 in der Fehlermeldung nennen. Dazu ein Test in test_backup.py: zwei Einträge, os.replace scheitert beim zweiten Aufruf, Erwartung je nach gewähltem Weg.

**Gegenprüfung:** Am Code nachvollzogen. Bei einer Ausnahme in der Schleife (Zeilen 228-249) geht `geschrieben` verloren, weil die Ausnahme ohne Teilergebnis weitergereicht wird. app.py:3443-3448 zeigt dann nur „Die Sicherung konnte nicht wiederhergestellt werden“. Die zuvor bereits per os.replace ersetzten Dateien bleiben ersetzt, und die Meldung nennt sie nicht. Zu Fortschritt.md gibt es keinen Konflikt. Einstufung niedrig passt.

### 4. Doppeltes Öffnen und Passwort-Handling in sicherung_inhalt und sicherung_wiederherstellen

- Rolle: Wartbarkeit, Schweregrad: optional
- Stelle: db_sicherung.py:170

Beide Funktionen öffnen das ZIP mit pyzipper.AESZipFile, setzen das Passwort, rufen _zip_grenzen_pruefen auf und übersetzen RuntimeError mit 'password' in PasswortFalschError. Das ist doppelt (Zeilen 169-189 und 222-253). Die Fehlermeldungen unterscheiden sich zudem leicht (ausführlich bzw. nur 'Das Passwort ist falsch.'). Eine Änderung an der Passwortlogik muss an zwei Stellen erfolgen.

**Vorschlag:** Kleinen Kontextmanager oder Helfer einführen, z. B. _zip_oeffnen(zip_pfad, passwort), der öffnet, Passwort setzt, Grenzen prüft und RuntimeError in PasswortFalschError umwandelt. Beide Funktionen nutzen ihn.

**Gegenprüfung:** Zutreffend. Das Öffnen mit AESZipFile, setpassword, _zip_grenzen_pruefen und die RuntimeError→PasswortFalschError-Übersetzung stehen doppelt in den Zeilen 169-189 und 222-253, mit unterschiedlichen Meldungstexten. Dazu kommt: Nur sicherung_inhalt() übersetzt BadZipFile in ValueError, sicherung_wiederherstellen() nicht. Optionaler Wartbarkeitspunkt.

### 5. Docstring von sicherung_wiederherstellen unvollständig

- Rolle: Wartbarkeit, Schweregrad: optional
- Stelle: db_sicherung.py:199

Der Docstring nennt nicht, dass die Funktion PasswortFalschError (bei falschem Passwort) und ValueError (unsicherer Zielname, überschrittene ZIP-Grenzen) wirft. sicherung_inhalt dokumentiert seine Ausnahmen dagegen. Außerdem ist der Absatz zur atomaren Schreibweise mit Review-Historie ('QS-Review 19./20.09.: vorher direktes write_bytes') überladen, die in Fortschritt.md besser aufgehoben ist.

**Vorschlag:** Abschnitt 'Wirft ...' ergänzen und die Review-Historie im Docstring kürzen. Die Historie bleibt in Fortschritt.md.

**Gegenprüfung:** Nur teilweise bestätigt. Richtig ist: Der Docstring nennt PasswortFalschError und ValueError nicht (unsicherer Zielname in Zeile 234, ZIP-Grenzen), sicherung_inhalt() dagegen schon. Der zweite Teil, die Review-Historie aus dem Docstring zu entfernen, wird verworfen. Herkunftsvermerke wie „QS-Review 19./20.09.“ oder „Codeprüfung 22.09., G5“ sind im ganzen Projekt durchgängig so üblich, siehe z. B. desktop_dialoge.py:1001. Optional.

### 7. Überschrift-Kommentar wiederholt das Moduldocstring

- Rolle: Wartbarkeit, Schweregrad: optional
- Stelle: db_sicherung.py:19

Der Block '--- Datensicherung (Export/Import ...) ---' stammt noch aus der Zeit in db.py. Im eigenständigen Modul wiederholt er den Modul-Docstring (Zeilen 1-5). Nur der pyzipper-Begründungsteil ist darin noch sinnvoll.

**Vorschlag:** Überschriftzeile streichen und den pyzipper-Hinweis in den Modul-Docstring oder direkt an den Import hängen.

**Gegenprüfung:** Zutreffend, aber eine Kleinigkeit. Die Überschrift in Zeile 19 wiederholt den Modul-Docstring (Zeilen 1-5) und stammt sichtlich aus db.py. Inhaltlich trägt nur die pyzipper-Begründung in den Zeilen 21-25 etwas bei. Optional.

## Verworfen

### 6. Sehr langer Docstring mit Review-Geschichte in _ist_sicherer_dateiname

- Rolle: Wartbarkeit, Schweregrad: optional
- Stelle: db_sicherung.py:75

Der Docstring (Zeilen 76-90) besteht überwiegend aus der Entstehungsgeschichte der Lücke (Review 19./20.09., Konfliktdialog übersprungen usw.) statt aus dem Vertrag der Funktion. Das erschwert das Lesen, und die Beschreibung 'wurde ... übernommen' beschreibt einen Zustand, der im aktuellen Code nicht mehr existiert.

**Vorschlag:** Auf 3-4 Zeilen kürzen (was ist 'sicher', wo wird geprüft, warum zweifach). Der Hintergrund steht in Fortschritt.md.

**Gegenprüfung:** Verworfen. Begründung (warum) und Entstehungshistorie mit Review-Kennung stehen im Projekt durchgängig und bewusst in Kommentaren und Docstrings (z. B. S-8, G5, QS-Review 19./20.09.), das ist Hauskonvention und kein Mangel. Der Docstring beschreibt in Zeilen 76-79 und 88-90 den Vertrag korrekt. Die Vergangenheitsform „wurde ... übernommen“ bezieht sich ausdrücklich auf den Zustand „ohne diese Prüfung“ und ist damit nicht irreführend. Soweit es um Review-Historie in Docstrings geht, deckt sich der Punkt zudem mit #5.
