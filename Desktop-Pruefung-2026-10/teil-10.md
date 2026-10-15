# Desktop-Prüfung Teil 10: Demoprüfung

- **Datum:** 14.10.2026
- **Commit:** 17f9176 (Version 1.0.47; Programmcode seit 25f9572 unverändert)
- **Geprüft:** `desktop_demo.py`, `demo_daten.py`; `app.py` `_demo_starten`, `_demo_sperren`,
  `StartDialog._demo_waehlen` (dazu `app.py` 4015–4028, 4179–4190, 4447–4469);
  `test_app_gui.py` ab Z. 4713.
- **Ablauf:**
  - Geplant als Cloud-Probelauf. Die Cloud-Ausführung griff nicht: Der Prüfer lief lokal unter
    Windows in einer temporären Arbeitskopie (automatisch entfernt; GitHub unverändert, per
    `git ls-remote` vor/nach verglichen). Gegenprüfung danach auf Marcos Wunsch lokal.
  - Beide haben offscreen nachgestellt, mit simulierten Bildschirmen 1920×1040, 1366×728 und
    800×800.
  - Tests grün: `pytest test_app_gui.py -k demo` 25 passed, `TestDemoDaten` 5 OK.
- **Ergebnis:** 11 Befunde gemeldet, 10 bestätigt, 1 teilweise (Nr. 10). Kein Schweregrad
  geändert. Kein Sicherheitsbefund.

| Schweregrad | Anzahl | Befunde |
|---|---|---|
| mittel | 1 | 1 |
| niedrig | 6 | 2, 3, 4, 5, 6, 7 |
| optional | 4 | 8, 9, 10, 11 |

**Stand mit Marco:** alle Befunde noch unbesprochen.

## Bestätigte Befunde

### Nr. 1 [mittel] Erklärfenster rutscht in Schritt 13–15 unter den Bildschirmrand

- **Stelle:** `desktop_demo.py:239-255` (`anzeigen`: `adjustSize()`, Position nur beim ersten Mal
  gesetzt), `:283-298` (`ausweichen`/`_in_ecke_setzen`).
- **Kategorie:** Korrektheit, Qt.
- **Ablauf:** `_in_ecke_setzen` setzt die Position mit der aktuellen Höhe, `adjustSize()` wächst
  danach nach unten (obere Kante fest). Zuletzt ausgerichtet wird in Schritt 12 (ca. 200 px hoch).
  Schritt 13 ist mit Text, „Gespeichert unter …“ und Knopfzeile ca. 350 px hoch; sein Ziel
  (`ergebnisliste_btn`) überlappt nicht, also keine Neuausrichtung. Schritt 14/15 haben kein Ziel.
- **Nachgestellt (Unterkante bei Bildschirmunterkante 1040):**

| Schritt | Überstand (Prüfer) | Überstand (Gegenprüfung) |
|---|---|---|
| 13 | 100 px | 101 px |
| 14 | 10 px | 26 px |
| 15 | 40 px | 56 px |

  Bei 1366×728 und 800×800 dieselben Überstände; hängt nur von Reihenfolge und Texthöhen ab.
- **Folge:** Unter Windows liegt die Knopfzeile („PDF öffnen“, „Weiter“/„Fertig ✔“, „Beenden“)
  hinter der Taskleiste bzw. unter dem Rand, genau beim Kernstück „PDF öffnen“. Laut Gegenprüfung
  ist der Überstand mit echter Titelleiste eher größer (nur am Code). Einschränkung: Die
  Titelleiste bleibt sichtbar, das Fenster lässt sich hochziehen; das X beendet die Demo wie
  „Fertig“; 13 und 14 schalten per Countdown weiter.
- **Soll:** Das Fenster bleibt immer vollständig in `screen().availableGeometry()`.
- **Vorschlag:** Unterkante verankern: nach jeder Größenänderung (`resizeEvent` oder am Ende von
  `anzeigen`/`hinweis`/`extra`/`angehalten_anzeigen`) `y = min(y, verfügbar.bottom() -
  frameHeight - 48)`. GUI-Test „Panel liegt in jedem Schritt innerhalb von availableGeometry“.
- **Gegenprüfung:** bestätigt, mittel (jeder Lauf auf üblichem Bildschirm; Text von Schritt 13
  wurde am 13.10. noch verlängert).

### Nr. 2 [niedrig] „Weiter“ lässt das Erklärfenster vor jedem Schritt in die andere Ecke springen

- **Stelle:** `desktop_demo.py:427-438` (`weiter` → `_alles_sofort`), `:509-523` (Ende von
  `_naechste_aktion`), `:283-291`.
- **Ablauf:** `weiter()` ruft auch bei fertigem Schritt `_alles_sofort()` → `_naechste_aktion()`;
  deren Ende führt erneut `_panel_ausweichen()` und `_countdown_starten()` aus. Bei großen Zielen
  (Tabellen in Schritt 4, 5, 10, 11, 12) überlappt das Fenster in beiden Ecken, `ausweichen`
  springt ohne Platzprüfung.
- **Nachgestellt:** je „Weiter“ zwei Sprünge, z. B. x=24 → 1379/1409 → 24 (4→5, 10→11, 11→12).
- **Vorschlag:** Ende von `_naechste_aktion` nur ausführen, wenn eine Aktion lief, bzw.
  `_alles_sofort` bei leerem `_offen` überspringen; in `ausweichen` nur wechseln, wenn die andere
  Ecke das Ziel nicht schneidet.
- **Gegenprüfung:** bestätigt, niedrig.

### Nr. 3 [niedrig] Schritt 4 übernimmt den Teilnehmer-Dialog ohne Prüfung

- **Stelle:** `desktop_demo.py:1000-1009` (`ersten_speichern`); Folgen `:1089-1093`,
  `:1148-1150`.
- **Ablauf:** Eigene Eingaben im Demo-Dialog sind vorgesehen (`eventFilter`). Schritt 2 prüft den
  Termin-Dialog mit `_pruefen_und_akzeptieren`, Schritt 4 nimmt `dialog.ergebnis()` ungeprüft und
  merkt die ID unter dem eingegebenen Nachnamen.
- **Nachgestellt (beide):**
  - Nachname „Müller“: Schritt 8 hält mit „Dieser Schritt ließ sich nicht vorführen: 'Albers'“
    (KeyError).
  - Vor- und Rufname leer: Teilnehmer ohne Pflichtangaben gespeichert.
  - Geburtsdatum „31.02.2020“: Abbruch in Schritt 4, Meldung ohne Feldnamen.
  - Disziplin geändert: Schritt 8 meldet „Zeile … nicht zu finden“.
  - Folgen bleiben auf den Demo-Termin beschränkt.
- **Vorschlag:** `dialog._pruefen_und_akzeptieren()` aufrufen, bei `result() != Accepted`
  `DemoFehler` mit Hinweis; `self._ids` immer unter dem Demonamen
  (`demo_daten.TEILNEHMER[0]["daten"]["nachname"]`); optional `KeyError` in `feld()` als
  `DemoFehler`.
- **Gegenprüfung:** bestätigt, niedrig.

### Nr. 4 [niedrig] Schritte 4–6, 9, 10 und 12 holen ihren Reiter nicht nach vorn

- **Stelle:** `desktop_demo.py:997-1048`, `:1110-1130`, `:1141-1155`; nur Schritt 3, 7, 8, 11, 13
  rufen `_reiter_zeigen`.
- **Nachgestellt:** In Schritt 3 auf „Zeitplan“ wechseln: Schritte 4–6 laufen unsichtbar weiter,
  Markierung nicht sichtbar; erst Schritt 7 wieder sichtbar.
- **Vorschlag:** Am Anfang jedes Schritts bzw. vor dem Markieren `_reiter_zeigen(...)`.
- **Gegenprüfung:** bestätigt, niedrig.

### Nr. 5 [niedrig] Startfehler aus dem Startdialog beendet das ganze Programm; Statusmeldung im Hauptfenster irreführend

- **Stelle:** `desktop_demo.py:384-393`, `:1186-1194`; `app.py:4466-4467`; Statusmeldung
  `desktop_demo.py:482-487`.
- **Ablauf (nachgestellt mit `init_db` → `OSError(28)`):** `starten()` räumt sauber auf
  (Temp-Ordner weg, `quitOnLastWindowClosed` wiederhergestellt) und wirft weiter; im
  Startdialog-Weg fängt niemand (`demo_ohne_termin_ausfuehren`, `_startdialog_schleife`, `main`),
  „Unerwarteter Fehler“, Programm endet. Im Hauptfenster-Weg steht „Demoprüfung beendet – der
  Demo-Termin wurde gelöscht.“, obwohl die Demo nie lief (Knöpfe frei, echter Termin verbunden).
- **Vorschlag:** In `_startdialog_schleife` bzw. `demo_ohne_termin_ausfuehren` `Exception`
  abfangen, Klartext-Warnung, zurück zum Startdialog; Statusmeldung nur nach erfolgreichem Start
  (Merker `self._gestartet`).
- **Gegenprüfung:** bestätigt, niedrig.

### Nr. 6 [niedrig] Unerwartete Fehler in Demo-Schritten nur gekürzt angezeigt, nirgends protokolliert

- **Stelle:** `desktop_demo.py:504-506`, `:514-516`, `:535-541`.
- **Ablauf:** Jede Ausnahme, auch Programmierfehler, landet nur als `str(exc)` im Erklärfenster
  (bei KeyError nur „'Albers'“, siehe Nr. 3). Kein Traceback im Absturzprotokoll, kein Eintrag in
  „Diagnose kopieren“.
- **Vorschlag:** Für Nicht-`DemoFehler` Traceback ins Absturzprotokoll (Hilfsfunktion in
  `desktop_gemeinsam`) und `f"{type(exc).__name__}: {exc}"` im Panel.
- **Gegenprüfung:** bestätigt, niedrig.

### Nr. 7 [niedrig] Testlücken

- Kein Test für: Lage des Erklärfensters (Nr. 1) und Springen (Nr. 2), eigene Änderungen im
  Teilnehmer-Dialog (Nr. 3), Reiter nach vorn (Nr. 4), Startfehler im Startdialog-Weg (Nr. 5),
  Schließen des Erklärfensters über das X (`DemoPanel.closeEvent` → `beenden`; der vorhandene
  Test schließt das Hauptfenster), `_termin_wechseln` mit Demo-Wunsch (`app.py:4188-4190`;
  `_StartDialogAttrappe` liefert `Rejected`), `_sitzungsende_pruefen` während laufender Demo.
- **Gegenprüfung:** bestätigt, niedrig.

### Nr. 8 [optional] Doppelte Rückfrage zu ungespeicherten Ergebnissen, „verwerfen“ beim Start trifft nicht zu

- **Stelle:** `app.py:4021`, `desktop_demo.py:948-955`.
- **Ablauf:** Die Startfrage „… starten und diese ungespeicherten Änderungen verwerfen?“ verwirft
  nichts; umgeschaltet wird erst in Schritt 2, der erneut fragt (bis zu vier Fragen).
- **Einordnung (Gegenprüfung):** Die Rückfrage in Schritt 2 ist bewusst entschieden
  (Verifikation 04.10., Befund 5); übrig bleibt die irreführende Startfrage.
- **Vorschlag:** Startfrage umformulieren oder nur in Schritt 2 fragen.

### Nr. 9 [optional] Toter Zweig und unzutreffender Kommentar

- `app.py:4018-4020` mit `desktop_demo.py:421-425`: `_demo_starten` → `panel_zeigen()` ist
  unerreichbar, weil `demo_btn` während der Demo gesperrt ist. Wegen Nr. 1 wäre ein „Erklärfenster
  zeigen“ nützlich: Knopf aktiv lassen oder Zweig entfernen.
- `desktop_demo.py:1004`: „Dialog wurde vom Anwender geschlossen – mit den Demodaten weiter“
  stimmt nicht; X/Esc verstecken den Dialog nur (`_lebt` bleibt True), übernommen werden seine
  Werte; der `else`-Zweig ist praktisch unerreichbar.
- **Gegenprüfung:** bestätigt, optional.

### Nr. 10 [optional, teilweise] Demo baut Reiter-Logik nach

- **Stelle:** `desktop_demo.py:1019-1029`, `:1050-1072`, `:1141-1155`, `:1157-1175` gegenüber
  `app.py:752`, `:2944-2971`, `:2234-2265`, `:3308-3315`; Zugriffe auf `_bezahlt_umschalten`,
  `_auswahl_wiederherstellen`, `_pruefen_und_akzeptieren`, `_pfad_manuell_geaendert`.
- **Verworfen (Gegenprüfung):** Dass die Demo direkt über `db`/`pdf_export` statt über die Knöpfe
  arbeitet, ist dokumentiert entschieden (Fortschritt.md 04.10.: „Modale Rückfragen werden
  umgangen …“); die Kopplung an private Methoden fängt der Komplettlauf-Test ab.
- **Bleibt:** Beim Stechen fasst die Demo alle Teilnehmer mit `stechen == "offen"` über alle
  Leistungsklassen zusammen; die echte Logik trennt nach Leistungsklasse
  (`shs_core.stechen_gruppen`). Mit den Demodaten folgenlos.
- **Vorschlag (Prüfer):** Kern ohne Rückfrage in den Reitern abtrennen (z. B.
  `ZeitplanTab.verteilen_ohne_rueckfrage()`), von Knopf und Demo gemeinsam genutzt.

### Nr. 11 [optional] „Durchsuchen…“ bleibt im Demo-Dialog „Neuen Termin anlegen“ aktiv

- **Stelle:** `desktop_demo.py:905-908`; der Knopf liegt nicht in der `QDialogButtonBox`
  (`desktop_dialoge.py:1420`).
- **Ablauf:** Pfadfeld schreibgeschützt, über „Durchsuchen…“ lässt sich trotzdem ein Ort wählen;
  angezeigt, aber ignoriert (gespeichert wird in `self.pfad`).
- **Vorschlag:** Knopf in der Demo sperren (Attribut im Dialog).
- **Gegenprüfung:** bestätigt, optional.

## Hinweise des Prüfers: Einordnung

- **`TerminImportDialog` migriert Alt-Dateien beim Lesen** (`desktop_dialoge.py:717`), auch aus
  dem Demo-Termin heraus: kein eigener Befund, Teilaspekt von Teil 1 Nr. 2; Nebeneffekt laut
  Fortschritt.md:279 als harmlos festgehalten. Die Zusage der Demo betrifft ihre eigenen Aktionen.
- **Rückgabewert von `QDesktopServices.openUrl` nirgends geprüft** (`desktop_gemeinsam.py:115`,
  `:131`, `app.py:3248`, `:3809`, `desktop_demo.py:622`): kein Befund für Teil 10; unter Windows
  erscheint bei fehlender Zuordnung meist „Öffnen mit“. Höchstens optionaler Punkt für das ganze
  Programm (Teil 9).
- **Teil 3/8:** `_tab_gewechselt` fragt modal, wenn der Anwender während Schritt 8/9 den Reiter
  wechselt; erwartetes Verhalten, in der Demo eine weitere Unterbrechung.
- **Bezug, nicht neu gezählt:** Teil 7 Nr. 4 und Nr. 9 (`_termin_setzen` zweimal je Lauf, alte
  Reiter), Teil 2 Nr. 9 (versteckte Dialoge).

## Ohne Befund geprüft (laut Prüfer)

Temp-Ordner (`mkdtemp` 0700, Prüfung gegen Termine-Ordner, Löschen samt `Ausdrucke`;
`demo_reste_aufraeumen` nur `shs_demo_*`, Symlink-Wurzel verweigert); Sperren (Datensicherung,
Terminwechsel, zweiter Demo-Start; Strg+S versteckter Reiter feuert nicht); Klartext (S-1) im
Erklärfenster, Statusleiste und Titel; Wiederherstellung des echten Termins samt Reiter,
`_demo_sperren(False)` und Schließen im `finally`; Rückfrage zu ungespeicherten Ergebnissen;
Schließen des Hauptfensters in Schritt 1 und ab Schritt 2; Countdown (wartet bei modalen Fenstern,
hält bei Eingabe und „PDF öffnen“, keiner im letzten Schritt/nach Fehler, Filter entfernt);
Wiedereintritt bei modalen Rückfragen; Lebensdauer über `_lebt`, `closeEvent` rekursionsfrei;
Start aus dem Startdialog (eigene Schleife, `deleteLater`); Demo-Daten und Erklärtexte der
Schritte 1–15 passen zum Code; `init_db` auf aktuellem echten Termin schreibt nicht (gleicher Hash
und mtime); PostgreSQL/Web nicht betroffen.
