import { staffWrite, type SiteRecord } from "@/components/admin/staff-api"

const linesFromText = (text: string) =>
  text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0)

export const saveManageSite = async (
  siteId: string,
  payload: {
    name: string
    greeting: string
    privacyUrl: string
    websiteUrl: string
    originsText: string
    contactInfoText: string
    windowHours: number
  },
  onSaved: (site: SiteRecord) => void,
  onError: (message: string | null) => void,
) => {
  const response = await staffWrite(`/api/sites/${siteId}`, "PATCH", {
    name: payload.name,
    greeting: payload.greeting,
    privacy_url: payload.privacyUrl,
    origins: linesFromText(payload.originsText),
    website_url: payload.websiteUrl,
    contact_info: linesFromText(payload.contactInfoText),
    callback_window_hours: payload.windowHours,
  })
  if (!response.ok) {
    onError("Check the origin list. Paths, wildcards, and credentials are not allowed.")
    return
  }
  onError(null)
  onSaved((await response.json()) as SiteRecord)
}

export const copyManageSnippet = async (snippet: string, onNotice: (message: string) => void) => {
  try {
    await navigator.clipboard.writeText(snippet)
    onNotice("Snippet copied.")
  } catch {
    onNotice("Could not copy the snippet.")
  }
}
