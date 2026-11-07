# Firmware für den ESP32-C3-Zero

- `version.txt` – Versionsnummer der Firmware, die hier liegt (z. B. `2.1`). Der ESP vergleicht sie beim Einschalten mit seiner eigenen `FIRMWARE_VERSION` (im Sketch) und lädt `pfeil_licht.bin`, wenn die Nummer hier größer ist.
- `pfeil_licht.bin` – kompilierte Firmware (Arduino IDE: *Sketch → Kompilierte Binärdatei exportieren*, Board ESP32C3 Dev Module, USB CDC On Boot: Enabled; wird die Datei größer als 1,2 MB: Partition Scheme „Minimal SPIFFS (1.9MB APP with OTA)“, das muss dann einmal per USB auf den ESP).

Neue Version veröffentlichen: `FIRMWARE_VERSION` im Sketch hochzählen, Binärdatei exportieren, hierher kopieren, `version.txt` auf dieselbe Nummer setzen, pushen.
