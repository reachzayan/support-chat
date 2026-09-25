import { describe, expect, test } from "vitest"

import nextConfig from "../next.config"
import { staffDocumentCsp } from "./proxy"

const headerValue = (
  rules: { source: string; headers: { key: string; value: string }[] }[],
  source: string,
  key: string,
) => {
  const rule = rules.find((item) => item.source === source)
  return rule?.headers.find((header) => header.key === key)?.value
}

describe("security headers", () => {
  test("widget CSP is not baked at build time and staff CSP uses nonces", async () => {
    const rules = await nextConfig.headers!()
    expect(headerValue(rules, "/widget", "Content-Security-Policy")).toBeUndefined()
    expect(headerValue(rules, "/widget", "Referrer-Policy")).toBe("no-referrer")
    expect(headerValue(rules, "/admin/:path*", "Content-Security-Policy")).toBeUndefined()
    expect(headerValue(rules, "/login", "Content-Security-Policy")).toBeUndefined()
    expect(headerValue(rules, "/widget", "X-Content-Type-Options")).toBe("nosniff")
    expect(headerValue(rules, "/admin/:path*", "X-Content-Type-Options")).toBe("nosniff")
    expect(headerValue(rules, "/admin/:path*", "Referrer-Policy")).toBe(
      "strict-origin-when-cross-origin",
    )

    const staffCsp = staffDocumentCsp("test-nonce")
    expect(staffCsp).toContain("frame-ancestors 'none'")
    expect(staffCsp).toContain("default-src 'self'")
    expect(staffCsp).toContain("script-src 'self' 'nonce-test-nonce' 'strict-dynamic'")
    expect(staffCsp).not.toContain("unsafe-eval")
    expect(staffCsp).not.toMatch(/script-src[^;]*'unsafe-inline'/)
    expect(staffCsp).toContain("style-src 'self' 'unsafe-inline'")
    expect(staffCsp).toContain("object-src 'none'")
    expect(staffCsp).toContain("base-uri 'self'")
    expect(staffCsp).toContain("form-action 'self'")
    expect(staffCsp).toContain("connect-src")
  })
})
