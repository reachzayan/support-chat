import { describe, expect, test } from "vitest"

import nextConfig from "../next.config"

describe("legacy console paths", async () => {
  const redirects = await nextConfig.redirects!()
  const bySource = new Map(redirects.map((rule) => [rule.source, rule]))

  test.each([
    "inbox",
    "sites",
    "knowledge",
    "settings",
    "data",
    "status",
    "logs",
    "blocked",
    "canned-responses",
    "suggested-faqs",
    "notifications",
  ])("/%s redirects permanently to /admin/%s, keeping nested paths", (path) => {
    expect(bySource.get(`/${path}`)).toMatchObject({
      destination: `/admin/${path}`,
      permanent: true,
    })
    expect(bySource.get(`/${path}/:path*`)).toMatchObject({
      destination: `/admin/${path}/:path*`,
      permanent: true,
    })
  })
})
