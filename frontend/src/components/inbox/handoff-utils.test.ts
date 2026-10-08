import { describe, expect, test } from "vitest"

import { handoffReasonLabel } from "./handoff-utils"

describe("handoffReasonLabel", () => {
  test("maps known reason codes to human labels", () => {
    expect(handoffReasonLabel("visitor_request")).toBe("Visitor asked for a specialist")
    expect(handoffReasonLabel("retrieval_miss")).toBe("No matching answer found")
  })

  test("humanizes unknown codes", () => {
    expect(handoffReasonLabel("new_weird-code")).toBe("New weird code")
    expect(handoffReasonLabel("")).toBe("Unknown reason")
  })
})
