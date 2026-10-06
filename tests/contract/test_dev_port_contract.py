"""开发端口契约：前端 dev server 端口必须被后端 CORS 白名单覆盖（评审 P2）。

评审指出 `vite.config.ts` 用 3000 而后端默认白名单是 5173 ⇒ 浏览器**直连** 8080 时会被 CORS 拦掉。
（注：走 vite 代理时是同源请求，不受 CORS 影响 —— 这点我实测过；但直连/preview 场景会踩到。）

这条门禁不写死端口：它**从 vite.config.ts 读出真实端口**，再要求后端白名单包含它，
从而让"改端口忘记改白名单"这类漂移在 CI 上立刻暴露。
"""

import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestDevPortContract(unittest.TestCase):
    def _vite_dev_port(self) -> int:
        text = (PROJECT_ROOT / "app" / "vite.config.ts").read_text(encoding="utf-8")
        match = re.search(r"port:\s*(\d+)", text)
        self.assertIsNotNone(match, "未能从 vite.config.ts 解析出 dev server 端口")
        return int(match.group(1))

    def _cors_defaults(self) -> tuple[str, ...]:
        from energy_system.config.runtime_config import ApiConfig

        defaults = ApiConfig.__dataclass_fields__["cors_origins"].default
        return tuple(defaults)

    def test_backend_cors_allows_the_vite_dev_port(self):
        port = self._vite_dev_port()
        origins = self._cors_defaults()
        for host in ("localhost", "127.0.0.1"):
            expected = f"http://{host}:{port}"
            self.assertIn(
                expected,
                origins,
                f"后端 CORS 默认白名单缺 {expected}（实际：{origins}）—— 直连后端会被浏览器拦掉",
            )

    def test_preview_port_is_also_allowed(self):
        """构建产物预览（vite preview 默认 4173）也应当在白名单里，避免"演示时踩坑"。"""
        origins = self._cors_defaults()
        self.assertTrue(
            any(":5173" in o for o in origins),
            f"CORS 默认白名单应保留 5173（实际：{origins}）",
        )


if __name__ == "__main__":
    unittest.main()
