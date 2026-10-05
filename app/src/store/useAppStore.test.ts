/**
 * G6 · 前端最小测试网（第一块）：**store 纯逻辑**。
 *
 * 为什么从这里开始：`app/` 此前零测试，而下一步要做"删掉 61% 不可达 ui/ 文件"
 * 这类批量改动 —— 没有测试网就是赌博。store 是最容易先测、也最该锁住的部分：
 * 它承载了三条"必须保留"的行为（离线兜底 / 连接态只在变化时提示 / accept-reject 只改本地）。
 *
 * 手法：整体 mock '@/services/api'，但**保留真实的 mock 生成器**（它们是离线兜底的数据源），
 * 只把 7 个 fetch* 与 isBackendAvailable 换成可编程的假实现。
 * 数据侧一律走"fetch 失败 ⇒ 回落 mock"，避免在测试里手写庞大的后端负载类型。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/api')>()
  return {
    ...actual,
    fetchSnapshot: vi.fn(),
    fetchChart: vi.fn(),
    fetchAICandidates: vi.fn(),
    fetchResilienceEvents: vi.fn(),
    fetchEnergySummary: vi.fn(),
    fetchHealth: vi.fn(),
    fetchSimulationParams: vi.fn(),
  }
})

import * as api from '@/services/api'
import { useAppStore } from '@/store/useAppStore'

const INITIAL = useAppStore.getState()

/** 全部端点失败 ⇒ 按整轮聚合应判为"离线"并回落 mock。 */
function failAll() {
  vi.mocked(api.fetchSnapshot).mockRejectedValue(new Error('backend down'))
  vi.mocked(api.fetchChart).mockRejectedValue(new Error('backend down'))
  vi.mocked(api.fetchAICandidates).mockRejectedValue(new Error('backend down'))
  vi.mocked(api.fetchResilienceEvents).mockRejectedValue(new Error('backend down'))
  vi.mocked(api.fetchEnergySummary).mockRejectedValue(new Error('backend down'))
  vi.mocked(api.fetchHealth).mockRejectedValue(new Error('backend down'))
  vi.mocked(api.fetchSimulationParams).mockRejectedValue(new Error('backend down'))
}

/** 6 个端点成功、只有 chart 失败：后端其实是活的。 */
function oneEndpointFails() {
  failAll()
  vi.mocked(api.fetchSnapshot).mockResolvedValue({} as never)
  vi.mocked(api.fetchAICandidates).mockResolvedValue([{}] as never)
  vi.mocked(api.fetchResilienceEvents).mockResolvedValue([{}] as never)
  vi.mocked(api.fetchEnergySummary).mockResolvedValue({} as never)
  vi.mocked(api.fetchHealth).mockResolvedValue({} as never)
  vi.mocked(api.fetchSimulationParams).mockResolvedValue({} as never)
}

/** 全部端点成功。 */
function succeedAll() {
  failAll()
  oneEndpointFails()
  vi.mocked(api.fetchChart).mockResolvedValue([{}] as never)
}

beforeEach(() => {
  // 单例 store：每个用例前把状态整体还原为初始快照（含 action 函数）
  useAppStore.setState({ ...INITIAL, toasts: [] }, true)
})

afterEach(() => {
  vi.useRealTimers()
})

describe('refreshData · 离线兜底（必须保留）', () => {
  it('后端不可达时回落到 mock 数据，并把 backendOnline 置为 false', async () => {
    failAll()
    await useAppStore.getState().refreshData()

    const s = useAppStore.getState()
    expect(s.backendOnline).toBe(false)
    expect(s.isRefreshing).toBe(false)
    // 必须有数据可渲染：不得变成空白（离线可用性）
    expect(s.latestSnapshot).not.toBeNull()
    expect(s.chartData.length).toBeGreaterThan(0)
    expect(s.energySummary).not.toBeNull()
  })

  it('连接态只在**变化**时提示：连续两次离线只弹一次 toast', async () => {
    failAll()
    await useAppStore.getState().refreshData()
    const afterFirst = useAppStore.getState().toasts.length
    expect(afterFirst).toBe(1)
    expect(useAppStore.getState().toasts[0]?.type).toBe('warning')

    await useAppStore.getState().refreshData()
    expect(useAppStore.getState().toasts.length).toBe(afterFirst)
  })

  it('从离线恢复为在线时再提示一次', async () => {
    failAll()
    await useAppStore.getState().refreshData()
    expect(useAppStore.getState().backendOnline).toBe(false)

    succeedAll()
    await useAppStore.getState().refreshData()
    const s = useAppStore.getState()
    expect(s.backendOnline).toBe(true)
    expect(s.toasts.filter((t) => t.type === 'success')).toHaveLength(1)
  })
})

describe('accept / reject · 只改本地、不发网络请求（必须保留）', () => {
  const firstId = () => useAppStore.getState().aiCandidates[0]?.id as string

  it('acceptCandidate 标记本地状态、发 toast，且不触发任何 fetch', () => {
    const id = firstId()
    vi.mocked(api.fetchAICandidates).mockClear()

    useAppStore.getState().acceptCandidate(id)

    const c = useAppStore.getState().aiCandidates.find((x) => x.id === id)
    expect(c?.accepted).toBe(true)
    expect(c?.rejected).toBe(false)
    expect(api.fetchAICandidates).not.toHaveBeenCalled()
    expect(useAppStore.getState().toasts.at(-1)?.type).toBe('success')
  })

  it('rejectCandidate 记录拒绝原因，且同样不发网络请求', () => {
    const id = firstId()
    vi.mocked(api.fetchAICandidates).mockClear()

    useAppStore.getState().rejectCandidate(id, '理由：超出安全窗口')

    const c = useAppStore.getState().aiCandidates.find((x) => x.id === id)
    expect(c?.rejected).toBe(true)
    expect(c?.accepted).toBe(false)
    expect(c?.rejectedReason).toBe('理由：超出安全窗口')
    expect(api.fetchAICandidates).not.toHaveBeenCalled()
  })
})

describe('toast 生命周期与其余 UI 动作', () => {
  it('addToast 4 秒后自动移除，removeToast 立即移除', () => {
    vi.useFakeTimers()
    useAppStore.getState().addToast({ type: 'info', message: 'hi' })
    const id = useAppStore.getState().toasts[0]?.id as string
    expect(useAppStore.getState().toasts).toHaveLength(1)

    vi.advanceTimersByTime(3900)
    expect(useAppStore.getState().toasts).toHaveLength(1) // 还没到点
    vi.advanceTimersByTime(200)
    expect(useAppStore.getState().toasts).toHaveLength(0) // 到点自动清

    useAppStore.getState().addToast({ type: 'info', message: 'bye' })
    const id2 = useAppStore.getState().toasts[0]?.id as string
    useAppStore.getState().removeToast(id2)
    expect(useAppStore.getState().toasts).toHaveLength(0)
    expect(id).not.toBe(id2)
  })

  it('setTimeRange 立即切换区间与图表数据（不等待网络）', async () => {
    failAll()
    useAppStore.getState().setTimeRange('5m')
    const s = useAppStore.getState()
    expect(s.selectedTimeRange).toBe('5m')
    expect(s.chartData.length).toBeGreaterThan(0)
    await Promise.resolve()
  })

  it('toggleSidebar 取反；updateSimulationParams 做局部合并', () => {
    const before = useAppStore.getState().sidebarOpen
    useAppStore.getState().toggleSidebar()
    expect(useAppStore.getState().sidebarOpen).toBe(!before)

    const original = { ...useAppStore.getState().simulationParams }
    useAppStore.getState().updateSimulationParams({ days: 7 })
    const after = useAppStore.getState().simulationParams
    expect(after.days).toBe(7)
    // 未指定的字段必须保留（局部合并语义）
    expect(after).toEqual({ ...original, days: 7 })
  })
})

describe('M6.5 · 轮询可靠性不变量', () => {
  it('慢后端下不叠批次：在途期间的第二次 refreshData 直接返回', async () => {
    let release: (value: unknown) => void = () => {}
    const gate = new Promise((resolve) => {
      release = resolve
    })
    failAll()
    vi.mocked(api.fetchSnapshot).mockReturnValue(gate as never)

    const first = useAppStore.getState().refreshData()
    const second = useAppStore.getState().refreshData() // 应被去重

    expect(api.fetchSnapshot).toHaveBeenCalledTimes(1)

    release({})
    await Promise.all([first, second])
    // 去重不应把状态卡在"刷新中"
    expect(useAppStore.getState().isRefreshing).toBe(false)
  })

  it('单个端点失败**不算**离线（旧实现会误报"后端未连接"并每 3s 抖 toast）', async () => {
    oneEndpointFails()
    await useAppStore.getState().refreshData()

    const s = useAppStore.getState()
    expect(s.backendOnline).toBe(true)
    expect(s.toasts.filter((t) => t.type === 'warning')).toHaveLength(0)
  })

  it('全部端点失败才判离线，且只提示一次', async () => {
    failAll()
    await useAppStore.getState().refreshData()
    expect(useAppStore.getState().backendOnline).toBe(false)

    const before = useAppStore.getState().toasts.length
    await useAppStore.getState().refreshData()
    expect(useAppStore.getState().toasts.length).toBe(before)
  })

  it('setTimeRange 只拉图表端点，不重拉另外 6 个', async () => {
    succeedAll()
    useAppStore.getState().setTimeRange('5m')
    await Promise.resolve()
    await Promise.resolve()

    expect(api.fetchChart).toHaveBeenCalledTimes(1)
    expect(api.fetchSnapshot).not.toHaveBeenCalled()
    expect(api.fetchHealth).not.toHaveBeenCalled()
    expect(api.fetchResilienceEvents).not.toHaveBeenCalled()
    expect(useAppStore.getState().selectedTimeRange).toBe('5m')
  })
})
