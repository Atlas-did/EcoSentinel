// display.h — TFT status screen (optional).
//
// Renders a read-only status line for each sensor channel plus relay/curtain
// state. Compiled out entirely when no TFT library is present, and skipped at
// runtime for boards without a touch panel.
#pragma once

#include "config.h"
#include "state.h"

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
