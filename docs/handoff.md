# 交接说明（队友 / AI 代理）

> 最后更新：2026-10-06 · 对应提交 `main`（本文随代码走，数字以 `python -m pytest tests -q` 实测为准）

## 1. 队友五分钟自证（不需要硬件、不需要 API key）

```bash
git clone https://github.com/Atlas-did/EcoSentinel.git && cd EcoSentinel
python -m venv .venv && . .venv/Scripts/activate        # Linux/macOS: . .venv/bin/activate
pip install -r requirements.txt                          # 核心依赖就够了
python -m pytest tests -q                                # 期望：251 passed
python -m energy_system.simulation.compare               # 期望：退出码 0
python scripts/stack_acceptance.py                       # 期望：PASS（7/7 只读端点）
```

前端（可选，但三道门禁都要过）：

```bash
cd app && npm ci && npm run lint && npm run knip && npm test && npm run build
```

想连真后端看界面时：`python api_server.py --port 8080` + `cd app && npm run dev`
（前端 dev server 在 **3000**，其 `/api` 代理指向 8080；CORS 白名单已同步 3000，见
`tests/contract/test_dev_port_contract.py`）。

## 2. 当前状态（做完了什么）

| 分片 | 内容 | 状态 |
|---|---|---|
| ① 物理层 | 热模型显式欧拉（发散）→ **解析指数积分**；5 条数学性质断言先红后绿 | ✅ |
| ② 数字 | 节能率按真实重算 **29.8% → 17.6%**；README/文献综述/基线表全部更正并标注"演示级参数、非实测" | ✅ |
| ③ 数据源 | mock 改**本地小时**（原 UTC 差 8h）、室内温度按内热稳态温差推导、补 `bus_v/current_ma/pwr_mw` 使 `energy_wh` 可累积 | ✅ |
| ④ 计量 | 当日电量**跨重启累加** + 原子写（tmp+replace）；`ai_worker.stats` 进 `/api/health` | ✅ |
| ⑤ 前端去假 | 评审抓到的 3 个真 bug（`temp↔temperature`、累计曲线绑定、功率→电量系数 1000×）+ 假日志/假端口状态/**不存在的风扇硬件**/固定模式字样/除零 NaN/轮询统一 | ✅ |
| ⑥ 工程化 | CORS 端口对齐（3000）+ 跨文件门禁；依赖拆分 `requirements-dashboard.txt`；CI 4 job 全绿 | ✅ |
| ⑦ 学习 | `pythermalcomfort` 实算 PMV/PPD（见 `docs/pmv-ppd-study.md`）；Sinergym 待做 | 🔄 |

**验收口径**：Python **251 passed**、前端 **56 passed** + lint/knip/build 全绿、CI **4/4**、
仿真对比可复现。所有新门禁都做过**变异验证**（改坏实现必须变红）。

## 3. 明确**没做**的事（不要以为是遗漏）

1. **真机验证**：没有 ESP32-S3 实机 ⇒ 上板验收（`scripts/firmware_acceptance.py`）与实测节能量均未做；
   固件"能编译"由 CI 的 `arduino-cli compile` 保证，**不等于**上板跑通。
2. **建筑参数未标定**：`A_WALL/U_WALL/C_AIR` 仍是演示级取值 ⇒ 17.6% 只能作**内部一致性**参考，
   不可与文献实测值同表比较（`docs/refactor-baseline.md` 已注明）。
3. **`EnergyAccumulator` 自身内存状态**仍是进程级：跨重启累加只解决"当日累计被清零"的后果，
   未落盘的瞬时累计不会恢复。
4. **舒适度口径未改**：`comfort_eval.calc_TCI` 原样保留（PMV/PPD 只做了核对与记录）。

## 4. 需要人拍板的三件事（代理不要自行决定）

1. **对外数字**：竞赛材料若已印 29.8%，需改为 **17.6% + 口径说明**（仓库内文档已全部改完）。
2. **CI 物理回归设为 required**：属 GitHub 分支保护设置，需仓库管理员点选。
3. **舒适度口径**：是否把 TCI 换成 PMV/PPD（ISO 7730，需同时公开 `met/clo/RH/v` 假设），
   以及 `opt_temp/delta_allow` 如何处理。

## 5. 代理工作约定（摘要，详见 `AGENTS.md`）

- **判据一律以退出码为准**，不以日志文字为准。
- 改任何门禁都要做**变异验证**：把实现改坏必须让它变红；且必须**自证变异已生效**
  （打印"注入是否发生"）—— 本项目已三次因 CRLF/LF 或冗余防线导致"变异没生效"。
- **不臆造参数**：物理参数没有公开来源时，只改注释与口径，不改数值，并把决策列给用户。
