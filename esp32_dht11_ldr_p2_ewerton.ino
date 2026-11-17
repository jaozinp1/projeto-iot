/*
 * ESP32 + DHT11 + sensor de luminosidade (digital) com envio para a nuvem/servidor
 *
 * A cada 10 s lê os sensores e envia um payload JSON por HTTP POST (REST)
 * para o servidor Flask (servidor.py), que grava no MongoDB.
 *
 * Exemplo de payload:
 *   {"dispositivo":"esp32-01","temperatura":25.3,"umidade":61,"luminosidade":"claro"}
 *
 * Biblioteca necessária: "DHT sensor library" (Adafruit).
 * WiFi.h e HTTPClient.h já vêm com o pacote do ESP32.
 *
 * Ligações:
 *   DHT11:       VCC -> 3V3 | GND -> GND | DATA -> GPIO 4 (D4)
 *   Módulo LDR:  VCC -> 3V3 | GND -> GND | DO   -> GPIO 22 (D22)
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>

// ======== PREENCHA AQUI ========
const char* WIFI_SSID  = "BDAG";       // rede 2,4 GHz (o ESP32 não usa 5 GHz)
const char* WIFI_SENHA = "bdag2018";
// IP do computador que roda o servidor.py (veja com o comando ipconfig)
const char* URL_SERVIDOR = "http://10.64.67.164:5000/api/leituras";
const char* ID_DISPOSITIVO = "esp32-01";
// ===============================

#define PINO_DHT 22
#define TIPO_DHT DHT11
#define PINO_LDR 4
#define NIVEL_COM_LUZ LOW      // se aparecer invertido, troque por HIGH

const unsigned long INTERVALO_MS = 10000;   // envio a cada 10 s

DHT dht(PINO_DHT, TIPO_DHT);
unsigned long ultimoEnvio = 0;

void conectarWifi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.print("Conectando ao Wi-Fi ");
  Serial.print(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_SENHA);

  unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < 15000) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print(" conectado. IP do ESP32: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println(" falhou (confira nome/senha e se a rede é 2,4 GHz)");
  }
}

void setup() {
  Serial.begin(115200);
  dht.begin();
  pinMode(PINO_LDR, INPUT);
  conectarWifi();
}

void loop() {
  if (millis() - ultimoEnvio < INTERVALO_MS) return;
  ultimoEnvio = millis();

  // ---- Leitura dos sensores ----
  float umidade = dht.readHumidity();
  float temperatura = dht.readTemperature();   // Celsius
  bool dhtOk = !isnan(umidade) && !isnan(temperatura);
  bool claro = (digitalRead(PINO_LDR) == NIVEL_COM_LUZ);

  if (!dhtOk) Serial.println("Falha ao ler o DHT11 (enviando temperatura/umidade como null)");

  // ---- Montagem do JSON ----
  String json = "{\"dispositivo\":\"";
  json += ID_DISPOSITIVO;
  json += "\",\"temperatura\":";
  json += dhtOk ? String(temperatura, 1) : "null";
  json += ",\"umidade\":";
  json += dhtOk ? String(umidade, 0) : "null";
  json += ",\"luminosidade\":\"";
  json += claro ? "claro" : "escuro";
  json += "\"}";

  // ---- Envio por HTTP POST ----
  conectarWifi();
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin(URL_SERVIDOR);
  http.setTimeout(5000);
  http.addHeader("Content-Type", "application/json");
  int codigo = http.POST(json);

  Serial.print("Enviado: ");
  Serial.print(json);
  Serial.print(" -> ");
  if (codigo > 0) {
    Serial.print("HTTP ");
    Serial.println(codigo);              // 201 = gravado com sucesso
  } else {
    Serial.print("erro: ");
    Serial.println(http.errorToString(codigo));   // servidor fora do ar, IP errado ou firewall
  }
  http.end();
}
