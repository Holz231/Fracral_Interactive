# Roadmap Geisterrennen

Stand 11.11.2026. Im Spiel: drei feste Strecken, Schiff als Körper im Bild vor
einer Verfolgerkamera, Crash am echten Wandabstand, Geist, Bestzeiten.

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
sieht.

## 2. Schiff als echter Körper im Bild (GPU) — erledigt

Das Schiff wird im Beleuchtungsdurchlauf zusammen mit dem Fraktal gerechnet:

- Zwei Triebwerksgondeln, Kabine und Strebe als Abstandsfeld, pro Pixel entlang
  des Sichtstrahls innerhalb der Rumpfkugel verfolgt und mit der Treffertiefe des
  Fraktals verglichen. Das ergibt die Verdeckung in beide Richtungen.
- Eigenes Licht mit derselben Lichtrichtung, Glanz auf der Kabine, Triebwerke
  leuchten türkis, mit Shift orange, nach dem Crash rot.
- Schatten des Schiffs auf dem Fraktal (weiche Kugel) und eine Abdunklung der
  Fläche bis etwa 2,6 Rumpfradien um das Schiff.
- Kantenglättung: Schiffspixel sind im gerechneten Bild markiert (Alpha 0,75) und
  nehmen ihren Verlauf vom selben Bildpunkt statt über die Tiefe des Fraktals
  dahinter. Verlauf mit Schiff ist eigens markiert, damit Schiff und Fläche sich
  beim Wechsel nicht mischen.
- Eigene Shader-Varianten (`RACE_SHIP`); alle anderen Shader sind unverändert.

Geprüft: `--race-check` zählt Schiffspixel vor der Oberfläche (11.396) und hinter
ihr (0). Bilder mit und ohne Kantenglättung nach einer Sekunde Flug ohne Schlieren.
14 Ansichten außerhalb des Rennens pixelgleich. GPU-Zeit im Rennen mit und ohne
Schiff: 2,47 gegen 2,46 ms, 2,44 gegen 2,43 ms, 2,28 gegen 2,28 ms (1600 × 900,
Balanced).

Nicht gemacht:

- Das Fraktal wirft keinen Schatten auf das Schiff.
- Der Geist ist weiter ein flacher Kreis; er könnte denselben Körper
  halbtransparent bekommen.
- Der Schatten des Schiffs fällt durch dünne Wände, weil er nicht gegen das
  Fraktal geprüft wird.
- Schneller Schwenk und 4K sind nur von Hand zu beurteilen, das steht noch aus.

## Als Nächstes

Von Hand spielen und Tempo, Schiffsgröße, Schrumpfrate und Kameraarm festlegen.
Danach die Punkte unter „Nicht gemacht“ und die kleineren Punkte unten.

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
