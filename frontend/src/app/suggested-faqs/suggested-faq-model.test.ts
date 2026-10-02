import { describe, expect, test } from "vitest"

import { suggestShortcut } from "./suggested-faq-model"

describe("suggestShortcut", () => {
  test("keeps the meaningful words of a visitor question", () => {
    expect(suggestShortcut("How do I enroll a driver?")).toBe("enroll_driver")
    expect(suggestShortcut("What is the enrollment process?")).toBe("enrollment_process")
  })

  test("stops after three words so the picker stays readable", () => {
    expect(suggestShortcut("Can you explain random pool selection for owner operators")).toBe(
      "explain_random_pool",
    )
  })

  test("fits the 40 character shortcut limit without a trailing underscore", () => {
    expect(suggestShortcut("internationalization documentation requirements")).toBe(
      "internationalization_documentation_requi",
    )
    expect(suggestShortcut("internationalization internationalization")).toBe(
      "internationalization_internationalizatio",
    )
    expect(suggestShortcut(`${"a".repeat(39)} more`)).toBe("a".repeat(39))
  })

  test("falls back to a plain word when nothing meaningful is left", () => {
    expect(suggestShortcut("How do I?")).toBe("faq")
    expect(suggestShortcut("???")).toBe("faq")
  })
})
