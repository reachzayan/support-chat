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
  return { widgetOrigin, staffOrigin, siteKey, publicKey }
}

export const embedConfigMarkup = (siteKey: string, publicKey: string) => ({
  __html: `window.__supportchat = { siteKey: ${JSON.stringify(siteKey)}, publicKey: ${JSON.stringify(publicKey)} }`,
})
