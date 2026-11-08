# Firmware für den ESP32-C3-Zero

- `version.txt` – Versionsnummer der Firmware, die hier liegt (z. B. `3.5`). Der ESP vergleicht sie beim Einschalten mit seiner eigenen `FIRMWARE_VERSION` (im Sketch) und lädt `pfeil_licht.bin`, wenn die Nummer hier größer ist.
- `pfeil_licht.bin` – kompilierte Firmware.

**Beide Dateien werden automatisch erzeugt:** Sobald sich `elektronik/pfeil_licht/pfeil_licht.ino` auf `main` ändert, kompiliert GitHub Actions (`.github/workflows/firmware.yml`) den Sketch und legt die Dateien hier ab. Nichts von Hand hineinkopieren.

Neue Version veröffentlichen: `FIRMWARE_VERSION` im Sketch hochzählen und pushen, fertig. Die Laterne holt sich die Version beim nächsten Einschalten im Heim-WLAN (raw.githubusercontent.com braucht nach dem Build bis zu 5 Minuten).
