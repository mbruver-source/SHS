"""
Desktop-Client für die Web-Version (Marco 18.11.2026): Termin ins Web veröffentlichen und
Ergebnisse von dort holen. Reine Netzwerk-Schicht ohne Qt (gut testbar), nur Standardbibliothek.

Sicherheit:
- Nur HTTPS. http://-Adressen werden mit klarer Meldung abgelehnt, Zugangsdaten und Daten
  gehen nie unverschlüsselt hinaus.
- Zertifikat-Pinning statt Zertifikatskette: der Server nutzt ein langlebiges selbstsigniertes
  Zertifikat. Die Verbindung wird ohne Kettenprüfung aufgebaut (CERT_NONE), aber DIREKT nach dem
  TLS-Handshake und VOR dem ersten gesendeten Byte wird der SHA-256-Fingerabdruck des
  Serverzertifikats mit dem gespeicherten verglichen; bei Abweichung bricht die Verbindung ab
  (ZertifikatFehler), es wurde dann nichts gesendet. Die Erstverbindung holt den Fingerabdruck
  ohne Daten zu senden (hole_fingerabdruck); der Nutzer bestätigt ihn (Trust on first use).
- Passwort und Token stehen in keiner Fehlermeldung.

Server-Schnittstelle: siehe Architektur.md, Abschnitt „API für den Desktop“.
"""

from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import os
import re
import secrets
import socket
import ssl
from urllib.parse import urlsplit

#: Zeitgrenze (Sekunden) für Verbindungsaufbau und je Lese-/Schreibvorgang einer Anfrage.
ZEITGRENZE_SEKUNDEN = 20
#: Hochladen und Antwort auf einen Upload dürfen länger dauern.
ZEITGRENZE_UPLOAD_SEKUNDEN = 120
#: Obergrenzen gegen Speicherüberlauf durch einen fehlerhaften oder falschen Server.
MAX_ANTWORT_BYTES = 32 * 1024 * 1024
MAX_UPLOAD_BYTES = 200 * 1024 * 1024
_MAX_FEHLERTEXT = 300


class WebFehler(Exception):
    """Erwartbarer Fehler der Web-Verbindung; `meldung` ist ein fertiger deutscher Text für den
    Anwender (enthält nie Passwort oder Token)."""

    def __init__(self, meldung: str):
        super().__init__(meldung)
        self.meldung = meldung


class AdressFehler(WebFehler):
    """Die eingegebene Web-Adresse ist ungültig oder nicht HTTPS."""


class ZertifikatFehler(WebFehler):
    """Der Fingerabdruck des Serverzertifikats weicht vom gespeicherten ab. Es wurde nichts gesendet."""

    def __init__(self, meldung: str, erhalten: str | None = None):
        super().__init__(meldung)
        self.erhalten = erhalten


class AnmeldeFehler(WebFehler):
    """Anmeldung abgelehnt (falsche Zugangsdaten, kein Administrator, zu viele Versuche, Token ungültig)."""

    def __init__(self, meldung: str, status: int = 401):
        super().__init__(meldung)
        self.status = status


class ServerFehler(WebFehler):
    """Der Server hat die Anfrage mit einem Fehlerstatus beantwortet (`status`)."""

    def __init__(self, meldung: str, status: int):
        super().__init__(meldung)
        self.status = status


# --- Adresse und Fingerabdruck -------------------------------------------------------------------

def adresse_pruefen(text: str) -> str:
    """Normalisiert die Web-Adresse zu 'https://host[:port]'. Ohne Schema wird https:// ergänzt;
    http:// und andere Schemata werden abgelehnt, ebenso Benutzer/Passwort in der Adresse, Anfrage-
    Teile und Pfade (die API-Pfade hängt das Programm selbst an)."""
    roh = (text or "").strip()
    if not roh:
        raise AdressFehler("Bitte die Adresse des Web-Servers eingeben (z. B. https://shs.example.org).")
    if "://" not in roh:
        roh = "https://" + roh
    try:
        teile = urlsplit(roh)
        port = teile.port
    except ValueError:
        raise AdressFehler("Die Adresse ist ungültig.") from None
    if teile.scheme.lower() != "https":
        raise AdressFehler(
            "Es sind nur Adressen mit https:// erlaubt. Über eine unverschlüsselte Verbindung (http://) "
            "würden Zugangsdaten und Teilnehmerdaten ungeschützt durchs Netz gehen."
        )
    if not teile.hostname:
        raise AdressFehler("Die Adresse ist ungültig (kein Servername).")
    if teile.username is not None or teile.password is not None:
        raise AdressFehler("In der Adresse dürfen kein Benutzername und kein Passwort stehen.")
    if teile.query or teile.fragment or teile.path.strip("/"):
        raise AdressFehler("Bitte nur die Adresse des Servers ohne Pfad angeben (z. B. https://shs.example.org).")
    host = teile.hostname.lower()
    if ":" in host:  # IPv6
        host = f"[{host}]"
    return f"https://{host}" + (f":{port}" if port and port != 443 else "")


_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def fingerabdruck_normalisieren(text: str | None) -> str | None:
    """Wandelt eine Eingabe wie 'AB:CD ...' oder 'abcd...' in 64 Kleinbuchstaben-Hexzeichen um, sonst None."""
    if not text:
        return None
    sauber = re.sub(r"[\s:\-]", "", text).lower()
    return sauber if _HEX64.match(sauber) else None


def fingerabdruck_anzeige(hexwert: str) -> str:
    """Zweierblöcke in Großbuchstaben, 8 Blöcke je Zeile (leichter zu vergleichen, und schmal genug
    für große Schrift): 'AB:CD:...' in vier Zeilen."""
    paare = [hexwert[i:i + 2].upper() for i in range(0, len(hexwert), 2)]
    return "\n".join(":".join(paare[i:i + 8]) for i in range(0, len(paare), 8))


def _fingerabdruck_von(der: bytes) -> str:
    return hashlib.sha256(der).hexdigest()


# --- Verbindung mit Pinning ----------------------------------------------------------------------

def _tls_kontext() -> ssl.SSLContext:
    """Ohne Kettenprüfung (selbstsigniertes Zertifikat) - die Echtheit stellt das Pinning sicher."""
    kontext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    kontext.check_hostname = False
    kontext.verify_mode = ssl.CERT_NONE
    kontext.minimum_version = ssl.TLSVersion.TLSv1_2
    return kontext


class _GepinnteVerbindung(http.client.HTTPSConnection):
    """HTTPS-Verbindung, die nach dem TLS-Handshake und vor jeder Anfrage den Fingerabdruck prüft.
    `erwartet` None: nur den Fingerabdruck merken (Erstverbindung, es wird nichts gesendet)."""

    def __init__(self, host: str, port: int, erwartet: str | None, timeout: float):
        super().__init__(host, port, timeout=timeout, context=_tls_kontext())
        self._erwartet = erwartet
        self.fingerabdruck: str | None = None

    def connect(self) -> None:
        super().connect()  # TCP + TLS-Handshake; gesendet wurde noch nichts
        try:
            der = self.sock.getpeercert(binary_form=True)
        except (ValueError, OSError):
            der = None
        if not der:
            self.close()
            raise ZertifikatFehler("Der Server hat kein Zertifikat vorgelegt. Es wurde nichts gesendet.")
        self.fingerabdruck = _fingerabdruck_von(der)
        if self._erwartet is not None and not hmac.compare_digest(self.fingerabdruck, self._erwartet):
            self.close()
            raise ZertifikatFehler(
                "ACHTUNG: Das Zertifikat des Servers stimmt nicht mit dem gespeicherten Fingerabdruck "
                "überein. Entweder wurde das Zertifikat des Servers erneuert, oder jemand hört die "
                "Verbindung ab. Es wurde NICHTS gesendet (weder Passwort noch Daten). Bitte beim "
                "Betreiber des Servers nachfragen und erst danach in „Web-Verbindung…“ den neuen "
                "Fingerabdruck bestätigen.",
                erhalten=self.fingerabdruck,
            )


def _teile(adresse: str) -> tuple[str, int]:
    teile = urlsplit(adresse)
    return teile.hostname or "", teile.port or 443


def _uebersetze_fehler(exc: BaseException) -> WebFehler:
    """Verständliche Meldung zu einem Verbindungs-/Protokollfehler (Muster wie
    desktop_programm._neueste_version_pruefen). Nie mit Anfrageinhalt."""
    if isinstance(exc, WebFehler):
        return exc
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return WebFehler("Der Server hat nicht rechtzeitig geantwortet. Bitte später erneut versuchen.")
    if isinstance(exc, ssl.SSLError):
        return WebFehler(
            "Die sichere Verbindung (TLS) kam nicht zustande. Ist das die Adresse eines HTTPS-Servers "
            "(richtiger Port)?"
        )
    if isinstance(exc, ConnectionRefusedError):
        return WebFehler("Der Server nimmt keine Verbindung an (läuft er, und stimmt der Port?).")
    if isinstance(exc, socket.gaierror):
        return WebFehler("Der Servername ließ sich nicht finden. Stimmt die Adresse, und gibt es Internet/Netzwerk?")
    if isinstance(exc, (ConnectionError, OSError)):
        return WebFehler("Keine Verbindung zum Server möglich (kein Netzwerk, oder die Verbindung wurde getrennt).")
    if isinstance(exc, (http.client.HTTPException, ValueError)):
        return WebFehler("Die Antwort des Servers konnte nicht gelesen werden (ist das wirklich der SHS-Server?).")
    return WebFehler(f"Unerwarteter Fehler bei der Web-Verbindung ({type(exc).__name__}).")


def hole_fingerabdruck(adresse: str, zeitgrenze: float | None = None) -> str:
    """Erstverbindung (Trust on first use): baut nur die TLS-Verbindung auf, liest den SHA-256-
    Fingerabdruck des Serverzertifikats (64 Hexzeichen, klein) und trennt wieder - ohne etwas zu
    senden. Die Oberfläche zeigt ihn dem Nutzer zur Bestätigung."""
    adresse = adresse_pruefen(adresse)
    host, port = _teile(adresse)
    verbindung = _GepinnteVerbindung(host, port, None, zeitgrenze or ZEITGRENZE_SEKUNDEN)
    try:
        verbindung.connect()
        return verbindung.fingerabdruck or ""
    except Exception as exc:  # noqa: BLE001
        raise _uebersetze_fehler(exc) from None
    finally:
        verbindung.close()


# --- Multipart -----------------------------------------------------------------------------------

def baue_multipart(feldname: str, dateiname: str, inhalt: bytes,
                   inhaltstyp: str = "application/octet-stream") -> tuple[bytes, str]:
    """Baut einen multipart/form-data-Body mit einem Dateifeld. Liefert (Body, Content-Type-Header).
    Anführungszeichen, Backslashes und Zeilenumbrüche im Namen werden entfernt (kein Header-Einschleusen)."""
    sauber = re.sub(r'["\\\r\n]', "_", dateiname) or "datei"
    grenze = "----shs" + secrets.token_hex(16)
    kopf = (
        f"--{grenze}\r\n"
        f'Content-Disposition: form-data; name="{feldname}"; filename="{sauber}"\r\n'
        f"Content-Type: {inhaltstyp}\r\n\r\n"
    ).encode("utf-8")
    fuss = f"\r\n--{grenze}--\r\n".encode("ascii")
    return kopf + inhalt + fuss, f"multipart/form-data; boundary={grenze}"


# --- Zuordnung Server-Antwort -> Importlogik (EINE Stelle) ----------------------------------------

#: Felder je Teilnehmer, die der Server liefert (Architektur.md, „API für den Desktop“) und die
#: db_sync.importiere_ergebnisse_aus_liste liest. Ändert der Server Schlüssel, nur hier anpassen.
_TEILNEHMER_FELDER = ("startnummer", "nachname", "vorname", "rufname_hund", "art", "stufe", "disziplin", "ergebnis")


def teilnehmer_aus_antwort(eintrag):
    """Reduziert einen Teilnehmer der Server-Antwort auf die Felder, die der Import braucht. Etwas,
    das kein Objekt ist, bleibt unverändert (der Import meldet es dann als Fehler)."""
    if not isinstance(eintrag, dict):
        return eintrag
    return {feld: eintrag[feld] for feld in _TEILNEHMER_FELDER if feld in eintrag}


# --- Client --------------------------------------------------------------------------------------

def _fehlertext_aus(daten) -> str | None:
    if isinstance(daten, dict) and isinstance(daten.get("fehler"), str):
        text = "".join(c if c.isprintable() else " " for c in daten["fehler"]).strip()
        return text[:_MAX_FEHLERTEXT] or None
    return None


class WebClient:
    """Eine Sitzung beim SHS-Web-Server. Jede Anfrage baut eine neue, gepinnte Verbindung auf;
    der Token aus anmelden() hängt als Bearer-Header an den weiteren Anfragen."""

    def __init__(self, adresse: str, fingerabdruck: str):
        self.adresse = adresse_pruefen(adresse)
        norm = fingerabdruck_normalisieren(fingerabdruck)
        if norm is None:
            raise ValueError("Ohne bestätigten Fingerabdruck ist keine Verbindung erlaubt.")
        self._fingerabdruck = norm
        self._token: str | None = None
        self.gueltig_sekunden: int | None = None

    # -- Grundfunktion
    def _anfrage(self, methode: str, pfad: str, koerper: bytes | None = None,
                 inhaltstyp: str | None = None, zeitgrenze: float | None = None) -> tuple[int, dict, object]:
        host, port = _teile(self.adresse)
        verbindung = _GepinnteVerbindung(host, port, self._fingerabdruck, zeitgrenze or ZEITGRENZE_SEKUNDEN)
        kopf = {"Accept": "application/json", "User-Agent": "SHS-Pruefungsprogramm"}
        if inhaltstyp:
            kopf["Content-Type"] = inhaltstyp
        if self._token:
            kopf["Authorization"] = f"Bearer {self._token}"
        try:
            verbindung.connect()  # Pinning-Prüfung, bevor irgendetwas gesendet wird
            verbindung.request(methode, pfad, body=koerper, headers=kopf)
            antwort = verbindung.getresponse()
            roh = antwort.read(MAX_ANTWORT_BYTES + 1)
            status, header = antwort.status, {k.lower(): v for k, v in antwort.getheaders()}
        except Exception as exc:  # noqa: BLE001 - jeder Netzwerkfehler wird zu einer Klartext-Meldung
            raise _uebersetze_fehler(exc) from None
        finally:
            verbindung.close()
        if len(roh) > MAX_ANTWORT_BYTES:
            raise WebFehler("Die Antwort des Servers ist unerwartet groß und wurde verworfen.")
        daten = None
        if roh:
            try:
                daten = json.loads(roh.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                daten = None
        return status, header, daten

    def _json(self, methode: str, pfad: str, *, erwartet: tuple[int, ...], json_daten=None,
              koerper: bytes | None = None, inhaltstyp: str | None = None,
              zeitgrenze: float | None = None) -> dict:
        if json_daten is not None:
            koerper = json.dumps(json_daten).encode("utf-8")
            inhaltstyp = "application/json"
        status, header, daten = self._anfrage(methode, pfad, koerper, inhaltstyp, zeitgrenze)
        if status in erwartet:
            if not isinstance(daten, dict):
                raise WebFehler("Die Antwort des Servers hatte ein unerwartetes Format (ist das der SHS-Server?).")
            return daten
        self._status_melden(status, header, daten)
        raise AssertionError("unerreichbar")  # pragma: no cover

    @staticmethod
    def _status_melden(status: int, header: dict, daten) -> None:
        text = _fehlertext_aus(daten)
        if status == 429:
            warte = header.get("retry-after", "")
            zusatz = f" Bitte in etwa {int(warte)} Sekunden erneut versuchen." if warte.isdigit() else " Bitte später erneut versuchen."
            raise AnmeldeFehler("Zu viele Anmeldeversuche." + zusatz, 429)
        if status == 401:
            raise AnmeldeFehler(text or "Anmeldung abgelehnt (Benutzername oder Passwort falsch).", 401)
        if status == 403:
            raise AnmeldeFehler(text or "Dieses Konto darf das nicht (nur Administratoren können Termine verwalten).", 403)
        if 300 <= status < 400:
            raise WebFehler("Der Server hat auf eine andere Adresse weitergeleitet. Das ist nicht erlaubt; bitte die Adresse prüfen.")
        if status >= 500:
            raise ServerFehler(text or f"Der Server meldet einen internen Fehler ({status}).", status)
        raise ServerFehler(text or f"Der Server hat die Anfrage abgelehnt ({status}).", status)

    # -- Schnittstelle
    def anmelden(self, benutzername: str, passwort: str) -> None:
        daten = self._json("POST", "/api/login", erwartet=(200,),
                           json_daten={"benutzername": benutzername, "passwort": passwort})
        token = daten.get("token")
        if not isinstance(token, str) or not token:
            raise WebFehler("Der Server hat keinen Anmeldetoken geliefert.")
        self._token = token
        gueltig = daten.get("gueltig_sekunden")
        self.gueltig_sekunden = gueltig if isinstance(gueltig, int) and not isinstance(gueltig, bool) else None

    def termine(self) -> list[dict]:
        """Die auf dem Server veröffentlichten Termine (schema_name, verein, ort, datum, anzahl_teilnehmer)."""
        daten = self._json("GET", "/api/termine", erwartet=(200,))
        liste = daten.get("termine")
        if not isinstance(liste, list):
            raise WebFehler("Die Terminliste des Servers hatte ein unerwartetes Format.")
        return [t for t in liste if isinstance(t, dict) and isinstance(t.get("schema_name"), str)]

    def veroeffentlichen(self, sqlite_pfad: str) -> tuple[dict, str | None]:
        """Lädt eine (Kopie der) Termin-Datei hoch. Liefert (Termin-Info, dublette_hinweis oder None)."""
        try:
            groesse = os.path.getsize(sqlite_pfad)
            if groesse > MAX_UPLOAD_BYTES:
                raise WebFehler("Die Termin-Datei ist zu groß zum Hochladen.")
            with open(sqlite_pfad, "rb") as datei:
                inhalt = datei.read()
        except OSError as exc:
            raise WebFehler(f"Die Termin-Datei ließ sich nicht lesen ({type(exc).__name__}).") from None
        koerper, inhaltstyp = baue_multipart("sqlite_datei", "termin.sqlite", inhalt)
        daten = self._json("POST", "/api/termine", erwartet=(200, 201), koerper=koerper,
                           inhaltstyp=inhaltstyp, zeitgrenze=ZEITGRENZE_UPLOAD_SEKUNDEN)  # ggf. von Tests ersetzbar (Modulkonstante)
        termin = daten.get("termin")
        if not isinstance(termin, dict) or not isinstance(termin.get("schema_name"), str):
            raise WebFehler("Der Server hat den Termin nicht bestätigt (unerwartete Antwort).")
        hinweis = daten.get("dublette_hinweis")
        return termin, (hinweis if isinstance(hinweis, str) and hinweis.strip() else None)

    def ergebnisse(self, schema_name: str) -> list[dict]:
        """Teilnehmer des Termins mit ihren Ergebnissen (siehe db_sync.importiere_ergebnisse_aus_liste)."""
        if not re.fullmatch(r"[A-Za-z0-9_]{1,80}", schema_name or ""):
            raise WebFehler("Die Termin-Kennung ist ungültig.")
        daten = self._json("GET", f"/api/termine/{schema_name}/ergebnisse", erwartet=(200,))
        liste = daten.get("teilnehmer")
        if not isinstance(liste, list):
            raise WebFehler("Die Ergebnisliste des Servers hatte ein unerwartetes Format.")
        return [teilnehmer_aus_antwort(eintrag) for eintrag in liste]
