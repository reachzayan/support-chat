import { describe, expect, test } from "vitest"

import { safeClientErrorMessage } from "./client-error-reporter"

describe("safeClientErrorMessage", () => {
  test("reports a stable error class without transmitting exception contents", () => {
    const error = new Error("Authorization: Bearer secret visitor@example.com")

    expect(safeClientErrorMessage(error, "Unhandled promise rejection")).toBe("Error")
  })

  test("uses a generic fallback for attacker-controlled rejection strings", () => {
    expect(safeClientErrorMessage("password=hunter2", "Unhandled promise rejection")).toBe(
      "Unhandled promise rejection",
    )
  })
})
