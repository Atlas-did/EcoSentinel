// sensors.h — sensor acquisition (BH1750 driver, periodic read, I2C recovery).
//
// Owns the low-level sensor reads and populates the shared SensorFrame
// (struct Sensors). Missing sensors report NaN + a false *Ok flag, never a
// fabricated normal value.
#pragma once

#include "state.h"

// -----------------
// 内置 BH1750 最小驱动（避免依赖 BH1750 第三方库）
// 说明：BH1750 默认地址通常是 0x23（ADDR 接地）或 0x5C（ADDR 拉高）。
// 本驱动使用“连续高分辨率模式 1”（0x10），读 2 字节并换算 lux = raw / 1.2。
// -----------------

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
