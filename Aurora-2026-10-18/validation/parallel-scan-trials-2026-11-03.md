# Weitere GPU-Prüfung — 03.11.2026

Zwei Varianten einer parallelen Präfixsumme für die 128 Sortierfächer wurden
gegen die installierte EXE getestet. Keine zeigte einen verlässlichen Vorteil
über die geprüften Ansichten. Beide Varianten wurden verworfen; die
Produktionsshader und die installierte EXE sind gegenüber Beginn dieser Prüfung
unverändert. Als dauerhafte Änderung bleiben erweiterte GPU-Grenzfalltests.

## Messung

RTX 4070 SUPER, 3840 × 2160 Ausgabe, Balanced, zeitliche Kantenglättung an,
dynamische Auflösung aus. Dieselbe bisherige EXE lief mit eingebetteten Shadern
und abwechselnd mit dem Shader-Override des jeweiligen Versuchs.

- **128 Threads:** Jeder Thread summiert ein Sortierfach. Drei abwechselnde
  Runden, 14 Ansichten, je 32 gemessene Bilder und 16 Warmlaufbilder.
- **32 Threads:** Jeder Thread summiert vier aufeinanderfolgende Fächer lokal;
  anschließend werden die 32 Teilsummen parallel zusammengeführt. Vier
  abwechselnde Runden, fünf Ansichten, je 128 gemessene Bilder und 64
  Warmlaufbilder.

Summe der Zeiten über die jeweils geprüften Ansichten:

| Versuch | Kennzahl | Bisher | Versuch |
|---|---|---:|---:|
| 128 Threads, 14 Ansichten | Summe der besten Einzelzeiten | 109,98 ms | 108,36 ms |
| 128 Threads, 14 Ansichten | Summe der Rundenmediane¹ | 115,53 ms | 118,04 ms |
| 32 Threads, fünf Ansichten | Summe der besten Einzelzeiten | 47,11 ms | 46,73 ms |
| 32 Threads, fünf Ansichten | Summe der Rundenmediane¹ | 50,04 ms | 50,38 ms |

¹ Pro Ansicht zunächst der Median der Rundenmediane, dann die Summe über
Ansichten. Diese Summen dienen dem Vergleich; sie sind keine Bildschirm-FPS.

Die besseren Bestzeiten bestätigen sich insgesamt nicht in den Medianen.
Einzelne leichte Ansichten schwanken deutlich. Die Daten rechtfertigen daher
keine zusätzliche Tempo-Zusage und keine Übernahme der Versuche.

Alle **19 abschließenden PNG-Paare** sind SHA256-identisch. Es wurden keine
Bildunterschiede gefunden. Die Entscheidung gegen die Versuche beruht auf dem
fehlenden verlässlichen Leistungsvorteil.

## Dauerhafte Testverbesserung

`RendererTests::queuePreparation` prüft jetzt **153 Fälle auf der echten GPU**:

- Eine leere Warteschlange mit absichtlich veralteten Dispatch-Argumenten und
  Sortierfächern: gültige Null-Arbeit, unbenutzte Fächer bleiben unberührt.
- Je eine belegte Position in jedem der 128 Sortierfächer.
- Gleichmäßige und stark ungleichmäßige Verteilungen an zwölf Grenzen:
  1, 63, 64, 65, 16.383, 16.384, 16.385, 65.535, 65.536,
  4.194.240, 4.194.304 und 8.294.400 Strahlen.

Die GPU-Ergebnisse werden mit einer unabhängigen seriellen CPU-Präfixsumme
verglichen. Geprüft werden außerdem alle vier indirekten Dispatch-Tripel,
die Umschaltung zwischen Fortsetzung und parallelen Intervallen, die
zweidimensionale Dispatch-Grenze und der unveränderte Strahlzähler.

Der abschließende Release-Build verwendet wieder die ursprünglichen
Produktionsshader. **CTest 4/4 bestanden**, insgesamt 2,57 s; der GPU-Test
benötigte 0,31 s. Die 32-Thread-Versuchsvariante bestand die erweiterten Tests
ebenfalls, bevor sie verworfen wurde.

```powershell
cmake -S Aurora-2026-10-18/Source -B Aurora-2026-10-18/build
cmake --build Aurora-2026-10-18/build --config Release --parallel 2
ctest --test-dir Aurora-2026-10-18/build -C Release --output-on-failure
```

Rohdaten, beide Versuchsshader und die gesicherte vorherige EXE liegen unter
`build/validation/parallel-scan-2026-11-03/`. Sämtliche Rundenzeiten stehen auch
in `validation/checks/parallel-scan-trials-2026-11-03.json`.

Installierte EXE: `AEE3D858EC3A5EDD3F1DFFD0F05F082F56C29AFB4F4D862ADBE8F2F8E8A9543A`.
Wiederhergestellter Shader: `3D0AA56153810189BCA29ED24D3FB3403929509F48F21EE4826D8B84559DC450`.
