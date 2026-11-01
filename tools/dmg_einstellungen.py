# Einstellungen für dmgbuild (macOS-.dmg, Marco 01.11.2026).
#
# Aufruf aus .github/workflows/build-installer.yml (Job build-macos):
#   dmgbuild -s tools/dmg_einstellungen.py -D app=dist/SHS-Pruefungsprogramm.app \
#     -D lizenz=LICENSE -D drittlizenzen=build/THIRD_PARTY_LICENSES.txt \
#     "SHS-Pruefungsprogramm" Output/....dmg
#
# dmgbuild führt diese Datei mit exec() aus (kein Import, kein __file__); die Werte aus den
# -D-Schaltern stehen im Wörterbuch `defines`. Ergebnis: Die App liegt im Abbild neben einer
# Verknüpfung auf "Programme" zum Hineinziehen, dazu LICENSE.txt und THIRD_PARTY_LICENSES.txt.
# Beim Öffnen zeigt macOS die MIT-Lizenz an und hängt das Abbild erst nach "Akzeptieren" ein
# (wie der Lizenzschritt im Windows-Installer, installer.iss LicenseFile).

app = defines["app"]  # noqa: F821 - von dmgbuild bereitgestellt
lizenz = defines["lizenz"]  # noqa: F821
drittlizenzen = defines["drittlizenzen"]  # noqa: F821

format = "UDZO"

files = [
    app,
    drittlizenzen,
    # Unter macOS öffnet ein Doppelklick nur Dateien mit Endung direkt in TextEdit.
    (lizenz, "LICENSE.txt"),
]
symlinks = {"Applications": "/Applications"}

with open(lizenz, encoding="utf-8") as datei:
    lizenztext = datei.read()

# Format laut dmgbuild 1.6.7 (licensing.build_license): "licenses" ordnet Sprachkennungen den
# Text (oder einen Dateipfad) zu; die Knöpfe ("Akzeptieren", "Ablehnen" ...) liefert dmgbuild
# je Sprache selbst, ein eigener "buttons"-Eintrag ist nicht nötig. Der Text ist in beiden
# Sprachen das englische Original. macOS wählt die Sprache passend zur Systemsprache; ohne
# Treffer gilt der feste Standard von dmgbuild (Ressource 5000 = en_US). Einen Schlüssel
# "default-language" wertet dmgbuild 1.6.7 nicht aus. Der Text wird als Mac Roman kodiert -
# LICENSE ist reines ASCII.
license = {
    "licenses": {
        "de_DE": lizenztext,
        "en_US": lizenztext,
    },
}
