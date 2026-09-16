import { describe, expect, test } from "vitest"

import nextConfig from "../next.config"

const headerValue = (
  rules: { source: string; headers: { key: string; value: string }[] }[],
  source: string,
  key: string,
) => {
  const rule = rules.find((item) => item.source === source)
  return rule?.headers.find((header) => header.key === key)?.value
}

describe("security headers", () => {
  test("widget CSP is not baked at build time and staff HTML cannot be framed", async () => {
    const rules = await nextConfig.headers!()
    expect(headerValue(rules, "/widget", "Content-Security-Policy")).toBeUndefined()
    const staffCsp = headerValue(rules, "/inbox", "Content-Security-Policy")
    expect(staffCsp).toContain("frame-ancestors 'none'")
    expect(staffCsp).toContain("default-src 'self'")
    expect(staffCsp).toContain("script-src 'self' 'unsafe-inline' 'unsafe-eval'")
    expect(staffCsp).toContain("style-src 'self' 'unsafe-inline'")
    expect(staffCsp).toContain("object-src 'none'")
    expect(staffCsp).toContain("base-uri 'self'")
    expect(staffCsp).toContain("form-action 'self'")
    expect(staffCsp).toContain("connect-src")
    expect(headerValue(rules, "/widget", "X-Content-Type-Options")).toBe("nosniff")
    expect(headerValue(rules, "/inbox", "X-Content-Type-Options")).toBe("nosniff")
    expect(headerValue(rules, "/inbox", "Referrer-Policy")).toBe("strict-origin-when-cross-origin")
  })
})
