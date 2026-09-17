import {
  jsonOk,
  PAGE_ID,
  PAGE_TITLE,
  PAGE_URL,
  siteRecord,
  SITE_ID,
  SOURCE_ID,
} from "./knowledge-test-fetch"

export const createIngestQueuedFetch = () => {
  const state = { ingested: false }
  const fetchFn = async (input: RequestInfo, init?: RequestInit) => {
    const url = String(input)
    if (url === "/api/sites") {
      return jsonOk({
        items: [siteRecord(SITE_ID, "samplesite", "SampleSite")],
        widget_origin: "http://widget.localhost:3000",
      })
    }
    if (url === `/api/sites/${SITE_ID}/kb-sources` && init?.method !== "POST") {
      return jsonOk({
        items: [
          {
            id: SOURCE_ID,
            site_id: SITE_ID,
            start_url: PAGE_URL,
            mode: "list",
            status: state.ingested ? "ready" : "queued",
            error_code: null,
            page_count: state.ingested ? 1 : 0,
            enabled: true,
          },
        ],
      })
    }
    if (url === `/api/kb-sources/${SOURCE_ID}/pages`) {
      return state.ingested
        ? jsonOk({
            items: [
              {
                id: PAGE_ID,
                source_id: SOURCE_ID,
                url: PAGE_URL,
                title: PAGE_TITLE,
                enabled: true,
                chunk_count: 0,
              },
            ],
          })
        : jsonOk({ items: [] })
    }
    return { ok: false, status: 404, json: async () => ({}) }
  }
  return {
    fetchFn,
    markIngested: () => {
      state.ingested = true
    },
  }
}

export const REINGEST_COPY = "Negative results now report within 12 hours."

export const createReingestSameCountFetch = () => {
  const state = { version: 1 }
  const fetchFn = async (input: RequestInfo) => {
    const url = String(input)
    if (url === "/api/sites") {
      return jsonOk({
        items: [siteRecord(SITE_ID, "samplesite", "SampleSite")],
        widget_origin: "http://widget.localhost:3000",
      })
    }
    if (url === `/api/sites/${SITE_ID}/kb-sources`) {
      return jsonOk({
        items: [
          {
            id: SOURCE_ID,
            site_id: SITE_ID,
            start_url: PAGE_URL,
            mode: "list",
            status: "ready",
            error_code: null,
            page_count: 1,
            last_run_finished_at:
              state.version === 1 ? "2026-09-01T12:00:00Z" : "2026-09-17T15:00:00Z",
            enabled: true,
          },
        ],
      })
    }
    if (url === `/api/kb-sources/${SOURCE_ID}/pages`) {
      return jsonOk({
        items: [
          {
            id: PAGE_ID,
            source_id: SOURCE_ID,
            url: PAGE_URL,
            title: PAGE_TITLE,
            enabled: true,
            chunk_count: 1,
          },
        ],
      })
    }
    if (url === `/api/kb-pages/${PAGE_ID}`) {
      const body = state.version === 1 ? TIMING_COPY : REINGEST_COPY
      return jsonOk({
        id: PAGE_ID,
        source_id: SOURCE_ID,
        url: PAGE_URL,
        title: PAGE_TITLE,
        enabled: true,
        chunk_count: 1,
        skip_reason: null,
        content_text: body,
        chunks: [
          {
            id: "77777777-7777-4777-8777-777777777777",
            ordinal: 0,
            kind: "section",
            heading: PAGE_TITLE,
            body,
            enabled: true,
          },
        ],
      })
    }
    return { ok: false, status: 404, json: async () => ({}) }
  }
  return {
    fetchFn,
    markReingested: () => {
      state.version = 2
    },
  }
}

export const DOT_PAGE_ID = "99999999-9999-4999-8999-999999999999"
export const DOT_COPY = "DOT-regulated testing follows federal rules."
export const TIMING_COPY = "Most negative results are reported within 24-48 hours."

const pageDetailPayload = (
  page: { id: string; source_id: string; url: string; title: string; enabled: boolean },
  copy: string,
) =>
  jsonOk({
    ...page,
    skip_reason: null,
    content_text: copy,
    chunks: [
      {
        id: `${page.id}-chunk`,
        ordinal: 0,
        kind: "section",
        heading: page.title,
        body: copy,
        enabled: true,
      },
    ],
  })

export const createSelectedPagePollFetch = () => {
  const firstPage = {
    id: PAGE_ID,
    source_id: SOURCE_ID,
    url: PAGE_URL,
    title: PAGE_TITLE,
    enabled: true,
    chunk_count: 0,
  }
  const secondPage = {
    id: DOT_PAGE_ID,
    source_id: SOURCE_ID,
    url: "https://sample-site.example.com/dot",
    title: "DOT",
    enabled: true,
    chunk_count: 0,
  }
  const state = { polls: 0 }
  const fetchFn = async (input: RequestInfo) => {
    const url = String(input)
    if (url === "/api/sites") {
      return jsonOk({
        items: [siteRecord(SITE_ID, "samplesite", "SampleSite")],
        widget_origin: "http://widget.localhost:3000",
      })
    }
    if (url === `/api/sites/${SITE_ID}/kb-sources`) {
      state.polls += 1
      return jsonOk({
        items: [
          {
            id: SOURCE_ID,
            site_id: SITE_ID,
            start_url: PAGE_URL,
            mode: "prefix",
            status: state.polls === 1 ? "running" : "ready",
            stage: state.polls === 1 ? "processing" : "ready",
            error_code: null,
            page_count: 2,
            enabled: true,
            snapshot_state: "live",
          },
        ],
      })
    }
    if (url === `/api/kb-sources/${SOURCE_ID}/pages`) {
      return jsonOk({ items: [firstPage, secondPage] })
    }
    if (url === `/api/kb-pages/${PAGE_ID}`) {
      return pageDetailPayload(firstPage, TIMING_COPY)
    }
    if (url === `/api/kb-pages/${DOT_PAGE_ID}`) {
      return pageDetailPayload(secondPage, DOT_COPY)
    }
    return { ok: false, status: 404, json: async () => ({}) }
  }
  return fetchFn
}

const failedSource = {
  id: SOURCE_ID,
  site_id: SITE_ID,
  start_url: PAGE_URL,
  mode: "prefix",
  status: "failed",
  stage: "failed",
  error_code: "validation",
  page_count: 1,
  pages_failed: 1,
  enabled: true,
  snapshot_state: "live",
  validation_errors: ["faq_pair_preservation"],
}

const failedPage = {
  id: PAGE_ID,
  source_id: SOURCE_ID,
  url: PAGE_URL,
  title: PAGE_TITLE,
  enabled: true,
  chunk_count: 0,
  processing_status: "failed",
  failure_reason: "validation",
}

// oxlint-disable-next-line eslint/complexity -- The fixture mirrors the distinct knowledge API routes.
export const createFailedProgressFetch = () => async (input: RequestInfo, init?: RequestInit) => {
  const url = String(input)
  if (url === "/api/sites") {
    return jsonOk({ items: [siteRecord(SITE_ID, "samplesite", "SampleSite")] })
  }
  if (url === `/api/sites/${SITE_ID}/kb-sources`) {
    return jsonOk({ items: [failedSource] })
  }
  if (url === `/api/kb-sources/${SOURCE_ID}/pages`) {
    return jsonOk({ items: [failedPage] })
  }
  if (url === `/api/kb-pages/${PAGE_ID}` && init?.method !== "POST") {
    return jsonOk({
      ...failedPage,
      skip_reason: null,
      content_text: TIMING_COPY,
      chunks: [],
    })
  }
  if (url === `/api/kb-pages/${PAGE_ID}/retry` && init?.method === "POST") {
    return jsonOk({ ...failedSource, status: "queued", stage: "idle" })
  }
  if (url === `/api/kb-sources/${SOURCE_ID}/progress`) {
    return jsonOk({
      source: {},
      current_jobs: [],
      recent_events: [
        {
          timestamp: "2026-09-16T12:00:00Z",
          stage: "fetch",
          state: "dead_letter",
          page_url: PAGE_URL,
          duration_ms: 1200,
          error_code: "browser_crash",
          error_message: "Browser closed unexpectedly",
          message: "The browser could not open this page.",
          renderer: "crawl4ai",
          http_status: null,
        },
      ],
    })
  }
  return { ok: false, status: 404, json: async () => ({}) }
}
