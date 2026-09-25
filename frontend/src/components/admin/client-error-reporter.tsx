"use client"

import { useEffect } from "react"

import { getAccessToken, staffRequest } from "@/lib/auth-client"

const reportClientLog = async (payload: {
  event: "ui_window_error" | "ui_unhandled_rejection"
  error_class: string
  line?: number
  column?: number
}) => {
  if (!getAccessToken()) {
    return
  }
  try {
    await staffRequest("/api/logs/client", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
  } catch {
    // Client reporting must never break the admin UI.
  }
}

const ERROR_CLASSES = new Set([
  "Error",
  "TypeError",
  "ReferenceError",
  "SyntaxError",
  "RangeError",
  "URIError",
  "EvalError",
  "AggregateError",
  "DOMException",
  "AbortError",
  "NetworkError",
  "UnhandledRejection",
])

export const safeClientErrorMessage = (value: unknown, fallback: string): string =>
  value instanceof Error && ERROR_CLASSES.has(value.name) ? value.name : fallback

export const installClientErrorReporting = () => {
  const onError = (event: ErrorEvent) => {
    void reportClientLog({
      event: "ui_window_error",
      error_class: safeClientErrorMessage(event.error, "Error"),
      line: event.lineno,
      column: event.colno,
    })
  }

  const onRejection = (event: PromiseRejectionEvent) => {
    const reason = event.reason
    void reportClientLog({
      event: "ui_unhandled_rejection",
      error_class: safeClientErrorMessage(reason, "UnhandledRejection"),
    })
  }

  window.addEventListener("error", onError)
  window.addEventListener("unhandledrejection", onRejection)
  return () => {
    window.removeEventListener("error", onError)
    window.removeEventListener("unhandledrejection", onRejection)
  }
}

export const ClientErrorReporter = () => {
  useEffect(() => installClientErrorReporting(), [])
  return null
}
