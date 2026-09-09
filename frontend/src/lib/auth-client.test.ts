import { afterEach, describe, expect, test, vi } from "vitest"

import { refreshSession, setAccessToken, staffGet } from "./auth-client"

const ALEX = {
  id: "11111111-1111-4111-8111-000000000001",
  email: "agent@example.local",
  display_name: "Alex Morgan",
  is_admin: false,
}

const resetAuth = () => {
  setAccessToken(null)
  vi.unstubAllGlobals()
}

describe("refreshSession", () => {
  afterEach(resetAuth)

  test("parallel calls share one refresh request", async () => {
    let inflight = 0
    let peak = 0
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        inflight += 1
        peak = Math.max(peak, inflight)
        await new Promise((resolve) => setTimeout(resolve, 30))
        inflight -= 1
        return {
          ok: true,
          status: 200,
          json: async () => ({ access_token: "jwt-shared", user: ALEX }),
        }
      }),
    )
    document.cookie = "supportchat_csrf=csrf-token"

    const [first, second] = await Promise.all([refreshSession(), refreshSession()])

    expect(vi.mocked(fetch).mock.calls).toHaveLength(1)
    expect(peak).toBe(1)
    expect(first?.display_name).toBe("Alex Morgan")
    expect(second?.display_name).toBe("Alex Morgan")
  })
})

describe("staffGet", () => {
  afterEach(resetAuth)

  test("retries once after 401 with the refreshed access token", async () => {
    setAccessToken("expired-jwt")
    document.cookie = "supportchat_csrf=csrf-token"
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input) === "/auth/refresh") {
          return {
            ok: true,
            status: 200,
            json: async () => ({ access_token: "fresh-jwt", user: ALEX }),
          }
        }
        const auth = new Headers(init?.headers).get("Authorization")
        if (auth === "Bearer expired-jwt") {
          return { ok: false, status: 401, json: async () => ({ detail: "Not authenticated" }) }
        }
        if (auth === "Bearer fresh-jwt") {
          return {
            ok: true,
            status: 200,
            json: async () => ({
              items: [{ visitor_display: "Ada Lopez" }],
              next_cursor: null,
            }),
          }
        }
        return { ok: false, status: 500, json: async () => ({}) }
      }),
    )

    const response = await staffGet("/api/conversations?state=queued")
    const body = (await response.json()) as { items: { visitor_display: string }[] }
    const inboxCalls = vi
      .mocked(fetch)
      .mock.calls.filter((call) => String(call[0]).startsWith("/api/conversations"))

    expect(response.status).toBe(200)
    expect(body.items[0]?.visitor_display).toBe("Ada Lopez")
    expect(inboxCalls).toHaveLength(2)
  })

  test("does not retry after a failed refresh", async () => {
    setAccessToken("expired-jwt")
    document.cookie = "supportchat_csrf=csrf-token"
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input) === "/auth/refresh") {
          return { ok: false, status: 401, json: async () => ({ detail: "Not authenticated" }) }
        }
        return { ok: false, status: 401, json: async () => ({ detail: "Not authenticated" }) }
      }),
    )

    const response = await staffGet("/api/conversations?state=queued")
    const inboxCalls = vi
      .mocked(fetch)
      .mock.calls.filter((call) => String(call[0]).startsWith("/api/conversations"))

    expect(response.status).toBe(401)
    expect(inboxCalls).toHaveLength(1)
  })
})
