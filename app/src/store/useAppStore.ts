import { create } from 'zustand';
import type {
  SensorSnapshot,
  AICandidate,
  ResilienceEvent,
  EnergySummary,
  ChartDataPoint,
  HealthStatus,
  SimulationParams,
  SystemMode,
  RunLabel,
  AIStatus,
  TimeRange,
  Toast,
} from '@/types';
import {
  fetchSnapshot,
  fetchChart,
  fetchAICandidates,
  fetchResilienceEvents,
  fetchEnergySummary,
  fetchHealth,
  fetchSimulationParams,
  isBackendAvailable,
  generateMockSnapshot,
  generateChartData,
  generateMockAICandidates,
  generateMockResilienceEvents,
  generateMockEnergySummary,
  generateMockHealthStatus,
  getDefaultSimulationParams,
} from '@/services/api';

interface AppState {
  // UI State
  mode: SystemMode;
  runLabel: RunLabel;
  autoRefresh: boolean;
  selectedTimeRange: TimeRange;
  aiStatus: AIStatus;
  sidebarOpen: boolean;
  toasts: Toast[];

  // Data State
  latestSnapshot: SensorSnapshot | null;
  chartData: ChartDataPoint[];
  aiCandidates: AICandidate[];
  resilienceEvents: ResilienceEvent[];
  energySummary: EnergySummary | null;
  healthStatus: HealthStatus | null;
  simulationParams: SimulationParams;

  // Loading States
  isRefreshing: boolean;
  backendOnline: boolean | null;

  // Actions
  setMode: (mode: SystemMode) => void;
  setRunLabel: (label: RunLabel) => void;
  setAutoRefresh: (enabled: boolean) => void;
  setTimeRange: (range: TimeRange) => void;
  toggleSidebar: () => void;
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;

  // Data Actions
  refreshData: () => Promise<void>;
  acceptCandidate: (id: string) => void;
  rejectCandidate: (id: string, reason: string) => void;
  updateSimulationParams: (params: Partial<SimulationParams>) => void;
}

let toastIdCounter = 0;

export const useAppStore = create<AppState>((set, get) => ({
  // Initial UI State
  mode: 'real-time',
  runLabel: 'saving',
  autoRefresh: true,
  selectedTimeRange: '1h',
  aiStatus: 'enabled',
  sidebarOpen: true,
  toasts: [],

  // Initial Data State (seed with mock so UI renders immediately)
  latestSnapshot: generateMockSnapshot(),
  chartData: generateChartData('1h'),
  aiCandidates: generateMockAICandidates(),
  resilienceEvents: generateMockResilienceEvents(),
  energySummary: generateMockEnergySummary(),
  healthStatus: generateMockHealthStatus(),
  simulationParams: getDefaultSimulationParams(),

  // Initial Loading
  isRefreshing: false,
  backendOnline: null,

  // ── UI Actions ──────────────────────────────────────────────────
  setMode: (mode) => set({ mode }),
  setRunLabel: (runLabel) => set({ runLabel }),
  setAutoRefresh: (autoRefresh) => set({ autoRefresh }),
  setTimeRange: (selectedTimeRange) => {
    set({ selectedTimeRange });
    // Immediately show mock for time range change, then try live
    set({ chartData: generateChartData(selectedTimeRange) });
    get().refreshData();
  },
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  addToast: (toast) => {
    const id = `toast-${++toastIdCounter}`;
    set((state) => ({ toasts: [...state.toasts, { ...toast, id }] }));
    setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
    }, 4000);
  },
  removeToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),

  // ── Data Actions ────────────────────────────────────────────────
  refreshData: async () => {
    set({ isRefreshing: true });
    const state = get();

    // Try live API first, fall back to mock
    const [snap, chart, ai, resEv, energy, health, simParams] = await Promise.all([
      fetchSnapshot().catch(() => null),
      fetchChart(state.selectedTimeRange).catch(() => null),
      fetchAICandidates().catch(() => null),
      fetchResilienceEvents().catch(() => null),
      fetchEnergySummary().catch(() => null),
      fetchHealth().catch(() => null),
      fetchSimulationParams().catch(() => null),
    ]);

    const backendUp = isBackendAvailable();

    set({
      latestSnapshot: snap ?? generateMockSnapshot(),
      chartData: (chart && chart.length > 0) ? chart : generateChartData(state.selectedTimeRange),
      aiCandidates: (ai && ai.length > 0) ? ai : generateMockAICandidates(),
      resilienceEvents: (resEv && resEv.length > 0) ? resEv : generateMockResilienceEvents(),
      energySummary: energy ?? generateMockEnergySummary(),
      healthStatus: health ?? generateMockHealthStatus(),
      simulationParams: simParams ?? getDefaultSimulationParams(),
      backendOnline: backendUp,
      isRefreshing: false,
    });

    if (backendUp === true && state.backendOnline !== true) {
      get().addToast({ type: 'success', message: '已连接到后端 API 服务器' });
    } else if (backendUp === false && state.backendOnline !== false) {
      get().addToast({ type: 'warning', message: '后端未连接，使用模拟数据' });
    }
  },

  acceptCandidate: (id) => {
    set((state) => ({
      aiCandidates: state.aiCandidates.map((c) =>
        c.id === id ? { ...c, accepted: true, rejected: false } : c,
      ),
    }));
    get().addToast({ type: 'success', message: 'AI 建议已接受并执行' });
  },

  rejectCandidate: (id, reason) => {
    set((state) => ({
      aiCandidates: state.aiCandidates.map((c) =>
        c.id === id
          ? { ...c, accepted: false, rejected: true, rejectedReason: reason }
          : c,
      ),
    }));
    get().addToast({ type: 'warning', message: 'AI 建议已拒绝' });
  },

  updateSimulationParams: (params) =>
    set((state) => ({
      simulationParams: { ...state.simulationParams, ...params },
    })),
}));

// ── Auto-refresh ──────────────────────────────────────────────────
let refreshInterval: ReturnType<typeof setInterval> | null = null;

export function startAutoRefresh() {
  if (refreshInterval) clearInterval(refreshInterval);
  refreshInterval = setInterval(() => {
    const state = useAppStore.getState();
    if (state.autoRefresh) {
      state.refreshData();
    }
  }, 3000);
}

export function stopAutoRefresh() {
  if (refreshInterval) {
    clearInterval(refreshInterval);
    refreshInterval = null;
  }
}
