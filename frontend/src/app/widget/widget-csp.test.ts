import { describe, expect, test } from "vitest"

import nextConfig from "../../../next.config"

describe("widget document CSP", () => {
  test("next.config does not bake a static frame-ancestors union", async () => {
    const headers = nextConfig.headers
    expect(headers).toBeTypeOf("function")
    const rules = await headers!()
    const widget = rules.find((rule) => rule.source === "/widget")
    const csp = widget?.headers.find((header) => header.key === "Content-Security-Policy")
    expect(csp).toBeUndefined()
  })
})
