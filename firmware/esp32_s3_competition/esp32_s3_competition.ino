// ============================================================
//  ESP32-S3 环境监测节点 —— 主 sketch
// ============================================================
//  结构（header-only，单一翻译单元）：
//    config.h    — 引脚、总线常量、特性开关、设备对象
//    types.h     — 共享类型（Sensors 结构体 + 窗帘目标枚举）
//    state.h     — 运行时状态（全局变量，static 链接）
//    actuators.h — 继电器/蜂鸣器/步进电机驱动
//    sensors.h   — 传感器采集（BH1750 驱动、周期读取、I2C 自愈）
//    protocol.h  — 串口行协议（回复助手 + 命令路由）
//    display.h   — TFT 状态屏（可选）
//    mqtt.h      — MQTT 分布式接入骨架（可选）
//
//  本文件只保留 setup() / loop()。所有模块均以 `#pragma once` +
//  `static` 链接组织，等价于原单文件实现；串口协议字段保持不变。
//
//  注意：本环境无 Arduino/PlatformIO 工具链，此拆分需在 Arduino IDE 或
//  PlatformIO 中重新编译验证一次。
// ============================================================

#include "config.h"
#include "types.h"
#include "state.h"
#include "actuators.h"
#include "sensors.h"
#include "protocol.h"
#include "display.h"
#include "mqtt.h"

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
