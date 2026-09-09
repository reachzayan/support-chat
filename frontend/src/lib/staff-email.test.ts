import { Effect, Exit } from "effect"
import { describe, expect, test } from "vitest"

import { parseStaffEmail } from "./staff-email"

describe("parseStaffEmail", () => {
  test("trims and lowercases the plan-01 fixture", () => {
    const exit = Effect.runSyncExit(parseStaffEmail("  Alex@example.local "))
    expect(exit).toEqual(Exit.succeed("alex@example.local"))
  })

  test("keeps an already-normalized address", () => {
    const exit = Effect.runSyncExit(parseStaffEmail("agent@example.local"))
    expect(exit).toEqual(Exit.succeed("agent@example.local"))
  })

  test("accepts plus-addressing", () => {
    const exit = Effect.runSyncExit(parseStaffEmail("agent+ops@example.local"))
    expect(exit).toEqual(Exit.succeed("agent+ops@example.local"))
  })

  test("rejects an empty string", () => {
    expect(Exit.isFailure(Effect.runSyncExit(parseStaffEmail("")))).toBe(true)
  })

  test("rejects whitespace-only input", () => {
    expect(Exit.isFailure(Effect.runSyncExit(parseStaffEmail("  \t  ")))).toBe(true)
  })

  test("rejects a string without @", () => {
    expect(Exit.isFailure(Effect.runSyncExit(parseStaffEmail("not-an-email")))).toBe(true)
  })

  test("rejects a domain without a dot", () => {
    expect(Exit.isFailure(Effect.runSyncExit(parseStaffEmail("alex@example")))).toBe(true)
  })

  test("rejects a non-string", () => {
    expect(Exit.isFailure(Effect.runSyncExit(parseStaffEmail(1)))).toBe(true)
  })
})
