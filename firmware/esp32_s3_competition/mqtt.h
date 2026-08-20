// mqtt.h — optional distributed-access skeleton (PubSubClient).
//
// Compiled out when USE_MQTT is not defined. Publishes the same sensor fields as
// protocol.h to a `<node>/sensors` topic and routes inbound `<node>/cmd` payloads
// through the same `handleCommand` parser, so serial and MQTT share one contract.
#pragma once

#include "config.h"
#include "state.h"
#include "protocol.h"

// ================== MQTT 函数（骨架） ==================
#ifdef USE_MQTT

// ---- 用户配置：请按实际环境修改 ----
// 注意：以下为占位符，请勿在此处提交真实凭据。
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* MQTT_BROKER   = "broker.emqx.io";   // 免费公共 Broker
const int   MQTT_PORT     = 1883;
const char* NODE_ID       = "classroom_demo";   // 本节点唯一标识

String mqttTopicSensors;
String mqttTopicCmd;

WiFiClient   wifiClient;
PubSubClient mqttClient(wifiClient);

static uint32_t lastMqttReconnectMs = 0;

static void setupWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("WiFi connecting");
  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 30) {
    delay(500);
    Serial.print(".");
    retries++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi connect failed, running serial-only mode");
  }
}

static void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String cmd = "";
  for (unsigned int i = 0; i < length; i++) {
    cmd += (char)payload[i];
  }
  Serial.print("MQTT CMD: ");
  Serial.println(cmd);
  handleCommand(cmd);
}

static bool reconnectMQTT() {
  if (WiFi.status() != WL_CONNECTED) return false;

  mqttTopicSensors = String(NODE_ID) + "/sensors";
  mqttTopicCmd     = String(NODE_ID) + "/cmd";

  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);

  String clientId = "esp32-" + String(NODE_ID) + "-" + String(random(0xffff), HEX);
  if (mqttClient.connect(clientId.c_str())) {
    mqttClient.subscribe(mqttTopicCmd.c_str());
    Serial.println("MQTT connected: " + String(MQTT_BROKER));
    return true;
  }
  return false;
}

static void mqttPublishSensors() {
  if (!mqttClient.connected()) return;

  // 复用 replySensorsJson 的字段逻辑，构造 JSON String 后 publish
  String json = "{";

  bool dhtOk = !(isnan(sensors.temperatureC) || isnan(sensors.humidityPct));

  json += "\"temperature\":" + String(isnan(sensors.temperatureC) ? "null" : String(sensors.temperatureC, 2)) + ",";
  json += "\"humidity\":"    + String(isnan(sensors.humidityPct)   ? "null" : String(sensors.humidityPct, 2)) + ",";
  json += "\"illuminance\":" + String(isnan(sensors.illuminanceLux) ? "null" : String(sensors.illuminanceLux, 1));

  if (!dhtOk) {
    json += ",\"errors\":[\"DHT_NAN\"]";
  }
  if (sensors.sgpOk) {
    json += ",\"tvoc\":" + String(sensors.tvoc) + ",\"eco2\":" + String(sensors.eco2);
  }
  if (sensors.inaOk) {
    json += ",\"bus_v\":" + String(sensors.busV, 3);
    json += ",\"current_ma\":" + String(sensors.currentmA, 1);
    json += ",\"pwr_mw\":" + String(sensors.powermW, 1);
  }
  if (sensors.solarInaOk) {
    json += ",\"solar_bus_v\":" + String(sensors.solarBusV, 3);
    json += ",\"solar_current_ma\":" + String(sensors.solarCurrentmA, 1);
    json += ",\"solar_pwr_mw\":" + String(sensors.solarPowermW, 1);
  }
  json += ",\"relays\":[";
  for (int i = 0; i < 4; i++) {
    json += relayState[i] ? "1" : "0";
    if (i != 3) json += ",";
  }
  json += "]";
  json += ",\"curtain_steps\":" + String(curtainPositionSteps);
  json += ",\"node_id\":\"" + String(NODE_ID) + "\"";
  json += ",\"uptime_ms\":" + String(millis());
  json += "}";

  mqttClient.publish(mqttTopicSensors.c_str(), json.c_str());
}

#endif
// ================== /MQTT 函数 ==================
