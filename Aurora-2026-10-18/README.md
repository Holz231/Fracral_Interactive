# Aurora — 60-FPS-Version (18.10.2026)

Starte `AuroraFractal.exe` oder `Weiterfliegen.lnk`. Die Verknüpfung setzt deinen
letzten Flug fort (kopiert aus `Fraktals-Weiter/last-flight.aurora` vom 17.10., 21:58).
Steuerung, Welten, Paletten und Qualitätsstufen sind unverändert.

## Was behoben ist

**Pixelrauschen und Flimmern.** Wände, die man sehr flach sieht, und feine Löcher
kleiner als ein Pixel erschienen als Salz-und-Pfeffer-Rauschen, das bei jeder
Bewegung flackerte (Beispiele: `validation/images/corner-top.png`, `p0817-right.png`).
Neu ist eine zeitliche Kantenglättung (TAA): Jedes Bild tastet leicht versetzte
Positionen ab. Das Ergebnis wird über die exakte Kamerabewegung und Tiefe mit dem
Vorbild verrechnet und bei Verdeckungen automatisch verworfen. Starkes Flimmern
(Pixel mit mehr als 32 Helligkeitsstufen Sprung pro Bild) sank bei langsamer
Bewegung von 10.728 auf 787 Pixel pro Bild. Vergleich: `validation/images/taa-compare.png`.

## Was schneller ist

1. **Fraktal-Kern.** Die Faltungen der Störungsrechnung nutzen jetzt auf der CPU
   doppelt genau vorberechnete Grenzabstände (wie Astras Kugelkorrektur, jetzt auch
   für die Box-Faltung). Das vermeidet Auslöschung und braucht etwa ein Drittel der
   Rechenoperationen. Der Wechsel zur direkten Rechnung erfolgt, sobald der
   Rundungsfehler unter 1/100.000 Pixel liegt (vorher 1/1.000).
2. **Streifende Strahlen.** Strahlen, die nach 512 Schritten noch an einer Fläche
   entlanggleiten, bekommen eine sanft wachsende Trefferschwelle bis höchstens etwa
   ein Pixel. Das betrifft nur die längsten Strahlen.
3. **Beleuchtung.** Normale und Umgebungsverdeckung teilen sich eine Orbit-Suche pro
   Pixel statt je eine pro Abtastung.
4. **Ablauf.** 20 statt 33 Nachzügler-Durchläufe pro Bild.
5. **Sicherheitsnetz.** Wenn ein Bild das GPU-Budget von 13,5 ms überschreitet, sinkt
   die intern gerechnete Auflösung sanft (höchstens auf 75 % pro Achse, bei Ultra
   auf 55 %). Die
   Kantenglättung setzt daraus wieder das volle Bild zusammen. In den Tests lag der
   Wert meist bei 96–100 %. Die Anzeige oben rechts zeigt ihn dann, z. B. `· 96 %`.
6. **Ultra.** Ultra nutzt jetzt denselben Ablauf wie Balanced: gebündelte Strahlen,
   Kantenglättung und Sicherheitsnetz. Seine eigene Beleuchtung (8 Schatten- und
   4 Verdeckungsschritte) und die Grenze von 5 Megapixeln bleiben. Den zweiten
   Abtastpunkt pro Pixel des alten Einzeldurchlaufs ersetzt die Kantenglättung: Sie
   sammelt die leicht versetzten Abtastpunkte aufeinanderfolgender Bilder. Die Welt
   Iridescent Vaults (Taste T) rendert weiter im bisherigen Einzeldurchlauf.
7. **Ultra im 4K-Vollbild.** Das Sicherheitsnetz darf bei Ultra bis auf 55 % pro
   Achse gehen statt 75 %. Es greift nur, wenn ein Bild sonst zu lange dauert;
   Performance und Balanced bleiben bei 75 %.
8. **Anlauf in Ultra 4K.** Nach F (Vollbild), K (Qualitätsstufe) oder dem Start mit
   einem Fenster über 5 Megapixel beginnt Ultra im Flug bei 55 % pro Achse statt bei
   voller Auflösung. Das Sicherheitsnetz regelt ab dem ersten gemessenen Bild nach
   und darf in den ersten 20 Bildern direkt auf den passenden Wert springen. Vorher
   rechnete Ultra die ersten etwa 20 Bilder mit voller Auflösung (bis 35 ms pro Bild)
   und ruckelte eine Drittelsekunde lang. Standbilder in der Pause rechnet Ultra wie
   bisher mit voller Auflösung; der Start bei 55 % greift erst, wenn du weiterfliegst.
   Balanced, Performance und Ultra im Fenster bleiben unverändert.

Gleich geblieben sind Geometrie, Julia-Konstante, Iterationsgrenzen, das Budget von
8192 Schritten, Sichtweite, Beleuchtungsmodell und die Pixelgrenzen der Stufen
Performance, Balanced und Ultra.

## Messwerte

RTX 4070 SUPER, 1980 × 1058, Balanced. Flug über 600 Bilder mit echter Ausgabe
(V-Sync, Swapchain), Hin- und Rückflug ab gespeicherten Ansichten:

| Strecke | Astra | Neu |
|---|---|---|
| deine langsamste Aufnahme (Hauptordner) | 36,5 FPS, 366 Bilder über 20 ms | 60,0 FPS, 0 |
| deine langsamste Aufnahme (Preview, 08:17) | 44,3 FPS, 201 Bilder über 20 ms | 60,0 FPS, 0 |
| Ecke mit Kantenproblem | 59,7 FPS, 3 Bilder über 20 ms | 60,0 FPS, 0 |
| Korridor „slow-69ms“ | 60,0 FPS, 0 | 60,0 FPS, 0 |

Reine GPU-Zeit pro Bild bei voller Auflösung (ohne Sicherheitsnetz), Auswahl:

| Ansicht | Astra | Neu |
|---|---:|---:|
| deine langsamste Aufnahme (Hauptordner) | 28,9 ms | 16,1 ms |
| deine langsamste Aufnahme (Preview) | 27,4 ms | 15,5 ms |
| Ecke | 21,1 ms | 11,6 ms |
| Korridor slow-69ms | 16,4 ms | 9,9 ms |

Über alle 14 gespeicherten Ansichten: im Mittel 37 % weniger GPU-Zeit
(`validation/views`). Rohdaten der Flüge: `validation/flights`.

### Ultra

Reine GPU-Zeit pro Bild bei 1980 × 1058 und voller Auflösung (ohne Sicherheitsnetz).
Alter Einzeldurchlauf gegen neuen Ablauf, abwechselnd in drei Runden gemessen,
jeweils der beste Wert:

| Ansicht | Ultra alt | Ultra neu | Balanced zum Vergleich |
|---|---:|---:|---:|
| deine langsamste Aufnahme (Hauptordner) | 102,4 ms | 16,7 ms | 15,9 ms |
| deine langsamste Aufnahme (Preview) | 166,3 ms | 16,1 ms | 15,3 ms |
| Ecke | 70,8 ms | 12,1 ms | 11,4 ms |
| Korridor slow-69ms | 183,3 ms | 10,1 ms | 9,7 ms |
| alle 14 Ansichten zusammen | 945,7 ms | 112,6 ms | 106,6 ms |

Ultra braucht damit im Mittel 78 % weniger GPU-Zeit pro Ansicht und ist insgesamt
8,4-mal so schnell. Es kostet jetzt nur noch etwa 6 % mehr als Balanced.
Flug mit echter Ausgabe wie oben (600 Bilder, Ultra): auf allen vier Strecken
60,0 FPS und kein Bild über 20 ms.

Im 4K-Vollbild (3840 × 2160) rechnet Ultra intern mit 2980 × 1676 Pixeln (5 MP),
Balanced mit 1932 × 1086:

| Ansicht | Ultra alt | Ultra neu | Balanced zum Vergleich |
|---|---:|---:|---:|
| deine langsamste Aufnahme (Hauptordner) | 195,5 ms | 34,6 ms | 15,7 ms |
| deine langsamste Aufnahme (Preview) | 397,0 ms | 32,5 ms | 15,2 ms |
| Ecke | 121,3 ms | 23,6 ms | 11,7 ms |
| Korridor slow-69ms | 360,4 ms | 22,5 ms | 9,9 ms |
| alle 14 Ansichten zusammen | 1.945,8 ms | 235,0 ms | 108,5 ms |

Mit dem Sicherheitsnetz bis 55 % hält Ultra im 4K-Vollbild 60 FPS. Flug mit echter
Ausgabe in 3840 × 2160 (600 Bilder, V-Sync, je zwei Durchläufe), ab dem 25. Bild:

| Strecke | Ultra mit 75 % | Ultra mit 55 % | Balanced zum Vergleich |
|---|---|---|---|
| deine langsamste Aufnahme (Hauptordner) | 51,0 FPS, 101 Bilder über 20 ms | 60,0 FPS, 0 | 60,0 FPS, 0 |
| deine langsamste Aufnahme (Preview) | 55,9 FPS, 42 | 60,0 FPS, 0 | 60,0 FPS, 0 |
| Ecke mit Kantenproblem | 60,0 FPS, 0 | 60,0 FPS, 0 | 60,0 FPS, 0 |
| Korridor „slow-69ms“ | 60,0 FPS, 0 | 60,0 FPS, 0 | 60,0 FPS, 0 |

In den beiden langsamsten Aufnahmen rechnet Ultra dann intern meist mit 55–68 %
pro Achse (1640 × 920 bis 2040 × 1150 Pixel) und wirkt dort weicher, etwa so scharf wie
Balanced, aber mit den Ultra-Schatten. In allen anderen Ansichten bleibt das Bild
wie vorher. Vergleich: `validation/images/ultra-4k-vergleich.png`.

Anlauf in 4K (Ultra, echte Ausgabe mit V-Sync, sechs Strecken von schwer bis leicht,
je zwei Durchläufe): Bilder über 20 ms in der ersten Sekunde, Summe über die sechs
Strecken:

| Ereignis | vorher | jetzt |
|---|---:|---:|
| F: Fenster 1980 × 1058 → Vollbild | 36,5 | 0 |
| K: Balanced → Ultra im Vollbild | 44,5 | 0 |
| in der Pause F bzw. K, dann weiterfliegen | 39,5 / 47 | 1 / 1,5 |
| Programmstart direkt in 4K | 62,5 | 2* |

\* Das zweite Bild nach dem Öffnen wartet einmalig auf die erste Ausgabe, wie bei
Balanced. Leichte Ansichten sind nach F oder K etwa zehn Bilder lang weicher (nach
zwei Bildern etwa halb so viel Detail, nach 30 Bildern gleich), schwere zeigen sofort
die Schärfe des Dauerflugs. Vergleich: `validation/images/ultra-4k-anlauf.png`.
Gegenprobe im sichtbaren Fenster mit echten Tastendrücken (deine langsamste Aufnahme,
Autopilot, je zwei Läufe): vorher nach K 15 und nach F 17 Bilder über 20 ms in der ersten
Sekunde, jetzt 0.

Außerdem blieben im alten Ultra einzelne Strahlen nach 8192 Schritten unfertig und
ergaben Fehlpixel: über die 14 Ansichten 3.904 Pixel bei 1980 × 1058 und 13.898 im
4K-Vollbild. Im neuen Ultra sind es 0.

## Prüfungen

- CTest 2/2 (Geometrie, Kontinuität).
- `--benchmark`: alle Qualitätsstufen (Ultra jetzt im neuen Ablauf), Paletten,
  Größenänderung, Steuerung, Pause; Vaults-Culling pixelgleich.
- `--regression`: GPU/CPU-Feld bei Zoom 1, 10^6, 10^24 und 10^80 bestanden.
- `--field-regression` an der Ecke: Toleranzverhältnis 0,54 (Grenze 1,0).
- Balanced rendert nach der Ultra-Umstellung auf allen 14 Ansichten pixelgleich
  wie vorher.
- Nach der 55-%-Grenze für Ultra: Balanced (1980 × 1058 und 4K) und Ultra ohne
  Sicherheitsnetz rendern auf allen 14 Ansichten pixelgleich wie vorher;
  `--regression` und `--field-regression` liefern dieselben Werte.
- Nach dem Anlauf-Fix: Balanced und Ultra (1980 × 1058 und 4K, mit und ohne
  Kantenglättung) rendern auf allen 14 Ansichten pixelgleich wie vorher; `--benchmark`
  bestanden, `--regression` und `--field-regression` liefern dieselben Werte.

## Bekannte Grenzen

- Einzelne Pixel weichen von Astras Bildern ab, vor allem an streifenden Kanten.
  Astras strenge Gleichheitsprüfungen `--gaps` und `--replay` melden diese
  Unterschiede weiterhin. `--gaps` vergleicht Ultra jetzt mit einem Einzeldurchlauf
  mit einem Abtastpunkt; die Abweichungen liegen dort in derselben Größenordnung
  wie bei Performance und Balanced.
- Nach F, K oder dem Start in 4K beginnt Ultra im Flug bei 55 % pro Achse. Leichte
  Ansichten sind dadurch etwa zehn Bilder lang (rund 0,2 s) weicher, bis Sicherheitsnetz
  und Kantenglättung nachgezogen haben; schwere Ansichten laufen ohnehin mit 55–60 %.
- Beim Wechsel zwischen maximiertem Fenster und Vollbild (F) oder beim Maximieren
  verzögern sich ein bis drei Bilder, weil Windows die Darstellung umstellt. Das ist
  unabhängig von der Grafiklast und war in der vorigen Version genauso, auch bei Balanced.
- Ein plötzlicher Lastsprung, auch durch andere Programme auf der GPU, kann ein
  einzelnes Bild verzögern, bis die Auflösung nach etwa drei Bildern nachgeregelt ist.

## Neu bauen

Visual Studio 2022, Windows SDK und CMake:

```powershell
cmake -S Source -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release --parallel
ctest --test-dir build -C Release --output-on-failure
```

Diagnose (Umgebungsvariablen): `AURORA_TEMPORAL=0` schaltet die Kantenglättung ab
(Ultra rechnet dann nur einen Abtastpunkt pro Pixel), `AURORA_DRS=0` das
Sicherheitsnetz, `AURORA_FRAME_BUDGET` setzt das GPU-Budget in ms.
Messmodi: `--bench-views`, `--fly-views`, `--diag-views` (siehe `validation/tools`).
`AURORA_BENCH_QUALITY=2` wählt in `--bench-views`, `--fly-views` und
`--flight-profile` die Stufe Ultra.
