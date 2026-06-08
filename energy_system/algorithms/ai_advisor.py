from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass
from typing import Any

from energy_system.config.runtime_config import AIConfig, AIRequestCandidate

@dataclass
class _CandidateStats:
    n: int = 0
    ema_score: float = 0.0
    success: int = 0
    fail: int = 0
    consecutive_fail: int = 0
    circuit_open_until: float = 0.0  # monotonic timestamp
    circuit_open_count: int = 0


def _now_s() -> float:
    return time.monotonic()


class AIAdvisor:
    def __init__(
        self,
        api_key: str,
        ai_config: AIConfig,
    ):
        self.api_key = api_key
        self.cfg = ai_config
        self.logger = logging.getLogger("AIAdvisor")

        self._stats: dict[str, _CandidateStats] = {}
        self._last_candidate_id: str | None = None

        self._openai = None
        self.client = None
        if not (api_key or "").strip():
            # Allow local fallback to work even without API key.
            self._openai = None
            self.client = None
            return

        try:
            import openai  # type: ignore

            self._openai = openai
            # Create a default client; per-candidate override may create a temporary client.
            self.client = openai.OpenAI(api_key=api_key, base_url=ai_config.api_base)
        except Exception as e:
            self._openai = None
            self.client = None
            self.logger.error(f"AIAdvisor disabled (openai not available): {e}")

    def _score_sample(self, sensor_data: dict[str, Any]) -> float | None:
        comfort = sensor_data.get("comfort_score")
        power_w = sensor_data.get("power_w")
        if not isinstance(comfort, (int, float)):
            return None
        comfort_f = float(comfort)
        # Normalize power to [0,1] using a conservative ceiling.
        if isinstance(power_w, (int, float)) and float(power_w) >= 0:
            p = min(float(power_w) / 5000.0, 1.0)
        else:
            p = 0.0
        # Higher is better.
        return comfort_f - 0.3 * p

    @staticmethod
    def _sanitize_prompt_value(value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, list):
            return [AIAdvisor._sanitize_prompt_value(v) for v in value[:32]]
        if isinstance(value, tuple):
            return [AIAdvisor._sanitize_prompt_value(v) for v in list(value)[:32]]
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            for k, v in list(value.items())[:32]:
                out[str(k)] = AIAdvisor._sanitize_prompt_value(v)
            return out
        return str(value)

    def _prompt_sensor_payload(self, sensor_data: dict[str, Any]) -> dict[str, Any]:
        allowed_keys = {
            "temperature",
            "humidity",
            "illuminance",
            "indoor_lux",
            "eco2",
            "tvoc",
            "power_w",
            "energy_wh",
            "solar_power_w",
            "solar_energy_wh",
            "soc_percent",
            "comfort_score",
            "relays",
            "curtain_steps",
            "safe_mode",
            "safe_reason",
        }
        safe: dict[str, Any] = {}
        for key in allowed_keys:
            if key in sensor_data:
                safe[key] = self._sanitize_prompt_value(sensor_data.get(key))
        return safe

    def _update_stats(self, candidate_id: str, score: float | None, ok: bool) -> None:
        st = self._stats.get(candidate_id) or _CandidateStats()
        if ok:
            st.success += 1
            st.consecutive_fail = 0
            st.circuit_open_until = 0.0
            st.circuit_open_count = 0
        else:
            st.fail += 1
            st.consecutive_fail += 1
            # Circuit breaker: open after a few consecutive failures.
            # Keep defaults conservative to avoid flapping.
            if st.consecutive_fail >= 2:
                base_open_s = 20.0
                max_open_s = 10 * 60.0
                open_s = min(base_open_s * (2 ** min(st.circuit_open_count, 4)), max_open_s)
                st.circuit_open_until = _now_s() + open_s
                st.circuit_open_count += 1
        if score is not None:
            st.n += 1
            # EMA with small smoothing; enough to compare candidates.
            alpha = 0.2
            st.ema_score = score if st.n == 1 else (alpha * score + (1 - alpha) * st.ema_score)
        self._stats[candidate_id] = st

    def _is_circuit_open(self, candidate_id: str) -> bool:
        st = self._stats.get(candidate_id)
        if not st:
            return False
        return st.circuit_open_until > _now_s()

    def _filter_closed_candidates(self, candidates: list[AIRequestCandidate]) -> list[AIRequestCandidate]:
        closed = [c for c in candidates if not self._is_circuit_open(c.id)]
        return closed

    def _get_candidates(self) -> list[AIRequestCandidate]:
        if self.cfg.candidates:
            return list(self.cfg.candidates)
        # default single candidate based on top-level config
        return [
            AIRequestCandidate(
                id="default",
                temperature=0.2,
                max_tokens=512,
                timeout_s=10.0,
                max_retries=2,
                model=self.cfg.model,
                api_base=self.cfg.api_base,
            )
        ]

    def _choose_candidate(self, candidates: list[AIRequestCandidate]) -> AIRequestCandidate:
        # Prefer closed circuits; if all are open, pick the one that will open soonest (half-open probe).
        closed = self._filter_closed_candidates(candidates)
        pool = closed if closed else list(candidates)
        if len(pool) == 1:
            return pool[0]
        explore = float(self.cfg.exploration_rate)
        if explore > 0 and random.random() < explore:
            return random.choice(pool)
        # Exploit: pick best EMA score; tie-break by lower fail count.
        def key(c: AIRequestCandidate):
            st = self._stats.get(c.id)
            if not st:
                return (-1e9, 1e9)
            # Dynamic down-weight: penalize recent failures more than historical.
            penalty = 0.15 * float(st.fail) + 0.8 * float(st.consecutive_fail)
            return (st.ema_score - penalty, -st.fail)

        # If all are open, probe the one with smallest remaining open time.
        if not closed:
            def rem_open(c: AIRequestCandidate) -> float:
                st = self._stats.get(c.id) or _CandidateStats()
                return float(st.circuit_open_until)
            return min(pool, key=rem_open)

        return max(pool, key=key)

    def _build_prompt(self, sensor_data: dict[str, Any]) -> str:
        safe_sensor_data = self._prompt_sensor_payload(sensor_data)
        return (
            "Current indoor environment data: "
            + json.dumps(safe_sensor_data, ensure_ascii=False)
            + "\nGoals: Maximize comfort while minimizing energy consumption.\n\n"
            + "Controls available:\n"
            + "- RELAY 1 (Air Conditioner)\n"
            + "- RELAY 2 (Living Room Lights)\n"
            + "- RELAY 3 (Ventilation/Fresh Air)\n"
            + "- CURTAIN (OPEN/CLOSE/STOP)\n\n"
            + "Return a JSON object with:\n"
            + "1. 'reasoning': concise explanation.\n"
            + "2. 'commands': a list of raw ESP32 commands to execute.\n"
            + "Example: {\"reasoning\":\"High CO2 detected.\",\"commands\":[\"RELAY 3 1\"]}"
        )

    @staticmethod
    def _provider_tag(api_base: str) -> str:
        b = (api_base or "").lower()
        if "deepseek" in b:
            return "deepseek"
        if "openai" in b:
            return "openai"
        return "openai_compat"

    @staticmethod
    def _parse_json_object(content: str) -> dict[str, Any] | None:
        if not content:
            return None
        text = content.strip()
        # Strip common markdown fences
        if text.startswith("```"):
            lines = text.splitlines()
            # drop first fence line
            if lines:
                lines = lines[1:]
            # drop last fence line if present
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else None
        except Exception:
            pass

        # Best-effort: find a JSON object substring
        try:
            start = text.find("{")
            end = text.rfind("}")
            if 0 <= start < end:
                obj = json.loads(text[start : end + 1])
                return obj if isinstance(obj, dict) else None
        except Exception:
            return None

        return None

    def _call_cloud(self, candidate: AIRequestCandidate, prompt: str) -> tuple[dict[str, Any] | None, str | None]:
        if not self.client or not self._openai:
            return None, "client_unavailable"

        model = (candidate.model or self.cfg.model).strip() or self.cfg.model
        api_base = (candidate.api_base or self.cfg.api_base).strip() or self.cfg.api_base

        # Some openai client versions allow per-client timeout; create a temporary client if needed.
        try:
            client = self._openai.OpenAI(api_key=self.api_key, base_url=api_base, timeout=float(candidate.timeout_s))
        except Exception:
            client = self.client

        last_err: Exception | None = None
        for attempt in range(int(candidate.max_retries) + 1):
            try:
                kwargs = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are a smart home energy consultant."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": float(candidate.temperature),
                    "max_tokens": int(candidate.max_tokens),
                }

                # Prefer strict JSON output when supported.
                try:
                    response = client.chat.completions.create(
                        **kwargs,
                        response_format={"type": "json_object"},
                    )
                except Exception as e_rf:
                    # Some OpenAI-compatible providers may not support response_format.
                    msg = str(e_rf).lower()
                    if "response_format" in msg or "unknown" in msg or "unsupported" in msg:
                        response = client.chat.completions.create(**kwargs)
                    else:
                        raise

                content = response.choices[0].message.content
                if not content:
                    return None, "empty_response"
                obj = self._parse_json_object(content)
                if not isinstance(obj, dict):
                    return None, "json_parse_failed"
                obj.setdefault("reasoning", "")
                obj.setdefault("commands", [])
                if not isinstance(obj.get("commands"), list):
                    obj["commands"] = []
                obj.setdefault("provider", self._provider_tag(api_base))
                return obj, None
            except Exception as e:
                last_err = e
                self.logger.error(f"AI error (candidate={candidate.id} attempt {attempt + 1}/{int(candidate.max_retries) + 1}): {e}")
                time.sleep(0.4 * (attempt + 1))

        return None, f"cloud_error:{last_err}"

    def _local_fallback(self, sensor_data: dict[str, Any]) -> dict[str, Any]:
        cmds: list[str] = []
        reasons: list[str] = []

        eco2 = sensor_data.get("eco2")
        tvoc = sensor_data.get("tvoc")
        temp = sensor_data.get("temperature")
        lux = sensor_data.get("illuminance")
        hour = datetime_now_hour()

        if self.cfg.fallback_enable_relay3:
            # Simple ventilation policy
            if isinstance(eco2, (int, float)) and float(eco2) >= 1000:
                cmds.append("RELAY 3 1")
                reasons.append("eco2_high")
            elif isinstance(tvoc, (int, float)) and float(tvoc) >= 300:
                cmds.append("RELAY 3 1")
                reasons.append("tvoc_high")
            elif isinstance(eco2, (int, float)) and float(eco2) <= 650:
                cmds.append("RELAY 3 0")
                reasons.append("eco2_normal")

        if self.cfg.fallback_enable_curtain:
            # Daytime curtain heuristic: reduce solar gain when hot & bright.
            if isinstance(temp, (int, float)) and isinstance(lux, (int, float)):
                if 9 <= hour < 18 and float(temp) >= 27.5 and float(lux) >= 800:
                    cmds.append("CURTAIN CLOSE")
                    reasons.append("hot_and_bright")
                elif 9 <= hour < 18 and float(lux) <= 200:
                    cmds.append("CURTAIN OPEN")
                    reasons.append("too_dark")

        return {
            "reasoning": "local_fallback:" + ("/".join(reasons) if reasons else "no_action"),
            "commands": cmds,
        }

    def get_action(self, sensor_data: dict[str, Any]) -> dict[str, Any]:
        """
        Takes sensor JSON, sends to AI, and expects control commands back.
        sensor_data: dict with temperature, humidity, illuminance, eco2, tvoc
        """
        prompt = self._build_prompt(sensor_data)
        score = self._score_sample(sensor_data)

        candidates = self._get_candidates()
        chosen = self._choose_candidate(candidates)

        tuning_event = None
        if self._last_candidate_id is not None and self._last_candidate_id != chosen.id:
            prev = self._stats.get(self._last_candidate_id)
            tuning_event = {
                "from": self._last_candidate_id,
                "to": chosen.id,
                "prev_ema_score": prev.ema_score if prev else None,
                "prev_n": prev.n if prev else 0,
            }

        t0 = time.monotonic()
        obj, err = self._call_cloud(chosen, prompt)
        latency_ms = int((time.monotonic() - t0) * 1000)

        if obj is not None:
            self._update_stats(chosen.id, score, ok=True)
            self._last_candidate_id = chosen.id
            obj.setdefault("reasoning", "")
            obj.setdefault("commands", [])
            obj["advisor_source"] = "cloud"
            obj["candidate_id"] = chosen.id
            obj["latency_ms"] = latency_ms
            obj["score"] = score
            if tuning_event:
                obj["tuning_event"] = tuning_event
            return obj

        # Record failure for the chosen candidate (even if another candidate later succeeds).
        self._update_stats(chosen.id, score, ok=False)

        # Try other candidates (multi-layer fallback inside cloud tier)
        for cand in candidates:
            if cand.id == chosen.id:
                continue
            if self._is_circuit_open(cand.id):
                continue
            t1 = time.monotonic()
            obj2, err2 = self._call_cloud(cand, prompt)
            latency2 = int((time.monotonic() - t1) * 1000)
            if obj2 is not None:
                self._update_stats(cand.id, score, ok=True)
                self._last_candidate_id = cand.id
                obj2["advisor_source"] = "cloud_fallback"
                obj2["candidate_id"] = cand.id
                obj2["latency_ms"] = latency2
                obj2["score"] = score
                obj2["cloud_error"] = err
                if tuning_event:
                    obj2["tuning_event"] = tuning_event
                return obj2
            self._update_stats(cand.id, score, ok=False)

        # Local degrade strategy
        if self.cfg.enable_local_fallback:
            fb = self._local_fallback(sensor_data)
            fb["advisor_source"] = "local_fallback"
            fb["candidate_id"] = chosen.id
            fb["latency_ms"] = latency_ms
            fb["score"] = score
            fb["cloud_error"] = err
            if tuning_event:
                fb["tuning_event"] = tuning_event
            return fb

        return {
            "reasoning": f"AI disabled or failed: {err}",
            "commands": [],
            "advisor_source": "disabled",
            "candidate_id": chosen.id,
            "latency_ms": latency_ms,
            "score": score,
        }


def datetime_now_hour() -> int:
    # isolated for testability
    return time.localtime().tm_hour
