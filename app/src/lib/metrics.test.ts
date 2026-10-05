/**
 * M6.3 · 前端指标单一真值的行为测试。
 *
 * 只测**行为**（阈值判定、监视范围、默认显示）。
 * "阈值与指标键字面量只能出现在 lib/metrics.ts" 这条**结构门禁**放在 Python 侧
 * （tests/contract/test_metrics_registry.py）—— 那里本来就在读 TS 源码做跨语言契约检查，
 * 而本文件所在的浏览器 tsconfig 没有 node 类型。
 */

import { describe, expect, it } from 'vitest'

import { METRICS, anomaliesOf, defaultActiveSensors, isAnomalous, snapshotValue } from '@/lib/metrics'
import { SNAPSHOT_ALERTS, TARGET_TEMP_C, isSnapshotAlert } from '@/lib/metrics'

describe('METRICS · 覆盖与默认显示', () => {
  it('覆盖全部图表指标键', () => {
    expect(Object.keys(METRICS).sort()).toEqual(
      [
        'baseline_power',
        'comfort_score',
        'eco2',
        'humidity',
        'illuminance',
        'power_w',
        'saving_power',
        'solar_power_w',
        'temp',
      ].sort(),
    )
  })

  it('每个指标都有标签、单位、颜色与图标', () => {
    for (const [key, spec] of Object.entries(METRICS)) {
      expect(spec.label, `${key} 缺标签`).toBeTruthy()
      expect(spec.color, `${key} 缺颜色`).toMatch(/^#[0-9a-f]{6}$/i)
      expect(spec.icon, `${key} 缺图标`).toBeTruthy()
      expect(spec.unit, `${key} 缺单位（空串也允许，但字段必须在）`).toBeTypeOf('string')
    }
  })

  it('默认显示与重构前一致（power/illuminance/湿度/温度 开，eco2 关）', () => {
    const active = defaultActiveSensors()
    expect(active.temp).toBe(true)
    expect(active.humidity).toBe(true)
    expect(active.illuminance).toBe(true)
    expect(active.eco2).toBe(false)
    expect(active.power_w).toBe(true)
  })
})

describe('异常判定 · 阈值必须同源', () => {
  it('eco2 统一为 1000 ppm（2026-10 决策）：1001 异常、999 正常', () => {
    expect(METRICS.eco2.threshold).toBe(1000)
    expect(isAnomalous({ time: 't', eco2: 1001 })).toBe(true)
    expect(isAnomalous({ time: 't', eco2: 999 })).toBe(false)
    // 回归哨兵：旧的显示阈值 1200 已不再使用
    expect(METRICS.eco2.threshold).not.toBe(1200)
  })

  it('temp 阈值 30：31 异常、29 正常', () => {
    expect(isAnomalous({ time: 't', temp: 31 })).toBe(true)
    expect(isAnomalous({ time: 't', temp: 29 })).toBe(false)
  })

  it('只监视 temp 与 eco2（阈值可统一，但监视范围是行为，不得顺手扩大）', () => {
    const watched = Object.entries(METRICS)
      .filter(([, spec]) => spec.anomalyWatch)
      .map(([key]) => key)
      .sort()
    expect(watched).toEqual(['eco2', 'temp'])
    // 湿度/光照/功率即使超阈值也不进异常横幅
    expect(isAnomalous({ time: 't', humidity: 99, illuminance: 9999, power_w: 3500 })).toBe(false)
  })

  it('缺失值不算异常（与旧实现的 `d.temp && ...` 语义一致）', () => {
    expect(isAnomalous({ time: 't' })).toBe(false)
    expect(isAnomalous({ time: 't', temp: undefined })).toBe(false)
  })

  it('anomaliesOf 过滤出异常点且不修改入参', () => {
    const points = [
      { time: 'a', temp: 25 },
      { time: 'b', temp: 31 },
      { time: 'c', eco2: 1500 },
    ]
    const snapshot = JSON.parse(JSON.stringify(points))
    expect(anomaliesOf(points).map((p) => p.time)).toEqual(['b', 'c'])
    expect(points).toEqual(snapshot)
  })
})

describe('snapshotValue · 图表键 → 快照字段的唯一映射', () => {
  it('temp 必须映射到快照的 temperature（此前直接索引 ⇒ 温度恒显示 --）', () => {
    expect(snapshotValue({ temperature: 25.5 }, 'temp')).toBe(25.5)
    // 只认快照的真实字段名：`temp` 不是快照字段
    expect(snapshotValue({ temp: 25.5 }, 'temp')).toBeUndefined()
  })

  it('同名字段直接取用；缺失或非数值一律 undefined', () => {
    expect(snapshotValue({ humidity: 45 }, 'humidity')).toBe(45)
    expect(snapshotValue({ humidity: null }, 'humidity')).toBeUndefined()
    expect(snapshotValue({ humidity: '45' }, 'humidity')).toBeUndefined()
    expect(snapshotValue({}, 'eco2')).toBeUndefined()
    expect(snapshotValue(null, 'temp')).toBeUndefined()
  })
})

describe('SNAPSHOT_ALERTS · 快照指标阈值（含方向）', () => {
  it('温度：高于 30 告警（方向 above）', () => {
    expect(SNAPSHOT_ALERTS.temperature.threshold).toBe(30)
    expect(SNAPSHOT_ALERTS.temperature.direction).toBe('above')
    expect(isSnapshotAlert('temperature', 31)).toBe(true)
    expect(isSnapshotAlert('temperature', 30)).toBe(false)
    expect(isSnapshotAlert('temperature', 29)).toBe(false)
  })

  it('电量：低于 20 告警（方向 below —— 与温度相反，这正是"统一阈值"必须带方向的原因）', () => {
    expect(SNAPSHOT_ALERTS.soc_percent.threshold).toBe(20)
    expect(SNAPSHOT_ALERTS.soc_percent.direction).toBe('below')
    expect(isSnapshotAlert('soc_percent', 19)).toBe(true)
    expect(isSnapshotAlert('soc_percent', 20)).toBe(false)
    expect(isSnapshotAlert('soc_percent', 21)).toBe(false)
  })

  it('eCO2：高于 1000 告警（与图表阈值统一后同源）', () => {
    expect(SNAPSHOT_ALERTS.eco2.threshold).toBe(1000)
    expect(isSnapshotAlert('eco2', 1001)).toBe(true)
    expect(isSnapshotAlert('eco2', 999)).toBe(false)
  })

  it('缺失值不算告警（与旧实现 `latestSnapshot && ...` 语义一致）', () => {
    expect(isSnapshotAlert('temperature', null)).toBe(false)
    expect(isSnapshotAlert('temperature', undefined)).toBe(false)
    expect(isSnapshotAlert('soc_percent', null)).toBe(false)
  })

  it('目标温度为单一常量（原 DashboardPage 内联的 24.5）', () => {
    expect(TARGET_TEMP_C).toBe(24.5)
  })
})
