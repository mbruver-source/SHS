"""
PostgreSQL-Termine und Benutzerkonten der Web-Version.

Aus db.py ausgelagert (11.11.2026, Schichtenaufteilung); db.py bleibt als Fassade und reicht alle
Namen weiter. Code unverändert. Siehe Architektur.md.
"""

from __future__ import annotations
import datetime
import hashlib
import re
import secrets
from dataclasses import dataclass

from db_verbindung import (
    _migriere_ergebnisse_spalten,
    _migriere_teilnehmer_spalten,
    _migriere_veranstaltung_spalten,
    _migriere_zeitplan_spalten,
    _PostgresConnection,
    _richte_schema_im_aktuellen_suchpfad_ein,
    _vorhandene_spalten,
)


# --- Terminverwaltung für PostgreSQL (mehrere Termine in EINER gemeinsamen Datenbank) --
#
# Pendant zum Terminübersicht-Abschnitt oben, für die geplante Podman/Web-Version mit
# Mehrbenutzerzugriff (siehe Grobkonzept/Fortschritt.md). Bei der SQLite-Desktop-Version
# entspricht ein Termin einer eigenen Datei - "alle Termine auflisten" heißt dort einfach
# "den Ordner auflisten" (liste_termine()), und "einen Termin löschen" heißt "die Datei
# löschen". Auf einem gemeinsam genutzten PostgreSQL-Server, auf den mehrere Nutzer
# gleichzeitig zugreifen, gibt es aber keine "Dateien" - stattdessen bekommt jeder Termin
# ein eigenes PostgreSQL-SCHEMA (ein Namensraum für Tabellen innerhalb einer Datenbank,
# z. B. "termin_17"), das dieselben Tabellen enthält wie eine SQLite-Termin-Datei. Das
# bildet dieselbe Isolation und dieselbe gezielte, vollständige Löschbarkeit nach, die im
# Grobkonzept aus Datenschutzgründen ausdrücklich gefordert ist (DROP SCHEMA ... CASCADE
# entspricht dabei dem Löschen einer Datei) - und der entscheidende Vorteil: alle ~40
# Datenfunktionen weiter oben in diesem Modul (add_teilnehmer, eintragen_ergebnis, ...)
# brauchen dafür KEINE Änderung. Welcher Termin gemeint ist, wird eine Ebene darüber
# entschieden, indem der search_path der Verbindung auf das passende Schema gesetzt wird
# (oeffne_termin_postgres()) - danach arbeiten alle übrigen Funktionen ganz normal auf
# `conn` weiter, exakt wie bei einer geöffneten SQLite-Termin-Datei.
#
# Eine schlanke "Registry"-Tabelle (im PostgreSQL-Standard-Schema "public", also
# außerhalb jedes einzelnen Termin-Schemas) führt Buch darüber, welche Schema-Namen zu
# welchem Termin gehören - das Pendant zum "Ordner mit *.sqlite-Dateien" der
# Desktop-Version. Absichtlich SCHLANK gehalten (nur id/schema_name/erstellt_am, keine
# Kopie von Verein/Ort/Datum): liste_termine_postgres() liest diese Angaben stattdessen
# direkt aus der "veranstaltung"-Tabelle jedes einzelnen Termin-Schemas, genau wie
# liste_termine() bei SQLite jede Datei kurz öffnet - so gibt es nur EINE Quelle der
# Wahrheit statt zwei, die auseinanderlaufen könnten.
#
# Bewusst NICHT Teil dieses Moduls: eine Auswertung ÜBER mehrere Termine hinweg (auf
# ausdrücklichen Wunsch nicht benötigt, siehe Chatverlauf) - jedes Schema bleibt
# vollständig eigenständig, wie bisher jede Termin-Datei.

# fullmatch statt match mit "^...$" (Codeprüfung 22.09., G7): Pythons "$" passt auch vor
# einem abschließenden "\n" - "termin_5\n" war damit ein "gültiger" Name, DROP SCHEMA
# gelang, das DELETE aus termin_registry traf aber 0 Zeilen (verwaister Registry-Eintrag).
_SCHEMA_NAME_MUSTER = re.compile(r"termin_[0-9]+")

def _pruefe_schema_name(schema_name: str) -> None:
    """Stellt sicher, dass `schema_name` dem erwarteten Muster ('termin_<Zahl>')
    entspricht, BEVOR er in einen SQL-Text eingesetzt wird (CREATE/DROP SCHEMA und SET
    search_path erlauben - anders als normale Werte - keine parametrisierten Platzhalter
    für Bezeichner). In der Praxis wird `schema_name` in diesem Modul ausschließlich
    intern aus der Registry-ID erzeugt (nie aus direkter Nutzereingabe übernommen) - diese
    Prüfung ist die zusätzliche Absicherung dagegen, falls sich das einmal ändert."""
    if not _SCHEMA_NAME_MUSTER.fullmatch(schema_name):
        raise ValueError(f"Ungültiger Schema-Name: {schema_name!r}")

def _setze_termin_suchpfad(conn, schema_name: str) -> None:
    """Wechselt die Verbindung auf das angegebene Schema ('public' für die
    Registry-Tabelle, sonst ein Termin-Schema) - siehe Abschnitts-Kommentar oben."""
    if schema_name != "public":
        _pruefe_schema_name(schema_name)
    conn.execute(f"SET search_path TO {schema_name}")

@dataclass
class TerminInfoPostgres:
    """Eintrag für die Terminübersicht der PostgreSQL/Web-Version - das Pendant zu
    TerminInfo (SQLite) oben, ohne die dort dateibezogenen Felder (pfad/dateiname/
    lesbar), dafür mit der registrierten ID und dem Schema-Namen. Der Login läuft nicht
    mehr über einen Zugangscode je Termin (siehe Abschnitt "Benutzerkonten der
    Web-Version" weiter unten) - diese Klasse trägt deshalb keinen Zugangscode mehr."""
    id: int
    schema_name: str
    verein: str | None
    ort: str | None
    datum: str | None
    anzahl_teilnehmer: int
    erstellt_am: object  # datetime, vom psycopg2-Treiber geliefert

# --- Benutzerkonten der Web-Version (Login) -----------------------------------------
#
# Ursprünglich (V1) meldeten sich alle Richter/Helfer über einen einzigen, gemeinsamen
# sechsstelligen Zugangscode je Termin an (siehe _eindeutigen_zugangscode_erzeugen/
# pruefe_zugangscode_postgres in einer früheren Fassung dieser Datei - inzwischen
# entfernt). Auf ausdrücklichen Wunsch abgelöst durch echte, GLOBALE (nicht mehr an
# einen einzelnen Termin gebundene) Benutzerkonten mit Benutzername/Passwort:
#
#   - Beim allerersten Start (noch kein Konto vorhanden) richtet der Administrator sich
#     selbst mit einem frei gewählten Benutzernamen/Passwort ein (siehe gibt_es_admin/
#     admin_einrichten) - "Ersteinrichtung" in app_web.py.
#   - Danach kann der Administrator weitere Konten für Helfer/Richter anlegen
#     (benutzer_anlegen), die nur Ergebnisse eintragen dürfen (KEINE Benutzerverwaltung,
#     kein Löschen von Terminen o.ä.) - siehe app_web.py, Entscheidung "Admin + Eintragen"
#     (genau zwei Rollen, keine feinere Rechtevergabe).
#   - Weil Konten jetzt GLOBAL sind (nicht mehr an einen Termin gebunden wie vorher der
#     Zugangscode), muss nach dem Login zusätzlich ausgewählt werden, mit welchem gerade
#     veröffentlichten Termin weitergearbeitet werden soll (siehe app_web.py,
#     "/termin-waehlen" - wird übersprungen, wenn genau ein Termin offen ist).
#
# termin_registry.zugangscode (siehe verbinde_postgres_server) bleibt als Spalte
# bestehen (bereits veröffentlichte Registry-Einträge behalten ihren alten Wert), wird
# von diesem Modul aber nirgends mehr gelesen oder neu befüllt - reine Historie.
#
# Passwörter werden NIE im Klartext gespeichert, sondern über werkzeug.security
# (ohnehin schon eine Abhängigkeit von Flask, siehe requirements-web.txt) gehasht -
# keine zusätzliche pip-Abhängigkeit nötig.
_WEB_BENUTZER_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS public.web_benutzer ("
    "benutzername TEXT PRIMARY KEY, "
    "passwort_hash TEXT NOT NULL, "
    "ist_admin INTEGER NOT NULL DEFAULT 0 CHECK (ist_admin IN (0, 1)), "
    "erstellt_am TEXT NOT NULL)"
)

# QS-Fund (19./20.09.): web_benutzer.benutzername ist zwar PRIMARY KEY (schützt also vor
# exakt gleich geschriebenen Namen), pruefe_login() vergleicht beim Anmelden aber GROSS-/
# kleinschreibungs-UNABHÄNGIG (LOWER(benutzername), siehe dortiger Kommentar) - damit
# z. B. Mobilgeräte mit Autokapitalisierung nicht an der Schreibweise scheitern. Ohne
# diesen zusätzlichen, ebenfalls gross-/kleinschreibungsunabhängigen Unique-Index könnten
# zwei Konten wie "MHelfer" und "mhelfer" gleichzeitig angelegt werden - app_web.py prüft
# das zwar bereits VOR dem Anlegen (separate Python-Abfrage in admin_benutzer()), aber
# zwischen dieser Prüfung und dem eigentlichen INSERT bleibt ein kurzes Zeitfenster für
# einen echten Wettlauf zweier gleichzeitiger Anfragen - ganz analog zur
# Admin-Lösch-Race-Condition in benutzer_loeschen() weiter unten. Welches der beiden
# Konten sich dann beim Login durchsetzt, wäre von der SQL-Sortierung abhängig und für
# den Nutzer nicht nachvollziehbar. "CREATE UNIQUE INDEX ... ON (LOWER(...))" ist sowohl
# unter PostgreSQL als auch unter SQLite (ab 3.9, Ausdrucks-Indizes) identisch gültige
# Syntax - deshalb hier, wie schon bei _WEB_BENUTZER_SCHEMA, EINE gemeinsame Anweisung für
# beide Datenbanken statt einer Übersetzung je Datenbanktyp. IF NOT EXISTS sorgt dafür,
# dass auch bereits produktiv angelegte Datenbanken (ohne diesen Index) ihn beim nächsten
# verbinde_postgres_server()-Aufruf automatisch nachgerüstet bekommen.
_WEB_BENUTZER_INDEX_BENUTZERNAME_LOWER = (
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_web_benutzer_benutzername_lower "
    "ON web_benutzer (LOWER(benutzername))"
)

def _jetzt_iso() -> str:
    """ISO-8601-Zeitstempel (UTC) für web_benutzer.erstellt_am - bewusst als TEXT von
    Python aus gesetzt statt per DEFAULT now()/CURRENT_TIMESTAMP in der Tabellendefinition
    (die zwischen SQLite und PostgreSQL nicht identisch geschrieben werden), damit
    _WEB_BENUTZER_SCHEMA unverändert gegen beide Datenbanken läuft - genau wie SCHEMA/
    SCHEMA_POSTGRES weiter oben, nur ohne den Umweg über eine .replace()-Übersetzung."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def gibt_es_admin(conn) -> bool:
    """Liefert True, sobald mindestens ein Administrator-Konto existiert - Grundlage
    dafür, ob app_web.py beim Aufruf von '/' die einmalige Ersteinrichtung oder den
    normalen Login zeigt."""
    _setze_termin_suchpfad(conn, "public")
    treffer = conn.execute(
        "SELECT 1 AS vorhanden FROM web_benutzer WHERE ist_admin = 1 LIMIT 1"
    ).fetchone()
    return treffer is not None

def admin_einrichten(conn, benutzername: str, passwort: str) -> bool:
    """Richtet den ERSTEN Administrator ein (einmalige Ersteinrichtung, siehe
    gibt_es_admin) - lehnt ab (liefert False, legt nichts an), falls in der Zwischenzeit
    bereits ein Administrator existiert (z. B. zwei gleichzeitig geöffnete
    Ersteinrichtungs-Formulare), damit nie unbemerkt ein zweiter "erster" Admin
    entsteht."""
    _setze_termin_suchpfad(conn, "public")
    if gibt_es_admin(conn):
        return False
    benutzer_anlegen(conn, benutzername, passwort, ist_admin=True)
    return True

def benutzer_anlegen(conn, benutzername: str, passwort: str, ist_admin: bool = False) -> None:
    """Legt ein neues Web-Benutzerkonto an (vom Administrator über '/admin/benutzer',
    siehe app_web.py) - Benutzername muss eindeutig sein (Primärschlüssel der Tabelle,
    siehe _WEB_BENUTZER_SCHEMA, PLUS der zusätzliche Unique-Index auf LOWER(benutzername),
    siehe _WEB_BENUTZER_INDEX_BENUTZERNAME_LOWER - schützt auch vor einer Schreibweise,
    die sich nur in Groß-/Kleinschreibung von einem vorhandenen Konto unterscheidet), sonst
    wirft dies denselben IntegrityError wie jede andere doppelt vergebene eindeutige Spalte
    in diesem Modul. app_web.admin_benutzer() prüft das zwar schon vorher explizit, damit
    der Admin sofort eine verständliche Fehlermeldung sieht - dieser Unique-Index ist die
    zusätzliche, race-sichere Absicherung auf Datenbankebene für den seltenen Fall zweier
    gleichzeitiger Anfragen (siehe dortiger Kommentar).

    Importiert werkzeug.security bewusst erst hier statt am Modulanfang - genau wie
    psycopg2 in verbinde_postgres_server() weiter oben: werkzeug ist nur eine
    Abhängigkeit des Web-Servers (Flask zieht es mit, siehe requirements-web.txt), die
    Desktop-Version (requirements.txt) soll sie nicht mitinstallieren müssen, obwohl sie
    dasselbe db.py-Modul importiert."""
    from werkzeug.security import generate_password_hash

    _setze_termin_suchpfad(conn, "public")
    conn.execute(
        "INSERT INTO web_benutzer (benutzername, passwort_hash, ist_admin, erstellt_am) "
        "VALUES (?, ?, ?, ?)",
        (benutzername.strip(), generate_password_hash(passwort), 1 if ist_admin else 0, _jetzt_iso()),
    )
    conn.commit()

def benutzer_loeschen(conn, benutzername: str) -> None:
    """Löscht ein Web-Benutzerkonto. Verhindert dabei, dass der LETZTE verbleibende
    Administrator gelöscht wird (sonst gäbe es niemanden mehr, der neue Konten anlegen
    oder die Ersteinrichtung erneut durchlaufen könnte, ohne direkt in der Datenbank zu
    hantieren) - wirft in diesem Fall ValueError, ganz analog zur Schema-Namen-Prüfung
    in _pruefe_schema_name weiter oben.

    Sperrt bei PostgreSQL vor dem Zählen ALLE Admin-Zeilen (SELECT ... FOR UPDATE) - ohne
    das könnten zwei gleichzeitige Löschversuche (z. B. zwei Administratoren, die im
    selben Moment je ihr eigenes Konto löschen) beide unabhängig "es gibt noch 2 Admins"
    sehen, bevor einer committet, und am Ende gemeinsam 0 statt mindestens 1
    Administrator übrig lassen - eine sperrfreie COUNT(*)-Prüfung allein reicht dafür
    NICHT, da ein reiner lesender Zugriff unter PostgreSQLs Standard-Isolationsstufe
    (READ COMMITTED) keine anderen Transaktionen blockiert (QS-Review 19./20.09.). Für
    SQLite (nur in Tests relevant - web_benutzer existiert produktiv ausschließlich in
    der PostgreSQL-Variante, siehe verbinde_postgres_server) gibt es kein FOR UPDATE und
    keine echte Nebenläufigkeit auf derselben Verbindung. Bewusst POSITIV auf
    _PostgresConnection geprüft statt negativ auf sqlite3.Connection (wie in
    _vorhandene_spalten() weiter oben) - test_app_web.py lässt db.verbinde_postgres_server
    für seine SQLite-Testdatei durch einen eigenen, NICHT-sqlite3.Connection-Test-Wrapper
    (_NichtSchliessendeVerbindung) ersetzen, der aber ebenfalls kein FOR UPDATE kann."""
    _setze_termin_suchpfad(conn, "public")
    zeile = conn.execute(
        "SELECT ist_admin FROM web_benutzer WHERE benutzername = ?", (benutzername,)
    ).fetchone()
    if zeile is None:
        return
    if zeile["ist_admin"]:
        if isinstance(conn, _PostgresConnection):
            conn.execute("SELECT benutzername FROM web_benutzer WHERE ist_admin = 1 FOR UPDATE")
        anzahl_admins = conn.execute(
            "SELECT COUNT(*) AS anzahl FROM web_benutzer WHERE ist_admin = 1"
        ).fetchone()["anzahl"]
        if anzahl_admins <= 1:
            raise ValueError("Der letzte verbleibende Administrator kann nicht gelöscht werden.")
    conn.execute("DELETE FROM web_benutzer WHERE benutzername = ?", (benutzername,))
    conn.commit()

def liste_benutzer(conn) -> list[dict]:
    """Für die Benutzerverwaltung ('/admin/benutzer', nur für Administratoren
    sichtbar) - alphabetisch nach Benutzername, OHNE die Passwort-Hashes (die Ansicht
    braucht sie nicht, unnötig sensible Daten unnötig weiterzureichen)."""
    _setze_termin_suchpfad(conn, "public")
    zeilen = conn.execute(
        "SELECT benutzername, ist_admin, erstellt_am FROM web_benutzer ORDER BY benutzername"
    ).fetchall()
    return [
        {"benutzername": z["benutzername"], "ist_admin": bool(z["ist_admin"]), "erstellt_am": z["erstellt_am"]}
        for z in zeilen
    ]

def benutzer_stand(conn, benutzername: str) -> dict | None:
    """Liefert den AKTUELLEN Stand eines Web-Benutzerkontos ({"benutzername": ...,
    "ist_admin": bool}) oder None, falls das Konto nicht (mehr) existiert - anders als
    pruefe_login() OHNE Passwort-Prüfung, dient also nicht dem Login selbst, sondern der
    Re-Validierung einer bereits bestehenden Session (siehe
    app_web._aktueller_benutzer_oder_redirect()).

    QS-Fund (21.09.): _login_erforderlich/_admin_erforderlich/_termin_erforderlich in
    app_web.py prüften bisher nur den in der (signierten, aber sonst ungeprüften)
    Session hinterlegten Stand - löschte ein Administrator währenddessen das Konto eines
    anderen angemeldeten Nutzers, blieb dessen Session bis zum Abmelden/Sitzungsablauf
    voll nutzbar, ggf. sogar mit Admin-Rechten. Jede Anfrage re-validiert deshalb jetzt
    gegen diese Funktion.

    Analog zu liste_benutzer()/pruefe_login() implementiert (LOWER()-Vergleich wie beim
    Login, _setze_termin_suchpfad(conn, "public") nicht vergessen - web_benutzer liegt
    immer im "public"-Schema, unabhängig davon, auf welches Termin-Schema die Verbindung
    zuvor ggf. gewechselt war)."""
    _setze_termin_suchpfad(conn, "public")
    zeile = conn.execute(
        "SELECT benutzername, ist_admin, passwort_hash, erstellt_am FROM web_benutzer "
        "WHERE LOWER(benutzername) = LOWER(?)",
        (benutzername.strip(),),
    ).fetchone()
    if zeile is None:
        return None
    return {"benutzername": zeile["benutzername"], "ist_admin": bool(zeile["ist_admin"]),
            "kennung": _konto_kennung(zeile)}

def _konto_kennung(zeile) -> str:
    """Sicherheitsprüfung 03.10.2026, C-1: Fingerabdruck EINES konkreten Kontos für die
    Session. Der Benutzername allein reichte nicht - wurde ein Konto gelöscht und unter
    demselben Namen neu angelegt (ggf. als Administrator), übernahm ein altes Cookie dessen
    Rechte. Erstellzeit und (zufällig gesalzener) Passwort-Hash ändern sich bei jeder
    Neuanlage und bei jedem Passwortwechsel; gespeichert wird nur dieser Hash-Wert, nicht
    der Passwort-Hash selbst."""
    roh = f"{zeile['benutzername'].lower()}|{zeile['erstellt_am']}|{zeile['passwort_hash']}"
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()[:32]

# Dummy-Passwort-Hash für den Timing-Seitenkanal-Schutz in pruefe_login() unten - EINMALIG
# lazy (beim ersten pruefe_login()-Aufruf, nicht bei jedem einzelnen) berechnet und dann
# wiederverwendet, nicht bereits hier auf Modulebene: werkzeug.security wird in diesem
# Modul bewusst erst innerhalb der jeweiligen Funktion importiert (siehe Begründung in
# benutzer_anlegen()), damit die Desktop-Version (die dieses Modul ebenfalls importiert,
# aber kein Flask/werkzeug installiert hat) nicht plötzlich davon abhängt. Der zufällige
# Klartext dahinter spielt keine Rolle - es wird nie ein echtes Passwort damit verglichen,
# nur die Rechenzeit von check_password_hash() an den "bekannter Benutzername"-Fall
# angeglichen (siehe pruefe_login()).
_DUMMY_PASSWORT_HASH: str | None = None

def pruefe_login(conn, benutzername: str, passwort: str) -> dict | None:
    """Prüft Benutzername/Passwort gegen web_benutzer und liefert bei Erfolg
    {"benutzername": ..., "ist_admin": bool}, sonst None - Grundlage für den Login in
    app_web.py. Absichtlich IMMER derselbe Rückgabeweg bei unbekanntem Benutzernamen wie
    bei falschem Passwort (kein 'Benutzer nicht gefunden' vs. 'Passwort falsch'), damit
    sich über die Fehlermeldung keine vorhandenen Benutzernamen erraten lassen. Importiert
    werkzeug.security bewusst erst hier - siehe Begründung in benutzer_anlegen().

    QS-Fund (21.09.): bei unbekanntem Benutzernamen wurde check_password_hash() (teures
    PBKDF2) bisher gar nicht erst aufgerufen, bei bekanntem Benutzernamen (falsches
    Passwort) dagegen schon - die Antwortzeit unterschied sich dadurch messbar und hätte
    sich zum Erraten gültiger Benutzernamen ausnutzen lassen (Timing-Seitenkanal). Deshalb
    jetzt IMMER genau ein check_password_hash()-Aufruf, bei unbekanntem Benutzernamen
    gegen den oben einmalig erzeugten Dummy-Hash - dessen Ergebnis wird verworfen (führt
    ohnehin zu None über den zeile-is-None-Zweig), nur die Rechenzeit soll angeglichen
    werden.

    Der Vergleich läuft über LOWER() auf beiden Seiten, GROSS-/Kleinschreibung beim
    Benutzernamen spielt also keine Rolle (Passwörter bleiben dagegen wie gespeichert
    GROSS-/kleinschreibungsempfindlich) - ohne das würden z. B. Mobilgeräte, die den
    ersten Buchstaben eines Textfelds automatisch groß schreiben ("Autokapitalisierung"),
    beim Anmelden leicht einen ansonsten korrekten Benutzernamen ablehnen, nur weil er beim
    Anlegen des Kontos anders geschrieben wurde als beim späteren Anmelden."""
    from werkzeug.security import check_password_hash, generate_password_hash

    global _DUMMY_PASSWORT_HASH
    if _DUMMY_PASSWORT_HASH is None:
        _DUMMY_PASSWORT_HASH = generate_password_hash(secrets.token_hex(32))

    _setze_termin_suchpfad(conn, "public")
    zeile = conn.execute(
        "SELECT benutzername, passwort_hash, ist_admin, erstellt_am FROM web_benutzer "
        "WHERE LOWER(benutzername) = LOWER(?)",
        (benutzername.strip(),),
    ).fetchone()
    if zeile is None:
        check_password_hash(_DUMMY_PASSWORT_HASH, passwort)  # Ergebnis verworfen, siehe Docstring oben
        return None
    if not check_password_hash(zeile["passwort_hash"], passwort):
        return None
    return {"benutzername": zeile["benutzername"], "ist_admin": bool(zeile["ist_admin"]),
            "kennung": _konto_kennung(zeile)}

def verbinde_postgres_server(dsn: str, password: str | None = None) -> _PostgresConnection:
    """Öffnet eine Verbindung zum gemeinsam genutzten PostgreSQL-Server für die
    Terminverwaltung (anlegen/auflisten/öffnen/löschen, siehe die Funktionen unten) - das
    Pendant zum Anzeigen der Terminübersicht beim Programmstart der Desktop-Version
    (termine_ordner()/liste_termine()). Legt bei Bedarf die Registry-Tabelle sowie die
    Benutzerverwaltung (siehe Abschnitt "Benutzerkonten der Web-Version" weiter unten) an.

    Importiert psycopg2 bewusst erst hier statt am Modulanfang - siehe init_db_postgres()
    weiter oben für die Begründung.

    dsn: vollständiger PostgreSQL-Verbindungsstring (ohne Bezug zu einem bestimmten
    Termin - die Datenbank selbst wird von allen Terminen gemeinsam genutzt, siehe
    Abschnitts-Kommentar oben), z. B. "postgresql://benutzer:passwort@host:5432/shs".
    password: optional getrennt übergebenes Passwort (Sicherheitshinweis H-3, Secret-Datei
    statt Passwort im DSN, siehe app_web.geheimnis_lesen). psycopg2 führt es mit dem DSN
    zusammen; Sonderzeichen müssen dann nicht URL-kodiert werden.
    """
    import psycopg2
    import psycopg2.extras

    extra = {"password": password} if password else {}
    roh_verbindung = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor, **extra)
    conn = _PostgresConnection(roh_verbindung)
    # Die Einrichtung (Registry-Tabelle, nachgerüstete Spalte, Benutzertabelle samt Index)
    # läuft nur noch, wenn im Systemkatalog tatsächlich etwas fehlt - also praktisch nur
    # beim allerersten Start gegen eine neue Datenbank. Vorher lief sie bei JEDER
    # Verbindung (= jeder Web-Anfrage): "ALTER TABLE ... ADD COLUMN IF NOT EXISTS" braucht
    # aber auch dann eine exklusive Sperre auf termin_registry, wenn die Spalte längst
    # existiert, und "CREATE INDEX IF NOT EXISTS" eine Sperre, die mit laufenden
    # Schreibzugriffen auf web_benutzer kollidiert - eine andere, noch offene Transaktion
    # ließ den Verbindungsaufbau dadurch unbegrenzt warten (Befund aus der Codex-
    # Architekturprüfung vom 27.09.2026, siehe Fortschritt.md). Die reine Katalogabfrage
    # braucht keine Tabellensperren.
    stand = conn.execute(
        "SELECT to_regclass('public.termin_registry') IS NOT NULL AS registry, "
        "EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' "
        "AND table_name = 'termin_registry' AND column_name = 'zugangscode') AS zugangscode, "
        "to_regclass('public.web_benutzer') IS NOT NULL AS benutzer, "
        "to_regclass('public.ix_web_benutzer_benutzername_lower') IS NOT NULL AS benutzer_index"
    ).fetchone()
    if not stand["registry"]:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS public.termin_registry ("
            "id INTEGER PRIMARY KEY, schema_name TEXT NOT NULL UNIQUE, "
            "zugangscode TEXT, "
            "erstellt_am TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
    elif not stand["zugangscode"]:
        # Bereits vor der Zugangscode-Einführung angelegte Registry-Tabellen bekommen die
        # Spalte hier nachgerüstet - dasselbe Prinzip wie _migriere_veranstaltung_spalten()
        # für einzelne Termine, hier aber genügt eine einzelne feste ALTER-Anweisung, da es
        # nur um eine einzige, unabhängige Spalte ohne Constraints geht.
        conn.execute("ALTER TABLE public.termin_registry ADD COLUMN IF NOT EXISTS zugangscode TEXT")
    if not stand["benutzer"]:
        conn.execute(_WEB_BENUTZER_SCHEMA)
    if not stand["benutzer_index"]:
        conn.execute(_WEB_BENUTZER_INDEX_BENUTZERNAME_LOWER)
    conn.commit()
    return conn

def erstelle_termin_postgres(conn) -> TerminInfoPostgres:
    """Legt einen neuen, leeren Termin als eigenes PostgreSQL-Schema an (Postgres-Pendant
    zu einer neuen, leeren Termin-Datei bei der SQLite-Desktop-Version) - Isolation und
    spätere gezielte Löschbarkeit bleiben dadurch erhalten (siehe loesche_termin_postgres
    unten). Enthält danach dieselben (leeren) Tabellen wie init_db()/init_db_postgres().
    Verein/Ort/Datum werden anschließend ganz normal über set_veranstaltung() gesetzt,
    NACHDEM mit oeffne_termin_postgres() auf das neue Schema gewechselt wurde (hier noch
    None, wie bei einer frisch angelegten SQLite-Termin-Datei vor dem ersten Ausfüllen).

    Die Schema-ID kommt aus einer eigenen Sequenz statt aus der Registry-Tabelle selbst
    (die 'id' dort könnte sonst erst NACH dem Einfügen der Zeile bekannt sein, obwohl der
    Schema-Name - der ja von der ID abhängt - schon beim Einfügen gebraucht wird). Eine
    Sequenz vergibt zudem nie zweimal denselben Wert, auch nicht nach einem Löschen - ein
    neuer Termin bekommt also nie versehentlich den Schema-Namen eines zuvor gelöschten.

    Bekommt KEINEN Zugangscode mehr zugewiesen - der Login läuft über die globalen
    Benutzerkonten (siehe Abschnitt "Benutzerkonten der Web-Version" weiter oben); nach
    dem Login wird der Termin stattdessen über '/termin-waehlen' in app_web.py
    ausgewählt."""
    _setze_termin_suchpfad(conn, "public")
    conn.execute("CREATE SEQUENCE IF NOT EXISTS termin_registry_id_seq")
    neue_id = conn.execute("SELECT nextval('termin_registry_id_seq') AS id").fetchone()["id"]
    schema_name = f"termin_{neue_id}"
    conn.execute(
        "INSERT INTO termin_registry (id, schema_name) VALUES (?, ?)",
        (neue_id, schema_name),
    )
    conn.execute(f"CREATE SCHEMA {schema_name}")
    _setze_termin_suchpfad(conn, schema_name)
    _richte_schema_im_aktuellen_suchpfad_ein(conn)
    zeile = conn.execute(
        "SELECT erstellt_am FROM public.termin_registry WHERE id = ?", (neue_id,)
    ).fetchone()
    _setze_termin_suchpfad(conn, "public")
    return TerminInfoPostgres(
        id=neue_id, schema_name=schema_name, verein=None, ort=None, datum=None,
        anzahl_teilnehmer=0, erstellt_am=zeile["erstellt_am"],
    )

def oeffne_termin_postgres(conn, schema_name: str) -> None:
    """Wechselt die Verbindung auf das Schema eines bestehenden Termins (Postgres-Pendant
    zum Öffnen einer Termin-Datei bei der SQLite-Desktop-Version) und führt dabei - genau
    wie init_db()/init_db_postgres() - die Migrationen erneut aus, damit auch ein älterer
    Termin automatisch auf den aktuellen Stand gebracht wird. Alle übrigen Funktionen in
    diesem Modul (add_teilnehmer, eintragen_ergebnis, berechne_auswertung, ...) arbeiten
    danach ganz normal auf `conn` weiter - bis zum nächsten Wechsel (ein erneuter Aufruf
    hier, oder _setze_termin_suchpfad(conn, "public") für die Registry-Funktionen)."""
    _setze_termin_suchpfad(conn, schema_name)
    _migriere_veranstaltung_spalten(conn)
    _migriere_teilnehmer_spalten(conn)
    _migriere_ergebnisse_spalten(conn)
    _migriere_zeitplan_spalten(conn)

def liste_termine_postgres(conn) -> list[TerminInfoPostgres]:
    """Postgres-Pendant zu liste_termine() (SQLite) - ein Registry-Eintrag entspricht
    dabei einer Datei im Termine-Ordner. Für jeden registrierten Termin wird kurz auf
    dessen Schema gewechselt, um Verein/Ort/Datum/Teilnehmerzahl zu lesen - genau die
    gleiche Vorgehensweise wie bei liste_termine(), das jede Datei kurz öffnet. Neueste
    zuerst (nach Datum, wie liste_termine())."""
    _setze_termin_suchpfad(conn, "public")
    eintraege = conn.execute(
        "SELECT id, schema_name, erstellt_am FROM termin_registry ORDER BY erstellt_am"
    ).fetchall()
    ergebnisse: list[TerminInfoPostgres] = []
    for eintrag in eintraege:
        schema_name = eintrag["schema_name"]
        _setze_termin_suchpfad(conn, schema_name)
        v = conn.execute("SELECT * FROM veranstaltung WHERE id = 1").fetchone()
        # UX-Test 2026-11, T14: nur Teilnehmende wie am Desktop (TerminInfo.teilnehmend). Der
        # Web-Export überträgt „keine Teilnahme“ ohnehin nicht, gezählt wird trotzdem ausdrücklich.
        # Ein seit dem 02.10.2026 nie geöffnetes Schema hat die Spalte noch nicht (migriert wird
        # erst in oeffne_termin_postgres) - dann wie bisher alle (Verifikation B7).
        bedingung = (" WHERE COALESCE(keine_teilnahme, 0) = 0"
                     if "keine_teilnahme" in _vorhandene_spalten(conn, "teilnehmer") else "")
        anzahl = conn.execute(f"SELECT COUNT(*) AS anzahl FROM teilnehmer{bedingung}").fetchone()["anzahl"]
        ergebnisse.append(TerminInfoPostgres(
            id=eintrag["id"], schema_name=schema_name,
            verein=v["verein"] if v else None, ort=v["ort"] if v else None,
            datum=v["datum"] if v else None, anzahl_teilnehmer=anzahl,
            erstellt_am=eintrag["erstellt_am"],
        ))
    _setze_termin_suchpfad(conn, "public")
    ergebnisse.sort(key=lambda t: (t.datum or "", t.schema_name), reverse=True)
    return ergebnisse

def loesche_termin_postgres(conn, schema_name: str) -> None:
    """Löscht einen Termin vollständig und gezielt (Postgres-Pendant zum Löschen einer
    Termin-Datei bei der SQLite-Desktop-Version - siehe Grobkonzept: aus
    Datenschutzgründen ausdrücklich geforderte, gezielte Löschmöglichkeit, ohne andere
    Termine zu berühren). DROP SCHEMA ... CASCADE entfernt dabei alle Tabellen/Daten
    dieses einen Termins auf einen Schlag."""
    _pruefe_schema_name(schema_name)
    _setze_termin_suchpfad(conn, "public")
    conn.execute(f"DROP SCHEMA {schema_name} CASCADE")
    conn.execute("DELETE FROM termin_registry WHERE schema_name = ?", (schema_name,))
    conn.commit()
