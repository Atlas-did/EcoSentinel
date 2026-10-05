// protocol.h — serial line protocol (reply helpers + command routing).
//
// One JSON object per line, `\n`-terminated. This is the single public contract
// between the firmware and the edge host: reply field names here must stay
// stable. `handleCommand` parses the line and dispatches to the actuator /
// sensor primitives; it never writes pins directly.
#pragma once

#include "config.h"
#include "state.h"
#include "sensors.h"
#include "actuators.h"

static void replyOk(const char* what) {
  Serial.print("{\"ok\":true,\"msg\":\"");
  Serial.print(what);
  Serial.println("\"}");
}

static void replyError(const char* what) {
  Serial.print("{\"ok\":false,\"error\":\"");
  Serial.print(what);
  Serial.println("\"}");
}

static void jsonPrintFloatOrNull(const char* key, float value, int decimals) {
  Serial.print("\"");
  Serial.print(key);
  Serial.print("\":");
  if (isnan(value)) {
    Serial.print("null");
  } else {
    Serial.print(value, decimals);
  }
}

static void replySensorsJson() {
  // Always emit a JSON object.
  // Even if DHT fails (NaN), we still want other sensors (lux/power/relays) to flow to the PC.
  bool dhtOk = !(isnan(sensors.temperatureC) || isnan(sensors.humidityPct));

  Serial.print("{");
  jsonPrintFloatOrNull("temperature", sensors.temperatureC, 2);
  Serial.print(",");
  jsonPrintFloatOrNull("humidity", sensors.humidityPct, 2);
  Serial.print(",");
  jsonPrintFloatOrNull("illuminance", sensors.illuminanceLux, 1);

  if (!dhtOk) {
    Serial.print(",\"errors\":[\"DHT_NAN\"]");
  }

  if (sensors.sgpOk) {
    Serial.print(",\"tvoc\":");
    Serial.print(sensors.tvoc);
    Serial.print(",\"eco2\":");
    Serial.print(sensors.eco2);
  }

  if (sensors.inaOk) {
    Serial.print(",\"bus_v\":");
    Serial.print(sensors.busV, 3);
    Serial.print(",\"current_ma\":");
    Serial.print(sensors.currentmA, 1);
    Serial.print(",\"pwr_mw\":");
    Serial.print(sensors.powermW, 1);
  }

  if (sensors.solarInaOk) {
    Serial.print(",\"solar_bus_v\":");
    Serial.print(sensors.solarBusV, 3);
    Serial.print(",\"solar_current_ma\":");
    Serial.print(sensors.solarCurrentmA, 1);
    Serial.print(",\"solar_pwr_mw\":");
    Serial.print(sensors.solarPowermW, 1);
  }

  Serial.print(",\"relays\":[");
  for (int i = 0; i < 4; i++) {
    Serial.print(relayState[i] ? 1 : 0);
    if (i != 3) Serial.print(',');
  }
  Serial.print("]");

  Serial.print(",\"curtain_steps\":");
  Serial.print(curtainPositionSteps);

  Serial.println("}");
}

static void replyStateJson() {
  Serial.print("{\"ok\":true,\"type\":\"state\"");
  Serial.print(",\"protocol_version\":");
  Serial.print(PROTOCOL_VERSION);
  Serial.print(",\"uptime_ms\":");
  Serial.print(millis());
  Serial.print(",\"boot_count\":");
  Serial.print(bootCount);
  Serial.print(",\"i2c_recover_count\":");
  Serial.print(i2cRecoverCount);

  Serial.print(",\"bh1750_ok\":");
  Serial.print(bh1750Ok ? "true" : "false");

  #if HAVE_INA219
  Serial.print(",\"ina219_ok\":");
  Serial.print(ina219Ok ? "true" : "false");
  Serial.print(",\"ina219_solar_ok\":");
  Serial.print(ina219SolarOk ? "true" : "false");
  #endif

  #if HAVE_SGP30
  Serial.print(",\"sgp30_present\":");
  Serial.print("true");
  #else
  Serial.print(",\"sgp30_present\":");
  Serial.print("false");
  #endif

  #if HAVE_ESP_SYSTEM
  Serial.print(",\"reset_reason\":");
  Serial.print((int)esp_reset_reason());
  #endif

  Serial.print(",\"last_read_ms\":");
  Serial.print(sensors.lastReadMs);
  Serial.println("}");
}

static void replyPinMapJson() {
  Serial.print("{\"ok\":true,\"type\":\"pinmap\"");

  Serial.print(",\"i2c_sda\":"); Serial.print(PIN_I2C_SDA);
  Serial.print(",\"i2c_scl\":"); Serial.print(PIN_I2C_SCL);
  Serial.print(",\"dht\":"); Serial.print(PIN_DHT);

  Serial.print(",\"relay\":[");
  Serial.print(PIN_RELAY_1); Serial.print(",");
  Serial.print(PIN_RELAY_2); Serial.print(",");
  Serial.print(PIN_RELAY_3); Serial.print(",");
  Serial.print(PIN_RELAY_4); Serial.print("]");

  Serial.print(",\"buzzer\":"); Serial.print(PIN_BUZZER);

  Serial.print(",\"btn\":[");
  Serial.print(PIN_BTN_1); Serial.print(",");
  Serial.print(PIN_BTN_2); Serial.print(",");
  Serial.print(PIN_BTN_3); Serial.print(",");
  Serial.print(PIN_BTN_4); Serial.print("]");

  Serial.print(",\"stepper\":[");
  Serial.print(PIN_STEPPER_IN1); Serial.print(",");
  Serial.print(PIN_STEPPER_IN2); Serial.print(",");
  Serial.print(PIN_STEPPER_IN3); Serial.print(",");
  Serial.print(PIN_STEPPER_IN4); Serial.print("]");

  Serial.print(",\"tft\":{");
  Serial.print("\"miso\":"); Serial.print(PIN_TFT_MISO); Serial.print(",");
  Serial.print("\"mosi\":"); Serial.print(PIN_TFT_MOSI); Serial.print(",");
  Serial.print("\"sclk\":"); Serial.print(PIN_TFT_SCLK); Serial.print(",");
  Serial.print("\"cs\":"); Serial.print(PIN_TFT_CS); Serial.print(",");
  Serial.print("\"dc\":"); Serial.print(PIN_TFT_DC); Serial.print(",");
  Serial.print("\"rst\":"); Serial.print(PIN_TFT_RST); Serial.print(",");
  Serial.print("\"bl\":"); Serial.print(PIN_TFT_BL);
  Serial.print("}");

  Serial.print(",\"ir_tx\":"); Serial.print(PIN_IR_TX);

#ifdef USE_IR
  Serial.print(",\"ir_enabled\":true");
#else
  Serial.print(",\"ir_enabled\":false");
#endif

  // 快速冲突提示：I2C 与按键复用冲突
  bool i2cBtnConflict = (PIN_I2C_SDA == PIN_BTN_1) || (PIN_I2C_SDA == PIN_BTN_2) ||
                        (PIN_I2C_SDA == PIN_BTN_3) || (PIN_I2C_SDA == PIN_BTN_4) ||
                        (PIN_I2C_SCL == PIN_BTN_1) || (PIN_I2C_SCL == PIN_BTN_2) ||
                        (PIN_I2C_SCL == PIN_BTN_3) || (PIN_I2C_SCL == PIN_BTN_4);
  Serial.print(",\"warn_i2c_btn_conflict\":");
  Serial.print(i2cBtnConflict ? "true" : "false");

  Serial.println("}");
}

static void replyI2cScanJson() {
  Serial.print("{\"ok\":true,\"type\":\"i2c_scan\"");
  Serial.print(",\"sda\":"); Serial.print(PIN_I2C_SDA);
  Serial.print(",\"scl\":"); Serial.print(PIN_I2C_SCL);

  Serial.print(",\"devices\":[");
  bool first = true;
  bool hasBh1750 = false;
  bool hasIna219_40 = false;
  bool hasIna219_41 = false;
  bool hasSgp30 = false;

  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    uint8_t err = Wire.endTransmission();
    if (err == 0) {
      if (!first) Serial.print(",");
      Serial.print((int)addr);
      first = false;

      if (addr == BH1750_ADDR_LOW || addr == BH1750_ADDR_HIGH) hasBh1750 = true;
      if (addr == 0x40) hasIna219_40 = true;
      if (addr == 0x41) hasIna219_41 = true;
      if (addr == 0x58) hasSgp30 = true;
    }
  }
  Serial.print("]");

  Serial.print(",\"bh1750_found\":"); Serial.print(hasBh1750 ? "true" : "false");
  Serial.print(",\"ina219_0x40_found\":"); Serial.print(hasIna219_40 ? "true" : "false");
  Serial.print(",\"ina219_0x41_found\":"); Serial.print(hasIna219_41 ? "true" : "false");
  Serial.print(",\"sgp30_0x58_found\":"); Serial.print(hasSgp30 ? "true" : "false");

  Serial.println("}");
}

// -----------------
// 串口协议
// -----------------
// 一行一条命令，以 \n 结尾。
//
// 读取：
// - READ_SENSORS
// - GET_STATE
//
// 自愈（Option B）：
// - I2C_RECOVER
// - RESET
//
// 继电器：
// - RELAY 1 0/1
// - RELAY 2 0/1
// - RELAY 3 0/1
// - RELAY 4 0/1
//
// 蜂鸣器：
// - BUZZER 0/1
//
// 窗帘：
// - CURTAIN OPEN
// - CURTAIN CLOSE
// - CURTAIN STOP
// - CURTAIN CAL <maxSteps>
//
// IR（可选）：
// - IR_NEC <hex> <bits>
//
// 上板验收令牌 —— 供 scripts/firmware_acceptance.py 判定"固件已启动、关键子系统就绪"。
//
// 语义: "selftest":"pass" 只表示 setup() 完整执行完; 具体哪些子系统可用由各布尔字段给出,
// 传感器缺失**不算失败**(由验收脚本用 --require 决定哪些是必须的)。
// 这条令牌解决的是"同伴拿板子后如何自动判定通过", 而不是替人做硬件判断。
static void printSelfTest() {
  Serial.print("{\"selftest\":\"pass\",\"token\":\"ECO_SELFTEST_PASS\"");
  Serial.print(",\"boot\":");         Serial.print(bootCount);
  Serial.print(",\"i2c_recover\":");  Serial.print(i2cRecoverCount);
  Serial.print(",\"have_dht\":");     Serial.print(HAVE_DHT ? "true" : "false");
  Serial.print(",\"have_sgp30\":");   Serial.print(HAVE_SGP30 ? "true" : "false");
  Serial.print(",\"have_tft\":");     Serial.print(HAVE_TFT ? "true" : "false");
  Serial.print(",\"have_touch\":");   Serial.print(HAVE_TOUCH ? "true" : "false");
  Serial.print(",\"have_ina219\":");  Serial.print(HAVE_INA219 ? "true" : "false");
  Serial.print(",\"bh1750\":");       Serial.print(bh1750Ok ? "true" : "false");
  Serial.print(",\"sgp30\":");        Serial.print(sensors.sgpOk ? "true" : "false");
  Serial.print(",\"ina219\":");       Serial.print(sensors.inaOk ? "true" : "false");
  Serial.print(",\"solar_ina219\":"); Serial.print(sensors.solarInaOk ? "true" : "false");
  Serial.print(",\"relay\":true,\"buzzer\":true,\"stepper\":true");
#ifdef ESP_ARDUINO_VERSION_MAJOR
  Serial.print(",\"esp32_core\":\"");
  Serial.print(ESP_ARDUINO_VERSION_MAJOR);
  Serial.print(".");
  Serial.print(ESP_ARDUINO_VERSION_MINOR);
  Serial.print(".");
  Serial.print(ESP_ARDUINO_VERSION_PATCH);
  Serial.print("\"");
#endif
  Serial.println("}");
}

static void handleCommand(String line) {
  line.trim();
  if (line.length() == 0) return;

  if (line == "READ_SENSORS") {
    replySensorsJson();
    return;
  }

  if (line == "GET_STATE") {
    replyStateJson();
    return;
  }

  if (line == "PINMAP") {
    replyPinMapJson();
    return;
  }

  if (line == "I2C_SCAN") {
    replyI2cScanJson();
    return;
  }

  if (line == "I2C_RECOVER") {
    bool ok = i2cRecover();
    if (ok) replyOk("I2C_RECOVER_OK");
    else replyError("I2C_RECOVER_FAILED");
    return;
  }

  if (line == "RESET") {
    replyOk("RESETTING");
    delay(50);
    ESP.restart();
    return;
  }

  if (line.startsWith("RELAY")) {
    int first = line.indexOf(' ');
    int second = line.indexOf(' ', first + 1);
    if (first < 0 || second < 0) {
      replyError("BAD_RELAY_CMD");
      return;
    }

    int relayNum = line.substring(first + 1, second).toInt();
    int state = line.substring(second + 1).toInt();
    setRelay(relayNum, state != 0);
    replyOk("RELAY_SET");
    return;
  }

  if (line.startsWith("BUZZER")) {
    int first = line.indexOf(' ');
    if (first < 0) {
      replyError("BAD_BUZZER_CMD");
      return;
    }
    int state = line.substring(first + 1).toInt();
    setBuzzer(state != 0);
    replyOk("BUZZER_SET");
    return;
  }

  if (line.startsWith("CURTAIN")) {
    if (line.indexOf("OPEN") > 0) {
      curtainTarget = CurtainTarget::Open;
      replyOk("CURTAIN_OPEN");
      return;
    }
    if (line.indexOf("CLOSE") > 0) {
      curtainTarget = CurtainTarget::Close;
      replyOk("CURTAIN_CLOSE");
      return;
    }
    if (line.indexOf("STOP") > 0) {
      curtainTarget = CurtainTarget::Stop;
      stepperDisable();
      replyOk("CURTAIN_STOP");
      return;
    }
    if (line.indexOf("CAL") > 0) {
      int lastSpace = line.lastIndexOf(' ');
      if (lastSpace < 0) {
        replyError("BAD_CURTAIN_CAL");
        return;
      }
      int32_t maxSteps = (int32_t)line.substring(lastSpace + 1).toInt();
      if (maxSteps < 100) {
        replyError("CURTAIN_CAL_TOO_SMALL");
        return;
      }
      curtainMaxSteps = maxSteps;
      if (curtainPositionSteps > curtainMaxSteps) curtainPositionSteps = curtainMaxSteps;
      replyOk("CURTAIN_CAL_OK");
      return;
    }

    replyError("BAD_CURTAIN_CMD");
    return;
  }

#ifdef USE_IR
  if (line.startsWith("IR_NEC")) {
    // 例：IR_NEC 0x20DF10EF 32
    int first = line.indexOf(' ');
    int second = line.indexOf(' ', first + 1);
    if (first < 0 || second < 0) {
      replyError("BAD_IR_CMD");
      return;
    }

    String hexStr = line.substring(first + 1, second);
    hexStr.replace("0x", "");
    uint32_t code = (uint32_t)strtoul(hexStr.c_str(), nullptr, 16);
    uint16_t bits = (uint16_t)line.substring(second + 1).toInt();

    irsend.sendNEC(code, bits);
    replyOk("IR_SENT");
    return;
  }
#endif

  // 诊断 / 验收命令 —— replySensorsJson / replyStateJson / replyPinMapJson / replyI2cScanJson
  // 此前**已实现却无人分发**, 于是 scripts/hardware_autodiag.py 文档里写的
  // GET_STATE / READ_SENSORS / PINMAP / I2C_SCAN 永远收不到应答(只有被动遥测)。
  if (line.startsWith("GET_STATE"))    { replyStateJson();   return; }
  if (line.startsWith("READ_SENSORS")) { replySensorsJson(); return; }
  if (line.startsWith("PINMAP"))       { replyPinMapJson();  return; }
  if (line.startsWith("I2C_SCAN"))     { replyI2cScanJson(); return; }
  if (line.startsWith("SELFTEST"))     { printSelfTest();    return; }

  replyError("UNKNOWN_CMD");
}
