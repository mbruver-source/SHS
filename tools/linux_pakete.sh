#!/usr/bin/env bash
# Baut aus dem PyInstaller-Ordner dist/SHS-Pruefungsprogramm/ (build.spec unter Linux) das
# AppImage und das .deb-Paket (Linux-Vorschau, Marco 07.10.2026). Läuft in der CI
# (build-installer.yml, Job build-linux) auf Ubuntu 22.04.
#
#   tools/linux_pakete.sh <version> <appimagetool> <runtime>
#
# <appimagetool> und <runtime> sind die vorher geladenen und per Prüfsumme geprüften Dateien
# (S-3: keine ungeprüften Downloads; appimagetool lädt die Runtime sonst selbst nach).
#
# Ergebnis in Output/:
#   SHS-Pruefungsprogramm-<version>-x86_64.AppImage
#   shs-pruefungsprogramm_<version>_amd64.deb
set -euo pipefail

VERSION="$1"
APPIMAGETOOL="$2"
RUNTIME="$3"

if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Version hat nicht das Format X.Y.Z: $VERSION" >&2
  exit 1
fi

NAME="SHS-Pruefungsprogramm"
PAKET="shs-pruefungsprogramm"
QUELLE="dist/$NAME"
AUSGABE="Output"
ARBEIT="$(mktemp -d)"
trap 'rm -rf "$ARBEIT"' EXIT

test -x "$QUELLE/$NAME" || { echo "$QUELLE/$NAME fehlt - zuerst 'pyinstaller build.spec'" >&2; exit 1; }
mkdir -p "$AUSGABE"

desktop_datei() {  # $1 = Exec-Zeile
  cat <<EOF
[Desktop Entry]
Type=Application
Name=SHS-Prüfungsprogramm
Comment=Prüfungsverwaltung für den Spürhundsport
Exec=$1
Icon=$PAKET
Terminal=false
Categories=Office;
StartupWMClass=$NAME
EOF
}

# --- AppImage ---------------------------------------------------------------------------
APPDIR="$ARBEIT/AppDir"
mkdir -p "$APPDIR/usr/lib" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/512x512/apps"
cp -a "$QUELLE" "$APPDIR/usr/lib/$PAKET"
cat > "$APPDIR/AppRun" <<EOF
#!/bin/sh
HERE="\$(dirname "\$(readlink -f "\$0")")"
exec "\$HERE/usr/lib/$PAKET/$NAME" "\$@"
EOF
chmod 755 "$APPDIR/AppRun"
desktop_datei "$NAME" > "$APPDIR/$PAKET.desktop"
cp "$APPDIR/$PAKET.desktop" "$APPDIR/usr/share/applications/"
cp symbol/programmsymbol.png "$APPDIR/$PAKET.png"
cp symbol/programmsymbol.png "$APPDIR/usr/share/icons/hicolor/512x512/apps/$PAKET.png"

# --appimage-extract-and-run: auf den CI-Runnern gibt es kein FUSE.
ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run --runtime-file "$RUNTIME" \
  "$APPDIR" "$AUSGABE/$NAME-$VERSION-x86_64.AppImage"

# --- .deb -------------------------------------------------------------------------------
PKG="$ARBEIT/deb"
mkdir -p "$PKG/DEBIAN" "$PKG/opt" "$PKG/usr/bin" "$PKG/usr/share/applications" \
  "$PKG/usr/share/icons/hicolor/512x512/apps"
cp -a "$QUELLE" "$PKG/opt/$PAKET"
ln -s "/opt/$PAKET/$NAME" "$PKG/usr/bin/$PAKET"
# Exec auf das Programm selbst statt auf den Link in /usr/bin: Qt leitet die Fensterklasse
# (X11, StartupWMClass) aus dem Programmnamen ab, der Link heißt kleingeschrieben.
desktop_datei "/opt/$PAKET/$NAME" > "$PKG/usr/share/applications/$PAKET.desktop"
cp symbol/programmsymbol.png "$PKG/usr/share/icons/hicolor/512x512/apps/$PAKET.png"
GROESSE_KB="$(du -sk "$PKG" | cut -f1)"
# Qt (xcb) braucht diese Systembibliotheken; PySide6 bringt Qt selbst mit.
cat > "$PKG/DEBIAN/control" <<EOF
Package: $PAKET
Version: $VERSION
Section: misc
Priority: optional
Architecture: amd64
Installed-Size: $GROESSE_KB
Depends: libc6 (>= 2.35), libglib2.0-0, libgl1, libegl1, libopengl0, libfontconfig1, libxkbcommon0, libxkbcommon-x11-0, libdbus-1-3, libxcb-cursor0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, libxcb-shape0, libxcb-xfixes0, libxcb-xinerama0, libxcb-xkb1
Maintainer: Marco <m.bruver@gmail.com>
Homepage: https://mbruver-source.github.io/SHS/
Description: SHS-Prüfungsprogramm (Vorschau)
 Verwaltung von Spürhundsport-Prüfungen: Teilnehmer, Zeitplan, Ergebnisse,
 Auswertung und Ausdrucke. Vorschau-Version für Linux.
EOF
find "$PKG" -type d -exec chmod 755 {} +
dpkg-deb --root-owner-group --build "$PKG" "$AUSGABE/${PAKET}_${VERSION}_amd64.deb"

ls -l "$AUSGABE"
