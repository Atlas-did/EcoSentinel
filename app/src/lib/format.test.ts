import { describe, expect, it } from 'vitest'

import { KG_CO2_PER_TREE_YEAR, treesEquivalent } from '@/lib/format'

describe('treesEquivalent · kg CO2 → 等效树木棵数', () => {
  it('按 20 kg/棵·年 换算', () => {
    expect(treesEquivalent(100)).toBeCloseTo(5)
    expect(treesEquivalent(KG_CO2_PER_TREE_YEAR)).toBeCloseTo(1)
  })

  it('缺失值按 0 处理，不产生 NaN', () => {
    expect(treesEquivalent(null)).toBe(0)
    expect(treesEquivalent(undefined)).toBe(0)
  })

  it('回归哨兵：必须真的除以 20（旧代码 `x ?? 0 / 20` 优先级写错，除以 20 从未生效）', () => {
    // 旧表达式 `100 ?? (0/20)` 会得到 100（≈ 20 棵树），而不是 5
    const result = treesEquivalent(100)
    expect(result).not.toBe(100)
    expect(result).toBe(5)
  })
})
