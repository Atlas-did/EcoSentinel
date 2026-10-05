/**
 * M6.6 · API 层（services/api.ts）契约测试。
 *
 * 锁住 M6.5 定下的可靠性不变量：
 * 1) 失败一律返回 null（调用方按整轮聚合判在线，不靠模块级标志）；
 * 2) 单次请求超时**必须小于轮询间隔 3000ms** —— 这里用假定时器行为化验证，
 *    谁把 2500 改回 5000 都会红（改成 5000 时本文件第二个用例会失败）；
 * 3) 图表端点带上 range 参数（与后端 /api/chart 的契约）。
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchChart, fetchSnapshot } from '@/services/api'

/** 让 fetch 永远不 resolve，只有被 abort 时才 reject（用于验证超时）。 */
function installHangingFetch() {
  const spy = vi.fn((_url: string, init?: RequestInit) => {
    return new Promise((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () =>
        reject(new DOMException('aborted', 'AbortError')),
      )
    })
  })
  vi.stubGlobal('fetch', spy)
  return spy
}

function installFetch(handler: (url: string, init?: RequestInit) => unknown) {
  const spy = vi.fn(handler as (url: string, init?: RequestInit) => Promise<Response>)
  vi.stubGlobal('fetch', spy)
  return spy
}

const POLL_INTERVAL_MS = 3000

describe('services/api · 失败与超时', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('HTTP 非 2xx 时返回 null（不抛异常）', async () => {
    installFetch(() => ({ ok: false, status: 500, json: async () => ({}) }))
    await expect(fetchSnapshot()).resolves.toBeNull()
  })

  it('网络异常时返回 null', async () => {
    installFetch(() => {
      throw new Error('network down')
    })
    await expect(fetchSnapshot()).resolves.toBeNull()
  })

  it('超时后中止请求并返回 null，且超时必须**小于轮询间隔**（3000ms）', async () => {
    installHangingFetch()
    const pending = fetchSnapshot()

    // 推进到轮询间隔（3000ms）：此时请求必须已经因超时而结束
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)

    await expect(pending).resolves.toBeNull()
  })

  it('请求在超时前返回则正常解析 JSON', async () => {
    installFetch(async () => ({ ok: true, status: 200, json: async () => ({ temperature: 25 }) }))
    await expect(fetchSnapshot()).resolves.toEqual({ temperature: 25 })
  })
})

describe('services/api · 端点与参数契约', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('图表端点请求 /api/chart 并带 range 参数', async () => {
    const spy = installFetch(async () => ({ ok: true, status: 200, json: async () => [] }))

    await fetchChart('5m')

    expect(spy).toHaveBeenCalledTimes(1)
    const url = String(spy.mock.calls[0][0])
    expect(url).toContain('/api/chart')
    expect(url).toContain('range=5m')
  })

  it('快照端点请求 /api/snapshot', async () => {
    const spy = installFetch(async () => ({ ok: true, status: 200, json: async () => ({}) }))
    await fetchSnapshot()
    expect(String(spy.mock.calls[0][0])).toContain('/api/snapshot')
  })
})
