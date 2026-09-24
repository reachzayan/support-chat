const SITE_KEY_RE = /^[a-z][a-z0-9-]{0,62}$/
const PUBLIC_KEY_RE = /^[0-9a-f]{64}$/

export const readDemoWidgetConfig = () => {
  const widgetOrigin = process.env.NEXT_PUBLIC_WIDGET_ORIGIN
  const staffOrigin = process.env.NEXT_PUBLIC_STAFF_APP_ORIGIN
  const siteKey = process.env.NEXT_PUBLIC_DEMO_SITE_KEY
  const publicKey = process.env.NEXT_PUBLIC_DEMO_PUBLIC_KEY
  if (!widgetOrigin || !staffOrigin || !siteKey || !publicKey) {
    throw new Error("SupportChat demo widget is not configured")
  }
  if (widgetOrigin === staffOrigin) {
    throw new Error("SupportChat widget origin must differ from the staff app origin")
  }
  if (!SITE_KEY_RE.test(siteKey)) {
    throw new Error("SupportChat demo site key is invalid")
  }
  if (!PUBLIC_KEY_RE.test(publicKey)) {
    throw new Error("SupportChat demo public key is invalid")
  }
  return { widgetOrigin, staffOrigin, siteKey, publicKey }
}

const scriptJson = (value: string) => JSON.stringify(value).replaceAll("<", "\\u003c")

export const embedConfigMarkup = (siteKey: string, publicKey: string) => ({
  __html: `window.__supportchat = { siteKey: ${scriptJson(siteKey)}, publicKey: ${scriptJson(publicKey)} }`,
})
