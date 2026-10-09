"""Gemeinsame Hilfen der Desktop-Oberfläche: Ablageorte und PDF-Speicherdialoge,
Fehlermeldungen, responsive Schriftgrößen, Tabellen-Hilfsklassen und Spaltenkonstanten
der Ergebnistabelle.

Aus app.py ausgelagert (Codex-Architekturprüfung 27.09.2026); rein interne Umstellung,
Aussehen und Verhalten sind unverändert. Die Abhängigkeiten laufen nur in eine Richtung:
app -> desktop_dialoge -> desktop_gemeinsam, app -> desktop_darstellung (jeweils -> db/
pdf_export); keines dieser Module importiert app.
"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QLibraryInfo, QLocale, Qt, QTranslator, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (
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
    jedem Aufruf den kompletten Datensatz, da es keine partiellen Updates kennt."""
    aktuell = get_veranstaltung(conn) or {}
    werte = {
        "verein": aktuell.get("verein") or "",
        "datum": aktuell.get("datum") or "",
        "ort": aktuell.get("ort"),
        "vereins_nr": aktuell.get("vereins_nr"),
        "pruefungsnummer": aktuell.get("pruefungsnummer"),
        "wertungsrichter_1": aktuell.get("wertungsrichter_1"),
        "wertungsrichter_2": aktuell.get("wertungsrichter_2"),
        "wertungsrichter_3": aktuell.get("wertungsrichter_3"),
        "wertungsrichter_4": aktuell.get("wertungsrichter_4"),
        "wertungsrichter_5": aktuell.get("wertungsrichter_5"),
        "pruefungsleiter": aktuell.get("pruefungsleiter"),
        "pruefungsgebuehr_ed": aktuell.get("pruefungsgebuehr_ed"),
        "pruefungsgebuehr_dk": aktuell.get("pruefungsgebuehr_dk"),
        "zeitplan_start": aktuell.get("zeitplan_start"),
        # Nutzerwunsch 28.09.2026 (Anmeldeformular) - sonst gingen diese Felder bei jeder
        # Änderung aus einem anderen Tab (z. B. Zeitplan-Start) verloren.
        "verband": aktuell.get("verband"),
        "meldestelle": aktuell.get("meldestelle"),
        "angebotene_pruefungen": aktuell.get("angebotene_pruefungen"),
        "startnummer_bereiche": aktuell.get("startnummer_bereiche"),  # UX-Test U1
        "dk_mindestabstand": aktuell.get("dk_mindestabstand"),  # UX-Test U2
        "startnummer_bereichsgroesse": aktuell.get("startnummer_bereichsgroesse"),  # Marco 09.10.2026
    }
    werte.update(overrides)
    set_veranstaltung(conn, **werte)


class _Ablageort:
    """Gemeinsamer, veränderlicher Ablageort für alle PDF-Export-Buttons EINES Termins
    (Tabs "Zeitplan" und "Export", seit 23.09. auch der Druck-Button im Tab "Auswertung")
    - ein einzelnes, von allen diesen Tabs geteiltes Objekt statt
    je ein eigener String pro Tab. Wählt der Nutzer beim Speichern bewusst einen anderen
    Ordner, gilt dieser dadurch sofort auch als neuer Standard-Speicherort im jeweils
    ANDEREN Tab, statt dass beide unabhängig voneinander ihren eigenen (dann ggf.
    unterschiedlichen) Ablageort verfolgen."""

    def __init__(self, pfad: str):
        self.pfad = pfad


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


def _ordner_zeigen(pfad: str) -> None:
    """Öffnet den Explorer mit markierter Datei (Windows) bzw. den Ordner."""
    if sys.platform == "win32" and os.path.isfile(pfad):
        import subprocess

        subprocess.Popen(["explorer", "/select,", _pfad_anzeige(pfad)])
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(pfad) if os.path.isfile(pfad) else pfad))


def _datei_gespeichert_melden(parent, pfad: str, titel: str, datei_oeffnen_text: str | None = "PDF öffnen") -> None:
    """Meldung nach dem Speichern mit den nächsten Schritten [PDF öffnen] [Ordner zeigen]
    [OK] - statt nur einer leicht übersehenen Statuszeile."""
    box = QMessageBox(parent)
    box.setTextFormat(Qt.PlainText)  # S-1: Pfade/Namen nie als HTML deuten
    box.setIcon(QMessageBox.Information)
    box.setWindowTitle(titel)
    box.setText(f"Gespeichert unter:\n{_pfad_anzeige(pfad)}")
    oeffnen_btn = box.addButton(datei_oeffnen_text, QMessageBox.ActionRole) if datei_oeffnen_text else None
    ordner_btn = box.addButton("Ordner zeigen", QMessageBox.ActionRole)
    box.setDefaultButton(box.addButton(QMessageBox.Ok))
    box.exec()
    if oeffnen_btn is not None and box.clickedButton() is oeffnen_btn:
        QDesktopServices.openUrl(QUrl.fromLocalFile(pfad))
    elif box.clickedButton() is ordner_btn:
        _ordner_zeigen(pfad)


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
    QMessageBox.critical(
        parent, "PDF konnte nicht erstellt werden",
        f"Der Export ist fehlgeschlagen (z.B. Zielpfad nicht schreibbar oder Datei "
        f"gerade in einem anderen Programm geöffnet):\n\n{exc}",
    )


def _zeitplan_pdf_exportieren(parent, conn, ablageort: "_Ablageort", status_label: QLabel) -> None:
    """Gemeinsame Umsetzung für den Zeitplan-PDF-Export - vorher wortgleich in
    ZeitplanTab._pdf_exportieren und ExportTab._zeitplan_exportieren dupliziert."""
    # UX-Test 02.10.2026, U2: nicht unbemerkt einen Plan mit doppelt eingeplanten Teams
    # verschicken.
    konflikte = zeitplan_ueberschneidungen(conn)
    if konflikte:
        antwort = QMessageBox.question(
            parent, "Überschneidungen im Zeitplan",
            f"Im Zeitplan gibt es {len(konflikte)} Überschneidung(en): Teams stehen gleichzeitig "
            "bzw. ohne Mindestabstand an zwei Stellen (im Reiter „Zeitplan“ rot markiert).\n\n"
            "Trotzdem als PDF speichern?",
        )
        if antwort != QMessageBox.Yes:
            return
    pfad = _pdf_speicherort_waehlen(parent, ablageort, "Zeitplan speichern", _export_dateiname(conn, "Zeitplan"))
    if not pfad:
        return
    try:
        pdf_export.erstelle_zeitplan_pdf(conn, pfad)
    except Exception as exc:
        _pdf_export_fehler_anzeigen(parent, exc)
        return
    status_label.setText(f"Zeitplan gespeichert: {_pfad_anzeige(pfad)}")
    _datei_gespeichert_melden(parent, pfad, "Zeitplan gespeichert")


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
        pt = _responsive_schriftgroesse(self.width())
        self.setStyleSheet(f"QHeaderView::section {{ font-size: {pt:.1f}pt; }} QLabel {{ font-size: {pt:.1f}pt; }}")


def _fehler_anzeigen(parent, exc: Exception) -> None:
    """Zeigt einen Datenbankfehler (z.B. verletzte Fachregel) als Dialog statt die App abstürzen zu lassen."""
    QMessageBox.critical(
        parent,
        "Eingabe konnte nicht gespeichert werden",
        f"Die Daten verletzen eine Fachregel und wurden nicht gespeichert:\n\n{exc}",
    )


def _db_fehler_anzeigen(parent, exc: Exception) -> None:
    """Zeigt einen unerwarteten Datenbankfehler (z.B. gesperrte Datei, voller Datenträger) als
    Dialog statt die App abstürzen zu lassen - für einfache Aktionen ohne eigene
    Fachregel-Prüfung (Richter/Zeitplan verwalten u.ä.), bei denen ein sqlite3.Error bisher
    unbehandelt durchschlug."""
    QMessageBox.critical(
        parent,
        "Datenbankfehler",
        f"Die Änderung konnte nicht gespeichert werden:\n\n{exc}",
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
            return QMessageBox.StandardButton(box.exec())
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
_ABSTURZPROTOKOLL_MAX_BYTES = 1_000_000
# faulthandler schreibt im Absturzfall direkt in diese (offen gehaltene) Datei.
_absturzprotokoll_datei = None


def absturzprotokoll_einrichten(version: str, ordner=None):
    """Richtet das Absturzprotokoll ein und liefert den Pfad der Datei (oder None, wenn sie
    nicht geschrieben werden kann - das Programm startet dann trotzdem normal). `ordner`
    ist standardmäßig der Programmordner im Benutzerprofil (neben "Termine")."""
    global _absturzprotokoll_datei
    import datetime
    import faulthandler
    import traceback
    from pathlib import Path

    from db import termine_ordner

    try:
        pfad = Path(ordner if ordner is not None else termine_ordner().parent) / ABSTURZPROTOKOLL_DATEINAME
        # Größe begrenzen: wird die Datei zu groß, beginnt sie von vorn.
        modus = "w" if pfad.exists() and pfad.stat().st_size > _ABSTURZPROTOKOLL_MAX_BYTES else "a"
        datei = open(pfad, modus, encoding="utf-8")
        datei.write(f"--- Start {datetime.datetime.now():%Y-%m-%d %H:%M:%S}, Version {version} ---\n")
        datei.flush()
    except OSError:
        return None

    _absturzprotokoll_datei = datei
    faulthandler.enable(file=datei, all_threads=True)

    bisheriger_hook = sys.excepthook

    def _protokollieren(typ, wert, tb):
        try:
            datei.write(f"Unbehandelter Fehler {datetime.datetime.now():%Y-%m-%d %H:%M:%S}:\n")
            datei.write("".join(traceback.format_exception(typ, wert, tb)))
            datei.flush()
        except (OSError, ValueError):
            pass
        try:
            bisheriger_hook(typ, wert, tb)
        except Exception:  # noqa: BLE001 - ohne Konsole (sys.stderr None) darf das nicht stören
            pass

    sys.excepthook = _protokollieren
    return pfad
