# Sicherheitsprüfung Web-Verbindung des Desktops (20.11.2026)

Anlass: UX-Test Web 2026-11, Aufgabe U8 (Entscheidung E4: Ohne „Passwort merken“ behält das
Programm das Web-Passwort im Arbeitsspeicher bis zum Beenden, statt es bei jedem Ablauf neu
abzufragen). Prüfer: Agent `qs-sicherheit`, Diff `desktop_web.py`, `app.py`, `test_gui_web.py`;
dazu die Nachprüfung aus Aufgabe U13 und die Korrektur S-U14 (Aufgabe U14).

**Veröffentlicht am 21.11.2026, nach dem Release 1.0.63.** Die Web-Verbindung des Desktops ist mit
1.0.63 zum ersten Mal ausgeliefert worden; alle hier genannten Punkte waren vorher in keinem Release.
Der Bericht nennt nur Punkte, die in 1.0.63 behoben sind.

## Ergebnis

**Kein hoher und kein mittlerer Fund.**
- Das Passwort geht an keinen anderen Server als den, für den es eingegeben wurde. Es ist an
  Adresse, Benutzer und normalisierten Fingerabdruck gebunden, und der Fingerabdruck wird geprüft,
  bevor das erste Byte gesendet wird.
- Es landet nicht in den Einstellungen (QSettings), in Dateien, Protokollen, Meldungen oder
  Tooltips. Protokolle entstehen über `traceback.format_exception` ohne lokale Variablen,
  Netzfehler werden mit `from None` weitergegeben.
- Es wird in allen vorgesehenen Fällen verworfen: Terminwechsel, geänderte Verbindungsdaten,
  Ablehnung durch den Server (401), Programmende.
- Die Variable mit dem Passwort wird nur im GUI-Thread benutzt.

## Punkte und Stand

| Punkt | Inhalt | Stand in 1.0.63 |
|---|---|---|
| G-1 (gering) | Mit Windows-Tresor und bewusst abgewähltem „Passwort merken“ behielt das Programm das Passwort trotzdem bis zum Beenden oder Terminwechsel, ohne dass das sichtbar war (Problem bei gemeinsam genutztem PC). | Behoben: Ein sichtbarer Hinweis unter dem Haken erklärt das, solange er nicht gesetzt ist (`_behalten_hinweis`). Das Verhalten selbst ist die Entscheidung E4. |
| G-2 (gering) | Ein Passwort aus dem Tresor oder ein eben dort abgelegtes wurde zusätzlich bis Programmende im Arbeitsspeicher gehalten, als zweite langlebige Kopie ohne Nutzen. | Behoben: Im Arbeitsspeicher bleibt nur, was nicht im Tresor liegt (`mit_web_anmeldung`, `_uebernehmen`). |
| G-2a (gering, Nachbesserung zu G-2) | Der Fix zu G-2 war unvollständig. Ein zweiter Aufruf von `mit_web_anmeldung` in derselben Sitzung (z. B. „Ergebnisse aus Web holen“: erst Terminliste, dann Laden) verlor die Herkunft „Tresor“, sodass das Tresor-Passwort doch im Arbeitsspeicher landete. Ein 401 im zweiten Aufruf hätte den Tresor-Eintrag nicht verworfen. | Behoben: Die Sitzung führt die Herkunft mit (`_Sitzung.aus_tresor`), auch für ein im selben Ablauf neu abgelegtes Passwort. Test `test_sitzung_behaelt_die_herkunft_des_passworts`. |
| H-1 (Hinweis) | „Verbindung testen“: Ein 401 verwarf nur die Kopie im Arbeitsspeicher, nicht das abgelehnte Tresor-Passwort. Ein 401 nach der Anmeldung (abgelaufenes Token) hätte dagegen ein richtiges Passwort verworfen. | Behoben: Die Quelle des Passworts wird gemerkt, nur ein 401 der Anmeldung zählt, und genau diese Quelle wird verworfen. |
| H-2 (Hinweis) | Der Platzhalter im Passwortfeld las den Tresor bei jedem Tastendruck in der Adresszeile neu (unnötige Klartextkopien). | Behoben: Der Tresor-Stand wird je Adresse zwischengespeichert, die Adresse erst nach Abschluss der Eingabe ausgewertet. |
| S-U14 (Hinweis, in der Prüfung zuerst „H-3“) | Der Tresor-Eintrag war nur an die Adresse gebunden, nicht an den Fingerabdruck. Bestätigte man für dieselbe Adresse einen neuen Fingerabdruck (z. B. nach einem Angriff auf Netz oder DNS, trotz deutlicher Warnung), gingen Verbindungstest und Abläufe mit dem Tresor-Passwort an den neuen Server. | Behoben: Wird ein abweichender Fingerabdruck bestätigt, löscht das Programm den Tresor-Eintrag dieser Adresse, ebenso einen Eintrag ohne bekannten Fingerabdruck. Schlägt das Löschen fehl, übernimmt es den neuen Fingerabdruck nicht. Die Warnung „ANDERER Fingerabdruck“ vergleicht normalisiert und auch mit dem gespeicherten Wert. Tests `test_neuer_fingerabdruck_*`, `test_gleicher_fingerabdruck_*`, `test_tresor_eintrag_ohne_bekannten_fingerabdruck_wird_entfernt`, `test_sicherheitskorrektur_s_u14`. |

## Einordnung

Python-Zeichenketten lassen sich im Speicher nicht überschreiben. Gegen andere Programme desselben
Windows-Benutzers ist das Passwort im Arbeitsspeicher damit ähnlich geschützt wie im Tresor, gegen
ein Speicherabbild oder die Auslagerungsdatei etwas schwächer. Für den Einsatzzweck ist das
vertretbar (Entscheidung E4).

Zusammenhang: [UX-Test Web 2026-11](UX-Test-2026-11-Web/Bericht.md), Aufgaben U8, U13 und U14 in
[aufgaben-umsetzung.md](UX-Test-2026-11-Web/aufgaben-umsetzung.md); Bedienung im Handbuch,
Kapitel 12 „Für die Prüfungsleitung: Termin im Web veröffentlichen“.
