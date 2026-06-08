# EcoSentinel — Hardware Procurement & Wiring Guide (Competition Edition)

This guide separates “getting it running” from “getting it to score” —

- 能跑起来：用最少器件走通传感器采集 → 串口通信 → 继电器执行。
- 能拿分：用屏幕/多传感器/步进电机/红外等把展示效果拉满，评委一眼看懂你做的是“完整闭环系统”。

---

## 1. 采购清单（分级 BOM）

### 方案 A：基础验证版（￥60 级别，目标：闭环跑通）

- 主控：ESP32-C3 开发板（带 USB 转串口芯片，Type-C）
- 温湿度：DHT11（或 DHT22）模块
- 光照：BH1750 模块（I2C）
- 执行：2 路继电器模块（强烈建议光耦隔离）
- 杂项：优质杜邦线、面包板、Type-C 数据线（必须能传数据）

### 方案 B：专业竞赛豪华版（￥398 级别，目标：展示效果与技术深度）

**核心算力与供电**

- ESP32-S3 开发板（引脚多、资源足，适合屏幕与多外设）
- LM2596 降压模块（建议 12V/2A 适配器 → 5V/3A 给继电器/屏幕）

**多模态传感器阵列**

- DHT22（精度明显优于 DHT11）
- BH1750（光照）
- SGP30（TVOC/eCO2，空气质量亮点）
- 可选对照：BME280（更高精度的温湿度/气压）

**执行器矩阵（视觉冲击力）**

- 4 路继电器（空调/照明/新风/备用）
- 28BYJ-48 步进电机 + ULN2003（做“自动窗帘”模型）
- 红外发射模块（发射空调红外码，比“断电式控制”更像真实产品）

**本地交互（HMI）**

- ILI9341 2.4"/2.8" SPI TFT（把关键指标在设备端展示）
- 蜂鸣器 + 按键（超限报警、本地切换模式）

---

## 1.3 比赛展示优先（推荐落地）：A 方案单 INA219 + 成品充电宝当储能

你选择的目标是“系统消耗功率/节能对比”，最稳的硬件做法是：

- 储能：用成品充电宝/USB 电源模块（安全、省事、可重复）。
- 计量：只测“充电宝 5V 输出 → 系统负载”的功率/能耗。

### 必买硬件

- INA219 模块 ×1（I2C）
- 成品充电宝/USB 电源模块（≥ 2A 输出更稳）

### 接线拓扑（关键）

把 INA219 串在供电正极上：

```text
充电宝 5V(+)  -> INA219 VIN+ -> INA219 VIN- -> 系统 5V 输入(供继电器/屏幕/外设)
充电宝 GND    -> 系统 GND（必须共地）

INA219 VCC -> 3.3V
INA219 GND -> GND
INA219 SDA -> GPIO21
INA219 SCL -> GPIO38
```

这样固件会回传：`bus_v / current_ma / pwr_mw`，TFT 上也会显示 `PWR: xV y mA zW`。

---

## 1.4 B 简化版（可选加分）：第二路 INA219 测“太阳能 5V 输出功率”

目标：在不破坏 A 方案（单 INA219 测系统消耗功率/能耗）的前提下，再加一块 INA219，用来测“太阳能充电模块/升压模块输出的 5V”的电压/电流/功率（输入侧），形成“输入功率 vs 系统消耗功率”的对照展示。

### 地址要求（必须）

两块 INA219 共用同一条 I2C 总线时，必须是不同地址：

- 系统消耗（INA219#1）：默认 `0x40`
- 太阳能输入（INA219#2）：建议改到 `0x41`

多数 INA219 模块通过 A0/A1 焊盘改地址（不同厂家的丝印略有差异）。你需要把第二块 INA219 改到 `0x41`，否则两块会冲突。

固件默认已按 `0x41` 初始化第二路（`INA219_ADDR_SOLAR`）。如果你改成了别的地址，需要同步改固件。

### 接线拓扑（推荐布点）

把 INA219#2 串在“太阳能模块 5V 输出正极”上：

```text
太阳能板 -> 充电/升压模块 -> 5V(+) -> INA219#2 VIN+ -> INA219#2 VIN- -> 系统 5V 总线/充电宝输入(+)
GND 全部共地

INA219#2 VCC -> 3.3V
INA219#2 GND -> GND
INA219#2 SDA -> GPIO21 (与 INA219#1/BH1750/SGP30 并联)
INA219#2 SCL -> GPIO38 (与 INA219#1/BH1750/SGP30 并联)
```

注意：`VCC/GND/SDA/SCL` 可以并联共用；但每块 INA219 的 `VIN+/VIN-` 是各自的电流通道，不要接混。

### 串口 JSON 字段（新增）

当第二路 INA219 初始化成功时，`READ_SENSORS` 的 JSON 会额外包含：

- `solar_bus_v`
- `solar_current_ma`
- `solar_pwr_mw`

如果没接第二路、地址没改对、或初始化失败，这些字段不会出现（会自动降级，不影响 A 方案）。

---

## 2. 接线与供电原则（最容易翻车的点）

- ESP32 与传感器逻辑电平：基本都是 3.3V；DHT 系列优先接 3.3V。
- 继电器：多数需要 5V 供电，但控制脚一般可识别 3.3V。
- 必须共地：ESP32 GND、传感器 GND、继电器 GND 必须连在一起。
- 串口独占：Python 通信时必须关闭 Arduino 串口监视器。

---

## 3. 推荐引脚分配（以 ESP32-S3 豪华版为例）

> 下面是“推荐”，不是唯一正确答案；你也可以按自己开发板丝印调整。
> 但请避免 ESP32-S3 常见禁区：22~25（不存在）、26~32（内部 SPI）、33~37（常见 Flash/PSRAM 复用）。

```text
I2C 总线（并联 BH1750 / SGP30 / INA219）
- GPIO21: SDA
- GPIO38: SCL

DHT22
- GPIO18: DATA

继电器（四路）
- GPIO12: RELAY1（空调）
- GPIO13: RELAY2（照明）
- GPIO14: RELAY3（新风）
- GPIO15: RELAY4（备用）

步进电机 ULN2003
- GPIO4~GPIO7: IN1~IN4

红外发射
- GPIO48: IR_TX

蜂鸣器
- GPIO39: BUZZER

按键（4 路）
- GPIO40: BTN1
- GPIO41: BTN2
- GPIO42: BTN3
- GPIO47: BTN4
```

---

## 4. 到货前就能做的事：把固件先写好、先编译过

### 4.1 Arduino IDE 与开发板支持

1. 安装 Arduino IDE 2.x。
2. 在“附加开发板管理器网址”添加：
   - `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
3. 开发板管理器安装 `esp32`。
4. 库管理器安装：
   - `DHT sensor library`（Adafruit）
   - `BH1750`
   - （可选）`Adafruit SGP30 Sensor`

### 4.2 固件示例（统一 READ_SENSORS + RELAY）

这段固件的目标是：**Python 端只要发送一条 `READ_SENSORS`，就拿到一条 JSON**；控制执行则用 `RELAY n state`。

### 4.3 豪华版完整固件（含屏幕/步进/空气质量/按键）

我已经把“豪华版”做成了一个可以直接用 Arduino IDE 打开的工程文件：

- 固件路径：firmware/esp32_s3_competition/esp32_s3_competition.ino

它包含：

- 传感器：DHT22、BH1750、SGP30（可不接，固件会自动降级）
- 显示：ILI9341 SPI TFT（显示温湿度/光照/eCO2/TVOC/继电器/窗帘位置）
- 执行：4 路继电器、蜂鸣器
- 机械演示：ULN2003 + 28BYJ-48 步进电机（窗帘模型，支持 OPEN/CLOSE/STOP）
- 交互：4 个按键（示例映射：按键1/2 控窗帘，按键3/4 切换继电器1/2）
- 串口协议：一行一条命令，回 JSON

#### 需要安装的 Arduino 库

在 Arduino IDE 的“库管理器”安装：

- `DHT sensor library`（Adafruit）

可选（装了就启用，没装也能编译通过，固件会自动降级）：

- `Adafruit SGP30 Sensor`
- `Adafruit GFX Library`
- `Adafruit ILI9341`

说明：固件里 **BH1750 不再依赖第三方 `BH1750` 库**，而是直接用 `Wire` 按 I2C 协议读取（解决“装了库也找不到头文件”的常见坑）。

（可选）如果你要发红外，再安装：

- `IRremoteESP8266`（并在固件里把 `#define USE_IR` 打开）

#### TFT 额外说明（最容易卡住的点）

ILI9341 屏除了 SPI 线（MOSI/MISO/SCK/CS）以外，**还必须要 DC 与 RST 两根控制线**：

- 你给的表里只有 SPI 的 4 根线；请再额外选 2 个空闲 GPIO：
  - `PIN_TFT_DC`（默认用 GPIO16）
  - `PIN_TFT_RST`（默认用 GPIO17；如果你把 RST 直接接 3.3V，也可以把代码里改成 `-1`）

如果你的屏幕背板有 `BL/LED`（背光）引脚：

- 可以接到 3.3V 常亮；或者接一个 GPIO 做亮度控制（固件里 `PIN_TFT_BL`，默认关闭为 `-1`）。

---

## 5. SPI 触摸屏（你这张图对应的 14Pin/9Pin 引脚表）

你发的引脚表非常典型：

- 显示：ILI9341（SPI）
- 触摸：XPT2046（SPI）

### SPI 复用规则（必须这样接）

触摸与显示共用 SPI 三根线：

- `T_CLK` ↔ `SCK`
- `T_DIN` ↔ `SDI(MOSI)`
- `T_DO` ↔ `SDO(MISO)`

但片选必须分开：

- 显示用 `CS`
- 触摸用 `T_CS`

### 背光 LED（你选的方案：3.3V 常亮）

- `LED` 直接接 3.3V 常亮即可（比赛最省事、最稳）。

### 固件需要改的引脚（触摸启用必改）

固件文件：`firmware/esp32_s3_competition/esp32_s3_competition.ino`

- `PIN_TOUCH_CS`：改成你实际接的 `T_CS` GPIO（默认 -1 表示关闭触摸）
- （可选）`PIN_TOUCH_IRQ`：接 `T_IRQ` GPIO（不接也能用，但 IRQ 更省电/更灵敏）

---

## 6. 看板硬件模式：开始/停止采集（比赛现场建议流程）

你现在的 `dashboard.py` 硬件模式支持“开始/停止采集”，用于现场稳定展示功率曲线。

### 6.1 启动看板

在项目根目录执行：

```bash
streamlit run dashboard.py
```

### 6.2 硬件模式操作步骤

1) 在左侧选择：`物理硬件 (Real-time)`
2) 串口连接区：填写正确的 `COM` 口与波特率 `115200`，点击“连接/重连”
3) 采集控制区：
  - 设置“采集间隔（秒）”（建议 1~2 秒，曲线更平滑）
  - 点击“开始”进入自动采集（会持续轮询串口并更新曲线）
  - 需要暂停展示时点击“停止”
  - 重新开始一轮展示前可点“清空”（清空本次缓存曲线）
4) 如仅需手动拉取一次数据，可点击“刷新一次”

---

## 7. AI / DeepSeek（Demo）最小跑通（软件侧）

硬件部分接好后，如果你要展示“AI 建议 + 可降级 + 候选池 + 反馈闭环”，建议按下面顺序：

1) DeepSeek connectivity test (verify key, network, and dependencies):

```bash
python scripts/test_deepseek.py
```

2) 再编辑 `energy_system/config/params.yaml` 启用 AI（建议先用 `suggest`）：

```yaml
ai:
  enabled: true
  control_mode: suggest
  model: deepseek-chat
  api_base: https://api.deepseek.com/v1
  enable_local_fallback: true
```

3) Key 注入方式（二选一）：

- 环境变量（推荐）：`DEEPSEEK_API_KEY=...`
- 或写入项目根目录 `.env`：`DEEPSEEK_API_KEY=...`（文件已被 `.gitignore` 忽略）

4) 运行主程序：会写入 `logs/hardware_<label>.jsonl`，看板会展示 AI candidate 的聚合指标（成功率/延迟/评分等）。

### 6.3 与节能对比（A 方案）如何配合

如果你要展示“基准 vs 节能”的能耗对比：

- 先运行一次 `main.py` 并设置 `RUN_LABEL=baseline`，生成 `logs/hardware_baseline.jsonl`
- 再运行一次 `main.py` 并设置 `RUN_LABEL=saving`，生成 `logs/hardware_saving.jsonl`

看板硬件模式下的“系统能耗/节能对比（基于日志）”区域会自动读取这两份日志，计算节能率并绘制对比曲线。

#### 串口指令（直接复制就能测）

波特率 `115200`，结尾符选 `NewLine`：

- `READ_SENSORS` → 返回一行 JSON（温湿度/光照/空气质量/继电器/窗帘位置）
- `RELAY 1 1` / `RELAY 1 0` → 打开/关闭继电器 1（其余 2/3/4 同理）
- `BUZZER 1` / `BUZZER 0` → 蜂鸣器开/关
- `CURTAIN OPEN` / `CURTAIN CLOSE` / `CURTAIN STOP`
- `CURTAIN CAL 2048` → 标定“全开到全关”的步数上限（一定要实测后改）

（可选）红外：

- `IR_NEC 0x20DF10EF 32` → 发送一个 NEC 示例码（仅用于演示链路，真实空调码需要采集）

```cpp
#include <Arduino.h>
#include <Wire.h>

#include <DHT.h>
#include <BH1750.h>

// 可选：如果你安装了 Adafruit SGP30 库，再打开这行
// #define USE_SGP30

#ifdef USE_SGP30
#include <Adafruit_SGP30.h>
#endif

#define DHT_PIN 18
#define RELAY1_PIN 12
#define RELAY2_PIN 13

#define I2C_SDA 21
#define I2C_SCL 38

DHT dht(DHT_PIN, DHT22);
BH1750 lightMeter;

#ifdef USE_SGP30
Adafruit_SGP30 sgp;
#endif

static void setRelay(int relayNum, int state) {
  int value = (state != 0) ? HIGH : LOW;
  if (relayNum == 1) digitalWrite(RELAY1_PIN, value);
  if (relayNum == 2) digitalWrite(RELAY2_PIN, value);
}

void setup() {
  Serial.begin(115200);

  pinMode(RELAY1_PIN, OUTPUT);
  pinMode(RELAY2_PIN, OUTPUT);
  setRelay(1, 0);
  setRelay(2, 0);

  dht.begin();

  Wire.begin(I2C_SDA, I2C_SCL);
  lightMeter.begin();

#ifdef USE_SGP30
  sgp.begin();
#endif

  Serial.println("ESP32 Ready");
}

static void replySensorsJson() {
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  float lux = lightMeter.readLightLevel();

  // DHT 偶尔会读到 NaN；这里直接不回包，便于上位机重试
  if (isnan(t) || isnan(h)) return;

  Serial.print("{\"temperature\":");
  Serial.print(t, 2);
  Serial.print(",\"humidity\":");
  Serial.print(h, 2);
  Serial.print(",\"illuminance\":");
  Serial.print(lux, 1);

#ifdef USE_SGP30
  if (sgp.IAQmeasure()) {
    Serial.print(",\"tvoc\":");
    Serial.print(sgp.TVOC);
    Serial.print(",\"eco2\":");
    Serial.print(sgp.eCO2);
  }
#endif

  Serial.println("}");
}

static void processLine(String line) {
  line.trim();
  if (line.length() == 0) return;

  if (line == "READ_SENSORS") {
    replySensorsJson();
    return;
  }

  if (line.startsWith("RELAY")) {
    // 格式：RELAY 1 1
    int firstSpace = line.indexOf(' ');
    int secondSpace = line.indexOf(' ', firstSpace + 1);
    if (firstSpace < 0 || secondSpace < 0) return;

    int relayNum = line.substring(firstSpace + 1, secondSpace).toInt();
    int state = line.substring(secondSpace + 1).toInt();
    setRelay(relayNum, state);
    Serial.println("{\"success\":true}");
    return;
  }
}

void loop() {
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    processLine(line);
  }
  delay(30);
}
```

---

## 5. 货到后的落地四步走（零玄学）

1. **先接低压**：只接 3.3V 传感器与 I2C，不要上 220V。
2. **先烧录**：Arduino IDE 选择正确端口与开发板，上传固件。
3. **先裸测**（串口监视器 115200 + NewLine）：
   - 发 `READ_SENSORS`，应返回一行 JSON。
   - 发 `RELAY 1 1`，听继电器“嗒”一声。
4. **再上 Python**：关闭串口监视器，Python 才能独占串口通信。

---

## 6. 竞赛展示怎么讲（评委最吃这一套）

- 层 1（真实世界）：桌面屏幕/串口日志展示“实时温湿度 + 空气质量 + 光照”。
- 层 2（算法效果）：电脑端 Streamlit 展示“基线 vs 节能控制”对比曲线与节能率。
- 层 3（执行闭环）：用手电筒照 BH1750 → 触发策略 → 步进电机拉窗帘/继电器关灯，形成强记忆点。