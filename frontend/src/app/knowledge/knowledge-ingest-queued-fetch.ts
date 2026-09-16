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
