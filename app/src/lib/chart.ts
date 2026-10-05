import type { ChartDataPoint } from '@/types'

/**
 * 逐点功率 → 累计电量的换算系数。
 *
 * ⚠️ 这是从页面里**原样提取**出来的既有魔数，数值未改动（口径：按 1 分钟采样步长把 W 折算成
 * kWh 量级）。其单位口径本身是否正确另需确认 —— 本次重构只做"提取 + 命名"，不悄悄改数字。
 */
export const POWER_TO_ENERGY_FACTOR = 0.0167

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
