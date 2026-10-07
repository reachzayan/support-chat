import { NextRequest } from "next/server"
import { expect, test } from "vitest"

import { proxy } from "./proxy"

test.each(["widget.localhost:3000", "host.localhost:3000"])(
  "%s cannot register a staff push worker or access device APIs",
  async (host) => {
    const paths = [
      "/staff-push-sw.js",
      "/manifest.webmanifest",
      "/api/notifications/push/config",
      "/api/notifications/push/subscriptions",
    ]
    const responses = await Promise.all(
      paths.map((path) => proxy(new NextRequest(`http://${host}${path}`, { headers: { host } }))),
    )
    for (const response of responses) expect(response.status).toBe(404)
  },
)
