import { describe, expect, test } from "vitest"

import nextConfig from "../next.config"

describe("API rewrites", () => {
  test("proxies handoff outcome and summary routes to the backend", async () => {
    const rules = await nextConfig.rewrites!()
    const list = Array.isArray(rules)
      ? rules
      : [...(rules.beforeFiles ?? []), ...(rules.afterFiles ?? []), ...(rules.fallback ?? [])]
    const handoff = list.find((rule) => rule.source === "/api/handoffs/:path*")
    expect(handoff?.destination).toBe("http://127.0.0.1:8000/api/handoffs/:path*")
  })

  test("proxies application log routes to the backend", async () => {
    const rules = await nextConfig.rewrites!()
    const list = Array.isArray(rules)
      ? rules
      : [...(rules.beforeFiles ?? []), ...(rules.afterFiles ?? []), ...(rules.fallback ?? [])]
    const logs = list.find((rule) => rule.source === "/api/logs/:path*")
    expect(logs?.destination).toBe("http://127.0.0.1:8000/api/logs/:path*")
  })

  test("proxies visitor block routes to the backend", async () => {
    const rules = await nextConfig.rewrites!()
    const list = Array.isArray(rules)
      ? rules
      : [...(rules.beforeFiles ?? []), ...(rules.afterFiles ?? []), ...(rules.fallback ?? [])]
    const exact = list.find((rule) => rule.source === "/api/visitor-blocks")
    const nested = list.find((rule) => rule.source === "/api/visitor-blocks/:path*")
    expect(exact?.destination).toBe("http://127.0.0.1:8000/api/visitor-blocks")
    expect(nested?.destination).toBe("http://127.0.0.1:8000/api/visitor-blocks/:path*")
  })
})
