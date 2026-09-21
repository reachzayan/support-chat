import {
  parseConversationSnapshot,
  parseHostToWidget,
  type ConversationHistoryItem,
  type ConversationSnapshot,
  type ReturningIdentity,
} from "../src/lib/postmessage"

export type PublicWidgetConfig = {
  name: string
  greeting: string
  privacy_url: string
  contact_info: string[]
  bot_enabled: boolean
  human_enabled: boolean
}

export type BootstrapResult =
  | {
      mode: "conversation"
      widget: PublicWidgetConfig
      bootstrap_token: string
      resume_token?: string
      conversation?: ConversationSnapshot
    }
  | { mode: "identity"; widget: PublicWidgetConfig; identity: ReturningIdentity }
  | {
      mode: "history"
      widget: PublicWidgetConfig
      identity: ReturningIdentity
      conversations: ConversationHistoryItem[]
    }
  | { mode: "forgotten"; widget: PublicWidgetConfig }

export type BootstrapAction = {
  action?: "identify" | "history" | "open" | "refresh" | "reset" | "forget"
  conversationId?: string
  replaceCurrent?: boolean
}

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === "object" && value !== null
}

const parseWidget = (value: unknown): PublicWidgetConfig | null => {
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

// Each mode has a different closed response shape; keep validation at this boundary.
// oxlint-disable-next-line complexity
export const parseBootstrapResult = (value: unknown): BootstrapResult | null => {
  if (!isRecord(value)) {
    return null
  }
  const widget = parseWidget(value.widget)
  if (widget === null) {
    return null
  }
  if (value.mode === "identity" || value.mode === "history") {
    const frame = parseHostToWidget({
      type: value.mode === "identity" ? "host.identity" : "host.history",
      widget: value.widget,
      identity: value.identity,
      ...(value.mode === "history" ? { conversations: value.conversations } : {}),
    })
    if (frame?.type === "host.identity") {
      return { mode: "identity", widget, identity: frame.identity }
    }
    if (frame?.type === "host.history") {
      return {
        mode: "history",
        widget,
        identity: frame.identity,
        conversations: frame.conversations,
      }
    }
    return null
  }
  if (value.mode === "forgotten") {
    return { mode: "forgotten", widget }
  }
  if (typeof value.bootstrap_token !== "string") {
    return null
  }
  const resume = typeof value.resume_token === "string" ? { resume_token: value.resume_token } : {}
  const conversation = parseConversationSnapshot(value.conversation)
  return {
    mode: "conversation",
    widget,
    bootstrap_token: value.bootstrap_token,
    ...resume,
    ...(conversation === undefined ? {} : { conversation }),
  }
}

export const requestBootstrap = async (
  widgetOrigin: string,
  siteKey: string,
  publicKey: string,
  resumeToken: string | null,
  options: BootstrapAction = {},
): Promise<BootstrapResult | null> => {
  const body: Record<string, string | boolean | null> = {
    site_key: siteKey,
    public_key: publicKey,
    resume_token: resumeToken,
    action: options.action ?? "identify",
  }
  if (options.conversationId !== undefined) {
    body.conversation_id = options.conversationId
  }
  if (options.replaceCurrent !== undefined) {
    body.replace_current = options.replaceCurrent
  }
  try {
    const response = await fetch(`${widgetOrigin}/api/public/widget-bootstrap`, {
      method: "POST",
      headers: { "Content-Type": "text/plain;charset=UTF-8" },
      body: JSON.stringify(body),
    })
    if (!response.ok) {
      return null
    }
    return parseBootstrapResult(await response.json())
  } catch {
    return null
  }
}
