/**
 * PrecisionKnob · 拖动期间窗口监听的注册/注销必须成对。
 *
 * 旧实现注册 pointerup 时传一个内联箭头函数、注销时传**另一个**内联箭头函数，
 * removeEventListener 按引用匹配 ⇒ 静默失败、监听器永不解除（真实泄漏）；
 * 又因 handlePointerMove 随 value 变化重建 effect，拖动中监听器还会持续累积。
 */
import { act, cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import PrecisionKnob from '@/components/common/PrecisionKnob'

type Entry = { type: string; fn: unknown }

function trackWindowListeners() {
  const added: Entry[] = []
  const removed: Entry[] = []
  vi.spyOn(window, 'addEventListener').mockImplementation(((type: string, fn: unknown) => {
    added.push({ type, fn })
  }) as never)
  vi.spyOn(window, 'removeEventListener').mockImplementation(((type: string, fn: unknown) => {
    removed.push({ type, fn })
  }) as never)
  return { added, removed }
}

function renderKnob() {
  return render(<PrecisionKnob value={24} onChange={() => {}} />)
}

/** 旋钮本体（带 onPointerDown 的那个 div）；外层是 flex 包装 div，不能拿 firstElementChild。 */
function knobOf(container: HTMLElement): Element {
  const knob = container.querySelector('.cursor-grab')
  if (!knob) throw new Error('未找到旋钮本体（.cursor-grab）⇒ 测试会空过，必须失败')
  return knob
}

/** 按下旋钮开始拖动；并断言确实注册了 pointerup（否则测试空过）。 */
function startDrag(container: HTMLElement, added: Entry[]) {
  fireEvent.pointerDown(knobOf(container), { bubbles: true })
  const up = added.find((a) => a.type === 'pointerup')
  if (!up) throw new Error('拖动未注册 pointerup ⇒ 测试会空过，必须失败')
  return up
}

describe('PrecisionKnob · 事件监听生命周期', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('开始拖动时注册 pointermove 与 pointerup', () => {
    const { added } = trackWindowListeners()
    const { container } = renderKnob()

    startDrag(container, added)

    const types = added.map((a) => a.type)
    expect(types).toContain('pointermove')
    expect(types).toContain('pointerup')
  })

  it('卸载时注销的是注册时的**同一个函数**（旧实现移除另一个匿名函数 ⇒ 永久泄漏）', () => {
    const { added, removed } = trackWindowListeners()
    const { container, unmount } = renderKnob()

    const registeredUp = startDrag(container, added)
    unmount()

    const removedUps = removed.filter((r) => r.type === 'pointerup').map((r) => r.fn)
    expect(removedUps, '卸载后未注销 pointerup').toContain(registeredUp.fn)
  })

  it('pointerup 触发后结束拖动，并清理 pointermove/pointerup', () => {
    const { added, removed } = trackWindowListeners()
    const { container } = renderKnob()

    const up = startDrag(container, added).fn as () => void

    // 调用真实处理器：isDragging 复位 ⇒ effect 依赖变化 ⇒ 走 cleanup
    act(() => {
      up()
    })

    const removedTypes = removed.map((r) => r.type)
    expect(removedTypes).toContain('pointermove')
    expect(removedTypes).toContain('pointerup')
  })
})
