import { describe, expect, test } from "vitest"

import { resolveKnowledgeSiteId, selectedSiteValue } from "./knowledge-site"

const DEMO_ID = "11111111-1111-4111-8111-111111111111"
const EASY_ID = "44444444-4444-4444-8444-444444444444"

const sites = [
  { id: DEMO_ID, key: "demo", name: "Demo" },
  { id: EASY_ID, key: "samplesite", name: "SampleSite" },
]

describe("resolveKnowledgeSiteId", () => {
  test("staying on Demo does not switch, whether the dropdown sent the id, name, or key", () => {
    expect(resolveKnowledgeSiteId(sites, DEMO_ID, DEMO_ID)).toBeNull()
    expect(resolveKnowledgeSiteId(sites, "Demo", DEMO_ID)).toBeNull()
    expect(resolveKnowledgeSiteId(sites, "demo", DEMO_ID)).toBeNull()
  })

  test("choosing SampleSite from Demo returns the SampleSite id", () => {
    expect(resolveKnowledgeSiteId(sites, EASY_ID, DEMO_ID)).toBe(EASY_ID)
    expect(resolveKnowledgeSiteId(sites, "SampleSite", DEMO_ID)).toBe(EASY_ID)
  })

  test("unknown dropdown values do not switch away from Demo", () => {
    expect(resolveKnowledgeSiteId(sites, "nope", DEMO_ID)).toBeNull()
  })
})

describe("selectedSiteValue", () => {
  test("reads a site id from a string or a label/value item", () => {
    expect(selectedSiteValue(DEMO_ID)).toBe(DEMO_ID)
    expect(selectedSiteValue({ label: "Demo", value: DEMO_ID })).toBe(DEMO_ID)
    expect(selectedSiteValue(null)).toBeNull()
    expect(selectedSiteValue("")).toBeNull()
  })
})
