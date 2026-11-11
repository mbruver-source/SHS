"""
Speichern der Ergebniserfassung (seit 11.11.2026 aus desktop_ergebnis.py ausgelagert,
Methoden unverändert): Alle speichern mit Einzel- und Sammel-Commit, Zurücknehmen eines
gescheiterten Sammelspeicherns, Meldungen. Als Mixin von ErgebnisTab, weil die Methoden auf
die Tabellenzustände des Reiters zugreifen. Bewusst KEIN `import app`.
"""

from __future__ import annotations

import contextlib
import sqlite3

from PySide6.QtWidgets import (
    QMessageBox,
)

from db import (
    eintragen_ergebnis,
    pruefe_ergebnis_eingabe,
    setze_ergebnis_status,
)
from shs_core import (
    ABBRUCH_GRUENDE,
    ANZEIGE_MAX,
    SUCHE_MAX,
)
from desktop_ergebnis_zellen import (
    _SORTIERSPALTEN_AUS_STAMMDATEN,
)
from desktop_gemeinsam import (
    fehler_protokollieren,
    meldung_protokollieren,
    _db_fehler_anzeigen,
)

# Lasttest 16.10.2026 (Marcos Entscheidung): Bei mehr Teilnehmern speichert "Alle speichern"
# in EINER Transaktion statt mit einem Commit je Ergebnis (bei 1000 Teilnehmern 2,9 s -> 0,6 s).
# Ein Datenbankfehler speichert dann gar nichts; bis einschließlich dieser Zahl bleibt es beim
# bisherigen Verhalten, bei dem schon gespeicherte Zeilen erhalten bleiben.
_SAMMELSPEICHERN_UEBER_TEILNEHMER = 200


class _ErgebnisSpeichernMixin:
    """Speichern der Ergebnistabelle; wird von ErgebnisTab geerbt (siehe Moduldocstring)."""

    def _sammelspeichern_zuruecknehmen(self, geladen_vorher: list, status_geladen_vorher: list) -> None:
        """Rollt ein gescheitertes Sammelspeichern zurück und setzt die Tabelle auf den
        Stand davor: alle Eingaben gelten wieder als ungespeichert."""
        with contextlib.suppress(sqlite3.Error):
            self.conn.rollback()
        self._geladen_je_zeile = geladen_vorher
        self._status_geladen_je_zeile = status_geladen_vorher
        for zeile in range(len(self._teilnehmer_je_zeile)):
            self._aktualisiere_zeilenstatus(zeile)

    def alle_speichern(self, meldungen: bool = True) -> None:
        """Speichert alle geänderten Zeilen der Tabelle auf einmal (unabhängig vom
        aktuellen Filter - auch ausgeblendete Zeilen werden mitgespeichert). Bei mehr als
        _SAMMELSPEICHERN_UEBER_TEILNEHMER Teilnehmern in einer Transaktion (ganz oder gar
        nicht), sonst mit einem Commit je Ergebnis. Ein offenes Eingabefeld wird vorher
        übernommen (Strg+S, Knopf, Reiterwechsel, Schließen). Mit meldungen=False (Sitzungsende
        ohne erlaubte Interaktion, OFFEN.md B5) erscheint kein Fenster; ins Absturzprotokoll
        gehen nur Anzahl und Art der Fehler, keine Teilnehmernamen (es landet in der kopierbaren
        Diagnose)."""
        self._verworfen_meldung = None
        self.tabelle.offenen_editor_beenden()
        # UX-Test 2026-11, T3: gezählt werden Teilnehmer, nicht Disziplinen - „29 Ergebnis(se)“
        # bei 16 Teilnehmern wirkte wie doppelt gespeichert.
        gespeicherte_zeilen: set[int] = set()
        fehler: list[str] = []
        # Stand die Tabelle vor dem Speichern auf dem aktuellen Datenstand, entspricht sie
        # danach wieder der Datenbank - der nächste Tabwechsel muss dann nicht neu aufbauen.
        # Ausnahme: Sortierung nach einer Ergebnisspalte, die ein Neuaufbau neu anwenden würde.
        stand_vorher = self._datenstand()
        tabelle_war_aktuell = (
            stand_vorher is not None
            and stand_vorher == self._geladener_datenstand
            and self._sortierspalte in (None, *_SORTIERSPALTEN_AUS_STAMMDATEN)
        )
        gesammelt = len(self._teilnehmer_je_zeile) > _SAMMELSPEICHERN_UEBER_TEILNEHMER
        if gesammelt:
            # Für den Fehlerfall: dann gilt wieder der Stand vor dem Speichern.
            geladen_vorher = [dict(geladen) for geladen in self._geladen_je_zeile]
            status_geladen_vorher = list(self._status_geladen_je_zeile)

        # Desktop-Prüfung 14.10.2026, Teil 3 Nr. 1: Ein Schreibfehler der Datenbank
        # (schreibgeschützt, gesperrt, Stick abgezogen) bricht beim ersten Mal ab - die
        # übrigen Eingaben bleiben als ungespeichert stehen, sodass die Nachfrage beim
        # Beenden bzw. Terminwechsel greift, statt dass eine Ausnahme sie überspringt.
        # Im Sammelmodus (siehe _SAMMELSPEICHERN_UEBER_TEILNEHMER) wird dabei alles
        # zurückgerollt, und alle Eingaben bleiben ungespeichert stehen.
        db_fehler: sqlite3.Error | None = None
        try:
            for row, t in enumerate(self._teilnehmer_je_zeile):
                self._zeile_speichern(row, t, gesammelt, gespeicherte_zeilen, fehler)
            if gesammelt:
                self.conn.commit()
        except sqlite3.Error as exc:
            db_fehler = exc
            if gesammelt:
                self._sammelspeichern_zuruecknehmen(geladen_vorher, status_geladen_vorher)
                gespeicherte_zeilen.clear()
            else:
                self._aktualisiere_zeilenstatus(row)
        except BaseException:
            # Unerwarteter Fehler (kein Datenbankfehler): im Sammelmodus keine halbe
            # Transaktion offen lassen, die der nächste Commit einer anderen Aktion
            # festschreiben würde.
            if gesammelt:
                self._sammelspeichern_zuruecknehmen(geladen_vorher, status_geladen_vorher)
            raise

        gespeichert = len(gespeicherte_zeilen)
        if tabelle_war_aktuell and db_fehler is None:
            stand_nachher = self._datenstand()
            # Eigene Commits ändern nur total_changes. Hat eine andere Verbindung während
            # des Speicherns geschrieben (data_version geändert), bleibt der alte Stand
            # gemerkt, und der nächste Tabwechsel baut neu auf.
            if stand_nachher is not None and stand_nachher[1] == stand_vorher[1]:
                self._geladener_datenstand = stand_nachher
        self._speichern_melden(db_fehler, fehler, gespeichert, gesammelt, meldungen)

    def _zeile_speichern(
        self, row: int, t: dict, gesammelt: bool, gespeicherte_zeilen: set[int], fehler: list[str]
    ) -> None:
        """Speichert eine Tabellenzeile: geänderte Punkte je Disziplin und den Status
        (Disqualifiziert/Abbruch). Datenbankfehler gehen an alle_speichern weiter."""
        status_wert = self._status_der_zeile(row)
        if not self._punkte_gesperrt(status_wert):
            self._punkte_der_zeile_speichern(row, t, gesammelt, gespeicherte_zeilen, fehler)
        # Ist die Zeile gesperrt (Disqualifiziert/Abbruch), werden die (geleerten)
        # Punkte-Felder beim Speichern bewusst NICHT ausgewertet: eine ggf. weiterhin
        # in der DB stehende Punktzahl bleibt unangetastet (siehe
        # db.setze_ergebnis_status()-Docstring) - vorher wurden hier fälschlich beide
        # Felder als "geleert" erkannt und die echten Punkte dauerhaft gelöscht.

        if status_wert != self._status_geladen_je_zeile[row]:
            setze_ergebnis_status(
                self.conn, t["id"], status_wert[0], status_wert[1] is not None,
                abbruch_grund=status_wert[1] if status_wert[1] in ABBRUCH_GRUENDE else None,
                commit=not gesammelt,
            )
            self._status_geladen_je_zeile[row] = status_wert
            gespeicherte_zeilen.add(row)

        self._aktualisiere_zeilenstatus(row)

    def _punkte_der_zeile_speichern(
        self, row: int, t: dict, gesammelt: bool, gespeicherte_zeilen: set[int], fehler: list[str]
    ) -> None:
        name = f"{t['nachname']}, {t['vorname']}"
        geladen = self._geladen_je_zeile[row]
        for disziplin, (suche_feld, anzeige_feld) in self._boxen_je_zeile[row].items():
            suche_wert, anzeige_wert = self._feldwert(suche_feld), self._feldwert(anzeige_feld)
            if (suche_wert, anzeige_wert) == geladen[disziplin]:
                continue  # unverändert - nichts zu tun

            if suche_wert is None and anzeige_wert is None:
                # Beide Felder wurden geleert - vorher eingetragenes Ergebnis wird
                # als gelöscht gespeichert (NULL in der DB), statt nur in der
                # Tabelle leer auszusehen, aber beim nächsten Laden wieder
                # aufzutauchen bzw. dauerhaft als "nicht gespeichert" markiert zu
                # bleiben.
                eintragen_ergebnis(self.conn, t["id"], disziplin, None, None, commit=not gesammelt)
                geladen[disziplin] = (None, None)
                gespeicherte_zeilen.add(row)
                continue

            # Codeprüfung 22.09., G6: gemeinsame Eingaberegel mit dem Web-Frontend
            # (db.pruefe_ergebnis_eingabe) statt eigener Prüfung - eine halb
            # ausgefüllte Disziplin wird weiterhin abgelehnt und bleibt ungespeichert.
            eingabe_fehler = pruefe_ergebnis_eingabe(suche_wert, anzeige_wert)
            if eingabe_fehler is not None:
                fehler.append(f"{name} – {disziplin}: {eingabe_fehler}")
                continue
            zu_hoch = [
                f"{teil} höchstens {maximum} Punkte (eingegeben: {wert})"
                for teil, wert, maximum in (
                    ("Suche", suche_wert, SUCHE_MAX), ("Anzeige", anzeige_wert, ANZEIGE_MAX)
                )
                if wert > maximum
            ]
            if zu_hoch:
                fehler.append(f"{name} – {disziplin}: " + ", ".join(zu_hoch))
                continue

            try:
                eintragen_ergebnis(
                    self.conn, t["id"], disziplin, suche_wert, anzeige_wert, commit=not gesammelt
                )
            except sqlite3.IntegrityError as exc:
                fehler.append(f"{name} – {disziplin}: {exc}")
                if gesammelt:
                    # eintragen_ergebnis hat die ganze offene Transaktion
                    # zurückgerollt (db._mit_rollback) - also Abbruch wie in alle_speichern.
                    raise
                continue

            geladen[disziplin] = (suche_wert, anzeige_wert)
            gespeicherte_zeilen.add(row)

    def _speichern_melden(
        self, db_fehler: sqlite3.Error | None, fehler: list[str], gespeichert: int, gesammelt: bool,
        meldungen: bool,
    ) -> None:
        """Statuszeile und Meldungen nach alle_speichern; ohne `meldungen` nur ins
        Absturzprotokoll."""
        if db_fehler is not None:
            if gesammelt:
                self.status_label.setText("Speichern abgebrochen – nichts gespeichert.")
                einleitung = (
                    "Die Ergebnisse konnten nicht gespeichert werden. Es wurde nichts gespeichert, "
                    "alle Eingaben stehen weiter in der Tabelle."
                )
            else:
                self.status_label.setText(
                    f"Speichern abgebrochen – {gespeichert} Teilnehmer gespeichert, die übrigen nicht."
                )
                einleitung = (
                    "Die Ergebnisse konnten nicht (vollständig) gespeichert werden. Bereits gespeicherte "
                    "Zeilen bleiben erhalten, die übrigen Eingaben stehen weiter in der Tabelle."
                )
            if fehler:
                # Eine einzige Meldung (Desktop-Prüfung 14.10.2026): Eingabefehler, die vor dem
                # Abbruch auffielen, gehören mit hinein.
                einleitung += "\n\nAußerdem fehlerhafte Eingaben:\n" + "\n".join(fehler)
            if meldungen:
                _db_fehler_anzeigen(self, db_fehler, einleitung)
            else:
                fehler_protokollieren(db_fehler)
                meldung_protokollieren(
                    "Speichern beim Sitzungsende",
                    f"Speichern abgebrochen ({gespeichert} Teilnehmer gespeichert, {len(fehler)} fehlerhafte "
                    "Eingabe(n)); die übrigen Eingaben stehen weiter in der Tabelle.",
                )
        elif gespeichert:
            self.status_label.setText(f"{gespeichert} Teilnehmer gespeichert.")
        elif not fehler:
            self.status_label.setText("Keine Änderungen zu speichern.")
        if self._verworfen_meldung is not None:
            # N8 (Verifikation B14): beim Speichern mit offenem Feld ging die Meldung sonst unter.
            self.status_label.setText(f"{self._verworfen_meldung} {self.status_label.text()}")

        if fehler and db_fehler is None:
            text = ("Folgende Zeilen konnten nicht gespeichert werden (übrige wurden gespeichert):\n\n"
                    + "\n".join(fehler))
            if meldungen:
                QMessageBox.warning(self, "Nicht alle Ergebnisse gespeichert", text)
            else:
                meldung_protokollieren(
                    "Speichern beim Sitzungsende",
                    f"{len(fehler)} Eingabe(n) nicht speicherbar (unvollständig oder zu hoch); "
                    "sie stehen weiter in der Tabelle.",
                )
