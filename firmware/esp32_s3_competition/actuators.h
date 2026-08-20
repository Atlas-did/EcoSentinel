// actuators.h — relay, buzzer, and stepper (curtain) control.
//
// Each actuator keeps its own state and never shares a single giant command
// function. Command routing (protocol.h) calls these primitives; this module
// owns the low-level pin writes and the curtain stepping state machine.
#pragma once

#include "state.h"

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
