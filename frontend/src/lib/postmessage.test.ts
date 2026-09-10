import { describe, expect, test } from "vitest"

import {
  parseHostToWidget,
  parseWidgetToHost,
  WIDGET_RESIZE_MAX,
  WIDGET_RESIZE_MIN,
} from "./postmessage"

describe("host to widget frames", () => {
  test("accepts bootstrap with widget config and page fields", () => {
    const frame = parseHostToWidget({
      type: "host.bootstrap",
      bootstrap_token: "tok",
      widget: {
        name: "SupportChat demo",
        greeting: "Talk to a specialist about screening.",
        privacy_url: "http://localhost:3000/privacy",
      },
      page_url: "http://localhost:3000/demo",
      page_title: "Testing LiveChat inhouse",
      referrer: "",
    })

    expect(frame?.type).toBe("host.bootstrap")
    if (frame?.type !== "host.bootstrap") {
      return
    }
    expect(frame.widget.name).toBe("SupportChat demo")
    expect(frame.bootstrap_token).toBe("tok")
  })

  test("rejects unknown host types", () => {
    expect(parseHostToWidget({ type: "host.hack" })).toBeNull()
  })
})

describe("widget to host frames", () => {
  test("accepts resize only between 320 and 720", () => {
    expect(WIDGET_RESIZE_MIN).toBe(320)
    expect(WIDGET_RESIZE_MAX).toBe(720)
    expect(parseWidgetToHost({ type: "widget.resize", height: 600 })).toEqual({
      type: "widget.resize",
      height: 600,
    })
    expect(parseWidgetToHost({ type: "widget.resize", height: 5000 })).toBeNull()
    expect(parseWidgetToHost({ type: "widget.resize", height: 100 })).toBeNull()
  })

  test("rejects unknown widget types", () => {
    expect(parseWidgetToHost({ type: "widget.explode" })).toBeNull()
  })
})
