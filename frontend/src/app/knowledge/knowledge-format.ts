const CODE_LABELS: Record<string, string> = {
  faq_pair_preservation: "FAQ answers did not match",
  numeric_fact_preservation: "numeric facts were lost",
  smoke_assertions: "required content was missing",
  no_truncation: "content was truncated",
  dedupe: "duplicate content was found",
  size_cap: "content exceeded the size limit",
  validation: "validation failed",
  empty: "no usable content",
  extract: "extraction failed",
  persist: "could not save the page",
  timeout: "the crawl timed out",
  browser: "browser renderer unavailable",
  browser_crash: "browser renderer crashed",
  url_overlap: "page belongs to another source",
  page_failures: "pages failed during the crawl",
}

const EVENT_ERROR_SENTENCES: Record<string, string> = {
  browser_crash: "The browser could not open this page.",
  browser: "The browser could not open this page.",
  timeout: "This page took too long to open.",
  empty: "This page had no usable answers.",
  ssrf: "This page could not be opened from our servers.",
  numeric_fact_preservation:
    "This page's numbers did not match the saved answers, so those answers were skipped.",
  no_truncation: "One answer was cut off, so it was skipped.",
  schema: "One answer was incomplete, so it was skipped.",
  dedupe: "Duplicate answers were skipped.",
  size_cap: "One answer was too long, so it was skipped.",
  smoke_assertions: "Required phrases were missing from the saved answers.",
  validation: "This page's answers did not pass review, so they were skipped.",
  extract: "This page could not be read.",
  persist: "This page could not be saved.",
}

const STAGE_RUNNING: Record<string, string> = {
  fetch: "Opening this page.",
  extract: "Reading this page.",
  llm_extract: "Turning this page into answers.",
  embed: "Preparing answers for search.",
  persist: "Saving this page.",
}

const STAGE_DONE: Record<string, string> = {
  fetch: "Opened this page.",
  extract: "Read this page.",
  llm_extract: "Turned this page into answers.",
  embed: "Prepared answers for search.",
  persist: "Saved this page.",
}

export const humanizeCode = (code: string) => CODE_LABELS[code] ?? code.replaceAll("_", " ")

const describeError = (errorCode: string, state: string) => {
  const sentence = EVENT_ERROR_SENTENCES[errorCode] ?? "This page could not be finished."
  if (state === "transient_failed") {
    return `${sentence} Trying again.`
  }
  return sentence
}

const describeStage = (stage: string, state: string) => {
  if (state === "running") {
    return STAGE_RUNNING[stage] ?? "Working on this page."
  }
  if (state === "done") {
    return STAGE_DONE[stage] ?? "Finished this page."
  }
  return null
}

export const describeProgressEvent = (event: {
  message?: string | null
  stage: string
  state: string
  error_code: string | null
}) => {
  if (event.message) {
    return event.message
  }
  if (event.error_code) {
    return describeError(event.error_code, event.state)
  }
  if (event.state === "unchanged") {
    return "This page had not changed, so the live answers were kept."
  }
  const stageCopy = describeStage(event.stage, event.state)
  if (stageCopy) {
    return stageCopy
  }
  if (event.state === "dead_letter") {
    return "This page could not be finished."
  }
  return "Working on this page."
}
