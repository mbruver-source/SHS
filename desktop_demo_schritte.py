"""
Die Schritte und Aktionen der geführten Demoprüfung (seit 11.11.2026 aus desktop_demo.py
ausgelagert, Methoden unverändert): _schritte_aufbauen liefert die Schrittliste, die
_aktionen_* die vorgeführten Handgriffe. Als Mixin von DemoTour, weil die Aktionen auf deren
Zustand zugreifen (self.fenster, self._markieren …). Bewusst KEIN `import app`.
"""

from __future__ import annotations

import os
import random
from typing import Callable

from PySide6.QtWidgets import (
    QDialog,
)

import demo_daten
import pdf_export
from db import (
    NeuerTeilnehmer,
    add_teilnehmer,
    angebotene_pruefungen,
    berechne_auswertung,
    fehlende_startnummern_vergeben,
    get_veranstaltung,
    list_zeitplan_richter,
    pruefung_nach_kuerzel,
    pruefung_sortierschluessel,
    pruefungs_kuerzel,
    set_veranstaltung,
    setze_stechen_sieger,
    startnummer_bereiche,
    vergebene_startnummern,
    zeitplan_richter_aus_veranstaltung_anlegen,
)
from desktop_demo_panel import DemoSchritt, _lebt
from desktop_dialoge import TeilnehmerDialog, VeranstaltungsDialog
from desktop_gemeinsam import (
    _DQ_SPALTE,
    _ERGEBNIS_SPALTEN_JE_DISZIPLIN,
    _ausdrucke_ordner,
    _export_dateiname,
    _pfad_anzeige,
)
from shs_core import stechen_gruppen


class DemoFehler(Exception):
    """Ein Schritt ließ sich nicht vorführen (z. B. weil im Dialog etwas geändert wurde) -
    der Text erscheint im Erklärfenster."""


class _DemoSchritteMixin:
    """Schrittliste und Aktionen der Demo; wird von DemoTour geerbt (siehe Moduldocstring)."""

    # --- Die einzelnen Schritte ----------------------------------------------

    def _schritte_aufbauen(self) -> list[DemoSchritt]:
        zurueck = (
            "Danach bist du wieder in deinem vorherigen Termin."
            if not self.eigenes_fenster else "Danach siehst du wieder den Startbildschirm."
        )
        return [
            DemoSchritt(
                "Willkommen zur Demoprüfung",
                "Die Demo spielt einen kompletten Prüfungstag einmal vor: vom Anlegen des "
                "Termins über Teilnehmer, Zeitplan und Ergebnisse bis zur Ergebnisliste.\n\n"
                "Das Programm klickt und tippt selbst. Ist ein Schritt fertig, geht es nach einer "
                "Lesezeit (je nach Textlänge) von allein weiter – oder du drückst „Weiter“. Wer selbst "
                "bestimmen will, nimmt den Haken bei „Automatisch weiter“ heraus. „Schritt zurück“ "
                "nimmt ab Schritt 4 den letzten Schritt zurück und spielt ihn noch einmal ab (bis "
                "dahin zeigt „Vorheriger Text“ die Erklärung davor). Ein farbiger "
                "Rahmen zeigt jeweils, wo gerade gearbeitet wird. Wer es eilig hat: „Weiter“ "
                "füllt einen laufenden Schritt sofort fertig aus.\n\n"
                "Alle Namen und Daten sind erfunden. Der Demo-Termin liegt in einem "
                "temporären Ordner und wird am Ende gelöscht – deine echten Termine bleiben "
                "unberührt. „Beenden“ bricht jederzeit ab.",
            ),
            DemoSchritt(
                "1. Neuen Termin anlegen",
                "Jede Prüfung beginnt mit einem Termin. Im Startbildschirm öffnet „Neuen "
                "Termin anlegen…“ dieses Fenster.\n\n"
                "Pflicht sind nur Verein und Datum – daraus entsteht der Dateiname. Richter "
                "und Prüfungsleiter erscheinen später im Zeitplan und auf den Ausdrucken. "
                "Verband und Meldestelle stehen im Kopf des Anmeldeformulars.\n\n"
                "„Angebotene Prüfungen“ legt fest, was die Teilnehmer auf dem Anmeldeformular "
                "ankreuzen können. Die Startnummern-Bereiche sorgen dafür, dass man jeder "
                "Nummer ansieht, zu welcher Prüfung sie gehört.\n\n"
                "Normalerweise liegt die Termin-Datei im Termine-Ordner – die Demo nutzt "
                "einen temporären Ordner.",
                self._aktionen_termin_dialog,
            ),
            DemoSchritt(
                "2. Termin gespeichert",
                "Mit OK prüft das Programm die Angaben und legt den Termin an. Ein Termin ist "
                "genau eine Datei – darin steht alles: Teilnehmer, Zeitplan und Ergebnisse.\n\n"
                "Oben siehst du jetzt die Reiter, durch die die Demo der Reihe nach geht. "
                "Den Reiter „Datensicherung“ hat die Demo gesperrt, weil er immer mit deinen "
                "echten Terminen arbeitet.",
                self._aktionen_termin_speichern,
            ),
            DemoSchritt(
                "3. Einen Teilnehmer erfassen",
                "Im Reiter „Teilnehmer“ öffnet „Teilnehmer hinzufügen…“ (oder Strg+N von jedem "
                "Reiter aus) die Erfassungsmaske.\n\n"
                f"Wichtig ist das Feld „Prüfung“: „{pruefung_nach_kuerzel('ED1-Trümmerfeld').bezeichnung}“ "
                "ist eine Einzeldisziplin (ED: Trümmerfeld, Flächensuche oder Behältnisstrecke), "
                f"„{pruefung_nach_kuerzel('DK1').bezeichnung}“ der Dreikampf aus allen drei. Bei ED "
                "gibt es genau einen Suchgegenstand.\n\n"
                "Die Startnummer bleibt hier bewusst offen – sie wird gleich für alle "
                "gemeinsam vergeben.",
                self._aktionen_teilnehmer_dialog,
            ),
            DemoSchritt(
                "4. Weitere Meldungen",
                "Die übrigen Meldungen kommen dazu. In der Praxis tippt man sie selten ab: "
                "Meist kommen sie über das ausfüllbare Anmeldeformular (PDF) oder eine "
                "Excel-Liste – beides liest der Reiter „Formular-Import“ ein.\n\n"
                "Achte auf die Spalte „Anmerkungen“: Bei Hugo Hansen fehlt die Chip-Nummer. "
                "Solche orangefarbenen Warnungen sollten vor dem Prüfungstag geklärt sein.",
                self._aktionen_weitere_teilnehmer,
            ),
            DemoSchritt(
                "5. Startnummern vergeben",
                "„Fehlende Startnummern vergeben…“ verteilt die Nummern auf einen Schlag: je "
                "Prüfung lückenlos aus dem im Termin hinterlegten Bereich, innerhalb der "
                "Prüfung nach Namen sortiert.\n\n"
                "Bereits vergebene Nummern ändert das Programm nie – kommen später Meldungen "
                "dazu, einfach erneut drücken.",
                self._aktionen_startnummern,
            ),
            DemoSchritt(
                "6. Wer hat bezahlt?",
                "„Bezahlt umschalten“ setzt den Zahlungsstatus für alle markierten "
                "Teilnehmer, ohne die Erfassungsmaske zu öffnen – praktisch am Anmeldetisch.\n\n"
                "Mit dem Filter „Bezahlt“ siehst du sofort, wer noch offen ist: hier Hugo "
                "Hansen. Das Suchfeld „Suche“ findet jeden Teilnehmer nach Name oder Hund, "
                "und ein Rechtsklick auf eine Zeile zeigt die Aktionen der Knöpfe.",
                self._aktionen_bezahlt,
            ),
            DemoSchritt(
                "7. Zeitplan",
                "Der Reiter „Zeitplan“ legt für jeden Richter aus den Termindaten eine Spalte "
                "an. „Automatisch verteilen…“ macht daraus einen ausgewogenen Vorschlag.\n\n"
                "Dreikampf-Teams laufen dabei nie gleichzeitig bei zwei Richtern und halten "
                "den Mindestabstand ein. Der Vorschlag lässt sich danach von Hand ändern, "
                "Start- und Endzeiten rechnet das Programm selbst. Die Seitenleiste "
                "„Offene Starts“ zeigt, ob jede Prüfung eingeplant ist.",
                self._aktionen_zeitplan,
            ),
            DemoSchritt(
                "8. Ergebnisse eintragen",
                "Am Prüfungstag kommen die Punkte in die Ergebniserfassung: je Disziplin die "
                "Suchleistung (0–60) und die Anzeigeleistung (0–40). Beim Dreikampf stehen "
                "alle drei Disziplinen nebeneinander in einer Zeile.\n\n"
                "Einfach eine Zelle anklicken und lostippen. Tab springt zur nächsten Zelle, "
                "Enter übernimmt die Zahl, Entf leert die Zelle.\n\n"
                "Gelbe Zeilen sind noch nicht gespeichert.",
                self._aktionen_ergebnisse,
            ),
            DemoSchritt(
                "9. Disqualifikation",
                "Wird ein Team disqualifiziert, setzt man den Haken „Disqualifiziert“ (per "
                "Klick oder mit der Leertaste). Die Punktezellen werden dann geleert und "
                "gesperrt (abgesetzte Fläche).\n\n"
                "Bricht ein Team ab, wählt man in der Spalte „Abbruch“ den Grund "
                "(Ungehorsam, Verletzung Hund, Krankheit, Verletzung HF). Die bis dahin "
                "erreichten Punkte bleiben eintragbar und zählen als Teilbewertung.\n\n"
                "In beiden Fällen gibt es keine Wertnote und keinen Platz, das Team zählt "
                "aber bei der Zahl der Starter mit.",
                self._aktionen_disqualifikation,
            ),
            DemoSchritt(
                "10. Speichern",
                "Erst „Alle Ergebnisse speichern“ (oder Strg+S) schreibt die Eingaben in die "
                "Termin-Datei – die gelbe Markierung verschwindet.\n\n"
                "Vergisst man es doch einmal, fragt das Programm beim Reiterwechsel nach. "
                "Beim Schließen des Programms speichert es automatisch.",
                self._aktionen_speichern,
            ),
            DemoSchritt(
                "11. Auswertung",
                "Die Auswertung rechnet Wertnoten und Plätze je Leistungsklasse selbst aus. "
                "ED (höchstens 100 Punkte): ab 96 Vorzüglich, ab 90 Sehr Gut, ab 80 Gut, ab "
                "70 Befriedigend. Dreikampf (höchstens 300): ab 286, 270, 240 bzw. 210 – und "
                "in jeder Disziplin mindestens 70 Punkte.\n\n"
                "Darunter heißt es „nicht Bestanden“ (rot, ohne Platz). Anna Albers und Ben "
                "Brandt sind mit je 96 Punkten gleichauf auf Platz 1"
                + (" – dort steht „Stechen offen“." if self._mit_stechen else "."),
                self._aktionen_auswertung,
            ),
            DemoSchritt(
                "12. Stechen",
                (
                    "Bei Gleichstand auf Platz 1 entscheidet ein Stechen auf dem Platz. Das "
                    "Ergebnis trägt man mit „Stechen-Sieger festlegen…“ ein: Der Sieger wird 1., "
                    "die anderen werden 2.\n\n"
                    "In der Demo gewinnt Anna Albers."
                    if self._mit_stechen else
                    "Für Prüfungen ab dem 01.01.2027 entfällt das Stechen. Punktgleiche "
                    "teilen sich den Platz – Anna Albers und Ben Brandt sind beide 1."
                ),
                self._aktionen_stechen,
            ),
            DemoSchritt(
                "13. Ergebnisliste als PDF",
                "Im Reiter „Ausdrucke/Export“ liegen alle Ausdrucke: Ergebnisliste, Etiketten "
                "(auch für die Behältnisse, mit einstellbarer Größe), Statistik, Bewertungsbögen "
                "(beim Dreikampf wahlweise ein Blatt je Disziplin), Zeitplan und mehr. Neben jedem Knopf steht "
                "kurz, was er erzeugt; bleibt die Maus darauf, zeigt ein Tooltip "
                "Einzelheiten.\n\n"
                "Normalerweise fragt das Programm, wo die Datei hin soll (Standard: Ordner "
                "„Ausdrucke“ neben dem Termin); mit dem Haken „Dateien ohne Nachfrage im "
                "Ablageort speichern“ entfällt die Frage. Die Demo hat die Ergebnisliste schon "
                "erzeugt – „PDF öffnen“ zeigt sie dir. Auch diese Datei wird am Ende gelöscht "
                "(ist sie dann noch im PDF-Programm geöffnet: beim nächsten Programmstart).",
                self._aktionen_pdf,
            ),
            DemoSchritt(
                "14. Abrechnung der Leistungsrichter",
                "Im Reiter „Abrechnung Leistungsrichter“ steht je Richter eine Zeile mit den "
                "Namen aus den Veranstaltungsdaten. Du trägst die gefahrenen Kilometer (hin und "
                "zurück) ein; Fahrtkosten und Summe rechnet das Programm aus den Sätzen des "
                "Termins (Vergütung je km und Tagespauschale), die sich oben und je Richter "
                "ändern lassen.\n\n"
                "Darunter erzeugt „Übersicht als PDF…“ die Gesamtabrechnung, „Quittung…“ je "
                "Richter eine Quittung, und „Export als CSV…“ liefert die Beträge für ein "
                "Vereinstool mit Ein- und Ausgaben.",
                self._aktionen_abrechnung,
            ),
            DemoSchritt(
                "15. Checkliste zum Prüfungstermin",
                "Damit am Prüfungstag nichts vergessen wird, gibt es im Reiter „Verwaltung“ eine "
                "Checkliste, gegliedert in Kategorien (zum Beispiel vor, während und nach der "
                "Prüfung). Erledigtes hakst du ab; oben steht, wie viele Punkte schon erledigt "
                "sind.\n\n"
                "Eigene Kategorien und Punkte lassen sich hinzufügen, nicht benötigte "
                "Schritte ausblenden. Der Knopf „Checkliste“ oben im Fenster springt von jedem "
                "Reiter aus direkt dorthin.",
                self._aktionen_checkliste,
            ),
            DemoSchritt(
                "16. Richter am Tablet",
                "Bei größeren Prüfungen müssen die Ergebnisse nicht am Rechner der "
                "Prüfungsleitung eingetippt werden: Der Termin lässt sich im Web "
                "veröffentlichen, die Richter tragen ihre Punkte dann am Tablet oder Handy "
                "im Browser ein, und die Ergebnisse werden anschließend in den Termin "
                "übernommen.\n\n"
                "Wie das geht, steht im Handbuch in den Kapiteln „Für Richter: Ergebnisse im "
                "Browser eintragen“ und „Für die Prüfungsleitung: Termin im Web "
                "veröffentlichen“.",
                self._aktionen_nichts_markieren,
            ),
            DemoSchritt(
                "17. Demo-Termin löschen",
                "Das war ein kompletter Prüfungstag.\n\n"
                "Mit „Fertig“ wird der Demo-Termin samt Ergebnisliste gelöscht (eine noch im "
                "PDF-Programm geöffnete Ergebnisliste beim nächsten Programmstart). " + zurueck + "\n\n"
                "Echte Termine löschst du im Startbildschirm über „Löschen…“ – vorher am "
                "besten im Reiter „Datensicherung“ eine Sicherung erstellen.",
                self._aktionen_nichts_markieren,
            ),
        ]

    def _aktionen_nichts_markieren(self) -> list[Callable[[], None]]:
        return [lambda: self._markieren(None)]

    def _aktionen_termin_dialog(self) -> list[Callable[[], None]]:
        dialog = VeranstaltungsDialog(self._fenster)
        # Speicherort fest auf den Temp-Ordner - der automatische Vorschlag würde sonst in
        # den Termine-Ordner zeigen. Gespeichert wird ohnehin in self.pfad (siehe unten).
        dialog._pfad_manuell_geaendert = True
        dialog.pfad_feld.setText(_pfad_anzeige(self.pfad))
        dialog.pfad_feld.setReadOnly(True)
        dialog.pfad_pruefen = False  # der Demo-Termin existiert schon (siehe _starten)
        dialog.durchsuchen_btn.setEnabled(False)  # gespeichert wird immer im Demo-Ordner (Teil 10 Nr. 11)
        self._dialog_zeigen(dialog)

        werte = demo_daten.VERANSTALTUNG
        aktionen = [
            *self._eintragen(dialog.verein, werte["verein"]),
            *self._eintragen(dialog.vereins_nr, werte["vereins_nr"]),
            *self._eintragen(dialog.ort, werte["ort"]),
            *self._eintragen(dialog.datum, self._heute.strftime("%d.%m.%Y")),
            *self._eintragen(dialog.pruefungsnummer, werte["pruefungsnummer"]),
            *self._eintragen(dialog.pruefungsleiter, werte["pruefungsleiter"]),
            *self._eintragen(dialog.wertungsrichter_1, werte["wertungsrichter_1"]),
            *self._eintragen(dialog.wertungsrichter_2, werte["wertungsrichter_2"]),
            *self._eintragen(dialog.verband, werte["verband"]),
            *self._eintragen(dialog.meldestelle, werte["meldestelle"]),
        ]
        for kuerzel in demo_daten.PRUEFUNGEN:
            aktionen += self._eintragen(dialog.pruefung_checkboxen[kuerzel], True)
        for kuerzel, (von, bis) in demo_daten.PRUEFUNGEN.items():
            _beschriftung, von_feld, bis_feld = dialog.bereich_felder[kuerzel]
            aktionen += self._eintragen(von_feld, str(von))
            aktionen += self._eintragen(bis_feld, str(bis))
        aktionen.append(self._markieren_aktion(self._dialog_ok_knopf))
        return aktionen

    def _aktionen_termin_speichern(self) -> list[Callable[[], None]]:
        def speichern() -> None:
            dialog = self._dialog
            if not _lebt(dialog) or not isinstance(dialog, VeranstaltungsDialog):
                raise DemoFehler("Das Fenster „Neuen Termin anlegen“ ist nicht mehr offen.")
            # Dieselbe Prüfung wie beim Klick auf OK (zeigt bei vollständigen Angaben
            # keine Rückfrage).
            dialog._pruefen_und_akzeptieren()
            if dialog.result() != QDialog.Accepted:
                raise DemoFehler(
                    "Die Angaben im Fenster „Neuen Termin anlegen“ wurden verändert und sind "
                    "nicht vollständig – die Demo kann hier nicht weitermachen."
                )
            # Verifikation 04.10.2026, Befund 5: Wurden während Schritt 1 im eigenen Termin
            # noch Ergebnisse eingetippt, wie beim Terminwechsel nachfragen statt sie beim
            # Umschalten auf den Demo-Termin stillschweigend zu verwerfen.
            if not self.eigenes_fenster and not self._fenster._ungespeicherte_ergebnisse_klaeren(
                "Trotzdem mit der Demoprüfung weitermachen"
            ):
                raise DemoFehler(
                    "Die Demo hält hier an: In deinem Termin gibt es noch nicht gespeicherte "
                    "Ergebnisse. Nach „Beenden“ bist du wieder in deinem Termin, die Eingaben "
                    "sind noch da und lassen sich speichern oder korrigieren."
                )
            set_veranstaltung(self.conn, **dialog.veranstaltung_werte())
            self._dialog_schliessen()
            self._fenster._termin_setzen(self.conn, self.pfad, demo=True)
            self._fenster._tabs.setCurrentWidget(self._fenster.teilnehmer_tab)
            self._markieren(self._fenster._tabs.tabBar())

        return [speichern]

    def _aktionen_teilnehmer_dialog(self) -> list[Callable[[], None]]:
        fenster = self._fenster
        tab = fenster.teilnehmer_tab
        self._reiter_zeigen(tab)

        def oeffnen() -> None:
            self._markieren(tab.hinzufuegen_btn)

        def dialog_zeigen() -> None:
            # Dieselben Angaben wie TeilnehmerTab._teilnehmer_hinzufuegen. Seit UX-Test 2026-11
            # (T14) mit `angebotene`, damit die Demo die Zeile „… – wird angeboten“ zeigt.
            veranstaltung = get_veranstaltung(self.conn)
            dialog = TeilnehmerDialog(
                tab,
                vergebene_nummern=vergebene_startnummern(self.conn),
                namen_je_startnummer={},
                bereiche=startnummer_bereiche(veranstaltung),
                angebotene={p.kuerzel for p in angebotene_pruefungen(veranstaltung)},
                stichtag=(veranstaltung or {}).get("datum"),
            )
            self._dialog_zeigen(dialog)
            daten = demo_daten.TEILNEHMER[0]["daten"]
            # UX-Test 2026-11, T5: die Prüfung über die Auswahl „Prüfung“ wählen; ist sie (nach
            # eigener Änderung der Veranstaltungsdaten) nicht angeboten, wie bisher Art/LK/Disziplin.
            kuerzel = pruefungs_kuerzel(daten["art"], daten["stufe"], daten["disziplin"])
            if dialog.pruefung_auswahl.findData(kuerzel) >= 0:
                pruefung = self._eintragen(dialog.pruefung_auswahl, pruefung_nach_kuerzel(kuerzel).bezeichnung)
            else:
                pruefung = [
                    *self._eintragen(dialog.pruefung_auswahl, dialog.pruefung_auswahl.itemText(
                        dialog.pruefung_auswahl.count() - 1)),  # „andere Prüfung …“ blendet die Felder ein
                    *self._eintragen(dialog.art, daten["art"]),
                    *self._eintragen(dialog.stufe, str(daten["stufe"])),
                    *self._eintragen(dialog.disziplin, daten["disziplin"]),
                ]
            self._offen[:0] = [
                *self._eintragen(dialog.nachname, daten["nachname"]),
                *self._eintragen(dialog.vorname, daten["vorname"]),
                *self._eintragen(dialog.verein, daten["verein"]),
                *self._eintragen(dialog.rufname_hund, daten["rufname_hund"]),
                *self._eintragen(dialog.chip_nr, daten["chip_nr"]),
                *pruefung,
                *self._eintragen(dialog.gegenstand_1, daten["gegenstand_1"]),
                self._markieren_aktion(self._dialog_ok_knopf),
            ]

        return [oeffnen, dialog_zeigen]

    def _aktionen_weitere_teilnehmer(self) -> list[Callable[[], None]]:
        tab = self._fenster.teilnehmer_tab
        self._reiter_zeigen(tab)
        demo = demo_daten.TEILNEHMER[0]["daten"]

        def ersten_speichern() -> None:
            dialog = self._dialog
            if _lebt(dialog) and isinstance(dialog, TeilnehmerDialog):
                # Eigene Eingaben im Demo-Dialog sind erlaubt - geprüft wird wie beim echten
                # OK (Desktop-Prüfung 14.10.2026, Teil 10 Nr. 3).
                dialog._pruefen_und_akzeptieren()
                if dialog.result() != QDialog.Accepted:
                    raise DemoFehler(
                        "Die Angaben im Fenster „Teilnehmer erfassen“ lassen sich so nicht "
                        "übernehmen (siehe Meldung) – die Demo kann hier nicht weitermachen."
                    )
                neu = dialog.ergebnis()
                if (neu.art, neu.stufe, neu.disziplin) != (demo["art"], demo["stufe"], demo.get("disziplin")):
                    raise DemoFehler(
                        "Die Prüfung im Fenster „Teilnehmer erfassen“ wurde geändert – für die "
                        "weiteren Schritte muss sie bleiben, wie die Demo sie eingetragen hat."
                    )
            else:  # Dialog ist nicht mehr da (z. B. nach „Schritt zurück“ aus Schritt 5) - mit den Demodaten weiter
                neu = NeuerTeilnehmer(**demo)
            self._dialog_schliessen()
            # Immer unter dem Demonamen merken - spätere Schritte suchen ihn darunter.
            self._ids[demo["nachname"]] = add_teilnehmer(self.conn, neu)
            tab.aktualisieren()
            self._markieren(tab.tabelle)

        def anlegen(daten: dict) -> Callable[[], None]:
            def aktion() -> None:
                self._ids[daten["nachname"]] = add_teilnehmer(self.conn, NeuerTeilnehmer(**daten))
                tab.aktualisieren()
            return aktion

        return [ersten_speichern] + [anlegen(t["daten"]) for t in demo_daten.TEILNEHMER[1:]]

    def _aktionen_startnummern(self) -> list[Callable[[], None]]:
        self._reiter_zeigen(self._fenster.teilnehmer_tab)  # Teil 10 Nr. 4
        tab = self._fenster.teilnehmer_tab

        def vergeben() -> None:
            # Direkt statt über den Knopf - der zeigt danach ein Meldungsfenster.
            ergebnis = fehlende_startnummern_vergeben(self.conn)
            tab.aktualisieren()
            self._panel.hinweis(f"{len(ergebnis.vergeben)} Startnummern vergeben.")
            self._markieren(tab.tabelle)

        return [lambda: self._markieren(tab.vergeben_btn), vergeben]

    def _aktionen_bezahlt(self) -> list[Callable[[], None]]:
        self._reiter_zeigen(self._fenster.teilnehmer_tab)  # Teil 10 Nr. 4
        tab = self._fenster.teilnehmer_tab

        def markieren_und_umschalten() -> None:
            bezahlt = {tid for name, tid in self._ids.items() if name != demo_daten.NICHT_BEZAHLT}
            tab._auswahl_wiederherstellen(bezahlt)
            self._markieren(tab.bezahlt_btn)

        def umschalten() -> None:
            tab._bezahlt_umschalten()
            tab.tabelle.clearSelection()
            self._markieren(tab.tabelle)

        return [
            markieren_und_umschalten,
            umschalten,
            *self._eintragen(tab.filter_bezahlt, "Nicht bezahlt"),
        ]

    def _aktionen_zeitplan(self) -> list[Callable[[], None]]:
        fenster = self._fenster
        fenster.teilnehmer_tab.filter_bezahlt.setCurrentText("Alle")
        tab = fenster.zeitplan_tab

        def zeigen() -> None:
            zeitplan_richter_aus_veranstaltung_anlegen(self.conn)
            self._reiter_zeigen(tab)
            tab.aktualisieren()
            self._markieren(tab.verteilen_btn)

        def verteilen() -> None:
            # Direkt statt über den Knopf - der öffnet den Dialog „Automatisch verteilen“ (T1).
            if not list_zeitplan_richter(self.conn):
                raise DemoFehler("Im Zeitplan sind keine Richter angelegt.")
            if not tab.verteilen_ohne_rueckfrage():
                raise DemoFehler("Der Zeitplan-Vorschlag ließ sich nicht erstellen.")

        return [zeigen, verteilen]

    def _aktionen_ergebnisse(self) -> list[Callable[[], None]]:
        tab = self._fenster.ergebnis_tab
        self._reiter_zeigen(tab)
        aktionen: list[Callable[[], None]] = []
        for eintrag in demo_daten.TEILNEHMER:
            nachname = eintrag["daten"]["nachname"]
            for disziplin, (suche, anzeige) in eintrag.get("ergebnis", {}).items():
                for index, wert in ((0, suche), (1, anzeige)):
                    aktionen += self._punkte_eintragen(nachname, disziplin, index, wert)
        return aktionen

    def _punkte_eintragen(self, nachname: str, disziplin: str, index: int, wert: int) -> list[Callable[[], None]]:
        """Tippt eine Punktzahl Ziffer für Ziffer. Das Feld wird jedes Mal frisch gesucht -
        baut der Anwender die Tabelle zwischendurch neu auf („Liste aktualisieren“), sind
        die alten Felder weg."""
        tab = self._fenster.ergebnis_tab
        feldname = ("suche", "anzeige")[index]

        def zeile() -> int:
            row = tab.zeile_von(self._ids[nachname])
            if row is None or disziplin not in tab.erfassbare_disziplinen(row):
                raise DemoFehler(f"Die Zeile von {nachname} ist in der Ergebniserfassung nicht zu finden.")
            return row

        def eintragen(text: str) -> None:
            tab.punkte_eintragen(zeile(), disziplin, **{feldname: text})

        def fokus() -> None:
            tab.zeile_zeigen(zeile())
            self._ergebniszelle_markieren(self._ids[nachname], _ERGEBNIS_SPALTEN_JE_DISZIPLIN[disziplin][index])
            eintragen("")
        fokus.pause_ms = self.PAUSE_MS // 3

        text = str(wert)
        aktionen: list[Callable[[], None]] = [fokus]
        for laenge in range(1, len(text) + 1):
            taste = (lambda teil=text[:laenge]: eintragen(teil))
            taste.pause_ms = random.randint(*self.TASTE_MS)
            aktionen.append(taste)
        aktionen[-1].pause_ms = self.PAUSE_MS // 2
        return aktionen

    def _aktionen_disqualifikation(self) -> list[Callable[[], None]]:
        self._reiter_zeigen(self._fenster.ergebnis_tab)  # Teil 10 Nr. 4
        def aktion() -> None:
            nachname = next(t["daten"]["nachname"] for t in demo_daten.TEILNEHMER if t.get("status") == "dq")
            tab = self._fenster.ergebnis_tab
            row = tab.zeile_von(self._ids[nachname])
            if row is None:
                raise DemoFehler(f"Die Zeile von {nachname} ist in der Ergebniserfassung nicht zu finden.")
            tab.zeile_zeigen(row)
            self._ergebniszelle_markieren(self._ids[nachname], _DQ_SPALTE)
            tab.status_setzen(row, dq=True)
        return [aktion]

    def _aktionen_speichern(self) -> list[Callable[[], None]]:
        self._reiter_zeigen(self._fenster.ergebnis_tab)  # Teil 10 Nr. 4
        tab = self._fenster.ergebnis_tab

        def speichern() -> None:
            tab.alle_speichern()
            if tab.hat_ungespeicherte_aenderungen():
                raise DemoFehler("Nicht alle Ergebnisse ließen sich speichern (siehe Meldung).")
            self._markieren(tab.tabelle)

        return [lambda: self._markieren(tab.speichern_btn), speichern]

    def _aktionen_auswertung(self) -> list[Callable[[], None]]:
        tab = self._fenster.auswertung_tab

        def zeigen() -> None:
            self._reiter_zeigen(tab)
            self._markieren(tab.tabelle)

        return [zeigen]

    def _aktionen_stechen(self) -> list[Callable[[], None]]:
        self._reiter_zeigen(self._fenster.auswertung_tab)  # Teil 10 Nr. 4
        tab = self._fenster.auswertung_tab

        def festlegen() -> None:
            # Direkt statt über den Knopf - der fragt den Sieger in einem Dialog ab.
            fertig, _ausstehend = berechne_auswertung(self.conn)
            sieger = self._ids.get(demo_daten.STECHEN_SIEGER)
            # Wie in der Auswertung je Leistungsklasse (shs_core.stechen_gruppen), Teil 10 Nr. 10.
            gruppe = next(
                ([int(t.id) for t in g] for g in stechen_gruppen(fertig, pruefung_sortierschluessel).values()
                 if any(int(t.id) == sieger and t.stechen == "offen" for t in g)),
                [],
            )
            if not gruppe:
                raise DemoFehler("In der Auswertung ist kein offenes Stechen zu finden.")
            setze_stechen_sieger(self.conn, sieger, gruppe)
            tab.aktualisieren()
            self._markieren(tab.tabelle)

        if not self._mit_stechen:  # PO1: neue PO, nichts festzulegen
            return [lambda: self._markieren(tab.tabelle)]
        return [lambda: self._markieren(tab.stechen_btn), festlegen]

    def _aktionen_pdf(self) -> list[Callable[[], None]]:
        tab = self._fenster.export_tab

        def zeigen() -> None:
            self._reiter_zeigen(tab)
            self._markieren(tab.ergebnisliste_btn)

        def erzeugen() -> None:
            # Direkt statt über den Knopf - der fragt nach dem Speicherort und zeigt danach
            # ein Meldungsfenster.
            ordner = _ausdrucke_ordner(self.pfad)
            os.makedirs(ordner, exist_ok=True)
            ziel = os.path.join(ordner, _export_dateiname(self.conn, "Ergebnisliste"))
            pdf_export.erstelle_ergebnisliste_pdf(self.conn, ziel)
            self.pdf_pfad = ziel
            self._panel.hinweis(f"Gespeichert unter: {_pfad_anzeige(ziel)}")
            self._panel.extra("PDF öffnen", lambda: self._pdf_oeffnen(ziel))

        return [zeigen, erzeugen]

    def _aktionen_abrechnung(self) -> list[Callable[[], None]]:
        tab = self._fenster.abrechnung_tab

        def zeigen() -> None:
            self._reiter_zeigen(tab)
            tab.aktualisieren()  # die Richternamen stehen erst seit dem Anlegen des Termins fest
            self._markieren(tab.tabelle)

        return [zeigen, lambda: self._markieren(tab.uebersicht_btn)]

    def _aktionen_checkliste(self) -> list[Callable[[], None]]:
        tab = self._fenster.verwaltung_tab

        def zeigen() -> None:
            self._reiter_zeigen(tab)
            tab.zur_checkliste()
            self._markieren(tab._checkliste_bildlauf)

        return [zeigen]
