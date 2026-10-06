# Refactor Baseline (行为冻结清单)

> 生成方式：`python scripts/collect_baseline.py`
>
> 用途：在渐进式重构期间冻结当前可运行行为，任何代码迁移若导致下述数字变化，必须保留新旧结果并解释变化来源（bug 修复 / 参数变化 / 算法变化）。

## 1. 复现命令

```bash
python -m pytest tests -q
python -m energy_system.simulation.compare
# 或一键生成结构化基线
python scripts/collect_baseline.py --out results/baseline.json
```

## 2. 测试基线

| 项目 | 基线值 |
|---|---|
| 测试数量 | 20 项通过 |
| 覆盖范围 | 配置解析、协议解析、AI 回退、自愈编排、命令校验 |

## 3. 仿真基线（固定参数）

| 参数 | 值 |
|---|---|
| 随机种子 | 42 |
| 时间步长 | 300 s |
| 时长 | 3 天 |
| 初始室内温度 | 20.0 °C |
| 天气输入版本 | `environment_generator_v1` |

| 指标 | baseline | saving |
|---|---|---|
| 总能耗 | 199.10 kWh | 164.01 kWh |
| 节省电量 | — | 35.09 kWh |
| 节能率 | — | 17.6% |
| 平均舒适度 | 49.3% | 49.1% |

> ⚠️ **2026-10 更正**：上表旧值为 81.48 / 57.18 / 24.30 / 29.8% / 82.1%，那是 **热模型显式欧拉发散**
> （dt=300s > 2τ=27.8s）时的产物，**不是**有效仿真结果。修好积分器（解析指数积分）后按真实重算，
> 即上表现值。详见 `docs/refactor-design-v1.md` 的实施记录与 `tests/unit/test_thermal_model.py`。

> 以上数字仅说明“当前模型与参数下仿真可运行、可比较”，**不是**真实建筑实测节能率；
> 建筑参数（`A_WALL/U_WALL/C_AIR`）目前**为演示级取值、未做标定**，故节能率只能作内部一致性参考。

## 3bis. 两个估计量（2026-10 新增，审计建议 · 评审 §6.4）

| 估计量 | 方法 | 实测值 | 门禁 |
|---|---|---|---|
| **配对差值**（现行对外口径） | `python -m energy_system.simulation.compare`：先跑 baseline 3 天、再跑 saving 3 天，取两段总能耗之差 | **17.6%**（199.10 → 164.01 kWh，减碳 20.03 kg） | `tests/contract/test_simulation_baseline.py` |
| **IPMVP Option C（ASO 交替）** | `aso_experiment.run_aso_experiment()`：**同一段连续仿真内逐日交替**开关策略（"关"=baseline，"开"=报告期），用**室外温度回归**把 baseline 外推到报告期工况 | **19.12% ± 4.21 kWh（95%）**，6 天/seed 42，`baseline = -74.73 + 4.81·T_out`（`R²=0.82`） | `tests/contract/test_aso_experiment.py` |

⚠️ **两者是不同的估计量，不可混用、不可取平均**：配对差值回答"同一工况下开关节能策略差多少"；
Option C 回答"用回归 baseline 预测报告期工况，实际省了多少"。对外引用时**必须写明用的是哪一个**，
并都带上"仿真天数 / 未覆盖全工况 / 建筑参数未标定"的口径说明。
（决策待定：对外主口径用哪个 —— 见 `docs/handoff.md` §4。）

## 4. 行为不变清单

重构期间，以下行为不得在未获批准算法变更的情况下改变：

1. 规则控制器 `baseline` / `saving` 模式含义不变。
2. 温度滞回（±0.5 °C deadband）与最小启停时间（运行 ≥15 min、停止 ≥10 min）语义不变。
3. AI 不能接管规则保留的继电器 1、2。
4. 无硬件模式下不应尝试发送真实串口命令。
5. 传感器无效或数据过期时系统必须进入安全降级。
6. 日志字段重命名必须提供迁移或兼容读取策略。

## 5. 核心入口与契约

- 控制器输出字段：`power_ac`、`is_heating`、`power_light`、`t_set`。
- 命令允许范围：RELAY 1–4（AI 仅 3–4）、CURTAIN OPEN/CLOSE/STOP、BUZZER 0/1。
- 日志核心字段：`timestamp`、`temperature`、`humidity`、`illuminance`、`eco2`、`power_w`、`energy_wh`、`solar_power_w`、`comfort_score`、`safe_mode`、`ai_*`。
- API 路由：`/api/ping`、`/api/health`、`/api/snapshot`、`/api/chart`、`/api/energy-summary`、`/api/ai-candidates`、`/api/resilience`、`/api/simulation/params`。
