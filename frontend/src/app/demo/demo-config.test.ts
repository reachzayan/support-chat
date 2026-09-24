import { describe, expect, test } from "vitest"

import { embedConfigMarkup, readDemoWidgetConfig } from "./demo-config"

describe("embedConfigMarkup", () => {
  test("keeps deployment configuration inside the script element", () => {
    const markup = embedConfigMarkup("demo</script><script>alert(1)</script>", "public<key")
    const html = Object.values(markup)[0]

    expect(html).not.toContain("</script>")
    expect(html).toContain("demo\\u003c/script>")
    expect(html).toContain("public\\u003ckey")
  })
})

describe("readDemoWidgetConfig", () => {
  test("rejects site and public keys outside the expected character set", () => {
    const original = { ...process.env }
    process.env.NEXT_PUBLIC_WIDGET_ORIGIN = "http://widget.localhost:3000"
    process.env.NEXT_PUBLIC_STAFF_APP_ORIGIN = "http://localhost:3000"
    process.env.NEXT_PUBLIC_DEMO_SITE_KEY = "Demo Key"
    process.env.NEXT_PUBLIC_DEMO_PUBLIC_KEY = "ab".repeat(32)
    expect(() => readDemoWidgetConfig()).toThrow(/site key/)
    process.env.NEXT_PUBLIC_DEMO_SITE_KEY = "website-demo"
    process.env.NEXT_PUBLIC_DEMO_PUBLIC_KEY = "not-hex"
    expect(() => readDemoWidgetConfig()).toThrow(/public key/)
    process.env = original
  })
})
