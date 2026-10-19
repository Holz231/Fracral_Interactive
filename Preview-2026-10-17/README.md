# Aurora — Accelerated Preview

Native Windows-Vorschau vom 17.10.2026. Starte `AuroraFractal.exe`, oder verwende
`Weiterfliegen.lnk`, um den in diesem Ordner gespeicherten Flug zu laden.
WASD bewegt, rechte Maustaste dreht, F schaltet Vollbild, G den geführten Flug,
K die Qualitätsstufe. Die Beschleunigung ist für Citadel/Balanced optimiert.

Die Korrektur vom 17.10. behebt die nachgestellten schwarzen, verrauschten
Flächen an Kanten. Kleine Grenzabstände der Fraktalberechnung bleiben jetzt
beim Übertragen auf die GPU erhalten. Auflösung und Detailstufe bleiben gleich.
Der getestete Flug lief mit knapp 60 FPS; einzelne langsame Frames und
schwierige statische Ansichten sind noch offen. Ergebnisse: `Validation.md`.
Der vorherige Beschleunigungsbericht steht in `Acceleration-history.md`.

Beim Start wird die GPU kurz vorbereitet. Einstellungen, Flugposition und
automatisch erfasste langsame Ansichten werden in diesem Vorschauordner abgelegt.
F9 speichert die aktuelle Position. Die bisherige Programmversion im übergeordneten
Ordner bleibt separat verfügbar.

`Source` enthält den vollständigen Quellstand dieser EXE. Neu bauen mit Visual
Studio 2022 / Windows SDK und CMake:

```powershell
cmake -S Source -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release --parallel
ctest --test-dir build -C Release --output-on-failure
```
