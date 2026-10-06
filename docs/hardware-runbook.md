# 上板实测 runbook（给去测试的同学）

> 目的：拿到**可用于参数辨识**的实测数据，并把固件"上板验收"一次做完。
> 关联：`scripts/firmware_acceptance.py`（验收，退出码判据）、`scripts/identify_rc.py`（参数辨识）、
> `docs/hardware-guide.md`（接线）、`AGENTS.md` §3（固件命令与验收令牌）。
> 原则：**数据没到手之前不许编数字**；辨识值是否采用由人拍板（脚本不会自动改配置）。

## 0. ⚠️ 首要前置：我们**缺一个室外温度**

固件现有传感链路（`firmware/esp32_s3_competition/config.h`）是 **DHT（温湿度）+ SGP30（eCO2/TVOC）
+ BH1750（光照）+ INA219×2（电参量）** —— **没有室外温度** ✗。
而 1R1C 辨识的方程 `C·dT/dt = UA·(T_out − T_in) + Q` **必须有 `T_out`**：`UA` 恰恰是"室内外温差 → 传热"的系数。

可选方案（按推荐排序）：

1. **加一个室外 DHT22**（最干净）：走另一路 GPIO，随固件一起记录；两次测量同步打时间戳；
2. **用当地气象数据**（次选）：按 `time_s` 对齐到最近的整点气温，并在报告里写明"室外温度为气象再分析值"；
3. ❌ **不要**用仿真的天气生成器充当 `T_out` —— 那会让辨识**自我循环**（用仿真拟合仿真），结论无效。

## 1. 上板验收（先跑这个，5 分钟）

```bash
pip install -r requirements.txt
python scripts/firmware_acceptance.py --port COM4                                  # 默认要求 bh1750
python scripts/firmware_acceptance.py --port COM4 --require bh1750,relay --active   # 再验命令通道
python scripts/hardware_autodiag.py --port COM4 --baud 115200                       # 人看得懂的诊断
```

退出码即判据：`0` PASS / `1` NO_TOKEN / `2` SUBSYSTEM / `3` PORT / `4` BAD_INPUT。
固件自检令牌：`{"selftest":"pass","token":"ECO_SELFTEST_PASS",...}`（`protocol.h` 的 `printSelfTest()`）。

**安全**：`--active` 会真的操作继电器/蜂鸣器/窗帘；**不要**在带电负载无人看管时跑 ✗。

## 2. 采集辨识数据（关键：记录约定 + 采样率）

**采样率**：辨识 `C` 需要**暂态**，采样步长必须 **< 0.1τ**。
- 按当前**未标定**的演示级参数算 `τ = C/UA = 25000/1800 ≈ 13.9 s` ⇒ 需要**秒级采样**（建议 1 Hz）；
- 真实建筑 `τ` 通常以小时计 ⇒ 那时 300 s 也够。
- ⚠️ "仿真 τ 只有 14 s"本身就是**参数不合理**的证据（真实房间不会十几秒就热平衡）——这也是要标定的原因。

**激励**：至少覆盖 2–4 小时的**阶跃**（空调/继电器/窗帘开关若干次），否则 `Q` 与 `(T_out−T_in)` 共线、
`C` 不可辨识（`identify_rc.py` 会**拒答**，这是设计如此）。

**CSV 格式与记录约定**（每行 = `t` 时刻状态 + 区间 `[t, t+dt)` 内**生效**的 `T_out`/`Q`）：

```csv
time_s,T_in,T_out,Q_w
0,24.31,31.8,1200
1,24.30,31.8,1200
...
```

- `T_in`：室内温度（DHT）；`T_out`：室外（见 §0）；
- `Q_w`：**该区间内送入/移出房间的热量**（W）——空调制冷时取负、制热取正；无空调/未接入时填 `0`
  （此时只可能辨识 `UA`，脚本会提示）。

**从应用日志转 CSV**：`logs/hardware_<label>.jsonl` 里可直取 `timestamp` 与 `temperature`（→ `T_in`）✓；
但 `power_w` 是**总功率**、不是空调热功率，且日志**没有分列的空调功率** ✗ ⇒ 若要辨识 `Q` 项，
需要先让应用**单独记录空调功率**（属代码改动，应由人决定后做）。暂时可先用 `Q_w=0` + 天然温差激励。

## 3. 数据到手后（我这边会做，不建议你手动改参数）

```bash
python scripts/identify_rc.py --input data.csv            # 看 UA / C / τ / R² / rho
python scripts/identify_rc.py --selftest                  # 先自检（验代数）
```

判定链：`R²` 与 `rho` 合理 → **用户拍板是否采用** → 更新 `config/settings.py` → 同步
`tests/contract/test_simulation_baseline.py` 的 golden、README 口径、`docs/refactor-baseline.md`。
在此之前，对外只能写"参数为演示级未标定值"。

## 4. 采不到室外温度时的降级路径（诚实的选择）

只辨识 `UA`（把 `C` 保持现值并在文档里标注"未辨识"）：`Q_w=0`、利用天然昼夜温差，
`identify_rc.py` 会给出 `UA` 与 `rho`；此时**不要把 `C` 的结果写进配置** ✗。
