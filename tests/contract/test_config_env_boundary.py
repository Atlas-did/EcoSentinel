"""配置边界门禁：环境变量读取只允许发生在 `config/`（审计第 5 条）。

审计原话是"`grep os.getenv` 只命中 `config/`……但 `utils/env_loader.py` 仍有 1 处"。
**核实后的精确情况**：那 1 处是**文档字符串里的说明文字**（
"mutate ``os.environ``; applying values to the process environment is the job of ..."），
**不是真实调用** —— 也就是说代码层面的不变量**已经成立**，审计的 grep 把注释算进去了。

本项目此前已被"注释/文档里的字面量绊倒门禁"坑过四次（固件注释、AGENTS.md 说明文字等），
所以这里把规则写**精确**：

1. 剥掉注释与文档字符串后，`energy_system/**` 里 `os.getenv` / `os.environ` 只允许出现在 `config/`；
2. `utils/env_loader.py` 必须是**纯函数**（解析文本、不碰进程环境）。

这样"env 只在 config 读"这条不变量既有门禁、又不会被注释误伤。
"""

import ast
import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


#: 匹配**任何** `.getenv(` / `.environ`，不写死 `os.` 前缀 —— 否则
#: `import os as _probe; _probe.getenv(...)` 这类**别名导入**能绕过门禁
#: （这是本门禁第一版的真实缺陷，被"自证生效的变异"当场抓到）。
ENV_ACCESS = re.compile(r"\.getenv\s*\(|\.environ\b")


def _strip_comments_and_docstrings(source: str, path: Path) -> str:
    """先按 AST 去掉文档字符串，再去掉 `#` 行注释（AST 失败则退回纯正则）。"""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return re.sub(r"#[^\n]*", "", source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                node.body = body[1:]
    try:
        unparsed = ast.unparse(tree)
    except Exception:  # noqa: BLE001 —— 退回正则，宁可粗暴也不要漏
        return re.sub(r"#[^\n]*", "", source)
    return re.sub(r"#[^\n]*", "", unparsed)


class TestEnvReadsStayInConfig(unittest.TestCase):
    def _env_readers(self) -> dict[str, int]:
        found: dict[str, int] = {}
        for path in sorted((PROJECT_ROOT / "energy_system").rglob("*.py")):
            code = _strip_comments_and_docstrings(path.read_text(encoding="utf-8"), path)
            hits = len(ENV_ACCESS.findall(code))
            if hits:
                found[str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")] = hits
        return found

    def test_only_config_reads_the_environment(self):
        readers = self._env_readers()
        offenders = {p: n for p, n in readers.items() if not p.startswith("energy_system/config/")}
        self.assertEqual(
            offenders,
            {},
            "环境变量读取只应发生在 config/ 下，实际还出现在：" + str(offenders),
        )
        self.assertTrue(readers, "config/ 里应当至少有 env.py 在读环境变量（否则这条门禁是空转）")

    def test_env_loader_stays_a_pure_parser(self):
        text = (PROJECT_ROOT / "energy_system/utils/env_loader.py").read_text(encoding="utf-8")
        code = _strip_comments_and_docstrings(text, PROJECT_ROOT / "energy_system/utils/env_loader.py")
        self.assertNotIn("os.environ", code, "env_loader 必须是纯解析器，不得改进程环境")
        self.assertEqual(
            ENV_ACCESS.findall(code), [], "env_loader 必须是纯解析器，不得读进程环境（含别名导入）"
        )


if __name__ == "__main__":
    unittest.main()
