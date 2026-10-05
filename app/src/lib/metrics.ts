/**
 * M6.3 · 前端指标单一真值（`ChartDataPoint` 命名空间）。
 *
 * 此前同一份指标键集被复制了两份：
 *   - `components/charts/SensorChart.tsx`：9 个 `dataKey="..."` 字面量
 *   - `pages/RealtimePage.tsx`：`sensorConfigs`（键 + label/unit/color/threshold）
 * 改一个键名要改两处、且 tsc 不会报错（字符串字面量）。
 *
 * 这里集中定义。**注意命名空间**：本表是"图表数据键"（temp/eco2/power_w…）；
 * `HealthPage` 的 `sensorIcons` 用的是后端 `SensorHealth` 的开关字段（temperature/power/solar…），
 * 属于另一个命名空间，因此不并入本表（改由契约测试保证其键来自后端 schema）。
 */

import type { LucideIcon } from 'lucide-react'
import {
  Droplets,
  Sun,
  Thermometer,
  Wind,
  Zap,
} from 'lucide-react'

import type { ChartDataPoint } from '@/types'

/** 图表数据键 */
export type MetricKey = keyof Pick<
  ChartDataPoint,
  | 'temp'
  | 'humidity'
  | 'illuminance'
  | 'eco2'
  | 'power_w'
  | 'solar_power_w'
  | 'baseline_power'
  | 'saving_power'
  | 'comfort_score'
>

export interface MetricSpec {
  label: string
  unit: string
  color: string
  /** 展示用图标（集中在表里，页面不再各自 import 图标） */
  icon: LucideIcon
  /** 上限阈值；超过视为"需要关注"。null = 不设阈值 */
  threshold: number | null
  /** 实时页默认是否显示该曲线 */
  defaultActive: boolean
  /**
   * 是否参与"异常点"横幅判定。
   * ⚠️ 与阈值不同：阈值可统一，但**监视哪些指标是行为**，改动会让横幅多报/少报，
   * 因此单独用一个开关，保持与重构前完全一致（只监视 temp 与 eco2）。
   */
  anomalyWatch: boolean
  /** 阈值来源说明（写清出处，避免以后再出现两个数各说各话） */
  thresholdNote?: string
}

export const METRICS: Record<MetricKey, MetricSpec> = {
  temp: {
    label: '温度',
    unit: '°C',
    color: '#f97316',
    icon: Thermometer,
    threshold: 30,
    defaultActive: true,
    anomalyWatch: true,
    thresholdNote: '室内温度高于 30°C 视为需要关注',
  },
  humidity: {
    label: '湿度',
    unit: '%',
    color: '#3b82f6',
    icon: Droplets,
    threshold: 80,
    defaultActive: true,
    anomalyWatch: false,
  },
  illuminance: {
    label: '光照',
    unit: 'lx',
    color: '#eab308',
    icon: Sun,
    threshold: 1000,
    defaultActive: true,
    anomalyWatch: false,
  },
  eco2: {
    label: 'eCO2',
    unit: 'ppm',
    color: '#06b6d4',
    icon: Wind,
    // 2026-10 统一为 1000：页内原有两个值（显示 1200 / 异常判定 1000）。
    // 1000 ppm 是 ASHRAE / GB 类标准里的"需要通风/投诉"阈值，且与异常判定的既有取值一致。
    threshold: 1000,
    defaultActive: false,
    anomalyWatch: true,
    thresholdNote: '1000 ppm：通风/投诉阈值（统一后与异常判定一致）',
  },
  power_w: {
    label: '功率',
    unit: 'W',
    color: '#ef4444',
    icon: Zap,
    threshold: 20,
    defaultActive: true,
    anomalyWatch: false,
  },
  solar_power_w: {
    label: '太阳能',
    unit: 'W',
    // 以 SensorChart 现有渐变为准（渲染真相），不因"统一"而改变视觉
    color: '#eab308',
    icon: Sun,
    threshold: null,
    defaultActive: false,
    anomalyWatch: false,
  },
  baseline_power: {
    label: '基准功率',
    unit: 'W',
    // 以 SensorChart 现有渐变为准（渲染真相）
    color: '#94a3b8',
    icon: Zap,
    threshold: null,
    defaultActive: false,
    anomalyWatch: false,
  },
  saving_power: {
    label: '节省功率',
    unit: 'W',
    color: '#10b981',
    icon: Zap,
    threshold: null,
    defaultActive: false,
    anomalyWatch: false,
  },
  comfort_score: {
    label: '舒适度',
    unit: '',
    color: '#8b5cf6',
    icon: Thermometer,
    threshold: null,
    defaultActive: false,
    anomalyWatch: false,
  },
}

/** 实时页按顺序展示的指标 */
export const REALTIME_METRICS: MetricKey[] = ['temp', 'humidity', 'illuminance', 'eco2', 'power_w']

/** 实时页默认开/关状态（由 defaultActive 派生，集中一处） */
export function defaultActiveSensors(): Record<string, boolean> {
  return Object.fromEntries(
    Object.entries(METRICS).map(([key, spec]) => [key, spec.defaultActive]),
  )
}

/** 只要阈值与监视开关都命中，就算一个异常点（阈值取自本表，不再各写一份）。 */
export function isAnomalous(point: ChartDataPoint): boolean {
  return (Object.keys(METRICS) as MetricKey[]).some((key) => {
    const spec = METRICS[key]
    if (!spec.anomalyWatch || spec.threshold === null) return false
    const value = point[key]
    return typeof value === 'number' && value > spec.threshold
  })
}

/** 异常点列表（实时页横幅用） */
export function anomaliesOf(points: ChartDataPoint[]): ChartDataPoint[] {
  return points.filter(isAnomalous)
}
