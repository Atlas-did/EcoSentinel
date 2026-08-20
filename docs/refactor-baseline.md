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
| 总能耗 | 81.48 kWh | 57.18 kWh |
| 节省电量 | — | 24.30 kWh |
| 节能率 | — | 29.8% |
| 平均舒适度 | 82.1% | 82.1% |

> 以上数字仅说明“当前模型与参数下仿真可运行、可比较”，**不是**真实建筑实测节能率。

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
