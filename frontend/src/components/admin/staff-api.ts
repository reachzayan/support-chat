import { staffRequest } from "@/lib/auth-client"

export const staffRead = async (path: string) => staffRequest(path)

export const staffWrite = async (
  path: string,
  method: string,
  body: unknown,
  extras?: { keepalive?: boolean },
) => {
  return staffRequest(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    keepalive: extras?.keepalive,
  })
}

export type SiteRecord = {
  id: string
  key: string
  name: string
  greeting: string
  privacy_url: string
  public_key: string
  origins: string[]
  snippet: string
  enabled: boolean
  bot_enabled: boolean
  human_enabled: boolean
  callback_window_hours?: number
  off_brand_blocklist?: string[]
  website_url: string | null
  widget_installed: boolean | null
  widget_checked_at: string | null
  contact_info?: string[]
}

export type HandoffOutcomeRecord = {
  outcome: string
  note: string | null
  resolved_at: string
  resolved_by?: string | null
}

export type HandoffCandidate = {
  unit_id: string
  canonical_question: string | null
  heading: string | null
  rejection_reason: string | null
}

export type HandoffContextRecord = {
  id: string
  conversation_id: string
  site_id: string
  created_at: string
  escalation_reason: string
  original_question: string
  clarification_answer: string | null
  machine_summary: string
  machine_summary_model: string
  candidate_unit_ids: string[]
  rejection_reasons: { unit_id?: string; reason?: string }[]
  provider_stage_timings: Record<string, number>
  provider_status: string
  promised_response_by: string | null
  route: string
  snapshot_id: string | null
  outcome: HandoffOutcomeRecord | null
  candidates?: HandoffCandidate[]
}

export type ArticleRecord = {
  id: string
  site_id: string
  title: string
  body: string
  enabled: boolean
  updated_by: string | null
}

export type KbSourceRecord = {
  id: string
  site_id: string
  start_url: string
  mode: string
  source_kind?: string
  display_name?: string | null
  status: string
  stage?: string
  error_code: string | null
  page_count: number
  pages_discovered?: number
  pages_fetched?: number
  pages_extracted?: number
  pages_embedded?: number
  pages_failed?: number
  pages_skipped_unchanged?: number
  last_run_started_at?: string | null
  last_run_finished_at?: string | null
  enabled: boolean
  snapshot_state?: string | null
  snapshot_error_code?: string | null
  validation_errors?: string[]
}

export type KbSnapshotRecord = {
  id: string
  state: string
  created_at: string | null
  promoted_at: string | null
  token_estimate: number
  validation_errors: string[]
  error_code: string | null
}

export type KbEvidenceUnit = {
  kind: string
  canonical_question: string | null
  heading: string
  answer_verbatim: string
  display_locator: string | null
}

export type KbDiffChange = {
  before: KbEvidenceUnit
  after: KbEvidenceUnit
}

export type KbDiff = {
  added: KbEvidenceUnit[]
  changed: KbDiffChange[]
  removed: KbEvidenceUnit[]
}

export type KbPageRecord = {
  id: string
  source_id: string
  url: string
  title: string
  enabled: boolean
  chunk_count: number
  processing_status?: string
  failure_reason?: string | null
  last_success_at?: string | null
  tab?: "general" | "page"
}

export type KbChunkRecord = {
  id: string
  ordinal: number
  kind: string
  heading: string
  body: string
  enabled: boolean
  origin_urls?: string[]
  last_body_edit_id?: string | null
}

export type KbPageDetail = KbPageRecord & {
  skip_reason: string | null
  content_text: string
  chunks: KbChunkRecord[]
}

export type KbProgressEvent = {
  timestamp: string | null
  stage: string
  state: string
  page_url: string
  duration_ms: number | null
  error_code: string | null
  error_message: string | null
  message?: string | null
  renderer: string | null
  http_status: number | null
}

export type KbProgressRecord = {
  source: KbSourceRecord
  recent_events: KbProgressEvent[]
  current_jobs: Array<{
    page_url: string
    stage: string
    attempt: number
    started_at: string | null
    renderer: string | null
    message?: string | null
  }>
}
