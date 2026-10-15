"""Gemeinsame Hilfen der Desktop-Oberfläche: Ablageorte und PDF-Speicherdialoge,
Fehlermeldungen, responsive Schriftgrößen, Tabellen-Hilfsklassen und Spaltenkonstanten
der Ergebnistabelle, deutsche Qt-Texte, Absturzprotokoll, Fehlerfenster bei unbehandelten
Fehlern und die kopierbare Diagnose (ohne Benutzerpfad).

Aus app.py ausgelagert (Codex-Architekturprüfung 27.09.2026); rein interne Umstellung,
Aussehen und Verhalten sind unverändert. Die Abhängigkeiten laufen nur in eine Richtung:
app -> desktop_dialoge -> desktop_gemeinsam, app -> desktop_darstellung (jeweils -> db/
pdf_export); keines dieser Module importiert app.
"""

from __future__ import annotations

import atexit
import contextlib
import errno
import inspect
import os
import sqlite3
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QLocale, Qt, QTranslator, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTableWidgetItem,
    QWidget,
)

from db import (
    ALLE_DISZIPLINEN,
    get_veranstaltung,
    set_veranstaltung,
    zeitplan_ueberschneidungen,
)
import pdf_export


def _aktualisiere_veranstaltung_feld(conn, **overrides) -> None:
    """Aktualisiert einzelne Veranstaltungs-Felder, ohne die übrigen (z.B. von einem
    anderen Tab gepflegten) Felder zu überschreiben - set_veranstaltung ersetzt sonst bei
    jedem Aufruf den kompletten Datensatz, da es keine partiellen Updates kennt.

    Desktop-Prüfung 14.10.2026 (Teil 2 Nr. 11): die Felder kommen aus der Signatur von
    set_veranstaltung statt aus einer Liste von Hand - eine neue Spalte ginge sonst bei
    jeder Änderung von Zeitplan-Start oder Mindestabstand still verloren."""
    aktuell = get_veranstaltung(conn) or {}
    felder = [name for name in inspect.signature(set_veranstaltung).parameters if name != "conn"]
    werte = {name: aktuell.get(name) for name in felder}
    werte["verein"] = werte["verein"] or ""
    werte["datum"] = werte["datum"] or ""
    werte.update(overrides)
    set_veranstaltung(conn, **werte)


class _Ablageort:
    """Gemeinsamer, veränderlicher Ablageort für alle Export-Buttons EINES Termins
    (Reiter "Teilnehmer", "Auswertung", "Zeitplan" und "Export")
    - ein einzelnes, von allen diesen Tabs geteiltes Objekt statt
    je ein eigener String pro Tab. Wählt der Nutzer beim Speichern bewusst einen anderen
    Ordner, gilt dieser dadurch sofort auch als neuer Standard-Speicherort im jeweils
    ANDEREN Tab, statt dass beide unabhängig voneinander ihren eigenen (dann ggf.
    unterschiedlichen) Ablageort verfolgen."""

    def __init__(self, pfad: str):
        self.pfad = pfad


def _dateiname_teil(text: str) -> str:
    """Nutzertext als Teil eines Dateinamens (Desktop-Prüfung 14.10.2026, Teil 1 Nr. 5): ohne
    Zeichen, die Windows im Dateinamen nicht erlaubt bzw. als Ordnertrenner liest - sonst
    machte „Meier/Schulz“ den Vorschlag zu Ordner plus Datei."""
    import re

    return re.sub(r'\s*[\\/:*?"<>|\x00-\x1f]+\s*', "-", text or "").strip(" .-") or "Teilnehmer"


def _export_dateiname(conn, praefix: str) -> str:
    veranstaltung = get_veranstaltung(conn)
    datum = (veranstaltung or {}).get("datum") or ""
    return f"{praefix}_{datum}.pdf" if datum else f"{praefix}.pdf"


# UX-Test 02.10.2026, U7 (Rubrik ux_test_2026_10): PDFs landeten zwischen den
# Termin-Dateien, nach dem Speichern gab es nur eine kleine Statuszeile ("Wo ist das jetzt
# hin?"), und Importe starteten nicht dort, wo heruntergeladene Dateien liegen.
def _ausdrucke_ordner(termin_pfad: str) -> str:
    """Standard-Ablageort für PDFs eines Termins: Unterordner "Ausdrucke/<Termin>" neben
    der Termin-Datei (Marcos Entscheidung 03.10.2026). Wird erst beim Speichern angelegt."""
    ordner, dateiname = os.path.split(os.path.abspath(termin_pfad))
    return os.path.join(ordner, "Ausdrucke", os.path.splitext(dateiname)[0])


def _pfad_anzeige(pfad: str) -> str:
    """Pfad in Windows-Schreibweise (Qt-Dialoge liefern "/" als Trenner)."""
    return os.path.normpath(pfad)


def _ausfuehren(dialog) -> int:
    """Zeigt einen Dialog bzw. eine Meldung modal und gibt ihn danach zum Löschen frei.
    Desktop-Prüfung 14.10.2026 (Teil 2 Nr. 9, Teil 6 Nr. 8, Teil 7, Teil 8): Dialoge mit
    Elternfenster blieben sonst bis zum Programmende als Kinder liegen - samt Inhalt (z. B.
    eingegebener Passwörter). Gelöscht wird erst beim Rücklauf in die Ereignisschleife, der
    Aufrufer kann also danach noch Werte auslesen."""
    ergebnis = dialog.exec()
    loeschen = getattr(dialog, "deleteLater", None)  # Testattrappen haben keins
    if loeschen is not None:
        loeschen()
    return ergebnis


def _ja_nein(parent, titel: str, text: str, *, vorgabe_ja: bool = False) -> bool:
    """Ja/Nein-Rückfrage mit ausdrücklich gewählter Vorgabe; True bei „Ja“. Vorgabe „Nein“
    für alles, was Daten ändert oder verwirft (Abschluss-QS 15.10.2026, A19c). Ruft
    QMessageBox.question positionell auf - Klartext und Freigabe übernimmt
    meldungsfenster_als_klartext, und Tests können die Vorgabe als fünftes Argument lesen."""
    vorgabe = QMessageBox.Yes if vorgabe_ja else QMessageBox.No
    return QMessageBox.question(parent, titel, text, QMessageBox.Yes | QMessageBox.No, vorgabe) == QMessageBox.Yes


@contextlib.contextmanager
def _wartecursor():
    """Wartecursor für längere Arbeiten (PDF- und CSV-Export, Sicherung), sicher wieder
    zurückgesetzt (Teil 6 Nr. 7)."""
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()


def _url_oeffnen(parent, url: QUrl, anzeige: str) -> bool:
    """Öffnet `url` mit dem Standardprogramm. Desktop-Prüfung 14.10.2026 (Teil 9 Nr. 10):
    QDesktopServices.openUrl meldet einen Fehlschlag nur über den Rückgabewert (z. B. Linux
    ohne xdg-open, keine Anwendung für .pdf/.csv) - dann jetzt eine Meldung mit `anzeige`
    (Pfad bzw. Adresse) zum Öffnen von Hand, statt dass einfach nichts passiert."""
    if QDesktopServices.openUrl(url):
        return True
    QMessageBox.warning(
        parent, "Öffnen nicht möglich",
        f"Es ließ sich kein Programm zum Öffnen starten. Bitte von Hand öffnen:\n\n{anzeige}",
    )
    return False


def _ordner_zeigen(pfad: str, parent=None) -> None:
    """Öffnet den Explorer mit markierter Datei (Windows) bzw. den Ordner."""
    if sys.platform == "win32" and os.path.isfile(pfad):
        import subprocess

        try:
            # Desktop-Prüfung 14.10.2026 (Teil 6 Nr. 9): Pfad selbst in Anführungszeichen - die
            # Listenform quotet nur bei Leerzeichen, und der Explorer trennt sonst am Komma.
            subprocess.Popen(f'explorer /select,"{_pfad_anzeige(pfad)}"')
            return
        except OSError:
            pass  # Rückfall: den Ordner über Qt öffnen
    ordner = os.path.dirname(pfad) if os.path.isfile(pfad) else pfad
    _url_oeffnen(parent, QUrl.fromLocalFile(ordner), _pfad_anzeige(ordner))


def _datei_gespeichert_melden(
    parent, pfad: str, titel: str, datei_oeffnen_text: str | None = "PDF öffnen", hinweis: str | None = None,
) -> None:
    """Meldung nach dem Speichern mit den nächsten Schritten [PDF öffnen] [Ordner zeigen]
    [OK] - statt nur einer leicht übersehenen Statuszeile."""
    box = QMessageBox(parent)
    box.setTextFormat(Qt.PlainText)  # S-1: Pfade/Namen nie als HTML deuten
    box.setIcon(QMessageBox.Information)
    box.setWindowTitle(titel)
    box.setText(f"Gespeichert unter:\n{_pfad_anzeige(pfad)}")
    if hinweis:
        box.setInformativeText(hinweis)
    oeffnen_btn = box.addButton(datei_oeffnen_text, QMessageBox.ActionRole) if datei_oeffnen_text else None
    ordner_btn = box.addButton("Ordner zeigen", QMessageBox.ActionRole)
    box.setDefaultButton(box.addButton(QMessageBox.Ok))
    _ausfuehren(box)
    if oeffnen_btn is not None and box.clickedButton() is oeffnen_btn:
        _url_oeffnen(parent, QUrl.fromLocalFile(pfad), _pfad_anzeige(pfad))
    elif box.clickedButton() is ordner_btn:
        _ordner_zeigen(pfad, parent)


# Startordner der Import-Dialoge: zuerst "Downloads" (dort landen per E-Mail empfangene
# Anmeldungen/Listen), danach der zuletzt für einen Import benutzte Ordner.
_letzter_import_ordner: str | None = None


def _import_startordner() -> str:
    if _letzter_import_ordner and os.path.isdir(_letzter_import_ordner):
        return _letzter_import_ordner
    downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    return downloads if os.path.isdir(downloads) else os.path.expanduser("~")


def _import_ordner_merken(pfad: str) -> None:
    global _letzter_import_ordner
    if pfad:
        _letzter_import_ordner = os.path.dirname(pfad)


def _pdf_speicherort_waehlen(parent, ablageort: _Ablageort, titel: str, vorschlag_dateiname: str) -> str | None:
    try:
        # Der Ausdrucke-Ordner (siehe _ausdrucke_ordner) entsteht erst hier - sonst würde
        # der Dialog bei einem fehlenden Ordner an einer anderen Stelle starten.
        os.makedirs(ablageort.pfad, exist_ok=True)
    except OSError:
        pass
    vorschlag_pfad = os.path.join(ablageort.pfad, vorschlag_dateiname)
    pfad, _ = QFileDialog.getSaveFileName(parent, titel, vorschlag_pfad, "PDF-Datei (*.pdf)")
    if not pfad:
        return None
    # Merkt sich den zuletzt gewählten Ordner (siehe _Ablageort oben), damit sowohl der
    # nächste Speichern-Dialog in DIESEM Tab als auch im jeweils anderen Tab dorthin
    # zeigen, falls der Nutzer bewusst woanders gespeichert hat.
    ablageort.pfad = os.path.dirname(pfad)
    return pfad


def _pdf_export_fehler_anzeigen(parent, exc: Exception) -> None:
    """Desktop-Prüfung 14.10.2026 (Teil 9 Nr. 5): Nur ein Dateifehler liegt am Zielpfad bzw.
    an einer geöffneten Datei; jeder andere Fehler ist ein Programmfehler und kommt ins
    Absturzprotokoll (siehe _fehlertext)."""
    if isinstance(exc, OSError):
        text = f"Die PDF-Datei konnte nicht gespeichert werden.\n\n{_klartext_fehler(exc)}"
    else:
        text = f"Das PDF konnte nicht erstellt werden.\n\n{_fehlertext(exc)}"
    QMessageBox.critical(parent, "PDF konnte nicht erstellt werden", text)


def _pdf_exportieren(parent, ablageort: "_Ablageort", status_label: QLabel, titel: str,
                     vorschlag: str, export_fn, status_text) -> None:
    """Gemeinsamer Ablauf aller PDF-Exporte (Desktop-Prüfung 14.10.2026, Teil 6 Nr. 11):
    Speicherort wählen, export_fn(pfad) aufrufen, Fehler melden, Status setzen und die Meldung
    „gespeichert“ zeigen. `status_text` ist ein fester Text oder eine Funktion
    Ergebnis -> Text (z. B. „N Bewertungsbögen gespeichert“)."""
    pfad = _pdf_speicherort_waehlen(parent, ablageort, titel, vorschlag)
    if not pfad:
        return
    try:
        with _wartecursor():
            ergebnis = export_fn(pfad)
    except Exception as exc:  # noqa: BLE001 - Unterscheidung in _pdf_export_fehler_anzeigen
        _pdf_export_fehler_anzeigen(parent, exc)
        return
    text = status_text(ergebnis) if callable(status_text) else status_text
    status_label.setText(f"{text}: {_pfad_anzeige(pfad)}")
    _datei_gespeichert_melden(parent, pfad, text)


def _zeitplan_pdf_exportieren(parent, conn, ablageort: "_Ablageort", status_label: QLabel) -> None:
    """Gemeinsame Umsetzung für den Zeitplan-PDF-Export - vorher wortgleich in
    ZeitplanTab._pdf_exportieren und ExportTab._zeitplan_exportieren dupliziert."""
    # UX-Test 02.10.2026, U2: nicht unbemerkt einen Plan mit doppelt eingeplanten Teams
    # verschicken.
    konflikte = zeitplan_ueberschneidungen(conn)
    if konflikte:
        if not _ja_nein(
            parent, "Überschneidungen im Zeitplan",
            f"Im Zeitplan gibt es {len(konflikte)} Überschneidung(en): Teams stehen gleichzeitig "
            "bzw. ohne Mindestabstand an zwei Stellen (im Reiter „Zeitplan“ rot markiert).\n\n"
            "Trotzdem als PDF speichern?",
        ):
            return
    _pdf_exportieren(parent, ablageort, status_label, "Zeitplan speichern", _export_dateiname(conn, "Zeitplan"),
                     lambda pfad: pdf_export.erstelle_zeitplan_pdf(conn, pfad), "Zeitplan gespeichert")


def _responsive_schriftgroesse(breite: int, schmal: int = 480, breit: int = 900, pt_schmal: float = 8.0, pt_breit: float = 10.0) -> float:
    """Berechnet eine Schriftgröße (pt) zwischen pt_schmal und pt_breit, linear nach
    der Fensterbreite interpoliert - damit Beschriftungen (Spaltenköpfe, Filter- und
    Hinweistexte) bei kleineren Fenstern nicht abgeschnitten werden, sondern lesbar
    kleiner dargestellt werden, statt der Anwendung eine Mindestbreite vorzuschreiben."""
    if breite <= schmal:
        return pt_schmal
    if breite >= breit:
        return pt_breit
    anteil = (breite - schmal) / (breit - schmal)
    return pt_schmal + anteil * (pt_breit - pt_schmal)


def _ergebnis_spaltenbreiten_verteilen(
    natuerliche_breiten: list[int],
    minimum_breiten: list[int],
    verfuegbare_breite: int,
    harte_minima: list[int] | None = None,
) -> list[int]:
    """Passt Spaltenbreiten proportional an verfuegbare_breite an, ohne minimum_breiten zu
    unterschreiten - für die Ergebniserfassung (Nutzerwunsch 22.09.: Tabelle soll bei
    maximiertem Fenster ohne horizontales Scrollen auf den Bildschirm passen). Reicht der
    Platz bereits, bleiben die natürlichen Breiten unverändert (der Rest geht an die
    gestreckte Status-Spalte, siehe setStretchLastSection in ErgebnisTab). Reicht selbst das
    Zusammenstauchen auf die Minima nicht aus (Fenster schmaler als die Summe aller Minima)
    UND ist kein harte_minima übergeben, werden die Minima zurückgegeben - ein Scrollbalken
    ist dann der akzeptierte Fallback, kein Fehler. Reine Funktion ohne Qt-Abhängigkeit,
    daher direkt testbar.

    Mehrstufig statt ein einziger globaler Faktor (QS-Fund 22.09.): Spalten, deren Minimum
    bereits ihrer natürlichen Breite entspricht (z.B. Start-Nr./Name/Hund/Art-LK - reiner
    Text, der nicht schrumpfen soll), schrumpfen NIE, unabhängig vom globalen Faktor. Würde
    deren volle natürliche Breite dennoch in die Faktor-Berechnung einfließen, bekämen die
    tatsächlich schrumpfbaren Spalten (Punkte/Checkbox-Spalten) zu wenig abgezogen und die
    Summe würde verfuegbare_breite trotzdem überschreiten. Stattdessen iterativ: Spalten, die
    ihr Minimum erreichen (oder es sowieso schon sind), werden mit exakt ihrem Minimum aus
    der Verteilung herausgenommen, der verbleibende Faktor wird nur noch aus den übrigen
    (noch nicht fixierten) Spalten neu berechnet - bis sich nichts mehr ändert.

    Rundungs-Korrektur (CI-Regression 22.09., gefunden über test_ergebnis_tabelle_passt_bei_
    typischer_maximierter_breite_ohne_scrollbalken): das obige round() je Spalte kann die
    Summe der Zielbreiten trotzdem noch über verfuegbare_breite hinausschieben, wenn keine
    der offenen Spalten dabei ihr Minimum erreicht (z.B. natuerlich=[3]*10, minima=[0]*10,
    verfuegbare_breite=27 -> jede Spalte rundet 2.7 auf 3, Summe 30 > 27). Deshalb danach
    eine Korrektur-Passe: liegt die Summe noch über verfuegbare_breite, wird Spalten mit
    noch vorhandenem Spielraum (ziel > minimum) reihum je 1px abgezogen (größter Spielraum
    zuerst), bis die Summe passt oder keine Spalte mehr Spielraum hat.

    harte_minima-Fallback (CI-Regression 22.09., Fortsetzung: trat auf CI/Linux mit anderen
    Schriftmetriken als lokal unter Windows selbst nach obiger Rundungs-Korrektur weiter
    auf): reicht selbst das Zusammenstauchen auf minimum_breiten knapp nicht - z.B. weil
    andere Fonts die headertext-basierten Minima ein paar Pixel breiter messen als lokal -,
    UND ist harte_minima übergeben (je Spalte ein inhaltsbasiertes, i.d.R. niedrigeres
    Minimum ohne Kopfzeilen-Padding-Reserve), wird eine zweite Korrektur-Passe mit
    harte_minima statt minimum_breiten als Untergrenze versucht. Der Nutzerwunsch "kein
    Scrollbalken bei maximiertem Fenster" wiegt damit schwerer als ein paar Pixel
    Kopfzeilen-Luft - erst wenn auch harte_minima nicht ausreicht, bleibt der
    Scrollbalken-Fallback. Ohne harte_minima (Standard, `None`) ist das Verhalten exakt wie
    vorher."""
    ziel = list(natuerliche_breiten)
    gesamt = sum(ziel)
    if gesamt <= 0 or gesamt <= verfuegbare_breite:
        return ziel

    offen = list(range(len(ziel)))
    while offen:
        fixiert_summe = sum(minimum_breiten[i] for i in range(len(ziel)) if i not in offen)
        rest_budget = max(verfuegbare_breite - fixiert_summe, 0)
        rest_gesamt = sum(natuerliche_breiten[i] for i in offen)
        if rest_gesamt <= 0:
            break
        faktor = rest_budget / rest_gesamt

        neu_fixiert = []
        for i in offen:
            kandidat = round(natuerliche_breiten[i] * faktor)
            if kandidat <= minimum_breiten[i]:
                ziel[i] = minimum_breiten[i]
                neu_fixiert.append(i)
            else:
                ziel[i] = kandidat
        if not neu_fixiert:
            break
        offen = [i for i in offen if i not in neu_fixiert]

    def _reihum_abziehen(untergrenzen: list[int], ueberschuss: int) -> int:
        spielraum = [i for i in range(len(ziel)) if ziel[i] > untergrenzen[i]]
        spielraum.sort(key=lambda i: ziel[i] - untergrenzen[i], reverse=True)
        pos = 0
        while ueberschuss > 0 and spielraum:
            i = spielraum[pos % len(spielraum)]
            if ziel[i] > untergrenzen[i]:
                ziel[i] -= 1
                ueberschuss -= 1
                pos += 1
            else:
                spielraum.remove(i)
        return ueberschuss

    ueberschuss = sum(ziel) - verfuegbare_breite
    if ueberschuss > 0:
        ueberschuss = _reihum_abziehen(minimum_breiten, ueberschuss)
    if ueberschuss > 0 and harte_minima is not None:
        _reihum_abziehen(harte_minima, ueberschuss)

    return ziel


class ResponsiveSchriftMixin:
    """Mixin für Fenster/Dialoge: passt bei jeder Größenänderung die Schriftgröße von
    Spaltenköpfen und Beschriftungen (QLabel) an die aktuelle Fensterbreite an (siehe
    _responsive_schriftgroesse) - Tabellen und Formularfelder selbst bleiben in normaler
    Größe, nur die Beschriftungen schrumpfen bei kleinen Fenstern, statt abgeschnitten
    zu werden."""

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._schriftgroesse_anwenden()

    def _schriftgroesse_anwenden(self) -> None:
        pt = round(_responsive_schriftgroesse(self.width()), 1)
        # Nur bei geänderter Schriftgröße neu setzen - jedes setStyleSheet stößt ein
        # Neu-Polieren aller Kind-Widgets an (Desktop-Prüfung 14.10.2026, Teil 3 Nr. 6).
        if getattr(self, "_schrift_pt", None) == pt:
            return
        self._schrift_pt = pt
        self.setStyleSheet(f"QHeaderView::section {{ font-size: {pt:.1f}pt; }} QLabel {{ font-size: {pt:.1f}pt; }}")


def _fehler_anzeigen(parent, exc: Exception) -> None:
    """Zeigt einen Datenbankfehler (z.B. verletzte Fachregel) als Dialog statt die App abstürzen zu lassen."""
    QMessageBox.critical(
        parent,
        "Eingabe konnte nicht gespeichert werden",
        f"Die Daten verletzen eine Fachregel und wurden nicht gespeichert:\n\n{exc}",
    )


# Desktop-Prüfung 14.10.2026 (Teil 9 Nr. 6): typische SQLite-Fehlertexte und ihre Erklärung
# in Klartext.
_SQLITE_KLARTEXT = (
    (("readonly",), "Die Termin-Datei ist schreibgeschützt (z. B. schreibgeschützter USB-Stick "
                    "oder Dateieigenschaften „Schreibgeschützt“)."),
    (("locked", "busy"), "Die Termin-Datei ist gerade von einem anderen Programm gesperrt (z. B. "
                         "Synchronisierung, Virenscanner oder ein zweites Programmfenster). Bitte "
                         "kurz warten und es erneut versuchen."),
    (("disk is full",), "Der Datenträger ist voll."),
    (("disk i/o error",), "Die Termin-Datei ist nicht erreichbar (z. B. USB-Stick abgezogen oder "
                          "Netzlaufwerk getrennt)."),
    (("unable to open",), "Die Termin-Datei lässt sich nicht öffnen bzw. anlegen (z. B. Ordner "
                          "fehlt, USB-Stick abgezogen oder Netzlaufwerk getrennt)."),
)


def _datei_klartext(exc: OSError) -> str | None:
    """Erklärung zu den erwartbaren Dateifehlern (Teil 9 Nr. 6, Teil 5 Nr. 4)."""
    if exc.errno == errno.ENOSPC:
        return "Der Datenträger ist voll."
    if isinstance(exc, PermissionError):
        return ("Die Datei ist schreibgeschützt oder gerade in einem anderen Programm geöffnet "
                "(z. B. Excel oder eine PDF-Anzeige). Bitte die Datei dort schließen und es "
                "erneut versuchen.")
    if isinstance(exc, FileNotFoundError):
        return ("Die Datei bzw. der Ordner wurde nicht gefunden (z. B. USB-Stick abgezogen, "
                "Netzlaufwerk getrennt oder Datei verschoben).")
    return None


def _technischer_text(exc: BaseException) -> str:
    """Technischer Fehlertext für die Klammer „(Technisch: …)“. str(OSError) zeigt den Pfad
    als repr() - unter Windows mit doppelten Backslashes (Teil 5 Nr. 4); deshalb Fehlertext
    und Pfad einzeln."""
    if isinstance(exc, OSError) and exc.strerror:
        if isinstance(exc.filename, (str, bytes, os.PathLike)):
            return f"{exc.strerror}: {_pfad_anzeige(os.fsdecode(exc.filename))}"
        return exc.strerror
    return str(exc) or type(exc).__name__


def _klartext_fehler(exc: BaseException) -> str:
    """Verständliche Beschreibung eines erwartbaren Datei- oder Datenbankfehlers; der
    technische Text steht in Klammern dahinter. Unbekannte Fehler bleiben beim technischen
    Text."""
    technisch = _technischer_text(exc)
    erklaerung = None
    if isinstance(exc, sqlite3.Error):
        klein = technisch.lower()
        erklaerung = next((e for stichworte, e in _SQLITE_KLARTEXT
                           if any(wort in klein for wort in stichworte)), None)
    elif isinstance(exc, OSError):
        erklaerung = _datei_klartext(exc)
    if erklaerung:
        return f"{erklaerung}\n\n(Technisch: {technisch})"
    return technisch


def _fehlertext(exc: BaseException) -> str:
    """Text für die Meldung eines breiten Fängers (`except Exception`). Desktop-Prüfung
    14.10.2026 (Teil 9 Nr. 5, Teil 10 Nr. 6): Datei- und Datenbankfehler sind erwartbar und
    erscheinen in Klartext; alles andere ist ein Programmfehler - der kommt samt Traceback
    ins Absturzprotokoll und erscheint mit seinem Typ (bei KeyError stünde sonst nur der
    Schlüssel da)."""
    if isinstance(exc, (OSError, sqlite3.Error)):
        return _klartext_fehler(exc)
    fehler_protokollieren(exc)
    return (f"Programmfehler ({type(exc).__name__}: {exc}). Bitte über den Knopf „Version“ → "
            "„Diagnose kopieren“ melden.")


def _db_fehler_anzeigen(parent, exc: Exception,
                        einleitung: str = "Die Änderung konnte nicht gespeichert werden.") -> None:
    """Zeigt einen unerwarteten Datenbankfehler (z.B. gesperrte Datei, voller Datenträger) als
    Dialog statt die App abstürzen zu lassen - für Aktionen ohne eigene Fachregel-Prüfung
    (Richter/Zeitplan verwalten u.ä.) und für Schreibfehler beim Speichern."""
    QMessageBox.critical(
        parent,
        "Datenbankfehler",
        f"{einleitung}\n\n{_klartext_fehler(exc)}",
    )


# Auswahlwert für "diesem Gegenstand ist (noch) keine Disziplin zugeordnet" - bewusst kein
# Eintrag aus ALLE_DISZIPLINEN, damit er sich eindeutig von einer echten Zuordnung
# unterscheidet. Wird als NULL in der Datenbank abgelegt (siehe db.NeuerTeilnehmer).
_GEGENSTAND_ZUORDNUNG_FREI = "frei"

# Codeprüfung 22.09., G4: Auswahlwert für "Geschlecht nicht angegeben". Bisher kannte die
# Combo nur "Hündin"/"Rüde" - ein neuer Teilnehmer startete damit still auf "Hündin", und
# ein Teilnehmer mit geschlecht NULL (z. B. aus dem CSV-/Web-Import) wurde beim bloßen
# Öffnen und Speichern im Bearbeiten-Dialog unbemerkt zur "Hündin". Wird als NULL in der
# Datenbank abgelegt (das Schema erlaubt NULL, siehe db.SCHEMA).
_GESCHLECHT_UNBEKANNT = "–"


def _zuordnung_oder_none(combo: QComboBox) -> str | None:
    text = combo.currentText()
    return None if text == _GEGENSTAND_ZUORDNUNG_FREI else text


def _gegenstand_zeile(feld: QLineEdit, zuordnung: QComboBox) -> QWidget:
    """Kombiniert ein Gegenstand-Textfeld mit seiner Disziplin-Zuordnung (frei/Trümmerfeld/
    Flächensuche/Behältnisstrecke) zu einer gemeinsamen Formularzeile."""
    zeile = QHBoxLayout()
    zeile.setContentsMargins(0, 0, 0, 0)
    zeile.addWidget(feld, 2)
    zeile.addWidget(QLabel("gesucht in:"))
    zeile.addWidget(zuordnung, 1)
    widget = QWidget()
    widget.setLayout(zeile)
    return widget


def _startnummer_zeile(feld: QSpinBox, unbekannt: QCheckBox) -> QWidget:
    """Kombiniert das Startnummer-Feld mit dem Häkchen 'Startnummer steht noch nicht
    fest' zu einer gemeinsamen Formularzeile (Nutzerwunsch 20.09.: Startnummer soll bei
    der Ersterfassung kein Pflichtfeld mehr sein müssen)."""
    zeile = QHBoxLayout()
    zeile.setContentsMargins(0, 0, 0, 0)
    zeile.addWidget(feld, 1)
    zeile.addWidget(unbekannt, 2)
    widget = QWidget()
    widget.setLayout(zeile)
    return widget


class _NumerischSortierbaresItem(QTableWidgetItem):
    """QTableWidgetItem für die Start-Nr.-Spalte der Teilnehmerliste: sortiert nach einem
    echten Zahlenwert (2 vor 10) statt nach dem angezeigten Text ("10" vor "2").

    Der naheliegendere Ansatz - `item.setData(Qt.DisplayRole, zahl)` und sich auf Qts
    eingebauten Vergleich (QTableWidgetItem.operator<, liest Qt.DisplayRole) zu verlassen
    - sortiert in einem echten CI-Lauf (PySide6/Qt6) NICHT numerisch, sondern weiterhin
    rein alphabetisch (per CI-Fund am 20.09. entdeckt, siehe Fortschritt.md; lokal ohne
    installiertes PySide6 nicht überprüfbar gewesen). Stattdessen hier `__lt__` direkt
    überschrieben - das ist der Vergleich, den `QTableWidget.sortItems()`/`sortByColumn()`
    tatsächlich aufruft, unabhängig von Datenrollen-Feinheiten."""

    def __init__(self, text: str, sortierwert: int) -> None:
        super().__init__(text)
        self._sortierwert = sortierwert

    def __lt__(self, other) -> bool:  # noqa: D105 - siehe Klassen-Docstring
        if isinstance(other, _NumerischSortierbaresItem):
            return self._sortierwert < other._sortierwert
        return super().__lt__(other)


# Zeilenfarben der Ergebniserfassung (ungespeichert: dezentes Gelb bzw. im dunklen Design
# ein gedecktes Bernstein) kommen aus dem aktiven Hintergrund-Design, siehe _farbe().


def _zentrierte_zelle(widget: QWidget) -> QWidget:
    """Bettet `widget` (z.B. eine QCheckBox) in einen kleinen Container mit zentriertem
    Layout ein - als setCellWidget-Inhalt einer QTableWidget-Zelle, da eine QCheckBox
    allein dort automatisch linksbündig erscheint. Siehe ErgebnisTab (Disqualifiziert-/
    Abbruch-Spalten)."""
    zelle = QWidget()
    # Ein einfaches QWidget malt seinen per Stylesheet gesetzten Hintergrund (siehe
    # _aktualisiere_zeilenstatus) standardmäßig NICHT selbst - anders als z.B. QLineEdit,
    # das seinen Hintergrund ohnehin über den Stil zeichnet. WA_StyledBackground schaltet
    # das für dieses Widget gezielt ein.
    zelle.setAttribute(Qt.WA_StyledBackground, True)
    layout = QHBoxLayout(zelle)
    layout.addWidget(widget)
    layout.setAlignment(Qt.AlignCenter)
    layout.setContentsMargins(0, 0, 0, 0)
    return zelle

# Spaltenreihenfolge in der Ergebniserfassung: je Disziplin ein Such-/Anzeigeleistungs-Paar,
# alle drei nebeneinander in einer Zeile - bei DK sind alle drei aktiv, bei ED nur die
# jeweils zutreffende (die anderen beiden Spalten bleiben leer/gesperrt).
_ERGEBNIS_SPALTEN_JE_DISZIPLIN = {
    disziplin: (4 + 2 * i, 4 + 2 * i + 1) for i, disziplin in enumerate(ALLE_DISZIPLINEN)
}
# Nutzerwunsch (21.09.): zwei zusätzliche Spalten für die unabhängigen Status
# "Disqualifiziert"/"Abbruch", vor der bestehenden Status-Spalte (die den
# gespeichert/nicht-gespeichert-Hinweis dieser Zeile zeigt, siehe _aktualisiere_zeilenstatus).
_DQ_SPALTE = 4 + 2 * len(ALLE_DISZIPLINEN)
_ABBRUCH_SPALTE = _DQ_SPALTE + 1
_STATUS_SPALTE = _ABBRUCH_SPALTE + 1


# UX-Test 02.10.2026, Punkt U6 (Rubrik ux_test_2026_10): Standardknöpfe wie Yes/No/Cancel
# erschienen englisch, weil keine Qt-Übersetzung geladen war. Zweistufig gelöst:
# 1. die deutsche Qt-Übersetzung (qtbase_de.qm) laden, falls sie mitgeliefert ist (pip-
#    PySide6 und damit der PyInstaller-Build bringen sie üblicherweise mit; das lokale
#    Anaconda-PySide6 dagegen nicht);
# 2. unabhängig davon ein kleiner eingebauter Übersetzer für die Standardknöpfe und das
#    Kontextmenü der Eingabefelder - greift auch dann, wenn die .qm-Datei fehlt.
_DEUTSCHE_QT_TEXTE = {
    "QPlatformTheme": {
        "OK": "OK", "Save": "Speichern", "Save All": "Alle speichern", "Open": "Öffnen",
        "&Yes": "&Ja", "Yes to &All": "Ja, &alle", "&No": "&Nein", "N&o to All": "N&ein, keine",
        "Abort": "Abbrechen", "Retry": "Wiederholen", "Ignore": "Ignorieren",
        "Close": "Schließen", "Cancel": "Abbrechen", "Discard": "Verwerfen",
        "Don't Save": "Nicht speichern", "Help": "Hilfe", "Apply": "Anwenden",
        "Reset": "Zurücksetzen", "Restore Defaults": "Standardwerte",
    },
    "QMessageBox": {
        "Show Details...": "Details einblenden …", "Hide Details...": "Details ausblenden …",
    },
}
_KONTEXTMENUE_TEXTE = {
    "&Undo": "&Rückgängig", "&Redo": "Wieder&herstellen", "Cu&t": "&Ausschneiden",
    "&Copy": "&Kopieren", "&Paste": "Einf&ügen", "Delete": "Löschen",
    "Select All": "Alles auswählen",
}
_DEUTSCHE_QT_TEXTE["QLineEdit"] = _KONTEXTMENUE_TEXTE
_DEUTSCHE_QT_TEXTE["QWidgetTextControl"] = _KONTEXTMENUE_TEXTE


class _DeutscheStandardtexte(QTranslator):
    """Übersetzt nur die Texte aus _DEUTSCHE_QT_TEXTE. Für alles andere wird None
    zurückgegeben - Qt fragt dann den nächsten Übersetzer bzw. nimmt den Originaltext
    (ein leerer String würde dagegen als "Übersetzung" gelten und Texte verschwinden lassen)."""

    def translate(self, context, source_text, disambiguation=None, n=-1):  # noqa: D102
        return _DEUTSCHE_QT_TEXTE.get(context, {}).get(source_text)


# Referenzen festhalten: QApplication übernimmt installierte Übersetzer nicht in Besitz,
# ohne Referenz würde Python sie wieder einsammeln.
_installierte_uebersetzer: list[QTranslator] = []


def _qt_uebersetzungs_ordner() -> list[str]:
    """Mögliche Orte von qtbase_de.qm: Qt-Standardpfad, PySide6-Paket, PyInstaller-Bundle."""
    import PySide6

    ordner = [QLibraryInfo.path(QLibraryInfo.TranslationsPath),
              os.path.join(os.path.dirname(PySide6.__file__), "translations")]
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        ordner.append(os.path.join(bundle, "PySide6", "translations"))
    return ordner


def programmsymbol_pfad() -> str:
    """Pfad zu symbol/programmsymbol.png - im PyInstaller-Bundle unter sys._MEIPASS (dort per
    build.spec mitgeliefert), sonst neben diesem Modul (Marco 07.10.2026, Beagle-Symbol)."""
    basis = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(basis, "symbol", "programmsymbol.png")


def programmsymbol() -> QIcon:
    """Das Programmsymbol als QIcon; leer, falls die Datei fehlt (dann zeigt das System sein
    Standardsymbol - der Selbsttest der gebauten Fassung prüft, dass sie dabei ist)."""
    return QIcon(programmsymbol_pfad())


def meldungsfenster_als_klartext() -> None:
    """Sicherheitsprüfung 03.10.2026, S-1: Qt zeigt Meldungstexte automatisch als
    formatierten Text (HTML) an, sobald sie danach aussehen. Viele Meldungen enthalten Namen
    aus Importen bzw. fremden Termin-Dateien - ein präparierter Name könnte so Markup oder
    ein Bild (auch über einen Netzwerkpfad) einschleusen. Alle Standard-Meldungsfenster
    (question/information/warning/critical) zeigen ihren Text deshalb als reinen Text.
    Wird einmal beim Programmstart aufgerufen; mehrfaches Aufrufen schadet nicht."""
    if getattr(QMessageBox, "_shs_klartext", False):
        return

    def _fabrik(icon, standard_knoepfe):
        def meldung(parent, titel, text, buttons=standard_knoepfe,
                    defaultButton=QMessageBox.StandardButton.NoButton):
            box = QMessageBox(icon, titel, text, buttons, parent)
            box.setTextFormat(Qt.PlainText)
            if defaultButton != QMessageBox.StandardButton.NoButton:
                box.setDefaultButton(defaultButton)
            return QMessageBox.StandardButton(_ausfuehren(box))
        return staticmethod(meldung)

    ok = QMessageBox.StandardButton.Ok
    QMessageBox.question = _fabrik(QMessageBox.Icon.Question, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    QMessageBox.information = _fabrik(QMessageBox.Icon.Information, ok)
    QMessageBox.warning = _fabrik(QMessageBox.Icon.Warning, ok)
    QMessageBox.critical = _fabrik(QMessageBox.Icon.Critical, ok)
    QMessageBox._shs_klartext = True


def deutsche_qt_texte_laden(app) -> bool:
    """Installiert die deutschen Qt-Texte in `app`. Liefert True, wenn zusätzlich die
    vollständige Qt-Übersetzung (qtbase_de.qm) gefunden wurde."""
    datei_gefunden = False
    for ordner in _qt_uebersetzungs_ordner():
        uebersetzer = QTranslator(app)
        if uebersetzer.load(QLocale(QLocale.German, QLocale.Germany), "qtbase", "_", ordner):
            app.installTranslator(uebersetzer)
            _installierte_uebersetzer.append(uebersetzer)
            datei_gefunden = True
            break
    # Zuletzt installierte Übersetzer werden zuerst gefragt - der eingebaute hat damit für
    # die Standardknöpfe Vorrang und sorgt für einheitliche Texte, egal ob die .qm da ist.
    standard = _DeutscheStandardtexte(app)
    app.installTranslator(standard)
    _installierte_uebersetzer.append(standard)
    return datei_gefunden


# UX-Test 02.10.2026, Punkt P1 (Rubrik ux_test_2026_10): Bei mehreren Test-Personas beendete
# sich das Programm direkt nach einer Dateiauswahl ohne jede Meldung; im installierten
# Programm (PyInstaller, ohne Konsole) gingen solche Fehler bisher spurlos verloren. Deshalb
# schreibt das Programm jetzt ein Absturzprotokoll: unbehandelte Python-Fehler über
# sys.excepthook, harte Abstürze (z. B. Speicherfehler in Qt) über faulthandler. Bei jedem
# Start eine kurze Startzeile, damit sich ein späterer Absturz zeitlich zuordnen lässt.
ABSTURZPROTOKOLL_DATEINAME = "absturzprotokoll.txt"
# Desktop-Prüfung 14.10.2026 (Teil 9 Nr. 4): Ist das Protokoll beim Start größer, wird es zur
# ".alt"-Datei (statt geleert zu werden) - die Ursache bleibt so für "Diagnose kopieren"
# erhalten. Im laufenden Programm schreibt ein Lauf höchstens _PROTOKOLL_LAUF_MAX_ZEICHEN
# (Qt-Meldungen eigens höchstens _PROTOKOLL_QT_MAX_ZEICHEN, damit sie keinen späteren
# Fehler verdrängen), und ein wiederkehrender gleicher Eintrag (Fehler in paintEvent/Timer,
# Qt-Warnung) wird nur gezählt.
ABSTURZPROTOKOLL_ALT_DATEINAME = "absturzprotokoll.alt.txt"
_ABSTURZPROTOKOLL_MAX_BYTES = 1_000_000
_PROTOKOLL_LAUF_MAX_ZEICHEN = 1_000_000
_PROTOKOLL_QT_MAX_ZEICHEN = 200_000
_PROTOKOLL_MAX_EINTRAGSARTEN = 1000
# faulthandler schreibt im Absturzfall direkt in diese (offen gehaltene) Datei.
_absturzprotokoll_datei = None
# Pfad der Datei für "Diagnose kopieren" und "Protokoll-Ordner öffnen" (None: nicht eingerichtet).
_absturzprotokoll_pfad = None


def absturzprotokoll_einrichten(version: str, ordner=None):
    """Richtet das Absturzprotokoll ein und liefert den Pfad der Datei (oder None, wenn sie
    nicht geschrieben werden kann - das Programm startet dann trotzdem normal). `ordner`
    ist standardmäßig der Programmordner im Benutzerprofil (neben "Termine")."""
    global _absturzprotokoll_datei, _absturzprotokoll_pfad
    import datetime
    import faulthandler
    import traceback
    from pathlib import Path

    from db import termine_ordner

    try:
        pfad = Path(ordner if ordner is not None else termine_ordner().parent) / ABSTURZPROTOKOLL_DATEINAME
        if pfad.exists() and pfad.stat().st_size > _ABSTURZPROTOKOLL_MAX_BYTES:
            try:
                os.replace(pfad, pfad.with_name(ABSTURZPROTOKOLL_ALT_DATEINAME))
            except OSError:
                # Lässt sich nicht umbenennen (unter Windows z. B., weil ein zweites
                # Programmfenster die Datei offen hält): weiter anhängen statt die Einträge
                # des anderen Fensters zu löschen.
                pass
        datei = open(pfad, "a", encoding="utf-8")
        datei.write(f"--- Start {datetime.datetime.now():%Y-%m-%d %H:%M:%S}, Version {version} ---\n")
        datei.flush()
    except OSError:
        return None

    _absturzprotokoll_datei = datei
    _absturzprotokoll_pfad = pfad
    faulthandler.enable(file=datei, all_threads=True)
    atexit.register(_wiederholungen_schreiben, datei)

    bisheriger_hook = sys.excepthook

    def _protokollieren(typ, wert, tb):
        _protokoll_eintrag("Unbehandelter Fehler", "".join(traceback.format_exception(typ, wert, tb)))
        try:
            bisheriger_hook(typ, wert, tb)
        except Exception:  # noqa: BLE001 - ohne Konsole (sys.stderr None) darf das nicht stören
            pass

    sys.excepthook = _protokollieren
    return pfad


# Zustand des Protokolls im laufenden Programm (gehört zu der Datei in "datei"; wechselt
# sie, beginnt die Zählung neu): geschriebene Zeichen (getrennt für Qt-Meldungen) und je
# Eintrag die Zahl der ausgelassenen Wiederholungen. Die Sperre ist wiederbetretbar, und
# "aktiv" verwirft einen Eintrag, der im selben Thread während des Schreibens entsteht
# (z. B. eine Qt-Warnung aus einem Destruktor, den die Speicherbereinigung gerade auslöst) -
# sonst blockierte sich der Thread selbst.
_protokoll_sperre = threading.RLock()
_protokoll_zustand: dict = {"datei": None, "zeichen": {}, "eintraege": {}, "aktiv": False}


def _protokoll_eintrag(kopf: str, inhalt: str, *, qt_meldung: bool = False) -> None:
    """Schreibt einen Eintrag ins Absturzprotokoll (sofern eingerichtet). Ein bereits
    geschriebener gleicher Eintrag wird nur gezählt (siehe _wiederholungen_schreiben), und
    ist das Höchstmaß je Lauf erreicht, entfällt der Rest (Teil 9 Nr. 4)."""
    import datetime

    datei = _absturzprotokoll_datei
    if datei is None:
        return
    with _protokoll_sperre:
        zustand = _protokoll_zustand
        if zustand["aktiv"]:
            return
        zustand["aktiv"] = True
        try:
            if zustand["datei"] is not datei:
                zustand.update(datei=datei, zeichen={}, eintraege={})
            eintraege = zustand["eintraege"]
            if inhalt in eintraege:
                eintraege[inhalt] += 1
                return
            if len(eintraege) < _PROTOKOLL_MAX_EINTRAGSARTEN:
                eintraege[inhalt] = 0
            grenze = _PROTOKOLL_QT_MAX_ZEICHEN if qt_meldung else _PROTOKOLL_LAUF_MAX_ZEICHEN
            bisher = zustand["zeichen"].get(qt_meldung, 0)
            if bisher >= grenze:
                return
            text = f"{kopf} {datetime.datetime.now():%Y-%m-%d %H:%M:%S}:\n{inhalt}"
            if not text.endswith("\n"):
                text += "\n"
            if bisher + len(text) > grenze:
                art = "Qt-Meldungen" if qt_meldung else "Einträge"
                text = f"--- Protokoll für diesen Programmlauf voll, weitere {art} entfallen ---\n"
                zustand["zeichen"][qt_meldung] = grenze
            else:
                zustand["zeichen"][qt_meldung] = bisher + len(text)
            try:
                datei.write(text)
                datei.flush()
            except (OSError, ValueError):
                pass
        finally:
            zustand["aktiv"] = False


def _wiederholungen_schreiben(datei) -> None:
    """Beim Programmende: wie oft sich welche Einträge wiederholt haben."""
    with _protokoll_sperre:
        zustand = _protokoll_zustand
        if zustand["datei"] is not datei:
            return
        wiederholt = [(n, inhalt) for inhalt, n in zustand["eintraege"].items() if n]
        zustand["eintraege"] = {}
    if not wiederholt:
        return
    zeilen = ["Wiederholte Einträge in diesem Programmlauf:"]
    for anzahl, inhalt in sorted(wiederholt, reverse=True)[:20]:
        letzte = (inhalt.strip().splitlines() or [""])[-1]
        zeilen.append(f"  {anzahl}× wiederholt: {letzte}")
    try:
        datei.write("\n".join(zeilen) + "\n")
        datei.flush()
    except (OSError, ValueError):
        pass


def fehler_protokollieren(exc: BaseException) -> None:
    """Schreibt einen abgefangenen Fehler samt Traceback ins Absturzprotokoll (sofern
    eingerichtet) - für Stellen, die einen Fehler selbst melden, damit er trotzdem in
    „Diagnose kopieren“ auftaucht."""
    import traceback

    _protokoll_eintrag("Abgefangener Fehler",
                       "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))


def qt_meldungen_protokollieren():
    """Desktop-Prüfung 14.10.2026 (Teil 9 Nr. 8): Qt-Warnungen und -Fehler (z. B. „Could not
    parse application stylesheet“) gehen im installierten Programm ohne Konsole sonst
    verloren - jetzt landen sie im Absturzprotokoll (Wiederholungen nur gezählt) und, falls
    vorhanden, weiter auf der Konsole."""
    from PySide6.QtCore import QtMsgType, qInstallMessageHandler

    protokollieren = (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg)

    def _qt_meldung(art, _kontext, text) -> None:
        if art in protokollieren:
            _protokoll_eintrag("Qt-Meldung", text, qt_meldung=True)
        if sys.stderr is not None:
            try:
                print(text, file=sys.stderr)
            except (OSError, ValueError):
                pass

    return qInstallMessageHandler(_qt_meldung)


def absturzprotokoll_pfad():
    """Pfad des Absturzprotokolls dieses Programmlaufs, oder None, wenn es nicht
    eingerichtet werden konnte."""
    return _absturzprotokoll_pfad


# Rückmeldung Marco 13.10.2026 ("lohnt sich ein Fehler-Dump?"): statt eines Dumps mit der
# Termin-Datenbank (Personendaten) gibt es einen kopierbaren Diagnose-Text - Version, System
# und das Ende des Absturzprotokolls, ohne Benutzerpfad. Nichts wird automatisch verschickt.
_DIAGNOSE_PROTOKOLL_ZEILEN = 40
_BENUTZER_PLATZHALTER = "<Benutzer>"


def _kurzpfad(pfad: str) -> str | None:
    """Windows-8.3-Kurzform eines Pfads (z. B. C:\\Users\\MAXMUS~1), sonst None."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes

        puffer = ctypes.create_unicode_buffer(1024)
        if ctypes.windll.kernel32.GetShortPathNameW(pfad, puffer, len(puffer)):
            return puffer.value
    except (OSError, AttributeError, ValueError):
        pass
    return None


def _ohne_benutzerpfad(text: str) -> str:
    """Ersetzt den Benutzerordner durch "~" und den Benutzernamen durch "<Benutzer>" - in
    allen üblichen Schreibweisen: mit "\\", "/" oder (aus repr() in Fehlertexten) "\\\\",
    in beliebiger Groß-/Kleinschreibung und als Windows-Kurzpfad."""
    import re
    from pathlib import Path

    try:
        heim = str(Path.home())
    except (OSError, RuntimeError):
        return text
    if len(heim) <= 3:  # "/", "C:\" - kein eigener Benutzerordner erkennbar
        return text
    formen = {heim}
    kurz = _kurzpfad(heim)
    if kurz:
        formen.add(kurz)
    for form in list(formen):
        formen |= {form.replace("\\", "/"), form.replace("\\", "\\\\"), form.replace("/", "\\\\")}
    # Längste Form zuerst; nur ganze Ordnernamen (danach Trenner, Anführungszeichen o. Ä.).
    for form in sorted(formen, key=len, reverse=True):
        text = re.sub(re.escape(form) + r"(?![\w.~-])", "~", text, flags=re.IGNORECASE)
    namen = {Path(heim).name, os.environ.get("USERNAME", ""), os.environ.get("USER", "")}
    if kurz:
        namen.add(Path(kurz).name)
    for name in sorted((n for n in namen if len(n) >= 3), key=len, reverse=True):
        text = re.sub(r"(?<![\w~])" + re.escape(name) + r"(?![\w~])", _BENUTZER_PLATZHALTER, text,
                      flags=re.IGNORECASE)
    return text


def diagnose_text(version: str, fehler: str | None = None) -> str:
    """Kopierbarer Text für eine Fehlermeldung: Version, System, ggf. der aktuelle Fehler
    und die letzten Zeilen des Absturzprotokolls. Löst selbst keine Exception aus - fehlt
    eine Angabe, steht dort "(unbekannt)"."""
    def _angabe(abfrage) -> str:
        try:
            return str(abfrage())
        except Exception:  # noqa: BLE001 - die Diagnose soll im Fehlerfall immer entstehen
            return "(unbekannt)"

    def _system() -> str:
        import platform

        return platform.platform()

    def _versionen() -> str:
        import platform

        from PySide6 import __version__ as pyside_version
        from PySide6.QtCore import qVersion

        return f"Python {platform.python_version()}, PySide6 {pyside_version}, Qt {qVersion()}"

    zeilen = [
        "SHS-Prüfungsprogramm – Diagnose",
        f"Version: {version}",
        f"System: {_angabe(_system)}",
        _angabe(_versionen),
        f"Installiertes Programm: {'ja' if getattr(sys, 'frozen', False) else 'nein'}",
    ]
    pfad = _absturzprotokoll_pfad
    zeilen.append(f"Absturzprotokoll: {pfad if pfad is not None else '(nicht eingerichtet)'}")
    ende = None
    if pfad is not None:
        try:
            with open(pfad, encoding="utf-8", errors="replace") as datei:
                ende = datei.read().splitlines()[-_DIAGNOSE_PROTOKOLL_ZEILEN:]
        except (OSError, ValueError):
            ende = ["(nicht lesbar)"]
        else:
            # Ist die aktuelle Datei noch kurz (etwa nach der Rotation, Teil 9 Nr. 4), mit dem
            # Ende der alten Datei auffüllen.
            if len(ende) < _DIAGNOSE_PROTOKOLL_ZEILEN:
                try:
                    with open(Path(pfad).with_name(ABSTURZPROTOKOLL_ALT_DATEINAME),
                              encoding="utf-8", errors="replace") as alt:
                        ende = (alt.read().splitlines() + ende)[-_DIAGNOSE_PROTOKOLL_ZEILEN:]
                except (OSError, ValueError):
                    pass
    # Der aktuelle Fehler steht meist schon am Ende des Protokolls (der Protokoll-Hook
    # schreibt vorher) - nur gesondert aufführen, wenn er dort fehlt bzw. abgeschnitten ist.
    if fehler and (ende is None or fehler.rstrip() not in "\n".join(ende)):
        zeilen += ["", "Aktueller Fehler:", fehler.rstrip()]
    if ende is not None:
        zeilen += ["", f"Absturzprotokoll (letzte {_DIAGNOSE_PROTOKOLL_ZEILEN} Zeilen):", *ende]
    return _ohne_benutzerpfad("\n".join(zeilen)) + "\n"


def fehlerfenster_zeigen(version: str, fehler: str, parent=None, programm_endet: bool = False) -> None:
    """Meldung zu einem unerwarteten Fehler mit [Fehlerbericht kopieren]
    [Protokoll-Ordner öffnen] [OK]; der Traceback steht unter "Details". Ohne `parent`
    erscheint sie über dem aktiven Programmfenster."""
    from PySide6.QtWidgets import QApplication

    box = QMessageBox(parent if parent is not None else QApplication.activeWindow())
    box.setTextFormat(Qt.PlainText)  # S-1: Fehlertexte können Namen enthalten
    box.setIcon(QMessageBox.Critical)
    box.setWindowTitle("Unerwarteter Fehler")
    # programm_endet: Fehler in main(), nach dem das Programm sich ohnehin beendet - dann nicht
    # zum Weiterarbeiten auffordern (Desktop-Prüfung 14.10.2026, Teil 9 Nr. 7).
    weiter = (
        "Das Programm wird beendet. Bitte erneut starten."
        if programm_endet else
        "Falls etwas nicht wie erwartet aussieht, den Termin neu öffnen bzw. das Programm neu starten."
    )
    box.setText(
        "Es ist ein unerwarteter Fehler aufgetreten. Bereits gespeicherte Daten bleiben "
        f"erhalten. {weiter}\n\n"
        "Für eine Fehlermeldung „Fehlerbericht kopieren“ und den Text einfügen – vorher kurz "
        "prüfen, ob Teilnehmerdaten darin stehen."
    )
    box.setDetailedText(_ohne_benutzerpfad(fehler))
    kopieren_btn = box.addButton("Fehlerbericht kopieren", QMessageBox.ActionRole)
    # Kopieren soll das Fenster nicht schließen: die interne Schließ-Verbindung lösen.
    kopieren_btn.clicked.disconnect()

    def _kopieren() -> None:
        QApplication.clipboard().setText(diagnose_text(version, fehler))
        kopieren_btn.setText("Fehlerbericht kopiert")

    kopieren_btn.clicked.connect(_kopieren)
    ordner_btn = None
    if _absturzprotokoll_pfad is not None:
        ordner_btn = box.addButton("Protokoll-Ordner öffnen", QMessageBox.ActionRole)
    box.setDefaultButton(box.addButton(QMessageBox.Ok))
    _ausfuehren(box)
    if ordner_btn is not None and box.clickedButton() is ordner_btn:
        _ordner_zeigen(str(_absturzprotokoll_pfad), parent)


_fehlerfenster_offen = False
# Bereits gezeigte Fehlerbilder (Typ + Stelle) - ein ständig wiederkehrender Fehler (z. B. in
# einem Timer oder beim Zeichnen) öffnet so nicht nach jedem OK sofort das nächste Fenster.
_gezeigte_fehler: set = set()


def _fehlerbild(typ, tb) -> tuple:
    import traceback

    stellen = traceback.extract_tb(tb) if tb is not None else []
    stelle = stellen[-1] if stellen else None
    return (typ.__qualname__, stelle.filename if stelle else "", stelle.lineno if stelle else 0)


def fehlerfenster_einrichten(version: str) -> None:
    """Zeigt bei unbehandelten Fehlern (bisher nur still im Absturzprotokoll) zusätzlich ein
    Fenster. Nach dem Absturzprotokoll und nach dem Anlegen der QApplication aufrufen: der
    bisherige Hook protokolliert weiterhin zuerst. Jedes Fehlerbild erscheint nur einmal je
    Sitzung, nie zwei Fenster gleichzeitig; Fehler beim Anzeigen gehen nur ins Protokoll."""
    import traceback

    from PySide6.QtWidgets import QApplication

    bisheriger_hook = sys.excepthook

    def _melden(typ, wert, tb):
        global _fehlerfenster_offen
        try:
            bisheriger_hook(typ, wert, tb)
        except Exception:  # noqa: BLE001 - z. B. Standard-Hook ohne Konsole; Fenster trotzdem
            pass
        if (_fehlerfenster_offen or issubclass(typ, (KeyboardInterrupt, SystemExit))
                or threading.current_thread() is not threading.main_thread()
                or QApplication.instance() is None):
            return
        bild = _fehlerbild(typ, tb)
        if bild in _gezeigte_fehler:
            return
        _gezeigte_fehler.add(bild)
        _fehlerfenster_offen = True
        try:
            fehlerfenster_zeigen(version, "".join(traceback.format_exception(typ, wert, tb)))
        except Exception:  # noqa: BLE001 - das Protokoll bleibt der Rückfallweg
            pass
        finally:
            _fehlerfenster_offen = False

    sys.excepthook = _melden
