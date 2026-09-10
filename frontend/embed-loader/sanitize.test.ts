import { describe, expect, test } from "vitest"

import { sanitizePageUrl } from "./sanitize"

describe("page URL sanitization", () => {
  test("keeps https origin and path, strips query and fragment, and rejects javascript", () => {
    expect(sanitizePageUrl("https://sample-site.example.com/dot?q=1#top")).toBe(
      "https://sample-site.example.com/dot",
    )
    expect(sanitizePageUrl("javascript:alert(1)")).toBe("")
    expect(sanitizePageUrl("ftp://files.example/x")).toBe("")
  })
})
