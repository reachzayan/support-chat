import { NextRequest } from "next/server"
import { expect, test } from "vitest"

import config from "../next.config"
import { proxy } from "./proxy"

test.each(["widget.localhost:3000", "host.localhost:3000"])(
  "%s cannot access staff notifications",
  async (host) => {
    const response = await proxy(
      new NextRequest(`http://${host}/api/notifications/preferences`, { headers: { host } }),
    )
    expect(response.status).toBe(404)
  },
)

test("the staff frontend forwards notification feed and preference routes to the API", async () => {
  const rewrites = await config.rewrites?.()
  expect(rewrites).toEqual(
    expect.arrayContaining([
      { source: "/api/notifications", destination: "http://127.0.0.1:8000/api/notifications" },
      {
        source: "/api/notifications/:path*",
        destination: "http://127.0.0.1:8000/api/notifications/:path*",
      },
    ]),
  )
})
