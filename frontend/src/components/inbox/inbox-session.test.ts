import { describe, expect, test } from "vitest"

import { applyAgentFrame, emptyLive, type InboxLive } from "./inbox-session"
import type { ConversationDetail } from "./types"

const ADA_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
const OTHER_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
const ALEX_ID = "11111111-1111-4111-8111-000000000001"
const ADA_DOT = "How fast are DOT results?"
const OTHER_QUOTE = "Need a package quote"

const otherDetail = {
  id: OTHER_ID,
  site_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
  site_name: "Sample Services",
  state: "queued",
  inquiry_type: null,
  intent: null,
  assigned_agent: null,
  visitor: {
    name: "Other Visitor",
    email: "other@example.com",
    phone: null,
    ip: null,
    user_agent: null,
  },
  page: { title: null, url: null, referrer: null },
  messages: [],
} as unknown as ConversationDetail

const selectedOther = (): InboxLive => ({
  ...emptyLive(),
  chatState: "queued",
  detail: otherDetail,
  lines: [
    {
      id: 2,
      role: "visitor",
      author_user: null,
      body: OTHER_QUOTE,
      source_article_ids: null,
      source_chunk_ids: null,
      created_at: "2026-09-09T15:00:00+00:00",
    },
  ],
})

describe("applyAgentFrame conversation isolation", () => {
  test("Ada DOT frame tagged with Ada's id does not merge into Other Visitor", () => {
    const effect = applyAgentFrame(
      selectedOther(),
      {
        v: 1,
        type: "message",
        id: 40,
        role: "visitor",
        body: ADA_DOT,
        conversation_id: ADA_ID,
      },
      ALEX_ID,
      OTHER_ID,
    )

    expect(effect.live.lines.map((line) => line.body)).toEqual([OTHER_QUOTE])
    expect(effect.live.lines.some((line) => line.body === ADA_DOT)).toBe(false)
  })

  test("Ada human state tagged with Ada's id does not take over Other Visitor", () => {
    const effect = applyAgentFrame(
      selectedOther(),
      {
        v: 1,
        type: "state",
        state: "human",
        conversation_id: ADA_ID,
        assigned_agent: { id: ALEX_ID, display_name: "Alex Morgan" },
      },
      ALEX_ID,
      OTHER_ID,
    )

    expect(effect.live.chatState).toBe("queued")
    expect(effect.live.assigned).toBeNull()
  })
})

describe("applyAgentFrame merges selected conversation", () => {
  test("Other Visitor frame tagged with Other's id does merge", () => {
    const followUp = "Can you quote a county search?"
    const effect = applyAgentFrame(
      selectedOther(),
      {
        v: 1,
        type: "message",
        id: 41,
        role: "visitor",
        body: followUp,
        conversation_id: OTHER_ID,
      },
      ALEX_ID,
      OTHER_ID,
    )

    expect(effect.live.lines.map((line) => line.body)).toEqual([OTHER_QUOTE, followUp])
  })

  test("untagged message still merges into the selected transcript", () => {
    const followUp = "Can you quote a county search?"
    const effect = applyAgentFrame(
      selectedOther(),
      {
        v: 1,
        type: "message",
        id: 41,
        role: "visitor",
        body: followUp,
      },
      ALEX_ID,
      OTHER_ID,
    )

    expect(effect.live.lines.map((line) => line.body)).toEqual([OTHER_QUOTE, followUp])
  })

  test("bot state with a null assigned_agent clears the specialist", () => {
    const live: InboxLive = {
      ...selectedOther(),
      chatState: "human",
      assigned: { id: ALEX_ID, display_name: "Alex Morgan" },
      detail: {
        ...otherDetail,
        state: "human",
        assigned_agent: { id: ALEX_ID, display_name: "Alex Morgan" },
      },
    }
    const effect = applyAgentFrame(
      live,
      {
        v: 1,
        type: "state",
        state: "bot",
        conversation_id: OTHER_ID,
        assigned_agent: null,
      },
      ALEX_ID,
      OTHER_ID,
    )

    expect(effect.live.chatState).toBe("bot")
    expect(effect.live.assigned).toBeNull()
    expect(effect.live.detail?.assigned_agent).toBeNull()
  })
})
