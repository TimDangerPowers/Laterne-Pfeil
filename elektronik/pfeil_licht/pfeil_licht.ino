/*
  Raumjäger „Pfeil“ – Licht für Tonis Laterne
  ESP32-C3-Zero (oder SuperMini) im Griff, eine adressierbare WS2812B-Lichterkette (50 LEDs, 10 cm Abstand) im Raumschiff.

  Knöpfe:  FEUER  -> Laserkanonen schießen abwechselnd links/rechts (gedrückt halten = Dauerfeuer)
           TURBO  -> Triebwerke lodern 4 Sekunden hell und blau auf
  Beim Einschalten läuft eine kurze Startsequenz (Licht an, Triebwerke zünden).

  ZÄHLMODUS (zum Einrichten): beim Einstecken FEUER gedrückt halten.
    Es leuchtet genau eine LED weiß. FEUER = nächste LED, TURBO = eine zurück.
    Die Nummer steht im Seriellen Monitor (115200 Baud). Damit füllst du unten die Karte LED_MAP aus.

  UPDATE ÜBER WLAN: Trägst du unten WLAN_NAME und WLAN_PASS ein, bucht sich der ESP beim Einschalten
    für ein paar Sekunden ins Heim-WLAN ein und schaut auf GitHub nach, ob es eine neuere Firmware gibt.
    Gibt es eine, lädt er sie (alle LEDs pulsieren dabei blau) und startet neu. Kein WLAN in Reichweite
    (Laternenumzug): nichts passiert, die Lichter laufen sofort. Das allererste Aufspielen geht nur per USB.

  Arduino IDE: Board „ESP32C3 Dev Module“, „USB CDC On Boot: Enabled“.
  Bibliothek: „Adafruit NeoPixel“ (über den Bibliotheksverwalter installieren).
*/
#include <Adafruit_NeoPixel.h>
#ifdef ESP32
#include <WiFi.h>
#include <HTTPClient.h>
#include <HTTPUpdate.h>
#include <WiFiClientSecure.h>
#include <Preferences.h>
#endif

// ------------------------------------------------------------------ WLAN und Update
// Einmal eintragen und per USB hochladen: der ESP merkt sich die Zugangsdaten dauerhaft in seinem Speicher.
// Danach kann hier wieder "" stehen; die fertige Firmware im Repo (firmware/pfeil_licht.bin) enthält deshalb keine Passwörter.
const char* WLAN_NAME = "";          // Name deines WLANs. Leer = gespeicherte Daten verwenden (oder kein WLAN, falls nie eingetragen)
const char* WLAN_PASS = "";          // Passwort. (Diese Datei mit Passwort nicht weitergeben.)
const char* GITHUB_TOKEN = "";       // nur nötig, solange das Repo privat ist: Fine-grained Token mit Lesezugriff auf "Contents"
#ifdef ESP32
String wlanName, wlanPass, githubToken;   // tatsächlich benutzte Werte (aus den Zeilen oben oder aus dem Speicher)
#endif
const int   FIRMWARE_VERSION = 2;    // wird bei jeder neuen Version hochgezählt
const char* UPDATE_URL = "https://raw.githubusercontent.com/TimDangerPowers/Laterne-Pfeil/main/firmware/";   // dort liegen version.txt und pfeil_licht.bin
const uint32_t WLAN_WARTEN_MS = 8000;   // so lange wird aufs WLAN gewartet, dann wird es abgeschaltet

// ------------------------------------------------------------------ Anschlüsse
const int PIN_LEDS  = 4;   // Daten zur Lichterkette (über das JST-Verlängerungskabel)
const int PIN_FEUER = 6;   // Taster gegen GND
const int PIN_TURBO = 7;   // Taster gegen GND

// ------------------------------------------------------------------ Karte der LEDs
// Ein Zeichen pro LED in der Reihenfolge der Kette (LED 0 = am Stecker):
//   K = Kanzel (blau)        I = Innenlicht (warm)      H = Scheinwerfer (weiß)
//   L = Kanone links         R = Kanone rechts
//   F = Flamme links         f = Flamme rechts           - = aus (liegt z. B. im Kabelkanal)
// Mit dem Zählmodus nachsehen, welche LED wo liegt, und die Zeichen hier anpassen.
const char LED_MAP[] =
  "KK"           //  0- 1  unter der Kanzel
  "-L-"          //  2- 4  linker Kabelkanal, Mündung linke Kanone, zurück
  "IF-"          //  5- 7  innen, linke Flamme, zurück
  "II"           //  8- 9  quer durch den Rumpf
  "f-"           // 10-11  rechte Flamme, zurück
  "-R-"          // 12-14  rechter Kabelkanal, Mündung rechte Kanone, zurück
  "I"            // 15     innen
  "HH"           // 16-17  Scheinwerfer
  "--------------------------------";   // 18-49  Rest der Kette (aus)
const int NUM = sizeof(LED_MAP) - 1;

// ------------------------------------------------------------------ Einstellungen
const uint8_t  HELLIGKEIT  = 200;    // 0-255, gesamt
const uint16_t MAX_MA      = 1000;   // Stromgrenze für alle LEDs (Powerbank und Kabel schonen)
const uint16_t TURBO_MS    = 4000;
const uint16_t SCHUSS_MS   = 380;    // Abstand der Schüsse bei Dauerfeuer

Adafruit_NeoPixel strip(NUM, PIN_LEDS, NEO_GRB + NEO_KHZ800);

uint8_t heat[64];                     // Flackern pro LED
uint32_t turboUntil = 0, turboStart = 0;
uint32_t shotStart = 0, nextShot = 0;
bool shotLeft = true, shotActive = false;
uint32_t bootTime;

struct Btn { int pin; bool down; bool pressed; uint32_t t; };
Btn feuer{PIN_FEUER, false, false, 0}, turbo{PIN_TURBO, false, false, 0};

void readBtn(Btn &b) {
  bool d = digitalRead(b.pin) == LOW;
  b.pressed = false;
  if (d != b.down && millis() - b.t > 25) {   // entprellen
    b.t = millis();
    if (d) b.pressed = true;
    b.down = d;
  }
}

static inline uint8_t qadd(int a) { return a > 255 ? 255 : (a < 0 ? 0 : a); }
static inline uint32_t rgb(int r, int g, int b) { return strip.Color(qadd(r), qadd(g), qadd(b)); }

// Feuerfarbe aus „Hitze“ 0..255: Rot -> Orange -> Gelb
uint32_t fireColor(uint8_t h, float turboMix) {
  int r, g, b;
  if (h < 128) { r = h * 2; g = h / 4; b = 0; }
  else { r = 255; g = 32 + (h - 128) * 1.3; b = (h > 220) ? (h - 220) * 2 : 0; }
  // Turbo: Richtung Weiß-Blau überblenden
  r = r * (1 - turboMix) + (120 + h / 3) * turboMix;
  g = g * (1 - turboMix) + (150 + h / 3) * turboMix;
  b = b * (1 - turboMix) + 255 * turboMix;
  return rgb(r, g, b);
}

// Stromgrenze: grob 20 mA pro voll leuchtendem Farbkanal
void limitPower() {
  uint32_t sum = 0;
  for (int i = 0; i < NUM; i++) {
    uint32_t c = strip.getPixelColor(i);
    sum += ((c >> 16) & 255) + ((c >> 8) & 255) + (c & 255);
  }
  uint32_t ma = sum * 20 / 255;
  if (ma > MAX_MA) {
    float k = (float)MAX_MA / ma;
    for (int i = 0; i < NUM; i++) {
      uint32_t c = strip.getPixelColor(i);
      strip.setPixelColor(i, rgb(((c >> 16) & 255) * k, ((c >> 8) & 255) * k, (c & 255) * k));
    }
  }
}

// Indizes einer Zone sammeln (in Kettenreihenfolge)
int zone(char z, int *out) {
  int n = 0;
  for (int i = 0; i < NUM; i++) if (LED_MAP[i] == z) out[n++] = i;
  return n;
}

void countMode() {
  int idx = 0;
  Serial.println("Zählmodus: FEUER = weiter, TURBO = zurück");
  while (true) {
    readBtn(feuer); readBtn(turbo);
    if (feuer.pressed) idx = (idx + 1) % NUM;
    if (turbo.pressed) idx = (idx + NUM - 1) % NUM;
    strip.clear();
    strip.setPixelColor(idx, rgb(180, 180, 180));
    if (idx > 0) strip.setPixelColor(idx - 1, rgb(0, 0, 20));   // Nachbar zur Orientierung
    strip.show();
    static int last = -1;
    if (idx != last) { Serial.printf("LED %d  (Karte: '%c')\n", idx, LED_MAP[idx]); last = idx; }
    delay(10);
  }
}

// ------------------------------------------------------------------ Update über WLAN
#ifdef ESP32
bool wlanOffen = false;
uint32_t wlanBis = 0;

void zugangLaden() {
  Preferences pref;
  pref.begin("pfeil", false);
  if (WLAN_NAME[0]) {                       // neu eingetragen: merken
    pref.putString("ssid", WLAN_NAME);
    pref.putString("pass", WLAN_PASS);
    Serial.println("WLAN: Zugangsdaten gespeichert");
  }
  if (GITHUB_TOKEN[0]) pref.putString("token", GITHUB_TOKEN);
  wlanName = pref.getString("ssid", "");
  wlanPass = pref.getString("pass", "");
  githubToken = pref.getString("token", "");
  pref.end();
}

void wlanStart() {
  zugangLaden();
  if (wlanName.length() == 0) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(wlanName.c_str(), wlanPass.c_str());
  wlanOffen = true;
  wlanBis = millis() + WLAN_WARTEN_MS;
  Serial.printf("WLAN: verbinde mit %s ...\n", wlanName.c_str());
}

void wlanAus() {
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);
  wlanOffen = false;
}

void updateAnzeige(int ms) {   // alle LEDs pulsieren blau, solange geladen wird
  float s = 0.35 + 0.3 * sin(ms / 250.0);
  for (int i = 0; i < NUM; i++) strip.setPixelColor(i, rgb(0, 40 * s, 255 * s));
  strip.show();
}

void updatePruefen() {
  WiFiClientSecure client;
  client.setInsecure();            // kein Zertifikats-Check, reicht für eine Laterne
  HTTPClient http;
  http.setTimeout(4000);
  if (!http.begin(client, String(UPDATE_URL) + "version.txt")) return;
  if (githubToken.length()) http.addHeader("Authorization", "token " + githubToken);
  int code = http.GET();
  int neu = code == 200 ? http.getString().toInt() : -1;
  http.end();
  Serial.printf("Update: Server-Version %d, eigene %d\n", neu, FIRMWARE_VERSION);
  if (neu <= FIRMWARE_VERSION) return;

  Serial.println("Update: lade neue Firmware ...");
  httpUpdate.rebootOnUpdate(true);
  if (githubToken.length()) httpUpdate.setAuthorization("token " + githubToken);
  httpUpdate.onProgress([](int done, int total) { updateAnzeige(millis()); });
  t_httpUpdate_return r = httpUpdate.update(client, String(UPDATE_URL) + "pfeil_licht.bin");
  if (r == HTTP_UPDATE_FAILED) Serial.printf("Update fehlgeschlagen: %s\n", httpUpdate.getLastErrorString().c_str());
  // bei Erfolg startet der ESP neu und kommt hier nicht mehr an
}

void wlanTick() {
  if (!wlanOffen) return;
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("WLAN: verbunden, IP %s\n", WiFi.localIP().toString().c_str());
    updatePruefen();
    wlanAus();
  } else if ((int32_t)(millis() - wlanBis) > 0) {
    Serial.println("WLAN: nicht gefunden, weiter ohne");
    wlanAus();
  }
}
const char* wlanStatusText() {
  if (wlanName.length() == 0) return "kein WLAN eingetragen";
  if (wlanOffen) return "suche WLAN ...";
  return "WLAN-Suche beendet";
}
#else
void wlanStart() {}
void wlanTick() {}
const char* wlanStatusText() { return "kein WLAN (nicht ESP32)"; }
#endif

// alle 5 Sekunden eine Lebenszeichen-Zeile für den Seriellen Monitor
void statusZeile() {
  static uint32_t next = 0;
  if ((int32_t)(millis() - next) < 0) return;
  next = millis() + 5000;
  Serial.printf("Pfeil läuft, Firmware %d, %lu s an, %s\n", FIRMWARE_VERSION, (unsigned long)(millis() / 1000), wlanStatusText());
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.printf("\nPfeil startet, Firmware %d\n", FIRMWARE_VERSION);
  pinMode(PIN_FEUER, INPUT_PULLUP);
  pinMode(PIN_TURBO, INPUT_PULLUP);
  strip.begin();
  strip.setBrightness(HELLIGKEIT);
  strip.clear(); strip.show();
  delay(50);
  if (digitalRead(PIN_FEUER) == LOW) countMode();
  bootTime = millis();
  for (int i = 0; i < NUM; i++) heat[i % 64] = random(60, 160);
  wlanStart();   // läuft im Hintergrund, die Startsequenz beginnt sofort
}

void loop() {
  uint32_t now = millis();
  uint32_t t = now - bootTime;
  readBtn(feuer); readBtn(turbo);
  wlanTick();
  statusZeile();

  // ---------------- Startsequenz: 0-1,2 s Licht an, ab 1,2 s Triebwerke zünden
  float lightUp = constrain(t / 1200.0f, 0.0f, 1.0f);
  float ignite  = constrain((t - 1200.0f) / 1500.0f, 0.0f, 1.0f);
  if (t < 1200) ignite = 0;

  // ---------------- Turbo
  if (turbo.pressed && t > 2700) { turboStart = now; turboUntil = now + TURBO_MS; }
  float turboMix = 0;
  if (now < turboUntil) {
    uint32_t in = now - turboStart, left = turboUntil - now;
    turboMix = min(1.0f, min(in / 300.0f, left / 800.0f));
  }

  // ---------------- Feuer: abwechselnd links/rechts, Dauerfeuer beim Halten
  if (t > 2700 && (feuer.pressed || (feuer.down && now >= nextShot))) {
    shotActive = true; shotStart = now; nextShot = now + SCHUSS_MS; shotLeft = !shotLeft;
  }

  for (int i = 0; i < NUM; i++) {
    char z = LED_MAP[i];
    uint32_t c = 0;
    switch (z) {
      case 'K': {                                   // Kanzel: kühles Blau, leichtes Schimmern
        float s = 0.85 + 0.15 * sin(now / 900.0 + i);
        c = rgb(20 * s * lightUp, 120 * s * lightUp, 255 * s * lightUp);
        break;
      }
      case 'I': {                                   // Innenlicht: warmes Glühen, langsames Atmen
        float s = 0.75 + 0.25 * sin(now / 1600.0 + i * 0.7);
        c = rgb(255 * s * lightUp, 120 * s * lightUp, 30 * s * lightUp);
        break;
      }
      case 'H': c = rgb(230 * lightUp, 230 * lightUp, 210 * lightUp); break;   // Scheinwerfer
      case 'F': case 'f': {                         // Flammen
        uint8_t &h = heat[i % 64];
        int target = 90 + random(0, 140) + turboMix * 60;
        h = (h * 3 + target) / 4;                   // weiches Flackern
        if (random(0, 30) == 0) h = qadd(h + 80);    // Funke
        float k = ignite * (0.8 + 0.4 * turboMix);
        if (ignite < 1 && random(0, 4) == 0) k *= 0.2; // stotternde Zündung
        uint32_t fc = fireColor(h, turboMix);
        c = rgb(((fc >> 16) & 255) * k, ((fc >> 8) & 255) * k, (fc & 255) * k);
        break;
      }
      default: c = 0;
    }
    strip.setPixelColor(i, c);
  }

  // Kanonen: leises Rot im Leerlauf, beim Schuss läuft ein Lichtpuls zur Mündung und blitzt
  static int L[16], R[16];
  static int nl = zone('L', L), nr = zone('R', R);
  for (int side = 0; side < 2; side++) {
    int *ids = side == 0 ? L : R;
    int n = side == 0 ? nl : nr;
    for (int k = 0; k < n; k++) strip.setPixelColor(ids[k], rgb(25 * lightUp, 0, 0));
    if (shotActive && (side == 0) == shotLeft) {
      uint32_t dt = now - shotStart;
      // Hin- und Rückweg liegen beide im Rohr: alle LEDs der Kanone nach Position im Rohr gleich behandeln
      for (int k = 0; k < n; k++) {
        int pos = k < (n + 1) / 2 ? k : n - 1 - k;       // 0 = Fuß, höher = Mündung
        int maxPos = (n + 1) / 2 - 1;
        int tHit = pos * 45;                              // Puls läuft in 45 ms je Stufe nach vorn
        int d = (int)dt - tHit;
        uint32_t c = rgb(25, 0, 0);
        if (d >= 0 && d < 70) c = rgb(255, 30, 20);
        if (pos == maxPos && d >= 40 && d < 110) c = rgb(255, 220, 200);   // Mündungsblitz
        if (pos == maxPos && d >= 110 && d < 300) { int f = 255 - (d - 110); c = rgb(f, f / 6, 0); }
        strip.setPixelColor(ids[k], c);
      }
      if (dt > 320) shotActive = false;
    }
  }
  // Scheinwerfer blitzen beim Schuss kurz mit
  if (shotActive && now - shotStart < 60) {
    for (int i = 0; i < NUM; i++) if (LED_MAP[i] == 'H') strip.setPixelColor(i, rgb(255, 255, 255));
  }

  limitPower();
  strip.show();
  delay(16);   // ca. 60 Bilder pro Sekunde
}
