import { describe, expect, test } from "vitest"

import { applyVisitorFrame, emptyChat } from "./visitor-session"

const VISITOR_LINE = "How fast are results?"

describe("visitor session view", () => {
  test("prechat state drops prior canonical lines and assignment", () => {
    let view = emptyChat()
    view = applyVisitorFrame(view, {
      type: "message",
      id: 11,
      role: "visitor",
      body: VISITOR_LINE,
    })
    view = applyVisitorFrame(view, {
      type: "state",
      state: "human",
      assigned_agent: { display_name: "Alex Morgan" },
    })
    view = applyVisitorFrame(view, { type: "state", state: "prechat", assigned_agent: null })

    expect(view.conversation).toBe("prechat")
    expect(view.lines).toEqual([])
    expect(view.assignedName).toBeNull()
    expect(view.lastEventId).toBe(0)
  })

  test("the same canonical id is kept once", () => {
    let view = emptyChat()
    view = applyVisitorFrame(view, {
      type: "message",
      id: 12,
      role: "visitor",
      body: "still there?",
    })
    view = applyVisitorFrame(view, {
      type: "message",
      id: 12,
      role: "visitor",
      body: "still there?",
    })

    expect(view.lines).toEqual([
      {
        id: 12,
        role: "visitor",
        body: "still there?",
        source_chunk_ids: null,
        source_urls: null,
        display_locator: null,
        source_title: null,
        system_reason: null,
      },
    ])
    expect(view.lastEventId).toBe(12)
  })

  test("typing frames toggle the assistant indicator without adding a line", () => {
    let view = emptyChat()
    view = applyVisitorFrame(view, { v: 1, type: "state", state: "bot", assigned_agent: null })
    view = applyVisitorFrame(view, { v: 1, type: "typing", active: true })

    expect(view.typing).toBe(true)
    expect(view.lines).toEqual([])

    view = applyVisitorFrame(view, { v: 1, type: "typing", active: false })
    expect(view.typing).toBe(false)
  })

  test("prechat state clears a live typing indicator", () => {
    let view = emptyChat()
    view = applyVisitorFrame(view, { v: 1, type: "typing", active: true })
    view = applyVisitorFrame(view, { type: "state", state: "prechat", assigned_agent: null })

    expect(view.conversation).toBe("prechat")
    expect(view.typing).toBe(false)
  })
})
