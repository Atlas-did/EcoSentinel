# EcoSentinel — Smart Environmental Monitoring & AI Energy-Saving System

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/)
[![ESP32](https://img.shields.io/badge/Hardware-ESP32--S3-orange.svg)](firmware/)

A closed-loop edge-computing system for **real-time environmental monitoring** and **AI-assisted energy-saving control**. Designed for competition demos and engineering-grade reliability — the system stays stable even when the AI goes down.

**Core philosophy**: AI is the *advisor*, not the *executor*. Rule-based controllers with hysteresis, anti-short-cycle protection, and a self-healing orchestrator ensure safe operation regardless of cloud connectivity.

---

## What It Does

| Layer | Role |
|-------|------|
| **Physical** | ESP32-S3 collects environmental data (temp, humidity, light, air quality, power) via sensors + INA219 energy metering; relays & actuators close the control loop |
| **Edge (Python)** | Rule-based control (time-of-use setpoints, deadband, min-run/min-stop), AI advisor (DeepSeek/OpenAI-compatible with candidate pool, circuit breaker, local fallback), self-healing orchestrator (I2C recovery, MCU reset, rate limiting) |
| **Dashboard** | React web UI + Streamlit dashboard; real-time curves, baseline-vs-saving energy comparison, AI candidate metrics, comfort scores |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for the React frontend)
- (Optional) ESP32-S3 with sensors for hardware mode

### 3-command demo (simulation mode — no hardware needed)

```bash
# 1. Install Python dependencies (core: API / firmware tooling / tests)
pip install -r requirements.txt
# ...and, only if you want the Streamlit dashboard below (adds streamlit/pandas/matplotlib):
#     pip install -r requirements-dashboard.txt

# 2. Run simulation comparison (baseline vs energy-saving)
python -m energy_system.simulation.compare

# 3. Launch the Streamlit dashboard
streamlit run dashboard.py
```

### With React frontend (recommended)

```bash
# Terminal 1: Start the Python API server
python api_server.py --port 8080

# Terminal 2: Start the React frontend
cd app
npm install
npm run dev
```

Open `http://localhost:3000` — the frontend auto-connects to the backend API, and falls back to simulated data if the backend is down.

### With hardware (ESP32 + sensors)

```bash
# 1. Configure params.yaml with your serial port and settings
# 2. Run the main control loop
python main.py

# 3. Start the dashboard (in a separate terminal)
streamlit run dashboard.py
```

---

## Project Structure

```
ecosentinel/
├── main.py                  # Hardware-mode main control loop
├── api_server.py            # FastAPI backend for React frontend
├── dashboard.py             # Streamlit dashboard entry
│
├── energy_system/           # Core Python modules
│   ├── algorithms/          # AI advisor, comfort evaluation, energy savings
│   ├── config/              # YAML config loader, runtime settings
│   ├── core/                # Rule-based controller, thermal model, logging
│   ├── hardware/            # Serial bridge, MQTT client, mock drivers
│   ├── power/               # Energy accounting (Wh/kWh integration)
│   ├── resilience/          # Self-healing orchestrator (stale detection → recovery)
│   ├── simulation/          # Digital twin simulator + data generator
│   └── utils/               # Helpers, env loader, file I/O, process manager
│
├── dashboard/               # Streamlit dashboard modules
│   ├── realtime_view.py     # Real-time sensor curves
│   ├── energy_view.py       # Baseline vs saving energy comparison
│   ├── simulation_view.py   # Digital twin visualization
│   └── ...
│
├── app/                     # React (TypeScript + Tailwind) frontend
│   ├── src/
│   │   ├── components/      # UI components (charts, metric cards, controls)
│   │   ├── pages/           # Dashboard, Realtime, Energy, Simulation, AI pages
│   │   └── services/        # API client
│   └── package.json
│
├── firmware/                 # ESP32-S3 Arduino firmware
│   └── esp32_s3_competition/
│
├── scripts/                  # Utility scripts (DeepSeek test, serial tools)
├── tests/                    # pytest test suite
├── docs/                     # Hardware guide & supplementary docs
├── logs/                     # Runtime logs (gitignored)
├── LICENSE                   # MIT
└── CITATION.cff              # Citation metadata
```

---

## Key Features

### 1. Rule-Based Control with Engineering-Grade Stability

- **Time-of-use setpoints** — different temperature/lighting targets per time-of-day
- **Hysteresis + deadband** — ±0.5°C deadband prevents chattering near setpoints
- **Anti-short-cycle** — minimum 15-min run time, minimum 10-min stop time for compressor protection
- **State-aware actuation** — commands are only sent when relay state actually changes

### 2. AI Advisor with Graceful Degradation

- **Suggestion mode** (default) — AI proposes actions; the rule controller decides
- **Candidate pool** — multiple API configs with exploration/exploitation + EMA scoring
- **Circuit breaker** — consecutive failures auto-skip a candidate; half-open probing for recovery
- **Local fallback** — when the cloud is unreachable, heuristic strategies take over (ventilation, curtain control based on eCO₂/TVOC/temperature)
- Compatible with **DeepSeek** and any **OpenAI-compatible** API

### 3. Self-Healing & Resilience

- **Stale data detection** — triggers safe mode after configurable timeout
- **Auto-recovery actions** — I2C bus recovery, MCU soft reset (with cooldown + rate limiting)
- **Audit trail** — every self-healing action is logged to `logs/incidents_<label>.jsonl`

### 4. Quantifiable Energy Savings

- **INA219 energy metering** — integrates power over time → Wh/kWh
- **Baseline vs Saving comparison** — run two labels, dashboard shows savings rate
- **Comfort score** — temperature/humidity mapped to a unified metric, proving savings aren't from sacrificing comfort
- **Dual-channel metering** (optional) — measure both load consumption + solar input simultaneously

> ⚠️ **Simulation numbers are not field measurements.** With the current (uncalibrated, demo-grade)
> building parameters, the deterministic 3-day simulation reports baseline 199.10 kWh vs saving
> 164.01 kWh → **17.6% savings** (comfort score 49.3% vs 49.1%). Earlier revisions of this repo quoted
> 29.8% / 82.1%: those came from a numerically diverging thermal model (explicit Euler at dt=300 s,
> above the 2τ≈27.8 s stability limit) and are **retracted**. The savings claim still needs
> real-hardware, alternating baseline/saving runs before it can be compared with literature values.

> **Two estimators, not one.** The 17.6% above is a **paired** comparison (run baseline 3 days, then saving
> 3 days). A second, IPMVP-Option-C-style estimator lives in `energy_system/simulation/aso_experiment.py`:
> it **alternates the strategy inside one continuous run** (ASO) and extrapolates a
> outdoor-temperature regression baseline to the report periods — for 6 days at seed 42 it reports
> **19.12% ± 4.21 kWh (95%)**, `R²=0.82`. The two numbers are **different estimators and must not be
> averaged or mixed**; each must be quoted with its own method and caveat (see `docs/refactor-baseline.md`).

### 5. Observable Evidence Chain

Every sample written to JSONL includes:
- Energy: `power_w`, `energy_wh`, `solar_power_w`, `solar_energy_wh`
- Comfort: `comfort_score` + raw sensor fields
- AI: `ai_source`, `ai_candidate_id`, `ai_latency_ms`, `ai_score`, `ai_cloud_error`
- Safety: `safe_mode`, `safe_reason`, `resilience.*`

---

## Configuration

All runtime parameters live in `energy_system/config/params.yaml`:

| Section | Key settings |
|---------|-------------|
| `app` | `use_hardware` (true/false), `run_label` (baseline/saving) |
| `serial` | `port`, `baudrate`, `timeout_s` |
| `ai` | `enabled`, `control_mode` (suggest/execute), `model`, `api_base`, candidate pool |
| `control` | `enable_rule_control`, `safe_mode_stale_s`, `actuate_min_interval_s` |
| `self_healing` | `enabled`, `auto_i2c_recover`, `auto_reset`, cooldown settings |

**API keys** are NEVER stored in the YAML config. Inject them via:
1. Environment variable: `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, or `AI_API_KEY`
2. Local `.env` file (gitignored — see `.env.example`)

---

## Demo Flow (3–5 minutes, competition-ready)

1. Run `baseline` (comfort-first, no energy saving) for 30–60 seconds
2. Run `saving` (energy-saving with comfort floor) for 30–60 seconds
3. Open the dashboard: compare power curves + energy savings rate, verify `comfort_score` hasn't collapsed
4. Bonus: shine a flashlight on BH1750 or block the sensor — watch adaptive lighting/curtain strategy change in real time

---

## Running Tests

```bash
pytest tests/ -q
```

---

## Hardware

See [docs/hardware-guide.md](docs/hardware-guide.md) for the complete hardware guide: BOM (budget vs. competition-grade), wiring diagrams, pin assignments, firmware upload instructions, and serial protocol reference.

---

## Citation

If you use EcoSentinel in your research, please cite:

```bibtex
@software{ecosentinel2026,
  author       = {Yifan Wu},
  title        = {EcoSentinel: Smart Environmental Monitoring \& AI Energy-Saving System},
  year         = 2026,
  version      = {1.0.0},
  url          = {https://github.com/Atlas-did/ecosentinel},
  license      = {MIT},
}
```

GitHub will also display a "Cite this repository" button thanks to [CITATION.cff](CITATION.cff).

---

## License

MIT — see [LICENSE](LICENSE) for details.
