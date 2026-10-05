/**
 * M6.6 · SensorChart 的渲染契约。
 *
 * 覆盖两件事：
 * 1) **渐变 id 唯一**：同页两个图表实例不得产生重复的 <linearGradient id>（原实现是固定 id，
 *    后渲染的定义会遮蔽前一个，导致前一个图表填充色错乱）。
 * 2) 渐变颜色来自 lib/metrics（单一真值），且未显示的系列不产生渐变。
 *
 * jsdom 下 recharts 需要显式尺寸：这里把 ResponsiveContainer 替换为给子元素注入固定宽高。
 */

import { cleanup, render } from '@testing-library/react'
import React from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('recharts')>()
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactElement }) =>
      React.cloneElement(children, { width: 800, height: 300 } as never),
  }
})

import SensorChart from '@/components/charts/SensorChart'
import { METRICS } from '@/lib/metrics'

const DATA = [
  { time: '10:00', temp: 25, humidity: 45, power_w: 100 },
  { time: '10:05', temp: 26, humidity: 46, power_w: 110 },
]

function gradientIds(): string[] {
  return Array.from(document.querySelectorAll('linearGradient')).map(
    (el) => el.getAttribute('id') ?? '',
  )
}

describe('SensorChart · 渐变 id 与颜色', () => {
  afterEach(cleanup)

  it('单个图表的渐变 id 是 useId 前缀化的（不再是裸的 colorTemp）', () => {
    render(<SensorChart data={DATA} showTemp />)
    const ids = gradientIds()
    expect(ids.length).toBeGreaterThan(0)
    expect(ids.some((id) => id.endsWith('-colorTemp'))).toBe(true)
    expect(ids).not.toContain('colorTemp')
  })

  it('同一页面渲染两个图表时，渐变 id **不重复**（原固定 id 会互相覆盖）', () => {
    // 两个实例渲染**相同**系列：这样一旦退回固定 id 就必然出现重复，门禁才有牙
    render(
      <>
        <SensorChart data={DATA} showTemp showHumidity />
        <SensorChart data={DATA} showTemp showHumidity />
      </>,
    )
    const ids = gradientIds()
    expect(ids.length).toBeGreaterThanOrEqual(4) // 两个实例 × 两条系列
    const duplicated = ids.filter((id, i) => ids.indexOf(id) !== i)
    expect(duplicated, `出现重复渐变 id：${duplicated}`).toEqual([])
  })

  it('渐变颜色取自 lib/metrics（单一真值）', () => {
    render(<SensorChart data={DATA} showTemp />)
    const stops = Array.from(document.querySelectorAll('linearGradient stop')).map((el) =>
      // React 在 SVG 里把 stopColor 渲染为属性 stop-color（大小写敏感）
      el.getAttribute('stop-color'),
    )
    expect(stops).toContain(METRICS.temp.color)
  })

  it('未显示的系列不产生渐变（也不留死引用）', () => {
    render(<SensorChart data={DATA} showTemp={false} showPower={false} />)
    const ids = gradientIds()
    expect(ids.some((id) => id.endsWith('-colorTemp'))).toBe(false)
    expect(ids.some((id) => id.endsWith('-colorPower'))).toBe(false)
  })

  it('cumulative 模式必须把基准/节省系列改绑 *_cum（评审 P1：此前算完没人用）', () => {
    const cumData = [
      { time: '10:00', baseline_cum: 1.5, saving_cum: 1.0 },
      { time: '10:01', baseline_cum: 3.0, saving_cum: 2.0 },
    ]
    render(<SensorChart data={cumData} showBaseline showSaving cumulative />)
    // 图例文案来自 name 属性：累计模式下必须换成"累计电量"，否则图上画的是逐点功率却标成累计
    expect(document.body.textContent).toContain('基线累计电量')
    expect(document.body.textContent).toContain('节能累计电量')

    cleanup()
    render(<SensorChart data={DATA} showBaseline showSaving />)
    expect(document.body.textContent).toContain('基线功率')
    expect(document.body.textContent).not.toContain('基线累计电量')
  })
})
