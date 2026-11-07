# Einkaufsliste Raumjäger „Pfeil“ (bis Samstag)

Die Links sind Amazon-Suchen. Die Produktseiten kann ich selbst nicht öffnen. Setz links den Haken bei **Prime** und prüf auf der Produktseite die Punkte in „Darauf achten“. Wenn das Lieferdatum „bis Freitag“ zeigt, passt es.

| # | Teil | Menge | Amazon-Suche | Darauf achten |
| --- | --- | --- | --- | --- |
| 1 | ESP32-C3 SuperMini oder Waveshare ESP32-C3-Zero | 1 | [ESP32-C3 SuperMini gelötet](https://www.amazon.de/s?k=ESP32-C3+SuperMini+gel%C3%B6tet) | **mit angelöteten Stiftleisten** („soldered“, „mit Pins“, „vorgelötetem Header“), USB-C. Tim nimmt den C3-Zero (Variante Dev Board-M). |
| 2 | Adressierbare Draht-Lichterkette (gewählt: BTF-LIGHTING 5 m, 50 LEDs) | 1 | [WS2812B Fairy Lichterkette adressierbar 5V](https://www.amazon.de/s?k=WS2812B+Fairy+Lichterkette+adressierbar+5V) | **5 V**, WS2812B oder SK6812, **dünner Draht** statt 12-mm-Kapseln, mindestens 40 LEDs, Abstand am besten 5 cm (10 cm geht auch), 3 Adern am Eingang |
| 3 | ~~Adapter für die Kette~~ | 0 | entfällt | Du schneidest den Stecker am **Ende** der Kette mit etwa 5 cm Kabel ab. Er passt auf den Eingang, die offenen Adern kommen in die Wago-Klemmen. |
| 4 | JST-SM-3-Pin-Verlängerung 1 m (gewählt: GTIWUNG 4er-Set) | 1 Set | [JST SM 3 Pin Verlängerung 1m](https://www.amazon.de/s?k=JST+SM+3+Pin+Verl%C3%A4ngerung+1m) | Stecker auf Buchse. Für 2 m steckst du zwei zusammen. Am Griff-Ende schneidest du den Stecker ab, die Adern gehen in die Wago-Klemmen. Ersetzt das Servokabel. |
| 5 | Dupont-Kabel-Set | 1 | [Dupont Jumper Kabel Set](https://www.amazon.de/s?k=Dupont+Jumper+Kabel+Set+female+male) | Buchse–Buchse und Buchse–Stecker, 20 cm |
| 6 | Arcade-Taster 24 mm | 2 (rot + blau) | [Arcade Button 24mm Kabel](https://www.amazon.de/s?k=Arcade+Button+24mm+Set+Kabel) | 24 mm mit Mikroschalter. Ein Set mit Kabeln (2,8-mm-Steckhülsen) ist ideal. Oft gibt es 10er-Sets mit gemischten Farben. |
| 8 | Magnetisches USB-C-Kabel | 1 | [magnetisches USB C Ladekabel 2m](https://www.amazon.de/s?k=magnetisches+USB+C+Ladekabel+2m) | USB-A auf Magnet-USB-C, 1,5–2 m |

Schon vorhanden: Powerbank, Wago-Klemmen, Kabelbinder, Schrauben, Transparentpapier, Heißkleber, Schnur.

## Falls Amazon nicht bis Samstag liefert

- **Berrybase** (berrybase.de) und **Eckstein** (eckstein-shop.de) verschicken aus Deutschland, meist in 1–2 Tagen. Dort gibt es ESP32-C3-Boards, Dupont-Kabel, Arcade-Taster und WS2812-Ketten.
- Eine fertige Alternative zur Lichterkette ist das „Flexible RGB LED Wire, 5 m, 50 LEDs“ (WS2812/SK6812, 10 cm Abstand) von [Pimoroni](https://shop.pimoroni.com/en-eu/products/5m-flexible-rgb-led-wire-50-rgb-leds-aka-neopixel-ws2812-sk6812). Bei 10 cm Abstand landet in jeder Kanone nur eine LED pro Weg. Das sieht trotzdem gut aus.

## Wenn die Kette einen USB-Stecker oder eine Fernbedienung hat

Viele Ketten werden mit kleinem Controller und USB-Stecker verkauft. Den Controller brauchst du nicht. Meist sitzt zwischen Controller und Kette ein 3-poliger Stecker: Dort trennst du und steckst dein Kabel an. Gibt es dort keinen Stecker, schneid das Kabel hinter dem Controller ab, isolier die 3 Adern ab und steck sie in Wago-Klemmen. Die Adern sind: 5 V (meist rot), GND (meist weiß oder schwarz) und Daten (meist grün). Schick mir im Zweifel ein Foto, bevor du schneidest.
