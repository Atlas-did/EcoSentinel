"""Contract tests for the FastAPI read-only endpoints and CORS posture.

These run against the real app object (no hardware) and assert response shapes so
the React/Streamlit frontends and the backend stay in sync.
"""

import unittest

from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

import api_server
from api_server import app, cfg


class TestApiSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_ping(self):
        r = self.client.get("/api/ping")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIs(body["ok"], True)
        self.assertIn("time", body)

    def test_snapshot_shape(self):
        r = self.client.get("/api/snapshot")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("timestamp", body)
        self.assertIn("errors", body)

    def test_energy_summary_shape(self):
        r = self.client.get("/api/energy-summary")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        for key in ("baseline_kwh", "saving_kwh", "saving_rate",
                    "cost_saved_cny", "carbon_reduced_kg"):
            self.assertIn(key, body)

    def test_health_shape(self):
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("sampling_rate_hz", body)
        self.assertIn("sensors_online", body)
        self.assertIn("self_healing_enabled", body)

    def test_simulation_params_shape(self):
        r = self.client.get("/api/simulation/params")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("days", body)
        self.assertIn("enable_ai", body)

    def test_chart_returns_list(self):
        r = self.client.get("/api/chart", params={"range": "5m"})
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json(), list)


class TestCorsPosture(unittest.TestCase):
    def _cors_options(self):
        for m in app.user_middleware:
            if m.cls is CORSMiddleware:
                return m.kwargs
        self.fail("CORSMiddleware not found")

    def test_no_wildcard_origin_with_credentials(self):
        opts = self._cors_options()
        self.assertFalse(opts.get("allow_credentials", False) or "*" in opts.get("allow_origins", []))

    def test_config_default_is_local_dev_only(self):
        # The default config must not allow arbitrary origins in production.
        self.assertNotIn("*", cfg.api.cors_origins)
        self.assertFalse(cfg.api.allow_credentials)


if __name__ == "__main__":
    unittest.main()
