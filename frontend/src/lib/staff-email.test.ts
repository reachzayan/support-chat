import { describe, expect, test } from "vitest"

import { parseStaffEmail } from "./staff-email"

describe("parseStaffEmail", () => {
  test("trims and lowercases the plan-01 fixture", () => {
    expect(parseStaffEmail("  Alex@example.local ")).toBe("alex@example.local")
  })

  test("keeps an already-normalized address", () => {
    expect(parseStaffEmail("agent@example.local")).toBe("agent@example.local")
  })

  test("accepts plus-addressing", () => {
    expect(parseStaffEmail("agent+ops@example.local")).toBe("agent+ops@example.local")
  })

  test("rejects an empty string", () => {
    expect(parseStaffEmail("")).toBeNull()
  })

  test("rejects whitespace-only input", () => {
    expect(parseStaffEmail("  \t  ")).toBeNull()
  })

  test("rejects a string without @", () => {
    expect(parseStaffEmail("not-an-email")).toBeNull()
  })

  test("rejects a domain without a dot", () => {
    expect(parseStaffEmail("alex@example")).toBeNull()
  })
})
