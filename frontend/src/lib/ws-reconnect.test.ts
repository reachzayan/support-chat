import { afterEach, beforeEach, describe, expect, test, vi } from "vitest"

import { createReconnectScheduler, reconnectDelayMs } from "./ws-reconnect"

describe("reconnectDelayMs", () => {
  test("full jitter stays within the exponential ceiling", () => {
    expect(reconnectDelayMs(0, 500, 30_000, () => 0)).toBe(0)
    expect(reconnectDelayMs(0, 500, 30_000, () => 0.999)).toBe(499)
    expect(reconnectDelayMs(3, 500, 30_000, () => 0.5)).toBe(2000)
    expect(reconnectDelayMs(10, 500, 30_000, () => 1)).toBe(30_000)
  })
})

const withFakeTimers = () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })
}

describe("createReconnectScheduler backoff", () => {
  withFakeTimers()

  test("waits with backoff before reconnecting", () => {
    const onReconnect = vi.fn()
    const scheduler = createReconnectScheduler({
      baseMs: 500,
      capMs: 30_000,
      random: () => 0.5,
      onReconnect,
    })

    scheduler.handleClose()
    expect(onReconnect).not.toHaveBeenCalled()
    vi.advanceTimersByTime(249)
    expect(onReconnect).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1)
    expect(onReconnect).toHaveBeenCalledTimes(1)

    scheduler.handleClose()
    vi.advanceTimersByTime(499)
    expect(onReconnect).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(1)
    expect(onReconnect).toHaveBeenCalledTimes(2)
  })
})

describe("createReconnectScheduler auth reset", () => {
  withFakeTimers()

  test("resets attempt after authenticated success", () => {
    const onReconnect = vi.fn()
    const scheduler = createReconnectScheduler({
      baseMs: 500,
      capMs: 30_000,
      random: () => 0,
      onReconnect,
    })

    scheduler.handleClose()
    vi.advanceTimersByTime(500)
    scheduler.markAuthenticated()
    scheduler.handleClose()
    vi.advanceTimersByTime(500)
    expect(onReconnect).toHaveBeenCalledTimes(2)
  })
})

describe("createReconnectScheduler guards", () => {
  withFakeTimers()

  test("does not reconnect while disposed", () => {
    const onReconnect = vi.fn()
    const scheduler = createReconnectScheduler({
      baseMs: 100,
      capMs: 30_000,
      random: () => 0,
      isDisposed: () => true,
      onReconnect,
    })
    scheduler.handleClose()
    vi.advanceTimersByTime(200)
    expect(onReconnect).not.toHaveBeenCalled()
  })

  test("does not reconnect while hidden", () => {
    const onReconnect = vi.fn()
    const scheduler = createReconnectScheduler({
      baseMs: 100,
      capMs: 30_000,
      random: () => 0,
      isVisible: () => false,
      onReconnect,
    })
    scheduler.handleClose()
    vi.advanceTimersByTime(200)
    expect(onReconnect).not.toHaveBeenCalled()
  })

  test("does not reconnect while offline", () => {
    const onReconnect = vi.fn()
    const scheduler = createReconnectScheduler({
      baseMs: 100,
      capMs: 30_000,
      random: () => 0,
      isOnline: () => false,
      onReconnect,
    })
    scheduler.handleClose()
    vi.advanceTimersByTime(200)
    expect(onReconnect).not.toHaveBeenCalled()
  })
})

describe("createReconnectScheduler dispose", () => {
  withFakeTimers()

  test("dispose cancels a pending reconnect", () => {
    const onReconnect = vi.fn()
    const scheduler = createReconnectScheduler({
      baseMs: 500,
      capMs: 30_000,
      random: () => 0,
      onReconnect,
    })

    scheduler.handleClose()
    scheduler.dispose()
    vi.advanceTimersByTime(500)
    expect(onReconnect).not.toHaveBeenCalled()
  })
})
