import { screen } from "@testing-library/react"
import { describe, expect, test } from "vitest"

import { renderWithProviders } from "@/test/render"

import { readDemoWidgetConfig } from "./demo-config"
import DemoPage from "./page"

describe("public support stand-in", () => {
  test("shows only the requested demo sentence alongside the widget snippet", () => {
    renderWithProviders(<DemoPage />)

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "This is a demo website for the Chatbot widget.",
      }),
    ).toBeInTheDocument()
    expect(screen.queryByText("SampleSite")).not.toBeInTheDocument()
    expect(screen.queryByText("24-hour chat support")).not.toBeInTheDocument()
    expect(screen.queryByText("Clear answers for every screening step")).not.toBeInTheDocument()
    const loader = document.querySelector('script[src$="/supportchat.js"]')
    expect(loader?.getAttribute("src")).toBe("http://widget.localhost:3000/supportchat.js")
    expect(document.body.innerHTML).toContain("demo")
    expect(document.body.innerHTML).toContain("d".repeat(64))
  })

  test("rejects a missing pair or equal host and widget origins", () => {
    const original = { ...process.env }
    process.env.NEXT_PUBLIC_WIDGET_ORIGIN = "http://localhost:3000"
    process.env.NEXT_PUBLIC_STAFF_APP_ORIGIN = "http://localhost:3000"
    expect(() => readDemoWidgetConfig()).toThrow(/differ/)
    delete process.env.NEXT_PUBLIC_DEMO_PUBLIC_KEY
    process.env.NEXT_PUBLIC_WIDGET_ORIGIN = "http://widget.localhost:3000"
    expect(() => readDemoWidgetConfig()).toThrow(/configured/)
    process.env = original
  })

  test("embeds the configured demo site key", () => {
    const original = { ...process.env }
    process.env.NEXT_PUBLIC_WIDGET_ORIGIN = "http://widget.localhost:3000"
    process.env.NEXT_PUBLIC_STAFF_APP_ORIGIN = "http://localhost:3000"
    process.env.NEXT_PUBLIC_DEMO_SITE_KEY = "website-demo"
    process.env.NEXT_PUBLIC_DEMO_PUBLIC_KEY = "ab".repeat(32)
    expect(readDemoWidgetConfig()).toEqual({
      widgetOrigin: "http://widget.localhost:3000",
      staffOrigin: "http://localhost:3000",
      siteKey: "website-demo",
      publicKey: "ab".repeat(32),
    })
    process.env = original
  })
})
