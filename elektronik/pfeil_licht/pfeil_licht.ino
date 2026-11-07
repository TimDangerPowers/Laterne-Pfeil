/*
  Raumjäger „Pfeil“ – Licht für Tonis Laterne
  ESP32-C3-Zero (oder SuperMini) im Griff, eine adressierbare WS2812B-Lichterkette (50 LEDs, 10 cm Abstand) im Raumschiff.

  Knöpfe:  FEUER  -> Laserkanonen schießen abwechselnd links/rechts (gedrückt halten = Dauerfeuer)
           TURBO  -> kurz: Triebwerke lodern 4 Sekunden hell auf (Turbofarbe)
                     1,5 s halten: Schiff fährt herunter (erst Triebwerke, dann Laser/Scheinwerfer, zuletzt Kanzel)
           im Aus-Zustand irgendein Knopf -> Schiff fährt hoch (Kanzel, dann Licht vorn, dann zünden die Triebwerke langsam)
  Beim Einschalten läuft dieselbe Startsequenz.

  EINSTELLSEITE (Handy oder PC): Der ESP liefert eine Webseite aus, auf der du jede LED zuordnest
    (sie leuchtet dabei zur Kontrolle) und die Farben von Laser, Turbo und Flammen sowie die Helligkeit einstellst.
    Alles wird dauerhaft im ESP gespeichert und überlebt Updates.
      zu Hause:   ESP im Heim-WLAN, Seite unter  http://pfeil.local  (oder die IP aus dem Seriellen Monitor)
      unterwegs:  TURBO beim Einstecken gedrückt halten -> der ESP macht ein eigenes WLAN „Pfeil-Laterne“
                  (Passwort pfeil1234) auf, Handy damit verbinden, Seite unter  http://192.168.4.1

  ZÄHLMODUS (Alternative ohne Handy): beim Einstecken FEUER gedrückt halten.
    Es leuchtet genau eine LED weiß. FEUER = nächste LED, TURBO = eine zurück. Nummer im Seriellen Monitor (115200 Baud).

  UPDATE ÜBER WLAN: Trägst du unten WLAN_NAME und WLAN_PASS ein, bucht sich der ESP beim Einschalten
    ins Heim-WLAN ein und schaut auf GitHub nach, ob es eine neuere Firmware gibt.
    Gibt es eine, lädt er sie (alle LEDs pulsieren dabei blau) und startet neu. Kein WLAN in Reichweite
    (Laternenumzug): nichts passiert, die Lichter laufen sofort. Das allererste Aufspielen geht nur per USB.

  Arduino IDE: Board „ESP32C3 Dev Module“, „USB CDC On Boot: Enabled“,
               Partition Scheme „Minimal SPIFFS (1.9MB APP with OTA)“ (einmal per USB nötig, ab Firmware 3.0).
  Bibliothek: „Adafruit NeoPixel“ (über den Bibliotheksverwalter installieren).
*/
#include <Adafruit_NeoPixel.h>
#ifdef ESP32
#include <WiFi.h>
#include <HTTPClient.h>
#include <HTTPUpdate.h>
#include <WiFiClientSecure.h>
#include <Preferences.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#endif

// ------------------------------------------------------------------ WLAN und Update
// Einmal eintragen und per USB hochladen: der ESP merkt sich die Zugangsdaten dauerhaft in seinem Speicher.
// Danach kann hier wieder "" stehen; die fertige Firmware im Repo (firmware/pfeil_licht.bin) enthält deshalb keine Passwörter.
const char* WLAN_NAME = "";          // Name deines WLANs. Leer = gespeicherte Daten verwenden (oder kein WLAN, falls nie eingetragen)
const char* WLAN_PASS = "";          // Passwort. (Diese Datei mit Passwort nicht weitergeben.)
const char* GITHUB_TOKEN = "";       // nur nötig, solange das Repo privat ist: Fine-grained Token mit Lesezugriff auf "Contents"
const char* FIRMWARE_VERSION = "3.3";   // z. B. "2.1": wird bei jeder neuen Version hochgezählt, muss zu firmware/version.txt passen
const char* UPDATE_URL = "https://raw.githubusercontent.com/TimDangerPowers/Laterne-Pfeil/main/firmware/";   // dort liegen version.txt und pfeil_licht.bin
const uint32_t WLAN_WARTEN_MS = 20000;  // so lange wird je Versuch aufs WLAN gewartet
const uint32_t WLAN_PAUSE_MS  = 120000; // danach Pause, dann neuer Versuch im Hintergrund
const char* AP_NAME = "Pfeil-Laterne";  // eigenes WLAN unterwegs (TURBO beim Einstecken halten)
const char* AP_PASS = "pfeil1234";
const char* HOSTNAME = "pfeil";         // -> http://pfeil.local

// ------------------------------------------------------------------ Anschlüsse
const int PIN_LEDS  = 4;   // Daten zur Lichterkette (über das JST-Verlängerungskabel)
const int PIN_FEUER = 6;   // Taster gegen GND
const int PIN_TURBO = 7;   // Taster gegen GND

// ------------------------------------------------------------------ Karte der LEDs (Voreinstellung)
// Ein Zeichen pro LED in der Reihenfolge der Kette (LED 0 = am Stecker):
//   K = Kanzel (blau)        I = Innenlicht (warm)      H = Scheinwerfer (weiß)
//   L = Kanone links         R = Kanone rechts
//   F = Flamme links         f = Flamme rechts           - = aus (liegt z. B. im Kabelkanal)
// Die tatsächliche Karte stellst du auf der Einstellseite ein; diese hier gilt nur beim allerersten Start.
const char LED_MAP_DEFAULT[] =
  "KK"           //  0- 1  unter der Kanzel
  "-L-"          //  2- 4  linker Kabelkanal, Mündung linke Kanone, zurück
  "IF-"          //  5- 7  innen, linke Flamme, zurück
  "II"           //  8- 9  quer durch den Rumpf
  "f-"           // 10-11  rechte Flamme, zurück
  "-R-"          // 12-14  rechter Kabelkanal, Mündung rechte Kanone, zurück
  "I"            // 15     innen
  "HH"           // 16-17  Scheinwerfer
  "--------------------------------";   // 18-49  Rest der Kette (aus)
const int NUM = sizeof(LED_MAP_DEFAULT) - 1;
const char ZONEN[] = "KIHLRFf-";       // erlaubte Zeichen

// ------------------------------------------------------------------ Einstellungen (änderbar über die Webseite)
struct Einstellungen {
  char     map[NUM + 1];
  uint8_t  hell;          // Helligkeit 0-255
  uint32_t laser;         // Laserfarbe
  uint32_t turbo;         // Turbofarbe (Flammen beim Turbo)
  uint32_t flamme1;       // Flamme: Grundfarbe (kühler Teil)
  uint32_t flamme2;       // Flamme: Spitzenfarbe (heißester Teil)
  uint32_t kanzel;        // Kanzelfarbe
  uint32_t innen;         // Innenlicht
} E;

void standardEinstellungen() {
  strncpy(E.map, LED_MAP_DEFAULT, NUM); E.map[NUM] = 0;
  E.hell = 200;
  E.laser   = 0xFF1E14;   // Rot
  E.turbo   = 0x3C96FF;   // Blau
  E.flamme1 = 0xFF0A00;   // Rot (die grüne LED ist viel heller als die rote, darum wenig Grün)
  E.flamme2 = 0xFF5A00;   // Orange
  E.kanzel  = 0x1478FF;
  E.innen   = 0xFF781E;
}

const uint16_t MAX_MA      = 1000;   // Stromgrenze für alle LEDs (Powerbank und Kabel schonen)
const uint16_t TURBO_MS    = 4000;
const uint16_t SCHUSS_MS   = 380;    // Abstand der Schüsse bei Dauerfeuer

Adafruit_NeoPixel strip(NUM, PIN_LEDS, NEO_GRB + NEO_KHZ800);

uint8_t heat[64];                     // Flackern pro LED
uint32_t turboUntil = 0, turboStart = 0;
uint32_t shotStart = 0, nextShot = 0;
bool shotLeft = true, shotActive = false;
uint32_t bootTime;
int testLed = -1;                     // von der Webseite: diese LED weiß zeigen
uint32_t testBis = 0;
bool zonenNeu = true;                 // Kanonen-Zonen neu einsammeln
bool turboWeb = false;                // Turbo von der Webseite ausgelöst

struct Btn { int pin; bool down; bool pressed; bool released; uint32_t t; uint32_t heldMs; };
Btn feuer{PIN_FEUER, false, false, false, 0, 0}, turbo{PIN_TURBO, false, false, false, 0, 0};

void readBtn(Btn &b) {
  bool d = digitalRead(b.pin) == LOW;
  b.pressed = false; b.released = false;
  if (d != b.down && millis() - b.t > 25) {   // entprellen
    if (d) b.pressed = true; else { b.released = true; b.heldMs = millis() - b.t; }
    b.t = millis();
    b.down = d;
  }
}

// ------------------------------------------------------------------ An und Aus (Sequenzen)
// TURBO lange halten (1,5 s): Schiff fährt herunter – erst Triebwerke, dann Laser und Scheinwerfer, zuletzt Kanzel.
// Im ausgeschalteten Zustand irgendeinen Knopf drücken: hochfahren in umgekehrter Reihenfolge, Triebwerke zünden langsam.
enum Zustand { AN, FAEHRT_RUNTER, AUS, FAEHRT_HOCH };
Zustand zustand = FAEHRT_HOCH;
// Prototypen ausdrücklich hier: die Arduino-IDE erzeugt ihre eigenen sonst vor diesen Typdefinitionen
void readBtn(Btn &b);
void zustandSetzen(Zustand z);
uint32_t zustandSeit = 0;
const uint32_t HALTEN_AUS_MS = 1500;
float lvlKanzel = 0, lvlFront = 0, lvlTriebwerk = 0;   // 0..1 je Gruppe (Front = Innen, Scheinwerfer, Kanonen)

static inline float rampe(uint32_t t, uint32_t von, uint32_t bis) {   // 0 vor „von“, 1 nach „bis“
  if (t <= von) return 0;
  if (t >= bis) return 1;
  return (float)(t - von) / (bis - von);
}

void zustandSetzen(Zustand z) { zustand = z; zustandSeit = millis(); }

// berechnet die Pegel der drei Gruppen aus dem Zustand
void sequenzTick(uint32_t now) {
  // zustandSeit kann im selben Durchlauf gesetzt worden sein und 1 ms jünger als now sein: nicht unter 0 laufen lassen
  int32_t dt = (int32_t)(now - zustandSeit);
  uint32_t t = dt < 0 ? 0 : (uint32_t)dt;
  switch (zustand) {
    case FAEHRT_HOCH:                                   // Kanzel 0-1,5 s, Front 1-2,5 s, Triebwerke 2,5-6 s
      lvlKanzel = rampe(t, 0, 1500); lvlFront = rampe(t, 1000, 2500); lvlTriebwerk = rampe(t, 2500, 6000);
      if (t >= 6000) zustandSetzen(AN);
      break;
    case AN: lvlKanzel = lvlFront = lvlTriebwerk = 1; break;
    case FAEHRT_RUNTER:                                 // Triebwerke 0-2,5 s, Front 2,5-4 s, Kanzel 4-5,5 s
      lvlTriebwerk = 1 - rampe(t, 0, 2500); lvlFront = 1 - rampe(t, 2500, 4000); lvlKanzel = 1 - rampe(t, 4000, 5500);
      if (t >= 5500) zustandSetzen(AUS);
      break;
    case AUS: lvlKanzel = lvlFront = lvlTriebwerk = 0; break;
  }
}

static inline uint8_t qadd(int a) { return a > 255 ? 255 : (a < 0 ? 0 : a); }
static inline uint32_t rgb(int r, int g, int b) { return strip.Color(qadd(r), qadd(g), qadd(b)); }
static inline int R(uint32_t c) { return (c >> 16) & 255; }
static inline int G(uint32_t c) { return (c >> 8) & 255; }
static inline int B(uint32_t c) { return c & 255; }
// Farbe c mit Faktor k (0..1) dimmen
static inline uint32_t dim(uint32_t c, float k) { return rgb(R(c) * k, G(c) * k, B(c) * k); }
// zwischen zwei Farben überblenden, m = 0..1
static inline uint32_t mix(uint32_t a, uint32_t b, float m) {
  return rgb(R(a) * (1 - m) + R(b) * m, G(a) * (1 - m) + G(b) * m, B(a) * (1 - m) + B(b) * m);
}

// Feuerfarbe aus „Hitze“ 0..255: Grundfarbe -> Spitzenfarbe, beim Turbo Richtung Turbofarbe
uint32_t fireColor(uint8_t h, float turboMix) {
  float m = h / 255.0f;
  uint32_t c = mix(dim(E.flamme1, 0.2f + 0.8f * m), E.flamme2, m * m);
  if (h > 245) c = mix(c, 0xFFFFC8, (h - 245) / 10.0f * 0.35f);  // Funke: kurz heller
  if (turboMix > 0) c = mix(c, mix(E.turbo, 0xFFFFFF, m * 0.5f), turboMix);
  return c;
}

// Stromgrenze: grob 20 mA pro voll leuchtendem Farbkanal
void limitPower() {
  uint32_t sum = 0;
  for (int i = 0; i < NUM; i++) {
    uint32_t c = strip.getPixelColor(i);
    sum += R(c) + G(c) + B(c);
  }
  uint32_t ma = sum * 20 / 255;
  if (ma > MAX_MA) {
    float k = (float)MAX_MA / ma;
    for (int i = 0; i < NUM; i++) strip.setPixelColor(i, dim(strip.getPixelColor(i), k));
  }
}

// Indizes einer Zone sammeln (in Kettenreihenfolge)
int zone(char z, int *out) {
  int n = 0;
  for (int i = 0; i < NUM; i++) if (E.map[i] == z) out[n++] = i;
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
    if (idx != last) { Serial.printf("LED %d  (Karte: '%c')\n", idx, E.map[idx]); last = idx; }
    delay(10);
  }
}

// ------------------------------------------------------------------ Speichern, WLAN, Update, Webseite
#ifdef ESP32
String wlanName, wlanPass, githubToken;   // tatsächlich benutzte Werte (aus den Zeilen oben oder aus dem Speicher)
bool wlanOffen = false;                   // Verbindungsversuch läuft
bool wlanAktiv = false;                   // verbunden oder eigenes WLAN offen -> Webseite erreichbar
bool apModus = false;
uint32_t wlanBis = 0;
String wlanErgebnis = "";                 // Ergebnis der WLAN-Suche für die Statuszeile
WebServer server(80);

void einstellungenLaden() {
  Preferences p;
  p.begin("pfeil", true);
  standardEinstellungen();
  String m = p.getString("map", "");
  if (m.length() == NUM) strncpy(E.map, m.c_str(), NUM);
  E.hell    = p.getUChar("hell", E.hell);
  E.laser   = p.getUInt("laser", E.laser);
  E.turbo   = p.getUInt("turbo", E.turbo);
  E.flamme1 = p.getUInt("fl1", E.flamme1);
  E.flamme2 = p.getUInt("fl2", E.flamme2);
  E.kanzel  = p.getUInt("kanzel", E.kanzel);
  E.innen   = p.getUInt("innen", E.innen);
  p.end();
}

void einstellungenSpeichern() {
  Preferences p;
  p.begin("pfeil", false);
  p.putString("map", E.map);
  p.putUChar("hell", E.hell);
  p.putUInt("laser", E.laser);
  p.putUInt("turbo", E.turbo);
  p.putUInt("fl1", E.flamme1);
  p.putUInt("fl2", E.flamme2);
  p.putUInt("kanzel", E.kanzel);
  p.putUInt("innen", E.innen);
  p.end();
  Serial.println("Einstellungen gespeichert");
}

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

// ---------- Webseite (liegt komplett im Programmspeicher)
const char SEITE[] PROGMEM = R"HTML(<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Pfeil</title>
<style>
body{margin:0;background:#0b0d12;color:#e8e8ee;font:16px system-ui,sans-serif}
header{padding:14px 16px;background:#141824;font-weight:700;font-size:18px;display:flex;justify-content:space-between;align-items:center}
header small{font-weight:400;color:#8a90a8}
section{padding:14px 16px;border-bottom:1px solid #1e2330}
h2{margin:0 0 8px;font-size:14px;color:#8a90a8;text-transform:uppercase;letter-spacing:.06em}
.grid{display:grid;grid-template-columns:repeat(10,1fr);gap:6px}
.led{aspect-ratio:1;border-radius:8px;border:2px solid #2a3040;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;user-select:none}
.led.sel{outline:3px solid #fff;outline-offset:-1px}
.zonen{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.z{padding:10px 14px;border-radius:10px;border:2px solid #2a3040;font-weight:700}
.z.sel{border-color:#fff}
.zeile{display:flex;align-items:center;justify-content:space-between;padding:8px 0}
input[type=color]{width:56px;height:36px;border:none;background:none}
input[type=range]{width:60%}
button{background:#2b6cff;color:#fff;border:none;border-radius:10px;padding:12px 18px;font-size:16px;font-weight:700}
button.sek{background:#2a3040}
.btns{display:flex;gap:10px;flex-wrap:wrap}
#msg{color:#8a90a8;font-size:14px;margin-top:8px;min-height:18px}
</style></head><body>
<header>Pfeil – Einstellungen <small id="ver"></small></header>
<section><h2>LEDs zuordnen</h2>
<div style="color:#8a90a8;font-size:14px;margin-bottom:8px">LED antippen (sie leuchtet dann weiß im Schiff), danach unten sagen, was sie ist.</div>
<div class="grid" id="grid"></div>
<div class="zonen" id="zonen"></div>
</section>
<section><h2>Farben</h2>
<div class="zeile"><span>Laser</span><input type="color" id="laser"></div>
<div class="zeile"><span>Turbo</span><input type="color" id="turbo"></div>
<div class="zeile"><span>Flamme Grundfarbe</span><input type="color" id="fl1"></div>
<div class="zeile"><span>Flamme Spitze</span><input type="color" id="fl2"></div>
<div class="zeile"><span>Kanzel</span><input type="color" id="kanzel"></div>
<div class="zeile"><span>Innenlicht</span><input type="color" id="innen"></div>
<div class="zeile"><span>Helligkeit</span><input type="range" id="hell" min="20" max="255"></div>
</section>
<section><h2>Testen</h2>
<div class="btns"><button class="sek" onclick="api('fire')">Feuer</button><button class="sek" onclick="api('turbo')">Turbo</button><button class="sek" onclick="api('power')">An / Aus</button></div>
</section>
<section>
<div class="btns"><button onclick="speichern()">Speichern</button><button class="sek" onclick="laden()">Zurücksetzen</button></div>
<div id="msg"></div>
</section>
<script>
const ZN={K:['Kanzel','#1478ff'],I:['Innen','#ff781e'],H:['Scheinwerfer','#ddd'],L:['Kanone L','#ff3030'],R:['Kanone R','#ff3030'],F:['Flamme L','#ff9900'],f:['Flamme R','#ffc040'],'-':['aus','#444']};
let S=null,sel=-1;
const $=id=>document.getElementById(id);
const hex=n=>'#'+n.toString(16).padStart(6,'0');
function api(p,q){return fetch('/api/'+p+(q?'?'+q:''),{method:'POST'}).then(r=>r.json())}
function zeichnen(){
 const g=$('grid');g.innerHTML='';
 for(let i=0;i<S.map.length;i++){const z=S.map[i];const d=document.createElement('div');d.className='led'+(i==sel?' sel':'');
  d.style.borderColor=ZN[z][1];d.style.color=ZN[z][1];d.textContent=i;d.onclick=()=>{sel=i;api('test','led='+i);zeichnen()};g.appendChild(d)}
 const zs=$('zonen');zs.innerHTML='';
 for(const k in ZN){const b=document.createElement('div');b.className='z'+(sel>=0&&S.map[sel]==k?' sel':'');b.style.color=ZN[k][1];b.textContent=ZN[k][0]+' ('+k+')';
  b.onclick=()=>{if(sel<0){$('msg').textContent='Erst eine LED antippen.';return}S.map=S.map.substring(0,sel)+k+S.map.substring(sel+1);api('map','map='+encodeURIComponent(S.map));sel=Math.min(sel+1,S.map.length-1);api('test','led='+sel);zeichnen()};zs.appendChild(b)}
}
function laden(){fetch('/api/state').then(r=>r.json()).then(s=>{S=s;$('ver').textContent='Firmware '+s.version;
 for(const k of ['laser','turbo','fl1','fl2','kanzel','innen'])$(k).value=hex(s[k]);$('hell').value=s.hell;zeichnen();$('msg').textContent=''})}
for(const k of ['laser','turbo','fl1','fl2','kanzel','innen','hell'])$(k).oninput=()=>{const v=$(k).value;api('set',k+'='+encodeURIComponent(v))};
function speichern(){api('save').then(()=>$('msg').textContent='Gespeichert.')}
laden();
</script></body></html>)HTML";

String stateJson() {
  String j = "{\"version\":\"" + String(FIRMWARE_VERSION) + "\",\"map\":\"" + String(E.map) + "\",\"hell\":" + String(E.hell);
  j += ",\"laser\":" + String(E.laser) + ",\"turbo\":" + String(E.turbo) + ",\"fl1\":" + String(E.flamme1);
  j += ",\"fl2\":" + String(E.flamme2) + ",\"kanzel\":" + String(E.kanzel) + ",\"innen\":" + String(E.innen) + "}";
  return j;
}

uint32_t hexFarbe(String v) {          // "#rrggbb" oder "rrggbb"
  if (v.startsWith("#")) v = v.substring(1);
  return (uint32_t)strtoul(v.c_str(), nullptr, 16) & 0xFFFFFF;
}

void webStart() {
  server.on("/", HTTP_GET, []() { server.send_P(200, "text/html; charset=utf-8", SEITE); });
  server.on("/api/state", HTTP_ANY, []() { server.send(200, "application/json", stateJson()); });
  server.on("/api/test", HTTP_ANY, []() {     // eine LED weiß zeigen
    testLed = server.arg("led").toInt(); testBis = millis() + 4000;
    server.send(200, "application/json", "{\"ok\":1}");
  });
  server.on("/api/map", HTTP_ANY, []() {
    String m = server.arg("map");
    bool ok = m.length() == NUM;
    for (int i = 0; ok && i < NUM; i++) if (!strchr(ZONEN, m[i])) ok = false;
    if (ok) { strncpy(E.map, m.c_str(), NUM); zonenNeu = true; }
    server.send(ok ? 200 : 400, "application/json", ok ? "{\"ok\":1}" : "{\"ok\":0}");
  });
  server.on("/api/set", HTTP_ANY, []() {      // Farben und Helligkeit (sofort sichtbar, noch nicht gespeichert)
    if (server.hasArg("hell"))   { E.hell = constrain(server.arg("hell").toInt(), 20, 255); strip.setBrightness(E.hell); }
    if (server.hasArg("laser"))  E.laser   = hexFarbe(server.arg("laser"));
    if (server.hasArg("turbo"))  E.turbo   = hexFarbe(server.arg("turbo"));
    if (server.hasArg("fl1"))    E.flamme1 = hexFarbe(server.arg("fl1"));
    if (server.hasArg("fl2"))    E.flamme2 = hexFarbe(server.arg("fl2"));
    if (server.hasArg("kanzel")) E.kanzel  = hexFarbe(server.arg("kanzel"));
    if (server.hasArg("innen"))  E.innen   = hexFarbe(server.arg("innen"));
    server.send(200, "application/json", "{\"ok\":1}");
  });
  server.on("/api/fire",  HTTP_ANY, []() { feuer.pressed = true; server.send(200, "application/json", "{\"ok\":1}"); });
  server.on("/api/turbo", HTTP_ANY, []() { turboWeb = true; server.send(200, "application/json", "{\"ok\":1}"); });
  server.on("/api/power", HTTP_ANY, []() {    // An/Aus umschalten
    if (zustand == AUS || zustand == FAEHRT_RUNTER) zustandSetzen(FAEHRT_HOCH); else zustandSetzen(FAEHRT_RUNTER);
    server.send(200, "application/json", "{\"ok\":1}");
  });
  server.on("/api/save",  HTTP_ANY, []() { einstellungenSpeichern(); server.send(200, "application/json", "{\"ok\":1}"); });
  server.onNotFound([]() { server.sendHeader("Location", "/"); server.send(302, "text/plain", ""); });
  server.begin();
  if (MDNS.begin(HOSTNAME)) MDNS.addService("http", "tcp", 80);
  wlanAktiv = true;
}

void apStart() {
  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_NAME, AP_PASS);
  apModus = true;
  wlanErgebnis = "eigenes WLAN '" + String(AP_NAME) + "' offen, Seite: http://192.168.4.1";
  Serial.println(wlanErgebnis);
  webStart();
}

uint32_t wlanNaechster = 0;   // Zeitpunkt des nächsten Verbindungsversuchs
int wlanVersuche = 0;

void wlanVerbinden() {
  WiFi.setHostname(HOSTNAME);
  WiFi.mode(WIFI_STA);
  WiFi.begin(wlanName.c_str(), wlanPass.c_str());
  wlanOffen = true;
  wlanVersuche++;
  wlanBis = millis() + WLAN_WARTEN_MS;
  Serial.printf("WLAN: verbinde mit %s (Versuch %d) ...\n", wlanName.c_str(), wlanVersuche);
}

void wlanStart() {
  zugangLaden();
  if (wlanName.length() == 0) return;
  wlanVerbinden();
}

void wlanPause() {               // Versuch beenden, später nochmal
  WiFi.disconnect();
  wlanOffen = false;
  wlanNaechster = millis() + WLAN_PAUSE_MS;
}

void updateAnzeige(int ms) {   // alle LEDs pulsieren blau, solange geladen wird
  float s = 0.35 + 0.3 * sin(ms / 250.0);
  for (int i = 0; i < NUM; i++) strip.setPixelColor(i, rgb(0, 40 * s, 255 * s));
  strip.show();
}

// "2.1" -> 201, damit sich Versionen vergleichen lassen
int versionsZahl(const String& v) {
  int punkt = v.indexOf('.');
  if (punkt < 0) return v.toInt() * 100;
  return v.substring(0, punkt).toInt() * 100 + v.substring(punkt + 1).toInt();
}

void updatePruefen() {
  WiFiClientSecure client;
  client.setInsecure();            // kein Zertifikats-Check, reicht für eine Laterne
  HTTPClient http;
  http.setTimeout(4000);
  // ?t=... umgeht den Zwischenspeicher von raw.githubusercontent.com (sonst bis zu 5 Minuten alt)
  if (!http.begin(client, String(UPDATE_URL) + "version.txt?t=" + String(millis()))) return;
  if (githubToken.length()) http.addHeader("Authorization", "token " + githubToken);
  int code = http.GET();
  String neu = code == 200 ? http.getString() : String("");
  neu.trim();
  http.end();
  Serial.printf("Update: GitHub-Version %s, eigene %s (HTTP %d)\n", neu.c_str(), FIRMWARE_VERSION, code);
  if (code != 200) { wlanErgebnis += ", GitHub nicht erreichbar (HTTP " + String(code) + ")"; return; }
  wlanErgebnis += ", GitHub-Version " + neu;
  if (versionsZahl(neu) <= versionsZahl(FIRMWARE_VERSION)) return;

  Serial.println("Update: lade neue Firmware ...");
  httpUpdate.rebootOnUpdate(true);
  if (githubToken.length()) httpUpdate.setAuthorization("token " + githubToken);
  httpUpdate.onProgress([](int done, int total) { updateAnzeige(millis()); });
  t_httpUpdate_return r = httpUpdate.update(client, String(UPDATE_URL) + "pfeil_licht.bin?v=" + neu);
  if (r == HTTP_UPDATE_FAILED) {
    Serial.printf("Update fehlgeschlagen: %s\n", httpUpdate.getLastErrorString().c_str());
    wlanErgebnis += ", Update fehlgeschlagen: " + httpUpdate.getLastErrorString();
  }
  // bei Erfolg startet der ESP neu und kommt hier nicht mehr an
}

void wlanTick() {
  if (wlanAktiv) server.handleClient();
  if (!wlanOffen) {
    if (!wlanAktiv && !apModus && wlanName.length() && (int32_t)(millis() - wlanNaechster) > 0) wlanVerbinden();
    return;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("WLAN: verbunden, IP %s\n", WiFi.localIP().toString().c_str());
    wlanErgebnis = "WLAN verbunden, Seite: http://" + WiFi.localIP().toString() + " oder http://pfeil.local";
    updatePruefen();
    wlanOffen = false;
    webStart();                     // WLAN bleibt an, damit die Einstellseite erreichbar ist
  } else if ((int32_t)(millis() - wlanBis) > 0) {
    wl_status_t st = WiFi.status();
    wlanErgebnis = st == WL_NO_SSID_AVAIL ? "WLAN '" + wlanName + "' nicht gefunden (nur 2,4 GHz möglich)"
                 : st == WL_CONNECT_FAILED ? "WLAN-Verbindung abgelehnt (Passwort?)"
                 : "WLAN nicht verbunden (Status " + String((int)st) + ")";
    wlanErgebnis += ", neuer Versuch in " + String(WLAN_PAUSE_MS / 1000) + " s";
    Serial.println("WLAN: " + wlanErgebnis);
    wlanPause();
  }
}

const char* wlanStatusText() {
  if (apModus) return wlanErgebnis.c_str();
  if (wlanName.length() == 0) return "kein WLAN eingetragen";
  if (wlanOffen) return "suche WLAN ...";
  return wlanErgebnis.c_str();
}
#else
void einstellungenLaden() { standardEinstellungen(); }
void wlanStart() {}
void wlanTick() {}
void apStart() {}
const char* wlanStatusText() { return "kein WLAN (nicht ESP32)"; }
#endif

// alle 5 Sekunden eine Lebenszeichen-Zeile für den Seriellen Monitor
void statusZeile() {
  static uint32_t next = 0;
  if ((int32_t)(millis() - next) < 0) return;
  next = millis() + 5000;
  Serial.printf("Pfeil läuft, Firmware %s, %lu s an, %s\n", FIRMWARE_VERSION, (unsigned long)(millis() / 1000), wlanStatusText());
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.printf("\nPfeil startet, Firmware %s\n", FIRMWARE_VERSION);
  pinMode(PIN_FEUER, INPUT_PULLUP);
  pinMode(PIN_TURBO, INPUT_PULLUP);
  einstellungenLaden();
  strip.begin();
  strip.setBrightness(E.hell);
  strip.clear(); strip.show();
  delay(50);
  if (digitalRead(PIN_FEUER) == LOW) countMode();
  bootTime = millis();
  zustandSetzen(FAEHRT_HOCH);
  for (int i = 0; i < NUM; i++) heat[i % 64] = random(60, 160);
  if (digitalRead(PIN_TURBO) == LOW) apStart();   // TURBO beim Einstecken: eigenes WLAN für die Einstellseite
  else wlanStart();                               // sonst Heim-WLAN im Hintergrund, die Startsequenz beginnt sofort
}

void loop() {
  uint32_t now = millis();
  readBtn(feuer); readBtn(turbo);
  wlanTick();
  statusZeile();

  // ---------------- An/Aus: TURBO lange halten = herunterfahren, im Aus-Zustand ein Knopf = hochfahren
  if (zustand == AUS && (feuer.pressed || turbo.pressed)) { zustandSetzen(FAEHRT_HOCH); feuer.pressed = turbo.pressed = false; }
  else if ((zustand == AN || zustand == FAEHRT_HOCH) && turbo.down && now - turbo.t >= HALTEN_AUS_MS) { zustandSetzen(FAEHRT_RUNTER); turboUntil = 0; }
  sequenzTick(now);
  bool bereit = zustand == AN;
  float lightUp = lvlFront;       // Innen, Scheinwerfer, Kanonen
  float ignite  = lvlTriebwerk;   // Triebwerke
  float kanzelUp = lvlKanzel;

  // ---------------- Turbo: kurzer Druck (Loslassen vor 1,5 s) oder Knopf auf der Webseite
  bool turboAusloesen = (turbo.released && turbo.heldMs < HALTEN_AUS_MS) || turboWeb;
  turboWeb = false;
  if (turboAusloesen && bereit) { turboStart = now; turboUntil = now + TURBO_MS; }
  float turboMix = 0;
  if (now < turboUntil) {
    uint32_t in = now - turboStart, left = turboUntil - now;
    turboMix = min(1.0f, min(in / 300.0f, left / 800.0f));
  }

  // ---------------- Feuer: abwechselnd links/rechts, Dauerfeuer beim Halten
  if (bereit && (feuer.pressed || (feuer.down && now >= nextShot))) {
    shotActive = true; shotStart = now; nextShot = now + SCHUSS_MS; shotLeft = !shotLeft;
  }

  for (int i = 0; i < NUM; i++) {
    char z = E.map[i];
    uint32_t c = 0;
    switch (z) {
      case 'K': {                                   // Kanzel: leichtes Schimmern
        float s = (0.85 + 0.15 * sin(now / 900.0 + i)) * kanzelUp;
        c = dim(E.kanzel, s);
        break;
      }
      case 'I': {                                   // Innenlicht: langsames Atmen
        float s = (0.75 + 0.25 * sin(now / 1600.0 + i * 0.7)) * lightUp;
        c = dim(E.innen, s);
        break;
      }
      case 'H': c = rgb(230 * lightUp, 230 * lightUp, 210 * lightUp); break;   // Scheinwerfer
      case 'F': case 'f': {                         // Flammen
        uint8_t &h = heat[i % 64];
        int target = 90 + random(0, 140) + turboMix * 60;
        h = (h * 3 + target) / 4;                   // weiches Flackern
        if (random(0, 30) == 0) h = qadd(h + 80);    // Funke
        float k = ignite * (0.8 + 0.4 * turboMix);
        if (zustand == FAEHRT_HOCH && ignite < 1 && random(0, 4) == 0) k *= 0.2; // stotternde Zündung
        c = dim(fireColor(h, turboMix), k);
        break;
      }
      default: c = 0;
    }
    strip.setPixelColor(i, c);
  }

  // Kanonen: leises Glimmen im Leerlauf, beim Schuss läuft ein Lichtpuls zur Mündung und blitzt
  static int L[16], R_[16];
  static int nl = 0, nr = 0;
  if (zonenNeu) { nl = zone('L', L); nr = zone('R', R_); zonenNeu = false; }
  for (int side = 0; side < 2; side++) {
    int *ids = side == 0 ? L : R_;
    int n = side == 0 ? nl : nr;
    for (int k = 0; k < n; k++) strip.setPixelColor(ids[k], dim(E.laser, 0.1f * lightUp));
    if (shotActive && (side == 0) == shotLeft) {
      uint32_t dt = now - shotStart;
      // Hin- und Rückweg liegen beide im Rohr: alle LEDs der Kanone nach Position im Rohr gleich behandeln
      for (int k = 0; k < n; k++) {
        int pos = k < (n + 1) / 2 ? k : n - 1 - k;       // 0 = Fuß, höher = Mündung
        int maxPos = (n + 1) / 2 - 1;
        int tHit = pos * 45;                              // Puls läuft in 45 ms je Stufe nach vorn
        int d = (int)dt - tHit;
        uint32_t c = dim(E.laser, 0.1f);
        if (d >= 0 && d < 70) c = E.laser;
        if (pos == maxPos && d >= 40 && d < 110) c = mix(E.laser, 0xFFFFFF, 0.8f);   // Mündungsblitz
        if (pos == maxPos && d >= 110 && d < 300) c = dim(E.laser, (300 - d) / 190.0f);
        strip.setPixelColor(ids[k], c);
      }
      if (dt > 320) shotActive = false;
    }
  }
  // Scheinwerfer blitzen beim Schuss kurz mit
  if (shotActive && now - shotStart < 60) {
    for (int i = 0; i < NUM; i++) if (E.map[i] == 'H') strip.setPixelColor(i, rgb(255, 255, 255));
  }

  // Von der Webseite angetippte LED weiß zeigen
  if (testLed >= 0 && testLed < NUM) {
    if (now < testBis) strip.setPixelColor(testLed, rgb(255, 255, 255));
    else testLed = -1;
  }

  limitPower();
  strip.show();
  delay(16);
}
