"""
Meldungen und Abläufe rund um Importe der Desktop-Oberfläche (seit 11.11.2026 aus
desktop_teilnehmer.py ausgelagert, Code unverändert): Abschlussmeldungen nach CSV-, OMA-,
Formular- und Termin-Import, Rückfrage zur Startnummernvergabe, Datenbankfehler beim Import.
Bewusst KEIN `import app` (siehe desktop_programm.py).
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMessageBox,
)

from db import (
    get_veranstaltung,
    leistungsklasse_label,
    list_teilnehmer,
    fehlende_startnummern_vergeben,
    teilnehmer_ohne_startnummer,
    pruefung_nach_kuerzel,
    startnummer_bereiche,
)
from db_import import (
    importiere_teilnehmer_aus_csv,
    rat_bei_ablehnung,
)
from desktop_gemeinsam import (
    _klartext_fehler,
    _db_fehler_anzeigen,
    _ja_nein,
    _import_ordner_merken,
    _import_startordner,
    _ausfuehren,
)


def _pruefung_bezeichnung(kuerzel: str) -> str:
    """Bezeichnung einer Prüfung wie im Filter Art/LK (seit N5 überall dieselbe)."""
    pruefung = pruefung_nach_kuerzel(kuerzel)
    return pruefung.bezeichnung if pruefung is not None else kuerzel


def _fehlende_startnummern_vergeben_mit_meldung(
    parent, conn, pruefung: str | None = None, bezeichnung: str | None = None
) -> None:
    """UX-Test 02.10.2026, U1: Sammelvergabe (db.fehlende_startnummern_vergeben) mit
    verständlicher Abschlussmeldung - wer hat eine Nummer bekommen, wer nicht und warum.
    Mit `pruefung`/`bezeichnung` nur für diese Prüfung (Filter Art/LK, Marco 09.10.2026)."""
    if not startnummer_bereiche(get_veranstaltung(conn)):
        QMessageBox.information(
            parent, "Keine Startnummern-Bereiche",
            "Bitte zuerst in den Veranstaltungsdaten (Reiter „Verwaltung“ → "
            "„Veranstaltungsdaten bearbeiten…“) je Prüfung einen Startnummern-Bereich "
            "eintragen, z. B. DK LK 1: 1 bis 20.",
        )
        return
    try:
        ergebnis = fehlende_startnummern_vergeben(conn, pruefung)
    except sqlite3.Error as exc:
        _db_fehler_anzeigen(parent, exc)
        return

    def namen(liste):
        return [f"{t['vorname']} {t['nachname']} – {leistungsklasse_label(t)}" for t in liste]

    wo = f" in „{bezeichnung}“" if bezeichnung else ""
    _meldung_mit_listen(parent, "Startnummern vergeben", f"{len(ergebnis.vergeben)} Startnummer(n){wo} vergeben.", [
        ("Keine Nummer, weil für die Prüfung kein Bereich eingetragen ist:", namen(ergebnis.ohne_bereich)),
        ("Keine Nummer, weil der Bereich der Prüfung voll ist:", namen(ergebnis.bereich_voll)),
    ])


# Desktop-Prüfung 14.10.2026 (Teil 1 Nr. 4, Teil 5 Nr. 5): lange Namenslisten machten die
# Meldung höher als den Bildschirm (OK-Knopf nicht mehr sichtbar) - jetzt höchstens so viele
# Einträge je Liste, die vollständige Liste steht unter „Details“.
_MELDUNG_LISTE_MAX = 15


def _meldungstext_voll(einleitung: str, abschnitte: list[tuple[str, list[str]]]) -> str:
    """Der ungekürzte Text einer _meldung_mit_listen-Meldung (leere Abschnitte entfallen)."""
    return einleitung + "".join(
        f"\n\n{ueberschrift}\n" + "\n".join(eintraege) for ueberschrift, eintraege in abschnitte if eintraege
    )


def _meldung_mit_listen(parent, titel: str, einleitung: str, abschnitte: list[tuple[str, list[str]]],
                        warnung: bool = False, kopieren: bool = False) -> None:
    """Informationsmeldung aus `einleitung` und Abschnitten (Überschrift, Einträge); leere
    Abschnitte entfallen. Ist eine Liste länger als _MELDUNG_LISTE_MAX, wird sie gekürzt
    und die vollständige Fassung über „Details“ angeboten. UX-Test 03.11.2026, X10:
    `warnung` zeigt das Warnsymbol statt „i“, `kopieren` einen Knopf „Meldung kopieren und schließen“ - die
    Liste war nach „OK“ sonst nirgends mehr nachzulesen."""
    kurz = einleitung
    voll = _meldungstext_voll(einleitung, abschnitte)
    gekuerzt = False
    for ueberschrift, eintraege in abschnitte:
        if not eintraege:
            continue
        zeilen = list(eintraege[:_MELDUNG_LISTE_MAX])
        if len(eintraege) > _MELDUNG_LISTE_MAX:
            zeilen.append(f"… und {len(eintraege) - _MELDUNG_LISTE_MAX} weitere (siehe „Details“)")
            gekuerzt = True
        kurz += f"\n\n{ueberschrift}\n" + "\n".join(zeilen)
    if not (gekuerzt or warnung or kopieren):
        QMessageBox.information(parent, titel, kurz)
        return
    box = QMessageBox(parent)
    box.setTextFormat(Qt.PlainText)
    box.setIcon(QMessageBox.Warning if warnung else QMessageBox.Information)
    box.setWindowTitle(titel)
    box.setText(kurz)
    if gekuerzt:
        box.setDetailedText(voll)
    box.setStandardButtons(QMessageBox.Ok)
    kopieren_btn = box.addButton("Meldung kopieren und schließen", QMessageBox.ActionRole) if kopieren else None
    box.setDefaultButton(QMessageBox.Ok)
    # Mit dem Zusatzknopf findet Qt sonst keine Esc-Taste mehr (Verifikation A8, Befund 1).
    box.setEscapeButton(QMessageBox.Ok)
    _ausfuehren(box)
    if kopieren_btn is not None and box.clickedButton() is kopieren_btn:
        QApplication.clipboard().setText(voll)


#: UX-Test 03.11.2026, X10: was mit abgelehnten Meldungen zu tun ist (vorher fehlte der Rat).
_RAT_BEI_ABLEHNUNG = ("Abgelehnte Meldungen: beim Teilnehmer nachfragen und von Hand erfassen "
                      "(„Teilnehmer hinzufügen…“) oder korrigiert erneut einlesen – bereits "
                      "übernommene Meldungen werden dabei nicht doppelt angelegt. Ist die ganze "
                      "Datei betroffen, die Datei prüfen und erneut einlesen. Mit dem Kopier-Knopf "
                      "lässt sich alles z. B. in eine E-Mail einfügen; nachlesbar bleibt es im "
                      "Reiter „Formular-Import“ unter „Letzter Import“.")


def _letzten_import_zeigen(parent, text: str) -> None:
    """UX-Test 2026-11, T2: Die Abschlussmeldung eines Imports bleibt im Reiter
    „Formular-Import“ unter „Letzter Import“ nachlesbar - nach „OK“ (oder Enter) war die
    Ablehnungsliste sonst weg. Gilt auch für Importe aus dem Reiter „Teilnehmer“."""
    # Kein isinstance(parent, FormularImportTab): der Reiter liegt in desktop_formular.py, das
    # dieses Modul importiert (sonst ein Importkreis).
    if hasattr(parent, "letzten_import_zeigen"):
        tab = parent
    else:
        tab = getattr(parent.window(), "formular_import_tab", None) if parent is not None else None
    if tab is not None:
        tab.letzten_import_zeigen(text)


def _import_ergebnis_melden(parent, ergebnis, fehler_ueberschrift: str = "Zeile(n) übersprungen:") -> None:
    """Gemeinsame Abschlussmeldung für CSV-, OMA- und Anmeldeformular-Import (Teil 5 Nr. 5)."""
    einleitung = f"{ergebnis.importiert} Teilnehmer importiert."
    abschnitte = [
        # UX-Nachtest 03.10.2026, N1: bereits vorhandene Meldungen werden nicht doppelt angelegt.
        (f"{len(ergebnis.uebersprungen)} Meldung(en) bereits vorhanden, nicht erneut angelegt:",
         ergebnis.uebersprungen),
        # Nachtest 2 (N12): unter jedem abgelehnten Eintrag ein Rat passend zum Grund.
        (f"{len(ergebnis.fehler)} {fehler_ueberschrift}",
         [f"{fehler}\n   → {rat}" if (rat := rat_bei_ablehnung(fehler)) else fehler
          for fehler in ergebnis.fehler]),
        ("Was tun?", [_RAT_BEI_ABLEHNUNG] if ergebnis.fehler else []),
        ("Hinweis:", ergebnis.hinweise),
    ]
    _letzten_import_zeigen(parent, _meldungstext_voll(einleitung, abschnitte))
    _meldung_mit_listen(parent, "Import abgeschlossen", einleitung, abschnitte,
                        warnung=bool(ergebnis.fehler), kopieren=bool(ergebnis.fehler or ergebnis.uebersprungen))


_NICHTS_ZU_TAUSCHEN = ("Beide Teilnehmer haben noch keine Startnummer. Startnummern vergibst du "
                       "mit „Fehlende Startnummern vergeben…“ oder über „Bearbeiten…“.")


def _teilnehmerzahl(conn) -> int | None:
    try:
        return len(list_teilnehmer(conn))
    except sqlite3.Error:
        return None


def _ohne_startnummer_ids(conn) -> set[int] | None:
    """IDs der Teilnehmenden ohne Startnummer - vor einem Import gemerkt, damit die Rückfrage
    danach nur kommt, wenn der Import selbst neue Teilnehmer ohne Nummer gebracht hat."""
    try:
        return {t["id"] for t in teilnehmer_ohne_startnummer(conn)}
    except sqlite3.Error:
        return None


def _startnummern_nach_import_anbieten(parent, conn, vorher_ohne: set[int] | None = None) -> None:
    """UX-Test 02.10.2026, U1: Nach einem Import fehlen die Startnummern meist - direkt
    anbieten, sie gesammelt zu vergeben. Bewusst immer für alle Prüfungen, auch wenn im
    Reiter "Teilnehmer" ein Filter Art/LK gesetzt ist (Marco 09.10.2026). UX-Test 03.11.2026
    (X10/L-B): nur, wenn der Import neue Teilnehmer ohne Nummer gebracht hat (`vorher_ohne`)."""
    ohne = teilnehmer_ohne_startnummer(conn)
    if not ohne:
        return
    if vorher_ohne is not None and all(t["id"] in vorher_ohne for t in ohne):
        return
    haben = "hat" if len(ohne) == 1 else "haben"
    if not startnummer_bereiche(get_veranstaltung(conn)):
        QMessageBox.information(
            parent, "Startnummern fehlen",
            f"{len(ohne)} Teilnehmer {haben} noch keine Startnummer. Für die gesammelte Vergabe "
            "(„Fehlende Startnummern vergeben…“ im Reiter „Teilnehmer“) zuerst je Prüfung einen "
            "Startnummern-Bereich in den Veranstaltungsdaten eintragen (Reiter „Verwaltung“).",
        )
        return
    if _ja_nein(
        parent, "Startnummern fehlen",
        f"{len(ohne)} Teilnehmer {haben} noch keine Startnummer.\n\nJetzt „Fehlende "
        "Startnummern vergeben“? (Bereits vergebene Nummern bleiben unverändert.)",
        vorgabe_ja=True,
    ):
        _fehlende_startnummern_vergeben_mit_meldung(parent, conn)


def _import_db_fehler_melden(parent, exc: sqlite3.Error, conn=None, vorher: int | None = None,
                             einleitung: str = "Der Import wurde abgebrochen.") -> None:
    """Schreibfehler der Termin-Datei mitten in einem Import (Desktop-Prüfung 14.10.2026):
    die bis dahin übernommenen Teilnehmer bleiben gespeichert (Commit je Zeile). Mit `conn`
    und `vorher` (Teilnehmerzahl vor dem Import) nennt die Meldung, wie viele es sind (aus A4)."""
    nachher = _teilnehmerzahl(conn) if conn is not None and vorher is not None else None
    if nachher is not None:
        n = nachher - vorher
        anzahl = (f"{n} Teilnehmer wurde bis dahin übernommen und bleibt gespeichert" if n == 1 else
                  f"{n} Teilnehmer wurden bis dahin übernommen und bleiben gespeichert")
    else:
        anzahl = "Bereits übernommene Teilnehmer bleiben gespeichert"
    _db_fehler_anzeigen(
        parent, exc, f"{einleitung} {anzahl} - bitte die Teilnehmerliste prüfen, bevor die Datei "
        "erneut eingelesen wird.",
    )


def _teilnehmerliste_importieren(parent, conn) -> None:
    """CSV-/Excel-Teilnehmerliste einlesen - gemeinsam für den Reiter "Formular-Import" und
    den Knopf im Reiter "Teilnehmer" (UX-Test 02.10.2026, U10)."""
    pfad, _ = QFileDialog.getOpenFileName(parent, "Teilnehmerliste einlesen", _import_startordner(), "CSV- oder Textdatei (*.csv *.txt)")
    if not pfad:
        return
    _import_ordner_merken(pfad)
    vorher = _teilnehmerzahl(conn)
    vorher_ohne = _ohne_startnummer_ids(conn)
    try:
        ergebnis = importiere_teilnehmer_aus_csv(conn, pfad)
    except OSError as exc:
        QMessageBox.warning(parent, "Import fehlgeschlagen",
                            f"Die Datei konnte nicht gelesen werden.\n\n{_klartext_fehler(exc)}")
        return
    except sqlite3.Error as exc:
        _import_db_fehler_melden(parent, exc, conn, vorher)
        return
    if ergebnis.abbruch:
        QMessageBox.warning(parent, "Import nicht möglich", ergebnis.abbruch)
        return
    _import_ergebnis_melden(parent, ergebnis)
    if ergebnis.importiert:
        _startnummern_nach_import_anbieten(parent, conn, vorher_ohne)
