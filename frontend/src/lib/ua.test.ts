import { describe, expect, test } from "vitest"

import { parseUserAgent, safeHttpUrl } from "./ua"

const CHROME_MAC =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

describe("parseUserAgent", () => {
  test("maps the frozen Chrome macOS fixture", () => {
    expect(parseUserAgent(CHROME_MAC)).toEqual({ browser: "Chrome", os: "macOS" })
  })
})

describe("safeHttpUrl", () => {
  test("keeps http and https and rejects unsafe schemes", () => {
    expect(safeHttpUrl("https://sample-site.example.com/dot")).toBe("https://sample-site.example.com/dot")
    expect(safeHttpUrl("http://localhost:3000/portal")).toBe("http://localhost:3000/portal")
    expect(safeHttpUrl("javascript:alert(1)")).toBeNull()
    expect(safeHttpUrl("data:text/html,hi")).toBeNull()
  })
})
