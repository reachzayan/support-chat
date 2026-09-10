export const SITE_ID = "11111111-1111-4111-8111-111111111111"
export const SOURCE_ID = "22222222-2222-4222-8222-222222222222"
export const PAGE_ID = "33333333-3333-4333-8333-333333333333"
export const PAGE_TITLE = "Turnaround"
export const PAGE_URL = "https://sample-site.example.com/faq"
export const TIMING_BODY = "Most negative results are reported within 24-48 hours."
export const BG_SITE = "44444444-4444-4444-8444-444444444444"
export const BG_SOURCE = "55555555-5555-4555-8555-555555555555"
export const BG_PAGE = "66666666-6666-4666-8666-666666666666"
export const FCRA_TITLE = "What is FCRA?"

export const jsonOk = (payload: unknown, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => payload,
})

export const siteRecord = (id: string, key: string, name: string) => ({
  id,
  key,
  name,
  greeting: "Talk to a specialist about screening.",
  privacy_url: "https://sample-site.example.com/privacy",
  public_key: "a".repeat(64),
  origins: [],
  snippet: "",
  origins_missing_from_frame_ancestors: false,
  bot_enabled: true,
  human_enabled: true,
})

const easySource = (overrides: Record<string, unknown> = {}) => ({
  id: SOURCE_ID,
  site_id: SITE_ID,
  start_url: PAGE_URL,
  mode: "list",
  status: "ready",
  error_code: null,
  page_count: 1,
  enabled: true,
  ...overrides,
})

const easyPage = (overrides: Record<string, unknown> = {}) => ({
  id: PAGE_ID,
  source_id: SOURCE_ID,
  url: PAGE_URL,
  title: PAGE_TITLE,
  enabled: true,
  ...overrides,
})

const sitesList = () =>
  jsonOk({
    items: [siteRecord(SITE_ID, "samplesite", "SampleSite")],
    frame_ancestors: ["http://localhost:3000"],
    widget_origin: "http://widget.localhost:3000",
  })

const sourcesList = () => jsonOk({ items: [easySource()] })

const createSource = () => jsonOk(easySource({ status: "queued", page_count: 0 }), 201)

const patchSource = (init?: RequestInit) => {
  const body = JSON.parse(String(init?.body)) as { enabled: boolean }
  return jsonOk(easySource({ enabled: body.enabled }))
}

const sourcePages = () => jsonOk({ items: [easyPage()] })

const patchPage = (init?: RequestInit) => {
  const body = JSON.parse(String(init?.body)) as { enabled: boolean }
  return jsonOk(easyPage({ enabled: body.enabled }))
}

const pageDetail = () =>
  jsonOk({
    ...easyPage(),
    skip_reason: null,
    content_text: TIMING_BODY,
    chunks: [{ ordinal: 0, heading: PAGE_TITLE, body: TIMING_BODY, enabled: true }],
  })

const siteSourcesRoute = (url: string, init?: RequestInit) => {
  if (url !== `/api/sites/${SITE_ID}/kb-sources`) {
    return null
  }
  return init?.method === "POST" ? createSource() : sourcesList()
}

const kbPageRoute = (url: string, init?: RequestInit) => {
  if (url !== `/api/kb-pages/${PAGE_ID}`) {
    return null
  }
  return init?.method === "PATCH" ? patchPage(init) : pageDetail()
}

const knowledgeRoute = (url: string, init?: RequestInit) => {
  if (url === "/api/sites") {
    return sitesList()
  }
  const sources = siteSourcesRoute(url, init)
  if (sources) {
    return sources
  }
  if (url === `/api/kb-sources/${SOURCE_ID}` && init?.method === "PATCH") {
    return patchSource(init)
  }
  if (url === `/api/kb-sources/${SOURCE_ID}/pages`) {
    return sourcePages()
  }
  const page = kbPageRoute(url, init)
  if (page) {
    return page
  }
  return null
}

export const knowledgeFetch = async (input: RequestInfo, init?: RequestInit) => {
  const matched = knowledgeRoute(String(input), init)
  return matched ?? { ok: false, status: 404, json: async () => ({}) }
}

let releaseEasy: (value?: void | PromiseLike<void>) => void = () => undefined
let easyHold = Promise.resolve()

export const resetEasyHold = () => {
  easyHold = new Promise<void>((resolve) => {
    releaseEasy = resolve
  })
}

export const releaseEasyHold = () => releaseEasy()

const twoBrandSites = () =>
  jsonOk({
    items: [
      siteRecord(SITE_ID, "samplesite", "SampleSite"),
      siteRecord(BG_SITE, "backgroundchecks", "Sample Services"),
    ],
    frame_ancestors: ["http://localhost:3000"],
    widget_origin: "http://widget.localhost:3000",
  })

export const twoBrandFetch = async (input: RequestInfo) => {
  const url = String(input)
  if (url === "/api/sites") {
    return twoBrandSites()
  }
  if (url === `/api/sites/${SITE_ID}/kb-sources`) {
    await easyHold
    return sourcesList()
  }
  if (url === `/api/kb-sources/${SOURCE_ID}/pages`) {
    await easyHold
    return sourcePages()
  }
  if (url === `/api/sites/${BG_SITE}/kb-sources`) {
    return jsonOk({
      items: [
        {
          id: BG_SOURCE,
          site_id: BG_SITE,
          start_url: "https://sample-services.example.com/fcra",
          mode: "list",
          status: "ready",
          error_code: null,
          page_count: 1,
          enabled: true,
        },
      ],
    })
  }
  if (url === `/api/kb-sources/${BG_SOURCE}/pages`) {
    return jsonOk({
      items: [
        {
          id: BG_PAGE,
          source_id: BG_SOURCE,
          url: "https://sample-services.example.com/fcra",
          title: FCRA_TITLE,
          enabled: true,
        },
      ],
    })
  }
  return { ok: false, status: 404, json: async () => ({}) }
}

let releaseDiff: (value?: void | PromiseLike<void>) => void = () => undefined
const diffHold = new Promise<void>((resolve) => {
  releaseDiff = resolve
})

const OTHER_DIFF_SOURCE = "77777777-7777-4777-8777-777777777777"

export const diffRaceFetch = async (input: RequestInfo) => {
  const url = String(input)
  if (url === "/api/sites") {
    return sitesList()
  }
  if (url === `/api/sites/${SITE_ID}/kb-sources`) {
    return jsonOk({
      items: [
        easySource(),
        easySource({
          id: OTHER_DIFF_SOURCE,
          start_url: "https://sample-site.example.com/dot",
        }),
      ],
    })
  }
  if (url === `/api/kb-sources/${SOURCE_ID}/diff`) {
    await diffHold
    return jsonOk({ added: [], changed: [], removed: [] })
  }
  if (url === `/api/kb-sources/${OTHER_DIFF_SOURCE}/diff`) {
    return jsonOk({
      added: [{ kind: "faq", heading: "DOT timing", answer_verbatim: "24 hours." }],
      changed: [],
      removed: [],
    })
  }
  if (url.endsWith("/snapshots")) {
    return jsonOk({ items: [] })
  }
  if (url === `/api/kb-sources/${SOURCE_ID}/pages`) {
    return sourcePages()
  }
  if (url === `/api/kb-sources/${OTHER_DIFF_SOURCE}/pages`) {
    return jsonOk({ items: [] })
  }
  return { ok: false, status: 404, json: async () => ({}) }
}

export const releaseDiffHold = () => releaseDiff()
