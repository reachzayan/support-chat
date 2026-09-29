import { describe, expect, test } from "vitest"

import {
  EMPTY_FILTERS,
  filterSubmissions,
  hasActiveFilters,
  nextColumnSort,
  intentOptionsFromRows,
  sortSubmissions,
} from "./data-query"
import type { SubmissionRow } from "./data-shared"

const row = (overrides: {
  id: string
  name: string | null
  email: string | null
  phone: string | null
  state: string
  site_id: string
  site_name: string
  intent?: string | null
  attention_needed: boolean
  opening_message: string | null
  last_message_at: string
  closed_at?: string | null
}): SubmissionRow => ({
  id: overrides.id,
  site_id: overrides.site_id,
  site_key: overrides.site_id,
  site_name: overrides.site_name,
  state: overrides.state,
  inquiry_type: "results",
  intent: overrides.intent === undefined ? "turnaround" : overrides.intent,
  attention_needed: overrides.attention_needed,
  opening_message: overrides.opening_message,
  assigned_agent: null,
  visitor: {
    name: overrides.name,
    email: overrides.email,
    phone: overrides.phone,
    ip: "203.0.113.4",
    user_agent: "Chrome",
    geo_country: "US",
    geo_region: "NY",
    location: "New York, New York, United States",
    created_at: "2026-04-10T12:00:00Z",
  },
  page: {
    title: "Results timing",
    url: "https://sample-site.example.com/results",
    referrer: "https://google.com",
  },
  created_at: "2026-04-12T12:00:00Z",
  last_message_at: overrides.last_message_at,
  closed_at: overrides.closed_at ?? null,
  blocked: false,
  block_id: null,
})

const ALEX = row({
  id: "alex",
  name: "Alex Chen",
  email: "alex@sample-site.example.com",
  phone: "555-0101",
  state: "queued",
  site_id: "samplesite",
  site_name: "SampleSite Support",
  attention_needed: true,
  opening_message: "When will results post",
  last_message_at: "2026-04-15T10:00:00Z",
})
const BLAIR = row({
  id: "blair",
  name: "Blair Diaz",
  email: "blair@sample-services.example.com",
  phone: null,
  state: "closed",
  site_id: "bgc",
  site_name: "Sample Services",
  intent: "pricing",
  attention_needed: false,
  opening_message: "Need a background check quote",
  last_message_at: "2026-04-14T10:00:00Z",
  closed_at: "2026-04-14T11:00:00Z",
})
const CASEY = row({
  id: "casey",
  name: "Casey Ortiz",
  email: "casey@sample-site.example.com",
  phone: "555-0103",
  state: "human",
  site_id: "samplesite",
  site_name: "SampleSite Support",
  attention_needed: true,
  opening_message: "DOT physical timing",
  last_message_at: "2026-04-16T10:00:00Z",
})
const DANA = row({
  id: "dana",
  name: "Dana Wu",
  email: "dana.wu@example.com",
  phone: "555-0104",
  state: "bot",
  site_id: "bgc",
  site_name: "Sample Services",
  intent: "pricing",
  attention_needed: false,
  opening_message: "Hello",
  last_message_at: "2026-04-13T10:00:00Z",
})
const ELLIS = row({
  id: "ellis",
  name: "Ellis Park",
  email: null,
  phone: "555-0105",
  state: "prechat",
  site_id: "samplesite",
  site_name: "SampleSite Support",
  intent: null,
  attention_needed: false,
  opening_message: null,
  last_message_at: "2026-04-12T10:00:00Z",
})

const ROWS = [ALEX, BLAIR, CASEY, DANA, ELLIS]

describe("filterSubmissions", () => {
  test("empty filters keep all five rows in input order", () => {
    expect(filterSubmissions(ROWS, EMPTY_FILTERS).map((item) => item.id)).toEqual([
      "alex",
      "blair",
      "casey",
      "dana",
      "ellis",
    ])
  })

  test("search matches name, email, phone, or opening message", () => {
    expect(
      filterSubmissions(ROWS, { ...EMPTY_FILTERS, search: "sample-site.example.com" }).map(
        (item) => item.id,
      ),
    ).toEqual(["alex", "casey"])
    expect(
      filterSubmissions(ROWS, { ...EMPTY_FILTERS, search: "555-0101" }).map((item) => item.id),
    ).toEqual(["alex"])
    expect(
      filterSubmissions(ROWS, { ...EMPTY_FILTERS, search: "results" }).map((item) => item.id),
    ).toEqual(["alex"])
    expect(
      filterSubmissions(ROWS, { ...EMPTY_FILTERS, search: "ELLIS" }).map((item) => item.id),
    ).toEqual(["ellis"])
  })

  test("state queued keeps only Alex", () => {
    expect(
      filterSubmissions(ROWS, { ...EMPTY_FILTERS, state: "queued" }).map((item) => item.id),
    ).toEqual(["alex"])
  })

  test("site filter keeps Blair and Dana on Sample Services", () => {
    expect(
      filterSubmissions(ROWS, { ...EMPTY_FILTERS, siteId: "bgc" }).map((item) => item.id),
    ).toEqual(["blair", "dana"])
  })

  test("intent pricing keeps Blair and Dana", () => {
    expect(
      filterSubmissions(ROWS, { ...EMPTY_FILTERS, intent: "pricing" }).map((item) => item.id),
    ).toEqual(["blair", "dana"])
  })

  test("search, site, intent, and state combine as AND", () => {
    expect(
      filterSubmissions(ROWS, {
        search: "sample-site.example.com",
        siteId: "samplesite",
        intent: "turnaround",
        state: "queued",
      }).map((item) => item.id),
    ).toEqual(["alex"])
  })
})

describe("sortSubmissions", () => {
  test("null sort keeps input order", () => {
    expect(sortSubmissions(ROWS, null).map((item) => item.id)).toEqual([
      "alex",
      "blair",
      "casey",
      "dana",
      "ellis",
    ])
  })

  test("name asc and desc use the five known names", () => {
    expect(
      sortSubmissions(ROWS, { column: "Name", direction: "asc" }).map((item) => item.id),
    ).toEqual(["alex", "blair", "casey", "dana", "ellis"])
    expect(
      sortSubmissions(ROWS, { column: "Name", direction: "desc" }).map((item) => item.id),
    ).toEqual(["ellis", "dana", "casey", "blair", "alex"])
  })

  test("last message desc is Casey, Alex, Blair, Dana, Ellis", () => {
    expect(
      sortSubmissions(ROWS, { column: "Last message", direction: "desc" }).map((item) => item.id),
    ).toEqual(["casey", "alex", "blair", "dana", "ellis"])
  })

  test("phone, site, site key, and user agent are not sort columns", () => {
    const original = ["alex", "blair", "casey", "dana", "ellis"]
    expect(
      sortSubmissions(ROWS, { column: "Phone", direction: "asc" }).map((item) => item.id),
    ).toEqual(original)
    expect(
      sortSubmissions(ROWS, { column: "Site", direction: "asc" }).map((item) => item.id),
    ).toEqual(original)
    expect(
      sortSubmissions(ROWS, { column: "Site key", direction: "desc" }).map((item) => item.id),
    ).toEqual(original)
    expect(
      sortSubmissions(ROWS, { column: "User agent", direction: "asc" }).map((item) => item.id),
    ).toEqual(original)
  })

  test("transcript is not a sort column and leaves order unchanged", () => {
    expect(
      sortSubmissions(ROWS, { column: "Transcript", direction: "asc" }).map((item) => item.id),
    ).toEqual(["alex", "blair", "casey", "dana", "ellis"])
  })
})

describe("nextColumnSort", () => {
  test("cycles unsorted to asc, asc to desc, desc to unsorted on the same column", () => {
    expect(nextColumnSort(null, "Name")).toEqual({ column: "Name", direction: "asc" })
    expect(nextColumnSort({ column: "Name", direction: "asc" }, "Name")).toEqual({
      column: "Name",
      direction: "desc",
    })
    expect(nextColumnSort({ column: "Name", direction: "desc" }, "Name")).toBeNull()
  })

  test("clicking a different column starts at asc", () => {
    expect(nextColumnSort({ column: "Name", direction: "desc" }, "Email")).toEqual({
      column: "Email",
      direction: "asc",
    })
  })

  test("metadata columns stay unsorted", () => {
    const current = { column: "Name" as const, direction: "asc" as const }
    expect(nextColumnSort(null, "Phone")).toBeNull()
    expect(nextColumnSort(current, "Site")).toEqual(current)
    expect(nextColumnSort(current, "Site key")).toEqual(current)
    expect(nextColumnSort(current, "User agent")).toEqual(current)
    expect(nextColumnSort(null, "Transcript")).toBeNull()
    expect(nextColumnSort(current, "Transcript")).toEqual(current)
  })
})

describe("hasActiveFilters and siteOptionsFromRows", () => {
  test("empty filters are inactive; any field is active", () => {
    expect(hasActiveFilters(EMPTY_FILTERS)).toBe(false)
    expect(hasActiveFilters({ ...EMPTY_FILTERS, search: "alex" })).toBe(true)
    expect(hasActiveFilters({ ...EMPTY_FILTERS, siteId: "bgc" })).toBe(true)
    expect(hasActiveFilters({ ...EMPTY_FILTERS, intent: "pricing" })).toBe(true)
    expect(hasActiveFilters({ ...EMPTY_FILTERS, state: "queued" })).toBe(true)
  })

  test("intent options are pricing then turnaround, skipping empty", () => {
    expect(intentOptionsFromRows(ROWS)).toEqual(["pricing", "turnaround"])
  })
})
