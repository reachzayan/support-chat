export type PublicWidgetConfig = {
  name: string
  greeting: string
  privacy_url: string
  bot_enabled: boolean
  human_enabled: boolean
}

export type BootstrapResult = {
  widget: PublicWidgetConfig
  bootstrap_token: string
  resume_token?: string
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
  return {
    name: value.name,
    greeting: value.greeting,
    privacy_url: value.privacy_url,
    bot_enabled: value.bot_enabled !== false,
    human_enabled: value.human_enabled !== false,
  }
}

export const parseBootstrapResult = (value: unknown): BootstrapResult | null => {
  if (!isRecord(value) || typeof value.bootstrap_token !== "string") {
    return null
  }
  const widget = parseWidget(value.widget)
  if (widget === null) {
    return null
  }
  const resume = typeof value.resume_token === "string" ? { resume_token: value.resume_token } : {}
  return { widget, bootstrap_token: value.bootstrap_token, ...resume }
}

export const requestBootstrap = async (
  widgetOrigin: string,
  siteKey: string,
  publicKey: string,
  resumeToken: string | null,
): Promise<BootstrapResult | null> => {
  const body: Record<string, string | null> = {
    site_key: siteKey,
    public_key: publicKey,
    resume_token: resumeToken,
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
