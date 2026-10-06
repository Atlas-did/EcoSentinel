/**
 * `meanOf` 的性质断言（把评审 P1 的"空列表除零 NaN"固化下来）。
 *
 * 这条门禁的关键性质：**任何输入都不得产出 NaN/Infinity**。
 */

import { describe, expect, it } from 'vitest'

import { meanOf } from '@/lib/stats'

describe('meanOf · 空集合与异常输入不得产出 NaN', () => {
  it('空数组返回 0（而不是 0/0 = NaN）—— 这正是评审指出的界面缺陷', () => {
    const result = meanOf([])
    expect(result).toBe(0)
    expect(Number.isNaN(result)).toBe(false)
  })

  it('常规均值正确', () => {
    expect(meanOf([1, 2, 3])).toBe(2)
    expect(meanOf([0.5, 1.5])).toBe(1)
    expect(meanOf([7])).toBe(7)
  })

  it('含非有限值时忽略它们（也不让结果变成 NaN/Infinity）', () => {
    expect(meanOf([1, NaN, 3])).toBe(2)
    expect(meanOf([Infinity, 2])).toBe(2) // Infinity 被忽略，只对有限值求均值
    expect(Number.isFinite(meanOf([NaN, Infinity]))).toBe(true)
    expect(meanOf([NaN, Infinity])).toBe(0)
  })

  it('全零与负数也稳定', () => {
    expect(meanOf([0, 0])).toBe(0)
    expect(meanOf([-2, -4])).toBe(-3)
  })
})
