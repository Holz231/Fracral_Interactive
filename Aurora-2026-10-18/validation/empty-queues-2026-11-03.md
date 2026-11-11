# Weniger Arbeit für leere Strahlen-Warteschlangen — 03.11.2026

Die GPU-Vorbereitung überspringt jetzt die Präfixsumme über 128 Sortierfächer,
wenn keine Strahlen mehr übrig sind. Die indirekten Dispatch-Argumente werden
zuvor vollständig zurückgesetzt. Aktive Strahlen behalten ihre bisherige
Sortierung und Bearbeitungsreihenfolge.

Alle 20 Durchläufe und das Budget von 8192 akzeptierten Schritten bleiben
verfügbar. Auflösung, Geometrie, Beleuchtung und zeitliche Kantenglättung sind
gleich. Die Umschaltung nutzt ein bislang freies Feld des vorhandenen
Konstantenpuffers; zusätzliche GPU-Puffer sind nicht erforderlich.

## Messungen gegen die bisher installierte EXE

RTX 4070 SUPER, 3840 × 2160 Ausgabe, Balanced, zeitliche Kantenglättung an,
dynamische Auflösung aus. Drei abwechselnde Vorher-/Nachher-Runden mit jeweils
32 gemessenen Bildern pro Ansicht und vorherigem Warmlauf.

Median der drei Rundenmediane:

| Ansicht | Vorher | Jetzt |
|---|---:|---:|
| slowstart56 | 3,06 ms | 2,92 ms |
| user-root-last | 3,69 ms | 3,54 ms |
| stutter | 4,43 ms | 4,29 ms |
| interior | 6,84 ms | 6,78 ms |
| corner | 11,66 ms | 11,64 ms |
| user-root-slow | 16,26 ms | 16,14 ms |

Die Summe der besten Einzelzeiten über alle 14 Ansichten sinkt von **110,22 auf
109,04 ms**, ungefähr **1,1 %**. In leichten Ansichten beträgt die Einsparung
etwa 3–5 %, in schweren fällt sie kleiner aus oder liegt im Messrauschen.
Gemessen wurde GPU-Zeit; dies ist keine Messung zusätzlicher Bildschirm-FPS.

## Prüfungen

- CTest **4/4** bestanden. Der neue GPU-Test beginnt mit absichtlich veralteten
  Dispatch-Werten und prüft, dass ein leeres Paket sie auf gültige Null-Arbeit
  zurücksetzt. Er prüft außerdem, dass die unbenutzten Sortierfächer unberührt
  bleiben und eine nichtleere Warteschlange weiterhin korrekt summiert wird.
- **30 identische 4K-PNG-Paare** über Performance, Balanced und Ultra, einschließlich
  zweier aktueller Benutzeraufnahmen. In allen Ansichten null unfertige Pixel.
- **8.379.360 bitgleiche Treffertiefen und Strahlzustände** in vier schweren
  Ansichten bei 1980 × 1058.
- Zwei Flüge über je 120 feste Simulationsschritte in 4K: alle **10 erfassten
  Bildpaare** und beide abschließenden Kameradateien sind identisch.
- Der direkte EXE-Vergleich über alle 14 Ansichten liefert dieselben Bilder.
- `--benchmark`, `--regression` und `--field-regression` bestanden. Der Feldtest
  liegt unverändert bei einem maximalen Toleranzverhältnis von 0,544497.

Ein Versuch, die Sortierung auch für aktive späte Strahlenpakete wegzulassen,
zeigte in einem bewegten Test einen Leistungsnachteil und wurde verworfen.
Ausgeliefert wird ausschließlich die Abkürzung für vollständig leere Pakete.

## Diagnose und Reproduktion

```powershell
ctest --test-dir Aurora-2026-10-18/build -C Release --output-on-failure
python Aurora-2026-10-18/validation/tools/scheduling_checks.py Aurora-2026-10-18/build/Release/AuroraFractal.exe Aurora-2026-10-18/build/validation/scheduling-2026-11-03/reproduce
```

`AURORA_EMPTY_SCAN=0` aktiviert die bisherige Vorbereitung für A/B-Messungen.
`--batch-views <output> <width> <height> <frames> <fixtures...>` schreibt zusätzlich
die Strahlenzahlen und GPU-Intervalle jedes Durchlaufs. Die Diagnosetiefen werden
jetzt mit den Frame-Konstanten des zugehörigen Bildes erfasst.

Die Vergleichsskripte `ab.py` und `fly.py` unterstützen nun `--output`, damit
Messdaten im Build-Ordner bleiben. `ab.py` speichert sämtliche Rundenzeiten als
JSON; `fly.py` meldet fehlgeschlagene Teilflüge mit einem Fehlercode.

Rohdaten, verworfener Versuch und bisherige EXE liegen unter
`build/validation/scheduling-2026-11-03/`. Zusammengefasste Ergebnisse stehen in
`validation/checks/empty-queues-2026-11-03.json`.
