# 第三方审计应答表（逐条 → 状态 / 证据 / 门禁）

> 面向复测：本表按《EcoSentinel 技术评审与演进路线图》之外的**队友实测审计**逐条应答。
> 每条给出**可复核的证据**（文件 + 门禁 + 变异验证 + 提交号），并**明确写出我没做的项与理由**。
> 纪律：报告里只在 CI **四个 job 全部 completed=success** 后才写"全绿"，否则写"在跑/待核"。

## 1. 逐条应答

| # | 审计条目 | 我的核实 | 状态 | 证据（文件/门禁/提交） | 变异验证 |
|---|---|---|---|---|---|
| 1 | **P1 · G2 缺失**：无测试钉住仿真数字 | ✅ 成立（全仓检索只有 3 处命中，均非断言：键名检查 / 注释文字 / mock 的 30.0） | ✅ **已修** | `tests/contract/test_simulation_baseline.py`（7 个 golden + 自洽交叉校验），提交 `bacda10` | ✅ 用**审计自己的实验** `opt_temp 26→27` ⇒ 点名报红（`期望 0.493±0.002，实得 0.508`，与其观测 49.3%→50.8% 一致） |
| 2 | **P1 · §7-3 涟漪没降** | ✅ 成立（审计口径 28 文件；本仓更宽口径 48 文件，均远超 3） | ✅ **已改表述 + 撤回宣称** | `docs/refactor-design-v1.md` §7 第 3 条、L232 更正块 | —（文档项，无需门禁；已写明实测口径与两个数字） |
| 3 | **P1 · §7-5 `os.getenv` 未清零** | ⚠️ **精确核实**：`utils/env_loader.py` 那处是**文档字符串里的说明文字**，**不是真实调用** ⇒ 代码不变量本就成立；审计的 grep 把注释算进去了 | ✅ **转化为精确门禁** | `tests/contract/test_config_env_boundary.py`（AST 剥文档字符串+注释后，要求 env 读取只在 `config/`），提交 `a91d82c` | ✅ **抓到我自己门禁的洞**：原正则写死 `os.getenv`，被 `import os as _p; _p.getenv()` **别名绕过**；改为匹配任意 `.getenv(`/`.environ` 后如期报红 `{'energy_system/utils/helpers.py': 1}` |
| 4 | **P2 · M1 只覆盖 9 包 + 正则盲区** | ✅ 成立（缺 `resilience/hardware/persistence/power`；正则只抓字面量、抓不到裸标识符） | ✅ **已补齐 + 写明盲区** | `tests/contract/test_metrics_registry.py` 的 `SCAN_PACKAGES` 与新增注释块，提交 `a91d82c` | ✅ 往 `hardware/serial_bridge.py` 注入 `'tempreature'` ⇒ 点名报红（证明新包确实被扫描） |
| 5 | **P2 · ⑦ 参数标定/学习"完全没做"** | ⚠️ **部分成立**：研究**已做并入库**（`docs/pmv-ppd-study.md`、`docs/reference-repos-study.md`，提交 `8d62c67`/`cbc9012`，且 `handoff.md` 明写"参数未标定"）；**参数标定确实未做** | 🔒 **等你同学几天的实测数据** | 口径与验收脚本已就绪（`scripts/firmware_acceptance.py` + PMV/PPD 实测表）；**绝不臆造数字** | —（等数据；届时用实测序列拟合 R/C，并补 golden） |
| 6 | **P3 · "全绿"积压** | ✅ 成立（多轮报告曾挂"在跑/待核"却在同段写"全绿"） | ✅ **已改纪律** | 本表顶部的纪律声明；`docs/handoff.md` 同步 | —（流程项） |
| 7 | **P3 · knip 零豁免但配置在别处** | ✅ 成立（无 `knip.json`；`app/package.json` 里也**没有** `knip` 段 ⇒ knip 跑默认规则） | ⏸ **决定不新建 `knip.json`**，改为文档化 | 理由：**任何** `knip.json` 都会**覆盖默认值**，可能把"零豁免"悄悄削弱/掏空 ⇒ 不接受"为可读性改坏门禁"；如要做，先用 `knip --include` 等方法逐条比对生效规则再落盘 | —（决策项） |

## 2. 审计做的 8 处变异（我接受，且都不是我自封的）

G3 把 AI 搬回主线程 · G3 关掉过期丢弃 · G5 同一命令两种分发 · G4 叶子包外扩依赖 ·
M3 在 `config` 外读 env · M1 读取点笔误 · M1 未登记指标 · G8 页面内联阈值 —— 全部报红 ✓。
这些门禁此后仍由 CI 常驻（每次 push 都跑）。

## 3. 审计范围之外、但与之同源的补充（供复测时一并看）

- **IPMVP Option C / ASO 交替实验**（审计"建议 #1"的下一步、评审 §6.4）：已实现
  `energy_system/simulation/aso_experiment.py` + 门禁 `tests/contract/test_aso_experiment.py`（提交 `7ea9d96`/`fd7c2dd`）。
- **两个估计量必须分开写**：配对差值 **17.6%**（`compare`）与 Option C **19.12% ± 4.21 kWh(95%)**（ASO，6 天）
  **不可混用或取平均**；口径对照表见 `docs/refactor-baseline.md` §3bis。

## 4. 仍然挂账、需要用户拍板的决策（4 项）

1. 对外材料里的 **29.8%** ⇒ 改 **17.6% + 口径说明**（仓库内文档已改完，用户手上的 PDF/PPT 未动）；
2. **CI 物理回归设为 required**（GitHub 分支保护设置，需管理员）；
3. **舒适度口径**是否由 TCI 改为 **PMV/PPD（ISO 7730，公开 met/clo/RH/v 假设）**；建议夏季 23–26 ℃；
4. **节能率主口径**用配对 17.6% 还是 Option C 19.12%（或两者并列、各带方法）。
