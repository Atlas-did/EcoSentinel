#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>

#if __has_include(<esp_system.h>)
  #include <esp_system.h>
  #define HAVE_ESP_SYSTEM 1
#else
  #define HAVE_ESP_SYSTEM 0
#endif

#if __has_include(<DHT.h>)
  #include <DHT.h>
  #define HAVE_DHT 1
#else
  #define HAVE_DHT 0
#endif

#if __has_include(<Adafruit_SGP30.h>)
  #include <Adafruit_SGP30.h>
  #define HAVE_SGP30 1
#else
  #define HAVE_SGP30 0
#endif

#if __has_include(<Adafruit_GFX.h>) && __has_include(<Adafruit_ILI9341.h>)
  #include <Adafruit_GFX.h>
  #include <Adafruit_ILI9341.h>
  #define HAVE_TFT 1
#else
  #define HAVE_TFT 0
#endif

#if __has_include(<Adafruit_INA219.h>)
  #include <Adafruit_INA219.h>
  #define HAVE_INA219 1
#else
  #define HAVE_INA219 0
#endif

#if __has_include(<XPT2046_Touchscreen.h>)
  #include <XPT2046_Touchscreen.h>
  #define HAVE_TOUCH 1
#else
  #define HAVE_TOUCH 0
#endif

// IR 发送（可选）：如果你装了 IRremoteESP8266，就取消注释。
// 注意：不同空调品牌码值不同，需要后续采集/配置。
// #define USE_IR
#ifdef USE_IR
#include <IRremoteESP8266.h>
#include <IRsend.h>
#endif

// ================== MQTT 分布式接入（骨架） ==================
// 库依赖：PubSubClient（by Nick O'Leary）
// 如需禁用 MQTT，注释掉下面这行即可编译为纯串口模式
#define USE_MQTT

#ifdef USE_MQTT
#include <WiFi.h>
#include <PubSubClient.h>
#endif

// -----------------
// 引脚分配（ESP32-S3 修正版）
// 说明：避开 22~25(不存在) / 26~32(内部 SPI) / 33~37(常见 Flash/PSRAM 复用)
// -----------------

// I2C
static constexpr int PIN_I2C_SDA = 21;
static constexpr int PIN_I2C_SCL = 38;

// DHT22
static constexpr int PIN_DHT = 18;

// 继电器（4路）
static constexpr int PIN_RELAY_1 = 12;
static constexpr int PIN_RELAY_2 = 13;
static constexpr int PIN_RELAY_3 = 14;
static constexpr int PIN_RELAY_4 = 15;

// 蜂鸣器 & 按键
static constexpr int PIN_BUZZER = 39;
static constexpr int PIN_BTN_1 = 40;
static constexpr int PIN_BTN_2 = 41;
static constexpr int PIN_BTN_3 = 42;
static constexpr int PIN_BTN_4 = 47;

// 步进电机 ULN2003（4相）
static constexpr int PIN_STEPPER_IN1 = 4;
static constexpr int PIN_STEPPER_IN2 = 5;
static constexpr int PIN_STEPPER_IN3 = 6;
static constexpr int PIN_STEPPER_IN4 = 7;

// TFT ILI9341（SPI）
static constexpr int PIN_TFT_MOSI = 11;
static constexpr int PIN_TFT_MISO = 10;
static constexpr int PIN_TFT_SCLK = 9;
static constexpr int PIN_TFT_CS = 8;
static constexpr int PIN_TFT_DC = 16;  // 你需要找一个空闲 GPIO 接 DC
static constexpr int PIN_TFT_RST = 17; // 你需要找一个空闲 GPIO 接 RST（也可接 EN/3V3，改为 -1）
static constexpr int PIN_TFT_BL = -1;  // 背光（可选）：有的屏幕后背有 BLK/LED 引脚

// 触摸（常见 2.4 寸 ILI9341 电阻触摸：XPT2046，SPI）
// 注意：触摸一般是“独立一套 CS + 共用 SPI”。
static constexpr int PIN_TOUCH_CS = -1; // 若你的屏带触摸，改成实际 CS 引脚，例如 3 / 38 等
static constexpr int PIN_TOUCH_IRQ = -1; // 可选：触摸中断脚

// IR（可选）
static constexpr int PIN_IR_TX = 48;

// -----------------
// 设备对象
// -----------------

static constexpr int SERIAL_BAUD = 115200;

#if HAVE_DHT
DHT dht(PIN_DHT, DHT22);
#endif

#if HAVE_SGP30
Adafruit_SGP30 sgp;
#endif

#if HAVE_TFT
Adafruit_ILI9341 tft(PIN_TFT_CS, PIN_TFT_DC, PIN_TFT_RST);
#endif

#if HAVE_INA219
Adafruit_INA219 ina219;
#endif

#if HAVE_INA219
static bool ina219Ok = false;
#endif

// 第二路 INA219（B 简化版）：测“太阳能充电模块/5V 输出”的功率
// 默认地址建议用 0x41（需要在模块上通过 A0/A1 焊盘改地址）。
#if HAVE_INA219
static constexpr uint8_t INA219_ADDR_SOLAR = 0x41;
Adafruit_INA219 ina219Solar(INA219_ADDR_SOLAR);
static bool ina219SolarOk = false;
#endif

#if HAVE_TOUCH
XPT2046_Touchscreen touch(PIN_TOUCH_CS, PIN_TOUCH_IRQ);
#endif

#ifdef USE_IR
IRsend irsend(PIN_IR_TX);
#endif

// -----------------
// 状态与参数
// -----------------

enum class CurtainTarget : uint8_t {
  Stop = 0,
  Open = 1,
  Close = 2,
};

struct Sensors {
  float temperatureC = NAN;
  float humidityPct = NAN;
  float illuminanceLux = NAN;
  uint16_t tvoc = 0;
  uint16_t eco2 = 0;
  bool sgpOk = false;
  bool inaOk = false;
  float busV = NAN;
  float currentmA = NAN;
  float powermW = NAN;

  bool solarInaOk = false;
  float solarBusV = NAN;
  float solarCurrentmA = NAN;
  float solarPowermW = NAN;
  uint32_t lastReadMs = 0;
};

static Sensors sensors;

// Self-healing counters / state (persist across soft reset when possible)
RTC_DATA_ATTR static uint32_t bootCount = 0;
static uint32_t i2cRecoverCount = 0;

static void replyStateJson();
static bool i2cRecover();
static void replyPinMapJson();
static void replyI2cScanJson();

// -----------------
// 内置 BH1750 最小驱动（避免依赖 BH1750 第三方库）
// 说明：BH1750 默认地址通常是 0x23（ADDR 接地）或 0x5C（ADDR 拉高）。
// 本驱动使用“连续高分辨率模式 1”（0x10），读 2 字节并换算 lux = raw / 1.2。
// -----------------

static constexpr uint8_t BH1750_ADDR_LOW = 0x23;
static constexpr uint8_t BH1750_ADDR_HIGH = 0x5C;
static uint8_t bh1750Addr = BH1750_ADDR_LOW;
static bool bh1750Ok = false;

static bool bh1750WriteCmd(uint8_t cmd) {
  Wire.beginTransmission(bh1750Addr);
  Wire.write(cmd);
  return Wire.endTransmission() == 0;
}

static bool bh1750Begin() {
  // 先尝试低地址，再尝试高地址
  bh1750Addr = BH1750_ADDR_LOW;
  if (bh1750WriteCmd(0x01)) {
    // Power On
    bh1750Ok = bh1750WriteCmd(0x10);
    return bh1750Ok;
  }

  bh1750Addr = BH1750_ADDR_HIGH;
  if (bh1750WriteCmd(0x01)) {
    bh1750Ok = bh1750WriteCmd(0x10);
    return bh1750Ok;
  }

  bh1750Ok = false;
  return false;
}

static float bh1750ReadLux() {
  if (!bh1750Ok) return NAN;

  Wire.requestFrom((int)bh1750Addr, 2);
  if (Wire.available() < 2) return NAN;

  uint16_t raw = ((uint16_t)Wire.read() << 8) | (uint16_t)Wire.read();
  return (float)raw / 1.2f;
}

static bool relayState[4] = {false, false, false, false};
static bool buzzerOn = false;

static CurtainTarget curtainTarget = CurtainTarget::Stop;
static int32_t curtainPositionSteps = 0;
static int32_t curtainMaxSteps = 2048; // 需要实测标定：从全开到全关的步数

static uint32_t lastUiMs = 0;
static uint32_t lastPushMs = 0;

// 步进电机（半步）序列：IN1 IN2 IN3 IN4
static const uint8_t STEPPER_SEQ[8][4] = {
  {1, 0, 0, 0},
  {1, 1, 0, 0},
  {0, 1, 0, 0},
  {0, 1, 1, 0},
  {0, 0, 1, 0},
  {0, 0, 1, 1},
  {0, 0, 0, 1},
  {1, 0, 0, 1},
};

static uint8_t stepperPhase = 0;
static uint32_t lastStepperMs = 0;
static uint32_t stepperIntervalMs = 3; // 越小越快；过快会丢步

// -----------------
// 小工具函数
// -----------------

static void setRelay(int index1Based, bool on) {
  if (index1Based < 1 || index1Based > 4) return;
  relayState[index1Based - 1] = on;

  int pin = -1;
  switch (index1Based) {
    case 1: pin = PIN_RELAY_1; break;
    case 2: pin = PIN_RELAY_2; break;
    case 3: pin = PIN_RELAY_3; break;
    case 4: pin = PIN_RELAY_4; break;
  }
  if (pin >= 0) {
    digitalWrite(pin, on ? HIGH : LOW);
  }
}

static void setBuzzer(bool on) {
  buzzerOn = on;
  digitalWrite(PIN_BUZZER, on ? HIGH : LOW);
}

static void stepperWritePhase(uint8_t phase) {
  digitalWrite(PIN_STEPPER_IN1, STEPPER_SEQ[phase][0]);
  digitalWrite(PIN_STEPPER_IN2, STEPPER_SEQ[phase][1]);
  digitalWrite(PIN_STEPPER_IN3, STEPPER_SEQ[phase][2]);
  digitalWrite(PIN_STEPPER_IN4, STEPPER_SEQ[phase][3]);
}

static void stepperDisable() {
  digitalWrite(PIN_STEPPER_IN1, LOW);
  digitalWrite(PIN_STEPPER_IN2, LOW);
  digitalWrite(PIN_STEPPER_IN3, LOW);
  digitalWrite(PIN_STEPPER_IN4, LOW);
}

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

static bool i2cRecover() {
  // Best-effort recovery for a stuck I2C bus.
  // 1) Generate a few SCL pulses (if SDA is stuck low, this may release the slave)
  // 2) Re-init Wire and re-init sensors
  pinMode(PIN_I2C_SCL, OUTPUT_OPEN_DRAIN);
  digitalWrite(PIN_I2C_SCL, HIGH);
  pinMode(PIN_I2C_SDA, INPUT_PULLUP);
  delay(2);
  for (int i = 0; i < 9; i++) {
    digitalWrite(PIN_I2C_SCL, LOW);
    delayMicroseconds(5);
    digitalWrite(PIN_I2C_SCL, HIGH);
    delayMicroseconds(5);
  }

  // Hand control back to Wire
  #if defined(ARDUINO_ARCH_ESP32)
  Wire.end();
  #endif
  delay(5);
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);

  bool ok = true;
  ok = bh1750Begin() && ok;

  #if HAVE_INA219
  ina219Ok = ina219.begin();
  ina219SolarOk = ina219Solar.begin();
  ok = (ina219Ok || ina219SolarOk) && ok;
  #endif

  #if HAVE_SGP30
  // SGP30 may be optional; treat failure as non-fatal for overall bus recovery
  sgp.begin();
  #endif

  i2cRecoverCount++;
  return ok;
}

static void readSensorsIfDue(uint32_t nowMs) {
  // DHT 太频繁会不稳定；这里 2s 一次
  if (nowMs - sensors.lastReadMs < 2000) return;
  sensors.lastReadMs = nowMs;

  #if HAVE_DHT
  sensors.temperatureC = dht.readTemperature();
  sensors.humidityPct = dht.readHumidity();
  #else
  sensors.temperatureC = NAN;
  sensors.humidityPct = NAN;
  #endif
  sensors.illuminanceLux = bh1750ReadLux();

  // SGP30：建议每秒 measure 一次，这里按 1s
  sensors.sgpOk = false;
  static uint32_t lastSgpMs = 0;
  if (nowMs - lastSgpMs >= 1000) {
    lastSgpMs = nowMs;
    #if HAVE_SGP30
      if (sgp.IAQmeasure()) {
        sensors.sgpOk = true;
        sensors.tvoc = sgp.TVOC;
        sensors.eco2 = sgp.eCO2;
      }
    #endif
  }

  // INA219：电源/储能监测（2s 一次即可）
  sensors.inaOk = false;
  #if HAVE_INA219
  if (ina219Ok) {
    // ina219 读取会比较快，这里直接读取
    sensors.busV = ina219.getBusVoltage_V();
    sensors.currentmA = ina219.getCurrent_mA();
    sensors.powermW = ina219.getPower_mW();
    // 读到 NaN 视为失败
    if (!isnan(sensors.busV) && !isnan(sensors.currentmA) && !isnan(sensors.powermW)) {
      sensors.inaOk = true;
    }
  }
  #endif

  // 第二路 INA219：太阳能输入（可选）
  sensors.solarInaOk = false;
  #if HAVE_INA219
  if (ina219SolarOk) {
    sensors.solarBusV = ina219Solar.getBusVoltage_V();
    sensors.solarCurrentmA = ina219Solar.getCurrent_mA();
    sensors.solarPowermW = ina219Solar.getPower_mW();
    if (!isnan(sensors.solarBusV) && !isnan(sensors.solarCurrentmA) && !isnan(sensors.solarPowermW)) {
      sensors.solarInaOk = true;
    }
  }
  #endif
}

static void updateStepperIfNeeded(uint32_t nowMs) {
  if (curtainTarget == CurtainTarget::Stop) {
    stepperDisable();
    return;
  }

  if (nowMs - lastStepperMs < stepperIntervalMs) return;
  lastStepperMs = nowMs;

  // 目标边界
  if (curtainTarget == CurtainTarget::Open && curtainPositionSteps <= 0) {
    curtainPositionSteps = 0;
    curtainTarget = CurtainTarget::Stop;
    stepperDisable();
    return;
  }
  if (curtainTarget == CurtainTarget::Close && curtainPositionSteps >= curtainMaxSteps) {
    curtainPositionSteps = curtainMaxSteps;
    curtainTarget = CurtainTarget::Stop;
    stepperDisable();
    return;
  }

  // 走一步
  if (curtainTarget == CurtainTarget::Open) {
    stepperPhase = (stepperPhase + 7) % 8;
    curtainPositionSteps--;
  } else {
    stepperPhase = (stepperPhase + 1) % 8;
    curtainPositionSteps++;
  }

  stepperWritePhase(stepperPhase);
}

static void drawUi(uint32_t nowMs) {
#if !HAVE_TFT
  (void)nowMs;
  return;
#else
  if (nowMs - lastUiMs < 500) return;
  lastUiMs = nowMs;

  tft.fillScreen(ILI9341_BLACK);
  tft.setTextWrap(false);

  tft.setCursor(10, 10);
  tft.setTextSize(2);
  tft.setTextColor(ILI9341_CYAN);
  tft.print("T:");
  if (!isnan(sensors.temperatureC)) {
    tft.print(sensors.temperatureC, 1);
    tft.print("C ");
  } else {
    tft.print("--.-C ");
  }

  tft.setTextColor(ILI9341_YELLOW);
  tft.print("H:");
  if (!isnan(sensors.humidityPct)) {
    tft.print(sensors.humidityPct, 0);
    tft.print("%");
  } else {
    tft.print("--%");
  }

  tft.setCursor(10, 45);
  tft.setTextSize(2);
  tft.setTextColor(ILI9341_GREEN);
  tft.print("Lux: ");
  if (!isnan(sensors.illuminanceLux)) {
    tft.print(sensors.illuminanceLux, 0);
  } else {
    tft.print("--");
  }

  tft.setCursor(10, 80);
  tft.setTextSize(2);
  tft.setTextColor(ILI9341_WHITE);
  tft.print("eCO2: ");
  if (sensors.sgpOk) {
    tft.print(sensors.eco2);
    tft.print(" ppm");
  } else {
    tft.print("--");
  }

  tft.setCursor(10, 115);
  tft.setTextSize(2);
  tft.setTextColor(ILI9341_WHITE);
  tft.print("TVOC: ");
  if (sensors.sgpOk) {
    tft.print(sensors.tvoc);
    tft.print(" ppb");
  } else {
    tft.print("--");
  }

  tft.setCursor(10, 155);
  tft.setTextSize(2);
  tft.setTextColor(ILI9341_MAGENTA);
  tft.print("R:");
  for (int i = 0; i < 4; i++) {
    tft.print(relayState[i] ? "1" : "0");
    if (i != 3) tft.print(' ');
  }

  tft.setCursor(10, 190);
  tft.setTextSize(2);
  tft.setTextColor(ILI9341_ORANGE);
  tft.print("Curtain: ");
  tft.print(curtainPositionSteps);
  tft.print('/');
  tft.print(curtainMaxSteps);

  tft.setCursor(10, 225);
  tft.setTextSize(2);
  tft.setTextColor(ILI9341_CYAN);
  tft.print("PWR: ");
  if (sensors.inaOk) {
    tft.print(sensors.busV, 2);
    tft.print("V ");
    tft.print(sensors.currentmA, 0);
    tft.print("mA ");
    tft.print(sensors.powermW / 1000.0f, 2);
    tft.print("W");
  } else {
    tft.print("--");
  }

  tft.print("  SOL: ");
  if (sensors.solarInaOk) {
    tft.print(sensors.solarPowermW / 1000.0f, 2);
    tft.print("W");
  } else {
    tft.print("--");
  }

  // 触摸调试显示（可选，不影响不带触摸的屏）
  #if HAVE_TOUCH
  if (PIN_TOUCH_CS >= 0 && touch.touched()) {
    TS_Point p = touch.getPoint();
    tft.setCursor(10, 260);
    tft.setTextSize(2);
    tft.setTextColor(ILI9341_WHITE);
    tft.print("Touch:");
    tft.print(p.x);
    tft.print(",");
    tft.print(p.y);
  }
  #endif
#endif
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

  replyError("UNKNOWN_CMD");
}

static void handleButtons() {
  // 轻量演示：按键1/2 控窗帘，按键3/4 控继电器1/2
  // 需要外接按键模块时，建议用 INPUT_PULLUP（按下为 LOW）
  static uint32_t lastDebounceMs = 0;
  static uint8_t lastMask = 0;

  uint32_t now = millis();
  if (now - lastDebounceMs < 30) return;
  lastDebounceMs = now;

  uint8_t mask = 0;
  mask |= (digitalRead(PIN_BTN_1) == LOW) ? 0x01 : 0x00;
  mask |= (digitalRead(PIN_BTN_2) == LOW) ? 0x02 : 0x00;
  mask |= (digitalRead(PIN_BTN_3) == LOW) ? 0x04 : 0x00;
  mask |= (digitalRead(PIN_BTN_4) == LOW) ? 0x08 : 0x00;

  uint8_t rising = (uint8_t)(mask & ~lastMask);
  lastMask = mask;

  if (rising & 0x01) curtainTarget = CurtainTarget::Open;
  if (rising & 0x02) curtainTarget = CurtainTarget::Close;
  if (rising & 0x04) setRelay(1, !relayState[0]);
  if (rising & 0x08) setRelay(2, !relayState[1]);
}

// ================== MQTT 函数（骨架） ==================
#ifdef USE_MQTT

// ---- 用户配置：请按实际环境修改 ----
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

// -----------------
// Setup / Loop
// -----------------

void setup() {
  Serial.begin(SERIAL_BAUD);

  bootCount++;

  pinMode(PIN_RELAY_1, OUTPUT);
  pinMode(PIN_RELAY_2, OUTPUT);
  pinMode(PIN_RELAY_3, OUTPUT);
  pinMode(PIN_RELAY_4, OUTPUT);
  setRelay(1, false);
  setRelay(2, false);
  setRelay(3, false);
  setRelay(4, false);

  pinMode(PIN_BUZZER, OUTPUT);
  setBuzzer(false);

  pinMode(PIN_BTN_1, INPUT_PULLUP);
  pinMode(PIN_BTN_2, INPUT_PULLUP);
  pinMode(PIN_BTN_3, INPUT_PULLUP);
  pinMode(PIN_BTN_4, INPUT_PULLUP);

  pinMode(PIN_STEPPER_IN1, OUTPUT);
  pinMode(PIN_STEPPER_IN2, OUTPUT);
  pinMode(PIN_STEPPER_IN3, OUTPUT);
  pinMode(PIN_STEPPER_IN4, OUTPUT);
  stepperDisable();

#ifdef USE_IR
  irsend.begin();
#endif

  #if HAVE_DHT
  dht.begin();
  #endif

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  bh1750Begin();

  #if HAVE_INA219
  // INA219 默认地址 0x40（多数模块不改地址）
  // 如果你买的模块改过 A0/A1 地址，需要按库文档设置。
  ina219Ok = ina219.begin();

  // 第二路 INA219（太阳能输入）默认 0x41
  // 如果你没接第二路或没改地址，begin() 会失败但不影响运行。
  ina219SolarOk = ina219Solar.begin();
  #endif

  #if HAVE_SGP30
  if (!sgp.begin()) {
    // SGP30 可能没接/没供电，这不致命，继续跑
    sensors.sgpOk = false;
  }
  #endif

  // TFT 初始化（如果没装屏幕库，则自动跳过）
  #if HAVE_TFT
  SPI.begin(PIN_TFT_SCLK, PIN_TFT_MISO, PIN_TFT_MOSI, PIN_TFT_CS);
  if (PIN_TFT_BL >= 0) {
    pinMode(PIN_TFT_BL, OUTPUT);
    digitalWrite(PIN_TFT_BL, HIGH);
  }
  tft.begin();
  tft.setRotation(1);
  tft.fillScreen(ILI9341_BLACK);
  tft.setTextSize(2);
  tft.setTextColor(ILI9341_WHITE);
  tft.setCursor(10, 10);
  tft.println("Booting...");

  #if HAVE_TOUCH
  if (PIN_TOUCH_CS >= 0) {
    touch.begin();
    touch.setRotation(1);
  }
  #endif
  #endif

#ifdef USE_MQTT
  setupWiFi();
  reconnectMQTT();
#endif

  Serial.println("ESP32 Ready");
}

void loop() {
  uint32_t now = millis();

  readSensorsIfDue(now);
  updateStepperIfNeeded(now);
  handleButtons();
  drawUi(now);

  // 可选：每 5 秒主动推送一次（串口 + MQTT 双通道）
  if (now - lastPushMs >= 5000) {
    lastPushMs = now;
    replySensorsJson();
#ifdef USE_MQTT
    mqttPublishSensors();
#endif
  }

  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    handleCommand(line);
  }

#ifdef USE_MQTT
  if (WiFi.status() == WL_CONNECTED) {
    if (!mqttClient.connected()) {
      if (now - lastMqttReconnectMs >= 5000) {
        lastMqttReconnectMs = now;
        reconnectMQTT();
      }
    } else {
      mqttClient.loop();
    }
  }
#endif

  delay(5);
}
