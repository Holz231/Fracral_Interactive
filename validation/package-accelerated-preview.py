"""Package the validated native experiment without replacing the installed app."""
from pathlib import Path
import hashlib
import json
import shutil

root = Path(__file__).resolve().parent.parent
experiment = root / 'validation/experiments/cone-segments-native'
destination = root / 'Preview-2026-10-17'
if destination.exists():
    raise SystemExit(f'Preview already exists; preserve its flight/settings: {destination}')
executable = experiment / 'build-copy/Release/AuroraFractal.exe'
if not executable.is_file():
    raise SystemExit('Build the native experiment first')
destination.mkdir()
shutil.copy2(executable, destination / 'AuroraFractal.exe')
for name in ('settings.txt', 'last-flight.aurora'):
    source = root / name
    if source.exists():
        shutil.copy2(source, destination / name)
source_dir = destination / 'Source'
source_dir.mkdir()
for name in ('src', 'tests'):
    shutil.copytree(experiment / name, source_dir / name)
shutil.copy2(experiment / 'CMakeLists.txt', source_dir / 'CMakeLists.txt')
shutil.copy2(root / 'validation/acceleration-2026-10-17.md', destination / 'Validation.md')
(destination / 'README.md').write_text('''# Aurora — Accelerated Preview

Native Windows-Vorschau vom 17.10.2026. Starte `AuroraFractal.exe`, oder verwende
`Weiterfliegen.lnk`, um den in diesem Ordner gespeicherten Flug zu laden.
WASD bewegt, rechte Maustaste dreht, F schaltet Vollbild, G den geführten Flug,
K die Qualitätsstufe. Die Beschleunigung ist für Citadel/Balanced optimiert.

Die schwierige Testansicht benötigt etwa 16,7 statt 30,6 ms GPU-Zeit bei gleicher
Auflösung und Detailstufe. Die getestete Flugstrecke lief nach der Startphase
mit rund 60 FPS. Das ist noch keine Zusage für alle Blickrichtungen: einzelne
Silhouettenpixel weichen ab, und ein langsamer Messlauf ist noch ungeklärt.
Die vollständigen Ergebnisse und Grenzen stehen in `Validation.md`.

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
''', encoding='utf-8')
hashes = {}
for path in sorted(destination.rglob('*')):
    if path.is_file():
        hashes[path.relative_to(destination).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
(destination / 'build-manifest.json').write_text(json.dumps(hashes, indent=2) + '\n', encoding='utf-8')
print(destination)
print('EXE SHA256:', hashes['AuroraFractal.exe'])
