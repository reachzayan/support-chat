import { screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, test } from "vitest"

import {
  CONVO_ID,
  FakeSocket,
  OTHER_CONVO,
  adaQueued,
  emit,
  openQueuedAda,
  resetInboxHarness,
} from "./inbox-test-harness"

const ADA_DOT = "How fast are DOT results?"

describe("inbox conversation isolation", () => {
  beforeEach(() => {
    resetInboxHarness()
  })

  test("Ada DOT line does not appear after selecting Other Visitor", async () => {
    const user = await openQueuedAda()
    await waitFor(() => expect(screen.getAllByText(ADA_DOT).length).toBeGreaterThan(0))
    await user.click(screen.getByRole("button", { name: /Other Visitor/ }))
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Other Visitor" })).toBeInTheDocument(),
    )
    const transcript = screen.getByRole("log", { name: "Transcript" })
    expect(transcript).not.toHaveTextContent(ADA_DOT)
    expect(screen.queryByText("Visitor")).not.toBeInTheDocument()

    emit(FakeSocket.instances[0], {
      v: 1,
      type: "message",
      id: 40,
      role: "visitor",
      body: ADA_DOT,
      conversation_id: CONVO_ID,
    })

    expect(transcript).not.toHaveTextContent(ADA_DOT)
    expect(screen.queryByText("Visitor")).not.toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Other Visitor" })).toBeInTheDocument()
  })

  test("origin close 4403 does not open another agent socket", async () => {
    await openQueuedAda()
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    FakeSocket.instances[0]?.close(4403)
    await new Promise((resolve) => setTimeout(resolve, 80))
    expect(FakeSocket.instances.length).toBe(1)
  })

  test("auth close 4401 without a refreshed token does not open another socket", async () => {
    await openQueuedAda()
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    FakeSocket.instances[0]?.close(4401)
    await new Promise((resolve) => setTimeout(resolve, 80))
    expect(FakeSocket.instances.length).toBe(1)
  })
})

describe("inbox subscribe replace", () => {
  beforeEach(() => {
    resetInboxHarness()
  })

  test("selecting Other Visitor subscribes that conversation last", async () => {
    const user = await openQueuedAda()
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    await user.click(screen.getByRole("button", { name: /Other Visitor/ }))
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Other Visitor" })).toBeInTheDocument(),
    )
    const subscribes = (FakeSocket.instances[0]?.sent ?? [])
      .map((raw) => JSON.parse(raw) as { type?: string; conversation_id?: string })
      .filter((frame) => frame.type === "subscribe")
    expect(subscribes.at(-1)?.conversation_id).toBe(OTHER_CONVO)
    expect(adaQueued.id).toBe(CONVO_ID)
  })
})
