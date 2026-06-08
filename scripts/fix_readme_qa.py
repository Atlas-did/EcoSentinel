from __future__ import annotations

from pathlib import Path


def main() -> None:
    readme_path = Path(__file__).resolve().parents[1] / "README.md"
    text = readme_path.read_text(encoding="utf-8")

    start = text.find("\n## 8.")
    if start == -1:
        # Fallback: maybe section starts at file start (unlikely)
        start = text.find("## 8.")
    if start == -1:
        raise SystemExit("Cannot find '## 8.' section in README.md")

    prefix = text[:start].rstrip() + "\n\n"

    qa = r"""
## 8. 评委常见追问（Q&A）

### Q1：你们的控制算法是什么？滞回保护怎么做？

- 控制算法：边缘端以“规则控制 + 状态机”为主。核心是按时段设定目标温度/照度阈值，然后根据传感器读数决定执行器开关。
- 滞回保护（Hysteresis / Deadband）：温控使用 $T_{set}\pm0.5^\circ C$ 的死区，避免在设定点附近来回抖动。
- 防频繁启停（Anti-Short-Cycle）：温控状态机同时约束“最小运行时间 15 分钟”和“最小停机时间 10 分钟”。对应实现见 `energy_system/core/controller.py` 的 `RuleBasedController.compute_action()`。
- 硬件执行侧再加一层“只在变化时下发”：`main.py` 的 `_apply_rule_control()` 只在继电器状态发生变化时才下发串口命令，减少抖动与刷屏。

### Q2：怎么保证“不频繁起停”，不是越控越耗电？

- 策略层：温控死区 + 最小启停时间（见 `RuleBasedController`）。
- 执行层：主循环只在状态变化时下发命令，并对下发频率做节流（见 `main.py` 的 `_apply_rule_control()`）。
- 证据链：继电器状态 `relays` 与关键时间序列都会写入采样日志，可在看板直接看到“开关次数/持续时间”。

### Q3：AI 挂了怎么办？会不会导致系统失控？

- 默认设计：AI 是“建议层”而不是“执行层”。在 `ai.control_mode: suggest` 下，AI 只提供 `ai_commands/ai_reasoning`，最终执行仍由规则与安全壳裁决。
- 自动降级：当没有 Key、网络异常或云端返回不可解析时，`energy_system/algorithms/ai_advisor.py` 会切换到本地降级策略（`ai_source=local`），并把错误写入 `ai_cloud_error`，系统仍能按规则稳定运行。
- 稳定性增强：AI 候选池带熔断/半开探测，某个候选连续失败会临时跳过，避免“坏节点拖死整个系统”。
- 可审计：每次 AI 选择了哪个候选、延迟/评分如何都会落盘（`ai_candidate_id/ai_latency_ms/ai_score/ai_tuning_event`），Dashboard 可聚合展示长期表现。

### Q4：怎么证明你们真的节能了？

- 量化口径：以电功率积分得到能量 $E(Wh)=\int P(W)\,dt$，运行时写入 `energy_wh`（可选写入 `solar_energy_wh`）。
- 对比方法：用相同工况/相近时长分别运行 `run_label=baseline` 与 `run_label=saving`，写入两份 `logs/hardware_<label>.jsonl`，Dashboard 自动对比能量与曲线。
- 节能率：$saving\_rate = (E_{baseline}-E_{saving})/E_{baseline}$。同时展示 `comfort_score`，证明节能不是靠“牺牲舒适度到不可用”。
""".lstrip()

    readme_path.write_text(prefix + qa, encoding="utf-8")
    print("README Q&A section fixed")


if __name__ == "__main__":
    main()
