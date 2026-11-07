# Firmware für den ESP32-C3-Zero

- `version.txt` – Nummer der Firmware, die hier liegt. Der ESP vergleicht sie beim Einschalten mit seiner eigenen `FIRMWARE_VERSION` (im Sketch) und lädt `pfeil_licht.bin`, wenn die Nummer hier größer ist.
- `pfeil_licht.bin` – kompilierte Firmware (Arduino IDE: *Sketch → Kompilierte Binärdatei exportieren*, Board ESP32C3 Dev Module, USB CDC On Boot: Enabled).

Neue Version veröffentlichen: `FIRMWARE_VERSION` im Sketch hochzählen, Binärdatei exportieren, hierher kopieren, `version.txt` auf dieselbe Nummer setzen, pushen.
