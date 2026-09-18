import { describe, expect, test } from "vitest"

import { parseBootstrapResult } from "./bootstrap"

const WIDGET = {
  name: "SupportChat demo",
  greeting: "Talk to a specialist about screening.",
  privacy_url: "http://localhost:3000/privacy",
}

describe("widget bootstrap payload", () => {
  test("keeps a prechat conversation snapshot", () => {
    const result = parseBootstrapResult({
      widget: WIDGET,
      bootstrap_token: "boot-token",
      resume_token: "resume-1",
      conversation: { state: "prechat", assigned_agent: null, messages: [] },
    })

    expect(result?.bootstrap_token).toBe("boot-token")
    expect(result?.conversation).toEqual({
      state: "prechat",
      assigned_agent: null,
      messages: [],
    })
  })

  test("drops a malformed conversation snapshot and keeps the token", () => {
    const result = parseBootstrapResult({
      widget: WIDGET,
      bootstrap_token: "boot-token",
      conversation: { state: "nope" },
    })

    expect(result?.bootstrap_token).toBe("boot-token")
    expect(result?.conversation).toBeUndefined()
  })
})
