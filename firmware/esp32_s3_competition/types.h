// types.h — shared data types (SensorFrame + actuator target enum).
//
// The single sensor output struct used across the sensor, protocol, display and
// MQTT modules. Missing readings are represented as NaN (never fabricated as a
// plausible-looking normal value) and per-channel OK flags mark read failures.
#pragma once

#include "config.h"

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
