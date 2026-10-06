# AGENTS.md — EcoSentinel 代理开发规范

> 面向"能读文件、能跑命令"的 AI 代理（DSH / Claude Code / Cursor / Codex …），人类协作者同样适用。
> **先读本文件，再读 `README.md` 与 `docs/`。** 判据一律以**退出码**为准，不以日志文字为准。

## 0. 这是什么（30 秒）

ESP32-S3 边缘环境监测 + AI 节能控制：Python 边缘服务（`energy_system/`，FastAPI + Streamlit）
+ React 看板（`app/`）+ Arduino 固件（`firmware/esp32_s3_competition/`）。

## 1. 五分钟上手（不需要硬件）

```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows（Linux/macOS: . .venv/bin/activate）
pip install -r requirements.txt                    # 核心：API / 固件工具 / 测试
python -m pytest tests -q                          # 应全绿（2026-10 基线 251 passed）
python -m energy_system.simulation.compare         # 确定性仿真：baseline vs saving
python scripts/stack_acceptance.py                 # 一条命令自证"整栈健康"（起 API→打端点→校验 schema→退出码）
```

可选（只有要用 Streamlit 看板时才装，见 `requirements-dashboard.txt`，会多出 streamlit/pandas/matplotlib）：

```bash
pip install -r requirements-dashboard.txt
python -m streamlit run dashboard.py
```

前端（三道门禁都要过）：

```bash
cd app && npm ci && npm run lint && npm run knip && npm test && npm run build
```

> ⚠️ **两条已知陷阱**（2026-10 已修复，但历史文档/旧截图里可能仍是错的）：
> 1. 仿真对比**必须**用 `python -m energy_system.simulation.compare`；写成
>    `python energy_system/simulation/compare.py` 会 `ModuleNotFoundError`。
> 2. 节能率**现行口径是 17.6%**（建筑参数为演示级、未标定）。仓库历史与旧材料里出现过
>    **29.6% / 29.8% / 29.9%** —— 那些出自热模型显式欧拉**发散**时的无效仿真，**已作废**，
>    不要在总结/答辩材料里再引用（`tests/contract/test_metrics_registry.py` 会拦住前端回潮）。

延伸阅读：`docs/handoff.md`（交接状态 + 明确没做的事 + 待用户拍板的三件事）、
`docs/dsh-plugins-guide.md`（队友的 DSH 插件配置与命令）、
`docs/pmv-ppd-study.md`（ISO 7730 PMV/PPD 实测 + Sinergym 交叉核对）、
`docs/reference-repos-study.md`（评审 §6 的参考仓库：该套用什么、不该套用什么）。

## 2. 门禁与"绿"的定义

CI 共 4 个 job，**全绿才算过**（`main` 分支每次 push 都会跑）：

| job | 本地等价命令 | 期望 |
|---|---|---|
| Python tests & simulation smoke | `python -m pytest tests -q` | 退出码 0 |
| （同上） | `python -m energy_system.simulation.compare` | 退出码 0 |
| （同上） | `python -m compileall -q energy_system main.py api_server.py dashboard.py` | 退出码 0 |
| React lint & build | `cd app && npm run lint && npm run knip && npm test && npm run build` | 退出码 0 |
| Secret scan | （CI 用 gitleaks） | 无密钥入库 |
| **Firmware build** | 见 §4 | 退出码 0 |

> `knip`（死代码）与 `vitest`（前端单测）**是硬门禁**：knip 零豁免，vitest 当前 56 条。
> 本地 `python -m compileall` 在某些受限沙箱里会因**不可写 `__pycache__`** 而失败 —— 那是环境问题、
> 不是代码问题；以 CI 的编译检查为准，本地可用只读 AST 扫描替代。

## 3. 上板验收（拿到 ESP32-S3 之后）

```bash
python scripts/firmware_acceptance.py --port COM4                                  # 默认要求 bh1750
python scripts/firmware_acceptance.py --port COM4 --require bh1750,relay --active   # 再验证命令通道
```

退出码：`0` PASS / `1` NO_TOKEN / `2` SUBSYSTEM / `3` PORT / `4` BAD_INPUT（详见脚本 docstring）。

- 固件在 `setup()` 末尾打印自检令牌：`{"selftest":"pass","token":"ECO_SELFTEST_PASS",...}`
  （见 `firmware/esp32_s3_competition/protocol.h` 的 `printSelfTest()`）。**改动令牌字符串时，务必同步
  `scripts/firmware_acceptance.py` 的 `SELFTEST_TOKEN`** —— `tests/unit/test_firmware_acceptance.py` 会守这条契约。
- 命令通道：`GET_STATE` / `READ_SENSORS` / `PINMAP` / `I2C_SCAN` / `SELFTEST`
  （另有 `RELAY` / `BUZZER` / `CURTAIN OPEN|CLOSE|STOP|CAL` / `IR_NEC`）。
- 硬件诊断（人看得懂的摘要 + 接线建议）：`python scripts/hardware_autodiag.py --port COM4 --baud 115200`。
- 接线与供电：`docs/hardware-guide.md`（含引脚分配、I2C 地址、SPI 复用规则）。

## 4. 本地编译固件（工具链配方）

依赖（与 CI 一致，**请勿随意升降版本**）：

```bash
arduino-cli core install esp32:esp32@3.3.7
arduino-cli lib install PubSubClient
arduino-cli compile --fqbn esp32:esp32:esp32s3 firmware/esp32_s3_competition
```

- **为什么必须装 PubSubClient**：`config.h:66` 的 `#define USE_MQTT` 是**硬定义**，`:70` 直接
  `#include <PubSubClient.h>` ⇒ 硬依赖。
- **为什么只装它**：`DHT / SGP30 / ILI9341 / INA219 / XPT2046` 全部由 `__has_include` 保护
  （`config.h:19/26/33/41/48`），**缺失时编译期降级**。CI 故意不装它们，以守住"缺库也能编译"这一性质。
- ESP32 工具链约 600+ MB：网络慢时请提前下载；本机已装 Arduino IDE 时也可直接用 IDE 编译。

## 5. 必须保留的行为（改之前先读）

1. **离线可用**：后端不可达时用 mock 兜底渲染，不得变成空白/错误页（`app/src/store/useAppStore.ts:146-152`、`services/api.ts:42-44`）。
2. **连接态只在变化时提示**：toast 不能每次轮询都弹（`useAppStore.ts:157-161`）。
3. **AI 候选三态**与"**模型返回 ≠ 设备执行**"的语义必须保持区分（`app/src/types/index.ts:35,38-39`）。
4. **accept/reject 是本地乐观更新**，不发网络请求（`useAppStore.ts:164-182`）—— 改成写后端属行为变更。
5. 6 条路由与侧栏导航一一对应（`app/src/App.tsx:36-41`、`SideNav.tsx:15-22`）。
6. `SimulationPage.tsx:33-39` 的**确定性**预览是有意设计：**禁止改回 `Math.random()`**。
7. 传感器缺失必须在**编译期**降级；不要把 `__has_include` 保护改成硬依赖。
8. 指标/字段的键名以 `app/src/types/index.ts` 与固件 JSON 字段为契约，改名要**两处同时改**。

## 6. 明确不要做的事

- 不要重写 `energy_system/simulation/`：它是唯一的确定性回归基线。
- 不要把"编译检查"改成只打印不失败（门禁必须会使 CI 变红）。
- 不要在没有测试保护的情况下批量删除 `app/src/components/ui/`（先读 `docs/refactor-plan.md`）。
- 不要静默改动仿真基线数字：要改必须在测试/提交信息里**显式声明原因**。
- 不要把 `WIFI_SSID/WIFI_PASSWORD`（`firmware/esp32_s3_competition/mqtt.h`）等密钥写进仓库。

## 7. 目录速查与已知缺口

- `energy_system/` 分层：`domain/ core/ application/ hardware/ resilience/ utils/`（重构历史见 `docs/refactor-plan.md`）。
- `firmware/esp32_s3_competition/`：`protocol.h`（协议 + 自检）/ `sensors.h` / `actuators.h`（继电器·蜂鸣器·步进·按键）/ `display.h` / `mqtt.h` / `state.h` / `config.h` / `types.h`。
- 已知缺口（2026-10 记录，欢迎认领）：
  - 前端 `app/` **零测试**（改造前请先补最小 vitest 测试网）；
  - `config.h:66` 的 `USE_MQTT` 硬定义 ⇒ 未配置 WiFi 时上电会尝试连接并失败（是否改为可选待定）；
  - `docs/` 缺一份"重构设计书"（目标架构、门禁清单、必须保留/可安全重排两张清单）。
