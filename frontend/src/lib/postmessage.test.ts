import { describe, expect, test } from "vitest"
/* oxlint-disable max-lines-per-function -- protocol cases stay grouped as one contract */

import {
  parseHostToWidget,
  parseWidgetToHost,
  WIDGET_RESIZE_MAX,
  WIDGET_RESIZE_MIN,
} from "./postmessage"

describe("host to widget frames", () => {
  test("accepts bootstrap with widget config and page fields", () => {
    const frame = parseHostToWidget({
      type: "host.bootstrap",
      bootstrap_token: "tok",
      widget: {
        name: "SupportChat demo",
        greeting: "Talk to a specialist about screening.",
        privacy_url: "http://localhost:3000/privacy",
      },
      page_url: "http://localhost:3000/demo",
      page_title: "Testing LiveChat inhouse",
      referrer: "",
    })

    expect(frame?.type).toBe("host.bootstrap")
    if (frame?.type !== "host.bootstrap") {
      return
    }
    expect(frame.widget.name).toBe("SupportChat demo")
    expect(frame.bootstrap_token).toBe("tok")
    expect(frame.conversation).toBeUndefined()
  })

  test("accepts a prechat conversation snapshot on bootstrap", () => {
    const frame = parseHostToWidget({
      type: "host.bootstrap",
      bootstrap_token: "tok",
      widget: {
        name: "SupportChat demo",
        greeting: "Talk to a specialist about screening.",
        privacy_url: "http://localhost:3000/privacy",
      },
      page_url: "http://localhost:3000/demo",
      page_title: "Testing LiveChat inhouse",
      referrer: "",
      conversation: {
        state: "prechat",
        assigned_agent: null,
        messages: [],
      },
    })

    expect(frame?.type).toBe("host.bootstrap")
    if (frame?.type !== "host.bootstrap") {
      return
    }
    expect(frame.conversation).toEqual({
      state: "prechat",
      assigned_agent: null,
      messages: [],
    })
  })

  test("keeps bootstrap when the conversation snapshot is malformed", () => {
    const frame = parseHostToWidget({
      type: "host.bootstrap",
      bootstrap_token: "tok",
      widget: {
        name: "SupportChat demo",
        greeting: "Talk to a specialist about screening.",
        privacy_url: "http://localhost:3000/privacy",
      },
      page_url: "http://localhost:3000/demo",
      page_title: "Testing LiveChat inhouse",
      referrer: "",
      conversation: { state: "nope", messages: [] },
    })

    expect(frame?.type).toBe("host.bootstrap")
    if (frame?.type !== "host.bootstrap") {
      return
    }
    expect(frame.conversation).toBeUndefined()
  })

  test("rejects unknown host types", () => {
    expect(parseHostToWidget({ type: "host.hack" })).toBeNull()
  })

  test("accepts masked identity and metadata-only history frames", () => {
    const widget = {
      name: "SupportChat demo",
      greeting: "Talk to a specialist about screening.",
      privacy_url: "http://localhost:3000/privacy",
    }
    expect(
      parseHostToWidget({
        type: "host.identity",
        widget,
        identity: {
          display_name: "Ada L.",
          email_hint: "a•••@example.com",
          phone_hint: "••• ••• 0198",
          chat_count: 2,
        },
      }),
    ).toMatchObject({ type: "host.identity", identity: { display_name: "Ada L.", chat_count: 2 } })

    expect(
      parseHostToWidget({
        type: "host.history",
        widget,
        identity: {
          display_name: "Ada L.",
          email_hint: "a•••@example.com",
          phone_hint: null,
          chat_count: 1,
        },
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
    ).toMatchObject({ type: "host.history", conversations: [{ state: "closed" }] })
  })
})

describe("widget to host frames", () => {
  test("accepts resize only between 320 and 720", () => {
    expect(WIDGET_RESIZE_MIN).toBe(320)
    expect(WIDGET_RESIZE_MAX).toBe(720)
    expect(parseWidgetToHost({ type: "widget.resize", height: 600 })).toEqual({
      type: "widget.resize",
      height: 600,
    })
    expect(parseWidgetToHost({ type: "widget.resize", height: 5000 })).toBeNull()
    expect(parseWidgetToHost({ type: "widget.resize", height: 100 })).toBeNull()
  })

  test("accepts widget.painted", () => {
    expect(parseWidgetToHost({ type: "widget.painted" })).toEqual({ type: "widget.painted" })
  })

  test("accepts only closed resume actions with bounded identifiers", () => {
    const conversationId = "10000000-0000-4000-8000-000000000001"
    expect(parseWidgetToHost({ type: "widget.show_history" })).toEqual({
      type: "widget.show_history",
    })
    expect(parseWidgetToHost({ type: "widget.reset_current" })).toEqual({
      type: "widget.reset_current",
    })
    expect(parseWidgetToHost({ type: "widget.delete_all" })).toEqual({
      type: "widget.delete_all",
    })
    expect(
      parseWidgetToHost({
        type: "widget.open_conversation",
        conversation_id: conversationId,
        replace_current: true,
      }),
    ).toEqual({
      type: "widget.open_conversation",
      conversation_id: conversationId,
      replace_current: true,
    })
    expect(
      parseWidgetToHost({ type: "widget.open_conversation", conversation_id: "../other" }),
    ).toBeNull()
  })

  test("rejects unknown widget types", () => {
    expect(parseWidgetToHost({ type: "widget.explode" })).toBeNull()
  })
})
