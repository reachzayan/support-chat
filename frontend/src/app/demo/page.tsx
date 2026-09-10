import Script from "next/script"

import { embedConfigMarkup, readDemoWidgetConfig } from "./demo-config"

export default function DemoPage() {
  const { widgetOrigin, siteKey, publicKey } = readDemoWidgetConfig()
  const embedConfig = embedConfigMarkup(siteKey, publicKey)
  return (
    <main className="bg-ice text-ink flex min-h-dvh items-center justify-center px-6 text-center">
      <h1 className="max-w-lg text-2xl font-extrabold tracking-[-0.04em] text-balance sm:text-3xl">
        This is a demo website for the Chatbot widget.
      </h1>
      <script dangerouslySetInnerHTML={embedConfig} />
      <Script src={`${widgetOrigin}/supportchat.js`} strategy="afterInteractive" />
    </main>
  )
}
