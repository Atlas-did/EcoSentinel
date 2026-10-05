import { describe, expect, it } from 'vitest'

import {
  POWER_TO_ENERGY_FACTOR,
  cumulativeEnergySeries,
  hasCumulativeSeries,
} from '@/lib/chart'
import type { ChartDataPoint } from '@/types'

function point(extra: Partial<ChartDataPoint>): ChartDataPoint {
  return { time: '2026-01-01T00:00:00', ...extra }
}

describe('hasCumulativeSeries · 后端是否提供逐点基准功率', () => {
  it('后端形状的数据（只有 power_w/solar_power_w）⇒ 判定不可用', () => {
    const backendShaped = [
      point({ power_w: 120, solar_power_w: 30 }),
      point({ power_w: 140, solar_power_w: 25 }),
    ]
    expect(hasCumulativeSeries(backendShaped)).toBe(false)
  })

  it('mock 形状的数据（含 baseline_power/saving_power）⇒ 判定可用', () => {
    expect(hasCumulativeSeries([point({ baseline_power: 200, saving_power: 20 })])).toBe(true)
  })

  it('空数组 ⇒ 不可用', () => {
    expect(hasCumulativeSeries([])).toBe(false)
  })
})

describe('cumulativeEnergySeries · 累计曲线', () => {
  it('按前缀和累加，两次采样各 100W ⇒ 1.67 / 3.34', () => {
    const series = cumulativeEnergySeries([
      point({ baseline_power: 100, saving_power: 10 }),
      point({ baseline_power: 100, saving_power: 10 }),
    ])
    expect(series[0].baseline_cum).toBeCloseTo(100 * POWER_TO_ENERGY_FACTOR)
    expect(series[1].baseline_cum).toBeCloseTo(200 * POWER_TO_ENERGY_FACTOR)
    expect(series[1].saving_cum).toBeCloseTo(20 * POWER_TO_ENERGY_FACTOR)
  })

  it('字段缺失按 0 计，且不修改入参', () => {
    const input = [point({ power_w: 50 }), point({ baseline_power: 100 })]
    const snapshot = JSON.parse(JSON.stringify(input))
    const series = cumulativeEnergySeries(input)
    expect(series[0].baseline_cum).toBe(0)
    expect(series[1].baseline_cum).toBeCloseTo(100 * POWER_TO_ENERGY_FACTOR)
    expect(input).toEqual(snapshot)
  })

  it('保留原始字段（图表还要用 time 等）', () => {
    const series = cumulativeEnergySeries([point({ baseline_power: 100 })])
    expect(series[0].time).toBe('2026-01-01T00:00:00')
  })

  it('回归哨兵：前缀和结果必须与朴素 O(n²) 实现一致（顺带证明已从 O(n²) 收敛）', () => {
    const points = Array.from({ length: 100 }, (_, i) =>
      point({ baseline_power: i, saving_power: i / 2 }),
    )
    const naive = points.map((_, i) =>
      points
        .slice(0, i + 1)
        .reduce((acc, p) => acc + (p.baseline_power ?? 0) * POWER_TO_ENERGY_FACTOR, 0),
    )
    const fast = cumulativeEnergySeries(points).map((p) => p.baseline_cum)
    fast.forEach((value, i) => expect(value).toBeCloseTo(naive[i], 10))
  })
})
