export const WIDGET_RESIZE_MIN = 320
export const WIDGET_RESIZE_MAX = 720
export const WIDGET_WIDTH_MIN = 360
export const WIDGET_WIDTH_MAX = 560
export const WIDGET_DEFAULT_WIDTH = 420
export const WIDGET_DEFAULT_HEIGHT = 680
export const WIDGET_EXPANDED_WIDTH = 500
export const WIDGET_EXPANDED_HEIGHT = 720

export type PublicWidgetConfig = {
  name: string
  greeting: string
  privacy_url: string
  contact_info: string[]
  bot_enabled: boolean
  human_enabled: boolean
}

export type VisitorProfile = { name: string; email: string; phone: string }

export type ConversationSnapshot = {
  visitor_profile?: VisitorProfile
  id?: string
  state: "prechat" | "bot" | "queued" | "human" | "closed"
  assigned_agent: { id: string; display_name: string } | null
  messages: Record<string, unknown>[]
  has_older?: boolean
}

export type ReturningIdentity = {
  display_name: string
  email_hint: string
  phone_hint: string | null
  chat_count: number
}

export type ConversationHistoryItem = {
  preview?: string | null
  id: string
  state: ConversationSnapshot["state"]
  inquiry_type: string | null
  created_at: string
  last_message_at: string
  assigned_agent: ConversationSnapshot["assigned_agent"]
  is_current: boolean
}

export type HostToWidget =
  | { type: "host.sound"; enabled: boolean }
  | {
      type: "host.bootstrap"
      bootstrap_token: string
      widget: PublicWidgetConfig
      page_url: string
      page_title: string
      referrer: string
      conversation?: ConversationSnapshot
    }
  | { type: "host.identity"; widget: PublicWidgetConfig; identity: ReturningIdentity }
  | {
      type: "host.history"
      widget: PublicWidgetConfig
      identity: ReturningIdentity
      conversations: ConversationHistoryItem[]
    }
  | { type: "host.layout"; fullscreen: boolean }
  | { type: "host.context"; page_url: string; page_title: string; referrer: string }

export type WidgetToHost =
  | { type: "widget.sound"; enabled: boolean }
  | { type: "widget.message"; conversation_id: string; message_id: number }
  | { type: "widget.ready" }
  | { type: "widget.painted" }
  | { type: "widget.rebootstrap"; conversation_id?: string }
  | { type: "widget.activated" }
  | { type: "widget.close" }
  | { type: "widget.show_history" }
  | { type: "widget.reset_current" }
  | { type: "widget.delete_all" }
  | {
      type: "widget.open_conversation"
      conversation_id: string
      replace_current: boolean
    }
  | { type: "widget.resize"; height: number; width?: number }
  | { type: "widget.open_url"; url: string }

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === "object" && value !== null
}

const parseWidgetConfig = (value: unknown): PublicWidgetConfig | null => {
  if (!isRecord(value)) {
    return null
  }
  if (
    typeof value.name !== "string" ||
    typeof value.greeting !== "string" ||
    typeof value.privacy_url !== "string"
  ) {
    return null
  }
  const contactInfo = Array.isArray(value.contact_info)
    ? value.contact_info.filter(
        (item): item is string => typeof item === "string" && item.trim() !== "",
      )
    : []
  return {
    name: value.name,
    greeting: value.greeting,
    privacy_url: value.privacy_url,
    contact_info: contactInfo,
    bot_enabled: value.bot_enabled !== false,
    human_enabled: value.human_enabled !== false,
  }
}

const SNAPSHOT_STATES = new Set(["prechat", "bot", "queued", "human", "closed"])
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

const parseAssignedAgent = (value: unknown): ConversationSnapshot["assigned_agent"] | undefined => {
  if (value === null) {
    return null
  }
  if (!isRecord(value) || typeof value.id !== "string" || typeof value.display_name !== "string") {
    return undefined
  }
  return { id: value.id, display_name: value.display_name }
}

const parseVisitorProfile = (value: unknown): VisitorProfile | undefined => {
  if (
    !isRecord(value) ||
    typeof value.name !== "string" ||
    typeof value.email !== "string" ||
    typeof value.phone !== "string"
  )
    return undefined
  return { name: value.name, email: value.email, phone: value.phone }
}

export const parseConversationSnapshot = (value: unknown): ConversationSnapshot | undefined => {
  if (!isRecord(value) || typeof value.state !== "string" || !SNAPSHOT_STATES.has(value.state)) {
    return undefined
  }
  if (!Array.isArray(value.messages)) {
    return undefined
  }
  const assigned =
    value.assigned_agent === undefined ? null : parseAssignedAgent(value.assigned_agent)
  if (assigned === undefined) {
    return undefined
  }
  return {
    ...(typeof value.id === "string" && UUID_PATTERN.test(value.id) ? { id: value.id } : {}),
    state: value.state as ConversationSnapshot["state"],
    assigned_agent: assigned,
    messages: value.messages.filter(isRecord),
    has_older: value.has_older === true,
    visitor_profile: parseVisitorProfile(value.visitor_profile),
  }
}

const parseIdentity = (value: unknown): ReturningIdentity | null => {
  if (
    !isRecord(value) ||
    typeof value.display_name !== "string" ||
    typeof value.email_hint !== "string" ||
    (value.phone_hint !== null && typeof value.phone_hint !== "string") ||
    typeof value.chat_count !== "number" ||
    !Number.isInteger(value.chat_count) ||
    value.chat_count < 0
  ) {
    return null
  }
  return {
    display_name: value.display_name,
    email_hint: value.email_hint,
    phone_hint: value.phone_hint,
    chat_count: value.chat_count,
  }
}

// History metadata crosses a trust boundary and every field is validated here.
// oxlint-disable-next-line complexity
const parseHistoryItem = (value: unknown): ConversationHistoryItem | null => {
  if (
    !isRecord(value) ||
    typeof value.id !== "string" ||
    !UUID_PATTERN.test(value.id) ||
    typeof value.state !== "string" ||
    !SNAPSHOT_STATES.has(value.state) ||
    (value.inquiry_type !== null && typeof value.inquiry_type !== "string") ||
    typeof value.created_at !== "string" ||
    !Number.isFinite(Date.parse(value.created_at)) ||
    typeof value.last_message_at !== "string" ||
    !Number.isFinite(Date.parse(value.last_message_at)) ||
    typeof value.is_current !== "boolean"
  ) {
    return null
  }
  const assigned = parseAssignedAgent(value.assigned_agent)
  if (assigned === undefined) {
    return null
  }
  return {
    id: value.id,
    state: value.state as ConversationHistoryItem["state"],
    inquiry_type: value.inquiry_type,
    created_at: value.created_at,
    last_message_at: value.last_message_at,
    assigned_agent: assigned,
    is_current: value.is_current,
    preview: typeof value.preview === "string" ? value.preview.slice(0, 180) : null,
  }
}

const parseReturningFrame = (
  value: Record<string, unknown>,
): Extract<HostToWidget, { type: "host.identity" | "host.history" }> | null => {
  const widget = parseWidgetConfig(value.widget)
  const identity = parseIdentity(value.identity)
  if (widget === null || identity === null) {
    return null
  }
  if (value.type === "host.identity") {
    return { type: "host.identity", widget, identity }
  }
  if (value.type !== "host.history" || !Array.isArray(value.conversations)) {
    return null
  }
  const conversations = value.conversations.map(parseHistoryItem)
  if (conversations.some((item) => item === null)) {
    return null
  }
  return {
    type: "host.history",
    widget,
    identity,
    conversations: conversations as ConversationHistoryItem[],
  }
}

const parseBootstrap = (value: Record<string, unknown>): HostToWidget | null => {
  const widget = parseWidgetConfig(value.widget)
  if (typeof value.bootstrap_token !== "string" || widget === null) {
    return null
  }
  if (
    typeof value.page_url !== "string" ||
    typeof value.page_title !== "string" ||
    typeof value.referrer !== "string"
  ) {
    return null
  }
  const conversation = parseConversationSnapshot(value.conversation)
  return {
    type: "host.bootstrap",
    bootstrap_token: value.bootstrap_token,
    widget,
    page_url: value.page_url,
    page_title: value.page_title,
    referrer: value.referrer,
    ...(conversation === undefined ? {} : { conversation }),
  }
}

const parseContext = (value: Record<string, unknown>): HostToWidget | null => {
  if (
    typeof value.page_url !== "string" ||
    typeof value.page_title !== "string" ||
    typeof value.referrer !== "string"
  ) {
    return null
  }
  return {
    type: "host.context",
    page_url: value.page_url,
    page_title: value.page_title,
    referrer: value.referrer,
  }
}

const parseLayout = (value: Record<string, unknown>): HostToWidget | null =>
  typeof value.fullscreen === "boolean"
    ? { type: "host.layout", fullscreen: value.fullscreen }
    : null

export const parseHostToWidget = (value: unknown): HostToWidget | null => {
  if (!isRecord(value) || typeof value.type !== "string") {
    return null
  }
  if (value.type === "host.sound") {
    return typeof value.enabled === "boolean"
      ? { type: "host.sound", enabled: value.enabled }
      : null
  }
  if (value.type === "host.layout") {
    return parseLayout(value)
  }
  if (value.type === "host.bootstrap") {
    return parseBootstrap(value)
  }
  if (value.type === "host.identity" || value.type === "host.history") {
    return parseReturningFrame(value)
  }
  if (value.type === "host.context") {
    return parseContext(value)
  }
  return null
}

const parseResize = (value: Record<string, unknown>): WidgetToHost | null => {
  if (typeof value.height !== "number" || !Number.isInteger(value.height)) {
    return null
  }
  if (value.height < WIDGET_RESIZE_MIN || value.height > WIDGET_RESIZE_MAX) {
    return null
  }
  if (value.width === undefined) {
    return { type: "widget.resize", height: value.height }
  }
  if (typeof value.width !== "number" || !Number.isInteger(value.width)) {
    return null
  }
  if (value.width < WIDGET_WIDTH_MIN || value.width > WIDGET_WIDTH_MAX) {
    return null
  }
  return { type: "widget.resize", height: value.height, width: value.width }
}

const SIMPLE_WIDGET_TYPES = new Set([
  "widget.ready",
  "widget.painted",
  "widget.activated",
  "widget.close",
  "widget.show_history",
  "widget.reset_current",
  "widget.delete_all",
])

type SimpleWidgetType = Extract<
  WidgetToHost,
  {
    type:
      | "widget.ready"
      | "widget.painted"
      | "widget.activated"
      | "widget.close"
      | "widget.show_history"
      | "widget.reset_current"
      | "widget.delete_all"
  }
>

const parseSimpleWidget = (type: string): SimpleWidgetType | null => {
  if (!SIMPLE_WIDGET_TYPES.has(type)) {
    return null
  }
  return { type } as SimpleWidgetType
}

const parseOpenUrl = (value: Record<string, unknown>): WidgetToHost | null => {
  if (typeof value.url !== "string") {
    return null
  }
  try {
    const parsed = new URL(value.url)
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
      return null
    }
  } catch {
    return null
  }
  return { type: "widget.open_url", url: value.url }
}

// The widget protocol is intentionally closed; explicit branches reject extra action shapes.
// oxlint-disable-next-line complexity
export const parseWidgetToHost = (value: unknown): WidgetToHost | null => {
  if (!isRecord(value) || typeof value.type !== "string") {
    return null
  }
  if (value.type === "widget.sound") {
    return typeof value.enabled === "boolean"
      ? { type: "widget.sound", enabled: value.enabled }
      : null
  }
  if (value.type === "widget.message") {
    if (
      typeof value.conversation_id !== "string" ||
      !UUID_PATTERN.test(value.conversation_id) ||
      typeof value.message_id !== "number" ||
      !Number.isSafeInteger(value.message_id) ||
      value.message_id <= 0
    )
      return null
    return {
      type: "widget.message",
      conversation_id: value.conversation_id,
      message_id: value.message_id,
    }
  }
  const simple = parseSimpleWidget(value.type)
  if (simple !== null) {
    return simple
  }
  if (value.type === "widget.resize") {
    return parseResize(value)
  }
  if (value.type === "widget.rebootstrap") {
    if (value.conversation_id === undefined) {
      return { type: "widget.rebootstrap" }
    }
    if (typeof value.conversation_id !== "string" || !UUID_PATTERN.test(value.conversation_id)) {
      return null
    }
    return { type: "widget.rebootstrap", conversation_id: value.conversation_id }
  }
  if (value.type === "widget.open_conversation") {
    if (
      typeof value.conversation_id !== "string" ||
      !UUID_PATTERN.test(value.conversation_id) ||
      typeof value.replace_current !== "boolean"
    ) {
      return null
    }
    return {
      type: "widget.open_conversation",
      conversation_id: value.conversation_id,
      replace_current: value.replace_current,
    }
  }
  if (value.type === "widget.open_url") {
    return parseOpenUrl(value)
  }
  return null
}
