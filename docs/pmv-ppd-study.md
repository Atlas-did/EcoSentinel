# PMV/PPD 测算：用公开标准核对项目的舒适度指标（评审 §8 第 6 步）

> 目的：评审建议"引入 `pythermalcomfort` 算 PMV/PPD，替换拍脑袋的 TCI"。本文件记录**实测结果**，
> 以及在**不臆造参数**前提下能给出的具体建议。
> 声明：本文只做**方法学核对**，不改动 `algorithms/comfort_eval.py` 的任何数值（那需要一次对外口径决策）。

## 1. 方法与参数（全部可复现）

- 工具：`pythermalcomfort`（GitHub 仓库 `CenterForTheBuiltEnvironment/pythermalcomfort`；
  采用前请确认其 LICENSE 与版本），调用 `pmv_ppd_iso(model="7730-2005")`。
- 环境参数（**轻办公夏季**的常规取值，非本项目实测，故仅用于方法对比）：
  `met=1.2`（轻体力办公）、`clo=0.5`（夏季典型着装）、`RH=50%`、`v=0.1 m/s`、`tr=ta`（辐射温度取等于气温）。
- 复现命令（无需改动仓库依赖，uv 临时环境）：

```bash
uv run --with pythermalcomfort python - <<'PY'
from pythermalcomfort.models import pmv_ppd_iso
for t in (22,23,24,25,26,27,28):
    r = pmv_ppd_iso(tdb=t, tr=t, vr=0.1, rh=50, met=1.2, clo=0.5, model="7730-2005")
    print(t, round(r.pmv,2), round(r.ppd,1))
PY
```

## 2. 实测结果（2026-10 采集）

| 温度 | PMV | PPD | 项目当前 `calc_TCI` |
|---|---|---|---|
| 22 °C | −0.81 | 18.9% | 0.00 |
| 23 °C | −0.51 | 10.4% | 0.00 |
| **24 °C** | **−0.21** | **5.9%** | **0.00** |
| 25 °C | +0.08 | 5.1% | 0.50 |
| **26 °C** | **+0.38** | **8.1%** | **1.00** |
| 27 °C | +0.69 | 14.9% | 0.00 |
| 28 °C | +0.99 | 25.7% | 0.00 |

## 3. 两个结论（都有实测支撑）

1. **项目的舒适度指标与标准自相矛盾**：项目 `baseline` 的目标温度是 **24 °C**
   （`core/controller.py` 的 `SCHEDULE`），而 `calc_TCI(24.0, …)` 恰好等于 **0.00**（最差档）。
   同一工况下 ISO 7730 的 **PPD 只有 5.9%**，接近最优 —— 也就是说，**项目给"最舒适的温度"打了零分**。
   这不是"指标不够精细"，而是**指标方向反了**：`opt_temp=26.0 / delta_allow=2.0` 使 24 °C 落在可行区间之外。
2. **TCI 的最优点（26 °C）不是 PMV 的最优点（25 °C）**：26 °C 的 PPD 是 25 °C 的约 **1.6 倍**。
   即按 TCI 调参会把设定值推到"标准看来偏差更大"的一侧。

## 4. 不臆造参数前提下可给出的建议

- 若采用 PMV/PPD：按 ISO 7730，**PMV ∈ [−0.5, +0.5] 对应约 23–26.5 °C**（本参数组下实测），
  可把"舒适下限"定义为 PMV ≤ +0.5，而**不必**凭空改 `A_WALL/U_WALL/C_AIR` 等建筑参数。
- 设定值：若要单选一个点，**25 °C** 在本参数组下 PPD 最低（5.1%）。
- 对外表述：`docs/literature-review.md` 已声明"项目 49.3% 是仿真指标、不等同于 ASHRAE 55 符合率"；
  若改口径为 PMV/PPD，应写成"**PMV/PPD（ISO 7730，指定 met/clo/RH/v 假设）**"并列出上述假设，
  **不得**把 `met/clo` 等假设值写成实测值。

## 5. 与 Sinergym 基准的交叉核对（外部一致性）

评审建议"参考 Sinergym 的 `OfficesThermostat` 设定值/时间表做外部校准"。我用**稀疏克隆**只取配置与工具代码
（`git clone --depth 1 --filter=blob:none --sparse` 后 `sparse-checkout set sinergym/config sinergym/utils sinergym/envs`），
在其中找到**明文的舒适区与设定值**（Sinergym 是同行评审工作中广泛使用的 HVAC 强化学习基准）：

| 来源 | 位置 | 夏季舒适区 / 设定值 |
|---|---|---|
| Sinergym 环境注册表 | `sinergym/__init__.py:100-101` | `range_comfort_winter=(20.0, 23.5)`；**`range_comfort_summer=(23.0, 26.0)`** |
| Sinergym 规则控制器 | `sinergym/utils/controllers.py:44-45` | **`setpoints_summer=(23.0, 26.0)`**；`setpoints_winter=(20.0, 23.5)` |
| Sinergym 动作空间 | `sinergym/__init__.py:57-58` | 加热/制冷设定值上下界 `low=[15.0, 22.5]`、`high=[22.5, 30.0]` |
| 本文件 §2（ISO 7730 实算，PMV ∈ ±0.5） | 本仓库 | 约 **23 – 26.5 °C** |
| **本项目 `calc_TCI`（锚 26 ± 2）** | `energy_system/algorithms/comfort_eval.py` | **24 – 28 °C**（`TCI=0` 在 24 与 28） |

**结论**：两个**互相独立**的公开来源（ISO 7730 数值求解 / Sinergym 基准配置）把夏季舒适区都定在 **23–26 ℃** 一带；
而本项目的 TCI 可行带是 **24–28 ℃**，**整体偏暖约 1–1.5 ℃**，且它给 24 ℃ 打 0 分、给 28 ℃ 也打 0 分 ——
这与两个来源都不一致。

⇒ 若采用外部口径，建议把夏季舒适区定在 **23–26 ℃**（与两个来源一致），设定值可选 **25 ℃**（本参数组下 PPD 最低 5.1%）。
**注意**：这只涉及"舒适度口径与设定值"，**不涉及**建筑参数 `A_WALL/U_WALL/C_AIR` —— 后者仍无公开来源，保持不动。

## 6. 待用户决策（本文件不代做）

1. 是否把 `comfort_eval.calc_TCI` 换成（或并存）PMV/PPD？若换，`opt_temp/delta_allow` 的现行取值如何处理？
2. 是否把 `pythermalcomfort` 加入依赖？（建议放 `requirements-dashboard.txt` 之外的独立可选依赖，
   因为它会改变**系统对外宣称的舒适度口径**，不宜悄悄引入。）
3. 竞赛材料里若已按 TCI 口径写了舒适度数字，需要同步改写口径说明。
