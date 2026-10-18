# Messdaten und Werkzeuge zur Version 2026-10-18

- `fixtures/`: gespeicherte Kamerapositionen. Darunter Astras Testansichten und deine
  eigenen Aufnahmen (`user-root-*` aus dem Hauptordner, `user-preview*` aus dem Preview).
- `views/`: GPU-Zeit pro Ansicht bei voller Auflösung, Astra gegen neu (`bench.csv`-Format).
- `flights/`: 600-Bilder-Flüge mit echter Ausgabe (`*-new.csv`, `*-astra.csv`) und
  25-Sekunden-Autopilotflüge im sichtbaren Fenster (`*-live-window.csv`).
- `checks/`: Ergebnisse von `--benchmark`, `--regression` und `--field-regression`.
- `images/`: Vorher/nachher-Bilder, Rauschbeispiele, Arbeitskarte der teuren Strahlen.
- `tools/`: Python-Skripte für A/B-Messungen (`ab.py`), Flüge (`fly.py`), Live-Flüge
  (`live.ps1`, `livestats.py`) und Einzelmessungen (`bench.py`).
- `astra-harness/`: Astras Preview-Renderer vom 17.10., nur ergänzt um die Messmodi.
  Dient als Vergleichsbasis, nicht zum Fliegen.
