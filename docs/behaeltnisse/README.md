# SHS-Behältnisse in 3D

Interaktive 3D-Ansicht der SHS-Behältnisse nach der BLV-Anleitung zum Bau von SHS-Behältnissen:

- LK 1 / LK 2: 5-Liter-Wettkampfeimer (weiß) mit 3 bzw. 4 Geruchskammern, 8-mm-Öffnungen,
  3 Schrauben durch den Boden, Betonhöhe einstellbar mit Gewichtsangabe
- LK 3: Holzkiste (innen 38 x 26 x 28 cm, ca. 28 l) mit 5 Gläsern, Öffnungen 6-8 mm

Bedienung: Ziehen zum Drehen, Mausrad oder zwei Finger zum Zoomen, Glas antippen zum Entnehmen.
Es wird nichts gespeichert; jeder Aufruf startet im Ausgangszustand.

## Start

`index.html` im Browser öffnen. Läuft ohne Server und ohne Internet
(three.js liegt in `vendor/`). Es werden keine externen Schriften oder CDNs geladen (wie auf der
übrigen Website); die Seite nutzt die Systemschrift.

Auf der GitHub Page ist die Seite unter `behaeltnisse/` erreichbar (Menüpunkt "Behältnisse").

## Abhängigkeiten

- three.js r128 (`vendor/three.min.js`, `vendor/OrbitControls.js`), MIT-Lizenz, siehe `vendor/LICENSE-three.txt`
