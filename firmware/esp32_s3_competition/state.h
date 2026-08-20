// state.h — runtime state shared by the sensors, actuators, protocol, display
// and MQTT modules. Declared before those modules so their function bodies can
// reference these globals. All linkage is `static` (single sketch TU), matching
// the original single-file layout.
#pragma once

#include "types.h"

static Sensors sensors;

// Self-healing counters / state (persist across soft reset when possible)
RTC_DATA_ATTR static uint32_t bootCount = 0;
static uint32_t i2cRecoverCount = 0;

static bool relayState[4] = {false, false, false, false};
static bool buzzerOn = false;

static CurtainTarget curtainTarget = CurtainTarget::Stop;
static int32_t curtainPositionSteps = 0;
static int32_t curtainMaxSteps = 2048; // 需要实测标定：从全开到全关的步数

static uint32_t lastUiMs = 0;
static uint32_t lastPushMs = 0;

static uint8_t bh1750Addr = BH1750_ADDR_LOW;
static bool bh1750Ok = false;

static uint8_t stepperPhase = 0;
static uint32_t lastStepperMs = 0;
static uint32_t stepperIntervalMs = 3; // 越小越快；过快会丢步
