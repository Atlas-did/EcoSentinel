// Real-time sensor data snapshot
export interface SensorSnapshot {
  schema_version?: string;
  timestamp: string;
  temperature?: number;
  humidity?: number;
  illuminance?: number;
  eco2?: number;
  bus_v?: number;
  current_ma?: number;
  power_w?: number;
  solar_power_w?: number;
  soc_percent?: number;
  relays?: number[];
  curtain_steps?: number;
  comfort_score?: number;
  safe_mode?: boolean;
  safe_reason?: string;
  errors?: string[];
}

// AI candidate suggestion
export interface AICandidate {
  id: string;
  name: string;
  source: 'cloud' | 'local_fallback';
  score?: number;
  latency_ms?: number;
  accepted?: boolean;
  rejected?: boolean;
  rejectedReason?: string;
  commands: string[];
  risk?: string;
  createdAt: string;
  executed?: boolean; // whether the command was actually sent to hardware
}

// AI suggestion lifecycle: "model returned" vs "device executed" must stay distinct.
export type AICommandStatus = 'suggestion' | 'accepted' | 'rejected' | 'executed';

// Self-healing / resilience event
export interface ResilienceEvent {
  incident_id: string;
  state: string;
  action: string;
  success: boolean;
  reason?: string;
  timestamp: string;
}

// Energy summary data
export interface EnergySummary {
  schema_version?: string;
  baseline_kwh: number;
  saving_kwh: number;
  saving_rate: number;
  cost_saved_cny: number;
  carbon_reduced_kg: number;
  energy_saved_kwh?: number;
  carbon_factor?: number;
  carbon_factor_source?: string | null;
  carbon_factor_version?: string | null;
  electricity_price_cny_per_kwh?: number;
  price_source?: string | null;
}

// Chart data point
export interface ChartDataPoint {
  time: string;
  temp?: number;
  humidity?: number;
  illuminance?: number;
  eco2?: number;
  power_w?: number;
  solar_power_w?: number;
  baseline_power?: number;
  saving_power?: number;
  comfort_score?: number;
}

// System health status
export interface HealthStatus {
  schema_version?: string;
  serial_connected: boolean;
  last_heartbeat: string;
  sampling_rate_hz: number;
  sensors_online: Record<string, boolean>;
  retry_count: number;
  self_healing_enabled: boolean;
  stale_detected: boolean;
  corrupt_records?: number;
}

// Simulation parameters
export interface SimulationParams {
  days: number;
  outdoor_temp_base: number;
  solar_radiation_max: number;
  building_insulation_r: number;
  hvac_efficiency: number;
  occupancy_schedule: string;
  enable_ai: boolean;
  enable_rules: boolean;
}

// UI State types
export type SystemMode = 'real-time' | 'simulation';
export type RunLabel = 'baseline' | 'saving';
export type AIStatus = 'enabled' | 'degraded' | 'disconnected';
export type TimeRange = '5m' | '1h' | '24h';
export type PageTab = 'logs' | 'energy' | 'simulation';

// Toast notification
export interface Toast {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
}
