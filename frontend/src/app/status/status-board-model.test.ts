import { describe, expect, test } from "vitest"

import { latencySparkPath } from "./status-board-model"

describe("latency spark path", () => {
  test("empty hours produce no path", () => {
    expect(latencySparkPath(Array.from({ length: 24 }, () => null))).toBeNull()
  })

  test("samples only in the last four hours do not fill from the left edge", () => {
    const hours = [...Array.from({ length: 20 }, () => null), 10, 20, 42, 12]
    const spark = latencySparkPath(hours)
    expect(spark).not.toBeNull()
    // 20 / 23 * 120 = 104.347... first sample sits near the right, not at x=0
    expect(spark?.area).toContain("104.3")
    expect(spark?.area.startsWith("M 0")).toBe(false)
    expect(spark?.line.startsWith("M 0")).toBe(false)
  })

  test("a single sample at the current hour is a short mark on the right", () => {
    const hours = [...Array.from({ length: 23 }, () => null), 18]
    const spark = latencySparkPath(hours)
    expect(spark).not.toBeNull()
    expect(spark?.area.startsWith("M 0")).toBe(false)
    expect(spark?.area).toContain("120.0")
  })
})
