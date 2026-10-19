# UML-Schaubilder: SHS-Prüfungsprogramm

Stand: 19.10.2026 (nach der Aufteilung von `app.py` und dem Umbau der Ergebniserfassung,
offene Punkte O1–O11). Die Schaubilder sind Mermaid-Diagramme; GitHub zeigt sie direkt als
Grafik an. Sie ergänzen `Architektur.md` (Modultabelle, Entscheidungen) um die Abläufe.
Ändert sich ein Ablauf, das passende Diagramm hier mitpflegen.

Inhalt:
1. [Komponenten](#1-komponenten)
2. [Klassen der Desktop-App](#2-klassen-der-desktop-app)
3. [Gesamtablauf eines Prüfungstermins](#3-gesamtablauf-eines-prüfungstermins)
4. [Programmstart und Beenden](#4-programmstart-und-beenden)
5. [Termin öffnen (Prüfungen)](#5-termin-öffnen-prüfungen)
6. [Teilnehmer erfassen und importieren](#6-teilnehmer-erfassen-und-importieren)
7. [Zeitplan](#7-zeitplan)
8. [Ergebnisse erfassen und speichern (Desktop)](#8-ergebnisse-erfassen-und-speichern-desktop)
9. [Auswertung, Stechen und Ausdrucke](#9-auswertung-stechen-und-ausdrucke)
10. [Web-Erfassung am Prüfungstag](#10-web-erfassung-am-prüfungstag)
11. [Datensicherung und Wiederherstellung](#11-datensicherung-und-wiederherstellung)
12. [Update-Prüfung und Sitzungsende](#12-update-prüfung-und-sitzungsende)
13. [Demoprüfung](#13-demoprüfung)

---

## 1. Komponenten

Zwei Oberflächen, eine gemeinsame Fach- und Datenschicht. Pfeile zeigen „benutzt“.

```mermaid
flowchart LR
    subgraph Desktop["Desktop-App (PySide6)"]
        app["app.py<br/>HauptFenster, StartDialog,<br/>Teilnehmer, Formular-Import,<br/>Ergebniserfassung, main()"]
        reiter["desktop_auswertung.py<br/>desktop_zeitplan.py<br/>desktop_verwaltung.py"]
        programm["desktop_programm.py<br/>Version/Update, Sitzungsende,<br/>Zweitstart"]
        dialoge["desktop_dialoge.py"]
        gemeinsam["desktop_gemeinsam.py"]
        darstellung["desktop_darstellung.py"]
        demo["desktop_demo.py<br/>+ demo_daten.py"]
        imp["db_import.py"]
        sich["db_sicherung.py"]
        selbst["selbsttest.py"]
    end

    subgraph Web["Web-Backend (Flask, Container)"]
        web["app_web.py"]
        tpl["templates/*.html"]
    end

    subgraph Kern["Gemeinsame Schicht"]
        db["db.py<br/>Schema, Migrationen,<br/>Termine, Teilnehmer, Ergebnisse,<br/>Zeitplan, Sync"]
        core["shs_core.py<br/>Wertnoten, Rangliste"]
        pdf["pdf_export.py<br/>alle PDF-Ausdrucke"]
    end

    sqlite[("SQLite-Datei<br/>je Termin")]
    pg[("PostgreSQL<br/>Schema je Termin")]
    sync["sync_termin.py (CLI)"]
    gh(["GitHub Releases"])

    app --> reiter & programm & dialoge & gemeinsam & darstellung & demo & imp
    reiter --> dialoge & gemeinsam & sich & pdf
    app --> pdf & core & selbst
    demo --> pdf
    imp --> db
    sich --> db
    dialoge --> db
    gemeinsam --> db
    reiter --> db
    app --> db
    web --> db & tpl
    pdf --> db
    db --> core
    db --> sqlite
    db --> pg
    sync --> db
    programm -.Update-Prüfung.-> gh
```

---

## 2. Klassen der Desktop-App

Die wichtigsten Klassen und wie sie zusammenhängen. Reiter sind `QWidget`s im
`HauptFenster`; Dialoge werden bei Bedarf modal geöffnet (`_ausfuehren`).

```mermaid
classDiagram
    direction LR

    class HauptFenster {
        +conn
        +pfad
        +teilnehmer_tab
        +ergebnis_tab
        +auswertung_tab
        +zeitplan_tab
        -_tab_gewechselt(index)
        -_rueckfrage_ungespeichert()
        -_darstellung_neu_anwenden()
        +closeEvent(event)
    }
    class StartDialog {
        +pfad
        +neu_angelegt
        -_aktualisieren()
        -_termin_oeffnen()
        -_neuer_termin()
        -_termin_loeschen()
    }
    class TeilnehmerTab
    class FormularImportTab
    class ErgebnisTab {
        +tabelle
        +aktualisieren()
        +aktualisieren_falls_geaendert()
        +alle_speichern(meldungen)
        +farben_auffrischen()
        +hat_ungespeicherte_aenderungen()
        +punkte(zeile, disziplin)
        +punkte_eintragen(...)
        +status_setzen(...)
        +zelle_gesperrt(...)
    }
    class _ErgebnisTabelle {
        +moveCursor()
        +keyPressEvent()
        +offenen_editor_beenden()
    }
    class _PunkteDelegate {
        +createEditor()
        +setEditorData()
        +setModelData()
        +paint()
    }
    class _HakenDelegate {
        +paint()
        +editorEvent()
    }
    class _PunkteItem
    class _HakenItem
    class AuswertungTab
    class TeilnehmerUebersichtTab
    class ExportTab
    class ZeitplanTab
    class VerwaltungTab
    class DatensicherungTab
    class VersionDialog
    class SitzungsendeFilter
    class DemoTour {
        +starten()
        +beenden()
    }
    class DemoPanel
    class DemoMarkierung
    class DemoSchritt

    class TeilnehmerDialog
    class TerminImportDialog
    class VeranstaltungsDialog
    class SicherungErstellenDialog
    class PruefungsblockDialog
    class PauseDialog
    class BewertungsbogenAuswahlDialog
    class StartnummerTauschenDialog
    class HilfeDialog

    HauptFenster *-- TeilnehmerTab
    HauptFenster *-- FormularImportTab
    HauptFenster *-- ZeitplanTab
    HauptFenster *-- ErgebnisTab
    HauptFenster *-- AuswertungTab
    HauptFenster *-- TeilnehmerUebersichtTab
    HauptFenster *-- VerwaltungTab
    HauptFenster *-- ExportTab
    HauptFenster *-- DatensicherungTab
    HauptFenster ..> VersionDialog : öffnet
    HauptFenster ..> DemoTour : startet
    HauptFenster ..> SitzungsendeFilter : über sitzungsende_einrichten

    ErgebnisTab *-- _ErgebnisTabelle
    _ErgebnisTabelle o-- _PunkteItem
    _ErgebnisTabelle o-- _HakenItem
    _ErgebnisTabelle --> _PunkteDelegate : Punktespalten
    _ErgebnisTabelle --> _HakenDelegate : DQ / Abbruch

    TeilnehmerTab ..> TeilnehmerDialog
    TeilnehmerTab ..> TerminImportDialog
    TeilnehmerTab ..> StartnummerTauschenDialog
    TeilnehmerTab ..> BewertungsbogenAuswahlDialog
    ZeitplanTab ..> PruefungsblockDialog
    ZeitplanTab ..> PauseDialog
    VerwaltungTab ..> VeranstaltungsDialog
    StartDialog ..> VeranstaltungsDialog : neuer Termin
    DatensicherungTab ..> SicherungErstellenDialog
    HauptFenster ..> HilfeDialog

    DemoTour *-- DemoPanel
    DemoTour *-- DemoMarkierung
    DemoTour o-- DemoSchritt : 15 Schritte
```

---

## 3. Gesamtablauf eines Prüfungstermins

Vom Anlegen bis zur Ergebnisliste. Gestrichelte Wege sind optional.

```mermaid
flowchart TD
    start([Prüfung geplant]) --> anlegen[Termin anlegen<br/>StartDialog → VeranstaltungsDialog<br/>eine .sqlite-Datei je Termin]
    anlegen --> verw[Veranstaltungsdaten pflegen<br/>Verein, Datum, Richter,<br/>angebotene Prüfungen,<br/>Startnummern-Bereiche]
    verw --> tn{Teilnehmer erfassen}
    tn -->|einzeln| dlg[TeilnehmerDialog]
    tn -->|Liste| csv[CSV- / OMA-Import]
    tn -->|Anmeldeformulare| form[Formular-Import<br/>ausgefüllte PDF-Formulare]
    tn -->|anderer Termin| alt[Stammdaten aus<br/>anderem Termin]
    dlg & csv & form & alt --> nummern[Startnummern vergeben<br/>„Fehlende Startnummern vergeben…“]
    nummern --> bezahlt[Bezahlt / keine Teilnahme<br/>markieren]
    bezahlt --> zeit[Zeitplan<br/>automatisch verteilen,<br/>Blöcke und Pausen anpassen]
    zeit --> druck1[Ausdrucke vor der Prüfung<br/>Zeitplan, Bewertungsbögen,<br/>Etiketten, Richter-/Behältnisbedarf]
    druck1 --> tag{Prüfungstag:<br/>wo werden Ergebnisse erfasst?}
    tag -->|Desktop| erf[Ergebniserfassung<br/>Punkte, DQ, Abbruch<br/>„Alle Ergebnisse speichern“]
    tag -.->|mehrere Richter| webv[Termin im Web veröffentlichen<br/>Richter erfassen im Browser<br/>Ergebnisse zurückholen]
    webv -.-> erf
    erf --> ausw[Auswertung<br/>Wertnoten, Plätze]
    ausw --> stech{Gleichstand<br/>um einen Platz?}
    stech -->|ja| stechen[„Stechen-Sieger festlegen…“]
    stech -->|nein| druck2
    stechen --> druck2[Ergebnisliste, Statistik,<br/>Übersicht Prüfungsleitung als PDF]
    druck2 --> sich[Datensicherung<br/>ZIP, optional verschlüsselt]
    sich --> ende([Termin abgeschlossen])
```

---

## 4. Programmstart und Beenden

`app.main()` bis zur Ereignisschleife und das Beenden des Hauptfensters.

```mermaid
stateDiagram-v2
    [*] --> Argumente
    Argumente --> Selbsttest : --selbsttest
    Selbsttest --> [*] : Exit-Code 0/1 + Protokoll

    Argumente --> Einrichten : normaler Start
    note right of Einrichten
        Absturzprotokoll, Laufkennung (Mutex für das Setup),
        Fehlerfenster, deutsche Qt-Texte, Design/Akzentfarbe
    end note
    Einrichten --> Zweitstart
    Zweitstart --> [*] : läuft schon, Nutzer bricht ab
    Zweitstart --> DemoResteAufraeumen
    DemoResteAufraeumen --> Startdialog

    state Startdialog {
        [*] --> Terminliste
        Terminliste --> NeuerTermin : „Neuer Termin…“
        NeuerTermin --> Terminliste : abgebrochen
        Terminliste --> Gewaehlt : Termin gewählt
        NeuerTermin --> Gewaehlt : angelegt
        Terminliste --> DemoAusStart : „Demoprüfung“
        DemoAusStart --> Terminliste
    }
    Startdialog --> [*] : abgebrochen
    Gewaehlt --> TerminOeffnen
    TerminOeffnen --> Startdialog : nicht öffenbar / „Nein“ bei großer Datei
    TerminOeffnen --> Hauptfenster : Verbindung offen

    state Hauptfenster {
        [*] --> Arbeiten
        Arbeiten --> Arbeiten : Reiterwechsel (Rückfrage bei ungespeicherten Ergebnissen)
        Arbeiten --> Terminwechsel : „Anderen Termin öffnen…“
        Terminwechsel --> Arbeiten : abgebrochen
        Terminwechsel --> Arbeiten : neuer Termin geladen
        Arbeiten --> Schliessen : Fenster-X / Windows meldet ab
    }
    state Schliessen {
        [*] --> AutoSpeichern : ungespeicherte Ergebnisse
        [*] --> Ende : nichts offen
        AutoSpeichern --> Ende : alles gespeichert
        AutoSpeichern --> Nachfrage : Zeile nicht speicherbar
        Nachfrage --> Ende : „Ja, verwerfen“
    }
    Nachfrage --> Hauptfenster : „Nein“ (Vorgabe)
    Ende --> [*]
```

---

## 5. Termin öffnen (Prüfungen)

`_termin_oeffnen_mit_meldung` → `db.termin_oeffnen`. Fremde Dateien werden zuerst nur
lesend geprüft, bevor das Programm hineinschreibt.

```mermaid
sequenceDiagram
    autonumber
    actor N as Nutzer
    participant S as StartDialog
    participant A as app._termin_oeffnen_mit_meldung
    participant D as db.termin_oeffnen
    participant F as SQLite-Datei

    N->>S: Termin wählen
    S->>A: pfad
    A->>D: termin_oeffnen(pfad)
    D->>F: existiert? Größe?
    alt Datei fehlt
        D-->>A: TerminNichtOeffenbar
        A-->>N: Meldung, zurück zum Startdialog
    else größer als 50 MB
        D-->>A: TerminUngewoehnlichGross
        A->>N: „ungewöhnlich groß, trotzdem öffnen?“
        N-->>A: Ja
        A->>D: termin_oeffnen(pfad, groesse_bestaetigt=True)
        Note over D: ohne Schrittgrenze prüfen
    end
    D->>F: liegengebliebenes Journal zurückspielen
    D->>F: nur lesend öffnen
    Note over D,F: Schrittgrenze (lesen_begrenzen),<br/>Aufbau prüfen, quick_check
    alt beschädigt / fremd / zu aufwendig
        D-->>A: TerminNichtOeffenbar (Klartext)
        A-->>N: Meldung
    else in Ordnung
        D->>F: init_db (Migrationen)
        D->>F: Schreibprobe (PRAGMA user_version)
        D->>D: Wertebereiche prüfen
        D-->>A: Verbindung
        A-->>S: conn
    end
```

---

## 6. Teilnehmer erfassen und importieren

```mermaid
sequenceDiagram
    autonumber
    actor N as Nutzer
    participant T as TeilnehmerTab
    participant FI as FormularImportTab
    participant DL as TeilnehmerDialog / TerminImportDialog
    participant I as db_import
    participant D as db

    alt einzeln
        N->>T: „Neu…“ / Doppelklick
        T->>DL: TeilnehmerDialog
        N->>DL: Daten eingeben
        DL->>D: add_teilnehmer / update_teilnehmer
        D-->>DL: Startnummer doppelt? → Fehler im Klartext
    else CSV oder OMA-Meldeliste
        N->>T: Import wählen, Datei
        T->>I: importiere_teilnehmer_aus_csv / _aus_oma
        I->>D: je Zeile anlegen (Dubletten, Angebot prüfen)
        I-->>T: Bericht (übernommen, verworfen mit Grund)
    else ausgefüllte Anmeldeformulare
        N->>FI: PDF-Dateien wählen
        FI->>I: importiere_anmeldeformular_pdf
        I->>D: anlegen
        I-->>FI: Bericht
    else aus anderem Termin
        N->>T: „Aus anderem Termin importieren…“
        T->>DL: TerminImportDialog
        DL->>D: termin_lesend_pruefen + quick_check
        N->>DL: Teilnehmer auswählen
        DL->>I: importiere_teilnehmer_stammdaten
        I-->>DL: Hinweis auf nicht angebotene Prüfungen
    end
    N->>T: „Fehlende Startnummern vergeben…“
    T->>D: fehlende_startnummern_vergeben (je Prüfung aus den Bereichen)
    T->>T: Liste neu laden
```

---

## 7. Zeitplan

```mermaid
flowchart TD
    a[ZeitplanTab öffnen] --> b[Richter-Spuren aus den<br/>Veranstaltungsdaten]
    b --> c{Aktion}
    c -->|„Automatisch verteilen“| d[db: Prüfungsblöcke auf Richter verteilen<br/>DK-Mindestabstand beachten]
    c -->|Block hinzufügen| e[PruefungsblockDialog]
    c -->|Pause einfügen| f[PauseDialog<br/>an Position oder bei allen Richtern]
    c -->|Eintrag bearbeiten| m[db.zeitplan_eintrag<br/>Block: Dauer je Teilnehmer, Pause: PauseDialog]
    d & e & f & m --> g[db.berechne_zeitplan / berechne_zeitplan_bloecke]
    g --> h[db.zeitplan_ueberschneidungen]
    h --> i{Überschneidungen<br/>oder offene Starts?}
    i -->|ja| j[Hinweis im Reiter]
    i -->|nein| k[Plan fertig]
    j --> c
    k --> l[Zeitplan als PDF<br/>pdf_export]
```

---

## 8. Ergebnisse erfassen und speichern (Desktop)

Seit O8 sind die Zellen `QTableWidgetItem`s; ein Eingabefeld entsteht nur beim Bearbeiten.
Gespeichert wird erst mit „Alle Ergebnisse speichern“ (oder Strg+S).

```mermaid
sequenceDiagram
    autonumber
    actor N as Nutzer
    participant TB as _ErgebnisTabelle
    participant DG as _PunkteDelegate
    participant E as ErgebnisTab
    participant H as HauptFenster
    participant D as db

    N->>TB: Zelle anklicken, lostippen
    TB->>DG: createEditor (Validator 0–60 / 0–40)
    DG->>DG: setEditorData (nur solange nicht getippt)
    N->>DG: Ziffern, dann Tab / Enter
    DG->>TB: setModelData
    TB->>E: itemChanged → _zelle_geaendert
    E->>E: Zeile gelb „nicht gespeichert“,<br/>zu hoch → roter Rahmen
    opt Haken DQ / Abbruch (Klick oder Leertaste)
        N->>TB: Haken setzen (_HakenDelegate.editorEvent)
        TB->>E: itemChanged → _zelle_geaendert → _status_umgeschaltet
        E->>E: Punktezellen leeren und sperren
    end
    N->>E: „Alle Ergebnisse speichern“ / Strg+S
    E->>TB: offenen_editor_beenden (übernehmen)
    loop je geänderte Zeile
        E->>E: Eingaben prüfen (beide Felder, Höchstwerte)
        E->>D: eintragen_ergebnis / setze_ergebnis_status
    end
    Note over E,D: ab vielen Teilnehmern eine Transaktion,<br/>bei Fehler Rollback und alles bleibt gelb
    E-->>N: „n Ergebnis(se) gespeichert“ oder Liste der Fehler

    alt Reiterwechsel mit ungespeicherten Ergebnissen
        H->>N: Speichern / Nicht speichern / Abbrechen
    else Fenster schließen
        H->>E: alle_speichern (automatisch)
        E-->>H: Rest nicht speicherbar → Rückfrage
    end
```

---

## 9. Auswertung, Stechen und Ausdrucke

```mermaid
sequenceDiagram
    autonumber
    actor N as Nutzer
    participant AT as AuswertungTab
    participant D as db
    participant C as shs_core
    participant X as ExportTab
    participant P as pdf_export
    participant G as desktop_gemeinsam

    N->>AT: Reiter öffnen / Filter
    AT->>D: berechne_auswertung(conn)
    D->>C: berechne_wertnote_ed / berechne_wertnote_dk
    D->>C: berechne_rangliste (DQ/Abbruch ohne Platz)
    C-->>D: Teilnehmerergebnisse
    D-->>AT: Ergebnisse + Stechen-Gruppen
    opt Gleichstand
        N->>AT: „Stechen-Sieger festlegen…“
        AT->>D: Stechen-Sieger speichern
        AT->>D: berechne_auswertung (neu)
    end
    N->>X: Ausdruck wählen (Ergebnisliste, Statistik, …)
    X->>G: _pdf_exportieren (Ablageort Termine\Ausdrucke\Termin)
    G->>P: erstelle_…_pdf(conn, ziel)
    P->>D: Daten lesen
    P-->>G: PDF-Datei
    G-->>N: „gespeichert“ mit „PDF öffnen“ / „Ordner zeigen“
```

---

## 10. Web-Erfassung am Prüfungstag

Optional für größere Prüfungen: mehrere Richter erfassen gleichzeitig im Browser.
PostgreSQL hält je Termin ein eigenes Schema.

```mermaid
sequenceDiagram
    autonumber
    actor PL as Prüfungsleitung (Admin)
    actor R as Richter
    participant W as app_web (Flask)
    participant D as db
    participant PG as PostgreSQL

    PL->>W: Login, /admin/termine
    PL->>W: SQLite-Termin hochladen (veröffentlichen)
    W->>D: exportiere_termin_nach_postgres
    D->>PG: neues Schema mit Teilnehmern
    W-->>PL: Termin veröffentlicht

    R->>W: Login (CSRF, Session)
    R->>W: /termin-waehlen
    R->>W: /teilnehmer (Liste, Filter)
    R->>W: /teilnehmer/id öffnen
    W->>D: Ergebnis lesen (Stand beim Laden merken)
    R->>W: Punkte speichern (POST)
    W->>W: Eingaben prüfen (Bereiche, beide Felder)
    alt fehlerhaft
        W-->>R: Seite mit Fehlertext und den eingegebenen Werten
    else in Ordnung
        W->>D: eintragen_ergebnis nur für Disziplinen, die dieser Richter geändert hat
        Note over W,D: Schutz vor verlorenen Änderungen: unveränderte Disziplinen<br/>überschreiben keine Eingabe eines anderen Richters
        W-->>R: zurück zur Teilnehmerliste
    end

    PL->>W: Termin zurückholen (eigene SQLite-Datei hochladen)
    W->>D: importiere_ergebnisse_aus_postgres
    D->>PG: Ergebnisse lesen
    D-->>W: Bericht + aktualisierte Datei
    W-->>PL: Download-Link (einmalig)
    PL->>PL: Datei im Desktop öffnen,<br/>Auswertung wie gewohnt
```

Ohne Browser geht dasselbe über `sync_termin.py` auf der Kommandozeile.

---

## 11. Datensicherung und Wiederherstellung

```mermaid
sequenceDiagram
    autonumber
    actor N as Nutzer
    participant DT as DatensicherungTab
    participant S as db_sicherung
    participant F as Termine-Ordner
    participant Z as Sicherungs-ZIP

    rect rgba(127,127,127,0.08)
    N->>DT: „Sicherung erstellen…“ (optional Passwort)
    DT->>S: sicherung_erstellen(ziel, …)
    loop je Termin-Datei
        S->>F: nur lesend öffnen, backup() in den Speicher
        alt lesbar
            S->>Z: stimmige Momentaufnahme
        else nicht lesbar
            S->>Z: Datei roh + zugehöriges -journal
        end
    end
    S-->>DT: Anzahl + roh gesicherte Dateien
    DT-->>N: Meldung „gespeichert“
    end

    rect rgba(127,127,127,0.08)
    N->>DT: „Wiederherstellen…“, ZIP wählen
    DT->>S: sicherung_inhalt (Passwort sofort prüfen)
    DT->>N: Konflikte: überschreiben / als Kopie / überspringen
    DT->>S: sicherung_wiederherstellen(entscheidungen)
    S->>S: alles in Temp-Dateien entpacken (Grenzen, Namen prüfen)
    loop je Termin
        S->>F: alte Datei + altes Journal beiseitelegen
        S->>F: neue Datei (+ Journal aus dem ZIP) einsetzen
        alt Fehler
            S->>F: alte Dateien zurücklegen
        end
    end
    S-->>DT: wiederhergestellte Termine<br/>(TeilweiseWiederhergestelltError nennt die schon ersetzten)
    end
```

---

## 12. Update-Prüfung und Sitzungsende

```mermaid
sequenceDiagram
    autonumber
    actor N as Nutzer
    participant V as VersionDialog
    participant T as Hintergrund-Thread
    participant GH as GitHub API
    participant H as HauptFenster
    participant OS as Windows / Setup

    N->>V: „Version …“
    V->>T: _neueste_version_pruefen (Zeitgrenze)
    T->>GH: releases/latest
    GH-->>T: Version
    T-->>V: über _UpdateBote (Signal)
    V-->>N: aktuell / neue Version mit Link / Fehler im Klartext

    OS->>H: commitDataRequest (Abmelden, Setup)
    H->>H: _sitzungsende_pruefen
    alt ungespeicherte Ergebnisse
        H->>H: ErgebnisTab.alle_speichern (ohne erlaubte Interaktion: keine Meldung, Gründe ins Absturzprotokoll)
    end
    alt Reste ungespeichert, keine Rückfrage erlaubt
        H-->>OS: manager.cancel() (Beenden abgelehnt)
    else Reste ungespeichert, Rückfrage erlaubt
        H->>H: _ja_nein „trotzdem beenden?“
        H-->>OS: Nein: manager.cancel(), Ja: Beenden erlaubt
    else alles gespeichert
        H-->>OS: Beenden erlaubt
    end
    Note over H,OS: Wird ein erlaubtes Beenden doch abgebrochen, nimmt SitzungsendeFilter die Freigabe zurück
```

---

## 13. Demoprüfung

`DemoTour` spielt mit erfundenen Daten (`demo_daten.py`) einen Prüfungstag in einem eigenen
Temp-Ordner vor; der echte Termin bleibt unberührt.

```mermaid
stateDiagram-v2
    [*] --> Vorbereiten : „Demoprüfung“
    Vorbereiten : eigener Temp-Ordner,<br/>vorheriger Termin gemerkt
    Vorbereiten --> Schritt
    state Schritt {
        [*] --> Erklaeren : DemoPanel zeigt Text
        Erklaeren --> Vorfuehren : Aktionen nacheinander<br/>(DemoMarkierung rahmt das Element)
        Vorfuehren --> Warten : Schritt fertig
        Warten --> [*] : „Weiter“ oder automatisch nach Countdown
    }
    Schritt --> Schritt : nächster Schritt
    note right of Schritt
        Willkommen, dann 15 Schritte:
        1 Termin anlegen, 2 gespeichert, 3–4 Teilnehmer,
        5 Startnummern, 6 Bezahlt, 7 Zeitplan,
        8 Ergebnisse, 9 Disqualifikation, 10 Speichern,
        11 Auswertung, 12 Stechen, 13 Ergebnisliste als PDF,
        14 Richter am Tablet, 15 Demo-Termin löschen
    end note
    Schritt --> Fehler : DemoFehler
    Fehler --> Aufraeumen
    Schritt --> Aufraeumen : „Beenden“ / „Fertig“
    Aufraeumen : vorherigen Termin wiederherstellen,<br/>Temp-Ordner löschen
    Aufraeumen --> [*]
```
