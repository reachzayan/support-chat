import { screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, test } from "vitest"

import {
  ALEX,
  CONVO_ID,
  FakeSocket,
  HOURS_BODY,
  OTHER_CONVO,
  adaDetail,
  bgDetail,
  emitAlexJoined,
  openQueuedAda,
  resetInboxHarness,
  setDetails,
} from "./inbox-test-harness"

describe("inbox canned replies", () => {
  beforeEach(() => {
    resetInboxHarness()
  })

  test("expands #hours for SampleSite only and does not send until Send", async () => {
    const user = await openQueuedAda()
    await waitFor(() => expect(FakeSocket.instances.length).toBe(1))
    emitAlexJoined(FakeSocket.instances[0])
    await waitFor(() => expect(screen.getByLabelText("Message")).toBeEnabled())
    const composer = screen.getByLabelText("Message")
    await user.type(composer, "#hours")
    await user.keyboard("{Tab}")
    expect(composer).toHaveValue(HOURS_BODY)
    const sentBefore = FakeSocket.instances[0]?.sent.filter((raw) =>
      raw.includes('"type":"message"'),
    ).length
    expect(sentBefore).toBe(0)
    setDetails({
      [CONVO_ID]: structuredClone(adaDetail),
      [OTHER_CONVO]: {
        ...bgDetail,
        state: "human",
        assigned_agent: { id: ALEX.id, display_name: ALEX.display_name },
      },
    })
    await user.click(screen.getByRole("button", { name: /Other Visitor/ }))
    await waitFor(() => expect(screen.getByLabelText("Message")).toBeEnabled())
    const otherComposer = screen.getByLabelText("Message")
    await user.clear(otherComposer)
    await user.type(otherComposer, "#hours")
    await user.keyboard("{Tab}")
    expect(otherComposer).toHaveValue("#hours")
  })
})
