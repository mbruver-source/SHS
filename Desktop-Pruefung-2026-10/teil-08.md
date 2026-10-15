# Desktop-Prüfung Teil 8: Hauptfenster, Lebenszyklus, Version und Update

- **Datum:** 14.10.2026
- **Commit:** 0aa00df
- **Code:** `app.py` Kopf Z. 1–234, `HauptFenster` (Reiteraufbau, Menüs, Tabwechsel, `closeEvent`),
  `SitzungsendeFilter`, `laufkennung_setzen`, `sitzungsende_einrichten`, `_version_tupel`,
  `_neueste_version_pruefen`, `VersionDialog`, `main()`; `selbsttest.py`
- **Tests:** `test_app_gui.py` (Schließen, Sitzungsende, Mutex, Selbsttest): 37 passed, 1 skipped
  (Filter-Test braucht echtes Windows)
- **Ablauf:** Prüfer (`desktop-pruefer`), danach Gegenprüfung durch einen zweiten `desktop-pruefer`

**Ergebnis:** 10 bestätigte Befunde: 0 hoch, 0 mittel, 2 niedrig, 8 optional. Kein Sicherheitsbefund.

---

## Niedrig

### Nr. 1 Update-Prüfung: unbehandelte Ausnahmen, Knopf bleibt gesperrt auf „Wird geprüft…“

- **Stelle:** `app.py:3666–3681` (`_neueste_version_pruefen`), `3783–3793` (`_updates_pruefen`).
- **Kategorie:** Fehlerbehandlung.
- **Ablauf:**
  - `http.client.IncompleteRead`, `BadStatusLine` und `LineTooLong` sind `HTTPException`, kein
    `OSError`. `urllib` verpackt nur Fehler aus `h.request` in `URLError`; `getresponse()` und
    `read()` reichen sie roh durch, z. B. wenn das WLAN mitten in der Antwort abreißt. Sie fallen
    durch `except (URLError, OSError)`.
  - Eine JSON-Antwort, die kein Objekt ist (`[]`, `null`, `"x"`, `1`), wirft an `daten.get`
    (Z. 3678, außerhalb des `try`) einen `AttributeError`.
  - Das `KeyError` in `except (ValueError, KeyError)` ist tot.
- **Nachgestellt:** `urlopen` gepatcht. Danach `_updates_btn.isEnabled() == False`, Text
  „Wird geprüft…“, Ergebniszeile unsichtbar, dazu „Unerwarteter Fehler“. Beim zweiten gleichen
  Fehler zeigt `fehlerfenster_einrichten` wegen der Duplikatsperre gar nichts mehr. Erst ein neu
  geöffneter Dialog funktioniert wieder; Daten gehen nicht verloren. Der Docstring verspricht
  „in jedem Fall eine verständliche Rückmeldung“.
- **Vorschlag:** `except (URLError, OSError, http.client.HTTPException)`; `if not isinstance(daten,
  dict)` → „Antwort nicht lesbar“; Knopf in `_updates_pruefen` per `try/finally` zurücksetzen;
  `KeyError` streichen; Tests (Nr. 9).
- **Gegenprüfung:** bestätigt, niedrig.

### Nr. 2 Rückfrage beim Terminwechsel: Text und Esc verschleiern, dass „Nein“ verwirft

- **Stelle:** `app.py:4200–4230` (`_ungespeicherte_ergebnisse_klaeren`, Aufruf 4182) gegenüber
  `4232–4253` (`_tab_gewechselt`).
- **Kategorie:** Datenintegrität, Bedienung.
- **Ablauf:**
  - Beide Stellen zeigen denselben Titel und Text („… noch nicht gespeicherte Änderungen. Jetzt
    speichern?“, Ja/Nein).
  - Beim Reiterwechsel bleiben die Eingaben bei „Nein“ erhalten, beim Terminwechsel baut
    `_termin_setzen` die Reiter neu auf und verwirft sie.
  - Esc und Fenster-X werden zu „Nein“ (kein Abbrechen-Knopf).
- **Nachgestellt:** 55/35 eingetragen, „Anderen Termin öffnen…“, Esc, Termin B gewählt: Titel auf
  B, Punkte in `a.sqlite` `None`, ohne Meldung.
- **Einschränkung (Gegenprüfung):** Nach Esc öffnet sich erst der Startdialog; wer ihn abbricht,
  behält alles. Verloren ist es erst, wenn bewusst ein anderer Termin gewählt wird. Plausible
  Fehlbedienung bleibt: Wer vom Reiterwechsel gelernt hat, dass „Nein“ nichts verwirft, schaut
  „kurz in einen anderen Termin“.
- **Abgrenzung:** Dass „Nein“ verwirft, ist entschieden (Fortschritt.md:48, 4690f.) und wird nicht
  neu gemeldet. Neu sind der fehlende Hinweis und die fehlende Abbrechen-Möglichkeit.
- **Vorschlag:** `Save | Discard | Cancel` mit Vorgabe Save (Esc = Cancel), alternativ Text
  „Nein = Änderungen verwerfen“ plus Abbrechen. Rückfrage aus `_tab_gewechselt` und
  `_ungespeicherte_ergebnisse_klaeren` in eine Hilfsfunktion legen. GUI-Test: Esc, danach Termin
  unverändert offen.
- **Zusammen umsetzen mit:** Teil 10 Nr. 8 (zweite Frage beim Demo-Start, `desktop_demo.py:948`).
- **Gegenprüfung:** bestätigt, niedrig.

## Optional

### Nr. 3 (vormals 3b) Fenstertitel „None ()“ bei fremder Termin-Datei

- **Stelle:** `app.py:4125–4132`.
- Bei `verein`/`datum` NULL (nur in fremden Dateien mit eigener Tabellendefinition; Schema hat
  `NOT NULL`, `db.py:57/59`) lautet der Titel „SHS Prüfungsprogramm – None ()“ bzw.
  „None (TT.MM.JJJJ)“. Aus Teil 7 übergeben.
- **Vorschlag:** `veranstaltung['verein'] or dateiname`, Datum nur wenn vorhanden. Zusammen mit
  Teil 7 Nr. 4 (Plausibilitätsprüfung beim Öffnen) und Teil 2 Nr. 5 (Titel nach Bearbeiten,
  `_titel_aktualisieren()`).

### Nr. 4 Versionsvergleich: nicht lesbare Versionen ergeben „Du hast bereits die neueste Version.“

- **Stelle:** `app.py:3800–3806`.
- Mit `VERSION = "dev"` oder Tags wie `v1.1`, `v2.0.0-rc1` liefert `_version_tupel` `None`, gemeldet
  wird „neueste Version“. Praktisch kaum erreichbar (`version.py` im Bundle, `bump_version.py`
  erzeugt immer vX.Y.Z, `releases/latest` ohne Pre-Releases), die Aussage ist dann aber falsch.
- **Vorschlag:** „neueste“-Zweig nur bei `neueste <= aktuell`, sonst neutral „Neueste veröffentlichte
  Version: X (installiert: Y)“ mit Download-Knopf.

### Nr. 5 Update-Prüfung: Zeitgrenze und SSL-Fehlermeldung

- **Stelle:** `app.py:3667` (`timeout=5`), Kommentar `3777–3782`, Meldung `3673–3674`.
- `timeout` gilt je Socket-Operation; DNS (`getaddrinfo`) hat keine Grenze, `create_connection`
  versucht jede Adresse mit 5 s. Der GUI-Thread kann länger stehen („Keine Rückmeldung“).
- `ssl.SSLCertVerificationError` erscheint als „kein Internetzugang?“.
- **Offen, am echten Gerät zu prüfen:** Mac-/Linux-Bundles ohne `certifi`. Auf Macs mit
  python.org-artigem OpenSSL-Pfad könnte die Update-Prüfung grundsätzlich scheitern (mit falscher
  Meldung). Beim Mac-Rückmeldungstest gezielt prüfen; bestätigt es sich, wäre es niedrig.
- **Vorschlag:** Abfrage in `QThread`/`QNetworkAccessManager` mit Gesamtzeitgrenze; SSL-Fehler eigens
  melden; optional Selbsttest-Schritt `ssl.create_default_context().cert_store_stats()["x509_ca"] > 0`.

### Nr. 6 Zweiter Programmstart wird nicht erkannt

- **Stelle:** `app.py:3852–3877` (`laufkennung_setzen`): `ERROR_ALREADY_EXISTS` wird nicht
  ausgewertet; unter macOS/Linux keine Kennung.
- Zwei Instanzen können denselben Termin öffnen. Unter Windows scheitern Löschen/Wiederherstellen
  des in der anderen Instanz offenen Termins sicher (WinError 32). Unter Linux gelingt das Löschen,
  Instanz 1 schreibt in die gelöschte Datei. macOS: Doppelklick auf die .app startet keine zweite
  Instanz. Realistisch bleiben Doppelstart unter Windows/Linux und paralleles Erfassen im selben
  Termin (veraltete Ansichten). Nur am Code belegt.
- **Vorschlag:** `ctypes.get_last_error() == 183` auswerten, vor dem Startdialog fragen „Programm
  läuft bereits – trotzdem starten?“; plattformübergreifend `QLockFile`. Rückfrage, keine Sperre.

### Nr. 7 Selbsttest ohne Zeitgrenze; Windows-Build-Job ohne `timeout-minutes`

- **Stelle:** `selbsttest.py:44–71`; `.github/workflows/build-installer.yml` Job `build` (Z. 44–45),
  Mac/Linux haben 45 min.
- Öffnet ein `aktualisieren()` beim Durchschalten der Reiter eine modale Box, wartet der Test
  offscreen endlos; der Job läuft bis 360 min, ohne Stapel im Protokoll.
- **Vorschlag:** `faulthandler.dump_traceback_later(300, exit=True, file=...)` und im `finally`
  `cancel_dump_traceback_later()`; `timeout-minutes` für den Windows-Job.

### Nr. 8 Veraltete Kommentare

- `app.py:2–9`: Modul-Docstring „Prototyp“, „konnte hier aber nicht selbst gestartet werden“.
- `app.py:3907–3911`: „hier ungenutzte, leere QMenuBar“ – trägt seit `_theme_menue_aufbauen` das
  Menü „Ansicht“.
- `app.py:3777–3782`: „auf wenige Sekunden begrenzt“ (Nr. 5).
- `app.py:4047–4050`: `closeEvent`-Docstring sagt, die übrigen Ja/Nein-Rückfragen seien mit
  „Speichern“ vorbelegt; die zweite Frage in `_ungespeicherte_ergebnisse_klaeren` (4226) ist aber
  ebenfalls mit „Nein“ vorbelegt.
- (Die doppelte Rückfrage 4204–4212/4237–4245 gehört zu Nr. 2.)

### Nr. 9 Testlücken Update-Prüfung

- `_neueste_version_pruefen` ist in allen vier Tests weggepatcht (`test_app_gui.py:1665/1687/1706/1727`).
  Es fehlen Tests mit gepatchtem `urlopen`: HTTP 404/403, `URLError`, ungültiges JSON, JSON-Liste,
  fehlendes `tag_name`, `IncompleteRead`.
- `_version_tupel` ohne eigene Tests („v1.0.47“, „1.1“, „2.0.0-rc1“, „dev“); `_updates_pruefen` bei
  unlesbarer Version und bei Ausnahme (Knopf wieder frei).
- Titel- und Esc-Tests gehören zu Teil 2 Nr. 5 bzw. Nr. 2.

### Nr. 10 Linux/X11: abgebrochenes Abmelden lässt die Schließfreigabe stehen (aus Hinweis des Prüfers)

- **Stelle:** `sitzungsende_einrichten` (`app.py:3886`, `SitzungsendeFilter` nur unter Windows),
  `closeEvent` 4057–4061, `_beenden_vorbereiten` 4074–4078.
- Laut Qt-Doku kann der Session-Manager nach `commitDataRequest` beenden „or may not“ (unter XSMP
  auch beim Speichern eines Sitzungsstands oder wenn ein anderes Programm das Abmelden abbricht).
  Danach bleibt `_beenden_freigegeben = True`: Neue Eingaben gehen beim nächsten Fenster-X ohne
  Auto-Speichern verloren; eine laufende Demo wird dabei schon beendet.
- Nur Vorschau-Plattformen unter X11 (nicht Wayland, macOS über `closeEvent` nicht betroffen). Nur
  am Code und an der Qt-Doku belegt. Fortschritt.md:5224 nennt nur die `win32`-Absicherung.
- **Vorschlag:** In `closeEvent` auch bei Freigabe `hat_ungespeicherte_aenderungen()` prüfen und dann
  still `alle_speichern()` aufrufen; plattformneutral, unter Windows harmlos.

---

## Verworfen

- **Titel bleibt nach „Veranstaltungsdaten bearbeiten…“ veraltet (vormals 3a):** Doppelung zu
  Teil 2 Nr. 5.
- **„[*]“ im Vereinsnamen wird von Qt verschluckt (vormals 3c):** praktisch ausgeschlossen, ohne Folge.

## Hinweise, nicht gezählt

- **`closeEvent` nicht ausfallsicher** (`event.ignore()` zuerst, `accept()` nur bei Erfolg): Ergänzung
  zu Teil 3 Nr. 1; eine Ausnahme aus `tour.beenden()` trifft nur Demo-Daten.
- **Liegengebliebene Dialoge:** `VersionDialog(self).exec()`/`HilfeDialog(self).exec()`
  (`app.py:4010/4013`) und Boxen aus `meldungsfenster_als_klartext` (`desktop_gemeinsam.py:531`)
  bleiben als Kinder liegen – zur Gruppe „Liegengebliebene Dialoge“.
- **`_tab_gewechselt` während der Demo (aus Teil 10):** kein Befund; die Demo speichert vor jedem
  eigenen Wechsel, gefragt wird nur bei eigenen Eingaben des Anwenders.
- **`_termin_setzen`:** Teil 7 Nr. 4 und Nr. 9 bestätigt, nicht neu gezählt; Titelbildung beim Umbau
  gleich auslagern (Nr. 3, Teil 2 Nr. 5).

## Ohne Befund geprüft

Reihenfolge in `main` (Selbsttest vor `QApplication`/Mutex/Protokoll, Demo-Reste aufräumen, Abbruch im
Startdialog = Exit 0); `laufkennung_setzen` (Prototyp, Namen, Handles, Abgleich mit `installer.iss`);
`SitzungsendeFilter` (Null-Zeiger, fremde Ereignistypen, Lebensdauer); `_sitzungsende_pruefen`
(`release` im `finally`); Freigabe nur für ein `closeEvent`; `QActionGroup` ohne Doppelverbindung;
`currentChanged` beim Neuaufbau blockiert; `tag_name` als Klartext, Download nur feste URL; Selbsttest
(Temp-Ordner, Verbindung im `finally`, `faulthandler` wiederhergestellt, `stdout=None` abgefangen,
Protokollname); `pyflakes` ohne Befund.
