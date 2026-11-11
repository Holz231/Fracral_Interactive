# Roadmap Geisterrennen

Stand 11.11.2026. Im Spiel: drei feste Strecken, sichtbares Schiff vor einer
Verfolgerkamera, Crash am echten Wandabstand, Geist, Bestzeiten.

## 1. Crash am echten Wandabstand (CPU) — erledigt

Der Lauf endet, wenn der Rumpf die Oberfläche berührt. Vom Schiffsmittelpunkt aus
werden 64 gleichmäßig verteilte Strahlen bis zur Oberfläche verfolgt; der kürzeste
ist der Abstand. Er ersetzt die vorsichtige Schätzung beim Crash, bei der Anzeige
`Wall x…` und bei der Größenanpassung des Schiffs.

Was dabei herauskam:

- Die Schätzung lag beim 0,35- bis 0,5-Fachen des gemessenen Abstands. Das war der
  Grund für den viel zu frühen Crash.
- Das Schiff darf beim Schrumpfen nicht an seinem Kameraarm zurückrutschen. Dieser
  Rückzug hob einen Frontalanflug genau auf (das Schiff blieb bei 10 Radien
  hängen). Jetzt bleibt das Schiff an seinem Ort und die Kamera rückt nach.
- Eine Öffnung, die sich immer weiter verfeinert, hat keinen Boden. Dort crasht
  man auch mit Shift nicht, sondern taucht ein. Das ist gewollt.
- Abstimmung: Tempo 0,5 Schiffseinheiten pro Sekunde, Schrumpfrate 0,8 pro
  Sekunde, langsam 40 %.
- Kosten: etwa 0,3 ms CPU pro Simulationsschritt (aus dem Auslegen der Strecken:
  0,7 s für 2.660 Schritte).

Geprüft: Beim Crash liegt die Oberfläche unabhängig nachgemessen zwischen 0,6 und
1,15 Rumpfradien vom Schiffsmittelpunkt, die Kamera ist noch frei. Anflug auf die
nächste Wand crasht bei normalem Tempo und schneller mit Shift; langsam taucht man
ohne Crash ein. `--race-check` fliegt alle drei Strecken ins Ziel; mit Shift auf
die nächste Wand endet der Lauf nach 1,5 bis 1,9 Sekunden.

Offen: von Hand spielen und bestätigen, dass der Crash zu dem passt, was man
sieht. Das hängt auch an Punkt 2, weil das flache Schiff keine Tiefe zeigt.

## 2. Schiff als echter Körper im Bild (GPU)

**Ziel:** Man sieht, wie nah das Schiff der Wand ist, und beim Crash steckt der
Rumpf sichtbar an der Oberfläche.

**Ansatz:** Das Schiff im Shader zusammen mit dem Fraktal rechnen statt als
Overlay:

- Schiffsposition und Rumpfradius pro Bild an den Shader geben (freies Feld im
  Frame-Konstantenpuffer oder ein kleiner eigener Puffer).
- Im Beleuchtungsdurchlauf pro Pixel den Strahl mit dem Schiffskörper schneiden
  (Kugel oder einfache Form aus Kugeln und Kapseln) und mit der Treffertiefe des
  Fraktals vergleichen: Was näher ist, wird gezeichnet. Das ergibt die Verdeckung.
- Schatten des Schiffs auf dem Fraktal: Im Schattenstrahl zusätzlich das Schiff
  testen. Der Schatten läuft beim Annähern auf das Schiff zu und ist der
  wichtigste Hinweis auf den Abstand.
- Eigene Beleuchtung des Schiffs und Triebwerksleuchten; die Kollisionskugel nur
  noch als dünner Rand oder gar nicht.

**Zu beachten:**

- Außerhalb des Rennens muss das Bild pixelgleich bleiben (Prüfung über die 14
  gespeicherten Ansichten wie bisher). Am einfachsten über eine eigene
  Shader-Variante nur für das Rennen.
- Die zeitliche Kantenglättung reprojiziert über die Tiefe des Fraktals. Das Schiff
  bewegt sich mit der Kamera und braucht eine eigene Behandlung, sonst zieht es
  Schlieren oder wird verworfen.
- Temporales Hochskalieren und dynamische Auflösung gelten auch für das Schiff.
- GPU-Zeit im Rennen vorher und nachher messen (Budget 13,5 ms).
- Der Geist könnte denselben Körper halbtransparent bekommen.

**Fertig, wenn:**

- Wände verdecken das Schiff, das Schiff verdeckt Wände, in Bildern geprüft.
- Schatten auf der Oberfläche sichtbar und richtig herum.
- 14 Ansichten außerhalb des Rennens pixelgleich; GPU-Zeit im Rennen gemessen.
- Kein Schlierenziehen bei schnellem Schwenk.

## Reihenfolge

1. Von Hand spielen und Tempo, Schiffsgröße und Schrumpfrate festlegen.
2. Punkt 2 (Eingriff in den Renderer).

## Kleinere Punkte

- Laufender Abstand zum Geist während des Rennens; heute nur im Ziel.
- Ob die Vorgabezeiten des Autopiloten von Hand schlagbar sind, ist ungeprüft.
- Das Schiff sitzt an einem Arm von zwölf Radien vor der Kamera. Schwenken bewegt
  es deshalb stark seitwärts und kann es in eine Wand drücken. Beobachten, ob das
  beim Spielen stört; Abhilfe wäre ein kürzerer Arm oder eine Kamera, die dem
  Schiff nachgeführt wird statt umgekehrt.
- Landen und Verstecken aus der ersten Ideenrunde sind nicht begonnen.
- Aus der Optimierungsrunde offen: `user-preview-last` und `user-preview-slow`
  schwanken zwischen Messrunden stark (etwa 3 ms gegen 5 ms GPU-Zeit), Ursache
  nicht untersucht.
- Nicht mehr benutzt und löschbar: `race-start.aurora` und `race-ghost.bin` im
  Hauptordner (alte, selbst aufgenommene Strecke).
