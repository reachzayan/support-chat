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
      mode: "conversation",
      widget: WIDGET,
      bootstrap_token: "boot-token",
      resume_token: "resume-1",
      conversation: { state: "prechat", assigned_agent: null, messages: [] },
    })

    expect(result?.mode).toBe("conversation")
    if (result?.mode !== "conversation") return
    expect(result?.bootstrap_token).toBe("boot-token")
    expect(result?.conversation).toEqual({
      state: "prechat",
      assigned_agent: null,
      messages: [],
    })
  })

  test("drops a malformed conversation snapshot and keeps the token", () => {
    const result = parseBootstrapResult({
      mode: "conversation",
      widget: WIDGET,
      bootstrap_token: "boot-token",
      conversation: { state: "nope" },
    })

    expect(result?.mode).toBe("conversation")
    if (result?.mode !== "conversation") return
    expect(result?.bootstrap_token).toBe("boot-token")
    expect(result?.conversation).toBeUndefined()
  })

  test("parses identity and history without requiring a socket credential", () => {
    const identity = {
      display_name: "Ada L.",
      email_hint: "a•••@example.com",
      phone_hint: null,
      chat_count: 1,
    }
    expect(parseBootstrapResult({ mode: "identity", widget: WIDGET, identity })).toEqual({
      mode: "identity",
      widget: expect.objectContaining({ name: "SupportChat demo" }),
      identity,
    })
    expect(
      parseBootstrapResult({
        mode: "history",
        widget: WIDGET,
        identity,
        conversations: [
          {
            id: "10000000-0000-4000-8000-000000000001",
            state: "closed",
            inquiry_type: "results",
            created_at: "2026-09-20T12:00:00Z",
            last_message_at: "2026-09-20T12:10:00Z",
            assigned_agent: null,
            is_current: false,
          },
        ],
      }),
    ).toMatchObject({ mode: "history", conversations: [{ state: "closed" }] })
  })
})
