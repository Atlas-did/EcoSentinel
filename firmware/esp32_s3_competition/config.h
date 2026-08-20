// config.h — pins, sampling/bus constants, feature switches, and device objects.
//
// All GPIO assignments, I2C addresses, and compile-time feature toggles live here
// so no magic numbers are scattered through the sketch. Included first by the
// sketch; every other module may assume the macros and objects here are defined.
#pragma once

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
// 协议版本（新协议字段：GET_STATE 回复中携带，旧命令保持兼容）
// -----------------
static constexpr uint8_t PROTOCOL_VERSION = 1;

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
// 总线常量
// -----------------

static constexpr int SERIAL_BAUD = 115200;

// 内置 BH1750 最小驱动地址（避免依赖 BH1750 第三方库）
// 默认地址通常是 0x23（ADDR 接地）或 0x5C（ADDR 拉高）。
static constexpr uint8_t BH1750_ADDR_LOW = 0x23;
static constexpr uint8_t BH1750_ADDR_HIGH = 0x5C;

// 第二路 INA219（B 简化版）：测“太阳能充电模块/5V 输出”的功率
// 默认地址建议用 0x41（需要在模块上通过 A0/A1 焊盘改地址）。
static constexpr uint8_t INA219_ADDR_SOLAR = 0x41;

// -----------------
// 设备对象
// -----------------

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
static bool ina219Ok = false;
Adafruit_INA219 ina219Solar(INA219_ADDR_SOLAR);
static bool ina219SolarOk = false;
#endif

#if HAVE_TOUCH
XPT2046_Touchscreen touch(PIN_TOUCH_CS, PIN_TOUCH_IRQ);
#endif

#ifdef USE_IR
IRsend irsend(PIN_IR_TX);
#endif
