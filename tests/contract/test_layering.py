"""G4 · 分层依赖门禁（refactor design §3.1）。

用**层级秩**表达方向：包只能依赖"更内层或同层"的包（秩更大或相等），
反向依赖一律失败。这样"core 反过来依赖 simulation"这类**包级循环**会被自动抓住，
而不需要维护一张易腐烂的允许清单。

已知且已登记的例外写在 TRACKED_EXCEPTIONS 里（每条都要给原因）；
测试同时断言例外**仍然存在** —— 修好之后必须删掉条目，否则门禁自己就会烂掉。
"""

import ast
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PROJECT_ROOT / "energy_system"

#: 秩越大越"内层"。外层可依赖内层；同秩允许（如 simulation ↔ algorithms 的横向协作）。
LAYER_RANK = {
    "cli": 0,
    "api": 1,
    "application": 2,
    "simulation": 3,
    "algorithms": 3,
    "ai": 4,
    "resilience": 4,
    "core": 5,
    "domain": 6,
    "persistence": 6,
    "power": 6,
    "hardware": 7,
    "experiments": 7,
    "config": 8,
    "utils": 9,
}

#: 组装根文件豁免：这些文件承担"装配"职责，**本来就必须**认识具体适配器
#: （SerialBridge / EnvironmentGenerator…）。按**文件**豁免比按包豁免精确得多：
#: application 包里的其它文件仍然完全禁止 import hardware。
#:
#: 当前为**空**：`application -> hardware` 经层级秩判定本就是向内依赖（hardware 是叶子），
#: 所以不需要任何豁免（此前那条"已登记例外"是空转 —— 旧的检查只看边是否存在，
#: 没看它是否真的违规；本文件的 test_composition_root_exemptions_are_still_needed 现在会守住这点）。
COMPOSITION_ROOT_FILES: dict[str, str] = {}


def _imported_energy_packages(path: Path) -> set[str]:
    """Return the energy_system sub-packages imported by one file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        modules: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        for module in modules:
            parts = module.split(".")
            if len(parts) >= 2 and parts[0] == "energy_system":
                found.add(parts[1])
    return found


def _package_edges() -> dict[tuple[str, str], set[str]]:
    """Map (source package, target package) → files that create the edge."""
    edges: dict[tuple[str, str], set[str]] = {}
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        parts = path.relative_to(PACKAGE_ROOT).parts
        if len(parts) < 2 or "__pycache__" in parts:
            continue
        source = parts[0]
        for target in _imported_energy_packages(path):
            if target == source or target not in LAYER_RANK:
                continue
            edges.setdefault((source, target), set()).add(str(path.relative_to(PROJECT_ROOT)))
    return edges


class TestLayering(unittest.TestCase):
    def test_no_inward_package_depends_on_an_outer_package(self):
        violations = []
        for (source, target), files in sorted(_package_edges().items()):
            if LAYER_RANK[target] >= LAYER_RANK[source]:
                continue  # 向内或同层：允许
            if files <= set(COMPOSITION_ROOT_FILES):
                continue  # 该反向边的**每一处**都来自组装根文件 ⇒ 正当
            violations.append(
                "{} -> {} (秩 {} -> {}): {}".format(
                    source, target, LAYER_RANK[source], LAYER_RANK[target], ", ".join(sorted(files))
                )
            )
        self.assertEqual(
            violations,
            [],
            "发现反向依赖（内层依赖了外层）：\n  " + "\n  ".join(violations),
        )

    def test_core_does_not_depend_on_simulation(self):
        """曾经的包级循环 core -> simulation -> core（用函数内延迟导入绕过）。"""
        self.assertNotIn(
            ("core", "simulation"),
            _package_edges(),
            "core 又依赖 simulation 了：合成数据源应由组装根注入（见 data_acquisition.mock_generator）",
        )

    def test_leaf_packages_stay_leaves(self):
        """这些包不该 import 任何其它 energy_system 包（它们是纯叶子）。"""
        leaves = {"utils", "hardware", "persistence", "power", "experiments"}
        offenders = sorted(
            "{} -> {}".format(source, target)
            for (source, target) in _package_edges()
            if source in leaves
        )
        self.assertEqual(offenders, [], "叶子包出现了依赖：" + ", ".join(offenders))

    def test_composition_root_exemptions_are_still_needed(self):
        """豁免必须仍然"在干活"：若某个豁免文件已不再产生反向边，就该删掉条目。"""
        edges = _package_edges()
        used = set()
        for (source, target), files in edges.items():
            if LAYER_RANK[target] < LAYER_RANK[source]:
                used |= files & set(COMPOSITION_ROOT_FILES)
        stale = sorted(set(COMPOSITION_ROOT_FILES) - used)
        self.assertEqual(stale, [], "以下组装根豁免已不再需要，请从 COMPOSITION_ROOT_FILES 删除：{}".format(stale))

    def test_exemptions_do_not_leak_to_other_files(self):
        """反向边只有**全部**来源都是组装根时才放过；否则必须报违规。"""
        for (source, target), files in _package_edges().items():
            if LAYER_RANK[target] >= LAYER_RANK[source]:
                continue
            exempt = files & set(COMPOSITION_ROOT_FILES)
            if exempt and exempt != files:
                self.fail(
                    "{} -> {} 的违规来源里混入了非组装根文件：{}".format(
                        source, target, ", ".join(sorted(files - exempt))
                    )
                )

    def test_every_package_is_ranked(self):
        """新增包必须显式登记层级，否则门禁对它视而不见。"""
        present = {
            p.name
            for p in PACKAGE_ROOT.iterdir()
            if p.is_dir() and p.name != "__pycache__" and any(p.rglob("*.py"))
        }
        unranked = sorted(present - set(LAYER_RANK))
        self.assertEqual(unranked, [], "未登记层级的包：" + ", ".join(unranked))


if __name__ == "__main__":
    unittest.main()
