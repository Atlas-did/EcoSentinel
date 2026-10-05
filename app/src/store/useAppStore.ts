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
  /** 只刷新图表（切换时间区间用），不重拉另外 6 个端点。 */
  refreshChart: (range: TimeRange) => Promise<void>;
  acceptCandidate: (id: string) => void;
  rejectCandidate: (id: string, reason: string) => void;
  updateSimulationParams: (params: Partial<SimulationParams>) => void;
}

let toastIdCounter = 0;

/**
 * 批次去重：同一时刻只允许一轮 refreshData 在途。
 * 旧实现没有保护，而轮询间隔 3s、超时 5s ⇒ 慢后端下批次会重叠，
 * 旧批次还会把新批次的 isRefreshing 提前清掉。
 */
let refreshInFlight = false;

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
    // 立即用 mock 填图（避免空窗），随后**只**拉图表端点：
    // 旧实现顺带重拉全部 7 个端点，切一次区间等于整轮轮询。
    set({ chartData: generateChartData(selectedTimeRange) });
    void get().refreshChart(selectedTimeRange);
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
    if (refreshInFlight) return; // 慢后端下不叠批次
    refreshInFlight = true;
    set({ isRefreshing: true });
    const state = get();

    try {
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

      // 整轮聚合：**全部**端点失败才算离线。
      // 旧实现读的是 api.ts 的模块级标志（"最后一个完成的请求说了算"），
      // 于是一个端点失败、另外六个成功时也会误报"后端未连接"并每 3s 抖 toast。
      const backendUp = [snap, chart, ai, resEv, energy, health, simParams].some(
        (result) => result !== null,
      );

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

      if (backendUp && state.backendOnline !== true) {
        get().addToast({ type: 'success', message: '已连接到后端 API 服务器' });
      } else if (!backendUp && state.backendOnline !== false) {
        get().addToast({ type: 'warning', message: '后端未连接，使用模拟数据' });
      }
    } finally {
      refreshInFlight = false;
    }
  },

  refreshChart: async (range) => {
    const chart = await fetchChart(range).catch(() => null);
    if (chart && chart.length > 0) set({ chartData: chart });
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
