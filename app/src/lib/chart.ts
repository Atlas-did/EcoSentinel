import type { ChartDataPoint } from '@/types'

/**
 * 逐点功率 → 累计电量的换算系数。
 *
 * 口径：图表每个点是 **1 分钟**桶，功率单位为 W ⇒ 单点电量 = W × 60 s。
 * 换算成 kWh 需先除 3600（秒→小时）再除 1000（W→kW），即 60/3600/1000 ≈ 1.6667e-5。
 *
 * ⚠️ 2026-10 更正：此前的 `0.0167` 少了 **1000 倍**（它其实是 W·min → Wh 的系数，
 * 不是 kWh）。该错误由《EcoSentinel 技术评审与演进路线图》指出，已按上式修正。
 */
const SECONDS_PER_POINT = 60

export const POWER_TO_ENERGY_FACTOR = SECONDS_PER_POINT / 3600 / 1000

export type CumulativePoint = ChartDataPoint & { baseline_cum: number; saving_cum: number }

/**
 * 后端是否提供了逐点基准/节省功率。
 *
 * 只有前端 mock 生成器产出 `baseline_power` / `saving_power`（后端 `/api/chart` 逐点只给
 * `power_w` / `solar_power_w`），因此接真实后端时这两条曲线必然恒为 0 —— 此时必须**显式告知
 * 不可用**，而不是画一条恒为 0 的曲线让人以为"节能为零"。
 */
export function hasCumulativeSeries(points: ChartDataPoint[]): boolean {
  return points.some(
    (p) => p.baseline_power !== undefined || p.saving_power !== undefined,
  )
}

/** 前缀和一次遍历（原实现在 map 内做 slice+reduce ⇒ O(n²)）。缺失字段按 0 计。 */
export function cumulativeEnergySeries(points: ChartDataPoint[]): CumulativePoint[] {
  let baselineCum = 0
  let savingCum = 0
  return points.map((point) => {
    baselineCum += (point.baseline_power ?? 0) * POWER_TO_ENERGY_FACTOR
    savingCum += (point.saving_power ?? 0) * POWER_TO_ENERGY_FACTOR
    return { ...point, baseline_cum: baselineCum, saving_cum: savingCum }
  })
}
