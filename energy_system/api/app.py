"""FastAPI app factory.

Builds the read-only monitoring API on top of :class:`ApiServices` and a
:class:`JsonlTelemetryRepository`. Keeping this in a factory (instead of a
module-level ``app``) makes it testable in isolation and lets callers inject a
temp log directory or an explicit CORS origin list.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from energy_system.api.services import ApiServices
from energy_system.config.config_loader import load_app_config
from energy_system.persistence.jsonl_repository import JsonlTelemetryRepository


def create_app(
    cfg=None,
    log_dir: str | Path | None = None,
    cors_origins: list[str] | None = None,
    allow_credentials: bool | None = None,
    ai_worker_stats=None,
) -> FastAPI:
    """Create the EcoSentinel API application.

    All arguments are optional; by default the app reads config from the
    standard loader and the ``logs/`` directory, matching ``python api_server.py``.
    """
    if cfg is None:
        cfg, _warnings = load_app_config()

    if log_dir is None:
        log_dir = Path(__file__).resolve().parent.parent.parent / "logs"

    repository = JsonlTelemetryRepository(log_dir, run_label=cfg.run_label or "saving")
    services = ApiServices(repository, cfg)

    app = FastAPI(
        title="EcoSentinel API",
        version="2.0.0",
        description="Backend API for EcoSentinel — Smart Environmental Monitoring & AI Energy-Saving System",
    )

    origins = cors_origins if cors_origins is not None else list(cfg.api.cors_origins)
    credentials = (
        allow_credentials if allow_credentials is not None else bool(cfg.api.allow_credentials)
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/ping")
    def ping():
        return {"ok": True, "time": datetime.now().isoformat()}

    @app.get("/api/snapshot")
    def get_snapshot(label: str | None = None):
        return services.snapshot(label)

    @app.get("/api/chart")
    def get_chart(range: str = Query("1h", alias="range"), label: str | None = None):
        return services.chart(range, label)

    @app.get("/api/ai-candidates")
    def get_ai_candidates(label: str | None = None):
        return services.ai_candidates(label)

    @app.get("/api/resilience")
    def get_resilience(label: str | None = None):
        return services.resilience(label)

    @app.get("/api/energy-summary")
    def get_energy_summary(label: str | None = None):
        return services.energy_summary(label)

    @app.get("/api/health")
    def get_health(label: str | None = None):
        payload = services.health(label)
        # 评审 P1：把 AI 工作线程计数一并暴露，便于回答"建议为什么没被采纳"
        # （例如 AI_ADVICE_MAX_AGE_S 偏小 ⇒ 建议成批过期丢弃）。
        # 注入口可选：未接线时该字段保持为 null，不伪造任何数字。
        if ai_worker_stats is not None:
            try:
                stats = ai_worker_stats()
            except Exception:
                stats = None
            if isinstance(stats, dict):
                payload = payload.model_copy(update={"ai_worker": stats})
        return payload

    @app.get("/api/simulation/params")
    def get_simulation_params():
        return services.simulation_params()

    return app
