# EcoSentinel 重构一步一步实操手册

> **怎么用这本手册**：从第 1 步开始，一步一做。每一步固定四段：**干什么**（这步做什么）→ **怎么干**（编号操作，命令和提示词直接复制，每条后面跟「预期看到」）→ **怎么验**（一条命令 + 预期结果，**不过不进下一步**）→ **错了怎么退**。中途卡住，查附录 B 排错表。
>
> **前置**：你手里有旧仓库 EcoSentinel 和一份《EcoSentinel 全项目深度审阅报告》（2026-10）。本手册所有缺陷编号（D1–D10）、重构编号（R1–R8）、验收数字都来自该报告实测，**不许智能体在执行中「优化」这些数字**。
>
> **时间假设**：单人，每天 3–4 小时有效会话，共 11 周 43 步。

---

> ## 🔧 修复版说明（2026-10-26 实测核对补丁）
>
> 本版在原手册基础上按**实测**更正如下（逐条依据见随附 `重构手册核对报告.md`）：
>
> | 类别 | 原手册 | 本版（实测） | 验证方式 |
> |---|---|---|---|
> | 测试总数 | 354 | **365 passed, 1 skipped** | `python -m pytest tests -q` |
> | `tests/unit` 文件数 | 32 | **33** | 目录计数 |
> | `tools/` 四个探针 | "迁移旧仓库脚本" | **旧仓库没有 ⇒ 改为新写**（步 11.3 给完整代码） | `Test-Path tools` = False |
> | `pytest -m perf` | 直接可跑 | **必红**（366 deselected）⇒ 步 19 给出 marker 注册法 | 实跑 |
> | `energy_system.api.api_server` | 服务入口 | **不存在** ⇒ 用 `${REPO}/api_server.py` | 无此文件 |
> | `TopBar.tsx` | `components/TopBar.tsx` | **`components/layout/TopBar.tsx`** | 实数 |
> | `firmware/*.h` | `firmware/x.h` | **`firmware/esp32_s3_competition/x.h`** | 实数 |
> | 12 个文件行数 | 偏小 10–70 行 | **全部改为实测值** | 逐文件计数 |
> | uv / pyproject | 假设旧仓库已有 | **旧仓库没有**（只有 requirements.txt） | 实数 |
>
> **未改动的部分**（43 步编排、四段式结构、"先钉行为再重构"的方法论、D1–D10 判词）
> 经核对**成立，可直接使用**。其中 **D1 已实测复现**：saving 模式下
> `sim.controller` 与 `_controllers["saving"]` 确非同一实例（前者 0，后者 134）。
>
> **本机实测环境**：Python **3.14.3**（非 3.12）；`uv` 已安装但仓库未 pin；
> 旧仓库基线 `pytest` = **365 passed, 1 skipped**；`simulation.compare` = **17.6%**。

## 开始之前：先认清四棵树

整个重构涉及四个目录，先认清它们的分工，后面 43 步都在这四棵树上操作：

```text
~/                                ← 你的 home 目录
├── EcoSentinel/                  ← ① 旧仓库。步 2 冻结为只读博物馆（tag + 裸备份 + chmod）
├── EcoSentinel-legacy-backup.git/← ② 旧仓库的裸备份。步 2 建，永远不动
├── EcoSentinel-work/             ← ③ 旧仓库的工作副本。步 17 建（补表征测试用），步 41 删
├── ecosentinel-config-draft/     ← ④ 配置文件草稿箱。步 3 建，步 9 用完即删
└── ecosentinel-v2/               ← ★ 新仓库。步 9 建，本手册 43 步建的就是它
```

### 旧仓库关键文件速查表

本手册引用的旧仓库位置全在这张表里。**旧仓库的 Python 代码全部在 `energy_system/` 包里**（报告 §1.3：15 个子包——core / application / algorithms / config / hardware / api / simulation / ai / resilience / utils / domain / persistence / power 等）；报告原文常把包内文件写成包内相对路径（如 `simulation/simulator.py`），**本表一律补全为仓库根相对路径**，你 `cd ~/EcoSentinel` 后照抄即可打开。`dashboard`（Streamlit）、`firmware`、`scripts`、`tools`、`tests` 在包外，就是仓库根的顶层目录。完整结构以旧仓库 README 为准；**查任何口径都来这张表对 file:line，不许凭记忆**。

| 旧仓库文件 | 是什么 | 手册哪步用 |
|---|---|---|
| `energy_system/simulation/simulator.py:29-35` | 仿真器；D1「读错实例」位置（`mode="saving"` 时 `self.controller` 与 `_controllers["saving"]` 不是同一实例） | 步 21 |
| `energy_system/simulation/compare.py:145` | **读错实例的调用点**（读 `sim_save.controller`；`run_compare` 在 :56，打印在 :163）（`python -m energy_system.simulation.compare` 实测 17.6%） | 步 21 |
| `energy_system/core/command_dispatcher.py:133-141` | D2「失败被当成功缓存」 | 步 22 |
| `energy_system/hardware/serial_bridge.py:324-356` | D2 下发路径；覆盖率盲区 16% | 步 17、22 |
| `energy_system/core/log_manager.py:21` | D8 CWD 相对路径 | 步 18 |
| `energy_system/core/log_manager.py:89-114` | D3 跨午夜电量重复累计 | 步 23 |
| `energy_system/persistence/jsonl_repository.py:74-99` | D5 全量读（17k 行 114ms / 120k 行 670ms） | 步 19 |
| `energy_system/persistence/jsonl_repository.py:39-41,106` | D9 label 路径穿越 | 步 31 |
| `energy_system/api/services.py:76,102` | D4 舒适度两套量纲（0.5 vs 50.0） | 步 26 |
| `energy_system/api/services.py:157,159,168,170` | D6 API 语义伪造（四个假字段） | 步 32 |
| `energy_system/api/app.py` | FastAPI 工厂，8 端点全在这（stack_acceptance 实测覆盖 7 个，7/7 200） | 步 33 |
| `api_server.py:33` | 仓库根入口；D8 绝对路径 | 步 18 |
| `api_server.py:60-68` | 仓库根入口；D9 默认绑 0.0.0.0 + 无鉴权 | 步 31 |
| `energy_system/algorithms/comfort_eval.py` | D4 量纲两套口径同文件（TCI 0–1 vs band_share IPMVP） | 步 26 |
| `energy_system/algorithms/comfort_kpi.py` `peak_kpi.py` `energy_saving.py` | KPI 口径三实现（band / peak / energy，**资产**） | 步 8、25 |
| `energy_system/core/audit_events.py` | 全仓零引用的审计模块（0% 覆盖） | 步 29 |
| `energy_system/ai/circuit_breaker.py` | 干净可注入的熔断（83 行）——**但只被测试引用**，生产用 advisor 内联副本 | 步 27、30 |
| `energy_system/resilience/orchestrator.py` | 「规划即置 OPEN、执行失败不回滚 → 假 OPEN」（报告 §6.5 判词） | 步 30 |
| `energy_system/config/config_loader.py` | 366 行手写配置解析（`load_app_config` 155 行） | 步 28 |
| `energy_system/config/env.py:20` | key 优先级不看 `api_base`（S4：Key 可跨厂商外发） | 步 28、31 |
| `energy_system/algorithms/ai_advisor.py` | AI 生产实现（323 行，「半提取」：自带统计与熔断副本） | 步 27 |
| `energy_system/ai/service.py` `models.py` `provider.py` | 半成品门面 / `HALF_OPEN` 死枚举 / Protocol 定义良好但 advisor 不用 | 步 27 |
| `energy_system/application/usecases.py` / `loop.py` / `runtime.py` | 决策循环（`usecases(app)` 无类型；`runtime.py` 16 个透传属性） | 步 29 |
| `energy_system/core/control/`（267 行） | `ControlPlan/Compiler/ActuationService/Transport`——**生产未接线**（控制层双实现的未接线方） | 步 24 |
| `energy_system/domain/telemetry.py` / `domain/metrics.py` | 单一真值 schema（写入链路没用）vs 指标注册表（仅测试用，单位表重复）——指标双实现 | 步 13、25 |
| `dashboard/data_loader.py:10-43` | **正确尾读实现（资产，照搬）**：seek 末 256KB，120k 行 1.1ms | 步 19 |
| `dashboard/data_client.py:64` | D8 绝对路径（70 行死代码） | 步 18 |
| `dashboard/ai_pool.py` | `read_jsonl(max_lines=500)` 读文件头 bug | 步 37 |
| `app/src/store/useAppStore.ts:94-100` `app/src/components/layout/TopBar.tsx:30` `app/src/services/api.ts:206` | D7 前端「假在线」三处 | 步 32、35 |
| `firmware/esp32_s3_competition/mqtt.h:17-20,49-57` | D10 MQTT 裸奔（**:17-18 明文 WiFi 凭据**；:19-20 公共 broker；:49-57 回调无鉴权） | 步 38 |
| `firmware/esp32_s3_competition/protocol.h:322-385` | D10 命令解析歧义 | 步 38 |
| `firmware/esp32_s3_competition/config.h` | `USE_MQTT` 硬开启 | 步 38 |
| `tests/`（unit 33 / contract 13 / 根 4，365 passed + 1 skipped） | 测试**资产**，数量以 pytest 收集为准 | 步 14、17 |
| `tools/dyn1.py` `dyn3.py` `perf.py` `api_probe.py` | 四个行为探针 | 步 11 |

### 新仓库完整目标树（43 步建完就是它）

```text
ecosentinel-v2/                          ← 新仓库根（步 9 建）
├── .python-version                      ← 步 3（内容一行：3.12）
├── .gitignore                           ← 步 9
├── .pre-commit-config.yaml              ← 步 3 写草稿，步 9 进库
├── pyproject.toml                       ← 步 3 写草稿，步 9 进库
├── uv.lock                              ← 步 9 首次 uv sync 生成
├── AGENTS.md                            ← 步 9（智能体宪法）
├── README.md                            ← 步 7 写路线第一段，随步 9 进库
├── config/
│   └── params.yaml                      ← 步 28（R5 配置文件）
├── src/
│   ├── energy_system/                   ← Python 包。import 前缀、覆盖率 --cov 目标都是它
│   │   ├── __init__.py                  ← 步 13
│   │   ├── contracts/                   ← 步 13：schema codegen 的 Py 产物（唯一事实源是 SPEC.md）
│   │   │   ├── __init__.py              ← 步 13（只导出契约类型）
│   │   │   └── telemetry.py             ← 步 13：gen_schemas.py 生成，禁止手改
│   │   ├── api/
│   │   │   ├── __init__.py              ← 步 13（只导出契约类型）
│   │   │   ├── server.py                ← 步 31：默认 127.0.0.1 + 鉴权中间件
│   │   │   └── services.py              ← 步 32：HealthService（无来源返回 null）
│   │   ├── service/
│   │   │   └── __init__.py              ← 步 13 空壳；步 29 充实（QueryService 等）
│   │   ├── simulation/                  ← 步 21：跑领域模型的应用设施（秩在 domain 之上，domain 不许依赖它）
│   │   │   ├── simulator.py             ← 步 21：D1 单实例修复
│   │   │   └── compare.py               ← 步 21：对外论据生成（读实际运行实例）
│   │   ├── domain/
│   │   │   ├── __init__.py              ← 步 13
│   │   │   ├── control/
│   │   │   │   ├── protocol.py          ← 步 24a：控制协议抽象（步 24 充实适配层）
│   │   │   │   ├── control_law.py       ← 步 24b：迁 core/controller.py 控制律
│   │   │   │   └── command_policy.py    ← 步 24b：迁 core/command_policy.py 四段校验
│   │   │   ├── ai/
│   │   │   │   ├── facade.py            ← 步 27：AiFacade 唯一门面
│   │   │   │   ├── circuit_breaker.py   ← 步 27：唯一熔断（以旧 ai/circuit_breaker.py 为准）；步 30 HALF_OPEN 真赋值
│   │   │   │   ├── prompt_builder.py    ← 步 27：白名单提示词（修 frozenset 顺序）
│   │   │   │   └── provider.py          ← 步 27：AiProvider Protocol
│   │   │   ├── command_dispatcher.py    ← 步 22：D2 缓存只认成功
│   │   │   ├── energy_ledger.py         ← 步 23：D3 跨午夜修复
│   │   │   ├── comfort.py               ← 步 26：D4 唯一量纲 [0,1]
│   │   │   ├── store.py                 ← 步 20：TelemetryStore Protocol
│   │   │   ├── telemetry.py             ← 步 25：单位表唯一真值（迁旧 domain/telemetry.py 设计）
│   │   │   ├── kpi.py                   ← 步 25：band/peak/energy 唯一实现（合并指标双实现）
│   │   │   ├── pipeline.py              ← 步 29：4 Protocol + DecisionPipeline
│   │   │   ├── runtime_state.py         ← 步 29
│   │   │   └── resilience.py            ← 步 29：ResilienceFSM；步 30 修「假 OPEN」
│   │   ├── infra/
│   │   │   ├── paths.py                 ← 步 18：D8 数据目录（禁 CWD 相对）
│   │   │   ├── data_store.py            ← 步 19：JsonlStore 尾读
│   │   │   ├── sqlite_store.py          ← 步 20：SqliteStore（WAL + ts 索引）
│   │   │   ├── hardware.py              ← 步 30：HardwareAbstraction 接口 + 假实现
│   │   │   └── log_paths.py             ← 步 31：label 白名单校验
│   │   ├── config/
│   │   │   ├── settings.py              ← 步 18 最小版；步 28 换 pydantic-settings 完整版
│   │   │   └── feature_flags.py         ← 步 9：flag 框架
│   │   └── testing/
│   │       └── shadow.py                ← 步 15：shadow_compare 双跑框架
│   ├── web/                             ← 步 35：React+TS 新前端
│   │   └── src/
│   │       ├── hooks/
│   │       │   └── useTelemetryQuery.ts ← 步 35：统一轮询 + dataSource
│   │       ├── store/
│   │       │   └── useAppStore.ts       ← 步 35：初始不播种 mock
│   │       ├── components/
│   │       │   └── TopBar.tsx           ← 步 35：徽标只信 dataSource
│   │       ├── lib/
│   │       │   └── format.ts            ← 步 26/35：全前端唯一允许的 ×100
│   │       └── contracts/               ← 步 13：codegen 产物（TS interface）
│   └── firmware/                        ← 步 38：固件加固
│       ├── contracts.h                  ← 步 13：codegen 产物（C struct）
│       ├── protocol.h                   ← 步 38：命令解析重设计
│       ├── config.h                     ← 步 38：USE_MQTT 默认 0
│       └── test_protocol.cpp            ← 步 38：负例测试
├── scripts/
│   ├── gen_schemas.py                   ← 步 13：schema codegen（唯一事实源是 SPEC.md）
│   ├── stack_acceptance.py              ← 步 33：全栈验收（顺序打 7 端点，第 43 步用）
│   ├── check_doc_numbers.py             ← 步 40：文档数字校验
│   └── health.py                        ← 附录 A.4：健康度六指标
├── tools/                               ← 步 11：四个行为探针（PROBE_TARGET 约定，见步 11）
│   ├── dyn1.py                          ← 阻断 0 vs 134
│   ├── dyn3.py                          ← 失败缓存 / 跨日电量 / label 穿越
│   ├── perf.py                          ← 670ms vs 1.1ms
│   └── api_probe.py                     ← API 假字段
├── tests/
│   ├── contract/
│   │   ├── test_layering.py             ← 步 9：分层秩测试（第一个真实 commit）
│   │   ├── test_schemas.py              ← 步 13：契约测试（从 422 行降到 <80 行）
│   │   └── test_api_contract.py         ← 步 33：7 端点基线（200 + 负例）
│   ├── perf/
│   │   └── test_data_store_perf.py      ← 步 19：120k 行 P95 < 50ms
│   ├── test_simulator.py                ← 步 21
│   ├── test_command_dispatcher.py       ← 步 22
│   ├── test_energy_ledger.py            ← 步 23
│   ├── test_control_protocol.py         ← 步 24：同种子 1000 步逐位相等
│   ├── test_kpi_merge.py                ← 步 25：shadow 对拍 + 尾窗/EER 失败测试
│   ├── test_comfort.py                  ← 步 26：量纲 [0,1] + 两端口径一致
│   ├── test_ai_facade.py                ← 步 27：契约测试全量迁移（不改断言）
│   ├── test_settings.py                 ← 步 28：坏配置 fail-loud 三类
│   ├── test_pipeline.py                 ← 步 29：4 Protocol + 审计事件
│   ├── test_resilience.py               ← 步 29 钉旧行为；步 30 改钉修复后行为（假 OPEN）
│   ├── test_hardware.py                 ← 步 30：假实现链路 + SecurityError 传播
│   ├── test_security.py                 ← 步 31：5 类穿越 payload + 绑定断言
│   ├── test_api_semantics.py            ← 步 32
│   └── （步 17 起的表征测试，随各模块迁移陆续进来）
├── docs/
│   ├── specs/
│   │   ├── SPEC.md                      ← 步 8：唯一事实源（只写四章）
│   │   └── SEAMS.md                     ← 步 10：8 个接缝裁决表
│   ├── contracts/                       ← 步 10：契约卡 C1–C8
│   ├── adr/
│   │   └── 0002-single-evolution-track.md  ← 步 7
│   ├── FLAGS.md                         ← 步 9：flag 登记册
│   ├── STATUS.md                        ← 每周五进度看板（附录 A.3）
│   └── FINDINGS.md                      ← 副智能体「发现但不处理」清单
└── .github/
    └── workflows/
        └── ci.yml                       ← 步 3 草稿，步 9 进库；步 34 加两岗
```

**三条贯穿全程的目录纪律**：

1. **Python 包叫 `energy_system`，不叫 `backend`**——import 写 `from energy_system.infra.paths import logs_dir`，覆盖率命令 `--cov=energy_system`，mypy 严格检查的模块名 `energy_system.domain.*` 等，全以它为准。**`simulation`/`contracts`/`testing` 与 `api`/`service`/`domain`/`infra` 平级，都是 `energy_system.` 下的一级包**（`simulation` 尤其别塞进 `domain/`——它跑领域模型，秩在 domain 之上，见第 9 步 AGENTS.md 秩测试）。
2. **每个引入 flag 的步，必须在 commit 里同步更新 `docs/FLAGS.md`**（flag 名 / 默认值 / 删除条件 / 引入步号）。flag 出生时就登记死期，这是步 41「flag 清零」能执行的前提。
3. **每步一个分支，24 小时内 squash 进 main**；commit message 带契约卡五字段（Intent/Scope/Boundaries/Evidence/Recovery）。分支长寿是死山温床。

---

## 全步骤地图（43 步）

| 步 | 干什么 | 周次 | 前置 |
|---|---|---|---|
| 1 | 指挥智能体的四步工作法（一页纸，先读） | 动工前 | — |
| 2 | 冻结旧仓库（只读博物馆） | 第 1 周 | 步 1 |
| 3 | 装 uv，写好三个配置文件草稿 | 第 1 周 | — |
| 4 | 安装 DSH 桌面版 | 第 1 周 | — |
| 5 | 配置两个模型（主 Kimi + 副 DeepSeek） | 第 1 周 | 步 4 |
| 6 | 冒烟测试：主副智能体都活着 | 第 1 周 | 步 5 |
| 7 | 选定演进路线（只选一条）+ ADR-0002 | 第 1 周 | 步 2 |
| 8 | 提炼 SPEC.md（唯一事实源，你签字） | 第 1 周 | 步 7 |
| 9 | 建新仓库 + CI + AGENTS.md + flag 框架 | 第 1 周 | 步 3、8 |
| 10 | 写契约卡 C1–C8 + SEAMS.md 裁决表 | 第 1 周 | 步 9 |
| 11 | 迁移四个行为探针到 tools/ | 第 1 周 | 步 10 |
| 12 | （你本人）递交专利申请 | 第 1 周内 | — |
| 13 | 分层骨架 + Pydantic 契约 + schema codegen（R1） | 第 2–3 周 | 步 11 |
| 14 | 迁移测试基建（不改断言） | 第 2–3 周 | 步 13 |
| 15 | 建 shadow 双跑框架 | 第 2–3 周 | 步 14 |
| 16 | 记录覆盖率基线 | 第 2–3 周 | 步 14 |
| 17 | 在工作副本补硬件/cli 表征测试（先测再改） | 第 4 周 | 步 16 |
| 18 | D8：统一数据目录 paths.py | 第 4 周 | 步 17 |
| 19 | D5：尾读 DataStore（性能拐点） | 第 4 周 | 步 18 |
| 20 | R2：SqliteStore（WAL + ts 索引） | 第 4 周 | 步 19 |
| 21 | D1：阻断计数读错实例 | 第 4 周 | 步 20 |
| 22 | D2：失败下发被当成功缓存 | 第 4 周 | 步 21 |
| 23 | D3：跨午夜电量重复累计 | 第 4 周 | 步 22 |
| 24 | 控制层合并（branch-by-abstraction 四小步） | 第 5–6 周 | 步 23 |
| 25 | 指标/KPI 层合并 | 第 5–6 周 | 步 24 |
| 26 | D4：舒适度量纲统一 + Dark Launch | 第 5–6 周 | 步 25 |
| 27 | R4：AI 层合并（门面 + 唯一熔断） | 第 5–6 周 | 步 26 |
| 28 | R5：配置 pydantic-settings 化 | 第 5–6 周 | 步 27 |
| 29 | R3：决策管线接口化（4 个 Protocol） | 第 5–6 周 | 步 28 |
| 30 | 硬件抽象 + 韧性状态机 fail-loud 化（假 OPEN/无真半开） | 第 5–6 周 | 步 29 |
| 31 | D9：安全四件套（P0） | 第 7 周 | 步 30 |
| 32 | D6+D7：清除假状态（纯删除性变更） | 第 7 周 | 步 31 |
| 33 | 7/7 端点契约基线 | 第 7 周 | 步 32 |
| 34 | pip-audit + gitleaks 进 CI | 第 7 周 | 步 33 |
| 35 | R6：React+TS 新前端 | 第 8–9 周 | 步 34 |
| 36 | E2E + bundle + 性能验收 | 第 8–9 周 | 步 35 |
| 37 | R8：看板收敛 | 第 8–9 周 | 步 36 |
| 38 | D10+R7：固件加固 | 第 10–11 周 | 步 37 |
| 39 | P2 项按需（ADC/OTA） | 第 10–11 周 | 步 38 |
| 40 | 文档数字脚本化 check_doc_numbers.py | 第 10–11 周 | 步 39 |
| 41 | 死代码扫描 + flag 清零 | 第 10–11 周 | 步 40 |
| 42 | ADR 补全 + ARCHITECTURE.md | 第 10–11 周 | 步 41 |
| 43 | 终局验收（全量重跑） | 第 10–11 周 | 步 42 |

**周次 ↔ 报告的 30/60/90 天**：步 2–23 = 30 天窗口（证据修复 + 专利递交）；步 24–37 = 60 天窗口（性能与可复现）；步 38–43 = 90 天窗口（论文 + 竞赛 + 开源）。每天能投入 6 小时以上就按报告原周次执行，阶段顺序不变。

**阅读约定**：

- 命令一律带 `uv run` 前缀（副智能体起子进程不继承你的 shell 激活状态，`uv run` 是唯一可靠前缀）。
- 「**预期看到**」是验收的一部分——输出对不上，先当问题查，不要跳过。
- 探针用 `PROBE_TARGET` 环境变量指向「包含 `energy_system` 包的目录」：默认旧仓库根目录，指向新仓库时设 `PROBE_TARGET=src`（约定详见步 11）。
- 小树里的 ✅ = 本步新建，✏️ = 本步修改。
- 排错：附录 B 故障排查表；协作细节：附录 D。

---

## 第 1 步 · 指挥智能体的四步工作法（一页纸，动工前读完）

**预计时间**：15 分钟（纯阅读，不用开电脑）｜**前置**：无

**干什么**：后面 42 步，每一步都是派给智能体的一个任务。这一步给你任务的完整生命周期——**先学会怎么指挥，再动手**。展开版（九个智能体重构案例的教训、反模式提示词对照表、常见情况处置）在**附录 D**，本步只记一页纸。

**流程图**：

```
你（发任务卡，五字段：Intent/Scope/Boundaries/Evidence/Recovery）
   │
   ▼
① EXPLORE（主智能体 Kimi，plan mode 只读）
   读文件 → 起 reader 副智能体并行读 → 5 行复述理解
   │  「我说继续才动笔」
   ▼
② PLAN（主智能体 Kimi）写实现计划 ──你审阅──不通过──▶ 改计划（不许跳过）
   ▼ 通过
③ IMPLEMENT（主智能体 spawn builder 副智能体 Flash）
   先写失败测试 → 最小实现 → 跑测试 → report 回主会话
   ▼
④ VERIFY（主智能体 spawn verifier 副智能体 Flash，独立会话）
   对照契约卡审计 → PASS/FAIL + file:line
   │ FAIL ─▶ 回 ③（带 verifier 意见；两次不过 ─▶ 你介入/重开会话）
   ▼ PASS
⑤ COMMIT（主智能体）带契约卡 + 真实 Evidence → push → CI 绿 → squash 合并
   ▼
⑥ 你抽检关键 diff（只抽三类：flag 切换 / 删旧实现 / 口径变更）
```

**什么时候可以跳过 plan**：diff 一句话能描述完的（改文案、改配置）。本项目几乎每个任务都涉及口径，**默认不跳**。

**五段提示词模板**（完整可复制，后面每步的「怎么干」都基于它； spawn 副智能体必须显式钉 `provider=deepseek、model=deepseek-flash`，原因见步 5.3）：

**阶段 ① EXPLORE**（在 DSH 主会话发）：

```
进入 plan mode。任务卡如下：

【契约卡 C1 — D5 尾读迁移】
- Intent：消除 JSONL 全量读性能缺陷（120k 行全量 670ms）
- Scope：仅 src/energy_system/infra/data_store.py（新建）+ tests/test_data_store.py（新建）
- Boundaries：不改任何调用方；events.jsonl 行格式不变（30 字段白名单，报告 §6.1）
- Evidence：uv run pytest -q 全绿；uv run pytest -q -m perf 120k 行 P95 < 50ms
- Recovery：feature flag FLAG_DATA_TAIL_READ 默认关

参考（只读，不许改）：
- 旧仓库 dashboard/data_loader.py:10-43（正确尾读实现，照搬其逻辑）
- docs/specs/SPEC.md（口径唯一事实源）

要求：
1. 先起 2 个 reader 副智能体（provider=deepseek、model=deepseek-flash，
   显式指定不继承）：一个读旧仓库 data_loader.py:1-60，
   一个读旧仓库 jsonl_repository.py:74-99（read_all 位置）
2. 综合它们的报告，用 5 行以内复述：尾读算法的关键步骤 + read_all 的问题
3. 列出你打算改的文件和顺序
4. 停下，等我说「继续」。不许写代码。
```

**阶段 ③ PLAN 通过后，发「继续」**，然后：

```
按计划实现。用 subagent 工具起 builder 副智能体（provider=deepseek、
model=deepseek-flash，显式指定，不继承主会话模型），后台运行，
把下面任务卡完整给它（它看不到我们的对话历史）：

<粘贴契约卡 + spec 相关段落 + 参考文件路径>

builder 纪律：
- 先写失败测试固化期望行为，再写实现
- 只改 Scope 内文件
- 跑命令一律用 uv run 前缀
- 完成后报告：changed files；测试和性能命令的原文输出；偏离及原因

builder 完成后把报告带回主会话。
```

**阶段 ④ VERIFY**（builder 报告回来后）：

```
起 verifier 副智能体（provider=deepseek、model=deepseek-flash，显式指定，
新会话），输入：
1. builder 的完整 diff（git diff 输出）
2. 契约卡 C1
3. docs/specs/SPEC.md

审计清单：
a. Scope 外是否有改动？Boundaries 是否违反？
b. Evidence 行是否是真实命令输出（而非概述）？
c. 口径（字段名/量纲/KPI）是否被悄悄改变？
d. 语义幻觉：能跑但逻辑错的代码；旧行为是否被无意改变？
e. 双实现/死代码是否被引入？

输出：PASS 或 FAIL + file:line + 理由。只报告，禁止修改任何文件。
```

**阶段 ⑤ COMMIT**：

```
按 Conventional Commits 写 commit（Evidence 行贴真实输出原文），
推送分支，确认 CI 全绿后 squash 合并到 main。
合并后更新 docs/FLAGS.md（若本步引入 flag）。
```

**Input–Process–Output 骨架**（所有任务提示词的共同结构，把智能体当初级工程师 briefing，不要发模糊请求）：

```
【任务卡】编号/意图/范围（白名单）/边界（禁改清单）/证据（必须通过的命令）/回滚（flag 或 revert）
【输入】参考文件（file:line 指针，不粘贴内容）；迁移类任务写「以 X 为准，禁止迁移 Y，原因：…」
【过程】1. 先读这些文件，5 行以内复述理解（不许写代码）2. 等我说「继续」
        3. 先写失败测试固化期望行为 4. 最小实现通过测试 5. 跑全量命令贴真实输出
【输出】改动文件清单 + 每个文件为什么；测试/性能真实输出（贴原文，禁止概述编造）；
        旧代码「为什么」问题清单（回旧仓库查证后再继续）
```

**怎么验（本步怎么算过）**：能把流程图讲给身边的人听懂；五段模板抄到便签上备用。
**错了怎么退**：本步无代码，重读即可。

---

## 第 2 步 · 冻结旧仓库（只读博物馆）

**预计时间**：30 分钟｜**前置**：第 1 步｜**分支**：无（只读操作）

**干什么**：把旧仓库变成「规格库 + 博物馆」——**永远不删、永远不在里面修 bug**。它是口径的权威来源和「为什么当初这么写」的档案。先做个六项检查，确认「建新仓库 + 冻结旧仓库」是对的路线：

| # | 检查项 | EcoSentinel 的答案 |
|---|---|---|
| 1 | 测试能当安全网吗？ | ✅ 365 个 + 契约测试（价值最高的部分） |
| 2 | 需求稳定吗？ | ✅ 规格已冻结（旧文档虽多但口径可提炼） |
| 3 | 团队熟悉代码吗？ | ✅ 作者本人 + AI 可逐行分析 |
| 4 | 有重写窗口期吗？ | ⚠️ 竞赛/论文/专利三线并行，**没有 6 个月** |
| 5 | 「凭记忆重写」会丢事实吗？ | ❌ 会——365 测试和 79% 覆盖是买不来的资产 |
| 6 | 双实现泛滥的根因是架构还是历史？ | 历史（没做完），架构本身分层清晰 |

**结论**：建新仓库（步 9），旧仓库冻结为只读。**资产迁移过来，债务不迁移**：

| 资产（必须迁移，精心维护） | 债务（不迁移，或只迁移其「教训」） |
|---|---|
| 365 个测试（unit/contract/根目录三层） | 8 组双实现中的错误方（步 10 SEAMS.md 裁决） |
| 契约测试（分层门禁、协议双端断言、指标注册表） | 探针脚本本身（迁其逻辑为表征测试，不迁其形态） |
| 正确实现：`dashboard/data_loader.py:10-43` 尾读 | `fix_readme_qa.py`（用脚本覆写 README——删除） |
| KPI/口径定义（`energy_system/algorithms/comfort_eval.py` 的 band_share 口径、`energy_system/domain/telemetry.py` 的单位表） | 57 份文档中的过期数字、重复 PDF（合计约 133 MB） |
| 分层秩测试（`tests/contract/test_layering.py`） | 注释里的「评审 §X」噪音 |
| `energy_system/ai/prompt_builder.py` 的 16 字段白名单机制（密钥/路径/堆栈永不外发） | `algorithms/ai_advisor.py` 的内联熔断副本 + 归因错 + 无 key 清池 |

### 2.1 怎么干

1. **打 tag**：

   ```bash
   cd ~/EcoSentinel                    # 旧仓库
   git status                          # 先确认干净
   git tag legacy-reference
   ```

   预期看到：`git tag` 列出 `legacy-reference`。

2. **推远程备份**（有远程才做；没有就跳过，本地 tag 也够）：

   ```bash
   git push origin legacy-reference
   ```

3. **做本地裸备份**：

   ```bash
   git clone --bare ~/EcoSentinel ~/EcoSentinel-legacy-backup.git
   ```

   预期看到：生成 `~/EcoSentinel-legacy-backup.git/` 目录。

4. **设只读**（可选，推荐）：

   ```bash
   chmod -R a-w ~/EcoSentinel
   ```

   > ⚠️ 注意：`.git` 也会变只读，之后在该仓库里任何 git 写操作（commit/tag）都会失败。临时解锁：`chmod -R u+w ~/EcoSentinel`，用完再锁。**第 17 步要建工作副本，就是在裸备份上 clone，不碰这个只读原库。**

**冻结之后，旧仓库只有三种正确用法**：① 查口径（「elec_kwh 怎么定义的」→ 按速查表对 file:line 找权威实现，不许凭记忆）；② 迁移资产（按本手册各步的卡片搬运）；③ 当博物馆（写 ADR 时的引证材料）。**永远不许**：在旧仓库里修 bug（修了也不会进新仓库，纯属分裂）；照抄双实现（SEAMS.md 说「以 X 为准」的才抄）。

### 2.2 怎么验

```bash
cd ~/EcoSentinel && git tag && ls -d ~/EcoSentinel-legacy-backup.git
```

预期：tag 列表有 `legacy-reference`；裸备份目录存在。
**错了怎么退**：`git tag -d legacy-reference`；删备份目录。本步不碰任何代码。

---

## 第 3 步 · 装 uv，写好三个配置文件草稿

**预计时间**：30 分钟｜**前置**：无（可与第 4、5 步并行）｜**分支**：无

**干什么**：把新仓库的工具链一次调对——uv + ruff + mypy + pre-commit + pytest + 覆盖率门禁。**这是「机械门禁」的地基：没有工具链，后面所有防死山规矩都只是建议。**审阅报告两处点名：§5.12「依赖锁定｜后端加 `uv lock`」、§5.13「工具链｜**ruff + mypy + uv + pre-commit**｜P1」。本步只装工具 + 在草稿箱写三个文件；它们进库是第 9 步的事。

### 3.1 怎么干

1. **装 uv**（macOS/Linux 一条命令；Windows 用 PowerShell 版，见 https://docs.astral.sh/uv/）：

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   预期看到：安装完成提示；`uv --version` 有输出（≥0.4）。

2. **建草稿箱，写三个配置文件**：

   ```bash
   mkdir -p ~/ecosentinel-config-draft && cd ~/ecosentinel-config-draft
   ```

   然后用编辑器把下面三个文件写进去（第 9 步原样复制进新仓库）。

   **文件一 `pyproject.toml`**：

   ```toml
   [build-system]
   requires = ["hatchling"]
   build-backend = "hatchling"

   [project]
   name = "ecosentinel"
   version = "2.0.0"
   description = "EcoSentinel 楼宇能效监控（新仓库重构版）"
   requires-python = ">=3.12"
   dependencies = [
       "fastapi>=0.115",
       "uvicorn[standard]>=0.32",
       "pydantic>=2.9",
       "pydantic-settings>=2.6",
       "pyyaml>=6.0",
       "pyserial>=3.5",
       "httpx>=0.27",
   ]

   # src 布局：包在 src/energy_system，与项目名不同也可以 editable 安装
   [tool.hatch.build.targets.wheel]
   packages = ["src/energy_system"]

   # 开发依赖（uv sync --all-extras --dev 装这些）
   [dependency-groups]
   dev = [
       "pytest>=8.3",
       "pytest-cov>=6.0",
       "pytest-asyncio>=0.24",
       "mypy>=1.13",
       "ruff>=0.8",
       "coverage>=7.6",
       "pip-audit>=2.7",
       "vulture>=2.13",
   ]

   # ===== ruff（报告 §5.13 点名）=====
   [tool.ruff]
   line-length = 100
   target-version = "py312"

   [tool.ruff.lint]
   select = ["E", "F", "I", "UP", "B", "SIM"]
   # E/F 基础错误 · I import 排序 · UP 现代语法 · B bugbear · SIM 简化

   [tool.ruff.lint.per-file-ignores]
   "tests/*" = ["S101"]        # 测试里允许 assert

   # ===== mypy（报告 §5.12：「后端加 mypy（先三个包）」）=====
   [tool.mypy]
   python_version = "3.12"
   ignore_missing_imports = true      # 过渡期：第三方库无类型存根时不报错
   warn_unused_ignores = true

   [[tool.mypy.overrides]]            # 第一批严格检查的三个包
   module = ["energy_system.domain.*", "energy_system.api.*", "energy_system.infra.*"]
   disallow_untyped_defs = true

   # ===== pytest（perf 标记给性能验收用）=====
   # ⚠️ 核对更正：旧仓库 **没有** pytest.ini / pyproject.toml 的
   #    [tool.pytest.ini_options]，且没有 tests/perf/ 目录。
   #    在旧仓库直接跑 `pytest -m perf` 会得到「366 deselected」并以退出码 5 失败（实测）。
   #    因此：perf 标记与 perf 测试 **只在新仓库建立**（本 pyproject.toml 就是为此准备的）。
   #    旧仓库阶段想量性能，用步 11.3 的 tools/perf.py 探针，不要用 -m perf。
   [tool.pytest.ini_options]
   testpaths = ["tests"]
   markers = [
       "perf: 性能验收测试（120k 行尾读 P95 < 50ms 等）",
   ]
   addopts = "-q"

   # ===== 覆盖率（fail_under 写进配置，副智能体想跳过都跳不过去）=====
   [tool.coverage.run]
   source = ["energy_system"]

   [tool.coverage.report]
   fail_under = 80            # 报告 §5.12：「加 --cov-fail-under=80」
   show_missing = true
   ```

   **文件二 `.pre-commit-config.yaml`**：

   ```yaml
   repos:
     # ruff：lint + 格式（报告 §5.13 点名）
     - repo: https://github.com/astral-sh/ruff-pre-commit
       rev: v0.8.6            # ← 以 https://github.com/astral-sh/ruff-pre-commit/releases 最新版为准
       hooks:
         - id: ruff
           args: [--fix]
         - id: ruff-format

     # 基础文件卫生
     - repo: https://github.com/pre-commit/pre-commit-hooks
       rev: v5.0.0
       hooks:
         - id: trailing-whitespace
         - id: end-of-file-fixer
         - id: check-yaml
         - id: check-added-large-files
           args: [--maxkb=512]        # 防副智能体把 6MB 日志提交进仓库

     # ★ 机械门禁：禁止 JSONL 全量读回流（D5 防复发，步 19）
     - repo: local
       hooks:
         - id: no-read-all-in-src
           name: ban read_all() in src/ (D5 防复发)
           entry: grep -rnE "read_all\(" src/ --include=*.py
           language: system
           pass_filenames: false
           types: [python]
           # grep 找到匹配返回 0 → hook 失败 → commit 被拒。这就是「gate 是墙」。

     # ★ 机械门禁：文档数字必须与实测一致（防「写 251 实际 365」复发）
     - repo: local
       hooks:
         - id: doc-numbers-check
           name: README numbers must match measured output
           entry: python scripts/check_doc_numbers.py
           language: system
           pass_filenames: false
           files: ^(README\.md|docs/.*\.md)$
   ```

   **文件三 `.github/workflows/ci.yml`**：

   ```yaml
   name: ci
   on: [push, pull_request]

   jobs:
     backend-gate:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4

         # uv 官方 action：装 uv + 按 .python-version 装 Python
         - uses: astral-sh/setup-uv@v5

         - name: Pin Python
           run: uv python pin 3.12

         - name: Sync deps (frozen)
           run: uv sync --all-extras --dev --frozen    # 锁与 pyproject 不一致 → 直接红

         # 岗 1：测试 + 覆盖率门禁（报告 §5.12：--cov-fail-under=80）
         - name: Test + coverage
           run: uv run pytest -q --cov=energy_system --cov-report=term-missing

         # 岗 2：类型（报告 §5.12：后端加 mypy）
         - name: Type check
           run: uv run mypy src/

         # 岗 3：lint + 格式（报告 §5.13）
         - name: Lint
           run: |
             uv run ruff check .
             uv run ruff format --check .

         # 岗 4：性能红线
         - name: Performance
           run: uv run pytest -q -m perf

         # 岗 5：依赖安全（报告 §10.2 缺口：无 pip-audit）
         - name: Dependency audit
           run: uvx pip-audit

     frontend-gate:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-node@v4
           with:
             node-version: "22"
             cache: npm
         - run: npm ci
         - run: npm run lint
         - run: npm test
         - run: npm run knip            # 死代码（报告 §5.12：前端已有）
         - run: npm run build           # 产物大小进 CI 日志（首包 gzip < 150 kB）

     doc-numbers:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: astral-sh/setup-uv@v5
         - run: uv sync --frozen
         - name: Doc numbers vs measured
           run: uv run python scripts/check_doc_numbers.py
   ```

3. **速查：uv 全流程命令表**（第 9 步起天天用）：

   ```bash
   # ===== 阶段 1：固定 Python 版本（生成 .python-version 文件）=====
   uv python pin 3.12

   # ===== 阶段 2：建虚拟环境（uv 按 .python-version 自动找/下载 3.12）=====
   uv venv                          # 产物：.venv/（gitignore 它）

   # ===== 阶段 3：装全部依赖（含 dev 组）=====
   uv sync --all-extras --dev       # 同时生成 uv.lock —— 报告要的「uv lock」

   # ===== 阶段 4：日常跑一切（uv run 自动用 .venv，不用手动 activate）=====
   uv run pytest -q                          # 测试
   uv run pytest -q --cov=energy_system --cov-report=term-missing   # 覆盖率
   uv run mypy src/                          # 类型
   uv run ruff check . && uv run ruff format --check .              # lint + 格式检查
   uv run python -m energy_system.simulation.compare               # 跑迁移来的脚本

   # ===== 阶段 5：加/删依赖（自动更新 uv.lock）=====
   uv add fastapi                    # 加运行时依赖
   uv add --dev pytest-cov           # 加开发依赖
   uv remove <包名>                   # 删

   # ===== 阶段 6：锁文件维护 =====
   uv lock                            # 重新解析生成/更新锁
   uv lock --upgrade                  # 升级所有依赖到允许的最新版
   uv sync --frozen                   # CI 专用：严格按锁装，不一致就报错

   # ===== 阶段 7：一次性工具（不污染项目环境）=====
   uvx ruff@latest check .           # 不装进项目，跑完即走
   uvx pip-audit                     # 安全扫描（报告 §10.2 缺口）
   uvx vulture src/                  # 死代码扫描（报告 §5.12 建议）
   ```

4. **报告命令 → uv 命令对照表**（附录 A 实测清单的「翻译」，贴给智能体防它用回 pip）：

   | 旧命令（报告附录 A） | 新仓库命令 |
   |---|---|
   | `pip install -e ".[dev]"` | `uv sync --all-extras --dev` |
   | `pytest tests -q` | `uv run pytest tests -q` |
   | `pytest --cov=energy_system` | `uv run pytest -q --cov=energy_system` |
   | `python tools/dyn1.py` | `uv run python tools/dyn1.py` |
   | `python tools/perf.py` | `uv run python tools/perf.py` |
   | `python tools/api_probe.py` | `uv run python tools/api_probe.py` |
   | `pip-audit` | `uvx pip-audit` |
   | `vulture src/` | `uvx vulture src/` |

   **纪律**：智能体**不许手动跑 linter、不许手动调格式**（AGENTS.md 里也这么写）——pre-commit 自动做，模型的手动格式修改只会制造 diff 噪音。

> ⚠️ uv 会自带管理 Python 解释器。如果公司/学校环境禁止下载 Python，改用 `uv venv --python /path/to/existing/python3.12` 指定系统解释器，其余命令不变。

### 3.2 怎么验

```bash
uv --version
ls ~/ecosentinel-config-draft/
```

预期：uv 版本 ≥0.4；草稿箱里有三个文件（`pyproject.toml`、`.pre-commit-config.yaml`、`.github/workflows/ci.yml`）。
**错了怎么退**：删草稿箱重写。本步无项目代码。

---

## 第 4 步 · 安装 DSH 桌面版

**预计时间**：30 分钟｜**前置**：无（可与第 3、5 步并行）｜**分支**：无

**干什么**：装上 DeepSeek Harness（DSH）——DeepSeek 官方编程智能体框架。**桌面版开箱即用，新手直接选它**（插件管理有页面，不用记命令行）。

### 4.1 三条安装路，选桌面版

| 方式 | 命令/获取 | 适合谁 | 说明 |
|---|---|---|---|
| **① 桌面版（主推）** | 官网 **deepseek.com/harness** 下载 macOS / Windows 安装包 | **所有人，尤其新手** | 开箱即用：欢迎引导、插件管理页面（免命令行）、文件拖入、定时任务内置、自动更新 |
| ② npx 免安装 | `npx @deepseek-ai/dsh web` | 想先尝尝、或 macOS/Linux 无安装包时 | 浏览器打开 http://127.0.0.1:3080 |
| ③ 全局 npm | `npm install -g @deepseek-ai/dsh && dsh web` | 命令行重度用户 | 以后直接打 `dsh` |

**版本要求**：桌面版当前 **v0.2.1-rc.2**（2026-10-17 发布，支持 DeepSeek-V4.1-Flash-1017 与 Search/Fetch API），应用菜单里「Check for Updates」可升级；npx/npm 版要求 DSH ≥ v0.2.1-rc.1（`npx @deepseek-ai/dsh --version` 查看），Node.js **22.19+ 或 24 LTS**（低版本直接报语法错误）。

**桌面版 vs 命令行版的关键差异**（选之前知道）：

1. **插件各管各的**：Desktop 管理自己的插件。你以前在命令行版装的插件，桌面端要重新添加（Plugins → Add plugin，支持 npm 包名 / Git 地址 / 压缩包 / 本地绝对路径）。**迁移前先记录每个插件的包名、版本、设置。**
2. **定时任务**：桌面版内置「自动化任务」插件（侧栏插件页开启后，重复性工作可按计划执行，看运行记录）——Standard/Creator/PTC 模式可用，**Minimal 模式和 subagent 里不可用**；要跑定时任务就得让 app 保持运行。
3. **配置文件**：命令行版配置在 `~/.dsh/settings.yaml`；桌面版有自己的一套设置（模型、插件、工作区都在应用内管理），部分高级配置仍读写同一份 settings.yaml（以应用内 Settings 为准）。
4. **手动压缩上下文**：`/compact` 在 Web 和 Desktop 界面都可用——主会话太长时手动压缩（当然，首选还是开新会话，见第 5 步 5.5）。

> ⚠️ **安全第一课（先读再装）**：DSH 的 shell 工具能执行你电脑上的真实命令，还能加载插件、读取本地凭据文件，而它**目前未经系统性的安全审计**。所以：① 工作区（workspace）只能指向项目文件夹，**永远不要选桌面、home 根目录或系统目录**；② 不要在生产服务器上跑；③ 第三方插件安装前想清楚——插件有完整工具权限；④ DSH 是开发者预览版，**你的回滚主线是 git，不是沙箱**；⑤ API Key 只通过环境变量/应用内密钥管理给，不要写进任何会进 git 的文件。

### 4.2 怎么干（桌面版首次使用，按欢迎引导三步走）

1. **下载安装**：官网 deepseek.com/harness 下载对应系统安装包，装完打开。
2. **选方向**：引导会问「日常办公还是编程」以及「想看到多少智能体工作细节」——选**编程**、细节**看全**（排错需要）。
3. **登录/密钥**：用 DeepSeek 账号登录可领限时体验赠金（活动规则以页面为准）；更重要的：**Welcome → Add API Key** 把两个 Key 加进去：
   - DeepSeek API Key（`sk-` 开头，https://platform.deepseek.com/api_keys）
   - Kimi API Key（https://platform.moonshot.cn ，OpenAI 兼容）
   - 用 DeepSeek Coding Plan 的话：Settings → Models → Add model provider → **Custom model API**，填 Coding Plan 的 key 和 Base URL
4. **选工作区**：点「Choose workspace」。新仓库第 9 步才建，**现在先指向 `~/EcoSentinel`（旧仓库，只做只读分析）**；第 9 步建完新仓库后，回来改指 `~/ecosentinel-v2`。

**界面速认**：中间是对话区（生成的文件和每轮代码变更集中展示在对话里）；侧栏有文件预览、代码 diff 查看、插件管理、自动化任务；头部是模型指示 + 子智能体计数器（spawn child 后出现，点开看每个 child 的模型和状态）；Trajectory（轨迹）标签页记录每一次工具调用的入参、返回、token 消耗——**排错和审计的主战场**。

### 4.3 怎么验

打开 DSH，欢迎引导三步走完，工作区指向 `~/EcoSentinel`，界面能正常对话。
**错了怎么退**：卸载重装；工作区选错随时可以重新 Choose workspace。

---

## 第 5 步 · 配置两个模型（主 Kimi + 副 DeepSeek）

**预计时间**：30 分钟｜**前置**：第 4 步｜**分支**：无

**干什么**：主智能体用 **Kimi K3.1 Pro**（烧脑：规划、规格、裁决），副智能体池用 **DeepSeek V4.1 Flash**（跑腿：搬代码、写测试、跑命令、审计）。行业验证过的路由策略：强模型烧脑，便宜模型跑腿——副智能体各自持有独立上下文窗口，不但省钱，还让主会话保持干净。

### 5.1 两张模型名片

| | **主智能体：Kimi K3.1 Pro** | **副智能体：DeepSeek V4.1 Flash** |
|---|---|---|
| 定位 | Kimi 最新旗舰，3 万亿参数，原生视觉 | DeepSeek 廉价档，为 DSH 原生调优 |
| 上下文 | **1M tokens** | **1M tokens**（输出可达 384k） |
| 强项 | 长程编程、规划、指令遵循、架构完整性保持 | 每天跑几千次的机械活：搬代码、写测试、跑命令、分类总结 |
| 基准 | SWE 系/终端基准第一梯队。**（网传「4000+ 次工具调用、12 小时重构金融撮合引擎」是 K2.6 的案例，不是 K3.1 Pro——引用时注明）** | DeepSWE 77.0（**厂商自测**，超 Claude Opus 5 的 74.0 同为其自报口径）；Terminal-Bench 42.3；每任务成本 <$0.2 |
| 价格 | **平台人民币价（k2.7-code 档）：输入 ¥6.50 / 输出 ¥27.00 每百万 token（缓存 ¥1.30）；K3.1 Pro 价格以 platform.moonshot.cn 页面为准**（$0.95/$4.00 是美元口径且对应旧型号，勿混用） | 高峰 $0.30/$1.20 每百万 token；**官方闲时半价**（具体时段以定价页为准）；缓存命中 $0.003–0.006 |
| 速度 | 旗舰速度 | 中位 195 tokens/s |
| 思考模式 | 支持 | **默认开启** |

**搭配逻辑**：主智能体管对话、规格、规划、裁决；副智能体管机械执行、容易验证的活。**（「省 60–75%」是 Claude+DeepSeek 组合的实测数据，这里是类比估算，不是承诺——以你的实测账单为准。）**

**分工矩阵**：

| 任务类型 | 主（Kimi） | 副（Flash） | 说明 |
|---|---|---|---|
| 读旧仓库、逐行解释「为什么」 | ✅ | 汇总阅读 | 主智能体下结论；Flash 可以并行读多个文件返回摘要 |
| 写 spec / 架构方案 / ADR | ✅ | 不许碰 | 只有主智能体写规格 |
| 拆任务、发任务卡 | ✅ | 不许碰 | 主智能体是唯一调度入口 |
| 搬测试、改 import、机械重命名 | 审 | ✅ 干 | 典型副智能体活：范围明确、可验证 |
| 写新模块的样板代码 | 审 | ✅ 干 | 按 spec 填空 |
| 跑测试/lint/构建、贴输出 | — | ✅ 干 | 副智能体或 shell 直接跑 |
| **审计 diff（verifier）** | 最终抽检 | ✅ 独立会话审 | verifier 必须独立会话，防止「自己审自己」 |
| 口径裁决（KPI/字段名/量纲） | ✅ 独断 | 提案 | 副智能体可提议，主智能体裁决 |
| 删旧实现、切 flag | 你批准后主智能体执行 | 不许碰 | 最高风险动作，人类点头 |
| commit message | 主智能体 | 可代笔 | Evidence 行必须来自真实命令输出 |

**一条铁律**：副智能体**永不改 spec、永不改 AGENTS.md、永不改门禁**。规矩只能由你 + 主智能体改。

### 5.2 怎么干（优先应用内，备选手写 settings.yaml）

1. **优先用应用内/官方 provider**：桌面版 Settings → Models → Add model provider 里直接添加 DSH 内置的 Kimi provider，或安装官方 Kimi 插件（`dsh-llm-kimi`，提供三条路由：`kimi-code` / `kimi-cn` / `kimi-global`，按你的账号类型选）。内置 provider 的协议细节由官方维护，不会踩方言坑。

2. **备选：手写 `~/.dsh/settings.yaml`**（内置不满足时）：

   ```yaml
   # ~/.dsh/settings.yaml —— EcoSentinel 重构专用（修正版）
   llm-pi-ai:
     providers:
       # ============ 副智能体：DeepSeek V4.1 Flash ============
       # 官方 API，为 DSH 原生调优，要求 DSH >= v0.2.1-rc.1
       deepseek:
         displayName: DeepSeek V4.1 Flash
         apiKeyEnv: DEEPSEEK_API_KEY
         api: openai-completions
         baseURL: https://api.deepseek.com
         compat:
           thinkingFormat: deepseek      # ★坑1：必须显式声明，否则按 URL 猜方言会出错
         defaultContextWindow: 1048576  # ★坑2：默认只有 262144，白白浪费 3/4 上下文
         defaultMaxTokens: 32768        # ★坑3：放 provider 级（曾错误地写在 model 级，不生效）
         models:
           - id: deepseek-flash          # 官方 API 名（V4.1 Flash 1017 快照）
             name: DeepSeek-V4.1-Flash
             contextWindow: 1048576

       # ============ 主智能体：Kimi K3.1 Pro ============
       # 优先用内置/官方插件 provider；下面是手写备选
       kimi:
         displayName: Kimi K3.1 Pro
         apiKeyEnv: KIMI_API_KEY
         api: openai-completions
         baseURL: https://api.moonshot.cn/v1   # 国际站用 https://api.moonshot.ai/v1
         compat:
           thinkingFormat: openai      # ★Kimi 不是 deepseek 端点，必须显式声明 openai 方言
         defaultContextWindow: 1048576 # K3.1 Pro 支持 1M 上下文
         defaultMaxTokens: 32768       # 同上：provider 级
         models:
           - id: kimi-k3.1-pro
             name: Kimi-K3.1-Pro
             contextWindow: 1048576

     # 主智能体默认启动模型
     agent-default-model:
       provider: kimi
       model: kimi-k3.1-pro
   ```

3. **两个字段纪律**（写错不报错，但浪费钱）：

   | 纪律 | 说明 |
   |---|---|
   | `maxTokens` 放 **provider 级 `defaultMaxTokens`** | 写在 model 条目的 `maxTokens` 不生效 |
   | **不要**在 `openai-completions` provider 级写 `thinking:` / `reasoningEffort:` | 该适配器不读这两个键，写了会被**静默忽略**（造成「以为关了思考其实开着」的错觉）。思考格式统一走 `compat.thinkingFormat` |

4. **三个坑**（踩了会浪费钱或报错）：

   | 坑 | 现象 | 解法 |
   |---|---|---|
   | 方言猜错 | 非 deepseek 域名的端点（Kimi 就是）会被当成 OpenAI 方言对话，reasoning 内容处理错乱 | `compat.thinkingFormat` 显式声明（kimi→openai，deepseek→deepseek） |
   | 上下文缩水 | 手写的模型条目只拿到默认 262,144 token，而 V4.1 Flash 有 1M | 每个模型都写 `contextWindow: 1048576` |
   | Provider ID 永久 | WebUI 里创建 Provider 时填的 ID **不可改名**，写进会话记录和凭据引用 | 一开始就想好名字（本手册用 `kimi` / `deepseek`） |

5. **改完配置必须验证**（防「改了没生效」）：命令行版 `npx @deepseek-ai/dsh --dump-config` 看合并后的最终配置；桌面版在 Settings → Models 列表里确认 `kimi-k3.1-pro` 和 `deepseek-flash` 都在、上下文显示 1M。**不验证等于没改。**

### 5.3 subagent 机制与 ★ 模型继承陷阱（最容易烧错钱的一节）

DSH 的 subagent 是主会话用内置工具 spawn 的子智能体，特性：① **独立上下文窗口**——child 的阅读不会弄脏主会话；② **后台并行**——一句话可以同时起 5 个 child，各自运行，主会话在头部计数器看状态；③ **完成后回报**——每个 child 完成时以 subagent-report 注入主会话，主智能体汇总；④ **单独计费**——每个 child 的 token 单独统计（头部下拉可见），但通常总账更省；⑤ **可钉模型**——每个 child 可指定 provider/model，这就是「主副结合」的落点。

**陷阱原文**（DSH `dsh-model-pin` 插件 README + issues #455/#1581）：

> 子智能体继承的是**父会话「创建时」的模型**，而不是你当前在用的模型。

| 场景 | 会发生什么 |
|---|---|
| 你用 Kimi 开着主会话，中途 `/model` 切到 DeepSeek，再 spawn child | child 用的是**会话创建时**的模型，不是你切换后的 |
| 你以为切了模型就是在给副智能体换档 | 实际没换，账单按旧模型走 |
| 长时间跨天的会话 | 继承链早就乱了，spawn 出来的 child 模型不可预测 |

**解法三层（话术 → 规则 → 兜底）**：

**第 1 层 · 话术层（本手册全程使用，零成本）**：每个 spawn 提示词**显式写 provider + model**：

```
用 subagent 工具起一个子智能体：
- provider 固定为 deepseek，model 固定为 deepseek-flash
- ⚠️ 显式指定，不要继承主会话模型
- 后台运行，完成后把结果带回主会话
任务：……
```

**第 2 层 · 规则层（推荐安装）**：`dsh-subagent-model-config` 插件——WebUI 里多一个「Subagent Models」规则页，可以按**队员名字匹配**钉模型（例如「所有叫 builder/verifier/reader 的 child 一律用 deepseek-flash」），**即时生效**，不用每次写话术。装完仍然保留第 1 层话术（双保险）。

**第 3 层 · 兜底层（推荐安装）**：`dsh-model-pin` 插件——维护一个 allow-list，凡不在名单上的 provider/model，spawn 时直接 redirect 或 reject。防的是「某天你忘了写钉模型话术，child 悄悄跑了 Kimi」。

**每次 spawn 后的验证动作**（30 秒，防「以为钉了其实没钉」）：点头部子智能体计数器 → 看 child 详情里的**模型名**。发现不对 → 检查话术有没有写全、插件规则有没有生效。

### 5.4 两种协作方案（选 A 起步，B 增强）

**方案 A：原生 subagent + spec 契约（零安装）**——DSH Standard 预设自带 subagent 工具；钉模型靠话术；角色每次 spawn 现场定义，spec 里写角色契约；适合日常单线任务（本手册 90% 场景）、第 1–4 周。弱点：没有持久化的「队员名→模型」规则；每次 spawn 要带全上下文。

**方案 B：插件增强（三层插件叠加）**——`dsh-subagent-model-config`（规则钉模型）+ `@limuyang2/dsh-agent-team`（Leader+成员常驻团队）+ `dsh-model-pin`（allow-list 兜底）；适合 Phase 2 起多线并行、第 5 周后的验收评审。弱点：① 插件生态**未经广泛安全审计**，每个插件都有完整工具权限，装前三思；② agent-team 的配置是**快照，不热更新**——改了成员模板，运行中的团队还是旧的，要移除成员重新添加；③ 多一层故障面，排错时先想「是不是插件」。

**结论**：**第 1–4 周用方案 A**（先把工作流跑顺，插件只会增加变量）；**第 17 步起叠加方案 B 的 `dsh-subagent-model-config` + `dsh-model-pin`**（这两个纯增益、解决钉模型持久化）；**agent-team 插件等第 5 周后真有多线并行再上**。三个全装上但不会用，是另一种死法。

### 5.5 上下文卫生五条（防「主会话被实现细节撑爆」）

1. 主会话只放：任务卡、child 报告摘要、你的指令。**禁止**把整文件贴进主会话——给 file:line 指针，让 child 去读。
2. 每个 child 的 prompt 必须自带完整任务背景（child 看不见主会话历史）。
3. 读代码的活派给 child，主会话只收「5 行以内的结论」。
4. 同一会话连续两次修正失败 → **fork 或重开会话**，把教训写进新 prompt，不要无限纠正。
5. `AGENTS.md` 是长期记忆，任务卡是一次性上下文，**别把任务细节漏进 AGENTS.md**（超过一屏读不完，整份文件会被智能体忽略）。

### 5.6 怎么验

第 6 步冒烟测试就是本步的验收。
**错了怎么退**：Provider ID 不可改名——一开始就想好名字；配置改坏就改回来。

---

## 第 6 步 · 冒烟测试：确认主副智能体都活着

**预计时间**：15 分钟｜**前置**：第 5 步｜**分支**：无

**干什么**：对着 DSH 说「你好」，确认主智能体（Kimi）能回、副智能体（Flash）能 spawn 且模型钉对了。这是整个 11 周里最便宜的一次「验收不过就停下来」。

### 6.1 怎么干（两句提示词，这就是你的第一条提示词）

1. **第一句（测主智能体 Kimi）**，在 DSH 主会话发：

   ```
   用一句话介绍你自己，并告诉我你的上下文窗口多大。
   ```

   预期看到：Kimi 回复，提到 1M 上下文（K3.1 Pro）。

2. **第二句（测副智能体 spawn 机制 + 显式钉模型）**：

   ```
   用 subagent 工具起一个子智能体，provider 固定为 deepseek、model 固定为
   deepseek-flash（显式指定，不要继承主会话的模型），后台运行。
   任务：列出当前工作区的文件清单。完成后把结果带回主会话。
   ```

   预期看到：会话头部出现**子智能体计数器**（显示 1 个 child），几秒到几十秒后 child 完成，主会话收到一份「subagent-report」注入，内容是文件清单。

3. **验证钉模型生效**：点头部计数器 → 看 child 详情里的**模型名**。

   预期看到：`deepseek-flash`。这是钉模型是否生效的验证点（第 5 步 5.3 解释了为什么必须验）。

   如果第二句没有起 child，检查：① DSH 版本 ≥ 0.2.1-rc.1；② 用的预设是 Standard（只有 Standard 带 subagent 工具；桌面版欢迎引导选「编程」即可）。

### 6.2 插件管理（桌面版页面 vs 命令行）

**桌面版（推荐姿势）**：侧栏 → 插件管理页面 → Add plugin → 输入 npm 包名即可安装/停用/卸载，可查看介绍与来源，支持自定义插件索引，部分插件支持热重载（改完即时生效，不支持的要重启）。

**命令行版**：

```bash
# 第一步永远是这个：看清当前版本支持什么参数（各版本 profile 参数不一致）
npx @deepseek-ai/dsh plugin --help

# 第二步按帮助里的实际语法安装（下面两种写法各版本可能出现其一）
npx @deepseek-ai/dsh plugin add @limuyang2/dsh-agent-team
# 或（旧语法）
npx @deepseek-ai/dsh plugin --profile web add @limuyang2/dsh-agent-team

# 插件 2：房间式群组协作 —— chair + members，消息传递 + 共享任务列表
npx @deepseek-ai/dsh plugin add github:polohot/dsh-adrian-agents-group-work
```

装完在 Settings → Plugins 里确认已启用。

**本手册用到的三个协作插件**（按需安装，不要一次全装）：

| 插件 | 作用 | 什么时候装 |
|---|---|---|
| `dsh-subagent-model-config` | WebUI「Subagent Models」规则页，按队员名匹配钉模型，即时生效 | 第 17 步起（并行开工前） |
| `dsh-model-pin` | allow-list 兜底：非白名单模型 spawn 时 redirect/reject | 与上一个同时 |
| `@limuyang2/dsh-agent-team` | Leader + 成员常驻团队，角色模板化 | 第 5 周后多线并行时 |

> **两个插件怎么选**：日常重构用 **Agent Team**（常驻团队，Leader 分派任务）；需要「多个智能体对着一个方案争论到收敛」时用**房间插件**（临时开会，散会即归档）。本手册默认走原生 subagent（方案 A），插件是增强不是必需。**注意**：agent-team 的配置是**快照，不热更新**。

### 6.3 安全边界（再强调一遍）

- workspace 只指向项目目录；**不要**给 Agent home 目录/桌面/系统目录权限
- DSH **未经系统性安全审计**：shell 工具可执行真实命令、可加载插件、可访问本地凭据——第三方插件安装前三思
- PTC 模式（模型生成 TS 脚本自动执行）**不开**，直到你熟悉 DSH；Creator 模式（让 Agent 自己写插件）是实验功能，同样先别碰
- DSH 是开发者预览版，会有破坏性变更：**升级前 git 提交一切**；会话记录在本地，重要结论及时落盘到仓库
- 副智能体的 report 只是「提案」：Evidence 行凡是数字，**你用命令亲自复现一遍再信**（模型对编造和验证过的事实用同样确信的语气）

### 6.4 怎么验

两句提示词都通；child 详情里模型名是 `deepseek-flash`。
**错了怎么退**：本步无项目代码；DSH 配置改坏就改回来（settings.yaml 有备份就直接恢复）。

---

## 第 7 步 · 选定演进路线（只选一条）+ ADR-0002

**预计时间**：半天｜**前置**：第 2 步｜**分支**：无（决策动作）

**干什么**：审阅报告 §13.1 给出三条路线，**现状是三条都写了一半——这就是「半屎山感」的来源**。单选一条，写进 README 和 ADR——**这是后面所有「这个要不要做」争论的终审法庭**。

| 路线 | 保留 | 砍掉 | 目标 |
|---|---|---|---|
| **A 竞赛/教学模板** ✅ 推荐先走 | 模拟模式、规则、单看板、硬件指南 | Streamlit 业务、MQTT 骨架、多候选池 | 30 分钟跑通 |
| B 楼宇能效网关 | 全栈 + 鉴权/多节点/时序库/OTA/告警 | LLM 退出实时回路 | 可交付产品 |
| C 研究平台 | 仿真 + KPI + 审计 + 评测协议 | 前端、固件 | 论文/基准 |

**决策规则**：报告建议**先 A 保底（1 个月）**，再选 B 或 C。本手册 43 步按「先 A」编排。

> 报告 §5.9 的硬约束（不管哪条路线都成立）：楼宇热惯性以「分钟—小时」计，LLM 延迟以「秒」计且输出不确定。**实时控制 = 规则（现状）+ 可选 MPC；LLM 只做「建议 + 解释 + 告警归因」且必须过裁决层。**论文创新点写成「LLM 参与闭环的安全边界与评测方法」，而不是「LLM 节能」——后者无法证明，前者可以实验。

### 7.1 怎么干

1. **发提示词给主智能体**（帮你看清代价，只读分析不改文件）：

   ```
   读审阅报告 §13.1 三条演进路线。用表格对比：每条路线需要动
   双实现中的哪几组、兼容性破坏范围、预计周期、对 365 个测试的影响。
   给出你的推荐和理由。只读分析，不改任何文件。
   ```

   预期看到：一张三路线对比表 + 明确推荐。**推荐应该指向 A**——如果主智能体推荐 B/C，让它把「对 365 个测试的影响」量化再决定。

2. **你决定选 A**，把两行决定写下来（第 9 步进库）：

   `README.md` 第一段：

   ```markdown
   # EcoSentinel

   **演进路线：A（竞赛/教学模板）**——本仓库唯一业务方向。模拟模式 + 规则控制 +
   单业务看板 + 硬件指南，目标 30 分钟跑通。路线决策记录见
   docs/adr/0002-single-evolution-track.md。
   ```

   `docs/adr/0002-single-evolution-track.md`：

   ```markdown
   # ADR-0002：单一演进路线（先 A 后 B/C）

   - 状态：已接受（2026-10）
   - 背景：报告 §13.1 三条路线各写了一半；§5.9 硬约束：LLM 不进实时回路
   - 决策：路线 A 保底 1 个月，再评估 B/C
   - 后果：Streamlit 业务视图砍掉（步 37 降级为诊断台）；MQTT 默认关（步 38）
   ```

### 7.2 怎么验

README 第一段出现唯一路线 A；ADR-0002 文件存在（先放草稿箱，第 9 步进库）。
**错了怎么退**：改 README（本步无代码）。

---

## 第 8 步 · 提炼 SPEC.md（唯一事实源）

**预计时间**：1 天｜**前置**：第 7 步｜**分支**：`docs/spec`

**干什么**：把旧仓库 42 个文档提炼成一份**唯一事实源** `docs/specs/SPEC.md`。错一个数字，全盘皆输——所以这一步的产出**必须你亲自逐行读一遍并签字**。后面所有「口径」争论（字段名、量纲、KPI 定义、端点契约）都以它终审。

SPEC.md **只写四章**：**KPI 口径**（节能率/舒适度/P95）、**数据契约**（events.jsonl 行格式 + 7 个前端轮询端点）、**字段表**（`elec_kwh` 唯一名）、**量纲**（舒适度归一化 [0,1]）。每个数字必须标注来源 file:line，写不出来的留「待确认」标记，**禁止编造**。

### 8.1 怎么干

1. **发提示词**：

   ```
   任务：从旧仓库提炼 docs/specs/SPEC.md。信息源（只读）：
   - 旧仓库 README.md、docs/ 下所有文档
   - KPI 口径：energy_system/algorithms/ 下 comfort_eval.py（94 行，两套口径同文件）、
     comfort_kpi.py（109 行）、peak_kpi.py（83 行）、energy_saving.py（46 行）
   - 数据契约：energy_system/api/app.py（8 端点全在工厂）、energy_system/api/schemas.py（121 行）
   - 字段表：energy_system/domain/telemetry.py（159 行，单一真值设计）、
     energy_system/domain/metrics.py（163 行）
   起 3 个 reader 副智能体（provider=deepseek、model=deepseek-flash，显式指定）
   分头读，你综合。SPEC.md 只写四章：KPI口径/数据契约/字段表/量纲。
   每个数字必须标注来源 file:line。写不出来的留「待确认」标记，禁止编造。
   ```

   预期看到：3 个 child 并行读完各自回报；主智能体综合出 SPEC.md 草稿。**spawn 后看一眼 child 详情里的模型名**（步 5.3 的继承陷阱），确认是 `deepseek-flash` 再放行。

2. **你亲自逐行读**，重点核对三类数字：
   - KPI 定义（节能率怎么算、舒适度归一化区间、P95 统计口径）
   - 字段名（`elec_kwh` 是不是唯一名，有没有 `kwh`/`energy_kwh` 别名残留）
   - 端点契约（`energy_system/api/app.py` 工厂共 8 个端点、前端轮询其中 7 个——路径、方法、返回字段都以 SPEC 为准）

   预期看到：每个数字后面都有 `file:line`；对不上的标「待确认」，回旧仓库查证。

3. **签字**：在 SPEC.md 末尾加一行 `> 口径签字：<你的名字>，<日期>。此后改动必须先写 ADR。`

### 8.2 怎么验

SPEC.md 存在且只有四章；每个数字有 file:line 来源；「待确认」项已清零或列出查证计划；**你签了字**。
**错了怎么退**：删文件重写（本步无代码）。

---

## 第 9 步 · 建新仓库 + CI + AGENTS.md + flag 框架

**预计时间**：1 天｜**前置**：第 3、8 步｜**分支**：`chore/bootstrap`

**干什么**：新仓库地基。第 3 步的三个配置文件草稿 + 第 7 步的 README/ADR + 第 8 步的 SPEC，连同事先立好的「法律」（秩测试 + flag 框架 + AGENTS.md）一起落库。**秩测试是第一个真实 commit**——从第一天起，架构分层就有机械门禁。

### 9.1 怎么干

1. **在 GitHub 建空仓库**：New repository → 名字 `ecosentinel-v2` → **不要**初始化 README/.gitignore/license（保持空白，第 2 步的本地 init 才是第一次提交）。创建后记下 HTTPS 地址。

2. **本地建仓 + 拉骨架**：

   ```bash
   mkdir ~/ecosentinel-v2 && cd ~/ecosentinel-v2
   git init
   git remote add origin <第 1 步记下的仓库地址>

   # 固定 Python + 建环境 + 装依赖（读第 3 步的 pyproject.toml）
   cp ~/ecosentinel-config-draft/pyproject.toml .
   echo "3.12" > .python-version
   uv venv && uv sync --all-extras --dev
   ```

   预期看到：`uv sync` 装完全部依赖，生成 `uv.lock`；`.venv/` 出现。

3. **建目录骨架**（对照开头「新仓库完整目标树」）：

   ```bash
   mkdir -p src/energy_system/{api,service,simulation,domain,infra,config,contracts,testing} \
            src/energy_system/domain/{control,ai} \
            src/web/src/{hooks,store,components,lib,contracts} \
            src/firmware \
            scripts tools \
            tests/contract tests/perf \
            docs/specs docs/contracts docs/adr \
            config .github/workflows

   # 每个包一个 __init__.py（步 13 填内容；contracts 的产物由 gen_schemas.py 生成）
   touch src/energy_system/__init__.py \
         src/energy_system/{api,service,simulation,domain,infra,config,contracts,testing}/__init__.py \
         src/energy_system/domain/{control,ai}/__init__.py
   ```

   预期看到：目录树与「新仓库完整目标树」一致（缺的后面各步补）。

4. **复制草稿箱三件套进库**：

   ```bash
   cp ~/ecosentinel-config-draft/.pre-commit-config.yaml .
   mkdir -p .github && cp ~/ecosentinel-config-draft/.github/workflows/ci.yml .github/workflows/
   ```

5. **写 `.gitignore`**：

   ```gitignore
   .venv/
   __pycache__/
   *.pyc
   .pytest_cache/
   .mypy_cache/
   .ruff_cache/
   node_modules/
   dist/
   .pio/
   data/
   *.log
   .env
   ```

6. **复制文档资产**（第 7/8 步产出）：

   ```bash
   cp ~/ecosentinel-config-draft/README.md .                    # 第 7 步写的路线第一段
   cp ~/ecosentinel-config-draft/docs/adr/0002-single-evolution-track.md docs/adr/
   cp ~/ecosentinel-config-draft/docs/specs/SPEC.md docs/specs/  # 第 8 步签过字的
   ```

7. **第一个真实 commit：分层秩测试**（**第一个提交的就是它**——架构门禁先于任何业务代码）。旧仓库那份 `test_layering.py` 测的是旧仓库的平铺模块；**要搬的是秩规则，不是 import 路径**：

   ```bash
   mkdir -p tests/contract
   cp ~/EcoSentinel/tests/contract/test_layering.py tests/contract/test_layering.py
   ```

   然后把秩表按**新仓库包名**重写一遍（**秩的方向一条不动**，动的只是模块名——这正是 AGENTS.md「新包必须登记层级」的含义，不是「改门禁让测试过」）：

   ```python
   # tests/contract/test_layering.py —— 秩表（新仓库包名）
   LAYERS = {
       "energy_system.api": 1,
       "energy_system.service": 2,
       "energy_system.simulation": 3,   # 跑领域模型的应用设施
       "energy_system.domain": 4,       # 纯领域逻辑（对应旧仓库 AGENTS.md 的 core）
       "energy_system.infra": 5,
   }
   # 断言：每个包只许 import 秩 >= 自己的包；domain import simulation → 红
   ```

   ```bash
   git add -A && git commit -m "test(contract): 分层秩测试作为第一个 commit

   Intent: 架构分层门禁先于业务代码落地
   Scope: tests/contract/test_layering.py（秩规则取自旧仓库，模块名按新包名重写）
   Boundaries: 秩的方向不动（api → service → simulation → domain → infra）；
              只把旧仓库平铺模块名换成 energy_system.* 新包名
   Evidence: uv run pytest -q tests/contract/ 全绿
   Recovery: revert"
   git push -u origin main
   ```

   预期看到：CI 触发。此时 CI 的覆盖率岗会失败（还没有 `energy_system` 包的代码，覆盖率 0 < 80）——**这是预期的**，见第 9.2 节的处置。

8. **flag 框架两个文件**：

   `src/energy_system/config/feature_flags.py`：

   ```python
   """Feature flag 登记处。每个 flag 必须同时在 docs/FLAGS.md 登记
   （flag 名 / 默认值 / 删除条件 / 引入步号）——出生时登记死期，
   步 41「flag 清零」才执行得下去。"""

   from __future__ import annotations

   import os


   def _flag(name: str, default: bool) -> bool:
       """flag 从环境变量读，缺省用默认值。测试里用 monkeypatch 覆盖。"""
       return os.environ.get(name, "1" if default else "0") in ("1", "true", "True")


   # ---- 本手册各步引入的 flag（默认值 = 该步的安全态）----
   FLAGS: dict[str, bool] = {
       "FLAG_DATA_TAIL_READ": False,     # 步 19：D5 尾读（默认关，走旧路径）
       "FLAG_SQLITE_STORE": False,       # 步 20：R2 SQLite 存储
       "FLAG_SIM_FIX": False,            # 步 21：D1 仿真单实例修复
       "FLAG_SEND_RESULT": False,        # 步 22：D2 下发结果语义
       "FLAG_DAY_ROLLOVER": False,       # 步 23：D3 跨午夜电量
       "FLAG_CONTROL_MERGED": False,     # 步 24：控制层合并
       "FLAG_KPI_MERGED": False,         # 步 25：KPI 层合并
       "FLAG_COMFORT_NORM": False,       # 步 26：D4 舒适度量纲统一
       "FLAG_AI_SIM": False,             # 步 27：R4 AI 门面
       "FLAG_CONFIG_V2": False,          # 步 28：R5 配置
       "FLAG_PIPELINE": False,           # 步 29：R3 决策管线
       "FLAG_AUTH": False,               # 步 31：D9 鉴权（先 warn 后 enforce）
       "FLAG_WEB_REACT": False,          # 步 35：R6 新前端
       "FLAG_BOARD_STREAMLIT": False,    # 步 37：R8 看板收敛
       "FLAG_FIRMWARE_V2": False,        # 步 38：D10/R7 固件
   }


   def enabled(name: str) -> bool:
       """查询 flag。未登记的 flag 直接报错——防止智能体私设开关。"""
       if name not in FLAGS:
           raise KeyError(f"flag {name!r} 未在 FLAGS 登记；先加进本字典和 docs/FLAGS.md")
       return _flag(name, FLAGS[name])
   ```

   `docs/FLAGS.md`：

   ```markdown
   # FLAGS.md — feature flag 登记册

   > 纪律：每个引入 flag 的 commit 必须同步更新本表（flag 名/默认值/删除条件/引入步号）。
   > 步 41 要求本表活跃项 = 0；删不掉的 flag = 对应合并没完工，回对应 Phase 收尾。

   | flag | 默认 | 引入步 | 删除条件 |
   |---|---|---|---|
   | FLAG_DATA_TAIL_READ | 关 | 19 | shadow 双跑一周无回归且你批准 |
   | FLAG_SQLITE_STORE | 关 | 20 | 双实现对拍一致 + 一周无回归 |
   | FLAG_SIM_FIX | 关 | 21 | 复现测试绿 + dyn1 探针输出真实计数 |
   | FLAG_SEND_RESULT | 关 | 22 | 连续 3 轮重发测试绿 |
   | FLAG_DAY_ROLLOVER | 关 | 23 | 跨午夜测试绿 + dyn3 探针消失 |
   | FLAG_CONTROL_MERGED | 关 | 24 | 同种子 1000 步逐位相等 |
   | FLAG_KPI_MERGED | 关 | 25 | shadow 最大偏差 < 1e-9 |
   | FLAG_COMFORT_NORM | 关 | 26 | shadow 双跑两周偏差 < 1e-6 + 你批准 |
   | FLAG_AI_SIM | 关 | 27 | 旧测试不改断言全绿 + stub 不可达有测试 |
   | FLAG_CONFIG_V2 | 关 | 28 | 坏配置 fail-loud 测试绿 |
   | FLAG_PIPELINE | 关 | 29 | usecases(app) 消失 + 审计事件有覆盖 |
   | FLAG_AUTH | 关 | 31 | 5 类 payload 被拒 + 7/7 契约仍绿 |
   | FLAG_WEB_REACT | 关 | 35 | E2E 绿 + 首包 < 150 kB + 并行一周 |
   | FLAG_BOARD_STREAMLIT | 关 | 37 | 仅一个业务看板 + 旧服务已删 |
   | FLAG_FIRMWARE_V2 | 关 | 38 | 负例测试绿 + 硬件联调通过 |
   ```

9. **AGENTS.md**（下面全文，手工雕琢，**不许用 `/init` 自动生成**）：

   `AGENTS.md`：

   ```markdown
   # EcoSentinel AGENTS.md（智能体宪法）

   ## 命令（置顶；改动此处必须同步改真实命令）
   - 环境：Python 3.12 / Node 22 / PlatformIO（固件）
   - 装依赖：uv sync --all-extras --dev ；前端 npm ci
   - 全量测试：uv run pytest -q          （不全绿 = 任务没完成）
   - 覆盖率门禁：uv run pytest -q --cov=energy_system   （fail_under=80，见 pyproject.toml）
   - 类型检查：uv run mypy src/ ；npx tsc --noEmit
   - 性能验收：uv run pytest -q -m perf   （120k 行尾读 P95 < 50ms；首包 gzip < 150kB）
   - lint/格式：pre-commit 自动跑；智能体不许手动跑 linter、不许手动调格式

   ## 架构规则（机械门禁：tests/contract/test_layering.py）
   - 分层秩：energy_system.api → service → simulation → domain → infra；禁止反向依赖
   - domain 不许依赖 simulation（simulation 是跑领域模型的应用设施，只能自上而下被依赖；
     对应旧 AGENTS.md「core 不许依赖 simulation」——v2 无 core 包，纯领域逻辑在 domain）
   - 新包必须在 tests/contract/test_layering.py 登记层级
   - 每个领域概念只允许一个实现；发现双实现 = 报告主智能体，禁止加第三套
   - 跨层数据只走契约（Pydantic schema / TypedDict），禁止裸 dict

   ## 已知陷阱（旧仓库实测踩过的坑，禁止再踩）
   - JSONL 必须尾读（seek 末 256KB）；禁止全量 read（120k 行全量 670ms）
   - 舒适度量纲唯一：归一化 [0,1]；字段名 elec_kwh 全仓唯一，禁止 kwh/energy_kwh 别名
   - 异常处理 fail-loud：禁止静默 catch 注入异常
   - 模拟器必须真实执行模型；禁止编造 plausible 数字
   - 设备离线必须真实探测；禁止假 online
   - label 必须校验 ^[A-Za-z0-9_-]{1,32}$；禁止裸拼文件路径（路径穿越）

   ## 边界（永远不许）
   - 不许改 tests/contract/test_layering.py 的秩表来让测试通过——改架构，不改门禁
   - 不许新建双实现；合并走 branch-by-abstraction + feature flag（docs/adr/0004）
   - 不许改 docs/specs/SPEC.md 的 KPI 口径——那是规格；要改先写 ADR
   - 不许碰 .env、密钥、真实硬件；硬件交互只经 HardwareAbstraction 接口
   - 不许在没写表征测试的情况下顺手重构碰到的旧代码
   - 副智能体不许改 AGENTS.md、spec、门禁配置

   ## 工作流
   - 大任务四步：explore（只读）→ plan（等人类批准）→ implement → verify
   - 一次只做一个接缝（docs/specs/SEAMS.md 列出全部 8 个）
   - 每个 commit 带契约卡：Intent / Scope / Boundaries / Evidence / Recovery
   - 会话连续两次修正失败 → 停下，写更好的初始提示重开
   - 主智能体（Kimi）：规划、规格、裁决。副智能体（Flash）：按任务卡机械执行 + 独立审计

   ## 文档地图（渐进披露，按需读）
   - docs/specs/SPEC.md        系统行为规格（KPI、契约、字段口径）——唯一事实源
   - docs/specs/SEAMS.md       8 个合并接缝的清单与进度
   - docs/contracts/           契约卡 C1–C8（每个任务的五字段合同）
   - docs/adr/                 决策记录（0002 演进路线；0004 合并策略；各接缝 ADR）
   - docs/FLAGS.md             活跃 feature flag 及删除条件
   - docs/FINDINGS.md          智能体「发现但不处理」清单
   - docs/STATUS.md            每周进度看板
   ```

   **写作铁律**（2500+ 仓库的分析 + Anthropic 实践）：**<300 行，理想 <60 行**——超过一屏读不完，无关指令会稀释成「整个文件被忽略」；命令置顶，带完整 flags；代码优于文字；具体到版本；明确边界；渐进披露（细节放 `docs/`，AGENTS.md 只放指针——别粘贴代码片段，会腐烂，用 file:line 指向权威位置）；别把智能体当 linter（格式化交给 pre-commit hook）；别自动生成（`/init` 生成的膨胀文件是负资产，手工雕琢）。

   配套：子目录可放嵌套 AGENTS.md（最近的优先）。新仓库至少三个：根 / `src/energy_system/` / `src/web/`。

10. **提交清单**（每项一个 commit，Conventional Commits 格式，全部完成后 `git push`）：

    | # | 提交内容 | commit 类型 |
    |---|---|---|
    | 1 | `tests/contract/test_layering.py`（秩测试，第一个真实 commit） | `test(contract):` |
    | 2 | `src/energy_system/config/feature_flags.py` + `docs/FLAGS.md` | `feat(config):` |
    | 3 | `pyproject.toml` + `.pre-commit-config.yaml` + `.github/workflows/ci.yml` + `.gitignore` | `chore:` |
    | 4 | `README.md` + `docs/adr/0002-*.md` + `docs/specs/SPEC.md` | `docs:` |
    | 5 | `AGENTS.md`（根 + `src/energy_system/` + `src/web/` 三份嵌套） | `docs:` |

11. **给 main 加保护规则**（GitHub 仓库 Settings → Branches）：必须 CI 绿才能合并、禁止 force push、squash merge。

### 9.2 关于「CI 覆盖率岗现在会红」的处置

第 7 小步推上空骨架时，覆盖率岗必然失败（`energy_system` 还没有代码，覆盖率 0）。两种处置选一：

- **推荐**：第一个 commit 不带 ci.yml（第 3 项提交里先只放 pyproject + pre-commit），等第 13 步骨架 + 契约建好、第 14 步测试迁入、覆盖率过 80 后再提交 ci.yml。
- 或者：现在就提交 ci.yml，接受前两周 CI 红，把「覆盖率岗转绿」当作第 14 步的验收之一。

无论哪种，**秩测试和 pre-commit 从第一个 commit 起就是活的**——这两道门禁等不起。

### 9.3 怎么验

```bash
cd ~/ecosentinel-v2
uv run pytest -q                        # 秩测试绿
uv sync --frozen                        # 锁文件有效
git log --oneline | head -5             # 5 个 commit 按清单顺序
```

预期：秩测试绿；锁文件有效；commit 清单齐。
**错了怎么退**：`git revert` 对应 commit；最坏情况删库重来（本步无业务代码，成本最低）。

---

## 第 10 步 · 写契约卡 C1–C8 + SEAMS.md 裁决表

**预计时间**：1 天｜**前置**：第 9 步｜**分支**：`docs/contracts`

**干什么**：两份文件。**契约卡**是每个任务的五字段合同（Intent/Scope/Boundaries/Evidence/Recovery）——没有卡片不派活；**SEAMS.md** 是 8 个双实现接缝的裁决表——「以 X 为准，禁止迁移 Y」，它是后续所有 builder 的任务边界来源。**两张表都要你 review 签字。**

### 10.1 SEAMS.md（先生成，你签字）

```
读审阅报告 §11「双实现清单」和第 2 步的资产/债务分流表。
生成 docs/specs/SEAMS.md：8 个接缝，每个接缝一张表：
接缝名/正确实现(file:line)/错误实现(file:line)/裁决(以正确为准)/
合并策略(branch-by-abstraction 或直接替换)/对应契约卡编号。
```

预期看到：8 行接缝表，每行的「正确实现」都能在旧仓库速查表里对上 file:line。

### 10.2 八张预制契约卡（C1–C8）全文

> 每张卡就是一次分支 + 一次 PR + 若干 commit。Evidence 行全部来自审阅报告实测数字。后面各步的任务卡是这些卡的实例化。

**契约卡 C1 — D5 尾读迁移（第 19 步用）**

```
Intent: 消除 JSONL 全量读的性能缺陷（7 天数据即劣化至 670ms+）
Scope: 仅 src/energy_system/infra/data_store.py（新建）；tests/test_data_store.py（新建）
Boundaries: 不改任何调用方；读接口签名冻结；events.jsonl 行格式不变（30 字段白名单）
Evidence: 新增测试：120k 行文件 read_tail P95 < 50ms；全量 pytest 绿
Recovery: flag FLAG_DATA_TAIL_READ 默认关；旧路径不动
迁移源: 旧仓库 dashboard/data_loader.py:10-43 是正确实现——照搬其逻辑
        （seek 末 256KB + 逐行解析 + 丢弃不完整尾行），禁止重新发明
禁止: 迁移旧仓库中任何 read_all 全量读代码
```

**契约卡 C2 — D4 舒适度量纲统一（第 26 步用）**

```
Intent: 消除舒适度两套量纲——同一份数据 /snapshot 返回 0.5、/chart 返回 50.0（差 100 倍）；
        全仓唯一为 [0,1] 占比口径（band_share，IPMVP），显示格式化交给前端
Scope: src/energy_system/domain/comfort.py（新建，唯一口径）；其调用方（白名单见 docs/SEAMS.md#comfort）
Boundaries: API 响应 schema 中该字段名与量纲冻结（先查 docs/SPEC.md）；不动 KPI 定义
Evidence: 契约测试断言 /snapshot 与 /chart 口径一致且输出 ∈ [0,1]；Dark Launch 影子对比两周：
         新旧实现在同一输入序列下最大偏差 < 1e-6（除已知修正点）
Recovery: FLAG_COMFORT_NORM，关即回旧量纲
迁移源: 旧仓库 energy_system/algorithms/comfort_eval.py（94 行）两套口径同文件：
        band_share（IPMVP 占比口径，为准）与 TCI（0–1，已被官方否定，禁止迁移）；
        ×100 变体在 energy_system/api/services.py:102，禁止迁移
```

**契约卡 C3 — 控制层合并（第 24 步用，branch by abstraction 第一步）**

```
Intent: 消除控制层双实现——生产路径 energy_system/core/command_policy.py（139 行）
        + energy_system/core/command_dispatcher.py（146 行）vs energy_system/core/control/*
        （206 行，ControlPlan/Compiler/ActuationService/Transport，生产未接线）；
        收敛为 src/energy_system/domain/control/ 唯一纯函数实现
Scope: src/energy_system/domain/control/（新建/改写）；tests/contract/ 不动
Boundaries: 本次只建抽象与适配，不切换调用方（下一步才切）；
        控制算法数值行为逐位一致；
        RELAY 1/2 通道保留规则以 command_policy 为准——core/control/compiler 直发
        RELAY 1/2 与保留规则冲突，接入前必须对齐
Evidence: 用旧仓库同一随机种子跑 1000 步，新旧输出逐位相等（测试断言）
Recovery: FLAG_CONTROL_MERGED；抽象建立本身即可独立合并（无行为变更）
步骤: ①抽象接口（合main）②旧实现适配到接口（合main，行为不变）
     ③新唯一实现 behind flag（合main）④切换 ⑤删适配层
```

**契约卡 C4 — AI 层合并（第 27 步用）**

```
Intent: 消除 AI 双实现——energy_system/algorithms/ai_advisor.py（323 行，生产在用但
        "半提取"：自带统计与内联熔断副本）vs energy_system/ai/circuit_breaker.py
        （83 行，干净、可注入时钟，但只被测试引用）+ energy_system/ai/service.py
        （88 行，半成品门面）；收敛为 src/energy_system/domain/ai/ 唯一门面 + 唯一熔断（报告 R4）
Scope: src/energy_system/domain/ai/（唯一实现 + provider 抽象）
Boundaries: 熔断状态机契约（CLOSED/OPEN/HALF_OPEN）与旧仓库 ai/circuit_breaker.py 一致；
        provider 可换（LLM 是租来的），契约不换
Evidence: 旧仓库 AI 层对应测试全量迁移后不改断言全绿；内联熔断副本删除且有测试证明不可达
Recovery: FLAG_AI_SIM；provider 抽象允许无 key 环境显式报 NO_LLM 错误（不静默、不返回假结果）
禁止: 迁移内联熔断副本；迁移「client_unavailable 计失败、无 key 两轮清池」的现状缺陷；
        「无 key 时返回 plausible 假结果」
保留: energy_system/ai/prompt_builder.py 的白名单机制（16 字段，密钥/路径/堆栈永不外发）
        是全仓最佳实践，原样保留；但须修 frozenset 迭代顺序随哈希变（实测三次三序）
        → 提示词不可复现的问题（改有序结构）
```

**契约卡 C5 — D1/D2/D3 数据正确性三连修（第 21–23 步用）**

```
Intent: 修阻断计数读错实例（0 vs 134）、失败下发被当成功缓存、跨午夜电量重复累计
Scope: src/energy_system/domain/*.py 对应三处；每个缺陷一个独立 commit + 独立分支
Boundaries: 先写失败测试固化「错误行为」→ 再修 → 测试转绿；
        不许一次性改三处（回滚粒度）
Evidence: 三个新测试分别复现报告 §7 的原始证据链；全量 pytest 绿
Recovery: 各自独立 revert（这就是拆三个分支的原因）
提示词要点: 先让智能体读旧仓库 energy_system/simulation/simulator.py:29-35，
        用 5 行复述「为什么 _controllers[mode] 和 self.controller 是两个实例」——理解优先于动手
```

**契约卡 C6 — D6/D7 假状态清除（第 32 步用，前端 + API）**

```
Intent: 删除前端「假在线」三处、API 假字段（serial_connected=true / retry_count=0 /
        risk="低" / simulation_params 虚构）、残留 29.9% 节能率文案
Scope: src/web/（新前端从零，只接真实字段）；src/energy_system/api/
Boundaries: 禁止把「假但好看」的字段搬进新前端；真实离线必须显式展示
Evidence: API 测试断言无假字段；前端 56 个旧测试迁移后全绿；首包 gzip < 150 kB
Recovery: 纯删除性变更，revert 即恢复
迁移源: 前端假在线三处：app/src/store/useAppStore.ts:94-100（初始播种 mock）、
        app/src/components/layout/TopBar.tsx:30、app/src/services/api.ts:206；
        API 假字段：energy_system/api/services.py:157,168,187,216（报告 §7 D6）
```

**契约卡 C7 — D9 安全加固（第 31 步用）**

```
Intent: 修 label 路径穿越、API 无鉴权、默认 0.0.0.0 三项（MQTT 裸奔属 D10，见步 38）
Scope: src/energy_system/api/（label 校验 + 鉴权中间件）；config 启动校验
Boundaries: label 白名单校验（re.fullmatch(r"[A-Za-z0-9_-]{1,32}", label) + resolve()
        校验，报告原文，大小写不改）；默认绑定 127.0.0.1；鉴权分阶段开
Evidence: 新增安全测试（穿越 payload 列表：../, ..\, %2e, 空 label, 超长 label）；
        全量 pytest 绿
Recovery: 各自独立分支；鉴权可用 flag 分阶段开（先 label 校验，后鉴权）
迁移源: energy_system/persistence/jsonl_repository.py:39-41,106（label 直拼路径）；
        api_server.py:60-68（仓库根入口：无鉴权 + 默认 0.0.0.0）
```

**契约卡 C8 — R6/R8 前端收敛（第 35 步用）**

```
Intent: 消除前端双实现——dashboard.py（Streamlit，第二套业务看板，8501）vs app/
        （React + Vite，3000）；只保留 React 作为唯一业务看板
Scope: src/web/（新前端从零）；旧 Streamlit 业务视图删除（第 37 步执行）
Boundaries: 先契约测试锁定 7/7 端点行为；E2E（playwright）覆盖核心路径后切换
Evidence: 56 旧测试迁移全绿 + E2E 绿 + 首包 gzip < 150 kB + React 提交次数 −50%
Recovery: FLAG_WEB_REACT；Streamlit 旧看板并行存活至 React 版稳定一周后删（铁律 2）
```

### 10.3 怎么验

```bash
ls docs/contracts/ docs/specs/SEAMS.md
```

预期：8 张卡在 `docs/contracts/`（每张一个文件，如 `C1-tail-read.md`）；SEAMS.md 8 个接缝齐全；**你 review 签字**。
**错了怎么退**：改文件（本步无代码）。

---

## 第 11 步 · 新建四个行为探针到 tools/

**预计时间**：半天｜**前置**：第 10 步｜**分支**：`chore/probes`

**干什么**：在项目里建立 `tools/` 目录并**新写**四个行为探针（`dyn1/dyn3/perf/api_probe`）。**这是「先钉行为」的物理载体——后面每个缺陷修复前，先跑对应探针确认缺陷存在；修复后再跑，确认现象消失。**

> ### ⚠️ 核对更正：旧仓库**没有** `tools/` 目录
>
> 实测 `Test-Path tools` = **False**；`dyn1.py` / `dyn3.py` / `perf.py` / `api_probe.py`
> **四个文件一个都不存在**。原手册写"把旧仓库 tools/ 下四个脚本复制过来"——**源头无物，此步会直接卡死**。
>
> **本步改为「新写」**，11.3 给出可直接落盘的完整代码。要复现的缺陷 D1/D2/D3/D5/D9
> **均已实测确认存在**，因此新写的探针能够复现报告现象。

### 11.1 PROBE_TARGET 约定（先懂这个再迁）

探针要能跑在**两套代码**上：修复前跑旧仓库实现（复现缺陷），修复后跑新仓库实现（验证修复）。约定：每个探针头部有 `TARGET` 逻辑——`PROBE_TARGET` 环境变量指向「包含 `energy_system` 包的目录」，**默认旧仓库根目录**；指向新仓库时设 `PROBE_TARGET=src`（相对新仓库根）。

```python
# 每个探针头部的统一约定（照此改旧仓库探针的 import）
import os
import sys
from pathlib import Path

TARGET = os.environ.get("PROBE_TARGET", "../../EcoSentinel")   # 默认：旧仓库
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / TARGET))

from energy_system.simulation.simulator import Simulator   # noqa: E402
```

`api_probe.py` 同理，加一个目标地址约定：

```python
API_BASE = os.environ.get("PROBE_API_BASE", "http://127.0.0.1:8000")  # 默认旧服务；步 33 起指向新服务
```

**各探针分工**：

| 探针 | 测什么现象（报告附录 A） | 哪几步用它 |
|---|---|---|
| `tools/dyn1.py` | 阻断计数 0 vs 134 | 步 21 |
| `tools/dyn3.py` | 失败缓存、跨日电量、label 穿越 | 步 22、23、31 |
| `tools/perf.py` | 670ms vs 1.1ms | 步 19 |
| `tools/api_probe.py` | API 假字段 | 步 32、33 |

### 11.2 怎么干

1. **建目录并新写**（不是复制）：`mkdir -p tools && touch tools/__init__.py`，再按 **11.3** 的代码逐个落盘。**不要**去找"旧仓库的 tools/"，它不存在。

2. **跑一遍（默认指向旧仓库，应复现报告现象）**：

   ```bash
   cd ~/ecosentinel-v2
   uv run python tools/dyn1.py      # 预期：阻断 0 vs 134（复现）
   uv run python tools/dyn3.py      # 预期：失败缓存、跨日电量、label 穿越（复现）
   uv run python tools/perf.py      # 预期：670ms vs 1.1ms（复现）
   uv run python tools/api_probe.py # 预期：假字段（复现；需旧 API 服务在 127.0.0.1:8000 跑着）
   ```

   预期看到：四个探针的输出与报告附录 A 记录的现象一致。**复现不出来 = 迁移改了逻辑**，检查 import 和 TARGET 路径，不许「差不多就行」。

   > `api_probe.py` 需要旧服务在跑：`cd ~/EcoSentinel && uv run python api_server.py --port 8000`（或旧仓库 README 里的启动方式）。旧服务只读不写，放心跑。

3. **提交**：`chore(tools): 迁移四个行为探针 + PROBE_TARGET 约定`。

### 11.3 四个探针的可落地实现（直接落盘）

> 以下代码按**实测行为**编写：D1 的实例分裂、D5 的全量读都已在本仓库验证会复现。
> **不要**为了让探针"跑通"去改断言——探针的价值就是复现缺陷。

**`tools/dyn1.py` — 复现 D1「读错实例」**

```python
"""探针 dyn1：复现 D1 —— compare 读了错误的 controller 实例。

预期（修复前）：sim.controller.short_cycle_blocks = 0
                _controllers["saving"].short_cycle_blocks = 134
两者不等 ⇒ D1 复现
"""
import os
import sys
from pathlib import Path

TARGET = os.environ.get("PROBE_TARGET", "../../EcoSentinel")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / TARGET))

from energy_system.simulation.simulator import Simulator  # noqa: E402


def main() -> int:
    sim = Simulator(mode="saving", seed=42)
    sim.run_simulation()

    attr = "short_cycle_blocks"
    via_ctrl = getattr(sim.controller, attr, None)
    real = getattr(sim._controllers.get("saving"), attr, None)

    print("sim.controller.%-22s = %s" % (attr, via_ctrl))
    print("_controllers['saving'].%-14s = %s" % (attr, real))
    print("SAME INSTANCE?                 =", sim.controller is sim._controllers.get("saving"))

    if via_ctrl != real:
        print(">>> D1 复现：两个实例不一致（compare.py 读到了错误那个）")
    else:
        print(">>> D1 已修复：两个数一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

> 实测参考值：`sim.controller = 0`，`_controllers['saving'] = 134`，`SAME INSTANCE = False`。

**`tools/perf.py` — 量化 D5「latest/tail/read_since 都走全量读」**

```python
"""探针 perf：生成 N 行合成 JSONL，分别计时四类读取。"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

TARGET = os.environ.get("PROBE_TARGET", "../../EcoSentinel")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / TARGET))

from energy_system.persistence.jsonl_repository import JsonlRepository  # noqa: E402

N = int(os.environ.get("PROBE_ROWS", "120000"))


def make_file(path: Path, n: int) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for i in range(n):
            fh.write(json.dumps({
                "timestamp": "2026-10-01T00:%02d:%02d" % (i // 60 % 60, i % 60),
                "temperature": 24.0 + (i % 5) * 0.1,
                "comfort_score": 0.5,
            }, ensure_ascii=False) + "\n")


def timed(label, fn):
    t0 = time.perf_counter()
    fn()
    print("%-24s %8.1f ms" % (label, (time.perf_counter() - t0) * 1000))


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "hardware_probe.jsonl"
        make_file(p, N)
        print("rows=%d  size=%.1f MB" % (N, p.stat().st_size / 1e6))
        repo = JsonlRepository(log_dir=p.parent, run_label="probe")
        timed("read_all", lambda: repo.read_all("probe"))
        timed("latest", lambda: repo.latest("probe"))
        timed("tail(200)", lambda: repo.tail(200, "probe"))
        timed("read_since(300s)", lambda: repo.read_since(300, "probe"))
        print(">>> 目标：修复后每项 P95 < 50 ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

> `JsonlRepository` 的构造参数请以 `energy_system/persistence/jsonl_repository.py:34-41` 为准，先 `grep` 再落盘。

**`tools/dyn3.py` — 复现 D3「跨午夜电量重复累计」**

```python
"""探针 dyn3：把日基线强制重置后再累计一次，观察是否重复相加。"""
import os
import sys
import tempfile
from pathlib import Path

TARGET = os.environ.get("PROBE_TARGET", "../../EcoSentinel")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / TARGET))

from energy_system.core.log_manager import LogManager  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        os.chdir(td)                      # log_manager 用 CWD 相对路径（D8 相关）
        lm = LogManager(run_label="probe")
        # 实际方法名以 log_manager.py:89-114 为准（可能是 _write_daily / update_energy）
        writer = None
        for name in ("update_daily_from_row", "_write_daily", "update_energy"):
            if hasattr(lm, name):
                writer = getattr(lm, name)
                break
        if writer is None:
            print("!! 找不到日累计写入方法，请先 grep log_manager.py")
            return 2

        row = {"energy_wh": 100.0, "solar_energy_wh": 10.0, "soc_percent": 50.0}
        writer(row)
        # 模拟跨午夜：清空进程内基线缓存后再次写入
        lm._daily_baseline_date = None
        lm._daily_baseline = (0.0, 0.0)
        writer(row)

        files = sorted(Path("logs").glob("daily_energy_*.json"))
        print("daily files:", [f.name for f in files])
        if files:
            print("content:", files[0].read_text(encoding="utf-8")[:300])
            print(">>> 若 load_energy_wh ≈ 200（而非 100）即为 D3 复现")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**`tools/api_probe.py` — 查 D6「API 语义伪造」**

```python
"""探针 api_probe：检查 /api/health 是否把"无数据"伪造成具体值。"""
import json
import os
import urllib.request

API_BASE = os.environ.get("PROBE_API_BASE", "http://127.0.0.1:8000")
SUSPECT = ("retry_count", "sampling_rate_hz", "stale_detected", "serial_connected")


def main() -> int:
    url = API_BASE.rstrip("/") + "/api/health"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            body = json.loads(r.read().decode("utf-8"))
    except Exception as exc:
        print("!! 无法访问", url, "->", exc)
        print("   先起服务：uv run python api_server.py --port 8000")
        return 2

    print("GET", url)
    print(json.dumps(body, ensure_ascii=False, indent=2)[:600])
    hits = [k for k in SUSPECT if k in body]
    print("可疑字段:", hits)
    print(">>> D6 复现：无数据时仍返回具体值（修复后应为 null）" if hits
          else ">>> D6 已修复：无来源字段为 null")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**验收**：四个探针跑完，终端各应出现 `>>> Dx 复现` 字样。把输出贴进验收记录。

### 11.4 怎么验

四个探针在默认目标（旧仓库）下复现报告现象；`PROBE_TARGET=src uv run python tools/dyn1.py` 此刻应该报 ImportError（新仓库还没建 simulator）——**这是预期的**，第 21 步建好后同一条命令就要输出真实计数。
**错了怎么退**：删 `tools/`（只加文件，无风险）。

---

## 第 12 步 · （你本人）递交专利申请

**预计时间**：智能体替代不了，你本人跑流程｜**前置**：无（越早越好，第 1 周内）｜**分支**：无

**干什么**：报告风险表原文：「专利公开时点 | 中 | **极高** | 先申请再公开」；§14.3：「先申请专利：在所有公开之前」。这是**人类动作**：整理技术交底书 → 递交 → 拿到申请日。**递完才能对外开源/发布。**

### 12.1 怎么干

1. 从旧仓库和审阅报告整理技术交底书：创新点写「LLM 参与闭环的安全边界与评测方法」（第 7 步的硬约束），不是「LLM 节能」。
2. 递交，拿到**申请日**（受理通知书）。
3. 把申请日记进 `docs/adr/` 之外的一个安全位置（含技术细节，**不进 git**）。

### 12.2 怎么验

拿到专利申请受理通知书（申请日）。
**错了怎么退**：无（行政流程）。

---

## 第 13 步 · 分层骨架 + Pydantic 契约 + schema codegen（R1）

**预计时间**：3 天｜**前置**：第 11 步｜**分支**：`refactor/layered-skeleton`｜**契约卡**：新建（R1）

**干什么**：四层空壳（api → service → domain → infra，每层 `__init__.py` 只导出契约类型）+ **契约包 `contracts/`**（R1 落点四件套之一）+ 把旧仓库 `energy_system/domain/telemetry.py`（159 行，单一真值设计）的 schema 结构迁为 Pydantic 契约 + **schema codegen**：从 SPEC.md 字段表生成 Py / TS / 固件三份产物——契约测试从 422 行降到 <80 行。

**本步文件**：

```text
ecosentinel-v2/
├── src/energy_system/
│   ├── __init__.py                    ✅ 填内容（导出契约类型）
│   ├── contracts/                     ✅ R1 落点：codegen 的 Py 产物（步 9 已建空壳）
│   │   ├── __init__.py                ✅ 只导出契约类型
│   │   └── telemetry.py               ✅ gen_schemas.py 从 SPEC.md 字段表生成，禁止手改
│   ├── api/__init__.py                ✅ 空壳（只导出契约）
│   ├── service/__init__.py            ✅ 空壳
│   ├── domain/__init__.py             ✅ 空壳
│   └── infra/__init__.py              ✅ 空壳
├── src/web/src/contracts/             ✅ codegen 产物（TS interface）
├── src/firmware/contracts.h           ✅ codegen 产物（C struct）
├── scripts/gen_schemas.py             ✅ schema 生成器
└── tests/contract/test_schemas.py     ✅ 契约测试（<80 行）
```

### 13.1 先写本 Phase 的 spec（以后每个阶段动工前都按这个模板写一份）

```markdown
# Phase 1 spec：骨架与契约
## 1. 技术栈与前置      Python 3.12 / pytest / 已有契约
## 2. 仓库结构           本 Phase 只建 src/energy_system/{api,service,domain,infra,contracts} 空壳 + scripts/gen_schemas.py
## 3. 环境与运行命令     uv sync --all-extras --dev；uv run pytest -q
## 4. 数据模型           events.jsonl 行格式（30 字段白名单，照搬旧仓库，冻结）
## 5. API 契约           TelemetryEvent（字段名以 docs/specs/SPEC.md 为准，禁止发明新字段）
## 6. 纯逻辑             codegen 从 SPEC.md 字段表读，不手写字段
## 7. 验证               见第 9 节验收命令
## 8. 构建/提交工作流    refactor/layered-skeleton 分支，24h 内 squash
## 9. 验收（Definition of Done）
   - [ ] uv run pytest -q 全绿
   - [ ] 契约测试 <80 行（R1 验收：从 422 行降下来）
   - [ ] 改一个字段 → 三份生成物同步变（证明 codegen 真的在跑）
   - [ ] uv run mypy src/ 零错
## 10. Subagents（角色契约，见下）
## 11. 每个功能的双勾选框   [ ] 初始实现（builder）  [ ] 独立验证（verifier）
```

spec 每份末尾固定带 Subagents 段（按 Phase 裁剪）：

```markdown
## Subagents

### builder（副智能体 · provider=deepseek / model=deepseek-flash · 显式钉模型）
- 触发：主智能体在实现阶段 spawn
- 输入：本 spec + 任务卡（Intent/Scope/Boundaries/Evidence/Recovery）
- 纪律：只改 Scope 内文件；先写失败测试再实现；不碰 AGENTS.md
- 输出（report 格式）：changed files 清单；测试/性能命令的原文输出；
  任何偏离 spec 之处及原因；发现的双实现/陷阱（只记录不处理）

### verifier（副智能体 · provider=deepseek / model=deepseek-flash · 独立会话）
- 触发：builder 完成后，主智能体 spawn（**新会话**，防自己审自己）
- 输入：builder 的 diff + spec + docs/specs/SPEC.md
- 检查：① 对照契约卡五字段 ② 口径是否被悄悄改变 ③ 语义幻觉
  （能编译能跑但逻辑错的代码）④ 是否有 Scope 外改动
- 输出：PASS / FAIL + 具体 file:line + 理由。只报告，禁止修改文件。

### reader（副智能体 · provider=deepseek / model=deepseek-flash）
- 触发：需要读旧仓库/大文件时
- 纪律：只读；输出 ≤10 行结论 + 关键 file:line 指针
```

**写作心法**：spec 要完整到「通用副智能体可以直接实现」——所有决策钉死，让便宜副智能体不用提问就能执行。社区验证的模式：**用强模型（Kimi）烧对话和 spec，把机械实现委托给便宜副智能体（Flash）**。

### 13.2 怎么干

1. **发提示词**（第 1 步五段模板的 EXPLORE 阶段）：

   ```
   实现分层骨架（plan mode 先给计划）：energy_system.api → service → domain → infra
   四层空壳，每层 __init__.py 只导出契约类型；另建 contracts 契约包。迁移旧仓库
   energy_system/domain/telemetry.py（159 行，单一真值设计）的 schema 结构为
   Pydantic 契约（字段名以 docs/specs/SPEC.md 为准，禁止发明新字段；旧仓库
   domain/metrics.py 163 行与它单位表重复，冲突处以 SPEC.md 签字口径为准）。
   写 scripts/gen_schemas.py：从 SPEC.md 字段表生成
   Py dataclass / TS interface / 固件 struct 三份（R1）——Py 产物落
   src/energy_system/contracts/，TS 落 src/web/src/contracts/，C 落
   src/firmware/contracts.h。写 tests/contract/test_schemas.py：断言
   events.jsonl 真实样本行能通过契约解析。完成后 builder/verifier 流程走一遍。
   ```

   预期看到：plan mode 的计划（改哪些文件、什么顺序）；你说「继续」后 builder 开工。

2. **代码骨架参照**（智能体按 spec 填充，你派活前就知道要什么）：

   ```python
   # scripts/gen_schemas.py（骨架）
   FIELDS = load_spec_fields("docs/specs/SPEC.md")     # 唯一事实源

   def gen_python() -> str:
       """Pydantic BaseModel：字段名/类型/单位全部来自 SPEC.md。"""
       lines = ["from pydantic import BaseModel", "", "class TelemetryEvent(BaseModel):"]
       for f in FIELDS:
           lines.append(f"    {f.name}: {f.py_type}  # {f.unit}")
       return "\n".join(lines)

   def gen_typescript() -> str: ...      # interface TelemetryEvent { ... }
   def gen_firmware() -> str: ...        # typedef struct { ... } TelemetryEvent;
   ```

   ```python
   # tests/contract/test_schemas.py（从 422 行降到 <80 行的关键：只留手写断言）
   def test_events_v3_sample_parses():
       """旧仓库 events.jsonl 真实样本行能通过契约解析。"""
       for line in SAMPLE_LINES:                       # 样本文件，不是手写 422 行
           ev = TelemetryEvent.parse_raw(line)
           assert ev.elec_kwh >= 0                      # 量纲抽查
   ```

3. **跑验收命令**：

   ```bash
   uv run pytest -q                                   # 全绿
   uv run mypy src/                                   # 零错
   wc -l tests/contract/test_schemas.py               # <80
   ```

   预期看到：三项全过。契约测试行数是 R1 的核心验收（从 422 行降下来）。

4. **证明 codegen 真的在跑**：让 builder 改 SPEC.md 里一个字段名 → 三份生成物（Py/TS/固件）同步变 → 再改回来。预期看到：三份产物都跟着变；只有手工改一份 = codegen 是假的。

5. **提交**：`feat(contract): 分层骨架 + Pydantic 契约 + schema codegen（R1）`，commit message 带契约卡五字段 + 真实 Evidence。

### 13.3 怎么验

```bash
uv run pytest -q && uv run mypy src/ && wc -l tests/contract/test_schemas.py
```

预期：全绿 + 零错 + 契约测试 <80 行。
**错了怎么退**：revert（生成器是新增，不影响旧测试）。

---

## 第 14 步 · 迁移测试基建（不改断言）

**预计时间**：3 天｜**前置**：第 13 步｜**分支**：`chore/test-infra`

**干什么**：365 个测试的**基础设施**（fixtures/工具/conftest）原样搬入，**不改断言**。测试本体暂不搬（等对应模块建好再搬，避免大面积 skip）。

### 14.1 怎么干

1. **发提示词**：

   ```
   迁移旧仓库 tests/ 的基础设施部分到新仓库：
   - conftest.py、fixtures、测试工具函数原样复制
   - 测试本体暂不搬（等对应模块建好再搬，避免大面积 skip）
   起 builder（deepseek-flash，显式指定）复制 + 修 import 路径；
   verifier 审「原样」二字。报告：迁移了哪些文件；
   uv run pytest -q 收集到多少测试（允许部分 skip）。
   ```

   预期看到：builder 回报迁移文件清单；verifier 确认「原样」（断言一字未改，只改 import 路径）。

2. **跑收集数**：

   ```bash
   uv run pytest -q --collect-only | tail -3
   ```

   预期看到：收集数 **≥300**，无失败（允许部分 skip）。

### 14.2 怎么验

收集数 ≥300；无失败；diff 里只有 import 路径变化，没有断言变化。
**错了怎么退**：revert。

---

## 第 15 步 · 建 shadow 双跑框架

**预计时间**：1 天｜**前置**：第 14 步｜**分支**：`chore/shadow`

**干什么**：一个工具函数，喂两组实现 + 输入序列，输出两者最大偏差。**这是后续所有「口径修正」的安全带**（dark launching 的地基）——报告 §12.3 迁移五步的第 3 步「shadow 双跑」靠它落地。

**本步文件**：`src/energy_system/testing/shadow.py` ✅ + `tests/test_shadow.py` ✅

### 15.1 怎么干

1. **发提示词**：

   ```
   新建 src/energy_system/testing/shadow.py：
   def shadow_compare(old_impl, new_impl, inputs) -> max_deviation
   写测试：用两个故意不同的函数验证能测出偏差。
   ```

   预期看到：builder 实现 + 自测绿；verifier 确认「能测出偏差」的测试真的能测出（不是恒真断言）。

2. **迁移五步顺序**（报告 §12.3 原文，后面每个合并都按这个来）：

   ```
   先测（补 hardware/cli 覆盖）
     → 加接口（不改行为）
       → shadow 双跑（新旧比对）
         → 开关切换（保留 1 周）
           → 删除旧实现
   ```

   | 步 | 报告原文 | 本手册落地 | 门禁（不过不进下一步） | 回滚 |
   |---|---|---|---|---|
   | 1 | 先测（补 hardware/cli 覆盖） | 第 17 步：表征测试补到 ≥60% | `uv run pytest -q --cov=energy_system` 对应模块 ≥60% | 无（只加测试） |
   | 2 | 加接口（不改行为） | 8 组双实现全部先建 Protocol 抽象 | CI 绿 + 零行为变更（同种子输出逐位相等） | revert |
   | 3 | shadow 双跑（新旧比对） | 用本步的 shadow 框架：喂同一输入序列，记录最大偏差 | 偏差符合预期（D4 量纲类 <1e-6；控制类逐位相等） | 关 flag |
   | 4 | 开关切换（保留 1 周） | flag 默认开，旧路径仍在 | 一周无回归 + 你批准 | 秒关 flag |
   | 5 | 删除旧实现 | 删适配层 + 删 flag + 删死代码 | `grep` 无残留；vulture/knip 干净；测试数不减 | revert |

   「每步都要有**回滚开关**与**行为对拍**；不建议一次性替换数据层。」

### 15.2 怎么验

单测绿（shadow 能测出故意制造的偏差）。
**错了怎么退**：revert。

---

## 第 16 步 · 记录覆盖率基线

**预计时间**：半天｜**前置**：第 14 步｜**分支**：`docs/coverage-baseline`

**干什么**：把报告盲区写进 `docs/COVERAGE.md` 和 SPEC 附录——下一补（第 17 步）就从这里开始。报告盲区原话：「`cli` 0%、`serial_bridge` 16%、`usecases` 41%、`command_dispatcher` 48%——恰恰是 bug 最多的三个模块。这不是巧合：**没测的地方就是会坏的地方**。」（`hardware` 21.8%。）

**本步文件**：`docs/COVERAGE.md` ✅

### 16.1 怎么干

1. **跑一次覆盖率**，把各模块数字记进 `docs/COVERAGE.md`：

   ```bash
   uv run pytest -q --cov=energy_system --cov-report=term-missing
   ```

   预期看到：term-missing 表；把每个模块的行抄进 COVERAGE.md（**抄真实输出，不许手填**）。

2. **在 SPEC 附录列盲区清单**：五个模块（cli / hardware / serial_bridge / usecases / command_dispatcher）+ 报告实测数字 + 「第 17 步补到 ≥60%」的目标。

### 16.2 怎么验

`docs/COVERAGE.md` 存在且数字来自真实命令输出；SPEC 附录有盲区清单。
**错了怎么退**：改文件（无代码）。

---

## 第 17 步 · 在工作副本补表征测试（先测再改）

**预计时间**：2 天｜**前置**：第 16 步｜**分支**：`test/characterization`（在 EcoSentinel-work 上）

**干什么**：迁移五步第 1 步「先测」。给 `cli` / `hardware` / `serial_bridge` / `usecases` / `command_dispatcher` 五个模块写表征测试——**固化当前行为，包括已知缺陷行为：先钉住，再修**。这是第 19 步性能改造和第 21–23 步缺陷修复的安全网。

**为什么在工作副本做**：表征测试的对象是**旧代码**（新仓库这些模块还没建），而旧仓库已冻结只读。所以第 2 步的裸备份现在派上用场：clone 一个可写的工作副本，在上面只加测试、不改实现。测完随模块迁移进新仓库，工作副本第 41 步删除。

**本步文件**：

```text
~/EcoSentinel-work/                    ✅ clone 自裸备份（可写）
├── energy_system/                     （旧代码，只读使用——只加测试，不改一行实现）
└── tests/characterization/            ✅ 五个模块的表征测试
    ├── test_cli.py
    ├── test_hardware.py
    ├── test_serial_bridge.py
    ├── test_usecases.py
    └── test_command_dispatcher.py
```

### 17.1 怎么干

1. **建工作副本**：

   ```bash
   git clone ~/EcoSentinel-legacy-backup.git ~/EcoSentinel-work
   cd ~/EcoSentinel-work
   git tag legacy-reference            # 对齐冻结点的 tag（备份里有）
   uv sync --all-extras --dev          # 用旧仓库的 pyproject 建环境
   ```

   预期看到：clone 成功；`uv run pytest -q` 在旧代码上全绿（365 个）。

2. **装两个钉模型插件**（第 5 步 5.4 方案 B 的两个纯增益插件，后面开始有多线并行）：

   ```bash
   # 桌面版：插件管理页面 → Add plugin → 输入包名
   # 命令行版：
   npx @deepseek-ai/dsh plugin add dsh-subagent-model-config
   npx @deepseek-ai/dsh plugin add dsh-model-pin
   ```

   装完在 Settings → Plugins 确认已启用；`dsh-subagent-model-config` 的规则页里加一条：builder/verifier/reader → deepseek-flash。

3. **发提示词**（DSH 工作区切到 `~/EcoSentinel-work`）：

   ```
   给这五个模块写表征测试：cli、hardware、serial_bridge、usecases、
   command_dispatcher。要求：
   - 固化当前行为（包括已知缺陷行为——先钉住，再修）
   - 每个模块至少一个「能跑通当前实现」的测试
   - 不修任何缺陷；发现的问题写进 FINDINGS.md，不许动
   - 跑 uv run pytest -q --cov=energy_system 贴输出
   ```

   预期看到：五个测试文件；每个模块至少一个「能跑通当前实现」的测试——**包括已知缺陷行为也要钉住**（例如 dispatcher 的失败缓存行为，此刻测试断言的是「现状」，第 22 步才改成「应该」）。

4. **跑覆盖率**：

   ```bash
   uv run pytest -q --cov=energy_system --cov-report=term-missing
   ```

   预期看到：五个模块各自 **≥60%**（hardware 基线 21.8%，提升最大）；全绿。

5. **记录迁移映射**（写进 `docs/FINDINGS.md` 或工作副本 README，后面各步按这张表迁测试）：

   | 表征测试 | 新仓库模块 | 随哪步迁 |
   |---|---|---|
   | `test_command_dispatcher.py` | `src/energy_system/domain/command_dispatcher.py` | 步 22 |
   | `test_serial_bridge.py` | `src/energy_system/infra/`（串口桥） | 步 30 |
   | `test_hardware.py` | `src/energy_system/infra/`（硬件抽象） | 步 30 |
   | `test_usecases.py` | `src/energy_system/domain/pipeline.py` 等 | 步 29 |
   | `test_cli.py` | `src/energy_system/`（CLI 入口） | 步 29 |

### 17.2 怎么验

```bash
cd ~/EcoSentinel-work
uv run pytest -q --cov=energy_system --cov-report=term-missing
```

预期：五个模块覆盖率 ≥60%；`uv run pytest -q` 全绿；迁移映射表已记录。
**错了怎么退**：revert（只加测试，无风险）。

---

## 第 18 步 · D8：统一数据目录 paths.py

**预计时间**：半天｜**前置**：第 17 步｜**分支**：`fix/d8-paths`｜**契约卡**：新建

**干什么**：修「路径与工作目录」缺陷——`energy_system/core/log_manager.py:21` 用 CWD 相对路径，而 `api_server.py:33`（仓库根入口）、`dashboard/data_client.py:64` 用绝对路径；换目录启动 → 数据写别处、API 读空、前端全 `--` 且不报错。**这是第 19 步性能测试的前置地基：文件路径先可靠，性能测试才测的是真东西。**

**报告原文**（§7 D8）：

| 列 | 内容 |
|---|---|
| 位置 | 旧仓库 `energy_system/core/log_manager.py:21`（CWD 相对） vs `api_server.py:33`（仓库根入口）、`dashboard/data_client.py:64`（绝对） |
| 影响 | 换目录启动 → 数据写别处、API 读空、前端全 `--` 且不报错 |
| 修法 | 全仓唯一数据目录解析处，`DATA_DIR` 只来自配置/环境变量 |

**本步文件**：

```text
ecosentinel-v2/src/energy_system/
├── infra/paths.py            ✅ 全仓唯一数据目录解析处
└── config/settings.py        ✅ 最小版（只有 data_dir；步 28 换完整版）
```

### 18.1 怎么干

1. **代码骨架**（修复后的目标形态；settings.py 此时是最小版，步 28 换 pydantic-settings 完整版）：

   ```python
   # src/energy_system/config/settings.py（最小版，步 18）
   import os
   from pathlib import Path

   data_dir: Path = Path(os.environ.get("ECOSENTINEL_DATA_DIR", "./data"))
   ```

   ```python
   # src/energy_system/infra/paths.py —— 全仓唯一数据目录解析处
   from pathlib import Path
   from energy_system.config import settings

   def data_dir() -> Path:
       """数据目录只来自配置/环境变量，禁止 CWD 相对（报告 §7 D8）。"""
       return settings.data_dir.expanduser().resolve()

   def logs_dir() -> Path:
       return data_dir() / "logs"
   ```

2. **测试骨架**：

   ```python
   def test_data_dir_independent_of_cwd(tmp_path, monkeypatch):
       """固化报告 §7 D8：换目录启动，读写都指向同一处。"""
       monkeypatch.setenv("ECOSENTINEL_DATA_DIR", str(tmp_path))
       monkeypatch.chdir("/")                 # 从根目录启动
       assert logs_dir() == tmp_path / "logs"
       monkeypatch.chdir("/tmp")              # 换个目录再启动
       assert logs_dir() == tmp_path / "logs" # 还是同一处
   ```

3. **派活提示词定制点**：builder 建 paths.py + 测试 + 把仓库里 `Path("logs")` 类裸相对路径调用全换掉；verifier 审「全仓再无裸相对路径拼数据目录」。

### 18.2 怎么验

```bash
uv run pytest -q -k paths
grep -rn 'Path("logs")' src/                   # 期望空
```

预期：测试绿（含从两个不同目录启动的断言）；grep 空。
**错了怎么退**：revert。

---

## 第 19 步 · D5：尾读 DataStore（性能拐点）

**预计时间**：2 天｜**前置**：第 18 步｜**分支**：`refactor/data-tail-read`｜**flag**：`FLAG_DATA_TAIL_READ`｜**契约卡**：C1

**干什么**：修全套改进里影响面最大的一项——JSONL 全量读。报告 §8.2 的拐点判断：**>7 天数据系统不可用**（单轮询 5.7 s > 3 s，前端永久落后，CPU 打满）。而正确实现就在旧仓库另一个目录里——**照搬，禁止重新发明**。

**报告原文**（§7 D5 + §8）：

| 列 | 内容 |
|---|---|
| 位置 | 旧仓库 `energy_system/persistence/jsonl_repository.py:74-99` |
| 实测 | 17k 行 **114 ms**；120k 行 **670 ms**；7 端点/轮询 ≈ **5.7 s/3 s**；尾读对照 **1.1 ms**（**634×** 差距） |
| 容量模型 | 5 s 采样 → 17,280 行/天；单行 ≈350 B → **≈6 MB/天**、**≈2.2 GB/年**、630 万行/年 |
| 修法 | 复用 `dashboard/data_loader.py:10-43` 的尾读 + `(mtime,size)` 缓存；中期 SQLite |
| 验收 | **120k 行 P95 < 50 ms**（报告 §8.4 目标） |

**本步文件**：

```text
ecosentinel-v2/
├── src/energy_system/infra/data_store.py   ✅ JsonlStore（尾读）
└── tests/
    ├── test_data_store.py                   ✅ 尾读正确性
    └── perf/test_data_store_perf.py         ✅ 性能验收（@pytest.mark.perf）
```

### 19.1 怎么干

1. **先跑探针确认现象存在**（第 11 步迁的 `tools/perf.py`，默认打旧仓库）：

   ```bash
   cd ~/ecosentinel-v2
   uv run python tools/perf.py
   ```

   预期看到：670ms vs 1.1ms 对照（与报告附录 A 一致）。**复现不出来先查 TARGET 路径，不许跳过。**

2. **代码骨架**（照搬旧 `dashboard/data_loader.py:10-43` 的逻辑，禁止重新发明）：

   ```python
   class JsonlStore:
       """JSONL 尾读：seek 末 256KB → 逐行解析 → 丢弃不完整尾行。"""

       TAIL_BYTES = 256 * 1024

       def __init__(self):
           self._cache: dict[Path, tuple[tuple[int, int], list[TelemetryEvent]]] = {}

       def read_tail(self, path: Path, n: int) -> list[TelemetryEvent]:
           stat = path.stat()
           key = (stat.st_mtime_ns, stat.st_size)
           cached = self._cache.get(path)
           if cached and cached[0] == key:
               return cached[1][-n:]                      # (mtime,size) 缓存命中
           events = self._read_tail_uncached(path)
           self._cache[path] = (key, events)
           return events[-n:]

       def _read_tail_uncached(self, path: Path) -> list[TelemetryEvent]:
           size = path.stat().st_size
           with path.open("rb") as f:
               f.seek(max(0, size - self.TAIL_BYTES))
               raw = f.read()
           lines = raw.split(b"\n")
           if size > self.TAIL_BYTES:
               lines = lines[1:]                          # 首行可能被截断，丢弃
           if lines and lines[-1] == b"":
               lines = lines[:-1]                          # 丢弃不完整尾行
           return [TelemetryEvent.parse_raw(line) for line in lines if line]
   ```

3. **测试骨架**（两组：正确性 + 性能）：

   ```python
   def test_read_tail_returns_last_n_lines(tmp_path):
       """尾读正确性：120k 行的文件，取最后 120 行。"""
       path = write_jsonl(tmp_path, n_lines=120_000)
       events = JsonlStore().read_tail(path, 120)
       assert len(events) == 120
       assert events[-1].seq == 119_999                  # 最后一行不丢

   def test_read_tail_p95_under_50ms(tmp_path):
       """固化报告 §7 D5 验收：120k 行 P95 < 50ms（对照全量读 670ms）。"""
       path = write_jsonl(tmp_path, n_lines=120_000)
       store = JsonlStore()
       latencies = sorted(timeit_latencies(store.read_tail, path, 120, runs=50))
       p95 = latencies[int(0.95 * len(latencies))]
       assert p95 < 0.050, f"P95={p95*1000:.1f}ms，超过报告 §8.4 的 50ms 线"
   ```

4. **派活提示词**（第 1 步五段模板填实）：

   ```
   【契约卡 C1 — D5 尾读迁移】
   - Intent：消除 JSONL 全量读性能缺陷（120k 行全量 670ms）
   - Scope：仅 src/energy_system/infra/data_store.py（新建）+ tests/test_data_store.py（新建）
   - Boundaries：不改任何调用方；读接口签名冻结；events.jsonl 行格式不变（30 字段白名单）
   - Evidence：uv run pytest -q 全绿；uv run pytest -q -m perf 120k 行 P95 < 50ms
   - Recovery：feature flag FLAG_DATA_TAIL_READ 默认关

   参考（只读，不许改）：
   - 旧仓库 dashboard/data_loader.py:10-43（正确尾读实现，照搬其逻辑）
   - docs/specs/SPEC.md（口径唯一事实源）

   要求：
   1. 先起 reader 副智能体（provider=deepseek、model=deepseek-flash，显式指定）
      读旧仓库 data_loader.py:1-60 和 jsonl_repository.py:74-99，5 行以内回报
   2. 综合后用 5 行复述：尾读算法的关键步骤 + read_all 的问题，停下等我说「继续」
   3. 【我说继续后】起 builder 副智能体（同样显式钉模型，后台运行）：
      a. 先跑 uv run python tools/perf.py 贴输出（确认 670ms 现象存在）
      b. 照搬 data_loader.py:10-43 逻辑实现 JsonlStore.read_tail
      c. 先写 120k 行性能测试（红），再实现（绿）
      d. uv run pytest -q 贴原文输出
   4. builder 完成后起 verifier 副智能体（新会话，显式钉模型）审 diff：
      重点：是否真的尾读、有无 read_all 残留、缓存键是不是 (mtime,size)
   5. 全绿后写 commit：refactor(d5): <摘要> + 契约卡 + 真实 Evidence
   ```

   预期看到：builder 报告「红→绿」的命令原文；verifier PASS。

5. **flag 接线**：`data_store.py` 的读取入口按 `FLAG_DATA_TAIL_READ` 分流（默认关走旧路径）；同步在 `docs/FLAGS.md` 登记（第 9 步已预填，确认默认值与删除条件）。

### 19.2 怎么验

```bash
uv run pytest -q -m perf                      # 120k 行 P95 < 50ms
uv run python tools/perf.py                   # 探针对照：670ms vs 1.1ms
grep -rn "read_all" src/ --include=*.py       # 期望空（pre-commit 也有这道门禁）
```

预期：P95 < 50ms（对照全量 670ms）；grep 空。**P95 在 50ms 边缘抖动 = 机器负载问题，重跑三次取稳。**
**错了怎么退**：`FLAG_DATA_TAIL_READ` 默认关 + revert。

**中期路线（第 20 步的 SQLite 部分）**：报告 §8.5 容量规划——1 节点 ×1 年（630 万行 / 2.2 GB）SQLite 足够（单表 + ts 索引）；10 节点 ×1 年（22 GB）上 TimescaleDB/InfluxDB。

---

## 第 20 步 · R2：SqliteStore（WAL + ts 索引）

**预计时间**：2 天｜**前置**：第 19 步｜**分支**：`refactor/sqlite-store`｜**flag**：`FLAG_SQLITE_STORE`｜**契约卡**：C1（R2 后半）

**干什么**：R2 的后半——按报告 §8.5 落 `SqliteStore`（WAL + ts 索引）。`JsonlStore` 保留为归档/导入导出格式；两个实现走同一 `TelemetryStore` 协议，flag 切换保留一周。

**本步文件**：

```text
ecosentinel-v2/src/energy_system/
├── domain/store.py             ✅ TelemetryStore Protocol（存储接口，冻结）
└── infra/sqlite_store.py      ✅ SqliteStore（WAL + ts 索引）
```

### 20.1 怎么干

1. **代码骨架**：

   ```python
   # src/energy_system/domain/store.py —— 存储接口（domain/telemetry.py 留给步 25 的单位表）
   class TelemetryStore(Protocol):
       def read_tail(self, n: int) -> list[TelemetryEvent]: ...
       def read_range(self, start: datetime, end: datetime) -> list[TelemetryEvent]: ...
   ```

   ```python
   # src/energy_system/infra/sqlite_store.py（骨架）
   class SqliteStore:
       """WAL + ts 索引；1 节点 ×1 年（630 万行/2.2GB）SQLite 足够（报告 §8.5）。"""
       def __init__(self, db_path: Path):
           self._db = sqlite3.connect(db_path)
           self._db.execute("PRAGMA journal_mode=WAL")
           self._db.execute("CREATE TABLE IF NOT EXISTS telemetry(ts REAL PRIMARY KEY, payload BLOB)")
           self._db.execute("CREATE INDEX IF NOT EXISTS idx_ts ON telemetry(ts)")
   ```

2. **派活提示词要点**：接口 `QueryService ── TelemetryStore(Protocol)`，两个实现 `SqliteStore`（WAL + ts 索引）/ `JsonlStore`（归档/导入导出）；**尾读逻辑照搬第 19 步的实现**（同一份，禁止第二套）；双实现必须对拍一致。

3. **副智能体分工**：builder 建 Protocol + SqliteStore；verifier 审「接口冻结、两实现对拍一致」。

### 20.2 怎么验

同数据双实现对拍一致（shadow 框架，第 15 步）；`uv run pytest -q -m perf`：120k 行查询 P95 < 50 ms。
**错了怎么退**：`FLAG_SQLITE_STORE` 关。

### 20.3 Phase 2 出口门禁（第 4 周结束，不过不进第 5 周）

> 完整出口门禁见第 23 步末（D1/D2/D3 修完才算 Phase 2 结束）。到本步为止必须已达成：
>
> - [ ] 尾读性能达标：120k 行 **P95 < 50 ms**（`uv run pytest -q -m perf`）
> - [ ] `uv run pytest -q` 全绿
> - [ ] `uv.lock` 未动（本 Phase 不加新依赖，sqlite 是内置模块）

---

## 第 21 步 · D1：阻断计数读错实例（正确性四连修之一）

**预计时间**：1 天｜**前置**：第 20 步（顺序）；第 17 步（表征测试已钉住当前行为）；第 11 步（探针已迁移）｜**分支**：`fix/d1-blocked-count`｜**flag**：`FLAG_SIM_FIX`｜**契约卡**：C5-1

**干什么**：修「对外数字不真实」的第一例——仿真里 `saving_short_cycle_blocks` 报告 0，实际运行的控制器计数 **134**。README 用「0 次」论证「节能策略几乎不动作」，论证链断裂（结论方向可能仍成立，但证据是假的）。**论文里出现这种数字，是不可承受的。**

**先说通用打法**（D1/D2/D3 三个正确性缺陷共用，本步起连续三天都按这个来）：

三个缺陷都是「对外数字/口径不真实」，修法都是「**先写失败测试复现报告证据链 → 再修 → 测试转绿**」。**每个缺陷独立分支、独立 commit、独立 revert**（回滚粒度）。下面的通用模板第 22、23 步原样复用，只换契约卡内容。

### 21.0 通用提示词模板（D1/D2/D3 共用，发给主智能体，进入 plan mode）

```
进入 plan mode。任务卡如下：

【契约卡 C5-<n> — D<?> <缺陷名>】
- Intent：<报告 §7 D<?> 的现象，一句话>
- Scope：仅 src/energy_system/domain/<对应模块>.py + tests/test_<模块>.py（新建）
- Boundaries：
  · 先写失败测试，复现审阅报告 §7 D<?> 的实测证据链（<具体数字>）
  · KPI 口径不动；不顺手修其他缺陷（发现的问题写进 FINDINGS.md）
- Evidence：复现测试红→绿；uv run pytest -q 全绿
- Recovery：独立分支 fix/d<?>，revert 即回

参考（只读，不许改）：
- 旧仓库 <file:line>（报告 §7 D<?> 指定位置）
- 旧仓库探针脚本 tools/<对应探针>.py（已迁到新仓库 tools/）
- docs/specs/SPEC.md（口径唯一事实源）

要求：
1. 先起 reader 副智能体（provider=deepseek、model=deepseek-flash，显式指定）
   读旧仓库 <file:line>，5 行以内回报：这段代码在做什么、为什么错
2. 你综合后用 5 行复述「旧代码为什么错」，停下等我说「继续」
3. 【我说继续后】起 builder 副智能体（同样显式钉模型，后台运行）：
   a. 先把探针脚本在新仓库跑一遍贴输出（探针第 11 步已迁，默认打旧仓库）
   b. 写失败测试：固化报告实测证据（<数字>）
   c. 按报告修法修：<报告修法原文>
   d. uv run pytest -q 贴原文输出
4. builder 完成后起 verifier 副智能体（新会话，显式钉模型）审 diff：
   重点：修的是「读错/算错」，不是「把数字改好看」；有无 Scope 外改动
5. 全绿后写 commit：fix(d<?>): <摘要> + 契约卡 + 真实 Evidence
```

### 21.1 报告原文（§7 D1）

| 列 | 内容 |
|---|---|
| 位置 | 旧仓库 `energy_system/simulation/simulator.py:29-35`、`energy_system/simulation/compare.py:145` |
| 现象 | `saving_short_cycle_blocks` 报告 0，实际运行的控制器计数 **134** |
| 实测 | `Simulator(mode="saving")` → `sim.controller.short_cycle_blocks=0`，`sim._controllers["saving"].short_cycle_blocks=134`，两者 `is` 为 False |
| 影响 | README 用「0 次」论证「节能策略几乎不动作」——论证链断裂 |
| 修法 | `_controllers` 与 `self.controller` 指向同一实例；或 `compare` 读实际运行实例 |
| 验收 | 单测断言 `saving_short_cycle_blocks == 134`（seed 42） |

**本步文件**：

```text
ecosentinel-v2/
├── src/energy_system/simulation/        ← 一级包（与 domain 平级；domain 不许依赖它）
│   ├── simulator.py              ✅ D1 修复：self.controller 与 _controllers[mode] 同一实例
│   └── compare.py                ✅ 从旧仓库 energy_system/simulation/compare.py:145 迁移（读实际运行实例）
└── tests/
    └── test_simulator.py         ✅ 复现测试（红→绿证据链）
```

### 21.2 怎么干

1. **建分支**（主智能体或你自己）：

   ```bash
   cd ~/ecosentinel-v2
   git checkout -b fix/d1-blocked-count
   ```

2. **先跑探针确认现象存在**（第 11 步迁的 `tools/dyn1.py`，PROBE_TARGET 默认指旧仓库，此刻旧仓库缺陷还在，理应复现）：

   ```bash
   uv run python tools/dyn1.py
   ```

   预期看到：输出含「0 vs 134」——`sim.controller.short_cycle_blocks=0` 而 `sim._controllers["saving"].short_cycle_blocks=134`，两者 `is` 为 False。**贴这段输出，它是修复前的证据。**

3. **派 reader 副智能体读旧代码**（显式钉 `provider=deepseek、model=deepseek-flash`）：

   ```
   读旧仓库 ~/EcoSentinel/energy_system/simulation/simulator.py:25-40 和
   energy_system/simulation/compare.py:140-150，
   5 行以内回报：simulator 里 _controllers 和 self.controller 分别是什么，
   为什么读到的计数是 0 而实际运行的是 134。
   ```

   预期看到：reader 指出「`self.controller` 指向另一个（没跑过的）Controller 实例」。

4. **主智能体 5 行复述，你说「继续」**，然后派 builder 副智能体（后台运行）：

   ```
   【契约卡 C5-1 — D1 阻断计数读错实例】
   - Intent：修复 saving_short_cycle_blocks 报告 0、实际 134 的读错实例缺陷
   - Scope：仅 src/energy_system/simulation/simulator.py +
     src/energy_system/simulation/compare.py（从旧仓库迁移）+
     tests/test_simulator.py（新建）
   - Boundaries：先写失败测试复现「0 vs 134」；seed 42 冻结；
     README 的对外数字等验收通过后由主智能体统一改，你不许改 README
   - Evidence：单测断言 saving_short_cycle_blocks == 134（seed 42）通过；
     uv run pytest -q 全绿
   - Recovery：独立分支 fix/d1，revert 即回

   参考（只读）：旧仓库 energy_system/simulation/simulator.py:29-35、
   energy_system/simulation/compare.py:145；docs/specs/SPEC.md

   纪律：修的是「读错实例」，不是「把 134 改成 0 让测试过」——
   对外数字必须来自真实运行。先复述「为什么 _controllers["saving"]
   和 self.controller 是两个实例」再动手。
   ```

5. **builder 交付后派 verifier 副智能体**（新会话，显式钉模型）审 diff，重点：有没有为了好看而改数字、有无 Scope 外改动。

6. **全绿后提交**（commit message 带契约卡五字段 + 真实 Evidence 原文），同步更新 `docs/FLAGS.md`（`FLAG_SIM_FIX` 引入步已是 21，确认登记行存在）。

### 21.3 代码骨架（修复后的目标形态）

```python
# src/energy_system/simulation/simulator.py
class Simulator:
    """楼宇热仿真：跑控制循环，产出对外论据。"""

    def __init__(self, mode: str = "saving", seed: int = 42, ...):
        self._controllers: dict[str, Controller] = {
            "saving": Controller(profile="saving", ...),
            "comfort": Controller(profile="comfort", ...),
        }
        # ★D1 修复：self.controller 必须与 _controllers[mode] 是同一个实例。
        # 旧代码在这里 new 了一个新 Controller（或指向了默认实例），
        # 导致 sim.controller 读到的永远是没跑过的对象的计数。
        self.controller = self._controllers[mode]

    def run(self, steps: int) -> None:
        for _ in range(steps):
            self.controller.step(...)   # 只有这一个实例在跑
```

```python
# tests/test_simulator.py —— 红→绿的证据链
def test_saving_short_cycle_blocks_matches_report():
    """固化报告 §7 D1 实测：seed 42 下阻断计数必须是 134，不是 0。"""
    sim = Simulator(mode="saving", seed=42)
    sim.run(steps=...)                       # 步数按旧仓库 compare 的等价配置
    # 第一层断言：读错实例的根因——两个引用必须是同一个对象
    assert sim.controller is sim._controllers["saving"]
    # 第二层断言：报告实测数字（seed 42）
    assert sim.controller.short_cycle_blocks == 134
```

> `compare.py` 从旧仓库迁移时：**只迁逻辑，顺带修掉「读错实例」的调用**（报告修法：或 `compare` 读实际运行实例）。迁移后 `uv run python -m energy_system.simulation.compare` 必须输出真实计数。

### 21.4 怎么验

```bash
uv run pytest -q -k short_cycle                       # 绿；断言值是 134（seed 42）
uv run python -m energy_system.simulation.compare    # 输出与报告修正值一致
PROBE_TARGET=src uv run python tools/dyn1.py          # 新仓库验证：两个数一致，不再 0 vs 134
```

预期看到：三条命令全过；探针打新仓库时两个引用同一实例、计数一致（都是 134）。
**不过怎么办**：若 `pytest -k short_cycle` 红——看断言值是不是 134（seed 42 冻结，换 seed 数字会变，不许换）；若探针打新仓库仍报 0 vs 134——检查 `PROBE_TARGET=src` 是否指到了包含 `energy_system` 包的目录。
**错了怎么退**：`FLAG_SIM_FIX` 关 + revert（独立分支，回滚不影响其他步）。

---

## 第 22 步 · D2：下发失败被当成功缓存（正确性四连修之二）

**预计时间**：1 天｜**前置**：第 21 步｜**分支**：`fix/d2-send-cache`｜**flag**：`FLAG_SEND_RESULT`｜**契约卡**：C5-2

**干什么**：修 `send_command` 返回 `{"ok": false}` 时仍写 `_last_relay1/2` 的缺陷——**设备可能整天不动**（缓存认为已开，不再重发）。这是三个正确性缺陷里唯一影响物理设备的，最危险。模板用第 21.0 节的通用模板，只换契约卡内容。

### 22.1 报告原文（§7 D2）

| 列 | 内容 |
|---|---|
| 位置 | 旧仓库 `energy_system/core/command_dispatcher.py:133-141`、`energy_system/hardware/serial_bridge.py:324-356` |
| 现象 | `send_command` 返回 `{"ok": false}` 时仍写 `_last_relay1/2` |
| 实测 | 假串口连发两次 `apply()`，第 2 次 **0 条命令**（缓存认为已开） |
| 修法 | `res = send_command(...); if res.get("ok"): 更新缓存 else: 置 None + 退避重试`；每轮用固件回传的 `relays` 对账 |
| 验收 | 连续 3 轮假串口场景，每轮都重发 |

**本步文件**：

```text
ecosentinel-v2/
├── src/energy_system/domain/
│   └── command_dispatcher.py      ✅ D2 修复：缓存只认成功 + 指数退避 + 固件对账
└── tests/
    └── test_command_dispatcher.py  ✅ 两组测试 + 第 17 步表征测试迁移进来
```

> **表征测试迁移（第 17 步映射表）**：第 17 步在 `~/EcoSentinel-work` 上写的 `test_command_dispatcher.py` 随本步迁进新仓库。迁移规矩：**复制文件 + 只改 import 行**（旧平铺布局 → `from energy_system.domain.command_dispatcher import ...`），**断言一字不改**。其中钉住「失败也写缓存」旧行为的断言，在本步修复后改为钉住修复后行为——**改动处必须写注释**：`# 报告 §7 D2：旧行为是缺陷，此处由表征断言改为正确性断言`。这就是第 17 步「已知缺陷行为也钉住」的兑现时刻。

### 22.2 怎么干

1. **建分支 + 跑探针确认现象**：

   ```bash
   cd ~/ecosentinel-v2
   git checkout -b fix/d2-send-cache
   uv run python tools/dyn3.py        # 默认打旧仓库
   ```

   预期看到：输出含「失败被当成功缓存」现象（连发两次 `apply()`，第 2 次 0 条命令）。贴出来。

2. **派 reader 读旧代码**（显式钉模型）：

   ```
   读旧仓库 ~/EcoSentinel/energy_system/core/command_dispatcher.py:130-145 和
   energy_system/hardware/serial_bridge.py:305-315，5 行以内回报：apply() 里缓存是什么时候写的、
   为什么 send_command 失败了还写。
   ```

3. **主智能体复述后你说「继续」**，派 builder（后台运行）——契约卡 C5-2 定制点：

   - Intent 换成「设备可能整天不动」；
   - Scope 为 `src/energy_system/domain/command_dispatcher.py` + 假串口 fixture + 表征测试迁移；
   - Evidence 写「连续 3 轮假串口场景，每轮都重发（复现报告 §7 D2 实测）」；
   - 修法原文照抄 22.1 表；
   - **特别提醒**：这个缺陷的影响是「设备可能整天不动」——退避重试必须真的实现，不是只把缓存删掉了事。

4. **verifier 专项**：审「退避逻辑与对账」——`_reconcile_with_firmware` 在不在、指数退避是不是真的。

5. **提交**：带契约卡五字段 + 真实 Evidence；确认 `docs/FLAGS.md` 里 `FLAG_SEND_RESULT` 行存在。

### 22.3 代码骨架（修复后的目标形态）

```python
@dataclass(frozen=True)
class SendResult:
    ok: bool
    acked_relays: tuple[int, ...] | None = None   # 固件回传的真实继电器状态

class CommandDispatcher:
    """AI/规则命令 → 校验 → 执行 → 缓存。缓存只认成功。"""

    def __init__(self, transport: Transport, clock: Clock, ...):
        self._transport = transport
        self._clock = clock
        self._last_relay1: int | None = None
        self._last_relay2: int | None = None
        self._retry_at: float | None = None
        self._backoff_s: float = 1.0

    def apply(self, plan: ControlPlan) -> None:
        if self._retry_at is not None and self._clock.now() < self._retry_at:
            return                                  # 退避窗口内不重发
        res = self._transport.send_command(plan.command)
        if res.ok:
            self._last_relay1 = plan.relay1          # 成功才缓存
            self._last_relay2 = plan.relay2
            self._retry_at = None
            self._backoff_s = 1.0
        else:
            self._last_relay1 = None                 # 失败置空，下轮必然重发
            self._last_relay2 = None
            self._retry_at = self._clock.now() + self._backoff_s
            self._backoff_s = min(self._backoff_s * 2, 30.0)   # 指数退避
        self._reconcile_with_firmware(res.acked_relays)         # 每轮对账

    def _reconcile_with_firmware(self, acked: tuple[int, ...] | None) -> None:
        if acked is None:
            return
        self._last_relay1 = acked[0] if len(acked) > 0 else None
        self._last_relay2 = acked[1] if len(acked) > 1 else None
```

```python
# tests/test_command_dispatcher.py —— 两组：失败重发 + 成功缓存对照
def test_failed_send_is_not_cached_and_retried(fake_transport):
    """固化报告 §7 D2 实测：失败不下发缓存，连续 3 轮每轮都重发。"""
    fake_transport.fail_next_sends = 999        # 让前两次下发失败
    d = CommandDispatcher(transport=fake_transport, clock=FakeClock(...))
    for round_no in range(3):
        fake_transport.sent.clear()
        d.apply(plan_with_relay1_on())
        assert fake_transport.sent, f"第 {round_no} 轮没有重发（缓存把失败当成功了）"

def test_success_updates_cache_and_skips_duplicate(fake_transport):
    """对照断言：成功才缓存，避免重复下发。"""
    ...
```

### 22.4 怎么验

```bash
uv run pytest -q -k dispatcher                       # 绿（含迁移来的表征测试）
uv run python tools/dyn3.py                          # 修后再贴一次：失败缓存项不再复现
```

预期看到：`test_failed_send_is_not_cached_and_retried` 绿（连续 3 轮每轮都重发）；dyn3 输出里「失败被当成功缓存」项消失。
**不过怎么办**：若第 2 轮没有重发——检查 `apply()` 是不是在退避窗口内直接 return 了（`fail_next_sends=999` 时退避会阻止重发，测试里 FakeClock 要能跨过退避窗口，或断言前手动推进时钟）；若表征测试迁移后红——先看是不是 import 行没改对，再确认断言里钉旧行为的部分已按 22.1 的注释规矩改过。
**错了怎么退**：`FLAG_SEND_RESULT` 关 + revert。

---

## 第 23 步 · D3：跨午夜电量重复累计（正确性四连修之三）

**预计时间**：1 天｜**前置**：第 22 步｜**分支**：`fix/d3-midnight-energy`｜**flag**：`FLAG_DAY_ROLLOVER`｜**契约卡**：C5-3

**干什么**：修跨午夜电量重复累计——6/1 写 100 Wh，跨天后 6/2 文件仍写 **100 Wh**（当天真实 0）。所有「当日能耗」类数字都不可信。模板同样用第 21.0 节通用模板。

### 23.1 报告原文（§7 D3）

| 列 | 内容 |
|---|---|
| 位置 | 旧仓库 `energy_system/core/log_manager.py:89-114` |
| 实测 | 6/1 写 100 Wh；跨天后 6/2 文件写 **100 Wh**（当天真实 0） |
| 修法 | 日期切换时记 `day_start_total`，写 `base + (current_total − day_start_total)` |
| 验收 | 伪造日期单测，6/2 = 0 |

**本步文件**：

```text
ecosentinel-v2/
├── src/energy_system/domain/
│   └── energy_ledger.py           ✅ D3 修复：日期切换重置当日起点
└── tests/
    └── test_energy_ledger.py      ✅ FakeClock 跨午夜测试
```

### 23.2 怎么干

1. **建分支 + 跑探针确认现象**：

   ```bash
   cd ~/ecosentinel-v2
   git checkout -b fix/d3-midnight-energy
   uv run python tools/dyn3.py        # 默认打旧仓库
   ```

   预期看到：输出含跨日电量重复累计项（6/2 文件写 100 Wh，当天真实 0）。贴出来。

2. **派 builder**（reader 步可省——旧代码位置明确；契约卡 C5-3 定制点）：

   - Evidence 写「伪造日期单测：6/2 当日增量 = 0」；
   - 必须用 FakeClock 注入日期（AGENTS.md 时钟注入规则，第 9 步已立）；
   - Scope 含日汇总部分；
   - 修完再跑一次 `uv run python tools/dyn3.py` 贴输出，确认跨日项消失。

3. **verifier 专项**：审「`day_start_total` 在日期切换时更新，而不是每小时更新」。

4. **提交**：带契约卡五字段；确认 `docs/FLAGS.md` 里 `FLAG_DAY_ROLLOVER` 行存在。

### 23.3 代码骨架（修复后的目标形态）

```python
# src/energy_system/domain/energy_ledger.py
class EnergyLedger:
    """当日电量 = 历史基数 + (当前累计 − 当日起点累计)。"""

    def __init__(self, clock: Clock, store: LedgerStore):
        self._clock = clock
        self._store = store
        self._day: date | None = None
        self._day_start_total_wh: float = 0.0

    def today_wh(self, cumulative_total_wh: float) -> float:
        today = self._clock.now().date()
        if today != self._day:                       # 日期切换：重置当日起点
            self._day = today
            self._day_start_total_wh = cumulative_total_wh
        base_wh = self._store.read_base(today)       # 历史累计（跨日前已落盘）
        return base_wh + (cumulative_total_wh - self._day_start_total_wh)
```

```python
# tests/test_energy_ledger.py
def test_midnight_rollover_does_not_double_count():
    """固化报告 §7 D3 实测：6/1 写 100 Wh，6/2 当天真实 0，必须是 0。"""
    clock = FakeClock(start="2026-06-01 23:59:00")
    ledger = EnergyLedger(clock=clock, store=FakeLedgerStore())
    ledger.today_wh(cumulative_total_wh=100.0)       # 6/1：当天 100 Wh
    clock.advance_to("2026-06-02 00:01:00")          # 跨午夜
    assert ledger.today_wh(cumulative_total_wh=100.0) == 0.0   # 6/2：0
```

### 23.4 怎么验

```bash
uv run pytest -q -k ledger                           # 绿；6/2 = 0
uv run python tools/dyn3.py                          # 跨日项不再复现
```

预期看到：测试绿（含「23:59→00:01 切换」用例）；dyn3 输出里跨日电量项消失。
**不过怎么办**：若 6/2 仍非 0——检查 `day_start_total_wh` 是不是在 `today != self._day` 时才更新（写进 if 里，不是每小时更新）；若 FakeClock 推进后日期没变——检查 FakeClock 的 `advance_to` 实现。
**错了怎么退**：`FLAG_DAY_ROLLOVER` 关 + revert。

### 23.5 Phase 2 出口门禁（第 4 周结束，不过不进第 5 周）

- [ ] 尾读性能达标：120k 行 **P95 < 50 ms**（`uv run pytest -q -m perf`，第 19 步的线）
- [ ] 三个缺陷（D1/D2/D3）各有复现测试且探针现象消失（dyn1/dyn3 输出贴案）
- [ ] `uv run pytest -q` 全绿
- [ ] `uv.lock` 未动（本 Phase 不加新依赖，sqlite 是内置模块）

> 第 20.3 节的「到本步为止必须已达成」四项是它的子集；本门禁才是 Phase 2 的完整出口。

---

## 第 24 步 · 控制层合并（Phase 3 开场：双实现合并主战场）

**预计时间**：4 天｜**前置**：第 23 步｜**分支**：`refactor/control-merge-{a,b,c,d}`（四小步各一个分支，24h 内 squash）｜**flag**：`FLAG_CONTROL_MERGED`｜**契约卡**：C3

**干什么**：消除控制层双实现——生产路径 `energy_system/core/command_policy.py`（139 行，四段校验 + 通道保留）+ `energy_system/core/command_dispatcher.py`（146 行，AI 命令兼容校验 + 规则执行器）vs `energy_system/core/control/*`（206 行：`ControlPlan/Compiler/ActuationService/Transport`，**生产未接线**）。这是 Phase 3（第 5–6 周）的第一个合并，也是全套 8 个接缝合并的**完整示范**——第 25/26/27/29 步都是这个打法。

**本步裁决（SEAMS.md#control，第 10 步已签字）**：**以生产路径的行为为准**（policy 的四段校验 + dispatcher 的执行语义，缺陷已在第 22 步修）；`core/control/*` 只取它的抽象形态（ControlPlan/Compiler/Transport 分层），**不取它的 compiler 行为**——compiler 直发 `RELAY 1/2` 与 policy 的通道保留规则冲突（报告 §6.1 原文），接入前必须对齐。

**本 Phase 通用打法**（branch-by-abstraction 四小步）：

```
a. 建抽象：只建接口，无实现。CI 绿即合并。
b. 旧实现适配：把 SEAMS.md 裁决「以 X 为准」的正确实现适配到接口，
   行为逐位不变。verifier 审「行为不变」。
c. 新唯一实现 behind flag：全仓只走协议实现（旧的另一份撤走）。
   默认 flag 关→行为不变；开→走新路径。shadow 双跑一周。
d. 切 flag 为默认开 → 删适配层和 flag（你批准后）。
```

**本步文件**：

```text
ecosentinel-v2/
├── src/energy_system/domain/
│   ├── command_dispatcher.py      ← 第 22 步已建（D2 修复版，执行器）
│   └── control/
│       ├── protocol.py            ✅ 步 24a：控制协议抽象（只建接口，形态取自 core/control/*）
│       ├── control_law.py         ✅ 步 24b：迁 core/controller.py 控制律（分时设定点/死区/最短运行）
│       └── command_policy.py      ✅ 步 24b：迁 core/command_policy.py 四段校验 + 通道保留
└── tests/
    └── test_control_protocol.py   ✅ 同种子 1000 步逐位相等断言
```

### 24.1 怎么干（提示词，以 24b 为例，a/c/d 同理裁剪）

```
步 24b：把 SEAMS.md#control 裁决的正确实现适配到 domain/control/protocol.py。
迁移源（只读）：energy_system/core/command_policy.py（139 行，四段校验 + 通道
保留）+ energy_system/core/command_dispatcher.py（146 行，执行语义）+
energy_system/core/controller.py（217 行，控制律）。硬性要求：同随机种子
1000 步输出逐位相等。RELAY 1/2 通道保留规则以 command_policy 为准——
core/control/compiler 直发 RELAY 1/2 与保留规则冲突，禁止照搬其行为。
verifier 用另一会话独立审这个逐位相等声明。
```

四小步各自的落地要点：

| 小步 | 干什么 | 合并条件 |
|---|---|---|
| a | 建 `domain/control/protocol.py` 抽象接口，无实现 | CI 绿即合 main（零行为变更） |
| b | 把 SEAMS.md#control 裁决的正确实现（policy 四段校验 + dispatcher 执行语义 + controller 控制律）适配到接口 | 同种子 1000 步输出逐位相等，verifier 独立审 |
| c | 新唯一实现 behind flag，shadow 双跑一周 | 一周偏差为 0 |
| d | flag 默认开 → 删适配层和 flag | 测试数不减，**你批准** |

**副智能体分工**：builder 建抽象 + 适配；verifier 专项审「行为逐位不变」的声明（用另一会话独立验证，防止自己审自己）。

### 24.2 怎么验

- 24a：接口文件存在且无实现，CI 绿（零行为变更的直接证据）；
- 24b：同种子逐位相等（测试断言，不是口头声明）；
- 24c：shadow 双跑一周偏差为 0（shadow 框架第 15 步已建，`shadow_compare(旧实现, 新实现, 同输入序列)`）；
- 24d：删 flag 后测试数不减。

**错了怎么退**：任一步 revert；3.1c 还可秒关 `FLAG_CONTROL_MERGED`。

---

## 第 25 步 · 指标/KPI 层合并

**预计时间**：3 天｜**前置**：第 24 步｜**分支**：`refactor/kpi-merge`｜**flag**：`FLAG_KPI_MERGED`｜**契约卡**：C3 模式

**干什么**：按第 24 步的 a/b/c/d 四小步，对象换成**指标/KPI 双实现**——旧仓库 `energy_system/domain/telemetry.py`（159 行，单一真值 + `set_metric` 抛错，**设计意图最好**，但写入链路没用它）vs `energy_system/domain/metrics.py`（163 行，与 telemetry **单位表重复**；`MetricSnapshot` 仅测试用）；KPI 计算又四散在 `energy_system/algorithms/` 下（`comfort_kpi.py` 109 行 / `peak_kpi.py` 83 行 / `energy_saving.py` 46 行）。合并为 `domain/kpi.py` 唯一实现（报告 §12.1 领域层目标：kpi（band/peak/energy））。KPI 口径以 SPEC.md 为唯一事实源（第 8 步已签字），本步只合并实现、不动口径。

**本步裁决（SEAMS.md#metrics，第 10 步已签字）**：**单位表以 `domain/telemetry.py` 为准**（单一真值设计）；**带外积分以 `algorithms/comfort_kpi.py` 为准**（报告判词「实现正确，仅仿真用」→ 提为唯一实现）；`domain/metrics.py` 与 telemetry 重复的单位表删除。两个文件级缺陷在合并分支按报告建议顺手修（各先写失败测试固化）：`peak_kpi.py` 不足 15 min 的尾窗也计入 max（`300` 硬编码）；`energy_saving.py` 的 `calc_EER` 放行负值（碳因子两处取）。`comfort_eval.py` 的两套口径**不归本步**——那是第 26 步的对象。

**本步文件**：

```text
ecosentinel-v2/
├── src/energy_system/domain/
│   ├── telemetry.py                ✅ 单位表唯一真值（迁 domain/telemetry.py 设计）
│   └── kpi.py                      ✅ band/peak/energy 唯一实现（合并双实现 + 两处缺陷修复）
└── tests/
    └── test_kpi_merge.py           ✅ 同种子 shadow 对拍断言 + 尾窗/EER 两个失败测试
```

### 25.1 怎么干（提示词要点）

```
按 24 步的 a/b/c/d 四小步执行，对象是指标/KPI 双实现。迁移源（只读）：
energy_system/domain/telemetry.py（159 行，单位表以此为准）、
energy_system/domain/metrics.py（163 行，单位表与 telemetry 重复，删）、
energy_system/algorithms/comfort_kpi.py（109 行，积分实现以此为准）、
energy_system/algorithms/peak_kpi.py（83 行）、energy_system/algorithms/energy_saving.py（46 行）。
验收同种子数值一致（shadow 最大偏差 < 1e-9）。peak_kpi 尾窗缺陷与 energy_saving
EER 负值缺陷：各先写失败测试固化报告实测，再修，测试转绿。
comfort_eval.py 的两套口径不许在本步动（第 26 步的对象）。
```

**副智能体分工**：builder 建指标抽象 + 适配 + flag 切换；verifier 审「KPI 口径一个字没动，动的只有实现」。

### 25.2 怎么验

shadow 双跑一周，同种子数值一致（最大偏差 < 1e-9）；删 flag 后测试数不减。
**错了怎么退**：`FLAG_KPI_MERGED` 秒关 + revert。

> ⚠️ 本步最大的风险是「合并实现时顺手改口径」——verifier 的唯一职责就是盯这个。口径要动，回第 8 步改 SPEC.md 走签字流程，不许在合并分支里偷渡。

---

## 第 26 步 · D4：舒适度量纲统一 + Dark Launch

**预计时间**：3 天｜**前置**：第 25 步｜**分支**：`fix/d4-comfort-scale`｜**flag**：`FLAG_COMFORT_NORM`｜**契约卡**：C2

**干什么**：修舒适度两套量纲——同一份数据，`/snapshot` 返回 0.5，`/chart` 返回 50.0（旧仓库 `energy_system/api/services.py:76` 原样 0–1 vs `:102` ×100）。SPEC.md 已裁决**统一 [0,1]**（第 8 步 + 契约卡 C2），本步执行该裁决。

### 26.1 报告原文（§7 D4）

| 列 | 内容 |
|---|---|
| 位置 | 旧仓库 `energy_system/api/services.py:76`（原样 0–1） vs `:102`（×100） |
| 实测 | 同一份数据，`/snapshot` 返回 0.5，`/chart` 返回 50.0 |
| 修法 | 统一 0–1，前端格式化；或统一 0–100 并全局一致 |
| 验收 | 契约测试断言两端口径一致 |

**本步文件**：

```text
ecosentinel-v2/
├── src/energy_system/domain/
│   └── comfort.py                ✅ 全仓唯一量纲实现（[0,1]）
├── src/web/src/lib/
│   └── format.ts                 ✅ 展示层唯一允许的 ×100（display-only）
└── tests/
    └── test_comfort.py           ✅ 量纲断言 + 两端口径一致契约测试
```

### 26.2 代码骨架

```python
# src/energy_system/domain/comfort.py —— 全仓唯一量纲实现
def comfort_score(**inputs) -> float:
    """返回归一化舒适度 ∈ [0,1]。API 层原样序列化；
    展示层的 ×100 只发生在前端 format 函数里（display-only）。"""
    ...
```

```typescript
// src/web/src/lib/format.ts —— 展示层唯一允许的 ×100
export function comfortPercent(score01: number): string {
  return `${(score01 * 100).toFixed(1)}%`;   // 仅用于显示，不回写 API
}
```

```python
# tests/test_comfort.py —— 正确性 + 契约两组
def test_comfort_is_normalized_unit_interval():
    """固化报告 §7 D4：所有输入下输出 ∈ [0,1]。"""
    for case in COMFORT_CASES:
        assert 0.0 <= comfort_score(**case) <= 1.0

def test_snapshot_and_chart_use_same_scale(client):
    """契约测试：两个端点的同一字段口径一致（报告验收）。"""
    snap = client.get("/api/v1/snapshot").json()
    chart = client.get("/api/v1/chart?range=24h").json()
    assert snap["comfort"] == chart["comfort"]       # 同一份数据同一个数
```

### 26.3 怎么干（Dark Launch 三小步）

本步不是一次性切换，分三小步走（与第 24 步 branch-by-abstraction 的 c/d 同构——shadow 双跑 + 你批准才删旧的）：

```
步 26a 唯一实现 [0,1]；契约测试断言 API 输出 ∈ [0,1]（先红后绿）
步 26b FLAG_COMFORT_NORM 后 shadow 双跑：新旧实现在同一输入序列下
        跑两周，记录偏差（预期：除已知修正点外 < 1e-6）
步 26c 两周数据给你看 → 你批准 → 默认开 → 删旧量纲代码和 flag
```

**副智能体分工**：builder 写 comfort.py + 契约测试 + shadow 对比脚本；verifier 审「×100 只出现在前端 format 函数，grep 全仓验证」。

### 26.4 怎么验

```bash
uv run pytest -q -k comfort                       # 两端口径一致绿
grep -rn "\* *100" src/energy_system/ --include=*.py   # 期望空（后端不许有 ×100）
```

预期看到：测试绿；后端 grep 空（×100 只许在前端 `format.ts`）。
**不过怎么办**：若 `/chart` 仍返回 50.0——检查序列化层是不是还带着 ×100（API 层只许原样序列化）；若 grep 命中——把那处 ×100 挪进前端 format 函数，不许在后端留。
**错了怎么退**：`FLAG_COMFORT_NORM` 关（回旧量纲）。

---

## 第 27 步 · R4：AI 双实现合并（门面 + 唯一熔断）

**预计时间**：3 天｜**前置**：第 26 步｜**分支**：`refactor/ai-merge`｜**flag**：`FLAG_AI_SIM`｜**契约卡**：C4

**干什么**：消除 AI 双实现——`energy_system/algorithms/ai_advisor.py`（323 行，**生产在用但「半提取」**：自带统计与内联熔断副本）vs `energy_system/ai/` 包（`circuit_breaker.py` 83 行干净可注入但**只被测试引用** / `service.py` 88 行半成品门面 / `models.py` 56 行 `HALF_OPEN` 死枚举 / `provider.py` 19 行 Protocol 定义良好但 advisor 不用）。收敛为 `domain/ai/` **唯一门面 + 唯一熔断**（报告 R4 原话：「AI 双实现合并（门面 + 唯一熔断）」，验收「现有测试不改断言通过」）。核心哲学：**契约是资产，实现是脚手架**——LLM 是租来的，熔断状态机契约不换。

**本步文件**：

```text
ecosentinel-v2/
├── src/energy_system/domain/
│   └── ai/
│       ├── facade.py             ✅ AiFacade 唯一门面（迁 ai_advisor.py 323 行生产逻辑）
│       ├── circuit_breaker.py    ✅ 唯一熔断（以 ai/circuit_breaker.py 83 行为准，合并 advisor 内联副本）
│       ├── prompt_builder.py     ✅ 白名单提示词（迁 ai/prompt_builder.py 63 行，修 frozenset 顺序）
│       └── provider.py           ✅ AiProvider Protocol（迁 ai/provider.py 19 行，advisor 从此走它）
└── tests/
    └── test_ai_facade.py         ✅ 旧仓库 AI 层测试全量迁移（不改断言）
```

### 27.1 实现指引

- **熔断以 `energy_system/ai/circuit_breaker.py`（83 行）为准**——报告 §6.3 判词「干净、可注入时钟」；advisor 的内联副本（与它逐项同值）**删除**，生产只走唯一熔断；
- **门面迁 `algorithms/ai_advisor.py` 的生产逻辑**（323 行），三个缺陷各先写失败测试固化报告实测、再修：① 分数在调用前算、成功后归给候选（**归因错**）；② `client_unavailable` 计为失败（无 key 两轮清池）→ 无 key 是**配置错误**，显式报 `NO_LLM`；③ 惩罚 `0.15f+0.8cf` 与 EMA 不同量纲（一次失败≈扣 80%）；
- `prompt_builder.py` 的白名单机制（16 字段，密钥/路径/堆栈永不外发）是**全仓最佳实践，原样保留**；但 `frozenset` 迭代顺序随哈希变（实测三次三序）→ 提示词不可复现，改有序结构（`tuple`/`sorted`）；
- `ai/models.py` 的 `HALF_OPEN` 死枚举与 `resilience/models.py` 的 `HALF_OPEN` 从未赋值——熔断唯一化后统一到一份枚举；
- 旧测试里钉住上述缺陷行为的断言：按第 17 步规矩改后**必须写注释**（`# 报告 §6.4：旧行为是缺陷，此处由表征断言改为正确性断言`）。

代码骨架：

```python
# src/energy_system/domain/ai/facade.py（骨架）
class AiFacade:
    """唯一门面 + 唯一熔断（报告 §6.3/R4）。"""

    def __init__(self, provider: AiProvider, breaker: CircuitBreaker, clock: Clock):
        self._provider = provider
        self._breaker = breaker
        self._clock = clock

    def advise(self, snapshot: TelemetryEvent) -> Advice:
        if not self._breaker.allow():                 # 唯一熔断入口
            raise CircuitOpenError("AI 熔断中")        # fail-loud，不静默返回假建议
        try:
            prompt = build_prompt(snapshot)           # 白名单提示词（有序，可复现）
            advice = self._provider.advise(prompt)
        except NoApiKeyError:
            raise NoLLMConfiguredError("未配置 API key——显式报错，不静默、不返回假建议")
        except Exception as exc:
            self._breaker.record_failure(self._clock.now())
            raise AiUnavailableError(str(exc)) from exc    # 不吞异常
        self._breaker.record_success()
        return advice
```

### 27.2 怎么干（提示词要点）

- 契约保留 + 测试全量迁移**不改断言**（R4 验收原文）；
- 内联熔断副本删除且不可达**有测试证明**；
- 无 key 显式 `NO_LLM`，不返回 plausible 假结果；
- 熔断唯一化（删 advisor 内联副本）；
- 归因错误 / 无 key 清池 / 惩罚量纲三个缺陷：先失败测试固化，再修。

**副智能体分工**：builder 迁契约测试 + 建门面 + 唯一熔断；verifier 审「测试断言一字未改（除注释规矩那几处）、内联副本不可达、无静默 catch」。

### 27.3 怎么验

旧仓库 AI 层测试迁移后**不改断言**全绿；内联熔断副本不可达有测试证明；`grep -rn "circuit_breaker" src/energy_system/` 只有 `domain/ai/circuit_breaker.py` 一个实现。
**错了怎么退**：`FLAG_AI_SIM` 关（provider 抽象允许无 key 环境显式报错回退——但必须是显式 `NO_LLM`，不静默）。

---

## 第 28 步 · R5：配置 pydantic-settings 化

**预计时间**：2 天｜**前置**：第 27 步｜**分支**：`refactor/config-settings`｜**flag**：`FLAG_CONFIG_V2`｜**契约卡**：新建

**干什么**：把旧仓库 `energy_system/config/config_loader.py`（366 行，其中 `load_app_config` 155 行手写解析）换成 pydantic-settings——报告 §5.11 迁移收益原话：「字段缺省/越界有明确报错；自动生成配置文档；`params.yaml` 与 dataclass 不再双份维护」。同目录的 `settings.py`（148 行，第二真值源：`TIME_STEP=300` 与边缘 5 s 并列）与 `runtime_config.py`（88 行，默认值与 YAML 双份）一并收敛进唯一 `Settings`。

**本步文件**：

```text
ecosentinel-v2/
├── config/
│   └── params.yaml              ✅ 配置文件（缺文件/坏 YAML → 启动即报错）
├── src/energy_system/config/
│   └── settings.py              ✏️ 第 18 步最小版 → 本步换 pydantic-settings 完整版
└── tests/
    └── test_settings.py         ✅ 坏配置 fail-loud 三类测试
```

### 28.1 代码骨架

```python
# src/energy_system/config/settings.py（完整版，替换第 18 步最小版）
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ECOSENTINEL_", yaml_file="config/params.yaml")
    bind_host: str = "127.0.0.1"          # 报告 §9 P0
    data_dir: Path                        # 必填，无默认——缺了就报错，不猜
    use_hardware: bool
    deepseek_api_key: str | None = None
    api_base: str | None = None

    @model_validator(mode="after")
    def key_matches_base(self):           # 报告 §9 P0：Key 与 api_base 绑定校验
        if self.deepseek_api_key and self.api_base and "deepseek" not in self.api_base:
            raise ValueError("DeepSeek key 与 api_base 不匹配，错配 fail-fast")
        return self

settings = Settings()                      # 坏配置在这里就炸，不会静默跑下去
```

### 28.2 怎么干（提示词要点）

- 报告迁移收益原话（§5.11）；
- 默认路径禁止相对 CWD（接第 18 步 D8 的 `paths.py`——`data_dir` 经 `paths.data_dir()` 解析）；
- **缺文件/坏 YAML 必须报错退出，禁止静默用默认**（报告 §6.10 实测的坑：缺文件只告警 → 静默用 `use_hardware=False` 继续跑——这类「静默降级」是本步要根除的反模式）；
- `key_matches_base` validator 的 fail-fast 必须有测试（DeepSeek key 发往 `api.openai.com` 必须启动即报错）。

**副智能体分工**：builder 建 Settings + 删 config_loader 手写解析；verifier 审「坏配置启动测试必须抛异常」。

### 28.3 怎么验

```bash
wc -l src/energy_system/config/settings.py        # 期望 < 100（原 297 行手写解析）
uv run pytest -q -k settings                      # 三类 fail-loud 全绿
```

预期看到：行数 < 100；三类测试（缺文件、坏 YAML、Key 与 api_base 不匹配）都抛异常。
**不过怎么办**：若某类坏配置没炸——检查是不是还有 `try/except` 在吞异常（静默降级反模式复发）；若 `key_matches_base` 没触发——确认 validator 是 `mode="after"` 且字段名与 env 前缀对得上。
**错了怎么退**：revert。

---

## 第 29 步 · R3：决策管线接口化（4 个 Protocol）

**预计时间**：2 天｜**前置**：第 28 步｜**分支**：`refactor/decision-pipeline`｜**flag**：`FLAG_PIPELINE`｜**契约卡**：新建

**干什么**：把决策管线接口化——`DecisionPipeline: Propose → Validate → Apply → Audit` + `RuntimeState` + Clock 注入 + `ResilienceFSM`。验收标志：旧仓库 `energy_system/application/usecases.py`（148 行，全函数 `(app)` 无类型；`_last_*` 四处散写；AI 串口写无兜底 `:125`）那种 `usecases(app)` 调用消失，连带 `runtime.py`（63 行）的 16 个透传属性收进 `RuntimeState` dataclass。**顺手把 `energy_system/core/audit_events.py`（51 行，全仓零引用、0% 覆盖）接线**——报告 §6.1 的原话：「接线或删文档」（`docs/command-safety.md` 声称「每个决策都记」，代码却没记）。

> **ResilienceFSM 的移植规矩（同第 17 步）**：先钉住旧行为——包括两个已知缺陷的现象：「假 OPEN」（`energy_system/resilience/orchestrator.py:188` 规划即置 OPEN、执行失败不回滚）和「无真半开」（`resilience/models.py` 与 `ai/models.py` 的 `HALF_OPEN` 从未赋值）。第 30 步修这两个缺陷，届时按规矩改断言 + 写注释。

**本步文件**：

```text
ecosentinel-v2/
├── src/energy_system/domain/
│   ├── pipeline.py               ✅ 4 Protocol + DecisionPipeline
│   ├── runtime_state.py          ✅ RuntimeState dataclass（替 16 个透传属性）
│   └── resilience.py             ✅ ResilienceFSM（先忠实移植，缺陷第 30 步修）
└── tests/
    ├── test_pipeline.py          ✅ 接口测试 + 审计事件覆盖
    └── test_resilience.py        ✅ 表征测试：钉住旧行为（含假 OPEN/无真半开现象）
```

> **表征测试迁移（第 17 步映射表）**：`test_usecases.py`、`test_cli.py` 随本步迁进新仓库（规矩同第 22 步：复制 + 只改 import 行，断言一字不改）。usecases 的表征测试钉的是「`(app)` 透传」的旧行为——迁移后它们证明新管线行为不变；cli 的测试证明入口不变。resilience 的旧测试（`tests/` 下对应文件）随本步迁入 `test_resilience.py`，**假 OPEN/无真半开的旧行为断言原样保留**——第 30 步修缺陷时才动它们。

### 29.1 代码骨架

```python
# src/energy_system/domain/pipeline.py（骨架）
class Proposer(Protocol):
    def propose(self, state: RuntimeState) -> ControlPlan: ...
class Validator(Protocol):
    def validate(self, plan: ControlPlan) -> ValidationResult: ...
class Actuator(Protocol):
    def apply(self, plan: ControlPlan) -> SendResult: ...
class Auditor(Protocol):
    def record(self, event: AuditEvent) -> None: ...   # audit_events 接线处

class DecisionPipeline:
    def __init__(self, proposer, validator, actuator, auditor, clock: Clock):
        ...
    def run_once(self, state: RuntimeState) -> None:
        plan = self.proposer.propose(state)
        result = self.validator.validate(plan)
        if not result.ok:
            self.auditor.record(AuditEvent.rejected(plan, result.reason)); return
        send = self.actuator.apply(plan)
        self.auditor.record(AuditEvent.applied(plan, send.ok))   # 谁在何时下了什么命令
```

### 29.2 怎么干（提示词要点）

目标架构 + RuntimeState + Clock 注入 + ResilienceFSM；audit 接线（`audit_events.py` 从零引用变为有覆盖）。

**副智能体分工**：builder 建 4 个 Protocol + Pipeline + RuntimeState dataclass；verifier 审「循环体整体 try/except + 连续失败计数 + 退避」（报告 §6.2 对旧仓库 `loop.py` 的判词）。

### 29.3 怎么验

```bash
grep -rn "usecases(app)" src/                        # 期望空
uv run pytest -q -k pipeline                         # 绿（含迁移来的表征测试）
```

预期看到：grep 空；审计事件有测试覆盖（「谁在何时下了什么命令」可查）。
**不过怎么办**：若 grep 还有命中——那处透传没改完，回到 builder；若审计事件没覆盖——检查 `Auditor` 是不是注入了真实现而不是 None。
**错了怎么退**：revert（接口化本身不改行为）。

---

## 第 30 步 · 硬件抽象 + 韧性状态机 fail-loud 化

**预计时间**：2 天｜**前置**：第 29 步｜**分支**：`refactor/hardware-abstraction`｜**flag**：无（接口 + 缺陷修复，无行为切换）｜**契约卡**：新建

**干什么**：两件事——① 建 `HardwareAbstraction` 接口 + 假实现（供测试注入，硬件链路从此可离线测；基线覆盖率：`energy_system/hardware` 21.8%、`serial_bridge` 16%，报告 §6.15 盲区原话「没测的地方就是会坏的地方」）；② **韧性状态机 fail-loud 化**——修第 29 步钉住的两个缺陷（报告 §4.4 状态机表 + §6.5 判词）：

| 缺陷 | 报告判词（原文） | 修法 |
|---|---|---|
| **假 OPEN** | `energy_system/resilience/orchestrator.py`（223 行）：「**规划即置 OPEN、执行失败不回滚 → 假 OPEN**」；`_last_i2c_attempt_ts` 只在 executed 时写 → `use_hardware=False` 永不升级到 RESET；`why_not` 丢原因 | 执行成功才置 OPEN，失败回滚；时间戳在规划时就写；`why_not` 保留原因 |
| **无真半开** | `resilience/models.py`（60 行）与 `ai/models.py`（56 行）的 `HALF_OPEN` **从未赋值** → 无真半开（报告 §4.4：AI 熔断连续失败 ≥2，20 s×2^k ≤600 s） | `HALF_OPEN` 真的被赋值；熔断唯一化后统一到一份枚举（第 27 步已合） |

**本步文件**：

```text
ecosentinel-v2/
├── src/energy_system/
│   ├── infra/
│   │   └── hardware.py            ✅ HardwareAbstraction 接口 + 假实现（可注入）
│   └── domain/
│       ├── resilience.py          ✏️ 第 29 步的 FSM → 本步修「假 OPEN」（执行成功才置 OPEN）
│       └── ai/
│           └── circuit_breaker.py ✏️ 第 27 步唯一熔断 → 本步「HALF_OPEN 真赋值」
└── tests/
    ├── test_hardware.py           ✅ 假实现链路测试 + SecurityError 传播测试
    └── test_resilience.py         ✏️ 第 29 步钉旧行为的断言 → 本步改钉修复后行为（写注释）
```

> **表征测试迁移（第 17 步映射表）**：`test_serial_bridge.py`、`test_hardware.py`（工作副本里的两份）随本步迁进新仓库，与新建的假实现测试合并且**不改断言**。

### 30.1 怎么干（提示词）

```
新建 HardwareAbstraction 接口 + 假实现（供测试注入，硬件链路离线可测）。
硬件路径测试补齐到 ≥60%（基线：hardware 21.8%、serial_bridge 16%）。
韧性状态机 fail-loud 化（报告 §6.5 对 energy_system/resilience/orchestrator.py
的判词）：「规划即置 OPEN、执行失败不回滚 → 假 OPEN」——修为执行成功才置
OPEN、失败回滚；_last_i2c_attempt_ts 规划时就写（use_hardware=False 也要能
升级到 RESET）；why_not 保留原因。HALF_OPEN 从未赋值 → 真赋值（§4.4）。
第 29 步 test_resilience.py 里钉住旧行为的断言，按第 17 步规矩改钉修复后
行为，改动处写注释。
```

**副智能体分工**：builder 建接口 + 假实现 + 补硬件链路测试 + 修 FSM；verifier 审「假 OPEN 修复有失败测试固化过的证据链、SecurityError 传播路径上没有任何 catch」。

### 30.2 怎么验

```bash
uv run pytest -q -k "hardware or resilience"          # 绿（含假 OPEN 修复测试）
uv run pytest -q --cov=energy_system --cov-report=term-missing   # 硬件链路 ≥60%
uv run mypy src/                                    # 零错
```

预期看到：三条全过；覆盖率报告里硬件相关模块 ≥60%；`use_hardware=False` 的场景下 FSM 能升级到 RESET（旧行为是永不升级）。
**不过怎么办**：若假 OPEN 还在——检查置 OPEN 的调用点是不是在「执行成功」之后（不是规划时）；若 `use_hardware=False` 仍不升级——检查 `_last_i2c_attempt_ts` 是不是还只在 executed 分支写；若覆盖率不够——用假实现补链路测试（离线可跑，不等硬件）。
**错了怎么退**：revert（FSM 修复有第 29 步的表征测试兜底，回滚后旧行为断言仍在）。

### 30.3 Phase 3 出口门禁（第 5–6 周结束，不过不进第 7 周）

- [ ] 双实现 **8→3**（剩看板/前端/JSONL 解析；JSONL 若已在第 19/20 步统一则 8→2）
- [ ] `uv run mypy src/` 零错
- [ ] 覆盖率 ≥75% 且硬件链路 ≥60%
- [ ] 每个合并过的接缝都有 shadow 双跑记录贴案

---

## 第 31 步 · D9：安全四件套（P0，Phase 4 开场）

**预计时间**：2 天｜**前置**：第 30 步｜**分支**：`fix/d9-security`｜**flag**：`FLAG_AUTH`｜**契约卡**：C7

**干什么**：一次清掉三个安全缺陷——label 路径穿越（`label=../../../../Windows/win` 解析到 logs 之外仍返回 200）、API 无鉴权、默认绑 `0.0.0.0`。加上第 28 步已落地的 Key 与 `api_base` 绑定校验（本步只确认它有测试在 CI 里），报告 §9.5 的两行 P0 就清完了（MQTT 默认关属固件侧，第 38 步 D10 执行）。**30 天窗口内必须完成**（现在排在第 7 周，是因为要等 API 层建好；如果你每天 6 小时以上，按报告原周次提前执行）。

### 31.1 报告原文（§7 D9）

| 列 | 内容 |
|---|---|
| 位置 | 旧仓库 `energy_system/persistence/jsonl_repository.py:39-41,106`（label 直拼路径）；`api_server.py:60-68`（仓库根入口：无鉴权 + 默认 `0.0.0.0`） |
| 实测 | `label=../../../../Windows/win` → 解析到 logs 之外，仍返回 200 |
| 修法 | `re.fullmatch(r"[A-Za-z0-9_-]{1,32}", label)` + `resolve()` 校验 + 默认回环 + 可选 API Key |

**报告 §9 安全优先级清单**（本步要全清前两项 P0，P1 按 flag 分阶段开）：

| 优先级 | 动作 |
|---|---|
| P0 | 默认绑 `127.0.0.1`；`label` 白名单；MQTT 默认关 |
| P0 | Key 与 `api_base` 绑定校验，错配 fail-fast |
| P1 | API Key / OAuth2 + 限流（slowapi） |
| P1 | MQTT TLS + 用户名密码 + 主题 ACL |
| P1 | 启用 `audit_events`，记录「谁在何时下了什么命令」（第 29 步已接线） |

> **Key 与 `api_base` 绑定校验在第 28 步已落地**（`settings.key_matches_base`，DeepSeek key 发往 `api.openai.com` 启动即报错）。本步确认它有测试在 CI 里，不用重做。

**本步文件**：

```text
ecosentinel-v2/
├── src/energy_system/
│   ├── infra/
│   │   └── log_paths.py          ✅ label 白名单校验 + resolve 双保险
│   └── api/
│       └── server.py             ✅ 默认回环 + 鉴权中间件（flag 分阶段开）
└── tests/
    └── test_security.py          ✅ 5 类穿越 payload + 绑定断言
```

### 31.2 代码骨架（校验 + 绑定）

```python
# src/energy_system/infra/log_paths.py
import re
from pathlib import Path
from energy_system.infra.paths import logs_dir

_LABEL_RE = re.compile(r"[A-Za-z0-9_-]{1,32}")

class InvalidLabelError(ValueError): ...
class PathTraversalError(ValueError): ...

def resolve_log_path(label: str) -> Path:
    """label → 日志路径。白名单 + resolve 双保险（报告 §7 D9）。"""
    if not _LABEL_RE.fullmatch(label):
        raise InvalidLabelError(f"非法 label: {label!r}")
    base = logs_dir().resolve()
    p = (base / label).resolve()
    if base not in p.parents:                 # 双保险：即使白名单被绕过也拒
        raise PathTraversalError(f"路径穿越: {label!r}")
    return p
```

```python
# src/energy_system/api/server.py —— 默认回环（报告 §9 P0）
def create_app() -> FastAPI:
    app = FastAPI(...)
    app.add_middleware(ApiKeyMiddleware, enabled=settings.api_key_required)  # P1，flag 分阶段开
    return app

if __name__ == "__main__":
    uvicorn.run(app, host=settings.bind_host)   # 默认 127.0.0.1，配置可覆盖
```

测试骨架（5 类穿越 payload + 绑定断言）：

```python
@pytest.mark.parametrize("bad", [
    "../../../../Windows/win", "..\\..\\win", "%2e%2e%2f", "", "a" * 33,
    "has space", "semi;colon", "slash/in-label",
])
def test_traversal_payloads_rejected(bad):
    """固化报告 §7 D9 实测：穿越 payload 全部被拒。"""
    with pytest.raises((InvalidLabelError, PathTraversalError)):
        resolve_log_path(bad)

def test_default_bind_is_loopback():
    assert settings.bind_host == "127.0.0.1"
```

### 31.3 怎么干（任务卡全文 + 定制点）

```
（契约卡 C7 照发，另加：）
安全三件套一个分支落地：① label 白名单校验（_LABEL_RE 正则 +
resolve 双保险）；② 鉴权中间件（flag 分阶段开：先 warn 后 enforce）；
③ 默认绑 127.0.0.1。
穿越 payload 必须有测试：../、..\、%2e、空 label、超长 label。
Key 与 api_base 绑定校验第 28 步已落地——本步只确认测试在 CI 里。
```

**副智能体分工**：builder 写校验 + payload 测试 + 绑定测试；verifier 审「resolve 双保险在不在、fail-fast 是不是真抛异常」。

### 31.4 怎么验

```bash
uv run pytest -q -k security                       # 绿
uv run python tools/api_probe.py                   # 打默认启动的服务：无鉴权时按配置行为
```

预期看到：5 类穿越 payload 测试全部被拒（贴输出）；启动默认 `127.0.0.1`；鉴权 enforce 后第 33 步的契约测试仍 7/7。
**不过怎么办**：若某类 payload 没被拒——检查是不是只有白名单没有 resolve 双保险（双保险是报告修法的一部分）；若鉴权开了之后契约测试红——那是预期的，先补 401 负例再开 enforce（先 warn 后 enforce）。
**错了怎么退**：`FLAG_AUTH` 降级为 warn；revert（各自独立分支）。

> ⚠️ 预警：「校验正则抄对——报告原文是 `[A-Za-z0-9_-]{1,32}`，大小写不改」。改成小写会拒掉合法设备名。

---

## 第 32 步 · D6 + D7：清除假状态（纯删除性变更）

**预计时间**：1 天｜**前置**：第 31 步｜**分支**：`fix/d6d7-fake-state`｜**契约卡**：C6

**干什么**：两张卡一起清——D6（API 语义伪造：无串口时 `serial_connected=true`、`retry_count=0`、`risk="低"`、`days=7`）+ D7（前端「假在线」：页面初始即 `latestSnapshot` 非空 → 在线徽标恒亮；残留 29.9% 节能率与虚构硬件「风扇」「AUTO_COOLING」）。**本步是纯删除性变更**——删假播种、删假字段、删虚构文案，revert 即恢复。

### 32.1 报告原文

**D6**（§7）：

| 列 | 内容 |
|---|---|
| 位置 | 旧仓库 `energy_system/api/services.py:157,159,168,170` |
| 实测 | 无串口时 `serial_connected=true`、`retry_count=0`、`risk="低"`、`days=7` |
| 修法 | 接真实来源（`SerialBridge.get_health()`、韧性计数器、`settings.PARAMETER_SETS`）；**无来源返回 `null`** |

**D7**（§7）：

| 列 | 内容 |
|---|---|
| 位置 | 旧仓库 `app/src/store/useAppStore.ts:94-100`（初始播种 mock）、`app/src/components/layout/TopBar.tsx:30`、`app/src/services/api.ts:206` |
| 实测 | 页面初始即 `latestSnapshot` 非空 → 在线徽标恒亮 |
| 修法 | 初始不播种；加 `dataSource: 'live' \| 'demo'`；删除 29.9% 与虚构硬件 |

**本步文件**：

```text
ecosentinel-v2/
├── src/energy_system/api/
│   └── services.py              ✏️ HealthService：无来源返回 null（删四个假字段）
├── src/web/src/
│   ├── store/useAppStore.ts     ✏️ 初始不播种任何 mock；加 dataSource
│   └── components/layout/TopBar.tsx  ✏️ 徽标只看 dataSource（与旧仓库同布局）
└── tests/
    └── test_api_semantics.py    ✅ 无串口时四字段为 null
```

代码骨架（API 侧「无来源返回 null」）：

```python
class HealthService:
    """健康状态只来自真实来源；没有来源就返回 None，不编。"""

    def __init__(self, serial: SerialBridge, resilience: ResilienceFSM, settings: Settings):
        self._serial = serial
        self._resilience = resilience
        self._settings = settings

    def serial_connected(self) -> bool | None:
        health = self._serial.get_health()          # 真实来源
        return None if health is None else health.connected

    def retry_count(self) -> int | None:
        return self._resilience.retry_count         # 韧性计数器，不是常量 0

    def risk_level(self) -> str | None:
        return self._resilience.current_risk()      # 没有评估结果就不给"低"

    def available_days(self) -> int | None:
        return self._settings.PARAMETER_SETS and len(self._settings.PARAMETER_SETS)
```

前端侧（本步先立规矩，新前端第 35 步从零写时执行）：

```typescript
// src/web/src/store/useAppStore.ts —— 初始不播种任何 mock
interface AppState {
  latestSnapshot: Snapshot | null;      // 初始 null，不是 mock 数据
  dataSource: 'live' | 'demo';          // 在线徽标只信这个
}

// src/web/src/components/layout/TopBar.tsx —— 徽标只看 dataSource
export function OnlineBadge({ dataSource }: { dataSource: 'live' | 'demo' }) {
  return <Badge variant={dataSource === 'live' ? 'ok' : 'muted'}>
    {dataSource === 'live' ? '在线' : '演示数据'}
  </Badge>;
}
```

机械门禁（进 pre-commit 或 CI，本步就装上）：

```bash
# 假字段/虚构硬件一个都不许进新前端
grep -rn "29\.9\|AUTO_COOLING\|风扇" src/web/ && exit 1 || true
```

### 32.2 怎么干（提示词要点）

- 核心纪律：「**无来源返回 null，禁止返回看起来合理的假值**」——与 AGENTS.md「禁止编造 plausible 数字」同源；
- 删假 online（前端三处）、API 四个假字段（`serial_connected`/`retry_count`/`risk`/`days`）、残留节能率文案；
- API 测试断言无来源字段为 null；
- verifier 专项跑上面的 grep。

**副智能体分工**：builder 删假播种 + 加 dataSource + 更新徽标 + 接真实来源；verifier 审 grep 干净 + 离线时徽标正确显示「演示数据」+ 「每个字段都能追到一个真实来源，追不到的返回 None」。

### 32.3 怎么验

```bash
uv run pytest -q -k api_semantics                # 无串口时四字段为 null，不是假值
uv run python tools/api_probe.py                 # 输出无假字段
grep -rn "29\.9\|AUTO_COOLING\|风扇" src/web/    # 期望空
```

预期看到：三条全过。
**不过怎么办**：若 grep 命中——那处假文案没删干净（把 mock 数据藏到 env 开关后面不算修，初始状态必须诚实）；若 API 仍返回假值——查是不是还有常量没换成真实来源。
**错了怎么退**：revert（纯删除性变更，恢复即还原）。

---

## 第 33 步 · 7/7 端点契约基线

**预计时间**：1 天｜**前置**：第 32 步｜**分支**：`test/contract-baseline`

**干什么**：旧仓库 API 工厂（`energy_system/api/app.py`）共 8 个端点，前端轮询其中 7 个——把**这 7 个端点**的契约测试搬过来当基线（报告实测 7/7 200）。每个端点至少一个 200 用例 + 一个负例（401/400/404）。这是「新旧并行」在 API 层的锚点——以后任何 API 改动，先过这 7 个端点。同时把报告附录 A 的 stack_acceptance 脚本落到 `scripts/`（旧仓库 `tools/` 里有就迁，没有就写一个：起服务 + 顺序打 7 个端点 + 汇总 PASS/FAIL）。

**本步文件**：

```text
ecosentinel-v2/
├── tests/contract/
│   └── test_api_contract.py  ✅ 7 端点基线（每端点 200 + 负例）
└── scripts/
    └── stack_acceptance.py   ✅ 全栈验收脚本（第 43 步终局验收用）
```

### 33.1 怎么干（提示词）

```
旧仓库 energy_system/api/app.py 工厂共 8 端点，前端轮询 7 个——把
7 个端点的契约测试搬过来当基线（报告实测 7/7 200）。
每个端点至少一个 200 用例 + 一个负例（401/400/404）。
负例必须真的触发对应状态码，不是摆设。
贴 uv run pytest tests/contract -q 输出。
```

**副智能体分工**：builder 搬契约测试 + 写 stack_acceptance；verifier 审「负例真的能触发 401/400/404，不是摆设」。

### 33.2 怎么验

```bash
uv run pytest tests/contract -q                  # 期望 7/7 绿
uv run python scripts/stack_acceptance.py        # 期望 PASS 7/7（127.0.0.1）
```

预期看到：两条全过。
**不过怎么办**：若某端点 200 用例红——先查是不是第 31/32 步的改动影响了它（安全/假状态清理是常见的连带原因），修连带不改基线；若负例没触发状态码——检查测试是不是只断言了「不 500」。
**错了怎么退**：revert。

---

## 第 34 步 · pip-audit + gitleaks 进 CI

**预计时间**：半天｜**前置**：第 33 步｜**分支**：`ci/security-gates`

**干什么**：补上报告 §10.2 指出的 CI 缺口——依赖漏洞扫描（pip-audit）和密钥扫描（gitleaks）。CI 五岗变七岗。

**本步文件**：

```text
ecosentinel-v2/.github/workflows/
└── ci.yml                   ✏️ 加两岗：pip-audit + gitleaks
```

### 34.1 怎么干（提示词）

```
CI 加两岗：uvx pip-audit（依赖漏洞，报告 §10.2 缺口）和
gitleaks（密钥扫描）。先在本地跑一遍贴输出，再接 CI。
```

### 34.2 怎么验

```bash
uvx pip-audit                 # 本地干净
gitleaks detect --no-git      # 本地干净（或按 gitleaks 版本用 detect 的等价命令）
```

预期看到：本地两条干净；CI 两岗绿。
**不过怎么办**：若 pip-audit 报漏洞——升级该依赖（`uv add <包>@<新版>`，lock 会跟着变，这是 uv.lock 的合法改动）；若 gitleaks 命中——那是真密钥泄露，先轮换密钥再清历史。
**错了怎么退**：revert。

### 34.3 Phase 4 出口门禁（第 7 周结束）

- [ ] P0 安全项全清（报告 §9 两条 P0：默认回环 + label 白名单；Key 绑定 fail-fast）
- [ ] 契约测试 **7/7** 绿
- [ ] 依赖干净（pip-audit）+ 无密钥泄露（gitleaks）
- [ ] 假状态字段全部为 null 或已删

---

## 第 35 步 · R6：React + TS 新前端（从零写，只接真实字段）

**预计时间**：4 天｜**前置**：第 34 步｜**分支**：`feat/react-frontend`｜**flag**：`FLAG_WEB_REACT`｜**契约卡**：C8

**干什么**：从零写 React + TS 新前端（目录 `src/web`），迁移 56 个旧测试（**不改断言**），一次性对治报告 §8.3 的前端「五宗罪」。**禁止把任何假字段搬进新前端**（第 32 步的门禁继续有效）。

### 35.1 五宗罪对治表（报告 §8.3）

| 报告问题 | 证据 | 对治 |
|---|---|---|
| 单 chunk 892 kB | 构建输出 | 路由 lazy（`React.lazy` + `Suspense`） |
| `DashboardPage`（517 行）0 个 `useMemo` | 每 3 s 全量重算派生数组 | 派生数组 `useMemo`，依赖写全 |
| 全 store 订阅 | 各页面 `useAppStore()` 无 selector | selector 订阅（`useAppStore(s => s.latest)`） |
| 图表动画 | `SensorChart` 未关入场动画 | 关掉入场动画（每次轮询重播） |
| 无代码分割 | `App.tsx` 静态 import 6 页面 | 按路由分割 |

**本步文件**：

```text
ecosentinel-v2/src/web/src/
├── hooks/
│   └── useTelemetryQuery.ts ✅ 统一轮询 + dataSource（同时治 D7 假在线）
├── store/
│   └── useAppStore.ts       ✅ 初始不播种 mock（第 32 步规矩在这里落地）
├── components/
│   └── TopBar.tsx           ✅ 徽标只信 dataSource
├── lib/
│   └── format.ts            ✅ 全前端唯一允许的 ×100（第 26 步）
└── contracts/               ✅ 第 13 步 codegen 的 TS interface
```

统一轮询 hook（同时治 D7 假在线）：

```typescript
// src/web/src/hooks/useTelemetryQuery.ts（骨架：轮询 + 缓存 + dataSource）
export function useTelemetryQuery(endpoint: string, intervalMs = 3000) {
  const [data, setData] = useState<Snapshot | null>(null);     // 初始 null（D7）
  const [dataSource, setDataSource] = useState<'live' | 'demo'>('demo');
  useEffect(() => {
    const timer = setInterval(async () => {
      const r = await fetch(endpoint);
      setData(await r.json()); setDataSource('live');          // 拿到真实数据才亮「在线」
    }, intervalMs);
    return () => clearInterval(timer);
  }, [endpoint, intervalMs]);
  return { data, dataSource };
}
```

### 35.2 怎么干（提示词）

```
从零写 React+TS 新前端（目录 src/web），只接真实字段。
迁移 56 个旧测试（不改断言）。禁止把任何假字段搬进新前端。
报告 §8.3 五宗罪对治：路由 lazy / useMemo / selector /
关图表动画 / 代码分割。旧 Streamlit 看板保留至 flag 切换后一周（铁律 2）。
```

mock 隔离纪律：mock 只在 `__mocks__`，生产 bundle 不含。

**副智能体分工**：builder 写组件；verifier 跑假字段 grep 专项 + 迁移测试不改断言的声明审查。

### 35.3 怎么验

```bash
cd src/web && npm ci && npm test                 # 56 个旧测试全绿
grep -rn "29\.9\|AUTO_COOLING\|风扇" src/web/    # 期望空
npm run knip                                     # 无新死代码
```

预期看到：三条全过。
**不过怎么办**：若迁移测试红——只许改 import 和测试基建，不许改断言（改断言=改行为，回第 32 步的门禁意思）；若 knip 报死代码——删掉，不许留「以后可能用到」的代码。
**错了怎么退**：flag 关，旧 Streamlit 看板顶上；revert。

> 铁律：旧 Streamlit 业务看板**并行存活 ≥7 天**才删（第 37 步执行删除，你批准）。

---

## 第 36 步 · E2E + bundle + 性能验收

**预计时间**：2 天｜**前置**：第 35 步｜**分支**：`feat/e2e-perf`

**干什么**：给新前端上 E2E 和性能验收——报告 §8.4 的两个前端数字（首包 gzip < 150 kB、提交次数 −50%）在本步落地。

**本步文件**：

```text
ecosentinel-v2/src/web/
├── e2e/
│   └── core-path.spec.ts    ✅ playwright：登录→看板→下发命令→看到遥测更新
└── （构建产物日志：首包 gzip 数字贴案）
```

### 36.1 怎么干（提示词）

```
补 playwright 核心路径 E2E（登录→看板→下发一条命令→看到遥测更新）。
跑 npm run build，贴首包 gzip 数字，目标 < 150 kB（不是总产物）。
用 React Profiler 记录轮询期间提交次数，对照基线算降幅，目标 −50%。
```

**副智能体分工**：builder 写 E2E + 跑构建 + 记录 Profiler；verifier 审「gzip 数字是首包不是总产物、Profiler 记录贴案」。

### 36.2 怎么验

```bash
cd src/web && npx playwright test                 # 核心路径绿
npm run build                                     # 日志里找首包 gzip：期望 < 150 kB（现状 263.56 kB）
```

预期看到：E2E 绿；首包 gzip **< 150 kB**；提交次数 **−50%**（Profiler 记录贴案）。
**不过怎么办**：若 gzip 差一点——查是不是还有静态 import 没改 lazy（五宗罪对治表逐项过）；若提交次数没降——查派生数组是不是漏了 useMemo 或 selector。
**错了怎么退**：revert。

### 36.3 Phase 5 出口门禁（第 8–9 周结束）

- [ ] 前端性能达标：首包 gzip < 150 kB；提交次数 −50%
- [ ] 双实现只剩 0–1 组
- [ ] 仅一个业务看板
- [ ] 56 个迁移测试全绿 + E2E 核心路径绿

---

## 第 37 步 · R8：看板收敛（Streamlit 降级）

**预计时间**：1 天｜**前置**：第 36 步｜**分支**：`refactor/board-convergence`｜**flag**：`FLAG_BOARD_STREAMLIT`

**干什么**：执行报告 §5.9 结论原话：「React 做唯一业务看板；Streamlit 降级为『标定/诊断台』（跑 `identify_rc.py`、`hardware_autodiag.py` 的结果可视化）。两套都做业务 = 双倍维护 + 双倍 bug」。**不迁移旧仓库 `dashboard/ai_pool.py` 的 `read_jsonl(max_lines=500)` 读文件头显示旧数据这个 bug**——新实现只用尾读。同时执行第 35 步立的铁律：`FLAG_WEB_REACT` 并行一周后删除 Streamlit 业务视图（**你批准**）。

### 37.1 怎么干（提示词）

业务看板唯一 + Streamlit 只留标定/诊断两个视图 + 不迁移「读文件头」bug + 删 Streamlit 业务视图。

**副智能体分工**：builder 删 Streamlit 业务视图（只留两个诊断视图）；verifier 审「仅一个业务看板、Streamlit 只剩两个诊断视图、尾读之外无全量读」。

### 37.2 怎么验

业务看板只有一个；Streamlit 只剩标定/诊断两个视图；旧业务视图已删且测试不减。
**错了怎么退**：flag 回切。

---

## 第 38 步 · D10 + R7：固件加固（命令重设计 + 采集照搬）

**预计时间**：3 天｜**前置**：第 37 步｜**分支**：`refactor/firmware-hardening`｜**flag**：`FLAG_FIRMWARE_V2`｜**契约卡**：新建

**干什么**：固件侧两个 P0——MQTT 裸奔（公网可发 `RESET`）+ 命令解析歧义（`RELAYX 1 1` 会执行；`CURTAIN SCALE 500` 被 `indexOf("CAL")` 命中；越界通道回 `ok:true`）。**铁律：采集/上报格式照搬**（那是嵌入式侧契约，第 2 步的资产/债务分流表已裁决），**命令表重新设计**。

### 38.1 报告原文（§7 D10）

| 列 | 内容 |
|---|---|
| 位置 | 旧仓库 `firmware/esp32_s3_competition/mqtt.h:17-20,49-57`；`firmware/esp32_s3_competition/protocol.h:322-385` |
| 影响 | 公网可发 `RESET`；`RELAYX 1 1` 会执行；越界通道回 `ok:true` |
| 修法 | 默认关 `USE_MQTT`；启用则 TLS+认证+ACL；命令 token 精确匹配 + 区间校验 + 失败回 `error` |

**报告 §6.12 固件补充问题**（同一张卡清掉）：`firmware/esp32_s3_competition/protocol.h` 只按空格切参；`indexOf("CAL")` 被 `CURTAIN SCALE 500` 命中；`readStringUntil` 无上限；`.ino` 无看门狗、`setup()` 阻塞 WiFi 最长 15 s；`actuators.h` 的 `setRelay` 越界静默；`display.h` 每 500 ms 全屏重绘；`config.h` 的 `USE_MQTT` 硬开启（均在 `firmware/esp32_s3_competition/` 下）。

**本步文件**：

```text
ecosentinel-v2/src/firmware/
├── contracts.h              ✅ 第 13 步 codegen 产物（C struct，不动）
├── protocol.h               ✏️ 命令解析重设计（token 精确匹配 + 区间校验）
├── config.h                 ✏️ USE_MQTT 默认 0
├── test_protocol.cpp        ✅ 负例测试
└── （.ino：setup() 非阻塞 + 看门狗）
```

代码骨架（命令解析目标形态，C 伪码）：

```c
// protocol.h —— token 精确匹配 + 区间校验 + 失败回 error
typedef enum { CMD_RELAY, CMD_CURTAIN, CMD_CAL, CMD_RESET, CMD_UNKNOWN } CmdKind;

static bool parse_command(const char* line, Command* out) {
    char tokens[MAX_TOKENS][MAX_TOKEN_LEN];
    int n = split_tokens(line, tokens, MAX_TOKENS, MAX_TOKEN_LEN);  // 有长度上限
    if (n == 0) return false;
    // 精确匹配整个 token，禁止 indexOf 子串命中
    if (strcmp(tokens[0], "RELAY") == 0)      out->kind = CMD_RELAY;
    else if (strcmp(tokens[0], "CURTAIN") == 0) out->kind = CMD_CURTAIN;
    else if (strcmp(tokens[0], "CAL") == 0)     out->kind = CMD_CAL;
    else if (strcmp(tokens[0], "RESET") == 0)   out->kind = CMD_RESET;
    else { out->kind = CMD_UNKNOWN; return true; }   // 未知命令 → error，不执行

    if (out->kind == CMD_RELAY) {
        if (n != 3) return false;
        int ch = atoi_strict(tokens[1]);            // 非数字 → error
        int val = atoi_strict(tokens[2]);
        if (ch < 1 || ch > 2 || val < 0 || val > 1) {
            out->kind = CMD_UNKNOWN;                // 越界 → error，不回 ok
            return true;
        }
        out->channel = ch; out->value = val;
    }
    /* CURTAIN/CAL/RESET 同理：token 数、区间全部校验 */
    return true;
}

// 执行结果：成功回 {"ok":true}；任何失败回 {"ok":false,"error":"..."}——禁止静默 ok
```

```c
// config.h —— MQTT 默认关（报告 §9 P0）
#define USE_MQTT 0            // 默认关；启用需 TLS + 用户名密码 + 主题 ACL
// .ino —— setup() 非阻塞 + 看门狗
void setup() {
    WiFi.begin(...);           // 不阻塞：移入 loop 里重试
    esp_task_wdt_init(WDT_TIMEOUT_S, true);   // 看门狗
}
```

测试骨架（负例测试，报告 R7 验收）：

```cpp
// test_protocol.cpp —— 固化报告 §7 D10 / R7 的负例
TEST(Protocol, RelayXIsRejected)      { assert_rejected("RELAYX 1 1"); }
TEST(Protocol, OutOfRangeRejected)    { assert_error("RELAY 5 1"); }     // 不是 ok
TEST(Protocol, CurtainScaleNotCal)    { assert_not_cal("CURTAIN SCALE 500"); }
TEST(Protocol, EmptyLabelRejected)    { assert_rejected(""); }
TEST(Protocol, NoLengthLimitCrash)    { assert_no_crash(std::string(10000, 'A')); }
```

### 38.2 怎么干（任务卡全文 + 定制点）

```
（两张任务卡照发，另加：）
采集格式是契约，照搬旧仓库，禁止发明新字段；
命令表重新设计（RELAYX 歧义、CURTAIN SCALE 500 不命中 CAL）。
负例测试：RELAYX 1 1 拒、越界回 error、CURTAIN SCALE 500 不命中。
补 WDT；setup() WiFi 阻塞改非阻塞。
```

**排期说明**（诚实列出来）：本手册把固件放在第 10–11 周（报告 R7 排在第 6 周）——单人每天 3–4 小时，固件改动需要硬件在环验证；若你有常驻硬件，可提前与第 35 步并行（用独立工作区防上下文污染）。

**副智能体分工**：builder 重写 protocol.h 解析 + 负例测试 + WDT + 非阻塞 WiFi；verifier 审「失败路径全部回 error，没有一条静默 ok」。

### 38.3 怎么验

负例测试通过；`arduino-cli compile` 过；`USE_MQTT` 默认为 0；真实硬件联调一次通过（**或记录未联调原因，不许假装通过**）。
**错了怎么退**：revert（固件烧录有独立版本管理，保留上一版 bin）。

> **纪律**：固件构建进 CI——报告 §10.2 原话：`arduino-cli` CI。固件是唯一「烧错了要物理接触才能恢复」的部分，编译岗不能省。

---

## 第 39 步 · P2 项按需（ADC 量化 / OTA 证书校验）

**预计时间**：2 天｜**前置**：第 38 步｜**分支**：按项建

**干什么**：报告 P2 清单（ADC 量化、OTA 证书校验等）按剩余时间取舍。**纪律：P2 永远给 P0/P1 让路**——前 38 步有任何返工没清完，本步就给返工让位。

**怎么验**：做了的项有测试；没做的项在 `docs/FINDINGS.md` 里记一笔（欠债明示，不是假装不存在）。
**错了怎么退**：revert 对应分支；没做的项留在 FINDINGS.md，下个迭代再排。

---

## 第 40 步 · 文档数字脚本化（check_doc_numbers.py）

**预计时间**：1 天｜**前置**：第 39 步｜**分支**：`chore/doc-numbers`

**干什么**：把 README/SPEC 里的关键数字（测试数、覆盖率、性能）从测试/构建输出生成，CI 校验一致性——「写 251 实际 365」这类文档腐烂从此不可能。第 3 步的 pre-commit 里已预留 `doc-numbers-check` 钩子位，本步把脚本写出来装上。

**本步文件**：

```text
ecosentinel-v2/scripts/
└── check_doc_numbers.py    ✅ 从实测输出生成数字，CI 校验一致性
```

### 40.1 怎么干（提示词）

```
写 scripts/check_doc_numbers.py：README/SPEC 里的关键数字
（测试数、覆盖率、性能）从测试/构建输出生成，CI 校验一致性。
「写 251 实际 365」从此不可能。
```

### 40.2 怎么验

```bash
uv run python scripts/check_doc_numbers.py        # 期望 PASS
```

自测法：**故意改错 README 里一个数字，脚本必须报错**；改回来再绿。
**错了怎么退**：revert。

---

## 第 41 步 · 死代码扫描 + flag 清零 + 删工作副本

**预计时间**：1 天｜**前置**：第 40 步｜**分支**：`chore/deadcode-flag-zero`

**干什么**：三件事——① `uvx vulture src/` + `npm run knip` 扫死代码；② FLAGS.md 活跃项必须为 0（**删不掉的 flag 说明对应合并没完成，回到对应 Phase 收尾**——这是 flag 纪律的闭环：每个 flag 出生时就知道自己的死期）；③ 删除 `~/EcoSentinel-work`（第 17 步建的工作副本，表征测试已全部迁进新仓库，它的使命结束了）。

**本步文件**：

```text
~/EcoSentinel-work/          ❌ 删除（表征测试已全部迁进新仓库）
docs/FLAGS.md                ✏️ 活跃项清零（删掉的 flag 连同死代码分支一起删）
```

### 41.1 怎么干（提示词）

```
uvx vulture src/ + npm run knip，输出贴出来。
FLAGS.md 活跃项必须为 0：每个 flag 删除时同步删它的死代码分支。
删不掉的 flag 说明合并没完成，回到对应 Phase。
```

### 41.2 怎么验

```bash
uvx vulture src/                                  # 无新死代码
cd src/web && npm run knip                        # 无新死代码
cat docs/FLAGS.md                                 # 活跃 flag = 0
ls ~/EcoSentinel-work 2>&1                        # 期望：No such file or directory
```

预期看到：四条全过。
**不过怎么办**：vulture 误报——加白名单注释（`# noqa` 或 vulture whitelist），不许 bare except 式忽略；flag 删不掉——**那才是真问题**，回到对应合并步收尾，不许硬删 flag 留死代码。
**错了怎么退**：revert（但先查为什么删不掉——那才是真问题）。

---

## 第 42 步 · ADR 补全 + ARCHITECTURE.md

**预计时间**：半天｜**前置**：第 41 步｜**分支**：`docs/adr-complete`

**干什么**：两件事——① 每个合并决策（8 个接缝）补一条 ADR：为什么以 X 为准、旧实现去哪了。**未来的你和论文审稿人会感谢现在**——ADR 是「为什么」的博物馆的索引。② 补 `docs/ARCHITECTURE.md`（第 9 步的 AGENTS.md 文档地图承诺过它，现在架构已定型，写全景：四层 + 数据流 + 8 接缝的最终形态）。

**本步文件**：

```text
ecosentinel-v2/docs/
├── adr/
│   ├── 0002-single-evolution-track.md  ← 步 7（已有）
│   └── 0003-0010-<接缝名>.md           ✅ 每个合并接缝一条
└── ARCHITECTURE.md                     ✅ 架构全景
```

### 42.1 怎么干（提示词）

```
对照 docs/specs/SEAMS.md 的 8 个接缝，每个补一条 ADR：
决策上下文/备选方案/为什么以 X 为准/旧实现的去向/日期。
另写 docs/ARCHITECTURE.md：四层架构 + 数据流 + 8 接缝最终形态。
```

### 42.2 怎么验

ADR 数量 = 已合并接缝数；每条能回答「旧实现去哪了」；ARCHITECTURE.md 的四层与代码实际分层一致（`uv run pytest tests/contract/test_layering.py` 绿就是一致）。
**错了怎么退**：改文件。

---

## 第 43 步 · 终局验收（全量重跑，新仓库「转正」）

**预计时间**：1 天｜**前置**：第 42 步｜**分支**：无（只在 main 上跑）

**干什么**：把报告附录 A 的实测清单**全部重跑一遍**，贴真实输出。任一项不过：定位 → 修 → 重跑。全绿后写终局报告（数字 + 截图路径）。

### 43.1 怎么干（全量命令，逐条贴输出）

```bash
# 后端
uv run pytest tests -q                                    # 期望 ≥400 passed（当前实测基线 365）
uv run pytest tests -q --cov=energy_system                # 期望 TOTAL ≥80%
uv run python -m energy_system.simulation.compare       # 期望 D1 已修（阻断计数真实）
uv run python scripts/stack_acceptance.py                 # 期望 PASS 7/7（127.0.0.1）

# 前端（src/web/）
npm ci && npm run lint && npm run knip && npm test         # 期望 56 passed 起只增不减
npm run build                                             # 期望首包 gzip < 150 kB

# 行为探针（tools/，此时全部打新仓库验证修复）
PROBE_TARGET=src uv run python tools/dyn1.py      # 阻断 0 vs 134 → 修正后两个数一致（都是 134）
PROBE_TARGET=src uv run python tools/dyn3.py      # 失败缓存、跨日电量、label 穿越 → 不再复现
PROBE_TARGET=src uv run python tools/perf.py      # 670ms → 修正后 P95 < 50ms
PROBE_TARGET=src uv run python tools/api_probe.py # API 语义 → 修正后无假字段

# 工程债清理
uvx vulture src/                                         # 期望无新死代码
uvx pip-audit                                            # 期望干净
uv run python scripts/check_doc_numbers.py               # 期望 PASS
cat docs/FLAGS.md                                        # 期望活跃 flag = 0
```

### 43.2 验收数字对照表（性能目标唯一来源，全部来自报告 §8.4）

| 指标 | 现状（报告实测） | 目标（报告 §8.4） | 新仓库验收命令 |
|---|---|---|---|
| 120k 行（≈7 天）查询 P95 | 670 ms（`read_all`）；`latest/tail/read_since` 835/848/791 ms | **< 50 ms** | `uv run pytest -q -m perf` |
| 轮询 CPU 占比 | 190%（7 天） | < 10% | 压测脚本（迁 `tools/perf.py`） |
| 首包 gzip | 263.56 kB | **< 150 kB** | `npm run build` 产物日志 |
| 轮询期间 React 提交次数 | 每 3 s 全树 | **−50%** | React Profiler 记录 |
| 采集→落盘延迟 | 5 s 周期 | 不变 | 去掉串口阻塞后复核 |
| 尾读参照实现 | 120k 行 **1.1 ms** | — | 对照基线（**不是验收线**；验收线是上表的 50 ms） |

> **特别强调**：1.1 ms 是尾读实现本身的耗时，**不是**任何接口的验收线；报告的验收线是 **P95 < 50 ms**。前端同理：报告要的是**首包 gzip < 150 kB**，不是总产物 < 300 kB。

### 43.3 Phase 6 出口门禁（新仓库「转正」）

- [ ] 上面八项全绿，真实输出贴案
- [ ] 终局报告写完（数字 + 截图路径）
- [ ] **旧仓库保留只读存档，永不删除**——它是「为什么」的博物馆

**错了怎么退**：任一项不过 → 回到对应步骤修（门禁表里每项都标了来源步）→ 重跑本步全量命令；不允许「跳过该项直接转正」——43 步的意义就是全绿才算完。

---

# 附录 A · 日常三清单 + 健康度六指标

11 周跑完后，这些习惯决定仓库是**资产**还是**新的死山**。

## A.1 每天开工前（2 分钟）

- [ ] `git status` 干净；main 是绿的
- [ ] 今天做哪一步？把该步的契约卡贴到便签
- [ ] DSH 工作区指向正确；会话是新的（或 fork 自干净点）

## A.2 每个任务完成后（5 分钟）

- [ ] 契约卡五字段在 commit message 里
- [ ] Evidence 是真实命令输出原文
- [ ] verifier PASS 记录在案（正式级任务）
- [ ] flag/SEAMS/SPEC 有变动已同步
- [ ] `uv.lock` 的改动是有意的（加了依赖）还是漂移

## A.3 每周五（10 分钟，死山预警）

先跑进度看板提示词，贴进 `docs/STATUS.md`：

```
生成本周进度看板：当前 Phase/本周完成步/双实现剩余数（对照 SEAMS.md）/
测试总数/覆盖率/活跃 flag 数/分支最长寿命/uv.lock 是否被无意义改动。
用一张 ASCII 表输出。
```

然后逐项过：

- [ ] 最长分支寿命 < 48h？
- [ ] 测试数比上周少？（唯一合法减少：删双实现时的同步迁移）
- [ ] 本周有没有「同一个 bug 修第二次」？（有 = 在打补丁，停下来修根因）
- [ ] 文档数字和实测还对得上吗？（第 43.2 节那张表逐项过）
- [ ] 亲自读过本周的关键 diff 吗（flag 切换/删旧实现/口径变更）？
- [ ] 对照 D/R 总表：本周计划完成了吗？有没有被智能体「顺手」改口径？

**命中任意两条异常 → 当周停止开新任务，只做修复。连续两周同一项没有变化，就是死山预警信号。**

## A.4 健康度六指标（终局后长期保持）

把这六个指标写成 `scripts/health.py`，CI 每周跑一次，贴进 `docs/STATUS.md`：

| 指标 | 健康线 | 超过怎么办 |
|---|---|---|
| 测试总数 | 只增不减（合法减少仅限删双实现同步迁移） | 停止开新任务，先补回 |
| 覆盖率 TOTAL | ≥80%（第 43 步验收线） | 掉出先补表征测试再写新功能 |
| 活跃 flag 数 | 0（合并完成的标志） | >0 超过两周 = 有合并没有完工，回去收尾 |
| 最长分支寿命 | <48h | 拆分任务；分支长寿 = 冲突与死山温床 |
| `uv.lock` 漂移 | 仅 `uv add` 产生 | 查是谁手动改了；`uv sync --frozen` 对齐 |
| 文档数字一致性 | `check_doc_numbers.py` PASS | 跑第 40 步的脚本重生成 |

> **一句话总结运营**：契约是软的，git 和 CI 是硬的。每天两分钟、每周十分钟，是把「防死山」从口号变成肌肉记忆的唯一方式。

---

# 附录 B · 成本模型与故障排查

## B.1 成本模型（心里有账）

| 项 | 数字 |
|---|---|
| DeepSeek V4.1 Flash 每次编程请求平均成本 | ≈ $0.0067（list price 实测流量） |
| Flash 每任务成本 | <$0.20（top setting）；低 effort ≈$0.10 |
| Kimi 旗舰（k2.7-code 档平台价） | 输入 **¥6.50** / 输出 **¥27.00** 每百万 token（缓存 ¥1.30）；K3.1 Pro 以平台页面为准 |
| 主副搭配（≈80% Flash + 20% Kimi） vs 全 Kimi | 类比估算：**省 60–75%**（同类路由策略在 Claude+DeepSeek 组合的实测；这里是估算不是承诺，以你的账单为准） |
| 缓存命中 | Flash 缓存输入 $0.003–0.006/百万——按前缀匹配生效，长会话反复读相同开头（如 AGENTS.md）**可能**命中；是否自动开取决于版本与请求结构，**以实测账单为准** |

**两条渠道不要混**：DeepSeek **官方** API 在闲时半价（时段以定价页为准）；另有第三方渠道（如七牛云等）长期折扣。两者计费体系不同，账单以你实际走的渠道为准。

**四条省钱纪律**：

1. **低谷跑批量**：用官方 API 就把批量迁移、大批测试跑在闲时半价窗口（时段查定价页）；用第三方渠道就按它的折扣规则。
2. **输入 token 是大头**：编程智能体每次请求 32k–55k token 是系统开销（**这是 Claude Code 的实测数据，DSH 上以 Trajectory 面板看到的为准**）——所以**主会话别贴大文件**，给 file:line 让 child 去读。
3. **reader 汇总替代主会话精读**：读 10 个文件的活派 1 个 child，主会话只收 10 行结论。
4. **verifier 用 Flash 不用 Kimi**：审计是对照性工作，不烧脑——除非 verifier 连续误判，再升级到 Kimi。

## B.2 故障排查表

| 现象 | 原因 | 解法 |
|---|---|---|
| 模型调用报错 | key/额度/地址 | 桌面版：Settings → Models 看 provider 配置；CLI：`npx @deepseek-ai/dsh --dump-config` 看合并后配置 |
| reasoning 内容乱码/思考不显示 | 方言猜错 | settings.yaml 补 `compat.thinkingFormat`（kimi→openai，deepseek→deepseek，三坑之一） |
| 长文档被截断 | contextWindow 默认 262k | 模型条目写 `contextWindow: 1048576`（三坑之二） |
| 起了 subagent 但模型不对 | **继承了会话创建时的模型** | spawn 话术显式钉 provider+model；装 `dsh-subagent-model-config` + `dsh-model-pin` |
| 起不了 subagent | 预设模式不是 Standard / 版本太低 | 切 Standard；升级 DSH ≥0.2.1-rc.1 |
| agent-team 成员不生效 | 改了模板但运行中是旧快照 | 移除成员重新添加（不热更新） |
| Agent 读写不到文件 | workspace 选错 | 桌面版重新 Choose workspace（Agent 只能访问该目录） |
| child 报告「token 暴涨」 | child prompt 里粘了整文件 | 改给 file:line 指针 |
| `uv run` 报找不到解释器 | 没 pin 过 Python | `uv python pin 3.12` 后重试 |
| CI 红、本地绿 | 锁文件漂移/本地没跑全岗 | `uv sync --frozen` 对齐；本地 `uv run pre-commit run --all-files` |
| Node 语法错误 | Node 版本低 | 升到 22.19+ |
| 智能体反复改不对 | 会话污染 | 重开会话，把任务卡+教训写成更好的初始提示 |
| 插件装上没反应 | profile 参数/版本不匹配 | `plugin --help` 核对语法；重启 DSH（桌面版在插件管理页检查启用状态） |
| 桌面版插件管理找不到某个插件 | Desktop 管理自己的插件列表 | 旧 CLI 装的插件要在 Plugins → Add plugin 手动迁移 |
| 探针跑起来报 ImportError | PROBE_TARGET 指错了 | 探针默认打旧仓库根；打新仓库才设 `PROBE_TARGET=src`，且目标目录必须含 `energy_system` 包 |
| 表征测试迁进新仓库后红 | import 行没改 / 旧行为断言没兑现 | 只许改 import（旧平铺 → `energy_system.` 包路径）；钉缺陷旧行为的断言按迁移步的注释规矩改 |

## B.3 安全纪律（再强调一遍）

- workspace 只指向项目目录；**不要**给 Agent home 目录/桌面/系统目录权限
- DSH **未经系统性安全审计**：shell 工具可执行真实命令、可加载插件、可访问本地凭据——第三方插件安装前三思
- PTC 模式（模型生成 TS 脚本自动执行）**不开**，直到你熟悉 DSH
- DSH 是开发者预览版，会有破坏性变更：**升级前 git 提交一切**；会话记录在本地，重要结论及时落盘到仓库
- 副智能体的 report 只是「提案」：Evidence 行凡是数字，**你用命令亲自复现一遍再信**（模型对编造和验证过的事实用同样确信的语气）

---

# 附录 C · 参考链接

**DeepSeek Harness（DSH）**

1. DSH GitHub：https://github.com/deepseek-ai/deepseek-harness （docs/ 目录含 development.md、AGENTS.md）
2. DSH 桌面版下载：https://deepseek.com/harness （macOS/Windows 安装包；插件管理页面免命令行）
3. DSH Subagents 教程（spec.md 角色契约 + spawn 机制 + 模型钉定）：https://deepseekharnessplugins.com/learn/subagents-guide
4. DSH 安装与自定义 Provider（三个静默故障：方言/上下文/ID）：https://www.atlascloud.ai/blog/tips/how-to-install-deepseek-harness
5. DSH 入门（Cordis 架构/四种预设/安全注意）：https://developer.aliyun.com/article/1773655 与微信公众号《DeepSeek-Harness 入门》
6. Agent Team 插件（Leader+成员，按角色分模型）：https://ai-develop.top/blog/1787737087810
7. 房间式群组协作插件：https://ai-develop.top/blog/1791679788788
8. dsh-model-pin / dsh-subagent-model-config（subagent 模型钉定，第 5 步三层解法的插件层）

**模型与价格**

9. Kimi 开放平台模型与价格：https://platform.moonshot.cn/ ；K3.1 Pro 价格见平台模型列表
10. DeepSeek V4.1 Flash-1017 发布说明（为 DSH 调优、Search/Fetch API）：https://aitoolinsights.com/deepseek-releases-v4-1-flash-1017-with-mit-licensed-weights-and-new-search-and-fetch-apis
11. V4.1 Flash 在编程智能体中的实测与成本：https://clawdbytes.com/article/2026-10-24-deepseek-v41-flash-in-claude-code-and-opencode-setup-test-runs-and-what-it-costs.html

**工具链标准**

12. uv 文档（python pin / sync / lock / run / add）：https://docs.astral.sh/uv/
13. AGENTS.md 开放标准：https://agents.md/
14. Conventional Commits：https://www.conventionalcommits.org/

**项目事实来源**

15. **《EcoSentinel 全项目深度审阅报告》（2026-10）**——本手册所有项目数字（D1–D10 缺陷、R1–R8 动作、覆盖率盲区、性能指标、双实现清单、迁移五步）的唯一来源。每个缺陷/重构步骤的「报告原文」行均标注了其在报告中的小节。
16. 旧仓库（`legacy-reference` tag，只读存档）——规格与行为的博物馆；「为什么这样改」的答案有一半在里面。

---

# 附录 D · 四步工作法展开版（指挥智能体的完整参考）

第 1 步是一页纸版；这里是可以反复查的完整版。

## D.1 流程图

```
你（发任务卡）
   │
   ▼
① EXPLORE（主智能体 Kimi，plan mode 只读）
   读文件 → 起 reader 副智能体并行读 → 5 行复述理解
   │  「我说继续才动笔」
   ▼
② PLAN（主智能体 Kimi）
   写实现计划（改哪些文件、什么顺序、风险点）
   │  你审阅 ──不通过──▶ 改计划（不许跳过）
   ▼ 通过
③ IMPLEMENT（主智能体 spawn builder 副智能体 Flash）
   先写失败测试 → 最小实现 → 跑测试
   │  report 回主会话
   ▼
④ VERIFY（主智能体 spawn verifier 副智能体 Flash，独立会话）
   对照契约卡审计 → PASS/FAIL + file:line
   │ FAIL ──▶ 回 ③（带 verifier 意见；两次不过 ──▶ 你介入/重开会话）
   ▼ PASS
⑤ COMMIT（主智能体）
   git commit（带契约卡 + 真实 Evidence）→ push → CI 绿 → squash 合并
   │
   ▼
⑥ 你抽检关键 diff（只读 flag 切换/删旧实现/口径变更三类）
```

**什么时候可以跳过 plan**：diff 一句话能描述完的（改文案、改配置）。本项目几乎每个任务都涉及口径，**默认不跳**。

## D.2 提示词总结构：Input–Process–Output

把智能体当**初级工程师** briefing：不要模糊请求，要结构化指令。所有任务提示词遵循同一骨架：

```
【任务卡】
- 编号/意图（Intent）：
- 范围（Scope）：允许读/改的文件清单（白名单）
- 边界（Boundaries）：禁止改的接口/schema/测试；必须保持兼容的行为
- 证据（Evidence）：必须通过的命令与性能数字
- 回滚（Recovery）：flag 名 / revert commit

【输入（Input）】
- 参考文件（file:line，指向权威位置，不粘贴内容）
- 旧实现位置（如涉及迁移）：以 X 为准，禁止迁移 Y，原因：……

【过程（Process）】
1. 先读这些文件，用 5 行以内复述你理解的任务（不许写代码）
2. 【等我说「继续」】
3. 表征测试：先写失败测试固化旧行为
4. 最小实现，通过测试
5. 跑全量命令，贴真实输出

【输出（Output）】
- 改动的文件清单 + 每个文件为什么
- 测试/性能真实输出（贴原文，禁止概述编造）
- 遇到的旧代码「为什么」问题清单（回旧仓库查证后再继续）
```

**两条会话纪律**：

1. 两次修正失败就**重置会话**，把学到的东西写进更好的初始提示，而不是继续纠正（Anthropic 对无限纠正失败模式的标准处方）
2. **无限探索禁止**：给文件清单，不让智能体满仓库自己逛（上下文填充 → 注意力稀释 → 开始瞎编）

## D.3 反模式提示词对照表

| ❌ 反模式（智能体会顺势重写/幻觉） | ✅ 正模式 |
|---|---|
| 「重构这个项目」 | 「把 X 模块的 read_all 换成尾读，只改 data_store.py，测试先行」 |
| 「优化一下性能」 | 「120k 行文件读取 P95 从 670ms 降到 <50ms，验收命令：uv run pytest -m perf」 |
| 「修复舒适度的问题」 | 「comfort.py 输出必须是 [0,1]；先写断言 API 输出范围的失败测试」 |
| 「看看还有没有类似问题，一起改了」 | 「本次只修 D5。发现的其他问题写进 FINDINGS.md，不许动」 |
| 「用你熟悉的架构重写 dashboard」 | 「新前端用 React+TS，只接 api.ts 现有字段；Python 服务并行存活」 |
| 「（把整份旧仓库粘进上下文）」 | 「file:line 指针 + 按需读」——上下文是预算，不是垃圾桶 |
| 「继续修，直到通过」 | 两次失败 → 重置会话，重写初始提示 |

## D.4 常见情况处置

| 情况 | 处置 |
|---|---|
| builder 两次没做好 | **不要第三次纠正同一会话**。重开会话，把前两次的教训写进新任务卡 |
| verifier 和 builder 结论冲突 | 你当法官：让双方各贴证据（file:line + 命令输出），主智能体只转述不站队 |
| 主会话上下文见涨（头部 token 数变大） | 开新会话，把当前任务卡 + 已有结论粘过去（任务卡是「便携式上下文」） |
| 副智能体想改 AGENTS.md | 拒绝。只有你能改，且改完必须 rebuild 团队快照（agent-team 插件不热更新运行中成员） |
| 想看看副智能体究竟干了什么 | Trajectory 标签页：每一步工具调用入参/返回/token 全在 |
| child 跑完发现模型不对（第 5 步的陷阱） | 检查 spawn 话术有没有显式钉模型；装 `dsh-subagent-model-config` + `dsh-model-pin` 兜底 |

## D.5 九个智能体重构案例浓缩成五条纪律

| 案例 | 一句话 | 对本手册的哪条纪律的启示 |
|---|---|---|
| 美团 31 万行定向重构 | 先定向定位再穷举验证，不整体重写 | 一次只做一个接缝（分步合并） |
| bayesm（R 包） | AI 重构引入**隐蔽数学缺陷**，测试全绿但结果错 | verifier 必查「语义幻觉」：能跑≠对 |
| kuva（Rust） | 重构后逐张核对 900 张输出图 | 对外数字必须有人眼验收（SPEC.md 签字） |
| HI.SIM | 零干预下达成了字节级一致的迁移 | 先钉行为 + 对拍，是能做到「零干预」的前提 |
| 200K 行 Java 项目 | 最有价值的一份文档是「**what NOT to do**」 | AGENTS.md 的「已知陷阱」和「边界」章节 |
| CodeScene 30 万行分析 | 用回放轨迹测试验证重构，花了 $4000 | shadow 双跑框架值得建（第 15 步） |
| Kimi Code 8 子智能体 | 三种并发模式（流水线/评审团/分治）均验证可行 | 主副架构可行；reader→builder→verifier 就是流水线模式 |
| 10 Agent 并行实验 | 权限隔离是并行不翻车的前提 | 一个智能体一次只碰一个接缝（Scope 白名单） |
| k10s / WorkOS 约束面对比 | 同一模型，有约束面无死山、无约束面 3 个月成山 | 本手册全部机械门禁的存在理由 |

---

# 附录 E · D/R/flag 编号速查表

**缺陷 D1–D10 → 手册步号**（按报告 §7 顺序；位置见开头「旧仓库关键文件速查表」）：

| # | 缺陷 | 修于步 | flag | 契约卡 |
|---|---|---|---|---|
| D1 | 阻断计数读错实例（0 vs 134） | 步 21 | `FLAG_SIM_FIX` | C5 |
| D2 | 下发失败被当成功缓存 | 步 22 | `FLAG_SEND_RESULT` | C5 |
| D3 | 跨午夜电量重复累计 | 步 23 | `FLAG_DAY_ROLLOVER` | C5 |
| D4 | 舒适度两套量纲（0.5 vs 50.0） | 步 26 | `FLAG_COMFORT_NORM` | C2 |
| D5 | JSONL 全量读（7 天即崩） | 步 19 | `FLAG_DATA_TAIL_READ` | C1 |
| D6 | API 语义伪造（四个假字段） | 步 32 | 无（纯删除） | C6 |
| D7 | 前端「假在线」+ 残留 29.9% | 步 32/35 | `FLAG_WEB_REACT` | C6/C8 |
| D8 | 路径与工作目录 | 步 18 | 无 | 新建 |
| D9 | label 穿越 + 无鉴权 + 0.0.0.0 | 步 31 | `FLAG_AUTH` | C7 |
| D10 | 固件 MQTT 裸奔 + 命令歧义 | 步 38 | `FLAG_FIRMWARE_V2` | 新建 |

**重构 R1–R8 → 手册步号**（按报告 §12.2 顺序）：

| # | 动作 | 做于步 | flag |
|---|---|---|---|
| R1 | 遥测 schema codegen（Py/TS/固件） | 步 13 | 无 |
| R2 | `TelemetryStore` + 尾读 + SQLite | 步 19/20 | `FLAG_DATA_TAIL_READ` / `FLAG_SQLITE_STORE` |
| R3 | 决策管线接口化（4 Protocol） | 步 29 | `FLAG_PIPELINE` |
| R4 | AI 双实现合并（门面 + 唯一熔断） | 步 27 | `FLAG_AI_SIM` |
| R5 | 配置 pydantic-settings 化 | 步 28 | `FLAG_CONFIG_V2` |
| R6 | 前端收敛（React+TS） | 步 35 | `FLAG_WEB_REACT` |
| R7 | 固件加固（WDT/解析/ACK/MQTT） | 步 38 | `FLAG_FIRMWARE_V2` |
| R8 | 看板收敛（Streamlit 降级） | 步 37 | `FLAG_BOARD_STREAMLIT` |

**15 个 flag 全表**（登记册 `docs/FLAGS.md` 是运行时的事实源；本表是导航）：

| flag | 引入步 | 删除条件 |
|---|---|---|
| `FLAG_DATA_TAIL_READ` | 19 | shadow 双跑一周无回归且你批准 |
| `FLAG_SQLITE_STORE` | 20 | 双实现对拍一致 + 一周无回归 |
| `FLAG_SIM_FIX` | 21 | 复现测试绿 + dyn1 探针输出真实计数 |
| `FLAG_SEND_RESULT` | 22 | 连续 3 轮重发测试绿 |
| `FLAG_DAY_ROLLOVER` | 23 | 跨午夜测试绿 + dyn3 探针消失 |
| `FLAG_CONTROL_MERGED` | 24 | 同种子 1000 步逐位相等 |
| `FLAG_KPI_MERGED` | 25 | shadow 最大偏差 < 1e-9 |
| `FLAG_COMFORT_NORM` | 26 | shadow 双跑两周偏差 < 1e-6 + 你批准 |
| `FLAG_AI_SIM` | 27 | 旧测试不改断言全绿 + stub 不可达有测试 |
| `FLAG_CONFIG_V2` | 28 | 坏配置 fail-loud 测试绿 |
| `FLAG_PIPELINE` | 29 | `usecases(app)` 消失 + 审计事件有覆盖 |
| `FLAG_AUTH` | 31 | 5 类 payload 被拒 + 7/7 契约仍绿 |
| `FLAG_WEB_REACT` | 35 | E2E 绿 + 首包 < 150 kB + 并行一周 |
| `FLAG_BOARD_STREAMLIT` | 37 | 仅一个业务看板 + 旧服务已删 |
| `FLAG_FIRMWARE_V2` | 38 | 负例测试绿 + 硬件联调通过 |

**报告 §14.2 的「8 个 P0」是哪 8 个**：报告 §11.2 缺陷影响矩阵中 ●●● 的 8 行，按行序即：**D1、D2、D3、D4、D5、D6+D7、D9、D10**。30 天窗口内必须全部完成（§7.7）。

**如果只做三件事**（报告 §14.3）：① 修证据（D1–D4）；② 换数据层（D5）；③ 先申请专利（在所有公开之前，第 12 步）。

---

*本手册的每条命令、每段话术都经过来源交叉验证；DSH 处于开发者预览期，具体版本行为以 `dsh --version` 实测为准。规矩是软的，git 和 CI 是硬的——任何时候不确定，先 commit。*
