# EcoSentinel 代码重构详细实施计划

> **文档版本**：v1.0
>
> **编制日期**：2026 年 8 月 20 日
>
> **适用仓库**：`https://github.com/Atlas-did/EcoSentinel`
>
> **计划定位**：这是一个面向现有代码库的渐进式重构实施方案。目标不是一次性推倒重写，而是在保留当前可运行能力和仿真结果的前提下，逐步降低耦合、提高可测试性、收紧安全边界，并为真实硬件闭环和后续工程化部署打基础。

---

## 1. 执行摘要

EcoSentinel 当前已经具备一个可运行的竞赛原型：Python 边缘控制、ESP32-S3 固件、串口 JSON 通信、规则控制、AI 建议与本地回退、能耗核算、自愈编排、Streamlit Dashboard、FastAPI API 和 React 前端均已存在；当前仓库测试为 20 项通过，三天数字仿真可以输出 baseline/saving 对照结果。

但从“能运行”走向“可长期维护、可验证、可安全扩展”，仍存在几类结构性问题：

1. `main.py` 中的应用编排、硬件初始化、主循环、指标计算、AI 调用、动作执行、日志和自愈流程集中在同一个应用类中，修改一个环节容易影响其他环节。
2. `api_server.py` 把 HTTP 路由、JSONL 文件读取、业务指标计算和运行配置混在一起，并存在开放 CORS、硬编码采样率、硬编码电价/碳因子、按固定行数而不是按时间戳查询等问题。
3. `ai_advisor.py` 同时承担 API 客户端、候选池、Prompt、JSON 解析、评分、熔断和本地回退，模块过大；AI 输出仍需要进一步转换为强类型领域命令，而不能停留在字符串命令层。
4. 控制器、串口桥、自愈编排和日志模块大量使用裸字典、字符串状态和自由格式命令，边界不够清晰。
5. 配置已经有 dataclass 和字段校验的雏形，但缺少环境分层、跨字段校验、配置来源记录和一致的启动错误策略。
6. 测试主要覆盖配置、协议解析、AI 回退和自愈基础行为，API、控制状态机、能耗积分、日志损坏、硬件适配和端到端链路覆盖不足。
7. ESP32 固件集中在单个约 1183 行的 `.ino` 文件中，传感器、协议、命令路由、自愈、状态和业务循环尚未形成清晰模块边界。

本计划采用以下总原则：

> **先冻结行为，再建立边界；先补测试，再移动代码；先收紧安全边界，再增加高级能力；每个阶段都能独立验证和回滚。**

建议执行顺序为：

- **P0：基线与安全边界**——不改变核心控制策略，先把行为记录下来，补齐高风险校验，关闭明显不安全默认值。
- **P1：领域模型与模块拆分**——逐步拆分主循环、AI、API、日志、硬件和控制器，建立强类型数据流。
- **P2：工程化与性能演进**——引入更完整的部署、观测、消息总线、数据库、MPC/RL 等能力，但必须以真实实验和稳定接口为前提。

---

## 2. 当前基线与审查结论

### 2.1 当前已确认的能力

以下内容属于当前源码或当前实验已确认的范围：

| 范围 | 当前状态 | 证据/入口 |
|---|---|---|
| Python 后端 | 已存在 | `main.py`、`energy_system/` |
| 规则控制 | 已存在 | `energy_system/core/controller.py` |
| AI 建议与本地回退 | 已存在 | `energy_system/algorithms/ai_advisor.py` |
| AI 字符串命令基础校验 | 已存在，但仍需加强 | `energy_system/core/command_dispatcher.py` |
| 串口 JSON 解析 | 已存在 | `energy_system/hardware/serial_bridge.py` |
| 自愈动作规划 | 已存在 | `energy_system/resilience/orchestrator.py` |
| 能耗积分 | 已存在 | `energy_system/power/energy_accounting.py` |
| 数字仿真 | 已存在 | `energy_system/simulation/` |
| Streamlit 看板 | 已存在 | `dashboard.py`、`dashboard/` |
| FastAPI 服务 | 已存在 | `api_server.py` |
| React 前端 | 已存在 | `app/src/` |
| ESP32-S3 固件 | 已存在 | `firmware/esp32_s3_competition/esp32_s3_competition.ino` |
| 自动化测试 | 当前 20 项通过 | `tests/` |
| 三天 baseline/saving 仿真 | 已核验 | `python -m energy_system.simulation.compare` |

### 2.2 当前实验口径

当前已核验的三天仿真结果为：baseline 81.48 kWh、saving 57.18 kWh、节省 24.30 kWh、节能率 29.8%，两种模式平均舒适度均为 82.1%。这些数字只能说明当前模型和参数下的仿真可运行、可比较，不能直接称为真实建筑实测节能率。

重构期间必须保持这条口径不变：

- 代码重构不应悄悄改变仿真参数、时间步长、初始状态和指标定义。
- 如果重构导致结果变化，必须保存旧版与新版结果，并解释变化来自 bug 修复、参数变化还是算法变化。
- 每一项新指标都要同时记录实验条件、原始数据位置、脚本版本和生成时间。

### 2.3 主要技术债务清单

| 编号 | 问题 | 影响 | 优先级 |
|---|---|---|---|
| TD-01 | `main.py` 编排职责过多 | 测试困难，修改风险高 | P1 |
| TD-02 | API 路由、文件读取、业务计算混杂 | 难以复用和测试 | P1 |
| TD-03 | API `allow_origins=["*"]` 且允许凭证 | 生产环境存在跨域安全风险 | P0 |
| TD-04 | API 采样率固定为 `1.0` | 与实际 5 秒主循环可能不一致 | P0 |
| TD-05 | 电价和碳因子硬编码 | 指标不可追溯、口径易漂移 | P0 |
| TD-06 | 图表范围按行数映射 | 数据稀疏或采样变化时结果失真 | P1 |
| TD-07 | AI 模块职责过多 | 网络、策略和安全难以隔离 | P1 |
| TD-08 | AI 输出以自由字符串为主 | 命令边界和审计粒度不足 | P0 |
| TD-09 | 控制器使用较多缩写和弱类型字段 | 领域含义不够清晰 | P1 |
| TD-10 | 自愈状态和动作使用字符串/字典 | 状态转换易出现拼写和字段漂移 | P1 |
| TD-11 | 配置缺少环境分层 | 模拟、硬件、测试配置容易互相污染 | P1 |
| TD-12 | JSONL 读取对损坏行、并发写入处理有限 | 看板和 API 可能读到不完整数据 | P1 |
| TD-13 | 测试未覆盖 API 和完整执行链 | 回归风险未被及时发现 | P1 |
| TD-14 | 固件集中于单个 `.ino` 文件 | 维护、复用、硬件测试困难 | P1 |
| TD-15 | 前端 API 类型与后端响应缺少单一契约 | 字段变更容易造成运行时错误 | P1 |
| TD-16 | 异常捕获范围偏宽 | 真正 bug 可能被降级为普通失败 | P1 |

---

## 3. 重构目标与非目标

### 3.1 总体目标

重构完成后，系统应具备以下特征：

1. **控制安全**：AI 默认只能提出建议；所有可执行动作必须经过领域命令模型、白名单、参数范围、模式权限、速率限制和审计记录。
2. **模块清晰**：采集、领域计算、策略决策、命令验证、硬件执行、日志、API 和展示层之间通过明确接口通信。
3. **行为可验证**：基线仿真、控制器状态机、能耗积分、自愈流程和 API 响应都有稳定测试。
4. **配置可追溯**：每个运行实例都能知道配置来自哪个文件、哪些环境变量覆盖了哪些字段、使用了什么指标口径。
5. **故障可解释**：网络超时、串口断开、传感器数据过期、AI 输出非法、日志损坏等情况都有明确错误类型和降级路径。
6. **迁移可回滚**：旧入口在迁移期间继续可用；每个阶段通过兼容适配层逐步切换，而不是一次性删除旧代码。
7. **前后端契约一致**：API 响应具有明确 schema，React、Streamlit 和测试使用同一套字段语义。
8. **为实测留接口**：能耗、舒适度、动作次数、数据质量、实验模式和校准信息都能进入统一数据模型。

### 3.2 本轮明确不做的事情

以下内容不应在第一轮重构中抢占主线：

- 不在没有真实数据和安全约束的情况下直接部署强化学习控制。
- 不在没有稳定指标定义的情况下引入 RAG、向量数据库或复杂知识图谱。
- 不把仿真节能率包装成真实实测成果。
- 不为了“看起来先进”而一次性引入 Kubernetes、微服务集群或消息中间件。
- 不在没有回归测试的情况下删除旧入口。
- 不把 API 密钥写入 YAML、固件或日志。

---

## 4. 重构原则与工作方式

### 4.1 代码原则

- 一个模块只负责一个主要变化原因。
- 领域对象优先于裸字典；外部输入先解析，再进入领域层。
- 适配器依赖接口，业务层不直接依赖 `serial.Serial`、OpenAI SDK、Streamlit 或 FastAPI。
- 时间分为“事件时间”和“单调时间”：前者用于展示和对齐数据，后者用于超时、冷却和限频。
- 失败必须分类：输入无效、设备离线、网络超时、服务拒绝、配置错误和内部程序错误不能全部使用 `Exception` 混在一起。
- 默认安全而非默认便利：AI `suggest` 默认开启，`execute` 必须显式配置且有额外审计。
- 尽量使用不可变数据对象传递状态快照，避免跨模块共享可变字典。

### 4.2 提交与分支原则

每个阶段建议拆成多个小提交，提交标题包含阶段编号，例如：

```text
refactor(p0): add command schema and audit events
refactor(p1): extract control cycle service
test(p1): cover hysteresis boundary transitions
fix(api): calculate sampling rate from timestamps
```

建议分支：

```text
main
├── refactor/p0-baseline-safety
├── refactor/p1-domain-boundaries
├── refactor/p1-ai-adapter
├── refactor/p1-api-contract
└── refactor/p2-observability-deployment
```

每个分支合并前都必须满足：

- 旧测试通过。
- 新增测试通过。
- 仿真结果已经比较。
- 没有把密钥、真实串口信息或运行日志提交进仓库。
- 变更说明写清楚“行为是否改变”。

### 4.3 不变式

在没有单独批准算法变更前，以下不变式必须保持：

- 规则控制器的 baseline/saving 模式含义不变。
- 温度滞回和最小启停时间的业务语义不变。
- AI 不能接管规则保留的继电器 1、2。
- 无硬件模式下不应尝试发送真实串口命令。
- 传感器无效或数据过期时系统必须进入安全降级，而不是继续使用不可信数据控制设备。
- 日志字段重命名必须提供迁移或兼容读取策略。

---

## 5. 目标架构

### 5.1 当前运行链路

```text
main.py
  ├─ 配置加载
  ├─ SerialBridge / DataAcquisition
  ├─ RuleBasedController
  ├─ AIAdvisor
  ├─ RuleActuationController
  ├─ EnergyAccumulator / Comfort
  ├─ ResilienceOrchestrator
  └─ LogManager

api_server.py ── 直接读取 JSONL + 直接计算摘要 + 返回 HTTP
 dashboard.py ── 直接读取日志并渲染 Streamlit
 React ── 调用 API 响应
 ESP32 单文件 .ino ── 传感器、协议、命令、状态、自愈、主循环
```

### 5.2 目标运行链路

```text
入口层
  ├─ cli/run_edge.py
  ├─ cli/run_simulation.py
  ├─ api/app.py
  ├─ dashboard/streamlit_app.py
  └─ firmware/...

应用层
  ├─ EdgeRuntime
  ├─ ControlCycleService
  ├─ RecoveryService
  └─ ExperimentService

领域层
  ├─ models/telemetry.py
  ├─ models/commands.py
  ├─ models/control.py
  ├─ models/energy.py
  ├─ models/resilience.py
  └─ policies/

基础设施层
  ├─ adapters/serial_transport.py
  ├─ adapters/mqtt_transport.py
  ├─ adapters/ai_openai.py
  ├─ repositories/jsonl_repository.py
  ├─ repositories/experiment_repository.py
  ├─ observability/logging.py
  └─ clock.py

接口层
  ├─ API schema
  ├─ React TypeScript types
  ├─ Streamlit view models
  └─ ESP32 wire protocol
```

### 5.3 推荐目标目录

第一阶段不要求立即创建全部目录；以下是逐步迁移后的目标形态：

```text
EcoSentinel/
├─ pyproject.toml
├─ README.md
├─ docs/
│  ├─ architecture.md
│  ├─ api-contract.md
│  ├─ command-safety.md
│  ├─ experiment-protocol.md
│  └─ migration/
├─ config/
│  ├─ base.yaml
│  ├─ dev.yaml
│  ├─ simulation.yaml
│  ├─ hardware.yaml
│  └─ test.yaml
├─ src/ecosentinel/
│  ├─ cli/
│  ├─ application/
│  ├─ domain/
│  │  ├─ models/
│  │  ├─ policies/
│  │  └─ services/
│  ├─ infrastructure/
│  │  ├─ ai/
│  │  ├─ hardware/
│  │  ├─ persistence/
│  │  └─ observability/
│  ├─ interfaces/
│  │  ├─ api/
│  │  └─ dashboard/
│  └─ config/
├─ tests/
│  ├─ unit/
│  ├─ contract/
│  ├─ integration/
│  └─ e2e/
├─ app/
│  └─ src/
├─ firmware/
│  └─ esp32_s3_competition/
└─ scripts/
```

迁移早期可以继续保留现有 `energy_system/`，通过兼容导入逐步迁移；不要为了目录“漂亮”而先改动所有 import。

---

## 6. 分阶段实施路线

## 阶段 0：建立基线与重构护栏（P0，1—2 天）

### 目标

在任何大规模移动代码之前，冻结当前行为，建立可重复验证和可回滚的基线。

### 修改范围

主要涉及：

- `README.md`
- `requirements.txt`
- `tests/`
- `energy_system/simulation/compare.py`
- 新增 `docs/refactor-baseline.md`
- 新增 `scripts/collect_baseline.py`

### 具体任务

1. 固定 Python 版本、依赖安装方式和测试命令。
2. 保存一次当前测试输出和仿真输出，不把可能包含敏感信息的日志提交到仓库。
3. 为仿真增加明确参数输出：随机种子、时间步长、总时长、初始温度、天气输入版本、控制模式和模型参数摘要。
4. 将仿真结果保存为结构化 JSON，例如：

```json
{
  "schema_version": "1.0",
  "experiment_id": "baseline-2026-08-20",
  "dt_seconds": 300,
  "duration_days": 3,
  "mode": "saving",
  "energy_kwh": 57.18,
  "comfort_mean": 0.821
}
```

5. 为当前 API、仿真、硬件模式分别写一页运行说明，明确哪些命令需要硬件。
6. 建立“行为不变清单”，列出控制器输出、命令允许范围、日志核心字段和 API 路由。

### 验收标准

- `pytest tests -q` 通过。
- `python -m energy_system.simulation.compare` 能运行。
- 仿真输出中能看到全部实验参数。
- 重复运行相同参数时结果一致；若本模型存在随机性，则必须固定随机种子。
- 现有入口未被删除。

### 回滚点

本阶段只新增脚本和文档，不修改生产逻辑，天然可回滚。

---

## 阶段 1：P0 安全边界和错误分类（2—4 天）

### 目标

先解决最不应该拖到后面的安全问题：AI 命令执行边界、API CORS、密钥处理、异常分类和审计记录。

### 1.1 AI 命令从字符串升级为领域对象

当前 `validate_ai_commands()` 返回字符串列表。建议新增：

```python
class CommandType(str, Enum):
    RELAY = "relay"
    CURTAIN = "curtain"
    BUZZER = "buzzer"

@dataclass(frozen=True)
class RelayCommand:
    channel: int
    state: bool

@dataclass(frozen=True)
class CurtainCommand:
    action: CurtainAction
```

解析过程分为四步：

1. 外部模型输出解析。
2. 语法校验。
3. 领域范围校验。
4. 权限和运行模式校验。

不要让 API、AI 模块和串口桥分别实现一套命令解析。

建议新增文件：

- `energy_system/core/models/commands.py`
- `energy_system/core/command_parser.py`
- `energy_system/core/command_policy.py`
- `energy_system/core/audit_events.py`

保留 `validate_ai_commands()` 作为兼容入口，但内部转调新的解析器，并在迁移完成后标记弃用。

### 1.2 命令安全规则

至少实现以下规则：

- 继电器通道只能是 1—4。
- 继电器值只能是 0/1。
- AI 默认不能控制继电器 1、2。
- `CURTAIN` 只能是 `OPEN/CLOSE/STOP`。
- `BUZZER` 只能是 0/1。
- 每周期命令数不能超过配置上限。
- 单个命令长度、总 payload 长度和重复命令次数有限制。
- `execute` 模式必须满足显式配置、设备在线、安全模式关闭和最小执行间隔条件。
- 被拒绝的命令必须记录原始命令的脱敏摘要、拒绝原因、候选 ID、运行模式和时间戳。
- 不把 API 密钥、完整 Prompt 或可能包含隐私的传感器原始数据写入审计日志。

### 1.3 收紧 API 默认安全配置

修改 `api_server.py` 和配置模型：

- 开发环境允许配置本地前端来源。
- 生产环境来源必须来自配置，禁止默认 `*`。
- 当 `allow_credentials=True` 时，禁止 `allow_origins=["*"]`。
- 后续增加认证前，至少增加管理开关和安全警告；不能把未经认证的执行接口暴露到公网。
- API 只读路由与控制路由分离；控制路由默认关闭。

### 1.4 错误类型

新增有限的错误层次，例如：

```text
EcoSentinelError
├─ ConfigurationError
├─ InvalidTelemetryError
├─ CommandValidationError
├─ TransportError
│  ├─ SerialDisconnectedError
│  └─ MqttUnavailableError
├─ AIProviderError
│  ├─ AITimeoutError
│  ├─ AIResponseFormatError
│  └─ AICircuitOpenError
└─ PersistenceError
```

不要求所有地方一次性消灭 `except Exception`，但高风险边界必须先捕获更具体的异常，并在日志中保留 `error_type`、`operation`、`recoverable` 和 `correlation_id`。

### 验收标准

- 非法继电器通道、非法状态、规则保留通道、超量命令均有测试。
- `suggest` 模式不会发送 AI 命令。
- `execute` 模式在无硬件时不会假装发送成功。
- 生产配置下 CORS 不再是任意来源。
- 审计日志能区分 accepted/rejected/rate_limited/not_executed。
- 任何测试输出和日志中没有密钥值。

---

## 阶段 2：配置、时间和领域数据模型（P1，3—5 天）

### 目标

把配置和跨模块数据从“字段约定”升级为可校验的稳定契约。

### 2.1 配置分层

当前 `energy_system/config/params.yaml` 继续作为过渡配置，但目标拆成：

```text
config/base.yaml        # 所有环境共有的安全默认值
config/dev.yaml         # 本地开发
config/simulation.yaml  # 仿真参数
config/hardware.yaml    # 串口和硬件差异
config/test.yaml        # 测试专用
```

加载顺序建议：

```text
base.yaml
→ 环境文件
→ 显式 --config 参数
→ 环境变量覆盖
→ 启动时跨字段校验
```

密钥只从环境变量或外部密钥服务读取，不进入 YAML。

### 2.2 配置模型

现有 `runtime_config.py` 可以继续作为迁移起点，建议分成：

- `AppRuntimeConfig`
- `SerialConfig`
- `AIConfig`
- `ControlConfig`
- `ResilienceConfig`
- `EnergyAccountingConfig`
- `ApiConfig`
- `LoggingConfig`
- `SimulationConfig`

增加跨字段校验：

- `control_mode=execute` 时必须显式启用硬件执行权限。
- `safe_mode_stale_s` 必须大于采样超时和串口读取超时。
- `reset_cooldown_s` 不得小于 `action_cooldown_s`。
- `max_ai_cmds_per_cycle` 不能为负数。
- `api.allow_credentials=true` 时不允许来源列表包含 `*`。
- 碳因子和电价必须带单位、来源和版本。

### 2.3 时间抽象

新增：

```python
class Clock(Protocol):
    def now(self) -> datetime: ...
    def monotonic(self) -> float: ...
```

生产使用系统时钟，测试使用 `FakeClock`。以下模块必须改为注入时钟：

- `RuleActuationController`
- `AIAdvisor`
- `ResilienceOrchestrator`
- `EnergyAccumulator`
- 日志和采样窗口服务

这样可以稳定测试“等待 10 分钟”“冷却 120 秒”“数据过期 30 秒”等边界，不再依赖真实睡眠。

### 2.4 Telemetry 模型

建议新增 `TelemetrySample`，至少包含：

- `timestamp`
- `temperature_c`
- `humidity_pct`
- `illuminance_lux`
- `eco2_ppm`
- `tvoc_ppb`
- `power_w`
- `solar_power_w`
- `relay_states`
- `source`
- `quality`
- `schema_version`

所有串口、模拟器和测试输入先转换为该模型，再进入控制器。缺失字段使用明确的 `None` 和质量标记，不要默默用 25°C、50% 等默认值掩盖数据缺失；如果确实要使用估计值，要写入 `field_estimated=true`。

### 验收标准

- 配置错误可以定位到字段路径。
- 相同配置在仿真和测试中解析结果一致。
- 生产代码不直接调用 `time.monotonic()`，而是通过时钟接口或封装函数。
- 无效传感器输入不会直接进入执行链。
- 新模型有序列化和反序列化测试。

---

## 阶段 3：控制器与执行链路拆分（P1，4—7 天）

### 目标

将“决定做什么”和“把命令发给设备”分开，使控制策略可以在无硬件环境中单测和仿真。

### 3.1 拆分 `controller.py`

当前 `controller.py` 同时包含动作数据、滞回状态机和规则控制器。建议拆分：

```text
energy_system/core/control/
├─ action.py              # ControlAction、HVACAction、LightingAction
├─ schedule.py            # 时段设定点计划
├─ hysteresis.py          # 滞回状态机
├─ rule_policy.py         # 温度与灯光策略
└─ service.py             # 组装策略并生成控制计划
```

命名建议：

- `T_in` → `indoor_temperature_c`
- `T_set` → `target_temperature_c`
- `I_solar` → `solar_irradiance_w_m2`
- `power_ac` → `hvac_power_w` 或明确单位的功率字段
- `is_heating` → `hvac_mode` 枚举

### 3.2 引入 ControlPlan

控制器不要直接返回串口字符串，而返回：

```text
ControlPlan
├─ generated_at
├─ policy_name
├─ hvac_action
├─ lighting_action
├─ reason_codes
├─ blocked_actions
└─ requires_confirmation
```

再由 `CommandCompiler` 把 `ControlPlan` 编译为允许的设备命令。规则策略和 AI 策略都只能生成计划，不能直接调用 `SerialBridge`。

### 3.3 执行器接口

定义：

```python
class ActuatorTransport(Protocol):
    def send(self, command: DeviceCommand) -> CommandResult: ...
    def health(self) -> TransportHealth: ...
```

实现：

- `SerialActuatorTransport`
- `MockActuatorTransport`
- 后续可选 `MqttActuatorTransport`

`RuleActuationController` 改名或逐步迁移为 `ActuationService`，只负责：

1. 接收控制计划。
2. 检查状态差异和最小间隔。
3. 调用 transport。
4. 记录结果。

### 3.4 明确控制优先级

推荐固定优先级：

```text
安全模式
→ 设备离线保护
→ 规则控制边界
→ AI 建议融合
→ 动作去抖与最小间隔
→ 执行器发送
→ 结果审计
```

AI 不能绕过安全模式、最小运行时间、最小停止时间和设备健康检查。

### 验收标准

- 规则控制器可以在完全没有串口、网络和 Streamlit 的情况下运行。
- 相同 `TelemetrySample` 输入得到确定性的 `ControlPlan`。
- 控制器单测覆盖 0/7/9/18/22/24 点边界。
- 覆盖 15 分钟最小运行、10 分钟最小停止和状态同步。
- 执行器只发送发生变化且通过限频的动作。
- 发送失败不会被记录为成功。

---

## 阶段 4：AI Advisor 拆分与安全降级（P1，5—8 天）

### 目标

把 AI 从“大而全的业务模块”拆成可替换的建议服务，同时保证 AI 永远不能成为未经验证的硬件命令入口。

### 4.1 拆分模块

当前 `energy_system/algorithms/ai_advisor.py` 建议迁移为：

```text
energy_system/ai/
├─ models.py              # AIRequest、AIResponse、AIRecommendation
├─ provider.py            # AIProvider 协议
├─ openai_provider.py     # OpenAI 兼容适配器
├─ prompt_builder.py      # 仅允许白名单字段进入 Prompt
├─ response_parser.py     # JSON/schema 解析
├─ candidate_selector.py  # 候选池与探索策略
├─ circuit_breaker.py     # 熔断状态机
├─ fallback_policy.py     # 本地回退策略
└─ service.py              # AIAdvisorService 外观
```

### 4.2 强类型输出

模型输出先解析为：

```text
AIRecommendation
├─ recommendation_id
├─ reasoning_summary
├─ requested_actions
├─ confidence
├─ source
├─ candidate_id
├─ latency_ms
├─ schema_version
└─ warnings
```

`requested_actions` 必须是结构化对象，禁止把模型返回文本直接交给串口桥。

### 4.3 Prompt 数据最小化

Prompt 只允许进入控制所需的字段：温度、湿度、照度、空气质量、功率、模式、时间段和数据质量。以下信息默认不进入：

- API 密钥。
- 文件系统路径。
- 内部异常堆栈。
- 未经脱敏的用户信息。
- 完整历史日志。
- 可让模型伪造系统指令的内部配置。

### 4.4 候选池和熔断器

候选选择、评分和熔断独立后，分别测试：

- 候选为空时的默认策略。
- 候选超时后的重试顺序。
- 连续失败达到阈值时熔断。
- 熔断冷却结束后的半开探测。
- 所有云端候选失败时本地回退。
- 本地回退被禁用时进入“无动作但可解释”状态。

### 4.5 AI 执行模式

建议将 `execute` 拆为更明确的权限：

```text
suggest                  # 默认，只返回建议
execute_safe_devices     # 只允许非关键设备
execute_all              # 仅实验环境，必须显式启用
```

当前竞赛和真实部署默认只能使用 `suggest` 或 `execute_safe_devices`。`execute_all` 不应作为普通配置默认值，也不应在没有认证和审计的 API 中开放。

### 验收标准

- AI 服务可以用 fake provider 测试，不需要真实 API。
- 任意非法 JSON、字段缺失、超范围 confidence 和非法动作都会被拒绝或降级。
- 云端超时、HTTP 错误、返回格式错误和熔断状态分别可观测。
- AI 失败不影响规则控制器继续运行。
- AI 产生的每条建议都有候选 ID、来源、延迟、接受/拒绝结果和审计关联 ID。
- 测试中不使用真实密钥、不向日志写入密钥。

---

## 阶段 5：自愈、数据质量和可靠性重构（P1，3—5 天）

### 目标

让自愈系统从“字符串动作计划 + 字典事件”升级为可解释、可限频、可审计的状态机。

### 修改范围

- `energy_system/resilience/orchestrator.py`
- `energy_system/core/data_acquisition.py`
- `energy_system/hardware/serial_bridge.py`
- `energy_system/core/log_manager.py`
- 新增 `energy_system/resilience/models.py`
- 新增 `energy_system/resilience/policies.py`

### 具体任务

1. 将 `CLOSED`、`OPEN`、`HALF_OPEN` 等状态改为枚举，避免字符串拼写错误。
2. 将 `I2C_RECOVER`、`RESET`、`MANUAL_INTERVENTION` 等动作改为动作枚举。
3. 把动作计划、动作执行结果、事件审计记录分别建模，明确 `planned`、`executed`、`succeeded`、`skipped` 和 `failed` 的区别。
4. 继续保持“编排器负责规划、调用方负责执行”的边界，但新增统一的 `RecoveryExecutor` 接口。
5. 为每个动作增加幂等键，防止同一个故障周期重复发送恢复命令。
6. 对数据过期、串口断开、JSON 解析失败、I2C 异常和 MCU 复位分别设置错误码。
7. 记录故障首次发生、最近一次样本、恢复尝试次数、冷却剩余时间和最终状态。
8. JSONL 写入采用临时文件/单行原子追加策略；读取时允许跳过坏行，但必须统计坏行数量并在健康状态中展示。
9. 将心跳、样本、动作和事故事件分开写入不同的逻辑记录类型，避免 API 通过猜字段判断记录类型。

### 验收标准

- 故障状态转换有单元测试和状态转换表。
- 相同事故在冷却窗口内不会重复执行不可幂等动作。
- 硬件未连接时只能生成“待人工执行”或“未执行”事件，不能伪造成功。
- JSONL 中有坏行时 API 仍可返回有效数据，同时报告 `corrupt_records`。
- 连续无数据会按预期进入安全模式，并在恢复后正确退出。
- 自愈动作顺序、限频和每小时复位上限均有测试。

---

## 阶段 6：`main.py` 应用编排拆分（P1，4—6 天）

### 目标

把 422 行左右的主入口降级为“组装依赖和启动运行时”，将实际业务流程迁移到可测试的应用服务。

### 修改范围

- `main.py`
- 新增 `energy_system/application/runtime.py`
- 新增 `energy_system/application/control_cycle.py`
- 新增 `energy_system/application/dependency_container.py`
- 新增 `energy_system/application/state.py`
- 新增 `energy_system/cli/run_edge.py`

### 迁移步骤

1. 先把 `EnergySystemApp` 的初始化拆为依赖工厂：配置、时钟、采集器、AI 服务、控制服务、执行器、持久化和恢复服务。
2. 将 `_compute_comfort()` 和 `_compute_energy()` 迁移到 `TelemetryEnrichmentService`，输入输出使用 `TelemetrySample` 和 `MetricSnapshot`。
3. 将 `_run_ai_cycle()` 迁移到 `DecisionService`，主循环只接收 `DecisionResult`。
4. 将 `_handle_no_data()` 和 `_trigger_self_healing()` 迁移到 `RecoveryService`。
5. 将 `_enrich_and_log()` 迁移到 `TelemetryRecorder`，区分样本记录和事件记录。
6. 将 `_sleep_until()` 变成注入式 `Scheduler`，测试中使用 fake clock，不进行真实等待。
7. 保留 `main.py` 作为兼容入口，内部调用 `run_edge()`；迁移完成后只保留参数解析、配置加载、依赖组装和退出码处理。

### 目标主循环

```python
while runtime.running:
    sample = acquisition.read()
    result = control_cycle.process(sample)
    recorder.record(result)
    scheduler.wait_until_next_tick()
```

### 验收标准

- 主循环业务代码不直接创建 OpenAI 客户端、串口对象或日志文件。
- `ControlCycleService` 可使用 fake acquisition、fake AI provider 和 mock actuator 单独测试。
- 无数据、坏数据、AI 超时和执行失败均能通过 `DecisionResult` 传递，而不是依赖隐式修改共享字典。
- 旧命令 `python main.py` 仍然可用。
- 新命令 `python -m energy_system.cli.run_edge --config ...` 可用。

---

## 阶段 7：能耗、实验记录和统一数据管道（P1，3—5 天）

### 目标

让能耗和舒适度指标有统一来源，为真实计量闭环和答辩证据准备数据基础。

### 修改范围

- `energy_system/power/energy_accounting.py`
- `energy_system/algorithms/comfort_eval.py`
- `energy_system/simulation/compare.py`
- `energy_system/simulation/simulator.py`
- `api_server.py`
- 新增 `energy_system/domain/metrics.py`
- 新增 `energy_system/experiments/manifest.py`

### 具体任务

1. 所有功率字段明确单位，统一内部计算单位为 W、时间为秒、能量为 Wh/kWh。
2. 对采样间隔异常、时间戳倒退、重复样本和大间隔进行处理并记录质量告警。
3. 将碳因子、电价、计量点和适用区域放进 `EnergyAccountingConfig`，摘要中返回：
   - `value`
   - `unit`
   - `factor_source`
   - `factor_version`
   - `calculation_window`
4. 仿真与实测采用同一个 `MetricSnapshot` 输出结构。
5. 实验清单至少包含：实验 ID、模式、开始/结束时间、设备/模拟器版本、配置哈希、采样周期、原始 JSONL 路径、汇总表路径和备注。
6. baseline 与 saving 实验支持交替或随机化顺序，避免把天气变化误判成控制策略效果。
7. 汇总报告输出均值、标准差、样本数和置信区间；在样本不足时明确标记“仅描述性统计”。

### 验收标准

- 能耗积分在固定样本下有可手算对照测试。
- 时间戳异常不会静默产生负能耗。
- API 和 Streamlit 使用同一套摘要服务。
- 仿真结果中包含实验条件和参数哈希。
- 真实电表数据可以通过适配器进入同一数据模型，而不需要改控制器。

---

## 阶段 8：FastAPI API 重构与契约测试（P1，4—6 天）

### 目标

把 `api_server.py` 从单文件脚本变成“路由—服务—仓储—schema”分层的只读监控 API，并为未来认证控制预留边界。

### 目标目录

```text
energy_system/interfaces/api/
├─ app.py
├─ dependencies.py
├─ schemas.py
├─ routes/
│  ├─ health.py
│  ├─ telemetry.py
│  ├─ energy.py
│  ├─ ai.py
│  └─ simulation.py
└─ services/
   ├─ snapshot_service.py
   ├─ chart_service.py
   └─ summary_service.py
```

### 具体任务

1. 将 `_read_log_tail()`、`_read_log_last()` 迁移到 `JsonlTelemetryRepository`。
2. 将 `/api/snapshot`、`/api/chart`、`/api/energy-summary` 的业务逻辑迁移到服务层。
3. 使用 Pydantic response schema 明确字段类型、单位、可选性和 `schema_version`。
4. `get_health()` 的采样率改为根据有效时间戳计算，数据不足时返回 `null` 和原因，而不是伪造固定值。
5. 图表查询按时间窗口过滤，例如 `5m`、`1h`、`24h` 转换为时间范围；行数只作为最大返回条数。
6. 电价和碳因子来自配置/实验清单，响应带来源和版本。
7. CORS 通过配置读取；默认只允许本地开发来源。
8. 统一 HTTP 错误响应格式：`code`、`message`、`request_id`、`details`。
9. 为日志文件不存在、空文件、坏行、权限错误和配置错误分别设置行为。
10. 保留 `api_server.py` 兼容启动入口，内部调用新的 `create_app()`。

### 验收标准

- API 路由不直接打开日志文件。
- API schema 测试覆盖正常、空数据、坏行和字段缺失。
- `/api/health` 不再固定返回与主循环无关的采样率。
- 通过 TestClient 可以在无硬件环境测试全部只读接口。
- 开发/生产 CORS 行为有测试。
- 前端使用的类型字段与 OpenAPI/schema 保持一致。

---

## 阶段 9：Streamlit 与 React 前端重构（P1/P2，4—7 天）

### 目标

使两个展示端只负责展示和交互，不重复计算核心指标，不自行猜测后端字段。

### Streamlit 任务

涉及：

- `dashboard.py`
- `dashboard/data_loader.py`
- `dashboard/energy_view.py`
- `dashboard/realtime_view.py`
- `dashboard/hardware_status.py`
- `dashboard/simulation_view.py`

具体任务：

1. `dashboard.py` 只保留页面导航、配置和视图组装。
2. 数据读取统一通过 `DashboardDataClient`，不要每个页面自行读 JSONL。
3. 每个视图使用 view model，避免直接依赖后端内部字典。
4. 所有指标显示单位、时间窗口和数据新鲜度。
5. API 不可用时显示“数据不可用/最后成功时间/原因”，不要显示看似正常的零值。
6. 将 baseline/saving 的仿真结果标注为仿真，不与实测卡片混在一起。

### React 任务

涉及：

- `app/src/services/api.ts`
- `app/src/types/index.ts`
- `app/src/store/useAppStore.ts`
- `app/src/pages/`
- `app/src/components/`

具体任务：

1. `types/index.ts` 成为前端领域类型入口。
2. `api.ts` 统一请求超时、错误解析、重试和 request ID。
3. 后端 schema 变化时先更新契约测试，再更新页面。
4. 将实时数据、能耗、AI 建议、健康状态和仿真页面的加载状态/错误状态统一处理。
5. 显示 AI 建议时明确 `suggestion`、`accepted`、`rejected`、`executed` 状态，避免把“模型返回”显示成“设备已执行”。
6. 增加前端 lint、typecheck、build 作为合并门禁。
7. 后续可用 OpenAPI 生成 TypeScript 类型，但第一阶段不为生成工具增加不必要的运行时复杂度。

### 验收标准

- API 断开时页面有可理解的错误状态。
- 前端构建和 lint 通过。
- 页面不再重复实现节能率或碳排放计算。
- 仿真和实测数据有明显标签。
- AI 建议和实际执行状态不会混淆。

---

## 阶段 10：ESP32 固件分层重构（P1/P2，7—12 天）

### 目标

将单个约 1183 行的 `.ino` 文件拆成可读、可诊断、协议稳定的固件模块，同时保持当前串口协议兼容。

### 建议目录

```text
firmware/esp32_s3_competition/
├─ esp32_s3_competition.ino   # setup/loop 最薄入口
├─ config.h                    # 引脚、采样周期、功能开关
├─ types.h                    # SensorFrame、DeviceState、CommandResult
├─ sensors/
│  ├─ sensor_manager.h
│  ├─ dht_sensor.h
│  ├─ bh1750_sensor.h
│  ├─ sgp30_sensor.h
│  └─ ina219_sensor.h
├─ protocol/
│  ├─ serial_protocol.h
│  ├─ json_codec.h
│  └─ command_parser.h
├─ actuators/
│  ├─ relay_controller.h
│  ├─ curtain_controller.h
│  └─ buzzer_controller.h
├─ resilience/
│  ├─ i2c_recovery.h
│  ├─ watchdog_manager.h
│  └─ health_reporter.h
└─ diagnostics/
   └─ diagnostic_commands.h
```

### 具体任务

1. 先画出现有 `setup()`、`loop()`、串口命令和传感器读取调用图。
2. 把常量、GPIO、I2C 地址和功能开关移到 `config.h`，禁止散落魔法数字。
3. 用 `SensorFrame` 统一传感器输出，明确缺失值和错误码。
4. 协议层只负责收发和解析，不直接操作传感器或继电器。
5. 命令路由只接受明确枚举和参数范围，非法命令返回结构化错误。
6. 继电器、窗帘和蜂鸣器分别维护状态，避免一个巨大命令函数处理所有设备。
7. I2C 恢复、看门狗和复位次数限制独立成可靠性模块。
8. 保留旧命令兼容期；新协议增加 `protocol_version` 和 `request_id`。
9. 将 `PINMAP`、`I2C_SCAN`、`READ_SENSORS` 等诊断命令列入文档，并对输出结构做版本化。

### 验收标准

- 固件编译通过，烧录后能完成启动、传感器读取和状态上报。
- 旧版 Python 串口桥仍能解析新版固件的核心数据。
- 非法命令不会改变设备状态。
- 传感器缺失时上报错误质量，不输出伪造正常值。
- I2C 恢复和 MCU 复位均有次数限制和诊断记录。
- 引脚定义、接线文档和固件实际配置一致。

---

## 阶段 11：测试体系、CI/CD 和质量门禁（P1/P2，4—7 天）

### 11.1 测试分层

```text
tests/unit/
  配置、解析器、控制策略、滞回、自愈、能耗、AI schema

tests/contract/
  API response schema、串口协议、前后端字段契约

tests/integration/
  fake acquisition → control cycle → mock actuator → repository

tests/e2e/
  simulation compare、API TestClient、Dashboard data client

tests/golden/
  固定参数仿真结果和关键日志字段
```

### 11.2 必须补齐的测试

- 配置：缺文件、空文件、类型错误、范围错误、跨字段冲突、环境变量覆盖。
- 控制：时段边界、温度边界、滞回、最小启停、灯光策略、模式切换。
- 命令：非法语法、越界通道、保留通道、重复命令、超量、执行权限。
- AI：schema、超时、重试、熔断、回退、Prompt 白名单、密钥不落日志。
- 协议：坏 JSON、部分字段、类型错误、乱码、过长行、串口断开。
- 自愈：冷却、限频、动作顺序、人工介入、恢复后清理状态。
- 能耗：时间戳倒退、长间隔、零功率、功率突变、单位转换。
- API：空文件、坏行、窗口查询、健康采样率、CORS 和错误格式。
- 集成：无硬件模式完整周期、AI 失败仍执行规则、执行器失败进入审计。

### 11.3 质量门禁

Python：

```powershell
python -m pytest tests -q
python -m compileall energy_system main.py api_server.py dashboard.py
```

如果依赖允许，再逐步加入：

```powershell
ruff check .
ruff format --check .
mypy energy_system
```

React：

```powershell
cd app
npm run lint
npm run build
```

仿真回归：

```powershell
python -m energy_system.simulation.compare
```

固件：使用 Arduino IDE 或 PlatformIO 编译；编译输出、板卡型号、库版本和引脚配置写入实验记录。

### 11.4 CI 建议

第一版 CI 只做轻量门禁：

1. Python 依赖安装。
2. 单元测试。
3. 编译检查。
4. 仿真 smoke test。
5. React lint/build。
6. secret scan 和敏感文件检查。

后续再加入覆盖率阈值、OpenAPI 契约差异检查和固件编译矩阵。不要一开始就把所有部署步骤塞进 CI，导致开发者因环境问题绕过门禁。

---

## 7. P0/P1/P2 排期建议

| 时间 | 优先级 | 重点结果 | 不应做的事 |
|---|---|---|---|
| 第 1—2 天 | P0 | 基线、仿真参数记录、行为快照 | 不移动大量文件 |
| 第 3—6 天 | P0 | 命令 schema、白名单、审计、CORS 收紧 | 不开放未认证执行 API |
| 第 1 周 | P1 | 配置分层、时钟接口、Telemetry 模型 | 不改变控制算法目标 |
| 第 2 周 | P1 | 控制器/执行器拆分、主循环服务化 | 不删除兼容入口 |
| 第 3 周 | P1 | AI provider、解析、熔断、回退拆分 | 不接入 RL 控制生产设备 |
| 第 4 周 | P1 | 自愈、日志、能耗指标统一 | 不把坏数据当正常数据展示 |
| 第 5 周 | P1 | API 分层和契约测试 | 不继续使用开放生产 CORS |
| 第 6 周 | P1/P2 | Streamlit、React、固件接口整理 | 不在没有实测数据时夸大指标 |
| 第 7 周以后 | P2 | CI/CD、观测、实验平台、部署优化 | 不为复杂而复杂 |

### 推荐交付里程碑

- **M0：可重复基线**——测试和仿真可复现。
- **M1：安全边界完成**——AI 命令可审计，生产 CORS 收紧。
- **M2：核心领域层完成**——控制和能耗不依赖硬件/API/UI。
- **M3：运行时拆分完成**——旧入口兼容，新入口可运行。
- **M4：接口契约完成**——API、React、Streamlit 字段统一。
- **M5：硬件模块化完成**——固件协议和诊断可维护。
- **M6：实测闭环准备完成**——可导入电表数据并生成可追溯报告。

---

## 8. 详细文件迁移清单

### 第一批：先新增，不破坏旧代码

```text
energy_system/core/models/commands.py
energy_system/core/models/telemetry.py
energy_system/core/models/events.py
energy_system/core/clock.py
energy_system/core/errors.py
energy_system/core/audit_events.py
energy_system/ai/provider.py
energy_system/ai/response_parser.py
energy_system/api/schemas.py
energy_system/persistence/jsonl_repository.py
tests/unit/test_commands.py
tests/unit/test_clock.py
tests/contract/test_api_schema.py
docs/command-safety.md
docs/refactor-baseline.md
```

### 第二批：迁移调用方

```text
energy_system/core/command_dispatcher.py
energy_system/core/controller.py
energy_system/core/data_acquisition.py
energy_system/core/log_manager.py
energy_system/algorithms/ai_advisor.py
energy_system/resilience/orchestrator.py
api_server.py
main.py
```

### 第三批：兼容层与清理

- `main.py` 保留兼容入口。
- `api_server.py` 保留兼容启动参数。
- `validate_ai_commands()` 保留一段过渡期。
- 旧日志字段提供读取兼容，不再新增旧字段。
- 在文档中标注弃用时间和替代接口。
- 旧代码连续两个版本未被调用、且测试覆盖充分后再删除。

---

## 9. 统一日志与可观测性规范

### 9.1 日志字段

每条结构化记录建议包含：

```text
schema_version
record_type
timestamp
monotonic_elapsed_s
request_id
correlation_id
run_id
source
severity
operation
status
error_type
error_code
message
```

业务记录再按类型增加字段，例如样本的温度和功率、动作的命令摘要和结果、AI 建议的候选 ID 和解析状态。

### 9.2 日志级别

- `DEBUG`：开发诊断，不默认持久化。
- `INFO`：周期摘要、状态变更、实验关键事件。
- `WARNING`：可恢复异常、数据质量问题、回退。
- `ERROR`：操作失败但进程仍可运行。
- `CRITICAL`：必须进入安全状态或人工介入。

### 9.3 日志禁区

严禁写入：

- API key、token、密码。
- 完整认证头。
- 未脱敏的外部服务响应。
- 能够反推出密钥的调试信息。
- 无必要的完整 Prompt。

---

## 10. 风险清单与应对措施

| 风险 | 触发方式 | 影响 | 应对 |
|---|---|---|---|
| 重构改变控制行为 | 移动代码时修改边界条件 | 设备动作变化 | 先做 golden tests，再迁移 |
| 新旧模型字段不一致 | Telemetry 字段改名 | API/看板报错 | schema_version + 适配器 |
| AI 解析过严导致建议减少 | 模型返回格式波动 | 建议数量下降 | 本地回退 + 记录原因 |
| API 安全配置误伤开发 | CORS 来源未配置 | 前端无法访问 | dev 配置显式列来源 |
| JSONL 并发读写冲突 | 看板读取写入中的行 | 数据解析错误 | 原子追加、坏行统计、重试 |
| 串口桥迁移失败 | Windows 端口行为差异 | 硬件无法连接 | 保留旧适配器和诊断脚本 |
| 固件拆分引脚漂移 | 常量迁移错误 | 传感器失效 | 编译前后 PINMAP 测试和实测 |
| 过度抽象拖慢竞赛 | 一次性引入太多层 | 开发延期 | 每阶段独立可运行 |
| 指标口径漂移 | 电价/碳因子改变 | 答辩数据不一致 | 实验清单记录来源版本 |
| 异常被吞掉 | 宽泛 `except Exception` | 故障难排查 | 错误分类 + 结构化日志 |

---

## 11. 回滚策略

### 11.1 代码回滚

- 每个阶段一个可合并分支。
- 每个迁移步骤保留旧入口和新入口。
- 新服务通过 feature flag 切换，默认先走旧路径或 shadow mode。
- 发生回归时先关闭 feature flag，不立即回退整个分支。
- 只有在旧路径与新路径结果对照完成后，才删除兼容代码。

### 11.2 数据回滚

- 日志 schema 增加 `schema_version`。
- 读取器至少兼容最近两个版本。
- 新字段只能追加，暂不原地覆盖旧字段含义。
- 实验结果以新文件写出，不覆盖原始 JSONL。
- 仿真报告保存配置哈希，不能只保存最后一个数字。

### 11.3 硬件回滚

- 固件升级前保存可启动旧固件。
- 保留旧串口协议兼容期。
- 先在模拟器和脱机串口回放中验证，再接入真实执行器。
- 继电器和空调控制改动必须先在断开负载或安全测试负载上验证。
- 任何通信异常都应回到安全状态，而不是反复发送未知命令。

---

## 12. 推荐开发命令与验证清单

### 12.1 Python 环境

```powershell
python --version
python -m pip install -r requirements.txt
```

### 12.2 回归测试

```powershell
python -m pytest tests -q
python -m compileall energy_system main.py api_server.py dashboard.py
```

### 12.3 仿真

```powershell
python -m energy_system.simulation.compare
```

确认输出至少包含：

- baseline 总能耗。
- saving 总能耗。
- 节省电量。
- 节能率。
- baseline/saving 舒适度。
- 仿真条件和配置标识。

### 12.4 API

```powershell
python api_server.py --host 127.0.0.1 --port 8080
```

然后验证：

```text
GET /api/ping
GET /api/health
GET /api/snapshot
GET /api/chart?range=5m
GET /api/energy-summary
GET /api/simulation/params
```

### 12.5 Streamlit

```powershell
streamlit run dashboard.py
```

验证：

- 无日志文件时页面不崩溃。
- 日志有坏行时显示数据质量提示。
- API 或硬件离线时不显示伪造的正常状态。
- 仿真数字明确标注为仿真。

### 12.6 React

```powershell
cd app
npm install
npm run lint
npm run build
npm run dev
```

### 12.7 硬件前置检查

```powershell
python scripts/list_serial_ports.py
python scripts/hardware_autodiag.py --help
python scripts/sniff_serial.py --help
```

真实硬件测试必须记录板卡型号、固件版本、传感器接线、端口、采样周期和原始数据位置。不能只截取看板截图作为唯一证据。

---

## 13. 竞赛答辩中的重构表述

推荐说法：

> 我们没有把系统一次性推倒重写，而是采用“先冻结行为、再拆分边界、最后升级能力”的渐进式重构。第一步固定仿真和规则控制的可复现基线；第二步把 AI 输出转成经过白名单和参数校验的领域命令，并保留审计；第三步将采集、决策、执行、日志和 API 解耦。这样做的好处是：即使云端 AI 不可用，规则控制和本地安全策略仍然能够独立运行；每一次代码变化也都可以通过测试和仿真对照验证。

需要避免的说法：

- “重构后已经达到 99.9% 可用性”。
- “AI 可以直接控制所有硬件”。
- “29.8% 已经是真实办公室实测节能率”。
- “系统已经完成 TLS、RBAC、OTA 回滚”，除非这些功能有源码和测试证据。
- “代码全部模块化、没有技术债务”。

### 答辩可展示的重构证据

1. 一张旧架构与目标架构对比图。
2. 一个非法 AI 命令被拒绝并进入审计日志的测试。
3. 一个 AI 超时后规则控制继续运行的演示。
4. 一个 JSONL 坏行被隔离、API 仍返回健康数据的测试。
5. 一次固定参数仿真前后结果对照。
6. 一张测试数量、模块覆盖范围和已知未完成项表格。

---

## 14. 最终完成判定

只有同时满足以下条件，才可以把本轮重构称为“完成”：

- P0 安全边界全部完成，并有自动化测试。
- 核心控制行为与基线对照通过，任何差异都有解释。
- 规则控制、AI 建议、硬件执行和自愈编排可以分别测试。
- API 不再直接承担日志解析和业务指标计算。
- CORS、密钥、错误响应和审计日志达到部署环境要求。
- 仿真和实测数据使用统一指标模型，但报告中明确区分来源。
- React、Streamlit、FastAPI 的字段契约一致。
- 固件协议有版本号、非法命令处理和诊断入口。
- CI 至少能自动执行测试、编译检查、仿真 smoke test 和前端构建。
- 旧入口完成迁移后再删除，且有回滚说明。

最终目标不是让目录看起来“更像大项目”，而是让每一个重要结论都能回答三个问题：

1. 这段代码负责什么？
2. 它依赖什么、失败时怎么办？
3. 如何用测试、日志或实验数据证明它确实工作？

这三个问题都能回答，重构才算真正完成；否则只是把文件搬了个家，技术债务仍然住在原地。
