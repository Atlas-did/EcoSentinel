# EcoSentinel 重构设计书 v1

| 项 | 内容 |
|---|---|
| 对象 | `Atlas-did/EcoSentinel`（public/MIT）。**基线锚点已对齐**：`origin/main` = `174cb5d`（2026-09-09 推送）；本设计书取证用的克隆 `_archive\ecosentinel` 即在 `174cb5d`；而工作副本 `D:\Temp_download\环境监测` 当时在 `c571f25`（**落后 1 个提交**，非领先），已于 2026-10-05 `git pull --ff-only` 对齐 |
| 撰写方式 | **只读取证**：克隆 → 装依赖 → 跑基线 → 静态分析（导入图/涟漪因子/时序热点）。**未改动任何项目文件** |
| 诉求（你的原话） | ① 感觉代码不干净 ② 结构乱/耦合重、加新功能慢 ③ 性能或可靠性（采集/控制/告警延迟）④ 固件没有门禁、怕上板翻车 |
| 本版结论 | **不建议"完全大重构"**；建议 **3 道门禁 + 4 条主线** 的增量重构（详见 §0 与 §4） |

---

## §0 结论摘要（先看这段就够）

### 0.1 为什么**不建议**再大重构一次

1. **这已经不是第一次重构了**：`docs/refactor-plan.md` **51.7 KB**（P0–P11）+ `docs/refactor-baseline.md`；
   `application/runtime.py` 的 docstring 明写「从 `main.py` 拆出，让循环可无副作用导入、各服务可独立测试」。
   **再来一次"完全重构"= 第二次重写**，把上一轮已验证的分层推倒。
2. **项目不脏，脏的是几个具体位置**（§2 全部带 `file:line`）：分层命名（`domain/core/application/hardware/resilience/utils`）已经成立，
   **循环导入 0 对** —— 结构骨架是好的。
3. **你有 148 条测试在 3.47 秒里全绿**（实测）+ 一条确定性仿真回归（CI 里那条，退出码 0）。
   大重构会让这 148 条（=你现在唯一的行为规格）大规模作废或重写，换来的收益不确定。
4. **真正的风险不在"结构"，而在"没有门禁"**：固件从未被编译过（§2-P3）、控制回路里没有延迟预算断言（§2-P2）。
   这两件事**不修**，无论重构与否都会在上板那天翻车。

### 0.2 建议做三件事（按投入产出排序）

| # | 门禁 | 成本 | 收益 |
|---|---|---|---|
| **G1** | **固件编译进门禁**（`arduino-cli compile` for ESP32-S3） | 半天 | 把"能不能编译"从人工变成常驻；直接消除"上板翻车"的第一类原因 |
| **G2** | **行为基线快照**（148 测试 + 仿真输出数字 + 一份 golden） | 半天 | 之后**任何**重构都有回滚网；这是"敢重构"的前提 |
| **G3** | **主回路延迟预算断言**（AI 不得在采集/控制路径上阻塞超过 X ms） | 1 天 | 把"延迟痛点"变成会变红的测试，而不是靠感觉 |
| **G6** | **前端最小测试网**（vitest，覆盖 store 纯逻辑） | 1 天 | 前端当前 **0 测试**，而 M6 要删 61% 死代码 —— **没网就删代码是赌博** |

### 0.3 四条主线（在 G1–G3 之后按此顺序做，每步可回滚）

**M1 遥测模型化**（治"加新功能慢"）→ **M2 AI 出主回路**（治延迟）→ **M3 配置/环境收敛**（治"不干净"）→ **M4 编排器拆分**（治扇出 12）。
**M6 前端瘦身与契约单点化可全程并行**（不同目录、无冲突），且它是**最便宜的早期收益**：删掉 61% 死代码不需任何设计决策。

> 原则：**先立门禁，再动结构；每一步都让 148 条测试保持全绿；每步一个可回滚提交。**
> 前端在补测之前**先别删代码**（G6 必须先于 M6.2）。

---

## §1 现状基线（全部为本次实测，命令见附录 A）

### 1.1 结果级基线

| 项 | 实测 |
|---|---|
| 单元 + 契约测试 | **148 passed / 3.47 s / 退出码 0** |
| 确定性仿真冒烟（CI 同款） | 退出码 0；输出可读指标（碳减排 20.03 kgCO₂、舒适度 49.3%）⚠️ 2026-10 更正：旧值 13.87/82.1% 来自发散的热模型 |
| CI | 3 job 全绿（Python 测试 + `compileall` + 仿真冒烟、React lint/build、gitleaks） |

### 1.2 代码规模

| 区域 | 文件 | 行数 |
|---|---|---|
| `app/`（React/TS） | 77 | 9685 |
| `energy_system/`（Python 核心） | 67 | 6164 |
| `tests/` | 21 | 1759 |
| `firmware/`（ESP32-S3 Arduino） | 9 | 1277 |
| `dashboard/`（Streamlit） | 8 | 745 |
| `scripts/` | 7 | 714 |
| 根 `dashboard.py` / `api_server.py` / `main.py` | 3 | 462 |

### 1.3 Python 内核分层（`energy_system/`）

| 层 | 文件 | 行数 | 评价 |
|---|---|---|---|
| `core/`（时钟/命令/控制/采集/审计/日志） | 11 | 1048 | 骨架合理，单一职责清晰 |
| `config/` | 3 | 501 | 被 6 个模块依赖（**依赖面最大的模块**） |
| `hardware/`（串口/MQTT） | 3 | 561 | 与设备强耦合，属预期 |
| `application/`（编排） | 6 | 489 | **`runtime.py` 扇出 12 → 上帝编排器** |
| `ai/` + `algorithms/` | 11 | 911 | AI 服务与顾问分离 ✓ |
| `resilience/` | 4 | 380 | 有节流/自愈策略 ✓ |
| `simulation/` | 3 | 300 | 确定性回归的来源 ✓ |
| 其余（domain/models/utils/persistence/power/api/cli/experiments） | — | ~1500 | 体量合理 |

### 1.4 导入图（67 模块 / 34 个有内部依赖）

- **循环导入：0 对**（无相互 import）⇒ **增量重构是安全的**，这是本设计书最重要的前提。
- **扇入 Top**：`config`(6)、`core.models.commands`(6)、`config.runtime_config`(4)、`persistence.jsonl_repository`(3)、`domain.metrics`(3)
- **扇出 Top**：**`application.runtime`(12)**、`ai`(7)、`ai.service`(6)、`core.control.actuation`(5)、`simulation.*`(5)

---

## §2 四个痛点的根因（每条都有可复核证据）

### P1 「结构乱 / 耦合重 / 加新功能慢」——根因不是"乱"，是**指标不是数据**

**量化证据（涟漪因子）**：一个指标名在仓库里被硬编码到多少处：

| 指标 | 命中 | 跨文件 |
|---|---|---|
| `temperature` | 52 处 | **27 个文件** |
| `humidity` | 60 处 | **20 个文件** |
| `co2` | 32 处 | **16 个文件** |
| `occupancy`（最新、未铺开） | 1 处 | 1 个文件 |

⇒ **加/改一个指标要碰 16–27 个文件**，这就是"加新功能越来越慢"的机制性原因：
遥测以**松散 dict 键**在各层之间流动（`core/data_acquisition.py` → `application/enrichment.py` → `application/decision.py` → `core/log_manager.py` → `api/` → 前端），
没有一处**类型化的遥测模型**作为单一真值。

**次要证据（编排器扇出）**：`energy_system/application/runtime.py` **282 行、扇出 12**，一个构造函数里手工装配 9 个服务
（`SerialBridge` / `DataAcquisition` / `AIAdvisor` / `RuleBasedController` / `RuleActuationController` /
`TelemetryEnrichmentService` / `DecisionService` / `LogManager` / `ResilienceOrchestrator`，见 `runtime.py:50-125`），
并**直接读环境变量**：`runtime.py:104-105` 的 `os.getenv("BATTERY_CAPACITY_MAH")` / `os.getenv("BATTERY_INITIAL_SOC")`
（应用层读 env ⇒ 配置边界泄漏，也让该模块难测）。

### P2 「性能 / 可靠性（采集、控制、告警延迟）」——根因是**AI 在同步主回路上**

主回路 `runtime.py:131-174` 的实际顺序：

```
while running:
    sensor_data = acquisition.read()       # 阻塞读取(串口 timeout=1s, serial_bridge.py:171)
    ...enrichment.enrich(...)              # 计算指标
    self._run_ai_cycle(sensor_data)        # ← 网络调用就在这一行, 同步等待
    if ... and not safe_mode:
        self.actuation.apply(sensor_data)  # ← 控制动作排在 AI 之后
    ...log...
    next_tick = self.scheduler.wait_until_next_tick(next_tick, 5.0)   # 名义周期 5.0 s
```

**证据链**：
1. AI 客户端带超时与**指数退避**：`algorithms/ai_advisor.py:178`（`timeout=candidate.timeout_s`）、
   `ai_advisor.py:224`（`time.sleep(0.4 * (attempt + 1))`）。
2. 同一条线程上有串口阻塞读：`hardware/serial_bridge.py:171`（`timeout=1`）、`serial_bridge.py:189/204/225`
   （连接与重连各 `sleep 0.2 s`、退避 `1.0*(attempt+1)`）。
3. 一旦某轮超时，调度器**只打印告警、不做补偿**：`application/scheduler.py` 的
   `wait_until_next_tick()` → `logger.warning("Loop overrun by ...")`，随后**下一个 tick 仍按原节奏推进**。

⇒ 后果：**告警/控制延迟 = AI 最坏耗时（可数秒~数十秒）× 重试次数**；
采集也被同一线程拖住；`overrun` 只是日志，不会触发降级。
这与你的诉求③完全对应，且**是结构问题、不是硬件问题**。

### P3 「固件没有门禁、怕上板翻车」——固件从未被编译过

- CI 的"编译检查"是 `python -m compileall -q energy_system main.py api_server.py dashboard.py`（`.github/workflows/ci.yml`），
  **完全不覆盖 `firmware/`**；工作流自己的注释也写着 "firmware build matrix … added later"。
- 固件是 **Arduino `.ino` + 8 个头文件**（`firmware/esp32_s3_competition/`，共 1277 行）：
  `protocol.h`(10.7 KB) / `sensors.h` / `actuators.h` / `mqtt.h` / `display.h` / `state.h` / `config.h` / `types.h`。
  `.ino` 只保留 `setup()`/`loop()`（`.ino:34/121`），行协议 `Serial.readStringUntil('\n')`（`.ino:138-139`）。
- 测试侧只有 `tests/contract/test_api_schema.py`（**API schema 契约**），**没有"主机解析 ⇄ 固件协议"的契约测试** ✗。

⇒ 三类上板翻车原因目前**全都不可见**：① 编译不过（API 版本差异，如 ESP32 core 2.x→3.x 的 `ledcSetup`→`ledcAttach`）；
② 协议字段/单位不一致（`protocol.h` 与 `hardware/serial_bridge.py` 各写一份）；③ 实机时序（看门狗、`loop()` 周期）。

### P4 「感觉代码不干净」——不是全局脏，是**三类局部异味**

| 异味 | 证据 | 影响 |
|---|---|---|
| 环境变量来源分散 | `os.getenv/os.environ` 共 10 处 / 3 文件：`runtime.py:104-105`、`cli/run_edge.py:73-75`（**3 个不同的 API key 变量名** `DEEPSEEK_API_KEY`/`OPENAI_API_KEY`/`AI_API_KEY`）、`utils/env_loader.py:28/41` | 配置真值不唯一；测试需 monkeypatch env |
| 加载器有全局副作用 | `utils/env_loader.py:41` 直接写 `os.environ` | 导入即改进程状态，违背 `runtime.py` docstring 宣称的"无副作用可导入" |
| 路径/工厂不一致 | 根目录同时存在 `main.py`(21 行) / `api_server.py`(69) / `dashboard.py`(372) 与 `dashboard/` 包（745 行） | 新人（或下一个代理）难以判断"从哪进" |

> 结论：**P4 是"整理"级别的活**（M3），不构成重写理由。

### P5 前端（`app/`）：证据最充分、**风险却最高**的一块（详见附录 B）

前端**不是**"分层混乱"：zustand 单 store、**全项目唯一一处 `fetch`**、7 个端点收敛在 `api.ts`、类型集中在 `types/index.ts` ✓。
真正的问题有四类，全部有 `file:line`：

| 类别 | 证据 | 严重度 |
|---|---|---|
| **契约有三份副本** | 指标键集重复 3 次（`SensorChart.tsx:138-225`、`RealtimePage.tsx:19-23`、`HealthPage.tsx:23-30`）+ mock 生成器**又一份**（`api.ts:86-245`）+ 字段直读 **30+ 处** ⇒ 改后端字段名 **tsc 不报错、静默失效** | 高（对应痛点①④） |
| **61% 的 src 是死脚手架** | `components/ui/` **51/53 文件、5954 行不可达**（本设计书已独立复核：22 处 ui import 中 20 处是 ui→ui 内部） | 高（对应痛点①"不干净"） |
| **零测试** | 无测试文件/脚本/依赖/覆盖率（0%）；且 `useAppStore.ts:91-96` **import 期即执行 `Math.random`**、`api.ts:38` 直接调 `window.fetch` ⇒ **无注入缝** | 最高（重构的安全网为零） |
| **已确认缺陷 3 个** | ① `PrecisionKnob.tsx:55/:61` `pointerup` 监听**永不解除**（真泄漏）；② `EnergyAnalysisPage.tsx:229` `?? /` 优先级 ⇒ **÷20 从未生效**；③ `EnergyAnalysisPage.tsx:30-31` 依赖仅 mock 产出的字段 ⇒ **接真实后端时累计曲线恒为 0** | 中–高（用户体验可见） |

还要一条**行为契约不一致**：`types/index.ts:15,19`（relays/errors）暗示推送式契约，但全 `src` **无 WebSocket/EventSource**，
"实时"完全靠 3 s 轮询 ⇒ 契约与实现不符（需与后端确认哪个为准）。

> 判定：前端要做的**不是重构，而是"删 + 单点化 + 补测"**（B.8 的 15 条，多为机械动作）✓
> 且**越早删掉那 61% 越安全**（剩余代码越小，补测越便宜）。

---

## §3 目标架构（保留现有分层，只补三条边界）

### 3.1 依赖方向（唯一的硬规则，可自动检查）

```
                 ┌───────────────┐
   adapters ───▶ │ application   │ ───▶ domain / core
 (cli, api,      │ (用例编排)     │        ▲
  hardware,      └───────────────┘        │  只允许向下依赖
  dashboard)                              │
                 ┌───────────────┐        │
                 │ core          │ ───────┘
                 │ (策略/算法/时钟)│
                 └───────────────┘
   domain  ← 谁都可以依赖它；它不依赖任何人
   config  只被最外层读（见 M3），不再被 6 个模块各自解释
```

**新增可自动检查的规则**（放进 CI，一条 grep/import-lint 即可）：
1. `domain/` 不得 import `core/`、`application/`、`hardware/`、`config/`；
2. `core/` 不得 import `application/`、`hardware/`、`cli/`、`api/`；
3. `application/` 不得 import `hardware/` 的**具体实现**（只依赖接口/协议）；
4. **任何模块不得直接 `os.getenv`**（只允许 `config/` 层，M3 后加断言）。

### 3.2 三条新边界（对应四个痛点）

| 边界 | 现在 | 目标 | 治哪个痛点 |
|---|---|---|---|
| **B1 类型化遥测** | 松散 dict 键跨 16–27 文件 | `Telemetry`（dataclass/typed dict）+ `METRICS` 注册表；各层只依赖模型，新增指标只改**模型 + 注册表 2 处** | P1（加新功能慢） |
| **B2 AI 出主回路** | AI 与采集/控制在同一线程同步 | 采集/控制/告警回路**永不被网络阻塞**；AI 走 worker + 有界队列；结果**带时效**（过期即弃）；`suggest`/`execute` 语义不变 | P2（延迟） |
| **B3 协议单一真值** | `protocol.h` 与 `serial_bridge.py` 各写一份 | 一份机器可读的协议定义（字段/单位/行格式/校验），**生成**或同时被两端断言；加契约测试 | P3（上板翻车） |

> **明确不做**：不换语言、不换框架、不合并 `app/` 与 `dashboard/`、不引入 ORM/消息中间件、不重写仿真内核（它是你唯一的回归基线）。

---

## §4 迁移计划（M0–M6：每步都可独立回滚）

> 每步的**通用验收**：`pytest tests -q` 148 条全绿 + `python -m energy_system.simulation.compare` 输出**逐位不变**（除非该步明确声明要改数字）。
> 每步一个提交，提交信息写明"本步验收命令与结果"。

### M0 · 门禁（先做，半天）—— 见 §5 的 G1/G2/G3（前端门禁 G6/G7 是 M6 的前置）

**验收**：CI 出现 3 个新 job/步骤且**故意破坏时变红**（变异验证）；给出修前/修后两次输出。

### M1 · 遥测模型化（1–2 天，治 P1）

1. 新增 `domain/telemetry.py`：`Telemetry` 模型 + `METRICS` 注册表（名称、单位、量程、默认缺失策略）。
2. **只加不改**：先提供 `Telemetry.from_dict()/to_dict()` 适配现有 dict 路径，**保持所有调用方不变**（148 条测试必须仍绿）。
3. 再逐层替换：`data_acquisition` → `enrichment` → `decision` → `log_manager` → `api`，每层一个提交。

**验收**：新增一个"测试用指标"（例如 `pm25`）**只需改 2 个文件**（模型 + 注册表），并有测试证明它自动流经落盘/API；
涟漪因子从 16–27 降到 ≤3（可用同一段统计脚本量化，见附录 A）。

#### M1 实施记录（第一片，2026-10-05，提交 2211765）

- **涟漪基线重测（119 个源文件，含前端与固件）**：`temperature` **31 个文件**、`illuminance` 28、
  `humidity` 25、`power_w` 19、`eco2` 19、`comfort_score`/`solar_power_w` 12、`tvoc`/`bus_v` 11
  —— 比 §2 里"16–27"更糟（那是 Python-only 口径）。
- **已落地**：`domain/telemetry.py`（`MetricSpec` + 三类注册表共 25 个**真实**字段 + `ALIASES` +
  `unit_of` + **`set_metric`（键名拼错立刻抛错）** + `WIRE_FIELDS`（固件线上名 → 规范键 + 换算系数））；
  `application/enrichment.py` 的 6 处字面量赋值改为 `set_metric`。
- **契约门禁**（`tests/contract/test_metrics_registry.py`，10 条）：API schema（`Snapshot`/`ChartPoint`）、
  **固件传感器帧**（限定 `replySensorsJson`，且同时收 `Serial.print("\"k\":")` 与 `jsonPrint*(...)` 两种写法）、
  前端 TS 接口（`SensorSnapshot`/`ChartDataPoint`）的字段必须都已登记；另有一条**可执行**的换算校验
  （`estimate_power_w({"pwr_mw": 1500}) == 1.5`）。**变异验证**：往 `Snapshot` 塞未登记字段 ⇒
  门禁指名 `probe_unregistered_metric` 变红 ✓。
- **顺带核实（不是 bug）**：固件以 `pwr_mw`/`solar_pwr_mw`（毫瓦）上报，而 API/前端是
  `power_w`/`solar_power_w`（瓦）—— 换算确实存在（`EnergyAccumulator.estimate_power_w`: `/1000`
  或 `V×I/1000` ✓），只是此前**无处可查**；现已登记进 `WIRE_FIELDS` ✓。
- **待续**：把 Python 侧其余读取点也改为经注册表（当前只做了"写入侧"），届时涟漪才会真正降到 ≤3。

### M2 · AI 出主回路（2–3 天，治 P2）

1. 抽出 `application/loop.py`（节拍）+ 把 AI 调用移入 `ai/worker.py`（独立线程 + `queue.Queue(maxsize=1)`：**只保留最新一次请求**）。
2. 主回路每周期只做：`read → enrich → (rule actuation) → log → 取 AI 最新建议(非阻塞)`。
3. 建议**带时效**（`issued_at`），超过 `ai_max_age_s` 直接丢弃并记录 `dropped_stale_advice`。
4. `ai.control_mode == "execute"` 时，AI 建议仍要经过**原有规则/安全闸门**（保持 `command_policy` 语义不变）。

**验收**：G3 的延迟断言——**人为让 AI 慢 10 s，采集周期与告警延迟不变**（新测试）；
仿真冒烟数字不变；`overrun` 告警在 AI 慢时不再出现。

#### M2 实施记录 + G3 落地（2026-10-05，提交 84f7586）

- **先写会失败的测试（G3）**：`tests/unit/test_loop_latency_budget.py`。用仓库既有的 `FakeClock`
  + 可注入 `Scheduler` 把时间虚拟化，让"AI 每次 10 秒"，实测结果：
  **虚拟 60 秒内只跑 7 轮**（应 12），且 `Loop overrun` **逐次累积 5→10→15→20→25→30 s** ——
  即"AI 慢"不是"每轮慢一点"，而是**节拍持续塌陷、永不追回**，而 `scheduler.py:32` 只打印告警。
- **实现**：新增 `energy_system/application/ai_worker.py`（`AiWorker` + `ThreadJobRunner` 默认 /
  `ManualJobRunner` 供确定性测试）：
  `submit`/`poll` 非阻塞；**至多一个在途任务**，更新的请求只进 1 槽信箱（顶掉旧待办）⇒ 无界积压不可能；
  建议按**请求时刻**计龄（`AI_ADVICE_MAX_AGE_S = 10.0` = 2× 周期），过期一律丢弃、绝不驱动硬件；
  AI 侧异常被隔离（`errors` 计数）且失败后可继续提交。
  `runtime.py` 主回路改为 `_apply_ai_advice()`（先落地上一轮未过期建议）→ `_request_ai_cycle()`（再发起异步计算）；
  循环周期提为 `loop_interval_s` 属性。
- **验收**：G3 断言转绿（12 轮、零 overrun）；全量 **173 passed**（原 164 + 新 9）；
  仿真基线**逐位不变**（**现行值**：碳减排 20.03 kgCO₂、舒适度 49.3%；2026-10 修好热模型积分后由 13.87/82.1% 更新）。
- **两条防假绿断言**（写进测试）：① AI 确实被调用过（否则"节拍正常"是假象）；
  ② AI 建议**最终确实进入日志管线**（异步化不等于把 AI 丢掉）。
- **本地环境注记**：`python -m compileall` 在本机因沙箱不可写 `__pycache__` 而**必然失败**（四个目标
  全部同样的 PermissionError，含未改动的 `main.py`）⇒ 本地等价验证改用**只读 AST 扫描全仓**（0 语法错误）；
  真正的 compileall 由 CI 跑（Linux runner 可写）。

### M3 · 配置/环境收敛（1 天，治 P4）

1. `config/` 成为**唯一**读 env 的地方；`runtime.py:104-105`、`cli/run_edge.py:73-75` 的读取上移。
2. `utils/env_loader.py` 不再直接写 `os.environ`（改为返回 dict，由 `config` 层合并）。
3. 保留 3 个 API key 变量名作为**兼容别名**，在 config 层归一为一个字段（避免破坏现有部署）。

**验收**：§3.1 规则 4 的断言通过（`grep -r "os.getenv" energy_system --include=*.py` 只命中 `config/`）。

#### M3 实施记录（2026-10-05，提交 75fb6c8）

- **验收达成**：全仓 `os.getenv`/`os.environ` 的**实际用法**只剩 `energy_system/config/env.py`
  （另有两处命中是**文档里在陈述这条规则**本身，不是使用）。
- **实现**：新增 `config/env.py`（唯一门面：`apply_dotenv` 首写胜 / `env_value` / `ai_api_key`
  别名优先级 DEEPSEEK>OPENAI>AI / `battery_capacity_mah` / `battery_initial_soc` / `cors_origins_override`；
  数值解析失败**告警并回退默认值**，此前 `float()` 会直接抛异常 ✗）；
  `utils/env_loader.py` 变为**纯解析器**（不再碰 `os.environ`，删掉 `load_file`/`load_dotenv_if_present`）；
  消费方 `runtime.py` / `cli/run_edge.py` / `api_server.py` / `scripts/test_deepseek.py` 全部改走门面
  （后者还删掉了一整份重复的 `.env` 解析器 + 别名链）。
- **门禁**：`tests/unit/test_env_config.py`（11 条）含一条**AST 结构门禁** —— 除 `config/env.py` 外
  任何模块出现 `os.getenv`/`os.environ` 即失败（AST 避免注释/文档误报）。
  **变异验证**：往 `runtime.py` 注入 `os.getenv('X')` ⇒ 门禁指名 `runtime.py:323` 变红 ✓。
- **验证**：全量 **184 passed**（原 173 + 新 11）。

### M4 · 编排器拆分（1–2 天，治 P1 次要项）

把 `runtime.py`（282 行 / 扇出 12）拆为：`wiring.py`（装配与依赖注入）、`loop.py`（节拍与主循环）、
`usecases.py`（`no_data` / `heal` / `ai_cycle`），`EnergySystemApp` 仅保留对外门面（保持 `main.py` 的 re-export 兼容）。

**验收**：`runtime.py` 扇出 ≤5；`modules_count`/导入图脚本输出对比；148 测试全绿。

#### M4 实施记录（2026-10-05，提交 2fc12ff + 5bf77fa）

- **拆分结果（全部逐字搬迁、零行为改动）**：

| 模块 | 行数 | 内部依赖 | 职责 |
|---|---|---|---|
| `application/runtime.py` | 325 → **64** | 15 → **2** | 门面：`EnergySystemApp`（公开属性与拆分前完全一致）+ `run()` |
| `application/loop.py` | 新增 74 | 2 | 主回路节拍（logger 文案/KeyboardInterrupt/tick 计算原样） |
| `application/usecases.py` | 新增 149 | 3 | 无数据/自愈/同步/AI 周期/落盘（只依赖 app 公开属性 ⇒ 可单测） |
| `application/wiring.py` | 新增 164 | 14 | **组装根**：唯一认识具体适配器的地方 |

- **验收达成**：四个模块扇出全部 ≤5 ✓；`main.py` 的 re-export 实测可用 ✓；
  全量 **200 passed** ✓；仿真基线逐位不变 ✓；G3 的"12 轮 / 零 overrun"仍绿 ✓。
- **一处对本文档自身的更正**：G4 记录里写的"唯一例外 `application → hardware`"**是错的** ——
  按层级秩 `hardware` 是叶子(7)、`application`(2) 依赖它是**向内**，本就不违规；那条"例外"
  一直空转（旧检查只看边是否存在，不看它是否真违规）。现已把 `COMPOSITION_ROOT_FILES` **清空**
  （门禁零豁免 ✓），并保留"豁免必须仍然需要"的自检 —— 正是这条新自检当场抓出了空转条目 ✓。
- **迁移副作用（已按需修好）**：测试的 patch 目标必须跟着代码搬家（`wiring.LogManager`、
  `usecases.append_jsonl`、`usecases.time`），三处修完即绿 —— 这反过来证明搬迁是真的。

### M5 · 固件协议契约（1 天，治 P3）

1. 抽出 `protocol/eco_protocol.yaml`（或 `.h` 生成源）：字段名、类型、单位、行格式、错误码。
2. 主机侧解析器与固件 `protocol.h` 都由它**生成或断言**；加 `tests/contract/test_serial_protocol.py`（含边界：截断行、超长行、非法数字、未知字段）。
3. 固件编译 job（G1）纳入同一提交。

**验收**：故意把协议字段单位从 `0.1°C` 改成 `°C`（只改一端）时，契约测试**变红**。

#### M5 实施记录（2026-10-05，提交 457ecfc）

- **单一真值**：`protocol/eco_protocol.yaml` —— 传输参数（含 `max_frame_bytes: 4096`，此前主机侧**没有任何上限**）、
  回复形状、**11 条命令**（含 `match: exact|prefix`、参数形状、回复令牌）、错误令牌、以及传感器帧
  14 个字段的 wire→canonical + unit + scale；`hardware/protocol_contract.py` 是加载器（缓存 + 缺文件兜底），
  **主机行为由清单驱动**（`serial_bridge.parse_sensor_line` 的超长帧丢弃取自清单）。
- **双侧门禁** `tests/contract/test_serial_protocol.py`（18 条）：固件侧（清单命令必须有分发、固件分发必须都在清单、
  回复令牌双向一致、帧字段双向一致、**同一命令不得同时存在 exact 与 prefix 两种分发**）+
  主机侧（真实函数、无需硬件：合法帧→sensor、ack→ack、截断/非 JSON/`DHT_`→None、未知字段容忍、
  非数字不崩、超长帧拒收/临界长度收下）+ 换算一致性（清单 ⟷ `WIRE_FIELDS` ⟷ 实现实算）。
- **清理**：删掉我在 H3 误加的 4 条 `startsWith` 重复分支中的最后 2 条 —— `READ_SENSORS`/`GET_STATE`
  原本由 `line == "X"` 精确匹配处理，`startsWith` 版**永远不可达**；只保留 `SELFTEST`（确实没有精确匹配版）。
- **三条变异验证**：① 清单只把 `scale: 0.001` 改成 `1.0` ⇒ 换算一致性红；
  ② 固件多发一个字段 ⇒ 帧字段一致性红；③ 把 `GET_STATE` 死分支加回 ⇒ 重复分发规则点名 `GET_STATE` 红。
- **顺带修正**：`test_layering` 的叶子集合去掉 `hardware`（`protocol_contract` 需要 `utils.logger`，属向内依赖）。

#### M6.3 实施记录（第一片，2026-10-05，提交 1d02f02）

- **新增** `app/src/lib/metrics.ts`：9 个 `ChartDataPoint` 指标的 label/unit/color/icon/threshold/
  `defaultActive`/**`anomalyWatch`**/`thresholdNote` + `isAnomalous`/`anomaliesOf`/`defaultActiveSensors`。
- **阈值统一（用户决策）**：`METRICS.eco2.threshold = 1000` —— 页内原先显示用 1200、异常判定用 >1000，
  现统一为 **1000 ppm**（通风/投诉阈值，且与异常判定原值一致）。
  ⚠️ 关键设计：**阈值可以统一，但"监视哪些指标"是行为** ⇒ 用独立开关 `anomalyWatch` 保持与重构前一致（仅 temp+eco2）。
- **`RealtimePage`**：`sensorConfigs` 改由表派生；异常判定改用 `anomaliesOf`（与阈值同源）；默认开关改用
  `defaultActiveSensors()`；图标不再各自 import；两处 `value > threshold` 补 null 守卫（`tsc` strict 抓出）。
- **两处对本文档/早先说法的更正**：
  1. `HealthPage.sensorIcons` **不是**同一份键集的第三份 —— 它用的是后端 `SensorHealth` 的开关字段
     （`temperature`/`power`/`solar`…），属**另一个命名空间**，故不并入指标表；
  2. `SensorChart` 的 9 个 `dataKey` 是 **recharts 必需的字符串字面量**，无法靠表消除 ⇒ 本轮只消除
     "键集 + 元数据"的重复，未动 `SensorChart`（如实记录，而非宣称已完全单点化）。
- **G8 门禁**（放在 Python 侧 —— 浏览器 tsconfig 无 node 类型，vitest 里读文件会让 `build` 失败，已实测）：
  `tests/contract/test_metrics_registry.py::TestFrontendSingleSource` —— 三个页面不得出现 `threshold:` 声明
  或指标键字面量；且前端指标表必须覆盖后端 `ChartPoint` 的数值字段。
  **变异验证**：往 `RealtimePage` 注入 `{ threshold: 1200 }` ⇒ 门禁指名该文件变红 ✓。
- **验证**：Python **221 passed**；前端 **33 passed** + lint/build/knip 全 exit 0。

#### M6.3 实施记录（第二、三片，2026-10-05，提交 e73e13c + 4397787）

- **图表渐变色收口（e73e13c）**：发现表与图表有**两处颜色漂移**（`solar` 图表用 `#eab308`、
  `baseline` 用 `#94a3b8`，而表里写的是 `#22c55e`/`#64748b`）⇒ **以图表（渲染真相）为准对齐表**，
  不为"统一"而改变视觉；`SensorChart` 的 7 条 `<linearGradient>` 由 14 处 `stopColor` 字面量
  改为表驱动。门禁：图表不得再出现硬编码 `stopColor` 十六进制（变异验证 ✓）。
- **阈值全面收口（4397787）**：新增 `exceedsThreshold()`（`isAnomalous` 复用之）+
  **`SNAPSHOT_ALERTS`**（快照命名空间：`temperature` >30、`soc_percent` **<20（方向相反！）**、
  `eco2` >1000）+ `isSnapshotAlert()` + `TARGET_TEMP_C`。关键设计：**阈值统一必须带方向**
  （电量是"低于"告警），行为用 `direction` 字段显式表达。
- **门禁当场抓出 3 处我漏掉的内联阈值** ✓：`DashboardPage:137`（`eco2! > 1000`）其实是我在设计书里
  只记了两处中的一个漏项 ✗，而 `RealtimePage:178/181`（`a.temp > 30`、`a.eco2 > 1000`）是我**先前完全没看到**的
  ✓ —— 三条内联阈值全部收口。这条"内联阈值比较"门禁（扫描前剥离注释 ✓，注释里举例旧代码不算违规 ✓）
  是这轮最有价值的产出。另补：快照告警表的键必须来自后端 `Snapshot` 字段 ✓。
- **验证**：Python **225 passed**；前端 **38 passed** + lint/build/knip 全 exit 0；
  变异验证：把判定函数写回内联比较 ⇒ 门禁点名 `DashboardPage.tsx` 变红 ✓，还原后绿 ✓。

#### M6.6 实施记录（进行中，2026-10-05，提交 b261021 + bde39c6）

- **修掉一个潜在缺陷**（前端证据包风险 E）：`SensorChart` 的 7 条 `<linearGradient>` 用固定 id
  （`colorTemp`…）⇒ **同页两个图表实例**时，后渲染的定义会遮蔽前一个，前一个图表填充色错乱。
  改为 `useId()` 前缀（去掉冒号以免 CSS 选择器不安全），7 处 `fill="url(#...)"` 同步模板化
  —— "改 id 忘改引用"正是"渐变不显示"的常见成因。
- **新增** `SensorChart.test.tsx`（4 条）：id 前缀化、**两实例同系列时 id 不重复**、颜色取自表、
  隐藏系列不产生渐变。⚠️ **首版测试有洞**：两个图表渲染的是**不同**系列，退回固定 id 也不会重复
  ⇒ 门禁空转；改成同系列后变异验证才真的红（2 条失败）✓。
  **教训（值得复用）：门禁必须在"退回旧实现"时确实变红，否则只是装饰。**
- **新增** `services/api.test.ts`（6 条）：非 2xx / 网络异常 ⇒ `null`；
  **超时后中止并返回 null，且超时必须小于轮询间隔**（假定时器行为化验证 —— `2500` 改回 `5000` 就红 ✓）；
  端点契约（`/api/chart` 带 `range`、`/api/snapshot`）。
- **验证**：前端 **48 passed**（33 → 48）+ lint/build/knip 全 exit 0；Python 保持 **225 passed** ✓；
  两处变异验证均通过 ✓。过程里 `tsc` 又抓出我自己两处类型错误（`vi.fn(handler as never)` 污染返回类型、
  SVG 属性名应为 `stop-color`）—— 再次印证"测试代码同样要过类型检查"这条纪律。

### M6 · 前端瘦身与契约单点化（**可与 M1–M5 并行**，治痛点①④；2–3 天）

> 前置：先跑通 `npm ci && npm run build && npm run lint`（子代理**未能**验证这三条，见 B.10-①②③）——
> 若 build 本来就红，先修红再谈重构。

| 步骤 | 内容 | 验收 |
|---|---|---|
| **M6.1 固化现状** | 记录 build/lint 结果、包体大小、页面清单 | 三条命令的原始输出 |
| **M6.2 删死代码** ✅**已完成**（提交 `4eb1b01`） | 实际删除 **53 文件 + 38 依赖 + 4 个死 store 成员** | `npm run build`/`lint`/`test`/`knip` 全 exit 0；**src 9661 → 3787 行（−61%）**；`dependencies` 49 → 13 |
| **M6.3 契约单点化** | B.8 的 5/6/13（三份键集合一、抽 `lib/format.ts` 与 `PageHeader`、阈值上提并**先定夺 `RealtimePage:19-23` vs `:50` 哪个对**） | 故意改一个指标键名 ⇒ **只需改 1 处**，且 `tsc` 报错（不再是静默失效） |
| **M6.4 修 3 个确认缺陷** ✅**已完成**（`0d392e5` + `e608266`） | ① `PrecisionKnob` 监听泄漏（身份断言 + 变异验证 ✓）② `??` 优先级导致 ÷20 从未生效（抽成纯函数 `treesEquivalent` ✓）③ 累计曲线依赖后端不产出的字段 ⇒ 按选定方案 A **如实显示"不可用"**（并顺带把该页 O(n²) 改为前缀和 + `useMemo` ✓） | 前端测试 11 → 21；四处门禁全绿 |
| **M6.5 可靠性不变量** ✅**已完成**（`8f7db06`） | ① 超时 5000ms → **2500ms**（必须小于 3s 轮询间隔）② 移除"最后写入者胜"的模块级离线标志 ⇒ 改为**整轮聚合**（全失败才离线）③ `refreshData` 加 in-flight 去重 ④ `setTimeRange` 只拉图表端点 | 前端测试 21 → 25；新增 4 条不变量用例（旧实现天然失败 ⇒ 即回归证明） |
| **M6.5 可靠性不变量** | B.8 的 10/11（in-flight 去重、连接态按轮聚合、`setTimeRange` 只拉 chart） | 新测试：慢后端下**批次不重叠**；单个端点失败**不**误导"后端未连接" |
| **M6.6 最小测试网** 🔄**进行中**（`b261021` + `bde39c6`） | 已做：`SensorChart` 渲染契约（含修掉渐变 id 冲突）+ `services/api.ts` 契约（失败/超时/端点）；待做：`services/http.ts` 可注入抽象 | 前端 33 → **48 passed**；两处变异验证通过 ✓ |

**验收总则**：B.7 的 **13 条行为必须逐条仍然成立**（尤其 §7 的离线可用、连接态只在变化时提示、本地乐观裁决）。

---

## §5 门禁清单（G1–G8：重构的"安全带"，先于一切结构改动）

> 判定原则（沿用你仓库 CI 现有的风格，并补一条）：**门禁必须"会变红"才算门禁**。
> 每条门禁都要附一次**变异验证**：故意破坏 → 门禁变红 → 还原 → 变绿。

### G1 · 固件编译门禁（治 P3 第一类风险）

`.github/workflows/ci.yml` 新增 job：

```yaml
  firmware-build:
    name: Firmware build (ESP32-S3)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: arduino/setup-arduino-cli@v2
      - name: Install ESP32 core
        run: |
          arduino-cli core update-index
          arduino-cli core install esp32:esp32
      - name: Compile sketch
        run: |
          arduino-cli compile --fqbn esp32:esp32:esp32s3 \
            firmware/esp32_s3_competition
```

**判据**：编译失败即 CI 红；**并在报告里写明使用的 core 版本**（避免"能编译但换了版本就不行"）。
**变异验证**：随便在 `.ino` 里加一个不存在的符号 → 必须红。
**注意**：`firmware/esp32_s3_competition/` 是 sketch 目录名与 `.ino` 同名 ✓，`arduino-cli` 才能识别（当前满足）。
若未来改用 PlatformIO，则等价命令为 `pio run -d firmware/esp32_s3_competition`。

#### G1 实施记录（2026-10-05）

- **已落地（本地提交 `707c301`，尚未推送）**：`.github/workflows/ci.yml` 新增 `firmware-build` job
  （arduino-cli + `esp32:esp32@3.3.7` + `PubSubClient` → `arduino-cli compile --fqbn esp32:esp32:esp32s3 firmware/esp32_s3_competition`），
  头部注释同步删除 "firmware build matrix … later"。
- **关键发现（决定 job 怎么写）**：`config.h:66` 的 `USE_MQTT` 是**硬定义**（`:70` `#include <PubSubClient.h>`）⇒ **PubSubClient 是硬依赖**；
  `DHT/SGP30/ILI9341/INA219/XPT2046` 全部由 `__has_include` 保护（`:19/26/33/41/48`）⇒ **缺失时编译期降级** ✓；
  `// #define USE_IR`（`:57`）默认关闭 ✓。因此 job **故意不装**这些传感器库，以同时守住"缺库也能编译"这一性质。
- **本地无法验证编译（实测）**：拉 ESP32 工具链时 `esp32:esp-rv32@2601` 需 **673 MB**、实测 ~200 KB/s（ETA 3 小时）✗；
  已装的 `Arduino15\packages\esp32\3.3.7`（**6 GB**）因 ACL（`CodexSandboxUsers → ReadAndExecute`）无法被 CLI 更新元数据 ✗
  ⇒ **"能不能编译"只能由 CI 回答**（这本身就是把门禁放 CI 的又一理由）。
- **已做的替代本地验证**：FQBN 在 3.3.7 的 `boards.txt` 中存在（`esp32s3.name=ESP32S3 Dev Module`，共 326 块板）✓；
  `core install` 支持 `@VERSION` ✓；`arduino/setup-arduino-cli@v2` 上游存在 ✓；YAML 可解析、4 个 job 结构正确 ✓。
- **待办**：推送后由 CI 给出编译结论；若编不过，按报错修并同步修订 §4 的 M5。

### G2 · 行为基线快照（治"不敢重构"）

1. 记录并提交：`pytest tests -q` 的**用例总数与耗时**（当前 148 / 3.47 s）；
2. 把 `python -m energy_system.simulation.compare` 的关键输出**固化为 golden**（写入 `tests/golden/simulation_baseline.json`，含碳减排、舒适度等字段），并加断言测试；
3. 允许差异的方式：**显式声明**（测试里写"本步预期改变 X，原因 Y"），不允许静默漂移。

**判据**：任何改动若使 golden 变化而未声明 → 红。
**变异验证**：把仿真里任一处系数改 1% → golden 测试必须红。

### G3 · 主回路延迟预算断言（治 P2）

新增 `tests/unit/test_loop_latency_budget.py`，用**注入的假时钟 + 假 AI**（仓库已有可注入的 `Scheduler(monotonic=…, sleep=…)` ✓ 复用同一手法）：

| 断言 | 判据 |
|---|---|
| AI 慢 10 s 时，单轮回路耗时可观测地**不被它拉长** | `loop_cycle_s < interval_s`（注入时钟推进量） |
| 采集到决策的**陈旧建议**必须被丢弃 | `dropped_stale_advice >= 1`，且未下发过时命令 |
| 串口读超时（`timeout=1s`）不得阻塞节拍 | 注入假串口返回空 → 节拍仍按 `interval` 推进 |
| `overrun` 不得出现 | 假时钟下 `logger.warning("Loop overrun")` 未被触发 |

**变异验证**：把 AI 调用移回主线程 → 该测试必须红（这就是"防止回退"的锁）。

### G4 · 依赖方向断言（治 P1 结构性回退）

用 `import-linter`（或 20 行自写脚本）把 §3.1 的四条规则写成测试：
`tests/contract/test_layering.py` —— 违反时**指名到 file:line** 失败。
**变异验证**：在 `core/` 里加一句 `from energy_system.cli.run_edge import main` → 必须红。

#### G4 实施记录（2026-10-05，提交 95d6637）

- **一处对本文档自身的更正**：§1.4 写的"**0 个二元环**"是**模块级**测量的结论；按**包级**重算后
  存在一个循环：`core → simulation`（`core/data_acquisition.py:30` 用**函数内延迟导入**
  `simulation.data_generator` 绕开）而 `simulation/simulator.py:2-3` 又导入 `core.thermal_model` /
  `core.controller` ⇒ **包级循环** `core → simulation → core`。两者可同时成立，但按包级看更诚实。
- **已修复**：合成数据源改为**构造参数注入**（`DataAcquisition(..., mock_generator=...)`），
  由组装根 `application/runtime.py` 注入 `EnvironmentGenerator(seed=None)`（方向：外层 → 内层 ✓）；
  未注入时返回 `None`（= 无采样）并给出可搜索告警，**绝不伪造读数**。
- **G4 门禁落地**（`tests/contract/test_layering.py`，5 条）：用**层级秩**表达依赖方向 ——
  内层不得依赖外层（自动抓住包级循环，无需维护允许清单）；专设一条守 `core` 不得依赖 `simulation`；
  叶子包（`utils/hardware/persistence/power/experiments`）不得有内部依赖；
  已登记例外**必须仍然存在**（修好后要删条目，否则门禁自己会腐烂）；新增包必须在 `LAYER_RANK` 显式登记。
  当前唯一例外：`application → hardware`（组装根构造 `SerialBridge`，待 M4 收敛为注入接口）。
- **验证**：`test_layering.py` 5 passed；全量 **189 passed**；
  **变异验证**：把 `core → simulation` 塞回去 ⇒ 门禁指名 `core/data_acquisition.py` 变红 ✓；
  仿真基线逐位不变（**现行值**：碳减排 20.03 kgCO₂、舒适度 49.3%）。

#### M1 读取侧 + G8 完成记录（2026-10-06，提交 b326ec1）

**M1 读取侧（指标名笔误门禁）**
- 实测：Python 侧有 **46 处**以字面量读取指标键，分布在 10 个文件（`core/log_manager.py` 21 处最多）。
- **设计取舍（两版对比，值得记录）**：
  1. 第一版写"所有读取键都必须已登记" ⇒ 报出 **5502 字符**的清单，其中绝大多数是**合法的非指标键**
     （`ai_*` 元数据、诊断字段、仿真内部键）⇒ 只能靠一份巨大允许清单压住，**那正是垃圾桶清单，故否决**；
  2. 第二版改为**近邻检测**：只把"与某个已登记指标很像但不是它"的键判为可疑（`humidty`/`tempreature`）。
     **零允许清单**，且恰好命中真实风险（笔误 ⇒ 静默读到 None）。仅保留**一条**有理由的例外
     （`error` 与指标 `errors` 确实是不同字段）。
  - 另两处必要处理：扫描前剥离**文档字符串**（否则 `telemetry.py` 里举例的 `comfort_scope` 会误报）；
    小样本相似度阈值取 0.85（实测零噪声）。
- **变异验证** ✓：把 `enrichment.py` 的 `"humidity"` 写成 `"humidty"` ⇒ 门禁点名
  `{'humidty': {'looks_like': 'humidity', 'files': ['energy_system/application/enrichment.py']}}` 变红。

**G8 契约单点化断言（已完成）** —— 现状是"任何一处契约漂移都会让 CI 变红"，共 6 类：

| 断言 | 覆盖 | 变异验证 |
|---|---|---|
| 指标注册表自洽 + API/固件/前端三方字段一致 | 4 种语言 | 往 `Snapshot` 塞未登记字段 ⇒ 红 ✓ |
| 固件传感器帧字段 ⟷ 协议清单 ⟷ 换算实现 | 固件 / 主机 | 改清单 scale、固件多发字段 ⇒ 红 ✓ |
| 命令集与回复令牌双侧一致 + **同一命令不得两种分发** | 固件 / 主机 | 加回死分支 ⇒ 点名 `GET_STATE` ✓ |
| 前端页面不得自带阈值/指标键/内联比较 | 前端页面 | 注入 `threshold: 1200`、写回内联比较 ⇒ 红 ✓ |
| 图表渐变色必须来自指标表 | 前端图表 | 写回 `#123456` ⇒ 红 ✓ |
| 分层依赖方向（层级秩、组装根按文件豁免） | 后端包结构 | 塞回 `core → simulation` ⇒ 红 ✓ |

**M6.6 完成**：前端测试网 25 → **48 条**（本次系列累计）；`services/http.ts` 可注入抽象**未做** ——
因为 M6.5 之后 store 已能通过模块 mock 完整测试（且 12 条用例覆盖了兜底/聚合/去重），
再抽一层接口属"为抽象而抽象"，故**明确不做**并记录理由。

### G5 · 协议契约（M5 时落地，治 P3 第二类风险）

`tests/contract/test_serial_protocol.py` 覆盖：正常帧、截断帧、超长帧、非法数字、未知字段、单位一致性。
**变异验证**：只改一端单位 → 红。

### G6 · 前端最小测试门禁（治"零测试"）

前端**当前 0 测试**（附录 B.5），而 M6 要删 6000 行 —— **没有测试网就删代码是赌博** 🎲。
最小动作（**先于 M6.2**）：

```yaml
  frontend-tests:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: app, shell: bash } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: npm, cache-dependency-path: app/package-lock.json }
      - run: npm ci
      - run: npm test -- --run        # vitest，起步覆盖 store 纯逻辑
```

**起步覆盖**（按"最易先行"排序，子代理已给出判据）：`refreshData` 的 mock 兜底（`useAppStore.ts:146-152`）、
`accept/reject` 归约（`:164-182`）、连接态翻转只在变化时弹 toast（`:157-161`）。
**判据**：`npm test` 在 CI 中执行且失败即红；**变异验证**：把 `acceptCandidate` 改成计数不增 → 必须红。

#### G6 实施记录（2026-10-05，本设计书作者执行）

- **已落地（提交 `ba47e64`，已推送）**：`app/vitest.config.ts`（独立配置：jsdom + `@` 别名）+ `app/src/store/useAppStore.test.ts`
  （**8 条**）+ `package.json` 的 `test`/`test:watch` + CI frontend job 在 Lint 与 Build 之间新增**阻塞**步骤 `npm test`。
- **覆盖的三条"必须保留"行为**（对应 B.7）：离线兜底（后端不可达时回落 mock 且数据非空）、
  连接态**只在变化时**弹 toast、`accept/reject` 为**本地乐观更新**不发网络请求。
- **版本选择（差点踩坑，已实测）**：`vitest@5` 要求 **Node ≥22.12** ✗ 而 CI 用 **Node 20**；
  `jsdom@latest` 同样要求 ≥22.22 ✗。⇒ 选 **vitest@^4**（`^20 || ^22 || >=24` ✓）+ **jsdom@^26**（≥18 ✓）。
  这类"本地能跑、CI 装不上"的坑与 G1 的 core 版本钉扎是同一类问题。
- **验证（本地）**：`npm test` 8 passed / exit 0；`npm run lint` exit 0；`npm run build`（含 `tsc -b`）exit 0；
  `npm ci --dry-run` exit 0（**package.json 与 lockfile 同步** —— 否则 CI 的 `npm ci` 会直接失败）；
  **变异验证**：把断言改成 `toBe(999)` ⇒ exit 1，还原 ⇒ exit 0（门禁有牙 ✓）。
- **过程中的两个自身失误（记录在案）**：① `tsc` 抓到测试里的类型错误（`SimulationParams` 无 `seed` 字段）⇒ 改用真实字段 `days`；
  ② 用 `Set-Content -Encoding utf8` 改文件引入了 **BOM + 重编码**，中文变成乱码并导致 esbuild `Unterminated string literal` ⇒
  **结论：改这类含中文的源码文件必须用编辑器/写入工具（UTF-8 无 BOM），不要用 PowerShell 文本命令回写** ✓。

### G7 · 死代码与依赖门禁（治"不干净"且防止它长回来）

- **前端**：`npx knip`（或 `ts-prune`）→ 输出未使用文件/导出/依赖；**先把当前基线记为"已知豁免清单"**（含那 51 个 ui 文件），
  再在 M6.2 里逐条删除并把豁免清单清空；`axios` 与 kimi 插件同样纳入。
- **后端**：`vulture`（或自写 AST 脚本）扫未使用函数/变量；`pip` 侧检查 `requirements.txt` 中未被 import 的包。
- **判据**：门禁运行且输出"新增死代码 = 0"（相对基线），任何**新增**未使用项即红。
- **变异验证**：故意留一个未使用的导出 → 门禁必须红。

#### G7 实施记录 + M6.2 完成（2026-10-05，提交 4eb1b01）

- **M6.2 已落地**：删除 **53 个不可达文件**（`components/ui/` 51 个 + `App.css` + `use-mobile.ts`）、
  **38 个无主依赖**、4 个死 store 成员、`kimi-plugin-inspect-react`（含 `vite.config.ts` 去插件）、
  0 引用的 `PageTab` 与 `AICommandStatus`。
- **量化结果**：`src/` 行数 **9661 → 3787（−61%）**；`dependencies` **49 → 13**。
- **G7 已落地（零豁免基线）**：`scripts.knip = knip` + CI 阻塞步骤 `Dead-code check (knip)`。
  **不配置任何 ignore**，因此当前是"零发现"状态：注入一个私有文件 ⇒ `exit 1` 并指名文件，
  移除 ⇒ `exit 0`（已实测 ✓）。
- **三处需要判断、而不是无脑删除的地方**（记录判断依据，便于复审）：
  1. `AICommandStatus` 虽是 0 引用，但其注释承载"模型返回 ≠ 设备执行"的语义 ⇒ 删除类型别名、
     **把语义合并到 `AICandidate.executed` 的注释**（语义未丢失）；
  2. `buttonVariants` 在 `button.tsx` 内部仍被使用（L46/L56）⇒ 只取消 `export`，不删定义；
  3. 契约字段（`schema_version`/`relays`/`errors`/`carbon_factor*` 等）**本轮未动** —— 它们镜像后端契约，
     删除属契约变更，需先比对 `api_server.py`（见 B.10-⑤）。
- **验证**：`npm run build` / `npm test`（8 passed）/ `npm run lint` / `npm run knip` 全部 exit 0；
  由 CI run #8 复核。

### G8 · 契约单点化断言（治"三份副本"）

在 `types/` 旁建**唯一指标/字段常量表**（M6.3）后，加断言：
前端 `SensorChart`/`RealtimePage`/`HealthPage` **不得再出现裸字符串键**（lint 规则或 AST 检查），
后端 `metrich` 同理（对应 M1 的 `METRICS` 注册表）。
**判据**：改一个键名 → 只需改 1 处 + `tsc` 报错；**变异验证**：把某组件改回裸字符串 → 门禁红。



### 6.1 不做（避免"重构上瘾"）

| 不做 | 原因 |
|---|---|
| 推倒重写 Python 内核 | 已有分层 + 0 循环导入 + 148 条测试，重写只剩风险 |
| 换语言/换框架（如把 Streamlit 换掉、后端换 Django） | 与四个痛点无因果关系 |
| 合并 `app/` 与 `dashboard/` | 两者服务不同场景（竞赛面板 vs 运维看板），合并会放大耦合 |
| 重写 `simulation/` | 它是你唯一的**结果级**回归基线，动它等于拆掉卷尺 |
| 引入数据库/消息中间件 | JSONL 落盘 + 5 s 周期下不是瓶颈；先用量化证据说话 |

### 6.2 风险登记

| 风险 | 触发条件 | 缓解 |
|---|---|---|
| R1 重构期间竞赛交付受影响 | 截止日临近 | 只做 M0–M1（门禁+模型化），M2 之后放到赛后 |
| R2 固件换 core 版本后编译行为变化 | G1 安装最新 core | 在 CI 固定 core 版本；本地也固定 |
| R3 AI 异步化改变"execute"语义 | M2 改动 | 保留同一套规则闸门；用现有 `tests/unit/test_decision.py` 守住 |
| R4 golden 被"顺手更新" | 有人图省事改 golden | golden 改动必须走显式声明 + 评审（CI 里禁止自动更新 golden） |
| R5 模型化引入大量样板 | M1 用力过猛 | 先做"适配层"（不改调用方），逐层替换；不允许一次性改 100+ 处 |

---

## §7 完成判定（做到什么算这轮重构成功）

1. **G1–G4 全绿且各自通过变异验证**（G5 在 M5 完成时补）；
2. 148 条测试 + 新增测试全绿；仿真 golden 数字**在未声明的情况下零漂移**；
3. 涟漪因子：新增一个指标只需改 **≤3 个文件**，并有测试证明；
4. **AI 慢 10 s 不影响采集/控制/告警时效**（G3 断言）；
5. `grep -r "os.getenv" energy_system` 只命中 `config/`；
6. `application/runtime.py` 扇出 ≤5；
7. 以上每一条都有**可粘贴的命令与原始输出**（沿用你仓库 CI 的"退出码即事实"风格）。

**前端追加（M6 完成时）**：

8. `src/components/ui/` 只剩**被引用**的组件；`npx knip` 相对基线**新增死代码 = 0**（G7）；
9. 指标键集**只有一份**定义，改键名 `tsc` 报错、且只改 1 处（G8 的变异验证通过）；
10. 3 个已确认缺陷各自有测试守着（`PrecisionKnob` 无残留监听 / `??` 括号 / 累计曲线接真实后端不再恒 0）；
11. `npm test` 在 CI 执行且覆盖 store 纯逻辑；慢后端批次不重叠、单端点失败不再误报离线（G6 + M6.5）；
12. B.7 的 **13 条行为逐条仍成立**（尤其离线可用、连接态只在变化时提示、本地乐观裁决）。

---

## 附录 A · 本设计书的取证命令（可复现）

```powershell
# 0) 克隆与依赖（独立 venv，不碰项目环境）
git clone --depth 1 https://github.com/Atlas-did/EcoSentinel.git _archive\ecosentinel
uv venv --python 3.12 _archive\eco_venv
uv pip install --python _archive\eco_venv\Scripts\python.exe -r _archive\ecosentinel\requirements.txt

# 1) 结果级基线
_archive\eco_venv\Scripts\python.exe -m pytest tests -q                     # 148 passed / 3.47s
_archive\eco_venv\Scripts\python.exe -m energy_system.simulation.compare    # 退出码 0

# 2) 涟漪因子（加一个指标要碰多少文件）
Get-ChildItem energy_system,api_server.py,main.py,scripts,firmware -Recurse -File -Include *.py,*.h,*.ino |
  ForEach-Object { Select-String -LiteralPath $_.FullName -Pattern 'temperature' -SimpleMatch } |
  Select-Object -ExpandProperty Path -Unique | Measure-Object            # 27 个文件

# 3) 导入图（扇入/扇出/循环）与延迟热点：见 §1.4 / §2 的脚本与 grep 结果
```

## 附录 B · 前端（`app/`）证据包

> 口径：**只读**分析；未装依赖、未跑 npm/vite/tsc；行号来自逐文件读取。
> 实测 **76 个 `.ts/.tsx` = 9661 行**（含空行；加 `src/App.css` + `index.css` 为 78 文件 —— 与 §1.2 的 "77 文件/9685 行" 差异来自是否计 `.css`）。
> 状态：**证据 1–4/5 已到**（§1–§4 全 + §5 可测试性 + §6 死代码）；仅"必须保留 vs 可安全重排"两张清单待 5/5。

### B.1 结构盘点（1/5）

| 证据 | 事实 |
|---|---|
| `src/components/ui/` | **53 文件 / 6082 行** —— 未被应用的 shadcn 脚手架，占 `src` 行数 **61%** |
| `src/components/common/` `charts/` `layout/` | 7 / 1 / 2 文件（445 / 236 / 294 行） |
| `src/pages/` | 6 文件 1950 行（`DashboardPage` 507、`SimulationPage` 382、`AIDecisionPage` 362） |
| `src/store/` `services/` `types/` `hooks/` `lib/` | 1 / 1 / 1 / 1 / 1 文件（208 / 245 / 118 / 19 / 6 行） |
| 实际被引用的 ui 组件 | **仅 2 个**：`ui/tabs`（`DashboardPage.tsx:23`）、`ui/button`（`TopBar.tsx:14`） |
| 分层缺口 | 无 `features/` 层；业务 UI 直接堆在 `pages/*.tsx`；`common/` 只有展示组件，无数据/容器层 |
| 路由 | `App.tsx:36-41` 共 6 条；`vite.config.ts:21` alias `@` → `./src` |

### B.2 状态与数据流（1/5）—— **这部分是"必须保留"的资产**

| 证据 | 事实 |
|---|---|
| `useAppStore.ts:1` | zustand 单 store（`package.json`: zustand ^5.0.14）；全 `src` 无 redux/react-query |
| `api.ts:38` | **全项目唯一一处 `fetch`** |
| `api.ts:28-82` | 7 个 `fetch*` 函数 |
| `useAppStore.ts:133-141` | `refreshData` 为唯一调用方，`Promise.all` 并发取 7 端点 ⇒ **不存在"多组件各拉一次"** |
| `useAppStore.ts:91-97` / `:193-201` | 初始化用 mock 播种；`setInterval` **3000 ms** 自动刷新（模块级单例 `:191`，路由互斥不会双轮询） |
| `useAppStore.ts:108-113` | ✗ `setTimeRange()` 只改图表区间，却触发 `refreshData()` **重拉全部 7 端点** |
| `AIDecisionPage.tsx:36-43` vs `DashboardPage.tsx:216` | ✗ 同一组 accepted/rejected 计数**各算一遍**（重复派生，非重复请求） |

### B.3 后端契约耦合（2/5）—— 结论：**类型层集中、运行期分散**

端点/主机名收敛 ✓，但**字段名与取值域在组件里被复制 3 份**，改后端字段 **tsc 不报错 → 静默失效** ✗：

| 证据 | 事实 |
|---|---|
| `api.ts:23` / `vite.config.ts:14` | `API_BASE='/api'`；后端主机名唯一处 `http://127.0.0.1:8080` ✓ |
| `api.ts:57,61,65,69,73,77,81` | 7 个端点字面量（snapshot/chart/ai-candidates/resilience/energy-summary/health/simulation/params） |
| `types/index.ts:2-104` | 后端字段名（snake_case）的**唯一声明处** ✓ |
| **`SensorChart.tsx:138,149,160,170,180,191,202,214,225`** | ✗ **9 个 dataKey 字符串字面量**，重复 `types/index.ts:69-78` |
| **`RealtimePage.tsx:19-23`** | ✗ 第二份同键集（+阈值 30/80/1000/1200/20 散落此处） |
| **`HealthPage.tsx:23-30`** | ✗ 第三份同键集（temperature/humidity/illuminance/eco2/power/solar） |
| `api.ts:86-245` | ✗ mock 生成器（6 个函数）**硬编码全部字段名**= 离线契约的第二份副本 |
| 散落魔数 | `DashboardPage.tsx:44` `targetTemp=24.5`；`EnergyAnalysisPage.tsx:30-31` `0.0167`(W→kWh)；`:214` `264` / `DashboardPage.tsx:490` `251`(SVG 周长) |
| 声明后 0 引用 | `types/index.ts:3,14,35,39,53,59-63,83,91,111`（`schema_version`/`relays`/`executed`/`AICommandStatus`/`energy_saved_kwh`/`carbon_factor*`/`electricity_price_cny_per_kwh`/`corrupt_records`/`PageTab`） |
| ✗ **可见缺陷** | `useAppStore.ts:42,55,64,66,87,100,114,116`：`isLoading` **从不置 true**；`aiStatus` 只被 `TopBar.tsx:21` 读、**全项目无写入** ⇒ **AI 状态徽章恒定不刷新** |

**涟漪（前端口径）**：新增一个后端字段需改 `types/index.ts` + mock 生成器 + 各消费组件；
新增一个图表指标需改 `types` + `SensorChart` 字面量 + `RealtimePage` 配置 + `HealthPage` 映射 ⇒ 与后端"指标涟漪 16–27 文件"是**同一类债务**。

### B.4 风险与缺陷（3–4/5，全部可复核）

**A. 渲染期重活（无 `useMemo`）**

| 证据 | 事实 |
|---|---|
| `EnergyAnalysisPage.tsx:28-32` | ✗ O(n²)：`map` 内 2 次 `slice(0,i+1).reduce()`；图表 100 点（`api.ts:110`）⇒ **每次渲染约 2 万次迭代**，且该页随 3 s 轮询重渲染 |
| `AIDecisionPage.tsx:29-43` | ✗ 每次渲染 4 次 `filter` + 2 次 `reduce`；仅切换 `expandedId`(:26) 也全量重算 |
| `RealtimePage.tsx:49-51` / `SimulationPage.tsx:35-39` | ✗ 每次渲染对 `chartData` 全量 filter/map |
| ✗ **正确性** `EnergyAnalysisPage.tsx:30-31` | 依赖 `baseline_power`/`saving_power`，而这两字段**只有 mock 产出**（`api.ts:129-130`）且在类型里可选（`types/index.ts:76-77`）⇒ **接真实 `/chart` 时累计曲线恒为 0** |

**B. `useEffect` 依赖与清理**

| 证据 | 事实 |
|---|---|
| ✗ **真实泄漏** `PrecisionKnob.tsx:55 vs :61` | 注册匿名 `pointerup`，却用**另一个**匿名函数 `removeEventListener` ⇒ 按引用匹配失败，**该监听永不解除** |
| ✗ `PrecisionKnob.tsx:67 + :49` | deps 含 `handlePointerMove`（依赖 value/onChange）⇒ 拖动中每次值变都重建 effect，**旧的 pointerup 持续累积** |
| `use-mobile.ts:8-16` | 清理正确（但只被**死文件** `ui/sidebar.tsx:8` 引用） |
| `DashboardPage.tsx:39-42` / `RealtimePage.tsx:36-39` | 空 deps 单例轮询；`main.tsx:8` StrictMode 下 effect 双跑，配合 `useAppStore.ts:194` 重启 ⇒ 功能安全但**脆弱** |

**C. 定时器 / 订阅**

| 证据 | 事实 |
|---|---|
| `useAppStore.ts:120-122` | `addToast` 的 `setTimeout` 未存句柄 ⇒ 无法取消 |
| `useAppStore.ts:191-208` | 轮询 interval 为**模块级变量**，只由页面卸载时的 `stopAutoRefresh` 关闭 ⇒ 应用级卸载/HMR 不触发时残留 |
| 全 `src` | 无 WebSocket/EventSource（grep 0 命中）⇒ "实时"完全靠 3 s 轮询；但 `types/index.ts:15,19`（relays/errors）暗示**推送式契约**（契约与实现不一致） |

**D. 无虚拟化**：`package.json` 无虚拟列表依赖；`DashboardPage.tsx:220,301`、`AIDecisionPage.tsx:120,252`、`HealthPage.tsx:129,191` 全量 `map`；
`/resilience` **无 limit/分页参数**（`api.ts:69` + `types/index.ts:42-49`）⇒ 后端返历史即全渲染。（`RealtimePage.tsx:184` 已封顶，安全 ✓）

**E. 渲染期非确定性**

| 证据 | 事实 |
|---|---|
| `api.ts:90-105,108-135` | ✗ `Math.random()` 生成；由 `useAppStore.ts:91-92`（初始化）与 `:146-149`（**每次轮询兜底**）调用 ⇒ 后端离线时**每 3 s 全量换数、图表抖动** |
| `TopBar.tsx:125`、`DashboardPage.tsx:314`、`HealthPage.tsx:101,218`、`AIDecisionPage.tsx:190` | 渲染期 `new Date(...).toLocaleTimeString('zh-CN')`（受宿主时区/ICU 影响） |
| `SensorChart.tsx:68,74,80,86,92,98,104` | 固定 SVG 渐变 id ⇒ 同页两个实例会冲突（当前路由互斥，属潜在风险） |

**F. 轮询正确性（对应"可靠性"痛点）**

| 证据 | 事实 |
|---|---|
| ✗ `api.ts:24` vs `useAppStore.ts:200` | 超时 **5000 ms > 间隔 3000 ms**，且 `refreshData`(:128-162) **无 in-flight 保护** ⇒ 慢后端时**批次重叠**；`:129` 置 true / `:154` 置 false 会被旧批次提前清 |
| ✗ `api.ts:26,:40,:43` | `_backendAvailable` 是**模块级全局**，由最后完成/失败的请求写入 ⇒ **单个端点失败即置 false 并弹"后端未连接"**（`useAppStore.ts:159-160`），其余 6 个成功也误报 ⇒ 连接态每 3 s 抖动 |

**G. 确定的正确性 bug**

| 证据 | 事实 |
|---|---|
| ✗ `EnergyAnalysisPage.tsx:229` | `(energySummary?.carbon_reduced_kg ?? 0 / 20)`：`??` 优先级低于 `/` ⇒ 实为 `x ?? (0/20)`，**除以 20 从未生效**（对比 `:223` 直接输出原值） |

### B.5 可测试性（4/5）：**零测试**

无测试文件、无 `test` 脚本、无测试依赖、无覆盖率配置、实际 0% ✓（唯一 "spec" 命中是 `a**spec**t-ratio.tsx` 子串误报）。

**障碍**：`useAppStore.ts:91-96` **import 期即执行 `Math.random`**（导入即有副作用、无注入缝）；`api.ts:38` 直接调 `window.fetch`（无客户端抽象）；`api.ts:23` `API_BASE` 是模块常量非 env；`api.ts:26` / `useAppStore.ts:191` 模块级状态跨用例残留；`useAppStore.ts:120` 需 fake timers。
**有利**：`types` 已集中 ✓；store 可 `useAppStore.getState()` 免渲染测试（应用自身即如此用，`useAppStore.ts:196`）✓。

### B.6 死代码与重复（4/5）

**方法**：grep `from '@/components/ui/` ⇒ 全项目**仅 2 命中**；再查可达闭包（`tabs.tsx`→radix+tabs、`button.tsx`→radix-slot）⇒ 其余 51 个即使互相 import 也**从入口不可达**。
**局限（须写进结论）**：只统计静态 import 说明符；已 grep 确认全 `src` 无动态 `import(`。

| 证据 | 事实 |
|---|---|
| `src/components/ui/` | **51/53 文件、5954/6082 行（占 src 61%）从入口不可达** |
| `src/App.css` | 从未被 import（`main.tsx:4` 只引 `index.css`） |
| `src/hooks/use-mobile.ts` | 唯一引用方 `ui/sidebar.tsx:8` 本身已死 ⇒ 传递性死代码 |
| `package.json` | `axios ^1.16.1` 全 `src` **0 引用**（取数用 fetch）；`vite.config.ts:4,9` 仍留 `kimi-plugin-inspect-react`（dev 插桩） |
| 重复 | 5 份日期格式化（`TopBar:125`/`DashboardPage:314`/`HealthPage:101,218`/`AIDecisionPage:190`）；`AIDecisionPage:69-100` 与 `DashboardPage:370-390` 内联重写统计卡片而未复用 `common/MetricCard`；3 页各写一份 page-header（`AIDecisionPage:49-60`、`SimulationPage:45-58`、`EnergyAnalysisPage:38-51`） |
| `lib/utils.ts` | 仅 6 行，只有 `cn` |



### B.7 重构时**必须保留**的行为（5/5 终稿，共 13 条）

1. **离线可用**：后端不可达必须回落 mock 并正常渲染，不得变空白/错误页（`api.ts:42-44` 返回 `null`；`useAppStore.ts:146-152` 的 `?? generateMock*`）。
2. **轮询节律与手动刷新**：3 s 固定间隔（`useAppStore.ts:195-200`）+ TopBar 手动刷新（`TopBar.tsx:154`）+ `autoRefresh` 开关**真能停掉取数**（`:197`）、**默认开启**（`:83`）。
3. **连接态只在变化时提示**：toast 仅在 `backendUp` 相对上次翻转时弹（`useAppStore.ts:157-161`），非每轮都弹。
4. **7 个端点路径与语义**：`api.ts:57-81`，尤其 `/chart?range=` 的 `'5m'|'1h'|'24h'`（`types/index.ts:110`）。
5. **snake_case 字段名与可选性**：`types/index.ts:2-104`；多数 `SensorSnapshot` 字段可选、组件已按可空渲染（`DashboardPage.tsx:99,467,471` 的 `?? '--'`）——**不要改成必填**。
6. **AI 候选三态 + "已执行"语义**：未决/已接受/已拒绝（`AIDecisionPage.tsx:29-33,247-273`、`DashboardPage.tsx:247-273`）；`types/index.ts:35` + `:38-39` 注释强调的 **"模型返回 ≠ 设备执行"必须保持区分**（`DashboardPage.tsx:263-268` 的"已执行"文案即此语义）。
7. **本地乐观裁决**：`acceptCandidate`/`rejectCandidate` **只改本地 state + 发 toast，不发网络请求**（`useAppStore.ts:164-182`）——改成写后端属**行为变更**。
8. **安全模式横幅与兜底文案**：`HealthPage.tsx:242-255`（`safe_mode` + `safe_reason || '系统检测到异常，已进入安全运行模式'`）。
9. **路由与深链**：`App.tsx:36-41` 的 6 条路径必须与 `SideNav.tsx:15-22` 一一对应；活跃态按 `pathname` **精确匹配**（`:49`）。
10. **侧栏折叠联动**：`sidebarOpen` 同时驱动 SideNav 宽度（`SideNav.tsx:31-33`）与主内容 padding（`App.tsx:21-23`）。
11. **仿真预览的确定性**：`SimulationPage.tsx:33-39` 明确注释改 index-based 的意图 —— **勿"顺手改回"**。
12. **mock 数据字段完整度**：`api.ts:86-245` 是**离线演示契约**，字段名必须与 `types/index.ts` 一致（否则离线态/在线态渲染分叉）。
13. **运行期依赖大版本**：zustand 5 / React 19 / recharts 2 / framer-motion 12 / tailwind 3（`package.json`）。

### B.8 可以**安全重排**的部分（5/5 终稿，共 15 条）

1. 删除 51 个不可达 `src/components/ui/*.tsx`（−5954 行）；若要把设计系统留作备查，**改为独立包或补可达性测试后再删**。
2. 删除 `src/App.css`、`src/hooks/use-mobile.ts`、`axios` 依赖、`vite.config.ts:4,9` 的 `kimi-plugin-inspect-react` 插桩（dev 插件不应进入生产构建路径）。
3. 删除 store 死成员 `activeTab`/`setActiveTab`/`isLoading`/`setAIStatus`（`useAppStore.ts:42,55,64,66,87,100,114,116`）。
4. 删除 `types/index.ts:3,14,35,39,53,59-63,83,91,111` 的 0 引用契约成员 —— **但若后端确已返回这些字段，应改为"消费"而非删除**（见 B.10-⑤）。
5. 三份指标键集（`SensorChart.tsx:138-225`、`RealtimePage.tsx:19-23`、`HealthPage.tsx:23-30`）**合并为 `types/` 旁的单一常量表** ⇒ 字段改名变单点修改。
6. 抽 `src/lib/format.ts` 收敛 5 处时间格式化；抽 `PageHeader` 收敛 5 处页头。
7. `EnergyAnalysisPage.tsx:28-32` 加 `useMemo` 并改前缀和（O(n²)→O(n)）；`AIDecisionPage.tsx:29-43` 加 `useMemo` 单遍统计。
8. 修 `PrecisionKnob.tsx:55/:61` 监听泄漏（具名 handler 或 `useRef` 保存引用）。
9. 修 `EnergyAnalysisPage.tsx:229` 括号优先级 bug。
10. `refreshData`（`useAppStore.ts:128`）加 **in-flight 去重**；`_backendAvailable`（`api.ts:26`）由"最后写入者胜"改为**按轮次聚合**（全部失败才算离线）。
11. `setTimeRange`（`useAppStore.ts:108-113`）只触发 `fetchChart`，不触发全量 `refreshData`。
12. 抽 `services/http.ts` 封装 `fetch`（可注入、可测），`API_BASE` 改 env 驱动。
13. 阈值常量上提到统一配置（`DashboardPage.tsx:44,110,153`、`RealtimePage.tsx:19-23,50`）—— ⚠️ **当前 `RealtimePage.tsx:19-23` 与 `:50` 的阈值本身就不一致，须先定夺哪个是正确的**。
14. 引入 vitest + @testing-library/react，从 store **纯逻辑**（`refreshData` 兜底、`accept/reject` 归约）起步，再覆盖 `/api` 层。
15. 引入虚拟列表为 `resilienceEvents`/`aiCandidates` 做窗口化（**需先与后端确认 `/resilience` 是否返回长历史**）。

### B.9 前端证据的**交叉结论**（与后端 §2 合并看）

| 现象 | 后端 | 前端 | 共同根因 |
|---|---|---|---|
| "加新功能要改很多地方" | 指标名跨 **16–27 文件** | 指标键集 **3 份副本** + mock 生成器**又一份** + 字段名散落 **30+ 处** | **契约与派生值缺少单一真值** |
| "不干净" | env 读取 3 处、`env_loader` 有全局副作用 | **61% 的 src 是不可达脚手架** + 4 个死成员 + 1 个死依赖 + 1 个 dev 插件留在构建里 | 缺少**死代码/依赖门禁** |
| "可靠性" | AI 在同步主回路、串口 1 s 阻塞 | 轮询 5 s 超时 > 3 s 间隔、无 in-flight 去重、连接态被单个端点左右 | 缺少**超时/并发不变量** |

> 所以第 1–5 部分指向**同一个结论**：这个项目的问题不是"分层混乱"，而是
> **契约/派生值没有单一真值 + 没有死代码与不变量门禁**。这两类问题都适合**增量收口**，不适合重写。

<!-- 设计书结束。修订请追加到对应小节，不要另起并行文档。 -->


### B.10 不确定项（5/5 自陈，共 8 条）+ 本设计书的复核结果

| # | 未验证项 | 本设计书的处理 |
|---|---|---|
| ① | 未跑 `npm run build`（tsc -b）⇒ `DashboardPage.tsx:153` `soc_percent!` 等非空断言、`HealthPage.tsx:92` 窄化是否通过**未知** | 记入 M6 步骤 1（先跑通 build 再动手） |
| ② | 未跑 eslint ⇒ `PrecisionKnob.tsx:52-67` 是否已被 `react-hooks/exhaustive-deps` 捕获未知 | 同上 |
| ③ | 无 `node_modules` ⇒ 依赖实际版本解析、recharts/framer-motion 行为未验证 | 同上 |
| ④ | 未运行应用 ⇒ "图表每 3 s 抖动"等由**代码路径推出**，未实测 | 结论标注为"代码路径推断" |
| ⑤ | 未读后端 ⇒ `/resilience` 是否真返长历史、`/chart` 是否真不含 `baseline_power` 属前端侧推断 | 待与 `api_server.py` 比对（M6 前置） |
| ⑥ | 行数口径 9661 vs 任务书 9685（差 24） | 差额应为 2 个 `.css`，**不影响结论** |
| ⑦ | grep 死代码只覆盖静态 import 与字面量 ⇒ 动态 import/字符串路径/CSS 类名可能误判 | 已 grep 确认全 `src` **无 `import(`** |
| ⑧ | 未做 git 操作 ⇒ "死文件"可能是他人进行中的工作 | **✅ 本设计书已复核**：工作区干净、HEAD `174cb5d` ⇒ 死文件是**已提交**的上游代码 |

**本设计书额外独立复核的三条**（用不同方法，结论一致）：

1. `components/ui/` 的 22 处 import 中，**20 处是 `ui/`→`ui/` 内部依赖**，仅 **2 处来自入口**（`layout/TopBar.tsx:14` → `ui/button`；`pages/DashboardPage.tsx:23` → `ui/tabs`）⇒ **"51/53 不可达"成立**；
2. `axios` 全 `src` **0 引用** ✓（确认）；`vite.config.ts` 确有 `import { inspectAttr } from 'kimi-plugin-inspect-react'` ✓（确认）；
3. `EnergyAnalysisPage.tsx:229` 的 `?? /` 优先级判断**正确**（JS 中 `??` 优先级低于 `/`，表达式等价于 `x ?? (0/20)`）。

> **判定**：前端是四个痛点里**证据最充分、但风险最高**的区域（**零测试** + 61% 死代码 + 3 个已确认缺陷）。
> 但**修复清单是"删除 + 单点化 + 加去重"这类机械动作**（B.8 的 12 条），**不构成"推倒重写"的理由** ——
> 反而**先删掉 61% 再用 vitest 锁住剩下的 39%**，是最划算的第一步。

<!-- 设计书结束。修订请追加到对应小节，不要另起并行文档。 -->



