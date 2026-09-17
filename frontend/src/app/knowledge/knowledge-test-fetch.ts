export const SITE_ID = "11111111-1111-4111-8111-111111111111"
export const SOURCE_ID = "22222222-2222-4222-8222-222222222222"
export const PAGE_ID = "33333333-3333-4333-8333-333333333333"
export const CHUNK_ID = "77777777-7777-4777-8777-777777777777"
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
  chunk_count: 1,
  ...overrides,
})

const sitesList = () =>
  jsonOk({
    items: [siteRecord(SITE_ID, "samplesite", "SampleSite")],
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
    chunks: [
      {
        id: CHUNK_ID,
        ordinal: 0,
        kind: "section",
        heading: PAGE_TITLE,
        body: TIMING_BODY,
        enabled: true,
      },
    ],
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

// oxlint-disable-next-line eslint/complexity -- The test router mirrors the distinct API paths the page consumes.
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
  if (url === `/api/kb-sources/${SOURCE_ID}/diff`) {
    return jsonOk({
      added: [
        {
          kind: "section",
          canonical_question: null,
          heading: PAGE_TITLE,
          answer_verbatim: TIMING_BODY,
          display_locator: null,
        },
      ],
      changed: [],
      removed: [],
    })
  }
  if (url === `/api/kb-sources/${SOURCE_ID}/snapshots`) {
    return jsonOk({
      items: [
        {
          id: "88888888-8888-4888-8888-888888888888",
          state: "live",
          created_at: "2026-09-16T12:00:00+00:00",
          promoted_at: "2026-09-16T12:00:00+00:00",
          token_estimate: 12,
          validation_errors: [],
          error_code: null,
        },
      ],
    })
  }
  if (url === `/api/kb-chunks/${CHUNK_ID}` && init?.method === "PATCH") {
    const body = JSON.parse(String(init.body)) as { enabled: boolean }
    return jsonOk({
      id: CHUNK_ID,
      ordinal: 0,
      kind: "section",
      heading: PAGE_TITLE,
      body: TIMING_BODY,
      enabled: body.enabled,
    })
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

export const DEMO_PAGE_TITLE = "Demo"

export const demoKnowledgeFetch = async (input: RequestInfo) => {
  const url = String(input)
  if (url === "/api/sites") {
    return jsonOk({
      items: [siteRecord(SITE_ID, "demo", "Demo"), siteRecord(BG_SITE, "samplesite", "SampleSite")],
      widget_origin: "http://widget.localhost:3000",
    })
  }
  if (url === `/api/sites/${SITE_ID}/kb-sources`) {
    return sourcesList()
  }
  if (url === `/api/kb-sources/${SOURCE_ID}/pages`) {
    return jsonOk({ items: [easyPage({ title: DEMO_PAGE_TITLE })] })
  }
  if (url === `/api/kb-pages/${PAGE_ID}`) {
    return jsonOk({
      ...easyPage({ title: DEMO_PAGE_TITLE }),
      skip_reason: null,
      content_text: TIMING_BODY,
      chunks: [
        {
          id: CHUNK_ID,
          ordinal: 0,
          kind: "section",
          heading: DEMO_PAGE_TITLE,
          body: TIMING_BODY,
          enabled: true,
        },
      ],
    })
  }
  if (url === `/api/sites/${BG_SITE}/kb-sources`) {
    return jsonOk({ items: [] })
  }
  return { ok: false, status: 404, json: async () => ({}) }
}

const twoBrandSites = () =>
  jsonOk({
    items: [
      siteRecord(SITE_ID, "samplesite", "SampleSite"),
      siteRecord(BG_SITE, "backgroundchecks", "Sample Services"),
    ],
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
          chunk_count: 0,
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

export const OTHER_SOURCE_ID = "88888888-8888-4888-8888-888888888888"
export const OTHER_PAGE_TITLE = "Privacy Rights"

export const twoSourceFetch = async (input: RequestInfo) => {
  const url = String(input)
  if (url === "/api/sites") {
    return sitesList()
  }
  if (url === `/api/sites/${SITE_ID}/kb-sources`) {
    return jsonOk({
      items: [
        easySource(),
        easySource({
          id: OTHER_SOURCE_ID,
          start_url: "https://sample-data.example.com/",
          display_name: "Sample Data Services",
        }),
      ],
    })
  }
  if (url === `/api/kb-sources/${SOURCE_ID}/pages`) {
    return sourcePages()
  }
  if (url === `/api/kb-sources/${OTHER_SOURCE_ID}/pages`) {
    return jsonOk({
      items: [
        easyPage({
          id: "99999999-9999-4999-8999-999999999999",
          source_id: OTHER_SOURCE_ID,
          url: "https://sample-data.example.com/privacy",
          title: OTHER_PAGE_TITLE,
        }),
      ],
    })
  }
  if (url === `/api/kb-pages/${PAGE_ID}`) {
    return pageDetail()
  }
  return { ok: false, status: 404, json: async () => ({}) }
}

export const GENERAL_PAGE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
export const HOME_PAGE_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
export const MAIL_PAGE_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
export const CONTACT_BODY = "Phone: 202-555-0101. Email: inquiries@sample-data.example.com"

export const multiPageFetch = async (input: RequestInfo) => {
  const url = String(input)
  if (url === "/api/sites") {
    return jsonOk({
      items: [siteRecord(SITE_ID, "sampledata", "Sample Data Services")],
      widget_origin: "http://widget.localhost:3000",
    })
  }
  if (url === `/api/sites/${SITE_ID}/kb-sources`) {
    return jsonOk({
      items: [
        easySource({
          start_url: "https://sample-data.example.com/",
          display_name: "Sample Data Services",
          page_count: 2,
        }),
      ],
    })
  }
  if (url === `/api/kb-sources/${SOURCE_ID}/pages`) {
    return jsonOk({
      items: [
        easyPage({
          id: GENERAL_PAGE_ID,
          url: "https://sample-data.example.com/",
          title: "General",
          tab: "general",
          chunk_count: 1,
        }),
        easyPage({
          id: HOME_PAGE_ID,
          url: "https://sample-data.example.com/",
          title: "Home",
          tab: "page",
          chunk_count: 0,
        }),
        easyPage({
          id: MAIL_PAGE_ID,
          url: "https://sample-data.example.com/samplemail",
          title: "SampleMail",
          tab: "page",
          chunk_count: 1,
        }),
      ],
    })
  }
  if (url === `/api/kb-pages/${GENERAL_PAGE_ID}`) {
    return jsonOk({
      id: GENERAL_PAGE_ID,
      source_id: SOURCE_ID,
      url: "https://sample-data.example.com/",
      title: "General",
      tab: "general",
      enabled: true,
      chunk_count: 1,
      skip_reason: null,
      content_text: CONTACT_BODY,
      chunks: [
        {
          id: CHUNK_ID,
          ordinal: 0,
          kind: "section",
          heading: "Contact",
          body: CONTACT_BODY,
          enabled: true,
          origin_urls: ["https://sample-data.example.com/", "https://sample-data.example.com/samplemail"],
        },
      ],
    })
  }
  return { ok: false, status: 404, json: async () => ({}) }
}
