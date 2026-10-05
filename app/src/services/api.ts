/**
 * API service layer.
 *
 * Two modes:
 *   - LIVE:  fetches from the Python backend (api_server.py on port 8080)
 *   - MOCK:  generates synthetic data (used when backend is unreachable)
 *
 * The store automatically falls back to mock data when the backend is down,
 * so the frontend is always usable for demos.
 */

import type {
  SensorSnapshot,
  AICandidate,
  ResilienceEvent,
  EnergySummary,
  ChartDataPoint,
  HealthStatus,
  SimulationParams,
} from '@/types';

// ── Config ────────────────────────────────────────────────────────
const API_BASE = '/api'; // proxied to backend via vite.config.ts

/**
 * 单次请求超时。**必须小于轮询间隔（3000ms）**，否则慢后端会让批次重叠
 * （旧值 5000ms > 3000ms，实测会产生重叠请求）。
 */
const REQUEST_TIMEOUT_MS = 2500;

async function apiGet<T>(path: string, params?: Record<string, string>): Promise<T | null> {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const res = await fetch(url.toString(), { signal: controller.signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as T;
  } catch {
    return null; // null = 本次请求失败；**连不连得上**由调用方按整轮结果聚合判定
  } finally {
    clearTimeout(timer);
  }
}

// ── Live API calls ────────────────────────────────────────────────

export async function fetchSnapshot(): Promise<SensorSnapshot | null> {
  return apiGet<SensorSnapshot>('/snapshot');
}

export async function fetchChart(range: string): Promise<ChartDataPoint[] | null> {
  return apiGet<ChartDataPoint[]>('/chart', { range });
}

export async function fetchAICandidates(): Promise<AICandidate[] | null> {
  return apiGet<AICandidate[]>('/ai-candidates');
}

export async function fetchResilienceEvents(): Promise<ResilienceEvent[] | null> {
  return apiGet<ResilienceEvent[]>('/resilience');
}

export async function fetchEnergySummary(): Promise<EnergySummary | null> {
  return apiGet<EnergySummary>('/energy-summary');
}

export async function fetchHealth(): Promise<HealthStatus | null> {
  return apiGet<HealthStatus>('/health');
}

export async function fetchSimulationParams(): Promise<SimulationParams | null> {
  return apiGet<SimulationParams>('/simulation/params');
}

// ── Mock generators (fallback) ────────────────────────────────────

export function generateMockSnapshot(): SensorSnapshot {
  const now = new Date();
  return {
    timestamp: now.toISOString(),
    temperature: 22 + Math.random() * 6,
    humidity: 40 + Math.random() * 30,
    illuminance: 200 + Math.random() * 800,
    eco2: 400 + Math.random() * 600,
    bus_v: 3.3 + Math.random() * 0.2,
    current_ma: 100 + Math.random() * 500,
    power_w: 2 + Math.random() * 15,
    solar_power_w: Math.random() * 50,
    soc_percent: 60 + Math.random() * 35,
    relays: [Math.random() > 0.5 ? 1 : 0, Math.random() > 0.5 ? 1 : 0],
    curtain_steps: Math.floor(Math.random() * 1000),
    comfort_score: 60 + Math.random() * 35,
    safe_mode: Math.random() > 0.9,
    safe_reason: Math.random() > 0.9 ? 'Thermal spike detected' : undefined,
    errors: [],
  };
}

export function generateChartData(range: string): ChartDataPoint[] {
  const points: ChartDataPoint[] = [];
  const count = range === '5m' ? 30 : range === '1h' ? 60 : 100;
  const now = new Date();

  for (let i = 0; i < count; i++) {
    const t = new Date(
      now.getTime() - (count - i) * (range === '5m' ? 10000 : range === '1h' ? 60000 : 864000),
    );
    points.push({
      time: t.toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
        second: range === '5m' ? '2-digit' : undefined,
      }),
      temp: 22 + Math.sin(i * 0.1) * 3 + Math.random() * 2,
      humidity: 50 + Math.cos(i * 0.08) * 15 + Math.random() * 5,
      illuminance: 300 + Math.sin(i * 0.05) * 500 + Math.random() * 100,
      eco2: 500 + Math.sin(i * 0.12) * 200 + Math.random() * 50,
      power_w: 5 + Math.sin(i * 0.07) * 8 + Math.random() * 3,
      solar_power_w: Math.max(0, Math.sin(i * 0.06) * 40 + Math.random() * 10),
      baseline_power: 12 + Math.sin(i * 0.07) * 5 + Math.random() * 2,
      saving_power: 8 + Math.sin(i * 0.07) * 4 + Math.random() * 1.5,
      comfort_score: 70 + Math.cos(i * 0.1) * 20 + Math.random() * 5,
    });
  }
  return points;
}

export function generateMockAICandidates(): AICandidate[] {
  return [
    {
      id: 'ai-001',
      name: '温度微调策略',
      source: 'cloud',
      score: 0.92,
      latency_ms: 245,
      accepted: true,
      rejected: false,
      commands: ['降低空调温度 1°C', '开启辅助风扇'],
      risk: '低',
      createdAt: new Date(Date.now() - 120000).toISOString(),
    },
    {
      id: 'ai-002',
      name: '光照节能方案',
      source: 'local_fallback',
      score: 0.78,
      latency_ms: 120,
      accepted: false,
      rejected: true,
      rejectedReason: '当前光照已处于最低阈值',
      commands: ['调暗灯光 20%', '利用自然光'],
      risk: '中',
      createdAt: new Date(Date.now() - 300000).toISOString(),
    },
    {
      id: 'ai-003',
      name: '窗帘自动控制',
      source: 'cloud',
      score: 0.85,
      latency_ms: 180,
      commands: ['窗帘关闭 50%', '遮阳模式启动'],
      risk: '低',
      createdAt: new Date(Date.now() - 600000).toISOString(),
    },
  ];
}

export function generateMockResilienceEvents(): ResilienceEvent[] {
  return [
    {
      incident_id: 'inc-001',
      state: 'stale_detected',
      action: 'I2C_RECOVER',
      success: true,
      reason: '传感器无响应，执行总线恢复',
      timestamp: new Date(Date.now() - 360000).toISOString(),
    },
    {
      incident_id: 'inc-002',
      state: 'connection_lost',
      action: 'RESET',
      success: true,
      reason: '串口连接中断，执行软复位',
      timestamp: new Date(Date.now() - 720000).toISOString(),
    },
    {
      incident_id: 'inc-003',
      state: 'thermal_alert',
      action: 'AUTO_COOLING',
      success: true,
      timestamp: new Date(Date.now() - 1800000).toISOString(),
    },
  ];
}

export function generateMockEnergySummary(): EnergySummary {
  return {
    baseline_kwh: 45.8,
    saving_kwh: 32.1,
    saving_rate: 29.9,
    cost_saved_cny: 18.4,
    carbon_reduced_kg: 12.7,
  };
}

export function generateMockHealthStatus(): HealthStatus {
  return {
    serial_connected: true,
    last_heartbeat: new Date().toISOString(),
    sampling_rate_hz: 1.0,
    sensors_online: {
      temperature: true,
      humidity: true,
      illuminance: true,
      eco2: true,
      power: true,
      solar: true,
    },
    retry_count: 0,
    self_healing_enabled: true,
    stale_detected: false,
  };
}

export function getDefaultSimulationParams(): SimulationParams {
  return {
    days: 7,
    outdoor_temp_base: 28,
    solar_radiation_max: 1000,
    building_insulation_r: 3.5,
    hvac_efficiency: 0.85,
    occupancy_schedule: '9-18',
    enable_ai: true,
    enable_rules: true,
  };
}
