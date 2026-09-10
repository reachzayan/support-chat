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
  bot_enabled: boolean
  human_enabled: boolean
}

export type HostToWidget =
  | {
      type: "host.bootstrap"
      bootstrap_token: string
      widget: PublicWidgetConfig
      page_url: string
      page_title: string
      referrer: string
    }
  | { type: "host.context"; page_url: string; page_title: string; referrer: string }

export type WidgetToHost =
  | { type: "widget.ready" }
  | { type: "widget.rebootstrap" }
  | { type: "widget.activated" }
  | { type: "widget.close" }
  | { type: "widget.reset" }
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
  return {
    name: value.name,
    greeting: value.greeting,
    privacy_url: value.privacy_url,
    bot_enabled: value.bot_enabled !== false,
    human_enabled: value.human_enabled !== false,
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
  return {
    type: "host.bootstrap",
    bootstrap_token: value.bootstrap_token,
    widget,
    page_url: value.page_url,
    page_title: value.page_title,
    referrer: value.referrer,
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

export const parseHostToWidget = (value: unknown): HostToWidget | null => {
  if (!isRecord(value) || typeof value.type !== "string") {
    return null
  }
  if (value.type === "host.bootstrap") {
    return parseBootstrap(value)
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
  "widget.rebootstrap",
  "widget.activated",
  "widget.close",
  "widget.reset",
])

type SimpleWidgetType = Extract<
  WidgetToHost,
  {
    type:
      | "widget.ready"
      | "widget.rebootstrap"
      | "widget.activated"
      | "widget.close"
      | "widget.reset"
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

export const parseWidgetToHost = (value: unknown): WidgetToHost | null => {
  if (!isRecord(value) || typeof value.type !== "string") {
    return null
  }
  const simple = parseSimpleWidget(value.type)
  if (simple !== null) {
    return simple
  }
  if (value.type === "widget.resize") {
    return parseResize(value)
  }
  if (value.type === "widget.open_url") {
    return parseOpenUrl(value)
  }
  return null
}
