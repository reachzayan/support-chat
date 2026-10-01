"use client"

import { useLayoutEffect } from "react"

import { readDemoWidgetConfig } from "@/app/demo/demo-config"

export const DemoWidgetEmbed = () => {
  const { widgetOrigin, siteKey, publicKey } = readDemoWidgetConfig()

  useLayoutEffect(() => {
    window.__supportchat = { siteKey, publicKey }
    if (document.getElementById("supportchat-loader") !== null) {
      return
    }
    const loader = document.createElement("script")
    loader.id = "supportchat-loader"
    loader.src = `${widgetOrigin}/supportchat.js`
    loader.async = true
    document.body.appendChild(loader)
  }, [publicKey, siteKey, widgetOrigin])

  return null
}
