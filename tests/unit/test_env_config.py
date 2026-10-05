"""M3 · 环境访问收敛：只有 energy_system/config/env.py 可以碰进程环境。

覆盖两件事：
1) 门面本身的行为（.env 解析语义、别名优先级、默认值、坏值回退、CORS 覆盖）；
2) **结构门禁**（refactor design §3.1 规则 4）：用 AST 扫描仓库，确认除 config/env.py
   之外没有任何模块读写 os.environ / os.getenv。AST 而非文本匹配，因此注释与文档里
   提到这些名字不会误报。
"""

import ast
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from energy_system.config import env as cfg_env
from energy_system.utils.env_loader import parse_dotenv_text, read_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = ["energy_system", "scripts", "main.py", "api_server.py", "dashboard.py"]
ALLOWED = (PROJECT_ROOT / "energy_system" / "config" / "env.py").resolve()
ENV_ATTRS = {"getenv", "environ", "putenv"}


class TestDotenvParsing(unittest.TestCase):
    def test_parses_values_comments_bom_and_quotes(self):
        text = (
            "\ufeffDEEPSEEK_API_KEY=sk-abc\n"
            "# comment\n"
            "// also comment\n"
            "\n"
            'QUOTED="  spaced  "\n'
            "SINGLE='x=1'\n"
            "EMPTY=\n"
            "NOEQUALS\n"
        )
        values = parse_dotenv_text(text)
        self.assertEqual(values["DEEPSEEK_API_KEY"], "sk-abc")
        # 引号只被剥掉，内部的空格是**有意保留**的（与 M3 之前的解析器语义一致）
        self.assertEqual(values["QUOTED"], "  spaced  ")
        self.assertEqual(values["SINGLE"], "x=1")
        self.assertNotIn("EMPTY", values, "空值不应写入")
        self.assertNotIn("NOEQUALS", values)

    def test_first_definition_wins_within_a_file(self):
        self.assertEqual(parse_dotenv_text("K=1\nK=2\n")["K"], "1")

    def test_missing_file_is_empty_and_never_raises(self):
        self.assertEqual(read_dotenv(PROJECT_ROOT / "no-such-file.env"), {})


class TestEnvFacade(unittest.TestCase):
    def test_apply_dotenv_does_not_overwrite_existing(self):
        with patch.dict(os.environ, {"KEEP": "original"}, clear=True):
            loaded = cfg_env.apply_dotenv(str(PROJECT_ROOT / "no-such-file.env"))
            self.assertEqual(loaded, {})
            self.assertEqual(os.environ["KEEP"], "original")

    def test_ai_api_key_precedence_and_empty(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(cfg_env.ai_api_key(), "")
            self.assertFalse(cfg_env.has_ai_api_key())

            os.environ["AI_API_KEY"] = " third "
            self.assertEqual(cfg_env.ai_api_key(), "third")

            os.environ["OPENAI_API_KEY"] = "second"
            self.assertEqual(cfg_env.ai_api_key(), "second")

            os.environ["DEEPSEEK_API_KEY"] = "first"
            self.assertEqual(cfg_env.ai_api_key(), "first", "DEEPSEEK 优先级最高")
            self.assertTrue(cfg_env.has_ai_api_key())

    def test_blank_values_do_not_count_as_a_key(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "   "}, clear=True):
            self.assertEqual(cfg_env.ai_api_key(), "", "全空白视为未配置")

    def test_battery_defaults_and_overrides(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(cfg_env.battery_capacity_mah(), 10000.0)
            self.assertEqual(cfg_env.battery_initial_soc(), 80.0)
        with patch.dict(os.environ, {"BATTERY_CAPACITY_MAH": "5000", "BATTERY_INITIAL_SOC": "42.5"}):
            self.assertEqual(cfg_env.battery_capacity_mah(), 5000.0)
            self.assertEqual(cfg_env.battery_initial_soc(), 42.5)

    def test_bad_numeric_value_falls_back_with_a_warning(self):
        with patch.dict(os.environ, {"BATTERY_CAPACITY_MAH": "ten thousand"}, clear=True):
            with self.assertLogs("ConfigEnv", level="WARNING") as logs:
                self.assertEqual(cfg_env.battery_capacity_mah(), 10000.0)
            self.assertIn("not a number", "\n".join(logs.output))

    def test_cors_override_parsing(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(cfg_env.cors_origins_override(), [])
        with patch.dict(os.environ, {"ECOSENTINEL_CORS_ORIGINS": "http://a , http://b,"}):
            self.assertEqual(cfg_env.cors_origins_override(), ["http://a", "http://b"])

    def test_env_value_strips(self):
        with patch.dict(os.environ, {"SOME_VAR": "  v  "}, clear=True):
            self.assertEqual(cfg_env.env_value("SOME_VAR"), "v")
            self.assertEqual(cfg_env.env_value("MISSING", "d"), "d")


class TestOnlyConfigTouchesTheEnvironment(unittest.TestCase):
    """结构门禁：用 AST 找 os.getenv / os.environ 的真实用法（注释与文档不算）。"""

    def _offenders(self):
        found = []
        files = []
        for root in SCAN_ROOTS:
            p = PROJECT_ROOT / root
            if p.is_dir():
                files.extend(sorted(p.rglob("*.py")))
            elif p.is_file():
                files.append(p)
        for f in files:
            if "__pycache__" in f.parts or f.resolve() == ALLOWED:
                continue
            try:
                tree = ast.parse(f.read_text(encoding="utf-8"))
            except SyntaxError:  # 语法错误由别处负责报告
                continue
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "os"
                    and node.attr in ENV_ATTRS
                ):
                    found.append("{}:{}".format(f.relative_to(PROJECT_ROOT), node.lineno))
        return found

    def test_no_module_outside_config_reads_the_environment(self):
        offenders = self._offenders()
        self.assertEqual(
            offenders,
            [],
            "以下位置直接读了进程环境，应改为调用 energy_system.config.env 的门面："
            + ", ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
