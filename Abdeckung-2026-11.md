# Testabdeckung, Stand 01.11.2026 (OFFEN B10)

Messung mit coverage 7.16.2 auf Windows 11 (Anaconda-Python 3.14, PySide6 6.11). Gemessen haben
`test_app_gui.py`, `test_theme.py` (417 bestanden) und die lokale Unittest-Suite (693 Tests,
175 übersprungen). Nicht dabei sind die echten PostgreSQL-Tests, die nur in der CI laufen.
Gezählt werden Anweisungen der Programm-Module, ohne Tests und `tools/`.

**Gesamt: 91 % (9134 Anweisungen, 801 nicht ausgeführt).**

| Modul | Anweisungen | nicht ausgeführt | Abdeckung |
|---|---:|---:|---:|
| bump_version.py | 69 | 50 | 28 % ¹ |
| sync_termin.py | 73 | 50 | 32 % ² |
| desktop_zeitplan.py | 450 | 89 | 80 % |
| desktop_verwaltung.py | 201 | 39 | 81 % |
| desktop_dialoge.py | 911 | 104 | 89 % |
| desktop_gemeinsam.py | 549 | 55 | 90 % |
| app.py | 1879 | 177 | 91 % |
| selbsttest.py | 192 | 18 | 91 % |
| desktop_auswertung.py | 345 | 30 | 91 % |
| db.py | 1319 | 95 | 93 % ² |
| desktop_demo.py | 735 | 41 | 94 % |
| db_sicherung.py | 238 | 10 | 96 % |
| desktop_programm.py | 255 | 10 | 96 % |
| desktop_darstellung.py | 127 | 4 | 97 % |
| app_web.py | 427 | 12 | 97 % |
| db_import.py | 424 | 10 | 98 % |
| shs_core.py | 107 | 1 | 99 % |
| pdf_export.py | 822 | 6 | 99 % |
| demo_daten.py, version.py | 11 | 0 | 100 % |

¹ `test_bump_version` startet das Skript als eigenen Prozess; der wird nicht mitgemessen. Die
Abdeckung ist dort tatsächlich höher.
² `sync_termin.py` und die `*_postgres`-Funktionen in `db.py` testet die CI gegen PostgreSQL.

## Die größten echten Lücken

Gemeint sind Funktionen, von denen mindestens 5 Zeilen in keinem Test laufen.

**Zeitplan-Reiter (`desktop_zeitplan.py`).** Die Bearbeitungsaktionen werden nur indirekt
angestoßen:
- `_richter_hinzufuegen`, `_richter_umbenennen`, `_richter_verschieben`, `_richter_loeschen`
- `_eintrag_verschieben`, `_eintrag_bearbeiten`, `_eintrag_entfernen`
- `_pruefungsblock_hinzufuegen`

Die dahinterliegenden `db.py`-Funktionen sind getestet, die Oberflächen-Schicht (Rückfrage,
Fehlermeldung, Aktualisieren) nicht. Das ist die größte zusammenhängende Lücke.

**Datensicherung (`desktop_verwaltung.py`).**
- `_konflikt_abfragen`, die Rückfrage bei schon vorhandenen Terminen beim Wiederherstellen,
  läuft in keinem Test.
- Bei `_sicherung_erstellen` und `_sicherung_wiederherstellen` fehlen einzelne Fehlerwege.

**Dialoge (`desktop_dialoge.py`).** Diese Dialoge werden in Tests nie aufgebaut, weil die
Aufrufer sie ersetzen:
- `PruefungsblockDialog`
- `SicherungErstellenDialog`
- `StartnummerTauschenDialog`

Bei `VeranstaltungsDialog._pruefen_und_akzeptieren` fehlen einzelne Prüfzweige.

**Hauptfenster (`app.py`).**
- `main` (Programmstart, wird über den Selbsttest der gebauten Fassung geprüft).
- Teile von `_startnummer_tauschen` / `_zwei_markierte_tauschen`, `_teilnahme_umschalten`,
  `_bezahlt_umschalten`, `_oma_importieren`, `_termin_loeschen` (Fehler- und Abbruchwege) und
  `_sortierschluessel_fuer_zeile`.

**Kleinere Stellen.**
- `desktop_gemeinsam._datei_gespeichert_melden`
- `desktop_auswertung._ablageort_oeffnen`
- `_stechen_sieger_festlegen` (Teile)
- `desktop_demo._reiter_zeigen` (Teile)
- `db.termin_oeffnen`: Fehlerwege beim Öffnen beschädigter oder fremder Dateien

## Empfehlung

Die Zahlen oben sind der Stand vor den neuen Tests. Marco hat alle drei Empfehlungen
freigegeben; sie sind am selben Tag umgesetzt, siehe den Nachtrag unten. Empfohlen waren:

1. **Zeitplan-Bearbeitung über die Oberfläche** (Richter anlegen, umbenennen, verschieben,
   löschen; Eintrag verschieben, bearbeiten, entfernen; Prüfungsblock). Das wird am Prüfungstag
   häufig benutzt und hebt `desktop_zeitplan.py` auf über 90 %. Größe etwa M.
2. **Konflikt-Rückfrage beim Wiederherstellen einer Sicherung.** Hier droht Datenverlust, wenn
   die Rückfrage falsch entscheidet. Größe S.
3. **Die drei nie aufgebauten Dialoge** einmal aufbauen und mit gültiger und ungültiger Eingabe
   bestätigen. Größe S.

`main`, die PostgreSQL-Wege und `bump_version.py` brauchen keine weiteren lokalen Tests; sie
sind über Selbsttest bzw. CI abgedeckt.

## Nachtrag 01.11.2026: Lücken geschlossen

In `test_app_gui.py` gibt es neue Tests, alle im Block „Abdeckung 01.11.2026 (OFFEN B10)“.

| Modul | vorher | nachher |
|---|---:|---:|
| desktop_zeitplan.py | 80 % | 96 % |
| desktop_verwaltung.py | 81 % | 90 % |
| desktop_dialoge.py | 89 % | 98 % |

Die Werte „nachher“ stammen aus dem Lauf von `test_app_gui.py` und `test_theme.py` allein; mit
der Unittest-Suite liegen sie eher etwas höher. Fehler im Programm haben die neuen Tests nicht
gefunden.

Eine Auffälligkeit gab es: „Entfernen“ im Zeitplan löschte einen Prüfungsblock ohne Rückfrage.
Auf Marcos Wunsch fragt das Programm jetzt nach, mit Vorgabe „Nein“, wie bei „Richter löschen“.

Weiterhin ungetestet sind vor allem die Fehlerwege beim Erstellen und Wiederherstellen von
Sicherungen (z. B. Datei nicht schreibbar) und im Zeitplan die Startzeit-, Verteilungs- und
Pausen-für-alle-Fehlerwege.
