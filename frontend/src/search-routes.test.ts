import { NextRequest } from "next/server"
import { expect, test } from "vitest"

import config from "../next.config"
import { proxy } from "./proxy"
test.each(["widget.localhost:3000", "host.localhost:3000"])(
  "%s cannot access workspace search",
  async (host) => {
    const response = await proxy(
      new NextRequest(`http://${host}/api/search`, { method: "POST", headers: { host } }),
    )
    expect(response.status).toBe(404)
  },
)
test("staff search is forwarded to the authenticated backend", async () => {
  expect(await config.rewrites?.()).toEqual(
    expect.arrayContaining([
      { source: "/api/search", destination: "http://127.0.0.1:8000/api/search" },
    ]),
  )
})
