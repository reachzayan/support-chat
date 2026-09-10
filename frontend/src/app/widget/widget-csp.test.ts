import { describe, expect, test } from "vitest"

import nextConfig from "../../../next.config"

describe("widget document CSP", () => {
  test("frame-ancestors is the configured union and never a wildcard", async () => {
    const headers = nextConfig.headers
    expect(headers).toBeTypeOf("function")
    const rules = await headers!()
    const widget = rules.find((rule) => rule.source === "/widget")
    const csp = widget?.headers.find((header) => header.key === "Content-Security-Policy")
    expect(csp?.value).toBe("frame-ancestors http://localhost:3000")
    expect(csp?.value.includes("*")).toBe(false)
  })
})
