type StaffUser = {
  id: string
  email: string
  display_name: string
  is_admin: boolean
}

type LoginResponse = {
  access_token: string
  user: StaffUser
}

let accessToken: string | null = null
let refreshInFlight: Promise<StaffUser | null> | null = null

export const getAccessToken = () => accessToken

export const setAccessToken = (token: string | null) => {
  accessToken = token
}

const readCookie = (name: string) => {
  const prefix = `${name}=`
  const parts = document.cookie.split(";")
  for (const part of parts) {
    const trimmed = part.trim()
    if (trimmed.startsWith(prefix)) {
      return decodeURIComponent(trimmed.slice(prefix.length))
    }
  }
  return null
}

const csrfHeaders = (): Record<string, string> => {
  const token = readCookie("supportchat_csrf")
  if (!token) {
    return {}
  }
  return { "X-CSRF-Token": token }
}

const authHeaders = (): Record<string, string> => {
  if (!accessToken) {
    return {}
  }
  return { Authorization: `Bearer ${accessToken}` }
}

export const login = async (email: string, password: string) => {
  const response = await fetch("/auth/login", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  })
  if (!response.ok) {
    throw new Error("invalid")
  }
  const body = (await response.json()) as LoginResponse
  accessToken = body.access_token
  return body.user
}

export const refreshSession = async () => {
  if (refreshInFlight !== null) {
    return refreshInFlight
  }
  refreshInFlight = (async () => {
    const response = await fetch("/auth/refresh", {
      method: "POST",
      credentials: "include",
      headers: csrfHeaders(),
    })
    if (response.status === 401) {
      accessToken = null
      return null
    }
    if (!response.ok) {
      return null
    }
    const body = (await response.json()) as LoginResponse
    accessToken = body.access_token
    return body.user
  })().finally(() => {
    refreshInFlight = null
  })
  return refreshInFlight
}

export const fetchMe = async () => {
  const token = accessToken
  if (!token) {
    return null
  }
  const response = await fetch("/auth/me", {
    credentials: "include",
    headers: { Authorization: `Bearer ${token}` },
  })
  if (response.status === 401) {
    accessToken = null
    return null
  }
  if (!response.ok) {
    return null
  }
  return (await response.json()) as StaffUser
}

export const staffRequest = async (path: string, init: RequestInit = {}) => {
  const send = () => {
    const headers = new Headers(init.headers)
    for (const [key, value] of Object.entries(authHeaders())) {
      if (!headers.has(key)) {
        headers.set(key, value)
      }
    }
    return fetch(path, { ...init, credentials: "include", headers })
  }
  const response = await send()
  if (response.status !== 401) {
    return response
  }
  const user = await refreshSession()
  if (user === null) {
    return response
  }
  return send()
}

export const staffGet = async (path: string) => staffRequest(path)

export type { StaffUser }
